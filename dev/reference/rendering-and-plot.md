# Rendering pipeline & centerline plot

## Purpose

This subsystem turns the in-memory survey model (computed station coordinates + user drawings) into pixels (GDI+) and vectors (SVG). It covers the master paint pipeline in `cDesign.Paint`, the centerline "plot" renderers (`cPlot`/`cPlotPlan`/`cPlotProfile`), the retained-mode display-list cache (`cDrawCache`), and the highlight/customization system that colors shots and stations. The same pipeline serves four consumers — design editor, print preview, image/SVG export, and viewer — differing only by the `cOptionsCenterline`-derived options object passed in.

## Domain concepts

- **Design vs Plot** — a *design* (`cDesign` → `cDesignPlan`/`cDesignProfile`) is the user's drawing: 7 fixed layers of vector items. The *plot* (`cPlot` → `cPlotPlan`/`cPlotProfile`) is the machine-generated centerline overlay: shot lines, station symbols/labels, splays, LRUD polygons, highlights. Each design owns one plot (`cDesignPlan.vb:65-69`).
- **World coordinates are meters.** Everything renders in survey coordinates (1 unit = 1 m, origin = survey origin station); a single world→screen `Matrix` (zoom + translation) is set on the `Graphics` before painting. Pens/fonts are sized in world units.
- **PaintOptions** — a `cOptionsCenterline` subclass carries every draw switch (`DrawPlot`, `DrawSegments`, `DrawSplay`, `DrawLRUD`, `DrawHighlights`, `DesignStyle`, `CurrentScale`, …). Subclasses: `cOptionsDesign` (editor), `cOptionsPreview` (print), `cOptionsExport` (image/SVG), `cOptions3D` — all `Inherits cOptionsCenterline` (`cOptions.vb:168`); `cOptionsViewer` inherits `cOptionsDesign` (`cOptionsViewer.vb:6`). `Mode` distinguishes Design/Preview/Viewer (`cOptions.vb:63-67`). **The options *instance* is also the cache key** (see caching below).
- **Profiles (confusing name)** — `cViewerProfile`/`cPreviewProfile`/`cExportProfile` are *named bundles of options* ("profiles" like a settings preset), not the profile view (`cViewerProfile.vb:111-120`, `cPreviewProfile.vb:127-136`, `cExportProfile.vb:120`). The vertical-section design is called *Profile* (`cDesignProfile`).
- **Trigpoint** = survey station; **Segment** = shot. **Translations** = per-cave/per-branch XY offsets used to draw an "exploded" map; translated station copies are linked back with orthogonal translation lines (`cPlot.RenderTrigpointTranslations`, `cPlot.vb:410`).
- **Highlights** — user/system-defined conditional decorations of shots/stations (colored halo, gradient overlay), driven by embedded VB/C# scripts evaluated at render time.

## Architecture

Data flow, editor case:

1. `frmMain2.picMap_Paint` (`frmMain2.vb:4031`) fires on WinForms paint → `pSurveyDraw(e.Graphics)` (`frmMain2.vb:9248`).
2. `pSurveyDraw` sets GDI+ quality, applies the world→screen transform, then calls `oCurrentDesign.Paint(Graphics, oCurrentOptions, cDrawOptions.Empty, oDesignTools)` (`frmMain2.vb:9307`).
3. `cDesign.Paint` (`cDesign.vb:987`) orchestrates the full scene: surface maps → linked surveys → layers (items) → area fills → centerline plot (`Plot.Paint`, `cDesign.vb:1435`).
4. Every leaf renderer (item or plot) follows the same **render-then-paint** pattern: `Render` builds a `cDrawCache` display list *once* (only if `Invalidated`), `Paint` replays it onto the `Graphics` (e.g. `cItemFreeHandLine.vb:176-205`, `cPlotPlan.vb:634-647`).
5. Selection chrome, axis, metric grid, and rulers are drawn on top by `frmMain2`, *outside* `cDesign.Paint` (`frmMain2.vb:9290-9337`).

