<script lang="ts">
 import {onDestroy} from 'svelte';
 import {Api,errorMessage} from '../api';
 import type {Product} from '../contracts';
 import ProductVisual from './ProductVisual.svelte';
 export let product:Product;
 export let choose:(product:Product)=>void;
 let products:Product[]=[];let message='';let loading=true;let request:AbortController|undefined;let epoch=0;let alive=true;
 const api=new Api();
 async function load(shelf:string){
  request?.abort();const abort=new AbortController();request=abort;const key=++epoch;products=[];message='';loading=true;
  try{const result=await api.products({shelf_id:shelf,page_size:24},abort.signal);if(alive&&key===epoch)products=result.products.filter(p=>p.shelf.id===shelf);}
  catch(error){if(alive&&key===epoch&&!abort.signal.aborted)message=errorMessage(error);}
  finally{if(alive&&key===epoch)loading=false;}
 }
 // Portal updates also invalidate object props during unrelated voice turns.
 // Only a changed shelf identity should cancel/reload this request.
 $: shelfID=product.shelf.id;
 $: void load(shelfID);
 onDestroy(()=>{alive=false;epoch++;request?.abort();});
</script>
<section class="shelf-display" aria-label="Products at the selected shelf" aria-busy={loading}>
 <div class="shelf-title"><h3>Your product on the shelf</h3><span>{product.aisle.label} · {product.shelf.label}</span></div>
 <div class="shelf-cabinet"><div class="shelf-products">{#each products as item(item.id)}<button class="shelf-facing" class:selected={item.id===product.id} aria-label={`Show route to ${item.name}`} aria-pressed={item.id===product.id} onclick={()=>choose(item)}><ProductVisual productID={item.id} category={item.category} compact/><span>{item.name}</span>{#if item.id===product.id}<strong>Your item</strong>{/if}</button>{/each}</div><div class="shelf-edge"><span>{product.shelf.label}</span></div></div>
 {#if loading}<p role="status">Loading shelf…</p>{:else if message}<p role="status">{message}</p><button class="text-button" onclick={()=>load(product.shelf.id)}>Retry shelf</button>{:else if !products.length}<p>No products currently published at this shelf.</p>{/if}
 <p class="catalog-disclosure">Sample shelf arrangement. Follow the stored aisle and shelf labels; exact placement may vary.</p>
</section>
