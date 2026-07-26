# Roadmap decisions

A running record of strategy decisions for the automation goal, and the findings behind them. Append new entries at the top. Unlike the rest of [dev/reference/](../reference/README.md) — which documents *the codebase* — this documents *the project*: what was decided, why, what's still unverified, and what to do next.

---

## 2026-07-26 — Symbol-mapping brief CLOSED; TDX→cSurvey processing is operational

The [symbol-mapping brief](../projects/0002-tdx-symbol-mapping/brief.md) closed with user sign-off after iterative acceptance on two real surveys. The standing workflow (phone → pre-process → import → post-fix, with a user-owned mapping config and a visual mapping workbench) is documented in **[tdx-processing-protocol.md](../production/tdx-processing-protocol.md)** — the entry point for routine TDX survey processing. Notable engineering finds along the way: cSurvey's per-segment, non-accumulating line-decoration stamping (dense polylines render plain — worked around via post-import spline linetypes; upstream fix candidate), the `water-flow` +90° orientation tweak, glyph-gallery extensibility (signs pack shipped), and the fixed 13-line/6-area import vocabulary. Next frontier unchanged: the **reflection hypothesis** (headless driver beside the installed exe) to automate steps 3–4 of the protocol, then the MCP surface per [mcp-blueprint.md](../reference/mcp-blueprint.md).

---

## 2026-07-19 — Pipeline A confirmed on real data; environment gaps closed; instrumented run staged

### What changed since 2026-07-16

Three of the five critical-path items landed, and the biggest open question is answered:

1. **The first real TopoDroid export exists** (critical path #2): `dev/example/ponor_rupa_babi_pod_kucu-1p.csx` — TopoDroid 6.4.29, exported 2026-07-18. **Gitignored — invisible to git history**; SHA256 recorded in the run log. It carries **34 flat sketch items** (12 plan + 22 profile) → **the surveyor draws on the phone → Pipeline A confirmed on data**, no longer just on the user's word. Bonus finding: the `-1p` (plan) and `-1s` (profile) exports are **byte-identical** — TopoDroid's csx always contains both designs; one export suffices.
2. **The Stage 0 inspector is built and verified** (critical path #3): `dev/production/tools/inspect_survey.py` (+ README). Reproduces the nine-file corpus baseline exactly, counts both sketch shapes, decodes datarow provenance stamps, and now carries a per-design geometry digest (bbox + coord-sum) so warping is diff-visible. Found `import_source="pockettopo"` stamps in `buless_test1.csz` — its PocketTopo provenance is now file-confirmed, not inferred.
3. **The dev environment finding is obsolete** (was #2 of "findings that reordered the plan"): cSurvey **is now installed and configured** on this machine (`C:\csurvey64\cSurveyPC.exe`, release binary 2025-12-10, x64; full `HKCU\Software\Cepelabs\cSurvey` key) and **therion is installed** with `therion.path` set (critical path #1). Version skew vs this source tree is still unmeasured — the staged run's prediction 8 measures it.

### Docs-vs-reality scorecard (first contact)

No contradictions. Upgraded from inference to fact: flat `<item>` children under `<plan>`/`<profile>` with therion symbol names (incl. subtype `wall:presumed` and `user`); `points@data` = `X Y B X Y …`, %.2f, no `S` bindings; segment ids sequential on legs / **empty on splays** — the duplicate-id reality behind `OFRegenerateSegmentsID`. New details the docs didn't predict: TopoDroid pre-names splay stations (`0(0)`) and stamps `exclude="1"` itself; LRUD written as explicit zeros; `creatdate` is date-only.

### Decision — run the instrumented import

Run the **instrumented import** next — protocol at [dev/production/methods/instrumented-run.md](../production/methods/instrumented-run.md), run state in [dev/projects/0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/RUNLOG.md](../projects/0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/RUNLOG.md) (step-00 done; steps 01-03 need the user at the UI). It tests the save-after-each-step protocol itself, produces the first ground-truth diff of the fix-up chain, and measures binary/source skew. After it: the **reflection hypothesis** (critical path #4) is the highest-leverage next experiment — headless Pipeline A with no build.

### Outcome (same day) — run complete, Pipeline A validated end-to-end

The run executed in full: **import 10/10 predictions confirmed (zero contradictions, zero version skew — the 2025-12 binary writes file version 1.14), binding real (all 473 points bound), warping real (shot edit moved both designs' bound sketches)**. Full evidence in the RUNLOG. Two limitations surfaced, both fixable *before* import without touching cSurvey: (1) point symbols outside `SignEnum` become irrecoverable Undefined X-boxes (therion name discarded at conversion — `cImportTopoDroidHelper.vb:380-398`); (2) wall-stroke orientation is not normalized, so clockwise strokes invert the cave-border fill (in-app fix: "Revert sequences", `frmMain2.vb:18420`). Follow-up brief: [dev/projects/0002-tdx-symbol-mapping/brief.md](../projects/0002-tdx-symbol-mapping/brief.md) (symbol-zoo experiment → mapping matrix → csx pre-processor → TDX palette). TopoDroid manuals now in `dev/literature/topodroid/`; the user's TDX handoff folder is `G:\My Drive\Share\TDX` (phone syncs there — the natural watch-folder for future automation). ⚠ The pristine raw export was lost in a post-run file move (recovery pending; SHA256 in RUNLOG) — future runs snapshot the raw input into the run dir at step-00.

---

## 2026-07-16 — Commit to Pipeline A; probe the two untested gates

### Decision

**Target Pipeline A** (reuse the sketch the surveyor drew on the phone), not Pipeline B (synthesize walls from splays). The user has confirmed the working assumption: TopoDroid surveys arrive with a rough sketch already drawn, which forms the basis for processing in cSurvey.

### The reframe that drove it

The goal "TopoDroid → automated processing → finished digitized map" contains two very different projects, and [auto-sketch-feasibility.md](../reference/auto-sketch-feasibility.md) prices them very differently:

- **Pipeline A — phone sketch exists.** `cSurvey.Load(path, LoadOptionsEnum.FixTopoDroid)` already converts the sketch into typed, centerline-bound native items *and* calculates the network. Implemented end-to-end inside the app today (`frmMain2.vb:11860-11865`). The doc's own words: *"end of story."* Quality is genuinely map-like **because a human made the cartographic decisions underground**.
- **Pipeline B — no sketch.** Where all the risk lives: the plan generator is debug-gated (`frmMain2.vb:15901`) and never binds its output; the profile generator is a literal empty function (`modSegmentsTools.vb:641-647` — verified: the stubs take **no parameters at all**, so there isn't even a signature to fill in); and the reason profile is hard rests on an `(inferred)` claim about junction unrolling that has never been tested.

The feasibility doc's headline verdict — *fully automatic finished cartography is not achievable with honest quality* ([auto-sketch-feasibility.md:144](../reference/auto-sketch-feasibility.md#L144)) — is true but answers a question this project need not ask. **Sketching on the phone is TopoDroid's central workflow.** If real inputs carry sketches, Pipeline B's multi-week, medium-risk work is **off the critical path entirely**, and the goal becomes largely a packaging problem around code that already works.

### Findings that reordered the plan

**1. There is no ground truth on the input side.** The repo contains **zero real TopoDroid files**. The entire description of what TopoDroid emits was reconstructed backwards from cSurvey's *reader* code — stated plainly at [topodroid-end-to-end-trace.md:27](../reference/topodroid/topodroid-end-to-end-trace.md#L27): *"No TopoDroid-fresh sample exists in this repo... this is reconstructed from the exact attributes the code consumes."* The `.zip` internals are marked `(inferred)`. The docs are strong archaeology; they have not met reality.

**2. The dev environment cannot build or run cSurvey.** Probed 2026-07-16: no Visual Studio, no DevExpress v24.2.13, no `therion.exe`, no cSurvey installed, and **no `HKCU\Software\Cepelabs` registry key — meaning cSurvey has never been run on this machine.** Only `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\MSBuild.exe` and a `dotnet` binary with no detected SDK.

**3. The corpus is centerline-only.** All nine `.csz` files in `cSurveyPC/data/` were inspected in memory. Full table in [dev/projects/0001-stage0-inspector/brief.md](../projects/0001-stage0-inspector/brief.md#4-the-existing-corpus--verified-ground-truth). Highlights:
- **`test extend 2.csz` is the only file in the repo with a real drawing item** — the sole ground truth for the `<points data>` / `S<guid>` binding encoding.
- **`buless_test1.csz` is a trap.** Looks rich (1.3 MB, 46 cliparts, 2 MB surface DEM) but has **zero design items**; all 7 plan layers empty. PocketTopo-derived, not TopoDroid. Right test for container/asset handling, wrong test for drawings.
- None carries `creatid="topodroid"`.

### Dependency correction: DevExpress vs therion

These were conflated in earlier discussion. They differ in kind:

| | What it is | Needed by | Cost |
|---|---|---|---|
| **DevExpress v24.2.13** | Commercial UI library the source *references* | **Build only** — the shipped binary has it compiled in | Licensed |
| **therion.exe** | External program cSurvey shells out to for network solving | **Runtime — released binary *and* source build alike.** No `therion.path` ⇒ no calculation, at all | Free |

Therion is not a "source build" concern. Install it regardless.

### Open hypothesis: Pipeline A may need no build at all

**Untested, but it would remove DevExpress from the critical path.** Pipeline A is three calls, and per [topodroid-end-to-end-trace.md:151](../reference/topodroid/topodroid-end-to-end-trace.md#L151) **all three are already `Public`**: `New cSurvey` → `Load(path, FixTopoDroid)` → `SaveTo(path)`. `Load` runs both the calculation and the binding internally, so a driver can *"rely on `Load` having already done both"* rather than crossing the Friend wall.

So: a small net48 console app dropped **into the installed cSurvey folder**, referencing the shipped `cSurveyPC.exe` as a library, may drive the whole import with **no source build and no DevExpress license**.

The obstacle is the bootstrap: `My.Application.Settings` is initialized only by the WinForms startup pipeline (~757 read sites) and `modMain.LoadLocalizedStrings` is `Friend` — both reachable by **reflection**, which [automation-surface.md](../reference/automation-surface.md) already lists as the no-source-change fallback. Constraints: the driver exe **must sit beside `cSurveyPC.exe`** (paths derive from `Process.MainModule.FileName`, `modMain.vb:42-47`) and bitness must match.

If it holds, DevExpress is needed only later, to *fix* things inside cSurvey (e.g. the missing `BindSegments()` call), not to prove the pipeline.

### Sequencing questions, resolved

| Question asked | Answer |
|---|---|
| Run the process manually, record steps, debug, repeat several times? | **Run it manually — but once or twice, not as a campaign.** Zero→one real run is worth more than every subsequent run combined. **Instrument it** (save the survey after each UI step, diff `_data.xml`) rather than taking prose notes: a diff of the serialized survey is a spec; notes about a UI session rot. |
| Implement MCP now for fast agent feedback? | **Only the free part.** Stage 0 (read-only XML tooling) needs no build and is the instrument for everything else — do it now. Stages 1-3 are all gated behind the DevExpress build; committing to them before Pipeline A is proven is building on air. |
| Generate many cave projects → knowledge base of finished examples? | **No, not now — and it's actively risky.** Fixtures synthesized from a spec reverse-engineered from reader code would *encode the guesses as facts*: a corpus that agrees with itself and disagrees with reality. Get one real export, validate the spec, *then* synthesize. The valuable variant — (raw input, human-finished map) pairs as an auto-sketch eval set — only matters on Pipeline B, which is off the path. |
| Local (binary) or git (source) version? | **Both, by purpose.** Manual ground-truth spike → **released binary** (zero toolchain). Anything automated → **source build**, *unless* the reflection hypothesis above holds. Watch for **version skew**: the docs are grounded against this source tree; if the shipped build differs, ground truth from a manual run drifts from the code the docs describe. |

### Critical path (2-4 are independent, run in parallel)

1. **Install therion**, note the path. Free, hard prerequisite either way.
2. **Obtain one real TopoDroid `.csx` export.** The highest-value artifact in the project — it turns the reconstructed input spec into verified fact.
3. **Build the Stage 0 inspector** — delegated; brief at [dev/projects/0001-stage0-inspector/brief.md](../projects/0001-stage0-inspector/brief.md). Point it at (2); the design-item count confirms or kills Pipeline A.
4. **Test the reflection hypothesis** — can a net48 driver in the install folder call Public `Load`/`SaveTo` without a source build?
5. **Compare the shipped cSurvey version against this source tree** (pending: install path).

### ⚠️ The one detail that must not be gotten wrong

**A raw TopoDroid `.csx` stores sketch items as flat `<item>` children under `<plan>`, not in the `<layers>/<layer>/<items>` structure native cSurvey files use.** Flat children are materialized *only* by `cImportTopoDroidHelper.ConvertDesign` (`cImportTopoDroidHelper.vb:54`) during the fix-up chain; normal deserialization consumes only `<layers>` children (`cSurvey.vb:1386-1399`). A third shape exists: TopoDroid's `exportEmptyCsxSketch` emits a legacy `<layers>` skeleton.

Any tool that counts only the native shape reports **zero drawing items for a TopoDroid file with a complete sketch** — the exact false negative that would send the project down Pipeline B for no reason. Count all shapes, labelled distinctly.

### Corrections to existing docs

- **`dev/example/` and `dev/literature/` do not exist** (gitignored, `.gitignore:346-347`) but are cited by [CLAUDE.md](../../CLAUDE.md) and several docs. The real corpus is **`cSurveyPC/data/`**; `buless.csz` is **`cSurveyPC/data/buless_test1.csz`** — and it is PocketTopo-derived with zero design items, so CLAUDE.md's framing of it as "the realistic phone-surveyed case" is misleading for any drawing-related work.
- `modSegmentsTools.vb:641-647`: the profile stubs are emptier than documented — **no parameters**, so "port the plan algorithm" carries no scaffolding credit; the signature must be designed too.
