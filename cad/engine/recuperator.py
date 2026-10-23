# -*- coding: utf-8 -*-
"""GR180-CCHP  E4 RECUPERATOR - parametric FreeCAD model (Part workbench), ROOF frame in mm.

Run from the project folder (first run the calculation, which writes the core dimensions):
    python3 sim/engine/e4_recuperator_calc.py
    LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd -c "exec(open('cad/engine/recuperator.py').read())"

Outputs (cad_out/engine/E4/):
    E4_core.step               2 brazed plate-fin modules (envelopes)          E4_core_detail_sample.step  OSF fin/plate pack sample
    E4_headers_plenums.step    cold headers, hot-inlet plenum, skirt, plate, hood
    E4_ducts.step              C1 / C2 bellows spools, H1 spool + elbow, exhaust duct, bellows, flanges
    E4_supports.step           legs, pads, slide/base plates, sway struts        E4_ports.step   TC bosses, taps, drains, borescope ports
    E4_insulation.step         microporous insulation + cladding envelope       E4_assembly.step  everything except the sample
    E4_recuperator.FCStd, E4_interfaces.json, E4_iso.png;   docs/bom/engine_E4_bom.csv
Layout (see docs/engine/E4_recuperator.md): core north of the engine, plates in the y-z plane stacked along ROOF x, hot gas
flows UP (+z) through the core, cold air enters/leaves through crossflow windows on the SOUTH face (headers face the engine
flanges C1/C2), hot gas enters a bottom plenum from H1 (elbow down) and leaves through the top hood to the east flange.
The engine-side flanges C1, C2 (cad_out/engine/E2/E2_interfaces.json) and H1 (cad_out/engine/E3/E3_interfaces.json) are read from
their ENG_mm positions and converted with the ENG -> ROOF transform below (docs/06 sec.1: X = 1.880 + x/1000).  C1 is a round DN100
flange (straight spool), C2 a rectangular E2 flange (E4 carries the rect-to-round transition), H1 a DN250 flange at ENG (300, 250, 0).
"""
import os, sys, json, math, glob

def _root():
    cands = []
    try: cands.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    except NameError: pass
    cands += [os.getcwd(), os.environ.get('GR180_ROOT', '')]
    for c in cands:
        d = c
        for _ in range(4):
            if d and os.path.exists(os.path.join(d, 'docs', '06_master_design.md')): return d
            d = os.path.dirname(d)
    raise SystemExit('project root not found - run from the project folder or set GR180_ROOT')

ROOT = _root()
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'E4')
os.makedirs(OUT, exist_ok=True)

import FreeCAD as App   # noqa: E402
import Part             # noqa: E402
import Import           # noqa: E402
V = App.Vector

# ------------------------------------------------------------------------------------------------------------------
# 1. parameters (calc JSON + layout)
# ------------------------------------------------------------------------------------------------------------------
CALC = {}
_cj = os.path.join(OUT, 'E4_calc_results.json')
if os.path.exists(_cj):
    CALC = json.load(open(_cj))
D = CALC.get('design', {})
W = D.get('W', 0.28) * 1e3                 # layer width  -> ROOF y
H = D.get('H', 0.536) * 1e3                # stack height -> ROOF x
L = D.get('Ltot', 0.42) * 1e3              # flow length  -> ROOF z
LW = D.get('Ld', 0.085) * 1e3              # window / distributor length
EB = D.get('end_bar', 0.015) * 1e3         # cold-layer end bar
T_HDR = D.get('t_header', 0.0015) * 1e3
NC, NH = D.get('nc', 80), D.get('nh', 81)
FC = D.get('fin_cold', dict(p=1.2e-3, t=1.0e-4, b=2.0e-3, l=3.0e-3))
FH = D.get('fin_hot', dict(p=1.6e-3, t=1.2e-4, b=3.8e-3, l=3.2e-3))
TP = D.get('t_p', 4.0e-4) * 1e3
INS = CALC.get('insulation', {}).get('thickness_m', {})
def ins_t(key, default):
    for k, v in INS.items():
        if key in k: return v * 1e3
    return default
T_INS_HOT, T_INS_C2, T_INS_CORE, T_INS_HOOD, T_INS_C1 = (ins_t('H1 duct', 70), ins_t('cold-outlet', 65), ins_t('core block', 70),
                                                        ins_t('outlet hood', 20), ins_t('cold-inlet', 15))
T_CLAD = 0.5

# layout (ROOF mm)
X0 = 1380.0                       # core west face
X1 = X0 + H                       # core east face
XM = X0 + H / 2                   # module joint
Y_S = 8225.0                      # core south face (cold windows / headers)
Y_N = Y_S + W
YC = 0.5 * (Y_S + Y_N)
Z_CB = 375.0                      # core bottom face (hot inlet)
Z_CT = Z_CB + L                   # core top face (hot outlet)
R_HDR = 55.0                      # header half-pipe inner radius
Z_HB = Z_CB + EB + LW / 2         # bottom (cold-out) header axis
Z_HT = Z_CT - EB - LW / 2         # top (cold-in) header axis
WALL = 3.0                        # plenum / hood wall
Z_PL0 = 172.0                     # plenum bottom (outer)
Z_PLT = 350.0                     # plenum top plate (outer) ; U-skirt 350..375
X_PL1 = 2303.0                    # plenum east end (outer)
Z_HD0, Z_HD1 = Z_CT + 25.0, Z_CT + 320.0      # hood box (skirt Z_CT..Z_HD0)
Z_EXO = Z_CT + 165.0              # exhaust outlet axis on hood east wall
R_PERF = (Z_CB - 57.0)            # perforated plate level

# interface flanges (ROOF mm).  ENG -> ROOF: X = 1880 + x, Y = 7850 + y, Z = 600 + z  (docs/06 sec.1, 2026-10-23)
ENG0 = (1880.0, 7850.0, 600.0)
def eng2roof(x, y, z): return (ENG0[0] + x, ENG0[1] + y, ENG0[2] + z)
FL = {  # name: (point, direction, DN, PN) - defaults = the E2/E3 published positions (2026-10-23)
    'C1': [eng2roof(-11, 190, Z_HT - 600), (0, 1, 0), 'DN100', 'PN16'],
    'C2': [eng2roof(73.5, 170, Z_HB - 600 + 12.0), (0, 1, 0), 'DN125', 'PN16'],
    'H1': [eng2roof(300, 250, 0), (0, 1, 0), 'DN250', 'PN6'],
    'EXH': [(2900.0, 8250.0, 800.0), (1, 0, 0), 'DN250', 'PN6']}
SOURCE = {k: 'E4 default (E2/E3 JSON not found)' for k in FL}
SOURCE['EXH'] = 'docs/06 sec.3 (package east face x 2.90 after the EP-1 enlargement)'
PARTNER = {}                        # tag -> full partner-interface dict (C2: rectangular flange data)

def _scan_partner_jsons():
    """Use E2/E3 flange data if published: any dict containing a name with C1/C2/H1 and a ROOF position."""
    found = {}
    for f in glob.glob(os.path.join(ROOT, 'cad_out', 'engine', 'E[23]', '*interfaces*.json')):
        try: js = json.load(open(f))
        except Exception: continue
        def walk(o, name=''):
            if isinstance(o, dict):
                nm = ' '.join(str(o.get(k, '')) for k in ('name', 'id', 'tag', 'interface')) + ' ' + name
                pos = None
                for k in ('ENG_mm', 'eng_mm'):              # preferred: engine frame, converted with this script's transform
                    v = o.get(k)
                    if isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(a, (int, float)) for a in v):
                        pos = list(eng2roof(*v)); break
                for k in ('roof_m', 'ROOF_m', 'pos_roof_m', 'position_roof_m', 'roof', 'ROOF', 'position_roof', 'pos_roof', 'position'):
                    v = o.get(k)
                    if pos is None and isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(a, (int, float)) for a in v):
                        pos = [a * 1000.0 if abs(a) < 50 else a for a in v]; break
                for tag in ('C1', 'C2', 'H1'):
                    if pos and (' %s' % tag in ' ' + nm or nm.startswith(tag)) and tag not in found:
                        d = o.get('direction') or o.get('dir') or o.get('normal') or [0, 1, 0]
                        found[tag] = (tuple(pos), tuple(d), os.path.relpath(f, ROOT), o)
                for k, v in o.items(): walk(v, str(k))
            elif isinstance(o, list):
                for v in o: walk(v, name)
        walk(js)
    return found

for tag, (pos, d, src, o) in _scan_partner_jsons().items():
    FL[tag][0], FL[tag][1] = pos, d
    SOURCE[tag] = src; PARTNER[tag] = o
    print('using %s flange from %s: %s' % (tag, src, pos))
C2_RECT = PARTNER.get('C2', {}).get('rect_inner_mm')            # E2 rectangular C2 flange (inside x, z)
_ra = PARTNER.get('C2', {}).get('round_axis_ENG_mm')
X_C2_ROUND = eng2roof(_ra[0], 0, 0)[0] if _ra else FL['C2'][0][0]   # bellows / header-nozzle axis of the C2 spool
X_PL1 = max(X_PL1, FL['H1'][0][0] + 173.0)                     # plenum east end follows the H1 entry

