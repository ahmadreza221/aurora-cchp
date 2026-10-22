"""E1 bore-less blisk: 1/29 cyclic-symmetry sector with PLANAR periodic cut faces for CalculiX (sim/engine/e1_blisk_cyclic.py,
sim/engine/e1_sector_stress.py).

Sector = bore-less disc (final, machined) cut by two radial planes theta0 and theta0 + pitch, plus the whole blade piece
(blade above the hub, with its R0.8 root fillet). The planes are placed so the fillet footprint on the hub is centred
between them (cyclic symmetry only needs periodic cut faces; the blade may lean over them above the hub).
Writes cad_out/engine/E1/E1_sector_boreless.step and .json (theta0_deg, pitch_deg, footprint).
Run:  LANG=en_US.UTF-8 freecadcmd cad/engine/e1_sector_tool.py
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

V = App.Vector
T0 = time.time()


def log(*a):
    print('[%5.0fs]' % (time.time() - T0), *a, flush=True)


rot = G.design_rotor()
blade_raw, blade_f, blade_c, nw = G.fc_blade(rot)
disc = G.fc_disc('final', G.DISC_BORELESS)
piece = blade_f.cut(disc)
log('blade piece vol %.2f mm3 valid %s; disc vol %.0f' % (piece.Volume, piece.isValid(), disc.Volume))

# footprint of the blade piece on the hub: theta of the piece's points within 0.25 mm of the hub surface
pts = []
for f in piece.Faces:
    for u in [i / 24 for i in range(25)]:
        for v in [i / 24 for i in range(25)]:
            u0, u1, v0, v1 = f.ParameterRange
            p = f.valueAt(u0 + (u1 - u0) * u, v0 + (v1 - v0) * v)
            if f.isInside(p, 1e-4, True):
                pts.append((p.x, math.hypot(p.y, p.z), math.atan2(p.z, p.y)))
rh = {x: float(G.r_hub(x)) for x in sorted(set(round(p[0], 3) for p in pts))}
foot = [th for x, r, th in pts if r <= float(G.r_hub(x)) + 0.25]
pitch = 2 * math.pi / G.Z_ROT
th_lo, th_hi = min(foot), max(foot)
mid = 0.5 * (th_lo + th_hi)
theta0 = mid - pitch / 2
clear = min(th_lo - theta0, theta0 + pitch - th_hi)
log('footprint theta %.2f .. %.2f deg (span %.2f, pitch %.2f) -> cut planes %.2f / %.2f deg, clearance %.2f deg'
    % (math.degrees(th_lo), math.degrees(th_hi), math.degrees(th_hi - th_lo), math.degrees(pitch), math.degrees(theta0),
       math.degrees(theta0 + pitch), math.degrees(clear)))
if clear < 0:
    raise SystemExit('fillet footprint wider than the pitch: planar cut not possible')

# wedge: triangle in the yz-plane (apex on the axis) extruded along x
R = 60.0
tri = Part.makePolygon([V(100.0, 0, 0), V(100.0, R * math.cos(theta0), R * math.sin(theta0)),
                        V(100.0, R * math.cos(theta0 + pitch), R * math.sin(theta0 + pitch)), V(100.0, 0, 0)])
wedge = Part.Face(tri).extrude(V(25.0, 0, 0))
disc_cut = disc.common(wedge)
log('disc sector vol %.1f (x%d = %.0f vs disc %.0f) solids %d valid %s'
    % (disc_cut.Volume, G.Z_ROT, G.Z_ROT * disc_cut.Volume, disc.Volume, len(disc_cut.Solids), disc_cut.isValid()))
sector = disc_cut.fuse(piece)
try:
    sector = sector.removeSplitter()
except Exception:
    pass
sols = [s for s in sector.Solids if s.Volume > 1.0]
log('sector solids %d, vol %.1f (disc sector %.1f + blade %.1f = %.1f), valid %s, faces %d'
    % (len(sols), sum(s.Volume for s in sols), disc_cut.Volume, piece.Volume, disc_cut.Volume + piece.Volume, sector.isValid(), len(sector.Faces)))
if len(sols) != 1:
    raise SystemExit('sector is not a single solid')
sec = sols[0]
OUT = G.OUT
os.makedirs(OUT, exist_ok=True)
sec.exportStep(os.path.join(OUT, 'E1_sector_boreless.step'))
json.dump(dict(theta0_deg=math.degrees(theta0), pitch_deg=math.degrees(pitch), Z=G.Z_ROT,
               footprint_deg=[math.degrees(th_lo), math.degrees(th_hi)], clearance_deg=math.degrees(clear),
               vol_mm3=sec.Volume, disc_sector_mm3=disc_cut.Volume, blade_mm3=piece.Volume, disc='DISC_BORELESS final'),
          open(os.path.join(OUT, 'E1_sector_boreless.json'), 'w'), indent=1)
log('written', os.path.join(OUT, 'E1_sector_boreless.step'))
