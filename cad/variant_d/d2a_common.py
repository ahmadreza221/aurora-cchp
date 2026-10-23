# GR180 version D2 - auxiliary systems (D2A): FreeCAD helpers shared by d2a_skid.py, d2a_fuel.py, d2a_lube_cool.py,
# d2a_sensors.py and d2a_check.py: primitives (box, cylinder on any axis, tube paths), STEP + json export with catalogue
# masses, the full D2 reference-part loader and a fast interference / keep-out test.
# ENG frame (mm): x = engine axis (+ downstream), x = 0 at the shaft-tunnel spigot front face, z up.
import FreeCAD as App, Part, os, sys, json, glob, math
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2a_layout as LY
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
D2 = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2')
AUX = os.path.join(D2, 'AUX')
os.makedirs(AUX, exist_ok=True)
XA, YA, ZA = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def bx(b):
    (x0, x1), (y0, y1), (z0, z1) = b
    return box(x0, x1, y0, y1, z0, z1)


def cyl(p0, p1, r, ri=0.0):
    """solid (or tube) cylinder from point p0 to point p1 (tuples)."""
    a, b = V(*p0), V(*p1)
    d = b - a
    s = Part.makeCylinder(r, d.Length, a, d)
    if ri > 0:
        e = V(d.x, d.y, d.z).normalize() * 0.5
        s = s.cut(Part.makeCylinder(ri, d.Length + 1.0, a - e, d))
    return s


def rad(x, ang_deg, r):
    a = math.radians(ang_deg)
    return (x, r * math.cos(a), r * math.sin(a))


def radial(x, ang_deg, r0, r1, rr, ri=0.0):
    return cyl(rad(x, ang_deg, r0), rad(x, ang_deg, r1), rr, ri)


def tube_path(pts, ro, ri=0.0):
    """swept tube along a polyline (balls in the corners), hollow if ri > 0."""
    pts = [V(*p) for p in pts]
    sh = None
    for p0, p1 in zip(pts[:-1], pts[1:]):
        d = p1 - p0
        if d.Length < 1e-6:
            continue
        c = Part.makeCylinder(ro, d.Length, p0, d)
        sh = c if sh is None else sh.fuse(c)
    for p in pts[1:-1]:
        sh = sh.fuse(Part.makeSphere(ro, p))
    if ri > 0:
        hole = None
        for p0, p1 in zip(pts[:-1], pts[1:]):
            d = p1 - p0
            if d.Length < 1e-6:
                continue
            e = V(d.x, d.y, d.z).normalize() * 0.01
            c = Part.makeCylinder(ri, d.Length + 0.02, p0 - e, d)
            hole = c if hole is None else hole.fuse(c)
        for p in pts[1:-1]:
            hole = hole.fuse(Part.makeSphere(ri, p))
        sh = sh.cut(hole)
    return sh.removeSplitter()


def hexbar(p0, p1, af):
    a, b = V(*p0), V(*p1)
    d = b - a
    r = af / math.sqrt(3)
    pts = [V(r * math.cos(math.radians(60 * k)), r * math.sin(math.radians(60 * k)), 0) for k in range(6)]
    s = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, d.Length))
    rot = App.Rotation(V(0, 0, 1), d)
    s.Placement = App.Placement(a, rot)
    return Part.Shape(s).copy()


def comp(shapes):
    return Part.makeCompound([s for s in shapes if s is not None])


def export(parts, sub, meta, fname):
    """parts: {tag: (shape, mass_kg, make_buy, spec, supplier)} -> AUX/<tag>.step + json rows."""
    d = os.path.join(AUX)
    rows = {}
    for tag, (s, m, mb, spec, sup) in parts.items():
        s.exportStep(os.path.join(d, tag + '.step'))
        bb = s.BoundBox
        rows[tag] = dict(subsystem=sub, valid=s.isValid(), x=[round(bb.XMin, 1), round(bb.XMax, 1)], y=[round(bb.YMin, 1), round(bb.YMax, 1)],
                         z=[round(bb.ZMin, 1), round(bb.ZMax, 1)], bbox_mm='%.0f x %.0f x %.0f' % (bb.XLength, bb.YLength, bb.ZLength),
                         mass_kg=round(m, 3), make_buy=mb, spec=spec, suppliers=sup, step=os.path.relpath(os.path.join(d, tag + '.step'), ROOT))
        print('%-40s valid %s  x %7.1f..%7.1f  y %7.1f..%7.1f  z %7.1f..%7.1f  %.2f kg' % (
            tag, s.isValid(), bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax, m))
    meta = dict(meta); meta['parts'] = rows
    json.dump(meta, open(os.path.join(AUX, fname), 'w'), indent=1)
    return rows


