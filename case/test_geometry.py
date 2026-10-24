"""Checks M1 of docs/fusion-case-plan.md. Run: case/.venv/bin/python case/test_geometry.py [LAYOUT.json]"""
import math
from pathlib import Path
import sys

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import geometry as G
import alice
from alice import corners, footprint, solid

lay = G.load(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "layouts" / "layout2.json"))
g = G.build(lay)
P, s, Ms = G.P, g["_shapes"], {h: np.array(d["matrix"]) for h, d in g["halves"].items()}
L_ = g["layers"]
placed = G.alice.place(lay)

# Refuses to build a layout with overlapping keys.
real = G.alice.collisions
G.alice.collisions = lambda placed: [("A", "B", 0.5)]
try:
    G.build(lay)
    raise AssertionError("built despite collisions")
except SystemExit:
    pass
finally:
    G.alice.collisions = real

# The ridge lies between the halves, and both plate planes meet on it.
# v2 (user): it is the midpoint of the two R2 (anchor) rows' extents, so both rows sit equally either side of it.
sp = P["half_spread"]
xs = {h: [p[0] + (-sp[0] if h == "left" else sp[1]) for o in solid(placed) if o["half"] == h for p in footprint(o)]
      for h in ("left", "right")}
r2 = {h: [p[0] + (-sp[0] if h == "left" else sp[1]) for o in solid(placed) if o["half"] == h and o["rname"].startswith("Anchor")
          for p in footprint(o)] for h in ("left", "right")}
assert abs((min(r2["left"]) + max(r2["right"])) / 2 - g["ridge_x"]) < 1e-9
assert abs((g["ridge_x"] - max(r2["left"])) - (min(r2["right"]) - g["ridge_x"])) < 1e-9  # the rows' inner ends: equidistant
assert abs((g["ridge_x"] - min(r2["left"])) - (max(r2["right"]) - g["ridge_x"])) < 1e-9  # and their outer ends
assert max(xs["left"]) + 2 <= g["ridge_x"] <= min(xs["right"]) - 2  # >= 2 mm to both halves' keys
for Y in (0.0, 50.0, 100.0):
    for w in (0.0, P["lip"], G.FLOOR_W):
        assert abs(G.z_at(Ms["left"], w, g["ridge_x"], Y) - G.z_at(Ms["right"], w, g["ridge_x"], Y)) < 1e-6

# M6: the bezel top is the plate top + lip along the normal everywhere over each plate (4 corners and centre): the
# case top there is the half's own facet, not the other half's
for h, d in g["halves"].items():
    M = Ms[h]
    u0, v0, u1, v1 = d["plate"].bounds
    for u_, v_ in ((u0, v0), (u1, v0), (u0, v1), (u1, v1), ((u0 + u1) / 2, (v0 + v1) / 2)):
        X, Y, Z = (M @ [u_, v_, P["lip"], 1])[:3]
        assert abs(G.surface(Ms.values(), P["lip"], X, Y) - Z) < 0.05 * M[2, 2], (h, u_, v_)

# Crease (M6 crease_mode): "front_horizontal" puts the crease of both front faces at one height (the outer front
# corners' mean crease height); the back vertices keep the deepening rule. "deepening": crease_depth on the front.
lb_ = g["lower_band"]
front_z = [c[2] for c in lb_["crease"][3:]]  # ring: lt, back mid, rt, then rb .. V .. lb (the front faces)
hf = (g["heights"]["front_left"] + g["heights"]["front_right"]) / 2
if P["crease_mode"] == "front_horizontal":
    assert max(front_z) - min(front_z) < 1e-9 and abs(front_z[0] - (hf - P["crease_depth"])) < 1e-9, front_z
else:
    assert min(lb_["depth"]) == P["crease_depth"]
assert abs(lb_["depth"][0] - g["heights"]["back_centre"] * (1 - P["lower_back"])) < 1e-9  # the back: unchanged rule

# The transforms are orthonormal rotations; the steepest slope is acos(cos typing * cos tent) (8.1° at 7 + 4,
# 8.6° at the plan's 7 + 5).
for M in Ms.values():
    R = M[:3, :3]
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-9) and abs(np.linalg.det(R) - 1) < 1e-9
    steep = math.degrees(math.acos(math.cos(math.radians(P["typing_angle"])) * math.cos(math.radians(P["tent"]))))
    assert abs(math.degrees(math.acos(R[2, 2])) - steep) < 1e-6

# §6.2: the opening holds every envelope with >= 1.5 mm along its edges and >= 0.85 mm at its corners.
opening, edge = s["opening"], s["opening"].boundary
assert len(s["envelopes"]) == len(G.alice.keycaps(placed))
for e in s["envelopes"]:
    assert opening.contains(e)
    ring = e.exterior.coords
    assert all(edge.distance(Point(p)) >= 0.85 for p in ring)
    for a, b in zip(ring, ring[1:]):
        n = max(int(math.dist(a, b)), 1)
        pts = [np.add(a, np.subtract(b, a) * t / n) for t in range(n + 1)]
        assert all(edge.distance(Point(p)) >= 1.5 - 1e-6 for p in pts
                   if min(math.dist(p, c) for c in ring) >= 1.5)

def world(M, w, poly):  # local (u, v) on the plane w -> world plan
    return affinity.affine_transform(poly, [M[0, 0], M[0, 1], M[1, 0], M[1, 1], M[0, 2] * w + M[0, 3], M[1, 2] * w + M[1, 3]])


# §6.6: each plate and PCB outline holds every switch body, each PCB every hotswap socket; both stay on their side.
for h, d in g["halves"].items():
    for k in d["keys"]:
        body = Polygon(corners(k["x"], k["y"], P["switch_body"], P["switch_body"], k["ang"]))  # y up: ccw
        assert d["pcb"].contains(body) and d["plate"].contains(body), (h, k["label"])
        x0, y0, x1, y1 = G.SOCKET  # key-local, y toward the user -> local v is flipped
        a = math.radians(k["ang"])
        sock = Polygon([(k["x"] + x * math.cos(a) + y * math.sin(a), k["y"] + x * math.sin(a) - y * math.cos(a))
                        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])
        assert d["pcb"].contains(sock), (h, k["label"])
    # the gaps hold at both faces in plan, despite the tilt (each outline is inset at its own mid-height)
    # (v2: the PCB and plate are frozen from v1, the pocket grew round them: the wall keeps v1's 0.80 / 0.906 at least)
    for poly, w0, w1, gap in ((d["plate"], -P["plate_t"], 0.0, P["plate_wall_min"]),
                              (d["pcb"], G.PCB_MID_W - P["pcb_t"] / 2, G.PCB_MID_W + P["pcb_t"] / 2, P["pcb_wall_min"])):
        for w in (w0, w1):
            pw = world(Ms[h], w, poly)
            assert opening.contains(pw) and min(edge.distance(Point(q)) for q in pw.exterior.coords) >= gap - 2e-3, (h, w)
    xw = [(Ms[h] @ [u, v, G.PCB_MID_W, 1])[0] for u, v in d["pcb"].exterior.coords]
    assert (max(xw) <= g["ridge_x"] - P["ridge_clear"] + 1e-6) if h == "left" else (min(xw) >= g["ridge_x"] + P["ridge_clear"] - 1e-6)


