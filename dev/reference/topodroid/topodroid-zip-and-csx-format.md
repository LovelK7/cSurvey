# TopoDroid-side formats: project .zip internals and the csx it exports

## Purpose

This doc grounds the *TopoDroid side* of the TopoDroid→cSurvey pipeline: what is actually inside a TopoDroid project `.zip` (manifest, `survey.sql`, `.tdr` sketch binaries, media), the on-phone SQLite schema those files serialize, and — element by element — the exact `.csx` XML that TopoDroid's exporter writes and cSurvey then ingests. It exists so the planned zip→csx pre-converter ([mcp-blueprint.md](../mcp-blueprint.md) Stage 4) and any test fixture can be built from verified format knowledge instead of guesses; every other doc in this set only covers the cSurvey (receiving) side.

**Source pinning:** citations of the form `TD:<path>:<line>` refer to the official TopoDroid repository <https://github.com/marcocorvi/topodroid>, `master` branch at commit `b0b28552ff80a74e2918fc12d23d7ffa5768454a` (2026-07-10). All TopoDroid files cited were downloaded and read at that commit. `cSurveyPC/...` citations are this repo, as usual.

## Domain concepts

- **TopoDroid project zip** — TopoDroid's own survey backup/interchange archive ("Export → ZIP"). It is *not* a cSurvey format and cSurvey cannot open it; only TopoDroid itself re-imports it (`TD:src/com/topodroid/inport/ImportZipTask.java:50-75`). One zip = one survey.
- **`manifest`** — a 4-line plain-text file, the mandatory *first* entry of the zip (`TD:src/com/topodroid/TDX/Archiver.java:439`).
- **`survey.sql`** — a text dump of the survey's rows from the phone database. Despite the name it is **not valid SQL and is not fed to SQLite**: it is written by hand-rolled `PrintWriter.format` calls (`TD:src/com/topodroid/TDX/DataHelper.java:6951-7270`) and read back by a hand-rolled `Scanline` parser (`TD:src/com/topodroid/TDX/DataHelper.java:7283+`).
- **`distox14.sqlite`** — the on-device SQLite database holding *all* surveys. It never travels inside the zip; the zip carries only the one-survey `survey.sql` dump of it.
- **`.tdr`** — TopoDroid's binary sketch file, one per plot (plan, extended profile, each x-section), written with Java `DataOutputStream` records (`TD:src/com/topodroid/TDX/DrawingIO.java:1243-1322`). Zip entry names are `<survey>-<plotname>.tdr` (`TD:src/com/topodroid/TDX/TDPath.java:537`).
- **Plot** — a row of the `plots` table; `type` distinguishes plan (1), extended profile (2), and x-sections (0 = station X-section from plan, 3 = horizontal leg section, 5 = vertical leg section, 7 = station X-section from profile), plus projected profile (8) (`TD:src/com/topodroid/types/PlotType.java:23-33`).
- **DBlock / leg / splay** — a `shots` table row. Legs have both `fStation` and `tStation`; splays have exactly one; rows with neither are repeated-measurement legs averaged into the previous leg (`TD:src/com/topodroid/TDX/TDExporter.java:484-617`).
- **extend** — TopoDroid's per-shot extended-elevation direction: −1 left, 0 vertical, 1 right, 2 ignore… (`TD:src/com/topodroid/TDX/TDExporter.java:90-91`). Exported to csx as the `direction` attribute via lookup `csurvey_extend = {1, 2, 0, ...}` indexed by `1+extend` (`TD:src/com/topodroid/TDX/TDExporter.java:92,497`) — matching cSurvey's `DirectionEnum` Right=0 / Left=1 / Vertical=2 (cSurveyPC/cSurvey.vb:71-75).
- **Scene vs world coordinates** — tdr files store *scene* pixels; csx stores *world* meters. Conversion: `world = (scene − CENTER) / 20` with `CENTER_X=100, CENTER_Y=120`, `SCALE_FIX=20` px/m (`TD:src/com/topodroid/TDX/DrawingUtil.java:26-28,77-83`). Y is positive-down in both.
- **"TCsx"** — TopoDroid's internal name for the *current* csx sketch encoding: flat `<item type="line|area|point" name="<therion-symbol>">` children of `<plan>`/`<profile>` (`toTCsurvey` methods). The retired original encoding ("Csx", cSurvey-layer-based `<layers><layer type="n"><items>`) survives only as commented-out code (`TD:src/com/topodroid/TDX/DrawingPointPath.java:589-614`) and as the empty-sketch skeleton (see Gotchas).

