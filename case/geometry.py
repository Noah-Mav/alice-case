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
    "typing_angle": 8.0, "tent": 5.0,  # v2 (user, heights helper): 6 / 4 -> 8 / 5, front kept low by base_min 3.5 (v1 had tent 5 -> 4 at M4, typing 7 -> 6 at M6)
    "plate_t": 1.5, "cutout": 14.0, "cutout_print": 14.05, "plate_to_pcb": 5.0, "pcb_t": 1.6, "socket_h": 1.8,
    "lip": 6.0, "skirt_bottom_out": 2.0,  # M7: Cherry/GMK skirt bottomed out (rest 6.0, verified, see keycaps.py); lip 2.0 -> 6.0 (user: skirt level with the case edge at rest): stack 0.5 lower (solid front base), walls up the rest
    "artisan_gap": 1.5, "plate_wall_gap": 1.0,
    "bezel_side": 6.0, "bezel_front": 6.0, "bezel_back": 8.5,  # v2: front 7 -> 6, back 9.5 -> 8.5 (user approved)
    "pocket_r": 3.0, "cavity_r": 6.0, "outer_r": 3.0, "top_round": 1.0, "opening_chamfer": 0.75,
    "crease_mode": "front_horizontal",  # M6 (user): the chosen design, front faces level ("deepening" = the M5 rule)
    "crease_depth": 9.0, "lower_back": 0.477,  # v2: 0.5 -> 0.477 keeps the end creases level (0.467 was worked out with the old ridge rule's heights; with the R2-midpoint ridge it leaves them 0.41 mm apart)  # crease: 10 mm on the front, lower band = lower_back x height at the back centre
    "lower_cant": 12.0, "panel_t": 4.0,  # v2: lower_cant 8 -> 10 -> 12 (user) (front footprint inset stays 1.27 mm with the front crease 1.9 mm lower)
     "rim": 6.0, "rear_strip_end": 6.0,  # M6 (user): = rim, so the back edge runs square into the side rims (was 10: an inset step at each back corner)
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
    # v2 (user): the visible opening is a neck usb_neck = [width, depth] through the rear face; behind it the 22 wide
    # chamber (usb_slot_w) holds the board's rear end (its top corners must clear the R3 roof corners, see the test).
    # The neck step sits 0.25 mm behind the board's rear edge, so usb_recess = neck depth + 0.25
    "usb_neck": [17.0, 2.0],
    "panel_gap_wood_fb": 0.5, "panel_gap_wood_lr": 0.1, "panel_gap_print": 0.2,
    "ledge": 14.0,
    # v2 (user): the TPU feet (28 x 6 bars, pockets, pegs) are gone: 4 adhesive bumpons (3M SJ5302, 7.9 dia x 2.2 high
    # hemispheres) sit in shallow locating recesses in the underside: recess diameter, depth, and how far in from the
    # two desk-level footprint edges of each corner (front pair under the solid bezel, rear pair in the body beside the
    # panel). The panel's sides are no longer set by feet: panel_half_w either side of the ridge
    "bumpon": {"d": 7.9, "h": 2.2, "recess_d": 8.4, "recess_depth": 0.5, "inset": 14.0}, "panel_half_w": 106.1,
    "rear_cut": {"drop": 4.0, "back": 14.3},  # v2 item 9 (user, medium), revised: a subtle accent, width ~91 at the rear face (was 181), apex 14.3 forward (was 25); see _build and the test (>= 6 mm to the pockets)
    "usb_opening": [12.0, 7.2],  # [1] = height used; [0] is NOT used (the visible width is usb_neck, the chamber usb_slot_w)
    # screws: 3 (M8): the two back panel corners and the V point
    "udb": [18.0, 16.5],            # §6.9 Unified Daughterboard C3, at the back on the ridge
    "udb_r": 2.0, "udb_holes": [14.0, 12.5], "udb_hole_d": 2.2, "udb_t": 1.6, "udb_air": 0.5,
    "usb_receptacle": [8.94, 7.35, 3.21],  # HRO TYPE-C-31-M-12 w x depth x h, on the UDB top, face at the board edge
    "usb_recess": 2.25,             # receptacle face behind the outer rear face: the neck depth + 0.25 (v2; was 1.0, limit <= 1.5)
    "keycap_h": 7.5,                # M6: Cherry profile cap, skirt to top (~R2-R4), for the bottomed-out envelope only
    "switch_top_h": 6.6,            # MX top housing above the plate top (housing top 11.6 above the PCB top)
    "jst": [6.0, 4.2, 2.95], "jst_pocket": [8.0, 6.0],  # §6.10 JST-SH 4-pin header, free space around it
    "snap_gap": 0.9,                # PCB edge to pocket wall at mid-PCB (the clip spine fills it)
    "screw_head": 6.72,             # ISO 10642 M3 head diameter
    "screw_clear": 3.4,             # M3 clearance hole in the panel (90° countersink to screw_head)
    "insert_hole": [4.0, 6.0],      # print: heat-set M3 x 5.7 hole, diameter and depth above the rabbet ceiling (M5: 6.5 -> 6.0)
    # M5: the two back-corner screws sit under the pocket floor; short inserts there keep >= 5 mm above them. Print:
    # M3 x 3 short heat-set (e.g. CNC Kitchen) in Ø4.0 x 3.6 (M7). Wood: a <= 3.5 mm long M3 insert.
    # M7: 4.0 -> 3.6 deep with the stack 1.2 lower (lip 3.2): the back-left boss would meet a hotswap socket by 0.3
    "insert_hole_short": [4.0, 3.6],
    # M5: the UDB hangs upside down (components toward the panel) from the bay ceiling, 0.5 mm (udb_air) under the
    # slot roof. The front pair of holes gets body standoffs: diameter, height (= the air over the board there). The
    # rear pair sits 3 mm inside the rear face, under the slot roof: no room for an insert with a 5 mm wall, so no
    # screw there (the slot holds the receptacle end).
    "udb_mount": [6.0, 1.0],
    # M2 insert hole in each standoff, diameter x depth from the board. Print: heat-set M2 x 3 (OD ~3.6) in Ø3.2 x 4.
    # Wood: brass knife-thread M2 x 4 (OD ~3.5-4), pilot per its datasheet (~Ø3.0-3.2 x 5), test in scrap.
    "udb_insert": [3.2, 3.6],  # M7: 5.0 -> 3.6 (stack 0.5 lower, UDB 1 mm higher with panel_t 4: the boss over it stays 2 mm under the PCB); M2 x 3 inserts
    "stab": {"w": 6.75, "h": 14.0, "y_top": 6.0, "y_bottom": -8.0, "x": 11.938, "min_w": 2.0},
    # M7: the opening's design envelope (w from .. to), frozen at the M6 numbers so the walls, the outline in plan, the
    # PCBs and the snap spots stay put while the bezel top rose. Not the cap skirt (that is skirt_bottom_out); the
    # real caps are checked against the opening (cap_gap)
    "opening_env": [1.6, 2.0],
    # M7: air between the PCB underside and the pocket floor plane (the grooves add relief[1]); foam is 3-3.5 mm.
    # User chose lip 3.2 / air 3.5 over 2.7 / 4.0 (more like a common custom; front floor rule is the limit)
    "floor_air": 3.5,
    "floor_above_panel": 2.0,       # §4 floor rule over the panel: pocket floor >= panel_t + this above the desk (M5: 3 -> 2)
    # M7 (user): solid front base. The panel covers only the rear (bay, channels, USB): a pentagon whose front is the
    # case's front V moved back panel_shift (tip on the ridge). In front of it the body is solid to the desk:
    # >= base_min of body under the pocket floor, >= base_min_groove under the relief grooves (H_front rule)
    "panel_shift": 48.0,  # (M7 panel_t 4: 41 -> 50 brings the side-front corners to the screws' first sound spots; the bay and channels stay covered)
    "panel_front_r": 6.0, "band_end_run": 21.2, "screw_recess_margin": 1.0,
    # M7 (user, reference photo): a shallow recessed field on the panel's underside: depth, border of full panel all
    # round, its own corner radius (>= the Ø6 flat end mill's R3), and full-thickness tabs round each screw countersink
    "panel_recess": [0.6, 3.5, 3.0, 1.5],  # v2 (user): depth 0.4 -> 0.6
    # v2: round each of the 3 screws a seat pad: the field is only screw_seat[0] deep there (a round pad of radius head / 2
    # + screw_seat[1], merged into the border), so the countersink cone still leaves panel_t - seat - 1.66 = 1.94 mm
    "screw_seat": [0.4, 1.5],
    # M7 (user): the same 0.4 mm recess on the panel's rear face (its edge and the band): border (smaller than the
    # bottom's 3.5: the face is only 7.6 mm tall), corner radius; a full-thickness frame of the same border round the
    # USB notch. Drawn in (x, z) on each rear lean plane; cut on an extra setup (the panel on edge / angle plate)
    "band_recess": [1.5, 1.5], "base_min": 3.5, "base_min_groove": 3.5,
    "relief": [7.0, 1.25],  # M6 floor relief grooves: notch diameter / 1.5 (> Ø6 tool), depth below the floor plane
    # M6 grooves under the sockets: margin round each socket keep-out, gap closing between neighbours in a row,
    # land left to the pocket wall, clearance round bosses / JST breakthroughs
    "socket_margin": 1.25, "socket_bridge": 3.0, "groove_r": 2.0, "clip_keep": 1.0, "groove_wall": 4.0, "island_clear": 1.0,  # M6 (user): flat 4 mm band along every wall (v2: for the PCB clips' recesses)
    "chan_h": 4.0,  # cable channel height
    # v2 (user): the PCBsnaps, their pillars and the pillar fillets are gone. The PCB is held by 10 printable TPU C-clips
    # (5 per half) on its edge: each 10 long, a slot of 1.5 for the 1.6 PCB (it grips), 2.5 of ledge under the PCB, a 1.0
    # lip 1.5 over the PCB top (30 deg lead-in), the spine filling the PCB-to-wall gap, a hex lattice below. Each clip
    # sits in a recess in the pocket floor: recess = [length, width, depth], its inner side snap_gap - width = 2.9 in from the PCB
    # edge (a fixed line, so the ledge's 2.5 + 0.4 always fits), running out to the pocket wall, which it is cut to: the width at the
    # floor is therefore 2.9 + the wall gap (3.2 at the back edge .. 4.7 at the front, the wall being vertical and the PCB tilted; the
    # nominal 3.8 only where the gap is 0.9). R1.5 corners (Ø3 tool), its wall side on the wall (no undercut),
    # and a 45 deg lead-in chamfer (the depth wide) on its three open sides. The floor plane under a recess must be
    # >= clip_floor_min above the desk (local exception to base_min: 4.0 - 0.5 = 3.5 left under it).
    # clip_pts: the PCB-local edge points (v1 PCB frame, as the spots were chosen); geometry.py snaps them to the frozen edge
    "clip": {"len": 10.0, "slot": 1.5, "under": 2.5, "lip": 1.0, "lip_overlap": 1.5, "lip_lead": 30.0, "lead": 0.4,
             "wall_air": 0.1, "lattice_cell": 2.3, "lattice_wall": 0.8,
             # fit in the recess: the clip's plan is the recess's own outline (rr_x: 10.4 long, R clip_r corners, running past the
             # wall) shrunk by `fit` all round: 0.2 to the ends and the R1.5 corners at the recess bottom (its narrowest: the
             # lead-in only widens it), trimmed by the profile's ledge (2.5 under the PCB, 0.4 in from the recess side) and the
             # spine (wall_air 0.1 off the wall). v2 first run: the square clip corners stood 0.2 into the R1.5 ones, 10 slivers
             # of 0.006 .. 0.03 mm3 in the Fusion interference check. The test asserts the clearance >= `min_fit`
             "fit": 0.2, "min_fit": 0.15,
             # two printed variants (user): the PCB-to-wall gap at the floor plane runs 0.3 .. 1.9 mm (the pocket wall is vertical, the
             # PCB tilted), so one spine cannot bear everywhere. Each variant's outer face is a straight line in (x, w) from its recess-bottom
             # offset xb to its lip-top offset xt, found by clip_variants() as the largest that keeps wall_air off the wall at every spot the
             # variant serves (a lean of ~8 deg, the wall's own). Plan: rectangle len x (under .. xmax) with R r_in (recess side) / r_out
             # (wall side) corners. Marks: blind dimples on the lip top (1 for F, 2 for B), mark_d wide, mark_depth deep, at x mark_x,
             # +-mark_dz along the edge: they touch nothing and change no fit
             "r_in": 1.2, "r_out": 2.5, "mark_d": 0.8, "mark_depth": 0.4, "mark_x": -0.4, "mark_dz": 1.0},
    # which spots (1-based, per half) take which variant: front edge (Alt, Shift/Z) = FRONT; back edge (R/T, Tab) and inner (right of B) = BACK
    "clip_variants": {"front": {"left": [1, 5], "right": [1, 5], "marks": 1}, "back": {"left": [2, 3, 4], "right": [2, 3, 4], "marks": 2}},
    "clip_clear": 0.5, "clip_slide": 2.0, "clip_recess": [10.4, 3.8, 0.5], "clip_r": 1.5, "clip_floor_min": 4.0,
    "clip_pts": {"left": [[71.3, 6.3], [124.3, 29.5], [102.7, 81.0], [13.0, 85.6], [20.0, 26.9]],
                 "right": [[197.0, 6.7], [139.0, 30.0], [154.4, 80.0], [245.0, 85.6], [240.0, 26.9]]},
    # v2: the v1 dummy PCB and plate are reused, so their outlines (case/frozen_v1.json) are frozen, not re-derived from
    # the opening at the new angles; the pocket walls grow round them to keep at least pcb_wall_min (mid-PCB gap
    # snap_gap, +- 0.1 over the tilted PCB's thickness) and plate_wall_min (v1: 0.906)
    "pcb_wall_min": 0.80, "plate_wall_min": 0.90,
    "cable_channel": 13.0,  # > 2 cavity_r so the R6 opening keeps it
    "lift_step": 0.1,               # H_front rounding (M7: 0.5 -> 0.1, so the stack sits where the floor rule puts it)
    "ridge_clear": 0.5,             # §6.6 PCB/plate clip at the ridge
    # M5: each half moved outward along layout x (left, right; mm) before the transforms, widening the centre web.
    # v2: the ridge (centreline) is the midpoint of the two R2 (anchor) rows' extents, not the whole-layout key gap,
    # so both R2 rows and both outer case edges are equidistant from it
    "half_spread": [3.5, 3.5],  # v2: 1.2 -> 3.5: the ridge is now the R2 midpoint, which puts the right half's top-row Y key 2.4 mm from it
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
# the real S-shaped socket body (case/fusion_export.py SOCKET_OUTLINE), key-local, +y = back: the clips' ledges are
# kept clear of it, not of the larger SOCKET box
SOCKET_REAL = [(-6.085, 1.51), (-0.2, 1.51), (-0.2, 3.4), (4.815, 3.4), (4.815, 6.11), (-1.0, 6.11), (-1.0, 4.2), (-6.085, 4.2)]
FROZEN = json.loads((Path(__file__).resolve().parent / "frozen_v1.json").read_text())

