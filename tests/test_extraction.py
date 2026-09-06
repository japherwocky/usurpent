"""Extraction mode: the run loop, banking, and the zone (#368).

The mode's economy in seven checks:

  1. The zone places itself inside the food disc, clear of live serpents,
     and announces itself to connected clients.
  2. Reaching it ends the run: carrying banks, an `extracted` message goes
     out, no carcass falls, and the zone relocates.
  3. A new run starts carrying at zero but keeps what was banked.
  4. Dying keeps the banked total (only the carrying scatters).
  5. For a registered player the bank lands on the Account row and comes
     back with them on their next connection.
  6. The leaderboard ranks banked, not carrying.
  7. An extraction bot carrying enough steers for the zone.

Run directly:  ./env/Scripts/python.exe tests/test_extraction.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point at a scratch database BEFORE config is imported -- config reads the
# path at import time, and db.py binds its SqliteDatabase from it.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="usurpent-extraction-", suffix=".db")
os.close(_DB_FD)
os.environ["USURPENT_DATABASE_PATH"] = _DB_PATH

import config
import db
import modes
import protocol
import usurpent
from models import Account

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok: {name}")
    else:
        FAILURES.append(f"{name} {detail}")
        print(f"  FAIL: {name} {detail}")


class FakeHandler:
    """Just enough handler for spawn/kill paths: captures outgoing messages."""

    def __init__(self, account_id=None, username="tester"):
        self.account_id = account_id
        self.username = username
        self.sent = []
        self.body_seen = {}
        self.food_seen = {}

    def write_message(self, msg, binary=False):
        self.sent.append(msg)


def as_dicts(sent):
    """Normalize captured messages: the wire path sends JSON strings, the
    event paths send dicts already."""
    out = []
    for m in sent:
        if isinstance(m, str):
            out.append(json.loads(m))
        elif isinstance(m, dict):
            out.append(m)
    return out


def extraction_world():
    world = usurpent.World(modes.ExtractionMode)
    world.players.clear()
    return world


def mode_of(world) -> modes.ExtractionMode:
    """The world's mode, narrowed for the type checker."""
    mode = world.mode
    assert isinstance(mode, modes.ExtractionMode)
    return mode


def spawn(world, handler=None, x=5000.0, y=5000.0):
    # Allocate an id the way the world does: the wire format quantizes ids as
    # u32, so a hand-made string id would break the binary encoder.
    world._next_id += 1
    player = usurpent.Player(str(world._next_id), handler, x, y)
    world.players[player.id] = player
    # A quiet field: the world seeds thousands of random pellets, and a head
    # that spawns next to one eats it during the test's tick, turning every
    # exact-score assertion into a coin flip.
    world.foods.clear()
    return player


def test_zone_placement():
    print("the zone places itself in the food disc, clear of serpents")
    world = extraction_world()
    handler = FakeHandler()
    player = spawn(world, handler, x=config.MAP_WIDTH / 2, y=config.MAP_HEIGHT / 2)
    world.tick()
    mode = mode_of(world)
    check("zone exists after a tick", mode.zone is not None)
    assert mode.zone is not None  # for the type checker; check() reported it
    z = mode.zone
    center_d = ((z["x"] - config.MAP_WIDTH / 2) ** 2
                + (z["y"] - config.MAP_HEIGHT / 2) ** 2) ** 0.5
    check("zone is in the food disc", center_d <= config.FOOD_SPAWN_RADIUS + 1.0,
          f"({center_d:.0f})")
    player_d = ((z["x"] - player.x) ** 2 + (z["y"] - player.y) ** 2) ** 0.5
    check("zone is clear of the player",
          player_d >= config.EXTRACTION_ZONE_CLEARANCE - 1.0, f"({player_d:.0f})")
    zones = [m for m in as_dicts(handler.sent)
             if m.get("type") == protocol.TYPE_ZONE]
    check("zone announced", len(zones) == 1 and zones[0]["zone"]["x"] == round(z["x"], 2),
          repr(zones))


def test_extract_banks_and_ends_run():
    print("reaching the zone banks the carrying and ends the run")
    world = extraction_world()
    handler = FakeHandler()
    player = spawn(world, handler)
    player.score = 25
    mode_of(world).zone = {"x": player.x, "y": player.y,
                       "r": config.EXTRACTION_ZONE_RADIUS}
    world.tick()
    check("run ended", not player.alive)
    check("carrying banked", player.banked == 25, repr(player.banked))
    check("score still shows on the card", player.score == 25)
    check("no death cause", player.death_cause is None, repr(player.death_cause))
    extracted = [m for m in as_dicts(handler.sent)
                 if m.get("type") == protocol.TYPE_EXTRACTED]
    check("client told", len(extracted) == 1
          and extracted[0][protocol.FIELD_BANKED] == 25
          and extracted[0][protocol.FIELD_GAINED] == 25, repr(extracted))
    carcass = [f for f in world.foods.values() if f.get("owner") == player.id]
    check("no carcass fell", not carcass)
    zone = mode_of(world).zone
    check("zone relocated", zone is not None
          and (zone["x"] != round(player.x, 2)
               or zone["y"] != round(player.y, 2)))


def test_new_run_keeps_banked():
    print("a new run starts at zero carrying, banked intact")
    world = extraction_world()
    player = spawn(world)
    player.score = 25
    mode_of(world).zone = {"x": player.x, "y": player.y,
                       "r": config.EXTRACTION_ZONE_RADIUS}
    world.tick()
    world._respawn_player(player.id)
    check("respawned", player.alive)
    check("carrying reset", player.score == 0, repr(player.score))
    check("banked kept", player.banked == 25, repr(player.banked))