## Architecture

There are two disjoint phone→PC paths, and only one of them is readable by cSurvey today:

1. **Project zip** (full-fidelity backup): `Archiver.archiveSurvey` zips manifest + `survey.sql` + note + `.tdr` plots + media (`TD:src/com/topodroid/TDX/Archiver.java:406-516`). Contains everything (raw sensor values, deleted plots, media, custom symbols) but in TopoDroid-private formats.
2. **csx export** (lossy, cSurvey-ready): `TDExporter.exportSurveyAsCsx` renders the survey plus the *live in-memory* plan/profile drawings into one cSurvey XML (`TD:src/com/topodroid/TDX/TDExporter.java:269-674`). Note the sketch part is generated from the open `DrawingCommandManager`s (`PlotSaveData.cm`, `TD:src/com/topodroid/TDX/PlotSaveData.java:25`), not by parsing `.tdr` files — except embedded x-sections, which *are* read from their `.tdr` file at export time (`TD:src/com/topodroid/TDX/DrawingPointPath.java:687-694`).

A **zip→csx pre-converter** therefore has to re-implement path 2 from the artifacts of path 1: unzip (flat entries) → parse `manifest` (compatibility gate) → parse `survey.sql` (shots/plots/fixeds rows) → walk shots with the leg/splay state machine → parse the plan and extended-profile `.tdr` files → flatten beziers, convert scene→world coordinates → emit the csx skeleton below. cSurvey's own fix-up chain (GUID regeneration, uppercasing, item conversion, `BindSegments`) then does the rest on load — see [topodroid-import.md](topodroid-import.md).

Data-flow of the csx export itself (all `TD:src/com/topodroid/TDX/TDExporter.java`): survey info → `<properties>` incl. `<note>` from the note file (:359-399) → one `<session>` from survey date/team/declination (:406-420) → `<caveinfo>` named after the survey with one branch per plan-plot name (:427-440) → `<gps refpointonorigin>` if any fixed point exists (:443-446) → `<segments>` from the shot list (:452-639) → `<trigpoints>` from fixeds (:643-652) → `<plan>`/`<profile>` items via `DrawingWindow.exportAsCsx` (:657) → done. cSurvey reads it back through `cSurvey.Load` (cSurveyPC/cSurvey.vb:936-953, 1566-1570).

## Key classes & files

