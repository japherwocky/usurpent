"""WebSocket message protocol for USURPENT.

Every message is a JSON object with a "type" field. Client and server both
import these constants so the wire format stays in one place and we never
hand-write a message type string elsewhere.
"""

# Message types.
TYPE_INPUT = "input"
TYPE_WELCOME = "welcome"
TYPE_SNAPSHOT = "snapshot"
# Standings, sent on its own slow cadence rather than riding the snapshot.
# Snapshots only carry serpents a client can see, so the leaderboard can no
# longer be derived from one -- and it never wanted to be, since it is read at
# a glance and was being rebuilt twenty times a second.
TYPE_LEADERBOARD = "leaderboard"

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
# The range of pellet radii the server can produce: a freshly spawned crumb
# and a blob that has merged its way to the cap. The client ramps pellet
# colour across this, so it has to be told the real ends rather than baking
# in a guess that silently drifts when the food constants are retuned.
# Cell sizes of the two SpatialGrids, so the debug overlay draws the grid the
# server is actually bucketing into rather than a plausible-looking guess.
FIELD_FOOD_GRID_CELL = "food_grid_cell"
FIELD_BODY_GRID_CELL = "body_grid_cell"
FIELD_FOOD_MIN_RADIUS = "food_min_radius"
FIELD_FOOD_MAX_RADIUS = "food_max_radius"

# Leaderboard message fields.
FIELD_ENTRIES = "entries"      # top N, each {id, username, score, is_bot, strategy}
FIELD_RANK = "rank"            # 1-based standing, so a viewer outside the top
                               # N still knows where they sit
FIELD_TOTAL_PLAYERS = "total"  # counts cover the whole map, not the slice a
FIELD_TOTAL_BOTS = "bots"      # client can see, or the stats panel would
                               # report the world shrinking as you walk away

# Per-player fields inside a snapshot's player list.
FIELD_ID = "id"
FIELD_HEADING = "heading"
FIELD_POINTS = "points"
# A body arrives in full the first time a viewer sees a serpent, and after
# that only as what changed: the points appended at the head since their last
# snapshot, and how many fell off the tail. Interior points never move (see
# the queue invariant in netcode.js), so re-sending them every tick was the
# bulk of the payload describing nothing new.
FIELD_POINTS_ADD = "add"
FIELD_POINTS_DROP = "drop"
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
