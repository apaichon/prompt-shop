<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { Portal } from '#lib/portal.ts';
  import Icon from '#lib/components/Icon.svelte';
  import VoicePanel from '#lib/components/VoicePanel.svelte';
  import StoreMap from '#lib/components/StoreMap.svelte';
  const portal = new Portal();
  const voice = portal.voice;
  let query = $state('');
  let dialog: HTMLDialogElement;
  let launcher: HTMLButtonElement;
  let focusVersion = 0;
  $effect(() => {
    if ($portal.focusVersion !== focusVersion && $portal.focus) {
      focusVersion = $portal.focusVersion;
      const target = $portal.focus;
      void tick().then(() => { if (!dialog?.open) document.getElementById(target)?.focus(); });
    }
  });
  function closeDrawer() { portal.stopVoice(); dialog?.close(); launcher?.focus(); }
  // Adapted from Monti's modal-only first/last control trap (see NOTICE.md).
  function trapDrawer(event: KeyboardEvent) {
    if (event.key !== 'Tab' || !dialog.open) return;
    const controls = [...dialog.querySelectorAll<HTMLButtonElement>('button:not([disabled])')];
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  onMount(() => {
    void portal.loadMap();
    const screen = matchMedia('(min-width: 900px)');
    const resize = () => { if (screen.matches && dialog.open) closeDrawer(); };
    const hidden = () => { if (document.hidden) portal.stopVoice(); };
    const leave = () => portal.stopVoice();
    screen.addEventListener('change', resize); document.addEventListener('visibilitychange', hidden); window.addEventListener('pagehide', leave);
    return () => { screen.removeEventListener('change', resize); document.removeEventListener('visibilitychange', hidden); window.removeEventListener('pagehide', leave); };
  });
  onDestroy(() => portal.destroy());
  function search() { void portal.search(query); }
</script>
<svelte:head><title>Find your aisle · Prompt Shop</title><meta name="description" content="Find an item and its shelf in the sample store. Ask by voice or type an item name, then follow directions from the entrance." /></svelte:head>
<main id="main" class="customer-page">
  <section class="hero">
    <p class="eyebrow"><span class="tiny-line"></span> A LITTLE HELP AROUND THE STORE</p>
    <h1>Your next find,<br class="mobile-break" /> <em>one ask away.</em></h1>
    <p>From “where’s the milk?” to the right shelf. Let’s find your way.</p>
  </section>
  <div class="customer-grid">
    <aside class="desktop-voice"><VoicePanel {portal} /></aside>
    <div class="finder-column">
      <section class="search-panel" aria-labelledby="search-title">
        <div class="section-top"><h2 id="search-title">What are you looking for?</h2><span class="subtle-label">English</span></div>
        <form onsubmit={(event) => { event.preventDefault(); search(); }}>
          <label class="sr-only" for="item-query">Item name</label>
          <div class="search-field"><Icon name="search" size={22} /><input id="item-query" name="query" bind:value={query} maxlength="200" placeholder="Try milk, rice, or toothpaste" autocomplete="off" /><button class="button" type="submit">Find item <Icon name="arrow" size={17} /></button></div>
        </form>
        <div class="suggestions"><span>Need a starting point?</span>{#each ['Milk', 'Rice', 'Toothpaste'] as item}<button onclick={() => { query = item; search(); }}>{item}<span aria-hidden="true">↗</span></button>{/each}</div>
      </section>
      <button bind:this={launcher} class="mobile-launch button" onclick={() => dialog.showModal()}><Icon name="mic" /> {$voice.active ? 'Open voice assistant' : 'Rather ask? Open voice assistant'} <Icon name="arrow" size={17} /></button>
      {#if $portal.loading || $portal.searched || $portal.message}
        <section class="results-section" aria-labelledby="results-heading" aria-busy={$portal.loading}>
          <div class="section-top"><h2 id="results-heading" tabindex="-1">{$portal.loading && !$portal.candidates.length ? 'Looking for your item…' : $portal.candidates.length ? `${$portal.candidates.length} ${$portal.candidates.length === 1 ? 'match' : 'matches'} found` : 'Search results'}</h2>{#if $portal.candidates.length}<span class="subtle-label">Store catalog</span>{/if}</div>
          <p class="result-message" role="status">{$portal.message}</p>
          <div class="product-grid">
            {#each $portal.candidates as product (product.id)}
              <article class="product-card" class:chosen={$portal.location?.id === product.id}>
                <div class="product-category"><Icon name="leaf" size={17} />{product.category}{#if $portal.location?.id === product.id}<span class="selected-badge"><Icon name="check" size={13} />Selected</span>{/if}</div>
                <h3>{product.name}</h3><p class="product-location"><Icon name="pin" size={16} />{product.aisle.label}<span aria-hidden="true"> / </span>{product.shelf.label}</p>
                <button onclick={() => portal.choose(product)} class="route-button" aria-label={`Show route to ${product.name}`}>{product.route_available ? 'Show route' : 'View shelf location'}<Icon name="arrow" size={17} /></button>
              </article>
            {/each}
          </div>
        </section>
      {/if}
      <section class="map-panel" aria-labelledby="route-heading">
        <div class="map-heading"><div><p class="eyebrow">YOUR WAY THERE</p><h2 id="route-heading" tabindex="-1">{$portal.location ? $portal.location.name : 'Get to know your store'}</h2></div><span class="map-symbol"><Icon name="map" size={23} /></span></div>
        <div class="map-meta"><span><Icon name="pin" size={14} /> From entrance</span><span>Sample map · Not live location</span></div>
        {#if $portal.location}<div class="destination-strip"><strong>{$portal.location.aisle.label}</strong><span>{$portal.location.shelf.label}</span>{#if $portal.route}<span class="verified-location"><Icon name="check" size={14} />Route found</span>{/if}</div>{/if}
        {#if $portal.map}<StoreMap map={$portal.map} route={$portal.route} />
        {:else}<div class="map-placeholder"><Icon name="map" size={40} /><p>{$portal.mapLoading ? 'Loading the store map…' : 'The map is unavailable right now.'}</p></div>{/if}
        {#if $portal.mapError}<div class="inline-error" role="status"><p>{$portal.mapError}</p><button class="text-button" onclick={() => portal.loadMap()}>Retry map</button></div>{/if}
        {#if $portal.routeMessage}<p class="route-message" role="status">{$portal.routeMessage}</p>{/if}
        {#if $portal.route}
          <div class="directions"><h3>Follow these directions</h3><ol>{#each $portal.route.steps as step}<li>{step}</li>{/each}</ol></div>
        {:else if !$portal.location}<p class="map-hint"><span class="hint-dot"></span> Find an item to see its shelf and walking route.</p>{/if}
        <div class="map-legend"><span><i class="legend-aisle"></i>Aisles</span><span><i class="legend-path"></i>Walking route</span><span><i class="legend-destination"></i>Destination</span></div>
      </section>
      <p class="finder-footnote">Can’t find what you need? A store colleague can help.</p>
    </div>
  </div>
</main>
<dialog bind:this={dialog} class="voice-dialog" onkeydown={trapDrawer} aria-label="Voice assistant" oncancel={(event) => { event.preventDefault(); closeDrawer(); }}>
  <button class="drawer-close" aria-label="Close voice assistant" onclick={closeDrawer}><Icon name="close" /></button>
  <VoicePanel {portal} prefix="mobile" />
</dialog>
