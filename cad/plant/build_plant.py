"""GR180-CCHP roof plant - build the scripted FreeCAD model, STEP files, interfaces, BOM, clash report and renders.

Run from the project folder:
    LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/plant/build_plant.py
Options (environment): PLANT_FAST=1 skips STEP export of single items and renders (quick clash iteration).

Outputs (only these folders are written):
    cad_out/plant/plant_assembly.step, items/*.step, piping/*.step, structure.step, reference_building.step,
    indoor_water_dhw.step, indoor_electrical_room.step, plant_interfaces.json, clash_report.txt, render_*.png
    docs/bom/plant_bom.csv
"""
import csv
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import FreeCAD as App
import Part
import Import

import plant_lib as L
import plant_items as PI

OUT = os.path.join(ROOT, 'cad_out', 'plant')
BOM = os.path.join(ROOT, 'docs', 'bom', 'plant_bom.csv')
FAST = os.environ.get('PLANT_FAST') == '1'
for d in (OUT, os.path.join(OUT, 'items'), os.path.join(OUT, 'piping'), os.path.dirname(BOM)):
    os.makedirs(d, exist_ok=True)
assert os.path.realpath(OUT).startswith(os.path.realpath(os.path.join(ROOT, 'cad_out', 'plant')))

T0 = time.time()
m = L.Model()
PI.equipment(m)
PI.piping(m)
PI.hall(m)
PI.interfaces(m)

# walkways (GRP grating tiles on pads at roof level); low pipes crossing them get auto step-over stiles
# WK-1 0.62 m wide between the DC-1 pad-water riser (x 1.66) and the engine glycol risers (x 2.40)
m.walkways = [dict(x0=1.72, y0=0.40, x1=2.34, y1=7.00, axis='y', name='WK-1 N-S hatch -> engine'),
              dict(x0=2.34, y0=4.45, x1=8.25, y1=5.15, axis='x', name='WK-2 E-W central'),
              dict(x0=1.20, y0=0.40, x1=1.72, y1=1.15, axis='x', name='WK-3 hatch landing')]
walk_area = 0.0
for w in m.walkways:
    m.add('WALK', w['name'], L.box(w['x0'], w['y0'], 0.0, w['x1'] - w['x0'], w['y1'] - w['y0'], 0.03), 'walk',
          (0.98, 0.85, 0.35), group='walkways')
    walk_area += (w['x1'] - w['x0']) * (w['y1'] - w['y0'])
n_stiles = L.step_overs(m)
sup_count = L.auto_supports(m)
print('model built: %d solids, %d routes, %d stiles (%.1f s)' % (len(m.parts), len(m.routes), n_stiles, time.time() - T0))
for w_ in m.warnings:
    print('  WARN', w_)


# ------------------------------------------------------------------------------------------------ checks
def walkway_check():
    res = []
    for w in m.walkways:
        zb = L.box(w['x0'], w['y0'], 0.03, w['x1'] - w['x0'], w['y1'] - w['y0'], 2.07)
        bb = zb.BoundBox
        for p in m.parts:
            if p.group in ('walkways',) or p.kind in ('ref', 'walk'):
                continue
            if not bb.intersect(p.shape.BoundBox):
                continue
            v = zb.common(p.shape)
            if v.Volume < 1000:
                continue
            top = v.BoundBox.ZMax / L.MM
            if p.kind in ('pipe', 'ins') and top <= 0.455:
                continue          # crosses under a stile
            res.append((w['name'], p.label, round(top, 3), v.Volume / 1e3))
    return res


def tower_ring_check():
    (cx, cy), R = m.tower_ring
    ring = Part.makeCylinder(R * L.MM, 2.6 * L.MM, L.V(cx, cy, 0.03)).cut(Part.makeCylinder(0.94 * L.MM, 2.6 * L.MM, L.V(cx, cy, 0.03)))
    res = []
    for p in m.parts:
        if p.owner == 'CT-1' or 'CT-1' in p.connects or p.kind in ('ref', 'walk') or p.owner.startswith('DUN-CT') or p.group == 'walkways':
            continue
        if not ring.BoundBox.intersect(p.shape.BoundBox):
            continue
        v = ring.common(p.shape).Volume
        if v > 1000:
            res.append((p.label, v / 1e3))
    return res


T1 = time.time()
clashes = L.clash_check(m)
hidden = L.connected_overlap_check(m)
zones = L.zone_check(m)
walks = walkway_check()
ring = tower_ring_check()
print('checks: %d clashes, %d connected-item overlaps away from a joint, %d service-zone, %d walkway, %d tower-ring, '
      '%d unchecked pairs (%.1f s)' % (len(clashes), len(hidden), len(zones), len(walks), len(ring), len(m.clash_errors),
                                       time.time() - T1))
