# 4 类模板对照

| 维度 | paper quick | paper full | manual | whitepaper | book |
|---|---|---|---|---|---|
| 模板文件 | `assets/template-paper.md` §quick 模式 | §full 模式 | `assets/template-manual.md` | `assets/template-whitepaper.md` | `assets/template-book.md` |
| 字符目标 | ≤ 2500 | 无上限（token 紧张时优先精简） | ≤ 3000 | ≤ 3500 | 无上限（完整性 > 篇幅） |
| 章节结构 | 6 H2 骨架 + 团队/3句话/背景/方法或评测/启示/局限 | 按 PDF 原生 Section 顺序 | 6 H2 骨架（产品概述/关键特性/接口与参数/适用场景/故障排查/附录） | 5 H2 骨架（行业背景/挑战与机遇/方案/案例/商业价值） | 按 PDF 原生 Chapter / Part / Appendix / Index |
| 开篇结构 | 3 列表格（Title / Venue / Topic） | 一行 metadata table | 3 列表格（产品名称 / 类型 / 厂商） | 3 列表格（白皮书标题 / 发布方 / 主题） | 一行 metadata table（Title / Author / ISBN / ...） |
| 关键标注 | `###` 设计点子段 | Definition / Theorem / Lemma / Algorithm | mermaid 架构图 + 参数表 | 客户案例表 + ROI 数字 | 章节层级 + 索引 term → page |
| 图表处理 | **抽原始 PDF 图** → `figures/*.png`（默认开） | mermaid / 表格 / ASCII | mermaid / 表格 / ASCII | mermaid / 表格 / ASCII | mermaid / 表格 / ASCII |
| 公式处理 | 不写 `$...$`（paper quick 不用） | 行内 `$...$` | 不用 | 不用 | 行内 `$...$`（book 保留 LaTeX 给 agent Q&A） |
| 评测 / benchmark 分支 | 是（"方法+实验" ↔ "评测设计+发现"） | 否（按 PDF 原生） | 否 | 否 | 否 |
| `--focus` 注入 | 末尾追加 "启发 / 追问" 段 | 在对应原生章节下追加子段 | 末尾追加 | 末尾追加 | 末尾追加 |

## 模板变更规则

> **任何模板变更只需要改对应 `assets/template-<type>.md`，SKILL.md 不重抄避免散落。**

模板 markdown 内 prompt 正文统一用 `````text` 4-backtick fence 包裹
（因为 prompt 内部要嵌套 markdown / mermaid 代码块示例），
脚本 `scripts/gemini_pdf_summary.py::_load_prompt_for_type` 用正则抽该 fence 内容。

### 段标题约定

每个模板 `## <段名>` 段名在脚本 `_load_prompt_for_type` 的 `head_patterns` 字典里：

| 类型 / 模式 | 段标题 |
|---|---|
| paper / quick | `## quick 模式（默认）` |
| paper / full | `## full 模式（`--full`）` |
| manual / quick 或 full | `## 模板` |
| whitepaper / quick 或 full | `## 模板` |
| book / full | `## 模板` |

**改模板时同步检查**：

1. 改完段标题 → 同步 `head_patterns` 字典里的正则
2. 改完字符数目标 → SKILL.md §输出的"字符数目标"小节**也**改（这是 SSOT 例外：模板与 SKILL.md 都要出现具体值，模板是 prompt 给 Gemini 的目标，SKILL.md 是给 agent 看的目标；两者必须同步）
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

### manual

```markdown
| **产品名称** | **类型** | **厂商** |
|-------|-------|-------|
| NVIDIA H100 SXM | GPU | NVIDIA |

* **手册版本 / 日期**：H100 SXM5 80GB v1.0（2026-03-15）
* **目标读者**：HPC 工程师 / ML 基础设施架构师
* **关联产品**：H100 NVL / H200 / GH200

## 产品概述
...

## 关键特性

* **FP8 Transformer Engine**：训练 / 推理时自动在 FP8 / FP16 间切换
```mermaidjs
graph LR
    A[H100 SXM] -->|NVLink 4.0<br/>900 GB/s| B[H100 SXM]
    A -->|NVSwitch 3.0| C[H100 SXM]
```
```

### whitepaper

```markdown
| **白皮书标题** | **发布方** | **主题** |
|-------|-------|-------|
| The State of AI Infrastructure 2026 | Gartner | AI Infra |

* **发布日期**：2026-02-10
* **发布立场**：行业中立研究

## 行业背景
* LLM serving 基础设施市场 2025 年规模约 80 亿美元，预计 2028 年达 420 亿美元

## 解决方案 / 核心主张
* **核心主张**：未来 3 年 LLM serving 基础设施的核心矛盾从"卡够不够"转向"调度够不够聪明"
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
