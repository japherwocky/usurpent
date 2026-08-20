<script>
  import { apiGet, apiPost } from './api.js';

  // 'login' or 'register'
  let mode = 'login';
  let username = '';
  let password = '';
  let email = '';
  let error = '';
  let busy = false;
  // null while loading; then { guest: true } or { guest: false, username, ... }
  let session = null;

  async function refresh() {
    try {
      session = await apiGet('/api/me');
    } catch (e) {
      session = { guest: true };
    }
  }

  async function submit() {
    error = '';
    busy = true;
    try {
      const path = mode === 'register' ? '/api/register' : '/api/login';
      const payload =
        mode === 'register'
          ? { username, password, email: email || undefined }
          : { username, password };
      await apiPost(path, payload);
      username = '';
      password = '';
      email = '';
      await refresh();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  async function logout() {
    error = '';
    busy = true;
    try {
      await apiPost('/api/logout', {});
      await refresh();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  function switchMode() {
    mode = mode === 'register' ? 'login' : 'register';
    error = '';
  }

  refresh();
</script>

<section class="auth">
  {#if session && !session.guest}
    <div class="session">
      <span class="user">Signed in as <strong>{session.username}</strong></span>
      <button on:click={logout} disabled={busy}>Log out</button>
    </div>
  {:else if session}
    <form on:submit|preventDefault={submit} class="card">
      <h2>{mode === 'register' ? 'Create account' : 'Sign in'}</h2>

      <label>
        <span>Username</span>
        <input
          bind:value={username}
          autocomplete="username"
          required
          minlength="3"
          maxlength="32"
          pattern="[A-Za-z0-9_-]+"
        />
      </label>

      <label>
        <span>Password</span>
        <input
          type="password"
          bind:value={password}
          autocomplete={mode === 'register' ? 'new-password' : 'current-password'}
          required
          minlength="8"
        />
      </label>

      {#if mode === 'register'}
        <label>
          <span>Email (optional)</span>
          <input type="email" bind:value={email} autocomplete="email" />
        </label>
      {/if}

      {#if error}<p class="error">{error}</p>{/if}

      <button type="submit" disabled={busy || !username || !password}>
        {busy ? '…' : mode === 'register' ? 'Register' : 'Log in'}
      </button>

      <p class="toggle">
        {mode === 'register' ? 'Already have an account?' : 'New here?'}
        <button type="button" on:click={switchMode} disabled={busy}>
          {mode === 'register' ? 'Sign in' : 'Create one'}
        </button>
      </p>
    </form>
  {:else}
    <p class="loading">Loading…</p>
  {/if}
</section>

<style>
  .auth {
    display: flex;
    justify-content: flex-end;
  }
  .card {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    width: 16rem;
    padding: 1rem;
    background: #11161d;
    border: 1px solid #2a323c;
    border-radius: 0.5rem;
  }
  h2 {
    margin: 0 0 0.25rem;
    font-size: 1.1rem;
  }
  label {
    display: flex;
    flex-direction: column;
    font-size: 0.8rem;
    color: #9fb0c0;
  }
  input {
    margin-top: 0.2rem;
    padding: 0.4rem 0.5rem;
    border-radius: 0.3rem;
    border: 1px solid #2a323c;
    background: #0b0f14;
    color: #e6edf3;
  }
  button {
    margin-top: 0.4rem;
    padding: 0.45rem 0.6rem;
    border: none;
    border-radius: 0.3rem;
    background: #2f81f7;
    color: white;
    cursor: pointer;
    font-weight: 600;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .error {
    color: #ff7b72;
    font-size: 0.8rem;
    margin: 0.2rem 0 0;
  }
  .toggle {
    font-size: 0.8rem;
    color: #9fb0c0;
    margin: 0.4rem 0 0;
  }
  .toggle button {
    background: none;
    color: #2f81f7;
    padding: 0;
    margin: 0 0 0 0.3rem;
    font-weight: 600;
  }
  .session {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.75rem;
    background: #11161d;
    border: 1px solid #2a323c;
    border-radius: 0.5rem;
  }
  .session .user {
    font-size: 0.85rem;
    color: #e6edf3;
  }
  .session button {
    margin: 0;
    padding: 0.35rem 0.6rem;
    background: #2a323c;
  }
  .loading {
    color: #9fb0c0;
    font-size: 0.85rem;
  }
</style>
