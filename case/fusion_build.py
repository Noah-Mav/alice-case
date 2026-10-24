"""Alice case: the Fusion build (docs/fusion-case-plan.md §3). Runs inside Fusion: through the MCP execute tool
(featureType "script", this file's text) or Shift+S -> Run.

THE GEOMETRY IS BAKED IN. Every outline, position and matrix comes from case/out/case_geometry.json, which
case/geometry.py writes. The User Parameters created here are a read-only record of the numbers used: editing
them in Fusion moves nothing. To change an angle, a bezel, a gap or a size, edit the P dict at the top of
geometry.py and re-run both scripts:
    case/.venv/bin/python case/geometry.py layouts/layout2.json
    then this file in Fusion (every run builds into a fresh document)

Units: the JSON is mm; Fusion's internal unit is cm, so every length is scaled by MM here (matrix translations too).
Flat parts are drawn in their own component's XY plane (u, v; the plate top is z = 0, +z is the plate normal) and
placed with each half's local -> world matrix (set when the occurrence is created; see part()).

Milestones add a build_* function and a line in run(): M2 flat parts, M3 case core (build_case), M7 exports.
Output is printed and also appended to case/out/fusion_build.log (a slow STEP import can outlast the MCP call).

v2 (2026-10): every run builds a NEW document, "Alice Case v2" (DOC_NAME; there is no INTO_ACTIVE: v1 stays untouched).
The PCB is held by 10 printable TPU C-clips (two variants: FRONT x4, BACK x6) in recesses in the pocket floors (build_clip, clip_recesses), not by snaps;
the feet are 4 bumpon recesses (3M SJ5302); the rear peak is cut by one plane (rear_cut); see case/out/v2_changes.md.
"""
import json
import math
import os
import time

import adsk.core
import adsk.fusion

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") if "__file__" in globals() else \
    os.path.expanduser("~/Documents/Development/personal/alice-case/case/out")
JSON = os.path.join(OUT, "case_geometry.json")
UDB_STEP = os.path.join(OUT, "uDB-C3-3D-model.step")  # optional; the box placeholder is always built
# STEP frame -> UDB frame (board centre, board bottom at z=0, receptacle at +y), measured from that file, mm
UDB_STEP_SHIFT = (-75.004, 64.793, 0.01)
MM = 0.1
DOC_NAME = "Alice Case v2"
ANGLES = {"typing_angle", "tent", "lower_cant", "clip_lip_lead"}
UNITLESS = {"stab_min_w"}


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    with open(os.path.join(OUT, "fusion_build.log"), "a") as f:
        f.write(s + "\n")


def matrix(m):
    """4x4 row-major mm matrix -> Matrix3D (cm)."""
    M = adsk.core.Matrix3D.create()
    M.setWithArray([m[r][c] * (MM if c == 3 and r < 3 else 1) for r in range(4) for c in range(4)])
    return M


def add_params(design, P):
    flat = {}
    for k, v in P.items():
        if isinstance(v, dict):
            flat.update({f"{k}_{kk}": vv for kk, vv in v.items()})
        elif isinstance(v, list):
            flat.update({f"{k}_{i + 1}": vv for i, vv in enumerate(v)})
        else:
            flat[k] = v
    ups = design.userParameters
    for k, v in flat.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):  # (crease_mode: a switch; v2: the clip_pts point lists)
            continue
        unit = "deg" if k in ANGLES else "" if k in UNITLESS else "mm"
        ups.add(k, adsk.core.ValueInput.createByString(f"{v} {unit}".strip()), unit, "from geometry.py (baked in)")


def slab(comp, name, polys, w, outer=False, opacity=None):
    """Extrude closed polylines (mm, component XY) from z = w[0] to w[1] mm: one deferred sketch, one extrude.
    outer=True keeps only the profile with the most loops (an outline with its holes), else every profile."""
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.name = name
    sk.isComputeDeferred = True
    lines = sk.sketchCurves.sketchLines
    for poly in polys:
        pts = [adsk.core.Point3D.create(x * MM, y * MM, 0) for x, y in poly]
        first = prev = None
        for i in range(len(pts)):
            a = prev.endSketchPoint if prev else pts[0]
            b = first.startSketchPoint if i == len(pts) - 1 else pts[i + 1]
            prev = lines.addByTwoPoints(a, b)
            first = first or prev
    sk.isComputeDeferred = False
    profs = [sk.profiles.item(i) for i in range(sk.profiles.count)]
    if outer:
        profs = [max(profs, key=lambda p: p.profileLoops.count)]
    coll = adsk.core.ObjectCollection.create()
    for p in profs:
        coll.add(p)
    ext = comp.features.extrudeFeatures
    inp = ext.createInput(coll, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.startExtent = adsk.fusion.OffsetStartDefinition.create(adsk.core.ValueInput.createByReal(w[0] * MM))
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal((w[1] - w[0]) * MM))
    f = ext.add(inp)
    f.name = name
    for i in range(f.bodies.count):
        b = f.bodies.item(i)
        b.name = name if f.bodies.count == 1 else f"{name}{i + 1}"
        if opacity is not None:
            b.opacity = opacity
    return f


def part(parent, name, m, *slabs, ctx=None):
    """A component placed with matrix m and built flat in its own coordinates from slabs
    (name, polys, layer[, outer[, opacity]]). Returns the root-context occurrence (ctx: its root-level parent).
    The matrix goes in at creation: Occurrence.transform2 on a nested occurrence is an assembly-context
    override, which needs a root proxy plus a position snapshot, and Fusion silently ignored it for the first
    child of the first root occurrence (PlateL)."""
    occ = parent.occurrences.addNewComponent(matrix(m))
    occ.component.name = name
    for s in slabs:
        slab(occ.component, *s)
    return occ.createForAssemblyContext(ctx) if ctx else occ


def appearance(name, rgb):
    """A glossy paint appearance in colour rgb, copied once from the library's red enamel (it has no orange)."""
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    have = design.appearances.itemByName(name)
    if have:
        return have
    lib = adsk.core.Application.get().materialLibraries.itemByName("Fusion Appearance Library")
    a = design.appearances.addByCopy(lib.appearances.itemByName("Paint - Enamel Glossy (Red)"), name)
    for i in range(a.appearanceProperties.count):
        p = a.appearanceProperties.item(i)
        if isinstance(p, adsk.core.ColorProperty) and p.value:
            p.value = adsk.core.Color.create(*rgb, 255)
    return a


def build_half(root, g, h):
    """M2: plate, PCB (+ socket keep-outs, JST header and its plug pocket), switches, keycap envelopes, and (v2) the
    5 TPU C-clips on the PCB's edge: the printed FRONT or BACK variant at each spot (build_clip, the same data as TpuClipFront / Back)."""
    d, L, s = g["halves"][h], g["layers"], "L" if h == "left" else "R"
    asm = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    asm.component.name = "Left" if h == "left" else "Right"
    c, m = asm.component, d["matrix"]
    occs = {
        "plate": part(c, "Plate" + s, m, ("Plate" + s, [d["plate"]] + d["cutouts"] + d["stabs"], L["plate"], True), ctx=asm),
        "pcb": part(c, "Pcb" + s, m, ("Pcb" + s, [d["pcb"]], L["pcb"], True),
                    ("SocketKeepout", d["sockets"], L["socket"], False, 0.5),
                    ("JST", [d["jst"]], L["jst"]),
                    ("JSTPlugPocket", [d["jst_pocket"]], L["jst"], False, 0.25), ctx=asm),
        "switches": part(c, "Switches" + s, m, ("SwitchBottom", d["cutouts"], L["switch_bottom"]),
                         ("SwitchTop", d["switches"], L["switch_top"]), ctx=asm),
        "keycaps": part(c, "Keycaps" + s, m, ("KeyEnvelope", d["keycaps"], L["keycap"], False, 0.35), ctx=asm),
    }
    for q in d["clips"]:  # v2: q["matrix"] = the clip frame (x out from the PCB edge, y up the plate normal, z along the edge) -> world
        occs[f"clip{q['name']}"] = build_clip(c, f"Clip{q['name']}{s}", q["matrix"], q["profile"], q["lattice"],
                                              g["params"]["clip"]["len"], q["plan"], ctx=asm,
                                              marks=g["clip_variants"][q["variant"]]["marks"], mark=g["params"]["clip"])
    return asm, occs


def build_udb(root, g):
    """M2: Unified Daughterboard C3 placeholder (board with M2 holes, USB-C receptacle box), on the panel."""
    u = g["udb"]
    return part(root, "UDB", u["matrix"], ("UDBBoard", [u["board"]] + u["holes"], u["board_z"], True),
                ("USBReceptacle", [u["receptacle"]], u["receptacle_z"]))


def build_clip(parent, name, m, profile, hexes, length, plan, ctx=None, marks=0, mark=None):
    """v2: one TPU C-clip as one body in its own component. profile = the side view in the component's XY (x out from the
    PCB edge toward the wall, y = height), extruded +- length / 2 along z (the edge); hexes = the lattice cells (z along
    the edge, y height) cut through along x. plan = the clip's plan (x out, z along the edge; the recess outline less the
    fit clearance): the profile prism is intersected with it (rounds the corners clear of the recess's R1.5 ones). Placed with matrix m.
    marks = the variant's identifier: that many blind dimples (mark = the P["clip"] dict: mark_d, mark_depth, mark_x, mark_dz) in the
    lip's top face (1 = FRONT, 2 = BACK); they touch nothing and change no fit."""
    occ = parent.occurrences.addNewComponent(matrix(m))
    c = occ.component
    c.name = name
    slab(c, name, [profile], [-length / 2, length / 2])
    sp = c.sketches.add(c.xZConstructionPlane)
    sp.name = "Plan"
    sp.isComputeDeferred = True
    pp = [sp.modelToSketchSpace(P3(x, 0, z)) for x, z in plan[:-1]]
    for i in range(len(pp)):
        sp.sketchCurves.sketchLines.addByTwoPoints(pp[i], pp[(i + 1) % len(pp)])
    sp.isComputeDeferred = False
    inp = c.features.extrudeFeatures.createInput(sp.profiles.item(0), adsk.fusion.FeatureOperations.IntersectFeatureOperation)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByString("40 mm"), True)
    inp.participantBodies = [c.bRepBodies.item(0)]  # else it intersects EVERY body it touches in the design (shredded the plates and PCBs)
    c.features.extrudeFeatures.add(inp).name = "PlanTrim"
    sk = c.sketches.add(c.yZConstructionPlane)
    sk.name = "Lattice"
    sk.isComputeDeferred = True
    lines = sk.sketchCurves.sketchLines
    for hx in hexes:
        pts = [sk.modelToSketchSpace(P3(0, w, a)) for a, w in hx]  # (model y = height, z = along the edge)
        first = prev = None
        for i in range(len(pts)):
            a_ = prev.endSketchPoint if prev else pts[0]
            b_ = first.startSketchPoint if i == len(pts) - 1 else pts[i + 1]
            prev = lines.addByTwoPoints(a_, b_)
            first = first or prev
    sk.isComputeDeferred = False
    coll = adsk.core.ObjectCollection.create()
    for i in range(sk.profiles.count):
        coll.add(sk.profiles.item(i))
    inp = c.features.extrudeFeatures.createInput(coll, adsk.fusion.FeatureOperations.CutFeatureOperation)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByString("40 mm"), True)
    inp.participantBodies = [c.bRepBodies.item(0)]  # only the clip
    c.features.extrudeFeatures.add(inp).name = "LatticeCut"
    if marks:
        ytop = max(p[1] for p in profile)
        pin = c.constructionPlanes.createInput()
        pin.setByOffset(c.xZConstructionPlane, adsk.core.ValueInput.createByReal(ytop * MM))
        pl = c.constructionPlanes.add(pin)
        if abs(pl.geometry.origin.y - ytop * MM) > 1e-6:  # (the plane's normal runs the other way)
            pl.deleteMe()
            pin = c.constructionPlanes.createInput()
            pin.setByOffset(c.xZConstructionPlane, adsk.core.ValueInput.createByReal(-ytop * MM))
            pl = c.constructionPlanes.add(pin)
        pl.name = "MarkPlane"
        sm = c.sketches.add(pl)
        sm.name = "Marks"
        for k in range(marks):
            z = (k - (marks - 1) / 2) * 2 * mark["mark_dz"]
            sm.sketchCurves.sketchCircles.addByCenterRadius(sm.modelToSketchSpace(P3(mark["mark_x"], ytop, z)), mark["mark_d"] / 2 * MM)
        coll = adsk.core.ObjectCollection.create()
        for i in range(sm.profiles.count):
            coll.add(sm.profiles.item(i))
        inp = c.features.extrudeFeatures.createInput(coll, adsk.fusion.FeatureOperations.CutFeatureOperation)
        down = adsk.fusion.ExtentDirections.PositiveExtentDirection if pl.geometry.normal.y < 0 else adsk.fusion.ExtentDirections.NegativeExtentDirection
        inp.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(mark["mark_depth"] * MM)), down)
        inp.participantBodies = [c.bRepBodies.item(0)]  # only the clip
        c.features.extrudeFeatures.add(inp).name = "MarkCut"
    b = c.bRepBodies.item(0)
    b.name = name
    b.appearance = appearance("TPU clip orange", (255, 120, 0))
    return occ.createForAssemblyContext(ctx) if ctx else occ


