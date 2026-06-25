# {{TOPIC_NAME}} Wiki — LLM 维护守则

> 这是本 wiki 的**纪律配置**——给维护本 wiki 的 LLM 看的"工作守则"。你（即 LLM）
> 必须在每次操作前先读这份文件；任何对 wiki 的写入都必须符合这里规定的边界。
>
> 本文件由 `llm-wiki-management` skill 的 `setup_wiki.py` 初始化时生成；后续
> 可由用户编辑，**但**任何与本 skill 的核心原则冲突的修改都视为"非标准配置"，
> skill 行为不再保证一致。
>
> **读取机制**：当你在 wiki 根目录内工作时，Claude Code 会自动加载根目录的
> `CLAUDE.md`（本文件）；在别处工作时，skill 会在每次操作前通过 `$LLM_WIKI_ROOT`
> 按需读取它——所以**不依赖 symlink**，多 wiki / 跨项目都能用。

## 一、本 wiki 的边界

### `raw/` —— 真相之源（**LLM 只读，用户可改**）

- 路径：`<wiki-root>/raw/{articles,assets}/`
- 性质：用户策划的原始资料（论文、剪藏、PDF、图片、播客转写、手写笔记等）
- 纪律：
  - **LLM 在任何情况下不写 / 删除 / 移动 raw/ 下文件**——只读
  - **用户可随时新增 / 更新 raw/**（重新剪藏、重存 PDF 都算）；这是用户的权限，
    不是违反纪律
  - raw 文件一旦被更新（同路径新内容），**由 ingest 重新消化**：更新对应 source
    页的正文 + `updated` 字段，并在 `log.md` 追加一条 ingest。`ingest_diff.py
    --check-stale` 会按 mtime vs source 页 `updated` 标记这类待重新摄取的文件
  - raw 文件路径是 wiki 内 source 页的 `sources` 字段的"永久引用"——改名会断链
  - raw/ 的内容是真相之源；wiki 摘要如与 raw 矛盾，**以 raw 为准**

### `wiki/` —— LLM 拥有的复利资产

- 路径：`<wiki-root>/wiki/{entities,concepts,sources,comparisons,syntheses}/`
- 性质：LLM 生成的相互链接的 Markdown 文件
- 纪律：
  - 用户**不写** wiki 页面（编辑 CLAUDE.md 除外）
  - 任何 wiki 页面**必须**含 YAML frontmatter（见下）
  - 任何 wiki 页面**必须**在 `wiki/index.md` 中有对应条目
  - 任何 wiki 页面**必须**有 ≥ 1 条 inbound 链接（index 或其它页）

### `log.md` —— 仅追加操作时间线

- 路径：`<wiki-root>/wiki/log.md`
- 纪律：
  - 每次 ingest / query / lint 后**必须**追加一条
  - 格式严格：`## [YYYY-MM-DD] <op> | <title>`（op ∈ {`ingest`, `query`, `lint`, `setup`}；
    `setup` 由 `scripts/setup_wiki.py` 在初始化时写入）
  - 标题简洁、不超过一行；URL / 详细摘要写在对应页面里
  - **不删不改**——只 append

### `index.md` —— wiki 单一入口

- 路径：`<wiki-root>/wiki/index.md`
- 纪律：
  - 按类别分组列出所有非 log 页面（entities / concepts / sources / comparisons / syntheses）
  - 每条带链接 + 一句话摘要
  - 每次 wiki 内容变更后**必须**同步（宁可多改）

## 二、页面类型与 frontmatter 约定

| 类型 | 目录 | `type` 字段 | 关键字段 |
| --- | --- | --- | --- |
| 实体页 | `entities/` | `entity` | `aliases`（别名数组，方便搜索） |
| 概念页 | `concepts/` | `concept` | `related`（相关概念路径数组） |
| 资料页 | `sources/` | `source` | `sources`（必填，raw/ 路径） |
| 对比页 | `comparisons/` | `comparison` | `compared`（被对比对象路径数组） |
| 综合页 | `syntheses/` | `synthesis` | `threads`（线索标题数组）+ `sources`（必填，wiki 内其它页路径） |

**所有页面共有 frontmatter**：

```yaml
---
title: <页面标题>
description: <一句话摘要>  # 推荐；index.md 摘要来源（OKF §4.1）
type: <entity|concept|source|comparison|synthesis>
tags: [<标签>]
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [<raw 相对路径数组>]  # source / synthesis 必填；entity / concept 可选
---
```

详细模板见 `llm-wiki-management/references/page-templates.md`。

## 三、写入纪律

1. **写前必搜**——创建新页面前先 grep / search `wiki/` 确认是否已有同名或近义页
2. **写后必同步**——新增 / 改 / 删页面后必须同步：
   - `index.md`（条目增减）
   - 相关的 entity / concept 页（追加"参考来源"段，**不重写**）
   - `log.md`（追加操作条目）
3. **改写而非新建**——若已有同类页，**编辑它**而不是建新的副本
4. **重写时保留 frontmatter**——不要因为改写丢失 `type` / `tags` / `sources` 字段
5. **交叉引用走相对路径**——`[link](../concepts/transformer.md)`，**不要**用 wikilink
   `[[transformer]]`、**不要**用绝对路径
6. **路径稳定**——文件名一旦确定就是永久 ID；想改名时用 git rename + 更新所有引用

## 四、阅读纪律

1. **读 raw 优先**——source 页的引用若与 raw 矛盾，回到 raw 复核
2. **读 index 起手**——找相关页面前先看 `index.md` 分类
3. **不读 log 内容**做证据——log 是时间线，证据在源页里
4. **跨页综合走 query 操作**——读多页 + 综合 + 给引用，不要拼接

## 五、Query 纪律

1. **先看 index，再读相关页**——不要直接全量 grep
2. **答案带引用**——每条事实带 `(来源: <page path>)`
3. **矛盾显式标注**——不要"和稀泥"
4. **好答案问归档**——对比 / 综合 / 发现新联系 → 询问用户是否写回 wiki

## 六、Lint 纪律

1. **脚本检查 deterministic 部分**——raw/ 不可变性、frontmatter、index 覆盖、断链、log 格式
2. **agent 检查半定性部分**——矛盾、缺失交叉引用、过期主张
3. **修 lint 不要回退 schema**——若 lint 报告与本文件冲突，**先讨论用户**再决定

## 七、本文件本身的纪律

- 本文件是 schema，**不是 wiki 内容**——不要往里塞 wiki 主题相关的笔记
- 改本文件 = 改 skill 行为 = 大事；先和用户确认
- 每次改都建议 git commit 并加清晰的 commit message

## 八、当前配置

| 字段 | 值 |
| --- | --- |
| 主题 | {{TOPIC_NAME}} |
| 创建日期 | {{SETUP_DATE}} |
| Wiki 根 | <由 LLM_WIKI_ROOT 环境变量或 setup 时确定> |
| Skill 版本 | 来自 `llm-wiki-management/SKILL.md` 的 `last_modified` 字段 |
