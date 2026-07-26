# cSurvey fork — project briefing for a collaborating agent

*A self-contained context package. Read this once and you'll have the mental model needed to help
build new features. It assumes you know cave-survey concepts (shots, splays, stations, LRUD, loop
closure, plan vs. extended-elevation profile, therion) but nothing about **cSurvey** or this fork.
Repo paths are cited throughout; if you have the repo, `CLAUDE.md` and `dev/reference/` go deeper.*

---

## TL;DR

**cSurvey** is Windows desktop cave-mapping software (VB.NET WinForms, .NET Framework 4.8, ~320k LOC).
A caver imports/types survey shots, the app computes the centerline, and the caver **draws the cave map**
(plan + extended-elevation profile) over that centerline, then exports/prints it.

This **fork** exists to (1) understand cSurvey deeply, (2) streamline the **TopoDroid → finished map**
workflow, and (3) build automation on top of it, eventually an **MCP server** that operates cSurvey.

**Where the work is right now:** the **TopoDroid-export → cSurvey-import** stage ("TDX → CSX") is the
active frontier and is already **operational as a semi-manual 4-step pipeline** (validated on real cave
surveys, July 2026). The next step is to make it **headless / one-command**, then wrap it as MCP. That's
the arc you'd be plugging into.

---

## 1. What cSurvey is (in your vocabulary)

- Users enter **shots** (distance / azimuth / inclination) + **splays**; cSurvey derives **stations**
  from shot names. It does **not** solve the network itself — it shells out to **external `therion.exe`**
  and parses back station coordinates (.plt) and loop errors. (`CalculateTypeEnum.Internal` exists but is
  dead code; the setter hard-codes Therion.)
- Coordinates: **X = east, Y = −north, Z = down**, meters, origin station pinned at (0,0,0). Plan
  projection = (X,Y); profile = **extended elevation** (unrolled abscissa D, Z).
- The distinctive thing cSurvey does that most tools don't: it's a **cartography editor**. You draw the
  cave outline, water, rock, morphology symbols, etc. as vector items over the centerline, and those
  drawings **warp automatically** when the centerline changes (re-survey, loop re-closure) because each
  drawn point can be **bound to the nearest shot**.
- No PDF writer of its own — finished PDF/SVG/DXF maps are produced by **therion** from exported
  `.th`/`.th2` scraps, or via cSurvey's native SVG/raster path.

## 2. The data & file model (what you'll manipulate)

- **`.csz`** = a ZIP (DotNetZip) containing `_data.xml` (the whole survey) + binary assets
  (`_data/design/<guid>.png`, cliparts, 3D chunks). **`.csx`** = the bare `_data.xml` with no zip.
  File-format version const is **`1.14`**, upgraded through a stepwise in-DOM chain on load.
- **Everything cross-references by string/GUID**: stations by UPPERCASE name, sessions by
  `yyyyMMdd_description`, caves by name, branches by backslash path, drawing points bound to shot **GUIDs**
  via `S<guid>` tokens in a flat `points@data` list. This is why **out-of-process XML manipulation is
  viable** — no binary object graph to reverse.
- Persisted classes follow a hand-written `New(Survey,[cFile,]XmlElement)` + `SaveTo(...)` convention;
  attributes omitted at default values; numbers are InvariantCulture.
- **Drawing model:** each design (Plan, Profile) has exactly **7 fixed z-ordered layers** (Base, Soil,
  Water/Floor, Rocks/Concretion, Ceiling, Borders, Signs). Items are `cItem*` subclasses storing absolute
  survey-meter coordinates. The cave outline is a `cItemInvertedFreeHandArea` on the Borders layer and
  **clips all lower layers**. Deep dive: `dev/reference/data-model-and-file-format.md`,
  `dev/reference/drawing-engine.md`.

## 3. The crux — TopoDroid interchange

The whole fork pivots on one reality:

- **cSurvey cannot read TopoDroid's `.zip` project archive.** The usable interchange is TopoDroid's
  **exported `.csx`** — which is *cSurvey's own XML format* (TopoDroid can emit it, richest option:
  centerline **plus** the sketch the surveyor drew on the phone). Therion `.th`/`.th2` are the leaner
  alternatives.
- A raw TopoDroid `.csx` is **auto-detected on load** (`properties/@creatid="topodroid"`) and run through
  a **three-stage fix-up chain** that turns therion-named flat sketch items into typed, centerline-bound
  cSurvey layer items, uppercases stations, assigns GUIDs, and force-binds everything. Headless entry
  point: `cSurvey.Load(path, LoadOptionsEnum.FixTopoDroid)` — exactly what the UI's import does, with no
  form involvement.