with open(os.path.join(OUT, 'clash_report.txt'), 'w') as f:
    f.write('GR180-CCHP roof plant - interference and clearance report (cad/plant/build_plant.py)\n')
    f.write('solids: %d, routes: %d\n\n' % (len(m.parts), len(m.routes)))
    f.write('[1] solid interference > 1 cm3 (connected items and own parts excluded): %d\n' % len(clashes))
    for a, b, v in clashes:
        f.write('  %-45s x %-45s %8.1f cm3\n' % (a, b, v))
    f.write('\n[1b] overlaps between connected items away from any nozzle / route end (> 0.30 m): %d\n' % len(hidden))
    for a, b, v, c, d in hidden:
        f.write('  %-45s x %-45s %8.1f cm3 at %s (%.2f m from a joint)\n' % (a, b, v, c, d))
    f.write('    pairs not checked (boolean failed, check by hand): %d\n' % len(m.clash_errors))
    for a, b in m.clash_errors:
        f.write('      %-45s x %s\n' % (a, b))
    f.write('\n[2] service / door zones (0.03-2.10 m) occupied by unrelated solids: %d\n' % len(zones))
    for o, lab, p, v in zones:
        f.write('  zone %-8s %-28s <- %-40s %8.1f cm3\n' % (o, lab, p, v))
    f.write('\n[3] walkways (0.03-2.10 m; low pipe crossings under stiles allowed): %d\n' % len(walks))
    for wn, p, top, v in walks:
        f.write('  %-28s <- %-40s top %.2f m %8.1f cm3\n' % (wn, p, top, v))
    f.write('\n[4] cooling-tower air-inlet ring (1.0 m) occupied by unrelated solids: %d\n' % len(ring))
    for p, v in ring:
        f.write('  %-40s %8.1f cm3\n' % (p, v))
    f.write('\nwarnings: %d\n' % len(m.warnings))
    for w_ in m.warnings:
        f.write('  %s\n' % w_)
for a, b, v, c, d in hidden:
    print('  HIDDEN %-40s x %-40s %7.1f cm3 at %s' % (a, b, v, c))
for a, b in m.clash_errors:
    print('  UNCHECKED %s x %s' % (a, b))
for a, b, v in clashes[:60]:
    print('  CLASH %-40s x %-40s %7.1f cm3' % (a, b, v))
for o, lab, p, v in zones[:40]:
    print('  ZONE  %-8s %-26s <- %-36s %7.1f cm3' % (o, lab, p, v))
for wn, p, top, v in walks[:40]:
    print('  WALK  %-26s <- %-36s top %.2f' % (wn, p, top))
for p, v in ring[:20]:
    print('  RING  %-40s %7.1f cm3' % (p, v))

# ------------------------------------------------------------------------------------------------ quantities
WALL = {15: 2.77, 20: 2.87, 25: 3.38, 32: 3.56, 40: 3.68, 50: 3.91, 65: 5.16, 80: 5.49, 100: 6.02, 250: 0.8}


def water_kg_m(r):
    od = r.od
    t = od / 11.0 if r.mat == 'PE100' else (od / 7.4 if r.mat == 'PPR' else WALL.get(r.dn, 3.0))
    if r.mat in ('DUCT',) or r.service.startswith('FK') or r.mat == 'GAS' or r.line.startswith('L-DR'):
        return 0.0
    return math.pi / 4 * ((od - 2 * t) / 1000) ** 2 * 1000


def ins_kg_m(r):
    if not r.ins or r.mat == 'DUCT':
        return 0.0
    t = L.INSULATION[r.ins][1] / 1000
    od = r.od / 1000
    rho = 100 if r.ins.startswith('MW') else 60
    area = math.pi / 4 * ((od + 2 * t) ** 2 - od ** 2)
    clad = 0.0 if r.ins == 'EL19' else math.pi * (od + 2 * t) * 0.0007 * 2700
    return area * rho + clad


rows = []


def row(tag, desc, qty, mb, spec, size, sup, mass, model, notes=''):
    rows.append(dict(tag=tag, description=desc, qty=qty, make_or_buy=mb, material_or_spec=spec, size_or_rating=size,
                     supplier_candidates=sup, mass_kg=mass, model_file=model, notes=notes))


