# MEMORY

> LLM agent 的持久化记忆索引（无 frontmatter）。
>
> **加载机制（0.23.0+ 改）**：AGENTS.md `§一 #### 跨会话记忆（索引）` 段**内联**本文件 `## 索引`
> 段下的全部条目（一行一条），让所有读 `AGENTS.md` 的 agent（Claude Code / Codex / Qoder / Gemini CLI）
> 都能立即看到有哪些经验；各条目正文（`MEMORY/<slug>.md`）按需 `Read`。条目增删时**同步改两处**
> （AGENTS.md 索引段 + 本文件 `## 索引`），否则会出现"AGENTS.md 列出但 `<slug>.md` 缺"或
> "`<slug>.md` 有但 AGENTS.md 漏"的不一致——lint `memory-not-indexed` 兜底（见
> `yzr-llm-wiki-management/references/lint-checklist.md` §二.14）。
>
> 之前（0.22.0 及更早）用 `@MEMORY/MEMORY.md` import——但 `@import` 递归展开只 Claude Code 支持，
> Codex / Qoder / Gemini CLI 不展开，整个 `MEMORY/` 对它们不可见。0.23.0+ 改内联后所有 agent 一视同仁
> （论证详见 `yzr-multi-agent-context/SKILL.md`「L2 陷阱段」）。
>
> 何时写 / 文件命名 / 维护纪律见 SKILL §4 Memory（本文件不重复，避免口径分裂）。

## 索引

<!-- 每条一行：短横线 + slug + 一句话摘要 + 指向 <slug>.md 正文的 Markdown 链接 -->
（暂无条目）