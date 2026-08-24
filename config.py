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
# long a serpent looks -- girth only sets how thick it is.
INITIAL_BODY_LENGTH = _env_int("USURPENT_INITIAL_BODY_LENGTH", 16)  # world units

# Body girth: the snake's thickness in world units. It grows as the snake eats
# and caps at MAX_GIRTH. Girth drives both the rendered body size and the
# collision size, so bigger snakes are bulkier and easier to hit.
BASE_GIRTH = _env_float("USURPENT_BASE_GIRTH", 6.0)
MAX_GIRTH = _env_float("USURPENT_MAX_GIRTH", 24.0)
# The score at which a serpent reaches MAX_GIRTH -- this is the knob, not the
# per-food increment. As an increment of 0.2 it read as a small number while
# meaning full thickness at score 90: on a leaderboard running to five
# figures every serpent was identically fat within seconds of spawning and
# the entire girth curve was dead weight. Expressed as a score it is a number
# you can hold against the leaderboard and reason about.
MAX_GIRTH_SCORE = _env_float("USURPENT_MAX_GIRTH_SCORE", 10000.0)
# Where the growth curve does its growing. Both girth and length run on
# log1p(score / GROWTH_KNEE), normalised to reach their maximum at
# MAX_GIRTH_SCORE, so this is the score around which growth stops feeling fast.
# Linear was the wrong shape at both ends: on a ten-thousand point curve the
# first hundred points moved a serpent one percent and felt like nothing, and
# the last thousand were equally invisible for the opposite reason. On a log,
# a new serpent grows visibly from its first few pellets -- the first hundred
# points are worth about fifteen percent of the whole curve -- while the top of
# the leaderboard still has somewhere to go.
GROWTH_KNEE = _env_float("USURPENT_GROWTH_KNEE", 100.0)

# Food.
# Each pellet carries a radius and a value; bigger pellets are worth more
# (value = round(radius / FOOD_RADIUS_PER_VALUE), minimum 1). Eating a pellet
# adds `value` to score and `value * FOOD_GROWTH` to tail length.
# Body length once a serpent has reached MAX_GIRTH_SCORE. With
# INITIAL_BODY_LENGTH and GROWTH_KNEE this fixes the whole length curve, which
# is derived from score rather than accumulated per pellet -- a curve cannot be
# held by adding a constant per bite. Segment count is length / spacing, and
# _handle_collisions tests every head against every point of every other body,
# so this constant sets the per-tick collision cost as much as it sets how long
# a serpent looks. The log curve also bounds the top end: past this score
# length keeps growing, but slowly, instead of running away with the score.
BODY_LENGTH_AT_MAX_GIRTH = _env_float("USURPENT_BODY_LENGTH_AT_MAX_GIRTH", 2000.0)
FOOD_COUNT = _env_int("USURPENT_FOOD_COUNT", 4000)             # initial seed at start
# A spawned pellet is the smallest thing on the map and the unit the rest of
# the food scale is read against, so it wants to be visibly a crumb next to a
# gathered blob (which caps at FOOD_MERGE_MAX_RADIUS). It also sets how
# densely a fresh carcass can land without its pellets starting out already
# inside one another -- see FOOD_MERGE_OVERLAP.
FOOD_BASE_RADIUS = _env_float("USURPENT_FOOD_BASE_RADIUS", 2.0)
FOOD_RADIUS_PER_VALUE = _env_float("USURPENT_FOOD_RADIUS_PER_VALUE", 10.0)
FOOD_PICKUP_PAD = _env_float("USURPENT_FOOD_PICKUP_PAD", 10.0) # added to pellet radius for pickup

# Continuous spawning: instead of a fixed pool that runs out, the server drops
# new food on a timer inside a circle centered on the map. This keeps the game
# going indefinitely.
# One pellet every five seconds could never fill a field of thousands, let
# alone keep up with seven snakes eating, so the timer drops a batch. Together
# these top the map up at FOOD_SPAWN_BATCH / FOOD_SPAWN_INTERVAL pellets a
# second, which comfortably outpaces consumption and holds the field near
# FOOD_MAX -- the spawner stops there.
FOOD_SPAWN_INTERVAL = _env_float("USURPENT_FOOD_SPAWN_INTERVAL", 0.2)  # seconds
FOOD_SPAWN_BATCH = _env_int("USURPENT_FOOD_SPAWN_BATCH", 8)            # pellets per drop
FOOD_SPAWN_RADIUS = _env_int("USURPENT_FOOD_SPAWN_RADIUS", 4000)       # from map center
# Cap to bound growth. 8000 measures at 44% of the tick budget at its peak
# with four players connected, which leaves room for a carcass landing on a
# bad tick. Past about 10000 the margin gets thin enough that a GC pause could
# overrun a tick.
FOOD_MAX = _env_int("USURPENT_FOOD_MAX", 8000)
# Interest management: a client is only sent the food inside a box this far
# either side of its head, rather than the whole map. Snapshot size stops
# tracking the size of the world and starts tracking what you can actually
# see, which is what lets FOOD_MAX be in the thousands.
#
# This must exceed any client's half-viewport or pellets pop in at the screen
# edge, but every unit past that is bandwidth spent on food nobody can see.
# The client shows VIEW_WORLD (600) units across its SHORTER axis, so width is
# what stretches: 1280x800 needs 480, 3440x1440 needs 717, and a 5120x1440
# super-ultrawide 1067. 1200 covers all of them with room for the head to
# travel between snapshots.
#
# The server cannot know a given window, so this is sized for the widest one.
# Having clients report their viewport would let it track the actual window
# and cut the payload again for the common case.
INTEREST_RADIUS = _env_float("USURPENT_INTEREST_RADIUS", 1200.0)
# Floor for a client-reported view distance, so a bogus or hostile value
# cannot leave someone unable to see the food in front of them.
INTEREST_MIN_RADIUS = _env_float("USURPENT_INTEREST_MIN_RADIUS", 400.0)
# Added to whatever a client reports, covering the ground its head can cover
# between snapshots plus a little slack so pellets are never seen arriving.
INTEREST_MARGIN = _env_float("USURPENT_INTEREST_MARGIN", 120.0)
# Cell size of the coarse interest grid that _food_list queries, instead of
# scanning every pellet for every viewer each tick. Sized around the interest
# radius -- NOT the fine merge/pickup grid (that is ~58u and would be far too
# many buckets for a query this wide). A viewer's query block is a few of these
# cells across, so the cell must be small enough that the block hugs the reach
# box (a big cell forces a wide block that visits most of the map anyway) yet
# large enough not to explode the bucket count. Measured across field sizes,
# ~INTEREST_RADIUS/8 tracks the reach box tightly enough to win at both the
# FOOD_MAX ceiling and well beyond, while staying far coarser than the 58u fine
# grid.
INTEREST_GRID_CELL = _env_float("USURPENT_INTEREST_GRID_CELL", INTEREST_RADIUS / 8.0)

