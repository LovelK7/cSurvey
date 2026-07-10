# Calculation Engine (survey network → coordinates → projections)

## Purpose

This subsystem turns raw survey shots (distance/azimuth/inclination between named stations, plus splays) into 3D station coordinates and into the two 2D projections the drawing layer works on: **plan** (top view) and **profile** (extended elevation, i.e. the cave "unrolled" along its passages). It also produces per-station wall estimates (LRUD side measures), loop-closure statistics (rings), geographic anchoring (lat/long/UTM, declination, meridian convergence) and cave statistics (speleometrics). Everything downstream — drawing, warping, 3D model, exports — reads this engine's output.

**The single most important architectural fact:** cSurvey does **not** solve the network itself. It shells out to an external **Therion** executable (`therion.exe`, path in user setting `therion.path`), which performs the least-squares network adjustment, loop closure, declination lookup and geodesy; cSurvey exports a temp `.th` file, runs Therion, then parses back a Compass `.plt` model file and the Therion log. The enum `CalculateTypeEnum` has `None/Internal/Therion` (cSurveyPC/cSurvey.vb:114) but the property setter is hard-coded: `iCalculateType = CalculateTypeEnum.Therion` (cSurveyPC/cProperties.vb:521) — Therion is the only engine that actually runs.

## Domain concepts

- **Trigpoint** = survey station. Two parallel worlds exist:
  - `cSurvey.cTrigPoint` (cSurveyPC/cTrigPoint.vb) — the *user-entered* station (name, entrance flag, GPS coordinate, notes). Its computed position lives in `.Data` (`Plot.cStationData`, X/Y/Z + IsOrphan/IsSplay/IsCalibration flags, cSurveyPC/Calculate/cCalculate.Plot.cStationData.vb:5).
  - `Calculate.cTrigPoint` (cSurveyPC/Calculate/cCalculate.cTrigpoint.vb:7) — the *calculation graph node*, rebuilt on every full calculate: connections to neighbour stations, a `cTrigPointPoint` position, a `cTrigPointCoordinate` (lat/long/alt), and a `cTrigPointSideMeasure` (LRUD).
- **cTrigPointPoint** — 4-component position `X, Y, Z, D` (cSurveyPC/Calculate/cCalculate.cTrigpointPoint.vb:14-17). `D` is the **extended-elevation abscissa**: the cumulative horizontal distance along the unrolled traverse. `To2DPoint(Projection)` yields `FromTop` = (X,Y) plan, `FromRightSide` = (Y,Z), `Perpendicular` = (D,Z) extended profile (cSurveyPC/Calculate/cCalculate.cTrigpointPoint.vb:125-133).
- **Coordinate convention** (from the `.plt` import, cSurveyPC/Calculate/cCalculate.vb:738-740): X = east (m), **Y = −north** (grows south/screen-down), **Z = −up** (grows with depth), origin station at (0,0,0). Plan/profile drawing coordinates are therefore already screen-oriented. Meters everywhere; Therion's meridian convergence is rotated back out so grid north stays "up" (cSurveyPC/Calculate/cCalculate.vb:1762, cCalculate.cTrigpoints.vb:291).
- **Segment** = one shot (`cSegment`). Its calculation output hangs off `Segment.Data` (`Calculate.Plot.cData`, cSurveyPC/cSegment.vb:810) with three `cSpatialData` copies — `SourceData` (as entered), `Data` (recomputed from adjusted coordinates), `OldData` (backup for warping deltas) — plus `Plan`/`Profile` projected data (cSurveyPC/Calculate/cCalculate.Plot.cData.vb:6-15).
- **Equate** = zero-length shot declaring two station names identical (`Segment.IsEquate`); handled specially throughout (equate index in `Calculate.cTrigPoints.CreateEquateIndex`, cSurveyPC/Calculate/cCalculate.cTrigpoints.vb:148).
- **Segment group** (`cSegmentGroup`, cSurveyPC/Calculate/cCalculate.cSegmentGroup.vb:5) — shots grouped per cave/branch, each with its own `ExtendStart` station and connection defs; used to order the extended-elevation walk and relocate branch profiles relative to each other.
- **Ring** (`cRing`) — a closed loop found by Therion, stored as an ordered station-name list plus error stats (% error, absolute error, ΔX/ΔY/ΔZ, loop length) parsed from the Therion log (cSurveyPC/Calculate/cCalculate.Plot.cRing.vb:127-162).
- **Side measures (LRUD)** — Left/Right (plan) and Up/Down (profile) wall distances at a station, keyed by which neighbouring station the shot came from (`cTrigPointSideMeasure`, cSurveyPC/Calculate/cCalculate.cTrigPointSideMeasure.vb:7). Fed either by explicit LRUD on shots or **derived from splays** (`Segment.GetBaseLeft/Right/Up/Down`).
- **Warping** — after recalculation, drawing items bound to moved shots are morphed with an affine matrix derived from old-vs-new shot geometry (`cPlanWarpingFactor.GetMatrix`, cSurveyPC/Calculate/cCalculate.Plot.cData.vb:58-89). That is why `OldData`/old points are preserved.