| File | Class / member | Responsibility |
|---|---|---|
| `TD:src/com/topodroid/TDX/Archiver.java` | `Archiver.archiveSurvey` (:406), `unArchive` (:731), `checkManifestFile` (:585), `checkVersionLine` (:652) | Builds/reads the project zip; defines entry set and manifest validation |
| `TD:src/com/topodroid/TDX/TopoDroidApp.java` | `writeManifestFile` (:1575) | Writes the 4-line manifest |
| `TD:src/com/topodroid/TDX/TDPath.java` | `getSqlFile` (:417), `getManifestFile` (:426), `getSurveyPlotTdrFile` (:537), `getSurveyNoteFile` (:570), photo/audio dirs (:737-742) | Canonical file/entry names |
| `TD:src/com/topodroid/TDX/DataHelper.java` | `DistoXOpenHelper.createTables` (:8059-8305), `dumpToFile` (:6951), `loadFromFile` (:7283) | SQLite schema; `survey.sql` writer/parser |
| `TD:src/com/topodroid/util/TDVersion.java` | `DB_VERSION="60"`, `DATABASE_VERSION=60`, `DATABASE_VERSION_MIN=21` (:35-37) | Version constants used by the manifest gate |
| `TD:src/com/topodroid/TDX/TDExporter.java` | `exportSurveyAsCsx` (:269 Uri wrapper, :308 writer), `writeCsxSegment` (:183), `writeCsxTSplaySegment`/`writeCsxFSplaySegment` (:194/:206), `writeCsxLeg` (:173), `writeCsxShotAttachments` (:218), `exportEmptyCsxSketch` (:144), `csurvey_extend` (:92) | The whole csx data part |
| `TD:src/com/topodroid/TDX/DrawingWindow.java` | `doSaveCsx` (:8166), `exportAsCsx` (:9132) | Sketch-export entry point; splits plan/profile, collects x-sections |
| `TD:src/com/topodroid/TDX/DrawingSurface.java` / `DrawingCommandManager.java` | `exportAsTCsx` (:1378 / :2257) | Fan out to per-item writers |
| `TD:src/com/topodroid/TDX/DrawingIO.java` | `doExportAsTCsx` (:2370), `exportDataStream` (:1243), `skipTdrHeader` (:618) | Item loop incl. section-point extras; tdr writer; tdr header spec |
| `TD:src/com/topodroid/TDX/DrawingLinePath.java` | `toTCsurvey` (:457), `toDataStream` (:528) | `<item type="line">` writer; tdr `L` record |
| `TD:src/com/topodroid/TDX/DrawingAreaPath.java` | `toTCsurvey` (:460), `toDataStream` (:490) | `<item type="area">` writer; tdr `A` record |
| `TD:src/com/topodroid/TDX/DrawingPointPath.java` | `toTCsurvey` (:624 plain, :646 section point), `exportTCsxXSection` (:687), `toDataStream` (:772) | `<item type="point">` writer incl. nested `<crosssection>`/`<crosssectionfile>`; tdr `P` record |
| `TD:src/com/topodroid/TDX/DrawingPointLinePath.java` | `toCsurveyPoints` (:823) | `<points data>` writer — bezier flattening, reversal |
| `TD:src/com/topodroid/TDX/LinePoint.java` | `toDataStream` (:284) | tdr per-vertex record (with optional control points) |
| `TD:src/com/topodroid/TDX/DrawingUtil.java` | `SCALE_FIX`, `CENTER_X/Y`, `sceneToWorldX/Y` (:26-28, 77-83) | tdr-scene ↔ csx-world conversion |
| `TD:src/com/topodroid/types/PlotType.java` | `PLOT_*` constants (:23-33) | Plot `type` values in db/tdr |
| cSurveyPC/modImport.vb | `FixTopodroidCSX` (:384) | cSurvey-side pre-parse fix-up the converter output must survive |
| cSurveyPC/cImportTopoDroidHelper.vb | `ConvertItem` (:112-401) | cSurvey-side consumer of every `<item>` attribute listed below |

## Key flows

### 1. How TopoDroid builds the project zip (`Archiver.archiveSurvey`)

All cites `TD:src/com/topodroid/TDX/Archiver.java`.

1. :439-442 — writes the manifest to a temp file (`TopoDroidApp.writeManifestFile`, see below) and adds it as **the first zip entry**, named `manifest`.
2. :445-448 — dumps the current survey to `<app>/survey.sql` via `DataHelper.dumpToFile` and adds it as entry `survey.sql` (the temp file is deleted afterwards, :512).
3. :451-453 — adds the survey note text file if present (entry `<survey>.txt`, from `TDPath.getSurveyNoteFile`, `TD:src/com/topodroid/TDX/TDPath.java:570-574`).
4. :455-468 — *only* if user level "expert"+ and the `mZipWithSymbols` setting: adds nested zips `points.zip`, `lines.zip`, `areas.zip` with the enabled custom therion symbol definitions.
5. :481-492 — for every plot of the survey, **both NORMAL and DELETED status**, adds `<survey>-<plotname>.tdr` if the file exists (`addOptionalEntry` — missing files are silently skipped).
6. :494-500 — adds every file of the survey photo dir (`<id>.jpg`) and audio dir (`<id>.wav`).
7. Entry names are **flat basenames** regardless of source path — `new ZipEntry( name.getName() )` / `new ZipEntry( filename )` (:137, :170); there are no directories inside the zip.

The **manifest** (`TD:src/com/topodroid/TDX/TopoDroidApp.java:1575-1594`) is four lines:

```
6.3.10 630100        <- TDVersion.string() + " " + TDVersion.code()
60                   <- TDVersion.DB_VERSION
MySurveyName         <- survey name (must match the surveys row)
2026.07.10           <- current date  (written but NEVER read back)
```

