"""AURORA-1000 (1 MW, 15,000 rpm, geared) package -> one glTF for the web viewer (viewer/a1000/index.html).

Frame: rotor frame of sim/engine/a1000_rotordynamics.py, mm, x = engine axis from the gearbox coupling face (x = 0) to the
exhaust, z up, shaft axis at z = 0. Contents:
  turbine   the rev 5 CAD (cad_out/engine/A1000: NGV rings + vane, blisk disc + blade), shifted by the rotor layout offset;
            blades / vanes written once and instanced
  rotor     shaft, drums, thrust collar, couplings (segments of the rotordynamics model); impellers from the meanline
            (sim/mw1_meanline.json: D2, inducer radii, b2, 13 + 13 blades)
  rest      casings, inlet plenum, can combustor and scroll, exhaust diffuser and collector, bearings, recuperator and ducts,
            epicyclic gearbox, generator, lube module and skid: concept envelopes from docs/08 (dimensions there), not
            detail design; they show the arrangement and the sizes
Run:   freecadcmd -c "exec(open('cad/engine/a1000_viewer_export.py').read())"     (GR180_ROOT = repo root)
Writes: viewer/a1000/a1000.json (glTF 2.0, embedded buffer; git-ignored, regenerate), viewer/a1000/a1000_parts.json
Viewer: viewer/a1000/index.html (published as a claude.ai artifact with a1000.json beside it)
Fusion: A1000_STEP=1 writes fusion/A1000_pkg/*.step + pkg.json instead of the glTF (turbine pieces are referenced from
        fusion/A1000, which also stands in for cad_out/engine/A1000 when that is not built); import with
        fusion/AURORA1000_Package/AURORA1000_Package.py
"""
import base64
import json
import math
import os
import sys

import numpy as np
import FreeCAD as App
import Part
import MeshPart

ROOT = os.environ.get('GR180_ROOT') or os.getcwd()
sys.path.insert(0, os.path.join(ROOT, 'sim', 'engine')); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_rotordynamics as RD                                   # noqa: E402  (rotor layout, a1000_turbine as RD.A)
sys.argv = _argv
A = RD.A
CAD = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
FUS = os.path.join(ROOT, 'fusion', 'A1000')                        # same pieces as STEP (fusion/export_a1000_parts.py)
STEP_OUT = os.path.join(ROOT, 'fusion', 'A1000_pkg') if os.environ.get('A1000_STEP') else None
OUT = os.path.join(ROOT, 'viewer', 'a1000'); os.makedirs(OUT, exist_ok=True)
V = App.Vector
DES = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
ML = json.load(open(os.path.join(ROOT, 'sim', 'mw1_meanline.json')))
PARTS = json.load(open(os.path.join(CAD, 'A1000_parts.json') if os.path.exists(os.path.join(CAD, 'A1000_parts.json'))
                       else os.path.join(FUS, 'parts.json')))
SRC = {}                                                            # id(shape) -> turbine piece name (STEP export)

GROUPS = {   # name: (rgba, metallic, roughness)
    'turbine': ((0.80, 0.81, 0.84, 1.0), 0.85, 0.30),
    'ngv':     ((0.86, 0.52, 0.28, 1.0), 0.60, 0.45),
    'rotor':   ((0.55, 0.58, 0.63, 1.0), 0.85, 0.30),
    'comp':    ((0.70, 0.78, 0.86, 1.0), 0.80, 0.30),
    'casing':  ((0.42, 0.45, 0.49, 1.0), 0.50, 0.55),
    'comb':    ((0.78, 0.45, 0.22, 1.0), 0.60, 0.45),
    'exhaust': ((0.60, 0.56, 0.52, 1.0), 0.60, 0.50),
    'bearing': ((0.85, 0.70, 0.25, 1.0), 0.80, 0.35),
    'recup':   ((0.66, 0.70, 0.66, 1.0), 0.60, 0.45),
    'gearbox': ((0.30, 0.45, 0.40, 1.0), 0.40, 0.60),
    'gen':     ((0.22, 0.36, 0.62, 1.0), 0.40, 0.55),
    'aux':     ((0.86, 0.72, 0.20, 1.0), 0.40, 0.60),
    'skid':    ((0.25, 0.27, 0.30, 1.0), 0.50, 0.60),
    'hot':     ((0.72, 0.55, 0.42, 1.0), 0.60, 0.45),
}
parts = []


