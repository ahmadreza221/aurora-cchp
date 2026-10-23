# GR180 version D2 - EXHAUST rev 2 (user feedback 2026-10-23): compact and COAXIAL - straight out of the back in line
# with the shaft, no elbow.  Bolted to the D2R turbine shroud flange (T-121: x 176, bore 70.7, OD 104, 6 x M6 on PCD 94,
# commit 20686b0) -> short conical diffuser (L <= 80, sizes from sim/variant_d/d2_intake_exhaust_calc.json 'exhaust.choice')
# -> 45 deg step into a straight DN125 (139.7 x 2) stub with the support lugs, drain and taps -> PN6 DN125 flange (+x).
# The turbine station is a parameter: GR180_D2_EXD_X / GR180_D2_EXD_D for the calc (then re-run this script).
# Hot parts 1.4828 (or 1.4541 fittings), TIG.  ENG frame mm.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_exhaust.py -> cad_out/variant_d/D2/EXHAUST/*.step
import sys, os, math, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

C = json.load(open(CALC))['exhaust']
CH = C['choice']; TB = C['turbine']; FLD = C['flange']
X_T = TB['x_flange']                         # turbine shroud flange face (176)
R_IN = TB['bore'] / 2                        # 35.35
L_FL = 8.0                                   # inlet flange plate
X_C0 = X_T + L_FL; X_C1 = X_C0 + CH['L_diffuser']
R_D = CH['D_diff_exit'] / 2
R_E = FLD['ID'] / 2; R_EO = FLD['OD'] / 2; T = 2.0
X_E0 = X_C1 + (R_E - R_D)                    # 45 deg step end
L_ST = 40.0                                  # straight stub incl. the flange
X_END = X_E0 + L_ST
F = FLD['fl']
X_F0 = X_END - F['b']
X_LUG = (X_E0 + 2.0, X_F0 - 2.0)
JK = 30.0                                    # insulation thickness
Y_LUG = 100.0                                # lug tip (pedestals on the rails at y +/-90)

for f in glob.glob(os.path.join(OUT, 'EXHAUST', '*.step')):    # obsolete rev-1 parts (DN200 elbow) must go
    os.remove(f)

parts = {}
# ---------------------------------------------------------------- EX-111 inlet flange (bolted to T-121)
fl_in = cyl(X_T, X_C0, 52.0, R_IN)
for h in bolt_holes(X_T, L_FL, 47.0, 6, 6.6, 30.0):
    fl_in = fl_in.cut(h)
parts['EX-111_Inlet_Flange_6xM6'] = (fl_in, '1.4828',
    '8 mm 1.4828 laser + turned, bore %.1f, OD 104, 6 x d6.6 on PCD 94 (30 deg start) = T-121 pattern; A286 M6 + Thermiculite 866 gasket' % (2 * R_IN))

# ---------------------------------------------------------------- EX-110 diffuser + step + stub weldment
prof = [(X_C0, R_IN), (X_C0 + 1.0, R_IN), (X_C1, R_D), (X_E0, R_E), (X_F0 + 3.0, R_E)]
wd = thick_revolve(prof, T, side=+1)


def r_out(x):
    if x <= X_C1:
        return R_IN + (R_D - R_IN) * (x - X_C0) / (X_C1 - X_C0) + T
    if x <= X_E0:
        return R_D + (x - X_C1) + T * 1.414
    return R_EO


bosses = [(X_C0 + 40.0, 45.0, 20.0, 6.0, 'TC M14x1.5'), (X_C0 + 8.0, 135.0, 12.0, 3.0, 'P1'),
          (0.5 * (X_LUG[0] + X_LUG[1]), 135.0, 12.0, 3.0, 'P2'), (0.5 * (X_LUG[0] + X_LUG[1]), 270.0, 22.0, 10.0, 'drain G1/4')]
for (x, a, d, h, tag) in bosses:
    r0 = r_out(x) - 1.5
    wd = wd.fuse(radial_boss(x, a, r0, r0 + 14.0, d))
for (x, a, d, h, tag) in bosses:
    wd = wd.cut(radial_boss(x, a, r_out(x) - 10, r_out(x) + 40, h))
inner = Part.Face(Part.makePolygon([V(X_C0 - 1, 0, 0), V(X_C0 - 1, 0, R_IN), V(X_C0, 0, R_IN), V(X_C1, 0, R_D), V(X_E0, 0, R_E),
                                    V(X_END + 1, 0, R_E), V(X_END + 1, 0, 0), V(X_C0 - 1, 0, 0)])).revolve(V(0, 0, 0), V(1, 0, 0), 360)
wd = wd.cut(inner).removeSplitter()
parts['EX-110_Diffuser_Stub_Weldment'] = (wd, '1.4828',
    'diffuser cone 2theta %.0f deg L%.0f (D%.1f -> D%.1f) rolled 2 mm 1.4828 + 45 deg step cone (spun) + %s stub %s; bosses: '
    'TC M14x1.5, 2 static taps M8, drain G1/4 at the bottom; TIG, stress relief, leak test' % (
        CH['two_theta'], CH['L_diffuser'], 2 * R_IN, 2 * R_D, C['DN_choice'], FLD['tube']))

