---
name: gemini-pdf-summary-manual-whitepaper-full-design
description: gemini-pdf-summary 的 manual / whitepaper 改 full 风格的 4 类设计决策与边界（2026-07-05 翻面）
metadata:
  type: project
  supersedes: gemini-paper-summary-manual-whitepaper-quick-style（旧实现已删除）
---

# gemini-pdf-summary manual / whitepaper full 风格设计（2026-07-05 翻面）

## Why

`gemini-paper-summary` 重命名为 `gemini-pdf-summary` 后扩展为 4 类文档（paper / manual / whitepaper / book）。早期实现把所有类型都写成"quick 风格"——精炼速读、字符数上限、给**人**看。但 manual / whitepaper / book 的实际消费对象是 **`llm-wiki-management` 的 `ingest_diff.py` 二次蒸馏**——二次蒸馏需要原文级细节以抽取 entity / concept / 关联，精炼总结会丢信息，下游 ingest 拿不到原始细节。

设计本意：只有 paper quick 是给**人**看（精炼速读，字符上限 ≤ 2500），其它 3 类（manual / whitepaper / book + paper full）都是给 LLM 消费的下游产物（按 PDF 原生章节顺序全文级转写，无字符上限）。脚本运行时已把 manual / whitepaper 走 `prompt_mode = "full"`（prompt 加载路径已对齐），但模板正文还是 quick 风格——这是脚本注释与实际行为的潜在不一致 bug。

## How to apply

未来给 `gemini-pdf-summary` 加内容或改模板时：

1. **manual / whitepaper 永远保持 single-template + full 风格**，不要再回头加 quick 模式——quick 风格只服务于 paper 的人类阅读场景
2. **任何想加字符上限的提议先问"这是给 LLM 消费还是给人看"**——给 LLM 消费的（manual / whitepaper / book / paper full）无字符上限；给**人**看的（paper quick）才有字符上限
3. **改 `template-manual.md` / `template-whitepaper.md` 时同步 SKILL.md §输出 + §C 4 类输出模板段**，避免单边更新导致 SKILL.md 描述与模板正文脱节（SSOT 例外规则见 `references/templates.md` §段标题约定）
4. **`_check_*_full_content` 4 个类型专属自检函数**（`scripts/gemini_pdf_summary.py`）—— paper 走 `### Section X.Y` + Definition/Theorem + `$$...$$` block；manual 走通用 H3 + 表格行数 + bash/yaml 代码块；whitepaper 走通用 H3 + 表格行数 + mermaidjs block；book 走 `## Chapter N` 计数。**不要**把 paper 的正则直接套到 manual / whitepaper / book——manual 章节命名无 Section X.Y 体系

## 4 类设计决策（SSOT）

### D1：manual / whitepaper 单模板 = full 风格

`template-manual.md` 与 `template-whitepaper.md` 各只有 1 份模板（不分 quick / full）；脚本 `prompt_mode = "full" if (args.full or doc_type in ("manual", "whitepaper", "book")) else "quick"` 已硬编码；用户传 `--type manual` 即可，无需 `--full`。与 paper 双模式（quick + full）刻意保持差异——paper 唯一保留 quick 风格。

### D2：manual / whitepaper / book 不抽原始 PNG

3 类脚本自动启用 `--no-figures`，架构 / 概念 / 数据图全部用 ` ```mermaidjs ` block / markdown 表格 / ASCII 在 markdown 内直接画；产物自包含，无需 PNG 配套（避免 outline 渲染破图）。`![图 N](PDF p.X ...)` 引用会断图，脚本后处理 `strip_pdf_figure_refs` 会清理。

### D3：manual / whitepaper / book 必保真元素表（按类型）

| 元素 | manual | whitepaper | book |
| --- | --- | --- | --- |
| 命令清单 / API endpoint | 必保真（` ```bash ` / ` ```yaml ` / ` ```json `） | 偶尔 | 必保真（` ```python ` / ` ```bash `） |
| 表格 | 必保真（参数表 / 接口表 / 错误码表） | 必保真（行业数据表 / 对比表 / 客户案例表） | 必保真 |
| 章节末尾特色内容 | 故障排查 / FAQ / 更新日志要点原样保留 | Conclusion / Key Takeaways / Recommendations 原样保留 | 小结 / 思考题 / 参考文献原样保留 |
| 索引 term → page | 通常无 | 通常无 | 必保真（书籍索引页） |
| 立场甄别 | N/A | 必填（vendor / 行业中立 / 学术 / 政策 / 咨询） | N/A |
| 数字精度 | 3 位有效数字 | 3 位有效数字 | 3 位有效数字 |

### D4：自检函数 4 类拆分（2026-07-05 新增）

`scripts/gemini_pdf_summary.py::self_check_full_content(md_text, doc_type=...)` 按 `doc_type` 分发：

- `paper`（默认，paper full 专属）：H2 ≥ 3 + `### Section X.Y` ≥ 5 + Definition/Theorem/Lemma/Algorithm ≥ 1 + `$$...$$` block ≥ 1 + 字符 ≥ 8000 + 占位比例 ≤ 50%
- `manual`：H2 ≥ 3 + 通用 H3 ≥ 5 + 表格行 ≥ 5 + bash/yaml/json 代码块 ≥ 1 + 字符 ≥ 6000 + 占位比例 ≤ 50%
- `whitepaper`：H2 ≥ 3 + 通用 H3 ≥ 5 + 表格行 ≥ 5 + mermaidjs block ≥ 1 + 字符 ≥ 7000 + 占位比例 ≤ 50%
- `book`：H2 ≥ 3 + `## Chapter/Part/Appendix/Index` ≥ 3 + H3 ≥ 5 + 字符 ≥ 8000 + 占位比例 ≤ 50%

阈值差异：manual 6000 / whitepaper 7000 / paper & book 8000——反映各类型文档本身的篇幅差异（manual 较短、whitepaper 居中、paper & book 较长）。

## 关键 bug 修复（顺手）

原代码 `if args.full: return _run_full_mode(args)` 让 `--type book` 也走 `_run_full_mode`，但 `_run_full_mode` 是 **paper 专属**（产物路径 `raw/papers/<slug>.quick.md + .full.md` 是 paper layout）。修复：`if args.full and doc_type == "paper": return _run_full_mode(args)`——book 现在走通用分支（prompt_mode 已自动 "full"，调用同一条 call_gemini + max_tokens，产物写到 `<output>/<slug>.md` 单文件）。

## 历史兼容

- `_load_prompt_for_type` 的 `head_patterns` 仍保留 `("manual", "quick")` / `("whitepaper", "quick")` 映射到 `## 模板` 段——这是为了旧脚本兼容（避免破坏任何外部调用方）。**但** main() 已不传 `mode="quick"` 给 manual / whitepaper，模板正文也已重写为 full 风格，所以实际上没有任何调用方会触发该映射
- `scripts/gemini_pdf_summary.py:1745` 的 paper full 自检调用显式传 `doc_type="paper"`，避免 dispatcher 默认行为变更影响该调用点