## Architecture

Data flow, end to end:

```
cSegment edits ──► cSurvey.iInvalidated |= segment.Invalidated   (cSurvey.vb:1921,1927)
                    (FullCalculate / PartialCalculate / OnlySplay per property touched)
        UI: frmMain2.pSurveyCalculate ── if CalculateMode=Automatic ──► oSurvey.Calculate.Calculate(True)
                                                                        (frmMain2.vb:5543,5551)
cCalculate.Calculate (Calculate/cCalculate.vb:576)
 ├─ 1. validate origin, GPS ref point, sessions        (cCalculate.vb:592-631)
 ├─ 2. pFillSegments → cSegmentGroupCollection         (cCalculate.vb:634, 2172)
 ├─ 3. pTrigPointsCalculate: build station graph       (cCalculate.vb:640, 2077)
 ├─ 4. pCalculatePrepareData: BFS from origin, detect orphans, mark splay/calibration stations
 │                                                     (cCalculate.vb:642, 955)
 ├─ 5. pCalculateSegments: THERION ROUND-TRIP          (cCalculate.vb:651, 1591)
 │    ├─ export %TEMP%\_therion*_input.th + .thconfig  (modExport.TherionThExportTo, modExport.vb:3791)
 │    ├─ run therion.exe                               (modMain.ExecuteTherion, modMain.vb:363)
 │    ├─ parse log: loop errors→cRings, geomag declination→cGeoMagDeclinationData,
 │    │   meridian convergence, per-line errors → typed exceptions   (cCalculate.vb:1693-1757)
 │    ├─ import _output.plt → Calculate.cTrigPoint.Point (X,Y,Z)     (pCompassPltImportFrom, cCalculate.vb:722)
 │    ├─ rotate plan by −meridianConvergence           (cCalculate.vb:1762)
 │    ├─ copy XYZ to survey stations: oSurvey.TrigPoints(n).Data.MoveTo  (cCalculate.vb:1765-1776)
 │    ├─ pCalculateRingData: flag shots in rings       (cCalculate.vb:1779, 1176)
 │    ├─ pCalculateDAndSideMeasures: compute D (extended elevation) + LRUD per station
 │    │                                                (cCalculate.vb:1782, 1198)
 │    ├─ read Therion XVI sketch rasters back for sketch morphing    (cCalculate.vb:1789-1967)
 │    └─ reverse-compute per-shot distance/bearing/inclination from adjusted coords
 │        into Segment.Data (backup first, for warping)              (cCalculate.vb:1983-2056)
 ├─ 6. pCalculateGeographics: lat/long/alt for every station from GPS ref point
 │                                                     (cCalculate.vb:653, 250)
 ├─ 7. oSurvey.Plan.Plot.Calculate + CalculateSplay    (cCalculate.vb:671-673 → cPlotPlan.vb:808,655)
 ├─ 8. oSurvey.Profile.Plot.Calculate + CalculateSplay (cCalculate.vb:679-681 → cPlotProfile.vb:752,210)
 ├─ 9. Speleometrics.Calculate                         (cCalculate.vb:687)
 └─ OnCalculateComplete → cSurvey resets Invalidated, redraws plots  (cSurvey.vb:1963-1968)
```

