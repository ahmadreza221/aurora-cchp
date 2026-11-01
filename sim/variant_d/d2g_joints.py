# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version D2 - generator pod joints, fits, seals and balance (d2g rev): one table per joint type for the drawings,
the BOM (docs/bom/variant_d2_generator_bom.csv) and docs/variant_d/05_generator_detail.md.

Screws: preload F = k * Rp0.2 * As (k 0.5 in Al / Helicoil and gasketed joints, 0.6 steel), torque T = F (0.16 P + 0.58 d2 mu + Dkm/2 mu),
mu 0.14 (A4 with Loctite 243).  Fits: ISO 286-2 limits (hard-coded for the sizes used).  O-rings: ISO 3601-1 class A, grooves ISO 3601-2 style.
Run:  uv run sim/variant_d/d2g_joints.py  ->  sim/variant_d/d2g_joints.json
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ screws
THREAD = {'M3': (0.5, 5.03, 2.675, 5.5, 3.4), 'M4': (0.7, 8.78, 3.545, 7.0, 4.5), 'M5': (0.8, 14.2, 4.480, 8.5, 5.5),
          'M6': (1.0, 20.1, 5.350, 10.0, 6.6), 'M10x0.75': (0.75, 64.5, 9.513, 18.0, 10.2)}


def torque(size, Rp, k=0.5, mu=0.14):
    P, As, d2, dk, dh = THREAD[size]
    F = k * Rp * As
    Dkm = 0.5 * (dk + dh)
    T = F * (0.16 * P + 0.58 * d2 * mu + 0.5 * Dkm * mu) / 1e3
    return F, T


SCREWS = [  # joint, designation, qty, material/class, thread in, engagement mm, k, lock
    ('front cover G-202 -> housing G-200', 'ISO 4762 M5x12', 6, 'A4-80', 'HELICOIL plus M5x1.5D (7.5) in 6082-T6', 8.0, 0.5, 'Loctite 243', 600),
    ('terminal box G-240 -> housing', 'ISO 7380-1 M4x12', 4, 'A4-80', 'HELICOIL plus M4x1D (4) blind 5.7', 5.2, 0.4, 'Loctite 243', 600),
    ('lid G-241 -> box', 'ISO 7380-1 M3x8', 4, 'A4-80', 'HELICOIL plus M3x1.5D in the box columns', 4.0, 0.35, 'none (gasket)', 600),
    ('PEEK block G-242 -> box floor', 'ISO 7380-1 M4x12', 2, 'A2-70', 'tapped direct in the 4 mm Al floor', 3.5, 0.25, 'Loctite 243', 450),
    ('phase studs M6 (nuts on lugs)', 'ISO 4032 M6 brass nut on M6 brass stud', 3, 'CuZn39Pb3', 'stud pressed in PEEK', 6.0, 0.3, 'spring washer', 250),
    ('strut roots INT-115 -> housing rear face', 'M6 rod-end thread (intake part)', 3, '1.4301', 'HELICOIL plus M6x2D (12)', 12.0, 0.5, 'Loctite 243', 450),
    ('tail fairing INT-120 -> rear face', 'ISO 7380-1 M4x8 (intake part)', 3, 'A4-80', 'HELICOIL plus M4x1.5D (6)', 6.0, 0.4, 'Loctite 243', 600),
    ('accelerometers VE-011 / VE-012 (AUX)', 'M6 stud', 2, 'steel', 'HELICOIL plus M6x1D (6) blind 8', 6.0, 0.3, 'none', 450),
    ('jack-hole plugs G-259', 'ISO 4026 M5x6', 2, 'A4', 'thread in G-200 (no insert)', 6.0, 0.2, 'Loctite 542', 450),
    ('cover jack-off (tool only)', '2 x ISO 4017 M5x20 (workshop)', 2, '8.8', 'M5 tapped in G-202 flange (HELICOIL)', 4.0, 0.3, '-', 640),
]
screw_rows = []
for j, des, q, cls, ins, eng, k, lock, Rp in SCREWS:
    size = des.split()[2].split('x')[0] if des.startswith('ISO') and 'M' in des.split()[2] else ('M6' if 'M6' in des else 'M5' if 'M5' in des else 'M4')
    if 'ISO 4032' in des:
        size = 'M6'
    F, T = torque(size, Rp, k)
    screw_rows.append(dict(joint=j, screw=des, qty=q, cls=cls, internal_thread=ins, engagement_mm=eng, preload_kN=round(F / 1e3, 2),
                           torque_Nm=round(T, 1), lock=lock))
