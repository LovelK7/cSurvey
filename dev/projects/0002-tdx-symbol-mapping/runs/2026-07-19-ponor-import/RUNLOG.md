# Run log: first real TopoDroid import (ponor_rupa_babi_pod_kucu)

Protocol: [dev/production/methods/instrumented-run.md](../../../../production/methods/instrumented-run.md)
Fixture: `dev/example/ponor_rupa_babi_pod_kucu-1p.csx` (gitignored; SHA256 `D0096817A4AE…753ACB`)
App under test: `C:\csurvey64\cSurveyPC.exe` (release binary dated 2025-12-10, x64)
Inspector: `dev/production/tools/inspect_survey.py`

Rules: one entry per step, newest last. Record the exact action taken in the UI
(including anything unexpected — dialogs, errors, hesitations), then the
machine-checked deltas. Where a delta contradicts a prediction from the
protocol's expectations table, mark it **CONTRADICTION** — the file wins over
the docs, and it must be fed back into dev/docs.

---

## step-00 — raw export baseline (2026-07-19, agent)

- Report: [step-00-raw-export.json](step-00-raw-export.json) — generated read-only
  from the untouched TopoDroid export; no UI involved.
- Verdict: raw TopoDroid export, creatid=TopoDroid 6.4.29, file version 1.11.
- 56 segments = 7 shots + 49 splays; 0 trigpoints; no `<calculate>` cache.
- Sketch: 34 flat items (plan 12: wall×4, overhang×7, label×1 · profile 22:
  wall×4, wall:presumed×1, water-drip×8, blocks×2, label×6, user×1);
  473 points, 0 bound.
- Geometry: plan bbox [-11.79..0.23]×[-9.95..1.69] coord-sum -1470.18;
  profile bbox [-14.42..0.58]×[-0.27..38.70] coord-sum 2384.66.
- Segment ids: sequential ints on legs, EMPTY on splays (duplicated —
  cSurvey must regenerate GUIDs at import).

## step-01 — after import, saved untouched (2026-07-19, user + agent)

- **User action:** switched `therion.path` to `C:\Program Files\Therion\therion.exe`
  (therion **6.4.0** 2026-05-07; previously 6.1.8/2023 in x86) — then opened the
  export in cSurvey (`C:\csurvey64\cSurveyPC.exe`) and saved into the run dir as
  `ponor_rupa_babi_pod_kucu-1p.csx` (+ a `_backup` copy). Agent copied it to the
  protocol name `step-01-after-import.csx`; report:
  [step-01-after-import.json](step-01-after-import.json). Original fixture SHA256
  re-verified unchanged. 29 KB → 249 KB (computed `<data>` per shot + `<calculate>` cache).
- **Predictions scorecard: 10/10 ✓, no contradictions.**
  1. ✓ verdict *post-import*, `creat_postprocessed` stamped.
  2. ✓ 34 flat → 34 nested, **zero items dropped** (incl. `wall:presumed`, `user`, labels).
  3. ✓ all 473 points bound (245+228), `items_without_bound_points` 0.
  4. ✓ trigpoints 0 → 57 (8 stations + 49 splay stations).
  5. ✓ `<calculate>` cache present (57 stations, speleometrics) — solved by therion 6.4.0.
  6. ✓ segment ids: 56/56 unique GUID-format (were sequential ints / empty).
  7. ✓ DistoX attrs moved to datarow; stamps present (see nuances).
  8. ✓ **root `version="1.14"` → zero version skew**: the 2025-12-10 binary writes the
     same file version as this source tree — docs citations apply to the app under test.
  9. ✓ geometry digest **exactly** unchanged (plan coord-sum -1470.18, profile 2384.66)
     — import binds points without moving them.
  10. ✓ splay stations keep TopoDroid names (`0(0)`…), `splay`/`exclude` flags survive;
     the explicit `l/r/u/d` zeros vanished (native omit-default serialization).
- **New knowledge (not in docs before this run):**
  - **Symbol → layer/item mapping** observed: plan `overhang` lines → layer 2
    WaterAndFloorMorphologies (`type=1 cat=3`); `wall` **and** `wall:presumed` →
    layer 5 Borders as **inverted free-hand areas** (`type=4 cat=1` — the cave-border
    item type, one per stroke, not unioned); point symbols (`water-drip`, `blocks`,
    `user`) → layer 6 Signs `type=6 cat=80`; `label` → Signs `type=8 cat=81` with
    `text` preserved (e.g. `spoj`) + font child. One profile line landed as a plain
    free-hand line `type=1 cat=2` on Borders.
  - Datarow custom fields are named `distox_g|distox_m|distox_dip|distox` (docs said
    `g/m/dip/distox`); order: `…|import_source|import_date`.
  - `import_source="TopoDroid"`; **`import_date` = TopoDroid's `creatdate`**
    (2026-07-18T00:00), *not* the import wall-clock (import happened 07-19).
  - Root `<csurvey>` got a fresh GUID `id` (was empty).
- **Not yet verified:** visual sanity (step-02) and whether binding actually warps
  (step-03).

## step-02 — UI observations (2026-07-19, user; code grounding by agent)

Two limitations observed by the user in the designer (screenshots shown in chat;
drop copies here as `step-02-plan.png` / `step-02-profile.png` if wanted). Both
already known to the user from the TDX→CS guidelines PDF (to be added to
`dev/literature/`); now grounded in code and quantified.

