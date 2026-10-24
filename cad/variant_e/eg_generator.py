# GR180 version E - self-built high-speed PMG, buildable detail (EG, 2026-10-24).
# All numbers: cad/variant_e/eg_layout.py; analyses: sim/variant_e/eg_*.py; joints: sim/variant_e/eg_joints.json.
# Pod: E-G200 housing (thick 6082 tube, bores 290 H7 / 286 H7 in one setting) + E-G201 glycol jacket (double-start helical
# channel, stator shrunk in) + 2 end bells with RE-ENTRANT hubs (bearings inside the end-winding envelope) + bearing / seal
# caps + guard; rotor: 42CrMo4 shaft, CuCr1Zr eddy screen, 12 laminated Sm2Co17 arc segments, 1.4404 end rings, T800S
# CFRP sleeve, 2 x 7008 hybrid in SFD cartridges, precision nuts, speed wheel, hollow quill on a 1:10 taper with a central
# pull bolt; cooling-air blower + hood; saddles.  Every fastener, Helicoil, dowel and O-ring is a simple body.
# One STEP per part -> cad_out/variant_e/GENERATOR/E-G2xx_*.step + e_generator_parts.json (read by e_check.py, eg_check.py
# and the Fusion MODE E importer).
# Run:  LANG=en_US.UTF-8 freecadcmd cad/variant_e/eg_generator.py   (or cad/variant_e/e_generator.py with e_layout.GEN_DETAILED)
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
from e_common import *
import e_common as EC
import eg_layout as G

EC.RHO.update({'CuCrZr': 8.89e-6, 'SmCo': 8.40e-6, 'CFRP': 1.58e-6, 'GFRP': 1.90e-6, 'PEEK': 1.32e-6, 'cu_slot': 6.6e-6, 'litz_ew': 4.6e-6,
               'lam10': 7.65e-6 * 0.95, 'bronze': 8.8e-6, 'FKM': 1.9e-6, 'EPDM': 1.2e-6, 'filter': 0.15e-6})
EM, R, EB, H, J, Q = G.EM, G.ROT, G.EB, G.HOUS, G.JACK, G.QUILL_EG
P = Parts('GENERATOR')


def add(tag, shape, mat, desc, mb, mass=None, note=''):
    P.add(tag, shape, mat, desc, mb, mass=mass, note=note)


def ring(x0, x1, ri, ro):
    return cyl(x0, x1, ro, ri)


def ax_cyl(x0, x1, r_pos, a, rad):
    return Part.makeCylinder(rad, x1 - x0, V(x0, 0, 0) + rdir(a) * r_pos, XA)


def screw_ax(x_face, r_pos, a, d, L, dk, k, into=+1):
    """ISO 4762 envelope along x: head outside the face, shank (d - 0.1) into the material (into = +1 -> +x)"""
    p = V(x_face, 0, 0) + rdir(a) * r_pos
    if into > 0:
        return Part.makeCylinder(dk / 2, k, p - XA * k, XA).fuse(Part.makeCylinder((d - 0.1) / 2, L, p, XA))
    return Part.makeCylinder(dk / 2, k, p, XA).fuse(Part.makeCylinder((d - 0.1) / 2, L, p - XA * L, XA))


def coil_ax(x_face, r_pos, a, d, depth, into=+1):
    """HELICOIL plus insert envelope: tube d .. 1.13 d over the depth"""
    p = V(x_face, 0, 0) + rdir(a) * r_pos
    p0 = p if into > 0 else p - XA * depth
    return Part.makeCylinder(0.565 * d, depth, p0, XA).cut(Part.makeCylinder(0.5 * d, depth + 2, p0 - XA, XA))


def rad_screw(x, a, r_face, d, L, dk, k):
    dr = rdir(a)
    return Part.makeCylinder(dk / 2, k, V(x, 0, 0) + dr * r_face, dr).fuse(Part.makeCylinder((d - 0.1) / 2, L, V(x, 0, 0) + dr * (r_face - L), dr))


def polar(n, phase=0.0):
    return [phase + 360.0 * k / n for k in range(n)]


def rot_slot(shape, k):
    shape.rotate(V(0, 0, 0), XA, 360.0 * (k + 0.5) / EM['slots'] - 90.0)
    return shape


Rb, Ro = EM['bore'] / 2, EM['stator_OD'] / 2
bs, hs, hw = EM['slot_w'], EM['slot_depth'], EM['wedge_h']


def slot_tool(x0, x1, k):
    t = box(x0, x1, -bs / 2, bs / 2, Rb - 2.0, Rb + hs).fuse(box(x0, x1, -bs / 2 - 0.8, bs / 2 + 0.8, Rb + 1.0, Rb + 3.0))
    return rot_slot(t, k)


def slotted(x0, x1, ro, ri):
    return cyl(x0, x1, ro, ri).cut(Part.makeCompound([slot_tool(x0 - 0.5, x1 + 0.5, k) for k in range(EM['slots'])]))


fx0, fx1 = EB['front']['disk']
rx0, rx1 = EB['rear']['disk']
X0, X1 = H['x']
B16 = polar(16, 11.25)
DOW = (95.625, 275.625)
JB = (5.625, 185.625)                       # end-bell jacking threads
IR_R = EB['ir_port_r']
LEAK_A = 200.0                              # leak-off fittings low on the -y side (clear of the saddles)
HX0, HX1 = G.HOOD['x']

# ================================================================== POD: housing, jacket, circlip, dowel
hous = rev([(X0, H['bore_front_r']), (X0, H['r_out']), (X1, H['r_out']), (X1, H['bore_rear_r']), (H['x_shoulder'], H['bore_rear_r']), (H['x_shoulder'], H['bore_front_r'])])
hous = hous.cut(cyl(-774.0, -770.0, 149.5, 140.0))
bos = [rad_cyl(xg_, 0.0, 150.0, 178.0, 18.0) for xg_ in (-740.0, -445.0)] + [rad_cyl(xl, LEAK_A, 150.0, 172.0, 9.0) for xl in (-752.0, -432.5)]
hous = fuse_all([hous] + bos).removeSplitter()
for xf, s in ((X0, +1), (X1, -1)):
    for a in B16:
        hous = hous.cut(ax_cyl(xf if s > 0 else xf - 22.0, xf + 22.0 if s > 0 else xf, 155.0, a, 0.565 * 10))
    for a in DOW:
        hous = hous.cut(ax_cyl(xf if s > 0 else xf - 16.0, xf + 16.0 if s > 0 else xf, 155.0, a, 4.0))
for xg_ in (-740.0, -445.0):
    hous = hous.cut(rad_cyl(xg_, 0.0, 162.0, 180.0, 13.2)).cut(rad_cyl(xg_, 0.0, 140.0, 163.0, 8.0))
