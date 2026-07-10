# UI Shell & Interaction Map (frmMain2)

## Purpose

This doc maps the cSurvey desktop UI: what the main window is made of, which handler runs when the user clicks something, how the modal drawing-tool state machine works, and how grid edits flow back into the survey data model and trigger recalculation. Use it to go from "user clicked X and Y broke" to the responsible sub in `cSurveyPC/frmMain2.vb`, and to find the domain entry points a headless automation would call instead of the UI.

## Domain concepts

- **frmMain2** — the single main window. It is a DevExpress `RibbonForm` (cSurveyPC/frmMain2.Designer.vb:3) and is the app's startup form (`<MainForm>frmMain2</MainForm>`, cSurveyPC/My Project/Application.myapp:4, cSurveyPC/My Project/Application.Designer.vb:35). **`frmMain.vb` (25k lines) is dead legacy code — it is not listed in cSurveyPC.vbproj and is not compiled.**
- **Design surface / `picMap`** — a custom `cPictureBox` (cSurveyPC/frmMain2.Designer.vb:8102, class at cSurveyPC/Specialized/cPictureBox.vb:1) on which both the plan and profile drawings are painted with GDI+. There is exactly one; switching plan/profile swaps `oCurrentDesign`, not the control.
- **Edit tools (`cEditTools` / `cEditDesignTools`)** — the modal state machine that decides what a mouse click on `picMap` means (select vs. add point vs. combine). Lives in cSurveyPC/cEditTools.vb (namespace `cSurvey.Helper.Editor`). Note: the files `cSurveyPC/cEditToolsDesign.vb`, `cSurveyPC/cEditToolsPlot.vb`, `cSurveyPC/Design/*.vb` and `cSurveyPC/cDockContent.vb` are **not in the .vbproj** (stale copies from an older DockPanelSuite-based UI); only `cSurveyPC/cEditTools.vb` is compiled.
- **Tool bag (`cEditToolsBag`)** — a description of one ribbon drawing tool (layer, item type, factory method name, parameters) parsed from `cSurveyPC/designtools.xml`. Tool buttons are built at runtime from this XML; the button's `Tag` holds the bag and the item is created by **reflection** on the layer object.
- **Segments grid (`grdSegments`)** — the shot data grid (DevExpress `GridControl`, cSurveyPC/frmMain2.Designer.vb:8452) bound to `UIHelpers.cSegmentsBindingList`, a `BindingList(Of cSegmentPlaceholder)` wrapper over the domain `cSegments` collection (cSurveyPC/cUIHelpers.vb:3485, 3217).
- **p-prefix subs** — frmMain2 convention: every ribbon handler `btnX_ItemClick` is a one-liner delegating to a private `pXxx` sub that does the work. Grep `Private Sub pSurvey` to find the verbs.

## Architecture

### Window composition (actual control fields)

```
frmMain2 (DevExpress.XtraBars.Ribbon.RibbonForm)
├── RibbonControl : pages pageFile, pageHome, pageSurvey, pageDesign, pageView,
│                   pageCurrentItem*, pageCurrentItemPoint*, pageOther
│                   (Designer.vb:8173,8206,8208,8210,8257,8516,8549,8665)
│                   * merged into pageHome at startup (frmMain2.vb:13862-13869)
├── DocumentManager/docView (Docking2010; Designer.vb:7621-7627) hosting the central document
├── DockManager (XtraBars.Docking) with DockPanels (Designer.vb:8348-8370, 8688, 8709, 8811):
│   ├── dockDesigner  → pnlDesigner (Designer.vb:8170) containing:
│   │     ├── picMap  (cPictureBox — 2D plan/profile canvas, Designer.vb:8102)
│   │     ├── pnl3D + h3D (ElementHost with WPF HelixToolkit viewport, Designer.vb:8156-8157)
│   │     └── dockFloatBar, pnlUndoPopup (Designer.vb:1159-1163)
│   ├── dockData      → spSegmentsAndTrigpoints splitter with grdSegments/grdViewSegments
│   │                   (shots) and grdTrigPoints/grdViewTrigpoints (stations)
│   │                   (Designer.vb:8452-8453, 8425, 791; grid in splitter at 6528)
│   ├── dockProperties→ pnlObjectProp: stack of cItem*PropertyControl panels built in Sub New
│   │                   (frmMain2.vb:13935-14047)
│   ├── dockLevels, dockClipart, dockBrushesAndPens, dockText, dockTexts, dockJoinPoints,
│   │   dockConsole, dockScript (ScintillaNET editor), dockAV (audio), dockIV (images),
│   │   dockLS (linked surveys), dockDistances
│   └── each panel gets a UserControl from cSurveyPC/DockControl/cDock*.vb, instantiated and
│       docked Fill in Sub New (frmMain2.vb:13872-13930), re-targeted to the current survey
│       via oDockX.SetSurvey(oSurvey) on every load (frmMain2.vb:837-847)
├── Status bar items: pnlStatusText, pnlStatusProgress, pnlStatusZoomBar, pnlStatusDesignInfo
│   (mouse world coordinates; updated at frmMain2.vb:3539)
└── Per-shot edit panel pnlSegment (txtSegmentDistance/Bearing/Inclination/Left/Right/Up/Down,
    chkSegmentInverted, chkSegmentExclude..., Designer.vb:8073-8117) shown under the grid
```

