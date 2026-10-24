# GR180 version E - interference check of the detailed generator (EG) against itself and against every other version-E
# part (cad_out/variant_e/*/e_*_parts.json): bbox pre-filter, common volume (> 1 mm3 = overlap), distance for contacts;
# generator mass / CG / envelope summary.  Run after eg_generator.py (or e_generator.py with GEN_DETAILED):
#   LANG=en_US.UTF-8 freecadcmd cad/variant_e/eg_check.py  ->  cad_out/variant_e/GENERATOR/eg_check.json + sim/variant_e/eg_check.json
import FreeCAD as App, Part, os, sys, json, glob, itertools
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e')
sys.path.insert(0, HERE)
import eg_layout as G
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_e')
TOL_MM3, TOUCH_MM = 1.0, 0.05

shapes, meta = {}, {}
for pj in sorted(glob.glob(os.path.join(OUT, '*', 'e_*_parts.json'))):
    d = json.load(open(pj))
    for tag, row in d['parts'].items():
        k = d['subsystem'] + '/' + tag
        shapes[k] = Part.read(os.path.join(ROOT, row['step']))
        meta[k] = row
gen = sorted(k for k in shapes if k.startswith('GENERATOR/'))
oth = sorted(k for k in shapes if not k.startswith('GENERATOR/'))
print('generator parts %d, other parts %d' % (len(gen), len(oth)))
res = dict(tol_mm3=TOL_MM3, generator_parts=len(gen), other_parts=len(oth), checked_pairs=0, checked_solid_pairs=0, overlaps=[], contacts=[])
SOL = {k: [(s_, s_.BoundBox) for s_ in (shapes[k].Solids or [shapes[k]])] for k in shapes}


def grown(bb, d):
    b = App.BoundBox(bb); b.enlarge(d); return b


pairs = list(itertools.combinations(gen, 2)) + [(a, b) for a in gen for b in oth]
for n_, (a, b) in enumerate(pairs):
    A, B = shapes[a], shapes[b]
    if not grown(A.BoundBox, TOUCH_MM).intersect(B.BoundBox):
        continue
    res['checked_pairs'] += 1
    v = 0.0; dmin = 99.0
    for sa, ba in SOL[a]:
        ga = grown(ba, TOUCH_MM)
        for sb, bb_ in SOL[b]:
            if not ga.intersect(bb_):
                continue
            res['checked_solid_pairs'] += 1
            if ba.intersect(bb_):
                try:
                    v += sa.common(sb).Volume
                except Exception:
                    v = -1e9
            if dmin > TOUCH_MM:
                try:
                    dmin = min(dmin, sa.distToShape(sb)[0])
                except Exception:
                    pass
    if v > TOL_MM3 or v < 0:
        res['overlaps'].append(dict(a=a, b=b, mm3=round(v, 2)))
        print('OVERLAP %-48s %-48s %.2f mm3' % (a, b, v), flush=True)
    elif dmin < TOUCH_MM:
        res['contacts'].append(dict(a=a, b=b, gap_mm=round(dmin, 3)))
    if res['checked_pairs'] % 50 == 0:
        print('  ... %d part pairs, %d solid pairs' % (res['checked_pairs'], res['checked_solid_pairs']), flush=True)
print('checked pairs %d, overlaps %d, contacts %d' % (res['checked_pairs'], len(res['overlaps']), len(res['contacts'])))
# masses, CG, envelope
groups = dict(rotor=[k for k in gen if any(s in k for s in ('Shaft', 'Screen', 'Magnet', 'CFRP', 'Locknut', 'Speed_', 'IR_Spacer', 'Quill_Hollow', 'Pull_Bolt'))],
              stator_pod=[k for k in gen if any(s in k for s in ('Housing', 'Jacket', 'Stator', 'Winding', 'Wedges', 'Circlip', 'Jacket_Dowel', 'End_Bell', 'Cap', 'Bearing_7008',
                                                                  'SFD', 'Wave', 'Shim', 'Spacer_Tube', 'Screws', 'HELICOIL', 'Dowels', 'O-ring', 'Pins', 'Terminal', 'PEEK',
                                                                  'IR_Pyro', 'Speed_Probes', 'Accelero', 'Fittings', 'Hood'))],
              guard=[k for k in gen if 'Guard' in k], supports=[k for k in gen if any(s in k for s in ('Saddle', 'Base_Beam'))],
              cooling_air=[k for k in gen if any(s in k for s in ('Blower', 'Filter', 'Bellows'))])
gm = {g: round(sum(meta[k]['mass_kg'] for k in ks), 2) for g, ks in groups.items()}
bb = None
for k in gen:
    if k in groups['supports'] or k in groups['cooling_air']:
        continue
    bb = shapes[k].BoundBox if bb is None else bb.united(shapes[k].BoundBox)
tot = sum(meta[k]['mass_kg'] for k in gen)
mx = sum(meta[k]['mass_kg'] * shapes[k].BoundBox.Center.x for k in gen) / tot
res.update(mass_kg=dict(groups=gm, total=round(tot, 1), pod_incl_rotor_guard=round(gm['rotor'] + gm['stator_pod'] + gm['guard'], 1)),
           pod_envelope_mm=dict(x=[round(bb.XMin, 1), round(bb.XMax, 1)], y=[round(bb.YMin, 1), round(bb.YMax, 1)], z=[round(bb.ZMin, 1), round(bb.ZMax, 1)],
                                L_x_W_x_H=[round(bb.XLength), round(bb.YLength), round(bb.ZLength)]),
           x_cg_total=round(mx, 1), rotor_parts=groups['rotor'],
           interfaces=dict(quill_socket=G.QUILL_EG['socket'], hex_engage=G.QUILL_EG['hex_engage'], rear_bearing_x=G.X_GR, guard_end_x=G.GUARD['x'][1],
                           saddles_x=G.SADDLE['x'], base_beam=G.SADDLE['base'], note='base beam bolted through the plenum floor onto the frame cross members at x -1050 / -600 / -200'))
print('masses', gm, 'total', round(tot, 1), 'envelope', res['pod_envelope_mm'])
json.dump(res, open(os.path.join(OUT, 'GENERATOR', 'eg_check.json'), 'w'), indent=1)
json.dump(res, open(os.path.join(ROOT, 'sim', 'variant_e', 'eg_check.json'), 'w'), indent=1)
print('-> cad_out/variant_e/GENERATOR/eg_check.json, sim/variant_e/eg_check.json')
