# OpenClaw Mission Control 中文使用手册

这份手册面向第一次接触本项目的使用者，目标是回答两个问题：

- 这个项目是干什么的
- 我应该按什么顺序把它跑起来并真正用起来

如果你只想先跑通，先看“5 分钟快速上手”；如果你要长期使用，建议从“推荐上手路径”开始。

## 1. 项目是什么

OpenClaw Mission Control 是 OpenClaw 的控制台和 HTTP API。

它把这些能力集中到一个系统里：

- 组织与成员管理
- Board Group / Board / Task 协作
- Agent 生命周期管理
- Gateway 接入与远程运行环境管理
- 审批流和审计留痕
- 飞书同步
- 通知通道
- Skills Marketplace / Skill Packs
- 活动流、指标面板和 API 自动化

简单理解：

- `Board Group` 是一组协作板的容器
- `Board` 是日常工作的主战场
- `Task` 是具体执行项
- `Agent` 是执行或协作实体
- `Gateway` 是连接 OpenClaw 运行环境的桥
- `Approval` 是需要人工确认的关键动作
- `Mission` 是更高层的编排和执行视图

## 2. 你可以怎么“玩”

这个项目有三种典型玩法。

### 玩法 A：把它当成团队任务与 Agent 控制台

适合先熟悉系统。

你可以：

1. 创建一个 Board Group
2. 创建几个 Board
3. 在 Board 里建任务、分配 Agent、加评论、看活动流
4. 用 Approvals 管理高风险动作

这一套即使不接 Gateway，也能先跑起来。

### 玩法 B：把它当成 OpenClaw 运行总控台

适合已经有 OpenClaw Gateway 的团队。

你可以：

1. 在 Gateways 页面登记网关
2. 把 Board 绑定到指定 Gateway
3. 管理 Agent 的上线、下线、检查心跳和会话状态
4. 在 Dashboard 和 Activity 里看系统整体状态

### 玩法 C：把它当成企业流程编排层

适合要接飞书、审批、通知和自动化的人。

你可以：

1. 接入 Feishu Sync
2. 配置通知通道
3. 建立审批流程
4. 用 API 或前端统一驱动日常协作

## 3. 环境要求

最省事的方式是 Docker。

### 推荐环境

- macOS 或 Linux
- Docker Engine + Docker Compose v2

### 本地开发环境

如果你不用 Docker，需要：

- Python 3.12+
- `uv`
- Node.js 18+（仓库根 README 对本地模式建议 Node 22+）
- PostgreSQL

## 4. 目录速览

- `backend/`：FastAPI 后端
- `frontend/`：Next.js 前端
- `compose.yml`：Docker 编排
- `docs/`：项目文档
- `install.sh`：交互式安装脚本

## 5. 5 分钟快速上手

### 方式一：安装脚本

如果你已经 clone 了仓库，在项目根目录执行：

```bash
./install.sh
```

脚本会交互式地帮你：

- 选择 `docker` 或 `local` 模式
- 检查依赖
- 生成环境文件
- 启动服务

### 方式二：手动 Docker 启动

#### 第一步：复制环境文件

```bash
cp .env.example .env
```

#### 第二步：编辑 `.env`

至少改这几个值：

```env
AUTH_MODE=local
LOCAL_AUTH_TOKEN=换成一个至少50字符的长token
NEXT_PUBLIC_API_URL=auto
```

建议同时设置：

```env
APP_SECRET_ENCRYPTION_KEY=换成一个你自己的密钥
```

#### 第三步：启动

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

#### 第四步：打开页面

- 前端: `http://localhost:3000`
- 后端健康检查: `http://localhost:8000/healthz`

#### 第五步：停止

```bash
docker compose -f compose.yml --env-file .env down
```

## 6. 推荐上手路径

第一次使用，建议按下面顺序。

1. 跑起系统
2. 登录
3. 完成个人资料和时区设置
4. 创建或确认组织
5. 创建 Board Group
6. 创建 Board
7. 在 Board 中建任务、评论、审批
8. 需要时再接入 Gateway / Feishu / Notifications / Skills

这样最稳，不会一上来就把集成项全堆在一起。

## 7. 登录与认证

项目支持两种认证模式。

### 本地模式 `local`

适合自托管和本地体验，默认最容易上手。

后端配置：

```env
AUTH_MODE=local
LOCAL_AUTH_TOKEN=你的长token
```

前端配置：

```env
NEXT_PUBLIC_AUTH_MODE=local
```

使用方式：

- 打开前端页面
- 在本地登录页输入 `LOCAL_AUTH_TOKEN`
- 之后请求会自动带上 `Authorization: Bearer <token>`

### Clerk 模式 `clerk`

适合正式登录体系。

需要额外配置：

- 后端：`CLERK_SECRET_KEY`
- 前端：`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`

如果只是本地试用，不建议一开始就上 Clerk。

## 8. 首次进入系统后先做什么

### 8.1 完成个人资料

`/onboarding` 页面会要求你补齐：

- Name
- Timezone

时区很重要，因为：

- Dashboard 的时间展示依赖它
- 任务时间字段依赖它
- Mission 与审批事件的时间判断依赖它

