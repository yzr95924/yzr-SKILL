# Scripts

> 本目录存放本 wiki 自维护的脚本（项目级 ingest 扩展 / 外部 CLI 胶水 / 自动化 hook）。
>
> **加载机制（0.24.0+ `@import` 收口）**：`<wiki-root>/AGENTS.md` 顶部单行
> `@scripts/SCRIPTS.md` 自动加载本文件全文——Claude Code 经薄壳 `CLAUDE.md → @AGENTS.md`
> 递归展开 / Qoder 原生支持 `AGENTS.md` 内 `@scripts/...` import 透明拿到 scripts 索引；
> Codex 不展开 `@import`，由 AGENTS.md 项目记忆段 HTML 注释的 Read 指引直接 Read 本文件
> 拿到完整脚本。三家都见 scripts——`@import` 机制透明展开，**不**像 0.23.0 内联方案需要在
> AGENTS.md 复制脚本条目。
>
> 0.23.0 短暂改"内联 AGENTS.md"——因双写 / 词数膨胀等坑回退（论证详见
> `yzr-multi-agent-context/SKILL.md`「为何不再用内联」段）。
>
> 形态（0.24.0+ 单段）：每脚本一段 `### <name> — <label>` 子节（首行起头
> `` - `<name>` — <一句话用途> `` one-liner，后接 4 要素契约）。0.23.0 双段
> `## 索引` + `## 分节契约（详细）` 已合并——`@import` 全文加载后 agent Read 即可。
>
> 脚本增删时**只改本文件**——`@import` 引用自动同步指向全文，AGENTS.md 不持有副本，无漂移。
>
> 何时写 / 编排纪律见 `yzr-llm-wiki-management/SKILL.md` §核心原则 §12（本文件不重复，
> 避免口径分裂）；路径与契约详细定义见 `yzr-llm-wiki-management/references/wiki-spec.md` §14。

## 索引

<!-- 每脚本一段：### <name> — <label>，首行起头 `- \`<name>\` — <一句话用途>` one-liner，
     后接 4 要素（使用场景 / 调用约定 / 作用 / 可选前置依赖） -->
（暂无脚本 —— 在此追加一段：`### <name> — <label>` + 完整 4 要素）