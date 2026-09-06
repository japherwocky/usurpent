"""Game modes for USURPENT.

A mode describes how one World plays: which death rules are in force, what
the leaderboard ranks, and any per-tick machinery the mode owns (extraction
zones, run timers). The World calls the hooks; the mode never reaches into
the tick loop itself.

This is the third registry in the house style, beside bots.py (AI brains)
and carcass.py (death scatters): REGISTRY holds classes, and each World
instantiates its own mode object, so per-world state (a zone position, a
run timer) lives on the instance and worlds cannot interfere with one
another.

To add a mode: subclass GameMode, give it an id/name/description, override
the hooks it needs, and append the class to REGISTRY. The WS handshake picks
a mode with ?mode=<id>; unknown ids are refused at the door.
"""

import bots


class GameMode:
    """Base class for game modes.

    Subclasses set ``id`` (the ?mode= wire value), ``name`` and
    ``description`` (both served to clients via /api/modes), and override
    whichever hooks they need. The base class is classic slither: nothing
    overridden, nothing extra.
    """

    id: str
    name: str
    description: str = ""

    # When True, a serpent's own body is lethal to its head (hardcore).
    # _handle_collisions consults this per world; the grace arc that keeps
    # the neck from killing the head lives with the collision code.
    self_collision = False

    def on_tick(self, world, dt):
        """Mode-level per-tick logic, run inside the world's tick after
        collisions and before the snapshot goes out, so state a hook changes
        is broadcast the same tick. Override for zone machines, timers, etc.
        """

    def on_bank(self, world, player):
        """A player reached the mode's objective. Override to move score
        somewhere safer than a live serpent (extraction banks it)."""

    def score_key(self, player):
        """What the leaderboard sorts by. Classic ranks the live score;
        a run-based mode ranks what has been banked instead."""
        return player.score

    def bot_strategies(self):
        """Bot brains this mode spawns, round-robin. Return an empty list
        for a mode with no bots."""
        return list(bots.REGISTRY)

    def welcome_fields(self):
        """Extra fields merged into the welcome message, so a joining client
        learns mode state (a zone position) in the same breath as everything
        else it needs to render."""
        return {}


class ClassicMode(GameMode):
    """The straight slither clone: eat, grow, cut others off, don't get cut."""

    id = "classic"
    name = "Classic"
    description = "The straight slither clone. Eat, grow, and cut other serpents off."


class HardcoreMode(GameMode):
    """Classic rules plus a memory: your own tail is as lethal as anyone
    else's. Every turn is a commitment, and a long serpent has to plan its
    path or lie down in it."""

    id = "hardcore"
    name = "Hardcore"
    description = "Your own tail kills you. Every turn is a commitment."
    self_collision = True


# Order is the order /api/modes serves them in.
REGISTRY: "list[type[GameMode]]" = [ClassicMode, HardcoreMode]


def get_mode(mode_id):
    """Look up a mode class by its wire id, or None if unknown.

    Scans rather than caching a dict so tests can append to REGISTRY after
    import; the registry is a handful of classes and the lookup runs once
    per connection.
    """
    for mode_cls in REGISTRY:
        if mode_cls.id == mode_id:
            return mode_cls
    return None


def mode_list():
    """The /api/modes payload: what a client needs to render mode buttons."""
    return [
        {"id": m.id, "name": m.name, "description": m.description}
        for m in REGISTRY
    ]
