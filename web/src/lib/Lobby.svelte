<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import Auth from './Auth.svelte';
  import { fetchModes } from './api.js';

  const dispatch = createEventDispatcher();

  const ADJECTIVES = [
    'Quick', 'Lazy', 'Sly', 'Bold', 'Calm', 'Wild', 'Iron', 'Crimson',
    'Shadow', 'Neon', 'Ancient', 'Hungry', 'Silent', 'Feral', 'Cosmic',
  ];
  const ANIMALS = [
    'Viper', 'Cobra', 'Adder', 'Mamba', 'Python', 'Serpent', 'Wyrm',
    'Eel', 'Naga', 'Boa', 'Rattler', 'Krait', 'Asp', 'Hydra',
  ];
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const randomName = () => pick(ADJECTIVES) + pick(ANIMALS);

  const NAME_RE = /^[A-Za-z0-9_-]{3,32}$/;

  const CONTROLS = [
    { action: 'Steer', keys: ['mouse'] },
    { action: 'Boost', keys: ['click', 'shift'] },
    { action: 'Stats', keys: ['right-click', 'L'] },
    { action: 'Grid', keys: ['G'] },
  ];

  // The guest name. Only ever used while signed out -- a signed-in player is
  // their account, see accountName below.
  let name = randomName();
  let touched = false;
  let session = null;

  // Signed in, there is no name to choose: you are your account. Leaving the
  // field editable meant the lobby showed two identities at once, and since
  // the server prefers a client-supplied name over the account
  // (usurpent.py:925) you could play as "LazyEel" while the score was
  // credited to "japherwocky".
  $: accountName = session && !session.guest && session.username ? session.username : null;

  // Shown under the field only once the player has typed something invalid,
  // so a first-time visitor sees a clean form rather than a rule they have
  // not broken yet.
  $: invalid = touched && name.length > 0 && !NAME_RE.test(name);

  // Joinable modes, served by /api/modes. The client renders buttons from
  // this list and never hardcodes one, so a mode added server-side shows up
  // without a client change. The last pick is remembered like the name.
  let modes = [];
  let modeId = 'classic';
  // If /api/modes is unreachable the picker hides but PLAY must still work,
  // so `selected` falls back to classic rather than to nothing.
  const FALLBACK_MODE = { id: 'classic', name: 'Classic', description: '' };
  $: selected = modes.find((m) => m.id === modeId) || modes[0] || FALLBACK_MODE;

  onMount(() => {
    // Remember the last name a returning player used. This is the guest name
    // and stays that way: signing in does not overwrite it, so signing out
    // hands the player back the handle they had.
    const saved = localStorage.getItem('usurpent.name');
    if (saved) name = saved;
    // Same for the mode. A stale id (a mode the server no longer serves)
    // falls back to the first served mode via `selected` above.
    const savedMode = localStorage.getItem('usurpent.mode');
    if (savedMode) modeId = savedMode;
    fetchModes()
      .then((list) => (modes = list))
      .catch(() => (modes = []));
  });

  function pickMode(m) {
    modeId = m.id;
    localStorage.setItem('usurpent.mode', m.id);
  }

  function onSession(e) {
    session = e.detail;
  }

  function shuffle() {
    name = randomName();
    touched = true;
  }

  function play() {
    if (!selected) return;
    if (accountName) {
      dispatch('play', { name: accountName, mode: selected });
      return;
    }
    let n = (name || '').trim();
    if (!NAME_RE.test(n)) n = randomName();
    localStorage.setItem('usurpent.name', n);
    dispatch('play', { name: n, mode: selected });
  }
</script>

