# Run log: rupe_preko_vertikale — pre-processor acceptance on real data

Brief: [dev/projects/0002-tdx-symbol-mapping/brief.md](../../brief.md) (phase 4 acceptance) ·
Matrix: [dev/production/tdx-symbol-matrix.md](../../../../production/tdx-symbol-matrix.md)
Fixture: `rupe_preko_vertikale-1p.csx` — **real TopoDroid 6.4.29 export**, drawn by the
user specifically with "most of the usually used symbols" for testing.
Raw snapshot IN this dir (lesson of run 1): `step-00-raw-export.csx`,
SHA256 `23D172C74EB9A1F222C02573E30ACFE05ED52119FE824AB7C6A46CEF95B900D2`.

---

## step-00 — raw baseline (2026-07-19, agent) ✅

[step-00-raw-export.json](step-00-raw-export.json): raw TopoDroid verdict; 4 shots +
34 splays; **55 flat items** (plan 20, profile 35), 823 points all unbound.

**New knowledge from first real-data contact (docs/matrix corrected):**

- The user's phone has **additional symbol sets** enabled — real exports carry
  names outside the stock speleo inventory: `clay-area` (area), `slope:shallow`,
  `floor-step`, `abyss-entrance` (lines), `tree-trunk`, `breakdown-choke` (points).
- `clay` and `clay-area` are DIFFERENT tools (stock vs extra set) and can coexist;
  `-area`-suffixed and `:subtype` names silently degrade in cSurvey's converter
  (only `wall:presumed` is a mapped subtype).
- `breakdown-choke` maps (`BreakdownChoke=261`) and has a glyph — free win.
- Real `user` items (3 points + 5 lines here) have **empty options** — the
  name-in-options recovery only applies to the palette-replacement scenario,
  not to deliberately-used user tools. These stay X-boxes / border lines.

## step-01 — pre-processed (2026-07-19, agent) ✅

`preprocess_tdx_csx.py` (extended with: generic `:subtype` strip for known line
bases, generic `-area` strip for known area bases, `floor-step`→`pit`,
`abyss-entrance`→`pit`, `tree-trunk`→`vegetable-debris` — the last three are
agent defaults, user may veto) → [step-01-preprocessed.csx] +
[step-01-preprocessed.json](step-01-preprocessed.json).
**19 transformations**: clay-area→clay ×4, water-drip→waterfall ×4,
debris→blocks ×5, slope:shallow→slope, floor-step→pit ×2, abyss-entrance→pit,
tree-trunk→vegetable-debris, danger→label "!" ×1. Warnings: 3 unrecoverable
`user` points. Item count 55 preserved.

## step-02 — import (pending: user)

Open `step-01-preprocessed.csx` in cSurvey (fix-up chain runs), Save As
`step-02-after-import.csx` here. Optionally also import the RAW
`step-00-raw-export.csx` in a second window for a side-by-side X-box
comparison. Expected in the pre-processed import:

- X-box points only: user ×3, anchor ×2*, clay-point ×1* + clay-as-mud n/a —
  (*anchor/clay map correctly; their X-boxes disappear once the signs-pack
  SVGs are installed — see step-03).
- water-drips render as waterfall symbols; debris as blocks; danger as "!";
  breakdown-choke, dig, entrance, continuation, air-draught, blocks as real
  glyphs; clay areas as sand-brush soil; pit/slope/chimney lines on their
  proper layers.

## step-03 — signs pack (agent) — see dev/production/tools/signs-pack/

