# 2D Drawing / Design Engine (the "sketch" model)

## Purpose

This subsystem is the vector cave-map model: the **Plan** and **Profile** drawings that users draw over the computed centerline, made of layered items (walls, floor fills, rocks, signs, texts, cross-sections, raster sketches). It covers how geometry is stored (points/sequences in survey meters), how every drawn point is **bound to a survey shot** so the drawing morphs ("warps") when new data is imported or a loop closes, how items serialize into `_data.xml`, and which code paths create items programmatically (the basis for auto-sketch generation from splays).

> Editing warning: `cSurveyPC/Design/` and `cSurveyPC/Design2D/` are **stale 2015 copies that are NOT compiled** (no `<Compile Include="Design2D\…">` entries in cSurveyPC/cSurveyPC.vbproj; the live entries are root-level, e.g. cSurveyPC/cSurveyPC.vbproj:1461,1465,1493). All drawing-engine classes live in root-level `cSurveyPC/*.vb` files. Always edit those.

## Domain concepts

- **Design** — one drawing surface. A survey owns exactly two 2D designs: `cSurvey.Plan` (`cDesignPlan`) and `cSurvey.Profile` (`cDesignProfile`), created at load (cSurveyPC/cSurvey.vb:673-674, 1387-1398) plus a 3D design (`cDesign3D`, out of scope). There is no user-defined design list — `cDesigns.vb` is dead code (empty class, cSurveyPC/cDesigns.vb:6-10).
- **Layer** — each design has exactly **7 fixed semantic layers** in a fixed z-order (see below). Layers are not user-creatable.
- **Item** (`cItem` subclass) — one drawn object (a wall line, an area fill, a symbol...). Items carry a `Type` (geometry/behavior class) and a `Category` (semantic: CaveBorder, Rock, Soil, WaterArea, Sign...; cSurveyPC/cIItem.vb:5-29), a `Cave`/`Branch` attribution, a `cPen` and/or `cBrush`, and a `cPoints` collection.
- **Point** (`cPoint`) — one vertex: absolute `PointF` in **survey meters** plus a reference to the survey shot it is bound to (`BindedSegment As cISegment`, cSurveyPC/cPoint.vb:666-674).
- **Sequence** — a run of points inside one item starting at a point with `BeginSequence=True` (`cSequence`, cSurveyPC/cSequence.vb:4). One item = one or more sequences (multi-part lines/areas). Each sequence can override the item's pen and line type (cSurveyPC/cSequence.vb:211-227).
- **Segment vs segment** — beware the overloaded word: `cSurvey.cSegment`/`cISegment` (cSurveyPC/cISegment.vb:2) is a **survey shot** (From/To stations, distance/bearing/inclination, splay flag). Drawing geometry never stores its own "path segments" as objects — a drawn path is just the point list rendered as lines/splines/beziers. `cItemSegment.vb` is a special *item* type (`cItemTypeEnum.Segment = 98`) used to render a centerline shot as a design object, and `cSegmentCollection` (cSurveyPC/cSegmentCollection.vb:14) is a collection of survey shots.
- **Binding / warping** — every point remembers the nearest shot at draw time. After recalculation, for each shot whose projected position changed, all points bound to it are transformed by the old-line→new-line affine map (`cPlanWarpingFactor`/`cProfileWarpingFactor`). This is what makes the hand drawing follow the centerline.
- **Coordinate space** — design coordinates are the **projected station coordinates in meters**: Plan = `To2DPoint(FromTop)` = (X, Y) with X=east, **Y=−north (grows screen-down)**; Profile = `To2DPoint(Perpendicular)` = (D, Z) with D = extended-elevation abscissa and Z=−up (cSurveyPC/Calculate/cCalculate.cTrigpointPoint.vb:125-133; see [calculation-engine.md](calculation-engine.md) for the convention). No per-station-relative storage: coordinates are absolute in this space, and binding+warping is what keeps them attached to stations.
- **PointsJoin** — a named group of points (possibly across items) welded together: moving one moves all (`cPointsJoin.CommitChange`, cSurveyPC/cPoint.vb:283-289). Serialized positionally (layer,itemIndex,pointIndex).
- **DesignAffinity** — `Design` (real cave drawing, warps) vs `Extra` (decoration; excluded from plan warping) (cSurveyPC/cItem.vb:87-91, plan warp filter at cSurveyPC/cDesignPlan.vb:214; the profile warp filter keys on `BindDesignType=MainDesign` instead, cSurveyPC/cDesignProfile.vb:218).
- **BindDesignType** — `MainDesign` (bind to centerline shots) vs `CrossSections` (bind to a cross-section's virtual segment) (cSurveyPC/cItem.vb:52-55).

## Architecture

### Ownership chain

```
cSurvey
 ├─ .Plan    : cDesignPlan    ─┐
 ├─ .Profile : cDesignProfile ─┴─ Inherits cDesign          (cSurveyPC/cDesign.vb:10)
 │     ├─ .Layers : cLayers   — fixed list of 7 cLayer      (cSurveyPC/cLayers.vb:214-225)
 │     │     └─ cLayer.Items : cItems (BindingList(Of cItem)) (cSurveyPC/cItems.vb:10)
 │     │           └─ cItem (abstract) → 20+ concrete cItem* classes
 │     │                 └─ .Points : cPoints → cPoint { PointF, BindedSegment, BeginSequence, LineType, Pen, SegmentLocked }
 │     ├─ .PointsJoins : cPointsJoins                        (cSurveyPC/cDesign.vb:519-523)
 │     └─ .Plot : cPlotPlan / cPlotProfile — centerline/splay rendering + WARPING TRIGGER (see rendering doc)
 ├─ .CrossSections : cDesignCrossSections — registry of cDesignCrossSection (each Implements cISegment!)
 └─ .Sketches : cDesignSketches — registry of raster cItemSketch items    (cSurveyPC/cDesignSketches.vb)
```

### The 7 fixed layers (z-order = paint order = enum order)

`cLayers.LayerTypeEnum` (cSurveyPC/cLayers.vb:34-42); constructed bottom-to-top at cSurveyPC/cLayers.vb:218-224, painted in enum order (cSurveyPC/cDesign.vb:1186, 1272):

| # | Enum | Class | Typical content (factory methods) |
|---|------|-------|-----------------------------------|
| 0 | `Base` | `cLayerBase` (cSurveyPC/cLayerBase.vb) | tracing images (`cItemImage`), raster sketches (`cItemSketch`), 3D chunks |
| 1 | `Soil` | `cLayerSoil` (cSurveyPC/cLayerSoil.vb:16-62) | floor fills: `CreateSoil`, `CreateSandSoil`, `CreatePebblesSoil`, `CreateSmallDebritsSoil`, `CreateBigDebritsSoil`, `CreateFlowSoil` — all `cItemFreeHandArea` |
| 2 | `WaterAndFloorMorphologies` | `cLayerWaterAndFloorMorphologies` (cSurveyPC/cLayerWaterAndFloorMorphologies.vb) | water areas, floor curves/cliffs/gradients (`cItemFreeHandLine`) |
| 3 | `RocksAndConcretion` | `cLayerRocks` (cSurveyPC/cLayerRocks.vb) | rock/concretion cliparts (`cItemClipart`) |
| 4 | `CeilingMorphologies` | `cLayerCeilingMorphologies` (cSurveyPC/cLayerCeilingMorphologies.vb) | ceiling lines |
| 5 | `Borders` | `cLayerBorders` (cSurveyPC/cLayerBorders.vb:29-76) | **cave walls**: `CreateCaveBorder`/`CreatePresumedCaveBorder`/`CreateTooNarrowCaveBorder`/`CreateUnderlyingCaveBorder`/`CreateExternalBorder` → `cItemInvertedFreeHandArea`; plain `CreateBorder` → `cItemFreeHandLine` |
| 6 | `Signs` | `cLayerSigns` (cSurveyPC/cLayerSigns.vb) | point symbols (`cItemSign`), texts (`cItemText`), quotas (`cItemQuota`), cross-sections |

**Clipping semantics:** the Borders layer is special — its `cItemInvertedFreeHandArea` items (Category=CaveBorder) define the cave outline polygons. `cDesign.GetCaveClippingPaths/Regions` (cSurveyPC/cDesign.vb:324-485) unions all `MergeMode=Add` border areas and excludes `MergeMode=Subtract` ones (pillars/holes; enum at cSurveyPC/cIItemMergeableArea.vb:3-6, `mergemode` XML attribute at cSurveyPC/cItemInvertedFreeHandArea.vb:270), keyed per cave/branch. During preview/export paint, every item on layers **below** Borders is clipped to stay *inside* the cave outline of its own cave/branch, while layers above Borders (Signs) and the borders themselves are not clipped; per-item override via `cItem.ClippingType` (Default/None/InsideBorder/OutsideBorder, cSurveyPC/cItem.vb:15-20). The same rule drives SVG export masks (cSurveyPC/cLayer.vb:41-66; exception: Soil areas on the Profile design get the *inverted* mask, cSurveyPC/cLayer.vb:47-49). `cLayerBorders.Paint` force-renders borders before anything else so clip paths are always fresh (cSurveyPC/cLayerBorders.vb:11-19).

### Item taxonomy

`cIItem.cItemTypeEnum` (cSurveyPC/cIItem.vb:31-61). All items serialize as an `<item>` element (never a type-specific element name); the `type` attribute (decimal enum value) selects the class at load via the factory `cLayer.CreateItem(Survey, Design, Layer, File, XmlElement)` (cSurveyPC/cLayer.vb:215-267). Base attributes written by `cItem.SaveTo` (cSurveyPC/cItem.vb:548-577): `layer, name, cave, branch, crosssection, binddesigntype, type, category, hiddenindesign, hiddeninpreview, locked, clippingtype, da (affinity), transparency`, children `<pen>`, `<brush>`, `<points>`, `<datarow>`.

| type | Class (root-level file) | What it is on the map | Extra XML |
|------|------------------------|----------------------|-----------|
| 0 `Items` | `cItemItems` | transient multi-selection wrapper (exploded on load, cSurveyPC/cLayer.vb:278-281) | — |
| 1 `FreeHandLine` | `cItemFreeHandLine` (cSurveyPC/cItemFreeHandLine.vb:7) | open polyline/spline/bezier (floor curves, ceiling lines, generic borders); pen only, no brush | `linetype` |
| 3 `FreeHandArea` | `cItemFreeHandArea` (cSurveyPC/cItemFreeHandArea.vb) | closed filled area (soil, water); pen+brush | `linetype` |
| 4 `InvertedFreeHandArea` | `cItemInvertedFreeHandArea` (cSurveyPC/cItemInvertedFreeHandArea.vb:208-270) | **cave wall/outline area** — "inverted" because it fills the outside during clipping; the add/subtract source of the cave clip region | `linetype`, `mergemode` |
| 5 `Clipart` | `cItemClipart` (cSurveyPC/cItemClipart.vb) | vector clipart shape (rocks, concretions) | clipart data ref |
| 6 `Sign` | `cItemSign` (cSurveyPC/cItemSign.vb) | single-point symbol (stalactite, entrance arrow...); one point, `signsize`, `angle` | `data` (clipart id/hash), `dataformat`, `signsize`, `angle` |
| 7 `Image` | `cItemImage` (cSurveyPC/cItemImage.vb) | raster image to trace over | image payload |
| 8 `Text` | `cItemText` (cSurveyPC/cItemText.vb) | free text label | text, font |
| 9 `CrossSection` | `cItemCrossSection` (cSurveyPC/cItemCrossSection.vb) | a cross-section outline drawn at a station; owns/links a `cDesignCrossSection` (constructor takes a `cSegment`, cSurveyPC/cLayer.vb:289-299) | crosssection refs |
| 10 `Quota` | `cItemQuota` (cSurveyPC/cItemQuota.vb) | elevation/measure annotation (also vertical/horizontal scale variants, cSurveyPC/cIItemQuota.vb:26-28) | quota props |
| 11 `Sketch` | `cItemSketch` (cSurveyPC/cItemSketch.vb:405-420, 526-601) | georeferenced raster sketch (e.g. TopoDroid/therion XVI) with per-station pixel anchors (`<stations>`); auto-rescaled every calculate | `imageid`, `designimageid`, `image`, `designimage` (paths in .csz, base64 in .csx), `morphingdisabled`, `manualadjust`, `<stations>` |
| 12 `Attachment` | `cItemAttachment` (cSurveyPC/cItemAttachment.vb) | file attachment marker | attachment ref |
| 13/14/15/16 | `cItemLegend`/`cItemScale`/`cItemCompass`/`cItemInformationBoxText` | print furniture (legend, scale bar, north arrow, info box) | — |
| 29 `CrossSectionMarker` | `cItemPlanCrossSectionMarker` / `cItemProfileCrossSectionMarker` (chosen by design type, cSurveyPC/cLayer.vb:236-241) | the "A—A′" section cut line on plan/profile | marker props |
| 95 `Chunk3D` | `cItemChunk3D` | 3D chunk reference drawn in 2D | — |
| 96/97/98 | `cItemMarker`/`cItemTrigpoint`/`cItemSegment` | internal renderers for markers/stations/shots | — |
| 99 `Generic` | `cItemGeneric` (cSurveyPC/cItemGeneric.vb) | untyped imported geometry (e.g. from therion .th2); convertible into any real item via `FromGeneric` (cSurveyPC/cItem.vb:355, cSurveyPC/cItemFreeHandLine.vb:295-306) | `linetype` |

Capabilities are declared per class as `MustOverride` booleans on `cItem` — `CanBeWarped`, `CanBeBinded`, `BindMode` (AllPoints/CenterPoint/None/Special), `CanBeClipped`, `HavePen/HaveBrush/HaveLineType`... (cSurveyPC/cItem.vb:337-373). E.g. `cItemFreeHandLine.CanBeWarped=True, BindMode=AllPoints` (cSurveyPC/cItemFreeHandLine.vb:104-108, 140-144); `cItemSketch.BindMode=Special` (cSurveyPC/cItemSketch.vb:428-432) and `CanBeBinded=False` (cSurveyPC/cItemSketch.vb:464-468).

### Geometry model

- An item's shape is only its ordered `cPoints` list, split into sequences at `BeginSequence` points (`GetSequences`, cSurveyPC/cPoints.vb:677).
- How points become a path: `modPaint.SequenceToPath` (cSurveyPC/modPaint.vb:4107-4123) — `LineTypeEnum.Lines` → `AddLines`, `Splines` → `AddCurve` (cardinal spline with default tension), `Beziers` → `PointsToBeziers` where every main point is followed by 2 control points (control points are auto-inserted 0.1 m left/right on add, cSurveyPC/cPoints.vb:82-110; enum at cSurveyPC/cIItemLine.vb:3-8).
- Rendering is cached: `cItem.Render` builds `GraphicsPath`s into a `cDrawCache` (per `cOptions` instance), `cItem.Paint` replays the cache (pattern in cSurveyPC/cItemFreeHandLine.vb:176-205). `Caches.Invalidate()` on any point/pen/brush change (cSurveyPC/cItem.vb:953-971).
- Styling: `cPen` has ~35 semantic pen types (CavePen, PresumedCavePen, CliffUpPen, IcePen, fault pens...; cSurveyPC/cPen.vb:1161-1212); `cBrush` has semantic fills (Water, Sand, Pebbles, Flow, Debrits, SnowOrIce... plus clipart/pattern/texture custom brushes; cSurveyPC/cBrush.vb:2631-2647). Choosing a *type* pen/brush keeps the drawing restyleable survey-wide.

### XML serialization (inside `_data.xml`, root `<csurvey>`)

Verified against `dev/example/Demo Survey/survey_6.csz`:

```xml
<csurvey>
  ...
  <plan>                                    <!-- cDesignPlan.SaveTo, cSurveyPC/cDesignPlan.vb:56-63 -->
    <layers>                                <!-- cLayers.SaveTo, cSurveyPC/cLayers.vb:205-212 -->
      <layer name="Borders" type="5">       <!-- cLayer.SaveTo, cSurveyPC/cLayer.vb:180-189 -->
        <items>
          <item layer="5" cave="Grotta" branch="Ramo 1\Ingresso" type="4" category="1"
                linetype="1" mergemode="0">
            <pen type="1" />
            <points data="1.28 -5.67 BS0571085f-... 1.10 -5.58 S 0.97 -5.45 S ..."/>
          </item>
        </items>
      </layer>
    </layers>
    <pointsjoins>                           <!-- cPointsJoins.SaveTo, cSurveyPC/cPoint.vb:109-119 -->
      <pointsjoin id="..." data="5,0,12 5,1,0 "/>  <!-- layerType,itemIndex,pointIndex -->
    </pointsjoins>
    <plot/>
  </plan>
  <profile> ...same structure... </profile> <!-- cSurveyPC/cDesignProfile.vb:44 -->
  <crosssections/> <sketches/>
</csurvey>
```

**The `points/@data` compact format** (writer cSurveyPC/cPoints.vb:626-667, parser cSurveyPC/cPoints.vb:496-618): space-separated `x y [flagtoken]` triples; the flag token is optional and is a concatenation, in this order: `B` = BeginSequence (may be followed by `P` = a `<pen>` child of `<points>` applies to this sequence, then `T<d>` = per-sequence line type digit), `L` = SegmentLocked, `S<segmentGuid>` = bound to that shot, bare `S` = bound to the **same** shot as the previous bound point. Legacy files instead contain `<point x= y= beginsequence= linetype= segmentlocked= bindedsegment=>` children (cSurveyPC/cPoint.vb:550-594).

### Station binding & warping (the critical mechanism)

1. **Bind at creation/edit.** `cItem.SetCave(cave, branch)` (cSurveyPC/cItem.vb:644-664) → `BindSegments()` (cSurveyPC/cItem.vb:796-841): for each point not `SegmentLocked`, find the nearest shot via `cDesign.GetNearestSegment(cave, branch, crosssection, x, y, bindDesignType)` — plan uses point-to-segment distance against `Segment.Data.Plan.FromPoint/ToPoint` (cSurveyPC/cDesignPlan.vb:71-101), profile against `Segment.Data.Profile.*` (cSurveyPC/cDesignProfile.vb:62-70). Only shots of the item's cave/branch are candidates, and shots flagged `IsUnbindable` are skipped. With `BindDesignType.CrossSections`, all points bind to a single `cDesignCrossSection` (which itself `Implements cISegment`, cSurveyPC/cDesignCrossSection.vb:13-14). An item with `Cave=""` gets fully *unbound* (cSurveyPC/cItem.vb:797-801) — so unattributed items never warp.
2. **Track change.** Each shot's `Data` keeps `olddata` + old projected line alongside the current one; `cPlanProjectedData.SetPoints` backs up the previous From/To points and sets `Changed` (cSurveyPC/Calculate/cCalculate.Plot.cPlanProjectedData.vb:278-302).
3. **Compute the delta.** `Segment.Data.PlanWarpingFactor` lazily builds `cPlanWarpingFactor(GetOldLine, GetLine, oldBearing, newBearing)` (cSurveyPC/Calculate/cCalculate.Plot.cData.vb:322-338): OldLocation/NewLocation (line start), Old/NewAngle, `DeltaSize = newLen/oldLen`, `IsChanged` when any delta ≠ 0 (cSurveyPC/Calculate/cCalculate.Plot.cData.vb:115-146), `IsCritical` when a length collapses to 0 (warp skipped, cSurveyPC/cDesignPlan.vb:208).
4. **Apply.** After every recalculation, `cPlotPlan.Calculate` (cSurveyPC/cPlotPlan.vb:1139-1202) intersects `Segments.GetChangedSegments(Plan, ForWarping:=True)` (cSurveyPC/cSegments.vb:526-543: valid, not splay, not equate, not unbindable, `Data.Plan.Changed` and factor changed) with `GetBindedSegments(Plan)`, optionally shows `frmWarpingDetails` (grid of per-shot deltas; Apply=OK / Cancel-and-pause=Ignore / Abort disables warping, cSurveyPC/frmWarpingDetails.vb:96-109 handled at cSurveyPC/cPlotPlan.vb:1158-1172), then per shot calls `oSurvey.Plan.WarpItems(oSegment)` and `oSegment.Data.Plan.ResetChange()` (cSurveyPC/cPlotPlan.vb:1164-1165). Profile mirrors this (cSurveyPC/cPlotProfile.vb:874), then cross-sections warp their own bound items (cSurveyPC/cPlotPlan.vb:1176-1200, cSurveyPC/cDesignCrossSection.vb:40-146).
5. **The transform.** `cDesignPlan.WarpItemsEx(segment, factor, force)` (cSurveyPC/cDesignPlan.vb:207-261) collects every point of every item where `CanBeWarped And DesignAffinity=Design` whose `BindedSegment Is segment`, then applies one `Matrix`: `Translate(−OldLocation) · Rotate(−OldAngle) · Scale(1, DeltaSize) · Rotate(NewAngle) · Translate(NewLocation)` and `MoveTo`s each point (joined points moved once, cSurveyPC/cDesignPlan.vb:248-257). Profile version scales `(DeltaSize, 1)`, uses inclination-derived angles with opposite rotation signs, and filters on `CanBeWarped And BindDesignType=MainDesign` instead of DesignAffinity (cSurveyPC/cDesignProfile.vb:209-265, filter at :218). So a drawing vertex effectively lives in the rotated/scaled frame of its shot even though it is stored absolute.
6. **Rebinding on merge/import.** `cItem.RebindSegments(oldId→newId dictionary / cISegment pairs)` swaps bindings without moving points (cSurveyPC/cItem.vb:769-794); cSurvey-file import warps imported items from the *source* survey geometry onto the destination by constructing explicit `cPlanWarpingFactor(newSegment, oldSegment)` pairs (cSurveyPC/frmMain.vb:17400-17411).
7. **Raster sketch morphing** is separate: `cItemSketch` keeps station→pixel anchors; after each Therion calculation the plan/profile XVI images are re-scaled/translated so two reference stations coincide with their computed positions, and the item's 2 points (top-left + bottom-right of image bounds) are rewritten (cSurveyPC/Calculate/cCalculate.vb:1789-1875); `MorphingDisabled`/`ManualAdjust` opt out per item (cSurveyPC/cItemSketch.vb:299, 563-568).

Global switches: `Survey.Properties.DesignWarpingMode` (Default/None), `PlanWarpingDisabled`, `ShowWarpingDetails`, `DesignWarpingState` (paused) — all checked at cSurveyPC/cPlotPlan.vb:1141-1171.

### Painting pipeline (short — details in [rendering-and-plot.md](rendering-and-plot.md))

`cDesign.Paint(Graphics, cOptionsCenterline, cDrawOptions, Selection)` (cSurveyPC/cDesign.vb:987-1441): optional surface/orthophoto + linked surveys underlay (plan only) → editor mode: paint layers in order, current layer solid, others wireframe/schematic per `UnselectedLevelDrawingMode` (cSurveyPC/cDesign.vb:1180-1218) → preview/export mode: build cave clipping paths, fill cave background, then per cave/branch × per layer solid paint with clipping regions (cSurveyPC/cDesign.vb:1222-1282) → optional colored-area style (cSurveyPC/cDesign.vb:1293-1421) → centerline plot on top (cSurveyPC/cDesign.vb:1434-1436). Per-layer painting filters items by visibility flags, cave/branch highlight and cave-visibility profiles, applies per-item translation (exploded views) and clip region, then `cItem.Paint` (cSurveyPC/cLayer.vb:422-505). SVG export mirrors this via `ToSvgItem` on design/layer/item (cSurveyPC/cDesignPlan.vb:438-500).

## Key classes & files

| File (repo-relative) | Class | Responsibility |
|---|---|---|
| cSurveyPC/cDesign.vb | `cDesign` (MustInherit) | base drawing: layers, points-joins, bounds, clipping paths/regions, Paint, CleanUp, `WarpItems` contract (line 1445), `GetNearestSegment` contract (line 1463) |
| cSurveyPC/cDesignPlan.vb | `cDesignPlan` | plan design: nearest-segment on plan projection, plan warp matrix, saves as `<plan>`, owns `cPlotPlan` |
| cSurveyPC/cDesignProfile.vb | `cDesignProfile` | profile design: same on (D,Z) projection, saves as `<profile>`, owns `cPlotProfile` |
| cSurveyPC/cLayers.vb | `cLayers`, `LayerTypeEnum` | the fixed 7-layer list, typed accessors (`BordersLayer`…), `<layers>` (de)serialization |
| cSurveyPC/cLayer.vb | `cLayer` | item collection host, all `CreateItem` factories (XML at :215, typed at :289-381), visibility filtering, per-layer Paint/HitTest, SVG clipping mask assignment |
| cSurveyPC/cLayerBorders.vb (+Soil/Signs/Rocks/Water/Ceiling/Base) | `cLayerBorders` etc. | semantic factory methods per layer (`CreateCaveBorder` :36, `CreateSoil`…), pen/brush type presets |
| cSurveyPC/cItems.vb | `cItems` | `BindingList` of items; `Add` sets parent layer (:65-68), `Remove` marks deleted + unjoins points (:115-123) |
| cSurveyPC/cItem.vb | `cItem` (MustInherit) | identity (type/category/cave/branch), pen/brush/points, capability flags, `SetCave`/`BindSegments`/`RebindSegments`/`UnbindSegments` (:644-841), Move/Resize/Rotate/Combine, `<item>` (de)serialization (:484-577) |
| cSurveyPC/cIItem.vb | `cIItem` + enums | the live `cItemTypeEnum`/`cItemCategoryEnum` (namespace `cSurvey.Design.Items`) |
| cSurveyPC/cPoints.vb | `cPoints` | point list: `StartSequence` (:76), `AddFromPaintPoint` (:82,97), sequence extraction (:677), compact `data` writer (:626)/parser (:496), CleanUp/ReducePoints support |
| cSurveyPC/cPoint.vb | `cPoint`, `cPointsJoin(s)` | vertex + `BindSegment`/`BindedSegment` (:638-674), `SegmentLocked`, joins (`CommitChange` :283) |
| cSurveyPC/cSequence.vb | `cSequence` | one polyline run: per-sequence pen/linetype (:211-227), ToLine/ToSpline/ToBezier converters, Reverse |
| cSurveyPC/cItemFreeHandLine.vb / cItemFreeHandArea.vb / cItemInvertedFreeHandArea.vb | the three freehand types | line/area/cave-wall geometry, `linetype`, Render via `SequenceToPath` (line item :176-193) |
| cSurveyPC/cItemSketch.vb | `cItemSketch` (+`cStations`) | raster sketch with station anchors; image stored in .csz under `_data\design\<guid>.png` (:583-590) |
| cSurveyPC/cItemCrossSection.vb, cSurveyPC/cDesignCrossSection.vb, cSurveyPC/cDesignCrossSections.vb | cross-section item + virtual segment | cross-section drawing bound to a station; `cDesignCrossSection Implements cISegment` so its items warp with it (:40-146) |
| cSurveyPC/cPen.vb / cPens.vb, cSurveyPC/cBrush.vb / cBrushes.vb | `cPen`, `cBrush` | semantic style system (`PenTypeEnum` cPen.vb:1161, `BrushTypeEnum` cBrush.vb:2631), render-time transparency events |
| cSurveyPC/cEditPaintObjects.vb (base class in cSurveyPC/cPaintObjects.vb) | `cEditPaintObjects` (Inherits `cPaintObjects`) | shared editor-chrome pens/brushes (selection handles, bezier control points; cSurveyPC/cEditPaintObjects.vb:6) |
| cSurveyPC/Calculate/cCalculate.Plot.cData.vb | `cPlanWarpingFactor`, `cProfileWarpingFactor`, `cIWarpingFactor` | the old→new shot transform description (:38-338) |
| cSurveyPC/cPlotPlan.vb / cPlotProfile.vb | `cPlotPlan/Profile` | end-of-Calculate warping trigger loops (:1139-1202 / :846-914) |
| cSurveyPC/modSegmentsTools.vb | module | **auto-generation from splays** (below), binded-segment queries used by warping (:152-193) |
| cSurveyPC/modDesign.vb | module | item visibility predicates used everywhere (`GetIfItemMustBeDrawedByHiddenFlag` :12, `…ByCaveAndBranch` :55) |
| cSurveyPC/modDesignLRUD.vb | module | *reverse* direction: derive LRUD/side data from drawn cave borders (`cLRUDFromDesignCache2`, cSurveyPC/modDesignLRUD.vb:353; ray-intersection `Intersect` at :404) |
| cSurveyPC/designtools.xml | data | drawing-tool palette (below) |
| cSurveyPC/frmWarpingDetails.vb | `frmWarpingDetails` | pre-warp review dialog (per-shot ΔX/ΔY/Δangle/Δsize grid) |
| cSurveyPC/cBorderFromSplay.vb, cSurveyPC/cAreaFromSequence.vb | UI panels | dropdown option panels only; real logic in modSegmentsTools / modPaint.WidenSequence |

## Key flows

### 1. Programmatic item creation (no UI) — the auto-sketch building block

What the UI does via reflection, automation can do directly:

1. cSurveyPC/frmMain2.vb:6802 — `pSurveyDesignToolsLoad` loads `designtools.xml` from the app dir.
2. cSurveyPC/frmMain2.vb:7116 — clicking a tool invokes `oLayer.GetType.GetMethod(Bag.Method).Invoke(oLayer, {cave, branch, ...})`, i.e. the `method`/`parameters` attributes of the `<tool>` name a public factory on the layer class.
3. cSurveyPC/cLayerBorders.vb:36-41 — e.g. `CreateCaveBorder(cave, branch)` calls the generic `cLayer.CreateItem(cItemTypeEnum.InvertedFreeHandArea, cItemCategoryEnum.CaveBorder)` (cSurveyPC/cLayer.vb:335-351), which constructs the item **and already adds it to `Layer.Items`**, then presets `Pen.Type = CavePen` and calls `SetCave`.
4. cSurveyPC/cPoints.vb:76-110 — add geometry: `item.Points.StartSequence()` once per subpath, then `AddFromPaintPoint(x, y)` per vertex (meters, design space; for Beziers this auto-adds 2 control points per call).
5. cSurveyPC/cItem.vb:644-664 — call `SetCave(cave, branch)` (again) or `BindSegments()` after the points exist, so every point acquires its `BindedSegment` — without this the item will not warp.
6. cSurveyPC/cSurvey.vb:1825-1829 — `Survey.SaveTo` persists `Plan`/`Profile` into `_data.xml` (`<plan>`, `<profile>`).

Minimum viable "wall" item: `DirectCast(Survey.Plan.Layers.BordersLayer, cLayerBorders).CreateCaveBorder(cave, branch)` → `StartSequence` → n × `AddFromPaintPoint` → close by re-adding the first point → `item.LineType = Splines`.

### 2. Auto-generating cave borders from splays (the existing auto-sketch)

Entry: ribbon "create border from splays" panel → `frmMain2.oBorderFromSplay_OnCreate` (cSurveyPC/frmMain2.vb:15918-15936).

- Mode "all splays" (plan only):
  1. cSurveyPC/modSegmentsTools.vb:424 — `CreatePlanBorderFromSplay(Survey, Cave, Branch, LineType, AngularPrecision, UseHull)` (overload per single shot at :627).
  2. cSurveyPC/modSegmentsTools.vb:400-422 — for every valid non-splay/non-surface/non-duplicate shot of the cave/branch, build a per-shot polygon and Clipper-union them all.
  3. cSurveyPC/modSegmentsTools.vb:316-398 — per-shot polygon: around each endpoint station collect its splays' plan endpoints (`Segment.Data.Plan.FromSplays/ToSplays`) into a bearing-sorted dictionary (keeping the farthest point per bearing bucket of `AngularPrecision` degrees, :299-314), add the opposite station and neighbour stations, optionally convex-hull (`BorderHullEnum`; concave hull variant at :684), plus a minimum octagon around each station; union From-side + To-side via Clipper.
  4. cSurveyPC/modSegmentsTools.vb:427-436 — create ONE `cItemInvertedFreeHandArea` via `CreateCaveBorder(Cave, Branch)`, set `LineType`, then per result polygon `Points.StartSequence()` + `AddFromPaintPoint` each vertex + repeat first vertex to close.
  5. Binding happens inside `CreateCaveBorder`→`SetCave` (points added later are bound on the next `BindSegments`/SetCave; the UI triggers rebind via cave selection).
- Mode "cut and LRUD": `CreateBorder3DOutline(Survey, Cave, Branch, PlanOrProfile)` (cSurveyPC/modSegmentsTools.vb:443-449, impl :451+) — builds the 3D passage model (cave_model/DNetCM via `cHolosViewer.Get3DPoints`), slices its outline, and creates border items; this is the **only** profile-border generator: `CreateProfileBorderFromSplay` is an **empty stub** (cSurveyPC/modSegmentsTools.vb:641-647).
- Related generator: `modPaint.WidenSequence(item, point, width)` converts a drawn centerline-ish line into an area outline (`cAreaFromSequence` panel) (cSurveyPC/modPaint.vb:4133-4154).

### 3. Warping after recalculation (drawing follows the centerline)

1. cSurveyPC/Calculate/cCalculate.vb (Therion run) → new station coordinates; `Segment.Data.Plan.SetPoints(from, to, newFrom, newTo)` backs up old line and flags `Changed` (cSurveyPC/Calculate/cCalculate.Plot.cPlanProjectedData.vb:278-302).
2. cSurveyPC/cPlotPlan.vb:1141 — `Calculate(..., PerformWarping:=True)` checks `DesignWarpingMode=Default` and not `PlanWarpingDisabled`.
3. cSurveyPC/cPlotPlan.vb:1146-1148 — candidate set = `GetChangedSegments(Plan, True) ∩ GetBindedSegments(Plan)`.
4. cSurveyPC/cPlotPlan.vb:1153-1157 — optional `frmWarpingDetails` review (OK applies, Abort sets `DesignWarpingMode=None`, Ignore pauses).
5. cSurveyPC/cDesignPlan.vb:263-265 — `WarpItems(segment)` → `WarpItemsEx(segment, segment.Data.PlanWarpingFactor, False)`.
6. cSurveyPC/cDesignPlan.vb:210-257 — gather bound points of warpable Design-affinity items → apply old→new matrix → `cPoint.MoveTo` (skips duplicates in the same PointsJoin).
7. cSurveyPC/cPlotPlan.vb:1165 — `segment.Data.Plan.ResetChange()` so the delta is consumed exactly once.
8. cSurveyPC/cPlotPlan.vb:1176-1200 — cross-section virtual segments get repositioned and their bound items warped via `cDesignCrossSection.WarpItems` (cSurveyPC/cDesignCrossSection.vb:138-146).

### 4. Load → draw round-trip

1. cSurveyPC/cSurvey.vb:1387-1398 — `New cDesignPlan(Me, oFile, oXmlRoot.Item("plan"))` / same for `"profile"`.
2. cSurveyPC/cDesign.vb:503-517 — reads `<layers>` and `<pointsjoins>`.
3. cSurveyPC/cLayers.vb:166-203 — instantiates each `<layer>` by `type` attribute, backfills any missing layer so all 7 always exist.
4. cSurveyPC/cLayer.vb:170-178 → cSurveyPC/cLayer.vb:215-267 — each `<item>` dispatched by `type` to the concrete constructor; `cItem` base ctor parses attributes + `<points>` (cSurveyPC/cItem.vb:484-546).
5. cSurveyPC/cPoints.vb:496-618 — points parsed; `bindedsegment` GUIDs resolved lazily against `Survey.GetSegment(id)` on first `BindedSegment` access (cSurveyPC/cPoint.vb:666-674) — so items load even before segments are indexed.
6. Paint: frmMain2 map control → `cDesignPlan.Paint` (cSurveyPC/cDesignPlan.vb:19-21 → cSurveyPC/cDesign.vb:987) → `cLayer.Paint` (cSurveyPC/cLayer.vb:422) → `cItem.Render`/`Paint` with `cDrawCache`.

## How to modify safely

- **Never edit `Design/` or `Design2D/` folders** — changes there compile nowhere. Mirror-edit the root-level file (check the `.vbproj` when in doubt).
- **Preserve the `points/@data` token grammar** (order `B`,`P`,`T<d>`,`L`,`S…`; bare `S` = repeat-previous-segment; invariant decimal formatting via `modNumbers.NumberToString`). Both TopoDroid-exported CSX files and every existing survey depend on it; the parser is hand-rolled and order-sensitive (cSurveyPC/cPoints.vb:529-608).
- **Enum values are file format.** `LayerTypeEnum`, `cItemTypeEnum`, `cItemCategoryEnum`, `PenTypeEnum`, `BrushTypeEnum`, `MergeModeEnum`, `LineTypeEnum` are serialized as integers — never renumber; only append.
- **PointsJoins are positional** — serialized as `layerType,itemIndex,pointIndex` (cSurveyPC/cPoint.vb:158-172). Any code that reorders `Layer.Items` or `Item.Points` silently breaks saved joins.
- **Warp lifecycle**: whoever applies a warp must call `Data.Plan/Profile.ResetChange()` (and the factor caches reset via `ResetWarpingFactor`, cSurveyPC/Calculate/cCalculate.Plot.cData.vb:317). Warping twice double-moves geometry; forgetting `ResetChange` re-warps on the next calculate.
- **Always bind after adding geometry**: an item whose points have `BindedSegment Is Nothing` is invisible to warping and to `GetBindedSegments`; `SetCave("", ...)` actively unbinds (cSurveyPC/cItem.vb:797-801). Respect `SegmentLocked` — `BindSegment` silently no-ops on locked points (cSurveyPC/cPoint.vb:638-643).
- **Items self-delete**: removing the last point removes the item from its layer (`oPoints_OnChanged`, cSurveyPC/cItem.vb:965-971); `cPoints.CleanUp` during `cDesign.CleanUp` deletes empty items too (cSurveyPC/cDesign.vb:648-666). Don't hold references across point clearing.
- **Thread use**: `BindSegments`/`RebindSegments`/cache invalidation run under `Parallel.ForEach` (cSurveyPC/cItem.vb:714, 777, 798; cSurveyPC/cDesign.vb:159) — keep per-point work side-effect-free beyond the point itself.
- **Beziers have structural control points**: each main vertex is followed by two control vertices; deleting/counting points must respect that (guards in `cPoints.Remove`, cSurveyPC/cPoints.vb:228-239).
- The Borders layer's `InvertedFreeHandArea` items feed clipping for the whole design — a malformed/open border makes lower-layer fills disappear in preview while looking fine in the editor (editor paints without cave clipping, cSurveyPC/cDesign.vb:1180-1218).

## Gotchas

- **Two main forms**: `frmMain.vb` (legacy) and `frmMain2.vb` (current) both contain near-identical design-tool code; when tracing UI behavior use frmMain2 (e.g. border-from-splay handler at cSurveyPC/frmMain2.vb:15918 vs cSurveyPC/frmMain.vb:23764).
- `cDesign.SaveTo` writes a `<design>` element (cSurveyPC/cDesign.vb:525-531) but is **always overridden** — real files contain `<plan>`/`<profile>`.
- `cBorderFromSplay`/`cAreaFromSequence` are just WinForms option panels; searching for the algorithm there is a dead end — it's in `modSegmentsTools` / `modPaint.WidenSequence`.
- `CreateProfileBorderFromSplay` is an empty function returning Nothing (cSurveyPC/modSegmentsTools.vb:645-647) — profile walls only come from hand drawing or the 3D-outline path.
- Plan warp scales `(1, DeltaSize)` (cSurveyPC/cDesignPlan.vb:236) while profile scales `(DeltaSize, 1)` (cSurveyPC/cDesignProfile.vb:240) — the scale axis is relative to the rotated shot frame; don't "fix" the apparent inconsistency.
- `cItem.GetBounds` builds a polygon from raw points (cSurveyPC/cItem.vb:375-394) — for splines/beziers the painted curve can exceed these bounds slightly; hit-testing at item level is bounds-only (cSurveyPC/cItem.vb:427-441).
- The nearest-segment search is per-point (plan) — a long line crossing several shots gets points bound to different shots, which is exactly what makes warping locally correct; forcing all points to one shot (cross-section mode) is the exception (cSurveyPC/cItem.vb:803-831).
- `cPoint.BindedSegment` resolves lazily by string id; if the shot was deleted the property returns `Nothing` from then on — stale `S<guid>` tokens are silently dropped on next save.
- Progress/UI strings inside the engine are partly Italian ("Pulizia punti", comments throughout) — don't rely on message text.
- `designtools_debug.xml` exists alongside `designtools.xml`, but it is only loaded by the legacy `frmMain` (cSurveyPC/frmMain.vb:9069); `frmMain2` loads `designtools.xml` (cSurveyPC/frmMain2.vb:6802). Tools with `debug="1"` (e.g. Chunk3D, cSurveyPC/designtools.xml:9) only appear when the app runs with the `debug` command-line flag (`modMain.bIsInDebug`, checked at cSurveyPC/frmMain2.vb:6604-6605). Both files are copied to the output dir (`CopyToOutputDirectory=Always`, cSurveyPC/cSurveyPC.vbproj:3577-3584) and loaded from the **application path**, not the survey.
- Items with `HiddenInDesign` are still saved and still warp; `FilteredInDesign` is runtime-only (not serialized) (cSurveyPC/cItem.vb:548-577 writes only hidden flags).
- `cItemSketch` registers itself in `Survey.Sketches` from its constructor (cSurveyPC/cItemSketch.vb:419) — creating one has global side effects; its images bloat `.csz` files (`_data\design\*.png`).
- `cSurvey.DesignWarpingModeEnum.None` (set when the user clicks Abort in the warping dialog) permanently disables warping for the survey until re-enabled in properties — a classic "my drawing stopped following the data" support case (cSurveyPC/cPlotPlan.vb:1170-1171).

## Related docs

- [topodroid-import.md](topodroid-import.md) — how TopoDroid CSX/therion files become segments + design items (uses `cItemGeneric`→`FromGeneric`, the points `data` format, and `RebindSegments`).
- [calculation-engine.md](calculation-engine.md) — where `Segment.Data.Plan/Profile` projected coordinates and `D` (extended elevation) come from; coordinate conventions.
- [rendering-and-plot.md](rendering-and-plot.md) — `cPlot*` centerline drawing, `cOptions*` paint-option objects, draw caches, print/export pipelines.
- [data-model-and-file-format.md](data-model-and-file-format.md) — `.csz`/`.csx` container, `_data.xml` root layout, `cFile`/storage items.
