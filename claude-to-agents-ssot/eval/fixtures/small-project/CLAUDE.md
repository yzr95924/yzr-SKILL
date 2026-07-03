# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

`pdf-toc-extractor` 是一个把扫描版 PDF 的目录页 OCR 成结构化 JSON 的小工具。
输入 PDF，输出 `{ title, page, level }` 列表。单用户、本地运行。

## 仓库规约

- 所有 Python 代码用 `ruff` 格式化，行宽 100。
- 函数必须有类型注解。
- 提交信息用 `feat: / fix: / chore:` 前缀。

## 常用命令

### 运行

```bash
python3 -m pdftoc --input paper.pdf --output toc.json
```

### 评估

```bash
python3 scripts/run_eval.py --eval-set evals/evals.json
```

`scripts/run_eval.py` 调用 `claude -p` 子进程跑端到端用例，需要本机已安装并登录 Claude Code。

## 高层结构

```
.
├── pdftoc/            主包（OCR + 结构化）
├── scripts/run_eval.py
└── evals/             评估用例
```

## 注意事项

- OCR 引擎用 Tesseract；首次运行需 `apt install tesseract-ocr`。
- 不要把 `evals/outputs/` 提交进 git（已在 .gitignore）。