GROUP_FILE = {}
mass_roof = {'equipment': 0.0, 'piping (filled)': 0.0, 'insulation': 0.0, 'dunnage + mounts': 0.0, 'supports + walkways': 0.0}
mass_hall = 0.0
for tag, it in m.items.items():
    model = 'cad_out/plant/items/%s.step' % tag.replace('/', '_')
    row(tag, it['description'], it['qty'], it['make_or_buy'], it['material_or_spec'], it['size_or_rating'],
        it['supplier_candidates'], it['mass_kg'], model, it['notes'])
    if tag == 'EP-1':
        continue
    if it['group'] == 'hall':
        mass_hall += it['mass_kg']
    else:
        mass_roof['equipment'] += it['mass_kg']

# inline components
COMP_DESC = {
    'ball': ('ball valve, full bore, PN16, lever', 'Genebre (ES), Giacomini (IT), KSB (DE); domestic'),
    'motorball': ('motorised ball valve on/off with end switches, 24 VAC', 'Belimo (CH), Siemens (DE)'),
    'butterfly': ('butterfly valve, lug type, EPDM liner, lever/gear, PN16', 'Genebre (ES), Zetkama (PL), KSB (DE)'),
    'mbutterfly': ('motorised butterfly valve on/off with end switches (staging)', 'Belimo (CH), Siemens (DE), Genebre (ES)'),
    'check': ('silent check valve, wafer, PN16', 'Genebre (ES), Zetkama (PL), Socla (FR)'),
    'ystrainer': ('Y-strainer 1 mm (20 mesh), PN16, with drain plug', 'Genebre (ES), Zetkama (PL); domestic'),
    'basket': ('basket strainer DN100 with dp gauge', 'Zetkama (PL), Genebre (ES); domestic'),
    'magflow': ('electromagnetic flow meter, 4-20 mA + Modbus', 'Endress+Hauser (CH/DE), Krohne (DE), Siemens SITRANS FM (DE)'),
    'heatmeter': ('ultrasonic thermal energy meter with pair of PT500 sensors, M-Bus', 'Kamstrup MULTICAL 603 (DK), Siemens UH50 (DE), Danfoss Sonometer (DK)'),
    'picv': ('pressure-independent control valve, 0-10 V actuator with feedback', 'Belimo EPIV/PIQCV (CH), Danfoss AB-QM + NovoCon (DK), IMI TA (CH)'),
    'pump_inline': ('in-line wet-rotor/dry-runner circulator, ECM, Modbus', 'Grundfos MAGNA3 / TPE3 (DK), Wilo Stratos MAXO (DE), DAB (IT)'),
    'pump_twin': ('twin in-line circulator ECM, duty/standby, Modbus', 'Grundfos MAGNA3 D (DK), Wilo Stratos MAXO-D (DE)'),
    'separator': ('microbubble + dirt + magnetic separator', 'Spirotech SpiroCombi (NL), Caleffi DISCALDIRT (IT), Flamco (NL)'),
    'threeway': ('3-way modulating valve (tower bypass), 0-10 V', 'Belimo (CH), Siemens (DE)'),
    'meter_water': ('water meter with pulse output', 'Zenner (DE), Diehl Metering (DE), B Meters (IT)'),
    'flex': ('flexible connector (stainless braided / gas-approved)', 'Witzenmann (DE), domestic'),
    'bellows': ('exhaust expansion joint DN250, 316L multi-ply, 650 C', 'Witzenmann (DE), Kompaflex (CH); domestic'),
    'psv': ('discharge pressure switch (FK-5-1-12 released)', 'per listed fire system'),
}
agg = {}
for r in m.routes.values():
    for c in r.comps:
        ct, dn = c['type'], c['dn']
        mat = 'PE/steel spool' if r.mat == 'PE100' else r.mat
        if c['tag']:
            d, sup = COMP_DESC[ct]
            mass = {'pump_inline': 6 + dn * 0.25, 'pump_twin': 14 + dn * 0.45, 'magflow': 4 + dn * 0.12,
                    'basket': 45, 'separator': 6 + dn * 0.15, 'threeway': 6 + dn * 0.2}.get(ct, 1.0 + dn * 0.05)
            row(c['tag'], '%s, DN%d, on %s (%s)' % (d, dn, r.line, r.service), 1, 'buy', d, 'DN%d' % dn, sup, round(mass, 1),
                'cad_out/plant/piping/%s.step' % r.name, 'inline on route %s' % r.name)
            mass_hall_flag = r.hall
            if mass_hall_flag:
                mass_hall += mass
            else:
                mass_roof['equipment'] += mass
        else:
            key = (ct, dn, r.hall)
            agg.setdefault(key, []).append(r.name)
