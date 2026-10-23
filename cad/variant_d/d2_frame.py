# GR180 version D2 - BASE FRAME rev 3 (user feedback 2026-10-23): one welded RHS frame on 4 anti-vibration mounts, low.
# Engine supports (thermal growth free, no double constraint):
#   FIXED   front: FR-120 pedestal plate bolted (2 x M10 along x) to the foot of the INT-112 intake rear ring (core front,
#                  x -8.4..-2.4) - the stiff ring that also carries the plenum and the 3 pod struts;
#   SLIDING rear : plain pedestals FR-131 under the 2 D2R turbine-housing pads (x 128..142, y +/-70..85, bottom z -10,
#                  vertical M10 at y +/-79 in an x-slot) and under the 2 EX-113 lugs on the exhaust diffuser.
#   POD     : FR-170 cradle under the generator pod at its CG (x -205) on FR-171: soft elastomer pad + PTFE slide plate +
#             jack screw.  WEIGHT RELIEF ONLY - the 3 intake struts stay the one locator of the pod (alignment to the core
#             and the quill is set once on the bench), the cradle is free in x / y and soft in z, so frame or mount
#             deflection cannot misalign the quill and nothing is located twice.
#   FILTER  : 4 posts FR-160 carry the intake filter box (floor channels at x -205 / +80) - not the plenum.
# Frame top z -126.  The filter box overhangs the frame (y +/-301.5 at z >= 105): lift the skid with the box removed.
# ENG frame mm.
# Run after d2_intake.py and d2_exhaust.py: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_frame.py
#   -> cad_out/variant_d/D2/FRAME/*.step + d2_frame_interfaces.json + d2_interfaces.json
import sys, os, math, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

INT = json.load(open(os.path.join(OUT, 'd2_intake_interfaces.json')))
EXH = json.load(open(os.path.join(OUT, 'd2_exhaust_interfaces.json')))
CALC_J = json.load(open(CALC))
LUG = EXH['interfaces']['lugs']
FB = INT['interfaces']['filter_box']
Z_T = -126.0                  # frame top
H_R, W_R = 60.0, 40.0         # RHS 60 x 40 x 3, standing
Y_R = 90.0                    # rail centre lines (pedestals on the rails)
Y_XF, Y_XR = 150.0, 150.0     # front / rear cross member half lengths (AUX skid AX-610 starts at y -160)
X0, X1 = -225.0, 260.0        # frame ends
TP = dict(x=(128.0, 142.0), bolt_x=135.0, bolt_y=79.0, z_bottom=-10.0)   # D2R turbine housing pads (20686b0 / 03352b0)
X_FOOT = INT['interfaces']['front_support']['face_x']                   # -2.4
X_POD = -205.0                # pod cradle centre (pod CG x ~ -198)
R_POD = 55.0
POSTS = [(-205.0, 130.0, 30.0, 30.0), (100.0, 90.0, 20.0, 30.0)]   # filter box posts: x, |y|, size x, size y (rear pair clear of the AUX ignition trafo x <= 90)
Z_CH = 105.0                  # channel bottom

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
frame = frame.fuse(rhs(X0, X0 + 40, -Y_XF, Y_XF, zb, Z_T, along='y'))                    # front cross member (pod cradle + box posts)
frame = frame.fuse(rhs(X1 - 40, X1, -Y_XR, Y_XR, zb, Z_T, along='y'))                    # rear cross member
frame = frame.fuse(rhs(-20.0, 20.0, -Y_R + W_R / 2, Y_R - W_R / 2, zb, Z_T, along='y'))  # mid member under the front pedestal
MOUNTS = [(X0 + 20, s * 125.0) for s in (1, -1)] + [(X1 - 20, s * 125.0) for s in (1, -1)]
for (x, y) in MOUNTS:
    frame = frame.fuse(Part.makeBox(50, 50, 8, V(x - 25, y - 25, zb - 8)).cut(Part.makeCylinder(5.5, 20, V(x, y, zb - 10), V(0, 0, 1))))
parts['FR-110_Base_Frame_RHS'] = (frame.removeSplitter(), 'S355',
    'RHS 60x40x3 S355 (EN 10219): 2 rails L405 at y +/-90, front cross member L300 (x -225..-185: pod cradle + box posts), '
    'rear cross member L300 (x 220..260), mid member at x 0; 4 x 8 mm mount pads; MAG on a flat table, galvanised or 2K epoxy')

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
for (xc, ztop, yb, slot) in ((TP['bolt_x'], TP['z_bottom'], TP['bolt_y'], True), (X_LC, LUG['z'][0], LUG['slot_y'], False)):
    for sgn in (1, -1):
        post = rhs(xc - 20, xc + 20, sgn * Y_R - 20, sgn * Y_R + 20, Z_T, ztop - 12, along='z')
        top = Part.makeBox(46, 34, 12, V(xc - 23, (74 if sgn > 0 else -108), ztop - 12))
        if slot:
            top = top.cut(Part.makeBox(12, 11, 30, V(xc - 6, sgn * yb - 5.5, ztop - 20)))
        else:
            top = top.cut(Part.makeCylinder(5.5, 30, V(xc, sgn * yb, ztop - 20), V(0, 0, 1)))
        peds.append(post.fuse(top))
