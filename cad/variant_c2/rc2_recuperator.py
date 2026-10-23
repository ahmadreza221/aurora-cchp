# GR180 version C2 - compact recuperator R-C2 on the version-C exhaust outlet + hot-water heat exchanger HX-C2 + C1/C2 risers
# + support frame.  Scripted parametric FreeCAD model (Part workbench), ENG frame (mm): x downstream (east), y north, z up.
# Geometry: sim/variant_c2/c2_design.json (python3 sim/variant_c2/c2_calc.py); E2-C2 flanges from cad_out/variant_c2/E2C2/E2C2_interfaces.json.
# Run (after cad/variant_c2/e2c2_combustor_casing.py):
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/variant_c2/rc2_recuperator.py
# Outputs: cad_out/variant_c2/RC2/ (RC2-xxx), cad_out/variant_c2/HXC2/ (HX-xxx), cad_out/variant_c2/FRAME/ (C2F-xxx), each part a STEP,
#          cad_out/variant_c2/C2_interfaces.json, C2_checks.json, C2_section.png, docs/bom/variant_c2_bom.csv (whole C2 package).
# Layout: hot gas leaves the exhaust box UP through the DN200 outlet (x 201.5, face z 390), passes a DN200 bellows into the R-C2
# inlet plenum, flows UP through the plate-fin core (2 brazed modules stacked along x), the hood, the finned-tube hot-water coil and
# leaves through a DN200 stack flange on top.  Cold air: E2-C2 C1 (north) -> riser -> north header (top window) -> core (down) ->
# south header (bottom window) -> riser -> E2-C2 C2 (south).
import FreeCAD as App, Part, os, json, math, sys, csv
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles', False)
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'sim', 'variant_c2', 'c2_design.json')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
CO = os.path.join(ROOT, 'cad_out', 'variant_c2')
OUTS = {k: os.path.join(CO, k) for k in ('RC2', 'HXC2', 'FRAME')}
for d in OUTS.values(): os.makedirs(d, exist_ok=True)
D = json.load(open(os.path.join(ROOT, 'sim', 'variant_c2', 'c2_design.json')))
RS = json.load(open(os.path.join(ROOT, 'sim', 'variant_c2', 'c2_results.json')))
E2I = json.load(open(os.path.join(CO, 'E2C2', 'E2C2_interfaces.json')))
LAY, RC, HXD = D['layout'], D['R_C2'], D['HX_C2']
ROOF0 = (1880.0, 7850.0, 600.0)
def roof(p): return [round((ROOF0[i] + p[i]) / 1000, 4) for i in range(3)]
log = []
def say(*a):
    s = ' '.join(str(v) for v in a); print(s); log.append(s); sys.stdout.flush()

# ---------------------------------------------------------------- helpers
def vec(p): return p if isinstance(p, App.Vector) else V(*p)
def box(x0, x1, y0, y1, z0, z1): return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def cyl(r, p0, p1):
    p0, p1 = vec(p0), vec(p1); d = p1 - p0; return Part.makeCylinder(r, d.Length, p0, d.normalize())
def tube(ro, t, p0, p1):
    p0, p1 = vec(p0), vec(p1); n = (p1 - p0).normalize(); return cyl(ro, p0, p1).cut(cyl(ro - t, p0 - n, p1 + n))
def frame_matrix(X, Y, Z, c): return App.Matrix(X.x, Y.x, Z.x, c.x, X.y, Y.y, Z.y, c.y, X.z, Y.z, Z.z, c.z, 0, 0, 0, 1)
def torus_seg(start, d1, d2, R, r):
    d1, d2 = vec(d1).normalize(), vec(d2).normalize(); th = math.degrees(d1.getAngle(d2))
    nin = (d2 - d1 * d1.dot(d2)).normalize(); c = vec(start) + nin * R
    X = nin * -1; Z = d1.cross(d2).normalize(); Y = Z.cross(X)
    t = Part.makeTorus(R, r, V(0, 0, 0), V(0, 0, 1), -180, 180, th); t.Placement = App.Placement(frame_matrix(X, Y, Z, c))
    return t, c, th
def elbow(start, d1, d2, R, ro, t):
    o, c, th = torus_seg(start, d1, d2, R, ro); i, _, _ = torus_seg(start, d1, d2, R, ro - t)
    d1v, d2v = vec(d1).normalize(), vec(d2).normalize(); nin = (d2v - d1v * d1v.dot(d2v)).normalize(); a = math.radians(th)
    endp = c + (nin * -1) * (R * math.cos(a)) + d1v * (R * math.sin(a))
    return o.cut(i), endp, o
def disk_flange(c, n, D_, bore, K, nb, dh, b):
    n = vec(n).normalize(); c = vec(c); f = Part.makeCylinder(D_ / 2, b, c, n).cut(Part.makeCylinder(bore / 2, b + 2, c - n, n))
    a = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0); e1 = n.cross(a).normalize(); e2 = n.cross(e1)
    for k in range(nb):
        ph = 2 * math.pi * (k + 0.5) / nb
        f = f.cut(Part.makeCylinder(dh / 2, b + 2, c - n + e1 * (K / 2 * math.cos(ph)) + e2 * (K / 2 * math.sin(ph)), n))
    return f
