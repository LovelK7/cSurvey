# CLAUDE.md — cSurvey orientation for AI agents

cSurvey is Windows desktop cave-survey software (VB.NET WinForms, .NET Framework 4.8, ~320k LOC): users import or type survey shots (distance/azimuth/inclination + splays), the app computes station coordinates, and users draw the cave map (plan + extended-elevation profile) over the computed centerline, then print/export it. This fork's goals: understand the codebase deeply, streamline the **TopoDroid → finished map** workflow, and build automation (eventually an MCP server) on top of it.

**Detailed subsystem documentation lives in [dev/reference/](dev/reference/README.md). Read the relevant doc before working in a subsystem — every doc is grounded with `path:line` citations.**

## Repository layout

| Path | What it is |
|---|---|
| `cSurveyPC/` | The application (single project, `cSurveyPC.sln`). Nearly all live code is **flat in the project root**. |
| `cPrintController/` | Print-dialog suppression + reimplemented print preview control (UI plumbing only). |
| `cave_model/` | Native C++/CLI mesh generator (`DNetCMCave`) used by the 3D "Holos" viewer. |
| `HelixToolkit.Wpf.cSurveySpecialized/` | 3-file HelixToolkit fork (terrain from in-memory elevation instead of .bt files). |
| `cSurveyDiagnostics/`, `cSurveyUpdateVersion/` | Crash reporting; build version stamper (post-build step). |
| `cSurveyPC/data/` | **The real, tracked test corpus** — nine `.csz` surveys. See "Test corpus" below; it is centerline-only, which matters. |
| `dev/` | **Fork R&D workspace, organized into four zones. Start at [dev/README.md](dev/README.md)** — the operating manual for the zones below and the develop→validate→productionize loop. |
| `dev/reference/` | **Zone 1 — architecture** (how cSurvey works; stable, `path:line`-grounded). This is the AI-oriented knowledge base; index at [dev/reference/README.md](dev/reference/README.md). |
| `dev/production/` | **Zone 2 — what we run routinely**: the pre/post-processing `tools/` (incl. the Stage-0 `inspect_survey.py`), the standing SOP [tdx-processing-protocol.md](dev/production/tdx-processing-protocol.md), and reusable `methods/`. Index: [dev/production/README.md](dev/production/README.md). |
| `dev/projects/` | **Zone 3 — the dev loop, one folder per work item**: `NNNN-slug/{brief.md, log.md, runs/, findings/}`, cradle-to-grave. Status board + lifecycle: [dev/projects/README.md](dev/projects/README.md). Instrumented runs live in each project's `runs/` (RUNLOG + inspector JSON tracked; survey snapshots gitignored). |
| `dev/decisions/` | **Zone 4 — portfolio-strategy log.** [roadmap-decisions.md](dev/decisions/roadmap-decisions.md) is where to learn current project state and what's actually being worked on. |
| `dev/sessions/` | **Session journal** ([SESSIONS.md](dev/sessions/SESSIONS.md)) — one terse block per working session (what changed, how it went, next). Append one at the end of every session. |
| `dev/backlog/` | Parked feature ideas for later (e.g. custom TDX↔cSurvey symbol palette), kept out of the four zones deliberately. |
| `G:\My Drive\Share\TDX` | **The user's TopoDroid handoff folder** (phone syncs exports here via Google Drive; additional working directory). Holds the real TopoDroid survey saves from the 2026-07-19 run. ⚠ The pristine raw export was lost in a file move — recovery pending, SHA256 in the run log. |
| `dev/literature/` | **Gitignored — absent from a fresh clone.** Manuals: `csurvey.it.en.pdf` (machine-translated English — see translation traps below), `cSurvey_RAD_Paride.pdf` (tutorial); TopoDroid manuals + symbol repo under `topodroid/`. |
| `dev/example/` | **Gitignored — absent from a fresh clone, and cited by stale paths throughout `dev/reference/`.** The docs' `dev/example/buless.csz` is really `cSurveyPC/data/buless_test1.csz`. |