# v2 (user): the same dummy PCB and plate as v1. Their outlines (and so the holes, which hang on the keys) are v1's, moved
# along u with the keys: identical to case/frozen_v1.json, and to the v1 checkpoint JSON where it is present.
v1_ck = Path(__file__).resolve().parent / "checkpoints" / "v1" / "case_geometry.json"
v1_json = G.json.loads(v1_ck.read_text()) if v1_ck.exists() else None
for h, d in g["halves"].items():
    du_h = d["keys"][0]["x"] - G.FROZEN[h]["keys"][0][0]
    for nm_ in ("pcb", "plate"):
        for src_, pts_ in (("frozen_v1.json", G.FROZEN[h][nm_]), ("v1 checkpoint", v1_json["halves"][h][nm_] if v1_json else None)):
            if pts_ is None:
                continue
            want = affinity.translate(Polygon(pts_), du_h, 0)
            assert d[nm_].equals_exact(want, 1e-9), (h, nm_, src_)  # same vertices, same outline
            assert abs(d[nm_].area - Polygon(pts_).area) < 1e-6
    # every key keeps its place on the frozen PCB (same relative positions, angles, widths as v1)
    for k, k1 in zip(d["keys"], G.FROZEN[h]["keys"]):
        assert abs(k["x"] - du_h - k1[0]) < 2e-3 and abs(k["y"] - k1[1]) < 2e-3 and abs(k["ang"] - k1[2]) < 2e-3, (h, k["label"])
    assert len(d["keys"]) == len(G.FROZEN[h]["keys"])
    if v1_json:  # the JST header, plug pocket and stab cutouts are those of v1 too
        v1h = v1_json["halves"][h]
        assert affinity.translate(Polygon(v1h["jst"]), du_h, 0).symmetric_difference(d["jst"]).area < 1e-6
        assert affinity.translate(Polygon(v1h["jst_pocket"]), du_h, 0).symmetric_difference(d["jst_pocket"]).area < 1e-6
        assert len(v1h["stabs"]) == len(d["stabs"]) and all(
            affinity.translate(Polygon(a_), du_h, 0).symmetric_difference(b_).area < 0.02 for a_, b_ in zip(v1h["stabs"], d["stabs"]))
assert P["pcb_t"] == 1.6 and P["plate_t"] == 1.5 and P["plate_to_pcb"] == 5.0 and P["floor_air"] == 3.5 and P["cutout"] == 14.0


def radius_ok(poly, r, skip=None, tol=0.05):
    """Every vertex is reachable by a disc of radius r inside poly, i.e. no convex corner is tighter than r."""
    core = poly.buffer(-r)
    return all(core.distance(Point(p)) <= r + tol for q in getattr(poly, "geoms", [poly])
               for ring in (q.exterior, *q.interiors) for p in ring.coords
               if skip is None or skip.distance(Point(p)) > 0.01)


assert not radius_ok(box(0, 0, 50, 50), 3)  # the check catches a sharp corner
# Internal corners: top pocket >= pocket_r, rabbets >= pocket_r (except where they run out the rear face),
# bottom cavity >= cavity_r; §7's R0.5 on the material corners left between keys.
assert radius_ok(opening, P["pocket_r"])
assert radius_ok(s["cavity"], P["cavity_r"])
for rab in s["rabbet"].values():
    assert radius_ok(rab, P["pocket_r"], skip=s["footprint"].exterior)
assert radius_ok(s["outline"].difference(opening), 0.5)  # §7
assert s["outline"].contains(opening) and s["footprint"].buffer(1e-6).contains(s["panel"]) and s["panel"].contains(s["cavity"])


# H_front: the smallest lift (0.5 mm steps) that puts the pocket floor >= panel_t + 3 above the desk everywhere.
def floor_z(lift, X, Y):  # straight from each floor plane's point and normal, independent of geometry.z_at
    zs = []
    for sgn in (1, -1):
        M = G.matrix(sgn, g["ridge_x"], lift)
        p0, n = M @ [0, 0, G.FLOOR_W, 1], M[:3, 2]
        zs.append(p0[2] - (n[0] * (X - p0[0]) + n[1] * (Y - p0[1])) / n[2])
    return min(zs)


need = P["base_min"]  # M7: solid front base (over the panel the floor rule is checked below)
verts = [p for q in getattr(opening, "geoms", [opening]) for p in q.exterior.coords]
low = lambda lift: min(floor_z(lift, x, y) for x, y in verts)
assert abs(g["lift"] / P["lift_step"] - round(g["lift"] / P["lift_step"])) < 1e-9
assert low(g["lift"]) >= need and low(g["lift"] - P["lift_step"]) < need
assert abs(low(g["lift"]) - g["floor_min_z"]) < 1e-9
# M7: over the (rear) panel the floor keeps panel_t + floor_above_panel; in front of it the body is solid to the desk
ov = opening.intersection(s["panel"].buffer(P["panel_gap_print"]))
assert min(floor_z(g["lift"], x, y) for q in getattr(ov, "geoms", [ov]) for x, y in q.exterior.coords) >= \
    P["panel_t"] + P["floor_above_panel"]
# M7: real bottomed-out Cherry caps (tapered, skirt_bottom_out .. lip) keep the artisan gap to the opening (M6 envelope)
assert g["cap_gap"] >= P["artisan_gap"], g["cap_gap"]


