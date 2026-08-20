/* USURPENT client — WebSocket-driven multiplayer renderer.

The server is authoritative. We send our mouse target, then:
  - predict OUR OWN snake locally each animation frame (instant response),
    reconciling to the server snapshot when it arrives;
  - interpolate OTHER players between the last two snapshots by time, so
    they glide smoothly instead of jumping at 20 Hz.
*/

const WS_PROTO = location.protocol === "https:" ? "wss" : "ws";

// Simulation constants, overwritten from the welcome message (server config).
const SIM = {
  headSpeed: 120,
  maxTurnRate: 6.0,
  tailSpacing: 8,
  tickHz: 20,
};

let ws = null;
let selfId = null;
let players = {};            // id -> { server, prev, local, isSelf }
let foods = [];              // last food list from server
let MAP_W = 1000;            // updated from welcome (handles env overrides)
let MAP_H = 1000;

let scaleX, scaleY, gEnts, gParts, gFood, lineGen;

let lastSnapTime = 0;
let snapInterval = 50;       // measured ms between snapshots
let selfTarget = { x: 0, y: 0 };
let lastFrameTime = 0;
let rafStarted = false;

document.getElementById("cta").addEventListener("click", function () {
  document.getElementById("welcome").classList.add("hide");
  document.getElementById("screenwrapper").classList.remove("hide");
  main();
});

function main() {
  window.USURPENT = { particles: mkParticles() };
  mkScreen();
  connect();
}

function connect() {
  ws = new WebSocket(`${WS_PROTO}://${location.host}/ws`);
  ws.onmessage = (ev) => handleMessage(JSON.parse(ev.data));
  ws.onclose = () => logging("connection closed");
}

function handleMessage(msg) {
  if (msg.type === "welcome") {
    selfId = msg.self_id;
    if (msg.map_width && msg.map_height) {
      MAP_W = msg.map_width;
      MAP_H = msg.map_height;
      rebuildScales();
      window.USURPENT.particles = mkParticles();
    }
    if (msg.head_speed) SIM.headSpeed = msg.head_speed;
    if (msg.max_turn_rate) SIM.maxTurnRate = msg.max_turn_rate;
    if (msg.tail_spacing) SIM.tailSpacing = msg.tail_spacing;
    if (msg.tick_hz) SIM.tickHz = msg.tick_hz;
    players = {};
    msg.players.forEach((p) => (players[p.id] = makeState(p)));
    foods = msg.food || [];
    if (!rafStarted) {
      rafStarted = true;
      lastFrameTime = performance.now();
      requestAnimationFrame(frame);
    }
  } else if (msg.type === "snapshot") {
    const now = performance.now();
    if (lastSnapTime) {
      // Smooth the measured interval so alpha stays stable.
      snapInterval += (now - lastSnapTime - snapInterval) * 0.2;
    }
    lastSnapTime = now;

    const ids = new Set(msg.players.map((p) => p.id));
    msg.players.forEach((p) => {
      const st = players[p.id] || makeState(p);
      st.prev = st.server;          // old authoritative state = interp start
      st.server = p;                // new authoritative state = interp end
      if (st.isSelf) reconcileLocal(st);
      players[p.id] = st;
    });
    Object.keys(players).forEach((id) => {
      if (!ids.has(id)) delete players[id];
    });
    foods = msg.food || [];
  }
}

function makeState(p) {
  return {
    server: p,
    prev: null,
    isSelf: p.id === selfId,
    local: p.id === selfId ? cloneLocal(p) : null,
  };
}

// Copy the server's head/tail into a local predicted state. Target is kept.
function cloneLocal(p) {
  return {
    x: p.x,
    y: p.y,
    heading: p.heading,
    points: p.points.map((pt) => [pt[0], pt[1]]),
    cap: p.points.length,
  };
}

// On snapshot, snap local prediction to the server's truth (no drift buildup).
function reconcileLocal(st) {
  if (!st.local) st.local = cloneLocal(st.server);
  st.local.x = st.server.x;
  st.local.y = st.server.y;
  st.local.heading = st.server.heading;
  st.local.points = st.server.points.map((pt) => [pt[0], pt[1]]);
  st.local.cap = st.server.points.length;
}

function stepLocal(local, dt, target) {
  const desired = Math.atan2(target.y - local.y, target.x - local.x);
  let diff = wrapAngle(desired - local.heading);
  const maxStep = SIM.maxTurnRate * dt;
  local.heading += Math.max(-maxStep, Math.min(maxStep, diff));

  local.x += Math.cos(local.heading) * SIM.headSpeed * dt;
  local.y += Math.sin(local.heading) * SIM.headSpeed * dt;
  local.x = Math.max(0, Math.min(MAP_W, local.x));
  local.y = Math.max(0, Math.min(MAP_H, local.y));

  const last = local.points[local.points.length - 1];
  if (Math.hypot(local.x - last[0], local.y - last[1]) >= SIM.tailSpacing) {
    local.points.push([local.x, local.y]);
    while (local.points.length > local.cap) local.points.shift();
  }
}

// Build the dict we actually draw for one player this frame.
function renderState(st, alpha) {
  if (st.isSelf && st.local && st.server.alive) {
    return {
      id: st.server.id,
      x: st.local.x,
      y: st.local.y,
      heading: st.local.heading,
      points: st.local.points,
      alive: st.server.alive,
      score: st.server.score,
    };
  }
  if (!st.prev) return st.server;
  return {
    id: st.server.id,
    x: lerp(st.prev.x, st.server.x, alpha),
    y: lerp(st.prev.y, st.server.y, alpha),
    heading: lerpAngle(st.prev.heading, st.server.heading, alpha),
    points: interpPoints(st.prev.points, st.server.points, alpha),
    alive: st.server.alive,
    score: st.server.score,
  };
}

