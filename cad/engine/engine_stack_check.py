# GR180-CCHP engine stack: pairwise interference of core v13A (kept parts) + E2 + E3 + E4, and flange coincidence E2/E3/E4.
# Reads the per-part STEPs written by build_gr180.py (cad_out/v13A/asm_parts), cad/engine/combustor_casing.py (E2),
# cad/engine/fpt_pmg.py (E3) and cad/engine/recuperator.py (E4, ROOF frame -> moved to ENG here).
# Run (after the four builds):
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/engine/engine_stack_check.py
# Output: cad_out/engine/engine_stack_checks.json (+ printed summary).  Within-subsystem pairs are checked by each build script.
# Variant B (GR180-STEAM, simple cycle): STACK_VARIANT=B -> core + E2-B (cad_out/variant_b/E2B, cad/variant_b/e2b_combustor_casing.py)
#     + E3, no E4; output cad_out/variant_b/stack_checks_B.json.
import FreeCAD as App, Part, os, json, glob, math, sys
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'docs', '06_master_design.md')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
CO = os.path.join(ROOT, 'cad_out')
ENG0 = (1880.0, 7850.0, 600.0)          # ENG origin in ROOF (mm), docs/06 sec.1
def say(*a): print(' '.join(str(v) for v in a)); sys.stdout.flush()
VARIANT = os.environ.get('STACK_VARIANT', 'A').upper()

CORE_KEPT = ('Intake', 'IntakeOuter', 'Compressor', 'Diffuser', 'Shaft', 'ShaftTunnel', 'NGV', 'Turbine', 'TurbineNut', 'NoseCone', 'Starter',
             'RPM_Sensor', 'RPM_Magnet', 'Balance_Slug', 'FrontBearing_608_hybrid_8x22x7', 'RearBearing_608_hybrid_8x22x7', 'FrontBearing_Oring',
             'WaveSpring_22x16_free3_0_inst2_8')
def load(f):
    s = Part.Shape(); s.read(f); return s
SHAPES = {}                               # key -> (subsystem, shape in ENG)
for n in CORE_KEPT:
    f = os.path.join(CO, 'v13A', 'asm_parts', n + '.step')
    if os.path.exists(f): SHAPES['core:' + n] = ('core', load(f))
f = os.path.join(CO, 'v13A', 'asm_parts', 'Fasteners.step')
if os.path.exists(f):                     # only the front screws (x < 0) are kept; the 4 at x 112-119.5 held Rutten's casing/exhaust
    fs = [s for s in load(f).Solids if s.BoundBox.XMax < 0]
    if fs: SHAPES['core:Fasteners_front'] = ('core', Part.makeCompound(fs))
SUBDIRS = [('E2', os.path.join(CO, 'engine', 'E2'), 'E2-'), ('E3', os.path.join(CO, 'engine', 'E3'), 'E3-')] if VARIANT == 'A' else \
          [('E2B', os.path.join(CO, 'variant_b', 'E2B'), 'E2B-'), ('E3', os.path.join(CO, 'engine', 'E3'), 'E3-')]
for sub, d_, pre in SUBDIRS:
    for f in sorted(glob.glob(os.path.join(d_, '%s*.step' % pre))):
        SHAPES['%s:%s' % (sub, os.path.basename(f)[:-5])] = (sub, load(f))
if VARIANT == 'A':
    for g in ('core', 'headers_plenums', 'ducts', 'supports', 'ports', 'insulation'):
        f = os.path.join(CO, 'engine', 'E4', 'E4_%s.step' % g)
        if os.path.exists(f):
            s = load(f); s.translate(V(-ENG0[0], -ENG0[1], -ENG0[2])); SHAPES['E4:' + g] = ('E4', s)
say('variant %s: loaded %d shapes: %s' % (VARIANT, len(SHAPES), {k: sum(1 for v in SHAPES.values() if v[0] == k) for k in ('core', 'E2', 'E2B', 'E3', 'E4')}))

# bolted joints between subsystems: faces touch (distance 0) but must not overlap
JOINT_TOUCH = {('E2:E2-102_C1_Outlet_Nozzle', 'E4:ducts'): 'C1 flange pair', ('E2:E2-151_C2_Inlet_Duct_RectFlange', 'E4:ducts'): 'C2 flange pair',
               ('E3:E3-110_Collector_Body', 'E4:ducts'): 'H1 flange pair', ('E2:E2-150_Hot_Pressure_Casing', 'E3:E3-101_Interduct_NGV_module'): 'E2/E3 flange (1 mm gasket gap)',
               ('E2B:E2B-150_Rear_Pressure_Casing', 'E3:E3-101_Interduct_NGV_module'): 'E2-B/E3 flange (1 mm gasket gap)'}
def overlap(a, b):
    if not a.BoundBox.intersect(b.BoundBox): return 0.0
    try: return a.common(b).Volume
    except Exception: return -1.0
