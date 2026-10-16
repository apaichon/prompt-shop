<script lang="ts">
 import {onMount,onDestroy} from 'svelte';
 import {Api,errorMessage} from '../api';
 import type {Product,ProductList} from '../contracts';
 import ProductCard from './ProductCard.svelte';
 export let choose:(product:Product)=>void;
 export let selectedID:string|undefined=undefined;
 const api=new Api();
 let catalog:ProductList|null=null;
 let category='Dairy';let page=1;let loading=true;let message='';let request:AbortController|undefined;
 let epoch=0;let alive=true;
 async function load(nextCategory=category,nextPage=1){
  category=nextCategory;page=nextPage;request?.abort();const abort=new AbortController();request=abort;
  const key=++epoch;loading=true;message='';
  try{const result=await api.products({category,page,page_size:12},abort.signal);if(alive&&key===epoch)catalog=result;}
  catch(error){if(alive&&key===epoch&&!abort.signal.aborted)message=errorMessage(error);}
  finally{if(alive&&key===epoch)loading=false;}
 }
 onMount(()=>{void load();});
 onDestroy(()=>{alive=false;epoch++;request?.abort();});
</script>
<section class="catalog-browser" aria-labelledby="catalog-heading" aria-busy={loading}>
 <div class="section-top"><div><span class="small-overline">A STORE FULL OF POSSIBILITIES</span><h2 id="catalog-heading">Explore your store</h2></div><span class="catalog-total">{catalog ? catalog.categories.reduce((sum,c)=>sum+c.count,0)+' products' : 'Store catalog'}</span></div>
 <p class="catalog-description">Pick your next find. Monti will show you the way.</p>
 {#if catalog}<div class="category-tabs" aria-label="Browse product category"><button aria-pressed={category===''} onclick={()=>load('')}>All products</button>{#each catalog.categories as c}<button aria-label={`${c.name} (${c.count} products)`} aria-pressed={category===c.name} onclick={()=>load(c.name)}>{c.name}<span>{c.count}</span></button>{/each}</div>{/if}
 {#if message}<p role="status">{message}</p><button class="text-button" onclick={()=>load(category,page)}>Retry catalog</button>
 {:else if catalog}<div class="product-grid browse-grid" class:catalog-loading={loading}>{#each catalog.products as product(product.id)}<ProductCard {product} selected={selectedID===product.id} {choose}/>{/each}</div>{#if !catalog.products.length}<p>No products in this category.</p>{/if}
 <nav class="catalog-pagination" aria-label="Catalog pages"><button disabled={page===1||loading} onclick={()=>load(category,page-1)}>← Previous</button><span>Page {page} of {Math.max(1,Math.ceil(catalog.total/catalog.page_size))}</span><button disabled={page*catalog.page_size>=catalog.total||loading} onclick={()=>load(category,page+1)}>Next →</button></nav>
 {:else}<p role="status">Loading products…</p>{/if}
 <p class="catalog-disclosure">Sample product images. Packaging may vary.</p>
</section>
