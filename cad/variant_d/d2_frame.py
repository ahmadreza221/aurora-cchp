# GR180 version D2 - BASE FRAME rev 2 (user feedback 2026-10-23): one welded RHS frame on 4 anti-vibration mounts, low.
# Engine supports (thermal growth free):
#   FIXED   front: FR-120 pedestal plate bolted (2 x M10 along x) to the foot of the INT-112 intake rear ring (core front,
#                  x -8.4..-2.4) - the stiff ring that also carries the plenum and the pod struts;
#   SLIDING rear : plain pedestals FR-131 under the 2 D2R turbine-housing pads (x 128..142, y +/-70..85, bottom z -10,
#                  vertical M10 at y +/-79 in an x-slot) and under the 2 EX-113 exhaust lugs (centre-line, x-slot).
# Rails at y +/-90 carry the 4 pedestals; end cross members reach y +/-150 for the mounts and the lifting lugs.
# Frame top z -126 (lowest engine item: DN125 exhaust flange r 120).  ENG frame mm.
# Run after d2_intake.py and d2_exhaust.py: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_frame.py
#   -> cad_out/variant_d/D2/FRAME/*.step + d2_frame_interfaces.json + d2_interfaces.json
import sys, os, math, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

INT = json.load(open(os.path.join(OUT, 'd2_intake_interfaces.json')))
EXH = json.load(open(os.path.join(OUT, 'd2_exhaust_interfaces.json')))
CALC_J = json.load(open(CALC))
LUG = EXH['interfaces']['lugs']
Z_T = -126.0                  # frame top
H_R, W_R = 60.0, 40.0         # RHS 60 x 40 x 3, standing
Y_R = 90.0                    # rail centre lines (pedestals on the rails)
Y_X = 150.0                   # end cross members half length (mounts, lifting lugs)
X0, X1 = -160.0, 340.0        # frame ends
TP = dict(x=(128.0, 142.0), bolt_x=135.0, bolt_y=79.0, z_bottom=-10.0)   # D2R turbine housing pads (commit 20686b0)
X_FOOT = INT['interfaces']['front_support']['face_x']                   # -2.4

for f in glob.glob(os.path.join(OUT, 'FRAME', '*.step')):
    os.remove(f)


def rhs(x0, x1, y0, y1, z0, z1, t=3.0, along='x'):
    o = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
    if along == 'x':
        i = Part.makeBox(x1 - x0 + 2, y1 - y0 - 2 * t, z1 - z0 - 2 * t, V(x0 - 1, y0 + t, z0 + t))
    elif along == 'y':
        i = Part.makeBox(x1 - x0 - 2 * t, y1 - y0 + 2, z1 - z0 - 2 * t, V(x0 + t, y0 - 1, z0 + t))
    else:
        i = Part.makeBox(x1 - x0 - 2 * t, y1 - y0 - 2 * t, z1 - z0 + 2, V(x0 + t, y0 + t, z0 - 1))
    return o.cut(i)


parts = {}
# ---------------------------------------------------------------- FR-110 welded RHS base frame
zb = Z_T - H_R
frame = rhs(X0 + 40, X1 - 40, Y_R - W_R / 2, Y_R + W_R / 2, zb, Z_T)
frame = frame.fuse(rhs(X0 + 40, X1 - 40, -Y_R - W_R / 2, -Y_R + W_R / 2, zb, Z_T))
frame = frame.fuse(rhs(X0, X0 + 40, -Y_X, Y_X, zb, Z_T, along='y'))                       # front end cross member
frame = frame.fuse(rhs(X1 - 40, X1, -Y_X, Y_X, zb, Z_T, along='y'))                       # rear end cross member
frame = frame.fuse(rhs(-20.0, 20.0, -Y_R + W_R / 2, Y_R - W_R / 2, zb, Z_T, along='y'))  # mid member under the front pedestal
MOUNTS = [(X0 + 25, s * (Y_X - 25)) for s in (1, -1)] + [(X1 - 25, s * (Y_X - 25)) for s in (1, -1)]
for (x, y) in MOUNTS:
    frame = frame.fuse(Part.makeBox(50, 50, 8, V(x - 25, y - 25, zb - 8)).cut(Part.makeCylinder(5.5, 20, V(x, y, zb - 10), V(0, 0, 1))))
parts['FR-110_Base_Frame_RHS'] = (frame.removeSplitter(), 'S355',
    'RHS 60x40x3 S355 (EN 10219): 2 rails at y +/-90 + 2 end cross members L300 + 1 mid member, 4 x 8 mm mount pads; MAG on a flat table, galvanised or 2K epoxy')

# ---------------------------------------------------------------- FR-120 fixed front pedestal (to the intake rear-ring foot)
ped = Part.makeBox(12, 90, -80.0 - Z_T, V(X_FOOT, -45, Z_T))
for sgn in (1, -1):
    ped = ped.cut(Part.makeCylinder(5.5, 30, V(X_FOOT - 5, sgn * 25, -102), V(1, 0, 0)))
    g = Part.Face(Part.makePolygon([V(X_FOOT + 12, 0, Z_T), V(X_FOOT + 50, 0, Z_T), V(X_FOOT + 12, 0, -92), V(X_FOOT + 12, 0, Z_T)])).extrude(V(0, 8, 0))
    g.translate(V(0, sgn * 36 - 4, 0))
    ped = ped.fuse(g)
parts['FR-120_Front_Pedestal_Fixed'] = (ped.removeSplitter(), 'S355',
    '12 mm S355 plate 90 x 46 + 2 gussets, welded on the mid member; 2 x M10 8.8 into the INT-112 foot (face x -2.4): FIXED point')

