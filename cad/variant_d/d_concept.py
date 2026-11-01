# GR180 version D (concept shape only): single-shaft turbo-generator. The v13A turbojet keeps its compressor,
# combustor and turbine; the starter and nose cone are replaced by a front generator pod (PMG at shaft speed,
# 115k rpm) that is no wider than the engine casing, joined to the compressor nose by a flexible quill shaft.
# Intake air enters radially through a screen between the pod and the intake bell; the jet nozzle becomes an
# exhaust diffuser. Envelope geometry for layout only - the radial turbine, PMG and rotordynamics come later.
# ENG frame (mm): x = engine axis (downstream +), x = 0 at the shaft-tunnel spigot front face (as build_gr180.py).
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d_concept.py  ->  cad_out/variant_d/D-*.step + d_concept.json
import FreeCAD as App, Part, os, json, math
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'cad_out', 'v13A')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.path.join(ROOT, 'cad_out', 'variant_d'); os.makedirs(OUT, exist_ok=True)

R_CASE = 55.0                     # v13A casing outer radius (Casing.step bbox r 53.8..55)
X_INTAKE_LIP = -48.0              # v13A intake bell front lip
GAP = 60.0                        # radial inlet gap between pod rear and intake lip
L_POD = 190.0                     # generator pod length (allowed to be long, not wider than the casing)
X_POD1 = X_INTAKE_LIP - GAP       # pod rear face
X_POD0 = X_POD1 - L_POD           # pod front face
R_POD = R_CASE                    # pod outer radius = casing radius
X_NOSE = -40.0                    # compressor nut / nose (front LH M6 thread end, v13A NoseCone starts at -58.8)

def cyl(x0, x1, r, ri=0.0):
    s = Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return s.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), V(1, 0, 0))) if ri > 0 else s

def cone(x0, x1, r0, r1, t=0.0):
    o = Part.makeCone(r0, r1, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return o.cut(Part.makeCone(r0 - t, r1 - t, x1 - x0, V(x0, 0, 0), V(1, 0, 0))) if t else o

parts = {}
# generator pod: housing with glycol jacket (outer shell), rounded front cap, rear end shield
shell = cyl(X_POD0 + 25, X_POD1 - 15, R_POD, R_POD - 6)
front = cone(X_POD0, X_POD0 + 25, 22.0, R_POD).fuse(cyl(X_POD0 + 22, X_POD0 + 25, R_POD))
front = front.cut(cyl(X_POD0 + 3, X_POD0 + 25.5, R_POD - 6))
rear = cyl(X_POD1 - 15, X_POD1, R_POD, 9.0).cut(cyl(X_POD1 - 12, X_POD1 - 3, R_POD - 6, 20.0))
parts['D-101_Generator_Housing_Jacket'] = shell.fuse(rear).removeSplitter()
parts['D-102_Generator_Front_Cap'] = front
# stator core + winding, PMG rotor, generator shaft, two bearings
xs0, xs1 = X_POD0 + 55, X_POD1 - 45
parts['D-110_Stator_Core'] = cyl(xs0 + 10, xs1 - 10, R_POD - 7, 24.0)
parts['D-111_Stator_Winding'] = cyl(xs0, xs1, R_POD - 18, 24.5).cut(cyl(xs0 + 10, xs1 - 10, R_POD - 7, 0))
parts['D-120_PMG_Rotor_Magnets_Sleeve'] = cyl(xs0 + 12, xs1 - 12, 22.5, 7.0)
parts['D-121_Generator_Shaft'] = cyl(X_POD0 + 20, X_POD1 + 4, 7.0)
for tag, x in (('D-130_Bearing_Front', X_POD0 + 32), ('D-131_Bearing_Rear', X_POD1 - 28)):
    parts[tag] = cyl(x - 6, x + 6, 16.0, 7.0)
# flexible quill shaft + coupling hubs (generator shaft end -> compressor nose nut)
parts['D-140_Quill_Shaft'] = cyl(X_POD1 + 4, X_NOSE - 6, 3.0)
parts['D-141_Coupling_Hub_Generator'] = cyl(X_POD1 + 2, X_POD1 + 16, 9.0, 3.0)
parts['D-142_Coupling_Hub_Nose_Fairing'] = cyl(X_NOSE - 22, X_NOSE, 9.0).fuse(cone(X_NOSE - 40, X_NOSE - 22, 4.0, 9.0))
# 3 struts (not 4: no 4-per-rev features in the gas path) from the pod rear shield to the intake outer ring
struts = []
for k in range(3):
    th = math.radians(90 + 120 * k)
    d = V(0, math.cos(th), math.sin(th))
    p0 = V(X_POD1 - 8, 0, 0) + d * (R_POD - 4)
    p1 = V(-12.0, 0, 0) + d * (R_CASE - 2)
    ax = p1 - p0
    st = Part.makeCylinder(4.0, ax.Length, p0, ax)
    struts.append(st)
parts['D-150_Pod_Struts_x3'] = Part.makeCompound(struts)
# radial inlet screen (cylindrical mesh envelope between pod and intake lip) - see-through in Fusion
parts['D-160_Inlet_Screen'] = cyl(X_POD1 + 2, X_INTAKE_LIP + 8, R_CASE + 12, R_CASE + 10)
# terminal box on the pod
parts['D-170_Terminal_Box'] = Part.makeBox(70, 50, 30, V(X_POD0 + 70, -25, R_POD - 2))
# exhaust diffuser (replaces the jet nozzle): conical, from the turbine exit to a DN150 flange
X_EX0, X_EX1 = 113.0, 260.0
dif = cone(X_EX0, X_EX1, 46.0, 72.0, 2.5)
fl = cyl(X_EX1, X_EX1 + 16, 105.0, 72.0)
parts['D-180_Exhaust_Diffuser_DN150'] = dif.fuse(fl).removeSplitter()

info = dict(note='version D concept envelopes (shape only)', pod=dict(x=[X_POD0, X_POD1], r=R_POD, length=L_POD),
            inlet_gap_mm=GAP, quill=[X_POD1, X_NOSE], exhaust=[X_EX0, X_EX1 + 16], parts={})
for k, s in parts.items():
    s.exportStep(os.path.join(OUT, k + '.step'))
    bb = s.BoundBox
    info['parts'][k] = dict(valid=s.isValid(), x=[round(bb.XMin, 1), round(bb.XMax, 1)], r=round(max(bb.YMax, bb.ZMax), 1))
    print(k, s.isValid(), 'x %.0f..%.0f' % (bb.XMin, bb.XMax))
json.dump(info, open(os.path.join(OUT, 'd_concept.json'), 'w'), indent=1)
print('overall length (pod front to diffuser flange): %.0f mm' % (X_EX1 + 16 - X_POD0))