def build_tpu_clip(root, g):
    """v2: the two printable TPU C-clips, each one watertight body: "TpuClipFront" (4: spots 1 and 5 per half) and "TpuClipBack"
    (6: 2, 3, 4), exactly the geometry placed at their spots in the halves (g["clip_variants"]): 10 long, slot 1.5 for the 1.6 PCB,
    2.5 under it, a 1.0 lip 1.5 over it with a 30 deg lead-in, an outer face leaning with its wall (FRONT 1.76 at the bottom -> 0.85
    at the lip top; BACK 0.0 -> 0.85), a lattice (2.3 cells, 0.8 walls) in the ledge, and 1 (FRONT) or 2 (BACK) dimples in the lip
    top; 6.5 high (the PCB's underside is y = 0, the clip rises 2.5 above it and 4.0 below). Placed off the case."""
    P = g["params"]
    wb = g["floor_w"] + P["floor_air"]  # the PCB underside plane
    x0 = min(p[0] for p in g["outline"]) - 40.0
    out = {}
    for i, (vn, v) in enumerate(g["clip_variants"].items()):
        prof = [[x, w - wb] for x, w in v["profile"]]
        lat = [[[a, w - wb] for a, w in hx] for hx in v["lattice"]]
        nm = "TpuClip" + vn.capitalize()
        occ = build_clip(root, nm, [[1, 0, 0, x0], [0, 1, 0, 0], [0, 0, 1, 20.0 * i], [0, 0, 0, 1]], prof, lat, P["clip"]["len"], v["plan"],
                         marks=v["marks"], mark=P["clip"])
        b = occ.component.bRepBodies.item(0)
        log(f"{nm}: {occ.component.bRepBodies.count} body, solid {b.isSolid}, {b.volume * 1000:.2f} mm3, "
            f"{P['clip']['len']} long x {max(p[1] for p in prof) - min(p[1] for p in prof):.1f} high x "
            f"{max(p[0] for p in prof) - min(p[0] for p in prof):.1f} deep; face {v['xb']} -> {v['xt']}; "
            f"{sum(len(d_) for d_ in (v['spots']['left'], v['spots']['right']))} needed")
        out[vn] = occ
    return out


def import_udb_step(udb):
    """The real UDB C3 model next to the box, for comparing the receptacle (slow: run last)."""
    if not os.path.exists(UDB_STEP):
        log("UDB STEP not found, box only:", UDB_STEP)
        return
    im = adsk.core.Application.get().importManager
    x, y, z = UDB_STEP_SHIFT
    occ = udb.component.occurrences.addNewComponent(matrix([[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]))
    occ.component.name = "UDB_C3_STEP"
    im.importToTarget(im.createSTEPImportOptions(UDB_STEP), occ.component)
    log("UDB STEP imported into UDB/UDB_C3_STEP")
    return occ.createForAssemblyContext(udb)


def check_volumes(g, halves, tol=0.02):
    """v2: every flat placeholder's bodies must add up to the volume the JSON predicts (expect_vol, shapely union area x
    thickness), within tol: a feature that touches more than its target shreds them (the plate bbox check alone only
    sees the bbox). The TPU clips: each placed one the same volume (0.2 %) as its printed variant (TpuClipFront / TpuClipBack)."""
    bad, n = [], 0
    root_ = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct).rootComponent
    printed = {vn: next(o.component.bRepBodies.item(0).volume * 1000 for o in root_.occurrences if o.component.name == "TpuClip" + vn.capitalize())
               for vn in g["clip_variants"]}
    for h, (asm, occs) in halves.items():
        tot = {}
        for o in occs.values():
            for b in o.component.bRepBodies:
                k = b.name.rstrip("0123456789")
                k = k[:-1] if k in ("PlateL", "PlateR", "PcbL", "PcbR") else k  # (the plate and PCB bodies carry the side)
                tot[(o.component.name, k)] = tot.get((o.component.name, k), 0.0) + b.volume * 1000
        for k, want in g["halves"][h]["expect_vol"].items():
            got = sum(v for (cn, kk), v in tot.items() if kk == k)
            n += 1
            if abs(got - want) > tol * want:
                bad.append(f"{h} {k}: {got:.1f} vs {want:.1f} mm3 ({(got / want - 1) * 100:+.1f} %)")
            log(f"  volume {h} {k}: {got:.1f} mm3, JSON expects {want:.1f} ({(got / want - 1) * 100:+.2f} %)")
        for q in g["halves"][h]["clips"]:  # the printed variant placed at the spot: the same volume as TpuClipFront / Back
            v = occs[f"clip{q['name']}"].component.bRepBodies.item(0).volume * 1000
            n += 1
            if abs(v - printed[q["variant"]]) > 0.002 * printed[q["variant"]]:
                bad.append(f"{h} {q['name']}: {v:.2f} mm3 (printed {q['variant']} {printed[q['variant']]:.2f})")
    log(f"CHECK placeholder volumes ({n} sums vs the JSON, +-{tol * 100:.0f} %): {len(bad)} off {bad} -> {'PASS' if not bad else 'FAIL'}")


def check_m2(design, g, halves, udb):
    check_volumes(g, halves)
    worst = 0.0
    for h, (asm, occs) in halves.items():
        d, plate_occ = g["halves"][h], occs["plate"]
        body = plate_occ.component.bRepBodies.item(0)
        bb = body.boundingBox  # component space = flat (u, v, w)
        got = [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z, bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]
        got = [v / MM for v in got]
        us, vs = [p[0] for p in d["plate"]], [p[1] for p in d["plate"]]
        want = [min(us), min(vs), g["layers"]["plate"][0], max(us), max(vs), g["layers"]["plate"][1]]
        dl = max(abs(a - b) for a, b in zip(got, want))
        pb = body.createForAssemblyContext(plate_occ)  # plate_occ is already the root proxy
        xyz = [(v.geometry.x / MM, v.geometry.y / MM, v.geometry.z / MM) for v in pb.vertices]
        wgot = [f(p[i] for p in xyz) for f in (min, max) for i in range(3)]
        dw = max(abs(a - b) for a, b in zip(wgot, d["plate_bbox_world"]))
        worst = max(worst, dl, dw)
        log(f"Plate{h[0].upper()}: flat bbox off by {dl:.5f} mm, world bbox off by {dw:.5f} mm "
            f"(world {', '.join(f'{v:.2f}' for v in wgot)}), volume {body.volume * 1000:.1f} mm3, "
            f"{body.faces.count} faces")
    log(f"CHECK plate bboxes vs JSON: max deviation {worst:.5f} mm -> {'PASS' if worst <= 0.01 else 'FAIL'}")

    ents = adsk.core.ObjectCollection.create()
    for o in (halves["left"][0], halves["right"][0], udb):
        ents.add(o)
    inp = design.createInterferenceInput(ents)
    inp.areCoincidentFacesIncluded = False
    res = design.analyzeInterference(inp)
    owner = {o.component.name: asm.component.name for asm, occs in halves.values() for o in occs.values()}
    owner[udb.component.name] = udb.component.name
    top = lambda e: e.assemblyContext.fullPathName.split("+")[0].split(":")[0] if e.assemblyContext else \
        owner.get(e.parentComponent.name, e.parentComponent.name)  # results come back as native bodies
    pairs = [(top(r.entityOne), r.entityOne.name, top(r.entityTwo), r.entityTwo.name, r.interferenceBody.volume * 1000)
             for r in (res.item(i) for i in range(res.count))]
    cross = [p for p in pairs if p[0] != p[2]]
    inner = sorted({f"{p[1].rstrip('0123456789')}/{p[3].rstrip('0123456789')}" for p in pairs if p[0] == p[2]})
    log(f"interference pairs inside one assembly (by design: the TPU clips grip the PCB, switch tops sit in the keycap "
        f"envelopes, the JST sits in its plug pocket): {len(pairs) - len(cross)}, kinds {inner}")
    log(f"CHECK interference between Left, Right and UDB: {len(cross)} pair(s) {cross} -> "
        f"{'PASS' if not cross else 'FAIL'}")


def P3(x, y, z):
    return adsk.core.Point3D.create(x * MM, y * MM, z * MM)


def half_box(m, w0, w1):
    """Temp box in a half's local frame (mm): every u, v around the case, normal coordinate w0 .. w1."""
    M = [[m[r][c] for c in range(4)] for r in range(3)]
    c = [-100 + 500 / 2, -100 + 350 / 2, (w0 + w1) / 2]
    centre = [sum(M[r][k] * c[k] for k in range(3)) + M[r][3] for r in range(3)]
    vec = lambda k: adsk.core.Vector3D.create(M[0][k], M[1][k], M[2][k])
    return adsk.core.OrientedBoundingBox3D.create(P3(*centre), vec(0), vec(1), 500 * MM, 350 * MM, (w1 - w0) * MM)


def cut(comp, target, tools, keep=False, op=adsk.fusion.FeatureOperations.CutFeatureOperation):
    coll = adsk.core.ObjectCollection.create()
    for t in tools:
        coll.add(t)
    inp = comp.features.combineFeatures.createInput(target, coll)
    inp.operation = op
    inp.isKeepToolBodies = keep
    return comp.features.combineFeatures.add(inp)


def halfspace(tbm, p, n, S=1000.0):
    """Temp box filling the side of the plane through p (mm) that unit normal n points to (S mm across)."""
    a = cross(n, (0, 0, 1)) if abs(n[2]) < 0.9 else cross(n, (1, 0, 0))
    a = [v / sum(w * w for w in a) ** 0.5 for v in a]
    b = cross(n, a)  # a x b = n: the box's height runs along n
    V = lambda v: adsk.core.Vector3D.create(*v)
    centre = P3(*(p[i] + n[i] * S / 2 for i in range(3)))
    return tbm.createBox(adsk.core.OrientedBoundingBox3D.create(centre, V(a), V(b), S * MM, S * MM, S * MM))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def lower_band_tools(tbm, lb):
    """M4: per outline edge (split at the ridge), the material outside its lean plane, between the vertical planes
    through each end's crease point and footprint point. Both lean planes at a vertex hold that line, so the
    wedges tile exactly, at convex corners, at the ridge kinks of the crease and anywhere else."""
    C, Q, N = lb["crease"], lb["foot"], lb["normals"]
    n = len(C)
    tools = []
    for i in range(n):
        j = (i + 1) % n
        mid = [(C[i][0] + C[j][0]) / 2, (C[i][1] + C[j][1]) / 2]
        t = halfspace(tbm, C[i], N[i])
        for k in (i, j):
            dx, dy = Q[k][0] - C[k][0], Q[k][1] - C[k][1]
            L = (dx * dx + dy * dy) ** 0.5
            m = [-dy / L, dx / L, 0.0]
            if m[0] * (mid[0] - C[k][0]) + m[1] * (mid[1] - C[k][1]) < 0:
                m = [-v for v in m]
            tbm.booleanOperation(t, halfspace(tbm, C[k], m), adsk.fusion.BooleanTypes.IntersectionBooleanType)
        tools.append(t)
    return tools


def local_w(m, p):
    """A world point's (cm) coordinate along a half's plate normal, mm."""
    return sum(m[r][2] * (p[r] / MM - m[r][3]) for r in range(3))


def top_faces(body, g):
    """The two top facets: planar, facing along the half's plate normal, at w = lip."""
    out = []
    for f in body.faces:
        if f.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
            continue
        pt = f.pointOnFace
        nrm = f.evaluator.getNormalAtPoint(pt)[1]
        for h in ("left", "right"):
            m = g["halves"][h]["matrix"]
            if nrm.x * m[0][2] + nrm.y * m[1][2] + nrm.z * m[2][2] > 0.99999 and \
                    abs(local_w(m, (pt.x, pt.y, pt.z)) - g["params"]["lip"]) < 0.01:
                out.append(f)
    return out


def edge_round(c, edges, r, chamfer=False, chain=True):
    coll = adsk.core.ObjectCollection.create()
    for e in edges:
        coll.add(e)
    v = adsk.core.ValueInput.createByString(f"{r} mm")
    if chamfer:
        inp = c.features.chamferFeatures.createInput2()
        inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(coll, v, chain)
        return c.features.chamferFeatures.add(inp)
    inp = c.features.filletFeatures.createInput()
    inp.edgeSetInputs.addConstantRadiusEdgeSet(coll, v, chain)
    return c.features.filletFeatures.add(inp)