Validation on re-import (`checkManifestFile`, `TD:src/com/topodroid/TDX/Archiver.java:585-642`): line 1 must parse as version ≥ 2.1.1 / code ≥ 20101 (:689-716, `TD:src/com/topodroid/util/TDVersion.java:61-64`); line 2 must satisfy `21 ≤ db_version ≤ 60`; line 3 becomes the survey name (spaces→underscores) and must not already exist on the device. Only 3 lines are consumed.

On re-import (`unArchive` :771-841) entries are dispatched **by name/extension**: `manifest` skipped, `survey.sql` → `DataHelper.loadFromFile`, `*.tdr` → tdr dir, `*.txt` → note dir, `*.wav`/`*.jpg` → audio/photo dir of the manifest's survey, `points.zip`/`lines.zip`/`areas.zip` → symbol libraries; anything else logs "unexpected file type" and is ignored.

### 2. `survey.sql` — content and row formats

Written by `DataHelper.dumpToFile` (`TD:src/com/topodroid/TDX/DataHelper.java:6951-7270`), one line per row, in this table order: `surveys` (exactly one row, always first), `originals`, `audios`, `photos`, `plots`, `shots`, `fixeds`, `stations`, `sensors`. Reconstructed sample (formats verbatim from the `pw.format` strings; `TDString.escape`d strings in double quotes):

```sql
INSERT into surveys values( 1, "mycave", "2026.07.10", "team", 2.5000, "comment", "0", 0, 0, 1, 1752130000 0 );
INSERT into shots values( 1, 0, "1", "2", 4.230, 123.45, -12.30, 0.00, 0.98, 42.10, 55.30, 1, 0, 0, 0, "", 0, 12345, 0, 0.00, "AA:BB:CC:DD:EE:FF", 0, 0, 0, 0, 0, 0, 0, 0 );
INSERT into plots values( 1, 1, "1p", 1, 0, "1", "", 0.00, 0.00, 1.00, 0.00, 0.00, "", "", 0, 0, -1.00, 0.00, 0.00, 0.00 );
INSERT into fixeds values( 1, 0, "1", 15.1234567, 45.1234567, 320.00, 274.00, "", 0, 1, "", 0.0000000, 0.0000000, 0.0, 1, 2, 0.0000, -1.0, -1.0, 1.000000, 1.000000 );
INSERT into stations values( 1, 0, "2", "lake", 0, "2", "NIL", 0 );
```

- `shots` dump column order (`:7127-7170`): `surveyId, id, fStation, tStation, distance(m), bearing(°), clino(°), roll, acceleration, magnetic, dip, extend, flag, leg, status, comment, type, millis, color, stretch, address(MAC), rawMx, rawMy, rawMz, rawGx, rawGy, rawGz, idx, time`. Schema comments: `flag` = NONE / DUPLICATE / SURFACE / COMMENTED…, `leg` = MAIN / SEC / SPLAY / XSPLAY / BACK… (`:8106-8107`; numeric values live in `com.topodroid.common` LegType/shot-flag classes — not opened here *(inferred)*).
- `plots` dump order (`:7055-7085` with `mPlotFieldsFull`): `surveyId, id, name, type, status, start, view, xoffset, yoffset, zoom, azimuth, clino, hide, nick, orientation, maxscrap, intercept, center_x, center_y, center_z`. `start` is the origin station; for leg x-sections `view` is the To-station; plan plots are conventionally named `<n>p` / profile `<n>s` *(inferred from `psd1.name` handling, `TD:src/com/topodroid/TDX/TDExporter.java:318-322`)*.
- `fixeds` dump order (`:7178-7209`): `surveyId, id, station, longitude, latitude, altitude(WGS84 ellipsoid), altimetric(geoid), comment, status, source, cs_name, cs_longitude, cs_latitude, cs_altitude, source(again — duplicated by the dump, :7202), cs_decimals, convergence, accuracy, accuracy_v, m_to_units, m_to_vunits`.
- Full CREATE TABLE schema of the phone db (needed only if you read `distox14.sqlite` directly off a device): `TD:src/com/topodroid/TDX/DataHelper.java:8075-8126` (surveys, shots), :8128-8153 (fixeds), :8155-8193 (stations, plots), :8223-8278 (photos, sensors, audios, originals). Current `DATABASE_VERSION` = 60.
- **Parser reality check**: `loadFromFile` (`:7283-7350`) does `line.split(" ", 4)`, takes token 2 as table name and scans the `( ... )` payload with a custom `Scanline` — column count expectations are gated on the manifest db_version. It is order-tolerant per line but **the first line must be the `surveys` row**.