for xl in (-752.0, -432.5):
    hous = hous.cut(rad_cyl(xl, LEAK_A, 162.0, 174.0, 4.9)).cut(rad_cyl(xl, LEAK_A, 140.0, 163.0, 1.5))
TBS = [(xb_, a) for a in (64.9, 115.1) for xb_ in (-800.0, -710.0)]
for xb_, a in TBS:
    hous = hous.cut(rad_cyl(xb_, a, 152.0, 166.0, 0.565 * 8))
w0, w1, wh = G.TBOX['window']
hous = hous.cut(box(w0, w1, -wh, wh, 130.0, 175.0))
hous = hous.cut(rad_cyl(-766.0, 0.0, 144.0, 166.0, 4.0))
add('E-G200_Pod_Housing', hous, 'Al', 'pod housing: thick tube OD 330, bore 290 H7 (front, jacket seat) / 286 H7 (rear) turned in ONE setting (coaxial <= 0.02), '
    'jacket shoulder x -422.5, DIN 472 circlip groove, 2 x 16 HELICOIL M10 + 2 dowels per end face, glycol ports G3/4 (+y), leak-off G1/8 (low -y), lead window (top), '
    '4 x HELICOIL M8 for the terminal box, jacket anti-rotation dowel hole',
    'make: 6082-T6 forged ring / thick tube d340/280 x 480, CNC turning (both bores one clamping) + 5-axis for ports / holes',
    note='bores Ra 0.8, coaxiality 290 H7 / 286 H7 <= 0.02, end faces perpendicular <= 0.02; HELICOIL plus M10 x 1.5D')
jk = rev([(J['x'][0], J['r_in'] + 1.0), (J['x'][0], J['r_out']), (J['x'][1], J['r_out']), (J['x'][1], J['r_in'] + 1.0), (-450.0, J['r_in'] + 1.0), (-450.0, J['r_in']),
          (-735.0, J['r_in']), (-735.0, J['r_in'] + 1.0)])
xg0, xg1 = J['channel']
jk = jk.cut(cyl(xg0, xg0 + 5.0, J['r_out'] + 1, J['r_groove'])).cut(cyl(xg1 - 5.0, xg1, J['r_out'] + 1, J['r_groove']))
xc = xg0 + 8.0
while xc + 18.0 <= xg1 - 8.0 + 1e-6:
    jk = jk.cut(cyl(xc, xc + 18.0, J['r_out'] + 1, J['r_groove']))
    xc += 23.0
ORG = ((-760.5, -755.7), (-749.0, -744.2), (-440.7, -435.9), (-429.4, -424.6))
for (a_, b_) in ORG:
    jk = jk.cut(cyl(a_, b_, J['r_out'] + 1, 142.15))
for (a_, b_) in ((-753.0, -751.0), (-433.5, -431.5)):
    jk = jk.cut(cyl(a_, b_, J['r_out'] + 1, 144.0))
for a in (90.0, 270.0):
    jk = jk.cut(ax_cyl(J['x'][0] - 1, J['x'][0] + 14.0, 138.0, a, 4.25))
jk = jk.cut(rad_cyl(-766.0, 0.0, 139.5, 146.0, 4.1))
add('E-G201_Glycol_Jacket', jk, 'Al', 'glycol jacket sleeve: ID 262 H6 (stator shrink 0.18-0.24), OD 290 g6 lands, double-start helical channel 18 x 8 lead 46 (2 x 6.5 turns), '
    'front / rear manifold grooves, 2 + 2 O-ring grooves (bottom d284.3) with leak-off grooves, 2 x M10 pull-out threads, anti-rotation dowel slot',
    'make: 6082-T6 tube d300/250 x 350, CNC turning; helix single-point turned (2-start, like a coarse thread)',
    note='CAD shows the helix as 12 rings of the same section; h 7200 W/m2K, 28 kPa at 30 L/min (eg_thermal.json)')
add('E-G207_Jacket_Circlip_DIN472_290', ring(-774.0, -770.0, 140.0, 149.4), 'steel', 'internal circlip DIN 472 290 x 4 (axial stop of the jacket, front)', 'buy (Hugro DE / Wuerth DE)', mass=0.35)
add('E-G208_Jacket_Dowel_d8', rad_cyl(-766.0, 0.0, 140.0, 158.0, 4.0), 'steel', 'radial anti-rotation dowel ISO 8734 8 m6 x 18 (housing -> jacket slot), reacts the stator torque', 'buy (Bossard CH, Halder DE)', mass=0.007)

# ================================================================== STATOR: core, end plates, winding, wedges
add('E-G202_Stator_Core_NO10', slotted(G.X_SF, G.X_SR, Ro, Rb), 'lam10', 'stator core 24 open slots 8.6 x 37 (+ wedge notches), bore 126, OD 262.24 ground (shrink), stack 270 of 0.10 mm NO10, '
    'self-bonding varnish (backlack), no welds / keys', 'buy: bonded lamination stack to our drawing (laser cut + backlack bonded, OD ground)',
    note='order spec docs/variant_e/02_generator.md section 5; Kienle+Spiess (DE), Euro Group (IT), Surahammar / Cogent (SE), JFE (JP), Baosteel (CN)')
add('E-G203_Stator_End_Plates_x2', Part.makeCompound([slotted(G.X_SF - 1.5, G.X_SF, Ro - 2.0, Rb + 0.5), slotted(G.X_SR, G.X_SR + 1.5, Ro - 2.0, Rb + 0.5)]), 'GFRP',
    'insulating end plates 1.5 mm (glass-epoxy EP GC 203), slotted like the core, protect the coils at the slot exits', 'make: CNC milled / waterjet from EP GC 203 sheet')
rr = G.conductor_radii()
cond = [rot_slot(box(G.X_SF - 1.5, G.X_SR + 1.5, -G.WIND['ins_w'] / 2, G.WIND['ins_w'] / 2, r_c - G.WIND['ins_h'] / 2, r_c + G.WIND['ins_h'] / 2), k)
        for k in range(EM['slots']) for r_c in rr]
add('E-G204_Winding_Slot_Conductors', Part.makeCompound(cond), 'cu_slot', 'winding, slot parts: 96 compacted rectangular Litz conductors 7.7 x 8.05 insulated (1260 x 0.20 mm, Cu 39.6 mm2) - '
    '24 diamond coils x 2 turns, double layer, pitch 1-11, 2 parallel paths (pole groups), 8 series turns / phase; APA 0.31 liner, APA 0.5 separator',
    'make: rewind shop (form-wound coils, VPI class H)', note='winding spec docs/variant_e/02_generator.md section 6')
