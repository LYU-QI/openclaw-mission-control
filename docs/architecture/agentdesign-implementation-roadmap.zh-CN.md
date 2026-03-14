# agentdesign.md 实施路线图

这份路线图基于两份前置文档：

- [agentdesgin.md](/Users/riqi/project/openclaw-mission-control/agentdesgin.md)
- [agentdesgin.md 到当前系统的实现映射](/Users/riqi/project/openclaw-mission-control/docs/architecture/agentdesign-to-implementation-map.zh-CN.md)

目标不是一次性造出 5 个“人格化正式 agent”，而是沿着当前仓库已经存在的能力，分阶段把它演进成稳定的单 Gateway 多 Agent 体系。

## 一、总原则

### 1. 先收敛单 Gateway

后续所有设计都以“单 Gateway 稳定运行”为前提。

不要在这条路线里同时引入：

- 多 Gateway
- 多公网入口
- 多套认证策略
- 多套 provider 默认模型

### 2. 先做岗位能力，再做岗位人格

当前系统里很多能力已经存在，只是还没有被包装成显式 agent：

- Sync：已经有 Feishu Sync / writeback
- Comms：已经有 notification / bot
- Watcher：已经有 timeout scan / metrics
- Knowledge：已经有 context loaders

所以应先把能力跑稳，再决定哪些必须常驻成 agent。

### 3. Mission 是编排单元，Agent 是执行单元

这条边界必须固定：

- PM Task：业务任务
- Mission：Mission Control 内部编排单元
- MissionSubtask：一次性临时工任务
- Gateway Agent / Board Agent：OpenClaw 运行单元

## 二、推荐的 4 个阶段

## Phase 0：单 Gateway 稳定化

### 目标

确保现在这套单 Gateway 环境能持续稳定工作，不再因为认证、配对、端口、模型限流把上层架构拖垮。

### 重点工作

- 固定单一主 Gateway
- 固定单一默认模型/provider
- 固定 Gateway token / pairing 策略
- 让 Gateway Agent、Board Agent、Lead Agent 生命周期稳定

### 后端改动重点

- 强化 Gateway 健康探测和错误原因回传
- 把 `pairing required` / `token mismatch` / `no check-in` 这类错误标准化
- 为 Gateway main agent 增加更明确的 lifecycle 诊断

### 前端改动重点

- 在 Gateway 页明确显示：
  - 网络错误
  - 配对错误
  - token 错误
  - 远端未 check-in
- 对 `provisioning/updating` 给出更明确的提示文案

### 验收标准

- 单 Gateway 下创建 Gateway Agent 稳定进入 `online`
- 创建一个 Board Agent 能稳定进入 `online`
- 指派最小任务后能稳定回评论

## Phase 1：把 Orchestrator 做成一等对象

### 目标

把当前已经存在的 `MissionOrchestrator + decomposer + aggregator` 明确提升为系统中的正式“总控能力”。

### 重点工作

- 明确 Mission 生命周期
- 明确 MissionSubtask 生命周期
- 明确 Orchestrator 的输入、输出、审批边界
- 避免让 Board Agent 和 Orchestrator 语义混杂

### 后端改动重点

- 继续收敛 [backend/app/services/missions/orchestrator.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/missions/orchestrator.py)
- 给 Mission 增加更稳定的状态机字段或事件语义
- 明确：
  - 什么时候自动拆解
  - 什么时候发起 approval
  - 什么时候自动聚合
  - 什么时候 writeback

### 前端改动重点

- 完成 Mission 详情页的 Orchestrator 视图
- 能直接看到：
  - Mission 当前阶段
  - subtasks 状态
  - 风险等级
  - next action
  - approval gate

### 验收标准

- 一条复杂 Mission 能自动拆出 subtasks
- subtasks 完成后 Mission 自动聚合
- Mission 需要审批时能稳定进入 approval 流

## Phase 2：把 Sync / Comms 提升为正式岗位能力

### 目标

把飞书同步和通知从“能工作”推进到“职责清楚、可观测、可审计”。

### Sync Agent 的实现重点

先不急着造常驻人格，先把这些做完整：

- 字段映射版本化
- 外部任务 ID 与内部 Mission ID 的稳定映射
- 幂等同步
- 幂等回写
- 冲突处理

