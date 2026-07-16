# Task brief: Stage 0 survey inspector

**Status:** not started · **Prerequisites:** none (no build, no DevExpress, no therion)
**Repo:** `c:\Users\lkuku\VSCode\cSurvey` · **Read [CLAUDE.md](../../CLAUDE.md) first** for orientation.

This brief is self-contained. It was written by an orchestrating session so that a fresh session can execute the task without inheriting that conversation's context.

---

## 1. Why this exists — the decision it informs

The fork's goal is: **TopoDroid phone survey → cSurvey processing → finished digitized map**, eventually automated.

The strategy hinges on which of two pipelines the real data lands in:

- **Pipeline A — the surveyor drew a sketch on the phone.** `cSurvey.Load(path, LoadOptionsEnum.FixTopoDroid)` already converts that sketch into typed, centerline-bound native items and calculates the network. This path is *already implemented end-to-end inside the app*. Automating it is mostly packaging.
- **Pipeline B — no phone sketch; walls must be synthesized from splays.** Medium-risk, multi-week: the plan generator is debug-gated and never binds its output, and the profile generator is a literal empty function (`cSurveyPC/modSegmentsTools.vb:641-647` — the stubs take no parameters at all).

**The project is committing to Pipeline A.** This inspector's job is to make that commitment verifiable rather than assumed — and to be the standing instrument that answers, for any given file: *does this survey have a usable phone sketch?*

**The single most important number this tool reports is the count of drawing items per design, per layer.** Non-zero on a raw TopoDroid export ⇒ Pipeline A confirmed, and most of the goal is already built. Zero ⇒ the hard road.

Secondary uses:
- Diagnosing bad imports without opening the app.
- Provenance probing (`creatid`, `import_source` / `import_date` stamps).
- Instrumenting manual runs: save the survey after each manual UI step, diff the reports, and get machine-readable ground truth instead of prose notes.

---

## 2. Scope — read this before writing code

**In scope:** a read-only command-line tool that ingests a `.csz` or `.csx` and prints a structured report (human-readable table + a `--json` mode for diffing).

**Out of scope — do not do these:**
- **No writes, ever.** Do not modify, repack, or "fix" any survey file. `cStorage.SaveTo` rewrites the full in-memory entry set; a naive repack silently drops binary assets.
- **No extraction to disk** of the corpus files. Read the zip in memory.
- **Do not reference or build `cSurveyPC`.** This tool deliberately needs no build. That is its entire strategic value — it works today, while everything downstream waits on a DevExpress v24.2.13 license.
- **Do not reimplement domain logic** (calculation, warping, binding). Report what is in the XML; nothing more.

**Language:** the tool must run on this machine today. Python (`zipfile` + `xml.etree`) is the natural fit; PowerShell 5.1 is the zero-install fallback. Confirm what's available before choosing. `dotnet` exists at `C:\Program Files\dotnet\dotnet.exe` but no SDK was detected and there is no Visual Studio — don't count on a compile step.

---

## 3. File format facts you need

### Container
- `.csz` = plain ZIP (DotNetZip) containing `_data.xml` plus optional binary assets (`_data/design/<guid>.png`, `_data/cliparts/*.svg`, `_data/surface/*.dat`).
- `.csx` = bare XML, no zip. **TopoDroid exports `.csx`** — the tool must handle both.
- Format is chosen by extension (`cSurveyPC/cFile.vb:35-48`); the zip's survey entry is always `_data.xml` (`cFile.vb:386-403`).

### Top-level structure of `_data.xml` (constant across the corpus)
```
properties, segments, trigpoints, options, cliparts, signs, plan, profile,
[crosssections], previewprofiles, exportprofiles, sharedsettings, surface,
caveregister, [masterslave], calculate
```

### ⚠️ The critical correctness detail — TWO sketch shapes

**Getting this wrong produces exactly the wrong answer to the decision question above.**

