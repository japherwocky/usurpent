// USURPENT client netcode — ported from static/game.js.
//
// The server is authoritative. We send our mouse target, then:
//   - predict OUR OWN snake locally each animation frame (instant response),
//     reconciling to the server snapshot when it arrives;
//   - interpolate OTHER players between the last two snapshots by time, so
//     they glide smoothly instead of jumping at the tick rate.
//
// This module is framework-agnostic; the Svelte component drives it: it feeds
// welcome/snapshot messages in and reads renderList()/alpha() out each frame.

const SIM = { headSpeed: 120, maxTurnRate: 8.4, tickHz: 20,
  baseGirth: 6, maxGirth: 24, turnGirthFalloff: 0.4,
  segmentSpacingFactor: 0.333, minSegmentSpacing: 1.0, boostMultiplier: 1.8 };

export const PALETTE = [
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
];

// Bots are colored by their strategy so different AIs are easy to tell apart
// (and you can watch them compete). Humans keep the random PALETTE via
// colorFor(id). Keys match the `strategy` field sent by the server.
export const STRATEGY_COLORS = {
  seeker: '#ff4d6d',
  wanderer: '#4dd2ff',
};

export function colorFor(id) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

// The color a serpent renders as: bots by strategy so competing AIs are easy
// to tell apart, humans by a stable hash of their id. Carcass pellets are
// tinted with this too, so you can see whose remains you are eating.
export function serpentColor(player) {
  return player.is_bot && player.strategy && STRATEGY_COLORS[player.strategy]
    ? STRATEGY_COLORS[player.strategy]
    : colorFor(player.id);
}

function wrapAngle(a) {
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a <= -Math.PI) a += 2 * Math.PI;
  return a;
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerpAngle(a, b, t) {
  return a + wrapAngle(b - a) * t;
}

// A body is a QUEUE, not a set of moving parts: the server appends a point at
// the head once it has travelled one spacing, and drops one off the tail. The
// points in between never move at all.
//
// So interpolating them index-by-index is wrong -- b[i] is the same world
// position as a[i + dropped], and lerping a[i] toward b[i] drags every segment
// one spacing forward each tick, cutting corners on bends. That was the
// shimmer. Aligning the two snapshots on their shared run instead lets us draw
// the middle exactly where the server put it and animate only the two ends.
//
// Returns {dropped, added}, or null when the two snapshots share no run at all
// (a respawn or teleport), in which case there is nothing to animate between.
function alignPoints(prev, next) {
  if (!prev || !prev.length || !next || !next.length) return null;
  const head = next[0];
  // Points only leave from the front, a couple per tick at most, so a short
  // scan finds the overlap. Failing to find it means the body was replaced.
  const limit = Math.min(prev.length, 16);
  for (let k = 0; k < limit; k++) {
    if (prev[k][0] === head[0] && prev[k][1] === head[1]) {
      const shared = prev.length - k;
      if (shared <= 0 || shared > next.length) return null;
      return { dropped: k, added: next.length - shared };
    }
  }
  return null;
}

// Body points as [x, y, alpha] triples. Shared points sit at full opacity
// exactly where the server put them; the freshly appended head points fade in
// across the tick and the dropped tail points fade out, so segments arrive and
// leave instead of popping. This is the enter/update/exit split, done against
// the canvas rather than a DOM data join.
function queuedPoints(st, alpha) {
  const next = st.server.points;
  const shift = st.shift;
  if (!shift || !st.prev) return next.map((p) => [p[0], p[1], 1]);
  const out = [];
  const prev = st.prev.points;
  for (let i = 0; i < shift.dropped; i++) {
    out.push([prev[i][0], prev[i][1], 1 - alpha]);
  }
  const entering = next.length - shift.added;
  for (let i = 0; i < next.length; i++) {
    out.push([next[i][0], next[i][1], i >= entering ? alpha : 1]);
  }
  return out;
}

