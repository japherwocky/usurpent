"""Carcass scatter patterns for USURPENT.

When a serpent dies its body is scattered into food pellets. A pattern decides
where those pellets land relative to the body path, and the world picks one at
random per death so no two carcasses look alike.

A pattern is a function with the contract::

    scatter(points, spread) -> [(x, y), ...]

where ``points`` are the sampled body points (head first) and ``spread`` is how
far off the spine pellets may throw, in world units. It must return exactly one
position per input point. To add a shape, write the function and append it to
:data:`REGISTRY`.

Pellet gravity then pulls whatever lands here back together (see
``World._attract_food``), so a pattern only sets the opening arrangement --
every one of these converges to a handful of fat blobs within a few seconds.
"""

import math

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))  # ~137.5 degrees


def subdivide(points, factor):
    """Insert `factor - 1` evenly spaced points between each pair of body points.

    Serpents are only a handful of segments long, so scattering one pellet per
    segment leaves too few to read as a shape. Densifying the spine first gives
    the patterns something to work with without changing where the body was.
    """
    if factor <= 1 or len(points) < 2:
        return list(points)
    out = []
    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        for step in range(factor):
            t = step / factor
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    out.append(points[-1])
    return out


def _frames(points):
    """Unit tangent and normal at each body point, as (tx, ty, nx, ny).

    Sampling neighbours rather than the raw heading keeps this correct for
    carcasses that were decimated down to CARCASS_MAX_PELLETS.
    """
    frames = []
    last = len(points) - 1
    for i in range(len(points)):
        ax, ay = points[max(i - 1, 0)]
        bx, by = points[min(i + 1, last)]
        tx, ty = bx - ax, by - ay
        mag = math.hypot(tx, ty) or 1.0
        tx, ty = tx / mag, ty / mag
        frames.append((tx, ty, -ty, tx))
    return frames


def scatter_spine(points, spread):
    """Pellets fall exactly on the body path -- a clean, undisturbed trail."""
    return list(points)


def scatter_ribs(points, spread):
    """Herringbone struts alternating either side of the spine, like bones."""
    out = []
    frames = _frames(points)
    for i, (x, y) in enumerate(points):
        _, _, nx, ny = frames[i]
        side = 1.0 if (i // 4) % 2 == 0 else -1.0
        reach = ((i % 4) + 1) / 4.0
        out.append((x + nx * spread * reach * side, y + ny * spread * reach * side))
    return out


def scatter_helix(points, spread):
    """A coiled ribbon: the offset swings sinusoidally along the spine."""
    out = []
    frames = _frames(points)
    for i, (x, y) in enumerate(points):
        tx, ty, nx, ny = frames[i]
        phase = i * 0.40
        off = math.sin(phase) * spread
        along = math.cos(phase) * spread * 0.30
        out.append((x + nx * off + tx * along, y + ny * off + ty * along))
    return out


def scatter_phyllotaxis(points, spread):
    """Golden-angle spray: an even, non-repeating band around the spine."""
    out = []
    frames = _frames(points)
    for i, (x, y) in enumerate(points):
        tx, ty, nx, ny = frames[i]
        theta = i * GOLDEN_ANGLE
        # sqrt keeps the disc evenly filled instead of crowding the centre
        reach = spread * math.sqrt((i % 34) / 34.0)
        cos_t, sin_t = math.cos(theta) * reach, math.sin(theta) * reach
        out.append((x + nx * cos_t + tx * sin_t, y + ny * cos_t + ty * sin_t))
    return out


def scatter_rosettes(points, spread):
    """Evenly spaced rings along the body, like a string of beads."""
    out = []
    frames = _frames(points)
    last = len(points) - 1
    per_ring = 10
    reach = spread * 0.75
    for i in range(len(points)):
        hub = min((i // per_ring) * per_ring, last)
        hx, hy = points[hub]
        tx, ty, nx, ny = frames[hub]
        theta = (i % per_ring) / per_ring * 2.0 * math.pi
        cos_t, sin_t = math.cos(theta) * reach, math.sin(theta) * reach
        out.append((hx + nx * cos_t + tx * sin_t, hy + ny * cos_t + ty * sin_t))
    return out


# Picked from at random on each death, so deaths stay visually varied.
REGISTRY = [
    scatter_spine,
    scatter_ribs,
    scatter_helix,
    scatter_phyllotaxis,
    scatter_rosettes,
]
