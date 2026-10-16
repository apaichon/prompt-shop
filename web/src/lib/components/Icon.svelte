<script lang="ts">
  export let name = 'search';
  export let size = 20;
  const paths: Record<string, string> = {
    search: 'm21 21-4.5-4.5 M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0',
    mic: 'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5 M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8',
    arrow: 'M4 12h16 m-6-6 6 6-6 6',
    pin: 'M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0 M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    sound: 'M3 9h4l5-5v16l-5-5H3V9 M16 8a6 6 0 0 1 0 8 M19 5a10 10 0 0 1 0 14',
    close: 'm6 6 12 12 M6 18 18 6',
    map: 'm3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2V5 M9 3v16 M15 5v16',
    check: 'm5 12 4 4L19 6',
    stop: 'M6 6h12v12H6z',
    leaf: 'M19 3C7 3 3 7 5 15c8 4 15-2 14-12 M4 21 15 9',
    chat: 'M21 11a9 9 0 0 1-9 9H4l-3 2 2-6a9 9 0 1 1 18-5 M7 10h10 M7 14h6',
    route: 'M6 19h9a4 4 0 0 0 0-8H9a4 4 0 0 1 0-8h9 M6 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0 M18 1v4m-2-2h4',
    sparkle: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3',
    chevron: 'm6 9 6 6 6-6',
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z'
  };
</script>
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.search} /></svg>
