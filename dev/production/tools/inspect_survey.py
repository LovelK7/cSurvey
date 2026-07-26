#!/usr/bin/env python3
"""Stage 0 survey inspector for cSurvey .csz / .csx files.

Read-only: opens the container in memory, parses `_data.xml`, prints a
structured report (human table or --json for diffing). Never writes, never
extracts, never builds cSurveyPC.

Task brief: dev/tasks/stage0-inspector-brief.md
Schema reference: dev/docs/data-model-and-file-format.md

The one thing this tool must get right (see README): a survey sketch can be
stored in TWO shapes —

  * native / post-import:        <plan>/<layers>/<layer>/<items>/<item>
  * raw TopoDroid pre-conversion: <plan>/<item>   (flat children, no <layers>)

Both are counted, separately and explicitly labelled. A counter that only
looks at the nested shape reports 0 items for a raw TopoDroid export that
carries a full phone sketch — exactly the false negative this tool exists
to prevent.

Numbers in _data.xml are invariant-culture ('.' decimal separator) regardless
of host locale; everything here parses with Python's locale-independent
float().
"""

import argparse
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

LAYER_NAMES = {
    0: "Base",
    1: "Soil",
    2: "WaterAndFloorMorphologies",
    3: "RocksAndConcretion",
    4: "CeilingMorphologies",
    5: "Borders",
    6: "Signs",
}

# raw TopoDroid sensor attributes; absorbed into datarow fields on import
# (cSegment.vb:735-740) — their presence as attributes marks a raw export
DISTOX_ATTRS = ("g", "m", "dip", "distox")

IMPORT_STAMP_FIELDS = ("import_source", "import_date", "import_source_type")


# ---------------------------------------------------------------------------
# container

def load_survey(path):
    """Return (root Element, container_info dict, warnings list).

    Format is chosen by extension, mirroring cFile.vb:66-81 (.csx = bare XML,
    everything else = zip with a `_data.xml` entry). If that fails we sniff
    and retry, but loudly: cSurvey itself would not.
    """
    warnings = []
    is_csx = path.lower().endswith(".csx")
    with open(path, "rb") as f:
        blob = f.read()
    looks_zipped = blob[:4] == b"PK\x03\x04"

    if is_csx and looks_zipped:
        warnings.append(
            "extension is .csx but content is a ZIP — cSurvey would fail to "
            "open this file; inspecting the zip anyway")
        is_csx = False
    elif not is_csx and not looks_zipped:
        warnings.append(
            "extension says zip (.csz) but content is not a ZIP — cSurvey "
            "would fail to open this file; trying bare XML anyway")
        is_csx = True

    if is_csx:
        container = {
            "format": "csx",
            "file_bytes": len(blob),
            "xml_bytes": len(blob),
            "entries": None,
            "assets": {},
        }
        xml_bytes = blob
    else:
        zf = zipfile.ZipFile(io.BytesIO(blob))  # in memory, never extracted
        names = zf.namelist()
        entry = next((n for n in names
                      if n.replace("\\", "/").lower() == "_data.xml"), None)
        if entry is None:
            raise ValueError("no _data.xml entry in zip (entries: %s)"
                             % ", ".join(names[:10]))
        xml_bytes = zf.read(entry)
        assets = {}
        for n in names:
            norm = n.replace("\\", "/").lower()
            if norm == "_data.xml":
                continue
            if norm.startswith("_data/design3d/"):
                kind = "design3d"
            elif norm.startswith("_data/design/"):
                kind = "design_images"
            elif norm.startswith("_data/cliparts/"):
                kind = "cliparts"
            elif norm.startswith("_data/surface/"):
                kind = "surface"
            else:
                kind = "other"
            assets.setdefault(kind, []).append(n)
        container = {
            "format": "csz",
            "file_bytes": len(blob),
            "xml_bytes": len(xml_bytes),
            "entries": len(names),
            "assets": {k: sorted(v) for k, v in sorted(assets.items())},
        }

    root = ET.fromstring(xml_bytes)
    if root.tag != "csurvey":
        raise ValueError("root element is <%s>, expected <csurvey>" % root.tag)
    return root, container, warnings


# ---------------------------------------------------------------------------
# invariant-culture numbers

def inv_float(s, default=0.0):
    """Parse an invariant-culture number ('.' decimal). float() is already
    locale-independent in Python; this just adds the empty/None default."""
    if s is None or s == "":
        return default
    try:
        return float(s)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# datarow decoding (pipe-positional; cDataProperties.vb:69-102)

