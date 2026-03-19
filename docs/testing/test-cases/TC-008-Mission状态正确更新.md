# 测试用例：TC-008 Mission 状态正确更新

## 用例信息
- **用例编号**: TC-008
- **用例名称**: Mission 状态正确更新
- **优先级**: P0
- **测试类型**: E2E

## 测试步骤

| 步骤 | 操作 | 预期结果 | 状态 |
|------|------|----------|------|
| 1 | 检查 Mission 状态 | status = dispatched | ✅ |
| 2 | 验证任务状态 | task.status = in_progress | ✅ |
| 3 | 检查子任务 | subtasks 生成 | ✅ |

## 测试数据
- Mission ID: `bc87c330-30e7-46cb-9b89-ac620362a3fb`

## 实际结果
```
Mission:
- status: dispatched
- goal: 测试自动委派功能

Task:
- status: review (Mission 完成后)

Subtasks (3个):
- Gather Facts: completed
- Analyze Options: pending
- Prepare Execution Plan: pending
```

## 结论
✅ **通过** - Mission 状态正确更新，任务流转正确