# Death: a slain serpent leaves a carcass of food pellets -- one per body
# segment, sized from its girth. Dropped pellets render at lower opacity.
DROP_RADIUS_FACTOR = _env_float("USURPENT_DROP_RADIUS_FACTOR", 0.4)    # carcass radius = girth * this
CARCASS_MAX_PELLETS = _env_int("USURPENT_CARCASS_MAX_PELLETS", 400)    # sample if longer
# Pellets are thrown clear of the spine in one of the shapes in carcass.py,
# picked at random per death. Spread scales with girth, so a big serpent
# leaves a correspondingly big mess. This is the width of the ribbon the
# pattern draws around the body path: at 6.0 a maxed serpent threw its crumbs
# 144 units clear, a quarter of the 600 units of world a client can see, so
# the shapes were technically there and far too narrow to read as shapes.
# At 16.0 the spray is 384 units across and a helix looks like a helix.
CARCASS_SPREAD_FACTOR = _env_float("USURPENT_CARCASS_SPREAD_FACTOR", 16.0)
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
# Drift speed for a value-1 crumb at point-blank range, in world units/sec.
# HEAD_SPEED is 80, so even at full pull a crumb moves at a fiftieth of a
# serpent's pace: gathering a carcass is an animation you catch in progress,
# not something that resolves while you watch.
FOOD_ATTRACT_SPEED = _env_float("USURPENT_FOOD_ATTRACT_SPEED", 1.6)
# How sharply the pull strengthens as pellets close. The drift used to be a
# flat speed in the direction of the surrounding mass -- the distance to that
# mass cancelled out of the step entirely, so a crumb at the rim of the pull
# range crept in at exactly the pace of one already touching a blob. It read
# as a conveyor belt rather than gravity. The step is now scaled by a
# closeness ramp, raised to this power: 1.0 is a linear ramp, 2.0 accelerates
# into contact the way a real pull does.
FOOD_ATTRACT_FALLOFF = _env_float("USURPENT_FOOD_ATTRACT_FALLOFF", 2.0)
# Floor under that ramp. Without it a pellet at the edge of the mesh's reach
# would have no pull at all and outliers from a wide carcass scatter would
# simply sit there forever instead of eventually finding their way in.
FOOD_ATTRACT_MIN = _env_float("USURPENT_FOOD_ATTRACT_MIN", 0.2)
# Both gravity passes work on a rota rather than the whole field every tick:
# each tick only the shard whose pellet id matches gets its neighbourhood
# scanned. Ids are handed out in sequence, so a carcass spreads itself evenly
# across the rota. Drift steps are scaled by the shard count, so this buys
# cost and not slowness (use FOOD_ATTRACT_SPEED for slowness). It also flattens
# the cost spike when a big carcass lands and a thousand crumbs want to fuse
# on the same tick.
FOOD_GRAVITY_SHARDS = _env_int("USURPENT_FOOD_GRAVITY_SHARDS", 8)
FOOD_MERGE_MAX_RADIUS = _env_float("USURPENT_FOOD_MERGE_MAX_RADIUS", 34.0)  # blobs stop growing here
# How close two pellets must be before they fuse, as a fraction of (r1 + r2).
# 1.0 fuses the instant their circles graze; lower values require them to
# interpenetrate first. This was 0.25, which meant two touching crumbs had to
# close to a quarter of their combined radii -- most of the way to concentric
# -- before merging, so pellets visibly sat inside one another waiting. 0.8
# fuses just after the circles meet, which reads as two blobs coalescing.
# The reason it was ever set so low is that a fresh carcass drops crumbs
# closer together than their own diameter, so a high value collapsed the
# whole thing on the first tick and the drift never showed. A smaller
# FOOD_BASE_RADIUS and the closeness ramp on the pull are what buy that back:
# the crumbs start apart, so they have somewhere to travel from.
FOOD_MERGE_OVERLAP = _env_float("USURPENT_FOOD_MERGE_OVERLAP", 0.8)

# Leaderboard: sent as its own message, because snapshots now carry only the
# serpents a client can see and standings are global. Slow on purpose -- it is
# glanceable text, not gameplay, and at TICK_HZ it was being rebuilt twenty
# times a second to be read maybe once.
LEADERBOARD_SIZE = _env_int("USURPENT_LEADERBOARD_SIZE", 10)
LEADERBOARD_HZ = _env_float("USURPENT_LEADERBOARD_HZ", 2.0)

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
