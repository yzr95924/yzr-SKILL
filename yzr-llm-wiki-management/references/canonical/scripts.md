# Scripts

> 本目录存放本 wiki 自维护的脚本（项目级 ingest 扩展 / 外部 CLI 胶水 / 自动化 hook）。
>
> **加载机制（0.23.0+ 改）**：AGENTS.md 顶部 `#### Wiki-local scripts（索引）` 段**内联**本文件
> `## 索引` 段下的 one-liner 列表（每行：`- \`<name>\` — <一句话用途>`），让所有读 `AGENTS.md` 的
> agent（Claude Code / Codex / Qoder / Gemini CLI）都能立即看到有哪些脚本；完整分节契约
> （每脚本一段：使用场景 / 调用约定 / 作用 / 前置依赖）仍在本文件 `## 分节契约` 段，agent 按需
> `Read` 对应分节。脚本增删时**同步改两处**（AGENTS.md 紧凑索引行 + 本文件分节段），
> 否则会出现"AGENTS.md 列出但分节缺"或"分节有但 AGENTS.md 漏"的不一致。
>
> 何时写 / 编排纪律见 `yzr-llm-wiki-management/SKILL.md` §核心原则 §12（本文件不重复，
> 避免口径分裂）；路径与契约详细定义见 `yzr-llm-wiki-management/references/wiki-spec.md` §14。

## 索引

<!-- 每脚本一行：- `<script-name>` — <一句话用途>（同步投影到 AGENTS.md §一 #### Wiki-local scripts（索引）） -->
（暂无脚本 —— 在此追加 `- \`<name>\` — <一句话用途>` 一行）

## 分节契约（详细）

<!-- 每脚本一段：### <name> — <short label> + 使用场景 + 调用约定 + 作用（+ 可选前置依赖） -->
（暂无脚本 —— 在此追加 `### <name> — <label>` 段）