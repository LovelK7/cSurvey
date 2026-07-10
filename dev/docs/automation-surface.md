# Automation surface: CLI, scripting, external-tool orchestration (MCP foundation)

## Purpose

This doc inventories every existing way to drive cSurvey without a human clicking the UI: the command-line parameters the exe accepts, the built-in runtime scripting engine, which domain operations are already callable without a form, and how the app shells out to external tools (Therion, Blender, MeshLab). It closes with a grounded comparison of three possible MCP-server architectures for the target workflow "import TopoDroid data → auto-generate sketch → save/export".

## Domain concepts

- **Command()** — the classic VB.NET function returning the raw command line; cSurvey parses it itself instead of using `My.Application.CommandLineArgs`.
- **Script / formula** — a user-supplied VB.NET or C# snippet compiled *at runtime* with CodeDOM into a throwaway assembly that references the running `cSurveyPC` exe. Used both as an interactive "macro" console and as boolean/value formulas stored in the survey file.
- **cScriptBag prefix format** — how a script is stored in a string/XML attribute: `vb#>` or `c#>` prefix selects the language; an additional `>` marks the code as "unboxed" (already a complete method body, not an expression to wrap) (cSurveyPC/cScript.vb:158-183).
- **Friend accessibility wall** — VB `Module`s default to `Friend`, so "Public" functions inside `Module modImport`/`modExport`/`modMain` are invisible to any *other* assembly (including runtime-compiled scripts and any external headless host). This is the single most important constraint for architecture decisions.
- **cEnvironmentSettings** — app settings backed by registry key `HKCU\Software\Cepelabs\cSurvey`, exposed as `My.Application.Settings`; a second, in-memory instance is `My.Application.RuntimeSettings` (cSurveyPC/ApplicationEvents.vb:53-62, 69, 122-135).

## Architecture

There is **no batch/headless mode, no IPC server, no COM automation, and no macro auto-run** in cSurvey today. The whole automation surface is:

1. **Command line → open a file.** `frmMain2`'s constructor parses `Command()` into a `cCommandLineParameters` collection (cSurveyPC/frmMain2.vb:13858) and `frmMain_Load` opens the file named there (cSurveyPC/frmMain2.vb:2461-2478). Nothing else is scriptable from the shell.
2. **Runtime scripting engine** (`cSurveyPC.cSurvey.Scripting` namespace, cSurveyPC/cScript.vb). One engine, five entry points: the interactive Script dock panel, highlight conditions, segment replicate-info formulas, surface-grid formulas, and cave-register data binding. Scripts receive the live `cSurvey` object; there is no way to trigger a script from outside the UI.
3. **Headless-capable domain core.** The full pipeline *open → TopoDroid fix → calculate → save → Therion export* is implemented in non-form classes (`cSurvey`, `cFile`, `modImport`, `cCalculate`, `modExport`) that never show UI on that path. `frmMain2` itself proves this by running the exact pipeline on a second in-memory survey during "import from cSurvey file" (cSurveyPC/frmMain2.vb:11860-11865).
4. **External tools via `Process`.** Therion is the load-bearing one: when a survey's calculate mode is `Therion`, `cCalculate` writes `.th`/`.thconfig` files to %TEMP%, runs `therion.exe`, and parses the resulting `.plt`/`.xvi`/log (cSurveyPC/Calculate/cCalculate.vb:1596-1719). Blender and MeshLab follow the same write-script → run-exe → read-output pattern.
5. **Network code is client-only.** `modNetwork` + `cNetHistory.vb` implement an HTTP POST client (cookies, `login.php`, `get.php`) for a cave-register web service — nothing listens for inbound automation (cSurveyPC/modNetwork.vb:13-61, cSurveyPC/cNetHistory.vb:43-117).

Data-flow narrative for the only CLI-drivable flow: user runs `csurveypc.exe "C:\cave.csz"` → `MyApplication_Startup` loads registry settings and localized strings (cSurveyPC/ApplicationEvents.vb:64-83) → `frmMain2.New` parses the command line (cSurveyPC/frmMain2.vb:13858-13860) → `frmMain_Load` calls `pSurveyLoad(filename)` (cSurveyPC/frmMain2.vb:2470) → `pSurveyLoad` constructs a fresh `cSurvey`, calls `cSurvey.Load(Filename)` (cSurveyPC/frmMain2.vb:780, 808) → `Load` unzips `_data.xml` via `cFile`, applies `modImport.FixTopodroidCSX` if the file was created by TopoDroid (cSurveyPC/cSurvey.vb:940-945), applies version migrations, and populates the object model.

