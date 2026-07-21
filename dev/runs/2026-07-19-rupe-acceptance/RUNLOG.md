# Run log: rupe_preko_vertikale — pre-processor acceptance on real data

Brief: [dev/tasks/tdx-symbol-mapping-brief.md](../../tasks/tdx-symbol-mapping-brief.md) (phase 4 acceptance) ·
Matrix: [dev/docs/tdx-symbol-matrix.md](../../docs/tdx-symbol-matrix.md)
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

## step-03 — signs pack (agent) — see dev/tools/signs-pack/

8 SVGs for the mapped-but-glyphless signs (anchor, archeo-material, clay,
gradient, ice, sand, snow, water). Install: copy into
`C:\csurvey64\Objects\Cliparts\Signs\` (cSurvey restart likely needed —
gallery index is built once per session). After install + reopening the
step-02 file, anchor/clay X-boxes should render.

## step-04 — verdict (pending: agent after user's step-02 save + screenshots)
