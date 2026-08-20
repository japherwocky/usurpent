"""WebSocket message protocol for USURPENT.

Every message is a JSON object with a "type" field. Client and server both
import these constants so the wire format stays in one place and we never
hand-write a message type string elsewhere.
"""

# Message types.
TYPE_INPUT = "input"
TYPE_WELCOME = "welcome"
TYPE_SNAPSHOT = "snapshot"

# Common field names.
FIELD_TYPE = "type"
FIELD_SELF_ID = "self_id"
FIELD_TICK = "tick"
FIELD_PLAYERS = "players"
FIELD_TARGET = "target"  # steering direction vector (dx, dy) in world space
FIELD_X = "x"
FIELD_Y = "y"
FIELD_MAP_WIDTH = "map_width"
FIELD_MAP_HEIGHT = "map_height"
FIELD_FOOD = "food"
FIELD_HEAD_SPEED = "head_speed"
FIELD_MAX_TURN_RATE = "max_turn_rate"
FIELD_SEGMENT_SPACING_FACTOR = "segment_spacing_factor"
FIELD_MIN_SEGMENT_SPACING = "min_segment_spacing"
FIELD_LENGTH = "length"
FIELD_TICK_HZ = "tick_hz"
FIELD_FOOD_SPAWN_RADIUS = "food_spawn_radius"
FIELD_BASE_GIRTH = "base_girth"
FIELD_MAX_GIRTH = "max_girth"
FIELD_TURN_GIRTH_FALLOFF = "turn_girth_falloff"

# Per-player fields inside a snapshot's player list.
FIELD_ID = "id"
FIELD_HEADING = "heading"
FIELD_POINTS = "points"
FIELD_ALIVE = "alive"
FIELD_SCORE = "score"
FIELD_USERNAME = "username"
FIELD_GUEST = "guest"
FIELD_GIRTH = "girth"
FIELD_FOOD_RADIUS = "r"
FIELD_FOOD_DROPPED = "dropped"
FIELD_IS_BOT = "is_bot"
FIELD_STRATEGY = "strategy"
