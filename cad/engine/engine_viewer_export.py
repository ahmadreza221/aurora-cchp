"""GR180-CCHP engine assembly -> one GLB for the web viewer (viewer/engine/index.html).

Collects the current design of every engine subsystem in the ENG frame (mm, x = engine axis, z up):
  core   v13A core (build_gr180.py, cad_out/v13A/asm_parts) minus the parts replaced by E1/E2/E3
  E1     gas-generator turbine stage (fusion/E1: bore-less disc + 29 blades, NGV rings + 21 vanes, welded shaft)
  E2     recuperated combustor + pressure casing (cad_out/engine/E2/*.step or $GR180_E2_DIR), if built yet;
         otherwise the v13A combustor is shown in group 'legacy' as a stand-in
  E3     interduct + FPT + bearings + PMG + collector (cad_out/engine/E3/E3-*.step)
  E4     recuperator (cad_out/engine/E4/*.step, ROOF mm -> ENG mm)
Blades and vanes are written once and instanced, so the GLB stays small.
Run:  LANG=en_US.UTF-8 freecadcmd -c "exec(open('cad/engine/engine_viewer_export.py',encoding='utf-8').read())"
"""
import os, glob, json, csv, math, struct
import FreeCAD as App, Part, MeshPart
import numpy as np

ROOT = os.environ.get('GR180_ROOT') or os.getcwd()
OUT = os.path.join(ROOT, 'viewer', 'engine'); os.makedirs(OUT, exist_ok=True)
E2_DIR = os.environ.get('GR180_E2_DIR') or os.path.join(ROOT, 'cad_out', 'engine', 'E2')
ROOF2ENG = App.Vector(-1680.0, -7850.0, -600.0)

GROUPS = {   # name: (label, rgba, metallic, roughness)
    'core':   ('GR180 core (v13A)', (0.72, 0.74, 0.78, 1.0), 0.7, 0.35),
    'E1':     ('E1 GG turbine + NGV (IN713LC)', (0.25, 0.45, 0.85, 1.0), 0.8, 0.30),
    'E2':     ('E2 combustor + pressure casing', (0.85, 0.55, 0.20, 1.0), 0.6, 0.40),
    'E3':     ('E3 interduct + FPT + PMG', (0.90, 0.62, 0.25, 1.0), 0.6, 0.40),
    'E3pmg':  ('E3 PMG (stator, magnets, windings)', (0.72, 0.42, 0.20, 1.0), 0.7, 0.35),
    'E3sens': ('E3 sensors', (0.20, 0.70, 0.40, 1.0), 0.3, 0.50),
    'E4':     ('E4 recuperator', (0.60, 0.62, 0.60, 1.0), 0.6, 0.45),
    'E4ins':  ('E4 insulation', (0.95, 0.93, 0.85, 0.35), 0.0, 0.90),
    'legacy': ('v13A combustor (stand-in until E2)', (0.80, 0.35, 0.30, 1.0), 0.5, 0.50),
}

def bom_rows():
    rows = {}
    for f in glob.glob(os.path.join(ROOT, 'docs', 'bom', 'engine_*_bom.csv')):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            mf = os.path.basename(r.get('model_file') or '')
            rows.setdefault(r['tag'], r)
            if mf: rows.setdefault('file:' + mf, r)
    return rows
BOM = bom_rows()

parts = []   # dict(name, group, shape, inst=[angle_deg...] or None, meta)
def add(name, group, shape, inst=None, **meta):
    if shape is None or shape.isNull(): print('skip empty', name); return
    parts.append(dict(name=name, group=group, shape=shape, inst=inst, meta=meta))

def read(path, move=None):
    s = Part.Shape(); s.read(path)
    if move is not None: s.translate(move)
    return s

# ---- E2 present? -----------------------------------------------------------------------------------------------
e2_files = sorted(glob.glob(os.path.join(E2_DIR, '*.step')))
e2_files = [f for f in e2_files if 'assembly' not in os.path.basename(f).lower()]
has_e2 = bool(e2_files)