# M2 parts. Plate cutouts (switch + §4 stab: 2 per key >= 2u) sit inside the plate with a web between them.
for h, d in g["halves"].items():
    big = [k for k in d["keys"] if k["w"] >= P["stab"]["min_w"]]
    assert len(d["stabs"]) == 2 * len(big) and len(d["cutouts"]) == len(d["switches"]) == len(d["keys"])
    holes = d["cutouts"] + d["stabs"]
    assert all(d["plate"].contains(c) for c in holes)
    assert min(a.distance(b) for i, a in enumerate(holes) for b in holes[i + 1:]) >= 1.0, h
    for k in big:  # stab rectangles: 6.75 x 14, at +-11.938 across the key, +6 .. -8 along it (+ = back)
        a = math.radians(k["ang"])
        for sx in (-1, 1):
            c = np.add([k["x"], k["y"]], [sx * 11.938 * math.cos(a) + math.sin(a), sx * 11.938 * math.sin(a) - math.cos(a)])
            assert min(Point(c).distance(st.centroid) for st in d["stabs"]) < 1e-6
    assert all(abs(st.area - 6.75 * 14) < 1e-6 for st in d["stabs"])

    # §6.10 JST header with its 8 x 6 plug pocket: on the PCB, clear of sockets and centre posts, inner back area.
    keep = unary_union(d["sockets"] + [Point(k["x"], k["y"]).buffer(2.0) for k in d["keys"]])
    assert d["jst_pocket"].within(d["pcb"]) and not d["jst_pocket"].intersects(keep)
    assert d["jst"].within(d["jst_pocket"]) and abs(d["jst"].area - 6.0 * 4.2) < 1e-6
    minu, minv, maxu, maxv = d["pcb"].bounds
    jc = d["jst"].centroid
    assert (jc.x > (minu + maxu) / 2) == (h == "left") and jc.y > (minv + maxv) / 2, h

    # v2 (user): 5 TPU C-clips per half on the PCB edge, no snaps / pillars. The ledge under the PCB (len 10 x 2.5) clears the
    # real hotswap sockets, stabs and the JST pocket by clip_clear; the clip stands in the PCB-to-wall gap and fits its
    # recess (10.4 long, 3.8 across at the nominal gap, R1.5, 0.5 deep, wall side on the wall: no undercut, a 45 deg lead-in
    # chamfer); the floor plane under it is >= clip_floor_min above the desk (local exception to base_min).
    assert len(d["clips"]) == 5 == len(P["clip_pts"][h])
    ext = d["pcb"].exterior
    L_c, W_c, D_c = P["clip_recess"]
    cl = P["clip"]
    real_socks = unary_union([Polygon([(k["x"] + x * math.cos(math.radians(k["ang"])) - y * math.sin(math.radians(k["ang"])),
                                        k["y"] + x * math.sin(math.radians(k["ang"])) + y * math.cos(math.radians(k["ang"])))
                                       for x, y in G.SOCKET_REAL]) for k in d["keys"]])
    o_h = [o for o in opening.geoms if (o.centroid.x < g["ridge_x"]) == (h == "left")][0]
    o_at = lambda w_: G.to_local(Ms[h], w_, o_h)  # the vertical wall seen in the plane w (the PCB frame)
    o_loc = o_at(G.FLOOR_W)
    w_bot = G.FLOOR_W - D_c
    w_pcb = G.FLOOR_W + (P["floor_air"])  # the PCB underside
    for q, (px, py) in zip(d["clips"], P["clip_pts"][h]):
        c = Point(q["edge_pt"])
        t, n = np.array(q["t"]), np.array(q["n"])
        assert ext.distance(c) < 1e-6 and abs(q["slide"]) <= P["clip_slide"] + 1e-9
        du_h = d["keys"][0]["x"] - G.FROZEN[h]["keys"][0][0]  # the given v1 point, moved with the keys
        assert Point(px + du_h, py).distance(c) <= P["clip_slide"] + 0.5
        assert not d["pcb"].contains(Point(*(np.array(q["edge_pt"]) + n * 0.5))) and d["pcb"].contains(Point(*(np.array(q["edge_pt"]) - n * 0.5)))
        fr = lambda a, b_: Point(*(np.array(q["edge_pt"]) + t * a + n * b_))
        ledge = Polygon([fr(a, b_) for a, b_ in ((-cl["len"] / 2, -cl["under"]), (cl["len"] / 2, -cl["under"]), (cl["len"] / 2, 0), (-cl["len"] / 2, 0))])
        assert ledge.distance(real_socks) >= P["clip_clear"] - 1e-6 and ledge.distance(unary_union(d["stabs"])) >= P["clip_clear"] - 1e-6
        assert ledge.distance(d["jst_pocket"]) >= P["clip_clear"] - 1e-6
        # the lip (1.5 over the PCB top, 0.9 above it, under the plate): clear of the switch bodies in the plate cutouts
        lip = Polygon([fr(a, b_) for a, b_ in ((-cl["len"] / 2, -cl["lip_overlap"]), (cl["len"] / 2, -cl["lip_overlap"]), (cl["len"] / 2, 0), (-cl["len"] / 2, 0))])
        assert lip.distance(unary_union(d["cutouts"])) >= 0.5, (h, q["name"])  # (the switch bodies below the plate fill the 14 mm cutouts)
        assert q["edge_dev"] <= 0.25, q["edge_dev"]  # a straight box on the tangent: the edge is straight to 0.25 along it
        # the recess: inside the pocket at the floor plane (wall side on the wall), 10.4 long, its inner side 3.8 - gap in
        rec_, mo_ = q["recess"], q["mouth"]
        assert rec_.geom_type == "Polygon" and o_loc.buffer(1e-3).contains(rec_) and o_loc.buffer(1e-3).contains(mo_)
        loc = [((np.array(p_) - np.array(q["edge_pt"])) @ t, (np.array(p_) - np.array(q["edge_pt"])) @ n) for p_ in rec_.exterior.coords]
        assert abs(max(a for a, _ in loc) - L_c / 2) < 0.15 and abs(min(a for a, _ in loc) + L_c / 2) < 0.15, q["name"]  # 10.4 long
        assert abs(min(b_ for _, b_ in loc) + (W_c - P["snap_gap"])) < 0.05, q["name"]  # 3.8 across at the nominal 0.9 gap
        assert abs(max(b_ for _, b_ in loc) - q["wall_gap"]) < 0.1, q["name"]  # the wall side is the wall
        assert 0.7 * L_c * W_c < rec_.area and mo_.area > rec_.area
        # the PCB-to-wall gap at the clip over its tilted thickness (the PCB underside .. top) is >= pcb_wall_min; the spine
        # (0.9 at mid-PCB) fills it: the wall offset at the slot mid is 0.9 +- 0.1 at the clips on the long edges
        wn = dict(q["wall_n"])
        for w_ in (w_pcb, w_pcb + P["pcb_t"]):
            hit = LineString([Point(q["edge_pt"]), Point(*(np.array(q["edge_pt"]) + n * 4.0))]).intersection(o_at(w_).exterior)
            assert min(Point(q["edge_pt"]).distance(p_) for p_ in getattr(hit, "geoms", [hit])) >= P["pcb_wall_min"] - 2e-3, (h, q["name"], w_)
        # the clip: profile in (x out from the PCB edge, w), extruded cl["len"] along the edge. Spine on the wall less wall_air;
        # the whole body inside the recess at its bottom (rounded R1.2 where its corners meet the R1.5 ones: checked below),
        # the slot 1.5 high over the PCB, the lip, the lead-in 30 deg
        prof = q["profile"]
        xs_p, ws_p = [a for a, _ in prof], [b_ for _, b_ in prof]
        slot_lo, slot_hi = G.FLOOR_W + P["floor_air"], G.FLOOR_W + P["floor_air"] + cl["slot"]
        assert abs(min(ws_p) - w_bot) < 1e-9 and abs(min(xs_p) + cl["under"]) < 1e-9
        assert abs(max(ws_p) - (slot_hi + cl["lip"])) < 1e-6 and abs(max(ws_p) - w_bot - (D_c + P["floor_air"] + cl["slot"] + cl["lip"])) < 1e-6
        assert abs(max(ws_p) - w_bot - 6.5) < 1e-6  # total height (the 6.6 spec: the PCB top is 0.1 over the slot's roof)
        body_bot = Polygon([fr(-cl["len"] / 2, -cl["under"]), fr(cl["len"] / 2, -cl["under"]), fr(cl["len"] / 2, max(xs_p[1], 0.01)),
                            fr(-cl["len"] / 2, max(xs_p[1], 0.01))]).buffer(-1.2, quad_segs=16).buffer(1.2, quad_segs=16)
        assert rec_.buffer(1e-6).contains(body_bot), (h, q["name"])  # recess-fit: the clip's bottom in its recess
        # fit clearance: the clip's plan (the recess outline less `fit`, then trimmed by the profile's ledge side and spine) lies in
        # the recess's own outline (rx_: 10.4 x 3.8 R1.5, running past the wall) at its bottom, the narrowest (the taper only widens it)
        plan_ = Polygon([tuple(np.array(q["edge_pt"]) + t * z_ + n * x_) for x_, z_ in q["plan"]]).intersection(
            Polygon([fr(-cl["len"] / 2 - 1, -cl["under"]), fr(cl["len"] / 2 + 1, -cl["under"]), fr(cl["len"] / 2 + 1, q["wall_gap"] - cl["wall_air"]), fr(-cl["len"] / 2 - 1, q["wall_gap"] - cl["wall_air"])]))
        rx_ = q["recess_x"]
        fit_ = rx_.exterior.distance(plan_.exterior)
        assert rx_.contains(plan_) and cl["fit"] >= cl["min_fit"] and fit_ >= cl["min_fit"] - 1e-6, (h, q["name"], fit_)
        assert abs(plan_.bounds[0] - plan_.bounds[2]) > 0 and abs(plan_.area) > 0.9 * 9.4 * (cl["under"] + 0.1)  # (not eaten)
        assert 0.1 <= q["profile"][1][0] <= q["wall_gap"] + 0.0 + 1e-6 or q["profile"][1][0] <= q["wall_gap"] + 1e-6, (h, q["name"])  # spine on the wall side
        for a_, w_ in ((prof[1][0], w_bot), (prof[2][0], slot_hi + cl["lip"])):
            wn_ = float(next(v for k_, v in q["wall_n"] if abs(k_ - w_) < 1e-9))
            assert abs(a_ - (wn_ - cl["wall_air"])) < 1e-6, (h, q["name"], w_)
        # the plan, wall side included, stays wall_air inside the pocket wall at the clip's bottom and top levels (the wall may curve in)
        for w_ in (w_bot, slot_hi + cl["lip"]):
            assert o_at(w_).buffer(-cl["wall_air"] + 1e-6).contains(Polygon([tuple(np.array(q["edge_pt"]) + t * z_ + n * x_) for x_, z_ in q["plan"]])), (h, q["name"], w_)
        assert len(q["lattice"]) == 3 and all(len(hx) == 6 for hx in q["lattice"])
        hx_w = [p_[1] for p_ in q["lattice"][0]]
        assert abs((max(hx_w) - min(hx_w)) - cl["lattice_cell"] * 2 / math.sqrt(3)) < 1e-9  # 2.3 across flats
        assert abs(q["lattice"][1][0][0] - q["lattice"][0][0][0] - (cl["lattice_cell"] + cl["lattice_wall"])) < 1e-9  # 0.8 walls
        assert min(hx_w) - w_bot >= 0.6 and slot_lo - max(hx_w) >= 0.6, (h, q["name"])  # the cells sit between a floor and the ledge top
        assert q["floor_z_min"] >= P["clip_floor_min"] - 1e-6 and abs(q["floor_z_min"] - min(
            G.z_at(Ms[h], G.FLOOR_W, x_, y_) for x_, y_ in mo_.exterior.coords)) < 1e-9
        assert q["floor_z_min"] - D_c >= P["base_min_groove"] - 1e-6  # >= 3.5 of body left under the recess floor
        # the clip's matrix puts its (x out, y up w, z along) frame on the PCB-local point, in the world
        Mc = np.array(q["matrix"])
        assert np.allclose(Mc @ [0, 0, 0, 1], Ms[h] @ [q["edge_pt"][0], q["edge_pt"][1], 0, 1], atol=1e-6)
    for a_, b_ in zip(d["clips"], d["clips"][1:]):
        assert a_["mouth"].distance(b_["mouth"]) > 3.0  # no two recesses meet

