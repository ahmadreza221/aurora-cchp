# GR180 version D2 - shared helpers for the intake / exhaust / frame scripts (d2_intake.py, d2_exhaust.py, d2_frame.py):
# paths, thick spun-profile revolve, D2 strut solids, STEP + json export, D2 reference-part loader and the
# interference check.  ENG frame (mm): x = engine axis (+ downstream), x = 0 at the shaft-tunnel spigot front face, z up.
import FreeCAD as App, Part, os, json, math, glob
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'cad_out', 'v13A')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2')
CALC = os.path.join(ROOT, 'sim', 'variant_d', 'd2_intake_exhaust_calc.json')
RHO = {'1.4301': 7.90e-6, '1.4828': 7.90e-6, '1.4541': 7.90e-6, 'S355': 7.85e-6, 'mesh': 1.6e-6, 'blanket': 0.30e-6,
       'cartridge': 0.12e-6, 'rubber': 1.2e-6}           # kg/mm3 (mesh / blanket / cartridge = effective envelope density)

# D2 reference set (as Fusion MODE D2): v13A core minus the parts replaced by the generator pod / radial stage,
# concept pod parts D-*, and the D2R radial turbine stage (cad_out/variant_d/D2/TURBINE, or GR180_D2_TURBINE_DIR to
# check against a specific turbine build, e.g. the commit-20686b0 one with the bolted exhaust flange x 176).
CORE_SKIP = {'Starter', 'NoseCone', 'Exhaust', 'Turbine', 'NGV', 'TurbineNut'}
D_SKIP = {'D-180_Exhaust_Diffuser_DN150'}
SUPERSEDED = {'D-160_Inlet_Screen': 'replaced by the INT-110 plenum + INT-140 port guard',
              'D-150_Pod_Struts_x3': 'replaced by INT-115 struts (same axes, trimmed at x -18, end blocks with radial M6)',
              'RT-180_Exhaust_Diffuser_DN150': 'replaced by the compact coaxial EX-1xx exhaust'}
TURBINE_DIR = os.environ.get('GR180_D2_TURBINE_DIR') or os.path.join(ROOT, 'cad_out', 'variant_d', 'D2', 'TURBINE')


