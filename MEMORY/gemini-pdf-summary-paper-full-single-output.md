---
name: gemini-pdf-summary-paper-full-single-output
description: gemini-pdf-summary paper --full 模式从"双产物 quick+full"翻为"单产物 full"的设计决策与边界（2026-07-07 翻面）
metadata:
  type: project
  supersedes: gemini-paper-summary-full-mode-design.md §1 (D1) + §2（双产物 why）
---

# gemini-pdf-summary paper --full 单产物设计（2026-07-07 翻面）

## Why

`gemini-pdf-summary` 的 `paper --full` 模式原设计是"单次调用同时产 quick summary +
full PDF→Markdown 全量转写"——一份调用两份产物对齐走
`raw/papers/<slug>.{quick,full}.md`。MEMORY §1 (D1) + §2 给出 rationale：避免重复 token
开销、保证 quick 与 full 在同一文件族对齐、保持"一次成型"的产品形态。

**翻面原因（2026-07-07）**：

1. **产品定位已分家**。`gemini-pdf-summary-manual-whitepaper-full-design.md` D1 已经把
   manual / whitepaper / book 翻为"full 风格 = 给 LLM 消费的下游产物（供 llm-wiki 二次
   ingest）"，把 paper quick 孤立为"给**人**看的精炼速读"。换句话说，quick 与 full 的
   消费对象本就不同——quick 给人看（≤ 2500 字符、6 H2 骨架、带图）、full 给 LLM 看（PDF 原生
   章节顺序、自包含无图）。把它们绑在一份调用里反而强迫 agent 同时承担"人 + LLM"两条
   产品线。
2. **下游消费方不需要"对齐"**。`llm-wiki-management` 的 ingest_diff 只读 full.md 当
   source 蒸馏；quick summary 若要给"未来 publish 流程"用，由未来 publish skill 自己
   跑 quick 模式拿，比"夹带在 --full 产物里"更干净。
3. **避免无谓 token 开销**。用户只想跑 full 拿 Q&A 底座时，被动多走一遍 quick summary
   调用；用户只想看 quick + 带图时，被动多走一遍 full 调用。一次成型的卖点是"省心"，
   代价是"贵 token + 副作用"——当产物定位分家后，省心已无意义（quick 与 full 互不消费
   对方的产物），副作用反而成了负资产。

## How to apply

未来给 `gemini-pdf-summary` 加内容或改模板时：

1. **paper `--full` 永远保持 single-output**——只产 `<wiki_root>/raw/papers/<slug>.full.md`，
   不写 `.quick.md`、不落 PNG、不跑 Stage 2
2. **quick 与 full 是独立触发**：`--type paper` 默认 = quick 模式（带图）；
   `--type paper --full` = full 模式（自包含无图）。两个 flag 不再"一份调用塞两份"
3. **改 `_run_full_mode` / 改 `paper --full` 行为前先读 SKILL.md §输出 +
   `references/full-mode-contract.md` §接口约定核心**，避免重新走"双产物"老路
4. **`--force-full` 只保护 `.full.md`**（不再保护已删除的 `.quick.md`）；默认拒绝覆盖
   full 抽取的理由不变（保护下游已多次引用的 raw）
5. **图处理硬边界**：full 模式不落 PNG；想看 PNG 跑 quick 模式（默认）或 `--extract-figures`
   单跑

## 4 个设计决策（SSOT）

### D1：paper `--full` 单产物（与 manual/whitepaper/book 对齐）

**2026-07-07 翻面前**：`_run_full_mode` 单次调用产 `.quick.md + .full.md` 双份
（quick = academic 模板 ≤ 2500 字符 + 落 PNG；full = full 模板全文级 + 不落 PNG）。

**翻面后**：`_run_full_mode` 单次调用只产 `.full.md` 一份（full 模板全文级 +
不落 PNG）。quick summary 与 full **完全解耦**——quick 走 `--type paper` 默认，full
走 `--type paper --full`，两个独立触发、各走各的产物 layout。

4 类 full 现在的产物形态完全对齐：

| 类型 | 触发 | 产物 layout |
| --- | --- | --- |
| paper full | `--type paper --full` | `<wiki_root>/raw/papers/<slug>.full.md`（单文件） |
| manual | `--type manual` | `<output>/summary.md`（单文件） |
| whitepaper | `--type whitepaper` | `<output>/summary.md`（单文件） |
| book | `--type book`（自动 full） | `<output>/<slug>.md`（单文件） |

### D2：quick 与 full 的消费对象已分家

- **quick**（paper 默认）= 给**人**看的精炼速读：≤ 2500 字符 + 6 H2 骨架 + 带 PNG +
  学术总结视角
- **full**（paper `--full` + manual + whitepaper + book）= 给 LLM 消费的下游产物：
  解除字符上限 + 按 PDF 原生章节顺序 + 自包含无图 + 蒸馏/查询底座视角

把 quick 与 full 绑在一份调用里，等于强迫 agent 同时承担"人 + LLM"两条产品线。
翻面后，quick 与 full 各跑各的，agent 按用户意图选对应模式。

### D3：full 模式的图表示仍走 mermaid / ASCII / 表格（不变）

