---
name: llm-worker-subagent
description: skill 需要起额外 LLM worker（评审员 / judge / 对照侧）时一律用会话内 harness subagent，不起 opencode run 之类 CLI 子进程；harness 无此能力时如实退回单模型现状
metadata:
  type: feedback
  scope: 各 skill 多模型 / 评估管线的 worker 发起机制选型
  modified: 2026-10-08
---

# LLM 调用一律 harness subagent

- skill 需要额外 LLM worker（评审员 / judge / 对照侧）时，由主 agent 在会话内用 harness subagent
  并行发起，票间唯一差异是 model 参数；不起 `opencode run` 子进程
- **为什么**：`opencode run` 编排曾以 272 行 Python 重造 harness 原生的并行 / 重试 / 结果送达能力
  （外加 flag 探测、`$PWD` 坑、名单锁死），且被当作"标准机制"复制进 writing-review，令多模型评审
  难用——2026-10-08 会话定案删除
- **边界**：① 用户显式要求多模型评审即构成逐票指定 model 的显式授权，覆盖 subagent 工具"未经点名
  不设 model"的劝阻；② harness 无可指定 model 的 subagent 时按该 skill 回退路径如实退回单模型现状，
  不静默改走 CLI；③ 本条管 worker 发起方式，不管主 agent 自身推理；④ 仓库外入口（cron / 裸脚本）
  与数百次以上超大批量场景出现时再议，不预设豁免

## 关键证据

- 2026-10-08 会话：writing-review 删 `run_multi_review.py` 编排、多模型改走 subagent；机制污染的
  根因是 skill-creator 的 `opencode run` 先例被整体复制进会话内场景，边界无人写明
