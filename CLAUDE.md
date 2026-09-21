# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

> **薄壳声明**：项目上下文的**单一真源是 `AGENTS.md`**——本文件用 `@AGENTS.md` 引入全部共用内容。
> 改内容请改 `AGENTS.md`；本文件只承载 Claude 专属、无法泛化的逃生舱内容（见下方），勿在此编辑共用部分。

@AGENTS.md

<!-- Claude Code 专属（以下为无法泛化为工具无关的内容，AGENTS.md 不含此部分） -->

- `.claude/settings.local.json#permissions.allow` 已预批准一组 MCP / Bash 权限（Gemini Docs
  MCP、`pip install *`、`python3 *` 等），新增依赖工具时若需新权限需走 `update-config` skill。
- `~/.claude/skills/<name>` 是 vendored 副本软链（→ `~/.agents/skills/<name>`，
  `.agents/` 是 npx install 出来的真目录）——改 SKILL 必须改仓库源（`<skill-name>/`），
  不能只改这里。
