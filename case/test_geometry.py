"""Checks M1 of docs/fusion-case-plan.md. Run: case/.venv/bin/python case/test_geometry.py [LAYOUT.json]"""
import math
from pathlib import Path
import sys

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import geometry as G
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
sp = P["half_spread"]
xs = {h: [p[0] + (-sp[0] if h == "left" else sp[1]) for o in solid(placed) if o["half"] == h for p in footprint(o)]
      for h in ("left", "right")}
assert max(xs["left"]) + 2 <= g["ridge_x"] <= min(xs["right"]) - 2  # M5: >= 2 mm to both halves' keys
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
    for poly, w0, w1, gap in ((d["plate"], -P["plate_t"], 0.0, P["plate_wall_gap"]),
                              (d["pcb"], G.PCB_MID_W - P["pcb_t"] / 2, G.PCB_MID_W + P["pcb_t"] / 2, P["snap_gap"])):
        for w in (w0, w1):
            pw = world(Ms[h], w, poly)
            assert opening.contains(pw) and min(edge.distance(Point(q)) for q in pw.exterior.coords) >= gap - 0.15, (h, w)
    xw = [(Ms[h] @ [u, v, G.PCB_MID_W, 1])[0] for u, v in d["pcb"].exterior.coords]
    assert (max(xw) <= g["ridge_x"] - P["ridge_clear"] + 1e-6) if h == "left" else (min(xw) >= g["ridge_x"] + P["ridge_clear"] - 1e-6)


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

    # §6.11 snaps: one per outer end / front / back / inner end (M5), flush on a straight bit of edge, off the wall in 3D, clear
    # of sockets, the JST pocket and stabs, and >= 15 mm along the edge from any real (>= 45°) corner.
    assert [q["side"] for q in d["snaps"]] == ["front", "front2", "back", "back2"]  # M6 (user): 4 per half, by the corners
    # M6 staple: every snap the full 20 mm part, reach 2.5 or 2.0 (the end walls straightened for it: end_runs)
    for q in d["snaps"]:
        assert q["length"] == P["snap"][0] and q["depth"] - P["snap_spine"] in (2.5, 2.0), (h, q["side"], q["depth"])
    for e_ in ("front", "back"):  # each pair >= L + 5 apart, one toward each corner of its edge
        us = sorted(q["poly"].centroid.x for q in d["snaps"] if q["side"].rstrip("2") == e_)
        assert len(us) == 2 and us[1] - us[0] >= P["snap"][0] + 5 - 1e-6, (h, e_, us)
    ext = d["pcb"].exterior
    for q in d["snaps"]:
        sp = q["poly"]
        # legs (under the PCB) clear of sockets, centre posts, JST pocket; top bar clear of the switch housings
        below = unary_union(d["sockets"] + [d["jst_pocket"]] + [Point(k["x"], k["y"]).buffer(2.0) for k in d["keys"]])
        assert not any(l_.intersects(below) for l_ in q["legs"]) and not sp.intersects(unary_union(d["cutouts"]))
        assert sp.distance(unary_union(d["stabs"])) >= 3.0 and all(l_.difference(sp).area < 1e-9 for l_ in q["legs"])
        cs = list(sp.exterior.coords)[:4]
        outer = LineString(cs[:2])  # the face toward the wall: snap_spine past the edge, the edge flat within snap_flat
        # (over the face's middle 90 %: an end snap's ends sit by the next rows' stagger steps)
        dist = [ext.distance(outer.interpolate(t, normalized=True)) for t in np.linspace(0.05, 0.95, 361)]
        assert q["spine"].intersection(d["pcb"]).area < 1e-3, (h, q["side"])  # the spine stays beside the PCB
        assert max(dist) - min(dist) <= P["snap_flat"] + 1e-3 and -2e-3 < min(dist) - P["snap_spine"] <= P["snap_flat"], (h, q["side"])  # (the edge just past the ends may curve out)
        for k_, lay in [("bar", "snap_bar"), ("spine", "snap_spine")] + [(i_, "snap_leg") for i_ in (0, 1)]:
            part_ = q["legs"][k_] if isinstance(k_, int) else q[k_]  # every part inside the opening at both its ends
            assert part_.geom_type == "Polygon" and part_.area > 1.0, (h, q["side"], k_)
            for w in L_[lay]:
                assert opening.buffer(-P["snap_wall_air"] + 1e-6).contains(world(Ms[h], w, part_)), (h, q["side"], k_, w)
        s0, L = ext.project(outer.centroid), ext.length
        pts = [ext.interpolate((s0 + t) % L) for t in np.arange(-20, 20.01, 0.5)]
        hd = [math.atan2(b.y - a.y, b.x - a.x) for a, b in zip(pts, pts[1:])]
        net = [abs(math.degrees(math.remainder(hd[j] - hd[i], math.tau))) for i in range(4) for j in range(len(hd) - 4, len(hd))]
        if q["corner_dist"] < 15:  # M6: as close to a corner as allowed; >= 5 (reported)
            assert q["corner_dist"] >= 5, (h, q["side"], q["corner_dist"])
            continue
        assert q["corner_dist"] >= 15 and max(net) < 45, (h, q["side"], max(net))  # 15 + 5 either side: no corner