parts['FR-131_Slide_Pedestals_x4'] = (Part.makeCompound(peds), 'S355',
    '4 x RHS 40x40x3 posts + 12 mm top (6 mm calcium-silicate board + 2 mm PTFE / graphite-bronze slide plate on S355); '
    '2 under the turbine pads (x-slot 12 x 11 at x 135), 2 under the diffuser lugs (M10 hole, the lug has the slot); '
    'M10 A286 shoulder bolts + Belleville washers hand-tight')

# ---------------------------------------------------------------- FR-140 anti-vibration mounts (envelopes)
mts = []
for (x, y) in MOUNTS:
    z0 = zb - 8 - 45
    mts.append(Part.makeCylinder(25, 35, V(x, y, z0 + 10), V(0, 0, 1)).fuse(Part.makeBox(80, 44, 10, V(x - 40, y - 22, z0))))
parts['FR-140_AV_Mounts_x4_env'] = (Part.makeCompound(mts), 'rubber',
    'BUY: 4 x cylindrical rubber-metal mount D50 x 35 + base flange, M10, ~55 Sh, ~40 kg rated each (static defl. ~2 mm, f_n ~11 Hz)')

# ---------------------------------------------------------------- FR-150 lifting lugs (front: outside the filter box, rear: cross member ends)
lifts = []
for sgn in (1, -1):
    for (x, yy) in ((X0, Y_XF), (X1 - 40, Y_XR)):
        p = Part.makeBox(40, 10, 90, V(x, yy if sgn > 0 else -yy - 10, zb))
        p = p.cut(Part.makeCylinder(12.5, 800, V(x + 20, -400, Z_T + 14), V(0, 1, 0)))
        lifts.append(p)
parts['FR-150_Lifting_Lugs_x4'] = (Part.makeCompound(lifts), 'S355',
    '4 x 10 mm S355 plates 40 x 90, hole D25 (0.5 t shackle) at the cross member ends (y +/-150); '
    'lift with the filter box removed (8 x M8 + 8 x M6) - the slings would touch its overhang; 4-leg sling + spreader')

# ---------------------------------------------------------------- FR-160 filter box posts x4
fp = []
for (xc, ya, sx, sy) in POSTS:
    for sgn in (1, -1):
        yc = sgn * ya
        post = rhs(xc - sx / 2, xc + sx / 2, yc - sy / 2, yc + sy / 2, Z_T, Z_CH - 5, t=2.0, along='z')
        top = Part.makeBox(25, 50, 5, V(xc - 12.5, yc - 25, Z_CH - 5))
        top = top.cut(Part.makeCylinder(4.5, 20, V(xc, yc + 15, Z_CH - 10), V(0, 0, 1))).cut(Part.makeCylinder(4.5, 20, V(xc, yc - 15, Z_CH - 10), V(0, 0, 1)))
        fp.append(post.fuse(top))
parts['FR-160_Filter_Box_Posts_x4'] = (Part.makeCompound(fp), 'S355',
    'front pair RHS 30x30x2 on the front cross member (x -205, y +/-130), rear pair RHS 30x20x2 on the rails (x 100, y +/-90); '
    '5 mm top plates 25 x 50, 2 x M8 each into rivnuts of the box floor channels (rubber washers); carry the filter box + cell (~15 kg)')

# ---------------------------------------------------------------- FR-170 pod cradle + FR-171 weight-relief pedestal
xc0, xc1 = X_POD - 15.0, X_POD + 15.0
band = cyl(xc0, xc1, R_POD + 6.0, R_POD + 0.1)
lower = Part.makeBox(40, 400, 400, V(xc0 - 5, -200, -R_POD * 0.34 - 400))       # keep the band below z -18.7 (~140 deg arc)
band = band.common(lower)
blk = Part.makeBox(xc1 - xc0, 50, 18, V(xc0, -25, -74)).cut(Part.makeCylinder(R_POD + 0.1, 60, V(xc0 - 10, 0, 0), V(1, 0, 0)))
cradle = band.fuse(blk)
parts['FR-170_Pod_Cradle'] = (cradle.removeSplitter(), '1.4301',
    '1.4301: 6 mm rolled 140 deg saddle band x 30 wide + 50 x 18 base block, lined with 1 mm PTFE-faced EPDM (r 55.1); '
    'at the pod CG (x -205), clear of the bearings (x -266 / -136), terminal box and glycol ports (all on top)')
