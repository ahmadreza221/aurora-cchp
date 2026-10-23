# GR180 version C2 (simplified) - recuperator R-C2 on the version-C exhaust outlet + bought hot-water economiser + C1/C2 risers + frame.
# Scripted parametric FreeCAD model (Part workbench), ENG frame (mm): x downstream (east), y north, z up.
# Geometry: sim/variant_c2/c2_design.json (python3 sim/variant_c2/c2_calc.py); E2-C2 flanges from cad_out/variant_c2/E2C2/E2C2_interfaces.json.
# Run (after cad/variant_c2/e2c2_combustor_casing.py):
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/variant_c2/rc2_recuperator.py
# Outputs: cad_out/variant_c2/RC2/ (RC2-xxx), cad_out/variant_c2/HXC2/ (HX-xxx), cad_out/variant_c2/FRAME/ (C2F-10), one STEP per part + a
#          per-folder assembly STEP; cad_out/variant_c2/C2_interfaces.json, C2_checks.json; docs/bom/variant_c2_bom.csv (whole C2 package).
# Simplifications (user, 2026-10-23): ONE brazed core block bought to drawing, bolt-on header boxes, straight risers with standard braided
# metal hoses, standard DN200 expansion joint, round EN 1092-1 flanges only, bought finned-tube economiser (envelope), one welded RHS frame,
# only the instruments that control/protection need.
import FreeCAD as App, Part, os, json, math, sys, csv
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles', False)
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'sim', 'variant_c2', 'c2_design.json')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
CO = os.path.join(ROOT, 'cad_out', 'variant_c2')
OUTS = {k: os.path.join(CO, k) for k in ('RC2', 'HXC2', 'FRAME')}
for d in OUTS.values():
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):                                    # remove parts of the first (superseded) layout
        if f.endswith('.step'): os.remove(os.path.join(d, f))
D = json.load(open(os.path.join(ROOT, 'sim', 'variant_c2', 'c2_design.json')))
RS = json.load(open(os.path.join(ROOT, 'sim', 'variant_c2', 'c2_results.json')))
E2I = json.load(open(os.path.join(CO, 'E2C2', 'E2C2_interfaces.json')))
LAY, RC = D['layout'], D['R_C2']
ROOF0 = (1880.0, 7850.0, 600.0)
def roof(p): return [round((ROOF0[i] + p[i]) / 1000, 4) for i in range(3)]
log = []
def say(*a):
    s = ' '.join(str(v) for v in a); print(s); log.append(s); sys.stdout.flush()

# ---------------------------------------------------------------- helpers
def vec(p): return p if isinstance(p, App.Vector) else V(*p)
def box(x0, x1, y0, y1, z0, z1): return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def shell_box(x0, x1, y0, y1, z0, z1, t, open_face=None):
    o = box(x0, x1, y0, y1, z0, z1); i = box(x0 + t, x1 - t, y0 + t, y1 - t, z0 + t, z1 - t)
    if open_face == '-y': i = box(x0 + t, x1 - t, y0 - 1, y1 - t, z0 + t, z1 - t)
    if open_face == '+y': i = box(x0 + t, x1 - t, y0 + t, y1 + 1, z0 + t, z1 - t)
    return o.cut(i)
def cyl(r, p0, p1):
    p0, p1 = vec(p0), vec(p1); d = p1 - p0; return Part.makeCylinder(r, d.Length, p0, d.normalize())
def tube(ro, t, p0, p1):
    p0, p1 = vec(p0), vec(p1); n = (p1 - p0).normalize(); return cyl(ro, p0, p1).cut(cyl(ro - t, p0 - n, p1 + n))
def disk_flange(c, n, D_, bore, K, nb, dh, b):
    n = vec(n).normalize(); c = vec(c); f = Part.makeCylinder(D_ / 2, b, c, n).cut(Part.makeCylinder(bore / 2, b + 2, c - n, n))
    a = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0); e1 = n.cross(a).normalize(); e2 = n.cross(e1)
    for k in range(nb):
        ph = 2 * math.pi * (k + 0.5) / nb
        f = f.cut(Part.makeCylinder(dh / 2, b + 2, c - n + e1 * (K / 2 * math.cos(ph)) + e2 * (K / 2 * math.sin(ph)), n))
    return f
