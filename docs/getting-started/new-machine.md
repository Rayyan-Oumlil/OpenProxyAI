# Continuing on a new machine

`git clone` brings all code, migrations, Compose files, tests and `CLAUDE.md`. It does not bring tools,
git-ignored files or built artifacts. Set those up as below.

## 1. Install
| Tool | Why |
|---|---|
| Git | clone |
| Docker Desktop | Postgres 16 + pgvector, Redis, demo stack |
| Python 3.11 | backend (matches `backend/Dockerfile`) |
| Node.js 20 LTS | `admin-console/` (matches its Dockerfile) and `web-app/` |
| Claude Code (optional) | AI-assisted work; read `CLAUDE.md` first |

## 2. Fastest check: the seeded demo (no secrets needed)
```bash
docker compose -f docker-compose.demo.yml up -d --build --wait api console
scripts/smoke.sh
```
Console: http://localhost:5173, login `admin@example.com` / `DemoPass123!`. The first build downloads images
and can be slow on a weak connection.

## 3. Real development setup
```bash
# backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env        # then fill in values; .env is git-ignored, never commit it
docker compose up -d        # from repo root: Postgres (port 5434) + Redis
alembic upgrade head
uvicorn app.main:app --reload --port 8000
pytest

# admin console
cd admin-console && npm ci && npm run dev      # http://localhost:5173
npm run typecheck && npm run lint && npm test
npx playwright install                          # browsers for e2e / recording
```
Do the same `npm ci` in `web-app/` if you work on it.

## 4. Not in git (carry over by hand)
- `backend/.env` real values (SECRET_KEY, provider keys, Stripe). Use a password manager, not GitHub.
- Database contents: the local DB starts empty; migrations recreate the schema, the demo seeds its own data.
- The walkthrough video: re-record with `npm run record:walkthrough` against a fresh demo stack
  (`docker compose -f docker-compose.demo.yml down -v` first).
- Claude Code user config (`~/.claude/`), if you want the same personal rules and memory.
- Local-only branches or stashes: check `git branch` and `git stash list` on the old machine before leaving.
