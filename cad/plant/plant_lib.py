"""GR180-CCHP roof plant - geometry / piping / BOM / clash library for the scripted FreeCAD model.

Frame: ROOF (docs/06_master_design.md section 1): origin = SW corner of the finished roof, x east, y north, z up.
All public inputs are in metres; FreeCAD works in millimetres internally (V() converts).
Run only through build_plant.py with freecadcmd (LANG=en_US.UTF-8).
"""
import csv
import json
import math
import os

import FreeCAD as App
import Part

MM = 1000.0
EPS = 1e-6


def V(x, y=None, z=None):
    if y is None:
        x, y, z = x
    return App.Vector(x * MM, y * MM, z * MM)


def M(v):
    return (round(v.x / MM, 4), round(v.y / MM, 4), round(v.z / MM, 4))


def unit(v):
    w = App.Vector(v)
    L = w.Length
    return w * (1.0 / L) if L > EPS else w


# ----------------------------------------------------------------------------------------------- pipe data
# steel OD (EN 10220 / ASME B36.10), mm
OD_STEEL = {10: 17.2, 15: 21.3, 20: 26.9, 25: 33.7, 32: 42.4, 40: 48.3, 50: 60.3, 65: 76.1, 80: 88.9, 100: 114.3,
            125: 139.7, 150: 168.3, 200: 219.1, 250: 273.0}
FLANGE_OD = {10: 90, 15: 95, 20: 105, 25: 115, 32: 140, 40: 150, 50: 165, 65: 185, 80: 200, 100: 220, 125: 250,
             150: 285, 200: 340, 250: 405}
MATERIALS = {
    # key: (description for BOM, OD table, kg/m empty, colour, flanged above DN)
    'CS40':  ('carbon steel EN 10216-2 P235GH / A106 Gr.B, Sch40 seamless, welded, PN16', OD_STEEL,
              {15: 1.27, 20: 1.69, 25: 2.50, 32: 3.39, 40: 4.05, 50: 5.44, 65: 8.63, 80: 11.29, 100: 16.07}, (0.55, 0.55, 0.58), 40),
    'PE100': ('PE100 SDR11 PN16 black, UV-stabilised, butt/electro-fusion; steel spools at valves',
              {20: 25, 25: 32, 32: 40, 40: 50, 50: 63, 65: 75, 80: 90, 100: 110},
              {20: 0.17, 25: 0.28, 32: 0.43, 40: 0.67, 50: 1.05, 65: 1.47, 80: 2.11, 100: 3.14}, (0.10, 0.10, 0.12), 50),
    'SS304': ('stainless 1.4301 press-fit system (EN 10312), EPDM seals, glycol 40 %', OD_STEEL,
              {15: 0.40, 20: 0.55, 25: 0.85, 32: 1.10, 40: 1.40}, (0.75, 0.75, 0.78), 99),
    'SS316F': ('stainless 316 Sch80 seamless, listed threaded/press fittings, FK-5-1-12 system pressure', OD_STEEL,
               {15: 1.62, 20: 2.20, 25: 3.24}, (0.85, 0.15, 0.15), 99),
    'PPR':   ('PP-R PN16 (EN ISO 15874), fusion-welded', {15: 20, 20: 25, 25: 32, 32: 40},
              {15: 0.17, 20: 0.23, 25: 0.36, 32: 0.57}, (0.30, 0.60, 0.30), 99),
    'PVC':   ('PVC-U drain pipe, solvent-cemented, fall >= 1 %', {20: 25, 25: 32, 32: 40, 40: 50, 50: 63},
              {20: 0.20, 25: 0.30, 32: 0.40, 40: 0.55, 50: 0.80}, (0.60, 0.60, 0.60), 99),
    'GAS':   ('carbon steel Sch40 seamless, welded, yellow (EN 1775 / national gas code)', OD_STEEL,
              {15: 1.27, 20: 1.69, 25: 2.50}, (0.95, 0.80, 0.10), 99),
    'SS316D': ('stainless 316L Sch10S, TIG-welded (acidic start-up condensate)', OD_STEEL,
               {15: 0.80, 20: 1.00, 25: 1.40, 32: 1.80}, (0.80, 0.80, 0.85), 99),
    'DUCT':  ('exhaust duct DN250, inner 316L 0.8 mm + 50 mm mineral wool + 1.4301 outer skin, clamp-band joints',
              {250: 273.0}, {250: 28.0}, (0.80, 0.45, 0.30), 0),
}
INSULATION = {
    # key: (BOM description, thickness mm, kg/m per DN approx factor, colour)
    'MW50': ('stone wool pipe section 50 mm, 100 kg/m3, + 0.6 mm aluminium cladding', 50, (0.80, 0.80, 0.82)),
    'EL40': ('elastomeric (k <= 0.036) 40 mm + 0.8 mm aluminium / GRP cladding, roof', 40, (0.82, 0.84, 0.86)),
    'EL19': ('elastomeric (k <= 0.036) 19 mm, indoor', 19, (0.15, 0.15, 0.15)),
    'EL25H': ('elastomeric 25 mm over self-regulating heat tracing 20 W/m + aluminium cladding', 25, (0.82, 0.84, 0.86)),
    'DW50': ('integral double-wall insulation (part of the duct)', 48, (0.82, 0.55, 0.40)),
}
SPAN = {'CS40': {15: 1.8, 20: 1.8, 25: 2.1, 32: 2.4, 40: 2.4, 50: 2.7, 65: 3.0, 80: 3.0, 100: 3.3},
        'PE100': 1.2, 'SS304': 1.8, 'SS316F': 1.8, 'PPR': 1.0, 'PVC': 1.2, 'GAS': 2.1, 'SS316D': 1.8, 'DUCT': 2.0}


