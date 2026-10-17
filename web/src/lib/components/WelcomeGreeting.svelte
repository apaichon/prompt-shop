<script lang="ts">
  import { onMount } from 'svelte';
  import AssistantAvatar from './AssistantAvatar.svelte';
  import { VoiceClient } from '../voice/client';
  import { prepareWelcome, takeWelcome, registerWelcomeCancel } from '../voice/welcome';
  const welcome = new VoiceClient({event:()=>{},turn:()=>{}});
  let shown = false;
  function stop() { welcome.stop(); shown = false; }
  function retry() { void welcome.start(prepareWelcome(), true); }
  onMount(() => {
    const unregister = registerWelcomeCancel(stop);
    const audio = takeWelcome();
    if (audio && !document.hidden) { shown = true; void welcome.start(audio, true); }
    else audio?.close();
    const hidden = () => { if(document.hidden)stop(); };
    document.addEventListener('visibilitychange',hidden); window.addEventListener('pagehide',stop);
    return () => { unregister(); stop(); welcome.devices.destroy(); document.removeEventListener('visibilitychange',hidden); window.removeEventListener('pagehide',stop); };
  });
</script>
{#if shown}<section class="welcome-greeting" aria-label="Monti welcome">
  <AssistantAvatar phase={$welcome.phase} level={$welcome.outputLevel} size={64}/>
  <div><strong>Hi, I’m Monti. Welcome!</strong><p>Ask me a question or tell me what you’d like to find.</p><span class="welcome-status" role="status">{$welcome.active ? 'Playing welcome · Microphone off' : $welcome.phase === 'error' ? 'Tap Play welcome to hear Monti.' : 'Choose Start voice when you’re ready to talk.'}</span></div>
  {#if $welcome.active}<button onclick={stop}>Skip welcome</button>{:else if $welcome.phase === 'error'}<button onclick={retry}>Play welcome</button>{:else}<button onclick={stop}>Dismiss welcome</button>{/if}
</section>{/if}
<style>
  .welcome-greeting{display:flex;align-items:center;gap:16px;padding:18px 24px;margin:18px auto;background:#eef4ff;border:1px solid #c6d8f9;border-radius:18px;color:#18386f;max-width:1440px}.welcome-greeting strong{font-size:18px}.welcome-greeting p{margin:5px 0;font-size:14px;line-height:1.5}.welcome-status{font-size:12px}.welcome-greeting button{margin-left:auto;flex-shrink:0;min-height:44px;background:white;border:1px solid #8799b6;color:#18386f;border-radius:10px;padding:10px 16px;font-weight:600}@media(max-width:600px){.welcome-greeting{margin:12px;gap:10px;padding:14px;flex-wrap:wrap}.welcome-greeting>div{flex:1;min-width:160px}.welcome-greeting button{margin-left:0}.welcome-greeting strong{font-size:16px}}
</style>
