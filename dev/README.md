# dev/ — the fork's R&D workspace

This folder is everything the fork produces *around* cSurvey: the knowledge, the tools, the
work-in-progress, and the record of what was done. It is organized so that at any moment — human
or AI, fresh session or deep in a task — you can answer four questions without archaeology:

- **How does cSurvey work?** → `reference/`
- **What do we run on a real survey?** → `production/`
- **What are we building right now, and how does it work?** → `projects/`
- **Why did we decide to do it this way?** → `decisions/`

New here? Read this file, then open [projects/README.md](projects/README.md) (the work board) and
[decisions/roadmap-decisions.md](decisions/roadmap-decisions.md) (current project state).

---

## The four zones

| Zone | Question it answers | What lives here | Lifespan |
|---|---|---|---|
| **`reference/`** | *How does cSurvey work?* | Architecture docs about the **software** — data model, calculation, drawing, rendering, exports, UI, TopoDroid internals. `path:line`-grounded, adversarially checked. | Stable; changes only when we learn something new about cSurvey. |
| **`production/`** | *What do we run routinely?* | The **operational toolkit** we run on every survey — pre/post-processing scripts (`tools/`), the standing SOP (`tdx-processing-protocol.md`), reusable `methods/`, and the config/knowledge those depend on. | Stable; the "shipped" surface. |
| **`projects/`** | *What are we building, and how does it work?* | The **dev loop** — one folder per work item (`NNNN-slug/`), holding its brief, its implementation log, its instrumented runs, and its findings. This is where **R&D happens**. | In flight → closed. Each folder is a permanent record. |
| **`decisions/`** | *Why this way?* | The **portfolio-strategy log** — dated, high-altitude decisions and the findings behind them (which pipeline, why, what's verified). | Append-only history. |

Supporting folders: **`sessions/`** (chronological session journal — see Logging), **`backlog/`**
(parked ideas), **`literature/`** and **`example/`** (external manuals + sample surveys, both
gitignored).

### The one idea that keeps it clean

**R&D is a *phase*; Production and Reference are *destinations*.** They are not three peer buckets you
sort a file into. Work is *born* in a `projects/` folder (a brief), matures through research and
validation *inside* that folder, and on success **promotes its outputs outward**:

```
        ┌──────────────────── projects/NNNN-slug/  (R&D in flight) ─────────────────────┐
        │   brief  →  research  →  propose ⇄ iterate with user  →  validate             │
        └───────────────────────────────────┬───────────────────────────────────────────┘
                              on close, promote the durable outputs:
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                    ▼
         reference/  (durable "how it works")            production/  (routines we now run)
                                     │
                                     ▼
                    decisions/  (the strategic "why", if the call was load-bearing)
```

So "is this R&D or production?" is never ambiguous: if it's still being figured out, it's a project;
once it's proven and we run it for real, it's in production; once it's settled knowledge about
cSurvey, it's in reference. Nothing lingers half-classified.

---

## The dev loop (how a piece of work moves)

Every non-trivial task follows the same arc. It maps 1:1 to the states a brief moves through:

| Loop step | Brief `status` | What happens | Where it's recorded |
|---|---|---|---|
| **State the problem** | `draft` | Write the brief: problem, why it matters, what "done" means. | `projects/NNNN/brief.md` |
| **Research it** | `research` | Investigate the code/data; produce findings. Instrumented runs go under `runs/`. | `brief.md` + `log.md` + `runs/` |
| **Propose & iterate** | `proposal` | Put options to the user; converge on an approach. | `log.md` (decisions), `brief.md` (chosen approach) |
| **Validate** | `validation` | Build it; test on real data; get user acceptance. | `log.md` + `runs/` |
| **Productionize** | `closed` | Promote tools→`production/`, knowledge→`reference/`, strategy→`decisions/`. Flip the brief to `closed` with a one-line pointer to what it produced. | everywhere the outputs landed |

Parked mid-flight → `parked` (say why, in the log). The point of the states is that **anyone can read
a brief's header and know exactly where the work stands** — no need to reconstruct it from chat.

To **start a new project**: copy `projects/_templates/` into `projects/NNNN-slug/`, fill in `brief.md`,
add a row to [projects/README.md](projects/README.md). See that file for the numbering convention.

---

## Logging — three tiers, deliberately non-overlapping

So we always know *what has been done and how successfully*, without one log becoming a dumping ground:

| Tier | File | Scope | When you write it | Answers |
|---|---|---|---|---|
| **Strategy** | `decisions/roadmap-decisions.md` | the whole fork | rarely — only on a load-bearing decision | "Why are we targeting Pipeline A?" |
| **Implementation** | `projects/NNNN/log.md` | one work item | per work chunk, as you go | "What was built/tried/decided in *this* project, and did it work?" |
| **Session** | `sessions/SESSIONS.md` | one working session, across projects | **at the end of every session** | "What did today touch, and how did it go?" |

Rule of thumb: a **decision that changes the plan** → decisions log; **progress on a task** → that
project's log; **a chronological "what happened today" for continuity across agents** → the session
journal. When in doubt, the project log is the default home; the session journal just links to it.

---

## Map: where does a thing go?

| I have… | It goes in… |
|---|---|
| a new fact about how cSurvey behaves internally | `reference/` (the relevant doc; add a `path:line` cite) |
| a script I'll run on every survey | `production/tools/` + a line in `production/README.md` |
| a step-by-step operating procedure | `production/` (an SOP) or `production/methods/` (a reusable method) |
| a new problem to solve | a new `projects/NNNN-slug/` (start from `_templates/`) |
| a one-off experiment script or its output | inside its project's `runs/<dated>/` or `findings/` |
| a strategic decision + its rationale | `decisions/roadmap-decisions.md` |
| an idea for later | `backlog/` |
| "what I did this session" | append to `sessions/SESSIONS.md` |