ewb = []
for s, x_face in ((-1, G.X_SF - 1.5), (+1, G.X_SR + 1.5)):
    o = G.EW_OVER - 1.5
    prof = [(0.0, 66.6), (0.0, 100.4), (12.0, 101.0), (o - 14.0, 103.5), (o, 97.0), (o, 72.0), (o - 14.0, 67.5), (12.0, 66.6)]
    ewb.append(rev([(x_face + s * u, r) for (u, r) in prof]))
conn = ring(G.X_SF - G.EW_OVER + 10.0, G.X_SF - G.EW_OVER + 24.0, 105.0, 118.0)
leads = [box(-797.0, -793.0, -21.0 + 8.0 * k, -17.0 + 8.0 * k, 117.0, 176.0) for k in range(6)]
add('E-G205_Winding_End_Turns_Leads', fuse_all(ewb + [conn] + leads).removeSplitter(), 'litz_ew', 'end windings (VPI baskets, overhang 88 mm), front connection ring (series / parallel connections, '
    'brazed Cu lugs, glass-tape bound), 6 leads 2 x 70 mm2 silicone (U1 V1 W1 U2 V2 W2) through the lead window; 6 slot + 4 end-winding PT100 embedded', 'make: rewind shop')
wd = [rot_slot(box(G.X_SF - 1.5, G.X_SR + 1.5, -bs / 2 - 0.75, bs / 2 + 0.75, Rb + 1.05, Rb + 2.95).fuse(box(G.X_SF - 1.5, G.X_SR + 1.5, -bs / 2 + 0.05, bs / 2 - 0.05, Rb + 0.3, Rb + 3.75)), k)
      for k in range(EM['slots'])]
add('E-G206_Slot_Wedges_x24', Part.makeCompound(wd), 'GFRP', '24 slot wedges glass-epoxy EP GC 203, dovetail 10.1 x 1.9 in the notches, 273 long, driven in before VPI', 'make: milled strip (wedge profile: Krempel DE / Von Roll CH)')

# ================================================================== ROTOR
sp = []
for (n, x0, x1, r) in R['shaft']:
    if 'taper' in n:
        sp.append(rev([(x0, 0.0), (x0, R['taper']['d_large'] / 2), (x1, R['taper']['d_small'] / 2), (x1, 0.0)]))
    else:
        sp.append(cyl(x0, x1, r))
sp.append(cyl(-822.0, -812.0, 15.0))
shaft = fuse_all(sp).removeSplitter()
shaft = shaft.cut(cyl(-823.0, -808.0, 4.0)).cut(cyl(-380.0, -354.0, 6.0))
add('E-G210_Generator_Shaft', shaft, 'steel', 'generator shaft one piece: magnet body d71 (screen seat 71 +0.10/+0.12), seal lands d50 h6, journals d40 js4, threads M35x1.5 (2), spacer seat d38, '
    'speed-wheel stub d30 k5, rear 1:10 taper d33 -> d30.6 x 24 for the quill hub, M12x1.25 pull-bolt thread, centres',
    'make: 42CrMo4 +QT (Rm 1000) bar d80, CNC turn, grind journals / lands / taper in one setting between centres',
    note='run-out journals <= 2 um, taper / journals coaxial <= 3 um; magnetic particle test; balance as an assembly')
add('E-G211_Cu_Eddy_Screen', ring(R['screen'][0], R['screen'][1], EM['magnet_ID'] / 2 - EM['shield_t'], EM['magnet_ID'] / 2), 'CuCrZr',
    'eddy-current screen sleeve 71/74 x 296 CuCr1Zr (CW106C, 43 MS/m): screens the steel shaft from the 6f / 12f bridge harmonics (950 -> 55 W)',
    'make: CuCr1Zr tube / bar (KME DE, Wieland DE, Aurubis DE), turn; shrink 0.08-0.12 at 220 C, OD finish-ground 74 h5 on the shaft')
mg = []
for k in range(12):
    seg = Part.makeCylinder(EM['magnet_OD'] / 2, R['magnets'][1] - R['magnets'][0], V(R['magnets'][0], 0, 0), XA, 29.4)
    seg = seg.cut(Part.makeCylinder(EM['magnet_ID'] / 2 + 0.03, R['magnets'][1] - R['magnets'][0] + 2, V(R['magnets'][0] - 1, 0, 0), XA))
    seg.rotate(V(0, 0, 0), XA, 360.0 * k / 12 + 0.3)
    mg.append(seg)
add('E-G212_Magnet_Segments_x12', Part.makeCompound(mg), 'SmCo', '12 Sm2Co17 arc segments 30 deg, r 37.03-53.0 x 272, each laminated from 136 slices 2.0 mm (insulating bond), parallel (diametral) '
    'magnetisation of the ring = segment-specific magnetisation angle (marked), bonded on the screen', 'buy: magnet maker to our drawing (order spec section 5)',
    note='VAC (DE) VACOMAX / Shin-Etsu (JP) / Ningbo Yunsheng, Hangzhou Permanent Magnet Group, Xiamen Tungsten (CN)')
er = Part.makeCompound([ring(R['sleeve'][0], R['magnets'][0], EM['magnet_ID'] / 2, EM['magnet_OD'] / 2), ring(R['magnets'][1], R['sleeve'][1], EM['magnet_ID'] / 2, EM['magnet_OD'] / 2)])
for a in polar(12):
    er = er.cut(rad_cyl(R['sleeve'][0] + 6.0, a, 50.0, 54.0, 2.0)).cut(rad_cyl(R['sleeve'][1] - 6.0, a, 50.0, 54.0, 2.0))
add('E-G213_Magnet_End_Rings_x2', er, 'stainless', 'end rings 74/106 x 12 (1.4404, non-magnetic): axial stop of the magnet stack, sleeve support, balance planes (12 x d4 radial correction holes, <= 3 deep)',
    'make: 1.4404 bar d110, CNC turn; OD ground with the magnets (1:500 taper)')
add('E-G214_CFRP_Sleeve', ring(R['sleeve'][0], R['sleeve'][1], EM['magnet_OD'] / 2, EM['rotor_OD'] / 2), 'CFRP', 'retention sleeve 106/120 x 296: T800S-class carbon / high-Tg epoxy (Tg >= 190 C), '
    '88 % hoop + 12 % +/-15 deg, taper press-fit 0.57 mm diametral interference (rotor chilled to -150 C), OD ground 120 h6 after pressing',
    'buy: CFRP winding shop to our spec (eg_sleeve.json) + hot spin test 42,000 rpm', note='Toray T800S / T700S (JP) or Zhongfu Shenying SYT55 (CN) fibre; winding: e+a (CH), BUCCI Composites (IT), CompoTech (CZ)')
add('E-G215_Precision_Locknuts_M35x1.5_x2', Part.makeCompound([ring(R['nut']['x_front'][0], R['nut']['x_front'][1], 17.5, 26.0), ring(R['nut']['x_rear'][0], R['nut']['x_rear'][1], 17.5, 26.0)]),
    'steel', 'precision lock nuts M35x1.5 OD 52 x 12 with 2 radial clamping screws (bearing IR clamp 9 kN, 47 N.m)', 'buy: Spieth MSF 35x1.5 (DE) / SKF KMD 7 (SE) / GMN (DE)', mass=0.24)