def bellows(p0, p1, ro, conv_h=20.0, pitch=15.0):
    p0, p1 = vec(p0), vec(p1); d = p1 - p0; Lb = d.Length; n = d.normalize()
    parts = [tube(ro, 1.5, p0, p0 + n * 10), tube(ro, 1.5, p1 - n * 10, p1)]
    ncv = max(2, int((Lb - 26) / pitch)); rm = ro + conv_h / 2; s0 = 0.5 * (Lb - (ncv - 1) * pitch)
    for k in range(ncv): parts.append(Part.makeTorus(rm - conv_h * 0.25, conv_h * 0.3, p0 + n * (s0 + k * pitch), n))
    parts.append(tube(ro + 2, 0.6, p0 + n * 10, p1 - n * 10))
    return Part.makeCompound(parts), ncv
FLD = {('DN100', 'PN16'): (220, 180, 8, 18, 20), ('DN125', 'PN16'): (250, 210, 8, 18, 22), ('DN200', 'PN6'): (320, 280, 8, 18, 20),
       ('DN32', 'PN16'): (140, 100, 4, 18, 16)}
PIPE = {'DN100': (114.3, 2.0), 'DN125': (139.7, 2.0), 'DN200': (219.1, 2.0), 'DN32': (42.4, 2.0)}
PARTS = {}
def add(tag, name, shp, mat, rho, group, out, qty=1, note='', mk='make', spec='', sup=''):
    PARTS[tag] = dict(name=name, shape=shp, mat=mat, rho=rho, group=group, out=out, qty=qty, note=note, mk=mk, spec=spec, sup=sup)
    say('  %-8s %-34s valid %-5s solids %3d  mass %7.2f kg' % (tag, name, shp.isValid(), len(shp.Solids), shp.Volume * rho))
RHO = {'347H': 7.96e-6, '321H': 7.90e-6, 'IN625': 8.44e-6, '1.4404': 7.98e-6, '1.4301': 7.90e-6, 'S355': 7.85e-6, 'ins': 0.30e-6, 'misc': 3.0e-6}

