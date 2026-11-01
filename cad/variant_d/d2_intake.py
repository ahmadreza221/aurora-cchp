# GR180 version D2 - INTAKE rev 3 (user feedback 2026-10-23): compact CLOSED plenum, OD 180, round the radial inlet gap
# between the generator pod rear and the v13A intake bell, fed from the TOP by a minimal filter box holding an F7 V-cell
# 592 x 592 x 292 (header up, face up): coarse inlet grille in a lift-off lid with 4 toggle latches -> V-cell (header on an
# EPDM seat, 4 corner guide rails) -> 70 mm clean chamber -> FOD guard panel -> 45 deg tapered collar 188 x 246 ->
# 112 x 170 top opening of the plenum -> round the pod tail -> radial gap (3 struts, never 4) -> intake lip -> eye.
# Orientation TOP (not +y): no extra floor area (the box sits over the cool generator pod inside the package width), a
# 592 mm square cannot hang beside a 239 mm high axis, gravity + dirty-side pressure seat the header, the cell lifts out
# straight up.  Box kept forward (inner x -490..110) so it is not over the hot turbine (housing from x 118).
# The box is carried by 4 posts on the frame (FR-160, d2_frame.py), NOT by the plenum: the collar flange only seals.
# The D-150 concept struts are replaced by INT-115 (same axes, end blocks with radial M6 screws through the skirt).
# Sheet metal: plenum / collar 1.4301 TIG; box + lid aluminium 5754 1.5 mm folded, riveted + sealed.  Pod internals,
# quill and bearings are not designed here (nothing clamps the pod; the front wall only has an EPDM lip seal at x -130).
# ENG frame mm.  Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_intake.py -> cad_out/variant_d/D2/INTAKE/*.step
import sys, os, math, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

X_DISH = -46.3          # dish wetted face = v13A intake front flange face (Intake.step flange x -46.3..-41.8, OD 94)
R_LIP = 47.5            # dish inner edge (v13A intake flange OD 47.0 + 0.5)
R_W = 88.0; T = 2.0     # can wetted radius / wall -> OD 180
X_FW = -130.0           # front wall front face (behind the pod glycol port x -152 and terminal box x -160)
X_RR = (-8.4, -2.4)     # rear ring (clamp on the casing / IntakeOuter lap joint)
X_P = -71.0             # top opening centre x
HX, HY = 56.0, 85.0     # top opening half sizes (inner) 112 x 170
Z_C = 90.0              # straight collar top = frustum start
Z_FL = (128.0, 130.0)   # collar flange (box floor sits on it at z 130)
HXF, HYF = HX + (Z_FL[0] - Z_C), HY + (Z_FL[0] - Z_C)     # 45 deg frustum -> 94 x 123 half sizes at z 128 (188 x 246)
FLH = (118.0, 147.0)    # flange outer half sizes (236 x 294)
X_B = -190.0            # filter box centre x (inner 600 x 600: x -490..110)
BI, TB = 300.0, 1.5     # box inner half size, alu wall
Z_FLOOR = 130.0
Z_SEAT = 464.0          # seat ledge top (3 mm EPDM gasket -> header bottom 467)
Z_HDR = (467.0, 492.0)  # V-cell header (25 mm)
Z_BODY0 = 200.0         # V-cell body bottom (292 - 25 = 267 below the header)
Z_RIM = 497.0           # box wall rim (lid seats here)
Z_LID = 527.0           # lid / grille top
CH_X = ((-220.0, -190.0), (85.0, 110.0))  # floor channels (post seats), clear of the collar flange x -189..47
BULK = ((-30.0, 185.0), (-30.0, 275.0), (-30.0, 300.0))   # line bulkheads: 2 fuel lines, RPM cable (below the collar)
SH = struts(0.75)

for f in glob.glob(os.path.join(OUT, 'INTAKE', '*.step')):      # obsolete parts must not stay in the assembly
    os.remove(f)


def rect_pts(cx, cy, hx, hy, z):
    return [V(cx - hx, cy - hy, z), V(cx + hx, cy - hy, z), V(cx + hx, cy + hy, z), V(cx - hx, cy + hy, z), V(cx - hx, cy - hy, z)]


def frustum(hx0, hy0, z0, hx1, hy1, z1, cx=X_P):
    return Part.makeLoft([Part.makePolygon(rect_pts(cx, 0, hx0, hy0, z0)), Part.makePolygon(rect_pts(cx, 0, hx1, hy1, z1))], True, True)


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def sq_ring(cx, h_out, h_in, z0, z1):        # square tube / frame centred on (cx, 0)
    return box(cx - h_out, cx + h_out, -h_out, h_out, z0, z1).cut(box(cx - h_in, cx + h_in, -h_in, h_in, z0 - 1, z1 + 1))


