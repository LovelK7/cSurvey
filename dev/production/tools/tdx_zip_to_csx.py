"""Regenerate a TopoDroid .csx from a TopoDroid project .zip (manifest + survey.sql + .tdr).

Rescue tool for the TopoDroid 6.4.99 export bugs: the app crashes writing .csx
(0-byte file) and its new-format .tdr sketches (format 604098) are silently
dropped by older app versions. The project zip still contains everything; this
script replays TopoDroid's own csx exporter offline.

Faithful to TopoDroid master source (mirrored in tdsrc/ next to this script):
  - segment state machine  : TDExporter.exportSurveyAsCsx (:310-676)
  - segment/splay/leg attrs: TDExporter writeCsx* helpers (:175-218)
  - item writers           : Drawing{Line,Area,Point,Label}Path.toTCsurvey
  - points data            : DrawingPointLinePath.toCsurveyPoints (:820-913)
  - world coords           : world = (scene - (100,120)) / 20, Y down
  - tdr binary             : parse_tdr.py (same folder)

Known simplifications (fine for these surveys, logged when encountered):
  - x-section points, photos/audio attachments: skipped with a warning
  - bezier segments flattened at 8 samples (TopoDroid uses an adaptive count)

Usage:
  python tdx_zip_to_csx.py <project.zip> [more.zip ...]     one or more zips
  python tdx_zip_to_csx.py <folder>                         every *.zip under the folder (recursive)
  python tdx_zip_to_csx.py <project.zip> -o out.csx         explicit output (single input only)
  --raw-only        skip the symbol-mapping preprocessor (preprocess_tdx_csx.py, run
                    automatically when found next to this script; output <name>_recovered_pp.csx)

Outputs land next to each zip: <survey>_recovered.csx (raw) and <survey>_recovered_pp.csx
(import this one into cSurvey). Paths with spaces are fine — quote them, or use the
recover_tdx.bat drag-and-drop wrapper in the TDX handoff folder.
"""
import io
import os
import re
import sys
import zipfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_tdr import parse_tdr_bytes

CENTER_X, CENTER_Y, SCALE = 100.0, 120.0, 20.0
DECLINATION_UNSET = 1080.0
BEZIER_SAMPLES = 8
CSURVEY_EXTEND = [1, 2, 0]  # index 1+extend for extend in (-1, 0)


def xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def w2(v):
    return "%.2f" % v


# ---------------- survey.sql ----------------

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([-+0-9.eE]+)')


def parse_sql_values(line):
    """Return the values( ... ) tuple of one INSERT line as python values."""
    body = line[line.index("(") + 1:line.rindex(")")]
    vals = []
    for m in _TOKEN.finditer(body):
        if m.group(1) is not None:
            vals.append(m.group(1))
        else:
            t = m.group(2)
            vals.append(float(t) if ("." in t or "e" in t or "E" in t) else int(t))
    return vals


def load_survey_sql(text):
    survey, plots, shots, fixeds = None, [], [], []
    for line in text.splitlines():
        line = line.strip()
        if not line.lower().startswith("insert into"):
            continue
        table = line.split()[2].strip().lower()
        v = parse_sql_values(line)
        if table == "surveys":
            survey = {"name": v[1], "date": v[2], "team": v[3],
                      "declination": float(v[4]), "comment": v[5],
                      "init_station": str(v[6]) if len(v) > 6 else ""}
        elif table == "plots":
            plots.append({"id": v[1], "name": v[2], "type": int(v[3]),
                          "status": int(v[4]), "start": str(v[5])})
        elif table == "shots":
            shots.append({"id": v[1], "from": str(v[2]), "to": str(v[3]),
                          "distance": float(v[4]), "bearing": float(v[5]),
                          "clino": float(v[6]), "roll": float(v[7]),
                          "accel": float(v[8]), "magnetic": float(v[9]),
                          "dip": float(v[10]), "extend": int(v[11]),
                          "flag": int(v[12]), "leg": int(v[13]),
                          "status": int(v[14]), "comment": str(v[15]),
                          "address": str(v[20]) if len(v) > 20 else ""})
        elif table == "fixeds":
            fixeds.append(v)
    return survey, plots, shots, fixeds


