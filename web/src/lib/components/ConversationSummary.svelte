<script lang="ts">
  import type { Portal } from '../portal';
  import type { Product } from '../contracts';
  import ProductVisual from './ProductVisual.svelte';
  export let portal: Portal;
  const voice=portal.voice;
  $: entries=$portal.summary.entries;
  $: confirmed=[...new Map(entries.filter(e=>e.status==='confirmed').flatMap(e=>e.products).map(p=>[p.id,p])).values()];
  $: groups=Object.values(confirmed.reduce((all:Record<string,{aisle:string;products:Product[]}>,p)=>{
    const group=all[p.aisle.id]??(all[p.aisle.id]={aisle:p.aisle.label,products:[]});group.products.push(p);return all;
  },{})).sort((a,b)=>a.aisle.localeCompare(b.aisle,undefined,{numeric:true}));
  $: unresolved=entries.filter(e=>e.status!=='confirmed');
</script>
{#if entries.length || $portal.summaryVisible}
<section class="conversation-summary" aria-labelledby="summary-heading">
  <div class="summary-top"><div><span class="summary-overline">YOUR CONVERSATION</span><h2 id="summary-heading" tabindex="-1">Items and locations</h2></div><button onclick={()=>$portal.summaryVisible?portal.hideSummary():portal.showSummary()} aria-expanded={$portal.summaryVisible}>{$portal.summaryVisible?'Hide summary':'Show summary'}</button></div>
  {#if $voice.summaryOffer}<div class="summary-offer" role="status"><p>Would you like a summary of the items and their locations?</p><div><button onclick={()=>portal.acceptSummary()}>Yes, summarize</button><button onclick={()=>voice.dismissSummaryOffer()}>No thanks</button></div></div>{/if}
  {#if $portal.summaryVisible}
    <p class="summary-note">{confirmed.length} confirmed {confirmed.length===1?'item':'items'} · {unresolved.length} unresolved {unresolved.length===1?'request':'requests'}. Locations last verified in this conversation. Choose Locate to check current directions from the entrance.</p>
    {#if $portal.summary.truncated}<p class="summary-warning" role="status">This report shows the most recent retained requests. Earlier requests exceeded the session report limit.</p>{/if}
    {#if !entries.length}<p>No items have been looked up yet. Ask Monti to find an item first.</p>{/if}
    {#each groups as group (group.aisle)}<section class="aisle-summary" aria-label={group.aisle}><h3>{group.aisle}</h3><ul>{#each [...group.products].sort((a,b)=>a.shelf.label.localeCompare(b.shelf.label,undefined,{numeric:true})) as product (product.id)}<li><div class="summary-image"><ProductVisual productID={product.id} category={product.category} compact /></div><div class="summary-product"><strong>{product.name}</strong><span>{product.aisle.label} · {product.shelf.label}</span></div><button aria-label={`Locate ${product.name} from summary`} onclick={()=>{void portal.chooseBrowse(product);}}>Locate</button></li>{/each}</ul></section>{/each}
    {#if unresolved.length}<section class="unresolved-summary" aria-label="Unresolved requests"><h3>Still to confirm</h3><ul>{#each unresolved as entry}<li><strong>{entry.query}</strong><span>{entry.status==='not_found'?'No catalog match found':entry.status==='needs_choice'?'Choose the product you mean':'Directions not confirmed'}</span>{#if entry.products.length}<p>Catalog matches: {entry.products.map(p=>p.name).join(', ')}. Ask Monti to find your choice.</p>{/if}</li>{/each}</ul></section>{/if}
  {/if}
</section>
{/if}
<style>
.conversation-summary{background:white;border:1px solid #cbdcf8;border-radius:20px;padding:22px;margin:20px 0;color:#18386f;min-width:0}.summary-top{display:flex;align-items:center;justify-content:space-between;gap:12px}.summary-overline{font-size:11px;letter-spacing:2px;font-weight:700}.summary-top h2{font-size:23px;margin:6px 0}.conversation-summary button{min-height:44px;padding:10px 14px;border:1px solid #91aedb;border-radius:10px;background:white;color:#13418a;font-weight:600;flex-shrink:0}.summary-note{font-size:14px;line-height:1.6;color:#526588}.summary-offer{background:#eef4ff;border-radius:12px;padding:16px;margin-top:16px}.summary-offer p{margin:0 0 10px}.summary-offer>div{display:flex;gap:10px;flex-wrap:wrap}.summary-warning{background:#fff5de;padding:12px;border-radius:10px;color:#75501e}.aisle-summary h3{font-size:18px;border-bottom:2px solid #cbdcf8;padding-bottom:10px}.conversation-summary ul{list-style:none;padding:0}.aisle-summary li{display:flex;align-items:center;gap:12px;border-bottom:1px solid #e7edf7;padding:12px 0}.summary-image{width:70px;flex-shrink:0}.summary-image :global(.product-visual){min-height:0;height:70px;border-radius:10px}.summary-image :global(svg){height:65px}.summary-product{display:flex;flex:1;min-width:0;flex-direction:column;gap:6px;overflow-wrap:anywhere}.summary-product span,.unresolved-summary span{font-size:14px;color:#526588}.unresolved-summary{background:#f6f8fd;padding:14px;border-radius:12px}.unresolved-summary li{display:flex;flex-direction:column;gap:6px;margin-bottom:14px;overflow-wrap:anywhere}.unresolved-summary p{font-size:13px;margin:0;line-height:1.5}@media(max-width:500px){.conversation-summary{padding:14px}.summary-top{align-items:flex-start;flex-wrap:wrap}.summary-image{width:45px}.summary-image :global(.product-visual){height:50px}.aisle-summary li{gap:8px}.conversation-summary button{padding:10px}.summary-product{font-size:14px}}
</style>
