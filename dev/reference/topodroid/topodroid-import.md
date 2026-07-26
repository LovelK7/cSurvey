# TopoDroid & external data import

## Purpose

This doc covers how cSurvey ingests data produced outside the app, with TopoDroid as the primary focus: which TopoDroid artifacts cSurvey can consume, the full call graph from menu click to committed survey objects, how TopoDroid/therion sketch symbols map to cSurvey drawing items, and the known failure modes. It also inventories the sibling importers (PocketTopo, Compass, VisualTopo, CaveExplorer, text/CSV, Excel variants, MNemo) for contrast.

## Domain concepts

- **TopoDroid CSX export** — TopoDroid (the Android surveying app) can itself export a survey *in cSurvey's own .csx XML format*, including centerline **and** the sketches drawn on the phone. This is the richest TopoDroid→cSurvey path. Such files carry `properties/@creatid="topodroid"` and `properties/@creatversion` (cSurveyPC/cSurvey.vb:1755-1761, cSurveyPC/cProperties.vb:1033-1034). cSurvey detects that marker at load time and runs a fix-up pipeline over the raw XML and the loaded object model.
- **`creat_postprocessed`** — once cSurvey saves a file that had a foreign `creatid`, it stamps `creat_postprocessed="1"` on `<properties>` so the TopoDroid fix-ups run only once (cSurveyPC/cProperties.vb:1185, read back at cSurveyPC/cSurvey.vb:1747-1753).
- **Therion .th / .th2** — TopoDroid also exports therion format: `.th` files hold centerline data (`centerline … endcenterline` blocks), `.th2` files hold 2D scrap drawings (`scrap … endscrap` with `point`/`line`/`area` symbols). cSurvey has separate importers for each.
- **Segment (shot)** — a `cSegment` is one measured shot (from/to/distance/bearing/inclination + LRUD + flags such as splay/duplicate/surface). Splays are segments with an empty or generated `To` name.
- **Session** — a `cSession` groups shots by survey trip (date + description + instrument settings such as units and back-sight direction).
- **Design / Layer / Item** — `cDesign` is a drawing (Plan or Profile); each design has fixed typed layers (`Borders`, `Signs`, `Soil`, `WaterAndFloorMorphologies`, `CeilingMorphologies`, `RocksAndConcretion`, …; helper accessors at cSurveyPC/cLayers.vb:44-74). Drawing objects are `cItem` subclasses (`cItemFreeHandLine`, `cItemFreeHandArea`, `cItemInvertedFreeHandArea`, `cItemSign`, `cItemText`, `cItemCrossSection`, …).
- **Points `data` attribute** — item geometry is serialized as a single space-separated string in `<points data="x y [flags] …">`; flags per point: leading `#<meta>` (meta command), `B` begin-sequence, `P` pen follows as child node, `T<n>` line type, `L` locked, `S<segmentid>` binds the point to a centerline segment (parser at cSurveyPC/cPoints.vb:496-599). This matters because TopoDroid writes those `S…` tokens with its own non-GUID segment ids.
- **Warping** — imported drawing items bound to segments can be re-projected ("warped") when station coordinates differ between source and destination survey (`WarpItemsEx`, `cPlanWarpingFactor`/`cProfileWarpingFactor`).

## Architecture

There are three distinct TopoDroid ingestion routes, plus a family of unrelated shot-data importers. All are driven from `frmMain2` (the current main form; `frmMain.vb` is a legacy copy with near-identical code, e.g. its own `pSurveyImportTherion` at cSurveyPC/frmMain.vb:15953).

1. **Open a TopoDroid .csx directly** (File → Open). `cSurvey.Load` detects `creatid="topodroid"` (and not yet post-processed) and applies three fix-up passes: `FixTopodroidCSX` rewrites the raw XML *before* parsing (GUID ids, uppercase station names, `<note>` child → attribute); after the object model is built, `FixTopodroidDesign` converts TopoDroid's flat `<plan>/<item>` and `<profile>/<item>` lists into real layer items via `cImportTopoDroidHelper`, and `FixTopodroidSurvey` stamps `import_source`/`import_date` data fields, executes the `C` (close-sequences) meta command and re-binds every item to the centerline (cSurveyPC/cSurvey.vb:943-945, 1566-1570).
2. **Import/merge a .csx/.csz into the current survey** (Import data → cSurvey filter, or drag & drop). `pSurveyImportcSurvey` loads the foreign file into a *second* in-memory `cSurvey` with `LoadOptionsEnum.FixTopoDroid` forced on (so the same TopoDroid fix-ups run), shows the `frmImportcSurvey` option dialog, then copies caves/branches, grades, sessions, segments (with duplicate detection/overwrite policies), trigpoints, and optionally the plan/profile graphics (serializing each item to XML and re-creating it in the target, remapping segment ids and warping) (cSurveyPC/frmMain2.vb:11854-12592).
3. **Therion imports** — `.th` centerline via `cTherion.Import` (creates sessions, segments, splays, fixes/GPS reference), `.th2` scraps via `modImport.TherionTh2ImportFrom` (creates drawing items in Plan/Profile from scrap symbols). TopoDroid's therion exports go through these when the user prefers therion files over csx.

