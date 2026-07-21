#!/usr/bin/env python3
"""Generate the TDX -> cSurvey mapping workbench: two local HTML pages.

  tdx-mapping-workbench.html  — one row per TopoDroid tool (numbered T1..),
      showing its icon, current import outcome, the current cSurvey target AS
      A PICTURE, and an input box: type a target number (live preview) and
      press "Export tdx-mapping.json" to download the mapping file. Replace
      dev/tools/tdx-mapping.json with it and re-run preprocess_tdx_csx.py.

  cs-targets.html             — the numbered menu of every cSurvey target:
      point glyphs (1..N, real gallery SVGs), line types (101..113) and area
      types (201..206) with stylized previews. Open side-by-side with the
      workbench.

Input semantics in the workbench (documented on the page):
  empty          -> default behavior (whatever the converter does naturally)
  <number>       -> map to that cSurvey target (points 1..99 for point rows,
                    101..113 for line rows, 201..206 for area rows)
  label:TEXT     -> convert the point to a text label saying TEXT
  leave          -> keep as-is and silence pre-processor warnings

Usage: python dev/tools/make_signs_catalog.py
Defaults: cSurvey glyphs from C:\\csurvey64\\Objects\\Cliparts\\Signs, TDX
symbols from dev/literature/topodroid/symbols-git, current mapping from
dev/tools/tdx-mapping.json, outputs next to this script.
"""

import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SIGN_NAMES = {0:"Undefined",257:"Continuation",258:"NarrowEnd",259:"LowEnd",
260:"FlowstoneChoke",261:"BreakdownChoke",262:"ClayChoke",263:"Entrance",
513:"FlowStone",514:"Moonmilk",515:"Stalactite",516:"Stalactites",
517:"Stalagmite",518:"Stalagmites",519:"Pillar",520:"Pillars",521:"Curtain",
522:"SodaStraw",523:"Popcorn",524:"CavePearl",525:"Disk",526:"Helictite",
527:"Aragonite",528:"Crystal",529:"WallCalcite",530:"Gypsum",
531:"GypsumFlower",532:"Anastomosis",533:"Karren",534:"Scallop",535:"Flute",
536:"RaftCone",537:"ClayTree",538:"RimstonePool",539:"RimstoneDam",
769:"ArcheoMaterial",770:"PaleoMaterial",771:"VegetableDebris",772:"Root",
773:"Dig",774:"AirDraught",775:"AirDraughtSummer",776:"AirDraughtWinter",
777:"WaterFlow",778:"WaterFlowIntermittent",779:"WaterFlowPaleo",
780:"Waterfall",781:"Spring",782:"Sink",783:"IceStalactite",
784:"IceStalagmite",785:"IcePillar",786:"Gradient",1025:"Camp",1026:"Anchor",
1027:"Rope",1028:"RopeLadder",1029:"FixedLadder",1030:"Steps",
1031:"ViaFerrata",1032:"Traverse",1033:"Bridge",1034:"Handrail",1281:"Ice",
1282:"Snow",1283:"Water",1284:"Pebbles",1285:"Clay",1286:"Raft",
1287:"Guano",1288:"Sand",1289:"Debrits",1290:"Blocks",1291:"Rock"}

STRIPPED_TO_SIGN = {n.lower(): v for v, n in SIGN_NAMES.items()}

LINE_TARGETS = [  # number 101.. in this order
    ("wall", "cave border — inverted filled area (Borders)"),
    ("wall:presumed", "presumed cave border (Borders)"),
    ("presumed", "presumed border line (Borders)"),
    ("border", "plain border line (Borders)"),
    ("overhang", "overhang curve (Water/floor)"),
    ("pit", "cliff/drop curve (Water/floor)"),
    ("chimney", "ceiling cliff curve (Ceiling)"),
    ("slope", "level/slope curve (Water/floor)"),
    ("floor-meander", "meander (Water/floor)"),
    ("ceiling-meander", "meander (Ceiling)"),
    ("rock-border", "rock area (Rocks)"),
    ("water-flow", "watercourse line (Water/floor)"),
    ("section", "x-section placeholder (Water/floor)"),
]

