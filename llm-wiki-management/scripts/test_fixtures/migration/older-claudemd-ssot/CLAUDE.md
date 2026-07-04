# Test Wiki — LLM 维护守则

> 迁移测试 fixture，老格式场景——CLAUDE.md §八 Wiki Spec 版本 = 0.10.0
> （0.11.0 前：CLAUDE.md 作 SSOT，未拆 AGENTS.md + 薄壳；@import 在 CLAUDE.md 顶部）
>
> **读取机制**：当你在 wiki 根目录内工作时，Claude Code 会自动加载根目录的 `CLAUDE.md`（本文件）；
> 在别处工作时由 skill 经 `$LLM_WIKI_ROOT` 按需读取——不依赖 symlink。

@MEMORY/MEMORY.md

## 一、本 wiki 的边界

### raw/ —— 真相之源（LLM 只读）

- LLM 在任何情况下不写 / 删除 / 移动 raw/ 下文件
- raw 文件路径是 source 页 `sources` 字段的永久引用——改名会断链

### wiki/ —— LLM 拥有的复利资产

- 用户不写 wiki 页面（编辑 CLAUDE.md 除外）
- 任何 wiki 页面必须含 frontmatter + 在 index.md 中有对应条目

## 二、页面类型与 frontmatter

略——见 page-templates.md。

## 八、当前配置

| 字段 | 值 |
| --- | --- |
| 主题 | Test Wiki (older-claudemd-ssot) |
| 创建日期 | 2026-06-01 |
| Wiki 根 | `test fixture` |
| Wiki Spec 版本 | 0.10.0 |
| CLI 版本 | 0.1.0 |
