# yzr 个人 SKILLs

个人自定义 AI skills 合集，经 npx 分发；本仓同时是“造 skill”的元仓。
仓库规约与常用命令见 [AGENTS.md](./AGENTS.md)（项目上下文单一真源）。

## SKILLs 名单

- `yzr-skill-management`（元）—— 创建 / 改进 / 审计 skill 本身，维护骨架标准
- `yzr-coding-review` —— 代码 review（合理性审视 + 重构场景，语言中立，默认不改文件）
- `yzr-writing-style` —— 公共写作风格规则集（写作时遵循 + 审计时当标尺；多模型交叉评审）
- `yzr-md-to-html` —— 本地 md 转自包含 HTML（深色主题 + 侧边栏 + 公式 / mermaid）
- `yzr-sys-design-doc` —— 系统设计文档写作（full / lite 两档 + 实施任务书）
- `yzr-memory-management` —— 项目记忆管理（MEMORY/ 沉淀 · 体检 · 防腐化防膨胀）

## 提示词模板

- [`prompts/paper-summary.md`](./prompts/paper-summary.md) —— 上传论文 PDF 即用的总结提示词
  （3 句话总结 + 方法 / 实验 / 启示结构化输出，术语分层保留英文，适配 Outline 归档）

## 快速开始（开发环境）

首次备齐工具链（pyyaml / ruff / markdownlint-cli）：

```bash
python3 scripts/install-dev-deps.py
```

幂等、跨平台；环境变量与 PEP 668 细节见脚本头部 docstring。

## 设计原则

- 参考 [Claude 官方指导](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
  与 [anthropics/skills 的 skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
- 骨架标准与实现原则见 [`./yzr-skill-management`](./yzr-skill-management)