def pipe_od(mat, dn):
    return MATERIALS[mat][1][dn]


# ----------------------------------------------------------------------------------------------- registry
class Part_:
    """One solid in the model: owner tag, kind ('equip', 'pipe', 'ins', 'comp', 'support', 'struct', 'walk', 'ref'),
    colour, and the set of owners it may legitimately touch (connections)."""
    __slots__ = ('owner', 'label', 'shape', 'kind', 'color', 'connects', 'group')

    def __init__(s, owner, label, shape, kind, color, connects=(), group=None):
        s.owner, s.label, s.shape, s.kind, s.color = owner, label, shape, kind, color
        s.connects = set(connects)
        s.group = group or owner


class Model:
    def __init__(s):
        s.parts = []            # list of Part_
        s.items = {}            # tag -> dict(bom fields, group, file)
        s.nozzles = {}          # (tag, name) -> dict(p, d, dn, end, medium)
        s.interfaces = []       # dicts for plant_interfaces.json
        s.routes = {}           # name -> Route
        s.zones = []            # service zones: dict(owner, box(x0,y0,z0,x1,y1,z1), label)
        s.walkways = []         # dict(x0,y0,x1,y1, axis)
        s.bom_extra = []        # rows appended verbatim
        s.footprints = {}       # tag -> (x0, y0, x1, y1) for support placement / skid detection
        s.warnings = []

    # ---- items
    def item(s, tag, desc, make_buy, spec, size, suppliers, mass, group, notes='', qty=1, file_group=None):
        s.items[tag] = dict(tag=tag, description=desc, qty=qty, make_or_buy=make_buy, material_or_spec=spec,
                            size_or_rating=size, supplier_candidates=suppliers, mass_kg=mass, group=group,
                            notes=notes, file_group=file_group or group)

    def add(s, owner, label, shape, kind='equip', color=(0.6, 0.6, 0.6), connects=(), group=None):
        if shape is None or shape.isNull():
            return
        s.parts.append(Part_(owner, label, shape, kind, color, connects, group))

    def nozzle(s, tag, name, p, d, dn, medium, stub=0.10, mat='CS40', flange=True, color=(0.5, 0.5, 0.5)):
        """Equipment nozzle: p = point on equipment face (m), d = outward direction. Adds stub + flange to the
        equipment and returns the connection point (stub end, m)."""
        dv = unit(App.Vector(*d))
        p0 = V(p)
        od = pipe_od(mat, dn) if dn in MATERIALS[mat][1] else OD_STEEL[dn]
        if stub > 0:
            s.add(tag, '%s.%s.stub' % (tag, name), Part.makeCylinder(od / 2, stub * MM, p0, dv), 'equip', color)
        end = p0 + dv * (stub * MM)
        if flange and dn >= 15:
            fo = FLANGE_OD.get(dn, od * 1.6)
            s.add(tag, '%s.%s.flange' % (tag, name), Part.makeCylinder(fo / 2, 16, end - dv * 16, dv), 'equip', color)
        s.nozzles[(tag, name)] = dict(p=M(end), d=tuple(round(c, 4) for c in (dv.x, dv.y, dv.z)), dn=dn, medium=medium)
        return M(end)

    def nz(s, tag, name):
        return s.nozzles[(tag, name)]['p']

    def interface(s, name, item, p, d, size, medium, counterpart, note=''):
        s.interfaces.append(dict(name=name, item=item, position_roof_m=list(p), direction=list(d), size=size,
                                 medium=medium, counterpart=counterpart, note=note))

    def zone(s, owner, x0, y0, x1, y1, z0=0.03, z1=2.10, label='service'):
        s.zones.append(dict(owner=owner, box=(x0, y0, z0, x1, y1, z1), label=label))


