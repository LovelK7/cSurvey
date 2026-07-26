#!/usr/bin/env python3
"""TDX csx pre-processor — phase 4 of dev/tasks/tdx-symbol-mapping-brief.md.

Rewrites a raw TopoDroid .csx BEFORE cSurvey imports it, so that symbols which
would otherwise degrade (verified empirically in dev/docs/tdx-symbol-matrix.md)
map to something cSurvey can both parse AND render. All choices below were
agreed with the user on 2026-07-19.

Transformations (flat `<item>` children of <plan>/<profile>, plus items nested
inside section points' <crosssection> elements):

  points:
    debris      -> blocks      (cSurvey's enum spells 'Debrits'; Blocks renders)
    water-drip  -> waterfall   (nearest water-from-above glyph)
    mud         -> clay        (semantically closest; data correct, glyph
                                pending a clay SVG in the install gallery)
    danger      -> label "!"   (text renders always; Signs layer never clipped)
    minus       -> label "-"
    plus        -> label "+"
    plus-minus  -> label "+/-"
    user        -> if the options string reveals the original tool name
                   (TopoDroid writes it there when a palette tool is missing),
                   rename to that and re-run the mapping; else left, flagged.
  lines:
    wall:blocks / wall:clay / wall:debris / wall:ice -> wall
                   (only bare `wall` and `wall:presumed` keep wall-ness in
                    cSurvey's converter; the subtype texture is lost either
                    way, but this recovers the cave border + fill)

Known degradations intentionally NOT touched (reported as warnings):
  line `arrow`, line `water` (become plain border lines), areas
  ice/snow/user (become blank generic soil).

Winding is NOT normalized: verified irrelevant to rendering (zoo CAL runs).

Safety: never modifies the input; refuses to overwrite an existing output
unless --force; original symbol name is preserved in the item's `options`
string as `tdxpp:<name>` for audit.

Usage:
  python dev/tools/preprocess_tdx_csx.py INPUT.csx [-o OUTPUT.csx] [--force]
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

DEFAULT_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "tdx-mapping.json")

# Filled from the mapping file (tdx-mapping.json) in main(); the defaults
# below are the 2026-07-19 user-agreed mapping, used if no file is found.
POINT_RENAMES = {
    "debris": "blocks",
    "water-drip": "waterfall",
    "mud": "clay",
    "tree-trunk": "vegetable-debris",
}

POINT_TO_LABEL = {
    "danger": "!",
    "minus": "-",
    "plus": "+",
    "plus-minus": "+/-",
}

POINT_LEAVE = set()
LINE_LEAVE = set()
AREA_LEAVE = set()

# per-entry extras from the mapping file: {(section, tdx-name): {...}}
#   "reverse": True     (lines) flip stroke direction -> decorations face the
#                       other side (e.g. chimney->overhang pointing outward)
#   "orientation": deg  (points) set the item's orientation attribute
EXTRAS = {}

LINE_RENAMES = {
    "wall:blocks": "wall",
    "wall:clay": "wall",
    "wall:debris": "wall",
    "wall:ice": "wall",
    "floor-step": "pit",
    "abyss-entrance": "pit",
}

AREA_RENAMES = {
    "clay-area": "clay",
}

GENERIC = {"strip_line_subtypes": True, "strip_area_suffix": True}


def load_mapping(path):
    """Populate the mapping tables from a tdx-mapping.json file."""
    global GENERIC
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for section, renames, labels, leaves in (
            ("points", POINT_RENAMES, POINT_TO_LABEL, POINT_LEAVE),
            ("lines", LINE_RENAMES, None, LINE_LEAVE),
            ("areas", AREA_RENAMES, None, AREA_LEAVE)):
        if section not in cfg:
            continue
        renames.clear()
        if labels is not None:
            labels.clear()
        for name, action in cfg[section].items():
            name = name.lower()
            if "to" in action:
                renames[name] = action["to"].lower()
            elif "label" in action and labels is not None:
                labels[name] = action["label"]
            elif action.get("leave"):
                leaves.add(name)
            extras = {k: action[k] for k in ("reverse", "orientation")
                      if k in action}
            if extras:
                EXTRAS[(section, name)] = extras
    GENERIC = {**GENERIC, **cfg.get("generic", {})}


def reverse_line_points(item, warnings):
    """Reverse the stroke direction of a raw TDX line item (its `points@data`
    is `x y [B] x y ...` — B marks the stroke start). Decorated pens stamp
    their marks on a side determined by direction, so this flips them."""
    pts_el = item.find("points")
    data = pts_el.get("data") if pts_el is not None else None
    if not data:
        return False
    toks = data.split()
    pts, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t[0] in "-0123456789.":
            if i + 1 < len(toks) and toks[i + 1][0] in "-0123456789.":
                pts.append((t, toks[i + 1]))
                i += 2
            else:
                warnings.append("reverse skipped (odd coordinate) on %r"
                                % item.get("name"))
                return False
        elif t == "B":
            i += 1
        else:
            warnings.append("reverse skipped (unexpected token %r) on %r"
                            % (t, item.get("name")))
            return False
    if len(pts) < 2:
        return False
    pts.reverse()
    out = ["%s %s" % pts[0], "B"] + ["%s %s" % p for p in pts[1:]]
    pts_el.set("data", " ".join(out) + " ")
    return True

# line names cSurvey's ConvertItem maps specially; a `base:subtype` name whose
# base is here falls through to a generic border UNLESS it is an explicit case
# (`wall:presumed` is the only mapped subtype) — so strip unknown subtypes
LINE_BASES = {"water-flow", "rock-border", "overhang", "wall", "presumed",
              "pit", "chimney", "slope", "floor-meander", "ceiling-meander",
              "border"}

# area names ConvertItem maps; extra sets use variants like `clay-area`
AREA_BASES = {"water", "sand", "debris", "blocks", "pebbles", "clay"}

# names that will still degrade after preprocessing — surfaced, not changed
KNOWN_DEGRADED = {
    ("line", "arrow"): "becomes a plain border line",
    ("line", "water"): "becomes a plain border line (no waterway line type)",
    ("line", "user"): "becomes a plain border line",
    ("area", "ice"): "becomes blank generic soil",
    ("area", "snow"): "becomes blank generic soil",
    ("area", "user"): "becomes blank generic soil",
}

# names known to fully map+render, for re-mapping recovered `user` tools
MAPPABLE_POINTS = {
    "air-draught", "anchor", "aragonite", "archeo-material", "blocks", "clay",
    "continuation", "crystal", "curtain", "dig", "entrance", "flowstone",
    "gradient", "guano", "gypsum", "helictite", "ice", "label", "moonmilk",
    "narrow-end", "paleo-material", "pebbles", "pillar", "popcorn", "root",
    "sand", "scallop", "sink", "snow", "soda-straw", "spring", "stalactite",
    "stalagmite", "wall-calcite", "water", "water-flow", "waterfall",
}


def mark(item, original):
    opts = item.get("options", "")
    item.set("options", (opts + " " if opts else "") + "tdxpp:" + original)


def process_item(item, stats, warnings):
    kind = (item.get("type") or "").lower()
    name = (item.get("name") or "").lower()

    if kind == "point":
        if name in POINT_RENAMES:
            item.set("name", POINT_RENAMES[name])
            mark(item, name)
            stats["renamed"].append("%s -> %s" % (name, POINT_RENAMES[name]))
        elif name in POINT_TO_LABEL:
            item.set("name", "label")
            item.set("text", POINT_TO_LABEL[name])
            mark(item, name)
            stats["labeled"].append('%s -> label "%s"'
                                    % (name, POINT_TO_LABEL[name]))
        elif name == "user":
            opts = item.get("options", "")
            recovered = None
            for tok in opts.replace("-", " -").split():
                t = tok.strip().lower().lstrip("-")
                if t in MAPPABLE_POINTS or t in POINT_RENAMES or t in POINT_TO_LABEL:
                    recovered = t
                    break
            if recovered:
                item.set("name", recovered)
                mark(item, "user")
                stats["recovered"].append("user -> %s (from options %r)"
                                          % (recovered, opts))
                process_item(item, stats, warnings)  # apply mapping to it too
            else:
                warnings.append("point 'user' not recoverable (options=%r) — "
                                "will be an X-box" % opts)
    elif kind == "line":
        if name in LINE_RENAMES:
            item.set("name", LINE_RENAMES[name])
            mark(item, name)
            stats["renamed"].append("%s -> %s" % (name, LINE_RENAMES[name]))
        elif (GENERIC.get("strip_line_subtypes") and ":" in name
                and name != "wall:presumed" and name not in LINE_LEAVE):
            base = name.split(":", 1)[0]
            if base in LINE_BASES:
                item.set("name", base)
                mark(item, name)
                stats["renamed"].append("%s -> %s (subtype stripped)"
                                        % (name, base))
    elif kind == "area":
        if name in AREA_RENAMES:
            item.set("name", AREA_RENAMES[name])
            mark(item, name)
            stats["renamed"].append("%s -> %s" % (name, AREA_RENAMES[name]))
        elif (GENERIC.get("strip_area_suffix") and name.endswith("-area")
                and name[:-5] in AREA_BASES and name not in AREA_LEAVE):
            item.set("name", name[:-5])
            mark(item, name)
            stats["renamed"].append("%s -> %s" % (name, name[:-5]))

    extras = EXTRAS.get(({"point": "points", "line": "lines",
                          "area": "areas"}.get(kind, ""), name))
    if extras:
        if extras.get("reverse") and kind == "line":
            if reverse_line_points(item, warnings):
                stats["renamed"].append("%s: stroke direction reversed" % name)
        if "orientation" in extras and kind == "point":
            item.set("orientation", "%.2f" % float(extras["orientation"]))
            stats["renamed"].append("%s: orientation set to %s"
                                    % (name, extras["orientation"]))

    leave = {"point": POINT_LEAVE, "line": LINE_LEAVE,
             "area": AREA_LEAVE}.get(kind, set())
    if (kind, name) in KNOWN_DEGRADED and name not in leave:
        warnings.append("%s '%s' left as-is — %s"
                        % (kind, name, KNOWN_DEGRADED[(kind, name)]))

    for xsec in item.findall("crosssection"):
        for sub in xsec.findall("item"):
            process_item(sub, stats, warnings)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pre-process a raw TopoDroid .csx so its symbols survive "
                    "the cSurvey import (see dev/docs/tdx-symbol-matrix.md).")
    ap.add_argument("input", help="raw TopoDroid .csx")
    ap.add_argument("-o", "--out",
                    help="output path (default: <input>_pp.csx)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing output file")
    ap.add_argument("--map", dest="map_file", default=DEFAULT_MAP,
                    help="mapping file (default: tdx-mapping.json next to "
                         "this script; built-in defaults if absent)")
    args = ap.parse_args(argv)

    if os.path.exists(args.map_file):
        load_mapping(args.map_file)
        print("mapping: %s" % args.map_file)
    else:
        print("mapping: built-in defaults (%s not found)" % args.map_file)

    out = args.out or (os.path.splitext(args.input)[0] + "_pp.csx")
    if os.path.abspath(out) == os.path.abspath(args.input):
        print("ERROR: output must differ from input", file=sys.stderr)
        return 1
    if os.path.exists(out) and not args.force:
        print("ERROR: %s exists (use --force to overwrite)" % out,
              file=sys.stderr)
        return 1

    tree = ET.parse(args.input)
    root = tree.getroot()
    if root.tag != "csurvey":
        print("ERROR: not a csx file (root <%s>)" % root.tag, file=sys.stderr)
        return 1
    props = root.find("properties")
    creatid = (props.get("creatid") or "").lower() if props is not None else ""
    if creatid != "topodroid":
        print("WARNING: creatid=%r — not a TopoDroid export; proceeding anyway"
              % creatid, file=sys.stderr)
    elif props.get("creat_postprocessed"):
        print("WARNING: file is already post-import (creat_postprocessed set) "
              "— renames feed a conversion that will NOT run again",
              file=sys.stderr)

    stats = {"renamed": [], "labeled": [], "recovered": []}
    warnings = []
    for design in ("plan", "profile"):
        d = root.find(design)
        if d is None:
            continue
        for item in d.findall("item"):
            process_item(item, stats, warnings)

    tree.write(out, encoding="UTF-8", xml_declaration=True)

    print("wrote %s" % out)
    for k, label in (("renamed", "renamed"), ("labeled", "converted to label"),
                     ("recovered", "recovered 'user'")):
        for line in stats[k]:
            print("  %s: %s" % (label, line))
    n = sum(len(v) for v in stats.values())
    print("%d item(s) transformed, %d warning(s)" % (n, len(warnings)))
    for w in warnings:
        print("  ⚠ %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
