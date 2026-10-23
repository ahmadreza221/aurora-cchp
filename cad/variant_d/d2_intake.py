# GR180 version D2 - INTAKE: axisymmetric radial-inlet plenum around the rear of the generator pod.
# Air path: coaxial GT filter cartridge pair (445/324 x 660, F9, research decision sim/variant_d/d_decisions.json) ->
# bore annulus 324/110 along the pod (pod cooled by the intake air) -> tube-sheet opening ID 324 -> plenum: the flow
# turns round the pod tail fairing (R15) and the plenum fillet (R40) -> radially inward through the FOD guard and the
# 3 pod struts (3, never 4 per rev) -> round the v13A intake lip into the compressor eye.
# Build 1 runs without the cartridge: the open tube sheet + the stainless FOD guard on the radial gap.
# Sheet metal: spun / rolled 1.4301, laser-cut plates, TIG.  The pod internals, struts, quill and bearings are NOT
# designed here (generator pod bearings at x -266 / -136 stay untouched: nothing clamps the pod near them).
# ENG frame mm.  Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_intake.py -> cad_out/variant_d/D2/INTAKE/*.step
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

X_DISH = -46.3          # dish wetted face = v13A intake front flange face (Intake.step flange x -46.3..-41.8, OD 94)
R_LIP = 47.5            # dish inner edge (v13A intake flange OD 47.0 + 0.5)
R_PL = 162.0            # plenum wetted radius = tube-sheet opening ID 324
R_FIL = 40.0            # plenum fillet
X_TS = -130.0           # tube sheet rear face (front / gasket face at X_TS - 8)
T_TS = 6.0
R_TS = 250.0            # tube sheet OD 500 (cartridge OD 445 + gasket land)
L_CART = 660.0; N_CART = 2   # cartridge pair (cyl/cyl)
SH = struts(0.75)        # strut clearance holes (strut d8 + 2 x 0.75)

parts = {}
# ---------------------------------------------------------------- INT-110 plenum bell: dish + fillet + cylinder
prof = [(X_DISH, R_LIP), (X_DISH, R_PL - R_FIL)] + arc(X_DISH - R_FIL, R_PL - R_FIL, R_FIL, 0, 90)[1:] + [(X_TS, R_PL)]
bell = thick_revolve(prof, 2.0, side=-1)
pad = Part.makeBox(30, 80, 24, V(-124, -40, 150)).cut(cyl(-130, -86, R_PL + 1.0))      # service port pad (top)
for (y, x, d) in ((-18, -109, 40.5), (22, -116, 21.5), (22, -102, 21.5)):                 # M40 power gland, 2 x G1/2 glycol/oil
    pad = pad.cut(Part.makeCylinder(d / 2, 40, V(x, y, 140), V(0, 0, 1)))
bell = bell.fuse(pad).fuse(radial_boss(-110, 45, R_PL + 1, R_PL + 12, 14, 0))           # static-pressure tap boss
bell = bell.cut(cyl(-131, -86, R_PL)).cut(Part.makeCylinder(2.0, 30, V(-110, 0, 0) + V(0, math.cos(math.radians(45)), math.sin(math.radians(45))) * (R_PL - 5), V(0, math.cos(math.radians(45)), math.sin(math.radians(45)))))
for s in SH:
    bell = bell.cut(s)
parts['INT-110_Plenum_Bell'] = (bell.removeSplitter(), '1.4301',
    'spun 2 mm 1.4301 (dish + R40 fillet + D328 x 2 cylinder), 3 strut holes d9.5, service pad (M40 power gland, 2 x G1/2), P-tap')

# ---------------------------------------------------------------- INT-111 tube sheet (filter interface FI-1) + yoke tabs
ts = cyl(X_TS - T_TS, X_TS, R_TS, R_PL)
for h in bolt_holes(X_TS - T_TS, T_TS, 237.0, 1, 13.0, 250.0) + bolt_holes(X_TS - T_TS, T_TS, 237.0, 1, 13.0, 290.0):
    ts = ts.cut(h)                                               # 2 x M12 to the front saddle (250 / 290 deg)
for k in range(3):                                               # 3 yoke tabs (30/150/270 deg, between the struts)
    th = math.radians(30 + 120 * k)
    tab = Part.makeBox(14, 16.5, 20, V(X_TS - T_TS, R_PL - 18, -10))
    tab.rotate(V(0, 0, 0), V(1, 0, 0), math.degrees(th))
    hole = Part.makeCylinder(6.5, 20, V(X_TS - T_TS - 2, 150 * math.cos(th), 150 * math.sin(th)), V(1, 0, 0))
    ts = ts.fuse(tab.cut(hole))
parts['INT-111_Tube_Sheet_FI-1'] = (ts.removeSplitter(), '1.4301',
    'laser-cut 6 mm 1.4301, opening ID 324 (std GT cartridge), OD 500, gasket land r162..226 faced flat 0.2 mm, 3 yoke tabs M12 at r150, 2 x M12 saddle holes')

# ---------------------------------------------------------------- INT-112 skirt (dish -> core front), bosses
sk = cyl(X_DISH + 2.0, -11.4, 62.0, 60.0).fuse(cyl(-11.4, -8.4, 70.0, 54.0))
for (x, a) in ((-28.0, 168.0), (-28.0, 275.0), (-36.0, 90.0)):  # bulkheads: fuel line, pilot/2nd line, RPM sensor cable
    sk = sk.fuse(radial_boss(x, a, 61.0, 72.0, 16.0))