### Dead code traps (do not edit these)
- `cSurveyPC/frmMain.vb` (25k lines) is a **legacy duplicate** of `frmMain2.vb` and is NOT in the .vbproj. `frmMain2.vb` is the real main window.
- `cSurveyPC/Design/`, `Design2D/`, `Design3D/` folders are **stale 2015 copies**, not compiled. The live classes with the same names sit in the project root.
- `cSurveyPC/cModel3D.vb` is 100% commented out; `cTopoDroidImportHelper.vb` is a 3-line placeholder (the real converter is `cImportTopoDroidHelper.vb`).
- Also not compiled: `cEditToolsDesign.vb`, `cEditToolsPlot.vb`, `cDockContent.vb`, `frmDisto.vb`. When in doubt, check membership in `cSurveyPC.vbproj`.

### Build notes
- Compile blocker: **DevExpress v24.2.13** (~27 GAC-referenced assemblies, no HintPath, plus `licenses.licx`). Domain classes do not use DevExpress — only the UI layer does.
- NuGet `packages/`: EPPlus, ScintillaNET, NAudio, HelixToolkit, CsvHelper, Clipper/Clipper2. Loose DLLs at project root: `GeoUtility.dll`, `Ionic.Zip.dll` (DotNetZip).
- Pre-build `crea file di risorse.bat` (resource generation), post-build `cSurveyUpdateVersion.exe`. `cave_model` is a C++ vcxproj ProjectReference. x86/x64 per configuration.

## Architecture in one page