# ----------------------------------------------------------------------------------------------- primitives
def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx * MM, dy * MM, dz * MM, V(x0, y0, z0))


def cyl(cx, cy, z0, d, h):
    return Part.makeCylinder(d / 2 * MM, h * MM, V(cx, cy, z0), App.Vector(0, 0, 1))


def cylp(p, d, dirv, L):
    return Part.makeCylinder(d / 2 * MM, L * MM, V(p), unit(App.Vector(*dirv)))


def loft_rect_circle(x0, y0, z0, dx, dy, cx, cy, z1, d):
    r = Part.makePolygon([V(x0, y0, z0), V(x0 + dx, y0, z0), V(x0 + dx, y0 + dy, z0), V(x0, y0 + dy, z0), V(x0, y0, z0)])
    c = Part.Wire(Part.makeCircle(d / 2 * MM, V(cx, cy, z1), App.Vector(0, 0, 1)))
    return Part.makeLoft([r, c], True, True)


def i_beam(p0, p1, h=0.133, b=0.140, tw=0.0055, tf=0.0085):
    """HEA-type I-beam between two points on a horizontal line (web vertical); p0/p1 at the bottom-flange
    underside centre line."""
    a, b_ = V(p0), V(p1)
    d = b_ - a
    L = d.Length
    ux = unit(d)
    uy = App.Vector(0, 0, 1).cross(ux)
    H, B, TW, TF = h * MM, b * MM, tw * MM, tf * MM
    pts2 = [(-B / 2, 0), (B / 2, 0), (B / 2, TF), (TW / 2, TF), (TW / 2, H - TF), (B / 2, H - TF), (B / 2, H), (-B / 2, H),
            (-B / 2, H - TF), (-TW / 2, H - TF), (-TW / 2, TF), (-B / 2, TF), (-B / 2, 0)]
    pts3 = [a + uy * u + App.Vector(0, 0, w) for u, w in pts2]
    face = Part.Face(Part.makePolygon(pts3))
    return face.extrude(ux * L)


def angle_post(x, y, z0, z1, a=0.06):
    return box(x - a / 2, y - a / 2, z0, a, a, z1 - z0)


# ----------------------------------------------------------------------------------------------- inline components
def comp_len(ctype, od, dn):
    """face-to-face length (mm) of inline components by type and pipe OD"""
    t = {
        'ball': 2.2 * od + 40, 'butterfly': 0.45 * od + 25, 'check': 0.8 * od + 40, 'ystrainer': 3.0 * od + 30,
        'basket': 460.0, 'magflow': 2.0 * od + 100, 'heatmeter': max(190.0, 2.2 * od + 60), 'picv': 2.4 * od + 60,
        'motorball': 2.2 * od + 40, 'mbutterfly': 0.45 * od + 25, 'flex': 2.5 * od + 60, 'bellows': 260.0,
        'separator': max(260.0, 4.5 * od), 'threeway': 2.6 * od + 50, 'meter_water': 190.0, 'float': 120.0,
        'balancing': 2.4 * od + 40, 'psv': 120.0, 'regulator': 200.0, 'filter': 200.0,
    }
    if ctype in ('pump_inline', 'pump_twin'):
        return {20: 150, 25: 180, 32: 220, 40: 250, 50: 280, 65: 340, 80: 360, 100: 450}[dn]
    return t[ctype]


