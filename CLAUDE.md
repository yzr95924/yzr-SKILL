# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

> **薄壳声明**：项目上下文的**单一真源是 `AGENTS.md`**——本文件用 `@AGENTS.md` 引入全部共用内容。
> 改内容请改 `AGENTS.md`；本文件只承载 Claude 专属、无法泛化的逃生舱内容（见下方），勿在此编辑共用部分。

@AGENTS.md

<!-- Claude Code 专属（以下为无法泛化为工具无关的内容，AGENTS.md 不含此部分） -->

- `yzr-skill-creator/scripts/run_eval.py` 与 `improve_description.py` 调用 `claude -p` 子进程
  跑评估 / 描述优化——需本机已安装并登录 Claude Code（`claude` CLI 不可用时脚本会直接报错）。
- `.claude/settings.local.json#permissions.allow` 已预批准一组 MCP / Bash 权限（Gemini Docs
  MCP、`pip install *`、`python3 *` 等），新增依赖工具时若需新权限需走 `update-config` skill。
- `~/.claude.json#mcpServers.outline` 是当前 session 的 Outline MCP 配置文件路径，token 与
  `~/.claude/skills/outline-wiki-setup` 装填的 setup 当时一致。
- 部分 agent（包括当前 Claude Code）会截断 MCP `fetch` 多 content block——读 outline 文档完整
  正文需走 REST `POST /api/documents.info` 旁路（详见 [[agent-mcp-truncates-multiblock]]）。