# MX centre post (Ø4) sticks out below the PCB: JST keep-out. ponytail: ignores 5-pin pegs; add if PCBs use them.
POST_R = 2.0
# M7: the pocket floor plane, floor_air under the PCB underside along the normal
FLOOR_W = -(P["plate_to_pcb"] + P["pcb_t"] + P["floor_air"])
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


def clip_variants(pre, w_bot, wb_, w_slot, w_top):
    """v2 (user): the two printed TPU clip variants, FRONT (spots P["clip_variants"]["front"]) and BACK. One profile, one plan, per
    variant, valid at every spot it serves: the outer (wall-side) face is the straight line (xb, w_bot) -> (xt, w_top), the largest
    that keeps clip["wall_air"] between the clip's sections and the pocket wall (all 10 mm of it, at 14 levels) and the recess's own
    outline `fit` (min_fit) off them at the recess bottom, at every one of its spots. Start from the tightest centre-line wall offset
    at each end less wall_air; step down by 0.01 at the end that fails (a pocket corner curving in along the clip: the back
    edge's R3 / R4), then floor to 0.01. Returns {name: {name, xb, xt, profile, plan, marks, spots, gaps, spot_keys}}."""
    cl = P["clip"]
    out = {}
    levels = [w_bot + 0.001 + (w_top - w_bot - 0.002) * i / 13 for i in range(14)]
    u, lo, L = cl["under"], cl["lip_overlap"], cl["len"]
    ld = cl["lead"] / math.tan(math.radians(cl["lip_lead"]))
    for name, spec in P["clip_variants"].items():
        keys = [(h, i) for h in ("left", "right") for i in spec[h]]
        shape = lambda xb, xt: clip_shape(xb, xt, w_bot, wb_, w_slot, w_top)

        def bad(xb, xt):
            prof, plan = shape(xb, xt)
            b = []
            for k in keys:
                p = pre[k]
                for w in levels:
                    sec = clip_section(prof, plan, w)
                    sl = Polygon([tuple(p["c"] + p["t"] * z + p["n"] * x) for x, z in sec.exterior.coords])
                    wall = p["o_at"](w)
                    if not wall.buffer(-cl["wall_air"] + 1e-4).contains(sl):
                        b.append(w)
                    if w < w_bot + 0.01 and not p["rr_x"].buffer(-cl["min_fit"] + 1e-4).contains(sl):
                        b.append(w)
            return b
        xb = min(pre[k]["wall_at"](w_bot) for k in keys) - cl["wall_air"]
        xt = min(pre[k]["wall_at"](w_top) for k in keys) - cl["wall_air"]
        for _ in range(300):
            bd = bad(xb, xt)
            if not bd:
                break
            if min(bd) < (w_bot + w_top) / 2:
                xb -= 0.01
            else:
                xt -= 0.01
        else:
            raise SystemExit(f"clip variant {name}: no outer face clears every spot")
        xb, xt = math.floor(xb * 100 + 1e-6) / 100, math.floor(xt * 100 + 1e-6) / 100
        assert not bad(xb, xt), name
        prof, plan = shape(xb, xt)
        gaps = {}
        for k in keys:
            ws = {w: pre[k]["wall_at"](w) - (xb + (xt - xb) * (w - w_bot) / (w_top - w_bot)) for w in (w_bot, wb_, w_top)}
            gaps[f"{k[0]} {k[1]}"] = [round(min(ws.values()), 3), round(max(ws.values()), 3)]
        out[name] = {"name": name, "xb": xb, "xt": xt, "profile": [[round(x, 4), round(w, 4)] for x, w in prof],
                     "plan": [(round(x, 4), round(z, 4)) for x, z in plan.exterior.coords], "marks": spec["marks"],
                     "spots": {h: spec[h] for h in ("left", "right")}, "gaps": gaps, "spot_keys": keys}
    allk = sorted(k for v in out.values() for k in v["spot_keys"])
    assert allk == sorted((h, i) for h in ("left", "right") for i in range(1, 6)), allk  # 2 variants, all 10 spots exactly once
    return out