# ---------------- sketch items ----------------

def scene_to_world(x, y):
    return (x - CENTER_X) / SCALE, (y - CENTER_Y) / SCALE


def bezier(p0, p1, p2, p3, t):
    u = 1.0 - t
    return (u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
            u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1])


def csurvey_points_data(points, close, reversed_):
    """Replicates DrawingPointLinePath.toCsurveyPoints: world coords, B after
    the first pair, beziers flattened, closed shapes repeat the first vertex."""
    seq = list(reversed(points)) if reversed_ else points
    out = []
    first = seq[0]
    prev = scene_to_world(first["x"], first["y"])
    out.append("%s %s " % (w2(prev[0]), w2(prev[1])))
    out.append("B ")
    for i in range(1, len(seq)):
        pt = seq[i]
        cur = scene_to_world(pt["x"], pt["y"])
        # control points belong to the incoming segment of the *forward* order;
        # when reversed, the reader swaps cp1/cp2 (DrawingPointLinePath :881-885)
        cp_holder = pt if not reversed_ else seq[i - 1]
        cp = cp_holder.get("cp")
        if cp:
            c1 = scene_to_world(cp[0], cp[1])
            c2 = scene_to_world(cp[2], cp[3])
            if reversed_:
                c1, c2 = c2, c1
            for n in range(1, BEZIER_SAMPLES):
                p = bezier(prev, c1, c2, cur, n / float(BEZIER_SAMPLES))
                out.append("%s %s " % (w2(p[0]), w2(p[1])))
        out.append("%s %s " % (w2(cur[0]), w2(cur[1])))
        prev = cur
    if close:
        p0 = scene_to_world(points[0]["x"], points[0]["y"])
        out.append("%s %s " % (w2(p0[0]), w2(p0[1])))
    return "".join(out)


def emit_items(out, tdr, cave, branch, warnings):
    for it in tdr["items"]:
        tag = it["tag"]
        if tag == "line":
            out.append('          <item type="line" name="%s" cave="%s" branch="%s" '
                       'reversed="%d" closed="%d" outline="%d" options="%s" >\n'
                       % (xml_escape(it["name"]), cave, branch,
                          1 if it["reversed"] else 0, 1 if it["closed"] else 0,
                          it["outline"], xml_escape(it.get("options") or "")))
            out.append('            <points data="%s" />\n'
                       % csurvey_points_data(it["points"], it["closed"], it["reversed"]))
            out.append('          </item>\n')
        elif tag == "area":
            out.append('          <item type="area" name="%s" cave="%s" branch="%s" '
                       'orientation="%.2f" options="%s" >\n'
                       % (xml_escape(it["name"]), cave, branch,
                          it.get("orientation", 0.0), xml_escape(it.get("options") or "")))
            out.append('            <points data="%s" />\n'
                       % csurvey_points_data(it["points"], True, False))
            out.append('          </item>\n')
        elif tag == "point":
            if it["name"] == "section":
                warnings.append("x-section point skipped (not supported): %r" % it)
                continue
            x, y = scene_to_world(it["x"], it["y"])
            out.append('<item type="point" name="%s" cave="%s" branch="%s" text="%s" '
                       'scale="%d" orientation="%.2f" options="%s" >\n'
                       % (xml_escape(it["name"]), cave, branch,
                          xml_escape(it.get("text") or ""), it.get("scale", 0),
                          it.get("orientation", 0.0), xml_escape(it.get("options") or "")))
            out.append(' <points data="%s %s " />\n' % (w2(x), w2(y)))
            out.append('</item>\n')
        elif tag == "label":
            x, y = scene_to_world(it["x"], it["y"])
            out.append('<item type="point" name="label" cave="%s" branch="%s" text="%s" '
                       'scale="%d" orientation="%.2f" options="%s" >\n'
                       % (cave, branch, xml_escape(it.get("text") or ""),
                          it.get("scale", 0), it.get("orientation", 0.0),
                          xml_escape(it.get("options") or "")))
            out.append(' <points data="%s %s " />\n' % (w2(x), w2(y)))
            out.append('</item>\n')
        elif tag in ("photo", "audio", "special"):
            warnings.append("%s item skipped (not supported)" % tag)
        # station_user / station_name records are not csx items


