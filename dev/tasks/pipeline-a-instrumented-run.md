# Protocol: instrumented Pipeline A run (first real TopoDroid import)

**Status:** ✅ **RUN COMPLETE 2026-07-19 — Pipeline A validated end-to-end** (import 10/10 predictions, binding real, warping real; two pre-import-fixable limitations found). Verdict and per-step evidence: [RUNLOG](../runs/2026-07-19-ponor-import/RUNLOG.md). This document remains the template for future runs (new dated dir under `dev/runs/`). ⚠ The pristine raw export was lost in a file move afterwards — recovery pending (see RUNLOG incident note); snapshot the raw input INTO the run dir at step-00 in future runs.
**Prerequisites:** all verified present on this machine 2026-07-19 — see §2.
**Roles:** the **user** performs UI steps in cSurvey; a **Claude agent** generates/diffs reports, verifies predictions, and logs findings. Either can read this cold and know exactly where the run stands from [dev/runs/2026-07-19-ponor-import/RUNLOG.md](../runs/2026-07-19-ponor-import/RUNLOG.md).

---

## 1. What this run is for

Pipeline A ("the surveyor drew on the phone — cSurvey's import chain does the rest") was **confirmed on data** on 2026-07-18: the first real TopoDroid export (`dev/example/ponor_rupa_babi_pod_kucu-1p.csx`) carries a 34-item phone sketch. What has *never* been observed is the import chain actually running on a real file. This run:

1. **Exercises the whole TopoDroid → cSurvey import end-to-end** on the released binary, producing machine-readable before/after evidence instead of prose notes.
2. **Tests the instrumentation protocol itself** — save-after-every-step + inspector diff — which is the standing method for all future manual ground-truth work (per [roadmap 2026-07-16](../docs/roadmap-decisions.md): *"a diff of the serialized survey is a spec; notes about a UI session rot"*).
3. **Validates or refutes the reconstructed docs** ([topodroid-import.md](../docs/topodroid-import.md), [topodroid-zip-and-csx-format.md](../docs/topodroid-zip-and-csx-format.md)) against reality. Rule: **where the file contradicts the docs, the file wins**, and the contradiction is a first-class finding.
4. **Measures version skew**: the installed binary predates this source tree by an unknown amount; the `version`/`creatversion` the binary writes into step-01 tells us how far the docs (grounded on this source) drift from the app under test.

## 2. Verified environment (probed 2026-07-19)

