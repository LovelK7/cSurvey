# TDX → cSurvey symbol matrix

Deliverable of [dev/projects/0002-tdx-symbol-mapping/brief.md](../projects/0002-tdx-symbol-mapping/brief.md) phases 1–3.
**Status: ✅ RUN-CONFIRMED IN FULL.** The symbol-zoo import (`dev/projects/0002-tdx-symbol-mapping/runs/2026-07-19-symbol-zoo/`, executed 2026-07-19 on the installed binary) verified **all 74 predictions below with zero contradictions** — per-layer counts matched exactly (Soil 8, Water/floor 7, Rocks 1, Ceiling 2, Borders 12, Signs 44) and every per-symbol outcome (layer, item type/category, `sign` value, Undefined set, text/name preservation) matched the prediction. The Conf column records how each row was first derived (**RUN** = seen on real ponor data before the zoo; **code** = predicted from `cImportTopoDroidHelper.ConvertItem` ([cImportTopoDroidHelper.vb:112-401](../../cSurveyPC/cImportTopoDroidHelper.vb#L112)) and `cIItemSign.SignEnum` ([cIItemSign.vb:34-119](../../cSurveyPC/cIItemSign.vb#L34)) at commit 0c6700b) — **every row now carries zoo-run evidence** regardless of its Conf tag.

## Rendering layer (zoo v3 import + installed-build gallery scan, 2026-07-19)

Mapping to `SignEnum` is necessary but **not sufficient** for a visible symbol: the glyph must exist in the signs gallery. Sign artwork = SVGs with a `csurvey:sign` attribute under `<install>\Objects\Cliparts\Signs\`; items whose sign has no gallery SVG render the shared X-box placeholder (`clipart_error`, [cItemSign.vb:383-398](../../cSurveyPC/cItemSign.vb#L383) → [frmMain2.vb:16535](../../cSurveyPC/frmMain2.vb#L16535) → [cSignsImportHelper.vb:399](../../cSurveyPC/cSignsImportHelper.vb#L399)). Scan of the installed build (`C:\csurvey64`, 2025-12-10; 46 sign SVGs) intersected with the mapping, **confirmed against the labeled zoo v3 screenshots**:

- **✅✅ Fully usable TDX points (map + glyph), 27:** air-draught, aragonite, blocks, continuation, crystal, curtain, dig, entrance, flowstone, guano, gypsum, helictite, moonmilk, narrow-end, paleo-material, pebbles, pillar, popcorn, root, scallop, sink, soda-straw, spring, stalactite, stalagmite, wall-calcite, water-flow.
- **⚠ Map but NO glyph in this build (X-box with correct data), 8:** anchor, archeo-material, clay, gradient, ice, sand, snow, water. (Data is right — a future glyph would light them up; for print today they are X-boxes.)
- **❌ No mapping (Undefined, name lost), 8:** danger, debris, minus, mud, plus, plus-minus, user, water-drip. Total X-boxes in the zoo points rows: **16** — matches the user's screenshots exactly.
- **Installed glyphs with no TDX stock counterpart (rename-target menu), 19:** Anastomosis, BreakdownChoke, Camp, CavePearl, ClayTree, Disk, FlowstoneChoke, Flute, GypsumFlower, Karren, LowEnd, Raft, RaftCone, RimstoneDam, RimstonePool, VegetableDebris, Waterfall, WaterFlowPaleo (+ the Undefined placeholder itself).

**Winding verdict (CAL row + v1 pair):** stroke direction does **not** change rendering in this build — CW and CCW single strokes fill identically, and the consistent/inconsistent passages render the same. An inverted-area wall stroke fills the region enclosed by the stroke *plus its start→end chord*; the ponor "purple mess" was **overlapping chord-fills of multiple partial strokes**, cured by joining strokes into one outline (what the user did; the guidelines PDF's "combinato" merge + CCW rule appears to be legacy advice for older cSurvey). **Pre-processor consequence: winding normalization is unnecessary; stroke-joining is the real (optional) improvement.**

**Print-clipping caveat (user observation, zoo v3):** layers below Borders (Soil, Water/floor, Rocks, Ceiling) are **clipped to the cave-border interior in print/export** — with no enclosing `wall` border they simply don't print (designer still shows them). Line/area symbol tests must be judged in the designer or inside a drawn border. This is also a real-workflow fact: imported morphology only prints once walls enclose it.

**Soil-area brushes (v1 visual):** blocks/debris/pebbles/sand distinct; `clay` renders with the sand brush (as coded); `ice`/`snow`/`user` blank generic soil; area `water` a faint outline.

## Agreed remediation (user decisions 2026-07-19, implemented in `dev/production/tools/preprocess_tdx_csx.py`)

| Problem symbol | Decision |
|---|---|
| `debris` (point) | rename → `blocks` |
| `water-drip` | rename → `waterfall` |
| `mud` | rename → `clay` (maps; glyph pending a clay SVG) |
| `danger` / `minus` / `plus` / `plus-minus` | convert → `label` points with text `!` / `-` / `+` / `+/-` |
| `user` (point) | recover original tool name from `options` if present, else flag |
| `wall:blocks/clay/debris/ice` | rename → `wall` (recovers cave border; subtype texture lost regardless) |
| `arrow`, `water` line, `ice`/`snow`/`user` areas | left as-is, reported as warnings |
| 8 mapped-but-glyphless signs | fix by authoring gallery SVGs (no rename needed) — backlog: [custom-sign-palette.md](../backlog/custom-sign-palette.md) |

Original names are preserved as `tdxpp:<name>` markers in the item `options` string for audit. Winding normalization intentionally omitted (proven irrelevant). Acceptance: zoo v3 passed (11 transformations, counts preserved); the real ponor survey pending its raw-export recovery.

### Real-data additions (rupe_preko_vertikale, 2026-07-19 — see `dev/projects/0002-tdx-symbol-mapping/runs/2026-07-19-rupe-acceptance/`)

The user's phone has **additional TDX symbol sets** enabled, so real exports carry names beyond the stock speleo inventory. Verified in the rupe export and handled:

| Extra-set name | Kind | Handling |
|---|---|---|
| `clay-area` | area | rename → `clay` (generic rule: strip `-area` when the base is a mapped area name). NB: stock `clay` area and extra-set `clay-area` are different tools and can coexist in one sketch |
| `slope:shallow` | line | rename → `slope` (generic rule: strip `:subtype` when the base is a mapped line name; `wall:presumed` exempt) |
| `floor-step` | line | rename → `pit` (cliff-curve family) — agent default, user may veto |
| `abyss-entrance` | line | rename → `pit` — agent default, user may veto |
| `tree-trunk` | point | rename → `vegetable-debris` (maps + glyph) — agent default, user may veto |
| `breakdown-choke` | point | no action needed — maps (`BreakdownChoke=261`) and has a glyph |

Also learned: real `user` items carry **empty `options`** when the user deliberately drew with the user tool — the name-in-options recovery only applies to TopoDroid's missing-palette-tool replacement scenario. Deliberate `user` items are unmappable by design (points → X-box, lines → border, areas → soil).

## Inventory provenance

- TopoDroid stock **speleology** set (the only set installed by default), from the TopoDroid repo `symbols-git/symbols_speleo/{point,line,area}` (master, fetched 2026-07-19): 42 point / 14 line / 7 area files.
- Plus the 8 **system tools** compiled into the app (manual p.168/175, always enabled, not files): points `user`, `label`, `section`; lines `user`, `wall`, `section`; areas `user`, `water`.
- **The csx `name` attribute is the symbol's `th_name`, not its filename.** Verified deltas: file `archeo` → `th_name archeo-material`, file `paleo` → `paleo-material`; line filenames use `=` for therion's `:` (`wall=presumed` → `wall:presumed`).
- The user's phone (TopoDroid 6.4.29) also emits `overhang` lines (seen in the ponor survey) which are absent from master's speleo set — additional sets (Extra speleo, Mining, Geology, …, manual p.170) exist and overlap; the zoo covers the union of speleo + names `ConvertItem` handles.
- Palette nuance (manual p.169): a sketch item whose tool is missing from the palette is replaced by a **`user` symbol with the original tool name in its options string** — the pre-processor should inspect `options` on `user`/`u:` items before declaring them unmappable.

## Points (resolution: `label`/`section` special-cased; otherwise name minus `-`/`_` is `Enum.TryParse`d against `SignEnum`, else Undefined X-box; name discarded)

| csx `name` | Predicted outcome | Conf |
|---|---|---|
| air-draught | ✅ Sign `AirDraught` (774), orientation +90° tweak | code |
| anchor | ✅ `Anchor` (1026) | code |
| aragonite | ✅ `Aragonite` (527) | code |
| archeo-material | ✅ `ArcheoMaterial` (769) | code |
| blocks | ✅ `Blocks` (1290) | **RUN** (ponor) |
| clay | ✅ `Clay` (1285) | code |
| continuation | ✅ `Continuation` (257) | code |
| crystal | ✅ `Crystal` (528) | code |
| curtain | ✅ `Curtain` (521) | code |
| danger | ❌ Undefined X-box | code |
| debris | ❌ Undefined — **cSurvey spells the enum `Debrits` (1289)**; `debris` can never match. Pre-processor rename `debris`→`debrits` fixes it | code |
| dig | ✅ `Dig` (773) | code |
| entrance | ✅ `Entrance` (263) | code |
| flowstone | ✅ `FlowStone` (513) | code |
| gradient | ✅ `Gradient` (786) | code |
| guano | ✅ `Guano` (1287) | code |
| gypsum | ✅ `Gypsum` (530) | code |
| helictite | ✅ `Helictite` (526) | code |
| ice | ✅ `Ice` (1281) | code |
| label *(system)* | ✅ `cItemText`, text preserved | **RUN** (ponor) |
| minus | ❌ Undefined | code |
| moonmilk | ✅ `Moonmilk` (514) | code |
| mud | ❌ Undefined | code |
| narrow-end | ✅ `NarrowEnd` (258) | code |
| paleo-material | ✅ `PaleoMaterial` (770) | code |
| pebbles | ✅ `Pebbles` (1284) | code |
| pillar | ✅ `Pillar` (519) | code |
| plus | ❌ Undefined | code |
| plus-minus | ❌ Undefined | code |
| popcorn | ✅ `Popcorn` (523) | code |
| root | ✅ `Root` (772) | code |
| sand | ✅ `Sand` (1288) | code |
| scallop | ✅ `Scallop` (534) | code |
| section *(system)* | ✅ `cItemCrossSection` + nested conversion — **excluded from zoo v1**: a synthetic section point without a well-formed nested `<crosssection>` risks a fatal load error (`<plan>` construction is unguarded); test with a real phone-drawn x-section in a dedicated run | code |
| sink | ✅ `Sink` (782) | code |
| snow | ✅ `Snow` (1282) | code |
| soda-straw | ✅ `SodaStraw` (522) | code |
| spring | ✅ `Spring` (781) | code |
| stalactite | ✅ `Stalactite` (515) | code |
| stalagmite | ✅ `Stalagmite` (517) | code |
| user *(system)* | ❌ Undefined (check `options` for the original tool name) | **RUN** (ponor) |
| wall-calcite | ✅ `WallCalcite` (529) | code |
| water | ✅ `Water` (1283) | code |
| water-drip | ❌ Undefined — no drip in `SignEnum`; nearest semantic neighbours are all wrong. Long-term: extend enum (append-only) | **RUN** (ponor) |
| water-flow | ✅ `WaterFlow` (777), orientation +90° tweak | code |

Unused on the cSurvey side (no TDX stock counterpart): `Stalactites/Stalagmites/Pillars` (plural variants), `BreakdownChoke`, `ClayChoke`, `FlowstoneChoke`, `LowEnd`, `CavePearl`, `Disk`, `Anastomosis`, `Karren`, `Flute`, `RaftCone`, `ClayTree`, `RimstonePool/Dam`, `VegetableDebris`, `AirDraughtSummer/Winter`, `WaterFlowIntermittent/Paleo`, `Waterfall`, `IceStalactite/Stalagmite/Pillar`, equipment set (`Camp`…`Handrail`), `Raft`, `Rock` — candidates as rename **targets** for the pre-processor or for a richer TDX custom palette.

## Lines (hardcoded `Select Case`; unknown → generic border line on Borders layer, name lost)

| csx `name` | Predicted outcome | Conf |
|---|---|---|
| arrow | ⚠ falls through to **generic Borders border** — semantically wrong (it's an arrow) | code |
| border | ✅ Borders border line | code |
| ceiling-meander | ✅ Ceiling `CreateCeilingMeander` | code |
| chimney | ✅ Ceiling `CreateCeilingCliffCurve` | code |
| floor-meander | ✅ Water/floor `CreateMeander` | code |
| overhang | ✅ Water/floor `CreateOverhangCurve` (layer 2 — placement debatable but intended) | **RUN** (ponor) |
| pit | ✅ Water/floor `CreateCliffCurve` | code |
| presumed | ✅ Borders `CreatePresumedBorder` | code |
| rock-border | ✅ Rocks `CreateRockArea` (line → **area**) | code |
| section *(system)* | ✅ placeholder presumed-border named "xsection …" (author's noted simplification, :226-235) | code |
| slope | ✅ Water/floor `CreateLevelCurve` | code |
| user *(system)* | ⚠ generic Borders border | code |
| wall *(system)* | ✅ `outline=1/-1` → **inverted cave-border area** (per stroke; `-1` → MergeMode Subtract); other outline → plain border. ⚠ **Winding not normalized** — CW strokes invert the fill (run-1 finding 2); zoo carries a CW/CCW calibration pair | **RUN** (ponor) |
| wall:blocks | ⚠ **falls through to generic border line** — loses wall-ness entirely (no cave border, no fill). Only bare `wall` and `wall:presumed` are special-cased. Pre-processor rename `wall:*`→`wall` recovers the border | code |
| wall:clay | ⚠ same as wall:blocks | code |
| wall:debris | ⚠ same | code |
| wall:ice | ⚠ same | code |
| wall:presumed | ✅ Borders `CreatePresumedCaveBorder` (inverted area) | **RUN** (ponor) |
| water | ⚠ generic Borders border — **not** water (only `water-flow` is mapped) | code |
| water-flow | ✅ Water/floor border, blue pen (cSurvey has no waterway line type — author's comment) | code |

## Areas (hardcoded; unknown → generic Soil, name lost)

| csx `name` | Predicted outcome | Conf |
|---|---|---|
| blocks | ✅ Soil `CreateBigDebritsSoil` | code |
| clay | ⚠ maps to `CreateSandSoil` — **rendered as sand**, semantically off | code |
| debris | ✅ Soil `CreateSmallDebritsSoil` | code |
| ice | ⚠ generic Soil | code |
| pebbles | ✅ Soil `CreatePebblesSoil` | code |
| sand | ✅ Soil `CreateSandSoil` | code |
| snow | ⚠ generic Soil | code |
| user *(system)* | ⚠ generic Soil | code |
| water *(system)* | ✅ Water/floor `CreateWaterArea` | code |

## Score (predicted)

Points: 36 ✅ / 7 ❌ (+ `user`) · Lines: 12 ✅ / 7 ⚠ · Areas: 5 ✅ / 4 ⚠. The ❌/⚠ set is small and stable — a rename map (`debris`→`debrits`, `wall:*`→`wall`) plus winding normalization recovers the biggest losses; the rest (danger, mud, minus, plus, plus-minus, water-drip, arrow, water-line, ice/snow areas) need either a chosen rename target from the unused-enum list above or a TDX-palette exclusion.
