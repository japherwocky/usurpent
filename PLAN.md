# USURPENT Plan

## Where we are

- **Phase 1 & 2**: Complete (Python 3, Tornado 6, security headers, env config).
- **Current state**: Single-player visual demo. Server serves `index.html` + `game.js`, plus a markdown doc handler under `/docs/*`. No real networking between players despite the README claims — `game.js` runs purely client-side and `netcodedemo.html` is a standalone teaching file.
- **Goal of this plan**: Figure out what we actually want to ship next. We're starting that conversation, not promising dates.

## What's done (don't re-litigate)

- Python 2 → 3 migration, Tornado API modernization.
- `requirements.txt` pinned (`tornado>=6.5.0`, `markdown>=3.8.0`, `python-dotenv`).
- Security headers + path-traversal hardening in `DocHandler`.
- Cookie secret via env var.
- `.env` / `.env.example` workflow.

## What's still loose ends (small, do opportunistically)

- No tests anywhere — `tests/` is referenced but doesn't exist. Even a smoke test for `usurpent.py` startup + doc route would help.
- `README.md` overpromises "real-time multiplayer" and claims a "Network Architecture" demo. README should match reality.
- No license file.
- `Makefile` uses `./env/bin/...` paths that don't exist on Windows (venv uses `Scripts/`). Either make it cross-platform or document Windows commands.

## Phase 3 — MVP: one shared map with snake mechanics ✅ COMPLETE

**Scope**: a single shared map. Players join via WebSocket, move on the map, grow tails, collide. No rooms, no lobby, no accounts, no persistence. Server is authoritative; clients predict and reconcile.

**Status**: Built and verified end-to-end (food seed, pickup/growth, collision death, respawn, food restock all confirmed against a running server). Code lives in `config.py`, `protocol.py`, `usurpent.py` (`World`/`Player`/`GameWebSocketHandler`), and `static/game.js`.

### Server (`usurpent.py`)

- `GameWebSocketHandler` (Tornado `WebSocketHandler`).
- One `World` instance holding players + their tails, ticked at 20 Hz.
- Player input = target direction (or mouse target — decide during build).
- Server simulates: position, tail growth on food pickup, head-vs-tail collisions, head-vs-head collisions.
- On connect: assign id, spawn at free spot, send `welcome` with current world snapshot.
- On disconnect: remove player, broadcast updated snapshot.
- Broadcast: full snapshot per tick is fine at MVP scale (< 20 players).

### Protocol (JSON over WS)

- Client → server: `{ "type": "input", "target": {x, y} }` (mouse target in logical map coords).
- Server → client: `{ "type": "welcome", "self_id": "...", "world": {...} }` on connect.
- Server → client: `{ "type": "snapshot", "tick": N, "players": [...] }` at ~20 Hz.
- Keep it boring. No delta compression, no binary, in MVP.

### Client (`static/game.js`)

- Open WS, render server-authoritative positions (drop the mouse-follow physics for *other* players; keep it for self-prediction).
- Client-side prediction: move self locally on input, reconcile against snapshot.
- Interpolate other players between snapshots.
- Render tails as polylines, head as circle (reuse the existing circle styling).
- Food: small dots, one type, respawn on pickup.

### Collisions (MVP rule set)

- Head vs. own tail: ignore (you can't kill yourself on your own trail in MVP — revisit later).
- Head vs. any other player's body: death. Snake resets.
- Head vs. food: grow by N segments, score++.
- Out-of-bounds: clamp to map edges.

### Out of scope for MVP (explicitly)

- Multiple rooms / lobbies.
- Accounts, persistence, leaderboards.
- Power-ups, varied food, obstacles.
- Mobile/touch.
- Anti-cheat beyond server authority.

### Open questions to settle before coding

- ~~**Input model**: absolute mouse target vs. discrete direction.~~ **Decided: mouse target.** Player sets a target point; the head steers toward it. Smooth curves, circular motion, and the existing demo UX carries over. Tradeoff: "snake" is more aesthetic than arcade — collisions matter less because you can't dart sharply. We'll lean into that — make trails long and curvy, collisions about positioning rather than twitch.

### Tuning knobs (defaults picked, all configurable)

No magic numbers. Gameplay constants live in one module so they can be overridden by env vars or a config file later.

| Knob | Default | Why |
|---|---|---|
| `MAP_WIDTH`, `MAP_HEIGHT` | `1000, 1000` | Logical units, scaled to viewport. Square keeps the math simple for MVP. |
| `TICK_HZ` | `20` | Server tick rate. 20 Hz is plenty for mouse-target steering; client interpolates between snapshots. |
| `HEAD_SPEED` | `120` (units/sec) | Fast enough to feel responsive, slow enough that collisions are readable. |
| `MAX_TURN_RATE` | `6.0` (rad/sec) | Caps how fast the head can rotate. Prevents mouse-flick 180°s that skip the trail. |
| `TAIL_SEGMENT_SPACING` | `8` (units) | Distance between tail joints. Smaller = denser trail. |
| `INITIAL_TAIL_LENGTH` | `20` | Starting segments. |
| `FOOD_GROWTH` | `5` | Segments added per food pickup. |
| `FOOD_COUNT` | `30` | Food on the map at any time. |
| `RESPAWN_DELAY` | `1.5` (sec) | Short enough to not be annoying, long enough to register a death. |

These get loaded from env (e.g. `USURPENT_MAP_WIDTH=1500`) with the defaults above as fallback. No edits to source to tune feel — just restart with new env vars.

### Concrete first steps

1. ✅ Add `WebSocketHandler` skeleton + connect/disconnect logging.
2. ✅ Define the JSON protocol constants in one place.
3. ✅ World class with a tick loop (start with one player, broadcast to itself, log it).
4. ✅ Hook client WS, replace mouse-follow with server-driven position.
5. ✅ Add tail growth + food.
6. ✅ Add collisions + death/respawn.

### Deferred from the original client plan

- **Client-side prediction for self** and **true interpolation for others**: the client currently renders server snapshots directly, gliding between them with 50 ms D3 transitions. Good enough at 20 Hz; add prediction/reconciliation if motion feels laggy.
- **`world` field in welcome**: welcome carries `players` + `food` directly (no nested `world` wrapper). Minor wire-format difference from the early sketch.

## Risks

- Tornado's `WebSocketHandler` is fine but undocumented-for-games; we'll be inventing patterns.
- No persistence means restarts wipe state — fine for MVP, document it.
- CSP currently allows `'unsafe-inline'` for scripts — we'll need to clean that up if we add a WebSocket client that doesn't need inline JS, but for MVP it's tolerable.

## What's next (post-MVP, not started)

- README still claims "single-player only" in Contributing — update it; multiplayer now works.
- A smoke test in `tests/` (server boot + WS connect + one tick) so CI has a floor.
- Client-side prediction / interpolation if feel demands it.
- Rooms/lobbies, accounts, persistence, leaderboards, mobile/touch — all explicitly out of MVP scope.

## Next concrete step

Settle the remaining open questions (map size, growth rate, death feedback, max turn rate). Then I start with step 1: the WebSocket handler skeleton.
