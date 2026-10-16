<script lang="ts">
  import type { Product } from '../contracts';
  import ProductVisual from './ProductVisual.svelte';
  import Icon from './Icon.svelte';
  export let product: Product;
  export let selected = false;
  export let choose: (product: Product) => void;
</script>
<article class="product-card" class:chosen={selected}>
  <div class="product-art-wrap"><ProductVisual productID={product.id} category={product.category} />
    {#if selected}<span class="selected-badge"><Icon name="check" size={12} />Selected</span>{/if}
  </div>
  <div class="product-card-body"><span class="product-category">{product.category}</span><h3>{product.name}</h3>
    <p class="product-location"><Icon name="pin" size={15} />{product.aisle.label}<span aria-hidden="true">·</span>{product.shelf.label}</p>
    <button class="route-button" aria-label={`Show route to ${product.name}`} onclick={() => choose(product)}><Icon name="pin" size={16} />{product.route_available ? 'Locate item' : 'View shelf location'}<Icon name="arrow" size={15} /></button>
  </div>
</article>
