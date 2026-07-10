# 3D Model & Surface/Terrain

## Purpose

This subsystem renders the interactive 3D view of the cave ("Holos" viewer), generates the 3D passage-wall model from survey data, and manages surface terrain data (DEM elevations, orthophotos, WMS map layers) that can be draped over the cave in 3D, used as map backgrounds in 2D, and exported to Therion/Loch. It is a *downstream consumer* of the calculation engine and of the 2D drawings — it never modifies survey data.

## Domain concepts

- **Holos** — cSurvey's built-in 3D viewer. A WPF `UserControl` (`cHolosViewer`, XAML + code-behind) hosted inside the WinForms main window through an `ElementHost` (`h3D`), rendered with HelixToolkit.Wpf 2.27.3 (cSurveyPC/packages.config:13; `HelixViewport3D` named `mainViewport`).
- **cave_model / DotNetCaveModel** — a native C++ passage-wall mesh generator (repo folder `cave_model/`, a C++/CLI project referenced by cSurveyPC at cSurveyPC/cSurveyPC.vbproj:5105). Its managed wrapper class is `DotNetCaveModel.DNetCMCave` (cave_model/dNetCMCave.h:99). Comments and terminology ("piket" = survey station) are Russian; it bundles the `wykobi` geometry library and OGRE-derived math (cave_model/cave_model/ subfolders `wykobi`, `ogre`, `common`, `format`) — third-party origin (inferred).
- **Piket** — a station vertex fed to cave_model (`DNPiketInfo`: id, name, x/y/z, `extendedElevationX`, marks like `MARK_Z_TURN`, cave_model/dNetCMCave.h:40-56). Walls (`addWall`) are radial points around a piket; edges (`addEdge`) connect pikets.
- **SubData** — oversampled per-shot subdivisions with their own LRUD, computed by `cCalculate.CalculateDataFromDesigns` when `ThreeDModelMode > Simple` (cSurveyPC/Calculate/cCalculate.vb:271). The LRUD values are measured *from the user's 2D plan/profile drawings*, not from shot data (cSurveyPC/Calculate/cCalculate.vb:334-344 uses `modDesignLRUD.GetLRFromDesign` / `GetUDFromDesign`).
- **ThreeDModelMode** — survey property enum `Simple = 0 / Oversample = 1 / AdvancedOversample = 2` (cSurveyPC/cProperties.vb:907-911). Governs whether the 3D walls come from plain plot side-points or from design-derived oversampled LRUD.
- **Cut shot** — a splay flagged `Cut`; setting `Cut = True` forces `Splay = True` and `Exclude = True` (cSurveyPC/cSegment.vb:574-584). Cut shots are the only splays that contribute *wall points* to the 3D model (cSurveyPC/Specialized/cHolosViewer.xaml.vb:2014-2017).
- **Chunk (`cItemChunk3D`)** — an imported external 3D model (OBJ + MTL + textures, e.g. photogrammetry) stored inside the survey file and anchored to two survey stations. Chunks live in a third design, the "3D design" (`cDesign3D`, XML element `model3d`).
- **Surface items** — three collections under `cSurvey.Surface`: `cElevations` (DEM grids), `cOrthoPhotos` (georeferenced raster images), `cWMSs` (WMS server definitions). Persisted under `<surface>` in `_data.xml` (cSurveyPC/cSurface.vb:136-143).
- **Loch / .lox** — Therion's 3D viewer and its file format. cSurvey does not write .lox itself; it exports .th + surface data, runs `therion.exe` with `export model -fmt loch`, then launches `loch.exe`.

## Architecture

Two largely independent halves share the Holos viewport:

