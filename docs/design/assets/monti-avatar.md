# Monti avatar asset record

Generated on 16 October 2026 with the built-in `image_gen` tool, using the imagegen
skill. This is original project artwork. The supplied Monti Store UI informed the
character direction; no product photograph or catalog fact was generated.

- Master: [monti-atlas-master.png](monti-atlas-master.png), 1536×1024 RGBA.
- Runtime: [atlas.webp](../../../web/static/avatar/monti/atlas.webp), 672×448 RGBA,
  74,240 bytes. Encoded with `cwebp -q 65 -resize 672 448`; alpha is retained.
- A 3-column × 2-row atlas, each runtime cell 224×224. Row-major poses are neutral,
  listening, thinking, speaking half-open, speaking open and recovery.
- A single cached atlas supplies all views and states below the proposed 80 KB
  initial-portrait budget, replacing the draft's separate lazy pose files.
- The typed manifest and pose mapping live in `web/src/lib/ui-config.ts`.
- Avatar motion is a presentation of voice state and observed local speaker
  playback. Reduced motion freezes the portrait. Missing assets use a mic icon.

## Final generation prompt

```text
Use case: stylized-concept. Asset type: production transparent avatar sprite atlas for a grocery voice assistant named Monti. Create original polished 3D illustrated sable-and-white rough collie dog HEAD AND CHEST portrait: warm amber and black fur, fluffy white ruff, upright ears, expressive kind brown eyes, friendly sophisticated retail mascot. Crisp studio render, soft natural shading, consistent lighting, front-facing, no collar or props. A precise sprite atlas of SIX portraits arranged THREE columns by TWO rows on true transparent background. Each cell is the same square size; perfectly aligned head center, scale, chest baseline and safe 10 percent padding, no part overlapping another cell. Entire atlas landscape aspect 3:2, no gutters. ROW ONE left-to-right: neutral warm closed-mouth smile; attentive listening eyes/ears with closed mouth; thoughtful slight head tilt with closed mouth. ROW TWO left-to-right: speaking mouth HALF OPEN; speaking mouth FULL OPEN; gentle concerned recovery expression with closed mouth. All are the identical original dog identity and framing, only the expression/mouth differs. Transparent around every portrait, no solid cell backgrounds, no labels, no borders, no text, no shadow outside the cutout. These are actual UI avatar assets, not a screenshot or UI mockup.
```
