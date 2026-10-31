# GR180 version E - EXHAUST: long 10 deg conical diffuser (slip collar on the turbine shroud tail), 90 deg elbow with
# 2 turning vanes (R 450), DN450 PN6 outlet flange to the CHP heat exchanger.  Numbers: e_layout.EXH / sim/variant_e/e_ducts.json.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_e/e_exhaust.py  -> cad_out/variant_e/EXHAUST/*.step
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
from e_common import *
import e_layout as L

X = Parts('EXHAUST')
e = L.EXH
cone = rev([(485.0, 141.0), (485.0, 150.0), (530.0, 150.0), (530.0, 134.3), (1463.0, 216.9), (1463.0, 270.0), (1475.0, 270.0), (1475.0, 214.0), (525.0, 131.0), (525.0, 141.0)])
cone = cut_all(cone, bolt_circle_holes(1463.0, 1475.0, 500.0, 12, 18.0, 15.0))
X.add('E-X110_Diffuser_Cone', cone, '1.4828', '10 deg conical diffuser d262 -> d428 (3 mm 1.4828), slip collar d282 with piston ring over the shroud tail, '
      'end flange; outside 100 mm ceramic blanket + 1.4301 cladding (not modelled)', 'make (rolled 1.4828 sheet + turned collar / flange, TIG)')
Rb, ri_, ro_ = e['elbow_R'], e['elbow_r'], e['elbow_r'] + e['elbow_t']
xb = 1500.0
inlet = fuse_all([cyl(1475.0, xb, ro_, ri_), cyl(1475.0, 1487.0, 270.0, ro_)])
inlet = cut_all(inlet, bolt_circle_holes(1475.0, 1487.0, 500.0, 12, 18.0, 15.0))
ann = Part.Face(Part.Wire(Part.makeCircle(ro_, V(xb, 0, 0), XA))).cut(Part.Face(Part.Wire(Part.makeCircle(ri_, V(xb, 0, 0), XA))))
bend = ann.revolve(V(xb, 0, Rb), V(0, -1, 0), 90)
xo = xb + Rb
outlet = fuse_all([zcyl(xo, 0, Rb, Rb + 20.0, ro_, ri_), zcyl(xo, 0, Rb + 20.0, Rb + 42.0, e['flange']['OD'] / 2, ri_)])
outlet = cut_all(outlet, [Part.makeCylinder(11.0, 30.0, V(xo + 292.5 * math.cos(math.radians(11.25 + 22.5 * k)), 292.5 * math.sin(math.radians(11.25 + 22.5 * k)), Rb + 16.0), V(0, 0, 1)) for k in range(16)])
X.add('E-X120_Elbow_DN450_Flange', fuse_all([inlet, bend, outlet]), '1.4828', '90 deg elbow DN450 (457 x 6.3), R 450, inlet flange to the cone, outlet flange %s facing up' % e['flange']['name'],
      'make (5-segment mitred 1.4828 pipe or bought EN 10253 elbow + flanges)')
vanes = []
for dv in (-80.0, 80.0):
    Rv = Rb - dv
    face = Part.Face(Part.makePolygon([V(xb, -195.0, -dv - 1.5), V(xb, 195.0, -dv - 1.5), V(xb, 195.0, -dv + 1.5), V(xb, -195.0, -dv + 1.5), V(xb, -195.0, -dv - 1.5)]))
    vanes.append(face.revolve(V(xb, 0, Rb), V(0, -1, 0), 90))
X.add('E-X121_Elbow_Turning_Vanes_x2', fuse_all(vanes), '1.4828', '2 turning vanes in the elbow (3 mm, at R 370 / 530), welded to the elbow sides', 'make (rolled strip)')
X.save(dict(outlet=dict(x=xo, y=0.0, z=Rb + 42.0, normal='+z', flange=e['flange']['name'])))