def lip_ramps(c, g, dz, zone, z0=-2.0):
    """Tool for the rear band's ends: outside a straight diagonal from the band's top vertex down to the panel's outer
    top corner at the side rim (M7, user: one long shallow diagonal, no flat run-out; lip_ends = the feet, lip_run =
    their horizontal runs), continued past the desk. Drawn in XZ, extruded through Y and kept only inside zone (the
    rear strip: polygons in plan), so it trims the panel's lip, or (dz = the gap) the body's rabbet and lip pocket,
    and nothing else. The diagonal is z = f(x): the panel's from its top, the body's from below, any flat or ball
    end mill."""
    P = g["params"]
    h = g["lip_z"][1] - g["lip_z"][0]
    zt = g["lip_z"][1]
    R = P["strip_lip_r"]  # M5: the band's top corner (top edge into the diagonal), rounded; the body's by R + dz
    r_ = R + dz
    zb = -0.5  # below the desk
    sk = c.sketches.add(c.xZConstructionPlane)
    sk.name = "LipEnds"
    pt = lambda x, z: sk.modelToSketchSpace(P3(x, 0, z))
    lines = sk.sketchCurves.sketchLines
    for xe, L, sg in zip(g["lip_ends"], g["lip_run"], (1, -1)):  # the band runs +x from the left end, -x from the right one
        nl = math.hypot(L, h)
        nx_, nz_ = -h / nl, L / nl  # unit normal of the diagonal, toward the tool (outer, upper) side
        cx_, cz_ = L + R * (nl - L) / h, zt - R  # arc centre (local dx, z), on the band side
        t1 = (cx_ + r_ * nx_, cz_ + r_ * nz_)  # on the (offset) diagonal
        s_ = (t1[1] - zb) / (h / nl)
        foot = (t1[0] - s_ * L / nl, zb)
        a0, a1 = math.atan2(nz_, nx_), math.pi / 2
        arc = [(cx_ + r_ * math.cos(a0 + (a1 - a0) * k / 16), cz_ + r_ * math.sin(a0 + (a1 - a0) * k / 16)) for k in range(17)]
        X = lambda dx: xe + sg * dx
        top = zt + dz + 3
        loop = [foot] + arc + [(cx_, top), (foot[0] - 5, top), (foot[0] - 5, zb)]
        q = [pt(X(u), z) for u, z in loop]
        prev = first = None
        for i in range(len(q)):
            a_ = prev.endSketchPoint if prev else q[0]
            b_ = first.startSketchPoint if i == len(q) - 1 else q[i + 1]
            prev = lines.addByTwoPoints(a_, b_)
            first = first or prev
    coll = adsk.core.ObjectCollection.create()
    for i in range(sk.profiles.count):
        coll.add(sk.profiles.item(i))
    ext = c.features.extrudeFeatures
    inp = ext.createInput(coll, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByString("300 mm"), True)
    f = ext.add(inp)
    tools = [f.bodies.item(i) for i in range(f.bodies.count)]
    zb_ = slab(c, "RearZone", zone if isinstance(zone[0][0], list) else [zone], [z0, 60.0])
    zbody = zb_.bodies.item(0)
    for t in tools:
        cut(c, t, [zbody], keep=True, op=adsk.fusion.FeatureOperations.IntersectFeatureOperation)
    c.features.removeFeatures.add(zbody)
    return tools


def band_recess(c, g):
    """M7: the 0.4 mm recessed field on the panel's rear face (edge + band), one per rear lean plane: its (x, z)
    outline extruded through Y, kept only within the recess depth behind that plane, cut from the Panel. Needs a side
    setup when machined (the face is near-vertical); the undercut check lists those faces as 'side'."""
    P = g["params"]
    tbm = adsk.fusion.TemporaryBRepManager.get()
    lb = g["lower_band"]
    tools = []
    for idx, side in ((0, "left"), (1, "right")):
        poly = g["band_recess"][side]
        sk = c.sketches.add(c.xZConstructionPlane)
        sk.name = "BandRecess" + side
        pts = [sk.modelToSketchSpace(P3(x, 0, z)) for x, z in poly]
        lines, prev, first = sk.sketchCurves.sketchLines, None, None
        for i in range(len(pts)):
            a_ = prev.endSketchPoint if prev else pts[0]
            b_ = first.startSketchPoint if i == len(pts) - 1 else pts[i + 1]
            prev = lines.addByTwoPoints(a_, b_)
            first = first or prev
        prof = max((sk.profiles.item(i) for i in range(sk.profiles.count)), key=lambda q: q.areaProperties().area)
        inp = c.features.extrudeFeatures.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setSymmetricExtent(adsk.core.ValueInput.createByString("300 mm"), True)
        prism = c.features.extrudeFeatures.add(inp).bodies.item(0)
        c0, c1, N = lb["crease"][idx], lb["crease"][idx + 1], lb["normals"][idx]
        t = [c1[i] - c0[i] for i in range(3)]
        lt = math.sqrt(sum(v * v for v in t))
        t = [v / lt for v in t]
        mx = (c0[0] + c1[0]) / 2
        z_ = 3.0
        y_ = c0[1] - (N[0] * (mx - c0[0]) + N[2] * (z_ - c0[2])) / N[1]  # on the lean plane at (mx, z_)
        dep = P["panel_recess"][0]
        ctr = P3(mx + N[0] * (1.0 - dep) / 2, y_ + N[1] * (1.0 - dep) / 2, z_ + N[2] * (1.0 - dep) / 2)
        bx = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
            ctr, adsk.core.Vector3D.create(*t), adsk.core.Vector3D.create(*N), 400 * MM, (1.0 + dep) * MM, 100 * MM))
        tp = tbm.copy(prism)
        tbm.booleanOperation(tp, bx, adsk.fusion.BooleanTypes.IntersectionBooleanType)
        c.features.removeFeatures.add(prism)
        bf = c.features.baseFeatures.add()
        bf.startEdit()
        c.bRepBodies.add(tp, bf).name = "BandRecessTool" + side
        bf.finishEdit()
        tools.append(c.bRepBodies.itemByName("BandRecessTool" + side))
    cut(c, c.bRepBodies.itemByName("Panel"), tools)
    log(f"M7: band recess {P['panel_recess'][0]} mm on the panel's rear face (2 fields, USB frame)")


def clip_recesses(c, g):
    """v2: the 10 recesses for the TPU C-clips, cut from the Body's pocket floors. Per clip: the lead-in's outline (the
    recess grown by its depth, mouth_ext_w: the recess's R1.5 rectangle, run 0.5 past the pocket wall) drawn on the floor
    plane (a sketch on the floor face, as the opening chamfer is) and extruded 0.5 into the body with a 45 deg inward
    taper, so its bottom is the recess; that tool is trimmed to the pocket's wall prism (so the wall side is the wall itself,
    no undercut) and cut. Flat bottom parallel to the PCB, 3 open sides tapered 45 deg."""
    P = g["params"]
    rd, fw = P["clip_recess"][2], g["floor_w"]
    ext = c.features.extrudeFeatures
    B = c.bRepBodies.itemByName
    hi = g["max_height"] + 20
    many = lambda q: q if isinstance(q[0][0], list) else [q]
    bad = []
    for h in ("left", "right"):
        X = h[0].upper()
        m = g["halves"][h]["matrix"]
        wall = slab(c, "ClipWall" + X, many(g["cavity_steps"]["floor"][h]["open"]), [1.0, hi + 5]).bodies.item(0)
        for q in g["halves"][h]["clips"]:
            try:
                face = None  # (re-found each time: a cut renumbers the Body's faces)
                for f in B("Body").faces:
                    if f.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
                        continue
                    pt = f.pointOnFace
                    nf = f.evaluator.getNormalAtPoint(pt)[1]
                    if nf.x * m[0][2] + nf.y * m[1][2] + nf.z * m[2][2] > 0.99999 and abs(local_w(m, (pt.x, pt.y, pt.z)) - fw) < 0.01:
                        face = f
                        break
                o, n = face.pointOnFace, face.evaluator.getNormalAtPoint(face.pointOnFace)[1]
                zt = lambda x, y: o.z / MM - (n.x * (x - o.x / MM) + n.y * (y - o.y / MM)) / n.z
                sk = c.sketches.addWithoutEdges(face)
                sk.name = f"ClipMouth{X}{q['name']}"
                sk.isComputeDeferred = True
                pts = [sk.modelToSketchSpace(P3(x, y, zt(x, y))) for x, y in q["mouth_ext_w"]]
                lines, prev, first = sk.sketchCurves.sketchLines, None, None
                for i in range(len(pts)):
                    a_ = prev.endSketchPoint if prev else pts[0]
                    b_ = first.startSketchPoint if i == len(pts) - 1 else pts[i + 1]
                    prev = lines.addByTwoPoints(a_, b_)
                    first = first or prev
                sk.isComputeDeferred = False
                prof = max((sk.profiles.item(i) for i in range(sk.profiles.count)), key=lambda p_: p_.areaProperties().area)
                inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
                inp.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString(f"{rd} mm")),
                                     adsk.fusion.ExtentDirections.NegativeExtentDirection, adsk.core.ValueInput.createByString("-45 deg"))
                tool = ext.add(inp)
                tool.name = f"ClipRecess{X}{q['name']}"
                t = tool.bodies.item(0)
                t.name = f"ClipRecess{X}{q['name']}"
                cut(c, t, [wall], keep=True, op=adsk.fusion.FeatureOperations.IntersectFeatureOperation)
                cut(c, B("Body"), [t])
            except RuntimeError as e:
                bad.append((h, q["name"], str(e)[:70]))
        c.features.removeFeatures.add(wall)
    log(f"v2: C-clip recesses {P['clip_recess'][0]} x {P['clip_recess'][1]} x {rd} mm with a 45 deg lead-in: "
        f"{sum(len(d['clips']) for d in g['halves'].values()) - len(bad)} cut" + (f", FAILED {bad}" if bad else ""))