# ---------------------------------------------------------------- FR-131 plain slide pedestals x4 (turbine pads, exhaust lugs)
peds = []
X_LC = 0.5 * (LUG['x'][0] + LUG['x'][1])
# turbine pads: round M10 in the pad, x-slot in the pedestal; exhaust lugs: x-slot in the lug, round hole in the pedestal,
# post shifted forward so it stays clear of the DN125 outlet flange disc
for (xc, xb, ztop, yb, slot) in ((TP['bolt_x'], TP['bolt_x'], TP['z_bottom'], TP['bolt_y'], True),
                                 (X_LC - 10.0, X_LC, LUG['z'][0], LUG['slot_y'], False)):
    for sgn in (1, -1):
        post = rhs(xc - 20, xc + 20, sgn * Y_R - 20, sgn * Y_R + 20, Z_T, ztop - 12, along='z')
        top = Part.makeBox(46, 34, 12, V(xc - 23, (74 if sgn > 0 else -108), ztop - 12))
        if slot:
            top = top.cut(Part.makeBox(12, 11, 30, V(xb - 6, sgn * yb - 5.5, ztop - 20)))
        else:
            top = top.cut(Part.makeCylinder(5.5, 30, V(xb, sgn * yb, ztop - 20), V(0, 0, 1)))
        peds.append(post.fuse(top))
parts['FR-131_Slide_Pedestals_x4'] = (Part.makeCompound(peds), 'S355',
    '4 x RHS 40x40x3 posts + 12 mm top (6 mm calcium-silicate board + 2 mm PTFE / graphite-bronze slide plate on S355), x-slot 12 x 11, '
    'M10 A286 shoulder bolt + Belleville washers hand-tight; 2 under the turbine pads (x 135), 2 under the exhaust lugs')

# ---------------------------------------------------------------- FR-140 anti-vibration mounts (envelopes)
mts = []
for (x, y) in MOUNTS:
    z0 = zb - 8 - 45
    mts.append(Part.makeCylinder(25, 35, V(x, y, z0 + 10), V(0, 0, 1)).fuse(Part.makeBox(80, 44, 10, V(x - 40, y - 22, z0))))
parts['FR-140_AV_Mounts_x4_env'] = (Part.makeCompound(mts), 'rubber',
    'BUY: 4 x cylindrical rubber-metal mount D50 x 35 + base flange, M10, ~55 Sh, ~30 kg rated each (static defl. ~2 mm, f_n ~11 Hz)')

# ---------------------------------------------------------------- FR-150 lifting lugs (end cross member ends)
lifts = []
for sgn in (1, -1):
    for x in (X0, X1 - 40):
        p = Part.makeBox(40, 10, zb + 0 - (zb) + 90, V(x, Y_X if sgn > 0 else -Y_X - 10, zb))
        p = p.cut(Part.makeCylinder(12.5, 400, V(x + 20, -200, Z_T + 14), V(0, 1, 0)))
        lifts.append(p)
parts['FR-150_Lifting_Lugs_x4'] = (Part.makeCompound(lifts), 'S355',
    '4 x 10 mm S355 plates 40 x 90, hole D25 (0.5 t shackle), welded to the end cross member ends; 4-leg sling + spreader')

growth = CALC_J['frame_supports']
meta = dict(subsystem='FRAME', rev=2, frame='ENG mm', footprint_mm=dict(x=[X0, X1], y=[-(Y_X + 10), Y_X + 10]),
            heights=dict(frame_top_z=Z_T, floor_z=zb - 8 - 45, axis_above_floor=-(zb - 8 - 45)),
            supports=dict(fixed_front=dict(x=[X_FOOT, X_FOOT + 12], to='INT-112 rear-ring foot, 2 x M10 (y +/-25, z -102)'),
                          sliding_turbine=dict(x=TP['x'], bolt=[TP['bolt_x'], TP['bolt_y']], pad_z=TP['z_bottom'], slide='x'),
                          sliding_exhaust=dict(x=LUG['x'], slot_y=LUG['slot_y'], pad_z=LUG['z'][0], slide='x'),
                          growth_mm=dict(turbine_pads=growth['axial_growth_at_turbine_pads_mm'], exhaust_lugs=growth['axial_growth_at_exhaust_lugs_mm'])),
            mounts=dict(n=4, xy=MOUNTS, load_N=growth['load_per_mount_N']),
            lifting=dict(n=4, hole_d=25, x=[X0 + 20, X1 - 20], y=[Y_X + 5, -Y_X - 5], z=Z_T + 14))
rows = export(parts, 'FRAME', meta)

allj = dict(title='GR180 D2 intake / exhaust / frame interfaces (rev 2)', coords='ENG mm (ROOF X = 1.880 + x/1000, Y = 7.850 + y/1000, Z = 0.600 + z/1000)',
            calc='sim/variant_d/d2_intake_exhaust_calc.json', superseded=SUPERSEDED,
            intake=INT['interfaces'], exhaust=EXH['interfaces'], exhaust_dp=EXH['dp'], base_frame=meta)
json.dump(allj, open(os.path.join(OUT, 'd2_interfaces.json'), 'w'), indent=1)
print('footprint x %.0f..%.0f, y +/-%.0f, floor z %.0f, axis %.0f above floor' % (X0, X1, Y_X + 10, meta['heights']['floor_z'],
                                                                              meta['heights']['axis_above_floor']))