# ---------------------------------------------------------------- EX-112 outlet flange (coaxial, +x)
fo = cyl(X_F0, X_END, F['D'] / 2, R_EO + 0.3)
for h in bolt_holes(X_F0, F['b'], F['K'] / 2, F['n'], F['hole'], 22.5):
    fo = fo.cut(h)
parts['EX-112_Flange_%s_PN6' % C['DN_choice']] = (fo, '1.4828',
    'flange %s with EN 1092-1 PN6 drilling (D%d K%d %d x %s), 12 mm laser-cut 1.4828 (or std type 01 16 mm 1.4541), slip-on, welded inside + outside' % (
        C['DN_choice'], F['D'], F['K'], F['n'], F['bolt']))

# ---------------------------------------------------------------- EX-113 support lugs (centre-line, slide in x)
lugs = []
for sgn in (1, -1):
    y0 = R_EO + 0.05
    lug = Part.makeBox(X_LUG[1] - X_LUG[0], Y_LUG - y0, 10, V(X_LUG[0], y0 if sgn > 0 else -Y_LUG, -5))
    slot = Part.makeBox(X_LUG[1] - X_LUG[0] - 8, 11, 20, V(X_LUG[0] + 4, 84.5 if sgn > 0 else -95.5, -10))
    lugs.append(lug.cut(slot))
parts['EX-113_Support_Lugs'] = (Part.makeCompound(lugs), '1.4828',
    '2 x 10 mm 1.4828 plates at the centre-line (y +/-), TIG to the stub, x-slot 11 wide at y +/-90 for an M10 shoulder bolt on FR-131')


# ---------------------------------------------------------------- EX-120 insulation jacket envelope
def run_solid(add):
    p = [V(X_C0 + 4, 0, 0), V(X_C0 + 4, 0, r_out(X_C0 + 4) + add), V(X_C1, 0, R_D + T * 1.45 + add), V(X_E0 - 0.8, 0, R_EO + add),
         V(X_F0 - 5.3, 0, R_EO + add), V(X_F0 - 5.3, 0, 0), V(X_C0 + 4, 0, 0)]
    return Part.Face(Part.makePolygon(p)).revolve(V(0, 0, 0), V(1, 0, 0), 360)


jk = run_solid(JK).cut(run_solid(0.5))
for (x, a, d, h, tag) in bosses:
    jk = jk.cut(radial_boss(x, a, 20, 200, d + 8))
for sgn in (1, -1):                           # lugs + pedestal zone
    jk = jk.cut(Part.makeBox(X_LUG[1] - X_LUG[0] + 40, 60, 160, V(X_LUG[0] - 25, 68 if sgn > 0 else -128, -150)))
jk2 = jk.removeSplitter()
jk = jk2 if jk2.isValid() else jk
parts['EX-120_Insulation_Jacket_env'] = (jk, 'blanket',
    'removable 30 mm AES / ceramic-fibre blanket, 1.4301 foil + mesh skin, lacing hooks, split at y = 0; cut-outs for lugs, pedestals, TC, taps, drain')

meta = dict(subsystem='EXHAUST', rev=2, frame='ENG mm', calc='sim/variant_d/d2_intake_exhaust_calc.json', choice=CH['name'],
            dp=dict(dp0_incl_exit_Pa=CH['dp0_incl_exit_Pa'], pct_of_P0=CH['pct_of_P0'], Cp_system=CH['Cp_system'],
                    cost_vs_ideal_kW=CH['cost_vs_ideal_kW'], DN125_minus_DN150_kW=C['DN125_minus_DN150_kW'],
                    gain_vs_meanline_dump_kW=CH['gain_vs_no_diffuser_dump_kW']),
            interfaces=dict(
                inlet=dict(x=X_T, ID=2 * R_IN, joint='bolted to T-121: OD 104, 6 x M6 on PCD 94 (30 deg), Thermiculite gasket'),
                outlet=dict(x=X_END, dir='+x (coaxial)', std='EN 1092-1 PN6 %s (D%d K%d %d x %s)' % (C['DN_choice'], F['D'], F['K'], F['n'], F['bolt']),
                            max_r=F['D'] / 2, downstream='user duct / silencer with its own support + bellows'),
                lugs=dict(x=list(X_LUG), y=[R_EO, Y_LUG], slot_y=90.0, z=[-5, 5], slide='x'),
                drain=dict(x=bosses[3][0], dir='-z', size='G1/4'), thermocouple=dict(x=bosses[0][0], angle_deg=45, size='M14x1.5'),
                p_taps=[dict(x=bosses[1][0], angle_deg=135), dict(x=bosses[2][0], angle_deg=135)],
                stations=dict(cone=[X_C0, X_C1], step=[X_C1, X_E0], stub=[X_E0, X_END])))
rows = export(parts, 'EXHAUST', meta)
print('exhaust x %.0f..%.0f (length %.0f), max radius %.0f (flange)' % (X_T, X_END, X_END - X_T, F['D'] / 2))
