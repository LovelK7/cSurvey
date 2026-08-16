# projects/ — the dev loop, one folder per work item

Each project folder is the **complete, permanent record** of one piece of work — from "here's a
problem" to "here's what shipped". This is where R&D happens; see [dev/README.md](../README.md) for
how projects promote their outputs into `production/`, `reference/`, and `decisions/`.

## Anatomy of a project folder

```
NNNN-slug/
├── brief.md        the living spec — problem, approach, definition of done, status
├── log.md          implementation log — dated entries, each with a Result (the "how successfully")
├── runs/           instrumented runs (dated subdirs; RUNLOG.md + inspector JSON tracked, surveys gitignored)
└── findings/       experiment scripts and their outputs, matrices, anything R&D produced but not yet promoted
```

`runs/` and `findings/` are optional — add them when the work needs them.

## Lifecycle (a brief's `status`)

`draft → research → proposal → validation → closed`  (or `parked`)

Read a brief's header and you know where it stands. States map to the dev loop: state the problem
(`draft`) → research (`research`) → propose & iterate with the user (`proposal`) → validate on real
data (`validation`) → promote outputs and close (`closed`).

## Starting a new project

1. Pick the next free number: `NNNN` zero-padded, `slug` kebab-case (e.g. `0003-headless-driver`).
2. Copy `_templates/` → `NNNN-slug/` and fill in `brief.md` (status `draft`).
3. Add a row to the board below.
4. Work the loop; log as you go; on close, fill the brief's **Outputs** section and flip status to `closed`.

## Board

| ID | Project | Status | Brief | Latest |
|---|---|---|---|---|
| 0001 | Stage-0 survey inspector | ✅ closed | [brief](0001-stage0-inspector/brief.md) | `inspect_survey.py` built + verified against the 9-file corpus and the first real TopoDroid export; promoted to `production/tools/`. |
| 0002 | TDX → cSurvey symbol mapping | ✅ closed | [brief](0002-tdx-symbol-mapping/brief.md) | Full pipeline (mapping json → pre-process → import → post-fix) accepted on real surveys 2026-07-26; promoted to `production/` + the symbol matrix. |
| 0003 | TDX 6.4.99 export recovery (zip→csx) | ✅ closed | [brief](0003-tdx-zip-recovery/brief.md) | Root cause pinned (tdr format change 604088–604098 + silent version gate at DrawingIO.java:750); recovered surveys imported successfully in cSurvey 2026-08-16; promoted to `production/tools/` (`tdx_zip_to_csx.py` batch mode + `recover_tdx.bat` drag-and-drop in the TDX folder). |

### Next up (not yet briefed)

- **Headless driver / reflection hypothesis** — automate steps 3–4 of the TDX protocol (a net48 driver
  beside the installed exe calling Public `Load`/`SaveTo`), collapsing the pipeline into one command and
  setting up the MCP surface. Queued as the top item in [decisions/roadmap-decisions.md](../decisions/roadmap-decisions.md);
  design in [reference/mcp-blueprint.md](../reference/mcp-blueprint.md). Start it as `0004-headless-driver`.
