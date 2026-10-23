# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - self-built generator: joints, fits, seals, fasteners, torques (tables for the drawings, the BOM
docs/bom/variant_e_generator_bom.csv, the CAD (cad/variant_e/eg_generator.py) and docs/variant_e/02_generator.md).

Screws: preload F = k * Rp0.2 * A_s (k 0.6 steel-in-steel, 0.5 in Al with HELICOIL plus, 0.7 for the 12.9 pull bolt),
tightening torque T = F (0.16 P + 0.58 d2 mu_G + Dkm / 2 mu_K) with mu 0.12 (A4 + Loctite 243 / zinc flake) or 0.10 (MoS2 paste).
Fits: ISO 286-2 deviations for the sizes used.  O-rings: ISO 3601-1 (series G / class A), grooves to ISO 3601-2.
Run:  python3 sim/variant_e/eg_joints.py  ->  sim/variant_e/eg_joints.json
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_e'))
import eg_layout as EG                       # noqa: E402

# P, A_s, d2, head d_k, hole d_h (ISO 273 medium)
THREAD = {'M5': (0.8, 14.2, 4.480, 8.5, 5.5), 'M6': (1.0, 20.1, 5.350, 10.0, 6.6), 'M8': (1.25, 36.6, 7.188, 13.0, 9.0), 'M10': (1.5, 58.0, 9.026, 16.0, 11.0),
          'M12': (1.75, 84.3, 10.863, 18.0, 13.5), 'M12x1.25': (1.25, 92.1, 11.188, 18.0, 13.0), 'M16': (2.0, 157.0, 14.701, 24.0, 17.5),
          'M35x1.5': (1.5, 890.0, 34.026, 52.0, 35.0)}
RP = {'A4-70': 450, 'A4-80': 600, '8.8': 640, '10.9': 940, '12.9': 1100}


def screw(size, cls, k, mu=0.12):
    P, As, d2, dk, dh = THREAD[size]
    F = k * RP[cls] * As
    T = F * (0.16 * P + 0.58 * d2 * mu + 0.5 * 0.5 * (dk + dh) * mu) / 1e3
    return F, T


SCREWS = [  # joint, designation, qty, class, internal thread, k, lock / note
    ('front end bell E-G230 -> housing E-G200', 'ISO 4762 M10x35', 16, 'A4-80', 'HELICOIL plus M10 x 1.5D (15) in 6082-T6, blind 22', 0.5, 'Loctite 243, cross pattern 3 steps'),
    ('rear end bell E-G231 -> housing E-G200', 'ISO 4762 M10x35', 16, 'A4-80', 'HELICOIL plus M10 x 1.5D (15) in 6082-T6, blind 22', 0.5, 'Loctite 243, cross pattern 3 steps'),
    ('front bearing cap E-G232 -> front hub', 'ISO 4762 M6x16', 6, 'A4-80', 'HELICOIL plus M6 x 1.5D (9)', 0.5, 'Loctite 243'),
    ('rear seal cap E-G233 + guard flange E-G235 -> rear hub', 'ISO 4762 M6x30', 6, 'A4-80', 'HELICOIL plus M6 x 1.5D (9)', 0.5, 'Loctite 243'),
    ('air hood E-G234 -> front end bell', 'ISO 4762 M6x45', 8, 'A4-80', 'HELICOIL plus M6 x 1D (6), through the hood bosses', 0.4, 'EPDM foam gasket'),
    ('terminal box E-G240 -> housing', 'ISO 4762 M8x25', 4, 'A4-80', 'HELICOIL plus M8 x 1.5D (12)', 0.5, 'Loctite 243, flat silicone gasket'),
    ('terminal-box lid E-G241', 'ISO 7380-1 M5x10', 8, 'A4-70', 'HELICOIL plus M5 x 1.5D (7.5)', 0.35, 'IP65 gasket'),
    ('PEEK terminal block E-G242 -> box', 'ISO 4762 M6x20', 4, 'A4-70', 'tapped M6 in 6082 (12 deep)', 0.3, 'Loctite 243'),
    ('blower bracket E-G250 -> saddle base', 'ISO 4017 M8x25 + ISO 4032', 4, '8.8', 'through, nut', 0.6, 'Nord-Lock washers'),
    ('saddle clamp straps E-G261', 'ISO 4017 M12x80 + ISO 4032', 4, '8.8', 'through the strap ears, nut', 0.5, 'Nord-Lock; strap preload limits the Al housing stress'),
    ('saddles E-G260 -> base beam E-G262', 'ISO 4017 M16x60', 8, '8.8', 'through x-slots, nuts', 0.6, 'after alignment; jack bolts M16 x / y, shims z'),
    ('base beam E-G262 -> plenum floor / frame', 'ISO 4017 M16x50', 6, '8.8', 'through floor + doubler, onto the frame cross members x -1050 / -600 / -200', 0.6, 'Nord-Lock'),
]
rows = []
for j, des, q, cls, ins, k, lock in SCREWS:
    size = des.split()[2].split('x')[0]
    F, T = screw(size, cls, k)
    rows.append(dict(joint=j, screw=des, qty=q, cls=cls, internal_thread=ins, preload_kN=round(F / 1e3, 1), torque_Nm=round(T, 1), lock=lock))
