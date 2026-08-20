# AGENTS.md

Guidance for AI coding agents working on USURPENT.

## What this is

USURPENT is a real-time, multiplayer snake game. The server is authoritative:
it runs a fixed-tick simulation and streams snapshots over WebSocket. Clients
send only a mouse-target and render with local prediction/interpolation.

Stack: Python 3.12 + Tornado (WebSocket server), Peewee + SQLite for accounts,
Vite + Svelte on the client (game renderer in `web/src/lib/Game.svelte`, netcode
in `web/src/lib/netcode.js`; Canvas 2D, head-centered camera, same
prediction/interpolation as the old D3 client). Clients send a steering
direction (mouse offset from screen center), not a world target.

## Project layout

- `usurpent.py` — Tornado app. `World` (authoritative sim), `Player` (snake
  state), `GameWebSocketHandler` (`/ws`), `App` (settings + `world` + `init_db`).
- `config.py` — All gameplay constants. Overridable via `USURPENT_*` env vars.
  No magic numbers elsewhere; import from here.
- `protocol.py` — WebSocket message types and field names.
- `db.py` — Peewee `SqliteDatabase` + `init_db()` (creates tables; called from
  `App.__init__`).
- `models.py` — `Account` model (registered players) with bcrypt password helpers.
- `web/` — Vite + Svelte frontend. Source in `web/src`, built to `web/dist`
  (gitignored). Tornado serves `web/dist` in production; Vite serves it and
  proxies `/ws` to the backend in development.
- `templates/` + `static/game.js` — Retired vanilla D3 client and entry page.
  The renderer was ported to Svelte in #182; these remain only as historical
  reference and are no longer served.
- `static/netcodedemo.html` — Standalone netcode teaching demo.
- `pyrightconfig.json` — Points pyright at the venv (`venvPath`/`venv`). Do not
  set `pythonPath` there; it is not a valid pyright setting.
- `requirements.txt` — Runtime deps only.
- `env/` — Python 3.12.4 virtualenv. Run it directly:
  `./env/Scripts/python.exe`, `./env/Scripts/pip.exe`, `./env/Scripts/kanban.exe`.

## Frontend (web/)

The client is a Vite + Svelte app in `web/`.

- Develop: `cd web && npm install && npm run dev`. Vite serves the app on its
  dev port and proxies `/ws` (and `/api`) to the Tornado server (default
  `http://localhost:8011`).
- Ship: `cd web && npm run build` writes `web/dist`; run `usurpent.py` and
  Tornado serves `web/dist` with an `index.html` fallback for client routes.

Keep gameplay/behavior constants server-side in `config.py`; the client only
renders what the server sends.

## HTTP API (auth)

Auth uses Tornado secure cookies (`user` = signed account id) plus XSRF
protection (`xsrf_cookies=True`). The SPA must read the `_xsrf` cookie set on
any GET and echo it in the `X-XSRFToken` header on every API POST.

- `POST /api/register` — body `{username, password, email?}` → `{ok, username}`.
  Username 3-32 chars `[A-Za-z0-9_-]`; password >= 8 chars; email optional.
- `POST /api/login` — body `{username, password}` → `{ok, username}`.
- `POST /api/logout` — clears the session.
- `GET /api/me` — `{guest: true}` or `{guest: false, username, high_score, games_played}`.

Errors are JSON: `{"error": "..."}` with a matching status code (400/401/409/429).
Anonymous guests play without a session. The WebSocket (`/ws`) reads the same
signed `user` cookie on connect: if present it binds the snake to that
`Account` (and the welcome message reports `guest: false` + `username`); if
absent the connection is an anonymous guest (`guest: true`). No separate WS
token is used.

## Kanban board (planning artifact)

The board is the live backlog. `PLAN.md` was deleted on purpose — plan here,
not in a markdown file.

- Tool: `pkanban` (pip package; the CLI command is `kanban`, not `pkanban`).
  Already installed in the venv.
- Host: `https://kanban.pearachute.com`. Auth is already set up in
  `~/.kanban.yaml`; the CLI works without re-login.
- Board: **"usurpent", ID 10**.
- Columns: **Backlog (29), To Do (30), In Progress (31), Done (32)**.

Useful commands (run from the venv, e.g. `./env/Scripts/kanban.exe ...`):

- `kanban board get 10` — view the whole board.
- `kanban card create --column 29 --title "..." --body "..."` — add a card.
- `kanban card move <id> --column <col>` — move a card between columns.
- `kanban card move <id> --position <n>` — reorder within a column.

Ordering note: `board get` lists cards by ID, but the web UI sorts by
`position` (new cards default to 0). Use `card move <id> --position <n>` to
control the visible order when sequence matters (e.g. scaffold-before-feature).

Workflow: keep cards moving Backlog → To Do → In Progress → Done as you work.
When you start a card, move it to In Progress; when the code is committed, move
it to Done.

## Conventions

- Commit to `main` directly. No branches, no PRs, no CI — it is just us.
- Keep gameplay/behavior constants in `config.py` with a `USURPENT_` env override.
- Run the type checker with the venv's pyright; it should report 0 errors.
