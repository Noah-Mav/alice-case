"""Alice case: M6 fit coupons, M7 exports and M9 prototype meshes (docs/fusion-case-plan.md §7, §8).

Runs inside Fusion, one step per MCP script call (a long script that dies is rolled back whole):
    def run(_c):
        ns = {}; exec(open(".../case/fusion_export.py", encoding="utf-8").read(), ns); ns["copy"]()   # then "step", "halves", ...
Reads the open "Alice Case" document (never modifies or saves it): every part is copied as a temporary B-Rep, in
world coordinates, into a fresh unsaved direct-modelling document; all cutting happens there. Close that document
without saving when done. Flat parts (print plates, dummy PCBs, PCB strip) are drawn from case_geometry.json.
Local follow-up (DXF, key CSVs, mesh checks): case/.venv/bin/python case/export_local.py
"""
import json
import math
import os

import adsk.core
import adsk.fusion

CASE = os.path.expanduser("~/Documents/Development/personal/alice-case/case")
OUT = os.path.join(CASE, "out")
COUP = os.path.join(OUT, "coupons")
PROTO = os.path.join(OUT, "prototype")
_fb = {}
exec(open(os.path.join(CASE, "fusion_build.py"), encoding="utf-8").read(), _fb)  # reuse slab(), P3, MM (module level only)
slab, P3, MM = _fb["slab"], _fb["P3"], _fb["MM"]
app = adsk.core.Application.get()
tbm = adsk.fusion.TemporaryBRepManager.get()
g = json.load(open(os.path.join(OUT, "case_geometry.json")))
P = g["params"]
RIDGE = g["ridge_x"]
DOWEL = (3.0, 0.1, 6.0)  # dowel Ø, clearance per side (hole Ø3.2), hole depth each side (10 mm dowels)
BED = P["bed"]
PANEL_SPLIT = 30.0  # panel cut, mm right of the ridge: the panel bridges the body seam
SRC = "Alice Case v2"


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    with open(os.path.join(OUT, "fusion_export.log"), "a", encoding="utf-8") as f:
        f.write(s + "\n")


def design():
    """The export document (active, never Alice Case)."""
    d = app.activeDocument
    assert d.name != SRC, "the active document is Alice Case: refusing to modify it"
    return adsk.fusion.Design.cast(d.products.itemByProductType("DesignProductType"))


def comp(name):
    c = design().allComponents.itemByName(name)
    assert c, name
    return c


def body(name, i=0):
    return comp(name).bRepBodies.item(i)


def put(name, bodies, hidden=False):
    """A fresh root component holding temp bodies (replaces one of that name)."""
    root = design().rootComponent
    for o in list(root.occurrences):
        if o.component.name == name:
            o.deleteMe()
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    for b in bodies:
        occ.component.bRepBodies.add(b)
    occ.isLightBulbOn = not hidden
    return occ.component


def box(x0, x1, y0, y1, z0, z1):
    V = adsk.core.Vector3D.create
    return tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
        P3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), V(1, 0, 0), V(0, 1, 0),
        (x1 - x0) * MM, (y1 - y0) * MM, (z1 - z0) * MM))


def obox(c, a, L, W, z0, z1):
    """Box centred on plan point c, length L along plan unit vector a, width W across, z0 .. z1."""
    V = adsk.core.Vector3D.create
    return tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
        P3(c[0], c[1], (z0 + z1) / 2), V(a[0], a[1], 0), V(-a[1], a[0], 0), L * MM, W * MM, (z1 - z0) * MM))


def op(t, tool, kind):
    ok = tbm.booleanOperation(t, tool, getattr(adsk.fusion.BooleanTypes, kind + "BooleanType"))
    assert ok, kind
    return t


def cp(b):
    return tbm.copy(b)


def bbox(b):
    bb = b.boundingBox
    return [bb.minPoint.x / MM, bb.minPoint.y / MM, bb.minPoint.z / MM, bb.maxPoint.x / MM, bb.maxPoint.y / MM,
            bb.maxPoint.z / MM]


