# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

OpenClaw Mission Control 是一个集中式运营平台，用于管理 OpenClaw 的 Agent、Gateway、Mission 和组织。提供工作编排、审批驱动的治理、飞书集成和 API 自动化能力。

## 核心概念

- **Gateway** - OpenClaw 运行时网关，负责执行 Agent 任务
- **Board** - 任务看板，组织工作流
- **Mission** - 任务执行单元，由 Orchestrator 协调
- **Subtask** - Mission 的子任务，由 Worker Agents 执行
- **Lead Agent** - 看板负责人，审核任务结果，生成评论
- **Worker Agents (Subagents)** - 执行具体任务的临时 agent
- **Orchestrator** - 协调 Mission 流程，分配 subtask 给 subagents

## 飞书集成

- **任务同步**：Bitable（多维表格）↔ Mission Control 双向同步
- **消息通知**：任务完成、审批请求等推送到飞书群
- **回写规则**：仅 `external_source == "feishu"` 的任务会回写到飞书多维表格

## 架构

**Monorepo**，两个包通过根目录的 `Makefile` 协调（无 Nx/Turborepo）：
- `backend/` — Python 3.12 FastAPI 服务（uv 包管理器）
- `frontend/` — Next.js 16 TypeScript 应用（npm）

### 后端 (`backend/app/`)
- `api/` — FastAPI 路由处理器（保持轻量，委托给 services）
- `models/` — SQLModel ORM 模型（PostgreSQL 16，异步 SQLAlchemy）
- `schemas/` — Pydantic 请求/响应模型
- `services/` — 按领域组织的业务逻辑（missions、openclaw、feishu、notification、webhooks）
- `core/` — 横切关注点：认证、配置、错误处理、日志、密钥加密
- `db/` — 会话管理、CRUD 辅助工具、分页
- `migrations/` — Alembic 数据库迁移

### 前端 (`frontend/src/`)
- `app/` — Next.js App Router 页面
- `components/` — 按领域组织的组件 + `ui/`（shadcn 风格的 Radix 基础组件）
- `api/generated/` — **自动生成的** React Query hooks + TypeScript 类型（禁止手动编辑）
- `api/mutator.ts` — 自定义 fetch 封装（认证注入、SSE 支持、错误处理）
- `lib/` — 共享工具函数
- `auth/` — 双模式认证（Clerk JWT 或本地 bearer token）

### API 客户端生成流水线
Orval 读取后端的 OpenAPI schema（`/openapi.json`），生成 TypeScript 类型和 React Query hooks 到 `frontend/src/api/generated/`。重新生成时后端必须运行在 `127.0.0.1:8000`：`make api-gen`。

### 状态管理
TanStack React Query 是唯一的状态管理层（无 Redux/Zustand）。查询配置：15 秒 stale time，5 分钟 GC，窗口聚焦时重新获取。

### 认证
双模式：`AUTH_MODE=clerk`（Clerk JWT）或 `AUTH_MODE=local`（共享 bearer token，最少 50 字符）。

### 基础设施
Docker Compose 运行 5 个服务：`db`（Postgres 16）、`redis`（Redis 7）、`backend`、`frontend`、`webhook-worker`（RQ）。

## 常用命令

| 命令 | 说明 |
|------|------|
| `make setup` | 安装所有依赖（uv sync + npm install） |
| `make check` | 完整 CI：lint + 类型检查 + 覆盖率 + 测试 + 构建 |
| `make backend-test` | 运行后端 pytest |
| `make frontend-test` | 运行前端 vitest（含覆盖率） |
| `make backend-e2e` | 运行后端 E2E 流程测试 |
| `make backend-coverage` | 作用域 100% 覆盖率检查（error_handling、mentions） |
| `make backend-lint` | isort + black 检查 + flake8 + mypy |
| `make frontend-lint` | ESLint |
| `make typecheck` | mypy（后端）+ tsc（前端） |
| `make format` | 自动格式化：isort + black（后端），prettier（前端） |
| `make api-gen` | 重新生成 TS API 客户端（后端需运行在 :8000） |
| `make docker-up` | 启动完整 Docker 服务栈 |
| `make docker-watch` | Watch 模式（自动重建前端 UI 变更） |
| `make docker-down` | 停止 Docker 服务栈 |
| `make build` | Next.js 生产构建 |
| `make docs-lint` | Markdown 文件 lint |
| `make backend-migrate` | 应用数据库迁移 |

### 运行单个测试
```bash
# 后端：单个文件
cd backend && uv run pytest tests/test_openclaw_decomposer.py -q

# 后端：单个测试函数
cd backend && uv run pytest tests/test_openclaw_decomposer.py::test_function_name -q

# 前端：单个文件
cd frontend && npx vitest run src/lib/backoff.test.ts
```

### 快速本地开发流程
```bash
docker compose -f compose.yml --env-file .env up -d db
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

### 快速启动（生产风格）
```bash
# 一键安装脚本（交互式）
./install.sh
# 或
curl -fsSL https://raw.githubusercontent.com/abhi1693/openclaw-mission-control/master/install.sh | bash
```

### 健康检查
- 后端：`http://localhost:8000/healthz`
- 前端：`http://localhost:3000`

## 编码规范

### Python
- Black + isort + flake8 + strict mypy。最大行宽 100。使用 `snake_case`。
- 路由处理器保持轻量，业务逻辑放在 `services/` 中。

### TypeScript/React
- ESLint + Prettier。组件使用 `PascalCase`，变量/函数使用 `camelCase`。
- 故意未使用的解构变量加 `_` 前缀以满足 lint 要求。

### 提交规范
Conventional Commits：`feat:`、`fix:`、`refactor:`、`test:`、`docs:`、`chore:`、`perf:`。

## 测试

- **后端**：pytest + pytest-asyncio。测试在 `backend/tests/` 中，遵循 `test_*.py` 命名。Conftest 设置 `AUTH_MODE=local`。
- **前端**：Vitest + Testing Library。对明确列出的模块执行 100% 覆盖率检查。
- **E2E**：Cypress（前端，`frontend/cypress/e2e/`）和后端流程测试（`make backend-e2e`）。
- 覆盖率策略：逐步扩展选定模块的 100% 覆盖率门控（参见 `Makefile` 和 `vitest.config.ts`）。

## CI 流水线

GitHub Actions（`.github/workflows/ci.yml`）：lint、类型检查、作用域覆盖率、测试、构建、迁移完整性检查（每个 PR 一次迁移，upgrade/downgrade/upgrade 循环）、Cypress E2E、文档 lint。

## 配置

通过 Pydantic Settings 的环境变量驱动。将 `.env.example` 复制为 `.env`。关键变量：`AUTH_MODE`、`DATABASE_URL`、`BASE_URL`、`LOCAL_AUTH_TOKEN`（或 `CLERK_SECRET_KEY`）、`RQ_REDIS_URL`、`FEISHU_APP_ID`/`FEISHU_APP_SECRET`。开发环境下 Alembic 迁移在启动时自动执行（`DB_AUTO_MIGRATE=true` 默认开启）。

## 文档

- 入口：`docs/README.md`
- 架构：`docs/architecture/README.md`
- 部署：`docs/deployment/README.md`
- 开发：`docs/development/README.md`

## 环境模板

- 根目录：`.env.example`
- 后端：`backend/.env.example`
- 前端：`frontend/.env.example`

## 用户全局规则

本项目使用 `~/.claude/rules/` 中的全局规则（编码风格、测试、Git 工作流、性能优化等）。Claude Code 会自动应用这些规则。
