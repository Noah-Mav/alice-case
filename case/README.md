# Alice case: how to change it and rebuild

The case is built in two stages. **Python does the maths** (`geometry.py` writes a JSON file), and **Fusion only draws** what that JSON says. The full design record and every decided value is in `docs/fusion-case-plan.md` ("Status and decisions").

## Files

| File | What it does |
|---|---|
| `geometry.py` | All the maths. The `P` dict at the top holds every number (angles, bezels, gaps, sizes): this is the **source of truth**. Reads the layout, writes `out/case_geometry.json`. |
| `test_geometry.py` | Plain-assert tests of the geometry (clearances, wall thickness, angles, snaps, screws, floor air). Prints `ok ...` on success. |
| `fusion_build.py` | Runs **inside Fusion**. Reads the JSON and builds parts, case, panel and the checks. Its User Parameters in Fusion are a read-only record: editing them in Fusion moves nothing. |
| `fusion_checks.py` | Runs **inside Fusion** after a build: checks-only runner (step 2 below). |
| `fusion_check_standoffs.py` | Runs inside Fusion: the UDB standoff check on its own. |
| `out/` | Generated files (git-ignored): `case_geometry.json`, `fusion_build.log`, `uDB-C3-3D-model.step` (the UDB board model, used as a placeholder). |
| `checkpoints/` | Saved copies of the scripts and JSON that made a good state (git-ignored). `2026-10-17-1910/` is the earlier state, `stepped-centre/` is the current one. Copy a folder's files back over `case/` to return to it. |
| `.venv/` | The Python environment (git-ignored). |

`alice.py` (in the `layout/` submodule) comes from the **layout designer** app. `geometry.py` imports it for key positions; do not edit it for the case. The layout comes from `layouts/layout2.json`: save from the app to `layouts/layout2.json` first, so the file matches what is on screen.

## Change a parameter and rebuild

1. **One-time venv** (only Homebrew python3.15 has a working Tk here):
   `/opt/homebrew/bin/python3.15 -m venv case/.venv && case/.venv/bin/pip install shapely numpy   # venv has shapely 2.2.0, numpy 2.5.4`
2. **Edit the number** in the `P` dict at the top of `geometry.py` (for example `"typing_angle": 6.0`).
3. **Run the tests** from the repo root:
   `case/.venv/bin/python case/test_geometry.py layouts/layout2.json`
   Fix anything it complains about before going on.
4. **Write the JSON:**
   `case/.venv/bin/python case/geometry.py layouts/layout2.json`
   (`ALICE_WEB_MODE=straight` in front of the command builds the straight-centre web instead of the stepped one.)
5. **Build in Fusion through the Fusion MCP, in two steps** (the MCP call times out after about 60 s but the build keeps going; watch `out/fusion_build.log` for `built (checks skipped)`):
   - **Step 1, build only.** Run the text of `fusion_build.py` with the script globals `NO_CHECKS = True`. Add `INTO_ACTIVE = True` to rebuild inside the open "Alice Case" document (it clears the timeline first); leave it out for a fresh document. A full build takes about 5 minutes.
   - **Step 2, checks.** Run the text of `fusion_checks.py` (it loads `fusion_build.py` and calls `check_m3`, `check_m4`, `check_m5` and the UDB STEP check on the open document). Set the global `WHICH = ["m3"]` (or `"m4"`, `"m5"`, `"step"`) to run one at a time, which is safer against the 60 s timeout and rollback. It always skips the standoff probe (`SKIP_STANDOFF`); run `fusion_check_standoffs.py` on its own for the UDB standoff probe (slow; it has hung in full runs).
6. **Read the log** (`out/fusion_build.log`): every `CHECK ...` line should end in `PASS`.
7. **Save** in Fusion as a **new version** of "Alice Case" in the **Default Project** (File > Save, add a version note). Copy `geometry.py`, `test_geometry.py`, `fusion_build.py` and `out/case_geometry.json` into a new `checkpoints/<name>/` folder if the state is worth keeping.

## What the checks mean

- **Plate bbox vs JSON:** the plates in Fusion are the size the maths said (within 0.01 mm).
- **Interference (Left / Right / UDB, and case vs all placeholders):** no part collides with another. A few overlaps inside one assembly are by design (snaps clip the PCB, switches sit in the keycap envelope).
- **Snap gap:** the PCB-edge-to-wall gap at each snap is `snap_gap` (0.9 mm) at PCB mid-thickness.
- **USB opening:** the slot is 22 x 7.2 mm and lines up with the board's USB receptacle.
- **Walls (thinnest wall >= 5 mm):** no wall is thinner than 5 mm anywhere, as wood needs.
- **Bezel top over the plate top (lip):** the case top is exactly 2.0 mm above each half's plate top everywhere.
- **Pillar tops:** the snap posts are parallel to the PCB and 0.25 mm under it.
- **Floor over the cable channels / M3 inserts:** enough material (3 mm / 5 mm) is left over the cable channels and above each screw insert.
- **UDB rest pad / standoffs:** the daughterboard has its support pad and both M2 standoffs.
- **Crease depth rule:** the crease line sits where the design says (9 mm below the top on the ends and back, level on the front).
- **Lower band:** the leaning faces below the crease are flat planes leaning about 8 degrees.
- **Web top flush:** the centre web top lies exactly on the top surface (no steps).
- **Undercuts (Body, Panel):** every face can be cut by a 3-axis machine from the top or the bottom with no hidden face. "info: graze/hairline" lines are tiny slivers (under 0.03 mm) and are not failures.
- **UDB STEP model vs Body + Panel:** the real board model fits the bay and slot with no collision.

## Known Fusion quirks

- The MCP call times out at about 60 s while the build continues. Read `out/fusion_build.log` to see where it is.
- A script that raises an error is **rolled back whole** by Fusion, model included. That is why the build and the checks are separate calls.
- A full build with checks in one go stopped silently twice (right after the UDB rest-pad check, Fusion idle, no error logged) and the UDB standoff probe has hung. Re-running only the checks worked.
- Version numbers in the Fusion data panel can skip (version 4 of "Alice Case" appeared from a rolled-back build).
- `ui.messageBox` blocks the MCP; scripts only use `print` and the log. Fusion's internal unit is cm, so the script scales mm by 0.1.
- Fusion MCP has no authentication: untick Fusion > Preferences > General > API > Fusion MCP Server when you are done.