State fields that decide what everything operates on (frmMain2.vb:43-48, 221-222): `oSurvey` (the loaded `cSurvey.cSurvey`), `oCurrentDesign` (`oSurvey.Plan` / `oSurvey.Profile` / 3D), `oCurrentOptions` (`cOptionsCenterline` view options), `oTools` (`cEditTools`), and `oPlanTools`/`oProfileTools`/`o3DTools` (`cEditDesignTools`, one per design). `pGetCurrentDesignTools()` (frmMain2.vb:15985) returns the one matching `oCurrentDesign`.

### Data-flow narrative

1. **Startup**: `Sub New` (frmMain2.vb:13755) builds dock contents and property panels, parses the command line (13858); `frmMain_Load` (frmMain2.vb:2461) calls `pSurveyNew()` and then `pSurveyLoad(filename)` if a file was passed on the command line — this is the only built-in headless-ish entry (`cSurveyPC.exe "file.csz"`).
2. **Load**: `pSurveyLoad` (frmMain2.vb:745) → `oSurvey = New cSurvey.cSurvey` (780) → `oSurvey.Load(Filename)` (808) → recreates tools (`pToolsCreate`, 381: `oTools = New cEditTools(oSurvey)`), rebinds every dock panel (837-847), shows plan (851), rebinds the segments grid (853) and redraws.
3. **Edit shots**: grid cell edits write through `cSegmentPlaceholder` into `cSegment`; the domain raises `cSurvey.OnSegmentsChange`, handled at frmMain2.vb:5491, which calls `pSurveyCalculate(False)` — i.e. recalculation is event-driven, automatic when `Properties.CalculateMode = Automatic` (5543).
4. **Recalculate**: `pSurveyCalculate` (frmMain2.vb:5542) → `oSurvey.Calculate.Calculate(True)` (5551); calculation errors are mapped back onto grid rows via `cSegmentsBindingList.SetCalculateException` (5559) and shown as clickable popup links; then `pSurveyRedraw` (5793) → `oSurvey.Redraw(oCurrentOptions)` → `pMapInvalidate` (9418) → `picMap_Paint` (4031) → `pSurveyDraw` (9248) → `oCurrentDesign.Paint(Graphics, oCurrentOptions, cDrawOptions.Empty, oDesignTools)` (9307).
5. **Draw map items**: ribbon tool button → `btnDesignTools_ItemClick` (7254) → `pDesignTools_CreateItem(Bag)` (6849) → layer factory method invoked by reflection (7116) → `pGetCurrentDesignTools.EditItem(oItem, True)` (cEditTools.vb:1548) → subsequent `picMap` mouse events add points to `CurrentItem` → double-click / End-edit button commits via `EndAndSelectItem` (cEditTools.vb:1579).
6. **Save**: `pSurveySave` (frmMain2.vb:1094) → `pSurveySaveCurrentWorkarea()` (1124, persists zoom/pan into the file) → `oSurvey.SaveTo(filename, Options)` (1126), plus optional history snapshots and autosave thread (1146).

## Key classes & files