def add(name, group, shape, inst=None, **meta):
    if shape is None or shape.isNull() or shape.Volume <= 0:
        print('skip', name); return
    parts.append(dict(name=name, group=group, shape=shape, inst=inst, meta=meta))


def rev(poly, angle=360.0):
    """solid of revolution of an (x, r) polygon about the x axis"""
    pts = [V(x, 0, r) for x, r in poly]
    if (pts[0] - pts[-1]).Length > 1e-6: pts.append(pts[0])
    f = Part.Face(Part.makePolygon(pts))
    return f.revolve(V(0, 0, 0), V(1, 0, 0), angle)


def tube(x0, x1, ro, ri=0.0):
    return rev([(x0, ri), (x1, ri), (x1, ro), (x0, ro)])


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(r, h, p, d):
    return Part.makeCylinder(r, h, V(*p), V(*d))


def shell_cyl(ro, ri, h, p, d):
    return cyl(ro, h, p, d).cut(cyl(ri, h, p, d))


def read(name, dx=0.0):
    p = os.path.join(CAD, name + '.brep')
    s = Part.Shape(); s.read(p if os.path.exists(p) else os.path.join(FUS, name + '.step'))
    s.translate(V(dx, 0, 0)); SRC[id(s)] = name; return s


def mass(shape, rho):                                               # kg, rho in kg/m3, volume in mm3
    return round(shape.Volume * 1e-9 * rho, 1)


# ------------------------------------------------------------------------------------------------ rotor (dynamics model)
R = RD.rotor('A')
b1 = R['discs']['blisk1']
X_OFF = b1['hub'][0] - (0.5 * (A.X_LE['R1'] + A.X_TE['R1']) - A.DISC['R1']['hub_w'] / 2)
Z = {k: DES[k]['Z'] for k in ('N1', 'R1', 'N2', 'R2')}
x_n1 = X_OFF + DES['N1']['x_le']; x_r2 = X_OFF + DES['R2']['x_te']
print('turbine offset %.1f mm: NGV1 LE x %.0f, R2 TE x %.0f, bearings %s' % (X_OFF, x_n1, x_r2, [round(b) for b in R['brg']]))

# ------------------------------------------------------------------------------------------------ turbine (rev 5 CAD)
RHO_M = 8540.0
add('NGV1 rings', 'ngv', read('A1000_N1_rings', X_OFF), desc='NGV1 inner and outer rings, cast integral with the vanes',
    material='MAR-M247, aluminide + TBC', mass_kg=round(PARTS['A1000_N1_rings']['mass_kg'], 1))
add('NGV1 vane x%d' % Z['N1'], 'ngv', read('A1000_N1_vane', X_OFF), inst=[360.0 * k / Z['N1'] for k in range(Z['N1'])],
    desc='%d vanes, axial chord %.0f mm, throat 174 cm2 (M 0.75)' % (Z['N1'], DES['N1']['x_te'] - DES['N1']['x_le']),
    material='MAR-M247 + TBC', mass_kg=round(Z['N1'] * PARTS['A1000_N1_vane']['mass_kg'], 1))
add('Blisk 1 disc', 'turbine', read('A1000_R1_disc', X_OFF), desc='stage-1 blisk disc (bore-less, curvic hubs), vacuum cast + HIP',
    material='MAR-M247', mass_kg=round(PARTS['A1000_R1_disc']['mass_kg'], 1))
add('Blisk 1 blade x%d' % Z['R1'], 'turbine', read('A1000_R1_blade', X_OFF), inst=[360.0 * k / Z['R1'] for k in range(Z['R1'])],
    desc='%d blades cast integral with the disc; root 100 MPa at 865 C, creep 2.6e5 h' % Z['R1'], material='MAR-M247',
    mass_kg=round(Z['R1'] * PARTS['A1000_R1_blade']['mass_kg'], 1))
add('NGV2 rings', 'ngv', read('A1000_N2_rings', X_OFF), desc='NGV2 inner and outer rings', material='MAR-M247',
    mass_kg=round(PARTS['A1000_N2_rings']['mass_kg'], 1))
add('NGV2 vane x%d' % Z['N2'], 'ngv', read('A1000_N2_vane', X_OFF), inst=[360.0 * k / Z['N2'] for k in range(Z['N2'])],
    desc='%d long-chord vanes, axial chord %.0f mm, throat 278 cm2 (M 0.81)' % (Z['N2'], DES['N2']['x_te'] - DES['N2']['x_le']),
    material='MAR-M247', mass_kg=round(Z['N2'] * PARTS['A1000_N2_vane']['mass_kg'], 1))
