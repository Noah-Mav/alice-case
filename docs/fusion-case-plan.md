# Alice 40% case + plate in Fusion: build plan

**For:** a Claude Code agent working in this repo, driving Autodesk Fusion through MCP.
**Builds:** a tented, unibody, CloudNine-styled case for the layout this repo's app designed, plus two plates, placeholder electronics and print/CNC exports.

Read this whole file before starting. Section 4's numbers were decided at the start, but many have since changed: see "Status and decisions" below. Section 10 lists the few things to check with the user, but the plan doesn't block on any of them.

---

> **Reading guide.** Sections 1 to 11 below are the **original plan** (written before M1). Parts the build has since moved away from are marked **SUPERSEDED** and point at the table in "Status and decisions". Where the two disagree, the table and `case/geometry.py` (the `P` dict) win. The files `case/geometry.py`, `case/test_geometry.py`, `case/fusion_build.py` and `case/README.md` are the working record; see the README for how to rebuild.

## Status and decisions (as built, 2026-10-18)

State: milestones M1 to M6 done. The Fusion design "Alice Case" (Default Project) holds the model; the final scripts and JSON are in `case/checkpoints/stepped-centre/` (earlier state: `case/checkpoints/2026-10-17-1910/`). All values below come from the `P` dict in `case/geometry.py`. The layout is `~/Documents/layout2.json` (40%, 41 keys).

Resulting size: outline 280.46 x 107.12 mm, front corners 15.91 / 15.55 mm high, front V 23.95 mm, back centre 35.22 mm (so 40 mm stock plus skim is enough).