**Cave geometry half.** `frmMain2` owns one `cHolosViewer` instance (`oHolos`), created at startup and plugged into ElementHost `h3D` (cSurveyPC/frmMain2.vb:14125-14130; failure disables the 3D buttons). When the 3D pane needs a redraw, `pSurvey3DForceRedraw` recalculates the survey if invalidated and calls `oHolos.Redraw(oSurvey, DirectCast(oCurrentOptions, cOptions3D), o3DTools)` (cSurveyPC/frmMain2.vb:15703-15708). View options are the `cOptions3D` instance stored under key `"_design.3d"` in the survey options collection (cSurveyPC/cOptionsCollection.vb:33). `Redraw` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:673) rebuilds the whole scene: centerline plot, station markers/labels, splays, LRUD crosses, the wall model, chunks, and the terrain, all collected into a `SortingVisual3D` added to `mainViewport` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:735-742).

Coordinates: station 3D positions are *not* taken from raw shot data but merged from the already-computed 2D plots — plan X/Y plus profile Y as depth: `x = Plan.X`, `y = -Plan.Y`, `z = -Profile.Y`, scaled by `AltitudeAmplification` (`Get3DPoints`, cSurveyPC/Specialized/cHolosViewer.xaml.vb:1226, 1423-1435). Each station gets 5 sub-points (`SubPointIndexEnum` Center/Left/Right/Up/Down, cSurveyPC/Specialized/cHolosViewer.xaml.vb:1206-1212) built from the plot's side points (`Data.Plan.FromSidePointLeft/Right`, `Data.Profile.FromSidePointUp/Down`). Linked surveys are positioned by UTM offset of their origin against the main survey origin, rotated by meridian convergence (cSurveyPC/Specialized/cHolosViewer.xaml.vb:1551-1566).

The wall mesh is produced by cave_model: `pCaves` feeds every non-splay/non-surface/non-duplicate shot (or its SubDatas) into a `DNetCMCave` via `addVertice` + 4 `addWall` LRUD rays per station + `addEdge` per shot (cSurveyPC/Specialized/cHolosViewer.xaml.vb:1946-2043), sets `RenderMode` (`SM_ROUGH_WALLS`/`SM_SMOOTH_WALLS`/`SM_CUTS`/`SM_OUTLINE`) and `ColoringMode` from `cOptions3D` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:2048-2049; enum clones at cSurveyPC/cOptions3D.vb:16-30), calls `finishInit`, and converts the returned triangles (`getOutputPoly`) into per-color `MeshGeometry3D` visuals (cSurveyPC/Specialized/cHolosViewer.xaml.vb:2070-2151). Outline mode re-queries cave_model on camera moves via a timer (cSurveyPC/Specialized/cHolosViewer.xaml.vb:2244-2296).

**Surface half.** `cSurvey.Surface` (property of the survey) aggregates elevations, orthophotos and WMSs and re-emits change events (cSurveyPC/cSurface.vb:46-116). In the 3D view, `pSurface` converts the selected `cElevation` grid into a float array (NoData→0, altitude × amplification), composes a texture from the visible orthophoto/WMS layers via `modPaint.GetSurfaceImage` (cSurveyPC/modPaint.vb:3332-3370), and hands both to the forked `TerrainVisual3D` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:255-385). The fork `HelixToolkit.Wpf.cSurveySpecialized` (own project) is a 3-file specialization of HelixToolkit's terrain visual: instead of loading `.bt` files from disk, `TerrainVisual3D.Source` accepts a `cITerrainElevation` interface (width/height/float data/texture bitmap/opacity/LOD, HelixToolkit.Wpf.cSurveySpecialized/cITerrainElevation.cs:9-57) implemented by `cHolosViewer.cElevation` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:143-144); `TerrainModel.CreateModel(lod)` builds the mesh (HelixToolkit.Wpf.cSurveySpecialized/TerrainVisual3D.cs:98-119). Terrain is positioned by the DEM's top-left corner in survey coordinates (`cElevation.GetTLPoint` converts UTM corner minus survey-origin UTM, cSurveyPC/cElevation.vb:813-817).

The same surface items also serve the 2D designer (WMS/orthophoto map backgrounds and the surface profile line via `cOptionsDesign.SurfaceOptions` — see cSurveyPC/DesignPropertyControl/cDesignSurfaceControl.vb:39-64) and the Therion/Loch export (`cSurface.CreateTherionSurfaceDataFile` writes a `surface ... grid ... endsurface` block plus JPG bitmap, cSurveyPC/cSurface.vb:145-226).

