# Core data model & file format (.csz / .csx / `_data.xml`)

All paths below are relative to the repo root (`c:/Users/Lovel.IZRK-LK-NB/Programming/cSurvey`). Line numbers refer to the state of the code at commit `0c6700b`.

## Purpose

This subsystem is the in-memory object model of a cave survey (shots, stations, sessions, caves/branches, drawings, cached calculation results) and its persistence format: a single XML document (`_data.xml`) optionally wrapped in a ZIP archive together with binary assets. Everything the application knows about a survey round-trips through this one XML document, which makes it the natural integration surface for out-of-process automation (e.g. an MCP server that builds or edits surveys without launching the WinForms app).

## Domain concepts

| Term | Meaning |
|---|---|
| **Segment** (`cSegment`) | One *shot*: a measurement from station `from` to station `to` (distance / bearing / inclination + optional LRUD). Also used, with flags, for splays, surface legs, duplicates and calibration shots. |
| **Trigpoint** (`cTrigPoint`) | A *station*. Identified by its **name** (string, e.g. `A0`, `0.1`, `0.1(1)`). Stations are derived data: they are auto-created from the station names appearing in segments (cSurveyPC/cTrigPoints.vb:103-110, called from cSurveyPC/Calculate/cCalculate.vb:590) and carry per-station metadata (entrance flag, GPS fix, note, label style). |
| **Splay** | A shot flagged `splay="1"`. Its `to` station is auto-named `basename(N)`, e.g. `0.1(1)` (cSurveyPC/cSegments.vb:314-331). Splays are always excluded from cave metrics (cSurveyPC/cSegment.vb:624). |
| **Session** | A survey trip: date + description + instrument settings (units, declination, calibrations). Segments reference sessions by string ID `yyyyMMdd_` + description lower-cased with spaces replaced by `_` (cSurveyPC/cSession.vb:198-206). |
| **Cave / Branch** | Logical grouping of segments. Caves are identified by **name**; branches form a tree inside a cave and are referenced by backslash-separated path, e.g. `Ramo 1\Ingresso` (separator constant cSurveyPC/cCaveInfoBranches.vb:8, path building cSurveyPC/cCaveInfoBranch.vb:322-328). |
| **Design** | A drawing: `plan` and `profile` are the two main designs; each has fixed layers (Base, Soil, Water, Rocks, TerrainLevel, Borders, Signs) holding vector *items* whose points can be **bound to segment GUIDs** so the drawing warps when the centerline changes. |
| **Calculate cache** | The solved network (x/y/z per station, projected per-shot line work, loop/ring info, speleometric totals) is *persisted inside the file* (`<calculate>` element and per-segment `<data>` children) so re-opening a file does not recompute (cSurveyPC/cSurvey.vb:1532-1553). |
| **Origin** | The station name anchored at coordinate (0,0,0) (`properties@origin`, cSurveyPC/cProperties.vb:266; auto-set at load if empty, cSurveyPC/cSurvey.vb:1541-1543). |

## Architecture

### File container

- **`.csz`** = ZIP archive (Ionic.Zip / DotNetZip) containing `_data.xml` plus optional binary assets under `_data\…` subfolders (`_data\design\<guid>.png` sketch/image rasters — cSurveyPC/cItemImage.vb:373-374, cSurveyPC/cItemSketch.vb:583-588; `_data\cliparts\<hash>.svg`; `_data\surface\…` DEM/orthophotos — cSurveyPC/cOrthoPhoto.vb:201; `_data\design3d\<id>\…` — cSurveyPC/cChunks3Ds.vb:375-376).
- **`.csx`** = the bare `_data.xml` (legacy format, still fully supported; TopoDroid exports this).
- `cFile` (cSurveyPC/cFile.vb:5) wraps both. Format is chosen by extension (`.csx` → CSX, everything else → CSZ; cSurveyPC/cFile.vb:66-81). On open, `cStorage` inflates **every** zip entry into a `MemoryStream` (cSurveyPC/cFile.vb:386-403), then the `XmlDocument` is loaded from the `_data.xml` entry (cSurveyPC/cFile.vb:77-79). On save, the document is serialized back into the storage and the whole zip is rewritten (cSurveyPC/cFile.vb:91-112, 340-380).

### Object graph (what hangs off the `cSurvey` root)

`cSurvey.cSurvey` (cSurveyPC/cSurvey.vb:10) is the root aggregate. Its constructor (cSurveyPC/cSurvey.vb:659-701) creates every child collection; every child gets a back-reference to the survey (`New xxx(Me)` pattern). Public accessors (cSurveyPC/cSurvey.vb:1603-1736):

