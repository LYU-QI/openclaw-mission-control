# Repository Guidelines

## Project Structure & Module Organization
- `backend/` contains the FastAPI service.
- Core backend code lives in `backend/app/`: routes in `api/`, domain models in `models/`, request/response schemas in `schemas/`, and business logic in `services/`.
- Database migrations are in `backend/migrations/versions/`.
- Backend tests live in `backend/tests/` and follow `test_*.py` naming.
- `frontend/` is a Next.js app: route files under `frontend/src/app/`, reusable UI in `frontend/src/components/`, shared helpers in `frontend/src/lib/`.
- Generated API client code is under `frontend/src/api/generated/` (do not hand-edit; regenerate).
- Docs and operational notes are under `docs/`.

## Build, Test, and Development Commands
- `make setup`: install/sync backend and frontend dependencies.
- `make check`: CI-parity checks (lint, typecheck, coverage scope, frontend tests, build).
- `make docker-up`: start full stack (`db`, `redis`, `backend`, `frontend`, worker).
- `make backend-test` / `make frontend-test`: run backend pytest and frontend vitest.
- `make backend-e2e`: run mission/feishu/notification end-to-end backend flow.
- `make api-gen`: regenerate frontend TypeScript API client (backend must be running).

## Coding Style & Naming Conventions
- Python: 4-space indentation, max line length 100, `snake_case`; format with Black and isort; lint with flake8; typecheck with strict mypy.
- TypeScript/React: `PascalCase` for components, `camelCase` for variables/functions; lint with ESLint; format with Prettier.
- Keep modules focused; prefer small service functions over large route handlers.

## Testing Guidelines
- Frameworks: `pytest` (backend), `vitest` + Testing Library (frontend).
- Add/adjust tests with every behavior change, especially for API contracts and orchestration logic.
- Run targeted tests locally first (for example, `uv run pytest tests/test_openclaw_decomposer.py -q`) before full `make check`.

## Commit & Pull Request Guidelines
- Follow Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`.
- Keep PRs scoped and reviewable; avoid unrelated generated churn.
- PRs should include: purpose, key changes, test evidence (commands + results), linked issue, and screenshots for UI changes.

## Security & Configuration Tips
- Never commit secrets; copy from `.env.example` and store real values in local `.env`.
- Use `APP_SECRET_ENCRYPTION_KEY` for at-rest secret encryption and keep it out of version control.
