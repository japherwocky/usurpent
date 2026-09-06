"""End-to-end smoke test: boot the server, play a tick (kanban #170).

The other tests in here exercise pieces of the pipeline against a World built
by hand. This one is the cheap guard the pieces cannot give you: it starts a
real Tornado server, opens a real WebSocket, and proves a client can connect,
get a welcome, and receive snapshots that decode -- the sim loop, the handler,
the wire format and the tick callback all wired together.

It runs against a throwaway SQLite file so a test run never touches the
development database.

Run directly:  ./env/Scripts/python.exe tests/test_smoke_ws.py
"""

import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point at a scratch database BEFORE config is imported -- config reads the
# path at import time, and db.py binds its SqliteDatabase from it.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="usurpent-smoke-", suffix=".db")
os.close(_DB_FD)
os.environ["USURPENT_DATABASE_PATH"] = _DB_PATH

import tornado.httpserver
from tornado.testing import bind_unused_port
from tornado.websocket import websocket_connect

import config
import protocol
import usurpent
import wire

# A tick is 1/TICK_HZ; give every read many ticks of headroom so a slow
# machine reports a real failure rather than a timeout.
READ_TIMEOUT = max(5.0, 20.0 / config.TICK_HZ)


async def read_message(conn, what):
    """Read one frame, failing loudly instead of hanging forever."""
    try:
        msg = await asyncio.wait_for(conn.read_message(), READ_TIMEOUT)
    except asyncio.TimeoutError:
        return None, f"timed out after {READ_TIMEOUT:.1f}s waiting for {what}"
    if msg is None:
        return None, f"connection closed while waiting for {what}"
    return msg, None


def check_welcome(welcome):
    """The welcome has to carry everything a client needs to decode snapshots.

    decode_snapshot dequantizes against map size, max girth and food radius, so
    a welcome missing any of them yields a client that renders garbage.
    """
    required = [
        protocol.FIELD_SELF_ID,
        protocol.FIELD_MAP_WIDTH,
        protocol.FIELD_MAP_HEIGHT,
        protocol.FIELD_MAX_GIRTH,
        protocol.FIELD_FOOD_MAX_RADIUS,
    ]
    missing = [f for f in required if not welcome.get(f)]
    if missing:
        return f"welcome missing fields: {missing}"
    if not isinstance(welcome.get(protocol.FIELD_PLAYERS), list):
        return "welcome has no players list"
    # The welcome sends food as an all-adds delta; the client starts empty.
    food = welcome.get(protocol.FIELD_FOOD)
    if not isinstance(food, dict):
        return "welcome has no food block"
    return None


async def play_a_tick():
    app = usurpent.App(debug=True)
    sock, port = bind_unused_port()
    server = tornado.httpserver.HTTPServer(app)
    server.add_sockets([sock])
    conn = None
    try:
        url = f"ws://127.0.0.1:{port}/ws?name=smoketest"
        conn = await websocket_connect(url)

        msg, err = await read_message(conn, "welcome")
        if err:
            return err
        if not isinstance(msg, str):
            return f"welcome should be text JSON, got {type(msg).__name__}"
        welcome = json.loads(msg)
        err = check_welcome(welcome)
        if err:
            return err
        self_id = welcome[protocol.FIELD_SELF_ID]

        # Steer somewhere, the way a client does, so the input path is covered
        # too. Nothing is asserted about where the serpent ends up -- only that
        # the server keeps ticking after being told something.
        conn.write_message(json.dumps({
            protocol.FIELD_TYPE: protocol.TYPE_INPUT,
            protocol.FIELD_TARGET: {protocol.FIELD_X: 1.0, protocol.FIELD_Y: 0.0},
        }))

        # Snapshots are binary; leaderboard frames are text and interleave, so
        # read until two snapshots land. Two, not one, because a single frame
        # would not prove the tick callback is still running after the first.
        snapshots = 0
        seen_self = False
        while snapshots < 2:
            msg, err = await read_message(conn, "snapshot")
            if err:
                return err
            if not isinstance(msg, bytes):
                continue  # leaderboard or other text frame
            snap = wire.decode_snapshot(
                msg,
                welcome[protocol.FIELD_MAP_WIDTH],
                welcome[protocol.FIELD_MAP_HEIGHT],
                welcome[protocol.FIELD_MAX_GIRTH],
                welcome[protocol.FIELD_FOOD_MAX_RADIUS],
            )
            snapshots += 1
            for p in snap[protocol.FIELD_PLAYERS]:
                if p[protocol.FIELD_ID] == self_id:
                    seen_self = True
            if protocol.FIELD_FOOD not in snap:
                return f"snapshot {snapshots} carries no food block"

        if not seen_self:
            return "our own serpent never appeared in a snapshot"

        # Disconnecting has to retire the player, or the world leaks serpents
        # for every client that has ever connected.
        conn.close()
        conn = None
        for _ in range(int(READ_TIMEOUT * config.TICK_HZ)):
            await asyncio.sleep(1.0 / config.TICK_HZ)
            if self_id not in app.get_world("classic").players:
                break
        else:
            return "player was not removed from the world after close"
        return None
    finally:
        if conn is not None:
            conn.close()
        app.stop_worlds()
        server.stop()


def main():
    try:
        err = asyncio.run(play_a_tick())
    finally:
        try:
            os.unlink(_DB_PATH)
        except OSError:
            pass
    if err:
        print("FAIL smoke:", err)
        return 1
    print("OK: server boots, client connects, welcome is complete, snapshots "
          "decode, and the player retires on disconnect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
