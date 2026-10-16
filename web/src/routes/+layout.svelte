<script lang="ts">
  import { page } from '$app/state';
  import ShopperGate from '#lib/components/ShopperGate.svelte';
  import Icon from '#lib/components/Icon.svelte';
  import '../app.css';
  let { children } = $props();
</script>
<a class="skip-link" href="#main">Skip to content</a>
{#if page.url.pathname !== '/'}<header class="site-header">
  <a class="brand" href="/" aria-label="Prompt Shop home"><span class="brand-mark">p<span>·</span></span><span>prompt<span class="brand-light">shop</span></span></a>
  <nav aria-label="Main navigation">
    <a class:current={page.url.pathname === '/'} href="/" aria-current={page.url.pathname === '/' ? 'page' : undefined}>Find an item</a>
    <a class:current={page.url.pathname.startsWith('/backoffice')} href="/backoffice" aria-current={page.url.pathname.startsWith('/backoffice') ? 'page' : undefined}>Backoffice <span aria-hidden="true">↗</span></a>
  </nav>
  <span class="store-badge"><Icon name="pin" size={15} /> Sample store</span>
</header>{/if}
<ShopperGate {children} adminOnly={page.url.pathname.startsWith('/backoffice')} />
{#if page.url.pathname !== '/'}<footer class="site-footer"><span>Less searching. More finding.</span><span>Directions from the entrance · Sample store map</span></footer>{/if}
