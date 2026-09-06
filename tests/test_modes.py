"""Mode foundation: one world per mode, lazily created, idle wind-down (#365).

Boots a real server with a second (stub) mode injected into the registry, then
proves the properties the mode system rests on:

  1. /api/modes serves the registry, so a client can render its buttons.
  2. Two modes are two worlds: separate player sets, and each mode supplies
     its own bot strategies (the stub spawns none).
  3. Two connections to the same mode land in the same world.
  4. An unknown mode is refused at the door with an error, not dropped into
     some other arena.
  5. Wind-down: when a world's last human leaves, its simulation pauses;
     the next join resumes it. Empty modes cost nothing.

It runs against a throwaway SQLite file so a test run never touches the
development database.

Run directly:  ./env/Scripts/python.exe tests/test_modes.py
"""

import asyncio
import json
import os
import sys
import tempfile
from typing import NoReturn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point at a scratch database BEFORE config is imported -- config reads the
# path at import time, and db.py binds its SqliteDatabase from it.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="usurpent-modes-", suffix=".db")
os.close(_DB_FD)
os.environ["USURPENT_DATABASE_PATH"] = _DB_PATH

import tornado.httpserver
from tornado.httpclient import AsyncHTTPClient
from tornado.testing import bind_unused_port
from tornado.websocket import WebSocketClientConnection, websocket_connect

import config
import modes
import protocol
import usurpent

READ_TIMEOUT = max(5.0, 20.0 / config.TICK_HZ)
# How long to wait for the wind-down (or any close-driven state change) to
# land. on_close is asynchronous; poll rather than sleep a fixed beat.
SETTLE_TIMEOUT = 5.0


class StubMode(modes.GameMode):
    """A second mode for the test, distinguishable from classic in two ways:
    no bots (its world's player list is exactly its humans) and its own id."""

    id = "stub"
    name = "Stub"
    description = "Test-only mode: classic rules, no bots."

    def bot_strategies(self):
        return []


def fail(what, detail) -> NoReturn:
    """A test helper's way of bailing: raise, and main() reports it."""
    raise AssertionError(f"{what}: {detail}")


async def read_text(conn: WebSocketClientConnection, what: str) -> dict:
    """Read one text frame, failing loudly instead of hanging forever."""
    try:
        msg = await asyncio.wait_for(conn.read_message(), READ_TIMEOUT)
    except asyncio.TimeoutError:
        fail(what, f"timed out after {READ_TIMEOUT:.1f}s")
    if msg is None:
        fail(what, "connection closed")
    if not isinstance(msg, str):
        fail(what, f"expected text JSON, got {type(msg).__name__}")
    return json.loads(msg)


async def connect_welcome(port, query):
    """Open a WS and read its welcome. Returns (conn, welcome dict)."""
    conn = await websocket_connect(f"ws://127.0.0.1:{port}/ws{query}")
    welcome = await read_text(conn, f"welcome ({query})")
    return conn, welcome


