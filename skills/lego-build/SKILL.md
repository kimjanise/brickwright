---
name: lego-build
description: Create or revise custom LEGO builds from prompts with a validated model, illustrated assembly PDF, live LEGO Pick a Brick price breakdown, and upload-ready parts CSV. Use for /lego-build requests, custom brick models, or pricing and exporting an existing Brickwright build.
---

# LEGO Build

Turn the user's idea into a real build and a shopping-ready kit. Example: `/lego-build create me a sunflower build`. In clients using dollar-prefixed skills, invoke `$lego-build create me a sunflower build`.

You author the model in this conversation using Brickwright's SDK. No web server, nested AI process, separate AI API key, or LEGO account is required. Internet access is needed for first-time setup and current prices.

## Set up

Resolve the skill directory from this `SKILL.md`; script paths below are relative to it. Run:

```sh
python3 <skill-dir>/scripts/setup_runtime.py
```

This installs a pinned version of the public Brickwright fork into the user's cache with `git` and `uv`, and prints absolute `python`, `brickwright`, and `repository` paths. If a compatible checkout already exists, use `--repo <checkout>` to reuse it. If prerequisites or network access are unavailable, explain that concrete blocker; do not invent a generated build or price. Use the returned executable paths in the commands below, quoted when they contain spaces.

Keep output in the current task's writable workspace (e.g. `lego-builds/`), not inside the installed skill or runtime cache. Use an absolute records directory such as `<workspace>/lego-builds/records` consistently. Export each finished kit to a **new** sibling folder, e.g. `<workspace>/lego-builds/sunflower-01`.

Use the requested country/currency when present. Otherwise state the assumption **United States / USD (`en-us`)** and proceed. Supported markets: `en-us`, `en-gb`, `en-ca`, `en-au`, `de-de`, `fr-fr`, `nl-nl`. Do not silently substitute a different market if the requested one is unsupported.

## Design and validate

1. Run `<brickwright> external instructions`, save the output outside a record, and read the authoring guidance and relevant SDK reference (the output is long; read it in sections). Do not guess part APIs or author raw LDraw as a substitute for validation.
2. Initialize a record with `<brickwright> external init "<design brief>" --records-dir <records>`. For revisions, include `--from <previous-record-id>`; preserve previous deliverables.
3. Edit only the printed `build.py` in that record. Choose a sensible size from the request; for unspecified decorative builds, aim for a modest desk-sized model with common purchasable parts. Keep at most 200 distinct part/color combinations and 2,000 total pieces for this exporter. Respect the user's requested details and budget; do not replace the requested design with a generic sample. Author a practical assembly sequence using flat part placements and `build.add_step()` after each group (at most 12 pieces and 6 part/color types per step). The PDF exporter rejects nested submodels and models without authored steps; do not pretend file order is an assembly plan. Read [references/assembly-instructions.md](references/assembly-instructions.md) for authoring, captions, and checking the sequence.
4. Run `<brickwright> external validate <record-id> --records-dir <records>` and fix reported failures. Once valid, run `external finalize` with the same record ID and records directory. Do not claim success without a current finalized export.
5. Export and price the exact finished model:

```sh
<python> <skill-dir>/scripts/export_bundle.py \
  --record <records>/<record-id> \
  --locale en-us \
  --out <workspace>/lego-builds/<unique-kit-name>
```

The exporter checks finalization and hashes, queries LEGO's live catalog, and writes the bundle atomically. Exit **0** means all pieces are uploadable; **2** means a valid bundle with missing/unavailable pieces; **1** means export failed. Do not treat exit 2 as a lost build or retry the same output folder. If live pricing fails, still deliver the finalized model from the record and explain that current prices/upload IDs are unavailable; do not fabricate a CSV.

Open `build.png` to inspect the actual model's silhouette, colors, and proportions. Inspect the instruction PDF and step images, especially underside connections and any obscured placement. They are rendered from the real part meshes. If the design or sequence is unclear, revise, validate, finalize, and export to a new kit folder. Describe geometry/connection validation accurately; it is not a physical load, assembly-access, or durability guarantee.

## Resolve parts and price

Read `price.json` and `price-breakdown.csv`. Prices are **current listed parts subtotals**, not checkout totals. Report market, currency, lookup time, and excluded shipping/service fees/additional checkout tax. Never fill missing prices with zero or an estimate labeled as actual.

For unavailable parts, use `PickABrickClient.search(<design-id or name>)` from the returned Python runtime to find real catalog options. Preserve the design's essential colors and shape; make reasonable structural substitutions, validate again, then export a new kit. Do not substitute a different color only in the CSV: it must match the delivered build. If a requested color/part is essential or no suitable replacement exists, deliver the partial kit with explicit missing quantities rather than inventing IDs or promising a complete order.

## Deliver

Return a short description and an inline preview of the actual build. Include:

- Piece count, the live parts subtotal (or clearly labeled partial subtotal), market/currency, and exclusions.
- A breakdown table with part/color, quantity, unit price, and line total. For long lists, summarize the major rows and link the complete breakdown.
- Download links to **`instructions.pdf`**, **`build.ldr`**, **`pick-a-brick.csv`**, **`price-breakdown.csv`**, and **`build-kit.zip`**. The ZIP also contains individual step images and an instruction manifest. Include `build.png` when useful. Use actual absolute local paths or the host's supported artifact links.
- If incomplete, link **`pick-a-brick-available.csv`** and **`missing-pieces.csv`** instead and explicitly state how many required pieces are omitted. If nothing can be uploaded, no upload CSV is emitted.
- The selected market's [LEGO Pick a Brick](https://www.lego.com/en-us/pick-and-build/pick-a-brick) link and the short instruction: **Upload List → choose the parts CSV → View All Pieces**. The price-breakdown CSV is for the user, not the LEGO importer.

The PDF provides illustrated, agent-authored assembly instructions; the LDraw model preserves the same step boundaries. Do not claim the sequence has been physically tested. This skill creates files for the user to upload; it does not add items to a bag or place an order.

Read [references/pick-a-brick-csv.md](references/pick-a-brick-csv.md) if diagnosing an upload issue or changing the export format.