The display list makes the pipeline output-agnostic: `cDrawCache.Paint` replays to GDI+ (screen, printer, `Bitmap`), while `cDrawCache.ToSvgItem` serializes the same paths to SVG XML (`cDrawCache.vb:338`, `cDrawCache.vb:995`). Print preview and raster export reuse `cDesign.Paint` verbatim with a different options object and transform (`frmPreview.vb:1052-1086`); vector export walks the caches via `cDesignPlan.ToSvg` (`cDesignPlan.vb:444`).

Invalidation flow: recalculating the survey fires `oCalc_OnCalculateComplete` → `oPlan.Plot.Redraw()` / `oProfile.Plot.Redraw()` (`cSurvey.vb:1963-1966`), which clears all plot caches in parallel (`cPlotPlan.vb:244-251`). Item edits invalidate per-item caches via `cDesign.Redraw` (`cDesign.vb:156-163`). Options changes drop the per-options cache entry (`cDrawCaches.vb:64-73`).

## Key classes & files

| File | Class / module | Responsibility |
|---|---|---|
| `cSurveyPC/cDesign.vb` | `cDesign` (MustInherit) | Master paint pipeline for one view (plan or profile): surface, linked surveys, layers, area fills, then plot (`cDesign.vb:987-1441`); per-item cache invalidation (`:156`) |
| `cSurveyPC/cDesignPlan.vb` / `cDesignProfile.vb` | `cDesignPlan`, `cDesignProfile` | Concrete designs; own `cPlotPlan`/`cPlotProfile` (`cDesignPlan.vb:33`); SVG export entry `ToSvg` (`cDesignPlan.vb:444`) |
| `cSurveyPC/cPlot.vb` | `cPlot` (MustInherit) | Base centerline renderer: visible-segment filtering (`GetAllVisibleSegments`, `cPlot.vb:508`), translation-line drawing with interval dedup (`:370-447`), abstract `Paint`/`Render`/`Calculate`/`HitTest`/`GetBounds` |
| `cSurveyPC/cPlotPlan.vb` | `cPlotPlan` | Plan centerline: renders splays, LRUD areas, shot lines, highlights, station symbols+labels into per-segment/per-station caches (`Render`, `cPlotPlan.vb:253-605`); `Paint` replays caches (`:634`) |
| `cSurveyPC/cPlotProfile.vb` | `cPlotProfile` | Same for profile view (uses `Data.Profile` projections, U/D instead of L/R, adds surface profile line at `cPlotProfile.vb:509`) |
| `cSurveyPC/cDrawCache.vb` | `cDrawCache`, `cDrawCacheItem`, `cDrawCacheItemText`, `cDrawCacheSegmentCustomOptions`, `cDrawCacheTrigpointCustomOptions` | Retained display list: items typed Filler/SetClip/ResetClip/Border/Text each holding a `GraphicsPath` + cloned Pen/Brush (`cDrawCache.vb:747-753`); GDI replay (`:374`), SVG serialization (`:338`), hit-test (`:132`); custom per-element draw overrides (`:18-107`) |
| `cSurveyPC/cDrawCaches.vb` | `cDrawCaches` | `Dictionary(Of cOptionsCenterline, cDrawCache)` — one display list per options instance; `Invalidate(Options)` drops one or all entries (`cDrawCaches.vb:64`) |
| `cSurveyPC/cDrawOptions.vb` | `cDrawOptions` | Tiny flags wrapper: `Empty` vs `Schematic` (wireframe-ish page preview) draw mode |
| `cSurveyPC/modPaint.vb` | `modPaint` | GDI helpers: zoom↔scale (`GetZoomFactor` `:942`, `GetScaleFactor` `:958`), world↔screen point math (`ToPaintPoint` `:1008`), splay rendering (`PaintStationSplays` `:2734`), selection chrome (`PaintSelection` `:2863`), axis/grid/rulers (`MapDrawAxis` `:3127`, `MapDrawMetricGrid` `:3261`), surface maps (`MapDrawElevation` `:3317`, `MapDrawOrthophoto` `:3304`, `MapDrawWMS` `:3452`), print/export area overlay (`MapDrawPrintOrExportArea` `:3546`), inverse-transform viewport (`GetViewport` `:3688`) |
| `cSurveyPC/modRender.vb` | `modRender` | Plot glyph builders: entrance arrow (`:15`), shot highlight (gradient line, `:36`), station highlight (double halo, `:51`), station symbol with custom-option overrides (`RenderTrigPoint` `:80`), station label (`:64`) |
| `cSurveyPC/modPlot.vb` | `modPlot` | Cave/branch translation lookup (`GetPlanSegmentTranslation` `:11`), LRUD area paths (`GetPlanAreaPolygon` `:137`, profile variants `:160-185`) |
| `cSurveyPC/cLayer.vb` | `cLayer` | Per-layer item loop with clipping, translation and viewport culling (`Paint`, `cLayer.vb:422-505`) |
| `cSurveyPC/cLayers.vb` | `cLayers.LayerTypeEnum` | Fixed layer order: Base=0, Soil=1, WaterAndFloorMorphologies=2, RocksAndConcretion=3, CeilingMorphologies=4, Borders=5, Signs=6 (`cLayers.vb:34-42`) |
| `cSurveyPC/cOptions.vb` | `cOptions`, `cOptionsCenterline` | All draw switches; Design/Preview/Viewer mode; owns `DrawingObjects`, `HighlightsOptions`, `TranslationsOptions`, `SurfaceOptions` (`cOptions.vb:168-`) |
| `cSurveyPC/cOptionsDrawingObjects.vb` | `cOptionsDrawingObjects` | The pen/brush/font kit for the plot (`Pen`, `SelectedPen`, `TranslationPen`, `LRUDPen/Brush`, `SplayPen`, `PointBrush`, `InfoFont`, …, `:127-373`); sizes rebound in world units from `DesignProperties` values (`Rebind` `:379-450`; the internal zoom factor is hardcoded to 1, `:381`) |
| `cSurveyPC/cProperties.cHighlightsDetails.vb` | `cHighlightsDetails` | Survey-level highlight definitions incl. system defaults (`_ring`, `_entrance`, `_exploration`, `_gpsdefaultfix`, `_gpsmanualfix`, `_shotwithnote`, `_stationwithnote`, `_stationbyalt`, `_shotbyalt`; `:10-39`); persisted as `<hlsds><hlsd id= n= colors= sz= op= at= cnd= sys=>` (`:80-89`) |
| `cSurveyPC/cProperties.cHighlightsDetail.vb` | `cHighlightsDetail`, `cShotHighlightDetails`, `cStationHighlightDetails`, `cHighlightsDetailMeters` | One highlight rule: color(s)/size/opacity + `ApplyTo` (Stations/Shots) + script `Condition`; script compiled lazily to `GetHighlight(Details)` (`:295-324`); `Details.CustomOptions` lets scripts override element drawing (`:16-23`, `:62-69`) |
| `cSurveyPC/cOptions.cHighlightsOptions.vb` | `cHighlightsOptions` | Per-options-profile list of *enabled* highlight IDs, saved as `<hlsoptions v="id|id|…">` (`:122-128`) |
| `cSurveyPC/frmMain2.vb` | `frmMain2` | Editor consumer: paint event (`:4031`), `pSurveyDraw` (`:9248`), zoom bookkeeping (`pMapZoom` `:306`), quality enum (`:169-173`) |
| `cSurveyPC/frmPreview.vb` | `frmPreview` | Print/raster-export consumer: builds page transform then calls `Survey.Plan/Profile.Paint` (`:1052-1086` image, `:1178-1210` printer page) |
| `cSurveyPC/cViewerProfile.vb` / `cPreviewProfile.vb` | `cViewerProfile(s)`, `cPreviewProfile(s)` | Named saved option-sets for viewer / print preview (two system entries per design type, `cViewerProfile.vb:30-31`) |