for (ct, dn, hall_), names in sorted(agg.items()):
    d, sup = COMP_DESC[ct]
    q = len(names)
    mass = (1.0 + dn * 0.06) * q
    row('V-%s-DN%d%s' % (ct.upper()[:4], dn, '-H' if hall_ else ''), '%s, DN%d (untagged isolation/strainer items)' % (d, dn), q, 'buy', d,
        'DN%d PN16' % dn, sup, round(mass, 1), 'cad_out/plant/piping/', 'routes: ' + ', '.join(sorted(set(names))))
    if hall_:
        mass_hall += mass
    else:
        mass_roof['equipment'] += mass

# pipes, elbows, tees, flanges, reducers, insulation
pipe_len, elb, tees, ins_len, ins_kg, flanges, ht_len = {}, {}, {}, {}, {}, {}, 0.0
for r in m.routes.values():
    k = (r.mat, r.dn)
    pipe_len[k] = pipe_len.get(k, 0.0) + r.length
    kg = (L.MATERIALS[r.mat][2].get(r.dn, 0) + water_kg_m(r)) * r.length
    ik = ins_kg_m(r) * r.length
    if r.hall:
        mass_hall += kg + ik
    else:
        mass_roof['piping (filled)'] += kg
        mass_roof['insulation'] += ik
    for a in r.elbows:
        ac = 90 if abs(a - 90) <= 2 else (45 if abs(a - 45) <= 2 else a)
        elb[(r.mat, r.dn, ac)] = elb.get((r.mat, r.dn, ac), 0) + 1
    for par in (r.parent, r.end_parent):
        if par and par in m.routes:
            p = m.routes[par]
            kt = (p.mat, p.dn, r.dn)
            tees[kt] = tees.get(kt, 0) + 1
    if r.ins:
        ki = (r.ins, r.dn)
        ins_len[ki] = ins_len.get(ki, 0.0) + r.length
        ins_kg[ki] = ins_kg.get(ki, 0.0) + ik
    if r.heat_trace:
        ht_len += r.length
    for c in r.comps:
        if c['dn'] >= 32 and c['type'] not in ('flex', 'bellows', 'psv'):
            kf = (c['dn'], 'PE stub-end + backing ring' if r.mat == 'PE100' else 'weld-neck PN16')
            flanges[kf] = flanges.get(kf, 0) + 2
    # equipment end connections
    for p_ in (r.pts[0], r.pts[-1]):
        for (tg, nm), n in m.nozzles.items():
            if math.dist(n['p'], p_) < 0.002 and r.dn >= 32 and r.mat not in ('DUCT',):
                kf = (r.dn, 'PE stub-end + backing ring' if r.mat == 'PE100' else 'weld-neck PN16')
                flanges[kf] = flanges.get(kf, 0) + 1
                if n['dn'] != r.dn:
                    kt = ('reducer', r.mat, r.dn, n['dn'])
                    tees[kt] = tees.get(kt, 0) + 1
for (mat, dn), Lm in sorted(pipe_len.items()):
    d = L.MATERIALS[mat][0]
    row('PIPE-%s-DN%d' % (mat, dn), 'pipe %s DN%d (length incl. 5 %% cut allowance)' % (mat, dn), round(Lm * 1.05, 1), 'buy', d,
        'DN%d / OD %.1f mm' % (dn, L.MATERIALS[mat][1][dn]), {'CS40': 'domestic mills (Safa, Isfahan) / EU', 'PE100': 'domestic PE pipe makers',
                                                            'SS304': 'Geberit Mapress (CH/DE), Viega Sanpress (DE)', 'SS316F': 'per listed fire system',
                                                            'PPR': 'domestic PP-R makers; Aquatherm (DE)', 'PVC': 'domestic', 'GAS': 'domestic mills',
                                                            'SS316D': 'domestic stainless fabricators', 'DUCT': 'Jeremias, Schiedel (DE); domestic'}[mat],
        round(L.MATERIALS[mat][2].get(dn, 0) * Lm * 1.05, 1), 'cad_out/plant/piping/', 'unit: m')
for (mat, dn, a), q in sorted(elb.items(), key=lambda x: (x[0][0], x[0][1], str(x[0][2]))):
    row('ELB-%s-DN%d-%s' % (mat, dn, a), 'elbow %s deg, %s DN%d (long radius 1.5D / PE moulded)' % (a, mat, dn), q, 'buy',
        L.MATERIALS[mat][0], 'DN%d' % dn, 'as pipe', round(q * 0.3 * dn / 25, 1), 'cad_out/plant/piping/', '')
