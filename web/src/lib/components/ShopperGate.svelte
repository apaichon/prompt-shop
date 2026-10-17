<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { z } from 'zod';
  import { prepareWelcome, queueWelcome, cancelWelcome } from '../voice/welcome';
  export let children: Snippet;
  export let adminOnly = false;
  const sessionSchema = z.discriminatedUnion('enabled', [z.object({enabled:z.literal(false)}), z.object({enabled:z.literal(true),username:z.string(),role:z.enum(['admin','shopper']),expires_at:z.string().datetime({offset:true}),csrf_token:z.string()})]);
  type Session = z.infer<typeof sessionSchema>;
  let session: Session | null = null;
  let loading = true, busy = false, username = '', password = '', message = '';
  let logoutCSRF = '';
  let expiry: ReturnType<typeof setTimeout> | undefined;
  let generation = 0;
  function clearSession(note = '') { cancelWelcome(); generation++; session = null; loading = false; message = note; if (expiry) clearTimeout(expiry); }
  function apply(value: Session) {
    session = value; loading = false; message = ''; logoutCSRF = '';
    if (expiry) clearTimeout(expiry);
    if (value.enabled) expiry = setTimeout(() => clearSession('Your sign-in expired. Please sign in again.'), Math.max(0, Date.parse(value.expires_at) - Date.now()));
  }
  async function check() {
    const key = ++generation;
    try {
      const response = await fetch('/api/auth/session', {credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
      if (key !== generation) return;
      if (response.status === 401) { clearSession(); return; }
      if (!response.ok) throw new Error();
      const value = sessionSchema.parse(await response.json());
      if (key === generation) apply(value);
    } catch { if (key === generation) clearSession('Sign-in is temporarily unavailable. Try again.'); }
  }
  async function login(event: SubmitEvent) {
    event.preventDefault(); if (busy) return; busy = true; message = '';
    const key = ++generation;
    let welcome = !adminOnly ? prepareWelcome() : undefined;
    try {
      const response = await fetch('/api/auth/session', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password}),signal:AbortSignal.timeout(10000)});
      if (key !== generation) return;
      if (!response.ok) { message = response.status === 429 ? 'Too many attempts. Wait a minute and try again.' : response.status === 401 ? 'Username or password is incorrect.' : 'Sign-in is temporarily unavailable. Try again.'; return; }
      const value = sessionSchema.parse(await response.json());
      if (key === generation) {
        if (value.enabled && welcome && !adminOnly) { queueWelcome(welcome); welcome = undefined; }
        apply(value);
      }
    } catch { if (key === generation) message = 'Sign-in is temporarily unavailable. Try again.'; }
    finally { welcome?.close(); password = ''; busy = false; }
  }
  async function logout() {
    if (busy) return;
    if (session?.enabled) logoutCSRF = session.csrf_token;
    if (!logoutCSRF) return;
    const csrf = logoutCSRF; busy = true;
    // Unmount shopper content immediately, stopping voice and releasing its mic.
    clearSession();
    try {
      const response = await fetch('/api/auth/session', {method:'DELETE',credentials:'same-origin',headers:{'X-CSRF-Token':csrf},signal:AbortSignal.timeout(10000)});
      if (!response.ok && response.status !== 401) message = 'Sign-out could not be confirmed. Retry sign-out.';
      else { logoutCSRF = ''; message = 'Signed out.'; }
    } catch { message = 'Sign-out could not be confirmed. Retry sign-out.'; }
    finally { busy = false; }
  }
  onMount(() => {
    void check();
    const lost = () => { if(session?.enabled)clearSession('Please sign in again.'); };
    const focus = () => { if (!busy && session?.enabled) void check(); };
    window.addEventListener('shop-auth-required',lost); window.addEventListener('focus',focus);
    return () => { cancelWelcome(); generation++; if(expiry)clearTimeout(expiry); window.removeEventListener('shop-auth-required',lost);window.removeEventListener('focus',focus); };
  });
</script>
<svelte:head>{#if !session || (adminOnly && session.enabled && session.role !== "admin")}<title>Sign in · Monti Store</title>{/if}</svelte:head>
{#if loading}<main id="main" class="signin-shell"><p role="status">Checking sign-in…</p></main>
{:else if session}
  {#if session.enabled}<section class="account-bar" aria-label="Shopper account"><span>Signed in as <strong>{session.username}</strong></span><button onclick={logout} disabled={busy}>Sign out</button></section>{/if}
  {#if adminOnly && session.enabled && session.role !== 'admin'}<main id="main" class="signin-shell"><section class="signin-card"><h1>Administrator access required</h1><p>This account can use the shopper page. Sign in with an administrator account to edit the catalog.</p><a href="/">Return to the store</a></section></main>{:else}{@render children()}{/if}
{:else}
  <main id="main" class="signin-shell"><section class="signin-card" aria-labelledby="signin-title"><span class="signin-brand">Monti Store</span><h1 id="signin-title">Welcome back</h1><p>Sign in to talk to Monti and find your way around the store.</p>
    <form onsubmit={login}><label for="shop-username">Username</label><input id="shop-username" name="username" autocomplete="username" bind:value={username} required maxlength="32" autocapitalize="none" spellcheck="false" />
    <label for="shop-password">Password</label><input id="shop-password" name="password" type="password" autocomplete="current-password" bind:value={password} required maxlength="72" />
    <button class="signin-submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button></form>
    {#if message}<p role="status">{message}</p>{/if}
    <button class="retry-session" disabled={busy} onclick={check}>Check sign-in again</button>{#if logoutCSRF}<button disabled={busy} onclick={logout}>Retry sign-out</button>{/if}<a href="/backoffice">Maintainer backoffice</a>
  </section></main>
{/if}
<style>
  .signin-shell{min-height:85dvh;display:grid;place-items:center;padding:24px;background:#f3f7ff;color:#18386f}
  .signin-card{width:100%;max-width:420px;background:white;border:1px solid #d6e3fa;border-radius:24px;padding:32px;box-shadow:0 12px 40px #143e8c12}
  .signin-brand{color:#0057d9;font-weight:800}.signin-card h1{font-size:32px;margin:16px 0}.signin-card p{line-height:1.6}.signin-card label{display:block;margin:18px 0 6px;font-weight:600}.signin-card input{width:100%;min-height:48px;border:1px solid #8799b6;border-radius:10px;padding:10px;color:#18386f;background:white}.signin-submit{width:100%;margin-top:24px;background:#0057d9;color:white;border:0;border-radius:10px;min-height:48px;font-weight:700}
  .retry-session{display:block;border:0;background:transparent;color:#0057d9;min-height:44px;margin-top:12px}.signin-card a{display:inline-block;color:#224c88;min-height:44px;padding-top:12px}.account-bar{display:flex;justify-content:flex-end;align-items:center;gap:16px;background:#eef4ff;color:#18386f;padding:4px 20px;font-size:13px}.account-bar button{min-height:44px;border:0;background:transparent;color:#0048b5;font-weight:600}
</style>
