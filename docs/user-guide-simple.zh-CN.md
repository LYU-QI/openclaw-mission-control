# OpenClaw Mission Control 傻瓜式上手指南

这份文档只做一件事：

带你从 0 到 1 跑起项目，并真的用一遍。

不讲太多概念，你照着做就行。

## 1. 先准备什么

你只需要先确认两件事：

- 电脑装了 Docker
- 你在项目根目录里

项目根目录里应该能看到这些文件：

- `compose.yml`
- `README.md`
- `backend/`
- `frontend/`

## 2. 第一次启动

### 第 1 步：复制配置文件

在项目根目录执行：

```bash
cp .env.example .env
```

### 第 2 步：打开 `.env`

把下面两项改掉：

```env
AUTH_MODE=local
LOCAL_AUTH_TOKEN=abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz
```

要求：

- `LOCAL_AUTH_TOKEN` 不能留空
- 长度至少 50 个字符

你也可以顺手加上这一项：

```env
APP_SECRET_ENCRYPTION_KEY=my-local-secret-key-change-me
```

### 第 3 步：启动服务

执行：

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

第一次启动会慢一点，正常。

### 第 4 步：确认后端活着

浏览器打开：

`http://localhost:8000/healthz`

如果能看到正常响应，说明后端起来了。

### 第 5 步：打开前端

浏览器打开：

`http://localhost:3000`

## 3. 第一次登录

如果你现在是本地模式，页面会让你输入 token。

你就输入刚才写进 `.env` 里的：

`LOCAL_AUTH_TOKEN`

如果登录失败，先别慌，通常只看这 3 件事：

1. token 有没有输错
2. token 是否至少 50 个字符
3. `.env` 里的 `AUTH_MODE` 是否为 `local`

## 4. 第一次进入后要做的事

### 第 1 件事：填个人资料

系统大概率会带你到 `/onboarding`。

你只需要填：

- Name
- Timezone

填完点保存。

### 第 2 件事：进入 Dashboard

看到 Dashboard 就说明系统基本通了。

如果 Dashboard 报错，优先检查：

- `http://localhost:8000/healthz` 能不能打开
- 前端有没有登录成功

## 5. 现在开始真正“玩”

下面这套是最简单、最不容易卡住的玩法。

目标：

建一个工作分组，建一个看板，建几个任务，跑通一次协作流程。

### 第 1 步：打开 Organization

左侧菜单找到：

- `Organization`

先确认你能看到组织页面。

能打开就行，先不用折腾复杂权限。

### 第 2 步：创建一个 Board Group

左侧打开：

- `Board groups`

点击创建，名字建议直接写：

`My First Group`

创建成功后，继续下一步。

### 第 3 步：创建一个 Board

左侧打开：

- `Boards`

点击创建，名字建议写：

`My First Board`

如果页面要求你选分组，就选刚才那个 `My First Group`。

### 第 4 步：进入这个 Board

打开你刚创建的 `My First Board`。

你会看到这是系统里最核心的页面。

先不要管太多区块，你只需要盯住这几个：

- 任务区
- Approvals
- Board chat
- Live feed

### 第 5 步：创建 3 个任务

建议直接建这 3 个：

1. `检查系统是否正常`
2. `创建一个测试流程`
3. `写一条测试评论`

你不需要一开始把字段填满，先建出来。

### 第 6 步：改一次任务状态

随便打开一个任务，把状态改掉一次。

例如：

- 从待办改成进行中

这一步的意义是确认：

- 任务更新正常
- Live feed 会出现记录

### 第 7 步：写一条评论

给任意任务加一条评论：

`这是一条测试评论`

如果评论成功，说明 Board 内的基础协作功能已经通了。

### 第 8 步：去 Live feed 看记录

现在打开 Board 里的：

- `Live feed`

你应该能看到刚才做过的事，比如：

- 创建任务
- 更新任务
- 添加评论

如果这里有记录，说明系统核心链路是通的。

## 6. 再往前一步：测试审批

如果你想多试一个功能，接着做这个。

### 第 1 步：打开 `Approvals`

左侧菜单里有：

- `Approvals`

或者在 Board 详情页里看审批区。

### 第 2 步：找一个可以触发审批的动作

不同流程下触发方式可能不一样，但你的目标很简单：

- 让系统里出现一条待审批记录

### 第 3 步：批准或拒绝一次

只要你能完成一次审批操作，就说明人工兜底流程是通的。

## 7. 再往前一步：测试标签

### 第 1 步：打开 `Tags`

创建两个标签：

- `test`
- `urgent`

### 第 2 步：回到 Board

给任务打上标签。

这样你就把最基础的任务分类也跑通了。

## 8. 如果你是管理员，再试这 3 个功能

这三个不是第一步必须做的，但可以后面再玩。

### 8.1 Agents

用途：

- 看 Agent 列表
- 创建或编辑 Agent

如果你现在没有真实 Agent，先只看页面能不能打开。

### 8.2 Gateways

用途：

- 接 OpenClaw Gateway

如果你现在只是本地试玩，可以先跳过。

只有你已经有可用 Gateway 时，再去填：

- Gateway URL
- Token
- Workspace Root

### 8.3 Notifications

用途：

- 配通知
- 发测试消息

如果你只是先熟悉界面，也可以先不做。

## 9. 飞书要不要现在接

不建议第一天就接。

正确顺序是：

1. 先把 Board、Task、Activity 跑通
2. 再去接飞书

不然你很难判断问题到底出在系统本身，还是出在飞书配置。

## 10. 最容易踩坑的 5 个地方

### 坑 1：后端没起来

检查：

`http://localhost:8000/healthz`

打不开就先别管前端。

### 坑 2：token 配了，但太短

`LOCAL_AUTH_TOKEN` 至少 50 个字符。

### 坑 3：前端能开，接口全报错

通常是：

- 没登录
- token 错了
- 后端没起来

### 坑 4：远程访问时还在用 `localhost`

如果你不是在同一台机器访问，就不能继续写 `localhost`。

你要改真实地址，重点看：

- `NEXT_PUBLIC_API_URL`
- `CORS_ORIGINS`
- `BASE_URL`

### 坑 5：一上来就搞 Gateway 和飞书

不建议。

先把最简单的 Board 和 Task 跑通，再加集成。

## 11. 你至少要学会的 4 个命令

### 启动

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

### 停止

```bash
docker compose -f compose.yml --env-file .env down
```

### 看后端健康状态

浏览器打开：

`http://localhost:8000/healthz`

### 一键启动完整栈

```bash
make docker-up
```

## 12. 最短成功路径

如果你只想确认“这个项目我会用了没”，那就以这 6 条为准：

1. 能启动服务
2. 能登录
3. 能创建 Board Group
4. 能创建 Board
5. 能创建和更新 Task
6. 能在 Live feed 看到记录

做到这里，就已经算上手了。

## 13. 下一步建议

你已经跑通基础玩法后，再按这个顺序加功能：

1. Tags
2. Approvals
3. Notifications
4. Agents
5. Gateways
6. Feishu Sync
7. Skills Marketplace

## 14. 看更完整说明

如果你后面不满足于“傻瓜式”，再看这些文档：

- [完整中文使用手册](./user-manual.zh-CN.md)
- [Getting started](./getting-started/README.md)
- [Authentication](./reference/authentication.md)
- [Configuration reference](./reference/configuration.md)

## 15. 一句话版本

最简单的玩法就是：

先用 Docker 跑起来，用本地 token 登录，建一个 Group、一个 Board、三个 Task，再去 Live feed 看记录。