### 3. The csx TopoDroid writes — annotated skeleton

Reconstructed strictly from the `pw.format` calls in `TD:src/com/topodroid/TDX/TDExporter.java` (line cites inline). This is **not a captured file** — no genuine TopoDroid export exists in this repo — but every byte below is traceable to the writer:

```xml
<csurvey version="1.11" id="">                                      <!-- :359 -->
<!-- 2026-07-10 created by TopoDroid v 6.3.10 -->                    <!-- :360 -->
  <properties id="" name="" origin="1"                              <!-- :365-368; origin = plot origin station, prefixed "MYCAVE-" if mExportStationsPrefix -->
     creatid="TopoDroid" creatversion="6.3.10" creatdate="2026-07-10"   <!-- :370 -->
     calculatemode="1" calculatetype="2" calculateversion="-1"      <!-- :371 -->
     ringcorrectionmode="2" nordcorrectionmode="0" inversionmode="1"
     designwarpingmode="1" bindcrosssection="1">                    <!-- :372-373 -->
    <note>survey note text, if <survey>.txt exists</note>           <!-- :376-399; else <note /> -->
    <sessions>
      <session date="2026.07.10" description="MYCAVE" team="..."
               nordtype="0" manualdeclination="1" declination="2.5000">  <!-- :407-418; declination attrs only if set -->
      </session>
    </sessions>
    <caveinfos>
      <caveinfo name="MYCAVE" color="1724697804" comment="...">     <!-- :428-433; cave = survey name UPPERCASED :313 -->
        <branches>
          <branch name="1" color="...">  </branch>                  <!-- :436; name = plan plot name minus last char :318-322 -->
        </branches>
      </caveinfo>
    </caveinfos>
    <gps enabled="0" refpointonorigin="1" geo="WGS84" format="" sendtotherion="0" />  <!-- :444 -->
  </properties>
  <segments>                                                        <!-- :452 -->
    <!-- leg: -->
    <segment id="12" cave="MYCAVE" branch="1" session="20260710_mycave" from="1" to="2"
             direction="1" exclude="1" duplicate="1" commented="1"  <!-- :497-505: direction only if extend<1; flag attrs only when set -->
             distance="4.23" bearing="123.4" inclination="-12.3"    <!-- :175-177 averaged leg -->
             g="947.9" m="42.1" dip="55.3"                          <!-- :178 DistoX calibration values -->
             l="0" r="0" u="0" d="0" note="..." distox="AA:BB:CC:DD:EE:FF" >  <!-- :507-512; LRUD is ALWAYS zero -->
      <attachments>                                                 <!-- :218-251 only with mExportMedia -->
        <attachment dataformat="0" data="<base64 jpg/wav>" name="" note="" type="image/jpeg" />
      </attachments>
    </segment>
    <!-- splay from station "2" (id empty, generated to-name, cut="1" when x-splay): -->
    <segment id="" cave="MYCAVE" branch="1" session="20260710_mycave" from="2" to="2(17)"
             splay="1" exclude="1" distance="1.85" bearing="200.0" inclination="4.0"
             g="..." m="..." dip="..." l="0" r="0" u="0" d="0" distox="..." >  <!-- :206-216, :563-577 -->
    </segment>
    <!-- calibration-check shots come first with calibration="1" exclude="1" (:454-468) -->
  </segments>
  <trigpoints>                                                      <!-- :643-652, one per fixeds row -->
     <trigpoint name="1" labelsymbol="0" >
       <coordinate latv="45.1234567" longv="15.1234567" altv="320.00"
                   lat="45.1234567 N" long="15.1234567 E" format="dd.ddddddd N" alt="320.00" />
     </trigpoint>
  </trigpoints>
  <plan>                                                            <!-- DrawingWindow.exportAsCsx :9137 -->
          <item type="line" name="wall" cave="MYCAVE" branch="1" reversed="0" closed="0"
                outline="1" options="" >                            <!-- DrawingLinePath.toTCsurvey :461-466; outline 1=out −1=in 0=none :38-40 -->
            <points data="0.45 -2.10 B 0.62 -2.33 ... " />          <!-- toCsurveyPoints :823+; world meters, beziers flattened, B after first point -->
          </item>
          <item type="area" name="sand" cave="MYCAVE" branch="1" orientation="0.00" options="" >  <!-- DrawingAreaPath.toTCsurvey :464 -->
            <points data="..." />
          </item>
<item type="point" name="stalagmite" cave="MYCAVE" branch="1" text="" scale="0" orientation="0.00" options="" >  <!-- DrawingPointPath.toTCsurvey :627-632 (writer does not indent points) -->
 <points data="1.23 -0.45 " />
</item>
<item type="point" name="section" cave="MYCAVE" branch="1" text=""
      sectiontext="nick" sectionname="xx0" stationfrom="1" stationto="2"
      sectionazimuth="123.00" sectionclino="0.00" sectionid="0"
      scale="0" orientation="0.00" options="-scrap mycave-xx0" >    <!-- DrawingIO.doExportAsTCsx :2408-2422 + DrawingPointPath :646-655 -->
 <points data="3.10 -1.20 " />
    <crosssection>                                                  <!-- :659-661 items of the section tdr, converted through the same toTCsurvey writers -->
          <item type="line" name="wall" ... > ... </item>
    </crosssection>
    <crosssectionfile>                                              <!-- :662-674 only if <survey>/photo/<section>.jpg exists -->
 <attachment dataformat="0" data="<base64>" name="" note="" type="image/jpeg" />
    </crosssectionfile>
</item>
    <plot />                                                        <!-- :9145 -->
  </plan>
  <profile>  ...same structure from the extended-profile plot...  </profile>  <!-- :9148-9159 -->
</csurvey>                                                          <!-- :666 -->
```

