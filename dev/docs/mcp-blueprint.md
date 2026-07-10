# MCP server blueprint: driving cSurvey from Claude (TopoDroid in → finished map out)

All paths are relative to the repo root. Line citations are either verified directly in this pass (marked ✓ where load-bearing) or inherited from the grounded subsystem docs listed in [Related docs](#related-docs); nothing here is speculation unless marked *(inferred)*.

## Purpose

This is the actionable build plan for an MCP server that lets a Claude agent operate cSurvey on behalf of the user: import TopoDroid data, inspect and fix the survey, auto-generate a plan/profile sketch, and export a finished map (PNG/SVG/therion PDF). It synthesizes the architecture decision, the concrete MCP tool list with the exact cSurvey code path behind each tool, a staged roadmap, and the open technical risks with mitigations.

## Domain concepts

- **Worker host** — a .NET Framework 4.8 console process that references `cSurveyPC.exe` as a library and holds one live `cSurvey.cSurvey` object in memory. It is where all domain calls happen. It must run from (or beside) the cSurvey install directory so DevExpress assemblies and the `resources` localization file resolve (cSurveyPC/modMain.vb:42-47, 414-426).
- **MCP front-end** — a modern-.NET (or Node/Python) stdio process implementing the MCP protocol. MCP SDKs do not target net48, so the front-end spawns the worker host and talks to it over a private line-JSON protocol on stdin/stdout. Two processes, one logical server.
- **Friend wall** — VB `Module`s and many key methods are assembly-internal: `modImport`/`modExport`/`modMain`/`modSegmentsTools` are Friend modules (✓ `Module modSegmentsTools` at cSurveyPC/modSegmentsTools.vb:8) and `cCalculate.Calculate` is `Friend` (✓ cSurveyPC/Calculate/cCalculate.vb:576). No `InternalsVisibleTo` exists anywhere in the source (✓ grep: only doc files mention it). Crossing this wall requires a one-line source change or a small facade compiled into cSurveyPC.
- **Automation facade (`cAutomation`)** — the recommended ~100-line `Public` class added to the cSurveyPC project that (a) bootstraps `My.Application.Settings`/`RuntimeSettings` and localized strings, and (b) forwards to the Friend members the pipeline needs. This is the only cSurvey source change the whole blueprint requires.
- **TopoDroid interchange reality** — cSurvey cannot read TopoDroid's own project `.zip`. The supported inputs are TopoDroid's *exports*: `.csx` (cSurvey XML, richest — centerline + phone sketches), therion `.th` (centerline) and `.th2` (sketch scraps) ([topodroid-import.md](topodroid-import.md)). "Import TopoDroid zip" therefore means either asking the user for the csx export, or shipping a separate zip→csx pre-converter (the zip contains a 4-line manifest, a `survey.sql` text dump of the phone DB, and binary `.tdr` sketch files — internals fully grounded in [topodroid-zip-and-csx-format.md](topodroid-zip-and-csx-format.md)).

## Architecture

### Decision: architecture (b) from [automation-surface.md](automation-surface.md) — headless .NET host + facade, with direct-XML as a read-only complement

Of the three candidates evaluated there:

| Candidate | Verdict | Why (code reality) |
|---|---|---|
| (a) Out-of-process `_data.xml` manipulation only | **Complement, not backbone** | Full read access works (all cross-references are strings, calc cache is embedded — [data-model-and-file-format.md](data-model-and-file-format.md)); but sketch generation, recalculation (therion round-trip + splay projection), warping and binding would all have to be reimplemented from scratch. Weeks of duplicated logic, permanently drifting from the app. |
| **(b) net48 worker host loading cSurveyPC.exe + facade** | **Chosen** | The exact pipeline already runs headless inside the app: `frmMain2.pSurveyImportcSurvey` does `New cSurvey → Load(path, FixTopoDroid) → Invalidate() → Calculate.Calculate(True)` on a windowless survey (✓ cSurveyPC/frmMain2.vb:11860-11865; the recalc pair is guarded by `If Not …Calculate.LoadedFromFile`). `cSurvey.New/Load/SaveTo/Invalidate` are Public (✓ cSurveyPC/cSurvey.vb:936, 1864-1882, 1939). Only the Friend wall, settings bootstrap and localization stand between today's code and a headless driver — all fixable with one small in-repo facade. Every future capability (auto-sketch, rendering, exports) reuses the app's own code. |
| (c) UI automation of the running app | **Rejected** | The map canvas is custom-painted with no automation peers; imports go through modal dialogs; no single-instance IPC channel exists (`IsSingleInstance=false`); localization changes captions ([automation-surface.md](automation-surface.md) §c). Permanent fragility. |

### Process topology

```
Claude ⇄ (MCP stdio) ⇄ mcp-csurvey front-end (net8/node)
                            │  spawns, line-JSON over stdio
                            ▼
                      csurvey-worker.exe (net48, x86/x64 matching install)
                            │  references cSurveyPC.exe + cAutomation facade
                            │  holds ONE cSurvey object per session
                            ├──► therion.exe (spawned per recalculation/PDF export)
                            └──► reads/writes .csz/.csx on disk
```

Rules the topology encodes:

1. **One worker, one survey, one thread.** The domain is not thread-safe for concurrent use (paint options objects are mutated during paint — [rendering-and-plot.md](rendering-and-plot.md); `cSegments` events can fire cross-thread, commit 0c6700b). The worker processes one command at a time; the front-end serializes tool calls.
2. **Worker lives in the install dir.** `modMain.GetApplicationPath` derives from `Process.MainModule.FileName` (cSurveyPC/modMain.vb:42-47), so `objects\`, cliparts and the `resources` localization file resolve only if the worker exe sits beside `cSurveyPC.exe`.
3. **Worker never touches forms.** DevExpress types JIT-load only when UI classes are instantiated; a worker that stays on domain classes runs without a DevExpress runtime license prompt *(inferred from JIT semantics; verified pattern: the in-app import survey has no form attached)*. Explicit no-go list: `frmWarpingDetails` (disable `Properties.ShowWarpingDetails`), `cBlenderHelper`/`cMeshLabHelper` (MessageBox landmines, cSurveyPC/cBlenderHelper.vb:112-121), `cHolosViewer` (WPF/STA), `cSurvey.Check` (keyboard-state check, cSurveyPC/cSurvey.vb:902-907 — call `Load` directly).
4. **Stage-0 tools bypass the worker entirely**: the front-end unzips `.csz` (plain ZIP, `_data.xml` inside) and answers read-only queries from the XML. Cheap, no build dependency, works even when cSurveyPC can't be compiled yet.

### The `cAutomation` facade (the one source change)

A Public class in the cSurveyPC project exposing exactly:

| Facade member | Forwards to | Why needed |
|---|---|---|
| `Bootstrap()` | replicate `MyApplication.ReloadSettings` (cSurveyPC/ApplicationEvents.vb:53-83) + `modMain.LoadLocalizedStrings` (cSurveyPC/modMain.vb:414) | `My.Application.Settings` is read at ~712 sites (grep) incl. the calculate path (Calculate/cCalculate.vb:1601); both NRE headless otherwise |
| `Calculate(survey, warping)` | `survey.Calculate.Calculate(warping)` (✓ Friend, Calculate/cCalculate.vb:576) | recalculation |
| `ExportTherion(survey, path, opts)` | `modExport.TherionThExportTo` (cSurveyPC/modExport.vb:3791) + `TherionCreateConfig` (:795-833) | .th/.th2/thconfig, PDF pipeline |
| `RunTherion(...)` | `modMain.ExecuteTherionAsync` (cSurveyPC/modMain.vb:298) | **not** the sync variant — it pops a MsgBox at 120 s (modMain.vb:388-395) |
| `GeneratePlanWalls(survey, cave, branch, lineType, precision, hull)` | `modSegmentsTools.CreatePlanBorderFromSplay` (✓ cSurveyPC/modSegmentsTools.vb:424, 627) **then `item.BindSegments()`** (Friend, cSurveyPC/cItem.vb:796) | the generator never binds its output ([auto-sketch-feasibility.md](auto-sketch-feasibility.md) Flow 1 step 6) |
| `BindItem(item)` | `cItem.BindSegments` | required after any programmatic item creation |
| `ImportTh2(survey, file, cave, opts, scale)` | `modImport.TherionTh2ImportFrom` (cSurveyPC/modImport.vb:490) | th2 sketch route |
| `ReplaceItemIds(xml, map)` | `modImport.ReplaceIDItem` (cSurveyPC/modImport.vb:451) | merge tooling (Stage 1+) |

Alternative with zero new code: `<InternalsVisibleTo("csurvey-worker")>` in AssemblyInfo — but the facade is preferred because it also centralizes `Bootstrap()` and documents the sanctioned automation surface.

### Concrete MCP tool list

Minimal set covering the user's workflow. `[S0]` = implementable in Stage 0 (XML-only), `[W]` = needs the worker.

| Tool | Params | Behavior | Code path / XML mapping |
|---|---|---|---|
| `open_survey` [W] | `path` | Loads a .csz/.csx into the worker's `cSurvey`; auto-runs TopoDroid fix-ups if `creatid="topodroid"`. Returns basic identity + whether calc cache was present. | `New cSurvey` → `Load(path)` (✓ cSurvey.vb:936); auto fix-up at cSurvey.vb:943-945 |
| `import_topodroid` [W] | `path`, `save_as?` | The flagship: load TopoDroid-exported csx with fix-ups forced, recalculate, save. Rejects `.zip` with a message telling the user to export csx from TopoDroid (until a zip pre-converter exists). Returns calc result + counts (shots/splays/sketch items found). | ✓ frmMain2.vb:11860-11865 sequence: `Load(path, LoadOptionsEnum.FixTopoDroid)` → `Invalidate()` → facade `Calculate(True)` → `SaveTo` |
| `get_survey_stats` [S0/W] | — | Shots/splays/caves/branches/sessions counts, origin, speleometrics, loop errors, unbound-item count, whether phone sketch present. | S0: parse `_data.xml` (`<segments>`, `<calculate><sms>`, `<rngs>`); W: `Survey.Segments`, `Survey.Calculate.Speleometrics/Rings` |
| `list_shots` [S0/W] | `filter?` (cave/branch/splay/errors) | Tabular shot dump: id, from, to, d/b/i, LRUD, flags, session, cave/branch. | S0: `<segment>` attrs per the field table in [data-model-and-file-format.md](data-model-and-file-format.md); W: `cSegments` enumeration |
| `update_shot` [W] | `id`, `fields{}` | Sets properties on one `cSegment` (distance, bearing, flags, session, cave/branch, note…). Honors flag coupling (cut→splay→exclude). Marks survey invalidated; does not auto-recalculate. | `Survey.Segments(id)` property setters (cSegment.vb); invalidation bubbles via cSurvey.vb:1884-1924 |
| `add_shots` [W] | `rows[]` | Bulk-append shots (fresh GUIDs, splay auto-naming). No event storm headless — worker has no `OnSegmentsChange` subscribers. | `Survey.Segments.Append` (Public, cSegments.vb:260/272); splay names via cSegments.vb:308-333 |
| `recalculate` [W] | `warping?=true` | Runs the full pipeline (therion round-trip); returns the typed error from `cActionResult.Exception` (missing session / orphan shots / therion missing) as a structured diagnosis, never throws. | facade → `Calculate.Calculate(True)` (✓ cCalculate.vb:576); preconditions per [topodroid-end-to-end-trace.md](topodroid-end-to-end-trace.md) Flow C step 3 |
| `validate_survey` [W] | — | Pre-flight without therion: origin set? every shot has a session? station-name case collisions? therion.path configured? | reads `Properties.Origin`, `Segments`, `My.Application.Settings("therion.path")`; mirrors checks at cCalculate.vb:592-649 |
| `generate_walls_from_splays` [W] | `cave`, `branch?`, `view=plan`, `angular_precision=10`, `hull=none` | Creates the cave-border item(s) from splay fans and **binds them**. `view=profile` returns "not implemented" until the Stage-2 port lands. | facade → ✓ `CreatePlanBorderFromSplay` (modSegmentsTools.vb:424) + `BindSegments()`; ✓ profile stub at modSegmentsTools.vb:645 |
| `add_drawing_item` [W] | `design`, `layer`, `kind`, `points[]`, `cave`, `branch` | Generic item creation: typed layer factory, sequences of world-meter points, cave/branch set, bound. Used for quotas, presumed borders, water/soil areas, signs, texts. | layer factories (cLayerBorders.vb:36-48, cLayer.vb:289-381) + `Points.StartSequence()/AddFromPaintPoint` (cPoints.vb:76-110) + `SetCave` + facade `BindItem` |
| `list_drawing_items` [S0/W] | `design` | Items per layer with type/category/cave/bound-point counts — lets the agent detect an existing phone sketch (Pipeline C dispatch). | S0: `<plan>/<layers>/<layer>/<items>/<item>`; W: `Survey.Plan/Profile.Layers` |
| `render_preview_png` [W] | `design`, `scale=500`, `out_path` | Renders the design to a PNG so the agent can *see* the current map. Offscreen `Bitmap` + `Graphics`, one long-lived `cOptionsExport` instance, world→page matrix from `GetZoomFactor` + design bounds. | replicate frmPreview.vb:1004-1086: `Survey.Plan.Paint(g, options, cDrawOptions.Empty, cEmptyEditDesignSelection.Empty)` ([rendering-and-plot.md](rendering-and-plot.md)) |
| `export_svg` [W] | `design`, `out_path` | Vector export. Must run after a Paint/Render with the *same* options object (SVG serializes the draw caches). | `cDesignPlan/cDesignProfile.ToSvg` (✓ Friend, cDesignPlan.vb:444 — needs a facade forwarder) per frmPreview.vb:1574-1666 recipe (`ToSvg` call at :1664-1666) |
| `export_therion` [W] | `out_path`, `flags?` | Writes .th (+ .th2 scraps + thconfig). | facade → `TherionThExportTo(survey, path, TherionGetSavenameDictionary(survey), Default Or Scrap Or CalculateSplay Or SegmentSplayWithoutName)` (modExport.vb:3791) |
| `export_pdf` [W] | `out_path`, `view=plan|profile|both` | Finished PDF via therion compile — cSurvey has no PDF writer. Replicates the TherionPad recipe. | frmMain2.vb:9674 (`pSurveyExportToTherion`): export temp .th with Scrap → `TherionCreateConfig` with `export map -o *.pdf` → facade `RunTherion` ([exports-and-printing.md](exports-and-printing.md)) |
| `save_survey` [W] | `path?` | Persists; stamps `creat_postprocessed="1"` on first save of TopoDroid files, embeds the `<calculate>` cache. | ✓ `SaveTo(path)` (cSurvey.vb:1875); stamp at cProperties.vb:1182-1185 |
| `get_xml` [S0] | `path`, `xpath?` | Raw read-only escape hatch: extract `_data.xml` (or a fragment) from a .csz for arbitrary inspection. | ZIP + XPath; schema map in [data-model-and-file-format.md](data-model-and-file-format.md) |

### Staged implementation roadmap

**Stage 0 — read-only XML tools (days).**
Front-end only; no cSurveyPC build, no worker, no therion. Implement `get_survey_stats`, `list_shots`, `list_drawing_items`, `get_xml` directly over the ZIP/`_data.xml` (schema fully documented). Immediately useful for diagnosis ("why does my import look wrong") and as the provenance probe (`import_source`/`import_date` datarow stamps, DistoX fields, `creatid` markers).
*Prerequisites:* none. *Risks:* number parsing — `_data.xml` stores '.' decimals, so the Stage-0 front-end must parse with invariant culture (the app itself normalizes '.' to the host decimal separator before parsing, `StringToDecimal` cSurveyPC/modNumbers.vb:228-236); pipe-positional `<datarow>` decoding needs the `<datatables>` definitions.

**Stage 1 — worker host + data-write + import (1–2 weeks).**
Build the net48 worker + `cAutomation` facade; implement `open_survey`, `import_topodroid`, `recalculate`, `validate_survey`, `update_shot`, `add_shots`, `save_survey`. This is Pipeline A of [auto-sketch-feasibility.md](auto-sketch-feasibility.md): when the surveyor drew on the phone, `Load(FixTopoDroid)` already yields a bound, typed sketch — end of story.
*Prerequisites:* ability to compile cSurveyPC (DevExpress v24.2 GAC + licenses.licx is the build blocker — [ui-map.md](ui-map.md)); therion.exe installed and `therion.path` set in `HKCU\Software\Cepelabs\cSurvey`; worker bitness matched to the installed build.
*Risks:* settings/localization bootstrap ordering (facade `Bootstrap()` must run before any `Load`); the first `Calculate` runs *inside* `Load` for version `-1` files and its errors don't fail `Load` — the tool must re-check via an explicit `recalculate`.

**Stage 2 — sketch generation (2–4 weeks).**
Implement `generate_walls_from_splays` and `add_drawing_item`; hybrid dispatch (Pipeline C): reuse phone sketch when `list_drawing_items` finds items, synthesize otherwise.
Plan view is ~70% done: call the existing generator, add the missing `BindSegments()`, pre-set per-shot `PlanSplayBorderInclinationRange` (the generator ignores the `InRange` flag, modSegmentsTools.vb:331-333). Profile view is the real work: `CreateProfileBorderFromSplay` is an empty stub (✓ modSegmentsTools.vb:645) — port the plan algorithm to `Data.Profile.FromSplays/ToSplays` in (D,Z) space, unioning per segment-group because junctions unroll to different D. QA loop via `modDesignLRUD.GetLRFromDesign` raycasts (modDesignLRUD.vb:740) compared to splay extents.
*Prerequisites:* Stage 1; a calculated survey (splay projections exist only after `Calculate`).
*Risks:* output is a wall *envelope*, not cartography — set user expectations; generator is debug-menu-only experimental code (frmMain2.vb:15901); Clipper works at 1 cm integer resolution (×100 scaling).

**Stage 3 — rendering & export (1–2 weeks).**
`render_preview_png` (gives the agent eyes — enables iterate-on-sketch loops), `export_svg`, `export_therion`, `export_pdf`.
*Prerequisites:* Stage 1; for PDF, therion again.
*Risks:* `GetZoomFactor` sniffs 96 DPI to distinguish screen vs printer (modPaint.vb:942) — create the offscreen Graphics at 96 DPI; the options instance is the draw-cache dictionary key (cDrawCaches.vb:52-62) — keep exactly one per design for the worker's lifetime; SVG export requires prior cache population with that same instance.

**Stage 4 (optional) — TopoDroid zip pre-converter.**
A standalone reader for TopoDroid's project zip (flat entries: `manifest`, `survey.sql` shot/plot/fixed dump, `.tdr` binary sketches, media) emitting cSurvey csx (`version="-1"`, `creatid="TopoDroid"` to opt into the fix-up chain) — removes the "please export csx" step. Entirely outside cSurvey. All input formats and the exact csx TopoDroid itself would write (the template to imitate) are grounded in [topodroid-zip-and-csx-format.md](topodroid-zip-and-csx-format.md); the native csx schema superset is in [data-model-and-file-format.md](data-model-and-file-format.md).

## Key classes & files

| File | Class / member | Role in the blueprint |
|---|---|---|
| cSurveyPC/cSurvey.vb:936, 1875, 1939 | `cSurvey.Load/SaveTo/Invalidate` (Public ✓) | Worker's core lifecycle API |
| cSurveyPC/frmMain2.vb:11860-11865 | `pSurveyImportcSurvey` (fragment ✓) | The proven headless import+calculate sequence to copy verbatim |
| cSurveyPC/Calculate/cCalculate.vb:576 | `Friend Calculate(PerformWarping) As cActionResult` (✓) | Recalculation — behind the Friend wall, facade target |
| cSurveyPC/modSegmentsTools.vb:8, 424, 627, 645 | `modSegmentsTools` (Friend module ✓), `CreatePlanBorderFromSplay` (✓), `CreateProfileBorderFromSplay` (empty stub ✓) | Auto-sketch generators — facade targets |
| cSurveyPC/cItem.vb:796 | `Friend BindSegments()` | Mandatory post-generation binding — facade target |
| cSurveyPC/modExport.vb:3791, 795 | `TherionThExportTo`, `TherionCreateConfig` | .th/.th2/PDF pipeline — facade targets |
| cSurveyPC/modMain.vb:298, 363, 414 | `ExecuteTherionAsync` / `ExecuteTherion` (MsgBox at timeout) / `LoadLocalizedStrings` | External-tool runner + localization bootstrap |
| cSurveyPC/ApplicationEvents.vb:53-83 | `MyApplication.ReloadSettings`/Startup | Settings bootstrap the facade must replicate |
| cSurveyPC/cImportTopoDroidHelper.vb:6, 54-66 | `cImportTopoDroidHelper` (Public Shared) | TopoDroid sketch converter — already externally callable |
| cSurveyPC/modImport.vb:384, 490, 451 | `FixTopodroidCSX`, `TherionTh2ImportFrom`, `ReplaceIDItem` | Fix-up + th2 route + id remapping |
| cSurveyPC/cFile.vb:66-112, 386-403 | `cFile`/`cStorage` | .csz container — also the spec for Stage-0 ZIP handling |
| cSurveyPC/cDesignPlan.vb:444; cSurveyPC/frmPreview.vb:1004-1086, 1574-1666 | `ToSvg` (Friend ✓); render recipes | Stage-3 rendering/export references |
| cSurveyPC/modDesignLRUD.vb:740 | `GetLRFromDesign` | Sketch-quality QA raycast |

## Key flows

### 1. `import_topodroid` (worker internals)

1. worker — `cAutomation.Bootstrap()` once at startup: settings from `HKCU\Software\Cepelabs\cSurvey` (cSurveyPC/ApplicationEvents.vb:53-62) + `modMain.LoadLocalizedStrings` (cSurveyPC/modMain.vb:414).
2. cSurveyPC/cSurvey.vb:936 — `New cSurvey` → `Load(path, LoadOptionsEnum.FixTopoDroid)`.
3. cSurveyPC/cSurvey.vb:943-945 — phase-1 DOM fix-up `modImport.FixTopodroidCSX` (GUID ids, uppercase stations, note attribute).
4. cSurveyPC/cSurvey.vb:1547-1550 — version `-1` has no `<calculate>` cache → in-Load `Invalidate()` + `Calculate(False)` (therion round-trip runs here).
5. cSurveyPC/cSurvey.vb:1566-1570 — phase-2: `FixTopodroidDesign` materializes phone-sketch items, `FixTopodroidSurvey` stamps provenance and force-`BindSegments()` on every item.
6. worker — `Invalidate()` + facade `Calculate(True)` (✓ frmMain2.vb:11862-11865 pattern); map the typed `cActionResult.Exception` to a structured tool error (missing session / orphan shots / therion missing).
7. cSurveyPC/cSurvey.vb:1875 — `SaveTo(save_as)`; first save stamps `creat_postprocessed="1"` (cProperties.vb:1182-1185) and embeds `<calculate>`.

### 2. `generate_walls_from_splays` (plan)

1. worker — precondition: survey calculated (splay projections `Segment.Data.Plan.FromSplays/ToSplays` populated by `cPlotPlan.CalculateSplay`, cSurveyPC/cPlotPlan.vb:655-767).
2. worker (optional) — per shot set `PlanSplayBorderInclinationRange` to exclude ceiling/floor splays (cSurveyPC/cSegment.vb:214-304) — the generator ignores the `InRange` flag.
3. cSurveyPC/modSegmentsTools.vb:424 — facade → `CreatePlanBorderFromSplay(survey, cave, branch, LineTypeEnum.Splines, precision, hull)`: bearing-buckets splay tips, station octagons, Clipper union → one `cItemInvertedFreeHandArea` added to the Plan Borders layer.
4. cSurveyPC/cItem.vb:796 — facade → `item.BindSegments()` on each returned item (the UI flow omits this; unbound borders never warp).
5. worker — respond with item ids + `modDesignLRUD.GetLRFromDesign` QA metrics (cSurveyPC/modDesignLRUD.vb:740) vs splay extents.

### 3. `render_preview_png`

1. worker — lazily create the design's single long-lived `cOptionsExport` (options instance = draw-cache key, cSurveyPC/cDrawCaches.vb:52-62); set `CurrentScale`, `DrawPlot/DrawSplay/DrawHighlights` per params.
2. worker — `New Bitmap(w,h)` at 96 DPI + `Graphics.FromImage`; `zoom = modPaint.GetZoomFactor(g, scaleN)` (cSurveyPC/modPaint.vb:942); transform = Scale(zoom) + Translate(fit of `Survey.Plan.GetDesignVisibleBounds(options)`) — the frmPreview.vb:1004-1056 recipe.
3. cSurveyPC/cDesign.vb:987 — `Survey.Plan.Paint(g, options, cDrawOptions.Empty, cEmptyEditDesignSelection.Empty)` — surface, 7 layers, area fills, centerline; no UI dependency (progress events unhandled are safe).
4. worker — `bitmap.Save(out_path, Png)`; return path so the agent can view it.

### 4. `export_pdf` (via therion)

1. worker — facade `ExportTherion`: `modExport.TherionThExportTo(survey, tmp.th, TherionGetSavenameDictionary(survey), Default Or Scrap Or CalculateSplay Or SegmentSplayWithoutName)` (cSurveyPC/modExport.vb:3791) — writes .th + .th2 scraps from the drawings.
2. cSurveyPC/modExport.vb:795-833 — `TherionCreateConfig` with `export map -o out.pdf` (+ `-proj extended` for profile) and the Metapost clipart layout.
3. cSurveyPC/modMain.vb:298 — facade `RunTherion` → `ExecuteTherionAsync` (hidden window, `THERION` env var pointing at the therion.ini folder; throws `TimeoutException` instead of the sync variant's MsgBox at modMain.vb:388-395).
4. worker — collect therion log lines for the tool result; return the PDF path. This mirrors `frmMain2.pSurveyExportToTherion` (cSurveyPC/frmMain2.vb:9674).

## How to modify safely

- **Keep the facade thin and inside cSurveyPC.** It should only bootstrap + forward; any logic added there duplicates UI code paths and will drift. New automation needs → expose the existing Friend member, don't reimplement it in the worker.
- **Serialize everything through the single worker thread.** Do not parallelize tool calls against one survey: paint options are mutated during paint, `cSegments` events may fire on non-UI threads, and the undo/XML machinery assumes sequential access.
- **Never subscribe the worker to `OnSegmentsChange`.** The UI's `bDisableSegmentsChangeEvent` push/pop guard exists only because frmMain2 recalculates per change (frmMain2.vb:5491-5518); headless code with no subscribers needs no guard — adding a subscriber reintroduces the event-storm problem.
- **Always bind after generating.** Any item the worker creates must end with cave/branch set *then* `BindSegments()` — unbound items silently detach from warping and drift on the next recalculation ([auto-sketch-feasibility.md](auto-sketch-feasibility.md)).
- **Round-trip the whole zip.** `.csz` files can carry attachments, sketch PNGs, 3D chunks beside `_data.xml`; Stage-0 write experiments (if ever) must preserve all entries (`cStorage.SaveTo` writes the full in-memory set, cSurveyPC/cFile.vb:340-380). Prefer: never write XML directly — route writes through the worker.
- **Culture: force invariant.** Set `CultureInfo.InvariantCulture` on the worker thread. `StringToDecimal` (used for distance/bearing/inclination/LRUD, cSurveyPC/cSegment.vb:657-664) defends dot decimals by replacing '.' with the host decimal separator before a culture-aware `TryParse` (cSurveyPC/modNumbers.vb:229-231), but other sites use plain `Convert.ToDecimal` in the current culture (`ToDecimal`, modNumbers.vb:220-226) and values containing the host's group separator can still misparse — force invariant anyway.
- **Never call `cSurvey.Check`, always `Load`.** Check reads physical keyboard state and hard-fails on unset therion.path (cSurveyPC/cSurvey.vb:887-919).
- **Pin the option instances.** One `cOptionsExport`/`cOptionsPreview` per design per worker lifetime — a fresh instance per render defeats the draw cache and breaks `ToSvg`.

## Gotchas

- **The DevExpress build blocker is a *build*-time problem, not a runtime one for the worker** — but Stage 1 cannot even start until someone with the DevExpress v24.2 license compiles cSurveyPC + facade. Mitigation: the repo owner builds; or the facade ships as a tiny separate patch the owner applies. Stage 0 needs no build at all.
- **therion.exe is a hard dependency** for `recalculate` and `export_pdf` (`cCalculateTherionMissingException` when `therion.path` is unset; `CalculateTypeEnum.Internal` is dead — the property setter hard-codes Therion, cSurveyPC/cProperties.vb:521). `validate_survey` should check the setting up front and tell the user how to fix it.
- **The sync therion runner can block on a hidden MsgBox** after 120 s (cSurveyPC/modMain.vb:388-395). The facade must route *all* therion runs through `ExecuteTherionAsync`. Note the in-Load calculation (import step 4) uses the sync path internally (✓ Calculate/cCalculate.vb:1688 calls `modMain.ExecuteTherion`) — very large surveys imported headless can hit it; mitigation: pre-warn on >120 s surveys or raise the timeout in the facade-driven recalculate and treat the in-Load result as advisory.
- **GDI+ headless works in a console session but not reliably in session-0 services** *(inferred, standard GDI+ behavior)* — run the worker as a user process, not a Windows service. WPF (`cHolosViewer`) is excluded entirely: needs STA + real rendering; 3D is out of scope.
- **`debug=1` fixes therion temp filenames** (`_therion_input.th`, cCalculate.vb:1613) — never set `bIsInDebug` in the worker or two concurrent recalculations clobber each other.
- **`Load` swallows first-calculation errors** for version `-1` files: `import_topodroid` must always run its own explicit `recalculate` to surface missing-session/orphan errors as tool output.
- **Merging repeat trips into a master survey is NOT covered by any tool above** — the merge loop is 740 lines welded into frmMain2 reading dialog controls; automating it means re-implementing per [topodroid-end-to-end-trace.md](topodroid-end-to-end-trace.md) Appendix Case 2 (duplicate detection must use data-match, not GUID — ids are regenerated per load). Treat as a post-Stage-3 feature.
- **Station names are case-sensitive in the calculate dictionary** — created without `StringComparer.OrdinalIgnoreCase` (commented out) and case-duplicate stations are silently dropped, with a comment naming TopoDroid same-name-different-case stations as the suspected cause (cSurveyPC/Calculate/cCalculate.cTrigPoints.vb:175-185) — though fix-ups uppercase everything; surveys mixing sources can still collide; `validate_survey` should flag case-variant duplicates.
- **`pGetFileCreatPostProcessed` returns True on exception** (cSurvey.vb:1750-1751): a malformed `<properties>` silently *skips* TopoDroid fix-ups and then dies on duplicate integer ids — `import_topodroid` should pass `FixTopoDroid` explicitly (it does) rather than rely on detection.
- **Bitness must match the installed build** (cSurveyPC builds x86 or x64 per configuration, cSurveyPC.vbproj) — worker and cSurveyPC.exe must agree or the reference fails at load.

## Related docs

- [automation-surface.md](automation-surface.md) — architecture candidates, Friend wall, settings/localization bootstrap detail
- [topodroid-end-to-end-trace.md](topodroid-end-to-end-trace.md) — line-level import trace + minimal programmatic import appendix
- [auto-sketch-feasibility.md](auto-sketch-feasibility.md) — pipelines A/B/C, generator internals, profile-stub gap, QA raycast
- [data-model-and-file-format.md](data-model-and-file-format.md) — full `_data.xml` schema for Stage-0 tools
- [topodroid-import.md](topodroid-import.md) — supported TopoDroid artifacts and symbol mapping
- [calculation-engine.md](calculation-engine.md) — therion round-trip, invalidation, typed calculate errors
- [drawing-engine.md](drawing-engine.md) — item/layer factories, points grammar, binding/warping invariants
- [rendering-and-plot.md](rendering-and-plot.md) — headless PNG/SVG render recipes
- [exports-and-printing.md](exports-and-printing.md) — TherionPad PDF pipeline, SVG writer
- [ui-map.md](ui-map.md) — build notes (DevExpress blocker), where the UI calls the same paths
- [human-workflow-and-glossary.md](human-workflow-and-glossary.md) — what a "finished map" means to the user
