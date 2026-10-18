"""Checks-only runner for a built "Alice Case" document (run inside Fusion via the MCP, after a NO_CHECKS build).
Set WHICH before running, e.g. WHICH = ["m3"] (any of m3, m4, m5, step; default all). SKIP_STANDOFF skips the slow UDB standoff probe
(run fusion_check_standoffs.py on its own). Results go to case/out/fusion_build.log."""
import os
CASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.expanduser("~/Documents/Development/alice-case/case")
import adsk.core, adsk.fusion, json, time, traceback
def run(_c):
    path = os.path.join(CASE, 'fusion_build.py')
    ns = {'__name__': 'fb', '__file__': path, 'SKIP_STANDOFF': True}
    exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), ns)
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    g = json.load(open(ns['JSON']))
    halves = {}
    for h, nm in (('left', 'Left:1'), ('right', 'Right:1')):
        asm = root.occurrences.itemByName(nm)
        occs = {}
        for o in asm.childOccurrences:
            k = o.component.name.rstrip('LR').lower()
            occs[k] = o
        halves[h] = (asm, occs)
    udb = root.occurrences.itemByName('UDB:1')
    case = root.occurrences.itemByName('Case:1')
    t0 = time.time()
    ns['log'](f'--- checks only {time.ctime()} (active document)')
    try:
        for fn in globals().get('WHICH', ['m3', 'm4', 'm5', 'step']):
            if fn == 'm3': ns['check_m3'](design, g, halves, udb, case)
            if fn == 'm4': ns['check_m4'](g, case)
            if fn == 'm5': ns['check_m5'](g, case)
            if fn == 'step':
                step = ns['import_udb_step'](udb)
                ents = adsk.core.ObjectCollection.create()
                ents.add(step)
                for n in ('Body', 'Panel'):
                    ents.add(case.component.bRepBodies.itemByName(n).createForAssemblyContext(case))
                inp = design.createInterferenceInput(ents)
                inp.areCoincidentFacesIncluded = False
                res = design.analyzeInterference(inp)
                hits = [(r.entityOne.name, r.entityTwo.name) for r in (res.item(i) for i in range(res.count))]
                hits = [h for h in hits if {'Body', 'Panel'} & set(h)]
                ns['log'](f"CHECK UDB STEP model vs Body + Panel: {len(hits)} pair(s) {hits[:10]} -> {'PASS' if not hits else 'FAIL'}")
            ns['log'](f'{fn} done {time.time() - t0:.0f} s')
    except Exception:
        ns['log']('CHECK ERROR ' + traceback.format_exc())
        raise
    app.activeViewport.fit()
