# USURPENT

A real-time, multiplayer snake game. The server is authoritative: it runs a
fixed-tick simulation and streams snapshots over WebSocket. Clients send only
a steering direction and render with local prediction/interpolation.

## Overview

USURPENT is a real-time multiplayer game where players steer a growing
serpent through a shared game space, eating food and avoiding other players'
trails. The backend simulation is the single source of truth; the frontend is
a thin renderer.

## Features

- **Real-time multiplayer gameplay** - players and AI bots share the same
  simulated world, broadcast over WebSocket at a fixed tick rate
- **Client-side prediction & interpolation** - smooth movement despite
  network latency, reconciled against authoritative server snapshots
- **Mouse-controlled steering** - snakes turn toward the mouse offset from
  screen center, with server-capped turn rate
- **Accounts** - optional registration/login; guests can play without one
- **Web-based** - runs entirely in the browser with no additional client
  software

## Technology Stack

### Backend
- **Python 3.12** - core language
- **Tornado** - async web framework, serves the HTTP API and the `/ws`
  WebSocket endpoint, and runs the authoritative game loop
- **Peewee + SQLite** - account storage
- **bcrypt** - password hashing

### Frontend
- **Vite + Svelte** - dev server and build tooling for the client
- **Canvas 2D** - game rendering, head-centered camera
- **JavaScript (ES6+)** - netcode (prediction/interpolation), UI

## Project Structure

```
usurpent/
├── usurpent.py          # Tornado app: World (sim), Player, GameWebSocketHandler (/ws), App
├── config.py             # Gameplay tuning knobs (USURPENT_* env-overridable, no magic numbers)
├── protocol.py            # WebSocket message types and field names
├── db.py                  # Peewee SqliteDatabase + init_db()
├── models.py               # Account model (bcrypt password helpers)
├── bots.py                  # AI bot behaviors
├── requirements.txt          # Python dependencies (runtime only)
├── Makefile                   # Backend build/dev commands (Unix-style paths)
├── web/                        # Vite + Svelte frontend
│   ├── src/
│   │   ├── App.svelte
│   │   └── lib/
│   │       ├── Lobby.svelte     # Name entry / auth screen
│   │       ├── Auth.svelte      # Login / register forms
│   │       ├── Game.svelte      # Canvas renderer
│   │       ├── netcode.js       # Prediction/interpolation
│   │       └── api.js           # HTTP API client
│   └── dist/                    # Production build output (gitignored)
├── templates/ + static/game.js  # Retired vanilla D3 client (historical reference only)
└── README.md
```

## Installation & Setup

### Prerequisites
- Python 3.12
- Node.js (for the frontend)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/japherwocky/usurpent.git
   cd usurpent
   ```

2. **Set up the backend environment**
   ```bash
   python3 -m venv ./env
   ./env/bin/pip install -r requirements.txt   # Windows: ./env/Scripts/pip.exe
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # generate a real cookie secret:
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

4. **Run the backend**
   ```bash
   ./env/bin/python usurpent.py --debug   # Windows: ./env/Scripts/python.exe
   ```
   Starts on `http://localhost:55555` (override with `--port` or `PORT` in `.env`).

5. **Run the frontend (separate terminal)**
   ```bash
   cd web
   npm install
   npm run dev
   ```
   Vite serves the app and proxies `/api` and `/ws` to the backend. Open the
   URL Vite prints (typically `http://localhost:5173`).

### Production build

```bash
cd web && npm run build   # writes web/dist
cd .. && ./env/bin/python usurpent.py
```
Tornado serves `web/dist` directly, with an `index.html` fallback for client
routes - no separate frontend server needed.

## Usage

1. Start the backend and frontend dev server as described above
2. Open the Vite dev URL and pick a name (or leave it blank for a random one)
3. Click **PLAY**
4. Move your mouse to steer; click and hold (or hold Shift) to boost
5. Watch your score top-left and the leaderboard top-right
6. Right-click (or press `L`) for the stats panel and the bot-strategy legend
7. When you die, the card shows the score of that life; click **RESPAWN** to
   go again

## Game Mechanics

- **Steering**: the server caps turn rate, so trails curve smoothly rather
  than snapping to the cursor
- **Collision**: head-vs-other-body kills; your own tail is ignored. The
  hit distance is the two serpents' girths added, so bigger snakes are both
  bulkier and easier to clip — tune via `BASE_GIRTH` / `GIRTH_PER_FOOD` /
  `MAX_GIRTH` in `config.py`. Touching a world border also kills
- **Score**: food pickups increment score; resets on respawn, not on death,
  so the death card can show what the life you just lost was worth
- **Respawn**: bots come back on a `RESPAWN_DELAY` timer; a human stays dead
  until they click **RESPAWN**, which the server honours once the same delay
  has passed. A dead serpent ships no body -- its remains are already on the
  map as carcass pellets, and a corpse cannot kill anyone
- **Pellet gravity**: loose food drifts toward nearby food and merges on
  contact, so a scattered carcass slowly gathers into a few fat blobs. Merging
  conserves value exactly, so a blob is worth what its crumbs were
- **Simulation**: the server runs a fixed-tick loop at 20 Hz and sends each
  client the slice of the world it can see; the client interpolates between
  snapshots and predicts its own serpent locally

## Development

### Available commands (backend, from `Makefile`)

- `make init` - set up the Python virtualenv and install dependencies
- `make dev` - run the backend with debug mode enabled
- `make demo` - run the backend in production mode
- `make clean` - remove the virtualenv

The Makefile assumes a Unix-style venv layout (`./env/bin/...`). On Windows,
run the equivalent commands directly against `./env/Scripts/python.exe`.

### Frontend commands (from `web/`)

- `npm run dev` - Vite dev server with HMR, proxying `/api` and `/ws` to the
  backend
- `npm run build` - production build to `web/dist`
- `npm run preview` - preview the production build locally

### Configuration

Gameplay constants live in `config.py` and are overridable via `USURPENT_*`
environment variables - no magic numbers elsewhere in the codebase.

Server-level config comes from `.env` (copy `.env.example` to start):

- `COOKIE_SECRET` - session cookie signing key
- `PORT` - backend port (default 55555)
- `DEBUG` - enable Tornado debug mode / autoreload

## HTTP API (auth)

- `POST /api/register` - `{username, password, email?}` → `{ok, username}`
- `POST /api/login` - `{username, password}` → `{ok, username}`
- `POST /api/logout` - clears the session
- `GET /api/me` - `{guest: true}` or `{guest: false, username, high_score, games_played}`

Auth uses Tornado secure cookies plus XSRF protection. Errors are JSON
(`{"error": "..."}`) with a matching status code.

## Contributing

This is an active solo side project. Current areas for improvement:

1. **Game modes** - different gameplay variations (not yet built)
2. **Performance** - snapshots are already cut to each client's viewport, so
   payload tracks the view rather than the map. The remaining wins are delta
   compression (snapshots are still full-state *within* the viewport) and
   culling distant players the way food already is
3. **Mobile support** - touch controls (not yet built)
4. **Tests** - no automated test suite yet

See `AGENTS.md` for conventions and the kanban board used to track work.

## License

No explicit license is provided. Please contact the original author for
usage permissions.

## Author

Created by Japherwocky.