Key generation rules a converter must copy:

- `cave` = survey name uppercased; `session` = `yyyymmdd_<survey-name-with-underscores>` lowercased (:313, :405, :422-423) — this exactly matches cSurvey's computed session ID `Format(date,"yyyyMMdd") & "_" & description.Replace(" ","_").ToLower` (cSurveyPC/cSession.vb:198-206), which is how segments find their session.
- Leg reduction: consecutive no-station shots are averaged into the previous leg (`AverageLeg`, :482-617); splays are emitted with empty `id` and synthetic station `NAME(counter)` on the empty side (:194-216).
- Segment `id` is the phone db shot id (an integer!) — cSurvey regenerates non-GUID ids on load (cSurveyPC/modImport.vb:397-410), so a converter can use any stable string.
- `<segments>` may legitimately be followed by shots that never appear in any session UI: calib-check shots (`calibration="1"`, consumed at cSurveyPC/cSegment.vb:683) and x-splays (`cut="1"`, cSurveyPC/cSegment.vb:679).
- The item `name` attribute is the therion symbol name (`getThName()`); the full mapping of names cSurvey understands is the ConvertItem table in [topodroid-import.md](topodroid-import.md) (cSurveyPC/cImportTopoDroidHelper.vb:112-401). Unknown names degrade gracefully (border line / generic soil / "Undefined" sign).
- Points data uses `%.2f` world meters, space-separated, `B` token after the first point of the (single) sequence, written in reverse order when `reversed` (then attribute `reversed="1"` tells cSurvey *not* to revert again — cSurveyPC/cImportTopoDroidHelper.vb:69-72).

### 4. `.tdr` sketch binary — record layout

Everything Java `DataOutputStream` big-endian; strings are `writeUTF` (2-byte length + modified-UTF-8). Header comment/spec at `TD:src/com/topodroid/TDX/DrawingIO.java:610-616`, writer at :1243-1322 (and the multi-scrap variant :1325+):

