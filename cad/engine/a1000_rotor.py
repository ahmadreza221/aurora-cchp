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
Bearings: tilting-pad journals (5 pads, load between pads) in integral S-spring squeeze-film damper rings (ISFD),
double-acting tilting-pad thrust bearing on the integral collar, at the cold end.

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
STUD = dict(n=16, d=10.0, r=76.0, hole=10.5, nut_h=6.0, nut_af=14.0, pre_kN=27.0)   # M10x1.25 MJ, IN718
CURVIC_HOT = dict(ri=62.0, ro=90.0, N=48, phi=30.0, h=2.6)        # bolted curvic on every hot flange face


def arm_x(row, side):
    """(hub face x, joint face x) of a blisk arm: side 'f' (forward) or 'a' (aft)"""
    xf, xa = HUB[row]
    if side == 'f': return xf, xf - ARM['cav'] - ARM['tf']
    return xa, xa + ARM['cav'] + ARM['tf']


X_J = dict(drum_R1=arm_x('R1', 'f')[1], R1_R2=0.5 * (arm_x('R1', 'a')[1] + arm_x('R2', 'f')[1]), R2_stub=arm_x('R2', 'a')[1])


def disc_profile_arms(row):
    """cast blisk meridional (x, r) outline in the rotor frame: rev 5 bore-less disc + forward / aft arms and flanges"""
    q = A.DISC[row]
    rh = A.row_radius(row, 0.0); x0, x1 = A.X_LE[row] - A.PLAT_OVH, A.X_TE[row] + A.PLAT_OVH; xm = 0.5 * (x0 + x1)
    r_rim = rh - q['rim_d']; tr, th, hw = q['t_rim'] / 2, q['t_hub'] / 2, q['hub_w'] / 2
    o = X_OFF; ri, ro, rf, c, t = ARM['ri'], ARM['ro'], ARM['rf'], ARM['cav'], ARM['tf']
    xa, xf = xm + hw + o, xm - hw + o
    xj_a = X_J['R1_R2'] if row == 'R1' else X_J['R2_stub']
    xj_f = X_J['drum_R1'] if row == 'R1' else X_J['R1_R2']
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
CURVIC_C = dict(stub_I1=dict(ri=44.0, ro=58.0, N=36), I1_spc=dict(ri=50.0, ro=70.0, N=36),
                spc_I2=dict(ri=52.0, ro=72.0, N=36), I2_drum=dict(ri=55.0, ro=75.0, N=36))
R_HUB_IN = (60.0, 80.0)                                           # impeller inducer hub radii (flow-path hub at the faces)
JOURNAL = dict(D=100.0, L=45.0)                                 # tilting-pad journals (sim/engine/a1000_rotor_stack.py)
COLLAR = dict(x0=146.0, x1=166.0, ro=82.0)                       # integral thrust collar
THRUST = dict(ri=56.0, ro=78.0, n=8, t=12.0)                     # thrust pads per side (inner / outer radius, thickness)
BACKFACE = dict(r_seal=200.0, r_feed=120.0)                      # impeller 2 back face: labyrinth at r 200, compressor-delivery
                                                                 # air fed at r 120 (pressurised back-face cavity, thrust balance)
BAL_SEAL_R = 85.0                                               # drum balance-piston labyrinth radius (thrust balance)
SFD = dict(R=80.0, L=35.0, c=0.13)                               # squeeze-film damper land radius, length, radial clearance
ISFD = dict(n=8, l=43.0, t=4.2, ri=74.0, ro=92.0, span=30.0)      # integral S-spring damper ring (wire EDM): springs, beam
                                                                 # length / radial thickness, ring radii, spring arc [deg]
X_BRG = (95.0, RD.rotor('A')['brg'][1])                          # journal 1 moved 15 mm forward (thrust bearing behind it)


