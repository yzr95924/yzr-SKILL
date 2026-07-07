# 4 类输出骨架 + 参考样例（从 SKILL.md 抽出）

> 本文件是 SKILL.md §工作流 §C（4 类模板骨架）+ §参考样例（5 个样例）的下放层。
>
> **SSOT 例外说明**：本文件与 SKILL.md 同步——SKILL.md §C 写"详见 `references/output-skeletons-and-examples.md`"，
> 本文件展开细节；改一处必须同步另一处（与 `assets/template-*.md` 顶部声明同源）。
>
> **不在本文件范围**：
>
> - 模板的 prompt 正文（4 类模板各自的章节骨架 + 必保真元素）—— 见 `assets/template-{paper,manual,whitepaper,book}.md` 顶部 fence 块。
> - 4 类模板共用片段（API 调用 / 风格基线 / 字符数纪律 / 图表处理）—— 见 `assets/_base.md`。
> - `--full` 模式的契约与故障排查 —— 见 `references/full-mode-contract.md`。

## 目录

- [4 类输出骨架](#4-类输出骨架)
  - [paper quick（默认）](#paper-quick默认)
  - [paper full](#paper-full)
  - [manual（产品手册；full 风格全文级转写）](#manual产品手册full-风格全文级转写)
  - [whitepaper（白皮书；full 风格全文级转写）](#whitepaper白皮书full-风格全文级转写)
  - [book（书籍；仅 full 模式）](#book书籍仅-full-模式)
- [参考样例](#参考样例)
  - [样例一：单篇论文总结](#样例一单篇论文总结)
  - [样例二：产品手册（manual · full 风格）](#样例二产品手册manual--full-风格)
  - [样例三：行业白皮书（whitepaper · full 风格）](#样例三行业白皮书whitepaper--full-风格)
  - [样例四：书籍（full 模式）](#样例四书籍full-模式)
  - [样例五：不确定类型（auto-detect）](#样例五不确定类型auto-detect)

---

## 4 类输出骨架

### paper quick（默认）

学术论文速读版。详见 `assets/template-paper.md` §quick 模式 + `assets/_base.md`。

```text
章节顺序：
  开篇 3 列表格（Title / Venue / Topic）
  + 论文链接 item（含 > <TODO> 占位）
  + 团队/机构 item
  → ## 3 句话总结
  → ## 背景与动机
  → ## 方法设计    ─┐ 二选一
  → ## 代表性实验结果 ─┘
       或 评测设计 + 评测发现（评测 / benchmark 类论文）
  → ## 业务启示 & 价值（含开源实现 / 相关工作子段）
  → ## 局限与未来工作
  → ## 启发 / 追问（仅 --focus 时输出）

字符目标 ≤ 2500；含图（默认）。
```

### paper full

按 PDF 原生章节顺序全量转写。详见 `assets/template-paper.md` §full 模式 +
`references/full-mode-contract.md`。

```text
章节顺序：严格按 PDF 原生 Section N / Section N.M / Section N.M.K 顺序展开
必保真元素：Definition / Theorem / Lemma / Corollary / Algorithm 标注 + 公式 $...$ +
            表格行级转写 + 数字精度 3 位有效数字
图处理：mermaid block（架构 / 概念）/ markdown 表格（数据可视化）/ 文字一句（装饰图省略）
字符目标：解除上限；token 紧张时优先精简措辞、缩例子；禁止合并整段 / 删小节 / 跳公式
产物：<output>/<slug>.full.md（**单产物**，2026-07-07 翻面后；full 自包含无图；想看 quick + 带图跑 `--type paper` 默认）
```

### manual（产品手册；full 风格全文级转写）

详见 `assets/template-manual.md`。

```text
章节顺序：严格按 PDF 原生目录结构逐小节展开（Section N / Section N.M / Appendix）
          原英文标题保留（如 ## Hardware Specifications、## Installation Guide）

必保真元素：命令清单 / API endpoint（fenced code block）
            参数 / 配置 / 环境变量表（markdown 表格，3 位有效数字）
            错误码 / 异常表（markdown 表格）
            产品参数表（型号 / 容量 / 性能 / 接口 / 协议 / 标准）
            章节末尾的故障排查 / FAQ / 更新日志要点（manual 特色，原样保留）
            术语表 / Glossary / 参考链接（附录）

图处理：架构 / 模块关系 → mermaid block；数据图 → markdown 表格；装饰图省略
字符目标：无上限；完整性 > 篇幅；token 超限时先详写前 N 章 + 末章占位
不含原始 PNG；产物 <output>/summary.md（单文件）
```

### whitepaper（白皮书；full 风格全文级转写）

详见 `assets/template-whitepaper.md`。

```text
章节顺序：严格按 PDF 原生目录结构逐小节展开（Executive Summary / Market Analysis /
          Challenge / Solution / Case Studies / Conclusion 等）
          原英文标题保留（如 ## Executive Summary、## Market Analysis）

必保真元素：行业数据表（市场规模 / CAGR / 渗透率，3 位有效数字）
            对比表 / benchmark 表（vendor 对比 / 方案对比）
            客户案例 / 实证数据（ROI / 收益 / 客户名）
            章节末尾的 Conclusion / Key Takeaways + Recommendations（whitepaper 特色，原样保留）
            About the Publisher / Methodology / References（附录）

立场甄别：vendor 自家方案 vs 行业中立 vs 学术 / 政策 / 咨询——必须在元信息段"发布立场"标注，
          立场影响读者如何解读结论，识别不出时写"原文未明确"

图处理：架构 / 价值链 / 流程 → mermaid block；数据图 → markdown 表格；装饰图省略
字符目标：无上限；完整性 > 篇幅；token 超限时先详写前 N 章 + 末章占位
不含原始 PNG；产物 <output>/summary.md（单文件）
```

### book（书籍；仅 full 模式）

详见 `assets/template-book.md`。

```text
章节顺序：严格按 PDF 原生 Chapter / Part / Appendix / Index 顺序
必保真元素：章节标题层级 / Definition-Theorem-Lemma-Algorithm 标注 / 公式 / 表格 / 代码 /
            章节末尾小结 + 思考题 + 参考文献 / 索引（term → page 列表原样保留）
字符目标：无上限；完整性 > 篇幅；token 超限时先详写前 N 章 + 末章占位
不含图（mermaid / 表格 / ASCII）。
产物：<output>/<slug>.md（单文件，章节级展开）
```

---

## 参考样例

### 样例一：单篇论文总结

**用户**："帮我把 `~/papers/attention_is_all_you_need.pdf` 总结成中文"

**agent 工作流**：

1. 用户已说明是论文 → `--type paper`
2. 反问输出路径 → 用户答 `~/papers/summaries/attention_is_all_you_need/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/attention_is_all_you_need.pdf \
  --type paper \
  --output ~/papers/summaries/attention_is_all_you_need  # 目录：summary.md + figures/*.png
```

### 样例二：产品手册（manual · full 风格）

**用户**："这是我们新硬件的 datasheet，整理一下"

**agent 工作流**：

1. 用户提到 datasheet → `--type manual`
2. 反问输出路径 → 用户答 `~/wiki/llm-systems/raw/manuals/h100-sxm/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/h100-sxm-datasheet.pdf \
  --type manual \
  --output ~/wiki/llm-systems/raw/manuals/h100-sxm/
# 产物：summary.md（按 PDF 原生章节顺序全文级转写；含命令清单 / 参数表 / 错误码 / 故障排查；无 PNG）
# 产物供 llm-wiki ingest_diff 二次蒸馏，不直接给人阅读
```

### 样例三：行业白皮书（whitepaper · full 风格）

**用户**："读一下这份 Gartner 关于 AI Infra 的报告"

**agent 工作流**：

1. "Gartner 报告" → `--type whitepaper`
2. 反问输出路径 → 用户答 `~/wiki/industry/raw/whitepapers/ai-infra-2026/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/gartner-ai-infra-2026.pdf \
  --type whitepaper \
  --output ~/wiki/industry/raw/whitepapers/ai-infra-2026/
# 产物：summary.md（按 PDF 原生章节顺序全文级转写；含行业数据表 / 对比表 / 客户案例 /
#         章节末尾的 Conclusion + Key Takeaways；无 PNG；发布立场"行业中立"在元信息段标注）
# 产物供 llm-wiki ingest_diff 二次蒸馏，不直接给人阅读
```

### 样例四：书籍（full 模式）

**用户**："我想把这本《Crafting Interpreters》转成 markdown 方便后续 Q&A"

**agent 工作流**：

1. 书籍 → `--type book`（脚本自动启用 `--full`）
2. 反问输出路径 → 用户答 `~/wiki/llm-systems/raw/books/crafting-interpreters/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/books/crafting-interpreters.pdf \
  --type book \
  --output ~/wiki/llm-systems/raw/books/crafting-interpreters/
# 产物：<slug>.md（按 Chapter / Part / Appendix 顺序全量转写）
# book 长篇不需额外传 --model（默认已走 pro-preview）
```

### 样例五：不确定类型（auto-detect）

**用户**："总结一下这份 PDF"

**agent 工作流**：

1. 用户没说类型 → 用 `--auto-detect`；同时反问输出路径

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/unknown.pdf \
  --auto-detect \
  --output ~/wiki/llm-systems/raw/manuals/foo/    # 类型由 auto-detect 决定，路径仍是用户指定
# 脚本 INFO: auto-detect 判定 --type manual
# 产物：summary.md（manual 模板）
```