// The self body is predicted locally at frame rate rather than interpolated
// between snapshots, so there is no prev/next pair to diff. Fade its ends on
// how far the head has pulled past the newest point instead: at a full spacing
// a new point is appended and the oldest dropped, and both alphas hand over at
// exactly the same moment, so the cycle is seamless.
function localPoints(local, sim) {
  const pts = local.points;
  if (!pts.length) return [];
  const girth = local.girth || sim.baseGirth;
  const spacing = Math.max(sim.minSegmentSpacing, girth * sim.segmentSpacingFactor);
  const newest = pts[pts.length - 1];
  const frac = spacing > 0
    ? Math.min(1, Math.hypot(local.x - newest[0], local.y - newest[1]) / spacing)
    : 1;
  const maxPoints = Math.max(1, Math.round((local.length || 0) / spacing) + 1);
  // Only fade the tail once the queue is full; while the serpent is still
  // growing nothing is being dropped, so the tail must stay solid.
  const atCapacity = pts.length >= maxPoints;
  return pts.map((p, i) => {
    if (i === pts.length - 1 && pts.length > 1) return [p[0], p[1], frac];
    if (i === 0 && atCapacity && pts.length > 1) return [p[0], p[1], 1 - frac];
    return [p[0], p[1], 1];
  });
}

function cloneLocal(p) {
  return {
    x: p.x,
    y: p.y,
    heading: p.heading,
    points: p.points.map((pt) => [pt[0], pt[1]]),
    length: p.length,
    girth: p.girth,
  };
}

function makeState(p, selfId) {
  return {
    server: p,
    prev: null,
    isSelf: p.id === selfId,
    local: p.id === selfId ? cloneLocal(p) : null,
  };
}

// Snap local prediction to the server's truth so error can't accumulate.
function reconcileLocal(st) {
  if (!st.local) st.local = cloneLocal(st.server);
  st.local.x = st.server.x;
  st.local.y = st.server.y;
  st.local.heading = st.server.heading;
  st.local.points = st.server.points.map((pt) => [pt[0], pt[1]]);
  st.local.length = st.server.length;
  st.local.girth = st.server.girth;
}

function stepLocal(local, dt, target, mapW, mapH, sim, boost) {
  // target is a direction vector (dx, dy), not a world point: steer toward
  // that absolute heading so holding a direction yields a straight path.
  let desired;
  if (target.x === 0 && target.y === 0) {
    desired = local.heading; // no input: keep current heading
  } else {
    desired = Math.atan2(target.y, target.x);
  }
  const diff = wrapAngle(desired - local.heading);
  // Match the server: turn rate falls off as the snake gets girthier, so a
  // fat snake has a wider turning radius. Keeps local prediction in sync.
  const g = local.girth || sim.baseGirth;
  let frac = (g - sim.baseGirth) / (sim.maxGirth - sim.baseGirth);
  frac = Math.max(0, Math.min(1, frac));
  const effTurn = sim.maxTurnRate * (1 - sim.turnGirthFalloff * frac);
  const maxStep = effTurn * dt;
  local.heading += Math.max(-maxStep, Math.min(maxStep, diff));

  // Match the server: boosting multiplies head speed while the control is held.
  const speed = sim.headSpeed * (boost ? sim.boostMultiplier : 1);
  local.x += Math.cos(local.heading) * speed * dt;
  local.y += Math.sin(local.heading) * speed * dt;
  local.x = Math.max(0, Math.min(mapW, local.x));
  local.y = Math.max(0, Math.min(mapH, local.y));

  // Segment spacing scales with girth (matches the server) so the predicted
  // trail density lines up with what the server renders.
  const spacing = Math.max(sim.minSegmentSpacing, g * sim.segmentSpacingFactor);
  const last = local.points[local.points.length - 1];
  if (Math.hypot(local.x - last[0], local.y - last[1]) >= spacing) {
    local.points.push([local.x, local.y]);
    const maxPoints = Math.max(1, Math.round((local.length || 0) / spacing) + 1);
    while (local.points.length > maxPoints) local.points.shift();
  }
}

