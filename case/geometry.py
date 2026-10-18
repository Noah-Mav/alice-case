"""Case geometry for the Alice layout (docs/fusion-case-plan.md §3, §4, §6). All maths lives here; the
Fusion script only draws what case/out/case_geometry.json gives it.

Run:  case/.venv/bin/python case/geometry.py layouts/layout2.json
      (ALICE_WEB_MODE=straight picks the straight-centre version; default stepped)

Frames
- layout: alice.place() mm, origin top-left, y toward the user, angles clockwise degrees.
- local (per half, the plate-top plane): u = layout x, v = y_front - y (+v = back), w = plate normal, w=0 plate top.
  Key angles in local are counter-clockwise degrees (= -layout angle).
- world: X right, Y back, Z up, desk at Z=0. world = M @ (u, v, w, 1), M per half (4x4, mm).
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely import affinity, ops
from shapely.geometry import LineString, MultiPoint, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.prepared import prep
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "layout"))
import alice  # noqa: E402

P = {  # §4, decided. Edit here and re-run both scripts. M5 sleeker (user): bezels front/back
    # 8/11 -> 7/9.5, crease 10 -> 9, lower_cant 6 -> 8, panel_t 4 -> 3, floor_above_panel 3 -> 2
    "typing_angle": 6.0, "tent": 4.0,  # tent 5 -> 4: user at M4 (back wall too tall); typing 7 -> 6: user at M6
    "plate_t": 1.5, "cutout": 14.0, "cutout_print": 14.05, "plate_to_pcb": 5.0, "pcb_t": 1.6, "socket_h": 1.8,
    "floor_clear": 3.0, "lip": 2.0, "skirt_bottom_out": 1.6, "artisan_gap": 1.5, "snap_gap": 0.9, "plate_wall_gap": 1.0,
    "bezel_side": 6.0, "bezel_front": 7.0, "bezel_back": 9.5,
    "pocket_r": 3.0, "cavity_r": 6.0, "outer_r": 3.0, "top_round": 1.0, "opening_chamfer": 0.75,
    "crease_mode": "front_horizontal",  # M6 (user): the chosen design, front faces level ("deepening" = the M5 rule)
    "crease_depth": 9.0, "lower_back": 0.5,  # crease: 10 mm on the front, lower band = lower_back x height at the back centre
    "lower_cant": 8.0, "panel_t": 3.0, "rim": 6.0, "rear_strip_end": 6.0,  # M6 (user): = rim, so the back edge runs square into the side rims (was 10: an inset step at each back corner)
    # M4: the strip's lip rises up the rear face to the USB centre (CloudNine's seam runs through the port); it
    # meets the seam this far from each rear corner, is this thick at the desk (the lean adds ~0.4 mm at its top),
    # and its top edge runs down to the seam over the last 7.2 mm in a straight diagonal (1:2, ~27 deg), so seen
    # from behind the band is a trapezoid
    "strip_lip": [20.0, 2.5, 7.2],
    "strip_lip_r": 6.0,  # M5: the band's top corner (seen from behind, top edge into the diagonal), rounded
    # USB slot seen from behind: an even rounded rectangle, R3 on all four corners. Roof corners: Ø6 ball mill from
    # below, in the 3.6 mm of body above the seam; floor corners: Ø6 ball mill on the panel from its top. The slot
    # is 22 wide (bay 19) so the floor R3 clears the UDB board's rear corners (0.3 mm), which sit inside the lip.
    "usb_r": [3.0, 3.0], "usb_slot_w": 22.0,
    "panel_gap_wood_fb": 0.5, "panel_gap_wood_lr": 0.1, "panel_gap_print": 0.2,
    "ledge": 14.0, "feet": [28.0, 8.0], "foot_depth": 1.0, "foot_proud": 2.0,
    # M6 (user): removable press-fit TPU test feet: the plug in the pocket is foot_fit oversize per side. Pocket depth
    # stays 1.0: the corner screws' countersinks start at the pocket floor and need 1.66 of the 3.0 panel (2.0 deep
    # would put the heads 0.66 into the insert / rabbet ceiling)
    "foot_fit": 0.15,
    # M6 (user): two round pegs on each foot press into Ø3 x 2 holes through the panel from the pocket floor: diameter,
    # hole depth, the first peg's distance from the corner screw (>= 1 mm wall to its countersink); the second sits
    # at the foot's far round end. The pegs are foot_fit oversize per side; the pocket stays for location
    "foot_peg": [3.0, 2.0, 6.0], "usb_opening": [12.0, 7.2],  # height used; the opening is now the bay-wide slot
    # screws: 6, one at each panel corner (under the feet), mid back (shifted clear of the UDB bay), front V point
    "udb": [18.0, 16.5],            # §6.9 Unified Daughterboard C3, at the back on the ridge
    "udb_r": 2.0, "udb_holes": [14.0, 12.5], "udb_hole_d": 2.2, "udb_t": 1.6, "udb_air": 0.5,
    "usb_receptacle": [8.94, 7.35, 3.21],  # HRO TYPE-C-31-M-12 w x depth x h, on the UDB top, face at the board edge
    "usb_recess": 1.0,              # receptacle face behind the outer rear face (<= 1.5)
    "keycap_h": 7.5,                # M6: Cherry profile cap, skirt to top (~R2-R4), for the bottomed-out envelope only
    "switch_top_h": 6.6,            # MX top housing above the plate top (housing top 11.6 above the PCB top)
    "jst": [6.0, 4.2, 2.95], "jst_pocket": [8.0, 6.0],  # §6.10 JST-SH 4-pin header, free space around it
    # M6 PCBsnap (Geon x Nuxros, user approved; sizes from product photos, +-30 %, re-run with a measured one): a
    # staple. Length along the wall, reach onto the PCB (top bar and legs), centre notch between the legs; the spine
    # (thickness) stands in the PCB-to-wall gap, the top bar runs from the PCB top to snap_bar_air under the plate,
    # the end legs drop snap_drop below the PCB underside. Corner/stab distance
    "snap": [20.0, 2.5, 8.5], "snap_spine": 0.6, "snap_bar_air": 0.3, "snap_drop": 2.5, "snap_wall_air": 0.1,
    "snap_corner": 15.0, "snap_stab": 3.0, "snap_flat": 0.25,
    "screw_head": 6.72,             # ISO 10642 M3 head diameter
    "screw_clear": 3.4,             # M3 clearance hole in the panel (90° countersink to screw_head)
    "insert_hole": [4.0, 6.0],      # print: heat-set M3 x 5.7 hole, diameter and depth above the rabbet ceiling (M5: 6.5 -> 6.0)
    # M5: the two back-corner screws sit under the pocket floor; short inserts there keep >= 5 mm above them. Print:
    # M3 x 3 short heat-set (e.g. CNC Kitchen) in Ø4.0 x 4.0. Wood: a <= 4 mm long M3 insert (short knife-thread).
    "insert_hole_short": [4.0, 4.0],
    # M5: the UDB hangs upside down (components toward the panel) from the bay ceiling, 0.5 mm (udb_air) under the
    # slot roof. The front pair of holes gets body standoffs: diameter, height (= the air over the board there). The
    # rear pair sits 3 mm inside the rear face, under the slot roof: no room for an insert with a 5 mm wall, so no
    # screw there (the slot holds the receptacle end).
    "udb_mount": [6.0, 1.0],
    # M2 insert hole in each standoff, diameter x depth from the board. Print: heat-set M2 x 3 (OD ~3.6) in Ø3.2 x 4.
    # Wood: brass knife-thread M2 x 4 (OD ~3.5-4), pilot per its datasheet (~Ø3.0-3.2 x 5), test in scrap.
    "udb_insert": [3.2, 5.0],
    "stab": {"w": 6.75, "h": 14.0, "y_top": 6.0, "y_bottom": -8.0, "x": 11.938, "min_w": 2.0},
    "stack_raise": 1.5,             # M6: stack raised in the shell (= old lip 3.5 - lip); H_front rule reference below
    "floor_above_panel": 2.0,       # §4 H_front rule: pocket floor >= panel_t + this above the desk (M5: 3 -> 2)
    # PCBsnap pillars (M6: posts in the snap's centre notch, the "O-ring post" it locks onto): width along the wall
    # (its R3 wall fillets reach ~1.7 mm along the wall at the spine, inside the 7 mm notch), depth from the wall, top below the PCB underside, corner radius; cable channel height
    "relief": [7.0, 1.25],  # M6 floor relief grooves: notch diameter / 1.5 (> Ø6 tool), depth below the floor plane
    # M6 grooves under the sockets: margin round each socket keep-out, gap closing between neighbours in a row,
    # land left to the pocket wall, clearance round pillars / bosses / JST breakthroughs
    "socket_margin": 1.0, "socket_bridge": 3.0, "groove_wall": 4.0, "island_clear": 1.0,  # M6 (user): flat 4 mm band along every wall for the snap legs / posts
    "pillar": [6.0, 3.5, 0.25], "pillar_r": 1.0, "chan_h": 4.0,  # M6 (user): 6 wide, the checkpoint's 3.5 deep (capped at the snap's reach)
    # M6 (user, option A): the pillar's fillets into the wall are R1.5 (Ø3 tool; R1 / Ø2 is too long and thin for
    # hardwood ~15 mm down). The snap's notch is 8.5 so its legs clear the 6 mm post and those fillets: an estimate
    # from photos (6-8); measure a real snap, and if its notch is narrower, revisit the fillet or the post
    "pillar_fillet": 1.5,
    "cable_channel": 13.0,  # > 2 cavity_r so the R6 opening keeps it
    "lift_step": 0.5,               # H_front rounding
    "ridge_clear": 0.5,             # §6.6 PCB/plate clip at the ridge
    # M5: each half moved outward along layout x (left, right; mm) before the transforms, widening the centre web;
    # the ridge sits at the key-gap midpoint, so the web is symmetric about it (the outline centre is not: the
    # right half is ~4.6 mm wider than the left, which no x shift can change)
    "half_spread": [1.2, 1.2],
    "web_mode": os.environ.get("ALICE_WEB_MODE", "stepped"),          # M6 (user keeps both): "stepped" (centre split follows the keys) | "straight"
    "web_band": 16.0,               # M6: the web-side treatment (hull / R3 corners) this near the ridge
    "row_smooth_r": 100.0, "row_smooth_depth": 1.0,  # M6: front/back row edges, cusp fill radius (leaves >= 12 mm straight per key for the snaps) and max depth
    "stagger_r": 0.5,               # §7: outward material corners at the stagger steps
    "switch_body": 15.6,
    "bed": [256.0, 256.0],          # §7 print bed
}
# Kailh CPG151101S11 hotswap socket incl. pads, key-local layout mm (y toward the user), from the KiCad MX
# hotswap footprint (pads at (-7.085, -2.54) and (5.842, -5.08)). ponytail: approximate box, not the drawing.
SOCKET = (-8.4, -7.0, 7.2, -0.6)

# MX centre post (Ø4) sticks out below the PCB: JST keep-out. ponytail: ignores 5-pin pegs; add if PCBs use them.
POST_R = 2.0
# M6 (user): the plate/PCB/switch/keycap stack sits stack_raise higher inside an unchanged shell (lip 3.5 -> 2.0), so the
# H_front rule keeps its old reference: the floor plane floor_clear + stack_raise under the PCB underside, along the normal
FLOOR_W = -(P["plate_to_pcb"] + P["pcb_t"] + P["floor_clear"] + P["stack_raise"])
PCB_MID_W = -(P["plate_to_pcb"] + P["pcb_t"] / 2)


def matrix(sgn, ridge, lift):
    """Local -> world for one half (sgn +1 left, -1 right): tent about the ridge axis, tilt about X, lift."""
    t, a = math.radians(P["tent"]), math.radians(P["typing_angle"])
    c, s = math.cos(t), math.sin(t)
    tent = np.array([[c, 0, -sgn * s], [0, 1, 0], [sgn * s, 0, c]])  # outer edge drops
    tilt = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])  # back rises
    R = tilt @ tent
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = R @ [-ridge, 0, 0] + [ridge, 0, lift]
    return M


def z_at(M, w, X, Y):
    """Z of the local plane w=const of matrix M above world (X, Y)."""
    A = M[:2, :2]
    u, v = np.linalg.solve(A, np.array([X, Y]) - M[:2, 2] * w - M[:2, 3])
    return float(M[2] @ [u, v, w, 1])


def surface(Ms, w, X, Y):
    """Two facets meeting at the ridge (both rise toward it), so the surface is the lower of the two planes."""
    return min(z_at(M, w, X, Y) for M in Ms)


def to_local(M, w, geom):
    """World XY -> local (u, v) on the plane w: invert the affine plane -> XY projection."""
    A = M[:2, :2]
    b = M[:2, 2] * w + M[:2, 3]
    Ai = np.linalg.inv(A)
    c = -Ai @ b
    return affinity.affine_transform(geom, [Ai[0, 0], Ai[0, 1], Ai[1, 0], Ai[1, 1], c[0], c[1]])


def rnd(r, g):
    """Round convex and concave corners to r (closing, then opening)."""
    return g.buffer(r).buffer(-2 * r).buffer(r)


def key_rect(k, x0, y0, x1, y1):
    """A rectangle in key-local coords (+y = back) -> local (u, v), for a key dict of halves[h]["keys"]."""
    a = math.radians(k["ang"])
    c, s = math.cos(a), math.sin(a)
    return Polygon([(k["x"] + x * c - y * s, k["y"] + x * s + y * c) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])


def place_jst(pcb, keep, sgn):
    """§6.10: header with its long side along v and the plug entry facing the ridge, as close to the PCB's inner
    back corner as its 8 x 6 pocket fits inside the PCB and clear of the sockets and centre posts."""
    (pl, pd), (hl, hd) = P["jst_pocket"], P["jst"][:2]
    minu, minv, maxu, maxv = pcb.bounds
    corner = np.array([maxu if sgn > 0 else minu, maxv])
    inside, blocked = prep(pcb), prep(keep)
    best = None
    for du in np.arange(0, 40, 0.25):
        for dv in np.arange(0, 40, 0.25):
            c = corner + [-sgn * (du + pd / 2), -(dv + pl / 2)]
            pocket = box(c[0] - pd / 2, c[1] - pl / 2, c[0] + pd / 2, c[1] + pl / 2)
            if (best is None or math.hypot(du, dv) < best[0]) and inside.contains(pocket) and not blocked.intersects(pocket):
                best = (math.hypot(du, dv), c, pocket)
    if best is None:
        raise SystemExit("no room for the JST header near the inner back corner")
    c = best[1]
    return box(c[0] - hd / 2, c[1] - hl / 2, c[0] + hd / 2, c[1] + hl / 2), best[2]


def world(M, u, v, w):
    return tuple((M @ [u, v, w, 1])[:2])


def place_snaps(pcb, below, above, stabs, sgn):
    """§6.11: one snap on the outer end, front, back and (M5) inner end each, flush on one straight PCB edge segment (>= 1 mm from
    its ends), >= snap_corner along the edge from the outline's corners, >= snap_stab from stabilizer cutouts, clear
    of sockets and the JST pocket, as far from corners as possible.
    A corner is a net turn >= 45° between consecutive straight segments (>= 5 mm). Stagger steps (2-3 mm jogs that
    return to the same heading) and the 3° kinks of curved rows aren't corners: the outer ends are stepped per row,
    so a 15 mm rule that counted steps would leave no straight wall long enough.
    M6 staple: the spine reaches snap_spine past the PCB edge (snap_gap - snap_spine of air at mid-PCB, so the wall
    lean over its height keeps it off the wall). Its legs and the pillar in its notch (under the PCB) stay clear of
    `below` (sockets, centre posts, JST pocket); its top bar (over the PCB) clear of `above` (switch housings). Where
    the 2.5 mm reach doesn't fit, it gets shallower (2.0). ponytail: sizes from photos; re-run with a measured one."""
    L, notch = P["snap"][0], P["snap"][2]
    out_ = P["snap_spine"]
    pa0, pa1 = -(P["snap_gap"] - out_) - 1.5, P["pillar"][1] - (P["snap_gap"] - out_)  # pillar, from the outer face
    ring = list(orient(pcb).exterior.coords)[:-1]  # ccw: outward normal of edge (dx, dy) is (dy, -dx)
    n = len(ring)
    seg = [(np.array(ring[i]), np.array(ring[(i + 1) % n])) for i in range(n)]
    lens = [float(np.linalg.norm(q - p)) for p, q in seg]
    head = [math.atan2(*(q - p)[::-1]) for p, q in seg]
    start = np.concatenate([[0.0], np.cumsum(lens)[:-1]])
    total = sum(lens)
    long_ = [i for i in range(n) if lens[i] >= 5]
    # M6: a stagger step deeper than 5 mm (a turn and its opposite turn over a step < 15 mm long, back to the same
    # heading, e.g. where a straightened end run rejoins the stepped wall) is no corner either
    pairs_ = list(zip(long_, long_[1:] + long_[:1]))
    turn = [math.remainder(head[j] - head[i], math.tau) for i, j in pairs_]
    big = [abs(t_) >= math.radians(45) for t_ in turn]
    step_ = [False] * len(pairs_)
    for k_ in range(len(pairs_)):
        k2 = (k_ + 1) % len(pairs_)
        if big[k_] and big[k2] and abs(turn[k_] + turn[k2]) < math.radians(45) and lens[pairs_[k_][1]] < 15:
            step_[k_] = step_[k2] = True
    corner_s = [x for (i, j), b_, st_ in zip(pairs_, big, step_) if b_ and not st_ for x in (start[i] + lens[i], start[j])]
    cdist = lambda s: min(min(abs(s - c), total - abs(s - c)) for c in corner_s)
    dirs = {"outer": (-sgn, 0), "front": (0, -1), "back": (0, 1), "inner": (sgn, 0)}  # M5: 4 per half
    # M6: a 20 mm staple spans more than one straight segment of the R100-smoothed row edges: any stretch of edge
    # within snap_flat of its chord will do; the outer face sits snap_spine past the edge's outermost point there
    ext_ = LineString(ring + ring[:1])
    def spots(L, end=False):
        out = []
        for s_ in np.arange(L / 2, total - L / 2, 0.5):
            pa, pb = (np.array(ext_.interpolate(x).coords[0]) for x in (s_ - L / 2, s_ + L / 2))
            t = (pb - pa) / np.linalg.norm(pb - pa)
            if end:  # (an end snap: lined up with the longest row end it spans, which it sits on)
                ov = [(min(start[i] + lens[i], s_ + L / 2) - max(start[i], s_ - L / 2), i) for i in range(n)]
                i_ = max(ov)[1]
                t = (seg[i_][1] - seg[i_][0]) / lens[i_]
            nrm = np.array([t[1], -t[0]])
            xs_ = list(np.arange(s_ - L / 2, s_ + L / 2 + 1e-9, 0.25))
            dev = [(np.array(ext_.interpolate(x).coords[0]) - pa) @ nrm for x in xs_ +
                   [x for x in start if s_ - L / 2 < x < s_ + L / 2]]  # (the vertices too: the outermost point exactly)
            top = max(dev)
            mid = (pa + pb) / 2
            m_ = mid + nrm * (top - (mid - pa) @ nrm)
            if max(dev) - min(dev) <= P["snap_flat"]:
                out.append((s_, m_, t, nrm))
        return out
    best = {}
    wall_ = pcb.buffer(P["snap_gap"] - 0.1, quad_segs=16)  # (the whole part clear of the wall at mid-PCB, corners included)
    # M6 (user): 4 per half, all the full part: 2 on the front edge and 2 on the back, each as close to one of the
    # half's 4 corners as the corner rule (snap_corner, else 10, 5), sockets and stabs allow; none on the ends
    for cmin in (P["snap_corner"], 10.0, 5.0):
        for D in (out_ + P["snap"][1], out_ + 2.0):
            cands = {}
            for s_, m, t, nrm in spots(L):
                side = next((k for k, d in dirs.items() if nrm @ d >= 0.7), None)
                if side not in ("front", "back"):
                    continue
                cd = min(cdist(s_ - L / 2), cdist(s_ + L / 2))
                if cd < cmin:
                    continue
                rr = lambda s0, s1, a0, a1: Polygon([m + t * s0 + nrm * (out_ - a0), m + t * s1 + nrm * (out_ - a0),
                                                     m + t * s1 + nrm * (out_ - a1), m + t * s0 + nrm * (out_ - a1)])
                poly = rr(-L / 2, L / 2, 0, D)
                legs = [rr(-L / 2, -notch / 2, 0, D), rr(notch / 2, L / 2, 0, D)]
                post = rr(-P["pillar"][0] / 2, P["pillar"][0] / 2, pa0, min(pa1, D))
                if not poly.within(wall_) or poly.intersects(above) or any(q_.intersects(below) for q_ in legs + [post]) or \
                        (not stabs.is_empty and poly.distance(stabs) < P["snap_stab"]):
                    continue
                cands.setdefault(side, []).append({"side": side, "poly": poly, "legs": legs, "spine": rr(-L / 2, L / 2, 0, out_),
                                                   "corner_dist": round(cd, 3), "depth": D, "u": m[0], "length": L,
                                                   "post_depth": min(pa1, D) + P["snap_gap"] - out_})
            for side, cs_ in cands.items():
                for k, sg in ((side, -1), (side + "2", 1)):  # the one nearest the -u corner, then the +u one
                    if k in best:
                        continue
                    ok_ = [c_ for c_ in cs_ if all(abs(c_["u"] - b_["u"]) >= L + 5 for b_ in best.values()
                                                   if b_["side"].rstrip("2") == side)]
                    if ok_:
                        best[k] = dict(max(ok_, key=lambda c_: sg * c_["u"]), side=k)
    dirs = {"front": 0, "front2": 0, "back": 0, "back2": 0}
    if len(best) != len(dirs):
        raise SystemExit(f"no PCBsnap spot for {set(dirs) - set(best)}")
    for v in best.values():
        v.pop("u")
        a_, b_ = list(v["poly"].exterior.coords)[:2]
        mid = pcb.exterior.interpolate(pcb.exterior.project(Point((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)))
        v["edge_mid"] = [mid.x, mid.y]  # the PCB edge point under the snap's middle (the Fusion gap check)
    return [best[k] for k in dirs]


def coords(g):
    """A polygon's outline as [[x, y], ...]; a MultiPolygon as a list of those."""
    if g.geom_type == "MultiPolygon":
        return [coords(p) for p in g.geoms]
    assert g.geom_type == "Polygon" and not g.interiors, g.geom_type
    return [[round(x, 4), round(y, 4)] for x, y in g.exterior.coords[:-1]]


def build(lay):
    """The ridge (tent fold) is the key-gap midpoint, after half_spread moves the halves apart (M5): the centre
    web is symmetric about it. The outline is not centred on it (see half_spread)."""
    g = _build(lay)
    lo, hi = g["key_gap"]
    if hi - lo < 4:
        raise SystemExit(f"key gap {lo:.2f} .. {hi:.2f} too narrow: the ridge needs >= 2 mm to each half")
    ox0, _, ox1, _ = g["_shapes"]["outline_sharp"].bounds
    g["outline_offset"] = (ox0 + ox1) / 2 - g["ridge_x"]
    return g


def _build(lay):
    placed = alice.place(lay)
    if hits := alice.collisions(placed):
        raise SystemExit(f"refusing to build: {len(hits)} overlapping key pairs, e.g. {hits[:3]}")
    for o in placed:  # M5 half_spread: alice's dicts, moved in place (the layout itself is untouched)
        o["x"] += -P["half_spread"][0] if o["half"] == "left" else P["half_spread"][1]
    caps = alice.keycaps(placed)
    pts = {h: [p for o in alice.solid(placed) if o["half"] == h for p in alice.footprint(o)] for h in ("left", "right")}
    key_gap = (max(p[0] for p in pts["left"]), min(p[0] for p in pts["right"]))
    ridge = sum(key_gap) / 2
    y_front = max(p[1] for q in pts.values() for p in q)
    flip = lambda xy: (xy[0], y_front - xy[1])  # layout -> local (u, v)

    M0 = {"left": matrix(1, ridge, 0.0), "right": matrix(-1, ridge, 0.0)}
    world = lambda M, u, v, w: tuple((M @ [u, v, w, 1])[:2])

    # §6.1 key envelopes: footprint box from skirt-at-bottom-out to the bezel top, projected to plan
    env = [MultiPoint([world(M0[o["half"]], *flip(c), w) for c in alice.footprint(o)
                       for w in (P["skirt_bottom_out"], P["lip"])]).convex_hull for o in caps]
    # §6.2 opening, plus §7's R0.5 on the outward material corners (closing only ever enlarges the opening)
    opening = unary_union(env).buffer(-1.5).buffer(1.5 + P["artisan_gap"])
    opening = opening.buffer(P["stagger_r"]).buffer(-P["stagger_r"])
    # drop the sub-micron segments the buffers leave (Fusion cannot chamfer/fillet them); edges move <= 4 um, outward
    # M6 (user): along the front and back of each row the per-key envelopes leave shallow cusps between neighbouring
    # keys (the 3.25 deg curve and small stagger steps), so the edge zig-zags. Fill just those (a closing: shallow,
    # wider than tall; it only grows the opening and stays inside its convex hull, so clearances and bezels hold)
    # with a large radius, so each row edge reads as one gentle arc. Web, outer ends and big stagger steps untouched.
    R_ = P["row_smooth_r"]
    fills = []
    for o_ in getattr(opening, "geoms", [opening]):
        cl = o_.buffer(R_, quad_segs=64).buffer(-R_, quad_segs=64)
        add = cl.difference(o_)
        for q in getattr(add, "geoms", [add]):
            x0_, y0_, x1_, y1_ = q.bounds
            if q.area > 1e-3 and x1_ - x0_ >= 2 * (y1_ - y0_) and \
                    max(o_.exterior.distance(Point(c)) for c in q.exterior.coords) <= P["row_smooth_depth"]:
                fills.append(cl.intersection(q.buffer(0.5)))  # the closed edge itself, past the joins: no jog there
    # M6 web_mode (user keeps both): "straight": each web-side edge is the convex hull of the opening within web_band
    # of the ridge (straight runs from row end to row end, the rows' own R3 corners, R3 where a run meets the row
    # edges). "stepped": the edges follow their keys' envelopes (the centre split, stagger steps kept); their small
    # R0.5 corners (the S-jog / lobes) become R3 like the rest (an R3 closing within web_band: only grows the opening)
    if P["web_mode"] == "straight":
        for o_ in getattr(opening, "geoms", [opening]):
            band = o_.intersection(box(ridge - P["web_band"], -1e3, ridge + P["web_band"], 1e3))
            add = band.convex_hull.difference(o_)
            fills += [q for q in getattr(add, "geoms", [add]) if q.area > 1e-3]
    elif P["web_mode"] != "stepped":
        raise SystemExit(f"web_mode {P['web_mode']!r}: 'stepped' or 'straight'")
    opening = unary_union([opening] + fills)
    fills = []
    for o_ in getattr(opening, "geoms", [opening]):
        cl = o_.buffer(P["pocket_r"], quad_segs=16).buffer(-P["pocket_r"], quad_segs=16)
        add = cl.difference(o_)
        if P["web_mode"] == "straight":
            add = add.intersection(box(ridge - P["web_band"] - 4, -1e3, ridge + P["web_band"] + 4, 1e3))
            fills += [cl.intersection(q.buffer(0.5)) for q in getattr(add, "geoms", [add]) if q.area > 1e-4]
        else:
            fills += [cl.intersection(q.buffer(0.5)) for q in getattr(add, "geoms", [add])
                      if q.area > 1e-4 and abs(q.centroid.x - ridge) <= P["web_band"]]
    opening = unary_union([opening] + fills)
    oo_ = sorted(getattr(opening, "geoms", [opening]), key=lambda o: o.bounds[0])
    web_sym = [ridge - oo_[0].bounds[2], oo_[-1].bounds[0] - ridge]  # (symmetric about the ridge)
    opening = opening.simplify(0.002).buffer(0.002, join_style="mitre")  # then out again: still holds the original
    # M6: a 0.005 mm jog where two back-row envelopes meet left a hairline wall face: drop sub-0.01 segments, then
    # out 0.005 so every envelope keeps its clearance
    opening = shapely.remove_repeated_points(opening, 0.01).buffer(0.005, join_style="mitre")
    # §6.2 expects one merged opening (halves "about 4.8 mm apart"), but that 4.8 compares different rows; when
    # the halves are further apart the web between them stays (min width reported as web_min)
    web_min = opening.geoms[0].distance(opening.geoms[1]) if opening.geom_type == "MultiPolygon" else 0.0

    # §6.3 outline: alice.frame()'s 5 edge directions, each pushed to the opening's support line + bezel
    fr = alice.frame(placed, 8.0)[0]
    if len(fr) != 5:
        raise SystemExit("alice.frame() didn't give the 5-corner Alice outline for this layout")
    fr = [flip(p) for p in fr]  # lt, rt, rb, v, lb (world-handed now: clockwise)
    bezel = [P["bezel_back"], P["bezel_side"], P["bezel_front"], P["bezel_front"], P["bezel_side"]]
    op = [p for g in getattr(opening, "geoms", [opening]) for p in g.exterior.coords]

    def corners(bezel):
        lines = []
        for i, b in enumerate(bezel):
            (x1, y1), (x2, y2) = fr[i], fr[(i + 1) % 5]
            n = np.array([-(y2 - y1), x2 - x1]) / math.hypot(x2 - x1, y2 - y1)  # outward: the ring is clockwise
            d = max(n @ p for p in op) + b
            p0 = n * d
            lines.append((tuple(p0), tuple(p0 + [-n[1], n[0]])))
        return [alice._meet(*lines[i - 1], *lines[i]) for i in range(5)]  # lt, rt, rb, v, lb, as fr

    sharp = corners(bezel)
    # M6 (user): the V's inner corner sits on the ridge. One front edge moves out (its bezel grows by d, the other
    # stays bezel_front), d found by bisection; the side that needs the smaller d is used
    v_off0 = sharp[3][0] - ridge
    best_ = None
    for i_ in (2, 3):  # bezel[2]: right front edge (rb -> v), bezel[3]: left front edge (v -> lb)
        f_ = lambda d_: corners([b + (d_ if k == i_ else 0) for k, b in enumerate(bezel)])[3][0] - ridge
        if f_(0) * f_(6) < 0:
            lo_, hi_ = 0.0, 6.0
            for _ in range(60):
                mid_ = (lo_ + hi_) / 2
                lo_, hi_ = (mid_, hi_) if f_(lo_) * f_(mid_) > 0 else (lo_, mid_)
            if best_ is None or hi_ < best_[1]:
                best_ = (i_, hi_)
    if best_:
        bezel[best_[0]] += best_[1]
        sharp = corners(bezel)
    front_bezels = (bezel[3], bezel[2])  # left, right
    outline_sharp = Polygon(sharp)
    outline = rnd(P["outer_r"], outline_sharp)

    # H_front: smallest lift (rounded up) putting the pocket floor >= panel_t + 3 above the desk everywhere
    need = P["panel_t"] + P["floor_above_panel"]
    low = min(surface(M0.values(), FLOOR_W, x, y) for g_ in getattr(opening, "geoms", [opening]) for x, y in g_.exterior.coords)
    lift = math.ceil((need - low) / P["lift_step"] - 1e-9) * P["lift_step"]
    Ms = {"left": matrix(1, ridge, lift), "right": matrix(-1, ridge, lift)}
    top = lambda x, y: surface(Ms.values(), P["lip"], x, y)
    lt, rt, rb, v, lb = sharp
    back_mid = (ridge, lt[1] + (rt[1] - lt[1]) * (ridge - lt[0]) / (rt[0] - lt[0]))
    heights = {"front_left": top(*lb), "front_right": top(*rb), "front_v": top(*v),
               "back_left": top(*lt), "back_right": top(*rt), "back_centre": top(*back_mid)}

    # §6.8 lower band -> §6.7 bottom footprint: every outline edge (split at the ridge) gets a plane hinged on
    # its crease and leaning in; where that plane meets the desk is the footprint edge
    on_ridge = lambda a, b: [(ridge, a[1] + (b[1] - a[1]) * (ridge - a[0]) / (b[0] - a[0]))]
    # the V tip may sit off the ridge: split the front edge that crosses it
    ring = [lt, back_mid, rt, rb] + (on_ridge(rb, v) if v[0] < ridge - 1e-6 else []) + [v] + \
        (on_ridge(v, lb) if v[0] > ridge + 1e-6 else []) + [lb]
    phi = math.radians(P["lower_cant"])
    # crease depth below the top edge, per ring vertex: crease_depth on the front vertices, one deeper value on the
    # back ones (so the lower band at the back centre is lower_back of its height), and along each edge the crease
    # runs straight between its vertices (on the ends the depth grows linearly front to back). Straight creases keep
    # every lower-band face planar.
    back_depth = heights["back_centre"] * (1 - P["lower_back"])
    depth = [back_depth if p in (lt, back_mid, rt) else P["crease_depth"] for p in ring]
    if P["crease_mode"] == "front_horizontal":  # M6 trial (user): on the two front faces the crease is level, at
        # the outer front corners' crease height (their mean: the corners differ by 0.4 mm, and both faces must meet at
        # one height at the V); the ends and the back keep the deepening rule from those corners
        z_f = (heights["front_left"] + heights["front_right"]) / 2 - P["crease_depth"]
        depth = [d_ if p in (lt, back_mid, rt) else top(*p) - z_f for p, d_ in zip(ring, depth)]
    else:
        assert P["crease_mode"] == "deepening", P["crease_mode"]
    crease = [np.array([*p, top(*p) - dd]) for p, dd in zip(ring, depth)]
    desk, lean_n = [], []
    for i in range(len(ring)):
        c0, c1 = crease[i], crease[(i + 1) % len(ring)]
        t = (c1 - c0) / np.linalg.norm(c1 - c0)
        n = np.array([-t[1], t[0], 0.0]) / math.hypot(t[0], t[1])  # outward, clockwise ring
        d = np.array([0, 0, -1.0]) + t[2] * t
        d /= np.linalg.norm(d)
        d = math.cos(phi) * d - math.sin(phi) * n  # hinge the wall in by lower_cant
        N = np.cross(t, d)
        lean_n.append(N / np.linalg.norm(N) * np.sign(N @ n))  # the lean plane's outward normal
        q0, q1 = (c - c[2] / d[2] * d for c in (c0, c1))
        desk.append((tuple(q0[:2]), tuple(q1[:2])))
    # (two collinear edges, e.g. the back's two halves under a horizontal crease, meet anywhere on their common desk
    # line: take the vertex's own point on it)
    foot_pts = [alice._meet(*desk[i - 1], *desk[i]) or desk[i][0] for i in range(len(desk))]
    footprint = Polygon(foot_pts)
    # for Fusion (M4): per ring vertex the crease point and the footprint point (the two lean planes meet on that
    # line), per edge the lean plane's outward normal (the plane holds the crease)
    lower_band = {"crease": [c.tolist() for c in crease], "depth": depth, "foot": foot_pts,
                  "normals": [N.tolist() for N in lean_n]}

    # §6.7 panel: footprint inset by rim, except a strip out to the rear face between the strip ends
    back = LineString([foot_pts[0], foot_pts[1], foot_pts[2]])  # back-left, ridge, back-right
    strip = ops.substring(back, P["rear_strip_end"], back.length - P["rear_strip_end"])
    raw = footprint.buffer(-P["rim"], join_style="mitre").union(strip.buffer(P["rim"] + 1, cap_style="flat"))
    panel = rnd(P["pocket_r"], raw).intersection(footprint)
    # Fusion: the strip and its rabbet run 1 mm past the footprint and are trimmed by the rear lean planes, so the
    # strip's rear face continues the lower band (no knife-edge of body behind it)
    panel_lean = rnd(P["pocket_r"], raw).intersection(footprint.buffer(1.0, join_style="mitre"))
    rabbet_lean = panel_lean.buffer(P["panel_gap_print"]).intersection(footprint.buffer(1.2, join_style="mitre"))
    rabbet = {"print": panel.buffer(P["panel_gap_print"]).intersection(footprint),
              "wood": affinity.scale(affinity.scale(panel, 1, P["panel_gap_wood_lr"] / P["panel_gap_wood_fb"], origin=(0, 0))
                                     .buffer(P["panel_gap_wood_lr"]), 1, P["panel_gap_wood_fb"] / P["panel_gap_wood_lr"],
                                     origin=(0, 0)).intersection(footprint)}
    cavity = panel.buffer(-P["ledge"] - P["cavity_r"]).buffer(P["cavity_r"])

    # §6.9 UDB (M5: upside down from the body): centred on the ridge, back face udb_air under the slot roof,
    # receptacle (now under the board) face usb_recess behind the
    # rear face. ponytail: rear face = footprint back point at the ridge leaning out by tan(cant); M3 measures it.
    (bw, bd), (rw, rd, rh), r = P["udb"], P["usb_receptacle"], P["udb_r"]
    z_top = P["panel_t"] + P["usb_opening"][1] - P["udb_air"]  # the board's back (non-component) face, up
    z_rx = z_top - P["udb_t"] - rh / 2
    udb_c = (ridge, foot_pts[1][1] + z_rx * math.tan(phi) - P["usb_recess"] - bd / 2)
    udb_board = box(udb_c[0] - bw / 2, udb_c[1] - bd / 2, udb_c[0] + bw / 2, udb_c[1] + bd / 2)
    udb_keep = udb_board.buffer(0.5 + P["screw_head"] / 2, join_style="mitre")  # bay (UDB + 0.5) plus the head
    hx, hy = P["udb_holes"][0] / 2, P["udb_holes"][1] / 2
    # flipped about its own Y axis: local z = 0 (the back face) at z_top, the components toward -z
    udb = {"matrix": [[-1, 0, 0, udb_c[0]], [0, 1, 0, udb_c[1]], [0, 0, -1, z_top], [0, 0, 0, 1]],
           "board": box(-bw / 2 + r, -bd / 2 + r, bw / 2 - r, bd / 2 - r).buffer(r), "board_z": [0.0, P["udb_t"]],
           "holes": [Point(x, y).buffer(P["udb_hole_d"] / 2) for x in (-hx, hx) for y in (-hy, hy)],
           "receptacle": box(-rw / 2, bd / 2 - rd, rw / 2, bd / 2), "receptacle_z": [P["udb_t"], P["udb_t"] + rh],
           "receptacle_centre_z": z_rx, "board_top_z": z_top,
           # the front pair of holes (world), each with a standoff from the ceiling down to the board
           "mounts": [[udb_c[0] + x, udb_c[1] - hy] for x in (-hx, hx)],
           "mount_z": [z_top, z_top + P["udb_mount"][1]]}

    # screws, on the ledge's centre line: the 4 panel corners (under the feet), the front V point, and the middle
    # of the back moved along the line just far enough to clear the UDB bay
    path = panel.buffer(-P["ledge"] / 2).exterior
    at = lambda i: path.project(Point(foot_pts[i]))
    screws = [path.interpolate(at(i)) for i in (0, 2, 3, len(foot_pts) - 1, ring.index(v))]  # bl, br, fr, fl, V
    for d in np.arange(0, 60, 0.05):
        q = [q for sg in (-1, 1) if not udb_keep.intersects(q := path.interpolate((at(1) + sg * d) % path.length))]
        if q:
            screws.append(q[0])
            udb["back_screw_shift"] = round(q[0].x - ridge, 3)
            break

    # M4 rear lip: the panel strip rises up the rear face (z panel_t .. USB centre) as a visible band, the body cut
    # back to match (lip + print gap). It ends lip_end from the corners. M5 DFM: the body's lip pocket (cut from below)
    # had R1 inner corners (Ø2 tool); it now runs 4 mm out past the rear face (air) so it is >= 2 pocket_r wide and
    # takes an R3 opening: Ø6 from below. The lip is the pocket less the gap, so its inner end corners are R2.8.
    lip_end, lip_d, _ = P["strip_lip"]
    lip_top = P["panel_t"] + P["usb_opening"][1] / 2
    lip_line = ops.substring(back, lip_end, back.length - lip_end)
    band = lip_line.buffer(10, cap_style="flat")
    band_x = ops.substring(back, lip_end - 4, back.length - lip_end + 4).buffer(10, cap_style="flat")
    raw_pocket = band_x.intersection(footprint.buffer(4.0, join_style="mitre")).difference(
        footprint.buffer(-lip_d - P["panel_gap_print"], join_style="mitre"))
    lip_pocket = raw_pocket.buffer(-P["pocket_r"], quad_segs=16).buffer(P["pocket_r"], quad_segs=16).simplify(0.002)
    # lip and pocket run 4 mm past each end in plan (their R3 / R2.8 corners out of the way): the band's end is the
    # diagonal alone (a plan end at the seam point left a 0.2 mm notch in the end line). The pocket starts at the
    # seam (z panel_t), so below it the rabbet alone is the void.
    lip = band_x.intersection(footprint.buffer(4.0, join_style="mitre")).difference(
        footprint.buffer(-lip_d, join_style="mitre")).buffer(-P["pocket_r"] + P["panel_gap_print"], quad_segs=16).buffer(
        P["pocket_r"] - P["panel_gap_print"], quad_segs=16).intersection(footprint.buffer(1.0, join_style="mitre"))
    # M5 band ends, one diagonal from the band top to the desk (Fusion's lip_ramps): it trims the panel's rear run-out
    # inside rear_zone_panel and the body's rabbet / lip pocket inside rear_zone_body, which starts gap further out
    # (the hidden step where the trimmed run-out meets the full panel keeps its gap; the corner rabbet is untouched)
    rear = LineString([foot_pts[0], foot_pts[1], foot_pts[2]]).buffer(P["rim"] + 4, cap_style="flat")
    rear_zone = {k: rear.difference(footprint.buffer(-P["rim"] + o, join_style="mitre"))
                 for k, o in (("panel", 0.3), ("body", 0.3 + P["panel_gap_print"]))}
    ir = P["insert_hole"][0] / 2
    # M6: with the panel's back edge square into the side rims, the back-corner screws sit nearer the lip pocket:
    # each moves along the ledge line (toward the front) until its insert is 5 mm clear of it
    for i in (0, 1):
        q0, dy = screws[i], 0.0
        while lip_pocket.distance(screws[i]) < 5.0 + ir:
            dy += 0.05
            screws[i] = path.interpolate(path.project(Point(q0.x, q0.y - dy)))  # (straight forward, kept on the ledge line)
    # the back screw's insert would sit 2.5 mm from the lip pocket: move it straight in (-y) until 5 mm clear, and
    # leave a boss for it in the cavity (5 mm round the hole, cavity corners stay cavity_r)
    ir = P["insert_hole"][0] / 2
    q = screws[5]
    dy = 0.0
    while lip_pocket.distance(Point(q.x, q.y - dy)) < 5.0 + ir:
        dy += 0.01
    screws[5] = Point(q.x, q.y - dy)
    udb["back_screw_inward"] = round(dy, 2)
    cavity = cavity.difference(screws[5].buffer(ir + 5.05))  # +0.05: the buffered circle is a polygon
    cavity = cavity.buffer(-P["cavity_r"]).buffer(P["cavity_r"])

    # §6.9 UDB bay (UDB + 0.5, corners rounded to pocket_r), cut from below to the standoff tops, its back edge 5 mm inside
    # the (M4, leaning) rear face at the slot top. Behind it the slot: bay-wide, open to the bottom, through the rear
    # face, its top usb_opening[1] above the panel seam. It is the USB opening and clears the board's rear edge.
    uw, uh = P["usb_opening"]
    bay_full = rnd(P["pocket_r"], udb_board.buffer(0.5, join_style="mitre"))
    # 5 mm measured square to the back-left lean plane (edge 0, from lt), at the ridge, at the slot top
    zt, c0, N0 = P["panel_t"] + uh, lower_band["crease"][0], lean_n[0]
    wall_y = c0[1] + (-5.0 - N0[0] * (ridge - c0[0]) - N0[2] * (zt - c0[2])) / N0[1]
    wall_y = min(wall_y, back_mid[1] - 5.0)  # M6: above the crease the rear face is the upright band
    bx0, by0, bx1, _ = bay_full.bounds
    bay = rnd(P["pocket_r"], bay_full.intersection(box(bx0 - 1, by0 - 1, bx1 + 1, wall_y)))
    sw = max(P["usb_slot_w"], bx1 - bx0) / 2
    # wider than the bay: round its inner end in plan (pocket_r) so the Ø6 cutter from below can make it
    notch = box(ridge - sw, wall_y - P["pocket_r"], ridge + sw, back_mid[1] + 5 + P["pocket_r"]).buffer(
        -P["pocket_r"], quad_segs=16).buffer(P["pocket_r"], quad_segs=16)
    usb_centre_z = P["panel_t"] + uh / 2
    # M5 UDB rest pad: the slot roof comes down to the board's back face over the board's rear edge (behind the bay,
    # 0.25 mm short of the edge), so plugging the USB can't flex the board. Across, it stops where the Ø6 ball for
    # the roof's R3 corners (axis usb_slot_w / 2 - usb_r from the ridge) would cut it; Fusion trims it to that ball.
    udb["pad"] = {"x": [ridge - (sw - P["usb_r"][0]), ridge + (sw - P["usb_r"][0])],
                  "y": [wall_y + 0.3, udb_c[1] + bd / 2 - 0.25], "z": [z_top, P["panel_t"] + uh + 0.05]}

    # feet (28 x 8 stadium bars, round ends = the pocket's tool radius): along the adjacent front/back edge, the
    # outer end's centre on the corner screw, so the bar covers the head (radius 3.36 < 4) and stays on the panel
    fl_, fw_ = P["feet"]
    feet, feet_pegs = [], []
    for i, (q, toward) in enumerate(zip(screws[:4], (foot_pts[1], foot_pts[1], v, v))):  # bl, br, fr, fl
        t = np.subtract(toward, foot_pts[(0, 2, 3, len(foot_pts) - 1)[i]])
        t = t / np.linalg.norm(t)
        a = np.array([q.x, q.y])
        feet.append(LineString([a, a + t * (fl_ - fw_)]).buffer(fw_ / 2, quad_segs=16))
        feet_pegs.extend(Point(*(a + t * u_)) for u_ in (P["foot_peg"][2], fl_ - fw_))

    # wall thickness in plan (M4's lower band leans in, so the desk-level footprint is the outer face at z = 0)
    rab = rabbet["print"]
    walls = {"bezel": min(outline.exterior.distance(o) for o in getattr(opening, "geoms", [opening])), "web": web_min,
             "cavity_to_footprint": footprint.exterior.distance(cavity),
             # front and sides (the back is the strip, open to the rear by design)
             "rabbet_to_footprint": LineString(foot_pts[2:] + foot_pts[:1]).distance(rab),
             "insert_to_cavity": min(cavity.exterior.distance(q) for q in screws) - P["insert_hole"][0] / 2,
             # bay back edge to the rear face above the slot: at M3 the face is vertical (outline); at M4 it
             # leans in and is thinnest at the slot top
             "bay_rear_m3": back_mid[1] - bay.bounds[3],
             "bay_rear_m4": -float(N0 @ np.subtract([ridge, bay.bounds[3], zt], c0)),
             "insert_to_lip": min(lip_pocket.distance(q) for q in screws) - P["insert_hole"][0] / 2,
             "cavity_to_lip": cavity.distance(lip_pocket)}

    # §6.6 PCB and plate outlines, per half, in local coordinates (inset in plan, each at its own mid-height, so
    # the wall gap is exact there), plus the M2 flat parts drawn on them
    pt, top_w = P["plate_t"], -P["plate_to_pcb"]
    bot_w = top_w - P["pcb_t"]
    layers = {"plate": [-pt, 0.0], "pcb": [bot_w, top_w], "switch_bottom": [top_w, 0.0],
              "switch_top": [0.0, P["switch_top_h"]], "keycap": [P["skirt_bottom_out"], P["skirt_bottom_out"] + P["keycap_h"]],
              "socket": [bot_w - P["socket_h"], bot_w], "jst": [bot_w - P["jst"][2], bot_w],
              "snap_bar": [top_w, -pt - P["snap_bar_air"]], "snap_spine": [bot_w, top_w], "snap_leg": [bot_w - P["snap_drop"], bot_w]}
    st, c, hw, U = P["stab"], P["cutout"] / 2, P["switch_body"] / 2, alice.U
    halves = {}
    for h, sgn in (("left", 1), ("right", -1)):
        M = Ms[h]
        side = box(-1e4, -1e4, ridge - P["ridge_clear"], 1e4) if sgn > 0 else box(ridge + P["ridge_clear"], -1e4, 1e4, 1e4)
        cut = lambda gap, w: to_local(M, w, opening.buffer(-gap).intersection(side))
        pcb, plate = cut(P["snap_gap"], PCB_MID_W), cut(P["plate_wall_gap"], -pt / 2)
        keys = [{"label": o["key"]["label"], "x": round(o["x"], 4), "y": round(y_front - o["y"], 4),
                 "ang": round(-o["ang"], 4), "w": o["key"]["w"]} for o in caps if o["half"] == h]
        blockers = [[list(map(lambda c: round(c, 4), flip(c))) for c in alice.footprint(o)]
                    for o in alice.solid(placed) if o["half"] == h and o["key"].get("blocker")]
        stabs = [key_rect(k, x - st["w"] / 2, st["y_bottom"], x + st["w"] / 2, st["y_top"])
                 for k in keys if k["w"] >= st["min_w"] for x in (-st["x"], st["x"])]
        x0, y0, x1, y1 = SOCKET  # y toward the user -> flip
        sockets = [key_rect(k, x0, -y1, x1, -y0) for k in keys]
        posts = [Point(k["x"], k["y"]).buffer(POST_R) for k in keys]
        jst, pocket = place_jst(pcb, unary_union(sockets + posts), sgn)
        corners3 = [M @ [x, y, w, 1] for x, y in plate.exterior.coords for w in (-pt, 0.0)]
        snaps = place_snaps(pcb, unary_union(sockets + posts + [pocket]),
                            unary_union([key_rect(k, -c, -c, c, c) for k in keys]), unary_union(stabs), sgn)
        # M6: the walls are vertical, the staple stands on the tilted PCB, so over its 7.3 mm height the gap runs
        # ~0.4 .. 1.4 mm: each part is trimmed to stay snap_wall_air off the wall at both ends of its layer (where it
        # would touch, the real silicone part is compressed against the wall)
        inner = lambda w: to_local(M, w, opening.buffer(-P["snap_wall_air"]).intersection(side))
        clip = lambda g_, lay: g_.intersection(inner(layers[lay][0])).intersection(inner(layers[lay][1]))
        for q in snaps:
            q["bar"], q["spine"] = clip(q["poly"], "snap_bar"), clip(q["spine"], "snap_spine")
            q["legs"] = [clip(l_, "snap_leg") for l_ in q["legs"]]
        halves[h] = {"matrix": M.tolist(), "keys": keys, "blockers": blockers, "pcb": pcb, "plate": plate,
                     "cutouts": [key_rect(k, -c, -c, c, c) for k in keys], "stabs": stabs,
                     "switches": [key_rect(k, -hw, -hw, hw, hw) for k in keys], "sockets": sockets,
                     # 0.05 mm shy of the grid per side so neighbours share no faces in Fusion (the opening uses
                     # the full §6.1 envelopes)
                     "keycaps": [key_rect(k, -k["w"] * U / 2 + .05, -U / 2 + .05, k["w"] * U / 2 - .05, U / 2 - .05)
                                 for k in keys],
                     "jst": jst, "jst_pocket": pocket,
                     "snaps": snaps,
                     "plate_bbox_world": [round(f(q[i] for q in corners3), 4) for f in (min, max) for i in range(3)]}

    # M5/M6 solid body. The pocket floor (op 2, from the top) is one plane per half parallel to its PCB with shallow
    # relief grooves between the rows (below). Islands stand up from it: a pillar under each PCBsnap (its top
    # pillar[2] under the PCB underside, i.e. just under the snap's lower lip, parallel to the PCB) and a boss over
    # each insert that lies under a pocket (>= 5 mm of material over it). Underneath, the body is solid but for
    # the UDB bay and a cable channel per half (JST -> bay, cable_channel wide, chan_h tall), joined to the pocket by
    # a breakthrough round each JST plug pocket.
    wb = -(P["plate_to_pcb"] + P["pcb_t"])
    z_base = P["panel_t"] + P["floor_above_panel"]
    r3 = P["pocket_r"]
    def zp_above(M, cz):  # {PCB underside z >= cz} for one half: a half-plane
        f = lambda x, y: z_at(M, wb, x, y)
        a, b, c0 = f(1, 0) - f(0, 0), f(0, 1) - f(0, 0), f(0, 0) - cz
        n = math.hypot(a, b)
        o, t, u = np.array([a, b]) * -c0 / n ** 2, np.array([-b, a]) / n, np.array([a, b]) / n
        return Polygon([o - 1e3 * t, o + 1e3 * t, o + 1e3 * t + 1e3 * u, o - 1e3 * t + 1e3 * u])
    opn3 = lambda r_: r_.buffer(-r3, quad_segs=16).buffer(r3, quad_segs=16)
    # drop the ~1e-11 mm segments the booleans leave (they trip Fusion's kernel), keeping every real vertex (a
    # simplify would move the walls a few um off the pocket's own, leaving slivers)
    dedup = lambda g_: shapely.remove_repeated_points(g_, 1e-4)
    def merge(raw, region, r_=r3):  # an island in region with R3 fillets where it meets the walls (its own corners kept)
        air = region.difference(raw).buffer(-r_, quad_segs=16).buffer(r_, quad_segs=16)
        m_ = region.difference(air).intersection(raw.buffer(r_ + 1))
        return max(getattr(m_, "geoms", [m_]), key=lambda q: q.intersection(raw).area)
    opens_h = dict(zip(("left", "right"), sorted(getattr(opening, "geoms", [opening]), key=lambda o: o.bounds[0])))
    # M6 build order (kernel-friendly, no coincident walls): per half one void tool = the opening prism from the
    # lowest level up, less each raised terrace and each island, every one of them run 0.5 mm into the pocket wall;
    # the body is then cut once by that void
    wallrun = lambda q, o_: dedup(q.buffer(0).union(q.buffer(0.5).difference(o_)).buffer(0))
    # M6 (user, Neo65-style photo): each half's floor is one plane parallel to its PCB, FLOOR_W along the normal
    # (the H_front rule plane: floor_clear + stack_raise = 4.5 mm of air under the PCB everywhere), with shallow
    # relief grooves (relief[1] deep) between the key rows, below; the lands between them are the floor plane
    fw = FLOOR_W
    floor_z = lambda h, x, y: z_at(Ms[h], fw, x, y)
    floor = {h: {"open": o_, "open_run": dedup(o_.buffer(0.5, join_style="mitre")), "w": fw} for h, o_ in opens_h.items()}
    def floor_under(h, poly):  # the highest floor-plane point under poly
        return max(floor_z(h, x, y) for x, y in poly.exterior.coords)
    islands = []
    for h, d in halves.items():  # a pillar under each PCBsnap
        M, o_ = Ms[h], opens_h[h]
        A = [M[0, 0], M[0, 1], M[1, 0], M[1, 1], M[0, 2] * wb + M[0, 3], M[1, 2] * wb + M[1, 3]]
        for q in d["snaps"]:
            sq = list(affinity.affine_transform(q["poly"], A).exterior.coords)[:4]
            p0, p1, p3 = np.array(sq[0]), np.array(sq[1]), np.array(sq[3])
            t = (p1 - p0) / np.linalg.norm(p1 - p0)
            n_in = (p3 - p0) / np.linalg.norm(p3 - p0)  # from the snap's outer face inward
            m = (p0 + p1) / 2
            L_, D_ = P["pillar"][0] / 2, q["post_depth"]  # (from the wall; shorter where the legs are trimmed)
            a0, a1 = -(P["snap_gap"] - P["snap_spine"] + 1.5), D_ - (P["snap_gap"] - P["snap_spine"])  # from the outer face: 1.5 into the wall, D_ in from the wall
            rect = Polygon([m - t * L_ + n_in * a0, m + t * L_ + n_in * a0, m + t * L_ + n_in * a1, m - t * L_ + n_in * a1])
            rect = rect.buffer(-P["pillar_r"]).buffer(P["pillar_r"])
            isl = dedup(merge(rect.intersection(o_), o_, P["pillar_fillet"]))
            # its top is the half's PCB-underside plane moved down pillar[2] (parallel to the PCB); Fusion trims the
            # prism to that plane
            zs = [z_at(M, wb, x, y) - P["pillar"][2] for x, y in isl.exterior.coords]
            er = isl.buffer(-0.6)
            er = max(getattr(er, "geoms", [er]), key=lambda e_: e_.area)
            ec = list(er.exterior.coords)
            islands.append({"poly": isl, "z": [z_base - 1.0, max(zs) + 0.5], "kind": f"pillar {h} {q['side']}", "half": h, "fillet": P["pillar_fillet"],
                            "w_top": wb - P["pillar"][2], "z_low": min(zs), "z_high": max(zs), "z_floor": floor_under(h, isl),
                            "probes": [list(f(ec, key=k_)) for f in (min, max) for k_ in (lambda p: p[0] + p[1], lambda p: p[0] - p[1])]})
    bosses = [(f"insert boss {i + 1}", q.x, q.y, P["insert_hole"][0] / 2,
               P["panel_t"] + (P["insert_hole_short"][1] if i < 2 else P["insert_hole"][1])) for i, q in enumerate(screws)]
    bosses += [(f"UDB insert boss {i + 1}", x, y, P["udb_insert"][0] / 2, udb["mount_z"][0] + P["udb_insert"][1])
               for i, (x, y) in enumerate(udb["mounts"])]
    for kind, x, y, ri, itop in bosses:  # >= 5 mm of material over each insert under a pocket (5.2: measured)
        top = itop + 5.2
        for h, o_ in opens_h.items():
            if o_.distance(Point(x, y)) < ri + 5:
                isl = merge(Point(x, y).buffer(ri + 5).intersection(o_), o_)
                low_ = o_.difference(zp_above(Ms[h], top + 0.3 - fw + wb))  # where the floor plane is below its top (+0.3)
                eff = isl.intersection(low_.buffer(0.5)) if not low_.is_empty else Polygon()
                if kind.startswith("UDB") and not eff.is_empty:
                    # M6 (undercut check): a UDB boss clipped where the floor rises past its top left zero-area slivers
                    # on its top at the wall; it stands on its whole disc instead, top >= 0.5 over the floor there
                    eff = isl
                eff = max(getattr(eff, "geoms", [eff]), key=lambda e: e.area) if not eff.is_empty else eff
                if not eff.is_empty and eff.area > 2.0:
                    # its flat top clears the tilted floor under it by >= 0.5 (a top grazing the floor left slivers)
                    islands.append({"poly": dedup(eff), "z": [z_base - 1.0, max(top, floor_under(h, eff) + 0.5)], "kind": kind, "half": h,
                                    "z_floor": floor_under(h, eff)})
    # cable path under the floor: a breakthrough round each JST plug pocket, then a channel to the UDB bay
    bay_c = bay.centroid
    lines, stubs = [], []
    for h, d in halves.items():
        M = Ms[h]
        A = [M[0, 0], M[0, 1], M[1, 0], M[1, 1], M[0, 2] * wb + M[0, 3], M[1, 2] * wb + M[1, 3]]
        jp = affinity.affine_transform(d["jst_pocket"], A)
        stubs.append(opn3(jp.buffer(r3).intersection(opens_h[h])))
        lines.append(LineString([(jp.centroid.x, jp.centroid.y), (bay_c.x, bay_c.y)]))
    for q in islands:  # what Fusion takes out of the void: the island, run 0.5 into the wall (M6: no longer grown 0.05 in the
        # pocket: it left micro-jogs at the wall)
        o_ = opens_h[q["half"]]
        # (kept 1 mm off the JST breakthroughs: a boss top meeting a breakthrough wall left zero-area slivers)
        q["poly"] = q["poly"].buffer(0).difference(unary_union(stubs).buffer(1.0)).buffer(0)  # (dedup can leave a bow-tie)
        q["poly"] = max(getattr(q["poly"], "geoms", [q["poly"]]), key=lambda e: e.area)
        # (M6: no 0.05 growth any more: it left a lip along the wall past each island's fillet, ending in 0.01 mm
        # jogs and zero-area triangles that no tool reaches; the island already shares the wall exactly)
        grow = 0.0
        j_ = q["poly"].buffer(0.5).difference(o_.difference(q["poly"].buffer(grow))).buffer(0)
        q["join_alt"] = dedup(Polygon(max(getattr(j_, "geoms", [j_]), key=lambda e: e.area).exterior))  # Fusion fallback
        # and the razor wedges where its R3 fillets run tangent into the wall (no Ø6 reaches them anyway) join it too
        loc = o_.intersection(j_.buffer(10.0))
        rf = q.get("fillet", r3)  # (the pillars' R2: an R3 opening here would grow their fillets back to R3)
        air_ = loc.difference(j_).buffer(-rf, quad_segs=16).buffer(rf, quad_segs=16)
        j_ = j_.union(loc.difference(air_.buffer(0.05)).intersection(j_.buffer(rf))).buffer(0)  # (M6: 0.01 left 0.03-0.04 mm slots)
        # (M6: healed by a 1 um closing: a float-noise gap between the pocket part and its wall run made the largest
        # piece below the pocket part alone, leaving a 0.03 mm slot between some pillars and the wall)
        j_ = j_.union(j_.buffer(0.5).difference(o_)).buffer(0.001, join_style="mitre").buffer(-0.001, join_style="mitre")  # (that fill runs into the wall too)
        q["join"] = dedup(Polygon(max(getattr(j_, "geoms", [j_]), key=lambda e: e.area).exterior))  # (pinholes filled)
    # (the channels run under the hung board, below its standoffs, and open into the bay)
    channels = [ln.buffer(P["cable_channel"] / 2) for ln in lines]
    chan = opn3(unary_union(channels).intersection(cavity))
    # relief grooves. M6 (user): one per key row, under that row's hotswap sockets: each socket keep-out (projected
    # along the PCB normal onto the floor plane) grown socket_margin, the gaps between neighbouring sockets in the row
    # closed, so it follows the row's curve and stagger; a semicircular notch at the row's middle key, R3 corners
    # (>= Ø6 tool), stopping groove_wall short of the pocket walls. Kept out of the snap pillars, JST breakthroughs
    # and bosses (island_clear round them). None where its bottom would break the H_front rule; over the cable
    # channels and the UDB bay >= 3 mm of material is left (checked in the test)
    gw, gd = P["relief"]
    for h, d in halves.items():
        M, o_ = Ms[h], opens_h[h]
        A = [M[0, 0], M[0, 1], M[1, 0], M[1, 1], M[0, 2] * fw + M[0, 3], M[1, 2] * fw + M[1, 3]]
        rows = {}
        for o, k, sk in zip([o for o in caps if o["half"] == h], d["keys"], d["sockets"]):
            rows.setdefault(o["row"], []).append((k, sk))
        grooves = []
        for r_, ks in sorted(rows.items()):
            band = unary_union([sk.buffer(P["socket_margin"], join_style="mitre") for _, sk in ks])
            band = band.buffer(P["socket_bridge"], join_style="mitre").buffer(-P["socket_bridge"], join_style="mitre")
            grooves.append(band)
            k_, sk_ = sorted(ks, key=lambda q: q[0]["x"])[len(ks) // 2]
            big = max(getattr(band, "geoms", [band]), key=lambda q: q.area)
            c0 = Point(k_["x"], k_["y"])  # the notch on the groove's edge nearest the middle key's centre
            c_ = big.exterior.interpolate(big.exterior.project(c0))
            grooves.append(Point(c_.x, c_.y).buffer(gw * 0.75))
        gro = affinity.affine_transform(unary_union(grooves), A).intersection(o_.buffer(-P["groove_wall"]))
        rule_ok = zp_above(M, P["panel_t"] + P["floor_above_panel"] + gd - fw + wb)
        keep_out = unary_union([q["poly"].buffer(P["island_clear"]) for q in islands if q["half"] == h] +
                               [unary_union(stubs).buffer(P["island_clear"])])
        gro = opn3(gro.intersection(rule_ok).difference(keep_out))
        gro = unary_union([q for q in getattr(gro, "geoms", [gro]) if q.area > 20])
        gro = shapely.remove_repeated_points(gro, 0.02).buffer(0)  # (M6: drops the 0.01 mm jogs the booleans leave: sliver faces)
        floor[h].update({"grooves": dedup(gro), "groove_w": [fw - gd, fw]})  # off the walls: no shared faces
    cavity_steps = {"channels": channels, "chan": chan, "chan_z": [-1.0, P["panel_t"] + P["chan_h"]],
                    "stubs": unary_union(stubs), "floor": floor, "islands": islands}

    minx, miny, maxx, maxy = outline.bounds
    return {
        "params": P, "layers": layers, "udb": udb, "socket_box": SOCKET, "floor_w": FLOOR_W, "pcb_mid_w": PCB_MID_W,
        "ridge_x": ridge, "y_front": y_front, "lift": lift, "h_front": min(heights["front_left"], heights["front_right"]),
        "max_height": max(heights.values()), "heights": heights, "floor_min_z": low + lift, "web_min": web_min, "web_sym": web_sym,
        "outline_size": [maxx - minx, maxy - miny],
        "key_gap": key_gap, "v_offset": sharp[3][0] - ridge, "v_offset_equal_bezels": v_off0, "front_bezels": front_bezels,
        "_shapes": {"envelopes": env, "opening": opening, "outline": outline, "outline_sharp": outline_sharp,
                    "footprint": footprint, "panel": panel, "rabbet": rabbet, "cavity": cavity},
        "screws": [[round(p.x, 4), round(p.y, 4)] for p in screws],
        "cavity_steps": cavity_steps, "bay": bay, "bay_z": [-1.0, z_top + P["udb_mount"][1]], "notch": notch, "notch_z": [-1.0, P["panel_t"] + uh],
        "usb_centre": [ridge, usb_centre_z], "feet": feet, "feet_plug": [f.buffer(P["foot_fit"], quad_segs=16) for f in feet],
        "peg_holes": [q.buffer(P["foot_peg"][0] / 2, quad_segs=16) for q in feet_pegs],
        "pegs": [q.buffer(P["foot_peg"][0] / 2 + P["foot_fit"], quad_segs=16) for q in feet_pegs], "walls": walls, "lower_band": lower_band,
        "panel_lean": panel_lean, "rabbet_lean": rabbet_lean, "lip": lip, "lip_pocket": lip_pocket,
        "rear_zone_panel": rear_zone["panel"], "rear_zone_body": rear_zone["body"],
        "lip_z": [P["panel_t"], lip_top], "lip_ends": [lip_line.coords[0][0], lip_line.coords[-1][0]], "lip_pocket_z": [P["panel_t"] - 0.01, lip_top + P["panel_gap_print"]],
        # M4: the opening chamfer's top edge on the facets (Fusion cuts it with a 45 deg tapered extrude: its
        # chamfer feature fails on the faceted opening)
        "chamfer_top": opening.buffer(P["opening_chamfer"]).simplify(0.002).buffer(0.002, join_style="mitre"),
        "halves": halves,
    }


def jsonable(x):
    if hasattr(x, "geom_type"):
        return coords(x)
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    return [jsonable(v) for v in x] if isinstance(x, (list, tuple)) else x


def to_json(g):
    s = g["_shapes"]
    out = jsonable({k: v for k, v in g.items() if k != "_shapes"})
    out.update({k: coords(s[k]) for k in ("opening", "outline", "outline_sharp", "footprint", "panel", "cavity")})
    out["rabbet"] = {k: coords(v) for k, v in s["rabbet"].items()}
    return out


def load(path):
    lay = json.loads(Path(path).expanduser().read_text())
    lay.setdefault("outer", lay.pop("tilt", 0))  # as alice.App.load
    return lay


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: geometry.py LAYOUT.json")
    g = build(load(sys.argv[1]))
    out = Path(__file__).resolve().parent / "out" / "case_geometry.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(to_json(g), indent=1))
    hh = g["heights"]
    print(f"ridge x {g['ridge_x']:.2f} mm, lift {g['lift']:.1f} mm, pocket floor min {g['floor_min_z']:.2f} mm")
    print(f"H_front (outer front corner) {g['h_front']:.2f} mm, max height {g['max_height']:.2f} mm, "
          f"back centre {hh['back_centre']:.2f} mm")
    print("heights: " + ", ".join(f"{k} {v:.2f}" for k, v in hh.items()))
    print(f"centre web between the openings, narrowest: {g['web_min']:.2f} mm")
    print(f"halves spread {P['half_spread']} mm; ridge at mid key gap {g['key_gap'][0]:.2f} .. {g['key_gap'][1]:.2f}; "
          f"outline centre {g['outline_offset']:+.2f} mm off it; side bezels {P['bezel_side']} each; "
          f"V front point {g['v_offset']:+.2f} mm off the ridge")
    print(f"outline {g['outline_size'][0]:.2f} x {g['outline_size'][1]:.2f} mm, {len(g['screws'])} screws, back one "
          f"{g['udb']['back_screw_shift']:+.2f} mm off the ridge -> {out}")
    fl = g["cavity_steps"]["floor"]
    print("pocket floor: plane parallel to each PCB, " + "; ".join(f"{h} z {min(G_ := [z_at(np.array(g['halves'][h]['matrix']), f['w'], x, y) for x, y in f['open'].exterior.coords]):.2f}..{max(G_):.2f}, grooves {f['grooves'].area:.0f} mm2 at -{P['relief'][1]}" for h, f in fl.items()))
    print("islands: " + ", ".join(f"{q['kind']} top z " + (f"{q['z_low']:.2f}..{q['z_high']:.2f}" if 'w_top' in q else f"{q['z'][1]:.2f}")
                                  + f" (floor {q['z_floor']:.1f})" for q in g["cavity_steps"]["islands"]))
    print("walls (plan, mm): " + ", ".join(f"{k} {v:.2f}" for k, v in g["walls"].items()))
    for h, d in g["halves"].items():
        jc = d["jst"].centroid
        print(f"{h}: {len(d['stabs'])} stab cutouts, JST at ({jc.x:.1f}, {jc.y:.1f}), snaps " +
              ", ".join(f"{s['side']}" +
                        f" {s['length']:.0f} mm, {s['corner_dist']:.1f} mm from corners" for s in d["snaps"]))
