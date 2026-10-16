<script lang="ts">
  import type { Snippet } from 'svelte';
  import AudioSettings from './AudioSettings.svelte';
  import Icon from './Icon.svelte';
  import AssistantAvatar from './AssistantAvatar.svelte';
  import { shopBrand } from '../ui-config';
  import type { Portal } from '../portal';
  export let portal: Portal;
  export let prefix = 'desktop';
  export let mapContent: Snippet | undefined = undefined;
  const voice = portal.voice;
  const labels = { idle: 'Ready when you are', connecting: 'Connecting', listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking', interrupted: 'Listening after interruption', error: 'Voice paused' };
  $: countdown = `${Math.floor($voice.remaining / 60)}:${String($voice.remaining % 60).padStart(2, '0')}`;
</script>
<section class="voice-panel monti-panel" aria-labelledby={`${prefix}-voice-title`}>
  <div class="assistant-intro"><div class="portrait-orbit"><AssistantAvatar phase={$voice.phase} level={$voice.outputLevel} size={124} /></div><div><span class="small-overline">YOUR STORE COMPANION</span><h2 id={`${prefix}-voice-title`}>Hi, I’m {shopBrand.assistant}<span class="hello-dot">.</span></h2><p>Let’s find what you need.</p><span class="assistant-language">English <span aria-hidden="true">·</span> Voice AI</span></div></div>
  <div class="captions" aria-label="Live captions" aria-live="polite" aria-atomic="false">
    {#if $voice.input}<p class="user-bubble"><strong>You</strong><span>{$voice.input}</span></p>{/if}
    {#if $voice.output}<p class="assistant-bubble"><strong>{shopBrand.assistant}</strong><span>{$voice.output}</span></p>{/if}
    {#if !$voice.input && !$voice.output}<p class="assistant-bubble welcome-bubble"><Icon name="sparkle" size={16} /><span>Say hello, plan a meal, or ask me where to find an item.</span></p>{/if}
    <span class="caption-disclosure">Live captions · Provisional</span>
  </div>
  {@render mapContent?.()}
  <div class="voice-controls">
    <div class="voice-status" role="status" aria-live="polite"><span class:active={$voice.active}></span>{labels[$voice.phase]}</div>
    {#if $voice.active}<p class="session-time">{$voice.micMuted ? 'Microphone muted' : $voice.micHeld ? 'Mic paused for speakers' : 'Microphone on'} <span aria-hidden="true">·</span> <span aria-label={`${$voice.remaining} seconds remaining`}>{countdown} left</span></p>{:else}<p class="session-time">Tap the mic and ask me</p>{/if}
    <div class="voice-control-row"><button class="round-control" disabled={!$voice.active} aria-label={$voice.micMuted ? 'Unmute mic' : 'Mute mic'} aria-pressed={$voice.micMuted} onclick={() => voice.muteMicrophone()}><Icon name="mic" size={20} /></button><button class="voice-primary" class:ending={$voice.active} aria-label={$voice.active ? 'End voice' : $voice.phase === 'error' ? 'Restart voice' : 'Start voice'} onclick={() => $voice.active ? portal.stopVoice() : portal.startVoice()}><Icon name={$voice.active ? 'stop' : 'mic'} size={29} /></button><button class="round-control" disabled={!$voice.active} aria-label={$voice.soundMuted ? 'Unmute sound' : 'Mute sound'} aria-pressed={$voice.soundMuted} onclick={() => voice.muteSpeaker()}><Icon name="sound" size={21} /></button></div>
    <span class="voice-action-label">{$voice.active ? 'End conversation' : `Talk to ${shopBrand.assistant}`}</span>
    <div class="speaker-mode-controls">
      <button class="speaker-mode-toggle" aria-pressed={$voice.speakerMode} onclick={() => voice.toggleSpeakerMode()}>Speaker mode {$voice.speakerMode ? 'on' : 'off'}</button>
      {#if $voice.speakerMode && $voice.active}<button class="interrupt-reply" disabled={!$voice.micHeld} onclick={() => voice.interrupt()}>Interrupt</button>{/if}
    </div>
    <p class="speaker-mode-help">{$voice.speakerMode ? 'Mic pauses during replies. Tap Interrupt to speak sooner.' : 'You can interrupt by speaking. Using speakers? Turn on Speaker mode.'}</p>
    {#if $voice.message}<p class="voice-notice" role={$voice.phase === 'error' ? 'alert' : undefined}>{$voice.message}</p>{/if}
    <AudioSettings {voice} {prefix} />
    <p class="privacy-note"><Icon name="check" size={12} /> Listening starts only when you choose.</p>
  </div>
</section>
