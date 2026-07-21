# Backlog: custom TDX↔cSurvey symbol palette from SVG icons

**Status: idea, parked** (user request 2026-07-19, during the symbol-zoo campaign).
Grounding: [dev/docs/tdx-symbol-matrix.md](../docs/tdx-symbol-matrix.md) ("Rendering layer" section).

## The insight

Both ends of the pipeline are extensible with plain content files — no builds:

- **cSurvey side:** sign glyphs are SVG files carrying a `csurvey:sign="<enum value>"`
  attribute in `<install>\Objects\Cliparts\Signs\` (46 shipped in the 2025-12 build).
  Dropping a new SVG there gives any `SignEnum` value artwork instantly
  (index built at runtime, `cSignsImportHelper.CreateIndex`).
- **TopoDroid side:** drawing tools are plain text files in the app's
  `point/`/`line/`/`area/` symbol dirs; custom sets install via the PALETTE menu,
  and the project zip can carry them (`points.zip`/`lines.zip`/`areas.zip`).

So a **matched pair** — a TDX custom symbol set and a cSurvey glyph pack, agreeing on
names/enum values — would give the club a shared, arbitrary symbol vocabulary that
survives the phone→PC trip with zero code changes on either side.

## What it would take

1. **Near-term, no build (partially done):** author the 8 missing glyph SVGs for
   signs that already map but lack artwork in the installed build
   (anchor, archeo-material, clay, gradient, ice, sand, snow, water) — clone the
   structure of an existing gallery SVG (e.g. `blocks.svg`), set `csurvey:sign`
   to the right value, drop into the install dir. Instantly upgrades those 8
   from X-box to rendered symbol; imported data is already correct.
2. **Truly new symbols (needs one source change):** a genuinely new symbol
   (e.g. a real *water-drip*) needs a new `SignEnum` member — append-only, never
   renumber (file-format invariant), so it is a one-line change per symbol +
   glyph SVG + a `ConvertItem`/TryParse-compatible name. Parked behind the
   DevExpress build.
3. **TDX custom set:** restrict/extend the phone palette to the club's agreed
   vocabulary (matrix ✅✅ set + pack from 1/2); pre-processor
   (`dev/tools/preprocess_tdx_csx.py`) remains the safety net for old surveys.

## Open questions

- SVG authoring conventions the gallery expects (viewBox size, stroke widths,
  the `csurvey` namespace attributes) — derive from shipped files before
  authoring.
- Whether glyph SVGs dropped into the install survive cSurvey upgrades
  (install-dir content — likely overwritten/merged by installer; keep the pack
  in the repo and re-copy after upgrades).
- Long-term: propose the missing speleo symbols (drip, danger, ±) upstream to
  cSurvey so the enum grows officially.
