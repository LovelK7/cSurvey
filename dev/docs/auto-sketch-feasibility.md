# Automated Final-Sketch Feasibility (TopoDroid data in → finished plan+profile map out)

## Purpose

This doc inventories **every facility in cSurvey that generates drawing geometry from measurement data** — splay-based wall generation, 3D-outline borders, LRUD machinery, sequence-widening, splay projection/rendering, and TopoDroid's own sketch import — with exact APIs and algorithms, and then gives a grounded feasibility verdict with three concrete pipeline designs for "TopoDroid zip in → finished cave sketch out". Bottom line up front: **a plan-view wall generator already exists** (`modSegmentsTools.CreatePlanBorderFromSplay`, hidden behind a debug-only menu), **the profile equivalent is an empty stub**, and the highest-quality path is to reuse the sketch the surveyor already drew in TopoDroid (auto-converted on load) and only synthesize walls where no sketch exists.

## Domain concepts

- **Splay border**: the envelope polygon around a shot formed by the tips of its splay shots. cSurvey computes per-shot splay projections during calculation (`Segment.Data.Plan.FromSplays/ToSplays`, `Segment.Data.Profile.FromSplays/ToSplays`) and can render them as a tracing aid; the *generator* turns them into an actual `cItemInvertedFreeHandArea` cave-border item.
- **Per-shot splay-border tuning**: every `cSegment` carries plan/profile splay filter properties (inclination ranges, projection plane, max angle variation) via the `cIItemPlanSplayBorder`/`cIItemProfileSplayBorder`/`cIItemCrossSectionSplayBorder` interfaces (cSurveyPC/cIItemSplayBorder.vb:2-31; implemented on `cSegment` at cSurveyPC/cSegment.vb:214-304, 1536).
- **LRUD side points**: per-station Left/Right/Up/Down wall distances from the shot's own `l/r/u/d` fields, accumulated into `SideMeasure` and turned into side points on each segment's projected data. This is a *separate* wall-information channel from splays.
- **Wall envelope vs. cartography**: everything below produces a geometric envelope. A finished cave map additionally encodes *interpretation* (floor vs ceiling morphology, presumed passages, symbol/label placement) that no facility in this codebase derives from measurements.
- **Outline bezier**: the native `cave_model` mesh generator can emit a 2D outline of the 3D passage model as bezier curves (`calcOutineBesier`), used as an alternative border generator.

## Architecture

There are six distinct "geometry from data" facilities. Their data dependencies:

```
shots + splays ──cCalculate.Calculate──► station XYZ/D
                                          │
                    ┌─────────────────────┼──────────────────────────┐
                    ▼                     ▼                          ▼
      cPlotPlan.CalculateSplay   cPlotProfile.CalculateSplay   SideMeasure (from l/r/u/d)
      Data.Plan.From/ToSplays    Data.Profile.From/ToSplays    Data.Plan/Profile side points
                    │                     │                          │
        ┌───────────┘                     │                          ├──► 3D model (DNetCMCave)
        ▼                                 ▼                          ▼
  (1) CreatePlanBorderFromSplay   (2) profile generator =      (3) CreateBorder3DOutline
      Clipper union → 1 cave          EMPTY STUB               calcOutineBesier → bezier
      border item on Plan                                      border items (Plan or Profile)
```