Results live in three places, all serialized into `_data.xml` under `<calculate>` (`cCalculate.SaveTo`, cSurveyPC/Calculate/cCalculate.vb:125: `<ts>` trigpoints incl. side measures, `<rngs>` rings, `<mdd>` declination, `<sms>` speleometrics) and per-segment under `<data>` (`cData.SaveTo`, cSurveyPC/Calculate/cCalculate.Plot.cData.vb:355: `srcdata/olddata/data` + `planpd`/`profilepd`). Because results are persisted, a freshly loaded file does not recalculate until invalidated.

### Invalidation granularity

`cCalculate.InvalidateEnum` (cSurveyPC/Calculate/cCalculate.vb:95): `OnlyPlanSplay`, `OnlyProfileSplay`, `OnlySplay`, `PartialCalculate` (re-walk D/LRUD without re-running Therion, cCalculate.vb:654-655), `FullCalculate`. `Calculate()` dispatches on `oSurvey.Invalidated` (cCalculate.vb:582-588, 637). A `cSegment` property setter only marks the object changed; the appropriate flag is computed when the segment is saved, by diffing old vs new field values (cSurveyPC/cSegment.vb:1097-1134 — LRUD/UnBindable ⇒ `PartialCalculate`, nearly everything else ⇒ `FullCalculate`); `cSurvey` ORs the flags together in its change-event handlers (cSurveyPC/cSurvey.vb:1921, 1927, 1989). Recalc is *not* fired by the events themselves — the UI decides (automatic mode) or the user presses F9 (`pSurveyCalculate(Force)`, cSurveyPC/frmMain2.vb:5542).

### Plan vs profile projection

- **Plan** (`cPlotPlan.Calculate`, cSurveyPC/cPlotPlan.vb:808): for each valid segment, from/to points are simply `Calculate.TrigPoints(name).Point.To2DPoint(FromTop)` (cPlotPlan.vb:837), written into `Segment.Data.Plan.SetPoints(from, to, p1, p2)` (cPlotPlan.vb:884). A second pass computes **side points** (left/right wall points at each station) from `SideMeasure.GetLeftRight(connection)` projected along a bearing chosen by `SideMeasuresTypeEnum` (Bisection / PerpendicularToNext / PerpendicularToPrevious, cPlotPlan.vb:932-945) and stores them via `Data.Plan.SetSidePoints(...)` (cPlotPlan.vb:1119). These side points are the built-in wall estimate polygon (`cPlanProjectedData.GetPolygon`, cSurveyPC/Calculate/cCalculate.Plot.cPlanProjectedData.vb:375).
- **Profile / extended elevation** (`cPlotProfile.Calculate`, cSurveyPC/cPlotProfile.vb:752): points come from the **per-connection** point `TrigPoints(from).Connections(to).GetPoint.To2DPoint(Perpendicular)` = (D, Z) (cPlotProfile.vb:771-777). The same physical station can appear at *different D* for different connections — that is how the cave "unrolls": junctions and loops are duplicated horizontally instead of overlapping. Up/Down side points are vertical offsets from `SideMeasure.GetUpDown` (cPlotProfile.vb:792-805). A surface terrain profile is sampled every 2 m along the plan projection if a DEM is configured (cPlotProfile.vb:811-845).
- **How D is computed** (`pCalculateDAndSideMeasures`, cSurveyPC/Calculate/cCalculate.vb:1198): breadth-first walk per segment group starting at the group's `ExtendStart`; for every shot, `D(to) = D(from) + planProjectedLength × sign` where sign = −1 for `Direction=Left`, ×−1 again if the shot is reversed (cCalculate.vb:1269-1283); vertical shots add 0. Results are stored per connection (`toTP.Connections.SetPoint(fromName, point)`, cCalculate.vb:1287). The same walk appends LRUD into `SideMeasure` — splays always attach U/D + L/R to the shot's far station (cCalculate.vb:1301-1309); normal shots attach at start or end per `GetSideMeasuresReferTo` (cCalculate.vb:1311-1328). Afterwards, branch groups are shifted along D to their parent connection station and finally everything is offset so the origin sits at D=0 (cCalculate.vb:1358-1463). `extend start` / `extend ignore` directives are also exported to Therion so its own extended output matches (modExport.vb:3847, 3873).

### Splays in the projections