for k in range(3):                                               # strut-end radial screws M6 (struts land on the skirt)
    sk = sk.fuse(radial_boss(-16.0, 90 + 120 * k, 61.0, 68.0, 12.0))
for (x, a) in ((-28.0, 168.0), (-28.0, 275.0), (-36.0, 90.0)):
    sk = sk.cut(radial_boss(x, a, 50.0, 80.0, 9.0))
for k in range(3):
    sk = sk.cut(radial_boss(-16.0, 90 + 120 * k, 58.0, 70.0, 6.5))
for h in bolt_holes(-11.4, 3.0, 63.0, 6, 5.5, 0.0):
    sk = sk.cut(h)
parts['INT-112_Skirt'] = (sk.removeSplitter(), '1.4301',
    'rolled 2 mm cylinder D124 + 3 mm laser ring, welded to the dish back; 3 bulkhead bosses (G1/4 / M12 gland), 3 strut-end screw bosses')

# ---------------------------------------------------------------- INT-113 split clamp band on the casing / IntakeOuter lap
band = cyl(-8.4, -3.0, 66.0, 53.85)
for sgn in (1, -1):
    ear = Part.makeBox(5.4, 16, 14, V(-8.4, 64 if sgn > 0 else -80, -7))
    band = band.fuse(ear.cut(Part.makeCylinder(3.3, 20, V(-5.7, sgn * 72, -10), V(0, 0, 1))))
for h in bolt_holes(-8.4, 5.4, 63.0, 6, 5.0, 0.0):
    band = band.cut(h)
parts['INT-113_Clamp_Band_2halves'] = (band.removeSplitter(), '1.4301',
    'laser-cut 2 halves 5.4 mm, bore 107.7 on the casing lap joint, 2 ears M6, 6 x M5 tapped to the skirt ring; 0.5 mm graphite tape')

# ---------------------------------------------------------------- INT-120 pod tail fairing (3 segments, screwed to the pod rear face)
fp = [(-128.0, 57.0), (-117.0, 61.0)] + arc(-117.0, 46.0, 15.0, 90, 0)[1:]
fair = thick_revolve(fp, 1.5, side=-1).fuse(cyl(-107.8, -103.0, 46.0, 44.5))
for s in SH:
    fair = fair.cut(s)
parts['INT-120_Pod_Tail_Fairing'] = (fair.removeSplitter(), '1.4301',
    'spun 1.5 mm quarter-torus R15 + foot ring, cut into 3 segments at the struts, 3 x M4 into the pod rear face; no clamp near the x -136 bearing')

# ---------------------------------------------------------------- INT-140 FOD guard on the radial gap (2 halves)
guard = cyl(-118.0, X_DISH - 0.1, 101.0, 99.0).fuse(cyl(-120.0, -118.0, 101.0, 61.0))
parts['INT-140_FOD_Guard_2halves'] = (guard.removeSplitter(), 'mesh',
    'woven 1.4301 mesh 6 mm opening / 1.0 mm wire (f 0.69) on 2 rolled 3x10 frame rings, 2 halves, 6 x M5 to the dish, clipped to the fairing')

# ---------------------------------------------------------------- INT-150 / 151 filter cartridge pair + yoke (BUY, later; envelope)
xf = X_TS - T_TS
cart = cyl(xf - N_CART * L_CART, xf, 222.5, R_PL)
parts['INT-150_GT_Cartridge_Pair_env'] = (cart, 'cartridge',
    'BUY later: 2 x cylindrical GT cartridge 445/324 x 660 F9 (Camfil CamPulse GTC class), envelope only')
yk = []
for k in range(3):
    th = math.radians(30 + 120 * k)
    yk.append(Part.makeCylinder(6.0, N_CART * L_CART + 3, V(xf - N_CART * L_CART - 3, 150 * math.cos(th), 150 * math.sin(th)), V(1, 0, 0)))
cover = cyl(xf - N_CART * L_CART - 3, xf - N_CART * L_CART, 228.0)
parts['INT-151_Yoke_EndCover'] = (cover.fuse(yk).removeSplitter(), '1.4301',
    'BUY/make with the cartridge: 3 yoke rods M12 on r150 + 3 mm dished end cover d456, hand-wheel nuts')

meta = dict(subsystem='INTAKE', frame='ENG mm', calc='sim/variant_d/d2_intake_exhaust_calc.json',
            interfaces=dict(
                FI_1_tube_sheet=dict(x_gasket_face=X_TS - T_TS, opening_ID=2 * R_PL, OD=2 * R_TS, face='-x', gasket_land_r=[R_PL, 226],
                                     yoke='3 x M12 at r150, 30/150/270 deg', cartridge='445/324 x 660 GT cylinder, pair -> front cover at x %.0f' % (xf - N_CART * L_CART - 3)),
                core_clamp=dict(x=[-8.4, -3.0], bore=107.7, on='v13A Casing over IntakeOuter (lap joint, x -11..-5)'),
                strut_ends=dict(x=-16.0, r_screw=61.0, angles_deg=[90, 210, 330], note='D-150 strut ends get a radial M6 tapped hole'),
                pod_rear_face=dict(x=-108.0, fairing_foot_r=[44.5, 46.0], screws='3 x M4'),
                bulkheads=dict(fuel_168deg=[-28, 168], line_275deg=[-28, 275], rpm_cable_90deg=[-36, 90]),
                service_pad=dict(x=[-124, -94], top=True, holes=['M40 PMG power gland', 'G1/2', 'G1/2']),
                front_support=dict(saddle_holes='2 x M12 on r237 at 250/290 deg in INT-111', x_face=X_TS)))
rows = export(parts, 'INTAKE', meta)
