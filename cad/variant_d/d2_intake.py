# GR180 version D2 - INTAKE rev 2 (user feedback 2026-10-23): compact CLOSED plenum, OD 180, round the radial inlet gap
# between the generator pod rear and the v13A intake bell, with ONE side port on +y: a DN150 spigot (168.3 x 2) 150 mm
# long from the can, ending in a PN6 DN150-drilled flange (D265 K225 8 x M16) where the user mounts his own filter.
# The port opens into the can through a stadium window 112 x 170 (the housing is only ~120 mm long between the pod
# glycol port / terminal box and the core front), via a sheet-metal round-to-stadium transition.
# Air path: filter -> FOD guard disc in the spigot -> window -> plenum round the pod tail -> radial gap (3 struts, never 4)
# -> round the v13A intake lip into the compressor eye.  Rev 1 tube sheet / GT cartridges / yoke / gap guard are dropped.
# The D-150 concept struts are replaced by INT-115 (same axes, end blocks with radial M6 screws through the skirt).
# Sheet metal 1.4301 spun / rolled / laser-cut + TIG.  Pod internals, quill and bearings are not designed here
# (nothing clamps the pod: the front wall only carries an EPDM lip seal on the pod shell, x -130, bearing at x -136).
# ENG frame mm.  Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_intake.py -> cad_out/variant_d/D2/INTAKE/*.step
import sys, os, math, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

X_DISH = -46.3          # dish wetted face = v13A intake front flange face (Intake.step flange x -46.3..-41.8, OD 94)
R_LIP = 47.5            # dish inner edge (v13A intake flange OD 47.0 + 0.5)
R_W = 88.0; T = 2.0     # can wetted radius / wall -> OD 180
X_FW = -130.0           # front wall front face (behind the pod glycol port x -152 and terminal box x -168)
X_RR = (-8.4, -2.4)     # rear ring (clamp on the casing / IntakeOuter lap joint)
X_P = -71.0             # port centre x
HX_I, HZ_I = 56.0, 85.0 # stadium window half sizes (inner)
Y_ST = 15.0             # stadium plane (inside the can)
Y_RT = 190.0            # round section start
R_PI, R_PO = 82.15, 84.15   # DN150 tube 168.3 x 2
Y_FL = (232.0, 240.0)   # flange (8 mm, PN6 DN150 drilling)
SH = struts(0.75)

for f in glob.glob(os.path.join(OUT, 'INTAKE', '*.step')):      # obsolete rev-1 parts must not stay in the assembly
    os.remove(f)


