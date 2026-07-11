---
name: experience-affecting-skill-distribution-goes-to-skill-not-memory
description: 影响 SKILL 分发后用户行为的"坑 / 经验 / 为什么"，必须进 SKILL（+ bundled refs），不能只留仓库 MEMORY——MEMORY 是仓库 SSOT 不进 npx vendor 副本，其他位置安装时拿不到。
metadata:
  type: project
---

# 影响分发后行为的经验必须进 SKILL，不能只留 MEMORY

**Why：** 2026-06-30 实战踩坑——两份关键经验最初都只写在仓库 `MEMORY/`：

1. `MEMORY/ddnsto-relay-https-only-quirk.md`（ddnsto relay HTTP 80 端口对所有
   路径返空 200，真上游只透 HTTPS 443）
2. `MEMORY/outline-mcp-permission-allowlist.md`（15 条 `mcp__outline__*`
   工具必须在 `.claude/settings.local.json#permissions.allow` 加白名单）

如果只留 MEMORY，`npx skills install yzr-outline-wiki-setup` 出去后，**新用户拿着
SKILL.md + bundled refs 在另一台机器装，看不到 MEMORY**——前面踩过的坑等于
白踩，会按"鉴权错 / 配置问题"再排 20+ 分钟。本轮把这两条经验同步进了
`SKILL.md` 故障排查 + `references/onboarding.md` 常见问题，才彻底补上。

**仓库结构事实**（AGENTS.md / CLAUDE.md 顶层定义）：

- `MEMORY/` 在仓库根 `/root/my_SKILL/MEMORY/`——**仓库 SSOT，npx 不带**
- 分发出去的是 `<skill-name>/SKILL.md` + bundled `scripts/` / `references/` / `assets/` / `eval/`
- `~/.claude/skills/<name>` → 软链 → `.agents/skills/<name>`（vendored 真目录），
  跟仓库源是**两份独立副本**
- 结论：MEMORY 不进 npx / 不进 vendor 副本 / 不会出现在新用户的
  agent 上下文中

**判定标准**（这条经验该去哪）：

| 经验类型 | 去向 |
| --- | --- |
| 影响 SKILL 触发后用户能否达成目标（典型是别人会踩的"坑"） | → **SKILL.md** 故障排查 / 注意事项 + `references/` 详方案 |
| 只记录仓库维护者的设计决策 / 为什么（无对外行为影响） | → **MEMORY** |
| 跨 skill 协作约定 / boundary decisions（如 paper-wiki 解耦） | → **MEMORY**，由相关 SKILL.md 引用 |
| 影响多个 skill 的元规则（如 description 写法原则） | → **MEMORY/**`yzr-skill-creator/references/skill-writing-principles.md` 等专门档 |

**How to apply：**

任何新发现的"坑 / 经验 / 为什么"，**先问自己**：

> 另一个用户在另一台机器上 `npx install <skill>`，能指望他们自己撞见并解决吗？

- **不能 → 必须进 SKILL**（先 SKILL，必要时再 MEMORY 留底——MEMORY 是补充不是替代）
- **能，但需维护上下文 → 只 MEMORY**
- **边界模糊 → 写 SKILL**（错放 SKILL 顶多多一句废话；错放 MEMORY 会让人重蹈覆辙）

进 SKILL 时按"症状→指引 / 详方案放 references/"分层，避免 SKILL.md 自身顶到 5000 词上限。本轮落地形式是 SKILL.md 故障排查 1 行症状 + onboarding.md 常见问题/调用脚本 详方案。

**反模式**：

- "我先把想法写到 MEMORY，下次有空再补 SKILL"——窗口期给未来用户挖坑
- "MEMORY 写了就行，反正只有这个仓库"——忘了 MEMORY 不进 npx vendor；本仓库能用 ≠ 分发后能用
- "description 加触发就够"——description 只决定**是否触发**，不决定**怎么跑**；运行细节必须进 SKILL.md 正文
- "SKILL.md 别加诊断段，保持简短"——节制是好，但踩坑指引不可省；指引放 `references/` 即可，SKILL.md 正文保 5000 词内

**关联：**

- [[memory-synced-to-skill-source]]——同主题但视角相反：本条从**分发端**（用户视角，能拿到什么内容）讲；那条从**改动流程**（作者视角，何时该同步）讲
- [[skill-source-vs-runtime-vendor]]——vendor 副本 vs 仓库源的两份同步问题；本条更进一层，讲哪些内容**连 vendor 都不带**