# §6.9 UDB (M5: hung upside down from the body): centred on the ridge, back face udb_air under the slot roof,
# receptacle on its underside, face <= 1.5 behind the rear; two front standoffs into the bay ceiling.
u = g["udb"]
U4 = np.array(u["matrix"])
board = affinity.translate(u["board"], U4[0, 3], U4[1, 3])
assert abs(U4[0, 3] - g["ridge_x"]) < 1e-9 and np.allclose(U4[:3, :3], np.diag([-1, 1, -1]))
assert abs(g["notch_z"][1] - U4[2, 3] - P["udb_air"]) < 1e-9 and abs(g["bay_z"][1] - U4[2, 3] - P["udb_mount"][1]) < 1e-9
assert P["udb_mount"][1] >= 0.5 and len(u["mounts"]) == 2
assert s["panel"].buffer(1.0).contains(board) and abs(board.area - (18 * 16.5 - (4 - math.pi) * 4)) < 0.1
assert abs(u["receptacle_centre_z"] - (U4[2, 3] - P["udb_t"] - P["usb_receptacle"][2] / 2)) < 1e-9 and 0 < P["usb_recess"] <= P["usb_neck"][1] + 0.25 + 1e-9  # v2: the neck depth + 0.25 (v1: <= 1.5)
assert abs(u["receptacle"].bounds[3] - 16.5 / 2) < 1e-9  # face at the board's back edge
assert all(u["board"].contains(hl) for hl in u["holes"])

# Screws (M8, user): 3, all in the panel's recessed field just inside its border: the 2 back corners, and one at the
# panel's V point on the ridge (screw_front_offset: its distance from the V); every countersink head inside the
# recess, >= 5 mm of floor straight over each (short) insert
sc = [Point(q) for q in g["screws"]]
assert len(sc) == 3 and g["insert_depths"] == [P["insert_hole_short"][1]] * 3
rec = g["panel_recess"]
assert all(rec.buffer(-0.5).contains(q.buffer(P["screw_head"] / 2)) for q in sc)
assert all(rec.exterior.distance(q) <= P["screw_head"] / 2 + P["screw_recess_margin"] + 0.6 for q in sc[:2])  # at the field's edge
assert all(0 <= o_ <= 30 for o_ in g["screw_front_offset"]), g["screw_front_offset"]  # V screw: its distance from the V
gro_all = unary_union([f["grooves"] for f in g["cavity_steps"]["floor"].values()])
for q in sc:  # >= 5 mm of body straight over each insert (the floor plane, less a relief groove where one runs over it)
    for a in np.linspace(0, 6.3, 9):
        x_, y_ = q.x + 2 * math.cos(a), q.y + 2 * math.sin(a)
        fz = G.surface(Ms.values(), G.FLOOR_W, x_, y_) - (P["relief"][1] if gro_all.contains(Point(x_, y_)) else 0)
        assert fz - P["panel_t"] - P["insert_hole_short"][1] >= 5.0, (q, fz)
assert sc[0].x < g["ridge_x"] < sc[1].x and abs(sc[2].x - g["ridge_x"]) < 1.0 and min(sc[0].y, sc[1].y) > sc[2].y + 10
# the countersink in the 3.6 mm field: what is left under the head's cone
under_cs = P["panel_t"] - P["screw_seat"][0] - (P["screw_head"] - P["screw_clear"]) / 2  # v2: the seat pad is 0.4 deep, the field 0.6
assert under_cs > 1.9, under_cs  # M7 panel_t 4: 1.94 (target 2 for wood)
# v2 seat pads: round each screw, radius head / 2 + screw_seat[1], the field is only the seat depth deep there; the deep
# part (R3 corners) is the field less the pads, inside the field
pad_r = P["screw_head"] / 2 + P["screw_seat"][1]
deep = g["panel_recess_deep"]
assert abs(P["panel_recess"][0] - 0.6) < 1e-9 and P["panel_recess"][0] > P["screw_seat"][0]
assert rec.buffer(1e-6).contains(deep) and all(deep.distance(q) >= pad_r - 0.01 for q in sc)
assert deep.area > 0.9 * (rec.area - sum(math.pi * pad_r ** 2 for _ in sc)) - 50 and radius_ok(deep.union(box(deep.bounds[0], deep.bounds[3] - 0.5, deep.bounds[2], deep.bounds[3] + 30)), P["panel_recess"][2], skip=rec.exterior.buffer(0.01).union(unary_union([q.buffer(pad_r + 0.01).boundary for q in sc])).union(box(-1e3, deep.bounds[3] - 0.5, 1e3, 1e3)))  # (v2: as it runs on out through the back edge)
pc = list(s["panel"].exterior.coords)
tip_ = min(pc, key=lambda q: abs(q[0] - g["ridge_x"]) * 10 + q[1])  # the panel's V tip
assert s["panel"].contains(unary_union([g["bay"], g["cavity_steps"]["chan"]]).buffer(-0.01)) and \
    s["panel"].buffer(-P["ledge"] + 0.01).contains(g["cavity_steps"]["chan"]), "channels / bay under the panel"
