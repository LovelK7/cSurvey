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
TopoDroid import stamp, in a POST-IMPORT save (.csz or .csx). Point coordinates
are untouched — dense points constrain the spline, geometry stays visually
identical, decorations start rendering.

Accepts BOTH the rich .csz (zip) you get from a normal Save and the bare .csx —
whichever you saved, drag it in. Output keeps the same container (_lt.csz /
_lt.csx). Never modifies the input. Re-open the _lt output in cSurvey and do
all mapping there. For drag-and-drop convenience use fix_tdx.bat.

It refuses a file that has NOT been imported into cSurvey yet (a raw/phone or
_pp file), telling you to import + Save As first — so you cannot run it on the
wrong step by accident.

Usage:
  python dev/tools/fix_imported_linetypes.py INPUT.csx|INPUT.csz [-o OUT] [--force]
  python dev/tools/fix_imported_linetypes.py FILE1 FILE2 ...   (batch / drag-drop)
"""

import argparse
import json
import os
import sys
import zipfile
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


DATA_ENTRY = "_data.xml"


def is_zip(path):
    with open(path, "rb") as f:
        return f.read(4) == b"PK\x03\x04"


def load_root(path):
    """Return (root, is_csz). Reads _data.xml from a .csz zip, or parses .csx."""
    if is_zip(path):
        with zipfile.ZipFile(path) as z:
            if DATA_ENTRY not in z.namelist():
                raise ValueError("zip has no %s — not a cSurvey file" % DATA_ENTRY)
            return ET.fromstring(z.read(DATA_ENTRY)), True
    return ET.parse(path).getroot(), False


def write_root(root, src_path, out, is_csz):
    """Write root back, preserving the container. For .csz, copy every other
    zip entry (design PNGs, cliparts, surface DEM...) verbatim."""
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if is_csz:
        with zipfile.ZipFile(src_path) as zin, \
                zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename == DATA_ENTRY:
                    continue
                zout.writestr(info, zin.read(info.filename))
            zout.writestr(DATA_ENTRY, data)
    else:
        with open(out, "wb") as f:
            f.write(data)


def not_yet_imported(root):
    """True if this is a raw/phone or _pp file (flat <plan>/<item>, no
    <layers>) that has NOT been through cSurvey's import + Save. Such a file
    must be imported first; running the fixer on it would silently do nothing."""
    for design in ("plan", "profile"):
        d = root.find(design)
        if d is None:
            continue
        if d.find("layers") is not None:
            return False          # native/post-import shape present
        if d.findall("item"):
            return True           # flat items, no layers -> pre-import
    return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="+",
                    help="post-import .csz or .csx file(s) saved by cSurvey")
    ap.add_argument("-o", "--out",
                    help="output path (default: <input>_lt.<same ext>); "
                         "single input only")
    ap.add_argument("--all-lines", action="store_true",
                    help="also fix lines without a TopoDroid import stamp")
    ap.add_argument("--map", dest="map_file", default=DEFAULT_MAP,
                    help="tdx-mapping.json (its `postimport` section drives "
                         "the rules; defaults: spline_linetypes on)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if args.out and len(args.input) > 1:
        print("ERROR: -o/--out works with a single input only", file=sys.stderr)
        return 1

    rules = {"spline_linetypes": True, "nonstandard_water": False}
    if os.path.exists(args.map_file):
        with open(args.map_file, encoding="utf-8") as f:
            rules.update(json.load(f).get("postimport", {}))

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

    batch = len(args.input) > 1
    rc = 0
    for inp in args.input:
        base, ext = os.path.splitext(inp)
        # In batch/drag-drop mode, silently skip our own outputs so a folder
        # full of files doesn't produce <name>_lt_lt on a second pass.
        if batch and base.lower().endswith("_lt"):
            print("skip %s (already a _lt output)" % inp)
            continue
        if not os.path.exists(inp):
            print("ERROR: %s does not exist" % inp, file=sys.stderr)
            rc = 1
            continue

        try:
            root, is_csz = load_root(inp)
        except (ET.ParseError, ValueError, zipfile.BadZipFile) as e:
            print("ERROR: cannot read %s (%s) — is it really a cSurvey file?"
                  % (inp, e), file=sys.stderr)
            rc = 1
            continue

        # BLOCKER: wrong step. A raw/phone or _pp file has no cSurvey <layers>
        # yet; the fixer would silently change nothing. Stop and say what to do.
        if not_yet_imported(root):
            print("BLOCKED: %s has NOT been imported into cSurvey yet.\n"
                  "  Do the IMPORT step first:\n"
                  "    1. Open this file in cSurvey.\n"
                  "    2. File > Save As  (any name; .csz or .csx both fine).\n"
                  "  Then run this step on THAT saved file." % inp,
                  file=sys.stderr)
            rc = 1
            continue

        out = args.out or (base + "_lt" + ext)
        if os.path.abspath(out) == os.path.abspath(inp):
            print("ERROR: output must differ from input (%s)" % inp,
                  file=sys.stderr)
            rc = 1
            continue
        if os.path.exists(out) and not args.force:
            print("ERROR: %s exists (use --force)" % out, file=sys.stderr)
            rc = 1
            continue

        fixed_lines = fixed_water = fixed_sizes = imported_seen = 0
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
                if imported:
                    imported_seen += 1
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

        write_root(root, inp, out, is_csz)
        print("OK  %s\n    %d line(s) -> splines, %d water area(s) -> "
              "non-standard brush, %d size(s) applied"
              % (out, fixed_lines, fixed_water, fixed_sizes))
        if imported_seen == 0 and not args.all_lines:
            print("    NOTE: no TopoDroid-imported items found in this file. "
                  "If it wasn't a TopoDroid import, nothing here needed fixing.")
        elif fixed_lines == 0 and rules.get("spline_linetypes"):
            print("    NOTE: lines were already splines — nothing to change "
                  "(safe to have re-run).")
    return rc


if __name__ == "__main__":
    sys.exit(main())
