<script>
  import Auth from './lib/Auth.svelte';
</script>

<main>
  <header>
    <h1>USURPENT</h1>
    <Auth />
  </header>

  <section class="stage">
    <p>The game renderer lands in #182. You can register and sign in above.</p>
  </section>
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
  .stage {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9fb0c0;
  }
</style>
