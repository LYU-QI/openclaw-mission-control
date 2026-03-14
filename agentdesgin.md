## 一、我给你的推荐架构

### 总体结构

**项目管理系统（飞书多维表格）**
→ **Mission Control**
→ **OpenClaw Gateway**
→ **5 个正式 agent**
→ **按需拉起 subagent**
→ **结果回写 PM 系统 + 通知飞书群**

这个设计的核心逻辑是：

* **PM 系统**做业务主账本
* **Mission Control**做 AI 编排与治理台
* **OpenClaw**做统一运行时
* **正式 agent**做长期岗位
* **subagent**做一次性短活

之所以这么分，是因为 OpenClaw 官方把 subagent 明确区分成 one-shot 的 `/subagents spawn`，而要做持久线程式会话，需要用 `sessions_spawn` 的 session 模式；这说明它天然更适合“正式工 + 临时工”分层，而不是把所有长期岗位都塞进一次性 subagent。([OpenClaw][2])

---

## 二、组织架构图

```text
Mission Control
   │
   └── OpenClaw Gateway
         │
         ├── 1. Orchestrator（总控 agent）
         ├── 2. Sync Agent（台账同步 agent）
         ├── 3. Comms Agent（沟通协调 agent）
         ├── 4. Watcher Agent（巡检运营 agent）
         ├── 5. Knowledge Agent（知识上下文 agent）
         │
         └── Subagents（临时工池）
              ├── Log Investigator
              ├── Document Summarizer
              ├── Risk Analyzer
              ├── Action-Item Extractor
              └── Report Drafter
```

这套设计建立在两个前提上：
第一，单 Gateway 就能跑多个 agent；第二，每个 agent 可以独立隔离自己的 workspace、配置和 sessions，所以这些正式 agent 不会互相污染。([OpenClaw][1])

---

## 三、5 个正式 agent 的职责设计

### 1）Orchestrator：总控 agent

这是你的“项目 AI 经理”。

它负责：

* 接 Mission Control 下发的任务
* 判断任务该给谁
* 决定什么时候拉起 subagent
* 汇总所有执行结果
* 决定何时回写 PM 系统
* 决定何时通知飞书群
* 遇到高风险动作时把任务送去审批

它必须是正式工，不适合做 subagent，因为它承担的是**默认收口和持续编排职责**。OpenClaw 的多 agent 模型本来就支持在一个 Gateway 下运行多个隔离 agent，这个岗位最适合作为那个长期存在的“总控脑”。([OpenClaw][3])

我建议给它独立 workspace，里面放：

* 项目总规则
* agent 协作规范
* 回写规则
* 审批规则
* 输出模板

---

### 2）Sync Agent：台账同步 agent

这是“项目台账管理员”。

它负责：

* 从飞书多维表格读取新任务、变更任务、超期任务
* 把任务元数据同步到 Mission Control / OpenClaw 可用格式
* 把 AI 结果回写到飞书多维表格
* 维护外部任务 ID 与内部 mission ID 的映射
* 防止重复创建、重复回写、状态漂移

它之所以要单独设岗位，是因为 PM 系统是业务主账本，而 Mission Control 的官方定位是控制与治理平台，不是替代 PM 主账。这个岗位长期存在，才能把“业务任务”和“AI 任务”之间的映射做稳。([GitHub][4])

它的 workspace 里建议放：

* 字段映射规则
* 状态机规则
* 回写模板
* 重试和幂等策略

---

### 3）Comms Agent：沟通协调 agent

这是“飞书群秘书”。

它负责：

* 监听飞书群里的项目更新、临时问题、补充说明
* 把群里的非结构化消息整理成结构化输入
* 把 OpenClaw 的执行结果发回群里
* 发催办、提醒、异常播报
* 向人类请求补充信息或确认

这个岗位必须常驻，因为渠道接入是长期能力，不是一次性动作。OpenClaw 配置文档也强调 Gateway 会连接消息渠道并控制谁可以给 bot 发消息，这类能力天然是长期值守型。([OpenClaw][1])

它的 workspace 里建议放：

* 群消息格式规范
* 提醒模板
* 异常升级模板
* 人工确认话术

---

### 4）Watcher Agent：巡检运营 agent

这是“项目值班员”。

它负责：

* 每天扫描超期任务
* 每周汇总风险项
* 定期生成日报、周报
* 监控 Mission Control 里 pending / failed 的执行项
* 对长时间无更新任务发提醒
* 对高优先级阻塞自动升级

这个岗位很适合正式工，因为它明显属于周期性、定时性、持续性工作，而不是一次性委派。OpenClaw 官方对自动化和 Gateway 运行时的设计，本来就适合承接这类长期巡检任务。([OpenClaw][1])

它的 workspace 建议放：

* 巡检规则
* 风险阈值
* 超期判定逻辑
* 日报周报模板

---

### 5）Knowledge Agent：知识上下文 agent

这是“项目知识管理员”。

它负责：

* 整理会议纪要
* 维护项目 FAQ
* 抽取历史决策
* 维护项目背景资料索引
* 给总控 agent 提供稳定上下文