# ---- core v13A -------------------------------------------------------------------------------------------------
REPLACED = {'Turbine', 'TurbineNut', 'NGV', 'Shaft', 'Exhaust', 'Balance_Slug'}        # by E1 / E3
COMBUSTOR = {'CC_FrontCap', 'CC_Inner', 'CC_Outer', 'CC_RearCone', 'CC_Vaporisers', 'Casing',
             'GasBulkhead', 'SupplyLines', 'SupplySeals'}                               # by E2
for f in sorted(glob.glob(os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts', '*.step'))):
    n = os.path.splitext(os.path.basename(f))[0]
    if n in REPLACED: continue
    if n in COMBUSTOR:
        if has_e2: continue
        add('v13A ' + n, 'legacy', read(f), desc='v13A part, replaced by E2 (recuperated combustor, no vaporisers)')
    else:
        add('v13A ' + n, 'core', read(f), desc='GR180 core per Rutten drawings (build_gr180.py v13A)')

# ---- E1 --------------------------------------------------------------------------------------------------------
E1 = os.path.join(ROOT, 'fusion', 'E1')
add('E1 disc (bore-less, final)', 'E1', read(os.path.join(E1, 'E1_disc_boreless_final.step')),
    desc='GG turbine disc, cast IN713LC, friction-welded to the shaft at x 104.3')
add('E1 rotor blade x29', 'E1', read(os.path.join(E1, 'E1_blade_final.step')),
    inst=[360.0 * k / 29 for k in range(29)], desc='29 blades, integral with the disc (blisk)')
add('E1 NGV rings (final)', 'E1', read(os.path.join(E1, 'E1_ngv_rings_final.step')),
    desc='NGV inner/outer rings, cast IN713LC')
add('E1 NGV vane x21', 'E1', read(os.path.join(E1, 'E1_ngv_vane_final.step')),
    inst=[360.0 * k / 21 for k in range(21)], desc='21 NGV vanes, cast integral with the rings')
add('E1 shaft (42CrMo4, welded)', 'E1', read(os.path.join(E1, 'E1_shaft_welded.step')),
    desc='GG shaft, 42CrMo4, friction-welded to the disc; compressor-side nut clamps the stack')

# ---- E2 --------------------------------------------------------------------------------------------------------
for f in e2_files:
    n = os.path.splitext(os.path.basename(f))[0]
    r = BOM.get('file:' + os.path.basename(f)) or {}
    add(n, 'E2', read(f), desc=r.get('description', ''), material=r.get('material_or_spec', ''))

# ---- E3 --------------------------------------------------------------------------------------------------------
for f in sorted(glob.glob(os.path.join(ROOT, 'cad_out', 'engine', 'E3', 'E3-*.step'))):
    n = os.path.splitext(os.path.basename(f))[0]
    tag = n.split('_')[0]
    num = int(tag.split('-')[1])
    g = 'E3sens' if 500 <= num < 600 else ('E3pmg' if num in (202, 203, 204, 303, 304) else 'E3')
    r = BOM.get(tag) or {}
    add(n, g, read(f), desc=r.get('description', ''), material=r.get('material_or_spec', ''), mass_kg=r.get('mass_kg', ''))

# ---- E4 (ROOF mm -> ENG mm) --------------------------------------------------------------------------------------
for key in ('core', 'headers_plenums', 'ducts', 'ports', 'supports', 'insulation'):
    f = os.path.join(ROOT, 'cad_out', 'engine', 'E4', 'E4_%s.step' % key)
    if not os.path.exists(f): continue
    add('E4 ' + key.replace('_', ' + '), 'E4ins' if key == 'insulation' else 'E4', read(f, ROOF2ENG),
        desc={'core': 'two brazed plate-fin cores, 347H, counterflow', 'insulation': 'insulation (skin <= 60 C)'}.get(key, ''))

# ---- tessellate + GLB --------------------------------------------------------------------------------------------
def tess(shape):
    """Indexed mesh (shared vertices, no normals: the viewer flat-shades). Angular deflection caps cylinder facets."""
    bb = shape.BoundBox
    tol = max(0.02, min(0.8, bb.DiagonalLength * 0.0012))
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=tol, AngularDeflection=0.35, Relative=False)
    pts, tris = m.Topology
    if not tris: return None, None, tol
    P = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float32)
    T = np.array(tris, dtype=np.uint32).reshape(-1)
    return P, T, tol