1. **`CreatePlanBorderFromSplay`** (cSurveyPC/modSegmentsTools.vb:424 whole cave/branch, :627 single shot): the real splay→wall generator. Per shot it buckets splay tips by bearing keeping the farthest per bucket, adds a 0.3 m octagon around each station, adds connected-station points, optionally convex-hulls, then Clipper-unions everything into one closed `cItemInvertedFreeHandArea` on the plan Borders layer. **UI access is debug-only** (frmMain2.vb:15901).
2. **`CreateProfileBorderFromSplay`** (modSegmentsTools.vb:645-647) and its path helper (:641-643) are **empty function bodies** — the profile-from-splay generator was never written, even though the input data (profile-projected splays, cSurveyPC/cPlotProfile.vb:210-290) already exists.
3. **`CreateBorder3DOutline`** (modSegmentsTools.vb:443-449, impl :451-625): feeds stations + LRUD side points into the native `DNetCMCave` mesh generator and converts its 2D outline beziers back into per-shot cave-border items, for plan *or* profile (extended elevation conversion at :526-527). Wall quality depends entirely on LRUD/side-point data — raw TopoDroid splay-only data has `l/r/u/d = 0` (verified in dev/example/buless.csz: 316 segments, LRUD overwhelmingly "0"), which yields minimum-size tubes.
4. **`modPaint.WidenSequence`** (cSurveyPC/modPaint.vb:4133-4154): turns an existing drawn polyline into a closed area of given width via `GraphicsPath.Widen` — the "area from sequence" tool (frmMain2.vb:15824-15845). A decoration helper, not a from-data generator.
5. **Splay-border *rendering* aids** (not item generators): plot splay overlay `modPaint.PaintStationSplays` (modPaint.vb:2734), per-shot plan splay filtering with Z-plane projection modes (cPlotPlan.vb:687-756), profile splay projection onto a vertical plane along the shot bearing (cPlotProfile.vb:247-290), and the cross-section splay overlay (`ShowSplayBorder`, cSurveyPC/cItemCrossSection.vb:228-236, render :644-704) that projects splays onto the section plane so a human can trace them.
6. **TopoDroid's own sketch as source**: a TopoDroid-exported .csx already contains the phone-drawn plan/profile sketch; `cSurvey.Load(file, LoadOptionsEnum.FixTopoDroid)` converts it to native typed items and binds it to the centerline automatically (see [topodroid-import.md](topodroid-import.md)); .th2 scraps import via `modImport.TherionTh2ImportFrom` (cSurveyPC/modImport.vb:490).

The **warping system** ([drawing-engine.md](drawing-engine.md)) is what makes any generated sketch survive later data edits: points bound to a shot (`BindedSegment`) are re-warped by `cDesignPlan/cDesignProfile.WarpItemsEx` (cSurveyPC/cDesignPlan.vb:207-261) after each recalculation. Binding does **not** happen automatically when points are added programmatically — see Gotchas.

Finally, **`modDesignLRUD`** (cSurveyPC/modDesignLRUD.vb) works in the *opposite* direction: `GetLRFromDesign` (:740, :785-818) raycasts from a station along the perpendicular bearings against the drawn cave-border `GraphicsPath`s (`cLRUDFromDesignCache2.Intersect`, :404-459) to *measure* LRUD from the finished drawing (consumed by the 3D oversample model). For automation it is a ready-made **quality metric**: generate walls, then check that design-derived LRUD roughly matches splay extents.

## Key classes & files

