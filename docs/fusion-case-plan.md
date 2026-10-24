# Alice 40% case + plate in Fusion: build plan

**For:** a Claude Code agent working in this repo, driving Autodesk Fusion through MCP.
**Builds:** a tented, unibody, CloudNine-styled case for the layout this repo's app designed, plus two plates, placeholder electronics and print/CNC exports.

Read this whole file before starting. Section 4's numbers were decided at the start, but many have since changed: see "Status and decisions" below. Section 10 lists the few things to check with the user, but the plan doesn't block on any of them.

---

> **Reading guide.** Sections 1 to 11 below are the **original plan** (written before M1). Parts the build has since moved away from are marked **SUPERSEDED** and point at the table in "Status and decisions". Where the two disagree, the table and `case/geometry.py` (the `P` dict) win. The files `case/geometry.py`, `case/test_geometry.py`, `case/fusion_build.py` and `case/README.md` are the working record; see the README for how to rebuild.

## Status and decisions (as built, 2026-10-18; v2 below, 2026-10-23)

### v2 (2026-10-23, user approved): decisions that replace the rows of the table further down

v1 is kept in `case/checkpoints/v1/` (scripts and JSON); v2 is built into a NEW Fusion document, **"Alice Case v2"**. The same dummy PCB and plate as v1 must fit: their outlines are frozen in `case/frozen_v1.json` (moved along u with the keys, never regenerated) and the pocket walls grow about 0.3 mm round them (`pcb_wall_min` 0.80, `plate_wall_min` 0.90). Everything below is the `P` dict of `case/geometry.py`; the change log with old to new values is `case/out/v2_changes.md`.