AREA_TARGETS = [  # number 201..
    ("water", "water area (Water/floor)"),
    ("sand", "sand soil"),
    ("clay", "soil, sand brush (no clay brush exists)"),
    ("debris", "small-debris soil"),
    ("blocks", "big-debris soil"),
    ("pebbles", "pebbles soil"),
]

# stylized previews — the real cSurvey rendering differs in detail
LINE_PREVIEWS = {
    "wall": '<path d="M2,10 L46,7 L46,21 L2,21 Z" style="fill:#ccc;stroke:none"/><path d="M2,10 L46,7" style="stroke:#000;stroke-width:2"/>',
    "wall:presumed": '<path d="M2,10 L46,7 L46,21 L2,21 Z" style="fill:#e2e2e2;stroke:none"/><path d="M2,10 L46,7" style="stroke:#000;stroke-width:2;stroke-dasharray:5,3"/>',
    "presumed": '<path d="M2,13 L46,11" style="stroke:#000;stroke-width:1;stroke-dasharray:4,3"/>',
    "border": '<path d="M2,13 L46,11" style="stroke:#000;stroke-width:1"/>',
    "overhang": '<path d="M2,13 Q24,8 46,12" style="stroke:#000;stroke-width:1;stroke-dasharray:7,2,2,2"/>',
    "pit": '<path d="M2,11 L46,11" style="stroke:#000;stroke-width:1"/><path d="M8,11 L8,16 M16,11 L16,16 M24,11 L24,16 M32,11 L32,16 M40,11 L40,16" style="stroke:#000;stroke-width:0.8"/>',
    "chimney": '<path d="M2,15 L46,15" style="stroke:#000;stroke-width:1;stroke-dasharray:5,2"/><path d="M8,15 L8,10 M16,15 L16,10 M24,15 L24,10 M32,15 L32,10 M40,15 L40,10" style="stroke:#000;stroke-width:0.8"/>',
    "slope": '<path d="M2,12 L46,12" style="stroke:#000;stroke-width:1"/><path d="M10,12 L10,18 M22,12 L22,18 M34,12 L34,18" style="stroke:#000;stroke-width:0.8"/>',
    "floor-meander": '<path d="M2,16 L10,8 L18,16 L26,8 L34,16 L42,8 L46,12" style="fill:none;stroke:#000;stroke-width:1"/>',
    "ceiling-meander": '<path d="M2,16 L10,8 L18,16 L26,8 L34,16 L42,8 L46,12" style="fill:none;stroke:#000;stroke-width:1;stroke-dasharray:4,2"/>',
    "rock-border": '<path d="M8,18 L4,10 L14,5 L30,4 L44,9 L40,19 L24,21 Z" style="fill:#eee;stroke:#000;stroke-width:1"/>',
    "water-flow": '<path d="M2,13 Q24,9 46,13" style="fill:none;stroke:#06c;stroke-width:1.4"/><path d="M38,10 L46,13 L38,16" style="fill:none;stroke:#06c;stroke-width:1"/>',
    "section": '<path d="M2,13 L46,11" style="stroke:#888;stroke-width:1.6;stroke-dasharray:6,3"/>',
}

