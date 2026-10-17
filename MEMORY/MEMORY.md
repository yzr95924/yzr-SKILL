# MEMORY/

## 规则

- Skill 黑盒化：规范归 yzr-skill-management 设计原则“脚本黑盒化”
- [LLM 调用一律 harness subagent](llm-worker-subagent.md)：skill 起额外 LLM worker 用会话内 subagent，不起 CLI 子进程；无此能力时如实退回单模型
- 新增运行时机制前先问防的事故真实发生过吗：文档 / 测试 / 纪律能给确定性的，不落成运行期脚本与协议
