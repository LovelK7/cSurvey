"""Parse TopoDroid .tdr binary sketch files (all format versions through 604098).

Layout transcribed from TopoDroid master source (see tdsrc/ in this folder):
  DrawingIO.java readTdr loop (:734-850), DrawingPointPath/LinePath/AreaPath/
  LabelPath/StationUser/StationName/SpecialPath/PhotoPath/AudioPath
  loadDataStream, LinePoint.toDataStream.

Usage: python parse_tdr.py file1.tdr [file2.tdr ...] [--json out.json] [--items]
"""
import io
import json
import struct
import sys

PLOT_TYPES = {-1: "NULL", 0: "X_SECTION", 1: "PLAN", 2: "EXTENDED", 3: "H_SECTION",
              4: "PHOTO", 5: "SECTION", 6: "SKETCH_3D", 7: "XH_SECTION",
              8: "PROJECTED", 9: "LEG"}


class R:
    def __init__(self, data):
        self.b = data
        self.i = 0

    def eof(self):
        return self.i >= len(self.b)

    def u1(self):
        v = self.b[self.i]
        self.i += 1
        return v

    def i4(self):
        v = struct.unpack_from(">i", self.b, self.i)[0]
        self.i += 4
        return v

    def f4(self):
        v = struct.unpack_from(">f", self.b, self.i)[0]
        self.i += 4
        return v

    def utf(self):
        n = struct.unpack_from(">H", self.b, self.i)[0]
        self.i += 2
        s = self.b[self.i:self.i + n].decode("utf-8", errors="replace")
        self.i += n
        return s


def read_vertices(r, npt):
    pts = []
    for _ in range(npt):
        x, y = r.f4(), r.f4()
        has_cp = r.u1()
        cp = None
        if has_cp == 1:
            cp = (r.f4(), r.f4(), r.f4(), r.f4())
        pts.append({"x": x, "y": y, "cp": cp})
    return pts


def parse_tdr(path):
    return parse_tdr_bytes(open(path, "rb").read(), path)


