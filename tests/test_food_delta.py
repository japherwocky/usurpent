"""Equivalence test for food delta encoding (kanban #174).

Bodies are already sent as deltas (a viewer gets a full body once, then only
what changed). Food now does the same: _food_delta sends only pellets that
entered view (fadd), left it (frem), or moved within it (fmov), against the
per-viewer `seen` map. This test proves that applying those deltas
cumulatively leaves the client holding EXACTLY the visible set that the old
full-list encoder would have sent -- over many ticks of gravity drift,
merging, spawning and pellets crossing the interest boundary.

Run directly:  ./env/Scripts/python.exe tests/test_food_delta.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import usurpent
import protocol


def reconcile_over_ticks(trials=50, ticks=15):
    rng = random.Random(99)
    for t in range(trials):
        w = usurpent.World()
        # No bots: we only need the food simulation (gravity/merge/spawn) and
        # the per-tick grid rebuild that _food_delta relies on.
        w.players.clear()
        seen = {}
        vx = rng.uniform(0, config.MAP_WIDTH)
        vy = rng.uniform(0, config.MAP_HEIGHT)
        reach = (rng.uniform(config.INTEREST_MIN_RADIUS, config.INTEREST_RADIUS)
                 + config.INTEREST_MARGIN)
        client = {}  # id -> last pellet dict the client holds
        for _ in range(ticks):
            w.tick()
            delta = w._food_delta((vx, vy), reach, seen)
            for f in delta[protocol.FIELD_FOOD_ADD]:
                client[f[protocol.FIELD_ID]] = f
            for fid in delta[protocol.FIELD_FOOD_REMOVE]:
                client.pop(fid, None)
            for f in delta[protocol.FIELD_FOOD_MOVE]:
                client[f[protocol.FIELD_ID]] = f
            expected = {d[protocol.FIELD_ID]: d
                        for d in w._food_list((vx, vy), reach)}
            if client != expected:
                only_client = set(client) - set(expected)
                only_expected = set(expected) - set(client)
                changed = [i for i in set(client) & set(expected)
                           if client[i] != expected[i]]
                return False, (t, len(client), len(expected),
                               len(only_client), len(only_expected), len(changed))
    return True, None


def welcome_is_all_added():
    w = usurpent.World()
    w.players.clear()
    seen = {}
    vx, vy = config.MAP_WIDTH / 2.0, config.MAP_HEIGHT / 2.0
    reach = config.INTEREST_RADIUS + config.INTEREST_MARGIN
    delta = w._food_delta((vx, vy), reach, seen)
    expected_ids = {d[protocol.FIELD_ID] for d in w._food_list((vx, vy), reach)}
    added_ids = {f[protocol.FIELD_ID] for f in delta[protocol.FIELD_FOOD_ADD]}
    if added_ids != expected_ids:
        return False, ("welcome add mismatch", len(added_ids), len(expected_ids))
    if delta[protocol.FIELD_FOOD_REMOVE] or delta[protocol.FIELD_FOOD_MOVE]:
        return False, ("welcome should carry no rem/mov",)
    if set(seen) != expected_ids:
        return False, ("seen not seeded by welcome",)
    return True, None


def main():
    ok, info = welcome_is_all_added()
    if not ok:
        print("FAIL welcome:", info)
        return 1
    ok, info = reconcile_over_ticks()
    if not ok:
        print("FAIL reconcile:", info)
        return 1
    print("OK: food delta reconciles to the full visible set over ticks; "
          "welcome sends every pellet as add")
    return 0


if __name__ == "__main__":
    sys.exit(main())
