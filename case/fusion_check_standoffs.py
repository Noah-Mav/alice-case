"""Standalone UDB standoff check for a built "Alice Case" document (run inside Fusion via the MCP). Logs to case/out/fusion_build.log."""
import os
CASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.expanduser("~/Documents/Development/alice-case/case")
import adsk.core, adsk.fusion, json, math, time
G = json.load(open(os.path.join(CASE, 'out', 'case_geometry.json')))
LOG = os.path.join(CASE, 'out', 'fusion_build.log')
def log(s):
    print(s)
    open(LOG, 'a').write(s + '\n')
def run(_c):
    t0 = time.time()
    app = adsk.core.Application.get()
    d = adsk.fusion.Design.cast(app.activeProduct)
    c = d.rootComponent.occurrences.itemByName('Case:1').component
    body = c.bRepBodies.itemByName('Body')
    P = G['params']; MM = 0.1
    P3 = lambda x, y, z: adsk.core.Point3D.create(x * MM, y * MM, z * MM)
    IN = adsk.fusion.PointContainment.PointInsidePointContainment
    inside = lambda x, y, z: body.pointContainment(P3(x, y, z)) == IN
    bd, di = P['udb_mount'][0], P['udb_insert'][0]
    z0, z1 = G['udb']['mount_z']
    pres = []
    for x, y in G['udb']['mounts']:
        ring = all(inside(x + (bd + di) / 4 * math.cos(a), y + (bd + di) / 4 * math.sin(a), (z0 + z1) / 2) for a in [k * math.pi / 4 for k in range(8)])
        pres.append(ring and not inside(x, y + bd / 2 + 0.3, (z0 + z1) / 2) and not inside(x, y, (z0 + z1) / 2))
    def up(x, y, zs):  # material straight up from zs: 0.5 mm steps, then bisection to 0.01
        if not inside(x, y, zs + 0.01):
            return 0.0
        z = zs
        while inside(x, y, z + 0.5) and z < zs + 30:
            z += 0.5
        lo, hi = z, z + 0.5
        while hi - lo > 0.01:
            m = (lo + hi) / 2
            lo, hi = (m, hi) if inside(x, y, m) else (lo, m)
        return lo - zs
    zi = z0 + P['udb_insert'][1]
    w = min(up(x + di / 2 * math.cos(a) * k, y + di / 2 * math.sin(a) * k, zi) for x, y in G['udb']['mounts']
            for k in (0, 1) for a in [j * math.pi / 2 for j in range(4)])
    ok = all(pres) and len(pres) == 2 and w >= 5 - 1e-4
    log(f"CHECK UDB standoffs in the body, standalone (Ø{bd} x {z1 - z0:.1f} mm, M2 insert hole Ø{di} open): {sum(pres)}/2; "
        f"material over each insert {w:.2f} mm (outside / cavity: geometry walls) -> {'PASS' if ok else 'FAIL'} ({time.time() - t0:.0f} s)")