### 8.2 看 Dashboard

`/dashboard` 是总览页，适合先确认系统是否正常。

你通常能看到：

- 在线 Agent
- 进行中的任务
- 错误率
- 完成速度
- 工作负载
- 吞吐
- Gateway 健康状态

如果 Dashboard 本身报错，优先检查：

- 后端是否启动
- 登录 token 是否正确
- `NEXT_PUBLIC_API_URL` 是否可达

## 9. 主要页面怎么用

下面按左侧导航顺序说明。

### 9.1 Dashboard

作用：

- 看系统整体健康度和关键指标
- 快速发现 Agent、任务、Gateway 的异常

适合谁：

- 值班人员
- 平台管理员
- 日常观察整体运行状态的人

### 9.2 Activity

作用：

- 查看系统实时活动流
- 追踪谁在什么时候创建、更新、审批或触发了动作

适合：

- 排障
- 审计
- 回溯问题过程

### 9.3 Board Groups

作用：

- 把多个 Board 组织成一个协作分组
- 查看组内任务概况
- 维护组级聊天和组级笔记

建议用法：

- 按团队、项目线、客户、环境或阶段分组

例如：

- `Growth Team`
- `Production Incident`
- `Client A Delivery`

### 9.4 Boards

作用：

- 日常工作主界面
- 维护任务、评论、审批、Board Chat、Live Feed、设置

一个 Board 页面通常包含：

- 任务看板
- 审批面板
- Board Chat
- Live Feed
- Board 设置

推荐把 Board 当作“一个真实执行现场”来理解。

### 9.5 Board 内常见操作

进入某个 Board 后，通常这样用：

1. 创建任务
2. 设置状态、优先级、负责人或 Agent
3. 补充评论和上下文
4. 需要人工确认时提交审批
5. 在 Live Feed 看最新动态
6. 在 Board Chat 记录板级沟通或指令

适合管理的内容：

- 功能开发
- 运维动作
- 缺陷修复
- Agent 协作任务

### 9.6 Tags

作用：

- 给任务、板或流程对象打标签
- 方便筛选和管理

常见标签设计：

- `prod`
- `urgent`
- `needs-review`
- `customer-a`

### 9.7 Approvals

作用：

- 统一查看所有 Board 的审批项
- 执行批准或拒绝

适合放进审批流的动作：

- 高风险变更
- 影响生产的动作
- 需要主管确认的任务流转

如果你的流程强调人工兜底，这个页面会用得很多。

### 9.8 Custom Fields

作用：

- 为任务增加自定义字段
- 约束不同组织的任务录入规范

适合补充的字段：

- 影响范围
- 发布窗口
- 客户优先级
- 关联工单号

如果你要把 Mission Control 真正作为团队系统长期使用，建议尽早定义好字段。

### 9.9 Missions

作用：

- 查看 Mission 生命周期
- 跟踪执行状态
- 进入详情看任务拆解与结果证据

建议理解为更高层的编排视图，不是普通任务列表的替代品。

### 9.10 Feishu Sync

作用：

- 把 Mission Control 与飞书多维表格/流程同步起来
- 管理字段映射和同步历史

使用前你通常要准备：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- 飞书 Bitable 的 app token / table id

建议：

- 先在测试环境验证字段映射
- 确认同步方向和触发方式
- 再上生产数据

### 9.11 Notifications

作用：

- 配置通知通道
- 测试通知
- 查看通知投递日志

典型用途：

- Mission 完成通知
- Mission 失败告警
- 审批请求提醒

### 9.12 Skills Marketplace / Skill Packs

作用：

- 管理技能市场条目
- 安装或维护 Skill Packs

更适合管理员使用，因为它偏平台能力扩展，不是普通用户的日常入口。

### 9.13 Organization

作用：

- 管理组织信息
- 邀请成员
- 设置成员权限
- 控制成员对 Board 的读写范围

推荐做法：

- 管理员统一建组织
- 按最小权限原则分配 Board 访问权限

### 9.14 Agents

作用：

- 查看 Agent 列表
- 创建、编辑、删除 Agent
- 查看 Agent 详情与健康状态

如果你有多 Agent 协作，这一页和 Board 会来回切换使用。

### 9.15 Gateways

作用：

- 管理 OpenClaw Gateway 连接
- 指定工作目录
- 配置网关 Token
- 允许或禁止自签名 TLS

网关 URL 示例：

- `ws://localhost:18789`
- `wss://gateway.example.com`

如果你使用自签名证书，需要在 Gateway 配置里启用“允许自签名 TLS 证书”。生产环境优先使用正式证书。

### 9.16 Settings

作用：

- 个人设置
- 账户相关设置

## 10. 一条最实用的入门工作流

如果你只是想真正“玩起来”，建议照着下面做一次。

### 场景：建立一个研发协作板

1. 启动系统并登录
2. 打开 Organization，确认自己有管理员权限
3. 打开 Board Groups，新建 `Platform Team`
4. 打开 Boards，新建 `Agent Runtime Upgrade`
5. 在 Board 内创建几个任务
6. 给任务加标签，例如 `urgent`、`release`
7. 如果某任务需要审核，发起 Approval
8. 在 Activity 页面确认事件流正常
9. 在 Notifications 配置一个测试通知通道
10. 有 OpenClaw 运行环境时，再去 Gateways 绑定网关