# EN 1092-1 flange data: D, K, n bolts, hole, thickness ; pipe OD, wall (EN 10217-7 welded 1.4550/1.4912)
FLD = {('DN100', 'PN16'): (220, 180, 8, 18, 20), ('DN125', 'PN16'): (250, 210, 8, 18, 22), ('DN250', 'PN6'): (375, 335, 12, 18, 22),
       ('DN50', 'PN16'): (165, 125, 4, 18, 18)}
PIPE = {'DN15': (21.3, 2.0), 'DN50': (60.3, 2.0), 'DN100': (114.3, 2.0), 'DN125': (139.7, 2.0), 'DN250': (273.0, 2.0)}

# ------------------------------------------------------------------------------------------------------------------
# 2. geometry helpers
# ------------------------------------------------------------------------------------------------------------------
def vec(p): return V(*p) if not isinstance(p, App.Vector) else p
def box(x0, x1, y0, y1, z0, z1): return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def cyl(r, p0, p1):
    p0, p1 = vec(p0), vec(p1); d = p1 - p0
    return Part.makeCylinder(r, d.Length, p0, d.normalize())
def tube(ro, t, p0, p1): return cyl(ro, p0, p1).cut(cyl(ro - t, vec(p0) - (vec(p1) - vec(p0)).normalize() * 1, vec(p1) + (vec(p1) - vec(p0)).normalize() * 1))

def frame_matrix(X, Y, Z, c):
    return App.Matrix(X.x, Y.x, Z.x, c.x, X.y, Y.y, Z.y, c.y, X.z, Y.z, Z.z, c.z, 0, 0, 0, 1)

def torus_seg(start, d1, d2, R, r):
    """solid torus segment: starts at 'start' with tangent d1, ends with tangent d2, bend radius R, tube radius r."""
    d1, d2 = vec(d1).normalize(), vec(d2).normalize()
    th = math.degrees(d1.getAngle(d2))
    nin = (d2 - d1 * d1.dot(d2)).normalize()
    c = vec(start) + nin * R
    X = nin * -1; Z = d1.cross(d2).normalize(); Y = Z.cross(X)
    t = Part.makeTorus(R, r, V(0, 0, 0), V(0, 0, 1), -180, 180, th)
    t.Placement = App.Placement(frame_matrix(X, Y, Z, c))
    return t, c, th

def elbow(start, d1, d2, R, ro, t):
    o, c, th = torus_seg(start, d1, d2, R, ro)
    i, _, _ = torus_seg(start, d1, d2, R, ro - t)
    d1v, d2v = vec(d1).normalize(), vec(d2).normalize()
    end = c + (vec(start) - c).multiply(1.0)
    # end point = rotate (start-c) by th about axis -> compute via geometry
    nin = (d2v - d1v * d1v.dot(d2v)).normalize()
    ang = math.radians(th)
    endp = c + (nin * -1) * (R * math.cos(ang)) + d1v * (R * math.sin(ang))
    return o.cut(i), endp, o

def disk_flange(center, n, dn, pn, bore=None):
    Df, K, nb, dh, b = FLD[(dn, pn)]
    n = vec(n).normalize(); c = vec(center)
    f = Part.makeCylinder(Df / 2, b, c, n)
    ro = PIPE[dn][0] / 2
    f = f.cut(Part.makeCylinder(bore / 2 if bore else ro - PIPE[dn][1], b + 2, c - n, n))
    a = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0)
    e1 = n.cross(a).normalize(); e2 = n.cross(e1)
    holes = [Part.makeCylinder(dh / 2, b + 2, c - n + e1 * (K / 2 * math.cos(2 * math.pi * (k + 0.5) / nb)) + e2 * (K / 2 * math.sin(2 * math.pi * (k + 0.5) / nb)), n)
             for k in range(nb)]
    for hsh in holes: f = f.cut(hsh)
    return f

def bellows(p0, p1, ro_pipe, conv_h=22.0, pitch=16.0):
    """multi-ply bellows: convolution rings (tori) + end collars + internal flow liner."""
    p0, p1 = vec(p0), vec(p1); d = p1 - p0; Lb = d.Length; n = d.normalize()
    parts = [tube(ro_pipe, 1.5, p0, p0 + n * 12), tube(ro_pipe, 1.5, p1 - n * 12, p1)]
    ncv = max(2, int((Lb - 30) / pitch))
    rm = ro_pipe + conv_h / 2; rc = conv_h / 2
    s0 = 0.5 * (Lb - (ncv - 1) * pitch)
    for k in range(ncv):
        parts.append(Part.makeTorus(rm - rc * 0.5, rc * 0.55, p0 + n * (s0 + k * pitch), n))
    parts.append(tube(ro_pipe - 4, 1.0, p0 + n * 5, p1 - n * 30))     # flow liner, welded upstream end
    parts.append(tube(ro_pipe + 2, 0.6, p0 + n * 12, p1 - n * 12))    # inner convolution base (envelope)
    return Part.makeCompound(parts)

def route(points, ro, t, R, ins=0.0):
    """straight tubes + torus bends through a polyline; returns (metal solids, keep-out solids, insulation solids,
    straight segments [(a, b)])."""
    P = [vec(p) for p in points]
    metal, keep, insul, segs = [], [], [], []
    cur = P[0]
    for i in range(1, len(P)):
        d_in = (P[i] - P[i - 1]).normalize()
        if i < len(P) - 1:
            d_out = (P[i + 1] - P[i]).normalize()
            th = d_in.getAngle(d_out)
            if th > 1e-4:
                tl = R * math.tan(th / 2)
                a = P[i] - d_in * tl
                if (a - cur).Length > 0.5:
                    metal.append(tube(ro, t, cur, a)); keep.append(cyl(ro, cur, a)); segs.append((cur, a))
                    if ins: insul.append(cyl(ro + ins, cur, a).cut(cyl(ro, cur - d_in, a + d_in)))
                e, endp, o = elbow(a, d_in, d_out, R, ro, t)
                metal.append(e); keep.append(o)
                if ins:
                    oi, _, _ = torus_seg(a, d_in, d_out, R, ro + ins)
                    insul.append(oi.cut(o))
                cur = endp
                continue
        if (P[i] - cur).Length > 0.5:
            metal.append(tube(ro, t, cur, P[i])); keep.append(cyl(ro, cur, P[i])); segs.append((cur, P[i]))
            if ins: insul.append(cyl(ro + ins, cur, P[i]).cut(cyl(ro, cur - d_in, P[i] + d_in)))
        cur = P[i]
    return metal, keep, insul, segs

def plate_xz(pts_xz, y0, y1, thick=None):
    w = Part.makePolygon([V(x, y0, z) for x, z in pts_xz] + [V(pts_xz[0][0], y0, pts_xz[0][1])])
    return Part.Face(w).extrude(V(0, y1 - y0, 0))

def boss(p, n, d=30.0, h=35.0, bore=8.0):
    p, n = vec(p), vec(n).normalize()
    b = Part.makeCylinder(d / 2, h, p - n * 5, n).cut(Part.makeCylinder(bore / 2, h + 2, p - n * 6, n))
    hexn = Part.makeCylinder(d / 2 * 0.8, 14, p + n * (h - 5), n)        # compression fitting body (simplified)
    return Part.makeCompound([b, hexn]), Part.makeCylinder(d / 2, h + 9, p - n * 5, n)

# ------------------------------------------------------------------------------------------------------------------
# 3. build
# ------------------------------------------------------------------------------------------------------------------
G = {k: [] for k in ('core', 'headers_plenums', 'ducts', 'supports', 'ports')}       # (label, shape, material, mass_override)
KEEP = []                 # outer envelopes of metal (insulation is cut by these)
INSUL = []                # insulation solids
INFO = {}

def add(grp, label, shp, mat='347H', mass=None):
    G[grp].append((label, shp, mat, mass))

