# GR180 version E - shared FreeCAD helpers for cad/variant_e/e_*.py: revolve profiles, cylinders, vanes, STEP + json
# export (one STEP per part into cad_out/variant_e/<SUBSYSTEM>/), densities.  ENG frame mm (see e_layout.py).
import FreeCAD as App, Part, os, json, math, glob
V = App.Vector
XA = V(1, 0, 0)
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_e')
RHO = {  # kg/mm3 (effective for envelopes)
    'Al': 2.70e-6, 'steel': 7.85e-6, 'stainless': 7.90e-6, '1.4828': 7.90e-6, 'IN713LC': 8.00e-6, 'IN625': 8.44e-6, 'alloyX': 8.22e-6,
    'N75': 8.37e-6, '17-4PH': 7.80e-6, 'SmCo+CF': 7.0e-6, 'lam': 7.65e-6 * 0.80, 'winding': 4.5e-6, 'bearing': 7.0e-6 * 0.55,
    'rubber': 1.2e-6, 'brass': 8.5e-6, 'filter': 0.10e-6, 'insul': 0.13e-6}


def rev(pts):
    """revolve a closed (x, r) polygon about the x axis"""
    p = [V(x, 0, r) for x, r in pts]
    if (p[0] - p[-1]).Length > 1e-9:
        p.append(p[0])
    return Part.Face(Part.makePolygon(p)).revolve(V(0, 0, 0), XA, 360)


def ell(cx, cr, a, b, t0, t1, sx=1, sr=1, n=24):
    """points on an ellipse arc: x = cx + sx a f(t), r = cr + sr b g(t); returns list for t in [t0, t1] deg using
    x = cx + a*cos(t), r = cr + b*sin(t)"""
    return [(cx + a * math.cos(math.radians(t0 + (t1 - t0) * k / n)), cr + b * math.sin(math.radians(t0 + (t1 - t0) * k / n))) for k in range(n + 1)]


def cyl(x0, x1, r, ri=0.0):
    s = Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), XA)
    return s.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), XA)) if ri > 0 else s


def zcyl(xc, yc, z0, z1, r, ri=0.0):
    s = Part.makeCylinder(r, z1 - z0, V(xc, yc, z0), V(0, 0, 1))
    return s.cut(Part.makeCylinder(ri, z1 - z0 + 2, V(xc, yc, z0 - 1), V(0, 0, 1))) if ri > 0 else s


def hexprism(x0, x1, af):
    r = af / math.sqrt(3)
    pts = [V(x0, r * math.cos(math.radians(30 + 60 * k)), r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0))


def rdir(a):
    return V(0, math.cos(math.radians(a)), math.sin(math.radians(a)))


def rad_cyl(x, a, r0, r1, rad):
    d = rdir(a)
    return Part.makeCylinder(rad, r1 - r0, V(x, 0, 0) + d * r0, d)


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def vane_row(n, x0, x1, r_le, r_te, ang_le_deg, t_le, t_te, phase=0.0, inward=False):
    """n straight 2.5D vanes (constant section along x) between r_le and r_te; the vane line leaves the LE point at the
    flow angle ang_le from the radial direction; wedge thickness t_le -> t_te.  Returns a compound of prisms."""
    out = []
    for k in range(n):
        th = math.radians(phase + 360.0 * k / n)
        er = (math.cos(th), math.sin(th)); et = (-math.sin(th), math.cos(th))
        p1 = (r_le * er[0], r_le * er[1])
        a = math.radians(ang_le_deg)
        sgn = -1.0 if inward else 1.0
        d = (sgn * math.cos(a) * er[0] + math.sin(a) * et[0], sgn * math.cos(a) * er[1] + math.sin(a) * et[1])
        # march along d until |p| = r_te
        s0, s1 = 0.0, 5 * abs(r_te - r_le) + 400
        for _ in range(80):
            sm = 0.5 * (s0 + s1)
            rr = math.hypot(p1[0] + sm * d[0], p1[1] + sm * d[1])
            if (rr < r_te) != inward:
                s0 = sm
            else:
                s1 = sm
        p2 = (p1[0] + s0 * d[0], p1[1] + s0 * d[1])
        nrm = (-d[1], d[0])
        q = [(p1[0] + nrm[0] * t_le / 2, p1[1] + nrm[1] * t_le / 2), (p2[0] + nrm[0] * t_te / 2, p2[1] + nrm[1] * t_te / 2),
             (p2[0] - nrm[0] * t_te / 2, p2[1] - nrm[1] * t_te / 2), (p1[0] - nrm[0] * t_le / 2, p1[1] - nrm[1] * t_le / 2)]
        pts = [V(x0, y, z) for (y, z) in q]
        out.append(Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0)))
    return out


def clip_annulus(shape, x0, x1, r0, r1):
    return shape.common(cyl(x0, x1, r1, r0))


def bolt_circle_holes(x0, x1, pcd, n, d, phase=0.0):
    hs = []
    for k in range(n):
        th = math.radians(phase + 360.0 * k / n)
        hs.append(Part.makeCylinder(d / 2, x1 - x0 + 2, V(x0 - 1, pcd / 2 * math.cos(th), pcd / 2 * math.sin(th)), XA))
    return hs


def cut_all(s, tools):
    for t in tools:
        s = s.cut(t)
    return s


def fuse_all(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s


class Parts:
    """collect parts -> STEP files + parts json for one subsystem"""

    def __init__(self, sub):
        self.sub = sub
        self.dir = os.path.join(OUT, sub)
        os.makedirs(self.dir, exist_ok=True)
        for f in glob.glob(os.path.join(self.dir, '*.step')):
            os.remove(f)
        self.rows = {}

    def add(self, tag, shape, mat, desc, make_buy, mass=None, note=''):
        try:
            shape = shape.removeSplitter()
        except Exception:
            pass
        f = os.path.join(self.dir, tag + '.step')
        shape.exportStep(f)
        bb = shape.BoundBox
        m = mass if mass is not None else shape.Volume * RHO[mat]
        self.rows[tag] = dict(subsystem=self.sub, desc=desc, make_buy=make_buy, material=mat, valid=shape.isValid(), n_solids=len(shape.Solids),
                              volume_cm3=round(shape.Volume / 1e3, 1), mass_kg=round(m, 2), mass_source='override (bought / envelope)' if mass is not None else 'CAD volume',
                              bbox=[[round(bb.XMin, 1), round(bb.XMax, 1)], [round(bb.YMin, 1), round(bb.YMax, 1)], [round(bb.ZMin, 1), round(bb.ZMax, 1)]],
                              note=note, step=os.path.relpath(f, ROOT))
        print('%-34s %-6s valid %-5s solids %2d  x %7.1f..%7.1f  y %7.1f..%7.1f  z %7.1f..%7.1f  %8.2f kg' % (
            tag, self.sub[:6], shape.isValid(), len(shape.Solids), bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax, m))

    def save(self, meta=None):
        d = dict(subsystem=self.sub, frame='ENG mm (x engine axis downstream, x = 0 at the compressor tip, z up)', parts=self.rows)
        if meta:
            d.update(meta)
        json.dump(d, open(os.path.join(self.dir, 'e_%s_parts.json' % self.sub.lower()), 'w'), indent=1)
        print('-> %s: %d parts, %.1f kg' % (self.sub, len(self.rows), sum(r['mass_kg'] for r in self.rows.values())))
