# GR180 version D2 - compact EXHAUST: short conical diffuser behind the exducer -> 45 deg expansion cone -> DN200
# straight spool (support lugs, drain) -> DN200 90 deg SR elbow turning UP -> EN 1092-1 PN6 DN200 flange facing +z
# (bellows + duct support on the plant side, research decision sim/variant_d/d_decisions.json).
# Sizes come from sim/variant_d/d2_intake_exhaust_calc.json ('exhaust.choice': shortest diffuser within 0.8 kPa of the
# best static recovery).  The exducer station is a parameter (bought turbo wheel: exit ~D60-66 at x 190-200):
#   GR180_D2_EXD_D=64 GR180_D2_EXD_X=195 python3 sim/variant_d/d2_intake_exhaust_calc.py  (then re-run this script)
# Hot parts 1.4828 (or 321 / 1.4541 fittings), TIG; the inlet V-band flange is the only part that follows the wheel.
# ENG frame mm.  Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_exhaust.py -> cad_out/variant_d/D2/EXHAUST/*.step
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

C = json.load(open(CALC))['exhaust']
CH = C['choice']
X6 = C['meanline']['x_exducer_exit']          # shroud end face (RT-121 ends at x 199)
R_IN = CH['D_in'] / 2                          # shroud bore (74.8 -> r 37.4)
L_D = CH['L_diffuser']; R_D = CH['D_diff_exit'] / 2
R_E = 215.1 / 2; T = 2.0; R_EO = R_E + T       # DN200 tube 219.1 x 2.0
R_B = CH['elbow_R']                            # 203.2 (B16.9 SR, R/D ~ 0.95)
L_FL = 8.0                                     # V-band flange ring length
X_C0 = X6 + L_FL                               # diffuser cone start
X_C1 = X_C0 + L_D                              # diffuser cone end
X_E0 = X_C1 + (R_E - R_D)                      # 45 deg expansion cone end
L_SP = 40.0
X_EL = X_E0 + L_SP                             # elbow inlet plane
XC_EL, ZC_EL = X_EL + R_B, R_B                 # elbow outlet centre (x), outlet plane z
L_STUB = 40.0
FL = C['flange']                               # PN6 DN200: D 320, K 280, 8 x 18, b 20
Z_FL1 = ZC_EL + L_STUB; Z_FL0 = Z_FL1 - FL['b']
JK = 50.0                                      # insulation thickness

parts = {}
# ---------------------------------------------------------------- EX-111 inlet V-band flange ring (follows the wheel)
vb = cyl(X6, X_C0, 50.0, R_IN)
parts['EX-111_VBand_Inlet_Flange'] = (vb, '1.4828',
    'turned 1.4828 ring ID %.1f, V-band profile OD 100 (40 deg flanks); mates a V-band flange on the RT-121 shroud end; Inconel V-band clamp' % (2 * R_IN))

# ---------------------------------------------------------------- EX-110 diffuser + expansion cone + spool + elbow + stub
prof = [(X_C0, R_IN), (X_C0 + 1.0, R_IN), (X_C1, R_D), (X_E0, R_E), (X_EL, R_E)]
straight = thick_revolve(prof, T, side=+1)                      # material outside the wetted surface
ring = Part.Face(Part.Wire(Part.makeCircle(R_EO, V(X_EL, 0, 0), V(1, 0, 0))))
ring = ring.cut(Part.Face(Part.Wire(Part.makeCircle(R_E, V(X_EL, 0, 0), V(1, 0, 0)))))
elbow = ring.revolve(V(X_EL, 0, R_B), V(0, -1, 0), 90)
stub = Part.makeCylinder(R_EO, L_STUB - 3, V(XC_EL, 0, ZC_EL), V(0, 0, 1)).cut(Part.makeCylinder(R_E, L_STUB + 2, V(XC_EL, 0, ZC_EL - 1), V(0, 0, 1)))
wd = straight.fuse(elbow).fuse(stub)


def r_out(x):                                                   # outer wall radius along the straight run
    if x <= X_C1:
        return R_IN + (R_D - R_IN) * (x - X_C0) / L_D + T
    if x <= X_E0:
        return R_D + (x - X_C1) + T * 1.414
    return R_EO


bosses = [(X_C0 + 50, 45.0, 22.0, 6.0, 'TC'), (X_C0 + 10, 135.0, 14.0, 3.0, 'P1'), (X_E0 + 20, 135.0, 14.0, 3.0, 'P2'),
          (X_E0 + 12, 270.0, 28.0, 14.0, 'drain')]
for (x, a, d, h, tag) in bosses:
    r0 = r_out(x) - 1.5
    wd = wd.fuse(radial_boss(x, a, r0, r0 + (22.0 if tag == 'drain' else 16.0), d))
for (x, a, d, h, tag) in bosses:
    wd = wd.cut(radial_boss(x, a, r_out(x) - 10, r_out(x) + 40, h))
inner = Part.Face(Part.makePolygon([V(X_C0 - 1, 0, 0), V(X_C0 - 1, 0, R_IN), V(X_C0, 0, R_IN), V(X_C1, 0, R_D), V(X_E0, 0, R_E),
                                    V(X_EL + 0.01, 0, R_E), V(X_EL + 0.01, 0, 0), V(X_C0 - 1, 0, 0)])).revolve(V(0, 0, 0), V(1, 0, 0), 360)
wd = wd.cut(inner).removeSplitter()
parts['EX-110_Diffuser_Elbow_Weldment'] = (wd, '1.4828',
    'diffuser cone 2theta %.0f deg L %.0f (D%.1f -> D%.1f) + 45 deg cone, 1.4828 2 mm rolled/spun; DN200 spool 219.1x2 L40; '
    'DN200 90 deg SR elbow R%.0f (EN 10253-4 / B16.9, 1.4541 or 1.4828); stub L40; bosses: TC M14x1.5, 2 P-taps M8, drain G1/2' % (
        CH['two_theta'], L_D, 2 * R_IN, 2 * R_D, R_B))