8 SVGs for the mapped-but-glyphless signs (anchor, archeo-material, clay,
gradient, ice, sand, snow, water). Install: copy into
`C:\csurvey64\Objects\Cliparts\Signs\` (cSurvey restart likely needed —
gallery index is built once per session). After install + reopening the
step-02 file, anchor/clay X-boxes should render.

## step-02b — redrawn export, user mapping, import (2026-07-23/26)

User redrew the survey (`rupe_preko_vertikale-1s.csx` → `step-00b-raw-export.csx`,
SHA256 `A5A6FFE7…FD1F1A`, 67 items) and produced their own mapping via the
workbench (`dev/production/tools/tdx-mapping.json`: 26 transformations incl. anchor→label
"f", debris→breakdown-choke, water-drip→waterflow, chimney/abyss-entrance→
overhang). Imported `step-01b-preprocessed.csx`, saved → `step-02b-after-import.csx`.

**Result — points: 100% correct** (verified in XML: waterflow×4,
breakdownchoke×6, stalactite×4, stalagmite×2, vegetabledebris, blocks×5,
labels "f"×2/"!"×1; Undefined only on the 3 deliberate `user` points).
Soil areas correct. **Lines: mapping is DATA-CORRECT but renders plain.**
XML proof: Water/floor holds pen=5 (CliffDownPen/Scarpata) ×5, pen=7
(GradientDownPen) ×5, pen=12 (OverhangDownPen) ×3 — exactly the pens the
toolbar factories assign ([cLayerWaterAndFloorMorphologies.vb:46-86](../../../../../cSurveyPC/cLayerWaterAndFloorMorphologies.vb#L46)).
Yet the designer shows plain thin lines, no triangles/ticks.

Investigated and excluded: designstyle (=0=full Design mode), pens gallery
(not used — decorations are built-in cliparts, `modPenClipart`, stamped along
the path in [cPen.vb:1034-1100](../../../../../cSurveyPC/cPen.vb#L1034) /
`cClipartOnPath`). Decoration size/spacing scale with a design-properties
zoom factor — suspicion: decoration geometry vs. short lines in a small cave,
or an item-level attribute difference vs natively-drawn lines (ConvertItem
forces `LineType=Lines`).

**Next: the 30-second discriminating experiment** — in the imported survey,
draw ONE native Scarpata next to an imported pit line (similar length), save
as `step-03b-native-compare.csx`. Same view: if native shows triangles and
imported doesn't → item-level cause, and the XML diff of the two items
pinpoints the attribute; if BOTH plain → survey/scale-level cause
(design properties), not the import.

## step-03b — native-compare → ROOT CAUSE FOUND (2026-07-26)

User drew a native Scarpata into the imported survey
(`step-03b-native-compare.csx`). XML diff against the imported pit lines:
identical type/category/pen — **the only rendering-relevant difference is
`linetype`: native = 1 (Splines), imported = 0 (Lines)**, hardcoded by
`ConvertItem` (`oItem.LineType = LineTypeEnum.Lines`).

Mechanism (code-confirmed): pen decorations on pure polyline paths are
stamped **per segment, only when a single segment exceeds the decoration
width — distance does not accumulate across segments**
([cClipartOnPath.vb:88-99](../../../../../cSurveyPC/cClipartOnPath.vb#L88),
`pDrawClipartOnLines`). TopoDroid strokes are dense flattened polylines
(10–30 cm segments) → no segment ever qualifies → plain lines. Splines fail
`pIsPathLine` → curve branch → decorations render. The zoo's synthetic lines
had metre-long segments, which is why they decorated — a happy-path blind
spot real data exposed. Arguably a cSurvey rendering bug (any dense polyline
from any source is affected); upstream one-liners: accumulate distance in
`pDrawClipartOnLines`, or make `ConvertItem` create splines.

## step-01c — refinement round (2026-07-26, agent) — user feedback after linetype fix

Linetype fix **confirmed working by user** ("now it works as expected").
Three refinements implemented:
1. **Water area → "Acqua (non standard)"**: designer-only (import can only
   produce the standard water brush), so implemented as a post-import rule —
   `fix_imported_linetypes.py` now reads the mapping file's new `postimport`
   section (`spline_linetypes`, `nonstandard_water`) and swaps brush type
   2→6 on imported water areas. Also: system tools (incl. area `water`) had
   no workbench rows (no files in symbols-git) — synthesized rows added.
2. **Chimney decorations should face outward**: pre-processor gains
   per-mapping `"reverse": true` (flips stroke direction → pen stamps the
   other side); applied to chimney→overhang. Workbench input flag: `105 r`.
3. **Water-drip arrow should point down**: root cause — our rename to
   `waterflow` (no dash) skipped ConvertItem's built-in +90° orientation
   tweak for `water-flow`. Mapping changed to `water-flow` (dash); if still
   wrong, per-mapping `"orientation": NN` / workbench flag `oNN` forces it.

`step-01c-preprocessed.csx` generated (27 transformations: chimney reversed,
water-drip→water-flow ×4, rest as before). Awaiting import → `step-02c` →
post-import fixer → visual check.

## CLOSED — acceptance complete (2026-07-26)

d-series (orientation 180 on drips, size rules in `postimport`) accepted by
the user: drips down, "!" and entrance at Big, air-draught/stalactites/
stalagmites at Medium, chimney marks outward, non-standard water brush,
decorated lines. **The full pipeline (mapping json → pre-process → import →
post-fix) is the standing workflow** — documented in
[dev/production/tdx-processing-protocol.md](../../../../production/tdx-processing-protocol.md).
Brief closed.

## step-04b — post-import linetype fix (2026-07-26, agent) — superseded by d-series, kept for history

New tool `dev/production/tools/fix_imported_linetypes.py`: flips `linetype` 0→1 on
freehand-line items carrying the TopoDroid import datarow stamp, in a
post-import .csx save. Applied to step-03b → `step-04b-linetype-fix.csx`
(**20 lines switched**). Points untouched → geometry constrained, warping
unaffected. **User: open step-04b-linetype-fix.csx — decorations should now
render on all imported lines.** If confirmed: pipeline becomes
pre-process → import → save → linetype-fix → reopen; note as candidate
upstream fix behind the DevExpress build.