sw = ring(-822.0, -812.0, 15.0, 30.0)
for a in polar(4):
    sw = sw.cut(rad_cyl(-818.0, a, 24.0, 31.0, 3.0))
add('E-G216_Speed_Phase_Wheel', sw, 'steel', 'speed / phase wheel d60 x 10, 4 notches (2.33 kHz) + 1 deeper phase notch, on the d30 k5 stub, M8 centre screw', 'make: 1.4057 QT, turn + mill')
add('E-G216b_Speed_Wheel_Screw_M8', screw_ax(-822.0, 0.0, 0.0, 8.0, 12.0, 13.0, 8.0, into=+1), 'steel', 'ISO 4762 M8x16 12.9 + Nord-Lock (speed wheel)', 'buy', mass=0.012)
add('E-G219_Front_IR_Spacer', ring(-800.0, -792.5, 19.0, 26.0), 'steel', 'spacer ring 52/38 x 7.5 between the front bearing IR and the lock nut (ground faces)', 'make: 1.4034 hardened, ground', mass=0.06)
qh = rev([(Q['hub'][0], R['taper']['d_large'] / 2), (Q['hub'][0], 28.0), (Q['hub'][1], 28.0), (Q['hub'][1], 6.5), (R['taper']['x_small'], 6.5),
          (R['taper']['x_small'], R['taper']['d_small'] / 2)])
quill = fuse_all([qh, ring(Q['waist'][0], Q['waist'][1], 9.5, 15.0), ring(Q['socket'][0], Q['socket'][1], 9.5, 28.0).cut(hexprism(-141.0, -116.0, 24.03))]).removeSplitter()
add('E-G217_Quill_Hollow_Taper_AF24', quill, 'steel', 'hollow quill d30/19 x 180 with taper hub (1:10 bore, OD 56) and AF24 socket (rotary-broached, plasma-nitrided), float +/-1 mm on the crowned core hex',
    'make: 34CrNiMo6 QT bar d60, deep-drill d19, turn + grind, lap the taper to the shaft, broach the hex, nitride, shot-peen the waist', note='eg_rotor.json: tau 20.5 MPa rated, 103 MPa at 5 x; taper T_cap 716 N.m')
add('E-G218_Quill_Pull_Bolt_M12x1.25', screw_ax(Q['hub'][1], 0.0, 0.0, 12.0, 24.0, 18.0, 12.0, into=-1), 'steel',
    'quill pull bolt ISO 4762 M12x1.25x25 12.9 (56 kN, 90 N.m with MoS2), head on the hub wall inside the quill bore, tightened through the hollow quill', 'buy (Bossard CH / Wuerth DE)', mass=0.05)
add('E-G220_Bearing_7008E_front', ring(G.X_GF - 7.5, G.X_GF + 7.5, 20.0, 34.0), 'bearing', 'hybrid angular-contact 7008-E (25 deg) P4, locating', 'buy', mass=0.21, note=G.BRG['model'])
add('E-G221_Bearing_7008C_rear', ring(G.X_GR - 7.5, G.X_GR + 7.5, 20.0, 34.0), 'bearing', 'hybrid angular-contact 7008-C (15 deg) P4, floating + 300 N wave spring', 'buy', mass=0.21, note=G.BRG['model'])
cf = rev([(-792.5, 34.0), (-792.5, 42.0), (-768.5, 42.0), (-768.5, 31.5), (-777.5, 31.5), (-777.5, 34.0)])
for (a_, b_) in ((-790.0, -786.4), (-775.0, -771.4)):
    cf = cf.cut(cyl(a_, b_, 43.0, 39.79))
cf = cf.cut(rad_cyl(-785.0, 90.0, 33.0, 43.0, 0.6)).cut(box(-792.6, -768.4, -1.5, 1.5, -43.0, -33.5)).cut(ax_cyl(-771.5, -768.4, 38.0, 315.0, 2.1))
add('E-G222_SFD_Cartridge_Front', cf, '17-4PH', 'front SFD cartridge (locating): OD 84.000 (0/-10) in 84.24 H6 (film 0.12-0.136), bore 68 H4, lip, 2 FKM O-ring grooves, d1.2 jet / feed, drain slot, pin slot',
    'make: 1.4542 (17-4PH) H1025 bar d90, turn + internal / external grinding (same family as the core E-B120)')
cr = rev([(-413.5, 31.5), (-413.5, 42.0), (-386.5, 42.0), (-386.5, 34.0), (-411.0, 34.0), (-411.0, 31.5)])
for (a_, b_) in ((-410.0, -406.4), (-392.0, -388.4)):
    cr = cr.cut(cyl(a_, b_, 43.0, 39.79))
cr = cr.cut(rad_cyl(-400.0, 90.0, 33.0, 43.0, 0.6)).cut(box(-413.6, -386.4, -1.5, 1.5, -43.0, -33.5)).cut(ax_cyl(-413.6, -410.4, 38.0, 315.0, 2.1))
add('E-G223_SFD_Cartridge_Rear', cr, '17-4PH', 'rear SFD cartridge (floating bearing): same OD / O-rings, lip for the wave spring, pin slot', 'make: 1.4542 H1025, turn + grind')
add('E-G224_Wave_Spring_300N', ring(-411.0, -407.5, 31.6, 33.8), 'steel', 'crest-to-crest wave spring 300 N (rear outer ring preload)', 'buy: Lesjofors (SE) / Scherdel (DE) / TFC (UK)', mass=0.01)
add('E-G226_Front_Cartridge_Shim', ring(-768.5, -767.5, 34.5, 42.0).cut(ax_cyl(-768.6, -767.4, 38.0, 315.0, 2.1)), 'stainless',
    'ground shim 84/69 x 0.5-2.0 (set at assembly): axial rotor position (magnet centre +/-0.3 mm to the stack)', 'make: 1.4034 hardened, surface-ground', mass=0.01)
add('E-G227_Rear_Spacer_Tube', ring(-386.5, -362.0, 30.0, 42.0), 'Al', 'rear spacer tube 84/60 x 24.5: clamps the rear cartridge between the hub shoulder and the rear seal cap', 'make: 6082-T6, turn')

# ================================================================== END BELLS, CAPS, HOOD, GUARD
feb = rev([(fx0, 42.12), (fx0, EB['flange_r']), (fx1, EB['flange_r']), (fx1, 145.0), (fx1 + EB['spigot_L'], 145.0), (fx1 + EB['spigot_L'], 135.0), (fx1, 135.0), (fx1, EB['hub_r']),
           (EB['front']['hub_nose'], EB['hub_r']), (EB['front']['hub_nose'], 25.3), (-767.5, 25.3), (-767.5, 42.12)])