| File | Class / member | Responsibility |
|---|---|---|
| cSurveyPC/frmMain2.vb (20509 ln) | `frmMain2` | The entire shell: all ribbon handlers, picMap mouse/paint pipeline, import/export dispatch, dock orchestration |
| cSurveyPC/frmMain2.Designer.vb (8828 ln) | `frmMain2` (partial) | All control fields: ribbon items (`btn*`, `page*`, `grp*`), dock panels (`dock*`), grids (`grdSegments`, `grdTrigPoints`), `picMap`, `pnl3D`/`h3D` |
| cSurveyPC/cEditTools.vb | `cEditTools` (516), `cEditDesignTools` (1237), `cEditToolsBag` (2150) | Selection + modal edit state machine; per-design undo (`Undo` property, 1295); tool descriptors from XML |
| cSurveyPC/cUIHelpers.vb | `cSegmentPlaceholder` (3217), `cSegmentsBindingList` (3485) | Grid↔domain bridge for shots; marshals domain events to the UI thread via `SynchronizationContext.Post` (3491, 3507) |
| cSurveyPC/designtools.xml | — | Declarative catalog of the ribbon drawing tools — 84 `<tool>` entries (of which ~63 are actual tools; 11 separators, 10 dropdown containers): `type`, `layer`, `method` (layer factory, e.g. `CreateSandSoil`), `parameters`, per-language `<caption lang=…>` children |
| cSurveyPC/DockControl/cDock*.vb | `cDockLevels`, `cDockClipart`, `cDockConsole`, `cDockScript`, `cDockBrushesAndPens`, `cDockText(s)`, `cDockJoinPoints`, `cDockLinkedSurveys`, `cDockDistances`, `cDockAudioViewer`, `cDockImageViewer` | UserControls hosted inside DevExpress dock panels; each has `SetSurvey(oSurvey)` |
| cSurveyPC/frmProperties.vb | `frmProperties` (18), ctor (37) | Modal survey-properties dialog (caves, sessions, calc mode…); opened by `pSurveyProperty` (frmMain2.vb:5317) |
| cSurveyPC/frmPreview.vb | `frmPreview` | Print preview AND image export window (`PreviewModeEnum.Preview` vs `.Export`), see [exports-and-printing.md](exports-and-printing.md) |
| cSurveyPC/frmImportcSurvey.vb | `frmImportcSurvey` | Interactive merge dialog for importing another .csx/.csz (the TopoDroid path) |
| cSurveyPC/frmSketchEdit.vb | `frmSketchEdit` (14), ctor `New(Sketch As cItemSketch)` (259) | Field-sketch editor: warp a bitmap sketch onto stations before tracing |
| cSurveyPC/frmResurveyMain.vb | `frmResurveyMain` | "Resurvey" acquisition UI (.crsx/.crsz), invoked by `pResurvey` (frmMain2.vb:14569) then merged via `frmImportResurvey` (14572) |
| cSurveyPC/modDevExpress.vb | module | DevExpress helpers: skin menu (117), floating-form fix (129), `RestoreDockPanel` (142), grid focus helpers (176) |
| cSurveyPC/modToolbars.vb | module | Save/restore legacy `ToolStrip` positions (38 lines, minor) |
| cSurveyPC/frmDisto.vb | `frmDisto` | DistoX serial terminal — **legacy, not compiled** (only referenced from dead frmMain.vb); current build has no live DistoX UI |
| cSurveyPC/Specialized/cPictureBox.vb | `cPictureBox` | Double-buffered picture box used as design canvas |

## Key flows (routing table + call chains)

### Routing table: user gesture → handler → domain call

All handlers below are in `cSurveyPC/frmMain2.vb` unless noted. Pattern: handler → `p*` sub → domain.