- ⚠ **Storage-shape trap:** a raw TopoDroid `.csx` stores sketch items as **flat `<item>` children under
  `<plan>`/`<profile>`**, *not* the nested `<layers>/<layer>/<items>` shape native cSurvey files use.
  Tooling that counts only the native shape reports **zero drawings for a file with a full sketch** — the
  exact false negative to avoid.

### Two possible pipelines (why one is chosen)

- **Pipeline A — the phone sketch exists.** The surveyor drew a rough map underground in TopoDroid.
  cSurvey's import chain already converts it into typed, bound, warp-ready native items *and* runs the
  calculation. Quality is genuinely map-like **because a human made the cartographic decisions**. This is
  TopoDroid's central workflow, and it is **the fork's target.**
- **Pipeline B — no sketch, synthesize walls from splays.** Where all the risk lives: the plan wall
  generator (`modSegmentsTools.CreatePlanBorderFromSplay`) is debug-gated and never binds its output; the
  **profile generator is an empty stub** (no parameters even); LRUD-from-splays isn't derived anywhere and
  phone data carries no LRUD. **Off the critical path** — don't build here unless a feature specifically needs it.

### What the `.csx` actually carries (beyond shots / splays / sketch)

The export is plain XML; this payload is **confirmed against real exports** (TopoDroid 6.4.29), not just
reconstructed. Beyond the centerline and the drawing, one file conveys:

| Category | Where in the XML | Notes / real example |
|---|---|---|
| **Cave name** | `<caveinfo name>` | = the survey name, UPPERCASED (`RUPE_PREKO_VERTIKALE`) |
| **Branch(es)** | `<branch name>` | the cave's sub-tree (e.g. `"1"`) |
| **Survey/trip date** | `<session date>` | the *real* survey date (`2024.02.04`) — **distinct from the export date** |
| **Team** | `<session team>` | surveyor initials, comma-separated (`dg,dm,id,sk`) |
| **Magnetic declination** | `<session manualdeclination declination>` | **conditional** — present only when set manually; the real file has `manualdeclination="0"` and **no declination value** (auto/unset declination is simply not written) |
| **North handling** | `nordtype`, `nordcorrectionmode` | grid vs. true-north config |
| **Survey note (free text)** | `<note>` | present only if the survey carries a note; often empty |
| **Provenance fingerprint** | `creatid`, `creatversion`, `creatdate`, line-2 comment | `creatid="TopoDroid"` is what triggers cSurvey's fix-up chain; version + export date + a `<!-- … created by TopoDroid v x.y.z -->` comment |
| **Calc configuration** | `calculatemode/type/version`, `ringcorrectionmode`, `inversionmode`, `designwarpingmode`, `bindcrosssection`, `origin` | loop-closure / inversion / warp / origin-station settings |
| **Geo fixed points** | `<gps enabled geo>` + `<trigpoints>/<coordinate lat long alt>` | only if the surveyor placed GPS/fixed points; **disabled** in the real file (`enabled="0"`) |
| **Raw instrument data, per shot** | segment attrs `g`, `m`, `dip`, `distox` | DistoX gravity/magnetic/dip sensor magnitudes + the **device MAC** (`00:13:43:B0:F6:60`) |
| **Per-shot flags** | `exclude`, `duplicate`, `commented`, `splay`, `calibration`, `cut`, `direction`, `note` | calib-check shots (`calibration="1"`), cross-splays (`cut="1"`), extend direction, per-shot comment |
| **LRUD** | `l/r/u/d` on segments | present but **always literal `0`** on phone surveys — walls are captured as splays, not LRUD |
| **Media** | `<attachments>` / `<crosssectionfile>` (base64 jpg/wav) | only if media-export is enabled on the phone (off in the real file) |

Two things to internalize: **(1) declination is not guaranteed** — don't assume it's present; if the phone
used auto/no declination the attribute is simply absent. **(2) survey date ≠ export date** (`session date`
vs `creatdate`) — use `session date` for the trip. On import, cSurvey **preserves the survey structure**
(sessions incl. team/date/declination, cave/branch, segments, trigpoints, sketch); DistoX `g`/`m`/`dip`/MAC
ride along as raw markers; LRUD zeros and audio/photo *points* are dropped (x-section photos are kept).
Field-by-field consumption: `dev/reference/topodroid/topodroid-import.md`.