feb = feb.cut(cyl(fx1 + 4.0, fx1 + 8.8, 146.0, 142.15))
for a in B16:
    feb = feb.cut(ax_cyl(fx0 - 1, fx1 + 1, 155.0, a, 5.5))
for a in DOW:
    feb = feb.cut(ax_cyl(fx0 - 1, fx1 + 1, 155.0, a, 4.0))
for a in JB:
    feb = feb.cut(ax_cyl(fx0 - 1, fx1 + 1, 155.0, a, 4.25))
for a in polar(EB['air_holes']['n'], 15.0):
    feb = feb.cut(ax_cyl(fx0 - 1, fx1 + 1, EB['air_holes']['r'], a, EB['air_holes']['d'] / 2))
for a in polar(6, 30.0):
    feb = feb.cut(ax_cyl(fx0 - 1, fx0 + 10.0, 47.0, a, 0.565 * 6))
for a in polar(8, 22.5):
    feb = feb.cut(ax_cyl(fx0 - 1, fx0 + 7.0, G.HOOD['screw_r'], a, 0.565 * 6))
for a in (45.0, 225.0):
    feb = feb.cut(ax_cyl(fx0 - 1, fx0 + 10.0, IR_R, a, 0.565 * 12)).cut(ax_cyl(fx0 + 9.0, fx1 + 1, IR_R, a, 4.0))
feb = feb.cut(rad_cyl(fx0 + 7.0, 90.0, 46.5, EB['flange_r'] + 1, 2.0)).cut(ax_cyl(fx0 + 5.0, -790.0, 46.5, 90.0, 2.0)).cut(rad_cyl(-790.0, 90.0, 41.0, 48.0, 1.0))
feb = feb.cut(rad_cyl(fx0 + 7.0, 270.0, 46.0, EB['flange_r'] + 1, 4.0)).cut(ax_cyl(fx0 + 3.0, -776.0, 46.0, 270.0, 4.0)).cut(rad_cyl(-780.0, 270.0, 41.0, 50.0, 3.0))
feb = feb.cut(ax_cyl(-767.6, -763.0, 38.0, 315.0, 2.0))
add('E-G230_Front_End_Bell', feb, 'Al', 'front end bell: disk + re-entrant hub (SFD bore 84.24 H6, 5-tooth labyrinth on the d50 land), spigot 290 g6 + FKM O-ring, 16 x d11 + 2 dowels + 2 x M10 jacking, '
    '12 x d22 cooling-air inlets, 2 IR-pyrometer ports M12x1, oil feed (top, M10x1 ISO 6149) -> axial gallery -> jet, oil drain (bottom, G3/8), HELICOILs for cap / hood',
    'make: 6082-T6 forged disc d340 x 110, CNC turning (spigot + hub bore one clamping) + 5-axis drilling', note='hub bore 84.24 H6 coaxial to the spigot <= 0.01; labyrinth teeth tips d50.60')
reb = rev([(rx1, 42.12), (rx1, EB['flange_r']), (rx0, EB['flange_r']), (rx0, 143.0), (rx0 - EB['spigot_L'], 143.0), (rx0 - EB['spigot_L'], 133.0), (rx0, 133.0), (rx0, EB['hub_r']),
           (EB['rear']['hub_nose'], EB['hub_r']), (EB['rear']['hub_nose'], 25.3), (-413.5, 25.3), (-413.5, 42.12)])
reb = reb.cut(cyl(rx0 - 8.8, rx0 - 4.0, 144.0, 140.15))
for a in B16:
    reb = reb.cut(ax_cyl(rx0 - 1, rx1 + 1, 155.0, a, 5.5))
for a in DOW:
    reb = reb.cut(ax_cyl(rx0 - 1, rx1 + 1, 155.0, a, 4.0))
for a in JB:
    reb = reb.cut(ax_cyl(rx0 - 1, rx1 + 1, 155.0, a, 4.25))
for a in polar(EB['air_holes']['n'], 15.0):
    reb = reb.cut(ax_cyl(rx0 - 1, rx1 + 1, EB['air_holes']['r'], a, EB['air_holes']['d'] / 2))
for a in polar(6, 30.0):
    reb = reb.cut(ax_cyl(rx1 - 10.0, rx1 + 1, 47.0, a, 0.565 * 6))
for a in (45.0, 225.0):
    reb = reb.cut(ax_cyl(rx1 - 10.0, rx1 + 1, IR_R, a, 0.565 * 12)).cut(ax_cyl(rx0 - 1, rx1 - 9.0, IR_R, a, 4.0))
reb = reb.cut(rad_cyl(rx1 - 7.0, 90.0, 46.5, EB['flange_r'] + 1, 2.0)).cut(ax_cyl(-405.0, rx1 - 5.0, 46.5, 90.0, 2.0)).cut(rad_cyl(-405.0, 90.0, 41.0, 48.0, 1.0))
reb = reb.cut(rad_cyl(rx1 - 7.0, 270.0, 46.0, EB['flange_r'] + 1, 4.0)).cut(ax_cyl(-395.0, rx1 - 3.0, 46.0, 270.0, 4.0)).cut(rad_cyl(-395.0, 270.0, 41.0, 50.0, 3.0))
reb = reb.cut(ax_cyl(-417.0, -413.4, 38.0, 315.0, 2.0))
add('E-G231_Rear_End_Bell', reb, 'Al', 'rear end bell: disk + re-entrant hub (SFD bore 84.24 H6 for the floating bearing, labyrinth nose), spigot 286 g6 + O-ring, 16 x d11 + 2 dowels + 2 x M10 jacking, '
    '12 x d22 cooling-air outlets to the plenum, 2 IR ports, oil feed / drain galleries, 6 x HELICOIL M6 for the seal cap + guard', 'make: 6082-T6 forged disc d340 x 110, CNC turning + 5-axis drilling')
fcap = rev([(-851.5, 8.0), (-851.5, 51.0), (fx0, 51.0), (fx0, 42.1), (-792.5, 42.1), (-792.5, 31.0), (fx0, 31.0), (fx0, 8.0)])
for a in polar(6, 30.0):
    fcap = fcap.cut(ax_cyl(-852.5, fx0 + 1, 47.0, a, 3.3))
for a in (90.0, 270.0):
    fcap = fcap.cut(ax_cyl(-852.5, fx0 + 1, 24.0, a, 6.0))
fcap = fcap.cut(cyl(fx0 + 2.5, fx0 + 4.9, 42.2, 40.6))
add('E-G232_Front_Bearing_Cap', fcap, 'Al', 'front bearing cap: spigot clamps the front cartridge + bearing OR, covers nut / speed wheel, 2 axial speed-probe ports M12x1, d16 turning access, spigot O-ring 80 x 1.78, 6 x M6',
    'make: 6082-T6 bar d110 x 70, CNC turning')
