# GR180 variant B (GR180-STEAM) subsystem E3-B - compact exhaust collector for the simple-cycle gas section (generator 1).
# Scripted parametric FreeCAD model (Part workbench), ENG frame (mm): x downstream (east), y north, z up; x = 0 tunnel front.
# Replaces (variant B only) the variant-A collector E3-110/111/112/113, front foot E3-401 and exit sensors E3-504/505/506.
# All other E3 parts (cad_out/engine/E3/E3-*.step: interduct+NGV, shroud + radial-diffuser west wall, rotor, bearings, PMG,
# rear foot E3-402) are used unchanged; variant-A files (cad/engine/*, sim/engine/*, docs/engine/*) are not touched.
# Geometry comes from the design calculation (single source of truth):
#     python3 sim/variant_b/e3b_exhaust_calc.py        -> sim/variant_b/e3b_exhaust_results.json ('design' block)
# Run:
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/variant_b/e3b_exhaust.py
# Outputs (cad_out/variant_b/E3B/): E3B-xxx_<name>.step per part, E3B_assembly.step (new parts, ENG), E3B_full_E3_assembly.step
#     (kept E3 parts + E3-B, ENG), E3B_assembly.FCStd, E3B_interfaces.json, E3B_checks.json (interference report),
#     E3B_section.png (y = 0 and x = outlet-axis sections); docs/bom/variant_b_e3b_bom.csv.
# Parts: E3B-110 collector body (box + hood + DN200 stub + flange + lugs, welded), E3B-111 west cover (2 halves),
#     E3B-112 rear unit (spun hub bell + disc + IN625 cone, welded), E3B-113 rear heat shield, E3B-114 insulation jacket,
#     E3B-401 front support (portal plate, centre-line lugs), E3B-504/505/506 TE-505A/B + PT-525 on the outlet stub.
import FreeCAD as App, Part, os, json, math, sys, csv
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles', False)
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'sim', 'variant_b', 'e3b_exhaust_results.json')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.environ.get('GR180_EXH_OUT') or os.path.join(ROOT, 'cad_out', 'variant_b', 'E3B'); os.makedirs(OUT, exist_ok=True)   # variant C: own folder
E3_DIR = os.path.join(ROOT, 'cad_out', 'engine', 'E3')
E2B_DIR = os.path.join(ROOT, 'cad_out', 'variant_b', 'E2B')
GG_ASM = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
RS = json.load(open(os.environ.get('GR180_EXH_JSON') or os.path.join(ROOT, 'sim', 'variant_b', 'e3b_exhaust_results.json')))
D = RS['design']
CR = json.load(open(os.path.join(E3_DIR, 'E3_calc_results.json')))
GEO, X = CR['geometry']['GEO'], CR['geometry']['X']
ROOF0 = (1880.0, 7850.0, 600.0)
def roof(p): return [round((ROOF0[0] + p[0]) / 1000, 4), round((ROOF0[1] + p[1]) / 1000, 4), round((ROOF0[2] + p[2]) / 1000, 4)]
log = []
def say(*a):
    s = ' '.join(str(v) for v in a); print(s); log.append(s); sys.stdout.flush()

# ---------------------------------------------------------------- helpers (style of cad/engine/fpt_pmg.py)
def P(x, r, th_deg):                                   # polar point about the x axis; theta from +y toward +z
    t = math.radians(th_deg); return V(x, r * math.cos(t), r * math.sin(t))
def rdir(th_deg):
    t = math.radians(th_deg); return V(0, math.cos(t), math.sin(t))
def rv(pts):
    w = Part.makePolygon([V(x, r, 0) for x, r in pts] + [V(pts[0][0], pts[0][1], 0)])
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)
def ring(x0, x1, ri, ro):
    c = Part.makeCylinder(ro, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return c.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), V(1, 0, 0))) if ri > 0 else c
def offset_curve(pts, d):
    out = []
    for i, (x, r) in enumerate(pts):
        a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
        tx, tr = b[0] - a[0], b[1] - a[1]; n = math.hypot(tx, tr); out.append((x - tr / n * d, r + tx / n * d))
    return out