FLD = {'DN32': (140, 100, 4, 18, 16), 'DN100': (220, 180, 8, 18, 20), 'DN125': (250, 210, 8, 18, 22), 'DN200': (320, 280, 8, 18, 20)}   # EN 1092-1 PN16 / DN200 PN6
OD = {'DN32': 42.4, 'DN100': 114.3, 'DN125': 139.7, 'DN200': 219.1}
def flange(dn, c, n): D_, K, nb, dh, b = FLD[dn]; return disk_flange(c, n, D_, OD[dn] - 4, K, nb, dh, b), b
def braided_hose(dn, z0, z1, x, y):
    """standard flanged braided metal hose assembly (EN ISO 10380): two flanges + corrugated hose with braid (envelope)."""
    D_, K, nb, dh, b = FLD[dn]; ro = OD[dn] / 2
    f0 = disk_flange(V(x, y, z0), V(0, 0, 1), D_, OD[dn] - 4, K, nb, dh, b); f1 = disk_flange(V(x, y, z1 - b), V(0, 0, 1), D_, OD[dn] - 4, K, nb, dh, b)
    hose = cyl(ro + 8, V(x, y, z0 + b), V(x, y, z1 - b)).cut(cyl(ro - 2, V(x, y, z0), V(x, y, z1)))
    return Part.makeCompound([f0, f1, hose])
PARTS = {}
def add(tag, name, shp, mat, rho, group, out, qty=1, note='', mk='make', spec='', sup=''):
    PARTS[tag] = dict(name=name, shape=shp, mat=mat, rho=rho, group=group, out=out, qty=qty, note=note, mk=mk, spec=spec, sup=sup)
    say('  %-8s %-34s valid %-5s solids %3d  mass %7.2f kg' % (tag, name, shp.isValid(), len(shp.Solids), shp.Volume * rho))
RHO = {'347H': 7.96e-6, '321H': 7.90e-6, '1.4404': 7.98e-6, '1.4301': 7.90e-6, 'ins': 0.30e-6, 'misc': 3.0e-6}

# =====================================================================================================================
# RC2-101 core block (ONE brazed plate-fin block, bought to our drawing) with 20 mm bolting collars at both ends
C = LAY['core']; X0, X1 = C['x']; Y0, Y1 = C['y']; Z0, Z1 = C['z']; XM = 0.5 * (X0 + X1); FR, RIM = C['frame'], C['frame_rim']
ZHT, ZHB = C['z_hdr_top'], C['z_hdr_bot']; HH = LAY['headers']['height']; WALL = LAY['headers']['wall']
block = box(X0, X1, Y0, Y1, Z0, Z1)
collars = [box(X0 - RIM, X1 + RIM, Y0 - RIM, Y1 + RIM, z0_, z0_ + FR).cut(box(X0, X1, Y0, Y1, z0_ - 1, z0_ + FR + 1)) for z0_ in (Z0, Z1 - FR)]
core = block.fuse(collars).removeSplitter()
core_mass = RS['R_C2']['mass']['total'] + 2 * 2 * (X1 - X0 + Y1 - Y0 + 4 * RIM) * RIM * FR * RHO['347H']
add('RC2-101', 'Core_Block_PlateFin', core, '347H', core_mass / core.Volume, 'core', 'RC2',
    note='%d cold + %d hot layers, OSF 1.2/2.0/0.10 cold, %s hot; envelope solid; Z-flow: cold windows north-top / south-bottom' % (RC['nc'], RC['nh'], RC['fin_hot']),
    mk='buy (to drawing)', spec='brazed plate-fin, 347H, BNi-2 vacuum braze, He leak test, 2 bolting collars 20 mm; %.0f x %.0f x %.0f mm' % (X1 - X0, Y1 - Y0, Z1 - Z0),
    sup='Kelvion (DE) / Linde Kryotechnik (CH) / Nordon (FR) - brazed plate-fin to drawing')

