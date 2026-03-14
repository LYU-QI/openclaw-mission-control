# agentdesgin.md 开发任务清单

这份清单把路线图进一步拆成可以直接执行的 backlog。

参考文档：

- [agentdesgin.md](/Users/riqi/project/openclaw-mission-control/agentdesgin.md)
- [agentdesgin.md 到当前系统的实现映射](/Users/riqi/project/openclaw-mission-control/docs/architecture/agentdesign-to-implementation-map.zh-CN.md)
- [agentdesgin.md 实施路线图](/Users/riqi/project/openclaw-mission-control/docs/architecture/agentdesign-implementation-roadmap.zh-CN.md)

## 一、Phase 0：单 Gateway 稳定化

## 后端任务

### 0.1 Gateway 错误分类标准化

- 目标：把 `pairing required`、`token mismatch`、`did not receive a valid HTTP response`、`no check-in` 这些错误统一归类
- 主要位置：
  - [backend/app/services/openclaw/admin_service.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/openclaw/admin_service.py)
  - [backend/app/services/openclaw/lifecycle_orchestrator.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/openclaw/lifecycle_orchestrator.py)
- 产出：
  - 稳定错误码
  - 更明确的 `last_provision_error`

### 0.2 Gateway 健康探针增强

- 目标：区分 HTTP 可达、WS 可握手、RPC 可调用、session 可见、agent 可 check-in
- 主要位置：
  - [backend/app/api/gateways.py](/Users/riqi/project/openclaw-mission-control/backend/app/api/gateways.py)
- 产出：
  - 分层健康状态对象

## 前端任务

### 0.3 Gateway 页面诊断增强

- 目标：别只显示 `provisioning/updating`
- 主要位置：
  - [frontend/src/app/gateways/page.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/app/gateways/page.tsx)
- 产出：
  - 明确显示：
    - 配对未完成
    - token 不匹配
    - 远端无 session
    - wake 后未 check-in

## 测试任务

### 0.4 Gateway lifecycle 回归测试

- 覆盖：
  - pairing required
  - token mismatch
  - HTTP reachable but WS failed
  - wake timeout

## 验收标准

- 用户能从 UI 一眼看出 Gateway 卡在哪一层
- 新接入 Gateway 时，错误提示足够明确，不需要靠日志猜

## 二、Phase 1：Orchestrator 一等对象化

## 后端任务

### 1.1 Mission 状态机明确化

- 目标：明确 `draft / dispatched / running / aggregating / pending_approval / completed / failed`
- 主要位置：
  - [backend/app/models/missions.py](/Users/riqi/project/openclaw-mission-control/backend/app/models/missions.py)
  - [backend/app/services/missions/orchestrator.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/missions/orchestrator.py)

### 1.2 Mission timeline 结构化

- 目标：把 dispatch、subtask callback、aggregation、approval gate 变成统一 timeline
- 主要位置：
  - [backend/app/api/missions.py](/Users/riqi/project/openclaw-mission-control/backend/app/api/missions.py)

### 1.3 Approval 触发规则固定化

- 目标：审批走规则，不让 Orchestrator 自由裁量
- 主要位置：
  - [backend/app/api/approvals.py](/Users/riqi/project/openclaw-mission-control/backend/app/api/approvals.py)
  - [backend/app/services/missions/orchestrator.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/missions/orchestrator.py)

## 前端任务

### 1.4 Mission 详情页强化

- 目标：Mission 页面直接体现 Orchestrator 视角
- 主要位置：
  - [frontend/src/app/missions/[id]/page.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/app/missions/[id]/page.tsx)
  - [frontend/src/components/missions/MissionDetailPanel.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/components/missions/MissionDetailPanel.tsx)
- 产出：
  - 当前阶段
  - subtasks 摘要
  - 风险等级
  - next action
  - approval 状态

## 测试任务

### 1.5 Mission 编排 e2e

- 覆盖：
  - dispatch -> subtasks -> callback -> aggregation
  - approval gate -> writeback / complete

## 验收标准

- 一条复杂 Mission 的全生命周期在 UI 和 API 中都清晰可见

## 三、Phase 2：Sync / Comms 正式能力域

## 后端任务

### 2.1 Feishu Sync 幂等和冲突可视化

