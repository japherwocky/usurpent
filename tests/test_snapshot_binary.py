"""Equivalence test for the binary snapshot wire format (kanban #239).

The snapshot is sent as a packed binary frame instead of JSON. This test
proves the binary frame carries exactly the logical content of the JSON
snapshot dict _snapshot() produces: same players (full or delta, same body
point counts, same add/drop), same food delta (fadd/frem/fmov id sets and
per-pellet fields within quantization tolerance). It round-trips through
wire.encode_snapshot / wire.decode_snapshot, and checks the binary frame is
smaller than the JSON it replaces.

Run directly:  ./env/Scripts/python.exe tests/test_snapshot_binary.py
"""

import os
import math
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import usurpent
import protocol
import wire

# Quantization headroom: map quantization is ~0.15 u, radius ~0.13 u, etc.
COORD_TOL = 0.25
ANGLE_TOL = 0.01
GIRTH_TOL = 0.05
RAD_TOL = 0.25
LEN_TOL = 1.0


def approx(a, b, tol):
    return abs(a - b) <= tol


def ang_eq(a, b, tol):
    # Headings are periodic; the binary path wraps into [-pi, pi] while JSON may
    # send an unwrapped angle, so compare modulo 2pi.
    def wrap(x):
        x = math.fmod(x, 2.0 * math.pi)
        if x > math.pi:
            x -= 2.0 * math.pi
        elif x <= -math.pi:
            x += 2.0 * math.pi
        return x
    return abs(wrap(a) - wrap(b)) <= tol


def players_equal(json_ps, bin_ps):
    if len(json_ps) != len(bin_ps):
        return False, ("player count", len(json_ps), len(bin_ps))
    jmap = {p[protocol.FIELD_ID]: p for p in json_ps}
    bmap = {p[protocol.FIELD_ID]: p for p in bin_ps}
    if set(jmap) != set(bmap):
        return False, ("player id set", set(jmap), set(bmap))
    for pid in jmap:
        j = jmap[pid]
        b = bmap[pid]
        if not approx(j[protocol.FIELD_X], b[protocol.FIELD_X], COORD_TOL):
            return False, ("x", pid, j[protocol.FIELD_X], b[protocol.FIELD_X])
        if not approx(j[protocol.FIELD_Y], b[protocol.FIELD_Y], COORD_TOL):
            return False, ("y", pid)
        if not ang_eq(j[protocol.FIELD_HEADING], b[protocol.FIELD_HEADING], ANGLE_TOL):
            return False, ("heading", pid)
        if not approx(j[protocol.FIELD_GIRTH], b[protocol.FIELD_GIRTH], GIRTH_TOL):
            return False, ("girth", pid)
        if not approx(j[protocol.FIELD_LENGTH], b[protocol.FIELD_LENGTH], LEN_TOL):
            return False, ("length", pid)
        if j[protocol.FIELD_SCORE] != b[protocol.FIELD_SCORE]:
            return False, ("score", pid)
        if bool(j[protocol.FIELD_ALIVE]) != bool(b[protocol.FIELD_ALIVE]):
            return False, ("alive", pid)
        if bool(j[protocol.FIELD_IS_BOT]) != bool(b[protocol.FIELD_IS_BOT]):
            return False, ("is_bot", pid)
        if bool(j.get(protocol.FIELD_BOOST)) != bool(b.get(protocol.FIELD_BOOST)):
            return False, ("boost", pid)
        if (j.get(protocol.FIELD_USERNAME) or "") != (b.get(protocol.FIELD_USERNAME) or ""):
            return False, ("username", pid)
        if (j.get(protocol.FIELD_STRATEGY) or None) != (b.get(protocol.FIELD_STRATEGY) or None):
            return False, ("strategy", pid)
        # Body: either a full point list, or a delta (drop + add).
        if protocol.FIELD_POINTS in j:
            if protocol.FIELD_POINTS not in b:
                return False, ("body kind", pid, "json full / bin delta")
            jpts = j[protocol.FIELD_POINTS]
            bpts = b[protocol.FIELD_POINTS]
            if len(jpts) != len(bpts):
                return False, ("point count", pid, len(jpts), len(bpts))
            for (jx, jy), (bx, by) in zip(jpts, bpts):
                if not approx(jx, bx, COORD_TOL) or not approx(jy, by, COORD_TOL):
                    return False, ("point coord", pid)
        else:
            if protocol.FIELD_POINTS in b:
                return False, ("body kind", pid, "json delta / bin full")
            if j.get(protocol.FIELD_POINTS_DROP, 0) != b.get(protocol.FIELD_POINTS_DROP, 0):
                return False, ("drop", pid)
            jadd = j.get(protocol.FIELD_POINTS_ADD, [])
            badd = b.get(protocol.FIELD_POINTS_ADD, [])
            if len(jadd) != len(badd):
                return False, ("add count", pid, len(jadd), len(badd))
            for (jx, jy), (bx, by) in zip(jadd, badd):
                if not approx(jx, bx, COORD_TOL) or not approx(jy, by, COORD_TOL):
                    return False, ("add coord", pid)
    return True, None


