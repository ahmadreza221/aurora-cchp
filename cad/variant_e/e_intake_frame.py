# GR180 version E - INTAKE plenum (large, low loss: 3 x 3 filter-cell interface on top, filter house = plant scope) and
# FRAME (welded RHS base frame on 8 AV mounts, fixed pedestals under the compressor outer casing, sliding pedestals under
# the cool casing, saddles under the exhaust cone and elbow).  Run after e_core.py and e_exhaust.py (uses their solids).
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_e/e_intake_frame.py  -> cad_out/variant_e/{INTAKE,FRAME}/*.step
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
from e_common import *
import e_layout as L

P = L.PLENUM
I = Parts('INTAKE')
(x0, x1), (y0, y1), (z0, z1), w = P['x'], P['y'], P['z'], P['wall']
xc = 0.5 * (x0 + x1)
fo = P['filter_opening']
pl = box(x0, x1, y0, y1, z0, z1).cut(box(x0 + w, x1 - w, y0 + w, y1 - w, z0 + w, z1 - w))
pl = pl.cut(box(xc - fo[0] / 2, xc + fo[0] / 2, -fo[1] / 2, fo[1] / 2, z1 - 10.0, z1 + 10.0))
pl = pl.cut(cyl(x1 - 10.0, x1 + 10.0, P['bellmouth_hole_r']))
I.add('E-I110_Intake_Plenum', pl, 'stainless', 'clean-air plenum 1910 x 1900 x 1300 (3 mm 1.4301, stiffened), rear wall with the bellmouth opening d644, top opening 1830 x 1830; '
      'V ~0.7 m/s inside; generator pod on its feet inside; access door (not modelled)', 'make (sheet metal, laser + brake + MAG, bolted panels)')
fr = box(x0, x1, y0, y1, z1, z1 + 15.0).cut(box(xc - fo[0] / 2, xc + fo[0] / 2, -fo[1] / 2, fo[1] / 2, z1 - 1.0, z1 + 20.0))
for k in (1, 2):
    fr = fr.fuse(box(xc - fo[0] / 2 + 610.0 * k - 10.0, xc - fo[0] / 2 + 610.0 * k + 10.0, -fo[1] / 2, fo[1] / 2, z1, z1 + 15.0))
    fr = fr.fuse(box(xc - fo[0] / 2, xc + fo[0] / 2, -fo[1] / 2 + 610.0 * k - 10.0, -fo[1] / 2 + 610.0 * k + 10.0, z1, z1 + 15.0))
I.add('E-I120_Filter_Interface_Frame', fr, 'stainless', 'filter-bank interface: 3 x 3 holding-frame grid 610 pitch for 592 x 592 cells (G4 panel + F7 V-cell), knife-edge seal face; '
      'filter house / weather hood bolts on top (plant scope)', 'make (flat bar + angle, welded)')
I.save(dict(filter=dict(cells='3 x 3 x (592 x 592 G4 48 + F7 V-cell 292)', opening_mm=list(fo), top_z=z1 + 15.0, flow_m3_h_30C=9420,
                        dp='clean 180 / mid-life 248 / change-out 317 Pa total intake (0.18 / 0.25 / 0.31 %), sim/variant_e/e_ducts.json')))

F = Parts('FRAME')
zt = L.FRAME['z_top']; h = L.FRAME['rhs'][0]; t = L.FRAME['rhs'][2]
zb = zt - h
xa, xb = L.FRAME['x'][0], 2250.0


def rhs_x(xa_, xb_, yc, wy=100.0):
    return box(xa_, xb_, yc - wy / 2, yc + wy / 2, zb, zt).cut(box(xa_ - 1, xb_ + 1, yc - wy / 2 + t, yc + wy / 2 - t, zb + t, zt - t))


def rhs_y(xc_, ya_, yb_, wx=100.0):
    return box(xc_ - wx / 2, xc_ + wx / 2, ya_, yb_, zb, zt).cut(box(xc_ - wx / 2 + t, xc_ + wx / 2 - t, ya_ - 1, yb_ + 1, zb + t, zt - t))


parts = [rhs_x(xa, xb, s * L.FRAME['y_rail']) for s in (1, -1)]
for xc_ in (-2050.0, -1550.0, -1050.0, -600.0, -200.0):
    parts.append(rhs_y(xc_, y0, y1))                        # outriggers under the plenum
for xc_ in (72.5, 285.0, 910.0, 1360.0, 1600.0, 2200.0):
    parts.append(rhs_y(xc_, -600.0, 600.0))
for xc_ in (72.5, 285.0):                                   # outrigger stubs under the engine pedestals
    parts.append(rhs_y(xc_, -600.0, -360.0)); parts.append(rhs_y(xc_, 360.0, 600.0))
frame = fuse_all(parts)
F.add('E-F110_Base_Frame_RHS', frame, 'steel', 'welded base frame RHS 200 x 100 x 6.3 (S355J2H, EN 10219): 2 rails x -2100..2250 at y +/-550, 5 outriggers under the plenum, '
      '6 cross members; lifting at the 4 rail ends (lugs not modelled)', 'make (MAG on a table, hot-dip galvanised)')
peds = []
for s in (1, -1):
    yy = (330.0, 400.0) if s > 0 else (-400.0, -330.0)
    peds.append(box(50.0, 95.0, yy[0], yy[1], zt, -30.0).cut(box(56.0, 89.0, yy[0] + 6, yy[1] - 6, zt + 6, -36.0)))
F.add('E-F120_Fixed_Pedestals_x2', fuse_all(peds), 'steel', '2 FIXED pedestals under the outer-casing trunnion pads (x 50..95): 2 x M20 + 2 dowels each', 'make (S355 plate box)')
sl = []
for s in (1, -1):
    yy = (385.0, 420.0) if s > 0 else (-420.0, -385.0)
    sl.append(box(270.0, 300.0, yy[0], yy[1], zt, -20.0))
F.add('E-F121_Sliding_Pedestals_x2', fuse_all(sl), 'steel', '2 SLIDING pedestals under the cool-casing pads: PTFE / bronze slide plate, M20 shoulder bolts in x-slots (thermal growth ~2 mm)', 'make (S355)')
cone_out = rev([(485.0, 0.0), (485.0, 150.0), (530.0, 150.0), (530.0, 134.3), (1463.0, 216.9), (1463.0, 270.0), (1475.0, 270.0), (1475.0, 0.0)])
sad = []
for xs in (910.0, 1360.0):
    sad.append(box(xs - 30.0, xs + 30.0, -150.0, 150.0, zt, -130.0).cut(cone_out).cut(box(xs - 18.0, xs + 18.0, -138.0, 138.0, zt + 12.0, -250.0)))
Rb, ro_ = L.EXH['elbow_R'], L.EXH['elbow_r'] + L.EXH['elbow_t']
torus_out = Part.Face(Part.Wire(Part.makeCircle(ro_, V(1500.0, 0, 0), XA))).revolve(V(1500.0, 0, Rb), V(0, -1, 0), 90)
sad.append(box(1570.0, 1630.0, -150.0, 150.0, zt, -150.0).cut(torus_out).cut(cyl(1475.0, 1501.0, 271.0)).cut(box(1582.0, 1618.0, -138.0, 138.0, zt + 12.0, -300.0)))
F.add('E-F122_Exhaust_Saddles_x3', fuse_all(sad), 'steel', '3 saddles under the diffuser cone (2) and the elbow (1): slide plates, insulated pads', 'make (S355)')
avs = []
for xm in (-2000.0, -800.0, 400.0, 2150.0):
    for s in (1, -1):
        avs.append(zcyl(xm, s * L.FRAME['y_rail'], zb - L.FRAME['av_h'], zb, 60.0))
F.add('E-F130_AV_Mounts_x8', fuse_all(avs), 'rubber', '8 rubber-metal AV mounts (~800 kg rated each, f_n ~10 Hz), M16', 'buy (Trelleborg SE / Freudenberg (Vibracoustic) DE / Getzner AT)', mass=8 * 3.5)
F.save(dict(footprint_mm=dict(x=[xa, xb], y=[y0, y1]), floor_z=zb - L.FRAME['av_h'], axis_above_floor=-(zb - L.FRAME['av_h'])))