async def wait_for(predicate, what):
    """Poll a zero-arg predicate until true or the settle budget runs out."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + SETTLE_TIMEOUT
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(1.0 / config.TICK_HZ)
    fail("wind-down", f"timed out waiting for {what}")


async def run():
    # Injected before the App exists, so the registry scan in get_mode sees it.
    modes.REGISTRY.append(StubMode)

    app = usurpent.App(debug=True)
    sock, port = bind_unused_port()
    server = tornado.httpserver.HTTPServer(app)
    server.add_sockets([sock])
    conns = []
    try:
        # 1. /api/modes serves the registry with id, name and description.
        # The shipped modes are whatever REGISTRY holds by now (classic,
        # hardcore, ...); the test only demands the injected stub and classic
        # are both there, so adding a mode never breaks this test.
        resp = await AsyncHTTPClient().fetch(f"http://127.0.0.1:{port}/api/modes")
        listing = json.loads(resp.body)[protocol.FIELD_MODES]
        by_id = {m["id"]: m for m in listing}
        if not {"classic", "stub"} <= set(by_id):
            fail("/api/modes", f"served {sorted(by_id)}, expected classic+stub")
        for m in listing:
            if not m.get("name") or not m.get("description"):
                fail("/api/modes", f"entry missing name/description: {m}")

        # 2. Classic world: welcome names the mode and carries bots.
        a, welcome_a = await connect_welcome(port, "?mode=classic&name=A")
        conns.append(a)
        if welcome_a[protocol.FIELD_MODE] != "classic":
            fail("classic welcome", f"mode={welcome_a[protocol.FIELD_MODE]!r}")
        bots_a = [p for p in welcome_a[protocol.FIELD_PLAYERS]
                  if p[protocol.FIELD_IS_BOT]]
        if not bots_a:
            fail("classic world", "spawned no bots")

        # 3. Stub world: separate world, mode-owned strategies (none).
        b, welcome_b = await connect_welcome(port, "?mode=stub&name=B")
        conns.append(b)
        if welcome_b[protocol.FIELD_MODE] != "stub":
            fail("stub welcome", f"mode={welcome_b[protocol.FIELD_MODE]!r}")
        ids_b = {p[protocol.FIELD_ID] for p in welcome_b[protocol.FIELD_PLAYERS]}
        if ids_b != {welcome_b[protocol.FIELD_SELF_ID]}:
            fail("stub world", f"leaked players: {ids_b}")
        if welcome_a[protocol.FIELD_SELF_ID] in ids_b:
            fail("isolation", "player A appeared in the stub world")

        # 4. A second classic connection lands in the SAME world: it can see A.
        a2, welcome_a2 = await connect_welcome(port, "?mode=classic&name=A2")
        conns.append(a2)
        ids_a2 = {p[protocol.FIELD_ID] for p in welcome_a2[protocol.FIELD_PLAYERS]}
        if welcome_a[protocol.FIELD_SELF_ID] not in ids_a2:
            fail("same world", "two classic connections landed in different worlds")

        # 5. Unknown mode: refused with an error frame, then closed.
        bad = await websocket_connect(f"ws://127.0.0.1:{port}/ws?mode=nope")
        error = await read_text(bad, "error frame")
        if error.get(protocol.FIELD_TYPE) != protocol.TYPE_ERROR:
            fail("unknown mode", f"got {error.get(protocol.FIELD_TYPE)!r}, "
                                 "not an error frame")
        if "nope" not in error.get(protocol.FIELD_ERROR, ""):
            fail("error frame", f"does not name the bad mode: {error}")
        if await bad.read_message() is not None:
            # The server may need a beat to finish the closing handshake.
            await asyncio.sleep(0.2)
            if await bad.read_message() is not None:
                fail("unknown mode", "connection stayed open")

        # 6. Worlds exist exactly for the modes that have been joined.
        if set(app.worlds) != {"classic", "stub"}:
            fail("lazy worlds", f"app.worlds = {sorted(app.worlds)}")

        # 7. Wind-down: last human leaves -> simulation pauses.
        world_c = app.get_world("classic")
        world_s = app.get_world("stub")
        if not (world_c.is_ticking() and world_s.is_ticking()):
            fail("wind-down", "worlds should be ticking while humans are connected")
        for c in conns:
            c.close()
        conns = []
        await wait_for(lambda: not world_c.is_ticking(), "classic world pause")
        await wait_for(lambda: not world_s.is_ticking(), "stub world pause")

        # 8. The next join resumes the frozen world where it left off.
        r, _welcome_r = await connect_welcome(port, "?mode=classic&name=R")
        conns.append(r)
        if not world_c.is_ticking():
            fail("resume", "rejoining a wound-down world did not resume it")
    finally:
        for c in conns:
            c.close()
        app.stop_worlds()
        server.stop()


def main():
    try:
        asyncio.run(run())
    except AssertionError as e:
        print(f"FAIL modes: {e}")
        return 1
    finally:
        try:
            modes.REGISTRY.remove(StubMode)
        except ValueError:
            pass
        try:
            os.unlink(_DB_PATH)
        except OSError:
            pass
    print("OK: /api/modes serves the registry; modes are isolated worlds with "
          "mode-owned bots; same mode shares a world; unknown modes are "
          "refused; idle worlds wind down and resume on the next join")
    return 0


if __name__ == "__main__":
    sys.exit(main())
