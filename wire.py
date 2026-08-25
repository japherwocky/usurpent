"""Binary encoder/decoder for TYPE_SNAPSHOT (kanban #239).

See protocol.py (BINARY_SNAPSHOT_*) for the byte layout. The encoder takes the
same dict _snapshot() produces and packs it; the decoder (used by tests and as
a reference) reconstructs that dict, so the binary path is provably the same
logical message as the JSON path, modulo the documented quantization.

Quantization is chosen so the wire error is far below anything the game can
see: coordinates land at ~0.15 u on a 10000-unit map, heading at ~0.0001 rad,
girth at ~0.0004 u, radius at ~0.13 u. The client dequantizes with the map
dimensions and food radius range it already learned from the welcome, so the
two ends stay in lockstep if those constants are ever retuned.
"""

import math
import struct

import protocol
from protocol import BINARY_SNAPSHOT_MAGIC, BINARY_SNAPSHOT_VERSION

_Q16 = 65535
_Q8 = 255
_TWO_PI = 2.0 * math.pi


# --- quantize (server -> wire) ------------------------------------------------

def _q_coord(v, size):
    q = int(round(v / size * _Q16))
    return 0 if q < 0 else (_Q16 if q > _Q16 else q)


def _q_angle(a):
    # Server heading is not wrapped to [-pi, pi]; angles are periodic so we wrap
    # here. The client reads heading modulo 2pi (lerpAngle/wrapAngle), so the
    # decoded value is functionally identical to the unwrapped one JSON sends.
    a = math.fmod(a, _TWO_PI)
    if a > math.pi:
        a -= _TWO_PI
    elif a <= -math.pi:
        a += _TWO_PI
    q = int(round((a + math.pi) / _TWO_PI * _Q16))
    return 0 if q < 0 else (_Q16 if q > _Q16 else q)


def _q_girth(g, maxg):
    q = int(round(g / maxg * _Q16))
    return 0 if q < 0 else (_Q16 if q > _Q16 else q)


def _q_rad(r, maxr):
    q = int(round(r / maxr * _Q8))
    return 0 if q < 0 else (_Q8 if q > _Q8 else q)


# --- dequantize (wire -> client) ----------------------------------------------

def _u_coord(q, size):
    return q / _Q16 * size


def _u_angle(q):
    return q / _Q16 * _TWO_PI - math.pi


def _u_girth(q, maxg):
    return q / _Q16 * maxg


def _u_rad(q, maxr):
    return q / _Q8 * maxr


# --- packing helpers ----------------------------------------------------------

def _pack_pellet(pel, out, map_w, map_h, food_max_r):
    out += struct.pack(">I", int(pel[protocol.FIELD_ID]))
    out += struct.pack(">HH",
                       _q_coord(pel[protocol.FIELD_X], map_w),
                       _q_coord(pel[protocol.FIELD_Y], map_h))
    out += struct.pack(">B", _q_rad(pel[protocol.FIELD_FOOD_RADIUS], food_max_r))
    flags = 0
    if pel.get(protocol.FIELD_FOOD_DROPPED):
        flags |= 1
    owner = pel.get(protocol.FIELD_FOOD_OWNER)
    if owner is not None:
        flags |= 2
    out.append(flags)
    if owner is not None:
        out += struct.pack(">I", int(owner))


def encode_snapshot(snap, map_w, map_h, max_girth, food_max_r):
    """Pack a _snapshot() dict into the binary frame described in protocol.py."""
    players = snap[protocol.FIELD_PLAYERS]
    food = snap[protocol.FIELD_FOOD]
    fadd = food[protocol.FIELD_FOOD_ADD]
    fmov = food[protocol.FIELD_FOOD_MOVE]
    frem = food[protocol.FIELD_FOOD_REMOVE]

    out = bytearray()
    out += BINARY_SNAPSHOT_MAGIC
    out.append(BINARY_SNAPSHOT_VERSION)
    out += struct.pack(">I", snap[protocol.FIELD_TICK])
    out += struct.pack(">HHHH", len(players), len(fadd), len(fmov), len(frem))

    for p in players:
        out += struct.pack(">I", int(p[protocol.FIELD_ID]))
        out += struct.pack(">HH",
                           _q_coord(p[protocol.FIELD_X], map_w),
                           _q_coord(p[protocol.FIELD_Y], map_h))
        out += struct.pack(">H", _q_angle(p[protocol.FIELD_HEADING]))
        out.append(1 if p[protocol.FIELD_ALIVE] else 0)
        out += struct.pack(">I", int(p[protocol.FIELD_SCORE]))
        out += struct.pack(">H", _q_girth(p[protocol.FIELD_GIRTH], max_girth))
        out += struct.pack(">H", int(round(p[protocol.FIELD_LENGTH])))
        out.append(1 if p[protocol.FIELD_IS_BOT] else 0)
        out.append(1 if p.get(protocol.FIELD_BOOST) else 0)
        uname = (p.get(protocol.FIELD_USERNAME) or "").encode("utf-8")
        out.append(len(uname))
        out += uname
        strat = (p.get(protocol.FIELD_STRATEGY) or "").encode("utf-8")
        out.append(len(strat))
        out += strat
        if protocol.FIELD_POINTS in p:
            out.append(0)  # full body
            pts = p[protocol.FIELD_POINTS]
            out += struct.pack(">H", len(pts))
            for px, py in pts:
                out += struct.pack(">HH",
                                   _q_coord(px, map_w), _q_coord(py, map_h))
        else:
            out.append(1)  # delta body
            out += struct.pack(">H", int(p.get(protocol.FIELD_POINTS_DROP, 0)))
            add = p.get(protocol.FIELD_POINTS_ADD, [])
            out += struct.pack(">H", len(add))
            for px, py in add:
                out += struct.pack(">HH",
                                   _q_coord(px, map_w), _q_coord(py, map_h))

    for pel in fadd:
        _pack_pellet(pel, out, map_w, map_h, food_max_r)
    for pel in fmov:
        _pack_pellet(pel, out, map_w, map_h, food_max_r)
    for fid in frem:
        out += struct.pack(">I", int(fid))

    return bytes(out)