# ---------------- segments ----------------

def segment_common(shot, extend):
    a = []
    if extend < 1:
        a.append(' direction="%d"' % CSURVEY_EXTEND[1 + extend])
    a.append(' distance="%.2f" bearing="%.1f" inclination="%.1f"'
             % (shot["distance"], shot["bearing"], shot["clino"]))
    a.append(' g="%.1f" m="%.1f" dip="%.1f"'
             % (shot["accel"], shot["magnetic"], shot["dip"]))
    return a


def emit_segments(out, shots, cave, branch, session):
    """TDExporter.exportSurveyAsCsx shot loop (:474-640): repeats (leg==1)
    average into the previous leg; one-empty-station rows are splays."""
    cnt_splay = 0
    ref = None          # pending leg's first shot
    ref_f = ref_t = ""
    ref_extend = 0
    leg_sum = None      # [n, dist, dx, dy, dz] averaging accumulator

    def leg_avg():
        import math
        n, d, sb, cb, c = leg_sum
        return d / n, (math.degrees(math.atan2(sb, cb)) + 360.0) % 360.0, c / n

    def start_leg(shot):
        import math
        b = math.radians(shot["bearing"])
        return [1, shot["distance"], math.sin(b), math.cos(b), shot["clino"]]

    def add_to_leg(shot):
        import math
        b = math.radians(shot["bearing"])
        leg_sum[0] += 1
        leg_sum[1] += shot["distance"]
        leg_sum[2] += math.sin(b)
        leg_sum[3] += math.cos(b)
        leg_sum[4] += shot["clino"]

    def flush_leg():
        nonlocal ref
        if ref is None:
            return
        d, b, c = leg_avg()
        out.append('<segment id="%d" cave="%s" branch="%s" session="%s" from="%s" to="%s"'
                   % (ref["id"], cave, branch, session, ref_f, ref_t))
        if ref_extend < 1:
            out.append(' direction="%d"' % CSURVEY_EXTEND[1 + ref_extend])
        if ref["flag"] == 2:
            out.append(' exclude="1" duplicate="1"')
        elif ref["flag"] == 1:
            out.append(' exclude="1" surface="1"')
        out.append(' distance="%.2f" bearing="%.1f" inclination="%.1f"' % (d, b, c))
        out.append(' g="%.1f" m="%.1f" dip="%.1f"'
                   % (ref["accel"], ref["magnetic"], ref["dip"]))
        out.append(' l="0" r="0" u="0" d="0"')
        if ref["comment"]:
            out.append(' note="%s"' % xml_escape(ref["comment"]))
        out.append(' distox="%s" >\n    </segment>\n' % ref["address"])
        ref = None

    for shot in shots:
        if shot["status"] != 0:
            continue
        f, t = shot["from"], shot["to"]
        if not f and not t:  # secondary leg / repeat
            if ref is not None and shot["leg"] == 1:
                add_to_leg(shot)
            continue
        if f and t:  # new leg
            flush_leg()
            ref = shot
            ref_f, ref_t = f, t
            ref_extend = shot["extend"]
            leg_sum = start_leg(shot)
            continue
        # splay (exactly one station set)
        flush_leg()
        station = f or t
        if f:
            out.append('<segment id="" cave="%s" branch="%s" session="%s" from="%s" to="%s(%d)"'
                       % (cave, branch, session, station, station, cnt_splay))
        else:
            out.append('<segment id="" cave="%s" branch="%s" session="%s" from="%s(%d)" to="%s"'
                       % (cave, branch, session, station, cnt_splay, station))
        cnt_splay += 1
        if shot["leg"] in (2, 4, 5):  # x/h/v-splay
            out.append(' cut="1"')
        out.append(' splay="1" exclude="1"')
        out.extend(segment_common(shot, shot["extend"]))
        out.append(' l="0" r="0" u="0" d="0"')
        if shot["comment"]:
            out.append(' note="%s"' % xml_escape(shot["comment"]))
        out.append(' distox="%s" >\n    </segment>\n' % shot["address"])
    flush_leg()


