"""M7 local exports + mesh checks (no Fusion): DXFs and key CSVs from case_geometry.json, then every exported
STL / 3MF under case/out checked for watertightness, volume and bounding box.
    case/.venv/bin/python case/export_local.py
"""
import csv
import glob
import json
import os
import re
import struct
import sys
import zipfile
from collections import Counter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def dxf(path, polys):
    """R12 DXF, mm, one closed LINE loop per polygon (flat coordinates as given)."""
    rows = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4",
            "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for p in polys:
        for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1]):
            rows += ["0", "LINE", "8", "0", "10", f"{x0:.4f}", "20", f"{y0:.4f}", "30", "0",
                     "11", f"{x1:.4f}", "21", f"{y1:.4f}", "31", "0"]
    rows += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(rows) + "\n")


def flat_exports(g):
    for h, d in g["halves"].items():
        dxf(os.path.join(OUT, f"plate_{h}.dxf"), [d["plate"]] + d["cutouts"] + d["stabs"])  # nominal 14.0 cutouts
        dxf(os.path.join(OUT, f"pcb_{h}.dxf"), [d["pcb"]])
        with open(os.path.join(OUT, f"pcb_{h}_keys.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["label", "x_mm", "y_mm", "angle_deg_ccw", "width_u"])
            for k in d["keys"]:
                w.writerow([k["label"], f"{k['x']:.4f}", f"{k['y']:.4f}", f"{k['ang']:.4f}", k["w"]])


def tris_stl(path):
    b = open(path, "rb").read()
    n = struct.unpack("<I", b[80:84])[0]
    assert len(b) == 84 + 50 * n, "not a binary STL"
    return [struct.unpack("<9f", b[84 + 50 * i + 12:84 + 50 * i + 48]) for i in range(n)]


def tris_3mf(path):
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if n.endswith(".model"))
    x = z.read(name).decode()
    unit = re.search(r'unit="(\w+)"', x)
    k = {"millimeter": 1.0, "centimeter": 10.0, "meter": 1000.0, "inch": 25.4}[unit.group(1) if unit else "millimeter"]
    out = []
    for obj in re.findall(r"<mesh>(.*?)</mesh>", x, re.S):
        vs = [tuple(float(a) * k for a in m) for m in re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', obj)]
        for t in re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', obj):
            a, b, c = (vs[int(i)] for i in t)
            out.append(a + b + c)
    return out


def check(tris):
    """(watertight, volume mm3, bbox size, shells-free edge count): every edge used exactly twice, once each way."""
    key = lambda i, t: tuple(t[3 * i:3 * i + 3])  # shared vertices are bit-identical
    edges = Counter()
    vol = 0.0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for t in tris:
        p = [key(i, t) for i in range(3)]
        for i in range(3):
            edges[(p[i], p[(i + 1) % 3])] += 1
            for a in range(3):
                lo[a], hi[a] = min(lo[a], p[i][a]), max(hi[a], p[i][a])
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = p
        vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6
    bad = sum(1 for (a, b), n in edges.items() if n != 1 or edges.get((b, a), 0) != 1)
    return bad == 0, vol, [hi[a] - lo[a] for a in range(3)], bad


def verify():
    rows = []
    for p in sorted(glob.glob(os.path.join(OUT, "**", "*.stl"), recursive=True) +
                    glob.glob(os.path.join(OUT, "**", "*.3mf"), recursive=True)):
        t = tris_stl(p) if p.endswith(".stl") else tris_3mf(p)
        ok, vol, size, bad = check(t)
        rows.append((os.path.relpath(p, OUT), len(t), ok, vol, size, bad))
    print(f"{'file':42} {'tris':>7} {'watertight':>10} {'volume mm3':>12}  size mm (x y z)")
    for r in rows:
        print(f"{r[0]:42} {r[1]:7d} {('yes' if r[2] else f'NO ({r[5]})'):>10} {r[3]:12.1f}  "
              f"{r[4][0]:.1f} x {r[4][1]:.1f} x {r[4][2]:.1f}")
    return all(r[2] and r[3] > 0 for r in rows)


if __name__ == "__main__":
    flat_exports(json.load(open(os.path.join(OUT, "case_geometry.json"))))
    # self-check of check(): a unit tetrahedron is watertight with volume 1/6
    tet = [(0, 0, 0, 0, 1, 0, 1, 0, 0), (0, 0, 0, 1, 0, 0, 0, 0, 1), (0, 0, 0, 0, 0, 1, 0, 1, 0), (1, 0, 0, 0, 1, 0, 0, 0, 1)]
    ok, vol, _, _ = check(tet)
    assert ok and abs(vol - 1 / 6) < 1e-9, (ok, vol)
    sys.exit(0 if verify() else 1)
