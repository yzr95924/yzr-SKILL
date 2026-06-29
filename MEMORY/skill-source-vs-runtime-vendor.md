---
name: skill-source-vs-runtime-vendor
description: 本代码仓里 SKILL 的"代码仓源" vs "运行时 vendor 副本"是两套；改 SKILL 必须改源，不要只改 .claude/skills/。
metadata:
  type: project
---

# SKILL 代码仓源 vs 运行时 vendor 副本

**Why:** 本仓库是 SKILL 的代码仓（CLAUDE.md 顶层定义"个人自定义 Claude Skills 合集"）。
仓库内每个 SKILL 目录（`gemini-paper-summary/` / `outline-wiki-setup/` / `outline-wiki-search/` / `outline-wiki-upload/` / `yzr-skill-creator/` /
`design-doc-edit/`）是**单一事实源（SSOT）**。运行时 Claude Code 通过 `~/.claude/skills/` 加载 SKILL，
而 `~/.claude/skills/` 实际是**软链**到 `~/.agents/skills/`，`.agents/skills/` 是 `npx skills add`
install 出来的**真实目录（vendored 副本）**——和代码仓源是两份**独立**的副本，不是同步链接。

**典型结构**（gemini-paper-summary 为例）：

```text
/home/zryang/my_SKILL/gemini-paper-summary/                 # ← 代码仓源（SSOT，编辑这里）
/home/zryang/my_SKILL/.agents/skills/gemini-paper-summary/  # ← vendored 副本（npx install）
/home/zryang/my_SKILL/.claude/skills/gemini-paper-summary   # ← 软链 → 上面那个
```

- `ls -la .claude/skills/gemini-paper-summary` → `lrwxrwxrwx ... -> ../../.agents/skills/gemini-paper-summary`
- `file .agents/skills/gemini-paper-summary` → `directory`（不是软链，是真目录）

**How to apply:**

- **改 SKILL 必须改代码仓源**：`/home/zryang/my_SKILL/<skill-name>/` 下的 SKILL.md /
  scripts/ / assets/ / references/。改完后可以**选择性**同步到 vendored 副本，
  或靠 `npx skills add ... --skill <name>` 重新 install 一份新 vendor 副本。
- **不要**把代码仓的修改当成"已生效"——Claude Code 加载的是 vendored 副本，源改完不
  同步过去的话，下次 Skill 调用还看到旧版。
- **判断当前生效版在哪**：`Skill <name>` 命令会从 `~/.claude/skills/<name>/SKILL.md` 加载；
  改完代码仓源后**必须**把更新复制到 `~/.agents/skills/<name>/` 才能让新会话看到。

**反模式**（**别**这么干）：

- 只改 `~/.claude/skills/<name>/`（vendored 副本）→ 看起来生效但下次 `npx skills add` 重装
  时被覆盖回旧版，源也丢了
- 只改 `~/.claude/skills/<name>/`（以为是 source）→ 实际写到 vendor，源没改 → 提交 git 时
  不会带这些修改，下个开发者拉下来还是旧版
- 以为 `.claude/skills/` 是软链改 .agents/ 就行 → 实际 `.agents/` 本身是独立目录（不是软链）

**判定方法**：

```bash
# 1) 确认软链/真目录结构
ls -la .claude/skills/gemini-paper-summary
file .agents/skills/gemini-paper-summary

# 2) 比对源 vs 当前 vendor
diff -q gemini-paper-summary/SKILL.md .claude/skills/gemini-paper-summary/SKILL.md
diff -q gemini-paper-summary/assets/prompt-template.md .claude/skills/gemini-paper-summary/assets/prompt-template.md

# 3) 同步源到 vendor（单向）
rsync -a --delete gemini-paper-summary/ .claude/skills/gemini-paper-summary/
# 注意：--delete 会清掉 vendor 独有的文件，先 dry-run 一次
rsync -a --delete --dry-run gemini-paper-summary/ .claude/skills/gemini-paper-summary/
```

**关联：** [[memory-synced-to-skill-source]]——影响 SKILL 输出的"为什么"记忆必须同步到
SKILL 自身，不要只放 MEMORY。