### Command-line parameter inventory (complete)

Parsing site: `cCommandLineParameters.FromCommandLine` (cSurveyPC/cCommandLineParameters.vb:106-145) — splits on spaces (quote-aware), each token is `key=value` or a bare key; keys are lower-cased. Consumed only in the two main-form constructors/Load handlers (`frmMain2.vb` is the active form per `OnCreateMainForm`, cSurveyPC/My Project/Application.Designer.vb:34-36; `frmMain.vb` is the legacy copy with identical logic at cSurveyPC/frmMain.vb:18669).

| Parameter | Where read | Effect |
|---|---|---|
| *(bare argument, exactly one)* | cSurveyPC/frmMain2.vb:2469-2470 | Treated as a survey filename; opened via `pSurveyLoad(name, False)`. `.crsx/.crsz` route to resurvey mode (cSurveyPC/frmMain2.vb:772-773). This is also what Explorer file association and the taskbar jump list pass (cSurveyPC/frmMain2.vb:2500). |
| `filename=<path>` | cSurveyPC/frmMain2.vb:2472-2475 | Same as above, usable when other parameters are present. |
| `debug=<0/1>` | cSurveyPC/frmMain2.vb:13859 | Sets `modMain.bIsInDebug`: verbose behavior, fixed (non-GUID) Therion temp filenames (cSurveyPC/Calculate/cCalculate.vb:1613), skin menu suppression (cSurveyPC/frmMain2.vb:2462). |
| `modernos=<0/1>` (default 1) | cSurveyPC/frmMain2.vb:13860 | If 1, `bIsModernOS` is computed from the Windows version; passing 0 forces legacy rendering paths. |

That's all. There are no export/import/quit/silent flags. `IsSingleInstance = false` (cSurveyPC/My Project/Application.Designer.vb:27), so every invocation is an independent process and there is no `StartupNextInstance` message channel either.

### Scripting engine

- **Languages**: VB.NET and C#, selected by enum `LanguageEnum` (cSurveyPC/cScript.vb:12-15) or by `cScriptBag` prefix (`vb#>`, `c#>`).
- **Compilation**: `cScript.pCodeInitialize` wraps the user code in a class `cSurvey.cScriptEvaluator` with a `SetSurvey(Survey As cSurveyPC.cSurvey.cSurvey)` member, adds imports (System/Xml/Data/Drawing + `cSurveyPC.cSurvey`), and compiles in-memory with `VBCodeProvider`/`CSharpCodeProvider`, referencing system DLLs plus **the currently executing cSurveyPC assembly** (cSurveyPC/cScript.vb:281-353). `cScript.Eval(name, params)` invokes the method via reflection and stores any exception in `RuntimeError` (cSurveyPC/cScript.vb:355-367).
- **Cached variant**: `cClass` compiles a named class to a DLL on disk under `<CommonAppData>\csurvey_cache`, keyed by code hash + bitness, and reuses it across runs (cSurveyPC/cScript.vb:104-141, 370-396).
- **Object model exposed**: whatever is `Public` in the cSurveyPC assembly. Because the script lives in a *separate* generated assembly, `Friend` members are invisible: a script **can** `New cSurvey()`, `Survey.Load(...)`, `Survey.SaveTo(...)`, `Survey.Segments.Append(...)` (cSurveyPC/cSegments.vb:260, 272), read `Survey.TrigPoints`, but **cannot** call `Calculate.Calculate` (Friend, cSurveyPC/Calculate/cCalculate.vb:576) or anything in `modImport`/`modExport` (Friend modules, cSurveyPC/modImport.vb:8, cSurveyPC/modExport.vb:20).
- **Trigger points** (all UI-initiated; none run automatically on load/save/timer):
  1. **Script dock panel** ("run macros" console, `cDockScript`): code is wrapped as `public sub CustomCode(Survey as object, Debug as object)` and executed on a `BackgroundWorker` with `Survey` = the open survey and `Debug.Print(...)` piped to the dock's output box (cSurveyPC/DockControl/cDockScript.vb:55-64, 114-135, cSurveyPC/cScriptDebug.vb:21-24). Scripts load/save as standalone `.CScriptX` XML files (`<cscript language=...>code</cscript>`, cSurveyPC/DockControl/cDockScript.vb:164-222) — they are *not* stored in the survey.
  2. **Highlight conditions** (per-shot/per-station coloring rules): boolean expression wrapped as `GetHighlight(Details)`, persisted *inside the survey XML* as attribute `cnd` of element `hlsd` in cScriptBag format (cSurveyPC/cProperties.cHighlightsDetail.vb:295-324, 332, 344).
  3. **Segment replicate-info formulas**: `ReplicateFormula(CurrentSegment)` mutates fields across a range of shots; built ad-hoc in the dialog, not persisted (cSurveyPC/frmSegmentsReplicateInfo.vb:186-218).
  4. **Surface/DEM grid formulas**: `FormulaApply(Row, Col, Data)` transforms elevation-grid cells (cSurveyPC/frmSurface.vb:689-698).
  5. **Cave-register data binding**: property-path snippets evaluated per row (cSurveyPC/frmCaveRegister.vb:116-119).
  - Shared editor for 2-4: `frmScriptFormulaEditor` (syntax check via trial compile, cSurveyPC/frmScriptFormulaEditor.vb:48-70).
