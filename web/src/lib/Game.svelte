<script>
  import { onMount, onDestroy } from 'svelte';
  import { Game, colorFor, PALETTE, STRATEGY_COLORS } from './netcode.js';

  let canvas;
  let status = 'connecting';
  let selfId = null;
  let selfScore = 0;

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
    ws = new WebSocket(`${proto}://${location.host}/ws`);
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
        ctx.font = '11px sans-serif';
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
    game.step(dt);
    draw();
    raf = requestAnimationFrame(loop);
  }

  onMount(() => {
    game.onScore = (sc) => (selfScore = sc);
    connect();
    lastFrame = performance.now();
    raf = requestAnimationFrame(loop);
  });

  onDestroy(() => {
    cancelAnimationFrame(raf);
    if (ws) ws.close();
  });
</script>

<div class="game">
  <canvas bind:this={canvas} on:mousemove={onMouseMove}></canvas>
  <div class="hud">
    <span class="status {status}">{status}</span>
    {#if selfId}
      <span class="score">score {selfScore}</span>
    {/if}
  </div>
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
</style>
