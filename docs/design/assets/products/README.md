# Sample product artwork

Generated on 16 October 2026 using the built-in `image_gen.imagegen` tool and the
imagegen skill. Five separate opaque 1536×1024 PNG atlases contain 24 original,
unbranded sample packshots each (6 columns × 4 rows, read left-to-right).

Exact prompts: `atlas-1-prompt.txt` through `atlas-5-prompt.txt` in this directory.
PNG masters: `atlas-1.png` through `atlas-5.png`. Runtime WebP copies are in
`web/static/products/atlas-{1..5}.webp`, encoded with `cwebp -q 75` (674,608 bytes
total). ID/cell mapping: `web/src/lib/product-images.json`. Generation used no
reference image; the user's Monti screenshot informed the storefront direction.
No external brand/product photography was downloaded.

These are illustrative demo assets, not packaging, price, stock, ingredient,
allergen or shelf-position evidence. The app labels sample imagery and sample
shelf arrangements. Shelf membership and labels come from published catalog DTOs.
Products without a mapped or available atlas use category illustrations.

`desktop-catalog.png`, `desktop-shelf.png`, and `mobile-shelf.png` show the actual
local portal with the expanded seeded catalog. They contain no shopper recordings.
