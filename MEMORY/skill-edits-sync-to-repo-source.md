---
name: skill-edits-sync-to-repo-source
description: 改 SKILL.md / references / scripts 一律直落仓库源（git 跟踪的 <skill-name>/），不碰 vendored 副本；修完 commit + push，用户经 npx skills 同步 vendored（2026-08-16 起工作流改为 agent 不再手拷）。
metadata:
  type: project
---

# SKILL 修改：直落仓库源 + commit/push + 用户 npx 同步

**Why：** 本仓库是 SKILL 的"源 / 描述"载体（`yzr-coding-review/` / `yzr-skill-creator/` 等顶层
子目录即各 skill 源），而 agent 加载的是 `.claude/skills/<name> -> ../../.agents/skills/<name>`
的软链（vendored 副本，被 `.gitignore` 排除）。两套文件**不同 inode**——`Edit` 默认改的是
vendored 副本，不在 git 跟踪范围内，会随下次 `npx skills` 同步被覆盖。

**How to apply：**

- 修改任何 skill 的 `SKILL.md` / `references/*.md` / `scripts/*.py` 等"描述类"文件，**直接编辑
  仓库源**（`/root/yzr-SKILL/<skill-name>/`），不要读 / 改 vendored 副本（`~/.claude/skills/` /
  `~/.agents/skills/` 是 npx install 派生的，注定被覆盖）
- 修完验证（quick_validate / markdownlint / ruff）后 **commit + push**——由用户跑 `npx skills`
  完成 vendored 同步，**agent 不再手拷**（2026-08-16 起的工作流，取代旧 cp 流程）
- 一次 commit 只含本次审计 / 修复的 skill，不混入无关改动——commit 前 `git status` / `git diff`
  过一遍
- 反例（历史）：早期只在 vendored 改、没同步仓库源，被用户提醒才补；后改用 cp 拷回，再改为
  现在的 commit/push + npx 同步

**关联：** [[skill-source-vs-runtime-vendor]]——vendor 副本的物理结构；[[skill-source-priority-over-memory-vendor]]——SKILL 源 /
MEMORY / vendor 的优先级排序。