| Shape | Path | Who writes it |
|---|---|---|
| **Native / post-import** | `<plan>/<layers>/<layer>/<items>/<item>` | cSurvey's own serializer; normal deserialization consumes only `<layers>` children (`cSurvey.vb:1386-1399`) |
| **Modern TopoDroid, pre-conversion** | `<plan>/<item>` — **flat children, no `<layers>` wrapper** | TopoDroid's csx export; materialized *only* by `cImportTopoDroidHelper.ConvertDesign` (`cImportTopoDroidHelper.vb:54`) during the fix-up chain |
| **Legacy TopoDroid empty-sketch** | `<layers>` skeleton | `TDExporter.exportEmptyCsxSketch` — flips cSurvey into its old-format branches (`modImport.vb:354, 427-440`) |

A raw TopoDroid `.csx` with a real sketch has **flat `<item>` children**. A tool that only counts `<layers>/<layer>/<items>/<item>` would report **0 items for a file that has a full sketch** — the precise false negative that would send the project down Pipeline B for no reason.

**Count both shapes and report them separately and explicitly labelled.**

There are exactly 7 layers per design, fixed z-order: `Base=0, Soil, WaterAndFloorMorphologies, RocksAndConcretion, CeilingMorphologies, Borders=5, Signs=6`. The cave outline is `cItemInvertedFreeHandArea` on the Borders layer.

### Other parsing traps
- **Invariant culture.** `_data.xml` stores `.` as the decimal separator regardless of host locale. Parse with invariant culture explicitly. (The app itself normalizes `.` to the host separator before parsing — `modNumbers.vb:228-236`.)
- **`<datarow>` is pipe-positional.** Decoding requires the `<datatables>` field definitions to know what each position means. This is where `import_source` / `import_date` provenance stamps live.
- **Points geometry** is a flat space-separated list in `<points data="...">`, with `B` prefix opening a sequence and `S<guid>` tokens binding a point to a shot. Example from the corpus: `data="-2.70 2.41 BSbcf988b5-… -2.64 2.41 S … 8.72 8.98 BS 8.72 6.62 S1707b991-…"`. Parser contract is `cPoints.vb:496-599`. You do not need to fully parse this — but counting bound vs unbound points is valuable (unbound items silently fail to warp).
- **Segments serialize huge** (~2.7 KB/shot) because each carries a computed `<data>` block with `planpd`/`profilepd` geometry. Don't be surprised by file sizes.
- **TopoDroid marker:** `properties/@creatid="topodroid"` (matched case-insensitively; `pGetFileCreatID` lowercases at `cSurvey.vb:1755-1761`) **plus absence of** `creat_postprocessed`. Once cSurvey saves the file, `creat_postprocessed="1"` is stamped (`cProperties.vb:1185`) and the fix-ups never re-run — so that attribute tells you whether a file is pre- or post-import.

---

## 4. The existing corpus — verified ground truth

Nine tracked files in [cSurveyPC/data/](../../cSurveyPC/data/). These numbers were verified by direct in-memory inspection and are your regression baseline — **the tool should reproduce them.**

| File | XML size | Segments | Splays | LRUD≠0 | Trigpoints | **Design items** | creatid |
|---|---|---|---|---|---|---|---|
| `snow_2015_yanina.CSZ` | 3.65 MB | 1496 | 1176 | 0 | 1491 | 0 | — |
| `buless_test1.csz` | 1.29 MB | 318 | 267 | 37 | 317 | **0** | — |
| `banka_08_15+7(1).CSZ` | 647 KB | 228 | 168 | 31 | 228 | 0 | — |
| `test extend 2.csz` | 87 KB | 12 | 0 | 0 | 12 | **1** | cSurvey |
| `test extend 1.csz` | 86 KB | 13 | 0 | 0 | 11 | 0 | cSurvey |
| `test lrud.CSZ` | 66 KB | 4 | 0 | **3** | 5 | 0 | cSurvey |
| `test123.CSZ` | 62 KB | 9 | 4 | 5 | 11 | 0 | — |
| `test splay1.csz` | 56 KB | 7 | 4 | 2 | 6 | 0 | — |
| `test111.CSZ` | 49 KB | 3 | 0 | 2 | 3 | 0 | — |

