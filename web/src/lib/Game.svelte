<script>
  import { onMount, onDestroy } from 'svelte';
  import { Game, colorFor, PALETTE, STRATEGY_COLORS } from './netcode.js';

  // Display name chosen in the lobby; sent to the server on connect.
  export let name = '';

  let canvas;
  let status = 'connecting';
  let selfId = null;
  let selfScore = 0;

  // Right-click overlay (leaderboard / legend / debug stats) and boost state.
  let showOverlay = false;
  let stats = { fps: 0, tickHz: 0, snapMs: 0, players: 0, humans: 0, bots: 0, food: 0,
               selfScore: 0, selfGirth: 0, selfLength: 0, selfAlive: true, boosting: false,
               leaderboard: [] };
  let mouseBoost = false;
  let keyBoost = false;
  let fps = 0;
  // Static legend: each bot strategy's color, plus a note that humans are random.
  const legend = Object.entries(STRATEGY_COLORS).map(([name, color]) => ({ name, color }));

  let ws = null;
  const game = new Game();
  let raf = 0;
  let lastFrame = 0;
  let dpr = 1;
  let particles = [];
  // On-screen position of the self head, refreshed each frame. Steering is
  // computed relative to this (not the screen center) so it stays correct
  // when the camera isn't centered on the head (e.g. wide viewports).
  let headScreenX = 0;
  let headScreenY = 0;

  // World units visible across the smaller viewport axis. Smaller = more zoom
  // and a stronger "scrolling" feel.
  const VIEW_WORLD = 600;

  function mkParticles() {
    const arr = [];
    for (let i = 0; i < 13; i++) {
      const tx = Math.random() * game.mapW;
      const ty = Math.random() * game.mapH;
      arr.push({
        tx,
        ty,
        x: tx,
        y: ty,
        r: Math.random() * 6 + 2,
        color: Math.floor(Math.random() * PALETTE.length),
      });
    }
    return arr;
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const q = name ? `?name=${encodeURIComponent(name)}` : '';
    ws = new WebSocket(`${proto}://${location.host}/ws${q}`);
    ws.onopen = () => (status = 'open');
    ws.onclose = () => (status = 'closed');
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'welcome') {
        game.onWelcome(msg);
        particles = mkParticles();
        selfId = msg.self_id;
        selfScore = 0;
      } else if (msg.type === 'snapshot') {
        game.onSnapshot(msg, performance.now());
      }
    };
  }

  function sendTarget(dx, dy) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', target: { x: dx, y: dy } }));
    }
  }

  function onMouseMove(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    // Steering direction is the mouse offset from the SERPENT HEAD's on-screen
    // position, not the screen center. The head is centered while the camera
    // follows it, but on wide viewports the whole map is shown and the head
    // sits elsewhere, so using screen center would steer incorrectly.
    const dx = mx - headScreenX;
    const dy = -(my - headScreenY);
    game.selfTarget = { x: dx, y: dy };
    sendTarget(dx, dy);
  }

  function sendBoost(b) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', boost: b }));
    }
  }
  function updateBoost() {
    const b = mouseBoost || keyBoost;
    game.selfBoosting = b;
    sendBoost(b);
  }
  function toggleOverlay() {
    showOverlay = !showOverlay;
  }
  function onMouseDown(e) {
    if (e.button === 0) { mouseBoost = true; updateBoost(); }
  }
  function onMouseUp(e) {
    if (e.button === 0) { mouseBoost = false; updateBoost(); }
  }
  function onContextMenu(e) {
    e.preventDefault();
    toggleOverlay();
  }
  // Keyboard sketch (full bindings later): Shift = boost, L = toggle overlay.
  function onKeyDown(e) {
    if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') { keyBoost = true; updateBoost(); }
    else if (e.code === 'KeyL') { toggleOverlay(); }
  }
  function onKeyUp(e) {
    if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') { keyBoost = false; updateBoost(); }
  }
  function updateStats() {
    const players = Object.values(game.players).map((s) => s.server);
    const bots = players.filter((p) => p.is_bot).length;
    const self = game.players[game.selfId];
    const board = players
      .slice()
      .sort((a, b) => b.score - a.score)
      .map((p) => ({
        name: p.username || (p.is_bot ? 'Bot' : '???'),
        score: p.score,
        color: p.is_bot && p.strategy && STRATEGY_COLORS[p.strategy]
          ? STRATEGY_COLORS[p.strategy]
          : colorFor(p.id),
      }));
    stats = {
      fps: Math.round(fps),
      tickHz: game.sim.tickHz,
      snapMs: Math.round(game.snapInterval),
      players: players.length,
      humans: players.length - bots,
      bots,
      food: game.foods.length,
      selfScore: self ? self.server.score : 0,
      selfGirth: self ? self.server.girth : 0,
      selfLength: self ? self.server.length : 0,
      selfAlive: self ? self.server.alive : false,
      boosting: game.selfBoosting,
      leaderboard: board,
    };
  }

  function draw() {
    const ctx = canvas.getContext('2d');
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    dpr = window.devicePixelRatio || 1;
    const bw = Math.max(1, Math.floor(w * dpr));
    const bh = Math.max(1, Math.floor(h * dpr));
    if (canvas.width !== bw || canvas.height !== bh) {
      canvas.width = bw;
      canvas.height = bh;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Camera centers on the self head so it stays put on screen and the map
    // scrolls underneath. Only fall back to centering the whole map when the
    // viewport is large enough to show it entirely (otherwise the head is
    // always centered, in both axes).
    const s = Math.min(w, h) / VIEW_WORLD;
    const viewW = w / s;
    const viewH = h / s;

    const list = game.renderList(game.alpha(performance.now()));
    const selfEnt = list.find((p) => p.id === game.selfId);
    let camX = selfEnt ? selfEnt.x : game.mapW / 2;
    let camY = selfEnt ? selfEnt.y : game.mapH / 2;
    if (viewW >= game.mapW) camX = game.mapW / 2;
    if (viewH >= game.mapH) camY = game.mapH / 2;

    const toScreen = (wx, wy) => [
      (wx - camX) * s + w / 2,
      h / 2 - (wy - camY) * s,
    ];

    if (selfEnt) {
      const [hsx, hsy] = toScreen(selfEnt.x, selfEnt.y);
      headScreenX = hsx;
      headScreenY = hsy;
    } else {
      headScreenX = w / 2;
      headScreenY = h / 2;
    }

    // Map border, so the playfield bounds are visible as the world scrolls.
    const [bx0, by0] = toScreen(0, 0);
    const [bx1, by1] = toScreen(game.mapW, game.mapH);
    ctx.strokeStyle = '#3a4654';
    ctx.lineWidth = 3;
    ctx.strokeRect(
      Math.min(bx0, bx1),
      Math.min(by0, by1),
      Math.abs(bx1 - bx0),
      Math.abs(by1 - by0)
    );

    // Food spawn region: a filled, dashed circle centered on the map, drawn
    // with a slight opacity so players can see where new food appears.
    if (game.foodSpawnRadius > 0) {
      const [ccx, ccy] = toScreen(game.mapW / 2, game.mapH / 2);
      const screenR = game.foodSpawnRadius * s;
      ctx.save();
      // Subtle fill so the zone reads as a region, not just an outline.
      ctx.fillStyle = 'rgba(90, 107, 125, 0.08)';
      ctx.beginPath();
      ctx.arc(ccx, ccy, screenR, 0, Math.PI * 2);
      ctx.fill();
      // Dashed border with slight opacity, drawn on top of the fill.
      ctx.globalAlpha = 0.25;
      ctx.strokeStyle = '#5a6b7d';
      ctx.lineWidth = 2;
      ctx.setLineDash([10, 8]);
      ctx.beginPath();
      ctx.arc(ccx, ccy, screenR, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // Cosmetic rotating particle field (world-space, scrolls with camera).
    const a = (13 * Math.PI) / 180;
    const cos = Math.cos(a);
    const sin = Math.sin(a);
    ctx.globalAlpha = 0.15;
    for (const p of particles) {
      const nx = cos * (p.x - p.tx) + sin * (p.y - p.ty) + p.tx;
      const ny = cos * (p.y - p.ty) - sin * (p.x - p.tx) + p.ty;
      p.x = nx;
      p.y = ny;
      const [px, py] = toScreen(p.x, p.y);
      ctx.beginPath();
      ctx.arc(px, py, p.r, 0, Math.PI * 2);
      ctx.fillStyle = PALETTE[p.color % PALETTE.length];
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Food. Pellets carry a radius; dropped (carcass) pellets render at lower
    // opacity so they read differently from spawned food.
    for (const f of game.foods) {
      const [fx, fy] = toScreen(f.x, f.y);
      ctx.globalAlpha = f.dropped ? 0.61 : 1.0;
      ctx.fillStyle = '#ffd166';
      ctx.beginPath();
      ctx.arc(fx, fy, (f.r || 10) * s, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Snakes. Each body segment is a circle of radius `girth`, stroked so the
    // overlapping circles read as a scaling tube. The head is drawn on top.
    for (const pl of list) {
      // Bots are colored by their strategy; humans keep a random palette color.
      const col = pl.is_bot && pl.strategy && STRATEGY_COLORS[pl.strategy]
        ? STRATEGY_COLORS[pl.strategy]
        : colorFor(pl.id);
      const girthPx = (pl.girth || 6) * s;

      ctx.globalAlpha = pl.alive ? 1 : 0.3;
      ctx.fillStyle = col;
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.22)';
      ctx.lineWidth = 1;
      if (pl.points && pl.points.length) {
        for (const pt of pl.points) {
          const [px, py] = toScreen(pt[0], pt[1]);
          ctx.beginPath();
          ctx.arc(px, py, girthPx, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
      }

      const [hx, hy] = toScreen(pl.x, pl.y);
      ctx.beginPath();
      ctx.arc(hx, hy, girthPx, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.fill();

      if (pl.username) {
        ctx.globalAlpha = pl.alive ? 0.9 : 0.4;
        ctx.fillStyle = '#e6edf3';
        ctx.font = '11px "Silkscreen", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(pl.username, hx, hy - girthPx - 4);
      }
    }
    ctx.globalAlpha = 1;
  }

  function loop() {
    const now = performance.now();
    let dt = (now - lastFrame) / 1000;
    lastFrame = now;
    if (dt > 0.1) dt = 0.1; // clamp after the tab was backgrounded
    if (dt > 0) fps = fps * 0.9 + (1 / dt) * 0.1;
    game.step(dt);
    draw();
    if (showOverlay) updateStats();
    raf = requestAnimationFrame(loop);
  }

  onMount(() => {
    game.onScore = (sc) => (selfScore = sc);
    // Preload the pixel font so canvas labels don't flash a fallback.
    if (document.fonts && document.fonts.load) {
      document.fonts.load('11px "Silkscreen"');
      document.fonts.load('700 11px "Silkscreen"');
    }
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    connect();
    lastFrame = performance.now();
    raf = requestAnimationFrame(loop);
  });

  onDestroy(() => {
    cancelAnimationFrame(raf);
    window.removeEventListener('keydown', onKeyDown);
    window.removeEventListener('keyup', onKeyUp);
    if (ws) ws.close();
  });
</script>

  <div class="game" role="application" on:mousedown={onMouseDown} on:mouseup={onMouseUp} on:contextmenu={onContextMenu}>
    <canvas bind:this={canvas} on:mousemove={onMouseMove}></canvas>
    <div class="hud">
      <span class="status {status}">{status}</span>
      {#if selfId}
        <span class="score">score {selfScore}</span>
      {/if}
    </div>

    {#if showOverlay}
      <div class="overlay">
        <div class="panel">
          <h2>Debug / Leaderboard</h2>
          <div class="cols">
            <div class="col">
              <h3>Stats</h3>
              <ul>
                <li>FPS: {stats.fps}</li>
                <li>Tick rate: {stats.tickHz} Hz</li>
                <li>Snapshot: {stats.snapMs} ms</li>
                <li>Players: {stats.players} (humans {stats.humans}, bots {stats.bots})</li>
                <li>Food: {stats.food}</li>
                <li>You — score {stats.selfScore}, girth {stats.selfGirth}, length {stats.selfLength}, {stats.selfAlive ? 'alive' : 'dead'}{stats.boosting ? ', BOOSTING' : ''}</li>
              </ul>
            </div>
            <div class="col">
              <h3>Leaderboard</h3>
              <ol>
                {#each stats.leaderboard as p}
                  <li><span class="swatch" style="background:{p.color}"></span>{p.name} — {p.score}</li>
                {/each}
              </ol>
            </div>
            <div class="col">
              <h3>Legend</h3>
              <ul>
                {#each legend as s}
                  <li><span class="swatch" style="background:{s.color}"></span>{s.name}</li>
                {/each}
                <li><span class="swatch" style="background:linear-gradient(90deg,#1f77b4,#ff7f0e)"></span>Humans (random)</li>
              </ul>
              <p class="hint">Left-click / Shift: boost · Right-click / L: toggle this</p>
            </div>
          </div>
        </div>
      </div>
    {/if}
  </div>

<style>
  .game {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  canvas {
    display: block;
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    background: #0b0f14;
    cursor: crosshair;
  }
  .hud {
    position: absolute;
    top: 0.5rem;
    left: 0.5rem;
    display: flex;
    gap: 0.75rem;
    font-size: 0.8rem;
    color: #9fb0c0;
    pointer-events: none;
  }
  .status.open {
    color: #3fb950;
  }
  .status.closed,
  .status.connecting {
    color: #d29922;
  }
  .overlay {
    position: absolute;
    inset: 0;
    background: rgba(5, 8, 12, 0.72);
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    z-index: 10;
  }
  .panel {
    background: #0e141b;
    border: 1px solid #2a3642;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    color: #c9d6e2;
    font: 13px/1.5 ui-monospace, Menlo, Consolas, monospace;
    max-width: 92vw;
  }
  .panel h2 { margin: 0 0 0.5rem; font-size: 15px; color: #e6edf3; }
  .panel h3 { margin: 0.5rem 0 0.25rem; font-size: 12px; color: #9fb0c0; text-transform: uppercase; letter-spacing: 0.04em; }
  .cols { display: flex; gap: 2rem; flex-wrap: wrap; }
  .col { min-width: 190px; }
  .panel ul, .panel ol { margin: 0; padding-left: 1.1rem; }
  .panel li { margin: 2px 0; }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
  .hint { margin-top: 0.75rem; color: #6b7c8c; font-size: 11px; }
</style>