parts = {}
# ---------------------------------------------------------------- INT-110 plenum can + top collar weldment
can = cyl(X_FW + 2, X_RR[0], R_W + T, R_W)                                      # rolled 2 mm can, OD 180
can = can.fuse(cyl(X_FW, X_FW + 2, R_W + T, 56.0))                              # front wall (EPDM lip seal on the pod)
can = can.fuse(cyl(X_RR[0] - 6, X_RR[0], R_W, 80.0))                            # inner bolting ring 6 x M5 to the rear ring
c_out = box(X_P - HX - T, X_P + HX + T, -HY - T, HY + T, 15.0, Z_C + 0.5).fuse(
    frustum(HX + T - 1.2, HY + T - 1.2, Z_C - 2.0, HXF + 2.8, HYF + 2.8, Z_FL[0]))
c_in = box(X_P - HX, X_P + HX, -HY, HY, 10.0, Z_C + 0.01).fuse(frustum(HX, HY, Z_C, HXF, HYF, Z_FL[0] + 0.01)).fuse(
    box(X_P - HXF, X_P + HXF, -HYF, HYF, Z_FL[0], Z_FL[1] + 5))
collar = c_out.cut(c_in).cut(cyl(X_FW - 5, X_RR[0] + 5, R_W + 1.0))
fl = box(X_P - FLH[0], X_P + FLH[0], -FLH[1], FLH[1], Z_FL[0], Z_FL[1])
FL_HOLES = [(X_P + sx * 108.0, sy * 137.0) for sx in (-1, 0, 1) for sy in (-1, 1)] + [(X_P - 108.0, 0.0), (X_P + 108.0, 0.0)]
for (hx, hy) in FL_HOLES:
    fl = fl.cut(Part.makeCylinder(3.3, 10, V(hx, hy, Z_FL[0] - 5), V(0, 0, 1)))
for (x, a) in BULK + ((-110.0, 225.0),):                                       # 3 line bulkheads + plenum P-tap
    can = can.fuse(radial_boss(x, a, R_W + 1, R_W + 12, 16.0 if x > -100 else 12.0))
can = can.fuse(collar).fuse(fl).cut(c_in)
for (x, a, d) in tuple((x, a, 9.0) for (x, a) in BULK) + ((-110.0, 225.0, 4.0),):
    can = can.cut(radial_boss(x, a, R_W - 5, R_W + 20, d))
for h in bolt_holes(X_RR[0] - 6, 6.0, 84.0, 6, 5.5, 0.0):
    can = can.cut(h)
parts['INT-110_Plenum_Can_TopCollar'] = (can.removeSplitter(), '1.4301',
    'rolled 2 mm 1.4301 can OD180 x 122 + 2 mm front wall (ID 112, EPDM lip seal on the pod) + inner bolt ring; top opening '
    '112 x 170 with a straight collar + 45 deg frustum to 188 x 246 (4 folded plates, TIG) + 2 mm flange 236 x 294 (8 x M6 to the '
    'box floor, EPDM gasket); 3 bulkhead bosses (2 fuel lines, RPM cable), P-tap')

# ---------------------------------------------------------------- INT-111 dish + skirt weldment
prof = [(X_DISH, R_LIP), (X_DISH, 62.0)] + arc(X_DISH + 6.0, 62.0, 6.0, 180, 90)[1:] + [(X_DISH + 8.3, 68.0)]
dish = thick_revolve(prof, 2.0, side=-1)
sk = cyl(X_DISH + 2.0, -11.4, 62.0, 60.0).fuse(cyl(-11.4, X_RR[0], 70.0, 54.0))
for (x, a) in BULK:                                                             # line bulkheads (lines go on to the can)
    sk = sk.fuse(radial_boss(x, a, 61.0, 72.0, 16.0))
for k in range(3):                                                              # strut-end screw bosses M6
    sk = sk.fuse(radial_boss(-23.0, 90 + 120 * k, 61.0, 68.0, 12.0))
dsk = dish.fuse(sk)
for (x, a) in BULK:
    dsk = dsk.cut(radial_boss(x, a, 50.0, 80.0, 9.0))
for k in range(3):
    dsk = dsk.cut(radial_boss(-23.0, 90 + 120 * k, 58.0, 70.0, 6.4))
for h in bolt_holes(-11.4, 3.0, 63.0, 6, 5.5, 0.0):
    dsk = dsk.cut(h)