All are `version="1.05"` or `"1.09"`. **None has `creatid="topodroid"` — the repo contains zero real TopoDroid files.** Obtaining one is tracked separately; this tool must be ready to point at it the moment it arrives.

**Corpus notes that matter:**
- **`test extend 2.csz` is the only file in the repo with a real drawing item.** It is your only ground truth for the `<points data>` / `S<guid>` binding encoding. Treat it as the primary fixture for anything sketch-related.
- **`buless_test1.csz` is a trap.** It looks rich (1.3 MB, 46 clipart SVGs, a 2 MB surface DEM, 94 pointsjoins) but has **zero design items** — all 7 plan layers have empty `<items/>` and every pointsjoin is `data="  "`. It is PocketTopo-derived, not TopoDroid. Its bulk is centerline (857 KB of `<segments>`). It is the only multi-entry zip, so it is the right test for **container/asset handling** — and the wrong test for anything about drawings.
- `snow_2015_yanina.CSZ` (1496 shots) is the scale/perf case.
- `test splay1.csz` is the smallest file with splays — best fast unit fixture.

⚠️ **Stale path warning:** [CLAUDE.md](../../CLAUDE.md) and several `dev/docs/` files cite `dev/example/buless.csz` and `dev/literature/`. **Those directories do not exist** (gitignored at `.gitignore:346-347`). The real corpus is `cSurveyPC/data/`. Don't chase those paths.

---

## 5. Suggested report contents

Per file:
- **Provenance:** `creatid`, `creatversion`, `creatdate`, `creat_postprocessed` present?, file `version`, `import_source`/`import_date` datarow stamps → **verdict line: "raw TopoDroid export" / "post-import" / "native cSurvey" / "other"**
- **Centerline:** total segments, splays (`splay="1"`), non-splay shots, trigpoints, caves/branches/sessions, origin station, count of LRUD≠0
- **Sketch (the headline):** per design (plan, profile), per layer — item count, broken out by **shape** (`<layers>` nested vs flat `<item>` children). Plus bound vs unbound point counts.
- **Container:** zip entries, external assets (cliparts, design PNGs, surface DEMs)
- **Cross-sections:** count
- **Calculation:** is `<calculate>` present/populated (i.e. does the file carry cached results)?

Design the `--json` output for **diffing two reports**, since instrumenting manual UI runs is a primary use case.

---

## 6. Definition of done

- Handles both `.csz` and `.csx`.
- Reproduces the table in §4 exactly, across all nine corpus files.
- Correctly counts **both** sketch shapes, labelled distinctly (§3).
- Read-only: no file in the repo is modified. Verify with `git status` afterwards.
- Invariant-culture number parsing.
- `--json` mode suitable for diffing.
- Brief README covering usage and the two-sketch-shapes gotcha.

---

## 7. Grounding

Written against the fork's knowledge base in [dev/docs/](../docs/README.md). Most relevant:
- [dev/docs/mcp-blueprint.md](../docs/mcp-blueprint.md) — defines this as "Stage 0"; the tool contracts here (`get_survey_stats`, `list_shots`, `list_drawing_items`, `get_xml`) are the eventual MCP surface. Stage 0 is deliberately a parallel implementation that needs no build.
- [dev/docs/data-model-and-file-format.md](../docs/data-model-and-file-format.md) — the annotated `_data.xml` schema. **The reference for this task.**
- [dev/docs/topodroid-import.md](../docs/topodroid-import.md) and [dev/docs/topodroid-zip-and-csx-format.md](../docs/topodroid-zip-and-csx-format.md) — the fix-up chain and what TopoDroid emits.

**Trust caveat:** the docs are strong on cSurvey's *reader* code (citations spot-check accurately) but the TopoDroid *input* side is **reconstructed from that reader code, never captured from a real phone export** (stated at `topodroid-end-to-end-trace.md:27`). Anything describing what TopoDroid actually writes is an informed inference. Where this tool's findings contradict the docs on a real TopoDroid file, **the file wins** — and that contradiction is a finding worth reporting loudly.
