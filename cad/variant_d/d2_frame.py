# GR180 version D2 - BASE FRAME + MOUNTS: one welded RHS frame on 4 anti-vibration mounts.
# Engine supports (thermal growth free):
#   FIXED   front: 12 mm saddle bolted (2 x M12) to the INT-111 tube sheet (the stiff intake ring at x -136..-130);
#   SLIDING rear : 2-half collar on the turbine plenum RT-120 with centre-line trunnion ears on PTFE/graphite slide pads,
#                  x-slots (axial growth ~1 mm) - the axis height stays fixed because the pads are at z = 0;
#   SLIDING exh. : the EX-113 centre-line lugs on the same pad type (axial growth ~3 mm).
# 4 lifting lugs on the rail ends.  Frame top at z -256 (tube sheet OD 500 is the lowest engine item), rails y +/-190.
# ENG frame mm.  Run after d2_intake.py and d2_exhaust.py:
#   LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_frame.py -> cad_out/variant_d/D2/FRAME/*.step + d2_interfaces.json
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

INT = json.load(open(os.path.join(OUT, 'd2_intake_interfaces.json')))
EXH = json.load(open(os.path.join(OUT, 'd2_exhaust_interfaces.json')))
CALC_J = json.load(open(CALC))
X_TS = INT['interfaces']['front_support']['x_face']           # -130 (tube sheet rear face)
LUG = EXH['interfaces']['lugs']
Z_T = -256.0                  # frame top
H_R, W_R = 60.0, 40.0         # RHS 60 x 40 x 3, standing
Y_R = 190.0                   # rail centre lines
X0, X1 = -170.0, 420.0        # rail ends
Z_PAD = -6.0                  # pad top = lug / ear bottom (lugs at z -6..+6)
X_COL = (128.0, 146.0)        # plenum collar (RT-120 shell r 81..84, x 118..158)


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
fr = []
for s in (1, -1):
    fr.append(rhs(X0, X1, s * Y_R - W_R / 2, s * Y_R + W_R / 2, Z_T - H_R, Z_T))
yi = Y_R - W_R / 2
for (xa, xb) in ((-150.0, -110.0), (117.0, 157.0), (X1 - 40.0, X1)):
    fr.append(rhs(xa, xb, -yi, yi, Z_T - H_R, Z_T, along='y'))
frame = fr[0]
for f in fr[1:]:
    frame = frame.fuse(f)
for s in (1, -1):                                            # 4 mount pads 8 mm under the rail ends (M10 studs)
    for x in (X0 + 25, X1 - 25):
        frame = frame.fuse(Part.makeBox(60, 60, 8, V(x - 30, s * Y_R - 30, Z_T - H_R - 8)).cut(
            Part.makeCylinder(5.5, 20, V(x, s * Y_R, Z_T - H_R - 10), V(0, 0, 1))))
parts['FR-110_Base_Frame_RHS'] = (frame.removeSplitter(), 'S355',
    'RHS 60x40x3 S355 (EN 10219): 2 rails L590 at y +/-190 + 3 cross members; 4 x 8 mm mount pads; MAG welded, hot-dip galvanised or 2K epoxy')

# ---------------------------------------------------------------- FR-120 fixed front saddle (to the tube sheet)
xs0, xs1 = X_TS, X_TS + 12.0
sad = Part.makeBox(12, 380, -120 - Z_T, V(xs0, -190, Z_T)).cut(Part.makeCylinder(167.0, 30, V(xs0 - 5, 0, 0), V(1, 0, 0)))
for a in (250.0, 290.0):
    th = math.radians(a)
    sad = sad.cut(Part.makeCylinder(6.5, 30, V(xs0 - 5, 237 * math.cos(th), 237 * math.sin(th)), V(1, 0, 0)))
for s in (1, -1):                                            # 2 gussets behind the saddle
    g = Part.Face(Part.makePolygon([V(xs1, 0, Z_T), V(xs1 + 60, 0, Z_T), V(xs1, 0, -175), V(xs1, 0, Z_T)])).extrude(V(0, 10, 0))
    g.translate(V(0, s * 120 - 5, 0))
    sad = sad.fuse(g)
parts['FR-120_Front_Saddle'] = (sad.removeSplitter(), 'S355',
    '12 mm S355 laser-cut cradle (arc R167 round the plenum cylinder) + 2 gussets, welded on the front cross member; 2 x M12 8.8 to INT-111 at r237 (250/290 deg): FIXED point')

# ---------------------------------------------------------------- FR-130 plenum collar (2 halves, centre-line ears)
col = cyl(X_COL[0], X_COL[1], 93.0, 85.0)
for s in (1, -1):
    ear = Part.makeBox(X_COL[1] - X_COL[0], 205 - 90, 12, V(X_COL[0], 90 if s > 0 else -205, -6))
    ear = ear.cut(Part.makeBox(14, 13, 20, V(sum(X_COL) / 2 - 7, 183.5 if s > 0 else -196.5, -10)))
    col = col.fuse(ear)
col = col.cut(cyl(X_COL[0] - 1, X_COL[1] + 1, 85.0))
parts['FR-130_Plenum_Collar_2halves'] = (col.removeSplitter(), '1.4828',
    '1.4828 laser-cut 2 halves, bore 170 over 1 mm mica/ceramic paper on the RT-120 shell (r84), ears 12 mm at the centre-line with x-slots 14 x 13 (M12 A286 shoulder bolts); split at z = 0')