def parse_tdr_bytes(data, label="<bytes>"):
    r = R(data)
    out = {"file": label, "size": len(data), "version": None, "scrap": None,
           "plot_type": None, "bbox": None, "items": [], "stations": [],
           "counts": {}, "clean_end": False, "error": None, "trailing": 0}
    version = 0

    def bump(k):
        out["counts"][k] = out["counts"].get(k, 0) + 1

    try:
        while not r.eof():
            tag = chr(r.u1())
            if tag == "V":
                version = r.i4()
                out["version"] = version
            elif tag == "S":
                out["scrap"] = r.utf()
                ptype = r.i4()
                out["plot_type"] = PLOT_TYPES.get(ptype, ptype)
                if ptype == 8:  # PLOT_PROJECTED
                    out["proj_dir"] = r.i4()
                out["palette_points"] = r.utf()
                out["palette_lines"] = r.utf()
                out["palette_areas"] = r.utf()
            elif tag == "I":
                out["bbox"] = [r.f4(), r.f4(), r.f4(), r.f4()]
                if r.i4() == 1:
                    out["north"] = [r.f4(), r.f4(), r.f4(), r.f4()]
            elif tag == "N":
                out["scrap_index"] = r.i4()
            elif tag == "P":
                it = {"tag": "point", "x": r.f4(), "y": r.f4(), "name": r.utf()}
                if version >= 401147:
                    it["group"] = r.utf()
                it["orientation"] = r.f4()
                it["scale"] = r.i4()
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                if version >= 303066:
                    it["text"] = r.utf()
                it["options"] = r.utf()
                out["items"].append(it)
                bump("point")
            elif tag == "T":
                it = {"tag": "label", "x": r.f4(), "y": r.f4()}
                if version > 207043:
                    it["orientation"] = r.f4()
                it["scale"] = r.i4()
                if version > 401090:
                    it["level"] = r.i4()
                if version > 401160:
                    it["scrap_n"] = r.i4()
                it["text"] = r.utf()
                it["options"] = r.utf()
                out["items"].append(it)
                bump("label")
            elif tag == "L":
                it = {"tag": "line", "name": r.utf()}
                if version >= 401147:
                    it["group"] = r.utf()
                it["closed"] = r.u1() == 1
                it["reversed"] = r.u1() == 1
                it["outline"] = r.i4()
                if version >= 602055:
                    it["lside"] = r.i4()
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                if version >= 604088:
                    it["scale"] = r.i4()
                it["options"] = r.utf()
                npt = r.i4()
                it["points"] = read_vertices(r, npt)
                it["npt"] = npt
                out["items"].append(it)
                bump("line")
            elif tag == "A":
                it = {"tag": "area", "name": r.utf()}
                if version >= 401147:
                    it["group"] = r.utf()
                it["prefix"] = r.utf()
                it["cnt"] = r.i4()
                it["visible"] = r.u1() == 1
                it["orientation"] = r.f4()
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                if version >= 604096:
                    it["scale"] = r.i4()
                if version >= 604098:
                    it["options"] = r.utf()
                npt = r.i4()
                it["points"] = read_vertices(r, npt)
                it["npt"] = npt
                out["items"].append(it)
                bump("area")
            elif tag == "J":
                it = {"tag": "special", "type": r.i4(), "x": r.f4(), "y": r.f4()}
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                out["items"].append(it)
                bump("special")
            elif tag == "U":
                it = {"tag": "station_user", "x": r.f4(), "y": r.f4(),
                      "scale": r.i4()}
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                it["name"] = r.utf()
                out["stations"].append(it)
                bump("station_user")
            elif tag == "X":
                it = {"tag": "station_name", "x": r.f4(), "y": r.f4(),
                      "name": r.utf()}
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                if version >= 207038:
                    xt = r.i4()
                    if xt != -1:  # PLOT_NULL
                        it["xsection"] = {"type": PLOT_TYPES.get(xt, xt),
                                          "x": r.f4(), "y": r.f4()}
                out["stations"].append(it)
                bump("station_name")
            elif tag == "Y":
                it = {"tag": "photo", "x": r.f4(), "y": r.f4()}
                if version > 207043:
                    it["orientation"] = r.f4()
                it["scale"] = r.i4()
                if version >= 401090:
                    it["level"] = r.i4()
                if version >= 401160:
                    it["scrap_n"] = r.i4()
                it["text"] = r.utf()
                it["options"] = r.utf()
                it["id"] = r.i4()
                if version >= 602067:
                    it["code"] = r.utf()
                    if r.i4() == 1:
                        it["picture"] = [r.f4(), r.f4(), r.f4()]
                out["items"].append(it)
                bump("photo")
            elif tag == "Z":
                it = {"tag": "audio", "x": r.f4(), "y": r.f4()}
                if version > 207043:
                    it["orientation"] = r.f4()
                it["scale"] = r.i4()
                if version >= 401090:
                    it["level"] = r.i4()
                if version > 401160:
                    it["scrap_n"] = r.i4()
                it["text"] = r.utf()
                it["options"] = r.utf()
                it["id"] = r.i4()
                out["items"].append(it)
                bump("audio")
            elif tag == "D":
                out["plot_info"] = {
                    "xoffset": r.f4(), "yoffset": r.f4(), "azimuth": r.f4(),
                    "clino": r.f4(), "intercept": r.f4(), "start": r.utf(),
                    "view": r.utf(), "hide": r.utf(), "nick": r.utf()}
                bump("plot_info")
            elif tag == "F":
                bump("F_end_paths")
                continue  # stations may follow
            elif tag == "E":
                out["clean_end"] = True
                out["trailing"] = len(data) - r.i
                break
            else:
                out["error"] = "unknown tag %r at offset %d" % (tag, r.i - 1)
                break
    except (struct.error, IndexError) as e:
        out["error"] = "truncated/misparse at offset %d: %s" % (r.i, e)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_json = "--json" in sys.argv
    want_items = "--items" in sys.argv
    results = []
    for path in args:
        res = parse_tdr(path)
        results.append(res)
        status = "OK (clean E, %d trailing bytes)" % res["trailing"] if res["clean_end"] \
            else "FAILED: %s" % res["error"]
        print("%s\n  version=%s scrap=%s type=%s\n  counts=%s\n  %s" % (
            res["file"], res["version"], res["scrap"], res["plot_type"],
            res["counts"], status))
        if want_items:
            for it in res["items"]:
                label = it.get("name") or it.get("text") or ""
                print("    %-8s %-24s npt=%-4s options=%r" % (
                    it["tag"], label, it.get("npt", ""), it.get("options", "")))
        print()
    if want_json:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
        print("json written to", out)


if __name__ == "__main__":
    main()