def comp_shape(ctype, A, u, L, od, dn, motor_dir=None, act=None):
    """Envelope of an inline component starting at A (mm vector) along unit u, length L (mm)."""
    sh = []
    up = App.Vector(0, 0, 1) if abs(u.z) < 0.9 else App.Vector(1, 0, 0)
    if act is not None:
        up = unit(App.Vector(*act))
    side = unit(u.cross(up))
    mid = A + u * (L / 2)
    fo = FLANGE_OD.get(dn, od * 1.6)
    if ctype in ('ball', 'motorball', 'balancing', 'picv', 'threeway', 'check', 'ystrainer', 'magflow', 'heatmeter',
                 'meter_water', 'separator', 'regulator', 'filter', 'psv', 'float'):
        body_d = {'check': fo * 0.95, 'magflow': fo, 'separator': max(2.4 * od, 150)}.get(ctype, max(fo * 0.9, od * 1.5))
        sh.append(Part.makeCylinder(body_d / 2, L, A, u))
        if ctype in ('ball', 'balancing'):
            sh.append(Part.makeCylinder(8, 0.9 * od + 40, mid, up))
        if ctype in ('motorball', 'picv', 'threeway'):
            h = 0.5 * body_d + 90
            sh.append(Part.Shape(Part.makeBox(110, 90, 100, mid + up * h - u * 55 - side * 45)))
            sh.append(Part.makeCylinder(10, h, mid, up))
        if ctype == 'magflow':
            sh.append(Part.makeBox(120, 120, 120, mid + up * (fo / 2) - u * 60 - side * 60))
        if ctype == 'heatmeter':
            sh.append(Part.makeBox(110, 60, 120, mid + up * (od / 2 + 30) - u * 55 - side * 30))
        if ctype == 'ystrainer':
            leg = unit(up * -1 + u * 0.7)
            sh.append(Part.makeCylinder(od * 0.65, od * 1.8, mid, leg))
        if ctype == 'separator':
            sh.append(Part.makeCylinder(body_d / 2, 2.6 * body_d, mid - up * (1.3 * body_d), up))
    elif ctype in ('butterfly', 'mbutterfly'):
        sh.append(Part.makeCylinder(fo * 0.95 / 2, L, A, u))
        h = fo / 2 + (120 if ctype == 'mbutterfly' else 60)
        sh.append(Part.makeCylinder(15, h, mid, up))
        if ctype == 'mbutterfly':
            sh.append(Part.makeBox(130, 100, 110, mid + up * h - u * 65 - side * 50))
        else:
            sh.append(Part.makeBox(220, 30, 20, mid + up * h - side * 15))
    elif ctype == 'basket':
        sh.append(Part.makeCylinder(od / 2 * 1.05, L, A, u))
        sh.append(Part.makeCylinder(130, 520, mid - up * 200, up))
    elif ctype in ('flex', 'bellows'):
        sh.append(Part.makeCylinder(od * 0.62, L, A, u))
    elif ctype in ('pump_inline', 'pump_twin'):
        cas = max(2.6 * od, 160)
        sh.append(Part.makeCylinder(fo * 0.95 / 2, L, A, u))
        sh.append(Part.makeBox(L * 0.8, cas, cas * 0.9, mid - u * (L * 0.4) - side * (cas / 2) - up * (cas * 0.45)))
        md = unit(App.Vector(*motor_dir)) if motor_dir else up
        mlen = {20: 230, 25: 250, 32: 300, 40: 330, 50: 380, 65: 470, 80: 520, 100: 600}[dn]
        mdia = {20: 110, 25: 120, 32: 150, 40: 160, 50: 180, 65: 220, 80: 240, 100: 260}[dn]
        if ctype == 'pump_twin':
            perp = unit(md.cross(u))
            for sgn in (-1, 1):
                b = mid + perp * (sgn * (mdia / 2 + 10)) + md * (cas * 0.45)
                sh.append(Part.makeCylinder(mdia / 2, mlen, b, md))
                sh.append(Part.makeBox(1, 1, 1, b))
        else:
            sh.append(Part.makeCylinder(mdia / 2, mlen, mid + md * (cas * 0.45), md))
    else:
        raise ValueError(ctype)
    # flanges both sides for flanged components
    if dn >= 32 and ctype not in ('flex', 'bellows', 'float', 'psv'):
        for q in (A, A + u * (L - 16)):
            sh.append(Part.makeCylinder(fo / 2, 16, q, u))
    s = sh[0]
    for x in sh[1:]:
        s = s.fuse(x)
    return s.removeSplitter() if hasattr(s, 'removeSplitter') else s


# ----------------------------------------------------------------------------------------------- routes
class Route:
    def __init__(s, name, line, service, dn, mat, pts, ins=None, connects=(), parent=None, inline=(), rf=1.5,
                 group='piping', notes='', end_parent=None, heat_trace=False, support=True, color=None, hall=False):
        s.name, s.line, s.service, s.dn, s.mat, s.ins = name, line, service, dn, mat, ins
        s.pts = [tuple(float(c) for c in p) for p in pts]
        s.connects = set(connects)
        s.parent, s.end_parent = parent, end_parent
        s.inline = list(inline)
        s.rf, s.group, s.notes = rf, group, notes
        s.heat_trace, s.support, s.color, s.hall = heat_trace, support, color, hall
        s.length = 0.0
        s.elbows = []
        s.straights = []          # (A, B) mm vectors of straight pipe centre-line pieces (after fillets)
        s.comps = []              # (ctype, tag, dn, A, u, L, spec)

    @property
    def od(s):
        return pipe_od(s.mat, s.dn)

    @property
    def od_ins(s):
        return s.od + 2 * (INSULATION[s.ins][1] if s.ins else 0)


def _dedupe(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) > 1e-6:
            out.append(p)
    return out