Splays are first calculated exactly like normal shots (their own `Data.Plan`/`Data.Profile` from/to points). `CalculateSplay` then attaches, to every *centerline* segment, the list of splays radiating from its two stations: `Segment.Data.Plan.FromSplays/ToSplays` filled with `cSplayPlanProjectedData` records (splay segment ID, tip point, left/right side points, in-range flag) (cSurveyPC/cPlotPlan.vb:655-767; record shape at cSurveyPC/Calculate/cCalculate.Plot.cSplayPlanProjectedData.vb:24-32). The in-range flag implements `PlanSplayBorderProjectionType` filtering (project all splays, or only those within an inclination range / a Z-slab around a reference altitude, cPlotPlan.vb:687-700). The profile equivalent lives in cPlotProfile.vb:210. The drawing layer's "splay border" items consume these collections to auto-draw walls. Splay-only invalidation (`OnlySplay`) skips the whole Therion pipeline (cCalculate.vb:582-588).

### Loop closure / error distribution

Loop detection and error distribution are done **entirely by Therion** during the network adjustment; the adjusted coordinates come back in the `.plt`. cSurvey only *reports* loops: log lines between the `loop errors` markers are parsed into `cRing` objects (`oRs.Append(line, dict)`, cCalculate.vb:1748-1755; fixed-column parse at cSurveyPC/Calculate/cCalculate.Plot.cRing.vb:127-162), the `average loop error:` line fills `cRings.SetAverageErrorPercent` (cCalculate.vb:1742-1746), and `pCalculateRingData` flags each segment whose two stations are in some ring (`Segment.Data.SetFlag(IsInRing)`, cCalculate.vb:1176-1183) so the UI can color loops. Ring selection/color survives recalcs via a hash of the sorted station list (cSurveyPC/Calculate/cCalculate.Plot.cRings.vb:149-162).

### Geographic anchoring: fixed points, UTM, declination

- A survey has an **origin** station (`Properties.Origin`) pinned to (0,0,0), and optionally a **GPS reference point** (origin or custom, `cTrigPoints.GetGPSBaseReferencePoint`, cSurveyPC/cTrigPoints.vb:272) with a `cCoordinate` (lat/long/alt with format/system conversion, cSurveyPC/cCoordinate.vb:4; UTM↔WGS84 via GeoUtility wrappers in cSurveyPC/modUTM.vb:109-171, incl. `GetMeridianConvergence`).
- If `Properties.GPS.SendToTherion`, every fixed station is exported as `cs lat-long` + `fix <station> lat long alt` (modExport.vb:3878-3881); Therion then does geodesy and **automatic per-session magnetic declination** (its `geomag declinations` log lines are parsed into `cGeoMagDeclinationData`, a date→declination map, cSurveyPC/Calculate/cCalculate.Plot.cGeoMagDeclinationData.vb:115-131; meridian convergence at cCalculate.vb:1700-1705). Without GPS, a manual global declination is exported as `survey ... -declination [x deg]` (modExport.vb:3805-3812).
- After import, the plan is rotated by −meridianConvergence so drawings stay grid-north-up (cCalculate.vb:1762); the same angle is reapplied where true geo output is needed (e.g. cSurveyPC/cDesign.vb:1001).
- `pCalculateGeographics` (cCalculate.vb:250-269) then computes lat/long/alt for *every* station from the reference point via `modExport.CalculateCoordinatesFromTrigpoint` (modExport.vb:598) and stores it in `Calculate.cTrigPoint.Coordinate` (plain decimal lat/long/alt, cSurveyPC/Calculate/cCalculate.cTrigpointCoordinate.vb:7).

## Key classes & files