rcap = rev([(-362.0, 28.3), (-362.0, 42.1), (rx1, 42.1), (rx1, 51.0), (rx1 + 8.0, 51.0), (rx1 + 8.0, 28.3)])
for k in range(5):
    rcap = rcap.cut(cyl(-358.0 + 3.0 * k, -357.0 + 3.0 * k, 29.5, 28.0))
for a in polar(6, 30.0):
    rcap = rcap.cut(ax_cyl(rx1 - 1, rx1 + 9.0, 47.0, a, 3.3))
rcap = rcap.cut(cyl(rx1 - 4.9, rx1 - 2.5, 42.2, 40.6))
add('E-G233_Rear_Seal_Cap', rcap, 'bronze', 'rear seal cap: spigot clamps spacer + rear cartridge, 5-groove labyrinth on the quill hub d56 (0.30 radial), flange shared with the guard (6 x M6x30), spigot O-ring 80 x 1.78',
    'make: CuSn12 (rub-tolerant), CNC turning')
hood = rev([(HX0, G.HOOD['r_in']), (HX0, G.HOOD['r']), (HX1, G.HOOD['r']), (HX1, G.HOOD['r'] - 6.0), (HX0 + 4.0, G.HOOD['r'] - 6.0), (HX0 + 4.0, G.HOOD['r_in'] + 4.0),
            (HX1, G.HOOD['r_in'] + 4.0), (HX1, G.HOOD['r_in'])])
hood = fuse_all([hood] + [ax_cyl(HX0 + 4.0, HX1, G.HOOD['screw_r'], a, 7.0) for a in polar(8, 22.5)] + [Part.makeCylinder(42.0, 26.0, V(HX0 - 25.5, 0.0, 100.0), XA)]).removeSplitter()
hood = hood.cut(Part.makeCylinder(38.0, 31.0, V(HX0 - 26.0, 0.0, 100.0), XA))
for a in polar(8, 22.5):
    hood = hood.cut(ax_cyl(HX0 - 1, HX1 + 1, G.HOOD['screw_r'], a, 3.3))
add('E-G234_Air_Inlet_Hood', hood, 'Al', 'cooling-air inlet hood: annular chamber r 66-138 over the 12 front air inlets, axial DN80 spigot, 8 internal bosses, 8 x M6x45 to the front end bell, EPDM foam gasket',
    'make: 6082-T6 turned from bar d290 (or spun 4 mm + welded bosses)')
gt = fuse_all([ring(rx1 + 8.0, rx1 + 18.0, 33.0, 51.0), ring(rx1 + 18.0, G.GUARD['x'][1], G.GUARD['ID'] / 2, G.GUARD['OD'] / 2)]).removeSplitter()
for a in polar(6, 30.0):
    gt = gt.cut(ax_cyl(rx1 + 7.0, rx1 + 19.0, 47.0, a, 3.3))
for a in polar(G.GUARD['vents'], 45.0):
    v = box(rx1 + 25.0, rx1 + 65.0, -7.5, 7.5, 30.0, 40.0); v.rotate(V(0, 0, 0), XA, a - 90.0); gt = gt.cut(v)
add('E-G235_Quill_Guard_Tube', gt, 'stainless', 'stationary quill guard d76/66 to x -98 (continues the impeller hub line) with flange on the rear seal cap and 4 vent slots 40 x 15 '
    '(guard interior at plenum pressure: no compressor-eye suction on the rear seal)', 'make: 1.4301 tube 76.1 x 5 + turned flange, TIG')

# ================================================================== FASTENERS, INSERTS, DOWELS, O-RINGS
add('E-G270_Screws_ISO4762_M10x35_x32', Part.makeCompound([screw_ax(fx0, 155.0, a, 10.0, 34.0, 16.0, 10.0, +1) for a in B16] + [screw_ax(rx1, 155.0, a, 10.0, 34.0, 16.0, 10.0, -1) for a in B16]),
    'stainless', 'ISO 4762 M10x35 A4-80, end bells -> housing (2 x 16), 29 N.m, Loctite 243', 'buy (Bossard CH / Wuerth DE / Boellhoff DE)', mass=32 * 0.030)
add('E-G271_HELICOIL_M10_1.5D_x32', Part.makeCompound([coil_ax(X0, 155.0, a, 10.0, 15.0, +1) for a in B16] + [coil_ax(X1, 155.0, a, 10.0, 15.0, -1) for a in B16]),
    'stainless', 'HELICOIL plus M10 x 1.5D 1.4301 in the housing end faces', 'buy (Boellhoff DE)', mass=32 * 0.003)
add('E-G272_Dowels_ISO8734_8x24_x4', Part.makeCompound([ax_cyl(X0 - 8.0, X0 + 16.0, 155.0, a, 3.98) for a in DOW] + [ax_cyl(X1 - 16.0, X1 + 8.0, 155.0, a, 3.98) for a in DOW]),
    'steel', 'ISO 8734 8 m6 x 24 (1.4034 hardened) end bell / housing location', 'buy (Bossard CH / Halder DE)', mass=4 * 0.009)
add('E-G273_Screws_M6x16_front_cap_x6', Part.makeCompound([screw_ax(-851.5, 47.0, a, 6.0, 22.0, 10.0, 6.0, +1) for a in polar(6, 30.0)]), 'stainless',
    'ISO 4762 M6x22 A4-80 (front bearing cap), 6.0 N.m, HELICOIL M6 x 1.5D', 'buy', mass=6 * 0.007)
add('E-G274_Screws_M6x30_rear_cap_guard_x6', Part.makeCompound([screw_ax(rx1 + 18.0, 47.0, a, 6.0, 26.0, 10.0, 6.0, -1) for a in polar(6, 30.0)]), 'stainless',
    'ISO 4762 M6x30 A4-80 (guard flange + rear seal cap -> rear hub), 6.0 N.m, HELICOIL M6 x 1.5D', 'buy', mass=6 * 0.009)
add('E-G276_Screws_M6x45_hood_x8', Part.makeCompound([screw_ax(HX0, G.HOOD['screw_r'], a, 6.0, 46.0, 10.0, 6.0, +1) for a in polar(8, 22.5)]), 'stainless',
    'ISO 4762 M6x45 A4-80 (hood through its bosses into the front end bell), 4.5 N.m, HELICOIL M6 x 1D', 'buy', mass=8 * 0.012)
add('E-G280_O-rings_Jacket_280x3.55_EPDM_x4', Part.makeCompound([ring(a_ + 0.6, b_ - 0.6, 142.2, 145.0) for (a_, b_) in ORG]), 'EPDM',
    'ISO 3601-1 280 x 3.55 EPDM 70 (glycol), jacket lands, squeeze 19.7 %, stretch 1.5 %', 'buy (Freudenberg DE / Trelleborg SE / COG DE)', mass=4 * 0.012)