# ---------------- main ----------------

def convert(src, out_path=None):
    warnings = []
    if os.path.isdir(src):
        read = lambda name: open(os.path.join(src, name), "rb").read()
        names = os.listdir(src)
    else:
        zf = zipfile.ZipFile(src)
        read = lambda name: zf.read(name)
        names = zf.namelist()

    manifest = read("manifest").decode("utf-8", "replace").splitlines()
    td_version = manifest[0].split()[0] if manifest else "?"
    survey, plots, shots, fixeds = load_survey_sql(read("survey.sql").decode("utf-8", "replace"))
    name = survey["name"]
    cave = xml_escape(name.upper())

    plan = next((p for p in plots if p["type"] == 1 and p["status"] == 0), None)
    prof = next((p for p in plots if p["type"] == 2 and p["status"] == 0), None)
    branch = xml_escape(plan["name"][:-1]) if plan and len(plan["name"]) > 1 else ""

    tdrs = {}
    for p in (plan, prof):
        if p is None:
            continue
        # match by exact name first, then by "-<plot>.tdr" suffix — zip entry
        # names may be mojibake (cp437 vs UTF-8) when the survey name is non-ASCII
        entry = "%s-%s.tdr" % (name, p["name"])
        if entry not in names:
            suffix = "-%s.tdr" % p["name"]
            cands = [n for n in names if n.endswith(suffix)]
            entry = cands[0] if len(cands) == 1 else None
        if entry:
            tdrs[p["name"]] = parse_tdr_bytes(read(entry), entry)
            if not tdrs[p["name"]]["clean_end"]:
                warnings.append("tdr %s did not parse cleanly: %s"
                                % (entry, tdrs[p["name"]]["error"]))
        else:
            warnings.append("tdr entry missing in zip: %s-%s.tdr" % (name, p["name"]))

    # origin: plot start > survey init_station > first from
    origin = None
    for t in tdrs.values():
        pi = t.get("plot_info")
        if pi and pi.get("start"):
            origin = pi["start"]
            break
    if not origin and plan:
        origin = plan["start"]
    if not origin:
        origin = survey.get("init_station")
    if not origin:
        origin = next((s["from"] for s in shots if s["from"]), "0")

    info_date = re.sub(r"[.,\-/]", "", survey["date"])
    session = ("%s_%s" % (info_date, name.replace(" ", "_"))).lower()
    today = date.today().strftime("%Y-%m-%d")
    has_decl = abs(survey["declination"]) < DECLINATION_UNSET

    out = []
    out.append('<csurvey version="1.11" id="">\n')
    out.append('<!-- %s created by TopoDroid v %s (zip2csx recovery) -->\n'
               % (today, td_version))
    out.append('  <properties id="" name="" origin="%s" ' % xml_escape(origin))
    out.append('creatid="TopoDroid" creatversion="%s" creatdate="%s" ' % (td_version, today))
    out.append('calculatemode="1" calculatetype="2" calculateversion="-1" ')
    out.append('ringcorrectionmode="2" nordcorrectionmode="0" inversionmode="1" ')
    out.append('designwarpingmode="1" bindcrosssection="1">\n')
    out.append('    <note />\n')
    out.append('    <sessions>\n')
    out.append('      <session date="%s" description="%s" ' % (survey["date"], cave))
    if survey["team"]:
        out.append(' team="%s" ' % xml_escape(survey["team"]))
    if has_decl:
        out.append('nordtype="0" manualdeclination="1" declination="%.4f" '
                   % survey["declination"])
    else:
        out.append('nordtype="0" manualdeclination="0" ')
    out.append('>\n      </session>\n    </sessions>\n')
    out.append('    <caveinfos>\n      <caveinfo name="%s" color="1724697804"' % cave)
    if survey["comment"]:
        out.append(' comment="%s"\n' % xml_escape(survey["comment"]))
    out.append(' >\n        <branches>\n')
    if branch:
        out.append('          <branch name="%s" color="1731024809">\n          </branch>\n' % branch)
    out.append('        </branches>\n      </caveinfo>\n    </caveinfos>\n')
    out.append('    <gps enabled="0" refpointonorigin="%s" geo="WGS84" format="" sendtotherion="0" />\n'
               % xml_escape(origin))
    out.append('  </properties>\n')

    out.append('  <segments>\n')
    emit_segments(out, shots, cave, branch, session)
    out.append('  </segments>\n')

    out.append('  <trigpoints>\n')
    for v in fixeds:
        warnings.append("fixed point present but not converted: %r" % (v,))
    out.append('  </trigpoints>\n')

    for xml_tag, p in (("plan", plan), ("profile", prof)):
        out.append('  <%s>\n' % xml_tag)
        if p and p["name"] in tdrs:
            emit_items(out, tdrs[p["name"]], cave, branch, warnings)
        out.append('    <plot />\n')
        out.append('  </%s>\n' % xml_tag)
    out.append('</csurvey>\n')

    if out_path is None:
        base = os.path.dirname(os.path.abspath(src))
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "survey"
        out_path = os.path.join(base, safe + "_recovered.csx")
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))

    n_items = sum(len(t["items"]) for t in tdrs.values())
    print("wrote %s" % out_path)
    print("  survey=%s date=%s origin=%s session=%s" % (name, survey["date"], origin, session))
    print("  shots rows=%d  sketch items: %s (total %d)"
          % (len(shots), {k: len(t["items"]) for k, t in tdrs.items()}, n_items))
    for wmsg in warnings:
        print("  WARNING: %s" % wmsg)
    return out_path


