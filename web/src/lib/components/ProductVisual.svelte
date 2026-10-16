<script lang="ts">
  import images from '../product-images.json';
  export let productID = '';
  export let category = '';
  let failed = false;
  $: image = (images as Record<string,{atlas:number;cell:number}>)[productID];
  $: productID, failed = false;
  export let compact = false;
  $: type = /dairy|milk|beverage/i.test(category) ? 'carton' : /personal|health|clean/i.test(category) ? 'bottle' : 'bag';
</script>
<div class="product-visual" class:compact data-type={type} aria-hidden="true">
  {#if image && !failed}
    <img class="atlas-preload" src={`/products/atlas-${image.atlas}.webp`} alt="" onerror={() => failed = true} />
    <div class="product-packshot" style={`background-image:url('/products/atlas-${image.atlas}.webp');background-position:${(image.cell%6)*20}% ${Math.floor(image.cell/6)*100/3}%`}></div>
  {:else}
  <div class="product-visual-halo"></div>
  <svg viewBox="0 0 180 200" fill="none">
    <ellipse cx="90" cy="184" rx="48" ry="7" fill="#143B7912" />
    {#if type === 'carton'}
      <path d="M58 48 74 24h38l15 24v126a7 7 0 0 1-7 7H64a6 6 0 0 1-6-6Z" fill="#FFF" stroke="#B6C8E3" stroke-width="2" />
      <path d="m112 24 15 24H58l16-24" fill="#A2C3F8" /><path d="M58 48h69v15H58z" fill="#DBE9FE" />
      <path d="M58 84h69v64H58z" fill="#5A8DDD" /><path d="M58 132c18-21 43 14 69-8v24H58z" fill="#2B61B3" />
      <path d="M90 92c-7 10-14 17-14 24a14 14 0 0 0 28 0c0-7-7-14-14-24Z" fill="#FFF" />
      <path d="M75 158h35m-30 8h25" stroke="#B5C8E8" stroke-width="3" stroke-linecap="round" />
      <path d="M80 24v-7h23v7" fill="#EAF0FC" stroke="#B6C8E3" stroke-width="2" />
    {:else if type === 'bottle'}
      <rect x="77" y="23" width="28" height="24" rx="5" fill="#1E66D9" /><path d="M73 45h36v20c14 8 19 15 19 30v72a12 12 0 0 1-12 12H65a12 12 0 0 1-12-12V95c0-15 6-22 20-30Z" fill="#FFF" stroke="#BACFEA" stroke-width="2" />
      <rect x="54" y="94" width="73" height="57" rx="2" fill="#DCEAFF" /><path d="m91 107 6 12 14 2-10 9 2 14-12-6-12 6 2-14-10-9 14-2Z" fill="#3D7CE0" />
    {:else}
      <path d="m54 32 13 3 13-3 13 3 13-3 14 3 9-3-4 32 13 107c1 7-4 10-12 10H53c-8 0-11-4-10-11L57 64Z" fill="#F3E4CD" stroke="#D2BA92" stroke-width="2" />
      <path d="M54 46h73M57 59h68" stroke="#D2BA92" stroke-width="2" /><path d="M51 90h80l5 64H46Z" fill="#A8C7B7" />
      <path d="M89 143v-36m0 12c-13 0-18-7-18-13 12 0 18 5 18 13Zm0 12c13 0 18-7 18-13-12 0-18 5-18 13Z" stroke="#376E5A" stroke-width="3" stroke-linecap="round" />
    {/if}
  </svg>
  {/if}
  {#if !compact}<span class="illustration-label">{image && !failed ? 'Sample product image' : 'Category illustration'}</span>{/if}
</div>

<style>
 .atlas-preload {position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
 .product-packshot {width:100%;aspect-ratio:1;max-width:240px;background-size:600% 400%;background-repeat:no-repeat;mix-blend-mode:multiply}
</style>