- 目标：明确同一外部记录重复同步、回写冲突、字段丢失时怎么处理
- 主要位置：
  - [backend/app/services/feishu/sync_service.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/feishu/sync_service.py)
  - [backend/app/services/feishu/conflict_resolver.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/feishu/conflict_resolver.py)

### 2.2 Notification 事件模板治理

- 目标：让通知事件、模板、失败原因都有统一对象
- 主要位置：
  - [backend/app/services/notification/notification_service.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/notification/notification_service.py)
  - [backend/app/services/notification/feishu_bot.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/notification/feishu_bot.py)

## 前端任务

### 2.3 Feishu Sync 页面增强

- 主要位置：
  - [frontend/src/app/feishu-sync/page.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/app/feishu-sync/page.tsx)
- 产出：
  - 最近同步结果
  - 失败原因
  - 字段映射状态
  - 冲突提示

### 2.4 Notifications 页面增强

- 主要位置：
  - [frontend/src/app/notifications/page.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/app/notifications/page.tsx)
- 产出：
  - 事件类型
  - 模板预览
  - 最近失败原因
  - 测试发送结果

## 测试任务

### 2.5 Feishu 真联调回归套件

- 覆盖：
  - 拉任务
  - 创建 Mission
  - 结果回写
  - 飞书通知

## 验收标准

- 用户不用看后端日志，也能知道同步和通知哪里失败

## 四、Phase 3：Watcher 产品化

## 后端任务

### 3.1 统一 Attention 规则

- 目标：把 mission / task / approval 的异常统一归到一个 attention 输出
- 主要位置：
  - [backend/app/api/metrics.py](/Users/riqi/project/openclaw-mission-control/backend/app/api/metrics.py)
  - [backend/app/services/missions/subtask_timeout.py](/Users/riqi/project/openclaw-mission-control/backend/app/services/missions/subtask_timeout.py)

### 3.2 日报/周报生成能力

- 目标：先做服务，不急着做人格化 Watcher Agent

## 前端任务

### 3.3 Dashboard Attention 视图

- 主要位置：
  - [frontend/src/app/dashboard/page.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/app/dashboard/page.tsx)
- 产出：
  - failed subtasks
  - timed out subtasks
  - stale missions
  - pending approvals

### 3.4 Missions 列表筛选增强

- 主要位置：
  - [frontend/src/app/missions/page.tsx](/Users/riqi/project/openclaw-mission-control/frontend/src/app/missions/page.tsx)
- 产出：
  - `needs_attention`
  - `timed_out`
  - `failed_subtasks`

## 测试任务

### 3.5 规则与 UI 联动测试

- 覆盖：
  - timeout 后 attention 出现
  - redispatch 后 attention 消失

## 验收标准

- 一眼能从 Dashboard 和 Missions 页面看到系统当前最需要处理的事

## 五、Phase 4：Knowledge 资产化

## 后端任务

### 4.1 知识条目模型

- 目标：从“读上下文”走向“存知识”
- 可新增：
  - FAQ
  - 决策卡片
  - 背景摘要
  - 上下文包

### 4.2 文档/群消息沉淀规则

- 目标：明确哪些信息自动沉淀，哪些要人工确认

## 前端任务

### 4.3 知识概览页

- 产出：
  - FAQ 列表
  - 决策摘要
  - 最近更新

## 测试任务

### 4.4 知识沉淀链测试

- 覆盖：
  - 飞书文档 -> 知识条目
  - 群消息摘要 -> action items / FAQ

## 验收标准

- 同一项目的长期背景不再完全依赖临时上下文拼装

## 六、建议先开的 10 个任务

1. Gateway lifecycle 错误分类标准化
2. Gateway 页面诊断增强
3. Mission 状态机文档化与字段收敛
4. Mission timeline 结构化
5. Approval 触发规则固定化
6. Feishu Sync 冲突与失败原因可视化
7. Notification 模板与失败原因可视化
8. Dashboard Attention 视图完善
9. Missions 列表异常筛选增强
10. Knowledge 条目模型设计

## 七、优先级建议

如果只按价值排序，我建议：

### P0

- 1
- 2
- 3
- 4

### P1

- 5
- 6
- 7
- 8

### P2

- 9
- 10

## 八、一句话版本

先把“单 Gateway 稳定 + Mission 编排清晰 + Feishu 通道可观测”这三件事做扎实，再谈 5 个正式 agent 的人格化，成本最低，成功率最高。
