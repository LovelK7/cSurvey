# Session journal

One block per working session (human or agent), **newest on top**. Write one at the end of every
session — it's the continuity thread across sessions and agents: what got touched, how it went, and
what's next. Keep it terse; link to project logs / runs / decisions for detail. This is the tier that
answers *"what has been done lately, and how successfully"* without reading every project.

Per the three-tier model ([dev/README.md](../README.md#logging--three-tiers-deliberately-non-overlapping)):
strategy → `decisions/`, per-task detail → `projects/NNNN/log.md`, chronology → here.

---

### 2026-07-26 — restructured dev/ into the four-zone system (agent) ✅

- **Did:** reorganized `dev/` from the tangled `docs/`+`tools/`+`tasks/`+`runs/` layout into four zones
  — `reference/` (architecture), `production/` (routine toolkit + SOP + methods), `projects/`
  (the dev loop, one folder per work item), `decisions/` (strategy log) — plus a `sessions/` journal.
  Established the dev-loop lifecycle (`draft→research→proposal→validation→closed`), project-folder
  anatomy (`brief.md` + `log.md` + `runs/` + `findings/`), templates under `projects/_templates/`, and
  the three-tier logging model.
- **Result:** 92 files moved; 86 cross-references auto-rewritten (incl. depth-sensitive `../../cSurveyPC`
  citations) with **0 newly-broken links** (the only 2 danglers are the pre-existing lost `step-00-raw-export.json`).
  Existing work refiled: inspector → project 0001; TDX symbol mapping + its 3 runs → project 0002;
  protocol/matrix/tools → `production/`; roadmap → `decisions/`. CLAUDE.md layout table + `dev/README.md`
  now describe the new structure.
- **Evidence:** `dev/README.md`, `dev/projects/README.md`, this reorg's git status (40+ renames).
- **Next:** brief up `0003-headless-driver` (the reflection hypothesis) as the first project run under the
  new system. Nothing blocking; user to review the structure.