# ---------------------------------------------------------------- FR-131 slide pedestals (2 at the collar, 2 at the exhaust lugs)
peds = []
for xc in (sum(X_COL) / 2, LUG['slot_centre_x']):
    for s in (1, -1):
        post = rhs(xc - 20, xc + 20, s * Y_R - 20, s * Y_R + 20, Z_T, Z_PAD - 14, along='z')
        top = Part.makeBox(50, 50, 14, V(xc - 25, s * Y_R - 25, Z_PAD - 14))
        top = top.cut(Part.makeCylinder(6.0, 30, V(xc, s * Y_R, Z_PAD - 20), V(0, 0, 1)))
        peds.append(post.fuse(top))
parts['FR-131_Slide_Pedestals_x4'] = (Part.makeCompound(peds), 'S355',
    '4 x RHS 40x40x3 posts + 14 mm top plate (6 mm calcium-silicate insulating board + 2 mm PTFE/graphite-bronze slide plate + M12 tapped); posts welded on the rails')

# ---------------------------------------------------------------- FR-140 anti-vibration mounts (envelopes)
mts = []
for s in (1, -1):
    for x in (X0 + 25, X1 - 25):
        z0 = Z_T - H_R - 8 - 45
        m = Part.makeCylinder(30, 35, V(x, s * Y_R, z0 + 10), V(0, 0, 1)).fuse(Part.makeBox(90, 50, 10, V(x - 45, s * Y_R - 25, z0)))
        mts.append(m)
parts['FR-140_AV_Mounts_x4_env'] = (Part.makeCompound(mts), 'rubber',
    'BUY: 4 x cylindrical rubber/metal mount D60 x 35 + base flange, M10, ~60 Sh, ~50 kg rated each (static defl. ~2.5 mm, f_n ~10 Hz)')

# ---------------------------------------------------------------- FR-150 lifting lugs (rail ends, outer faces)
lifts = []
for s in (1, -1):
    for x in (X0 + 10, X1 - 50):
        p = Part.makeBox(40, 10, 110, V(x, (Y_R + W_R / 2) if s > 0 else -(Y_R + W_R / 2) - 10, Z_T - H_R))
        p = p.cut(Part.makeCylinder(15, 400, V(x + 20, -200, Z_T + 25), V(0, 1, 0)))
        lifts.append(p)
parts['FR-150_Lifting_Lugs_x4'] = (Part.makeCompound(lifts), 'S355',
    '4 x 10 mm S355 plates 40 x 110, hole D30 (shackle 1 t), welded to the rail outer faces; lift with a 4-leg sling + spreader')

growth = CALC_J['frame_supports']
meta = dict(subsystem='FRAME', frame='ENG mm', footprint_mm=dict(x=[X0, X1], y=[-(Y_R + W_R / 2 + 10), Y_R + W_R / 2 + 10]),
            heights=dict(frame_top_z=Z_T, floor_z=Z_T - H_R - 8 - 45, axis_above_floor=-(Z_T - H_R - 8 - 45),
                         exhaust_flange_top_z=EXH['interfaces']['outlet']['centre'][2]),
            supports=dict(fixed_front=dict(x=[xs0, xs1], to='INT-111 tube sheet 2 x M12 (r237, 250/290 deg)'),
                          sliding_plenum=dict(x=X_COL, slot_centre=[sum(X_COL) / 2, 190.0], slide='x'),
                          sliding_exhaust=dict(x=LUG['x'], slot_centre=[LUG['slot_centre_x'], 190.0], slide='x'),
                          growth_mm=dict(collar=growth['axial_growth_at_rear_collar_mm'], exhaust_lugs=growth['axial_growth_at_exhaust_lugs_mm'],
                                         slot_free_each_side=growth['slot_length_each_side_mm'])),
            mounts=dict(n=4, xy=[[X0 + 25, Y_R], [X0 + 25, -Y_R], [X1 - 25, Y_R], [X1 - 25, -Y_R]], load_N=growth['load_per_mount_N']),
            lifting=dict(n=4, hole_d=30, centres=[[X0 + 30, Y_R + 25, Z_T + 25], [X1 - 30, Y_R + 25, Z_T + 25]]))
rows = export(parts, 'FRAME', meta)

# ---------------------------------------------------------------- combined interfaces file
allj = dict(title='GR180 D2 intake / exhaust / frame interfaces', coords='ENG mm (ROOF X = 1.880 + x/1000, Y = 7.850 + y/1000, Z = 0.600 + z/1000)',
            calc='sim/variant_d/d2_intake_exhaust_calc.json', superseded=SUPERSEDED,
            intake=INT['interfaces'], exhaust=EXH['interfaces'], exhaust_dp=EXH['dp'], base_frame=meta)
json.dump(allj, open(os.path.join(OUT, 'd2_interfaces.json'), 'w'), indent=1)
print('footprint x %.0f..%.0f, y +/-%.0f, floor z %.0f, axis %.0f above floor' % (X0, X1, Y_R + W_R / 2 + 10, meta['heights']['floor_z'],
                                                                              meta['heights']['axis_above_floor']))