for s in SH:
    dsk = dsk.cut(s)
parts['INT-111_Dish_Skirt'] = (dsk.removeSplitter(), '1.4301',
    'spun 2 mm dish r47.5..68 flush with the intake flange (x -46.3) with a rolled R6 rim lip; rolled 2 mm skirt D124 + 3 mm ring; '
    '3 strut holes d9.5, 3 strut-screw bosses (M6 at x -23), 3 bulkhead bosses; TIG')

# ---------------------------------------------------------------- INT-112 rear ring (2 halves): clamp + front support foot
rr = cyl(X_RR[0], X_RR[1], R_W + T, 53.85)
for sgn in (1, -1):                                                                                       # side ears (split at z = 0)
    rr = rr.fuse(Part.makeBox(X_RR[1] - X_RR[0], 16, 14, V(X_RR[0], 88 if sgn > 0 else -104, -7)))
foot = Part.makeBox(X_RR[1] - X_RR[0], 80, 34, V(X_RR[0], -40, -114))
rr = rr.fuse(foot)
for sgn in (1, -1):
    rr = rr.cut(Part.makeCylinder(3.3, 30, V((X_RR[0] + X_RR[1]) / 2, sgn * 96, -15), V(0, 0, 1)))       # M6 ear bolts
for sgn in (1, -1):
    rr = rr.cut(Part.makeCylinder(5.5, 20, V(X_RR[0] - 5, sgn * 25, -102), V(1, 0, 0)))                # 2 x M10 to FR-120 (one per half)
for h in bolt_holes(X_RR[0], X_RR[1] - X_RR[0], 63.0, 6, 5.0, 0.0) + bolt_holes(X_RR[0], X_RR[1] - X_RR[0], 84.0, 6, 5.0, 0.0):
    rr = rr.cut(h)
parts['INT-112_Rear_Ring_2halves_Foot'] = (rr.removeSplitter(), '1.4301',
    'laser-cut 6 mm 1.4301, 2 halves split at z 0 (2 side ears M6; the lower half carries the foot), bore 107.7 on the casing / IntakeOuter lap joint (0.5 mm graphite tape), '
    '6 + 6 x M5 tapped for skirt and can; lower half with the 80 x 30 foot (2 x M10) = FIXED front support')

# ---------------------------------------------------------------- INT-115 pod struts x3 (replace D-150; radial M6 at the end)
st = []
for k in range(3):
    th = math.radians(90 + 120 * k)
    d = V(0, math.cos(th), math.sin(th))
    p0 = V(-116.0, 0, 0) + d * 51.0
    p1 = V(-12.0, 0, 0) + d * 53.0
    ax = p1 - p0
    at = lambda x: p0 + ax * ((x - p0.x) / ax.x)
    a0, a1 = at(-107.9), at(-18.0)
    rod = Part.makeCylinder(4.0, (a1 - a0).Length, a0, a1 - a0)
    blk = Part.makeBox(10, 12, 10.5, V(-28.0, -6, 49.0))                        # end block r 49..59.5 (built at +z, rotated)
    blk = blk.cut(Part.makeCylinder(2.5, 12, V(-23.0, 0, 50.0), V(0, 0, 1)))    # M6 tapped (core d5)
    blk.rotate(V(0, 0, 0), V(1, 0, 0), 120 * k)
    st.append(rod.fuse(blk))
parts['INT-115_Pod_Struts_x3'] = (Part.makeCompound(st), '1.4301',
    '3 x d8 17-4PH / 1.4301 rods on the D-150 axes (90/210/330 deg), welded/screwed to the pod rear plate at x -108, '
    'end blocks 10 x 12 x 10.5 with M6 tapped radially at x -23 (screw through the skirt boss)')

# ---------------------------------------------------------------- INT-120 pod tail fairing (3 segments)
fp = [(-126.0, 57.0), (-117.0, 61.0)] + arc(-117.0, 46.0, 15.0, 90, 0)[1:]
fair = thick_revolve(fp, 1.5, side=-1).fuse(cyl(-107.8, -103.0, 46.0, 44.5))
for s in SH:
    fair = fair.cut(s)
parts['INT-120_Pod_Tail_Fairing'] = (fair.removeSplitter(), '1.4301',
    'spun 1.5 mm quarter-torus R15 + foot ring, cut into 3 segments at the struts, 3 x M4 into the pod rear face')

