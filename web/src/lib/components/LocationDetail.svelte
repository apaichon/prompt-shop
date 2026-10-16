<script lang="ts">
  import type { Product, Route } from '../contracts';
  import ProductVisual from './ProductVisual.svelte';
  import Icon from './Icon.svelte';
  export let product: Product | null;
  export let route: Route | null;
</script>
<section class="location-detail" aria-labelledby="location-title">
  <div class="section-top"><h2 id="location-title">{product ? 'Your product, located.' : 'A little direction goes a long way.'}</h2><span class="small-overline">FIND YOUR WAY</span></div>
  {#if product}
    <div class="location-selected"><ProductVisual productID={product.id} category={product.category} compact />
      <div><span class="small-overline">YOUR NEXT STOP</span><h3>{product.name}</h3><div class="location-pills"><span><Icon name="pin" size={14} />{product.aisle.label}</span><span>{product.shelf.label}</span></div><p>{route ? 'Start at the entrance and follow the highlighted store walkway.' : 'Shelf location is known. A walking route is not available yet.'}</p></div>
    </div>
    {#if route}<div class="directions"><h3><Icon name="route" size={17} />Follow these directions</h3><ol>{#each route.steps as step}<li>{step}</li>{/each}</ol></div>{/if}
  {:else}
    <div class="how-it-works">{#each [{n:'01',title:'Ask or search',text:'An item, an ingredient, a dinner idea.'},{n:'02',title:'Find your match',text:'Choose the product you have in mind.'},{n:'03',title:'Follow the blue',text:'We’ll guide you from the entrance.'}] as step}<div><span>{step.n}</span><h3>{step.title}</h3><p>{step.text}</p></div>{/each}</div>
  {/if}
</section>