## Key flows

### 1. Editor screen paint (plan or profile)

1. `cSurveyPC/frmMain2.vb:4031` — `picMap_Paint` → `pSurveyDraw(e.Graphics)`.
2. `cSurveyPC/frmMain2.vb:9256-9272` — GDI quality set from `iDesignQuality` (`Base`=HighSpeed/no AA, `MediumQuality`=AA, `HighQuality`=HQ bicubic).
3. `cSurveyPC/frmMain2.vb:9278-9279` — world→screen transform: `Graphics.ScaleTransform(sPaintZoom, sPaintZoom, Append)` then `Graphics.TranslateTransform(oPaintTranslation.X, .Y, Append)`. `sPaintZoom` maps meters→pixels; `oCurrentOptions.CurrentScale` (1:N map scale) is derived from it as `DPI/(zoom*0.0254)` (`frmMain2.vb:329-334`).
4. `cSurveyPC/frmMain2.vb:9307` — `oCurrentDesign.Paint(Graphics, oCurrentOptions, cDrawOptions.Empty, oDesignTools)` (`oDesignTools` is the `cIEditDesignSelection`: current layer/item/cave/branch/segment/trigpoint + `Cancel` flag).
5. `cSurveyPC/cDesign.vb:994-1043` — (plan + georeferenced only) surface underlays: elevation/orthophoto/WMS drawn with `SmoothingMode.None`, rotated by meridian convergence.
6. `cSurveyPC/cDesign.vb:1047-1101` — linked surveys painted recursively, then veiled by a translucent white `FillRectangle` (`:1099`).
7. `cSurveyPC/cDesign.vb:1130-1132` — "original position" cave silhouettes (if translations active and configured under-design).
8. `cSurveyPC/cDesign.vb:1180-1218` — **editor layer loop**: `For Each oLayer In oLayers` in enum order Base→Signs; the current layer paints `Solid` (`:1196`); layers before it paint `Solid|SchematicLayerDraw`, layers after paint `Wireframe`, or are skipped, per `UnselectedLevelDrawingMode` (`:1198-1214`). A translucent wash separates lower layers (`:1192`). No cave/branch clipping in editor mode.
9. `cSurveyPC/cLayer.vb:438-500` — per-layer item loop: visibility filter (`GetIfItemMustBeDrawedByCaveAndBranch` `:439`), translation transform (`:471`), viewport culling (`:486`), clip region (`:494`), `oItem.Paint(...)` (`:495`).
10. `cSurveyPC/cItemFreeHandLine.vb:195-205` — item `Paint` = `Render` into `Caches(PaintOptions)` if `Invalidated` (`:176-193`), then `cDrawCache.Paint` replay (`cDrawCache.vb:374-460`).
11. `cSurveyPC/cDesign.vb:1287-1422` — area/combined fills (cave-colored region fills from Border-layer `InvertedFreeHandArea` items).
12. `cSurveyPC/cDesign.vb:1434-1436` — **centerline**: `Plot.Paint(Graphics, PaintOptions, Selection)` if `DrawPlot`/`DrawSpecialPoints`/translation lines/surface profile enabled.
13. `cSurveyPC/frmMain2.vb:9290-9316` — selection chrome on top: `pSurveyDrawTools` → `modPaint.PaintSelection`/`PaintSelectionTools` (grab handles, edit points), new/last point markers.
14. `cSurveyPC/frmMain2.vb:9320-9337` — `SmoothingMode.None`, then axis (`MapDrawAxis`), metric grid (`MapDrawMetricGrid`, mode 1=global, 2=segment-anchored), rulers.
15. `cSurveyPC/frmMain2.vb:9340-9364` — `Graphics.ResetTransform()`; multiselect rubber-band drawn in *screen* space.