add('Blisk 2 disc', 'turbine', read('A1000_R2_disc', X_OFF), desc='stage-2 blisk disc', material='MAR-M247',
    mass_kg=round(PARTS['A1000_R2_disc']['mass_kg'], 1))
add('Blisk 2 blade x%d' % Z['R2'], 'turbine', read('A1000_R2_blade', X_OFF), inst=[360.0 * k / Z['R2'] for k in range(Z['R2'])],
    desc='%d blades; root 188 MPa at 723 C' % Z['R2'], material='MAR-M247', mass_kg=round(Z['R2'] * PARTS['A1000_R2_blade']['mass_kg'], 1))

# ------------------------------------------------------------------------------------------------ shaft and drums
LAB = {0: ('Coupling shaft', 'output shaft to the gearbox coupling'), 1: ('Journal / thrust shaft', 'front journal bearing and thrust collar'),
       3: ('Interstage spacer', 'curvic coupling both ends, return-channel seal'), 5: ('Compressor-turbine drum', 'tie bolt inside, labyrinth seals'),
       7: ('Turbine interstage spacer', 'under NGV2, interstage seal'), 9: ('Rear stub shaft', 'rear journal bearing in the exhaust hub')}
RHO = dict(steel=7850, in718=8190)
for i, (x0, x1, od, idd, mat, carries) in enumerate(R['seg']):
    if i not in LAB: continue
    s = tube(x0, x1, od / 2, idd / 2); n, d = LAB[i]
    add(n, 'rotor', s, desc=d, material={'steel': '42CrMo4', 'in718': 'IN718'}[mat], mass_kg=mass(s, RHO[mat]))
s = tube(147.5, 172.5, 110.0, 55.0)
add('Thrust collar', 'rotor', s, desc='double-acting thrust collar, cold end', material='42CrMo4', mass_kg=mass(s, 7850))
s = tube(R['tie'][0], R['tie'][1], R['tie'][2] / 2)
add('Tie bolt', 'rotor', s, desc='preloaded tie bolt, collar to blisk-1 hub (clamps the curvic stack)', material='IN718', mass_kg=mass(s, 8190))
s = tube(-190.0, 0.0, 110.0, 40.0).fuse(tube(-120.0, -70.0, 125.0, 40.0))
add('High-speed coupling', 'rotor', s, desc='diaphragm coupling turbine -> gearbox, 15,000 rpm', material='steel, disc packs')


# ------------------------------------------------------------------------------------------------ impellers
def impeller(name, st, x0, mat, rho):
    r2 = st['D2'] / 2 * 1e3; r1h = st['r1h'] * 1e3; r1t = st['r1t'] * 1e3; b2 = st['b2'] * 1e3
    L = 0.30 * 2 * r2; tb = 7.0; bore = 24.0
    hub = [(x0 + (L - tb) * math.sin(p), r1h + (r2 - r1h) * (1 - math.cos(p))) for p in np.linspace(0, math.pi / 2, 24)]
    s = rev([(x0, bore)] + hub + [(x0 + L, r2), (x0 + L, bore)])
    add(name + ' hub', 'comp', s, desc='%s, D2 %.0f mm, U2 %.0f m/s, PR %.2f' % (st['name'], 2 * r2, st['U2'], st['pr']), material=mat,
        mass_kg=mass(s, rho))
    # blades: hub curve -> shroud curve stations, wrapped; 13 full + 13 splitters (thin lofted plates)
    Lh = L - tb; Ls = L - tb - b2
    def station(p, th, t=2.8):
        hx, hr = x0 + Lh * math.sin(p), r1h + (r2 - r1h) * (1 - math.cos(p))
        sx, sr = x0 + Ls * math.sin(p), r1t + (r2 - r1t) * (1 - math.cos(p))
        pts = []
        for (x, r, sg) in ((hx, hr + 0.5, -1), (sx, sr - 0.6, -1), (sx, sr - 0.6, 1), (hx, hr + 0.5, 1)):
            a = th + sg * t / 2 / r
            pts.append(V(x, r * math.sin(a), r * math.cos(a)))
        return Part.makePolygon(pts + [pts[0]])
    def blade(p0):
        ps = np.linspace(p0, math.pi / 2 * 0.995, 10)
        wires = [station(p, 1.05 * (p / (math.pi / 2)) ** 1.6 - 0.25 * (p / (math.pi / 2)) ** 6) for p in ps]
        return Part.makeLoft(wires, True, False)
    nb = 13
    add(name + ' blade x%d' % nb, 'comp', blade(0.02), inst=[360.0 * k / nb for k in range(nb)], desc='full blades, backsweep 40 deg',
        material=mat)
    add(name + ' splitter x%d' % nb, 'comp', blade(0.55), inst=[360.0 * (k + 0.5) / nb for k in range(nb)], desc='splitter blades',
        material=mat)
    return dict(r2=r2, r1t=r1t, r1h=r1h, b2=b2, L=L, x0=x0, Ls=Ls)