| File (cSurveyPC/) | Class | Responsibility |
|---|---|---|
| Calculate/cCalculate.vb | `cCalculate` | Orchestrates the whole pipeline; owns `TrigPoints`, `Rings`, `GeoMagDeclinationData`, `Speleometrics`, `CalculateData` (log items); typed exceptions (`cCalculateTherionException`, `cCalculateOrphanShotsException`, `cCalculateMissingSessionException`, ...) |
| Calculate/cCalculate.cTrigpoints.vb | `Calculate.cTrigPoints` | Name→`cTrigPoint` dictionary (case-sensitive!); equate index; `PlanRotate` |
| Calculate/cCalculate.cTrigpoint.vb | `Calculate.cTrigPoint` | Graph node: `Point`, `Coordinate`, `Connections`, `SideMeasure`, `Depth` |
| Calculate/cCalculate.cTrigpointPoint.vb | `cTrigPointPoint` | X/Y/Z/D value type + `To2DPoint(ProjectionEnum)` |
| Calculate/cCalculate.cTrigpointConnections.vb / cCalculate.cTrigpointConnection.vb | `cTrigPointConnections`, `cTrigPointConnection` | Per-neighbour edge list; each connection stores its own `cTrigPointPoint` (this is where extended-elevation positions live) |
| Calculate/cCalculate.cTrigPointSideMeasure.vb | `cTrigPointSideMeasure` | Per-station LRUD keyed by connection; `GetLeftRight(conn)`, `GetUpDown()` |
| cTrigPointLeftRightSideMeasure.vb / cTrigPointUpDownSideMeasure.vb | `cTrigPointLeftRightSideMeasure`, `cTrigPointUpDownSideMeasure` | One L/R (with `SideMeasuresTypeEnum`) or U/D pair; XML `smlr`/`smud` |
| Calculate/cCalculate.cSegmentGroup.vb (+Collection) | `cSegmentGroup` | Cave/branch shot group with `ExtendStart`, `ParentConnection`/`Connection` |
| Calculate/cCalculate.Plot.cData.vb | `Plot.cData` | Per-segment calc results: `SourceData`/`Data`/`OldData`, `Plan`, `Profile`, `SubDatas` (3D oversampling), warping factors, `IsInRing` |
| Calculate/cCalculate.Plot.cSpatialData.vb | `cSpatialData` | From/To/Distance/Bearing/Inclination/Direction/Reversed record |
| Calculate/cCalculate.Plot.cPlanProjectedData.vb | `cPlanProjectedData` | Plan from/to points, 4 side points + bearings, old copies, `FromSplays`/`ToSplays`, `GetProjectedDistance` |
| Calculate/cCalculate.Plot.cProfileProjectedData.vb | `cProfileProjectedData` | Same for extended elevation (Up/Down side points, `SurfaceProfile`) |
| Calculate/cCalculate.Plot.cSplayPlanProjectedData.vb (+s, +Profile variants) | `cSplayPlanProjectedData` etc. | One projected splay attached to a station: tip + L/R (or U/D) points, `InRange` |
| Calculate/cCalculate.Plot.cRing.vb / cRings.vb | `cRing`, `cRings` | Loop membership + error stats parsed from Therion log |
| Calculate/cCalculate.Plot.cGeoMagDeclinationData.vb | `cGeoMagDeclinationData` | Date→declination table + meridian convergence |
| Calculate/cCalculate.Plot.cStationData.vb | `Plot.cStationData` | Final X/Y/Z + flags stored on the *survey-level* `cTrigPoint.Data` |
| Calculate/cCalculate.Plot.cSpeleometrics.vb (+cSpeleometric) | `cSpeleometrics` | Per cave/branch stats: measured/real/plan length, depth range, station/segment counts |
| Calculate/cCalculate.Plot.cSubData(s)/cPlanSubData/cProfileSubData | `cSubData` family | Shot subdivision + LRUD interpolation for the 3D model (`CalculateDataFromDesigns`, cCalculate.vb:271, can also *reverse-engineer* LRUD from the drawn map via `modDesignLRUD`) |
| cPlot.vb | `cPlot` (abstract) | Common plot API: `Calculate`/`CalculateSplay` (cPlot.vb:485-486), `Redraw` (303-305), `HitTest` (573-575), `GetBounds` (579) |
| cPlotPlan.vb / cPlotProfile.vb | `cPlotPlan`, `cPlotProfile` | Projection computation + design warping trigger |
| cCoordinate.vb | `cCoordinate` | User-facing geo coordinate with format/system parsing (WGS84, UTM zone/band) |
| modUTM.vb | `modUTM` | UTM↔WGS84 conversion, `GetMeridianConvergence` |
| modExport.vb | `TherionThExportTo`, `TherionCreateConfig` | Generates the `.th`/`.thconfig` Therion input (sessions→centreline blocks, equates, fix, extend, station-name dictionary) |
| modMain.vb | `ExecuteTherion` | Runs therion.exe hidden, 120 s timeout, THERION env var for ini |

## Key flows

### 1. Full recalculation (edit shot → new map)