def read_datafields(datatables, table):
    """Field names, in document order, for one datatable (segments /
    trigpoints / designitems)."""
    if datatables is None:
        return []
    tbl = datatables.find(table)
    if tbl is None:
        return []
    return [df.get("name", "") for df in tbl.findall("datafield")]


def decode_datarow(datarow, positional_fields):
    """-> dict field->value. A datarow with a `fields` attribute is
    self-describing (import/clipboard variant); otherwise values are
    positional per the datatable definitions."""
    if datarow is None:
        return {}
    text = datarow.text or ""
    values = text.split("|")
    fields_attr = datarow.get("fields")
    names = fields_attr.split("|") if fields_attr else positional_fields
    return {n: v for n, v in zip(names, values) if v != ""}


# ---------------------------------------------------------------------------
# points@data (cPoints.vb:496-599) — only enough to count bound points

_NUM_START = set("-0123456789.")


def scan_points(data, geo=None):
    """-> (total_points, bound_points, warnings). Token stream is
    `X Y [flags]` per point; flags is a concatenation of B / P / T<digit> /
    L / S[<guid>]. `S` (with or without guid) = point bound to a segment.

    `geo`, if given, is a mutable dict accumulating a geometry digest
    (bbox + coordinate sum) so that warping/morphing — which changes
    coordinates but no counts — shows up when diffing two reports."""
    total = bound = 0
    warnings = 0
    tokens = data.split()
    i = 0
    while i < len(tokens):
        if tokens[i][0] not in _NUM_START:
            warnings += 1  # flags token with no preceding coordinate pair
            i += 1
            continue
        if i + 1 >= len(tokens) or tokens[i + 1][0] not in _NUM_START:
            warnings += 1  # dangling X with no Y
            i += 1
            continue
        total += 1
        if geo is not None:
            try:
                x, y = float(tokens[i]), float(tokens[i + 1])
                geo["sum"] = geo.get("sum", 0.0) + x + y
                geo["minx"] = min(geo.get("minx", x), x)
                geo["maxx"] = max(geo.get("maxx", x), x)
                geo["miny"] = min(geo.get("miny", y), y)
                geo["maxy"] = max(geo.get("maxy", y), y)
            except ValueError:
                warnings += 1
        i += 2
        if i < len(tokens) and tokens[i][0] not in _NUM_START:
            flags = tokens[i]
            i += 1
            j = 0
            while j < len(flags):
                c = flags[j]
                if c in "BPL":
                    j += 1
                elif c == "T":
                    j += 2  # T<digit>
                elif c == "S":
                    bound += 1
                    break  # rest of the word is the (optional) guid
                else:
                    warnings += 1
                    break
    return total, bound, warnings


def count_item_points(item, geo=None):
    """Points of one <item>: modern `<points data="...">` or legacy child
    `<point>` elements (cPoints.vb:610-616)."""
    pts = item.find("points")
    if pts is not None and pts.get("data") is not None:
        return scan_points(pts.get("data"), geo)
    legacy = item.findall("point") + (pts.findall("point") if pts is not None else [])
    if legacy:
        bound = sum(1 for p in legacy if p.get("segment"))
        return len(legacy), bound, 0
    return 0, 0, 0


# ---------------------------------------------------------------------------
# sketch: the two shapes

def inspect_design(design):
    """Count items in one <plan>/<profile>, in BOTH shapes, labelled."""
    result = {
        "nested_items": 0,          # <layers>/<layer>/<items>/<item> (native)
        "nested_by_layer": {},
        "flat_items": 0,            # direct <item> children (raw TopoDroid)
        "flat_by_type": {},
        "flat_names": {},
        "has_layers_element": False,
        "points_total": 0,
        "points_bound": 0,
        "points_parse_warnings": 0,
        "items_without_bound_points": 0,  # items that will never warp
        "bbox": None,        # [minx, miny, maxx, maxy], world meters
        "coord_sum": None,   # checksum of all coordinates — warp detector
    }
    if design is None:
        return result

    geo = {}

    def take(item):
        t, b, w = count_item_points(item, geo)
        result["points_total"] += t
        result["points_bound"] += b
        result["points_parse_warnings"] += w
        if t > 0 and b == 0:
            result["items_without_bound_points"] += 1

    layers = design.find("layers")
    if layers is not None:
        result["has_layers_element"] = True
        for layer in layers.findall("layer"):
            ltype = int(layer.get("type", "-1"))
            items_el = layer.find("items")
            items = items_el.findall("item") if items_el is not None else []
            # tolerate items directly under <layer> too
            items += layer.findall("item")
            if items:
                label = "%d %s" % (ltype, LAYER_NAMES.get(ltype, "?"))
                result["nested_by_layer"][label] = len(items)
                result["nested_items"] += len(items)
            for item in items:
                take(item)

    for item in design.findall("item"):  # flat shape — raw TopoDroid
        result["flat_items"] += 1
        itype = item.get("type", "?")
        result["flat_by_type"][itype] = result["flat_by_type"].get(itype, 0) + 1
        name = item.get("name")
        if name:
            result["flat_names"][name] = result["flat_names"].get(name, 0) + 1
        take(item)

    if "sum" in geo:
        result["bbox"] = [round(geo["minx"], 2), round(geo["miny"], 2),
                          round(geo["maxx"], 2), round(geo["maxy"], 2)]
        result["coord_sum"] = round(geo["sum"], 2)

    return result


