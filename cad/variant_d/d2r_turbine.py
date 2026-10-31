# GR180 version D2 - radial turbine stage for a BOUGHT turbocharger wheel (D4 78, 11 blades, exducer 70/21), part STEP.
# Gas path: combustor exit annulus (r 22.25..35.35) -> 7-strut turbine-end support (replaces the v13A NGV) -> turning duct
# between the housing front wall and the heat shield -> 360 deg plenum (shell r 70) -> 17-vane radial nozzle ring
# (r 56.6 -> 42.9, b 14) -> wheel -> exducer shroud -> exhaust (starts at x 176, ID 70.7).
# Numbers: sim/variant_d/d2r_turbine.py (meanline), cad/variant_d/d2r_layout.py (layout). ENG frame mm, x = engine axis.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2r_turbine.py  ->  cad_out/variant_d/D2/TURBINE/*.step + d2r_turbine_parts.json
import FreeCAD as App, Part, os, sys, json, math
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2r_layout as L
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2', 'TURBINE'); os.makedirs(OUT, exist_ok=True)
XA = V(1, 0, 0)


def rev(pts):
    """closed (x, r) polygon -> solid of revolution about x"""
    p = [V(x, 0, r) for x, r in pts] + [V(pts[0][0], 0, pts[0][1])]
    return Part.Face(Part.makePolygon(p)).revolve(V(0, 0, 0), XA, 360)


def cyl(x0, x1, r, ri=0.0):
    s = Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), XA)
    return s.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), XA)) if ri > 0 else s


def P(x, r, th):
    return V(x, r * math.cos(th), r * math.sin(th))


def bolt_holes(n, pcd, d, x0, x1, ang0=0.0):
    hs = [Part.makeCylinder(d / 2, x1 - x0 + 2, V(x0 - 1, pcd / 2 * math.cos(math.radians(ang0 + 360 * k / n)),
                                                     pcd / 2 * math.sin(math.radians(ang0 + 360 * k / n))), XA) for k in range(n)]
    return Part.makeCompound(hs)


parts = {}
W = L.WHEEL
R4, R6T, R6H = W['D4'] / 2, W['D6t'] / 2, W['D6h'] / 2
XLE = W['x_back'] + W['rim']                  # hub-side leading edge (back-disc rim face)
XEX = W['x_exit']
B4 = W['b4']


def hub(a):  return (XEX - (XEX - XLE) * math.cos(a), R4 - (R4 - R6H) * math.sin(a))
def shr(a):  return (XEX - (XEX - XLE - B4) * math.cos(a), R4 - (R4 - R6T) * math.sin(a))


# ---------------------------------------------------------------- T-101 turbine wheel (bought shaft&wheel envelope)
N_A = 24
prof = [(W['x_back'], 0.0), (W['x_back'], 9.5), (W['x_back'] + 0.0, R4 - 0.0), (XLE, R4)]
# scalloped-equivalent back disc: thin rim, thick hub (typical turbo wheel), modelled as a cone from the hub to the rim
prof = [(W['x_back'], 0.0), (W['x_back'], 14.0), (W['x_back'] + 0.6, 30.0), (W['x_back'] + 0.0, R4), (XLE, R4)]
prof += [hub(a) for a in [i / N_A * math.pi / 2 for i in range(1, N_A + 1)]]
prof += [(XEX, 7.0), (W['x_nose'], 5.0), (W['x_nose'], 0.0)]
hubsolid = rev(prof)
THM, T_HUB, T_TIP, Z = math.radians(40.0), 1.6, 0.9, W['Z']
wires = []
for i in range(17):
    s = i / 16; a = s * math.pi / 2; th = THM * s * s
    (xh, rh), (xs, rs) = hub(a), shr(a)
    rh_ = max(rh - 0.8, 1.0)
    dh, ds = T_HUB / 2 / rh_, T_TIP / 2 / rs
    wires.append(Part.makePolygon([P(xh, rh_, th - dh), P(xs, rs, th - ds), P(xs, rs, th + ds), P(xh, rh_, th + dh), P(xh, rh_, th - dh)]))
blade = Part.makeLoft(wires, True, True)
blades = []
for k in range(Z):
    b = blade.copy(); b.rotate(V(0, 0, 0), XA, 360.0 * k / Z); blades.append(b)
parts['T-101_Turbine_Wheel_D78_11bl'] = hubsolid.fuse(blades).removeSplitter()

# ---------------------------------------------------------------- T-110 radial nozzle ring (17 vanes + two side plates)
NZ = L.NOZZLE
vanes = []
a_in, a_out = 45.0, 68.0                       # vane metal angle from radial: inlet ~45, exit ~68 (meanline alpha3 68.0)
NS = 14
def camber(k):
    """theta(r) along a variable-angle spiral, from r_in to r_out"""
    pts = []; th = 0.0; r = NZ['r_in']
    dr = (NZ['r_in'] - NZ['r_out']) / NS
    for i in range(NS + 1):
        pts.append((r, th))
        f = i / NS; al = math.radians(a_in + (a_out - a_in) * f)
        th += math.tan(al) * dr / (r - dr / 2)
        r -= dr
    return pts
