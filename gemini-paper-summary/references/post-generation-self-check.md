# 生成后自检（图片完整性 + 边界破坏）

> 本文是 `SKILL.md` §生成后自检的完整规范。SKILL.md 正文只保留一句话索引，本文展开。
> 跑完 `gemini_paper_summary.py` 后、推到 outline-wiki 前来读。

## 背景

用户在 2026-06-21 反馈——"最终生成完的论文总结，要自检一下图片是否完整，是否存在图片边界破坏的情况"。单看 doc body 字面 ok 不代表图真的 ok（attachment 可能 0 字节 / doc body 引用的尺寸与实际 PNG 尺寸不一致 / 图片被错误裁剪）。自检是生成流程的**最后一道防线**，分 3 个层面：

| 层面 | 自动化 | 检测什么 | 失败信号 |
| --- | --- | --- | --- |
| 1. 引用完整性 | ✓（脚本） | doc body 里的 `attachments.redirect?id=<id>` 引用 ID 是否在 `attachments.list` 返回中存在 | attachment 被删但 doc 还引用 → 破图 |
| 2. 二进制完整性 | ✓（脚本） | 每个 in-use attachment 的 `attachments.redirect` HEAD 是否 200 + image/... + size > 0 | 0 字节 / HTML 错误页 = 上传失败未发现 |
| 3. 边界破坏 | ✓ + 人工 | (a) 本地 `figures/*.png` 实际像素尺寸 vs markdown title `=WxH` 差 ≥ 5% → 标题尺寸字段失效；(b) 人工到 outline UI 看图是否截断 / 留白过多 / 边界切错 | 裁剪坐标错误 / 重新上传导致 title 尺寸与实际不符 |

## How to apply

### 脚本侧（自动）

`gemini_paper_summary.py` 主流程末尾调 `self_check_figures()`，挂在 `--output` 写文件**之后**、进程退出**之前**；返回 `{ok, warnings[], failures[]}`，不抛异常（warning 继续 / failure 才抛）：

- **阶段 1**：parse markdown text 抽 `attachments.redirect?id=<id>` 引用 ID 集合
- **阶段 2**：`attachments.list` 拉真实存在 ID 集合（用 outline API key 走 curl/MCP）→ 差集 = 失效引用
- **阶段 3**：每个 in-use ID 走 `attachments.redirect` HEAD，验证 200 + content-type image/ + size > 0
- **阶段 4**：本地 `figures/` 目录每个 PNG 用 pymupdf 读像素尺寸，对照 markdown 里 `=WxH` title 字段；差 ≥ 5% 警告

输出示例：

- `Self-check: 3/3 attachments OK, 0 size mismatch, 0 broken references`
- 或列出失败项

### 人工侧（必做）

agent 把生成的 doc 链接给用户后，**让用户在 outline UI 看一眼** 3 张图——是否完整、是否截断、是否切到不该切的位置；用户反馈"图破了"再回查（脚本不会自动做视觉 diff）。

### 运行时

- 本地 summary.md 生成时（`--extract-figures`）走 阶段 1+3+4
- 推到 outline 后走 阶段 1+2+3
- 不阻塞主流程（warning log）

### 失败处理

- 阶段 1/2/3 失败 → stderr WARNING + 返回值里 `failures[]` 列出，**不抛异常**（生成成功 ≠ 上传成功，agent 据此决定要不要重试 / 走 fallback）
- 阶段 4 失败 → stderr WARNING（标题尺寸字段失效，UI 仍可显示，只是尺寸不准）

## Why not visual diff 自动做

outline doc 渲染图含 outline UI chrome（背景色 / padding / 标题区），与原 figure 直接像素 diff 噪声大；可靠方案是按论文 PDF 原 page 渲染 + bbox 内裁剪后与 `figures/*.png` 对比——成本高，作为可选 Step 4b（默认不跑，agent 怀疑有问题时手动启用）。