| Tag | Payload | Cite |
|---|---|---|
| `V` | int TopoDroid version code (e.g. 630100) | :1247-1248 |
| `S` | UTF scrap fullname (`<survey>-<plot>`), int plot type, (+ int azimuth only when type==8 projected) , then `BrushManager.toDataStream` (symbol-library palette block) | :1249-1256 |
| `I` | 4 floats bounding box (left, top, right, bottom), int 0 (no north) | :1258-1263 |
| `N` | int scrap index | :1265-1266 |
| `P` (point) | float cx, float cy (scene px), UTF thname, UTF group, float orientation, int scale, int level, int scrap, UTF pointText, UTF options | DrawingPointPath.java:772-800 |
| `L` (line) | UTF thname, UTF group, byte closed, byte reversed, int outline, int lSide, int level, int scrap, UTF options, int npt, then npt vertex records | DrawingLinePath.java:528-561 |
| `A` (area) | UTF thname, UTF group, UTF prefix, int areaCnt, … then vertices (same vertex records) | DrawingAreaPath.java:490-504+ |
| vertex | float x, float y, byte has_cp; if 1: float x1,y1,x2,y2 (incoming bezier control points, scene px) | LinePoint.java:284-303 |
| `T`,`U`,`X` | label / user station / special records (see DrawingIO reader) | :613-615 |
| `F` | end of paths (bbox/autostation extras may follow) | :1277 |
| `E` | end of file | :1318 |

To turn a tdr path into csx `<points data>`: `world = (scene − (100,120)) / 20`, flatten bezier segments (csx has no control points in this encoding — TopoDroid itself samples them at `TDSetting.getBezierStep()`, DrawingPointLinePath.java:825-862), emit `%.2f` pairs with `B` after the first.

## How to modify safely (rules for the zip→csx converter)

- **Parse `survey.sql`, not SQLite, and not with an SQL parser.** The dump is line-oriented; split like `loadFromFile` does (`TD:src/com/topodroid/TDX/DataHelper.java:7299-7303`). Gate optional columns on the manifest's db_version exactly as :7312-7325 does, or require ≥ 56 and reject older zips with a clear message.
- **Reproduce the leg/splay state machine faithfully** (TDExporter :484-617): a leg's displayed values are the *average* of its repeats; a converter that emits every raw shot row as a segment will create duplicate legs cSurvey can't merge.
- **Emit `creatid="TopoDroid"` and do NOT emit `creat_postprocessed`** — that is the opt-in to cSurvey's entire fix-up chain (cSurveyPC/cSurvey.vb:943, matched case-insensitively via `pGetFileCreatID` :1755-1761). Setting `creatversion` is what makes the import log read "TopoDroid x.y.z".
- **Prefer `version="-1"` over `"1.11"`** on the `<csurvey>` root: `-1` is cSurvey's "foreign file, skip conversions" meta version (cSurveyPC/cSurvey.vb:953). TopoDroid's own `1.11` works but walks the 1.11→1.12→1.13→1.14 conversion cases, each raising `OnFileConversionRequest` (cSurveyPC/cSurvey.vb:1201-1236) — harmless no-ops today, but pointless risk for a generator.
- **Keep station/session naming consistent**: session attribute string must equal `yyyymmdd_description(lower, underscores)` of a `<session>` you also emit, or the shots land session-less; from/to may be any case (cSurvey uppercases, modImport.vb:408-409) but must be *consistently* cased across segments, items (`stationfrom/to`) and `origin`.
- **LRUD**: write literal `l="0" r="0" u="0" d="0"` like TopoDroid (:507, :527) — phone surveys carry walls as splays, and cSurvey's splay machinery (not LRUD) is what auto-sketch relies on ([auto-sketch-feasibility.md](../auto-sketch-feasibility.md)).
- **Sketch geometry must be resolvable by `BindSegments`**: cSurvey re-binds every imported item to the nearest centerline segment itself (modImport.vb:367-377), so converter items need no `S<id>` tokens — but their world coordinates must be in the same frame as the computed centerline (plot origin at the `origin` station, meters, Y down / depth positive as produced by `sceneToWorld`).
- If you extend TopoDroid instead (the cleaner long-term fix): the csx writer is self-contained in `TDExporter.exportSurveyAsCsx` + the three `toTCsurvey` methods; the export entry point that has both plots is `DrawingWindow.doSaveCsx` (`TD:src/com/topodroid/TDX/DrawingWindow.java:8166-8172`).

