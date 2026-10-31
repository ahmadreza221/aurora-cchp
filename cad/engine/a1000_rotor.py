"""AURORA-1000 rotor stack and bearings (rotor rev 1): geometry of the shaft parts, joints and bearing cartridges.

The two cast MAR-M247 blisks are bore-less: a bore of 50 mm doubles the centre stress (disc FEA: 771-919 MPa at 15,000 rpm,
trip yield margin 0.75-0.90, LCF < 1,000 starts; sim/engine/a1000_rotor_stack.py --bore-study), so no tie bolt can pass
through the turbine. The stack is therefore built in two parts:
  compressor   front stub (journal 1 + integral thrust collar) - impeller 1 - spacer - impeller 2 - drum, clamped by one
               central IN718 tie bolt (M42) from a nut in the front stub to a threaded bulkhead in the drum; Gleason-type
               curvic couplings (30 deg) centre the parts and carry the torque
  turbine      each blisk gets short integral cast arms on both hub faces (r 58-66) ending in a flange (r 58-92, 9 mm);
               the flanges are joined by 16 x M10 IN718 studs through bolted curvic couplings (teeth r 62-90, the stud holes
               pass through the teeth, so the clamp acts symmetrically on the teeth): drum - R1, R1 - R2, R2 - rear stub.
               The studs sit in the wrought part (drum, rear stub) or, at R1 - R2, in Heli-Coil inserts in the R2 flange; the
               nuts are run down in the 13 mm cavity behind each flange with radial access between the blade rows, so the
               rotor is built and balanced outside the engine and the NGV rings are split in two halves (horizontally split
               turbine casing)
               rev 6 (R1 - NGV2 gap +25 mm, docs/08 sec. 12.4.2): the blisks sit 25 mm further apart. The cast arms stay as
               rev 1 and an IN718 spacer ring (RT-107) with a curvic on each face fills the R1 - R2 joint; the 16 studs of
               that joint pass through it (25 mm longer). The ring carries the 4 knife edges of the interstage seal under
               NGV2. Chosen over 12.5 mm longer cast arms: the blisk castings, their disc FEA and the cyclic / forced-response
               models stay as they are; the ring section (r 60-88) is ~5 x stiffer in bending than the thin arm tube
               (r 58-66) it replaces; the seal fins are on a wrought, replaceable part; and over the added length studs
               and ring are both IN718 (no expansion mismatch). Cost: one more curvic interface and ~1.7 kg more than arms.
Bearings: tilting-pad journals (5 pads, load between pads) in integral spring squeeze-film damper rings (ISFD; phase 4:
4 hairpin springs + 4 damper pads, docs/08 sec. 21),
double-acting tilting-pad thrust bearing on the integral collar, at the cold end.
               rotor rev 1.3 (bearing losses, docs/08 sec. 13.10): journals D100 x L45 -> D90 x L36, thrust pads r 56-78 -> 52-68 with
               8 pads on the loaded (aft) side and 4 on the inactive (forward) side, collar r 82 -> 72; the stub and rear-stub
               lands step down with the journal (front seal r 43, neck r 44.5, seal runner r 41, collar shoulders r 48).
               Bearing + seal losses 28.6 -> 15.9 kW at the same film and critical-speed margins.
               phase 5 (transient thermal-structural, docs/08 sec. 22): R1 - R2 studs, nuts and spacer ring in Waspaloy at
               24 kN (the joint runs at ~710 C), TBC on the R1 platform, start / stop rule; no geometry change. Open: the
               blisk arm-root fillets reach only ~1,500-4,700 starts in transients (sec. 22.12, disc redesign proposed).

Frame: rotor frame of sim/engine/a1000_rotordynamics.py, mm, x = engine axis from the gearbox coupling face, r = radius.
Run:   freecadcmd -c "import sys; sys.argv=['a1000_rotor.py','--cad']; exec(open('cad/engine/a1000_rotor.py').read())"
       -> cad_out/engine/A1000_rotor/*.step, fusion/A1000_rotor/*.step + parts.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'sim', 'engine'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_rotordynamics as RD                               # noqa: E402  (layout; a1000_turbine as RD.A)
sys.argv = _argv
A = RD.A
_R = RD.rotor('A')
X_I1 = (205.0, _R['discs']['impeller1']['L'] + 205.0)
X_I2 = (X_I1[1] + 50.0, X_I1[1] + 50.0 + _R['discs']['impeller2']['L'])
HUB = dict(R1=_R['discs']['blisk1']['hub'], R2=_R['discs']['blisk2']['hub'])        # blisk hub faces (x front, x aft)
X_OFF = HUB['R1'][0] - (0.5 * (A.X_LE['R1'] + A.X_TE['R1']) - A.DISC['R1']['hub_w'] / 2)

# ------------------------------------------------------------------------------------------------ hot joints (cast arms)
ARM = dict(ri=58.0, ro=66.0, cav=13.0, tf=9.0, rf=92.0)          # arm bore / OD, cavity length, flange thickness / OD
STUD = dict(n=16, d=10.0, r=76.0, hole=10.5, nut_h=6.0, nut_af=14.0, pre_kN=27.0)   # M10x1.25 MJ, IN718 (R1 - R2: STUD_R12)
# phase 5 (docs/08 sec. 22): the unpurged interstage cavity runs the R1 - R2 joint at ~710 C, over the 650 C IN718 bolting
# limit -> studs, nuts and the RT-107 spacer ring in Waspaloy, lower preload, 50 % relaxation allowance (re-torque at the
# hot-section inspection), Heli-Coils in the R2 flange in Nimonic 90
STUD_R12 = dict(mat='Waspaloy', pre_kN=24.0, relax=0.50, insert='Nimonic 90 Heli-Coil')
CURVIC_HOT = dict(ri=62.0, ro=90.0, N=48, phi=30.0, h=2.6)        # bolted curvic on every hot flange face
# phase 5: thermal barrier on the R1 platform and blade-root fillets (rim 795 -> 770 C, platform LCF 6,000 -> 15,000 starts)
TBC_R1 = dict(t=0.4, system='MCrAlY bond coat + 7YSZ (as NGV1)', area='R1 platform top and blade-root fillets')


def arm_x(row, side):
    """(hub face x, joint face x) of a blisk arm: side 'f' (forward) or 'a' (aft)"""
    xf, xa = HUB[row]
    if side == 'f': return xf, xf - ARM['cav'] - ARM['tf']
    return xa, xa + ARM['cav'] + ARM['tf']


X_J = dict(drum_R1=arm_x('R1', 'f')[1], R1_spc=arm_x('R1', 'a')[1], spc_R2=arm_x('R2', 'f')[1], R2_stub=arm_x('R2', 'a')[1])
# rev 6: R1 - R2 spacer ring between the R1 aft and the R2 forward arm flanges (curvic both faces, 4 seal fins); phase 5:
# Waspaloy (was IN718), the same alloy as its studs
TSPC = dict(ri=60.0, ro=88.0, land=5.0, n_fin=4, fin_pitch=3.0, r_fin=92.3, mat='Waspaloy')
L_TSPC = X_J['spc_R2'] - X_J['R1_spc']
# stud sets of the hot joints: (stud x0, x1, nut face x, nut direction); R1 - R2: from the Heli-Coil inserts in the R2
# flange forward through the spacer and the R1 flange, nut in the R1 aft cavity
STUD_SETS = {'drum - R1': (X_J['drum_R1'] - ARM['tf'], X_J['drum_R1'] + ARM['tf'] + STUD['nut_h'] + 2, X_J['drum_R1'] + ARM['tf'], +1),
             'R1 - R2': (X_J['R1_spc'] - ARM['tf'] - STUD['nut_h'] - 2, X_J['spc_R2'] + ARM['tf'], X_J['R1_spc'] - ARM['tf'], -1),
             'R2 - rear stub': (X_J['R2_stub'] - ARM['tf'] - STUD['nut_h'] - 2, X_J['R2_stub'] + ARM['tf'], X_J['R2_stub'] - ARM['tf'], -1)}


def disc_profile_arms(row):
    """cast blisk meridional (x, r) outline in the rotor frame: rev 5 bore-less disc + forward / aft arms and flanges"""
    q = A.DISC[row]
    rh = A.row_radius(row, 0.0); x0, x1 = A.X_LE[row] - A.PLAT_OVH, A.X_TE[row] + A.PLAT_OVH; xm = 0.5 * (x0 + x1)
    r_rim = rh - q['rim_d']; tr, th, hw = q['t_rim'] / 2, q['t_hub'] / 2, q['hub_w'] / 2
    o = X_OFF; ri, ro, rf, c, t = ARM['ri'], ARM['ro'], ARM['rf'], ARM['cav'], ARM['tf']
    xa, xf = xm + hw + o, xm - hw + o
    xj_a = X_J['R1_spc'] if row == 'R1' else X_J['R2_stub']
    xj_f = X_J['drum_R1'] if row == 'R1' else X_J['spc_R2']
    poly = [(x0 + o, rh), (x1 + o, rh), (x1 + o, r_rim + 6), (xm + tr + o, r_rim - 4), (xm + th + o, q['r_web_in']),
            (xa, q['r_boss']),
            (xa, ro), (xa + c, ro), (xa + c, rf), (xj_a, rf), (xj_a, ri), (xa, ri),            # aft arm + flange
            (xa, 0.0), (xf, 0.0),
            (xf, ri), (xj_f, ri), (xj_f, rf), (xf - c, rf), (xf - c, ro), (xf, ro),            # forward arm + flange
            (xf, q['r_boss']), (xm - th + o, q['r_web_in']), (xm - tr + o, r_rim - 4), (x0 + o, r_rim + 6)]
    radii = [0, 0, 3.0, q['R_rim'], q['R_hub'], 8.0,
             8.0, 2.0, 1.0, 0.5, 0.5, 5.0,
             0, 0,
             5.0, 0.5, 0.5, 1.0, 2.0, 8.0,
             8.0, q['R_hub'], q['R_rim'], 3.0]
    return A.round_polygon(poly, radii)


# ------------------------------------------------------------------------------------------------ compressor stack
TIE = dict(d=42.0, pitch=3.0, shank=28.0, pre_kN=185.0, land=45.8, x_nut=(18.0, 48.0), x_end=626.0, thread_len=36.0,
           lands=(266.0, 353.0, 446.0))
BORE_IMP = 46.0
# curvic bands after the impeller detail design (inducer hubs r 60 / 80, sim/a1000_impeller_design.json)
# phase 4 (docs/08 sec. 21): stub - I1 band r 44-58 -> 35-47. The stub is a tube r 23-48 (seal land) behind a thin nose
# flare to r 60, boxed in by the front bearing housing up to x 201: the outer teeth sat on the flare, the contact ran to
# the inner radius (3D FEA: tooth root 1,120 MPa, 3,100 starts). Inside the tube the band has a solid backing.
CURVIC_C = dict(stub_I1=dict(ri=35.0, ro=47.0, N=36), I1_spc=dict(ri=50.0, ro=70.0, N=36),
                spc_I2=dict(ri=52.0, ro=72.0, N=36), I2_drum=dict(ri=55.0, ro=75.0, N=36))
R_HUB_IN = (60.0, 80.0)                                           # impeller inducer hub radii (flow-path hub at the faces)
JOURNAL = dict(D=90.0, L=36.0, n_pad=4, arc=65.0)               # tilting-pad journals (sim/engine/a1000_rotor_stack.py), rev 1.3;
                                                                 # sec. 19: 4 pads x 65 deg load between pads (was 5 x 52): the
                                                                 # horizontal split of the front bearing housing runs between pads
COLLAR = dict(x0=116.0, x1=136.0, ro=72.0)                       # integral thrust collar (pad ro + 4)
THRUST = dict(ri=52.0, ro=68.0, n=8, n_in=4, t=12.0)             # thrust pads (inner / outer radius, thickness): n on the loaded
                                                                 # (aft) side, n_in on the inactive (forward) side
BACKFACE = dict(r_seal=200.0, r_feed=120.0)                      # impeller 2 back face: labyrinth at r 200, compressor-delivery
                                                                 # air fed at r 120 (pressurised back-face cavity, thrust balance)
BAL_SEAL_R = 85.0                                               # drum balance-piston labyrinth radius (thrust balance)
# phase 4 (docs/08 sec. 21, sim/engine/a1000_joint_fea.py): the drawn ISFD (8 single circumferential beams, short webs) was
# 1.36e9 N/m in the 2D FE, 43 x the 3.1e7 of the rotor dynamics (a beam loaded along its arc acts as a strut), and had no
# film gap. Now 4 hairpin springs (inner arm from a web on the inner ring, U-turn, outer arm back to a web on the outer
# ring: radial and tangential load both bend the arms) and 4 damper pads on the inner ring between them (film on the
# outer-ring bore, open ends, fed from the housing groove); same envelope r 74-92 x 43 mm, same housings
SFD = dict(R=89.0, L=43.0, c=0.13, pad=53.0)                      # damper pads: film radius (outer-ring bore), length, radial
                                                                  # clearance, arc of each of the 4 pads [deg]
ISFD = dict(n=4, kind='hairpin', t=2.56, span=34.0, gap=1.6, w_web=4.0, w_u=4.0, t_ring=3.0, ri=74.0, ro=92.0, Lf=43.0)
                                                                  # integral hairpin-spring damper ring (wire EDM): springs,
                                                                  # arm thickness, arm arc [deg], arm-ring gaps, web / U-turn
                                                                  # widths [deg], ring thickness, ring radii, axial length
X_BRG = (65.0, RD.rotor('A')['brg'][1])                          # journal 1 at x 65: the thrust bearing behind it ends at
                                                                 # x 156, so the stage-1 radial inlet has x 156-205 to turn
# inlet hub fairing (rear of the thrust housing = hub wall of the stage-1 radial inlet bend): (x, r) points from the
# radial wall at x 157 to the inducer hub r 60 at the impeller face; the shroud side (bellmouth) is the compressor design
INLET_HUB = [(157.0, 150.0), (158.0, 132.0), (160.5, 112.0), (166.5, 94.0), (177.0, 79.0), (189.0, 68.0), (201.0, 61.5)]   # 5 mm fuller at r 95-130 (compressor 1.1: area dip 0.91 removed)


def stub_profile():
    """front stub shaft 34CrNiMo6: coupling flange, seal, journal 1, integral thrust collar, inlet seal, front curvic"""
    D, L = JOURNAL['D'], JOURNAL['L']; xb = X_BRG[0]; c0, c1, cro = COLLAR['x0'], COLLAR['x1'], COLLAR['ro']
    rc = THRUST['ri'] - 4.0                                    # collar shoulders: 4 mm under the pad bore
    assert xb - L / 2 - 6 > 22.0 and rc >= 48.0
    aft = [(c1 + 6, rc), (c1 + 6, 48.0)] if rc > 48.0 else []
    return [(0.0, 35.0), (0.0, 80.0), (14.0, 80.0), (14.0, D / 2 - 3), (22.0, D / 2 - 3), (22.0, D / 2 - 2),
            (xb - L / 2 - 6, D / 2 - 2), (xb - L / 2 - 6, D / 2), (xb + L / 2 + 8, D / 2), (xb + L / 2 + 8, rc),   # shoulder 2 mm clear of the carrier
            (c0, rc), (c0, cro), (c1, cro), (c1, rc)] + aft + [(X_I1[0] - 4, 48.0),
            (X_I1[0] - 1.5, R_HUB_IN[0]), (X_I1[0], R_HUB_IN[0]),
            (X_I1[0], BORE_IMP / 2), (TIE['x_nut'][1], BORE_IMP / 2), (TIE['x_nut'][1], 35.0)]


def spacer_profile():
    """compressor interstage spacer 17-4PH H1025: curvics r 50-70 (front) / 52-72 (rear), labyrinth land r 75, rear end on
    the r 80 flow-path hub of impeller 2"""
    x0, x1 = X_I1[1], X_I2[0]
    return [(x0, BORE_IMP / 2), (x0, 72.0), (x0 + 4, 72.0), (x0 + 4, 75.0), (x0 + 30, 75.0), (x0 + 36, 70.0),
            (x1 - 10, 70.0), (x1 - 4, R_HUB_IN[1]), (x1, R_HUB_IN[1]), (x1, BORE_IMP / 2)]


def drum_profile():
    """IN718 drum: front curvic r 55-75, balance-piston land, tube r 70-85, bulkhead with the M42 tie-bolt thread
    (x 590-628), neck r 50-60, flange r 50-92 with the 16 studs to R1"""
    x0, xj = X_I2[1], X_J['drum_R1']; tf = ARM['tf']; xbh = TIE['x_end'] + 2
    return [(x0, 50.0), (x0, 77.0), (x0 + 6, 77.0), (x0 + 6, BAL_SEAL_R), (xj - 75, BAL_SEAL_R), (xj - 55, 72.0),
            (xj - 30, 62.0), (xj - tf - 12, 60.0), (xj - tf, 60.0), (xj - tf, ARM['rf']), (xj, ARM['rf']), (xj, 50.0),
            (xj - tf - 6, 50.0), (xbh, 46.0), (xbh, TIE['d'] / 2), (xbh - 40, TIE['d'] / 2), (xbh - 40, 66.0),
            (xbh - 46, 70.0), (x0 + 20, 70.0), (x0 + 14, 50.0)]


def rear_stub_profile():
    """IN718 rear stub: flange (studs to R2), neck, journal 2, seal runner"""
    xj = X_J['R2_stub']; tf = ARM['tf']; D, L = JOURNAL['D'], JOURNAL['L']; xb = X_BRG[1]
    return [(xj, 25.0), (xj, ARM['rf']), (xj + tf, ARM['rf']), (xj + tf, 60.0), (xj + tf + 3, 60.0), (xj + tf + 7, D / 2 - 0.5),
            (xb - L / 2 - 6, D / 2 - 0.5), (xb - L / 2 - 6, D / 2), (xb + L / 2 + 6, D / 2), (xb + L / 2 + 6, D / 2 - 4),
            (xb + L / 2 + 30, D / 2 - 4), (xb + L / 2 + 30, 25.0)]


def turbine_spacer_profile():
    """IN718 R1 - R2 spacer ring (rev 6): curvic lands r 60-92 at both faces, waist r 60-88 with 4 knife edges to r 92.3
    (interstage seal, 0.3 mm cold to the r 92.6 honeycomb of the NGV2 diaphragm)"""
    q = TSPC; x0, x1 = X_J['R1_spc'], X_J['spc_R2']; rf = ARM['rf']
    p = [(x0, q['ri']), (x0, rf), (x0 + q['land'], rf), (x0 + q['land'] + 1.0, q['ro'])]
    xm = 0.5 * (x0 + x1)
    for k in range(q['n_fin']):
        xk = xm + (k - (q['n_fin'] - 1) / 2) * q['fin_pitch']
        p += [(xk - 0.9, q['ro']), (xk - 0.15, q['r_fin']), (xk + 0.15, q['r_fin']), (xk + 0.9, q['ro'])]
    return p + [(x1 - q['land'] - 1.0, q['ro']), (x1 - q['land'], rf), (x1, rf), (x1, q['ri'])]


def tie_profile():
    x0 = TIE['x_nut'][0] + 2; x1 = TIE['x_end']; d, s = TIE['d'], TIE['shank']
    p = [(x0, 0.0), (x0, d / 2), (TIE['x_nut'][1] + 4, d / 2), (TIE['x_nut'][1] + 10, s / 2)]
    for xl in TIE['lands']:
        p += [(xl - 12, s / 2), (xl - 8, TIE['land'] / 2), (xl + 8, TIE['land'] / 2), (xl + 12, s / 2)]
    p += [(x1 - TIE['thread_len'] - 8, s / 2), (x1 - TIE['thread_len'], d / 2), (x1, d / 2), (x1, 0.0)]
    return p


def nut_profile():
    x0, x1 = TIE['x_nut']
    return [(x0, TIE['d'] / 2), (x0, 33.0), (x1, 33.0), (x1, TIE['d'] / 2)]


ROTOR_PARTS = [  # name, profile function, material, density kg/m3, colour group
    ('RT-101 Front stub shaft + thrust collar', stub_profile, '34CrNiMo6 QT', 7850),
    ('RT-102 Tie bolt M42 IN718', tie_profile, 'IN718', 8190),
    ('RT-103 Tie-bolt nut', nut_profile, 'IN718', 8190),
    ('RT-104 Compressor spacer', spacer_profile, '17-4PH H1025', 7800),
    ('RT-105 Drum IN718', drum_profile, 'IN718', 8190),
    ('RT-106 Rear stub shaft', rear_stub_profile, 'IN718', 8190),
    ('RT-107 Turbine spacer ring R1 - R2', turbine_spacer_profile, 'Waspaloy', 8190),
]


def poly_area_props(poly):
    """volume of revolution [mm3] (Pappus) and axial centroid of an (x, r) polygon: sum over the triangles (origin, p_i,
    p_i+1) of 2 pi int r dA and 2 pi int x r dA (exact for straight edges)"""
    V = 0.0; Mx = 0.0
    n = len(poly)
    for i in range(n):
        x1, r1 = poly[i]; x2, r2 = poly[(i + 1) % n]
        a = 0.5 * (x1 * r2 - x2 * r1)
        V += 2 * math.pi * a * (r1 + r2) / 3.0
        Mx += 2 * math.pi * a / 12.0 * (x1 * r1 + x2 * r2 + (x1 + x2) * (r1 + r2))
    return abs(V), (Mx / V if V else 0.0)


# ================================================================================================ FreeCAD (--cad)
def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def revolve(poly):
    App, Part, V = _fc()
    pts = [V(x, 0, r) for x, r in poly]
    if (pts[0] - pts[-1]).Length > 1e-6: pts.append(pts[0])
    f = Part.Face(Part.makePolygon(pts))
    s = f.revolve(V(0, 0, 0), V(1, 0, 0), 360)
    return s if s.Volume > 0 else s.reversed()


def tube(x0, x1, ro, ri=0.0):
    return revolve([(x0, ri), (x1, ri), (x1, ro), (x0, ro)])


def curvic_teeth(x_face, ri, ro, N, h, direction, phase=0.0):
    """ring of N curvic teeth on a face at x_face, standing in +x (direction +1) or -x (-1); 30 deg flanks.
    Teeth are trapezoids in the (circumference, x) plane, lofted from ri to ro (straight radial approximation)."""
    App, Part, V = _fc()
    teeth = []
    for k in range(N):
        th0 = 2 * math.pi * (k + phase) / N
        wires = []
        for r in (ri, ro):
            p = 2 * math.pi * r / N; top = 0.25 * p; root = top + 2 * h * math.tan(math.radians(30.0))
            root = min(root, 0.98 * p)
            pts2 = [(-root / 2, 0.0), (root / 2, 0.0), (top / 2, h), (-top / 2, h)]
            pts = []
            for s_, z in pts2:
                a = th0 + s_ / r
                pts.append(V(x_face + direction * z, r * math.cos(a), r * math.sin(a)))
            pts.append(pts[0]); wires.append(Part.makePolygon(pts))
        teeth.append(Part.makeLoft(wires, True, True))
    return teeth


def curvic_face(part, xj, side, ri, ro, N, h, phase=0.0):
    """cut half the tooth band off the joint face of `part` (side -1: part lies at x < xj, +1: at x > xj) and add N teeth
    across the whole band [xj - h/2, xj + h/2]; the mating part uses the other side and phase + 0.5, so the teeth mesh"""
    if side < 0:
        part = part.cut(tube(xj - h / 2, xj + 0.01, ro, ri)); teeth = curvic_teeth(xj - h / 2, ri, ro, N, h, +1, phase)
    else:
        part = part.cut(tube(xj - 0.01, xj + h / 2, ro, ri)); teeth = curvic_teeth(xj + h / 2, ri, ro, N, h, -1, phase)
    return part.fuse(teeth)


def holes(x0, x1, r, d, n, phase=0.5):
    App, Part, V = _fc()
    return [Part.makeCylinder(d / 2, x1 - x0, V(x0, r * math.cos(2 * math.pi * (k + phase) / n), r * math.sin(2 * math.pi * (k + phase) / n)),
                              V(1, 0, 0)) for k in range(n)]


def thread_grooves(x0, x1, r_major, pitch, inner=False):
    """thread zone shown as circumferential V-grooves (cosmetic; the drawing carries the thread callout)"""
    App, Part, V = _fc()
    g = []
    x = x0 + pitch
    d = 0.6 * pitch
    while x < x1 - pitch / 2:
        if inner:
            g.append(revolve([(x - pitch / 2, r_major - d - 0.3), (x + pitch / 2, r_major - d - 0.3), (x, r_major)]))
        else:
            g.append(revolve([(x - pitch / 2, r_major + 0.3), (x + pitch / 2, r_major + 0.3), (x, r_major - d)]))
        x += pitch
    return g


def stud_set(x_stud0, x_stud1, x_nut, nut_dir, n, r, phase=0.5):
    """studs (cylinders) and 12-point nuts (hexagonal prisms) on a bolt circle; nut_dir +1: nut face toward +x"""
    App, Part, V = _fc()
    studs, nuts = [], []
    d, af, hn = STUD['d'], STUD['nut_af'], STUD['nut_h']
    for k in range(n):
        a = 2 * math.pi * (k + phase) / n; y, z = r * math.cos(a), r * math.sin(a)
        studs.append(Part.makeCylinder(d / 2, x_stud1 - x_stud0, V(x_stud0, y, z), V(1, 0, 0)))
        R = af / math.sqrt(3)
        hexpts = [V(0, y + R * math.cos(math.pi / 3 * j + a), z + R * math.sin(math.pi / 3 * j + a)) for j in range(6)]
        hexpts.append(hexpts[0])
        f = Part.Face(Part.makePolygon(hexpts)); x0 = x_nut if nut_dir > 0 else x_nut - hn
        nut = f.extrude(V(hn, 0, 0)); nut.translate(V(x0, 0, 0))
        nut = nut.cut(Part.makeCylinder(d / 2, hn + 2, V(x0 - 1, y, z), V(1, 0, 0)))
        nuts.append(nut)
    return studs, nuts


def build_rotor():
    """rotor parts as solids: {name: (shape, material, group)}"""
    App, Part, V = _fc()
    out = {}
    stub = revolve(stub_profile())
    stub = stub.cut(holes(-1, 15, 66.0, 13.0, 12))                                         # coupling flange 12 x M12
    c = CURVIC_C['stub_I1']; stub = curvic_face(stub, X_I1[0], -1, c['ri'], c['ro'], c['N'], 2.4)
    out['RT-101 Front stub shaft + thrust collar'] = (stub.removeSplitter(), '34CrNiMo6 QT', 'shaft')
    tie = revolve(tie_profile())
    tie = tie.cut(thread_grooves(TIE['x_nut'][0] + 2, TIE['x_nut'][1] + 2, TIE['d'] / 2, TIE['pitch']))
    tie = tie.cut(thread_grooves(TIE['x_end'] - TIE['thread_len'], TIE['x_end'], TIE['d'] / 2, TIE['pitch']))
    out['RT-102 Tie bolt M42 IN718'] = (tie, 'IN718', 'tie')
    nut = revolve(nut_profile()).cut(holes(TIE['x_nut'][0] - 1, TIE['x_nut'][0] + 6, 28.0, 6.0, 4, 0.0))
    out['RT-103 Tie-bolt nut'] = (nut, 'IN718', 'tie')
    spc = revolve(spacer_profile())
    for k in range(4):                                                                       # 4 labyrinth teeth
        xk = X_I1[1] + 8 + 6 * k
        spc = spc.fuse(revolve([(xk - 1.5, 75.0), (xk + 1.5, 75.0), (xk + 0.3, 79.0), (xk - 0.3, 79.0)]))
    c = CURVIC_C['I1_spc']; spc = curvic_face(spc, X_I1[1], +1, c['ri'], c['ro'], c['N'], 3.0, 0.5)
    c = CURVIC_C['spc_I2']; spc = curvic_face(spc, X_I2[0], -1, c['ri'], c['ro'], c['N'], 2.6)
    out['RT-104 Compressor spacer'] = (spc.removeSplitter(), '17-4PH H1025', 'shaft')
    drum = revolve(drum_profile())
    for k in range(6):                                                                       # balance-piston labyrinth
        xk = X_I2[1] + 12 + 7 * k
        drum = drum.fuse(revolve([(xk - 1.6, BAL_SEAL_R), (xk + 1.6, BAL_SEAL_R), (xk + 0.3, BAL_SEAL_R + 4.5), (xk - 0.3, BAL_SEAL_R + 4.5)]))
    c = CURVIC_C['I2_drum']; drum = curvic_face(drum, X_I2[1], +1, c['ri'], c['ro'], c['N'], 3.2, 0.5)
    xj = X_J['drum_R1']; ch = CURVIC_HOT
    drum = curvic_face(drum, xj, -1, ch['ri'], ch['ro'], ch['N'], ch['h'])
    drum = drum.cut(holes(xj - ARM['tf'] - 1, xj + ch['h'], STUD['r'], STUD['hole'], STUD['n']))
    out['RT-105 Drum IN718'] = (drum.removeSplitter(), 'IN718', 'drum')
    rs = revolve(rear_stub_profile())
    xj = X_J['R2_stub']
    ch = CURVIC_HOT; rs = curvic_face(rs, xj, +1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.5)
    rs = rs.cut(holes(xj - ch['h'], xj + ARM['tf'] + 1, STUD['r'], STUD['hole'], STUD['n']))
    out['RT-106 Rear stub shaft'] = (rs.removeSplitter(), 'IN718', 'shaft')
    sp = revolve(turbine_spacer_profile())                                                    # rev 6: R1 - R2 spacer ring
    sp = curvic_face(sp, X_J['R1_spc'], +1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.5)       # mates the R1 aft face
    sp = curvic_face(sp, X_J['spc_R2'], -1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.0)       # mates the R2 forward face
    sp = sp.cut(holes(X_J['R1_spc'] - ch['h'], X_J['spc_R2'] + ch['h'], STUD['r'], STUD['hole'], STUD['n']))
    out['RT-107 Turbine spacer ring R1 - R2'] = (sp.removeSplitter(), TSPC['mat'], 'shaft')
    # studs + nuts of the three hot joints (nuts in the cavity behind the cast flange): drum - R1 from the drum flange through
    # the R1 flange, nut aft of it; R1 - R2 from the R2 flange inserts through the spacer and the R1 flange, nut in front;
    # R2 - rear stub from the rear-stub flange through the R2 flange, nut in front
    for tag, (x0_, x1_, xn_, dn_) in STUD_SETS.items():
        st, nu = stud_set(x0_, x1_, xn_, dn_, STUD['n'], STUD['r'])
        out['RT-11%d Studs + nuts %s (16 x M10)' % (len([k for k in out if 'Studs' in k]) + 1, tag)] = (
            Part.makeCompound(st + nu), 'Waspaloy studs + nuts' if tag == 'R1 - R2' else 'IN718 / Waspaloy nuts', 'studs')
    return out


def build_blisk_arms(row):
    """the cast blisk disc with arms and flanges (replaces fusion/A1000/A1000_<row>_disc.step in the rotor model):
    revolved outline + curvic teeth and stud holes on both flange faces. Blades: unchanged rev 5 pieces."""
    App, Part, V = _fc()
    s = revolve(disc_profile_arms(row))
    # the rev 5 disc seam is rotated by half a blade pitch: irrelevant for a solid of revolution
    xa = X_J['R1_spc'] if row == 'R1' else X_J['R2_stub']
    xf = X_J['drum_R1'] if row == 'R1' else X_J['spc_R2']
    ch = CURVIC_HOT
    s = curvic_face(s, xf, +1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.5)          # forward face: mates the part in front
    s = curvic_face(s, xa, -1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.0)          # aft face: mates the part behind
    s = s.cut(holes(xf - ch['h'], xf + ARM['tf'] + 1, STUD['r'], STUD['hole'], STUD['n']))
    s = s.cut(holes(xa - ARM['tf'] - 1, xa + ch['h'], STUD['r'], STUD['hole'], STUD['n']))
    return s.removeSplitter()


# ------------------------------------------------------------------------------------------------ bearings (FreeCAD)
# sec. 19 (assembly, lubrication and piping review): the front stub carries the integral coupling flange (r 80) and the
# integral thrust collar (r 72) on both sides of journal 1, so no one-piece housing, damper ring or carrier can reach JB1 or
# the thrust bearing. The front bearings therefore sit in one horizontally split front bearing housing (FB-1 / FB-2,
# centre-line feet at the split): the lower halves are in place before the balanced rotor is lowered in, the upper halves
# close over it. The journals have 4 pads (load between pads, sec. 19) so the split runs through the inter-pad gaps; the
# carriers and the ISFD rings are split too (springs clocked 7.5 deg so the split runs between springs). JB2 stays a
# one-piece cartridge that slides on from the rear (the rear stub only gets smaller aft of the journal), with a split
# labyrinth ring on the r 44.5 land in front of the journal and a blind end cover (the shaft ends inside).
# Lubrication (sim/engine/a1000_lube_piping.py): directed lube - 4 spray bars per journal in the inter-pad gaps, 2 jets each
# aimed at the leading edge of the next pad; housing groove at line pressure -> 2 transfer tubes (with the flow orifices)
# -> carrier gallery -> bars; the ISFD land is fed from the same groove through 2 orifices and sealed by piston rings;
# thrust pads with leading-edge grooves fed from grooves at the base-ring ODs. Drains DN65 (FBH) / DN50 (JB2), vents DN25 /
# DN32 at the top. Seals: JB1 front - windback + 3 teeth (c 0.20, no buffer); TB rear (compressor eye below ambient) and
# JB2 front - windback + teeth | buffer annulus | teeth, buffer air from the compressor stage-1 exit.
LUBE_JSON = os.path.join(ROOT, 'sim', 'engine', 'fea', 'a1000_lube_piping.json')
PAD = dict(t=10.0, pivot=0.60, stop_deg=12.0)                   # pad thickness, pivot offset (fraction of the arc), stop pin
SPRAY = dict(w=8.0, r0=46.5, jets=2, d_jet=1.5, aim=15.0)        # spray bar width, inner radius, jets per bar, jet d, inward aim
ISFD_FEED_D = 1.4                                                # pad feed orifices (2 per ring, sec. 21)
ISFD_CLOCK = 28.0                                                # spring k from 28 + 90 k (centres 45 / 135 / 225 / 315 deg): the pads
                                                                 # sit at 0 / 90 / 180 / 270, the split plane runs through two pads
SEAL_C = dict(jb1=0.20, tb=0.15, jb2=0.20)                       # radial clearance of the oil / buffer labyrinths
FBH = dict(x0=27.0, ro=130.0, lug=(125.0, 165.0, 20.0), foot=200.0, x_max=141.0)   # front bearing housing: front face, OD,
# split lugs, feet; x_max: nothing of FB-1 / FB-2 at r > 130 aft of x 141 (inlet casing hub wall x 143-157 over the OD, its
# rear face seals on the fairing face x 157; phase 3, docs/08 sec. 20), except that fairing face and the fairing itself
JB2C = dict(x0=911.0, x1=1026.0, ro=130.0, cover_t=10.0, seal=(913.5, 930.5), shoulder=(985.0, 990.0, 140.0),
            x_port=1005.0, shield=(167.0, 181.0), shield_x0=904.0)   # JB2 cartridge (phase 2 mount), shield (fibre + foils)
# phase 2 exhaust frame (sim/engine/a1000_exhaust.py JB2_MOUNT): ring EX-412 r 130-150 over x 925-985 clamps the housing,
# 8 radial keys at 22.5 + 45 k deg (16 mm, x 935-975) into the hub bore ring r 185; oil in through the top strut (90 deg)
JB2_RING = dict(x=(925.0, 985.0), r=(130.0, 150.0), keys=8, key_w=16.0, key_x=(935.0, 975.0))


def _lube():
    try:
        return json.load(open(LUBE_JSON))
    except Exception:
        return {}


def journal_pad_angles():
    """leading-edge angles of the journal pads (deg, rotation +theta): load between the two bottom pads"""
    n, arc = JOURNAL['n_pad'], JOURNAL['arc']
    c0 = 270.0 - 180.0 / n                                    # first bottom pad centre
    return [(c0 + 360.0 / n * k - arc / 2) % 360.0 for k in range(n)]


def spray_bar_angles():
    """inter-pad gaps; the bars of the gaps on the split plane (0 / 180) sit just below it, in the lower half"""
    out = []
    for a in journal_pad_angles():
        g = (a - (360.0 / JOURNAL['n_pad'] - JOURNAL['arc']) / 2) % 360.0
        half_w = math.degrees(SPRAY['w'] / 2 / 52.0) + 0.3
        if abs(math.sin(math.radians(g))) < math.sin(math.radians(half_w)):
            g = g - half_w if math.cos(math.radians(g)) > 0 else g + half_w
        out.append((g, a))                                     # (bar angle, leading edge it feeds)
    return out


def _clean(shape):
    """removeSplitter, kept only if the result is valid and has the same volume (it can break a many-feature solid)"""
    ok = shape.isValid()
    try:
        c = shape.copy().removeSplitter()                           # (refines in place in this FreeCAD build)
        if c.isValid() and (not ok or abs(c.Volume - shape.Volume) <= 1e-4 * abs(shape.Volume)): return c
    except Exception:
        pass
    if not ok:
        c = shape.copy(); c.fix(1e-6, 1e-6, 1e-6)
        if c.isValid(): return c
    return shape


def _splitz(shape):
    """[lower, upper] halves of a shape cut on z = 0"""
    App, Part, V = _fc()
    lo = shape.common(Part.makeBox(4000, 4000, 2000, V(-1000, -2000, -2000)))
    up = shape.common(Part.makeBox(4000, 4000, 2000, V(-1000, -2000, 0)))
    return [_clean(lo), _clean(up)]


def _radial_hole(x, r0, r1, deg, d):
    App, Part, V = _fc()
    return Part.makeCylinder(d / 2, r1 - r0, _polar(x, r0, deg), _radial(deg))


def _teeth(xs, r_body, r_tip):
    """labyrinth teeth on a stator bore (r_body) pointing in to r_tip"""
    return [revolve([(xk - 0.8, r_body), (xk + 0.8, r_body), (xk + 0.25, r_tip), (xk - 0.25, r_tip)]) for xk in xs]


def _windback(x0, x1, r_bore, pitch=2.5, depth=0.8):
    """windback thread in a stator bore (shown as grooves; the drawing gives the hand: it pumps toward the oil side)"""
    g = []; x = x0 + pitch / 2
    while x < x1 - pitch / 2:
        g.append(revolve([(x - 0.6, r_bore - 0.01), (x + 0.6, r_bore - 0.01), (x + 0.6, r_bore + depth), (x - 0.6, r_bore + depth)]))
        x += pitch
    return g


def journal_parts(xb, tag):
    """4-pad tilting-pad journal (load between pads, 60 % pivot) in a split carrier with 4 spray bars, in a split ISFD ring
    (4 hairpin springs + 4 open-ended damper pads, O-rings on the OD, 2 transfer tubes; sec. 21): {name: (shape, material, group)}"""
    App, Part, V = _fc()
    D, L, arc = JOURNAL['D'], JOURNAL['L'], JOURNAL['arc']; R = D / 2
    r_pad, r_car = R + PAD['t'], ISFD['ri']
    out = {}
    pads = []
    for a0 in journal_pad_angles():
        ring = tube(xb - L / 2, xb + L / 2, r_pad, R + 0.12)
        pad = ring.common(_sector(xb, r_pad + 5, a0, arc, L + 2))
        ap = a0 + PAD['pivot'] * arc
        pad = pad.fuse(Part.makeCylinder(5.0, 4.6, _polar(xb, r_pad - 1.0, ap), _radial(ap)))
        # stop-pin hole 12 deg behind the leading edge on the back: off the pad centre, so a pad turned round does not fit
        pad = pad.cut(Part.makeCylinder(2.6, 4.0, _polar(xb, r_pad - 3.0, a0 + PAD['stop_deg']), _radial(a0 + PAD['stop_deg'])))
        pads.append(_clean(pad))
    out['%s tilting pads x%d (steel + babbitt)' % (tag, JOURNAL['n_pad'])] = (Part.makeCompound(pads), 'steel + babbitt', 'pads')
    # carrier: ring r 59-74, end plates down to R + 0.4 (evacuated housing), OD gallery 8 x 5, spray bars, stop pins
    x0c, x1c = xb - L / 2 - 6, xb + L / 2 + 6
    car = tube(x0c, x1c, r_car, r_pad + 4.0)
    car = car.fuse(tube(x0c, xb - L / 2 - 1, r_car, R + 0.4)).fuse(tube(xb + L / 2 + 1, x1c, r_car, R + 0.4))
    for g, le in spray_bar_angles():
        bar = tube(xb - L / 2 + 2, xb + L / 2 - 2, r_pad + 4.1, SPRAY['r0']).common(
            _sector(xb, r_pad + 6, g - math.degrees(SPRAY['w'] / 2 / 52.0), math.degrees(SPRAY['w'] / 52.0), L))
        car = car.fuse(bar)
    car = car.cut(tube(xb - 4.0, xb + 4.0, r_car + 0.01, r_car - 5.0))                     # gallery groove
    d_jet = _lube().get('bearings', {}).get(tag, {}).get('jets', {}).get('d_mm', SPRAY['d_jet'])
    for g, le in spray_bar_angles():
        car = car.cut(_radial_hole(xb, SPRAY['r0'] + 3.0, r_car - 4.5, g, 4.0))            # feed bore into the bar
        for j in range(SPRAY['jets']):                                                  # jets toward the next leading edge
            xj = xb + (j - (SPRAY['jets'] - 1) / 2) * L / 3
            p0 = _polar(xj, 51.0, g); t = math.radians(g + 90.0)
            d = V(0, math.cos(t), math.sin(t)) * math.cos(math.radians(SPRAY['aim'])) - _radial(g) * math.sin(math.radians(SPRAY['aim']))
            car = car.cut(Part.makeCylinder(d_jet / 2, 12.0, p0, d))
    for a0 in journal_pad_angles():                                                     # stop pins (pressed in the carrier)
        car = car.fuse(Part.makeCylinder(2.4, 6.0, _polar(xb, r_pad + 4.5, a0 + PAD['stop_deg']), _radial(a0 + PAD['stop_deg']) * -1))
    # split dowels: d 6 at +y, d 8 at -y (the halves go back only one way)
    for sy, d in ((1, 6.0), (-1, 8.0)):
        car = car.cut(Part.makeCylinder(d / 2, 16.0, V(xb + sy * 12.0, sy * 66.5, -8.0), V(0, 0, 1)))
    car = car.cut(_radial_hole(xb + 10.0, 60.0, r_car + 1, 135.0, 6.0))                  # anti-rotation pin from the ISFD ring
    out['%s pad carrier + end plates (split)' % tag] = (Part.makeCompound(_splitz(car)), 'steel', 'carrier')
    # ISFD ring, split: inner ring r 74-77 with 4 damper pads (to the film radius - c), outer ring r 89-92, 4 hairpin
    # springs (sec. 21); the split plane runs through the pads at 0 / 180 deg
    q = ISFD; Lf = ISFD['Lf']; x0, x1 = xb - Lf / 2, xb + Lf / 2
    r1, r2 = q['ri'] + q['t_ring'], q['ro'] - q['t_ring']
    gm = (r2 - r1) - 2 * q['t'] - 2 * q['gap']
    rA0 = r1 + q['gap']; rA1 = rA0 + q['t']; rB0 = rA1 + gm; rB1 = rB0 + q['t']
    isfd = tube(x0, x1, r1, q['ri']).fuse(tube(x0, x1, q['ro'], r2))
    for k in range(q['n']):
        a = ISFD_CLOCK + 360.0 / q['n'] * k; sp, w, wu = q['span'], q['w_web'], q['w_u']
        def arc(ra, rb, a0, a1): return tube(x0, x1, rb, ra).common(_sector(xb, q['ro'] + 2, a0, a1 - a0, Lf + 2))
        pad0, pad1 = a + sp + 1.5, a + 360.0 / q['n'] - 1.5                      # pad between this spring and the next
        isfd = isfd.fuse([arc(rA0, rA1, a, a + sp), arc(rB0, rB1, a, a + sp), arc(rA0, rB1, a + sp - wu, a + sp),
                          arc(r1 - 0.5, rA0 + 0.5, a, a + w), arc(rB1 - 0.5, r2 + 0.5, a, a + w),
                          arc(r1 - 0.5, SFD['R'] - SFD['c'], pad0, pad1)])
    isfd = isfd.cut(tube(x0 + 2, x0 + 5, q['ro'] + 0.1, q['ro'] - 1.8)).cut(tube(x1 - 5, x1 - 2, q['ro'] + 0.1, q['ro'] - 1.8))   # O-rings
    # (open-ended pads: no piston rings; the pad films drain at their ends into the bearing cavity)
    for deg in (90.0, 270.0):                                                          # transfer-tube bores through the 90 / 270 pads;
        isfd = isfd.cut(_radial_hole(xb, q['ri'] - 1, q['ro'] + 1, deg, 12.2))           # 13 in the outer ring: the pad moves c
        isfd = isfd.cut(_radial_hole(xb, r2 - 0.5, q['ro'] + 1, deg, 13.0))
    for deg in (0.0 + 9.0, 180.0 + 9.0):                                               # pad feed orifices (beside the split)
        isfd = isfd.cut(_radial_hole(xb, r2 - 0.5, q['ro'] + 0.5, deg, ISFD_FEED_D))
    isfd = isfd.cut(_radial_hole(xb + 10.0, q['ri'] - 1, r1 + 0.5, 135.0, 6.0))            # carrier anti-rotation pin
    isfd = isfd.cut(_radial_hole(xb - 10.0, r2 - 0.5, q['ro'] + 0.5, 45.0, 8.0))            # pin from the housing (outer ring)
    tubes = []
    for deg in (90.0, 270.0):
        tt = Part.makeCylinder(6.0, q['ro'] - 1.0 - q['ri'] - 0.05, _polar(xb, q['ri'] + 0.05, deg), _radial(deg)).cut(
            Part.makeCylinder(4.0, 21.0, _polar(xb, q['ri'] - 1.0, deg), _radial(deg)))     # seats on the carrier OD (O-ring)
        tubes.append(tt)
    isfd_h = _splitz(isfd)
    out['%s integral hairpin-spring damper ring (ISFD, %d springs + %d pads, split) + transfer tubes' % (tag, q['n'], q['n'])] = (
        Part.makeCompound(isfd_h + tubes), '17-4PH H1100', 'cage')
    return out


def front_bearing_housing():
    """FB-1 / FB-2: horizontally split front bearing housing for JB1 and the thrust bearing, with the inlet hub fairing,
    centre-line feet, oil inlets on the lower half (no line is opened to lift the upper half), drain 2 x DN40 and vent DN25,
    buffered rear seal (compressor eye) and plain front seal (coupling side); all lines leave forward through the dry
    tunnel of the inlet plenum (phase 3)"""
    App, Part, V = _fc()
    xb, L = X_BRG[0], JOURNAL['L']; c0, c1 = COLLAR['x0'], COLLAR['x1']; t = THRUST['t']; e = 0.15; tc = 8.0
    xr1 = c1 + e + t + tc; xf1 = c0 - e - t - tc                     # aft / forward base-ring outer faces
    Lf = ISFD['Lf']; xi0, xi1 = xb - Lf / 2, xb + Lf / 2
    x_n = INLET_HUB[-1][0]; ro = FBH['ro']; rq = ISFD['ro']
    sep0 = xb + L / 2 + 6.5                                          # separator wall between JB1 and the thrust chamber
    prof = [(FBH['x0'], 44.0), (FBH['x0'], ro), (INLET_HUB[0][0], ro)] + INLET_HUB + [(x_n, 49.0), (xr1, 49.0), (xr1, 74.05),
            (xr1 - tc, 74.05), (xr1 - tc, 90.0), (xf1 + tc, 90.0), (xf1 + tc, 74.05), (xf1, 74.05), (xf1, 49.5), (sep0, 49.5),
            (sep0, rq), (xi1, rq), (xi1, rq + 0.02), (xi0, rq + 0.02), (xi0, rq), (xb - L / 2 - 10.0, rq), (xb - L / 2 - 10.0, 44.0)]
    hs = revolve(prof)
    xw1 = xb - L / 2 - 10.0                                           # back face of the front wall
    c = SEAL_C['jb1']
    hs = hs.fuse(_teeth([FBH['x0'] + 2.0, FBH['x0'] + 4.5, FBH['x0'] + 7.0], 44.0, 43.0 + c)).cut(_windback(FBH['x0'] + 8.0, xw1, 44.0 - 0.8))
    c = SEAL_C['tb']                                                  # rear: windback + 3 teeth | buffer annulus | 4 teeth
    hs = hs.cut(_windback(xr1 + 1.0, xr1 + 13.0, 49.0))
    hs = hs.fuse(_teeth([xr1 + 15.5, xr1 + 18.0, xr1 + 20.5], 49.0, 48.0 + c))
    xbuf = xr1 + 24.5
    hs = hs.cut(tube(xbuf - 2.5, xbuf + 2.5, 53.0, 48.9))
    hs = hs.fuse(_teeth([xbuf + 4.5, xbuf + 7.5, xbuf + 10.5, xbuf + 13.5], 49.0, 48.0 + c))
    # oil grooves: ISFD feed groove at the journal centre, LEG grooves at the two base-ring ODs
    hs = hs.cut(tube(xb - 5.0, xb + 5.0, rq + 6.0, rq - 0.5))
    for xg in (xf1 + tc / 2, xr1 - tc / 2):
        hs = hs.cut(tube(xg - 2.5, xg + 2.5, 78.0, 74.0))
    # split lugs (both halves) and centre-line feet (lower half, extended), bolt + dowel holes; lifting bosses (upper half)
    l0, l1, lt = FBH['lug']
    for sy in (1, -1):
        hs = hs.fuse(Part.makeBox(FBH['x_max'] - 1.0 - FBH['x0'] - 5.0, l1 - l0, 2 * lt, V(FBH['x0'] + 5.0, min(sy * l0, sy * l1), -lt)))
        hs = hs.fuse(Part.makeBox(70.0, FBH['foot'] - l1, lt, V(xb - 5.0, min(sy * l1, sy * FBH['foot']), -lt)))
        for xh in (FBH['x0'] + 13.0, xb + 23.0, FBH['x_max'] - 11.0):
            hs = hs.cut(Part.makeCylinder(6.5, 4 * lt, V(xh, sy * 147.0, -2 * lt), V(0, 0, 1)))       # M12 split bolts (phase 8)
        hs = hs.cut(Part.makeCylinder(5.0 if sy > 0 else 6.0, 4 * lt, V(xb + 2.0 if sy > 0 else c0 - 7.0, sy * 147.0, -2 * lt), V(0, 0, 1)))
        # feet on the inlet-casing brackets (centre-line support): M16 in slots 18 x 26 along y (FB runs ~45 K hotter than the
        # casing), a transverse key slot 16 x 6 under each foot for the axial location (thrust path)
        for xh in (xb + 5.0, xb + 55.0):
            hs = hs.cut(Part.makeCylinder(9.0, 3 * lt, V(xh, sy * 181.0, -2 * lt), V(0, 0, 1))).cut(
                Part.makeCylinder(9.0, 3 * lt, V(xh, sy * 189.0, -2 * lt), V(0, 0, 1))).cut(
                Part.makeBox(18.0, 8.0, 3 * lt, V(xh - 9.0, sy * 185.0 - 4.0, -2 * lt)))
        hs = hs.cut(Part.makeBox(16.0, FBH['foot'] - l1 + 1.0, 6.0, V(xb + 22.0, min(sy * l1, sy * (FBH['foot'] + 1.0)), -lt)))
    hs = hs.cut(Part.makeBox(40.0, 20.0, 9.0, V(FBH['x0'] + 13.0, -10.0, -ro - 1.0)))                  # bottom centre keyway (y)
    for xh, yh in ((FBH['x0'] + 18.0, 0.0), (FBH['x_max'] - 23.0, 60.0), (FBH['x_max'] - 23.0, -60.0)):   # lifting: M12 eye bolts
        zh = math.sqrt(ro ** 2 - yh ** 2)
        hs = hs.fuse(Part.makeCylinder(18.0, ro + 12.0 - zh + 4.0, V(xh, yh, zh - 4.0), V(0, 0, 1))).cut(
            Part.makeCylinder(7.0, 30.0, V(xh, yh, ro - 6.0), V(0, 0, 1)))
    # oil inlets on the lower half, -y side, below the split lugs: JB1 -> feed groove; TB -> axial gallery -> LEG grooves
    z_in = -45.0
    for xin in (xb, 0.5 * (c0 + c1)):
        hs = hs.fuse(Part.makeCylinder(14.0, 30.0, V(xin, -ro + 12.0, z_in), V(0, -1, 0)))
    hs = hs.cut(Part.makeCylinder(4.0, ro + 20.0 - 80.0, V(xb, -ro - 20.0, z_in), V(0, 1, 0)))
    xm = 0.5 * (c0 + c1); a_g = math.radians(205.0); yg, zg = 100.0 * math.cos(a_g), 100.0 * math.sin(a_g)
    hs = hs.cut(Part.makeCylinder(4.0, ro + 20.0 + yg, V(xm, -ro - 20.0, zg), V(0, 1, 0)))
    # (the gallery runs 2 mm past both LEG feed holes: a hole tangent to the gallery end left an invalid face on FB-2)
    hs = hs.cut(Part.makeCylinder(4.0, xr1 - xf1 + 4.0, V(xf1 - 2.0, yg, zg), V(1, 0, 0)))
    for xg in (xf1 + tc / 2, xr1 - tc / 2):
        hs = hs.cut(_radial_hole(xg, 75.0, 101.0, 205.0, 6.0))
    # JB1 chambers -> thrust chamber: 4 axial holes d 16 at r 82 through the separator (vent + drain paths) and a d 14 drain
    # hole at the bottom from the front chamber; drain DN65 at the bottom of the thrust chamber, vent DN25 at the top
    for deg in (45.0, 135.0, 225.0, 270.0, 315.0):
        hs = hs.cut(Part.makeCylinder(8.0, xf1 + tc - xi1 + 2.0, _polar(xi1 - 1.0, 82.0, deg), V(1, 0, 0)))
    hs = hs.cut(Part.makeCylinder(7.0, xf1 + tc - xw1 + 2.0, _polar(xw1 - 1.0, 100.0, 270.0), V(1, 0, 0)))
    hs = hs.cut(_radial_hole(xw1 + 3.0, 92.0, 101.0, 270.0, 6.0))
    # drain: two DN40 socket bosses side by side under the thrust chamber (x <= 141), bores d 44 from the chamber floor
    xd = FBH['x_max'] - 31.0
    for yd in (-32.0, 32.0):
        hs = hs.fuse(Part.makeCylinder(31.0, 25.0, V(xd, yd, -ro + 5.0), V(0, 0, -1)))
        hs = hs.cut(Part.makeCylinder(22.0, ro + 20.0 - 80.0, V(xd, yd, -80.0), V(0, 0, -1)))     # from inside the chamber floor
    xv = FBH['x_max'] - 23.0                                          # vent DN25 boss on the top of the thrust chamber
    hs = hs.fuse(Part.makeCylinder(22.0, 30.0, V(xv, 0, ro - 6.0), V(0, 0, 1))).cut(Part.makeCylinder(13.5, ro - 60.0, V(xv, 0, 88.0), V(0, 0, 1)))
    # buffer air: boss on the lower half (225 deg) and a straight drilling through the fairing into the buffer annulus
    xab = FBH['x_max'] - 16.0
    a = 225.0; p0 = _polar(xab, 124.0, a); p1 = _polar(xbuf, 50.5, a)
    hs = hs.fuse(Part.makeCylinder(11.0, 22.0, _polar(xab, ro - 8.0, a), _radial(a)))
    hs = hs.cut(Part.makeCylinder(3.0, (p1 - p0).Length + 30.0, p0 - (p1 - p0).normalize() * 30.0, (p1 - p0).normalize()))
    hs = hs.cut(Part.makeCylinder(3.0, 30.0, _polar(xab, 120.0, a), _radial(a)))
    hs = hs.cut(_radial_hole(xi0 - 3.0, rq + 0.5, ro + 1.0, 45.0, 8.0))                  # ISFD anti-rotation pin (top)
    hs = _clean(hs)
    lo, up = _splitz(hs)
    return {'FB-1 Front bearing housing, upper half (JB1 + thrust, EN-GJS-400-18)': (up, 'EN-GJS-400-18', 'housing'),
            'FB-2 Front bearing housing, lower half (JB1 + thrust, EN-GJS-400-18)': (lo, 'EN-GJS-400-18', 'housing')}


def jb2_cartridge():
    """JB2: one-piece cartridge housing that slides on from the rear into the support ring of the exhaust frame (phase 2,
    EX-412: plain OD r 130 over the ring, shoulder behind it), split front labyrinth ring (buffer annulus fed from the
    hub air through 4 restrictor holes, sized in sim/engine/a1000_lube_piping.py), blind end cover, heat shield (fibre in
    1.4828 foil) in the annulus between the
    support ring and the hub bore, slotted for the 8 frame keys"""
    App, Part, V = _fc()
    xb, L = X_BRG[1], JOURNAL['L']; q = JB2C; rq = ISFD['ro']; ro = q['ro']
    Lf = ISFD['Lf']; xi0, xi1 = xb - Lf / 2, xb + Lf / 2
    s0, s1 = q['seal']; sh0, sh1, r_sh = q['shoulder']
    prof = [(q['x0'], 61.55), (q['x0'], ro), (sh0, ro), (sh0, r_sh), (sh1, r_sh), (sh1, ro), (q['x1'], ro), (q['x1'], rq),
            (xi1, rq), (xi1, rq + 0.02), (xi0, rq + 0.02), (xi0, rq), (s1 + 0.5, rq), (s1 + 0.5, 60.05), (s0 + 3.5, 60.05),
            (s0 + 3.5, 61.55)]           # front counterbore for the seal-ring step: the housing slides on from the rear, a
                                         # reversed ring (step at the oil end) does not fit under the 60.05 bore
    hs = revolve(prof)
    hs = hs.cut(tube(xb - 5.0, xb + 5.0, rq + 6.0, rq - 0.5))                                  # ISFD feed groove
    xbuf = 0.5 * (s0 + s1) + 1.5
    hs = hs.cut(tube(xbuf - 1.5, xbuf + 1.5, 63.0, 60.0))                                      # buffer groove at the seal ring
    for deg in (45.0, 135.0, 225.0, 315.0):                                                    # restrictor holes from the shield air
        hs = hs.cut(_radial_hole(xbuf, 61.0, ro + 1.0, deg, _lube().get('seals', {}).get(
            'JB2 front (turbine side, R2 aft cavity 1.04 bar)', {}).get('restrictor_mm', 5.5)))
    hs = hs.cut(Part.makeCylinder(7.0, q['x_port'] - s1 + 6.0, _polar(s1 - 1.0, 100.0, 270.0), V(1, 0, 0)))   # front -> rear chamber
    hs = hs.cut(_radial_hole(s1 + 1.5, rq - 0.5, 101.0, 270.0, 6.0))
    # ports to the strut services (phase 2): oil in at the top through the ring hole; drain (bottom) and vent (-y) behind
    # the ring, from the rear chamber
    for deg, xp, r_b, r_h, r_in in ((90.0, xb, 12.0, 4.0, rq + 4.0), (270.0, q['x_port'], 18.0, 15.0, rq - 1.0),
                                    (180.0, q['x_port'], 16.0, 13.0, rq - 1.0)):
        hs = hs.fuse(Part.makeCylinder(r_b, JB2_RING['r'][1] - ro + 6.0, _polar(xp, ro - 6.0, deg), _radial(deg)))
        hs = hs.cut(_radial_hole(xp, r_in, JB2_RING['r'][1] + 1.0, deg, 2 * r_h))
    for k in range(8):                                                                         # 8 x M8 end cover
        hs = hs.cut(Part.makeCylinder(3.4, 16.0, _polar(q['x1'] - 15.0, 110.0, 45.0 * k), V(1, 0, 0)))
    hs = hs.cut(_radial_hole(xi0 - 3.0, rq + 0.5, ro + 1.0, 45.0, 8.0))                        # ISFD anti-rotation pin
    hs = hs.fuse(Part.makeCylinder(16.0, 14.0, _polar(q['x1'] - 8.0, ro - 4.0, 90.0), _radial(90.0))).cut(
        Part.makeCylinder(5.0, 20.0, _polar(q['x1'] - 8.0, ro - 2.0, 90.0), _radial(90.0)))   # M10 eye-bolt boss (top)
    out = {'JB2 bearing cartridge housing (one piece, from the rear)': (_clean(hs), '1.4313', 'housing')}
    # split labyrinth ring: gas side 3 teeth | buffer annulus | windback to the oil side, on the r 44.5 land
    c = SEAL_C['jb2']; r_land = rear_stub_profile()[6][1]
    ring = tube(s0, s1, 60.0, r_land + c + 1.3).fuse(tube(s0, s0 + 3.0, 61.5, 59.0))   # gas-side step: no reverse fit
    ring = ring.fuse(_teeth([s0 + 1.5, s0 + 4.0, s0 + 6.5], r_land + c + 1.3, r_land + c))
    ring = ring.cut(tube(xbuf - 2.0, xbuf + 2.0, 50.0, r_land + c + 1.0))
    ring = ring.fuse(tube(xbuf + 2.5, s1, r_land + c + 1.3, r_land + c)).cut(_windback(xbuf + 2.5, s1, r_land + c))
    for deg in (45.0, 135.0, 225.0, 315.0):
        ring = ring.cut(_radial_hole(xbuf, 48.0, 61.0, deg, 4.0))
    out['JB2 front seal ring (split, labyrinth + buffer + windback)'] = (Part.makeCompound(_splitz(ring)), '1.4313', 'carrier')
    cov = tube(q['x1'], q['x1'] + q['cover_t'], 125.0, 0.0).fuse(tube(q['x1'] - 6.0, q['x1'], rq - 0.05, rq - 7.0))
    for k in range(8):
        cov = cov.cut(Part.makeCylinder(4.5, q['cover_t'] + 2.0, _polar(q['x1'] - 1.0, 110.0, 45.0 * k), V(1, 0, 0)))
    out['JB2 end cover'] = (_clean(cov), '1.4313', 'housing')
    si, so_ = q['shield']; xs0 = q['shield_x0']
    sh = tube(q['x0'] - 1.0, q['x_port'] + 22.0, so_, si).fuse(tube(xs0, xs0 + 6.0, so_, 96.0))
    w = JB2_RING['key_w'] / 2 + 1.0
    for k in range(JB2_RING['keys']):                                                          # slots for the frame keys
        sh = sh.cut(_sector(0.5 * sum(JB2_RING['key_x']), so_ + 2.0, 22.5 + 45.0 * k - math.degrees(w / si), 2 * math.degrees(w / si),
                            JB2_RING['key_x'][1] - JB2_RING['key_x'][0] + 4.0))
    for deg, xp, r_h in ((90.0, xb, 15.0), (270.0, q['x_port'], 21.0), (180.0, q['x_port'], 19.0)):
        sh = sh.cut(_radial_hole(xp, si - 1.0, so_ + 1.0, deg, 2 * r_h))
    out['JB2 heat shield (ceramic fibre in 1.4828 foil)'] = (_clean(sh), 'ceramic fibre + 1.4828 foil', 'housing')
    return out


def _polar(x, r, deg):
    App, Part, V = _fc(); a = math.radians(deg); return V(x, r * math.cos(a), r * math.sin(a))


def _radial(deg):
    App, Part, V = _fc(); a = math.radians(deg); return V(0, math.cos(a), math.sin(a))


def _sector(xc, r, a0, span, L):
    App, Part, V = _fc()
    pts = [V(xc - L / 2, 0, 0)]
    for j in range(13):
        a = math.radians(a0 + span * j / 12); pts.append(V(xc - L / 2, r * math.cos(a), r * math.sin(a)))
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(L, 0, 0))


def thrust_bearing():
    """double-acting tilting-pad thrust bearing on the integral collar: 8 pads on the loaded aft side, 4 of the same size on
    the inactive forward side, leading-edge-groove lube fed through radial holes from the base-ring OD grooves (the
    housing grooves FB-1 / FB-2), base rings split at z = 0 with 2 anti-rotation dowels each. The housing is FB-1 / FB-2."""
    App, Part, V = _fc()
    out = {}
    c0, c1 = COLLAR['x0'], COLLAR['x1']; ri, ro, n, t = THRUST['ri'], THRUST['ro'], THRUST['n'], THRUST['t']
    e = 0.15                                                                 # half the axial end play
    pads = []
    for x0, m in ((c0 - e - t, THRUST['n_in']), (c1 + e, n)):
        for k in range(m):
            ring = tube(x0, x0 + t, ro, ri)
            pads.append(ring.common(_sector(x0 + t / 2, ro + 5, 360.0 / m * k + 3.0, 360.0 / n - 6.0, t + 2)))
    out['TB thrust pads %d + %d (steel + babbitt)' % (n, THRUST['n_in'])] = (Part.makeCompound(pads), 'steel + babbitt', 'pads')
    tc = 8.0; lube = _lube().get('bearings', {}).get('TB', {}).get('leg', {})
    rings = []
    for (xa, xz), m, d in (((c0 - e - t - tc, c0 - e - t), THRUST['n_in'], lube.get('d_feed_inactive_mm', 1.3)),
                           ((c1 + e + t, c1 + e + t + tc), n, lube.get('d_feed_loaded_mm', 1.6))):
        rg = tube(xa, xz, ro + 6, ri - 3)
        for k in range(m):                                                   # LEG feed: radial hole at each leading edge
            rg = rg.cut(_radial_hole(0.5 * (xa + xz), ri - 4, ro + 7, 360.0 / m * k + 1.5, d))
        for sy in (1, -1):
            rg = rg.cut(Part.makeCylinder(3.0, 12.0, V(0.5 * (xa + xz), sy * 0.5 * (ri + ro + 3), -6.0), V(0, 0, 1)))   # split dowels
        rg = rg.cut(_radial_hole(0.5 * (xa + xz), ro + 1.0, ro + 7, 135.0, 6.0))                  # anti-rotation pin
        rings += _splitz(rg)
    out['TB carrier rings (split)'] = (Part.makeCompound(rings), 'steel', 'carrier')
    return out


def build_all():
    parts = build_rotor()
    for row in ('R1', 'R2'):
        parts['A1000_%s disc with arms (cast MAR-M247)' % row] = (build_blisk_arms(row), 'MAR-M247', 'blisk')
    parts.update(journal_parts(X_BRG[0], 'JB1'))
    parts.update(journal_parts(X_BRG[1], 'JB2'))
    parts.update(thrust_bearing())
    parts.update(front_bearing_housing())
    parts.update(jb2_cartridge())
    return parts


def main_cad():
    """export every part, or with --only=<text> the parts whose name contains it (parts.json is merged, the replaced
    parts' old entries with the same name prefix up to the first '(' are dropped)"""
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_rotor'); out_f = os.path.join(ROOT, 'fusion', 'A1000_rotor')
    os.makedirs(out_c, exist_ok=True); os.makedirs(out_f, exist_ok=True)
    only = [a.split('=', 1)[1] for a in sys.argv if a.startswith('--only=')]
    rho = {'MAR-M247': 8540, 'IN718': 8190, '34CrNiMo6 QT': 7850, '17-4PH H1025': 7800, '17-4PH H1100': 7800, 'EN-GJS-400-18': 7100,
           '1.4313': 7700, 'ceramic fibre + 1.4828 foil': 700}
    info = {}
    App, Part, V = _fc()
    if only:
        allp = dict(build_rotor()) if any(o.startswith('RT-') for o in only) else {}
        for xb, tag in ((X_BRG[0], 'JB1'), (X_BRG[1], 'JB2')):
            allp.update(journal_parts(xb, tag))
        built = {k: v for k, v in allp.items() if any(o in k for o in only)}
    else:
        built = build_all()
    for name, (s, mat, grp) in built.items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(out_f, fn))
        rt = Part.Shape(); rt.read(os.path.join(out_f, fn))          # valid in memory is not enough: read the STEP back
        bb = s.BoundBox
        info[name] = dict(step=fn, material=mat, group=grp, valid=s.isValid() and rt.isValid(), solids=len(s.Solids), vol_cm3=round(s.Volume / 1e3, 2),
                          mass_kg=round(s.Volume * 1e-9 * rho.get(mat, 7850), 3), x=[round(bb.XMin, 2), round(bb.XMax, 2)],
                          r=round(max(bb.YMax, bb.ZMax), 2))
        print('%-50s %-6s solids %3d  %8.2f kg  x %.1f..%.1f  r %.1f' % (name, info[name]['valid'], len(s.Solids), info[name]['mass_kg'],
                                                                           bb.XMin, bb.XMax, info[name]['r']), flush=True)
    if only:                                                           # merge into the existing list
        old = json.load(open(os.path.join(out_f, 'parts.json')))['parts']
        new_pref = {k.split('(')[0] for k in info}
        info = dict({k: v for k, v in old.items() if k.split('(')[0] not in new_pref}, **info)
    json.dump(dict(frame='rotor frame mm, x = engine axis from the gearbox coupling face', x_offset_turbine=X_OFF,
                   joints=X_J, parts=info), open(os.path.join(out_f, 'parts.json'), 'w'), indent=1)


if '--cad' in sys.argv:
    main_cad()