### How to know what a given export contains

1. **Read the XML** — it's plain text; the `<properties>/<sessions>/<caveinfos>/<segments>/<trigpoints>/<plan>/<profile>`
   tree is self-describing. Fastest full truth for one file.
2. **Run the Stage-0 inspector** (`dev/production/tools/inspect_survey.py [--json]`) for a structured,
   diffable report: provenance verdict, centerline / session / cave / branch counts, sketch item counts in
   **both** storage shapes, geo, cached results. *(It reports structure + provenance but does **not** yet
   break out session attributes like team/declination — reading the XML stays authoritative, and surfacing
   that metadata block is a good small inspector enhancement.)*
3. **The field-by-field spec** is `dev/reference/topodroid/topodroid-zip-and-csx-format.md` §3 — an annotated
   skeleton grounded line-by-line in TopoDroid's exporter source, plus the generation rules any converter
   must copy. Where a real file and the spec ever disagree, **the file wins.**

## 4. Current state — the "TDX → CSX" pipeline (the active work)

**Status: operational since 2026-07-26**, accepted on two real TopoDroid cave surveys. Pipeline A was
validated end-to-end (import 10/10 predictions, binding real, warping real, zero file-version skew against
the installed 2025-12 binary). The standing procedure (SOP: `dev/production/tdx-processing-protocol.md`):

1. **Phone:** draw in TopoDroid preferring "green-verdict" tools; export **one** `.csx` (it contains both
   plan and profile) into the handoff folder.
2. **Pre-process** (`dev/production/tools/preprocess_tdx_csx.py`): rewrite the raw export so symbols
   survive import — driven by a **user-owned mapping** (`tdx-mapping.json`, editable via a visual
   workbench). Emits a new file + a report of what will degrade.
3. **Import** into cSurvey (fix-up chain + therion calc run automatically), then **Save As**.
4. **Post-fix** (`dev/production/tools/fix_imported_linetypes.py`): repair what import can't express.

Two hard-won findings from this stage (both matter for feature work):
- **Symbol conversion is name-driven and *fixed*:** 13 line targets, 6 area targets, points resolved by
  `Enum.TryParse` against `SignEnum`. Unknown names **degrade silently and irrecoverably** (original
  therion name is discarded). Unmapped points become "Undefined" X-in-a-box. Full run-verified matrix:
  `dev/production/tdx-symbol-matrix.md`.
- **A real cSurvey rendering bug was root-caused:** pen line-decorations are stamped **per polyline segment
  without accumulating distance** (`cClipartOnPath.vb:88-99`), so TopoDroid's dense flattened polylines
  (10–30 cm segments) render as **plain lines**. Worked around by converting to spline linetype
  post-import; the upstream one-liner fix is parked behind the build blocker (below).

## 5. What's next / open frontiers (where new features land)

- **Headless / one-command import (the top priority, currently a *hypothesis*).** The proven import
  sequence — `New cSurvey` → `Load(path, FixTopoDroid)` → `Invalidate()` → `Calculate.Calculate(True)` →
  `SaveTo` — is **entirely `Public`**. The **"reflection hypothesis"**: a small net48 console app dropped
  **beside the installed `cSurveyPC.exe`** (referencing it as a library) may drive the whole import with
  **no source build and no DevExpress license**, bootstrapping the WinForms-only settings via reflection.
  If it holds, steps 3–4 collapse into one command. Constraints: the driver **must sit next to the exe**
  (paths derive from `Process.MainModule.FileName`) and bitness must match. **Untested — the highest-leverage next experiment.**
- **MCP server.** Design already drafted (`dev/reference/mcp-blueprint.md`): a net48 worker host + a thin
  `Public` facade inside cSurveyPC, fronted by a modern-.NET MCP stdio process. The pre-processor is its
  first tool stage.
- **Upstream cSurvey fixes** (parked behind the build blocker): accumulate decoration distance; make the
  importer emit splines; **preserve the therion name on unmapped items** so nothing is irrecoverable;
  append new `SignEnum` members (never renumber — see invariants). A custom TopoDroid symbol **palette**
  so surveyors only draw what survives the trip is backlogged (`dev/backlog/`).