for k, q in sorted(tees.items(), key=lambda x: str(x[0])):
    if k[0] == 'reducer':
        _, mat, dn, ndn = k
        row('RED-%s-DN%dx%d' % (mat, dn, ndn), 'concentric reducer %s DN%d x DN%d at equipment nozzle' % (mat, dn, ndn), q, 'buy',
            L.MATERIALS[mat][0], 'DN%dxDN%d' % (dn, ndn), 'as pipe', round(q * 0.4, 1), 'cad_out/plant/piping/', 'final nozzle sizes per datasheets')
    else:
        mat, dn, bdn = k
        row('TEE-%s-DN%dx%d' % (mat, dn, bdn), '%s tee %s DN%d x DN%d' % ('equal' if dn == bdn else 'reducing', mat, dn, bdn), q, 'buy',
            L.MATERIALS[mat][0], 'DN%dxDN%d' % (dn, bdn), 'as pipe', round(q * 0.5 * dn / 25, 1), 'cad_out/plant/piping/', '')
for (dn, kind), q in sorted(flanges.items()):
    row('FLG-DN%d-%s' % (dn, kind.split()[0]), 'flange set DN%d %s + gasket + bolt set (A4 or galv.)' % (dn, kind), q, 'buy',
        'EN 1092-1 PN16, EPDM/graphite gasket', 'DN%d' % dn, 'domestic / EU', round(q * 0.12 * dn / 10, 1), 'cad_out/plant/piping/', '')
for (ins, dn), Lm in sorted(ins_len.items()):
    row('INS-%s-DN%d' % (ins, dn), 'pipe insulation %s on DN%d' % (L.INSULATION[ins][0], dn), round(Lm * 1.08, 1), 'buy',
        L.INSULATION[ins][0], 'DN%d, %d mm' % (dn, L.INSULATION[ins][1]),
        'Rockwool, Isover (EU) / Armacell, K-Flex (EU); domestic equivalents', round(ins_kg[(ins, dn)] * 1.08, 1), 'cad_out/plant/piping/',
        'unit: m incl. 8 % for fittings')
row('HT-1', 'self-regulating heat tracing 20 W/m + controller + RCD 30 mA (make-up, pad/fill water)', round(ht_len * 1.15, 1), 'buy',
    'self-regulating cable, IP67 kit, ambient thermostat 3 C', '20 W/m', 'Eltherm (DE), Heat Trace Ltd (UK); Chinese', round(ht_len * 0.15, 1),
    'cad_out/plant/piping/', 'unit: m')
for k, q in sorted(sup_count.items()):
    row('SUP-%d' % (len(rows)), k, q, 'buy', 'recycled-rubber base / galvanised post, U-bolt, EPDM liner (CHW: insulated support block)',
        '-', 'Big Foot Systems (UK), Kee Safety (UK), Sikla (DE); domestic', round(q * (4 if 'h 0.3' in k else 8)), 'cad_out/plant/structure.step', 'auto-placed')
    if 'hall' in k:
        mass_hall += q * 1.0
    else:
        mass_roof['supports + walkways'] += q * (4 if 'h 0.3' in k else 8)
dun_len = sum(x[1] for x in m.dunnage_log)
dun_pads = sum(x[2] for x in m.dunnage_log)
row('DUN-HEA140', 'roof dunnage beams HEA140 under all equipment, hot-dip galvanised, on EPDM bearing pads; structural engineer '
    'to confirm bearing points over RC beams', round(dun_len, 1), 'make', 'S275 HEA140, HDG', '24.7 kg/m',
    'domestic steel; galvaniser', round(dun_len * 24.7), 'cad_out/plant/structure.step', 'unit: m')
row('DUN-PAD', 'EPDM bearing pad 200 x 200 x 22 mm under dunnage', dun_pads, 'buy', 'EPDM 60 ShA', '200x200x22', 'domestic', round(dun_pads * 1.2, 1),
    'cad_out/plant/structure.step', '')
mass_roof['dunnage + mounts'] += dun_len * 24.7 + dun_pads * 1.2
for owner, kind, n in m.mount_log:
    pass
n_spr = sum(n for _, k, n in m.mount_log if k == 'spring')
n_pad = sum(n for _, k, n in m.mount_log if k == 'pad')
row('ISO-SPR', 'spring isolator, 25 mm static deflection, levelling bolt, seismic restraint (PS-1, PS-2, CT-1 ring)', n_spr + 6, 'buy',
    'housed open spring + neoprene cup', '150-400 kg each', 'Getzner (AT), Christie & Grey (UK); domestic', (n_spr + 6) * 3,
    'cad_out/plant/items/', '+6 under CT-1 base ring')
row('ISO-PAD', 'neoprene/ribbed isolation pad under equipment feet', n_pad, 'buy', 'neoprene 2-layer ribbed', '160x160x25', 'Getzner (AT); domestic',
    n_pad * 0.8, 'cad_out/plant/items/', '')
