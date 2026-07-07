---
name: design-optimization-ignore-vendor-state
description: 设计优化（schema 重构 / 路径改造 / spec bump / 重新设计）时以当前 repo 的 SKILL 描述为准，不查不补 vendor 副本
metadata:
  type: project
---

# 设计优化阶段：以当前 repo 的 SKILL 描述为准，忽略 vendor 副本

**Why：** 本仓库是 SKILL 的 SSOT——agent 加载的 vendored 副本（`~/.agents/skills/<name>/`
及其 `~/.claude/skills/<name>` 软链）是 npx install 出来的**派生**，不是事实源。设计优化
阶段（重构 schema、改 spec 版本号、调整路径、重新设计 entry 形态等）必须把**当前 repo
内的 SKILL.md / references/*.md / scripts/*.py** 作为唯一真源——vendor 里看到的版本
不代表任何东西，会随下次 `npx skills add` 覆盖。

设计阶段如果盯着 vendor 副本会出现反模式：

- 看到 vendor 是旧版就花时间 diff 哪里没跟上——但 vendor 注定要被覆盖；这种 diff 是噪音
- 改完源后顺手 cp 到 vendor，但 cp 错文件 / cp 漏文件 / cp 进 gitignored 路径反而误以为
  改完了——下次 npx 还是会被刷回
- 因为 vendor 里某个临时实验没归档就限制设计选择——vendor 不是 SSOT，实验就该扔掉
- 引用 vendor 里的旧字段名 / 旧路径 / 旧 finding 名来"对齐"——以当前 repo 的 SKILL
  描述为准，旧的让它自然过期

**How to apply：**

- **设计优化任务**（改 / 重构 / bump / 迁移 / 重新设计 / 调整路径）：**只**动仓库源
  （`<skill-name>/` 下 SKILL.md / references / scripts），跑 lint / quick_validate /
  自检测试即可交付。vendor 副本（包括 `/root/.agents/skills/<name>/`、
  `/tmp/.../my_SKILL/.../` 的副本、任何其他机器的软链）**不要读、不要 diff、不要补、不要引用**
- **SSOT 引用规则**：回答"当前 wiki spec §13 是什么" / "anchor 字段有哪些" / "路径
  怎么写"——一律 `Read` 当前 repo 的 `llm-wiki-management/references/wiki-spec.md`
  等；**不**用 vendor 副本 / web cache / 训练记忆里的旧版本作答
- **日常维护型编辑**（修 typo / 调一两句 description）：仍按
  [[skill-edits-sync-to-repo-source]] 走——改完源后 cp 到 vendor 让当前会话立即生效

**判定方法**：

- 任务关键词是 "改 / 重构 / bump / 迁移 / 优化 / 重新设计 / 调整 / 翻面" → 走本文
- 任务关键词是 "修 / 调 / 补 / 加一段 / 加一条 finding" → 走 [[skill-edits-sync-to-repo-source]]

**反模式**：

- 设计阶段 `ls .agents/skills/<name>/` 看 anchor / script 长啥样 → 看到的是旧版
  形态，被旧版误导走回老路
- 设计阶段被 vendor 里某个之前调试留下的临时文件分心 → 那文件注定要清掉，不必管
- 设计阶段跑 `git diff .agents/` 看变化 → vendor 在 `.gitignore` 内，diff 是空操作
- 引用"vendor 里说 ..." / "我之前在 vendored 副本里改过 ..." → 这些都不是 SSOT，
  以 repo 当前文件为准

**关联：** [[skill-source-vs-runtime-vendor]]——vendor 物理结构与 sync 路径；
[[skill-edits-sync-to-repo-source]]——日常编辑型任务的同步规则；
[[skill-source-priority-over-memory-vendor]]——SKILL 源 / MEMORY / vendor 的优先级排序。