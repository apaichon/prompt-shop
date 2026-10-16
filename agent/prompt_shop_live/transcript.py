"""Bounded turn input assembly for the existing single recovery reminder."""


def merge_transcript(previous: str, chunk: str) -> str:
    prior, next_chunk = previous.strip(), chunk.strip()
    if not next_chunk:
        return prior
    if not prior or next_chunk.startswith(prior):
        return next_chunk
    if prior.startswith(next_chunk):
        return prior
    # Gemini can send deltas or cumulative transcription; preserve both without
    # repeating a shared suffix. Do not discard a repeated word inside a delta.
    for size in range(min(len(prior), len(next_chunk), 48), 3, -1):
        if prior[-size:] == next_chunk[:size]:
            return prior + next_chunk[size:]
    joiner = "" if next_chunk[0] in ".,!?;:)" else " "
    return prior + joiner + next_chunk
