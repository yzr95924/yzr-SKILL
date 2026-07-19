# Workspace Spec 版本历史（Changelog）

> 本文件原为 `workspace-spec.md` 附录 B（spec 演进日志）。**CLI 实现与 SKILL 内容不读本文件**——
> CLI 落盘按 spec §1–§16 当前规则走；本文件只在追"为什么这条规则存在" / "哪个版本引入"时按需 Read。
> 表格 cell 内连带的 `SKILL.md` / 模板文件同步清单是 spec 演进时实际改过的范围——回看
> "那个版本的提交动了哪些文件"用。

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| 0.6.2 | 2026-07-18 | **对齐 `yzr-multi-agent-context` R1+R2：顶部强制 Read 指令 + 去品牌**——`AGENTS.md` 顶部新增**强制 Read 指令 blockquote**（"凡 `@path/to/file` 形式的引用…都用 Read 工具按需读取…不自动展开 `@import` 的 agent 尤须手动执行"，逐字移植自 `yzr-multi-agent-context/references/layering.md` 骨架）；删除 `@MEMORY/MEMORY.md` 上方段内 HTML 注释 Read 指引（职责由顶部指令接管——R2「段内不再单挂指引」）。SSOT（模板 + spec）去品牌 R1：`Claude Code` / `Qoder` / `Codex` / `Gemini CLI` 点名改行为化措辞（"经薄壳加载的 agent" / "原生读 `AGENTS.md` 的 agent" / "不展开 `@import` 的 agent"）；`CLAUDE.md` 薄壳保留 `Claude Code`（标题 + 薄壳声明 = R5 逃生舱）。SKILL.md `metadata.workspace_spec_version` 升至 0.6.2；`references/{workspace-agents-md,workspace-claude-md}-template.md` 顶部改造；`references/workspace-spec.md` §1 / §2 / §4 / §9.1 去品牌。**非破坏性**：加指令 + 去品牌是 additive / cosmetic，无 checker 驱动、无强制迁移；老 workspace 顶部补一条强制 Read 指令 blockquote 即对齐（可选） |
| 0.6.1 | 2026-07-08 | **`.gitignore` `settings*.json` 通配加固**：§10 把 `**/.x/settings.local.json` 加宽到 `**/.x/settings*.json`——覆盖 `settings.json` / `settings.local.json` / `settings.<env>.json` 等所有 settings 变体（非 local 版也可能含 token / MCP 配置）；附录 A.4 自检文案同步。**老 workspace 迁移**：`.gitignore` 把 `settings.local.json` 改成 `settings*.json` 即可（合并 0.6.0 一并做单步迁移） |
| 0.6.0 | 2026-07-08 | **`.gitignore` `**/` 通配补根目录层**：§10 把 `*/.claude/settings.local.json` + `*/.qoder/settings.local.json` 改成 `**/.claude/settings.local.json` + `**/.qoder/settings.local.json`——原 `*/` 模式只匹配 depth-1+（漏 `<workspace>/.claude/settings.local.json` 与 `<workspace>/.qoder/settings.local.json` 根级两行），`**/` 单行覆盖 workspace 根 + 任意深度子目录，不再需要分两行写。附录 A.4 自检文案同步。**老 workspace 迁移**：把 `.gitignore` 里两行 `*/.x/settings.local.json` 改成 `**/.x/settings.local.json` 即可（不影响 0.5.0 迁移） |
| 0.5.0 | 2026-07-08 | **`.qoder` 与 `.claude` 同管理逻辑**：§10 `.gitignore` 模板在 `*/.claude/settings.local.json` 后追加 `*/.qoder/settings.local.json`（Qoder IDE 项目级 settings，可能含 token）；附录 A gitignored 自检同步补 `.qoder`；老 workspace 迁移：在 workspace 根 `.gitignore` 手动追加一行即可 |
| 0.3.0 | 2026-07-01 | **breaking**：§9 MEMORY 重构——`MEMORY/README.md`（type:memory）→ `MEMORY/MEMORY.md`（无 frontmatter 索引，**CLI init 创建**，被 `<workspace>/CLAUDE.md` 用 `@MEMORY/MEMORY.md` import 会话常驻）；§1 ownership `MEMORY/` 改 CLI init 建骨架；§13 删 wiki reserved `memory` 引用（跟齐 wiki-spec 0.6.0）。**老 workspace 迁移**：删 `MEMORY/README.md` + 新建 `MEMORY/MEMORY.md` 索引并把现有 `*.md` 各补一行 |
| 0.2.0 | 2026-06-30 | **breaking**：新增 §4 `CLAUDE.md`（CLI init 按模板拷，用户所有）+ §9 `MEMORY/`；新增 `workspace-memory` reserved frontmatter type；§1 ownership 6 → 9 类；§12 拒绝条件新增 CLAUDE.md 已存在则拒绝 |
| 0.1.0 | 2026-06-30 | 初始：6 类文件归属 + INDEX/STATS/LINT/cross_queries schema + CLI/skill 边界 + 3 类 reserved type |
