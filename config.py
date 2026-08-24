"""Gameplay tuning knobs for USURPENT.

All values are overridable via environment variables (prefix USURPENT_).
Defaults are chosen for mouse-target steering feel; see PLAN.md for the
reasoning behind each. No gameplay constant should be a bare literal
elsewhere in the codebase -- import from here instead.
"""

import logging
import os


def _env_int(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Map geometry (logical units, scaled to viewport on the client).
MAP_WIDTH = _env_int("USURPENT_MAP_WIDTH", 10000)
MAP_HEIGHT = _env_int("USURPENT_MAP_HEIGHT", 10000)

# Server simulation.
TICK_HZ = _env_int("USURPENT_TICK_HZ", 20)
HEAD_SPEED = _env_float("USURPENT_HEAD_SPEED", 80.0)           # units / second
# Minimum turning radius is HEAD_SPEED / MAX_TURN_RATE, so halving the rate
# doubles how wide the tightest turn is.
MAX_TURN_RATE = _env_float("USURPENT_MAX_TURN_RATE", 4.2)      # radians / second (base)
TURN_GIRTH_FALLOFF = _env_float("USURPENT_TURN_GIRTH_FALLOFF", 0.4)  # max turn-rate loss at MAX_GIRTH
# Boost: holding the boost control raises head speed by this factor. No cost
# yet -- a natural follow-up is to drain length/score while boosting.
BOOST_MULTIPLIER = _env_float("USURPENT_BOOST_MULTIPLIER", 1.8)

# Tail shape. `length` is a world-length target; the spacing between rendered
# segments scales with girth so circles overlap into a connected tube at every
# size (thin snakes get closer-spaced segments). spacing =
# max(MIN_SEGMENT_SPACING, girth * SEGMENT_SPACING_FACTOR).
SEGMENT_SPACING_FACTOR = _env_float("USURPENT_SEGMENT_SPACING_FACTOR", 0.333)
MIN_SEGMENT_SPACING = _env_float("USURPENT_MIN_SEGMENT_SPACING", 1.0)
# Segment count is length / spacing, so these two knobs are what control how
# long a serpent looks -- girth only sets how thick it is. Both were pulled
# back by ~10x because snakes were reaching full length far too quickly.
INITIAL_BODY_LENGTH = _env_int("USURPENT_INITIAL_BODY_LENGTH", 16)  # world units

# Body girth: the snake's thickness in world units. It grows as the snake eats
# and caps at MAX_GIRTH. Girth drives both the rendered body size and the
# collision size, so bigger snakes are bulkier and easier to hit.
BASE_GIRTH = _env_float("USURPENT_BASE_GIRTH", 6.0)
GIRTH_PER_FOOD = _env_float("USURPENT_GIRTH_PER_FOOD", 0.2)
MAX_GIRTH = _env_float("USURPENT_MAX_GIRTH", 24.0)

# Food.
# Each pellet carries a radius and a value; bigger pellets are worth more
# (value = round(radius / FOOD_RADIUS_PER_VALUE), minimum 1). Eating a pellet
# adds `value` to score and `value * FOOD_GROWTH` to tail length.
BODY_GROWTH = _env_int("USURPENT_BODY_GROWTH", 2)             # world-length units per pellet value
FOOD_COUNT = _env_int("USURPENT_FOOD_COUNT", 30)               # initial seed at start
FOOD_BASE_RADIUS = _env_float("USURPENT_FOOD_BASE_RADIUS", 5.0)
FOOD_RADIUS_PER_VALUE = _env_float("USURPENT_FOOD_RADIUS_PER_VALUE", 10.0)
FOOD_PICKUP_PAD = _env_float("USURPENT_FOOD_PICKUP_PAD", 10.0) # added to pellet radius for pickup

# Continuous spawning: instead of a fixed pool that runs out, the server drops
# new food on a timer inside a circle centered on the map. This keeps the game
# going indefinitely.
FOOD_SPAWN_INTERVAL = _env_float("USURPENT_FOOD_SPAWN_INTERVAL", 5.0)  # seconds
FOOD_SPAWN_RADIUS = _env_int("USURPENT_FOOD_SPAWN_RADIUS", 4000)       # from map center
FOOD_MAX = _env_int("USURPENT_FOOD_MAX", 1000)                         # cap to bound growth

# Death: a slain serpent leaves a carcass of food pellets -- one per body
# segment, sized from its girth. Dropped pellets render at lower opacity.
DROP_RADIUS_FACTOR = _env_float("USURPENT_DROP_RADIUS_FACTOR", 0.4)    # carcass radius = girth * this
CARCASS_MAX_PELLETS = _env_int("USURPENT_CARCASS_MAX_PELLETS", 400)    # sample if longer
# Pellets are thrown clear of the spine in one of the shapes in carcass.py,
# picked at random per death. Spread scales with girth, so a big serpent
# leaves a correspondingly big mess.
CARCASS_SPREAD_FACTOR = _env_float("USURPENT_CARCASS_SPREAD_FACTOR", 6.0)
# Serpents are only a handful of segments long now, so one pellet per segment
# left too little for a scatter pattern to read as a pattern. Subdivide the
# body path this many times before scattering to get the shape back.
CARCASS_PELLETS_PER_SEGMENT = _env_int("USURPENT_CARCASS_PELLETS_PER_SEGMENT", 4)

# Pellet gravity: loose pellets drift toward nearby pellets and merge on
# contact, so a scattered carcass slowly gathers itself into a few fat blobs
# instead of littering the map. This is a gameplay hook (big blobs are worth
# hunting, and a fresh kill is a feast that clumps up while you race for it)
# and it is what keeps the food list small on its own -- FOOD_MAX is only the
# backstop. Merging conserves value exactly: a blob is worth what its crumbs
# were worth, so the score economy is unchanged.
FOOD_ATTRACT_RADIUS = _env_float("USURPENT_FOOD_ATTRACT_RADIUS", 140.0)  # pull range
# Drift speed for a value-1 crumb, in world units/sec. HEAD_SPEED is 80, so
# this is deliberately a slow crawl -- you should be able to watch a carcass
# gather, and always outrun it.
FOOD_ATTRACT_SPEED = _env_float("USURPENT_FOOD_ATTRACT_SPEED", 7.0)
# Both gravity passes work on a rota rather than the whole field every tick:
# each tick only the shard whose pellet id matches gets its neighbourhood
# scanned. Ids are handed out in sequence, so a carcass spreads itself evenly
# across the rota. Drift steps are scaled by the shard count, so this buys
# cost and not slowness (use FOOD_ATTRACT_SPEED for slowness). It also flattens
# the cost spike when a big carcass lands and a thousand crumbs want to fuse
# on the same tick.
FOOD_GRAVITY_SHARDS = _env_int("USURPENT_FOOD_GRAVITY_SHARDS", 8)
FOOD_MERGE_MAX_RADIUS = _env_float("USURPENT_FOOD_MERGE_MAX_RADIUS", 34.0)  # blobs stop growing here
# How deeply two pellets must overlap before they fuse, as a fraction of
# (r1 + r2). At 1.0 they merge the instant their circles graze -- which means
# a fresh carcass, whose crumbs are dropped closer together than their own
# diameter, collapses on the very first tick and the drift never shows. Lower
# values make pellets travel visibly toward each other before fusing. At 0.25
# a fresh carcass lands as a lootable field of crumbs that visibly crawls
# together over the next ten seconds or so.
FOOD_MERGE_OVERLAP = _env_float("USURPENT_FOOD_MERGE_OVERLAP", 0.25)

# Bots: server-side AI snakes that play alongside humans. Each bot runs a
# "strategy" (see bots.py) so different AIs can compete. BOT_COUNT is the
# number of bots at start; they respawn automatically to keep the count
# constant. The steering knobs below tune how cautiously bots move.
BOT_COUNT = _env_int("USURPENT_BOT_COUNT", 6)                  # bots at start
BOT_WALL_MARGIN = _env_float("USURPENT_BOT_WALL_MARGIN", 300.0)    # steer to center this close to an edge
BOT_AVOID_RADIUS = _env_float("USURPENT_BOT_AVOID_RADIUS", 120.0)  # body-avoidance sense radius
BOT_AVOID_WEIGHT = _env_float("USURPENT_BOT_AVOID_WEIGHT", 4000.0) # how strongly bodies push bots away

# Collisions. A head dies if it enters (attacker girth + defender girth) of any
# body point of another snake. Self-collision is intentionally off.

# Lifecycle.
RESPAWN_DELAY = _env_float("USURPENT_RESPAWN_DELAY", 1.5)      # seconds

# Persistence.
DATABASE_PATH = os.getenv("USURPENT_DATABASE_PATH", "usurpent.db")


# Auth / cookies.
def cookie_secret(debug=False):
    """The secret used to sign cookies (mirrors pearachute's convention).

    Raises in production if COOKIE_SECRET was never set. A weak-but-present
    value only warns: failing a deploy over secret length is worse than
    saying so.
    """
    DEV_COOKIE_SECRET = "changemeplz-dev-only"
    MIN_SECRET_LENGTH = 32

    secret = os.getenv("COOKIE_SECRET", DEV_COOKIE_SECRET)

    if secret == DEV_COOKIE_SECRET and not debug:
        raise ValueError(
            "COOKIE_SECRET environment variable must be set for production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    if not debug and len(secret) < MIN_SECRET_LENGTH:
        logging.warning(
            "COOKIE_SECRET is only %d characters; %d or more is recommended",
            len(secret), MIN_SECRET_LENGTH,
        )

    return secret
