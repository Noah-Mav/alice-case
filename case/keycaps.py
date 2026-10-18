"""Alice case M8: Cherry-profile keycaps and render appearances. Runs inside Fusion on the open "Alice Case"
(MCP execute, featureType "script", this file's text, or exec'd from disk like fusion_checks.py).

Set STEP before running (separate calls, each well under the MCP's ~60 s):
    STEP = "caps"    rebuild the root "Keycaps" component (deletes an old one first), hide the envelope placeholders
    STEP = "finish"  apply the appearances to the case, panel, feet, plates and PCBs

Geometry comes from case/out/case_geometry.json (key centres, angles and widths in each half's local frame,
plate top at w = 0); rows come from ~/Documents/layout2.json (row key counts per half, in order).
Cap model (Cherry profile, GMK row numbering: R1 number row .. R4 bottom row), all from KeyV2 cherry.scad: base
18.16 deep, (u * 19.05 - 0.89) wide; top 14.64 deep, base width - 6.31 wide (1u: 11.85), set TOP_SKEW back;
cylindrical dish (axis front-to-back) DISH mm deep at the centre; height and top tilt per row from ROWS. Caps are
solid (no stem or hollow): render only.
M7 heights (skirt bottom to the top edge) and dish: KeyV2's GMK-based Cherry profile (rsheldiii/KeyV2,
src/key_profiles/cherry.scad: total_depth 9.8 / 7.45 / 6.55 / 7.35 with Cherry's 0.6 mm stem inset, dish 0.65).
Seat: an MX stem top is 15.2 above the PCB (Deskthority, Cherry MX), i.e. 10.2 above the plate top; the cross is
~3.6-3.7 tall and the cap's sleeve rests on the slider at its foot (6.6, flush with the housing top), the sleeve
inset 0.6 above the skirt: skirt 6.0 above the plate at rest, 2.0 bottomed out (4.0 travel).
"""
import json
import math
import os

import adsk.core
import adsk.fusion

CASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    os.path.expanduser("~/Documents/Development/alice-case/case")
JSON = os.path.join(CASE, "out", "case_geometry.json")
LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "layouts", "layout2.json")
MM = 0.1
U = 19.05
BASE_D, TOP_D, TOP_SHRINK, BASE_GAP, TOP_SKEW = 18.16, 14.64, 6.31, 0.89, 2.0
R_BASE, R_TOP, DISH = 0.6, 1.5, 0.65
# height (skirt to top edge, mm), top tilt (+ = top faces the user): KeyV2 total_depth and $top_tilt (its positive
# tilt turns the top toward the back, hence the minus); R1 is unused on a 40%
ROWS = {"R1": (9.8, -0.0), "R2": (7.45, -2.5), "R3": (6.55, -5.0), "R4": (7.35, -11.5)}
ROW_OF = ["R2", "R3", "R4", "R4"]  # layout rows in the file's order: top letters, home, bottom, thumbs
TRAVEL = 4.0  # MX total travel (Cherry MX2A datasheet; pre-travel 2.0)
MODS = {"tab", "ctrl", "shift", "code", "fn", "bksp", "lower", "raise", "alt", "caps", "esc", "gui", "win", "del"}
COLOURS = {"alpha": ("Keycap cream", (204, 199, 186)), "mod": ("Keycap charcoal", (62, 60, 60)),
           "accent": ("Keycap maroon", (98, 26, 34))}


def kind(k):
    lab = k["label"].strip().lower()
    if lab == "enter":
        return "accent"
    if lab in MODS or (not lab and k["w"] < 2):  # blank bottom-row 1u / 1.25u are modifiers, a blank >= 2u is space
        return "mod"
    return "alpha"


def appearance(design, name, base, rgb=None):
    """A copy of library appearance `base` (recoloured to rgb if given), made once per design."""
    a = design.appearances.itemByName(name)
    if not a:
        lib = adsk.core.Application.get().materialLibraries.itemByName("Fusion Appearance Library")
        a = design.appearances.addByCopy(lib.appearances.itemByName(base), name)
    if rgb:
        for i in range(a.appearanceProperties.count):
            p = a.appearanceProperties.item(i)
            if isinstance(p, adsk.core.ColorProperty) and p.value:
                p.value = adsk.core.Color.create(*rgb, 255)
    return a


def P(x, y, z):
    return adsk.core.Point3D.create(x * MM, y * MM, z * MM)