assert 0.35 <= s["panel"].area / s["footprint"].area <= 0.65  # about half the underside
# M7 recessed field on the panel's underside: inside the border, R3+ corners (Ø6 flat end mill), one field
assert rec.geom_type == "Polygon" and s["panel"].buffer(0.6).contains(rec) and rec.bounds[3] >= s["panel"].bounds[3] - 0.01  # M8: runs out through the back edge
# (v2: judged as the field runs on out through the back edge, not as a wall at the clip: its side lines continue straight)
rec_run = rec.union(box(rec.bounds[0], s["panel"].bounds[3] - 0.5, rec.bounds[2], s["panel"].bounds[3] + 30))
assert radius_ok(rec_run, P["panel_recess"][2], skip=s["panel"].exterior.buffer(0.6).union(box(-1e3, s["panel"].bounds[3] - 0.5, 1e3, 1e3))) and rec.area > 0.6 * s["panel"].area  # M8: the back corners run out through the edge
# v2 (user): the underside field's side border and the rear-face field's side border are the same width (3.5), so they run on into
# each other with no jog, and the underside one is constant to the back edge (no taper)
y_back = s["panel"].bounds[3]
for key in ("left", "right"):
    xb_ = g["band_recess"][key].bounds[0 if key == "left" else 2]  # the rear-face field's outer side
    st_ = rec.intersection(box(-1e3, y_back - 0.07, 1e3, y_back - 0.05)).bounds  # the underside field's, at the back edge
    assert abs((st_[0] if key == "left" else st_[2]) - xb_) < 0.02, (key, st_, xb_)
    edge_x = s["panel"].bounds[0 if key == "left" else 2]
    assert abs(abs(xb_ - edge_x) - P["panel_recess"][1]) < 0.02, (key, xb_, edge_x)
for y_ in np.linspace(60.0, y_back - 0.1, 12):  # constant: the same border all the way
    row_ = rec.intersection(box(-1e3, y_, 1e3, y_ + 0.02)).bounds
    assert abs(row_[0] - s["panel"].bounds[0] - P["panel_recess"][1]) < 0.02 and abs(s["panel"].bounds[2] - row_[2] - P["panel_recess"][1]) < 0.02, (y_, row_)
# no 0.4-deep tongue / keyhole neck: the shallow (seat depth) part is the three seats only, none reaches the back edge
shallow = rec.difference(deep)
assert shallow.intersection(box(-1e3, y_back - 2.5, 1e3, 1e3)).area < 0.01, "seat tongue to the back edge"
seats_ = [q for q in getattr(shallow, "geoms", [shallow]) if q.area > 1.0]
assert len(seats_) == 3 and all(sum(q.contains(c_) for c_ in sc) == 1 for q in seats_), [q.area for q in seats_]
assert all(q.distance(c_) <= 0.0 for q in seats_ for c_ in sc if q.contains(c_))
keep = board.buffer(0.5 + P["screw_head"] / 2, join_style="mitre")
assert not any(keep.intersects(q) for q in sc)

# v2: 4 bumpons (3M SJ5302) in shallow recesses, the centres inset bumpon["inset"] from the two desk-level footprint edges
# of each corner: symmetric about the ridge, all inside the footprint, clear of the panel's rabbet, the screws and each
# other; the front pair outside the pockets (solid bezel), the rear pair with the body thick over them.
bp = g["bumpons"]
bd_ = P["bumpon"]
assert len(bp) == 4 and all(abs(b["d"] - bd_["recess_d"]) < 1e-9 and abs(b["depth"] - bd_["recess_depth"]) < 1e-9 for b in bp)
assert bd_["recess_d"] > bd_["d"] and 0.3 <= bd_["recess_depth"] < bd_["h"] - 1.0  # a locating recess, the bumpon stands >= 1 mm proud
assert abs(bd_["d"] - 7.9) < 1e-9 and abs(bd_["h"] - 2.2) < 1e-9  # 3M SJ5302
for b in bp:
    c_ = Point(b["x"], b["y"])
    assert s["footprint"].exterior.distance(c_) >= bd_["inset"] - 0.01 and s["footprint"].exterior.distance(c_) < bd_["inset"] + 1.0
    assert s["footprint"].buffer(-(bd_["inset"] - bd_["recess_d"] / 2) + 0.01).contains(c_.buffer(bd_["recess_d"] / 2))
    assert c_.buffer(bd_["recess_d"] / 2).distance(s["rabbet"]["print"]) > 10, b["name"]
    assert all(c_.distance(q) > bd_["recess_d"] / 2 + P["screw_head"] / 2 + 5 for q in sc), b["name"]  # clear of the countersink cones
    if b["name"].startswith("front"):
        assert c_.buffer(bd_["recess_d"] / 2).distance(opening) > 1.5, b["name"]  # under the solid bezel, not under a pocket
    else:  # under a rear pocket: the floor plane is high over it (>= 8 mm of body over the recess)
        assert G.surface(Ms.values(), G.FLOOR_W, b["x"], b["y"]) - bd_["recess_depth"] >= 8.0, b["name"]
xs_b = sorted(b["x"] for b in bp)
assert abs((xs_b[0] + xs_b[3]) / 2 - g["ridge_x"]) < 0.05 and abs((xs_b[1] + xs_b[2]) / 2 - g["ridge_x"]) < 0.05
assert min(Point(a["x"], a["y"]).distance(Point(b["x"], b["y"])) for a in bp for b in bp if a is not b) > 30
assert g["bay"].union(g["notch"]).contains(board.buffer(0.25)) and radius_ok(g["bay"], P["pocket_r"])
assert g["notch"].bounds[0] <= g["bay"].bounds[0] + 0.01 and g["notch"].bounds[2] >= g["bay"].bounds[2] - 0.01
assert radius_ok(g["notch"], P["pocket_r"])
# M5: was R1 (Ø2 tool). M7: inside the body (the footprint); its outer ends stop square at the rabbet's side walls,
# where the body's band diagonal leaves the pocket < 0.2 mm tall (skipped, as is the open rear face)
rims_ = s["footprint"].difference(g["rabbet_lean"])
assert radius_ok(g["lip_pocket"], P["pocket_r"], skip=rims_.buffer(0.01).boundary.union(rims_.buffer(5).difference(s["footprint"])))
# the slot's floor corner (R usb_r[1] seen from behind) clears the UDB board's rear corners
sw, rr = (g["notch"].bounds[2] - g["notch"].bounds[0]) / 2, P["usb_r"][1]
# M5: now the slot's roof corners (R usb_r[0]) clear the flipped board's top corners
rr = P["usb_r"][0]
assert math.hypot(sw - rr - P["udb"][0] / 2, g["notch_z"][1] - rr - U4[2, 3]) <= rr - 0.2
assert g["bay"].intersection(s["cavity"]).bounds[2] - g["bay"].intersection(s["cavity"]).bounds[0] >= 8
nx0, _, nx1, _ = g["notch"].bounds
rz = u["receptacle_centre_z"]
assert abs((nx0 + nx1) / 2 - U4[0, 3]) < 1e-9 and abs(g["usb_centre"][1] - rz) < 0.2
assert all(g["walls"][k] >= 5 - 1e-6 for k in ("bezel", "web", "rabbet_to_footprint", "cavity_to_footprint",
                                                "insert_to_cavity", "bay_rear_m3", "bay_rear_m4", "insert_to_lip", "cavity_to_lip"))

# M6 pocket floor: one plane per half parallel to its PCB (same normal), floor_air under the PCB
# underside, with relief grooves relief[1] deeper (R3 corners, off the walls). On a 2 mm grid over each PCB (islands
# excluded) the air is that, and nothing (grooves included) is below the H_front rule height.
cs = g["cavity_steps"]
WB = -(P["plate_to_pcb"] + P["pcb_t"])
isl = unary_union([q["poly"] for q in cs["islands"]])
fz_at = lambda h, pt: G.z_at(Ms[h], cs["floor"][h]["groove_w"][0] if cs["floor"][h]["grooves"].contains(pt) else
                             cs["floor"][h]["w"], pt.x, pt.y)
