# GR180 geometry measurement for the 0-D cycle and rotor models (read-only on the CAD).
# Run:  GR180_ROOT=<project dir> /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd sim/measure_geometry.py
# Reads asm_parts/*.step (assembly coords, x=0 tunnel front face, mm), writes sim/geometry_measured.json.
import FreeCAD as App, Part, math, os, sys, json, time
V = App.Vector
ROOT = os.environ.get('GR180_ROOT', os.getcwd())
ASM = os.path.join(ROOT, 'asm_parts')
OUTF = os.path.join(ROOT, 'sim', 'geometry_measured.json')
def pr(*a): print(*a); sys.stdout.flush()
def load(n):
    s = Part.Shape(); s.read(os.path.join(ASM, n + '.step')); return s

def blade_row_throat(shape, radii, x0, x1, n_expected, label):
    """Slice a blade row with thin cylindrical shells; min distance between neighbouring blade sections = throat width o(r)."""
    rows = []
    for r in radii:
        shell = Part.makeCylinder(r + 0.05, x1 - x0, V(x0, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(r - 0.05, x1 - x0, V(x0, 0, 0), V(1, 0, 0)))
        sols = shape.common(shell).Solids
        sols = sorted(sols, key=lambda s: math.atan2(s.CenterOfMass.z, s.CenterOfMass.y))
        n = len(sols)
        if n < 2: rows.append({'r': r, 'n': n}); continue
        d = [sols[i].distToShape(sols[(i + 1) % n])[0] for i in range(n)]
        rows.append({'r': r, 'n': n, 'o_min': min(d), 'o_mean': sum(d) / n, 'pitch': 2 * math.pi * r / n})
        pr('%s r=%.2f sections=%d throat o=%.3f (mean %.3f) pitch %.3f' % (label, r, n, min(d), sum(d) / n, 2 * math.pi * r / n))
    good = [x for x in rows if x.get('n') == n_expected]
    A = 0.0
    for a, b in zip(good[:-1], good[1:]): A += 0.5 * (a['o_mean'] + b['o_mean']) * (b['r'] - a['r'])
    return rows, A * n_expected   # area between first and last measured radius

res = {}
t0 = time.time()
# ---- NGV: vanes between inner shroud r22.25 and shroud bore r35.25 (v12)
ngv = load('NGV')
rr = [22.6 + k * (34.9 - 22.6) / 8 for k in range(9)]
rows, A = blade_row_throat(ngv, rr, 94.8, 118.8, 15, 'NGV')
A_full = A * (35.25 - 22.25) / (rr[-1] - rr[0])
res['NGV'] = {'rows': rows, 'throat_area_mm2': A_full, 'annulus_mm2': math.pi * (35.25**2 - 22.25**2)}
pr('NGV throat area %.0f mm2 (annulus %.0f), eff. exit angle %.1f deg' % (A_full, res['NGV']['annulus_mm2'], math.degrees(math.acos(A_full / res['NGV']['annulus_mm2']))))
# ---- Turbine rotor: blades r22.1 (rim) .. r35.15 (tip)
tw = load('Turbine')
rr = [22.5 + k * (34.9 - 22.5) / 8 for k in range(9)]
rows, A = blade_row_throat(tw, rr, 107.3, 121.9, 23, 'TURB')
A_full = A * (35.15 - 22.1) / (rr[-1] - rr[0])
res['Turbine'] = {'rows': rows, 'throat_area_mm2': A_full, 'annulus_mm2': math.pi * (35.15**2 - 22.1**2)}
pr('Turbine throat area %.0f mm2 (annulus %.0f), eff. exit angle %.1f deg' % (A_full, res['Turbine']['annulus_mm2'], math.degrees(math.acos(A_full / res['Turbine']['annulus_mm2']))))
# ---- Diffuser: vane passage x -11.3 .. -4.3 (height 7.0); slice with thin axial slabs
dif = load('Diffuser')
drows = []
for x in (-10.8, -7.8, -4.8):
    slab = Part.makeCylinder(60, 0.1, V(x - 0.05, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(37.5, 0.1, V(x - 0.05, 0, 0), V(1, 0, 0)))
    sols = [s for s in dif.common(slab).Solids if s.Volume > 1e-3]
    sols = sorted(sols, key=lambda s: math.atan2(s.CenterOfMass.z, s.CenterOfMass.y))
    n = len(sols)
    d = [sols[i].distToShape(sols[(i + 1) % n])[0] for i in range(n)] if n > 1 else []
    rmin = min(min(math.hypot(v.Point.y, v.Point.z) for v in s.Vertexes) for s in sols) if sols else 0
    drows.append({'x': x, 'n': n, 'o_min': min(d) if d else None, 'o_mean': sum(d) / len(d) if d else None, 'r_le': rmin})
    pr('DIFF x=%.1f sections=%d throat o_min=%s mean=%s r_LE=%.2f' % (x, n, d and round(min(d), 3), d and round(sum(d) / len(d), 3), rmin))
res['Diffuser'] = {'rows': drows, 'passage_height_mm': 7.0}
# ---- impeller exit width and diffuser entry width (radial face positions)
cw = load('Compressor')
bb = cw.BoundBox
res['Compressor'] = {'x_min': bb.XMin, 'x_max': bb.XMax, 'D': bb.YLength}
# ---- rotor mass properties (density g/mm3)
RHO = {'Shaft': 7.85e-3, 'NoseCone': 2.70e-3, 'Compressor': 2.76e-3, 'Turbine': 8.00e-3, 'TurbineNut': 8.00e-3,
       'RearSpacer_8x12x6_3': 7.85e-3, 'FrontShim_8x12x2_1': 7.85e-3, 'RPM_Magnet': 7.50e-3, 'Balance_Slug': 8.50e-3}
mp = {}
for n, rho in RHO.items():
    s = load(n)
    sol = s.Solids
    Vt = sum(x.Volume for x in sol)
    cx = sum(x.Volume * x.CenterOfMass.x for x in sol) / Vt
    Ip = 0.0; It = 0.0
    for x in sol:   # inertia about the x axis (polar) and about a transverse axis through the part CoM
        M = x.MatrixOfInertia; c = x.CenterOfMass
        Ip += M.A11 + x.Volume * (c.y**2 + c.z**2)
        It += 0.5 * (M.A22 + M.A33) + x.Volume * ((c.x - cx)**2 + 0.5 * (c.y**2 + c.z**2))
    mp[n] = {'mass_g': Vt * rho, 'x_cg': cx, 'Ip_gmm2': Ip * rho, 'It_gmm2': It * rho, 'x_min': s.BoundBox.XMin, 'x_max': s.BoundBox.XMax}
    pr('MASS %-22s m=%7.2f g  x_cg=%7.2f  Ip=%9.0f  It=%9.0f g.mm2' % (n, Vt * rho, cx, Ip * rho, It * rho))
res['rotor_parts'] = mp
json.dump(res, open(OUTF, 'w'), indent=1)
pr('wrote', OUTF, 'in %.0fs' % (time.time() - t0))