### 2. Centerline plot render (plan; profile is symmetric)

1. `cSurveyPC/cPlotPlan.vb:634-639` — `Paint` forces `HighlightCurrentCave=False` outside the editor, then calls `Render`.
2. `cSurveyPC/cPlotPlan.vb:260-262` — abort if no origin station (`oSurvey.Segments.GetOrigin`) — *nothing* is plotted without an origin.
3. `cSurveyPC/cPlotPlan.vb:277-282` — ring highlight defaults read from `HighlightsDetails(RingKey)`.
4. `cSurveyPC/cPlotPlan.vb:284-285` — **segment loop** over `GetAllVisibleSegments(PaintOptions)` (filters splay/equate/self-defined/hidden/surface/duplicate segments and applies cave-visibility profiles, `cPlot.vb:508-571`).
5. `cSurveyPC/cPlotPlan.vb:288-289` — per-segment cache lookup `pGetOrCreateSegmentFromCache(oSegment, PaintOptions)` (`:218-226`); body is skipped entirely unless `.Invalidated`.
6. Inside one segment's cache build, in order (z-order bottom→top): splays (`:312-349`, via `modPaint.PaintStationSplays` — cross/ray styles, in-range vs out-of-range coloring); LRUD area line/polygon (`:352-414`); **highlights under the shot line** — ring (`:423-429`) and scripted shot highlights (`:430-441` calling `modRender.RenderHighlightShot`); the shot line itself (`:470-479`, pen color from cave color / segment color / `CustomDrawOptions` override at `:462-468`); optional per-shot info text (`:483-490`); `.Rendered()` seals the cache (`:493`).
7. `cSurveyPC/cPlotPlan.vb:498-523` — station positions collected into `cTranslatedTrigPoints` (equate-aware, translation-aware).
8. `cSurveyPC/cPlotPlan.vb:532-603` — **station loop**: per-trigpoint cache (`:546`); translation lines (`:550` → `cPlot.vb:410-447`, with H/V interval dedup so overlapping lines draw once, `cPlot.vb:323-408`); entrance arrow (`:557`); scripted station highlights (`:560-575` → `modRender.RenderHighlightStation`); station symbol (`:578-585` → `modRender.RenderTrigPoint`, symbol shape from trigpoint or `PlotPointSymbol` design property, honoring `cDrawCacheTrigpointCustomOptions` overrides `modRender.vb:90-111`); station name label (`:586-590`, capped at 5 labels per identical point `:607-614`).
9. `cSurveyPC/cPlotPlan.vb:640-645` — `Paint` replays every segment cache then every trigpoint cache via `cDrawCache.Paint`.