def build_route(m, r):
    pts = _dedupe(r.pts)
    P_ = [V(p) for p in pts]
    # drop collinear interior points
    Q = [P_[0]]
    for i in range(1, len(P_) - 1):
        u = unit(P_[i] - Q[-1])
        v = unit(P_[i + 1] - P_[i])
        if u.getAngle(v) > 1e-3:
            Q.append(P_[i])
    Q.append(P_[-1])
    od = r.od
    R = r.rf * od if r.mat != 'DUCT' else 300.0
    n = len(Q)
    tl = [0.0] * n
    ang = [0.0] * n
    for i in range(1, n - 1):
        u = unit(Q[i] - Q[i - 1])
        v = unit(Q[i + 1] - Q[i])
        th = u.getAngle(v)
        ang[i] = th
        tl[i] = R * math.tan(th / 2)
    straights, arcs = [], []
    for i in range(n - 1):
        u = unit(Q[i + 1] - Q[i])
        a = Q[i] + u * tl[i]
        b = Q[i + 1] - u * tl[i + 1]
        if (b - a).dot(u) < -0.5:
            m.warnings.append('route %s: segment %d too short for bends (%.0f mm short)' % (r.name, i, -(b - a).dot(u)))
            b = a
        straights.append((a, b))
    for i in range(1, n - 1):
        if ang[i] < 1e-3:
            continue
        u = unit(Q[i] - Q[i - 1])
        v = unit(Q[i + 1] - Q[i])
        A = Q[i] - u * tl[i]
        bis = unit(v - u)
        C = Q[i] + bis * (R / math.cos(ang[i] / 2))
        arcs.append((A, u, v, C, ang[i], Q[i]))
        r.elbows.append(round(math.degrees(ang[i])))
    r.length = sum((b - a).Length for a, b in straights) / MM + sum(R * a[4] for a in arcs) / MM
    # inline components
    comp_iv = {}       # straight index -> list of (s0, s1)
    for spec in r.inline:
        ctype = spec['type']
        dn = spec.get('dn', r.dn)
        odc = OD_STEEL.get(dn, od)
        L = spec.get('L', comp_len(ctype, odc, dn) / 1.0)
        at = V(spec['at'])
        placed = False
        for k, (a, b) in enumerate(straights):
            d = b - a
            Ls = d.Length
            if Ls < 1:
                continue
            u = unit(d)
            s = (at - a).dot(u)
            perp = (at - a) - u * s
            if perp.Length < 2.0 and -1 <= s <= Ls + 1:
                s0 = min(max(s - L / 2, 0.0), Ls - L)
                if s0 < -0.5:
                    m.warnings.append('route %s: no room for %s %s (%.0f mm needed, %.0f mm straight)' % (
                        r.name, ctype, spec.get('tag', ''), L, Ls))
                    s0 = 0.0
                A = a + u * s0
                r.comps.append(dict(type=ctype, tag=spec.get('tag', ''), dn=dn, A=A, u=u, L=L, spec=spec))
                comp_iv.setdefault(k, []).append((s0, s0 + L))
                placed = True
                break
        if not placed:
            m.warnings.append('route %s: inline %s %s at %s not on a straight' % (r.name, ctype, spec.get('tag', ''), spec['at']))
    # geometry
    col = r.color or MATERIALS[r.mat][3]
    rins = r.od_ins / 2
    for k, (a, b) in enumerate(straights):
        d = b - a
        Ls = d.Length
        if Ls < 0.5:
            continue
        u = unit(d)
        cuts = sorted(comp_iv.get(k, []))
        s = 0.0
        pieces = []
        for c0, c1 in cuts:
            if c0 - s > 0.5:
                pieces.append((s, c0))
            s = max(s, c1)
        if Ls - s > 0.5:
            pieces.append((s, Ls))
        for s0, s1 in pieces:
            A = a + u * s0
            m.add(r.name, '%s.pipe' % r.name, Part.makeCylinder(od / 2, s1 - s0, A, u), 'pipe', col,
                  connects=r.connects | ({r.parent} if r.parent else set()) | ({r.end_parent} if r.end_parent else set()),
                  group=r.group)
            if r.ins:
                m.add(r.name, '%s.ins' % r.name, Part.makeCylinder(rins, s1 - s0, A, u).cut(Part.makeCylinder(od / 2, s1 - s0, A, u)),
                      'ins', INSULATION[r.ins][2],
                      connects=r.connects | ({r.parent} if r.parent else set()) | ({r.end_parent} if r.end_parent else set()),
                      group=r.group)
        r.straights.append((a, b, pieces))
    for A, u, v, C, th, corner in arcs:
        nrm = unit(u.cross(v))
        Bexp = corner + v * (R * math.tan(th / 2))
        deg = math.degrees(th)
        rot = App.Rotation(nrm, deg)
        sgn = 1.0 if (rot.multVec(A - C) + C - Bexp).Length < (App.Rotation(nrm, -deg).multVec(A - C) + C - Bexp).Length else -1.0
        cons = r.connects | ({r.parent} if r.parent else set()) | ({r.end_parent} if r.end_parent else set())

        def bend(rad):
            if rad < R * 0.97:
                try:
                    return Part.Face(Part.Wire(Part.makeCircle(rad, A, u))).revolve(C, nrm, sgn * deg)
                except Exception:
                    pass
            # mitred envelope (tight bend relative to the radius): two cylinders to the corner + sphere
            s1 = Part.makeCylinder(rad, (corner - A).Length + 0.01, A, u)
            s2 = Part.makeCylinder(rad, (Bexp - corner).Length + 0.01, corner, v)
            return s1.fuse(s2).fuse(Part.makeSphere(rad, corner))

        pipe_b = bend(od / 2)
        m.add(r.name, '%s.pipe.elbow' % r.name, pipe_b, 'pipe', col, connects=cons, group=r.group)
        if r.ins:
            ib = bend(rins)
            try:
                ib = ib.cut(pipe_b)
            except Exception:
                pass
            m.add(r.name, '%s.ins.elbow' % r.name, ib, 'ins', INSULATION[r.ins][2], connects=cons, group=r.group)
    for c in r.comps:
        odc = OD_STEEL.get(c['dn'], od)
        sh = comp_shape(c['type'], c['A'], c['u'], c['L'], odc, c['dn'], c['spec'].get('motor_dir'), c['spec'].get('act'))
        m.add(r.name, '%s.%s' % (r.name, c['tag'] or c['type']), sh, 'comp', c['spec'].get('color', (0.25, 0.35, 0.65)),
              connects=r.connects | ({r.parent} if r.parent else set()) | ({r.end_parent} if r.end_parent else set()),
              group=r.group)
    m.routes[r.name] = r
    return r


