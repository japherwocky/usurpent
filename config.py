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
MAX_TURN_RATE = _env_float("USURPENT_MAX_TURN_RATE", 6.0)      # radians / second

# Tail shape.
TAIL_SEGMENT_SPACING = _env_float("USURPENT_TAIL_SEGMENT_SPACING", 8.0)
INITIAL_TAIL_LENGTH = _env_int("USURPENT_INITIAL_TAIL_LENGTH", 20)

# Body girth: the snake's thickness in world units. It grows as the snake eats
# and caps at MAX_GIRTH. Girth drives both the rendered body size and the
# collision size, so bigger snakes are bulkier and easier to hit.
BASE_GIRTH = _env_float("USURPENT_BASE_GIRTH", 6.0)
GIRTH_PER_FOOD = _env_float("USURPENT_GIRTH_PER_FOOD", 0.4)
MAX_GIRTH = _env_float("USURPENT_MAX_GIRTH", 24.0)

# Food.
# Each pellet carries a radius and a value; bigger pellets are worth more
# (value = round(radius / FOOD_RADIUS_PER_VALUE), minimum 1). Eating a pellet
# adds `value` to score and `value * FOOD_GROWTH` to tail length.
FOOD_GROWTH = _env_int("USURPENT_FOOD_GROWTH", 5)              # tail length per value point
FOOD_COUNT = _env_int("USURPENT_FOOD_COUNT", 30)               # initial seed at start
FOOD_BASE_RADIUS = _env_float("USURPENT_FOOD_BASE_RADIUS", 10.0)
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
DROP_RADIUS_FACTOR = _env_float("USURPENT_DROP_RADIUS_FACTOR", 0.8)    # carcass radius = girth * this
CARCASS_MAX_PELLETS = _env_int("USURPENT_CARCASS_MAX_PELLETS", 400)    # sample if longer

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