# ---------------------------------------------------------------- INT-140 FOD guard panel on the box floor
gd = box(X_P - HXF - 10, X_P + HXF + 10, -HYF - 10, HYF + 10, Z_FLOOR + TB, Z_FLOOR + TB + 2.0)
parts['INT-140_FOD_Guard_Panel'] = (gd, 'mesh',
    'woven 1.4301 mesh 8 mm opening / 1.0 mm wire (f 0.79) on a 3 x 15 flat frame 208 x 266, 6 x M5 into the box floor over '
    'the collar opening - catches anything dropped while the cell is out')

# ---------------------------------------------------------------- INT-150 filter box body (alu)
walls = sq_ring(X_B, BI + TB, BI, Z_FLOOR + TB, Z_RIM)
floor = box(X_B - BI - TB, X_B + BI + TB, -BI - TB, BI + TB, Z_FLOOR, Z_FLOOR + TB)
floor = floor.cut(box(X_P - HXF, X_P + HXF, -HYF, HYF, Z_FLOOR - 1, Z_FLOOR + 5))
for (hx, hy) in FL_HOLES:
    floor = floor.cut(Part.makeCylinder(3.3, 10, V(hx, hy, Z_FLOOR - 5), V(0, 0, 1)))
bx = walls.fuse(floor)
seat = sq_ring(X_B, BI, 287.0, Z_SEAT - 3.0, Z_SEAT).fuse(sq_ring(X_B, BI, BI - 3.0, Z_SEAT - 23.0, Z_SEAT))   # angle frame
bx = bx.fuse(seat)
for sx in (-1, 1):                                                              # 4 corner guide rails (L 12 x 12 x 2)
    for sy in (-1, 1):
        cx, cy = X_B + sx * 293.0, sy * 293.0
        g1 = box(cx - 6, cx + 6, cy - 1, cy + 1, Z_BODY0 + 10, Z_SEAT - 23).fuse(box(cx - 1, cx + 1, cy - 6, cy + 6, Z_BODY0 + 10, Z_SEAT - 23))
        bx = bx.fuse(g1)
for (x0, x1) in CH_X:                                                           # 2 floor channels (post seats, M8 rivnuts)
    ch = box(x0, x1, -BI - TB, BI + TB, Z_FLOOR - 25.0, Z_FLOOR).cut(box(x0 + 2, x1 - 2, -BI - 5, BI + 5, Z_FLOOR - 23.0, Z_FLOOR - 2))
    bx = bx.fuse(ch)
X_DR, Y_DR = X_B - 270.0, -270.0                                                # drain boss at the front-left floor corner
bx = bx.fuse(Part.makeCylinder(10.0, 12.0, V(X_DR, Y_DR, Z_FLOOR - 12.0), V(0, 0, 1)))
bx = bx.cut(Part.makeCylinder(4.0, 30.0, V(X_DR, Y_DR, Z_FLOOR - 20.0), V(0, 0, 1)))
parts['INT-150_Filter_Box'] = (bx.removeSplitter(), 'alu',
    'aluminium 5754 1.5 mm folded box 603 x 603 x 367 (inner 600 x 600), riveted + sealed (MS polymer); floor with the collar '
    'opening 188 x 246 + 8 x M6; angle seat 13 mm wide at z 464 (EPDM 10 x 3 gasket); 4 corner guide rails; 2 floor channels '
    '30 x 25 with M8 rivnuts for the FR-160 posts; G1/4 drain boss at the floor corner')

# ---------------------------------------------------------------- INT-151 lid with inlet grille
LO, LI = BI + TB + 2.0, BI + TB + 0.5                                          # lid skirt 0.5 mm outside the box wall
lid = sq_ring(X_B, LO, LI, Z_RIM - 12.0, Z_LID)
lid = lid.fuse(sq_ring(X_B, LI, 290.0, Z_RIM, Z_RIM + TB))                      # rim plate on the box rim (gasket)
lid = lid.fuse(sq_ring(X_B, LO, 280.0, Z_LID - TB, Z_LID))                      # top frame
lid = lid.fuse(sq_ring(X_B, 289.0, 287.5, Z_HDR[1] + 2.0, Z_LID - TB))          # pressing lip (10 mm foam on the header)
lid = lid.fuse(box(X_B - 287.5, X_B + 287.5, -287.5, 287.5, Z_LID - 3.0, Z_LID - TB))   # expanded-metal grille
parts['INT-151_Lid_Grille'] = (lid.removeSplitter(), 'alu',
    'aluminium 1.5 mm lid 607 x 607 x 42 with a coarse expanded-metal grille (alu 10 x 5 mesh, ~70 % open), skirt over the box rim, '
    'EPDM rim gasket, inner pressing lip with 10 mm foam on the cell header; lifted off after opening the 4 latches')

