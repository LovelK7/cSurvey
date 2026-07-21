#!/usr/bin/env python3
"""Generate the TDX symbol-zoo fixture (v3): a synthetic TopoDroid .csx with
one drawing item per known symbol name, for one instrumented import that
yields the complete empirically-verified symbol mapping matrix.

Phase 2 of dev/tasks/tdx-symbol-mapping-brief.md; inventory and predictions in
dev/docs/tdx-symbol-matrix.md. Output shape mirrors TopoDroid's csx emission
as specified (and run-validated) in dev/docs/topodroid-zip-and-csx-format.md.

v3 (user feedback):
- grid layout, 20 symbol slots per row (rows 12 m apart) — snippable row by row;
- labels alternate below/above the centerline (even/odd column) — no collisions;
- STATION NAMES ARE THE SYMBOL TAGS (`P07`, `L12`, `A03`, `C00`…): the
  centerline itself labels every slot; shot distance/bearing are computed from
  the grid coordinates so the solved network reproduces the layout exactly;
- text label with kind-index + name ("P07 crystal") under/over every item;
- winding calibration via two 2-stroke mini-passages (CAL2 anti-parallel =
  consistent, CAL3 parallel = inconsistent) — a lone stroke fills regardless
  of winding (v1/v2 finding).

Usage:  python dev/tools/make_symbol_zoo.py OUTDIR
Writes OUTDIR/step-03-zoo-v3.csx and OUTDIR/zoo-key-v3.md.
"""

import math
import os
import sys

CAVE = "SYMBOL_ZOO"
SESSION = "20260719_zoo"
COLS = 20        # symbol slots per row
DX = 2.0         # column spacing, m
DY = 12.0        # row spacing, m

POINTS = [
    "air-draught", "anchor", "aragonite", "archeo-material", "blocks",
    "clay", "continuation", "crystal", "curtain", "danger", "debris",
    "dig", "entrance", "flowstone", "gradient", "guano", "gypsum",
    "helictite", "ice", "label", "minus", "moonmilk", "mud", "narrow-end",
    "paleo-material", "pebbles", "pillar", "plus", "plus-minus", "popcorn",
    "root", "sand", "scallop", "section", "sink", "snow", "soda-straw",
    "spring", "stalactite", "stalagmite", "user", "wall-calcite", "water",
    "water-drip", "water-flow",
]  # "section" slot is reserved but label-only (fatal-load risk, see matrix)

LINES = [
    "arrow", "border", "ceiling-meander", "chimney", "floor-meander",
    "overhang", "pit", "presumed", "rock-border", "section", "slope",
    "user", "wall", "wall:blocks", "wall:clay", "wall:debris",
    "wall:ice", "wall:presumed", "water", "water-flow",
]

AREAS = [
    "blocks", "clay", "debris", "ice", "pebbles", "sand", "snow",
    "user", "water",
]


def el_point(name, x, y, text=""):
    t = text if text else ("zoo label" if name == "label" else "")
    return ('<item type="point" name="%s" cave="%s" branch="1" text="%s" '
            'scale="0" orientation="0.00" options="" >\n'
            ' <points data="%.2f %.2f " />\n</item>' % (name, CAVE, t, x, y))


def el_label(text, x, y):
    return ('<item type="point" name="label" cave="%s" branch="1" text="%s" '
            'scale="0" orientation="0.00" options="" >\n'
            ' <points data="%.2f %.2f " />\n</item>' % (CAVE, text, x, y))


def el_line(name, pts, outline="0", options=""):
    data = "%.2f %.2f B " % pts[0] + " ".join("%.2f %.2f" % p for p in pts[1:])
    return ('<item type="line" name="%s" cave="%s" branch="1" reversed="0" '
            'closed="0" outline="%s" options="%s" >\n'
            '            <points data="%s " />\n          </item>'
            % (name, CAVE, outline, options, data))