airs, sock_cover = {}, {}
for h, f in cs["floor"].items():
    M, d = Ms[h], g["halves"][h]
    assert abs(f["w"] - G.FLOOR_W) < 1e-9 and abs(f["groove_w"][1] - f["groove_w"][0] - P["relief"][1]) < 1e-9
    gr = f["grooves"]
    assert gr.area > 1000 and f["open"].buffer(-P["groove_wall"] + 0.01).contains(gr) and radius_ok(gr, P["groove_r"], tol=0.1) and P["groove_r"] >= 1.5, h  # (v2: R2 groove corners, Ø3 tool min R1.5)
    # M6 (user): the grooves run under the hotswap sockets: every socket keep-out, projected along the PCB normal
    # onto the floor plane, lies in a groove, but where it is within island_clear + R3 of an island (insert boss,
    # boss) or a JST breakthrough, which the grooves keep away from
    keep = unary_union([q["poly"].buffer(P["island_clear"] + 0.01) for q in cs["islands"] if q["half"] == h] +
                       [])  # (v2: the grooves may run into the JST breakthroughs / cable channels)
    n_part = n_wall = 0
    for sk in d["sockets"]:
        fl = world(M, f["w"], sk)
        # (and the groove's R3 corners round those notches). M6 (user): a flat groove_wall band along every wall for
        # the C-clips' recesses: a socket reaching within groove_wall + R3 of the wall is exempt (counted)
        if not f["open"].buffer(-P["groove_wall"] - P["pocket_r"]).contains(fl):
            n_wall += 1
            continue
        rest = fl.difference(keep.buffer(P["pocket_r"]))  # (a socket partly under a clip mouth keep-out is not exempt: its groove must cover the rest)
        assert rest.is_empty or gr.buffer(1e-6).contains(rest), (h, sk.centroid, rest.difference(gr).area)
        n_part += not fl.difference(keep).equals(fl)
    sock_cover[h] = (len(d["sockets"]), n_part, n_wall)
    # v2: one groove per row, no fragments: every piece >= 100 mm2, and no land < 1 mm between two grooves
    pcs_ = list(getattr(gr, "geoms", [gr]))
    assert all(q_.area >= 100 for q_ in pcs_), (h, [round(q_.area) for q_ in pcs_])
    assert all(a_.distance(b_) >= 1.0 for i_, a_ in enumerate(pcs_) for b_ in pcs_[i_ + 1:]), h
    n_ch_ = sum(1 for q_ in pcs_ if q_.intersects(cs["chan"].union(cs["stubs"])))
    print(f"{h}: grooves per piece (mm2) {sorted(round(q_.area) for q_ in pcs_)}; touching a cable channel / breakthrough: {n_ch_}")
    for q in getattr(gr, "geoms", [gr]):
        # M7: >= base_min_groove of body under a groove (over the desk in front, over the rabbet ceiling over the panel)
        pz_ = s["rabbet"]["print"]
        for part_, base_ in ((q.difference(pz_), P["base_min_groove"]), (q.intersection(pz_), P["panel_t"] + P["base_min_groove"])):
            for g_ in getattr(part_, "geoms", [part_]):
                if not g_.is_empty and g_.area > 1e-6:
                    assert all(G.z_at(M, f["groove_w"][0], x, y) >= base_ - 1e-6 for x, y in g_.exterior.coords), h
    pcbw = world(M, WB, d["pcb"])
    x0, y0, x1, y1 = pcbw.bounds
    lo_hi = []
    for x in np.arange(x0, x1, 2.0):
        for y in np.arange(y0, y1, 2.0):
            pt = Point(x, y)
            if pcbw.contains(pt) and not isl.buffer(0.5).contains(pt):
                lo_hi.append((G.z_at(M, WB, x, y) - fz_at(h, pt)) * M[2, 2])  # along the normal
    want = WB - G.FLOOR_W
    assert all(want - 1e-6 <= a_ <= want + P["relief"][1] + 1e-6 for a_ in lo_hi), h
    airs[h] = (min(lo_hi), max(lo_hi))
assert not any(q["kind"].startswith("pillar") for q in cs["islands"])  # v2: no snap pillars
# v2: each C-clip recess (mouth at the floor plane) lies in the flat wall band: within the pocket, off the grooves, bosses
# and JST breakthroughs, and the band keeps >= groove_wall - clip_out... from the grooves
for h, d in g["halves"].items():
    f_ = cs["floor"][h]
    for q in d["clips"]:
        mouth = world(Ms[h], f_["w"], q["mouth"])
        assert f_["open"].buffer(1e-3).contains(mouth), (h, q["name"])  # inside the pocket: wall side on the wall, no undercut
        isl_h = unary_union([i_["poly"] for i_ in cs["islands"] if i_["half"] == h] + [Point(0, 1e6).buffer(1)])
        assert mouth.distance(f_["grooves"]) >= P["clip_keep"] - 0.02 and mouth.distance(isl_h) >= 1.0 and mouth.distance(cs["stubs"]) >= 1.0, (h, q["name"])
        assert world(Ms[h], f_["w"], q["recess"]).distance(f_["grooves"]) >= 1.0, (h, q["name"])  # v2: land >= 1 mm to the recess too
        assert mouth.symmetric_difference(q["mouth_w"]).area < 1e-3
        ov_c = cs["chan"].intersection(mouth)  # over a cable channel the recess still leaves >= 3 mm of floor over it
        for o_ in getattr(ov_c, "geoms", [ov_c]):
            if not o_.is_empty and o_.area > 1e-6:
                assert min(G.z_at(Ms[h], f_["w"], x_, y_) for x_, y_ in o_.exterior.coords) - P["clip_recess"][2] - cs["chan_z"][1] >= 3 - 1e-6, (h, q["name"])
for q in cs["islands"]:
    assert q["poly"].geom_type == "Polygon" and q["z"][1] > q["z"][0] and q["join"].contains(q["poly"].buffer(-1e-3))
    if q["kind"].startswith("UDB"):
        assert all(G.z_at(Ms[q["half"]], WB, *p) - 2.0 >= q["z"][1] for p in q["poly"].exterior.coords), q["kind"]
    if q["kind"].startswith("insert boss"):  # M3 insert bosses: under the sockets and the PCB
        h = q["half"]
        socks = unary_union([world(Ms[h], WB, k_) for k_ in g["halves"][h]["sockets"]]).intersection(q["poly"])
        sp = [p for q_ in getattr(socks, "geoms", [socks]) if not q_.is_empty for p in q_.exterior.coords]
        assert all(G.z_at(Ms[h], WB, *p) - P["socket_h"] - 0.2 >= q["z"][1] for p in sp), q["kind"]
        assert all(G.z_at(Ms[h], WB, *p) - 0.5 >= q["z"][1] for p in q["poly"].exterior.coords), q["kind"]
# cable path: each JST plug pocket inside its breakthrough; channel + breakthroughs + bay one connected void;
# >= 3 mm of floor over the channel away from the breakthroughs
for h, d in g["halves"].items():
    assert cs["stubs"].buffer(0.01).contains(world(Ms[h], WB, d["jst_pocket"])), h
assert unary_union([cs["chan"], cs["stubs"], g["bay"]]).buffer(0.01).geom_type == "Polygon"
assert radius_ok(cs["chan"], P["pocket_r"], tol=0.1)
ctop = cs["chan_z"][1]
away = cs["chan"].difference(cs["stubs"].buffer(1.0))
for geom in getattr(away, "geoms", [away]):
    for x, y in geom.exterior.coords:
        for h, f in cs["floor"].items():
            pt = Point(x, y)
            if f["open"].buffer(P["pocket_r"]).contains(pt):
                fz = min(fz_at(h, Point(x + dx, y + dy)) for dx in (-0.5, 0, 0.5) for dy in (-0.5, 0, 0.5))
                assert fz - ctop >= 3 - 0.05, (x, y, fz)
assert ctop <= u["mount_z"][0] - P["udb_t"] - 1.0  # the channels pass under the board, not up into its mounts