**Finding 1 — unmapped point symbols render as X-in-a-square.**
`water-drip` and `user` points show the placeholder glyph instead of a drip symbol.
Mechanism ([cImportTopoDroidHelper.vb:380-398](../../../../../cSurveyPC/cImportTopoDroidHelper.vb#L380-L398)):
the therion name, minus dashes/underscores, is `Enum.TryParse`d against
`cIItemSign.SignEnum` (~70 members, [cIItemSign.vb:34-119](../../../../../cSurveyPC/cIItemSign.vb#L34-L119));
no match → `SignEnum.Undefined` → X-box. Quantified in step-01's XML: of the 10
profile sign items, **2 mapped** (`blocks` → `sign=1290` Blocks) and **8 are
Undefined** (7 water-drip + 1 user; the 8th water-drip was drawn as a *line* and
fell through the line-fallback into a generic Borders-layer border, `type=1 cat=2` —
a silent mis-categorization). **The original therion name is NOT kept** on the
item (no attr, not in datarow) → unmapped symbols are irrecoverable post-import;
any mapping fix must act on the csx *before* import or inside the converter.
Lines/areas have their own hardcoded `Select Case` maps with fallbacks
(unknown line → Borders border; unknown area → Soil): no name survives there either.

**Finding 2 — wall stroke orientation breaks the cave-border fill.**
TDX guideline: draw walls counterclockwise so "inside" is correct. Each `wall`
stroke becomes its own `cItemInvertedFreeHandArea` on Borders
([cImportTopoDroidHelper.vb:173-192](../../../../../cSurveyPC/cImportTopoDroidHelper.vb#L173-L192);
`outline=-1` → MergeMode Subtract); wrong-direction strokes fill the wrong side
(the purple-blob mess in the plan screenshot). The converter does **not**
normalize orientation (a `Points.Revert()` call at :208 exists but is commented
out — and is for `pit` lines anyway).
**cSurvey CAN flip direction post-import** (user hadn't found it): select the
item → **"Revert sequences"** (all strokes of the item,
[frmMain2.vb:18420](../../../../../cSurveyPC/frmMain2.vb#L18420)) or **"Revert
sequence"** (single stroke at selected point, :18563) — undo-safe.

Both findings share one shape: **fixable by a read/write csx pre-processor**
(rename symbols per a mapping table; CCW-normalize wall strokes via signed-area
test) — no cSurvey build needed. Follow-up briefs to be drafted; TDX manual
pending from user.

## ⚠ incident — pristine fixture lost from disk (2026-07-19)

The user moved their TopoDroid working files to **`G:\My Drive\Share\TDX`** (the
phone syncs there — this is now the standing TDX→PC handoff location). In the
move, the **raw 29 KB export vanished**: `dev/example` no longer holds it and the
G share holds only post-import saves (250 KB+). Compounding it, an agent batch
regeneration overwrote the good `step-00-raw-export.json` with an error stub
(now deleted; the inspector has since been hardened to never clobber an existing
report with an error payload). **All step-00 numbers survive in this log**; the
machine report is regenerable the moment the fixture returns.
**Recovery:** re-export from TopoDroid on the phone (survey unchanged there) or
Google Drive trash/version history; verify against SHA256 `D0096817A4AE…753ACB`.
Until then: treat `step-01-after-import.csx` as the earliest on-disk state.

## step-02b — border cleanup by user (2026-07-19, discovered from diffs)

Between step-01 and the warp probe the user additionally **consolidated the
wall strokes** in the designer (the fix for finding 2): plan Borders 4 items → 1,
profile Borders 6 → 1 (34 → 26 items total), point counts up (245→305 plan,
228→361 profile — merged/redrawn outlines), everything still bound. Snapshot
captured from the user's pre-warp save: [step-02b-border-cleanup.csx] →
[step-02b-border-cleanup.json](step-02b-border-cleanup.json).
*(User to confirm the exact operations used — presumed join/merge/redraw of
border items.)*

## step-03 — warp probe ✅ (2026-07-19, user + agent)

- **Deviation from protocol (harmless):** edited shot **6→7** distance
  4.97 → 6.10 (+1.13 m), not the prescribed 0→1. Saved as
  `…_warp.csx` on the G share; copied here as `step-03-warp-probe.csx` →
  [step-03-warp-probe.json](step-03-warp-probe.json).
- **Diffed against step-02b (the true base): WARPING CONFIRMED.**
  Item and point counts identical (26 items; 305+361 points, all bound);
  geometry moved on **both** designs: plan coord-sum -2472.22 → -2516.51,
  bbox deepened [-13.07 → -14.94] (the lengthened shot pushed the far end);
  profile coord-sum 5312.73 → 5200.04, bbox widened [-20.83 → -22.27].
  `designwarpingmode=1` intact. User confirms it looks right in the UI.

## findings — run verdict (2026-07-19, agent)

**Pipeline A validated end-to-end on real data: import 10/10 predictions,
binding real, warping real.** A phone sketch imported through
`Load(FixTopoDroid)` becomes typed, layered, fully bound items that follow
centerline edits. The automation core of the fork's goal is proven working
in the shipped binary, with zero version skew vs this source tree.

Known limitations (step-02, both pre-import-fixable, follow-up brief pending):
1. Point symbols outside `SignEnum` (e.g. `water-drip`, `user`) become
   irrecoverable Undefined X-boxes — original name discarded at conversion.
2. Wall-stroke orientation is not normalized at import; clockwise strokes
   invert the cave-border fill (manual fix exists: "Revert sequences").

Protocol lessons for future runs: (a) users *will* interleave their own edits
between steps — always diff against the actual predecessor file, not the
nominal one (step-02b exists because of this); (b) generate reports with
`-o` (BOM-free), never PowerShell `>`;  (c) snapshot the pristine input into
the run dir at step-00 time — a gitignored original elsewhere is one file-move
away from loss.
