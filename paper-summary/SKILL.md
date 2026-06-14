---
name: paper-summary
description: 用 Gemini API 读取本地 PDF 论文，生成中文结构化总结（研究问题/方法/关键结果/贡献/局限）。当用户要把一篇学术论文 PDF 总结成中文、或需要快速读懂一篇论文时使用；不适用于非 PDF 来源或需要逐字翻译全文的场景
dependencies:
  - google-genai（Python SDK，pip install -U google-genai）
---

# Paper Summary

用 Gemini API 原生读取本地 PDF 论文（含正文、图表、公式），生成一份
**中文结构化总结**。借助 Gemini 的多模态 + 长上下文能力，直接"读懂"PDF 原文，
而不依赖外部 OCR 或文本抽取管线。

## 何时使用 / 不使用

### 使用

- 用户提供一篇**本地 PDF 论文**路径，想要一份中文总结
- 需要快速掌握一篇论文的研究问题、方法、结果与贡献
- 论文含大量图表 / 公式，纯文本抽取会丢失关键信息

### 不使用

- 论文不是 PDF（网页链接、纯文本、Markdown 等）——先转成 PDF 或改用其他 skill
- 需要**逐字翻译 / 复刻全文**（本 skill 是"总结"不是"全文翻译"）
- 需要**对比多篇论文**（本 skill 一次只处理一篇）
- 用户未配置 `GEMINI_API_KEY` 且不愿配置

## 输入 / 输出

### 输入

- **论文 PDF 路径**（必选）：本地 `.pdf` 文件的绝对或相对路径
- **`GEMINI_API_KEY`**（必选）：环境变量。在
  [Google AI Studio](https://aistudio.google.com/apikey) 创建后，
  `export GEMINI_API_KEY="你的key"`
- **模型**（可选，默认见"执行原则"）
- **关注点**（可选）：用户特别想了解的方面，如"重点关注实验部分"

### 输出

一份中文 Markdown 总结，固定结构：

1. **一句话速览**：这篇论文解决了什么问题、核心贡献是什么
2. **研究问题 / 动机**：为什么要做这个研究
3. **方法**：核心思路与技术路线（含关键图表 / 公式的简要说明）
4. **关键结果**：主要实验结论与数据（保留具体数值）
5. **贡献与创新点**
6. **局限与未来工作**
7. **(可选) 启发 / 追问**：基于用户关注点延伸的思考

## 执行原则 / 边界

### 核心原则

1. **用 PDF 原文，不要先抽文本**
   - 直接把 PDF bytes 以 `application/pdf` 交给 Gemini，保留图表 / 公式信息
   - 不要用 pdftotext / PyPDF2 之类先抽成纯文本（会丢图表）
2. **总结，不是复述**
   - 输出是提炼后的结构化总结，单篇约 600–1200 字
   - 关键数据 / 结论保留具体数值，避免泛泛而谈
3. **忠于原文，不脑补**
   - 论文没说的不要编；不确定处标注"原文未明确"
   - 引用关键结论时点明出自论文哪个部分（如"见实验部分"）
4. **专业术语保留英文**
   - 中文总结里，专有名词 / 术语保留英文原文（如 Transformer、RLHF），
     避免生硬翻译
5. **模型选择**
   - **首选 Pro 级模型**（如 `gemini-3-pro`），论文理解质量最佳
   - **备选 `gemini-3.5-flash`**：更快更省，1M token 上下文处理长论文也够用
   - Pro 系列确切版本号以最新 Gemini 文档为准；可用本仓库 `gemini-api-dev` skill
     或 `gemini-api-docs-mcp`（`get_current_model`）核实当前可用模型

### 边界

- 只处理本地 PDF；非 PDF 来源先转换
- 不做全文逐字翻译、不输出与原文篇幅相当的复述
- 一次只总结一篇论文

## 工作流 / 步骤

1. **确认前置条件**
   - 检查 PDF 文件存在且可读
   - 检查 `GEMINI_API_KEY` 已设置；未设置则提示用户配置后再继续
   - 确认 `google-genai` 已安装：`pip install -U google-genai`
2. **读取 PDF**：以二进制方式读取 PDF 文件得到 bytes
3. **调用 Gemini 生成总结**
   - 用 `types.Part.from_bytes(data=<pdf_bytes>, mime_type="application/pdf")`
     把 PDF 作为多模态输入传入
   - 附上结构化总结的中文 prompt（见下方调用模板）
   - 取 `response.text` 作为总结
4. **整理输出**
   - 按上述固定结构组织 Markdown
   - 若用户给了关注点，在总结中相应侧重，或追加"启发 / 追问"小节
5. **报告**：把总结呈现给用户，标注所用模型与论文文件名

### 核心调用模板（Python / google-genai SDK）

```python
from google import genai
from google.genai import types

client = genai.Client()  # 自动读取环境变量 GEMINI_API_KEY

MODEL = "gemini-3-pro"  # 备选: "gemini-3.5-flash"
pdf_path = "path/to/paper.pdf"

with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

prompt = """你是一位学术论文阅读助手。请基于这篇论文，用**中文**输出一份结构化总结，严格包含以下小节：

1. 一句话速览
2. 研究问题 / 动机
3. 方法（说明核心思路，简要提及关键图表 / 公式的作用）
4. 关键结果（保留具体数值与对比）
5. 贡献与创新点
6. 局限与未来工作

要求：忠于原文，论文未提及的内容标注"原文未明确"；专业术语保留英文原文；
用 Markdown 标题分节，整体 600–1200 字。"""

response = client.models.generate_content(
    model=MODEL,
    contents=[
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        prompt,
    ],
)

print(response.text)
```

### 进阶用法

- **结合用户关注点**：在 prompt 末尾追加，
  如 `请额外重点分析：这篇方法能否用在时序数据上？`
- **结构化输出（JSON）**：需要机器消费时，加
  `config={"response_mime_type": "application/json", "response_json_schema": <schema>}`
  让 Gemini 返回固定结构 JSON
- **超大 PDF（接近 / 超 1M token）**：改用 File API 上传后引用——
  `uploaded = client.files.upload(file=pdf_path)`，再把 `uploaded` 放进 `contents`

## 参考样例

### 样例一：基础总结

**用户指令**："帮我把 `~/papers/attention_is_all_you_need.pdf` 总结成中文"

**执行**：

```text
1. 确认 PDF 存在、GEMINI_API_KEY 已设置
2. 读取 PDF bytes
3. 用 gemini-3-pro + 上面的 prompt 调用 generate_content
4. 把返回的 Markdown 总结呈现给用户，注明模型与论文文件名
```

### 样例二：带关注点

**用户指令**："总结 `~/papers/diffusion.pdf`，我想了解它的数学推导和采样效率"

**执行**：

```text
1. 同上读取 PDF
2. 在 prompt 末尾追加："请额外重点分析：数学推导的关键步骤，以及采样效率如何。"
3. 调用 Gemini，在"方法 / 关键结果"小节侧重这两点，并补"启发 / 追问"小节
```

### 样例三：成本优先（批量速览）

**用户指令**："我有 20 篇论文要快速过一遍，每篇简短总结就行"

**执行**：

```text
1. 改用 gemini-3.5-flash（更快更省），prompt 里要求每篇 300 字内的速览版
2. 逐篇调用（一次一篇），串行或受控并发
```

## 参考文档

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
- [获取 API Key](https://aistudio.google.com/apikey)