F_pb, T_pb = screw('M12x1.25', '12.9', 0.55, mu=0.10)
rows.append(dict(joint='quill hub on the 1:10 shaft taper', screw='ISO 4762 M12x1.25x45', qty=1, cls='12.9', internal_thread='M12x1.25 in the 42CrMo4 shaft end, 24 deep',
                 preload_kN=round(F_pb / 1e3, 1), torque_Nm=round(T_pb, 1), lock='MoS2 paste under the head + on the thread; drive-up 0.6 +/-0.1 mm checked with a dial gauge'))
F_nut = 9.0e3
P, As, d2, dk, dh = THREAD['M35x1.5']
T_nut = F_nut * (0.16 * P + 0.58 * d2 * 0.12 + 0.5 * 0.5 * (52 + 35) * 0.12) / 1e3
rows.append(dict(joint='bearing inner rings (front 7008-E + speed wheel, rear 7008-C)', screw='precision lock nut M35x1.5 OD 52 B 12 (Spieth MSF 35x1.5 / SKF KMD 7)', qty=2,
                 cls='steel', internal_thread='M35x1.5 6g on the shaft', preload_kN=9.0, torque_Nm=round(T_nut, 1), lock='2 radial clamping screws M5, 4 N.m (nut-maker value)'))

FITS = [
    dict(joint='bearing IR on the d40 journals', hole='bearing bore P4 (0/-6)', shaft='40 js4 (+/-3.5)', result='-3.5 .. +9.5 um (light press: heat IR to 80 C)'),
    dict(joint='bearing OR in the cartridges', hole='68 H4 (0/+8) in the cartridge', shaft='OR P4 (0/-7)', result='0 .. 15 um clearance (rear floats on the wave spring; front clamped by the cap)'),
    dict(joint='SFD land', hole='84.24 H6 (0/+22) in the end-bell hubs', shaft='cartridge OD 84.000 (0/-10)', result='radial oil film 0.120 .. 0.136 mm (same as the core cartridges)'),
    dict(joint='Cu screen on the shaft (shrink)', hole='screen bore 71 H6 (0/+19)', shaft='71 +0.120/+0.100', result='0.081 .. 0.120 interference; heat screen to 220 C (CuCr1Zr, 20 min)'),
    dict(joint='magnet segments on the screen', hole='magnet ID 74.06 +0.02/0 (ground arc segments)', shaft='screen OD 74.00 h5 (0/-13)', result='0.06 .. 0.093 bond gap: Henkel Loctite AA 326 + 7649 activator (or Araldite-free: Loctite EA 9497 high-temp epoxy)'),
    dict(joint='end rings on the screen', hole='74 H7 (0/+30)', shaft='74 h5', result='0 .. 43 clearance, Loctite 648 + axial clamp by the sleeve'),
    dict(joint='CFRP sleeve on magnets + end rings', hole='sleeve ID 1:500 taper', shaft='magnet OD 1:500 taper, ground after bonding', result='diametral interference 0.57 +/-0.02 mm set by the press stroke (eg_sleeve.json)'),
    dict(joint='stator stack in the jacket (shrink)', hole='jacket ID 262.000 +0.032/0', shaft='stack OD 262.240 0/-0.025 (ground)', result='0.183 .. 0.240 interference; heat jacket to 180 C; 0.08 .. 0.13 left at 60 C'),
    dict(joint='jacket in the housing', hole='290 H7 (0/+52)', shaft='jacket lands 290 g6 (-17/-49)', result='17 .. 101 clearance, 2 + 2 O-rings with leak-off groove'),
    dict(joint='front end-bell spigot', hole='290 H7 (housing, same setting as the 286 H7)', shaft='290 g6', result='17 .. 101 clearance + 2 dowels 8 m6'),
    dict(joint='rear end-bell spigot', hole='286 H7 (0/+52)', shaft='286 g6 (-17/-49)', result='17 .. 101 clearance + 2 dowels 8 m6; bores 290 / 286 coaxial <= 0.02'),
    dict(joint='dowels end bell / housing', hole='8 H7 housing (press) / 8 F7 end bell (slip)', shaft='ISO 8734 8 m6', result='location +/-0.01'),
    dict(joint='cartridge anti-rotation pins', hole='4 H7 in the hub shoulder; slot 4.2 in the cartridge lip', shaft='ISO 8734 4 m6 x 10', result='cartridge free radially, no rotation'),
    dict(joint='quill hub on the shaft taper', hole='hub taper 1:10 (lapped, blue check >= 85 % contact)', shaft='shaft taper 1:10 ground', result='drive-up 0.6 mm -> 0.06 mm diametral interference, T_cap 716 N.m (eg_rotor.json)'),
    dict(joint='quill socket on the core hex', hole='socket AF 24.020 .. 24.040 (rotary broached, plasma nitrided)', shaft='crowned hex AF 23.990 .. 24.000 (core shaft, gas nitrided)',
         result='0.020 .. 0.050 on flats, axial float +/-1 mm, no adjustment'),
    dict(joint='labyrinths (hub bores, 5 teeth)', hole='tooth tips d50.60 +0.05/0', shaft='seal lands 50 h6', result='radial 0.30 .. 0.33 mm (SFD orbit + thermal); outer: quill hub d56 h6 in d56.60'),
    dict(joint='speed wheel on the shaft', hole='38 H6', shaft='38 k5', result='-0.018 .. +0.014; clamped between IR and nut'),
    dict(joint='guard flange spigot', hole='rear end bell 120 H8', shaft='guard flange 120 f7', result='centres the guard on the shaft axis (<= 0.1)'),
]