c1, c2 = ML['compressor']
x_i1 = R['seg'][2][0]; x_i2 = R['seg'][4][0]
I1 = impeller('Impeller 1', c1, x_i1, 'Al 2618-T61, 5-axis milled', 2760)
I2 = impeller('Impeller 2', c2, x_i2, 'Ti-6Al-4V, 5-axis milled', 4430)

# ------------------------------------------------------------------------------------------------ compressor casing
def shroud_shell(I, t=10.0, gap=0.6):
    """casing wall following the shroud line from the inducer to the exit, then the diffuser front wall to 1.6 r2"""
    pin = [(I['x0'] + I['Ls'] * math.sin(p), I['r1t'] + gap + (I['r2'] - I['r1t']) * (1 - math.cos(p))) for p in np.linspace(0, math.pi / 2, 20)]
    xe = pin[-1][0]
    inner = [(I['x0'] - 40.0, I['r1t'] + gap)] + pin + [(xe, 1.6 * I['r2'])]
    outer = [(x - t, r + t) for x, r in inner[::-1]]
    return rev(inner + outer)


xd1 = I1['x0'] + I1['Ls']; xd2 = I2['x0'] + I2['Ls']
cas = shroud_shell(I1).fuse(shroud_shell(I2))
# diffuser rear walls (behind the impeller exit), return channel bend and the stage-2 discharge collector
cas = cas.fuse(tube(xd1 + I1['b2'] + 6, xd1 + I1['b2'] + 18, 1.6 * I1['r2'], I1['r2'] + 6))
bend = rev([(xd1 - 10, 1.6 * I1['r2'] + 10), (xd1 + I1['b2'] + 18, 1.6 * I1['r2'] + 10), (xd1 + I1['b2'] + 50, 1.6 * I1['r2'] - 20),
            (xd1 + I1['b2'] + 50, 1.6 * I1['r2'] - 40), (xd1 + I1['b2'] + 30, 1.6 * I1['r2'] - 40), (xd1 + I1['b2'] + 30, 1.6 * I1['r2'] - 5),
            (xd1 - 10, 1.6 * I1['r2'] - 5)])
cas = cas.fuse(bend).fuse(tube(I2['x0'] - 45, I2['x0'] - 30, 1.6 * I1['r2'] - 20, I2['r1t'] + 5))
cas = cas.fuse(tube(xd2 + I2['b2'] + 6, xd2 + I2['b2'] + 18, 1.6 * I2['r2'], I2['r2'] + 6))
col = Part.makeTorus(1.75 * I2['r2'], 0.20 * I2['r2'], V(xd2 - 5, 0, 0), V(1, 0, 0))
col = col.cut(Part.makeTorus(1.75 * I2['r2'], 0.20 * I2['r2'] - 8, V(xd2 - 5, 0, 0), V(1, 0, 0)))
cas = cas.fuse(col)
barrel = tube(x_i1 - 40, xd2 + 40, 1.75 * I2['r2'] + 0.20 * I2['r2'] + 20, 1.75 * I2['r2'] + 0.20 * I2['r2'] + 5)
add('Compressor casing', 'casing', cas.fuse(barrel), desc='shroud walls, vaned diffusers, return channel, discharge collector (concept)',
    material='ductile iron EN-GJS-400 / Ti diffuser vanes')
# inlet: bellmouth + plenum box with the filter-house duct on top
bell = rev([(x_i1 - 40, I1['r1t'] + 0.6), (x_i1 - 40, I1['r1t'] + 10), (x_i1 - 95, I1['r1t'] + 70), (x_i1 - 105, I1['r1t'] + 70),
            (x_i1 - 50, I1['r1t'] + 0.6)])