AREA_PREVIEWS = {
    "water": '<rect x="4" y="4" width="40" height="18" style="fill:#e6f2ff;stroke:#06c;stroke-width:0.8"/><path d="M8,10 Q12,7 16,10 Q20,13 24,10 Q28,7 32,10 M8,17 Q12,14 16,17 Q20,20 24,17 Q28,14 32,17" style="fill:none;stroke:#06c;stroke-width:0.8"/>',
    "sand": '<rect x="4" y="4" width="40" height="18" style="fill:#fff;stroke:#000;stroke-width:0.6"/>' + "".join('<circle cx="%d" cy="%d" r="0.7" style="fill:#000"/>' % (x, y) for x, y in [(9,9),(15,13),(21,8),(27,15),(33,9),(39,13),(12,18),(24,19),(36,18),(18,11),(30,12)]),
    "clay": '<rect x="4" y="4" width="40" height="18" style="fill:#fff;stroke:#000;stroke-width:0.6"/>' + "".join('<circle cx="%d" cy="%d" r="0.7" style="fill:#666"/>' % (x, y) for x, y in [(10,10),(18,14),(26,9),(34,15),(40,10),(14,18),(30,18)]),
    "debris": '<rect x="4" y="4" width="40" height="18" style="fill:#fff;stroke:#000;stroke-width:0.6"/>' + "".join('<circle cx="%d" cy="%d" r="1.8" style="fill:none;stroke:#000;stroke-width:0.6"/>' % (x, y) for x, y in [(10,10),(18,15),(26,8),(34,14),(40,9),(14,19)]),
    "blocks": '<rect x="4" y="4" width="40" height="18" style="fill:#fff;stroke:#000;stroke-width:0.6"/><path d="M8,14 L11,8 L17,9 L15,16 Z M20,18 L22,11 L29,12 L27,19 Z M31,13 L34,6 L41,8 L38,15 Z" style="fill:none;stroke:#000;stroke-width:0.7"/>',
    "pebbles": '<rect x="4" y="4" width="40" height="18" style="fill:#fff;stroke:#000;stroke-width:0.6"/>' + "".join('<ellipse cx="%d" cy="%d" rx="3" ry="2.2" style="fill:none;stroke:#000;stroke-width:0.6"/>' % (x, y) for x, y in [(11,10),(20,15),(29,9),(38,14),(15,19)]),
}

SET_ORDER = ["symbols_speleo", "symbols_extra", "symbols_karst",
             "symbols_geo", "symbols_mine", "symbols_archeo",
             "symbols_anthro", "symbols_paleo", "symbols_bio"]

sys.path.insert(0, HERE)
import preprocess_tdx_csx as PP  # noqa: E402


# ---------------------------------------------------------------------------
# cSurvey glyphs

def isolate_svg(text, idx, size=48):
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    prefix = "g%d_" % idx
    for cls in set(re.findall(r"\.([A-Za-z_][\w-]*)\s*\{", text)):
        text = re.sub(r"\.%s\b" % re.escape(cls), "." + prefix + cls, text)
        text = re.sub(r'class="([^"]*)\b%s\b([^"]*)"' % re.escape(cls),
                      lambda m: 'class="%s%s%s%s"' % (m.group(1), prefix, cls,
                                                      m.group(2)), text)
    for iid in set(re.findall(r'\bid="([^"]+)"', text)):
        text = text.replace('id="%s"' % iid, 'id="%s%s"' % (prefix, iid))
        text = text.replace("url(#%s)" % iid, "url(#%s%s)" % (prefix, iid))
        text = text.replace('href="#%s"' % iid, 'href="#%s%s"' % (prefix, iid))
    text = re.sub(r'\bwidth="[^"]*"', 'width="%d"' % size, text, count=1)
    text = re.sub(r'\bheight="[^"]*"', 'height="%d"' % size, text, count=1)
    return text.replace("<svg ", '<svg class="autofit" ', 1)


def load_cs_points(signs_dir):
    """-> ordered list of (number, sign_value, enum_name, app_name, svg)."""
    by_sign = {}
    idx = 0
    for fn in sorted(os.listdir(signs_dir), key=str.lower):
        if not fn.lower().endswith(".svg"):
            continue
        text = open(os.path.join(signs_dir, fn), encoding="utf-8",
                    errors="replace").read()
        m = re.search(r'csurvey:sign="(\d+)"', text[:4000])
        if not m:
            continue
        sign = int(m.group(1))
        if sign == 0 or sign in by_sign:
            continue
        idx += 1
        by_sign[sign] = (os.path.splitext(fn)[0], isolate_svg(text, idx))
    out = []
    for n, sign in enumerate(sorted(by_sign), start=1):
        app, svg = by_sign[sign]
        out.append((n, sign, SIGN_NAMES.get(sign, "?"), app, svg))
    return out


# ---------------------------------------------------------------------------
# TDX symbols