- **Could scripts drive import/export?** Partially. A dock script can open another survey (`Load` accepts `LoadOptionsEnum.FixTopoDroid`, cSurveyPC/cSurvey.vb:929-936), copy/append segments, and `SaveTo`. It cannot recalculate stations or export Therion because of the Friend wall, and there is no way to launch a script without the WinForms app and its dock panel. So scripting is a prototyping aid, not an automation channel.

### Headless capability map (what works without a form)

Verified decoupled (constructible/callable with no UI):

- `cSurvey.New()` — parameterless, builds the whole object graph (segments, trigpoints, designs, calculate engine) with zero form references (cSurveyPC/cSurvey.vb:659-701).
- `cSurvey.Load(Filename, LoadOptions)` — Public; opens `.csz/.csx`, auto-applies `modImport.FixTopodroidCSX` when `properties@creatid="topodroid"` and not yet post-processed, or when `LoadOptionsEnum.FixTopoDroid` is passed (cSurveyPC/cSurvey.vb:936-945, detection helpers at 1747-1769). Progress/log are events (`OnProgress`, `RaiseOnLogEvent`) — safe with no subscribers.
- `cSurvey.SaveTo(Filename|Stream|cFile, SaveOptionsEnum)` — Public (cSurveyPC/cSurvey.vb:1864-1882).
- `cFile`/`cStorage` — pure XML + DotNetZip (`Ionic.Zip`), reads/writes `_data.xml` plus sibling zip entries (attachments, sketch images, 3D chunks…) (cSurveyPC/cFile.vb:66-112, 340-403).
- `cImportTopoDroidHelper` — **Public Class with Public Shared methods** `GetTopodroidVersion`, `ConvertDesign`, `ConvertCrossSection` that turn TopoDroid XML drawing items into cSurvey design items (cSurveyPC/cImportTopoDroidHelper.vb:6, 50-66). This is the TopoDroid sketch converter, and it is externally reachable.
- `cCalculate.Calculate(PerformWarping)` — **Friend** (cSurveyPC/Calculate/cCalculate.vb:576). Internal mode (`CalculateTypeEnum.Internal`, cSurveyPC/cSurvey.vb:114-118) is pure .NET; Therion mode shells out (see below). No `MsgBox` anywhere in the class.
- `modExport.TherionThExportTo(Survey, Filename, Dictionary, Options)` (cSurveyPC/modExport.vb:3791) and `TherionThExportTo_Version1` (cSurveyPC/modExport.vb:3140) — take only domain objects and write `.th`/scrap files — but live in a **Friend module**.
- Precedent for the whole chain: `frmMain2.pSurveyImportcSurvey` does `New cSurvey` → `Load(Filename, FixTopoDroid)` → `If Not Calculate.LoadedFromFile Then Invalidate() : Calculate.Calculate(True)` on a background survey with no window attached to it (cSurveyPC/frmMain2.vb:11860-11865).

Form-entangled / headless blockers:

1. **The Friend wall** (see Domain concepts). No `InternalsVisibleTo` exists anywhere in the repo (grep across all AssemblyInfo/projects returned nothing). External code gets `cSurvey`, `cFile`, `cImportTopoDroidHelper`, `cSegments` — but not `Calculate.Calculate`, `modImport.*`, `modExport.*`, `modMain.*`.
2. **`My.Application.Settings`/`RuntimeSettings` are only initialized by the WinForms startup event** `MyApplication_Startup` (cSurveyPC/ApplicationEvents.vb:64-83; `ReloadSettings` at 53-62). Domain code reads them in ~47 files / 757 call sites, including the calculate path (`therion.path`, `therion.trigpointsafename`, … at cSurveyPC/Calculate/cCalculate.vb:1601-1687) and `cSurvey.Check` (cSurveyPC/cSurvey.vb:897). A host that loads the assembly without running the `WindowsFormsApplicationBase` pipeline gets `Nothing` there → NRE.
3. **Localized strings**: `modMain.GetLocalizedString` requires `LoadLocalizedStrings` to have created a file-based `ResourceManager` reading a `resources` file from the exe's directory (cSurveyPC/modMain.vb:414-426); `cSurvey.Load` calls it for progress text (cSurveyPC/cSurvey.vb:938). Headless host must run from (or point `GetApplicationPath`, cSurveyPC/modMain.vb:42-47, at) the cSurvey install dir and trigger `LoadLocalizedStrings` (Friend → reflection).
4. **Stray MessageBox in non-form helpers**: `cBlenderHelper` pops `MessageBox.Show` on missing paths/completion (cSurveyPC/cBlenderHelper.vb:112-121, 217) and KML export has one guard MsgBox (cSurveyPC/modExport.vb:548). The open→import→calc→save→Therion-export path has one: the synchronous `modMain.ExecuteTherion` (the one `cCalculate` calls) shows a MsgBox asking whether to keep waiting when therion.exe exceeds the 120 s timeout (cSurveyPC/modMain.vb:388-395) — a headless host must either guarantee fast surveys, use `ExecuteTherionAsync` (which throws `TimeoutException` instead, cSurveyPC/modMain.vb:344-355), or accept a possible hidden modal prompt. Elsewhere on that path there are no message boxes (grep over cSurvey.vb/cSegment*/cTrigPoint*/cDesign*/modImport: 0 hits).
5. Project is `WinExe`, .NET Framework 4.8, built x86 or x64 per configuration (cSurveyPC/cSurveyPC.vbproj:9,15,60,93) — a host must match bitness and have the DevExpress/ScintillaNET/Ionic dependencies resolvable (easiest: run beside the installed exe).

**Bottom line: yes, a headless .NET Framework host referencing `cSurveyPC.exe` can do open→import→save without UI today** (those members are Public), but *recalculation and Therion export require crossing the Friend wall* (one `InternalsVisibleTo` line, or making a small public facade, or reflection), and `My.Application.Settings`/localized resources must be initialized first (reflection or the same facade).

### Existing IPC / inter-process integration (question 4)

- **None inbound.** Grep for named pipes / remoting servers / sockets / `HttpListener` / `ServiceHost` / DDE finds nothing; the only `ComVisible(true)` is a copied `PrintPreviewControl` class in the separate cPrintController project (cPrintController/cPrintController.cs:203), not an automation API. `System.Runtime.Remoting` is referenced only for `CallContext` in cUndo (cSurveyPC/cUndo.vb:4).
- **Outbound HTTP client**: `cSurvey.Net.cNetCaveRegister` logs into a cave-register web service and fetches XML (cSurveyPC/cNetHistory.vb:43-117) via `modNetwork.PostValues` (cSurveyPC/modNetwork.vb:13-61).
- **Outbound process spawning** (the pattern to copy for external orchestration):
  - Therion: `modMain.ExecuteTherion` / `ExecuteTherionAsync` — hidden window, redirected stdout with a `DataReceivedEventHandler`, `THERION` env var, temp working dir, 120 s timeout (cSurveyPC/modMain.vb:298-318, 363-383). Config written by `modExport.TherionCreateConfig` (cSurveyPC/modExport.vb:795-833); the calculate engine then parses the `.plt`, two `.xvi` files and the log (cSurveyPC/Calculate/cCalculate.vb:1681-1719).
  - Blender: `cBlenderHelper.DecimateModel/MergeModel` write an embedded Python script to %TEMP% and run `blender --background --python <script> -- <args>` (cSurveyPC/cBlenderHelper.vb:103-160, 162-218).
  - MeshLab: same `ProcessStartInfo` pattern (cSurveyPC/cMeshLabHelper.vb:79-90).
  - Clipper is *not* external — it's an in-process polygon library (cSurveyPC/modClipper.vb) with GDI+ conversion helpers in `cClipperHelper` (cSurveyPC/cClipperHelper.vb:5-49).

## Key classes & files