def move(b, dx, dy, dz, rot_x180=False):
    """Temp body: optional 180° turn about X (upside down, not mirrored), then translate (mm)."""
    m = adsk.core.Matrix3D.create()
    if rot_x180:
        m.setWithArray([1, 0, 0, 0, 0, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1])
        tbm.transform(b, m)
        m = adsk.core.Matrix3D.create()
    m.translation = adsk.core.Vector3D.create(dx * MM, dy * MM, dz * MM)
    tbm.transform(b, m)
    return b


def to_origin(b, x=0.0, y=0.0):
    """Lay a temp body's bounding-box minimum at (x, y, 0)."""
    bb = bbox(b)
    return move(b, x - bb[0], y - bb[1], -bb[2])


def mesh(geom, path, threemf=False):
    em = design().exportManager
    if threemf:
        o = em.createC3MFExportOptions(geom, path)
    else:
        o = em.createSTLExportOptions(geom, path)
        o.isBinaryFormat = True
        o.unitType = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    o.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementCustom  # finer than "High" on the R1 rounds
    o.surfaceDeviation = 0.002  # cm (0.02 mm)
    o.normalDeviation = math.radians(10)
    assert em.execute(o), path
    log(f"  wrote {os.path.relpath(path, OUT)} ({os.path.getsize(path) / 1024:.0f} KB)")


def info(name, b):
    bb = bbox(b)
    log(f"  {name}: {b.volume * 1000:.1f} mm3, solid {b.isSolid}, lumps {b.lumps.count}, "
          f"size {bb[3] - bb[0]:.1f} x {bb[4] - bb[1]:.1f} x {bb[5] - bb[2]:.1f} mm")


def W(m, u, v, w):
    return [sum(m[r][k] * (u, v, w)[k] for k in range(3)) + m[r][3] for r in range(3)]


# ---------------------------------------------------------------- step 1: copy the parts out of Alice Case
PARTS = {  # export component <- (source component, body names or None for all)
    "Body": ("Case", ["Body"]), "Panel": ("Case", ["Panel"]),
    "PlateL": ("PlateL", None), "PlateR": ("PlateR", None), "PcbL": ("PcbL", None), "PcbR": ("PcbR", None),
    "UDB": ("UDB", ["UDBBoard", "USBReceptacle"]), "TpuClipFront": ("TpuClipFront", None),
    "TpuClipBack": ("TpuClipBack", None),  # v2: no feet or PCB snaps; two TPU clip variants (front 4, back 6)
}


def copy():
    src = next(d for d in app.documents if d.name == SRC)
    sd = adsk.fusion.Design.cast(src.products.itemByProductType("DesignProductType"))
    occs = {o.component.name: o for o in sd.rootComponent.allOccurrences}
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    d = design()
    d.designType = adsk.fusion.DesignTypes.DirectDesignType
    for name, (cn, names) in PARTS.items():
        o = occs[cn]
        bs = [b for b in o.bRepBodies if names is None or b.name in names]  # root-context proxies: world coords
        c = put(name, [cp(b) for b in bs])
        for i, b in enumerate(bs):
            c.bRepBodies.item(i).name = b.name
        log(name, len(bs), "bodies", f"{sum(b.volume for b in bs) * 1000:.1f} mm3")
    bb = bbox(body("PlateL"))
    want = g["halves"]["left"]["plate_bbox_world"]
    log("PlateL world bbox off JSON by", f"{max(abs(a - b) for a, b in zip(bb, want)):.4f} mm")
    app.activeViewport.fit()


# ---------------------------------------------------------------- step 2: STEP of the assembly and each part
def step():
    d = design()
    em = d.exportManager
    path = os.path.join(OUT, "alice_case_assembly.step")
    assert em.execute(em.createSTEPExportOptions(path, d.rootComponent))
    log("wrote", os.path.basename(path))
    for name in PARTS:
        fn = name.lower()
        fn = fn[:-1] + "_left" if name in ("PlateL", "PcbL") else fn[:-1] + "_right" if name in (
            "PlateR", "PcbR") else "tpu_clip_" + name[7:].lower() if name.startswith("TpuClip") else fn
        path = os.path.join(OUT, "step", fn + ".step")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        assert em.execute(em.createSTEPExportOptions(path, comp(name)))
        log("wrote step/" + os.path.basename(path))


