# dev/tools — Stage 0 survey inspector (+ TDX recovery tools)

## TopoDroid zip → csx recovery (`tdx_zip_to_csx.py`, `parse_tdr.py`, `recover_tdx.bat`)

Regenerates a raw-TopoDroid `.csx` (centerline **and** sketch) from a TopoDroid **project zip**
(`manifest` + `survey.sql` + `.tdr`), replaying TopoDroid's own csx exporter offline. Built in
[projects/0003-tdx-zip-recovery](../../projects/0003-tdx-zip-recovery/brief.md) after TopoDroid
6.4.99 shipped a 0-byte-csx crash and a tdr format bump that older app versions silently refuse
(sketches vanish on cross-version zip import — the data is fine, the readers aren't).

```
python dev/production/tools/tdx_zip_to_csx.py <project.zip | folder> [more.zip ...] [--raw-only]
```

- A folder argument is scanned recursively for project zips (non-project zips are skipped by a
  manifest+survey.sql sniff). Outputs land next to each zip: `<survey>_recovered.csx` and — via an
  automatic `preprocess_tdx_csx.py` pass — `<survey>_recovered_pp.csx`, the one to import.
- **No-typing path:** `recover_tdx.bat` (a copy lives in the TDX handoff folder) — double-click to
  process every zip in that folder, or drag zips onto it. Its sibling **`preprocess_tdx.bat`** does
  the same for the normal (non-recovery) flow: double-click = preprocess every *raw* TopoDroid csx
  in the folder tree (sniffed by `creatid="TopoDroid"` without `creat_postprocessed`; `_pp.csx`
  outputs and post-import saves skipped), or drag csx files onto it. A third, **`fix_tdx.bat`**,
  runs the *post-import* fixer (`fix_imported_linetypes.py`) — drag the file you made with **Save
  As** after importing onto it to get `<name>_lt.<same ext>` (splines so decorations render, sizes,
  water brush); run it right after Save As and map in the `_lt` file. It accepts **both `.csz` and
  `.csx`** (whichever you saved — the rich zip is rewritten in place, all other entries preserved)
  and **blocks with instructions** if handed a not-yet-imported (raw/`_pp`) file, so you can't run
  the wrong step. All three .bats print a runtime STEP banner, carry a runtime "what to do next"
  footer, and hold an absolute repo path (update them if the repo moves). `preprocess_tdx_csx.py`
  and `fix_imported_linetypes.py` both also accept multiple files (the latter a folder-worth of
  dragged files) directly. **A plain-language operator guide — `READ ME FIRST - process a
  survey.txt` — sits next to these tools and is copied into the TDX folder** (the human entry
  point; the markdown protocol is its technical counterpart).
- `parse_tdr.py FILE.tdr [--items] [--json out]` is the underlying all-version `.tdr` binary reader
  (also a standalone diagnostic: proves whether a sketch file is intact).
- Only project zips work as input — TopoDroid's "export bundle" zips (csx/dxf/csv collections)
  contain no tdr/sql and are rejected. Multi-plot surveys: only the first plan + first profile plot
  are converted (matches TopoDroid's own csx export).

---

`inspect_survey.py` is the Stage 0 tool from [dev/reference/mcp-blueprint.md](../../reference/mcp-blueprint.md):
a **read-only** command-line inspector for cSurvey `.csz` / `.csx` files. It needs no build, no
DevExpress, no therion — just Python 3 (stdlib only). Task brief:
[dev/projects/0001-stage0-inspector/brief.md](../../projects/0001-stage0-inspector/brief.md).

Its headline number is the **count of drawing items per design** — the answer to *"does this
survey carry a usable phone sketch?"*, which decides whether the TopoDroid→map pipeline is
already implemented (Pipeline A) or needs wall synthesis from splays (Pipeline B).

## Usage

```
python dev/production/tools/inspect_survey.py FILE [FILE ...] [--json]
```

- One report per file; with 2+ files, a summary table is appended (same columns as the
  verified baseline table in the task brief §4).
- `--json` emits a machine-readable report with **stable, sorted keys** — designed so two
  reports of the same survey (e.g. saved before/after a manual UI step) can be diffed:

```
python dev/production/tools/inspect_survey.py --json before.csz > before.json
python dev/production/tools/inspect_survey.py --json after.csz  > after.json
git diff --no-index before.json after.json
```

Guarantees: never writes or repacks a survey, never extracts zip entries to disk (all
in-memory), parses numbers invariant-culture (`.` decimal, locale-independent).

## ⚠ The two-sketch-shapes gotcha

A sketch can be stored in **two different XML shapes**, and confusing them produces the exact
false negative this tool exists to prevent:

| Shape | XML path | Written by |
|---|---|---|
| **Nested (native / post-import)** | `<plan>/<layers>/<layer>/<items>/<item>` | cSurvey's own serializer |
| **Flat (raw TopoDroid, pre-conversion)** | `<plan>/<item>` — direct children, no `<layers>` | TopoDroid's csx export ("TCsx") |

The flat shape is materialized into the nested one only by the TopoDroid fix-up chain
(`cImportTopoDroidHelper.ConvertDesign`) when cSurvey loads the file. A counter that only
looks inside `<layers>` reports **0 items for a raw TopoDroid export carrying a full phone
sketch** — which would wrongly send the project down the synthesize-walls-from-splays road.

The tool therefore counts **both shapes separately and labels them explicitly** in every
report (`nested (native <layers> shape)` vs `flat <item> (raw TopoDroid shape)`); the
summary "Items" column and JSON `sketch.total_items` are the sum of both, across plan and
profile. Legacy TopoDroid *empty*-sketch exports write a bare `<layers>` skeleton, so
"nested shape present but 0 items" is also a meaningful (and reported) state.

## What a report contains

- **Provenance verdict** — one of: *raw TopoDroid export* (`creatid="topodroid"`,
  case-insensitive, without `creat_postprocessed`), *post-import* (both present),
  *native cSurvey*, *other*. Plus `creatversion`/`creatdate`, file format version,
  custom datatable field definitions, and decoded `import_source` / `import_date` /
  `import_source_type` stamps from the pipe-positional `<datarow>` elements.
  Raw DistoX attributes (`g`/`m`/`dip`/`distox`) on segments are flagged as an extra
  raw-TopoDroid marker.
- **Centerline** — segments = shots + splays (`splay="1"`), trigpoints, count of shots with
  any nonzero LRUD, caves / branches / sessions, origin station (warns when unset — the
  centerline plot renders nothing without one).
- **Sketch** — per design (plan / profile): item counts in both shapes (nested broken out
  per layer, flat broken out per `type` and therion symbol `name`), per-design point
  totals split **bound vs unbound** (`S<guid>` tokens in `points@data`; unbound items never
  warp when the centerline changes), a count of items with zero bound points, and a
  **geometry digest** (bounding box + coordinate checksum) so that warping — which moves
  points without changing any count — shows up when diffing two reports.
- **Container** — zip entry count and asset classes (`_data/cliparts`, `_data/design`,
  `_data/surface`, `_data/design3d`), `_data.xml` size. `.csx` = bare XML. Extension chooses
  the format exactly as `cFile.vb` does; content that contradicts its extension is reported
  loudly (cSurvey itself would fail on such a file).
- **Cross-sections** — element count.
- **Calculate** — whether the file carries cached results (station count, speleometrics);
  absent means cSurvey recalculates on load, which requires therion.

## Verification status

Reproduces the verified nine-file baseline table (task brief §4, `cSurveyPC/data/`) exactly —
including `test extend 2.csz` = 1 item / 31 points all bound, and `buless_test1.csz` = 0 items
despite its 46 cliparts. On 2026-07-18 the tool ran on the first **real** TopoDroid export
(`dev/example/ponor_rupa_babi_pod_kucu-1p.csx`, gitignored): verdict *raw TopoDroid export*,
34 flat items — the flat-shape counting and TopoDroid verdicts are validated against reality,
not just against synthetic fixtures. See
[dev/projects/0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/](../../projects/0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/RUNLOG.md) for the
instrumented import run built on this tool, and
[dev/production/methods/instrumented-run.md](../methods/instrumented-run.md) for the
protocol. When any file contradicts the docs, trust the file.
