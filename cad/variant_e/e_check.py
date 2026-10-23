# GR180 version E - whole-machine check: interference of every part against every other (bbox pre-filter, common volume),
# overall dimensions, masses per subsystem / module, centre of gravity, and the external interfaces json.
# Run after all e_*.py builders:  LANG=en_US.UTF-8 freecadcmd cad/variant_e/e_check.py
#   -> cad_out/variant_e/e_check.json, cad_out/variant_e/e_interfaces.json  (+ copies in sim/variant_e/ for git)
import FreeCAD as App, Part, os, sys, json, glob, itertools, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
import e_layout as L
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_e')
TOL_MM3 = 1.0
TOUCH_MM = 0.05
V = App.Vector

shapes, meta = {}, {}
for pj in sorted(glob.glob(os.path.join(OUT, '*', 'e_*_parts.json'))):
    d = json.load(open(pj))
    for tag, row in d['parts'].items():
        shapes[d['subsystem'] + '/' + tag] = Part.read(os.path.join(ROOT, row['step']))
        meta[d['subsystem'] + '/' + tag] = row
names = sorted(shapes)
print('parts:', len(names))
res = dict(tol_mm3=TOL_MM3, overlaps=[], contacts=[], checked_pairs=0, parts=len(names))
for a, b in itertools.combinations(names, 2):
    A, B = shapes[a], shapes[b]
    if not A.BoundBox.intersect(B.BoundBox):
        continue
    res['checked_pairs'] += 1
    try:
        v = A.common(B).Volume
    except Exception:
        v = -1.0
    if v > TOL_MM3 or v < 0:
        res['overlaps'].append(dict(a=a, b=b, mm3=round(v, 2)))
        print('OVERLAP %-50s %-50s %.2f mm3' % (a, b, v))
    else:
        try:
            dd = A.distToShape(B)[0]
        except Exception:
            dd = 99.0
        if dd < TOUCH_MM:
            res['contacts'].append(dict(a=a, b=b, gap_mm=round(dd, 3)))
print('checked pairs %d, overlaps %d, contact faces %d' % (res['checked_pairs'], len(res['overlaps']), len(res['contacts'])))

# ------------------------------------------------------------------ dimensions, masses, CG
bb = None
for n in names:
    bb = shapes[n].BoundBox if bb is None else bb.united(shapes[n].BoundBox)
floor_z = L.FRAME['z_top'] - L.FRAME['rhs'][0] - L.FRAME['av_h']
dims = dict(x=[round(bb.XMin, 1), round(bb.XMax, 1)], y=[round(bb.YMin, 1), round(bb.YMax, 1)], z=[round(bb.ZMin, 1), round(bb.ZMax, 1)],
            L_W_H_mm=[round(bb.XLength), round(bb.YLength), round(bb.ZMax - floor_z)], floor_z=floor_z, axis_above_floor=-floor_z,
            note='H from the floor (AV-mount base) to the top of the UV scanner; the filter house / hood on the 1830 x 1830 interface adds ~0.6-0.9 m (plant scope)')
sub_m = {}
for n in names:
    s = n.split('/')[0]
    sub_m[s] = sub_m.get(s, 0.0) + meta[n]['mass_kg']
tot = sum(sub_m.values())
mx = my = mz = 0.0
for n in names:
    m = meta[n]['mass_kg']
    try:
        c = shapes[n].CenterOfGravity if hasattr(shapes[n], 'CenterOfGravity') else shapes[n].Solids[0].CenterOfMass
    except Exception:
        c = shapes[n].BoundBox.Center
    mx += m * c.x; my += m * c.y; mz += m * c.z
cg = [round(mx / tot), round(my / tot), round(mz / tot)]
modules = dict(
    core_engine=sum(sub_m.get(k, 0) for k in ('ROTOR', 'COMPRESSOR', 'BEARING', 'TURBINE', 'COMBUSTOR')),
    generator_pod=sub_m.get('GENERATOR', 0), exhaust=sub_m.get('EXHAUST', 0), intake_plenum=sub_m.get('INTAKE', 0), frame=sub_m.get('FRAME', 0))
res.update(dimensions=dims, mass_by_subsystem_kg={k: round(v, 1) for k, v in sub_m.items()}, mass_total_kg=round(tot, 1),
           mass_modules_kg={k: round(v, 1) for k, v in modules.items()}, cg_mm=cg,
           make_buy=dict(make=sum(1 for n in names if meta[n]['make_buy'].startswith('make')), buy=sum(1 for n in names if meta[n]['make_buy'].startswith('buy'))),
           notes=['wheel / bearing / magnet solids are blade-filled ENVELOPES; their masses are supplier estimates',
                  'fasteners, O-rings, piston rings, oil / glycol / gas piping, insulation and the auxiliaries skid (oil, glycol, gas train, '
                  'drive cabinet) are BOM rows, not CAD (docs/bom/variant_e_bom.csv)'])