# ----------------------------------------------------------------------------------------------- supports
def in_any_footprint(m, x, y, pad=0.05):
    for tag, (x0, y0, x1, y1) in m.footprints.items():
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            return tag
    return None


def in_walkway(m, x, y):
    for w in m.walkways:
        if w['x0'] <= x <= w['x1'] and w['y0'] <= y <= w['y1']:
            return True
    return False


def _support_ok(m, shp, r, obst):
    bb = shp.BoundBox
    for p, pbb in obst:
        if p.owner == r.name:
            continue
        if not bb.intersect(pbb):
            continue
        try:
            if shp.common(p.shape).Volume > 100.0:
                return False
        except Exception:
            return False
    for z in m.zones:
        if z['owner'] in r.connects or z['owner'] == r.name:
            continue
        x0, y0, z0, x1, y1, z1 = z['box']
        if bb.XMin < x1 * MM and bb.XMax > x0 * MM and bb.YMin < y1 * MM and bb.YMax > y0 * MM and bb.ZMin < z1 * MM:
            return False
    for w in m.walkways:
        if bb.XMin < w['x1'] * MM and bb.XMax > w['x0'] * MM and bb.YMin < w['y1'] * MM and bb.YMax > w['y0'] * MM:
            return False
    if getattr(m, 'tower_ring', None):
        (cx, cy), R = m.tower_ring
        if r.name not in ('CW-S', 'CW-R', 'CW-RT', 'MU-1', 'DR-OV') and 'CT-1' not in r.connects:
            px, py = (bb.XMin + bb.XMax) / 2 / MM, (bb.YMin + bb.YMax) / 2 / MM
            if math.hypot(px - cx, py - cy) < R + 0.15:
                return False
    return True