# =====================================================================================================================
# R-C2 recuperator
C = LAY['core']; X0, X1 = C['x']; Y0, Y1 = C['y']; Z0, Z1 = C['z']; XM = 0.5 * (X0 + X1)
WIN, EB = C['window_len'], C['end_bar']; ZHT, ZHB = C['z_hdr_top'], C['z_hdr_bot']
WALL = 3.0; RH, TH = 55.0, 1.5; ROH = RH + TH
core_mass = RS['R_C2']['mass']['total']
for k, (xa, xb) in enumerate(((X0, XM), (XM, X1))):
    add('RC2-10%d' % (k + 1), 'Core_Module_%s' % 'AB'[k], box(xa, xb, Y0, Y1, Z0, Z1), '347H', core_mass / 2 / ((xb - xa) * (Y1 - Y0) * (Z1 - Z0)), 'core', 'RC2',
        note='brazed plate-fin %d cold + %d hot layers (half stack), envelope solid; fins: cold %s, hot %s' % (RC['nc'] // 2, RC['nh'] // 2, 'OSF 1.2/2.0/0.10', RC['fin_hot']),
        mk='make', spec='fin forming + stacking + vacuum braze BNi-2 + He leak test; 347H 0.4 mm parting sheets', sup='EU braze shop (Kelvion DE / Linde Kryotechnik CH) or local vacuum furnace')

def header(y_face, sign, zc, nozzle_x, dn, label, tag):
    """half-pipe header on a y-face (sign +1 north, -1 south), axis along x, with end caps and a nozzle stub pointing +-y."""
    full = Part.makeCylinder(ROH, X1 - X0, V(X0, y_face, zc), V(1, 0, 0)).cut(Part.makeCylinder(RH, X1 - X0 + 2, V(X0 - 1, y_face, zc), V(1, 0, 0)))
    side = box(X0 - 1, X1 + 1, y_face, y_face + sign * (ROH + 1), zc - ROH - 1, zc + ROH + 1) if sign > 0 else box(X0 - 1, X1 + 1, y_face - ROH - 1, y_face, zc - ROH - 1, zc + ROH + 1)
    hp = full.common(side)
    for xe in (X0, X1 - 4):
        hp = hp.fuse(Part.makeCylinder(ROH, 4, V(xe, y_face, zc), V(1, 0, 0)).common(side))
    ro, t = PIPE[dn][0] / 2, PIPE[dn][1]
    p0 = V(nozzle_x, y_face + sign * (RH - 5), zc); p1 = V(nozzle_x, y_face + sign * (ROH + 14), zc)
    hp = hp.fuse(cyl(ro, p0, p1)).cut(cyl(ro - t, p0 - V(0, sign * 2, 0), p1 + V(0, sign * 1, 0)))
    add(tag, label, hp, '347H', RHO['347H'], 'header', 'RC2', mk='make', spec='rolled half-pipe 1.5 mm + end caps + nozzle stub, TIG to the core side bars', sup='local TIG shop')
    return p1
c1x = [i for i in E2I['interfaces'] if i['name'].startswith('C1')][0]['ENG_mm']
c2i = [i for i in E2I['interfaces'] if i['name'].startswith('C2')][0]; c2x = c2i['ENG_mm']
NOZ1 = header(Y1, +1, ZHT, c1x[0], 'DN100', 'Header_ColdIn_North', 'RC2-111')
NOZ2 = header(Y0, -1, ZHB, c2i['round_axis_ENG_mm'][0] if c2i.get('round_axis_ENG_mm') else 71.0, 'DN125', 'Header_ColdOut_South', 'RC2-112')

# inlet: mating DN200 PN6 flange on the exhaust outlet, bellows, plenum with perforated plate and support lugs
EF = LAY['exhaust_flange']; IN = LAY['inlet']; XE = EF['x']; ro2 = PIPE['DN200'][0] / 2
fl_in = disk_flange(V(XE, 0, IN['z_flange'][0]), V(0, 0, 1), EF['D'], 2 * (ro2 - 2), EF['K'], EF['n'], EF['hole'], 20)
bel_in, ncv_in = bellows(V(XE, 0, IN['z_flange'][1]), V(XE, 0, IN['z_bellows'][1]), ro2)
add('RC2-120', 'Inlet_Flange_Bellows_DN200', Part.makeCompound([fl_in, bel_in, tube(ro2, 2.0, V(XE, 0, IN['z_bellows'][1]), V(XE, 0, IN['z_plenum'][0] + 4))]),
    '321H', RHO['321H'], 'hot', 'RC2', mk='buy', spec='DN200 PN6 flange + 2-ply IN625 bellows with flow liner, axial +-8 / lateral +-5 mm, 620 C',
    sup='Witzenmann (DE) / BOA (DE) / Belman (DK)')
zp0, zp1 = IN['z_plenum']
pl_o = box(X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL, zp0, zp1)
pl = pl_o.cut(box(X0, X1, Y0, Y1, zp0 + WALL, zp1 + 1)).cut(Part.makeCylinder(ro2 - 2, 10, V(XE, 0, zp0 - 1), V(0, 0, 1)))
perf = box(X0, X1, Y0, Y1, IN['perf_plate_z'], IN['perf_plate_z'] + 2)
skirt = box(X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL, zp1, Z0).cut(box(X0, X1, Y0, Y1, zp1 - 1, Z0 + 1))
lugs = []
for xl in (X0 + 40.0, X1 - 40.0):
    for sy in (-1, 1):
        y_in, y_out = (Y1 + WALL, LAY['portal']['y_cols'][1] + 20) if sy > 0 else (LAY['portal']['y_cols'][0] - 20, Y0 - WALL)
        lugs.append(box(xl - 30, xl + 30, y_in, y_out, 420.0, 440.0))                 # foot plate resting on the top beam (z 420)
        lugs.append(box(xl - 4, xl + 4, y_in, y_out, 440.0, zp0 + 40.0))               # web welded to the plenum side wall
plen = pl.fuse([perf, skirt] + lugs).removeSplitter()
add('RC2-121', 'Inlet_Plenum_PerfPlate_Lugs', plen, '347H', RHO['347H'], 'hot', 'RC2', mk='make', spec='3 mm 347H sheet + TIG; perforated plate 2 mm phi 0.55 (holes not modelled); 4 support lugs',
    sup='local TIG shop')
# hood (skirt) on top, TE-512 boss
ZH0, ZH1 = LAY['hood']['z']
hood = box(X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL, Z1, ZH1).cut(box(X0, X1, Y0, Y1, Z1 - 1, ZH1 + 1))
add('RC2-122', 'Outlet_Hood_Skirt', hood, '347H', RHO['347H'], 'hot', 'RC2', mk='make', spec='3 mm sheet, flanged to HX-C2 (gasket)', sup='local')

# C1 / C2 risers (spools with bellows) from the E2-C2 flanges to the header nozzles
def route(points, ro, t, R):
    P = [vec(p) for p in points]; metal, keep, segs = [], [], []; cur = P[0]
    for i in range(1, len(P)):
        d_in = (P[i] - P[i - 1]).normalize()
        if i < len(P) - 1:
            d_out = (P[i + 1] - P[i]).normalize(); th = d_in.getAngle(d_out)
            if th > 1e-4:
                a = P[i] - d_in * (R * math.tan(th / 2))
                if (a - cur).Length > 0.5: metal.append(tube(ro, t, cur, a)); keep.append(cyl(ro, cur, a)); segs.append((cur, a))
                e, endp, o = elbow(a, d_in, d_out, R, ro, t); metal.append(e); keep.append(o); cur = endp; continue
        if (P[i] - cur).Length > 0.5: metal.append(tube(ro, t, cur, P[i])); keep.append(cyl(ro, cur, P[i])); segs.append((cur, P[i]))
        cur = P[i]
    return metal, keep, segs
RIS = LAY['risers']
# C1: E2-C2 flange face y 190 (north) -> mating flange -> north to the riser -> up -> south into the north header nozzle
p_c1 = vec(c1x); dn1 = 'DN100'; ro1 = PIPE[dn1][0] / 2; R1 = 0.75 * PIPE[dn1][0]; y_r1 = RIS['C1']['y']
D1, K1, n1, h1, b1 = FLD[(dn1, 'PN16')]
f1 = disk_flange(p_c1, V(0, 1, 0), D1, 2 * (ro1 - 2), K1, n1, h1, b1)
pts1 = [p_c1 + V(0, b1, 0), V(p_c1.x, y_r1, p_c1.z), V(p_c1.x, y_r1, ZHT), V(NOZ1.x, NOZ1.y, ZHT)]
m1, k1, s1 = route(pts1, ro1, 2.0, R1)
vseg1 = max(s1, key=lambda s: abs(s[1].z - s[0].z))                             # vertical leg -> bellows in its middle
zb1 = 0.5 * (vseg1[0].z + vseg1[1].z); bel1, nc1 = bellows(V(p_c1.x, y_r1, zb1 - 60), V(p_c1.x, y_r1, zb1 + 60), ro1)
m1 = [m.cut(cyl(ro1 + 25, V(p_c1.x, y_r1, zb1 - 60), V(p_c1.x, y_r1, zb1 + 60))) for m in m1] + [bel1, f1]
add('RC2-131', 'Riser_C1_DN100_with_bellows', Part.makeCompound(m1), '1.4404', RHO['1.4404'], 'cold', 'RC2', mk='make spool; buy bellows',
    spec='EN 10217-7 114.3x2 1.4404, 2 elbows R%.0f, DN100 PN16 flange, 2-ply 321 bellows L120 (axial +-10 mm)' % R1, sup='bellows Witzenmann (DE) / BOA (DE)')
# C2: E2-C2 rect flange face y -170 (south) -> rect flange + rect-to-round transition -> south -> up -> north into the south header
p_c2 = vec(c2x); ro2c = PIPE['DN125'][0] / 2; R2 = 0.75 * PIPE['DN125'][0]; y_r2 = -abs(RIS['C2']['y'])
wi, hi = c2i['rect_inner_mm']; rim = 0.5 * (c2i['rect_flange_mm'][0] - wi); xr = c2i['round_axis_ENG_mm'][0]; zr = c2i['round_axis_ENG_mm'][2]
xa0, xa1, za0, za1 = p_c2.x - wi / 2, p_c2.x + wi / 2, p_c2.z - hi / 2, p_c2.z + hi / 2
rfl = box(xa0 - rim, xa1 + rim, p_c2.y - 15, p_c2.y, za0 - rim, za1 + rim).cut(box(xa0, xa1, p_c2.y - 16, p_c2.y + 1, za0, za1))
for bx_, bz_ in c2i['rect_bolts_xz_mm']: rfl = rfl.cut(Part.makeCylinder(4.5, 20, V(bx_, p_c2.y + 1, bz_), V(0, -1, 0)))
def rw(y, x0, x1, z0, z1): return Part.makePolygon([V(x0, y, z0), V(x1, y, z0), V(x1, y, z1), V(x0, y, z1), V(x0, y, z0)])
def cw(y, r): return Part.Wire(Part.makeCircle(r, V(xr, y, zr), V(0, 1, 0)))
yt0, yt1 = p_c2.y - 15, p_c2.y - 55
lo = Part.makeLoft([rw(yt0, xa0 - 3, xa1 + 3, za0 - 3, za1 + 3), cw(yt1, ro2c)], True, True)
li = Part.makeLoft([rw(yt0 + 0.01, xa0, xa1, za0, za1), cw(yt1 - 0.01, ro2c - 2)], True, True)
pts2 = [V(xr, yt1, zr), V(xr, y_r2, zr), V(xr, y_r2, ZHB), V(NOZ2.x, NOZ2.y, ZHB)]
m2, k2, s2 = route(pts2, ro2c, 2.0, R2)
vseg2 = max(s2, key=lambda s: abs(s[1].z - s[0].z)); zb2 = 0.5 * (vseg2[0].z + vseg2[1].z)
bel2, nc2 = bellows(V(xr, y_r2, zb2 - 70), V(xr, y_r2, zb2 + 70), ro2c)
m2 = [m.cut(cyl(ro2c + 25, V(xr, y_r2, zb2 - 70), V(xr, y_r2, zb2 + 70))) for m in m2] + [bel2, rfl, lo.cut(li)]
add('RC2-132', 'Riser_C2_DN125_with_bellows', Part.makeCompound(m2), '321H', RHO['321H'], 'hot', 'RC2', mk='make spool; buy bellows',
    spec='rect flange 14 x M8 + rect-to-round transition + 139.7x2 321H, 2 elbows R%.0f, 2-ply IN625 bellows L140 (axial +-12 / lateral +-6 mm)' % R2,
    sup='bellows Witzenmann (DE) / BOA (DE)')

# =====================================================================================================================
# HX-C2: finned-tube coil (gas up, water down), box, return bends, DN32 headers
HXZ0, HXZ1 = LAY['hx']['z']; nt, nr = LAY['hx']['tubes_per_row'], LAY['hx']['rows']; Pt, Pl, Do, Df = LAY['hx']['Pt'], LAY['hx']['Pl'], LAY['hx']['Do'], LAY['hx']['fin_D']
hxbox = box(X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL, HXZ0, HXZ1).cut(box(X0, X1, Y0, Y1, HXZ0 - 1, HXZ1 + 1))
xt0, xt1 = X0 - 25.0, X1 + 25.0                                    # tubes pass the 3 mm walls (tube sheets) and end in the return bends
rows = []
for k in range(nr):
    zk = HXZ1 - 20.0 - Pl / 2 - k * Pl                              # row 1 at the top (water in), row nr at the bottom (water out)
    sh = (-Pt / 4 if k % 2 == 0 else Pt / 4)
    rows.append((zk, [-(nt - 1) / 2 * Pt + i * Pt + sh for i in range(nt)]))
fins, tubes_, bends = [], [], []
for zk, ys in rows:
    for y in ys:
        fins.append(cyl(Df / 2, V(X0 + 2, y, zk), V(X1 - 2, y, zk)).cut(cyl(Do / 2 - 0.01, V(X0, y, zk), V(X1, y, zk))))
        tubes_.append(tube(Do / 2, 1.0, V(xt0, y, zk), V(xt1, y, zk)))
for k in range(nr - 1):
    xe = xt1 if k % 2 == 0 else xt0; sgn = 1 if k % 2 == 0 else -1
    (za, ya), (zb_, yb) = (rows[k][0], rows[k][1]), (rows[k + 1][0], rows[k + 1][1])
    for i in range(nt):
        pa, pb = V(xe, ya[i], za), V(xe, yb[i], zb_); mid = (pa + pb) * 0.5; rr = (pb - pa).Length / 2
        nrm = V(1, 0, 0).cross((pb - pa).normalize()).normalize()
        t_o = Part.makeTorus(rr, Do / 2, mid, nrm); t_i = Part.makeTorus(rr, Do / 2 - 1.0, mid, nrm)
        half = box(xe, xe + sgn * (rr + Do), -400, 400, -100, 3000) if sgn > 0 else box(xe - rr - Do, xe, -400, 400, -100, 3000)
        bends.append(t_o.cut(t_i).common(half))
add('HX-101', 'Finned_Tube_Coil_%dx%d' % (nr, nt), Part.makeCompound(tubes_ + bends), '1.4404', RHO['1.4404'], 'hx', 'HXC2',
    mk='make', spec='tubes 16x1 1.4404 (EN 10217-7), %d rows x %d, serpentine, U-bends R%.0f, TIG' % (nr, nt, Pl / 2), sup='local; tube Sandvik (SE) / Outokumpu (FI)')
add('HX-102', 'Helical_Fins_envelope', Part.makeCompound(fins), '1.4301', RHO['1.4301'] * RS['HX_C2']['mass_tubes_kg'] / max(1e-9, sum(f.Volume for f in fins) * RHO['1.4301']) * 0.75,
    'hx', 'HXC2', note='fin envelope Ø%.0f (0.4 mm fins at 3.0 mm pitch, not modelled individually)' % Df,
    mk='buy', spec='helically wound 1.4301 fins 0.4 x 9 mm on 16 mm tube, 333 fins/m, high-frequency welded', sup='Schmöle (DE) / Kelvion (DE) finned tube')
# water headers DN32 at the west end: inlet to row 1 (top), outlet from row nr (bottom)
whd = []
WNOZ = {}
for tag, (zk, ys) in (('in', rows[0]), ('out', rows[-1])):
    xh = xt0 - 38.0                                                   # outside the 30 mm coil-box insulation
    whd.append(tube(21.2, 2.0, V(xh, min(ys) - 30, zk), V(xh, max(ys) + 30, zk)))
    for y in ys: whd.append(tube(Do / 2, 1.0, V(xh, y, zk), V(xt0 + 0.5, y, zk)))
    pn = V(xh - 19.0, 0.5 * (min(ys) + max(ys)), zk); whd.append(tube(21.2, 2.0, pn, pn + V(-60, 0, 0)))     # nozzle points west
    Dw, Kw, nw, hw, bw = FLD[('DN32', 'PN16')]
    whd.append(disk_flange(pn + V(-60, 0, 0), V(-1, 0, 0), Dw, 2 * 19.2, Kw, nw, hw, bw))
    WNOZ[tag] = pn + V(-76, 0, 0)
add('HX-103', 'Water_Headers_DN32', Part.makeCompound(whd), '1.4404', RHO['1.4404'], 'hx', 'HXC2', mk='make', spec='42.4x2 1.4404 headers + DN32 PN16 flanges; PN6 water, 95 C',
    sup='local; flanges Erne (AT)')
add('HX-104', 'Coil_Box_TubeSheets', hxbox, '1.4404', RHO['1.4404'], 'hx', 'HXC2', mk='make', spec='3 mm 1.4404 box, tube sheets = end walls (tubes expanded/welded), gasketed to RC2-122 and the stack cone',
    sup='local TIG shop')
# stack cone + DN200 PN6 flange on top
ST = LAY['stack']; zs0 = HXZ1; zs1 = HXZ1 + 90.0; zs2 = zs1 + ST['h'] - 90.0
so = Part.makeLoft([Part.makePolygon([V(X0 - WALL, Y0 - WALL, zs0), V(X1 + WALL, Y0 - WALL, zs0), V(X1 + WALL, Y1 + WALL, zs0), V(X0 - WALL, Y1 + WALL, zs0), V(X0 - WALL, Y0 - WALL, zs0)]),
                    Part.Wire(Part.makeCircle(ro2, V(XM, 0, zs1), V(0, 0, 1)))], True, True)
si = Part.makeLoft([Part.makePolygon([V(X0, Y0, zs0 - 0.01), V(X1, Y0, zs0 - 0.01), V(X1, Y1, zs0 - 0.01), V(X0, Y1, zs0 - 0.01), V(X0, Y0, zs0 - 0.01)]),
                    Part.Wire(Part.makeCircle(ro2 - 2, V(XM, 0, zs1 + 0.01), V(0, 0, 1)))], True, True)
stack = so.cut(si).fuse([tube(ro2, 2.0, V(XM, 0, zs1), V(XM, 0, zs2)),
                         disk_flange(V(XM, 0, zs2), V(0, 0, 1), ST['D'], 2 * (ro2 - 2), 280, 8, 18, 20)])
add('HX-105', 'Stack_Cone_DN200_Flange', stack, '1.4404', RHO['1.4404'], 'hx', 'HXC2', mk='make', spec='3 mm cone + 219.1x2 stub + DN200 PN6 flange (to the site stack / chimney)', sup='local')

# =====================================================================================================================
# insulation (removable boxes, microporous + 0.5 mm 1.4301 cladding)
INS = LAY['insulation']
def riser_ins(segs, ro, t_ins):
    return Part.makeCompound([cyl(ro + t_ins, a, b).cut(cyl(ro + 0.5, a - (b - a).normalize(), b + (b - a).normalize())) for a, b in segs if (b - a).Length > 30])
add('RC2-141', 'Insulation_Risers', Part.makeCompound([riser_ins(s1, ro1, INS['risers_C1_mm']), riser_ins(s2, ro2c, INS['risers_C2_mm'])]), 'microporous', RHO['ins'] * 1.3,
    'ins', 'RC2', mk='buy', spec='C1 20 mm mineral wool, C2 60 mm microporous, clad; bellows and elbows: removable blankets', sup='Promat (BE/DE) / Rockwool (DK)')
INS = LAY['insulation']; ti, th_ = INS['recup_mm'], INS['hx_mm']
ins_r = box(X0 - WALL - ti, X1 + WALL + ti, Y0 - ROH - 20, Y1 + ROH + 20, zp0 - ti, ZH1)                # recuperator: plenum, core, headers, hood
ins_r = ins_r.cut(box(X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL, zp0, ZH1 + 1))
for sh_ in [PARTS['RC2-111']['shape'], PARTS['RC2-112']['shape']]:
    hb = sh_.BoundBox; ins_r = ins_r.cut(box(hb.XMin, hb.XMax, hb.YMin, hb.YMax, hb.ZMin, hb.ZMax))                    # headers: own removable boxes
ins_r = ins_r.cut(Part.makeCylinder(ro2 + 40, 200, V(XE, 0, zp0 - ti - 100), V(0, 0, 1)))                                # bellows (own blanket)
ins_r = ins_r.cut(Part.makeCompound(k1 + k2)).cut(PARTS['RC2-141']['shape'])                                     # riser stubs, elbows, riser insulation
ins_r = ins_r.cut(Part.makeCompound([Part.makeCylinder(ro1 + 30, 400, V(c1x[0], Y1 + ROH, ZHT), V(0, 1, 0)), Part.makeCylinder(ro2c + 30, 400, V(xr, Y0 - ROH, ZHB), V(0, -1, 0))]))
for xl in (X0 + 40.0, X1 - 40.0): ins_r = ins_r.cut(box(xl - 32, xl + 32, -300, 300, 410, zp0 + 45))                     # support lugs
add('RC2-140', 'Insulation_Recuperator', ins_r, 'microporous', RHO['ins'] * 1.3, 'ins', 'RC2', mk='buy', spec='microporous %d mm in 0.5 mm 1.4301 cladding, removable boxes' % ti,
    sup='Promat MICROTHERM (BE/DE)')
ins_h = box(X0 - WALL - th_, X1 + WALL + th_, Y0 - WALL - th_, Y1 + WALL + th_, HXZ0, HXZ1).cut(box(X0 - WALL, X1 + WALL, Y0 - WALL, Y1 + WALL, HXZ0 - 1, HXZ1 + 1))
add('HX-140', 'Insulation_Coil_Box', ins_h, 'mineral wool', RHO['ins'] * 0.5, 'ins', 'HXC2', mk='buy', spec='mineral wool %d mm + 0.5 mm 1.4301 cladding (box 300 C max)' % th_,
    sup='Rockwool (DK) / Isover (FR)')

# =====================================================================================================================
# frame (extends the version-C base frame): rail extensions, 2 cross beams, 4 columns, 2 top beams
PO = LAY['portal']; (xc0, xc1), (yc0, yc1) = PO['x_cols'], PO['y_cols']; zb0, zb1 = 380.0, 420.0; zr0, zr1 = -310.0, -250.0
fr = []
def rhs_x(x0, x1, y0, y1, z0, z1, t=3.0): return box(x0, x1, y0, y1, z0, z1).cut(box(x0 - 1, x1 + 1, y0 + t, y1 - t, z0 + t, z1 - t))
def rhs_y(x0, x1, y0, y1, z0, z1, t=3.0): return box(x0, x1, y0, y1, z0, z1).cut(box(x0 + t, x1 - t, y0 - 1, y1 + 1, z0 + t, z1 - t))
fr.append(Part.makeCompound([rhs_x(xc0 - 20, -69.5, 100 if sy > 0 else -120, 120 if sy > 0 else -100, zr0, zr1) for sy in (-1, 1)] +
                            [rhs_x(467.6, xc1 + 20, 100 if sy > 0 else -120, 120 if sy > 0 else -100, zr0, zr1) for sy in (-1, 1)]))
fr.append(Part.makeCompound([rhs_y(xc - 20, xc + 20, yc0 - 20, yc1 + 20, zr0, zr1) for xc in (xc0, xc1)]))
fr.append(Part.makeCompound([box(xc - 30, xc + 30, yc - 30, yc + 30, zr1, zb0).cut(box(xc - 26, xc + 26, yc - 26, yc + 26, zr1 - 1, zb0 + 1)) for xc in (xc0, xc1) for yc in (yc0, yc1)]))
fr.append(Part.makeCompound([box(xc0 - 30, xc1 + 30, yc - 20, yc + 20, zb0, zb1).cut(box(xc0 - 31, xc1 + 31, yc - 17, yc + 17, zb0 + 3, zb1 - 3)) for yc in (yc0, yc1)]))
FRN = [('C2F-01', 'Rail_Extensions_RHS60x40_x4', 'RHS 60x40x3 1.4301, bolted to the C-410 rails'), ('C2F-02', 'Cross_Beams_RHS60x40_x2', 'RHS 60x40x3 1.4301'),
       ('C2F-03', 'Columns_SHS60x4_x4', 'SHS 60x60x4 1.4301, base plates M12 to the cross beams'), ('C2F-04', 'Top_Beams_RHS80x40_x2', 'RHS 80x40x3 1.4301 carrying the 4 R-C2 lugs')]
for (tg, nm, sp), shp in zip(FRN, fr):
    add(tg, nm, shp, '1.4301', RHO['1.4301'], 'frame', 'FRAME', mk='make', spec=sp + '; laser-cut + TIG, or galvanised S355 if indoors', sup='local; profiles Outokumpu / Tata Steel EU')

# =====================================================================================================================
# instrument bosses (envelopes): TE-502 (C1 riser), TE-503 (C2 riser), TE-512 (hood), TE-513 stack, TE/PT water in/out
def probe(p, n, segs):
    p, n = vec(p), vec(n).normalize(); s, d = [], 0.0
    for L_, r_ in segs: s.append(Part.makeCylinder(r_, L_, p + n * d, n)); d += L_
    return Part.makeCompound(s)
SENS = [('TE-502', 'T2 cold-in (C1 riser, top)', V(c1x[0], y_r1, ZHT - R1 - 40) + V(0, ro1, 0), V(0, 1, 0)),
        ('TE-503', 'T2r cold-out (C2 riser, top)', V(xr, y_r2, ZHB - R2 - 40) + V(0, -ro2c, 0), V(0, -1, 0)),
        ('TE-512', 'R-C2 hot out / HX in (hood, east)', V(X1 + WALL, 60.0, 0.5 * (ZH0 + ZH1)), V(1, 0, 0)),
        ('TE-513', 'stack (HX out)', V(XM, ro2, zs1 + 30), V(0, 1, 0)),
        ('TE-770', 'hot water out 90 C (DN32)', WNOZ['out'] + V(45, 0, 21.2), V(0, 0, 1)),
        ('TE-771', 'hot water in 70 C (DN32)', WNOZ['in'] + V(45, 0, 21.2), V(0, 0, 1))]
for i, (tg, lab, p, n) in enumerate(SENS):
    add('RC2-5%02d' % (i + 1), '%s_%s' % (tg, lab.split(' ')[0]), probe(p, n, [(30.0, 7.0), (50.0, 3.0)]), 'sensor', RHO['misc'], 'sensor', 'RC2',
        note=lab, mk='buy', spec='type K MI 3 mm (gas) / PT1000 (water), compression fitting on a welded boss', sup='Roessel Messtechnik (DE)')

# =====================================================================================================================
# checks (internal pairs; the full stack check is cad/engine/engine_stack_check.py STACK_VARIANT=C2)
def overlap(a, b):
    if not a.BoundBox.intersect(b.BoundBox): return 0.0
    try: return a.common(b).Volume
    except Exception: return -1.0
JOINT_PFX = {('RC2-101', 'RC2-102'), ('RC2-101', 'RC2-111'), ('RC2-102', 'RC2-111'), ('RC2-101', 'RC2-112'), ('RC2-102', 'RC2-112'), ('RC2-121', 'RC2-120'),
             ('RC2-131', 'RC2-111'), ('RC2-132', 'RC2-112'), ('HX-101', 'HX-102'), ('HX-101', 'HX-104'), ('HX-101', 'HX-103'), ('HX-102', 'HX-104'),
             ('C2F-01', 'C2F-02'), ('C2F-02', 'C2F-03'), ('C2F-03', 'C2F-04'), ('RC2-121', 'C2F-04'), ('HX-103', 'HX-104'), ('RC2-140', 'RC2-121'), ('HX-104', 'HX-105'),
             ('HX-101', 'HX-140'), ('HX-103', 'HX-140'), ('RC2-122', 'HX-104'), ('RC2-140', 'RC2-131'), ('RC2-140', 'RC2-132'), ('RC2-141', 'RC2-131'), ('RC2-141', 'RC2-132')}
chk = dict(internal=[])
tags = sorted(PARTS)
for i, a in enumerate(tags):
    for b in tags[i + 1:]:
        v = overlap(PARTS[a]['shape'], PARTS[b]['shape'])
        if v > 1.0 or v < 0:
            exp = (a, b) in JOINT_PFX or (b, a) in JOINT_PFX or 'sensor' in (PARTS[a]['group'], PARTS[b]['group'])
            chk['internal'].append(dict(a=a, b=b, vol_mm3=round(v, 1), expected=exp))
bad = [r for r in chk['internal'] if not r['expected']]
say('R-C2/HX/frame internal overlaps > 1 mm3: %d (unexpected %d) %s' % (len(chk['internal']), len(bad), bad[:12]))
json.dump(chk, open(os.path.join(CO, 'C2_checks.json'), 'w'), indent=1)

# exports
for t, p in PARTS.items(): p['shape'].exportStep(os.path.join(OUTS[p['out']], '%s_%s.step' % (t, p['name'])))
for k in OUTS:
    sub = [p['shape'] for p in PARTS.values() if p['out'] == k]
    if sub: Part.makeCompound(sub).exportStep(os.path.join(OUTS[k], '%s_assembly.step' % k))
bb = Part.makeCompound([p['shape'] for p in PARTS.values()]).BoundBox
say('R-C2 + HX + frame bbox x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f' % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))