# RC2-111 / RC2-112 header boxes (bolted to the core side over the cold windows), nozzle + round flange on the BOTTOM
HN, HS = LAY['headers']['north'], LAY['headers']['south']
def header_box(tag, name, y_rng, zc, noz_xy, dn, sign):
    y0_, y1_ = sorted(y_rng)
    z0_, z1_ = zc - HH / 2, zc + HH / 2
    if sign > 0: hb = shell_box(X0, X1, Y1, y1_, z0_, z1_, WALL, open_face='-y')
    else: hb = shell_box(X0, X1, y0_, Y0, z0_, z1_, WALL, open_face='+y')
    x, y = noz_xy; ro = OD[dn] / 2
    hb = hb.cut(cyl(ro - 2, V(x, y, z0_ - 1), V(x, y, z0_ + WALL + 1)))
    stub = tube(ro, 2.0, V(x, y, z0_ - 30.0), V(x, y, z0_ + 0.5))
    fl, b = flange(dn, V(x, y, z0_ - 30.0), V(0, 0, -1))
    add(tag, name, hb.fuse([stub, fl]).removeSplitter(), '347H', RHO['347H'], 'header', 'RC2', mk='make',
        spec='3 mm 347H box, gasket (Thermiculite 815) + M8 studs to the core side bars, %s PN16 nozzle on the bottom' % dn, sup='local TIG shop')
    return z0_ - 30.0 - b                                         # header flange face (facing down)
ZF1 = header_box('RC2-111', 'Header_Box_North_ColdIn', HN['y'], ZHT, HN['nozzle_xy'], 'DN100', +1)
ZF2 = header_box('RC2-112', 'Header_Box_South_ColdOut', HS['y'], ZHB, HS['nozzle_xy'], 'DN125', -1)

# RC2-120 DN200 expansion joint (bought, flanged, on the exhaust outlet flange), RC2-121 round-to-rectangle transition + perforated plate + 4 support legs
EF = LAY['exhaust_flange']; IN = LAY['inlet']; XE = EF['x']; ro2 = OD['DN200'] / 2
zj0, zj1 = IN['z_joint']; zt0, zt1 = IN['z_trans']
fa, b_ = flange('DN200', V(XE, 0, EF['z']), V(0, 0, 1)); fb, _ = flange('DN200', V(XE, 0, zt0 - b_), V(0, 0, 1))
bel = [Part.makeTorus(ro2 + 6, 7, V(XE, 0, zj0 + 12 + 12 * k), V(0, 0, 1)) for k in range(int((zt0 - b_ - EF['z'] - b_ - 20) / 12))]
add('RC2-120', 'Expansion_Joint_DN200_PN6', Part.makeCompound([fa, fb, tube(ro2, 2.0, V(XE, 0, EF['z'] + b_), V(XE, 0, zt0 - b_))] + bel), '1.4541/IN625', RHO['321H'],
    'hot', 'RC2', mk='buy', spec='standard axial expansion joint DN200 PN6, 2-ply 1.4541, inner sleeve, 650 C, axial +-10 / lateral +-5 mm, flanged EN 1092-1',
    sup='Witzenmann (DE) / BOA (DE) / Belman (DK)')
ft, _ = flange('DN200', V(XE, 0, zt0), V(0, 0, 1))
lo = Part.makeLoft([Part.Wire(Part.makeCircle(ro2, V(XE, 0, zt0 + b_), V(0, 0, 1))),
                    Part.makePolygon([V(X0, Y0, zt1), V(X1, Y0, zt1), V(X1, Y1, zt1), V(X0, Y1, zt1), V(X0, Y0, zt1)])], True, True)
li = Part.makeLoft([Part.Wire(Part.makeCircle(ro2 - 2, V(XE, 0, zt0 + b_ - 0.01), V(0, 0, 1))),
                    Part.makePolygon([V(X0 + 3, Y0 + 3, zt1 + 0.01), V(X1 - 3, Y0 + 3, zt1 + 0.01), V(X1 - 3, Y1 - 3, zt1 + 0.01), V(X0 + 3, Y1 - 3, zt1 + 0.01), V(X0 + 3, Y0 + 3, zt1 + 0.01)])], True, True)
