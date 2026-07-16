# MEMORY/

跨会话"为什么 + 边界规则"的纯索引（L2 SSOT）；`AGENTS.md` 的「跨会话记忆（索引）」段用单行
`@MEMORY/MEMORY.md` 引入——自动展开 `@import` 的 agent 读入全文，不展开的由 AGENTS.md **顶部
强制 Read 指令**兜底（不再靠段内 HTML 注释）；正文按需 `Read`（`MEMORY/<slug>.md`，同级）。
新条目追加到本文件末尾即可，无需同步副本——只活这一份，AGENTS.md 单行引用负责把"指针"挂到 L1。

> 本文件是项目级规则的**唯一**真源；agent 会话级 memory 只放指向本文件的指针，不再持有内容副本，避免跟代码仓迁移时失同步。

## 规则

### Python 最低 3.7

新脚本最低支持 Python 3.7（2026-07-01 起放弃 CentOS 7/3.6 兼容，与 pyproject target-version 对齐）。 → [正文](python-min-3-7.md)

### 后续脚本优先 Python 3 而非 shell

新脚本首选 Python 3（便于生态统一），仅一行管道/纯文本流场景用 shell。 → [正文](python-preferred-over-shell.md)

### SKILL 描述类修改默认同步仓库源

改 SKILL.md/references/scripts 前默认目标是仓库源（非 vendored 副本），改完 `cp` 回源并用 `git` 确认。 → [正文](skill-edits-sync-to-repo-source.md)

### SKILL 源 vs 运行时 vendor

SKILL.md 有仓库源 + vendored 副本两份独立文件，改源才进 git、才随 npx 分发。 → [正文](skill-source-vs-runtime-vendor.md)

### 影响 SKILL 输出的"为什么"必须同步到 SKILL 源

MEMORY 只记"为什么"；影响输出/行为的决策必须显式落到 SKILL.md/assets/scripts，否则下次触发就丢。 → [正文](memory-synced-to-skill-source.md)

### SKILL 代码仓优先级：源 > MEMORY > vendor

npx 分发包只含 SKILL 目录，影响行为的规则必须落 SKILL 源；MEMORY 不分发、vendor 是派生副本。 → [正文](skill-source-priority-over-memory-vendor.md)

### H1 transform：publish 时注入，local 无 H1（parked）

Gemini 产物保持无 H1（标题在 outline title 字段）；H1 由未来 publish skill 推送时注入，不回写 local。 → [正文](h1-transform-publish-time-inject.md)

### 影响分发后行为的经验必须进 SKILL

新踩的坑/经验先进 SKILL 后 MEMORY；判定"另一台机器 npx 装的用户能自己解决吗"，不能则必须进 SKILL。 → [正文](experience-affecting-skill-distribution-goes-to-skill-not-memory.md)

### wiki-spec ↔ workspace-spec type enum 耦合

workspace-spec §13 type 表"复用 wiki-spec §9"——改 wiki-spec type enum（如 0.6.0 删 type:memory）时必须同步查
workspace-spec §13 / §9.1，否则"复用"引用悬空。 → [正文](wiki-workspace-spec-type-coupling.md)

### wiki/workspace 纪律文件 AGENTS.md SSOT + CLAUDE.md 薄壳（0.11.0/0.4.0）

套用 yzr-multi-agent-context 方法：纪律 SSOT 从 `<root>/CLAUDE.md` 改 `AGENTS.md`（工具无关）+ `CLAUDE.md` 薄壳；
@import 归 AGENTS.md、版本在 AGENTS.md；lint 优先 AGENTS.md fallback CLAUDE.md + `claudemd-to-agents-md-split` 迁移。
两 spec 对称，改 SSOT 引用同步两 skill + 模板 + canonical/fixtures。 → [正文](wiki-spec-0-11-agents-md-ssot.md)

### yzr-skill-creator 审计/归档记录不要每次都写

按入口 4（原则校验）跑完检查后**直接交付结果 + 修复**就行——不要每次都把
"audit-YYYY-MM-DD.md" 那种报告归档到 skill 目录。用户没主动要 audit 文档时，结论放在回复里、
修复改在文件里，不留 audit 文件也不写 MEMORY 历史。

### run_eval / run_loop 并行克隆冲突（harness 结构性缺陷）

ProcessPoolExecutor(10 workers) 并行跑评测时，10 个 _eval_skill_<uuid> 克隆（描述相同）共存，
模型任意调用其中一个，grader 只认分配给当前查询的克隆 → recall 结构性压到 ~6%（即使直接
probe 单克隆能 100% 触发）。已安装 skill 还多一层"真 skill 偷调用"冲突。修法见正文：grader 改
为认任一 _eval_skill_<hex> 命中即触发（已实测：recall 从 6% 升到 56% Train / 42% Test）。
**本机曾未跑通过 run_loop**（修前全系统 0 个 iteration-* / best_description commit）——
其它 skill 描述"看着 OK"是因为根本没经过优化，harness 缺陷从未暴露。修 grader 后实测有效。 →
[正文](run-eval-harness-parallel-clone-collision.md)

### 设计优化阶段以 repo 内 SKILL 描述为准（2026-07-07）

设计优化（重构 / bump / 调整路径 / 重新设计）只动仓库源——vendor 副本（`~/.agents/skills/`）是
npx install 派生的，注定被覆盖；不要读 / diff / 补 vendor。回答"当前 spec / schema / finding 是什么"
一律 `Read` 当前 repo 的文件，不引用 vendor / 训练记忆 / web cache 里的旧版。日常维护型编辑
（修 typo / 调 description）才走 [[skill-edits-sync-to-repo-source]] 的同步流程。 →
[正文](design-optimization-ignore-vendor-state.md)

### markdownlint 从 skill 子目录跑会 MD013 假阳性

`markdownlint <file>` 从 skill 子目录跑时，markdownlint-cli 不向上查找仓库根 `.markdownlint.jsonc`，
退回默认 line_length 80 → 正常行被误报 MD013。从仓库根跑，或 `-c .markdownlint.jsonc` 显式指定 config。
另：MD060（compact 表格竖线 `|---|` 无空格）是仓库全局既存噪音（`.markdownlint.jsonc` 用
`default:true` 未配 MD060），每个表格都触发、非新引入——判回归只看有无 **新错误类别**
（如新出现 MD013/MD041），MD060 计数变化不算回归。