对应代码主要在：

- [backend/app/models/feishu_sync.py](/Users/riqi/project/openclaw-mission-control/backend/app/models/feishu_sync.py)
- [backend/app/services/feishu/sync_service.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/feishu/sync_service.py)
- [backend/app/services/feishu/writeback_service.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/feishu/writeback_service.py)

### Comms Agent 的实现重点

先把通知链做成一个正式能力域：

- 事件类型清单
- 通知模板版本化
- 通知重试
- 通知审计日志
- 人工确认消息规范

对应代码主要在：

- [backend/app/services/notification/notification_service.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/notification/notification_service.py)
- [backend/app/services/notification/feishu_bot.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/notification/feishu_bot.py)

### 前端改动重点

- `Feishu Sync` 页面加同步状态、映射状态、冲突提示
- `Notifications` 页面加模板、事件类型、最近失败原因

### 验收标准

- 飞书台账 -> Mission Control 同步稳定
- Mission 完成/失败/审批事件稳定推飞书
- Mission 结果稳定回写飞书

## Phase 3：Watcher 能力域产品化

### 目标

在不急着引入新常驻 agent 的前提下，把巡检和升级能力做成完整的“Watcher 能力域”。

### 重点工作

- timeout scan
- failed mission attention
- pending approvals attention
- stale tasks attention
- daily / weekly summary

### 后端改动重点

- 强化现有 timeout / retry / redispatch 规则
- 为 Watcher 增加统一的规则入口
- 把巡检输出结构化成可展示对象，而不是散落在日志/metrics 中

### 前端改动重点

- Dashboard 增加 `Needs attention`
- Missions 列表页增加按异常类型过滤
- 支持按：
  - failed subtasks
  - timed out subtasks
  - pending approvals
  - stale missions
 过滤

### 验收标准

- 用户能在 UI 里快速发现需要处理的 mission
- 超时 / 失败 / 待审批都能形成明确的 attention 列表

## Phase 4：Knowledge 从“上下文读取”升级到“知识资产”

### 目标

把当前的文档/群消息 loader，推进成真正的项目知识资产层。

### 重点工作

- 定义知识条目格式
- 定义 FAQ / 决策卡片 / 背景摘要格式
- 定义上下文包格式
- 决定哪些由自动抽取生成，哪些由人工确认后入库

### 后端改动重点

- 在现有 context loader 之上增加知识沉淀层
- 让“读取上下文”和“维护知识资产”不再混在一起

### 前端改动重点

- 增加知识卡片或知识概览页
- 显示最近沉淀的 FAQ / 决策 / 摘要

### 验收标准

- 同一个项目的背景知识不再靠临时读取拼出来
- Mission / Agent 能稳定复用结构化知识资产

## 三、先做什么，后做什么

如果你接下来只做最少的工作，我建议顺序固定成：

1. Phase 0：先把单 Gateway 稳住
2. Phase 1：把 Orchestrator 做成一等对象
3. Phase 2：把 Sync / Comms 做成正式能力域
4. Phase 3：Watcher 产品化
5. Phase 4：Knowledge 资产化

## 四、哪些事情现在不要做

### 1. 不要先做多 Gateway

这会把主要精力从“业务编排”拖回“运行稳定性”。

### 2. 不要一开始就做 5 个常驻人格 agent

当前仓库更多能力还在服务层和规则层，过早人格化只会放大维护成本。

### 3. 不要让 Orchestrator 自由裁量审批

审批应该尽量规则化，避免变成不可审计的黑盒判断。

## 五、下一步可以直接做的开发项

如果要立刻往前推，我建议先开这 5 类任务：

1. Gateway lifecycle 错误分类与 UI 展示优化
2. Mission 状态机与 timeline 明确化
3. Feishu Sync 映射/冲突可视化
4. Notification 事件模板和失败原因可视化
5. Dashboard / Missions attention 视图完善

## 六、一句话版本

这份设计最稳的实现方式不是“马上造 5 个会说话的 agent”，而是：

先用当前仓库已经有的 `Mission / Subtask / Approval / Feishu Sync / Notification / Context Loader` 把岗位能力分层清楚，再逐步把最值得常驻的那几个岗位人格化。