def stadium_pts(hx, hz, y, n=72):
    """points of a stadium (rounded slot, radius hx) in the plane y, centre (X_P, z 0), ray-sampled for lofting."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        lo, hi = 0.0, 400.0
        for _ in range(60):
            t = (lo + hi) / 2
            px, pz = t * c, t * s
            zc = max(abs(pz) - (hz - hx), 0.0)
            (lo, hi) = (t, hi) if math.hypot(px, zc) <= hx else (lo, t)
        pts.append(V(X_P + lo * c, y, lo * s))
    return pts + [pts[0]]


def circle_pts(r, y, n=72):
    p = [V(X_P + r * math.cos(2 * math.pi * i / n), y, r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return p + [p[0]]


def hood(hx, hz, r, y_end):
    lo = Part.makeLoft([Part.makePolygon(stadium_pts(hx, hz, Y_ST)), Part.makePolygon(circle_pts(r, Y_RT))], True, True)
    return lo.fuse(Part.makeCylinder(r, y_end - Y_RT, V(X_P, Y_RT, 0), V(0, 1, 0)))


parts = {}
# ---------------------------------------------------------------- INT-110 plenum can + side port weldment
can = cyl(X_FW + 2, X_RR[0], R_W + T, R_W)                                      # rolled 2 mm can, OD 180
can = can.fuse(cyl(X_FW, X_FW + 2, R_W + T, 56.0))                              # front wall (EPDM lip seal on the pod)
can = can.fuse(cyl(X_RR[0] - 6, X_RR[0], R_W, 80.0))                            # inner bolting ring 6 x M5 to the rear ring
h_out = hood(HX_I + T, HZ_I + T, R_PO, Y_FL[0])
h_in = hood(HX_I, HZ_I, R_PI, Y_FL[1] + 5)
shell = h_out.cut(h_in).cut(cyl(X_FW - 5, X_RR[0] + 5, R_W + 1.0))
fl = Part.makeCylinder(132.5, Y_FL[1] - Y_FL[0], V(X_P, Y_FL[0], 0), V(0, 1, 0)).cut(
    Part.makeCylinder(R_PO + 0.3, 20, V(X_P, Y_FL[0] - 5, 0), V(0, 1, 0)))
for k in range(8):
    th = math.radians(22.5 + 45 * k)
    fl = fl.cut(Part.makeCylinder(9.0, 20, V(X_P + 112.5 * math.cos(th), Y_FL[0] - 5, 112.5 * math.sin(th)), V(0, 1, 0)))
for (x, a) in ((-30.0, 168.0), (-30.0, 275.0), (-32.0, 115.0), (-110.0, 225.0)):  # 3 line bulkheads + plenum P-tap
    can = can.fuse(radial_boss(x, a, R_W + 1, R_W + 12, 16.0 if x > -100 else 12.0))
can = can.fuse(shell).fuse(fl).cut(h_in)
for (x, a, d) in ((-30.0, 168.0, 9.0), (-30.0, 275.0, 9.0), (-32.0, 115.0, 9.0), (-110.0, 225.0, 4.0)):
    can = can.cut(radial_boss(x, a, R_W - 5, R_W + 20, d))
for h in bolt_holes(X_RR[0] - 6, 6.0, 84.0, 6, 5.5, 0.0):
    can = can.cut(h)
parts['INT-110_Plenum_Can_SidePort'] = (can.removeSplitter(), '1.4301',
    'rolled 2 mm 1.4301 can OD180 x 122 + 2 mm front wall (ID 112, EPDM lip seal on the pod) + inner bolt ring; side port +y: '
    'round 168.3x2 -> stadium 112x170 transition (2 pressed halves, TIG) + 150 mm spigot + 8 mm flange PN6 DN150 drilling; '
    '3 bulkhead bosses (2 fuel lines, RPM cable), P-tap')

# ---------------------------------------------------------------- INT-111 dish + skirt weldment
prof = [(X_DISH, R_LIP), (X_DISH, 62.0)] + arc(X_DISH + 6.0, 62.0, 6.0, 180, 90)[1:] + [(X_DISH + 8.3, 68.0)]
dish = thick_revolve(prof, 2.0, side=-1)
sk = cyl(X_DISH + 2.0, -11.4, 62.0, 60.0).fuse(cyl(-11.4, X_RR[0], 70.0, 54.0))
for (x, a) in ((-30.0, 168.0), (-30.0, 275.0), (-32.0, 115.0)):                 # line bulkheads (lines go on to the can)
    sk = sk.fuse(radial_boss(x, a, 61.0, 72.0, 16.0))
for k in range(3):                                                              # strut-end screw bosses M6
    sk = sk.fuse(radial_boss(-23.0, 90 + 120 * k, 61.0, 68.0, 12.0))
dsk = dish.fuse(sk)
for (x, a) in ((-30.0, 168.0), (-30.0, 275.0), (-32.0, 115.0)):
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
rr = rr.fuse(Part.makeBox(X_RR[1] - X_RR[0], 30, 16, V(X_RR[0], -15, 88)))                      # top ear (split at y = 0)
foot = Part.makeBox(X_RR[1] - X_RR[0], 80, 34, V(X_RR[0], -40, -114))
rr = rr.fuse(foot)
rr = rr.cut(Part.makeCylinder(3.3, 40, V((X_RR[0] + X_RR[1]) / 2, -20, 97), V(0, 1, 0)))                 # M6 ear bolt (along y)
for sgn in (1, -1):
    rr = rr.cut(Part.makeCylinder(5.5, 20, V(X_RR[0] - 5, sgn * 25, -102), V(1, 0, 0)))                # 2 x M10 to FR-120 (one per half)
rr = rr.cut(h_out)                                                                                        # clear the port transition
for h in bolt_holes(X_RR[0], X_RR[1] - X_RR[0], 63.0, 6, 5.0, 0.0) + bolt_holes(X_RR[0], X_RR[1] - X_RR[0], 84.0, 6, 5.0, 0.0):
    rr = rr.cut(h)
parts['INT-112_Rear_Ring_2halves_Foot'] = (rr.removeSplitter(), '1.4301',
    'laser-cut 6 mm 1.4301, 2 halves split at y 0 (top ear M6, the 2 foot halves bolt to FR-120), bore 107.7 on the casing / IntakeOuter lap joint (0.5 mm graphite tape), '
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

# ---------------------------------------------------------------- INT-140 FOD guard disc in the port spigot
gd = Part.makeCylinder(R_PI - 0.2, 2.0, V(X_P, 200.0, 0), V(0, 1, 0))
parts['INT-140_Port_FOD_Guard'] = (gd, 'mesh',
    'woven 1.4301 mesh 8 mm opening / 1.0 mm wire (f 0.79) on a 3 x 8 rolled ring, tack-welded in the spigot at y 200')

meta = dict(subsystem='INTAKE', rev=2, frame='ENG mm', calc='sim/variant_d/d2_intake_exhaust_calc.json',
            interfaces=dict(
                filter_port=dict(dir='+y', centre=[X_P, Y_FL[1], 0.0], tube='168.3 x 2 (DN150)', spigot_length_from_can=Y_FL[1] - (R_W + T),
                                 flange='8 mm, PN6 DN150 drilling: D265, K225, 8 x d18 (M16), holes off the vertical (22.5 deg)',
                                 note='bolt the user filter (or a DN150 rubber hump hose + clamps on an adapter) here'),
                housing=dict(OD=2 * (R_W + T), x=[X_FW, X_RR[1]], length=X_RR[1] - X_FW),
                core_clamp=dict(x=list(X_RR), bore=107.7, on='v13A Casing over IntakeOuter (lap joint x -11..-5)'),
                front_support=dict(foot_x=list(X_RR), face_x=X_RR[1], bolts='2 x M10 along x at y +/-25, z -102', fixed=True),
                pod_seal=dict(x=[X_FW, X_FW + 2], on='pod shell r 55, EPDM lip', note='no clamp on the pod'),
                struts=dict(part='INT-115 (replaces D-150)', root='pod rear plate x -108', screw='M6 radial at x -23 through the skirt boss'),
                bulkheads=dict(fuel_168deg=[-30, 168], line_275deg=[-30, 275], rpm_cable_115deg=[-32, 115], p_tap=[-110, 225])))
rows = export(parts, 'INTAKE', meta)
