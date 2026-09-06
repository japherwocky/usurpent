"""Hardcore mode: self-collision with a grace arc (#367).

The rule: in hardcore a serpent's own body is lethal to its head, except for
the neck -- the points just behind the head, which sit inside the collision
radius at every size and would make every turn a suicide. The tests pin the
whole shape of that:

  1. The grace arc actually covers the neck: K * spacing >= the collision
     reach, at several girths, so the geometry cannot fall behind a retune.
  2. A body point beyond the grace arc under the head kills, with cause
     "self" -- and the client is told via a `died` message.
  3. The SAME overlap inside the grace arc is forgiven.
  4. The forgiveness is by arc (index along the body), not by distance: a
     point at zero distance from the head still kills if it was laid down
     long ago. Distance-based forgiveness would make self-collision dead
     code, since everything within reach is also within the grace.
  5. Classic is untouched: the same lethal geometry survives there.
  6. Causes: wall deaths say "wall", snake deaths say "snake".
  7. A lone bot in a hardcore world survives a soak, because its avoidance
     sense now includes its own body (minus the neck).

Run directly:  ./env/Scripts/python.exe tests/test_hardcore.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point at a scratch database BEFORE config is imported -- config reads the
# path at import time, and db.py binds its SqliteDatabase from it.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="usurpent-hardcore-", suffix=".db")
os.close(_DB_FD)
os.environ["USURPENT_DATABASE_PATH"] = _DB_PATH

import config
import modes
import protocol
import usurpent

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok: {name}")
    else:
        FAILURES.append(f"{name} {detail}")
        print(f"  FAIL: {name} {detail}")


class FakeHandler:
    """Just enough handler for Player: captures outgoing messages."""

    def __init__(self):
        self.sent = []

    def write_message(self, msg):
        self.sent.append(msg)


def crafted_world(mode_cls):
    """A world of the given mode with no bots in it."""
    world = usurpent.World(mode_cls)
    world.players.clear()
    return world


def line_behind(x, y, spacing, count):
    """`count` points marching west from (x, y), neck first in list order
    reversed: points[0] is the tail tip, points[-1] the neck."""
    return [(x - i * spacing, y) for i in range(count, 0, -1)]


def spawn(world, handler=None, x=5000.0, y=5000.0):
    player = usurpent.Player("p1", handler, x, y)
    world.players[player.id] = player
    return player


def collide(world):
    boxes, bodies = world._index_players()
    world._handle_collisions(bodies)


def test_grace_covers_the_neck():
    print("grace arc covers the neck at every girth")
    for girth in (config.BASE_GIRTH, 12.0, config.MAX_GIRTH):
        spacing = max(config.MIN_SEGMENT_SPACING,
                      girth * config.SEGMENT_SPACING_FACTOR)
        k = usurpent._self_grace_segments(girth)
        reach = usurpent._collision_reach(girth, girth)
        check(f"girth {girth}: {k:.0f} segments x {spacing:.2f} spacing "
              f">= reach {reach}", k * spacing >= reach,
              f"({k * spacing:.2f})")


def test_self_hit_beyond_grace_kills():
    print("a loop laid down earlier kills, with cause self and a died message")
    world = crafted_world(modes.HardcoreMode)
    handler = FakeHandler()
    player = spawn(world, handler)
    spacing = player._segment_spacing()
    k = usurpent._self_grace_segments(player.girth)
    # A straight body trailing west, with one old point parked exactly under
    # the head, one segment beyond the grace arc.
    points = line_behind(player.x, player.y, spacing, 30)
    points[len(points) - k - 1] = (player.x, player.y)
    player.points = points
    collide(world)
    check("serpent died", not player.alive)
    check("cause is self", player.death_cause == "self", repr(player.death_cause))
    died = [m for m in handler.sent if m.get(protocol.FIELD_TYPE) == protocol.TYPE_DEATH]
    check("client told", len(died) == 1 and died[0][protocol.FIELD_CAUSE] == "self",
          repr(handler.sent))


def test_neck_overlap_is_forgiven():
    print("the neck sitting on the head is forgiven")
    world = crafted_world(modes.HardcoreMode)
    player = spawn(world)
    spacing = player._segment_spacing()
    k = usurpent._self_grace_segments(player.girth)
    # Straight body trailing west, with the LAST point (the neck, inside the
    # grace arc) parked exactly under the head.
    points = line_behind(player.x, player.y, spacing, 30)
    points[-1] = (player.x, player.y)
    player.points = points
    check("setup: neck is inside the grace", len(points) - 1 >= len(points) - k)
    collide(world)
    check("serpent survived", player.alive)


def test_grace_is_arc_not_distance():
    print("forgiveness is by arc length, not distance")
    world = crafted_world(modes.HardcoreMode)
    player = spawn(world)
    spacing = player._segment_spacing()
    k = usurpent._self_grace_segments(player.girth)
    # Same zero-distance overlap as the forgiven case, but at an index deep
    # in the body. A distance-based grace would forgive this too, and
    # self-collision would never kill anything.
    points = line_behind(player.x, player.y, spacing, 30)
    points[2] = (player.x, player.y)
    player.points = points
    check("setup: overlap is beyond the grace", 2 < len(points) - k)
    collide(world)
    check("serpent died", not player.alive)
    check("cause is self", player.death_cause == "self", repr(player.death_cause))


def test_classic_ignores_own_body():
    print("classic: the same lethal geometry survives")
    world = crafted_world(modes.ClassicMode)
    player = spawn(world)
    spacing = player._segment_spacing()
    points = line_behind(player.x, player.y, spacing, 30)
    points[2] = (player.x, player.y)
    player.points = points
    collide(world)
    check("serpent survived", player.alive)


def test_causes():
    print("wall and snake causes")
    world = crafted_world(modes.HardcoreMode)
    player = spawn(world, x=0.0)
    collide(world)
    check("wall death", not player.alive and player.death_cause == "wall",
          repr(player.death_cause))

    world = crafted_world(modes.HardcoreMode)
    victim = spawn(world, x=5000.0, y=5000.0)
    killer = usurpent.Player("p2", None, 5100.0, 5000.0)
    world.players[killer.id] = killer
    # The killer's body is a line running west THROUGH the victim's head, so
    # the victim's head is on the killer's body. The killer's own head sits
    # 100 units east of its body, clear of everything.
    killer.points = [(5000.0 + j * 2.0, 5000.0) for j in range(20)]
    collide(world)
    check("snake death", not victim.alive and victim.death_cause == "snake",
          repr(victim.death_cause))
    check("killer survived", killer.alive)


def test_bot_soak():
    print("a lone bot survives a hardcore soak (self-avoidance works)")
    world = usurpent.World(modes.HardcoreMode)
    bots = [p for p in world.players.values() if p.is_bot]
    check("world spawned bots", bool(bots))
    lone = bots[0]
    for pid in [pid for pid, p in world.players.items() if p is not lone]:
        del world.players[pid]
    deaths = 0
    for _ in range(600):  # 30 simulated seconds
        world.tick()
        if not lone.alive:
            deaths += 1
            world._respawn_player(lone.id)
    check("lone bot mostly survived the soak", deaths <= 2, f"({deaths} deaths)")


def main():
    try:
        test_grace_covers_the_neck()
        test_self_hit_beyond_grace_kills()
        test_neck_overlap_is_forgiven()
        test_grace_is_arc_not_distance()
        test_classic_ignores_own_body()
        test_causes()
        test_bot_soak()
    finally:
        try:
            os.unlink(_DB_PATH)
        except OSError:
            pass
    if FAILURES:
        print(f"FAILED hardcore: {len(FAILURES)} failure(s)")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("OK: hardcore self-collision kills beyond the grace arc, forgives "
          "the neck, stays dead code in classic, names its causes, and bots "
          "do not self-destruct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
