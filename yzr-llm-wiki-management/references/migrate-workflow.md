# Migrate（升级 wiki spec）详细流程

> 本文件从 `SKILL.md` §5 Migrate 整段下沉而来——主 SKILL.md 留 pointer 即可，
> 详细流程按需 Read 本文件。SSOT 是 [`wiki-spec.md` 附录 B](wiki-spec.md#附录-b版本历史)
> （迁移依据每行写在那边），本文件是 agent 视角的执行流。

## 触发

用户说"升级 wiki / 迁移 / 检查 wiki 版本 / 老格式 / spec 升级 / 是否需要
reformat"；或 `lint_wiki.py` 报告 `legacy-confidence-field` 等迁移期 warn。

## 为什么需要这一步

[`wiki-spec.md` §10](wiki-spec.md#10-版本钉死) 规定每个 wiki 仓在
`<wiki-root>/AGENTS.md` §八 钉一份 `Wiki Spec 版本`（CLI init 时从 SKILL 仓
`metadata.wiki_spec_version` 镜像）。spec 演进时（0.5.0 → 0.6.0 → 0.7.0…）
老 wiki 会**有意识地保留**部分旧字段（如 `confidence`）——避免一刀切破坏用户沉淀的内容。
本节定义**检测 + 自动修复**的 workflow：让用户/agent 对着一份"按 spec 升级的清单"逐项
把 wiki 推到与 SKILL 仓一致的格式。

## 职责切分（**关键**——避免与 ingest / lint 混淆）

- **脚本**（`scripts/lint_wiki.py --check-version`）= 探测器。只扫不修，输出报告 / 落盘
  `.migration-plan.json`，**不**改任何 wiki 内容
- **agent**（本节定义）= 修复者。按 `.migration-plan.json` + `wiki-spec.md` 附录 B 用
  Edit/Write 改 frontmatter / 移文件 / 补索引 / 改 AGENTS.md §八
- **`wiki-spec.md` 附录 B** = SSOT。每行写明"老 wiki 迁移"的依据；agent 与脚本都引用
- **不**追加 log 条目——迁移是脚本运行，不是 wiki 操作事件（与 `--migrate-confidence` 一致）

## 流程（agent 驱动，与 SKILL.md §1-§4 风格一致）

1. **操作前置**：跑 orient ritual（AGENTS.md + `wiki/index.md` + `wiki/log.md` 最近 ~30 行）
2. **跑探测**：

   ```bash
   python3 scripts/lint_wiki.py "$LLM_WIKI_ROOT" --check-version
   ```

   - 解析 `<wiki-root>/AGENTS.md` §八 "Wiki Spec 版本"——拿到 `current_spec`
   - 与 SKILL 仓 `metadata.wiki_spec_version`（`scripts/lint_wiki.py` 顶部常量
     `CURRENT_WIKI_SPEC`）比对：相等 / 老 / 新
   - 扫已知 legacy 现场：老字段（`confidence`）+ 其它受 spec 演进影响的内容（详见
     [wiki-spec 附录 B](wiki-spec.md#附录-b版本历史)）
     - 退役 `type` 值（`type: memory`）
   - 标记冲突页（同时含老字段与新字段）→ `conflicts[]`，**agent 不覆盖**
3. **dry-run 报告**（默认必走）：
   - 按 legacy pattern 分组列"哪些文件需改、依据 wiki-spec.md 附录 B 哪行"
   - 冲突页单独标红，**绝不自动覆盖**——等用户裁定
   - 询问用户：应用全部 / 部分应用 / 仅看清单
4. **生成 plan**（用户同意应用时）：

   ```bash
   python3 scripts/lint_wiki.py "$LLM_WIKI_ROOT" --check-version --apply
   ```

   落盘 `<wiki-root>/.migration-plan.json`——含 `actions[]`（每个含 file / type /
   rule_ref / remove / add_or_modify）+ `skipped_conflicts[]` + `agent_rules[]`。
   若 plan 已存在 → 拒绝覆盖，提示用户删除或改名。
5. **执行修复**（agent 用 Edit/Write）：
   - 按 `actions[]` 顺序逐项修；每个 action 前打印依据 `rule_ref`
   - `frontmatter-rename`：Edit 改 frontmatter（删老字段、加新字段；**不动 `updated`**）
   - `file-move`：先读源 → 写目标 → 删源
   - `frontmatter-retype`：按 `action.note` 与 `wiki-spec §5.2` 决定具体改法
   - **跳过 `skipped_conflicts[]`**——永不自动覆盖人工决策
6. **改 `<wiki-root>/AGENTS.md` §八 "Wiki Spec 版本"**：
   - 用 Edit 替换为 `to_version`（其它字段不动）
   - 这是**迁移本身**的操作，**不**触及 reviewed 戳机制（AGENTS.md 不参与 SKILL.md
     核心原则 §10 的 `reviewed-stale` 兜底）
7. **验证**：重跑 `lint_wiki.py --check-version`：
   - 若 `needs_migration == false` 且无残留 legacy → 告知用户完成
   - 若仍有 → 报告残留 pattern + 转人工
8. **清理临时文件**（验证通过后，保证 wiki 干净）：删 `<wiki-root>/.migration-plan.json`
   + 升级过程产出的 `*.bak` 备份。两者都是升级中间产物——plan 已执行完毕、anchor 重写
   备份已无需回滚；残留无意义且 `.gitignore` 已忽略它们（`.migration-plan.json` / `*.bak`）。

   ```bash
   rm "$LLM_WIKI_ROOT/.migration-plan.json"
   find "$LLM_WIKI_ROOT" -maxdepth 2 -name '*.bak' -delete
   ```

   > **何时不删**：升级中途暂停（plan 未执行完 / 待人工裁定冲突页）时保留 `.migration-plan.json`，
   > 它是续跑的依据；只有 step 7 验证通过（`needs_migration == false`）才删。
9. **不**追加 log 条目 / **不**触发 ingest / query / lint（保持职责单一）

## `--json` 联用

把报告 + plan 一起输出 JSON，给 agent 程序化消费（CI / 编排场景）。
默认人读报告（含 `[LEGACY]` / `[CONFLICTS]` 分组 + `[HINT]` 提示加 `--apply`）。

## 边界

- **不**修改 `raw/` 下任何文件（即便用户要求）——延续 SKILL.md 核心原则 §1 的 LLM 只读纪律
- **不**删除 wiki 内容（即便 raw 已不存在 source 页）——用 `archived: true` 替代
- **不**对 MEMORY 索引做"自动补行"以外的改动——MEMORY.md 是 LLM 私有记忆清单
- **不**改 `wiki/log.md` / `wiki/index.md` frontmatter（4 字段 reserved，迁移不触及）
- **不**在迁移过程中调用 ingest / query / lint（保持职责单一）
- **冲突页绝不自动覆盖**（已在 step 3 / step 5 双重保险）
- **不**给迁移追加 log 条目——迁移是脚本运行，不是 wiki 操作事件
- **`current_spec > skill_spec`**（wiki 比 SKILL 新）：**不**阻断，告警用户升级 SKILL 仓；
  **不**改 wiki

## fixtures 字段更新清单（0.20.0+）

> **本节回答"升级时每个约定文件要对齐什么"**——集中一处，避免散落在 SKILL.md / spec 附录 B。
> 权威信号清单是 `scripts/check_wiki_fixtures.py` 的 `SKELETON_SPECS` + `CHECK_REGISTRY`（数 = SKILL.md `metadata.fixtures_check_count`）；
> 本节只做 agent 视角的分类与指路，**不重抄字段名**（否则三处漂移）。

升级 wiki spec 时，约定文件（fixtures）必须对齐当前 spec 的骨架。`check_wiki_fixtures.py`
读 `references/canonical/` + `references/fixtures/gitignore.txt` 作 SSOT 做字段级骨架比对
（改 fixtures → check 自动跟随）。

### 纯骨架件（结构不变，只追加 bullet/段/行）—— 全字段骨架比对

| 文件 | 骨架信号源 | 成长内容（迁移**不动**） |
| --- | --- | --- |
| `.gitignore` | `fixtures/gitignore.txt` | 用户自定义新增规则 |
| `MEMORY/MEMORY.md` | `canonical/memory-index.md` | `## 索引` 下经验条目 |
| `scripts/SCRIPTS.md` | `canonical/scripts.md` | `## 索引` 下脚本段 |
| `wiki/tags.md` | `canonical/tags.md` | tag bullet 列表（tags 无 `## 索引`，直接 bullet） |

→ 升级时：脚本查 H1 + 说明块（`>` 引用）+ `## 索引`（tags 除外）+ `.gitignore` 段结构
（OS/编辑器 + Obsidian + 临时文件 三段齐全，各 ≥1 规则）；缺则产 `fixtures-fix-skeleton`
action，agent 单 Edit 补结构骨架，**不动成长内容**。

### 成长型件（只比"结构必填"，不动成长内容）

| 文件 | 结构必填骨架 | 成长内容（永不触碰） |
| --- | --- | --- |
| `wiki/index.md` | frontmatter 6 键（title/type/okf_version/tags/created/updated）+ H1（`# <topic> Wiki`）+ 说明块 + 5 类别标题 | 类别下 source/entity/concept 条目 |
| `wiki/log.md` | frontmatter 5 键（title/type/tags/created/updated）+ `## [date] op \| title` 行格式 | 历史 log 条目（lint-checklist §5.5 永不修） |

→ 升级时：脚本只比结构骨架（frontmatter 键 + H1 + 行格式）；成长内容由 LLM 按
ingest/query 流程维护，迁移不触及。

### .gitignore 段结构（容忍定制）

`gitignore-init-rules-complete` 只查**段注释齐全 + 每段 ≥1 规则**，不绑死具体规则行——
容忍用户删自己不用的编辑器规则（只用 VSCode 的删 `.idea/`、纯 Linux 的删 `.DS_Store`）。
但**临时文件段的 `.migration-plan.json` 建议保留**（升级中间产物的中断保险）；即便漏掉，
升级末尾 step 8 的 `rm` 也会清掉 plan，双重保险。

### 权威源指针

- 骨架信号定义：`scripts/check_wiki_fixtures.py` 的 `SKELETON_SPECS` + `CHECK_REGISTRY`
- 字节金标准：`references/canonical/*.md`（`.gitignore` 见 `references/fixtures/gitignore.txt`）
- 语义合并（跨条目归并）：lint-checklist §五（与本文件同源）

## 与现有 lint 检查的协同

- 迁移后会**自然清理** `legacy-confidence-field` warn（lint §二.13.C）
- 迁移**不**触及 `reviewed-stale` warn（页面正文未改，仅字段重命名；按 SKILL.md
  核心原则 §10 "LLM 修改页面正文"边界，本操作属于元数据重命名，不算正文修改——但若用户谨慎，
  可在迁移后跑 `lint_wiki.py --severity warn` 让人工审视 reviewed 戳）
- 与 `--migrate-confidence`（0.5.0→0.7.0 单点硬编码迁移）的关系：`--migrate-confidence`
  保留仅供旧用法兼容；新流程一律走 `--check-version --apply`（覆盖其功能 + 范围更广）

## 完整样例

见 [`examples.md`](examples.md) §五（"检查 wiki 是否需要升级到最新 spec"）。