mass_roof['dunnage + mounts'] += (n_spr + 6) * 3 + n_pad * 0.8
row('WALK', 'GRP walkway grating tiles on adjustable roof pads (anti-slip, yellow)', round(walk_area, 1), 'buy', 'GRP 38 mm moulded grating',
    'm2', 'Fibrelite (UK), Kee Safety (UK); domestic GRP', round(walk_area * 18), 'cad_out/plant/structure.step', 'unit: m2')
mass_roof['supports + walkways'] += walk_area * 18
for r_ in m.bom_extra:
    rows.append(r_)
    mass_roof['supports + walkways'] += r_['mass_kg']

# instruments from io_list.csv (field devices)
io = os.path.join(ROOT, 'docs', 'hvac', 'io_list.csv')
INSTR = ('TE', 'TT', 'PT', 'PDT', 'DPT', 'FT', 'FS', 'FSL', 'LT', 'LSL', 'LSH', 'LSLL', 'AT', 'AIT', 'MT', 'VS', 'LD', 'ZT', 'PSH', 'TSHH', 'TSH')
already = {r_['tag'] for r_ in rows} | {'LD-E'}     # LD-E: listed once with the indoor items (cable + module)
ninstr = 0
with open(io) as f:
    rd = csv.reader(f)
    head = next(rd)
    for rr in rd:
        tag = rr[0]
        pre = tag.split('-')[0]
        if pre in INSTR and tag not in already and not tag.endswith(('-FLT', '-RUN', '-BUS', '-CMD')):
            kind = rr[2] if len(rr) > 2 else ''
            spec = {'AI-RTD': 'PT1000 class A, 316 thermowell, 3-wire', 'AI-TC': 'type K, Inconel sheath', 'AI-mA': '4-20 mA transmitter',
                    'DI': 'switch, dry contact'}.get(kind, kind)
            row(tag, 'instrument: %s' % rr[1], 1, 'buy', spec, rr[3] if len(rr) > 3 else '',
                'WIKA, JUMO, Endress+Hauser (DE/CH), Huba (CH), Vaisala (FI), Kobold (DE)', 0.5,
                'not modelled (installed on line/equipment; < 1 kg)', 'location: %s; board %s (io_list.csv)' % (rr[4] if len(rr) > 4 else '', rr[5] if len(rr) > 5 else ''))
            ninstr += 1
mass_roof['equipment'] += ninstr * 0.5

