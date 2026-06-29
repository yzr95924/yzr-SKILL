---
title: "MEMORY"
type: memory
tags: [memory]
created: 2026-06-28
updated: 2026-06-28
---

# MEMORY

> 本目录是 **LLM agent 的持久化记忆**——LLM 在 ingest / query / lint 工作过程中
> 沉淀的经验、踩坑记录、用户偏好都写到这里。
> 用户**不**直接编辑本目录；它是 agent 私有记录。

## 何时写

- **遇到踩坑**——raw/ 里的 PDF 经常有 OCR 错误，下次让用户先转换格式
- **发现用户偏好**——用户偏好表格化的对比、不喜欢散文式总结
- **跨 ingest 的关联**——两个 source 页指向同一篇会议论文的不同章节
- **lint 报告的 recurring pattern**——每次 lint 都报某个特定 type 缺字段

## 文件命名

- kebab-case（与 wiki 内容页一致）：`ocr-preprocessing.md` / `user-preferences.md`
- 文件命名按主题归类，不要按时间归档——本目录不是时间线

## 维护纪律

- frontmatter 5 必填（title / type / created / updated / tags）
- 写新文件时**保留**原文件的 `created` 字段；只更新 `updated`
- 不删除任何文件——踩坑记录沉淀下来，未来回顾有价值
