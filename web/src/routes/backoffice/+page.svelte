<script lang="ts">
 import {onMount,onDestroy,tick} from 'svelte';
 import {Backoffice,type Draft} from './model';
 import Icon from '#lib/components/Icon.svelte';
 import './backoffice.css';
 const office=new Backoffice();
 let password=$state('');let query=$state('');let stateFilter=$state('');let lastFocus=0;
 $effect(()=>{if($office.focus!==lastFocus){lastFocus=$office.focus;void tick().then(()=>document.getElementById('product-name')?.focus())}});
 onMount(()=>{void office.init();const timer=setInterval(()=>office.checkExpiry(),1000);return()=>clearInterval(timer)});
 onDestroy(()=>office.destroy());
 function update(field:keyof Draft,value:string){if($office.draft)office.update({...$office.draft,[field]:value})}
 async function login(){const value=password;password='';await office.login(value)}
 const statusLabel={draft:'Draft',published:'Published',archived:'Archived'};
</script>
<svelte:head><title>Catalog workspace · Prompt Shop</title></svelte:head>
<main id="main" class="backoffice-page">
 <div class="workspace-heading"><div><p class="eyebrow">KEEP THE STORE EASY TO FIND</p><h1>Catalog workspace</h1><p>Maintain item names, shelf locations, and shopper visibility.</p></div>{#if $office.phase==='authenticated'}<button class="text-button logout" disabled={$office.saving} onclick={()=>office.logout()}>Log out <Icon name="arrow" size={16}/></button>{/if}</div>
 {#if $office.phase==='loading'}<p role="status">Checking your session…</p>
 {:else if $office.phase==='anonymous'}
  <section class="login-card" aria-labelledby="login-heading"><div class="login-icon"><Icon name="leaf" size={24}/></div><p class="eyebrow">FOR STORE MAINTAINERS</p><h2 id="login-heading">Welcome back.</h2><p>Log in to keep every item in the right place.</p>
   {#if $office.draft}<p class="notice">Your unsaved edit is kept on this page. Log in again to continue.</p>{/if}
   <form onsubmit={e=>{e.preventDefault();void login()}}><label for="maintainer-password">Maintainer password</label><input id="maintainer-password" type="password" bind:value={password} autocomplete="current-password" required minlength="16" maxlength="72" disabled={$office.saving}/><button class="button" type="submit" disabled={$office.saving}>{$office.saving?'Logging in…':'Log in'}<Icon name="arrow" size={16}/></button></form>
   <p class="login-note">Looking for an item? <a href="/">Return to the shopper finder.</a></p>
  </section>
 {:else}
  <div class="workspace-grid">
   <section class="catalog-card" aria-labelledby="catalog-heading" aria-busy={$office.loading}>
    <div class="catalog-title"><h2 id="catalog-heading">Store catalog</h2><button class="button new-item" disabled={$office.saving} onclick={()=>office.edit()}>+ New item</button></div>
    <form class="catalog-filters" onsubmit={e=>{e.preventDefault();void office.load('',[],{q:query,state:stateFilter})}}><div><label for="catalog-query">Search catalog</label><input id="catalog-query" bind:value={query} maxlength="200" placeholder="Item name or alias"/></div><div><label for="catalog-state">Visibility</label><select id="catalog-state" bind:value={stateFilter}><option value="">All items</option><option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option></select></div><button class="button" disabled={$office.loading} type="submit">Filter</button></form>
    <div class="catalog-items">{#each $office.items as item (item.id)}<button class="catalog-item" disabled={$office.saving} class:selected={$office.draft?.id===item.id} onclick={()=>office.edit(item)} aria-label={`Edit ${item.name}`}><div><strong>{item.name}</strong><span>{item.category} <span aria-hidden="true">·</span> {item.id}</span></div><span class={`state-pill ${item.state}`}>{statusLabel[item.state]}</span><Icon name="arrow" size={15}/></button>{:else}<p class="catalog-empty">{$office.loading?'Loading the catalog…':'No items match this filter.'}</p>{/each}</div>
    <div class="catalog-pagination"><button class="text-button" disabled={!$office.history.length||$office.loading} onclick={()=>office.previous()}>← Previous</button><span>Page {$office.history.length+1}</span><button class="text-button" disabled={!$office.next||$office.loading} onclick={()=>office.next()}>Next →</button></div>
   </section>
   <section class="editor-card" aria-labelledby="editor-heading">
    {#if $office.draft}
     {@const draft=$office.draft}
     <div class="editor-heading"><div><p class="eyebrow">{$office.dirty?'UNSAVED CHANGES':draft.version===null?'START WITH A DRAFT':`VERSION ${draft.version}`}</p><h2 id="editor-heading">{draft.version===null?'New item':'Edit item'}</h2></div><button class="text-button" disabled={$office.saving} onclick={()=>office.cancel()}>Close</button></div>
     {#if draft.state==='published'}<p class="publication-warning"><Icon name="leaf" size={18}/>Saving changes hides this item from shoppers until you publish it again.</p>{/if}
     {#if $office.conflict}<div class="conflict-note" role="alert"><strong>A newer version is available.</strong><p>Your edit is kept. Replacing it with the latest version lets you review and edit again.</p><button class="text-button" disabled={$office.saving} onclick={()=>office.reloadLatest()}>Replace edit with latest version</button></div>{/if}
     <form class="product-form" onsubmit={e=>{e.preventDefault();void office.save()}}>
      <fieldset disabled={$office.saving||$office.conflict}><label for="product-id">Item ID</label><input id="product-id" value={draft.id} oninput={e=>update('id',e.currentTarget.value)} readonly={draft.version!==null} required pattern={'[a-z0-9-]{1,64}'} maxlength="64" placeholder="e.g. jasmine-rice-1kg"/><span class="field-help">Lowercase letters, numbers, and hyphens. Set once when creating.</span>
      <label for="product-name">Item name</label><input id="product-name" value={draft.name} oninput={e=>update('name',e.currentTarget.value)} required maxlength="120" placeholder="e.g. Jasmine rice 1 kg"/>
      <label for="product-category">Category</label><input id="product-category" value={draft.category} oninput={e=>update('category',e.currentTarget.value)} required maxlength="80" placeholder="e.g. Pantry"/>
      <label for="product-shelf">Shelf location</label><select id="product-shelf" value={draft.shelf_id} onchange={e=>update('shelf_id',e.currentTarget.value)} required><option value="" disabled>Choose an existing shelf</option>{#each $office.shelves as shelf}<option value={shelf.id}>{shelf.aisle.label} / {shelf.label}{shelf.mapped?'':' (not mapped)'}</option>{/each}</select>
      <label for="product-aliases">English search aliases</label><textarea id="product-aliases" value={draft.aliases} oninput={e=>update('aliases',e.currentTarget.value)} rows="4" placeholder="jasmine rice&#10;rice"></textarea><span class="field-help">One name or phrase per line, up to 20 aliases. At least one English alias is needed to publish.</span>
      <button class="button save-draft" type="submit">{$office.saving?'Saving…':'Save as draft'}<Icon name="check" size={16}/></button></fieldset>
     </form>
     {#if draft.version!==null}<div class="publication-actions"><div><span class={`state-pill ${draft.state}`}>{statusLabel[draft.state as keyof typeof statusLabel]}</span><p>{draft.state==='published'?'Visible to shoppers.':draft.state==='archived'?'Hidden from shoppers. The record is retained.':'Hidden from shoppers until published.'}</p></div><button class="button" disabled={$office.saving||$office.conflict||$office.dirty||draft.state==='published'||!$office.shelves.find(s=>s.id===draft.shelf_id)?.mapped} onclick={()=>office.transition('publish')}>Publish item</button><button class="archive-button" disabled={$office.saving||$office.conflict||$office.dirty||draft.state==='archived'} onclick={()=>office.transition('archive')}>Archive item</button></div>{/if}
    {:else}<div class="editor-empty"><Icon name="leaf" size={40}/><h2 id="editor-heading">A place for every item.</h2><p>Choose an item to edit its name and shelf, or create a new draft.</p></div>{/if}
   </section>
  </div>
 {/if}
 {#if $office.message}<div class="workspace-feedback" role="status" aria-live="polite"><Icon name="check" size={18}/><p>{$office.message}</p></div>{/if}
 <p class="workspace-footnote">Changes are checked before saving. Shopper locations always come from the store catalog.</p>
</main>