# ---------------------------------------------------------------- INT-152 V-cell (buy) envelope
cell = box(X_B - 296.0, X_B + 296.0, -296.0, 296.0, Z_HDR[0], Z_HDR[1]).fuse(box(X_B - 285.0, X_B + 285.0, -285.0, 285.0, Z_BODY0, Z_HDR[0]))
parts['INT-152_V-Cell_F7_592x592x292_env'] = (cell, 'vcell',
    'BUY: F7 (ISO ePM1 50-65 %) V-cell with header 592 x 592 x 292, 4 V-banks, plastic frame; ~3400 m3/h at ~90 Pa; '
    'body <= 570 x 570 below the 25 mm header (verify the model)')

# ---------------------------------------------------------------- INT-153 toggle latches x4 (buy)
lat = []
for (dx, dy) in ((0, 1), (0, -1), (1, 0), (-1, 0)):
    cx, cy = X_B + dx * (BI + TB), dy * (BI + TB)
    if dx == 0:
        lat.append(box(cx - 20, cx + 20, cy if dy > 0 else cy - 18, cy + 18 if dy > 0 else cy, Z_RIM - 45, Z_RIM - 13))
    else:
        lat.append(box(cx if dx > 0 else cx - 18, cx + 18 if dx > 0 else cx, -20, 20, Z_RIM - 45, Z_RIM - 13))
parts['INT-153_Toggle_Latches_x4_env'] = (Part.makeCompound(lat), '1.4301',
    'BUY: 4 x stainless over-centre toggle latches ~500 N (Elesa+Ganter GN 831 (DE/IT) / Kipp (DE)), '
    'riveted on the box walls, hooks on the lid skirt; no tools')

TOP = Z_LID
meta = dict(subsystem='INTAKE', rev=3, frame='ENG mm', calc='sim/variant_d/d2_intake_exhaust_calc.json',
            interfaces=dict(
                filter_box=dict(orientation='TOP (+z), cell face up, header up', cell='F7 V-cell 592 x 592 x 292 (header 25)',
                                envelope=dict(x=[X_B - BI - TB - 2.0, X_B + BI + TB + 2.0], y=[-(BI + TB + 20.0), BI + TB + 20.0],
                                              z=[Z_FLOOR - 25.0, TOP], note='incl. latches (y/x +18), floor channels from z 105'),
                                service_space=dict(x=[X_B - BI - 100.0, X_B + BI + 100.0], y=[-(BI + 100.0), BI + 100.0],
                                                   z=[TOP, TOP + 360.0], note='keep free: lid off + cell lifted straight up (292 + hands); '
                                                   'plus 100 mm all round at z 440..530 for the latches'),
                                change='open 4 toggle latches, lift the lid, lift the cell out by its header, drop the new one into the '
                                       'corner rails onto the EPDM seat, lid on, latches closed (no tools)',
                                drain=dict(xy=[X_DR, Y_DR], z=Z_FLOOR - 12.0, size='G1/4, tube to the package drain'),
                                supports='4 posts FR-160 under the floor channels x %s, see d2_frame' % str([list(c) for c in CH_X]),
                                collar_joint=dict(z=Z_FL[1], flange='236 x 294, 8 x M6, EPDM gasket (sealing only, no load)')),
                pod_services_keep_out=dict(x=[-300.0, -130.0], y=[-90.0, 90.0], z=[55.0, Z_FLOOR - 25.0],
                                           note='terminal box (top z 85), glycol fittings (z 67), cables + hoses run here under the box floor'),
                housing=dict(OD=2 * (R_W + T), x=[X_FW, X_RR[1]], length=X_RR[1] - X_FW, top_opening=[2 * HX, 2 * HY]),
                core_clamp=dict(x=list(X_RR), bore=107.7, on='v13A Casing over IntakeOuter (lap joint x -11..-5)'),
                front_support=dict(foot_x=list(X_RR), face_x=X_RR[1], bolts='2 x M10 along x at y +/-25, z -102', fixed=True),
                pod_seal=dict(x=[X_FW, X_FW + 2], on='pod shell r 55, EPDM lip', note='no clamp on the pod'),
                struts=dict(part='INT-115 (replaces D-150)', root='pod rear plate x -108', screw='M6 radial at x -23 through the skirt boss',
                            role='the ONLY locator of the pod (the FR-170 cradle is a soft weight relief)'),
                bulkheads=dict(fuel_185deg=list(BULK[0]), line_275deg=list(BULK[1]), rpm_cable_300deg=list(BULK[2]), p_tap=[-110, 225])))
rows = export(parts, 'INTAKE', meta)
