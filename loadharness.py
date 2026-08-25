"""Load harness: drive bot strategies as real WebSocket clients (kanban #240).

Connects N headless clients to /ws -- the same endpoint a browser hits -- runs
the server's own bot strategies (bots.py) against each client's LOCAL view of
the world, and reports aggregate stats: connect time, snapshot rate/latency,
drop rate, inputs sent.

Why this exists: every other benchmark on this board is a simulation (fake
World, fake handlers). Bots hitting the actual /ws endpoint over real sockets
is the only way to learn what N genuine connections cost end to end, including
Tornado's own per-connection overhead and the broadcast cost that scales with
connected players -- the thing #238/#174/#239 were meant to tame.

Bots don't render, so pin --view low (400). At full view (1200) a client costs
~4x more per tick, which would skew the very numbers we are measuring.

Run the server first (usurpent.py), then:
  ./env/Scripts/python.exe loadharness.py --clients 50 --view 400 --duration 30

The harness reuses protocol.FIELD_* and wire.decode_snapshot so it speaks the
exact wire format the server emits -- no hand-rolled message shapes.
"""

import argparse
import asyncio
import json
import math
import time

import tornado.ioloop
from tornado.websocket import websocket_connect

import bots
import config
import protocol
import wire


class _PlayerShim:
    """Minimal stand-in for a serpent, good enough for the bot strategies."""

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.alive = True
        self.points: list[tuple[float, float]] | None = None
        self.target = (0.0, 0.0)

    def set_target(self, dx, dy):
        self.target = (dx, dy)


class _WorldShim:
    """Exposes just the bits bots.py reads: .foods and .players."""

    def __init__(self, client):
        self._c = client

    @property
    def foods(self):
        return self._c.foods

    @property
    def players(self):
        return self._c.players