# ---------------------------------------------------------------- step 3: body halves with dowel holes
def dowel_points(b, n=3):
    """n points (y, z) on the ridge plane with solid material for a Ø3.2 x 2 x 6 mm hole plus 2 mm all round,
    spread as far apart as possible."""
    bb = bbox(b)
    r = DOWEL[0] / 2 + DOWEL[1] + 2.0
    inside = lambda x, y, z: b.pointContainment(P3(x, y, z)) == adsk.fusion.PointContainment.PointInsidePointContainment
    ok = []
    for yi in range(int(bb[1]) + 1, int(bb[4])):
        for zi in range(int(bb[2]) + 1, int(bb[5])):
            if not inside(RIDGE, yi, zi):
                continue
            ring = [(yi + r * math.cos(t * math.pi / 4), zi + r * math.sin(t * math.pi / 4)) for t in range(8)]
            if all(inside(RIDGE + dx, y, z) for dx in (-DOWEL[2] - 0.5, -3, -0.2, 0.2, 3, DOWEL[2] + 0.5)
                   for y, z in ring + [(yi, zi)]):
                ok.append((yi, zi))
    assert len(ok) >= n, ok
    far = max(((a, c) for a in ok for c in ok), key=lambda p: (p[0][0] - p[1][0]) ** 2 + (p[0][1] - p[1][1]) ** 2)
    pick = list(far)
    while len(pick) < n:
        pick.append(max(ok, key=lambda p: min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in pick)))
    return pick, len(ok)


DOWEL_YZ = [(-5, 4), (93, 33), (47, 8)]  # (M7 v7: the 4 mm panel's rabbet moved the middle one up)  # found by dowel_points() (slow: ~5 min); halves(search=True) re-runs it


def halves(search=False):
    src = body("Body")
    pts = DOWEL_YZ
    if search:
        pts, nok = dowel_points(src)
        log(f"({nok} candidate points)")
    log("dowel points (y, z) on the ridge:", pts)
    bb = bbox(src)
    out = []
    for side, x0, x1 in (("left", bb[0] - 5, RIDGE), ("right", RIDGE, bb[3] + 5)):
        h = op(cp(src), box(x0, x1, bb[1] - 5, bb[4] + 5, bb[2] - 5, bb[5] + 5), "Intersection")
        for y, z in pts:
            r = DOWEL[0] / 2 + DOWEL[1]
            op(h, tbm.createCylinderOrCone(P3(RIDGE - DOWEL[2], y, z), r * MM, P3(RIDGE + DOWEL[2], y, z), r * MM),
               "Difference")
        out.append((side, h))
    for side, h in out:
        c = put("Body_" + side, [h], hidden=True)
        b = c.bRepBodies.item(0)
        info("body_" + side, b)
        bb = bbox(b)
        log(f"  bed fit {BED[0]:.0f} x {BED[1]:.0f}: {bb[3] - bb[0]:.1f} x {bb[4] - bb[1]:.1f} -> "
              f"{'FITS' if max(bb[3] - bb[0], bb[4] - bb[1]) <= min(BED) - 5 else 'DOES NOT FIT'}")
        mesh(b, os.path.join(OUT, f"body_{side}.stl"))
        mesh(b, os.path.join(OUT, f"body_{side}.3mf"), threemf=True)


# ---------------------------------------------------------------- step 4: panel (split at the ridge) and print plates
def rect_fit(w, h, s):
    """Does a w x h rectangle fit an s x s bed at any rotation (1° steps)?"""
    return any(w * math.cos(t) + h * math.sin(t) <= s and w * math.sin(t) + h * math.cos(t) <= s
               for t in (math.radians(a) for a in range(0, 91)))


