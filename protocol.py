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
FIELD_TARGET = "target"
FIELD_X = "x"
FIELD_Y = "y"
FIELD_MAP_WIDTH = "map_width"
FIELD_MAP_HEIGHT = "map_height"

# Per-player fields inside a snapshot's player list.
FIELD_ID = "id"
FIELD_HEADING = "heading"
FIELD_POINTS = "points"
FIELD_ALIVE = "alive"
FIELD_SCORE = "score"
