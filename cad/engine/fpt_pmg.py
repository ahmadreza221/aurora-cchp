# GR180-CCHP subsystem E3 - interduct + FPT + FPT/PMG rotor, bearings, housings + 30 kW PMG + exhaust collector.
# Scripted parametric FreeCAD model (Part workbench), ENG frame (mm): x downstream (east), y north, z up; x = 0 tunnel front.
# Geometry comes from the design calculation (single source of truth):
#     uv run sim/engine/e3_fpt_pmg_calc.py      -> cad_out/engine/E3/E3_calc_results.json
# Run:
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/engine/fpt_pmg.py
# Outputs (cad_out/engine/E3/): E3-xxx_<name>.step per part, E3_assembly.step (ENG), E3_assembly_ROOF.step (ROOF, mm),
#     E3_assembly.FCStd, E3_interfaces.json, E3_massprops.json (rotor mass properties -> re-run the calc for J/rotordynamics),
#     E3_section.png (z = 0 section with the GG turbine/nut/NGV/shaft), E3_checks.json (interference report),
#     docs/bom/engine_E3_bom.csv (BOM with CAD masses).
# ROOF placement: X = 1.880 + x/1000, Y = 7.850 + y/1000, Z = 0.600 + z/1000 (m)  (docs/06 sec.1; engine moved 0.200 m east 2026-10-23
# so that the E4 core clears the H1 spool).
import FreeCAD as App, Part, os, json, math, sys, csv
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles', False)
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'sim', 'gg_turbine_design.json')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'E3'); os.makedirs(OUT, exist_ok=True)
GG_ASM = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
FAST = os.environ.get('E3_FAST', '0') == '1'
CR = json.load(open(os.path.join(OUT, 'E3_calc_results.json')))
G_ = CR['geometry']; X = G_['X']; GEO = G_['GEO']; L = G_['layout']; PM = G_['pmg']; PS = G_['pmg_slot']
B1, B2 = G_['BRG1'], G_['BRG2']; ROT = G_['ROT_FPT']; ZN, ZR = G_['Z_ngv'], G_['Z_rot']
ROOF0 = (1880.0, 7850.0, 600.0)                    # ENG origin in ROOF (mm)
def roof(p): return [round((ROOF0[0] + p[0]) / 1000, 4), round((ROOF0[1] + p[1]) / 1000, 4), round((ROOF0[2] + p[2]) / 1000, 4)]
log = []
def say(*a):
    s = ' '.join(str(v) for v in a); print(s); log.append(s); sys.stdout.flush()

# ---------------------------------------------------------------- helpers
def P(x, r, th_deg):                                   # polar point about the x axis; theta from +y toward +z
    t = math.radians(th_deg); return V(x, r * math.cos(t), r * math.sin(t))
def rdir(th_deg):
    t = math.radians(th_deg); return V(0, math.cos(t), math.sin(t))
