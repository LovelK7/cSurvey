# TDX → cSurvey processing protocol (closing report of the symbol-mapping brief)

**Status: OPERATIONAL** — brief [tdx-symbol-mapping-brief.md](../projects/0002-tdx-symbol-mapping/brief.md) closed 2026-07-26 with user sign-off after full acceptance on real surveys (`ponor_rupa_babi_pod_kucu`, `rupe_preko_vertikale`; runs in [dev/projects/0002-tdx-symbol-mapping/runs/](../projects/0002-tdx-symbol-mapping/runs/)).

## What was built

| Piece | File | Role |
|---|---|---|
| Inspector | `dev/production/tools/inspect_survey.py` | read-only stats/diff report for any `.csz`/`.csx` (Stage 0) |
| Pre-processor | `dev/production/tools/preprocess_tdx_csx.py` | rewrites a raw TDX export so symbols survive the import (renames, label conversions, stroke reversal, orientation) |
| Mapping config | `dev/production/tools/tdx-mapping.json` | **the user-owned mapping**: per-symbol `to`/`label`/`leave` + `reverse`/`orientation`, generic subtype/`-area` stripping, and `postimport` switches |
| Mapping workbench | `dev/production/tools/make_signs_catalog.py` → `tdx-mapping-workbench.html` + `cs-targets.html` | visual editor: every TDX tool (icons rendered from TopoDroid's own symbol files, all 9 sets + system tools) → numbered cSurvey targets; exports the json |
| Post-import fixer | `dev/production/tools/fix_imported_linetypes.py` | fixes what import cannot express: spline linetypes (decoration rendering), non-standard water brush, per-sign/label sizes |
| Signs pack | `dev/production/tools/signs-pack/*.svg` | 8 glyphs for mapped-but-artwork-less signs; installed into `C:\csurvey64\Objects\Cliparts\Signs\` |
| Knowledge | [tdx-symbol-matrix.md](tdx-symbol-matrix.md) | run-verified symbol matrix (mapping + glyph coverage + remediation decisions) |

## Key findings (details in the matrix and RUNLOGs)

- Conversion is name-driven and *fixed*: 13 line targets, 6 area targets, points via `SignEnum` (name minus dashes); unknown names degrade silently and irrecoverably (original name discarded).
- Rendering has its own gates: signs need a gallery SVG (X-box otherwise); line decorations need splines — cSurvey stamps decorations per polyline segment without accumulating distance ([cClipartOnPath.vb:88-99](../../cSurveyPC/cClipartOnPath.vb#L88)), so dense TopoDroid polylines render plain (upstream fix candidate; worked around post-import).
- `water-flow`-named points get a built-in +90° orientation tweak at import; sizes with TDX scale 0 are not applied — both handled via config.
- Winding/orientation of wall strokes is irrelevant to fill rendering; the historical "draw CCW" guideline is legacy advice.

## The standing protocol (routine survey)

1. **Phone:** draw in TopoDroid preferring green-verdict tools (see workbench); export **one** csx (it contains both plan and profile) into `G:\My Drive\Share\TDX`. **Also export the project ZIP archive every time** (Survey window → menu → Archive) — since TopoDroid 6.4.99 the zip is the durable artifact: it always carries the full sketch and survives app-version churn (see step 1b).

   **1b. If the csx is missing/0-byte or the sketch vanished (TopoDroid ≥6.4.98 bugs):** regenerate the csx from the project zip — double-click `recover_tdx.bat` in the TDX folder (processes every zip there), or drag specific zips onto it; equivalently `python dev\production\tools\tdx_zip_to_csx.py <zip|folder>`. It writes `<survey>_recovered.csx` **and already runs step 2** (`<survey>_recovered_pp.csx` → continue at step 3). Background + validation: [projects/0003-tdx-zip-recovery](../projects/0003-tdx-zip-recovery/brief.md). Export-bundle zips (csx/dxf/csv collections) are not project archives and are skipped.
2. **Pre-process:** double-click **`preprocess_tdx.bat`** in the TDX folder (preprocesses every raw
   TopoDroid csx in the folder tree; `_pp` outputs and post-import saves are skipped automatically),
   or drag specific `.csx` files onto it. Terminal equivalent (takes files or a folder):
   `python dev\production\tools\preprocess_tdx_csx.py "G:\My Drive\Share\TDX\<survey>.csx"`
   → `<survey>_pp.csx` + a report; read the ⚠ warnings (they list what will degrade).
3. **Import:** open `<survey>_pp.csx` in cSurvey (fix-up chain + therion calculation run automatically), then **Save As** your working file.
4. **Post-fix:**
   `python dev\production\tools\fix_imported_linetypes.py <saved>.csx`
   → `<saved>_lt.csx`; open that — it is the finished import (decorated lines, sizes, water brush). Continue mapping work in cSurvey from here.
5. **Optional:** `inspect_survey.py --json` snapshots before/after any step for diffable ground truth (protocol: [pipeline-a-instrumented-run.md](methods/instrumented-run.md)).

**Tuning the mapping:** edit `dev/production/tools/tdx-mapping.json` directly, or visually — `python dev\production\tools\make_signs_catalog.py`, open `tdx-mapping-workbench.html` (+ `cs-targets.html` side by side), type target numbers (`105 r`, `12 o90`, `label:!`, `leave`), export, replace the json. Sizes/water/splines live in the json's `postimport` section. Re-run steps 2–4 after changes.

## Known limits

- Deliberate `user` tools are unmappable by design (X-box/plain line/plain soil) — prefer named tools on the phone.
- Designer-only cSurvey tools (presumed line variants, faults, concretion, "Acqua (non standard)"… — listed at the bottom of `cs-targets.html`) are unreachable at import; the post-import fixer covers water, others need manual re-typing or a future generalized re-typer.
- After a cSurvey upgrade, re-copy the signs pack (install dir may be overwritten) and re-scan (`make_signs_catalog.py`).
- Upstream fix candidates (parked behind the DevExpress build): accumulate decoration distance across segments; spline linetype in `ConvertItem`; preserve the therion name on unmapped items; new enum members (real water-drip, danger, ±).