trans = lo.cut(li)
rimt = box(X0 - RIM, X1 + RIM, Y0 - RIM, Y1 + RIM, zt1, Z0).cut(box(X0, X1, Y0, Y1, zt1 - 1, Z0 + 1))            # bolting rim to the core bottom collar
perf = box(X0 + 3, X1 - 3, Y0 + 3, Y1 - 3, IN['perf_plate_z'], IN['perf_plate_z'] + 2).common(li)
FRM = LAY['frame']; (ycb0, ycb1), (zb0, zb1) = FRM['y_cols'], FRM['z_top']
legs = []
for xl in (X0 + 40.0, X1 - 40.0):
    for yc in (ycb0, ycb1):
        y_in, y_out = (Y1 + RIM, yc + 20) if yc > 0 else (yc - 20, Y0 - RIM)
        legs.append(box(xl - 30, xl + 30, min(y_in, y_out), max(y_in, y_out), zb1, zb1 + 10))                     # foot plate on the top beam
        legs.append(box(xl - 4, xl + 4, min(y_in, y_out) if yc > 0 else min(y_in, y_out), max(y_in, y_out), zb1 + 10, zt1))   # web to the transition rim
add('RC2-121', 'Inlet_Transition_PerfPlate_Legs', trans.fuse([ft, rimt, perf] + legs).removeSplitter(), '347H', RHO['347H'], 'hot', 'RC2', mk='make',
    spec='3 mm 347H round-to-rectangle transition, DN200 PN6 flange, bolting rim, perforated plate 2 mm phi 0.55 (holes not modelled), 4 support legs',
    sup='local TIG shop')

# RC2-131 / RC2-132 risers: straight pipe with two flanges + standard braided metal hose (flanged) up to the header box nozzle
def riser(tag, name, dn, iface, z_top_face, mat, spec):
    x, y, z0_ = iface['ENG_mm']; ro = OD[dn] / 2; D_, K, nb, dh, b = FLD[dn]
    L_hose = LAY['risers']['C1' if dn == 'DN100' else 'C2']['hose_L'] + 2 * b
    z_split = z_top_face - L_hose
    f0 = disk_flange(V(x, y, z0_), V(0, 0, 1), D_, OD[dn] - 4, K, nb, dh, b); f1 = disk_flange(V(x, y, z_split - b), V(0, 0, 1), D_, OD[dn] - 4, K, nb, dh, b)
    pipe = tube(ro, 2.0, V(x, y, z0_ + b), V(x, y, z_split - b))
    add(tag, name, Part.makeCompound([f0, pipe, f1, braided_hose(dn, z_split, z_top_face, x, y)]), mat, RHO[mat], 'cold' if dn == 'DN100' else 'hot', 'RC2',
        mk='make pipe; buy hose', spec=spec, sup='hose: Witzenmann HYDRA (DE) / BOA (DE) / IWKA; pipe EN 10217-7')
    return (V(x, y, z0_ + b), V(x, y, z_split - b), ro)
c1i = [i for i in E2I['interfaces'] if i['name'].startswith('C1')][0]; c2i = [i for i in E2I['interfaces'] if i['name'].startswith('C2')][0]
R1 = riser('RC2-131', 'Riser_C1_DN100_pipe_hose', 'DN100', c1i, ZF1, '1.4404',
           'DN100: 114.3x2 1.4404 pipe + DN100 PN16 flanges + braided hose DN100 L300 (1.4541 / 1.4301 braid, 250 C)')
R2 = riser('RC2-132', 'Riser_C2_DN125_pipe_hose', 'DN125', c2i, ZF2, '321H',
           'DN125: 139.7x2 1.4541 pipe + DN125 PN16 flanges + braided hose DN125 L300 (1.4541 / 1.4301 braid, rated 550 C with derating, 3 barg)')

# =====================================================================================================================
# HX-101 bought finned-tube exhaust economiser (envelope incl. its own insulation): rectangular inlet flange on the core top collar,
# DN200 outlet on top, DN32 water nozzles west (in = top, out = bottom)
HX = LAY['hx']; (hz0, hz1), (bx0, bx1), (by0, by1) = HX['z'], HX['body_x'], HX['body_y']
inl = box(X0 - RIM, X1 + RIM, Y0 - RIM, Y1 + RIM, Z1, Z1 + 20.0).cut(box(X0, X1, Y0, Y1, Z1 - 1, Z1 + 21))
body = box(bx0, bx1, by0, by1, Z1 + 20.0, hz1)
cone = Part.makeLoft([Part.makePolygon([V(bx0, by0, hz1), V(bx1, by0, hz1), V(bx1, by1, hz1), V(bx0, by1, hz1), V(bx0, by0, hz1)]),
                      Part.Wire(Part.makeCircle(ro2, V(XM, 0, hz1 + HX['cone_h']), V(0, 0, 1)))], True, True)
