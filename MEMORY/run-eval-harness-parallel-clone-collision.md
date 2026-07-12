---
name: run-eval-harness-parallel-clone-collision
description: run_eval.py / run_loop.py 在已安装的 skill 上评测会结构性压低 recall——ProcessPoolExecutor 把 10 个查询并行跑，每个查询注入 1 个 _eval_skill_<uuid> 克隆（描述相同），子进程看到 10 个同名描述匹配项会任意调用其中一个，grader 只认分配给当前查询的克隆→多数触发被计为 miss。
metadata:
  type: project
---

# run_eval / run_loop 并行克隆冲突（harness 结构性缺陷）

## 问题（已实证）

`yzr-skill-creator/scripts/run_eval.py` 用 `ProcessPoolExecutor(max_workers=10)` 并行跑评测。
每个查询在 `~/.claude/skills/_eval_skill_<uuid>` 注入一个带候选描述的克隆版本，跑完 `claude -p`
后清理该克隆（`run_eval.py:221-222` 的 rmtree）。但并行阶段任意瞬间会有最多 10 个克隆**共存**，
且全部带**相同**的候选描述（同一迭代），仅名称不同。

`claude -p` 子进程会从 `~/.claude/skills/` 发现全部 10 个克隆版本，看到 10 个描述相同的"匹配项"，
任意调用其中一个。`run_eval.py:228` 的 grader 只在工具输入里出现**分配给当前查询的**
`clean_name` 时计"触发"——模型选了其它 9 个克隆中任意一个都算 miss。

**症状**：跑一次 5 轮 iteration 的 loop，每轮 train/test `recall` 都被结构性压低（实测 ~6%），
即使直接用一条 should-trigger 查询 probe 单克隆能 100% 触发也无济于事。

## 另一层冲突（已修）

被测 skill 如果已用真名装在 `~/.claude/skills/`（项目内 skill 多为此情况，symlink 形式
`~/.claude/skills/<name> -> ~/.agents/skills/<name>`），模型会**直接调用真名 skill**而不碰
克隆版本，grader 永远 0% 召回。修法：跑 loop 期间临时 `mv` 真 skill 软链接到 `/tmp/<name>.bak`，
跑完 `mv` 回（`~/.claude/skills/` 是唯一发现入口；`.agents/skills/` 不被独立扫描）。

但修了这一层后，上面那层并行克隆冲突仍然存在——`recall` 只从 0% 升到 ~6%。

## 临时绕过

- `--num-workers 1` 跑 loop：串行消除并行克隆冲突。但每轮 12 train + 8 test = 20 个查询
  × 3 runs = 60 次 `claude -p`（每条 ~80s+）→ 单轮 ~80 min，5 轮 ~6.5 h。慢但信号可信。
- 适合"描述触发明显不准、要精修"的场景。

## 真正的修法（建议改 run_eval.py）

让 grader 认"**任一** `_eval_skill_*` 出现在工具输入"即计触发。当前 `clean_name in accumulated_json`
改为 `re.search(r"_eval_skill_[a-f0-9]+", accumulated_json) is not None`。改动 ~1 行，
保留"调用了某个 _eval_skill_* = 触发"语义，不限定 uuid（uuid 是 harness 内部细节，对评测语义无意义）。

**为什么 uuid 是 harness 内部细节**：eval 注入的克隆在模型视角就是"一个带某描述的 skill"，
模型选哪个是它的偏好；评测关心"模型是否在 N 个匹配项里挑了同类"，不该因为挑的不是分配给
当前查询的那一个就计 miss。

## 修法实测（2026-07-12）

修 grader 为 `EVAL_SKILL_PATTERN = re.compile(r"_eval_skill_[a-f0-9]{8}")`（8 hex 匹配
`uuid.uuid4().hex[:8]`），yzr-multi-agent-context 入口 3 跑 5 轮：

