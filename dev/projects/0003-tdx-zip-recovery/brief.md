# Task brief: Recover sketches from TopoDroid 6.4.99 exports (zip→csx converter)

- **ID:** 0003-tdx-zip-recovery
- **Status:** `closed`
- **Owner:** both
- **Opened:** 2026-08-16 · **Closed:** 2026-08-16
- **Read first:** [CLAUDE.md](../../../CLAUDE.md), [dev/README.md](../../README.md), [reference/topodroid/topodroid-zip-and-csx-format.md](../../reference/topodroid/topodroid-zip-and-csx-format.md), [production/tdx-processing-protocol.md](../../production/tdx-processing-protocol.md)

> This brief is self-contained: a fresh session can pick it up from cold and know exactly what to do
> and where the work stands, without inheriting any prior conversation.

---

## 1. Problem — what's wrong / missing, and why it matters

TopoDroid **6.4.99-36** broke the user's whole phone→cSurvey handoff:

1. **csx export crashes** on the phone and leaves a **0-byte .csx** — the primary interchange file
   (Pipeline A) is gone.
2. Project **zips import on other phones/older versions with the sketch missing** — only shots and
   splays appear; every line/area/symbol is dropped, silently.
3. Attempting to work around it by downgrading (e.g. to 6.4.57-36) fails: re-importing the zip hits
   **"duplicate survey"** because the survey still exists in the app's private database, and deleting
   the survey *folder* in a file manager doesn't remove it (it also destroys the on-phone `.tdr`
   sketches — the folder is where they live).

Real surveys were affected (`spilja_bunker_studena`, `zero_calory_dressing` in `G:\My Drive\Share\TDX`).
Without a recovery path, any survey sketched under 6.4.99 is unreachable for map production.

## 2. Context — what's already known (verified 2026-08-16)

- **Root cause found in TopoDroid source** (mirrored in `findings/tdsrc/`, fetched from GitHub master
  2026-08-16): the `.tdr` binary sketch format changed three times recently — line records gained
  `scale` at **604088**, area records gained `scale` at **604096** and `options` at **604098**
  (`DrawingLinePath.java:125`, `DrawingAreaPath.java:207-208`, `TDVersion.VERSION_TDR = 604098`).
  The tdr reader **hard-rejects any file newer than its own format version and returns an empty
  sketch with no error** (`DrawingIO.java:750`: `if (version > TDVersion.VERSION_TDR) return false;`).
  So old app + new zip = shots only (survey.sql loads, tdr refused). **The zip itself contains the
  full sketch** — nothing is lost at export time.
- The 0-byte csx is a separate 6.4.99 app bug (crash mid-export); the same data exists in the zip.
- Zip layout, `survey.sql` line format, csx skeleton, scene→world conversion: all as specified in
  [topodroid-zip-and-csx-format.md](../../reference/topodroid/topodroid-zip-and-csx-format.md).
  Two corrections found against real files and fed back: the post-`F` **`D` plot-info record**
  (5 floats + 4 UTF: xoffset, yoffset, azimuth, clino, intercept, start, view, hide, nick — reader
  removed in master, still written by phone builds) and the new 604088/604096/604098 fields.
- Version fingerprinting: zip `manifest` line 1 = exporting app version + code; line 2 = db version;
  tdr `V` record = *format* version (604098 for 6.4.99, i.e. `VERSION_TDR`, not the app code).
  Measured: `spilja_bunker_studena.zip` manifest says **6.2.16 / db 49** (exported long before the
  upgrade); `zero_calory_dressing.1.zip` says **6.4.99 / db 60**.

## 3. Approach — phases

**Phase 1 — tdr parser** (`findings/parse_tdr.py`). Full-fidelity reader for every tdr record
(V/S/I/N/P/T/L/A/J/U/X/Y/Z/D/F/E) with all historical version gates, transcribed from the mirrored
source. Reports per-file integrity (clean `E`, trailing bytes) and item inventory. **Done** — all 4
real tdr files (2 surveys × plan/profile, formats 602016 and 604098) parse to the end with 0 errors.

**Phase 2 — zip→csx converter** (`findings/tdx_zip_to_csx.py`). Replays TopoDroid's own
`TDExporter.exportSurveyAsCsx` offline: manifest + `survey.sql` (leg-repeat averaging state machine,
splay naming `N(i)`, extend→direction map) + tdr items → raw-TopoDroid-shaped `.csx` that enters the
standing processing protocol unchanged (auto-detected, fix-up chain binds items on import). **Done** —
both surveys converted; geometry verified to the centimeter against TopoDroid's own `.th2` export
(independent path); Stage-0 inspector sees healthy raw TopoDroid files (39 and 45 sketch items).

**Phase 3 — user validation.** Import `*_recovered_pp.csx` (preprocessed per protocol) into cSurvey,
confirm sketch renders over the centerline. **Done — user confirmed working import 2026-08-16.**

**Phase 4 — promote.** **Done 2026-08-16:** scripts moved to `production/tools/` (converter grew
multi-zip/folder batch mode + automatic preprocess pass; `recover_tdx.bat` drag-and-drop wrapper,
copy deployed to the TDX handoff folder), recovery step added to the protocol doc (step 1b), tdr
format corrections fed into `reference/topodroid/topodroid-zip-and-csx-format.md`.
Remaining follow-up (outside this brief): report the bugs upstream to TopoDroid
(csx crash + silent tdr rejection).

## 4. Definition of done

- [x] All four real tdr files parse cleanly end-to-end (proves sketches recoverable).
- [x] Converter output validates with the Stage-0 inspector as a raw TopoDroid csx (item counts match tdr inventory).
- [x] Geometry cross-checked against an independent TopoDroid export (`.th2`) — exact match.
- [x] User imports a recovered csx in cSurvey and the sketch renders bound to the centerline (confirmed 2026-08-16).
- [x] Scripts promoted to `production/tools/` + protocol/reference docs updated.
- [x] All runs logged under `runs/`; contradictions with `reference/` noted (D record, 604088+ fields).

## 5. Outputs (fill in on close)

- **Production:** `tools/parse_tdr.py`, `tools/tdx_zip_to_csx.py` (batch + auto-preprocess),
  `tools/recover_tdx.bat` (drag-and-drop; copy deployed to `G:\My Drive\Share\TDX\`);
  protocol step 1b (zip archive every survey + recovery path) in `tdx-processing-protocol.md`;
  tools README section.
- **Reference:** tdr `D` record + 604088/604096/604098 field gates + the `V`-semantics/silent-rejection
  warning added to `topodroid/topodroid-zip-and-csx-format.md`. TopoDroid master source mirror kept in
  `findings/tdsrc/` (fetched 2026-08-16).
- **Decisions:** 2026-08-16 entry in roadmap-decisions.md (zip promoted to canonical phone artifact).
- **Follow-ups:** report bugs upstream (marcocorvi/topodroid): 6.4.99 csx export crash + silent tdr
  version rejection; multi-plot surveys (2p/2s…) only convert the first plot pair — extend if a real
  survey needs it (requires station-solve to place secondary plots); non-project "export bundle" zips
  are detected and skipped, not converted (DXF-only recovery would be a separate, lossy path).