pst = rhs(X_POD - 20, X_POD + 20, -20, 20, Z_T, -100.0, along='z')
pst = pst.fuse(Part.makeBox(60, 60, 8, V(X_POD - 30, -30, -100.0)))
pst = pst.fuse(Part.makeCylinder(25.0, 18.0, V(X_POD, 0, -92.0), V(0, 0, 1)))    # elastomer pad + jack nut (z -92..-74)
parts['FR-171_Pod_Weight_Relief_Pedestal'] = (pst.removeSplitter(), 'S355',
    'RHS 40x40x3 post on the front cross member + 8 mm top plate with M16 jack screw / lock nut + elastomer pad D50 x 15 '
    '(~40 N/mm, NR 50 Sh) + 2 mm PTFE slide disc under the cradle block: preload = pod weight ~47 N (1.2 mm squeeze), free in x / y')

growth = CALC_J['frame_supports']
meta = dict(subsystem='FRAME', rev=3, frame='ENG mm', footprint_mm=dict(x=[X0, X1], y=[-(Y_XF + 10), Y_XF + 10]),
            heights=dict(frame_top_z=Z_T, floor_z=zb - 8 - 45, axis_above_floor=-(zb - 8 - 45)),
            supports=dict(fixed_front=dict(x=[X_FOOT, X_FOOT + 12], to='INT-112 rear-ring foot, 2 x M10 (y +/-25, z -102)'),
                          sliding_turbine=dict(x=TP['x'], bolt=[TP['bolt_x'], TP['bolt_y']], pad_z=TP['z_bottom'], slide='x'),
                          sliding_exhaust=dict(x=LUG['x'], slot_y=LUG['slot_y'], pad_z=LUG['z'][0], slide='x (slot in the lug)'),
                          pod_weight_relief=dict(x=[xc0, xc1], cradle_r=R_POD, pedestal_xy=[X_POD, 0.0], **{k: growth['pod_support'][k] for k in (
                              'mass_kg', 'x_cg', 'preload_N', 'pad_stiffness_N_mm', 'pad_deflection_mm', 'concept')}),
                          filter_box_posts=dict(xy=[[p[0], s_ * p[1]] for p in POSTS for s_ in (1, -1)], size=[[p[2], p[3]] for p in POSTS for s_ in (1, -1)], top_z=Z_CH),
                          growth_mm=dict(turbine_pads=growth['axial_growth_at_turbine_pads_mm'], exhaust_lugs=growth['axial_growth_at_exhaust_lugs_mm'])),
            mounts=dict(n=4, xy=MOUNTS, load_N=growth['load_per_mount_N']),
            lifting=dict(n=4, hole_d=25, front=[[X0 + 20, Y_XF + 5], [X0 + 20, -Y_XF - 5]], rear=[[X1 - 20, Y_XR + 5], [X1 - 20, -Y_XR - 5]], z=Z_T + 14))
rows = export(parts, 'FRAME', meta)

KEEP = dict(note='for the auxiliaries agent (gas train, oil + glycol units, junction box): do not place parts in these zones',
            filter_box=FB['envelope'], filter_service=FB['service_space'], pod_services=INT['interfaces']['pod_services_keep_out'],
            exhaust_jet=EXH['interfaces']['outlet']['keep_out'],
            filter_posts=[dict(x=[p[0] - 12.5, p[0] + 12.5], y=[s_ * p[1] - 25, s_ * p[1] + 25], z=[Z_T, Z_CH]) for p in POSTS for s_ in (1, -1)],
            frame_change_rev3=dict(front_cross_member_x=[X0, X0 + 40], rear_cross_member_x=[X1 - 40, X1], rails_x=[X0 + 40, X1 - 40],
                                   note='rev 2 had x -160..-120 / 300..340: the AUX skid brackets must move to these cross members'),
            pod_cradle=dict(x=[X_POD - 30, X_POD + 30], y=[-62, 62], z=[Z_T, -18]),
            engine_pedestals=dict(front=dict(x=[X_FOOT - 6, X_FOOT + 50], y=[-45, 45], z=[Z_T, -80]),
                                  turbine=dict(x=[112, 158], y=['+/-70..110'], z=[Z_T, -10]),
                                  exhaust=dict(x=[X_LC - 23, X_LC + 23], y=['+/-70..110'], z=[Z_T, -5])),
            free_frame_zones='rails y +/-(70..110) between x -185..110 except the posts listed; mid member x -20..20 under FR-120')
allj = dict(title='GR180 D2 intake / exhaust / frame interfaces (rev 3)', coords='ENG mm (ROOF X = 1.880 + x/1000, Y = 7.850 + y/1000, Z = 0.600 + z/1000)',
            calc='sim/variant_d/d2_intake_exhaust_calc.json', superseded=SUPERSEDED, keep_out=KEEP,
            intake=INT['interfaces'], exhaust=EXH['interfaces'], exhaust_dp=EXH['dp'], base_frame=meta)
json.dump(allj, open(os.path.join(OUT, 'd2_interfaces.json'), 'w'), indent=1)
print('footprint x %.0f..%.0f, y +/-%.0f, floor z %.0f, axis %.0f above floor' % (X0, X1, Y_XF + 10, meta['heights']['floor_z'],
                                                                              meta['heights']['axis_above_floor']))