| # | User action (ribbon/gesture) | Handler (frmMain2.vb:line) | Work sub → domain call |
|---|---|---|---|
| 1 | New survey | `btnNew_ItemClick` :16592 | `pSurveyNew` :400 → `New cSurvey.cSurvey`; optional template `oSurvey.Load(template, LoadOptionsEnum.Update)` :445 |
| 2 | Open survey | `btnLoad_ItemClick` :16596 | `pSurveyLoad` :745 → `cSurvey.Check` :776, `oSurvey.Load(Filename)` :808 |
| 3 | Rollback to saved | `btnRollback_ItemClick` :16600 | `pSurveyLoad(sFilename, False)` |
| 4 | Save / Save As | `btnSave_ItemClick` :16606 / `btnSaveAs_ItemClick` :16610 | `pSurveySave` :1094 → `oSurvey.SaveTo(file, Options)` :1126 |
| 5 | Save as template | `btnSaveAsTemplate_ItemClick` :16614 | `pSurveySave(templatePath, True, NoHistory Or Silent)` :16619 |
| 6 | Import survey data (TopoDroid .csx among others) | `btnImportData_ItemClick` :16688 | `pSurveyImport(Survey,"",True)` :572 → FilterIndex dispatch :599 (1=VisualTopo, **2=cSurvey/TopoDroid**, 3=PocketTopo :12594, 4=Compass :13027, 6=Text/CSV :11342, 7-9=XLSX, 10=Therion .th :11300) |
| 7 | → TopoDroid/.csx branch | — | `pSurveyImportcSurvey` :11854 → `oImportSurvey.Load(f, LoadOptionsEnum.FixTopoDroid)` :11861 → recalc if needed :11864 → `frmImportcSurvey` merge dialog :11868 (detects `Properties.CreatorID = "TopoDroid"` :11880) |
| 8 | Import design (SVG/.csx/.th2) | `btnImportDesign_ItemClick` :16696 | `pSurveyImport(Design,...)` :665 → `pSurveyImportSVG` :10293 / `pSurveyImportcSurvey` / `pSurveyImportTherionGraphics` :10261 |
| 9 | Drop file on canvas | `picMap_DragDrop` :8448 | extension dispatch :8465; .csx/.csz → `pSurveyLoad` if survey empty else import as design :8501-8506 |
| 10 | Add shot (grid "+") | `btnSegmentAdd_ItemClick` :17213 | `pSegmentAdd` :1439 → `oSurvey.Segments.Append()`; insert-row variant `pSegmentInsert` :1412 → `oSurvey.Segments.Insert(i)` |
| 11 | Edit shot cell in grid | DevExpress binding (no explicit handler) | `cSegmentPlaceholder` setter → `cSegment` property → `oSurvey.OnSegmentsChange` → handler :5491 → `pSurveyCalculate(False)` |
| 12 | Recalculate (forced) | `btnPlotCalculate_ItemClick` :16735 | `pSurveyCalculate(True)` :5542 → `oSurvey.Invalidate()` + `oSurvey.Calculate.Calculate(True)` :5551 |
| 13 | Rebind stations | `btnPlotRebind_ItemClick` :16739 | `pSurveyTrigpointsRefresh` :1401 → `oSurvey.TrigPoints.Rebind()` |
| 14 | Switch to Plan | `btnViewPlan_ItemClick` :20059 | `pSurveyShowPlan` :6121 → `oCurrentDesign = oSurvey.Plan`, options `oSurvey.Options("_design.plan")` :6140-6141, restores per-design zoom/pan :6157-6166 |
| 15 | Switch to Profile | `btnViewProfile_ItemClick` :20063 | `pSurveyShowProfile` :5956 (mirror of plan) |
| 16 | Switch to 3D | `btnView3D_ItemClick` :20067 | `pSurveyShow3D` :5806 → hides picMap, shows `pnl3D`/`h3D` (HelixToolkit `oHolos` viewer) |
| 17 | Pick a drawing tool | dynamically-created button → `btnDesignTools_ItemClick` :7254 | `pDesignTools_CreateItem(Bag)` :6849 → reflection `oLayer.GetType.GetMethod(Bag.Method).Invoke(...)` :7116 → `pGetCurrentDesignTools.EditItem(oItem, True)` :7128 |
| 18 | Draw line/area points | `picMap_MouseDown` :3047 (in-edit branch :3132) / `picMap_MouseMove` :3516 (drag branch :3563) | `CurrentItem.Points.AddFromPaintPoint(oMousePoint)` :3156/3585; snap `modPaint.PointSnap` :3139; grid-align :3137 |
| 19 | Finish the item | `picMap_DoubleClick` :3027 → `pToolsEnd` :5329, or End-edit button `btnItemsEndEdit_ItemClick` :16886 → `pDesignEndEdit` :16877 | `pGetCurrentDesignTools.EndAndSelectItem()` (cEditTools.vb:1579) |
| 20 | Select item on canvas | `picMap_MouseDown` else-branch :3202 → `oCurrentDesign.HitTest(...)` (:3189 pattern) | `pGetCurrentDesignTools.SelectItem(...)` (cEditTools.vb:1434) |
| 21 | Select shot/station on canvas | Alt+click branch :3090 | `oSurvey.Plan.Plot.HitTest(...)` :3099 → `pSegmentSelect`/`pTrigPointSelect` |
| 22 | Edit item properties | `btnItemsObjectProperties_ItemClick` :18973 → `pObjectPropShow` :6552, loaded by `pObjectPropertyLoad` :5177 | dockProperties panel stack (`cItem*PropertyControl`) writes straight into `pGetCurrentDesignTools.CurrentItem` |
| 23 | Survey properties (caves/sessions) | `btnProperties_ItemClick` :16632 | `pSurveyProperty` :5317 → `New frmProperties(oSurvey, tab, lang, element)` :5319 |
| 24 | Export data (.tro/.th/.xlsx) | `btnExportData_ItemClick` :16680 | `pSurveyExport(Survey)` :5662; **Therion**: FilterIndex 2 → `frmExportTherion` :5681 → `modExport.TherionThExportTo(oSurvey, file, nameDict, iThOptions)` :5691 (+ optional thconfig :5697) |
| 25 | Export image | `btnExportImage_ItemClick` :16676 | `pSurveyExport(Image)` :5743 → `New frmPreview(oSurvey, PreviewModeEnum.Export, view)` :5751 |
| 26 | Print / print preview | `btnPrint_ItemClick` :16628 | `pSurveyPrint` :5768 → `New frmPreview(oSurvey, PreviewModeEnum.Preview, plan-or-profile)` :5776 |
| 27 | Undo | `btnUndo_ItemClick` :20133 | `pSurveyUndo` :7803 → `pGetCurrentTools.Undo.RestoreSnapshot()` :7807, switches to the design the snapshot belongs to :7812/7824 |
| 28 | Zoom in/out/fit | `btnZoomIn/Out/ToFit_ItemClick` :16747-16757 | `pMapZoomIn` :4075 / `pMapZoomOut` :4056 / `pMapCenterAndFit`; repaint via `pMapRepaint` :4094 |
| 29 | Resurvey (.crsx) | `btnResurvey_ItemClick` :16652 | `pResurvey` :14569 → `frmResurveyMain` → `frmImportResurvey` → creates session + segments :14588 |
| 30 | 3D in Loch | `btnLoch_ItemClick` :16656 | `pSurveyLoch` (exports .th + launches Therion Loch) |

