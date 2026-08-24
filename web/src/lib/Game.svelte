<script>
  import { onMount, onDestroy } from 'svelte';
  import { Game, foodColor, serpentColor, PALETTE, STRATEGY_COLORS } from './netcode.js';

  // Display name chosen in the lobby; sent to the server on connect.
  export let name = '';

  let canvas;
  let status = 'connecting';
  let selfId = null;
  let selfScore = 0;

  // Death state. The server keeps a dead human dead until they ask to come
  // back, so `selfScore` still holds the score of the life they just lost and
  // the card can show it. `canRespawn` mirrors the server's RESPAWN_DELAY.
  let alive = true;
  let deathAt = 0;
  let canRespawn = false;
  let respawnBtn;

  // Leaderboard, rebuilt on a timer rather than every frame -- it is a sort
  // over every player on the map, and nobody can read it at 60 Hz anyway.
  const BOARD_HZ = 4;
  const BOARD_ROWS = 5;
  let board = [];
  let selfRow = null; // set only when the player is outside the visible rows
  let lastBoardAt = 0;

  // Right-click panel: frame timings and the bot-strategy legend. Purely a
  // developer read-out, so it lives in a corner instead of over the game.
  let showDebug = false;
  let debug = { fps: 0, tickHz: 0, snapMs: 0, players: 0, humans: 0, bots: 0,
                visible: 0, food: 0, girth: 0, length: 0, boosting: false };
  // Grid overlay: 0 off, 1 the food grid, 2 the body grid. Cycled with G.
  // Both are the same SpatialGrid on the server with different cell sizes,
  // which is easier to believe once you can see them on the field.
  let gridMode = 0;
  const GRID_MODES = [
    null,
    { label: 'food', color: '250, 204, 21' },
    { label: 'bodies', color: '124, 198, 255' },
  ];
  // Controls reminder, faded out once the player has had time to read it.
  let showHint = true;
  let hintTimer = 0;

  // Surfaced in the grid badge; written by draw(), read by the markup.
  let gridCell = 0;
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

  // Leaderboard scores run to six figures; a column of them needs to stay a
  // column, so anything over a thousand is abbreviated.
  function short(n) {
    if (n < 1000) return String(n);
    if (n < 100000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return Math.round(n / 1000) + 'k';
  }

  // Focus the button the moment it goes live, so Enter or Space respawns
  // without reaching for the mouse.
  $: if (canRespawn && respawnBtn) respawnBtn.focus();

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

  // How far this window can see from the head, in world units: half of its
  // longer axis. The server only sends food within this, so a small window
  // costs a fraction of what a wide one does. Recomputed on resize.
  function viewRadius() {
    const w = canvas ? canvas.clientWidth : window.innerWidth;
    const h = canvas ? canvas.clientHeight : window.innerHeight;
    const s = Math.min(w, h) / VIEW_WORLD;
    return Math.max(w, h) / s / 2;
  }

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', ...msg }));
    }
  }

  function sendView() {
    send({ view: viewRadius() });
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams();
    if (name) params.set('name', name);
    // Sent on the handshake so even the welcome payload is sized to us.
    params.set('view', String(Math.round(viewRadius())));
    const q = `?${params.toString()}`;
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
      } else if (msg.type === 'leaderboard') {
        game.onLeaderboard(msg);
        updateBoard();
      }
    };
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
    send({ target: { x: dx, y: dy } });
  }

  function updateBoost() {
    const b = mouseBoost || keyBoost;
    game.selfBoosting = b;
    send({ boost: b });
  }
  function toggleDebug() {
    showDebug = !showDebug;
  }
  function respawn() {
    if (!canRespawn) return;
    send({ respawn: true });
  }
  function onMouseDown(e) {
    // Dead serpents don't boost. Gating here rather than stopping propagation
    // on the death card means the click that hits RESPAWN can't also be read
    // as a boost, and the a11y tree keeps a plain <div> over the canvas.
    if (e.button === 0 && alive) { mouseBoost = true; updateBoost(); }
  }
  function onMouseUp(e) {
    if (e.button === 0) { mouseBoost = false; updateBoost(); }
  }
  function onContextMenu(e) {
    e.preventDefault();
    toggleDebug();
  }
  // Shift = boost, L = stats, G = cycle the grid overlay.
  //
  // Matched on `code` OR `key`. `code` is the layout-independent one and the
  // right default, but it is empty on synthesised events, and a letter
  // shortcut has no reason to be picky about which of the two it got.
  const isShift = (e) => e.code === 'ShiftLeft' || e.code === 'ShiftRight'
    || e.key === 'Shift';
  const isKey = (e, code, letter) => e.code === code
    || (e.key || '').toLowerCase() === letter;

  function onKeyDown(e) {
    if (isShift(e)) { keyBoost = true; updateBoost(); }
    else if (isKey(e, 'KeyL', 'l')) { toggleDebug(); }
    else if (isKey(e, 'KeyG', 'g')) { gridMode = (gridMode + 1) % GRID_MODES.length; }
  }
  function onKeyUp(e) {
    if (isShift(e)) { keyBoost = false; updateBoost(); }
  }

  // Built from the leaderboard message rather than from the snapshot: a
  // snapshot now carries only the serpents in view, so deriving standings from
  // one would rank whoever happens to be nearby. Rebuilt when that message
  // arrives instead of on a timer of our own.
  function updateBoard() {
    const ranked = game.leaderboard.map((p, i) => ({
      rank: i + 1,
      id: p.id,
      name: p.username || (p.is_bot ? 'Bot' : '???'),
      score: p.score,
      color: serpentColor(p),
      isSelf: p.id === game.selfId,
    }));
    board = ranked.slice(0, BOARD_ROWS);
    // Pin the player's own row underneath when they haven't cracked the top.
    const shown = ranked.slice(0, BOARD_ROWS).some((r) => r.isSelf);
    const self = game.players[game.selfId];
    selfRow = !shown && game.selfRank && self
      ? {
          rank: game.selfRank,
          id: game.selfId,
          name: self.server.username || '???',
          score: self.server.score,
          color: serpentColor(self.server),
          isSelf: true,
        }
      : null;
  }

  function updateDebug() {
    const self = game.players[game.selfId];
    debug = {
      fps: Math.round(fps),
      tickHz: game.sim.tickHz,
      snapMs: Math.round(game.snapInterval),
      // Totals are map-wide (from the leaderboard message); `visible` is what
      // interest culling actually put on the wire for us this tick.
      players: game.totalPlayers,
      humans: game.totalPlayers - game.totalBots,
      bots: game.totalBots,
      visible: Object.keys(game.players).length,
      food: game.foods.length,
      girth: self ? self.server.girth : 0,
      length: self ? self.server.length : 0,
      boosting: game.selfBoosting,
    };
  }

  // Watch for the alive -> dead edge (and back) so the death card appears
  // once, on the transition, rather than being recomputed every frame.
  function updateLifeState(now) {
    const self = game.players[game.selfId];
    const nowAlive = self ? self.server.alive : true;
    if (nowAlive !== alive) {
      alive = nowAlive;
      if (!alive) {
        deathAt = now;
        canRespawn = false;
        showHint = false;
      }
    }
    if (!alive && !canRespawn && now - deathAt >= game.respawnDelay * 1000) {
      canRespawn = true;
    }
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

    // The camera shows a few hundred world units of a 10000-unit map -- well
    // under 1% of its area -- but everything used to be drawn regardless, so
    // over 90% of the arcs fell entirely outside the canvas. Test in world
    // space (cheaper than projecting first) and skip what cannot be seen.
    const cullMinX = camX - viewW / 2;
    const cullMaxX = camX + viewW / 2;
    const cullMinY = camY - viewH / 2;
    const cullMaxY = camY + viewH / 2;
    const visible = (wx, wy, radius) =>
      wx + radius >= cullMinX && wx - radius <= cullMaxX &&
      wy + radius >= cullMinY && wy - radius <= cullMaxY;

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

    // Spatial grid overlay. Buckets what is on screen by the server's own cell
    // size and shades each cell by how full it is, so the thing being drawn is
    // the lookup the server actually does rather than a picture of one. The
    // 3x3 block a query walks is the cell plus its neighbours, which is why
    // the cell has to be at least as wide as the longest reach -- easier to
    // see than to argue about.
    const gridSpec = GRID_MODES[gridMode];
    if (gridSpec) {
      const cell = gridMode === 1 ? game.foodGridCell : game.bodyGridCell;
      if (cell > 0) {
        const counts = new Map();
        let busiest = 0;
        const tally = (wx, wy) => {
          const key = Math.floor(wx / cell) + ':' + Math.floor(wy / cell);
          const n = (counts.get(key) || 0) + 1;
          counts.set(key, n);
          if (n > busiest) busiest = n;
        };
        if (gridMode === 1) {
          for (const f of game.foods) tally(f.x, f.y);
        } else {
          for (const pl of list) {
            if (!pl.alive || !pl.points) continue;
            for (const pt of pl.points) tally(pt[0], pt[1]);
          }
        }
        const gx0 = Math.floor(cullMinX / cell);
        const gx1 = Math.floor(cullMaxX / cell);
        const gy0 = Math.floor(cullMinY / cell);
        const gy1 = Math.floor(cullMaxY / cell);
        ctx.save();
        for (let gx = gx0; gx <= gx1; gx++) {
          for (let gy = gy0; gy <= gy1; gy++) {
            const n = counts.get(gx + ':' + gy);
            if (!n) continue;
            const [x0, y1] = toScreen(gx * cell, gy * cell);
            const [x1, y0] = toScreen((gx + 1) * cell, (gy + 1) * cell);
            ctx.fillStyle = `rgba(${gridSpec.color}, ${0.05 + 0.16 * (n / busiest)})`;
            ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
          }
        }
        ctx.strokeStyle = `rgba(${gridSpec.color}, 0.22)`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let gx = gx0; gx <= gx1 + 1; gx++) {
          const [sx] = toScreen(gx * cell, 0);
          ctx.moveTo(sx, 0);
          ctx.lineTo(sx, h);
        }
        for (let gy = gy0; gy <= gy1 + 1; gy++) {
          const [, sy] = toScreen(0, gy * cell);
          ctx.moveTo(0, sy);
          ctx.lineTo(w, sy);
        }
        ctx.stroke();
        ctx.restore();
        // Guarded: draw() runs every frame, and an unconditional reactive
        // write here would schedule a Svelte update sixty times a second to
        // re-render a number that almost never changes.
        if (gridCell !== cell) gridCell = cell;
      }
    }

    // Cosmetic rotating particle field (world-space, scrolls with camera).
    const a = (13 * Math.PI) / 180;
    const cos = Math.cos(a);
    const sin = Math.sin(a);
    ctx.globalAlpha = 0.15;
    for (const p of particles) {
      // Keep orbiting every particle even when it is off screen, or they would
      // freeze in place and jump when the camera catches up; only the draw is
      // skipped. p.r is already in screen pixels, so convert it back for the
      // world-space test.
      const nx = cos * (p.x - p.tx) + sin * (p.y - p.ty) + p.tx;
      const ny = cos * (p.y - p.ty) - sin * (p.x - p.tx) + p.ty;
      p.x = nx;
      p.y = ny;
      if (!visible(p.x, p.y, p.r / s)) continue;
      const [px, py] = toScreen(p.x, p.y);
      ctx.beginPath();
      ctx.arc(px, py, p.r, 0, Math.PI * 2);
      ctx.fillStyle = PALETTE[p.color % PALETTE.length];
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Food. Pellets are colored by SIZE, ramped across the range the server
    // reports in the welcome: a crumb is lime, a blob that has merged its way
    // to the cap is red. Size is the thing a player is deciding on -- whether
    // that speck across the map is worth the trip -- and every pellet used to
    // be the same flat amber. Dropped (carcass) pellets keep their lower
    // opacity, so a fresh kill still reads differently from spawned food.
    for (const f of game.foods) {
      const fr = f.r || 10;
      if (!visible(f.x, f.y, fr)) continue;
      const [fx, fy] = toScreen(f.x, f.y);
      ctx.globalAlpha = f.dropped ? 0.61 : 1.0;
      ctx.fillStyle = foodColor(fr, game.foodMinRadius, game.foodMaxRadius);
      ctx.beginPath();
      ctx.arc(fx, fy, fr * s, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Snakes. Each body segment is a circle of radius `girth`, stroked so the
    // overlapping circles read as a scaling tube. The head is drawn on top.
    for (const pl of list) {
      // A dead serpent has already burst into carcass pellets, and the server
      // sends it with no body. Drawing its head would leave a marker where
      // there is no longer anything to collide with.
      if (!pl.alive) continue;
      // Bots are colored by their strategy; humans keep a random palette color.
      const col = serpentColor(pl);
      const girthPx = (pl.girth || 6) * s;

      ctx.fillStyle = col;
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.22)';
      ctx.lineWidth = 1;
      if (pl.points && pl.points.length) {
        // Points carry their own alpha so segments entering at the head and
        // leaving at the tail fade rather than pop (see queuedPoints).
        const girthWorld = pl.girth || 6;
        for (const pt of pl.points) {
          const a = pt.length > 2 ? pt[2] : 1;
          if (a <= 0.01) continue;
          if (!visible(pt[0], pt[1], girthWorld)) continue;
          ctx.globalAlpha = a;
          const [px, py] = toScreen(pt[0], pt[1]);
          ctx.beginPath();
          ctx.arc(px, py, girthPx * (0.55 + 0.45 * a), 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;

      // Most serpents on the map are nowhere near the camera; skip the head
      // and its label too, not just the body. The name sits above the head, so
      // allow a little extra height before culling it away.
      const headVisible = visible(pl.x, pl.y, (pl.girth || 6) + 24 / s);
      if (!headVisible) continue;

      const [hx, hy] = toScreen(pl.x, pl.y);
      ctx.beginPath();
      ctx.arc(hx, hy, girthPx, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.fill();

      if (pl.username) {
        ctx.globalAlpha = 0.9;
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
    updateLifeState(now);
    // The board rebuilds when its message lands, not on a clock of ours.
    if (showDebug && now - lastBoardAt >= 1000 / BOARD_HZ) {
      updateDebug();
      lastBoardAt = now;
    }
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
    window.addEventListener('resize', sendView);
    connect();
    lastFrame = performance.now();
    raf = requestAnimationFrame(loop);
    hintTimer = setTimeout(() => (showHint = false), 7000);
  });

  onDestroy(() => {
    cancelAnimationFrame(raf);
    clearTimeout(hintTimer);
    window.removeEventListener('keydown', onKeyDown);
    window.removeEventListener('keyup', onKeyUp);
    window.removeEventListener('resize', sendView);
    if (ws) ws.close();
  });
</script>

<div class="game" role="application" on:mousedown={onMouseDown} on:mouseup={onMouseUp} on:contextmenu={onContextMenu}>
  <canvas bind:this={canvas} on:mousemove={onMouseMove}></canvas>

  <!-- Score. The one number the player is actually playing for, so it gets
       the display face and the size to match. -->
  <div class="hud-score">
    <span class="label">Score</span>
    {#key selfScore}
      <span class="value">{selfScore.toLocaleString()}</span>
    {/key}
  </div>

  <!-- Connection state only surfaces when there is something wrong with it.
       A permanent "open" badge is a developer's reassurance, not a player's. -->
  {#if status !== 'open'}
    <div class="conn {status}">
      {status === 'connecting' ? 'Connecting…' : 'Disconnected'}
    </div>
  {/if}

  {#if gridMode}
    <div class="grid-badge">
      <span class="sw" style="background:rgb({GRID_MODES[gridMode].color})"></span>
      grid · {GRID_MODES[gridMode].label} · {Math.round(gridCell)}u
    </div>
  {/if}

  {#if board.length}
    <div class="board">
      <h2>Leaderboard</h2>
      <ol>
        {#each board as row (row.id)}
          <li class:me={row.isSelf}>
            <span class="rank">{row.rank}</span>
            <span class="swatch" style="background:{row.color}"></span>
            <span class="who">{row.name}</span>
            <span class="pts">{short(row.score)}</span>
          </li>
        {/each}
        {#if selfRow}
          <li class="me pinned">
            <span class="rank">{selfRow.rank}</span>
            <span class="swatch" style="background:{selfRow.color}"></span>
            <span class="who">{selfRow.name}</span>
            <span class="pts">{short(selfRow.score)}</span>
          </li>
        {/if}
      </ol>
    </div>
  {/if}

  <div class="hint" class:gone={!showHint}>
    <kbd>mouse</kbd> steer <span class="dot">·</span>
    <kbd>click</kbd> boost <span class="dot">·</span>
    <kbd>right-click</kbd> stats
  </div>

  {#if showDebug}
    <div class="debug">
      <h2>Stats</h2>
      <dl>
        <dt>fps</dt><dd>{debug.fps}</dd>
        <dt>tick</dt><dd>{debug.tickHz} Hz</dd>
        <dt>snapshot</dt><dd>{debug.snapMs} ms</dd>
        <dt>players</dt><dd>{debug.humans}H / {debug.bots}B</dd>
        <dt>in view</dt><dd>{debug.visible}</dd>
        <dt>grid f/b</dt><dd>{Math.round(game.foodGridCell)}/{Math.round(game.bodyGridCell)}u</dd>
        <dt>food</dt><dd>{debug.food}</dd>
        <dt>girth</dt><dd>{debug.girth}</dd>
        <dt>length</dt><dd>{debug.length}{debug.boosting ? ' · boost' : ''}</dd>
      </dl>
      <h2>Legend</h2>
      <ul>
        {#each legend as s}
          <li><span class="swatch" style="background:{s.color}"></span>{s.name}</li>
        {/each}
        <li><span class="swatch" style="background:linear-gradient(90deg,#1f77b4,#ff7f0e)"></span>humans</li>
      </ul>
      <h2>Pellet size</h2>
      <div class="ramp">
        <span class="bar"></span>
        <span class="ends"><i>crumb</i><i>blob</i></span>
      </div>
    </div>
  {/if}

  {#if !alive}
    <div class="death">
      <div class="death-card">
        <h2>You died</h2>
        <div class="final">
          <span class="label">Score</span>
          <span class="value">{selfScore.toLocaleString()}</span>
        </div>
        <button bind:this={respawnBtn} class="respawn" on:click={respawn} disabled={!canRespawn}>
          RESPAWN
        </button>
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
    background: var(--bg);
    cursor: crosshair;
  }

  /* --- Score ------------------------------------------------------------ */
  .hud-score {
    position: absolute;
    top: 0.9rem;
    left: 1.1rem;
    pointer-events: none;
  }
  .hud-score .label {
    display: block;
    font-family: var(--font-display);
    font-size: 0.6rem;
    letter-spacing: 0.22em;
    color: var(--ink-faint);
  }
  .hud-score .value {
    display: block;
    margin-top: 0.15rem;
    font-family: var(--font-display);
    font-size: 1.75rem;
    line-height: 1;
    color: var(--ink);
    text-shadow: 0 0 18px var(--glow);
    /* Re-keyed on every change, so the animation replays as you eat. */
    animation: pop 220ms ease-out;
  }
  @keyframes pop {
    from { transform: scale(1.18); color: var(--accent-hi); }
    to { transform: scale(1); color: var(--ink); }
  }

  /* --- Connection ------------------------------------------------------- */
  .conn {
    position: absolute;
    top: 0.9rem;
    left: 50%;
    transform: translateX(-50%);
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid currentColor;
    background: rgba(7, 11, 18, 0.85);
    font-size: 0.72rem;
    pointer-events: none;
  }
  .conn.connecting { color: var(--warn); }
  .conn.closed { color: var(--bad); }

  /* --- Grid badge ------------------------------------------------------- */
  .grid-badge {
    position: absolute;
    top: 0.9rem;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: rgba(7, 11, 18, 0.85);
    font-size: 0.7rem;
    color: var(--ink-dim);
    pointer-events: none;
  }
  .grid-badge .sw {
    width: 8px;
    height: 8px;
    border-radius: 2px;
  }

  /* --- Leaderboard ------------------------------------------------------ */
  .board {
    position: absolute;
    top: 0.9rem;
    right: 1.1rem;
    width: 12.5rem;
    padding: 0.6rem 0.7rem 0.5rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: rgba(13, 20, 31, 0.72);
    backdrop-filter: blur(6px);
    pointer-events: none;
  }
  .board h2 {
    margin: 0 0 0.45rem;
    font-family: var(--font-display);
    font-size: 0.58rem;
    letter-spacing: 0.18em;
    color: var(--ink-faint);
  }
  .board ol {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .board li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.15rem 0;
    font-size: 0.74rem;
    color: var(--ink-dim);
  }
  .board .rank {
    width: 1.1rem;
    font-family: var(--font-display);
    font-size: 0.6rem;
    color: var(--ink-faint);
  }
  .board .who {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .board .pts {
    font-family: var(--font-display);
    font-size: 0.68rem;
    color: var(--ink);
  }
  .board li.me {
    color: var(--accent-hi);
  }
  .board li.me .pts,
  .board li.me .rank {
    color: var(--accent-hi);
  }
  /* Your own row, pinned below the cut when you aren't in the top five. */
  .board li.pinned {
    margin-top: 0.25rem;
    padding-top: 0.35rem;
    border-top: 1px dashed var(--line);
  }
  .swatch {
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 2px;
  }

  /* --- Controls hint ---------------------------------------------------- */
  .hint {
    position: absolute;
    left: 50%;
    bottom: 1.1rem;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.35rem;
    white-space: nowrap;
    font-size: 0.72rem;
    color: var(--ink-faint);
    pointer-events: none;
    opacity: 1;
    transition: opacity 900ms ease;
  }
  .hint.gone {
    opacity: 0;
  }
  .hint kbd {
    padding: 0.1rem 0.35rem;
    border: 1px solid var(--line);
    border-bottom-width: 2px;
    border-radius: 4px;
    background: rgba(6, 10, 16, 0.8);
    font-family: var(--font-ui);
    font-size: 0.68rem;
    color: var(--ink-dim);
  }
  .hint .dot {
    color: var(--line-strong);
  }

  /* --- Debug panel ------------------------------------------------------ */
  .debug {
    position: absolute;
    left: 1.1rem;
    bottom: 1.1rem;
    width: 11rem;
    padding: 0.6rem 0.7rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: rgba(13, 20, 31, 0.82);
    backdrop-filter: blur(6px);
    pointer-events: none;
  }
  .debug h2 {
    margin: 0 0 0.35rem;
    font-family: var(--font-display);
    font-size: 0.58rem;
    letter-spacing: 0.18em;
    color: var(--ink-faint);
  }

  .debug dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.1rem 0.5rem;
    /* Room between the stats block and the legend heading under it. */
    margin: 0 0 0.85rem;
    font-size: 0.7rem;
  }
  .debug dt {
    color: var(--ink-faint);
  }
  .debug dd {
    margin: 0;
    text-align: right;
    font-family: var(--font-mono);
    color: var(--ink-dim);
  }
  .debug ul {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.7rem;
    color: var(--ink-dim);
  }
  .debug li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.08rem 0;
  }
  /* Mirrors FOOD_RAMP in netcode.js -- keep the two in step. */
  .ramp .bar {
    display: block;
    height: 7px;
    border-radius: 2px;
    background: linear-gradient(90deg, #a3e635, #facc15, #fb923c, #dc2626);
  }
  .ramp .ends {
    display: flex;
    justify-content: space-between;
    margin-top: 0.15rem;
    font-size: 0.62rem;
    font-style: normal;
    color: var(--ink-faint);
  }
  .ramp .ends i {
    font-style: normal;
  }

  /* --- Death card ------------------------------------------------------- */
  .death {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(40rem 26rem at 50% 50%, rgba(7, 11, 18, 0.82), rgba(7, 11, 18, 0.55));
    z-index: 10;
  }
  .death-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 1.75rem 2.5rem;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: var(--shadow);
    animation: rise 220ms ease-out;
  }
  @keyframes rise {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: none; }
  }
  .death-card h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.15rem;
    letter-spacing: 0.2em;
    text-indent: 0.2em;
    color: var(--bad);
  }
  .final {
    text-align: center;
  }
  .final .label {
    display: block;
    font-family: var(--font-display);
    font-size: 0.58rem;
    letter-spacing: 0.22em;
    color: var(--ink-faint);
  }
  .final .value {
    display: block;
    margin-top: 0.25rem;
    font-family: var(--font-display);
    font-size: 2.1rem;
    line-height: 1;
    color: var(--ink);
    text-shadow: 0 0 18px var(--glow);
  }
  .respawn {
    padding: 0.7rem 2rem;
    border: none;
    border-radius: var(--radius-sm);
    background: linear-gradient(180deg, var(--accent), var(--accent-deep));
    color: #fff;
    font-family: var(--font-display);
    font-size: 0.85rem;
    letter-spacing: 0.2em;
    text-indent: 0.2em;
    cursor: pointer;
    transition: box-shadow 140ms ease, filter 140ms ease;
  }
  .respawn:hover:not(:disabled) {
    filter: brightness(1.1);
    box-shadow: 0 0 22px 0 var(--glow);
  }
  /* Greyed for the server's RESPAWN_DELAY: the request would be rejected
     until then, so the button should not invite the click. */
  .respawn:disabled {
    background: var(--surface-2);
    color: var(--ink-faint);
    cursor: default;
  }
</style>