<section class="lobby">
  <div class="card">
    <header>
      <h1>USURPENT</h1>
      <div class="rule"></div>
      <p class="pitch">Real-time multiplayer snake. Eat, grow, survive.</p>
    </header>

    <div class="name">
      {#if accountName}
        <div class="identity">
          <span class="as">Playing as</span>
          <span class="who">{accountName}</span>
        </div>
        {#if session && session.banked > 0}
          <div class="wealth">
            <span class="as">Banked</span>
            <span class="amount">{session.banked.toLocaleString()}</span>
          </div>
        {/if}
      {:else}
        <div class="name-row">
          <input
            bind:value={name}
            on:input={() => (touched = true)}
            on:keydown={(e) => e.key === 'Enter' && play()}
            maxlength="32"
            autocomplete="off"
            spellcheck="false"
            aria-label="Your serpent name"
            aria-invalid={invalid}
            placeholder="your serpent name"
          />
          <button type="button" class="shuffle" on:click={shuffle} title="Pick a random name">
            ⟳
          </button>
        </div>
        {#if invalid}
          <span class="hint bad">3–32 characters: letters, numbers, _ or -</span>
        {/if}
      {/if}
    </div>

    <!-- Mode picker. Buttons carry the display face (they are titles);
         the description underneath is a sentence, so it keeps the UI face. -->
    {#if modes.length}
      <div class="modes">
        <div class="mode-row" role="radiogroup" aria-label="Game mode">
          {#each modes as m (m.id)}
            <button
              type="button"
              class="mode"
              class:active={selected && selected.id === m.id}
              role="radio"
              aria-checked={selected && selected.id === m.id}
              on:click={() => pickMode(m)}
            >
              {m.name}
            </button>
          {/each}
        </div>
        {#if selected}
          <p class="mode-desc">{selected.description}</p>
        {/if}
      </div>
    {/if}

    <button class="play" on:click={play}>PLAY</button>

    <ul class="controls">
      {#each CONTROLS as c}
        <li>
          <span class="action">{c.action}</span>
          <span class="keys">
            {#each c.keys as k, i}
              {#if i > 0}<span class="or">or</span>{/if}<kbd>{k}</kbd>
            {/each}
          </span>
        </li>
      {/each}
    </ul>

    <footer>
      <Auth on:session={onSession} />
    </footer>
  </div>
</section>

<style>
  .lobby {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    overflow: auto;
    /* A faint glow behind the card so the page isn't a flat black field. */
    background:
      radial-gradient(60rem 34rem at 50% 32%, rgba(47, 155, 255, 0.07), transparent 70%);
  }
  .card {
    width: 21rem;
    max-width: 100%;
    padding: 1.75rem 1.5rem 1.25rem;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
  }
  header {
    text-align: center;
  }
  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.9rem;
    letter-spacing: 0.28em;
    /* Nudge right: the wide tracking adds a trailing gap that reads as the
       word sitting off-center. */
    text-indent: 0.28em;
    color: var(--ink);
    text-shadow: 0 0 22px var(--glow);
  }
  .rule {
    height: 2px;
    margin: 0.9rem auto 0;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.65;
  }
  .pitch {
    margin: 0.75rem 0 0;
    color: var(--ink-faint);
    font-size: 0.78rem;
  }
  .name {
    margin-top: 1.5rem;
  }
  .name-row {
    display: flex;
    gap: 0.4rem;
  }
  /* Sized to match the guest name field, so the card doesn't jump height
     when a session resolves or the player signs out. */
  .identity {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.6rem 0.65rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--sunken);
  }
  .identity .as {
    flex: none;
    font-size: 0.72rem;
    color: var(--ink-faint);
  }
  .identity .who {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--font-display);
    font-size: 0.85rem;
    color: var(--accent-hi);
  }
  /* Extraction wealth, carried back into the lobby. Same sunken box as the
     identity line so the two read as one record. */
  .wealth {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-top: 0.4rem;
    padding: 0.6rem 0.65rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--sunken);
  }
  .wealth .as {
    flex: none;
    font-size: 0.72rem;
    color: var(--ink-faint);
  }
  .wealth .amount {
    font-family: var(--font-display);
    font-size: 0.85rem;
    color: #7cff4d;
  }
  input {
    flex: 1;
    min-width: 0;
    padding: 0.6rem 0.65rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--sunken);
    color: var(--ink);
    font-size: 0.9rem;
  }
  input:focus {
    border-color: var(--accent-deep);
    outline: none;
  }
  input[aria-invalid='true'] {
    border-color: var(--bad);
  }
  .shuffle {
    width: 2.4rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--surface-2);
    color: var(--ink-dim);
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
  }
  .shuffle:hover {
    color: var(--accent-hi);
    border-color: var(--accent-deep);
  }
  .hint {
    display: block;
    margin-top: 0.35rem;
    font-size: 0.7rem;
    color: var(--ink-faint);
  }
  .hint.bad {
    color: var(--bad);
  }
  .modes {
    margin-top: 0.9rem;
  }
  .mode-row {
    display: flex;
    gap: 0.4rem;
  }
  .mode {
    flex: 1;
    padding: 0.5rem 0.3rem;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--sunken);
    color: var(--ink-dim);
    font-family: var(--font-display);
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: border-color 140ms ease, color 140ms ease;
  }
  .mode:hover {
    color: var(--accent-hi);
    border-color: var(--accent-deep);
  }
  .mode.active {
    background: var(--surface-2);
    border-color: var(--accent-deep);
    color: var(--accent-hi);
  }
  .mode-desc {
    margin: 0.45rem 0 0;
    min-height: 2em;
    font-size: 0.7rem;
    line-height: 1.45;
    color: var(--ink-faint);
  }
  .play {
    margin-top: 0.75rem;
    width: 100%;
    padding: 0.75rem;
    border: none;
    border-radius: var(--radius-sm);
    background: linear-gradient(180deg, var(--accent), var(--accent-deep));
    color: #fff;
    font-family: var(--font-display);
    font-size: 1rem;
    letter-spacing: 0.22em;
    text-indent: 0.22em;
    cursor: pointer;
    box-shadow: 0 0 0 0 var(--glow);
    transition: box-shadow 140ms ease, filter 140ms ease;
  }
  .play:hover {
    filter: brightness(1.1);
    box-shadow: 0 0 22px 0 var(--glow);
  }
  .play:active {
    filter: brightness(0.95);
  }
  .controls {
    list-style: none;
    margin: 1.25rem 0 0;
    padding: 0;
  }
  .controls li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.3rem 0;
    font-size: 0.72rem;
    color: var(--ink-faint);
  }
  .action {
    font-family: var(--font-display);
    font-size: 0.62rem;
    letter-spacing: 0.1em;
    color: var(--ink-dim);
  }
  .keys {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }
  kbd {
    padding: 0.12rem 0.4rem;
    border: 1px solid var(--line);
    border-bottom-width: 2px;
    border-radius: 4px;
    background: var(--sunken);
    color: var(--ink-dim);
    font-family: var(--font-ui);
    font-size: 0.68rem;
  }
  .or {
    color: var(--line-strong);
  }
  footer {
    margin-top: 1.1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--line);
  }
</style>
