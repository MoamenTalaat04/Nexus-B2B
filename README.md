# Nexus B2B — AI SDR for Egyptian B2B

An AI sales-development agent that runs B2B lead generation for a business owner who has no technical background.

The owner signs up, uploads a few files about the business, answers a short onboarding form, connects a WhatsApp Business number, and turns the agent on. From then on the agent runs the cycle every day by itself:

1. Builds an **Ideal Customer Profile (ICP)** from the owner's files and answers.
2. **Finds potential customers**, starting with Google Maps (Places API).
3. **Scores and filters** them against the ICP, with a short reason for every decision.
4. **Finds contact details**, mainly a mobile number that can be reached on WhatsApp.
5. **Reaches out on WhatsApp** with a personalized first message (human approval by default).
6. **Holds the conversation**, answering from the company's own knowledge.
7. **Classifies every reply**: interested, not interested, wants an offer, wants management, later, wrong contact, or opt-out.
8. **Escalates hot leads** to the owner on Telegram.
9. **Logs everything** in a built-in CRM with reports, and learns from won and lost deals.

The design follows the "B2B Growth Engine" reference architecture (intent data, enrichment, an LLM, a database, BI, outreach tools, and a CRM). The difference is that everything is one product and every external dependency sits behind a replaceable adapter.

> **Status:** in development (Raed Misr, Agentic AI Engineering track). Deadline: Fri Dec 11, 2026.

## Documentation

| File | What it is |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Rules every coding agent follows in this repo (loaded automatically by Claude Code) |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | **Source of truth**: tables, enums, interfaces, jobs, API routes, env vars |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, the daily agent cycle, the lead state machine, guardrails |
| [docs/plan/00-START-HERE.md](docs/plan/00-START-HERE.md) | Team plan: calendar, who does what, the task protocol, showcase list |
| [docs/plan/tasks/](docs/plan/tasks/) | One file per member with ready-to-paste task prompts |
| [docs/ai-dev-log.md](docs/ai-dev-log.md) | Log of every task built with a coding agent |

## Stack

| Area | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| Background jobs | arq on Redis (cron in Africa/Cairo time) |
| Database | PostgreSQL 16, Redis 7 (Docker Compose) |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query |
| LLM | Anthropic API: Claude Opus 5.5 for reasoning, Claude Haiku 5.5 for bulk work |
| Lead source | Google Places API (New) |
| Outreach channel | WhatsApp Cloud API (official) |
| Owner notifications | Telegram bot |
| Tooling | uv + poethepoet (backend), npm (frontend), GitHub Actions CI |

## Quickstart

Works on Windows, macOS and Linux. No `make` needed.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.12 for you)
- [Node.js](https://nodejs.org/) 22 or newer
- Git

> **Windows, PowerShell:** if `npm` fails with "running scripts is disabled on this system", either run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or call `npm.cmd` instead of `npm`.

### 1. Infrastructure and config

```bash
git clone https://github.com/MoamenTalaat04/Nexus-B2B.git
cd Nexus-B2B
cp .env.example .env
docker compose up -d db redis
```

The defaults in `.env` use mock adapters and a mock LLM, so you don't need any API keys to start.

### 2. Backend (terminal 1)

```bash
cd backend
uv sync
uv run poe migrate
uv run poe api
```

Check it: <http://localhost:8000/api/v1/health> returns `{"status":"ok","db":"ok","redis":"ok"}`. The API docs are at <http://localhost:8000/docs>.

### 3. Worker (terminal 2)

```bash
cd backend
uv run poe worker
```

### 4. Frontend (terminal 3)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The page shows the backend status through the `/api` proxy.

## Everyday commands

| Command (run in `backend/`) | What it does |
|---|---|
| `uv run poe api` | FastAPI on :8000 with auto-reload |
| `uv run poe worker` | arq worker (jobs + cron) |
| `uv run poe migrate` | Apply migrations |
| `uv run poe makemigration "add leads"` | Autogenerate a migration from the models |
| `uv run poe check` | ruff + format check + mypy + pytest (**must pass before pushing**) |
| `uv run poe format` | Auto-format and auto-fix lint |
| `uv run poe eval <suite>` | Run an eval suite (calls the real API, costs money, not in CI) |
| `uv run poe seed-demo` | Create the demo tenant and data |

| Command (run in `frontend/`) | What it does |
|---|---|
| `npm run dev` | Next.js on :3000 |
| `npm run check` | lint + typecheck + tests (**must pass before pushing**) |
| `npm run build` | Production build |

The backend tests need Postgres and Redis running. They create a separate `app_test` database automatically and roll back every test.

## Project structure

```text
backend/
  app/
    main.py        FastAPI app; routers in app/api/*.py are auto-mounted under /api/v1
    config.py      all settings (env vars)
    db.py          async engine + get_session dependency
    models/        SQLAlchemy models (base.py has Base + mixins)
    schemas/       Pydantic request/response models
    api/           routers (one per area)
    services/      business logic
    agents/        LLM-powered agents; prompts in agents/prompts/*.md
    adapters/      external systems behind interfaces (LLM, search, WhatsApp, enrichment, notify)
    workers/       arq worker; jobs in workers/jobs/*.py (any async job_* is auto-registered)
    core/          errors, security, tenancy, tracing, lead state machine, crypto, phones
  alembic/         migrations
  evals/           eval suites and datasets
  tests/
frontend/
  src/app/         Next.js routes ((auth) and (app) groups arrive in P0-4)
  src/components/  UI components (shadcn/ui in components/ui)
  src/hooks/       TanStack Query hooks
  src/lib/         API client, types, utils
docs/              contracts, architecture, team plan, dev log
docker-compose.yml Postgres 16 + Redis 7
```

## Adding code: the two extension points

- **API router:** create `backend/app/api/<area>.py` with `router = APIRouter(prefix="/<area>", tags=["<area>"])`. It is mounted under `/api/v1` automatically.
- **Background job:** create `backend/app/workers/jobs/<area>.py` with `async def job_<name>(ctx, ...)`. It is registered automatically. For scheduled jobs, add `CRON_JOBS = [cron(job_<name>, hour=9, minute=0)]` (times are Cairo time). Enqueue from anywhere with `await enqueue("job_<name>", ...)` from `app.workers.queue`.
- **Errors:** raise `AppError("snake_case_code", "Human message", status_code=409)` from `app.core.errors`. Every error response has the shape `{"error": {"code": ..., "message": ...}}`.

## Contributing

1. Pick up your task from `docs/plan/tasks/member-<letter>.md` and follow the protocol in `docs/plan/00-START-HERE.md` (section 4).
2. Everyone pushes directly to `main`; there is no review gate. Start commit messages with the task id, e.g. `P2-3: lead scoring agent`.
3. Before pushing: `uv run poe check` and `npm run check` must pass, then `git pull --rebase origin main`.
4. CI runs both checks on every push to `main`. If it goes red after your push, fix it first.
5. Contract changes (`docs/CONTRACTS.md`) are announced in the group chat and pushed as their own `contract:` commit.

## Responsible outreach

- WhatsApp uses the official Cloud API only. The first message to a lead is an approved template.
- `demo_mode` is on by default: every outbound message is redirected to the team's whitelisted test phones.
- Opt-out is final. A lead who opts out never receives another message.
- No LinkedIn scraping. Lead data comes from Google Places and the businesses' own public websites (robots.txt respected).
- Personal data is handled in line with Egypt's Personal Data Protection Law (151/2020).