Diagnosis tip: given a symptom, grep frmMain2.vb for `Handles btn<Name>` (button names in the Designer read like their captions), then follow the single `pXxx` call inside.

### Flow A: TopoDroid import (UI path automation must replicate)

1. cSurveyPC/frmMain2.vb:16688 — `btnImportData_ItemClick` fires from ribbon File group.
2. cSurveyPC/frmMain2.vb:577-596 — `pSurveyImport` shows `OpenFileDialog` (filter index 2 = "*.CSX;*.CSZ").
3. cSurveyPC/frmMain2.vb:605 — dispatch to `pSurveyImportcSurvey(Filename, Append)`.
4. cSurveyPC/frmMain2.vb:11860-11865 — loads the file into a *second* in-memory survey: `oImportSurvey.Load(Filename, LoadOptionsEnum.FixTopoDroid)`; if it has no stored calculation, runs `oImportSurvey.Calculate.Calculate(True)`.
5. cSurveyPC/frmMain2.vb:11868-11950 — `frmImportcSurvey` dialog: validates station-name overlap (:11894), mergeable custom data tables (:11901), warping availability (:11926), then (on OK) merges segments/sessions/caves and optionally plan/profile graphics into `oSurvey`.
6. On completion the normal `OnSegmentsChange` → `pSurveyCalculate` → `pSurveyRedraw` chain refreshes everything. See [topodroid-import.md](topodroid-import.md) for the `FixTopoDroid` fixups and file format.

### Flow B: drawing an area on the design surface (edit-tool state machine)