### 3. Cache replay & wireframe fallback (`cDrawCache.Paint`)

1. `cSurveyPC/cDrawCache.vb:377-405` — wireframe/schematic mode: draws only `IsWireframeOutlined` items; if the item count exceeds `modMain.GetMaxDrawItemCount` (`modMain.vb:49`) it draws just the bounding rectangle (`:380-383`); each `DrawPath` is wrapped in try/catch because GDI+ throws OutOfMemory on sub-pixel wireframe paths (`:387-402`).
2. `cSurveyPC/cDrawCache.vb:407-452` — solid mode: sequential replay honoring `SetClip` (push `Graphics.Save`, intersect clip `:411-430`), `Filler`/`Border`/`Text` (`FillPath`+`DrawPath` `:431-444`), `ResetClip` (restore `:446-449`).
3. Errors are logged through `PaintOptions.Survey.RaiseOnLogEvent` and return `False` → item sets `HavePaintProblem` (`cItemFreeHandLine.vb:199`).

### 4. Print / raster export (same pipeline, different transform)

1. `cSurveyPC/frmPreview.vb:1004-1050` — compute `sPaintZoom` for the page: auto-fit (`design bounds vs page bounds`) or fixed map scale via `modPaint.GetZoomFactor(oGr, factor)`; store `oCurrentOptions.CurrentScale`.
2. `cSurveyPC/frmPreview.vb:1052-1056` — build `Matrix` = Scale(zoom) + Translate(center-on-page), assign to `Graphics.Transform` (printer page graphics at `:1178-1182`).
3. `cSurveyPC/frmPreview.vb:1059` / `:1075` (image) and `:1185` / `:1201` (printer) — `oSurvey.Plan/Profile.Paint(oGr, cOptionsPreview, cDrawOptions.Empty, oSelection)` — identical entry point as the editor, but `IsPreview` routes `cDesign.Paint` into the cave-by-cave clipped branch (`cDesign.vb:1220-1283`) with progress events (`:1269`).
4. `cSurveyPC/frmPreview.vb:1061-1073` — `ResetTransform`, then page-space gadgets: `Plot.Compass/Scale/InfoBox.Rebind(...)` + `.Paint(...)` (gadget classes `cDesignCompass`/`cDesignScale`/`cDesignInfoBox` owned by `cPlot`, `cPlot.vb:236-301`).
5. Vector path: `cDesignPlan.ToSvg` (`cDesignPlan.vb:444-500`) → layers `ToSvgItem` (`:375`) + `oPlot.ToSvgItem` (`:476` → `cPlotPlan.vb:616-626` which serializes the same segment/trigpoint caches). In the editor, the "print/export area" page rectangle overlay + schematic preview is `modPaint.MapDrawPrintOrExportArea` (`modPaint.vb:3546-3686`), which reuses `Plan.Paint` with `cDrawOptions.Schematic` (`:3616`). Full export details belong to the exports doc (see Related docs).