def parse_tdx_symbol(path):
    meta = {"kind": None, "name": None, "name_it": None, "th_name": None}
    elements, cur, inside = [], [], False
    for raw in open(path, encoding="utf-8", errors="replace").read().splitlines():
        t = raw.strip().split()
        if not t:
            continue
        key = t[0]
        if key == "symbol" and len(t) > 1:
            meta["kind"] = t[1]
        elif key == "name":
            meta["name"] = " ".join(t[1:])
        elif key == "name-it":
            meta["name_it"] = " ".join(t[1:])
        elif key == "th_name":
            meta["th_name"] = " ".join(t[1:])
        elif key == "path":
            inside = True
        elif key == "endpath":
            inside = False
            if cur:
                elements.append(("path", " ".join(cur)))
                cur = []
        elif inside:
            try:
                if key in ("moveTo", "moveT0"):
                    cur.append("M %s %s" % (t[1], t[2]))
                elif key == "lineTo":
                    cur.append("L %s %s" % (t[1], t[2]))
                elif key == "cubicTo":
                    cur.append("C %s %s %s %s %s %s" % tuple(t[1:7]))
                elif key == "addCircle":
                    elements.append(("circle", (t[1], t[2], t[3])))
                elif key == "arcTo":
                    cur.append("L %s %s" % (t[3], t[4]))
            except IndexError:
                pass
    if cur:
        elements.append(("path", " ".join(cur)))
    return meta, elements


def tdx_svg(elements, kind):
    fill = "#ddd" if kind == "area" else "none"
    parts = []
    for etype, data in elements:
        if etype == "path":
            parts.append('<path d="%s" style="fill:%s;stroke:#000;stroke-width:0.6"/>'
                         % (data, fill))
        else:
            cx, cy, r = data
            parts.append('<circle cx="%s" cy="%s" r="%s" style="fill:none;stroke:#000;stroke-width:0.6"/>'
                         % (cx, cy, r))
    return ('<svg class="autofit" xmlns="http://www.w3.org/2000/svg" width="48" '
            'height="48" viewBox="-12 -12 24 24">%s</svg>' % "".join(parts))


# ---------------------------------------------------------------------------
# outcome / current target resolution

def resolve_point(name, sign_to_num, glyphs):
    """-> (verdict, css, target_number_or_None, explicit_input_prefill)."""
    n = name.lower()
    if n in PP.POINT_TO_LABEL:
        return ('label “%s”' % PP.POINT_TO_LABEL[n], "ok", None,
                "label:" + PP.POINT_TO_LABEL[n])
    explicit = n in PP.POINT_RENAMES
    n2 = PP.POINT_RENAMES.get(n, n)
    if n2 == "label":
        return ("text label", "ok", None, "")
    if n2 == "section":
        return ("cross-section", "ok", None, "")
    stripped = n2.replace("-", "").replace("_", "")
    if stripped in STRIPPED_TO_SIGN:
        v = STRIPPED_TO_SIGN[stripped]
        num = sign_to_num.get(v)
        verdict = SIGN_NAMES[v] + (" — renders" if v in glyphs
                                   else " — NO GLYPH, X-box")
        css = "ok" if v in glyphs else "warn"
        return (verdict, css, num, str(num) if explicit and num else "")
    return ("UNMAPPED — X-box", "bad", None, "")


def resolve_line(name, name_to_num):
    n = name.lower()
    explicit = n in PP.LINE_RENAMES
    n2 = PP.LINE_RENAMES.get(n, n)
    if (PP.GENERIC.get("strip_line_subtypes") and ":" in n2
            and n2 != "wall:presumed"):
        base = n2.split(":", 1)[0]
        if base in PP.LINE_BASES:
            n2 = base
    if n2 in name_to_num:
        num = name_to_num[n2]
        return (n2, "ok", num, str(num) if explicit else "")
    return ("plain border (fallback)", "warn", name_to_num["border"], "")


