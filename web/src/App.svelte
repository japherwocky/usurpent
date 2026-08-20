<script>
  import Auth from './lib/Auth.svelte';
  import Game from './lib/Game.svelte';
</script>

<main>
  <header>
    <h1>USURPENT</h1>
    <Auth />
  </header>

  <Game />
</main>

<style>
  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #2a323c;
  }
  h1 {
    letter-spacing: 0.3em;
    font-weight: 700;
    margin: 0;
    font-size: 1.4rem;
  }
</style>
