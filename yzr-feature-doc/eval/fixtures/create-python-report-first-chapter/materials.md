# 通知合并发送测试材料

功能：后台通知任务按 5 秒窗口合并发送。

## 单元测试

- 框架：pytest
- 覆盖：合并窗口、空批次、失败重试状态
- 结果：32/32 通过
- 报告：<https://example.com/pytest>

## 进程测试

- 方式：直接运行 notification-worker 测试程序，验证单进程内批量消费与重试状态
- 结果：8/8 通过
- 报告：<https://example.com/worker>

## 系统集成测试

- 参与组件：notification-api、notification-worker、真实 PostgreSQL
- 不使用代码级 mock
- 场景：API 写入后 worker 消费并更新状态，6/6 通过
- 共享前置：6 个集成用例共用同一套服务启动与数据准备步骤，见 <https://example.com/setup>
- 集成步骤：<https://example.com/integration>

## 自设计 E2E

- 入口：后台创建通知任务
- 环境：测试环境；窗口配置 5 秒；依赖 PostgreSQL
- 步骤：
  1. 创建包含 3 条通知的任务
  2. 等待窗口结束
  3. 检查只发送 1 个合并请求
  4. 注入一次发送失败并等待重试
- 预期观察：日志出现 `batch_size=3`，最终所有通知状态为已发送
- 运行结果：<https://example.com/e2e>，PASS