def resolve_area(name, name_to_num):
    n = name.lower()
    explicit = n in PP.AREA_RENAMES
    n2 = PP.AREA_RENAMES.get(n, n)
    if (PP.GENERIC.get("strip_area_suffix") and n2.endswith("-area")
            and n2[:-5] in PP.AREA_BASES):
        n2 = n2[:-5]
    if n2 in name_to_num:
        num = name_to_num[n2]
        return (n2, "ok", num, str(num) if explicit else "")
    return ("generic soil (fallback)", "warn", None, "")


STYLE = """
 body{font-family:Segoe UI,sans-serif;margin:20px;background:#fafafa;color:#222}
 h1{font-size:19px} h2{font-size:15px;margin:26px 0 8px;border-bottom:2px solid #ccc}
 .row{display:flex;gap:12px;align-items:center;background:#fff;border:1px solid #ddd;
      border-radius:8px;padding:6px 12px;margin-bottom:6px;max-width:980px}
 .num{font-weight:700;font-size:15px;width:52px;flex:none;color:#333}
 .glyph{width:48px;height:48px;flex:none;display:flex;align-items:center;justify-content:center}
 .glyph svg{max-width:48px;max-height:48px;overflow:visible}
 .glyph svg *{vector-effect:non-scaling-stroke}
 .meta{font-size:12.5px;line-height:1.4;flex:1}
 .it{color:#046} .out{font-weight:600} .ok{color:#071} .warn{color:#b60} .bad{color:#b00}
 .tgt{width:64px;height:34px;flex:none;display:flex;align-items:center;justify-content:center;
      border-left:1px dashed #ccc;padding-left:10px}
 .tgt svg{max-width:60px;max-height:34px}
 input.map{width:80px;flex:none;font-size:14px;padding:3px 6px}
 .note{background:#ffe;border:1px solid #dda;padding:8px 12px;border-radius:6px;max-width:960px;font-size:13px}
 button{font-size:14px;padding:6px 14px;margin:8px 0}
 .arrow{flex:none;color:#999;font-size:16px}
"""

AUTOFIT_JS = """
function autofit(){
  document.querySelectorAll('svg.autofit').forEach(function(s){
    try{ var b=s.getBBox();
      if(b.width>0.01&&b.height>0.01){var p=0.12*Math.max(b.width,b.height);
        s.setAttribute('viewBox',(b.x-p)+' '+(b.y-p)+' '+(b.width+2*p)+' '+(b.height+2*p));}
    }catch(e){}});
}
window.addEventListener('load', autofit);
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--signs-dir", default=r"C:\csurvey64\Objects\Cliparts\Signs")
    ap.add_argument("--tdx-dir", default=os.path.join(
        REPO, "dev", "literature", "topodroid", "symbols-git"))
    ap.add_argument("--map", dest="map_file", default=PP.DEFAULT_MAP)
    args = ap.parse_args(argv)

    if os.path.exists(args.map_file):
        PP.load_mapping(args.map_file)
    cs_points = load_cs_points(args.signs_dir)
    glyphs = {sign for _, sign, _, _, _ in cs_points}
    sign_to_num = {sign: n for n, sign, _, _, _ in cs_points}
    line_to_num = {name: 101 + i for i, (name, _) in enumerate(LINE_TARGETS)}
    area_to_num = {name: 201 + i for i, (name, _) in enumerate(AREA_TARGETS)}

    # ---- cs-targets.html -------------------------------------------------
    rows = []
    for n, sign, ename, app, svg in cs_points:
        rows.append('<div class="row"><div class="num">%d</div>'
                    '<div class="glyph">%s</div><div class="meta"><b>%s</b> '
                    '<span class="it">app: %s</span> <span>(sign %d)</span>'
                    '</div></div>' % (n, svg, html.escape(ename),
                                      html.escape(app), sign))
    lrows = []
    for i, (name, desc) in enumerate(LINE_TARGETS):
        lrows.append('<div class="row"><div class="num">%d</div>'
                     '<div class="glyph"><svg class="noscale" width="60" height="30" '
                     'viewBox="0 0 48 26">%s</svg></div><div class="meta"><b>%s</b> '
                     '— %s</div></div>'
                     % (101 + i, LINE_PREVIEWS[name], html.escape(name),
                        html.escape(desc)))
    arows = []
    for i, (name, desc) in enumerate(AREA_TARGETS):
        arows.append('<div class="row"><div class="num">%d</div>'
                     '<div class="glyph"><svg class="noscale" width="60" height="30" '
                     'viewBox="0 0 48 26">%s</svg></div><div class="meta"><b>%s</b> '
                     '— %s</div></div>'
                     % (201 + i, AREA_PREVIEWS[name], html.escape(name),
                        html.escape(desc)))

    cs_page = """<!doctype html><html><head><meta charset="utf-8">
