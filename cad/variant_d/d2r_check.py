# GR180 version D2 - interference check of the D2R parts (ROTOR / TURBINE / GENERATOR) against each other, the kept v13A core
# parts and the generator pod shell (d_concept D-101/D-102), plus the D2R interfaces json.
# Overlap = common volume > TOL_MM3 (line-on-line fits and touching faces give ~0 and count as contact faces).
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2r_check.py
#   -> cad_out/variant_d/D2/d2r_check.json, cad_out/variant_d/D2/d2r_interfaces.json (+ copy sim/variant_d/d2r_interfaces.json)
import FreeCAD as App, Part, os, sys, json, glob, math, itertools
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2r_layout as L
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
D2 = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2')
CORE = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
POD = os.path.join(ROOT, 'cad_out', 'variant_d')
TOL_MM3 = 0.5
TOUCH_MM = 0.05

# v13A parts replaced / removed in D2 (see docs/variant_d/03): shaft, nose cone, axial turbine + nut + NGV + jet nozzle,
# 608 bearings + O-ring + wave spring, tunnel (new R-120), air starter, RPM magnet + slug (were in the nose cone), EGT probe (now TIT boss)
REPLACED = {'Shaft', 'NoseCone', 'Turbine', 'TurbineNut', 'NGV', 'Exhaust', 'FrontBearing_608_hybrid_8x22x7',
            'RearBearing_608_hybrid_8x22x7', 'FrontBearing_Oring', 'WaveSpring_22x16_free3_0_inst2_8', 'ShaftTunnel',
            'Starter', 'RPM_Magnet', 'Balance_Slug', 'EGT_Probe', 'Compressor'}   # Compressor -> R-100 (bored d10)
POD_PARTS = ['D-101_Generator_Housing_Jacket', 'D-102_Generator_Front_Cap', 'D-150_Pod_Struts_x3']

shapes = {}
for grp in ('ROTOR', 'TURBINE', 'GENERATOR'):
    for f in sorted(glob.glob(os.path.join(D2, grp, '*.step'))):
        shapes['D2R/' + os.path.basename(f)[:-5]] = Part.read(f)
for f in sorted(glob.glob(os.path.join(CORE, '*.step'))):
    n = os.path.basename(f)[:-5]
    if n in REPLACED:
        continue
    sh = Part.read(f)
    if n == 'SupplyLines':      # drop the two v13A 608 lube lines (front: ends x 14.4 below the tunnel; rear: ends x 91.7) -> D2R oil system
        keep = [so for so in sh.Solids if not (abs(so.BoundBox.XMax - 91.73) < 0.1 or (abs(so.BoundBox.XMax - 14.4) < 0.1 and so.BoundBox.ZMax < -13))]
        res_drop = len(sh.Solids) - len(keep)
        sh = Part.makeCompound(keep)
        print('SupplyLines: dropped %d v13A bearing lube lines' % res_drop)
    shapes['v13A/' + n] = sh
for n in POD_PARTS:
    f = os.path.join(POD, n + '.step')
    if os.path.exists(f):
        shapes['pod/' + n] = Part.read(f)
print('parts:', len(shapes), ' D2R:', sum(k.startswith('D2R') for k in shapes))

res = dict(tol_mm3=TOL_MM3, overlaps=[], contacts=[], checked_pairs=0)
names = sorted(shapes)
for a, b in itertools.combinations(names, 2):
    if not (a.startswith('D2R') or b.startswith('D2R')):
        continue                                            # core-vs-core and pod-vs-core are not ours
    A, B = shapes[a], shapes[b]
    ba, bb = A.BoundBox, B.BoundBox
    if not ba.intersect(bb):
        continue
    res['checked_pairs'] += 1
    try:
        v = A.common(B).Volume
    except Exception as e:
        v = -1
    if v > TOL_MM3:
        res['overlaps'].append(dict(a=a, b=b, mm3=round(v, 2)))
        print('OVERLAP %-48s %-48s %.2f mm3' % (a, b, v))
    else:
        try:
            d = A.distToShape(B)[0]
        except Exception:
            d = 99
        if d < TOUCH_MM:
            res['contacts'].append(dict(a=a, b=b, gap_mm=round(d, 3)))
print('checked pairs %d, overlaps %d, contact faces %d' % (res['checked_pairs'], len(res['overlaps']), len(res['contacts'])))
json.dump(res, open(os.path.join(D2, 'd2r_check.json'), 'w'), indent=1)

