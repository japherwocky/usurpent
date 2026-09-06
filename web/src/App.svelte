<script>
  import Lobby from './lib/Lobby.svelte';
  import Game from './lib/Game.svelte';

  let screen = 'lobby';
  let playerName = '';
  // The mode picked in the lobby, as {id, name} from /api/modes. Passed to
  // the Game, which joins its world with ?mode= and labels the HUD with it.
  let mode = null;

  function handlePlay(event) {
    playerName = event.detail.name;
    mode = event.detail.mode;
    screen = 'game';
  }

  // Back to the lobby from the death card. The Game tears itself down
  // (onDestroy closes the socket), so leaving is just swapping the screen.
  function handleExit() {
    screen = 'lobby';
  }
</script>

<main>
  {#if screen === 'lobby'}
    <Lobby on:play={handlePlay} />
  {:else if mode}
    <Game name={playerName} mode={mode} on:exit={handleExit} />
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