**Root aggregate.** Everything hangs off `cSurvey.cSurvey` ([cSurveyPC/cSurvey.vb:10](cSurveyPC/cSurvey.vb#L10)): `Properties` (sessions, cave/branch tree, origin, calc modes), `Segments` (shots), `TrigPoints` (stations — *derived* from shot names via `Rebind`), `Plan`/`Profile` (the two 2D designs), `Calculate` (results cache), plus galleries (pens/brushes/cliparts/attachments) and options profiles.

**Persistence.** `.csz` = ZIP (DotNetZip) containing `_data.xml` (the whole survey) + binary assets (`_data\design\<guid>.png`, cliparts, 3D chunks…). `.csx` = the bare XML. Every persisted class follows the hand-written convention `Friend New(Survey, [cFile,] XmlElement)` + `SaveTo(File, Document, Parent)`; attributes are omitted at default values; numbers are InvariantCulture. **All cross-references are strings**: stations by name (UPPERCASE), sessions by `yyyyMMdd_description` IDs, caves by name, branches by backslash paths (`Ramo 1\Ingresso`), drawing points bound to shot **GUIDs** via `S<guid>` tokens. File version const `"1.14"`; a stepwise in-DOM upgrade chain (1.00→1.14) runs in `cSurvey.Load` before object construction.

**Calculation.** cSurvey does NOT solve the survey network itself: `cCalculate.Calculate` ([Calculate/cCalculate.vb:576](cSurveyPC/Calculate/cCalculate.vb#L576)) exports a temp `.th`, **shells out to external `therion.exe`** (user setting `therion.path`), and parses back station XYZ (.plt) + loop errors/declination (log). `CalculateTypeEnum.Internal` exists but is dead — the setter hard-codes Therion. Coordinates: X=east, Y=−north, Z=down, meters, origin station at (0,0,0). Plan projection = (X,Y); profile = extended elevation (D,Z) where D is the per-connection unrolled abscissa. Splays and LRUD become per-shot side points/polygons — the raw material for wall generation. Results persist into `_data.xml`, so loaded files don't recalculate until invalidated.

**Drawing model.** Each design (Plan, Profile) has exactly **7 fixed layers** in z-order: Base=0, Soil, WaterAndFloorMorphologies, RocksAndConcretion, CeilingMorphologies, Borders=5, Signs=6. Items (`cItem*` subclasses, `<item type="n">`) store absolute coordinates in survey meters as a flat `cPoints` list; each point can be **bound to the nearest shot** (`BindedSegment`). Binding is what makes drawings **warp** automatically when the centerline changes after a recalc (affine matrix from old-vs-new shot geometry). An unbound item (empty cave) never warps. The cave outline is `cItemInvertedFreeHandArea` (category CaveBorder) on the Borders layer, and it clips all lower layers.

**Rendering.** `cDesign.Paint` ([cSurveyPC/cDesign.vb:987](cSurveyPC/cDesign.vb#L987)) is the single scene orchestrator for screen, print, raster export, and SVG alike — consumers differ only by the `cOptions*` subclass passed in. Retained-mode caches (`cDrawCache`) are keyed by the **options instance** — always reuse one options object per consumer. The centerline plot renders nothing if no origin station is set.

**Exports.** `modExport.TherionThExportTo` ([cSurveyPC/modExport.vb:3791](cSurveyPC/modExport.vb#L3791)) writes `.th` (+ `.th2` scraps from the drawings + `.thconfig`); therion.exe then compiles finished PDF/SVG/DXF ("TherionPad" ribbon buttons). cSurvey itself has **no PDF writer**. SVG is native via `cDesignPlan/cDesignProfile.ToSvg`. Raster via painting into a Bitmap.

**UI.** Single DevExpress RibbonForm `frmMain2` (20.5k lines). Every ribbon handler is a one-liner delegating to a private `p*` sub that calls the domain — the UI layer is thin and bypassable. Drawing tools come from `designtools.xml` and create items **by reflection** on layer factory methods.

## TopoDroid: what matters

- **The working TDX→cSurvey processing protocol is [dev/production/tdx-processing-protocol.md](dev/production/tdx-processing-protocol.md)** (pre-processor + user-owned mapping config + post-import fixer + visual mapping workbench, all in `dev/production/tools/`; operational since 2026-07-26). Symbol ground truth: [dev/production/tdx-symbol-matrix.md](dev/production/tdx-symbol-matrix.md).
- cSurvey **cannot read TopoDroid's .zip project archive.** The interchange formats are TopoDroid's exports: **`.csx`** (cSurvey's own XML — richest, contains data + phone-drawn sketches; the recommended path), therion `.th` (centerline), and `.th2` (sketches).
- TopoDroid `.csx` files are auto-detected on load (`properties/@creatid="topodroid"` without `creat_postprocessed`) and run through a three-stage fix-up: `modImport.FixTopodroidCSX` (raw DOM: GUID segment ids, uppercase stations), `cImportTopoDroidHelper.ConvertDesign/ConvertItem` (therion-named sketch items → typed layer items, x-sections, signs), `FixTopodroidSurvey` (stamps `import_source`/`import_date`, force-binds every item to the centerline).
- Headless-friendly entry point: `cSurvey.Load(path, LoadOptionsEnum.FixTopoDroid)` forces the whole chain — this is exactly what the UI import does at [frmMain2.vb:11861](cSurveyPC/frmMain2.vb#L11861), with no form involvement.
- **Auto-sketch generator already exists for plan**: `modSegmentsTools.CreatePlanBorderFromSplay` ([cSurveyPC/modSegmentsTools.vb:424](cSurveyPC/modSegmentsTools.vb#L424)) buckets splay endpoints per shot, Clipper-unions the polygons, and emits one cave-border item. Caveats: its only UI entry is a **debug-gated** context menu; it **never binds its output** (call `BindSegments()` afterwards or the border won't warp); it ignores the splay inclination-range filter. The profile equivalent is an **empty stub** (`:645`) — the main missing piece; alternative `CreateBorder3DOutline` uses LRUD, which is typically all-zero in phone-surveyed data.
- The TopoDroid **sending side** (project .zip internals, phone SQLite schema, binary .tdr sketch format, and the exact csx XML TopoDroid emits — verified against TopoDroid's source) is specified in [dev/reference/topodroid/topodroid-zip-and-csx-format.md](dev/reference/topodroid/topodroid-zip-and-csx-format.md) — the basis for a future zip→csx pre-converter and for synthesizing test fixtures.
- Details: [dev/reference/topodroid/topodroid-import.md](dev/reference/topodroid/topodroid-import.md), execution trace and feasibility study in dev/reference.

## Glossary (human term → code)

shot = `cSegment` · station = `cTrigPoint` (derived from shot names) · splay = `cSegment` with `Splay=True` (auto-named `X(n)`) · LRUD = left/right/up/down passage half-widths at a station · centerline/plot = computed shot lines (`cPlotPlan`/`cPlotProfile`) · design = a drawable map view (`cDesignPlan`/`cDesignProfile`) · extended elevation = the unrolled profile view · x-section = `cItemCrossSection` + `cDesignCrossSection` · warping = auto-morph of bound drawing points after recalc · session = survey trip (`cSession`, carries declination + grade) · cave/branch = organizational tree (`cCaveInfo`/`cCaveInfoBranch`) · origin = the station fixed at (0,0,0) · therion = external calc/typesetting engine · scrap = a therion drawing unit (.th2)

**Machine-translation traps in the English manual** (`dev/literature/csurvey.it.en.pdf` — gitignored, may not be present): "jokes" = shots, "cornerstones"/"strongholds" = stations, "plant" = plan, "polygonal" = centerline, "relief" = survey. The manual describes a 2011 build; trust the code and dev/reference over it.

## Invariants and gotchas (violate these and things break silently)

1. **Enum integer values ARE the file format** (layer types, item types/categories, pen/brush types, linetypes, mergemode). Append new values; never renumber.
2. **Calculation prerequisites**: an origin station set, every shot assigned a session, network fully connected — otherwise typed `cCalculateException`s. `therion.exe` configured via `therion.path` setting or every full calc fails.
3. **Station names are case-sensitive in the calc engine** and uppercased on import — a known TopoDroid duplicate-station trap. Names matching `*(*)` are auto-flagged splays.
4. **The Friend wall**: `cCalculate.Calculate`, `modImport`, `modExport`, `modMain` are `Friend` (assembly-internal). External automation must live inside `cSurveyPC` (facade class) or use `InternalsVisibleTo` — see [dev/reference/automation-surface.md](dev/reference/automation-surface.md).
5. **`My.Application.Settings` is initialized only by the WinForms startup pipeline** (~757 read sites); headless hosts must replicate `ReloadSettings` + `LoadLocalizedStrings` or NRE.
6. Domain events (e.g. `OnSegmentsChange`) may fire on worker threads; UI observers must marshal (`SynchronizationContext` — the commit 0c6700b fix). Bulk mutations should suppress per-change recalc (frmMain2 uses push/pop disable flags).
7. **One `cOptions*` instance per render consumer** — it's the draw-cache dictionary key. A fresh instance per frame defeats caching and leaks.
8. Items must carry cave/branch and be bound (`item.BindSegments()`) after programmatic creation, or they won't warp with future data changes.
9. `DesignWarpingMode` can be persistently set to None by a past user "Abort" — silently disables auto-warp.
10. Load is fault-tolerant per-section (Try/Catch → empty collection): **a broken XML section vanishes silently on next save**. Exception: `<segments>` is unguarded and fatal.
11. Headless hazards in otherwise UI-free paths: `ExecuteTherion` pops a modal MsgBox after its 120s timeout (use `ExecuteTherionAsync`); warping can raise a details dialog if `ShowWarpingDetails` is on; `cSurvey.Check` requires UI state — call `Load` directly, never `Check`.
12. UI text is localized via `GetLocalizedString("main.textpartNNN")` — to find code from a screenshot, grep the visible string in `cSurveyPC/*.resx`, then grep the key in `frmMain2.vb`.

## Where to route a problem

| Symptom domain | Look in | Doc |
|---|---|---|
| File won't open / save corrupts | `cSurvey.Load/SaveTo`, `cFile.vb`, version upgrade chain | [data-model-and-file-format.md](dev/reference/data-model-and-file-format.md) |
| Wrong coordinates, loop errors, "calculation failed" | `Calculate/cCalculate.vb`, therion round-trip | [calculation-engine.md](dev/reference/calculation-engine.md) |
| TopoDroid import problems | `modImport.vb`, `cImportTopoDroidHelper.vb`, merge in `frmMain2.pSurveyImportcSurvey` | [topodroid-import.md](dev/reference/topodroid/topodroid-import.md) |
| Drawing detached/warped wrongly, items misbehave | `cItem.vb`, `cPoints.vb`, `cDesignPlan.WarpItemsEx` | [drawing-engine.md](dev/reference/drawing-engine.md) |
| Blank/wrong screen or print output | `cDesign.Paint`, `cPlotPlan/cPlotProfile`, caches | [rendering-and-plot.md](dev/reference/rendering-and-plot.md) |
| Export/print output wrong | `modExport.vb`, `frmPreview.vb`, `modSVG.vb` | [exports-and-printing.md](dev/reference/exports-and-printing.md) |
| "I clicked X and…" | `frmMain2.vb` routing table | [ui-map.md](dev/reference/ui-map.md) |
| 3D view / terrain | `Specialized/cHolosViewer.xaml.vb`, `cSurface.vb` | [3d-and-surface.md](dev/reference/3d-and-surface.md) |
| Automation / MCP design | CLI, scripting engine, Friend wall analysis | [automation-surface.md](dev/reference/automation-surface.md) |
| Domain vocabulary, user workflow | manual + tutorial decoded | [human-workflow-and-glossary.md](dev/reference/human-workflow-and-glossary.md) |

## Conventions when changing code

- VB.NET style of the codebase: Hungarian-ish prefixes (`o` object, `s` string, `i` int/enum, `b` bool), `p*` for private subs, `cXxx` class files. Match it.
- UI strings go through resx localization (it/ru/en variants exist per form); don't hard-code user-facing text.
- Serialization changes must preserve backward compatibility: add attributes with defaults, bump the version const and extend the upgrade chain in `cSurvey.Load` only when unavoidable.

## Test corpus (`cSurveyPC/data/`, nine tracked `.csz`)

Verified by direct inspection 2026-07-16. **The whole corpus is centerline-only** — pick a fixture by what you're testing:

- **`test extend 2.csz`** — the **only file in the repo containing a real drawing item**. Sole ground truth for the `<points data>` / `S<guid>` binding encoding. Use for anything sketch-related.
- **`test splay1.csz`** (7 shots / 4 splays / 56 KB) — smallest file with splays; best fast fixture for splay machinery.
- **`test lrud.CSZ`** (4 shots, 3 with LRUD) — the only focused LRUD case. Note TopoDroid *never* produces LRUD, so this exercises a path phone data doesn't reach.
- **`buless_test1.csz`** (318 shots / 267 splays) — PocketTopo-derived. Representative of phone-surveyed **centerline** (splay-heavy, LRUD zero) and the only multi-entry zip (46 cliparts + 2 MB surface DEM), so it's the right container/asset test. **Trap: it has zero design items** — all 7 plan layers empty. Looks rich, is not. Never use it as a drawing fixture.
- **`snow_2015_yanina.CSZ`** (1496 shots / 1176 splays) — scale/perf case.

**No *tracked* file is a real TopoDroid export** (none carries `creatid="topodroid"`), but real ones live in the user's `G:\My Drive\Share\TDX` handoff folder and in local-only `dev/projects/0002-tdx-symbol-mapping/runs/` snapshots (TopoDroid 6.4.29; 7 shots + 49 splays, 34 flat sketch items → **Pipeline A confirmed and validated end-to-end 2026-07-19**; the pristine raw export awaits re-export — SHA256 in the run log). First contact validated the docs' reconstruction of what TopoDroid emits — details and scorecard in [dev/decisions/roadmap-decisions.md](dev/decisions/roadmap-decisions.md) (2026-07-19 entry). **A raw TopoDroid `.csx` stores sketch items as flat `<item>` children under `<plan>`, not the `<layers>/<layer>/<items>` structure native files use** — tooling that counts only the native shape reports zero items for a file with a full sketch. Where a real file ever contradicts the docs, the file wins.