function interpPoints(a, b, alpha) {
  if (!a || a.length !== b.length) return b;
  return a.map((pt, i) => [lerp(pt[0], b[i][0], alpha), lerp(pt[1], b[i][1], alpha)]);
}

function frame() {
  const now = performance.now();
  let dt = (now - lastFrameTime) / 1000;
  lastFrameTime = now;
  if (dt > 0.1) dt = 0.1; // clamp after tab was backgrounded

  const alpha = snapInterval > 0 ? Math.min(1, (now - lastSnapTime) / snapInterval) : 1;

  const st = selfId ? players[selfId] : null;
  if (st && st.local && st.server && st.server.alive) {
    stepLocal(st.local, dt, selfTarget);
  }

  const list = Object.values(players).map((s) => renderState(s, alpha));
  draw(list);
  drawFood();
  requestAnimationFrame(frame);
}

function colorFor(id) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return d3.schemeCategory10[h % 10];
}

function mkScreen() {
  const svg = d3.select("svg");

  function bounds() {
    const s = document.getElementById("screen");
    return { width: s.clientWidth, height: s.clientHeight };
  }
  const b = bounds();
  window.addEventListener("resize", () => {
    rebuildScales();
    window.USURPENT.particles = mkParticles();
  });

  scaleX = d3.scaleLinear().domain([0, MAP_W]).range([0, b.width]);
  scaleY = d3.scaleLinear().domain([0, MAP_H]).range([b.height, 0]);
  lineGen = d3
    .line()
    .x((d) => scaleX(d[0]))
    .y((d) => scaleY(d[1]));

  gParts = svg.append("g").attr("class", "particles");
  gFood = svg.append("g").attr("class", "food");
  gEnts = svg.append("g").attr("class", "entities");

  // Particle background: slow rotating dots, purely cosmetic.
  setInterval(() => {
    window.USURPENT.particles.forEach((p) => {
      const a = (Math.PI / 180) * 13;
      const cos = Math.cos(a);
      const sin = Math.sin(a);
      const nx = cos * (p.x - p.tx) + sin * (p.y - p.ty) + p.tx;
      const ny = cos * (p.y - p.ty) - sin * (p.x - p.tx) + p.ty;
      p.x = nx;
      p.y = ny;
    });
    const sel = gParts
      .selectAll("circle.particle")
      .data(window.USURPENT.particles, (d) => d.id);
    sel
      .enter()
      .append("circle")
      .attr("class", "particle")
      .attr("r", (d) => d.r)
      .merge(sel)
      .attr("cx", (d) => scaleX(d.x))
      .attr("cy", (d) => scaleY(d.y))
      .attr("fill", (d) => d3.schemeCategory10[d.color % 10])
      .attr("opacity", 0.5);
    sel.exit().remove();
  }, 100);

  document.onmousemove = (event) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const tx = scaleX.invert(event.layerX);
    const ty = scaleY.invert(event.layerY);
    selfTarget = { x: tx, y: ty };
    ws.send(JSON.stringify({ type: "input", target: { x: tx, y: ty } }));
  };
}

function rebuildScales() {
  const s = document.getElementById("screen");
  scaleX.domain([0, MAP_W]).range([0, s.clientWidth]);
  scaleY.domain([0, MAP_H]).range([s.clientHeight, 0]);
}

function draw(list) {
  const sel = gEnts.selectAll("g.player").data(list, (d) => d.id);

  const enter = sel.enter().append("g").attr("class", "player");
  enter.append("path").attr("class", "tail").attr("fill", "none");
  enter.append("circle").attr("class", "head");

  const merged = enter.merge(sel);

  merged
    .select("path.tail")
    .attr("d", (d) => lineGen(d.points))
    .attr("stroke", (d) => colorFor(d.id))
    .attr("stroke-width", 6)
    .attr("stroke-linecap", "round")
    .attr("opacity", (d) => (d.alive ? 0.9 : 0.25));

  merged
    .select("circle.head")
    .attr("cx", (d) => scaleX(d.x))
    .attr("cy", (d) => scaleY(d.y))
    .attr("r", (d) => 7 + Math.min(d.score, 30) * 0.2)
    .attr("fill", (d) => colorFor(d.id))
    .attr("opacity", (d) => (d.alive ? 1 : 0.4));

  sel.exit().remove();
}

function drawFood() {
  const sel = gFood.selectAll("circle.food").data(foods, (d) => d.id);
  sel
    .enter()
    .append("circle")
    .attr("class", "food")
    .attr("r", 5)
    .merge(sel)
    .attr("cx", (d) => scaleX(d.x))
    .attr("cy", (d) => scaleY(d.y))
    .attr("fill", "#ffd166")
    .attr("opacity", 0.9);
  sel.exit().remove();
}

function mkParticles() {
  const rand = d3.randomNormal(0, 1);
  return Array.from({ length: 13 }, () => {
    const tx = Math.random() * MAP_W;
    const ty = Math.random() * MAP_H;
    return {
      id: uuidv4(),
      tx,
      ty,
      x: tx + rand(),
      y: ty + rand(),
      r: Math.abs(rand()) * 6 + 2,
      color: Math.floor(Math.random() * 10),
    };
  });
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

function uuidv4() {
  return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
  );
}

function logging(msg) {
  console.log("[usurpent] " + msg);
}