add('E-G281_O-rings_Spigots_FKM_x2', Part.makeCompound([ring(fx1 + 4.6, fx1 + 8.2, 142.2, 145.0), ring(rx0 - 8.2, rx0 - 4.6, 140.2, 143.0)]), 'FKM',
    'ISO 3601-1 280 x 3.55 (front) / 275 x 3.55 (rear) FKM 75, end-bell spigots', 'buy', mass=2 * 0.015)
add('E-G282_O-rings_SFD_77.5x2.65_FKM_x4', Part.makeCompound([ring(a_ + 0.5, b_ - 0.5, 39.85, 42.12) for (a_, b_) in ((-790.0, -786.4), (-775.0, -771.4), (-410.0, -406.4), (-392.0, -388.4))]),
    'FKM', 'ISO 3601-1 77.5 x 2.65 FKM 75, SFD centring (squeeze 12 %, ~3 N/um per cartridge - measure)', 'buy', mass=4 * 0.002)
add('E-G283_O-rings_Caps_80x1.78_FKM_x2', Part.makeCompound([ring(fx0 + 2.7, fx0 + 4.7, 40.65, 42.12), ring(rx1 - 4.7, rx1 - 2.7, 40.65, 42.12)]), 'FKM',
    'ISO 3601-1 80 x 1.78 FKM 75, radial on the front bearing cap / rear seal cap spigots (squeeze 14.6 %, stretch 1.5 %)', 'buy', mass=0.002)
add('E-G284_Cartridge_Pins_ISO8734_4x10_x2', Part.makeCompound([ax_cyl(-771.0, -764.0, 38.0, 315.0, 1.98), ax_cyl(-417.0, -410.5, 38.0, 315.0, 1.98)]), 'steel',
    'ISO 8734 4 m6 x 10 anti-rotation pins (cartridges)', 'buy', mass=0.002)

# ================================================================== TERMINAL BOX
tx0, tx1 = G.TBOX['x']; ty0, ty1 = G.TBOX['y']; tz1 = G.TBOX['z'][1]
tb = box(tx0, tx1, ty0, ty1, 140.0, tz1 - 6.0).cut(cyl(tx0 - 1, tx1 + 1, H['r_out']))
tb = tb.cut(box(tx0 + 8.0, tx1 - 8.0, ty0 + 8.0, ty1 - 8.0, 140.0, tz1).cut(cyl(tx0, tx1, H['r_out'] + 10.0)))
tb = tb.cut(box(w0, w1, -wh, wh, 130.0, 190.0))
for xb_, a in TBS:
    tb = tb.cut(rad_cyl(xb_, a, 160.0, 180.0, 4.5))
for k in range(3):
    tb = tb.cut(Part.makeCylinder(20.0, 10.0, V(tx0 + 35.0 + 30.0 * k, ty1 - 9.0, 236.0), V(0, 1, 0)))
add('E-G240_Terminal_Box', tb, 'Al', 'terminal box 130 x 200 x 135 with a 10 mm saddle floor (r 165), 3 x M40 EMC glands (+y) for 6 x 95 mm2 cables, 2 x M25 signal glands, star bar, IP65',
    'make: 6082-T6 block, 3-axis milling (saddle face by ball-end)', note='mounted on 4 HELICOIL M8 in the housing; flat silicone gasket')
add('E-G241_Terminal_Box_Lid', box(tx0, tx1, ty0, ty1, tz1 - 6.0, tz1), 'Al', 'terminal box lid 6 mm, 8 x M5, IP65 gasket', 'make: 6082 plate, laser + mill')
tbk = box(tx0 + 15.0, tx1 - 15.0, -60.0, 60.0, 178.0, 198.0)
studs = [Part.makeCylinder(6.0, 40.0, V(tx0 + 28.0 + 16.0 * k, (-30.0 if k % 2 else 30.0), 198.0), V(0, 0, 1)) for k in range(6)]
add('E-G242_PEEK_Terminal_Block_6_Studs', fuse_all([tbk] + studs).removeSplitter(), 'PEEK', 'PEEK terminal block 100 x 120 x 20 with 6 brass studs M12 (U1 V1 W1 / U2 V2 W2), star bar on U2 V2 W2, creepage >= 12.5 mm',
    'make: PEEK plate milled + CuZn39Pb3 studs')
add('E-G243_Screws_M8_terminal_box_x4', Part.makeCompound([rad_screw(xb_, a, 175.0, 8.0, 22.0, 13.0, 8.0) for xb_, a in TBS]), 'stainless',
    'ISO 4762 M8x25 A4-80, terminal box -> housing, 14 N.m, HELICOIL M8 x 1.5D', 'buy', mass=4 * 0.014)

# ================================================================== COOLING AIR, SENSORS, FITTINGS
bx0, bx1 = G.BLOWER['x']; by0, by1 = G.BLOWER['y']; bz0, bz1 = G.BLOWER['z']
bl = box(bx0, bx1 - 15.0, by0, by1, bz0, bz1).fuse(Part.makeCylinder(42.0, 15.0, V(bx1 - 15.0, 0.0, G.BLOWER['outlet_z']), XA))
add('E-G250_Cooling_Air_Blower_EC', bl, 'steel', 'EC high-pressure radial blower 160 m3/h at 4 kPa, 0.55 kW, integrated EC drive 0-10 V (speed = rotor-temperature actuator), outlet DN80 axial',
    'buy: ebm-papst (DE) / Elektror (DE) / Becker (DE) / FPZ (IT)', mass=18.0)
stand = box(bx0 + 15.0, bx1 - 30.0, -110.0, 110.0, -547.0, bz0).cut(box(bx0 + 23.0, bx1 - 38.0, -102.0, 102.0, -548.0, bz0 + 1.0))
add('E-G250b_Blower_Stand', stand, 'steel', 'blower stand (S355 angle frame 40 x 4) on the saddle base beam, 4 x M8', 'make: S355, MAG', mass=6.0)
fil = Part.makeCylinder(100.0, 230.0, V(bx0 - 230.0, 0.0, 0.0), XA).cut(Part.makeCylinder(60.0, 232.0, V(bx0 - 231.0, 0.0, 0.0), XA))
add('E-G251_F9_Filter_Cartridge', fil, 'filter', 'ePM1 80 % (F9) filter cartridge d200 x 230 on the blower inlet (plenum air already G4 + F7), dp switch', 'buy: Camfil (SE) / Freudenberg Viledon (DE) / MANN+HUMMEL (DE)', mass=1.2)
add('E-G252_Air_Bellows_DN80', Part.makeCylinder(42.0, 10.0, V(HX0 - 35.5, 0.0, 100.0), XA).cut(Part.makeCylinder(38.0, 12.0, V(HX0 - 36.5, 0.0, 100.0), XA)),
    'stainless', 'DN80 stainless bellows + 2 hose clamps (blower -> hood, decouples blower vibration)', 'buy: Witzenmann (DE) / BOA (DE)', mass=0.5)