cl = camber(0)
for k in range(NZ['Z']):
    th0 = 2 * math.pi * k / NZ['Z']
    up, lo = [], []
    for i, (r, th) in enumerate(cl):
        f = i / NS
        t = 0.6 + 2.2 * math.sin(math.pi * min(1.0, (1 - f) * 1.15)) ** 0.8 if f < 1 else 0.6   # thickness mm
        t = max(t, 0.6)
        d = t / 2 / r
        up.append(P(NZ['x0'] - 0.5, r, th0 + th + d)); lo.append(P(NZ['x0'] - 0.5, r, th0 + th - d))
    poly = up + list(reversed(lo)) + [up[0]]
    vanes.append(Part.Face(Part.makePolygon(poly)).extrude(V(NZ['x1'] - NZ['x0'] + 1.0, 0, 0)))
pf = cyl(NZ['plate_front'][0], NZ['plate_front'][1], NZ['plate_r'][1], NZ['plate_r'][0])
pr = cyl(NZ['plate_rear'][0], NZ['plate_rear'][1], NZ['plate_r'][1], NZ['plate_rear_ri'])
parts['T-110_Radial_Nozzle_Ring_17v'] = pf.fuse(pr).fuse(vanes).removeSplitter()

# ---------------------------------------------------------------- T-115 heat shield (turning-duct inner wall + nozzle back wall)
hs = [(118.0, 21.25), (118.0, 22.25), (119.5, 27.0), (122.0, 32.5), (125.5, 37.0), (129.0, 40.0), (129.0, 58.0),
      (131.0, 58.0), (131.0, 39.0), (127.5, 35.5), (124.0, 31.0), (121.5, 26.0), (120.0, 21.25)]
parts['T-115_Heat_Shield'] = rev(hs)

# ---------------------------------------------------------------- T-116 turbine-end bearing support (7 struts, replaces NGV)
S = L.SPIDER
inner = cyl(S['x0'], S['x1'], S['r_in_wall'][1], S['r_in_wall'][0])
outer = cyl(S['x0'], L.CASING_FACE_X, S['r_out_wall'][1], S['r_out_wall'][0])
fl = cyl(S['flange'][0], S['flange'][1], S['flange'][3], S['flange'][2])
hubsleeve = cyl(100.0, S['seal_disc_x'][1], S['r_in_wall'][0] + 0.01, L.TUNNEL['rear_out_r'])   # spigot over the tunnel rear end
seal = cyl(S['seal_disc_x'][0], S['seal_disc_x'][1], L.TUNNEL['rear_out_r'] + 0.01, S['seal_bore_r'])   # labyrinth stator bore r 7.85
struts = []
for k in range(S['n_struts']):
    b = Part.makeBox(S['strut_x'][1] - S['strut_x'][0], S['r_out_wall'][0] - S['r_in_wall'][1] + 1.0, S['strut_t'],
                     V(S['strut_x'][0], S['r_in_wall'][1] - 0.5, -S['strut_t'] / 2))
    # round the leading/trailing edges: intersect with a long ellipse-ish prism (two cylinders)
    b.rotate(V(0, 0, 0), XA, 90.0 + 360.0 * k / S['n_struts'])
    struts.append(b)
spider = inner.fuse([outer, fl, hubsleeve, seal] + struts).removeSplitter()
# buffer / cooling-air holes in the web (6 x d2) and the flange bolt holes
holes = [Part.makeCylinder(1.0, 14, V(99.0, 19.4 * math.cos(math.radians(30 + 60 * k)), 19.4 * math.sin(math.radians(30 + 60 * k))), XA) for k in range(6)]
spider = spider.cut(Part.makeCompound(holes)).cut(bolt_holes(4, L.FLANGE_BOLTS['pcd'], 5.6, S['flange'][0], S['flange'][1], 45.0))
parts['T-116_Turbine_End_Support_7struts'] = spider

# ---------------------------------------------------------------- T-120 turbine housing / plenum
H = L.HOUSING
hp = [(H['x0'], H['lip_ri']), (H['x0'], H['shell_ro']), (H['x1'], H['shell_ro']), (H['x1'], H['rear_ri']),
      (H['rear_wall'][0], H['rear_ri']), (H['rear_wall'][0], H['shell_ri']), (H['front_wall'][1], H['shell_ri']),
      (H['front_wall'][1], H['lip_ri'])]