| File | Class / member | Responsibility |
|---|---|---|
| cSurveyPC/modSegmentsTools.vb:424, 627 | `modSegmentsTools.CreatePlanBorderFromSplay(Survey, Cave/Segment, LineType, AngularPrecision, UseHull)` | Splay→plan cave border generator (returns created `cItemInvertedFreeHandArea`s, already added to Plan Borders layer) |
| cSurveyPC/modSegmentsTools.vb:316-398 | `pCreatePlanBorderPathFromSplay` | Per-shot polygon: bearing-bucketed splay tips + 0.3 m station octagons + neighbour stations + optional convex hull, Clipper union |
| cSurveyPC/modSegmentsTools.vb:645, 641 | `CreateProfileBorderFromSplay` / `pCreateProfileBorderPathFromSplay` | **Empty stubs** — profile-from-splay generator missing |
| cSurveyPC/modSegmentsTools.vb:443-625 | `CreateBorder3DOutline(Survey, Cave, Branch/Segment, PlanOrProfile)` | Border items from the 3D passage model outline (`DNetCMCave.calcOutineBesier`), plan or extended-elevation profile |
| cSurveyPC/modSegmentsTools.vb:277-280, 725, 684 | `BorderHullEnum`, `pConvexHull`, `pConcaveHull` | Hull post-processing; `pConcaveHull` is dead code (never called) |
| cSurveyPC/cPlotPlan.vb:655-767 | `cPlotPlan.CalculateSplay` | Attaches plan-projected splay tips + L/R side points to every centerline shot (`Data.Plan.FromSplays/ToSplays`), with per-segment inclination/Z-plane filters |
| cSurveyPC/cPlotProfile.vb:210-290 | `cPlotProfile.CalculateSplay` | Projects splays onto a vertical plane along shot bearing ± `ProfileSplayBorderProjectionAngle` into `Data.Profile.FromSplays/ToSplays` |
| cSurveyPC/cIItemSplayBorder.vb:2-31 | `cIItemPlanSplayBorder` / `cIItemProfileSplayBorder` / `cIItemCrossSectionSplayBorder` | Per-object splay-filter property contracts (implemented by `cSegment`, `cItemCrossSection`, `cItemSegment`) |
| cSurveyPC/cSegment.vb:214-304, 1536 | Plan/Profile `SplayBorder*` properties | Persisted per-shot splay-border tuning (inclination ranges, projection type/deltaZ, max variation) |
| cSurveyPC/cItemSegment.vb:8-11, 316 | `cItemSegment` | Proxy design item wrapping a `cSegment` so the property UI can edit splay-border tuning — not a generator |
| cSurveyPC/cItemCrossSection.vb:228, 644-704 | `ShowSplayBorder` + render | Display-only splay projection on section plane (tracing aid) |
| cSurveyPC/cBorderFromSplay.vb:14-41 | `cBorderFromSplay` (UserControl) | Options panel for the generator (mode, hull, linetype, cave-vs-shot); settings keys `borderfromsplay.*` |
| cSurveyPC/frmMain2.vb:15901, 15918-15936 | `mnuDesignItemSegmentSplayCreateBorder`, `oBorderFromSplay_OnCreate` | UI dispatch — menu **visible only when `bIsInDebug`** |
| cSurveyPC/cAreaFromSequence.vb, frmMain2.vb:15824-15845, modPaint.vb:4133 | `cAreaFromSequence`, `WidenSequence` | Widen an existing drawn line into an area item (soil/water/etc. via reflection factory) |
| cSurveyPC/modDesignLRUD.vb:740-824, 404-459 | `GetLRFromDesign`, `cLRUDFromDesignCache2.Intersect` | Measure LRUD *from* the drawing by raycasting against cave borders (inverse direction; QA metric) |
| cSurveyPC/Calculate/cCalculate.vb:1300-1329 | SideMeasure accumulation | LRUD comes from the shot's own `l/r/u/d` fields (`GetBaseLeft` etc., cSegment.vb:1395-1409) — **not** from splay geometry |
| cSurveyPC/Specialized/cHolosViewer.xaml.vb:1226 | `Get3DPoints` (Public Shared) | Station Center/L/R/U/D Point3Ds from calculated plan+profile side points; input to `CreateBorder3DOutline` |
| cSurveyPC/modExport.vb:653, 669, 3505, 3538, 3618 | `TherionExportOptionsEnum.ExportSplay`, `SegmentSplayWithoutName` | Exports splays to therion (optionally anonymized as "`.`", commit 7a7fe49) — feeds therion/loch splay rendering, not a wall generator |
| cSurveyPC/cLayerBorders.vb:36-48 | `cLayerBorders.CreateCaveBorder/CreatePresumedCaveBorder` | Item factories used by all generators (set `PenTypeEnum.CavePen`, call `SetCave`) |
| cSurveyPC/cPoints.vb:82-110, 211-219 | `AddFromPaintPoint`, `Add` | Programmatic point insertion (auto-inserts 2 control points for Bezier sequences); **does not bind points** |
| cSurveyPC/cItem.vb:644-663, 796 | `SetCave` (Public), `BindSegments` (Friend) | Binding entry points; `SetCave` binds only when cave/branch actually changes |
| cSurveyPC/cEditTools.vb:1927-1931 | `pEndItem` | Where the interactive flow calls `BindSegments()` — the step headless generation must replicate |

## Key flows

### Flow 1 — Plan cave border from splays (the existing auto-sketch generator)

