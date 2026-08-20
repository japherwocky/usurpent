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

# Food.
FOOD_GROWTH = _env_int("USURPENT_FOOD_GROWTH", 5)
FOOD_COUNT = _env_int("USURPENT_FOOD_COUNT", 30)               # initial seed at start
FOOD_PICKUP_RADIUS = _env_float("USURPENT_FOOD_PICKUP_RADIUS", 14.0)

# Continuous spawning: instead of a fixed pool that runs out, the server drops
# new food on a timer inside a circle centered on the map. This keeps the game
# going indefinitely.
FOOD_SPAWN_INTERVAL = _env_float("USURPENT_FOOD_SPAWN_INTERVAL", 5.0)  # seconds
FOOD_SPAWN_RADIUS = _env_int("USURPENT_FOOD_SPAWN_RADIUS", 4000)       # from map center
FOOD_MAX = _env_int("USURPENT_FOOD_MAX", 1000)                         # cap to bound growth

# Collisions.
COLLISION_RADIUS = _env_float("USURPENT_COLLISION_RADIUS", 10.0)

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