def auto_supports(m):
    """Roof pipe supports under horizontal runs (rubber-base block / post), hall hangers from the slab soffit.
    A support is placed only where it does not hit another solid, a service zone of an unrelated item, a walkway or the
    tower air ring; otherwise it is shifted along the run (+-0.15/0.30/0.45 m) or skipped (logged)."""
    count = {}
    obst = [(p, p.shape.BoundBox) for p in m.parts if p.kind not in ('ref', 'walk')]
    skipped = 0
    for r in m.routes.values():
        if not r.support or r.mat == 'DUCT':
            continue
        span = SPAN[r.mat] if not isinstance(SPAN[r.mat], dict) else SPAN[r.mat].get(r.dn, 2.4)
        rad = r.od_ins / 2
        small = r.od_ins < 120
        for a, b, pieces in r.straights:
            d = b - a
            if d.Length < 300 or abs(unit(d).z) > 0.1:
                continue
            u = unit(d)
            L = d.Length / MM
            z = a.z / MM
            if not r.hall and z > 1.0 and L < span:
                continue      # short elevated run between risers: carried by the risers / equipment
            nsup = max(1, int(math.ceil(L / span - 1e-6)))
            for k in range(nsup):
                placed = False
                for off in (0.0, 0.15, -0.15, 0.30, -0.30, 0.45, -0.45):
                    s = (k + 0.5) * L / nsup + off
                    if s < 0.12 or s > L - 0.12:
                        continue
                    p = a + u * (s * MM)
                    x, y, zc = p.x / MM, p.y / MM, p.z / MM
                    if r.hall:
                        if zc > -0.32:
                            break
                        rod = Part.makeCylinder(5, (-0.30 - (zc + rad / MM)) * MM, V(x, y, zc + rad / MM), App.Vector(0, 0, 1))
                        clamp = Part.makeCylinder(rad + 6, 40, p - u * 20, u).cut(Part.makeCylinder(rad, 40, p - u * 20, u))
                        shp = rod.fuse(clamp)
                        key = 'hall hanger M10 rod + insulated clamp DN%d' % r.dn
                    else:
                        if in_any_footprint(m, x, y, pad=0.0):
                            break      # over a skid / equipment frame: carried by it
                        zb = zc - rad / MM
                        if zb < 0.05 or zc > 3.2:
                            break
                        bx = 0.20 if small else 0.30
                        by = 0.16 if small else 0.20
                        wx, wy = (bx, by) if abs(u.x) < 0.5 else (by, bx)
                        blk = box(x - wx / 2, y - wy / 2, 0.0, wx, wy, 0.03)
                        post = box(x - 0.025, y - 0.025, 0.03, 0.05, 0.05, max(zb - 0.03, 0.005))
                        shp = blk.fuse(post)
                        key = ('roof pipe support, recycled-rubber base + galv. post/clamp, h <= 0.6 m' if zb <= 0.60 else
                               'roof pipe stand, rubber base + galv. post + U-bolt, h %.1f m' % round(zb, 1))
                    if _support_ok(m, shp, r, obst):
                        m.add('SUP-%s' % r.name, '%s.support' % r.name, shp, 'support', (0.35, 0.35, 0.35),
                              connects={r.name} | set(r.connects) | ({r.parent} if r.parent else set()), group='supports')
                        obst.append((m.parts[-1], shp.BoundBox))
                        count[key] = count.get(key, 0) + 1
                        placed = True
                        break
                if not placed:
                    skipped += 1
    m.support_skipped = skipped
    return count


# ----------------------------------------------------------------------------------------------- walkway step-overs
def step_overs(m):
    n = 0
    for w in m.walkways:
        hits = []
        for r in m.routes.values():
            if r.hall:
                continue
            rad = r.od_ins / 2 / MM
            for a, b, _ in r.straights:
                A, B = M(a), M(b)
                if abs(A[2] - B[2]) > 1e-3 or A[2] + rad > 0.46 or A[2] - rad > 0.46:
                    if not (abs(A[2] - B[2]) > 1e-3):
                        continue
                if abs(A[2] - B[2]) > 1e-3:
                    continue
                # does the segment cross the walkway along its short axis?
                if w['axis'] == 'x':      # walkway runs along x, pipes cross in y
                    if abs(A[0] - B[0]) < 1e-3 and w['x0'] <= A[0] <= w['x1'] and min(A[1], B[1]) < w['y0'] and max(A[1], B[1]) > w['y1']:
                        hits.append(A[0])
                else:
                    if abs(A[1] - B[1]) < 1e-3 and w['y0'] <= A[1] <= w['y1'] and min(A[0], B[0]) < w['x0'] and max(A[0], B[0]) > w['x1']:
                        hits.append(A[1])
        hits.sort()
        groups = []
        for h in hits:
            if groups and h - groups[-1][-1] < 0.9:
                groups[-1].append(h)
            else:
                groups.append([h])
        for g in groups:
            c0, c1 = g[0] - 0.35, g[-1] + 0.35
            if w['axis'] == 'x':
                deck = box(c0, w['y0'], 0.45, c1 - c0, w['y1'] - w['y0'], 0.05)
                st = box(c0 - 0.30, w['y0'], 0.0, 0.30, w['y1'] - w['y0'], 0.22).fuse(box(c1, w['y0'], 0.0, 0.30, w['y1'] - w['y0'], 0.22))
                legs = box(c0, w['y0'], 0.0, 0.05, w['y1'] - w['y0'], 0.45).fuse(box(c1 - 0.05, w['y0'], 0.0, 0.05, w['y1'] - w['y0'], 0.45))
            else:
                deck = box(w['x0'], c0, 0.45, w['x1'] - w['x0'], c1 - c0, 0.05)
                st = box(w['x0'], c0 - 0.30, 0.0, w['x1'] - w['x0'], 0.30, 0.22).fuse(box(w['x0'], c1, 0.0, w['x1'] - w['x0'], 0.30, 0.22))
                legs = box(w['x0'], c0, 0.0, w['x1'] - w['x0'], 0.05, 0.45).fuse(box(w['x0'], c1 - 0.05, 0.0, w['x1'] - w['x0'], 0.05, 0.45))
            m.add('STILE-%d' % n, 'step-over %d (%.1f m)' % (n, c1 - c0), deck.fuse(st).fuse(legs), 'struct', (0.95, 0.75, 0.15),
                  connects=set(), group='walkways')
            m.bom_extra.append(dict(tag='STILE-%d' % n, description='GRP step-over stile with handrail over pipe crossing',
                                    qty=1, make_or_buy='buy', material_or_spec='GRP grating 38 mm, SS fixings, h 0.50 m',
                                    size_or_rating='%.2f x %.2f m deck' % (c1 - c0, (w['y1'] - w['y0']) if w['axis'] == 'x' else (w['x1'] - w['x0'])),
                                    supplier_candidates='Kee Safety (UK), Fibrelite (UK), domestic GRP fabricators',
                                    mass_kg=round(25 + 20 * (c1 - c0)), model_file='cad_out/plant/structure.step', notes='auto-placed where low pipes cross a walkway'))
            n += 1
    return n


