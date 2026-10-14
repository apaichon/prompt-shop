<script lang="ts">
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
</script>
<svelte:head><title>{page.params.path === 'backoffice' ? 'Catalog workspace' : 'Page not found'} · Prompt Shop</title></svelte:head>
<main id="main" class="placeholder-page">
  <div class="workspace-icon"><Icon name="leaf" size={36} /></div>
  {#if page.params.path === 'backoffice'}
    <p class="eyebrow">FOR STORE MAINTAINERS</p><h1>Catalog workspace</h1><p>Catalog management will be available here.<br />No catalog changes can be made from this page yet.</p>
  {:else}<h1>Page not found</h1><p>Let’s get you back to finding your item.</p>{/if}
  <a class="button" href="/">Back to item finder <Icon name="arrow" size={17} /></a>
</main>