def el_area(name, x, y):
    data = ("%.2f %.2f B %.2f %.2f %.2f %.2f %.2f %.2f"
            % (x, y, x + 1.6, y, x + 1.6, y + 1.7, x, y + 1.7))
    return ('<item type="area" name="%s" cave="%s" branch="1" '
            'orientation="0.00" options="" >\n'
            '            <points data="%s " />\n          </item>'
            % (name, CAVE, data))


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(outdir, exist_ok=True)

    slots = ([("P", i, n) for i, n in enumerate(POINTS)]
             + [("L", i, n) for i, n in enumerate(LINES)]
             + [("A", i, n) for i, n in enumerate(AREAS)])

    items, stations = [], []
    key = ["# Symbol-zoo v3 key (station name = symbol tag)", "",
           "Grid: %d slots per row, rows %.0f m apart; labels alternate "
           "below/above." % (COLS, DY), "",
           "| station | kind-# | csx name | row | col | note |",
           "|---|---|---|---|---|---|"]

    for g, (kind, i, name) in enumerate(slots):
        row, col = divmod(g, COLS)
        x, yb = DX * col, DY * row
        tag = "%s%02d" % (kind, i)
        stations.append((tag, x, yb))
        ylab = yb + 1.5 if col % 2 == 0 else yb - 1.2
        note = ""
        if kind == "P":
            if name == "section":
                items.append(el_label("%s %s (skipped)" % (tag, name), x, ylab))
                note = "label-only, item excluded"
            else:
                items.append(el_point(name, x, yb + 0.5))
                items.append(el_label("%s %s" % (tag, name), x, ylab))
        elif kind == "L":
            if name == "wall":
                pts = [(x, yb - 2.0), (x, yb - 3.6),
                       (x + 1.6, yb - 3.6), (x + 1.6, yb - 2.0)]
                items.append(el_line("wall", pts, outline="1"))
                note = "CCW-drawn C-stroke"
            else:
                opts = "-scrap zoo-xx0" if name == "section" else ""
                pts = [(x, yb - 2.0), (x + 0.8, yb - 3.0), (x + 1.6, yb - 2.4)]
                items.append(el_line(name, pts, options=opts))
            items.append(el_label("%s %s" % (tag, name), x, ylab))
        else:
            items.append(el_area(name, x, yb + 2.5))
            items.append(el_label("%s %s" % (tag, name), x, ylab))
        key.append("| %s | %s%02d | %s | %d | %d | %s |"
                   % (tag, kind, i, name, row, col, note))

    # --- calibration row (its own row below the last symbol row) ----------
    calrow = (len(slots) - 1) // COLS + 1
    yb = DY * calrow

    def cal_station(idx, x):
        tag = "C%02d" % idx
        stations.append((tag, x, yb))
        return tag

    x = 0.0
    cal_station(0, x)
    pts = [(x, yb - 2.0), (x, yb - 3.6),
           (x + 1.6, yb - 3.6), (x + 1.6, yb - 2.0)][::-1]
    items.append(el_line("wall", pts, outline="1"))
    items.append(el_label("CAL1 wall CW single", x, yb + 1.5))
    key.append("| C00 | CAL1 | wall | %d | 0 | same C-stroke as L12, points "
               "reversed (CW) |" % calrow)

    x = 6.0
    cal_station(1, x)
    cal_station(2, x + 6.0)
    items.append(el_line("wall", [(x, yb - 1.2), (x + 3, yb - 1.4),
                                  (x + 6, yb - 1.2)], outline="1"))
    items.append(el_line("wall", [(x + 6, yb + 1.2), (x + 3, yb + 1.4),
                                  (x, yb + 1.2)], outline="1"))
    items.append(el_label("CAL2 passage consistent (anti-parallel)", x, yb + 2.6))
    key.append("| C01-C02 | CAL2 | wall ×2 | %d | 3-6 | mini-passage, strokes "
               "anti-parallel = consistent winding |" % calrow)

    x = 16.0
    cal_station(3, x)
    cal_station(4, x + 6.0)
    items.append(el_line("wall", [(x, yb - 1.2), (x + 3, yb - 1.4),
                                  (x + 6, yb - 1.2)], outline="1"))
    items.append(el_line("wall", [(x, yb + 1.2), (x + 3, yb + 1.4),
                                  (x + 6, yb + 1.2)], outline="1"))
    items.append(el_label("CAL3 passage inconsistent (parallel)", x, yb + 2.6))
    key.append("| C03-C04 | CAL3 | wall ×2 | %d | 8-11 | mini-passage, strokes "
               "parallel = inconsistent winding |" % calrow)

    # --- shots: consecutive stations, geometry computed from coordinates --
    shots = []
    for i in range(1, len(stations)):
        (f, fx, fy), (t, tx, ty) = stations[i - 1], stations[i]
        dx, dy = tx - fx, ty - fy          # y is south-positive (csx world)
        dist = math.hypot(dx, dy)
        bearing = math.degrees(math.atan2(dx, -dy)) % 360.0
        shots.append('    <segment id="%d" cave="%s" branch="1" session="%s" '
                     'from="%s" to="%s" distance="%.2f" bearing="%.1f" '
                     'inclination="0.0" l="0" r="0" u="0" d="0" >\n'
                     '    </segment>'
                     % (i, CAVE, SESSION, f, t, dist, bearing))

    xml = '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<csurvey version="1.11" id="">',
        '  <properties id="" name="%s" origin="P00" creatid="TopoDroid" '
        'creatversion="6.4.29" creatdate="2026-07-19" calculatemode="1" '
        'calculatetype="2" calculateversion="-1" ringcorrectionmode="2" '
        'nordcorrectionmode="0" inversionmode="1" designwarpingmode="1" '
        'bindcrosssection="1">' % CAVE,
        '    <note />',
        '    <sessions>',
        '      <session date="2026.07.19" description="zoo" team="" '
        'nordtype="0" >',
        '      </session>',
        '    </sessions>',
        '    <caveinfos>',
        '      <caveinfo name="%s" color="1724697804" comment="">' % CAVE,
        '        <branches>',
        '          <branch name="1" >  </branch>',
        '        </branches>',
        '      </caveinfo>',
        '    </caveinfos>',
        '    <gps enabled="0" refpointonorigin="1" geo="WGS84" format="" '
        'sendtotherion="0" />',
        '  </properties>',
        '  <segments>',
        '\n'.join(shots),
        '  </segments>',
        '  <trigpoints>',
        '  </trigpoints>',
        '  <plan>',
        '          ' + '\n          '.join(items),
        '    <plot />',
        '  </plan>',
        '  <profile>',
        '    <plot />',
        '  </profile>',
        '</csurvey>',
        '',
    ])

    csx = os.path.join(outdir, "step-03-zoo-v3.csx")
    with open(csx, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    with open(os.path.join(outdir, "zoo-key-v3.md"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\n".join(key) + "\n")
    print("wrote %s (%d items, %d stations, %d rows of %d)"
          % (csx, len(items), len(stations),
             (len(slots) - 1) // COLS + 2, COLS))


if __name__ == "__main__":
    sys.exit(main())