## How to modify safely

- **Never bypass the render/paint split.** Geometry goes into `cDrawCache` inside `Render` (guarded by `.Invalidated` … `.Rendered()`); `Paint` must stay side-effect-free replay. Drawing directly on `Graphics` inside a render body breaks SVG export, which only sees the caches.
- **Cache keying**: `cDrawCaches` is keyed by the *options object reference* (`cDrawCaches.vb:52-62`). Creating a fresh `cOptionsCenterline` per frame would leak caches and defeat caching entirely — reuse one options instance per consumer.
- **Invalidation contract**: after any change to plot inputs you must call `cPlot.Redraw(...)` (or rely on `OnCalculateComplete`, `cSurvey.vb:1963-1966`); after item edits, `cDesign.Redraw`/item `Caches.Invalidate`. Forgetting this yields stale drawings that only fix themselves after a recalculation.
- **Pens/brushes in `cOptionsDrawingObjects` are shared and mutated** during rendering (e.g. `oDrawingObject.Pen.Color = oColor`, `cPlotPlan.vb:475`); `cDrawCacheItem.SetPen` clones them (`cDrawCache.vb:957-965`). If you add a new pen use, set color *before* `SetPen` and don't hold references.
- **Layer order and the enum values are load-bearing** (`cLayers.vb:34-42`): editor logic compares `oLayer.Type > Base` and "before/after current layer" (`cDesign.vb:1185-1214`). Don't reorder.
- **Everything is in world meters.** New glyph sizes must be derived from `DesignProperties` values like `cOptionsDrawingObjects.Rebind` does (`cOptionsDrawingObjects.vb:379-450` — e.g. pen width = `BaseLineWidthScaleFactor` (`:395`) × `PlotPenWidth`-style values, see `oSurfaceProfilePen` at `:435`), or they will be unreadable at other map scales.
- **Respect `Selection.Cancel`** in any long loop you add inside `cDesign.Paint` — it is the only way the UI aborts a slow repaint (checked at `cDesign.vb:1036,1045,1104,1216,…`).
- **Thread-safety**: cache item lists are guarded with `SyncLock oItems` (`cDrawCache.vb:135,305,320,343,409`) because invalidation runs on `Parallel.ForEach` (`cPlotPlan.vb:244-251`); keep that locking if you touch `cDrawCache` internals.

## Gotchas