def stub_profile():
    """front stub shaft 34CrNiMo6: coupling flange, seal, journal 1, integral thrust collar, inlet seal, front curvic"""
    D, L = JOURNAL['D'], JOURNAL['L']; xb = X_BRG[0]; c0, c1, cro = COLLAR['x0'], COLLAR['x1'], COLLAR['ro']
    return [(0.0, 35.0), (0.0, 80.0), (14.0, 80.0), (14.0, 45.0), (40.0, 45.0), (40.0, 47.0),
            (xb - L / 2 - 6, 47.0), (xb - L / 2 - 6, D / 2), (xb + L / 2 + 6, D / 2), (xb + L / 2 + 6, 52.0),
            (c0, 52.0), (c0, cro), (c1, cro), (c1, 52.0), (c1 + 6, 52.0), (c1 + 6, 48.0), (X_I1[0] - 4, 48.0),
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
    return [(xj, 25.0), (xj, ARM['rf']), (xj + tf, ARM['rf']), (xj + tf, 60.0), (xj + tf + 3, 60.0), (xj + tf + 7, 49.5),
            (xb - L / 2 - 6, 49.5), (xb - L / 2 - 6, D / 2), (xb + L / 2 + 6, D / 2), (xb + L / 2 + 6, 46.0),
            (xb + L / 2 + 30, 46.0), (xb + L / 2 + 30, 25.0)]


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
    # studs + nuts of the three hot joints (nuts in the cavity behind the cast flange)
    for tag, xj_, side in (('drum - R1', X_J['drum_R1'], 'R1f'), ('R1 - R2', X_J['R1_R2'], 'R1a'), ('R2 - rear stub', X_J['R2_stub'], 'R2a')):
        tf = ARM['tf']
        if side == 'R1f':      # stud from the drum flange (front) through the R1 flange, nut aft of it
            st, nu = stud_set(xj_ - tf, xj_ + tf + STUD['nut_h'] + 2, xj_ + tf, +1, STUD['n'], STUD['r'])
        elif side == 'R1a':    # stud in the R2 flange insert, through the R1 flange, nut in front of it
            st, nu = stud_set(xj_ - tf - STUD['nut_h'] - 2, xj_ + tf, xj_ - tf, -1, STUD['n'], STUD['r'])
        else:                  # stud from the rear-stub flange forward through the R2 flange, nut in front of it
            st, nu = stud_set(xj_ - tf - STUD['nut_h'] - 2, xj_ + tf, xj_ - tf, -1, STUD['n'], STUD['r'])
        out['RT-11%d Studs + nuts %s (16 x M10)' % (len([k for k in out if 'Studs' in k]) + 1, tag)] = (
            Part.makeCompound(st + nu), 'IN718 / Waspaloy nuts', 'studs')
    return out


def build_blisk_arms(row):
    """the cast blisk disc with arms and flanges (replaces fusion/A1000/A1000_<row>_disc.step in the rotor model):
    revolved outline + curvic teeth and stud holes on both flange faces. Blades: unchanged rev 5 pieces."""
    App, Part, V = _fc()
    s = revolve(disc_profile_arms(row))
    # the rev 5 disc seam is rotated by half a blade pitch: irrelevant for a solid of revolution
    xa = X_J['R1_R2'] if row == 'R1' else X_J['R2_stub']
    xf = X_J['drum_R1'] if row == 'R1' else X_J['R1_R2']
    ch = CURVIC_HOT
    s = curvic_face(s, xf, +1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.5)          # forward face: mates the part in front
    s = curvic_face(s, xa, -1, ch['ri'], ch['ro'], ch['N'], ch['h'], 0.0)          # aft face: mates the part behind
    s = s.cut(holes(xf - ch['h'], xf + ARM['tf'] + 1, STUD['r'], STUD['hole'], STUD['n']))
    s = s.cut(holes(xa - ARM['tf'] - 1, xa + ch['h'], STUD['r'], STUD['hole'], STUD['n']))
    return s.removeSplitter()


# ------------------------------------------------------------------------------------------------ bearings (FreeCAD)
def tilting_pad_journal(xb, tag, walls=(True, True)):
    """5-pad tilting-pad journal (load between pads, 60 % pivot offset) in a split carrier; the carrier sits in an
    integral squeeze-film damper ring (ISFD: 8 wire-EDM S-springs between an inner and an outer ring, squeeze-film lands
    under the springs, radial clearance 0.13 mm, O-ring end seals), the same axial length as the bearing; cartridge
    housing with labyrinth oil seals. walls: (front, rear) seal walls (the front bearing shares its rear wall with the
    thrust bearing). Returns {name: (shape, material, group)}"""
    App, Part, V = _fc()
    D, L = JOURNAL['D'], JOURNAL['L']; R = D / 2
    r_pad, r_car = R + 10.0, ISFD['ri']
    out = {}
    pads = []
    for k in range(5):
        a0 = 72.0 * k + 36.0 - 26.0                                           # 52 deg pads, load between pads (bottom)
        ring = tube(xb - L / 2, xb + L / 2, r_pad, R + 0.12)
        pad = ring.common(_sector(xb, r_pad + 5, a0, 52.0, L + 2))
        pad = pad.fuse(Part.makeCylinder(5.0, 4.6, _polar(xb, r_pad - 1.0, a0 + 31.2), _radial(a0 + 31.2))).removeSplitter()
        pads.append(pad)
    out['%s tilting pads x5 (steel + babbitt)' % tag] = (Part.makeCompound(pads), 'steel + babbitt', 'pads')
    carrier = tube(xb - L / 2 - 6, xb + L / 2 + 6, r_car, r_pad + 4.0)
    carrier = carrier.fuse(tube(xb - L / 2 - 6, xb - L / 2 - 1, r_car, R + 0.4)).fuse(tube(xb + L / 2 + 1, xb + L / 2 + 6, r_car, R + 0.4))
    for k in range(5):                                                         # oil feed nozzles between the pads
        carrier = carrier.cut(Part.makeCylinder(1.5, 30.0, _polar(xb, R + 2.0, 72.0 * k), _radial(72.0 * k)))
    out['%s pad carrier + end plates (split)' % tag] = (carrier.removeSplitter(), 'steel', 'carrier')
    q = ISFD; Lf = SFD['L'] + 8.0; x0, x1 = xb - Lf / 2, xb + Lf / 2
    r1, r2 = q['ri'] + 4.0, q['ro'] - 6.0                                       # inner ring OD, outer ring ID
    rb0 = 0.5 * (r1 + r2) - q['t'] / 2; rb1 = rb0 + q['t']
    isfd = tube(x0, x1, r1, q['ri']).fuse(tube(x0, x1, q['ro'], r2))
    for k in range(q['n']):
        a = 360.0 / q['n'] * k
        beam = tube(x0, x1, rb1, rb0).common(_sector(xb, r2 + 1, a, q['span'], Lf))
        w_in = tube(x0, x1, rb0 + 0.5, r1 - 0.5).common(_sector(xb, r2 + 1, a, 3.0, Lf))
        w_out = tube(x0, x1, r2 + 0.5, rb1 - 0.5).common(_sector(xb, r2 + 1, a + q['span'] - 3.0, 3.0, Lf))
        isfd = isfd.fuse([beam, w_in, w_out])
    isfd = isfd.cut(tube(x0 + 2, x0 + 5, q['ro'] + 0.1, q['ro'] - 2.4)).cut(tube(x1 - 5, x1 - 2, q['ro'] + 0.1, q['ro'] - 2.4))
    out['%s integral S-spring damper ring (ISFD, %d springs)' % (tag, q['n'])] = (isfd.removeSplitter(), '17-4PH H1100', 'cage')
    ro_h = q['ro'] + 38.0; xf, xr = xb - L / 2 - (20 if walls[0] else 6), xb + L / 2 + (20 if walls[1] else 6)
    hs = tube(xf, xr, ro_h, q['ro'] + 0.02)
    if walls[0]: hs = hs.fuse(tube(xf, xb - L / 2 - 7, ro_h, R + 1.0))
    if walls[1]: hs = hs.fuse(tube(xb + L / 2 + 7, xr, ro_h, R + 1.0))
    hs = hs.fuse(Part.makeCylinder(12.0, 40.0, V(xb, 0, ro_h - 5), V(0, 0, 1)))            # oil inlet boss (top)
    hs = hs.fuse(Part.makeCylinder(18.0, 40.0, V(xb + (L / 2 + 2 if walls[1] else 0.0), 0, -ro_h + 5), V(0, 0, -1)))   # drain (bottom)
    hs = hs.cut(Part.makeCylinder(4.0, 70.0, V(xb, 0, q['ro'] - 2), V(0, 0, 1)))           # pad / damper oil feed
    hs = hs.cut(holes(xf - 1, xr + 1, ro_h - 14.0, 13.0, 8, 0.0))                          # 8 x M12 cartridge bolts
    for w, xs in ((walls[0], xf + 5), (walls[1], xr - 5)):                                 # labyrinth oil-seal teeth
        if not w: continue
        for k in range(3):
            xk = xs - 4 + 4 * k
            hs = hs.fuse(revolve([(xk - 0.8, R + 1.0), (xk + 0.8, R + 1.0), (xk + 0.25, R + 0.25), (xk - 0.25, R + 0.25)]))
    out['%s bearing cartridge housing' % tag] = (hs.removeSplitter(), 'EN-GJS-400-18 (front) / 1.4313 (rear)', 'housing')
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
    """double-acting tilting-pad thrust bearing on the integral collar (2 x 8 pads, leading-edge-groove lube), split carrier
    rings, a housing that also closes the rear of journal 1 and carries the inlet-side labyrinth + windback seal"""
    App, Part, V = _fc()
    out = {}
    c0, c1 = COLLAR['x0'], COLLAR['x1']; ri, ro, n, t = THRUST['ri'], THRUST['ro'], THRUST['n'], THRUST['t']
    e = 0.15                                                                 # half the axial end play
    pads = []
    for x0 in (c0 - e - t, c1 + e):
        for k in range(n):
            ring = tube(x0, x0 + t, ro, ri)
            pads.append(ring.common(_sector(x0 + t / 2, ro + 5, 360.0 / n * k + 3.0, 360.0 / n - 6.0, t + 2)))
    out['TB thrust pads 2 x 8 (steel + babbitt)'] = (Part.makeCompound(pads), 'steel + babbitt', 'pads')
    tc = 8.0
    car = tube(c0 - e - t - tc, c0 - e - t, ro + 6, ri - 3).fuse(tube(c1 + e + t, c1 + e + t + tc, ro + 6, ri - 3))
    out['TB carrier rings (split)'] = (car, 'steel', 'carrier')
    xb = X_BRG[0]; xf = xb + JOURNAL['L'] / 2 + 6; xr = c1 + e + t + tc + 14
    hs = tube(xf, xr, ISFD['ro'] + 38.0, ro + 6.05)
    hs = hs.fuse(tube(xf, xf + 2, ISFD['ro'] + 38.0, JOURNAL['D'] / 2 + 3.5))
    hs = hs.fuse(tube(xr - 12, xr, ISFD['ro'] + 38.0, 49.0))
    for k in range(4):
        xk = xr - 10 + 3 * k
        hs = hs.fuse(revolve([(xk - 0.7, 49.0), (xk + 0.7, 49.0), (xk + 0.2, 48.25), (xk - 0.2, 48.25)]))
    hs = hs.fuse(Part.makeCylinder(10.0, 40.0, V(0.5 * (c0 + c1), 0, ISFD['ro'] + 33.0), V(0, 0, 1)))
    hs = hs.fuse(Part.makeCylinder(16.0, 40.0, V(0.5 * (c0 + c1), 0, -ISFD['ro'] - 33.0), V(0, 0, -1)))
    out['TB thrust housing + inlet seal'] = (hs.removeSplitter(), 'EN-GJS-400-18', 'housing')
    return out


def build_all():
    parts = build_rotor()
    for row in ('R1', 'R2'):
        parts['A1000_%s disc with arms (cast MAR-M247)' % row] = (build_blisk_arms(row), 'MAR-M247', 'blisk')
    parts.update(tilting_pad_journal(X_BRG[0], 'JB1', walls=(True, False)))
    parts.update(tilting_pad_journal(X_BRG[1], 'JB2'))
    parts.update(thrust_bearing())
    return parts


def main_cad():
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_rotor'); out_f = os.path.join(ROOT, 'fusion', 'A1000_rotor')
    os.makedirs(out_c, exist_ok=True); os.makedirs(out_f, exist_ok=True)
    rho = {'MAR-M247': 8540, 'IN718': 8190, '34CrNiMo6 QT': 7850, '17-4PH H1025': 7800, '17-4PH H1100': 7800}
    info = {}
    for name, (s, mat, grp) in build_all().items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(out_f, fn))
        bb = s.BoundBox
        info[name] = dict(step=fn, material=mat, group=grp, valid=s.isValid(), solids=len(s.Solids), vol_cm3=round(s.Volume / 1e3, 2),
                          mass_kg=round(s.Volume * 1e-9 * rho.get(mat, 7850), 3), x=[round(bb.XMin, 2), round(bb.XMax, 2)],
                          r=round(max(bb.YMax, bb.ZMax), 2))
        print('%-50s %-6s solids %3d  %8.2f kg  x %.1f..%.1f  r %.1f' % (name, s.isValid(), len(s.Solids), info[name]['mass_kg'],
                                                                           bb.XMin, bb.XMax, info[name]['r']), flush=True)
    json.dump(dict(frame='rotor frame mm, x = engine axis from the gearbox coupling face', x_offset_turbine=X_OFF,
                   joints=X_J, parts=info), open(os.path.join(out_f, 'parts.json'), 'w'), indent=1)


if '--cad' in sys.argv:
    main_cad()