def rv(pts):                                           # revolve a closed (x, r) polygon about x
    w = Part.makePolygon([V(x, r, 0) for x, r in pts] + [V(pts[0][0], pts[0][1], 0)])
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)
def ring(x0, x1, ri, ro):
    return Part.makeCylinder(ro, x1 - x0, V(x0, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(ri, x1 - x0, V(x0, 0, 0), V(1, 0, 0))) if ri > 0 \
        else Part.makeCylinder(ro, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
def radial_boss(x, th, r0, r1, rad, bore=0.0):
    b = Part.makeCylinder(rad, r1 - r0, P(x, r0, th), rdir(th))
    if bore > 0: b = b.cut(Part.makeCylinder(bore, r1 - r0 + 2, P(x, r0 - 1, th), rdir(th)))
    return b
def offset_curve(pts, d):
    """offset a polyline (x, r) by d along its left normal (for wall thickness)"""
    out = []
    for i, (x, r) in enumerate(pts):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        tx, tr = b[0] - a[0], b[1] - a[1]; n = math.hypot(tx, tr); out.append((x - tr / n * d, r + tx / n * d))
    return out
def arc(cx, cr, R, a0, a1, n=24):
    return [(cx + R * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cr + R * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
def frustum(x0, x1, r0, r1):                           # primitive cone / cylinder along +x (robust booleans with B-spline blades)
    if abs(r0 - r1) < 1e-6: return Part.makeCylinder(r0, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return Part.makeCone(r0, r1, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
def cone_tube(x0, x1, ri0, ri1, ro0, ro1):
    return frustum(x0, x1, ro0, ro1).cut(frustum(x0, x1, ri0, ri1))
def hexprism(x0, L_, af):
    R = af / math.sqrt(3)
    w = Part.makePolygon([V(x0, R * math.cos(math.radians(60 * k + 30)), R * math.sin(math.radians(60 * k + 30))) for k in range(7)])
    return Part.Face(w).extrude(V(L_, 0, 0))

# ---------------------------------------------------------------- blade geometry (wrapped quadratic-Bezier camber + NACA thickness)
def section_wire(sec, x_mid, th0_deg, rot, n=22, x_le=None):
    r = sec['r']; b = sec['b_ax']; ai, ao = math.radians(sec['ang_in']), math.radians(sec['ang_out'])
    u1 = 0.5 * b; s1 = u1 * math.tan(ai); s2 = s1 + (b - u1) * math.tan(ao)
    P0, P1_, P2 = (0.0, 0.0), (u1, s1), (b, s2)
    c = math.hypot(b, s2); tc, te = sec['tc'], sec['te']
    ts = [0.5 * (1 - math.cos(math.pi * k / n)) for k in range(n + 1)]
    up, lo = [], []
    for t in ts:
        bx = (1 - t) ** 2 * P0[0] + 2 * (1 - t) * t * P1_[0] + t * t * P2[0]
        by = (1 - t) ** 2 * P0[1] + 2 * (1 - t) * t * P1_[1] + t * t * P2[1]
        dx = 2 * (1 - t) * (P1_[0] - P0[0]) + 2 * t * (P2[0] - P1_[0]); dy = 2 * (1 - t) * (P1_[1] - P0[1]) + 2 * t * (P2[1] - P1_[1])
        nn = math.hypot(dx, dy); nx, ny = -dy / nn, dx / nn
        yt = 5 * tc * c * (0.2969 * math.sqrt(t) - 0.1260 * t - 0.3516 * t ** 2 + 0.2843 * t ** 3 - 0.1036 * t ** 4) + 0.5 * te * t
        up.append((bx + yt * nx, by + yt * ny)); lo.append((bx - yt * nx, by - yt * ny))
    loop = up[::-1] + lo[1:]                         # TE upper -> LE -> TE lower (open spline), TE closed by a line
    xl = x_mid - b / 2 if x_le is None else x_le
    pts = []
    for u, s in loop:
        th = math.radians(th0_deg) + rot * s / r
        pts.append(V(xl + u, r * math.cos(th), r * math.sin(th)))
    bs = Part.BSplineCurve(); bs.interpolate(pts)
    return Part.Wire([bs.toShape(), Part.LineSegment(pts[-1], pts[0]).toShape()])
def blade_row(secs, Z, x_mid, rot, trim, x_le=None, th_offset=0.0):
    out = []
    w0 = [section_wire(s, x_mid, 0.0, rot, x_le=x_le) for s in secs]
    sh = Part.makeLoft(w0, False, False)              # wrapped sections are not planar -> loft a shell, cap with filled faces
    caps = [Part.makeFilledFace(w0[0].Edges), Part.makeFilledFace(w0[-1].Edges)]
    shell = Part.Shell(sh.Faces + caps); shell.sewShape()
    lf = Part.Solid(shell)
    if lf.Volume < 0: lf.reverse()
    if not lf.isValid(): lf.fix(1e-5, 1e-5, 1e-5)
    tr = trim.copy(); tr.rotate(V(0, 0, 0), V(1, 0, 0), 180.0)   # keep the revolve seam away from the blade (boolean robustness)
    b0 = lf.common(tr)
    for k in range(Z):
        b = b0.copy(); b.rotate(V(0, 0, 0), V(1, 0, 0), th_offset + 360.0 * k / Z); out.append(b)
    return out

PARTS = {}            # tag -> dict(name, shape, material, rho [kg/mm3], group)
def add(tag, name, shp, mat, rho, group):
    PARTS[tag] = dict(name=name, shape=shp, mat=mat, rho=rho, group=group)
    say('  %-7s %-26s valid %-5s solids %2d  vol %10.0f mm3  mass %7.3f kg' % (tag, name, shp.isValid(), len(shp.Solids), shp.Volume, shp.Volume * rho))
RHO = dict(IN718=8.19e-6, IN625=8.44e-6, S1_4828=7.80e-6, SS316L=7.98e-6, AlSi10Mg=2.67e-6, steel=7.85e-6, SmCo=8.40e-6,
           CFRP=1.58e-6, Ti64=4.43e-6, brg=7.2e-6, lam=7.65e-6, wind=5.2e-6, ins=0.30e-6, S17_4=7.80e-6, S1_4541=7.90e-6, misc=3.0e-6)

# =====================================================================================================================
say('E3 build: NGV %d / rotor %d, ROT_FPT %+d, rotor x %.1f..%.1f, B1 %.1f, B2 %.1f' % (ZN, ZR, ROT, L['stud0'], L['shaft1'], L['b1'], L['b2']))
# ---------------------------------------------------------------- E3-101 interduct + NGV module (SLM IN718)
hub = [tuple(p) for p in G_['interduct_hub']]; cas = [tuple(p) for p in G_['interduct_cas']]
x_le, x_te = X['ngv_le'], X['ngv_te']
ngv_cas = [(x_le + (x_te - x_le) * k / 6, GEO['ngv_tip_le'] + (GEO['ngv_tip_te'] - GEO['ngv_tip_le']) * k / 6) for k in range(7)]
cas_all = cas + ngv_cas[1:]
T_ID = 1.5
outer_wall = rv(cas_all + offset_curve(cas_all, T_ID)[::-1])                          # gas side = cas (r), material outside
hub_all = hub + [(x_te, GEO['ngv_hub_te'])]
inner_wall = rv(hub_all + [(p[0], p[1] - 1.2) for p in hub_all][::-1])               # stationary hub cone / bullet, 1.2 wall
# NGV inner-ring back wall (closes the hub cavity) at the NGV leading edge; rim-seal lip toward the blisk
back_wall = ring(x_le, x_le + 2.0, 0.0, GEO['ngv_hub_le'] - 1.0)
rim_lip = ring(x_te, x_te + 1.7, GEO['ngv_hub_te'] - 2.2, GEO['ngv_hub_te'] - 0.4)
# front slip bore over the GG NGV shroud (OD 72.7, x 110.8..118.8): ID 73.2 from the E2 mating face (x 116.0) to the interduct inlet (119.3).
# The slip-joint piston ring sits in the E2 rear ring (E2 seal groove x 112.5-114.5, r 40: sim/engine/e2_design.json) - no ring on the E3 side.
slip = ring(X['flangeE2'], X['id0'] + 0.01, 36.6, 38.1)
step = ring(X['id0'], X['id0'] + 1.5, 35.35, 38.1)
fr_x0 = X['flangeE2']
# E2/E3 flange adopted from E2 (sim/engine/e2_design.json 2026-10-21): E2 rear ring x 106-116, r_e3_flange_o 88, pcd_e3 160, n_e3_bolts 16 (M8),
# e3_spigot_d 120 x depth 3.  E3 ring: IN718, 8 thick (x 116-124), OD 176, 16 x d9 on PCD 160, male spigot OD 120 h7 x 3 (x 113-116).
FR = dict(OD=176.0, PCD=160.0, n=16, hole=9.0, t=8.0, phase=11.25)
front_flange = ring(fr_x0, fr_x0 + FR['t'], 36.6, 0.5 * FR['OD']).fuse(ring(fr_x0 - 3.0, fr_x0, 56.0, 60.0))
mid_x0 = X['drum0'] - 6.0
mid_flange = ring(mid_x0, mid_x0 + 6.0, 38.0, 72.0)
rear_flange = ring(x_te - 4.0, x_te, GEO['ngv_tip_te'] - 1.0, 66.0)
tc_boss = []
for th in (45.0, 225.0, 135.0):                     # TE-510A, TE-510B, PT-524 (P45 static tap)
    tc_boss.append(radial_boss(X['tc_in'], th, 36.8, 52.0, 6.0))
mod = outer_wall.fuse([inner_wall, back_wall, rim_lip, slip, step, front_flange, mid_flange, rear_flange] + tc_boss)
for k in range(FR['n']):                             # E2/E3 flange 16 x d9 (M8) on PCD 160 per E2; phase 11.25 deg (straddling the vertical) - confirm with E2
    mod = mod.cut(Part.makeCylinder(0.5 * FR['hole'], FR['t'] + 2.0, P(fr_x0 - 1, 0.5 * FR['PCD'], FR['phase'] + 360.0 / FR['n'] * k), V(1, 0, 0)))
for k in range(12):                                  # mid flange 12 x M6 PCD 132 (to west cover)
    th = 15 + 30 * k
    mod = mod.cut(Part.makeCylinder(2.5, 8, P(mid_x0 - 1, 66.0, th), V(1, 0, 0)))
for k in range(16):                                  # rear flange 16 x M5 PCD 120 (to the shroud ring)
    mod = mod.cut(Part.makeCylinder(2.1, 6, P(x_te - 5, 60.0, 11.25 + 22.5 * k), V(1, 0, 0)))
for th in (45.0, 225.0, 135.0):
    mod = mod.cut(Part.makeCylinder(1.6 if th != 135.0 else 0.8, 30, P(X['tc_in'], 30.0, th), rdir(th)))
# NGV vanes
_sl = (GEO['ngv_tip_te'] - GEO['ngv_tip_le']) / (x_te - x_le)
ann_n = cone_tube(x_le - 0.5, x_te + 0.5, GEO['ngv_hub_le'] - 0.4, GEO['ngv_hub_te'] - 0.4,
                  GEO['ngv_tip_le'] + 0.4 - 0.5 * _sl, GEO['ngv_tip_te'] + 0.4 + 0.5 * _sl)
vanes = blade_row(G_['ngv_sections'], ZN, None, ROT, ann_n, x_le=x_le)
mod = mod.fuse(vanes)
if not FAST: mod = mod.removeSplitter()
add('E3-101', 'Interduct_NGV_module', mod, 'IN718 SLM (iDesign3D), stress-relief + AMS 5662 HT, seats machined', RHO['IN718'], 'hot')

# ---------------------------------------------------------------- E3-102 FPT shroud ring + exhaust-diffuser west (shroud-side) wall
rt = lambda x: GEO['rot_tip_le'] + (GEO['rot_tip_te'] - GEO['rot_tip_le']) * (x - X['rot_le']) / (X['rot_te'] - X['rot_le'])
gap = GEO['tip_gap']; xb = X['rad_w'] - GEO['shroud_bend_R']                 # bend start (221)
gas_sh = [(x_te, GEO['ngv_tip_te']), (X['rot_le'], rt(X['rot_le']) + gap), (X['rot_te'], rt(X['rot_te']) + gap), (xb, rt(X['rot_te']) + gap)]
gas_sh += arc(xb, rt(X['rot_te']) + gap + GEO['shroud_bend_R'], GEO['shroud_bend_R'], -90, 0, 12)[1:]
gas_sh += [(X['rad_w'], GEO['rad_out'])]
T_SH = 3.0
shroud = rv(gas_sh + offset_curve(gas_sh, T_SH)[::-1])
shroud = shroud.fuse([ring(x_te, x_te + 4.0, GEO['ngv_tip_te'] + 2.0, 66.0),
                      ring(X['rad_w'] - T_SH - 3.0, X['rad_w'] - T_SH + 0.5, GEO['rad_out'] - 6.0, GEO['rad_out'])])   # front flange, rim stiffener
for k in range(16):
    shroud = shroud.cut(Part.makeCylinder(2.75, 6, P(x_te - 1, 60.0, 11.25 + 22.5 * k), V(1, 0, 0)))
shroud = shroud.removeSplitter()
add('E3-102', 'Shroud_DiffuserWestWall', shroud, 'IN718 machined shroud ring + IN625 spun radial wall, EB/TIG welded', RHO['IN718'], 'hot')

# ---------------------------------------------------------------- E3-110 collector body: hub bell + diffuser east wall + hub cylinder + drum + DN250 outlet
xh = X['rot_te'] + 2.2                                                           # 219.0 stationary hub start (rear rim seal 0.5 mm)
gas_hb = [(xh, GEO['rot_hub_te'])] + arc(xh, GEO['rot_hub_te'] + GEO['hub_bend_R'], GEO['hub_bend_R'], -90, 0, 18)[1:] + [(X['rad_e'], GEO['rad_out'])]
T_C = 2.5
bell = rv(gas_hb + offset_curve(gas_hb, -T_C)[::-1])
d0, d1, Rd = X['drum0'] + 6.0, X['drum1'], GEO['drum_ro']                        # drum shell x 151..299, r 212..215
hubcyl = ring(X['rad_e'] + T_C - 0.5, d1, GEO['drum_hub_r'] - T_C, GEO['drum_hub_r'])
eastw = ring(d1 - 3.0, d1, GEO['drum_hub_r'] - T_C, Rd)
shell = ring(d0, d1, Rd - 3.0, Rd)
wflange = ring(d0, d0 + 6.0, Rd - 3.0, Rd + 20.0)
for k in range(24):
    wflange = wflange.cut(Part.makeCylinder(3.4, 8, P(d0 - 1, Rd + 11.0, 7.5 + 15 * k), V(1, 0, 0)))   # 24 x M8 tapped
# outlet: rounded-rectangle opening (x 120 x z 240) on the drum -> round DN250 (ID 260.4) at y 272, stub to 285, PN6 flange 285..305
XC_OUT = 0.5 * (d0 + d1); Y_T0, Y_T1, Y_STUB, Y_FL = 150.0, 222.0, 230.0, 250.0     # H1 face on the E3/E4 envelope boundary (ROOF y 8.100)
XH1 = 300.0                                       # H1 flange centre: skewed transition clears the drum west cover and E4 spools C1 (x 15) / C2 (x 60)
xc_y = lambda y: XC_OUT + (XH1 - XC_OUT) * (y - Y_T0) / (Y_T1 - Y_T0)
def sel_wire(y, a, b, R, n=64, rnd=4.0):
    pts = []
    for k in range(n):
        ph = 2 * math.pi * k / n; c, s_ = math.cos(ph), math.sin(ph)
        if R is None: pts.append(V(XC_OUT + a * math.copysign(abs(c) ** (2 / rnd), c), y, b * math.copysign(abs(s_) ** (2 / rnd), s_)))
        else: pts.append(V(XH1 + R * c, y, R * s_))
    return Part.makePolygon(pts + [pts[0]])
lo_out = Part.makeLoft([sel_wire(Y_T0, 63.0, 123.0, None), sel_wire(Y_T1, 0, 0, 136.5)], True, True)
lo_in = Part.makeLoft([sel_wire(Y_T0 - 0.01, 60.0, 120.0, None), sel_wire(Y_T1 + 0.01, 0, 0, 130.2)], True, True)
drum_in = Part.makeCylinder(Rd - 3.0, d1 - d0 + 2, V(d0 - 1, 0, 0), V(1, 0, 0))
trans = lo_out.cut(lo_in).cut(drum_in)
stub = Part.makeCylinder(136.5, Y_STUB - Y_T1, V(XH1, Y_T1, 0), V(0, 1, 0)).cut(Part.makeCylinder(130.2, Y_STUB - Y_T1, V(XH1, Y_T1, 0), V(0, 1, 0)))
flg = Part.makeCylinder(187.5, Y_FL - Y_STUB, V(XH1, Y_STUB, 0), V(0, 1, 0)).cut(Part.makeCylinder(130.2, Y_FL - Y_STUB, V(XH1, Y_STUB, 0), V(0, 1, 0)))
for k in range(12):
    a_ = math.radians(15 + 30 * k)
    flg = flg.cut(Part.makeCylinder(9.0, 30, V(XH1 + 167.5 * math.cos(a_), Y_STUB - 5, 167.5 * math.sin(a_)), V(0, 1, 0)))
# TOT thermocouple / exit-pressure bosses on the transition (y 230)
y_tc = 214.0; f_ = (y_tc - Y_T0) / (Y_T1 - Y_T0); a_tc = 63 + (136.5 - 63) * f_; b_tc = 123 + (136.5 - 123) * f_   # outside the drum (|z| > 100)
TOT = [(-40.0, 1, 'TE-505A'), (40.0, -1, 'TE-505B'), (0.0, 1, 'PT-525')]           # (x offset, side +1 top / -1 bottom, tag)
tot_boss = [Part.makeCylinder(7.0 if tg != 'PT-525' else 6.0, 26, V(xc_y(y_tc) + dx, y_tc, sd * (b_tc - 16)), V(0, 0, sd)) for dx, sd, tg in TOT]
body = bell.fuse([hubcyl, eastw, shell, wflange, trans, stub, flg] + tot_boss)
body = body.cut(lo_in)
body = body.cut(Part.makeCompound([Part.makeCylinder(1.6 if tg != 'PT-525' else 0.8, 50, V(xc_y(y_tc) + dx, y_tc, sd * (b_tc - 30)), V(0, 0, sd)) for dx, sd, tg in TOT]))
if not FAST: body = body.removeSplitter()
add('E3-110', 'Collector_Body', body, '1.4828 (310S-class) sheet 2.5-3 mm, TIG; outlet flange 1.4541 EN 1092-1 PN6 DN250', RHO['S1_4828'], 'hot')

# ---------------------------------------------------------------- E3-111 drum west cover (bolted: hot module slides in from the west)
cover = ring(X['drum0'], X['drum0'] + 6.0, 42.5, Rd + 20.0)
for k in range(24): cover = cover.cut(Part.makeCylinder(4.5, 8, P(X['drum0'] - 1, Rd + 11.0, 7.5 + 15 * k), V(1, 0, 0)))
for k in range(12): cover = cover.cut(Part.makeCylinder(3.3, 8, P(X['drum0'] - 1, 66.0, 15 + 30 * k), V(1, 0, 0)))
add('E3-111', 'Collector_WestCover', cover, '1.4828 plate 6 mm, laser cut + machined', RHO['S1_4828'], 'hot')

# ---------------------------------------------------------------- E3-112 thermal-barrier support cone (collector -> PMG housing), E3-113 insulation, E3-107 heat shield
X_SUP = 336.0
cone = rv([(d1, GEO['drum_hub_r'] - 2.5), (d1, GEO['drum_hub_r'] - 0.5), (X_SUP, 81.5), (X_SUP, 79.5)])
for k in range(6):                                   # 6 windows: lower conduction + routing of B1 oil/buffer/RTD lines
    th = 30 + 60 * k
    w_ = Part.makeBox(20, 40, 24, V(306, -20, -12)); w_.rotate(V(0, 0, 0), V(1, 0, 0), th - 90)
    w_.translate(P(0, 89.0, th) - V(0, 0, 0)); cone = cone.cut(Part.makeCylinder(11, 40, P(317, 70, th), rdir(th)))
cone = cone.fuse(ring(X_SUP - 3, X_SUP, 76.0, 86.0))
add('E3-112', 'Support_Cone', cone, 'IN625 sheet 1.5 mm spun + flange, 6 windows; mica spacer 3 mm at the PMG flange', RHO['IN625'], 'hot')
ins = ring(X['rad_e'] + T_C + 0.5, d1 - 3.1, GEO['drum_hub_r'] - T_C - 6.5, GEO['drum_hub_r'] - T_C - 0.1)
add('E3-113', 'Insulation_HubCylinder', ins, 'microporous panel 6 mm (+ 3 mm ceramic paper on the hub bell, not modelled)', RHO['ins'], 'hot')
shield = ring(L['disk_rear_rim'] + 0.7, L['disk_rear_rim'] + 1.5, 17.0, 24.0)
add('E3-107', 'Heat_Shield', shield, '1.4828 0.8 mm + ceramic paper 3 mm, 3 standoffs on the B1 housing', RHO['S1_4828'], 'hot')

# ---------------------------------------------------------------- rotor: E3-103 blisk, E3-104 nut, E3-105 stud, E3-106 heat-dam sleeve
hub_r = lambda x: GEO['rot_hub_le'] + (GEO['rot_hub_te'] - GEO['rot_hub_le']) * (x - X['rot_le']) / (X['rot_te'] - X['rot_le'])
rim = frustum(L['disk_front'], L['disk_rear_rim'], hub_r(L['disk_front']), hub_r(L['disk_rear_rim'])).cut(
      Part.makeCylinder(24.5, L['disk_rear_rim'] - L['disk_front'], V(L['disk_front'], 0, 0), V(1, 0, 0)))
web = rv([(L['hub_front'], 5.25), (L['hub_front'], 15.0), (L['hub_front'] + 8.0, 17.0), (L['hub_front'] + 8.0, 22.0), (L['disk_front'] + 1.0, 24.6),
          (L['disk_rear_rim'] - 1.0, 24.6), (L['hirth'] - 7.0, 22.0), (L['hirth'] - 7.0, 17.0), (L['hirth'], 15.0), (L['hirth'], 5.25)])
x0r, x1r = L['disk_front'] + 0.3, L['disk_rear_rim'] - 0.3
ann_r = cone_tube(x0r, x1r, hub_r(x0r) - 0.5, hub_r(x1r) - 0.5, rt(x0r), rt(x1r))
x_mid_r = 0.5 * (X['rot_le'] + X['rot_te'])
blades = blade_row(G_['rotor_sections'], ZR, x_mid_r, ROT, ann_r)
blisk = rim.fuse([web] + blades)
if not FAST: blisk = blisk.removeSplitter()
add('E3-103', 'FPT_Blisk', blisk, 'IN718 (AMS 5662/5663 forging, VDM/Aubert&Duval or GH4169), 5-axis, Hirth 24T rear', RHO['IN718'], 'rotor')
nut = hexprism(L['nut0'], 6.0, 15.0).cut(Part.makeCylinder(5.0, 6.0, V(L['nut0'], 0, 0), V(1, 0, 0)))
add('E3-104', 'FPT_Nut', nut, 'IN718 M10x1.25 RH, 15 AF, silver-plated thread', RHO['IN718'], 'rotor')
stud = Part.makeCylinder(5.0, L['shaft0'] + 16.0 - L['stud0'], V(L['stud0'], 0, 0), V(1, 0, 0))
add('E3-105', 'Tie_Stud', stud, 'IN718 M10x1.25 stud, rolled threads, preload ~25 kN', RHO['IN718'], 'rotor')
sleeve_hd = ring(L['hirth'], L['sleeve1'], 10.0, 13.5)
for xt in (224.5, 226.5, 228.5, 230.5): sleeve_hd = sleeve_hd.fuse(ring(xt, xt + 0.8, 13.0, 14.0))
sleeve_hd = sleeve_hd.fuse(ring(L['sleeve1'] - 4.0, L['sleeve1'] - 2.0, 13.0, 17.5)).removeSplitter()
add('E3-106', 'HeatDam_Sleeve', sleeve_hd, 'IN718, Hirth 24T front face, 4 labyrinth teeth r 14.0, oil slinger', RHO['IN718'], 'rotor')

# ---------------------------------------------------------------- E3-201 shaft, PM rotor (E3-202 magnets, E3-203 CF sleeve, E3-204 end rings)
shaft = rv([tuple(p) for p in L['shaft_profile']])
shaft = shaft.cut(Part.makeCylinder(5.0, 16.0, V(L['shaft0'], 0, 0), V(1, 0, 0)))          # M10x1.25 tapped hole for the stud
add('E3-201', 'Shaft', shaft, '34CrNiMo6 (1.6582) Q+T 1000-1100 MPa, ground h5 seats, magnetic return of the 2-pole rotor', RHO['steel'], 'rotor')
mags = ring(L['mag0'], L['mag1'], PM['R_shaft'], PM['R_mag'])
for k in range(1, 8): mags = mags.cut(ring(L['mag0'] + k * (L['mag1'] - L['mag0']) / 8 - 0.05, L['mag0'] + k * (L['mag1'] - L['mag0']) / 8 + 0.05, PM['R_shaft'], PM['R_mag']))
add('E3-202', 'PM_Magnets', mags, 'Sm2Co17 (VACOMAX 225 HR class), 8 axial x 8 segments, parallel (2-pole) magnetised', RHO['SmCo'], 'rotor')
cfs = ring(L['slv0'], L['slv1'], PM['R_mag'], PM['R_sleeve'])
add('E3-203', 'CF_Sleeve', cfs, 'T700S/high-Tg epoxy hoop-wound, 3.0 mm, 0.18 mm diametral interference', RHO['CFRP'], 'rotor')
erings = ring(L['slv0'], L['mag0'], PM['R_shaft'], PM['R_mag']).fuse(ring(L['mag1'], L['slv1'], PM['R_shaft'], PM['R_mag']))
add('E3-204', 'Magnet_EndRings', erings, 'Ti-6Al-4V (non-magnetic), bonded', RHO['Ti64'], 'rotor')
brg1 = ring(L['b1_0'], L['b1_1'], B1['d'] / 2, B1['D'] / 2)
add('E3-205', 'Bearing_B1_71905_hybrid', brg1, B1['desig'], RHO['brg'] * 0.75, 'bearing')
brg2 = ring(L['b2_0'], L['b2_1'], B2['d'] / 2, B2['D'] / 2)
add('E3-206', 'Bearing_B2_7005_hybrid', brg2, B2['desig'], RHO['brg'] * 0.75, 'bearing')
lnut = ring(L['nut2_0'], L['nut2_1'], 10.0, 16.0)
add('E3-210', 'B2_Locknut', lnut, 'precision locknut M20x1 (KMT/KMD 4 class)', RHO['steel'], 'rotor')
tgt = ring(L['tgt0'], L['tgt1'], 9.0, 14.0)
for th in (0.0, 180.0):
    tooth = Part.makeBox(L['tgt1'] - L['tgt0'], 6.0, 3.5, V(L['tgt0'], -3.0, 13.8)); tooth.rotate(V(0, 0, 0), V(1, 0, 0), th - 90 + 90)
    tgt = tgt.fuse(tooth)
tgt = tgt.common(Part.makeCylinder(17.0, 10, V(L['tgt0'] - 1, 0, 0), V(1, 0, 0))).removeSplitter()
add('E3-211', 'N2_Target_2tooth', tgt, '1.4542 (17-4PH, ferromagnetic) 2-tooth wheel -> 2 ppr (2.0 kHz @ 60k)', RHO['S17_4'], 'rotor')

# ---------------------------------------------------------------- bearing supports: E3-207/208 SFD cartridges (O-ring centred), E3-209 preload spring
sf1, sf2 = G_['SFD'], G_['SFD2']
cart1 = ring(L['b1_0'] - 4.0, L['b1_1'] + 4.0, B1['D'] / 2, sf1['R']).fuse(ring(L['b1_0'] - 4.0, L['b1_0'], 19.5, B1['D'] / 2))
cart1 = cart1.cut(ring(L['b1_0'] - 3.5, L['b1_0'] - 0.9, sf1['R'] - 1.4, sf1['R'] + 0.1)).cut(ring(L['b1_1'] + 0.9, L['b1_1'] + 3.5, sf1['R'] - 1.4, sf1['R'] + 0.1))
add('E3-207', 'B1_SFD_Cartridge', cart1, '1.4542 (17-4PH H1150), SFD land OD 50 g5, 2 x FKM O-ring 2.62 (centring)', RHO['S17_4'], 'stator')
c2x0, c2x1 = L['b2_0'] - 4.0, L['b2_1'] + 5.4
cart2 = ring(c2x0, c2x1, B2['D'] / 2, sf2['R']).fuse(ring(c2x1 - 2.0, c2x1, 20.0, B2['D'] / 2))
cart2 = cart2.cut(ring(c2x0 + 0.5, c2x0 + 3.1, sf2['R'] - 1.4, sf2['R'] + 0.1)).cut(ring(c2x1 - 4.6, c2x1 - 2.0, sf2['R'] - 1.4, sf2['R'] + 0.1))
add('E3-208', 'B2_SFD_Cartridge', cart2, '1.4542 (17-4PH H1150), SFD land OD 55 g5, 2 x FKM O-ring 2.62', RHO['S17_4'], 'stator')
spring = ring(L['b2_1'] + 0.4, c2x1 - 2.0, 20.5, 23.3)
add('E3-209', 'B2_Preload_WaveSpring', spring, 'wave spring 17-7PH, 200 N at 3.0 mm', RHO['steel'], 'stator')

# ---------------------------------------------------------------- E3-301 B1 bearing housing (SLM 316L, oil galleries / jets, labyrinth + windback lands)
b1h = rv([(222.8, 14.15), (222.8, 21.0), (230, 23.5), (236, 26.0), (239.5, 28.5), (242, 30.5), (246, 33.0), (258, 33.0), (258, 60.0), (262, 60.0),
          (262, sf1['R'] + 0.075), (L['b1_0'] - 4.0, sf1['R'] + 0.075), (L['b1_0'] - 4.0, 21.5), (239, 21.5), (239, 13.65), (235, 13.65), (235, 18.0),
          (232, 18.0), (232, 14.15)])
for k in range(8): b1h = b1h.cut(Part.makeCylinder(2.75, 6, P(257, 52.0, 22.5 + 45 * k), V(1, 0, 0)))
for th in (90.0, 210.0, 330.0):                    # oil jets (d 0.8) aimed at the inner-ring/cage gap
    b1h = b1h.cut(Part.makeCylinder(0.4, 12, P(L['b1_0'] - 6, 20.5, th), V(1, -0.0, 0)))
b1h = b1h.cut(Part.makeCylinder(1.5, 30, P(233.5, 17.0, 45.0), rdir(45.0)))   # buffer-air feed
b1h = b1h.cut(Part.makeCylinder(2.5, 20, P(L['b1'] + 6, 14.0, 270.0), rdir(270.0)))   # sump drain
add('E3-301', 'B1_Bearing_Housing', b1h, 'SLM 316L (3dfast) with internal oil/buffer galleries, HIP-free stress relief, bores machined', RHO['SS316L'], 'stator')

# ---------------------------------------------------------------- E3-302 PMG housing + cooling jacket (SLM AlSi10Mg, helical channel)
RJ_I, RJ_O = PM['R_out'], PM['R_out'] + 12.0
X_PF0 = 262.0; X_PR1 = L['shield_rear']
pmh = ring(X_PF0, X_PF0 + 8.0, 15.15, RJ_O).fuse([ring(X_PF0 + 8.0, X_PR1, RJ_I, RJ_O), ring(X_PR1 - 6.0, X_PR1, RJ_O, RJ_O + 5.2),
                                                  ring(X_SUP, X_SUP + 6.0, RJ_O, 84.0)])
X_CH0, X_CH1, PITCH = 300.0, 390.0, 15.0
helix_ok = False
if os.environ.get('E3_HELIX', '0') == '1':      # true helical sweep (valid solid, but the OCC boolean with the jacket is unreliable)
  try:
    hx = Part.makeHelix(PITCH, X_CH1 - X_CH0, RJ_I + 6.0)
    prof = Part.makePolygon([V(RJ_I + 3.0, 0, -6.0), V(RJ_I + 9.0, 0, -6.0), V(RJ_I + 9.0, 0, 6.0), V(RJ_I + 3.0, 0, 6.0), V(RJ_I + 3.0, 0, -6.0)])
    ch = Part.Wire(hx).makePipeShell([prof], True, True)
    ch.rotate(V(0, 0, 0), V(0, 1, 0), 90); ch.translate(V(X_CH0, 0, 0))
    if ch.Volume < 0: ch.reverse()
    pmh2 = pmh.cut(ch); helix_ok = pmh2.isValid() and len(pmh2.Solids) == 1 and pmh2.Volume > 0.5 * pmh.Volume
    if helix_ok: pmh = pmh2
  except Exception as e:
    say('helix channel failed (%s)' % e)
if not helix_ok:                                  # section-equivalent model: 6 annular grooves 12 x 6 at the helix pitch
    pmh = pmh.cut(Part.makeCompound([ring(X_CH0 + k * PITCH, X_CH0 + k * PITCH + 12, RJ_I + 3, RJ_I + 9) for k in range(6)]))
ports_pm = dict(GLY_IN=(392.0, 270.0, 8.0, 6.0), GLY_OUT=(298.0, 90.0, 8.0, 6.0), OIL_SUP_B1=(266.0, 90.0, 6.0, 2.5),
                BUFFER_AIR=(266.0, 45.0, 6.0, 2.0), SCAV_B1=(266.0, 270.0, 8.0, 5.0), RTD_B1=(266.0, 180.0, 6.0, 2.5))
pmh = pmh.fuse([radial_boss(xx, th, RJ_O - 1.0, RJ_O + 10.0, rb) for (xx, th, rb, bo) in ports_pm.values()] +
               [radial_boss(350.0, 180.0, RJ_O - 1.0, RJ_O + 5.0, 12.0)])                  # + VE-011 accelerometer pad
tools = [Part.makeCylinder(4.0, 20, P(274.0, RJ_I - 3, 30 + 60 * k), rdir(30 + 60 * k)) for k in range(6)]     # gap-air vents
tools += [Part.makeCylinder(bo, 20, P(xx, RJ_O - 4.0 if nm.startswith('GLY') else RJ_I - 1, th), rdir(th)) for nm, (xx, th, rb, bo) in ports_pm.items()]
tools += [Part.makeCylinder(6.0, 20, P(400.0, RJ_I - 2, 90.0), rdir(90.0))]                  # phase-lead feed-through to the terminal box
tools += [Part.makeCylinder(2.75, 8, P(X_PR1 - 7, RJ_O + 2.5, 22.5 + 45 * k), V(1, 0, 0)) for k in range(8)]
tools += [Part.makeCylinder(2.75, 8, P(X_SUP - 1, 80.0, 30.0 * k), V(1, 0, 0)) for k in range(12)]   # cone flange bolts
pmh = pmh.cut(Part.makeCompound(tools))
if not FAST: pmh = pmh.removeSplitter()
add('E3-302', 'PMG_Housing_Jacket', pmh, 'SLM AlSi10Mg (3dfast), helical glycol channel 12x6, T6, bore machined (stator shrink fit)', RHO['AlSi10Mg'], 'stator')

# ---------------------------------------------------------------- E3-303 stator core, E3-304 winding
stk0, stk1 = L['stk0'], L['stk1']
core = ring(stk0, stk1, PM['R_bore'], PM['R_out'])
r_open, r_sb = PM['R_bore'] + PS['tooth_tip'] + PS['wedge'], PM['R_slot_bottom']
def slot_prism(r0, r1, shrink=0.0):
    w0 = 2 * math.pi * r0 / PM['Qs'] - PS['b_tooth'] - 2 * shrink; w1 = 2 * math.pi * r1 / PM['Qs'] - PS['b_tooth'] - 2 * shrink
    pr = Part.makePolygon([V(0, r0 + shrink, -w0 / 2), V(0, r1 - shrink, -w1 / 2), V(0, r1 - shrink, w1 / 2), V(0, r0 + shrink, w0 / 2), V(0, r0 + shrink, -w0 / 2)])
    return Part.Face(pr).extrude(V(stk1 - stk0, 0, 0))
sl0 = slot_prism(r_open, r_sb).fuse(Part.makeBox(stk1 - stk0, r_open - PM['R_bore'] + 0.2, PS['b_open'], V(0, PM['R_bore'] - 0.1, -PS['b_open'] / 2)))
sl0.translate(V(stk0, 0, 0))
for k in range(PM['Qs']):
    s_ = sl0.copy(); s_.rotate(V(0, 0, 0), V(1, 0, 0), 360.0 * k / PM['Qs']); core = core.cut(s_)
add('E3-303', 'Stator_Core', core, '0.10 mm NO10 Si-steel (JFE 10JNEX900 / Baosteel B10AT class), bonded stack 63 mm, 24 slots', RHO['lam'], 'stator')
cu0 = slot_prism(r_open, r_sb, 0.35); cu0.translate(V(stk0, 0, 0))
wind = []
for k in range(PM['Qs']):
    c_ = cu0.copy(); c_.rotate(V(0, 0, 0), V(1, 0, 0), 360.0 * k / PM['Qs']); wind.append(c_)
lea = PM['l_end_ax']
ew_f = rv([(stk0, r_open + 0.5), (stk0 - lea + 6, r_open + 1.0), (stk0 - lea, 0.5 * (r_open + r_sb)), (stk0 - lea + 6, r_sb - 1.0), (stk0, r_sb - 0.5)])
ew_r = rv([(stk1, r_open + 0.5), (stk1 + lea - 6, r_open + 1.0), (stk1 + lea, 0.5 * (r_open + r_sb)), (stk1 + lea - 6, r_sb - 1.0), (stk1, r_sb - 0.5)])
winding = ew_f.fuse(wind + [ew_r])
add('E3-304', 'Stator_Winding', winding, 'Litz Cu (7 mm2 per conductor, 7 cond/slot, 2-layer 10/12 pitch, 2-pole), class H, VPI + potted end turns, 3 x PT1000', RHO['wind'], 'stator')

# ---------------------------------------------------------------- E3-305 B2 housing / rear end shield, E3-306 end cover, E3-307 terminal box
b2h = ring(X_PR1, X_PR1 + 6.0, 15.15, RJ_O + 5.2).fuse(ring(X_PR1 + 6.0, c2x1 + 0.6, sf2['R'] + 0.075, 36.0))
for k in range(8): b2h = b2h.cut(Part.makeCylinder(2.75, 8, P(X_PR1 - 1, RJ_O + 2.5, 22.5 + 45 * k), V(1, 0, 0)))
ports_b2 = dict(OIL_SUP_B2=(L['b2'], 90.0, 6.0, 2.5), SCAV_B2=(L['b2'], 270.0, 8.0, 5.0), RTD_B2=(L['b2'], 0.0, 6.0, 2.5))
for nm, (xx, th, rb, bo) in ports_b2.items():
    b2h = b2h.fuse(radial_boss(xx, th, 35.0, 46.0, rb)).cut(Part.makeCylinder(bo, 30, P(xx, 26.0, th), rdir(th)))
b2h = b2h.fuse(radial_boss(L['b2'], 180.0, 35.0, 40.0, 11.0))                  # VE-012 pad
GA_X = X_PR1 + 3.0
b2h = b2h.fuse(radial_boss(GA_X, 0.0, RJ_O, RJ_O + 14.0, 9.0)).cut(Part.makeCylinder(5.0, 40, P(GA_X, 50.0, 0.0), rdir(0.0)))   # gap-air inlet
add('E3-305', 'B2_Housing_EndShield', b2h, 'SLM 316L (3dfast) with oil galleries, bores machined', RHO['SS316L'], 'stator')
X_CV0 = c2x1 + 0.6; X_CV1 = L['cover1']
cover_e = ring(X_CV0, X_CV1 - 3.0, 37.0, 40.0).fuse(ring(X_CV1 - 3.0, X_CV1, 0.0, 40.0))
X_N2 = 0.5 * (L['tgt0'] + L['tgt1'])
cover_e = cover_e.fuse([radial_boss(X_N2, th, 39.0, 52.0, 8.0) for th in (45.0, 135.0)])
cover_e = cover_e.cut(Part.makeCompound([Part.makeCylinder(6.0, 30, P(X_N2, 33.0, th), rdir(th)) for th in (45.0, 135.0)]))
add('E3-306', 'End_Cover', cover_e, 'AlSi10Mg / 6082-T6 machined, 2 x M12x1 N2 sensor bosses', RHO['AlSi10Mg'], 'stator')
TB = dict(x0=380.0, x1=448.0, y=50.0, z0=RJ_O + 1.0, z1=RJ_O + 80.0)
tbox = Part.makeBox(TB['x1'] - TB['x0'], 2 * TB['y'], TB['z1'] - TB['z0'], V(TB['x0'], -TB['y'], TB['z0'])).cut(
       Part.makeBox(TB['x1'] - TB['x0'] - 6, 2 * TB['y'] - 6, TB['z1'] - TB['z0'] - 3, V(TB['x0'] + 3, -TB['y'] + 3, TB['z0'])))
tbox = tbox.fuse(Part.makeCylinder(24, 12, V(TB['x1'], 0, 0.5 * (TB['z0'] + TB['z1'])), V(1, 0, 0)).cut(Part.makeCylinder(20, 14, V(TB['x1'] - 1, 0, 0.5 * (TB['z0'] + TB['z1'])), V(1, 0, 0))))
add('E3-307', 'Terminal_Box', tbox, 'AlSi10Mg cast / Al box IP66, 3 x M8 studs on PEEK board, PT1000 connector, M40 EMC gland (east)', RHO['AlSi10Mg'], 'stator')

# ---------------------------------------------------------------- E3-401/402 feet (axially compliant flexure plates; skid top assumed ENG z -400 = ROOF 0.200)
Z_SKID = -400.0
XF1 = 225.0
ff = Part.makeBox(8, 180, 260, V(XF1 - 4, -90, Z_SKID + 10)).cut(Part.makeCylinder(Rd - 2.0, d1 - d0, V(d0, 0, 0), V(1, 0, 0)))
ff = ff.common(Part.makeBox(8, 180, 400, V(XF1 - 4, -90, Z_SKID))).fuse(Part.makeBox(48, 260, 10, V(XF1 - 24, -130, Z_SKID)))
for sy in (-100, 100):
    ff = ff.cut(Part.makeBox(16, 9, 12, V(XF1 - 20, sy - 4.5, Z_SKID - 1))).cut(Part.makeBox(16, 9, 12, V(XF1 + 4, sy - 4.5, Z_SKID - 1)))
ff = ff.common(Part.makeBox(60, 300, Rd + 400, V(XF1 - 30, -150, Z_SKID))).removeSplitter()
add('E3-401', 'Foot_Front_Flexure', ff, '1.4828 plate 8 mm flexure (axial stroke +-2 mm) + base 10 mm, slotted M12 holes', RHO['S1_4828'], 'support')
XF2 = X_PR1 - 10.0
fr = Part.makeBox(10, 160, 340, V(XF2 - 5, -80, Z_SKID + 10)).cut(Part.makeCylinder(RJ_O - 0.5, 40, V(XF2 - 20, 0, 0), V(1, 0, 0)))
fr = fr.common(Part.makeBox(10, 160, Z_SKID * -1 - 60, V(XF2 - 5, -80, Z_SKID))).fuse(Part.makeBox(50, 220, 10, V(XF2 - 25, -110, Z_SKID)))
for sy in (-90, 90): fr = fr.cut(Part.makeCylinder(6.5, 12, V(XF2 - 15, sy, Z_SKID - 1), V(0, 0, 1))).cut(Part.makeCylinder(6.5, 12, V(XF2 + 15, sy, Z_SKID - 1), V(0, 0, 1)))
fr = fr.removeSplitter()
add('E3-402', 'Foot_Rear_Flexure', fr, 'S355J2 / 1.4301 plate 10 mm flexure + base, clamp band to the PMG jacket', RHO['steel'], 'support')

# ---------------------------------------------------------------- E3-5xx sensors (envelopes)
SENS = {}
def sensor(tag, name, shp, desc, pos, direction):
    SENS[tag] = dict(name=name, desc=desc, pos=pos, dir=direction)
    add(tag, name, shp, desc, RHO['misc'], 'sensor')
for tg, th, io in (('E3-501', 45.0, 'TE-510A'), ('E3-502', 225.0, 'TE-510B')):
    s_ = Part.makeCylinder(0.75, 52.0 - 28.0, P(X['tc_in'], 28.0, th), rdir(th)).fuse(Part.makeCylinder(5.0, 20, P(X['tc_in'], 52.0, th), rdir(th)))
    sensor(tg, io + '_FPT_inlet_TC', s_, 'type K class 1, MI 1.5 mm Inconel 600, ungrounded, immersion mid-span (Roessel / Electronic Sensor)',
           [X['tc_in'], round(52 * math.cos(math.radians(th)), 1), round(52 * math.sin(math.radians(th)), 1)], [0, round(math.cos(math.radians(th)), 3), round(math.sin(math.radians(th)), 3)])
s_ = Part.makeCylinder(4.0, 18, P(X['tc_in'], 52.0, 135.0), rdir(135.0))
sensor('E3-503', 'PT-524_P45_tap', s_, 'static tap 1.6 mm + 1/8" tube to PT-524 (0-4 bar abs)', [X['tc_in'], -36.8, 36.8], [0, -0.707, 0.707])
for tg, (dx, sd, io) in zip(('E3-504', 'E3-505'), TOT[:2]):
    z_ = sd * (b_tc + 10)          # fitting outside the boss
    s_ = Part.makeCylinder(0.75, 70, V(xc_y(y_tc) + dx, y_tc, z_), V(0, 0, -sd)).fuse(Part.makeCylinder(5.0, 20, V(xc_y(y_tc) + dx, y_tc, z_), V(0, 0, sd)))
    sensor(tg, io + '_FPT_exit_TOT', s_, 'type K class 1, MI 3 mm Inconel 600, immersion 60 mm (TOT = recuperator hot inlet)', [round(xc_y(y_tc) + dx, 1), y_tc, round(z_, 1)], [0, 0, -sd])
s_ = Part.makeCylinder(4.0, 18, V(xc_y(y_tc), y_tc, b_tc + 10), V(0, 0, 1))
sensor('E3-506', 'PT-525_FPT_exit_tap', s_, 'static tap (proposed new tag PT-525, FPT exit/collector static)', [round(xc_y(y_tc), 1), y_tc, round(b_tc + 10, 1)], [0, 0, -1])
for tg, th, io in (('E3-507', 45.0, 'SE-002B1'), ('E3-508', 135.0, 'SE-002B2')):
    s_ = Part.makeCylinder(6.0, 52.0 - 18.0, P(X_N2, 18.0, th), rdir(th)).fuse(Part.makeCylinder(7.0, 25, P(X_N2, 52.0, th), rdir(th)))
    sensor(tg, io + '_N2_speed', s_, 'M12x1 Hall/inductive speed sensor, 2 ppr on the 2-tooth target, gap 1.0 mm (Jaquet DSD / Baumer class)',
           [round(X_N2, 1), round(52 * math.cos(math.radians(th)), 1), round(52 * math.sin(math.radians(th)), 1)], [0, round(math.cos(math.radians(th)), 3), round(math.sin(math.radians(th)), 3)])
s_ = Part.makeCylinder(10.0, 25, P(350.0, RJ_O + 5.0, 180.0), rdir(180.0))
sensor('E3-509', 'VE-011_vib_FPT_side', s_, 'IEPE 100 mV/g accelerometer, M5 stud (MMF KS80D / Hansford HS-100 class), radial horizontal', [350.0, -(RJ_O + 5.0), 0.0], [0, -1, 0])
s_ = Part.makeCylinder(10.0, 25, P(L['b2'], 40.0, 180.0), rdir(180.0))
sensor('E3-510', 'VE-012_vib_PMG_end', s_, 'IEPE 100 mV/g accelerometer, radial horizontal at B2', [round(L['b2'], 1), -40.0, 0.0], [0, -1, 0])
s_ = Part.makeCylinder(2.5, 20, P(L['b2'], 26.0, 0.0), rdir(0.0)).fuse(Part.makeCylinder(5, 12, P(L['b2'], 46.0, 0.0), rdir(0.0)))
sensor('E3-511', 'TE-721_B2_RTD', s_, 'PT1000 class A, 3-wire, spring-loaded on the B2 outer ring', [round(L['b2'], 1), 46.0, 0.0], [0, 1, 0])
s_ = Part.makeCylinder(2.5, 14, P(L['b1'] + 2, 25.2, 180.0), rdir(180.0))
sensor('E3-512', 'TE-720_B1_RTD', s_, 'PT1000 class A, 3-wire, embedded in the B1 housing at the outer ring, lead via cone window', [round(L['b1'] + 2, 1), -39.2, 0.0], [0, -1, 0])
fan = Part.makeCylinder(30.0, 30.0, P(GA_X, RJ_O + 14.0, 0.0), rdir(0.0))
add('E3-701', 'GapAir_Fan_48V', fan, '48 V EC radial blower 4 g/s @ 2 kPa + G4 filter (ebm-papst / Micronel class)', RHO['misc'] * 0.3, 'aux')

# =====================================================================================================================
# mass properties of the rotor (-> sim/engine/e3_fpt_pmg_calc.py second pass)
def massprops(shape, rho):
    sols = shape.Solids; vt = sum(s.Volume for s in sols)
    cx = sum(s.Volume * s.CenterOfMass.x for s in sols) / vt; cy = sum(s.Volume * s.CenterOfMass.y for s in sols) / vt
    cz = sum(s.Volume * s.CenterOfMass.z for s in sols) / vt
    Ixx = Iyy = 0.0
    for s in sols:
        I = s.MatrixOfInertia; c = s.CenterOfMass; v = s.Volume
        Ixx += I.A11 + v * ((c.y - cy) ** 2 + (c.z - cz) ** 2); Iyy += I.A22 + v * ((c.x - cx) ** 2 + (c.z - cz) ** 2)
    return dict(mass_kg=vt * rho, x_cg_mm=cx, y_cg_mm=cy, z_cg_mm=cz, Ip_kgm2=Ixx * rho * 1e-6, It_kgm2=Iyy * rho * 1e-6)
RMAP = {'FPT_blisk': ['E3-103'], 'FPT_nut': ['E3-104'], 'tie_stud': ['E3-105'], 'heatdam_sleeve': ['E3-106'], 'shaft': ['E3-201'],
        'magnets': ['E3-202'], 'sleeve_endrings': ['E3-203', 'E3-204'], 'B2_locknut': ['E3-210'], 'N2_target': ['E3-211']}
mp = {}
for k, tags in RMAP.items():
    if len(tags) == 1: mp[k] = massprops(PARTS[tags[0]]['shape'], PARTS[tags[0]]['rho'])
    else:
        ps = [massprops(PARTS[t]['shape'], PARTS[t]['rho']) for t in tags]; m = sum(p['mass_kg'] for p in ps)
        xc = sum(p['mass_kg'] * p['x_cg_mm'] for p in ps) / m
        mp[k] = dict(mass_kg=m, x_cg_mm=xc, Ip_kgm2=sum(p['Ip_kgm2'] for p in ps),
                     It_kgm2=sum(p['It_kgm2'] + p['mass_kg'] * ((p['x_cg_mm'] - xc) * 1e-3) ** 2 for p in ps))
J_cad = sum(v['Ip_kgm2'] for v in mp.values()) + sum(CR['rotor']['components'][k]['Ip_kgm2'] for k in ('B1_inner', 'B2_inner'))
m_cad = sum(v['mass_kg'] for v in mp.values()) + sum(CR['rotor']['components'][k]['mass_kg'] for k in ('B1_inner', 'B2_inner'))
say('rotor (CAD): mass %.3f kg, J = %.4e kg m2 (incl. analytic bearing inner rings); blisk %.1f g Ip %.3e; unbalance check: blisk y_cg %.4f mm'
    % (m_cad, J_cad, mp['FPT_blisk']['mass_kg'] * 1e3, mp['FPT_blisk']['Ip_kgm2'], mp['FPT_blisk']['y_cg_mm']))
json.dump(dict(rotor=mp, J_total_kgm2=J_cad, mass_total_kg=m_cad, note='CAD-measured (cad/engine/fpt_pmg.py); bearing inner rings analytic'),
          open(os.path.join(OUT, 'E3_massprops.json'), 'w'), indent=1)

# =====================================================================================================================
# interference checks: E3 vs GG core (asm_parts v13A) and E3 internal (rotor vs stator, all pairs)
def overlap(a, b):
    if not a.BoundBox.intersect(b.BoundBox): return 0.0
    try: return a.common(b).Volume
    except Exception: return -1.0
GG = {}
for n in ('Turbine', 'TurbineNut', 'NGV', 'Shaft', 'ShaftTunnel', 'Exhaust', 'Casing', 'EGT_Probe', 'Fasteners'):
    f = os.path.join(GG_ASM, n + '.step')
    if os.path.exists(f):
        s = Part.Shape(); s.read(f); GG[n] = s
chk = dict(gg_required={}, gg_replaced={}, internal=[], clearances={})
for n, s in GG.items():
    hits = {}
    for t, p in PARTS.items():
        v = overlap(p['shape'], s)
        if abs(v) > 1e-3: hits[t] = round(v, 3)
    (chk['gg_required'] if n in ('Turbine', 'TurbineNut', 'NGV', 'Shaft') else chk['gg_replaced'])[n] = hits
    say('GG %-12s vs E3: %s' % (n, hits if hits else 'no interference'))
JOINTS = {('E3-101', 'E3-102'), ('E3-101', 'E3-111'), ('E3-102', 'E3-110'), ('E3-110', 'E3-111'), ('E3-110', 'E3-112'), ('E3-112', 'E3-302'),
          ('E3-301', 'E3-302'), ('E3-302', 'E3-303'), ('E3-302', 'E3-305'), ('E3-305', 'E3-306'), ('E3-302', 'E3-307'), ('E3-110', 'E3-401'),
          ('E3-302', 'E3-402'), ('E3-305', 'E3-701'), ('E3-303', 'E3-304')}
tags = sorted(PARTS)
for i, a in enumerate(tags):
    for b in tags[i + 1:]:
        v = overlap(PARTS[a]['shape'], PARTS[b]['shape'])
        if v > 1.0 or v < 0:
            rec = dict(a=a, b=b, vol_mm3=round(v, 2), expected=((a, b) in JOINTS or PARTS[a]['group'] == 'sensor' or PARTS[b]['group'] == 'sensor'))
            chk['internal'].append(rec)
bad = [r for r in chk['internal'] if not r['expected']]
say('E3 internal overlaps > 1 mm3: %d (unexpected %d) %s' % (len(chk['internal']), len(bad), bad[:8]))
# running clearances (rotor vs stator), distance between shapes
def dist(a, b):
    try: return PARTS[a]['shape'].distToShape(PARTS[b]['shape'])[0]
    except Exception: return -1
for a, b, what in (('E3-103', 'E3-102', 'blisk tip / shroud'), ('E3-103', 'E3-101', 'blisk rim / NGV inner ring lip'), ('E3-103', 'E3-110', 'blisk rim / hub bell'),
                   ('E3-106', 'E3-301', 'labyrinth teeth / B1 housing'), ('E3-203', 'E3-303', 'CF sleeve / stator bore'), ('E3-201', 'E3-302', 'shaft / PMG front seal'),
                   ('E3-201', 'E3-305', 'shaft / B2 seal'), ('E3-211', 'E3-507', 'N2 target / sensor B1'), ('E3-103', 'E3-107', 'blisk / heat shield'),
                   ('E3-104', 'E3-101', 'FPT nut / NGV back wall')):
    chk['clearances'][what] = round(dist(a, b), 3)
for n in ('TurbineNut', 'Turbine', 'Shaft'):
    if n in GG: chk['clearances']['GG %s / interduct hub' % n] = round(GG[n].distToShape(PARTS['E3-101']['shape'])[0], 3)
say('clearances (mm): ' + ', '.join('%s %.2f' % kv for kv in chk['clearances'].items()))
json.dump(chk, open(os.path.join(OUT, 'E3_checks.json'), 'w'), indent=1)

# =====================================================================================================================
# exports: per-part STEP, assembly (ENG) + ROOF placement, FCStd
for t, p in PARTS.items():
    p['shape'].exportStep(os.path.join(OUT, '%s_%s.step' % (t, p['name'])))
asm = Part.makeCompound([p['shape'] for p in PARTS.values()])
asm.exportStep(os.path.join(OUT, 'E3_assembly.step'))
asm_r = asm.copy(); asm_r.translate(V(*ROOF0)); asm_r.exportStep(os.path.join(OUT, 'E3_assembly_ROOF.step'))
doc = App.newDocument('E3_FPT_PMG')
COL = dict(hot=(0.85, 0.45, 0.20), rotor=(0.20, 0.40, 0.85), stator=(0.30, 0.65, 0.35), bearing=(0.55, 0.30, 0.70), support=(0.5, 0.5, 0.5),
           sensor=(0.90, 0.10, 0.10), aux=(0.3, 0.3, 0.3))
for t, p in PARTS.items():
    o = doc.addObject('Part::Feature', t.replace('-', '_')); o.Shape = p['shape']; o.Label = '%s %s' % (t, p['name'])
doc.recompute(); doc.saveAs(os.path.join(OUT, 'E3_assembly.FCStd'))
bb = asm.BoundBox
say('assembly bbox x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f mm  -> ROOF X %.3f..%.3f m' % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax,
    (ROOF0[0] + bb.XMin) / 1e3, (ROOF0[0] + bb.XMax) / 1e3))

# =====================================================================================================================
# interfaces
st = CR['stage']; pmr = CR['pmg']; th_ = CR['thermal']; rot = CR['rotor']; br = CR['bearings']
def itf(name, pos, direction, size, counterpart, **kw):
    d = dict(name=name, ENG_mm=[round(v, 2) for v in pos], ROOF_m=roof(pos), direction=direction, size=size, counterpart=counterpart); d.update(kw); return d
IF = []
IF.append(itf('IF-E2E3 flange (E3 front) - reconciled with E2', [X['flangeE2'], 0, 0], [-1, 0, 0],
              'mating face x %.1f; OD %.0f, PCD %.0f, %d x M8 (holes %.0f, phase %.2f deg) 1.4980/A286-class or IN718 studs, silver-plated nuts; '
              'E3 ring IN718 %.0f thick (x %.0f-%.0f); male spigot OD 120 h7 x 3 (x %.0f-%.0f) into the E2 recess (e3_spigot_d 120 / depth 3); '
              'gasket mean dia 137 x 8 wide (E2 flange calc: W 34.4 kN, bolt area req 313 mm2 / avail 525 mm2), KLINGER Milam PSS 1 mm or Thermiculite 815; '
              'gas path ID 70.7 (r 35.35) at x 119.3' % (fr_x0, FR['OD'], FR['PCD'], FR['n'], FR['hole'], FR['phase'], FR['t'], fr_x0, fr_x0 + FR['t'], fr_x0 - 3, fr_x0),
              'E2 rear ring (cad/engine/combustor_casing.py, cad_out/engine/E2/E2_interfaces.json "IF-E2E3 rear flange"): E2 face x 115.0 + 1.0 mm gasket E3-605 '
              '= E3 face x 116.0; 16 x M8 blind tapped in the E2 ring at PCD 160, phase 11.25 deg (= E3 holes); annular groove r 55.5-60.0 x 112-115 for the '
              'E3 spigot; piston ring E2-171 in the E2 bore groove x 112.5-114.5 r 40',
              status='COINCIDENT with E2 (E2 published 2026-10-23). Superseded E3 proposal: face x 122, OD 150, PCD 135, 12 x M6',
              slip_joint='E3 slip bore ID 73.2 (x %.1f-119.3, radial clearance 0.25) over the GG NGV shroud OD 72.7 (x 110.8-118.8); the split piston ring is in the '
                         'E2 rear ring (E2 seal groove x 112.5-114.5, r 40) - no ring on the E3 side; separates casing air 2.9 bar from the 1.25 bar gas path' % fr_x0,
              hub_lip='stationary hub cone lip r 17.8-19.0 at x 119.3; 1.0 mm axial gap to the E1 rotor hub TE (x 118.3, r 19.0); clears GG nut (x 118.8-126.8) and shaft end (127.8)'))
IF.append(itf('H1 exhaust outlet to recuperator hot inlet', [XH1, Y_FL, 0], [0, 1, 0],
              'DN250 PN6 EN 1092-1 type 01 plate flange (OD 375, PCD 335, 12 x M16, holes 18), face y = %.0f; pipe 273 x 6.3; '
              'gas 0.397 kg/s, 611 C, static %.0f Pa (%.3f bar abs), V %.1f m/s' % (Y_FL, st['p5'], st['p5'] / 1e5, st['V5']),
              'E4 recuperator hot-side inlet spool E4-SP-H1 (cad/engine/recuperator.py reads this ENG position): flange, IN625 bellows, 3-piece mitre elbow R150 '
              'down into the E4 inlet plenum. E4 core moved relative to the engine (ROOF X = 1.880 + x) so the spool passes east of the core; '
              'TOT is measured here by TE-505A/B (E4 has no TE-505 boss). DN250 bellows on the E4 side (611 C, E3 growth ~+1.8 mm x / +1.5 mm y)'))
IF.append(itf('Oil supply B1 (jets + SFD)', [266.0, 0, RJ_O + 10], [0, 0, 1], 'boss M10x1 / 6 mm tube; %.2f L/min at %.1f barg, <= 75 C (TE-708)' % (th_['oil_B1_lpm'], th_['oil_supply_barg']),
              'E5 closed-loop oil system (PT-701); route through cone window', heat_W=round(th_['Q_B1_oil_W'])))
IF.append(itf('Oil supply B2 (jets + SFD)', [L['b2'], 0, 46.0], [0, 0, 1], 'boss M10x1 / 6 mm tube; %.2f L/min at %.1f barg' % (th_['oil_B2_lpm'], th_['oil_supply_barg']),
              'E5 oil system', heat_W=round(th_['Q_B2_oil_W'])))
IF.append(itf('Oil scavenge B1 sump', [266.0, 0, -(RJ_O + 10)], [0, 0, -1], 'boss M16x1.5 / 12 mm tube, gravity drain >= 5 deg slope via cone window', 'E5 oil tank (TE-706 on the combined return)'))
IF.append(itf('Oil scavenge B2 sump', [L['b2'], 0, -46.0], [0, 0, -1], 'boss M16x1.5 / 12 mm tube, gravity drain', 'E5 oil tank'))
IF.append(itf('Buffer air to B1 seal annulus', [266.0, (RJ_O + 10) * 0.707, (RJ_O + 10) * 0.707], [0, 0.707, 0.707],
              'boss M8x1 / 4 mm tube; %.1f g/s from compressor delivery (P2 ~3.0 bar) through a %.1f mm orifice + 40 um filter' % (CR['seals']['buffer_total_gs'], CR['seals']['buffer_orifice_mm']),
              'E2 compressor-delivery bleed port on the E2 drum (x -8, azimuth 150 deg, DIN 2353 L6 fitting E2-509; E2_interfaces.json)'))
IF.append(itf('Glycol inlet (PMG jacket)', [392.0, 0, -(RJ_O + 10)], [0, 0, -1], 'G1/2 boss; %.0f L/min 30 %% PG, design 40 C (max 55 C), dp %.0f kPa, heat %.0f W' % (8.0, pmr['dp_glycol'] / 1e3, pmr['Q_glycol']),
              'E5 glycol loop M-751 / DC-1 / HX-4 (TE-GLY)'))
IF.append(itf('Glycol outlet (PMG jacket)', [298.0, 0, RJ_O + 10], [0, 0, 1], 'G1/2 boss (vent at the high point)', 'E5 glycol loop (TE-754)'))
IF.append(itf('PMG power + RTD terminal box', [TB['x1'] + 12, 0, 0.5 * (TB['z0'] + TB['z1'])], [1, 0, 0],
              '3-phase, 2-pole, E_LL %.0f V rms @ 60k (1.0 kHz), I %.0f A rms @ 30 kW, Ls %.0f uH, R_ph %.0f mohm, I_sc %.0f A; M40 EMC gland (3 x 16 mm2 + PE, shielded); '
              'PT1000 TE-760/761/762 + TE-720/721 on M12 8-pin' % (pmr['E_LL'], pmr['I'], pmr['Ls'] * 1e6, pmr['R_ph'] * 1e3, pmr['I_sc']),
              'B3 active rectifier in RP-1 (electrical), cable W-PMG'))
IF.append(itf('Gap-air inlet (PMG cooling)', [GA_X, RJ_O + 44, 0], [0, 1, 0], '48 V fan 4 g/s at ~2 kPa, G4 filter; exits through 6 x d8 vents at x 274 (into the enclosure, hot zone)', 'E5 enclosure ventilation / 48 V (B4)'))
for t, s_ in SENS.items():
    IF.append(itf('Sensor %s %s' % (t, s_['name']), s_['pos'], s_['dir'], s_['desc'], 'B2 / B1 / B3 per docs/electrical/02_io_list'))
IF.append(itf('Foot front (flexure, axially compliant)', [XF1, 0, Z_SKID], [0, 0, -1], 'base 48 x 260 x 10, 4 x slotted M12 (y +-100)', 'E5 skid rail (top assumed ENG z -400 = ROOF Z 0.200)'))
IF.append(itf('Foot rear (flexure)', [XF2, 0, Z_SKID], [0, 0, -1], 'base 50 x 220 x 10, 4 x M12 (y +-90)', 'E5 skid rail; axial fixed point of the engine = E2 casing (E2/E5 to confirm)'))
info = dict(subsystem='E3 interduct + FPT + FPT/PMG rotor + bearings + PMG + exhaust collector', frame='ENG mm; ROOF = (1.880 + x/1000, 7.850 + y/1000, 0.600 + z/1000) m',
            source='cad/engine/fpt_pmg.py + sim/engine/e3_fpt_pmg_calc.py', envelope_ENG_mm=[[round(bb.XMin, 1), round(bb.YMin, 1), round(bb.ZMin, 1)], [round(bb.XMax, 1), round(bb.YMax, 1), round(bb.ZMax, 1)]],
            envelope_ROOF_m=[roof([bb.XMin, bb.YMin, bb.ZMin]), roof([bb.XMax, bb.YMax, bb.ZMax])],
            rotor=dict(N_design_rpm=60000, N_gov_max_rpm=65000, N_trip_rpm=71500, N_overspeed_design_rpm=72000, N_spin_test_rpm=78000,
                       continuous_band_rpm=[48000, 65000], rotation='counter-clockwise seen from the intake (opposite to the GG)',
                       J_kgm2=round(J_cad, 6), J_calc_kgm2=round(rot['J_kgm2'], 6), mass_kg=round(m_cad, 3),
                       criticals_rpm=[round(c['rpm']) for c in CR['rotordynamics']['criticals']] if CR.get('rotordynamics') else None,
                       runaway_ms=CR.get('runaway_ms')),
            fpt=dict(Z_ngv=ZN, Z_rot=ZR, eta_ts=round(st['eta_ts'], 4), eta_tt=round(st['eta_tt'], 4), P_shaft_kW=round(CR['power']['P_shaft_to_PMG'] / 1e3, 2),
                     inlet_P01_Pa=round(CR['interduct']['P01']), T01_K=round(CR['interduct']['T01'], 1), exit_T0_C=round(st['T03'] - 273.15, 1)),
            pmg=dict(P_rated_kW=30, poles=2, f_e_Hz=1000, E_LL_V=round(pmr['E_LL'], 1), I_A=round(pmr['I'], 1), Ls_uH=round(pmr['Ls'] * 1e6), eta=round(pmr['eta'], 4)),
            interfaces=IF)
json.dump(info, open(os.path.join(OUT, 'E3_interfaces.json'), 'w'), indent=1)
say('interfaces -> %s (%d entries)' % (os.path.join(OUT, 'E3_interfaces.json'), len(IF)))

# =====================================================================================================================
# half-section plot (z = 0): E3 + GG turbine / nut / NGV / shaft
def loops_of(shape):
    out = []
    try: ws = shape.slice(V(0, 0, 1), 0.0)
    except Exception: return out
    for w in ws:
        pts = [(p.x, p.y) for p in w.discretize(Deflection=0.05)]
        if len(pts) > 2: out.append(pts)
    return out
def area(pts): return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
def inside(pt, poly):
    x, y = pt; c = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0): c = not c
    return c
SEC = {t: loops_of(p['shape']) for t, p in PARTS.items()}
SEC_GG = {n: loops_of(GG[n]) for n in ('Turbine', 'TurbineNut', 'NGV', 'Shaft', 'ShaftTunnel') if n in GG}
json.dump(dict(E3={t: v for t, v in SEC.items()}, GG=SEC_GG), open(os.path.join(OUT, 'E3_section_xy.json'), 'w'))
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.path import Path as MPath; from matplotlib.patches import PathPatch
    def patch(loops, color, alpha=0.85, lw=0.3):
        loops = sorted(loops, key=lambda l: -abs(area(l))); verts, codes = [], []
        for i, l in enumerate(loops):
            depth = sum(1 for o in loops[:i] if abs(area(o)) > abs(area(l)) and inside(l[0], o))
            ccw = area(l) > 0
            if (depth % 2 == 0) != ccw: l = l[::-1]
            verts += l + [l[0]]; codes += [MPath.MOVETO] + [MPath.LINETO] * (len(l) - 1) + [MPath.CLOSEPOLY]
        return PathPatch(MPath(verts, codes), fc=color, ec='k', lw=lw, alpha=alpha)
    fig, axs = plt.subplots(2, 1, figsize=(17, 17), gridspec_kw=dict(height_ratios=[1.45, 1]))
    for ax, (xl, yl) in zip(axs, (((95, 480), (-235, 335)), ((180, 300), (-2, 72)))):
        for n, lps in SEC_GG.items():
            if lps: ax.add_patch(patch(lps, '#bbbbbb', 0.9))
        for t, lps in SEC.items():
            if lps: ax.add_patch(patch(lps, COL[PARTS[t]['group']], 0.75 if PARTS[t]['group'] != 'hot' else 0.6))
        ax.set_xlim(*xl); ax.set_ylim(*yl); ax.set_aspect('equal'); ax.grid(alpha=0.25)
        ax.axhline(0, c='k', lw=0.5, ls='-.')
        ax.set_xlabel('ENG x [mm] (east, downstream)  -  ROOF X = 1.880 + x/1000'); ax.set_ylabel('ENG y [mm] (north)')
    A = axs[0]
    lab = [(150, 60, 'E3-101 interduct + NGV (SLM IN718)'), (209, 72, 'E3-103 FPT blisk (19)'), (236, 140, 'E3-102 shroud / diffuser W wall'),
           (262, 150, 'E3-110 collector drum'), (300, 270, 'H1: DN250 PN6 -> E4 recuperator (x 300, face y=+250, ROOF 8.100)'), (248, -40, 'B1 71905 hybrid (SFD)'),
           (344, -50, 'PMG 30 kW, 2-pole SmCo, 60k'), (430, -42, 'B2 7005 hybrid (SFD, preload)'), (318, 95, 'E3-112 support cone'),
           (440, 120, 'E3-307 terminal box'), (118, -95, 'E2/E3 flange x=116 (per E2)'), (110, 22, 'GG turbine + nut (E1)'), (225, -330, 'feet -> skid z=-400')]
    for x, y, s in lab:
        A.annotate(s, (x, y), fontsize=8, ha='center', bbox=dict(boxstyle='round,pad=0.2', fc='w', alpha=0.7))
    A.set_title('GR180-CCHP E3 - section z = 0 (ENG frame): interduct, FPT (NGV %d / rotor %d, 60k rpm, eta_ts %.3f), FPT/PMG rotor on B1/B2, '
                'PMG, exhaust collector; GG turbine/nut/NGV/shaft in grey' % (ZN, ZR, st['eta_ts']), fontsize=10)
    axs[1].set_title('detail: GG exit -> interduct -> NGV -> blisk -> axial-radial diffuser; heat shield, labyrinth, buffer annulus, B1 cartridge', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'E3_section.png'), dpi=110); plt.close(fig)
    say('section -> %s' % os.path.join(OUT, 'E3_section.png'))
except ImportError:
    say('no matplotlib in FreeCAD python - section_xy.json written only')

# =====================================================================================================================
# BOM (docs/06 §5 columns) with CAD masses
BOMF = os.path.join(ROOT, 'docs', 'bom', 'engine_E3_bom.csv'); os.makedirs(os.path.dirname(BOMF), exist_ok=True)
SUP = {
 'E3-101': ('make', 'SLM IN718 (iDesign3D, Tehran); stress relief + solution/age AMS 5662; flanges & seal lands machined 5-axis', 'iDesign3D (IR)', 'NGV %d vanes; integral stationary hub cone over the GG nut; 2 TC + 1 P boss' % ZN),
 'E3-102': ('make', 'IN718 ring (5-axis/turn) + IN625 1.5-3 mm radial wall, EB/TIG weld', 'local 5-axis shop; IN718 bar VDM Metals (DE) / GH4169 (CN)', 'tip gap 0.30 mm cold (0.35 at assembly, check growth)'),
 'E3-103': ('make', 'IN718 forged disc AMS 5662/5663 (VDM Metals DE, Aubert & Duval FR, GH4169 CN); 5-axis CNC; Hirth 24T; balance G1.0; spin test 78k', 'local 5-axis + balancing service', '%d blades; FPI + CMM; spin-pit proof test 78k rpm RT' % ZR),
 'E3-104': ('make', 'IN718, M10x1.25 RH, 15 AF, silver plated', 'local', 'drag tightens (CCW rotor seen from intake, nut at the west end)'),
 'E3-105': ('make', 'IN718 stud M10x1.25 rolled thread, stretch-controlled preload ~25 kN', 'local', ''),
 'E3-106': ('make', 'IN718, Hirth 24T, 4 labyrinth teeth r 14.0, slinger', 'local 5-axis/turn', 'heat dam between blisk and B1'),
 'E3-107': ('make', '1.4828 0.8 mm + ceramic paper 3 mm (Unifrax/Thermal Ceramics EU)', 'local sheet', ''),
 'E3-110': ('make', '1.4828/310S sheet 2.5-3 mm, TIG; DN250 PN6 flange 1.4541; hub bell spun', 'local fabrication (robotic weld OK)', 'insulate outside (E5): 610 C surface'),
 'E3-111': ('make', '1.4828 plate 6 mm laser + machined, 24 x M8 to drum flange', 'local', 'hot module (interduct+NGV+shroud) slides in from the west'),
 'E3-112': ('make', 'IN625 1.5 mm spun cone + flange, 6 windows; mica spacer 3 mm', 'local spinning', 'thermal barrier hot collector -> cold PMG housing; ~120 W'),
 'E3-113': ('buy', 'microporous insulation panel 6 mm + ceramic paper 3 mm (hub bell)', 'Promat (BE) / Morgan Thermal Ceramics (UK) / Chinese', ''),
 'E3-201': ('make', '34CrNiMo6 (1.6582) Q+T, CNC turn + cylindrical grind (h5, runout <= 3 um)', 'local', 'magnetic return path of the 2-pole rotor'),
 'E3-202': ('buy', 'Sm2Co17 Br >= 1.06 T, Hcj >= 1500 kA/m, 8 x 8 segments, parallel magnetised 2-pole', 'Vacuumschmelze VACOMAX 225 HR (DE); Ningbo Ninggang / Chengdu Galaxy (CN)', 'magnetise after assembly or assemble with fixture'),
 'E3-203': ('make', 'T700S-class carbon / high-Tg epoxy, hoop wound, 3 mm, 0.18 mm interference (press/thermal)', 'Toray T700S (JP) / Zhongfu SYT49 (CN); local filament winding', 'spin test with PM rotor 78k'),
 'E3-204': ('make', 'Ti-6Al-4V rings, bonded', 'local', ''),
 'E3-205': ('buy', B1['desig'], 'GMN (DE) HY series, Schaeffler FAG HCB71905 (DE), SKF 71905 CE/HCP4A (SE), ZYS H71905C (CN)', 'locating bearing; ~%.0f N axial' % br['Fa1']),
 'E3-206': ('buy', B2['desig'], 'GMN (DE), FAG HCB7005 (DE), SKF 7005 CE/HCP4A (SE), ZYS (CN)', 'floating, %.0f N spring preload; L10 %.0f h, Lnm ~%.0f h' % (br['Fa2'], br['L10h_2'], br['Lnm_2'])),
 'E3-207': ('make', '1.4542 (17-4PH H1150), SFD land OD 50 g5 (c 0.075), 2 FKM O-rings 2.62', 'local', 'O-ring centring ~2 N/um'),
 'E3-208': ('make', '1.4542 (17-4PH H1150), SFD land OD 55 g5', 'local', ''),
 'E3-209': ('buy', 'wave spring 17-7PH, 200 N at working height', 'TFC (UK) / Chinese wave-spring makers', ''),
 'E3-210': ('buy', 'precision locknut M20x1 KMT/KMD class', 'SKF (SE) / GMN (DE) / Chinese', ''),
 'E3-211': ('make', '1.4542 2-tooth target wheel', 'local', '2 ppr -> 2.0 kHz @ 60k (SE-002B)'),
 'E3-301': ('make', 'SLM 316L (3dfast) with oil/buffer galleries + jets, stress relieved, bores machined', '3dfast (IR)', 'labyrinth lands r 14.15, windback r 13.65, buffer annulus'),
 'E3-302': ('make', 'SLM AlSi10Mg (3dfast), internal helical channel 12x6 (6 turns), T6, bore for stator shrink fit', '3dfast (IR)', 'glycol 8 L/min; leak test 6 bar'),
 'E3-303': ('buy', '0.10 mm NO10 Si-steel laminations, laser/wire cut, bonded, 24 slots', 'JFE 10JNEX900 (JP), Baosteel B10AT (CN), Cogent (UK)', 'or Co-Fe (VACOFLUX 48, DE) for higher B'),
 'E3-304': ('make', 'Litz wire (e.g. 270 x 0.18 mm, ~7 mm2) class H, 2-layer lap 10/12, VPI + potting, 3 x PT1000', 'Elektrisola / Rudolf Pack (DE); local winding shop', 'or buy stator wound to spec (see doc)'),
 'E3-305': ('make', 'SLM 316L (3dfast), oil galleries, bores machined', '3dfast (IR)', ''),
 'E3-306': ('make', 'AlSi10Mg / 6082-T6, 2 x M12x1 sensor bosses', 'local', ''),
 'E3-307': ('buy', 'Al IP66 box + PEEK terminal board 3 x M8, M40 EMC gland, M12 8-pin RTD connector', 'Rittal/ Spelsberg (DE), Phoenix Contact (DE), Lapp (DE)', ''),
 'E3-401': ('make', '1.4828 flexure plate 8 mm + base 10 mm', 'local', 'axially compliant (+-2 mm)'),
 'E3-402': ('make', 'S355J2 plate 10 mm flexure + base, clamp band', 'local', ''),
 'E3-701': ('buy', '48 V EC radial blower 4 g/s @ 2 kPa + G4 filter', 'ebm-papst (DE) / Micronel (CH)', 'PMG gap cooling + seal pressurisation of the PMG cavity'),
}
for t in SENS:
    SUP[t] = ('buy', SENS[t]['desc'], 'Roessel / Electronic Sensor (DE), Jaquet / Baumer (CH), MMF (DE), Hansford (UK)', 'tag per docs/electrical/02_io_list')
EXTRA = [
 ('E3-601', 'flange gaskets (E2/E3, mid-flange, NGV/shroud, drum cover, H1)', 6, 'buy', 'KLINGER Milam PSS 1 mm (mica) / Thermiculite 815', 'per flange', 'Klinger (AT) / Flexitallic (UK)', 0.30, '', ''),
 ('E3-602', 'hot bolting M5/M6/M8/M16 + nuts (incl. E2/E3 flange 16 x M8 x 45 per E2)', 144, 'buy', '1.4980 (A286-equiv.) / IN718 studs, silver-plated nuts', 'M5-M16', 'Boellhoff (DE) / Chinese GH2132', 1.7, '', 'torque per VDI 2230 (calc pending)'),
 ('E3-603', 'cold bolting (PMG/B1/B2/cover/box/feet)', 60, 'buy', 'A4-70 / 8.8 Zn-flake', 'M5-M12', 'Wuerth (DE)', 0.6, '', ''),
 ('E3-604', 'FKM O-rings (SFD centring 4, housings/ports 12)', 16, 'buy', 'FKM 75 Sh A, 200 C', 'various', 'Freudenberg (DE) / Trelleborg (SE)', 0.05, '', 'replace at bearing overhaul'),
 ('E3-605', 'E2/E3 flange gasket (mean dia 137 x 8 wide, per E2 flange calc)', 1, 'buy', 'KLINGER Milam PSS 1 mm (mica) / Thermiculite 815', 'ID 129 / OD 145', 'Klinger (AT) / Flexitallic (UK)', 0.01, '', 'slip-joint piston ring is E2 scope (E2 rear-ring groove x 112.5-114.5)'),
 ('E3-606', 'buffer-air orifice 2.4 mm + 40 um filter + check valve', 1, 'buy', 'SS316', '1/4" tube', 'Hy-Lok (KR) / Voss (DE)', 0.15, '', 'from E2 compressor-delivery port'),
 ('E3-607', 'oil fittings + tubes (2 supply, 2 scavenge, 2 buffer)', 1, 'buy', 'SS316 compression fittings, 6/12 mm tube', '', 'Hy-Lok (KR) / Voss (DE) / Dk-Lok (KR)', 0.8, '', 'routed through cone windows (B1)'),
 ('E3-608', 'glycol fittings G1/2 + hose', 2, 'buy', 'brass/SS, EPDM hose', 'G1/2', 'Voss (DE) / Gates EU', 0.3, '', ''),
 ('E3-609', 'phase leads + PT1000 harness inside PMG', 1, 'buy', 'silicone/PTFE 16 mm2 class H, PT1000 3-wire', '', 'Lapp (DE) / HELUKABEL (DE)', 0.4, '', ''),
 ('E3-610', 'external insulation blanket collector + interduct (E5 scope, listed for mass)', 1, 'buy', 'removable blanket, silica fabric + 50 mm', '', 'EU/Chinese', 4.0, '', 'surface < 60 C in the enclosure'),
 ('E3-611', 'balancing / spin-test / NDT services (blisk, PM rotor, assembled rotor)', 1, 'buy', 'G1.0 two-plane balance; spin pit 78k; FPI; CMM', '', 'Schenck RoTec (DE) / local service', 0, '', 'see doc section spin test'),
]
with open(BOMF, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes'])
    for t, p in PARTS.items():
        mb, spec, supl, note = SUP.get(t, ('make', p['mat'], 'local', ''))
        bbx = p['shape'].BoundBox
        w.writerow([t, p['name'].replace('_', ' '), 1, mb, spec if mb == 'make' else p['mat'], '%.0f x %.0f x %.0f mm' % (bbx.XLength, bbx.YLength, bbx.ZLength),
                    supl, round(p['shape'].Volume * p['rho'], 3), 'cad_out/engine/E3/%s_%s.step' % (t, p['name']), note])
    for r_ in EXTRA: w.writerow(r_)
say('BOM -> %s (%d rows)' % (BOMF, len(PARTS) + len(EXTRA)))
tot = sum(p['shape'].Volume * p['rho'] for p in PARTS.values()) + sum(r_[7] for r_ in EXTRA)
say('E3 total mass (models + listed extras) %.1f kg' % tot)
open(os.path.join(OUT, 'E3_build.log'), 'w').write('\n'.join(log))