做到这一步，你已经不是“把项目跑起来”，而是真的在使用它了。

## 11. Gateway 接入建议

如果你准备把它和 OpenClaw 真正连起来，建议按这个顺序。

1. 先单独确认 Gateway 本身可连通
2. 在 Mission Control 中创建 Gateway
3. 填写正确的 `BASE_URL`
4. 确保网关能访问 Mission Control 的后端地址
5. 再把 Board 或 Agent 关联到 Gateway

关键配置：

- 后端 `BASE_URL` 必填，供网关模板和心跳使用
- Gateway URL 使用 `ws://` 或 `wss://`
- 若是远程部署，`BASE_URL` 和 `NEXT_PUBLIC_API_URL` 都必须填成真实可访问地址，不能偷懒用 `localhost`

## 12. 飞书接入建议

启用飞书前建议先确认以下项：

- `.env` 中已配置 `FEISHU_APP_ID`
- `.env` 中已配置 `FEISHU_APP_SECRET`
- 已确认同步的目标表结构
- 已确定字段映射关系

推荐流程：

1. 先配置一条测试同步
2. 触发一次手动同步
3. 检查 Sync History
4. 再扩展到正式表

## 13. 通知配置建议

通知系统适合做这三类事情：

- 结果通知：任务或 Mission 完成
- 失败告警：Mission 失败、投递失败、同步失败
- 审批提醒：有新的待审项

建议至少保留一个可测试的通知通道，用于排障。

## 14. 常用命令

在仓库根目录执行。

### 安装依赖

```bash
make setup
```

### 启动完整 Docker 栈

```bash
make docker-up
```

### 停止 Docker 栈

```bash
make docker-down
```

### 自动监听前端改动

```bash
make docker-watch
```

### 后端测试

```bash
make backend-test
```

### 前端测试

```bash
make frontend-test
```

### 完整检查

```bash
make check
```

### 生成前端 API Client

要求后端已运行在 `127.0.0.1:8000`：

```bash
make api-gen
```

## 15. 本地开发模式

如果你不想用 Docker，可以分开跑后端和前端。

### 15.1 跑数据库

最简单的方法是只启动数据库容器：

```bash
cp .env.example .env
docker compose -f compose.yml --env-file .env up -d db
```

### 15.2 跑后端

```bash
cd backend
cp .env.example .env
uv sync --extra dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 15.3 跑前端

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

然后访问：

- 前端: `http://localhost:3000`
- 后端: `http://localhost:8000`

## 16. 常见问题

### 16.1 页面能打开，但接口报错

优先检查：

- 后端是否存活：`http://localhost:8000/healthz`
- `NEXT_PUBLIC_API_URL` 是否可从浏览器访问
- 前后端认证模式是否一致

最常见错误是：

- 前端是 `local`，后端却配成 `clerk`
- `NEXT_PUBLIC_API_URL` 指向了错误地址

### 16.2 登录一直失败

检查：

- `AUTH_MODE=local` 时，输入的 token 是否和 `.env` 完全一致
- `LOCAL_AUTH_TOKEN` 是否满足至少 50 字符
- 前端是否设置了 `NEXT_PUBLIC_AUTH_MODE=local`

### 16.3 后端起不来

检查：

- 数据库是否启动
- `DATABASE_URL` 是否正确
- 迁移是否已执行

可以手动执行：

```bash
make backend-migrate
```

### 16.4 跨机器访问失败

如果你不是在同一台机器访问，需要检查：

- `CORS_ORIGINS`
- `BASE_URL`
- `NEXT_PUBLIC_API_URL`

这三个值都应该是“真实可访问地址”，不要再写 `localhost`。

### 16.5 Gateway 连不上

检查：

- Gateway URL 是否正确
- `ws://` / `wss://` 是否匹配实际配置
- 自签名证书是否已允许
- Mission Control 后端的 `BASE_URL` 是否可被 Gateway 访问

## 17. 生产前最低建议

如果你要把它用于真实团队，请至少做到这些：

- 不要使用默认 token
- 配置 `APP_SECRET_ENCRYPTION_KEY`
- 使用正式域名和可访问的 `BASE_URL`
- 若使用 `wss://`，优先使用有效证书
- 给组织成员分配最小必要权限
- 为审批、通知和活动流建立日常检查流程

## 18. 推荐阅读

- `README.md`
- `docs/getting-started/README.md`
- `docs/reference/authentication.md`
- `docs/reference/configuration.md`
- `backend/README.md`
- `frontend/README.md`
- `docs/troubleshooting/README.md`
- `docs/openclaw_gateway_ws.md`

## 19. 一句话总结

最容易的玩法是：

先用 Docker 以 `local` 认证模式跑起来，登录后先建组织、Board Group、Board 和任务，把审批、活动流和通知走通；确认基础协作稳定后，再逐步接入 Gateway、飞书和 Skills。