function renderState(st, alpha, sim) {
  if (st.isSelf && st.local && st.server.alive) {
    return {
      id: st.server.id,
      x: st.local.x,
      y: st.local.y,
      heading: st.local.heading,
      points: localPoints(st.local, sim),
      alive: st.server.alive,
      score: st.server.score,
      girth: st.server.girth,
      username: st.server.username,
      is_bot: st.server.is_bot,
      strategy: st.server.strategy,
    };
  }
  if (!st.prev) return st.server;
  return {
    id: st.server.id,
    x: lerp(st.prev.x, st.server.x, alpha),
    y: lerp(st.prev.y, st.server.y, alpha),
    heading: lerpAngle(st.prev.heading, st.server.heading, alpha),
    points: queuedPoints(st, alpha),
    alive: st.server.alive,
    score: st.server.score,
    girth: st.server.girth,
    username: st.server.username,
    is_bot: st.server.is_bot,
    strategy: st.server.strategy,
  };
}

export class Game {
  constructor() {
    this.selfId = null;
    this.players = {};
    this.foods = [];
    this.mapW = 1000;
    this.mapH = 1000;
    this.sim = { ...SIM };
    this.lastSnapTime = 0;
    this.snapInterval = 50;
    this.selfTarget = { x: 0, y: 0 };
    this.selfBoosting = false; // mirror of the held boost control, for prediction
    this.foodSpawnRadius = 0; // radius of the central food-spawn circle
    this.onScore = null; // (score:number) => void, called when self score changes
  }

  onWelcome(msg) {
    this.selfId = msg.self_id;
    if (msg.map_width && msg.map_height) {
      this.mapW = msg.map_width;
      this.mapH = msg.map_height;
    }
    if (msg.head_speed) this.sim.headSpeed = msg.head_speed;
    if (msg.max_turn_rate) this.sim.maxTurnRate = msg.max_turn_rate;
    if (msg.tail_spacing) this.sim.tailSpacing = msg.tail_spacing;
    if (msg.tick_hz) this.sim.tickHz = msg.tick_hz;
    if (msg.food_spawn_radius) this.foodSpawnRadius = msg.food_spawn_radius;
    if (msg.base_girth) this.sim.baseGirth = msg.base_girth;
    if (msg.max_girth) this.sim.maxGirth = msg.max_girth;
    if (msg.turn_girth_falloff !== undefined) this.sim.turnGirthFalloff = msg.turn_girth_falloff;
    if (msg.boost_multiplier !== undefined) this.sim.boostMultiplier = msg.boost_multiplier;
    if (msg.segment_spacing_factor !== undefined) this.sim.segmentSpacingFactor = msg.segment_spacing_factor;
    if (msg.min_segment_spacing !== undefined) this.sim.minSegmentSpacing = msg.min_segment_spacing;
    this.players = {};
    msg.players.forEach((p) => (this.players[p.id] = makeState(p, this.selfId)));
    this.foods = msg.food || [];
    this.lastSnapTime = 0;
  }

  onSnapshot(msg, now) {
    if (this.lastSnapTime) {
      // Smooth the measured interval so alpha stays stable.
      this.snapInterval += (now - this.lastSnapTime - this.snapInterval) * 0.2;
    }
    this.lastSnapTime = now;

    const ids = new Set(msg.players.map((p) => p.id));
    msg.players.forEach((p) => {
      const st = this.players[p.id] || makeState(p, this.selfId);
      st.prev = st.server; // old authoritative state = interp start
      st.server = p; // new authoritative state = interp end
      // How the point queue shifted between the two, worked out once here
      // rather than on every frame of the tick.
      st.shift = st.prev ? alignPoints(st.prev.points, p.points) : null;
      if (st.isSelf) reconcileLocal(st);
      this.players[p.id] = st;
    });
    Object.keys(this.players).forEach((id) => {
      if (!ids.has(id)) delete this.players[id];
    });
    this.foods = msg.food || [];

    const self = this.players[this.selfId];
    if (self && this.onScore) this.onScore(self.server.score);
  }

  step(dt) {
    const st = this.players[this.selfId];
    if (st && st.local && st.server && st.server.alive) {
      stepLocal(st.local, dt, this.selfTarget, this.mapW, this.mapH, this.sim, this.selfBoosting);
    }
  }

  alpha(now) {
    return this.snapInterval > 0
      ? Math.min(1, (now - this.lastSnapTime) / this.snapInterval)
      : 1;
  }

  renderList(alpha) {
    return Object.values(this.players).map((s) => renderState(s, alpha, this.sim));
  }
}
