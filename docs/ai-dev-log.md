# AI Development Log

We build this project with coding agents (Claude Code + Claude Opus 5.5). After **every task**, the owner appends one entry. This log becomes the "how we used agentic engineering" part of the final presentation, so be honest. The mistakes are the most valuable part.

## Running totals (update at the end of each pipeline)

| Pipeline | Tasks | Agent sessions | Est. hours saved | Bugs caught by AI review | Bugs caught at slice demo | Contract changes |
|---|---|---|---|---|---|---|
| P0 | | | | | | |
| P1 | | | | | | |
| P2 | | | | | | |
| P3 | | | | | | |
| P4 | | | | | | |

## Entry template

```
### <task id> — <title> — <owner> — <date>
- Sessions / approx. time: 
- Plan-mode corrections I made (where the agent misread the task/contract):
- What the agent did well:
- What it got wrong and how I caught it (tests? review? running it?):
- Prompt tweaks that helped (copy the exact sentence):
- Eval result (if any): suite, score before → after
- Would I do it differently next time?
```

## Entries

### P0-0 — Repo scaffold, tooling, CI — Claude (Claude Code, Opus 5.5) — 2026-11-11
- Sessions / approx. time: 1 session, about 1 hour including toolchain setup on a fresh Windows machine.
- Plan-mode corrections: the repo's first README proposed a different stack (NestJS, Prisma, BullMQ, Vite). The human chose to keep the planned stack (FastAPI, Next.js, WhatsApp first), and the README was rewritten to match.
- What the agent did well: router and job auto-discovery, so later tasks never edit `main.py` or the worker settings; tests run on a separate `app_test` database with per-test rollback; it verified the worker end to end by enqueueing `job_ping`.
- What it got wrong and how it was caught: (1) `import app.api` clashed with the `app = FastAPI()` variable (caught by mypy); (2) `uvicorn --reload` watched `.venv` and kept reloading (caught by running the server; fixed with `--reload-dir app`); (3) arq logs were printed twice (caught by reading the worker output); (4) `@vitejs/plugin-react` had a peer-dependency conflict with the current Babel, so Vitest uses its built-in JSX transform instead.
- Notes for teammates: on Windows PowerShell, `npm` may be blocked by the execution policy. Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once or use `npm.cmd`. The scaffold uses Next.js 16, whose APIs differ from older versions; read `frontend/AGENTS.md`.
- Would I do it differently next time? Pin the frontend tool versions in the task prompt to avoid peer-dependency surprises.
