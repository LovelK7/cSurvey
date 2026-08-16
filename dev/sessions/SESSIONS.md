# Session journal

One block per working session (human or agent), **newest on top**. Write one at the end of every
session — it's the continuity thread across sessions and agents: what got touched, how it went, and
what's next. Keep it terse; link to project logs / runs / decisions for detail. This is the tier that
answers *"what has been done lately, and how successfully"* without reading every project.

Per the three-tier model ([dev/README.md](../README.md#logging--three-tiers-deliberately-non-overlapping)):
strategy → `decisions/`, per-task detail → `projects/NNNN/log.md`, chronology → here.

---

### 2026-08-16 (3) — slope-line spline fix diagnosed; STEP 4 made drag-drop + dumb-proofed (agent) ✅

- **Did:** user reported imported **slope** lines showing straight (decorations hidden) until manually
  switched to Splines. Diagnosis: already exactly what `fix_imported_linetypes.py`
  (`spline_linetypes:true`) does — slope is a plain `cItemFreeHandLine` (`type=1`, `linetype=0`,
  [cImportTopoDroidHelper.vb:218](../../cSurveyPC/cImportTopoDroidHelper.vb#L218)) caught by the blanket
  rule; verified on rupe files (step-02b `linetype=0` → step-04b `linetype=1`, all 20 lines). Real gap
  = user **skips step 4** because the routine was unclear (cryptic `_pp`/`_lt` suffixes, "drag onto"
  unexplained, hidden "must Save As .csx" trap). Dumb-proofed the whole thing:
  - `fix_imported_linetypes.py`: now accepts **`.csz` OR `.csx`** (rewrites the zip's `_data.xml`
    in place, all other entries byte-preserved — kills the save-as-csx trap), **BLOCKS** a
    not-yet-imported (flat `<plan>/<item>`, no `<layers>`) file with plain instructions, reports
    "nothing to do", takes multiple dragged files (skips `_lt`).
  - New **`fix_tdx.bat`** + runtime STEP banners/footers added to all three bats (fixed a batch
    `->`-as-redirection bug that ate footer lines + created stray files).
  - New **`READ ME FIRST - process a survey.txt`** — jargon-free numbered checklist (drag-drop,
    suffix glossary, black-window-message decoder). Copied into the TDX folder.
  - Protocol step 4 + both READMEs updated; `.csz` accepted; guide linked.
- **Result:** import the `_pp` → draw in the `_lt`, one double-click per step, wrong-step files
  refuse themselves. All paths tested (csx+csz round-trip w/ asset preservation, blocker, no-op,
  batch, bat execution). Honest limit: a bat still needs *remembering* — the zero-step cure is the
  parked upstream `ConvertItem` change (emit Splines at import).
- **Evidence:** `production/tools/{fix_imported_linetypes.py,fix_tdx.bat,preprocess_tdx.bat,
  recover_tdx.bat,READ ME FIRST - process a survey.txt}`, `tdx-processing-protocol.md` step 4,
  `production/README.md`, `tools/README.md`. TDX-folder copies synced.
- **Next:** if forgetting persists, do the upstream `ConvertItem` spline change when the DevExpress
  build is available (already listed as an upstream fix candidate).

### 2026-08-16 (2) — recovery accepted; project 0003 promoted and CLOSED (agent) ✅

- **Did:** user confirmed the recovered csx imports correctly in cSurvey → Phase 3/4 executed:
  `parse_tdr.py` + `tdx_zip_to_csx.py` moved to `production/tools/`; converter gained multi-zip /
  folder-scan batch mode with an automatic `preprocess_tdx_csx.py` pass (fixes the
  paths-with-spaces friction); new `recover_tdx.bat` (double-click = process all zips in the TDX
  folder, or drag zips onto it) deployed to `G:\My Drive\Share\TDX\`. Protocol got step 1b
  (always archive the project zip; recovery path); reference format doc got the `D` record +
  604088/604096/604098 gates + silent-rejection warning. Brief 0003 closed, board updated.
- **Result:** batch run over the TDX folder: 2/2 project zips converted; `lidar158out.zip` correctly
  identified as a non-project export bundle (0-byte crashed `-1p.csx`, an old 6.2.16 data-only csx,
  DXFs) — user re-exports the real archive zip from the phone, then drag-and-drop.
- **Evidence:** `production/tools/{tdx_zip_to_csx.py,parse_tdr.py,recover_tdx.bat,README.md}`,
  `production/tdx-processing-protocol.md` step 1b, closed brief `projects/0003-tdx-zip-recovery/`.
- **Next:** report both bugs upstream (marcocorvi/topodroid). Headless driver remains queued as `0004`.

### 2026-08-16 — TDX 6.4.99 export bug diagnosed + zip→csx recovery tool (agent) ✅

- **Did:** opened project `0003-tdx-zip-recovery` for the TopoDroid 6.4.99-36 breakage (0-byte csx
  export, sketches vanishing on cross-version zip import). Fetched TopoDroid master source and pinned
  the root cause: tdr binary format changed at 604088/604096/604098 and the reader **silently
  discards** any tdr newer than the running app (`DrawingIO.java:750`). Built `parse_tdr.py`
  (all-version tdr reader) and `tdx_zip_to_csx.py` (offline replay of TopoDroid's csx exporter).
- **Result:** both corrupt surveys fully recovered — `spilja_bunker_studena` (39 sketch items) and
  `zero_calory_dressing` (45 items); geometry exact vs TopoDroid's own th2; Stage-0 inspector clean;
  protocol preprocessor applied. `*_recovered_pp.csx` delivered next to the zips in the TDX folder.
  Two reference-doc gaps found (post-`F` `D` record; the three new version gates) — noted in the
  brief, doc update pending promotion.
- **Evidence:** `projects/0003-tdx-zip-recovery/{brief.md,log.md,runs/2026-08-16/}`.
- **Next:** user imports the `_pp.csx` files in cSurvey (Phase 3); on acceptance promote the two
  scripts to `production/tools/` + update the format reference; report both bugs upstream.
  Headless driver renumbered to `0004`.

### 2026-07-26 — restructured dev/ into the four-zone system (agent) ✅

- **Did:** reorganized `dev/` from the tangled `docs/`+`tools/`+`tasks/`+`runs/` layout into four zones
  — `reference/` (architecture), `production/` (routine toolkit + SOP + methods), `projects/`
  (the dev loop, one folder per work item), `decisions/` (strategy log) — plus a `sessions/` journal.
  Established the dev-loop lifecycle (`draft→research→proposal→validation→closed`), project-folder
  anatomy (`brief.md` + `log.md` + `runs/` + `findings/`), templates under `projects/_templates/`, and
  the three-tier logging model.
- **Result:** 92 files moved; 86 cross-references auto-rewritten (incl. depth-sensitive `../../cSurveyPC`
  citations) with **0 newly-broken links** (the only 2 danglers are the pre-existing lost `step-00-raw-export.json`).
  Existing work refiled: inspector → project 0001; TDX symbol mapping + its 3 runs → project 0002;
  protocol/matrix/tools → `production/`; roadmap → `decisions/`. CLAUDE.md layout table + `dev/README.md`
  now describe the new structure.
- **Evidence:** `dev/README.md`, `dev/projects/README.md`, this reorg's git status (40+ renames).
- **Next:** brief up `0003-headless-driver` (the reflection hypothesis) as the first project run under the
  new system. Nothing blocking; user to review the structure.