housing = rev(hp)
pads = []
for sgn in (1, -1):
    y0 = H['shell_ro'] - 3.0 if sgn > 0 else -H['mount_pad']['y_out']
    pads.append(Part.makeBox(H['mount_pad']['x'][1] - H['mount_pad']['x'][0], H['mount_pad']['y_out'] - H['shell_ro'] + 3.0,
                             H['mount_pad']['z'][1] - H['mount_pad']['z'][0], V(H['mount_pad']['x'][0], y0, H['mount_pad']['z'][0])))
tit_boss = Part.makeCylinder(6.0, 9.0, V(138.0, 0, H['shell_ro'] - 2.0), V(0, 0, 1))
housing = housing.fuse(pads + [tit_boss]).removeSplitter()
housing = housing.cut(Part.makeCylinder(2.0, 20, V(138.0, 0, H['shell_ri'] - 2), V(0, 0, 1)))       # TIT thermocouple bore
housing = housing.cut(bolt_holes(4, L.FLANGE_BOLTS['pcd'], 5.6, H['front_wall'][0], H['front_wall'][1], 45.0))
housing = housing.cut(bolt_holes(6, 50.0 * 2 - 6, 5.5, H['rear_wall'][0], H['rear_wall'][1], 0.0))
for sgn in (1, -1):                                                                                   # M10 frame bolts in the pads
    housing = housing.cut(Part.makeCylinder(5.25, 30, V(135.0, sgn * (H['mount_pad']['y_out'] - 6.0), -15), V(0, 0, 1)))
parts['T-120_Turbine_Housing_Plenum'] = housing

# ---------------------------------------------------------------- T-121 exducer shroud + exhaust flange
SH = L.SHROUD
c = SH['clr']
inner_line = [(shr(a)[0], shr(a)[1] + c) for a in [i / N_A * math.pi / 2 for i in range(0, N_A + 1)]]
inner_line[0] = (SH['x0'], inner_line[0][1])
inner_line += [(SH['x_end'], R6T + c)]
outer_line = [(SH['x_end'], SH['flange'][2]), (SH['flange'][0], SH['flange'][2]), (SH['flange'][0], R6T + c + SH['t']),
              (158.0, R6T + c + SH['t'] + 0.6), (158.0, 50.0), (155.0, 50.0), (155.0, 42.3), (SH['x0'], 42.3)]
shroud = rev(inner_line + outer_line)
shroud = shroud.cut(bolt_holes(6, SH['bolts']['pcd'], 6.6, SH['flange'][0], SH['flange'][1], 30.0))
shroud = shroud.cut(bolt_holes(6, 94.0, 5.5, 155.0, 158.0, 0.0))
parts['T-121_Exducer_Shroud_Exhaust_Flange'] = shroud

# ---------------------------------------------------------------- export
info = dict(note='D2R turbine stage parts (bought wheel envelope; nozzle/shroud/housing to make)', frame='ENG mm', parts={})
dens = {'T-101': 7.91, 'T-110': 8.19, 'T-115': 8.44, 'T-116': 8.19, 'T-120': 7.9, 'T-121': 8.44}   # IN713C, IN718, IN625, IN718(SLM/cast), 1.4848 cast, IN625
for k, s in parts.items():
    s.exportStep(os.path.join(OUT, k + '.step'))
    bb = s.BoundBox
    m = s.Volume / 1000 * dens[k[:5]] / 1000
    info['parts'][k] = dict(valid=s.isValid(), x=[round(bb.XMin, 2), round(bb.XMax, 2)], r=round(max(abs(bb.YMax), abs(bb.YMin), abs(bb.ZMax), abs(bb.ZMin)), 1),
                            volume_cm3=round(s.Volume / 1000, 2), mass_kg=round(m, 3))
    if k.startswith('T-101'):
        sols = s.Solids
        vt = sum(so.Volume for so in sols)
        xc = sum(so.Volume * so.CenterOfMass.x for so in sols) / vt
        Ip = sum(so.MatrixOfInertia.A11 + so.Volume * (so.CenterOfMass.y ** 2 + so.CenterOfMass.z ** 2) for so in sols)
        It = sum(so.MatrixOfInertia.A22 + so.Volume * ((so.CenterOfMass.x - xc) ** 2 + so.CenterOfMass.z ** 2) for so in sols)
        rho = dens['T-101'] * 1e-6                                 # kg/mm^3 ; inertia in kg mm^2 -> kg m^2
        info['parts'][k].update(n_solids=len(sols), x_cg=round(xc, 2), Ip_kgm2=Ip * rho * 1e-6, It_kgm2=It * rho * 1e-6)
    print('%-40s valid %s  x %.1f..%.1f  r %.1f  %.3f kg' % (k, s.isValid(), bb.XMin, bb.XMax, info['parts'][k]['r'], m))
json.dump(info, open(os.path.join(OUT, 'd2r_turbine_parts.json'), 'w'), indent=1)
print('->', OUT)
