import type { VoiceEvent } from '../contracts';

/** Socket identity plus monotonic server epochs; no client-assigned factual turn. */
export class EventGate {
  session: string | null = null;
  turn = 0;
  minimumTurn = 0;
  generation: string | null = null;
  private blocked = new Set<string>();
  private highestGeneration = -1;
  start(session: string) { this.stop(); this.session = session; }
  stop() { this.session = null; this.turn = 0; this.minimumTurn = 0; this.generation = null; this.blocked.clear(); this.highestGeneration = -1; }
  anticipateTurn() { this.minimumTurn = this.turn + 1; this.generation = null; }
  accept(event: VoiceEvent): { accepted: boolean; flush: boolean; newTurn: boolean } {
    const denied = { accepted: false, flush: false, newTurn: false };
    if (!this.session || event.session_id !== this.session) return denied;
    let newTurn = false;
    if ('turn_id' in event && event.turn_id) {
      const n = Number(event.turn_id.slice(5));
      if (n < this.turn || n < this.minimumTurn) return denied;
      if (n > this.turn) { this.turn = n; this.minimumTurn = n; this.generation = null; this.blocked.clear(); this.highestGeneration = -1; newTurn = true; }
    }
    if (event.type === 'interrupted') {
      // Gateway's new-turn marker uses the upcoming generation, not a cancelled one.
      if (!newTurn) { this.blocked.add(event.generation_id); this.minimumTurn = this.turn + 1; }
      this.generation = null;
      return { accepted: true, flush: true, newTurn };
    }
    if (event.type === 'audio_start') {
      const generation = Number(event.generation_id.slice(11));
      if (this.blocked.has(event.generation_id) || generation < this.highestGeneration) return denied;
      this.highestGeneration = generation;
      this.generation = event.generation_id;
    }
    if (event.type === 'audio_end') {
      if (event.generation_id !== this.generation) return denied;
      this.blocked.add(event.generation_id);
      this.generation = null;
    }
    return { accepted: true, flush: newTurn, newTurn };
  }
}
