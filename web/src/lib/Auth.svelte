<script>
  import { createEventDispatcher } from 'svelte';
  import { slide } from 'svelte/transition';
  import { apiGet, apiPost } from './api.js';

  const dispatch = createEventDispatcher();

  // 'login' or 'register'
  let mode = 'login';
  let username = '';
  let password = '';
  let email = '';
  let error = '';
  let busy = false;
  // null while loading; then { guest: true } or { guest: false, username, ... }
  let session = null;
  // The form is collapsed by default. Signing in is optional -- guests play
  // without an account -- so it stays a footer strip until asked for, instead
  // of a second card competing with PLAY for the eye.
  let open = false;

  async function refresh() {
    try {
      session = await apiGet('/api/me');
    } catch (e) {
      session = { guest: true };
    }
    dispatch('session', session);
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
      open = false;
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

  function reveal(next) {
    // Clicking the mode you are already showing closes the form again.
    if (open && mode === next) {
      open = false;
      return;
    }
    mode = next;
    open = true;
    error = '';
  }

  refresh();
</script>

<div class="auth">
  {#if session && !session.guest}
    <div class="strip">
      <span class="who">
        <span class="dot"></span>
        {session.username}
        {#if session.high_score}<span class="best">best {session.high_score}</span>{/if}
      </span>
      <button class="link" on:click={logout} disabled={busy}>Log out</button>
    </div>
  {:else if session}
    <div class="strip">
      <span class="who muted">Playing as guest</span>
      <span class="actions">
        <button class="link" class:on={open && mode === 'login'} on:click={() => reveal('login')}>
          Sign in
        </button>
        <span class="sep">/</span>
        <button class="link" class:on={open && mode === 'register'} on:click={() => reveal('register')}>
          Create account
        </button>
      </span>
    </div>

    {#if open}
      <form on:submit|preventDefault={submit} class="form" transition:slide={{ duration: 160 }}>
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
            <span>Email <em>(optional)</em></span>
            <input type="email" bind:value={email} autocomplete="email" />
          </label>
        {/if}

        {#if error}<p class="error">{error}</p>{/if}

        <button type="submit" class="submit" disabled={busy || !username || !password}>
          {busy ? '…' : mode === 'register' ? 'Create account' : 'Sign in'}
        </button>
      </form>
    {/if}
  {:else}
    <div class="strip"><span class="who muted">Checking session…</span></div>
  {/if}
</div>

<style>
  .auth {
    font-size: 0.78rem;
  }
  .strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .who {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--ink);
  }
  .who.muted {
    color: var(--ink-faint);
  }
  /* A lit dot beats the words "Signed in as" for the same information. */
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--good);
    box-shadow: 0 0 6px var(--good);
  }
  .best {
    font-family: var(--font-display);
    font-size: 0.62rem;
    color: var(--ink-faint);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .sep {
    color: var(--line-strong);
  }
  .link {
    padding: 0;
    border: none;
    background: none;
    color: var(--accent);
    font-size: inherit;
    cursor: pointer;
  }
  .link:hover:not(:disabled),
  .link.on {
    color: var(--accent-hi);
  }
  .link:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    margin-top: 0.85rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    color: var(--ink-dim);
    font-size: 0.72rem;
  }
  label em {
    font-style: normal;
    color: var(--ink-faint);
  }
  input {
    padding: 0.45rem 0.55rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--sunken);
    color: var(--ink);
    font-size: 0.82rem;
  }
  input:focus {
    border-color: var(--accent-deep);
    outline: none;
  }
  .submit {
    margin-top: 0.15rem;
    padding: 0.5rem;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-sm);
    background: var(--surface-2);
    color: var(--ink);
    font-family: var(--font-display);
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    cursor: pointer;
  }
  .submit:hover:not(:disabled) {
    border-color: var(--accent-deep);
    color: var(--accent-hi);
  }
  .submit:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .error {
    margin: 0;
    color: var(--bad);
    font-size: 0.72rem;
  }
</style>
