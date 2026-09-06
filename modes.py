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

import math
import random

import bots
import config
import protocol


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


class ExtractionMode(GameMode):
    """A run-based economy: enter, carry, extract or die.

    One zone sits on the map. Reach it and your carrying score banks -- the
    run ends, the serpent leaves the map alive, and the zone relocates so the
    next banking costs another journey. Die and your carrying scatters as a
    carcass, but what you banked is safe. The leaderboard ranks banked, not
    carrying: points are not yours until you have walked out with them.
    """

    id = "extraction"
    name = "Extraction"
    description = "Bank your points at the zone before you die. What you carry is not yours yet."

    # The zone as {x, y, r}, or None until the first tick places it. Lives on
    # the instance, so each world's zone is its own.
    zone: "dict | None" = None

    def score_key(self, player):
        # The board shows secured wealth. Carrying is visible on your own HUD.
        return player.banked

    def bot_strategies(self):
        return [bots.ExtractBotStrategy]

    def welcome_fields(self):
        return {protocol.FIELD_ZONE: self.zone_dict()}

    def on_tick(self, world, dt):
        if self.zone is None:
            self._relocate(world)
            return
        zx, zy, zr = self.zone["x"], self.zone["y"], self.zone["r"]
        for player in list(world.players.values()):
            if not player.alive:
                continue
            reach = zr + player.girth
            dx = player.x - zx
            dy = player.y - zy
            if dx * dx + dy * dy <= reach * reach:
                world._extract_player(player)
                # One extraction per tick: the zone has moved, so anyone else
                # standing here waits for the next placement.
                self._relocate(world)
                break

    def zone_dict(self):
        if self.zone is None:
            return None
        return {"x": round(self.zone["x"], 2),
                "y": round(self.zone["y"], 2),
                "r": round(self.zone["r"], 2)}

    def _relocate(self, world):
        """Place the zone: inside the food disc, clear of every live serpent,
        and far enough from where it was last that banking costs a journey.

        The constraints are tried in order and relaxed after enough failed
        attempts, so a crowded map can never wedge the placement entirely.
        """
        cx = config.MAP_WIDTH / 2
        cy = config.MAP_HEIGHT / 2
        old = self.zone
        spot = None
        x, y = cx, cy  # loop fallback if no candidate satisfies anything
        for attempt in range(64):
            angle = random.uniform(0.0, math.tau)
            radius = config.FOOD_SPAWN_RADIUS * math.sqrt(random.random())
            x = min(float(config.MAP_WIDTH) - 1.0,
                    max(1.0, cx + math.cos(angle) * radius))
            y = min(float(config.MAP_HEIGHT) - 1.0,
                    max(1.0, cy + math.sin(angle) * radius))
            clear = all(
                (p.x - x) ** 2 + (p.y - y) ** 2
                >= config.EXTRACTION_ZONE_CLEARANCE ** 2
                for p in world.players.values() if p.alive
            )
            travel = (
                old is None or attempt >= 32 or
                (old["x"] - x) ** 2 + (old["y"] - y) ** 2
                >= config.EXTRACTION_ZONE_TRAVEL ** 2
            )
            if clear and travel:
                spot = (x, y)
                break
        if spot is None:
            # Crowded map: the last candidate is merely clear of serpents,
            # which is the constraint that keeps the mode playable.
            spot = (x, y)
        self.zone = {"x": spot[0], "y": spot[1],
                     "r": config.EXTRACTION_ZONE_RADIUS}
        world.broadcast({
            "type": "zone",
            "zone": self.zone_dict(),
        })


# Order is the order /api/modes serves them in.
REGISTRY: "list[type[GameMode]]" = [ClassicMode, HardcoreMode, ExtractionMode]


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