| Iter | Train recall | Train acc | Test recall | Test acc |
|---|---|---|---|---|
| 1（原描述 baseline） | 22% | 61% | 17% | 58% |
| 2 | **56%** | **78%** | 33% | 67% |
| 3 | 56% | 78% | 17% | 58% |
| 4 | 56% | 78% | **42%** | **71%** |
| 5 | 44% | 72% | 17% | 58% |

Iter 2/4 并列 test_passed=6/8（75%）—— loop 按 `max(history, key=test_passed)` 选 iter 2 为
`best_description`（first-in-order tie-break）。修改 commit 见 yzr-skill-creator/scripts/run_eval.py
（`EVAL_SKILL_PATTERN` 常量 + 4 处 grader 替换）。

**对比基线（修前同环境）**：recall 6% / 100% precision → 修复后 baseline iter 1 recall 22%，
iter 2+ 56%+。结构性缺陷确认是 recall 压低的主因。

## 影响

- 对所有**已安装**的 skill（yzr-skill-creator / yzr-multi-agent-context / yzr-gemini-pdf-summary /
  yzr-outline-wiki-* / yzr-llm-* / yzr-code-refactoring-review / 任何第三方装在 `~/.claude/skills/`
  的 skill）跑描述优化，harness 都会产生噪声。
- 对**未安装**的 skill 跑描述优化（如新写的 skill 还没分发），并行克隆冲突仍然存在（10 个
  相同描述的克隆），只是没有"真 skill 偷调用"那一层——recall 会比 0% 好但仍偏低。

## 元发现：本机从未跑通过 run_loop（2026-07-12 实证）

全系统 `find` 验证：

- 0 个 `iteration-*` workspace 目录
- 0 个 `history.json` / `benchmark.json`
- 0 个 `yzr-skill-creator-workspace/`（yzr-skill-creator 自己从来没跑过 entry 3）
- `git log -G "best_description"` 0 匹配（从未 commit 过 loop 产出）
- `git log -G "test 6/6"` 0 匹配（`05ec12c TUNE: yzr-skill-creator description → test 6/6 (202 tokens)`
  的 "test 6/6" 是 commit message 里的备注文字，没有对应的产物/产物路径/产物 JSON）

**结论**：此环境（`glm-5.2[1m]` + `claude -p` + `ProcessPoolExecutor(10)`）下 `run_loop.py`
从未被成功使用过。其他 skill 的描述为什么"看着 OK"——是因为它们**根本没经过描述优化**，
所以 harness 缺陷从未暴露。`trigger_eval.json` 文件存在（`yzr-code-refactoring-review/eval/trigger_eval.json`）
但没有被 run_loop 消费过的证据（无 iteration 工作区、无 best_description commit、无 history.json）。

**含义**：下次有人说"别的 skill 跑 loop 没问题"——这不是事实，是**从未跑过**。在此环境想真
正优化描述，必须按上述"真正的修法"改 grader，或 `--num-workers 1` 跑慢模式。

## 适用

- 入口 3（描述优化）跑 `run_loop.py` 之前先判断：被测 skill 是否已安装？若已装，预期产出
  recall < 真实触发率；用直接 probe（手动注入单克隆跑 1 条 query 看 tool_use）作 ground truth。
- 若要让 loop 产出可信信号，按"真正的修法"改 grader（推荐）或临时 `--num-workers 1`（慢）。

## 实证记录

- 2026-07-12 跑 yzr-multi-agent-context 描述优化
- 直接 probe `_eval_skill_probe` + 单查询：模型 100% 触发克隆（`Skill` tool_use
  `{"skill": "_eval_skill_probe"}`）
- 同一描述放 loop 里跑：5 轮每轮 `recall≈6%`、`precision=100%`（典型"模型调用了 _eval_skill_*
  但不是分配的那一个"信号）
- 确认 `run_eval.py:17, 244, 312`：`ProcessPoolExecutor` + `--num-workers=10` + `as_completed`，
  per-query 克隆有 rmtree（line 221-222）但并行阶段 N 个克隆共存
