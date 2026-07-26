#!/usr/bin/env python3
"""Post-import fix: make TopoDroid-imported freehand lines render their pen
decorations (Scarpata triangles, Gradiente ticks, Sporgenza marks...).

Root cause (verified 2026-07-26, run dev/runs/2026-07-19-rupe-acceptance):
cSurvey stamps line decorations per straight segment and only when a single
segment is longer than the decoration width — distance does not accumulate
across segments (cClipartOnPath.vb:88-99, pDrawClipartOnLines). TopoDroid
strokes are dense flattened polylines (10-30 cm segments), so imported lines
never show decorations, while natively drawn splines (linetype=1) take the
curve branch and render fine. ConvertItem hardcodes LineType=Lines
(linetype=0) on every imported line.

Fix: rewrite linetype 0 -> 1 (Splines) on freehand-line items that carry the
TopoDroid import stamp, in a POST-IMPORT save (.csx). Point coordinates are
untouched — dense points constrain the spline, geometry stays visually
identical, decorations start rendering.

Usage:
  python dev/tools/fix_imported_linetypes.py INPUT.csx [-o OUTPUT.csx] [--force]
Never modifies the input. Re-open the output in cSurvey.
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

DEFAULT_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "tdx-mapping.json")

# shared cIItemSizable.SizeEnum (cIItemText.vb:20-33): signsize / textsize attr
SIZES = {"default": 0, "verysmall": 1, "small": 2, "medium": 3,
         "large": 4, "big": 4, "verylarge": 5}

# SignEnum members for the sign_sizes config (TDX-form names accepted)
SIGN_VALUES = {"continuation": 257, "narrow-end": 258, "low-end": 259,
"flowstone-choke": 260, "breakdown-choke": 261, "clay-choke": 262,
"entrance": 263, "flowstone": 513, "moonmilk": 514, "stalactite": 515,
"stalactites": 516, "stalagmite": 517, "stalagmites": 518, "pillar": 519,
"pillars": 520, "curtain": 521, "soda-straw": 522, "popcorn": 523,
"cave-pearl": 524, "disk": 525, "helictite": 526, "aragonite": 527,
"crystal": 528, "wall-calcite": 529, "gypsum": 530, "gypsum-flower": 531,
"anastomosis": 532, "karren": 533, "scallop": 534, "flute": 535,
"raft-cone": 536, "clay-tree": 537, "rimstone-pool": 538,
"rimstone-dam": 539, "archeo-material": 769, "paleo-material": 770,
"vegetable-debris": 771, "root": 772, "dig": 773, "air-draught": 774,
"water-flow": 777, "waterfall": 780, "spring": 781, "sink": 782,
"gradient": 786, "camp": 1025, "anchor": 1026, "ice": 1281, "snow": 1282,
"water": 1283, "pebbles": 1284, "clay": 1285, "raft": 1286, "guano": 1287,
"sand": 1288, "debrits": 1289, "blocks": 1290, "rock": 1291}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="post-import .csx (saved by cSurvey)")
    ap.add_argument("-o", "--out",
                    help="output path (default: <input>_lt.csx)")
    ap.add_argument("--all-lines", action="store_true",
                    help="also fix lines without a TopoDroid import stamp")
    ap.add_argument("--map", dest="map_file", default=DEFAULT_MAP,
                    help="tdx-mapping.json (its `postimport` section drives "
                         "the rules; defaults: spline_linetypes on)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    rules = {"spline_linetypes": True, "nonstandard_water": False}
    if os.path.exists(args.map_file):
        with open(args.map_file, encoding="utf-8") as f:
            rules.update(json.load(f).get("postimport", {}))

    out = args.out or (os.path.splitext(args.input)[0] + "_lt.csx")
    if os.path.abspath(out) == os.path.abspath(args.input):
        print("ERROR: output must differ from input", file=sys.stderr)
        return 1
    if os.path.exists(out) and not args.force:
        print("ERROR: %s exists (use --force)" % out, file=sys.stderr)
        return 1
    with open(args.input, "rb") as f:
        if f.read(4) == b"PK\x03\x04":
            print("ERROR: zip container (.csz) not supported yet — save as "
                  ".csx from cSurvey first", file=sys.stderr)
            return 1

    sign_sizes = {}
    for name, size in rules.get("sign_sizes", {}).items():
        v = SIGN_VALUES.get(name.lower())
        s = SIZES.get(str(size).lower())
        if v is None or s is None:
            print("WARNING: sign_sizes entry %r: %r ignored (unknown name "
                  "or size)" % (name, size), file=sys.stderr)
        else:
            sign_sizes[str(v)] = s
    label_sizes = {}
    for text, size in rules.get("label_sizes", {}).items():
        s = SIZES.get(str(size).lower())
        if s is None:
            print("WARNING: label_sizes entry %r ignored" % text,
                  file=sys.stderr)
        else:
            label_sizes[text] = s

    tree = ET.parse(args.input)
    root = tree.getroot()
    fixed_lines = fixed_water = fixed_sizes = 0
    for design in ("plan", "profile"):
        d = root.find(design)
        if d is None:
            continue
        layers = d.find("layers")
        if layers is None:
            continue
        for item in layers.iter("item"):
            dr = item.find("datarow")
            imported = dr is not None and (dr.text or "").startswith("TopoDroid|")
            if not (imported or args.all_lines):
                continue
            if (rules.get("spline_linetypes")
                    and item.get("type") == "1"
                    and item.get("linetype") == "0"):
                item.set("linetype", "1")
                fixed_lines += 1
            if (rules.get("nonstandard_water")
                    and item.get("type") == "3"
                    and item.get("category") == "64"):
                brush = item.find("brush")
                if brush is not None and brush.get("type") == "2":
                    brush.set("type", "6")  # Water -> NotStandardWater
                    fixed_water += 1
            if (item.get("type") == "6"
                    and item.get("sign") in sign_sizes):
                item.set("signsize", str(sign_sizes[item.get("sign")]))
                fixed_sizes += 1
            if (item.get("type") == "8"
                    and item.get("text") in label_sizes):
                item.set("textsize", str(label_sizes[item.get("text")]))
                fixed_sizes += 1

    tree.write(out, encoding="UTF-8", xml_declaration=True)
    print("wrote %s — %d line item(s) -> splines, %d water area(s) -> "
          "non-standard brush, %d size(s) applied"
          % (out, fixed_lines, fixed_water, fixed_sizes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