### The one build constraint you must know
Anything that **modifies cSurvey's source** requires building it, and the build is blocked by
**DevExpress v24.2.13** (~27 GAC-referenced commercial UI assemblies + `licenses.licx`). **The domain
core does not use DevExpress — only the UI does** — so out-of-process tooling and the headless-driver
route sidestep it. `therion.exe` is a *separate*, free, runtime dependency (needed by released binary and
source build alike; no therion ⇒ no calculation at all).

## 6. How the work is organized (so you know where to read & put things)

`dev/` is split into four zones (full operating manual: `dev/README.md`):

| Zone | Question | Contents |
|---|---|---|
| `dev/reference/` | *How does cSurvey work?* | Architecture docs, `path:line`-grounded, adversarially fact-checked |
| `dev/production/` | *What do we run routinely?* | The pre/post-processing toolkit, the SOP, reusable methods |
| `dev/projects/` | *What are we building?* | **The dev loop — one folder per work item**: `brief.md` + `log.md` + `runs/` + `findings/` |
| `dev/decisions/` | *Why this way?* | `roadmap-decisions.md` — dated strategy log; **read it for current state** |

**How a feature gets built here** (the loop you'd follow): create `dev/projects/NNNN-slug/` from
`dev/projects/_templates/`, write a `brief.md` (problem → approach → definition of done), work it through
`draft → research → proposal → validation → closed`, log progress in `log.md`, and on close **promote**
outputs to `production/` (tools/SOP) and `reference/` (durable knowledge). Instrumented runs (save the
survey after each step, diff the serialized XML — a diff is a spec, prose rots) live under the project's
`runs/`.

## 7. Invariants & gotchas (violate these and things break *silently*)

1. **Enum integer values ARE the file format** (layer/item/pen/brush/linetype types). Append new values;
   **never renumber.**
2. **Station names are case-sensitive in therion** and uppercased on import — a known TopoDroid
   duplicate-station trap. Names matching `*(*)` are auto-flagged as splays.
3. **Calculation prerequisites:** an origin station set, every shot assigned a session, network fully
   connected, `therion.path` configured — else typed exceptions and no output.
4. **Items must be bound** (`item.BindSegments()`) after programmatic creation or they won't warp. The
   existing plan wall generator forgets this.
5. **Load is fault-tolerant per section** (broken XML section → silently empty → **vanishes on next
   save**). Exception: `<segments>` is unguarded and fatal.
6. **Headless hazards in otherwise UI-free paths:** therion execution can pop a modal MsgBox after a 120s
   timeout (use the async variant); warping can raise a details dialog; never call `cSurvey.Check` (needs
   UI state) — call `Load` directly.
7. **`My.Application.Settings`** is initialized only by the WinForms startup pipeline (~757 read sites);
   any headless host must replicate settings + localized-string loading or NRE.

## 8. Ground truth / test data

- The tracked corpus (`cSurveyPC/data/`, nine `.csz`) is **centerline-only**; only `test extend 2.csz`
  contains a real drawing item. `buless_test1.csz` looks rich but has **zero design items** (a trap).
- **Real** TopoDroid exports are **not in git** (gitignored) — they live in the user's handoff folder
  (`G:\My Drive\Share\TDX`) and in local-only project `runs/` snapshots (TopoDroid 6.4.29). The pipeline
  above was validated against these. Where a real file ever contradicts a doc, **the file wins.**
- Environment on the dev machine: cSurvey installed at `C:\csurvey64\cSurveyPC.exe` (x64, 2025-12 release);
  therion installed and `therion.path` configured.

## 9. Deeper reading (if you have the repo)

- Orientation: `CLAUDE.md` (repo root) · workspace manual: `dev/README.md`
- Current state & strategy: `dev/decisions/roadmap-decisions.md`
- Architecture: `dev/reference/README.md` (reading order) — data model, calculation, drawing, rendering,
  exports, UI, and `dev/reference/topodroid/` (the TopoDroid sending side, grounded in TopoDroid source)
- Automation seams: `dev/reference/automation-surface.md`, `dev/reference/mcp-blueprint.md`
- The operational pipeline: `dev/production/README.md` + `dev/production/tdx-processing-protocol.md`
- Prior work: `dev/projects/0001-stage0-inspector/`, `dev/projects/0002-tdx-symbol-mapping/`

---

*Bottom line: cSurvey already turns a phone-drawn TopoDroid survey into a bound, warp-ready, therion-solved
cSurvey map — the fork has proven and semi-automated that (TDX → CSX). The frontier is making it headless
and MCP-driven, plus a short list of well-understood upstream fixes. New features should target that arc
and follow the `dev/projects/` loop.*