fo, _ = flange('DN200', V(XM, 0, hz1 + HX['cone_h']), V(0, 0, 1))
WNOZ = {}
noz = []
for tag, zw in (('in', hz1 - 60.0), ('out', Z1 + 80.0)):
    p0 = V(bx0, 0, zw); noz.append(cyl(OD['DN32'] / 2, p0 + V(1, 0, 0), p0 - V(60, 0, 0)))
    fw, bw = flange('DN32', p0 - V(60, 0, 0), V(-1, 0, 0)); noz.append(fw); WNOZ[tag] = p0 - V(60 + bw, 0, 0)
eco = inl.fuse([body, cone, fo] + noz).removeSplitter()
eco_mass = RS['HX_C2']['mass_tubes_kg'] + 45.0                      # finned tubes + casing, headers, insulation (supplier estimate)
add('HX-101', 'Economiser_FinnedTube_Envelope', eco, 'envelope', eco_mass / eco.Volume, 'hx', 'HXC2', mk='buy',
    note='%.0f kW, water 90/70 C, %.2f m3/h, gas %.0f -> 100 C, dp %.0f Pa; finned tubes %d x %d inside (sim/variant_c2/c2_calc.py)' %
         (RS['HX_C2']['Q_kW'], RS['HX_C2']['m3_h'], RS['R_C2']['Th_out_C'], RS['HX_C2']['dp_Pa'], RS['HX_C2']['n_rows'], RS['HX_C2']['n_tubes_per_row']),
    spec='standard exhaust-gas economiser: stainless finned tubes (1.4404 / 1.4301 fins), insulated casing, rect inlet flange to our drawing, DN200 PN6 outlet, DN32 PN16 water, PN6 / 110 C',
    sup='Kelvion (DE) / Schmöle (DE) / Alfa Laval Aalborg (DK)')

# =====================================================================================================================
# insulation: one removable jacket around transition + core, header boxes, riser pipes (hoses: blanket, not modelled)
INS = LAY['insulation']; ti = INS['recup_mm']; th = INS['headers_mm']
jac = box(X0 - RIM - ti, X1 + RIM + ti, Y0 - RIM - ti, Y1 + RIM + ti, zt0 + 25.0, Z1).cut(box(X0 - RIM, X1 + RIM, Y0 - RIM, Y1 + RIM, zt0, Z1 + 1))
XJ0, XJ1 = X0 - RIM - ti - 1, X1 + RIM + ti + 1
jac = jac.cut(Part.makeCompound([box(XJ0, XJ1, Y1, Y1 + 400, ZHT - HH / 2 - th, ZHT + HH / 2 + th), box(XJ0, XJ1, Y0 - 400, Y0, ZHB - HH / 2 - th, ZHB + HH / 2 + th)]))
for xl in (X0 + 40.0, X1 - 40.0): jac = jac.cut(box(xl - 10, xl + 10, -400, 400, zt0, zt1 + 1))
for (x, y), dn in ((HN['nozzle_xy'], 'DN100'), (HS['nozzle_xy'], 'DN125')):                                     # notch for nozzle / hose flanges
    jac = jac.cut(cyl(FLD[dn][0] / 2 + 5, V(x, y, zt0 - 10), V(x, y, Z1 + 10)))
CORE_ENV = box(X0 - RIM, X1 + RIM, Y0 - RIM, Y1 + RIM, zt1, Z1 + 20.0)                                          # core + collars + rims (no insulation inside)
add('RC2-140', 'Insulation_Jacket_Core', jac, 'microporous', RHO['ins'] * 1.3, 'ins', 'RC2', mk='buy', spec='microporous %d mm in 0.5 mm 1.4301 cladding, 2 removable halves' % ti,
    sup='Promat MICROTHERM (BE/DE)')
hins = []
for (y0_, y1_), zc, (x, y), dn in ((HN['y'], ZHT, HN['nozzle_xy'], 'DN100'), (HS['y'], ZHB, HS['nozzle_xy'], 'DN125')):
    ya, yb = sorted((y0_, y1_)); yo = (ya - th, yb) if yb <= Y0 + 1 else (ya, yb + th)
    hb = box(X0 - th, X1 + th, yo[0], yo[1], zc - HH / 2 - th, zc + HH / 2 + th).cut(box(X0 - 0.5, X1 + 0.5, ya - 0.5, yb + 0.5, zc - HH / 2 - 0.5, zc + HH / 2 + 0.5))
    hins.append(hb.cut(cyl(OD[dn] / 2 + 15, V(x, y, zc - 200), V(x, y, zc))).cut(CORE_ENV))