| Topic | v1 | **v2** |
|---|---|---|
| Crease | `lower_cant` 8, `lower_back` 0.5 | **`lower_cant` 10, `lower_back` 0.477** (end creases level; the spec's 0.467 was worked out with the old ridge heights and leaves 0.41 mm with the new ridge). Front crease stays horizontal. `panel_shift` 50 to **48** (panel V 2 mm further forward; panel / footprint area 0.35 limit kept) |
| Centreline (ridge) | key-gap midpoint, outline 2.31 mm off it | **midpoint of the two R2 rows** (Shift Z X C V B / N M < > Shift Fn extents, after `half_spread`). `half_spread` 1.2 to **3.5** each side. Both R2 rows end 8.20 mm from it, both outer case edges 142.4 mm, the outline is centred on it, B-N web 13.9 mm (was 9.5) |
| Feet | 4 TPU bar feet, pockets, pegs | **gone.** 4 bumpon recesses (3M SJ5302, 7.9 x 2.2) **Ø8.4 x 0.5**, centres 14 mm in from the two desk-level footprint edges of each corner (front pair under the solid bezel, rear pair in the body beside the panel) |
| Bottom panel | 195.6 wide | **212.2 wide** (`panel_half_w` 106.1 each side of the ridge), same rear-only pentagon, three screws, solid front underside |
| Angles, base | typing 6, tent 4, `base_min` 4.5 | **typing 8, tent 5, `base_min` 3.5** (`floor_air` stays 3.5). Heights: front outer 16.20 / 16.08, front V 26.49, rear outer 28.77, rear centre 41.35 (before the rear cut) |
| PCB mount | 8 silicone PCBsnaps, pillars, R1.5 pillar fillets | **10 printable TPU C-clips** (5 per half) in recesses 10.4 x 3.8 x 0.5 in the pocket floors (45 deg lead-in, R1.5, wall side on the wall) at PCB-local edge points left (71.3,6.3) (124.3,29.5) (102.7,81.0) (13,85.6) (20,26.9), right (197,6.7) (139,30) (154.4,80) (245,85.6) (240,26.9). No pillars, no pillar fillets, no centre pads; the 4 mm wall band and the UDB supports stay. Floor plane under every recess >= 4.0 (`clip_floor_min`, local exception to `base_min`; 4.6 min). The clip: 10 long, slot 1.5 for the 1.6 PCB, 2.5 under it, 1.0 lip 1.5 over it with a 30 deg lead-in, 0.9 spine, hex lattice 2.3 cells / 0.8 walls, 6.5 high; exported as the body `TpuClip` |
| Bezels | front 7.0 (7.40 / 7.00), back 9.5, sides 6.0 | **front 6.0 (left 6.00, right 6.10: the V correction moves to the right), back 8.5**, sides 6.0; outline 284.75 x 105.69 (the pocket growth round the frozen PCB adds to the spec's 285.05 x 105.21 estimate) |
| Rear triangle | peak 41.35 | **one plane** through the horizontal line on the rear face 8 mm under the peak (BC 33.35) and the crest point A 25 mm forward of the rear edge (37.83 high); everything above goes. Rear-face triangle 181 x 8, 4.66 mm of wall over the plate top at the pockets under it, blind to the UDB bay, 22.1 mm of rear face over the USB slot. Max height 37.83 |
| USB opening | 22 x 7.2, R3 | **stepped**: 17 x 7.2 neck 2 mm deep at the rear face, then the 22 wide chamber behind it; `usb_recess` 2.25 (board's receptacle 0.25 behind the step); the UDB still installs from below |
| Panel field | 0.4 deep | **0.6 deep** (border, R3 corners, wrap onto the rear face kept; band recess 0.6) with a **0.4 deep seat pad** R 4.86 round each of the 3 screws (0.2 proud of the field); countersink starts at the seat depth, so 1.94 mm is still left under each cone |
| UDB boss | | at the new geometry its fillet out to the wall came within 1.82 of the PCB: it is cut back along the line where the PCB underside is 2.0 + 0.02 over its flat top (the 2.0 rule is not relaxed) |


State: **v2 is the current design (see the block above; the table below is v1)**. Milestones M1 to M6 done, plus M8 (**v9**, 2026-10-18: back-edge recess wrap, 3 screws; saved as Alice Case version 9) and M7 (v6: band ends, 5 screws, lip 5.0; v7 = "Alice Case" version 8: lip 6.0, solid front, 4 mm rear pentagon panel with recessed fields, 4 screws, all feet in the body; checkpoint of v6 in `case/checkpoints/lip-5.0/`). The Fusion design "Alice Case" (Default Project) holds the model; the final scripts and JSON are in `case/checkpoints/stepped-centre/` (earlier state: `case/checkpoints/2026-10-17-1910/`). All values below come from the `P` dict in `case/geometry.py`. The layout is `~/Documents/layout2.json` (40%, 41 keys).

Resulting size (M7, v7: lip 6.0, solid front): outline 280.46 x 107.12 mm (unchanged), front corners 18.25 / 17.88 mm high, front V 26.29 mm, back centre 37.55 mm (minimum blank; 40 mm stock plus skim is enough).

| Topic | Old (original plan) | New (as built) | Why |
|---|---|---|---|
| Typing angle `typing_angle` | 7 deg | **6 deg** | user: back wall too tall |
| Tent `tent` | 5 deg per half | **4 deg** | user: back wall too tall |
| Lip `lip` | 3.5 mm | **6.0 mm** (M7, v7; 2.0 at M6, 5.0 in v6). The real Cherry skirt (6.0 above the plate at rest, verified) sits level with the case edge at rest; bottomed out (2.0, `skirt_bottom_out`, one constant) it is 4 mm under it. The stack sits 0.5 mm lower than in v6 (the solid front allows a 4.5 mm base) and the walls rose 0.5 mm. The opening, and so the outline in plan, keeps its M6 design envelope (`opening_env` [1.6, 2.0], not the cap skirt); real tapered Cherry caps keep 1.51 mm (>= `artisan_gap`) to it. Air `floor_air` 3.5 mm. Front feel: bottomed out, a thumb line through a front-row cap's top-front edge clears the front bezel up to 45.3 deg, so 30-45 deg thumbs clear | user: caps stood too high; skirt level with the edge, front feel kept. Options at lip 6.0: base 4.5 (picked: stack -0.5, walls +0.5, back 37.55) or base 5.0 (stack 0, walls +1.0, back 38.05); lip 7.0 was tried (back 39.05, feel 39.7 deg with the KeyV2 caps) and dropped |
| Panel `panel_t` | 4.0 mm | **4.0 mm** (M7, v7; 3.0 from M5 to v6) | user: the panel may be wood, the countersinks need more meat (1.94 mm left under each head in the recessed field); the case outside and the stack are unchanged, the panel's top face sits 1 mm higher in the body |
| Snap gap `snap_gap` | 0.75 mm | **0.9 mm** | vendors quote 0.8 to 1 mm; gap measures 0.81 to 0.99 mm over the PCB height because the PCB is tilted |
| PCBsnaps | 3 per half, 10 x 3 x 5.6 mm wedge box | **4 per half (2 front, 2 back), as close to the corners as allowed.** Placeholder is the real shape: a staple (Pi) 20 mm long, 8.5 mm centre notch, reach 2.5 mm (`snap`, `snap_spine` 0.6, `snap_drop` 2.5). Real parts are silicone. | the real PCBsnap is about 20 mm long with a notch, not a wedge; sizes are estimates from photos (+-30 %) |
| Snap posts ("pillars", in the snap's notch) | 8 x 3.5, R1 | **6 mm wide x 3.5 deep, top 0.25 mm under the PCB, parallel to it, R1.5 fillets into the wall** (`pillar`, `pillar_fillet`) | 6 mm clears the legs of the 8.5 notch; R1.5 means a Ø3 tool, R1 is too long and thin in hardwood |
| Pocket floor | `floor_clear` 3 mm under the PCB, plain | **One flat plane per half, parallel to its PCB, **3.5 mm** (M7, `floor_air`; 4.5 at M6) under the PCB underside, with socket-aligned grooves** (`relief` 7 wide x 1.25 deep, `socket_margin` 1.0, `socket_bridge` 3.0) **and a flat 4 mm wall band** (`groove_wall`) for the snap legs and posts. Air under the PCBs 3.50 to 4.75 mm (M7). | Neo65-style floor photo; sockets need room, the walls must stay flat for the snaps |
| Body underneath | big bottom cavity, 14 mm ledge, two terraces | **Solid body.** M7 (v7): **in front of and beside the panel it is solid down to the desk** (one flat underside, no seam): >= 4.5 mm of body under the pocket floor (`base_min`), >= 3.5 under the relief grooves (`base_min_groove`); this is the H_front rule now. Over the panel the same thickness is kept over the rabbet ceiling (5.75 mm min), which sets how far back the panel's V sits. Under the panel only the UDB bay, two 13 x 4 mm cable channels (4 mm clear over the panel top, >= 3 mm under the floor) with JST breakthroughs and the insert holes are cut from below. Machining: op 1 (bottom) is cut first, so in op 2 the flat underside sits fully supported on the fixture / spoilboard while the pocket floor is cut; a 4.5 mm walnut floor is fine there, with no unsupported thin skin | stiffer, simpler to machine, enough room for the cables; user: solid front base |
| Daughterboard (UDB) | on the panel, on 0.5 mm washers | **Hung upside down from the body**, 0.5 mm under the slot roof; two front standoffs Ø6 x 1.0 with M2 inserts (`udb_mount`, `udb_insert`); rear edge on a **rest pad**. The panel carries nothing. M7 (v7): with the 4 mm panel the board, slot and band sit 1 mm higher (receptacle 1.9 mm above the panel top); M2 insert holes **Ø3.2 x 3.6** (M2 x 3 inserts) so the boss over them stays 2 mm under the PCB | the 22 mm slot needs the board to pass the rear wall; a 5 mm wall leaves no room for rear screws |
| Screws | 6 to 8 M3, 4 at the corners | **M8 (v9, user): 3 M3.** The two front screws are removed; one sits at the panel's V point on the ridge, just inside the field's border (`screw_front_offset` 0.0, nearest spot to the V passing the field and the 3D insert rule). The two back corners are unchanged. Earlier (v7): **4 M3, all in the rear panel's recessed field**: the 2 back corners just inside the border (`screw_recess_margin` 1.0 from the head to the field edge), and the 2 side-front ones nudged in from the field's side-front corners to the nearest spot with >= 5 mm of body over the insert (3D rule, relief grooves counted, so no bosses): **15.1 mm (left) and 27.6 mm (right)** from those corners (`screw_front_offset`), between key rows. All inserts **Ø4 x 3.6** (short), rabbet ceiling at z 4.0. Heads seat on the recess floor: **1.94 mm** of panel under each countersink cone (target 2.0 for wood; aluminium or print fine). The back pair keeps 5.02 mm to the band pocket | user: v6 removed the mid-back screw; v7: 4 screws at the half panel's corners |
| Panel | full bottom, rim 6 mm | **Rear part only** (M7, v7): a pentagon, its front a V parallel to the case's front V, moved back 50 mm (`panel_shift`; set by the floor over it), tip on the ridge; its sides 3 mm inboard of the rear feet (`rear_foot_clear`) **straight to the back edge** (no wings to the back corners). Front corners R6 (`panel_front_r`), back corners square (they run out through the rear face). Covers 35 % of the underside: UDB bay, cable channels, USB. **Underside recessed field** 0.4 mm deep, 3.5 mm border on the front and sides, R3 corners (`panel_recess`), flat end mill from the outer face; the screws sit in it. **M8 (v9, user): no border along the back edge**: the field runs out through the edge and wraps onto the rear-face recess, so the two recesses are one continuous 0.4 mm floor over the edge (the back chain is lifted 30 mm before the inset so the side borders stay straight). **Rear-face recess** (the panel's edge and band, `band_recess`): the same 0.4 mm on each rear lean plane, 1.5 mm border on its sides and top, no border at its bottom (M8: the face runs below the edge, so it wraps onto the underside recess; the cutter floor is z -1) (the face is only 7.6 mm tall), R1.5 corners, with a full-thickness 1.5 mm frame round the USB notch; the band stays >= 2.6 mm thick behind it. **Machining:** in v9 the undercut check finds the rear-face recess faces reachable from below (0 side faces; reported as bottom / both) because they wrap onto the underside recess, so no extra setup should be needed. Confirm this in CAM; fine for print | user: solid front, half panel; reference photo for the recess; rear feet off the panel; no wings; recess carried up the band |
| Feet | 4 bar feet 28 x 5 mm | **28 x 6 mm** (M7; 8 wide at M6), removable press-fit **TPU** (`foot_fit` 0.15 per side) with **2 pegs each** (Ø3 holes x 2 mm, `foot_peg`; 1.35 mm of TPU each side of the Ø3.3 peg). M7 (v7): **all four press into 1 mm pockets in the solid body's underside**, the rear pair moved forward clear of the panel's back strip, >= 3 mm of body to the panel | user |
| USB opening | 12 x 7.2 mm | **22 x 7.2 mm with R3 on all four corners** (`usb_slot_w`, `usb_r`) | the board has to pass through the rear wall; R3 is the Ø6 ball mill. The floor R3 clears the UDB corners by 0.3 mm |
| Rear band | trapezoid-ish strip, square ends | **Rear band with one long shallow diagonal at each end (3.6 over 21.2 mm, about 9.6 deg, `band_end_run`) and R6 top corners** (`strip_lip` [20, 2.5, 7.2], `strip_lip_r` 6), each diagonal landing on the panel's outer top corner; no flat run-out, no concave corner. M7 (v7): the panel is narrower at the back (it no longer reaches the back corners), so the band's ends moved in with it (x 33.9 / 229.5); body fills the back corners beside it. The panel still drops straight out; the body pocket follows with the 0.2 gap and stops square at the rabbet side walls (under 0.2 mm tall there) | user screenshots: the old step and notch, then (M7) the concave corner at the ends; rear feet off the panel |
| Crease | 10 mm below the top, even all round, lean 6 deg | **9 mm, lean 8 deg** (`crease_depth`, `lower_cant`). **Deepening** on the ends and back (the crease follows the surface down); **horizontal on the front** (`crease_mode` = `front_horizontal`, permanent, the TODO to revert it was dropped) | user chose the look after a trial; front level at z 6.73 |
| Bezels | side / front / back 6 / 8 / 11 mm | **Equal 6 mm side bezels; front 7 (7.40 left / 7.00 right, see V); back 9.5 mm.** The ridge sits at the **key-gap midpoint** (`half_spread` 1.2 per half); the outline centre is **2.31 mm off the ridge** (the right half is about 4.6 mm wider than the left, no x shift can change that) | user: equal sides, symmetric web around the ridge |
| Front V | front V's inner corner 1.79 mm right of the ridge | **V on the ridge:** left front bezel 7.40, right 7.00; front screw moved with it | user: V should meet the ridge |
| Centre web | convex-hull web (straight runs between row ends) | **Stepped, key-hugging** (`web_mode` "stepped": the split follows the keys, every web corner R3), spread 1.2 mm per half, web at least 9.5 mm. `ALICE_WEB_MODE=straight` still builds the hull version. | hull left up to 7 mm of gap to the keycaps; the old R0.5 corners made lobes and an S-jog |
| Opening edges (front / back rows) | cusps between keys | **Cusps smoothed:** notches under 1 mm deep and wider than tall are filled with an R100 closing (`row_smooth_r`, `row_smooth_depth`); R100 keeps 12 mm of straight wall per key for the snaps | user screenshot |
| Sleekening (M5) | panel 4, bezels front/back 8/11, crease 10, lean 6, floor rule +3, M3 hole 6.5 | panel 3, bezels 7/9.5, crease 9, lean 8, floor rule +2, M3 hole 6.0; `floor_clear` 2.5 was tried and reverted (the JST header hits the floor) | user asked for a sleeker case |
| CloudNine | design reference, numbers to follow | **Style reference only.** Functional rules (walls, tool radii, clearances) stay hard; styling may deviate to look better | user decision |

Checks (last build, M7 v7 = "Alice Case" version 8, `case/out/fusion_build.log`): all PASS: no interference between the case and 204 placeholder bodies plus the UDB (and Left / Right / UDB); snap gap 0.9 +- 0.05; USB 22.00 x 7.20, 0.105 mm off the receptacle; thinnest wall 5.00 mm (insert to band pocket 5.02); >= 5.20 mm over every M3 insert; floor over the cable channels 7.06 mm; lip 6.000 mm everywhere; crease rule 0.0003 mm; lower band 6 planes at 7.98 to 8.00 deg; web flush; UDB STEP model and standoffs PASS; undercut check 0 unreachable faces on Body and Panel (v8: the panel's rear-face recess listed as side-setup faces; **v9: 0 side faces, the wrapped band faces are reported as bottom / both**, so confirm the setup in CAM). v9 checks: all PASS (interference, snap gap, USB, lip 6.000, walls 5.00, floor over channels 7.06, inserts 5.75, crease, lower band, web flush, UDB STEP, standoffs). Front feel 45.3 deg. Internal radii: R3 pocket / groove / slot / panel-recess corners (Ø6), R6 rabbet corners, R1.5 snap-post fillets (Ø3, the smallest tool, about 15-20 mm down in hardwood); no Ø2 anywhere. Exported meshes all watertight.

### Open items

**v2:** items 1 and 2 below are moot (no PCBsnaps). New: print one `TpuClip` and the 10 recesses on a test piece and check the grip (slot 1.5 for a 1.6 PCB is an interference fit by design), the lead-ins and the lattice in the real TPU; the clip's spine is 0.9 at mid-PCB but the PCB-to-wall gap is 0.8 to 1.3 over a clip (vertical wall, tilted PCB), so the fit bodies in the model follow each spot; the export script (`fusion_export.py`) still names the old snaps and feet and needs updating before the next export.


1. **Measure a real PCBsnap** (notch width, length, leg drop, bar height, reach, spine). The 20 / 8.5 / 2.5 sizes are estimates from photos. If the real notch is narrower than about 8.5 mm, revisit the post width (6) or its R1.5 fillets.
2. **The user will buy silicone PCBsnaps, 2 sets of 6** (8 used, 4 spare). Printed TPU stand-ins (`PCBsnapTPU`, one watertight body) are for fit tests only; silicone replaces them.
3. **Wood inserts for the three panel screws must be 3.5 mm long or less** (holes Ø4.0 x 3.6; print M3 x 3 heat-set). UDB M2 holes are Ø3.2 x 3.6 (M2 x 3).
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
5. **Top pocket.** *(SUPERSEDED: the floor is now one flat plane per half, 3.5 mm under the PCB (M7), with socket grooves and a 4 mm wall band; see Status.)* The opening prism, cut from the top down to a **floor** `floor_clear` below each half's PCB underside, parallel to that half's PCB.
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