# ----------------------------------------------------------------------------------------------- clash check
def clash_check(m, min_vol=1000.0):
    """Pairwise solid interference (> min_vol mm3), skipping same owner / declared connections / reference."""
    sol = [p for p in m.parts if p.kind not in ('ref',)]
    bbs = [p.shape.BoundBox for p in sol]
    res = []
    for i in range(len(sol)):
        a = sol[i]
        for j in range(i + 1, len(sol)):
            b = sol[j]
            if a.owner == b.owner or a.owner in b.connects or b.owner in a.connects:
                continue
            if a.group == b.group and a.group in ('walkways',):
                continue
            if not bbs[i].intersect(bbs[j]):
                continue
            try:
                v = a.shape.common(b.shape).Volume
            except Exception:
                continue
            if v > min_vol:
                res.append((a.label, b.label, v / 1e3))
    return res


def zone_check(m, min_vol=1000.0):
    res = []
    for z in m.zones:
        x0, y0, z0, x1, y1, z1 = z['box']
        zb = box(x0, y0, z0, x1 - x0, y1 - y0, z1 - z0)
        bb = zb.BoundBox
        for p in m.parts:
            if p.kind in ('ref', 'walk') or p.owner == z['owner'] or z['owner'] in p.connects:
                continue
            if p.group == 'walkways':
                continue
            if not bb.intersect(p.shape.BoundBox):
                continue
            try:
                v = zb.common(p.shape).Volume
            except Exception:
                continue
            if v > min_vol:
                res.append((z['owner'], z['label'], p.label, v / 1e3))
    return res


# ----------------------------------------------------------------------------------------------- render
def render(m, path, elev=28, azim=-60, title='', kinds=None, xlim=(-0.3, 10.3), ylim=(-0.3, 10.3), zlim=(-0.2, 4.5),
           tol=15.0, owners=None, figsize=(16, 12), ortho_top=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=figsize, dpi=110)
    ax = fig.add_subplot(111, projection='3d')
    polys, cols = [], []
    for p in m.parts:
        if kinds and p.kind not in kinds:
            continue
        if owners and not owners(p):
            continue
        try:
            verts, tris = p.shape.tessellate(tol)
        except Exception:
            continue
        vv = [(v.x / MM, v.y / MM, v.z / MM) for v in verts]
        for t in tris:
            polys.append([vv[t[0]], vv[t[1]], vv[t[2]]])
            cols.append(p.color)
    import numpy as np
    # simple directional shading
    L = np.array([0.4, -0.6, 0.7])
    L /= np.linalg.norm(L)
    shaded = []
    for poly, c in zip(polys, cols):
        a, b, cc = map(np.array, poly)
        n = np.cross(b - a, cc - a)
        nn = np.linalg.norm(n)
        k = 0.55 + 0.45 * abs(np.dot(n / nn, L)) if nn > 1e-12 else 0.8
        shaded.append(tuple(min(1.0, ch * k) for ch in c))
    pc = Poly3DCollection(polys, facecolors=shaded, edgecolors='none', linewidths=0)
    ax.add_collection3d(pc)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_zlim(*zlim)
    try:
        ax.set_box_aspect((xlim[1] - xlim[0], ylim[1] - ylim[0], zlim[1] - zlim[0]))
    except Exception:
        pass
    if ortho_top:
        ax.set_proj_type('ortho')
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('x east [m]')
    ax.set_ylabel('y north [m]')
    ax.set_zlabel('z [m]')
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return len(polys)