1. cSurveyPC/frmMain2.vb:6798-6802 — at startup `pSurveyDesignToolsLoad` reads `designtools.xml`, creating a `BarButtonItem` per `<tool>` with `Tag = New cEditToolsBag(xml)` (:6606) wired to `btnDesignTools_ItemClick` (:6663).
2. cSurveyPC/frmMain2.vb:7254-7278 — click bumps most/last-used counters and calls `pDesignTools_CreateItem(oBag)`.
3. cSurveyPC/frmMain2.vb:7113-7128 — default ("freehandarea"/"freehandline" etc.) branch: `SelectLayer(Bag.Layer)`, create the empty item by reflection (`Bag.Method` e.g. `CreateSandSoil` with `Bag.GetInvokeParameters("cave",…, "branch",…)`), set bind-design type, then `EditItem(oItem, True)`.
4. cSurveyPC/cEditTools.vb:1548-1566 — `cEditDesignTools.EditItem` sets `bIsInEdit=True`, `bIsNewItem`, `bStarted=False` and raises `OnItemEdit`. From now on the tools object is "in edit" and picMap clicks mean "add geometry".
5. cSurveyPC/frmMain2.vb:3132-3186 — `picMap_MouseDown`: because `IsInEdit`, calls `StartEditItem()` (cEditTools.vb:1993), applies grid-align (:3137) and snap-to-point (:3139), then per item type adds a point: freehand line/area → `Points.StartSequence()` + `Points.AddFromPaintPoint(oMousePoint)` (:3155-3156); fixed-point items (Text/Sign/Clipart…) move/add up to `MaxPointsCount` (:3175-3181).
6. cSurveyPC/frmMain2.vb:3563-3603 — `picMap_MouseMove` with button held streams more points (`AddFromPaintPoint`, :3585) or, in point-by-point mode (`bEditPointByPoint`), moves the last point (:3583).
7. cSurveyPC/frmMain2.vb:3027-3043 — double-click → `pToolsEnd` (:5329) → `EndAndSelectItem` (cEditTools.vb:1579-1599) clears `bIsInEdit` and the item becomes the current selection; `OnRefreshDesign` repaints. Undo snapshots are managed by `cEditDesignTools.BeginUndoSnapshot`/`CommitUndoSnapshot` (cEditTools.vb:1901, 1917).
8. While editing, paint overlays come from `pSurveyDraw` (frmMain2.vb:9286-9316): current item painted in `SelectionModeEnum.InEdit`, plus new/last point markers.

Other mouse modes in `picMap_MouseDown` (:3047): Ctrl (or `btnScrollMode`) = pan, Shift (or `btnMultiSelMode1/2`) = rubber-band multiselect (:3073-3088), Alt = hit-test centerline shots/stations instead of items (:3090-3124), Alt in `IsInCombine` = merge two items (:3188-3201). Keyboard A/S/D or `btnSnapToPoint0/1/2` select snap modes (:3059-3061).

### Flow C: grid edit → recalculation → redraw

1. cSurveyPC/frmMain2.vb:1392-1399 — `pSurveySegmentsGridSetup`: `grdSegments.DataSource = oTools.Segments` where `cEditTools.Segments` (cSurveyPC/cEditTools.vb:578) returns the `cSegmentsBindingList` created eagerly in the `cEditTools` constructor (cEditTools.vb:686).
2. cSurveyPC/frmMain2.Designer.vb:6600 — grid columns bind by field name to `cSegmentPlaceholder` properties (e.g. `colSegmentsListFrom.FieldName = "From"`).
3. cSurveyPC/cUIHelpers.vb:3217+ — a cell edit sets e.g. `cSegmentPlaceholder.Splay` which writes through to `oSegment.Splay` (:3273).
4. The domain raises `cSurvey.OnSegmentsChange`; cSurveyPC/frmMain2.vb:5491-5518 handles it (thread-safe via `Invoke`): Add/Change/Remove/Splay → `pSurveyCalculate(False)`; add also re-selects the segment via `oTools.SelectSegment` (:5503). The guard `bDisableSegmentsChangeEvent` (a push/pop flag stack, :228) suppresses this during bulk load/import.
5. cSurveyPC/frmMain2.vb:5542-5581 — `pSurveyCalculate`: only recalcs when `CalculateMode = Automatic` or forced; on error decorates offending rows (`SetCalculateException`, :5559-5563) and shows a clickable error popup; then `pSurveyRedraw` (:5577) → `oSurvey.Redraw(oCurrentOptions)` (:5797) → `pMapInvalidate` → `picMap_Paint` → `pSurveyDraw` → `oCurrentDesign.Paint(...)` (:9307).
6. Reverse direction: `cEditTools.SelectSegment` (cEditTools.vb:646) raises `OnSegmentSelect`, handled at frmMain2.vb:7635, which saves the previous segment's edit panel (`pSegmentSave`, :1904), focuses the grid row (:7639-7642) and redraws both plots' highlights.
7. The binding list itself listens to `cSegments` events and posts adds/removes to the UI thread (`oContext.Post`, cSurveyPC/cUIHelpers.vb:3507-3567) — this is the fix for the "shots changed from different threads" bug in commit 0c6700b.