# §6.9 UDB (M5: hung upside down from the body): centred on the ridge, back face udb_air under the slot roof,
# receptacle on its underside, face <= 1.5 behind the rear; two front standoffs into the bay ceiling.
u = g["udb"]
U4 = np.array(u["matrix"])
board = affinity.translate(u["board"], U4[0, 3], U4[1, 3])
assert abs(U4[0, 3] - g["ridge_x"]) < 1e-9 and np.allclose(U4[:3, :3], np.diag([-1, 1, -1]))
assert abs(g["notch_z"][1] - U4[2, 3] - P["udb_air"]) < 1e-9 and abs(g["bay_z"][1] - U4[2, 3] - P["udb_mount"][1]) < 1e-9
assert P["udb_mount"][1] >= 0.5 and len(u["mounts"]) == 2
assert s["panel"].buffer(1.0).contains(board) and abs(board.area - (18 * 16.5 - (4 - math.pi) * 4)) < 0.1
assert abs(u["receptacle_centre_z"] - (U4[2, 3] - P["udb_t"] - P["usb_receptacle"][2] / 2)) < 1e-9 and 0 < P["usb_recess"] <= 1.5
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
under_cs = P["panel_t"] - P["panel_recess"][0] - (P["screw_head"] - P["screw_clear"]) / 2
assert under_cs > 1.9, under_cs  # M7 panel_t 4: 1.94 (target 2 for wood)
pc = list(s["panel"].exterior.coords)
tip_ = min(pc, key=lambda q: abs(q[0] - g["ridge_x"]) * 10 + q[1])  # the panel's V tip
assert s["panel"].contains(unary_union([g["bay"], g["cavity_steps"]["chan"]]).buffer(-0.01)) and \
    s["panel"].buffer(-P["ledge"] + 0.01).contains(g["cavity_steps"]["chan"]), "channels / bay under the panel"
assert 0.35 <= s["panel"].area / s["footprint"].area <= 0.65  # about half the underside
# M7 recessed field on the panel's underside: inside the border, R3+ corners (Ø6 flat end mill), one field
assert rec.geom_type == "Polygon" and s["panel"].buffer(0.6).contains(rec) and rec.bounds[3] >= s["panel"].bounds[3] - 0.01  # M8: runs out through the back edge
assert radius_ok(rec, P["panel_recess"][2], skip=s["panel"].exterior.buffer(0.6)) and rec.area > 0.6 * s["panel"].area  # M8: the back corners run out through the edge
keep = board.buffer(0.5 + P["screw_head"] / 2, join_style="mitre")
assert not any(keep.intersects(q) for q in sc)

# M7: all four feet press into the body's underside, >= rear_foot_clear from the panel's rabbet; bay holds the UDB
# with R >= pocket_r and opens into the cavity (>= 8 mm cable path); the USB notch is centred on the receptacle.
assert len(g["feet"]) == 4
for i, f in enumerate(g["feet"]):
    fl_, fw_ = P["feet"]
    assert abs(f.area - ((fl_ - fw_) * fw_ + math.pi * fw_ ** 2 / 4)) < 0.2
    assert s["footprint"].buffer(-1.5).contains(f) and f.distance(s["rabbet"]["print"]) >= P["rear_foot_clear"] - 0.01, i