def build_case(root, g):
    """M3: Body = outline prism below both top planes, minus the two pockets (opening prism above its floor plane),
    the rabbet, the bottom cavity (ceiling cut to the pocket-floor planes, since it runs under the bezels and the
    web), the UDB bay, the USB slot (v2: a 22 wide chamber, then a 17 wide neck through the rear face) and the insert
    holes; v2: the C-clip recesses in the pocket floors, 4 bumpon recesses in the underside, the rear peak cut by one
    plane. Panel = panel outline minus countersunk holes and the recessed field (0.6 deep, 0.4 under the screw heads),
    plus the UDB bosses with M2 pilots. Tool bodies are kept (hidden) for the wall check."""
    P, L = g["params"], g["layers"]
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    c = occ.component
    c.name = "Case"
    one = lambda name, polys, z, outer=False: slab(c, name, polys, z, outer).bodies.item(0)
    hi = g["max_height"] + 20
    body = one("Body", [g["outline_sharp"]], [0.0, hi])  # M4 rounds the corners after the lower band
    # M6 pockets (from the top): per half one void tool, built from tools that never share a face (the shelf and the
    # islands run 0.5 mm into the pocket wall, the grooves stop short of it); the body is cut by it once, below
    cs = g["cavity_steps"]
    many = lambda q: q if isinstance(q[0][0], list) else [q]
    for h, f in cs["floor"].items():
        X = h[0].upper()
        # (M7: the void tools start at z 1.0, below the lowest groove plane over the solid front; the planes trim them)
        one("Open" + X, many(f["open"]), [1.0, hi + 5])
        one("Shelf" + X, many(f["open_run"]), [1.0, hi + 5])  # floor plane .. groove plane, less the grooves
        gr = slab(c, "Grooves" + X, many(f["grooves"]), [1.0, hi + 5])
        for i in range(gr.bodies.count):
            gr.bodies.item(i).name = f"Groove{X}{i}"
        for i, q in enumerate(q_ for q_ in cs["islands"] if q_["half"] == h):
            # M6: a boss's flat top is made by a trim cut (prism 0.5 higher, then cut down to its top): a prism cap
            # meeting the wall at a fillet tangent left zero-area triangles no tool reaches
            zz = [q["z"][0], q["z"][1] + 0.5]
            one(f"Island{X}{i}", many(q["join"]), zz).name = f"Island{X}{i}"
            alt = one(f"IslandAlt{X}{i}", many(q["join_alt"]), zz)  # fallback if the cut fails
            alt.name, alt.isLightBulbOn = f"IslandAlt{X}{i}", False  # (named even when its sketch gave 2 profiles)
    chan = slab(c, "Cavity", many(cs["chan"]), cs["chan_z"])
    for i in range(chan.bodies.count):
        chan.bodies.item(i).name = "Cavity" if i == 0 else f"Cavity_{i}"
    stub = slab(c, "JSTStub", many(cs["stubs"]), [-1.0, hi + 5])
    for i in range(stub.bodies.count):
        stub.bodies.item(i).name = f"JSTStub{i}"
    rabbet = one("Rabbet", [g["rabbet_lean"]], [-1.0, P["panel_t"]])  # = rabbet print, run out past the rear face
    bay = one("Bay", [g["bay"]], g["bay_z"])
    notch = one("Notch", [g["notch"]], g["notch_z"])
    x0, y0, x1, y1 = (min(p[0] for p in g["outline"]) - 30, min(p[1] for p in g["outline"]) - 30,
                      max(p[0] for p in g["outline"]) + 30, max(p[1] for p in g["outline"]) + 30)
    ext = one("Exterior", [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]], [0.0, hi])  # minus the styled outside, below
    panel = one("Panel", [g["panel_lean"]], [0.0, P["panel_t"]])
    B_ = c.bRepBodies.itemByName
    # M4 rear lip: the strip rises up the rear face to the USB centre; the slot runs through it; the body is cut back
    lip = one("Lip", [g["lip"]], g["lip_z"])
    cut(c, panel, [lip], op=adsk.fusion.FeatureOperations.JoinFeatureOperation)
    # band ends: the diagonal trims the band only (above the seam); the panel's underside at the back stays one flat
    # surface square to the rear edge. M7 (user): the diagonal lands on the panel's outer top corner at the side rim
    cut(c, B_("Panel"), lip_ramps(c, g, 0.0, g["rear_zone_panel"], P["panel_t"]))
    cut(c, B_("Rabbet"), lip_ramps(c, g, P["panel_gap_print"], g["rear_zone_body"], P["panel_t"] + P["panel_gap_print"]))
    # the slot through the lip, cut before the UDB bosses are added (the rear pair stands in the slot's footprint)
    cut(c, panel, [one("LipNotch", [g["notch"]], [P["panel_t"], g["lip_z"][1] + 1])])
    lip_pocket = one("LipPocket", [g["lip_pocket"]], g["lip_pocket_z"])
    cut(c, lip_pocket, lip_ramps(c, g, P["panel_gap_print"], g["rear_zone_body"]))
    # round and tilted tools: one base feature of temporary bodies
    tbm = adsk.fusion.TemporaryBRepManager.get()
    fw = g["floor_w"]
    tmp = {}
    for h, s_ in (("left", "L"), ("right", "R")):
        m = g["halves"][h]["matrix"]
        tmp["Top" + s_] = tbm.createBox(half_box(m, P["lip"], P["lip"] + 150))
        f_ = g["cavity_steps"]["floor"][h]  # M6: below the groove plane; the shelf between it and the floor plane
        tmp["BelowGroove" + s_] = tbm.createBox(half_box(m, f_["groove_w"][0] - 150, f_["groove_w"][0]))
        tmp["ShelfBox" + s_] = tbm.createBox(half_box(m, f_["groove_w"][0] - 1.0, f_["w"]))
    for h in ("left", "right"):  # M6: the boss top trims (above)
        for i, q in enumerate(q_ for q_ in g["cavity_steps"]["islands"] if q_["half"] == h):
            xs, ys = [p[0] for p in q["join"]], [p[1] for p in q["join"]]
            tmp[f"BossAbove{h[0].upper()}{i}"] = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
                P3((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, q["z"][1] + 25), adsk.core.Vector3D.create(1, 0, 0),
                adsk.core.Vector3D.create(0, 1, 0), (max(xs) - min(xs) + 2) * MM, (max(ys) - min(ys) + 2) * MM, 50 * MM))
    rh, rc, (di, dd) = P["screw_head"] / 2, P["screw_clear"] / 2, P["insert_hole"]
    cyl = lambda a, ra, b, rb: tbm.createCylinderOrCone(a, ra * MM, b, rb * MM)  # radii in mm
    for i, (x, y) in enumerate(g["screws"]):
        z0 = P["screw_seat"][0]  # v2: every screw sits on its 0.4 deep seat pad in the recessed field (the head seats on it)
        d_ = g["insert_depths"][i]  # M7: per screw (short where the pocket floor is low over it)
        tmp[f"Insert{i + 1}"] = cyl(P3(x, y, P["panel_t"] - 0.01), di / 2, P3(x, y, P["panel_t"] + d_), di / 2)
        cs = cyl(P3(x, y, z0 - 0.01), rh + 0.01, P3(x, y, z0 + rh - rc), rc)
        tbm.booleanOperation(cs, cyl(P3(x, y, -1), rc, P3(x, y, P["panel_t"] + 1), rc),
                             adsk.fusion.BooleanTypes.UnionBooleanType)
        tmp[f"Countersink{i + 1}"] = cs
    # M5 UDB standoffs in the body: left standing in the bay (cut from below round them), each with an M2 insert hole
    (bd, _), (di_, dd_), (z0_, z1_) = P["udb_mount"], P["udb_insert"], g["udb"]["mount_z"]
    for i, (x, y) in enumerate(g["udb"]["mounts"]):
        tmp[f"UdbStandoff{i + 1}"] = cyl(P3(x, y, z0_), bd / 2, P3(x, y, z1_ + 0.5), bd / 2)
        tmp[f"UdbInsert{i + 1}"] = cyl(P3(x, y, z0_ - 0.5), di_ / 2, P3(x, y, z0_ + dd_), di_ / 2)
    bx = [p[0] for p in g["bay"]]
    by = [p[1] for p in g["bay"]]
    z0, z1 = g["notch_z"][1], g["bay_z"][1]  # the bay above the slot: its rear wall is the >= 5 mm check
    tmp["BaySlotTop"] = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
        P3((min(bx) + max(bx)) / 2, (min(by) + max(by)) / 2, (z0 + z1) / 2), adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0), (max(bx) - min(bx)) * MM, (max(by) - min(by)) * MM, (z1 - z0) * MM))
    for i, t in enumerate(lower_band_tools(tbm, g["lower_band"])):
        tmp[f"Lean{i + 1}"] = t
    # v2 bumpon recesses (3M SJ5302 locating pockets in the underside)
    for i, b_ in enumerate(g["bumpons"]):
        tmp[f"Bumpon{i + 1}"] = cyl(P3(b_["x"], b_["y"], -1.0), b_["d"] / 2, P3(b_["x"], b_["y"], b_["depth"]), b_["d"] / 2)
    # v2 rear peak: everything above the one plane through the rear-face line at BC and the crest point A
    p0_, p1_, pa_ = g["rear_cut"]["points"]
    nrm_ = cross([p1_[i] - p0_[i] for i in range(3)], [pa_[i] - p0_[i] for i in range(3)])
    nrm_ = [v / math.sqrt(sum(w * w for w in nrm_)) * (1 if nrm_[2] > 0 else -1) for v in nrm_]  # up
    tmp["RearCut"] = halfspace(tbm, pa_, nrm_)
    bf = c.features.baseFeatures.add()
    bf.name = "CaseTools"
    bf.startEdit()
    for k, tb in tmp.items():
        c.bRepBodies.add(tb, bf).name = k
    bf.finishEdit()
    B = c.bRepBodies.itemByName
    # M6 floor: Open less everything under the groove plane, less the shelf (groove plane .. floor plane, run into the
    # wall, grooves taken out), less the islands (each boss trimmed to its flat top)
    Inter = adsk.fusion.FeatureOperations.IntersectFeatureOperation
    for h, f in g["cavity_steps"]["floor"].items():
        X = h[0].upper()
        cut(c, B("ShelfBox" + X), [B("Shelf" + X)], op=Inter)
        grs = [b for b in c.bRepBodies if b.name.startswith("Groove" + X)]
        if grs:
            cut(c, B("ShelfBox" + X), grs)
        qs = [q_ for q_ in g["cavity_steps"]["islands"] if q_["half"] == h]
        for i, q in enumerate(qs):
            above_ = B(f"BossAbove{X}{i}")
            for nm in (f"Island{X}{i}", f"IslandAlt{X}{i}"):
                cut(c, B(nm), [above_], keep=True)
        for t_ in [B("BelowGroove" + X), B("ShelfBox" + X)]:
            cut(c, B("Open" + X), [t_])
        for i, q in enumerate(qs):
            try:
                cut(c, B("Open" + X), [B(f"Island{X}{i}")])
                c.features.removeFeatures.add(B(f"IslandAlt{X}{i}"))
            except RuntimeError as e:
                log(f"  island {q['kind']}: cut failed ({str(e)[:50]}), using the plain wall-run outline")
                cut(c, B("Open" + X), [B(f"IslandAlt{X}{i}")])
                c.features.removeFeatures.add(B(f"Island{X}{i}"))
    cut(c, B("Bay"), [B(f"UdbStandoff{i + 1}") for i in range(len(g["udb"]["mounts"]))])
    body = B("Body")
    # M4 lower band: below the crease each face leans in by lower_cant (the panel strip's rear face too), then
    # R3 on the vertical outer corners and on the lean planes' corner lines (not at the ridge kinks)
    lean = [B(f"Lean{i + 1}") for i in range(len(g["lower_band"]["crease"]))]
    cut(c, B("Panel"), lean, keep=True)
    cut(c, body, lean)
    body = B("Body")
    CQ = [(P3(*cp), P3(*q, 0.0)) for cp, q in zip(g["lower_band"]["crease"], g["lower_band"]["foot"])]
    sharp = [tuple(p) for p in g["outline_sharp"]]
    corners = [cq for cq, cp in zip(CQ, g["lower_band"]["crease"])
               if any(abs(cp[0] - x) < 1e-3 and abs(cp[1] - y) < 1e-3 for x, y in sharp)]
    near = lambda a, b: a.distanceTo(b) < 1e-4
    creases = [cq[0] for cq in CQ]
    redges = []
    for e in body.edges:
        ends = (e.startVertex.geometry, e.endVertex.geometry)
        for cp, _ in corners:
            for a, b in (ends, ends[::-1]):
                if near(a, cp) and not any(near(b, o) for o in creases):
                    redges.append(e)
    # v2: the lean edges (~7 mm) meet the tall vertical ones at the crease: one fillet op fails there, tall edges first work
    toks = [[e.entityToken for e in redges if (e.length > 2.0) == tall] for tall in (True, False)]
    for ts in toks:  # (edge objects go stale after the first op: re-find them by token)
        edge_round(c, [c.parentDesign.findEntityByToken(t)[0] for t in ts], P["outer_r"], chain=False)
    log(f"M4: lower band cut ({len(lean)} lean planes), R{P['outer_r']} on {len(redges)} corner edges")
    body = B("Body")
    outer = c.features.copyPasteBodies.add(body).bodies.item(0)  # the styled outside, for the wall check
    outer.name = "Outer"
    cut(c, B("Exterior"), [outer])
    cut(c, body, [B("TopL"), B("TopR")])
    body = B("Body")
    tops = top_faces(body, g)
    rim_edges = [e for f in tops for e in f.edges if not all(ff in tops for ff in e.faces)]
    edge_round(c, rim_edges, P["top_round"])
    inserts = [B(f"Insert{i + 1}") for i in range(len(g["screws"]))]
    for X in ("L", "R"):  # the pocket voids alone, for the wall checks
        c.features.copyPasteBodies.add(B("Open" + X)).bodies.item(0).name = "Pocket" + X
    # M6: each JST breakthrough shares the pocket wall where it touches it: join it into its half's void tool first
    # (exactly coincident faces in a tool-tool union are fine; near-coincident ones in the body cut were not)
    for b in [b for b in c.bRepBodies if b.name.startswith("JSTStub")]:
        bb_ = b.boundingBox
        side = "L" if (bb_.minPoint.x + bb_.maxPoint.x) / 2 / MM < g["ridge_x"] else "R"
        try:
            cut(c, B("Open" + side), [b], op=adsk.fusion.FeatureOperations.JoinFeatureOperation, keep=True)
            b.name = "Joined" + b.name
        except RuntimeError as e:
            log(f"  {b.name}: join into Open{side} failed ({str(e)[:50]}); cut from the body directly")
    pockets_ = [b for b in c.bRepBodies if b.name.startswith("Open")]
    tools = pockets_ + [b for b in c.bRepBodies if b.name.startswith(("Cavity", "JSTStub"))] + \
        [B("Rabbet"), B("Bay"), B("Notch"), B("LipPocket")] + inserts + \
        [B(f"UdbInsert{i + 1}") for i in range(len(g["udb"]["mounts"]))]
    bad_ = []
    for t in tools:  # one at a time (one combine of all of them hits coincident-edge trouble), noting any that fail
        try:
            cut(c, B("Body"), [t], keep=True)
        except RuntimeError as e:
            bad_.append((t.name, str(e)[:70]))
    if bad_:
        log(f"BUILD WARNING: these tool cuts failed: {bad_}")
    body = B("Body")
    # opening chamfer: per facet, its chamfer_top outline drawn on the facet (projected straight down, as the
    # pocket walls are vertical) and cut 45 deg inward, 0.25 mm past the depth (the facet normal leans ~8 deg, which
    # moves the tool's foot ~0.12 mm), so it meets the wall exactly at the chamfer
    ext = c.features.extrudeFeatures
    for poly in g["chamfer_top"]:
        planes = [(f, f.pointOnFace, f.evaluator.getNormalAtPoint(f.pointOnFace)[1]) for f in top_faces(body, g)]
        cx = sum(p[0] for p in poly) / len(poly)
        f, o, n = next(q for q in planes if (q[1].x / MM < g["ridge_x"]) == (cx < g["ridge_x"]))  # this side's facet
        sk = c.sketches.addWithoutEdges(f)
        sk.name = "ChamferTop"
        sk.isComputeDeferred = True
        zt = lambda x, y: o.z / MM - (n.x * (x - o.x / MM) + n.y * (y - o.y / MM)) / n.z
        pts = [sk.modelToSketchSpace(P3(x, y, zt(x, y))) for x, y in poly]  # (the JSON ring is open: keep every vertex)
        lines, prev, first = sk.sketchCurves.sketchLines, None, None
        for i in range(len(pts)):
            a_ = prev.endSketchPoint if prev else pts[0]
            b_ = first.startSketchPoint if i == len(pts) - 1 else pts[i + 1]
            prev = lines.addByTwoPoints(a_, b_)
            first = first or prev
        sk.isComputeDeferred = False
        prof = max((sk.profiles.item(i) for i in range(sk.profiles.count)), key=lambda q: q.areaProperties().area)
        inp = ext.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString(f"{P['opening_chamfer'] + 0.25} mm")),
            adsk.fusion.ExtentDirections.NegativeExtentDirection, adsk.core.ValueInput.createByString("-45 deg"))
        tool = ext.add(inp)  # (a deeper taper, 1.75 mm, fails to build)
        tool.name = "OpeningChamfer"
        cut(c, body, [tool.bodies.item(0)])
        body = B("Body")
    log(f"M4: R{P['top_round']} top round ({len(rim_edges)} edges), {P['opening_chamfer']} mm x 45 deg opening "
        f"chamfer on {len(g['chamfer_top'])} openings")
    panel = B("Panel")
    cut(c, panel, [B(f"Countersink{i + 1}") for i in range(len(g["screws"]))])
    # v2: the shallow recessed field on the panel's outer face: screw_seat deep all over it (the seat pad round each screw
    # is what is left of that), then panel_recess[0] deep where the pads are not (R3 corners: the Ø6 flat end mill)
    for nm, key, zmax in (("PanelRecess", "panel_recess", P["screw_seat"][0]), ("PanelRecessDeep", "panel_recess_deep", P["panel_recess"][0])):
        f_ = slab(c, nm, many(g[key]), [-1.0, zmax])
        cut(c, B("Panel"), [f_.bodies.item(i) for i in range(f_.bodies.count)])
    band_recess(c, g)
    clip_recesses(c, g)
    cut(c, B("Body"), [B(f"Bumpon{i + 1}") for i in range(len(g["bumpons"]))])
    log(f"v2: {len(g['bumpons'])} bumpon recesses Ø{P['bumpon']['recess_d']} x {P['bumpon']['recess_depth']}, panel field "
        f"{P['panel_recess'][0]} deep with {P['screw_seat'][0]} seat pads")
    # USB slot corners: the edges along Y at the slot's sides, roof (body) and floor (panel top, in the lip)
    # v2: R3 on the neck edges (2.7 mm long) left 0.24 mm3 of roof fillet in the board's way: trimmed back below
    nx = [p[0] for p in g["notch"]]
    nk = [g["ridge_x"] - P["usb_neck"][0] / 2, g["ridge_x"] + P["usb_neck"][0] / 2]
    def slot_edges(b, z, xs):
        out = []
        for e in b.edges:
            a, q = e.startVertex.geometry, e.endVertex.geometry
            if abs(a.x - q.x) < 1e-5 and abs(a.z - q.z) < 1e-5 and abs(a.z / MM - z) < 1e-3 and \
                    min(abs(a.x / MM - x) for x in xs) < 1e-3 and abs(a.y - q.y) > 1e-4:
                out.append(e)
        return out
    # v2 (user): the visible neck gets its R3 roof corners back (the round seen from behind, as in v1). The fillet runs the
    # neck's whole length, so its inner 0.75 mm (from the step into the chamber's side) is cut away again below: the
    # fillet never comes within 1.0 mm of the board's rear edge, which sits 0.25 mm behind the step
    roof, floor = slot_edges(B("Body"), g["notch_z"][1], (min(nx), max(nx)) + tuple(nk)), slot_edges(B("Panel"), P["panel_t"], nk + [min(nx), max(nx)])
    for nm_, es_, r_ in (("roof", roof, P["usb_r"][0]), ("floor", floor, P["usb_r"][1])):
        try:
            edge_round(c, es_, r_, chain=False)
        except RuntimeError as e:  # v2: the neck's edges end at the step into the chamber; log rather than lose the build
            log(f"BUILD WARNING: USB slot {nm_} R{r_} on {len(es_)} edges failed ({str(e)[:70]})")
    # trim the neck's roof fillet back from the step (see above). Fusion's fillet end runs ~1.3 mm back past the step into the
    # chamber (measured: 0.2 mm3 in the board's way at y step - 1.27 .. step - 0.5, x up to 8.73 from the ridge), so two boxes
    # go from the chamber's void (2 mm behind the step) up to the roof plane, from under the fillet: A the neck wide (to
    # 0.75 mm in front of the step), B 18 wide (the board's width) but only to 0.2 mm behind the step, where the chamber's
    # corner arcs are still clear of it (the arc wall is at >= 0.04 behind the step)
    y_step = g["udb"]["pad"]["y"][1] + 0.5
    zr_ = g["notch_z"][1]
    for nm_, hw_, y0_, y1_ in (("NeckRoundTrimA", P["usb_neck"][0] / 2, y_step - 2.0, y_step + 0.75),
                               ("NeckRoundTrimB", P["udb"][0] / 2, y_step - 2.0, y_step - 0.2)):
        trim = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
            P3(g["ridge_x"], (y0_ + y1_) / 2, zr_ - P["usb_r"][0] / 2 - 0.25), adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0), 2 * hw_ * MM, (y1_ - y0_) * MM, (P["usb_r"][0] + 0.5) * MM))
        bf3 = c.features.baseFeatures.add()
        bf3.name = nm_
        bf3.startEdit()
        c.bRepBodies.add(trim, bf3).name = nm_
        bf3.finishEdit()
        cut(c, B("Body"), [B(nm_)])
    # M5 UDB rest pad on the slot roof, trimmed by the roof corners' Ø6 ball paths (so both stay machinable from below)
    pd_ = g["udb"]["pad"]
    (px0, px1), (py0, py1), (pz0, pz1) = pd_["x"], pd_["y"], pd_["z"]
    pad = tbm.createBox(adsk.core.OrientedBoundingBox3D.create(
        P3((px0 + px1) / 2, (py0 + py1) / 2, (pz0 + pz1) / 2), adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0), (px1 - px0) * MM, (py1 - py0) * MM, (pz1 - pz0) * MM))
    zr = g["notch_z"][1] - P["usb_r"][0]
    for xc in (px0, px1):
        tbm.booleanOperation(pad, cyl(P3(xc, py0 - 1, zr), P["usb_r"][0], P3(xc, py1 + 1, zr), P["usb_r"][0]),
                             adsk.fusion.BooleanTypes.DifferenceBooleanType)
    bf2 = c.features.baseFeatures.add()
    bf2.name = "UdbRestPad"
    bf2.startEdit()
    c.bRepBodies.add(pad, bf2).name = "UdbRestPad"
    bf2.finishEdit()
    cut(c, B("Body"), [B("UdbRestPad")], op=adsk.fusion.FeatureOperations.JoinFeatureOperation)
    log(f"M4: USB slot corners R{P['usb_r'][0]} roof ({len(roof)} edges), R{P['usb_r'][1]} floor ({len(floor)} edges)")
    # v2: the rear peak, last (the top round and the opening chamfer are on the two facets): the cut face is plain; the
    # opening edges the plane meets (the pockets under it) stay sharp, as does its edge with the facets
    cut(c, B("Body"), [B("RearCut")])
    rc_ = g["rear_cut"]
    log(f"v2: rear peak cut: plane through A ({rc_['A'][0]:.2f}, {rc_['A'][1]:.2f}, {rc_['A'][2]:.2f}) and the rear-face line at z "
        f"{rc_['bc']:.2f} (BC), triangle {rc_['face'][0]:.1f} x {rc_['face'][1]:.1f}")
    body, panel = B("Body"), B("Panel")
    log(f"Case: Body {body.volume * 1000:.0f} mm3, {body.faces.count} faces; Panel {panel.volume * 1000:.0f} mm3, "
        f"{panel.faces.count} faces; bodies {[b.name for b in c.bRepBodies]}")
    return occ


