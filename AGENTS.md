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
- `bots.py` — AI snake strategies. Each is a class with `think(world, bot)`;
  add one to `REGISTRY` and the world spawns it round-robin.
- `carcass.py` — Scatter patterns for a dead snake's pellets. Each is a
  `scatter(points, spread) -> [(x, y), ...]` function; add one to `REGISTRY`
  and deaths start picking it at random.
- `web/` — Vite + Svelte frontend. Source in `web/src`, built to `web/dist`
  (gitignored). Tornado serves `web/dist` in production; Vite serves it and
  proxies `/ws` to the backend in development.
- `templates/` + `static/game.js` — Retired vanilla D3 client and entry page.
  The renderer was ported to Svelte in #182; these remain only as historical
  reference and are no longer served.
- `pyrightconfig.json` — Points pyright at the venv (`venvPath`/`venv`). Do not
  set `pythonPath` there; it is not a valid pyright setting.
- `requirements.txt` — Runtime deps only.
- `env/` — Python 3.12.4 virtualenv. Run it directly:
  `./env/Scripts/python.exe`, `./env/Scripts/pip.exe`, `./env/Scripts/kanban.exe`.

## Frontend (web/)

The client is a Vite + Svelte app in `web/`.

- Develop: `cd web && npm install && npm run dev`. Vite serves the app on its
  dev port and proxies `/ws` (and `/api`) to the Tornado server (default
  `http://localhost:55555`).
- Ship: `cd web && npm run build` writes `web/dist`; run `usurpent.py` and
  Tornado serves `web/dist` with an `index.html` fallback for client routes.

Keep gameplay/behavior constants server-side in `config.py`; the client only
renders what the server sends.

Styling goes through the design tokens in `web/src/app.css` -- surfaces, ink,
accent, radii, shadow -- so the whole UI restyles from one place. Components
reference `var(--...)`, never literal colors. Two typefaces, and the split
matters: `--font-display` is Silkscreen, a caps-only bitmap face that renders
lowercase as uppercase glyphs, so it is for titles, buttons, numerals and
canvas labels only; body copy, form labels and hints use `--font-ui`. Putting
a sentence in the display face is how the old lobby ended up shouting its
form hints.

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

## Food and pellet gravity

The field is deliberately large — `FOOD_MAX` is 8000 — and what is kept small
is the slice each client is *sent*. Several invariants hold this up, and each
one was put there to fix a measured problem. Breaking any of them brings the
problem back, usually silently:

- **`FOOD_MAX` is global.** Anything that creates pellets goes through
  `World._make_room()` first. It evicts oldest-first and only evicts `dropped`
  crumbs, so spawned pellets (which mark the spawn circle) survive.
- **Merging conserves value exactly.** `_merge_food()` sums `value` and grows
  the radius by area, `sqrt(r1^2 + r2^2)`, capped at `FOOD_MERGE_MAX_RADIUS`.
  A blob is worth exactly what its crumbs were worth, so the score economy is
  unaffected by how much has clumped. A merged pellet stays `dropped` if
  either half was, so merging cannot launder crumbs past the cap.
- **Gravity reads a mass mesh, never individual neighbours.** Neighbour counts
  grow with density, so a per-neighbour scan is quadratic in field size — it
  measured 240 ms per tick at 50k pellets. `_attract_food()` instead reads nine
  per-cell centre-of-mass aggregates whatever the density, subtracting the
  pellet's own mass from its own cell. Reintroducing a pairwise scan will look
  fine at a thousand pellets and fall over at ten.
- **Both gravity passes are sharded** by `FOOD_GRAVITY_SHARDS`: a pellet is
  processed once every N ticks. The rota is stored on the pellet (`shard`) at
  creation rather than derived from its id, because `int(fid)` on every pellet
  every tick is real money at this field size. Drift steps are scaled by N, so
  sharding changes cost and not speed.
- **One walk of the food list per tick.** `_index_food()` builds the gravity
  mesh, the fine grid and the shard list in a single pass, because at this
  size walking the list is itself the expensive part. Don't add another walk.
- **The fine grid cell must cover the longest reach that queries it.**
  `_fine_cell()` derives it from the merge reach (which carries
  `FOOD_MERGE_OVERLAP`) and the pickup reach. A 3x3 block only guarantees one
  cell of coverage in each direction, so an undersized cell means a head can
  sit on a pellet and not eat it — no error, just a pellet that won't pick up.
  Retune `FOOD_MERGE_OVERLAP` or `FOOD_PICKUP_PAD` and this follows along.

Interest management is what lets the field be this big. `_broadcast_snapshot()`
sends each player only the food near them, so payload tracks the viewport
rather than the map. Clients report how much world they can show (`view`, on
the WS handshake and again on resize); the server clamps it between
`INTEREST_MIN_RADIUS` and `INTEREST_RADIUS` and adds `INTEREST_MARGIN`. This
costs the encode-once trick — snapshots differ per viewer now — which is a
good trade, but it does mean **snapshot cost scales with connected players**.

Note the ceiling is the map, not the server. A viewport covers 0.374% of
10000x10000; food concentrates inside `FOOD_SPAWN_RADIUS` rather than spreading
over the whole map, which roughly doubles it, so 8000 pellets reads as about
50 on screen. Raising `FOOD_MAX` past ~10000 runs out of tick budget before it
makes the screen look much busier — shrinking `MAP_WIDTH`/`MAP_HEIGHT` or
`FOOD_SPAWN_RADIUS` is the cheaper lever for density.

Measure before tuning. The budget is 50 ms at `TICK_HZ=20`; a populated map
with four players connected runs around 17 ms median and peaks near 30 ms.

## Conventions

- Commit to `main` directly. No branches, no PRs, no CI — it is just us.
- Keep gameplay/behavior constants in `config.py` with a `USURPENT_` env override.
- Run the type checker with the venv's pyright; it should report 0 errors.