# M6 press-fit pegs: 2 per foot, inside it (>= 1 mm of foot round each)
assert len(g["peg_holes"]) == 8 and len(g["pegs"]) == 8
for i, f in enumerate(g["feet"]):
    for h_ in g["peg_holes"][2 * i:2 * i + 2]:
        assert f.buffer(-1.0).contains(h_.buffer(P["foot_fit"])), (i, h_.centroid)  # >= 1 mm of TPU round each peg
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
    assert gr.area > 1000 and f["open"].buffer(-P["groove_wall"] + 0.01).contains(gr) and radius_ok(gr, P["pocket_r"], tol=0.1), h
    # M6 (user): the grooves run under the hotswap sockets: every socket keep-out, projected along the PCB normal
    # onto the floor plane, lies in a groove, but where it is within island_clear + R3 of an island (insert boss,
    # snap pillar) or a JST breakthrough, which the grooves keep away from
    keep = unary_union([q["poly"].buffer(P["island_clear"] + 0.01) for q in cs["islands"] if q["half"] == h] +
                       [cs["stubs"].buffer(P["island_clear"] + 0.01)])
    n_part = n_wall = 0
    for sk in d["sockets"]:
        fl = world(M, f["w"], sk)
        # (and the groove's R3 corners round those notches). M6 (user): a flat groove_wall band along every wall for
        # the snaps: a socket reaching within groove_wall + R3 of the wall is exempt (counted)
        if not f["open"].buffer(-P["groove_wall"] - P["pocket_r"]).contains(fl):
            n_wall += 1
            continue
        rest = fl.difference(keep.buffer(P["pocket_r"]))
        assert rest.is_empty or gr.buffer(1e-6).contains(rest), (h, sk.centroid, rest.difference(gr).area)
        n_part += not fl.difference(keep).equals(fl)
    sock_cover[h] = (len(d["sockets"]), n_part, n_wall)
    assert not gr.intersects(cs["stubs"].buffer(P["island_clear"] - 0.01)), h  # off the JST breakthroughs
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
pills = [q for q in cs["islands"] if q["kind"].startswith("pillar")]
for h, d in g["halves"].items():  # M6: each pillar (with its R3 wall fillets) clear of its snap's legs
    pil = unary_union([q[k_] for q in pills if q["half"] == h for k_ in ("poly", "join", "join_alt")])  # (as Fusion cuts them)
    for q in d["snaps"]:
        for l_ in q["legs"]:
            for w in L_["snap_leg"]:
                assert world(Ms[h], w, l_).distance(pil) >= 0.01, (h, q["side"], w)
assert len(pills) == 8, len(pills)  # M6: 4 per half
for q in pills:  # snap pillars: top = the half's PCB-underside plane less pillar[2] (0.2 under the snap lip)
    assert abs(q["w_top"] - (WB - P["pillar"][2])) < 1e-9 and 0.2 <= P["pillar"][2] <= 0.3  # M6: post in the notch
    assert q["z_low"] > q["z_floor"] + 0.5 and not q["poly"].intersects(cs["floor"][q["half"]]["grooves"]), q["kind"]
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

# M5: the ridge is the key-gap midpoint and the centre web is symmetric about it: each opening's nearest point
# is the same distance from the ridge, and the web is 9-10 mm at its narrowest.
assert abs(sum(g["key_gap"]) / 2 - g["ridge_x"]) < 1e-9
oL, oR = sorted(opening.geoms, key=lambda o: o.bounds[0])
dL, dR = g["ridge_x"] - oL.bounds[2], oR.bounds[0] - g["ridge_x"]
assert 9.3 <= g["web_min"] <= 10, (dL, dR, g["web_min"])  # M6 (user): ~9.5
# M6 (user): the spread is split equally: before the end runs the openings sit the same distance either side of the
# ridge; the outline centre stays +2.31 off it (accepted at M5, set by the layout, not the spread)
assert P["half_spread"][0] == P["half_spread"][1] and abs(g["web_sym"][0] - g["web_sym"][1]) < 0.05, g["web_sym"]
assert abs(g["outline_offset"] - 2.31) < 0.02, g["outline_offset"]
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
print("sockets over the floor grooves (total; partly over a boss / breakthrough; by the wall, exempt): " +
      ", ".join(f"{h} {a}; {b}; {c}" for h, (a, b, c) in sock_cover.items()))
print("air under the PCBs (mm): " + ", ".join(f"{h} {a:.2f}..{b:.2f}" for h, (a, b) in airs.items()))
print(f"ok  H_front {g['h_front']:.2f} mm, max height {g['max_height']:.2f} mm (back centre "
      f"{g['heights']['back_centre']:.2f}), outline {g['outline_size'][0]:.2f} x {g['outline_size'][1]:.2f} mm")