- **No origin ⇒ empty plot.** `cPlotPlan.Render` exits if `oSurvey.Segments.GetOrigin` is `Nothing` (`cPlotPlan.vb:260-262`). A survey whose origin station is missing renders drawings but no centerline — a classic "my centerline disappeared" symptom.
- `cDrawCaches.Invalidate` **deletes** the per-options entry rather than marking it dirty (`cDrawCaches.vb:64-73`), while `cDrawCache.Invalidate` marks-and-clears (`cDrawCache.vb:273-279`). Both paths exist; a fresh `cDrawCache` starts `bInvalidaded = True` (`cDrawCache.vb:164`) so it will be rebuilt on next `Render`.
- The GDI+ **OutOfMemoryException on tiny wireframe paths** is expected and swallowed (`cDrawCache.vb:387-402`) — don't "fix" the empty catch without reading the comment.
- `Graphics.PageUnit`/DPI sniffing in `GetZoomFactor` (`modPaint.vb:942-956`): a 96-DPI graphics is assumed to be screen/bitmap, anything else printer. Headless rendering with a non-96-DPI bitmap will compute wrong map scales.
- `cOptionsCenterline` state is **mutated during paint** (`HighlightCurrentCave`, `HighlightMode`, `DesignAffinity` set and restored inside `cDesign.Paint`, e.g. `cDesign.vb:1250-1259`, and `cPlotPlan.Paint` `cPlotPlan.vb:635-638`). Painting the same options object from two threads concurrently is unsafe.
- Highlight **scripts execute user code** at render time (`cHighlightsDetail.GetScript().Eval("GetHighlight", …)`, `cPlotPlan.vb:435`, `:567`; compiled per detail, `cProperties.cHighlightsDetail.vb:318-324`). Slow or throwing conditions degrade every repaint; system defaults are short VB scripts — mostly one-line conditions, but the two by-altitude ones are full multi-line `GetHighlight` functions (`cProperties.cHighlightsDetails.vb:31-39`).
- **Commit `4adb49c` ("rewritten code for plot draw")** changed z-order and extensibility: shot highlights now render *under* the shot line (previously over, and un-translated — a translation bug), and highlight scripts gained `Details.CustomOptions` to override segment color and station symbol/size/colors (`cDrawCacheSegmentCustomOptions`/`cDrawCacheTrigpointCustomOptions`, consumed at `cPlotPlan.vb:462-468` and `modRender.vb:90-111`). If a highlight "stopped drawing on top", that's this commit's intent, not a regression. (Two-color gradients in `RenderHighlightShot` (`modRender.vb:39`) predate this commit — they're in the initial import — and the translation-line interval dedup (`cPlot.vb:310-408`) landed later, in commit `e29aea1`.)
- The per-segment/per-trigpoint cache dictionaries (`oSegmentsCaches`/`oTrigpointsCaches`, `cPlotPlan.vb:205-206`) never evict removed segments until a full `Redraw()`; deleted-shot ghosts point here.
- Station labels drawn at the exact same point are capped at 5 (`pCheckLabelInSamePosition`, `cPlotPlan.vb:607-614`) — heavily equated stations silently stop labeling.
- SVG plot export serializes whatever is *currently* in the caches (`cPlotPlan.ToSvgItem`, `cPlotPlan.vb:616-626`) — callers must run `Render`/`Paint` with the same options object first or the plot group comes out empty. (`cDesignPlan.ToSvg` relies on the caches having been populated by the preceding on-screen/preview paint — inferred, no explicit `Render` call in `ToSvg`.)

## Related docs

- [topodroid-import.md](topodroid/topodroid-import.md) — how TopoDroid data becomes segments/splays that this pipeline draws.
- [calculation-engine.md](calculation-engine.md) — computes `Segment.Data.Plan/Profile` projections (`FromPoint`/`ToPoint`/side points) consumed here; its `OnCalculateComplete` triggers plot cache invalidation.
- [data-model-and-file-format.md](data-model-and-file-format.md) — where designs, items, `<hlsds>` highlight definitions and options live inside `_data.xml`.
- [exports-and-printing.md](exports-and-printing.md) — SVG/image/Therion export details; this doc only covers how the paint pipeline is re-entered for print/export.