irs = [ax_cyl(fx0 - 45.0, fx0, IR_R, a, 6.0) for a in (45.0, 225.0)] + [ax_cyl(rx1, rx1 + 45.0, IR_R, a, 6.0) for a in (45.0, 225.0)]
add('E-G253_IR_Pyrometers_x4', Part.makeCompound(irs), 'stainless', '4 IR pyrometers 8-14 um (2 per end, 1 used + 1 spare) on the CFRP sleeve ends, M12x1 heads, 4-20 mA', 'buy: Optris CSmicro LT (DE) / Calex PyroMini (UK)', mass=4 * 0.05)
add('E-G254_Speed_Probes_x2', Part.makeCompound([ax_cyl(-890.0, -823.5, 24.0, a, 5.9) for a in (90.0, 270.0)]), 'stainless',
    '2 eddy-current speed + phase probes M12x1 (axial, gap 1.5 mm to the speed wheel)', 'buy: Jaquet (CH) DSE / Braun (DE) A5S', mass=2 * 0.06)
add('E-G255_Accelerometers_x2', Part.makeCompound([rad_cyl(fx0 + 5.0, 0.0, EB['flange_r'], EB['flange_r'] + 40.0, 11.0), rad_cyl(rx1 - 5.0, 0.0, EB['flange_r'], EB['flange_r'] + 40.0, 11.0)]),
    'stainless', '2 IEPE accelerometers 100 mV/g on the end-bell rims (+y), M6 studs', 'buy: Bruel & Kjaer (DK) / Hansford (UK) / MMF (DE)', mass=2 * 0.05)
fit = [rad_cyl(xg_, 0.0, 178.0, 214.0, 13.0) for xg_ in (-740.0, -445.0)] + [rad_cyl(xl, LEAK_A, 172.0, 190.0, 6.0) for xl in (-752.0, -432.5)]
fit += [rad_cyl(fx0 + 7.0, 90.0, EB['flange_r'], EB['flange_r'] + 30.0, 8.0), rad_cyl(rx1 - 7.0, 90.0, EB['flange_r'], EB['flange_r'] + 30.0, 8.0),
        rad_cyl(fx0 + 7.0, 270.0, EB['flange_r'], EB['flange_r'] + 25.0, 11.0), rad_cyl(rx1 - 7.0, 270.0, EB['flange_r'], EB['flange_r'] + 25.0, 11.0)]
add('E-G256_Fittings_Glycol_Oil_x8', Part.makeCompound(fit), 'stainless', 'fittings: 2 x G3/4 glycol (ISO 1179-2 ED), 2 x G1/8 leak-off to the float switch, 2 x M10x1 oil feed (ISO 6149-3), 2 x G3/8 oil drain',
    'buy: Hydac (DE) / Voss (DE) / Ham-Let (IL)', mass=1.2)

# ================================================================== SUPPORTS
sad, straps = [], []
hw_, sw_ = G.SADDLE['w'] / 2, G.SADDLE['strap_w'] / 2
SBOLT = [(xs, yo) for xs in G.SADDLE['x'] for yo in (-60.0, 60.0)]
for xs in G.SADDLE['x']:
    s = box(xs - hw_, xs + hw_, -150.0, 150.0, -547.0, -120.0).cut(cyl(xs - hw_ - 1, xs + hw_ + 1, H['r_out']))
    s = s.cut(box(xs - hw_ + 8.0, xs + hw_ - 8.0, -138.0, 138.0, -535.0, -200.0))
    for (bx_, by_) in SBOLT:
        s = s.cut(Part.makeCylinder(8.75, 20.0, V(bx_, by_, -550.0), V(0, 0, 1)))
    sad.append(s)
    st = cyl(xs - sw_, xs + sw_, H['r_out'] + 6.0, H['r_out']).common(box(xs - sw_ - 5, xs + sw_ + 5, -200.0, 200.0, -95.0, 200.0))
    st = st.fuse(box(xs - sw_, xs + sw_, 135.0, 175.0, -101.0, -94.9)).fuse(box(xs - sw_, xs + sw_, -175.0, -135.0, -101.0, -94.9))
    straps.append(st.cut(cyl(xs - sw_ - 1, xs + sw_ + 1, H['r_out'])).removeSplitter())
add('E-G260_Saddles_x2', fuse_all(sad), 'steel', '2 saddles (S355 plate welded, cradle r 165 machined, shim packs under the feet, x / y jack bolts M16, x-slots for the 150 mm slide-out)', 'make: S355J2 plate 12/15, MAG, machine cradle + feet')
add('E-G261_Saddle_Clamp_Straps_x2', fuse_all(straps), 'steel', '2 clamp straps 50 x 6 (S355) with ears, 2 x M12 each (strap preload limited: Al housing)', 'make: S355 strip, rolled + welded ears', mass=2 * 1.6)
bb = box(G.SADDLE['base'][0], G.SADDLE['base'][1], -100.0, 100.0, -647.0, -547.0).cut(box(G.SADDLE['base'][0] - 1, G.SADDLE['base'][1] + 1, -93.7, 93.7, -640.7, -553.3))
for (bx_, by_) in SBOLT:
    bb = bb.cut(Part.makeCylinder(8.75, 20.0, V(bx_, by_, -560.0), V(0, 0, 1)))
add('E-G262_Saddle_Base_Beam', bb, 'steel', 'saddle base beam RHS 200 x 100 x 6.3 (S355J2H) x 970 on the plenum floor, bolted through the floor onto the frame cross members x -1050 / -600 / -200, carries saddles + blower',
    'make: RHS cut + plates, MAG, galvanised')
sb = [Part.makeCylinder(7.9, 26.0, V(bx_, by_, -561.0), V(0, 0, 1)).fuse(Part.makeCylinder(13.0, 10.0, V(bx_, by_, -535.0), V(0, 0, 1))) for (bx_, by_) in SBOLT]
add('E-G263_Saddle_Bolts_M16_x4', Part.makeCompound(sb), 'steel', 'ISO 4017 M16x40 8.8 + nuts inside the RHS (hand holes) + Nord-Lock (saddles -> base beam, 2 per saddle at y +/-60), 156 N.m', 'buy', mass=4 * 0.16)

P.save(dict(layout='cad/variant_e/eg_layout.py', analyses=['sim/variant_e/eg_em.json', 'eg_sleeve.json', 'eg_thermal.json', 'eg_rotor.json', 'eg_joints.json'], detailed=True))