```
cSurvey (ID = GUID, Version const "1.14")
├── Properties : cProperties            <properties>   name, origin, calc modes, units…
│     ├── Sessions  : cSessions         <sessions>     SortedDictionary keyed by session ID string
│     ├── CaveInfos : cCaveInfos        <caveinfos>    Dictionary keyed by cave NAME (case-insens.)
│     │     └── cCaveInfo ── Branches : cCaveInfoBranches (recursive tree of cCaveInfoBranch)
│     ├── GPS, DesignProperties, DataTables (custom user fields), CaveVisibilityProfiles, HLs
├── Segments   : cSegments              <segments>     ordered KeyedCollection keyed by segment GUID
│     └── cSegment (shot; holds cached Calculate.Plot.cData, cDataProperties "datarow", attachments)
├── TrigPoints : cTrigPoints            <trigpoints>   SortedList keyed by station NAME
├── Grades     : cGrades                <grades>       accuracy-grade definitions
├── Plan       : cDesignPlan            <plan>         drawing (layers → items → points)
├── Profile    : cDesignProfile         <profile>
├── ThreeD     : cDesign3D              <model3d>
├── CrossSections : cDesignCrossSections <crosssections>  (share segment-ID namespace, see below)
├── Sketches   : cDesignSketches        <sketches>
├── Attachments, Cliparts, Signs, Pens, Brushes        <attachments> <cliparts> <signs> <pens> <brushes>
├── Options    : cOptionsCollection     <options>      per-window paint options (_design.plan, _viewer.plan, …)
├── PreviewProfiles / ExportProfiles / ViewerProfiles  <previewprofiles> <exportprofiles> <viewerprofiles>
├── LinkedSurveys, SharedSettings, Surface, MasterSlave, Texts <txts>, ScaleRules
└── Calculate  : cCalculate             <calculate>    cached solved network
```

### How objects reference each other

Cross-references are **by string, not object pointer**, which is exactly what makes direct XML manipulation viable:

| Reference | Key | Example |
|---|---|---|
| segment → stations | station **name** in `from`/`to` | `from="A0" to="A1"` |
| segment → session | session ID string `yyyyMMdd_desc` | `session="20111119_sessione_a"` |
| segment → cave / branch | cave **name** + branch **path** (`\`-separated) | `cave="Grotta" branch="Ramo 1\Ingresso"` |
| design point → segment | segment **GUID** embedded in the `points@data` stream (`S<guid>` token) | see schema below |
| design item → cave/branch | name/path strings on the `<item>` | `cave="Grotta" branch="Ramo 1"` |
| image/sketch item → stations | trigpoint **name** in `<station trigpoint="A6">` | anchors raster warping |
| trigpoint → neighbours | `<connections v="A0;A2">` (names, `;`-separated) | derived, rebuilt on Rebind |
| item → raster payload | zip path string | `image="_data\design\<guid>.png"` |

Segment GUIDs are the only synthetic IDs used as cross-reference keys (caveinfos/grades also carry GUID `id` attributes, but nothing references them by it); they are generated when missing (cSurveyPC/cSegment.vb:651-652). `cSurvey.GetSegment(ID)` looks first in `Segments`, then in `CrossSections` (cSurveyPC/cSurvey.vb:1585-1595) — cross-sections and shots share one ID namespace so drawing items can bind to either.

### The universal (de)serialization pattern

There is no reflection/attribute-based serializer. **Every persisted class follows one hand-written convention**:

- a `Friend Sub New(Survey As cSurvey, [File As cFile,] Element As XmlElement)` constructor that reads attributes via `modXML.GetAttributeValue(node, name, default)` (cSurveyPC/modXML.vb:84-90) and recursively constructs children;
- a `Friend Function SaveTo(File As cFile, Document As XmlDocument, Parent As XmlElement, [Options]) As XmlElement` that creates its element, sets attributes (**omitting default values**), calls children's `SaveTo`, and appends itself to `Parent`.

Numbers are written with `modNumbers.NumberToString` — **InvariantCulture, default format `"0.00"`** (cSurveyPC/modNumbers.vb:85-127). Parsing is asymmetric: `StringToDouble`/`StringToSingle`/`StringToInteger` are strictly invariant (cSurveyPC/modNumbers.vb:137-166, 200-209), but `StringToDecimal` (cSurveyPC/modNumbers.vb:228-236) replaces `.` with the *current locale's* decimal separator and parses in the current culture — and shot `distance`/`bearing`/`inclination` go through `StringToDecimal` (cSurveyPC/cSegment.vb:657-659). Always write `.` decimals; they parse correctly everywhere. Colors are ARGB integers (cSurveyPC/modXML.vb:92-98). Booleans are `"1"`/`"0"` (attribute absent = false). Ranges use `;` (e.g. `plansplayborderinclinationrange="-90;90"`, cSurveyPC/cSegment.vb:702).

The same serializers feed the **undo system**: undo entries store `XmlElement` snapshots of segments/trigpoints/design items (cSurveyPC/cUndo.vb:102-193), and clipboard/import use `SaveOptionsEnum.ForClipboard/ForImport` (cSurveyPC/cSurvey.vb:63-69).

### Data-flow narrative

**Open**: `frmMain` → `cSurvey.Load(filename)` → `cFile` unzips & parses XML → (TopoDroid fixup if `properties@creatid="topodroid"` and not `creat_postprocessed`, cSurveyPC/cSurvey.vb:943-945) → version-upgrade loop mutates the DOM up to `Version` (cSurveyPC/cSurvey.vb:951-1242) → child collections constructed from root child elements → if `<calculate>` present, cached results are trusted and nothing is recomputed; otherwise a full `Calculate` runs (cSurveyPC/cSurvey.vb:1532-1553).

**Edit**: mutating a segment sets `Changed`/`Invalidated` flags; collection events bubble to `cSurvey.OnSegmentsChange` and OR `iInvalidated` with `FullCalculate` (cSurveyPC/cSurvey.vb:1884-1924). Recalculation (manual or automatic per `properties@calculatemode`) recomputes station x/y/z and per-segment projected data, then `TrigPoints.Rebind()` creates/orphans stations (cSurveyPC/Calculate/cCalculate.vb:590).

**Save**: `cSurvey.SaveTo(filename)` → `pSaveTo` builds a fresh `<csurvey version id>` root and calls each child's `SaveTo` in fixed order (cSurveyPC/cSurvey.vb:1781-1862) → `cFile.Save` rewrites `_data.xml` + assets into the zip.

## Key classes & files

| File | Class | Responsibility |
|---|---|---|
| cSurveyPC/cSurvey.vb | `cSurvey.cSurvey` | Root aggregate; `Load`/`SaveTo`; file-version upgrade chain; invalidation bookkeeping; global enums (`CalculateTypeEnum`, `SplayModeEnum`, …) |
| cSurveyPC/cFile.vb | `cFile`, `cStorage`, `cStorageItemFile` | .csz/.csx container; Ionic.Zip in-memory storage of `_data.xml` + binary assets |
| cSurveyPC/modXML.vb | `modXML` | Attribute helpers (`GetAttributeValue`, `ChildElementExist`, `GetAttributeColor`, `RenameElement`) |
| cSurveyPC/modNumbers.vb | `modNumbers` | Invariant-culture number ⇄ string (the file format's number convention) |
| cSurveyPC/cSegment.vb | `cSegment` (+ inner `cData` struct) | One shot: from/to/distance/bearing/inclination/LRUD + flags; XML ctor at :648, `SaveTo` at :745 |
| cSurveyPC/cSegments.vb | `cSegments` | Ordered shot list keyed by GUID; load loop :188; splay auto-naming :308-331; TopoDroid DistoX custom fields :191-208 |
| cSurveyPC/cSegmentCollection.vb | `cSegmentBaseCollection` | `KeyedCollection(Of String, cISegment)` keyed by `ID` (:6-12) |
| cSurveyPC/Calculate/cCalculate.Plot.cData.vb | `Calculate.Plot.cData` | Per-segment cached calc results (`srcdata`/`olddata`/`data`/`planpd`/`profilepd`/`sds`), warping factors; XML ctor :340 |
| cSurveyPC/cTrigPoint.vb | `cTrigPoint` | Station metadata; XML ctor :399, `SaveTo` :547 |
| cSurveyPC/cTrigPoints.vb | `cTrigPoints` | Station registry keyed by name; `Rebind` derives stations from segments :103-150 |
| cSurveyPC/cSession.vb | `cSession`, `cCalibration` | Trip settings/units/declination; ID derivation :198-206; `SaveTo` :479 |
| cSurveyPC/cSessions.vb | `cSessions` | `SortedDictionary(Of String, cSession)` (:8) |
| cSurveyPC/cCaveInfo.vb, cCaveInfos.vb | `cCaveInfo`, `cCaveInfos` | Cave registry by name; XML ctor cCaveInfo.vb:393 |
| cSurveyPC/cCaveInfoBranch.vb, cCaveInfoBranches.vb | `cCaveInfoBranch(es)` | Recursive branch tree; `\` path separator |
| cSurveyPC/cProperties.vb | `cProperties` | The `<properties>` element: identity, origin, calculation & unit modes; XML ctor :1021, `SaveTo` :1168 |
| cSurveyPC/cDataProperties.vb | `cDataProperties`, `cDataFields`, `cDataField` | User-defined columns (`datatables` definitions + per-object `<datarow>` pipe-separated values :69-102, :152-164) |
| cSurveyPC/cGrade.vb, cGrades.vb | `cGrade(s)` | Accuracy-grade definitions (`<grades><grade …>`) |
| cSurveyPC/cPoints.vb, cPoint.vb | `cPoints`, `cPoint` | Design item geometry; compact `points@data` string codec (Parse :496, SaveTo :626) |
| cSurveyPC/cUndo.vb | `cUndo*` (Namespace `cSurvey.Helper.Editor`) | Undo/redo via XML snapshots of segments/trigpoints/design items |
| cSurveyPC/cISurveyInfo.vb | `cISurveyInfo` | Tiny interface (Club/Note/Team/Designer) shared by properties & sessions |

## `_data.xml` schema map

Verified against `dev/example/Demo Survey/survey_1.csz` (v1.04, minimal), `survey_6.csz` (v1.04, full drawing), `dev/example/buless.csz` (v1.11, 316 shots incl. 267 splays, cross-sections, surface) and the serializers cited above. The version-upgrade chain rewrites old files to the current layout at load, so writing files in the current layout with `version="1.14"` is always safe.

```xml
<csurvey version="1.14" id="{guid}">              <!-- cSurvey.vb:1786-1788 -->

  <properties id="ER RN 864" name="Grotta del Buless"
      club=".." team=".." author=".." designer=".." note=".."
      defgrade=".." defaccuracy=".."
      creatid="topodroid" creatversion=".." creatdate="ISO" creat_postprocessed="1"
      origin="0.0"                       <!-- station name anchored at (0,0,0) -->
      calculatemode="1"                  <!-- 0 Manual, 1 Automatic (cSurvey.vb:104) -->
      calculatetype="2"                  <!-- 0 None, 1 Internal, 2 Therion (cSurvey.vb:114) -->
      calculateversion="2"
      ringcorrectionmode="2"             <!-- loop closure: 0 None, 1 Dummy, 2 Simple (cSurvey.vb:125) -->
      nordcorrectionmode="0"             <!-- 0 None, 1 DeclinationBySession (cSurvey.vb:120) -->
      inversionmode="1"                  <!-- 0 Relative (legacy), 1 Absolute -->
      designwarpingmode="1"              <!-- 0 None, 1 Default -->
      dataformat=".." distancetype=".." bearingtype=".." inclinationtype=".."
      declination=".." declinationenabled=".." splaymode=".." bindcrosssection="1"
      threed*=".." surfaceprofile*=".." historyenabled=".." slpeo="1">
                                         <!-- full list: cProperties.vb:1168-1267 -->
    <sessions>                           <!-- cSessions.vb:254 -->
      <session date="2015-05-13T00:00:00.0000000" description="Squadra FSRER"
          club=".." team=".." designer=".." note=".." color="argb"
          dataformat="0"                 <!-- 0 tape/clino/compass, 1 Cartesian, 2 Diving, 3 Cylpolar (cSegment.vb:319) -->
          distancetype="0"               <!-- 0 m, 1 ft, 2 yd (cSegment.vb:112) -->
          bearingtype="0" bearingdirection="0" inclinationtype="0" inclinationdirection="0"
          depthtype="0" grade=".."
          nordtype="0"                   <!-- 0 Magnetic, 1 Geographic (cSegment.vb:348) -->
          declinationenabled="0" declination="0.00"
          sidemeasurestype=".." sidemeasuresreferto=".." vthreshold=".." vthresholdenabled="1"/>
          <!-- optional child calibration elements with e / es attrs (cSession.vb:39-43) -->
    </sessions>
    <caveinfos>                          <!-- cCaveInfos.vb:239 -->
      <caveinfo id=".." name="ACQUACIOCCA" description=".." color=".." locked=".." extstart=".." pty=".." op="..">
        <branches>
          <branch name="Ramo 1" color="-32768">   <!-- recursive; cCaveInfoBranch.vb:238-255 -->
            <branches><branch name="Ingresso"><branches/></branch></branches>
          </branch>
        </branches>
      </caveinfo>
    </caveinfos>
    <cavevisibilityprofiles/>
    <gps refpointonorigin="1" format="dd mm ss.ss N"/>
    <designproperties>                   <!-- typed name/value items -->
      <item name="baselinewidthscalefactor" type="Decimal">0.01</item>
      <item name="designtextfont" type="cFont"><font color="-16777216" fontname="Tahoma" fontsize="8"/></item>
      <!-- ~42 items -->
    </designproperties>
    <datatables>                         <!-- custom user-field definitions (cDataProperties.vb) -->
      <segments/> <trigpoints/> <designitems/>   <!-- each holds <datafield name type category …> -->
    </datatables>
  </properties>

  <grades> ... </grades>                 <!-- only if defined; <grade id description distance(…) bearing(…) …> (cGrade.vb:324-406) -->
  <txts/>  <attachments/>                <!-- optional -->

  <segments>                             <!-- ONE ELEMENT PER SHOT, document order = data-entry order -->
    <segment id="{guid}" from="0.1" to="0.1(1)"
        distance="1.00" bearing="33.10" inclination="-14.33"   <!-- units per session/properties; degrees, meters by default -->
        l="1.02" r="0.89" u=".." d=".."  <!-- LRUD, omitted when 0 (cSegment.vb:756-759) -->
        splay="1" duplicate="1" surface="1" calibration="1" exclude="1"  <!-- flags, omitted when false -->
        cut="1" zsurvey="1" virtual="1" unbindable="1"
        direction="0"                    <!-- profile extend: 0 Right, 1 Left, 2 Vertical (cSurvey.vb:71) -->
        color="argb" note=".."
        cave="ACQUACIOCCA" branch="Ramo principale" session="20150513_squadra_fsrer"
        plansplay*=".." profilesplay*=".."   <!-- splay-border tuning (cSegment.vb:699-707) -->
        hiddenindesign="1" hiddeninpreview="1"
        g=".." m=".." dip=".." distox=".."   <!-- raw TopoDroid extras, absorbed into datarow at load (cSegment.vb:735-740) -->
        >
      <data>                             <!-- CACHED calculation (Calculate.Plot.cData.vb:355-375); safe to omit entirely -->
        <srcdata st="0.1(1)" sf="0.1" d="1.00" i="-14.33" b="33.10" dr="0" [r="1"]/>  <!-- as-entered -->
        <olddata …/> <data …/>           <!-- corrected values after loop closure / declination -->
        <planpd …/> <profilepd …/>       <!-- projected 2D line + splay-border endpoints -->
        <sds/>                           <!-- subdata (LRUD interpolation) -->
      </data>
      <datarow>val|val|…</datarow>       <!-- pipe-separated custom-field values, positional (cDataProperties.vb:152-164) -->
    </segment>
  </segments>

  <trigpoints>                           <!-- stations; regenerable from segments via Rebind -->
    <trigpoint name="A0" entrance="2" type=".." labelsymbol="0" labelposition=".." note=".."
               isinexploration="1" issystem="1" isspecial="1" zturn="1">
      <aliases/>                         <!-- optional -->
      <connections v="A1;A2"/>           <!-- derived neighbour list -->
      <coordinate latv="44.4274962" longv="11.4103341" altv="224.00"
                  lat="44,4274962° N" long=".." format="dd.ddddddd N" alt="224"/>  <!-- GPS fix -->
      <data x="0" y="0" z="0"/>          <!-- CACHED computed position, meters from origin -->
      <datarow>…</datarow>
    </trigpoint>
  </trigpoints>

  <options>                              <!-- per-context paint options, one child per context -->
    <_design.plan drawsplay=".." drawlrud=".." designstyle=".." …>   <!-- ~37 attrs -->
      <infoboxoptions/><compassoptions/><scaleoptions/><translationsoptions/><surfaceoptions/>
    </_design.plan>
    <_design.profile/> <_design.3d/> <_viewer.plan/> <_viewer.profile/>
    <_preview.plan pageformat=".." scale=".."/> <_preview.profile/>
    <_export.plan fileformat=".." dpix=".." imagewidth=".."/> <_export.profile/>
  </options>

  <cliparts/> <signs/> <pens/> <brushes/>   <!-- galleries; SVG payloads in _data\cliparts\<hash>.svg -->

  <plan>                                 <!-- THE PLAN DRAWING (same structure for <profile>) -->
    <layers>
      <layer name="Base" type="0">       <!-- fixed layer types 0..6: Base, Soil, Water, Rocks, TerrainLevel, Borders, Signs -->
        <items>
          <item layer="0" cave="Grotta" branch="Ramo 1" type="3" category="48" linetype="1">
            <pen type="0"/> <brush type="3"/>
            <points data="-14.58 1.04 BSa9f77a07-… -14.73 1.12 S -14.92 1.19 S … "/>
          </item>
          <!-- raster sketch item (e.g. imported TopoDroid sketch): -->
          <item type="11" category="113" imageid="{guid}" designimageid="{guid}"
                image="_data\design\{guid}.png" designimage="_data\design\{guid}.png" morphingdisabled="1">
            <points data="-34.15 -14.16 -8.98 12.78 "/>       <!-- bounds -->
            <stations><station x="270" y="255" trigpoint="A6"/>…</stations>  <!-- pixel→station anchors -->
          </item>
        </items>
      </layer>
    </layers>
    <pointsjoins/>  <plot/>
  </plan>
  <profile> … </profile>
  <model3d/> 

  <crosssections>                        <!-- cross-section pseudo-segments; share segment-ID namespace (cSurvey.vb:1585) -->
    <crosssection id="{guid}" crosssection="36" planmarker="4" profilemarker="4"><data>…</data></crosssection>
  </crosssections>

  <sketches/> <scalerules/> <previewprofiles/> <exportprofiles/> <viewerprofiles/> <linkedsurveys/>
  <sharedsettings><values selectedcave=".." plan.selectedcave=".." …/></sharedsettings>
  <surface/> <masterslave/>

  <calculate>                            <!-- CACHED solved network (cCalculate.vb:126); delete to force full recompute at load -->
    <ts>                                 <!-- one <t> per station (cCalculate.cTrigpoints.vb:196) -->
      <t n="A0">
        <tcon n="A1" dst="5.60"/> <tcons/>
        <p x="0" y="0" z="0.0000" d="0"/>            <!-- solved position, meters -->
        <coord alt="224.0000" lat="44.42749…" lon="11.41033…"/>
        <sm><smlrs/><smuds/></sm>                    <!-- side measures -->
      </t>
    </ts>
    <rngs aep=".."/>                     <!-- loop/ring data -->
    <mdd mc=".."/>                       <!-- geomagnetic declination cache -->
    <sms><sm pl=".." l=".." ml=".." e=".." sc=".." xsc=".." pvr=".." nvr=".."/></sms>  <!-- speleometrics -->
  </calculate>
</csurvey>
```

### The `points@data` grammar (how drawings bind to the centerline)

Design item geometry is a single space-separated string (`cPoints.Parse`, cSurveyPC/cPoints.vb:496-618; writer :626-667). Token stream per point: `X Y [flags]` where the optional flags word is a concatenation of:

- `B` — begins a new sub-sequence (a new stroke inside the same item);
- `P` — this stroke has an inline `<pen>` child element (consumed in order);
- `T<digit>` — line type override (`LineTypeEnum`: 0 Lines, 1 Splines, 2 Beziers, cSurveyPC/cIItemLine.vb:3-8);
- `L` — point's segment binding is locked;
- `S[<segment-guid>]` — **point is bound to that centerline segment**; a bare `S` repeats the previous GUID.

Example: `-14.58 1.04 BSa9f77a07-9cd0-46bb-8b11-8d09637dbf67 -14.73 1.12 S …` = start stroke, both points bound to segment `a9f77…`. Coordinates are world meters in the design plane (same space as the computed station positions), X east / Y in the plot's screen convention (inferred from matching `planpd` coordinates). This binding is what design warping uses to morph drawings when shots are edited (warping factors in cSurveyPC/Calculate/cCalculate.Plot.cData.vb:38-338).

### Shot field reference (complete)

From the `cData` struct (cSurveyPC/cSegment.vb:20-50), XML ctor (:648-743) and `SaveTo` (:745-808):

| XML attr | Field | Type / unit | Notes |
|---|---|---|---|
| `id` | ID | GUID string | generated if absent |
| `from`, `to` | From, To | station names | splay `to` is `name(N)` |
| `distance` | Distance | Decimal, meters (default; `distancetype` can select ft/yd) | tape length |
| `bearing` | Bearing | Decimal, decimal degrees 0–360 (or centesimal per `bearingtype`) | compass |
| `inclination` | Inclination | Decimal, decimal degrees −90…+90 (or centesimal/%) | clino |
| `l r u d` | Left/Right/Up/Down | Decimal, distance units | LRUD at the shot; omitted when 0 |
| `splay` | Splay | bool | forces `exclude` (cSegment.vb:624) |
| `duplicate` | Duplicate | bool | counted once in metrics; forces `exclude` |
| `surface` | Surface | bool | surface leg; forces `exclude` |
| `calibration` | Calibration | bool | instrument-calibration shot; forces `exclude` |
| `exclude` | Exclude | bool | excluded from cave metrics |
| `cut` | Cut | bool | "cut splay"; forces `splay` + `exclude` (:581-584) |
| `zsurvey` | ZSurvey | bool | part of a zig-zag centerline; clears splay/cut (:595-610) |
| `virtual` | Virtual | bool | virtual/system shot |
| `unbindable` | UnBindable | bool | design items may not bind to it |
| `direction` | Direction | 0 Right / 1 Left / 2 Vertical | extended-profile direction (legacy `inverted` bool auto-converted, :668-673) |
| `color` | — | ARGB int | per-shot color |
| `cave`, `branch` | Cave, Branch | name / `\`-path | |
| `session` | Session | session ID string | `"00010101_"` sentinel → `""` (:694) |
| `note` | — | string | |
| `plansplayprojectiontype`, `plansplaydeltaz`, `plansplaymaxdeltavariation`, `plansplayborderinclinationrange`, `profilesplayborderprojectionangle`, `profilesplaybordermaxanglevariation`, `profilesplayborderposinclinationrange`, `profilesplayborderneginclinationrange` | splay-border tuning | numbers / `min;max` pairs | control how splays become auto walls |
| `surfaceprofileshow`, `hiddenindesign`, `hiddeninpreview` | visibility | enum/bool | |
| `g m dip distox` | — | TopoDroid raw sensor values | moved into custom `datarow` fields at load (:735-740) |

### File-format versioning & backward compatibility

- Current version constant: `"1.14"` (cSurveyPC/cSurvey.vb:11); written on every save (:1787). Version `"-1"` is accepted as-is: it means "generated by external software without calculate data" (:953) — useful for generators that don't want to emit the cache.
- `cSurvey.Load` runs a stepwise in-DOM upgrade chain 1.00→1.14 (cSurveyPC/cSurvey.vb:951-1242), raising `OnFileConversionRequest` once (cancellable). Substantive rewrites: 1.00→1.01 `direction`→`bearing` + `inverted`→`direction`; 1.01→1.02 `sx/dx/top/bottom`→`l/r/u/d`; 1.02→1.03 `grade/accuracy`→`defgrade/defaccuracy`; 1.03→1.04 remaps `linetype`/`binddesigntype` values on all design items. 1.05–1.14 are essentially feature-marker bumps (only 1.07→1.08 touches the DOM: it stamps `properties@slpeo="1"`, cSurveyPC/cSurvey.vb:1162). Unknown versions fail the load (:1237-1241).
- Old per-point design XML (child `<point>` elements instead of `points@data`) is still parsed (cSurveyPC/cPoints.vb:610-616).
- Missing sections never fail: most children are constructed inside `Try/Catch` with an empty fallback (cSurveyPC/cSurvey.vb:1253-1530). Exceptions loaded **unguarded** (an exception there aborts the load): `<segments>` (:1296), `<trigpoints>` (:1299-1303), `<plan>` (:1386-1390), `<profile>` (:1395-1399), `<model3d>` (:1404-1408).

## Key flows

### 1. Loading a .csz (`cSurvey.Load`)

1. cSurveyPC/cSurvey.vb:940 — `New cFile(Filename)`; cFile.vb:74-79 unzips everything into memory and parses `_data.xml` into an `XmlDocument`.
2. cSurveyPC/cSurvey.vb:943-945 — if `properties@creatid="topodroid"` and not `creat_postprocessed` (or `LoadOptionsEnum.FixTopoDroid`), `modImport.FixTopodroidCSX(oXml)` rewrites the DOM (see [topodroid-import.md](topodroid-import.md)).
3. cSurveyPC/cSurvey.vb:950-1242 — version detected via `csurvey@version` (:1763-1769) and upgraded step-by-step in the DOM.
4. cSurveyPC/cSurvey.vb:1245-1530 — child objects constructed from root children in order: grades, properties, txts, attachments, **segments** (:1296), **trigpoints** (:1299), options, crosssections, sketches, cliparts, signs, pens, brushes, **plan** (:1387), **profile** (:1396), model3d, crosssection/sketch rebind, scalerules, preview/export/viewer profiles, linkedsurveys, sharedsettings, surface, masterslave.
5. cSurveyPC/cSurvey.vb:1532-1553 — `<calculate>` present → cached `cCalculate` loaded, `iInvalidated = None`; absent → `Invalidate()` + `oCalc.Calculate(False)`.
6. cSurveyPC/cSurvey.vb:1566-1570 — post-load TopoDroid fixups on plan/profile designs and survey.

### 2. Saving (`cSurvey.SaveTo` → `pSaveTo`)

1. cSurveyPC/cSurvey.vb:1875-1882 — format from extension (`.csx` → CSX else CSZ), `New cFile(format, filename)`.
2. cSurveyPC/cSurvey.vb:1786-1788 — fresh `<csurvey version="1.14" id="…">` element.
3. cSurveyPC/cSurvey.vb:1790-1857 — each child's `SaveTo(File, Document, root, Options)` in fixed order; empty optional collections skipped (`If … .Count <> 0`); cross-sections/sketches `Rebind(True)` before saving (:1835-1843); `oCalc.SaveTo` last (:1857) so the cache is always persisted.
4. cSurveyPC/cFile.vb:91-101 — `_data.xml` entry replaced in the storage, zip rewritten via `Ionic.Zip.ZipFile.Save` (:359-380). Binary assets were written by their owners during step 3 (e.g. cSurveyPC/cItemImage.vb:373-374).

### 3. Shot entered/edited → recalculation

1. `cSegments.Append()` (cSurveyPC/cSegments.vb:260-282) creates `cSegment`, hooks `OnChange`/`OnSplayChange`/`OnGetSplayName` handlers, raises `OnSegmentAppend`.
2. cSurveyPC/cSurvey.vb:1884-1889 — root handler ORs `iInvalidated` with `cCalculate.InvalidateEnum.FullCalculate` and re-raises `OnSegmentsChange` for the UI.
3. Property setters on `cSegment` write to `oTempData` and set `bChanged` (e.g. `Splay`, cSurveyPC/cSegment.vb:617-628); `cSegments.SaveAll` commits (cSurveyPC/cSegments.vb:127-144).
4. On calculate, station coordinates and per-segment `planpd`/`profilepd` are recomputed and `TrigPoints.Rebind()` auto-creates stations for new names / orphans removed ones (cSurveyPC/Calculate/cCalculate.vb:590, cSurveyPC/cTrigPoints.vb:103-150).

### 4. A design point binds to the centerline

1. On item load, `cPoints.Parse` decodes `points@data`, capturing `S<guid>` into `sBindedSegment` per point (cSurveyPC/cPoints.vb:594-601).
2. `cPoint.BindedSegment` lazily resolves the GUID via `oSurvey.GetSegment(id)` — segments first, then cross-sections (cSurveyPC/cPoint.vb:666-673, cSurveyPC/cSurvey.vb:1585-1595).
3. When calculation changes a bound segment, warping matrices from old→new segment geometry (`cPlanWarpingFactor.GetMatrix`, cSurveyPC/Calculate/cCalculate.Plot.cData.vb:58-89) transform the item's points.

## How to modify safely

- **Preserve the "omit defaults" convention.** Readers use `GetAttributeValue(…, default)`; writers must only emit non-default attributes, otherwise old-version diff-based tools and the upgrade chain assumptions break.
- **Never change the meaning of an existing attribute — add a new one and bump `cSurvey.Version`**, adding a `Case` to the upgrade chain in `Load` (cSurveyPC/cSurvey.vb:951-1242) even if it's a proforma bump; that is how every 1.05+ change was done.
- **Keep string keys stable**: renaming a station must go through `cTrigPoints.RenameTrigPoint` (updates segments/connections, cSurveyPC/cTrigPoints.vb:209+); renaming caves/branches through `cSegment.RenameCave` (cSurveyPC/cSegment.vb:816-826) — direct attribute edits desynchronize segments, design items (`item@cave/@branch`) and cave registry.
- **Respect flag coupling** when writing segments externally: `cut ⇒ splay ⇒ exclude`, `surface/duplicate/calibration ⇒ exclude`. The loader re-enforces it (cSurveyPC/cSegment.vb:684-685), so files violating it get silently corrected — but your tool's view then diverges from cSurvey's.
- **Invariant culture, `.` decimals, `;` pair separator, ARGB ints, ISO-8601 round-trip dates** (`date.ToString("O")`, cSurveyPC/cSession.vb:481). Comma-decimal input silently parses as `0` for Single/Double fields (invariant `TryParse`, cSurveyPC/modNumbers.vb:146, 166); Decimal fields (incl. distance/bearing/inclination) use the culture-dependent `StringToDecimal` (cSurveyPC/modNumbers.vb:228-236), which can *misread* comma-formatted numbers on dot-decimal locales — never emit them.
- **Segment order matters**: document order is data-entry order and drives calculation traversal and the UI grid; insert, don't sort.
- If you edit shots in `_data.xml` out-of-process, either also update the cached `<calculate>` + per-segment `<data>` blocks (hard) or **delete the root `<calculate>` element** so cSurvey recomputes on load (cSurveyPC/cSurvey.vb:1533-1539); per-segment `<data>` children may simply be omitted (cSurveyPC/cSegment.vb:714-718).

## Gotchas

- `cSurvey.Check` refuses files whose `inversionmode ≠ 1 (Absolute)` unless Shift+Ctrl is held at open (cSurveyPC/cSurvey.vb:902-907), and files with Therion calculatetype when `therion.path` isn't configured (:895-901). Note :895 reads attribute `calculatemode` into a `CalculateTypeEnum` — the enum check actually keys off the wrong attribute name (`calculatemode` is Manual/Automatic; the Therion value lives in `calculatetype`).
- The whole zip is inflated into `MemoryStream`s on open (cSurveyPC/cFile.vb:396-399) — multi-hundred-MB surveys cost that much RAM twice during save.
- Loading is exception-tolerant per section (empty fallback in `Catch`), so a syntactically-valid but semantically-broken section can silently vanish on next save. Load errors in `<segments>`, `<trigpoints>`, `<plan>`, `<profile>` and `<model3d>` are fatal (no `Try/Catch`, see above).
- `session="00010101_"` is a legacy null sentinel (cSurveyPC/cSegment.vb:694). Session IDs contain the lower-cased description — renaming a session changes its ID, which is why `cSessions` exposes dedicated rename plumbing (cSurveyPC/cSession.vb:214-230).
- Trigpoint `<data x y z>` and `<connections>` are caches; hand-written files can omit `<trigpoints>` entirely — stations materialize via `Rebind` after the first calculation (cSurveyPC/cTrigPoints.vb:103-110). But entrance flags/GPS fixes live on trigpoints, so those must be written if you need georeferencing.
- A `.csz` may or may not contain `_data\` directories (survey_1 has only `_data.xml`); code never assumes their presence.
- `cSegments` is keyed by GUID via `KeyedCollection` — **duplicate segment IDs throw on load**. TopoDroid exports had ID collisions, which is one reason `FixTopodroidCSX` regenerates segment IDs (cSurveyPC/cSurvey.vb:943-945, `modOpeningFlags.OFRegenerateSegmentsID`).
- Undo snapshots are XML (cSurveyPC/cUndo.vb:102-193): if you add a field to a serializer, undo/redo of old snapshots silently drops it unless the XML ctor defaults are sensible.
- `properties@origin` empty → `AutoSetOrigin` picks one at load (cSurveyPC/cSurvey.vb:1541-1543); don't rely on a specific origin unless you set it.

## Related docs

- [topodroid-import.md](topodroid-import.md) — how TopoDroid zips/csx get converted into this model (`modImport.FixTopodroidCSX/FixTopodroidDesign/FixTopodroidSurvey`, cSurveyPC/modImport.vb:330-384).
- [calculation-engine.md](calculation-engine.md) — how `cCalculate` solves the network whose cache is described here. *(if present)*
- [drawing-engine.md](drawing-engine.md) — the design/item/layer model whose anchoring is summarized here. *(if present)*