| File | Class/Module | Responsibility |
|---|---|---|
| cSurveyPC/cCommandLineParameters.vb | `cCommandLineParameters`, `cCommandLineParameter` | Quote-aware `key=value` command-line parser (keys lower-cased) |
| cSurveyPC/frmMain2.vb:13858, 2461-2478 | `frmMain2` | Only consumer of the command line; opens the named file on load |
| cSurveyPC/My Project/Application.Designer.vb | `MyApplication` | `IsSingleInstance=false`, `MainForm=frmMain2` |
| cSurveyPC/ApplicationEvents.vb | `MyApplication` (partial) | Startup: registry settings (`cEnvironmentSettings`), culture, localized strings; custom `Settings`/`RuntimeSettings` properties |
| cSurveyPC/cScript.vb | `Scripting.cScript`, `cClass`, `cScriptBag`, `cScriptHelper` | Runtime CodeDOM compiler + reflection `Eval`; script string format; on-disk assembly cache |
| cSurveyPC/cScriptDebug.vb | `cScriptDebug` | `Debug.Print` object handed to dock scripts (event-based output) |
| cSurveyPC/DockControl/cDockScript.vb | `cDockScript` | Interactive script console; wraps code as `CustomCode(Survey, Debug)`; `.CScriptX` load/save |
| cSurveyPC/frmScriptFormulaEditor.vb | `frmScriptFormulaEditor` | Shared formula editor dialog (compile-check via host-supplied full code) |
| cSurveyPC/cProperties.cHighlightsDetail.vb | `cHighlightsDetail` | Highlight condition scripts persisted in survey XML (`hlsd@cnd`) |
| cSurveyPC/Dynamic.vb | `XSystem.Linq.Dynamic.*` | Vendored Dynamic-LINQ string-expression parser (grid filtering; unrelated to cScript engine) |
| cSurveyPC/cSurvey.vb | `cSurvey.cSurvey` | Root aggregate; Public `New`/`Load`/`SaveTo`/`Check`; TopoDroid detection + file-version migration on load |
| cSurveyPC/cFile.vb | `cFile`, `Storage.cStorage` | `.csz` (DotNetZip) / `.csx` container; `_data.xml` + binary entries |
| cSurveyPC/modImport.vb | `modImport` (Friend) | `FixTopodroidCSX` (segment-ID regeneration etc.), Therion th2 import, GPX/KML waypoints |
| cSurveyPC/cImportTopoDroidHelper.vb | `cImportTopoDroidHelper` (Public) | Converts TopoDroid drawing XML into design items (`ConvertDesign`, `ConvertCrossSection`) |
| cSurveyPC/Calculate/cCalculate.vb | `Calculate.cCalculate` | Station-coordinate computation; `Friend Calculate()`; Therion mode drives therion.exe |
| cSurveyPC/modExport.vb | `modExport` (Friend) | `TherionThExportTo`, `TherionCreateConfig`, KML/VTopo/Excel exports |
| cSurveyPC/modMain.vb | `modMain` (Friend) | `ExecuteTherion(Async)`, `GetLocalizedString`/`LoadLocalizedStrings`, `bIsInDebug`, paths |
| cSurveyPC/cEditTools.vb:134 | `cEnvironmentSettings` | Registry-backed settings store used by `My.Application.Settings` |
| cSurveyPC/cSharedSettings.vb | `cSharedSettings` | Per-survey key/value store persisted in `_data.xml` (`sharedsettings/values`) |
| cSurveyPC/modNetwork.vb, cSurveyPC/cNetHistory.vb | `modNetwork`, `Net.cNetCaveRegister` | HTTP POST client for cave-register web service (outbound only) |
| cSurveyPC/cBlenderHelper.vb, cSurveyPC/cMeshLabHelper.vb | `cBlenderHelper`, `cMeshLabHelper` | Shell-out patterns to Blender/MeshLab (mesh decimate/merge) |
| cSurveyPC/frmTherionPad.vb | `frmTherionPad` | Small Therion console form; raises export events handled by frmMain2 |
| cSurveyPC/cLocalSecurity.vb | `cLocalSecurity` | TripleDES string encryption (stored credentials) |
| cSurveyPC/cWindowsObjects.vb | `clipboardChangeNotifier` | Clipboard viewer chain (UI utility, not IPC) |

## Key flows

### 1. Startup with a file argument (the only CLI flow)

