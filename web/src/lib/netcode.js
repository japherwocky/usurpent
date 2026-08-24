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

// How quickly a correction is paid off, in seconds. One snapshot interval, so
// roughly two thirds of an error is gone before the next one lands: corrections
// blend into each other rather than stacking up into rubber-banding.
const SMOOTH_TAU = 0.05;
// Past this the client has not mispredicted, it has lost the thread -- a
// respawn, a teleport, a long stall. Take the jump rather than sliding a huge
// offset in over a quarter second.
const RESYNC_DISTANCE = 40;

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

// Pellet colour runs on SIZE, not identity: a fresh crumb is cool lime and a
// blob that has merged its way to the cap runs red-hot, so what is worth
// crossing the map for reads at a glance. The low end stays bright on
// purpose -- a crumb is a couple of pixels across, and a perceptual ramp like
// viridis would put its darkest stop on the smallest, least visible thing on
// screen. The top end stays clear of the seeker bots' #ff4d6d.
const FOOD_RAMP = [
  [163, 230, 53],  // lime   -- a spawned crumb
  [250, 204, 21],  // amber
  [251, 146, 60],  // orange
  [220, 38, 38],   // red    -- a blob at FOOD_MERGE_MAX_RADIUS
];

// Baked into a lookup table at module load: foodColor runs once per visible
// pellet per frame, and building a css colour string each time would churn
// thousands of short-lived strings a second for colours that never change.
const FOOD_STEPS = 48;
const FOOD_COLORS = (() => {
  const out = [];
  const last = FOOD_RAMP.length - 1;
  for (let i = 0; i < FOOD_STEPS; i++) {
    const seg = (i / (FOOD_STEPS - 1)) * last;
    const lo = Math.min(last - 1, Math.floor(seg));
    const f = seg - lo;
    const a = FOOD_RAMP[lo];
    const b = FOOD_RAMP[lo + 1];
    out.push(
      `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},` +
        `${Math.round(a[1] + (b[1] - a[1]) * f)},` +
        `${Math.round(a[2] + (b[2] - a[2]) * f)})`
    );
  }
  return out;
})();

// Radius grows by AREA on every merge -- sqrt(r1^2 + r2^2) -- so reaching the
// cap from a spawned crumb takes on the order of 289 of them, and pellet
// radii pile up against the bottom of the range. Ramped linearly the whole
// field came out one shade of lime: a blob of twenty-five fused crumbs still
// sat at t=0.25. Taking the root of the fraction spends the palette where the
// pellets actually are, and because the growth is quadratic it means one step
// of colour is roughly one doubling of crumbs rather than of width.
const FOOD_RAMP_GAMMA = 0.5;

// Colour for a pellet of this radius. The ends come from the welcome
// (FOOD_BASE_RADIUS and FOOD_MERGE_MAX_RADIUS) so the ramp spans whatever
// range the server actually produces, rather than a constant here that goes
// quietly wrong the next time the food is retuned.
export function foodColor(r, minR, maxR) {
  const span = maxR - minR;
  let t = span > 0 ? (r - minR) / span : 0;
  if (t < 0) t = 0;
  else if (t > 1) t = 1;
  return FOOD_COLORS[Math.round(t ** FOOD_RAMP_GAMMA * (FOOD_STEPS - 1))];
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
function localPoints(local, sim, ox, oy) {
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
    const x = p[0] + ox;
    const y = p[1] + oy;
    if (i === pts.length - 1 && pts.length > 1) return [x, y, frac];
    if (i === 0 && atCapacity && pts.length > 1) return [x, y, 1 - frac];
    return [x, y, 1];
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

// Take the server's truth into the state, but not into the picture all at
// once. The state is overwritten exactly as before, so error still cannot
// accumulate; what is left behind is a visual offset that decays over the next
// few frames, so a correction slides in instead of popping.
function reconcileLocal(st) {
  if (!st.local) {
    st.local = cloneLocal(st.server);
    st.err = null;
    return;
  }
  // The rendered position is local + err. For it not to jump when local is
  // overwritten, err has to absorb exactly what local gives up -- so the new
  // offset is the prediction error plus whatever of the last one is still
  // showing. That makes the handover continuous by construction.
  const ex = st.local.x - st.server.x + (st.err ? st.err.x : 0);
  const ey = st.local.y - st.server.y + (st.err ? st.err.y : 0);
  st.local.x = st.server.x;
  st.local.y = st.server.y;
  st.local.heading = st.server.heading;
  st.local.length = st.server.length;
  st.local.girth = st.server.girth;

  if (Math.hypot(ex, ey) > RESYNC_DISTANCE) {
    st.local.points = st.server.points.map((pt) => [pt[0], pt[1]]);
    st.err = null;
    return;
  }
  // Keep the locally laid body. Both sides now lay points by the same rule on
  // the same path (see stepLocal), so overwriting it every snapshot swapped
  // one sampling of that path for another -- the end-of-body pop that outlived
  // the spacing fix. Points the client laid are as good as the ones it would
  // have been handed, and they are already on screen.
  st.err = { x: ex, y: ey };
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
  // trail density lines up with what the server renders. Lay down every point
  // the distance covered calls for, not one per frame: this runs at frame rate
  // rather than the server's 20 Hz, so one-per-step put the points ~2.67 apart
  // against a wanted 2.0 where the server managed 4.0 -- close enough to look
  // right on its own and far enough out that reconciling against the server
  // rewrote the whole body's geometry every snapshot.
  const spacing = Math.max(sim.minSegmentSpacing, g * sim.segmentSpacingFactor);
  const tail = local.points[local.points.length - 1];
  let lx = tail[0];
  let ly = tail[1];
  let gap = Math.hypot(local.x - lx, local.y - ly);
  while (gap >= spacing) {
    const t = spacing / gap;
    lx += (local.x - lx) * t;
    ly += (local.y - ly) * t;
    local.points.push([lx, ly]);
    gap = Math.hypot(local.x - lx, local.y - ly);
  }
  const maxPoints = Math.max(1, Math.round((local.length || 0) / spacing) + 1);
  while (local.points.length > maxPoints) local.points.shift();
}

function renderState(st, alpha, sim) {
  if (st.isSelf && st.local && st.server.alive) {
    const ox = st.err ? st.err.x : 0;
    const oy = st.err ? st.err.y : 0;
    return {
      id: st.server.id,
      x: st.local.x + ox,
      y: st.local.y + oy,
      heading: st.local.heading,
      points: localPoints(st.local, sim, ox, oy),
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
    // Seconds the server makes a dead player wait before it will honour a
    // respawn request. The death card greys its button for the same interval;
    // the real value arrives in the welcome so the two cannot drift apart.
    this.respawnDelay = 1.5;
    // Ends of the pellet colour ramp, replaced from the welcome.
    this.foodMinRadius = 2;
    this.foodMaxRadius = 34;
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
    if (msg.respawn_delay !== undefined) this.respawnDelay = msg.respawn_delay;
    if (msg.food_min_radius !== undefined) this.foodMinRadius = msg.food_min_radius;
    if (msg.food_max_radius !== undefined) this.foodMaxRadius = msg.food_max_radius;
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
    // Pay off the outstanding correction. Exponential, so the rate is
    // framerate-independent: a slow frame settles as much as three quick ones.
    if (st && st.err) {
      const k = Math.exp(-dt / SMOOTH_TAU);
      st.err.x *= k;
      st.err.y *= k;
      if (Math.abs(st.err.x) < 0.02 && Math.abs(st.err.y) < 0.02) st.err = null;
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
