# Print files

The v1 files are below; the current design, **v2**, is in [Print files v2](#print-files-v2) at the end and in `prints/v2/`.

Whole parts, flat on the bed, millimetres. Exported from Fusion "Alice Case" v9 by `case/fusion_export.py` (`copy`, `plates`, `proto`, `whole`).

| File | Material | Orientation / supports |
|---|---|---|
| `case_body.stl` | PLA or PETG | One piece, bottom down (as modelled). Supports under the panel-recess area. 280.5 x 107.1 mm: fits a 320 x 340 mm bed whole. |
| `bottom_panel.stl` | PLA or PETG | One piece, outer (desk) face down, no supports. 195.6 x 55 mm. |
| `tpu_foot_x4.stl` | TPU 95A | 4 feet on one plate, pad down, pegs up. |
| `tpu_pcbsnap_x8.stl` | TPU 95A | 8 snaps, spine wall face down, no supports. |
| `dummy_plate_left.stl`, `dummy_plate_right.stl` | PLA or PETG | Flat, 1.5 mm, 14.05 mm switch cutouts. |
| `dummy_pcb_left.stl`, `dummy_pcb_right.stl` | PLA or PETG | Real outline, 1.6 mm, printed top face down, socket side up (no supports); MX hotswap and stab holes and printed hotswap sockets (see below); JST marker bump points up (4.55 mm tall in all). |
| `switch_fit_test.stl` | PLA or PETG | 1.5 mm strip, 4 cutouts, sizes embossed 0.4 mm (z up). |

## Notes

- **Plates:** layer height 0.2 mm with a 0.3 mm first layer (0.3 + 6 x 0.2) so the plate prints at exactly 1.5 mm.
- **Elephant foot:** the first layer squashes outward and shrinks the cutouts. Enable elephant-foot compensation (about 0.1-0.2 mm) or print the fit strip with the same settings first.
- **Fit strip:** print it with the plate settings and drop a switch into each cutout. Use the smallest size where the switch clicks in without forcing and does not rattle (14.05 mm is the design value). If it differs from 14.05, change `cutout_print` in `case/geometry.py` and re-export.
- **Inserts:** M3 x 3 heat-set for the 3 panel screws (holes 4.0 x 3.6); M2 x 3 heat-set for the UDB standoffs (holes 3.2 x 3.6).
- **Feet:** the pegs press-fit into the body holes; if loose, add a drop of CA glue.
- **Foam:** case foam must be 3 mm or thinner under the PCB.

## Dummy PCBs

- Every key has the MX hotswap holes (centre post, two 5-pin pegs, two switch-pin holes at the Kailh positions); keys of 2u and more also have the Cherry PCB-mount stab holes.
- The holes are oversized for printing by `print_hole_clearance` (0.3 mm on the diameter, in `case/fusion_export.py`): post 4.3, pegs 2.05, switch pins 3.3, stab 4.29 and 3.35. Change it and re-run `dummy_pcbs()` if the fit is too loose or tight.
- Every key has a printed Kailh CPG151101S11 hotswap socket body on the underside: an S-shaped outline of two offset lobes round the switch pin holes (about 10.9 x 4.6 mm, 1.8 mm below the PCB, from the datasheet size, approximate shape; solder tabs left out). It sits inside the `SOCKET` keep-out in `case/geometry.py`, and its bottom is 1.7 mm clear of the case floor (3.5 mm air).
- Each socket keeps the 3.3 mm PCB pin holes open and has a pin slot of 1.9 mm (1.6 + 0.3) below them, so the switch blades slide in without gripping; the centre post and peg holes are cut through it too. Print flat PCB face down, sockets up: no supports.
- A printed PCB flexes more than FR4, so use it to check fit and assembly only, not feel or sound.

## Print files v2

Exported from Fusion "Alice Case v2" version 8 by `v2_prints()` in `case/fusion_export.py`, into `prints/v2/`. Millimetres, lowest point on z 0.

| File | Material | Orientation / supports |
|---|---|---|
| `v2/case_body.stl` | PLA or PETG | One piece, bottom down (as modelled), as for v1. 284.7 x 105.7 x 39.3 mm. Supports under the panel-recess area. |
| `v2/bottom_panel.stl` | PLA or PETG | One piece, outer (desk) face down, no supports. 212.2 x 54.9 mm. |
| `v2/tpu_clip_front.stl` | TPU 95A | FRONT C-clip, 4.3 x 6.5 x 10 mm, **one dimple** on the lip top. |
| `v2/tpu_clip_back.stl` | TPU 95A | BACK C-clip, 3.4 x 6.5 x 10 mm, **two dimples** on the lip top. |
| `v2/tpu_clip_front_x4.stl` | TPU 95A | 4 FRONT clips on one plate. |
| `v2/tpu_clip_back_x6.stl` | TPU 95A | 6 BACK clips on one plate. |

Which clip goes where (10 spots, 5 per half, same in the left and right half):

| Spot (per half) | Where | Clip |
|---|---|---|
| 1 | front edge, under Alt | FRONT (1 dimple) |
| 2 | inner edge, right of B | BACK (2 dimples) |
| 3 | back edge, above R / T | BACK (2 dimples) |
| 4 | back edge, above Tab | BACK (2 dimples) |
| 5 | front edge, under Shift / Z | FRONT (1 dimple) |

So 4 FRONT + 6 BACK. The two differ only in the outer (wall-side) face, which leans with the pocket wall it bears on: FRONT 1.76 mm out at the bottom to 0.85 at the lip top, BACK 0.0 to 0.85. Slot (1.5 for the 1.6 PCB), 1.0 lip, 2.5 ledge, lattice and 10 mm length are identical. Each is 0.1 mm off the wall at its tightest point and at most 0.15 (FRONT) / 0.35 (BACK spots 3 and 4) / 0.58 (BACK spot 2) away along the face.

- **Reused from v1:** the same dummy PCBs and plates (`dummy_pcb_*.stl`, `dummy_plate_*.stl`) and the switch fit strip. The v2 case is built round the frozen v1 outlines.
- **Gone from v1:** no TPU feet and no PCB snaps. The feet are replaced by 4 bumpon recesses (8 mm round, 0.5 mm deep) for **3M SJ5302** bumpons, 4 needed.
- **Clips are untested.** Print one `tpu_clip_front.stl` and one `tpu_clip_back.stl` first and check the grip on the 1.6 mm PCB edge and the fit in a recess before printing the plates.
- The v1 files above stay as they are so older links keep working.

## Print files v3

Exported from the Fusion v3 build by `v3_prints()` in `case/fusion_export.py`, into `prints/v3/`. Millimetres, lowest point on z 0.

| File | Material | Orientation / supports |
|---|---|---|
| `v3/case_body.stl` | PLA or PETG | One piece, bottom down (as modelled). 286.5 x 105.9 x 39.1 mm: needs a bed of about 290 x 110 mm or more. **Supports on the build plate only**, under the panel recess ceiling, the cable channels, the daughterboard bay and the USB slot (all open to the bed). Nothing on the top side needs support (the square pocket walls lean at most about 8 deg). |
| `v3/bottom_panel_flat.stl` | PLA or PETG | **The one to print.** Flat underside with no border, screw heads flush; the back keeps its bordered field. Outer face down, no supports (only small bridges). 212.2 x 55.2 x 7.6 mm. |
| `v3/bottom_panel.stl` | (machining) | The recessed-underside variant, for CNC. Printed face down, its 0.6 mm field (about 8,700 mm2) starts in the air, so it needs supports there and the visible face comes out rough; print the flat one instead. |
| `v3/tpu_clip.stl` | TPU 95A | The one C-clip for all 10 spots, 10 x 6.5 x 3.2 mm, already laid on its flat outer face: **no supports**. |
| `v3/tpu_clip_x10.stl` | TPU 95A | 10 clips on one plate, same orientation. |
| `switch_fit_test.stl` (in `prints/`) | PLA or PETG | Unchanged from v1: print it with the plate settings to check the 14.05 mm cutout first. |
| `v3/dummy_pcb_left.stl`, `v3/dummy_pcb_right.stl` | PLA or PETG | v3 dummy PCBs (the shared PCB / plate edge), printed top face down. |
| `v3/dummy_plate_left.stl`, `v3/dummy_plate_right.stl` | PLA or PETG | v3 dummy plates, flat, 1.5 mm, 14.05 mm switch cutouts. |

- **Checked before printing (v3.4):** every file is watertight (no open edges; each volume matches the Fusion solid). A slicer may report a few non-manifold edges where faces meet at razor-thin points (the panel's band feet, under 0.03 mm) and repair them automatically; they change nothing. In Fusion: no interference between the case and the PCBs, plates, switches, keycaps, sockets, headers and their plug space, daughterboard and gaskets; every gasket fits its recess; walls at least 5 mm.
- **Hardware:** 3 x M3 x 3 heat-set inserts (holes Ø4.0 x 3.6) and 3 x M3 x 6 countersunk screws (ISO 10642) for the panel (4.0 panel, 2.0 into the insert); 2 x M2 x 3 heat-set inserts (Ø3.2 x 3.6) and 2 x M2 x 5 screws for the daughterboard (1.6 board + 1.0 standoff, 2.4 into the insert); 4 x 3M SJ5302 bumpons; 10 printed TPU clips.
- **Fit gaps:** the panel sits 0.2 mm off the body all round (`panel_gap_print`), so turn on elephant-foot compensation (0.1 to 0.2 mm) for the body and the panel, or the first layers can bind.
- **Suggested order:** one `tpu_clip` and the switch fit strip first (check the grip and the cutout), then the dummy plates and PCBs, then the case body and the flat panel.
- **One clip everywhere.** The v3 pocket walls are square to the PCB, so the PCB edge is 0.9 mm from the wall at every spot and one clip fits all 10 (v2 needed FRONT and BACK variants).
- **Printing the clip:** it is a plain square block on its flat outer face: square corners on the bed, 0.5 mm rounds on the end edges (vertical as printed), 45 deg lead-ins on the slot, and the three lattice cells as vertical holes. No supports. Use 2 perimeters at 0.4 mm (the struts are 0.8 wide, the end walls 0.6, the skins 0.7) and 0.2 mm layers, slow (20 to 40 mm/s) as usual for TPU.
- **Lattice:** one row of three 2.3 x 2.6 mm cells with rounded corners in the 4 mm ledge under the PCB. The struts between cells lean and the 0.7 mm skins span the cell tops, so they bend under a keypress (soft) and stiffen as the cells close (progressive). Untested: print one clip in 95A first and check the grip on the 1.6 mm PCB edge, the fit in a recess and the give. If it is too stiff, try 85A or ask for thinner struts.
- **New PCB / plate edge.** The PCB and plate now share one edge (the outer edge of the two v1 outlines): the PCB is up to 0.54 mm bigger along the back and the centre side. Key, socket, stab and JST positions are unchanged, so update only the board outline (Edge.Cuts) in the real PCB. The v1 dummies do not fit the new pocket the same way; print the v3 ones. The switch fit strip is unchanged.
