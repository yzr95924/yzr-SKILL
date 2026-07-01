# {{WORKSPACE_DISPLAY_NAME}} Workspace — LLM 维护守则

> 这是本 workspace 的**纪律配置**——给跨 wiki 工作的 LLM 看的"工作守则"。你（即 LLM）
> 必须在每次跨 wiki 操作前先读这份文件；任何对 workspace 根级文件的写入都必须符合
> 这里规定的边界。
>
> 本文件由 workspace CLI 在初始化时按
> [`workspace-claude-md-template.md`](workspace-claude-md-template.md) 拷贝生成；
> 后续可由用户编辑，**但**任何与本 skill 的核心原则冲突的修改都视为"非标准配置"，
> skill 行为不再保证一致。
>
> **读取机制**：当你在 workspace 根目录内工作时，Claude Code 会自动加载根目录的
> `CLAUDE.md`（本文件）；在别处工作时，skill 会通过 `$LLMW_WORKSPACE` 按需读取它——
> 所以**不依赖 symlink**，多终端 / 跨项目都能用。

<!-- 下一行 @import 把跨 wiki MEMORY 索引内联进本文件，会话常驻；agent 写 memory 时同步更新它 -->
@MEMORY/MEMORY.md

## 一、本 workspace 的边界

### workspace 根的 9 类文件 / 目录

| 路径 | 维护方 | 说明 |
| --- | --- | --- |
| `workspace.toml` | workspace CLI | wiki 注册表 + 全局默认；skill **只读** |
| `workspace_models.toml` | workspace CLI | 模型注册表（API key 等敏感信息）；skill **不读不写** |
| `.gitignore` | workspace CLI | 排除 `workspace_models.toml` 等敏感文件 |
| `CLAUDE.md` | **用户**（CLI init 时拷模板） | 本文件 = workspace 的 schema；skill 只读 |
| `INDEX.md` / `STATS.md` | llm-workspace-management skill | workspace 入口文档 + 结构化统计 |
| `LINT.md` | llm-workspace-management skill | 最近一次 workspace lint 报告（快照） |
| `cross_queries/` | llm-workspace-management skill | 跨 wiki 综合答案归档 |
| `MEMORY/` | llm-workspace-management skill | 跨 wiki agent 私有记忆 |
| `<wiki-name>/` | workspace CLI + llm-wiki-management | 每个 wiki 是独立子仓 |

### 三层职责切分（与各 wiki 的 CLAUDE.md 区分）

- **workspace CLI**：管 `workspace.toml` / `workspace_models.toml` / `.gitignore` + 每个 wiki 子仓元数据；
  不写 INDEX/STATS/LINT/MEMORY/cross_queries
- **llm-workspace-management（本 skill）**：管 INDEX/STATS/LINT/MEMORY/cross_queries + 跨 wiki 编排；
  不写 workspace.toml / workspace_models.toml / .gitignore / CLAUDE.md
- **llm-wiki-management**：管各 wiki 的 ingest / query / lint + `<wiki>/wiki/MEMORY/`

完整不变量与权威定义见 [`workspace-spec.md`](workspace-spec.md)。

## 二、跨 wiki 约定

### xref 格式

跨 wiki 链接走相对 workspace 根路径，例：

```markdown
[huawei_storage wiki 的 storage-architecture](../huawei_storage_wiki/wiki/concepts/storage-architecture.md)
```

**不用 wikilink，不用绝对路径**。xref 由 llm-workspace-management 的 link 工作流
（[`SKILL.md` §3 link](../../llm-workspace-management/SKILL.md)）统一维护，禁止各 wiki
互相对对方 source 页做交叉写入（除非用户明确要求）。

### topic 重叠处理

若两个 wiki topic 部分重叠：

- **不合并**——每个 wiki 是用户精心策划的主题边界
- 在 `<workspace>/MEMORY/` 记一条"重叠 wiki 关联"，方便 query 跨扫
- xref 走单向（不互相编辑对方的 source 页）

### wiki 命名

新 wiki 命名见 `workspace-spec.md §15` 推荐纯 kebab-case（如 `llm-inference-opt`）；
CLI 允许 `[a-z0-9_-]{1,64}`，但**推荐避免下划线**以保持与 skill 名风格一致。

## 三、查询 / 综合纪律

### query 4 模式判定

参考 [`llm-workspace-management/SKILL.md` §2 query](../../llm-workspace-management/SKILL.md)
的 4 模式（route / synthesis / compare / local）判定规则。**空 INDEX.md 时**：

- 用户说"扫描 / 刷新 INDEX" → **scan**（先建 INDEX，再回答）
- 用户说"总结 / 综合所有 wiki" → **scan + synthesis**（先建 INDEX，再路由）

### good query 必有"是否归档"环节

跨 wiki synthesis 的好答案应问"是否归档到 `<workspace>/cross_queries/<slug>.md`"；
单 wiki 部分的子答案问"是否归档到对应 `<wiki>/wiki/syntheses/<slug>.md`"。

## 四、lint 纪律

`llm-workspace-management` skill 的 lint 工作流（详见
[`SKILL.md` §4 lint](../../llm-workspace-management/SKILL.md)）：

- **workspace 级** deterministic 检查（跨 wiki 重复实体 / 失效链接 / 未注册 wiki 子目录）+ 半定性检查（主题重叠 / tag 体系）
- **单 wiki 级** lint 走 `llm-wiki-management`，本 skill **不重复**

最近一次 lint 报告落 `<workspace>/LINT.md`（快照，每次 lint 覆盖）。

## 五、Memory 纪律

`<workspace>/MEMORY/` 是 LLM agent 的**跨 wiki**私有记忆。**禁止**写单 wiki 观察
（那些归 `<wiki>/wiki/MEMORY/`）。

何时写：

- 跨 wiki 的关联（"X 类主题放 A wiki，Y 类放 B wiki"）
- 用户对 workspace 组织的偏好（"我更喜欢按时间线而非主题分 wiki"）
- workspace-wide lint 模式（"最近 N 次 lint 总是报某类问题"）
- 跨 wiki 综合经验（"这类问题需要先 scan 再答"）

何时**不**写：

- 单 wiki 的踩坑 → 归 `<wiki>/wiki/MEMORY/`
- 跨 wiki 综合答案本身 → 归 `<workspace>/cross_queries/`
- 一次性观察 → 直接 chat，不写 MEMORY

frontmatter 5 必填（`title` / `type` / `created` / `updated` / `tags`）+ 推荐 `wikis`
字段（涉及 wiki 名数组）+ 推荐 `description`——指 `MEMORY/<slug>.md` 经验条目（`MEMORY.md`
索引本身无 frontmatter，被本文件 `@MEMORY/MEMORY.md` import 会话常驻）。**写每条经验后必须
同步追加 `MEMORY.md` 索引一行**，否则下次会话读不到。详见
[`workspace-spec.md` §9](../../llm-workspace-management/references/workspace-spec.md#9-workspace-memoryskill-维护)。

## 六、变更历史

| 日期 | 变更 |
| --- | --- |
| {{SETUP_DATE}} | workspace CLI 初始化生成（llmw v{{CLI_VERSION}} / workspace-spec v{{WORKSPACE_SPEC_VERSION}}） |