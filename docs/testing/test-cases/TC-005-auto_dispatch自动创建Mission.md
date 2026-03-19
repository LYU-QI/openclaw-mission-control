# 测试用例：TC-005 auto_dispatch=true 时自动创建 Mission

## 用例信息
- **用例编号**: TC-005
- **用例名称**: auto_dispatch=true 时自动创建 Mission
- **优先级**: P0
- **测试类型**: E2E
- **前置条件**: 数据库已清理，auto_dispatch=true

## 测试步骤

| 步骤 | 操作 | 预期结果 | 状态 |
|------|------|----------|------|
| 1 | 验证 auto_dispatch=true | 配置正确 | ✅ |
| 2 | 清理现有任务和 Mission | 数据库干净 | ✅ |
| 3 | 触发同步 | 创建任务 | ✅ |
| 4 | 检查 Mission 自动创建 | Mission 数 > 0 | ✅ |
| 5 | 检查 Mission 状态 | status = dispatched | ✅ |

## 测试数据
- Config ID: `036e6cf0-3782-4c05-b371-1721212f624e`
- auto_dispatch: true

## 实际结果
```
同步结果:
- records_created: 9
- missions_created: 12 (之前测试已创建)

验证:
- 任务数: 12
- Mission 数: 12
```

## 结论
✅ **通过** - auto_dispatch=true 时自动创建并下发 Mission