<title>cSurvey targets (numbered)</title><style>%s</style></head><body>
<h1>cSurvey targets — the numbered menu</h1>
<p class="note">Use these numbers in the mapping workbench. Point glyphs are the real
gallery SVGs from the installed build; line/area previews are stylized approximations.</p>
<h2>Points (type the number in a point row)</h2>%s
<h2>Lines (101–113, for line rows)</h2>%s
<h2>Areas (201–206, for area rows)</h2>%s
<script>%s</script></body></html>""" % (
        STYLE, "\n".join(rows), "\n".join(lrows), "\n".join(arows), AUTOFIT_JS)

    cs_out = os.path.join(HERE, "cs-targets.html")
    with open(cs_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(cs_page)

    # ---- workbench -------------------------------------------------------
    # target preview templates for live JS preview
    templates, js_names = [], {}
    for n, sign, ename, app, svg in cs_points:
        templates.append('<template id="cs-%d">%s<div>%s</div></template>'
                         % (n, svg, html.escape(ename)))
        js_names[n] = SIGN_NAMES[sign].lower()
    for i, (name, _) in enumerate(LINE_TARGETS):
        templates.append('<template id="cs-%d"><svg width="60" height="30" '
                         'viewBox="0 0 48 26">%s</svg><div>%s</div></template>'
                         % (101 + i, LINE_PREVIEWS[name], html.escape(name)))
        js_names[101 + i] = name
    for i, (name, _) in enumerate(AREA_TARGETS):
        templates.append('<template id="cs-%d"><svg width="60" height="30" '
                         'viewBox="0 0 48 26">%s</svg><div>%s</div></template>'
                         % (201 + i, AREA_PREVIEWS[name], html.escape(name)))
        js_names[201 + i] = name

    sections = []
    tnum = 0
    for symset in SET_ORDER:
        setdir = os.path.join(args.tdx_dir, symset)
        if not os.path.isdir(setdir):
            continue
        srows = []
        for kind in ("point", "line", "area"):
            kdir = os.path.join(setdir, kind)
            if not os.path.isdir(kdir):
                continue
            for fn in sorted(os.listdir(kdir), key=str.lower):
                p = os.path.join(kdir, fn)
                if not os.path.isfile(p):
                    continue
                meta, elements = parse_tdx_symbol(p)
                th = (meta["th_name"] or fn).replace("=", ":")
                if kind == "point":
                    verdict, css, tno, prefill = resolve_point(
                        th, sign_to_num, glyphs)
                elif kind == "line":
                    verdict, css, tno, prefill = resolve_line(th, line_to_num)
                else:
                    verdict, css, tno, prefill = resolve_area(th, area_to_num)
                tnum += 1
                it = meta["name_it"] or ""
                srows.append("""
<div class="row" data-kind="%s" data-name="%s">
 <div class="num">T%d</div>
 <div class="glyph">%s</div>
 <div class="meta"><b>%s</b> <span>(%s)</span><br><span class="it">%s</span>
  <span class="out %s">%s</span></div>
 <div class="arrow">→</div>
 <div class="tgt" data-init="%s"></div>
 <input class="map" placeholder="" value="%s" title="number, label:TEXT, or leave">
</div>""" % (kind, html.escape(th), tnum, tdx_svg(elements, kind),
             html.escape(th), kind, html.escape(it), css,
             html.escape(verdict), tno or "", html.escape(prefill)))
        if srows:
            sections.append("<h2>%s (%d tools)</h2>%s"
                            % (html.escape(symset.replace("symbols_", "")),
                               len(srows), "\n".join(srows)))

    wb_js = """
