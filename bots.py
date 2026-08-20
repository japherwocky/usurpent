"""Bot AI strategies for USURPENT.

A strategy is a small object with a ``think(world, bot)`` method that sets the
bot's steering target each tick. The base class defines the contract; concrete
strategies compete by out-eating and out-surviving one another. To add a new
brain, subclass :class:`BotStrategy`, set ``name``/``color``, implement
``think``, and append it to ``REGISTRY`` so the world will spawn it.
"""

import math
import random

import config


def _nearest_food(world, bot):
    """Return the food dict closest to the bot, or None if no food exists."""
    best = None
    best_d = None
    for food in world.foods.values():
        d = (food["x"] - bot.x) ** 2 + (food["y"] - bot.y) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best = food
    return best


def _avoid_bodies(world, bot, radius):
    """Repulsion vector (ax, ay) pushing the bot away from nearby body points
    of other live snakes. Sampled every 3rd point to stay cheap."""
    ax = ay = 0.0
    for other in world.players.values():
        if other is bot or not other.alive:
            continue
        for px, py in other.points[::3]:
            dx = bot.x - px
            dy = bot.y - py
            d2 = dx * dx + dy * dy
            if 0 < d2 < radius * radius:
                inv = 1.0 / d2
                ax += dx * inv
                ay += dy * inv
    return ax, ay


def _near_wall(bot, margin):
    return (bot.x < margin or bot.x > config.MAP_WIDTH - margin or
            bot.y < margin or bot.y > config.MAP_HEIGHT - margin)


def _to_center(bot):
    """Direction vector from the bot toward the map center."""
    return (config.MAP_WIDTH / 2 - bot.x, config.MAP_HEIGHT / 2 - bot.y)


class BotStrategy:
    """Base class for bot brains.

    Subclasses set ``name`` (sent to clients so they can color bots by
    strategy) and ``color`` (a hex string clients use for that strategy), and
    override :meth:`think`.
    """

    name = "base"
    color = "#9aa5b1"  # neutral grey, overridden by subclasses

    def think(self, world, bot):
        """Set ``bot.target`` to a steering direction (dx, dy). Override."""
        raise NotImplementedError


class FoodSeekerStrategy(BotStrategy):
    """Chase the nearest pellet; retreat to center near walls; dodge bodies."""

    name = "seeker"
    color = "#ff4d6d"

    def think(self, world, bot):
        if _near_wall(bot, config.BOT_WALL_MARGIN):
            dx, dy = _to_center(bot)
        else:
            food = _nearest_food(world, bot)
            if food is not None:
                dx = food["x"] - bot.x
                dy = food["y"] - bot.y
            else:
                dx, dy = _to_center(bot)
        ax, ay = _avoid_bodies(world, bot, config.BOT_AVOID_RADIUS)
        bot.set_target(dx + ax * config.BOT_AVOID_WEIGHT,
                       dy + ay * config.BOT_AVOID_WEIGHT)


class WandererStrategy(BotStrategy):
    """Roam on a slowly drifting heading; ignore food. A 'dumb' baseline so
    smarter strategies have something to beat in the competition."""

    name = "wanderer"
    color = "#4dd2ff"

    def __init__(self):
        self._heading = random.uniform(-math.pi, math.pi)

    def think(self, world, bot):
        if _near_wall(bot, config.BOT_WALL_MARGIN):
            dx, dy = _to_center(bot)
        else:
            # Wander: nudge the heading a little each tick for organic motion.
            self._heading += random.uniform(-0.3, 0.3)
            dx = math.cos(self._heading)
            dy = math.sin(self._heading)
        ax, ay = _avoid_bodies(world, bot, config.BOT_AVOID_RADIUS)
        bot.set_target(dx + ax * config.BOT_AVOID_WEIGHT,
                       dy + ay * config.BOT_AVOID_WEIGHT)


# Round-robin across these when spawning bots, so strategies compete head-to-head.
REGISTRY = [FoodSeekerStrategy, WandererStrategy]
