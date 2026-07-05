# Auto-detect 实现细节

被 `scripts/gemini_pdf_summary.py --auto-detect` 调用，由 `scripts/auto_detect.py` 实现。

## 整体流程

```text
[用户传 --auto-detect 而非 --type]
  ↓
[Layer 1: 本地启发式]
  读 PDF 元数据（Title / Subject / Keywords / Producer）+ 首页文本
  按 KEYWORD_HINTS 打分 → {type: score}
  决策（HEURISTIC_CONFIDENCE_THRESHOLD=6 且 HEURISTIC_MARGIN_THRESHOLD=3）
  ├─ 高置信度 → 返回类型（无需调 Gemini，省 token）
  └─ 低置信度 → 进入 Layer 2
  ↓
[Layer 2: Gemini 验证]
  把首页 1-3 页用 pymupdf 渲染成 PNG（2x DPI ≈ 144 DPI）
  送 Gemini 多模态（默认 gemini-3.5-flash）+ 简短分类 prompt
  ├─ Gemini 返回合法类型（paper/manual/whitepaper/book）→ 返回
  └─ Gemini 返回 unknown 或异常 → 抛 RuntimeError → 建议用户显式传 --type
```

## Layer 1: KEYWORD_HINTS 表

每个类型 4-5 个正则模式 + 命中权重：

```python
KEYWORD_HINTS = {
    "paper": [
        (r"\b(abstract|introduction|methodology|related work|references)\b", 3),
        (r"\b(arxiv|doi:|proceedings of|acm|springer|ieee)\b", 2),
        (r"\b(neural network|transformer|gradient|backpropagation|loss function)\b", 2),
        (r"\b(et al\.|\[1\]|\[\d+\])\b", 2),
    ],
    "manual": [
        (r"\b(user manual|installation guide|getting started|quick start)\b", 3),
        (r"\b(datasheet|specifications?|technical specs|product specifications)\b", 2),
        (r"\b(operating instructions|setup guide|configuration)\b", 2),
        (r"\b(command line|cli|api reference|endpoint)\b", 1),
        (r"\b(warranty|troubleshooting|faq)\b", 1),
    ],
    "whitepaper": [
        (r"\b(white paper|industry report|market analysis|market research)\b", 3),
        (r"\b(executive summary|introduction|challenges?|solutions?)\b", 1),
        (r"\b(case study|customer success|roi|total cost of ownership)\b", 2),
        (r"\b(gartner|forrester|idc|mckinsey|deloitte)\b", 2),
    ],
    "book": [
        (r"\b(chapter \d+|part [ivx]+|appendix|index)\b", 3),
        (r"\b(table of contents|foreword|preface|acknowledg(?:e?)ments)\b", 2),
        (r"\b(edition|hardcover| paperback|publisher:?|isbn)\b", 2),
        (r"\b(exercises?|review questions|further reading)\b", 1),
    ],
}
```

**阈值常量**（在 `auto_detect.py` 顶部）：

- `HEURISTIC_CONFIDENCE_THRESHOLD = 6`：top-1 类型总分 ≥ 6 才视为高置信
- `HEURISTIC_MARGIN_THRESHOLD = 3`：top-1 - top-2 ≥ 3 才视为可决策

任一不满足 → 进入 Layer 2。

## Layer 2: Gemini 验证

**Prompt**（`auto_detect.py::_ask_gemini_for_type`）：

```text
你是文档类型分类助手。基于这份 PDF 的首页 1-3 页版式 / 标题 / 排版风格，
判断它属于以下哪一类（只输出单词，不解释）：
  paper      - 学术论文（含 abstract / introduction / 双栏 / 公式 / 引用列表）
  manual     - 产品手册 / datasheet / 用户手册（含产品规格表 / 安装步骤 / API endpoint）
  whitepaper - 行业 / 技术 / vendor 白皮书（含 executive summary / market analysis / case study）
  book       - 书籍 / 长篇技术文档（含 chapter / part / appendix / 索引）
如果无法判断，输出: unknown
```

**调用约束**：

- 渲染倍率 2x DPI（≈ 144 DPI）—— 与 paper quick Stage 2 一致，保证 Gemini 看得清版式细节
- `temperature=0.0` —— 分类任务不要随机性
- `max_output_tokens=16` —— 只输出一个单词
- 解析：取响应 `text` 的首个 token，去掉 `.,;:!?"'` 等标点
- 若首 token 不在 `VALID_TYPES` → 抛 RuntimeError

## 失败兜底

| 失败模式 | 兜底 |
| --- | --- |
| PDF 文件不存在 | `RuntimeError("PDF 文件不存在: <path>")` |
| pymupdf 缺失 | 脚本 exit(2)，提示安装命令 |
| GEMINI_API_KEY 未设（仅 Layer 2 需要） | 脚本 exit(2)，提示设置环境变量 |
| google-genai 缺失 | 脚本 exit(2)，提示安装命令 |
| Gemini 返回 unknown / 非合法值 | 抛 RuntimeError，提示用户显式传 `--type` |
| Gemini 调用异常（网络 / 503 等） | Layer 2 重试由 `_gemini_call_with_retry`（gemini_pdf_summary.py 已实现）负责；本脚本不重复实现 |

最终 `auto_detect.detect_doc_type()` 抛 RuntimeError 时：

- 错误信息含具体原因 + "请显式传 `--type <paper|manual|whitepaper|book>`"
- gemini_pdf_summary.py main() 捕获后打印 + exit(3)

## 扩展点

**新增类型**（如 datasheet / report / presentation）需要：

1. 在 `KEYWORD_HINTS` 加新类型 + 4-5 个关键词模式
2. 在 `gemini_pdf_summary.py` 的 `VALID_TYPES` 加新值
3. 在 Layer 2 prompt 加新类型一行
4. 新建 `assets/template-<new_type>.md`
5. 更新 `SKILL.md` 描述 + 触发说明

**调阈值**：根据实际评估集（manual 跑过几份 PDF 才知道）调整
`HEURISTIC_CONFIDENCE_THRESHOLD` / `HEURISTIC_MARGIN_THRESHOLD` —— 当前值是经验值。