1. cSurveyPC/cSegment.vb:1199-1209 — a property setter (e.g. `From`) marks the segment changed; on save the segment's `Invalidated` flag reaches `cSurvey` (cSurveyPC/cSurvey.vb:1921) → `iInvalidated |= FullCalculate`.
2. cSurveyPC/frmMain2.vb:5543-5551 — if `Properties.CalculateMode = Automatic` (or user forces), calls `oSurvey.Calculate.Calculate(True)`.
3. cSurveyPC/Calculate/cCalculate.vb:590-634 — `TrigPoints.Rebind()`, origin/GPS validation, `pFillSegments` builds `cSegmentGroupCollection` and clones each shot's `SourceData` (`CloneData`, cCalculate.Plot.cData.vb:474).
4. cSurveyPC/Calculate/cCalculate.vb:640 — `pTrigPointsCalculate` rebuilds the `Calculate.cTrigPoints` graph (`Append` + `Connections.AppendAsShot/AppendAsEquate`, cCalculate.vb:2077-2115) and returns orphan stations (unreachable from origin ⇒ `cCalculateOrphanShotsException`, cCalculate.vb:643-649).
5. cSurveyPC/Calculate/cCalculate.vb:651 → 1591 — `pCalculateSegments`: writes `%TEMP%\_therion_<guid>_input.th` (station names optionally replaced by a numeric safe-name dictionary, cCalculate.vb:1640-1659), writes thconfig with `export model -fmt compass` + two `export map` XVI commands (cCalculate.vb:1681-1685), runs Therion (cCalculate.vb:1688), parses the log (rings/declination/convergence/errors, cCalculate.vb:1693-1757), imports the `.plt` (station XYZ, feet→m, sign flips, origin re-zeroed; equates propagated recursively, cCalculate.vb:722-788).
6. cSurveyPC/Calculate/cCalculate.vb:1765-1776 — copies each computed point into `oSurvey.TrigPoints(name).Data.MoveTo(X,Y,Z)`; unknown stations collapse onto the origin.
7. cSurveyPC/Calculate/cCalculate.vb:1782 → 1198 — `pCalculateDAndSideMeasures` computes extended-elevation D per connection and fills `SideMeasure` LRUD (details above).
8. cSurveyPC/Calculate/cCalculate.vb:1983-2056 — recomputes each shot's distance/bearing/inclination from adjusted coordinates into `Segment.Data.Data` (with `BackupData()` first) so warping factors can be derived.
9. cSurveyPC/Calculate/cCalculate.vb:671-681 — `Plan.Plot.Calculate` / `Profile.Plot.Calculate` project everything into `Segment.Data.Plan/.Profile` and (if `PerformWarping` and warping active) morph bound drawing items (cPlotPlan.vb:1140-1202); `CalculateSplay` attaches splay projections.
10. cSurveyPC/cSurvey.vb:1963-1968 — `OnCalculateComplete` resets `Invalidated`, redraws both plots, raises `OnCalculate` for the UI.

### 2. Ask "where is station X?" (public API surface)

All read paths, given `oSurvey As cSurvey`:

- **3D (adjusted, screen-convention):** `oSurvey.Calculate.TrigPoints("X").Point` → `cTrigPointPoint` with `.X .Y .Z .D As Decimal` (Calculate/cCalculate.cTrigpoints.vb:267 indexer; Calculate/cCalculate.cTrigpoint.vb:120). Also mirrored on `oSurvey.TrigPoints("X").Data` → `.X .Y .Z` (`Plot.cStationData`, cTrigPoint.vb:216).
- **Plan 2D:** `oSurvey.Calculate.TrigPoints("X").Point.To2DPoint(cTrigPointPoint.ProjectionEnum.FromTop)` → `PointD` (Calculate/cCalculate.cTrigpointPoint.vb:125).
- **Extended profile 2D:** `oSurvey.Calculate.TrigPoints("X").Connections(fromStation).GetPoint.To2DPoint(ProjectionEnum.Perpendicular)` — connection-specific! (this is what `cPlotProfile.Calculate` uses, cPlotProfile.vb:771).
- **Per-shot projected geometry:** `segment.Data.Plan.FromPoint/ToPoint/FromSidePointLeft/.../GetPolygon()` and `segment.Data.Profile.FromPoint/ToPoint/FromSidePointUp/Down` (Calculate/cCalculate.Plot.cPlanProjectedData.vb:214-252, 375).
- **Walls at a station:** `oSurvey.Calculate.TrigPoints("X").SideMeasure.GetLeftRight(connection) / .GetUpDown()` → `SizeD` (Calculate/cCalculate.cTrigPointSideMeasure.vb:63-96).
- **Splays around a shot:** `segment.Data.Plan.FromSplays / ToSplays` (enumerable of `cSplayPlanProjectedData` with `.ToPoint .LeftPoint .RightPoint .InRange`).
- **Geographic:** `oSurvey.Calculate.TrigPoints("X").Coordinate` → `.Latitude .Longitude .Altitude As Decimal`; convert with `modUTM.WGS84ToUTM(coordinate)` (modUTM.vb:117).
- **Loop stats:** `oSurvey.Calculate.Rings` (`AverageErrorPercent()`, per-ring `ErrorPercent/Length/GetStations()`); **stats:** `oSurvey.Calculate.Speleometrics`; **run diagnostics:** `oSurvey.Calculate.CalculateData` (cCalculate.vb:2130).

Note: `Segment.Data.Plan/Profile` are `Friend` (assembly-internal), as is `cCalculate.Calculate` itself — in-process automation inside cSurveyPC.exe sees everything; an external consumer would have to go through the survey file XML or exports.

### 3. Partial recalculation (LRUD edit)

1. Changing a shot's `Up`/`Down`/`Left`/`Right` (or `UnBindable`) sets only `PartialCalculate` (cSurveyPC/cSegment.vb:1123-1126, 1133). Note: flipping `Direction` does **not** — it sets `FullCalculate` and re-runs Therion (cSegment.vb:1117), as do From/To/Distance/Bearing/Inclination/Session/Cave/Branch and the shot-type flags (cSegment.vb:1097-1134).
2. cSurveyPC/Calculate/cCalculate.vb:654-655 — `Calculate` skips Therion and runs only `pCalculateDAndSideMeasures` (station XYZ unchanged, D + side measures re-walked).
3. cCalculate.vb:668-681 — plan+profile plots recomputed as usual (centerline identical, wall side-points move).

### 4. Speleometrics

1. cSurveyPC/Calculate/cCalculate.vb:687 — after plots, `oSpeleometrics.Calculate()`.
2. cSurveyPC/Calculate/cCalculate.Plot.cSpeleometrics.vb:14-110 — per cave × branch: sums `GetBaseDistance` (measured), `Data.Data.Distance` (adjusted), `Data.Plan.GetProjectedDistance` (plan length), depth range from profile bounds; stored in `cSpeleometric` items serialized under `<sms>`.

## How to modify safely

- **Never bypass `Invalidate` + `Calculate`.** All projected data (`Segment.Data.*`, `TrigPoint.Data`) is derived state persisted in the file; writing shots without recalculating leaves a stale-but-plausible map. After programmatic imports call `oSurvey.Invalidate()` then `oSurvey.Calculate.Calculate(True)` — the UI equivalent is `pSurveyInvalidate` (frmMain2.vb:5537-5540), which calls `pSurveyCalculate(False)`; note that with `Force=False` the recalc only actually runs when `Properties.CalculateMode = Automatic` (frmMain2.vb:5543), so headless code should call `Calculate(True)` itself.
- **Preserve the old/new data pairing.** Warping depends on `BackupData()` being called exactly once per recalc before `SetData` (cCalculate.vb:1987, 2051) and on `Plan/Profile.SetPoints` backing up old points (cCalculate.Plot.cPlanProjectedData.vb:278-302). Breaking this smears every bound drawing.
- **Session discipline (CalculateVersion ≥ 3).** Every non-equate, non-virtual segment must have a `Session`, or `Calculate` throws `cCalculateMissingSessionException` (cCalculate.vb:621-627). Sessions carry date (→ declination) and instrument config; the Therion export emits one centreline per session.
- **Origin & connectivity invariants:** exactly one origin (`Properties.Origin`) must exist and be non-orphan (cCalculate.vb:592-598); every station must be reachable from it through non-ignored connections, else orphan exceptions. Each cave/branch group must have either both `ParentConnection` and `Connection` or neither (cCalculate.vb:2193-2196), and its `ExtendStart` must touch one of its shots (cCalculate.vb:976-982).
- **Station names:** `Calculate.cTrigPoints` dictionary is case-sensitive while several lookups use `OrdinalIgnoreCase` (cCalculate.cTrigpoints.vb:175 vs cCalculate.vb:960); TopoDroid names differing only by case have historically produced duplicate-station bugs (comment at cCalculate.cTrigpoints.vb:181). Names matching `*(*)` are auto-flagged splay stations (cCalculate.vb:1064). The safe-name dictionary must stay bijective or the log/plt back-translation breaks (cCalculate.vb:1648-1658).
- **Don't change the .plt sign/units conversion** (cCalculate.vb:738-740) or `ProjectionEnum` mappings — the whole drawing stack, saved designs, and warping matrices assume Y-south/Z-down meters.
- **Threading:** heavy use of `Parallel.ForEach` with `SyncLock` on shared collections (e.g. cCalculate.vb:989-1032); anything you add inside those lambdas must be thread-safe. UI events raised from calculate are marshalled by handlers, not by the engine.