var CS_NAMES = %s;
function setPreview(row, val){
  var tgt = row.querySelector('.tgt');
  var n = parseInt(val, 10);
  if(!val){ n = parseInt(tgt.getAttribute('data-init'), 10); }
  tgt.innerHTML = '';
  if(val && val.indexOf('label:') === 0){ tgt.textContent = '"' + val.substring(6) + '"'; return; }
  if(val === 'leave'){ tgt.textContent = '(leave)'; return; }
  var t = document.getElementById('cs-' + n);
  if(t){ tgt.appendChild(t.content.cloneNode(true)); }
  else if(val){ tgt.textContent = '?'; }
}
document.querySelectorAll('.row[data-kind]').forEach(function(row){
  var inp = row.querySelector('input.map');
  setPreview(row, inp.value.trim());
  inp.addEventListener('input', function(){ setPreview(row, inp.value.trim()); autofit(); });
});
window.addEventListener('load', function(){
  document.querySelectorAll('.row[data-kind]').forEach(function(row){
    setPreview(row, row.querySelector('input.map').value.trim());
  });
  autofit();
});
function exportMap(){
  var cfg = {points:{}, lines:{}, areas:{},
             generic:{strip_line_subtypes:true, strip_area_suffix:true}};
  var bad = [];
  document.querySelectorAll('.row[data-kind]').forEach(function(row){
    var v = row.querySelector('input.map').value.trim();
    if(!v) return;
    var kind = row.getAttribute('data-kind'), name = row.getAttribute('data-name');
    var section = kind === 'point' ? 'points' : kind === 'line' ? 'lines' : 'areas';
    if(v === 'leave'){ cfg[section][name] = {leave:true}; return; }
    if(v.indexOf('label:') === 0){
      if(kind !== 'point'){ bad.push(name + ': label only for points'); return; }
      cfg[section][name] = {label: v.substring(6)}; return;
    }
    var n = parseInt(v, 10);
    if(isNaN(n) || !CS_NAMES[n]){ bad.push(name + ': unknown target ' + v); return; }
    var okRange = kind === 'point' ? (n < 100) : kind === 'line' ? (n >= 101 && n <= 199)
                : (n >= 201);
    if(!okRange){ bad.push(name + ': ' + v + ' is not a ' + kind + ' target'); return; }
    cfg[section][name] = {to: CS_NAMES[n]};
  });
  if(bad.length){ alert('Fix these first:\\n' + bad.join('\\n')); return; }
  var blob = new Blob([JSON.stringify(cfg, null, 2)], {type:'application/json'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'tdx-mapping.json'; a.click();
}
""" % json.dumps(js_names)

    wb_page = """<!doctype html><html><head><meta charset="utf-8">
<title>TDX mapping workbench</title><style>%s</style></head><body>
<h1>TDX → cSurvey mapping workbench</h1>
<p class="note"><b>How to use:</b> open <code>cs-targets.html</code> in a second window
for the numbered menu. In each row's box type a <b>target number</b> (points take 1–99,
lines 101–113, areas 201–206), or <code>label:TEXT</code> (points only), or
<code>leave</code>. Empty = default behavior. The → preview updates live.
Then press the button — it downloads <code>tdx-mapping.json</code>; replace
<code>dev/tools/tdx-mapping.json</code> with it and re-run
<code>preprocess_tdx_csx.py</code>. Prefilled boxes show the current explicit mapping.</p>
<button onclick="exportMap()">⬇ Export tdx-mapping.json</button>
%s
%s
<button onclick="exportMap()">⬇ Export tdx-mapping.json</button>
<script>%s%s</script></body></html>""" % (
        STYLE, "\n".join(templates), "\n".join(sections), AUTOFIT_JS, wb_js)

    wb_out = os.path.join(HERE, "tdx-mapping-workbench.html")
    with open(wb_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(wb_page)

    old = os.path.join(HERE, "signs-catalog.html")
    if os.path.exists(old):
        os.remove(old)
    print("wrote %s\nwrote %s" % (wb_out, cs_out))


if __name__ == "__main__":
    sys.exit(main())