def clip_shape(xb, xt, w_bot, wb_, w_slot, w_top):
    """A variant's side profile [(x out from the PCB edge, w)] and plan (shapely Polygon, (x, z along the edge))."""
    cl = P["clip"]
    u, lo, L = cl["under"], cl["lip_overlap"], cl["len"]
    ld = cl["lead"] / math.tan(math.radians(cl["lip_lead"]))
    prof = [(-u, w_bot), (xb, w_bot), (xt, w_top), (-lo, w_top), (-lo, w_slot + cl["lead"]), (-lo + ld, w_slot), (0.0, w_slot),
            (0.0, wb_), (-u + ld, wb_), (-u, wb_ - cl["lead"])]
    xp = max(xb, xt)
    ri, ro = cl["r_in"], cl["r_out"]
    A = box(-u, -L / 2, xp + 10, L / 2).buffer(-ri, quad_segs=8).buffer(ri, quad_segs=8)
    B = box(-u - 10, -L / 2, xp, L / 2).buffer(-ro, quad_segs=8).buffer(ro, quad_segs=8)
    return prof, A.intersection(B)


def clip_section(prof, plan, w):
    """The clip's cross-section (x, z) at the level w: the profile's x extents there, cut to the plan."""
    hit = Polygon(prof).intersection(LineString([(-50, w), (50, w)]))
    xs = [g_.bounds for g_ in getattr(hit, "geoms", [hit])]
    sec = unary_union([box(x0, -50, x1, 50) for x0, _, x1, _ in xs]).intersection(plan)
    return max(getattr(sec, "geoms", [sec]), key=lambda g_: g_.area) if not sec.is_empty else sec


def place_clips(pcb, pts, sockets_real, stabs, jst_pocket):
    """v2: the TPU C-clips on the PCB edge. For each PCB-local edge point of P["clip_pts"], the nearest point of the
    (frozen) PCB outline, the edge's tangent t and outward normal n there, and in that frame (t along the edge, n out
    from it): the clip's frame; the floor recess is made later, once the pocket walls are known
    (clip_recess). A point slides along the edge (<= clip_slide) to where the ledge is at least
    clip_clear from the real hotswap socket bodies, stab cutouts and the JST pocket; raises if none does."""
    L = P["clip_recess"][0]
    ext = pcb.exterior
    out = []
    for i, (x, y) in enumerate(pts):
        s_in = ext.project(Point(x, y))
        if ext.interpolate(s_in).distance(Point(x, y)) > 0.5:
            raise SystemExit(f"clip point {(x, y)} is {ext.interpolate(s_in).distance(Point(x, y)):.2f} mm off the PCB edge")
        # the given point, or the nearest spot along the edge (<= clip_slide) where the ledge clears the keep-outs
        for slide in [0.0] + [q * sg for q in np.arange(0.25, P["clip_slide"] + 1e-9, 0.25) for sg in (1, -1)]:
            s0 = s_in + slide
            c = np.array(ext.interpolate(s0).coords[0])
            a, b = np.array(ext.interpolate(s0 - 1.0).coords[0]), np.array(ext.interpolate(s0 + 1.0).coords[0])
            t = (b - a) / np.linalg.norm(b - a)
            n = np.array([t[1], -t[0]])
            if pcb.contains(Point(*(c + n * 0.5))):
                n = -n
            frame = lambda s_, q_: tuple(c + t * s_ + n * q_)
            rect = lambda s0_, s1_, q0, q1: Polygon([frame(s0_, q0), frame(s1_, q0), frame(s1_, q1), frame(s0_, q1)])
            cl = P["clip"]
            under = rect(-cl["len"] / 2, cl["len"] / 2, -cl["under"], 0.0)
            dmin = min(under.distance(o_) for o_ in sockets_real + stabs + [jst_pocket])
            if dmin >= P["clip_clear"]:
                break
        else:
            raise SystemExit(f"clip {i + 1} at {(round(x, 1), round(y, 1))}: no spot within {P['clip_slide']} mm clears the sockets / stabs / JST")
        # how straight the edge is along the clip (the recess is a straight box on the tangent)
        dev = [abs((np.array(ext.interpolate(s0 + d_).coords[0]) - c) @ n) for d_ in np.arange(-L / 2, L / 2 + 0.1, 0.5)]
        out.append({"name": i + 1, "edge_pt": [float(c[0]), float(c[1])], "t": t.tolist(), "n": n.tolist(), "slide": float(slide),
                    "edge_dev": float(max(dev)), "ledge_clear": float(dmin)})
    return out


def coords(g):
    """A polygon's outline as [[x, y], ...]; a MultiPolygon as a list of those."""
    if g.geom_type == "MultiPolygon":
        return [coords(p) for p in g.geoms]
    assert g.geom_type == "Polygon" and not g.interiors, g.geom_type
    return [[round(x, 4), round(y, 4)] for x, y in g.exterior.coords[:-1]]