## Gotchas

- **The `surveys` INSERT in `survey.sql` is malformed on purpose-ish**: the format string ends `"%d %d );"` — `created` and `immutable` are separated by a *space*, not a comma (`TD:src/com/topodroid/TDX/DataHelper.java:6971`). Real SQL tooling chokes; TopoDroid's Scanline parser doesn't care. Don't "fix" your parser by assuming valid SQL.
- **The zip is flat and order matters only for `manifest`** (must be first entry, Archiver.java:439). Unknown entry names are ignored on TopoDroid re-import (:817-819), so a converter can tolerate extras.
- **Manifest line 4 (date) is write-only** — `checkManifestFile` consumes exactly 3 lines (:596-620).
- **`.tdr` files of DELETED plots are archived too** (Archiver.java:488-492); filter plots by `status == 0` (NORMAL) using the plots rows, or you'll convert the user's trash.
- **A csx exported with no sketch contains the LEGACY empty `<layers>` skeleton** (`exportEmptyCsxSketch`, TDExporter.java:144-171, used when psd1 == null :658-664). That skeleton is exactly what makes cSurvey take its "old TopoDroid format" branches (`plan/layers` checks at cSurveyPC/modImport.vb:354, :427-440). Modern sketch exports put flat `<item>` children under `<plan>`/`<profile>` — both shapes are in the wild.
- **Station x-sections (`xs-`/`xh-` plots) export `station="..."` instead of `stationfrom`/`stationto`** (DrawingIO.java:2413-2417). cSurvey's ConvertItem only reads `stationfrom`/`stationto` (cSurveyPC/cImportTopoDroidHelper.vb:352-357), so those section points arrive with no segment reference (`CreateCrossSection` gets `Nothing`). Leg sections (start+view stations) bind fine.
- **`TDSetting.mExportStationsPrefix` silently renames every station** to `MYCAVE-<name>` including `origin` (TDExporter.java:186-191, :364-368). A converter should not enable an equivalent; a diagnostic agent should recognize the pattern.
- **Media**: `<attachments>`/`<crosssectionfile>` appear only when `TDSetting.mExportMedia` is on (TDExporter.java:220); on the cSurvey side audio/photo *points* are dropped anyway (conversion commented out, cSurveyPC/cImportTopoDroidHelper.vb:337-342) but the x-section photo attachment *is* imported (:368-377).
- **Bezier control points survive only in `.tdr`** — the csx `<points data>` encoding is flattened polylines (DrawingPointLinePath.java:847-862). Round-tripping TopoDroid→csx→analysis loses curve semantics; parse tdr if you need them.
- **The comment on line 2 of the csx** (`<!-- date created by TopoDroid v x.y.z -->`, TDExporter.java:360) is the quickest fingerprint of a genuine TopoDroid file when `creatid` has already been post-processed away by a cSurvey save.
- **No genuine TopoDroid fixture exists in this repo yet** — `dev/example/buless.csz` is PocketTopo-derived and the Demo Survey files are native ([topodroid-end-to-end-trace.md](topodroid-end-to-end-trace.md)). Until someone exports one from a phone (Sketch window → export → "cSurvey" for the full file, or a project zip for converter testing) and drops it in `dev/example/`, the skeleton in flow 3 above is the reference; it is grounded line-by-line in the exporter source at the pinned commit.

## Related docs

- [topodroid-import.md](topodroid-import.md) — the receiving side: cSurvey's fix-up chain and the full `<item name>` → cSurvey-item mapping this doc's csx feeds into.
- [topodroid-end-to-end-trace.md](topodroid-end-to-end-trace.md) — execution-level trace of loading such a csx into cSurvey.
- [data-model-and-file-format.md](../data-model-and-file-format.md) — the full native csx/csz schema (superset of what TopoDroid writes).
- [mcp-blueprint.md](../mcp-blueprint.md) — Stage 4 (zip→csx pre-converter) is the consumer of this doc.
- [auto-sketch-feasibility.md](../auto-sketch-feasibility.md) — what happens after import: generating the finished sketch from splays.