for (p0, p1, ro), t_ in ((R1, INS['risers_C1_mm']), (R2, INS['risers_C2_mm'])):
    hins.append(cyl(ro + t_, p0 + V(0, 0, 40), p1 - V(0, 0, 40)).cut(cyl(ro + 0.5, p0, p1)))
add('RC2-141', 'Insulation_Headers_Risers', Part.makeCompound(hins), 'microporous', RHO['ins'] * 1.3, 'ins', 'RC2', mk='buy',
    spec='headers 30 mm, C2 riser 30 mm, C1 riser 20 mm, clad; hoses and flanges: removable blankets', sup='Promat (BE/DE) / Rockwool (DK)')

# =====================================================================================================================
# C2F-10 one welded RHS frame: 2 rails (carry the engine feet E2C2-103, C-402, C-403), 2 cross members, 4 columns, 2 top beams
(rx0, rx1), (ry0, ry1), (xc0, xc1), (zr0, zr1) = FRM['rails_x'], FRM['rails_y'], FRM['x_cols'], FRM['z_base']
def rhs(x0, x1, y0, y1, z0, z1, t=3.0, axis='x'):
    o = box(x0, x1, y0, y1, z0, z1)
    i = box(x0 - 1, x1 + 1, y0 + t, y1 - t, z0 + t, z1 - t) if axis == 'x' else box(x0 + t, x1 - t, y0 - 1, y1 + 1, z0 + t, z1 - t) if axis == 'y' else \
        box(x0 + t, x1 - t, y0 + t, y1 - t, z0 - 1, z1 + 1)
    return o.cut(i)
fr = [rhs(rx0, rx1, -ry1 - 10.0, -ry1 + 30.0, zr0, zr1), rhs(rx0, rx1, ry1 - 30.0, ry1 + 10.0, zr0, zr1)]              # rails RHS 60x40 (y +-80..120)
fr += [rhs(xc - 30, xc + 30, ycb0 - 30, ycb1 + 30, zr0, zr1, axis='y') for xc in (xc0, xc1)]                               # cross members
fr += [rhs(xc - 30, xc + 30, yc - 30, yc + 30, zr1, zb0, t=4.0, axis='z') for xc in (xc0, xc1) for yc in (ycb0, ycb1)]   # columns SHS 60x4
fr += [rhs(rx0, rx1, yc - 20, yc + 20, zb0, zb1) for yc in (ycb0, ycb1)]                                                # top beams RHS 40x40x3
add('C2F-10', 'Frame_Welded_RHS', Part.makeCompound(fr), '1.4301', RHO['1.4301'], 'frame', 'FRAME', mk='make',
    spec='one welded frame: rails RHS 60x40x3, cross members RHS 60x40x3, 4 columns SHS 60x60x4, 2 top beams RHS 40x40x3 (1.4301, or S355 hot-dip galvanised)',
    sup='local; profiles Outokumpu (FI) / Tata Steel EU')

# =====================================================================================================================
# instruments (control / protection only, accessible): TE-503 combustor inlet air, TE-512 economiser inlet gas, TE-770 + FS-770 hot water out
def probe(p, n, segs):
    p, n = vec(p), vec(n).normalize(); s, d = [], 0.0
    for L_, r_ in segs: s.append(Part.makeCylinder(r_, L_, p + n * d, n)); d += L_
    return Part.makeCompound(s)
SENS = [('TE-503', 'T2r combustor-inlet air (C2 riser, low)', R2[0] + V(0, -R2[2], 120.0), V(0, -1, 0)),
        ('TE-512', 'economiser-inlet gas (protection, dry running)', V(X1 + RIM, 0.0, Z1 + 10.0), V(1, 0, 0)),
        ('TE-770', 'hot water out 90 C', WNOZ['out'] + V(30.0, 0, OD['DN32'] / 2), V(0, 0, 1)),
        ('FS-770', 'hot water flow switch (protection)', WNOZ['out'] + V(30.0, 0, -OD['DN32'] / 2), V(0, 0, -1))]