Data-flow narrative for the main TopoDroid path: TopoDroid exports `survey.csx` → user opens or imports it → raw XML fix-ups (`modImport.FixTopodroidCSX`) → normal CSX deserialization (`cSegments`, `cTrigPoints`, `cDesignPlan`, `cDesignProfile`, `cDesignCrossSections`…) → TopoDroid-only extras: DistoX calibration attributes (`g`, `m`, `dip`, `distox`) become segment DataProperties (cSurveyPC/cSegment.vb:735-740) backed by auto-created "DistoX" data-table fields (cSurveyPC/cSegments.vb:191-208) → sketch conversion (`cImportTopoDroidHelper.ConvertDesign/ConvertItem`) instantiates cSurvey items per therion-style symbol name → `FixTopodroidSurvey` re-binds items to segments → `cCalculate.Calculate` recomputes station coordinates (TopoDroid csx has file version `-1` = "no calculate data", cSurveyPC/cSurvey.vb:953) → survey behaves like a native one; on save it is stamped `creat_postprocessed`.

**What cSurvey does *not* read: the TopoDroid project .zip.** No importer touches TopoDroid's own zip archive (which contains the SQLite db/thbook). The only zip handling in the codebase is the Ionic.Zip-based CSZ container reader (cSurveyPC/cFile.vb:386-403; format chosen by extension at cSurveyPC/cFile.vb:35-48: `.csx` = bare XML, anything else = zip whose entries are read as storage items, the survey being `_data.xml`). For automation you must have TopoDroid export `.csx` (best), `.th`, or `.th2`.

## Key classes & files

| File | Class / member | Responsibility |
|---|---|---|
| cSurveyPC/cImportTopoDroidHelper.vb | `cImportTopoDroidHelper` | Static converter: TopoDroid `<item type= name=>` XML → cSurvey drawing items. `ConvertDesign` (:54), `ConvertCrossSection` (:60), `ConvertItem` (:112), scale mapping `pTopodroidscaleToSize` (:95), `cTopodroidVersion`/`GetTopodroidVersion` (:7-52, currently unreferenced elsewhere) |
| cSurveyPC/cTopoDroidImportHelper.vb | `cTopoDroidImportHelper` | Empty placeholder class (3 lines) — ignore |
| cSurveyPC/modImport.vb | `modImport` | TopoDroid fix-ups: `FixTopodroidCSX` (:384), `FixTopodroidDesign` (:330), `FixTopodroidSurvey` (:334), `ReplaceIDItem` (:451); therion th2 scrap importer `TherionTh2ImportFrom` (:490) + `TherionImportOptionsEnum` (:246); GPX/KML waypoint readers (:10, :29); shared splay-grouping helpers `cImportSegments`/`cImportSegment` (:50-141) used by PocketTopo/VisualTopo-style importers |
| cSurveyPC/cSurvey.vb | `cSurvey.Load` | Entry point for any csx/csz; TopoDroid detection & fix-up orchestration (:936, :943, :1566-1570); `LoadOptionsEnum.FixTopoDroid = &H100` (:929-934) |
| cSurveyPC/cTherion.vb | `cTherion` | Therion `.th` centerline importer: `Import` (:828), recursive `pImport` (:318), `cTherionImportOptions` (:270). Also contains therion **export** code (see modExport.vb for file generation) |
| cSurveyPC/frmMain2.vb | `frmMain2` | All import UI drivers: dispatcher `pSurveyImport` (:572), `pSurveyImportcSurvey` (:11854), `pSurveyImportTherion` (:11300), `pSurveyImportTherionGraphics` (:10261), `pSurveyImportText` (:11342), `pSurveyImportVisualTopo` (:11535), `pSurveyImportPocketTopo` (:12594), `pSurveyImportCompass`/`2` (:13027/:12929), `pSurveyImportCaveExplorer` (:13356), `pSurveyImportXLSX*` (:10620-:11091), `pSurveyImportSVG` (:10293), `pSurveyImportTrack` (:10330); ribbon handlers (:16688-16698); drag-drop dispatch (:8462-8517) |
| cSurveyPC/frmImportcSurvey.vb | `frmImportcSurvey` | Options dialog for csx/csz merge; persists every switch in `My.Application.Settings` under `data.import.csurvey.*` (:22-59); `GetShotsDuplicatesDetails` (:7) |
| cSurveyPC/frmImportcSurveyShotsDetails.vb | `frmImportcSurveyShotsDetails` | Flyout selecting *which* shot fields to overwrite on duplicates (Session, CaveBranch, Distance, Bearing, Inclination, LRUD, Direction, Notes, Color, DataProperties + reflection-listed `cReplicateDataAttribute` properties) (:26-41) |
| cSurveyPC/frmImportTherion.vb | `frmImportTherion` | Options for `.th` centerline import: station prefix, process-all-files, comments→notes, target cave/branch (:5-15) |
| cSurveyPC/frmImportTherion2.vb | `frmImportTherion2` | Options for `.th2` graphics import: plan/profile toggles, merge&reorder borders, bezier→spline (not implemented), scale factor (:3-27) |
| cSurveyPC/cSegment.vb | `cSegment` | Shot; reads TopoDroid DistoX attrs into DataProperties (:735-740); XML attrs `cave/branch/session` (:690-693) |
| cSurveyPC/cSegments.vb | `cSegments` | Shot collection; auto-creates DistoX data fields for TopoDroid files (:191-208); `Append` (:260,:272), `FindDuplicate` (:571), `Find(from,to,reverse)` (:602) |
| cSurveyPC/cSession.vb | `cSession` | Accepts TopoDroid date strings `yyyy.mm.dd` / `yyyy-mm-dd` (:395-403) |
| cSurveyPC/cPoints.vb | `cPoints.Parse` | Parses `<points data>` geometry incl. metas and `S<segmentid>` bindings (:496-599) |
| cSurveyPC/cLayerSigns.vb | `cLayerSigns` | Factories used by the converter: `CreateCrossSection` (:22), `CreateSign` by enum (:34) or SVG file (:52), `CreateText` (:68), `CreateAttachment` (:28) |
| cSurveyPC/cIItemSign.vb | `cIItemSign.SignEnum` | Symbol catalogue (Stalactite=515, AirDraught=774, …) that TopoDroid point names are parsed into (:34-119) |
| cSurveyPC/cUIHelpers.vb | `cSegmentsBindingList` | UI grid binding for segments; marshals cSegments events through `SynchronizationContext.Post` (:3485-3495) — the "shots changes from different threads" fix |
| cSurveyPC/cFile.vb | `cFile` | CSX/CSZ container (Ionic.Zip); `_data.xml` + embedded resources (:35-48, :386-403) |
| cSurveyPC/cDesignCrossSection.vb | `cDesignCrossSection` | Notes legacy "topodroid first file format" `<layers>` inside cross-sections (:376-382) |

