---
name: skill-source-priority-over-memory-vendor
description: SKILL 源是 SSOT 也是 npx 分发包内容；MEMORY 不分发只记"为什么"；vendor 副本派生且仅当前 session 生效——影响行为的规则必须先落 SKILL 源。
metadata:
  type: project
---

# SKILL 代码仓优先级：SKILL 源 > MEMORY > vendor

**Why：** 2026-06-21 用户明确——

1. "本代码仓是一个管理 SKILL 的代码仓，MEMORY 和 vendor 目录下的内容，原没有实际对应 SKILL 目录的内容重要，优先保证对 SKILL 效果影响的内容都同步到了对应文件夹"
2. **"这些 SKILL 的目录后面用户会通过 npx skills 安装，安装时不会携带 MEMORY 的记录信息，所以需要确保 MEMORY 中影响 SKILL 效果的内容，都已经同步到了对应文件夹"**

**根因**：用户最终通过 `npx skills add` 把 `gemini-paper-summary/` / `yzr-outline-wiki-setup/` / `yzr-outline-wiki-search/` / `yzr-outline-wiki-upload/` 等子目录分发出去，**分发包只含 SKILL 目录内容**（`SKILL.md` + `assets/` + `scripts/` + `references/`），**不含** `MEMORY/` 也不含仓库的"为什么"记录。**所以 MEMORY 里的"影响 SKILL 效果"的内容如果不显式落到 SKILL 目录，npx 装出去的版本就会丢这些规则。**

**优先级排序**（从高到低）：

1. **SKILL 源**（仓库根 `gemini-paper-summary/` / `yzr-outline-wiki-setup/` / `yzr-outline-wiki-search/` / `yzr-outline-wiki-upload/` / `design-doc-edit/` / `yzr-skill-creator/`）—— SSOT，agent 触发 skill 时实际加载的上下文；**也是 npx 分发包的内容**，安装到其他机器上的就是这些文件。影响 SKILL 行为的**所有**修改必须先改这里
2. **MEMORY**（`MEMORY/MEMORY.md` + 正文同级）—— 索引 + "为什么 + 边界规则"，**没有**实际运行效果，**也不会被 npx 分发**；只承载"为什么"注解，正文必须落到 SKILL 源
3. **vendor**（`.agents/skills/<name>/` + `.claude/skills/<name>` 软链）—— 当前 session 加载副本，**派生**于 SKILL 源；同样**不被 npx 分发**（仅本机 session 用）

**How to apply：**

- 改任何 SKILL 相关规则 / 输出格式 / 边界 → **必须**先改 SKILL 源（`SKILL.md` / `assets/` / `scripts/` / `references/`）
- **MEMORY 同步检查清单**（每次写 MEMORY 条目前 + 写入后自检）：
  1. MEMORY 条目引用的规则 / 边界 / 输出格式 / 行为，**有对应文件** 在 SKILL 源里？（`SKILL.md` / `assets/prompt-template.md` / `scripts/*.py` / `references/*.md`）
  2. **npx skills add 装出去的版本也能拿到这些规则**？如果只在本仓库的 `MEMORY/` 里就等于没装出去
  3. 跨机器场景：用户**新装**本 skill（不含本仓库任何历史），能否仅凭 `SKILL.md` + `assets/` + `scripts/` 复现所有行为？如果不能 → 缺东西
- vendor 同步是**派生操作**——SKILL 源改完后 `cp -r` 同步到 `.agents/skills/<name>/` 让当前 session 生效
- 冲突处理：MEMORY / vendor / SKILL 源三者矛盾时，**以 SKILL 源为准**；MEMORY 是过时的"为什么"提示，vendor 是过时的"加载副本"
- **反模式**：
  - 只改 MEMORY 不改 SKILL 源（规则在仓库外，**npx 装出去就丢**）
  - 只改 vendor 不改 SKILL 源（vendor 不在分发包内，**npx 装出去一样丢**；且本机 clean 重建也丢）
  - 只改 SKILL 源不 vendor 同步（当前 session 看不到新内容，**仅影响本地调试**）
  - **MEMORY 写规则但 SKILL 源已完整吸收**（MEMORY 不随 npx 分发，重复记录 = 死代码；维护时容易跟 SKILL 源漂移；按"SKILL 源是 SSOT"原则**应直接删除**，而不是"留 MEMORY 提醒"——SKILL.md 自己的描述才是 npx 装出去能看到的地方）

**关联**：

- [[memory-synced-to-skill-source]]——本规则的"前情提要"版（旧版只说"同步"，没强调优先级 + 没解释 npx 分发根因）
- [[skill-source-vs-runtime-vendor]]——vendor 副本的物理结构