def panel():
    src = body("Panel")
    bb = bbox(src)
    fits = rect_fit(bb[3] - bb[0], bb[4] - bb[1], min(BED) - 5)
    log(f"panel {bb[3] - bb[0]:.1f} x {bb[4] - bb[1]:.1f}: {'fits' if fits else 'does not fit'} the bed at any angle"
          f" ({'whole' if fits else 'split'})")
    # split PANEL_SPLIT mm right of the ridge (so the panel bridges the body seam), square to the right half's back
    # edge; clear of screws, feet, pegs and UDB mounts (nearest: screw at x 129.4, foot at x 234)
    pb = g["panel"]
    k = max(range(len(pb)), key=lambda i: pb[i][0] + pb[i][1])  # back-right corner of the outline
    a = [pb[k][0] - RIDGE, pb[k][1] - max(p[1] for p in pb if abs(p[0] - RIDGE) < 1e-3)]
    la = math.hypot(*a)
    a = [a[0] / la, a[1] / la]  # along the right back edge
    cx = RIDGE + PANEL_SPLIT
    S = 600.0
    side = lambda sg: obox([cx + sg * a[0] * S / 2, 50 + sg * a[1] * S / 2], a, S, S, bb[2] - 5, bb[5] + 5)
    parts = [("panel", cp(src))] if fits else [("panel_left", op(cp(src), side(-1), "Intersection")),
                                                ("panel_right", op(cp(src), side(1), "Intersection"))]
    log(f"panel split at x {cx:.2f} (ridge + {PANEL_SPLIT}), cut square to the back edge (dir {a[0]:.5f}, {a[1]:.5f})")
    for name, b in parts:
        b = put(name.capitalize(), [b], hidden=True).bRepBodies.item(0)
        info(name, b)
        mesh(b, os.path.join(OUT, name + ".stl"))
        mesh(b, os.path.join(OUT, name + ".3mf"), threemf=True)


def scaled(poly, k):
    cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
    return [[cx + (x - cx) * k, cy + (y - cy) * k] for x, y in poly]


def print_plate(h):
    """Flat plate for printing: real outline, cutouts grown to cutout_print (14.05), stabs as designed; z 0 .. 1.5."""
    d = g["halves"][h]
    k = P["cutout_print"] / P["cutout"]
    name = "PrintPlate" + ("L" if h == "left" else "R")
    c = put(name, [], hidden=True)
    slab(c, name, [d["plate"]] + [scaled(q, k) for q in d["cutouts"]] + d["stabs"], [0.0, P["plate_t"]], True)
    return c.bRepBodies.item(0)


def plates():
    for h in ("left", "right"):
        b = print_plate(h)
        info("plate_" + h, b)
        bb = bbox(b)
        log(f"  bed fit: {bb[3] - bb[0]:.1f} x {bb[4] - bb[1]:.1f}")
        for ext in ("stl", "3mf"):
            mesh(b, os.path.join(OUT, f"plate_{h}.{ext}"), threemf=ext == "3mf")


# ---------------------------------------------------------------- step 5: M6 fit coupons
def floor_z(m, x, y):
    """World z of a half's pocket floor plane (w = floor_w) above plan point (x, y), mm."""
    n = [m[0][2], m[1][2], m[2][2]]
    p0 = W(m, 0, 0, g["floor_w"])
    return p0[2] - (n[0] * (x - p0[0]) + n[1] * (y - p0[1])) / n[2]


