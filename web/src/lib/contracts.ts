import { z } from 'zod';

const id = z.string().regex(/^[a-z0-9-]{1,64}$/);
const label = z.object({ id, label: z.string().min(1).max(80) }).strict();
const point = z.object({ x: z.number().finite(), y: z.number().finite() }).strict();
const version = z.number().int().positive();
export const productSchema = z.object({
  id, name: z.string().min(1).max(120), category: z.string().min(1).max(80),
  aisle: label, shelf: label, route_available: z.boolean()
}).strict();
export const searchSchema = z.object({
  query: z.string().min(1).max(200), language: z.literal('en-US'), catalog_version: version,
  candidates: z.array(productSchema).max(3), ambiguous: z.boolean()
}).strict();
const routeFields = {
  product: productSchema, catalog_version: version, map_version: version,
  origin_node_id: z.literal('entrance'), node_ids: z.array(id).min(1).max(2048),
  points: z.array(point).min(1).max(2048), steps: z.array(z.string().min(1).max(500)).min(1).max(100),
  distance_units: z.number().finite().nonnegative()
};
export const routeSchema = z.object(routeFields).strict();
export const mapSchema = z.object({
  store_id: z.literal('demo-store'), name: z.string().min(1).max(120), map_version: version,
  width: z.number().finite().positive(), height: z.number().finite().positive(), origin_node_id: z.literal('entrance'),
  aisles: z.array(z.object({ ...label.shape, polygon: z.array(point).min(3).max(100) }).strict()).max(100),
  nodes: z.array(z.object({ ...label.shape, ...point.shape }).strict()).min(1).max(2048),
  edges: z.array(z.object({ from: id, to: id }).strict()).max(8192), enabled_languages: z.array(z.literal('en-US')).min(1).max(1)
}).strict();
export const ticketSchema = z.object({ session_id: z.string().min(1).max(128), ticket_expires_at: z.iso.datetime(), ws_path: z.literal('/ws/voice') }).strict();
export const errorSchema = z.object({ error: z.object({
  code: z.string().max(80), message: z.string().max(500), retryable: z.boolean(),
  details: z.object({ product: productSchema }).strict().optional()
}).strict(), request_id: z.string().max(128) }).strict();
const searchID = z.string().regex(/^[a-zA-Z0-9_-]{1,128}$/);
const envelope = { session_id: z.string().min(1).max(128) };
const turn = { turn_id: z.string().regex(/^turn-(0|[1-9][0-9]{0,8})$/) };
const generation = { generation_id: z.string().regex(/^generation-(0|[1-9][0-9]{0,8})$/) };
export const eventSchema = z.discriminatedUnion('type', [
  z.object({ ...envelope, type: z.literal('ready'), expires_at: z.iso.datetime(), input_rate: z.literal(16000), output_rate: z.literal(24000) }).strict(),
  z.object({ ...envelope, ...turn, type: z.enum(['input_transcript', 'output_transcript']), text: z.string().max(8000), final: z.boolean() }).strict(),
  z.object({ ...envelope, ...turn, type: z.literal('candidates'), search_id: searchID, catalog_version: version, candidates: z.array(productSchema).max(3) }).strict(),
  z.object({ ...envelope, ...turn, type: z.literal('route'), search_id: searchID, ...routeFields }).strict(),
  z.object({ ...envelope, ...turn, ...generation, type: z.enum(['audio_start', 'audio_end', 'interrupted']) }).strict(),
  z.object({ ...envelope, ...turn, type: z.literal('turn_complete') }).strict(),
  z.object({ ...envelope, type: z.literal('error'), code: z.string().max(80), message: z.string().max(500), retryable: z.boolean(), turn_id: turn.turn_id.optional() }).strict(),
  z.object({ ...envelope, type: z.literal('session_ending'), reason: z.string().max(80) }).strict(),
  z.object({ ...envelope, type: z.literal('pong') }).strict()
]);
export type Product = z.infer<typeof productSchema>;
export type Search = z.infer<typeof searchSchema>;
export type Route = z.infer<typeof routeSchema>;
export type StoreMap = z.infer<typeof mapSchema>;
export type VoiceEvent = z.infer<typeof eventSchema>;

export function routeMatchesMap(route: Route, map: StoreMap): boolean {
  if (route.map_version !== map.map_version || route.node_ids[0] !== map.origin_node_id || route.node_ids.length !== route.points.length) return false;
  if (!map.aisles.some((a) => a.id === route.product.aisle.id)) return false;
  return route.node_ids.every((id, i) => {
    const node = map.nodes.find((n) => n.id === id), p = route.points[i];
    if (!node || node.x !== p.x || node.y !== p.y || p.x < 0 || p.y < 0 || p.x > map.width || p.y > map.height) return false;
    const prior = route.node_ids[i - 1];
    return i === 0 || map.edges.some((e) => (e.from === prior && e.to === id) || (e.to === prior && e.from === id));
  });
}