# interfaces
def itf(name, pos, direction, size, counterpart, **kw):
    d = dict(name=name, ENG_mm=[round(v, 2) for v in pos], ROOF_m=roof(pos), direction=direction, size=size, counterpart=counterpart); d.update(kw); return d
IF = [itf('R-C2 hot inlet (on the version-C exhaust outlet)', [XE, 0, EF['z']], [0, 0, -1], 'DN200 PN6 EN 1092-1 (OD 320, PCD 280, 8 x M16), face z 390',
          'cad/variant_b/e3b_exhaust.py (variant C) outlet flange'),
      itf('C1 riser <- E2-C2 C1', c1x, [0, -1, 0], 'DN100 PN16', 'E2-C2 C1 flange'),
      itf('C2 riser -> E2-C2 C2 (rectangular)', c2x, [0, 1, 0], 'rect 84 x 235, 14 x M8', 'E2-C2 C2 flange'),
      itf('Hot water in 70 C', list(WNOZ['in']), [-1, 0, 0], 'DN32 PN16, %.2f m3/h, PN6 water 95 C max' % RS['HX_C2']['m3_h'], 'absorption chiller / hot-water loop return'),
      itf('Hot water out 90 C', list(WNOZ['out']), [-1, 0, 0], 'DN32 PN16, %.1f kW at 15 C' % RS['HX_C2']['Q_kW'], 'absorption chiller generator / DHW tank'),
      itf('Stack outlet', [XM, 0, zs2 + 20], [0, 0, 1], 'DN200 PN6, ~100 C, 0.40 kg/s', 'site stack / chimney (rain cap, condensate drain)'),
      itf('Frame feet (4 + version-C feet)', [xc0, yc0, zr0], [0, 0, -1], 'cross beams RHS 60x40 at x %.0f / %.0f, y %.0f..%.0f' % (xc0, xc1, yc0, yc1), 'roof skid / anti-vibration mounts')]
