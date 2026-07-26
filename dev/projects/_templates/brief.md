# Task brief: <one-line title>

<!-- Copy this whole _templates/ folder to projects/NNNN-slug/ and fill in. The brief is the
     living spec for one work item. Keep the header block current — it is the at-a-glance status
     anyone (human or agent) reads first. Delete these comments as you go. -->

- **ID:** NNNN-slug
- **Status:** `draft` <!-- draft → research → proposal → validation → closed (or parked) -->
- **Owner:** <user | agent | both>
- **Opened:** YYYY-MM-DD · **Closed:** —
- **Read first:** [CLAUDE.md](../../../CLAUDE.md), [dev/README.md](../../README.md), <the reference docs / prior runs this depends on>

> This brief is self-contained: a fresh session can pick it up from cold and know exactly what to do
> and where the work stands, without inheriting any prior conversation.

---

## 1. Problem — what's wrong / missing, and why it matters

<State the problem plainly. What can't be done today, or is done badly? What decision or capability
does solving it unlock? One or two paragraphs — enough that the "why" survives without you here.>

## 2. Context — what's already known

<Relevant code (`path:line`), prior findings, constraints, invariants that bound the solution.
Link into reference/ and any earlier project runs. Note what is verified vs assumed.>

## 3. Approach — phases

<Break the work into phases that map to the dev loop. Each phase names a concrete deliverable.
This section evolves: it starts as a plan and becomes the record of the chosen approach after the
proposal/iterate step.>

**Phase 1 — <name>.** <what it produces>
**Phase 2 — <name>.** <what it produces>
…

## 4. Definition of done

<Checklist of falsifiable conditions. What must be true — and verified how — for this to close?
Name the acceptance test / real-data check, not just "it works".>

- [ ] …
- [ ] All runs logged under `runs/`; contradictions with `reference/` fed back into the docs.

## 5. Outputs (fill in on close)

<On closing, list what this project promoted outward, so the brief is a durable index:>

- **Production:** <tools/SOPs added to `production/`>
- **Reference:** <docs created/corrected in `reference/`>
- **Decisions:** <entries added to `decisions/roadmap-decisions.md`>
- **Follow-ups:** <spawned briefs / backlog items>
