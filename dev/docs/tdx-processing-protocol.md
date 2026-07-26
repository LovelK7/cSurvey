# TDX → cSurvey processing protocol (closing report of the symbol-mapping brief)

**Status: OPERATIONAL** — brief [tdx-symbol-mapping-brief.md](../tasks/tdx-symbol-mapping-brief.md) closed 2026-07-26 with user sign-off after full acceptance on real surveys (`ponor_rupa_babi_pod_kucu`, `rupe_preko_vertikale`; runs in [dev/runs/](../runs/)).

## What was built

| Piece | File | Role |
|---|---|---|
| Inspector | `dev/tools/inspect_survey.py` | read-only stats/diff report for any `.csz`/`.csx` (Stage 0) |
| Pre-processor | `dev/tools/preprocess_tdx_csx.py` | rewrites a raw TDX export so symbols survive the import (renames, label conversions, stroke reversal, orientation) |
| Mapping config | `dev/tools/tdx-mapping.json` | **the user-owned mapping**: per-symbol `to`/`label`/`leave` + `reverse`/`orientation`, generic subtype/`-area` stripping, and `postimport` switches |
| Mapping workbench | `dev/tools/make_signs_catalog.py` → `tdx-mapping-workbench.html` + `cs-targets.html` | visual editor: every TDX tool (icons rendered from TopoDroid's own symbol files, all 9 sets + system tools) → numbered cSurvey targets; exports the json |
| Post-import fixer | `dev/tools/fix_imported_linetypes.py` | fixes what import cannot express: spline linetypes (decoration rendering), non-standard water brush, per-sign/label sizes |
| Signs pack | `dev/tools/signs-pack/*.svg` | 8 glyphs for mapped-but-artwork-less signs; installed into `C:\csurvey64\Objects\Cliparts\Signs\` |
| Knowledge | [tdx-symbol-matrix.md](tdx-symbol-matrix.md) | run-verified symbol matrix (mapping + glyph coverage + remediation decisions) |

## Key findings (details in the matrix and RUNLOGs)

- Conversion is name-driven and *fixed*: 13 line targets, 6 area targets, points via `SignEnum` (name minus dashes); unknown names degrade silently and irrecoverably (original name discarded).
- Rendering has its own gates: signs need a gallery SVG (X-box otherwise); line decorations need splines — cSurvey stamps decorations per polyline segment without accumulating distance ([cClipartOnPath.vb:88-99](../../cSurveyPC/cClipartOnPath.vb#L88)), so dense TopoDroid polylines render plain (upstream fix candidate; worked around post-import).
- `water-flow`-named points get a built-in +90° orientation tweak at import; sizes with TDX scale 0 are not applied — both handled via config.
- Winding/orientation of wall strokes is irrelevant to fill rendering; the historical "draw CCW" guideline is legacy advice.

## The standing protocol (routine survey)

1. **Phone:** draw in TopoDroid preferring green-verdict tools (see workbench); export **one** csx (it contains both plan and profile) into `G:\My Drive\Share\TDX`.
2. **Pre-process:**
   `python dev\tools\preprocess_tdx_csx.py "G:\My Drive\Share\TDX\<survey>.csx"`
   → `<survey>_pp.csx` + a report; read the ⚠ warnings (they list what will degrade).
3. **Import:** open `<survey>_pp.csx` in cSurvey (fix-up chain + therion calculation run automatically), then **Save As** your working file.
4. **Post-fix:**
   `python dev\tools\fix_imported_linetypes.py <saved>.csx`
   → `<saved>_lt.csx`; open that — it is the finished import (decorated lines, sizes, water brush). Continue mapping work in cSurvey from here.
5. **Optional:** `inspect_survey.py --json` snapshots before/after any step for diffable ground truth (protocol: [pipeline-a-instrumented-run.md](../tasks/pipeline-a-instrumented-run.md)).

**Tuning the mapping:** edit `dev/tools/tdx-mapping.json` directly, or visually — `python dev\tools\make_signs_catalog.py`, open `tdx-mapping-workbench.html` (+ `cs-targets.html` side by side), type target numbers (`105 r`, `12 o90`, `label:!`, `leave`), export, replace the json. Sizes/water/splines live in the json's `postimport` section. Re-run steps 2–4 after changes.

## Known limits

- Deliberate `user` tools are unmappable by design (X-box/plain line/plain soil) — prefer named tools on the phone.
- Designer-only cSurvey tools (presumed line variants, faults, concretion, "Acqua (non standard)"… — listed at the bottom of `cs-targets.html`) are unreachable at import; the post-import fixer covers water, others need manual re-typing or a future generalized re-typer.
- After a cSurvey upgrade, re-copy the signs pack (install dir may be overwritten) and re-scan (`make_signs_catalog.py`).
- Upstream fix candidates (parked behind the DevExpress build): accumulate decoration distance across segments; spline linetype in `ConvertItem`; preserve the therion name on unmapped items; new enum members (real water-drip, danger, ±).