def test_death_keeps_banked():
    print("dying scatters the carrying but never the banked")
    world = extraction_world()
    player = spawn(world)
    player.score = 25
    mode_of(world).zone = {"x": player.x, "y": player.y,
                       "r": config.EXTRACTION_ZONE_RADIUS}
    world.tick()
    world._respawn_player(player.id)
    player.score = 7
    player.x = 0.0  # wall
    boxes, bodies = world._index_players()
    world._handle_collisions(bodies)
    check("died at the wall", not player.alive
          and player.death_cause == "wall", repr(player.death_cause))
    check("banked survived", player.banked == 25, repr(player.banked))
    carcass = [f for f in world.foods.values() if f.get("owner") == player.id]
    check("carrying scattered as a carcass", bool(carcass))


def test_account_persistence():
    print("a registered player's bank lands on the Account and returns")
    db.init_db()
    account = Account(username="extractor", email=None)
    account.set_password("password123")
    account.save()

    world = extraction_world()
    handler = FakeHandler(account_id=account.id, username="extractor")
    world.spawn_player(handler)
    player = next(iter(world.players.values()))
    check("spawned with the account's banked", player.banked == 0)
    player.score = 30
    mode_of(world).zone = {"x": player.x, "y": player.y,
                       "r": config.EXTRACTION_ZONE_RADIUS}
    world.tick()
    fresh = Account.get_by_id(account.id)
    check("bank landed on the account", fresh.banked_score == 30,
          repr(fresh.banked_score))

    # A later connection walks in with the banked wealth.
    world2 = extraction_world()
    handler2 = FakeHandler(account_id=account.id, username="extractor")
    world2.spawn_player(handler2)
    player2 = next(iter(world2.players.values()))
    check("banked came back with them", player2.banked == 30,
          repr(player2.banked))


def test_leaderboard_ranks_banked():
    print("the leaderboard ranks banked, not carrying")
    world = extraction_world()
    a = spawn(world, x=4000.0, y=4000.0)
    a.banked = 50
    b = usurpent.Player("p2", None, 6000.0, 6000.0)
    b.score = 100
    world.players[b.id] = b
    lb = world._leaderboard(a)
    entries = lb[protocol.FIELD_ENTRIES]
    check("banked player ranks first", entries[0][protocol.FIELD_ID] == a.id,
          repr(entries))
    check("entry shows banked", entries[0][protocol.FIELD_SCORE] == 50)


def test_bot_heads_for_zone():
    print("a carrying bot steers for the zone")
    world = usurpent.World(modes.ExtractionMode)
    bot = next(p for p in world.players.values() if p.is_bot)
    bot.score = config.BOT_EXTRACT_THRESHOLD
    zx, zy = bot.x + 500.0, bot.y
    mode_of(world).zone = {"x": zx, "y": zy, "r": config.EXTRACTION_ZONE_RADIUS}
    bot.strategy.think(world, bot)
    tx, ty = bot.target
    # The steering target (a direction vector) must have a positive component
    # toward the zone; the avoidance term may skew it but not flip it.
    dot = tx * (zx - bot.x) + ty * (zy - bot.y)
    check("target leans toward the zone", dot > 0, f"(dot {dot:.1f})")


def test_banked_sizes_the_serpent():
    print("banked wealth sizes the serpent you walk in as")
    world = extraction_world()
    player = spawn(world)
    player.score = 25
    mode_of(world).zone = {"x": player.x, "y": player.y,
                           "r": config.EXTRACTION_ZONE_RADIUS}
    world.tick()
    world._respawn_player(player.id)
    check("respawn sized from banked",
          player.girth == usurpent._girth_for_score(25)
          and player.length == usurpent._length_for_score(25),
          f"(girth {player.girth:.2f})")
    check("bigger than a fresh guest",
          player.girth > usurpent._girth_for_score(0))
    # Eating grows from worth (carrying + banked), not the score alone.
    player.score = 0
    world._make_food(player.x, player.y, 2.0, 5, False)
    value = 5
    _mesh, _cell, fine, _shard = world._index_food()
    world._handle_food(fine)
    check("ate the pellet", player.score == value, repr(player.score))
    check("girth grew from worth",
          player.girth == usurpent._girth_for_score(value + 25),
          f"(girth {player.girth:.2f})")
    # Classic reads the same curves with banked pinned at zero.
    classic = usurpent.World(modes.ClassicMode)
    classic_player = next(p for p in classic.players.values() if not p.is_bot) \
        if any(not p.is_bot for p in classic.players.values()) else None
    if classic_player is None:
        classic.players.clear()
        classic_player = spawn(classic)
    check("classic worth is just the score",
          classic_player.worth() == classic_player.score == 0)


def main():
    try:
        test_zone_placement()
        test_extract_banks_and_ends_run()
        test_new_run_keeps_banked()
        test_death_keeps_banked()
        test_account_persistence()
        test_leaderboard_ranks_banked()
        test_bot_heads_for_zone()
        test_banked_sizes_the_serpent()
    finally:
        try:
            os.unlink(_DB_PATH)
        except OSError:
            pass
    if FAILURES:
        print(f"FAILED extraction: {len(FAILURES)} failure(s)")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("OK: extraction places and announces its zone, banks on contact, "
          "ends the run without a carcass, keeps banked through death and "
          "respawn, persists it on the Account, ranks the board by it, and "
          "bots play the loop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