# indoor items (own local-frame models)
INDOOR = [
    ('SOFT-1', 'twin alternating water softener, meter-initiated, 2 x 25 L resin, brine tank 100 L (LSL-403), 50 um prefilter; '
               'hardness < 100 ppm (pref. < 17), regeneration waste to sewer', 'buy', 'FRP vessels, Runxin/Canature valve', '0.5 m3/h',
     'BWT (AT); Runxin, Canature (CN); resin Lanxess Lewatit (DE); domestic assemblers', 120, 'water'),
    ('RO-1', 'RO unit 400 L/h permeate, ULP membranes, VFD pump, 5 um cartridge, antiscalant dosing (only if chiller maker '
             'requires <= 800 uS/cm)', 'buy', 'skid, SS/PVC', '400 L/h, ~0.7 kWh/m3', 'Toray (JP), LG Chem (KR), Vontron (CN) membranes; domestic skid', 90, 'water'),
    ('TK-401', 'blend / make-up tank 500 L with LT-401, AIT-402, TV-401 blend valve', 'buy', 'PE tank', '500 L', 'domestic', 540, 'water'),
    ('P-9', 'make-up booster pump with pressure vessel, ECM/VFD (to roof)', 'buy', 'multistage', '0.5 m3/h @ 25 m', 'Grundfos SCALA2/CMBE (DK), Wilo (DE), DAB (IT)', 25, 'water'),
    ('TK-DHW', 'DHW storage tank 500 L, 316L or enamelled, T&P valve, potable expansion vessel, TMV 50 C', 'buy', 'EN 12897', '500 L',
     'domestic tank makers; Caleffi TMV (IT)', 650, 'dhw'),
    ('HX-2', 'double-wall DHW charging PHE 30 kW, 90/70 -> 50/62 C', 'buy', 'SS316 double wall', '30 kW', 'Alfa Laval (SE), SWEP (SE), Kelvion (DE)', 40, 'dhw'),
    ('P-7', 'DHW charging / circulation pump, bronze or stainless', 'buy', 'ECM', '1 m3/h', 'Grundfos COMFORT/UP-B (DK), Wilo Star-Z (DE)', 5, 'dhw'),
    ('FCU-E', 'electrical-room wall fan coil 400 CFM, EC, drain pan + condensate pump, 2-way valve; NOT above electrical equipment',
     'buy', 'hydronic', '3.9 kW nominal', 'as FCU-1..4', 25, 'er'),
    ('AC-E', 'standby DX split 12 kBTU/h, T3 compressor (52 C), dry-contact enable', 'buy', 'inverter split', '3.5 kW', 'Gree, Midea (CN), LG, Samsung (KR)', 45, 'er'),
    ('EF-E', 'electrical-room / battery exhaust fan with XV-497 spring-close damper + ZSC-497', 'buy', 'EC fan + damper', '300 m3/h',
     'ebm-papst (DE), Systemair (SE); Belimo damper', 12, 'er'),
    ('LD-E', 'leak-detection cable under FCU-E and pipes + module', 'buy', 'sensing cable', '10 m', 'TTK FG-SYS (FR); Chinese', 2, 'er'),
    ('FS-2', 'FZ2 cylinder ~25 kg FK-5-1-12 (40 L class) with solenoid + manual actuator, PSL-890B, LLI, lock-off ZSC-899B, wall bracket',
     'buy', 'listed system', '24.7 kg agent for 31.5 m3 (ASSUMED room)', 'Siemens Sinorix 1230, Minimax MX 1230 (DE)', 60, 'fire'),
    ('FZ2-PIPE', 'FZ2 discharge piping DN25 Sch80 316 (~6 m) + 1 x 360 deg nozzle at ceiling centre + pressure relief vent', 'buy',
     'listed fittings', 'DN25', 'per listed system', 25, 'fire'),
    ('FX-1..3', 'portable extinguishers: roof 1 x CO2 5 kg + 1 x ABC 6 kg; electrical room 1 x CO2 5 kg', 'buy', 'EN 3', '3 pcs', 'domestic certified', 40, 'fire'),
    ('CHEM', 'water-treatment chemicals (phosphonate/polymer/TTA inhibitor, BCDMH or NaOCl+NaBr, isothiazolinone/DBNPA, molybdate '
             'for closed loops, MgO granulate) - first fill + 3 months', 'buy', 'service contract', 'lot', 'Kurita (JP), BWA (UK); domestic', 200, 'water'),
    ('GLY', 'propylene glycol 40 % premix for engine loop (~60 L incl. perimeter piping)', 'buy', 'inhibited MPG', '60 L', 'Clariant Antifrogen (DE); domestic', 62, 'engine'),
]
for tag, d, mb, spec, size, sup, kg, grp in INDOOR:
    fn = {'water': 'indoor_water_dhw.step', 'dhw': 'indoor_water_dhw.step', 'er': 'indoor_electrical_room.step',
          'fire': 'indoor_electrical_room.step', 'engine': '-'}[grp]
    row(tag, d, 1, mb, spec, size, sup, kg, ('cad_out/plant/' + fn) if fn != '-' else 'not modelled (fluid)',
        'indoor, local frame; position by site / electrical session' if fn != '-' else '')

with open(BOM, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating',
                                      'supplier_candidates', 'mass_kg', 'model_file', 'notes'])
    w.writeheader()
    for r_ in rows:
        w.writerow(r_)
tot = sum(mass_roof.values())
print('BOM: %d rows -> %s' % (len(rows), BOM))
print('roof operating mass from model: ' + ', '.join('%s %.0f' % kv for kv in mass_roof.items()) + ' -> total %.0f kg (+ EP-1 450 placeholder)' % tot)
print('hall (below roof) installed mass: %.0f kg' % mass_hall)

# ------------------------------------------------------------------------------------------------ interfaces json
ifc = dict(frame='ROOF (docs/06_master_design.md section 1): origin SW roof corner on finished roof, x east, y north, z up, metres',
           generated_by='cad/plant/build_plant.py', configuration='SC10+SC5 pair, light items (TK-1 300 L, LLH-1 hydraulic separator, PE100 CW)',
           ep1_box=dict(x=[1.30, 2.70], y=[7.60, 8.50], z=[0.0, 1.30]),
           interfaces=m.interfaces,
           nozzles=[dict(item=t, name=n, position_roof_m=list(v['p']), direction=list(v['d']), size='DN%d' % v['dn'], medium=v['medium'])
                    for (t, n), v in sorted(m.nozzles.items())],
           roof_mass_kg=round(tot), checks=dict(clashes=len(clashes), service_zones=len(zones), walkways=len(walks), tower_ring=len(ring)))
with open(os.path.join(OUT, 'plant_interfaces.json'), 'w') as f:
    json.dump(ifc, f, indent=1)

