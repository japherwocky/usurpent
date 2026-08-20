/* USURPENT client — WebSocket-driven multiplayer renderer.

The server is authoritative. We open /ws, send our mouse target, and render
the snapshots it broadcasts. No client-side simulation of other players; we
glide between snapshots with D3 transitions for smoothness.
*/

const WS_PROTO = location.protocol === "https:" ? "wss" : "ws";

let ws = null;
let selfId = null;
let players = {};            // id -> last player dict from server
let MAP_W = 1000;            // updated from welcome (handles env overrides)
let MAP_H = 1000;

let scaleX, scaleY, gEnts, gParts, lineGen;

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
    players = {};
    msg.players.forEach((p) => (players[p.id] = p));
    render();
  } else if (msg.type === "snapshot") {
    const ids = new Set(msg.players.map((p) => p.id));
    msg.players.forEach((p) => (players[p.id] = p));
    Object.keys(players).forEach((id) => {
      if (!ids.has(id)) delete players[id];
    });
    render();
  }
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
  gEnts = svg.append("g").attr("class", "entities");

  // Particle background: slow rotating dots, purely cosmetic.
  setInterval(() => {
    const t = performance.now();
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
    ws.send(JSON.stringify({ type: "input", target: { x: tx, y: ty } }));
  };
}

function rebuildScales() {
  const s = document.getElementById("screen");
  scaleX.domain([0, MAP_W]).range([0, s.clientWidth]);
  scaleY.domain([0, MAP_H]).range([s.clientHeight, 0]);
}

function render() {
  const list = Object.values(players);
  const sel = gEnts.selectAll("g.player").data(list, (d) => d.id);

  const enter = sel.enter().append("g").attr("class", "player");
  enter.append("path").attr("class", "tail").attr("fill", "none");
  enter.append("circle").attr("class", "head");

  const merged = enter.merge(sel);

  merged
    .select("path.tail")
    .transition()
    .duration(50)
    .attr("d", (d) => lineGen(d.points))
    .attr("stroke", (d) => colorFor(d.id))
    .attr("stroke-width", 6)
    .attr("stroke-linecap", "round")
    .attr("opacity", (d) => (d.alive ? 0.9 : 0.25));

  merged
    .select("circle.head")
    .transition()
    .duration(50)
    .attr("cx", (d) => scaleX(d.x))
    .attr("cy", (d) => scaleY(d.y))
    .attr("r", (d) => 7 + Math.min(d.score, 30) * 0.2)
    .attr("fill", (d) => colorFor(d.id))
    .attr("opacity", (d) => (d.alive ? 1 : 0.4));

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

function uuidv4() {
  return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
  );
}

function logging(msg) {
  console.log("[usurpent] " + msg);
}
