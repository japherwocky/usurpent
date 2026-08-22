<script>
  import Lobby from './lib/Lobby.svelte';
  import Game from './lib/Game.svelte';

  let screen = 'lobby';
  let playerName = '';

  function handlePlay(event) {
    playerName = event.detail.name;
    screen = 'game';
  }
</script>

<main>
  {#if screen === 'lobby'}
    <Lobby on:play={handlePlay} />
  {:else}
    <Game name={playerName} />
  {/if}
</main>

<style>
  main {
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
</style>
