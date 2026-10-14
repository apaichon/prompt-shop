<script lang="ts">
  import type { StoreMap, Route } from '#lib/contracts.ts';
  export let map: StoreMap;
  export let route: Route | null = null;
  $: nodes = new Map(map.nodes.map((node) => [node.id, node]));
  $: entrance = nodes.get(map.origin_node_id);
  $: destination = route?.points.at(-1);
  function center(points: { x: number; y: number }[]) {
    return { x: points.reduce((sum, p) => sum + p.x, 0) / points.length, y: points.reduce((sum, p) => sum + p.y, 0) / points.length };
  }
</script>
<div class="map-canvas">
  <svg viewBox={`-4 -6 ${map.width + 8} ${map.height + 16}`} role="img" aria-labelledby="map-title map-description">
    <title id="map-title">{map.name} floor map</title>
    <desc id="map-description">{route ? `Walking route from the entrance to ${route.product.aisle.label}, ${route.product.shelf.label}. Text directions follow below.` : 'Select an item to see its walking route from the entrance. Aisles and paths come from the store map.'}</desc>
    <rect x="0" y="0" width={map.width} height={map.height} rx="4" class="map-floor" />
    {#each map.edges as edge}
      {@const from = nodes.get(edge.from)}{@const to = nodes.get(edge.to)}
      {#if from && to}<line x1={from.x} y1={from.y} x2={to.x} y2={to.y} class="walkway" />{/if}
    {/each}
    {#each map.aisles as aisle}
      {@const middle = center(aisle.polygon)}
      <polygon points={aisle.polygon.map((p) => `${p.x},${p.y}`).join(' ')} class="aisle" class:selected={route?.product.aisle.id === aisle.id} />
      <text x={middle.x} y={middle.y} class="aisle-label" transform={`rotate(-90 ${middle.x} ${middle.y})`}>{aisle.label}</text>
    {/each}
    {#if route}
      <polyline data-testid="route-path" points={route.points.map((p) => `${p.x},${p.y}`).join(' ')} class="route-line" />
    {/if}
    {#if entrance}<circle cx={entrance.x} cy={entrance.y} r="2.2" class="entrance-dot" /><text x={entrance.x + 4} y={entrance.y - 4} class="entrance-label">Entrance</text>{/if}
    {#if destination && route}
      <circle cx={destination.x} cy={destination.y} r="3.8" class="destination-halo" />
      <circle cx={destination.x} cy={destination.y} r="1.8" class="destination-dot" />
      <text x={destination.x} y={destination.y - 5} class="destination-label">{route.product.shelf.label}</text>
    {/if}
  </svg>
</div>