# rotor locknut (stack clamp) and the carrier torque path
F_nut = 6000.0
P, As, d2, dk, dh = THREAD['M10x0.75']
T_nut = F_nut * (0.16 * P + 0.58 * d2 * 0.12 + 0.5 * 0.5 * (18 + 10.2) * 0.12) / 1e3
T_clamp = F_nut * 0.15 * (6.0e-3 + 6.0e-3)          # 2 friction faces at r_m ~6 mm (spacer / carrier faces)
T_rated, T_fault = 28e3 / (115000 * 2 * math.pi / 60), 4 * 28e3 / (115000 * 2 * math.pi / 60)

# ------------------------------------------------------------------ fits (ISO 286-2, um)
FITS = [
    dict(joint='bearing IR on the generator shaft', hole='d10 bearing bore P4 (0/-4)', shaft='10 js4 (+/-1.25)', result='-1.3 .. +5.3 (light press, warm IR to 60 C)'),
    dict(joint='bearing OR in the cartridge (front and rear)', hole='22 H5 (0/+9)', shaft='OR P4 (0/-5)', result='0 .. 14 clearance (rear floats; front held by the spring preload on the lip + shim)'),
    dict(joint='SFD land', hole='28 H6 (0/+13) in G-200 / G-202', shaft='27.800 (0/-9) cartridge', result='radial film 0.100 .. 0.111'),
    dict(joint='magnet carrier on the shaft', hole='10 (-4/-10) carrier bore', shaft='10 js4', result='2.8 .. 11.3 interference: heat carrier assembly to 150 C (SmCo, CF-epoxy Tg 180 OK); 60 N.m slip torque'),
    dict(joint='seal spacers on the shaft', hole='10 F6 (+13/+22)', shaft='10 js4', result='12 .. 23 clearance (slide by hand; clamped by the locknut)'),
    dict(joint='stator core in the jacket (shrink)', hole='88 H6 (0/+22)', shaft='88.120 +/-0.010 (ground core OD)', result='0.098 .. 0.130 interference; heat jacket to 130 C'),
    dict(joint='jacket in the housing', hole='98 H7 (0/+35) / 96 H7 (0/+35)', shaft='98 p6 (+37/+59) / 96 p6 (+37/+59)', result='2 .. 59 interference (press with a hand press, O-rings greased)'),
    dict(joint='front cover spigot', hole='98 H7', shaft='98 g6 (-12/-34)', result='12 .. 69 clearance + 2 dowels 4 m6 / H7 (location +/-0.01)'),
    dict(joint='cover / housing dowels', hole='4 H7 (0/+12)', shaft='4 m6 (+4/+12)', result='press in G-200, slip (H7 + 0.005) in G-202'),
    dict(joint='anti-rotation pins d2', hole='2 H7 in G-200 / G-202, slot 2.2 in the cartridge lip', shaft='2 m6', result='cartridge free radially +/-0.1, no rotation'),
    dict(joint='quill guard tube', hole='20 H8 (0/+33)', shaft='tube 20 (+/-0.08)', result='Loctite 638 (gap-filling retainer)'),
    dict(joint='quill socket on the engine hex', hole='socket AF 6.010 .. 6.020 (rotary broached, nitrided)', shaft='crowned hex AF 5.995 .. 6.000', result='0.010 .. 0.025 on flats, float +/-0.5 axial, no adjustment'),
]

# ------------------------------------------------------------------ O-rings (ISO 3601-1 class A)
def oring(name, ID, cs, groove_d_dia, mating_dia, groove_w, kind):
    squeeze = (cs - abs(mating_dia - groove_d_dia) / 2) / cs if kind == 'radial' else (cs - groove_d_dia) / cs
    stretch = (groove_d_dia / ID - 1) if kind == 'radial' else 0.0
    return dict(seal=name, oring='ISO 3601-1 %.1f x %.2f' % (ID, cs), groove='%s: groove d %.2f, width %.1f' % (kind, groove_d_dia, groove_w) if kind == 'radial'
                else 'axial face: groove depth %.2f, width %.1f, ID %.1f' % (groove_d_dia, groove_w, ID - 0.4), squeeze_pct=round(100 * squeeze, 1),
                stretch_pct=round(100 * stretch, 1))


ORINGS = [oring('SFD cartridge (x4, FKM 75)', 23.6, 1.80, 24.90, 28.0, 2.4, 'radial'),
          oring('jacket front (EPDM 70, glycol)', 92.5, 2.65, 93.90, 98.0, 3.6, 'radial'),
          oring('jacket rear (EPDM 70, glycol)', 90.0, 2.65, 91.90, 96.0, 3.6, 'radial'),
          oring('front cover face seal (FKM 75)', 103.0, 1.80, 1.30, 0, 2.6, 'axial')]

