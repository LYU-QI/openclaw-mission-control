# OpenClaw Mission Control 10 分钟上手演练

这是一份照着做就能跑通的演练脚本。

目标只有一个：

10 分钟内完成这 6 件事：

1. 启动系统
2. 登录系统
3. 创建一个分组
4. 创建一个看板
5. 创建一个任务
6. 在活动流里看到你的操作记录

如果你做完这 6 件事，就算真正上手了。

## 0. 开始前确认

你现在需要：

- 已安装 Docker
- 正在项目根目录

项目根目录应该有：

- `compose.yml`
- `backend/`
- `frontend/`

## 1. 第 1 分钟：准备配置

打开终端，在项目根目录执行：

```bash
cp .env.example .env
```

然后打开 `.env`，只改下面两行：

```env
AUTH_MODE=local
LOCAL_AUTH_TOKEN=abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz
```

如果你愿意，再补一行：

```env
APP_SECRET_ENCRYPTION_KEY=my-local-secret-key-change-me
```

### 成功标志

- 根目录里已经有 `.env`
- `LOCAL_AUTH_TOKEN` 不是空的
- `LOCAL_AUTH_TOKEN` 长度至少 50 个字符

## 2. 第 2 到 4 分钟：启动系统

终端执行：

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

第一次启动如果稍慢，正常。

然后打开浏览器访问：

`http://localhost:8000/healthz`

### 成功标志

- 页面能打开
- 不是浏览器报“无法连接”

接着打开：

`http://localhost:3000`

### 成功标志

- 前端页面能打开
- 你能看到登录界面或系统首页

## 3. 第 5 分钟：登录

如果页面要求输入 token，就输入你刚才写进 `.env` 的：

`LOCAL_AUTH_TOKEN`

### 成功标志

- 页面不再停留在登录状态
- 你能进入系统内部页面

如果登录失败，只检查这三件事：

1. `.env` 里是不是 `AUTH_MODE=local`
2. token 有没有输错
3. token 是否至少 50 个字符

## 4. 第 6 分钟：完成个人资料

系统可能会带你到：

`/onboarding`

你只填两项：

- `Name`
- `Timezone`

然后点保存。

### 成功标志

- 页面跳转到 Dashboard
- 或者你能手动进入 `/dashboard`

## 5. 第 7 分钟：创建第一个分组

左侧菜单点击：

- `Board groups`

然后点击创建。

建议名字直接填：

`Demo Group`

### 成功标志

- 列表里出现 `Demo Group`

如果没有出现，刷新一次页面再看。

## 6. 第 8 分钟：创建第一个看板

左侧菜单点击：

- `Boards`

点击创建。

建议这样填：

- Name: `Demo Board`
- Group: `Demo Group`

然后保存。

### 成功标志

- 列表里出现 `Demo Board`
- 你能点击进入它

## 7. 第 9 分钟：创建第一个任务

进入 `Demo Board`。

在任务区域点击新增任务。

标题直接填：

`我的第一个任务`

能填描述就填一句：

`这是一个测试任务`

然后保存。

### 成功标志

- 板上出现 `我的第一个任务`

接着再做一件小事：

把这个任务的状态改一次。

例如：

- 从待办改为进行中

### 成功标志

- 任务状态确实变了

## 8. 第 10 分钟：看活动流

还在 `Demo Board` 里，找到：

- `Live feed`

你应该能看到刚才的操作记录，例如：

- 创建任务
- 更新任务状态

### 成功标志

- Live feed 里确实出现了你的操作痕迹

这就说明核心链路已经跑通了。

## 9. 如果你还多 2 分钟，再做这两件事

### 9.1 写一条评论

给 `我的第一个任务` 加一条评论：

`测试评论`

成功标志：

- 评论保存成功
- Live feed 里能看到记录

### 9.2 建一个标签

左侧点：

- `Tags`

新建一个标签：

`test`

然后回到任务里给它打上这个标签。

成功标志：

- 标签能创建
- 任务能关联标签

## 10. 你现在已经会了什么

如果你做完上面流程，说明你已经会了：

- 启动系统
- 本地 token 登录
- 完成首次进入配置
- 创建 Board Group
- 创建 Board
- 创建 Task
- 查看 Live feed

这已经够你开始真正使用项目了。

## 11. 接下来按什么顺序继续

建议按下面顺序继续玩：

1. 再创建几个任务
2. 试试评论和标签
3. 看 `Approvals`
4. 看 `Agents`
5. 看 `Notifications`
6. 最后再碰 `Gateways` 和 `Feishu Sync`

原因很简单：

- 前面的功能最基础
- 后面的功能依赖更多配置

## 12. 失败时最短排查法

### 情况 1：前端打不开

重试：

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

然后再打开：

`http://localhost:3000`

### 情况 2：后端打不开

先看：

`http://localhost:8000/healthz`

如果打不开，先不要折腾前端。

### 情况 3：登录失败

只检查：

- `AUTH_MODE=local`
- token 是否一致
- token 是否够长

### 情况 4：页面能开，但操作没反应

优先看：

- 你是不是已经登录
- 后端健康检查是否正常

## 13. 一句话通关标准

你只要能看到：

- `Demo Group`
- `Demo Board`
- `我的第一个任务`
- Live feed 里的操作记录

就算这套系统已经被你跑通了。

## 14. 下一份该看什么

跑通这一份之后，建议继续看：

- [傻瓜式上手指南](./user-guide-simple.zh-CN.md)
- [完整中文使用手册](./user-manual.zh-CN.md)