## Key flows

### 1. Open a TopoDroid-exported .csx (File → Open)

1. cSurveyPC/frmMain2.vb:808 — `pSurveyLoad` calls `oSurvey.Load(Filename)` (no special flags; detection is automatic).
2. cSurveyPC/cSurvey.vb:940-941 — `cFile` opens the file; `.csx` parsed directly, `.csz` unzipped via Ionic.Zip (cSurveyPC/cFile.vb:35-48).
3. cSurveyPC/cSurvey.vb:943-945 — if `creatid="topodroid"` and not `creat_postprocessed` (or `LoadOptionsEnum.FixTopoDroid`, or the hidden Ctrl+Shift "regenerate segment ids" opening flag, cSurveyPC/modOpeningFlags.vb:20-42): `modImport.FixTopodroidCSX(oXml)` mutates the raw DOM:
   - uppercases `properties/@origin` (cSurveyPC/modImport.vb:388-390);
   - copies TopoDroid's `<properties><note>` child into the `note` attribute cSurvey expects (cSurveyPC/modImport.vb:392-394, added in commit 0c6700b);
   - replaces every non-GUID `segment/@id` with a fresh GUID and uppercases `from`/`to` (cSurveyPC/modImport.vb:397-410); same for `<crosssections>` ids (:413-425);
   - for the *old* TopoDroid format (`<plan><layers>`), rewrites `S<oldid> ` tokens inside every item's `points/@data` and `crosssection`/`segment` attributes to the new GUIDs (cSurveyPC/modImport.vb:427-488, `ReplaceIDItem` :451).
