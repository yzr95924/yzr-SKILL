# 4 类模板对照

| 维度 | paper quick | paper full | manual（full） | whitepaper（full） | book（full） |
|---|---|---|---|---|---|
| 模板文件 | `assets/template-paper.md` §quick 模式 | §full 模式 | `assets/template-manual.md` | `assets/template-whitepaper.md` | `assets/template-book.md` |
| 字符目标 | ≤ 2500 | 无上限（token 紧张时优先精简） | 无上限（完整性 > 篇幅） | 无上限（完整性 > 篇幅） | 无上限（完整性 > 篇幅） |
| 章节结构 | 6 H2 骨架 + 团队/3句话/背景/方法或评测/启示/局限 | 按 PDF 原生 Section 顺序 | 按 PDF 原生目录结构（原英文标题保留） | 按 PDF 原生目录结构（原英文标题保留） | 按 PDF 原生 Chapter / Part / Appendix / Index |
| 开篇结构 | 3 列表格（Title / Venue / Topic） | 一行 metadata table | 3 列表格（Title / Type / Vendor）+ 手册版本/目标读者/关联产品 items | 3 列表格（Title / Publisher / Topic）+ 发布日期/目标读者/**发布立场** items | 一行 metadata table（Title / Author / ISBN / ...） |
| 关键标注 | `###` 设计点子段 | Definition / Theorem / Lemma / Algorithm | 命令清单 / 参数表 / 错误码表 / 故障排查 + FAQ + 更新日志要点 | 行业数据表 / 对比表 / 客户案例 / Conclusion + Key Takeaways + Recommendations / **立场甄别** | 章节层级 + 索引 term → page |
| 图表处理 | **抽原始 PDF 图** → `figures/*.png`（默认开） | mermaid / 表格 / ASCII（不落 PNG） | mermaid / 表格 / ASCII（不落 PNG） | mermaid / 表格 / ASCII（不落 PNG） | mermaid / 表格 / ASCII（不落 PNG） |
| 公式处理 | 不写 `$...$`（paper quick 不用） | 行内 `$...$` | 不用 | 不用 | 行内 `$...$`（book 保留 LaTeX 给 agent Q&A） |
| 评测 / benchmark 分支 | 是（"方法+实验" ↔ "评测设计+发现"） | 否（按 PDF 原生） | 否 | 否 | 否 |
| `--focus` 注入 | 末尾追加 "启发 / 追问" 段 | 在对应原生章节下追加子段（`### 用户关注点: <focus>`） | 在对应原生章节下追加子节 | 在对应原生章节下追加子节 | 在对应原生章节下追加子节 |
| 消费对象 | **人**（唯一保留 quick 的类型） | LLM（Q&A 底座） | LLM（llm-wiki 二次 ingest） | LLM（llm-wiki 二次 ingest） | LLM（章节级 Q&A） |

## 模板变更规则

> **任何模板变更只需要改对应 `assets/template-<type>.md`，SKILL.md 不重抄避免散落。**

模板 markdown 内 prompt 正文统一用 `````text` 4-backtick fence 包裹
（因为 prompt 内部要嵌套 markdown / mermaid 代码块示例），
脚本 `scripts/gemini_pdf_summary.py::_load_prompt_for_type` 用正则抽该 fence 内容。

### 段标题约定

每个模板 `## <段名>` 段名在脚本 `_load_prompt_for_type` 的 `head_patterns` 字典里：

| 类型 / 模式 | 段标题 | 备注 |
|---|---|---|
| paper / quick | `## quick 模式（默认）` | 唯一保留 quick 风格的档位 |
| paper / full | `## full 模式（`--full`）` | 显式 `--full` 启用 |
| manual / full（单模板） | `## 模板` | 单模板即 full；脚本 `prompt_mode = "full"` 已硬编码 |
| whitepaper / full（单模板） | `## 模板` | 单模板即 full；同上 |
| book / full | `## 模板` | 单 full；`--type book` 自动启用 full |

**改模板时同步检查**：

1. 改完段标题 → 同步 `head_patterns` 字典里的正则
2. 改完字符数目标 → SKILL.md §输出的"字符数目标"小节**也**改（这是 SSOT 例外：模板与 SKILL.md 都要出现具体值，模板是 prompt 给 Gemini 的目标，SKILL.md 是给 agent 看的目标；两者必须同步）
   - **注意**：manual / whitepaper / book / paper full 是 full 风格，**无字符数上限**——不在 SSOT 例外范围（无需在 SKILL.md 字符数小节同步具体值）
3. 改完章节顺序 → SKILL.md §工作流 §C 对应类型的章节骨架块**也**改（同上 SSOT 例外）

## 写作样例（4 类各一份）

### paper quick

```markdown
| **Title** | **Venue** | **Topic** |
|-------|-------|-------|
| The Adaptive Radix Tree | ICDE'13 | Index structure |

* 论文链接（**留空，由用户在 Outline UI 手动填写**；Gemini 不必补）

  > <TODO>

* **团队/机构**：Viktor Leis; TU Munich; database systems

## 3 句话总结

1. **问题 + 方法**：ART 是为通用主存数据库设计的自适应基数树索引
2. **核心设计 / 关键数据**：4 种自适应内部节点 + 路径压缩 + 延迟扩展
3. **落地 / 影响**：在 HyPer 中实现并超越 B+ 树与 FAST 索引

## 背景与动机
...
```

### manual（full 风格）

```markdown
| **Title** | **Type** | **Vendor** |
|-------|-------|-------|
| NVIDIA H100 SXM Datasheet | GPU | NVIDIA |

* **手册版本 / 日期**：H100 SXM5 80GB v1.0（2026-03-15）
* **目标读者**：HPC 工程师 / ML 基础设施架构师
* **关联产品**：H100 NVL / H200 / GH200

## Hardware Specifications

| 参数 | 值 |
| :--- | :--- |
| **架构** | Hopper (GH100) |
| **CUDA cores** | 14592 |
| **Tensor cores** | 456（第 4 代） |
| **显存** | 80 GB HBM3 |
| **显存带宽** | 3.35 TB/s |
| **TDP** | 700W |
| **FP8 Tensor Core** | 1979 TFLOPS |

## NVLink & NVSwitch

```mermaidjs
graph LR
    A[H100 SXM] -->|NVLink 4.0<br/>900 GB/s| B[H100 SXM]
    A -->|NVSwitch 3.0| C[H100 SXM]
    A -->|NVSwitch 3.0| D[H100 SXM]
    A -->|PCIe Gen5<br/>128 GB/s| E[CPU Host]
```

## Installation

* 将 H100 SXM 插入主板 NVLink 插槽，确保电源连接
* ...（按 PDF 原生章节展开）

## Troubleshooting

| 错误码 | 含义 | 处置 |
| :--- | :--- | :--- |
| `E-1001` | NVLink 握手失败 | 重启 + 检查插槽 |
| `E-2003` | HBM3 ECC 不可纠正错误 | 立即停机，更换 GPU |
| ...
```

### whitepaper（full 风格）

```markdown
| **Title** | **Publisher** | **Topic** |
|-------|-------|-------|
| The State of AI Infrastructure 2026 | Gartner | AI Infra / LLM serving |

* **发布日期**：2026-02-10
* **目标读者**：CTO / 基础设施架构师 / 投资人
* **发布立场**：行业中立研究

## Executive Summary

* LLM serving 基础设施市场 2025 年规模约 $80B，预计 2028 年达 $420B（CAGR 70%+）。

## Market Analysis

### Market Size & Growth

| 年份 | 市场规模 | YoY 增长 |
| :--- | :--- | :--- |
| 2024 | $48B | — |
| 2025 | $80B | +66.7% |
| 2028E | $420B | CAGR ~70% |

### Key Drivers

* **模型规模扩张**（单卡推理已成少数）
* **推理成本压力**（token 成本压缩 10×）
* **多模态兴起**（GPU 利用率优化空间大）

## Challenges

* GPU 短缺与利用率不均并存
* ...

## Solution Framework

* 异构调度（GPU + NPU + CPU 协同）
* 推测解码（speculative decoding）规模化部署
* KV cache 跨请求复用（prompt cache）作为一级架构

## Conclusion & Recommendations

* **结论**：未来 3 年 LLM serving 基础设施的核心矛盾从"卡够不够"转向"调度够不够聪明"
* **建议**：
  * 阶段 1（0-6 月）：内部推理网关 + 缓存复用 → 成本 -30%
  * ...
```

### book

```markdown
| **Title** | **Author** | **Year** |
|-------|-------|-------|
| Crafting Interpreters | Robert Nystrom | 2021 |

## Part I: Tree-Walking

### Chapter 2: A Map of the Territory

* 解释编译器与解释器的本质差异：编译器提前翻译成机器码，解释器边执行边翻译
* 引入 jlox（Java 语言实现）与 clox（C 语言实现）两条平行路径的设计

### Chapter 3: The Lox Language

* Lox 语法示例：变量、表达式、控制流、函数、类
* 完整 grammar 定义（BNF 形式）

### Chapter 5: Representing Code

* 抽象语法树（AST）节点设计：Binary / Unary / Literal / Variable / Assign / ...
```

## 加新类型时的 checklist

如需扩展（如 datasheet / report / presentation），按以下顺序改：

1. **KEYWORD_HINTS** in `scripts/auto_detect.py`
2. **VALID_TYPES** in `scripts/gemini_pdf_summary.py`
3. **head_patterns** in `scripts/gemini_pdf_summary.py::_load_prompt_for_type`
4. **auto_detect.py::_ask_gemini_for_type prompt** 加新类型一行
5. **assets/template-<new_type>.md** 新建（参考 manual.md 模板）
6. **SKILL.md frontmatter description** 加新类型
7. **SKILL.md §输出的"按文档类型路由"小节** 加新类型一行
8. **SKILL.md §工作流 §C** 加新类型章节骨架块
9. **SKILL.md §故障排查** 任何相关报错处置
10. **eval/evals.json** 加新类型的 eval prompts（2-3 条）

> 改完跑 `python3 scripts/quick_validate.py gemini-pdf-summary`（yzr-skill-creator 提供）做 frontmatter 预检。