def rounded_rect(sk, c, ex, ey, a, b, r):
    """Rounded rectangle centred at model point c (mm), half sizes a, b along unit vectors ex, ey."""
    m = lambda x, y: sk.modelToSketchSpace(P(*(c[i] + x * ex[i] + y * ey[i] for i in range(3))))
    q = r * (1 - 1 / math.sqrt(2))
    arcs = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):  # counter-clockwise corners
        p0 = (sx * a, sy * (b - r)) if sx * sy > 0 else (sx * (a - r), sy * b)
        p1 = (sx * (a - r), sy * b) if sx * sy > 0 else (sx * a, sy * (b - r))
        arcs.append(sk.sketchCurves.sketchArcs.addByThreePoints(m(*p0), m(sx * (a - q), sy * (b - q)), m(*p1)))
    lines = sk.sketchCurves.sketchLines
    for i in range(4):
        e0, e1 = arcs[i], arcs[(i + 1) % 4]
        # the arc's end nearest the next arc joins a line to that arc's nearest end
        pa = min((e0.startSketchPoint, e0.endSketchPoint),
                 key=lambda p: min(p.geometry.distanceTo(e1.startSketchPoint.geometry), p.geometry.distanceTo(e1.endSketchPoint.geometry)))
        pb = min((e1.startSketchPoint, e1.endSketchPoint), key=lambda p: p.geometry.distanceTo(pa.geometry))
        lines.addByTwoPoints(pa, pb)
    return sk.profiles.item(0)


def template(comp, tbm, row, w):
    """One cap (row, width u) as a temporary B-rep, skirt centre at the origin, +z up, +y to the back."""
    h, tilt = ROWS[row]
    wb = w * U - BASE_GAP
    planes = comp.constructionPlanes
    sk0 = comp.sketches.add(comp.xYConstructionPlane)
    p0 = rounded_rect(sk0, (0, 0, 0), (1, 0, 0), (0, 1, 0), wb / 2, BASE_D / 2, R_BASE)
    pi = planes.createInput()
    pi.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(h * MM))
    off = planes.add(pi)
    sk1 = comp.sketches.add(off)
    axis = sk1.sketchCurves.sketchLines.addByTwoPoints(sk1.modelToSketchSpace(P(-20, 0, h)), sk1.modelToSketchSpace(P(20, 0, h)))
    t = math.radians(tilt)
    n_want = (0, -math.sin(t), math.cos(t))
    for sgn in (1, -1):
        pi = planes.createInput()
        pi.setByAngle(axis, adsk.core.ValueInput.createByReal(sgn * t), off)
        top = planes.add(pi)
        n = top.geometry.normal
        if abs(n.y * n_want[1] + n.z * n_want[2]) > 0.9999:
            break
        top.deleteMe()
    ey = (0, math.cos(t), math.sin(t))
    sk2 = comp.sketches.add(top)
    tc = (0, TOP_SKEW * ey[1], h + TOP_SKEW * ey[2])  # the top's centre, TOP_SKEW back along the top
    p1 = rounded_rect(sk2, tc, (1, 0, 0), ey, (wb - TOP_SHRINK) / 2, TOP_D / 2, R_TOP)
    lofts = comp.features.loftFeatures
    li = lofts.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    li.loftSections.add(p0)
    li.loftSections.add(p1)
    body = tbm.copy(lofts.add(li).bodies.item(0))
    # dish: a cylinder along the top's front-to-back direction, DISH deep at the centre, flush at the top's sides
    c = (wb - TOP_SHRINK) / 2
    R = (c * c + DISH * DISH) / (2 * DISH)
    ax = [n_want[i] * (R - DISH) + tc[i] for i in range(3)]
    cyl = tbm.createCylinderOrCone(P(*(ax[i] - 20 * ey[i] for i in range(3))), R * MM,
                                   P(*(ax[i] + 20 * ey[i] for i in range(3))), R * MM)
    tbm.booleanOperation(body, cyl, adsk.fusion.BooleanTypes.DifferenceBooleanType)
    return body


def mat(m):
    M = adsk.core.Matrix3D.create()
    M.setWithArray([m[r][c] * (MM if c == 3 and r < 3 else 1) for r in range(4) for c in range(4)])
    return M


