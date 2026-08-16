# production/ — what we run routinely

The "shipped" surface of the fork: the tools, procedures, and config we run on **real surveys**,
plus the run-verified knowledge they depend on. Everything here has been through a project's
validation and was accepted on real data — if something is still being figured out, it lives in a
[projects/](../projects/README.md) folder, not here.

## The standing procedure

**[tdx-processing-protocol.md](tdx-processing-protocol.md)** — the step-by-step SOP for turning a
phone-drawn TopoDroid survey into a finished cSurvey import. Operational since 2026-07-26. Start here
for routine survey processing.

## Toolkit (`tools/`)

| Tool | Role | Run when |
|---|---|---|
| [`READ ME FIRST - process a survey.txt`](tools/READ%20ME%20FIRST%20-%20process%20a%20survey.txt) (copied into the TDX folder) | plain-language, jargon-free operator checklist for the whole routine (drag-drop, `_pp`/`_lt` endings, black-window messages) | the human starting point — read before running anything |
| [`inspect_survey.py`](tools/inspect_survey.py) | read-only stats/diff report for any `.csz`/`.csx` (Stage 0) — see [tools/README.md](tools/README.md) | inspecting or diffing any survey, before/after any step |
| [`preprocess_tdx_csx.py`](tools/preprocess_tdx_csx.py) | rewrites a raw TDX export so symbols survive import (renames, label conversions, stroke reversal, orientation) | on the raw phone export, before opening in cSurvey |
| [`fix_imported_linetypes.py`](tools/fix_imported_linetypes.py) (drag-drop: `fix_tdx.bat`) | post-import fixer for what import can't express (**spline linetypes so slope/gradient/etc. line decorations render**, non-standard water brush, sign/label sizes) | right after **Save As**, before mapping — then map in the `_lt.csx` |
| [`make_signs_catalog.py`](tools/make_signs_catalog.py) → `tdx-mapping-workbench.html` + `cs-targets.html` | visual mapping editor: every TDX tool → numbered cSurvey targets; exports the mapping json | when tuning the mapping |
| [`tdx-mapping.json`](tools/tdx-mapping.json) | **the user-owned mapping** the pre/post-processors read | edit to change how symbols map |
| [`signs-pack/`](tools/signs-pack/) | 8 SVG glyphs for mapped-but-artwork-less signs; installed into cSurvey's Signs gallery | after a cSurvey upgrade (re-copy) |

## Methods (`methods/`)

Reusable procedures that aren't a single script:

- [`methods/instrumented-run.md`](methods/instrumented-run.md) — the save-after-each-step protocol for
  producing diffable ground truth from a manual cSurvey session. The template for any new run under a
  project's `runs/`.

## Reference knowledge produced here

- [`tdx-symbol-matrix.md`](tdx-symbol-matrix.md) — the run-verified TDX symbol → cSurvey outcome matrix
  the SOP and pre-processor depend on. (Produced by project 0002; kept beside the tools that consume it.)

---

*Provenance:* this toolkit was built and validated by [project 0002](../projects/0002-tdx-symbol-mapping/brief.md).
Upstream fix candidates it identified (parked behind the DevExpress build) are noted at the bottom of the
protocol and in the matrix.