plen = box(30, x_i1 - 40, -380, 380, -380, 380).cut(box(42, x_i1 - 40, -368, 368, -368, 368))
plen = plen.cut(cyl(I1['r1t'] + 70, 30, (x_i1 - 60, 0, 0), (1, 0, 0)))
duct = box(-10, x_i1 - 10, -300, 300, 380, 1350).cut(box(2, x_i1 - 22, -288, 288, 370, 1351))
add('Air inlet plenum + bellmouth', 'casing', plen.fuse(bell).fuse(duct), desc='radial-to-axial inlet; duct up to the filter house and the absorption-chiller inlet-air cooler',
    material='steel sheet, acoustic lining')

# ------------------------------------------------------------------------------------------------ turbine casing, scroll, combustor
rt_tip = A.r_tip(A.X_LE['R2']) + 8
tcas = tube(x_n1 - 20, x_r2 + 10, 330.0, rt_tip).fuse(tube(x_n1 - 40, x_n1 - 20, 420.0, 255.0))
add('Turbine casing + shroud carrier', 'casing', tcas, desc='shroud carrier (1.4828) at ~550 / 500 C for 0.45 / 0.55 mm running tip clearance',
    material='1.4828 + honeycomb shroud (Hastelloy X)')
ins = tube(x_n1 - 20, x_r2 + 10, 400.0, 332.0)
add('Turbine casing insulation', 'casing', ins, desc='ceramic-fibre blanket, skin <= 60 C', material='insulation')
xs_ = x_n1 - 72
scroll = Part.makeTorus(330.0, 65.0, V(xs_, 0, 0), V(1, 0, 0)).cut(Part.makeTorus(330.0, 59.0, V(xs_, 0, 0), V(1, 0, 0)))
feed = rev([(xs_ + 40, 272), (x_n1 + 1, A.r_hub(0.0) - 2), (x_n1 + 1, A.r_hub(0.0) - 8), (xs_ + 30, 266)]).fuse(
    rev([(xs_ + 40, 388), (x_n1 + 1, A.r_tip(0.0) + 2), (x_n1 + 1, A.r_tip(0.0) + 8), (xs_ + 30, 394)]))
add('Combustor-to-NGV1 scroll', 'comb', scroll.fuse(feed), desc='hot-gas scroll from the can to the NGV1 annulus (950 C)', material='Haynes 230')
can_x = xs_; can = shell_cyl(210.0, 200.0, 1000.0, (can_x, 0, 470.0), (0, 0, 1))
can = can.fuse(Part.makeSphere(210.0, V(can_x, 0, 1470.0)).cut(Part.makeSphere(200.0, V(can_x, 0, 1470.0))).cut(box(can_x - 300, can_x + 300, -300, 300, 1170, 1470)))
can = can.fuse(shell_cyl(150.0, 140.0, 80.0, (can_x, 0, 390.0), (0, 0, 1)))
add('Can combustor (DLE)', 'comb', can, desc='one external vertical can, lean premixed (DLE), NOx < 25 ppm; air 613 C from the recuperator',
    material='casing 1.4828, liner Hastelloy X + TBC')
inj = cyl(45.0, 160.0, (can_x, 0, 1650.0), (0, 0, 1)).fuse(cyl(18.0, 120.0, (can_x + 120, 0, 1560.0), (0.4, 0, 1)))
add('Fuel injector + igniter', 'comb', inj, desc='premix injector (city gas 3.5 bar, no booster) and igniter', material='Hastelloy X')

# ------------------------------------------------------------------------------------------------ exhaust
xe0 = x_r2 + 10; xe1 = xe0 + 420
dif = rev([(xe0, rt_tip), (xe1, 430.0), (xe1, 440.0), (xe0, rt_tip + 10)])
hub = rev([(xe0, A.r_hub(A.X_TE['R2']) - 2), (xe1 - 80, 150.0), (xe1 - 80, 140.0), (xe0, A.r_hub(A.X_TE['R2']) - 12)])
struts = None
for k in range(5):
    st = box(R['brg'][1] - 40, R['brg'][1] + 60, -9, 9, 150.0, 295.0)
    st.rotate(V(0, 0, 0), V(1, 0, 0), 72.0 * k)
    struts = st if struts is None else struts.fuse(st)
add('Exhaust diffuser + 5 struts', 'exhaust', dif.fuse(hub).fuse(struts), desc='annular diffuser to the collector; oil and buffer air through the struts',
    material='1.4828')
coll = box(xe1, xe1 + 520, -560, 560, -560, 560).cut(box(xe1 + 10, xe1 + 510, -550, 550, -550, 550))
coll = coll.cut(cyl(430.0, 20, (xe1 - 5, 0, 0), (1, 0, 0)))
coll = coll.fuse(shell_cyl(300.0, 290.0, 290.0, (xe1 + 260, 560.0, 0), (0, 1, 0)))
add('Exhaust collector', 'exhaust', coll, desc='collector box, side outlet DN600 to the recuperator hot side (approx. 560 C)', material='1.4828')