keys = sorted(SHAPES)
res = dict(pairs_checked=0, interferences=[], joint_contacts={}, near_misses_mm={}, flanges={})
for i, a in enumerate(keys):
    for b in keys[i + 1:]:
        sa, sb = SHAPES[a][0], SHAPES[b][0]
        if sa == sb: continue                                  # same subsystem: checked by its own build script
        A, B = SHAPES[a][1], SHAPES[b][1]
        res['pairs_checked'] += 1
        v = overlap(A, B)
        if v > 1.0 or v < 0:
            res['interferences'].append(dict(a=a, b=b, vol_mm3=round(v, 2)))
            say('  INTERFERENCE %s / %s : %.1f mm3' % (a, b, v))
        jt = JOINT_TOUCH.get((a, b)) or JOINT_TOUCH.get((b, a))
        if jt:
            res['joint_contacts'][jt] = dict(a=a, b=b, overlap_mm3=round(max(v, 0.0), 3), distance_mm=round(A.distToShape(B)[0], 3))
        elif v <= 1.0 and A.BoundBox.intersect(B.BoundBox) and (sa, sb) != ('E3', 'core') and (sb, sa) != ('E3', 'core'):
            res['near_misses_mm']['%s / %s' % (a, b)] = 'bounding boxes overlap, no solid overlap'   # distToShape is too slow on B-spline parts
        if res['pairs_checked'] % 200 == 0: say('  ... %d pairs' % res['pairs_checked'])
say('pairs checked %d, interferences %d' % (res['pairs_checked'], len(res['interferences'])))

# flange coincidence from the published interface files (all converted to ENG mm)
def jl(p):
    return json.load(open(p)) if os.path.exists(p) else {}
e2 = jl(os.path.join(CO, 'engine', 'E2', 'E2_interfaces.json') if VARIANT == 'A' else os.path.join(CO, 'variant_b', 'E2B', 'E2B_interfaces.json'))
e3 = jl(os.path.join(CO, 'engine', 'E3', 'E3_interfaces.json'))
e4 = jl(os.path.join(CO, 'engine', 'E4', 'E4_interfaces.json')) if VARIANT == 'A' else {}
def find(js, token, key):
    for it in js.get('interfaces', []):
        if token in it.get('name', ''): return it.get(key)
    return None
def r2e(p): return [round(p[0] * 1000 - ENG0[0], 2), round(p[1] * 1000 - ENG0[1], 2), round(p[2] * 1000 - ENG0[2], 2)]
pairs = [('C1', find(e2, 'C1 compressor', 'ENG_mm'), find(e4, 'C1 cold inlet', 'eng_mm'), find(e4, 'C1 cold inlet', 'roof_m')),
         ('C2', find(e2, 'C2 recuperated', 'ENG_mm'), find(e4, 'C2 cold outlet', 'eng_mm'), find(e4, 'C2 cold outlet', 'roof_m')),
         ('H1', find(e3, 'H1 exhaust', 'ENG_mm'), find(e4, 'H1 hot inlet', 'eng_mm'), find(e4, 'H1 hot inlet', 'roof_m'))]
for tag, pe, p4, r4 in pairs:
    if pe and p4:
        dev = max(abs(a - b) for a, b in zip(pe, p4)); dev_r = max(abs(a - b) for a, b in zip(pe, r2e(r4))) if r4 else None
        res['flanges'][tag] = dict(engine_side_ENG=pe, E4_ENG=p4, E4_ROOF_m=r4, max_dev_mm=round(dev, 2), max_dev_via_ROOF_mm=dev_r, ok=dev < 0.5 and (dev_r is None or dev_r < 0.5))
x23 = find(e2, 'IF-E2E3', 'ENG_mm'); x32 = find(e3, 'IF-E2E3', 'ENG_mm')
if x23 and x32:
    res['flanges']['E2/E3'] = dict(E2_face_x=x23[0], E3_face_x=x32[0], gap_mm=round(x32[0] - x23[0], 2), ok=abs(x32[0] - x23[0] - 1.0) < 0.05,
                                   note='1.0 mm gasket E3-605 between the faces')
for k, v in res['flanges'].items(): say('  flange %-5s %s' % (k, v))
bb = App.BoundBox()
for k, (sub, s) in SHAPES.items(): bb.add(s.BoundBox)
res['stack_bbox_ENG_mm'] = [[round(bb.XMin, 1), round(bb.YMin, 1), round(bb.ZMin, 1)], [round(bb.XMax, 1), round(bb.YMax, 1), round(bb.ZMax, 1)]]
res['stack_bbox_ROOF_m'] = [[round((ENG0[i] + v) / 1000, 3) for i, v in enumerate(res['stack_bbox_ENG_mm'][0])],
                            [round((ENG0[i] + v) / 1000, 3) for i, v in enumerate(res['stack_bbox_ENG_mm'][1])]]
EP1 = dict(x=(1.30, 2.90), y=(7.60, 8.60), z=(0.0, 1.30))
lo, hi = res['stack_bbox_ROOF_m']
res['inside_EP1'] = None if VARIANT != 'A' else all(EP1[a][0] - 1e-3 <= lo[i] and hi[i] <= EP1[a][1] + 1e-3 for i, a in enumerate('xyz'))
res['EP1_ROOF_m'] = EP1
say('stack bbox ROOF %s -> inside EP-1 %s' % (res['stack_bbox_ROOF_m'], res['inside_EP1']))
OUTF = os.path.join(CO, 'engine', 'engine_stack_checks.json') if VARIANT == 'A' else os.path.join(CO, 'variant_b', 'stack_checks_B.json')
res['variant'] = VARIANT
json.dump(res, open(OUTF, 'w'), indent=1)
say('written', OUTF)