for i, (tg, lab, p, n) in enumerate(SENS):
    add('RC2-5%02d' % (i + 1), '%s' % tg, probe(p, n, [(30.0, 7.0), (50.0, 3.0)]), 'sensor', RHO['misc'], 'sensor', 'RC2', note=lab, mk='buy',
        spec='type K MI 3 mm (gas/air) / PT1000 (water) / paddle flow switch, compression fitting on a welded boss', sup='Roessel Messtechnik (DE) / Kobold (DE)')

# =====================================================================================================================
# internal checks (the full package check: cad/engine/engine_stack_check.py with STACK_VARIANT=C2)
def overlap(a, b):
    if not a.BoundBox.intersect(b.BoundBox): return 0.0
    try: return a.common(b).Volume
    except Exception: return -1.0
JOINTS = {('RC2-101', 'RC2-111'), ('RC2-101', 'RC2-112'), ('RC2-101', 'RC2-121'), ('RC2-101', 'HX-101'), ('RC2-120', 'RC2-121'), ('RC2-111', 'RC2-131'),
          ('RC2-112', 'RC2-132'), ('RC2-121', 'C2F-10'), ('RC2-140', 'RC2-121'), ('RC2-141', 'RC2-111'), ('RC2-141', 'RC2-112'), ('RC2-141', 'RC2-131'),
          ('RC2-141', 'RC2-132'), ('RC2-140', 'RC2-101')}
chk = dict(internal=[])
tags = sorted(PARTS)
for i, a in enumerate(tags):
    for b in tags[i + 1:]:
        v = overlap(PARTS[a]['shape'], PARTS[b]['shape'])
        if v > 1.0 or v < 0:
            chk['internal'].append(dict(a=a, b=b, vol_mm3=round(v, 1), expected=(a, b) in JOINTS or (b, a) in JOINTS or 'sensor' in (PARTS[a]['group'], PARTS[b]['group'])))
bad = [r for r in chk['internal'] if not r['expected']]
say('R-C2 / economiser / frame internal overlaps > 1 mm3: %d (unexpected %d) %s' % (len(chk['internal']), len(bad), bad[:12]))
json.dump(chk, open(os.path.join(CO, 'C2_checks.json'), 'w'), indent=1)

# exports
for t, p in PARTS.items(): p['shape'].exportStep(os.path.join(OUTS[p['out']], '%s_%s.step' % (t, p['name'])))
for k in OUTS:
    sub = [p['shape'] for p in PARTS.values() if p['out'] == k]
    if sub: Part.makeCompound(sub).exportStep(os.path.join(OUTS[k], '%s_assembly.step' % k))
bb = Part.makeCompound([p['shape'] for p in PARTS.values()]).BoundBox
say('R-C2 + economiser + risers + frame bbox x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f' % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))

# interfaces
def itf(name, pos, direction, size, counterpart, **kw):
    d = dict(name=name, ENG_mm=[round(v, 2) for v in pos], ROOF_m=roof(pos), direction=direction, size=size, counterpart=counterpart); d.update(kw); return d
IF = [itf('R-C2 hot inlet (expansion joint on the version-C exhaust outlet)', [XE, 0, EF['z']], [0, 0, -1], 'DN200 PN6 EN 1092-1, face z 390', 'E3B-110 outlet flange'),
      itf('C1 riser <- E2-C2 C1', c1i['ENG_mm'], [0, 0, -1], 'DN100 PN16', 'E2C2-102 flange (facing up)'),
      itf('C2 riser -> E2-C2 C2', c2i['ENG_mm'], [0, 0, -1], 'DN125 PN16', 'E2C2-151 flange (facing up)'),
      itf('Hot water in 70 C', list(WNOZ['in']), [-1, 0, 0], 'DN32 PN16, %.2f m3/h, PN6 / 95 C' % RS['HX_C2']['m3_h'], 'absorption chiller / hot-water loop return'),
      itf('Hot water out 90 C', list(WNOZ['out']), [-1, 0, 0], 'DN32 PN16, %.1f kW at 15 C' % RS['HX_C2']['Q_kW'], 'absorption chiller generator / DHW tank'),
      itf('Stack outlet', [XM, 0, hz1 + HX['cone_h'] + FLD['DN200'][4]], [0, 0, 1], 'DN200 PN6, ~100 C, 0.40 kg/s', 'site stack (rain cap, condensate drain)'),
      itf('Frame feet', [xc0, 0, zr0], [0, 0, -1], 'cross members at x %.0f / %.0f, rails y +-80..120' % (xc0, xc1), 'roof skid / 4 anti-vibration mounts')]
