# Implementation log: TDX → cSurvey symbol mapping

Brief: [brief.md](brief.md)

> Backfilled 2026-07-26 during the dev/ reorg from the roadmap and the run logs — this project predates
> the logging convention, so entries are reconstructed. The runs under `runs/` hold the contemporaneous detail.

---

### 2026-07-19 — opened after the instrumented import surfaced two limits (agent) →

- **Did:** the first real instrumented import (project 0001's instrument) validated Pipeline A but
  exposed two conversion limits — unmapped point symbols become irrecoverable X-boxes (therion name
  discarded), and wall-stroke winding isn't normalized. Both are **pre-import** problems.
- **Result:** brief written with 5 phases (inventory → symbol-zoo → matrix → pre-processor → TDX palette).
- **Evidence:** [runs/2026-07-19-ponor-import/RUNLOG.md](runs/2026-07-19-ponor-import/RUNLOG.md)

### 2026-07-19 to 07-21 — inventory, symbol-zoo, matrix (agent) ✅

- **Did:** mined the TopoDroid manuals + symbol repo for the full stock symbol set; built a synthetic
  symbol-zoo csx (one item per name, distinctive geometry, CW/CCW wall calibration) and imported it.
- **Result:** all 74 mapping predictions confirmed; rendering layer resolved (glyph coverage comes from
  the installed build's sign-SVG gallery; winding proven irrelevant to fill). Matrix published.
- **Evidence:** [runs/2026-07-19-symbol-zoo/](runs/2026-07-19-symbol-zoo/RUNLOG.md), [tdx-symbol-matrix.md](../../production/tdx-symbol-matrix.md)

### 2026-07-21 to 07-26 — pre-processor, user-owned mapping, workbench (agent + user) ✅

- **Did:** built `preprocess_tdx_csx.py` (renames, label conversions, stroke reversal, orientation) driven
  by a user-editable `tdx-mapping.json`; built the visual workbench (`make_signs_catalog.py`) and the
  signs pack for glyphless-but-mapped signs.
- **Result:** points 100% correct on real surveys; soil areas correct. **Lines rendered plain** — flagged
  for root-cause.
- **Evidence:** [runs/2026-07-19-rupe-acceptance/RUNLOG.md](runs/2026-07-19-rupe-acceptance/RUNLOG.md) (step-02b)

### 2026-07-26 — line-decoration root cause + post-import fixer (agent + user) ✅

- **Did:** native-vs-imported XML diff isolated the cause; built `fix_imported_linetypes.py`.
- **Result:** **root cause = `linetype`** — `ConvertItem` hardcodes `Lines`; cSurvey stamps pen decorations
  per polyline segment *without accumulating distance* ([cClipartOnPath.vb:88-99](../../../cSurveyPC/cClipartOnPath.vb#L88)),
  so dense TopoDroid strokes never decorate. Splines take the curve branch and do. Post-import fixer flips
  `linetype` 0→1; user confirmed "now it works as expected". (Upstream one-liner candidate, parked behind the DevExpress build.)
- **Evidence:** [runs/2026-07-19-rupe-acceptance/RUNLOG.md](runs/2026-07-19-rupe-acceptance/RUNLOG.md) (step-03b)

### closed ✅ 2026-07-26 — user sign-off on real data

- **Outputs — Production:** `preprocess_tdx_csx.py`, `fix_imported_linetypes.py`, `make_signs_catalog.py`,
  `tdx-mapping.json`, `signs-pack/` → [`production/tools/`](../../production/tools/); the standing SOP
  [`tdx-processing-protocol.md`](../../production/tdx-processing-protocol.md).
- **Outputs — Reference/knowledge:** [`tdx-symbol-matrix.md`](../../production/tdx-symbol-matrix.md).
- **Follow-ups:** custom-sign-palette ([backlog](../../backlog/custom-sign-palette.md)); upstream fixes
  (accumulate decoration distance, spline linetype in `ConvertItem`, preserve therion name, new enum members)
  parked behind the DevExpress build; **next frontier: the headless driver / reflection hypothesis (→ 0003).**
