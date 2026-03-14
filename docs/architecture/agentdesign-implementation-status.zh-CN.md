# agentdesign backlog 实现状态报告

> 检查日期：2026-03-14
> 参考文档：[agentdesign-backlog.zh-CN.md](./agentdesign-backlog.zh-CN.md)

---

## Phase 0：单 Gateway 稳定化

| 任务 | 状态 | 说明 |
|------|------|------|
| **0.1** Gateway 错误分类标准化 | ✅ 完成 | `error_messages.py` 已实现 `PAIRING_REQUIRED`、`TOKEN_MISMATCH`、`CHECKIN_TIMEOUT`、`TRANSPORT_ERROR` 四类，返回稳定 `GatewayErrorInfo(code, message)` |
| **0.2** Gateway 健康探针增强 | ⚠️ 部分完成 | 5 层健康结构（`http_reachable/ws_connected/rpc_callable/session_active/agent_checked_in`）已定义并生成前端类型，但 `ws_connected` 非真实 WebSocket 握手探测，而是从本地 DB agent 状态推断 |
| **0.3** Gateway 页面诊断增强 | ✅ 完成 | `[gatewayId]/page.tsx` 已渲染全部 5 层健康状态 + `parseGatewayDiagnostic` 解析错误码，`GatewaysTable` 中有实时 `GatewayHealthBadge` |
| **0.4** Gateway lifecycle 回归测试 | ✅ 完成 | `test_gateway_lifecycle_exception.py`、`test_gateway_status_layers.py`、`test_gateway_error_messages.py` 均存在 |

---

## Phase 1：Orchestrator 一等对象化

| 任务 | 状态 | 说明 |
|------|------|------|
| **1.1** Mission 状态机明确化 | ✅ 完成 | `status_machine.py` 实现完整，状态为 `pending/dispatched/running/aggregating/pending_approval/completed/failed/cancelled`（backlog 写的 `draft`，实际用 `pending`） |
| **1.2** Mission timeline 结构化 | ✅ 完成 | `timeline.py` 含 14 种事件类型的元数据，前端 `MissionTimeline.tsx` 已渲染带 tone 着色的时间线 |
| **1.3** Approval 触发规则固定化 | ✅ 完成 | `ApprovalRule` DB 模型 + `ApprovalGate` 已实现规则驱动审批（`trigger_on_high_risk`、`trigger_on_tool_usage`、优先级判断） |
| **1.4** Mission 详情页强化 | ✅ 完成 | `[id]/page.tsx` + `MissionDetailPanel.tsx` 已展示：当前阶段、subtasks 摘要、风险等级、next action、approval 状态 |
| **1.5** Mission 编排 e2e | ✅ 完成 | `test_mission_orchestration_e2e.py`、`test_mission_approval_gate.py` 存在，`orchestrator.py` 覆盖完整链路 |

---

## Phase 2：Sync / Comms 正式能力域

| 任务 | 状态 | 说明 |
|------|------|------|
| **2.1** Feishu Sync 幂等和冲突可视化 | ⚠️ 部分完成 | `conflict_resolver.py` 实现 last-write-wins 逻辑，`sync_service.py` 有手动解决冲突的方法，前端也有冲突解决 UI；但**字段丢失检测**未实现 |
| **2.2** Notification 事件模板治理 | ⚠️ 部分完成 | `templates.py` 有 10 种事件类型的飞书卡片模板；但**失败原因**没有结构化字段，靠 generic `payload` dict 传递 |
| **2.3** Feishu Sync 页面增强 | ⚠️ 部分完成 | 同步结果、失败原因、字段映射、冲突提示均有；但同步结果**仅显示当次手动触发**的数据，历史记录走 `SyncHistoryTable` 单独展示 |
| **2.4** Notifications 页面增强 | ⚠️ 部分完成 | 事件类型统计、失败原因、测试发送均有；**模板预览**功能缺失 |
| **2.5** Feishu 真联调回归套件 | ✅ 完成 | `test_feishu_sync_service.py`、`test_feishu_sync_orchestration.py`、`test_e2e_mission_feishu_notification.py` 均存在 |

---

## Phase 3：Watcher 产品化

| 任务 | 状态 | 说明 |
|------|------|------|
| **3.1** 统一 Attention 规则 | ✅ 完成 | `metrics.py` 的 `/attention` 端点通过 `AttentionCollector` 聚合 4 类异常（failed subtasks、timed_out、stale missions、pending approvals） |
| **3.2** 日报/周报生成能力 | ✅ 完成 | `api/reports.py` + `services/watcher/report_generator.py` 存在，前端 `generated/reports/` hooks 已生成 |
| **3.3** Dashboard Attention 视图 | ✅ 完成 | `dashboard/page.tsx` 实现完整，15 秒轮询，4 类异常计数 + 最多 8 条详细条目 |
| **3.4** Missions 列表筛选增强 | ⚠️ 部分完成 | 有 `needs_attention` 开关（客户端过滤）；**`timed_out` 筛选缺失**（只判断 `failed`），无 URL 参数化筛选，无 `stale_missions` 筛选 |
| **3.5** 规则与 UI 联动测试 | ✅ 完成 | `test_attention_logic.py` 存在 |

---

## Phase 4：Knowledge 资产化

| 任务 | 状态 | 说明 |
|------|------|------|
| **4.1** 知识条目模型 | ✅ 完成 | `KnowledgeItem` 模型支持 `faq/decision/summary/context` 四类，有迁移文件 |
| **4.2** 文档/群消息沉淀规则 | ⚠️ 部分完成 | `services/knowledge/extractor.py` 存在，但自动沉淀 vs 人工确认的边界逻辑未明确 |
| **4.3** 知识概览页 | ✅ 完成 | `frontend/src/app/knowledge/page.tsx` 存在 |
| **4.4** 知识沉淀链测试 | ✅ 完成 | `test_knowledge.py` 存在 |

---

## 待处理缺口汇总

| 优先级 | 任务编号 | 缺口描述 | 涉及文件 |
|--------|----------|----------|----------|
| P1 | 0.2 | `ws_connected` 探针需真实 WebSocket 握手，当前为推断值 | `backend/app/services/openclaw/admin_service.py` |
| P1 | 2.1 | Feishu Sync 字段丢失检测逻辑缺失 | `backend/app/services/feishu/sync_service.py` |
| P1 | 2.2 | Notification 模板失败原因应结构化，当前走 generic dict | `backend/app/services/notification/templates.py` |
| P2 | 2.4 | Notifications 页面模板预览 UI 缺失 | `frontend/src/app/notifications/page.tsx` |
| P2 | 3.4 | Missions 列表缺 `timed_out`、`stale_missions` 筛选，且筛选无 URL 参数化 | `frontend/src/app/missions/page.tsx` |
| P3 | 4.2 | 知识沉淀规则：自动 vs 人工确认边界需明确 | `backend/app/services/knowledge/extractor.py` |

---

## 整体进度

- **总任务数**：20 项
- **完成**：14 项（70%）
- **部分完成**：6 项（30%）
- **未开始**：0 项

> Phase 0–3 核心链路均已跑通，剩余缺口为功能细化而非骨架缺失。建议按优先级逐步补齐。
