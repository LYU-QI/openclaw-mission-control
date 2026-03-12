# Review 卡在 Approval 的处理手册

这份手册解决的是一种很常见的情况：

- `codingAgent` 已经把任务做到 `review`
- `Lead Agent` 也开始审核了
- 但任务始终进不了 `done`
- Lead 会把任务重新打回 `inbox`

这通常不是 Agent 挂了，而是 **Board 开了 `require_approval_for_done`**，但任务没有关联任何已批准的 approval。

## 一句话判断

如果你同时看到下面 3 个现象，基本就是这个问题：

1. 任务已经进入 `review`
2. `Lead Agent` 评论里写了“deliverable looks good”之类的话
3. 任务又被退回 `inbox`，评论里提到 “approval” 或 “done is blocked”

## 这时候系统实际上在做什么

正常链路是：

1. Worker Agent 完成任务
2. 任务进入 `review`
3. Board Lead 审核
4. 如果 Board 要求 approval，系统还需要一条 linked approval
5. approval 被批准后，任务才能从 `review` 进入 `done`

如果第 4 步缺失，就会出现：

- Lead 认可交付结果
- 但不能直接改成 `done`
- 只能先退回 `inbox`

## 先检查什么

先看这 4 项：

1. Board 是否开启了 `require_approval_for_done`
2. 任务当前是不是 `review` 或刚被从 `review` 打回 `inbox`
3. 任务下有没有 lead 的 review 评论
4. 这个任务有没有任何 linked approval

如果 linked approval 是空的，这就是根因。

## 最稳的处理顺序

### 方案 A：走完整闭环

适合你想保留治理流程的时候。

1. 给任务创建一条 approval
2. 把这条 approval 批准
3. 把任务重新送回 `review`
4. 让 `Lead Agent` 再审一次
5. 任务进入 `done`

这才是完整链路：

`worker -> review -> approval -> done`

### 方案 B：测试环境临时放宽

适合你只是想快速验证 Agent 流程。

1. 关闭 Board 的 `require_approval_for_done`
2. 重新让任务进入 `review`
3. 让 `Lead Agent` 继续处理

这样任务就不再被 approval 挡住。

## 实际操作建议

## 傻瓜式点击步骤

下面这版不讲原理，只讲你在页面上怎么点。

### 场景

你看到：

- 任务已经做到 `review`
- `Lead Agent` 写了 review 评论
- 任务又回到了 `inbox`

这时就按下面步骤做。

### 第 1 步：打开任务所在 Board

点击路径：

1. 左侧点 `Boards`
2. 点进对应 Board
3. 在任务列表里找到那条任务

成功后你应该看到：

- 任务卡片
- 当前状态
- 评论区

### 第 2 步：先看任务评论

点击路径：

1. 点开这条任务
2. 滚到评论区

重点看有没有这类意思：

- 交付没问题
- 但是缺 approval
- 要先补 approval 才能进 `done`

如果你已经看到这种评论，就不要先让 `codingAgent` 重做。

### 第 3 步：打开 Approvals 页面

点击路径有两种：

1. 左侧点 `Approvals`
2. 或者在当前 Board 里点 `Approvals`

成功后你应该看到：

- approval 列表
- 每条 approval 的状态

### 第 4 步：给这条任务创建 approval

在 `Approvals` 页面里：

1. 点 `New approval`、`Create approval` 或同类按钮
2. 选择当前这条任务
3. `Action type` 选 review / result review 对应项
4. `Reason` 填一句简单说明

建议直接填：

`This task is ready for final review-to-done approval.`

5. 保存

成功后你应该看到：

- approval 出现在列表里
- 状态是 `pending`

### 第 5 步：批准这条 approval

在 approval 列表里：

1. 找到刚创建的 approval
2. 点 `Approve`

成功后你应该看到：

- approval 状态变成 `approved`

### 第 6 步：回到任务，把它送回 review

点击路径：

1. 回到 Board
2. 打开同一条任务
3. 把状态改成 `review`
4. 评论里写一句说明

建议直接写：

`Approval is approved. Returning task to review for final closure.`

5. 保存

成功后你应该看到：

- 任务状态回到 `review`
- 任务重新指派给 `Lead Agent`，或者很快由系统分给 `Lead Agent`

### 第 7 步：如果没有继续动作，就提醒 Lead Agent

如果过了 10 到 30 秒，这条任务还停在 `review`，就继续：

1. 打开 `Agents`
2. 找到 `Lead Agent`
3. 点 `Nudge`、`Wake` 或类似按钮

建议消息直接填：

`The linked approval is approved. Please review this task now and move it to done if acceptable.`

### 第 8 步：确认任务真的完成

回到任务页，看这 4 个结果：

1. approval 状态是 `approved`
2. 任务出现一条新的 review/comment
3. 任务状态变成 `done`
4. Activity / Live feed 里出现 `Task moved to done`

只要这 4 个结果出来，这条任务就闭环了。

## 一屏版速记

如果你已经熟了，直接记这个：

1. 打开任务评论，确认是缺 approval
2. 去 `Approvals` 创建一条 approval
3. 立刻 `Approve`
4. 回任务把状态改回 `review`
5. 必要时 nudge `Lead Agent`
6. 等任务进 `done`

### 看到任务被打回 `inbox` 时

不要先怀疑 Agent 出错，先看 lead 评论。

如果 lead 评论类似下面这类意思：

- “Returning to inbox because done is blocked until linked approval is approved”
- “Please add/approve approval, then move back to review”

那就不要反复重派任务，也不要重复让 worker 改代码。

正确动作是：

1. 给任务补 approval
2. 批准 approval
3. 再让任务回到 `review`

### 什么时候需要再 nudge Lead Agent

适合这两种情况：

1. approval 已经批准了，但任务还停在 `review`
2. 你刚批量把一批 `review` 任务指派给 `Lead Agent`

这时可以发一次 nudge，内容明确一点，例如：

`A linked approval for this task has been approved. Review it now and move it to done if acceptable.`

## 成功后你应该看到什么

一条完成的闭环任务，通常会出现这些事件：

1. `approval_granted`
2. `Task moved to review`
3. `Agent notified for assignment: Lead Agent`
4. `Task moved to done`

如果这些都出现了，就说明这条链路已经通了。

## 不要做的事

- 不要在缺 approval 的情况下反复让 worker 重新提交同一份结果
- 不要把 “Lead 打回 inbox” 误判成 lead 审核失败
- 不要只盯 Agent 状态，不看 task comment 和 activity
- 不要把 “review 卡住” 和 “Gateway 断连” 混为一谈

## 这套问题的根因总结

`review` 卡住，最常见的不是代码坏了，而是这两个规则叠加：

- Board 有 lead 审核流程
- Board 要求 `approval` 才能 `done`

所以判断顺序应当是：

1. 先看任务是否真的已经交付
2. 再看 lead 是否已经认可
3. 最后看 approval 是否存在且已批准

只要第 3 步补齐，任务就能从 `review` 正常进入 `done`。