# ---------------------------------------------------------------------------
# whole-file inspection

def count_branches(el):
    return len(el.findall(".//branch"))


def inspect(path):
    root, container, warnings = load_survey(path)

    props = root.find("properties")
    pa = dict(props.attrib) if props is not None else {}

    # --- provenance -------------------------------------------------------
    creatid = pa.get("creatid")
    postprocessed = "creat_postprocessed" in pa
    cid = (creatid or "").lower()
    if cid == "topodroid" and not postprocessed:
        verdict = "raw TopoDroid export (pre-import: fix-up chain will run on load)"
    elif cid == "topodroid":
        verdict = "post-import (TopoDroid origin, already processed by cSurvey)"
    elif cid == "csurvey":
        verdict = "native cSurvey"
    elif creatid is None:
        verdict = "other (no creatid attribute)"
    else:
        verdict = "other (creatid=%r)" % creatid

    datatables = props.find("datatables") if props is not None else None
    field_defs = {t: read_datafields(datatables, t)
                  for t in ("segments", "trigpoints", "designitems")}

    # --- centerline -------------------------------------------------------
    seg_el = root.find("segments")
    segments = seg_el.findall("segment") if seg_el is not None else []
    n_segments = len(segments)
    n_splays = sum(1 for s in segments if s.get("splay") == "1")
    n_lrud = sum(
        1 for s in segments
        if any(inv_float(s.get(a)) != 0.0 for a in ("l", "r", "u", "d")))
    n_distox = sum(
        1 for s in segments if any(a in s.attrib for a in DISTOX_ATTRS))

    import_stamps = {}
    for s in segments:
        row = decode_datarow(s.find("datarow"), field_defs["segments"])
        for f in IMPORT_STAMP_FIELDS:
            if f in row:
                bucket = import_stamps.setdefault(f, {})
                bucket[row[f]] = bucket.get(row[f], 0) + 1
    # keep distinct values bounded (import_date can be per-shot)
    for f, bucket in import_stamps.items():
        if len(bucket) > 10:
            vals = sorted(bucket)
            import_stamps[f] = {
                "distinct_values": len(bucket),
                "first": vals[0],
                "last": vals[-1],
                "stamped_rows": sum(bucket.values()),
            }
        else:
            import_stamps[f] = dict(sorted(bucket.items()))

    tp_el = root.find("trigpoints")
    n_trigpoints = len(tp_el.findall("trigpoint")) if tp_el is not None else 0

    caveinfos = props.find("caveinfos") if props is not None else None
    caves = caveinfos.findall("caveinfo") if caveinfos is not None else []
    sessions_el = props.find("sessions") if props is not None else None
    n_sessions = (len(sessions_el.findall("session"))
                  if sessions_el is not None else 0)

    # --- sketch (the headline) -------------------------------------------
    plan = inspect_design(root.find("plan"))
    profile = inspect_design(root.find("profile"))
    total_items = (plan["nested_items"] + plan["flat_items"]
                   + profile["nested_items"] + profile["flat_items"])

    # --- cross-sections / calculate --------------------------------------
    cs_el = root.find("crosssections")
    n_cs = len(cs_el.findall("crosssection")) if cs_el is not None else 0

    calc_el = root.find("calculate")
    calc = {"present": calc_el is not None, "stations": 0,
            "has_speleometrics": False}
    if calc_el is not None:
        ts = calc_el.find("ts")
        calc["stations"] = len(ts.findall("t")) if ts is not None else 0
        sms = calc_el.find("sms")
        calc["has_speleometrics"] = (sms is not None
                                     and sms.find("sm") is not None)

    return {
        "path": path,
        "file": os.path.basename(path),
        "container": container,
        "provenance": {
            "verdict": verdict,
            "creatid": creatid,
            "creatversion": pa.get("creatversion"),
            "creatdate": pa.get("creatdate"),
            "creat_postprocessed": postprocessed,
            "file_version": root.get("version"),
            "survey_name": pa.get("name") or None,
            "custom_fields": {k: v for k, v in field_defs.items() if v},
            "import_stamps": import_stamps,
        },
        "centerline": {
            "segments": n_segments,
            "splays": n_splays,
            "shots": n_segments - n_splays,
            "trigpoints": n_trigpoints,
            "lrud_nonzero": n_lrud,
            "distox_attr_segments": n_distox,
            "caves": len(caves),
            "branches": sum(count_branches(c) for c in caves),
            "sessions": n_sessions,
            "origin": pa.get("origin") or None,
        },
        "sketch": {
            "plan": plan,
            "profile": profile,
            "total_items": total_items,
        },
        "crosssections": n_cs,
        "calculate": calc,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# human report

def human_size(n):
    # decimal units, matching the verified baseline table in the task brief
    if n >= 1000 * 1000:
        return "%.2f MB" % (n / 1e6)
    if n >= 1000:
        return "%.0f KB" % (n / 1e3)
    return "%d B" % n


def fmt_design(name, d):
    lines = []
    nested = d["nested_items"]
    flat = d["flat_items"]
    layer_bits = ", ".join("%s: %d" % (k, v)
                           for k, v in sorted(d["nested_by_layer"].items()))
    lines.append("    %-8s nested (native <layers> shape):        %d%s"
                 % (name, nested, ("   [%s]" % layer_bits) if layer_bits else ""))
    type_bits = ", ".join("%s: %d" % (k, v)
                          for k, v in sorted(d["flat_by_type"].items()))
    lines.append("    %-8s flat <item> (raw TopoDroid shape):     %d%s"
                 % ("", flat, ("   [%s]" % type_bits) if type_bits else ""))
    if d["flat_names"]:
        top = sorted(d["flat_names"].items(), key=lambda kv: (-kv[1], kv[0]))[:8]
        lines.append("    %-8s flat item symbols: %s"
                     % ("", ", ".join("%s×%d" % (k, v) for k, v in top)))
    if not d["has_layers_element"] and nested == 0:
        lines.append("    %-8s (no <layers> element at all)" % "")
    if d["points_total"]:
        unbound = d["points_total"] - d["points_bound"]
        extra = ("  ⚠ unbound points do not warp" if unbound else "")
        lines.append("    %-8s points: %d total, %d bound / %d unbound%s"
                     % ("", d["points_total"], d["points_bound"], unbound, extra))
        if d["items_without_bound_points"]:
            lines.append("    %-8s items with zero bound points: %d (will not warp)"
                         % ("", d["items_without_bound_points"]))
        if d["bbox"]:
            lines.append("    %-8s geometry: bbox [%.2f..%.2f]×[%.2f..%.2f] m, "
                         "coord-sum %.2f"
                         % ("", d["bbox"][0], d["bbox"][2],
                            d["bbox"][1], d["bbox"][3], d["coord_sum"]))
    if d["points_parse_warnings"]:
        lines.append("    %-8s ⚠ %d points-data parse warnings"
                     % ("", d["points_parse_warnings"]))
    return lines


def print_report(r):
    c = r["container"]
    p = r["provenance"]
    cl = r["centerline"]
    sk = r["sketch"]

    print("=" * 72)
    print(r["path"])
    print("-" * 72)
    for w in r["warnings"]:
        print("  ⚠ %s" % w)

    if c["format"] == "csx":
        print("  Container:   bare XML (.csx), %s" % human_size(c["xml_bytes"]))
    else:
        asset_bits = ", ".join("%s: %d" % (k, len(v))
                               for k, v in c["assets"].items())
        print("  Container:   zip, %d entries, _data.xml %s%s"
              % (c["entries"], human_size(c["xml_bytes"]),
                 ("   [assets — %s]" % asset_bits) if asset_bits else ""))

    print("  Provenance:  %s" % p["verdict"])
    print("               creatid=%s  creatversion=%s  file version=%s  "
          "creat_postprocessed=%s"
          % (p["creatid"] or "—", p["creatversion"] or "—",
             p["file_version"], "yes" if p["creat_postprocessed"] else "no"))
    if p["survey_name"]:
        print("               survey name: %s" % p["survey_name"])
    if p["custom_fields"]:
        for tbl, fields in sorted(p["custom_fields"].items()):
            print("               custom %s fields: %s" % (tbl, ", ".join(fields)))
    if p["import_stamps"]:
        for f, vals in sorted(p["import_stamps"].items()):
            print("               %s: %s" % (f, json.dumps(vals, ensure_ascii=False)))

    print("  Centerline:  %d segments = %d shots + %d splays; "
          "%d trigpoints; LRUD≠0 on %d"
          % (cl["segments"], cl["shots"], cl["splays"],
             cl["trigpoints"], cl["lrud_nonzero"]))
    print("               caves: %d, branches: %d, sessions: %d, origin: %s"
          % (cl["caves"], cl["branches"], cl["sessions"],
             cl["origin"] or "— (none set!)"))
    if cl["distox_attr_segments"]:
        print("               raw DistoX attrs (g/m/dip/distox) on %d segments "
              "— raw TopoDroid marker" % cl["distox_attr_segments"])

    print("  Sketch:      TOTAL DRAWING ITEMS: %d   ← the headline number"
          % sk["total_items"])
    for line in fmt_design("plan", sk["plan"]):
        print(line)
    for line in fmt_design("profile", sk["profile"]):
        print(line)

    print("  X-sections:  %d" % r["crosssections"])
    calc = r["calculate"]
    if calc["present"]:
        print("  Calculate:   cached results present (%d stations%s)"
              % (calc["stations"],
                 ", speleometrics" if calc["has_speleometrics"] else ""))
    else:
        print("  Calculate:   ABSENT — cSurvey will recalculate on load "
              "(needs therion)")


def print_summary_table(reports):
    print()
    print("Summary" + " " * 24 +
          "(items = nested + flat, both designs)")
    hdr = ("%-28s %9s %6s %7s %7s %6s %6s %-10s"
           % ("File", "XML", "Segs", "Splays", "LRUD≠0", "Trig", "Items",
              "creatid"))
    print(hdr)
    print("-" * len(hdr))
    for r in reports:
        cl = r["centerline"]
        print("%-28s %9s %6d %7d %7d %6d %6d %-10s"
              % (r["file"][:28], human_size(r["container"]["xml_bytes"]),
                 cl["segments"], cl["splays"], cl["lrud_nonzero"],
                 cl["trigpoints"], r["sketch"]["total_items"],
                 r["provenance"]["creatid"] or "—"))


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Read-only inspector for cSurvey .csz/.csx survey files "
                    "(Stage 0 of the MCP roadmap).")
    ap.add_argument("files", nargs="+", help=".csz or .csx file(s)")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit JSON (stable key order — designed for diffing "
                         "two reports)")
    ap.add_argument("-o", "--out", metavar="FILE",
                    help="write the report to FILE as BOM-free UTF-8 "
                         "(PowerShell's '>' redirection adds a BOM that "
                         "breaks strict JSON parsers — prefer -o)")
    args = ap.parse_args(argv)

    reports = []
    failed = False
    for path in args.files:
        try:
            reports.append(inspect(path))
        except Exception as e:
            failed = True
            if args.as_json:
                reports.append({"path": path, "error": str(e)})
            else:
                print("ERROR: %s: %s" % (path, e), file=sys.stderr)

    if (args.out and os.path.exists(args.out)
            and all("error" in r for r in reports)):
        # never clobber an existing report with an error-only payload
        print("ERROR: nothing inspectable; leaving existing %s untouched"
              % args.out, file=sys.stderr)
        return 1

    out = (open(args.out, "w", encoding="utf-8", newline="\n")
           if args.out else sys.stdout)
    try:
        if args.as_json:
            payload = reports[0] if len(reports) == 1 else reports
            print(json.dumps(payload, indent=2, sort_keys=True,
                             ensure_ascii=False), file=out)
        else:
            import contextlib
            with contextlib.redirect_stdout(out):
                for r in reports:
                    if "error" not in r:
                        print_report(r)
                if len([r for r in reports if "error" not in r]) > 1:
                    print_summary_table([r for r in reports if "error" not in r])
    finally:
        if out is not sys.stdout:
            out.close()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