def d2_reference_files(include_superseded=False):
    f = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts', '*.step'))}
    f = {k: v for k, v in f.items() if k not in CORE_SKIP}
    f.update({os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_d', 'D-*.step'))})
    t = glob.glob(os.path.join(TURBINE_DIR, 'T-*.step'))
    if t:                                         # detailed D2R turbine replaces the RT2 concept stage
        f.update({os.path.splitext(os.path.basename(p))[0]: p for p in t})
    else:
        f.update({os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_d', 'RT2', 'RT-*.step'))})
    return {k: v for k, v in f.items() if k not in D_SKIP and (include_superseded or k not in SUPERSEDED)}


def struts(r_extra=0.0):
    """the 3 D-150 pod struts (same construction as d_concept.py), optionally fattened for clearance holes."""
    R_POD, X_POD1, R_CASE = 55.0, -108.0, 55.0
    out = []
    for k in range(3):
        th = math.radians(90 + 120 * k)
        d = V(0, math.cos(th), math.sin(th))
        p0 = V(X_POD1 - 8, 0, 0) + d * (R_POD - 4)
        p1 = V(-12.0, 0, 0) + d * (R_CASE - 2)
        ax = p1 - p0
        e = V(ax.x, ax.y, ax.z).normalize() * 30.0
        out.append(Part.makeCylinder(4.0 + r_extra, ax.Length + 30.0, p0 - e, ax))   # extended into the pod only
    return out


def thick_revolve(prof, t, side=-1, axis=V(1, 0, 0)):
    """revolve a sheet of thickness t about the x axis. prof = [(x, r), ...] is the WETTED surface; the material
    goes to the RIGHT of the walking direction (side=-1) or to the left (side=+1)."""
    pts_o, pts_i = [], []
    n = len(prof)
    for i, (x, r) in enumerate(prof):
        a = prof[max(i - 1, 0)]; b = prof[min(i + 1, n - 1)]
        dx, dr = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dr)
        nx, nr = (-dr / L, dx / L)                    # left normal
        if side < 0:
            nx, nr = -nx, -nr
        pts_o.append(V(x, 0, r)); pts_i.append(V(x + t * nx, 0, r + t * nr))
    poly = pts_o + list(reversed(pts_i)) + [pts_o[0]]
    return Part.Face(Part.makePolygon(poly)).revolve(V(0, 0, 0), axis, 360)


def arc(cx, cr, R, a0, a1, n=24):
    """points (x, r) on a circle centre (cx, cr), angle measured in the (x, r) plane from +x towards +r, degrees."""
    return [(cx + R * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cr + R * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def cyl(x0, x1, r, ri=0.0):
    s = Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return s.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), V(1, 0, 0))) if ri > 0 else s


def radial_boss(x, ang_deg, r0, r1, d, hole=0.0):
    th = math.radians(ang_deg)
    d_ = V(0, math.cos(th), math.sin(th))
    b = Part.makeCylinder(d / 2, r1 - r0, V(x, 0, 0) + d_ * r0, d_)
    if hole:
        b = b.cut(Part.makeCylinder(hole / 2, r1 - r0 + 40, V(x, 0, 0) + d_ * (r0 - 20), d_))
    return b


def bolt_holes(x0, L, bc_r, n, d, start_deg, axis=V(1, 0, 0)):
    hs = []
    for k in range(n):
        th = math.radians(start_deg + 360.0 * k / n)
        hs.append(Part.makeCylinder(d / 2, L + 2, V(x0 - 1, bc_r * math.cos(th), bc_r * math.sin(th)), axis))
    return hs


def export(parts, sub, meta):
    """parts: {tag: (shape, material, note)} -> STEP per part + list for the BOM/json."""
    d = os.path.join(OUT, sub); os.makedirs(d, exist_ok=True)
    rows = {}
    for tag, (s, mat, note) in parts.items():
        s.exportStep(os.path.join(d, tag + '.step'))
        bb = s.BoundBox
        rows[tag] = dict(valid=s.isValid(), x=[round(bb.XMin, 1), round(bb.XMax, 1)], y=[round(bb.YMin, 1), round(bb.YMax, 1)],
                         z=[round(bb.ZMin, 1), round(bb.ZMax, 1)], volume_cm3=round(s.Volume / 1e3, 1),
                         mass_kg=round(s.Volume * RHO[mat], 3), material=mat, note=note,
                         bbox_mm='%.0f x %.0f x %.0f' % (bb.XLength, bb.YLength, bb.ZLength),
                         step=os.path.relpath(os.path.join(d, tag + '.step'), ROOT))
        print('%-36s valid %s  x %7.1f..%7.1f  r/y %6.1f  z %6.1f..%6.1f  %.2f kg' % (
            tag, s.isValid(), bb.XMin, bb.XMax, max(abs(bb.YMin), bb.YMax), bb.ZMin, bb.ZMax, rows[tag]['mass_kg']))
    meta = dict(meta); meta['parts'] = rows
    json.dump(meta, open(os.path.join(OUT, 'd2_%s_interfaces.json' % sub.lower()), 'w'), indent=1)
    return rows


def interference(new, ref, contact_ok=(), tol=1.0):
    """common volume of every new part vs every reference part (bbox pre-filter). tol mm3; contact_ok = pairs that
    are bolted / clamped contact faces (reported, allowed if < 50 mm3)."""
    res = []
    for a, sa in new.items():
        ba = sa.BoundBox
        for b, sb in ref.items():
            if not ba.intersect(sb.BoundBox):
                continue
            try:
                v = sa.common(sb).Volume
            except Exception as e:                       # pragma: no cover
                v = -1.0
            if v > tol or v < 0:
                ok = (a, b) in contact_ok and 0 <= v < 50
                res.append(dict(new=a, ref=b, common_mm3=round(v, 2), status='contact (allowed)' if ok else
                                ('superseded part' if b in SUPERSEDED else 'OVERLAP')))
    return res