# ------------------------------------------------------------------------------------------------ STEP export
if not FAST:
    T2 = time.time()
    doc = App.newDocument('GR180_plant')
    objs = []
    by_owner = {}
    for p in m.parts:
        by_owner.setdefault((p.group if p.kind in ('pipe', 'ins', 'comp') else p.owner, p.kind == 'ref'), []).append(p)
    for (owner, is_ref), ps in sorted(by_owner.items()):
        comp = Part.makeCompound([p.shape for p in ps])
        o = doc.addObject('Part::Feature', owner.replace('/', '_').replace('.', '_').replace(' ', '_')[:40] or 'x')
        o.Label = owner
        o.Shape = comp
        if not is_ref:
            objs.append(o)
    Import.export(objs, os.path.join(OUT, 'plant_assembly.step'))
    # per-equipment item files
    eq_owners = sorted({p.owner for p in m.parts if p.kind == 'equip'})
    for t in eq_owners:
        Part.makeCompound([p.shape for p in m.parts if p.owner == t and p.kind == 'equip']).exportStep(
            os.path.join(OUT, 'items', '%s.step' % t.replace('/', '_')))
    for rn in m.routes:
        sh = [p.shape for p in m.parts if p.owner == rn]
        if sh:
            Part.makeCompound(sh).exportStep(os.path.join(OUT, 'piping', '%s.step' % rn.replace('/', '_')))
    Part.makeCompound([p.shape for p in m.parts if p.kind in ('struct', 'walk', 'support')]).exportStep(os.path.join(OUT, 'structure.step'))
    Part.makeCompound([p.shape for p in m.parts if p.kind == 'ref']).exportStep(os.path.join(OUT, 'reference_building.step'))
    # indoor local-frame models (envelopes)
    wd = [L.box(0, 0, 0, 0.9, 0.5, 1.6), L.box(1.1, 0, 0, 1.2, 0.6, 1.5), L.cyl(3.0, 0.45, 0, 0.9, 1.0), L.box(3.7, 0, 0, 0.6, 0.4, 0.8),
          L.cyl(5.0, 0.4, 0, 0.75, 1.8), L.box(5.6, 0, 0.6, 0.12, 0.3, 0.6), L.box(5.9, 0, 0.3, 0.25, 0.2, 0.3)]
    Part.makeCompound(wd).exportStep(os.path.join(OUT, 'indoor_water_dhw.step'))
    er = [L.box(0, 1.0, 2.2, 0.9, 0.25, 0.5), L.box(3.0, 1.2, 2.2, 0.9, 0.3, 0.3), L.box(2.0, 0.0, 2.4, 0.4, 0.3, 0.4),
          L.cyl(0.25, 2.6, 0.0, 0.27, 1.20), L.cylp((1.75, 1.5, 2.9), 0.0337, (0, 0, -1), 0.10)]
    Part.makeCompound(er).exportStep(os.path.join(OUT, 'indoor_electrical_room.step'))
    try:
        doc.saveAs(os.path.join(OUT, 'plant_assembly.FCStd'))
    except Exception as e:
        print('FCStd save failed', e)
    print('STEP export done (%.1f s)' % (time.time() - T2))

    T3 = time.time()
    n1 = L.render(m, os.path.join(OUT, 'render_iso_SE.png'), elev=30, azim=-58, title='GR180-CCHP roof plant (ROOF frame), view from SE',
                  zlim=(-3.0, 4.5), kinds=('equip', 'pipe', 'ins', 'comp', 'struct', 'walk', 'support'))
    L.render(m, os.path.join(OUT, 'render_iso_NW.png'), elev=30, azim=125, title='GR180-CCHP roof plant, view from NW',
             zlim=(-3.0, 4.5), kinds=('equip', 'pipe', 'ins', 'comp', 'struct', 'walk', 'support'))
    L.render(m, os.path.join(OUT, 'render_top.png'), elev=90, azim=-90, title='GR180-CCHP roof plant - plan (z > 0)',
             zlim=(0, 4.5), kinds=('equip', 'pipe', 'ins', 'comp', 'struct', 'walk', 'support'), ortho_top=True,
             owners=lambda p: p.shape.BoundBox.ZMax > 0)
    L.render(m, os.path.join(OUT, 'render_hall.png'), elev=25, azim=-60, title='hall below the roof: FCU-1..4 and CHW distribution',
             zlim=(-2.9, 0.6), kinds=('equip', 'pipe', 'ins', 'comp', 'support'), owners=lambda p: p.shape.BoundBox.ZMin < -0.05)
    print('renders done (%d facets, %.1f s)' % (n1, time.time() - T3))
print('total %.1f s' % (time.time() - T0))