# ------------------------------------------------------------------------------------------------ bearings
for i, xb in enumerate(R['brg']):
    s = tube(xb - 35, xb + 35, 150.0, 56.0).fuse(tube(xb - 15, xb + 15, 175.0, 150.0))
    add('Journal bearing %d (tilting pad + SFD)' % (i + 1), 'bearing', s, desc='tilting-pad journal D110 x 55, squeeze-film damper D150, cage spring 2.5e7 N/m',
        material='steel / babbitt pads')
s = tube(147.0, 178.0, 175.0, 112.0)
add('Thrust bearing', 'bearing', s, desc='double-acting tilting-pad thrust bearing, shared oil with the gearbox', material='steel / babbitt')

# ------------------------------------------------------------------------------------------------ recuperator and ducts
YR = 1450.0
rec = box(-900, 1900, YR - 600, YR + 600, -700, 900)
add('Recuperator (bought in)', 'recup', rec, desc='primary-surface / plate-fin, 3.1 MW, effectiveness 0.90, 347 stainless; about 2.8 x 1.2 x 1.6 m, 2-3 t',
    material='AISI 347')
ducts = shell_cyl(150.0, 142.0, YR - 600 - 300, (xd2 + 8, 300.0, 0), (0, 1, 0))                     # compressor discharge -> recuperator
hot = shell_cyl(150.0, 142.0, YR - 300, (can_x, 0.0, 1250.0), (0, 1, 0))                            # hot air -> can
hot = hot.fuse(shell_cyl(150.0, 142.0, 500.0, (can_x, YR - 300, 900.0), (0, 0, 1))).fuse(Part.makeSphere(150.0, V(can_x, YR - 300, 1250.0)).cut(Part.makeSphere(142.0, V(can_x, YR - 300, 1250.0))))
ducts = ducts.fuse(hot).fuse(shell_cyl(300.0, 290.0, 900.0, (-400, YR, 900.0), (0, 0, 1)))          # exhaust stack -> CCHP
add('Recuperator ducts', 'recup', ducts, desc='compressor air DN300 in, hot air DN300 to the can, exhaust DN600 in, outlet DN600 to the hot-water / chiller heat exchanger',
    material='321 stainless, insulated')

# ------------------------------------------------------------------------------------------------ gearbox, generator, aux, skid
gb = cyl(340.0, 760.0, (-1000.0, 0, 0), (1, 0, 0)).fuse(cyl(370.0, 40.0, (-1000.0, 0, 0), (1, 0, 0))).fuse(cyl(370.0, 40.0, (-280.0, 0, 0), (1, 0, 0)))
gb = gb.fuse(box(-950, -330, -380, 380, -700, -300)).fuse(cyl(90.0, 50.0, (-240.0, 0, 0), (1, 0, 0)))
add('Epicyclic gearbox 10:1', 'gearbox', gb, desc='star epicyclic, 15,000 -> 1,500 rpm, 1,100 kW, API 677 / AGMA 6123, >= 98.5 %; about 0.5-0.7 t',
    material='bought in (Flender, Allen, Renk, ZF)')
add('Starter motor', 'gearbox', cyl(130.0, 380.0, (-760.0, -340.0, 260.0), (0, -1, 0)), desc='AC starter + VFD 60-80 kW on the accessory pad',
    material='bought in')
lsc = tube(-1300.0, -1000.0, 160.0, 0.0).fuse(tube(-1180.0, -1120.0, 230.0, 160.0))
add('Low-speed coupling', 'gearbox', lsc, desc='disc coupling gearbox -> generator, 1,500 rpm', material='bought in')
gen = box(-3400, -1300, -525, 525, -700, 450).fuse(cyl(560.0, 1900.0, (-3300.0, 0, 0), (1, 0, 0)))
gen = gen.fuse(box(-3000, -1700, -450, 450, 450, 800)).fuse(box(-2300, -1900, 525, 800, -300, 200))
gen = gen.fuse(cyl(80.0, 120.0, (-1420.0, 0, 0), (1, 0, 0)))
add('Synchronous generator', 'gen', gen, desc='4-pole brushless, 1,250 kVA, 400 V, 1,500 rpm, IP54 for Borazjan dust; about 2.1 x 1.05 x 1.3 m, 3-3.5 t',
    material='bought in')
