# 测试用例：TC-006 auto_dispatch=false 时不创建 Mission

## 用例信息
- **用例编号**: TC-006
- **用例名称**: auto_dispatch=false 时不创建 Mission
- **优先级**: P1
- **测试类型**: E2E

## 测试步骤

| 步骤 | 操作 | 预期结果 | 状态 |
|------|------|----------|------|
| 1 | 设置 auto_dispatch=false | 配置更新 | - |
| 2 | 清理现有任务和 Mission | 数据库干净 | - |
| 3 | 触发同步 | 创建任务 | - |
| 4 | 检查 Mission 未自动创建 | Mission 数 = 0 | - |

## 测试数据
- Config ID: `036e6cf0-3782-4c05-b371-1721212f624e`

## 结论
⏳ **待执行** - 需要设置 auto_dispatch=false 后测试