bin_chunks, bufviews, accessors, meshes, materials, nodes = [], [], [], [], [], []
offset = 0
def push(arr, target):
    global offset
    b = arr.tobytes(); pad = (-len(b)) % 4
    bin_chunks.append(b + b'\0' * pad)
    bufviews.append(dict(buffer=0, byteOffset=offset, byteLength=len(b), target=target))
    offset += len(b) + pad
    return len(bufviews) - 1

mat_index = {}
for g, (label, rgba, met, rough) in GROUPS.items():
    m = dict(name=g, pbrMetallicRoughness=dict(baseColorFactor=list(rgba), metallicFactor=met, roughnessFactor=rough),
             doubleSided=True)
    if rgba[3] < 1: m['alphaMode'] = 'BLEND'
    mat_index[g] = len(materials); materials.append(m)

group_children = {g: [] for g in GROUPS}
summary = []
for p in parts:
    V, T, tol = tess(p['shape'])
    if V is None: print('no triangles', p['name']); continue
    bvp = push(V, 34962); bvi = push(T, 34963)
    accessors.append(dict(bufferView=bvp, componentType=5126, count=len(V), type='VEC3',
                          min=V.min(0).tolist(), max=V.max(0).tolist()))
    ap = len(accessors) - 1
    accessors.append(dict(bufferView=bvi, componentType=5125, count=len(T), type='SCALAR')); ai = len(accessors) - 1
    meshes.append(dict(name=p['name'], primitives=[dict(attributes=dict(POSITION=ap), indices=ai, material=mat_index[p['group']])]))
    mi = len(meshes) - 1
    bb = p['shape'].BoundBox
    extras = dict(group=p['group'], **{k: v for k, v in p['meta'].items() if v})
    extras['bbox_mm'] = [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)]
    angles = p['inst'] or [0.0]
    if p['inst']:
        kids = []
        for a in angles:
            h = math.radians(a) / 2
            nodes.append(dict(name='%s #%d' % (p['name'], len(kids) + 1), mesh=mi, rotation=[math.sin(h), 0, 0, math.cos(h)]))
            kids.append(len(nodes) - 1)
        nodes.append(dict(name=p['name'], children=kids, extras=extras))
    else:
        nodes.append(dict(name=p['name'], mesh=mi, extras=extras))
    group_children[p['group']].append(len(nodes) - 1)
    summary.append(dict(extras, name=p['name'], tris=len(T) // 3 * len(angles), tol_mm=round(tol, 3)))
    print('%-45s %-7s %8d tris  tol %.3f' % (p['name'], p['group'], len(T) // 3, tol), flush=True)

gnodes = []
for g, kids in group_children.items():
    if not kids: continue
    nodes.append(dict(name=g, children=kids, extras=dict(label=GROUPS[g][0]))); gnodes.append(len(nodes) - 1)
s = math.sqrt(0.5)
nodes.append(dict(name='GR180-CCHP engine (ENG frame, mm)', children=gnodes, rotation=[-s, 0, 0, s], scale=[0.001] * 3))
root = len(nodes) - 1

gltf = dict(asset=dict(version='2.0', generator='GR180 engine_viewer_export.py'), scene=0, scenes=[dict(nodes=[root])],
            nodes=nodes, meshes=meshes, materials=materials, accessors=accessors, bufferViews=bufviews,
            buffers=[dict(byteLength=offset)])
js = json.dumps(gltf, separators=(',', ':')).encode('utf-8'); js += b' ' * ((-len(js)) % 4)
binb = b''.join(bin_chunks)
with open(os.path.join(OUT, 'engine.glb'), 'wb') as fh:
    fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binb)))
    fh.write(struct.pack('<II', len(js), 0x4E4F534A)); fh.write(js)
    fh.write(struct.pack('<II', len(binb), 0x004E4942)); fh.write(binb)
json.dump(dict(has_e2=has_e2, groups={g: GROUPS[g][0] for g in GROUPS}, parts=summary),
          open(os.path.join(OUT, 'engine_parts.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('GLB %.1f MB, %d parts, E2 %s' % ((offset + len(js)) / 1e6, len(summary), 'yes' if has_e2 else 'no (legacy stand-in)'))
