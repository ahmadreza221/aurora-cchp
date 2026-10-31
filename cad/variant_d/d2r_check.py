# GR180 version D2 - interference check of the D2R parts (ROTOR / TURBINE / GENERATOR) against each other, the kept v13A core
# parts and the generator pod shell (d_concept D-101/D-102), plus the D2R interfaces json.
# Overlap = common volume > TOL_MM3 (line-on-line fits and touching faces give ~0 and count as contact faces).
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2r_check.py
#   -> cad_out/variant_d/D2/d2r_check.json, cad_out/variant_d/D2/d2r_interfaces.json (+ copy sim/variant_d/d2r_interfaces.json)
import FreeCAD as App, Part, os, sys, json, glob, math, itertools
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2r_layout as L
import d2g_layout as GL
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
POD_PARTS = ['D-101_Generator_Housing_Jacket', 'D-102_Generator_Front_Cap']      # D-150 struts superseded by INT-115 (intake agent)
PARTNER = ('INTAKE', 'EXHAUST', 'FRAME')                                            # intake/exhaust/frame agent parts (d2_*.py), if built

shapes = {}
for grp in ('ROTOR', 'TURBINE', 'GENERATOR', 'POD'):      # POD = G-200 housing + G-202 front cover (d2g rev pod shell)
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
if not glob.glob(os.path.join(D2, 'POD', 'G-2*.step')):  # concept pod shell only if the d2g housing is not built
    for n in POD_PARTS:
        f = os.path.join(POD, n + '.step')
        if os.path.exists(f):
            shapes['pod/' + n] = Part.read(f)
AUX_REPORT = os.environ.get('D2R_CHECK_AUX') == '1'      # AUX parts: report-only (paused agent; ports moved in the d2g rev)
if AUX_REPORT:
    for f in sorted(glob.glob(os.path.join(D2, 'AUX', '*.step'))):
        shapes['AUX/' + os.path.basename(f)[:-5]] = Part.read(f)
for grp in PARTNER:
    for f in sorted(glob.glob(os.path.join(D2, grp, '*.step'))):
        shapes['D2/' + os.path.basename(f)[:-5]] = Part.read(f)
print('parts:', len(shapes), ' D2R:', sum(k.startswith('D2R') for k in shapes), ' partner:', sum(k.startswith('D2/') for k in shapes))

res = dict(tol_mm3=TOL_MM3, overlaps=[], contacts=[], checked_pairs=0)
names = sorted(shapes)
for a, b in itertools.combinations(names, 2):
    if not (a.startswith('D2R') or b.startswith('D2R')):
        continue                                            # core-vs-core and pod-vs-core are not ours
    if AUX_REPORT and not (a.startswith('AUX') or b.startswith('AUX')):
        continue
    if AUX_REPORT and not ('GENERATOR' in a or 'GENERATOR' in b or '/G-2' in a or '/G-2' in b or '/G-1' in a or '/G-1' in b):
        continue
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
json.dump(res, open(os.path.join(D2, 'd2r_check_aux.json' if AUX_REPORT else 'd2r_check.json'), 'w'), indent=1)
if AUX_REPORT:
    sys.exit(0)

# ------------------------------------------------------------------ interfaces (ENG mm; ROOF = 1.880 + x/1000, 7.850 + y/1000, 0.600 + z/1000)
def roof(x, y=0.0, z=0.0):
    return [round(1.880 + x / 1000, 4), round(7.850 + y / 1000, 4), round(0.600 + z / 1000, 4)]

try:
    GJ = json.load(open(os.path.join(D2, 'GENERATOR', 'd2r_generator_parts.json')))
except Exception:
    GJ = {}
I = dict(
    title='GR180 D2R rotor / turbine / generator interfaces', frame='ENG mm (x engine axis downstream, z up); ROOF m via X = 1.880 + x/1000 (engine-frame EP-1 2026-10-23)',
    exhaust_start=dict(x=L.EXHAUST_START['x'], ID_mm=L.EXHAUST_START['ID'], flange_OD_mm=L.EXHAUST_START['flange_OD'],
                       bolts=L.EXHAUST_START['bolts'], face='exducer shroud T-121 rear face, gas leaves axially, c ~300 m/s, ~600 C, no swirl at design',
                       roof=roof(L.EXHAUST_START['x']), mating='EXHAUST agent rev 2 (7bd203a): 14 deg L80 diffuser + DN125 stub bolted to this flange'),
    casing_rear_flange=dict(x=L.CASING_FACE_X, r=[39.0, 48.0], bolts='4 x M5 PCD 88 at 45/135/225/315 deg (longer bolts, M5x20 A286)',
                            stack='casing flange | T-116 support flange (x 116-118) | T-120 housing front wall (x 118-121)'),
    turbine_housing_mounts=dict(pads='2 pads y = +/-(73..85), x 128-142, z -10..10, one vertical M10 bolt each at x 135, y +/-79',
                                roof_left=roof(135.0, 79.0, 0.0), roof_right=roof(135.0, -79.0, 0.0),
                                note='turbine housing carries the hot end on the FRAME slide pedestals; the 0.3 mm casing sheet must not carry it'),
    turbine_housing_envelope=dict(x=[L.HOUSING['x0'], L.HOUSING['x1']], OD=2 * L.HOUSING['shell_ro'], pads_y=L.HOUSING['mount_pad']['y_out']),
    tit_probe=dict(x=138.0, z_top=L.HOUSING['shell_ro'] + 7.0, thread='M8x1 boss, K-type 3 mm sheathed, tip in the plenum at r ~68'),
    generator_pod=dict(rev='d2g 2026-10-23 (buildable detail)', housing='G-200 x -260..-108 OD 110, front flange OD 128 at x -260..-252; G-202 front cover x -286..-258',
                       mass_kg=GJ.get('pod_mass_kg'), x_cg=GJ.get('pod_x_cg'), cradle='FR-170 at x -220..-190 on OD 110 (no bosses there); re-set the FR-171 jack for the new mass',
                       rear_face=dict(x=-108.0, strut_roots='3 x M6 Helicoil 2D at r 51.2, 90/210/330 deg', fairing='3 x M4 Helicoil at r 45.25, 30/150/270 deg',
                                      quill_guard='tube 20 x 1.5 pressed in a d20 H8 counterbore, x -116..-64'),
                       intake_lip_seal='x -130..-128 on OD 110 (no bosses at x > -131)',
                       terminal_box=dict(x=list(GL.TBOX['x']), y=list(GL.TBOX['y']), z=[GL.TBOX['z_gasket'][0], GL.TBOX['z_lid'][1]],
                                         power_gland='M25x1.5 on the front face (x -210), y 0, z 76', signal_gland='M16x1.5 on the +y side, x -180, z 76'),
                       ports=GJ.get('ports'), moved_ports=GL.MOVED_PORTS,
                       quill=dict(socket_x=list(L.QUILL['socket']), withdraw_travel_mm=13, waist='d6 x 54')),
    oil=dict(core_front_jet='drilled in tunnel flange (top), feed from the outside through a diffuser vane passage (v13A supply-line route)',
             core_rear_feed='tube d4x0.5 along the tunnel top (r 14.5) in the compressor-air annulus',
             core_scavenge='front: tunnel flange bottom port; rear: tube d6x0.5 along the tunnel bottom; both to the scavenge pump',
             generator='jets M8x1 at the top (G-202 x -276, G-200 x -136) into the SFD land, drains G1/8 at the bottom (x -277 / -141), 0.3 L/min per bearing',
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
