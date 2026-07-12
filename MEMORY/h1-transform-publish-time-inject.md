---
name: h1-transform-publish-time-inject
description: H1 由未来 publish skill 推送 outline 时注入（源 = outline title 字段），不回写 local .md；yzr-gemini-pdf-summary 产物保持无 H1（SSOT 在 references/markdown-style.md §6）。park 等 publish skill 落地。
metadata:
  type: project
---

# H1 transform：publish 时注入，local 无 H1（parked）

**Why：** outline-wiki doc 缺 H1 浪费一级标题；local 有 H1 + publish 又注入 = 双写漂移。

**How to apply：**

- yzr-gemini-pdf-summary 产物保持无 H1（SSOT 在 `references/markdown-style.md §6`）
- publish skill 落地时实现 transform：调 outline API 前 `f"# {title}\n\n{content}"` 拼接，源 = outline `title` 参数
- 不回写 local

**park 原因：** publish skill 还没建；paper-wiki-profile.md §7 已声明远端发布是 publish skill 职责。复活点：建 publish skill 时把此 transform 实现 + 在 paper-wiki-profile.md §7 加契约。