| Piece | State |
|---|---|
| Fixture | Was `dev/example/ponor_rupa_babi_pod_kucu-1p.csx` — raw TopoDroid 6.4.29 export, 7 shots + 49 splays, 34 flat sketch items (`-1s.csx` was byte-identical — TopoDroid's csx always contains both designs). **Post-run: the user's TDX files now live in `G:\My Drive\Share\TDX` (phone→Drive sync — the standing handoff folder); the raw export was lost in the move and awaits recovery** (SHA256 `D0096817A4AE…753ACB` in RUNLOG verifies any recovered copy). |
| cSurvey (app under test) | `C:\csurvey64\cSurveyPC.exe`, release binary dated 2025-12-10, x64. Configured & previously run (full `HKCU\Software\Cepelabs\cSurvey` key exists). |
| therion | **Two installs**: 6.1.8/2023 at `C:\Program Files (x86)\Therion\therion.exe` (what registry `therion.path` pointed at after auto-config) and 6.4.0/2026-05-07 at `C:\Program Files\Therion\therion.exe`. Switch to 6.4.0 (app: Settings... → therion path; or set `HKCU\Software\Cepelabs\cSurvey\therion.path` **with cSurvey closed**) *before* step-01, and record the active version in RUNLOG — therion is the network solver, so its version is part of the ground truth. Without a valid path the import's calculation step fails. |
| Inspector | `dev/tools/inspect_survey.py` (Python 3.11 present). Now reports a per-design **geometry digest** (bbox + coord-sum) so warping — which changes coordinates but no counts — is diff-visible. |
| Run directory | `dev/runs/2026-07-19-ponor-import/` — JSON reports + RUNLOG.md are **git-tracked**; survey snapshots are excluded by `dev/runs/.gitignore`. |

Note the 2026-07-16 roadmap claim "cSurvey has never been run on this machine" is **obsolete** — the environment gap it described has been closed.

## 3. Conventions

- **Never touch the original export.** Work only on a copy inside the run directory. The pristine fixture (+ its SHA256 in RUNLOG) is the anchor of the whole run.
- Snapshots: `step-NN-<label>.csz` in the run dir (local-only). Reports: `step-NN-<label>.json` (tracked). One RUNLOG entry per step, newest last; record surprises verbatim (dialog texts, error messages, anything you had to click).
- Snapshot = **File → Save As** into the run dir. Don't overwrite earlier snapshots; each step gets a new file.
- Generate a report immediately after each snapshot, and diff against the previous step:

```powershell
# after step NN's Save As:
python dev\tools\inspect_survey.py --json "dev\runs\2026-07-19-ponor-import\step-NN-<label>.csz" > "dev\runs\2026-07-19-ponor-import\step-NN-<label>.json"
git diff --no-index dev\runs\2026-07-19-ponor-import\step-MM-<prev>.json dev\runs\2026-07-19-ponor-import\step-NN-<label>.json
```

## 4. The steps

### step-00 — raw-export baseline ✅ done (agent, read-only)

[step-00-raw-export.json](../runs/2026-07-19-ponor-import/step-00-raw-export.json) — summarized in RUNLOG.

### step-01 — open in cSurvey, save untouched (user)

```powershell
Copy-Item "dev\example\ponor_rupa_babi_pod_kucu-1p.csx" "dev\runs\2026-07-19-ponor-import\work.csx"
& C:\csurvey64\cSurveyPC.exe "C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\runs\2026-07-19-ponor-import\work.csx"
```

Opening is enough: `creatid="topodroid"` without `creat_postprocessed` auto-triggers the fix-up chain (FixTopodroidCSX → ConvertDesign/ConvertItem → FixTopodroidSurvey), and `calculatemode=1` should auto-run the therion calculation. Then, **touching nothing else**: File → Save As → `step-01-after-import.csz` in the run dir (keep the app open for step-02/03). Report + diff per §3.

Record in RUNLOG: every dialog that appeared (conversion prompt, calculation progress/errors, warping notices), and how long the open took.

**Predictions to check against the diff** (each ✗ is a CONTRADICTION to log):

| # | Prediction | Grounding |
|---|---|---|
| 1 | Verdict flips to *post-import* (`creat_postprocessed="1"` stamped on save) | cProperties.vb:1185 |
| 2 | 34 flat items → **nested** items on typed layers; flat count 0. Total may drop below 34 only if symbols were dropped — record exactly which layer each symbol type landed on | cImportTopoDroidHelper.ConvertItem |
| 3 | Bound points go 0 → ~all; `items_without_bound_points` → 0 (FixTopodroidSurvey force-binds every item) | CLAUDE.md TopoDroid section |
| 4 | Trigpoints 0 → ≈57 (8 stations + 49 splay stations, from Rebind) | cTrigPoints.vb:103-150 |
| 5 | `<calculate>` cache appears (stations + speleometrics) | requires therion — configured |
| 6 | Segment ids: sequential/empty ints → 56 unique GUIDs | OFRegenerateSegmentsID |
| 7 | `g/m/dip/distox` attributes disappear from segments, reappear as `datatables` custom fields + per-segment datarow values; `import_source`/`import_date` stamps appear (record the exact `import_source` value) | cSegments.vb:191-208, FixTopodroidSurvey |
| 8 | Root `version` = the binary's format version. **1.14 ⇒ binary matches source docs; less ⇒ measured version skew** — either way, record it | cSurvey.vb version const |
| 9 | Geometry digest roughly unchanged (import binds, it shouldn't move points). If plan/profile bbox or coord-sum shift materially → CONTRADICTION worth deep investigation (coordinate-space transform in the converter) | inference — weakest prediction |
| 10 | Splay stations keep TopoDroid's `0(0)`-style names, splay+exclude flags survive | step-00 finding |

### step-02 — eyes-on-the-UI observations (user, no snapshot)

Nothing here changes the file; it captures what the XML can't. In both plan and profile view, note in RUNLOG (screenshots welcome: `step-02-plan.png`, `step-02-profile.png` in the run dir — tracked):

- Layer panel: which of the 7 layers hold items now; does the count match step-01's per-layer JSON?
- Did `wall:presumed`, `user`, and the label items (`text="spoj"` etc.) survive visibly, and as what?
- Does the **profile** sketch sit on the recomputed extended-elevation centerline, or is it offset/mangled? (TopoDroid unrolled the profile its own way; therion recomputes the abscissa — misalignment here is a known-unknown of Pipeline A.)
- Anything visually wrong: mirrored geometry, wrong scale, items in one heap.

### step-03 — warp probe (user)

The point of binding is that drawings follow the centerline. Prove it: in the shots grid, change shot `0 → 1` distance **2.59 → 3.09**, let it recalculate (auto; else trigger recalculation manually), then File → Save As → `step-03-warp-probe.csz`. Report + diff vs step-01.

- **Expected:** counts identical; plan & profile `bbox`/`coord_sum` change — bound points moved with the centerline. A warping-details dialog may appear; note what it said.
- **If geometry is unchanged** → binding or warping silently failed (check `designwarpingmode` in the step-03 JSON — a past "Abort" can set it to None persistently, CLAUDE.md invariant #9) → CONTRADICTION, and Pipeline A's headline claim needs a second look.

The scratch copy can be discarded afterwards; snapshots stay.

### step-04 — findings pass (agent)

1. Walk the three diffs (00→01, 01→03); fill the RUNLOG **findings** section: every prediction ✓/✗ with the JSON evidence inline.
2. For each CONTRADICTION: update the affected doc in [dev/docs/](../docs/README.md) (and CLAUDE.md if it repeats the claim), citing the run as evidence.
3. Promote validated inferences from "informed inference" to fact in [topodroid-zip-and-csx-format.md](../docs/topodroid-zip-and-csx-format.md) / [topodroid-import.md](../docs/topodroid-import.md).
4. Append a dated decision entry to [roadmap-decisions.md](../docs/roadmap-decisions.md) with the verdict: is Pipeline A's import chain fit for automation as-is, and what (if anything) it drops or breaks.
5. Update agent memory with the run outcome.

## 5. For Claude agents — how to get the complete picture

Reading order for a fresh session: this protocol → [RUNLOG.md](../runs/2026-07-19-ponor-import/RUNLOG.md) (where the run actually stands) → the step JSONs → [stage0-inspector-brief.md](stage0-inspector-brief.md) (why the inspector exists, corpus baseline) → [roadmap-decisions.md](../docs/roadmap-decisions.md) (strategy history).

Rules of engagement:

- The inspector is **read-only by design**; never "fix" or repack survey files, never extract zips to disk. If a step needs a modified survey, the *user* makes the change in the app.
- `dev/example/` is **gitignored** — the fixture is invisible to git history. Its SHA256 in RUNLOG is the integrity check. Never commit `.csz`/`.csx` (enforced by `dev/runs/.gitignore`).
- The file beats the docs; contradictions are findings, not errors to smooth over. Log them loudly in RUNLOG *and* fix the docs (step-04).
- The app under test is a 2025-12-10 release binary, but all docs cite *this source tree* — qualify any code citation with the possibility of skew until prediction 8 pins it down.
- If the UI shows a string you need to trace, grep it in `cSurveyPC/*.resx`, then the key in `frmMain2.vb` (CLAUDE.md invariant #12).

## 6. After this run

- **Import chain proven?** → next is the **reflection hypothesis** (roadmap 2026-07-16 critical path #4): a tiny net48 driver beside `C:\csurvey64\cSurveyPC.exe` calling public `Load(path, FixTopoDroid)` → `SaveTo` — headless Pipeline A with **no source build, no DevExpress**. If that works, Stage 1 of the [MCP blueprint](../docs/mcp-blueprint.md) shrinks dramatically.
- **Something broken?** → the run produced the exact diff showing where; route via CLAUDE.md's symptom table.
- Repeat runs (new caves, x-section-bearing surveys, multi-trip merges) reuse this protocol: new dated directory under `dev/runs/`, same step pattern, step-00 from the new export.
