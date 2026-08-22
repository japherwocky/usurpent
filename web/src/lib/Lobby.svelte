<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import Auth from './Auth.svelte';
  import { apiGet } from './api.js';

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

  let name = randomName();
  let touched = false;

  onMount(() => {
    // Remember the last name a returning player used.
    const saved = localStorage.getItem('usurpent.name');
    if (saved) {
      name = saved;
      touched = true;
    }
  });

  // When a player logs in, default the name to their account (unless they've
  // already typed their own).
  function onSession(e) {
    const s = e.detail;
    if (s && !s.guest && s.username && !touched) name = s.username;
  }

  function shuffle() {
    name = randomName();
    touched = true;
  }

  function play() {
    let n = (name || '').trim();
    if (!NAME_RE.test(n)) n = randomName();
    localStorage.setItem('usurpent.name', n);
    dispatch('play', { name: n });
  }
</script>

<section class="lobby">
  <div class="card">
    <h1>USURPENT</h1>
    <p class="pitch">A real-time multiplayer snake. Eat, grow, survive.</p>

    <ul class="howto">
      <li>Move the mouse to steer</li>
      <li>Click &amp; hold (or hold a key) to boost</li>
      <li>Right-click for debug / leaderboard</li>
    </ul>

    <label class="name">
      <span>Choose a name</span>
      <div class="name-row">
        <input
          bind:value={name}
          on:input={() => (touched = true)}
          maxlength="32"
          autocomplete="off"
          spellcheck="false"
          placeholder="your serpent name"
        />
        <button type="button" class="shuffle" on:click={shuffle} title="Pick a random name">
          random
        </button>
      </div>
      <span class="hint">3–32 characters: letters, numbers, _ or -</span>
    </label>

    <button class="play" on:click={play}>PLAY</button>

    <div class="auth-wrap">
      <Auth on:session={onSession} />
    </div>
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
  }
  .card {
    width: 22rem;
    max-width: 100%;
    padding: 1.5rem;
    background: #11161d;
    border: 1px solid #2a323c;
    border-radius: 0.5rem;
    text-align: center;
  }
  h1 {
    margin: 0;
    letter-spacing: 0.3em;
    font-weight: 700;
    font-size: 1.8rem;
  }
  .pitch {
    margin: 0.5rem 0 1rem;
    color: #9fb0c0;
    font-size: 0.85rem;
  }
  .howto {
    list-style: none;
    margin: 0 0 1.25rem;
    padding: 0.75rem;
    text-align: left;
    font-size: 0.8rem;
    color: #c9d6e2;
    background: #0b0f14;
    border: 1px solid #1c2530;
    border-radius: 0.4rem;
  }
  .howto li {
    margin: 0.2rem 0;
  }
  .name {
    display: flex;
    flex-direction: column;
    text-align: left;
    font-size: 0.8rem;
    color: #9fb0c0;
    gap: 0.3rem;
  }
  .name-row {
    display: flex;
    gap: 0.4rem;
  }
  input {
    flex: 1;
    min-width: 0;
    padding: 0.45rem 0.5rem;
    border-radius: 0.3rem;
    border: 1px solid #2a323c;
    background: #0b0f14;
    color: #e6edf3;
  }
  .shuffle {
    padding: 0.45rem 0.6rem;
    border: 1px solid #2a323c;
    border-radius: 0.3rem;
    background: #1a2230;
    color: #9fb0c0;
    cursor: pointer;
  }
  .shuffle:hover {
    color: #e6edf3;
  }
  .hint {
    font-size: 0.7rem;
    color: #6b7c8c;
  }
  .play {
    margin-top: 1rem;
    width: 100%;
    padding: 0.6rem;
    border: none;
    border-radius: 0.3rem;
    background: #2f81f7;
    color: white;
    font-weight: 700;
    letter-spacing: 0.15em;
    cursor: pointer;
  }
  .play:hover {
    background: #3b8cff;
  }
  .auth-wrap {
    margin-top: 1.25rem;
    padding-top: 1.25rem;
    border-top: 1px solid #2a323c;
    text-align: left;
  }
</style>