def caps(design):
    g, lay = json.load(open(JSON)), json.load(open(LAYOUT))
    root, tbm = design.rootComponent, adsk.fusion.TemporaryBRepManager.get()
    old = root.occurrences.itemByName("Keycaps:1")
    if old:
        old.deleteMe()
    tmp = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    tmp.component.name = "KeycapTemplates"
    plan, cache = [], {}
    for h in ("left", "right"):
        d = g["halves"][h]
        rows = [ROW_OF[i] for i, r in enumerate(lay[h]) for _ in r["keys"]]
        assert len(rows) == len(d["keys"]), (h, len(rows), len(d["keys"]))
        for k, row in zip(d["keys"], rows):
            if (row, k["w"]) not in cache:
                cache[row, k["w"]] = template(tmp.component, tbm, row, k["w"])
            a = math.radians(k["ang"])
            rest = g["params"]["skirt_bottom_out"] + TRAVEL  # skirt above the plate top at rest
            K = [[math.cos(a), -math.sin(a), 0, k["x"]], [math.sin(a), math.cos(a), 0, k["y"]], [0, 0, 1, rest], [0, 0, 0, 1]]
            Mh = d["matrix"]
            M = [[sum(Mh[r][i] * K[i][c] for i in range(4)) for c in range(4)] for r in range(4)]
            plan.append((h, k, row, M))
    tmp.deleteMe()
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    c = occ.component
    c.name = "Keycaps"
    bf = c.features.baseFeatures.add()
    bf.startEdit()
    out = []
    for i, (h, k, row, M) in enumerate(plan):
        b = tbm.copy(cache[row, k["w"]])
        tbm.transform(b, mat(M))
        out.append((c.bRepBodies.add(b, bf), h, k, row))
    bf.finishEdit()
    bf.name = "Keycaps"
    looks = {kk: appearance(design, n, "Plastic - Matte (White)", rgb) for kk, (n, rgb) in COLOURS.items()}
    for j, (_, h, k, row) in enumerate(out):
        b = c.bRepBodies.item(j)  # bodies after finishEdit
        b.name = f"{h[0].upper()}_{row}_{k['label'] or 'blank'}_{k['w']}u".replace(" ", "")
        b.appearance = looks[kind(k)]
    for n in ("Left:1", "Right:1"):  # the bottomed-out envelopes stay in the model (checks use them), hidden
        half = root.occurrences.itemByName(n)
        half.isLightBulbOn = True
        for o in half.childOccurrences:
            o.isLightBulbOn = not o.component.name.startswith(("Keycaps", "Snaps"))
    print(f"caps: {c.bRepBodies.count} bodies, {len(cache)} templates {sorted(cache)}")
    print({kk: sum(1 for b, h, k, r in out if kind(k) == kk) for kk in COLOURS})


def finish(design):
    root = design.rootComponent
    case = root.occurrences.itemByName("Case:1").component
    wood = appearance(design, "Walnut", "Walnut")
    tex = wood.appearanceProperties.itemById("opaque_albedo").connectedTexture.properties
    tex.itemById("texture_WAngle").value = 90.0  # the bitmap's grain runs along V: turn it to run along X
    tex.itemById("unifiedbitmap_RGBAmount").value = 1.3  # a lighter, oiled look
    tex.itemById("texture_RealWorldScaleX").value = 9.0  # half the library tile (18 x 36): finer grain
    tex.itemById("texture_RealWorldScaleY").value = 18.0
    body = case.bRepBodies.itemByName("Body")
    body.appearance = wood
    adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl).projectedTextureMapType = \
        adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection  # planar smears the walls
    case.bRepBodies.itemByName("Panel").appearance = appearance(
        design, "Anodized dark grey", "Aluminum - Anodized Rough (Grey)", (48, 50, 54))
    rubber = appearance(design, "Rubber black", "Rubber - Soft", (18, 18, 18))
    for b in case.bRepBodies:
        if b.name.startswith("Foot"):
            b.appearance = rubber
    plate = appearance(design, "Aluminum - Satin", "Aluminum - Satin")
    pcb = appearance(design, "PCB black", "Plastic - Matte (Black)")
    sw = appearance(design, "Switch housing", "Plastic - Matte (Black)", (30, 30, 32))
    for n in ("Left:1", "Right:1"):
        for o in root.occurrences.itemByName(n).childOccurrences:
            nm = o.component.name
            look = plate if nm.startswith("Plate") else pcb if nm.startswith("Pcb") else sw if nm.startswith("Switches") else None
            for b in o.component.bRepBodies if look else []:
                b.appearance = look
    print("finish: appearances set")


def run(_context):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    step = globals().get("STEP", "caps")
    {"caps": caps, "finish": finish}[step](design)
