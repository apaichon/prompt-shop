<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { Portal } from '#lib/portal.ts';
  import Icon from '#lib/components/Icon.svelte';
  import VoicePanel from '#lib/components/VoicePanel.svelte';
  import AssistantAvatar from '#lib/components/AssistantAvatar.svelte';
  import ProductCard from '#lib/components/ProductCard.svelte';
  import CatalogBrowser from '#lib/components/CatalogBrowser.svelte';
  import ShelfDisplay from '#lib/components/ShelfDisplay.svelte';
  import LocationDetail from '#lib/components/LocationDetail.svelte';
  import StoreMap from '#lib/components/StoreMap.svelte';
  import { shopBrand } from '#lib/ui-config.ts';
  import '../monti.css';
  const portal = new Portal();
  const voice = portal.voice;
  let query = $state('');
  let dialog: HTMLDialogElement;
  let launcher: HTMLButtonElement;
  let focusVersion = 0;
  let keyboardInset = $state(0);
  let displayedProducts = $derived($portal.location ? [...$portal.candidates].sort((a,b) => Number(b.id === $portal.location?.id) - Number(a.id === $portal.location?.id)) : $portal.candidates);
  let selectedID = $derived($portal.location?.id);
  let showAllMatches = $state(false);
  $effect(() => { selectedID; showAllMatches = false; });
  const statusLabels = { idle:'Ready to help', connecting:'Connecting', listening:'Listening', thinking:'Thinking', speaking:'Speaking', interrupted:'Listening', error:'Voice paused' };
  $effect(() => {
    if ($portal.focusVersion !== focusVersion && $portal.focus) {
      focusVersion = $portal.focusVersion;
      const target = $portal.focus;
      void tick().then(() => { if (!dialog?.open) document.getElementById(target)?.focus(); });
    }
  });
  function closeDrawer() { portal.stopVoice(); dialog?.close(); launcher?.focus(); }
  function minimizeDrawer() { dialog?.close(); launcher?.focus(); }
  function trapDrawer(event: KeyboardEvent) {
    if (event.key !== 'Tab' || !dialog.open) return;
    const controls = [...dialog.querySelectorAll<HTMLButtonElement>('button:not([disabled])')];
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  onMount(() => {
    void portal.loadMap();
    const screen = matchMedia('(min-width: 1200px)');
    const resize = () => { if (screen.matches && dialog.open) { dialog.close(); document.querySelector<HTMLButtonElement>('.desktop-voice .voice-primary')?.focus(); } };
    const hidden = () => { if (document.hidden) portal.stopVoice(); };
    const leave = () => portal.stopVoice();
    const viewport = window.visualViewport;
    const keyboard = () => {
      const editing = ['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName ?? '');
      keyboardInset = viewport && viewport.scale === 1 && editing ? Math.max(0, innerHeight - viewport.height - viewport.offsetTop) : 0;
    };
    viewport?.addEventListener('resize', keyboard); viewport?.addEventListener('scroll', keyboard);
    document.addEventListener('focusin', keyboard); document.addEventListener('focusout', keyboard);
    screen.addEventListener('change', resize); document.addEventListener('visibilitychange', hidden); window.addEventListener('pagehide', leave);
    return () => { screen.removeEventListener('change', resize); document.removeEventListener('visibilitychange', hidden); window.removeEventListener('pagehide', leave); viewport?.removeEventListener('resize', keyboard); viewport?.removeEventListener('scroll', keyboard); document.removeEventListener('focusin', keyboard); document.removeEventListener('focusout', keyboard); };
  });
  onDestroy(() => portal.destroy());
  function search() { void portal.search(query); }
</script>
<svelte:head><title>Find it. Say it. Shop it. · Monti Store</title><meta name="description" content="Meet Monti, your friendly store companion. Talk, plan a meal, or find an item and its shelf with verified directions from the entrance." /></svelte:head>
<div class="shop-portal">
  <header class="monti-header"><div class="monti-header-inner">
    <a class="monti-brand" href="/" aria-label={`${shopBrand.name} home`}><AssistantAvatar size={50} /><span>{shopBrand.name}</span></a>
    <span class="monti-store-label"><Icon name="pin" size={15} />{$portal.map?.name ?? 'Demo store'}</span>
    <form class="header-search" onsubmit={(event) => { event.preventDefault(); search(); }}><Icon name="search" size={21} /><label class="sr-only" for="item-query">Item name</label><input id="item-query" name="query" bind:value={query} maxlength="200" placeholder="Ask or search for a product" autocomplete="off" /><button class="search-submit" type="submit" aria-label="Find item"><Icon name="arrow" size={19} /></button><button class="search-mic" type="button" aria-label="Open voice assistant from search" onclick={() => { if (matchMedia('(min-width:1200px)').matches) { void portal.startVoice(); } else { dialog.showModal(); } }}><Icon name="mic" size={21} /></button></form>
    <a class="backoffice-link" href="/backoffice" aria-label="Backoffice"><Icon name="grid" size={20} /><span>Backoffice</span></a>
  </div></header>
  <main id="main" class="monti-main"><div class="shop-workspace" class:has-results={$portal.searched || !!$portal.location}>
    <div class="finder-column">
      <section class="shop-introduction"><div><p class="small-overline">LESS SEARCHING. MORE FINDING.</p><h1>Find it. Say it. <span>Shop it.</span></h1><p>Your store, a little easier. Just ask Monti.</p></div><span class="intro-mark" aria-hidden="true"><Icon name="sparkle" size={31} /></span></section>
      <section class="search-panel" aria-label="Suggested searches"><div class="suggestions"><span>Try an item</span>{#each ['Milk','Rice','Toothpaste'] as item}<button onclick={() => {query=item;search();}}><Icon name="search" size={13} />{item}</button>{/each}</div><span class="catalog-note"><Icon name="check" size={13} />Store catalog</span></section>
      {#if $portal.loading || $portal.searched || $portal.message}
        <section class="results-section" aria-labelledby="results-heading" aria-busy={$portal.loading}>
          <div class="section-top"><h2 id="results-heading" tabindex="-1">{$portal.loading && !$portal.candidates.length ? 'Looking for your item…' : $portal.candidates.length ? `${$portal.candidates.length} ${$portal.candidates.length === 1 ? 'match' : 'matches'} found` : 'Search results'}</h2><span class="result-source">{$portal.source === 'voice' ? 'Found with Monti' : $portal.query}</span></div><p class="result-message" role="status">{$portal.message}</p>
          <div class="product-grid" class:has-selection={!!$portal.location} class:show-all={showAllMatches}>{#each displayedProducts as product (product.id)}<ProductCard {product} selected={$portal.location?.id === product.id} choose={(product) => {void portal.choose(product);}} />{/each}</div>
          {#if $portal.location && $portal.candidates.length > 1}<button class="other-matches" onclick={() => showAllMatches = !showAllMatches}>{showAllMatches ? 'Show selected item' : `Show all ${$portal.candidates.length} matches`}<Icon name="chevron" size={14} /></button>{/if}
          {#if $portal.loading && !$portal.candidates.length}<div class="loading-cards" aria-hidden="true">{#each [1,2,3] as n}<div class="skeleton-card"><span></span><i></i><i></i></div>{/each}</div>{/if}
        </section>
      {/if}
      {#if $portal.location}<ShelfDisplay product={$portal.location} choose={(product)=>{void portal.chooseBrowse(product);}} />{/if}
      <LocationDetail product={$portal.location} route={$portal.route} />
      <CatalogBrowser selectedID={$portal.location?.id} choose={(product)=>{void portal.chooseBrowse(product);}} />
      <p class="finder-footnote"><Icon name="check" size={13} />Locations from the store catalog. Directions from the entrance.</p>
    </div>
    <aside class="assistant-rail desktop-voice" aria-label="Monti assistant and store map"><VoicePanel {portal}>
      {#snippet mapContent()}
        <section class="map-panel" aria-labelledby="route-heading"><div class="map-heading"><div><span class="small-overline">YOUR WAY THERE</span><h2 id="route-heading" tabindex="-1">{$portal.location ? $portal.location.name : 'Get to know your store'}</h2></div><Icon name="map" size={20} /></div>
          <div class="map-meta"><span><Icon name="pin" size={12} />From entrance</span><span>Sample map · Not live location</span></div>
          {#if $portal.location}<div class="destination-strip"><strong>{$portal.location.aisle.label}</strong><span>{$portal.location.shelf.label}</span>{#if $portal.route}<span class="verified-location"><Icon name="check" size={12} />Route found</span>{/if}</div>{/if}
          {#if $portal.map}<StoreMap map={$portal.map} route={$portal.route} />{:else}<div class="map-placeholder"><Icon name="map" size={32} /><p>{$portal.mapLoading ? 'Loading the store map…' : 'The map is unavailable right now.'}</p></div>{/if}
          {#if $portal.mapError}<div class="inline-error" role="status"><p>{$portal.mapError}</p><button class="text-button" onclick={() => portal.loadMap()}>Retry map</button></div>{/if}
          {#if $portal.routeMessage}<p class="route-message" role="status">{$portal.routeMessage}</p>{/if}
          <div class="map-map-footer"><span><i></i>{$portal.route ? 'Your walking route' : 'Find an item to see its route'}</span><Icon name="route" size={15} /></div>
        </section>
      {/snippet}
    </VoicePanel></aside>
  </div><footer class="monti-footer"><span><strong>{shopBrand.name}</strong> A little help around the store.</span><span>Powered by a friendly conversation.</span></footer></main>
  <div class="mobile-voice-dock" role="region" aria-label="Voice controls" style:bottom={`${keyboardInset}px`}>{#if $voice.phase === 'error'}<p class="dock-error" role="alert">{$voice.message}</p>{/if}<button bind:this={launcher} class="dock-companion" aria-label="Open voice assistant" onclick={() => dialog.showModal()}><AssistantAvatar phase={$voice.phase} level={$voice.outputLevel} size={46} /><span><strong>{shopBrand.assistant}</strong><small role="status" aria-live="polite">{$voice.active ? `${statusLabels[$voice.phase]} · ${$voice.micMuted ? 'Mic muted' : $voice.micHeld ? 'Mic paused' : 'Mic on'} · ${Math.floor($voice.remaining/60)}:${String($voice.remaining%60).padStart(2, '0')} left` : 'Ready to help'}<Icon name="chevron" size={11} /></small></span></button>{#if $voice.speakerMode && $voice.active}<button class="dock-interrupt interrupt-reply" disabled={!$voice.micHeld} onclick={() => voice.interrupt()}>Interrupt</button>{/if}<div class="dock-actions"><button class="round-control" disabled={!$voice.active} aria-label={$voice.micMuted ? 'Unmute mic' : 'Mute mic'} aria-pressed={$voice.micMuted} onclick={() => voice.muteMicrophone()}><Icon name="mic" size={17} /></button><button class="dock-primary" aria-label={$voice.active ? 'End voice' : $voice.phase === 'error' ? 'Restart voice' : 'Start voice'} onclick={() => $voice.active ? portal.stopVoice() : portal.startVoice()}><Icon name={$voice.active ? 'stop' : 'mic'} size={24} /></button><button class="round-control" disabled={!$voice.active} aria-label={$voice.soundMuted ? 'Unmute sound' : 'Mute sound'} aria-pressed={$voice.soundMuted} onclick={() => voice.muteSpeaker()}><Icon name="sound" size={18} /></button></div></div>
  <dialog bind:this={dialog} class="voice-dialog monti-dialog" onkeydown={trapDrawer} aria-label="Voice assistant" oncancel={(event) => {event.preventDefault();closeDrawer();}}><div class="dialog-actions"><button class="minimize-assistant" onclick={minimizeDrawer}>Minimize <Icon name="chevron" size={15} /></button><button class="drawer-close" aria-label="Close voice assistant" onclick={closeDrawer}><Icon name="close" /></button></div><VoicePanel {portal} prefix="mobile" /></dialog>
</div>
