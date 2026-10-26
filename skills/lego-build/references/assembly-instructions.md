# Author an assembly sequence

Use flat `Element` placements and `build.add_step()` after a small, practical group. Steps must cover every piece exactly once in placement order. Prefer an attached, accessible sequence: place supporting pieces before overhangs, avoid trapping parts in sealed cavities, and explicitly explain any loose arrangement or subassembly that must be held until secured. Do not infer stability from the finished model alone.

Check cumulative stages with `LegoBuild(build.placements[:boundary])`: inspect collisions, connections, and support. A deliberately loose initial arrangement can be valid with a clear instruction to hold it. These checks do not prove hand access, insertion clearance, clutch strength, or real-world stability. Visually review both views of every step and explain underside attachments in captions.

The exporter supports at most 12 pieces and 6 distinct part/color types per step. Split larger groups. Nested submodels must be flattened in the authored source and assigned new explicit steps; never silently discard their internal assembly steps.

Write a JSON sidecar outside the record for meaningful captions:

```json
{
  "title": "Sunflower",
  "preparation": "Sort pieces by size and color. Build on a flat table.",
  "steps": [
    {"title": "Arrange the base", "note": "Place the four bricks together. The next step locks them."},
    {"title": "Lock the base", "note": "Center the next piece over the seams."}
  ]
}
```

Supply exactly one entry per nonempty LDraw step. Titles are at most 70 characters, preparation 420, and step notes 320. Keep captions plain text. Add `--instructions <absolute-json-path>` to `export_bundle.py`. Without this file, neutral numbered captions are used; prefer authored captions for any nontrivial model.

Every export includes `instructions.pdf`, `instructions.json`, and two images per step in `steps/`. New pieces use their actual colors, previous pieces are gray. The PDF parts list uses LDraw design IDs and colors; the separate Pick a Brick CSV uses purchasable element IDs. The JSON records the model hash and per-step inventory. Export failures leave no partial kit.