# v2: the ridge is the R2 midpoint (checked at the top), not the key-gap midpoint; the spread is split equally, so the web
# is wider than v1's 9.5 mm (the right half's top-row Y key sits 3.5 + 0.06 mm from the ridge, its opening edge at least
# 2.3 mm: the crest keeps v1's 2.45 within 0.15), and the outline is centred on the ridge: both outer edges equidistant.
oL, oR = sorted(opening.geoms, key=lambda o: o.bounds[0])
dL, dR = g["ridge_x"] - oL.bounds[2], oR.bounds[0] - g["ridge_x"]
assert P["half_spread"][0] == P["half_spread"][1]
assert 12.5 <= g["web_min"] <= 15.5 and min(dL, dR) >= 2.3, (dL, dR, g["web_min"])
assert abs(g["outline_offset"]) < 0.02, g["outline_offset"]
ob_ = s["outline_sharp"].bounds
assert abs((g["ridge_x"] - ob_[0]) - (ob_[2] - g["ridge_x"])) < 0.05, ob_  # outer case edges equidistant from the centreline
# M6: the V's inner corner on the ridge (one front bezel grown just enough), both front bezels >= bezel_front
assert abs(g["v_offset"]) < 0.05 and min(g["front_bezels"]) >= P["bezel_front"] - 1e-9, (g["v_offset"], g["front_bezels"])
# M7: the panel's V tip on the ridge too (its screw is checked above)
assert abs(tip_[0] - g["ridge_x"]) < 1.0, tip_
for h, f in cs["floor"].items():  # M6: >= 3 mm of material between a groove and a cable channel / the UDB bay
    for void, ztop_ in ((cs["chan"], cs["chan_z"][1]), (g["bay"], g["bay_z"][1])):
        ov = f["grooves"].intersection(void)
        for q in getattr(ov, "geoms", [ov]):
            if not q.is_empty and q.area > 1e-6:
                assert min(G.z_at(Ms[h], f["groove_w"][0], x, y) for x, y in q.exterior.coords) - ztop_ >= 3 - 1e-6, h
# ---- v2 (user, approved) --------------------------------------------------------------------------------------------
# 1, 5, 6: the crease cant, the angles, the heights (outer front corners, front V, rear outer, rear centre before the cut)
assert P["lower_cant"] == 12.0 and P["panel_shift"] == 48.0 and P["half_spread"] == [3.5, 3.5]
assert P["typing_angle"] == 8.0 and P["tent"] == 5.0 and P["base_min"] == 3.5 and P["floor_air"] == 3.5
hh = g["heights"]
assert abs(hh["front_left"] - 16.2) < 0.4 and abs(hh["front_right"] - 16.1) < 0.4 and abs(hh["front_v"] - 26.4) < 0.4, hh
assert abs(hh["back_left"] - 28.8) < 0.6 and abs(hh["back_right"] - 28.8) < 0.6 and abs(hh["back_centre"] - 41.4) < 0.3, hh
assert abs(hh["back_left"] - hh["back_right"]) < 1e-3  # symmetric about the centreline (the front pair differs by the 0.1 bezel)
assert abs(hh["front_left"] - hh["front_right"]) < 0.3
assert g["floor_min_z"] >= P["base_min"] - 1e-9  # the front base rule (the clips' recesses: their own check above)
# the two front faces (level crease) lean lower_cant from the upright: the plane's normal is lower_cant above horizontal
for n_ in lb_["normals"][3:5]:
    assert abs(math.degrees(math.asin(abs(n_[2]) / np.linalg.norm(n_))) - P["lower_cant"]) < 0.01, n_
# the end creases are level: the back vertices' crease height equals the front's (lower_back 0.477; the spec's 0.467 left 0.41 mm)
assert abs(lb_["crease"][0][2] - lb_["crease"][3][2]) < 0.02 and abs(lb_["crease"][2][2] - lb_["crease"][3][2]) < 0.02, lb_["crease"]
# 2: the centreline is the R2 midpoint: both R2 rows end the same distance from it, so do the outer case edges
r2_in = g["ridge_x"] - max(r2["left"])
assert abs(r2_in - (min(r2["right"]) - g["ridge_x"])) < 1e-9 and 8.1 < r2_in < 8.3, r2_in  # ~8.2 mm (the spec's 8.24)
assert 141.9 < g["ridge_x"] - ob_[0] < 143.0, g["ridge_x"] - ob_[0]  # both outer edges ~142.4 mm from it (spec ~142.52)
assert 13.5 <= g["web_min"] <= 14.5, g["web_min"]  # the B-N web ~14 mm (spec ~14.1; the pocket grew round the frozen PCB)
assert abs(g["web_sym"][0] - dL) < 0.02 and abs(g["web_sym"][1] - dR) < 0.02 and min(g["web_sym"]) >= 2.3
# 8: bezels: front 6.0 (the V-alignment correction is on the right, +0.10), sides 6.0, back 8.5; outline ~285.05 x 105.21
assert P["bezel_front"] == 6.0 and P["bezel_back"] == 8.5 and P["bezel_side"] == 6.0
assert abs(g["front_bezels"][0] - 6.0) < 1e-9 and abs(g["front_bezels"][1] - 6.10) < 0.01, g["front_bezels"]
assert abs(g["outline_size"][0] - 285.05) < 0.5 and abs(g["outline_size"][1] - 105.21) < 0.6, g["outline_size"]
# 4: the bottom panel is 6 mm wider each side (195.6 -> ~212.3 mm), the rear pentagon, three screws, solid front underside
pb_ = s["panel"].bounds
assert 212.0 <= pb_[2] - pb_[0] <= 212.6, pb_[2] - pb_[0]
assert abs((pb_[0] + pb_[2]) / 2 - g["ridge_x"]) < 0.05 and len(sc) == 3
assert s["panel"].distance(Point(g["ridge_x"], s["footprint"].bounds[1] + 1.0)) > 40  # nothing of the panel at the front
# 3: bumpon recesses 8.4 x 0.5 for 3M SJ5302 at about the spec's spots (they follow the footprint)
want_b = {"front left": (4.4, 20.8), "rear left": (4.4, 80.7), "front right": (259.0, 19.9), "rear right": (259.0, 80.7)}
for b in bp:
    assert math.dist((b["x"], b["y"]), want_b[b["name"]]) < 0.7, (b["name"], b["x"], b["y"])
assert not any(k_ in P for k_ in ("feet", "foot_depth", "foot_peg", "foot_fit", "snap", "pillar"))  # TPU feet / pegs / snaps are gone
# 10: the USB opening is stepped: a 17 wide neck usb_neck[1] = 2 deep at the rear face, the 22 wide chamber behind it, the board's
# receptacle face 0.25 behind the step (usb_recess 2.25); both are R3 in plan
yb_board = U4[1, 3] + P["udb"][1] / 2
y_face = g["lower_band"]["foot"][1][1] + u["receptacle_centre_z"] * math.tan(math.radians(P["lower_cant"]))  # the rear face at the receptacle
y_step = yb_board + 0.25
assert abs(P["usb_recess"] - (P["usb_neck"][1] + 0.25)) < 1e-9 and abs((y_face - y_step) - P["usb_neck"][1]) < 1e-6, (y_face, y_step)
wid = lambda y_: g["notch"].intersection(LineString([(0, y_), (400, y_)])).length
assert abs(wid(y_face + 3.0) - P["usb_neck"][0]) < 1e-6 and abs(wid(y_step + 1.0) - P["usb_neck"][0]) < 1e-6  # the neck
assert abs(max(wid(y_) for y_ in np.arange(y_step - 12, y_step - 3, 0.5)) - P["usb_slot_w"]) < 1e-6  # the chamber
assert P["usb_opening"][1] == 7.2 and abs(g["notch_z"][1] - g["notch_z"][0] - (P["panel_t"] + 7.2 + 1.0)) < 1e-9
# 11: field 0.6 deep, seat pad 0.4 (0.2 proud of the field), countersink starts at the seat depth (under-cone check above)
assert P["panel_recess"][0] == 0.6 and P["screw_seat"][0] == 0.4 and abs(P["panel_recess"][0] - P["screw_seat"][0] - 0.2) < 1e-9
assert abs(under_cs - 1.94) < 0.02, under_cs