### Flow D: startup & workspace restore

1. cSurveyPC/My Project/Application.Designer.vb:35 — WinForms application framework creates `frmMain2`.
2. cSurveyPC/frmMain2.vb:13755 — `Sub New`: skins, dock contents, property-control stack, `oCommandLine = New cCommandLineParameters(Command)` (:13858).
3. cSurveyPC/frmMain2.vb:2461-2477 — `frmMain_Load`: `pSurveyNew()`, then loads a file given as the sole command-line argument or `filename=` parameter.
4. cSurveyPC/frmMain2.vb:2537-2559 — `pWorkspacesLoad` restores `*.cworkspace` dock layouts via DevExpress `WorkspaceManager` (hold Ctrl+Alt at startup to skip); `DockManager_LayoutUpgrade` (:19768) re-docks panels after version upgrades.

## How to modify safely

- **Respect the event-guard flags.** Any programmatic bulk change to `oSurvey.Segments`/`TrigPoints` must be wrapped in `bDisableSegmentsChangeEvent.Push()/.Pop()` (`cStateFlagStack`, frmMain2.vb:228) exactly as `pSurveyLoad` does (:805-813), otherwise every appended segment triggers a full recalculation + repaint.
- **Always go through `pSurveyEndEdit` (:734) before load/save/new** — it commits pending grid editors and the in-edit design item; skipping it loses user input or leaves `IsInEdit` true against a stale survey.
- **`pToolsCreate` must run after every `New cSurvey.cSurvey`** (:786, :823) — the tools hold the only per-design undo stacks and selection state; keeping an old `cEditDesignTools` referencing a disposed survey crashes on the next mouse event.
- **One canvas, three designs**: never cache `pGetCurrentDesignTools()`/`oCurrentDesign` across a plan/profile/3D switch; `pSurveyShowPlan/Profile/3D` also swap `oCurrentOptions` and per-design zoom (`oPaintInfo(...)` backup/restore, :6137, :6157-6166).
- **UI-thread discipline**: domain events can arrive from worker threads; follow the `InvokeRequired`/`BeginInvoke` pattern used by `oSurvey_OnSegmentsChange` (:5492) and `pConsoleAdd` (:706). `cSegmentsBindingList` must stay `SynchronizationContext`-posted.
- **Dynamic ribbon tools**: tool buttons only exist if `designtools.xml` parses; renaming a layer factory method in the domain (`CreateSoil`, `CreateImage`, …) silently breaks the corresponding tool because invocation is reflection by string (`Bag.Method`, cEditTools.vb:2171, invoke at frmMain2.vb:7116). Also, every visible tool button needs the parallel hidden `*_Standard` item (`pSurveyDesignToolsCreateStandardItem`, :6582) or last-used bars break.
- **Do not edit the legacy files** (`frmMain.vb`, `cEditToolsDesign.vb`, `cEditToolsPlot.vb`, `frmDisto.vb`, `cDockContent.vb`, `Design/*.vb`): they are not compiled; changes there do nothing — a classic trap since they mirror real class names.
- Settings live in the registry-backed `My.Application.Settings` (`cEnvironmentSettings`, cEditTools.vb:134); use `GetSetting/SetSetting` keys, don't add app.config settings.

## Build notes

