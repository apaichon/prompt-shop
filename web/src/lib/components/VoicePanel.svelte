<script lang="ts">
  import Icon from './Icon.svelte';
  import type { Portal } from '#lib/portal.ts';
  export let portal: Portal;
  export let prefix = 'desktop';
  const voice = portal.voice;
  const labels = { idle: 'Ready when you are', connecting: 'Connecting', listening: 'Listening', thinking: 'Finding your item', speaking: 'Speaking', interrupted: 'Listening after interruption', error: 'Voice paused' };
  $: countdown = `${Math.floor($voice.remaining / 60)}:${String($voice.remaining % 60).padStart(2, '0')}`;
</script>
<section class="voice-panel" aria-labelledby={`${prefix}-voice-title`}>
  <div class="eyebrow">YOUR STORE ASSISTANT <span class="language">EN</span></div>
  <h2 id={`${prefix}-voice-title`}>Just ask.</h2>
  <p class="voice-intro">Say what you’re looking for.<br />We’ll help you find its shelf.</p>
  <div class="voice-orb" class:live={$voice.active} class:speaking={$voice.phase === 'speaking'} aria-hidden="true"><div><Icon name="mic" size={34} /></div><span></span><span></span></div>
  <div class="voice-status" role="status" aria-live="polite"><span class:active={$voice.active}></span>{labels[$voice.phase]}</div>
  {#if $voice.active}<p class="session-time">{$voice.micMuted ? 'Microphone muted' : 'Microphone on'} <span aria-hidden="true">·</span> <span aria-label={`${$voice.remaining} seconds remaining`}>{countdown} left</span></p>{/if}
  {#if $voice.active}
    <button class="button voice-start end" onclick={() => portal.stopVoice()}><Icon name="stop" size={16} /> End voice</button>
  {:else}
    <button class="button voice-start" onclick={() => portal.startVoice()}><Icon name="mic" size={18} /> {$voice.phase === 'error' ? 'Restart voice' : 'Start voice'}</button>
  {/if}
  <div class="voice-options">
    <button disabled={!$voice.active} aria-pressed={$voice.micMuted} onclick={() => voice.muteMicrophone()}><Icon name="mic" size={16} /> {$voice.micMuted ? 'Unmute mic' : 'Mute mic'}</button>
    <button disabled={!$voice.active} aria-pressed={$voice.soundMuted} onclick={() => voice.muteSpeaker()}><Icon name="sound" size={16} /> {$voice.soundMuted ? 'Unmute sound' : 'Mute sound'}</button>
  </div>
  {#if $voice.message}<p class="voice-notice" role={$voice.phase === 'error' ? 'alert' : undefined}>{$voice.message}</p>{/if}
  <div class="captions" aria-label="Live captions" aria-live="polite" aria-atomic="false">
    <div class="caption-label">LIVE CAPTIONS <span>Provisional</span></div>
    {#if $voice.input}<p><strong>You</strong><span>{$voice.input}</span></p>{/if}
    {#if $voice.output}<p><strong>Assistant</strong><span>{$voice.output}</span></p>{/if}
    {#if !$voice.input && !$voice.output}<p class="caption-empty">Your conversation appears here.<br />Confirmed locations appear in the item cards.</p>{/if}
  </div>
  <p class="privacy-note"><Icon name="check" size={14} /> Listening starts only when you choose.</p>
</section>
