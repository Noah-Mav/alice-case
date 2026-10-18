# Print files

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
