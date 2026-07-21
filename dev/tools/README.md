# dev/tools — Stage 0 survey inspector

`inspect_survey.py` is the Stage 0 tool from [dev/docs/mcp-blueprint.md](../docs/mcp-blueprint.md):
a **read-only** command-line inspector for cSurvey `.csz` / `.csx` files. It needs no build, no
DevExpress, no therion — just Python 3 (stdlib only). Task brief:
[dev/tasks/stage0-inspector-brief.md](../tasks/stage0-inspector-brief.md).

Its headline number is the **count of drawing items per design** — the answer to *"does this
survey carry a usable phone sketch?"*, which decides whether the TopoDroid→map pipeline is
already implemented (Pipeline A) or needs wall synthesis from splays (Pipeline B).

## Usage

```
python dev/tools/inspect_survey.py FILE [FILE ...] [--json]
```

- One report per file; with 2+ files, a summary table is appended (same columns as the
  verified baseline table in the task brief §4).
- `--json` emits a machine-readable report with **stable, sorted keys** — designed so two
  reports of the same survey (e.g. saved before/after a manual UI step) can be diffed:

```
python dev/tools/inspect_survey.py --json before.csz > before.json
python dev/tools/inspect_survey.py --json after.csz  > after.json
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
[dev/runs/2026-07-19-ponor-import/](../runs/2026-07-19-ponor-import/RUNLOG.md) for the
instrumented import run built on this tool, and
[dev/tasks/pipeline-a-instrumented-run.md](../tasks/pipeline-a-instrumented-run.md) for the
protocol. When any file contradicts the docs, trust the file.
