# TDX signs pack — glyphs for mapped-but-artwork-less signs

8 SVG glyphs for the `SignEnum` values that TopoDroid imports map to correctly
but which the installed cSurvey build (2025-12-10) has no artwork for — so they
rendered as X-in-a-square placeholders (verified in the symbol-zoo runs,
[dev/docs/tdx-symbol-matrix.md](../../docs/tdx-symbol-matrix.md)):

| File | SignEnum | TDX symbol it lights up |
|---|---|---|
| anchor.svg | Anchor (1026) | anchor |
| archeo-material.svg | ArcheoMaterial (769) | archeo (exports as archeo-material) |
| clay.svg | Clay (1285) | clay, and `mud` via the pre-processor |
| gradient.svg | Gradient (786) | gradient |
| ice.svg | Ice (1281) | ice |
| sand.svg | Sand (1288) | sand |
| snow.svg | Snow (1282) | snow |
| water.svg | Water (1283) | water (point) |

## Install

Copy all eight files into `C:\csurvey64\Objects\Cliparts\Signs\` and restart
cSurvey (the sign→glyph index is built once per session,
`frmMain2.vb:16535` / `cSignsImportHelper.CreateIndex`). Already-imported
surveys pick the glyphs up on reopen — the items' `sign` data was always
correct; only the artwork was missing.

Format notes (cloned from the shipped gallery files, e.g. `blocks.svg`):
plain SVG, `xmlns:csurvey="http://www.csurvey.it"`, the binding is the
numeric `csurvey:sign` attribute on the root; glyph drawn as thin black
strokes in a small coordinate box. Artwork is deliberately simple/UIS-flavored
— replace freely, only the `csurvey:sign` value matters.

⚠ Keep this pack in the repo: a cSurvey upgrade may overwrite the install
directory; re-copy after upgrading. See
[dev/backlog/custom-sign-palette.md](../../backlog/custom-sign-palette.md)
for where this mechanism can go next.