def decode_snapshot(buf, map_w, map_h, max_girth, food_max_r):
    """Inverse of encode_snapshot: rebuild the _snapshot() dict (ids as str)."""
    view = memoryview(buf)
    pos = 0
    if bytes(view[pos:pos + 4]) != BINARY_SNAPSHOT_MAGIC:
        raise ValueError("bad binary snapshot magic")
    pos += 4
    version = view[pos]
    pos += 1
    if version != BINARY_SNAPSHOT_VERSION:
        raise ValueError(f"unsupported binary snapshot version {version}")
    (tick, pcount, fadd_c, fmov_c, frem_c) = struct.unpack_from(">IHHHH", view, pos)
    pos += 12

    players = []
    for _ in range(pcount):
        (pid,) = struct.unpack_from(">I", view, pos); pos += 4
        (qx, qy) = struct.unpack_from(">HH", view, pos); pos += 4
        (qh,) = struct.unpack_from(">H", view, pos); pos += 2
        alive = view[pos]; pos += 1
        (score,) = struct.unpack_from(">I", view, pos); pos += 4
        (qg,) = struct.unpack_from(">H", view, pos); pos += 2
        (length,) = struct.unpack_from(">H", view, pos); pos += 2
        is_bot = view[pos]; pos += 1
        boost = view[pos]; pos += 1
        ulen = view[pos]; pos += 1
        uname = bytes(view[pos:pos + ulen]).decode("utf-8"); pos += ulen
        slen = view[pos]; pos += 1
        strat = bytes(view[pos:pos + slen]).decode("utf-8") if slen else None
        pos += slen
        kind = view[pos]; pos += 1
        p = {
            protocol.FIELD_ID: str(pid),
            protocol.FIELD_X: _u_coord(qx, map_w),
            protocol.FIELD_Y: _u_coord(qy, map_h),
            protocol.FIELD_HEADING: _u_angle(qh),
            protocol.FIELD_ALIVE: bool(alive),
            protocol.FIELD_SCORE: score,
            protocol.FIELD_GIRTH: _u_girth(qg, max_girth),
            protocol.FIELD_LENGTH: float(length),
            protocol.FIELD_USERNAME: uname,
            protocol.FIELD_IS_BOT: bool(is_bot),
            protocol.FIELD_STRATEGY: strat,
            protocol.FIELD_BOOST: bool(boost),
        }
        if kind == 0:
            (ptc,) = struct.unpack_from(">H", view, pos); pos += 2
            pts = []
            for _ in range(ptc):
                (ax, ay) = struct.unpack_from(">HH", view, pos); pos += 4
                pts.append([_u_coord(ax, map_w), _u_coord(ay, map_h)])
            p[protocol.FIELD_POINTS] = pts
        else:
            (drop,) = struct.unpack_from(">H", view, pos); pos += 2
            (addc,) = struct.unpack_from(">H", view, pos); pos += 2
            add = []
            for _ in range(addc):
                (ax, ay) = struct.unpack_from(">HH", view, pos); pos += 4
                add.append([_u_coord(ax, map_w), _u_coord(ay, map_h)])
            p[protocol.FIELD_POINTS_DROP] = drop
            p[protocol.FIELD_POINTS_ADD] = add
        players.append(p)

    food = {
        protocol.FIELD_FOOD_ADD: [],
        protocol.FIELD_FOOD_MOVE: [],
        protocol.FIELD_FOOD_REMOVE: [],
    }
    for _ in range(fadd_c):
        pel, pos = _unpack_pellet(view, pos, map_w, map_h, food_max_r)
        food[protocol.FIELD_FOOD_ADD].append(pel)
    for _ in range(fmov_c):
        pel, pos = _unpack_pellet(view, pos, map_w, map_h, food_max_r)
        food[protocol.FIELD_FOOD_MOVE].append(pel)
    for _ in range(frem_c):
        (fid,) = struct.unpack_from(">I", view, pos); pos += 4
        food[protocol.FIELD_FOOD_REMOVE].append(str(fid))

    return {
        protocol.FIELD_TYPE: protocol.TYPE_SNAPSHOT,
        protocol.FIELD_TICK: tick,
        protocol.FIELD_PLAYERS: players,
        protocol.FIELD_FOOD: food,
    }


def _unpack_pellet(view, pos, map_w, map_h, food_max_r):
    (fid,) = struct.unpack_from(">I", view, pos); pos += 4
    (qx, qy) = struct.unpack_from(">HH", view, pos); pos += 4
    (qr,) = struct.unpack_from(">B", view, pos); pos += 1
    flags = view[pos]; pos += 1
    owner = None
    if flags & 2:
        (owner,) = struct.unpack_from(">I", view, pos); pos += 4
    pel = {
        protocol.FIELD_ID: str(fid),
        protocol.FIELD_X: _u_coord(qx, map_w),
        protocol.FIELD_Y: _u_coord(qy, map_h),
        protocol.FIELD_FOOD_RADIUS: _u_rad(qr, food_max_r),
        protocol.FIELD_FOOD_DROPPED: bool(flags & 1),
    }
    if owner is not None:
        pel[protocol.FIELD_FOOD_OWNER] = str(owner)
    return pel, pos