本翻面不动 full 模式的图处理约定——架构/概念图直接 mermaid block、数据可视化图转
markdown 表格、装饰图省略 + 文字一句。`raw/assets/<slug>/fig-NN.png` 不创建（仍由
quick 模式或 `--extract-figures` 单跑产生）。

### D4：`--force-full` 保护范围缩窄

翻面前：`--force-full` 允许覆盖 `raw/papers/<slug>.{quick,full}.md` 两份。

翻面后：`--force-full` 只允许覆盖 `raw/papers/<slug>.full.md`（quick.md 不再产生）。

## 关键纪律（4 类 full 都遵守）

- **不落 PNG**：full 模式产物自包含无图，layout 是 raw-compatible（或单文件 `<output>/`），
  不消费 `--extract-figures` / `--no-figures`（这些仅 paper quick 模式生效）；
  manual / whitepaper / book 默认就全程不抽 PNG
- **Stage 2 / `--refine-figures` 在 full 模式是哑参数**：full 不跑 Stage 2、不写
  `![图 N](...)` 引用、要 PNG 走 paper quick 模式或 `--extract-figures`
- **`--focus` 走 FOCUS_INJECTION_FULL**：full 没有 summary 段，focus 不能追加到末尾——
  而是**注入到对应的 PDF 原生章节下**，形式为 `### 用户关注点: <focus>` 子节
- **完整性 > 篇幅**：token 预算紧张时**优先精简措辞、缩具体例子 / 长引文 / 重复论证**；
  **禁止**合并整段、删除小节、跳过该类型必保真的元素

## 历史兼容 / 与旧 MEMORY 的关系

- 旧 `gemini-paper-summary-full-mode-design.md` §1 (D1) + §2（双产物 why）被本文件
  supersede；§3 / §4 / §5 / §5.1 / §6 / §7（其它决策如 raw-compatible layout、
  不落 PNG、PDF 原生章节顺序等）仍有效，未变
- 旧 `gemini-paper-summary-full-mode-design.md` §0 一句话总结 + §7 产物清单里
  "`<root>/raw/papers/<slug>.full.md + <slug>.quick.md`"双产物描述需同步翻面：
  仅 `full.md`，quick 不再由 `--full` 产出
- 脚本侧 `_run_full_mode` 函数（`scripts/gemini_pdf_summary.py:2442`）已翻面：
  移除 quick prompt 调用、移除 quick.md 写入、移除 quick.md overwrite 检测
- `references/full-mode-contract.md` 全文已翻面：§接口约定核心 paper `--full`
  单产物段、§产物 layout 表、§by-chapter 与现有 4 类 full 的对比表、§关键纪律
  paper `--full` 专属纪律段、§反模式 paper 专属段、§专属故障排查 paper 专属段
- `SKILL.md` 已翻面：frontmatter description 从"paper full（全文转写双产物）"改为
  "全文级 PDF→Markdown 转写，单产物"；§故障排查 `--by-chapter` 与 `--full` 互斥
  处置行从"双产物"改为"单产物"
- `eval/evals.json` 三条 paper full 测试用例（id 1/2/3）已翻面：断言清单去掉
  "两份产物落 raw-compatible layout" / "quick summary ≤2500 字符精炼" /
  "焦点在 quick 模板走 FOCUS_INJECTION"等依赖双产物的断言

## 翻面动机详情（why 这次彻底翻面，不留 `--quick-and-full` 中间态）

考虑过 `--quick-and-full` flag 让用户显式选双产物，但决定不留中间态的理由：

1. **双产物的"省心"卖点已消失**。manual / whitepaper / book 已经走单产物形态，
   paper --full 再保留双产物会让 4 类 full 不统一，agent 写 prompt 时要做
   "我跑 manual 拿单文件、跑 paper --full 拿两份"的心智切换——这个切换对下游
   消费方（llm-wiki ingest）毫无价值（ingest 只读 full.md）
2. **未来如果有人想要双产物，单独跑 quick + 单独跑 full 即可**，开销上 ~2x 调用
   但产物定位清晰。脚本不必为这种需求背复杂度的锅
3. **eval / debug 友好**：单产物调用出错时排错路径短（一份产物 + 一次调用），
   双产物出错要判断是哪一份、哪一次调用导致——已经吃过这个亏（gemini-white-paper-err.md
   提到 98 页白皮书 1 次调用 → 35%+ 章节截断，与双产物不同但都属于"一次调用 →
   多产物"的复杂度累积）

## 关联

- [[gemini-pdf-summary-manual-whitepaper-full-design]] — 本翻面的前置（manual / whitepaper
  / book 单产物化的 2026-07-05 翻面）
- [[gemini-paper-summary-full-mode-design]] — 旧 skill 时代的设计 SSOT；§1 (D1) + §2 由
  本文件 supersede
- [[gemini-paper-summary-figure-extraction-edges]] — Stage 2 / `--extract-figures` 的
  边界（quick 与 full 翻面不影响 PNG 落盘的合法路径）
- [[paper-wiki-integration-design]] — 下游 llm-wiki ingest 的契约（只读 full.md 当
  source 蒸馏）
- [[skill-source-priority-over-memory-vendor]] — SKILL.md 与 references/ 是设计真源，
  本 MEMORY 是 why 的归档；改设计时改 SKILL.md / references/，MEMORY 同步归档
