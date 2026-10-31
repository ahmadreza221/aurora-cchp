# GR180 variant C (compact turbo-generator): low base frame. The variant A/B feet stand on a skid at ENG z -400; version C
# sits on its own frame just under the exhaust box insulation, so the three supports are cut down to Z_BASE and get new
# base plates, and two longitudinal rails tie them together. ENG frame (mm), x = engine axis.
# Inputs: cad_out/variant_b/E2B/E2B-103 (front fixed point), cad_out/variant_c/EXH/E3B-401 (exhaust portal),
#         cad_out/engine/E3/E3-402 (rear flexure).  Output: cad_out/variant_c/FRAME/*.step + frame.json
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_c/c_frame.py
import FreeCAD as App, Part, os, json, glob
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'cad_out')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
CO = os.path.join(ROOT, 'cad_out')
OUT = os.path.join(CO, 'variant_c', 'FRAME'); os.makedirs(OUT, exist_ok=True)
FEET = {'C-401_Front_Foot': os.path.join(CO, 'variant_b', 'E2B', 'E2B-103_Front_Foot_FixedPoint.step'),
        'C-402_Exhaust_Support': os.path.join(CO, 'variant_c', 'EXH', 'E3B-401_Front_Support_Portal.step'),
        'C-403_Rear_Flexure': os.path.join(CO, 'engine', 'E3', 'E3-402_Foot_Rear_Flexure.step')}
OLD_BASE_TOP = -390.0                       # old feet: 10 mm base plate on the skid at z -400
T_PL, RAIL_H, RAIL_W, RAIL_T = 10.0, 60.0, 40.0, 3.0

def load(f):
    s = Part.Shape(); s.read(f); return s

# lowest point of everything that is not a support (exhaust insulation jacket governs)
low = []
for f in glob.glob(os.path.join(CO, 'variant_c', 'EXH', 'E3B-1*.step')) + glob.glob(os.path.join(CO, 'variant_b', 'E2B', 'E2B-1[1-7]*.step')):
    low.append(load(f).BoundBox.ZMin)
Z_BASE = round(min(low) - 12.0)             # base-plate underside; 12 mm air gap under the jacket
parts, info = {}, dict(Z_BASE=Z_BASE, feet={})
for name, f in FEET.items():
    old = load(f)
    bb = old.BoundBox
    keep = old.common(Part.makeBox(bb.XLength + 2, bb.YLength + 2, bb.ZMax - (Z_BASE + T_PL), V(bb.XMin - 1, bb.YMin - 1, Z_BASE + T_PL)))
    foot_pl = old.common(Part.makeBox(bb.XLength + 2, bb.YLength + 2, OLD_BASE_TOP - bb.ZMin + 0.01, V(bb.XMin - 1, bb.YMin - 1, bb.ZMin - 0.01))).BoundBox
    plate = Part.makeBox(foot_pl.XLength, foot_pl.YLength, T_PL, V(foot_pl.XMin, foot_pl.YMin, Z_BASE))
    parts[name] = keep.fuse(plate).removeSplitter()
    info['feet'][name] = dict(source=os.path.relpath(f, ROOT), cut_height_mm=round(Z_BASE - bb.ZMin, 1),
                              plate=[round(foot_pl.XMin, 1), round(foot_pl.XMax, 1), round(foot_pl.YMin, 1), round(foot_pl.YMax, 1)])
# two RHS 60x40x3 rails (1.4301) under the plates, y +-100
xs = [b.BoundBox.XMin for b in parts.values()] + [b.BoundBox.XMax for b in parts.values()]
x0, x1 = min(xs) - 40.0, max(xs) + 40.0
rails = []
for yc in (-100.0, 100.0):
    o = Part.makeBox(x1 - x0, RAIL_W, RAIL_H, V(x0, yc - RAIL_W / 2, Z_BASE - RAIL_H))
    i = Part.makeBox(x1 - x0 + 2, RAIL_W - 2 * RAIL_T, RAIL_H - 2 * RAIL_T, V(x0 - 1, yc - RAIL_W / 2 + RAIL_T, Z_BASE - RAIL_H + RAIL_T))
    rails.append(o.cut(i))
parts['C-410_Base_Rails_RHS60x40'] = Part.makeCompound(rails)
info['rails'] = dict(x=[round(x0, 1), round(x1, 1)], y=[-100, 100], section='RHS 60x40x3 1.4301', z_bottom=Z_BASE - RAIL_H)
for name, s in parts.items():
    s.exportStep(os.path.join(OUT, name + '.step'))
    print(name, 'valid', s.isValid(), 'bbox z %.0f..%.0f' % (s.BoundBox.ZMin, s.BoundBox.ZMax))
json.dump(info, open(os.path.join(OUT, 'frame.json'), 'w'), indent=1)
print('Z_BASE', Z_BASE, '| overall height from rail bottom to axis %.0f mm' % (-(Z_BASE - RAIL_H)))