add('Lube oil module', 'aux', box(-1250, -150, -1250, -450, -700, 0), desc='tank, pumps, cooler, filters; ISO VG 32 shared by the turbine and the gearbox',
    material='bought in')
sk = None
for y in (-1100.0, 1050.0):
    b = box(-3500, 2400, y - 150, y + 150, -1000, -700).cut(box(-3500, 2400, y - 140, y + 140, -985, -715)).fuse(box(-3500, 2400, y - 8, y + 8, -985, -715))
    sk = b if sk is None else sk.fuse(b)
for x in np.arange(-3400.0, 2400.0, 900.0):
    sk = sk.fuse(box(x, x + 160, -1100, 1050, -985, -715))
sk = sk.fuse(box(-900, 1900, YR - 650, YR + 650, -1000, -700).cut(box(-890, 1890, YR - 640, YR + 640, -1001, -699)))
add('Base frame (skid)', 'skid', sk, desc='welded steel base frame, about 5.9 m with the side-mounted recuperator', material='S355 sections')

# ------------------------------------------------------------------------------------------------ STEP for Fusion
if STEP_OUT:
    os.makedirs(STEP_OUT, exist_ok=True)
    pkg = dict(frame='rotor frame, mm, x = engine axis from the gearbox coupling face, z up', x_offset_turbine=X_OFF,
               groups={g: dict(rgb=[round(255 * c) for c in rgba[:3]]) for g, (rgba, _, _) in GROUPS.items()}, parts=[])
    for p in parts:
        e = dict(name=p['name'], group=p['group'], inst=p['inst'] or [0.0],
                 **{k: v for k, v in p['meta'].items() if v not in (None, '')})
        if id(p['shape']) in SRC:                                   # turbine piece: fusion/A1000/<piece>.step shifted by X_OFF
            e.update(step='../A1000/%s.step' % SRC[id(p['shape'])], dx=X_OFF)
        else:
            fn = ''.join(c if c.isalnum() else '_' for c in p['name']).strip('_') + '.step'
            p['shape'].exportStep(os.path.join(STEP_OUT, fn)); e.update(step=fn, dx=0.0)
        pkg['parts'].append(e); print('step  %-40s %s' % (p['name'], e['step']), flush=True)
    # rotor rev 1 (cad/engine/a1000_rotor.py --cad): the detailed stack, blisks with arms and bearings replace the
    # rotor-dynamics segments, the plain discs and the bearing envelopes
    rotor_json = os.path.join(ROOT, 'fusion', 'A1000_rotor', 'parts.json')
    if os.path.exists(rotor_json):
        old = lambda e: (e['group'] in ('rotor', 'bearing') and e['name'] != 'High-speed coupling') or e['name'] in ('Blisk 1 disc', 'Blisk 2 disc')
        pkg['parts'] = [e for e in pkg['parts'] if not old(e)]
        gmap = dict(shaft='rotor', tie='rotor', drum='rotor', studs='rotor', blisk='turbine', pads='bearing', carrier='bearing',
                    cage='bearing', housing='bearing')
        for name, q in json.load(open(rotor_json))['parts'].items():
            pkg['parts'].append(dict(name=name, group=gmap[q['group']], inst=[0.0], material=q['material'], mass_kg=q['mass_kg'],
                                     step='../A1000_rotor/' + q['step'], dx=0.0))
        print('rotor rev 1 parts from fusion/A1000_rotor')
    # hot section rev 1 (cad/engine/a1000_hot_section.py --cad): split outer casing, carriers, shrouds, diaphragms, pins
    hot_json = os.path.join(ROOT, 'fusion', 'A1000_hot', 'parts.json')
    if os.path.exists(hot_json):
        pkg['parts'] = [e for e in pkg['parts'] if e['name'] not in ('Turbine casing + shroud carrier', 'Turbine casing insulation')]
        for name, q in json.load(open(hot_json))['parts'].items():
            pkg['parts'].append(dict(name=name, group='casing' if q['group'] == 'casing' else 'hot', inst=[0.0], material=q['material'],
                                     mass_kg=q['mass_kg'], step='../A1000_hot/' + q['step'], dx=0.0))
        print('hot section rev 1 parts from fusion/A1000_hot')
    json.dump(pkg, open(os.path.join(STEP_OUT, 'pkg.json'), 'w'), indent=1)
    print('fusion/A1000_pkg: %d parts' % len(pkg['parts']))
    raise SystemExit(0)


