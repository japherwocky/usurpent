"""Equivalence test for the interest-grid food query (kanban #238).

_food_list used to scan every pellet for every viewer each tick
(O(pellets x viewers)). It now pulls from a coarse SpatialGrid built once per
tick by _index_food, then trims to the exact interest radius. This test proves
the grid path returns the SAME set of pellets the full scan would have, over
many randomized worlds -- viewers at the map centre and in every corner,
pellets sitting exactly on the reach boundary, and reaches from the floor to
the ceiling of what a client can report.

Run it directly:  ./env/Scripts/python.exe tests/test_food_interest_grid.py
It is also pytest-compatible if pytest is installed.
"""

import math
import os
import random
import sys

# Allow running from the tests/ directory: make the repo root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import usurpent
import protocol


def brute_food_ids(world, px, py, reach):
    """The old O(pellets) answer: every pellet whose centre is within `reach`."""
    out = set()
    for fid, f in world.foods.items():
        x = f["x"]
        if x < px - reach or x > px + reach:
            continue
        y = f["y"]
        if y < py - reach or y > py + reach:
            continue
        out.add(fid)
    return out


def grid_food_ids(world, px, py, reach):
    """The new grid answer, normalised to a set of ids for comparison."""
    return {d[protocol.FIELD_ID] for d in world._food_list(around=(px, py), reach=reach)}


def random_world(rng, n_pellets):
    """A World whose food we replace with `n_pellets` randomized pellets."""
    world = usurpent.World()
    world.foods.clear()
    world.players.clear()
    world._next_id = 0
    world._food_next = 0
    for _ in range(n_pellets):
        world._food_next += 1
        fid = str(world._food_next)
        # Spread across the whole map, including the edges and corners.
        x = rng.uniform(0.0, config.MAP_WIDTH)
        y = rng.uniform(0.0, config.MAP_HEIGHT)
        radius = rng.uniform(config.FOOD_BASE_RADIUS, config.FOOD_MERGE_MAX_RADIUS)
        value = max(1, round(radius / config.FOOD_RADIUS_PER_VALUE))
        dropped = rng.random() < 0.5
        owner = rng.choice([None, "1", "2", "3"])
        world.foods[fid] = {
            "x": x, "y": y, "r": radius, "value": value,
            "dropped": dropped, "owner": owner,
            "shard": rng.randrange(max(1, config.FOOD_GRAVITY_SHARDS)),
        }
    # Build the interest grid from these exact positions, as the tick would.
    world._index_food()
    return world


def trial(rng, n_pellets):
    world = random_world(rng, n_pellets)

    # Reaches from the floor to the ceiling of a real client's window.
    reaches = [
        config.INTEREST_MIN_RADIUS + config.INTEREST_MARGIN,
        config.INTEREST_RADIUS + config.INTEREST_MARGIN,
        rng.uniform(config.INTEREST_MIN_RADIUS, config.INTEREST_RADIUS)
        + config.INTEREST_MARGIN,
    ]
    # Viewers: centre, all four corners, and random points (some near edges).
    viewers = [
        (config.MAP_WIDTH / 2.0, config.MAP_HEIGHT / 2.0),
        (0.0, 0.0),
        (config.MAP_WIDTH, 0.0),
        (0.0, config.MAP_HEIGHT),
        (config.MAP_WIDTH, config.MAP_HEIGHT),
    ]
    for _ in range(4):
        viewers.append((rng.uniform(0.0, config.MAP_WIDTH),
                        rng.uniform(0.0, config.MAP_HEIGHT)))

    for reach in reaches:
        for px, py in viewers:
            # Drop a few pellets exactly on the reach boundary to exercise the
            # edge of the AABB test (inclusive vs. exclusive).
            for sign_x, sign_y in ((1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)):
                world._food_next += 1
                fid = "edge" + str(world._food_next)
                world.foods[fid] = {
                    "x": px + sign_x * reach,
                    "y": py + sign_y * reach,
                    "r": config.FOOD_BASE_RADIUS,
                    "value": 1, "dropped": False, "owner": None, "shard": 0,
                }
            # Rebuild the grid so the boundary pellets are indexed too.
            world._index_food()

            want = brute_food_ids(world, px, py, reach)
            got = grid_food_ids(world, px, py, reach)
            if want != got:
                missing = len(want - got)
                extra = len(got - want)
                return (f"pellets={n_pellets} viewer=({px:.0f},{py:.0f}) "
                        f"reach={reach:.0f} brute={len(want)} grid={len(got)} "
                        f"missing={missing} extra={extra}")
    return None


def main():
    rng = random.Random(1234)
    trials = 400
    for i in range(trials):
        n = rng.randint(500, 6000)
        err = trial(rng, n)
        if err is not None:
            print(f"FAIL trial {i}: {err}")
            return 1
    print(f"OK: {trials} randomized worlds, grid query matches full scan exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