# UDB supports: each M2 insert (Ø3.2 x 3.6 in a standoff) has >= 5 mm of body over it: the pocket floor plane where it is high
# enough (v2: 7.4 mm, no boss is generated), else a boss stands there and stays >= 2 mm under the PCB (checked with the islands)
itop_u = u["mount_z"][0] + P["udb_insert"][1]
for mx, my in u["mounts"]:
    cover = G.surface(Ms.values(), G.FLOOR_W, mx, my) - itop_u if opening.buffer(1e-6).contains(Point(mx, my)) else 99.0
    bosses_ = [q for q in cs["islands"] if q["kind"].startswith("UDB") and q["poly"].buffer(1e-6).contains(Point(mx, my))]
    assert cover >= 5.0 or bosses_, (mx, my, cover)
assert all(G.z_at(Ms[q["half"]], WB, *p_) - 2.0 >= q["z"][1] for q in cs["islands"] if q["kind"].startswith("UDB") for p_ in q["poly"].exterior.coords)

# 9: the rear triangle: ONE plane through the horizontal line on the rear face 8 mm under the peak (BC) and the crest point A
# 25 mm forward of the rear edge; everything above it is removed. BC ~33.4, the rear-face triangle ~180 x 8
rc = g["rear_cut"]
A_, yr_ = np.array(rc["A"]), rc["y_rear"]
assert abs(yr_ - g["_shapes"]["outline_sharp"].bounds[3]) < 1e-6 and abs(A_[0] - g["ridge_x"]) < 1e-9
assert abs((yr_ - A_[1]) - P["rear_cut"]["back"]) < 1e-9 and abs(A_[2] - G.surface(Ms.values(), P["lip"], A_[0], A_[1])) < 1e-9  # A on the crest roof
assert abs(rc["bc"] - (hh["back_centre"] - P["rear_cut"]["drop"])) < 1e-9 and abs(g["heights_cut"]["back_centre"] - rc["bc"]) < 1e-9
assert 37.0 <= rc["bc"] <= 37.7, rc["bc"]  # peak 41.35 less the drop (was 8: 33.35 / spec ~33.45; shallower so the triangle is narrower)
pl_ = [np.array(q_) for q_ in rc["points"]]  # three points of the plane: the face line's ends and A
nrm = np.cross(pl_[1] - pl_[0], pl_[2] - pl_[0])
assert abs(nrm[0]) < 1e-9 and abs(pl_[0][2] - pl_[1][2]) < 1e-9 and nrm[2] != 0  # the face line is horizontal: a plane tilted about X only
zpl = lambda x_, y_: float(pl_[0][2] - (nrm[0] * (x_ - pl_[0][0]) + nrm[1] * (y_ - pl_[0][1])) / nrm[2])
assert abs(zpl(*A_[:2]) - A_[2]) < 1e-9
roof = lambda x_, y_: G.surface(Ms.values(), P["lip"], x_, y_)
bw_, bh_ = rc["face"]
assert 90 <= bw_ <= 120 and abs(bh_ - P["rear_cut"]["drop"]) < 1e-9, rc["face"]  # the leftover rear-face triangle: a third to two fifths of the case width
assert rc["pocket_margin"] >= 6.0 and abs(rc["pocket_margin"] - Polygon(rc["plan"]).distance(unary_union(list(opening.geoms)))) < 1e-9, rc["pocket_margin"]  # plan: cut triangle to both pockets
for x_ in rc["x"]:  # its base ends: the roof is at BC on the rear face
    assert abs(roof(x_, yr_) - rc["bc"]) < 1e-6
    for f_ in (0.25, 0.5, 0.9):  # and the cut's two edges (plane meets facet) run straight to A
        px_, py_ = x_ + (A_[0] - x_) * f_, yr_ + (A_[1] - yr_) * f_
        assert abs(roof(px_, py_) - zpl(px_, py_)) < 1e-6, (x_, f_)
# only a triangle is cut: forward of A and outside the two edges the plane is above the roof, behind it below
assert zpl(g["ridge_x"], yr_ - P["rear_cut"]["back"] - 1.0) > roof(g["ridge_x"], yr_ - P["rear_cut"]["back"] - 1.0) and zpl(g["ridge_x"], yr_ - P["rear_cut"]["back"] + 1.0) < roof(g["ridge_x"], yr_ - P["rear_cut"]["back"] + 1.0)
assert zpl(rc["x"][0] - 5, yr_) > roof(rc["x"][0] - 5, yr_) and zpl(rc["x"][1] + 5, yr_) > roof(rc["x"][1] + 5, yr_) and zpl(g["ridge_x"], yr_) < roof(g["ridge_x"], yr_)
# the wall left above the plate top at the pockets under the cut stays >= 2 mm (vertical), and the cut stays blind to the UDB bay
tri_ = Polygon(rc["plan"])
wall_ = [zpl(x_, y_) - G.surface(Ms.values(), 0.0, x_, y_) for o_ in opening.geoms for x_, y_ in
         (o_.exterior.interpolate(t_) .coords[0] for t_ in np.arange(0, o_.exterior.length, 0.25)) if tri_.buffer(0.01).contains(Point(x_, y_))]
assert (min(wall_) >= 2.0 and abs(min(wall_) - rc["pocket_wall_min"]) < 1e-6) if wall_ else rc["pocket_wall_min"] is None  # (v2 revised: the triangle no longer reaches a pocket: margin >= 6 above)
bx0_, by0_, bx1_, by1_ = g["bay"].bounds
assert min(zpl(x_, y_) for x_, y_ in ((bx0_, by0_), (bx1_, by0_), (bx0_, by1_), (bx1_, by1_))) - g["bay_z"][1] >= 5.0  # blind to the bay
usb_top_ = P["panel_t"] + P["usb_opening"][1]
assert 24.0 <= rc["bc"] - usb_top_ <= 27.0, rc["bc"] - usb_top_  # the band of rear face above the USB slot (~25.6)
assert abs(g["max_height_cut"] - max(max(g["heights_cut"].values()), A_[2])) < 1e-9 and g["max_height_cut"] < g["max_height"]

# every key row keeps its relief groove (a row's groove once vanished: the R3 opening erases strips < 6 mm wide):
# >= 50% of each row's socket area lies in a groove (this layout: 70..100%)
for h, f in cs["floor"].items():
    rows_ = {}
    for o, sk in zip([o for o in alice.place(lay) if o["half"] == h], g["halves"][h]["sockets"]):
        rows_.setdefault(o["row"], []).append(world(Ms[h], f["w"], sk))
    for r_, s_ in rows_.items():
        u_ = unary_union(s_)
        assert f["grooves"].intersection(u_).area >= 0.5 * u_.area, (h, "row", r_, "groove vanished")

print("sockets over the floor grooves (total; partly over a boss / breakthrough; by the wall, exempt): " +
      ", ".join(f"{h} {a}; {b}; {c}" for h, (a, b, c) in sock_cover.items()))
print("air under the PCBs (mm): " + ", ".join(f"{h} {a:.2f}..{b:.2f}" for h, (a, b) in airs.items()))
print(f"ok  H_front {g['h_front']:.2f} mm, max height {g['max_height_cut']:.2f} mm after the rear cut ({g['max_height']:.2f} before; back centre "
      f"{g['heights']['back_centre']:.2f} -> {g['rear_cut']['bc']:.2f}), outline {g['outline_size'][0]:.2f} x {g['outline_size'][1]:.2f} mm")