1. cSurveyPC/My Project/Application.Designer.vb:34-36 — WinForms `MyApplication` creates `frmMain2` as main form (no single-instance).
2. cSurveyPC/ApplicationEvents.vb:64-83 — `Startup` event: `ReloadSettings()` reads `HKCU\Software\Cepelabs\cSurvey` into `My.Application.Settings`, creates `RuntimeSettings`, sets culture, calls `modMain.LoadLocalizedStrings`.
3. cSurveyPC/frmMain2.vb:13858-13860 — form constructor: `oCommandLine = New cCommandLineParameters(Command)`; reads `debug`, `modernos`.
4. cSurveyPC/frmMain2.vb:2461-2478 — `frmMain_Load`: single bare arg or `filename=` → `pSurveyLoad(path, False)`.
5. cSurveyPC/frmMain2.vb:776-808 — `pSurveyLoad`: `cSurvey.Check(path)` (verifies file, and that `therion.path` is configured if the survey's calculate mode is Therion, cSurveyPC/cSurvey.vb:887-919) → `New cSurvey` → `oSurvey.Load(Filename)`.
6. cSurveyPC/cSurvey.vb:940-945 — `Load`: `cFile` unzips `_data.xml`; if `properties@creatid="topodroid"` and `creat_postprocessed=0`, run `modImport.FixTopodroidCSX(oXml)` before parsing.

### 2. Headless-style import + calculate (the in-app precedent for an MCP host)

1. cSurveyPC/frmMain2.vb:11860 — `Dim oImportSurvey As New cSurvey.cSurvey` (no form attached).
2. cSurveyPC/frmMain2.vb:11861 — `oImportSurvey.Load(Filename, LoadOptionsEnum.FixTopoDroid)` — forces the TopoDroid fix regardless of `creatid`.
3. cSurveyPC/frmMain2.vb:11862-11865 — if the file carried no calculate data (`Calculate.LoadedFromFile` false): `Invalidate()` then `Calculate.Calculate(True)` (Friend call — legal only inside the assembly).
4. cSurveyPC/frmMain2.vb:11880-11881 — `Properties.CreatorID = "TopoDroid"` branch logs source version; drawing items were already converted by `cImportTopoDroidHelper` during the fix/import path.
5. From here the survey is normally merged into the open one via the `frmImportcSurvey` dialog — the merge UI is the only form-bound part.

### 3. Calculate via Therion (external-tool orchestration blueprint)

1. cSurveyPC/Calculate/cCalculate.vb:1595-1603 — `pCalculateSegments`: if `Survey.Properties.CalculateType = Therion`, read `therion.path` from `My.Application.Settings`; throw `cCalculateTherionMissingException` if empty.
2. cSurveyPC/Calculate/cCalculate.vb:1613-1630 — build %TEMP% filenames (`_therion_<guid>_input.th`, `_output.plt`, `_output_plan.xvi`, `_output_profile.xvi`, `_config.thconfig`, `_log.log`).
3. cSurveyPC/Calculate/cCalculate.vb:1663-1676 — `modExport.TherionThExportTo(oSurvey, inputTh, dictionary, options)` writes the survey data as Therion source.
4. cSurveyPC/Calculate/cCalculate.vb:1681-1685 — compose `export model/map` commands; `modExport.TherionCreateConfig` writes the thconfig.
5. cSurveyPC/Calculate/cCalculate.vb:1687-1688 — `modMain.ExecuteTherion(thPath, iniPath, "config -l log", AddressOf pProcessOutputHandler)` (cSurveyPC/modMain.vb:363: hidden window, stdout→survey log, `THERION` env var).
6. cSurveyPC/Calculate/cCalculate.vb:1693-1719 — parse the log (meridian convergence, geomag declination, loop errors) and then the `.plt`/`.xvi` outputs into station coordinates.

### 4. Running a dock script (the "macro" flow)

1. cSurveyPC/frmMain2.vb:13922-13925 — `cDockScript` instantiated and docked; `SetSurvey(oSurvey, language)` after each load (cSurveyPC/frmMain2.vb:838).
2. cSurveyPC/DockControl/cDockScript.vb:114-118 — Run button: syntax check (trial compile), then `bwScript.RunWorkerAsync(code)`.
3. cSurveyPC/DockControl/cDockScript.vb:55-64 — code wrapped as `public sub CustomCode(Survey as object, Debug as object)`.
4. cSurveyPC/cScript.vb:281-353 — CodeDOM compile in-memory referencing the running exe; instance created; `SetSurvey(oSurvey)`.
5. cSurveyPC/DockControl/cDockScript.vb:127-129 — `oScript.Eval("CustomCode", {oSurvey, oDebug})` on the worker thread; `cScriptDebug.OnPrint` events marshalled to the output box (152-158).

## How to modify safely

- **Do not repurpose `cCommandLineParameters` keys.** Any bare single argument is interpreted as a filename (cSurveyPC/frmMain2.vb:2469); adding a flag-style bare switch would be swallowed by the file-open path. New parameters should use `key=value` form and be read in the `frmMain2` constructor next to `debug`/`modernos`.
- **If you add a headless/automation entry point, put it inside the cSurveyPC assembly** (e.g. a `modAutomation` invoked from `frmMain2.New` before any dock/UI creation, or an `InternalsVisibleTo` grant). Everything important (`Calculate.Calculate`, `modExport.TherionThExportTo`, `modImport.FixTopodroidCSX`, `modMain.LoadLocalizedStrings`) is Friend; hoisting these to Public one-by-one is the alternative but touches more call-site expectations.
- **Initialize before touching domain code headless**: `My.Application.Settings`/`RuntimeSettings` (ApplicationEvents.vb:53-69) and `modMain.LoadLocalizedStrings` (modMain.vb:414) must be set up, or `cSurvey.Load` and `cCalculate` will NRE on the first `GetSetting`/`GetString`. Keep this invariant if you refactor startup.
- **Script format compatibility**: the `vb#>`/`c#>`/`>` prefixes of `cScriptBag` are persisted inside survey files (highlight `hlsd@cnd`); changing prefixes breaks existing surveys. The generated wrapper signatures (`GetHighlight`, `CustomCode`, `ReplicateFormula`, `FormulaApply`) are effectively public API for users' saved formulas.
- **Assembly-cache invalidation**: `cClass` reuses cached DLLs keyed by code hash + revision + bitness (cSurveyPC/cScript.vb:381-387). If you change the generated wrapper code, bump the revision argument or stale cached assemblies with the old shape will be loaded.
- **Preserve zip round-tripping**: `.csz` may contain attachments, sketch images, 3D chunk data etc. beside `_data.xml` (e.g. cSurveyPC/cAttachments.vb:229, cSurveyPC/cItemSketch.vb:584). Any external tool rewriting `_data.xml` must re-add all other entries (`cStorage.SaveTo` writes the whole in-memory set, cSurveyPC/cFile.vb:340-380).
- The Therion runner adds the `THERION` environment variable (sync: cSurveyPC/modMain.vb:379-383, async: 314-317) and uses a 120 s timeout (sync: cSurveyPC/modMain.vb:364, async default parameter at 298). On timeout the sync variant shows a MsgBox (OK = keep waiting, Cancel = kill process tree and raise an error, cSurveyPC/modMain.vb:388-395) while the async variant kills the process and throws `TimeoutException` (cSurveyPC/modMain.vb:344-355) — long surveys can exceed this; if you change it, change both variants.

## Gotchas

- **`frmMain.vb` vs `frmMain2.vb`**: both parse the command line identically; only `frmMain2` runs (Application.Designer.vb:35). Don't waste time patching `frmMain.vb`.
- **Scripts can't see Friend members** — a script that compiles fine in the app's own source tree (e.g. calling `Survey.Calculate.Calculate()`) fails at script-compile time with an accessibility error. This regularly surprises; the script surface is the *Public* API only.
- `cSurvey.Check` (called by the UI before `Load`) refuses files whose calculate mode is Therion when `therion.path` is unset, and refuses non-absolute inversion mode unless Shift+Ctrl are physically held (`My.Computer.Keyboard`, cSurveyPC/cSurvey.vb:902-907) — a headless host should call `Load` directly, not `Check`.
- `GetLocalizedString` does `oRM.GetString(Name).Replace(...)` with no fallback (cSurveyPC/modMain.vb:418-426): a missing `resources` file in the exe directory produces NREs deep inside load/progress code, not a clean error.
- `modMain.GetApplicationPath` derives from `Process.MainModule.FileName` (cSurveyPC/modMain.vb:42-47) — in a host process this points at *the host*, so the `objects\`, `resources` and clipart paths resolve wrong unless the host lives in the cSurvey install directory.
- `cCommandLineParameters` lower-cases keys, so `filename=` matching is case-insensitive, but the *value* keeps its case; quoted paths get quotes stripped in `pSurveyLoad` (cSurveyPC/frmMain2.vb:748), not in the parser.
- The `debug=1` flag makes Therion temp filenames fixed (`_therion_input.th`), so two debug instances calculating simultaneously clobber each other (cSurveyPC/Calculate/cCalculate.vb:1613).
- `cBlenderHelper` shows message boxes and, in `MergeModel`, always pops a completion dialog (cSurveyPC/cBlenderHelper.vb:217) — never call it on an automation path as-is.
- The `Dynamic.vb` LINQ parser is a completely separate expression engine from `cScript` (used for grid filter strings); don't conflate them when hunting "formula" bugs.

## MCP architecture comparison (question 5)

### (a) Out-of-process manipulation of `_data.xml` inside `.csz` (no app involvement)

- **Works today**: full read access to everything (shots, stations, computed coordinates — `cCalculate.SaveTo` embeds calculate data in the XML, cSurveyPC/cSurvey.vb:1857; drawings, properties). Writing *shot data* is feasible: TopoDroid itself produces cSurvey XML externally, and `cSurvey.Load` runs `FixTopodroidCSX` + version migrations on any file it opens (cSurveyPC/cSurvey.vb:943-945, 951+), so moderately imperfect XML is tolerated and gets recalculated in-app on open (segment changes set `InvalidateEnum.FullCalculate`, cSurveyPC/cSurvey.vb:1884-1924).
- **What breaks**: you must reimplement — outside the app — everything the app computes: station coordinates (or leave stale embedded calc data and rely on in-app recalc), splay projection, and above all the *auto-sketch generation* (borders from splays, cross-sections, item→segment ID bindings). The drawing item XML references segment IDs that `FixTopodroidCSX` rewrites (cSurveyPC/modImport.vb:384, 443-489), which is easy to corrupt. Zip round-tripping of binary entries also lands on you.
- **Effort**: low for "inject/patch shots and metadata"; very high (weeks+, reimplementation) for "generate a finished sketch". Good as a *complement* (inspection, small fixes), insufficient alone for the end goal.

### (b) .NET host loading cSurveyPC assemblies headlessly (recommended)

- **Works today** with zero source changes: reference `cSurveyPC.exe` (net48, match x86/x64, run from the install dir so DevExpress etc. resolve), then `New cSurvey` → `Load(path, FixTopoDroid)` → mutate via Public API → `SaveTo(path)`. `cImportTopoDroidHelper.ConvertDesign/ConvertCrossSection` (Public Shared) already converts TopoDroid sketch XML into design items.
- **What breaks / needs one-time fixes**: (1) `Calculate.Calculate`, `modExport.TherionThExportTo`, `modMain.LoadLocalizedStrings` are Friend — fix with a single `InternalsVisibleTo("YourMcpHost")` in cSurveyPC or a ~50-line Public facade class committed into cSurveyPC (the repo owner controls the source, so this is trivial); reflection works as a no-source-change fallback. (2) `My.Application.Settings/RuntimeSettings` must be initialized (call the same `ReloadSettings` logic via the facade). (3) Localized `resources` file must be loadable. The exact working call sequence to copy is `pSurveyImportcSurvey` (cSurveyPC/frmMain2.vb:11860-11865).
- **Effort**: ~1-2 days for a proof-of-concept open→import→calculate→save pipeline; the MCP wrapper (stdio server spawning the net48 host, since MCP SDKs target modern .NET) is another thin layer. All future features (auto-sketch via the same code the UI uses, Therion/SVG export, rendering plan images for the agent to look at) come for free from the domain assembly.

### (c) UI automation of the running app

- **Works today**: launching with a filename argument; basic ribbon buttons via UIA/DevExpress accessibility.
- **What breaks**: the map/sketch canvas is a custom-painted control with no automation peers; critical steps go through modal dialogs (`OpenFileDialog` in `pSurveyLoad` cSurveyPC/frmMain2.vb:757, `frmImportcSurvey` merge dialog, MsgBox confirmations); no single-instance channel means you can't even hand a second file to a running instance; localization changes control captions. Everything is timing- and skin-dependent.
- **Effort**: high initial, permanent fragility. Only worth it for end-to-end smoke tests, not as the MCP backbone.

**Recommendation**: (b), implemented as a small "automation facade" inside the cSurveyPC solution (new Public class or `InternalsVisibleTo`) plus an out-of-process MCP server that talks to the net48 host over stdio. Use (a) opportunistically for cheap read-only inspection of `.csz` files.

## Related docs

- [topodroid-import.md](topodroid-import.md) — the TopoDroid `.csx` fix-up and sketch conversion this doc's flows call into.
- [data-model-and-file-format.md](data-model-and-file-format.md) — `_data.xml` structure that architecture (a) would manipulate.
- [calculation-engine.md](calculation-engine.md) — `cCalculate` internals (internal vs Therion modes).
- [exports-and-printing.md](exports-and-printing.md) — the full `modExport` surface beyond Therion.
- [ui-map.md](ui-map.md) — `frmMain2` structure, where the CLI parsing and dock panels live.
- [drawing-engine.md](drawing-engine.md) — design items the auto-sketch must create.
