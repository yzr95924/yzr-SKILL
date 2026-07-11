# MEMORY

> LLM agent 的持久化记忆索引（无 frontmatter）。
>
> **加载机制（0.24.0+ `@import` 收口）**：`<wiki-root>/AGENTS.md` 顶部单行
> `@MEMORY/MEMORY.md` 自动加载本文件全文——Claude Code 经薄壳 `CLAUDE.md → @AGENTS.md`
> 递归展开 / Qoder 原生支持 `AGENTS.md` 内 `@MEMORY/...` import 透明拿到索引；Codex
> 不展开 `@import`，由 AGENTS.md 项目记忆段 HTML 注释的 Read 指引直接 `Read MEMORY/MEMORY.md`
> 拿到完整索引。三家都见 MEMORY 索引，无需在 AGENTS.md 复制副本。
>
> 0.23.0 短暂改"内联 AGENTS.md"——因双写 / 词数膨胀等坑回退（论证详见
> `yzr-multi-agent-context/SKILL.md`「为何不再用内联」段）。
>
> 条目增删时**只改本文件**——`@import` 引用自动同步指向全文，AGENTS.md 不持有副本，无漂移。
> 各条目正文（`MEMORY/<slug>.md`）按需 `Read`，lint `memory-not-indexed` 兜底漏列（见
> `yzr-llm-wiki-management/references/lint-checklist.md` §二.14）。
>
> 何时写 / 文件命名 / 维护纪律见 SKILL §4 Memory（本文件不重复，避免口径分裂）。

## 索引

<!-- 每条一行：短横线 + slug + 一句话摘要 + 指向 <slug>.md 正文的 Markdown 链接 -->
（暂无条目）