def coupons():
    os.makedirs(COUP, exist_ok=True)
    made = []

    def save(name, b, note):
        b = to_origin(b)
        c = put("C_" + name, [b], hidden=True)
        b = c.bRepBodies.item(0)
        info(name, b)
        log("   ", note)
        mesh(b, os.path.join(COUP, name + ".stl"))
        made.append(name)

    # 1. 3-key strip of the print plate (14.05 cutouts): Q W E
    L = g["halves"]["left"]
    ks = [k for k in L["keys"] if k["label"] in ("Q", "W", "E")]
    xs, ys = [k["x"] for k in ks], [k["y"] for k in ks]
    plate = print_plate("left")
    save("c1_plate_3key", op(cp(plate), box(min(xs) - 10.5, max(xs) + 10.5, min(ys) - 10.5, max(ys) + 10.5, -1, 3),
                             "Intersection"), "plate Q-W-E, 14.05 cutouts, flat")

    # 2. wall + snap gap + snap post + floor patch (left front snap), and the matching PCB edge strip
    q = next(s for s in L["snaps"] if s["side"] == "front")
    m = L["matrix"]
    p0, p1, p3 = q["poly"][0], q["poly"][1], q["poly"][3]
    a = [p1[0] - p0[0], p1[1] - p0[1]]
    la = math.hypot(*a)
    a = [a[0] / la, a[1] / la]
    nin = [p3[0] - p0[0], p3[1] - p0[1]]  # inward (from the wall side of the snap)
    ln = math.hypot(*nin)
    nin = [nin[0] / ln, nin[1] / ln]
    mid = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2]  # flat coords, ~0.1 off the wall
    out_, in_ = 12.0, 14.0  # plan: outward past the outer face, inward over the floor
    cflat = [mid[0] + nin[0] * (in_ - out_) / 2, mid[1] + nin[1] * (in_ - out_) / 2]
    cw = W(m, cflat[0], cflat[1], g["pcb_mid_w"])
    mw0, mw1 = W(m, mid[0], mid[1], g["pcb_mid_w"]), W(m, mid[0] + a[0], mid[1] + a[1], g["pcb_mid_w"])
    aw = [mw1[0] - mw0[0], mw1[1] - mw0[1]]
    law = math.hypot(*aw)
    aw = [aw[0] / law, aw[1] / law]
    corners = [W(m, mid[0] + a[0] * s * 16 + nin[0] * t, mid[1] + a[1] * s * 16 + nin[1] * t, g["pcb_mid_w"])
               for s in (-1, 1) for t in (0, in_)]
    zcut = min(floor_z(m, p[0], p[1]) for p in corners) - 2.0
    log("  snap coupon: floor-patch cut at z", round(zcut, 2))
    assert zcut > 0.5, zcut  # (M7: the body is solid to the desk under the front snaps)
    save("c2_wall_snap_body", op(cp(body("Body")), obox(cw, aw, 32, out_ + in_, zcut, 80), "Intersection"),
         f"left front snap: wall, {P['snap_gap']} gap, post, floor patch; flat cut face down")
    pcbc = put("FlatPcbL", [], hidden=True)
    slab(pcbc, "FlatPcbL", [L["pcb"]], [0.0, P["pcb_t"]], True)
    strip = op(cp(pcbc.bRepBodies.item(0)), obox(cflat, a, 32, out_ + in_, -1, 3), "Intersection")
    save("c2_pcb_edge_strip", strip, "PCB edge (1.6) at the same snap: clip a snap on it and drop it in")

    c3(save)

    # 4. rear USB notch with the panel band; diagonal band end (back-left corner)
    nb = (RIDGE - 17.0, RIDGE + 17.0, 74.0, 100.0)
    save("c4_usb_notch_body", op(cp(body("Body")), box(*nb, -1, 17.0), "Intersection"),
         "USB notch, UDB bay, lip pocket; bottom (rabbet roof plane) down; notch roof bridges 12 mm")
    save("c4_usb_panel_band", op(cp(body("Panel")), box(*nb, -10, 20), "Intersection"),
         "panel band under the notch with its lip and UDB mounts; outer face down")
    xe = g["lip_ends"][0]  # M7: the band end is one 21 mm diagonal from the panel's back-left corner to its top
    eb = (xe - 12.0, xe + 28.0, 78.0, 100.0)
    save("c4_band_end_body", op(cp(body("Body")), box(*eb, -1, 17.0), "Intersection"),
         "back-left corner where the band ends on its diagonal; bottom down, supports touching the bed only")
    save("c4_band_end_panel", op(cp(body("Panel")), box(*eb, -10, 20), "Intersection"),
         "panel band end (diagonal) at the back-left corner; outer face down")
    log("coupons:", made)


def c3(save=None):
    """Insert coupon: the panel's front-left screw (M7; was the front V tip). No insert in this design has a free-standing boss (each sits
    under solid floor or web), so the body is cut 2 mm over the blind Ø4 hole and printed upside down (cut face on
    the bed: no supports, hole opening upward for the heat-set tool), with its panel piece (countersink)."""
    if save is None:
        def save(name, b, note):
            b = put("C_" + name, [to_origin(b)], hidden=True).bRepBodies.item(0)
            info(name, b)
            log("   ", note)
            mesh(b, os.path.join(COUP, name + ".stl"))
    sx, sy = g["screws"][2]  # M8: the panel's V screw (short insert, in the recessed field)
    src = body("Body")
    z = P["panel_t"] + 0.5
    while src.pointContainment(P3(sx, sy, z)) != adsk.fusion.PointContainment.PointInsidePointContainment:
        z += 0.1
    log(f"  c3: insert hole top at z {z:.1f}; body cut at z {z + 2:.1f}")
    bx = (sx - 11.0, sx + 11.0, sy - 14.0, sy + 11.0)
    save("c3_insert_boss_body", move(op(cp(src), box(*bx, -1, z + 2.0), "Intersection"), 0, 0, 0, rot_x180=True),
         "panel V screw: rabbet, Ø4 x 3.6 heat-set hole; upside down (flat cut face on the bed), "
         "no supports")
    save("c3_panel_corner", op(cp(body("Panel")), box(*bx, -10, 20), "Intersection"),
         "panel at its V screw: countersunk M3 hole in the 0.4 mm recessed field; outer face down")