这个岗位的价值在于：每个正式 agent 都有独立 workspace，而 workspace 正是 agent 的“家”和长期工作目录。既然 OpenClaw 明确把 workspace 作为 agent 的 home，并且文件工具和 workspace context 都围绕它运转，那么“长期项目知识”最适合由一个常驻 agent 维护，而不是交给一次性 subagent 临时记忆。([OpenClaw][5])

---

## 四、哪些任务交给 subagent

subagent 不要拿来做长期岗位，拿来做短活最划算。

适合交给 subagent 的任务有：

* 临时查某个任务相关日志
* 并行整理三份文档
* 从一周群聊里提取 action items
* 生成一次性周报初稿
* 对某个延期任务做风险分析
* 汇总某次事故相关上下文

原因很明确：官方文档写的是 `/subagents spawn` 属于 one-shot 模式；要持久线程式子会话，需要 `sessions_spawn` 的 session 模式，而且近期还有非 Discord 渠道上持久 thread 受限的问题反馈。这说明 subagent 现在更适合“临时工”，不适合承接你这条项目链路里的核心常驻岗位。([OpenClaw][2])

---

## 五、每个正式 agent 的边界

为了避免职责打架，我建议你这样定边界。

### Orchestrator 不直接长期监听群

群由 Comms Agent 负责。
Orchestrator 只接收结构化输入和异常升级。

### Sync Agent 不做复杂分析

它只管读写和映射，不做“这件事该怎么办”的判断。
判断由 Orchestrator 或临时分析 subagent 负责。

### Watcher Agent 不直接改正式任务状态

它只发现问题、发提醒、触发升级。
真正改正式任务状态，由 Sync Agent 回写。

### Knowledge Agent 不负责对外通知

它只整理知识，不在群里主持沟通。
对外输出仍然通过 Comms Agent 或 Orchestrator。

这样分开后，每个岗位都像一个“长期固定工位”，而不是谁都能碰所有东西。

---

## 六、推荐的数据流

### 主链路

1. 飞书多维表格出现新任务
2. Sync Agent 把任务同步成可执行 mission
3. Mission Control 记录并编排
4. Orchestrator 接任务
5. Orchestrator 决定调用哪个正式 agent，是否拉 subagent
6. OpenClaw 执行
7. 结果回到 Orchestrator
8. 高风险动作走 Mission Control 审批
9. Sync Agent 回写 PM 系统
10. Comms Agent 通知飞书群

Mission Control 官方 README 里强调了 work orchestration、approval controls 和 API-backed automation，所以它非常适合放在“任务编排—审批—留痕”这几个节点上。([GitHub][4])

---

## 七、给你一版“岗位—工具—输入—输出”表

### Orchestrator

输入：Mission Control 任务、正式 agent 结果、subagent 结果
输出：任务分派、审批请求、最终摘要、执行决策
工具重点：路由、任务拆解、结果汇总

### Sync Agent

输入：飞书多维表格任务、Orchestrator 最终结果
输出：任务同步记录、状态回写、证据链接
工具重点：表格/API 读写、幂等更新

### Comms Agent

输入：飞书群消息、Orchestrator 指令
输出：提醒、摘要、确认请求、异常通报
工具重点：消息发送、消息解析、格式化通知

### Watcher Agent

输入：任务状态、截止时间、Mission Control 执行状态
输出：风险清单、超期提醒、日报周报
工具重点：定时触发、规则扫描、报表生成

### Knowledge Agent

输入：会议纪要、文档、历史记录、群聊摘要
输出：知识卡片、背景摘要、FAQ、上下文包
工具重点：文档整理、结构化归档、检索

---

## 八、我建议的最小落地顺序

别一开始就全上。

### 第 1 阶段：先上 3 个正式 agent

* Orchestrator
* Sync Agent
* Comms Agent

这时已经能完成：

* 任务同步
* AI 执行
* 结果通知

### 第 2 阶段：再加 Watcher

当你开始需要日报、超期提醒、定时巡检时再上。

### 第 3 阶段：最后加 Knowledge Agent

当项目知识量上来、历史上下文开始影响执行质量时再上。

这样更符合 OpenClaw “先单 Gateway、多 agent，再按需扩”的推荐路径。([OpenClaw][1])

---

## 九、我对你这个项目的最终建议

如果这是一个真实项目，而不是概念验证，我建议你先按下面这套编制启动：

**正式工**

* 1 个 Orchestrator
* 1 个 Sync Agent
* 1 个 Comms Agent
* 1 个 Watcher Agent

**半正式工 / 第二阶段**

* 1 个 Knowledge Agent

**临时工池**

* 日志分析 subagent
* 文档总结 subagent
* 风险分析 subagent
* 周报草拟 subagent

这套最平衡：
既符合 OpenClaw 单 Gateway 多 agent 的官方推荐，也符合 Mission Control 作为统一编排与治理台的角色，而且不会把长期岗位误塞进 one-shot subagent。([OpenClaw][1])
