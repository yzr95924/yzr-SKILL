# MEMORY/

跨会话"为什么 + 边界规则"的纯索引（L2 SSOT）；索引同步内联进 `AGENTS.md`「跨会话记忆」段（三家 agent 读 AGENTS.md 即见），正文按需 `Read`（`MEMORY/<slug>.md`，同级）。新条目追加末尾并同步内联副本。

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

### outline MCP 工具加 settings.local.json 白名单

新装 outline MCP 时同步加 `mcp__outline__*` 白名单（避免大文档写入被 classifier 拦）；退路走 REST。 → [正文](outline-mcp-permission-allowlist.md)

### SKILL 代码仓优先级：源 > MEMORY > vendor

npx 分发包只含 SKILL 目录，影响行为的规则必须落 SKILL 源；MEMORY 不分发、vendor 是派生副本。 → [正文](skill-source-priority-over-memory-vendor.md)

### paper-wiki 整合：本地与远端解耦

llm-wiki-management 只管本地复利，远端发布独立成 skill；producer（gemini-paper-summary）不假设 consumer。 → [正文](paper-wiki-integration-design.md)

### gemini-paper-summary --full 模式 4 个设计决策

--full 产全量转储当 raw 底座（D1-D4）；layout 基于 Karpathy 模式可识别性，不为特定 consumer。 → [正文](gemini-paper-summary-full-mode-design.md)

### gemini-pdf-summary manual / whitepaper 改 full 风格（2026-07-05 翻面）

manual / whitepaper / book 是给 LLM 消费的下游产物（供 llm-wiki 二次 ingest），按 PDF 原生章节顺序全文级转写；只有 paper quick 是给人看的精炼速读。模板 + 自检函数 + 文档已对齐，脚本对 book 的 latent 路由 bug 已顺手修。 → [正文](gemini-pdf-summary-manual-whitepaper-full-design.md)

### gemini-pdf-summary paper --full 单产物（2026-07-07 翻面）

`paper --full` 从"双产物 quick+full"翻为"单产物 full"——与 manual / whitepaper / book 4 类 full 产物形态对齐（单文件 + LLM 消费底座）；quick 与 full 完全解耦，独立触发。supersede 旧 `gemini-paper-summary-full-mode-design.md` §1 (D1) + §2。 → [正文](gemini-pdf-summary-paper-full-single-output.md)

### H1 transform：publish 时注入，local 无 H1（parked）

Gemini 产物保持无 H1（标题在 outline title 字段）；H1 由未来 publish skill 推送时注入，不回写 local。 → [正文](h1-transform-publish-time-inject.md)

### ddnsto relay 仅 HTTPS 443 才透到上游

走 ddnsto 隧道的 MCP endpoint 必须用 `https://`（HTTP 80 是 Caddy 占位假响应）；首次给 http:// 直接试 https://。 → [正文](ddnsto-relay-https-only-quirk.md)

### Outline MCP 吃掉 --- frontmatter

Outline 把 `---` YAML frontmatter 解析丢字；OKF 元数据走 yaml 代码围栏，title 由 Outline 字段承载。 → [正文](outline-mcp-strips-yaml-frontmatter.md)

### 影响分发后行为的经验必须进 SKILL

新踩的坑/经验先进 SKILL 后 MEMORY；判定"另一台机器 npx 装的用户能自己解决吗"，不能则必须进 SKILL。 → [正文](experience-affecting-skill-distribution-goes-to-skill-not-memory.md)

### 部分 agent 截断 MCP 多 content block

部分 agent 的 MCP 客户端只采纳首个 text block、丢弃其后；outline 读完整正文走 REST
`POST /api/documents.info`，元数据仍用 fetch。 → [正文](agent-mcp-truncates-multiblock.md)

### 字数限制用"字符"单一单位

论文总结字数上限只用"字符"（含中英文/空格/标点），不用"词"或"中文字符"，避免换算歧义。 → [正文](prompt-length-unit-character.md)

### gemini-paper-summary 图片提取边界与设计决策

Stage 2 视觉定位/坐标约定/caption 写 alt/quick 默认带图等图片提取全部设计决策与边界 case。 → [正文](gemini-paper-summary-figure-extraction-edges.md)

### wiki-spec ↔ workspace-spec type enum 耦合

workspace-spec §13 type 表"复用 wiki-spec §9"——改 wiki-spec type enum（如 0.6.0 删 type:memory）时必须同步查
workspace-spec §13 / §9.1，否则"复用"引用悬空。 → [正文](wiki-workspace-spec-type-coupling.md)

### wiki/workspace 纪律文件 AGENTS.md SSOT + CLAUDE.md 薄壳（0.11.0/0.4.0）

套用 yzr-multi-agent-context 方法：纪律 SSOT 从 `<root>/CLAUDE.md` 改 `AGENTS.md`（工具无关）+ `CLAUDE.md` 薄壳；
@import 归 AGENTS.md、版本在 AGENTS.md；lint 优先 AGENTS.md fallback CLAUDE.md + `claudemd-to-agents-md-split` 迁移。
两 spec 对称，改 SSOT 引用同步两 skill + 模板 + canonical/fixtures。 → [正文](wiki-spec-0-11-agents-md-ssot.md)

### yzr-skill-creator 审计/归档记录不要每次都写

按入口 4（原则校验）跑完检查后**直接交付结果 + 修复**就行——不要每次都把"audit-YYYY-MM-DD.md"那种报告归档到 skill 目录。用户没主动要 audit 文档时，结论放在回复里、修复改在文件里，不留 audit 文件也不写 MEMORY 历史。

### 设计优化阶段以 repo 内 SKILL 描述为准（2026-07-07）

设计优化（重构 / bump / 调整路径 / 重新设计）只动仓库源——vendor 副本（`~/.agents/skills/`）是 npx install 派生的，注定被覆盖；不要读 / diff / 补 vendor。回答"当前 spec / schema / finding 是什么"一律 `Read` 当前 repo 的文件，不引用 vendor / 训练记忆 / web cache 里的旧版。日常维护型编辑（修 typo / 调 description）才走 [[skill-edits-sync-to-repo-source]] 的同步流程。 → [正文](design-optimization-ignore-vendor-state.md)

### markdownlint 从 skill 子目录跑会 MD013 假阳性

`markdownlint <file>` 从 skill 子目录跑时，markdownlint-cli 不向上查找仓库根 `.markdownlint.jsonc`，退回默认 line_length 80 → 正常行被误报 MD013。从仓库根跑，或 `-c .markdownlint.jsonc` 显式指定 config。另：MD060（compact 表格竖线 `|---|` 无空格）是仓库全局既存噪音（`.markdownlint.jsonc` 用 `default:true` 未配 MD060），每个表格都触发、非新引入——判回归只看有无 **新错误类别**（如新出现 MD013/MD041），MD060 计数变化不算回归。