def arc(cx, cr, R, a0, a1, n=24):
    return [(cx + R * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cr + R * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
def box(x0, x1, y0, y1, z0, z1): return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def zcyl(cx, cy, r, z0, z1): return Part.makeCylinder(r, z1 - z0, V(cx, cy, z0), V(0, 0, 1))
def section_yz(hy, z_top, z_bot, Rc):
    """y-z outline of the box: flat top at z_top (open into the hood), sides y = +-hy, bottom z_bot with corner radius Rc"""
    pts = [V(0, -hy, z_top), V(0, -hy, z_bot + Rc)]
    for k in range(1, 9): a = math.radians(180 + 90 * k / 8); pts.append(V(0, -hy + Rc + Rc * math.cos(a), z_bot + Rc + Rc * math.sin(a)))
    pts.append(V(0, hy - Rc, z_bot))
    for k in range(1, 9): a = math.radians(270 + 90 * k / 8); pts.append(V(0, hy - Rc + Rc * math.cos(a), z_bot + Rc + Rc * math.sin(a)))
    pts += [V(0, hy, z_top), V(0, -hy, z_top)]
    return Part.Face(Part.makePolygon(pts))
NPHI = 96
def phis(hx, hy):
    s = sorted(set([2 * math.pi * k / NPHI for k in range(NPHI)] + [a % (2 * math.pi) for a in
               (math.atan2(hy, hx), math.atan2(hy, -hx), math.atan2(-hy, -hx), math.atan2(-hy, hx))]))
    return s
def rect_wire(cx, z, hx, hy, ph):                     # rectangle sampled at the polar angles ph (x-y plane, about (cx, 0))
    pts = []
    for p in ph:
        c, s_ = math.cos(p), math.sin(p)
        t = min(hx / abs(c) if abs(c) > 1e-12 else 1e9, hy / abs(s_) if abs(s_) > 1e-12 else 1e9)
        pts.append(V(cx + t * c, t * s_, z))
    return Part.makePolygon(pts + [pts[0]])
def circ_wire(cx, z, R, ph):
    pts = [V(cx + R * math.cos(p), R * math.sin(p), z) for p in ph]
    return Part.makePolygon(pts + [pts[0]])
def hood_solid(cx, z0, z1, hx, hy, R):
    ph = phis(hx, hy)
    return Part.makeLoft([rect_wire(cx, z0, hx, hy, ph), circ_wire(cx, z1, R, ph)], True, True)

PARTS = {}
def add(tag, name, shp, mat, rho, group):
    PARTS[tag] = dict(name=name, shape=shp, mat=mat, rho=rho, group=group)
    say('  %-8s %-30s valid %-5s solids %2d  vol %11.0f mm3  mass %7.3f kg' % (tag, name, shp.isValid(), len(shp.Solids), shp.Volume, shp.Volume * rho))
RHO = dict(S1_4828=7.80e-6, IN625=8.44e-6, S355=7.85e-6, ins=0.30e-6, paper=0.25e-6, misc=3.0e-6, S1_4541=7.90e-6)

# =====================================================================================================================
a, t, Rc = D['a_inner'], D['sheet_t'], D['corner_R_inner']
XI0, XI1, XW0, XE1, XC = D['x_in0'], D['x_in1'], D['x_wp0'], D['x_ep1'], D['x_outlet']
pp = D['pipe']; R_ID, R_OD = pp['ID'] / 2, pp['OD'] / 2
ZH0, ZH1, ZF0, ZF1 = D['z_hood0'], D['z_hood1'], D['z_flange0'], D['z_flange1']
T_INS = D['insulation']['t']
say('E3-B build: box inner %.0f x %.0f (x %.0f..%.0f), DN%d outlet axis x %.1f, hood z %.0f..%.0f, flange face z %.0f, insulation %.0f mm'
    % (2 * a, 2 * a, XI0, XI1, D['DN'], XC, ZH0, ZH1, ZF1, T_INS))

# ---------------------------------------------------------------- E3B-110 collector body (welded: U-shell + 2 end plates + hood + stub + flange + lugs)
sec_o = section_yz(a + t, ZH0, -(a + t), Rc + t); sec_i = section_yz(a, ZH0, -a, Rc)        # cavity solids share faces exactly (coplanar offsets break the boolean)
box_o = sec_o.extrude(V(XE1 - XW0, 0, 0)); box_o.translate(V(XW0, 0, 0))
box_i = sec_i.extrude(V(XI1 - XI0, 0, 0)); box_i.translate(V(XI0, 0, 0))
hood_o = hood_solid(XC, ZH0, ZH1, 0.5 * (XE1 - XW0), a + t, R_OD)
hood_i = hood_solid(XC, ZH0, ZH1, 0.5 * (XI1 - XI0), a, R_ID)
stub_o = zcyl(XC, 0, R_OD, ZH1, ZF0); stub_i = zcyl(XC, 0, R_ID, ZH1, ZF1 + 1)
flg = zcyl(XC, 0, pp['fl_OD'] / 2, ZF0, ZF1)
for k in range(pp['n']):                               # bolt holes straddle the x / y centre lines
    th = math.radians(180.0 / pp['n'] + 360.0 * k / pp['n'])
    flg = flg.cut(zcyl(XC + pp['fl_PCD'] / 2 * math.cos(th), pp['fl_PCD'] / 2 * math.sin(th), pp['hole'] / 2, ZF0 - 1, ZF1 + 1))
body = box_o.fuse([hood_o, stub_o]).cut(box_i.fuse([hood_i, stub_i])).fuse(flg.cut(stub_i))
# west end plate opening (hot module passes, cover closes it), east end plate opening (rear unit / cold cartridge)
body = body.cut(Part.makeCylinder(D['wp_open_r'], t + 2, V(XW0 - 1, 0, 0), V(1, 0, 0)))
body = body.cut(Part.makeCylinder(D['ep_open_r'], t + 2, V(XI1 - 1, 0, 0), V(1, 0, 0)))
# studs (captive, A286-class M8): west plate -> through the cover (west), east plate -> through the rear disc (east)
cb, db = D['cover_bolts'], D['disc_bolts']
studs = [Part.makeCylinder(4.0, 17.0, P(XW0 - 17.0, cb['PCD'] / 2, cb['phase'] + 360.0 / cb['n'] * k), V(1, 0, 0)) for k in range(cb['n'])]
studs += [Part.makeCylinder(4.0, 16.0, P(XE1, db['PCD'] / 2, db['phase'] + 360.0 / db['n'] * k), V(1, 0, 0)) for k in range(db['n'])]
# centre-line support lugs (10 mm, bottom face on the axis plane z = 0), slotted M12 hole in y
S_ = D['support']; LW, LT = S_['lug_w'], S_['lug_t']
LEG_Y0 = a + t + T_INS + 6.0; LEG_Y1 = LEG_Y0 + 30.0; LUG_Y1 = LEG_Y1 + 6.0
lugs = []
for sy in (1, -1):
    lg = box(XC - LW / 2, XC + LW / 2, min(sy * (a + t - 1.0), sy * LUG_Y1), max(sy * (a + t - 1.0), sy * LUG_Y1), 0.0, LT)
    yc = sy * 0.5 * (LEG_Y0 + LEG_Y1)
    slot = zcyl(XC, yc - 5.0, 6.5, -1, LT + 1).fuse([zcyl(XC, yc + 5.0, 6.5, -1, LT + 1), box(XC - 6.5, XC + 6.5, yc - 5.0, yc + 5.0, -1, LT + 1)])
    lugs.append(lg.cut(slot))
# drain boss G1/2 at the bottom centre
drain = zcyl(XC, 0, 12.0, -(a + t) - 15.0, -(a + t) + 0.5).cut(zcyl(XC, 0, 7.0, -(a + t) - 16.0, -a + 1))
# exit sensor bosses on the stub (TE-505A +y, TE-505B -y, PT-525 +x) - long nipples through the insulation
SZ = D['sensors']['z']; RB1 = D['sensors']['boss_r1']
SEN = [('E3B-504', 'TE-505A_FPT_exit_TOT', 90.0, 8.0, 1.6), ('E3B-505', 'TE-505B_FPT_exit_TOT', 270.0, 8.0, 1.6), ('E3B-506', 'PT-525_FPT_exit_tap', 0.0, 6.0, 0.8)]
def sdir(az): return V(math.cos(math.radians(az)), math.sin(math.radians(az)), 0)
def spt(az, r): d = sdir(az); return V(XC + r * d.x, r * d.y, SZ)
bosses = [Part.makeCylinder(rb, RB1 - (R_OD - 1.0), spt(az, R_OD - 1.0), sdir(az)) for _, _, az, rb, _ in SEN]
body = body.fuse(studs + lugs + [drain] + bosses)
body = body.cut(Part.makeCompound([Part.makeCylinder(bo, RB1 - R_ID + 5, spt(az, R_ID - 2.0), sdir(az)) for _, _, az, _, bo in SEN]))
body = body.removeSplitter()
add('E3B-110', 'Collector_Body', body, '1.4828 sheet 3 mm (U-shell + end plates + rect-to-round hood), DN200 219.1x3 stub, PN6 flange 1.4541; TIG/robot', RHO['S1_4828'], 'hot')

# ---------------------------------------------------------------- E3B-111 west cover, 2 halves (horizontal split z = 0)
X_C0 = D['x_cover0']; T_C = D['t_cover']
cov = ring(X_C0, X_C0 + T_C, D['cover_ID'] / 2, D['cover_OD'] / 2)
mb = D['mid_flange_bolts']
for k in range(mb['n']): cov = cov.cut(Part.makeCylinder(mb['hole'] / 2, T_C + 2, P(X_C0 - 1, mb['PCD'] / 2, mb['phase'] + 360.0 / mb['n'] * k), V(1, 0, 0)))
for k in range(cb['n']): cov = cov.cut(Part.makeCylinder(cb['hole'] / 2, T_C + 2, P(X_C0 - 1, cb['PCD'] / 2, cb['phase'] + 360.0 / cb['n'] * k), V(1, 0, 0)))
cov = cov.cut(box(X_C0 - 1, X_C0 + T_C + 1, -200, 200, -0.5, 0.5))
add('E3B-111', 'West_Cover_2halves', cov, '1.4828 plate 5 mm, laser cut, split at z = 0 (mica strip + 2 straps), 12 x M6 to the E3-101 mid flange', RHO['S1_4828'], 'hot')

# ---------------------------------------------------------------- E3B-112 rear unit: spun hub bell (= diffuser east wall) + 4 mm disc + IN625 cone -> PMG flange
bl = D['bell']; XD0 = D['x_rad_e']; TD = D['disc_t']
gas_hb = [(bl['x0'], bl['r0'])] + arc(bl['x0'], bl['r0'] + bl['R'], bl['R'], -90, 0, 18)[1:] + [(XD0, 66.0)]
bell = rv(gas_hb + offset_curve(gas_hb, -bl['t'])[::-1])
disc = ring(XD0, XD0 + TD, 60.0, D['disc_OD'] / 2)
for k in range(db['n']): disc = disc.cut(Part.makeCylinder(db['hole'] / 2, TD + 2, P(XD0 - 1, db['PCD'] / 2, db['phase'] + 360.0 / db['n'] * k), V(1, 0, 0)))
cn = D['cone']
cone = rv([(cn['x0'], cn['r0'] - 1.5), (cn['x0'], cn['r0']), (cn['flange'][0], cn['r1']), (cn['flange'][0], cn['r1'] - 1.5)])
XWIN = 0.5 * (cn['x0'] + cn['flange'][0])
for k in range(cn['windows']):                         # 6 windows (B1 oil / scavenge / buffer air / RTD lines leave radially)
    cone = cone.cut(Part.makeCylinder(13.0, 60, P(XWIN, 70.0, 30 + 60 * k), rdir(30 + 60 * k)))
cfl = ring(cn['flange'][0], cn['flange'][1], cn['flange'][2], cn['flange'][3])
for k in range(12): cfl = cfl.cut(Part.makeCylinder(2.75, 6, P(cn['flange'][0] - 1, 80.0, 30.0 * k), V(1, 0, 0)))
rear = bell.fuse([disc, cone, cfl]).removeSplitter()
add('E3B-112', 'Rear_Unit_Bell_Disc_Cone', rear, 'bell 1.4828 2.5 mm spun + disc 1.4828 4 mm laser + cone IN625 1.5 mm spun (6 windows), TIG; mica 3 mm at the PMG flange',
    RHO['S1_4828'], 'hot')

# ---------------------------------------------------------------- E3B-113 rear heat shield (disc east face, facing the PMG front wall)
hs = D['heat_shield']
shield = ring(hs['x0'], hs['x0'] + hs['t'], hs['r0'], hs['r1'])
for th in (45.0, 90.0, 180.0, 270.0):                  # notches round the PMG front-wall port bosses (x 266)
    shield = shield.cut(Part.makeCylinder(10.5, 60, P(266.0, 55.0, th), rdir(th)))
add('E3B-113', 'Rear_HeatShield', shield, 'ceramic-fibre paper 2.5 mm + 0.1 mm 1.4828 foil, clipped to the rear disc', RHO['paper'], 'hot')

# ---------------------------------------------------------------- E3B-401 front support: laser-cut portal plate (y-z plane) + pads + base
XS0, XS1 = XC - S_['plate_t'] / 2, XC + S_['plate_t'] / 2; ZSK = S_['z_skid']
portal = box(XS0, XS1, -LEG_Y1, LEG_Y1, ZSK + 10, -10.0).cut(box(XS0 - 1, XS1 + 1, -LEG_Y0, LEG_Y0, S_['web_z'][1], 0.0))
pads = [box(XC - LW / 2, XC + LW / 2, LEG_Y0, LEG_Y1, -10.0, 0.0), box(XC - LW / 2, XC + LW / 2, -LEG_Y1, -LEG_Y0, -10.0, 0.0)]
pads = [p_.cut(zcyl(XC, sy * 0.5 * (LEG_Y0 + LEG_Y1), 5.0, -11, 1)) for p_, sy in zip(pads, (1, -1))]   # M12 tapped (drill 10.2)
base = box(XC - 30.0, XC + 30.0, -(LEG_Y1 + 10), LEG_Y1 + 10, ZSK, ZSK + 10)
for sy in (1, -1):
    for sx in (-18.0, 18.0):
        yb = sy * (LEG_Y1 - 8.0)
        base = base.cut(zcyl(XC + sx, yb - 6, 6.5, ZSK - 1, ZSK + 11).fuse([zcyl(XC + sx, yb + 6, 6.5, ZSK - 1, ZSK + 11), box(XC + sx - 6.5, XC + sx + 6.5, yb - 6, yb + 6, ZSK - 1, ZSK + 11)]))
sup = portal.fuse(pads + [base]).removeSplitter()
add('E3B-401', 'Front_Support_Portal', sup, 'S355J2 / 1.4301 plate 8 mm laser-cut portal (axially compliant) + 2 pads 10 mm + base 10 mm; mica/Monolux washers under the lugs',
    RHO['S355'], 'support')

# ---------------------------------------------------------------- E3B-504/505/506 exit sensors (envelopes)
SENS = {}
for tg, nm, az, rb, bo in SEN:
    r_tip = R_ID - D['sensors']['immersion']
    if tg != 'E3B-506':
        s_ = Part.makeCylinder(1.5, RB1 - r_tip, spt(az, r_tip), sdir(az)).fuse(Part.makeCylinder(8.0, 22.0, spt(az, RB1), sdir(az)))
        desc = 'type K class 1, MI 3 mm Inconel 600, ungrounded, immersion 60 mm, compression fitting on a 1/2" nipple (TOT = HRSG inlet)'
    else:
        s_ = Part.makeCylinder(3.0, 22.0, spt(az, RB1), sdir(az))
        desc = 'static tap 1.6 mm + 1/4" tube to PT-525 (FPT exit / HRSG inlet static, 0-1.2 bar abs or dp to ambient)'
    p_ = spt(az, RB1 if tg == 'E3B-506' else r_tip); d_ = sdir(az)
    SENS[tg] = dict(name=nm, desc=desc, pos=[round(p_.x, 1), round(p_.y, 1), round(p_.z, 1)], dir=[round(-d_.x, 3), round(-d_.y, 3), 0.0])
    add(tg, nm, s_, desc, RHO['misc'], 'sensor')

# ---------------------------------------------------------------- E3B-114 insulation jacket (removable cassettes, microporous)
TI = T_INS
X_IW0 = X['flangeE2'] + 0.5                            # 116.5 (E2-B face x 115 + gasket)
X_IE1 = XE1 + TI                                       # east slab
jb = section_yz(a + t + TI, ZH0, -(a + t + TI), Rc + t + TI).extrude(V(X_IE1 - X_IW0, 0, 0)); jb.translate(V(X_IW0, 0, 0))
jh = hood_solid(XC, ZH0, ZH1, 0.5 * (XE1 - XW0) + TI, a + t + TI, R_OD + TI)
js = zcyl(XC, 0, R_OD + TI, ZH1, ZF0 - 35.0)
jk = jb.fuse([jh, js])
cuts = [box_o, hood_o, stub_o, zcyl(XC, 0, R_OD + 0.2, ZH1 - 1, ZF1 + 1),
        Part.makeCylinder(92.0, X_C0 - X_IW0 + 1, V(X_IW0 - 0.5, 0, 0), V(1, 0, 0)),                 # porch round the interduct / TCs
        Part.makeCylinder(D['cover_OD'] / 2 + 8, XW0 - 133.0 + 0.5, V(133.0, 0, 0), V(1, 0, 0)),      # cover rim + stud nuts
        Part.makeCylinder(D['disc_OD'] / 2 + 6, 270.0 - XE1, V(XE1 - 0.5, 0, 0), V(1, 0, 0)),           # rear disc + nuts
        Part.makeCylinder(122.0, X_IE1 - XE1 + 2, V(XE1 - 1, 0, 0), V(1, 0, 0))]                       # cone / PMG
cuts += [box(XC - LW / 2 - 2, XC + LW / 2 + 2, -LUG_Y1 - 1, LUG_Y1 + 1, -2.0, LT + 2.0)]               # lugs
cuts += [zcyl(XC, 0, 14.0, -(a + t) - TI - 1, -(a + t) + 1)]                                          # drain
cuts += [Part.makeCylinder(rb + 2.0, RB1 - R_OD + 30, spt(az, R_OD - 1), sdir(az)) for _, _, az, rb, _ in SEN]
jk = jk.cut(Part.makeCompound(cuts)).removeSplitter()
add('E3B-114', 'Insulation_Jacket', jk, 'microporous %.0f mm (Promat MICROTHERM / Morgan WDS class) in 0.5 mm 1.4301 cassettes, 4 pieces + hood/stub cuffs' % TI, RHO['ins'], 'insulation')

# =====================================================================================================================
# checks: vs kept E3 parts, vs the v13A core (kept parts, x < 200 region), vs E2-B; internal E3-B
def overlap(a_, b_):
    if not a_.BoundBox.intersect(b_.BoundBox): return 0.0
    try: return a_.common(b_).Volume
    except Exception: return -1.0
def load_dir(dr, skip=()):
    out = {}
    if not os.path.isdir(dr): return out
    for f in sorted(os.listdir(dr)):
        if f.endswith('.step') and 'assembly' not in f and not any(f.startswith(s) for s in skip):
            s = Part.Shape(); s.read(os.path.join(dr, f)); out[f[:-5]] = s
    return out
REPLACED = ('E3-110', 'E3-111', 'E3-112', 'E3-113', 'E3-401', 'E3-504', 'E3-505', 'E3-506')
KEPT = load_dir(E3_DIR, REPLACED)
CORE_REPLACED_BY_E2B = ('Casing', 'CC_', 'GasBulkhead', 'Igniter', 'SupplyLines', 'SupplySeals', 'Exhaust', 'EGT_Probe', 'Fasteners')
CORE = load_dir(GG_ASM, CORE_REPLACED_BY_E2B)
E2B = load_dir(E2B_DIR)
say('loaded kept E3 %d, core %d, E2-B %d parts' % (len(KEPT), len(CORE), len(E2B)))
chk = dict(threshold_mm3=1.0, replaced_E3=list(REPLACED), core_skipped_replaced_by_E2B=list(CORE_REPLACED_BY_E2B),
           vs_kept_E3={}, vs_core={}, vs_E2B={}, internal=[], contacts_mm={}, clearances_mm={})
for grp, lib in (('vs_kept_E3', KEPT), ('vs_core', CORE), ('vs_E2B', E2B)):
    n = 0
    for t_, p_ in PARTS.items():
        for nm, s in lib.items():
            v = overlap(p_['shape'], s)
            if v > chk['threshold_mm3'] or v < 0:
                chk[grp]['%s / %s' % (t_, nm)] = round(v, 2); n += 1
    say('E3-B %s: %d overlaps > 1 mm3 %s' % (grp, n, chk[grp] if n else ''))
tags = sorted(PARTS)
for i, a_ in enumerate(tags):
    for b_ in tags[i + 1:]:
        v = overlap(PARTS[a_]['shape'], PARTS[b_]['shape'])
        if v > 1.0 or v < 0: chk['internal'].append(dict(a=a_, b=b_, vol_mm3=round(v, 2)))
say('E3-B internal overlaps > 1 mm3: %d %s' % (len(chk['internal']), chk['internal'][:6]))
def dist(s1, s2):
    try: return round(s1.distToShape(s2)[0], 3)
    except Exception: return -1
K = lambda pre: [s for n, s in KEPT.items() if n.startswith(pre)][0]
for what, s1, s2 in (('blisk / hub bell (rear rim seal)', K('E3-103'), rear), ('B1 housing / hub bell', K('E3-301'), rear),
                     ('PMG housing / rear disc+cone', K('E3-302'), rear), ('PMG housing / heat shield', K('E3-302'), shield),
                     ('shroud+diffuser W wall / box body', K('E3-102'), body), ('interduct module / west cover', K('E3-101'), cov),
                     ('interduct module / box body', K('E3-101'), body), ('terminal box / insulation', K('E3-307'), jk),
                     ('rear foot / insulation', K('E3-402'), jk), ('body / rear unit (gasket gap)', body, rear),
                     ('body / west cover (gasket gap)', body, cov), ('lug / pad (bearing contact)', body, sup)):
    chk['clearances_mm'][what] = dist(s1, s2)
for nm, s in E2B.items():
    d_ = dist(s, jk);
    if 0 <= d_ < 30: chk['clearances_mm']['E2B %s / insulation' % nm] = d_
say('clearances (mm): ' + ', '.join('%s %.2f' % kv for kv in chk['clearances_mm'].items()))

# =====================================================================================================================
# envelope / mass: old E3 (all parts) vs variant-B E3 (kept + E3-B)
def bb_of(shapes):
    c = Part.makeCompound(list(shapes)); b = c.BoundBox
    return [[round(b.XMin, 1), round(b.YMin, 1), round(b.ZMin, 1)], [round(b.XMax, 1), round(b.YMax, 1), round(b.ZMax, 1)]]
OLD_ALL = load_dir(E3_DIR)
old_coll = [s for n, s in OLD_ALL.items() if n.startswith(('E3-110', 'E3-111', 'E3-112', 'E3-113', 'E3-401'))]
new_coll = [PARTS[t_]['shape'] for t_ in ('E3B-110', 'E3B-111', 'E3B-112', 'E3B-401')]
metal_new = [p_['shape'] for t_, p_ in PARTS.items() if p_['group'] != 'insulation']
env = dict(old_E3_all=bb_of(OLD_ALL.values()), new_E3_kept_plus_E3B_metal=bb_of(list(KEPT.values()) + metal_new),
           new_E3_kept_plus_E3B_with_insulation=bb_of(list(KEPT.values()) + [p_['shape'] for p_ in PARTS.values()]),
           old_collector_parts=bb_of(old_coll), new_collector_parts_metal=bb_of(new_coll),
           new_collector_with_insulation=bb_of(new_coll + [jk]))
mass_new = {t_: p_['shape'].Volume * p_['rho'] for t_, p_ in PARTS.items()}
chk['envelope_ENG_mm'] = env; chk['mass_kg'] = {k: round(v, 3) for k, v in mass_new.items()}
for k, v in env.items(): say('bbox %-40s x %7.1f..%7.1f  y %7.1f..%7.1f  z %7.1f..%7.1f' % (k, v[0][0], v[1][0], v[0][1], v[1][1], v[0][2], v[1][2]))
say('E3-B mass: metal %.1f kg (+ insulation %.1f kg, sensors %.2f kg)' % (sum(v for t_, v in mass_new.items() if PARTS[t_]['group'] not in ('insulation', 'sensor')),
    mass_new['E3B-114'], sum(v for t_, v in mass_new.items() if PARTS[t_]['group'] == 'sensor')))
json.dump(chk, open(os.path.join(OUT, 'E3B_checks.json'), 'w'), indent=1)

# =====================================================================================================================
# exports
for t_, p_ in PARTS.items():
    p_['shape'].exportStep(os.path.join(OUT, '%s_%s.step' % (t_, p_['name'])))
Part.makeCompound([p_['shape'] for p_ in PARTS.values()]).exportStep(os.path.join(OUT, 'E3B_assembly.step'))
full = Part.makeCompound(list(KEPT.values()) + [p_['shape'] for p_ in PARTS.values()])
full.exportStep(os.path.join(OUT, 'E3B_full_E3_assembly.step'))
fr = full.copy(); fr.translate(V(*ROOF0)); fr.exportStep(os.path.join(OUT, 'E3B_full_E3_assembly_ROOF.step'))
doc = App.newDocument('E3B_exhaust')
for t_, p_ in PARTS.items():
    o = doc.addObject('Part::Feature', t_.replace('-', '_')); o.Shape = p_['shape']; o.Label = '%s %s' % (t_, p_['name'])
for n, s in KEPT.items():
    o = doc.addObject('Part::Feature', n.split('_')[0].replace('-', '_')); o.Shape = s; o.Label = n
doc.recompute(); doc.saveAs(os.path.join(OUT, 'E3B_assembly.FCStd'))

# =====================================================================================================================
# interfaces
sel = RS['selected']; fp = RS['fpt']['B_new_E3B']
def itf(name, pos, direction, size, counterpart, **kw):
    d = dict(name=name, ENG_mm=[round(v, 2) for v in pos], ROOF_m=roof(pos), direction=direction, size=size, counterpart=counterpart); d.update(kw); return d
IF = [
 itf('H1-B exhaust outlet (to stack / HRSG)', [XC, 0, ZF1], [0, 0, 1],
     'DN%d PN6 EN 1092-1 type 01 plate flange (OD %.0f, PCD %.0f, %d x %s, holes %.0f, straddling x/y), face z = %.0f; pipe %.1f x %.1f 1.4828; '
     'gas %.3f kg/s, %.0f C, %.3f m3/s, V %.1f m/s, static %.0f Pa abs (%.2f %% above site ambient %.0f Pa)'
     % (D['DN'], pp['fl_OD'], pp['fl_PCD'], pp['n'], pp['bolt'], pp['hole'], ZF1, pp['OD'], pp['t'], RS['inputs']['mg_B_kg_s'], RS['inputs']['T_exh_C'],
        sel['Q_m3s'], sel['V5'], fp['p5_Pa'], 100 * (fp['p5_Pa'] / RS['inputs']['Pa_site_Pa'] - 1), RS['inputs']['Pa_site_Pa']),
     'B-HRSG inlet duct / temporary stack: DN200 bellows (axial +-10, lateral +-5 mm) directly on this flange; the E3-B stub top grows '
     '+%.1f mm up when hot; no duct loads on the flange (duct supported from the roof/HRSG)' % RS['thermal']['growth_mm']['stub_top_vs_axis'],
     gasket='Thermiculite 815 / Klinger Milam PSS DN200 PN6 ring, 1.5 mm', bolting='8 x M16 x 70 1.4980/A286-class studs + nuts'),
 itf('West cover <-> E3-101 interduct mid flange', [D['x_cover0'], 0, 0], [-1, 0, 0],
     '12 x M6 (PCD 132, phase 15 deg) into the tapped E3-101 mid flange (x 139-145); cover 2 halves 5 mm, ID 85', 'E3-101 (unchanged)'),
 itf('Rear unit flange <-> PMG housing flange', [cn['flange'][1], 0, 0], [1, 0, 0],
     '12 x M5 (r 80, phase 0) through the IN625 cone flange x 333-336 into the E3-302 flange x 336-342; mica spacer 3 mm', 'E3-302 (unchanged)',
     heat_to_glycol_W=round(RS['thermal']['Q_to_glycol_total_W'])),
 itf('Front support (centre-line lugs)', [XC, 0, S_['z_skid']], [0, 0, -1],
     'portal plate base 60 x %.0f x 10, 4 x slotted M12 (y +-%.0f, x +-18); lugs rest on the pads at z = 0 (axis plane), 1 x M12 per side in a y-slot' % (2 * (LEG_Y1 + 10), LEG_Y1 - 8),
     'E5 skid (top assumed ENG z -400 = ROOF Z 0.200 as variant A); axial fixed point of the engine = E2-B front foot'),
 itf('Box drain (G1/2, plugged)', [XC, 0, -(a + t) - 15.0], [0, 0, -1], 'G1/2 boss, plug 1.4571 + copper/graphite seal; open at commissioning / after water wash', 'E5 drain line (optional)'),
]
for t_, s_ in SENS.items():
    IF.append(itf('Sensor %s %s' % (t_, s_['name']), s_['pos'], s_['dir'], s_['desc'], 'B2 / B1 per docs/electrical/02_io_list (tags unchanged; moved from E3-504/505/506)'))
info = dict(subsystem='E3-B compact exhaust collector (variant B, simple-cycle gas section, generator 1)',
            frame='ENG mm; ROOF = (1.880 + x/1000, 7.850 + y/1000, 0.600 + z/1000) m (variant-A placement; variant-B roof layout open)',
            source='cad/variant_b/e3b_exhaust.py + sim/variant_b/e3b_exhaust_calc.py', replaces=list(REPLACED),
            keeps='all other cad_out/engine/E3/E3-*.step (E3-101, E3-102 shroud + radial-diffuser west wall, rotor, bearings, PMG, E3-402 rear foot)',
            envelope_ENG_mm=env, mass_kg={k: round(v, 3) for k, v in mass_new.items()},
            aero=dict(dp_static_p4_p5_Pa=round(sel['dp_static_p4_p5_Pa']), dp_static_pct=round(sel['dp_static_pct_Pa'], 3), dP0_Pa=round(sel['dP0_total_Pa']),
                      V_side=round(sel['V_side'], 1), V_top=round(sel['V_top'], 1), V_outlet=round(sel['V5'], 1),
                      FPT_shaft_kW=round(fp['P_shaft_kW'], 2), FPT_penalty_W=round(RS['fpt']['penalty_vs_old_same_model_W'])),
            interfaces=IF)
json.dump(info, open(os.path.join(OUT, 'E3B_interfaces.json'), 'w'), indent=1)
say('interfaces -> %s (%d entries)' % (os.path.join(OUT, 'E3B_interfaces.json'), len(IF)))

# =====================================================================================================================
# sections: y = 0 (x-z) and x = outlet axis (y-z)
def loops_of(shape, nrm, d0):
    out = []
    try: ws = shape.slice(nrm, d0)
    except Exception: return out
    for w in ws:
        pts = [(p_.x, p_.y, p_.z) for p_ in w.discretize(Deflection=0.2)]
        if len(pts) > 2: out.append(pts)
    return out
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.path import Path as MPath; from matplotlib.patches import PathPatch
    def area(pts): return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    def inside(pt, poly):
        x, y = pt; c = False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0): c = not c
        return c
    def patch(loops, fc, alpha, lw=0.3):
        loops = sorted(loops, key=lambda l: -abs(area(l))); verts, codes = [], []
        for i, l in enumerate(loops):
            depth = sum(1 for o in loops[:i] if abs(area(o)) > abs(area(l)) and inside(l[0], o))
            if (depth % 2 == 0) != (area(l) > 0): l = l[::-1]
            verts += l + [l[0]]; codes += [MPath.MOVETO] + [MPath.LINETO] * (len(l) - 1) + [MPath.CLOSEPOLY]
        return PathPatch(MPath(verts, codes), fc=fc, ec='k', lw=lw, alpha=alpha)
    COL = dict(hot='#d9733a', insulation='#f2d98c', support='#888888', sensor='#d01010')
    fig, axs = plt.subplots(1, 2, figsize=(20, 11), gridspec_kw=dict(width_ratios=[1.25, 1]))
    for ax, (nrm, d0, i1, i2, ttl) in zip(axs, ((V(0, 1, 0), 0.0, 0, 2, 'section y = 0 (x-z)'), (V(1, 0, 0), XC, 1, 2, 'section x = %.1f (y-z, outlet axis)' % XC))):
        for n, s in list(KEPT.items()) + list(E2B.items()):
            lps = [[(q[i1], q[i2]) for q in l] for l in loops_of(s, nrm, d0)]
            if lps: ax.add_patch(patch(lps, '#c8c8c8', 0.8))
        for t_, p_ in PARTS.items():
            lps = [[(q[i1], q[i2]) for q in l] for l in loops_of(p_['shape'], nrm, d0)]
            if lps: ax.add_patch(patch(lps, COL[p_['group']], 0.8 if p_['group'] != 'insulation' else 0.45, 0.4))
        ax.set_aspect('equal'); ax.grid(alpha=0.25); ax.set_title('E3-B compact exhaust - ' + ttl + ' (grey: kept E3 + E2-B)', fontsize=10)
        ax.set_ylabel('ENG z [mm]')
    axs[0].set_xlim(0, 480); axs[0].set_ylim(-410, ZF1 + 30); axs[0].set_xlabel('ENG x [mm]')
    axs[1].set_xlim(-320, 320); axs[1].set_ylim(-410, ZF1 + 30); axs[1].set_xlabel('ENG y [mm]')
    axs[0].annotate('DN%d PN6 outlet, face z %.0f' % (D['DN'], ZF1), (XC, ZF1 + 8), ha='center', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'E3B_section.png'), dpi=100); plt.close(fig)
    say('section -> %s' % os.path.join(OUT, 'E3B_section.png'))