json.dump(dict(subsystem='version C2: R-C2 recuperator + HX-C2 hot-water coil + risers + frame extension', frame='ENG mm (ROOF as variant A)',
               bbox_ENG_mm=[[round(bb.XMin), round(bb.YMin), round(bb.ZMin)], [round(bb.XMax), round(bb.YMax), round(bb.ZMax)]],
               masses_kg={t: round(p['shape'].Volume * p['rho'], 2) for t, p in PARTS.items()}, interfaces=IF),
          open(os.path.join(CO, 'C2_interfaces.json'), 'w'), indent=1, ensure_ascii=False)

# BOM: whole C2 package = E2-C2 rows + R-C2 / HX-C2 / frame rows + reused subsystems (reference rows)
rows = [['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes']]
e2rows = list(csv.reader(open(os.path.join(CO, 'E2C2', 'E2C2_bom.csv'))))[1:]
rows += e2rows
for t, p in PARTS.items():
    b_ = p['shape'].BoundBox; m = p['shape'].Volume * p['rho']
    rows.append([t, p['name'].replace('_', ' '), p['qty'], p['mk'], p['spec'] or p['mat'], '%.0f x %.0f x %.0f mm (bbox)' % (b_.XLength, b_.YLength, b_.ZLength),
                 p['sup'], round(m, 2), 'cad_out/variant_c2/%s/%s_%s.step' % (p['out'], t, p['name']), p['note']])