# ------------------------------------------------------------------------------------------------ tessellate -> glTF
def tess(shape):
    bb = shape.BoundBox
    tol = max(0.03, min(3.0, bb.DiagonalLength * 0.0015))
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=tol, AngularDeflection=0.12, Relative=False)
    pts, tris = m.Topology
    if not tris: return None, None, tol
    return np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float32), np.array(tris, dtype=np.uint32).reshape(-1), tol


chunks, bufviews, accessors, meshes, materials, nodes = [], [], [], [], [], []
offset = 0


def push(arr, target):
    global offset
    b = arr.tobytes(); pad = (-len(b)) % 4
    chunks.append(b + b'\0' * pad); bufviews.append(dict(buffer=0, byteOffset=offset, byteLength=len(b), target=target))
    offset += len(b) + pad; return len(bufviews) - 1


mat_index = {}
for g, (rgba, met, rough) in GROUPS.items():
    mat_index[g] = len(materials)
    materials.append(dict(name=g, pbrMetallicRoughness=dict(baseColorFactor=list(rgba), metallicFactor=met, roughnessFactor=rough), doubleSided=True))
group_children = {g: [] for g in GROUPS}
summary = []
for p in parts:
    Vt, T, tol = tess(p['shape'])
    if Vt is None: print('no triangles', p['name']); continue
    ap = len(accessors); accessors.append(dict(bufferView=push(Vt, 34962), componentType=5126, count=len(Vt), type='VEC3',
                                               min=Vt.min(0).tolist(), max=Vt.max(0).tolist()))
    ai = len(accessors); accessors.append(dict(bufferView=push(T, 34963), componentType=5125, count=len(T), type='SCALAR'))
    meshes.append(dict(name=p['name'], primitives=[dict(attributes=dict(POSITION=ap), indices=ai, material=mat_index[p['group']])]))
    mi = len(meshes) - 1
    bb = p['shape'].BoundBox
    extras = dict(group=p['group'], **{k: v for k, v in p['meta'].items() if v not in (None, '')})
    if p['inst']:
        ang = p['inst']; x0 = 0.5 * (bb.XMin + bb.XMax)
        r_out = max(math.hypot(bb.YMax, bb.ZMax), math.hypot(bb.YMin, bb.ZMin))
        extras['size_mm'] = [round(bb.XLength), round(2 * r_out)]
        kids = []
        for a in ang:
            h = math.radians(a) / 2
            nodes.append(dict(name='%s #%d' % (p['name'], len(kids) + 1), mesh=mi, rotation=[math.sin(h), 0, 0, math.cos(h)])); kids.append(len(nodes) - 1)
        nodes.append(dict(name=p['name'], children=kids, extras=extras))
    else:
        extras['size_mm'] = [round(bb.XLength), round(bb.YLength), round(bb.ZLength)]
        nodes.append(dict(name=p['name'], mesh=mi, extras=extras))
    group_children[p['group']].append(len(nodes) - 1)
    summary.append(dict(extras, name=p['name'], tris=len(T) // 3 * len(p['inst'] or [0])))
    print('%-40s %-8s %8d tris  tol %.2f' % (p['name'], p['group'], len(T) // 3, tol), flush=True)
gnodes = []
for g, kids in group_children.items():
    if kids:
        nodes.append(dict(name=g, children=kids)); gnodes.append(len(nodes) - 1)
s = math.sqrt(0.5)
nodes.append(dict(name='AURORA-1000 (rotor frame, mm)', children=gnodes, rotation=[-s, 0, 0, s], scale=[0.001] * 3))
binb = b''.join(chunks)
gltf = dict(asset=dict(version='2.0', generator='cad/engine/a1000_viewer_export.py'), scene=0, scenes=[dict(nodes=[len(nodes) - 1])],
            nodes=nodes, meshes=meshes, materials=materials, accessors=accessors, bufferViews=bufviews,
            buffers=[dict(byteLength=len(binb), uri='data:application/octet-stream;base64,' + base64.b64encode(binb).decode())])
with open(os.path.join(OUT, 'a1000.json'), 'w') as f:
    json.dump(gltf, f, separators=(',', ':'))
json.dump(dict(x_offset_turbine=X_OFF, Z=Z, bearings=R['brg'], parts=summary), open(os.path.join(OUT, 'a1000_parts.json'), 'w'), indent=1)
print('glTF %.1f MB, %d parts, %d triangles' % (os.path.getsize(os.path.join(OUT, 'a1000.json')) / 1e6, len(summary), sum(p['tris'] for p in summary)))