1. cSurveyPC/frmMain2.vb:15901 — context menu `mnuDesignItemSegmentSplayCreateBorder` is made visible only when `bIsInDebug` (hidden experimental feature).
2. cSurveyPC/frmMain2.vb:15918-15925 — `oBorderFromSplay_OnCreate` reads the options panel and calls `modSegmentsTools.CreatePlanBorderFromSplay(oSurvey, cave, branch, lineType, angularPrecision, useHull)` (whole cave/branch) or the single-shot overload.
3. cSurveyPC/modSegmentsTools.vb:400-422 — `pCreatePlanBorderFromSplay` resolves segments via `Survey.Properties.CaveInfos(Cave).GetSegments` (or `.Branches(Branch).GetSegments`), skips splay/surface/duplicate shots, and Clipper-unions all per-shot polygons (`PolyFillType.pftNonZero`, coordinates ×100 → 1 cm integer resolution).
4. cSurveyPC/modSegmentsTools.vb:316-398 — `pCreatePlanBorderPathFromSplay` per shot: adds an 8-sided 0.3 m shape (`dMinSize`, :282) around From and To stations; for each splay in `Segment.Data.Plan.FromSplays/ToSplays` buckets the tip by integer bearing (`AngularPrecision` quantization, keeping the farthest tip per bucket, :299-314); adds the opposite station and every connected non-splay shot's far station (:338-347, :370-379); appends the station itself if outside the polygon (:351-353); optional `pConvexHull` (:355-357, :725); unions the two station fans (:393-396).
5. cSurveyPC/modSegmentsTools.vb:427-436 — one `cItemInvertedFreeHandArea` is created via `CreateCaveBorder(Cave, Branch)` (cSurveyPC/cLayerBorders.vb:36-41, sets `CavePen` and `SetCave`), `LineType` applied, and each result polygon appended as a closed sequence with `Points.StartSequence()` + `AddFromPaintPoint` (cSurveyPC/cPoints.vb:82).
6. **Missing step**: nothing calls `BindSegments()` afterwards (frmMain2.vb:15933-15935 just repaints), so the generated border's points have no `BindedSegment` and will not warp — see Gotchas.
7. Prerequisite for step 4: `Data.Plan.FromSplays/ToSplays` are populated by `cPlotPlan.CalculateSplay` (cSurveyPC/cPlotPlan.vb:655-767) during `cCalculate.Calculate`, honoring per-shot filters: `PlanSplayBorderInclinationRange` (:711) and `ToAltitude`/`ToCenterOfSegment` Z-plane windows (:691-700) mark splays `InRange`, though note the generator itself uses all splays in the collection regardless of the `InRange` flag (:331-333).

### Flow 2 — Border from the 3D passage model (works for profile too, but needs LRUD)

