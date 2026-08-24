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
FIELD_BOOST = "boost"    # bool: speed boost requested (held control)
# How far the client can actually see, in world units from its head: half of
# the larger viewport axis. Interest management sends food within this rather
# than within a fixed radius sized for the widest window anyone might have, so
# an ordinary window costs a fraction of an ultrawide. Sent on connect as a
# query arg and again with input, so a resize takes effect. The server clamps
# it -- a client asking for the whole map would just be told no.
FIELD_VIEW = "view"
# bool: the player clicked RESPAWN on the death card. Humans stay dead until
# they ask, so the card can hold the score they just earned; bots keep the
# timer. RESPAWN_DELAY still applies as a floor, so the click cannot skip the
# beat between dying and coming back.
FIELD_RESPAWN = "respawn"
FIELD_X = "x"
FIELD_Y = "y"
FIELD_MAP_WIDTH = "map_width"
FIELD_MAP_HEIGHT = "map_height"
FIELD_FOOD = "food"
FIELD_HEAD_SPEED = "head_speed"
FIELD_MAX_TURN_RATE = "max_turn_rate"
FIELD_BOOST_MULTIPLIER = "boost_multiplier"
FIELD_SEGMENT_SPACING_FACTOR = "segment_spacing_factor"
FIELD_MIN_SEGMENT_SPACING = "min_segment_spacing"
FIELD_LENGTH = "length"
FIELD_TICK_HZ = "tick_hz"
FIELD_FOOD_SPAWN_RADIUS = "food_spawn_radius"
FIELD_BASE_GIRTH = "base_girth"
FIELD_MAX_GIRTH = "max_girth"
FIELD_TURN_GIRTH_FALLOFF = "turn_girth_falloff"
# Seconds a dead player must wait before a respawn request is honoured. Sent
# in the welcome so the client can time the death card's button instead of
# hardcoding a number the server owns.
FIELD_RESPAWN_DELAY = "respawn_delay"

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
# Id of the serpent a carcass pellet came from, so the client can tint it that
# serpent's color. Only present on dropped pellets. The client already has the
# whole player list each snapshot, so it resolves the color itself rather than
# us duplicating the palette server-side; one short field keeps food -- the
# dominant term in snapshot size -- cheap.
FIELD_FOOD_OWNER = "own"
FIELD_IS_BOT = "is_bot"
FIELD_STRATEGY = "strategy"