| Topic | Old (original plan) | New (as built) | Why |
|---|---|---|---|
| Typing angle `typing_angle` | 7 deg | **6 deg** | user: back wall too tall |
| Tent `tent` | 5 deg per half | **4 deg** | user: back wall too tall |
| Lip `lip` | 3.5 mm | **2.0 mm** (`stack_raise` 1.5: the plate/PCB/keycap stack sits 1.5 mm higher in an unchanged shell) | user: lower bezel top; Cherry skirt at bottom-out (1.6) still sits under it; outside heights unchanged (within 0.02 mm) |
| Panel `panel_t` | 4.0 mm | **3.0 mm** | sleekening; `floor_above_panel` 3 -> 2 with it |
| Snap gap `snap_gap` | 0.75 mm | **0.9 mm** | vendors quote 0.8 to 1 mm; gap measures 0.81 to 0.99 mm over the PCB height because the PCB is tilted |
| PCBsnaps | 3 per half, 10 x 3 x 5.6 mm wedge box | **4 per half (2 front, 2 back), as close to the corners as allowed.** Placeholder is the real shape: a staple (Pi) 20 mm long, 8.5 mm centre notch, reach 2.5 mm (`snap`, `snap_spine` 0.6, `snap_drop` 2.5). Real parts are silicone. | the real PCBsnap is about 20 mm long with a notch, not a wedge; sizes are estimates from photos (+-30 %) |
| Snap posts ("pillars", in the snap's notch) | 8 x 3.5, R1 | **6 mm wide x 3.5 deep, top 0.25 mm under the PCB, parallel to it, R1.5 fillets into the wall** (`pillar`, `pillar_fillet`) | 6 mm clears the legs of the 8.5 notch; R1.5 means a Ø3 tool, R1 is too long and thin in hardwood |
| Pocket floor | `floor_clear` 3 mm under the PCB, plain | **One flat plane per half, parallel to its PCB, 4.5 mm under the PCB underside, with socket-aligned grooves** (`relief` 7 wide x 1.25 deep, `socket_margin` 1.0, `socket_bridge` 3.0) **and a flat 4 mm wall band** (`groove_wall`) for the snap legs and posts. Air under the PCBs 4.50 to 5.75 mm. | Neo65-style floor photo; sockets need room, the walls must stay flat for the snaps |
| Body underneath | big bottom cavity, 14 mm ledge, two terraces | **Solid body.** Only the UDB bay, two 13 x 4 mm cable channels with JST breakthroughs, and the insert bosses are cut from below. | stiffer, simpler to machine, enough room for the cables |
| Daughterboard (UDB) | on the panel, on 0.5 mm washers | **Hung upside down from the body**, 0.5 mm under the slot roof; two front standoffs Ø6 x 1.0 with M2 inserts (`udb_mount`, `udb_insert`); rear edge on a **rest pad**. The panel carries nothing. | the 22 mm slot needs the board to pass the rear wall; a 5 mm wall leaves no room for rear screws |
| Screws | 6 to 8 M3, 4 at the corners | **6 M3**: 4 panel corners (under the feet), front at the V point, one at the back middle shifted clear of the UDB bay. **Short inserts at the two back corners** (`insert_hole_short` 4 x 4 mm; the others 4 x 6) | user: no extra height at the back; the back-corner screws sit under the foot pocket floor |
| Panel back | strip stops 10 mm short of each corner (`rear_strip_end`) | **Square:** `rear_strip_end` = `rim` = 6 mm, so the back edge runs straight into the side rims | no step under the back corners |
| Feet | 4 bar feet 28 x 5 mm | **28 x 8 mm**, removable press-fit **TPU** (`foot_fit` 0.15 per side) with **2 pegs each** (Ø3 x 2 mm holes through the panel, `foot_peg`) | user; pull a foot by hand to reach its screw |
| USB opening | 12 x 7.2 mm | **22 x 7.2 mm with R3 on all four corners** (`usb_slot_w`, `usb_r`) | the board has to pass through the rear wall; R3 is the Ø6 ball mill. The floor R3 clears the UDB corners by 0.3 mm |
| Rear band | trapezoid-ish strip, square ends | **Rear band with diagonal ends (1:2, about 27 deg) and R6 top corners** (`strip_lip` [20, 2.5, 7.2], `strip_lip_r` 6), the diagonal runs straight to the desk | user screenshots: the old step and notch at the ends |
| Crease | 10 mm below the top, even all round, lean 6 deg | **9 mm, lean 8 deg** (`crease_depth`, `lower_cant`). **Deepening** on the ends and back (the crease follows the surface down); **horizontal on the front** (`crease_mode` = `front_horizontal`, permanent, the TODO to revert it was dropped) | user chose the look after a trial; front level at z 6.73 |
| Bezels | side / front / back 6 / 8 / 11 mm | **Equal 6 mm side bezels; front 7 (7.40 left / 7.00 right, see V); back 9.5 mm.** The ridge sits at the **key-gap midpoint** (`half_spread` 1.2 per half); the outline centre is **2.31 mm off the ridge** (the right half is about 4.6 mm wider than the left, no x shift can change that) | user: equal sides, symmetric web around the ridge |
| Front V | front V's inner corner 1.79 mm right of the ridge | **V on the ridge:** left front bezel 7.40, right 7.00; front screw moved with it | user: V should meet the ridge |
| Centre web | convex-hull web (straight runs between row ends) | **Stepped, key-hugging** (`web_mode` "stepped": the split follows the keys, every web corner R3), spread 1.2 mm per half, web at least 9.5 mm. `ALICE_WEB_MODE=straight` still builds the hull version. | hull left up to 7 mm of gap to the keycaps; the old R0.5 corners made lobes and an S-jog |
| Opening edges (front / back rows) | cusps between keys | **Cusps smoothed:** notches under 1 mm deep and wider than tall are filled with an R100 closing (`row_smooth_r`, `row_smooth_depth`); R100 keeps 12 mm of straight wall per key for the snaps | user screenshot |
| Sleekening (M5) | panel 4, bezels front/back 8/11, crease 10, lean 6, floor rule +3, M3 hole 6.5 | panel 3, bezels 7/9.5, crease 9, lean 8, floor rule +2, M3 hole 6.0; `floor_clear` 2.5 was tried and reverted (the JST header hits the floor) | user asked for a sleeker case |
| CloudNine | design reference, numbers to follow | **Style reference only.** Functional rules (walls, tool radii, clearances) stay hard; styling may deviate to look better | user decision |

Checks (last build, `case/out/fusion_build.log`): all PASS: no interference between the case and 204 placeholder bodies plus the UDB; snap gap 0.9 +- 0.05 at PCB mid-thickness; USB 22.00 x 7.20, 0.105 mm off the receptacle; thinnest wall 5.00 mm; lip 2.000 mm at every sample; crease rule 0.0003 mm; lower band 6 planes at 7.98 to 8.00 deg; undercut check 0 unreachable faces on Body and Panel.

### Open items

1. **Measure a real PCBsnap** (notch width, length, leg drop, bar height, reach, spine). The 20 / 8.5 / 2.5 sizes are estimates from photos. If the real notch is narrower than about 8.5 mm, revisit the post width (6) or its R1.5 fillets.
2. **The user will buy silicone PCBsnaps, 2 sets of 6** (8 used, 4 spare). Printed TPU stand-ins (`PCBsnapTPU`, one watertight body) are for fit tests only; silicone replaces them.
3. **Wood back-corner inserts must be 4 mm long or less** (a short M3 insert, or print M3 x 3 heat-set in Ø4.0 x 4.0). If none exists, move those two screws (option: shift them) or accept more height.
4. **Fusion flakiness and the two-step build.** The MCP call times out at about 60 s while the build carries on. In "Alice Case" the full build (build plus checks in one script) died or stopped silently twice, and Fusion rolls back a script that dies, model included. Workaround: build with `NO_CHECKS`, then run the checks as separate calls. See `case/README.md`.
5. Smaller notes: the panel has a 26.6 deg knife edge at each band foot (fine in aluminium or print, fragile in brass); the undercut check's sliver and crevice rules are loose at the UDB boss tops (a handful of "graze" faces, under 0.03 mm wide), so inspect once in CAM; Fusion "Alice Case" version 4 appeared during a rolled-back build and was not inspected.

---

## 1. What the user asked for (requirements)

1. A **case and plate** for the Alice layout currently loaded in `alice.py`.
2. **Mounting: PCB snaps** *(gap now 0.9 mm, 4 staple-shaped snaps per half; see Status)*. This means the Nuxros/Geon **PCBsnap**: elastomer pieces clipped onto the PCB edge that wedge against the case wall. The case's job is to provide an accurate **0.75 mm PCB-edge-to-wall gap** at PCB height.
3. **7° typing angle**, front to back. *(SUPERSEDED: 6°, see Status.)*
4. **5° tent** per half, inner edge higher. *(SUPERSEDED: 4°.)* The two halves fold down from a centre ridge.
5. **Unibody body.** A **removable bottom panel** gives access to mount the daughterboard and route the cables.
6. **Two PCBs, one per half,** each linked to a **central daughterboard** by a JST cable. Model all three as placeholders.
7. The bottom panel is **inset**. A rim about one side-bezel wide (6 mm) stays all the way round, **except at the back**. There the panel runs out to the rear face as a visible strip, and the **USB-C opening** sits on that seam. CloudNine's rear accent strip is the same idea.
8. **Prototype printed; final CNC.** The final is most likely **hardwood**, possibly aluminium, machined from two sides (one flip).
9. **Look:** Machina **CloudNine** design language (section 5).
10. **Room for artisan keycaps** around the edges: no interference with most artisans.

## 2. Driving Fusion

The user runs Claude Code in a terminal. Fusion build 2705.1.30 is installed, and the `API/Scripts` and `API/AddIns` folders are empty.

**Primary option: Fusion's built-in MCP server** (shipped in the April 2026 update).

The user does this once:
1. Fusion → Preferences → General → **API** → tick **Fusion MCP Server**. Note the port (default 27182).
2. Click **Apply**. Closing without Apply discards the setting.
3. Open a new design.
4. In a terminal, run `claude mcp add --transport http fusion http://127.0.0.1:27182/mcp`.
5. Restart Claude Code.

Then:
- List the server's tools and confirm the names; they can change between releases. Expect an execute tool that runs a Python string defining `def run(_context):`. Its `print()` output and any uncaught exception come back to you, so don't swallow exceptions. Expect a read tool that can take viewport screenshots.
- Untick the checkbox when the work is done; the server has no authentication.

**Fallback 1:** if the checkbox is missing (for example on a license tier without it), use [frankhommers/autodesk-fusion-mcp](https://github.com/frankhommers/autodesk-fusion-mcp).
1. Unzip the release into `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/AutodeskFusionMCP`.
2. Run it from Shift+S → Add-Ins.
3. Run `claude mcp add --transport http fusion http://127.0.0.1:8765/mcp`.

**Fallback 2:** write the script to `.../API/Scripts/AliceCase/AliceCase.py` with a manifest. The user runs it with Shift+S → Run. The script appends to a `run.log` next to itself, which you read afterwards.

**Ground truth for the API** is the installed stubs at `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Python/defs/adsk/{core,fusion}.py`. Grep them before using any API name.

Names already checked as present in this build:
- `addThreePointRectangle`, `isComputeDeferred`
- `Occurrence.transform2`, `setByAngle`
- `createOffsetInput` / `addOffset2`
- `chamferFeatures.createInput2`, `filletInput.edgeSetInputs`
- `intersectWithSketchPlane`
- `createInterferenceInput` / `analyzeInterference`
- `createSTEPExportOptions`, `createC3MFExportOptions`

Retired names to avoid: `Sketch.offset`, `chamferFeatures.createInput`, `filletInput.add*EdgeSet`, `Occurrence.transform`.

**Fusion API traps**
- Internal length unit is **cm**; angles are **radians**. Prefer `ValueInput.createByString('3.5 mm')`.
- Every run builds into a **fresh document** (`app.documents.add(...)`). This is simpler and safer than deleting old components.
- Put all switch cutouts in **one sketch** with `isComputeDeferred = True`, followed by one extrude. Never create one feature per key.
- Pick profiles by `profileLoops.count` or area, never by index.
- After every milestone, read back bounding boxes and volumes, and take a screenshot. "No exception" doesn't mean the geometry is right.
- `ui.messageBox` is modal and blocks MCP. Use `print`/`app.log` only.

## 3. Architecture: two scripts, one source of truth

Put all the maths in plain Python. The Fusion script only draws what it is given.

```
case/
  geometry.py        # runs with the repo's Python; imports alice.place(); writes out/case_geometry.json
  test_geometry.py   # plain asserts, same style as test_alice.py
  fusion_build.py    # runs inside Fusion; reads out/case_geometry.json; builds + exports
  out/               # generated JSON, STEP, STL/3MF, DXF  (gitignore it)
```

- **Python environment:** `alice.py` imports `tkinter`, and only Homebrew **python3.15** has a working Tk here (3.14's Tk is broken).
  - Create the env with `/opt/homebrew/bin/python3.15 -m venv case/.venv && case/.venv/bin/pip install shapely`. Shapely 2.2 has been tested on this machine.
  - Gitignore `case/.venv/` and `case/out/`.
- **Parameters:** all the numbers in section 4 live in **one dict at the top of `geometry.py`** and are copied into the JSON.
  - The Fusion script also creates them as **User Parameters** so the user can see them.
  - Geometry from `geometry.py` (outlines, transforms) is baked in. To change an angle or a bezel, edit the dict and re-run both scripts. Say this clearly in a comment at the top of `fusion_build.py`.
- **Layout input:** the app is open, and the most recent save is `~/Documents/layout2.json` (40%, 41 keys, curve 3.25°/key, gap 0.25u, no collisions).
  - Before building, ask the user to **Save** from the app to that path (or give another path). That ensures the file matches what's on screen.
  - `geometry.py` takes the path as an argument and refuses to run if `alice.collisions()` is non-empty.
- **Reuse alice.py; don't reimplement it.**
  - `place()` gives key centres and angles in mm. Origin is the top-left; **y points toward the user (front)**; angles are clockwise degrees.
  - Use `solid()` / `keycaps()` / `footprint()` / `corners()`.
  - `frame()` gives the Alice outline's edge directions (straight back, square outer ends, V front).
- **World frame:** X to the right, **Y toward the back**, Z up, origin on the desk plane. Convert with `Y = y_front − y`.

### Coordinate transform (each half)
The **ridge** is the vertical plane at x = midpoint between the left half's largest key-corner x and the right half's smallest. For `layout2.json` that is about **129.39 mm**: left keys end at 127.01 and right keys start at 131.77.

For each half, the transform from plate-top layout coordinates to world coordinates is built in three steps:
1. **Tent fold.** Rotate by 5° about a front-to-back axis through the ridge, so the half's outer edge drops.
2. **Typing angle.** Tilt the whole board 7° about X, so the back rises.
3. **Lift.** Translate in Z so the constraint in section 4 ("H_front") holds.

The two halves are mirror images about the ridge plane, so their plate planes meet exactly on a line in the ridge plane. That line is the case's centre ridge.

Notes:
- The steepest slope on each half is about 8.6°.
- Export a 4×4 matrix (mm) for each half in the JSON. In Fusion, apply it to occurrences via `transform2`. Fusion expects cm, so scale the translation by 1/10.

## 4. Decided numbers

**SUPERSEDED in part.** This is the original table. Rows changed since: `typing_angle`, `tent`, `lip`, `snap_gap`, `bezel_*`, `crease_depth`, `lower_cant`, `panel_t`, `rear_strip_end`, `ledge`, `screws`, `feet`, `usb_opening`, and the H_front rule (+2 mm, not +3). Current values are in the `P` dict of `case/geometry.py` and the Status table above.

| Name | Value | Why / source |
|---|---|---|
| `typing_angle` | 7° | user; also CloudNine's angle |
| `tent` | 5° per half | user; the Qwertykeys Neo Ergo uses 8° + 5° |
| `plate_t` | 1.5 mm | MX standard (ai03) |
| `cutout` | 14.0 mm (prints: 14.05) | MX standard; printed holes shrink |
| `plate_to_pcb` | 5.0 mm, plate top to PCB top | MX standard (ai03) |
| `pcb_t` | 1.6 mm | standard |
| `socket_h` | 1.8 mm below PCB | Kailh CPG151101S11 |
| `floor_clear` | 3.0 mm below the PCB underside | ≥ socket 1.8 + 0.5 air (UDB guide), plus room for the snaps' lower lips |
| `lip` | 3.5 mm: bezel top above plate top, along the normal | Keycap skirt sits about 5.6 mm above the plate at rest and 1.6 mm at bottom-out, so the skirt sinks just below the bezel top. Artisans are kept clear sideways by `artisan_gap`. This also sets the front height (see below). |
| `artisan_gap` | 1.5 mm, plan view, from each key's 19.05 mm grid envelope to the wall | Typical cases use 0.5 mm. 1.5 mm fits flared artisans up to about 22 mm wide. |
| `snap_gap` | 0.75 mm, PCB edge to wall at PCB height | PCBsnap needs 0.5–1 mm |
| `plate_wall_gap` | 1.0 mm | the plate never touches the wall; only the snaps do |
| `bezel_side` / `bezel_front` / `bezel_back` | 6 / 8 / 11 mm (plan, opening wall → outer edge) | CloudNine is about 5 / 8 / 10–11 (estimated from photos). The sides are 6 because wood end-grain walls need at least 5. |
| `pocket_r` | ≥ 3 mm on every internal vertical corner of the top pocket | Ø6 tool; pocket about 13 mm deep |
| `cavity_r` | ≥ 6 mm on internal corners of the bottom cavity | up to about 30 mm deep; Ø12 tool, or Ø6 long-reach in wood |
| `outer_r` | 3 mm on vertical outer corners | CloudNine reads as crisp with small radii |
| `top_round` | R1.0 on the outer top perimeter | CloudNine V2 softened edges |
| `opening_chamfer` | 0.75 mm × 45° on the opening's top edge | artisan protection; reads as a fine highlight |
| `crease_depth` | 10 mm below the top edge, measured vertically | CloudNine character line |
| `lower_cant` | 6° inward (lower band leans in going down) | CloudNine (estimated 5–10°) |
| `panel_t` | 4.0 mm | aluminium or brass final panel; printed for the prototype |
| `rim` | 6 mm (= `bezel_side`) | user |
| `rear_strip_end` | 10 mm, the distance from each rear corner where the strip stops | CloudNine |
| `panel_gap` | wood body: 0.5 mm per side front/back (cross-grain), 0.1 mm per side left/right; prints: 0.2 mm per side | Walnut moves about 0.0027 per 1% moisture content across the grain. |
| `ledge` | 10 mm, from the panel edge to the bottom cavity wall | holds the M3 inserts |
| `screws` | M3 countersunk (ISO 10642), 6–8, ≤ 80 mm apart | Wood: knife-thread brass inserts (pilot hole per the insert's datasheet, about 4.8–6.35 mm; test in scrap). Print: heat-set M3 × 5.7 in Ø4.0 holes. Aluminium: tapped ≥ 6 mm. |
| `feet` | 4 bar feet, 28 × 5 mm, in 1.0 mm-deep pockets in the panel corners, each covering a corner screw | CloudNine hides its screws under its feet |
| `usb_opening` | 12.0 × 7.2 mm | fits standard USB-C overmolds (about 12 × 6.5–7) |
| `stab` | MX "small" cutout 6.75 × 14 mm, from +6 to −8 mm in key Y (+Y = back), at ±11.938 mm, for every key ≥ 2u | ai03 plate generator |

**H_front (solved, not chosen).** *(SUPERSEDED numbers: floor rule is `panel_t` + 2.0; solved front corner 15.55 mm, back centre 35.22 mm.)* Lift the board (step 3 of the transform) by the smallest amount, rounded up to 0.5 mm, such that the top pocket's floor is **≥ `panel_t` + 3.0 mm above the desk everywhere**.
- A rough calculation with these numbers gives an outer front corner of about **18.5 mm** and a back centre of about **39 mm**.
- For comparison, CloudNine is 18 mm at the front and about 32 mm at the back.
- Print the solved values.

## 5. CloudNine design language to apply

**Now a style reference only** (user decision, 2026-10-18): copy the feel, not the numbers. Items 2 (crease and lean 6°), 5 (the strip) and 6 (feet) were adapted; see Status.

Sources: machina.mx/products/cloudnine, Geekhack topic 121804. Every number below is an estimate from photos.

1. **Silhouette:** a sharp-edged slab with a flat bottom and a 7° top. No soft or pillowy surfaces, despite the name.
2. **Character crease:** the outer walls are an upright band 10 mm tall that follows the top edge. Below the crease, the walls lean inward about 6°, so the case reads as a thin slab floating on a darker base.
   - Here the top has two facets (the tent), so the crease on the **back** face bends at the ridge. Its lower band is two planes.
3. **Plan view:** crisp. Vertical corners R3, a small R1 on the top edge, no big chamfers. The top surface is flat and continuous; here it is two flat facets meeting at the ridge.
4. **The opening hugs the keys.** The top surface fills in flush wherever keys aren't, like CloudNine's HHKB corner pads. Here that means around the stagger steps and the split bottom row.
5. **A top frame over a contrasting bottom piece.** The bottom piece shows as a thin strip along the lower rear edge. **USB-C sits on that seam.** No badge on the top or front.
6. **No exterior screws.** Screws hide under bar-shaped silicone feet.
7. **Optional, last:** CloudNine's signature bottom is concentric ripple rings around a four-point star. On a wood or aluminium panel this could be a shallow engraved ring pattern. Skip it unless everything else is done.

Reference images (all from `https://cdn.shopify.com/s/files/1/0739/3925/5570/files/`):
- `F13_C9M_0508_F2.jpg`: front corner, crease, radius.
- `F14_C9M_0517_F2.jpg`: rear strip, foot, crease.
- `F11_C9M_1076_F2.jpg`: underside, feet, rear strip, USB-C.
- `F25_C9M_0905_F2.jpg`: USB pocket on the seam.
- `F10_C9M_1224_F2.jpg`: empty case, crease profile from the front.
- `F02_C9M_0634_F2.jpg`: bezel proportions from above.

Imgur prototype shots: `i.imgur.com/tVGXuzW.jpg` (rear elevation), `i.imgur.com/PX40oVN.jpg` (exploded view).

Fetch a few and compare them with your own screenshots at milestone M4.

## 6. Geometry spec (what `geometry.py` computes)

All results are polygons in mm, plus per-half 4×4 transforms.

1. **Key envelopes.** For each real key (spacers and WK blockers excluded):
   - Take a box in the key's local frame: footprint `w·19.05 × 19.05`, from 1.6 mm (skirt at bottom-out) up to `lip` above the plate top.
   - Transform its 8 corners to world and take the XY convex hull.
   - The case wall is vertical, but the key leans up to 8.6°, so the projection matters. Don't use the flat layout coordinates.
2. **Opening (plan view):**
   `opening = union(envelopes).buffer(−1.5).buffer(1.5 + artisan_gap)`.
   - Every pocket corner becomes ≥ R3 and every straight edge sits exactly `artisan_gap` out.
   - The two halves merge into **one opening**. Near the centre the halves are only about 4.8 mm apart, too thin to leave a web between them.
   - Assert: every envelope is inside the opening with ≥ 1.5 mm clearance along its edges and ≥ 0.85 mm at its corners.
3. **Outer outline (plan view, top edge).**
   - Take the 5 edge directions of the outline `alice.frame()` makes (one straight back edge, two outer ends, the two V front edges).
   - Push each one out to the opening's supporting line in that direction, plus that side's bezel. Intersect the half-planes.
   - Round the vertical corners with `outer_r`. The front V's inner corner is concave, so R3 is required there for the tool anyway.
4. **Top surface:** two planes, each half's plate-top plane raised by `lip` along its normal. They meet at the ridge.
5. **Top pocket.** *(SUPERSEDED: the floor is now one flat plane per half, 4.5 mm under the PCB, with socket grooves and a 4 mm wall band; see Status.)* The opening prism, cut from the top down to a **floor** `floor_clear` below each half's PCB underside, parallel to that half's PCB.
   - The two floor planes meet at the ridge.
   - The floor is also the **PCB stop**: the PCB edge rests over it with 3 mm of air, and the snaps hold it sideways.
   - The walls are vertical (3-axis friendly). The PCB tilt changes the gap by only about 0.24 mm over the PCB's thickness, which the elastomer absorbs.
6. **PCB and plate outlines** (in each half's own flat plane, for KiCad and the plate DXF):
   - Map the opening into the half's PCB plane: invert the affine plane→XY projection at PCB mid-thickness height.
   - Inset by `snap_gap` for the PCB, or by `plate_wall_gap` for the plate.
   - Clip at the ridge with 0.5 mm clearance.
   - Assert: each outline contains every switch's 15.6 mm body square, and each PCB contains every hotswap socket.
7. **Bottom (all on the desk plane z = 0):** *(SUPERSEDED in part: the bottom cavity is gone, the body is solid; the panel back is square, `rear_strip_end` = 6.)*
   - **Bottom footprint:** where the 6° lower band meets the desk (follows from item 8).
   - **Panel outline:** the footprint inset by `rim` on the front and sides. On the back between the strip ends (`rear_strip_end`), the outline runs out to the rear face, so the panel's edge **is** the rear strip.
   - **Rabbet:** the panel outline plus `panel_gap`, depth `panel_t`.
   - **Bottom cavity:** the panel outline inset by `ledge`, cut up from the rabbet until it breaks through into the top pocket. It provides cable routing, weight saving and access. Internal corners use `cavity_r`.
   - **Screws:** M3 holes in the ledge zone, ≤ 80 mm apart, with 4 at the panel corners under the feet.
8. **Lower band:** each outer face below the crease is replaced by a plane hinged on the crease line, leaning in by `lower_cant`.
   - The crease line is the face's top edge moved down `crease_depth` vertically.
   - The back face's lower band is two planes because of the ridge.
   - In Fusion: split faces at the crease, then cut with per-face wedge bodies or use Draft. Your choice; meet the acceptance check in M4.
9. **Daughterboard: Unified Daughterboard C3** *(SUPERSEDED: hung upside down from the body, 22 x 7.2 slot, not on the panel; see Status. Board size and receptacle data below still apply.)* (JST-SH 4-pin), 18 × 16.5 mm, R2 corners, M2 holes on a 14 × 12.5 pattern.
   - Mount it on the **panel** at the back, centred on the ridge, on 0.5 mm washers or bosses (≥ 0.5 mm air gap per the UDB guide).
   - Board underside 0.5 mm above the panel top → receptacle (HRO TYPE-C-31-M-12, 8.94 × 3.21 mm) centred about 3.7 mm above the panel top.
   - The **12 × 7.2 mm opening** therefore starts exactly at the panel seam.
   - Cut it as a **notch open to the bottom** through the rear face, plus a **UDB bay** pocket cut from below (UDB outline + 0.5 mm, ceiling ≥ 12 mm above the panel top so the JST plugs fit).
   - Put the receptacle face ≤ 1.5 mm behind the outer rear face.
   - Download `uDB-C3-3D-model.STEP` from github.com/Unified-Daughterboard/Unified-Daughterboard.github.io and use it as the placeholder. If you can't get it, use a box. Check the receptacle offset against it.
10. **Cable path:** a JST-SH 4-pin header placeholder (6.0 × 4.2 × 2.95 mm) on each PCB underside, at the inner back corner.
    - Clear path through the bottom cavity to the UDB bay, ≥ 8 × 4 mm.
    - An 8 × 6 mm pocket of free space around each header for the plug.
11. **PCBsnap placeholders:** *(SUPERSEDED: 4 per half, 20 mm staple shape, with posts in the notch; see Status.)* 3 per half, on straight stretches of wall (outer end, front, back), ≥ 15 mm from corners and away from stabilizers.
    - The pieces' real dimensions aren't published; use a 10 × 3 × 5.6 mm wedge box spanning PCB −2 mm to +2 mm.
    - The user should buy two sets of 6 and measure one.

## 7. Manufacturing rules (apply now so the CNC version needs no redesign)

- **3-axis, two operations, no undercuts.**
  - **Op 1 (bottom up):** rabbet, bottom cavity, UDB bay, USB notch, insert holes, and the leaning lower band below the crease.
  - **Op 2 (flipped, top down):** both top facets, the opening and pocket with its sloped floor, the upright band down to the crease, R1 top round, opening chamfer.
  - **The crease is where the two operations meet,** so any small mismatch hides in the character line.
  - Every surface must be reachable straight down from +Z (op 2) or straight up from −Z (op 1). Check it at M5.
- **Sloped surfaces:** the top facets and the pocket floor are cut by 3-axis 3D finishing. The pocket floor may be **terraced** (flat steps) in CAM, as long as every step stays at or below the required plane.
- **Corner radii:**
  - Internal vertical corners use `pocket_r` / `cavity_r`. No sharp internal corner anywhere.
  - Sharp outward-facing material corners at the stagger steps get R0.5 or more; a sharp point would chip in wood.
- **Wood:**
  - Walls ≥ 5 mm.
  - Long grain runs along the case width (about 280 mm); the end walls are short grain.
  - The blank must be ≥ the max height + 3 mm skim. At about 39 mm that means ≥ 42 mm. 8/4 stock planes to about 44.5 mm, which is tight; prefer 10/4 or two laminated 6/4 boards.
  - Use inserts, not tapped wood.
- **Aluminium:** the same model works. Use tapped M3 instead of inserts and add 0.05 mm to mating clearances for anodizing.
- **Prototype print:**
  - Print the body **bottom down**. The lower band leans 6°, and the USB notch roof bridges 12 mm; both print without supports.
  - The body (about 280 mm wide) is wider than a 256 mm bed. Split it at the **ridge plane** and join with 3 Ø3 mm dowels (0.1 mm clearance). The panel and screws bridge the seam.
  - The panel (about 265 × 95 mm) only just fits diagonally. Split it at the ridge too if needed.
  - Put the bed size in the params, default 256 × 256 mm.
  - Plates print flat with 14.05 mm cutouts.

## 8. Milestones (build in this order; show the user screenshots after each)

**M0 – Setup.**
- Fusion connected over MCP; the tool list is confirmed.
- `case/.venv` is created.
- The user has re-saved the layout.
- *Check:* a trivial `run()` that creates a 10 mm cube and prints its volume.

**M1 – geometry.py + test.**
- *Check:* `test_geometry.py` passes. It must cover:
  - the ridge lies between the halves
  - the transforms are orthonormal
  - the opening contains all envelopes with the clearances in §6.2
  - the PCB/plate outlines contain all switch bodies
  - every pocket/cavity polygon has internal corner radius ≥ spec (sample its vertices)
  - the solved H_front matches the floor rule
- Print H_front, max height, and outline width and depth.

**M2 – Flat parts.**
- In Fusion, build `PlateL`/`PlateR` (cutouts + stab cutouts), `PcbL`/`PcbR` (with socket keep-out slabs and JST placeholders), switch bodies, keycap envelopes, PCBsnaps and the UDB.
- Build them flat in their own components, then place each with its half's matrix.
- *Check:*
  - The plate bounding boxes match the JSON to within 0.01 mm.
  - No interference between the left and right assemblies (`analyzeInterference`).

**M3 – Case core.**
- Body = outline prism ∩ below both top planes, minus the top pocket (opening prism ∩ above the floor planes), minus the rabbet, bottom cavity, UDB bay and USB notch.
- Bottom panel with its strip, countersunk holes, foot pockets and UDB mounts.
- *Check:*
  - Zero interference between the case and every placeholder (including keycap envelopes).
  - Measured snap gap is 0.75 ± 0.05 mm at each snap location.
  - The USB opening centre is within 0.2 mm of the receptacle centre.
  - Thinnest wall ≥ 5 mm.

**M4 – Styling.**
- Crease + lower band, outer corner radii, R1 top round, opening chamfer, feet.
- *Check:*
  - The crease is parallel to the top edge (constant 10 mm on every face).
  - The lower-band faces are planar and lean 6° ± 1°.
  - Side-by-side screenshots against the CloudNine images in §5.

**M5 – DFM pass.**
- Undercut check: for every face, the normal's Z component must not point away from the operation that cuts it. Faces above the crease are cut from +Z, faces below from −Z.
- List any face that fails and fix it.
- Confirm the minimum internal radii.

**M6 – Fit coupons (prints in under an hour).**
- Small test pieces cut from the real model:
  - a 3-key strip of the plate
  - a wall segment with the snap gap
  - one insert boss
  - the rear USB notch with the panel strip
- The user prints them before committing to the full body.

**M7 – Exports to `case/out/`.**
- STEP of the whole assembly and of each part.
- 3MF/STL for the body halves (split at the ridge), the panel and both plates.
- DXF of each plate and each PCB outline in its own flat coordinates, for laser/waterjet and KiCad Edge.Cuts.
- `pcb_<half>_keys.csv` with key centre x, y, angle and width in each PCB's own coordinates, so the real PCBs can be laid out in KiCad later.

## 9. Things not to do

- Don't change `alice.py` or its design rules. If the case needs something from the layout, ask the user.
- Don't redesign the stack-up, mount or angles. They are decided above.
- Don't do CAM toolpaths; that comes later by hand in the Manufacture workspace. Just keep both operations machinable (§7).
- Don't model real electronics. Placeholders only, with dimensions from §4 and §6.
- Don't add knobs nobody asked for. The parameter dict holds the §4 values and nothing speculative.

## 10. Consequences and open points to tell the user (don't block on them)

- **Height:** 7° + 5° on a unibody makes the back centre about 39 mm tall against an 18.5 mm front, versus CloudNine's 18 / ~32. Each 1° less tent lowers the back centre by about 2.4 mm.
- **PCBsnap:** the piece's real dimensions aren't published. The wall gap (0.75 mm) is what matters, and M6 tests it.
- **Daughterboard:** UDB C3 is assumed. If the user prefers C4 (Molex Pico-EZmate) or the newer S-series (40 × 9 mm), only the bay and mounts move.
- **"Except the very back":** read as the panel running out to the rear face across the full width, stopping 10 mm short of each corner (CloudNine's strip). If the user meant only a tab at the USB port, change `rear_strip_end`.
- **Artisans:** `artisan_gap` = 1.5 mm covers caps up to about 22 mm across at the base. Caps that overhang the bezel need `lip` ≤ 1 mm, which would change the look and the front height.
- **Plate material:** the model doesn't depend on it; the plate is 1.5 mm with 14 mm cutouts either way.

## 11. Sources

- MX stack-up: wiki.ai03.com (switch dimensions), Cherry MX2A datasheet, Kailh CPG151101S11 drawing.
- Stabilizers: github.com/ai03-2725/yet-another-keyboard-builder (`src/cutouts`).
- UDB: github.com/Unified-Daughterboard/Unified-Daughterboard.github.io (`db-spec-c.md`, `info-designer-case.md`).
- PCBsnap: geon.works/products/geon-x-nuxros-pcbsnap, nuxroskb.store.
- CNC DFM: hubs.com CNC design guide, jlccnc.com design guideline.
- Wood movement: USDA FPL shrinkage tables.
- Fusion MCP: help.autodesk.com (ADSKMCP Fusion Desktop MCP server).
- CloudNine: machina.mx, geekhack.org/index.php?topic=121804.0.