1. cSurveyPC/frmMain2.vb:15926-15931 — "Cut and LRUD" mode calls `modSegmentsTools.CreateBorder3DOutline(oSurvey, cave, branch, PlanOrProfile)` (`True` = profile).
2. cSurveyPC/modSegmentsTools.vb:456 — station geometry from `cHolosViewer.Get3DPoints(Survey, Options("_design.3d"), 0,0,0,1)` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:1226): Center from plan X/Y + profile depth, L/R from `Data.Plan.From/ToSidePointLeft/Right`, U/D from `Data.Profile.From/ToSidePointUp/Down` — i.e. **LRUD side points, not splay tips** (side points come from `SideMeasure`, which is fed by the shots' own `l/r/u/d` fields, cSurveyPC/Calculate/cCalculate.vb:1300-1329, cSurveyPC/cSegment.vb:1395-1409).
3. cSurveyPC/modSegmentsTools.vb:457-523 — per station `addVertice` + up to four `addWall` rays into `DNetCMCave`; centerline shots become `addEdge`; shots flagged `Cut` contribute the To-point as an extra wall ray (:508-511).
4. cSurveyPC/modSegmentsTools.vb:525-534 — profile mode sets `setShouldConvertToExtendedElevation(True)` + look direction (0,−1,0); plan mode looks down (0,0,−1); `finishInit` then `calcOutineBesier()` returns the outline as bezier segments keyed to piket ids.
5. cSurveyPC/modSegmentsTools.vb:536-622 — beziers are grouped per shot (`from::to`), and for each shot one `cItemInvertedFreeHandArea` with `LineType = Beziers` is created on the Plan or Profile Borders layer, `SetCave` applied (:572-576 — this does fire `BindSegments` because the cave changes from "", but it runs *before* any points are added at :584-609, so it binds an empty point collection), the two side curves added as two sequences, and shared endpoints joined via `cPoint.Join` (:590-621). Net effect: these borders' points are unbound too — see Gotchas.

### Flow 3 — TopoDroid's own sketch as the drawing source (highest quality, zero generation)

1. cSurveyPC/cSurvey.vb:936, 943-945 — `cSurvey.Load(path, LoadOptionsEnum.FixTopoDroid)` (or auto-detection of `properties@creatid="topodroid"`) triggers the fix-up chain.
2. cSurveyPC/modImport.vb:330-382 — `FixTopodroidDesign`/`FixTopodroidSurvey` convert TopoDroid's flat item lists via `cImportTopoDroidHelper.ConvertItem` (walls → inverted-freehand cave borders, areas → soil/water, points → signs, sections → real `cItemCrossSection`s) and **force `BindSegments()` on every item** (modImport.vb:368, 377) because TopoDroid does not bind.
3. Full detail (symbol mapping table, cross-section attachments, station uppercasing, id regeneration): [topodroid-import.md](topodroid-import.md). Alternative source: therion .th2 scraps via `modImport.TherionTh2ImportFrom(Survey, File, CaveName, options, ScaleFactor)` (cSurveyPC/modImport.vb:490), plan vs profile selected by scrap `-projection` (modImport.vb:554-559).
4. After load: `Invalidate()` + `Calculate.Calculate(True)` (frmMain2.vb:11860-11865 is the proven sequence), which also warps/rescales the imported sketch to the computed centerline.

### Flow 4 — Area from sequence (decoration helper)

1. cSurveyPC/frmMain2.vb:15824-15845 — `oAreaFromSequence_OnCreate` takes the currently selected item/point, calls `modPaint.WidenSequence(item, point, width, reductionFactor)`.
2. cSurveyPC/modPaint.vb:4133-4154 — converts the sequence to a `GraphicsPath`, `Path.Widen(pen, Nothing, reduction)`, returns the outline points (optionally point-reduced).
3. frmMain2.vb:15831-15840 — creates the target item by reflection on a layer factory (`cConvertToToolsBag`), adds the widened points, `CloseSequences()`. Useful for auto-generating water/soil ribbons along a drawn or generated line.

## Feasibility verdict: three pipeline designs

Common trunk for all three (headless constraints in [automation-surface.md](automation-surface.md): net48 host in the install dir + a Friend-wall facade, since `modSegmentsTools`, `modImport`, `modExport` and `cCalculate.Calculate` are all assembly-internal — `Module modSegmentsTools` at cSurveyPC/modSegmentsTools.vb:8 has default Friend access):

```
TopoDroid (phone): export cSurvey .csx  ─►  cSurvey.Load(path, LoadOptionsEnum.FixTopoDroid)
  ─► survey.Invalidate() : survey.Calculate.Calculate(True)   ' therion.exe required
  ─► [pipeline-specific sketch step]
  ─► survey.SaveTo(out.csz)  and/or  render (Plan/Profile.Paint → PNG, ToSvg → SVG,
      TherionThExportTo + ExecuteTherion → PDF; see exports-and-printing.md)
```

Note the input is TopoDroid's **exported .csx**, not TopoDroid's own project zip — nothing in cSurvey reads that zip ([topodroid-import.md](topodroid-import.md)). "TopoDroid zip in" therefore means either asking users to export csx, or writing a new TopoDroid-zip → csx converter outside cSurvey (TopoDroid's zip contains a SQLite DB + .th2 sketches (inferred)).

### Pipeline A — Reuse the TopoDroid phone sketch (recommended default)

- **Call sequence**: exactly the common trunk; Flow 3 does all sketch work inside `Load`. If only .th/.th2 exist: `cTherion.Import(survey, thFile, options)` then `modImport.TherionTh2ImportFrom(survey, th2File, cave, ImportPlan Or ImportProfile Or MergeAndReorderBorders, 1)` (cSurveyPC/modImport.vb:490).
- **Output quality**: whatever the surveyor drew in the cave — genuinely a *sketch*, with walls, morphology and sections, correctly typed and bound. This is the only pipeline that yields something resembling a finished map, because a human made the cartographic decisions at survey time. Losses: audio/photo points dropped, `line section` becomes cosmetic, orientation/scale lost on some symbols (cSurveyPC/cImportTopoDroidHelper.vb:226-235, 337-342).
- **Gaps requiring new code**: none in the conversion itself; the work is the headless host + facade (settings init, localized strings, therion.path) per [automation-surface.md](automation-surface.md), plus output rendering replication (~50-line recipes in [rendering-and-plot.md](rendering-and-plot.md) / [exports-and-printing.md](exports-and-printing.md)).
- **Effort**: ~1-2 weeks (host + facade + render/export + smoke tests). Risk: low — this path runs today inside `pSurveyImportcSurvey`.

### Pipeline B — Synthesize walls from splays (no phone sketch)

- **Call sequence** (after the trunk): for each cave/branch with shots:
  1. Plan: `modSegmentsTools.CreatePlanBorderFromSplay(survey, cave, branch, cIItemLine.LineTypeEnum.Splines, AngularPrecision:=5-15, BorderHullEnum.None)` (modSegmentsTools.vb:424).
  2. Rebind: force binding on each returned item — either call the Friend `item.BindSegments()` from the facade, or from Public surface toggle `item.SetCave("", "", True)` then `item.SetCave(cave, branch, True)` (cSurveyPC/cItem.vb:644-663 only binds on actual change).
  3. Profile: **no generator exists** (empty stub, modSegmentsTools.vb:645). Options: (a) implement `CreateProfileBorderFromSplay` mirroring the plan algorithm over `Data.Profile.FromSplays/ToSplays` in (D,Z) space — the projection math already exists (cSurveyPC/cPlotProfile.vb:210-290), so this is a ~150-300-line port of :316-441; or (b) use `CreateBorder3DOutline(survey, cave, branch, True)` — but with splay-only TopoDroid data (`l/r/u/d = 0`, verified in buless.csz) it produces minimum-size tubes, so you must first **synthesize LRUD from splays** (new code: per station, bucket splays into left/right relative to shot bearing and up/down by inclination, write `Segment.Left/Right/Up/Down`), or flag ceiling/floor splays as `Cut` (`cSegment.Cut = True` forces Splay+Exclude, [3d-and-surface.md](3d-and-surface.md)).
  4. Optionally decorate: presumed borders at passage ends (`CreatePresumedCaveBorder`, cLayerBorders.vb:43), altitude quotas at stations, cross-section items at junctions (with `ShowSplayBorder = True` so the section shows the splay envelope for a human to refine later, cItemCrossSection.vb:228).
  5. QA loop: after generation, `modDesignLRUD.GetLRFromDesign` (modDesignLRUD.vb:740) raycasts the new borders — compare against max splay extents per station; large mismatch flags bad geometry.
- **Output quality — be honest**: a *wall envelope*, not a map. Expect: correct overall passage shape where splay coverage is dense; blobby octagon-union artifacts in sparse-splay or vertical passages (every station contributes a 0.3 m octagon); plan walls include ceiling/floor splays unless per-shot inclination ranges are set (the generator ignores the `InRange` filter flag, modSegmentsTools.vb:331-333); one undifferentiated border with no floor detail, no rocks/water/sediment, no ceiling morphology, no labels, no passage-overlap resolution. A cartographer adds exactly the things this cannot: interpreting splays into floor vs wall vs ceiling, drawing what the instrument didn't reach, choosing symbols, and composing legible overlaps. Realistic target: a "working sketch" comparable to Therion's auto-generated passage outlines, good as a tracing base and for quick-look maps.
- **Gaps requiring new code**: profile generator (the single biggest gap); binding step; per-shot splay filtering defaults (set `PlanSplayBorderProjectionType/InclinationRange` per segment before Calculate for sane plan walls); optional LRUD-from-splay synthesis; smoothing/point-reduction pass (`modPaint.ReducePoints` exists, referenced at modPaint.vb:4149).
- **Effort**: ~2-4 weeks on top of Pipeline A's host (profile port 1-2 w, LRUD synthesis + tuning 1 w, QA/smoothing 1 w). Risk: medium — algorithm exists and runs (debug menu), but it is explicitly experimental and untuned.

### Pipeline C — Hybrid (best achievable "finished sketch")

- **Design**: per cave/branch, if the loaded TopoDroid file contains drawing items (detect via `DataProperties import_source` stamps or simply non-empty `Survey.Plan/Profile` layers) use them (A); otherwise synthesize (B). Always: add quotas/entrance markers/cross-sections, run the LRUD QA raycast, then export plan+profile PDFs through the TherionPad path (`pSurveyExportToTherion` recipe, cSurveyPC/frmMain2.vb:9674, [exports-and-printing.md](exports-and-printing.md)) or SVG/PNG directly.
- A variant worth noting: skip in-cSurvey wall synthesis for the profile and let **therion** draw splays in the output (`TherionThExportTo` with `ExportSplay Or SegmentSplayWithoutName`, modExport.vb:653/669/3505/3538 — commit 7a7fe49 added the anonymous-"`.`" form) — therion renders splay fans as grey rays in its maps, which reads as a point-cloud sketch without any generated items (inferred for the therion-side rendering; the export side is verified).
- **Effort**: A + B + ~1 week orchestration/detection logic.

**Verdict**: fully automatic "finished cartography" from measurements alone is not achievable with honest quality — but (1) *finished sketch when the surveyor drew on the phone* is already implemented end-to-end and only needs a headless host, and (2) *automatic wall envelope when they didn't* is ~70% implemented for plan (needs binding fix + tuning) and 0% for profile (stub, but all input projections exist). Pipeline C is the right product target.

## How to modify safely

- **Always bind after generating**: any programmatically created item must end with `BindSegments()` (or a cave-changing `SetCave`) or it silently detaches from warping; the interactive reference is `cEditTools.pEndItem` (cSurveyPC/cEditTools.vb:1927-1931). Points bound to shots are rewarped on every recalculation (cSurveyPC/cDesignPlan.vb:207-261) — an *unbound* generated border will drift the first time data changes.
- **Run Calculate before generating**: `pCreatePlanBorderPathFromSplay` reads `Segment.Data.Plan.FromSplays/ToSplays` and projected points — all populated only by `cCalculate.Calculate`/`CalculateSplay`. Generating from a stale or never-calculated survey yields empty/garbage geometry.
- **Preserve the closed-sequence convention**: generators close polygons by re-adding the first point (modSegmentsTools.vb:435-436); `cItemInvertedFreeHandArea` on the Borders layer is what clips lower layers — an unclosed border breaks cave-area fill ([drawing-engine.md](drawing-engine.md)).
- **Respect line-type side effects**: `AddFromPaintPoint` inserts two extra control points per vertex when the active sequence is Beziers (cPoints.vb:88-92) — set `LineType` *before* adding points and don't mix conventions (Flow 2 relies on this for its bezier borders).
- **Clipper scale is 1 cm**: polygons are int-scaled ×100 (modSegmentsTools.vb:326 etc.); geometry finer than 1 cm collapses.
- **Per-shot splay filters are persisted survey data** (cSegment.vb:214-304): changing their defaults (modSegmentsTools.vb:9-23) changes how *existing* surveys project splays on next calculate.
- If you implement `CreateProfileBorderFromSplay`, keep the signature/product parallel to the plan version (return `cItemInvertedFreeHandArea` on `Survey.Profile.Layers(Borders)`) so frmMain2.vb:15918 can dispatch it, and remember profile coordinates are (D, Z-down) per-connection — junction stations unroll to different D values ([calculation-engine.md](calculation-engine.md)), so a whole-branch Clipper union must be done per segment-group, not globally (inferred).

## Gotchas

- **The generator UI is debug-only**: `mnuDesignItemSegmentSplayCreateBorder.Visible = bIsInDebug` (frmMain2.vb:15901) — users can't reach `CreatePlanBorderFromSplay` in a normal build; treat it as experimental code, not battle-tested.
- **Generated borders are never bound** in the current UI flow (no `BindSegments` after frmMain2.vb:15922-15924) — they won't warp. The 3D-outline flow is no better: its `SetCave(Cave, Branch)` (modSegmentsTools.vb:572-576) does trigger `BindSegments`, but it runs *before* the points are added (:584-609), so it binds nothing; a corrective `BindSegments()` after point insertion is needed in both flows.
- **`CreateProfileBorderFromSplay`/`pCreateProfileBorderPathFromSplay` are empty** (modSegmentsTools.vb:641-647): they compile (VB allows functions without Return) and return `Nothing` — calling them does nothing.
- **`CreateBorder3DOutline` ≠ splays**: despite living behind the "border from splay" panel, its walls come from LRUD side points (Get3DPoints, cHolosViewer.xaml.vb:1226-1292); splays contribute only via their own `l/r/u/d` fields (cCalculate.vb:1301-1309, normally 0) or `Cut` flags. TopoDroid splay-only data → minimum tubes.
- **`Properties.ThreeDModelMode > Simple` inverts the dependency**: in Oversample modes side points are measured *from the drawings* (`cCalculate.CalculateDataFromDesigns`, cSurveyPC/Calculate/cCalculate.vb:271, invoked from cHolosViewer.xaml.vb:669; `Get3DPoints` switches to the SubData-based path behind the `ThreeDModelMode > Simple` gate at cHolosViewer.xaml.vb:1238) — running the 3D-outline generator on such a survey with no drawings yet gives degenerate output; buless.csz ships with `threedmodelmode="2"`.
- **The `InRange` splay filter is cosmetic to the generator**: `pCreatePlanBorderPathFromSplay` iterates all `FromSplays/ToSplays` ignoring the flag (modSegmentsTools.vb:331-333) — per-shot inclination filtering affects rendering, not generated walls, unless you pre-filter.
- **`pCreatePlanBorderFromSplay` requires a real cave name**: it resolves `Survey.Properties.CaveInfos(Cave)` (modSegmentsTools.vb:403) — TopoDroid imports do create a cave, but an empty cave string will fail (inferred from the indexer usage).
- **Friend wall**: `modSegmentsTools`, `modDesignLRUD`, `modPaint` are Friend modules (modSegmentsTools.vb:8, modDesignLRUD.vb:14, modPaint.vb:19) and `cItem.BindSegments` is Friend (cItem.vb:796) — an external MCP host needs InternalsVisibleTo or an in-repo facade ([automation-surface.md](automation-surface.md)).
- **`cBorderFromSplay`/`cAreaFromSequence` are just settings panels** (cBorderFromSplay.vb:14-41) — all logic lives in frmMain2 handlers + modules; don't look for algorithms there. `frmSplay` is likewise only the per-segment splay-tuning dialog (frmSplay.vb:214-237).
- **Cross-section splay border is display-only** (cItemCrossSection.vb:644-704): it renders projected splay points/rays for tracing; no facility converts them into a section outline item.
- **Dead/duplicate code**: `pConcaveHull` never called (modSegmentsTools.vb:684); `Design2D/` copies of `cIItemSplayBorder`/layer factories are stale and uncompiled ([drawing-engine.md](drawing-engine.md)).

## Related docs

- [topodroid-import.md](topodroid-import.md) — csx/th/th2 ingestion, sketch conversion, binding fix-ups
- [drawing-engine.md](drawing-engine.md) — item model, layer factories, points grammar, warping invariants
- [calculation-engine.md](calculation-engine.md) — where splay projections and side measures are computed
- [rendering-and-plot.md](rendering-and-plot.md) — headless PNG/SVG rendering of the finished sketch
- [exports-and-printing.md](exports-and-printing.md) — therion export flags (splay export) and PDF production
- [automation-surface.md](automation-surface.md) — Friend wall, headless host architecture, MCP recommendation
- [3d-and-surface.md](3d-and-surface.md) — cave_model/DNetCMCave, LRUD-from-design oversample modes
- [human-workflow-and-glossary.md](human-workflow-and-glossary.md) — what a human cartographer actually does per stage