json.dump(dict(subsystem='version C2 (simplified): R-C2 + economiser + risers + frame', frame='ENG mm (ROOF as variant A)',
               bbox_ENG_mm=[[round(bb.XMin), round(bb.YMin), round(bb.ZMin)], [round(bb.XMax), round(bb.YMax), round(bb.ZMax)]],
               masses_kg={t: round(p['shape'].Volume * p['rho'], 2) for t, p in PARTS.items()}, interfaces=IF),
          open(os.path.join(CO, 'C2_interfaces.json'), 'w'), indent=1, ensure_ascii=False)

# BOM: whole C2 package
rows = [['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes']]
rows += list(csv.reader(open(os.path.join(CO, 'E2C2', 'E2C2_bom.csv'))))[1:]
for t, p in PARTS.items():
    b_ = p['shape'].BoundBox
    rows.append([t, p['name'].replace('_', ' '), p['qty'], p['mk'], p['spec'] or p['mat'], '%.0f x %.0f x %.0f mm (bbox)' % (b_.XLength, b_.YLength, b_.ZLength),
                 p['sup'], round(p['shape'].Volume * p['rho'], 2), 'cad_out/variant_c2/%s/%s_%s.step' % (p['out'], t, p['name']), p['note']])
rows += [['C2-REF-CORE', 'GR180 core v13A (kept parts)', 1, 'see docs/05_phase1_core_v13A.md', '', '', '', 6.0, 'cad_out/v13A/asm_parts', 'unchanged'],
         ['C2-REF-E1', 'E1 GG turbine stage (blisk, NGV, shaft)', 1, 'see docs/engine/E1_gg_turbine.md', 'IN713LC cast / 42CrMo4', '', '', 0, 'fusion/E1/*.step', 'unchanged'],
         ['C2-REF-E3', 'E3 interduct + FPT + PMG (kept parts; collector replaced by the version-C exhaust)', 1, 'see docs/bom/engine_E3_bom.csv', '', '30 kW PMG', '', 20.0, 'cad_out/engine/E3', ''],
         ['C2-REF-EXH', 'Version-C compact exhaust (E3B-110..506)', 1, 'see docs/bom/variant_b_e3b_bom.csv + sim/variant_c', '', 'DN200 up', '', 32.0, 'cad_out/variant_c/EXH', 'unchanged'],
         ['C2-REF-FEET', 'Version-C engine feet C-402 (exhaust portal) and C-403 (rear flexure); rails C-410 replaced by C2F-10, C-401 by E2C2-103', 2, 'see cad/variant_c/c_frame.py', '', '', '', 9.0, 'cad_out/variant_c/FRAME', ''],
         ['C2-601', 'Gaskets: DN200 x2 (Thermiculite 815), DN100 x2 + DN125 x2 (Thermiculite / graphite), header boxes x2 and economiser inlet (Thermiculite tape), DN32 x2 (EPDM)', 1, 'buy', 'EN 1514', '', 'Klinger (AT) / Flexitallic (UK)', 1.0, '', ''],
         ['C2-602', 'Bolting: DN200 8 x M16 x2, DN100 8 x M16 x3, DN125 8 x M16 x3, DN32 4 x M16 x2, header boxes and collars M8, frame M12', 1, 'buy', 'A4-70 / 1.4980 on hot joints', '', 'Bossard (CH) / Wuerth (DE)', 4.0, '', ''],
         ['C2-603', 'Anti-vibration mounts under the frame cross members', 4, 'buy', 'elastomer, 150 kg each', '', 'Freudenberg (DE) / Trelleborg (SE)', 2.0, '', '']]
with open(os.path.join(ROOT, 'docs', 'bom', 'variant_c2_bom.csv'), 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(rows)
tot = sum(p['shape'].Volume * p['rho'] for p in PARTS.values())
say('BOM -> docs/bom/variant_c2_bom.csv (%d rows); R-C2 + economiser + risers + frame %.1f kg' % (len(rows) - 1, tot))
open(os.path.join(CO, 'RC2_build.log'), 'w').write('\n'.join(log) + '\n')
