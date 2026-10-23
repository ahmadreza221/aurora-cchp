# GR180 version E - COMBUSTOR: single vertical reverse-flow can on the cool casing (axis x = X_CAN, y = 0, z up).
# Casing = DN300 pipe + 2 PN10 flanges + blind-flange cover; Nimonic 75 liner (holes from sim/variant_e/e_combustor.json),
# axial swirler, central gas lance, spark igniter, UV scanner, diffusing conical transition d210 -> d270 into the hot plenum.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_e/e_can.py  -> cad_out/variant_e/COMBUSTOR/*.step
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
from e_common import *
import e_layout as L

X0 = L.X_CAN
c = L.CAN
K = Parts('COMBUSTOR')
ro, ri = c['casing_OD'] / 2, c['casing_OD'] / 2 - c['casing_t']
fr = c['flange_OD'] / 2


def vholes(z0, z1, pcd, n, d, phase=15.0):
    return [Part.makeCylinder(d / 2, z1 - z0 + 2, V(X0 + pcd / 2 * math.cos(math.radians(phase + 360.0 * k / n)),
                                                  pcd / 2 * math.sin(math.radians(phase + 360.0 * k / n)), z0 - 1), V(0, 0, 1)) for k in range(n)]


cas = fuse_all([zcyl(X0, 0, 440.0, 460.0, fr, 155.0), zcyl(X0, 0, 460.0, 1160.0, ro, ri), zcyl(X0, 0, 1160.0, 1180.0, fr, 155.0)])
boss = Part.makeCylinder(20.0, 45.0, V(X0, 150.0, 1060.0), V(0, 1, 0)).cut(zcyl(X0, 0, 1000.0, 1100.0, ri))
cas = cas.fuse(boss).cut(Part.makeCylinder(10.0, 120.0, V(X0, 120.0, 1060.0), V(0, 1, 0)))
cas = cut_all(cas, vholes(440.0, 460.0, 400.0, 12, 22.0) + vholes(1160.0, 1180.0, 400.0, 12, 22.0))
K.add('E-K110_Combustor_Casing_DN300', cas, 'steel', 'can casing DN300 (323.9 x 7.1) z 460..1160 + 2 weld-neck flanges PN10 (OD 445, 12 x M20), '
      'igniter boss M18x1.5', 'make (EN 10216-2 P265GH pipe + EN 1092-1 flanges, welded; PED)')
cov = zcyl(X0, 0, 1180.0, 1205.0, fr).cut(zcyl(X0, 0, 1170.0, 1215.0, 16.0)).cut(zcyl(X0 + 120.0, 0, 1170.0, 1215.0, 12.0))
cov = cut_all(cov, vholes(1180.0, 1205.0, 400.0, 12, 22.0))
K.add('E-K111_Top_Cover', cov, 'steel', 'blind-flange top cover DN300 PN10 with the gas-lance bore d32, UV sight port, 3 liner hanger seats; '
      'lift off with the liner + injector for inspection (no engine strip)', 'make (EN 1092-1 blind flange, drilled)')
ln = zcyl(X0, 0, c['z_liner_exit'], 1108.0, 105.0, 103.5).fuse(zcyl(X0, 0, 1108.0, 1111.0, 105.0, 55.0))
holes = []
for key, (n, d, z) in c['holes'].items():
    for k in range(n):
        th = math.radians(360.0 * k / n + (0 if key != 'secondary' else 15.0))
        dirv = V(math.cos(th), math.sin(th), 0)
        holes.append(Part.makeCylinder(d / 2, 20.0, V(X0, 0, z) + dirv * 95.0, dirv))
ln = cut_all(ln, holes)
for z in (600.0, 800.0, 980.0, 1070.0):                     # film-cooling slot rings (envelope: a row of d4 holes)
    ln = cut_all(ln, [Part.makeCylinder(2.0, 20.0, V(X0, 0, z) + V(math.cos(math.radians(7.5 * k)), math.sin(math.radians(7.5 * k)), 0) * 95.0,
                                         V(math.cos(math.radians(7.5 * k)), math.sin(math.radians(7.5 * k)), 0)) for k in range(48)])
K.add('E-K120_Liner_D210', ln, 'N75', 'liner d210 x 1.5, L 588 + dome: primary 8 x d23.3, secondary 12 x d17.4, dilution 10 x d28, 4 film-cooling rows',
      'make (2.4951 Nimonic 75 sheet, flat patterns laser-cut, rolled + TIG; dome turned)')
K.add('E-K121_Axial_Swirler', zcyl(X0, 0, 1095.0, 1111.0, 55.0, 25.0), 'alloyX', 'axial swirler hub 50 / tip 110, 12 flat vanes 45 deg (envelope)', 'make (turned rings + laser-cut vanes, brazed)')
hang = fuse_all([zcyl(X0 + 80.0 * math.cos(math.radians(a)), 80.0 * math.sin(math.radians(a)), 1111.0, 1180.0, 6.0) for a in (90.0, 210.0, 330.0)])
K.add('E-K122_Liner_Hangers_x3', hang, 'alloyX', '3 liner hanger rods d12 from the dome to the cover (liner hangs, grows downward into the transition collar)', 'make')
tr = Part.Face(Part.makePolygon([V(X0 + r, 0, z) for (r, z) in ((135.0, 320.0), (137.0, 320.0), (107.0, 505.0), (107.0, 535.0), (105.0, 535.0), (105.0, 505.0), (135.0, 320.0))])
               ).revolve(V(X0, 0, 0), V(0, 0, 1), 360)
K.add('E-K130_Transition_Cone', tr, 'alloyX', 'diffusing conical transition d210 -> d270 (2 mm alloy X), collar slides over the liner, piston-ring seal in the hot-plenum inlet',
      'make (rolled cone + turned collar, TIG)')
inj = fuse_all([zcyl(X0, 0, 1090.0, 1205.0, 15.0), zcyl(X0, 0, 1205.0, 1260.0, 30.0), Part.makeCylinder(10.0, 80.0, V(X0, 0, 1240.0), V(0, 1, 0))])
K.add('E-K140_Gas_Lance', inj, 'stainless', 'central gas lance d30: 8 radial jets d4.5 into the swirler exit, flanged head with G3/4 gas inlet', 'make (1.4404 + 2.4665 tip)')
K.add('E-K150_Igniter', Part.makeCylinder(9.0, 150.0, V(X0, 107.0, 1060.0), V(0, 1, 0)), 'stainless', 'spark igniter M18x1.5 in a cooled sleeve, primary zone',
      'buy (industrial gas-engine plug NGK / MOTORTECH + HV capacitive coil)', mass=0.4)
K.add('E-K160_UV_Flame_Scanner', zcyl(X0 + 120.0, 0, 1205.0, 1300.0, 25.0), 'Al', 'UV flame scanner on the cover sight port (envelope)', 'buy (DURAG D-LX 100 class / Siemens QRA)', mass=0.8)
K.save()
