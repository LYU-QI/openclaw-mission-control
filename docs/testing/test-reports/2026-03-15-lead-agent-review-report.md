# 测试报告：Lead Agent 评审拦截功能验证

## 1. 测试目标
验证当任务状态为 `review` 时，分配到的 Lead Agent 是否必须先发布评审评论（Comment），才能将任务状态变更为 `done`。
同时验证 Lead Agent 收到的 Review 提醒是否按要求更新。

## 2. 测试方法与说明
考虑到整个 E2E 网络（包括真实的 Feishu Webhook 和 Local Agent 的授权及调度）在开发环境部分节点不够稳定，本次采用**在后端直接使用 Pytest 对 API 层进行内连拦截测试**的方法，以确保状态机与权限网关功能的明确生效。

使用了单独编写的测试用例文件 `backend/tests/test_lead_review_block.py` 进行拦截行为验证。

## 3. 测试步骤

| 步骤 | 操作 | 预期结果 | 实际结果 | 状态 |
|------|------|----------|----------|------|
| 1 | `test_lead_apply_status` 修改 | 能够抓取 ActorType == Agent 且 is_board_lead == True 的操作对象 | 拦截逻辑已注入并生效 | PASS |
| 2 | Lead Agent 未评论尝试标记 Done | 调用 Gateway 或 Backend 的 `PATCH /tasks/{id}` 转移状态去 done | 触发 `HTTP 409 Conflict` 异常，提示需先发布 review comment | PASS |
| 3 | Lead Agent 补充评论 | 写入类型为 `task.comment` 且符合时间判定参数的 `ActivityEvent` | 评论被正确存入，可查出对应的 valid record | PASS |
| 4 | Lead Agent 再次尝试标记 Done | 使用该 Agent 的身份并携带目标状态 done 再次请求 Status 更新 API | `HTTP 200 OK` 并且返回的 Task object status 变更为 done | PASS |

## 4. 其它验证
**通知内容优化**：在先前的实施阶段已经向 `tasks.py` 的通知下发函数中加入了对 `task.result_summary`, `task.result_risk`, `task.result_next_action` 的支持（解决了无 custom_fields 的 AttributeError），并将原本的话术调整为强制评论后方可操作的大写强化文案。

## 5. 结论结果
**测试通过，达到 PRD 需求。** Lead Agent 现在执行任务验收（从 review 进入 done 阶段）被严格实施了带有上下文验证时间的“先发表意见后准予关闭”的门控策略。