def clear_aux(prefixes):
    for f in glob.glob(os.path.join(AUX, '*.step')):
        if os.path.basename(f).split('_')[0][:2] in prefixes:
            os.remove(f)


# ---------------------------------------------------------------- D2 reference set (everything that is not AUX)
CORE_DROP = {'Shaft', 'NoseCone', 'Turbine', 'TurbineNut', 'NGV', 'Exhaust', 'FrontBearing_608_hybrid_8x22x7',
             'RearBearing_608_hybrid_8x22x7', 'FrontBearing_Oring', 'WaveSpring_22x16_free3_0_inst2_8', 'ShaftTunnel',
             'Starter', 'RPM_Magnet', 'Balance_Slug', 'EGT_Probe', 'Compressor',
             'SupplyLines', 'SupplySeals', 'RPM_Sensor'}      # D2A: gas manifold FU-110 + oil tubes OL-224 replace the v13A
                                                              # supply lines/seals; the nose-cone Hall sensor has no target any more


def d2_reference(include_pod_concept=False):
    """{name: shape} of the D2 assembly without the AUX parts. Pod shell: the D2A ported D-101/D-102 if built."""
    ref = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts', '*.step'))):
        n = os.path.basename(f)[:-5]
        if n not in CORE_DROP:
            ref['v13A/' + n] = Part.read(f)
    for grp in ('ROTOR', 'TURBINE', 'GENERATOR', 'INTAKE', 'EXHAUST', 'FRAME'):
        for f in sorted(glob.glob(os.path.join(D2, grp, '*.step'))):
            ref[grp + '/' + os.path.basename(f)[:-5]] = Part.read(f)
    pod = sorted(glob.glob(os.path.join(D2, 'POD', '*.step')))
    if pod and not include_pod_concept:
        for f in pod:
            ref['POD/' + os.path.basename(f)[:-5]] = Part.read(f)
    else:
        for n in ('D-101_Generator_Housing_Jacket', 'D-102_Generator_Front_Cap'):
            ref['pod/' + n] = Part.read(os.path.join(ROOT, 'cad_out', 'variant_d', n + '.step'))
    return ref


def aux_parts():
    return {'AUX/' + os.path.basename(f)[:-5]: Part.read(f) for f in sorted(glob.glob(os.path.join(AUX, '*.step')))}


def common_vol(a, b):
    if not a.BoundBox.intersect(b.BoundBox):
        return 0.0
    try:
        return a.common(b).Volume
    except Exception:
        return -1.0


def clash(new, ref, tol=0.5, label=''):
    """overlaps (> tol mm3) of every new part vs every ref part and new vs new; returns list."""
    out = []
    names = sorted(new)
    for i, a in enumerate(names):
        for b in list(ref) + names[i + 1:]:
            if b == a:
                continue
            sb = ref[b] if b in ref else new[b]
            v = common_vol(new[a], sb)
            if v > tol or v < 0:
                out.append(dict(a=a, b=b, mm3=round(v, 2)))
                print('%s OVERLAP %-44s %-44s %9.2f mm3' % (label, a, b, v))
    return out


def keepout(new):
    res = []
    for k, b in LY.KO.items():
        kb = bx(b)
        for a, s in new.items():
            v = common_vol(s, kb)
            if v > 0.5:
                res.append(dict(part=a, zone=k, mm3=round(v, 1)))
                print('KEEP-OUT %-40s in %s  %.0f mm3' % (a, k, v))
    return res
