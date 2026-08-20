# AGENTS.md

Guidance for AI coding agents working on USURPENT.

## What this is

USURPENT is a real-time, multiplayer snake game. The server is authoritative:
it runs a fixed-tick simulation and streams snapshots over WebSocket. Clients
send only a mouse-target and render with local prediction/interpolation.

Stack: Python 3.12 + Tornado (WebSocket server), Peewee + SQLite for accounts,
vanilla JS + D3 on the client (being ported to Vite + Svelte — see board).

## Project layout

- `usurpent.py` — Tornado app. `World` (authoritative sim), `Player` (snake
  state), `GameWebSocketHandler` (`/ws`), `App` (settings + `world` + `init_db`).
- `config.py` — All gameplay constants. Overridable via `USURPENT_*` env vars.
  No magic numbers elsewhere; import from here.
- `protocol.py` — WebSocket message types and field names.
- `db.py` — Peewee `SqliteDatabase` + `init_db()` (creates tables; called from
  `App.__init__`).
- `models.py` — `Account` model (registered players) with bcrypt password helpers.
- `templates/index.html` — Game entry page (vanilla, D3 from CDN).
- `templates/legacy.html` — Dead doc renderer; retire during the frontend port.
- `static/game.js` — Vanilla JS client (D3, WebSocket, prediction/interpolation).
- `static/netcodedemo.html` — Standalone netcode teaching demo.
- `pyrightconfig.json` — Points pyright at the venv (`venvPath`/`venv`). Do not
  set `pythonPath` there; it is not a valid pyright setting.
- `requirements.txt` — Runtime deps only.
- `env/` — Python 3.12.4 virtualenv. Run it directly:
  `./env/Scripts/python.exe`, `./env/Scripts/pip.exe`, `./env/Scripts/kanban.exe`.

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
