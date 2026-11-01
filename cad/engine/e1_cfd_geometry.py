"""E1 turbine stage: wall surfaces (STL, mm) of ONE NGV passage and ONE rotor passage for OpenFOAM / snappyHexMesh
(sim/cfd/e1_stage/).  Geometry from cad/engine/gg_turbine.py (same vane / blade lofts as the Fusion models).

NGV passage: vane (with fillets) as the obstacle; hub = inner ring OD r 22.25 (x 94.8..109.8); shroud = chamfer 26 deg
from r 36.05 (x 94.8) to the bore r_b (x 96.24) then the bore to x 118.8. Rotor passage: blade (with root fillet) on the
hub flare r 22.1 -> 19.0 (platform x 110.1..119.4), tip at r 35.15 under the shroud bore r_b.
Both periodic in theta by 360/21 and 360/29 deg; the vane / blade sit at theta ~ 0 (TE / centroid stacking of the code).
Run:  LANG=en_US.UTF-8 freecadcmd cad/engine/e1_cfd_geometry.py
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gg_turbine as G                                   # noqa: E402

import FreeCAD as App                                    # noqa: E402
import Part                                              # noqa: E402
import Mesh                                              # noqa: E402

V = App.Vector
OUT = os.path.join(G.ROOT, 'sim', 'cfd', 'e1_stage', 'geometry')
os.makedirs(OUT, exist_ok=True)
T0 = time.time()


def log(*a):
    print('[%5.0fs]' % (time.time() - T0), *a, flush=True)


def write_stl(shape, name, dev=0.01, ang=0.35):
    m = Mesh.Mesh(); m.addFacets(shape.tessellate(dev, ang)) if False else None
    faces = shape.tessellate(dev)
    m = Mesh.Mesh(faces)
    path = os.path.join(OUT, name + '.stl')
    m.write(path)
    log('%-18s %7d facets  bbox x %.2f..%.2f  -> %s' % (name, m.CountFacets, shape.BoundBox.XMin, shape.BoundBox.XMax, os.path.relpath(path, G.ROOT)))
    return m.CountFacets


def revolve_profile(pts):
    w = Part.makePolygon([V(x, r, 0) for x, r in pts])
    return w.revolve(V(0, 0, 0), V(1, 0, 0), 360).Faces if False else [e.revolve(V(0, 0, 0), V(1, 0, 0), 360) for e in w.Edges]


ngv = G.design_ngv(); rot = G.design_rotor()
RB = G.ngv_bore_r()
X_IN, X_MID, X_OUT = 90.0, 110.0, 126.0        # inlet plane, NGV/rotor interface (mid-gap 109.8 / 110.1), outlet plane

# ---------------------------------------------------------------- NGV passage walls
body, rb = G.ngv_body('final', RB)
vane, _ = G.fc_vane(ngv, rb)
piece = vane.common(G.ring(21.3, rb + 0.65, G.X_NGV, G.X_NGV + 24)).cut(body)
log('NGV vane piece vol %.1f valid %s faces %d' % (piece.Volume, piece.isValid(), len(piece.Faces)))
n_vane = write_stl(piece, 'ngv_vane', dev=0.005)
# hub: inner ring OD, extended upstream to the inlet plane and downstream to the interface (rotor platform 22.1 ~ same)
hub_ngv = Part.makeCylinder(G.R_NGV_HUB, X_MID - X_IN, V(X_IN, 0, 0), V(1, 0, 0)).Faces[0]
write_stl(Part.Shell([hub_ngv]) if False else hub_ngv, 'ngv_hub')
# shroud: r 36.05 from the inlet plane to x 94.8, chamfer 26 deg down to the bore at x 96.24, bore to the interface
chl = (36.05 - rb) / math.tan(math.radians(26))
prof = [(X_IN, 36.05), (G.X_NGV, 36.05), (G.X_NGV + chl, rb), (X_MID, rb)]
shr_faces = []
for (x0, r0), (x1, r1) in zip(prof, prof[1:]):
    e = Part.makeLine(V(x0, r0, 0), V(x1, r1, 0))
    shr_faces.append(e.revolve(V(0, 0, 0), V(1, 0, 0), 360))
shroud_ngv = Part.makeShell(shr_faces) if False else Part.Compound(shr_faces)
write_stl(shroud_ngv, 'ngv_shroud')

# ---------------------------------------------------------------- rotor passage walls
blade_raw, blade_f, blade_c, nw = G.fc_blade(rot)
disc = G.fc_disc('final', G.DISC_BORELESS)
bpiece = blade_f.cut(disc)
log('rotor blade piece vol %.1f valid %s' % (bpiece.Volume, bpiece.isValid()))
write_stl(bpiece, 'rot_blade', dev=0.005)
# hub: platform radius r_hub(x) from the interface to the outlet (flare 22.1 -> 19.0 between 110.3 and 118.6, then 19.0)
xs = [X_MID] + [G.X_FL0 + (G.X_FL1 - G.X_FL0) * k / 40 for k in range(41)] + [G.X_PR, X_OUT]
hub_pts = [(x, float(G.r_hub(x))) for x in xs]
hub_faces = []
for (x0, r0), (x1, r1) in zip(hub_pts, hub_pts[1:]):
    if abs(x1 - x0) < 1e-6:
        continue
    e = Part.makeLine(V(x0, r0, 0), V(x1, r1, 0)); hub_faces.append(e.revolve(V(0, 0, 0), V(1, 0, 0), 360))
write_stl(Part.Compound(hub_faces), 'rot_hub')
# shroud: NGV bore continues over the rotor to x 118.8 (ring end), then free (keep the bore radius to the outlet plane)
shroud_rot = Part.makeCylinder(rb, X_OUT - X_MID, V(X_MID, 0, 0), V(1, 0, 0)).Faces[0]
write_stl(shroud_rot, 'rot_shroud')

# ---------------------------------------------------------------- passage angles / metadata for the case generator
def theta_range(shape, r_lo, r_hi):
    ths = []
    for f in shape.Faces:
        u0, u1, v0, v1 = f.ParameterRange
        for i in range(21):
            for j in range(21):
                p = f.valueAt(u0 + (u1 - u0) * i / 20, v0 + (v1 - v0) * j / 20)
                r = math.hypot(p.y, p.z)
                if r_lo <= r <= r_hi:
                    ths.append(math.degrees(math.atan2(p.z, p.y)))
    return min(ths), max(ths)

tv = theta_range(piece, 22.0, 35.6); tb = theta_range(bpiece, 18.5, 35.3)
meta = dict(units='mm', axis='x', x_inlet=X_IN, x_interface=X_MID, x_outlet=X_OUT, r_hub_ngv=G.R_NGV_HUB, r_shroud_inlet=36.05,
            r_bore=rb, r_tip=G.R_TIP, r_hub_rotor_in=G.R_H0, r_hub_rotor_out=G.R_H1, x_flare=[G.X_FL0, G.X_FL1],
            Z_ngv=G.Z_NGV, Z_rot=G.Z_ROT, pitch_ngv_deg=360.0 / G.Z_NGV, pitch_rot_deg=360.0 / G.Z_ROT,
            vane_theta_deg=list(tv), blade_theta_deg=list(tb), x_ngv_le_te=[G.NGV_LE, G.NGV_TE], x_rot_le_te=[G.ROT_LE, G.ROT_TE],
            design=dict(N_rpm=G.N_RPM, mdot_kg_s=G.ML['mg'], T01_K=G.ML['T01'], P01_Pa=G.ML['P01'], P2_Pa=G.ML['P2'], T2_K=G.ML['T2'],
                        P3_Pa=G.ML['P3'], P03_Pa=G.ML['P03'], T03_K=G.ML['T03'], throat_ngv_mm2_meanline=G.ML['throat_ngv_mm2'],
                        throat_rot_mm2_meanline=G.ML['throat_rot_mm2'], source='sim/gg_turbine_design.json'))
json.dump(meta, open(os.path.join(OUT, 'passage.json'), 'w'), indent=1)
log('vane theta %.2f..%.2f deg (pitch %.2f), blade theta %.2f..%.2f (pitch %.2f)' % (tv[0], tv[1], 360 / G.Z_NGV, tb[0], tb[1], 360 / G.Z_ROT))
log('written', os.path.join(OUT, 'passage.json'))
