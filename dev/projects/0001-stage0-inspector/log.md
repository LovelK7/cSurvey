# Implementation log: Stage-0 survey inspector

Brief: [brief.md](brief.md)

> Backfilled 2026-07-26 during the dev/ reorg from the roadmap and the tool's README — this project
> predates the logging convention, so entries are reconstructed, not contemporaneous.

---

### 2026-07-18 — brief written and delegated (orchestrating session) ✅

- **Did:** wrote the self-contained brief for a read-only `.csz`/`.csx` inspector — no build, no
  DevExpress, no therion (stdlib Python).
- **Result:** brief specifies the headline metric (drawing-item count per design → decides Pipeline A vs B)
  and the two-sketch-shapes gotcha (nested native vs flat raw-TopoDroid).
- **Next:** build and verify against the nine-file corpus.

### 2026-07-18/19 — `inspect_survey.py` built and verified (agent) ✅

- **Did:** built the inspector; reproduced the verified nine-file corpus baseline; added per-design
  geometry digest (bbox + coord checksum) so warping is diff-visible; ran it on the first **real**
  TopoDroid export.
- **Result:** matches the baseline exactly (incl. `test extend 2.csz` = 1 item/31 points all bound,
  `buless_test1.csz` = 0 items despite 46 cliparts). On the real ponor export: verdict *raw TopoDroid*,
  34 flat items — flat-shape counting validated against reality, not just synthetic fixtures.
- **Evidence:** `../0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/` (the inspector is the instrument
  for that run); tool README.
- **Next:** promote to production; it becomes the Stage-0 instrument for all downstream work.

### closed ✅

- **Outputs — Production:** [`production/tools/inspect_survey.py`](../../production/tools/inspect_survey.py)
  (+ README). Now the read-only diff instrument used by every instrumented run and the standing SOP.
