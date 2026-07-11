# {{TOPIC_NAME}} Wiki — Claude Code 维护守则（薄壳）

> 本 wiki 的纪律**单一真源是 [`AGENTS.md`](AGENTS.md)**（工具无关）。本文件只是让 Claude Code 自动加载
> 它的薄壳——Claude Code 在 wiki 根目录启动时读 `CLAUDE.md`，`@AGENTS.md` 递归展开引入全部纪律 +
> 其正文内联的「跨会话记忆（索引）」与「Wiki-local scripts（索引）」两段（0.23.0+ 改：之前用
> `@MEMORY/MEMORY.md` + `@scripts/SCRIPTS.md` import——但 `@import` 只 Claude Code 展开，
> Codex / Qoder / Gemini CLI 不展开，wiki 对它们不可见。现已内联进 `AGENTS.md` 正文）。
>
> **改纪律请改 `AGENTS.md`，不要改本文件。** 用其他 agent（Codex / Gemini CLI 等读 `AGENTS.md` 的 agent）
> 维护本 wiki 时直接读 `AGENTS.md`，本文件不参与。

@AGENTS.md