# ------------------------------------------------------------------ shrink fit stator / jacket
E_al, E_st, a_al, a_st = 70e3, 205e3, 23.6e-6, 11.5e-6
D = 88.0
d_min20, d_max20 = 0.098, 0.130
loss_100C = D * (a_al - a_st) * 80
p_min = E_al * (d_min20 - loss_100C) / D * 0.5                 # thin Al sleeve on a stiff core (est)
T_cap_min = 0.2 * p_min * math.pi * D * 80 * D / 2 / 1e3
dT_assembly = (d_max20 + 0.05) / (D * a_al)

# ------------------------------------------------------------------ balance (ISO 21940-11)
def U_per(G, m, n):
    return 9549 * G * m / n                                    # g.mm
m_rot = 0.68
bal = dict(rotor_mass_kg=m_rot, n_rpm=115000, planes='G-223 front end ring (x -243.5) and rear end ring (x -158.5), radial d2 drillings max 1.5 deep',
           G1_total_gmm=round(U_per(1.0, m_rot, 115000), 3), G2_5_total_gmm=round(U_per(2.5, m_rot, 115000), 3),
           G1_per_plane_gmm=round(U_per(1.0, m_rot, 115000) / 2, 3), method='complete rotor incl. bearings, locknut and quill on a soft-bearing machine '
           '(supports on the bearing ORs), 2 planes, then check run-out of the socket hub <= 5 um TIR; target G1, accept <= G2.5',
           socket_clearance_effect_gmm=round(0.008 * 0.0125, 4))

# ------------------------------------------------------------------ hex coupling
T = T_rated
hex_p = T / (0.3 * 5.75e-3 * (6e-3) ** 2) / 1e6
out = dict(title='GR180 D2 generator pod: joints, fits, seals, balance (d2g rev)', date='2026-10-23', script='sim/variant_d/d2g_joints.py',
           screws=screw_rows,
           rotor_stack=dict(locknut='M10x0.75, OD 18 (G-225)', preload_kN=F_nut / 1e3, nut_torque_Nm=round(T_nut, 1),
                            shaft_stress_MPa=round(F_nut / (math.pi / 4 * 8.9 ** 2), 0), clamp_friction_torque_Nm=round(T_clamp, 1),
                            carrier_interference_torque_Nm=60, T_rated_Nm=round(T_rated, 2), T_fault_x4_Nm=round(T_fault, 2),
                            note='torque path: magnets -> carrier (interference fit, 60 N.m) -> shaft; the quill (fuse ~8.5 N.m) breaks first'),
           fits=FITS, orings=ORINGS,
           stator_shrink=dict(interference_20C_mm=[d_min20, d_max20], loss_at_100C_mm=round(loss_100C, 3), p_min_100C_MPa=round(p_min, 1),
                              torque_capacity_min_Nm=round(T_cap_min, 0), assembly_jacket_temp_C=round(20 + dT_assembly), choice='shrink fit only (no key, no adhesive): '
                              'simplest robust; stator torque 2.3 N.m rated / ~15 N.m short-circuit peak'),
           magnet_retention=dict(sleeve='T700/T800 carbon 3 mm', interference_mm=0.08, hoop_115k_MPa=417, hoop_138k_MPa=600, SF=2.67,
                                 assembly='grind magnet OD 30.08, press the sleeve (ID 30.00) over a 1:200 conical mandrel with assembly grease, grind OD 36.00'),
           balance=bal,
           hex_coupling=dict(AF=6, engagement_mm=11.5, contact_p_rated_MPa=round(hex_p, 1), contact_p_fault_MPa=round(4 * hex_p, 1),
                             lead_in='30 deg chamfers on the socket mouth and the hex tip', axial_float_mm=0.5,
                             disengage_travel_mm=13, alignment='rotor turned by an AF5 key through the M16 front plug until the flats line up'),
           wave_spring=dict(F_N=60, note='60 N > max quill-hex slip force with nitrided/DLC flats (mu 0.1 -> ~35 N), keeps both generator bearings loaded'))
for r in screw_rows:
    print('%-44s %-30s x%d  %-5s preload %.2f kN  T %.1f N.m  %s' % (r['joint'], r['screw'], r['qty'], r['cls'], r['preload_kN'], r['torque_Nm'], r['lock']))
print('locknut %.1f N.m for 6 kN; clamp friction %.1f N.m; stator shrink p_min(100C) %.1f MPa, T_cap %.0f N.m, heat jacket to %d C'
      % (T_nut, T_clamp, p_min, T_cap_min, 20 + dT_assembly))
for o in ORINGS:
    print(o)
print('balance G1 total %.3f g.mm, G2.5 %.3f g.mm' % (bal['G1_total_gmm'], bal['G2_5_total_gmm']))
json.dump(out, open(os.path.join(HERE, 'd2g_joints.json'), 'w'), indent=1)
print('-> sim/variant_d/d2g_joints.json')