def layout_shot():
    """All coupons in a row (print orientation) for m6-coupons.png."""
    root = design().rootComponent
    for o in root.occurrences:
        o.isLightBulbOn = False
    names = ["c1_plate_3key", "c2_wall_snap_body", "c2_pcb_edge_strip", "c3_insert_boss_body", "c3_panel_corner",
             "c4_usb_notch_body", "c4_usb_panel_band", "c4_band_end_body", "c4_band_end_panel"]
    bs = []
    for i, n in enumerate(names):  # 3 x 3 grid, 45 mm pitch
        bs.append(to_origin(cp(body("C_" + n)), (i % 3) * 45.0, -(i // 3) * 40.0))
    c = put("CouponLayout", bs)
    vp = app.activeViewport
    for view, fn in ((adsk.core.ViewOrientations.IsoTopRightViewOrientation, "m6-coupons.png"),
                     (adsk.core.ViewOrientations.IsoBottomRightViewOrientation, "m6-coupons-underside.png")):
        cam = vp.camera
        cam.viewOrientation = view
        cam.isFitView = True
        vp.camera = cam
        vp.refresh()
        path = os.path.join(COUP, fn)
        vp.saveAsImageFile(path, 1600, 1000)
    log("wrote", path, c.bRepBodies.count, "bodies")


# ---------------------------------------------------------------- step 6: M9 prototype meshes
# Dummy PCB holes: MX hotswap footprint + Cherry PCB-mount stab (KiCad SW_Cherry_MX_2.00u_PCB, Kailh hotswap),
# key-local mm, +y = back. (nominal Ø, x, y); printed Ø = nominal + print_hole_clearance.
print_hole_clearance = 0.3
MX_HOLES = [(4.0, 0, 0), (1.75, -5.08, 0), (1.75, 5.08, 0), (3.0, -3.81, 2.54), (3.0, 2.54, 5.08)]
STAB_HOLES = [(3.9878, 11.938, -8.2423), (3.0480, 11.938, 6.985)]  # large (front) and wire (back); also at -x


def pcb_holes(k):
    """Hole outlines (plan polygons, PCB frame) for one key: switch holes, plus stab holes for keys >= 2u."""
    hs = list(MX_HOLES)
    if k["w"] >= P["stab"]["min_w"]:
        hs += [(d, sx * x, y) for d, x, y in STAB_HOLES for sx in (-1, 1)]
    a = math.radians(k["ang"])
    c, s = math.cos(a), math.sin(a)
    out = []
    for d, x, y in hs:
        cx, cy = k["x"] + x * c - y * s, k["y"] + x * s + y * c
        r = (d + print_hole_clearance) / 2
        out.append([[cx + r * math.cos(t * math.pi / 24), cy + r * math.sin(t * math.pi / 24)] for t in range(48)])
    return out


# Kailh CPG151101S11 hotswap socket body, key-local (+y = back): two offset lobes round the switch pin holes,
# one S-shaped outline. ponytail: 10.9 x 4.6 mm from the datasheet outline as briefed (not fetched), pads left out.
SOCKET_OUTLINE = [(-6.085, 1.51), (-0.2, 1.51), (-0.2, 3.4), (4.815, 3.4), (4.815, 6.11), (-1.0, 6.11), (-1.0, 4.2), (-6.085, 4.2)]
SOCKET_PIN_D = 1.9  # Ø1.6 pin slot printed +0.3 (flat blades 1.5 x 0.4)


def socket_polys(k):
    """(lobes, cutters) plan polygons for one key: socket bodies; pin slots + centre post and peg holes through them."""
    a = math.radians(k["ang"])
    c, s = math.cos(a), math.sin(a)
    tf = lambda x, y: [k["x"] + x * c - y * s, k["y"] + x * s + y * c]
    lobes = [[tf(x, y) for x, y in SOCKET_OUTLINE]]
    cut = []
    for d, x, y in [(SOCKET_PIN_D - print_hole_clearance, -3.81, 2.54), (SOCKET_PIN_D - print_hole_clearance, 2.54, 5.08)] + MX_HOLES[:3]:
        r = (d + print_hole_clearance) / 2
        cx, cy = tf(x, y)
        cut.append([[cx + r * math.cos(t * math.pi / 24), cy + r * math.sin(t * math.pi / 24)] for t in range(48)])
    return lobes, cut


def dummy_pcbs():
    os.makedirs(PROTO, exist_ok=True)
    Lz = g["layers"]
    for h in ("left", "right"):
        d = g["halves"][h]
        s = "L" if h == "left" else "R"
        # dummy PCB, printed top face down: turned 180° about X, so v -> -v and w -> -w (not a mirror).
        # PCB w -6.6..-5.0 -> z 0..1.6 (z = -5.0 - w); the JST hangs below it -> bump up
        flip = lambda polys: [[[x, -y] for x, y in p] for p in polys]
        zr = lambda w: [-5.0 - w[1], -5.0 - w[0]]
        c = put("DummyPcb" + s, [], hidden=True)
        marks = []
        for q in d["snaps"]:  # Ø1.2 through holes 1 mm past each end of every snap, on its inner edge (2.3 mm in)
            p2, p3 = q["poly"][2], q["poly"][3]
            u = [p2[0] - p3[0], p2[1] - p3[1]]
            lu = math.hypot(*u)
            u = [u[0] / lu, u[1] / lu]
            for p, sg in ((p2, 1), (p3, -1)):
                cx, cy = p[0] + u[0] * sg * 1.6, p[1] + u[1] * sg * 1.6
                marks.append([[cx + 0.6 * math.cos(t * math.pi / 8), cy + 0.6 * math.sin(t * math.pi / 8)]
                              for t in range(16)])
        holes = [p for k in d["keys"] for p in pcb_holes(k)]
        slab(c, "Board", flip([d["pcb"]] + marks + holes), zr(Lz["pcb"]), True)
        slab(c, "JST", flip([d["jst"]]), zr(Lz["jst"]))
        sk = [socket_polys(k) for k in d["keys"]]
        slab(c, "Sockets", flip([q for l, _ in sk for q in l]), zr(Lz["socket"]))
        slab(c, "SocketCut", flip([q for _, cu in sk for q in cu]), [zr(Lz["socket"])[0] - 0.1, zr(Lz["socket"])[1] + 0.1])
        bs = [cp(b) for b in c.bRepBodies]
        board = bs[0]
        ns = len(sk)
        socks, cuts = bs[2:2 + ns], bs[2 + ns:]
        for sb in socks:  # cut each socket by the slots/holes inside its own footprint, then join (cheap small booleans)
            b0 = bbox(sb)
            for t in cuts:
                b1 = bbox(t)
                if b1[0] < b0[3] and b1[3] > b0[0] and b1[1] < b0[4] and b1[4] > b0[1]:
                    op(sb, cp(t), "Difference")
            op(board, sb, "Union")
        op(board, bs[1], "Union")
        b = put("DummyPcbPrint" + s, [to_origin(board)], hidden=True).bRepBodies.item(0)
        info(f"dummy_pcb_{h}", b)
        mesh(b, os.path.join(PROTO, f"dummy_pcb_{h}.stl"))


def proto():
    dummy_pcbs()
    os.makedirs(PROTO, exist_ok=True)
    for h in ("left", "right"):
        s = "L" if h == "left" else "R"
        pb = body("PrintPlate" + s)
        mesh(pb, os.path.join(PROTO, f"plate_{h}.stl"))


# ---------------------------------------------------------------- step 7: whole body, whole panel, switch fit strip -> prints/
PRINTS = os.path.join(os.path.dirname(CASE), "prints")
SEG = {"0": "abcdef", "1": "bc", "4": "bcfg", "5": "acdfg", "7": "abc", "9": "abcdfg"}  # 7-segment digits used below


def fit_strip():
    """1.5 mm strip, 4 MX cutouts 14.00 / 14.05 / 14.10 / 14.15, each size embossed 0.4 mm below it (z 1.5 .. 1.9)."""
    t, pitch, H = P["plate_t"], 19.05, 28.0
    sizes = [14.00, 14.05, 14.10, 14.15]
    cx = [pitch / 2 + i * pitch for i in range(4)]
    c = put("FitStrip", [], hidden=True)
    sq = lambda x, s, y0=19.0: [[x - s / 2, y0 - s / 2], [x + s / 2, y0 - s / 2], [x + s / 2, y0 + s / 2], [x - s / 2, y0 + s / 2]]
    slab(c, "FitStrip", [[[0, 0], [4 * pitch, 0], [4 * pitch, H], [0, H]]] + [sq(x, s) for x, s in zip(cx, sizes)], [0.0, t], True)
    strip = cp(c.bRepBodies.item(0))
    w, h, k, gap = 3.0, 6.0, 0.9, 1.0  # digit size, stroke, spacing
    rects = {"a": (0, w, h - k, h), "d": (0, w, 0, k), "g": (0, w, (h - k) / 2, (h + k) / 2), "f": (0, k, h / 2, h),
             "e": (0, k, 0, h / 2), "b": (w - k, w, h / 2, h), "c": (w - k, w, 0, h / 2)}
    for x, s in zip(cx, sizes):
        txt = f"{s:.2f}"
        x0 = x - (4 * (w + gap) + k + gap) / 2 + 0.2  # 4 digits and the dot
        for ch in txt:
            if ch == ".":
                op(strip, box(x0, x0 + k, 3.0, 3.0 + k, t - 0.01, t + 0.4), "Union")
                x0 += k + gap
                continue
            for sg in SEG[ch]:
                a, b, y0, y1 = rects[sg]
                op(strip, box(x0 + a, x0 + b, 3.0 + y0, 3.0 + y1, t - 0.01, t + 0.4), "Union")
            x0 += w + gap
    b = put("FitStripPrint", [to_origin(strip)], hidden=True).bRepBodies.item(0)
    info("switch_fit_test", b)
    mesh(b, os.path.join(PRINTS, "switch_fit_test.stl"))


def whole():
    """Whole body and whole panel, as modelled (bottom / outer face down), lowest point on z 0."""
    os.makedirs(PRINTS, exist_ok=True)
    for n, f in (("Body", "case_body"), ("Panel", "bottom_panel")):
        b = put(n + "Print", [to_origin(cp(body(n)))], hidden=True).bRepBodies.item(0)
        info(f, b)
        mesh(b, os.path.join(PRINTS, f + ".stl"))
    fit_strip()


def v2_prints(out=None):
    """v2: whole body and panel plus the two TPU clip variants (single, and a 4-up FRONT / 6-up BACK plate) -> prints/v2/
    (run after copy()). The old single-variant tpu_clip.stl / tpu_clip_x10.stl are removed."""
    out = out or os.path.join(PRINTS, "v2")
    os.makedirs(out, exist_ok=True)
    for old in ("tpu_clip.stl", "tpu_clip_x10.stl"):
        if os.path.exists(os.path.join(out, old)):
            os.remove(os.path.join(out, old))
    for n, f in (("Body", "case_body"), ("Panel", "bottom_panel"), ("TpuClipFront", "tpu_clip_front"), ("TpuClipBack", "tpu_clip_back")):
        b = put(n + "Print", [to_origin(cp(body(n)))], hidden=True).bRepBodies.item(0)
        info(f, b)
        mesh(b, os.path.join(out, f + ".stl"))
    for n, f, k in (("TpuClipFront", "tpu_clip_front_x4", 4), ("TpuClipBack", "tpu_clip_back_x6", 6)):
        cl, y = [], 0.0
        for i in range(k):  # one multi-lump body: a component with several bodies did not export
            t = to_origin(cp(body(n)), 0, y)
            y = bbox(t)[4] + 4
            cl.append(t)
        for b in cl[1:]:
            op(cl[0], b, "Union")
        b = put(n + "Plate", cl[:1], hidden=True).bRepBodies.item(0)
        info(f, b)
        mesh(b, os.path.join(out, f + ".stl"))
