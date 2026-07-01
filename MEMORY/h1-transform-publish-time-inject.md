# H1 transform 决策：publish 时注入，local 保持无 H1（parked, 2026-06-29）

**Why：** 2026-06-29 用户提出——Gemini 产物（local `.md`）当前无 H1，标题在 outline `title` 字段（即 document ID）里、不在 markdown body。推送到 outline-wiki 后 outline doc 缺 H1，**浪费一级标题**且正文读者看不到标题。H1 注入是 **publish 时的 transform**——不属于 `gemini-paper-summary` 的职责（它要维持"无 H1"的 local 约定，与项目其他 4 个 SKILL.md 一致）。

**How to apply：**

- **`gemini-paper-summary` 不变**：保持产物无 H1（已通过 `prompt-template.md` 风格约定 #9 + 基础要求 #5 固化，2026-06-29 audit 后统一）
- **publish transform 注入 H1**：源 = `outline` `documents.create` 传入的 `title` 参数（无需额外 API 调用）；在调 outline API 前对 content 做 `f"# {title}\n\n{content}"` 拼接
- **不回写 local**：H1 只活在 outline doc body，local `.md` 文件保持无 H1——避免"local 有 H1、publish 又覆盖"的双写漂移
- **复活点**：建 publish skill 时重提，先实现 transform；同时在 `paper-wiki-profile.md` §7 加"H1 由 publish transform 注入（源 = outline `title`）"作为契约
- **park 原因**：publish skill 还没建（参考 [[paper-wiki-integration-design]] "别现在建"决策）；避免在 publish skill 落地前造临时小工具（with_h1.py 之类的预制件）
- **不撤回的边界**：本决策不破坏 audit 已立的"4 个 SKILL.md 无 H1"约定——它明确划出 **local 文件无 H1 / outline doc 有 H1** 两条规则的边界

**关联：**

- [[paper-wiki-integration-design]]——本决策的父决策（publish skill 独立、远端不归 llm-wiki-management）
- [[gemini-paper-summary-full-mode-design]]——producer 侧 SSOT；本决策不与 D1-D4 冲突（layout 不变，仅 H1 由 publish 端补）
