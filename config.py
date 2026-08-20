"""Gameplay tuning knobs for USURPENT.

All values are overridable via environment variables (prefix USURPENT_).
Defaults are chosen for mouse-target steering feel; see PLAN.md for the
reasoning behind each. No gameplay constant should be a bare literal
elsewhere in the codebase -- import from here instead.
"""

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
MAP_WIDTH = _env_int("USURPENT_MAP_WIDTH", 1000)
MAP_HEIGHT = _env_int("USURPENT_MAP_HEIGHT", 1000)

# Server simulation.
TICK_HZ = _env_int("USURPENT_TICK_HZ", 20)
HEAD_SPEED = _env_float("USURPENT_HEAD_SPEED", 120.0)          # units / second
MAX_TURN_RATE = _env_float("USURPENT_MAX_TURN_RATE", 6.0)      # radians / second

# Tail shape.
TAIL_SEGMENT_SPACING = _env_float("USURPENT_TAIL_SEGMENT_SPACING", 8.0)
INITIAL_TAIL_LENGTH = _env_int("USURPENT_INITIAL_TAIL_LENGTH", 20)

# Food.
FOOD_GROWTH = _env_int("USURPENT_FOOD_GROWTH", 5)
FOOD_COUNT = _env_int("USURPENT_FOOD_COUNT", 30)
FOOD_PICKUP_RADIUS = _env_float("USURPENT_FOOD_PICKUP_RADIUS", 14.0)

# Collisions.
COLLISION_RADIUS = _env_float("USURPENT_COLLISION_RADIUS", 10.0)

# Lifecycle.
RESPAWN_DELAY = _env_float("USURPENT_RESPAWN_DELAY", 1.5)      # seconds

# Persistence.
DATABASE_PATH = os.getenv("USURPENT_DATABASE_PATH", "usurpent.db")