# ---------------------------------------------------------------- EX-112 PN6 DN200 flange facing +z
fl = Part.makeCylinder(FL['D'] / 2, FL['b'], V(XC_EL, 0, Z_FL0), V(0, 0, 1)).cut(Part.makeCylinder(R_EO + 0.3, FL['b'] + 2, V(XC_EL, 0, Z_FL0 - 1), V(0, 0, 1)))
for k in range(8):
    th = math.radians(22.5 + 45 * k)
    fl = fl.cut(Part.makeCylinder(FL['hole'] / 2, FL['b'] + 2, V(XC_EL + FL['K'] / 2 * math.cos(th), FL['K'] / 2 * math.sin(th), Z_FL0 - 1), V(0, 0, 1)))
parts['EX-112_Flange_DN200_PN6'] = (fl, '1.4541', 'EN 1092-1 type 01 plate flange DN200 PN6 (D320 K280 8 x M16), 1.4541, slip-on, fillet welded inside + outside')

# ---------------------------------------------------------------- EX-113 support lugs (centre-line, slide in x)
lugs = []
for sgn in (1, -1):
    y0 = R_EO + 0.1
    lug = Part.makeBox(24, 165 - y0, 12, V(X_E0 + 8, y0 if sgn > 0 else -165, -6))
    slot = Part.makeBox(14, 13, 20, V(X_E0 + 13, 146 if sgn > 0 else -159, -10))
    lugs.append(lug.cut(slot))
parts['EX-113_Support_Lugs'] = (Part.makeCompound(lugs), '1.4828',
    '2 x 12 mm 1.4828 plates at the centre-line (y +/-), TIG to the spool, slot 14 (x) x 13 for an M12 shoulder bolt: x-sliding, sit on FR-131 pads')

# ---------------------------------------------------------------- EX-120 insulation jacket envelope (removable blankets)
def solid_run(add):
    p = [V(X_C0 + 4, 0, 0), V(X_C0 + 4, 0, r_out(X_C0 + 4) + add), V(X_C1, 0, R_D + T * 1.45 + add), V(X_E0 - 0.8, 0, R_EO + add),
         V(X_EL, 0, R_EO + add), V(X_EL, 0, 0), V(X_C0 + 4, 0, 0)]
    s = Part.Face(Part.makePolygon(p)).revolve(V(0, 0, 0), V(1, 0, 0), 360)
    e = Part.Face(Part.Wire(Part.makeCircle(R_EO + add, V(X_EL, 0, 0), V(1, 0, 0)))).revolve(V(X_EL, 0, R_B), V(0, -1, 0), 90)
    st = Part.makeCylinder(R_EO + add, Z_FL0 - 6 - ZC_EL, V(XC_EL, 0, ZC_EL), V(0, 0, 1))
    return s.fuse(e).fuse(st)


jk = solid_run(JK).cut(solid_run(0.5))
for (x, a, d, h, tag) in bosses:
    jk = jk.cut(radial_boss(x, a, 20, 220, d + 10))
for l in lugs:
    bb = l.BoundBox
    jk = jk.cut(Part.makeBox(bb.XLength + 10, bb.YLength, bb.ZLength + 10, V(bb.XMin - 5, bb.YMin, bb.ZMin - 5)))
parts['EX-120_Insulation_Jacket_env'] = (jk.removeSplitter(), 'blanket',
    'removable blankets: 50 mm 1260 C ceramic-fibre / bio-soluble wool, 1.4301 foil/mesh skin, lacing hooks, split along the y = 0 plane; cut-outs for lugs, TC, taps, drain')

meta = dict(subsystem='EXHAUST', frame='ENG mm', calc='sim/variant_d/d2_intake_exhaust_calc.json', choice=CH['name'],
            dp=dict(dp0_total_Pa=CH['dp0_total_Pa'], dp0_pct=CH['dp0_pct_of_P0'], duct_pct=CH['duct_pct_of_P0'],
                    p6_minus_p_flange_Pa=CH['p6_minus_p_flange_Pa'], turbine_gain_vs_dump_kW=CH['turbine_work_gain_vs_dump_kW']),
            interfaces=dict(
                inlet=dict(x=X6, ID=2 * R_IN, joint='V-band OD 100 on the RT-121 shroud end (turbine side to add a V-band flange)'),
                outlet=dict(centre=[round(XC_EL, 1), 0.0, round(Z_FL1, 1)], dir='+z', std='EN 1092-1 PN6 DN200 (D320 K280 8 x M16)',
                            downstream='DN200 bellows (axial + lateral) and its own duct support - plant side'),
                lugs=dict(x=[X_E0 + 8, X_E0 + 32], y=[R_EO, 165], z=[-6, 6], slot_centre_x=X_E0 + 20, slide='x'),
                drain=dict(x=X_E0 + 12, dir='-z', size='G1/2'), thermocouple=dict(x=X_C0 + 50, angle_deg=45, size='M14x1.5'),
                p_taps=[dict(x=X_C0 + 10, angle_deg=135), dict(x=X_E0 + 20, angle_deg=135)],
                stations=dict(cone=[X_C0, X_C1], expansion=[X_C1, X_E0], spool=[X_E0, X_EL], elbow_in=X_EL, elbow_R=R_B)))
rows = export(parts, 'EXHAUST', meta)
print('flange top centre x %.1f z %.1f; overall x %.0f..%.0f' % (XC_EL, Z_FL1, X6, XC_EL + FL['D'] / 2))