4. cSurveyPC/cSurvey.vb:953 — files with meta version `-1` ("generated by other software, no calculate data") skip file-version conversion entirely. Note: current TopoDroid (master, 2026-07) actually writes `version="1.11"` on the `<csurvey>` root (see [topodroid-zip-and-csx-format.md](topodroid-zip-and-csx-format.md)), which walks the no-op 1.11→1.12→1.13→1.14 conversion cases (cSurveyPC/cSurvey.vb:1201-1236), each raising `OnFileConversionRequest` once before proceeding.
5. Normal deserialization: segments (cSurveyPC/cSegments.vb:188-224; DistoX fields :191-208, per-shot `g/m/dip/distox` attrs at cSurveyPC/cSegment.vb:735-740), trigpoints, plan/profile designs (cSurveyPC/cSurvey.vb:1386-1399 — only `<layers>` children are consumed here; the modern TopoDroid format's direct `<item>` children are ignored by this step).
6. cSurveyPC/cSurvey.vb:1532-1549 — no `<calculate>` node → full recalculation (`oCalc.Calculate(False)`).
7. cSurveyPC/cSurvey.vb:1566-1569 — post-load TopoDroid conversion:
   - `modImport.FixTopodroidDesign(Me, oPlan, oXmlRoot.Item("plan"))` → `cImportTopoDroidHelper.ConvertDesign` iterates `<plan>/<item>` elements and instantiates real items (cSurveyPC/modImport.vb:330-332, cSurveyPC/cImportTopoDroidHelper.vb:54-58); same for `<profile>`. **This is where plan vs profile is decided: whatever TopoDroid put under `<plan>` goes to `Survey.Plan`, `<profile>` to `Survey.Profile` — the converter itself is design-agnostic.**
   - `modImport.FixTopodroidSurvey(Me, oXmlRoot)` (cSurveyPC/modImport.vb:334-382) — guarded by "segments data-table does not yet contain `import_source`/`import_date`" (idempotency): adds those fields to the Segments and DesignItems data tables, stamps every segment and item with source id + date, honours the `#C` points meta (close all sequences — old format only), clears metas, and calls `oItem.BindSegments()` on every design item because "topodroid don't do it itself" (:367-368) — this attaches every drawing point to the nearest centerline segment so warping works.
8. On save, `creat_postprocessed="1"` is written so steps 3/7 never run again (cSurveyPC/cProperties.vb:1182-1185).

### 2. Import/merge a .csx/.csz into an open survey (TopoDroid or cSurvey source)

1. cSurveyPC/frmMain2.vb:16688-16689 — ribbon `btnImportData` → `pSurveyImport(ImportExportFormatEnum.Survey, "", True)`; file dialog filter list at :579; FilterIndex 2 = "cSurvey (*.CSX;*.CSZ)" → `pSurveyImportcSurvey` (:603-605). Drag & drop reaches the same place (:8501-8506: empty survey → plain `pSurveyLoad`; otherwise import).
2. cSurveyPC/frmMain2.vb:11860-11861 — the foreign file is loaded into a second survey: `oImportSurvey.Load(Filename, cSurvey.cSurvey.LoadOptionsEnum.FixTopoDroid)` — **the TopoDroid fix-ups from flow 1 are forced on regardless of creator**; :11862-11865 recalculates it if it had no calculate data.
3. cSurveyPC/frmMain2.vb:11868-11983 — `frmImportcSurvey` dialog is prepared; a log panel reports source app ("TopoDroid x.y.z" when `CreatorID = "TopoDroid"`, :11880-11882), whether the surveys share at least one station name (:11892-11899 — sharing none is an *error* that disables data+graphics import), data-table mergeability, warping availability, unbound points, etc.
4. On OK (:11985), in order:
   - texts merge (:11990-11994), surface elevations/orthophotos/WMS (:11996-12021);
   - cave/branch info: optionally grafted under a chosen cave/branch (`chkImportAsBranchOf`), optionally as a new branch named after the imported survey with `ExtendStart` set to the imported origin (:12032-12077);
   - grades (:12080-12086), sessions matched by (date, description) then `CopyFrom` (:12089-12099), non-system highlights (:12101-12106);
   - **segments**: each source segment is round-tripped through XML (`SaveTo` → `New cSegment`) (:12120-12125); duplicate detection per `cbocSurveyImportDuplicatesMode` — index 0 matches by segment **ID**, index 1 by data via `Segments.FindDuplicate` (:12126-12141); duplicates are imported/skipped/overwritten per the checkbox matrix (see options table below); with "overwrite only some data" each field is copied only if ticked in `frmImportcSurveyShotsDetails` (:12153-12202), including reflection-driven extra properties marked `cReplicateDataAttribute` (:12190-12199); non-duplicates are appended and splays get generated `To` names (:12256-12261). A `oDuplicatedSegments` old-id→new-id map is built for graphics rebinding (:12253, :12261);
   - **trigpoints**: `TrigPoints.Rebind()` then per-station copy of entrance/note/label/coordinate/aliases/connections/data (:12267-12297);
   - **graphics** (if `chkcSurveyImportGraphics`): design data-tables merged (:12314); translation vector computed from the two origins when not warping (:12318-12333); items partitioned into plain / cross-section-linked / legends (:12369-12371); each item is serialized with `SaveTo(..., ForImport)`, segment ids remapped via `modImport.ReplaceIDItem` (:12401), recreated by `oSurvey.Plan/Profile.Layers(iLayer).CreateItem(oFile, oXMLItem)` (:12405, :12412), cross-section items registered in `oSurvey.CrossSections` (:12406-12416), then moved or warped: per-segment `WarpItemsEx` with `cPlanWarpingFactor`/`cProfileWarpingFactor` when both sides have bound segments (:12341-12353), cross-section content warped at :12528-12542; markers re-attached (:12459-12465);
   - design properties / scale rules / linked surveys merges (:12559-12570); final `pSurveyCalculate(True)` (:12580).

### 3. Therion `.th` centerline import (TopoDroid "Therion" data export)

1. cSurveyPC/frmMain2.vb:629 — FilterIndex 10 ("*.TH") → `pSurveyImportTherion` (:11300).
2. cSurveyPC/frmMain2.vb:11301-11319 — `frmImportTherion` dialog (prefix, cave/branch target, import-as-new-cave, comments-as-notes); builds `cTherion.cTherionImportOptions` (cSurveyPC/cTherion.vb:270-316) and calls `cTherion.Import(oSurvey, Filename, oOptions)`.
3. cSurveyPC/cTherion.vb:828-834 — adds `import_source/date/filename/row` segment data fields, then recursive `pImport` (:318) parses line-by-line:
   - `survey` → cave (top level) or branch (nested), colored from a palette (:363-421);
   - `centerline` → new `cSession` (today's date + GUID description, renamed when a `date` line appears :443-449) (:422-434);
   - `data normal|dimensions` → column layout; `backcompass/backclino` set session `MeasureDirectionEnum.Inverted` (:450-472);
   - `team` appended to session (:481-486); `units` mapped to session distance/bearing/inclination types with cm→m factor (:501-550);
   - `input` recurses into referenced files (:566-573); `equate` becomes a zero-length segment joining `from@survey`/`to@survey` (:574-601);
   - `extend`/`flags duplicate|surface|splay` latch state for following shots (:602-617); `cs`+`fix` create/refresh a trigpoint UTM coordinate and enable survey GPS with that station as reference (:618-682); `station` is a TODO (:683-684);
   - any other line inside a centerline is a shot: `Survey.Segments.Append()`, session/cave/branch set, `.`/`-` from/to marks splays with synthesized station names (:687-721).
4. Back in frmMain2 (:11321-11337): UI lists refreshed, `pSurveyCalculate(True)`.

### 4. Therion `.th2` sketch import (TopoDroid sketch export)

1. cSurveyPC/frmMain2.vb:16696-16697 — `btnImportDesign` → `pSurveyImport(Design)`; FilterIndex 3 ("*.TH;*.TH2") → `pSurveyImportTherionGraphics` (:696-698, :10261).
2. cSurveyPC/frmMain2.vb:10262-10281 — `frmImportTherion2` options (plan/profile flags, merge&reorder borders, scale factor, forced cave name) → `modImport.TherionTh2ImportFrom(oSurvey, Filename, sForcedCaveName, iOptions, sScaleFactor)`.
3. cSurveyPC/modImport.vb:490-843 — streams the file (ASCII):
   - `input` recurses (:537-543); `scrap` opens a branch named after the scrap; `-projection extended` targets `Survey.Profile`, otherwise `Survey.Plan` (:545-559); `-scale x1 y1 x2 y2 X1 Y1 X2 Y2` computes a unit scale factor (:560-572);
   - `line wall|border|rock-border|pit|chimney` create border/cliff items with `-subtype presumed/invisible` pen mapping, `-outline in` → subtract merge mode, `-reverse`, `-place top/bottom`, `-clip off` (:750-838); coordinates are consumed as line/bezier sequences with Y negated (:592-638);
   - `point entrance|label|water-flow` create sign/text items with `-orientation`, `-scale`, `-align` (:654-690); `area water|sand|clay|pebbles|debrits|blocks|flowstone|else` create soil/water areas whose outlines are copied from previously `-id`-registered lines (:640-652, :692-748);
   - on `endscrap`, if MergeAndReorderBorders is on, all wall areas of the scrap are combined into one and sequences reordered (:576-589).
   - Everything is tagged `DataProperties("import_source") = "therion"`.

### TopoDroid symbol → cSurvey item mapping (`cImportTopoDroidHelper.ConvertItem`, csx path)

Input: `<item cave= branch= type="line|area|point" name="…" [closed reversed outline orientation scale text stationfrom stationto sectionname sectiontext options]><points data=…/>[<crosssection>…]<crosssectionfile>…</item>`. All cites cSurveyPC/cImportTopoDroidHelper.vb.

| TopoDroid `type`/`name` | cSurvey item created | Layer | Lines |
|---|---|---|---|
| line `wall` (outline 1/‑1) | `cItemInvertedFreeHandArea` via `CreateCaveBorder`; outline −1 → `MergeMode.Subtract` | Borders | :173-183 |
| line `wall` (outline 0) | `cItemFreeHandLine` via `CreateBorder` | Borders | :184-192 |
| line `wall:presumed` | `cItemInvertedFreeHandArea` via `CreatePresumedCaveBorder` | Borders | :157-164 |
| line `presumed` | `CreatePresumedBorder` line | Borders | :193-200 |
| line `border` / unknown line | `CreateBorder` line | Borders | :253-269 |
| line `water-flow` | `CreateBorder` line, blue pen ("csurvey has no water flow element") | WaterAndFloorMorphologies | :120-129 |
| line `rock-border` | `cItemFreeHandArea` via `CreateRockArea` | RocksAndConcretion | :149-156 |
| line `overhang` | `CreateOverhangCurve` | WaterAndFloorMorphologies | :165-172 |
| line `pit` | `CreateCliffCurve` | WaterAndFloorMorphologies | :201-209 |
| line `chimney` | `CreateCeilingCliffCurve` | CeilingMorphologies | :210-217 |
| line `slope` | `CreateLevelCurve` | WaterAndFloorMorphologies | :218-225 |
| line `section` | `CreatePresumedBorder` line named `"xsection <options>"` — *not* a real cross-section reference (author's comment :227-228) | WaterAndFloorMorphologies | :226-235 |
| line `floor-meander` / `ceiling-meander` | `CreateMeander` / `CreateCeilingMeander` | Water…/Ceiling… | :237-252 |
| area `water` | `CreateWaterArea` | WaterAndFloorMorphologies | :273-280 |
| area `sand`, `clay` | `CreateSandSoil` | Soil | :281-288, :312-318 |
| area `debris`/`blocks`/`pebbles` | `CreateSmallDebritsSoil`/`CreateBigDebritsSoil`/`CreatePebblesSoil` | Soil | :289-311 |
| unknown area | `CreateSoil` | Soil | :320-327 |
| point `label` | `cItemText` via `CreateText(text)` | Signs | :343-350 |
| point `section` (x-section marker) | `cItemCrossSection` via `CreateCrossSection(cave,branch,segment)` where segment = `Survey.Segments.Find(stationfrom, stationto, True)`; name/text from `sectionname`/`sectiontext`; nested `<crosssection>` items recursively converted with `BindDesignTypeEnum.CrossSections`; optional `<crosssectionfile>` base64 payload → `Survey.Attachments.Add` + `cItemAttachment` | Signs | :351-379 |
| point anything else | `cItemSign` — the name minus `-`/`_` is `Enum.TryParse`d into `cIItemSign.SignEnum` (`stalactite`→`Stalactite`, `air-draught`→`AirDraught`, …; catalogue at cSurveyPC/cIItemSign.vb:34-119); unknown names → `SignEnum.Undefined` (renders the error clipart, cSurveyPC/cLayerSigns.vb:36-37) | Signs | :380-398 |
| point `audio`, `photo` | **dropped** (conversion commented out) | — | :337-342 |

Common post-processing: `pConvertItem` reverts point order when `reversed=0` (i.e. cSurvey's native order is TopoDroid-reversed) and closes sequences when `closed=1` (:68-77); `pConvertSign` applies `orientation` (only if item is `cIItemRotable`) and maps TopoDroid `scale` −2…2 → `SizeEnum.VerySmall…VeryLarge` (:79-110); `water-flow`/`air-draught` points get +90° orientation (:331-334). Cross-section content is placed with a `Location` offset (currently `SizeF(0,0)` — see :366).

### Import options reference

`frmImportcSurvey` (csx/csz merge; settings keys `data.import.csurvey.*`, cSurveyPC/frmImportcSurvey.vb:22-59):

- `chkcSurveyImportData` — import shot data at all.
- `cbocSurveyImportDuplicatesMode` — duplicate detection: 0 = same segment ID, 1 = same data (`FindDuplicate`).
- `chkcSurveyImportDuplicates` — process duplicates (otherwise they're skipped but still id-mapped); `chkcSurveyImportDuplicatesOverwrite` — overwrite the existing shot; `…OverwriteOnlyUsed` — only overwrite shots that are design-bound (`IsBinded()`, frmMain2.vb:12147-12151).
- `chkcSurveyImportOverwriteOnlySomeData` + `cmdcSurveyImportShotsData` flyout — per-field overwrite (Session, CaveBranch, Distance, Bearing, Inclination, LRUD, Direction, Notes, Color, DataProperties, plus any `cReplicateDataAttribute` property) — this is the commit-4adb49c "overwrite only some data for shots" feature (frmMain2.vb:12153-12202).
- `chkcSurveyImportDuplicatesStations` — also refresh data of already-existing stations (:12276).
- `chkImportAsBranchOf` + cave/branch combos, `chkcSurveyImportCreateNewBranch`, `chkcSurveyDisableOriginAsExtendstart` — where the imported caves land; new branch gets `ExtendStart = imported origin` unless disabled (:12032-12056).
- `chkcSurveyImportGraphics`, `chkcSurveyImportPlan`, `chkcSurveyImportProfile` — drawing import; `cbocSurveyImportWarpingMode`: 0 = auto (translate when nothing is segment-bound, else warp), 1 = always warp, 2 = always translate (:12319, :12346-12351).
- `chkcSurveyImportCaveBranchFromDesign` — create cave/branch records from item ownership when shot data is not imported (:12382-12392).
- `chkcSurveyImportSurface`, `chkcSurveyImportDesignProperties`, `chkcSurveyImportScaleRules`, `chkcsurveyimportlinkedsurvey`, `chkcSurveyImportTexts` — auxiliary merges.

`frmImportTherion` (.th): station prefix, import-as-new-cave/branch target, `chkLineOfComment` (therion `#` comments become shot notes, cSurveyPC/cTherion.vb:325-337). `frmImportTherion2` (.th2): plan/profile enable, `chkTherionMergeAndReorderBorders` (combine all walls of a scrap into one area), `chktherionConvertBezierToSpline` (persisted but currently a no-op — code commented at cSurveyPC/modImport.vb:494, 597-601), scale factor, forced cave name.

### Sibling importers (contrast)

All follow the same pattern — modal options form, `Segments.Append()` per line, `import_source`/`import_date` DataProperties, `pSurveyCalculate(True)` at the end:

- **VisualTopo .TRO** — `pSurveyImportVisualTopo` (frmMain2.vb:11535); creates entrance trigpoint from origin (:11804-11811 in the same sub).
- **PocketTopo .TXT export** — `pSurveyImportPocketTopo` (:12594); parses keyword blocks `TRIP/FIX/DATE/DATA/PLAN/ELEVATION/STATIONS/SHOTS/POLYLINE/DECLINATION` (:12642); can import its sketch polylines as graphics too (:12608-12609).
- **Compass .DAT** — `pSurveyImportCompass` → `pSurveyImportCompass2` (:13027/:12929).
- **CaveExplorer .TXT** — `pSurveyImportCaveExplorer` (:13356).
- **Generic text/CSV** — `pSurveyImportText` (:11342) with `frmImportGenericData` column mapping, splay markers, comment chars, forced auto-splay mode (:11392-11395).
- **Excel**: generic XLSX (:11091), Eron XLSX (:10902), **MNemo** XLSX (:10669), cSurvey-format XLSX (:10620).
- **GPS tracks** KML/GPX (:10330) and **SVG** design import (:10293, creates one `cItemGeneric` clipart, optionally divided).

## How to modify safely

- **Idempotency guards**: `FixTopodroidSurvey` only runs its body when the Segments data-table lacks `import_source` (cSurveyPC/modImport.vb:335) and the whole fix-up trio only runs when `creat_postprocessed` is absent (cSurveyPC/cSurvey.vb:943, 1566; stamped at cSurveyPC/cProperties.vb:1185). If you add a new fix-up, put it inside these guards or make it independently idempotent — the same file can be loaded many times.
- **Fix-ups run in two phases**: `FixTopodroidCSX` mutates the *DOM before parsing* — anything that affects deserialization (ids, attribute shapes) must go there; `FixTopodroidDesign`/`FixTopodroidSurvey` run *after* the object model exists — anything needing `Survey.Segments` etc. goes there. Note `FixTopodroidDesign` receives the raw `<plan>`/`<profile>` XML elements again (cSurveyPC/cSurvey.vb:1567-1568): the modern TopoDroid `<item>` children are *only* materialized in this phase.
- **Segment ids must be GUIDs**: points data `S<id>` tokens, `crosssection` and `segment` attributes all reference segment ids as raw strings. If you change id regeneration, you must keep `ReplaceIDItem`/`pFixTopodoirdCSXReplaceID` (note the typo in the name) in sync (cSurveyPC/modImport.vb:443-488), and the merge path's `oDuplicatedSegments` mapping (frmMain2.vb:12401, 12447, 12503).
- **Station-name casing**: everything is uppercased on import (`from`/`to` at modImport.vb:408-409, `fix` stations at cTherion.vb:645-647). Keep this invariant — trigpoint identity is name-based and case-mismatch creates ghost duplicate stations (see the defensive check at cSurveyPC/Calculate/cCalculate.cTrigpoints.vb:181-185).
- **Always `BindSegments()` after creating items programmatically** — imported geometry is not bound to the centerline until you do, and unbound items can't warp when data changes (modImport.vb:367-377, and `SetBindDesignType(..., BindSegment:=True)` default at cSurveyPC/cItem.vb:618).
- **`cSegments` events may fire off the UI thread** during import; UI listeners must marshal (the pattern is `SynchronizationContext.Post`, cSurveyPC/cUIHelpers.vb:3491-3495). Don't add direct grid/list mutations in `cSegments` event handlers.
- **`ConvertItem` returns the created `cItem` and may return `Nothing`** for unhandled type values (falls off the outer `Select Case`, cSurveyPC/cImportTopoDroidHelper.vb:400-401). Callers ignore the return today; if you start using it, null-check.
- The therion `.th` importer recurses on `input` with shared `cTherionImporter` state (cSurveyPC/cTherion.vb:566-573); new per-file state must live on the `Importer` object, not in locals, or nested files will reset it.

## Gotchas

- **TopoDroid's own .zip project archive is not readable** — only its exported `.csx` / `.th` / `.th2` files are. (No code path opens TopoDroid zips; the only zip reader is the CSZ container, cSurveyPC/cFile.vb:386.)
- **`pConvertItem` reverses when `reversed` is *0*** (`If Not bReversed Then Item.Points.Revert()`, cSurveyPC/cImportTopoDroidHelper.vb:69-72) — TopoDroid's point order is opposite to cSurvey's; don't "fix" this by intuition.
- **Empty x-section crash (fixed in commit 0b90671)**: a TopoDroid `point section` with no `<crosssection>` child passed `Nothing` into `ConvertCrossSection`; the guard is `If Items IsNot Nothing` (cSurveyPC/cImportTopoDroidHelper.vb:61). Any new consumer of `XMLItem.Item("crosssection")` needs the same null check.
- **Cross-thread shots error (fixed in commit 0c6700b)**: importing appended segments from a worker context while `cSegmentsBindingList` mutated the bound grid list directly → "shots changes from different threads". All its event handlers now `oContext.Post` (cSurveyPC/cUIHelpers.vb:3506+). Note `oContext` is captured in the constructor — constructing the binding list off the UI thread would re-introduce the bug.
- **TopoDroid `<note>` support (commit 0c6700b)**: TopoDroid writes the survey note as a `<properties><note>` child; cSurvey expects an attribute; converted at cSurveyPC/modImport.vb:392-394. Only the *survey* note — per-shot comments come through the `comment`/note attribute path.
- **UTF-8**: the therion **export** had a utf8 crash with non-ASCII survey names (fixed in modExport.vb by commit 0b90671). On import, beware encodings: `TherionTh2ImportFrom` reads `.th2` as **ASCII** (cSurveyPC/modImport.vb:516) — non-ASCII labels are mangled; `cTherion.pImport` uses BOM detection (`New StreamReader(Filename, True)`, cSurveyPC/cTherion.vb:322) and only logs the therion `encoding` directive without applying it (:341-345).
- **`frmImportcSurveyShotsDetails` DataProperties bug**: the checked-changed handler stores the key as `"DataProperties "` (trailing space) while the reader checks `"DataProperties"` (cSurveyPC/frmImportcSurveyShotsDetails.vb:119 vs frmMain2.vb:12186). The corrupted key even round-trips through saved settings (written as `DataProperties =1` at cSurveyPC/frmImportcSurvey.vb:87-89, re-split on `=` with the trailing space intact at :48-58), and the checkbox seeding at cSurveyPC/frmImportcSurveyShotsDetails.vb:38 looks up the correct key — so once toggled via the UI, the DataProperties overwrite flag is never honored and the box reopens unchecked.
- **Old TopoDroid files** may contain: non-GUID ids, `<layers>` inside `<plan>` (legacy format, cSurveyPC/cDesignCrossSection.vb:376-382), or cross-section items placed in the wrong layer — the Clean-up tool removes those (`chkDesignRemoveInvalidItem`, cSurveyPC/frmMain2.vb:2148-2155).
- **Filter indices are load-bearing**: drag&drop and menu code call `pSurveyImport` with hard-coded `FilterIndex` values (e.g. 2 = cSurvey, 10 = therion .th); reordering the OpenFileDialog filter string at frmMain2.vb:579 silently breaks those call sites (:8487-8506, :14461-14513).
- **Data dropped from TopoDroid input**: audio/photo points; the `line section` type (becomes a cosmetic named line, not a section reference); item metas other than `C`; `orientation` on non-rotable items and `scale` on non-sizable items; unknown point names render as the "undefined" error sign rather than failing. In `.th` import: `explo-team`/`explo-date` (warned), `mark/infer/grid-angle/declination/grade/sd/instrument/calibrate/station-names` (silently ignored, cSurveyPC/cTherion.vb:490-499), scraps inside `.th` (:355-359), `station` lines (TODO :683), non-UTM `fix` coordinates (warned :675-681).
- `cTopoDroidImportHelper.vb` (3-line empty class) vs `cImportTopoDroidHelper.vb` (the real one) — easy to open the wrong file.

## Related docs

- [topodroid-zip-and-csx-format.md](topodroid-zip-and-csx-format.md) — the *sending* side: TopoDroid project .zip internals (manifest, survey.sql, .tdr) and the exact csx XML its exporter writes.
- [data-model-and-file-format.md](../data-model-and-file-format.md) — CSX/CSZ schema, `cSegment`/`cItem` serialization details.
- [calculation-engine.md](../calculation-engine.md) — what happens in `cCalculate.Calculate` after import (station coordinates, splay projection).