class BotClient:
    """One headless WebSocket client running a bot strategy locally."""

    def __init__(self, idx, url, strategy):
        self.idx = idx
        self.url = url
        self.strategy = strategy
        self.conn = None
        self.self_id = None
        self.map_w = config.MAP_WIDTH
        self.map_h = config.MAP_HEIGHT
        self.max_girth = config.MAX_GIRTH
        self.food_max_r = config.FOOD_MERGE_MAX_RADIUS
        self.foods = {}
        self.players = {}
        self.bot_shim = _PlayerShim()
        self.world_shim = _WorldShim(self)
        self.connected = False
        self.connect_start = None
        self.connect_time = None
        self.snap_count = 0
        self.last_snap_t = None
        self.intervals = []
        self.drops = 0
        self.inputs_sent = 0

    async def connect(self):
        self.connect_start = time.monotonic()
        try:
            self.conn = await websocket_connect(self.url)
        except Exception:
            return
        msg = await self.conn.read_message()
        if msg is None or not isinstance(msg, str):
            return
        self.on_welcome(json.loads(msg))
        self.connected = True
        self.connect_time = time.monotonic() - self.connect_start
        asyncio.ensure_future(self._read())

    def on_welcome(self, welcome):
        self.self_id = welcome[protocol.FIELD_SELF_ID]
        if welcome.get(protocol.FIELD_MAP_WIDTH):
            self.map_w = welcome[protocol.FIELD_MAP_WIDTH]
        if welcome.get(protocol.FIELD_MAP_HEIGHT):
            self.map_h = welcome[protocol.FIELD_MAP_HEIGHT]
        if welcome.get(protocol.FIELD_MAX_GIRTH):
            self.max_girth = welcome[protocol.FIELD_MAX_GIRTH]
        if welcome.get(protocol.FIELD_FOOD_MAX_RADIUS):
            self.food_max_r = welcome[protocol.FIELD_FOOD_MAX_RADIUS]
        for p in welcome.get(protocol.FIELD_PLAYERS, []):
            self._upsert_player(p)
        self._apply_food(welcome.get(protocol.FIELD_FOOD, {}))

    async def _read(self):
        while self.conn is not None:
            msg = await self.conn.read_message()
            if msg is None:
                self.connected = False
                return
            if isinstance(msg, bytes):
                self.on_snapshot_binary(msg)
            # welcome/leaderboard text: welcome already handled; leaderboard
            # carries no state the brain needs, so ignore it.

    def on_snapshot_binary(self, buf):
        now = time.monotonic()
        if self.last_snap_t is not None:
            gap = now - self.last_snap_t
            self.intervals.append(gap)
            if gap > 2.0 / config.TICK_HZ:
                self.drops += 1
        self.last_snap_t = now
        self.snap_count += 1
        snap = wire.decode_snapshot(buf, self.map_w, self.map_h,
                                    self.max_girth, self.food_max_r)
        for p in snap[protocol.FIELD_PLAYERS]:
            self._upsert_player(p)
        self._apply_food(snap[protocol.FIELD_FOOD])

    def _upsert_player(self, p):
        pid = p[protocol.FIELD_ID]
        # The self serpent IS the bot shim, so _avoid_bodies (which skips
        # `other is bot`) correctly ignores its own body, matching in-process.
        if pid == self.self_id:
            shim = self.bot_shim
        else:
            shim = self.players.get(pid)
            if shim is None:
                shim = _PlayerShim()
        shim.x = p[protocol.FIELD_X]
        shim.y = p[protocol.FIELD_Y]
        shim.alive = p[protocol.FIELD_ALIVE]
        if protocol.FIELD_POINTS in p:
            shim.points = [tuple(pt) for pt in p[protocol.FIELD_POINTS]]
        else:
            drop = p.get(protocol.FIELD_POINTS_DROP, 0)
            add = p.get(protocol.FIELD_POINTS_ADD, [])
            if shim.points is None:
                shim.points = []
            elif drop:
                shim.points = shim.points[drop:]
            shim.points = shim.points + [tuple(pt) for pt in add]
        self.players[pid] = shim

    def _apply_food(self, food):
        for f in food.get(protocol.FIELD_FOOD_ADD, []):
            self.foods[f[protocol.FIELD_ID]] = f
        for f in food.get(protocol.FIELD_FOOD_MOVE, []):
            self.foods[f[protocol.FIELD_ID]] = f
        for fid in food.get(protocol.FIELD_FOOD_REMOVE, []):
            self.foods.pop(fid, None)

    def think_and_send(self):
        if not self.connected or self.conn is None:
            return
        me = self.players.get(self.self_id)
        if me is None or not me.alive:
            return
        self.bot_shim.x = me.x
        self.bot_shim.y = me.y
        self.bot_shim.alive = me.alive
        self.strategy.think(self.world_shim, self.bot_shim)
        dx, dy = self.bot_shim.target
        out = {
            protocol.FIELD_TYPE: protocol.TYPE_INPUT,
            protocol.FIELD_TARGET: {protocol.FIELD_X: dx, protocol.FIELD_Y: dy},
        }
        self.conn.write_message(json.dumps(out))
        self.inputs_sent += 1


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    ap = argparse.ArgumentParser(description="USURPENT bot load harness (#240)")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=55555)
    ap.add_argument("--clients", type=int, default=20,
                    help="number of WebSocket clients to spawn")
    ap.add_argument("--view", type=int, default=400,
                    help="view radius to request (keep low; bots don't render)")
    ap.add_argument("--duration", type=int, default=20,
                    help="seconds to run before reporting")
    ap.add_argument("--strategy", default=None,
                    help="force one strategy (seeker/wanderer); "
                         "default round-robins REGISTRY")
    args = ap.parse_args()

    loop = tornado.ioloop.IOLoop.current()
    clients = []
    for i in range(args.clients):
        if args.strategy:
            cls = next((c for c in bots.REGISTRY if c.name == args.strategy),
                       bots.REGISTRY[0])
        else:
            cls = bots.REGISTRY[i % len(bots.REGISTRY)]
        url = (f"ws://{args.host}:{args.port}/ws"
               f"?view={args.view}&name=bot{i}")
        clients.append(BotClient(i, url, cls()))

    loop.run_sync(
        lambda: asyncio.gather(*(c.connect() for c in clients)))

    connected = [c for c in clients if c.connected]
    print(f"connected {len(connected)}/{len(clients)} clients "
          f"(view={args.view}, duration={args.duration}s)")

    def tick_all():
        for c in clients:
            c.think_and_send()

    pc = tornado.ioloop.PeriodicCallback(tick_all, 1000.0 / config.TICK_HZ)
    pc.start()

    def stop():
        pc.stop()
        loop.stop()

    loop.call_later(args.duration, stop)
    loop.start()

    # --- report -------------------------------------------------------------
    connect_times = [c.connect_time for c in connected if c.connect_time]
    all_intervals = [g for c in connected for g in c.intervals]
    total_snaps = sum(c.snap_count for c in clients)
    total_drops = sum(c.drops for c in clients)
    total_inputs = sum(c.inputs_sent for c in clients)
    expected_per_client = args.duration * config.TICK_HZ

    print("--- load harness report ---")
    print(f"clients requested : {len(clients)}")
    print(f"clients connected : {len(connected)}")
    if connect_times:
        print(f"connect time (ms) : "
              f"avg {_mean(connect_times)*1000:.1f}  "
              f"min {min(connect_times)*1000:.1f}  "
              f"max {max(connect_times)*1000:.1f}")
    print(f"snapshots total   : {total_snaps} "
          f"(~{total_snaps/max(1,args.duration):.0f}/s across all clients)")
    if connected:
        per = total_snaps / len(connected) / max(1, args.duration)
        print(f"snapshots/client  : ~{per:.1f}/s "
              f"(expected {config.TICK_HZ}/s)")
    if all_intervals:
        print(f"snapshot gap (ms) : avg {_mean(all_intervals)*1000:.1f}  "
              f"min {min(all_intervals)*1000:.1f}  "
              f"max {max(all_intervals)*1000:.1f}")
    print(f"snapshot drops    : {total_drops} "
          f"(gaps > 2x expected interval)")
    print(f"inputs sent       : {total_inputs} "
          f"(~{total_inputs/max(1,args.duration):.0f}/s)")
    print("---------------------------")


if __name__ == "__main__":
    main()