- **Solution**: `cSurveyPC/cSurveyPC.sln` — projects: `cSurveyPC` (VB.NET WinExe, .NET Framework 4.8, x86/x64 configs, vbproj:9-15), `cave_model` (**C++ vcxproj**, project dependency), `HelixToolkit.Wpf.cSurveySpecialized` (C#, forked 3D viewport), `cPrintController` (C#), `cSurveyDiagnostics` (VB).
- **DevExpress v24.2 is the blocker**: ~27 `DevExpress.*.v24.2` assemblies (vbproj:196-222) are referenced without HintPath (GAC/registered install) and `My Project/licenses.licx` compiles license metadata for RibbonControl, DockManager, XtraGrid etc. Building requires an installed, licensed DevExpress 24.2.13 — there is no NuGet fallback in the repo. This affects UI builds only; the domain classes (`cSurvey.*`) don't depend on DevExpress, which matters if you ever split out a headless core.
- NuGet `packages\` (HintPath'd, vbproj:179-298): Clipper/Clipper2, CommunityToolkit.*, CsvHelper, Diacritics, **EPPlus 4.5.3** (xlsx import/export), FTTLib, HelixToolkit(.Wpf) 2.27.3, ImageProcessor, NAudio 2.2.1 (survey audio notes), Newtonsoft.Json, **ScintillaNET 3.6.3** (dockScript editor). Loose DLLs at project root: `GeoUtility.dll` (coordinate conversion) and `Ionic.Zip.dll` (.csz zip I/O) (vbproj:234, 246).
- **DockPanelSuite (WeifenLuo) is NOT a dependency** of the current build despite `cDockContent.vb` existing — docking is DevExpress `XtraBars.Docking` + `Docking2010.DocumentManager`.
- Pre-build runs `crea file di risorse.bat` (resource generation via repo-root ResGen.exe) and post-build runs `cSurveyUpdateVersion.exe` (vbproj:5120-5123) — both assume repo-relative paths; they are the first things to stub out when building in CI.
- Runtime file dependencies next to the exe: `designtools.xml`, `objects\` (icons, cliparts, brushes, pens, patterns) — `pSurveyDesignToolsLoad` loads them from `modMain.GetApplicationPath` (:6802, :13853).

## Gotchas

- **frmMain2 vs frmMain**: grep hits in `frmMain.vb` are meaningless — verify a file is in `cSurveyPC.vbproj` before trusting it (640 `<Compile>` entries; notable non-compiled: `frmMain.vb`, `frmDisto.vb`, `cEditToolsDesign.vb`, `cEditToolsPlot.vb`, `cDockContent.vb`, whole `Design/` folder).
- **Import format is chosen by dialog FilterIndex, not file sniffing** (frmMain2.vb:599): a TopoDroid `.csx` opened with filter 1 would be parsed as VisualTopo. Automation should call the specific `pSurveyImport*` equivalent (or better, domain `cSurvey.Load` with `LoadOptionsEnum.FixTopoDroid`) rather than simulate the dialog.
- **Opening vs importing .csx/.csz**: `pSurveyLoad` replaces the survey; `pSurveyImportcSurvey` merges into the current one. Drag-drop picks between them based on `pSurveyIsEmpty()` (:8502).
- **"Recalculate" button ≠ automatic recalc**: with `CalculateMode = Manual`, grid edits only invalidate; nothing recomputes until `btnPlotCalculate` forces it (:5543).
- **Ctrl/Alt/Shift are overloaded** on the canvas and also emulated by toolbar toggle buttons (`btnScrollMode`, `btnAltMode`, `btnMultiSelMode1/2`, :3055-3057) — reproduce bugs with the buttons, not just the keys; Ctrl+Left-click is remapped to middle-button pan (:3051).
- **Undo is per-design** and switching views mid-undo is normal: `pSurveyUndo` jumps to the design stored in the snapshot (:7810-7824). Undo state lives in `cEditTools.Undo`, recreated on every load — loading a file clears undo history.
- **Localized-string indirection**: UI text comes from `GetLocalizedString("main.textpartNNN")`; to find code from a screenshot message, grep the string in `cSurveyPC/*.resx` first to get the key, then grep the key.
- **Zoom state is saved into the survey file** (`pSurveySaveCurrentWorkarea` :1124, restore :835) — "the view moved after load" reports usually trace here, not to paint code.
- `ProcessCmdKey` (:19898) rewrites the decimal key to a comma for Italian locale — surprising when debugging numeric input of shot data.
- The 3D viewport is WPF inside `ElementHost h3D` (Designer.vb:8157); WinForms/WPF focus quirks mean canvas shortcuts don't fire while 3D view is active.

## Related docs

- [topodroid-import.md](topodroid-import.md) — TopoDroid .csx specifics and `FixTopoDroid`
- [data-model-and-file-format.md](data-model-and-file-format.md) — `cSurvey`, `cSegment`, .csz/.csx format
- [calculation-engine.md](calculation-engine.md) — what `oSurvey.Calculate.Calculate` does
- [drawing-engine.md](drawing-engine.md) — `cDesign`, `cLayer`, `cItem*` used by the edit tools
- [rendering-and-plot.md](rendering-and-plot.md) — `cPlot`, `Paint` pipeline behind `pSurveyDraw`
- [exports-and-printing.md](exports-and-printing.md) — `modExport.TherionThExportTo`, `frmPreview`
