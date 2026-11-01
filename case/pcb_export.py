"""v3: what a real PCB needs from the case, per half, for KiCad -> pcb/v3/ (run after geometry.py).

<half>_outline.dxf: in each half's PCB frame (mm, top view, +y toward the back; the same frame as case_geometry.json),
layers EDGE (the board outline, shared by the plate: import it to Edge.Cuts), CLIP_KEEPOUT (the 10 TPU gasket zones:
no parts within them on either face), CONNECTOR (the JST-SH header the case is cut for), CONNECTOR_2 (left only: the
second, vertical header, for the link to the right half; the case's breakthrough is cut round both), SWITCH (14 mm
switch cutouts, for reference) and STAB.
<half>_keys.csv: each key's centre and rotation, in KiCad's frame (y down, rotation counter-clockwise as seen from the
top), to place the switch / hotswap / diode footprints.

Usage: case/.venv/Scripts/python case/pcb_export.py
"""
import csv
import json
import os

import numpy as np
from shapely.geometry import Polygon

CASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(CASE), "pcb", "v3")
g = json.load(open(os.path.join(CASE, "out", "case_geometry.json")))
P = g["params"]


def dxf(path, layers):
    """Plain R12 DXF of closed outlines as LINE entities: {layer: [polygon coords, ...]}."""
    out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for layer, polys in layers.items():
        for pts in polys:
            pts = list(pts)
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                out += ["0", "LINE", "8", layer, "10", f"{x0:.4f}", "20", f"{y0:.4f}", "30", "0",
                        "11", f"{x1:.4f}", "21", f"{y1:.4f}", "31", "0"]
    out += ["0", "ENDSEC", "0", "EOF"]
    open(path, "w").write("\n".join(out) + "\n")


def clip_zone(q):
    """A gasket's zone on the PCB: its 10 mm along the edge plus 0.6 each end, 3.0 in from the edge (the 2.5 ledge under
    the board, the 1.5 lip over it, with margin), out to the wall."""
    c, t, n = (np.array(q[k]) for k in ("edge_pt", "t", "n"))
    a = P["clip"]["len"] / 2 + 0.6
    return [tuple(c + t * s + n * m) for s, m in ((-a, -3.0), (a, -3.0), (a, 1.0), (-a, 1.0))]


def main():
    os.makedirs(OUT, exist_ok=True)
    for h, d in g["halves"].items():
        layers = {"EDGE": [d["pcb"]], "CLIP_KEEPOUT": [clip_zone(q) for q in d["clips"]], "CONNECTOR": [d["jst"], d["jst_pocket"]],
                  "SWITCH": d["cutouts"], "STAB": d["stabs"]}
        if h == "left":
            pocket2, header2 = d["jst_pocket2"], d["jst2"]
            layers["CONNECTOR_2"] = [header2, pocket2]
            bx0, by0, bx1, by1 = Polygon(pocket2).bounds
            print(f"left: second header pocket at x {bx0:.1f} .. {bx1:.1f}, y {by0:.1f} .. {by1:.1f}")
        dxf(os.path.join(OUT, f"{h}_outline.dxf"), layers)
        with open(os.path.join(OUT, f"{h}_keys.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["label", "width_u", "x_mm", "y_mm", "rotation_deg"])
            for k in d["keys"]:
                w.writerow([k["label"], k["w"], round(k["x"], 4), round(-k["y"], 4), round(k["ang"], 4)])
        xs, ys = zip(*d["pcb"])
        print(f"{h}: {len(d['keys'])} keys, board {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f} mm -> {OUT}")


if __name__ == "__main__":
    main()
