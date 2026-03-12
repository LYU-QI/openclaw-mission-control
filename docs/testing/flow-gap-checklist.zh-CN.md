# 流程图测试覆盖清单

本文按 [liuchengtu.md](/Users/riqi/project/openclaw-mission-control/liuchengtu.md) 跟踪当前测试覆盖情况。

## 已真实验证

### ① 项目管理系统 -> Mission Control

- Feishu Bitable 任务同步已真实通过
- 标题字段已从真实飞书表进入 Mission Control

### ③ 读取上下文

- 飞书文档读取已真实通过
- 飞书群消息读取已真实通过
- 日志/代码仓库读取已通过仓库内测试

### ⑥ Mission Control 更新执行状态 / 日志

- Mission 生命周期状态更新已通过
- 活动日志与通知日志已通过真实与 e2e 验证

### ⑦ 回写正式任务结果

- Mission Control -> Feishu 结果回写已真实通过

### ⑧ 通知与协作 -> 飞书群

- 真实飞书通知链已通过

## 已通过代码/集成测试，但还不算真实 swarm 联调

### ④ OpenClaw 拆解任务 -> Subagent们

当前状态：

- Mission dispatch 时会创建 `MissionSubtask`
- 分解器支持 LLM 输出和 fallback 拆解
- 已通过测试：
  - [backend/tests/test_openclaw_decomposer.py](/Users/riqi/project/openclaw-mission-control/backend/tests/test_openclaw_decomposer.py)
  - [backend/tests/test_e2e_mission_feishu_notification.py](/Users/riqi/project/openclaw-mission-control/backend/tests/test_e2e_mission_feishu_notification.py)

当前限制：

- 现在的 subtask 仍是 Mission Control 内部的任务分解对象
- 还没有把每个 subtask 真正派生成多个 OpenClaw 独立 worker / session

### ⑤ Subagent 结果回流 -> OpenClaw 聚合

当前状态：

- 聚合器会根据 subtask 结果生成：
  - `summary`
  - `risk`
  - `next_action`
  - `evidence`
- 已通过测试：
  - [backend/tests/test_openclaw_aggregator.py](/Users/riqi/project/openclaw-mission-control/backend/tests/test_openclaw_aggregator.py)
  - [backend/tests/test_e2e_mission_feishu_notification.py](/Users/riqi/project/openclaw-mission-control/backend/tests/test_e2e_mission_feishu_notification.py)

当前限制：

- 现在聚合输入来自 `MissionSubtask` 结果更新
- 还不是多个真实 OpenClaw subagent 的独立执行回流

## 当前剩余主要缺口

从“真实端到端 swarm 协作”角度看，主要还差这两件事：

1. 把 mission subtasks 真正下沉到多个独立 subagent / worker session
2. 把多个真实 subagent 的执行结果自动聚合回 Mission Control

## 建议下一步测试

1. 先做一条“复杂任务 -> 自动生成多个 subtasks -> 查看 subtasks API 与聚合结果”的半实战验证
2. 再决定是否需要开发“真实多 session subagent 派发”能力
