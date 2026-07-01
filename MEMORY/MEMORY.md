# MEMORY/

跨会话需要持久化的"为什么"与边界规则。本文件是**纯索引**：每条 = 标题 + 一句话 + 正文指针，经 CLAUDE.md 对本文件的 import 在会话启动时自动常驻；正文按需 `Read`（`MEMORY/<slug>.md`，与本文件同级）。新条目追加在末尾。

> 本文件是项目级规则的**唯一**真源。Claude 会话级 memory（`~/.claude/projects/.../memory/`）只放指向本文件的指针，不再持有内容副本，避免跟代码仓迁移时失同步。

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

### H1 transform：publish 时注入，local 无 H1（parked）

Gemini 产物保持无 H1（标题在 outline title 字段）；H1 由未来 publish skill 推送时注入，不回写 local。 → [正文](h1-transform-publish-time-inject.md)

### ddnsto relay 仅 HTTPS 443 才透到上游

走 ddnsto 隧道的 MCP endpoint 必须用 `https://`（HTTP 80 是 Caddy 占位假响应）；首次给 http:// 直接试 https://。 → [正文](ddnsto-relay-https-only-quirk.md)

### Outline MCP 吃掉 --- frontmatter

Outline 把 `---` YAML frontmatter 解析丢字；OKF 元数据走 yaml 代码围栏，title 由 Outline 字段承载。 → [正文](outline-mcp-strips-yaml-frontmatter.md)

### 影响分发后行为的经验必须进 SKILL

新踩的坑/经验先进 SKILL 后 MEMORY；判定"另一台机器 npx 装的用户能自己解决吗"，不能则必须进 SKILL。 → [正文](experience-affecting-skill-distribution-goes-to-skill-not-memory.md)

### Claude Code 截断 MCP 多 content block

CC 只采纳 MCP 首个 text block、丢弃其后；outline 读完整正文走 REST `POST /api/documents.info`，元数据仍用 fetch。 → [正文](claude-code-mcp-truncates-multiblock.md)

### 字数限制用"字符"单一单位

论文总结字数上限只用"字符"（含中英文/空格/标点），不用"词"或"中文字符"，避免换算歧义。 → [正文](prompt-length-unit-character.md)

### gemini-paper-summary 图片提取边界与设计决策

Stage 2 视觉定位/坐标约定/caption 写 alt/quick 默认带图等图片提取全部设计决策与边界 case。 → [正文](gemini-paper-summary-figure-extraction-edges.md)

### wiki-spec ↔ workspace-spec type enum 耦合

workspace-spec §13 type 表"复用 wiki-spec §9"——改 wiki-spec type enum（如 0.6.0 删 type:memory）时必须同步查 workspace-spec §13 / §9.1，否则"复用"引用悬空。 → [正文](wiki-workspace-spec-type-coupling.md)