## Key classes & files

| File | Class / member | Responsibility |
|---|---|---|
| cSurveyPC/Specialized/cHolosViewer.xaml.vb | `cHolosViewer` (2559 lines) | The whole 3D viewer: scene build (`Redraw`:673), station point extraction (`Get3DPoints`:1226, `GetStations3DPoints`:1443), wall model via cave_model (`pCaves`:1523), terrain (`pSurface`:255), chunks (:2157-2207), outline mode (`pCavesOutline`:2254), hit-testing/hotspots, camera (`SetView`:442, `CameraType`:415), export (`Export`:1175) |
| cave_model/dNetCMCave.h/.cpp | `DotNetCaveModel.DNetCMCave` | C++/CLI wrapper over native `CM::Cave`: `addVertice`/`addEdge`/`addWall`/`finishInit`/`getOutputPoly`/`getOutputLine`, `RenderMode`, `ColoringMode` |
| cave_model/cave_model/CMCave.h | `CM::Cave` | Native passage-wall mesh generator (triangulation, smoothing, outline, extended-elevation conversion) |
| cSurveyPC/Calculate/cCalculate.vb | `cCalculate.CalculateDataFromDesigns` (:271) | Builds per-shot SubDatas with LRUD sampled from the 2D plan/profile drawings (`modDesignLRUD.cLRUDFromDesignCache2`, `GetLRFromDesign`/`GetUDFromDesign`) for Oversample modes |
| cSurveyPC/cOptions3D.vb | `cSurvey.Design.cOptions3D` | 3D paint options (DrawModel/DrawSplay/DrawLRUD/DrawChunks, RenderMode/ColoringMode clones, `SurfaceOptions`); stored as options key `"_design.3d"` |
| cSurveyPC/cOptions.cSurface3DOptions.vb | `cSurface3DOptions`, `cSurface3DOptionsElevationItem` | Which elevation drives the terrain, per-layer visibility/transparency, `AltitudeAmplification` (:32-41) |
| cSurveyPC/cProperties.vb | `ThreeDModelModeEnum` (:907), `ThreeDOversamplingFactor`, `ThreeDMinPassageSize`, `ThreeDPrecision`, `ThreeDNormalizationFactor`, `ThreeDSurfaceModelLod`, `ThreeDSurfaceTextureLod`, `ThreeDLochShowSplay` (:107-116) | Survey-level 3D tuning knobs |
| cSurveyPC/cSurface.vb | `cSurvey.cSurface` | Aggregate of Elevations/OrthoPhotos/WMSs; XML `<surface>`; Therion surface export (`CreateTherionSurfaceDataFile`:145) |
| cSurveyPC/cElevation.vb | `cSurvey.Surface.cElevation` | DEM grid (rows/cols/cellsize/UTM or WGS84 corner). `.asc` ArcASCIIGrid import (`Import`:506, header parsing :601-630), WGS84→UTM reprojection (`pConvertToUTM`:670), `GetElevation(x,y)`:853, `GetTLPoint`:813, `Reduce`:78, `RemoveNodata`:108. `NoDataValue = -99999` (:12) |
| cSurveyPC/cOrthoPhoto.vb | `cSurvey.Surface.cOrthoPhoto` | Georeferenced raster; import = image + ESRI world file (`.jgw`/`.jpw`…, `pGetWorldFileFromImageFilename`:417, `Import`:431) |
| cSurveyPC/cWMS.vb | `cSurvey.Surface.cWMS`, `cWMSLayer` | WMS server definition (URL + layer + SRS override); `GetImage(TL,BR,Ratio)` builds a GetMap request and downloads via the tile manager (:199-209) |
| cSurveyPC/modWMSManager.vb | `modWMSManager` | GetCapabilities layer listing (`WMSDownloadLayerList`:24), sync/async tile download with disk cache at `%APPDATA%\cSurvey\wmscache` (`WMSLoadTile`:502, `WMSLoadTileAsync`:435), online/offline state (:385-393) |
| cSurveyPC/cDesign3D.vb | `cSurvey.Design.cDesign3D` | Third design (`Type = ThreeDModel`, XML `model3d`) holding `cLayers3D`; accessed as `Survey.ThreeD` (cSurveyPC/cSurvey.vb:1627-1631, loaded at :1404-1408) |
| cSurveyPC/cLayers3D.vb, cLayerChunk3D.vb, cLayer3D.vb | `cLayers3D` (`ChunkLayer`:82), `cLayerChunk3D` | Single-layer ("Chunks") layer collection of the 3D design |
| cSurveyPC/cItemChunk3D.vb | `cSurvey.Design.Items.cItemChunk3D` | Imported OBJ model as design item: `LoadModel()` via HelixToolkit `ModelImporter` (:141-155), material recoloring by cave/branch (:102-135), station anchors + transform |
| cSurveyPC/cChunks3Ds.vb | `cSurvey.Design3D.cTransform3D`, `cModelStations3D` (:209), `cModelFiles3D` (:283) | Chunk support types; model files embedded in .csz under `_data\design3d\<chunkID>\` or base64 in .csx (:364-386). This file is the only live code in namespace `cSurvey.Design3D` |
| cSurveyPC/cModel3DHelper.vb | `cModel3DHelper` | Static OBJ/MTL helpers: collect referenced files (`GetObjFilenames`:49), rewrite mtllib paths (:24) |
| cSurveyPC/frmSurface.vb | `frmSurface` | Surface manager dialog: import DEM/orthophoto, add/edit WMS, WMS→orthophoto snapshot (`oOrthophotoFromWMS_click`:642), elevation-from-orthophoto, NoData removal |
| cSurveyPC/frmLochDialog.vb | `frmLochDialog` | Pre-Loch dialog: pick elevation + orthophoto (stored in options `"_loch"`, a `cOptionsTherion`) and linked surveys (:8-62) |
| cSurveyPC/frmExportHolos.vb | `frmExportHolos` | Small options dialog for 3D data export (profile/LRUD/surface/colors, persisted in registry) |
| cSurveyPC/Specialized/frmHolosItemEdit.vb | `frmHolosItemEdit` | Chunk placement editor (rotate/scale/anchor to 2 stations); exports via `ObjExporter` (:539) |
| cSurveyPC/Specialized/frmItemChunk3DPlanRenderer.vb | `frmItemChunk3DPlanRenderer` | Experimental: renders a chunk top-down with an orthographic camera to a PNG (plan image of a photogrammetry model) — note hardcoded `d:\prova.jpg` (:80) |
| HelixToolkit.Wpf.cSurveySpecialized/ | `TerrainVisual3D`, `TerrainModel`, `cITerrainElevation` | The whole "fork": a terrain visual fed from in-memory elevation + texture instead of .bt files |
| cSurveyPC/cModel3D.vb, cSurveyPC/Design3D/*.vb | — | **Dead code.** cModel3D.vb is 100% commented out; the Design3D/ folder duplicates several class names but none of its files are in the .vbproj `<Compile>` list |

## Key flows

### 1. Rendering the 3D cave view

1. cSurveyPC/frmMain2.vb:15699-15708 — `oHolos_OnRedrawRequest` → `pSurvey3DForceRedraw`: recalc survey if invalidated, then `oHolos.Redraw(oSurvey, cOptions3D, o3DTools)`.
2. cSurveyPC/Specialized/cHolosViewer.xaml.vb:673-770 — `Redraw` clears the scene; if `ThreeDModelMode > Simple` and model/LRUD drawing is on, calls `pCalculateSubData` (:664) → `Survey.Calculate.CalculateDataFromDesigns` (also for linked surveys).
3. cSurveyPC/Calculate/cCalculate.vb:271-353 — for each valid non-splay shot, clears and re-adds `SubDatas`, sampling LRUD from the plan/profile drawings (`GetLRFromDesign`/`GetUDFromDesign` :334-337), normalizing (`pNormalizeSize` with `ThreeDMinPassageSize`) and smoothing (`UniformSubDataLRUD` :347).
4. cSurveyPC/Specialized/cHolosViewer.xaml.vb:1523-1567 — `pCaves` computes UTM origin offsets per (linked) survey and calls `Get3DPoints`.
5. cSurveyPC/Specialized/cHolosViewer.xaml.vb:1226-1441 — `Get3DPoints` builds `Dictionary(stationName → [Center, Left, Right, Up, Down] Point3D)` from plot plan/profile points and side points (SubDatas when present).
6. cSurveyPC/Specialized/cHolosViewer.xaml.vb:1943-2070 — if `DrawModel`: new `DNetCMCave`; `addStationFunc` adds a piket + up to 4 LRUD walls per station (:1950-1991); shots become `addEdge` calls (per SubData when `ThreeDModelMode > Simple`, :2019-2039); `Cut` shots add their To-point as a wall (:2014-2017); then `setMode`/`setColoringMode`/`finishInit` (:2048-2070).
7. cSurveyPC/Specialized/cHolosViewer.xaml.vb:2072-2151 — output triangles are bucketed by color into `MeshGeometry3D` + `MeshGeometryVisual3D`; cut/outline lines become `LinesVisual3D`.
8. cSurveyPC/Specialized/cHolosViewer.xaml.vb:718-742 — `pSurface` terrain + everything else is wrapped in a `SortingVisual3D` (transparency sorting) and added to `mainViewport`.

### 2. Importing a DEM (.asc) and draping an orthophoto

1. cSurveyPC/frmSurface.vb:778 — `btnDataAdd_Click` → file dialog → coordinate-system dialog (`frmSurfaceImportASCOptions`, UTM zone/band or WGS84 parameters, same pattern as :319-327).
2. cSurveyPC/cElevation.vb:506-668 — `Import(ArcASCIIGrid, filename, options)` parses `ncols/nrows/xllcorner/yllcorner/xllcenter/cellsize/nodata_value` headers (:601-630), fills `oData(rows, cols)`, maps file NoData to `-99999` (:585-589); WGS84 grids are reprojected to UTM by image-warping (`pConvertToUTM` :670).
3. cSurveyPC/frmSurface.vb:310-349 — orthophoto import: image file + world file found by naming convention (cSurveyPC/cOrthoPhoto.vb:417-429), producing a georeferenced `cOrthoPhoto`.
4. Alternatively cSurveyPC/frmSurface.vb:642-676 — WMS snapshot: `cWMS.GetImage(TL, BR, ratio, background)` (cSurveyPC/cWMS.vb:199-220) downloads a GetMap image covering the selected elevation's bounding box through `modWMSManager.WMSLoadTile` (disk cache, cSurveyPC/modWMSManager.vb:502-532) and stores it as a new orthophoto.
5. In 3D, the terrain texture is composed per redraw by `modPaint.GetSurfaceImage` (cSurveyPC/modPaint.vb:3332-3370): orthophotos are placed by UTM offset, WMS layers are tiled live via `MapDrawWMS` (:3395).

### 3. "View in Loch" (Therion 3D interop)

1. cSurveyPC/frmMain2.vb:9778-9789 — `frmLochDialog` collects elevation/orthophoto/linked-survey choices into options `"_loch"`; `ThreeDModelMode > Simple` triggers `CalculateDataFromDesigns`, otherwise splays may be exported (`ThreeDLochShowSplay` → `CalculateSplay Or ExportSplay`).
2. cSurveyPC/frmMain2.vb:9808-9816 — `modExport.TherionThExportTo(oSurvey, tempInput.th, dictionary, options)`; with SubData mode the export writes the oversampled shots (`TherionExportOptionsEnum.UseSubData`). Surface data goes along via `ExportSurfaceElevationsData` → `cSurface.CreateTherionSurfaceDataFile` (cSurveyPC/cSurface.vb:145-226).
3. cSurveyPC/frmMain2.vb:9850-9854 — `TherionCreateConfig(..., "export model -fmt loch -output <tmp>.lox")`, then `modMain.ExecuteTherion` runs therion.exe.
4. cSurveyPC/frmMain2.vb:9857-9859 — on success, `loch.exe` (looked up next to the configured therion.exe) is launched on the .lox; "save" instead moves the .lox to a user path (:9861-9871). The generic 3D data export path (`btnTherionPadExport3D_ItemClick`, cSurveyPC/frmMain2.vb:9919-9948) uses the same mechanism with `-fmt loch|compass|survex|dxf|esri|vrlm|3dmf|kml`.

### 4. Exporting the Holos scene / adding a chunk

1. Export: cSurveyPC/frmMain2.vb:16672-16674 → `oHolos.Export()` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:1175-1204) — `Viewport3DHelper.Export` writes STL/DAE/X3D/OBJ/PNG/JPG of the currently rendered scene.
2. Chunk import: `cItemChunk3D.New(..., Filename)` loads the OBJ and all files referenced from its mtllib chain into memory (cSurveyPC/cItemChunk3D.vb:184-193, cSurveyPC/cChunks3Ds.vb:307-315); on save they are embedded in the .csz storage (cSurveyPC/cChunks3Ds.vb:364-386). At render time `GetModel(Options)` caches a `Model3DGroup` and recolors materials by cave/branch if requested (cSurveyPC/cItemChunk3D.vb:102-135); the viewer places it via the two station anchors and `cTransform3D`, optionally cut by a `CuttingPlaneGroup` ("remove ceiling", cSurveyPC/Specialized/cHolosViewer.xaml.vb:2157-2207).

## How to modify safely

- **Do not touch the dead twins.** Every 3D class exists twice: the live file at cSurveyPC root (in the .vbproj) and an orphan in `cSurveyPC/Design3D/` (not compiled), plus fully-commented `cSurveyPC/cModel3D.vb`. Verify a file appears in `cSurveyPC/cSurveyPC.vbproj` `<Compile Include=...>` before editing; the live `cSurvey.Design3D` namespace lives only in cSurveyPC/cChunks3Ds.vb:21.
- **Axis convention is load-bearing:** 3D scene = `(PlanX, -PlanY, -ProfileY)` with Z scaled by `AltitudeAmplification` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:1423-1426). Terrain, chunks, sea-level quad and cave meshes all rely on it; changing signs anywhere desynchronizes cave vs terrain.
- **3D depends on the 2D plots being calculated.** `Redraw` reads `Segment.Data.Plan/Profile` — call `Survey.Calculate` first (frmMain2 does this at cSurveyPC/frmMain2.vb:15705). Headless code must replicate that ordering.
- **`Redraw` must run on a WPF-capable STA UI thread** — it builds WPF visuals and reads `mainViewport.Camera` (inferred from WPF threading rules; all invocations are from the UI thread).
- **cave_model is native C++ (x86/x64 per build config).** Changing `DNPiketInfo`/`DNWall` marshaling requires rebuilding `cave_model.vcxproj`; the enums in `cOptions3D` are hand-cloned from `DotNetCaveModel` (cSurveyPC/cOptions3D.vb:15-30) and must stay value-identical.
- **Terrain source interface:** `cITerrainElevation.Data` is a flat row-major float array built bottom-up (rows iterated `dRows-1 To 0`, cSurveyPC/Specialized/cHolosViewer.xaml.vb:279-289) and the final texture is Y-flipped (cSurveyPC/modPaint.vb:3368); keep both flips paired.
- **Surface XML is lenient by design** — each collection load is wrapped in Try/Catch falling back to empty (cSurveyPC/cSurface.vb:57-83); preserve that so old files keep loading.
- **NoData sentinel** `-99999` (cSurveyPC/cElevation.vb:12) is compared with `=` throughout; don't change the constant or interpolate through it.

## Gotchas

- The "3D model" walls are only as good as the 2D sketch: in Oversample modes LRUD is *measured from the drawn plan/profile outlines* (cSurveyPC/Calculate/cCalculate.vb:334-337). An empty sketch yields tube-like minimum-size passages (`ThreeDMinPassageSize` normalization :339-342). Plain splays (TopoDroid's main wall evidence) are **not** used for walls — they are drawn as lines only (`DrawSplay`), unless a splay is flagged `Cut`, which adds it as a wall point (cSurveyPC/Specialized/cHolosViewer.xaml.vb:2013-2017).
- `pCalculateSubData` clears and rebuilds `Segment.Data.SubDatas` on every 3D redraw when invalidated — heavy on big surveys; progress events with key `"3dsubdata"`/`"3dmodel"` are the observable heartbeat.
- The chunk texture workaround: `LoadModel` writes all embedded files to a temp dir, re-reads texture bitmaps into MemoryStreams, then deletes the dir — flagged "horrible" in-source (cSurveyPC/cItemChunk3D.vb:145-153). Expect disk+RAM spikes with photogrammetry models.
- `frmItemChunk3DPlanRenderer` saves to hardcoded `d:\prova.jpg` (cSurveyPC/Specialized/frmItemChunk3DPlanRenderer.vb:80) — experimental, not shippable as-is, but it is the seed of "render 3D scan to plan background" functionality.
- Outline render mode is camera-dependent: `setLookDirection` + full line regeneration on every camera stop, cancellable with ESC via `GetAsyncKeyState` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:2282).
- WMS tiles cache under `%APPDATA%\cSurvey\wmscache` and an in-memory dictionary (cSurveyPC/modWMSManager.vb:8-9); a global online/offline toggle sits in the status bar (cSurveyPC/frmMain2.vb:15714-15723). Offline yields placeholder images, not errors.
- Loch launch assumes `loch.exe` sits in the same directory as the configured `therion.exe` (cSurveyPC/frmMain2.vb:9858-9859).
- The `"_loch"` options entry is a `cOptionsTherion` (not `cOptions3D`) — surface selections for Loch and for Holos are configured in different places (cSurveyPC/frmLochDialog.vb:15 vs options `"_design.3d"`).
- `frmLochDialog` silently auto-accepts when "don't show" was checked or GPS is disabled (cSurveyPC/frmLochDialog.vb:93-102) — a headless Loch export may show no dialog at all.
- Example terrain data for testing lives at dev/example/Demo Survey/: `terrain.asc` (ArcASCIIGrid DEM), `terrain.jpg` + `terrain.jgw` (orthophoto + world file), `terrain.prj` (projection info; cSurvey does not parse .prj — coordinate system is chosen manually at import).

## Role in the TopoDroid workflow

3D is visualization/QA only — nothing in the TopoDroid-import → auto-sketch chain *requires* it. Useful touchpoints: (a) the Holos view is the quickest visual check that an import produced a sane centerline+splay cloud; (b) `Get3DPoints`/`GetStations3DPoints` (cSurveyPC/Specialized/cHolosViewer.xaml.vb:1226, 1443) are reusable, mostly-pure functions for getting 3D station coordinates out of a calculated survey; (c) if an auto-sketch produces plan/profile outlines, the 3D model (Oversample mode) immediately reflects their quality, making it a good automated regression signal; (d) marking imported splays as `Cut` shots would feed real wall points into the model without any drawing.

## Related docs

- [topodroid-import.md](topodroid-import.md) — how shots/splays get into the survey
- [calculation-engine.md](calculation-engine.md) — plot computation that feeds `Get3DPoints`
- [drawing-engine.md](drawing-engine.md) — the 2D designs whose outlines drive Oversample LRUD
- [exports-and-printing.md](exports-and-printing.md) — Therion export internals used by the Loch flow
- [data-model-and-file-format.md](data-model-and-file-format.md) — `_data.xml` layout (`<surface>`, `<model3d>`)
- [ui-map.md](ui-map.md) — where the 3D pane and surface dialogs live in frmMain2
