# Log — 0003-tdx-zip-recovery

## 2026-08-16 — diagnosis + converter built and validated in one session

**Symptoms reported:** TDX 6.4.99-36 csx export crashes (0-byte file); its zips import elsewhere
with all sketch items missing; downgrade blocked by "duplicate survey"; deleting survey folders on
the phone loses sketches while shots survive.

**Diagnosis (evidence-first):**
- Unzipped both real zips: `.tdr` sketch files present in both → export does NOT drop graphics.
- Manifests: `spilja_bunker_studena.zip` = TopoDroid **6.2.16**, db 49 (so that zip pre-dates the
  upgrade — line 1 of `manifest` is the version fingerprint); `zero_calory_dressing.1.zip` =
  **6.4.99**, db 60.
- Fetched TopoDroid master source (mirrored in `findings/tdsrc/`): tdr format changed at 604088
  (line `scale`), 604096 (area `scale`), 604098 (area `options`); reader at `DrawingIO.java:750`
  silently returns an empty sketch for any tdr newer than the app's `VERSION_TDR`. Mechanism fits
  every symptom: 6.4.57 (`VERSION_TDR` ≤ 602067-era) refuses 6.4.99's 604098 files.
- Wrote `findings/parse_tdr.py` from the reader source. All 4 real tdrs parse 100% clean:
  spilja 1p = 9 lines + 10 points + 3 areas, 1s = 5 lines + 12 points;
  zero 1p = 13 lines + 2 areas + 9 points + 1 label, 1s = 5 lines + 2 areas + 12 points + 1 label.
  Two format facts missing from the reference doc surfaced: post-`F` `D` plot-info record
  (still written by phone builds, reader dropped in master) and the three new version gates.

**Recovery tool:** `findings/tdx_zip_to_csx.py` — replays `TDExporter.exportSurveyAsCsx` offline
(leg-averaging state machine, splay `N(i)` naming, extend→direction, session id rules, item writers
with scene→world `(s−(100,120))/20`, bezier flattening 8 samples). Output is a raw-TopoDroid-shaped
csx so the standing protocol applies unchanged.

**Result:** both surveys regenerated. Validation:
- Geometry: first wall vertex of zero 1p = `2.83 3.76` in csx vs `(308.30,−384.42)/1.9685` from
  TopoDroid's own th2 export = `(2.83, 3.76)` — exact.
- Stage-0 inspector (`runs/2026-08-16/inspector.json`): both recognized as raw TopoDroid exports;
  39 / 45 sketch items; 5 legs + 63 splays / 5 legs + 71 splays (leg-repeat math consistent with
  78 / 87 raw rows).
- Protocol preprocessor ran clean (clay-area→clay, chimney→overhang+reverse, pit×4; 1 warning:
  line `user` left as border).
- Deliverables copied next to the source zips in `G:\My Drive\Share\TDX\<survey>\` as
  `<survey>_recovered.csx` (raw) and `<survey>_recovered_pp.csx` (import this one).

**Side observations for the user (also in session summary):** phone-side "delete survey" must be
done inside TopoDroid (survey data lives in the app's private SQLite db; folders are just working
copies holding the tdr sketches). Both surveys carry 2015 dates (survey date fields + shot millis ≈
June/Aug 2015) — phone or DistoX clock issue; affects cSurvey session ids (`20150625_…`).

**Next:** user imports `*_recovered_pp.csx` in cSurvey (Phase 3); then promote scripts + doc
corrections (Phase 4).