## Gotchas

- **Therion is a hard runtime dependency** for any calculation: if setting `therion.path` is empty, `Calculate` throws `cCalculateTherionMissingException` (cCalculate.vb:1601-1603). For headless use also mind `ExecuteTherion`'s 120 s timeout, which pops a **MsgBox** on expiry (modMain.vb:389-394) — a blocked automation run will hang on a dialog.
- Temp files go to `%TEMP%\_therion*`; in debug builds the same fixed names are reused, in release a GUID is appended; they are deleted only if setting `therion.deletetempfiles`=1 (cCalculate.vb:1606-1630, 1970-1972). The Therion log is the *only* source of loop/declination info — if parsing ever fails silently you simply get zero rings.
- One-shot setting `legacycalculation1` in shared settings flips a legacy Therion export (`TherionThExportTo_Version1`) for exactly one run, then switches itself off (cCalculate.vb:1665-1676). Legacy mode also skips the meridian-convergence back-rotation (cCalculate.vb:1762).
- `Calculate()` returns `cActionResult` and never rethrows managed exceptions — errors surface as `oResult.Exception` typed subclasses of `cCalculateException`; check `oResult.Result`. On any failure design warping is paused (`DesignWarpingState = Paused`, cCalculate.vb:700-714) and resumed on the next successful run (cCalculate.vb:666).
- Extended-elevation positions are per **connection**, not per station: reading `TrigPoint.Point.D` alone is wrong at junctions; use `Connections(other).GetPoint` (compare cPlotProfile.vb:771 vs 781 where Z comes from `.Point` but D from the connection).
- The profile X axis (D) accumulates *plan-projected* shot lengths, so vertical shots contribute 0 width; a shaft appears as a vertical line whose stations share D.
- `CalculateDataFromDesigns` (cCalculate.vb:271) runs **backwards**: it estimates LRUD sub-data for the 3D model *from the drawn map outlines* (`modDesignLRUD.GetLRFromDesign/GetUDFromDesign`). Don't confuse it with the forward pipeline; it only runs for 3D model modes Oversample/AdvancedOversample.
- Splays are fully recalculated as segments before being attached as splay projections (comment at cPlotPlan.vb:668-669); filtering (`InRange`) does not remove them, it just flags them, so consumers must check `.InRange`.
- The XVI sketch re-import inside `pCalculateSegments` (cCalculate.vb:1789-1967) silently swallows exceptions (logged only) — sketch morphing failures never fail a calculate.
- `cTrigPointCoordinate.IsEmpty` treats lat=0,long=0 as empty (cSurveyPC/Calculate/cCalculate.cTrigpointCoordinate.vb:18-23) — a survey exactly on the null island would be considered un-anchored (harmless in practice, noted in a code comment).

## Related docs

- [topodroid-import.md](topodroid-import.md) — how TopoDroid zips become `cSegment`s/sessions (the input to this engine)
- [data-model-and-file-format.md](data-model-and-file-format.md) — `cSurvey`, `cSegment`, `cTrigPoint`, sessions, file format
- [drawing-engine.md](drawing-engine.md) — how plan/profile designs, warping and sketches consume plot data