def oring(name, ID, cs, groove_d, mating_d, groove_w, kind, mat, qty):
    if kind == 'piston':          # groove in the inner part, sealing on the bore mating_d
        squeeze = (cs - (mating_d - groove_d) / 2) / cs
        stretch = groove_d / ID - 1
    elif kind == 'rod':
        squeeze = (cs - (groove_d - mating_d) / 2) / cs
        stretch = 0.0
    else:                         # face: groove_d = groove depth
        squeeze = (cs - groove_d) / cs
        stretch = 0.0
    return dict(seal=name, oring='ISO 3601-1 %g x %.2f' % (ID, cs), material=mat, qty=qty, groove='%s groove: %s %.2f, width %.1f' % (kind, 'bottom d' if kind != 'face' else 'depth', groove_d, groove_w),
                squeeze_pct=round(100 * squeeze, 1), stretch_pct=round(100 * stretch, 1), ok=bool(0.10 <= squeeze <= 0.30 and stretch <= 0.05))


ORINGS = [
    oring('jacket O-ring lands (2 per end, leak-off groove 2 x 1 mm between)', 280.0, 3.55, 284.30, 290.0, 4.8, 'piston', 'EPDM 70 (glycol, peroxide-cured)', 4),
    oring('front end-bell spigot (air / oil mist)', 280.0, 3.55, 284.30, 290.0, 4.8, 'piston', 'FKM 75', 1),
    oring('rear end-bell spigot', 275.0, 3.55, 280.30, 286.0, 4.8, 'piston', 'FKM 75', 1),
    oring('SFD cartridges (2 per cartridge, centring spring ~3 N/um, measure)', 77.5, 2.65, 79.58, 84.24, 3.6, 'piston', 'FKM 75', 4),
    oring('front bearing cap face (groove r 43.2-46.0)', 85.0, 2.65, 2.00, 0.0, 2.8, 'face', 'FKM 75', 1),
    oring('rear seal cap face (groove r 43.2-46.0)', 85.0, 2.65, 2.00, 0.0, 2.8, 'face', 'FKM 75', 1),
]
ORINGS.append(dict(seal='glycol fittings G3/4 + leak-off G1/8 (ISO 1179-2 form E)', oring='ED-rings G3/4 + G1/8', material='EPDM', qty=4, groove='-', squeeze_pct=None, stretch_pct=None, ok=True))

