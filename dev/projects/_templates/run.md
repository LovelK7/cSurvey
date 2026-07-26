# Run log: <fixture> — <what this run tests>

<!-- Template for one instrumented run. Create runs/YYYY-MM-DD-slug/ inside your project, save this
     as RUNLOG.md there, and drop the per-step inspector JSON beside it. Survey snapshots (.csz/.csx)
     are gitignored by runs/.gitignore — the JSON + this RUNLOG are the tracked ground truth.
     Full protocol: dev/production/methods/instrumented-run.md. -->

Brief: [../../brief.md](../../brief.md) · Method: [instrumented-run](../../../../production/methods/instrumented-run.md)
Fixture: `<file>` — <provenance: real TopoDroid export / synthetic / corpus file>.
Raw snapshot IN this dir (always snapshot the input at step-00): `step-00-<name>`,
SHA256 `<hash>`.

> Roles: the **user** performs UI steps in cSurvey; a **Claude agent** generates/diffs inspector
> reports, verifies predictions, and logs findings. Either can read this cold and know where the run stands.

---

## step-00 — raw baseline (YYYY-MM-DD, <actor>) <✅|→>

<`inspect_survey.py --json` on the raw input; record the headline numbers (verdict, shots/splays,
item counts in both sketch shapes, bound vs unbound points).>

## step-01 — <transform / import step> (YYYY-MM-DD, <actor>) <✅|→>

<What was done. Diff against the previous step's JSON. State predictions and whether they held.
A diff of the serialized survey is the spec; prose about a UI session rots — prefer the diff.>

## step-NN — …

<Continue per step. On completion, summarize the verdict and feed any doc contradictions back into
`reference/`. When the run's purpose is met, note the outcome and update the project log.>