def food_equal(json_food, bin_food):
    for key in (protocol.FIELD_FOOD_ADD, protocol.FIELD_FOOD_MOVE,
                protocol.FIELD_FOOD_REMOVE):
        j = json_food[key]
        b = bin_food[key]
        if key == protocol.FIELD_FOOD_REMOVE:
            jids = set(j)
            bids = set(b)
        else:
            jids = {d[protocol.FIELD_ID] for d in j}
            bids = {d[protocol.FIELD_ID] for d in b}
        if jids != bids:
            return False, (key + " id set", jids ^ bids)
        if key == protocol.FIELD_FOOD_REMOVE:
            continue
        jmap = {d[protocol.FIELD_ID]: d for d in j}
        bmap = {d[protocol.FIELD_ID]: d for d in b}
        for fid in jmap:
            jd = jmap[fid]
            bd = bmap[fid]
            if not approx(jd[protocol.FIELD_X], bd[protocol.FIELD_X], COORD_TOL):
                return False, ("fx", fid)
            if not approx(jd[protocol.FIELD_Y], bd[protocol.FIELD_Y], COORD_TOL):
                return False, ("fy", fid)
            if not approx(jd[protocol.FIELD_FOOD_RADIUS], bd[protocol.FIELD_FOOD_RADIUS], RAD_TOL):
                return False, ("fr", fid)
            if bool(jd.get(protocol.FIELD_FOOD_DROPPED)) != bool(bd.get(protocol.FIELD_FOOD_DROPPED)):
                return False, ("fdrop", fid)
            if str(jd.get(protocol.FIELD_FOOD_OWNER)) != str(bd.get(protocol.FIELD_FOOD_OWNER)):
                return False, ("fowner", fid)
    return True, None


def roundtrip_over_ticks(trials=40, ticks=12):
    rng = random.Random(7)
    for t in range(trials):
        w = usurpent.World()  # keep bots so there are serpents with bodies
        seen = {}
        food_seen = {}
        vx = rng.uniform(0, config.MAP_WIDTH)
        vy = rng.uniform(0, config.MAP_HEIGHT)
        reach = (rng.uniform(config.INTEREST_MIN_RADIUS, config.INTEREST_RADIUS)
                 + config.INTEREST_MARGIN)
        for _ in range(ticks):
            w.tick()
            snap = w._snapshot(around=(vx, vy), reach=reach,
                               seen=seen, food_seen=food_seen)
            buf = wire.encode_snapshot(
                snap, config.MAP_WIDTH, config.MAP_HEIGHT,
                config.MAX_GIRTH, config.FOOD_MERGE_MAX_RADIUS)
            dec = wire.decode_snapshot(
                buf, config.MAP_WIDTH, config.MAP_HEIGHT,
                config.MAX_GIRTH, config.FOOD_MERGE_MAX_RADIUS)
            if dec[protocol.FIELD_TICK] != snap[protocol.FIELD_TICK]:
                return False, ("tick", t)
            ok, info = players_equal(snap[protocol.FIELD_PLAYERS],
                                     dec[protocol.FIELD_PLAYERS])
            if not ok:
                return False, ("players", t, info)
            ok, info = food_equal(snap[protocol.FIELD_FOOD], dec[protocol.FIELD_FOOD])
            if not ok:
                return False, ("food", t, info)
    return True, None


def welcome_path():
    """With no history, the snapshot is all-adds and full bodies."""
    w = usurpent.World()
    snap = w._snapshot(seen=None, food_seen=None)
    buf = wire.encode_snapshot(
        snap, config.MAP_WIDTH, config.MAP_HEIGHT,
        config.MAX_GIRTH, config.FOOD_MERGE_MAX_RADIUS)
    dec = wire.decode_snapshot(
        buf, config.MAP_WIDTH, config.MAP_HEIGHT,
        config.MAX_GIRTH, config.FOOD_MERGE_MAX_RADIUS)
    food = dec[protocol.FIELD_FOOD]
    if food[protocol.FIELD_FOOD_REMOVE] or food[protocol.FIELD_FOOD_MOVE]:
        return False, ("welcome should carry only adds",)
    if len(food[protocol.FIELD_FOOD_ADD]) != len(snap[protocol.FIELD_FOOD][protocol.FIELD_FOOD_ADD]):
        return False, ("welcome add count",)
    for p in dec[protocol.FIELD_PLAYERS]:
        if protocol.FIELD_POINTS not in p:
            return False, ("welcome bodies must be full", p[protocol.FIELD_ID])
    return True, None


def smaller_than_json():
    w = usurpent.World()
    for _ in range(8):
        w.tick()
    snap = w._snapshot(seen={}, food_seen={})
    import json
    json_len = len(json.dumps(snap).encode("utf-8"))
    buf = wire.encode_snapshot(
        snap, config.MAP_WIDTH, config.MAP_HEIGHT,
        config.MAX_GIRTH, config.FOOD_MERGE_MAX_RADIUS)
    if not (len(buf) < json_len):
        return False, len(buf), json_len
    return True, len(buf), json_len


def main():
    ok, info = welcome_path()
    if not ok:
        print("FAIL welcome_path:", info)
        return 1
    ok, info = roundtrip_over_ticks()
    if not ok:
        print("FAIL roundtrip:", info)
        return 1
    ok, bin_len, json_len = smaller_than_json()
    if not ok:
        print("FAIL smaller_than_json:", bin_len, json_len)
        return 1
    print(f"OK: binary snapshot round-trips to the JSON content over ticks; "
          f"welcome is all-adds; frame {bin_len}B < JSON {json_len}B "
          f"({json_len / max(1, bin_len):.1f}x smaller)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
