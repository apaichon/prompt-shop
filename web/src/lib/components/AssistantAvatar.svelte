<script lang="ts">
  import type { VoicePhase } from '../voice/client';
  import { avatar, avatarPose } from '../ui-config';
  import Icon from './Icon.svelte';
  export let phase: VoicePhase = 'idle';
  export let level = 0;
  export let size = 128;
  let failed = false;
  $: pose = avatarPose(phase, level);
</script>
<div class="assistant-avatar" class:attentive={phase === 'listening'} style={`--avatar-size:${size}px`} data-pose={pose} aria-hidden="true">
  {#if failed}<div class="avatar-fallback"><Icon name="mic" size={size / 2} /></div>
  {:else}
    <img class="avatar-load" src={avatar.src} alt="" width={avatar.width} height={avatar.height} onerror={() => failed = true} />
    <div class="avatar-art" style={`background-image:url('${avatar.src}');background-position:${(pose % 3) * 50}% ${Math.floor(pose / 3) * 100}%`}></div>
  {/if}
</div>