rows += [['C2-REF-CORE', 'GR180 core v13A (kept parts)', 1, 'see docs/05_phase1_core_v13A.md', '', '', '', 6.0, 'cad_out/v13A/asm_parts', 'unchanged'],
         ['C2-REF-E1', 'E1 GG turbine stage (blisk, NGV, shaft)', 1, 'see docs/engine/E1_gg_turbine.md', 'IN713LC cast / 42CrMo4', '', '', 0, 'fusion/E1/*.step', 'unchanged'],
         ['C2-REF-E3', 'E3 interduct + FPT + PMG (kept parts, collector replaced)', 1, 'see docs/bom/engine_E3_bom.csv', '', '30 kW PMG', '', 20.0, 'cad_out/engine/E3', 'unchanged'],
         ['C2-REF-EXH', 'Version-C compact exhaust (E3B-110..506)', 1, 'see docs/bom/variant_b_e3b_bom.csv + sim/variant_c', '', 'DN200 up', '', 32.0, 'cad_out/variant_c/EXH', 'unchanged'],
         ['C2-REF-FRC', 'Version-C base frame C-402, C-403, C-410 (C-401 replaced by E2C2-103)', 1, 'see cad/variant_c/c_frame.py', '', '', '', 15.0, 'cad_out/variant_c/FRAME', ''],
         ['C2-601', 'Gaskets: DN200 (Thermiculite 815 / spiral-wound 321-mica), DN100, rect C2, DN32 water (EPDM)', 6, 'buy', 'EN 1514', '', 'Klinger (AT) / Kempchen (DE)', 1.0, '', ''],
         ['C2-602', 'Bolting: DN200 8 x M16, DN100 8 x M16, C2 14 x M8, DN32 2 x 4 x M16, frame M12 (A4-70 / 1.4980 hot)', 1, 'buy', 'EN ISO 3506 / 1.4980', '', 'Bossard (CH) / Wuerth (DE)', 3.0, '', ''],
         ['C2-603', 'Anti-vibration mounts under the cross beams', 4, 'buy', 'elastomer, 150 kg each', '', 'Freudenberg (DE) / Trelleborg (SE)', 2.0, '', 'decouples the package from the roof']]
with open(os.path.join(ROOT, 'docs', 'bom', 'variant_c2_bom.csv'), 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(rows)
tot = sum(p['shape'].Volume * p['rho'] for p in PARTS.values())
say('BOM -> docs/bom/variant_c2_bom.csv (%d rows); R-C2 + HX + risers + frame %.1f kg' % (len(rows) - 1, tot))
open(os.path.join(CO, 'RC2_build.log'), 'w').write('\n'.join(log) + '\n')
