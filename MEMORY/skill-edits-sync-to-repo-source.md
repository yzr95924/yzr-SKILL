# SKILL 描述类修改：默认同步仓库源

**Why：** 本仓库是 SKILL 的"源 / 描述"载体（`yzr-outline-wiki-setup/` / `yzr-outline-wiki-search/` / `yzr-outline-wiki-upload/` / `gemini-paper-summary/` / `yzr-skill-creator/` / `design-doc-edit/` 等顶层子目录即各 skill 源），而 agent 加载的是 `.claude/skills/<name> -> ../../.agents/skills/<name>` 的软链（vendored 副本，被 `.gitignore` 排除）。两套文件**不同 inode**——`Edit` 默认改的是 vendored 副本，不在 git 跟踪范围内，会随下次 `npx skills` 同步被覆盖。

**How to apply：**

- 修改任何 skill 的 `SKILL.md` / `references/*.md` / `scripts/*.py` 等"描述类"文件前，**先**问自己："这次修改是要进仓库源（`.gitignore` 之外），还是只调 vendored 副本做本地实验？"
- 默认是前者（持续维护的代码），改完后**必须**同步到仓库源——通常用 `cp` 把 vendored 副本拷回源（`cp .claude/skills/<name>/SKILL.md <name>/SKILL.md`），用 `git status` / `git diff --stat` 确认
- 一次只改一个 skill，不要顺手把 vendored 里其他无关改动一起带回去——`cp` 之前先 `diff` 一遍
- 涉及仓库源里 `Edit` 不到的字符（如大段重写、含特殊符号的）也可以走 `cp`，但**只覆盖源里未改的部分**；源已被别处修改时必须 `Edit` 走精准 patch，否则会丢别人的改动
- 反例：上次的 SKILL 修改我只在 `.claude/skills/outline-wiki-management/` 改了，没主动同步到源仓库，被用户提醒才补；这就是这条规则要堵的洞（2026-06-29 拆 3 skill 后该路径已不存在，仅作历史反例保留）

**关联：** [[skill-source-vs-runtime-vendor]]——vendor 副本的物理结构；[[skill-source-priority-over-memory-vendor]]——SKILL 源 / MEMORY / vendor 的优先级排序。