except ImportError:
    say('no matplotlib in FreeCAD python - no section png')

# =====================================================================================================================
# BOM (docs/06 sec.5 columns) with CAD masses
BOMF = os.environ.get('GR180_EXH_BOM') or os.path.join(ROOT, 'docs', 'bom', 'variant_b_e3b_bom.csv')
SUP = {
 'E3B-110': ('make', 'laser cut + press-brake (U-shell 3 mm, 2 bends R20; end plates 3 mm), hood rect-to-round 2 halves bump-bent, stub rolled 219.1 x 3 '
             'or 1.4828 welded tube, PN6 flange; TIG / robot MAG-free (TIG or plasma) welding, captive A286 M8 studs; stress relief 900 C, leak test 0.3 bar',
             'local sheet-metal + robot weld shop; sheet Outokumpu 153MA/253MA or 1.4828 (FI/SE), Aperam (BE); flange EU/IR', 'insulate outside (E3B-114)'),
 'E3B-111': ('make', '1.4828 plate 5 mm laser cut in 2 halves, drilled; split joint mica strip + 2 bolted straps', 'local laser', 'fitted round the interduct before the body'),
 'E3B-112': ('make', 'hub bell 1.4828 2.5 mm metal-spun (as E3-110 bell), disc 4 mm laser + faced, cone IN625 1.5 mm spun, 6 windows laser; TIG; face disc after welding',
             'local spinning + TIG; IN625 sheet VDM Metals (DE)', 'carried by the cold cartridge; nuts from the east (accessible)'),
 'E3B-113': ('buy', 'ceramic-fibre paper 2.5 mm (1260 C grade) + 0.1 mm 1.4828 foil, 4 notches', 'Unifrax / Morgan Thermal Ceramics (EU), Chinese', ''),
 'E3B-114': ('buy', 'microporous panels %.0f mm in 0.5 mm 1.4301 cassettes with quick-release latches; inner face ceramic paper' % T_INS,
             'Promat MICROTHERM (BE), Morgan WDS (DE/UK), Chinese microporous', 'skin <= 60 C at 40 C enclosure air (calc)'),
 'E3B-401': ('make', 'S355J2 (or 1.4301) plate 8 mm laser-cut portal + 2 pads 10 mm + base 10 mm, MAG/TIG; M12 tapped pads', 'local', 'centre-line support: axis stays put when the box grows 2 mm'),
}
EXTRA = [
 ('E3B-601', 'gasket west cover / box west plate (ring OD 330 x ID 280, 1 mm)', 1, 'buy', 'Thermiculite 815 / KLINGER Milam PSS', '1 mm', 'Flexitallic (UK) / Klinger (AT)', 0.05, '', ''),
 ('E3B-602', 'gasket box east plate / rear disc (ring OD 344 x ID 300, 1 mm)', 1, 'buy', 'Thermiculite 815 / KLINGER Milam PSS', '1 mm', 'Flexitallic (UK) / Klinger (AT)', 0.05, '', ''),
 ('E3B-603', 'gasket cover / E3-101 mid flange (ring OD 150 x ID 85, 1 mm)', 1, 'buy', 'KLINGER Milam PSS (mica)', '1 mm', 'Klinger (AT)', 0.01, '', ''),
 ('E3B-604', 'outlet flange gasket DN200 PN6', 1, 'buy', 'Thermiculite 815 / Milam PSS ring', 'DN200 PN6, 1.5 mm', 'Flexitallic (UK) / Klinger (AT)', 0.05, '', 'HRSG/stack side'),
 ('E3B-605', 'hot nuts M8 for the 32 captive studs + washers', 32, 'buy', '1.4980 (A286-class) silver-plated nuts', 'M8', 'Boellhoff (DE) / Chinese GH2132', 0.25, '', 'anti-seize Ni'),
 ('E3B-606', 'cover-to-mid-flange screws M6 x 16', 12, 'buy', '1.4980 / A286-class', 'M6 x 16', 'Boellhoff (DE)', 0.06, '', 'into tapped E3-101 mid flange'),
 ('E3B-607', 'cone-to-PMG screws M5 x 12 + mica spacer ring 3 mm', 12, 'buy', 'A4-70 screws, phlogopite mica ring OD 86 / ID 76', 'M5', 'Wuerth (DE); mica Elmelin (UK)', 0.05, '', 'thermal barrier'),
 ('E3B-608', 'split-joint strap set (2 straps + 4 x M6 + mica strip)', 1, 'make', '1.4828 strip 3 x 30', '', 'local', 0.1, '', 'west cover split line'),
 ('E3B-609', 'support bolting: 4 x M12 base (skid), 2 x M12 lug + 2 mica/Monolux washers', 1, 'buy', '8.8 Zn-flake / A4-70', 'M12', 'Wuerth (DE)', 0.4, '', 'lug slots let the box grow in y'),
 ('E3B-610', 'drain plug G1/2 + seal', 1, 'buy', '1.4571 + graphite seal', 'G1/2', 'Voss (DE) / Hy-Lok (KR)', 0.05, '', ''),
 ('E3B-611', 'outlet bolting M16 (HRSG side) studs + nuts', 8, 'buy', '1.4980/A286-class studs, silver-plated nuts', 'M16 x 70', 'Boellhoff (DE)', 0.9, '', 'supplied with the HRSG duct'),
]
with open(BOMF, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes'])
    for t_, p_ in PARTS.items():
        if t_ in SUP: mb_, spec, supl, note = SUP[t_]
        else: mb_, spec, supl, note = ('buy', p_['mat'], 'Roessel / Electronic Sensor (DE), Jaquet / Baumer (CH), WIKA (DE), Endress+Hauser (CH)', 'moved from E3-504/505/506')
        bbx = p_['shape'].BoundBox
        w.writerow([t_, p_['name'].replace('_', ' '), 1, mb_, spec, '%.0f x %.0f x %.0f mm (bbox)' % (bbx.XLength, bbx.YLength, bbx.ZLength), supl,
                    round(p_['shape'].Volume * p_['rho'], 3), 'cad_out/variant_b/E3B/%s_%s.step' % (t_, p_['name']), note])
    for r_ in EXTRA: w.writerow(r_)
say('BOM -> %s (%d rows)' % (BOMF, len(PARTS) + len(EXTRA)))
say('E3-B total (models + listed extras) %.1f kg' % (sum(mass_new.values()) + sum(r_[7] for r_ in EXTRA)))
open(os.path.join(OUT, 'E3B_build.log'), 'w').write('\n'.join(log))
