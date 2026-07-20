---
name: spec-version-bump-3way-atomic-cli
description: my_SKILL spec_version bump 必须 3-way 原子（frontmatter ↔ CLI WORKSPACE/WIKI_SPEC_VERSION ↔ submodule 指针）——agents-version-is-current 耦合，单独 bump 破 fresh-init 探测器 pass
metadata:
  type: project
---

# spec 版本号 bump 是 my_SKILL ↔ CLI 三方原子操作

`workspace_spec_version` / `wiki_spec_version` 升版本时，三处必须同一提交窗口对齐：

1. **my_SKILL 仓**：两 `SKILL.md` frontmatter `*_spec_version` + wiki `scripts/lint_wiki.py`
   `CURRENT_WIKI_SPEC`（`_assert_spec_version_sync` 在 import 时对照 frontmatter，失同步 warn）
2. **CLI 仓** `llmw/__init__.py`：`WORKSPACE_SPEC_VERSION` / `WIKI_SPEC_VERSION` 常量（init 时写入
   AGENTS.md §「当前配置」表 + `workspace.toml` `templates_version` 双分量）
3. **CLI 仓 submodule 指针**：指向含新 frontmatter 的 my_SKILL commit

**Why:** `check_workspace_fixtures.py` 的 `agents-version-is-current` check 比对 CLI 写进 AGENTS.md
的版本行（= CLI 常量）vs SKILL.md frontmatter `workspace_spec_version`（= 探测器 target）。my_SKILL
单独 bump → CLI 没跟 → 版本号不等 → fresh `llmw init` 产物被判违规 → 探测器 exit=1。这正是
2026-07-20 my_SKILL_fix §零.2 的症状（CLI `WIKI_SPEC_VERSION` 0.26.0 vs my_SKILL frontmatter 0.27.0
漂移）；路径 A 原子 bump 到 0.7.1/0.27.1 才修。CLI 的 `fixtures-smoke` CI gate 对版本漂移**免疫**
（显式忽略 `agents-version-is-current`），故 CLI 仓 CI 不红——红的是「用户手跑探测器看到 fail」的
体验，隐蔽性强。

**How to apply:** bump 流程——① my_SKILL 改 frontmatter + `lint_wiki.py` + 两 changelog 行，commit +
push → ② CLI 仓改 `llmw/__init__.py` 两常量 + `git submodule update --remote my_SKILL` 推进指针 →
③ 两边同窗口 push（CLI 有 pre-push hook 校验 my_SKILL 已是 origin 最新才放行）。CLI 仓
`git@github.com:yzr95924/llm_workspace_cli.git`，submodule 路径 `my_SKILL`，track `master`。
patch/minor 选型：非破坏性（新 check 在现有产物 pass / prose 不改字节）→ patch；引入字节级出生形态
变更 → 按 wiki/workspace-spec-changelog 既有惯例 minor/breaking。关联
[[wiki-workspace-spec-type-coupling]]（另一条跨 spec/跨仓 耦合）+ [[memory-synced-to-skill-source]]。
