# Gemini API 调用速查（PDF 总结场景）

> 本文件给 agent 在会话内**直接调 SDK** 时的最小参考。`scripts/gemini_paper_summary.py`
> 已经把下面"基础调用"封装好了，遇到超大 PDF / 结构化输出 / 缓存等高级需求时再读本文件。

## 1. SDK 选择

- **新包（必选）**：`google-genai`（Python）/ `@google/genai`（JS/TS）
- **已弃用（不要用）**：`google-generativeai` / `@google/generative-ai`

```bash
pip install -U google-genai
```

环境变量：

```bash
export GEMINI_API_KEY="你的 key"   # 在 https://aistudio.google.com/apikey 创建
```

## 2. 基础调用：PDF → 总结

```python
from google import genai
from google.genai import types

client = genai.Client()  # 自动读 GEMINI_API_KEY

MODEL = "gemini-3.5-flash"  # 详见 SKILL.md §执行原则
pdf_path = "path/to/paper.pdf"

with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

# 7 段式 prompt 完整内容见 assets/prompt-template.md
prompt = """<复制 assets/prompt-template.md 里的 default 模板>"""

response = client.models.generate_content(
    model=MODEL,
    contents=[
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        prompt,
    ],
)

print(response.text)
```

## 3. 超大 PDF（> 50 MB 或接近 1M token）

走 **File API**：

```python
uploaded = client.files.upload(file=pdf_path, config={"display_name": "paper"})

response = client.models.generate_content(
    model=MODEL,
    contents=[uploaded, prompt],
)
```

文件留在 Google 服务端 48 小时；要主动清理：

```python
client.files.delete(name=uploaded.name)
```

## 4. 结构化输出（JSON）

需要让 Gemini 返回固定 schema 的 JSON 时，加 `config`：

```python
from google.genai import types

schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tldr": {"type": "string"},
        "method": {"type": "string"},
        "key_results": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "tldr", "method", "key_results"],
}

response = client.models.generate_content(
    model=MODEL,
    contents=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"), prompt],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema,
        temperature=0.2,
    ),
)
```

> Markdown 总结场景用不上 JSON schema；本 skill 默认要 Markdown 文本。

## 5. 模型选择

**模型选型表 SSOT 在 `../SKILL.md` §模型选型**——本文件不重复。调用 SDK 时直接用
默认（`gemini-3.5-flash`），需要换模型时从 SKILL.md §模型选型 查"何时显式覆盖"。

实际可用模型以当前文档为准：
- `mcp__gemini-api-docs-mcp__get_current_model`
- 或仓库内 `gemini-api-dev` skill

## 6. 错误码速查

| 错误 | 原因 | 处置 |
| --- | --- | --- |
| `401 UNAUTHENTICATED` | API key 无效 / 过期 | 重新生成 key |
| `403 PERMISSION_DENIED` | key 对该模型无访问权限 | 换模型或在 AI Studio 申请访问 |
| `400 INVALID_ARGUMENT` + PDF 提示 | PDF 损坏 / 加密 / 非 PDF 头 | `file <pdf>` 核实；解密或重下 |
| `413 REQUEST_TOO_LARGE` | 单次请求超限 | 改用 File API（见 §3） |
| `404 NOT_FOUND` | 模型名拼错 / 已下线 | 用 `get_current_model` 查当前可用名 |
| `429 RESOURCE_EXHAUSTED` | 触发限流 | 退避重试；批量时降并发 |

## 7. 参考链接

- Gemini API 官方文档：https://ai.google.dev/gemini-api/docs
- google-genai Python SDK：https://github.com/googleapis/python-genai
- Python SDK 完整示例：https://ai.google.dev/gemini-api/docs/sdks