print('dims', dims); print('mass by subsystem', res['mass_by_subsystem_kg'], 'total', res['mass_total_kg'], 'CG', cg)
json.dump(res, open(os.path.join(OUT, 'e_check.json'), 'w'), indent=1)

# ------------------------------------------------------------------ external interfaces (ENG mm; ROOF transform as D2: X = 1.880 + x/1000 ...)
ex = json.load(open(os.path.join(OUT, 'EXHAUST', 'e_exhaust_parts.json')))
I = dict(
    title='GR180 version E external interfaces', frame='ENG mm (x = engine axis downstream, x = 0 at the compressor tip, z up, axis %.0f mm above the floor)' % -floor_z,
    air_inlet=dict(where='top of the intake plenum, 3 x 3 filter-cell interface 1830 x 1830 at z %.0f' % (L.PLENUM['z'][1] + 15), centre=[0.5 * sum(L.PLENUM['x']), 0.0, L.PLENUM['z'][1] + 15],
                   flow='3.0 kg/s (2.6 m3/s at 30 C), up to 3.5 kg/s at 0 C', dp_budget='<= 0.25 % incl. filters (mid-life)'),
    exhaust=dict(where='elbow outlet flange facing up', centre=[ex['outlet']['x'], 0.0, ex['outlet']['z']], flange=ex['outlet']['flange'],
                 flow='3.03 kg/s at ~525 C (TIT 770) / ~600 C (TIT 850)', back_pressure='CHP + stack <= 1.2 kPa (cycle basis)'),
    gas=dict(where='gas-lance head on the combustor cover, G3/4', position=[L.X_CAN, 80.0, 1240.0], pressure='>= 3.73 barg at the skid (booster below 3.7 barg)', flow='204 m3/h at 770 C, 30 C'),
    oil=dict(feed='core: 2 gallery feeds through the top deswirl vane (x 80); generator: end-bell jets (top)', drain='core: bottom deswirl vane (x 80) to the tank; generator: end-bell drains',
             spec='ISO VG 32, 2.5 barg, ~25 L/min total, ~7 kW to the glycol / air cooler'),
    glycol=dict(where='pod housing G1/2 ports at x -780 / -455 (top)', flow='30 L/min, inlet <= 45 C, ~4 kW (PMG) + converter + oil cooler on the same loop'),
    power=dict(where='terminal box on the pod top (x -630, z 260)', rating='3-ph ~650-820 V(dc after the bridge), 2-pole 583 Hz, 335 kW shaft; diode bridge + 400 V AFE in the drive cabinet'),
    supports=dict(fixed='outer-casing trunnion pads x 50..95, y +/-(314..400), z 0 (pedestals E-F120)', sliding='cool-casing pads x 270..300, y +/-(370..420) (E-F121); exhaust saddles (E-F122)',
                  generator='2 saddles on the plenum floor, shims / jack bolts; quill float +/-1 mm', av_mounts='8 x under the rails at x -2000/-800/400/2150, y +/-550'),
    removal=dict(generator='unbolt the guard flange, slide the pod forward 150 mm on its saddles (quill socket leaves the hex), lift out through the plenum door / filter opening',
                 combustor='unbolt the DN300 cover: lift the cover + lance + liner (hangers) upward; casing stays',
                 hot_section='remove the exhaust cone (slip collar) -> unbolt the cool-casing front flange -> slide the cool casing rearward over the shroud -> '
                             'hot plenum + shroud + nozzle ring come off the bearing-housing rear flange as a stack; turbine wheel stays on the rotor',
                 core_rotor='with the hot stack off: inlet cover off -> nut -> compressor wheel off the d40 seat -> rotor withdrawn rearward through the bearing housing'))
json.dump(I, open(os.path.join(OUT, 'e_interfaces.json'), 'w'), indent=1)
summ = dict(check={k: res[k] for k in ('parts', 'checked_pairs', 'tol_mm3')}, overlaps=res['overlaps'], n_contacts=len(res['contacts']), dimensions=dims,
            mass_by_subsystem_kg=res['mass_by_subsystem_kg'], mass_total_kg=res['mass_total_kg'], mass_modules_kg=res['mass_modules_kg'], cg_mm=cg,
            make_buy=res['make_buy'], parts={n: dict(mass_kg=meta[n]['mass_kg'], mass_source=meta[n]['mass_source'], material=meta[n]['material'], make_buy=meta[n]['make_buy'],
                                                     desc=meta[n]['desc'], note=meta[n]['note'], bbox=meta[n]['bbox'], step=meta[n]['step']) for n in names}, interfaces=I)
json.dump(summ, open(os.path.join(ROOT, 'sim', 'variant_e', 'e_cad_summary.json'), 'w'), indent=1)
print('-> cad_out/variant_e/e_check.json, e_interfaces.json, sim/variant_e/e_cad_summary.json')