HELICOILS = [dict(size='M10 x 1.5D', qty=32, where='housing end faces (end bells)'), dict(size='M8 x 1.5D', qty=4, where='housing top (terminal box)'),
             dict(size='M6 x 1.5D', qty=12, where='hub end faces r 47 (front bearing cap, rear seal cap + guard)'), dict(size='M6 x 1D', qty=8, where='front end-bell face (hood)'),
             dict(size='M5 x 1.5D', qty=8, where='terminal box (lid)'), dict(size='M12 x 1 x 1.5D', qty=2, where='end-bell IR-pyrometer ports')]
JACKING = [dict(part='end bells', threads='2 x M10 in each flange (180 deg apart), push against the housing face', tool='ISO 4017 M10x40 8.8 (2)'),
           dict(part='jacket + stator', threads='2 x M10 in the jacket front face', tool='pull bar + 2 x M10 rods, hydraulic cylinder 2 t against the housing face'),
           dict(part='front bearing cap', threads='2 x M6', tool='M6x25'),
           dict(part='quill hub', threads='M14 x 1.5 in the hub bore behind the bolt seat', tool='M14 jacking screw through the hollow quill'),
           dict(part='SFD cartridges', threads='internal groove for a puller', tool='Kukko 21-5 internal puller (DE)')]
AXIAL = dict(rotor_axial_position='front 7008-E locates; its cartridge is clamped by the front bearing cap on a ground shim (E-G226, 0.5-2.0 mm) -> '
                                   'magnet centre to stack centre +/-0.3 mm (measured from the rear seal-cap face with a depth gauge)',
             rear='7008-C outer ring floats in its cartridge (0..15 um), 300 N wave spring (E-G224) between the cartridge lip and the OR -> preload on both bearings',
             thermal='rotor grows ~+0.35 mm rearward vs. the housing at full load (steel shaft 85 C vs Al pod 60 C): taken by the floating rear OR and the +/-1 mm quill float',
             end_float_quill='+/-1.0 mm at the AF24 socket (hex engagement 23 mm)')
ELECTRICAL = dict(creepage='terminal block: >= 12.5 mm creepage, 8 mm clearance (IEC 60664-1, 1000 V, pollution 3)',
                  insulation='strand enamel grade 2 class 200 + polyimide tape + glass serving per conductor; NKN 0.31 slot liner (ground wall); NKN 0.5 layer separator; '
                             'Nomex 410 0.25 phase paper in the end windings; VPI epoxy class H (Elantas Elmotherm / Von Roll Damisol, CH/DE)',
                  tests='IEC 60034-1: 2 U + 1000 V = 2.3 kV ac 1 min (new winding; 1.0 kV dc IR > 1 GOhm at 40 C); surge 3.5 kV (IEC 60034-15 level for 690 V class)')

out = dict(title='GR180 version E generator joints / fits / seals / fasteners', date='2026-10-24', script='sim/variant_e/eg_joints.py',
           screws=rows, fits=FITS, orings=ORINGS, helicoils=HELICOILS, jacking=JACKING, axial=AXIAL, electrical=ELECTRICAL,
           dowels=[dict(where='end bell / housing', item='ISO 8734 8 m6 x 24, 1.4034 hardened', qty=4), dict(where='cartridge anti-rotation', item='ISO 8734 4 m6 x 10', qty=2),
                   dict(where='terminal box / housing', item='ISO 8734 6 m6 x 16', qty=2)],
           notes=['A4-80 into Al only with HELICOIL plus (Boellhoff DE, 1.4301), tapped with STI taps; k 0.5 keeps the Al bearing stress < 250 MPa under the heads (washer-face heads)',
                  'all rotating fasteners (nuts, pull bolt) are balanced with the rotor and angle-marked'])
json.dump(out, open(os.path.join(HERE, 'eg_joints.json'), 'w'), indent=1)
for r in rows:
    print('%-52s %-36s x%-2d %-6s F %5.1f kN  T %6.1f N.m' % (r['joint'], r['screw'], r['qty'], r['cls'], r['preload_kN'], r['torque_Nm']))
for o in ORINGS:
    print(o['seal'][:50], o['oring'], o['squeeze_pct'], o['stretch_pct'], o['ok'])
print('-> sim/variant_e/eg_joints.json')
