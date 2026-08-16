# Run 2026-08-16 — zip→csx recovery, first real conversion

Inputs (user's handoff folder, not copied here):
- `G:\My Drive\Share\TDX\spilja_bunker_studena\spilja_bunker_studena.zip`
  (manifest: TopoDroid 6.2.16 / db 49; tdr format 602016; SHA-independent — original zip untouched)
- `G:\My Drive\Share\TDX\zero_calory_dressing\zero_calory_dressing.1.zip`
  (manifest: TopoDroid 6.4.99 / db 60; tdr format 604098)

Commands:
```
python findings/tdx_zip_to_csx.py <zip> -o runs/2026-08-16/<name>_recovered.csx
python dev/production/tools/preprocess_tdx_csx.py <name>_recovered.csx -o <name>_recovered_pp.csx
python dev/production/tools/inspect_survey.py --json -o inspector.json <both recovered csx>
```

Results:
- spilja: 78 shot rows → 5 legs + 63 splays; 39 sketch items (plan 22 / profile 17); origin 1;
  session 20150625_spilja_bunker_studena.
- zero:   87 shot rows → 5 legs + 71 splays; 45 sketch items (plan 25 / profile 20); origin 0;
  session 20150813_zero_calory_dressing.
- Geometry cross-check vs TopoDroid's own th2 (zero, plan, first wall vertex): exact match (2.83, 3.76).
- Preprocessor: spilja 1 transform + 1 warning (line `user`); zero 6 transforms, 0 warnings.
- `inspector.json` in this folder is the tracked evidence; the four csx files are survey snapshots
  (gitignored class) and also live next to their zips in the TDX folder.

Status: awaiting cSurvey import validation by the user.
