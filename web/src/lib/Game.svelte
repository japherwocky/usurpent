<script>
  import { onMount, onDestroy } from 'svelte';
  import { Game, colorFor, PALETTE } from './netcode.js';

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

  function sendTarget(lx, ly) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', target: { x: lx, y: ly } }));
    }
  }

  function onMouseMove(e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const sx = w / game.mapW;
    const sy = h / game.mapH;
    // Logical y is "up positive" (matches the server's display flip).
    const lx = mx / sx;
    const ly = (h - my) / sy;
    game.selfTarget = { x: lx, y: ly };
    sendTarget(lx, ly);
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

    const sx = w / game.mapW;
    const sy = h / game.mapH;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Cosmetic rotating particle field.
    const a = (13 * Math.PI) / 180;
    const cos = Math.cos(a);
    const sin = Math.sin(a);
    ctx.globalAlpha = 0.15;
    for (const p of particles) {
      const nx = cos * (p.x - p.tx) + sin * (p.y - p.ty) + p.tx;
      const ny = cos * (p.y - p.ty) - sin * (p.x - p.tx) + p.ty;
      p.x = nx;
      p.y = ny;
      ctx.beginPath();
      ctx.arc(p.x * sx, h - p.y * sy, p.r, 0, Math.PI * 2);
      ctx.fillStyle = PALETTE[p.color % PALETTE.length];
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Food.
    ctx.fillStyle = '#ffd166';
    for (const f of game.foods) {
      ctx.beginPath();
      ctx.arc(f.x * sx, h - f.y * sy, 5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Snakes.
    const now = performance.now();
    const alpha = game.alpha(now);
    for (const pl of game.renderList(alpha)) {
      const col = colorFor(pl.id);

      if (pl.points && pl.points.length) {
        ctx.beginPath();
        for (let i = 0; i < pl.points.length; i++) {
          const px = pl.points[i][0] * sx;
          const py = h - pl.points[i][1] * sy;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.strokeStyle = col;
        ctx.lineWidth = 6;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.globalAlpha = pl.alive ? 0.9 : 0.25;
        ctx.stroke();
      }

      ctx.beginPath();
      ctx.arc(pl.x * sx, h - pl.y * sy, 7 + Math.min(pl.score, 30) * 0.2, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.globalAlpha = pl.alive ? 1 : 0.4;
      ctx.fill();

      if (pl.username) {
        ctx.globalAlpha = pl.alive ? 0.9 : 0.4;
        ctx.fillStyle = '#e6edf3';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(pl.username, pl.x * sx, h - pl.y * sy - 12);
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
    game.onScore = (s) => (selfScore = s);
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
