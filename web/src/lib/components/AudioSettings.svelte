<script lang="ts">
  import { onMount } from 'svelte';
  import type { VoiceClient } from '../voice/client';
  export let voice: VoiceClient;
  export let prefix: string;
  const devices=voice.devices;
  onMount(()=>devices.attach());
</script>
<details class="audio-settings" ontoggle={e=>{if(!e.currentTarget.open)devices.cancel();}}>
  <summary>Audio settings</summary>
  <p>Choose the microphone and speaker for your next conversation.</p>
  {#if $voice.active}<p role="status">End voice to change devices.</p>{/if}
  <fieldset disabled={$voice.active || $devices.busy}>
    <legend class="sr-only">Audio devices</legend>
    <label for={`${prefix}-microphone`}>Microphone</label>
    <select id={`${prefix}-microphone`} value={$devices.microphoneId} onchange={e=>devices.microphone(e.currentTarget.value)}><option value="">System default microphone</option>{#each $devices.microphones as d}<option value={d.id}>{d.label}</option>{/each}</select>
    <label for={`${prefix}-speaker`}>Speaker</label>
    <select id={`${prefix}-speaker`} disabled={!$devices.canSelectSpeaker} value={$devices.speakerId} onchange={e=>devices.speaker(e.currentTarget.value)}><option value="">System default speaker</option>{#each $devices.speakers as d}<option value={d.id}>{d.label}</option>{/each}</select>
    {#if !$devices.canSelectSpeaker}<p>Choose your output in the system sound settings; this browser uses the system default.</p>{/if}
    <div class="device-buttons"><button onclick={()=>devices.enable()}>Enable device names</button><button onclick={()=>devices.refresh()}>Refresh devices</button>{#if $devices.canChooseSpeaker && $devices.canSelectSpeaker}<button onclick={()=>devices.chooseSpeaker()}>Choose another speaker</button>{/if}<button disabled={$devices.testing} onclick={()=>devices.testSpeaker()}>{$devices.testing?'Playing test…':'Test speaker'}</button></div>
  </fieldset>
  {#if $devices.message}<p role="status">{$devices.message}</p>{/if}
</details>
<style>
  .audio-settings{text-align:left;border-top:1px solid #cfdaee;margin-top:16px;padding-top:10px;color:#18386f}.audio-settings summary{cursor:pointer;font-size:14px;font-weight:700;min-height:44px;padding:12px 0}.audio-settings p{font-size:12px;line-height:1.5}.audio-settings fieldset{border:0;padding:0;min-width:0}.audio-settings label{display:block;font-size:13px;font-weight:600;margin:12px 0 6px}.audio-settings select{width:100%;min-height:44px;border:1px solid #8799b6;background:white;color:#18386f;border-radius:8px;padding:8px;font-size:13px}.device-buttons{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.device-buttons button{min-height:44px;background:white;border:1px solid #8799b6;border-radius:8px;color:#18386f;padding:8px;font-size:12px}
</style>