# --- core: 2 brazed modules (envelope solids) ---------------------------------------------------------------
mc = CALC.get('design', {}).get('mass_core', {}).get('total', 141.6)
for k, (xa, xb) in enumerate(((X0, XM), (XM, X1))):
    add('core', 'E4-CORE-%s brazed plate-fin module %d+%d layers (envelope)' % ('AB'[k], NC // 2, NH - NC // 2), box(xa, xb, Y_S, Y_N, Z_CB, Z_CT), '347H',
        mc / 2)
KEEP.append(box(X0, X1, Y_S, Y_N, Z_CB, Z_CT))
# cold-window marks (0.5 mm proud bands on the south face inside the headers, for reference)
for zc in (Z_HB, Z_HT):
    add('core', 'E4-CORE window band z %.0f' % zc, box(X0 + 4, X1 - 4, Y_S - 0.5, Y_S, zc - LW / 2, zc + LW / 2), '347H', 0.0)

# --- cold headers: half pipes on the south face -------------------------------------------------------------
def half_pipe(zc, label, nozzle_x, dn):
    ro = R_HDR + T_HDR
    full = Part.makeCylinder(ro, H, V(X0, Y_S, zc), V(1, 0, 0)).cut(Part.makeCylinder(R_HDR, H + 2, V(X0 - 1, Y_S, zc), V(1, 0, 0)))
    south = box(X0 - 1, X1 + 1, Y_S - ro - 1, Y_S, zc - ro - 1, zc + ro + 1)
    hp = full.common(south)
    ends = []
    for xe in (X0, X1 - 4):
        e = Part.makeCylinder(ro, 4, V(xe, Y_S, zc), V(1, 0, 0)).common(box(xe - 1, xe + 5, Y_S - ro - 1, Y_S, zc - ro - 1, zc + ro + 1))
        ends.append(e)
    hole = Part.makeCylinder(PIPE[dn][0] / 2 - PIPE[dn][1], ro + 5, V(nozzle_x, Y_S - ro - 2, zc), V(0, 1, 0))
    hp = hp.cut(hole)
    add('headers_plenums', label, Part.makeCompound([hp] + ends), '347H')
    KEEP.append(Part.makeCylinder(ro, H, V(X0, Y_S, zc), V(1, 0, 0)).common(south))
    return Y_S - ro

y_hdr_top = half_pipe(Z_HT, 'E4-HDR-CI cold-inlet header R55 x %.1f (165 C)' % T_HDR, FL['C1'][0][0], 'DN100')
y_hdr_bot = half_pipe(Z_HB, 'E4-HDR-CO cold-outlet header R55 x %.1f (566 C)' % T_HDR, X_C2_ROUND, 'DN125')

# --- hot-inlet plenum, U-skirt, perforated plate, turning vanes ---------------------------------------------
pl_out = box(X0 - WALL, X_PL1, Y_S - WALL, Y_N + WALL, Z_PL0, Z_PLT)
pl_in = box(X0, X_PL1 - WALL, Y_S, Y_N, Z_PL0 + WALL, Z_PLT - WALL)
pl = pl_out.cut(pl_in).cut(box(X0, X1, Y_S, Y_N, Z_PLT - WALL - 1, Z_PLT + 1))
H1x, H1y = FL['H1'][0][0], YC
pl = pl.cut(Part.makeCylinder(PIPE['DN250'][0] / 2 - 2, 20, V(H1x, H1y, Z_PLT - 10), V(0, 0, 1)))
# stiffening ribs on the bottom (flat 40 x 4 @ 150 mm)
RIB_X = [x for x in (1500.0, 1650.0, 1800.0, 1950.0, 2100.0) if X0 + 50 < x < X_PL1 - 50]
ribs = [box(x, x + 4, Y_S - WALL, Y_N + WALL, Z_PL0 - 30, Z_PL0) for x in RIB_X]
add('headers_plenums', 'E4-PLN hot-inlet plenum 3 mm 347H with ribs (610 C)', Part.makeCompound([pl] + ribs), '347H')
KEEP.append(pl_out); KEEP += ribs
sk_o = box(X0 - 6, X1 + 6, Y_S - 6, Y_N + 6, Z_PLT, Z_CB); sk_i = box(X0 - 4.8, X1 + 4.8, Y_S - 4.8, Y_N + 4.8, Z_PLT - 1, Z_CB + 1)
add('headers_plenums', 'E4-SKT-H hot-end U-skirt 1.2 mm 347H (compliant core/plenum joint)', sk_o.cut(sk_i), '347H')
KEEP.append(sk_o)
add('headers_plenums', 'E4-PPL perforated distributor plate 2 mm, phi 0.55 (holes not modelled)', box(X0, X1, Y_S, Y_N, R_PERF, R_PERF + 2), '347H')
vanes = [plate_xz([(H1x - 140 + 70 * k, Z_PLT - WALL), (H1x - 140 + 70 * k + 2.5, Z_PLT - WALL), (H1x - 300 + 70 * k + 2.5, Z_PL0 + WALL + 30),
                   (H1x - 300 + 70 * k, Z_PL0 + WALL + 30)], Y_S, Y_N) for k in range(3)]
add('headers_plenums', 'E4-VAN turning vanes x3, 2.5 mm IN625', Part.makeCompound(vanes), 'IN625')

# --- outlet hood ------------------------------------------------------------------------------------------------
hd_out = box(X0 - WALL, X1 + WALL, Y_S - WALL, Y_N + WALL, Z_HD0, Z_HD1)
hd = hd_out.cut(box(X0, X1, Y_S, Y_N, Z_HD0 - 1, Z_HD1 - WALL))
hd = hd.cut(Part.makeCylinder(PIPE['DN250'][0] / 2 - 2, 20, V(X1 - 10, YC, Z_EXO), V(1, 0, 0)))
add('headers_plenums', 'E4-HOD outlet hood 3 mm 347H (215 C)', hd, '347H')
KEEP.append(hd_out)
sk2_o = box(X0 - 6, X1 + 6, Y_S - 6, Y_N + 6, Z_CT, Z_HD0); sk2_i = box(X0 - 4.8, X1 + 4.8, Y_S - 4.8, Y_N + 4.8, Z_CT - 1, Z_HD0 + 1)
add('headers_plenums', 'E4-SKT-C cold-end skirt 1.2 mm 347H', sk2_o.cut(sk2_i), '347H')
KEEP.append(sk2_o)

# --- C1 / C2 cold spools ----------------------------------------------------------------------------------------
def cold_spool(tag, z_hdr, y_surf, label):
    p, d, dn, pn = FL[tag]
    ro, t = PIPE[dn][0] / 2, PIPE[dn][1]
    rect = tag == 'C2' and C2_RECT
    nozzle = V(X_C2_ROUND if rect else p[0], y_surf + 8, z_hdr)   # stub end inside the header wall
    p0 = vec(p)
    straight = abs(p0.x - nozzle.x) < 1 and abs(p0.z - nozzle.z) < 1 and tuple(d) == (0, 1, 0)
    b = FLD[(dn, pn)][4]
    if rect:                                                # E2 rectangular flange -> rect-to-round transition -> bellows -> stub
        wi, hi = C2_RECT; rim = 0.5 * (PARTNER['C2']['rect_flange_mm'][0] - wi); tfl, tw = 15.0, 3.0
        xa0, xa1, za0, za1 = p0.x - wi / 2, p0.x + wi / 2, p0.z - hi / 2, p0.z + hi / 2
        fl = box(xa0 - rim, xa1 + rim, p0.y, p0.y + tfl, za0 - rim, za1 + rim).cut(box(xa0, xa1, p0.y - 1, p0.y + tfl + 1, za0, za1))
        for bx_, bz_ in PARTNER['C2'].get('rect_bolts_xz_mm', []):
            X_, _, Z_ = eng2roof(bx_, 0, bz_)
            fl = fl.cut(Part.makeCylinder(5.5, tfl + 2, V(X_, p0.y - 1, Z_), V(0, 1, 0)))
        y_t0, y_t1 = p0.y + tfl, p0.y + tfl + 40.0
        def rw(y, x0, x1, z0, z1): return Part.makePolygon([V(x0, y, z0), V(x1, y, z0), V(x1, y, z1), V(x0, y, z1), V(x0, y, z0)])
        def cw(y, r): return Part.Wire(Part.makeCircle(r, V(nozzle.x, y, z_hdr), V(0, 1, 0)))
        lo = Part.makeLoft([rw(y_t0, xa0 - tw, xa1 + tw, za0 - tw, za1 + tw), cw(y_t1, ro)], True, True)
        li = Part.makeLoft([rw(y_t0 - 0.01, xa0, xa1, za0, za1), cw(y_t1 + 0.01, ro - t)], True, True)
        bb = nozzle - V(0, 30, 0); a_ = V(nozzle.x, y_t1, z_hdr)
        parts = [fl, lo.cut(li), bellows(a_, bb, ro), tube(ro, t, bb, nozzle)]
        keep = [box(xa0 - rim, xa1 + rim, p0.y, p0.y + tfl, za0 - rim, za1 + rim), lo, cyl(ro + 12, a_, nozzle)]
        add('ducts', label, Part.makeCompound(parts), '347H'); KEEP.extend(keep)
        INFO[tag] = dict(spool_length_mm=nozzle.y - p0.y, straight=True, rect_flange_mm=PARTNER['C2']['rect_flange_mm'], bellows_y=(a_.y, bb.y))
        return
    fl = disk_flange(p0, V(*d), dn, pn)
    parts = [fl]
    if straight:
        a = p0 + V(0, b, 0); bb = nozzle - V(0, 30, 0)
        parts.append(bellows(a + V(0, 4, 0), bb, ro))
        parts.append(tube(ro, t, bb, nozzle))
        keep = [cyl(FLD[(dn, pn)][0] / 2, p0, p0 + V(0, b, 0)), cyl(ro + 12, a, nozzle)]
        L_spool = (nozzle - p0).Length
    else:                                                   # offset flange (E2 data): flange -> 2 bends -> header
        pts = [p0 + vec(d) * b, p0 + vec(d) * (b + 60), V(nozzle.x, nozzle.y - 60, nozzle.z), nozzle]
        m, k_, _, segs = route(pts, ro, t, 1.0 * PIPE[dn][0])
        parts += m; keep = k_ + [cyl(FLD[(dn, pn)][0] / 2, p0, p0 + V(0, b, 0))]
        L_spool = sum((s[1] - s[0]).Length for s in segs) + 200
    add('ducts', label, Part.makeCompound(parts), '347H')
    KEEP.extend(keep)
    INFO[tag] = dict(spool_length_mm=L_spool, straight=straight)

cold_spool('C1', Z_HT, y_hdr_top, 'E4-SP-C1 cold-inlet spool DN100: flange PN16 + 2-ply bellows 321 + stub')
cold_spool('C2', Z_HB, y_hdr_bot, 'E4-SP-C2 cold-outlet spool DN125: rectangular flange to E2 + rect-to-round transition + 2-ply bellows IN625 + stub')

# --- H1 hot spool: flange, collar, bellows, elbow down, stub into plenum ----------------------------------------
ro, t = PIPE['DN250'][0] / 2, 3.0
pH = vec(FL['H1'][0]); bH = FLD[('DN250', 'PN6')][4]
R_E = 150.0                                 # 3-piece mitre elbow R/D 0.55 (E3 H1 face at ROOF y 8.100 leaves no room for R190)
z_el_end = pH.z - R_E
y_el_start = H1y - R_E
parts = [disk_flange(pH, V(0, 1, 0), 'DN250', 'PN6')]                         # no collar: TOT = E3 TE-505A/B on the E3 transition
if y_el_start - (pH.y + bH) < 60:
    raise SystemExit('H1 flange too close to the plenum axis for the bellows spool - adjust layout')
parts.append(bellows(pH + V(0, bH, 0), V(pH.x, y_el_start, pH.z), ro))
e, endp, eo = elbow(V(pH.x, y_el_start, pH.z), V(0, 1, 0), V(0, 0, -1), R_E, ro, t)
parts.append(e)
parts.append(tube(ro, t, endp, V(endp.x, endp.y, Z_PLT - 1)))
add('ducts', 'E4-SP-H1 hot-inlet spool DN250: flange PN6, 2-ply IN625 bellows, 3-piece mitre elbow R150, stub (321H)', Part.makeCompound(parts), '321H')
KEEP += [cyl(FLD[('DN250', 'PN6')][0] / 2, pH, pH + V(0, bH, 0)), cyl(ro, pH + V(0, bH, 0), V(pH.x, y_el_start, pH.z)), eo,
         cyl(ro, endp, V(endp.x, endp.y, Z_PLT))]
ci = V(pH.x, y_el_start, z_el_end)          # tight bend (R < r_ins): insulation = sphere sweep along the elbow arc
_ap = [ci + V(0, R_E * math.sin(a), R_E * math.cos(a)) for a in [math.radians(22.5 * k) for k in range(5)]]
_pc = [cyl(ro + T_INS_HOT, _ap[k], _ap[k + 1]) for k in range(4)] + [Part.makeSphere(ro + T_INS_HOT, q) for q in _ap[1:4]]
o_ins = _pc[0].fuse(_pc[1:])
INSUL += [cyl(ro + T_INS_HOT, pH + V(0, bH, 0), V(pH.x, y_el_start, pH.z)), o_ins,
          cyl(ro + T_INS_HOT, endp, V(endp.x, endp.y, Z_PLT))]
INFO['H1_route'] = dict(elbow_R=R_E, bellows_y=(pH.y + bH, y_el_start), entry=(endp.x, endp.y, Z_PLT))

# --- exhaust duct: hood -> east, offset down/south -> bellows -> package flange EXH (2900, 8250, 800) -------------
pE = vec(FL['EXH'][0]); bE = FLD[('DN250', 'PN6')][4]
P0 = V(X1 + WALL, YC, Z_EXO); P1 = V(pE.x - 380.0, YC, Z_EXO); P2 = V(pE.x - 230.0, pE.y, pE.z); P3 = pE - V(bE, 0, 0)
m, k_, ins_e, segs = route([P0, P1, P2, P3], ro, t, 200.0, ins=0.0)
last_a, last_b = segs[-1]
bel_a = last_a + V(8, 0, 0)
m_last = m.pop()               # replace the last straight tube by stub + bellows
parts = m + [tube(ro, t, last_a, bel_a), bellows(bel_a, P3, ro), disk_flange(P3, V(1, 0, 0), 'DN250', 'PN6')]
add('ducts', 'E4-SP-EX exhaust duct DN250 x3 321: 2 mitred bends R200, 2-ply 321 bellows, flange PN6', Part.makeCompound(parts), '321H')
KEEP += k_ + [cyl(FLD[('DN250', 'PN6')][0] / 2, P3, pE)]
m2, _, ins2, _ = route([P0, P1, P2, bel_a], ro, t, 200.0, ins=T_INS_HOOD)
INSUL += ins2
INFO['EXH_route'] = dict(points=[tuple(p) for p in (P0, P1, P2, P3)], bend_R=200.0, bellows=(tuple(bel_a), tuple(P3)))

# --- supports ----------------------------------------------------------------------------------------------------
legs = [('E4-SUP-1 FIXED leg (pinned, under H1)', 2240.0, Y_S + 30), ('E4-SUP-2 guided leg (x free)', 2240.0, Y_N - 30),
        ('E4-SUP-3 sliding leg', X0 + 40, Y_S + 30), ('E4-SUP-4 sliding leg', X0 + 40, Y_N - 30)]
INFO['legs'] = []
for lbl, x, y in legs:
    sh = [box(x - 75, x + 75, y - 75, y + 75, 100, 106) if 'FIXED' not in lbl else box(x - 75, x + 75, y - 75, y + 75, 100, 106),
          box(x - 75, x + 75, y - 75, y + 75, 106, 118),                     # base plate 12 mm (slotted holes)
          box(x - 60, x + 60, y - 60, y + 60, 118, 143),                     # thermal-break pad 25 mm calcium silicate
          box(x - 25, x + 25, y - 25, y + 25, 143, Z_PL0 - 6).cut(box(x - 21, x + 21, y - 21, y + 21, 142, Z_PL0 - 5)),   # SHS 50x4
          box(x - 40, x + 40, y - 40, y + 40, Z_PL0 - 6, Z_PL0)]              # lug plate welded to plenum bottom
    add('supports', lbl + ': SHS 50x4 347H + pad + base plate', Part.makeCompound(sh), '347H')
    KEEP.append(box(x - 75, x + 75, y - 75, y + 75, 100, Z_PL0))
    INFO['legs'].append((lbl, x, y))
for k, x in enumerate((X0 + 70, X1 - 70)):
    p = V(x, Y_N + WALL, Z_HD1 - 50)
    sh = [box(x - 30, x + 30, Y_N + WALL, Y_N + WALL + 25, Z_HD1 - 80, Z_HD1 - 20),
          Part.makeCylinder(8, 8600 - (Y_N + WALL + 25), V(x, Y_N + WALL + 25, Z_HD1 - 50), V(0, 1, 0))]
    add('supports', 'E4-SUP-S%d sway strut M16 + clevis to E5 frame at y 8600 (free in z)' % (k + 1), Part.makeCompound(sh), 'A4')
    KEEP.append(box(x - 30, x + 30, Y_N + WALL, 8600, Z_HD1 - 80, Z_HD1 - 20))

# --- ports: thermocouples, pressure taps, drains, borescope -----------------------------------------------------
ports = []
def port(lbl, p, n, d=30.0, h=80.0, kind='TC'):
    b, k = boss(p, n, d, h)
    add('ports', lbl, b, '347H'); KEEP.append(k)
    ports.append(dict(tag=lbl.split()[0], label=lbl, roof_m=[round(c / 1000, 4) for c in p], dir=list(n), kind=kind))
ro_t = R_HDR + T_HDR
port('TE-502 T2 cold-in TC boss M14x1.5 (top header)', (X0 + 200, Y_S - ro_t, Z_HT), (0, -1, 0))        # west of the C1/C2 spools
port('TE-503 T2r cold-out TC boss M14x1.5 (bottom header)', (X0 + 200, Y_S - ro_t, Z_HB), (0, -1, 0))
port('TE-512 hot-out TC boss M14x1.5 (exhaust duct, top)', (X1 + 150.0, YC, Z_EXO + ro), (0, 0, 1), 30, 45)
port('PT-E4-1 cold-in pressure tap 1/4 (top header)', (X0 + 70, Y_S - ro_t, Z_HT), (0, -1, 0), 20, 80, 'P')
port('PT-E4-2 cold-out pressure tap 1/4 (bottom header)', (X0 + 70, Y_S - ro_t, Z_HB), (0, -1, 0), 20, 80, 'P')
port('PT-E4-3 hot-in pressure tap 1/4 (plenum south wall)', (2200.0, Y_S - WALL, 260.0), (0, -1, 0), 20, 80, 'P')
port('PT-E4-4 hot-out pressure tap 1/4 (hood north wall)', (X0 + 150, Y_N + WALL, Z_EXO), (0, 1, 0), 20, 80, 'P')
# drains DN15 (hot: plenum low point, cold: bottom header low point) with cap
for lbl, p, n, Lp in (('DR-E4-H hot-side drain DN15 + cap (plenum low point, bottom-flush, to north)', V(1560.0, Y_N + WALL, Z_PL0 + WALL + 11), V(0, 1, 0), 65),
                      ('DR-E4-C cold-side drain DN15 + cap (header low point, 45 deg down-south)', V(X0 + 150, Y_S - 25, Z_HB - math.sqrt(ro_t ** 2 - 25 ** 2)),
                       V(0, -1, -1).normalize(), 150)):
    pp = [tube(PIPE['DN15'][0] / 2, 2.0, p, p + n * Lp), Part.makeCylinder(15, 18, p + n * Lp, n)]
    add('ports', lbl, Part.makeCompound(pp), '316L'); KEEP.append(cyl(15, p, p + n * (Lp + 18)))
    ports.append(dict(tag=lbl.split()[0], label=lbl, roof_m=[round(c / 1000, 4) for c in p + n * (Lp + 18)], dir=list(n), kind='drain'))
# borescope ports DN50 + blind flange (west walls of plenum and hood)
for lbl, z in (('BS-E4-1 borescope port DN50 + blind (hot face, plenum)', 255.0), ('BS-E4-2 borescope port DN50 + blind (cold face, hood)', Z_EXO)):
    p = V(X0 - WALL, YC, z); q = V(1339.0, YC, z)
    pp = [tube(PIPE['DN50'][0] / 2, 2.0, q, p), disk_flange(V(1303.0, YC, z), V(1, 0, 0), 'DN50', 'PN16', bore=1),   # blind
          disk_flange(V(1321.0, YC, z), V(1, 0, 0), 'DN50', 'PN16')]                                               # weld-neck
    add('ports', lbl, Part.makeCompound(pp), '347H'); KEEP.append(cyl(82.5, V(1303.0, YC, z), p))
    ports.append(dict(tag=lbl.split()[0], label=lbl, roof_m=[1.303, YC / 1000, z / 1000], dir=[-1, 0, 0], kind='inspection'))

# --- insulation ---------------------------------------------------------------------------------------------------
y_south = min(y_hdr_bot, y_hdr_top) - T_INS_C2 - T_CLAD
INS_A = box(X0 - WALL - T_INS_CORE - T_CLAD, X1 + WALL + T_INS_CORE + T_CLAD, y_south, Y_N + WALL + T_INS_CORE + T_CLAD,
            Z_PL0 - 30 - 40 - T_CLAD, Z_HD1 + T_INS_HOOD + T_CLAD)
INS_B = box(X1 + WALL + T_INS_CORE + T_CLAD - 1, X_PL1 + T_INS_HOT + T_CLAD, Y_S - WALL - T_INS_HOT - T_CLAD, Y_N + WALL + T_INS_HOT + T_CLAD,
            Z_PL0 - 30 - 40 - T_CLAD, Z_PLT + T_INS_HOT + T_CLAD)
INSUL += [INS_A, INS_B]

# ------------------------------------------------------------------------------------------------------------------
# 4. detailed sample of the plate-fin pack (OSF), local frame, mm
# ------------------------------------------------------------------------------------------------------------------
def osf_layer(z0, fin, width, nstrip, y0=0.0):
    p, tf, b, l = fin['p'] * 1e3, fin['t'] * 1e3, fin['b'] * 1e3, fin['l'] * 1e3
    sol = []
    nf = int(width / p)
    for k in range(nstrip):
        off = 0.5 * p * (k % 2)
        for i in range(nf):
            y = y0 + off + i * p
            if y + tf > y0 + width: break
            sol.append(Part.makeBox(l, tf, b, V(k * l, y, z0)))                      # fin leg (vertical)
            zf = z0 if i % 2 == 0 else z0 + b - tf
            if y + p <= y0 + width: sol.append(Part.makeBox(l, p, tf, V(k * l, y, zf)))   # flange (alternating top/bottom)
    return sol

def detail_sample():
    width, nstrip = 24.0, 5
    parts, z = [], 0.0
    parts.append(Part.makeBox(nstrip * FH['l'] * 1e3, width + 10, 2.0, V(0, -5, z))); z += 2.0     # cap sheet
    seq = ['h', 'c', 'h', 'c', 'h']
    for s in seq:
        fin = FH if s == 'h' else FC
        b = fin['b'] * 1e3
        parts += osf_layer(z, fin, width, nstrip if s == 'h' else int(nstrip * FH['l'] / FC['l']))
        parts.append(Part.makeBox(nstrip * FH['l'] * 1e3, 5.0, b, V(0, -5, z)))        # side bar
        z += b
        parts.append(Part.makeBox(nstrip * FH['l'] * 1e3, width + 10, TP, V(0, -5, z))); z += TP   # parting sheet
    return Part.makeCompound(parts)

SAMPLE = detail_sample()

# ------------------------------------------------------------------------------------------------------------------
# 5. insulation boolean, masses, export
# ------------------------------------------------------------------------------------------------------------------
print('building insulation ...')
keep_u = KEEP[0].fuse(KEEP[1:]) if len(KEEP) > 1 else KEEP[0]
def _fuse_valid(pieces, tag):
    u = pieces[0]
    for k, pc in enumerate(pieces[1:], 1):
        t = u.fuse(pc)
        if not t.isValid():
            t2 = t.copy(); t2.fix(1e-4, 1e-4, 1e-3)
            if t2.isValid(): t = t2
            else:
                print('  %s piece %d (%s, vol %.1f L, valid %s) breaks the union' % (tag, k, pc.ShapeType, pc.Volume / 1e6, pc.isValid()))
        u = t
    return u
ins_u = _fuse_valid(INSUL, 'insulation')
print('  valid: keep %s, insulation union %s, union volume %.1f L' % (keep_u.isValid(), ins_u.isValid(), ins_u.Volume / 1e6))
ins_shape = ins_u.cut(keep_u)
if not ins_shape.isValid() or ins_shape.Volume < 1e6:
    print('  insulation boolean invalid -> piecewise cut (pieces may overlap slightly)')
    ins_shape = Part.makeCompound([pc.cut(keep_u) for pc in INSUL])
print('  insulation valid %s, volume %.1f L' % (ins_shape.isValid(), ins_shape.Volume / 1e6))
RHO = {'347H': 7960.0, '321H': 7900.0, 'IN625': 8440.0, '316L': 7990.0, 'A4': 7950.0, 'microporous': 260.0}

doc = App.newDocument('E4_recuperator')
OBJ = {}
masses = []
for grp, items in G.items():
    OBJ[grp] = []
    for lbl, shp, mat, m in items:
        o = doc.addObject('Part::Feature', lbl.split()[0].replace('-', '_'))
        o.Label = lbl; o.Shape = shp
        OBJ[grp].append(o)
        mm = m if m is not None else shp.Volume * 1e-9 * RHO.get(mat, 7900.0)
        masses.append((grp, lbl, mat, mm))
o = doc.addObject('Part::Feature', 'E4_INS'); o.Label = 'E4-INS microporous insulation + 0.5 mm 1.4301 cladding'; o.Shape = ins_shape
OBJ['insulation'] = [o]
clad_area = ins_shape.Area * 1e-6 * 0.5        # outer half of the faces ~ cladding
m_ins = ins_shape.Volume * 1e-9 * RHO['microporous']; m_clad = clad_area * 0.5e-3 * 7900
masses.append(('insulation', 'E4-INS microporous insulation (MICROTHERM class)', 'microporous', m_ins))
masses.append(('insulation', 'E4-CLD cladding 0.5 mm 1.4301', '1.4301', m_clad))
o = doc.addObject('Part::Feature', 'E4_SAMPLE'); o.Label = 'E4 OSF core detail sample (local frame)'; o.Shape = SAMPLE
doc.recompute()

files = {'core': 'E4_core.step', 'headers_plenums': 'E4_headers_plenums.step', 'ducts': 'E4_ducts.step', 'supports': 'E4_supports.step',
         'ports': 'E4_ports.step', 'insulation': 'E4_insulation.step'}
for grp, fn in files.items():
    Import.export(OBJ[grp], os.path.join(OUT, fn))
Import.export([o for g in files for o in OBJ[g]], os.path.join(OUT, 'E4_assembly.step'))
Import.export([doc.getObject('E4_SAMPLE')], os.path.join(OUT, 'E4_core_detail_sample.step'))
doc.saveAs(os.path.join(OUT, 'E4_recuperator.FCStd'))

# ------------------------------------------------------------------------------------------------------------------
# 6. checks: engine envelope, clearances between unconnected items, envelope box
# ------------------------------------------------------------------------------------------------------------------
ENG_CYL = Part.makeCylinder(150.0, 1600.0, V(1300.0, 7850.0, 600.0), V(1, 0, 0))
def gap(a, b):
    """min distance (mm) between shapes; negative = overlap volume (mm3) if the shapes intersect."""
    try:
        v = a.common(b).Volume
    except Exception:
        v = 0.0
    if v > 1.0: return -v
    try:
        return a.distToShape(b)[0]
    except Exception:
        for sa in a.Solids or [a]:
            pass
        try:
            return min(x.distToShape(y)[0] for x in (a.Solids or [a]) for y in (b.Solids or [b]))
        except Exception:
            bb1, bb2 = a.BoundBox, b.BoundBox
            dx = max(0.0, bb1.XMin - bb2.XMax, bb2.XMin - bb1.XMax); dy = max(0.0, bb1.YMin - bb2.YMax, bb2.YMin - bb1.YMax)
            dz = max(0.0, bb1.ZMin - bb2.ZMax, bb2.ZMin - bb1.ZMax)
            return math.sqrt(dx * dx + dy * dy + dz * dz)
checks = {}
allmetal = [(lbl, shp) for grp in G for (lbl, shp, mat, m) in G[grp]]
tot_eng = 0.0
for lbl, shp in allmetal + [('insulation', ins_shape)]:
    v = shp.common(ENG_CYL).Volume
    if v > 1.0:
        print('INTERFERENCE with engine envelope: %s %.0f mm3' % (lbl, v))
    tot_eng += v
checks['engine_envelope_cylinder_D300_common_mm3'] = round(tot_eng, 1)
min_d = min(gap(shp, ENG_CYL) for lbl, shp in allmetal + [('insulation', ins_shape)])
checks['min_distance_to_engine_envelope_mm'] = round(min_d, 1)
# pairs that must not touch
def find(prefix): return [s for l, s in allmetal if l.startswith(prefix)][0]
pairs = [('E4-SP-EX', 'E4-SP-H1'), ('E4-SP-C1', 'E4-SP-C2'), ('E4-SP-C2', 'E4-SP-H1'), ('E4-SP-C1', 'E4-SP-H1'), ('E4-SP-EX', 'E4-HDR-CI'),
         ('E4-SP-H1', 'E4-CORE-B'), ('E4-SP-H1', 'E4-HDR-CO'), ('E4-SP-EX', 'E4-SUP-1'), ('E4-HDR-CO', 'E4-PLN'), ('E4-HDR-CI', 'E4-HOD')]
checks['pairs'] = {}
for a, b in pairs:
    sa, sb = find(a), find(b)
    d = gap(sa, sb)
    checks['pairs']['%s / %s' % (a, b)] = round(d, 1)
# insulation-to-insulation clearance exhaust vs H1 (sleeve surfaces)
ex_ins = [s for s in ins2]; h1_ins = INSUL[:3]
checks['exhaust_vs_H1_insulation_gap_mm'] = round(min(gap(a, b) for a in ex_ins for b in h1_ins), 1)
bb = App.BoundBox()
for lbl, shp in allmetal + [('ins', ins_shape)]: bb.add(shp.BoundBox)
checks['assembly_bbox_roof_m'] = dict(x=(round(bb.XMin / 1e3, 3), round(bb.XMax / 1e3, 3)), y=(round(bb.YMin / 1e3, 3), round(bb.YMax / 1e3, 3)),
                                      z=(round(bb.ZMin / 1e3, 3), round(bb.ZMax / 1e3, 3)))
env = dict(x=(1.30, 2.90), y=(8.00, 8.60), z=(0.10, 1.20))   # EP-1 1.6 x 1.0 m (docs/06 sec.1, 2026-10-23)
checks['inside_proposed_envelope'] = all(env[a][0] - 1e-3 <= checks['assembly_bbox_roof_m'][a][0] and checks['assembly_bbox_roof_m'][a][1] <= env[a][1] + 1e-3
                                         for a in 'xyz')
print('CHECKS', json.dumps(checks, indent=1))

# ------------------------------------------------------------------------------------------------------------------
# 7. interfaces JSON + BOM
# ------------------------------------------------------------------------------------------------------------------
m_tot = sum(m[3] for m in masses)
dp = CALC.get('dp', {}); dsg = CALC.get('design', {}); gr = CALC.get('growth', {})
def r_m(p): return [round(c / 1000.0, 4) for c in p]
def eng_mm(p): return [round(p[0] - ENG0[0], 1), round(p[1] - ENG0[1], 1), round(p[2] - ENG0[2], 1)]
ifc = dict(
    subsystem='E4 recuperator', frame='ROOF (m): x east, y north, z up; ENG (mm) given for engine-side flanges',
    script='cad/engine/recuperator.py', calc='sim/engine/e4_recuperator_calc.py', doc='docs/engine/E4_recuperator.md',
    envelope_proposed_roof_m=dict(x=[1.30, 2.90], y=[8.00, 8.60], z=[0.10, 1.20],
                                  note='EP-1 enlarged to x 1.30-2.90 / y 7.60-8.60 (docs/06 sec.1, 2026-10-23); y < 8.10 only the C1/C2/H1 spools'),
    assembly_bbox_roof_m=checks['assembly_bbox_roof_m'],
    interfaces=[
        dict(name='C1 cold inlet (from E2 compressor collector)', roof_m=r_m(FL['C1'][0]), eng_mm=eng_mm(FL['C1'][0]), direction_E4_side=[0, -1, 0],
             engine_flange_faces=[0, 1, 0], size='DN100', flange='EN 1092-1 PN16 type 11, D220 K180 8xM16, gasket spiral-wound 321/graphite',
             fluid='air 0.395 kg/s, 165 C, 3.09 bar abs', design='3.5 barg / 250 C', movement_mm=gr.get('bellows', {}).get('C1'),
             source=SOURCE['C1'], status='COINCIDENT with E2 E2-102 (straight spool %s, top header axis ENG z %.1f)' % (INFO['C1']['straight'], Z_HT - 600)),
        dict(name='C2 cold outlet (to E2 combustor plenum)', roof_m=r_m(FL['C2'][0]), eng_mm=eng_mm(FL['C2'][0]), direction_E4_side=[0, -1, 0],
             engine_flange_faces=[0, 1, 0], size='DN125 spool, rectangular joint %s' % INFO['C2'].get('rect_flange_mm'),
             flange='rectangular plate flange 15 mm, 10 x M10 (E2 pattern), Thermiculite 815 sheet gasket',
             fluid='air 0.395 kg/s, %.0f C, 3.04 bar abs' % dsg.get('Tc_out_net_C', 568), design='3.5 barg / 620 C',
             movement_mm=gr.get('bellows', {}).get('C2'), source=SOURCE['C2'],
             status='COINCIDENT with E2 E2-151 rectangular flange %s; E4 transition to the DN125 bellows on x %.0f (ENG %.1f), bottom header z %.1f' %
                    (INFO['C2'].get('rect_flange_mm'), X_C2_ROUND, X_C2_ROUND - ENG0[0], Z_HB - 600)),
        dict(name='H1 hot inlet (from E3 FPT exhaust collector)', roof_m=r_m(FL['H1'][0]), eng_mm=eng_mm(FL['H1'][0]), direction_E4_side=[0, -1, 0],
             engine_flange_faces=[0, 1, 0], size='DN250', flange='EN 1092-1 PN6, D375 K335 12xM16, spiral-wound 321/mica',
             fluid='exhaust 0.397 kg/s, 610 C (trip limit 660), 1.063 bar abs', design='0.3 barg / 680 C',
             movement_mm=gr.get('bellows', {}).get('H1'), source=SOURCE['H1'],
             status='COINCIDENT with E3 E3-110 H1 (ENG 300, 250, 0); bellows y %.0f..%.0f, mitre elbow R%.0f into the plenum at ROOF y %.0f' %
                    (INFO['H1_route']['bellows_y'][0], INFO['H1_route']['bellows_y'][1], R_E, YC)),
        dict(name='EXH package exhaust flange (to HVAC hot duct -> D-101)', roof_m=r_m(FL['EXH'][0]), direction=[1, 0, 0], size='DN250',
             flange='EN 1092-1 PN6 (docs/06)', fluid='exhaust 0.397 kg/s, %.0f C design (real cp), 262 C in the constant-cp cycle model; '
                                                     'transient max 450 C' % dsg.get('Th_out_net_C', 218),
             design='0.3 barg / 450 C', movement_mm=dict(own_thermal=dict(x=-0.6, z=gr.get('dz_core_mm', 2.5) + gr.get('dz_plenum_mm', 2.1)),
                                                        note='package on spring isolators: HVAC side must add a flexible joint (+-15 axial, +-25 lateral)'),
             source=SOURCE['EXH']),
        dict(name='skid support legs (E5)', points_roof_m=[[round(x / 1e3, 3), round(y / 1e3, 3), 0.100] for _, x, y in INFO['legs']],
             types=[l for l, _, _ in INFO['legs']], base_plate='150x150x12, 4x M12 slotted (sliding legs) / round holes (fixed)',
             load_per_leg_N=round(m_tot * 9.81 / 4 * 1.3, 0), note='static wet mass x1.3 dynamic; seismic per 2800 by E5'),
        dict(name='sway struts (E5 frame)', points_roof_m=[[round((X0 + 70) / 1e3, 3), 8.600, round((Z_HD1 - 50) / 1e3, 3)],
                                                           [round((X1 - 70) / 1e3, 3), 8.600, round((Z_HD1 - 50) / 1e3, 3)]],
             note='horizontal y-restraint, clevis pins allow +-5 mm z growth; E5 provides a frame member at y 8.600'),
        dict(name='drains', items=[p for p in ports if p['kind'] == 'drain'], note='to package drain line, normally capped; open after long shutdown'),
        dict(name='inspection', items=[p for p in ports if p['kind'] == 'inspection'], note='west side, open from the package west door'),
        dict(name='instrument ports', items=[p for p in ports if p['kind'] in ('TC', 'P')],
             note='TE-502/503/505 per docs/electrical/02_io_list; TE-512 (reserve tag) used for recuperator hot outlet; PT-E4-1..4 new (dp cold/hot)')],
    performance=dict(duty_kW=dsg.get('Q_net_kW'), eps_clean=dsg.get('eps_clean'), eps_net=dsg.get('eps_net'),
                     dp_cold_pct=dp.get('cold_pct_P2'), dp_hot_pct_inlet=dp.get('hot_pct_inlet'), dp_hot_pct_pamb=dp.get('hot_pct_pamb'),
                     T_cold_out_C=dsg.get('Tc_out_net_C'), T_hot_out_C=dsg.get('Th_out_net_C')),
    masses_kg=dict(total_dry=round(m_tot, 1), core=round(mc, 1), insulation=round(m_ins + m_clad, 1)),
    heat_loss_kW=CALC.get('insulation', {}).get('Q_loss_kW'), checks=checks, ecu=dict(TOT_ramp_K_per_min=CALC.get('transient', {}).get('ramp_K_per_min', 15),
                                                                                       trip_TOT_C=660, purge_volume_m3=CALC.get('purge_volume_m3')))
json.dump(ifc, open(os.path.join(OUT, 'E4_interfaces.json'), 'w'), indent=1, ensure_ascii=False)

BOM_HDR = 'tag,description,qty,make_or_buy,material_or_spec,size_or_rating,supplier_candidates,mass_kg,model_file,notes'
def MF(fn): return 'cad_out/engine/E4/' + fn if fn else ''
def csv(*f): return ','.join('"%s"' % str(x).replace('"', "'") if (',' in str(x) or '"' in str(x)) else str(x) for x in f)
mass_of = {l.split()[0]: m for g, l, mat, m in masses}
mf = lambda t: round(mass_of.get(t, 0.0), 2)
fins = dsg.get('fin_cold', {}); finh = dsg.get('fin_hot', {})
bom = [BOM_HDR,
 csv('E4-CORE-A', 'Recuperator core module A, brazed plate-fin, %d cold + %d hot layers, counterflow + crossflow cold windows' % (NC // 2, NH - NC // 2), 1,
     'make: fin forming + stacking + vacuum braze BNi-2 1040 C + He leak test', '347H (1.4912/UNS S34709) sheets, 347 fins', '%.0fx%.0fx%.0f mm' % (H / 2, W, L),
     'IR: MAPNA turbine-blade vacuum-furnace shop (PARTO) - confirm; CN: stainless PFHE brazers (Hangzhou/Wuxi) to our drawing', round(mc / 2, 1), MF('E4_core.step'),
     'eps_net 0.905 with module B; 3.5 barg design, 5.3 barg hydro'),
 csv('E4-CORE-B', 'Recuperator core module B (identical to A)', 1, 'make: as A', 'as A', 'as A', 'as A', round(mc / 2, 1), MF('E4_core.step'), 'interchangeable'),
 csv('E4-FIN-C', 'Cold offset-strip fin stock p %.1f / t %.2f / h %.1f / strip %.1f mm' % (fins.get('p', 1.2e-3) * 1e3, fins.get('t', 1e-4) * 1e3, fins.get('b', 2e-3) * 1e3, fins.get('l', 3e-3) * 1e3),
     '%.1f m2' % (NC * W * L * 1e-6 * 1.05), 'make: OSF fin-forming die (5-axis/wire-EDM tool) or buy formed fin', '347 foil 0.10 mm (EN 1.4550)', '', 'foil: Outokumpu (FI), Aperam (FR/BE), TISCO (CN)', 0, MF('E4_core_detail_sample.step'), 'mass %.1f kg included in E4-CORE-A/B' % dsg.get('mass_core', {}).get('fins_cold', 9.8)),
 csv('E4-FIN-H', 'Hot offset-strip fin stock p %.1f / t %.2f / h %.1f / strip %.1f mm' % (finh.get('p', 1.6e-3) * 1e3, finh.get('t', 1.2e-4) * 1e3, finh.get('b', 3.8e-3) * 1e3, finh.get('l', 3.2e-3) * 1e3),
     '%.1f m2' % (NH * W * L * 1e-6 * 1.05), 'make: OSF fin-forming die', '347 foil 0.12 mm', '', 'as E4-FIN-C', 0, MF('E4_core_detail_sample.step'), 'mass %.1f kg included in E4-CORE-A/B; 0.12 mm = oxidation allowance' % dsg.get('mass_core', {}).get('fins_hot', 29.0)),
 csv('E4-FIN-D', 'Cold distributor fin (plain, 45 deg cut) p 2.0 / t 0.15 mm', '%.1f m2' % (NC * W * 2 * LW * 1e-6 * 1.1), 'make: fin-forming die', '347 foil 0.15 mm', '', 'as E4-FIN-C', 0, '', 'mass %.1f kg included in E4-CORE-A/B' % dsg.get('mass_core', {}).get('dist_fins_cold', 8.4)),
 csv('E4-PS', 'Parting sheets %.2f mm, cap sheets 2.0 mm, side/end bars 5 mm' % TP, 'set', 'make: laser cut, flattened, degreased', '347H', '', 'Outokumpu, Aperam, Acerinox (ES)', 0, '', 'mass %.1f kg included in E4-CORE-A/B' % (dsg.get('mass_core', {}).get('parting_sheets', 60) + dsg.get('mass_core', {}).get('side_bars', 16) + dsg.get('mass_core', {}).get('end_bars_cold', 10) + dsg.get('mass_core', {}).get('cap_sheets', 4))),
 csv('E4-BRZ', 'Braze filler BNi-2 amorphous foil 38 um (AWS A5.8 BNi-2 / ISO 17672 Ni 620)', '%.1f m2' % ((NC + NH) * 2 * W * L * 1e-6), 'buy', 'BNi-2', '38 um', 'Vacuumschmelze VITROBRAZE (DE), AT&M/Antai (CN)', 0, '', 'mass %.1f kg included in E4-CORE-A/B; stop-off on bars' % dsg.get('mass_core', {}).get('braze_BNi2', 4.8)),
]
bellows_sup = 'Witzenmann (DE), BOA (DE), Kompaflex (CH), Belman (DK), Aerosun (CN)'
def bel_txt(k):
    b = gr.get('bellows', {}).get(k, {})
    return 'bellows axial +-%.0f / lateral +-%.0f mm' % (b.get('axial_mm', 0), b.get('lateral_mm', 0))
desc = {'E4-HDR-CI': ('make: rolled half-pipe + TIG to core end bars', '347H 1.5 mm', 'R55 x %.0f' % H),
        'E4-HDR-CO': ('make: rolled half-pipe + TIG, PWHT none (stabilised)', '347H 1.5 mm', 'R55 x %.0f' % H),
        'E4-PLN': ('make: laser-cut sheet + TIG, ribs', '347H 3 mm', '%.0fx%.0fx%.0f' % (X_PL1 - X0 + WALL, W + 2 * WALL, Z_PLT - Z_PL0)),
        'E4-SKT-H': ('make: formed U-lip 1.2 mm + TIG', '347H 1.2 mm', 'ring %.0fx%.0f' % (H + 12, W + 12)),
        'E4-PPL': ('make: laser-perforated sheet', '347H 2 mm, phi 0.55', '%.0fx%.0f' % (H, W)),
        'E4-VAN': ('make: formed plates', 'IN625 2.5 mm', '3 vanes'),
        'E4-HOD': ('make: sheet + TIG', '347H 3 mm', '%.0fx%.0fx%.0f' % (H + 6, W + 6, Z_HD1 - Z_HD0)),
        'E4-SKT-C': ('make: formed 1.2 mm + TIG', '347H 1.2 mm', 'ring'),
        'E4-SP-C1': ('make spool; buy bellows', '321/1.4541 pipe 114.3x2, 2-ply 321 bellows with liner', 'DN100 PN16, 250 C, %s' % bel_txt('C1')),
        'E4-SP-C2': ('make spool; buy bellows', '347H pipe 139.7x2, 2-ply IN625 bellows with liner', 'DN125 PN16, 620 C, %s' % bel_txt('C2')),
        'E4-SP-H1': ('make spool + 3-piece mitre elbow; buy bellows', '321H pipe 273x3, 2-ply IN625 bellows with liner', 'DN250 PN6, 680 C, %s' % bel_txt('H1')),
        'E4-SP-EX': ('make duct; buy bellows', '321H pipe 273x3, 2-ply 321 bellows with liner', 'DN250 PN6, 450 C, axial +-10 / lateral +-10 mm')}
for g, l, mat, m in masses:
    t = l.split()[0]
    if g in ('core',) or t.startswith('E4-CORE'): continue
    if g == 'insulation':
        bom.append(csv(t, l.split(' ', 1)[1], 1, 'buy + fit (removable boxes on flanges/bellows)', 'microporous silica, 0.5 mm 1.4301 cladding' if t == 'E4-INS' else '1.4301 0.5 mm',
                       '%.0f/%.0f/%.0f mm (610/core/215 C)' % (T_INS_HOT, T_INS_CORE, T_INS_HOOD), 'Promat MICROTHERM/PROMALIGHT (BE/DE), Luyang (CN); cladding local IR',
                       round(m, 1), MF('E4_insulation.step'), 'skin <= 60 C at 40 C enclosure air'))
        continue
    if g == 'ports':
        sup = 'TC: Rössel (DE), TC Mess- und Regeltechnik (DE), local IR; bosses machined' if t.startswith('TE') else 'local machining; DN15/DN50 fittings EN stock'
        bom.append(csv(t, l.split(' ', 1)[1], 1, 'make boss; buy instrument (per docs/electrical)' if t.startswith(('TE', 'PT')) else 'make',
                       '347H/316L', '', sup, round(m, 2), MF('E4_ports.step'), ''))
        continue
    if g == 'supports':
        if 'strut' in l:
            bom.append(csv(t, l.split(' ', 1)[1], 1, 'make (rod + clevis lug); buy clevis pins', 'A4-70 rod M16, 347H lug on hood', 'L ~90 mm',
                           'local machining; clevis: Würth (DE)', round(m, 1), MF('E4_supports.step'), 'E5 provides the frame member at y 8.600'))
        else:
            bom.append(csv(t, l.split(' ', 1)[1], 1, 'make (welded SHS, plates); buy pad + slide plate', '347H SHS 50x4 + lug; S355 galv base 150x150x12; '
                           'calcium-silicate pad 25 mm; graphite-bronze slide plate (sliding legs)', 'static ~%.0f N' % (m_tot * 9.81 / 4),
                           'pads: Skamol (DK), Promat (DE); slide plates: KS Gleitlager (DE)', round(m, 1), MF('E4_supports.step'), ''))
        continue
    mk, mt, sz = desc.get(t, ('make', mat, ''))
    sup = bellows_sup if t.startswith('E4-SP') else 'IR sheet-metal + TIG shop (precision fabrication), material Outokumpu/Aperam/Acerinox'
    bom.append(csv(t, l.split(' ', 1)[1], 1, mk, mt, sz, sup, round(m, 1), MF(files.get(g, '')), ''))
bom += [
 csv('E4-BLT', 'Bolting kits for 4 flanged joints (C1 8xM16, C2 10xM10 rectangular, H1 12xM16, EXH 12xM16) + 2 borescope blinds 4xM16', 6, 'buy',
     'studs 1.7709 (21CrMoV5-7) + nuts 1.7258 on H1/C2 (hot), A4-70 on C1/EXH/blinds; nickel anti-seize', 'EN 1092-1 / EN 1515',
     'Würth (DE), Bossard (CH), IR fastener stockists', 3.5, MF('E4_ducts.step'), 'mating flanges on the engine side belong to E2/E3, on EXH to HVAC'),
 csv('E4-GSK', 'Gaskets: spiral-wound 321 + mica (H1), Thermiculite 815 rectangular sheet (C2), graphite (C1, EXH)', 4, 'buy', 'EN 1514-2', 'DN100/rect/250', 'Klinger (AT), Kempchen (DE), Donit (SI)', 1.2, '', 'spares: 2 sets'),
 csv('E4-TC', 'Thermocouples type K class 1 MI 3 mm Inconel 600 sheath (TE-502, TE-503, TE-512; TOT TE-505A/B are on E3)', 3, 'buy (electrical scope)', 'IEC 60584-1', '0-900 C', 'see docs/electrical/02_io_list', 0, MF('E4_ports.step'), 'counted in the electrical BOM (mass 0 here)'),
 csv('E4-PDT', 'Differential pressure transmitters cold side (PT-E4-1/2) and hot side (PT-E4-3/4)', 2, 'buy (electrical scope, NEW I/O)', '4-20 mA, 0-10 kPa / 0-5 kPa', '', 'Endress+Hauser (CH/DE), WIKA (DE), Keller (CH)', 1.6, '', 'add to docs/electrical I/O list: fouling + leak monitoring'),
]
os.makedirs(os.path.join(ROOT, 'docs', 'bom'), exist_ok=True)
open(os.path.join(ROOT, 'docs', 'bom', 'engine_E4_bom.csv'), 'w', encoding='utf-8').write('\n'.join(bom) + '\n')
print('mass breakdown:')
for g, l, mat, m in masses: print('  %-16s %-90s %7.1f kg' % (g, l[:90], m))
print('TOTAL dry mass %.1f kg' % m_tot)

# ------------------------------------------------------------------------------------------------------------------
# 8. iso PNG (matplotlib, tessellated shapes) - left: metal, top-right: insulated, bottom-right: core detail sample
# ------------------------------------------------------------------------------------------------------------------
try:
    import numpy as np
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
    COL = {'core': (0.85, 0.55, 0.20), 'headers_plenums': (0.55, 0.62, 0.72), 'ducts': (0.70, 0.70, 0.70), 'supports': (0.35, 0.45, 0.35),
           'ports': (0.80, 0.20, 0.20), 'insulation': (0.88, 0.88, 0.86), 'sample': (0.75, 0.75, 0.78)}
    def tris(shape, tol):
        vs, fs = shape.tessellate(tol)
        if not fs: return np.zeros((0, 3, 3))
        vs = np.array([[p.x, p.y, p.z] for p in vs]); return vs[np.array(fs)]
    LIGHT = np.array([0.4, -0.5, 0.75]); LIGHT /= np.linalg.norm(LIGHT)
    def shade(T, rgb):
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); ln = np.linalg.norm(n, axis=1) + 1e-12; n = n / ln[:, None]
        k = 0.45 + 0.55 * np.abs(n @ LIGHT)
        return np.clip(np.outer(k, rgb), 0, 1)
    def draw(ax, groups, elev=24, azim=-58, lims=None, edges=False):
        allT, allC = [], []
        for T, rgb, a in groups:
            if len(T) == 0: continue
            c = shade(T, rgb); c = np.hstack([c, np.full((len(c), 1), a)])
            allT.append(T); allC.append(c)
        T = np.vstack(allT); C = np.vstack(allC)
        pc = Poly3DCollection(T, facecolors=C, edgecolors=((0.2, 0.2, 0.25, 0.35) if edges else 'none'), linewidths=(0.15 if edges else 0))
        pc.set_zorder(1)
        ax.add_collection3d(pc)
        mn, mx = (lims if lims else (T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)))
        ax.set_xlim(mn[0], mx[0]); ax.set_ylim(mn[1], mx[1]); ax.set_zlim(mn[2], mx[2])
        ax.set_box_aspect(tuple(mx - mn)); ax.view_init(elev=elev, azim=azim); ax.set_proj_type('ortho')
        ax.set_axis_off()
        return mn, mx
    metal_groups = [(tris(Part.makeCompound([s for (_, s, _, _) in G[g]]), 1.5 if g != 'core' else 3.0), COL[g], 1.0) for g in G]
    fig = plt.figure(figsize=(16, 10), dpi=110)
    ax1 = fig.add_axes([0.0, 0.0, 0.62, 0.95], projection='3d')
    ax1.computed_zorder = False
    lims = (np.array([1290.0, 7990.0, 90.0]), np.array([2720.0, 8620.0, 1210.0]))
    draw(ax1, metal_groups + [(tris(ENG_CYL, 6.0), (0.3, 0.5, 0.9), 0.10)], lims=lims)
    # envelope wireframe + flange labels
    ex = [(1300, 2700), (8040, 8600), (100, 1200)]
    segs = []
    for a in ex[0]:
        for b in ex[1]: segs.append([(a, b, ex[2][0]), (a, b, ex[2][1])])
        for c in ex[2]: segs.append([(a, ex[1][0], c), (a, ex[1][1], c)])
    for b in ex[1]:
        for c in ex[2]: segs.append([(ex[0][0], b, c), (ex[0][1], b, c)])
    ax1.add_collection3d(Line3DCollection(segs, colors=(0.2, 0.2, 0.2, 0.35), linewidths=0.6, linestyles='dashed'))
    lab = {'C1': 'C1 cold in DN100\n(165 C, from E2)', 'C2': 'C2 cold out DN125\n(568 C, to combustor)', 'H1': 'H1 hot in DN250\n(610 C, from FPT)',
           'EXH': 'EXH DN250 (218 C)\nto D-101'}
    off = {'C1': (-330, -60, 120), 'C2': (-330, -60, -170), 'H1': (60, -60, -260), 'EXH': (40, 0, -200)}
    for tag, (p, d, dn, pn) in FL.items():
        q = (p[0] + off[tag][0], p[1] + off[tag][1], p[2] + off[tag][2])
        ax1.plot([p[0], q[0]], [p[1], q[1]], [p[2], q[2]], color='k', lw=0.7, zorder=20)
        ax1.text(q[0], q[1], q[2], lab[tag], fontsize=8.5, color='k', zorder=21,
                 bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='0.6', alpha=0.85))
    for vec_, nm in (((150, 0, 0), 'x E'), ((0, 150, 0), 'y N'), ((0, 0, 150), 'z')):
        ax1.quiver(1320, 8060, 1000, *vec_, color='k', lw=1.0, arrow_length_ratio=0.2, zorder=20)
        ax1.text(1320 + vec_[0] * 1.15, 8060 + vec_[1] * 1.15, 1000 + vec_[2] * 1.15, nm, fontsize=8, zorder=21)
    ax1.set_title('GR180-CCHP E4 recuperator - ROOF frame (dashed = E4 envelope, blue = engine D300 envelope); insulation hidden', fontsize=10)
    ax2 = fig.add_axes([0.60, 0.42, 0.40, 0.55], projection='3d')
    draw(ax2, [(tris(ins_shape, 3.0), COL['insulation'], 1.0)] + [m for m in metal_groups if m[1] in (COL['ducts'], COL['ports'], COL['supports'])],
         lims=lims, azim=-58)
    ax2.set_title('with microporous insulation + cladding', fontsize=9)
    ax3 = fig.add_axes([0.66, 0.02, 0.32, 0.40], projection='3d')
    draw(ax3, [(tris(SAMPLE, 0.05), COL['sample'], 1.0)], elev=16, azim=-152, edges=True)
    ax3.set_title('core detail: OSF hot %.1f/%.1f mm, cold %.1f/%.1f mm, parting sheet %.1f mm' % (FH['p'] * 1e3, FH['b'] * 1e3, FC['p'] * 1e3,
                                                                                                   FC['b'] * 1e3, TP), fontsize=8)
    perf = CALC.get('design', {})
    fig.text(0.01, 0.01, 'brazed plate-fin 347H, %d+%d layers, core %.0f x %.0f x %.0f mm (x,y,z), eps_net %.3f, dp %.2f %% / %.2f %%, Q %.0f kW, dry mass %.0f kg'
             % (NC, NH, H, W, L, perf.get('eps_net', 0), dp.get('cold_pct_P2', 0), dp.get('hot_pct_inlet', 0), perf.get('Q_net_kW', 0), m_tot), fontsize=9)
    fig.savefig(os.path.join(OUT, 'E4_iso.png'), dpi=110)
    print('wrote E4_iso.png')
except Exception as ex:
    import traceback; traceback.print_exc()
    print('PNG rendering skipped:', ex)
print('E4 done ->', OUT)