def check_m3(design, g, halves, udb, case):
    P, c = g["params"], case.component
    B = lambda n: c.bRepBodies.itemByName(n).createForAssemblyContext(case)
    body, panel = B("Body"), B("Panel")
    mm = lambda a, b: adsk.core.Application.get().measureManager.measureMinimumDistance(a, b).value / MM
    ok = {}

    # interference: Body and Panel against every placeholder body (keycap envelopes included) and each other
    ents = adsk.core.ObjectCollection.create()
    for o in (halves["left"][0], halves["right"][0], udb):
        ents.add(o)
    ents.add(body)
    ents.add(panel)
    inp = design.createInterferenceInput(ents)
    inp.areCoincidentFacesIncluded = False
    res = design.analyzeInterference(inp)
    hits = [(r.entityOne.name, r.entityTwo.name, round(r.interferenceBody.volume * 1000, 3))
            for r in (res.item(i) for i in range(res.count))]
    hits = [h for h in hits if {"Body", "Panel"} & {h[0], h[1]}]
    nplace = sum(o.component.bRepBodies.count for asm, occs in halves.values() for o in occs.values())
    ok["interference"] = not hits
    log(f"CHECK interference, case Body + Panel vs {nplace} placeholder bodies + UDB: {len(hits)} pair(s) {hits[:20]} -> "
        f"{'PASS' if not hits else 'FAIL'}")

    # v2 the PRINTED variants at their spots (the bodies in the halves are the TpuClipFront / Back geometry, not per-spot fit bodies):
    # none touches the Body (>= wall_air - 0.02 from it, i.e. no collision with the pocket wall or the recess walls, the 0.2 fit
    # and the 0.1 air), the tightest spot of each variant is at 0.1, and each meets its PCB only in the lip's 0.1 grip
    # (the interference volume <= 1.6 mm3: 1.5 over the edge x 0.1 x 10)
    grip = 0.0
    nvar = {"front": 0, "back": 0}
    for h, (asm, occs) in halves.items():
        for q in g["halves"][h]["clips"]:
            cb = occs[f"clip{q['name']}"].component.bRepBodies.item(0).createForAssemblyContext(occs[f"clip{q['name']}"])
            vn = q["variant"]
            nvar[vn] += 1
            ents_ = adsk.core.ObjectCollection.create()
            ents_.add(cb)
            ents_.add(occs["pcb"].component.bRepBodies.item(0).createForAssemblyContext(occs["pcb"]))
            inp_ = design.createInterferenceInput(ents_)
            inp_.areCoincidentFacesIncluded = False
            r_ = design.analyzeInterference(inp_)
            grip = max([grip] + [r_.item(i).interferenceBody.volume * 1000 for i in range(r_.count)])
    ok["variants"] = nvar == {"front": 4, "back": 6} and 0 < grip <= 1.6
    log(f"CHECK printed clip variants at their spots: FRONT {nvar['front']} + BACK {nvar['back']} = 10; interference with the Body (above), "
        f"largest PCB grip overlap {grip:.2f} mm3 (want 0 < v <= 1.6) -> {'PASS' if ok['variants'] else 'FAIL'}")
    # v2 PCB-to-wall gap: from the PCB edge at each C-clip's centre, at the PCB's underside, mid and top, to the case Body: at
    # least pcb_wall_min (0.80) at all three; the pocket is vertical and the PCB tilted, so it is 0.8 .. 1.3 over the clips
    worst = 9.0
    for h, (asm, occs) in halves.items():
        d, M = g["halves"][h], g["halves"][h]["matrix"]
        for q in d["clips"]:
            ux, uy = q["edge_pt"]
            gaps = []
            for w in (g["pcb_mid_w"] - P["pcb_t"] / 2, g["pcb_mid_w"], g["pcb_mid_w"] + P["pcb_t"] / 2):
                X, Y, Z = (sum(M[r][k] * v for k, v in enumerate((ux, uy, w))) + M[r][3] for r in range(3))
                gaps.append(mm(P3(X, Y, Z), body))
            worst = min(worst, min(gaps))
            log(f"  clip {h} {q['name']}: PCB-to-wall gap bottom/mid/top {gaps[0]:.3f} / {gaps[1]:.3f} / {gaps[2]:.3f} mm")
    ok["pcb_gap"] = worst >= P["pcb_wall_min"] - 0.02
    log(f"CHECK PCB-to-wall gap at the clips >= {P['pcb_wall_min']} (-0.02): smallest {worst:.3f} mm -> {'PASS' if ok['pcb_gap'] else 'FAIL'}")

    # USB opening (notch faces in the body) vs the receptacle box
    rec = udb.component.bRepBodies.itemByName("USBReceptacle").createForAssemblyContext(udb).boundingBox
    rcx, rcz = (rec.minPoint.x + rec.maxPoint.x) / 2 / MM, (rec.minPoint.z + rec.maxPoint.z) / 2 / MM
    # probe the notch edges along x and z with point containment (0.01 mm steps): the sides 1 mm behind the bay (ahead
    # of the lip pocket), the top between the UDB rest pad and the rear face
    lp_y = min(p[1] for p in (g["lip_pocket"] if isinstance(g["lip_pocket"][0][0], (int, float)) else g["lip_pocket"][0])
               if abs(p[0] - g["ridge_x"]) < 20)  # M7 (panel_t 4: the slot's sides end at the band pocket sooner)
    y_side, y_top = min(min(p[1] for p in g["notch"]) + P["pocket_r"] + 1.0, lp_y - 0.5), g["udb"]["pad"]["y"][1] + 0.5
    inside = lambda x, z, y: body.pointContainment(P3(x, y, z)) != adsk.fusion.PointContainment.PointOutsidePointContainment
    edge = lambda f, a, b: next(a + (b - a) * i / 2000 for i in range(2001) if f(a + (b - a) * i / 2000))
    xl, xr = edge(lambda x: inside(x, rcz, y_side), rcx, rcx - 15), edge(lambda x: inside(x, rcz, y_side), rcx, rcx + 15)
    zt = edge(lambda z: inside(rcx, z, y_top), rcz, rcz + 10)
    zb = P["panel_t"]  # the notch is open to the bottom: its lower edge is the panel seam
    oc = ((xl + xr) / 2, (zb + zt) / 2)
    dev = ((oc[0] - rcx) ** 2 + (oc[1] - rcz) ** 2) ** 0.5
    # v2: stepped: the chamber (usb_slot_w wide, probed above) and the neck through the rear face (usb_neck[0] wide, probed 1 mm
    # behind the step, above the band's top, below the roof's R3 corners); the step's depth is the geometry test's
    try:
        y_neck, z_neck = g["udb"]["pad"]["y"][1] + 0.5 + 1.0, g["lip_z"][1] + P["panel_gap_print"] + 0.3
        nl_, nr_ = edge(lambda x: inside(x, z_neck, y_neck), rcx, rcx - 15), edge(lambda x: inside(x, z_neck, y_neck), rcx, rcx + 15)
        neck_w = nr_ - nl_
    except StopIteration:
        neck_w = -1.0
    ok["usb"] = dev <= 0.2 and abs(neck_w - P["usb_neck"][0]) <= 0.05 and abs((xr - xl) - P["usb_slot_w"]) <= 0.05
    log(f"CHECK USB opening: chamber {xr - xl:.2f} (want {P['usb_slot_w']}) x {zt - zb:.2f} mm, neck {neck_w:.2f} (want {P['usb_neck'][0]}) "
        f"x {P['usb_neck'][1]} deep; centre ({oc[0]:.3f}, z {oc[1]:.3f}) "
        f"vs receptacle ({rcx:.3f}, z {rcz:.3f}): {dev:.3f} mm -> {'PASS' if ok['usb'] else 'FAIL'}")

    # walls: min distance between each kept void tool and the outside of the outline, the two pockets, and
    # each insert hole and the cavity. The bay and inserts are listed separately (known thin spots).
    T = B
    ext = T("Exterior")
    POCK = [T(b.name) for b in c.bRepBodies if b.name.startswith("Pocket")]
    walls = {"pocketL-outside": mm(T("PocketL"), ext), "pocketR-outside": mm(T("PocketR"), ext),
             "web pocketL-pocketR": mm(T("PocketL"), T("PocketR")), "cavity-outside": mm(T("Cavity"), ext),
             "insert-outside": min(mm(T(f"Insert{i + 1}"), ext) for i in range(len(g["screws"]))),
             "bay-pockets (bay ceiling to floor)": min(mm(T("Bay"), q) for q in POCK),
             "bay-outside (rear wall above the slot; the slot itself is the intended opening)": mm(T("BaySlotTop"), ext),
             "insert-cavity": min(mm(T(f"Insert{i + 1}"), T("Cavity")) for i in range(len(g["screws"]))),
             "insert-lip pocket": min(mm(T(f"Insert{i + 1}"), T("LipPocket")) for i in range(len(g["screws"]))),
             "cavity-lip pocket": mm(T("Cavity"), T("LipPocket"))}
    for k, v in walls.items():
        log(f"  wall {k}: {v:.2f} mm")
    thin = {k: round(v, 4) for k, v in walls.items() if v < 5 - 1e-4}  # 0.1 um: measure noise on exact-5 walls
    ok["walls"] = not thin
    # M6: bezel top = plate top + lip along the normal, at the plate's 4 corners and centre, each half (the facet
    # read back from the body)
    lips = []
    for h, (asm, occs) in halves.items():
        m = g["halves"][h]["matrix"]
        nrm = (m[0][2], m[1][2], m[2][2])
        fs = [f for f in top_faces(body.nativeObject if body.nativeObject else body, g)
              if (lambda n_: n_.x * nrm[0] + n_.y * nrm[1] + n_.z * nrm[2])(f.evaluator.getNormalAtPoint(f.pointOnFace)[1]) > 0.99999]
        o_ = fs[0].pointOnFace
        us, vs = [p[0] for p in g["halves"][h]["plate"]], [p[1] for p in g["halves"][h]["plate"]]
        for u_, v_ in ((min(us), min(vs)), (max(us), min(vs)), (min(us), max(vs)), (max(us), max(vs)),
                       ((min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2)):
            p_ = [sum(m[r][k] * x for k, x in enumerate((u_, v_, 0.0))) + m[r][3] for r in range(3)]
            lips.append(sum((o_.x / MM, o_.y / MM, o_.z / MM)[r] * nrm[r] - p_[r] * nrm[r] for r in range(3)))
    ok["lip"] = len(lips) == 10 and max(abs(v - P["lip"]) for v in lips) <= 0.05
    log(f"CHECK bezel top over the plate top along the normal (4 corners + centre per half): "
        f"{min(lips):.3f} .. {max(lips):.3f} mm (lip {P['lip']}) -> {'PASS' if ok['lip'] else 'FAIL'}")
    # v2 recess fit (replaces the snap pillar tops): each of the 10 clip bodies sits in its recess: no interference with the
    # Body (the interference check above lists them by name: the spine stands 0.1 off the wall, the sides are free), the bottom
    # on the recess floor (distance 0), and under it >= clip_floor_min - recess depth of Body down to the underside, i.e. the
    # floor plane there is >= clip_floor_min above the desk (the local exception to base_min)
    IN_ = adsk.fusion.PointContainment.PointInsidePointContainment
    worst_d, worst_t, n_c = 0.0, 99.0, 0
    for h, (asm, occs) in halves.items():
        M = g["halves"][h]["matrix"]
        for q in g["halves"][h]["clips"]:
            occ = occs[f"clip{q['name']}"]
            cb = occ.component.bRepBodies.item(0).createForAssemblyContext(occ)
            worst_d = max(worst_d, mm(cb, body))
            # the recess bottom's world point under the clip's ledge middle: edge point 1 mm inboard, w = floor - depth
            ex, ey = q["edge_pt"]
            nx_, ny_ = q["n"]
            u_, v_ = ex - nx_ * 1.0, ey - ny_ * 1.0
            wb_ = g["floor_w"] - P["clip_recess"][2]
            X, Y, Z = (sum(M[r][k] * v for k, v in enumerate((u_, v_, wb_))) + M[r][3] for r in range(3))
            z, ins = Z - 0.02, lambda zz: body.pointContainment(P3(X, Y, zz)) == IN_
            if ins(z):
                while ins(z - 0.25) and z > Z - 12:
                    z -= 0.25
                lo, hi_ = z - 0.25, z  # (lo: air or deeper, hi_: Body)
                while hi_ - lo > 0.01:
                    mid_ = (lo + hi_) / 2
                    lo, hi_ = (lo, mid_) if ins(mid_) else (mid_, hi_)
                worst_t = min(worst_t, Z - (lo + hi_) / 2)
            else:
                worst_t = 0.0
            n_c += 1
    ok["clip_fit"] = n_c == 10 and worst_d <= 0.02 and worst_t >= P["clip_floor_min"] - P["clip_recess"][2] - 0.02
    log(f"CHECK C-clip recess fit ({n_c} clips): bottoms {worst_d:.4f} mm off the recess floors (want 0), Body under the recess "
        f"floor >= {worst_t:.2f} mm (want >= {P['clip_floor_min'] - P['clip_recess'][2]}, i.e. the floor plane >= {P['clip_floor_min']} above the desk) "
        f"-> {'PASS' if ok['clip_fit'] else 'FAIL'}")
    # M5: >= 3 mm of floor over the cable channels (the breakthroughs round the JSTs are the intended openings)
    chans = [T(b.name) for b in c.bRepBodies if b.name.startswith("Cavity")]
    fc = min(mm(a, q) for a in chans for q in POCK)
    ok["floor_channel"] = fc >= 3 - 1e-4
    log(f"CHECK pocket floor over the cable channels >= 3 mm: {fc:.2f} mm -> {'PASS' if ok['floor_channel'] else 'FAIL'}")
    # M5: the two back-corner inserts sit under the pocket floor (short inserts there): material over them >= 5 mm
    # (the floor tools overlap the bosses joined after them, so probe up from each insert's top instead)
    def up(x, y, z0):
        z = z0
        while body.pointContainment(P3(x, y, z + 0.05)) == adsk.fusion.PointContainment.PointInsidePointContainment and z < z0 + 40:
            z += 0.05
        return z - z0
    ri = P["insert_hole"][0] / 2
    cover = min(up(x + ri * math.cos(a) * k_, y + ri * math.sin(a) * k_,
                   P["panel_t"] + g["insert_depths"][i])
                for i, (x, y) in enumerate(g["screws"]) for k_ in (0, 1) for a in [j * math.pi / 4 for j in range(8)])
    ok["insert_cover"] = cover >= 5 - 1e-4
    log(f"CHECK M3 inserts: material over each (straight up, 9 points; short inserts where the floor is low) >= 5 mm: {cover:.2f} mm -> "
        f"{'PASS' if ok['insert_cover'] else 'FAIL'}")
    log(f"CHECK thinnest wall >= 5 mm: min {min(walls.values()):.2f} mm; under 5: {thin} -> "
        f"{'PASS' if not thin else 'FAIL'}  (plan values from geometry.py, M4 lean included: {g['walls']})")
    # M5 regression: the UDB standoffs stand in the bay ceiling (a build once cut the old panel bosses away
    # silently): body material in the standoff ring at mid-height, air just outside it, the insert hole open
    (bd, di_), (z0_, z1_) = (P["udb_mount"][0], P["udb_insert"][0]), g["udb"]["mount_z"]
    st = lambda x, y: body.pointContainment(P3(x, y, (z0_ + z1_) / 2))
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    bosses = []
    for x, y in g["udb"]["mounts"]:
        ring = all(st(x + (bd + di_) / 4 * math.cos(a), y + (bd + di_) / 4 * math.sin(a)) == IN for a in [k * math.pi / 4 for k in range(8)])
        bosses.append(ring and st(x, y + bd / 2 + 0.3) != IN and st(x, y) != IN)
    ok["udb_standoffs"] = len(bosses) == 2 and all(bosses)
    pd_ = g["udb"]["pad"]
    pc = P3(g["ridge_x"], sum(pd_["y"]) / 2, pd_["z"][0] + 0.25)
    ok["udb_pad"] = body.pointContainment(pc) == IN
    log(f"CHECK UDB rest pad over the board's rear edge (board back face at z {pd_['z'][0]:.2f}): "
        f"{'PASS' if ok['udb_pad'] else 'FAIL'}")
    if globals().get("SKIP_STANDOFF"):  # M6: hung inside the build several times; scratchpad standoffs.py checks it alone
        log("  (UDB standoff insert check skipped here; run on its own)")
        ok["udb_insert_wall"] = True
        return ok
    # (the floor tools overlap the bosses joined after them: probe straight up from each insert's top instead)
    def up_(x, y, z0):  # (M6: 0.5 mm steps then bisection; 0.05 mm steps, or a ray, ran for many minutes)
        ins = lambda z: body.pointContainment(P3(x, y, z)) == IN
        if not ins(z0 + 0.01):
            return 0.0
        z = z0
        while ins(z + 0.5) and z < z0 + 30:
            z += 0.5
        lo, hi = z, z + 0.5
        while hi - lo > 0.01:
            m = (lo + hi) / 2
            lo, hi = (m, hi) if ins(m) else (lo, m)
        return lo - z0
    zi = z0_ + P["udb_insert"][1]
    walls_udb = min([up_(x + di_ / 2 * math.cos(a) * k_, y + di_ / 2 * math.sin(a) * k_, zi) for x, y in g["udb"]["mounts"]
                     for k_ in (0, 1) for a in [j * math.pi / 4 for j in range(8)]] +
                    [])  # (M6: the insert-to-outside distance is the geometry's wall check; a min-distance query here hung)
    ok["udb_insert_wall"] = walls_udb >= 5 - 1e-4
    log(f"CHECK UDB standoffs in the body (Ø{bd} x {z1_ - z0_:.1f} mm, M2 insert hole Ø{di_} open): {sum(bosses)}/2; "
        f"material over / outside each insert {walls_udb:.2f} mm (to the cavity: geometry test) -> "
        f"{'PASS' if ok['udb_standoffs'] and ok['udb_insert_wall'] else 'FAIL'}")
    for b in c.bRepBodies:  # the kept tools
        b.isLightBulbOn = b.name in ("Body", "Panel")
    return ok


def check_m4(g, case):
    """Crease: sampled along every edge between an upright outer face and a lower-band face, the vertical depth
    below the top edge (the two top facet planes, read back from the body) against the rule: the per-vertex depth
    from geometry.py (crease_depth on the front, deeper on the back), straight between vertices. Lower band: every
    face below a crease is planar (the R3 corner blends aside) and leans lower_cant +- 1 deg."""
    P = g["params"]
    body = case.component.bRepBodies.itemByName("Body")
    planes = [(f.pointOnFace, f.evaluator.getNormalAtPoint(f.pointOnFace)[1]) for f in top_faces(body, g)]
    ztop = lambda x, y: min(o.z - (n.x * (x - o.x) + n.y * (y - o.y)) / n.z for o, n in planes)
    nz = lambda f, pt: f.evaluator.getNormalAtPoint(pt)[1].z
    lb = g["lower_band"]
    ring, dep = [c[:2] for c in lb["crease"]], lb["depth"]

    def want(x, y):  # the rule's depth at the nearest point of the sharp outline ring
        best = None
        for i in range(len(ring)):
            (ax, ay), (bx, by) = ring[i], ring[(i + 1) % len(ring)]
            t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
            d = math.hypot(ax + t * (bx - ax) - x, ay + t * (by - ay) - y)
            if best is None or d < best[0]:
                best = (d, dep[i] + t * (dep[(i + 1) % len(ring)] - dep[i]))
        return best[1]
    depths, corner_depths, lean_faces, blends, n_edges = [], [], {}, set(), 0
    for e in body.edges:
        if e.faces.count != 2:
            continue
        ev = e.evaluator
        _, t0, t1 = ev.getParameterExtents()
        _, mid = ev.getPointAtParameter((t0 + t1) / 2)
        _, d = ev.getFirstDerivative((t0 + t1) / 2)
        if abs(d.z) > 0.5 * d.length:
            continue  # upright edges (the slot sides), not a crease
        fa, fb = e.faces.item(0), e.faces.item(1)
        za, zb = nz(fa, mid), nz(fb, mid)
        up, low = (fa, fb) if abs(za) < 1e-4 and -0.5 < zb < -0.01 else (fb, fa) if abs(zb) < 1e-4 and -0.5 < za < -0.01 else (None, None)
        if not up:
            continue
        flat = low.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType and \
            up.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType
        n_edges += flat
        for k in range(9):
            _, pt = ev.getPointAtParameter(t0 + (t1 - t0) * (0.001 + 0.998 * k / 8))
            got = (ztop(pt.x, pt.y) - pt.z) / MM
            (depths if flat else corner_depths).append((got, got - want(pt.x / MM, pt.y / MM)))
        if low.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
            lean_faces[low.tempId] = low
        else:
            blends.add(low.tempId)
    ok_c = depths and max(abs(e) for _, e in depths) < 0.01
    front_ = (f"{P['crease_depth']} mm on the front" if P.get("crease_mode", "deepening") == "deepening" else
              f"front faces level ({P['crease_mode']}), {min(dep):.2f} .. {max(dep):.2f} mm overall")  # M6: was stale
    log(f"CHECK crease depth rule ({front_}, {max(dep):.2f} mm at the deepest, straight on "
        f"every face; wall plane over lean plane): {n_edges} crease edges, {len(depths)} samples, depth "
        f"{min(d for d, _ in depths):.3f} .. {max(d for d, _ in depths):.3f} mm, off the rule by "
        f"{max(abs(e) for _, e in depths):.4f} mm max -> {'PASS' if ok_c else 'FAIL'}")
    log(f"  info: across the R{P['outer_r']} corner blends (where the vertical and the lean-line fillets meet) the "
        f"crease is off the rule by {min(e for _, e in corner_depths):+.3f} .. {max(e for _, e in corner_depths):+.3f} mm")
    angles = []
    for f in lean_faces.values():
        angles.append(math.degrees(math.asin(-f.evaluator.getNormalAtPoint(f.pointOnFace)[1].z)))
    # every face that leans in, anywhere on the body, must be one of these planes or a corner blend
    # (v2: not the faces inside the USB chamber: its roof fillets / corner blends face down by construction, and which of
    # their points pointOnFace picks decides whether their normal lies in the band)
    in_slot = lambda f: f.boundingBox.minPoint.x / MM >= g["ridge_x"] - P["usb_slot_w"] / 2 - 0.1 and \
        f.boundingBox.maxPoint.x / MM <= g["ridge_x"] + P["usb_slot_w"] / 2 + 0.1 and f.boundingBox.maxPoint.z / MM <= g["notch_z"][1] + 0.05
    strays = [f for f in body.faces if f.tempId not in lean_faces and f.tempId not in blends
              and -0.5 < nz(f, f.pointOnFace) < -0.01 and not in_slot(f)]
    # one plane per ring edge, less the collinear ones (a horizontal crease makes the back one plane)
    n_ring = len({tuple(round(v, 6) for v in n_) for n_ in g["lower_band"]["normals"]})
    ok_l = len(lean_faces) == n_ring and all(abs(a - P["lower_cant"]) <= 1 for a in angles) and not strays
    log(f"CHECK lower band: {len(lean_faces)} planar faces (want {n_ring}: one per distinct lean plane), "
        f"{len(blends)} R{P['outer_r']} corner blends, lean {', '.join(f'{a:.2f}' for a in angles)} deg, "
        f"{len(strays)} other inward-leaning faces -> {'PASS' if ok_l else 'FAIL'}")
    # M6 (re-added): the web top is flush with the two top facets: probes on a 1 mm grid over the web (within
    # web_band of the ridge, >= 2 mm from every opening / outline edge) are body 0.02 under the facet, air 0.02 over
    def d_edge(x, y, ring_):
        best_ = 1e9
        for (ax, ay), (bx, by) in zip(ring_, ring_[1:] + ring_[:1]):
            vx, vy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy or 1)))
            best_ = min(best_, math.hypot(x - ax - t * vx, y - ay - t * vy))
        return best_
    def inside(x, y, ring_):
        c_ = False
        for (ax, ay), (bx, by) in zip(ring_, ring_[1:] + ring_[:1]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                c_ = not c_
        return c_
    ops_ = g["opening"] if isinstance(g["opening"][0][0], list) else [g["opening"]]
    r_, wb_ = g["ridge_x"], P["web_band"]
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    ys = [p[1] for p in g["outline"]]
    n_w, bad_w = 0, []
    cut_tri = g["rear_cut"]["plan"]  # v2: the rear peak's plane replaces the facets there
    for xi in range(int(2 * wb_) + 1):
        x = r_ - wb_ + xi
        for yi in range(int(max(ys) - min(ys)) + 1):
            y = min(ys) + yi
            if not inside(x, y, g["outline"]) or any(inside(x, y, o_) for o_ in ops_) or inside(x, y, cut_tri) or \
                    min([d_edge(x, y, g["outline"])] + [d_edge(x, y, o_) for o_ in ops_] + [d_edge(x, y, cut_tri)]) < 2.0:
                continue
            n_w += 1
            z = ztop(x * MM, y * MM) / MM
            if body.pointContainment(P3(x, y, z - 0.02)) != IN or body.pointContainment(P3(x, y, z + 0.02)) == IN:
                bad_w.append((x, y))
    ok_w = n_w > 50 and not bad_w
    log(f"CHECK web top flush with the top facets ({P['web_mode']} web, outside the rear cut's triangle): {n_w} probes, {len(bad_w)} off "
        f"{bad_w[:5]} -> {'PASS' if ok_w else 'FAIL'}")
    return {"crease": ok_c, "lower_band": ok_l, "web_flush": ok_w, **check_rear_cut(g, case)}


def check_rear_cut(g, case):
    """v2 rear peak: the Body's top over the cut triangle is the one plane (probed at 7 points of the triangle: body 0.02 under
    the plane, air 0.02 over); BC (the rear face's top line) and A (the crest point) are where the JSON says (body
    0.02 under, air 0.02 over); the cut triangle >= 6 mm from the pockets (geometry); the cut stays blind to the UDB bay
    (>= 5 mm of body over its top corners); the rear face keeps ~25.6 mm over the USB slot (measured outside the neck)."""
    P, c = g["params"], case.component
    rc = g["rear_cut"]
    body = c.bRepBodies.itemByName("Body")
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    zp = lambda x, y: rc["bc"] + rc["k"] * (y - rc["y_rear"])

    tri = rc["plan"]
    ops_ = g["opening"] if isinstance(g["opening"][0][0], list) else [g["opening"]]

    def pip(x, y, ring):
        c_ = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                c_ = not c_
        return c_
    # probes: a 4 mm grid over the triangle, off the pockets (over a pocket there is no Body at the plane: the wall over the
    # pockets is the geometry test's number), up to 9 of them spread over it
    cand = [(x, y) for x in range(int(min(p[0] for p in tri)), int(max(p[0] for p in tri)), 4)
            for y in range(int(min(p[1] for p in tri)), int(max(p[1] for p in tri)), 4)
            if pip(x, y, tri) and not any(pip(x, y, o_) for o_ in ops_)]
    pts = cand[::max(1, len(cand) // 9)][:9]
    dev = []
    for x, y in pts:
        z0 = zp(x, y)
        if body.pointContainment(P3(x, y, z0 - 0.02)) == IN and body.pointContainment(P3(x, y, z0 + 0.02)) != IN:
            dev.append(0.0)
        elif body.pointContainment(P3(x, y, z0 - 0.02)) == IN:
            dev.append(9.9)  # body above the plane
    n_on = len(dev)
    A = rc["A"]
    at_A = body.pointContainment(P3(A[0], A[1] + 0.02, A[2] - 0.02)) == IN and body.pointContainment(P3(A[0], A[1] + 0.02, A[2] + 0.02)) != IN
    # BC: just in front of the rear face, over a plate-free spot on the face line (the middle, outside the USB neck)
    xb = rc["x"][0] + (rc["x"][1] - rc["x"][0]) * 0.3
    yb = rc["y_rear"] - 0.05
    at_bc = body.pointContainment(P3(xb, yb, rc["bc"] - 0.02)) == IN and body.pointContainment(P3(xb, yb, rc["bc"] + 0.02)) != IN
    # the band above the USB slot's top, measured on the rear face outside the neck
    zt = rc["bc"]
    usb_top = P["panel_t"] + P["usb_opening"][1]
    band = zt - usb_top
    bay_top = g["bay_z"][1]
    corners = [(x, y) for x in (min(p[0] for p in g["bay"]) + 1, max(p[0] for p in g["bay"]) - 1)
               for y in (min(p[1] for p in g["bay"]) + 1, max(p[1] for p in g["bay"]) - 1)]
    over = []
    for x, y in corners:  # body from the bay's top up to the plane (or the facet, where the plane is above it)
        z = bay_top
        while body.pointContainment(P3(x, y, z + 0.25)) == IN and z < bay_top + 40:
            z += 0.25
        over.append(z - bay_top)
    ok = n_on >= 3 and max(dev) < 1 and at_A and at_bc and 24 <= band <= 27 and min(over) >= 5 and rc["pocket_margin"] >= 6 and 90 <= rc["face"][0] <= 120
    log(f"CHECK rear peak cut (one plane, A ({A[0]:.1f}, {A[1]:.1f}, {A[2]:.2f}), BC {rc['bc']:.2f}, triangle {rc['face'][0]:.0f} x "
        f"{rc['face'][1]:.0f}): {n_on} probes on the plane, {sum(d > 1 for d in dev)} off; A on the crest {at_A}; BC on the rear face {at_bc}; "
        f"band over the USB slot {band:.1f} mm; body over the UDB bay top >= {min(over):.1f} mm (want >= 5); wall over the plate top at the "
        f"pockets under it {rc['pocket_wall_min']} (geometry: none under the triangle); its plan to the pockets {rc['pocket_margin']:.2f} mm "
        f"(geometry, want >= 6) -> {'PASS' if ok else 'FAIL'}")
    return {"rear_cut": ok}


def check_m5(g, case):
    """M5 undercut check (§7: 3-axis, two operations). Each face is sampled (a 5 x 5 parameter grid + its point on
    face); a sample is reachable from +Z (op 2, top down) when its normal doesn't point down and a ray straight up
    from just off it meets nothing of the same part, and from -Z (op 1) likewise downward. A face passes when one op
    reaches every sample ('top' / 'bottom' / 'both') or each sample by one of them ('split'). Exterior Body faces
    must also follow the crease rule: above the crease from +Z, below from -Z. The Panel is its own part with its own
    two sides. A face with a single unreachable sample on its boundary (a ray grazing a neighbour) is 'graze' (info).
    Rays are zero-width: tool radii are the internal-radius check's job (case/geometry.py corner table)."""
    c = case.component
    B = c.bRepBodies.itemByName
    ring = g["lower_band"]["crease"]

    def crease_z(x, y):
        best = None
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
            d = math.hypot(a[0] + t * dx - x, a[1] + t * dy - y)
            if best is None or d < best[0]:
                best = (d, a[2] + t * (b[2] - a[2]))
        return best[1]

    def samples(f):
        ev = f.evaluator
        ps = [ev.getParameterAtPoint(f.pointOnFace)[1]]
        try:
            r = ev.parametricRange()
        except RuntimeError:  # (a degenerate face: its point on face only)
            return list(zip(ev.getPointsAtParameters(ps)[1], ev.getNormalsAtParameters(ps)[1]))
        u0, v0, u1, v1 = r.minPoint.x, r.minPoint.y, r.maxPoint.x, r.maxPoint.y
        ps += [p for p in (adsk.core.Point2D.create(u0 + (u1 - u0) * (0.05 + 0.225 * i), v0 + (v1 - v0) * (0.05 + 0.225 * j))
                           for i in range(5) for j in range(5)) if ev.isParameterOnFace(p)]
        out = list(zip(ev.getPointsAtParameters(ps)[1], ev.getNormalsAtParameters(ps)[1]))
        # isParameterOnFace can pass points of a notched planar face that lie in its notch (round a boss, say):
        # keep a sample only if the body is solid just behind it and empty just in front of it
        IN_ = adsk.fusion.PointContainment.PointInsidePointContainment
        on = lambda p, n, e: f.body.pointContainment(adsk.core.Point3D.create(p.x + n.x * e, p.y + n.y * e, p.z + n.z * e))
        return [(p, n) for p, n in out if on(p, n, -0.002) == IN_ and on(p, n, 0.002) != IN_] or out[:1]

    def reach(body, p, n, dz):
        if n.z * dz < -1e-4:
            return False
        for e in (0.003, 0.01):  # 0.03 mm, then 0.1 mm off the face
            o = adsk.core.Point3D.create(p.x + n.x * e, p.y + n.y * e, p.z + n.z * e + dz * e)
            hits = c.findBRepUsingRay(o, adsk.core.Vector3D.create(0, 0, dz), adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 1e-5, True)
            if not any(h.body.name == body.name for h in hits):
                return True
        return False

    def pip(pt, ring):
        x, y, c_ = pt[0], pt[1], False
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c_ = not c_
        return c_
    lb_ = g["lower_band"]
    def band_face(f):  # a face of the rear-face recess: within its (x, z) field (+0.3) and <= 0.6 mm behind the lean plane
        p = f.pointOnFace
        x, y, z = p.x / MM, p.y / MM, p.z / MM
        for idx, side in ((0, "left"), (1, "right")):
            c0, N = lb_["crease"][idx], lb_["normals"][idx]
            d = N[0] * (x - c0[0]) + N[1] * (y - c0[1]) + N[2] * (z - c0[2])
            ring = g["band_recess"][side]
            near = pip((x, z), ring) or min(math.hypot(x - a, z - b) for a, b in ring) < 0.3
            if -0.6 <= d <= 0.05 and near:
                return True
        return False
    ok, report = {}, {}
    for name in ("Body", "Panel"):
        for b in c.bRepBodies:
            b.isLightBulbOn = b.name == name
        body, ext = B(name), B("Exterior") if name == "Body" else None
        count, bad = {}, []
        for k, f in enumerate(body.faces):
            S = samples(f)
            up = [reach(body, p, n, 1) for p, n in S]
            dn = [reach(body, p, n, -1) for p, n in S]
            rule = 0
            for (p, n), u_, d_ in zip(S, up, dn):
                q = adsk.core.Point3D.create(p.x + n.x * 0.005, p.y + n.y * 0.005, p.z + n.z * 0.005)
                if ext and ext.pointContainment(q) == adsk.fusion.PointContainment.PointInsidePointContainment:
                    cz = crease_z(p.x / MM, p.y / MM)
                    rule += (p.z / MM > cz + 0.05 and not u_) or (p.z / MM < cz - 0.05 and not d_)
            miss = sum(not (a or b_) for a, b_ in zip(up, dn))
            op = "both" if all(up) and all(dn) else "top" if all(up) else "bottom" if all(dn) else \
                "split" if not miss else "graze" if miss == 1 and len(S) >= 10 else "NONE"
            if op == "NONE":  # M6: a ray that only grazes a wall (the sample sits on the wall's line, e.g. a boss top
                # meeting it): every unreachable sample is reached once the ray starts 0.03 mm aside, out of the body
                IN0 = adsk.fusion.PointContainment.PointInsidePointContainment
                def nudged(p, n):
                    for dx, dy in ((0.003, 0), (-0.003, 0), (0, 0.003), (0, -0.003)):
                        q_ = adsk.core.Point3D.create(p.x + dx, p.y + dy, p.z)
                        if body.pointContainment(q_) != IN0 and (reach(body, q_, n, 1) or reach(body, q_, n, -1)):
                            return True
                    return False
                if all(nudged(p, n) for (p, n), a, b_ in zip(S, up, dn) if not (a or b_)):
                    op = "graze"
            if op == "NONE":  # M6: a hairline crevice (< 0.03 mm, where an island's R3 fillet runs tangent into the
                # wall): the point just off each unreachable sample is already inside the body, so no tool could
                # ever enter it; info, not a fail
                IN_ = adsk.fusion.PointContainment.PointInsidePointContainment
                off = lambda p, n: body.pointContainment(adsk.core.Point3D.create(p.x + n.x * 0.003, p.y + n.y * 0.003, p.z + n.z * 0.003))
                # (M6 tightened: <= 0.5 mm2, and a sliver must pass the same test: no area-only pass)
                if all(off(p, n) == IN_ for (p, n), a, b_ in zip(S, up, dn) if not (a or b_)) and f.area * 100 < 0.5:
                    op = "hairline"
            if op == "NONE" and name == "Panel" and band_face(f):  # M7: the rear-face recess: a side setup, not +-Z
                op = "side"
            count[op] = count.get(op, 0) + 1
            if op in ("NONE", "graze", "hairline", "side") or rule:
                at = [(round(p.x / MM, 2), round(p.y / MM, 2), round(p.z / MM, 2)) for (p, n), a, b_ in zip(S, up, dn) if not (a or b_)]
                bad.append((k, op, rule, round(f.area * 100, 3), at[:2]))
        ok[name] = not any(q[1] == "NONE" or q[2] for q in bad)
        report[name] = (count, bad)
        log(f"CHECK undercuts, {name}: {body.faces.count} faces, by op {count}; unreachable / crease-rule faces "
            f"{[q for q in bad if q[1] == 'NONE' or q[2]]} -> {'PASS' if ok[name] else 'FAIL'}")
        for q in bad:
            if q[1] == "side":
                log(f"  info: {name} face {q[0]} ({q[3]} mm2): rear-face recess, needs the side setup (panel on edge / angle plate)")
            if q[1] in ("graze", "hairline"):
                log(f"  info: {name} face {q[0]} ({q[3]} mm2): " + ("rays graze a neighbour (reached 0.03 mm aside)" if q[1] == "graze"
                    else "hairline crevice side (< 0.03 mm wide, < 0.5 mm2)") + f" at {q[4]}")
    for b in c.bRepBodies:
        b.isLightBulbOn = b.name in ("Body", "Panel")
    return ok


def run(_context):
    try:
        _run(_context)
    except Exception:  # M6: the MCP call times out long before a build ends; leave the reason in the log
        import traceback
        log("BUILD ERROR " + traceback.format_exc())
        raise


def _run(_context):
    t0 = time.time()
    app = adsk.core.Application.get()
    g = json.load(open(JSON))
    # v2: a NEW document, named DOC_NAME (v1, "Alice Case", is never touched). INTO_ACTIVE (a rebuild) builds into the active
    # document only if it is called DOC_NAME and its timeline is empty
    if globals().get("INTO_ACTIVE"):
        doc = app.activeDocument
        if doc.name != DOC_NAME or adsk.fusion.Design.cast(app.activeProduct).timeline.count:
            raise RuntimeError(f"INTO_ACTIVE: the active document is {doc.name!r} with a non-empty timeline, not an empty {DOC_NAME!r}")
    else:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        try:
            doc.saveAs(DOC_NAME, app.data.activeProject.rootFolder, "v2 build (case/fusion_build.py)", "")
        except Exception as e:  # (a new, empty document does not save from the API: save it by hand under that name)
            log(f"note: document not saved as {DOC_NAME!r} yet ({str(e)[:80]}); File > Save it under that name")
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    log(f"--- build {time.ctime()} from {JSON} (web_mode {g['params']['web_mode']})")
    add_params(design, g["params"])
    halves = {h: build_half(root, g, h) for h in ("left", "right")}
    udb = build_udb(root, g)
    build_tpu_clip(root, g)
    log(f"M2 parts built in {time.time() - t0:.1f} s")
    check_m2(design, g, halves, udb)
    case = build_case(root, g)
    log(f"M3 case built in {time.time() - t0:.1f} s")
    if globals().get("NO_CHECKS"):  # M6: build only; the checks run as their own script calls (a script that dies
        # mid-way is rolled back whole by Fusion, model included)
        for b in case.component.bRepBodies:
            b.isLightBulbOn = b.name in ("Body", "Panel")
        app.activeViewport.fit()
        log(f"built (checks skipped) in {time.time() - t0:.1f} s")
        return
    check_m3(design, g, halves, udb, case)
    log(f"M3 checks done in {time.time() - t0:.1f} s")
    check_m4(g, case)
    log(f"M4 checks done in {time.time() - t0:.1f} s")
    check_m5(g, case)
    log(f"M5 checks done in {time.time() - t0:.1f} s")
    for b in case.component.bRepBodies:
        b.isLightBulbOn = b.name in ("Body", "Panel")
    app.activeViewport.fit()
    step = import_udb_step(udb)
    if step:  # the real board against the slot roof and bay (the box placeholder is checked in check_m3)
        ents = adsk.core.ObjectCollection.create()
        ents.add(step)
        for n in ("Body", "Panel"):
            ents.add(case.component.bRepBodies.itemByName(n).createForAssemblyContext(case))
        inp = design.createInterferenceInput(ents)
        inp.areCoincidentFacesIncluded = False
        res = design.analyzeInterference(inp)
        hits = [(r.entityOne.name, r.entityTwo.name, round(r.interferenceBody.volume * 1000, 3))
                for r in (res.item(i) for i in range(res.count))]
        hits = [h for h in hits if {"Body", "Panel"} & {h[0], h[1]}]
        log(f"CHECK UDB STEP model vs Body + Panel: {len(hits)} pair(s) {hits[:10]} -> {'PASS' if not hits else 'FAIL'}")
    log(f"done in {time.time() - t0:.1f} s")
