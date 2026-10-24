"""Export the E1 turbine stage as compact single-feature STEP parts for Autodesk Fusion (fusion/E1/*.step).

The full wheels / NGV ring are 110-160 MB STEP files (29 / 21 B-spline blades each). Fusion gets one blade and one vane plus
the revolved bodies instead; fusion/import_e1.py patterns them around the engine axis (ENG frame: x = axis, mm), as
cad/engine/gg_turbine.py does (blades at 360 k / 29 deg, disc seam / NGV rings rotated by half a pitch).
Run:  freecadcmd fusion/export_e1_parts.py     (GR180_ROOT = repo root, default: parent of this folder)
"""
import os, sys, json
ROOT = os.environ.get('GR180_ROOT') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
import gg_turbine as G
OUT = os.path.join(ROOT, 'fusion', 'E1'); os.makedirs(OUT, exist_ok=True)
info = {}
def save(name, s):
    s.exportStep(os.path.join(OUT, name + '.step'))
    info[name] = dict(valid=s.isValid(), solids=len(s.Solids)); print(name, info[name], flush=True)
rot = G.design_rotor()
raw, bf, bc, nw = G.fc_blade(rot)
for kind, bl in (('final', bf), ('cast', bc)):
    disc = G.fc_disc(kind, G.DISC_BORELESS)
    save('E1_disc_boreless_' + kind, disc)
    save('E1_blade_' + kind, bl.cut(disc))
save('E1_shaft_welded', G.fc_shaft_welded())
ngv = G.design_ngv(); RB = G.ngv_bore_r()
for kind in ('final', 'cast'):
    body, rb = G.ngv_body(kind, RB)
    vane, _ = G.fc_vane(ngv, rb)
    piece = vane.common(G.ring(21.3, rb + 0.65, G.X_NGV, G.X_NGV + 24)).cut(body)
    body.rotate(G._fc()[2](0, 0, 0), G._fc()[2](1, 0, 0), 180.0 / G.Z_NGV)
    save('E1_ngv_rings_' + kind, body); save('E1_ngv_vane_' + kind, piece)
info['pattern'] = dict(blades=G.Z_ROT, vanes=G.Z_NGV, axis='x', units='mm')
json.dump(info, open(os.path.join(OUT, 'parts.json'), 'w'), indent=1)
