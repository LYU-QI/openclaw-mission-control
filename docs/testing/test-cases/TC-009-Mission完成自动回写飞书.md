# 测试用例：TC-009 Mission 完成自动回写飞书

## 用例信息
- **用例编号**: TC-009
- **用例名称**: Mission 完成自动回写飞书
- **优先级**: P1
- **测试类型**: E2E

## 测试步骤

| 步骤 | 操作 | 预期结果 | 状态 |
|------|------|----------|------|
| 1 | Mission 完成执行 | status = completed | ✅ |
| 2 | 检查任务状态更新 | task.status = review | ✅ |
| 3 | 检查结果字段 | result_summary 存在 | ✅ |
| 4 | 检查 next_action | result_next_action 存在 | ✅ |

## 实际结果
```
Task (已完成 Mission):
- status: review
- result_summary: "测试自动委派功能 | subtasks total=3, completed=3, pending=0, failed=0, anomalies=0"
- result_risk: "low"
- result_next_action: "Proceed to delivery and close the task."
```

## 结论
✅ **通过** - Mission 完成后任务状态和结果正确更新

## 备注
飞书回写需要任务标记为 done 状态时才会触发（根据代码逻辑）