def build(lay):
    """v2: the ridge (tent fold, the case centreline) is the midpoint of the two R2 (anchor) rows' extents after
    half_spread moves the halves apart. Both R2 rows then sit equally either side of it, and so do the outer case
    edges (outline_offset ~ 0). The nearest key of each half must still be >= 2 mm from it."""
    g = _build(lay)
    lo, hi = g["key_gap"]
    if g["ridge_x"] - lo < 2 or hi - g["ridge_x"] < 2:
        raise SystemExit(f"key gap {lo:.2f} .. {hi:.2f}: the ridge {g['ridge_x']:.2f} needs >= 2 mm to each half's keys")
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
    # v2: the centreline is the midpoint of the R2 (anchor row: Shift Z X C V B / N M < > Shift Fn) extents, not of the
    # whole-layout key gap (v1: sum(key_gap) / 2, which the right half's top-row Y key pulled 2.32 mm left of it)
    r2 = {h: [p[0] for o in alice.solid(placed) if o["half"] == h and o["rname"].startswith("Anchor") for p in alice.footprint(o)]
          for h in ("left", "right")}
    ridge = (min(r2["left"]) + max(r2["right"])) / 2
    y_front = max(p[1] for q in pts.values() for p in q)
    flip = lambda xy: (xy[0], y_front - xy[1])  # layout -> local (u, v)

    M0 = {"left": matrix(1, ridge, 0.0), "right": matrix(-1, ridge, 0.0)}
    world = lambda M, u, v, w: tuple((M @ [u, v, w, 1])[:2])

    # v2: the v1 PCB and plate are frozen (case/frozen_v1.json): each half's keys only moved along u (half_spread), so the
    # outlines move with them. Refuse to build if the keys changed in any other way.
    frozen = {}
    for h in ("left", "right"):
        f_ = FROZEN[h]
        ks_ = [(o["x"], y_front - o["y"], -o["ang"]) for o in caps if o["half"] == h]
        if len(ks_) != len(f_["keys"]):
            raise SystemExit(f"{h}: {len(ks_)} keys, the frozen v1 PCB has {len(f_['keys'])}")
        dus = {round(k[0] - q[0], 3) for k, q in zip(ks_, f_["keys"])}
        if len(dus) != 1 or any(abs(k[1] - q[1]) > 2e-3 or abs(k[2] - q[2]) > 2e-3 for k, q in zip(ks_, f_["keys"])):
            raise SystemExit(f"{h}: the keys are no longer the v1 keys moved along u (du {dus}); the frozen PCB / plate do not apply")
        du_ = dus.pop()
        frozen[h] = {"du": du_, "pcb": affinity.translate(Polygon(f_["pcb"]), du_, 0), "plate": affinity.translate(Polygon(f_["plate"]), du_, 0)}

    # §6.1 key envelopes: footprint box from skirt-at-bottom-out to the bezel top, projected to plan
    env = [MultiPoint([world(M0[o["half"]], *flip(c), w) for c in alice.footprint(o)
                       for w in P["opening_env"]]).convex_hull for o in caps]
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
    # v2: the frozen v1 PCB and plate must fit the pocket as built at the new angles: at both faces of each (the tilt
    # changes what the vertical walls see) the wall keeps pcb_wall_min / plate_wall_min round them, so the pocket grows
    # where the tilted PCB comes closer than that (R0.5 closing: no new sharp corners)
    top_w_ = -P["plate_to_pcb"]
    need_ = []
    for h in frozen:
        M_ = M0[h]
        for poly_, ws_, gap_ in ((frozen[h]["pcb"], (top_w_ - P["pcb_t"], top_w_), P["pcb_wall_min"]),
                                 (frozen[h]["plate"], (-P["plate_t"], 0.0), P["plate_wall_min"])):
            for w_ in ws_:
                A_ = [M_[0, 0], M_[0, 1], M_[1, 0], M_[1, 1], M_[0, 2] * w_ + M_[0, 3], M_[1, 2] * w_ + M_[1, 3]]
                need_.append(affinity.affine_transform(poly_, A_).buffer(gap_, quad_segs=16))
    grown_ = unary_union([opening] + need_).buffer(P["stagger_r"], quad_segs=16).buffer(-P["stagger_r"], quad_segs=16)
    pocket_growth = grown_.difference(opening)
    pocket_growth_max = max([Point(q).distance(opening.boundary) for g_ in getattr(pocket_growth, "geoms", [pocket_growth])
                             for q in g_.exterior.coords] or [0.0])
    opening = grown_
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

    # H_front: smallest lift (rounded up) putting the pocket floor >= base_min above the desk (M7: solid front; over
    # the panel, further back, the floor is far higher than panel_t + floor_above_panel: tested)
    need = P["base_min"]
    low = min(surface(M0.values(), FLOOR_W, x, y) for g_ in getattr(opening, "geoms", [opening]) for x, y in g_.exterior.coords)
    lift = math.ceil((need - low) / P["lift_step"] - 1e-9) * P["lift_step"]
    Ms = {"left": matrix(1, ridge, lift), "right": matrix(-1, ridge, lift)}
    # M7: the real caps (bottomed out, skirt_bottom_out .. lip) against the opening. Cherry profile (KeyV2, GMK based):
    # base 18.16 (0.445 inside the 19.05 pitch), top 6.31 narrower and 14.64 deep, set 2 mm back, over 7.45 (R2, the
    # least lean of the rows used): per mm up the sides come in 0.42, the front 0.50, the back goes out 0.03
    def cap_at(o, w):
        d_ = w - P["skirt_bottom_out"]
        side, front, back = 0.445 + 0.42 * d_, 0.445 + 0.50 * d_, 0.445 - 0.03 * d_
        ends = [np.array(flip(c)) for c in alice.footprint(o, 0.0, 2.0)]
        a_, b_ = ends[0], max(ends, key=lambda e: np.linalg.norm(e - ends[0]))
        vb = (b_ - a_) / np.linalg.norm(b_ - a_) * (1 if b_[1] > a_[1] else -1)  # the key's +v (back), local
        sh = vb * (front - back) / 2
        return [tuple((Ms[o["half"]] @ [*(np.array(flip(c)) + sh), w, 1])[:2])
                for c in alice.footprint(o, o["key"]["w"] * alice.U - 2 * side, alice.U - front - back)]
    env_real = [MultiPoint(cap_at(o, P["skirt_bottom_out"]) + cap_at(o, P["lip"])).convex_hull for o in caps]
    cap_gap = min(e.distance(opening.boundary) if opening.contains(e) else -1.0 for e in env_real)
    top = lambda x, y: surface(Ms.values(), P["lip"], x, y)
    lt, rt, rb, v, lb = sharp
    back_mid = (ridge, lt[1] + (rt[1] - lt[1]) * (ridge - lt[0]) / (rt[0] - lt[0]))
    heights = {"front_left": top(*lb), "front_right": top(*rb), "front_v": top(*v),
               "back_left": top(*lt), "back_right": top(*rt), "back_centre": top(*back_mid)}
    # v2 (user): ONE plane truncates the peak behind the ridge: it holds the horizontal line on the rear face rear_cut["drop"]
    # below the peak height (BC) and the point A on the ridge crest rear_cut["back"] forward of the rear edge (on the roof);
    # everything above it goes. The plane meets each roof facet in a straight line from A to the rear face, so what is left
    # of the rear face's top is a triangle (base on the rear face at BC, between the facets; apex A) and the cut face is that
    # triangle in plan too. dz/dy < 0: the plane rises toward the front, the crest toward the back, so they only cross at A.
    rc_ = P["rear_cut"]
    yb_ = back_mid[1]
    z_bc = heights["back_centre"] - rc_["drop"]
    A_ = np.array([ridge, yb_ - rc_["back"], top(ridge, yb_ - rc_["back"])])
    k_dz = (A_[2] - z_bc) / (A_[1] - yb_)
    xs_ = []
    for lo_x, hi_x in ((lt[0], ridge), (rt[0], ridge)):  # where the roof on each side is at BC (monotone toward the ridge)
        for _ in range(60):
            mid_x = (lo_x + hi_x) / 2
            if top(mid_x, yb_) < z_bc:
                lo_x = mid_x
            else:
                hi_x = mid_x
        xs_.append((lo_x + hi_x) / 2)
    rear_cut = {"A": A_.tolist(), "bc": z_bc, "k": k_dz, "y_rear": yb_, "x": xs_,
                "points": [[xs_[0], yb_, z_bc], [xs_[1], yb_, z_bc], A_.tolist()],
                "face": [xs_[1] - xs_[0], rc_["drop"]], "plan": [[xs_[0], yb_], [xs_[1], yb_], [A_[0], A_[1]]]}
    # the wall left over the plate top where the cut plane passes over a pocket: the opening's outline (every 0.25 mm) inside
    # the cut's plan triangle, plane z less the plate top (w = 0) there. The cut triangle also clears the UDB bay (below)
    tri_ = Polygon(rear_cut["plan"])
    pw_ = []
    for g_ in getattr(opening, "geoms", [opening]):
        ring_ = g_.exterior
        for s_ in np.arange(0, ring_.length, 0.25):
            q_ = ring_.interpolate(s_)
            if tri_.buffer(0.01).contains(q_):
                pw_.append(z_bc + k_dz * (q_.y - yb_) - surface(Ms.values(), 0.0, q_.x, q_.y))
    rear_cut["pocket_wall_min"] = min(pw_) if pw_ else None
    rear_cut["pocket_margin"] = float(tri_.distance(opening))  # plan distance, cut triangle to the pockets (both halves)
    heights_cut = dict(heights, back_centre=z_bc)
    max_cut = max(max(heights_cut.values()), float(A_[2]))

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
    # M7: the rear pentagon. Its front corners (and V tip) rounded panel_front_r: the rabbet's inner corners, from below
    # v2: the sides are panel_half_w either side of the ridge (they were set by the rear TPU feet, now bumpons in the
    # body well outside them); the sides run straight to the back edge (no wings to the back corners), the rear band
    # narrows with them, body fills the back corners beside it
    xl, xr = ridge - P["panel_half_w"], ridge + P["panel_half_w"]
    r_ = P["panel_front_r"]
    raw0 = raw
    floor_at = lambda x, y: z_at(Ms["left" if x < ridge else "right"], FLOOR_W, x, y)
    # M7 (user, panel_t 4): the V moves back from panel_shift in 0.5 mm steps until the body over the panel keeps
    # base_min of floor over the rabbet ceiling (panel_t + base_min above the desk) everywhere over it
    for shift in np.arange(P["panel_shift"], P["panel_shift"] + 40, 0.5):
        cut_ = raw0.intersection(affinity.translate(footprint, 0, shift)).intersection(box(xl, -1e3, xr, 1e3))
        # its front corners R6 (the back ones stay square: they run out through the rear face)
        y_c = max(foot_pts[3][1], foot_pts[-1][1]) + shift
        raw = cut_.intersection(box(-1e3, -1e3, 1e3, y_c + 15)).buffer(-r_, quad_segs=16).buffer(r_, quad_segs=16).union(
            cut_.intersection(box(-1e3, y_c + 10, 1e3, 1e3)))
        panel = rnd(P["pocket_r"], raw).intersection(footprint)
        ov_ = opening.intersection(panel.buffer(P["panel_gap_print"]))
        if min(floor_at(x, y) for q in getattr(ov_, "geoms", [ov_]) for x, y in q.exterior.coords) >= \
                P["panel_t"] + P["base_min"] - 1e-6:
            break
    panel_shift = float(shift)
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

    # screws (M7, user: 4, in the recessed field at its 4 outer corners, just inside the border; no V-tip screw).
    # Their line runs panel_recess[1] + the head radius + screw_recess_margin in from the panel edge: the back pair
    # here; the side-front pair after the relief grooves (below)
    path = panel.buffer(-(P["panel_recess"][1] + P["screw_head"] / 2 + P["screw_recess_margin"]), join_style="mitre").exterior
    ptsp = [path.interpolate(t) for t in np.linspace(0, path.length, 6000)]
    y_back = max(foot_pts[0][1], foot_pts[2][1])
    backs = [min(ptsp, key=lambda q: math.hypot(q.x - x_, q.y - y_back)) for x_ in (xl, xr)]
    screws = backs  # bl, br (+ front-left, front-right below)
    insert_depths = [P["insert_hole_short"][1]] * 3

    # M4 rear lip: the panel strip rises up the rear face (z panel_t .. USB centre) as a visible band, the body cut
    # back to match (lip + print gap). It ends lip_end from the corners. M5 DFM: the body's lip pocket (cut from below)
    # had R1 inner corners (Ø2 tool); it now runs 4 mm out past the rear face (air) so it is >= 2 pocket_r wide and
    # takes an R3 opening: Ø6 from below. The lip is the pocket less the gap, so its inner end corners are R2.8.
    lip_end, lip_d, _ = P["strip_lip"]
    lip_top = P["panel_t"] + P["usb_opening"][1] / 2
    lip_line = ops.substring(back, lip_end, back.length - lip_end)
    band = lip_line.buffer(10, cap_style="flat")
    # M7 (user): each band end is one long diagonal from the top edge's end down to the panel's outer top corner at
    # the side rim (no flat run-out, no concave corner), so the lip and its pocket run out to the panel's ends
    band_x = ops.substring(back, P["rear_strip_end"] - 4, back.length - P["rear_strip_end"] + 4).buffer(10, cap_style="flat")
    raw_pocket = band_x.intersection(footprint.buffer(4.0, join_style="mitre")).difference(
        footprint.buffer(-lip_d - P["panel_gap_print"], join_style="mitre"))
    lip_pocket = raw_pocket.buffer(-P["pocket_r"], quad_segs=16).buffer(P["pocket_r"], quad_segs=16).simplify(0.002)
    # M7: its ends stop at the rabbet's side walls (the panel's ends + the gap); behind the rear face it is air
    pe = sorted(p_.x for p_ in back.intersection(panel_lean.boundary).geoms)
    g_ = P["panel_gap_print"]
    lip_pocket = lip_pocket.intersection(rabbet_lean.buffer(-0.01).union(box(pe[0] - g_ + 0.02, 0, pe[-1] + g_ - 0.02, 1e3).difference(footprint)))
    # lip and pocket run 4 mm past each end in plan (their R3 / R2.8 corners out of the way): the band's end is the
    # diagonal alone (a plan end at the seam point left a 0.2 mm notch in the end line). The pocket starts at the
    # seam (z panel_t), so below it the rabbet alone is the void.
    lip = band_x.intersection(footprint.buffer(4.0, join_style="mitre")).difference(
        footprint.buffer(-lip_d, join_style="mitre")).buffer(-P["pocket_r"] + P["panel_gap_print"], quad_segs=16).buffer(
        P["pocket_r"] - P["panel_gap_print"], quad_segs=16).intersection(panel_lean)
    # the diagonals in the rear view (x): foot at the panel's outer corner on the back line, top vertex where the M5
    # band's was (strip_lip[2] in from lip_end), so the top edge and its R6 corner stay put
    band_ends = [pe[0], pe[-1]]
    band_run = [P["band_end_run"]] * 2  # M7: the v6 diagonal (3.6 over 21.2, ~9.6 deg) from the narrowed panel's corners
    # M7 rear-face recess, in (x, z): the face is the panel's edge (z 0 .. panel_t) plus the band with its diagonal
    # ends, less the border; less a frame round the USB notch; split at the ridge (two lean planes)
    bb_, br_ = P["band_recess"]
    x0_, x1_ = band_ends
    z1_ = P["panel_t"]; z2_ = z1_ + P["usb_opening"][1] / 2
    # M8 (user): the face runs down past the panel's back edge, so its field has no border there: it wraps onto the
    # bottom recess (clipped at z -1, the cutters' floor)
    face_ = Polygon([(x0_, -5), (x1_, -5), (x1_, z1_), (x1_ - band_run[1], z2_), (x0_ + band_run[0], z2_), (x0_, z1_)])
    # v2 (user): its side borders are the underside field's (panel_recess[1], 3.5), so the two borders run on into each other
    # with no jog; the top and the diagonals keep band_recess[0]
    fld_ = face_.buffer(-bb_, join_style="mitre").intersection(box(x0_ + P["panel_recess"][1], -1e3, x1_ - P["panel_recess"][1], 1e3)) \
        .buffer(-br_, quad_segs=16).buffer(br_, quad_segs=16).intersection(box(-1e3, -1, 1e3, 1e3))
    sw_ = P["usb_neck"][0] / 2  # v2: the frame goes round the visible neck
    frame_ = box(ridge - sw_, z1_, ridge + sw_, z2_ + 5).buffer(bb_, quad_segs=16)
    fld_ = fld_.difference(frame_)
    band_recess = {"left": fld_.intersection(box(-1e3, -1, ridge, 50)), "right": fld_.intersection(box(ridge, -1, 1e3, 50))}
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
    # v2: the notch is stepped: the chamber (usb_slot_w wide, holds the board's rear end) from its inner end to the neck
    # step, which sits 0.25 mm behind the board's rear edge; then the neck (usb_neck[0] wide) out through the rear face.
    # Rounded in plan (pocket_r) so the Ø6 cutter from below can make it; the chamber's rear corners round into the
    # neck walls (a 2.5 mm step is narrower than R3), the board's R2 corners clear them
    y_step = udb_c[1] + bd / 2 + 0.25
    nw = P["usb_neck"][0] / 2
    chamber_len = max(y_step - (wall_y - P["pocket_r"]), 2 * P["pocket_r"] + 0.6)  # (>= 2 R3 arcs + a flat: or the lobes round away)
    notch = unary_union([box(ridge - sw, y_step - chamber_len, ridge + sw, y_step),
                         box(ridge - nw, y_step - 1.0, ridge + nw, back_mid[1] + 5 + P["pocket_r"])]).buffer(
        -P["pocket_r"], quad_segs=16).buffer(P["pocket_r"], quad_segs=16)
    usb_centre_z = P["panel_t"] + uh / 2
    # M5 UDB rest pad: the slot roof comes down to the board's back face over the board's rear edge (behind the bay,
    # 0.25 mm short of the edge), so plugging the USB can't flex the board. Across, it stops where the Ø6 ball for
    # the roof's R3 corners (axis usb_slot_w / 2 - usb_r from the ridge) would cut it; Fusion trims it to that ball.
    udb["pad"] = {"x": [ridge - (sw - P["usb_r"][0]), ridge + (sw - P["usb_r"][0])],
                  "y": [wall_y + 0.3, udb_c[1] + bd / 2 - 0.25], "z": [z_top, P["panel_t"] + uh + 0.05]}

    # v2 bumpons: 4 adhesive 3M SJ5302 in shallow locating recesses, the centres inset bumpon["inset"] from the two
    # desk-level footprint edges of each corner (the corners of the inset footprint): the front pair in the solid bezel
    # outside the pockets, the rear pair in the body beside the panel (under the rear pockets, where the body is thick)
    bd_ = P["bumpon"]
    cs_ = list(footprint.buffer(-bd_["inset"], join_style="mitre").exterior.coords)[:-1]
    lft_, rgt_ = sorted(cs_, key=lambda q: q[0])[:2], sorted(cs_, key=lambda q: -q[0])[:2]
    bumpons = [{"x": round(q[0], 4), "y": round(q[1], 4), "d": bd_["recess_d"], "depth": bd_["recess_depth"],
                "name": nm_} for pair_, nms_ in ((sorted(lft_, key=lambda q: -q[1]), ("rear left", "front left")),
                                                  (sorted(rgt_, key=lambda q: -q[1]), ("rear right", "front right")))
               for q, nm_ in zip(pair_, nms_)]

    # M7 panel recess (underside field), clear of the screw heads by panel_recess[3]
    rd_, rb_, rr_, rc_ = P["panel_recess"]
    # (each pad joined to the border by the shortest way: rounded tabs, no islands in the field)
    # M8 (user): no border along the back edge, so the field runs out through it onto the band. The back chain
    # (within 2 mm of the top: the two corners and the shallow ridge kink) is lifted 30 mm before the inset, so the
    # side borders stay straight and the back border is pushed clear; the field is then clipped to the panel
    qc_ = list(panel.exterior.coords)[:-1]
    ext_ = [(x_, y_ + 30.0) if y_ > panel.bounds[3] - 2.0 else (x_, y_) for x_, y_ in qc_]
    recess_open = Polygon(ext_).buffer(-rb_, join_style="mitre")
    # v2 (user): no taper: the side borders keep rb_ (3.5) to the back edge, where the rear-face field's side border (below) is
    # the same width. The deep field is opened on this unclipped shape, so the back edge does not round its corner
    # (that left a 0.4 deep tongue beside the outer seats)
    recess_open = recess_open.buffer(-rr_, quad_segs=16).buffer(rr_, quad_segs=16)
    panel_recess = recess_open.intersection(panel.buffer(0.5, join_style="mitre"))
    panel_recess = max(getattr(panel_recess, "geoms", [panel_recess]), key=lambda q: q.area).simplify(0.004)  # (no 0.001 mm segments for Fusion's sketch)

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
              "socket": [bot_w - P["socket_h"], bot_w], "jst": [bot_w - P["jst"][2], bot_w]}
    st, c, hw, U = P["stab"], P["cutout"] / 2, P["switch_body"] / 2, alice.U
    halves = {}
    for h, sgn in (("left", 1), ("right", -1)):
        M = Ms[h]
        pcb, plate = frozen[h]["pcb"], frozen[h]["plate"]  # v2: frozen from v1 (the pocket walls were grown round them)
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
        # v2: the 5 C-clips of this half, at the given PCB-local edge points (v1 PCB frame: moved with the keys)
        socks_real = [Polygon([(k["x"] + x * math.cos(math.radians(k["ang"])) - y * math.sin(math.radians(k["ang"])),
                                k["y"] + x * math.sin(math.radians(k["ang"])) + y * math.cos(math.radians(k["ang"])))
                               for x, y in SOCKET_REAL]) for k in keys]
        clips = place_clips(pcb, [(x + frozen[h]["du"], y) for x, y in P["clip_pts"][h]], socks_real, stabs, pocket)
        halves[h] = {"matrix": M.tolist(), "keys": keys, "blockers": blockers, "pcb": pcb, "plate": plate,
                     "cutouts": [key_rect(k, -c, -c, c, c) for k in keys], "stabs": stabs,
                     "switches": [key_rect(k, -hw, -hw, hw, hw) for k in keys], "sockets": sockets,
                     # 0.05 mm shy of the grid per side so neighbours share no faces in Fusion (the opening uses
                     # the full §6.1 envelopes)
                     "keycaps": [key_rect(k, -k["w"] * U / 2 + .05, -U / 2 + .05, k["w"] * U / 2 - .05, U / 2 - .05)
                                 for k in keys],
                     "jst": jst, "jst_pocket": pocket,
                     "clips": clips,
                     "plate_bbox_world": [round(f(q[i] for q in corners3), 4) for f in (min, max) for i in range(3)],
                     # v2: what each flat placeholder's bodies must add up to in Fusion (mm3; fusion_build.check_volumes):
                     # shredded bodies (a feature that touched more than its target) fail it loudly
                     "expect_vol": {
                         "Plate": round((plate.area - unary_union([key_rect(k, -c, -c, c, c) for k in keys] + list(stabs)).area) * pt, 2),
                         "Pcb": round(pcb.area * P["pcb_t"], 2),
                         "SocketKeepout": round(unary_union(sockets).area * P["socket_h"], 2),
                         "JST": round(jst.area * P["jst"][2], 2), "JSTPlugPocket": round(pocket.area * P["jst"][2], 2),
                         "SwitchBottom": round(unary_union([key_rect(k, -c, -c, c, c) for k in keys]).area * -layers["switch_bottom"][0], 2),
                         "SwitchTop": round(unary_union([key_rect(k, -hw, -hw, hw, hw) for k in keys]).area * P["switch_top_h"], 2),
                         "KeyEnvelope": round(unary_union([key_rect(k, -k["w"] * U / 2 + .05, -U / 2 + .05, k["w"] * U / 2 - .05, U / 2 - .05)
                                                           for k in keys]).area * P["keycap_h"], 2)}}

    # M5/M6 solid body. The pocket floor (op 2, from the top) is one plane per half parallel to its PCB with shallow
    # relief grooves between the rows (below) and a recess under each PCB clip. Islands stand up from it: a boss over
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
    # v2 C-clip recesses, in the floor plane's local coordinates (which are the PCB's: the plane is parallel to it): along
    # the PCB edge's tangent recess[0] long; the inner side a fixed recess[1] - snap_gap (2.9) in from the PCB edge, out to the pocket wall
    # (found along the edge normal in the floor plane), which it is cut to (no undercut): its width is 2.9 + the wall gap there,
    # 3.2 at the back edge .. 4.7 at the front (the vertical wall and the tilted PCB), not a constant. R clip_r corners (Ø3 tool). Its
    # lead-in is a 45 deg taper: `mouth` = the recess grown by its depth (cut to the pocket), tapered in over that depth by
    # Fusion; `*_w` are the same in the world, on the floor plane.
    rl_, rw_, rd_ = P["clip_recess"]
    cl_ = P["clip"]
    wb_ = -(P["plate_to_pcb"] + P["pcb_t"])  # the PCB underside plane
    w_bot = fw - rd_  # the recess bottom
    w_slot = wb_ + cl_["slot"]  # the lip's underside (the PCB top is 0.1 over it: it grips)
    w_top = w_slot + cl_["lip"]
    pre = {}
    for h, d in halves.items():
        Mh = Ms[h]
        o_levels = {w_: to_local(Mh, w_, opens_h[h]) for w_ in (fw, w_bot, wb_, w_top)}  # the (vertical) wall seen in each plane
        o_at = lambda w_, Mh=Mh, h=h: to_local(Mh, w_, opens_h[h])
        A_fw = [Mh[0, 0], Mh[0, 1], Mh[1, 0], Mh[1, 1], Mh[0, 2] * fw + Mh[0, 3], Mh[1, 2] * fw + Mh[1, 3]]
        for q in d["clips"]:
            c_, t_, n_ = (np.array(q[k_]) for k_ in ("edge_pt", "t", "n"))
            def wall_at(w_, s_=0.0, c_=c_, t_=t_, n_=n_, o_levels=o_levels):  # the wall's distance from the PCB edge along the normal, in the plane w_ (s_ along the edge)
                c0_ = c_ + t_ * s_
                hit = LineString([c0_, c0_ + n_ * 4.0]).intersection(o_levels[w_].exterior)
                return min(Point(c0_).distance(p_) for p_ in getattr(hit, "geoms", [hit]))
            dw_ = wall_at(fw)
            fr_ = lambda s_, q_, c_=c_, t_=t_, n_=n_: tuple(c_ + t_ * s_ + n_ * q_)
            # across the edge: from recess width less the nominal gap under the PCB (3.8 - 0.9 = 2.9: the 2.5 ledge, the 0.4 spare)
            # out past the pocket wall (the tilt makes the wall's offset 0.3 .. 1.9 mm from the PCB edge at the floor plane), then
            # cut to the pocket: the wall side is the wall itself (no undercut, no rounded corners there), the R clip_r corners
            # are the inner ones
            raw_x = Polygon([fr_(-rl_ / 2, -(rw_ - P["snap_gap"])), fr_(rl_ / 2, -(rw_ - P["snap_gap"])), fr_(rl_ / 2, dw_ + 0.5),
                             fr_(-rl_ / 2, dw_ + 0.5)])
            rr_x = raw_x.buffer(-P["clip_r"], quad_segs=16).buffer(P["clip_r"], quad_segs=16)  # (corners past the wall: the wall side stays sharp)
            mo_x = rr_x.buffer(rd_, quad_segs=16)  # the lead-in's top outline, uncut: Fusion tapers it 45 deg down to rr_x, then trims to the wall
            rr_, mo_ = rr_x.intersection(o_levels[fw]), mo_x.intersection(o_levels[fw])
            pre[(h, q["name"])] = {"q": q, "c": c_, "t": t_, "n": n_, "wall_at": wall_at, "o_at": o_at, "rr_x": rr_x}
            q.update({"recess": rr_, "mouth": mo_, "wall_gap": float(dw_), "recess_w": affinity.affine_transform(rr_, A_fw),
                      "mouth_w": affinity.affine_transform(mo_, A_fw), "mouth_ext_w": affinity.affine_transform(mo_x, A_fw), "recess_x": rr_x})
    # the two printed variants (clip_variants): one profile / plan / lattice for every spot each serves
    variants = clip_variants(pre, w_bot, wb_, w_slot, w_top)
    ld_ = cl_["lead"] / math.tan(math.radians(cl_["lip_lead"]))
    cell, cw_ = cl_["lattice_cell"], cl_["lattice_wall"]
    hy_ = cell / math.sqrt(3)  # pointy-top hexagon, across flats `cell` (along the edge), 2 hy_ vertex to vertex
    nh_ = int((cl_["len"] - 2 * 0.7 + cw_) // (cell + cw_))  # 3 cells, 0.75 end walls
    wc_ = (w_bot + wb_) / 2  # the middle of the ledge's height
    hexes = [[(a0 + hy_ * math.cos(math.radians(60 * k_ + 30)), wc_ + hy_ * math.sin(math.radians(60 * k_ + 30))) for k_ in range(6)]
             for a0 in [(i_ - (nh_ - 1) / 2) * (cell + cw_) for i_ in range(nh_)]]
    for vn_, v_ in variants.items():
        v_["lattice"] = hexes
    for h, d in halves.items():
        Mh = Ms[h]
        for q in d["clips"]:
            c_, t_, n_ = pre[(h, q["name"])]["c"], pre[(h, q["name"])]["t"], pre[(h, q["name"])]["n"]
            v_ = next(v__ for v__ in variants.values() if (h, q["name"]) in v__["spot_keys"])
            Lc = np.array([[n_[0], 0, n_[1], c_[0]], [n_[1], 0, -n_[0], c_[1]], [0, 1, 0, 0], [0, 0, 0, 1]])
            q.update({"variant": v_["name"], "plan": v_["plan"], "profile": v_["profile"], "lattice": hexes,
                      "matrix": (Mh @ Lc).tolist(), "wall_n": [[w_, float(pre[(h, q["name"])]["wall_at"](w_))] for w_ in (w_bot, wb_, w_top)]})
    for v_ in variants.values():
        v_.pop("spot_keys")
    islands = []
    bosses = [(f"insert boss {i + 1}", q.x, q.y, P["insert_hole"][0] / 2, P["panel_t"] + insert_depths[i])
              for i, q in enumerate(screws)]
    bosses += [(f"UDB insert boss {i + 1}", x, y, P["udb_insert"][0] / 2, udb["mount_z"][0] + P["udb_insert"][1])
               for i, (x, y) in enumerate(udb["mounts"])]
    for kind, x, y, ri, itop in bosses:  # >= 5 mm of material over each insert under a pocket (5.2: measured)
        top = itop + 5.2
        for h, o_ in opens_h.items():
            if o_.distance(Point(x, y)) < ri + 5:
                isl = merge(Point(x, y).buffer(ri + 5).intersection(o_), o_)
                low_ = o_.difference(zp_above(Ms[h], top + 0.3 - fw + wb))  # where the floor plane is below its top (+0.3)
                if not kind.startswith("UDB"):
                    # M7: 5 mm of material in 3D from the insert hole: d mm out from its edge the floor needs only
                    # sqrt(25 - d^2) over the insert top (5 straight up, nothing at 5 to the side)
                    c_ = Point(x, y)
                    low_ = unary_union([c_.buffer(ri + d_ + 0.5).difference(c_.buffer(ri + d_)).intersection(
                        o_.difference(zp_above(Ms[h], itop + math.sqrt(25 - d_ * d_) + 0.2 - fw + wb)))
                        for d_ in np.arange(0, 5, 0.5)] + [c_.buffer(ri).intersection(
                        o_.difference(zp_above(Ms[h], itop + 5.2 - fw + wb)))])
                eff = isl.intersection(low_.buffer(0.5)) if not low_.is_empty else Polygon()
                if kind.startswith("UDB") and not eff.is_empty:
                    # M6 (undercut check): a UDB boss clipped where the floor rises past its top left zero-area slivers
                    # on its top at the wall; it stands on its whole disc instead, top >= 0.5 over the floor there
                    eff = isl
                eff = max(getattr(eff, "geoms", [eff]), key=lambda e: e.area) if not eff.is_empty else eff
                if not eff.is_empty and eff.area > 2.0:
                    ztop_ = max(top, floor_under(h, eff) + 0.5)  # its flat top clears the tilted floor under it by >= 0.5 (a top grazing the floor left slivers)
                    if kind.startswith("UDB"):
                        # v2: a UDB boss stays >= 2 mm under the PCB everywhere: its flat top is level but the PCB tilts
                        # down toward the outer wall, so where the PCB underside is lower than top + 2 (the boss's fillet
                        # out to the pocket wall, 2.6 mm further out than in v1 once the halves moved apart) it is cut
                        # back along that line (the rule is not relaxed); the part over the insert is well inside
                        cut_ = eff.intersection(zp_above(Ms[h], ztop_ + 2.0 + 0.02))
                        cut_ = max(getattr(cut_, "geoms", [cut_]), key=lambda e: e.area) if not cut_.is_empty else cut_
                        if cut_.is_empty or not cut_.buffer(1e-6).contains(Point(x, y).buffer(ri + 2.0)):
                            raise SystemExit(f"{kind}: cut back to 2 mm under the PCB, it no longer covers its insert")
                        eff = cut_
                    islands.append({"poly": dedup(eff), "z": [z_base - 1.0, ztop_], "kind": kind, "half": h,
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
        rf = r3
        air_ = loc.difference(j_).buffer(-rf, quad_segs=16).buffer(rf, quad_segs=16)
        j_ = j_.union(loc.difference(air_.buffer(0.05)).intersection(j_.buffer(rf))).buffer(0)  # (M6: 0.01 left 0.03-0.04 mm slots)
        # (M6: healed by a 1 um closing: a float-noise gap between the pocket part and its wall run made the largest
        # piece below the pocket part alone, leaving a 0.03 mm slot between some bosses and the wall)
        j_ = j_.union(j_.buffer(0.5).difference(o_)).buffer(0.001, join_style="mitre").buffer(-0.001, join_style="mitre")  # (that fill runs into the wall too)
        q["join"] = dedup(Polygon(max(getattr(j_, "geoms", [j_]), key=lambda e: e.area).exterior))  # (pinholes filled)
    # (the channels run under the hung board, below its standoffs, and open into the bay)
    channels = [ln.buffer(P["cable_channel"] / 2) for ln in lines]
    chan = opn3(unary_union(channels).intersection(cavity))
    # relief grooves. M6 (user): one per key row, under that row's hotswap sockets: each socket keep-out (projected
    # along the PCB normal onto the floor plane) grown socket_margin, the gaps between neighbouring sockets in the row
    # closed, so it follows the row's curve and stagger; a semicircular notch at the row's middle key, R3 corners
    # (>= Ø6 tool), stopping groove_wall short of the pocket walls. Kept out of the bosses, JST breakthroughs
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
        # M7: >= base_min_groove of body under a groove: over the desk in front, over the rabbet ceiling over the panel
        pz_ = rabbet["print"]
        rule_ok = zp_above(M, P["base_min_groove"] + gd - fw + wb).difference(pz_).union(
            zp_above(M, P["panel_t"] + P["base_min_groove"] + gd - fw + wb).intersection(pz_))
        # v2 (user, approved map): the grooves may run into the JST breakthroughs / cable channels (no keep-out: the 3 mm
        # rule over the channels is tested); R groove_r (2) corners; clip_keep (1.0) off each C-clip's mouth chamfer, which
        # lets the top row stay one groove past the clip (R3 and 0.5 left a 43-51 mm2 fragment split by a 0.1-0.5 mm land)
        keep_out = unary_union([q["poly"].buffer(P["island_clear"]) for q in islands if q["half"] == h] +
                               [q["mouth_w"].buffer(P["clip_keep"], quad_segs=16) for q in d["clips"]])
        gro = (lambda r_: r_.buffer(-P["groove_r"], quad_segs=16).buffer(P["groove_r"], quad_segs=16))(gro.intersection(rule_ok).difference(keep_out))
        gro = unary_union([q for q in getattr(gro, "geoms", [gro]) if q.area > 20])
        gro = shapely.remove_repeated_points(gro, 0.02).buffer(0)  # (M6: drops the 0.01 mm jogs the booleans leave: sliver faces)
        floor[h].update({"grooves": dedup(gro), "groove_w": [fw - gd, fw]})  # off the walls: no shared faces
    # M7 side-front panel screws: from the recessed field's side-front corner, the nearest spot (0.5 mm grid, within
    # 30 mm) where the body over the insert keeps >= 5 mm in 3D (sqrt(25 - d^2) over the insert top at d mm out from its
    # edge, + 0.2), counting any relief groove over it: so no boss is needed and the grooves stay whole
    itop_ = P["panel_t"] + P["insert_hole_short"][1]
    gro_ = unary_union([floor[h]["grooves"] for h in floor])
    def body_top(x, y):
        return floor_at(x, y) - (P["relief"][1] if gro_.contains(Point(x, y)) else 0.0)
    def insert_ok(x, y):
        return all(body_top(x + (2 + d_) * math.cos(a), y + (2 + d_) * math.sin(a)) >= itop_ + math.sqrt(25 - d_ * d_) + 0.2
                   for d_ in (0.0, 1.0, 2.0, 3.0, 4.0) for a in np.linspace(0, 2 * math.pi, 13)) and \
            all(body_top(x + r_ * math.cos(a), y + r_ * math.sin(a)) >= itop_ + 5.2 for r_ in (0.0, 1.0)
                for a in np.linspace(0, 2 * math.pi, 9))
    fld = panel_recess.buffer(-(P["screw_head"] / 2 + 0.5))
    # M8 (user): the two front screws are replaced by one at the panel's V point (on the ridge, just inside the border):
    # the nearest spot to the V where the field and the 3D insert rule both hold
    apex = min(ptsp, key=lambda q: q.y + 3 * abs(q.x - ridge))
    grid = [Point(apex.x + dx, apex.y + dy) for dx in np.arange(-10, 10.01, 0.25) for dy in np.arange(0, 30.01, 0.25)]
    v_ = min((q for q in grid if fld.contains(q) and insert_ok(q.x, q.y)), key=lambda q: q.distance(apex))
    fronts, screw_front_offset = [v_], [round(v_.distance(apex), 1)]
    screws = backs + fronts
    # v2 seat pads: the field is only screw_seat[0] deep within screw_head / 2 + screw_seat[1] of each screw (the pad
    # merges into the border), panel_recess[0] deep elsewhere: the deep part, opened with R3 (the Ø6 flat end mill),
    # is cut after the seat-depth field. The countersink cone starts at the seat depth, so it leaves what v1 had.
    pads = unary_union([Point(q.x, q.y).buffer(P["screw_head"] / 2 + P["screw_seat"][1], quad_segs=32) for q in screws])
    panel_recess_deep = recess_open.difference(pads).buffer(-P["panel_recess"][2], quad_segs=16).buffer(
        P["panel_recess"][2], quad_segs=16).intersection(panel_recess).simplify(0.004)  # (opened before the back-edge clip: no tongue)
    # M7: the cavity is no longer one void: the insert wall that matters is to the voids cut from below (channels, bay)
    walls["insert_to_cavity"] = min(unary_union([chan, bay]).distance(q) for q in screws) - P["insert_hole"][0] / 2
    # v2: each C-clip's recess (and its chamfered mouth) lies on the floor plane, so the body under it must keep
    # clip_floor_min - recess depth: checked here (a local exception to the base_min rule, which counts the floor plane)
    for h, d in halves.items():
        for q in d["clips"]:
            q["floor_z_min"] = min(z_at(Ms[h], fw, x, y) for x, y in q["mouth"].exterior.coords)
            if q["floor_z_min"] < P["clip_floor_min"] - 1e-6:
                raise SystemExit(f"{h} clip {q['name']}: the floor under its recess is {q['floor_z_min']:.2f} mm above the desk (< {P['clip_floor_min']})")
    cavity_steps = {"channels": channels, "chan": chan, "chan_z": [-1.0, P["panel_t"] + P["chan_h"]],
                    "stubs": unary_union(stubs), "floor": floor, "islands": islands}

    minx, miny, maxx, maxy = outline.bounds
    return {
        "params": P, "clip_variants": variants, "layers": layers, "udb": udb, "socket_box": SOCKET, "floor_w": FLOOR_W, "pcb_mid_w": PCB_MID_W,
        "ridge_x": ridge, "y_front": y_front, "lift": lift, "h_front": min(heights["front_left"], heights["front_right"]),
        "max_height": max(heights.values()), "heights": heights, "heights_cut": heights_cut, "max_height_cut": max_cut,
        "rear_cut": rear_cut, "floor_min_z": low + lift, "cap_gap": cap_gap, "web_min": web_min, "web_sym": web_sym,
        "outline_size": [maxx - minx, maxy - miny],
        "key_gap": key_gap, "v_offset": sharp[3][0] - ridge, "v_offset_equal_bezels": v_off0, "front_bezels": front_bezels,
        "_shapes": {"envelopes": env, "opening": opening, "outline": outline, "outline_sharp": outline_sharp,
                    "footprint": footprint, "panel": panel, "rabbet": rabbet, "cavity": cavity},
        "screws": [[round(p.x, 4), round(p.y, 4)] for p in screws], "insert_depths": insert_depths, "screw_front_offset": screw_front_offset, "panel_recess": panel_recess, "panel_recess_deep": panel_recess_deep, "pocket_growth": [pocket_growth.area, pocket_growth_max], "panel_shift": panel_shift, "band_recess": band_recess,
        "cavity_steps": cavity_steps, "bay": bay, "bay_z": [-1.0, z_top + P["udb_mount"][1]], "notch": notch, "notch_z": [-1.0, P["panel_t"] + uh],
        "usb_centre": [ridge, usb_centre_z], "bumpons": bumpons, "walls": walls, "lower_band": lower_band,
        "panel_lean": panel_lean, "rabbet_lean": rabbet_lean, "lip": lip, "lip_pocket": lip_pocket,
        "rear_zone_panel": rear_zone["panel"], "rear_zone_body": rear_zone["body"],
        "lip_z": [P["panel_t"], lip_top], "lip_ends": band_ends, "lip_run": band_run, "lip_pocket_z": [P["panel_t"] - 0.01, lip_top + P["panel_gap_print"]],
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
    print(f"halves spread {P['half_spread']} mm; ridge at the R2 midpoint (key gap {g['key_gap'][0]:.2f} .. {g['key_gap'][1]:.2f}); "
          f"outline centre {g['outline_offset']:+.2f} mm off it; side bezels {P['bezel_side']} each; "
          f"V front point {g['v_offset']:+.2f} mm off the ridge")
    print(f"outline {g['outline_size'][0]:.2f} x {g['outline_size'][1]:.2f} mm, {len(g['screws'])} screws -> {out}")
    fl = g["cavity_steps"]["floor"]
    print("pocket floor: plane parallel to each PCB, " + "; ".join(f"{h} z {min(G_ := [z_at(np.array(g['halves'][h]['matrix']), f['w'], x, y) for x, y in f['open'].exterior.coords]):.2f}..{max(G_):.2f}, grooves {f['grooves'].area:.0f} mm2 at -{P['relief'][1]}" for h, f in fl.items()))
    print("islands: " + ", ".join(f"{q['kind']} top z " + (f"{q['z_low']:.2f}..{q['z_high']:.2f}" if 'w_top' in q else f"{q['z'][1]:.2f}")
                                  + f" (floor {q['z_floor']:.1f})" for q in g["cavity_steps"]["islands"]))
    print("walls (plan, mm): " + ", ".join(f"{k} {v:.2f}" for k, v in g["walls"].items()))
    for h, d in g["halves"].items():
        jc = d["jst"].centroid
        print(f"{h}: {len(d['stabs'])} stab cutouts, JST at ({jc.x:.1f}, {jc.y:.1f}), {len(d['clips'])} C-clips (floor under their recesses "
              f"{min(q['floor_z_min'] for q in d['clips']):.2f} mm, edge deviation <= {max(q['edge_dev'] for q in d['clips']):.2f})")
    print(f"pocket grown round the frozen v1 PCB / plate: {g['pocket_growth'][0]:.2f} mm2, at most {g['pocket_growth'][1]:.2f} mm out")