def is_project_zip(path):
    """A TopoDroid project zip contains a manifest and survey.sql."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        return "manifest" in names and "survey.sql" in names
    except (zipfile.BadZipFile, OSError):
        return False


def run_preprocessor(csx_path):
    """Run the standing protocol's symbol-mapping preprocessor if it lives
    next to this script. Returns the _pp path or None."""
    import subprocess
    pp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "preprocess_tdx_csx.py")
    if not os.path.isfile(pp):
        print("  (preprocess_tdx_csx.py not found next to this script - raw csx only)")
        return None
    out = os.path.splitext(csx_path)[0] + "_pp.csx"
    r = subprocess.run([sys.executable, pp, csx_path, "-o", out, "--force"])
    if r.returncode != 0:
        print("  WARNING: preprocessor failed on %s" % csx_path)
        return None
    return out


def main(argv):
    out = None
    if "-o" in argv:
        i = argv.index("-o")
        out = argv[i + 1]
        del argv[i:i + 2]
    raw_only = "--raw-only" in argv
    argv = [a for a in argv if not a.startswith("--")]
    if not argv:
        print(__doc__)
        return 1

    # expand: each arg is a zip, an extracted dir, or a folder to scan
    inputs = []
    for a in argv:
        if os.path.isdir(a):
            if os.path.isfile(os.path.join(a, "survey.sql")):  # extracted project
                inputs.append(a)
                continue
            found = []
            for root, _dirs, files in os.walk(a):
                for fn in sorted(files):
                    if fn.lower().endswith(".zip"):
                        p = os.path.join(root, fn)
                        if is_project_zip(p):
                            found.append(p)
                        else:
                            print("skipping (not a TopoDroid project zip): %s" % p)
            inputs.extend(found)
        else:
            inputs.append(a)
    if not inputs:
        print("nothing to do - no TopoDroid project zips found")
        return 1
    if out is not None and len(inputs) > 1:
        print("-o only makes sense with a single input")
        return 1

    failures = 0
    for src in inputs:
        print("=" * 60)
        try:
            csx = convert(src, out)
            if not raw_only:
                pp = run_preprocessor(csx)
                if pp:
                    print("  import-ready: %s" % pp)
        except Exception as e:  # keep going on a bad zip in batch mode
            failures += 1
            print("FAILED %s: %s" % (src, e))
    print("=" * 60)
    print("%d/%d converted" % (len(inputs) - failures, len(inputs)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