# ------------------------------------------------------------------ interfaces (ENG mm; ROOF = 1.880 + x/1000, 7.850 + y/1000, 0.600 + z/1000)
def roof(x, y=0.0, z=0.0):
    return [round(1.880 + x / 1000, 4), round(7.850 + y / 1000, 4), round(0.600 + z / 1000, 4)]

I = dict(
    title='GR180 D2R rotor / turbine / generator interfaces', frame='ENG mm (x engine axis downstream, z up); ROOF m via X = 1.880 + x/1000 (engine-frame EP-1 2026-10-23)',
    exhaust_start=dict(x=L.EXHAUST_START['x'], ID_mm=L.EXHAUST_START['ID'], vband_OD_mm=L.EXHAUST_START['flange_OD'],
                       joint=L.EXHAUST_START['joint'], exducer_exit=dict(x=169.0, ID_mm=70.7),
                       face='T-121 shroud rear face; the shroud already carries the first diffuser cone 70.7 -> 74.8 (4.3 deg half angle) from x 172',
                       gas='~600 C, c ~270 m/s at x 199, no swirl at design', roof=roof(L.EXHAUST_START['x']),
                       mating='EXHAUST agent EX-111 V-band inlet ring (x 199-207, ID 74.8, OD 100) - unchanged'),
    casing_rear_flange=dict(x=L.CASING_FACE_X, r=[39.0, 48.0], bolts='4 x M5 PCD 88 at 45/135/225/315 deg (longer bolts, M5x20 A286)',
                            stack='casing flange | T-116 support flange (x 116-118) | T-120 housing front wall (x 118-121)'),
    turbine_housing_support=dict(x_collar=[128.0, 146.0], shell_OD=2 * L.HOUSING['shell_ro'],
                                 note='plenum shell OD 168 kept from RT2 so the FRAME collar FR-130 (centre-line ears, sliding) clamps it at x 128-146; '
                                      'the 0.3 mm casing sheet must not carry the hot end'),
    tit_probe=dict(x=L.HOUSING['tit_x'], z_top=L.HOUSING['shell_ro'] + 7.0, thread='M8x1 boss, K-type 3 mm sheathed, tip in the plenum at r ~78'),
    generator_pod=dict(bore_r=L.POD['bore_r'], internals_x=[-281.0, -123.0], rear_plate_contact_x=-123.0,
                       terminal_box=dict(x=list(L.TBOX['x']), y=list(L.TBOX['y']), z=list(L.TBOX['z']), cable='3 x 10 mm2 + PE, M32 gland, rear face'),
                       glycol_ports=dict(x=list(L.GLYCOL_PORTS), size='G1/4, top (z +55), 1.5-2 L/min 50/50 glycol, 35-40 C in'),
                       quill_guard=dict(x=[L.QUILL_GUARD['x0'], L.QUILL_GUARD['x1']], OD=2 * L.QUILL_GUARD['ro'])),
    oil=dict(core_front_jet='drilled in tunnel flange (top), feed from the outside through a diffuser vane passage (v13A supply-line route)',
             core_rear_feed='tube d4x0.5 along the tunnel top (r 14.5) in the compressor-air annulus',
             core_scavenge='front: tunnel flange bottom port; rear: tube d6x0.5 along the tunnel bottom; both to the scavenge pump',
             generator='jets from the top of each end shield, drains to the pod bottom (x -266 / -136, z -45), G1/8 scavenge ports',
             spec='ISO VG 32 synthetic turbine oil, 2.5 barg, ~0.3 L/min per bearing (4 bearings ~1.2 L/min), 10 um filter'),
    buffer_air=dict(core_front='compressor back-face air through the 3-tooth front labyrinth into the bearing chamber (vented)',
                    core_rear='compressor-delivery air from the inner combustor annulus through 6 x d2 holes in T-116 to the rear cavity; '
                              'leaks forward through the 4-tooth labyrinth into the bearing chamber and rearward past the wheel back face',
                    breather='bearing-chamber vent to the oil tank / mist separator'),
    rotor_axial=dict(core_locating_bearing_x=L.X_BF, quill_axial_float_mm=L.QUILL['float_mm'], quill_socket_x=list(L.QUILL['socket']), shaft_hex_x=list(L.QUILL['hex'])),
)
json.dump(I, open(os.path.join(D2, 'd2r_interfaces.json'), 'w'), indent=1)
json.dump(I, open(os.path.join(ROOT, 'sim', 'variant_d', 'd2r_interfaces.json'), 'w'), indent=1)
print('-> d2r_check.json, d2r_interfaces.json')
