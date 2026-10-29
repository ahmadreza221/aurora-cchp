"""AURORA-1000 two-stage axial turbine (15,000 rpm): blade-row aero design and CAD (vacuum-cast MAR-M247 blisks + NGV rings).

Source of the stage data: sim/mw1_meanline.json (python3 sim/mw1_meanline.py). Sections are built with the GR180 E1 blade
section generator (cad/engine/gg_turbine.py: conformal-plane camber + thickness, round TE tangent to the sides, throat
gauging solve with Carter deviation), on cylindrical stream surfaces at 5 span fractions per row (free vortex,
constant Cx, axial inlet to both NGVs, zero exit swirl after both rotors). Rotor sections are stacked on their
centroids, NGV sections on the trailing edge.

Frame: x axial downstream from the NGV1 leading edge [mm], radius [mm], +theta = direction of rotation.
Run:  python3 cad/engine/a1000_turbine.py                 aero design report -> sim/a1000_turbine_design.json
      freecadcmd -c "import sys; sys.argv=['x','--cad']; exec(open('cad/engine/a1000_turbine.py').read())"   CAD
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import gg_turbine as GG                                           # noqa: E402  (Section, Stream, throat, gauging solve)

ML = json.load(open(os.path.join(ROOT, 'sim', 'mw1_meanline.json')))
T = ML['turbine']
N_RPM = ML['rpm']; OM = N_RPM * 2 * math.pi / 60
RM = T['Dm'] / 2 * 1e3                                            # mean radius [mm], constant
CX = T['Cx']                                                      # axial velocity [m/s], constant
CT2_M = CX * math.tan(math.radians(T['alpha2']))                  # NGV exit swirl at the mean radius
K_SW = CT2_M * RM * 1e-3                                          # r C_theta [m2/s] (free vortex)
CP_G, GAM = 1170.0, 1.33; R_G = CP_G * (GAM - 1) / GAM
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')

# ------------------------------------------------------------------------------------------------ annulus and rows
# (x, blade height) at the row boundaries: NGV1 LE, NGV1/R1 gap, R1/NGV2 gap, NGV2/R2 gap, R2 TE
S1, S2 = T['stages']
GAP1, GAP2, GAP3 = 8.0, 9.0, 11.0
CX_ROW = dict(N1=S1['cx_ngv'] * 1e3, R1=S1['cx_rot'] * 1e3, N2=S2['cx_ngv'] * 1e3, R2=S2['cx_rot'] * 1e3)
X_LE = dict(N1=0.0)
X_LE['R1'] = X_LE['N1'] + CX_ROW['N1'] + GAP1
X_LE['N2'] = X_LE['R1'] + CX_ROW['R1'] + GAP2
X_LE['R2'] = X_LE['N2'] + CX_ROW['N2'] + GAP3
X_TE = {k: X_LE[k] + CX_ROW[k] for k in X_LE}
H_ST = [(X_LE['N1'], S1['h_ngv_in'] * 1e3), (X_TE['N1'] + GAP1 / 2, S1['h_ngv_out'] * 1e3),
        (X_TE['R1'] + GAP2 / 2, S1['h_rot_out'] * 1e3), (X_TE['N2'] + GAP3 / 2, S2['h_ngv_out'] * 1e3),
        (X_TE['R2'], S2['h_rot_out'] * 1e3)]
Z = dict(N1=S1['Z_ngv'], R1=S1['Z_rot'], N2=S2['Z_ngv'], R2=S2['Z_rot'])
SPANS = [0.0, 0.25, 0.50, 0.75, 1.0]
ROW_T0 = dict(N1=S1['T0_in'], R1=S1['T0_in'], N2=S2['T0_in'], R2=S2['T0_in'])


def height(x):
    xs, hs = zip(*H_ST); return float(np.interp(x, xs, hs))


def r_hub(x): return RM - height(x) / 2


def r_tip(x): return RM + height(x) / 2


def row_radius(row, f):
    """section radius at span fraction f, taken at the row mid-chord"""
    xm = 0.5 * (X_LE[row] + X_TE[row]); return r_hub(xm) + f * height(xm)


# ------------------------------------------------------------------------------------------------ flow angles
def ct2(r_mm): return K_SW / (r_mm * 1e-3)                        # NGV exit swirl (free vortex)


def alpha_ngv_out(r_mm): return math.degrees(math.atan2(ct2(r_mm), CX))


def beta_rot_in(r_mm): return math.degrees(math.atan2(ct2(r_mm) - OM * r_mm * 1e-3, CX))


def beta_rot_out(r_mm): return math.degrees(math.atan2(-OM * r_mm * 1e-3, CX))   # C_theta3 = 0


def mach(V, T0): T = T0 - V**2 / (2 * CP_G); return V / math.sqrt(GAM * R_G * T)


def reaction(r_mm):
    U = OM * r_mm * 1e-3; return 1 - ct2(r_mm) / (2 * U)            # with C_theta1 = C_theta3 = 0


# ------------------------------------------------------------------------------------------------ section parameters
def params(row, f):
    """thickness / LE / TE / camber shape per row and span (cast MAR-M247; TE >= 0.8 mm castable at this size)"""
    if row.startswith('N'):
        c = CX_ROW[row]
        return dict(tau=0.20, rle=0.075 * c, tte=1.0, sig_m=0.30, p=1.9)
    c = CX_ROW[row]
    return dict(tau=0.20 - 0.10 * f, rle=(0.045 - 0.015 * f) * c, tte=0.95 - 0.20 * f, sig_m=0.32 + 0.06 * f, p=2.0 - 0.4 * f)


def design_row(row):
    secs = {}
    for f in SPANS:
        r = row_radius(row, f); q = params(row, f); st = GG.Stream(r_const=r)
        x0, x1 = X_LE[row], X_TE[row]
        if row.startswith('N'):
            flow_out = alpha_ngv_out(r); k1 = 0.0
            Mx = mach(math.hypot(CX, ct2(r)), ROW_T0[row])
            def make(k2, st=st, q=q, x0=x0, x1=x1):
                s0 = GG.Section(st, x0, x1, 0.0, k2, q['p'], q['tau'], q['rle'], q['tte'], q['sig_m'])
                return GG.Section(st, x0, x1, 0.0, k2, q['p'], q['tau'], q['rle'], q['tte'], q['sig_m'], -s0.th[-1])
            sec = GG._solve_section(make, flow_out, Z[row], +1, q['p'], 0.0, +1, Mx)
            sec.flow_in, sec.flow_out = 0.0, flow_out
        else:
            k1 = beta_rot_in(r); flow_out = beta_rot_out(r)
            W3 = math.hypot(CX, OM * r * 1e-3); Mx = mach(W3, ROW_T0[row] - 70.0)
            def make(k2, st=st, q=q, x0=x0, x1=x1, k1=k1):
                s0 = GG.Section(st, x0, x1, k1, k2, q['p'], q['tau'], q['rle'], q['tte'], q['sig_m'])
                xc, tc, A = s0.centroid()
                return GG.Section(st, x0, x1, k1, k2, q['p'], q['tau'], q['rle'], q['tte'], q['sig_m'], -tc)
            sec = GG._solve_section(make, abs(flow_out), Z[row], -1, q['p'], k1, -1, Mx)
            sec.flow_in, sec.flow_out = k1, flow_out
        sec.r, sec.span, sec.M_exit_row = r, f, Mx
        # Zweifel loading coefficient (axial chord based)
        a_in, a_out = math.radians(sec.flow_in), math.radians(abs(sec.flow_out))
        s_pitch = 2 * math.pi * r / Z[row]; cx = x1 - x0
        sec.zweifel = 2 * (s_pitch / cx) * math.cos(a_out)**2 * abs(math.tan(a_out) + math.tan(a_in))
        secs[f] = sec
    return secs


def report(rows):
    out = {}
    print('AURORA-1000 turbine @ %.0f rpm: rm %.1f mm, Cx %.0f m/s, NGV exit swirl r*Ct %.1f m2/s' % (N_RPM, RM, CX, K_SW))
    print('rows (x LE..TE, Z): ' + '  '.join('%s %.1f..%.1f Z%d' % (k, X_LE[k], X_TE[k], Z[k]) for k in X_LE))
    for row, secs in rows.items():
        print('%s  span   r    in/out flow   k1/k2 metal  gauge  dev   o/s    chord  tmax  Zw    Mex  %s' % (
            row, 'R(hub->)' if row.startswith('R') else ''))
        throat = 0.0; rs = sorted(secs)
        for f in rs:
            s = secs[f]
            extra = '  R %.2f' % reaction(s.r) if row.startswith('R') else ''
            print('    %4.2f %6.1f  %6.1f/%6.1f  %6.1f/%6.1f  %5.1f %4.1f  %.3f  %5.1f  %4.2f  %.2f  %.2f%s' % (
                f, s.r, s.flow_in, s.flow_out, s.k1, s.k2, s.gauging, s.dev, s.o / s.pitch, s.chord, s.tmax_mm, s.zweifel,
                s.M_exit_row, extra))
        # throat area: integrate o(r) over the span at the TE
        rr = [secs[f].r for f in rs]; oo = [secs[f].o for f in rs]
        A = Z[row] * np.trapezoid(oo, rr) if hasattr(np, 'trapezoid') else Z[row] * np.trapz(oo, rr)
        print('    throat area %.0f cm2' % (A / 100) + (' (meanline %.0f)' % ((S1 if row == 'N1' else S2)['A_throat_ngv'] * 1e4)
                                                     if row.startswith('N') else ''))
        out[row] = dict(Z=Z[row], x_le=X_LE[row], x_te=X_TE[row], throat_cm2=A / 100,
                        sections=[dict(span=f, r=secs[f].r, flow_in=secs[f].flow_in, flow_out=secs[f].flow_out,
                                       k1=secs[f].k1, k2=secs[f].k2, gauging=secs[f].gauging, dev=secs[f].dev,
                                       o_s=secs[f].o / secs[f].pitch, chord=secs[f].chord, tmax=secs[f].tmax_mm,
                                       zweifel=secs[f].zweifel, M_exit=secs[f].M_exit_row, tte=secs[f].tte,
                                       rle=secs[f].rle) for f in rs])
    out['annulus'] = dict(stations=H_ST, rm=RM)
    json.dump(out, open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json'), 'w'), indent=1, default=float)
    return out


def design_all():
    return {row: design_row(row) for row in ('N1', 'R1', 'N2', 'R2')}


if __name__ == '__main__' and '--cad' not in sys.argv and '--quiet' not in sys.argv:
    report(design_all())


# ================================================================================================ CAD (FreeCAD)
FILLET = dict(R1=3.0, R2=3.5)                     # rotor root fillet radius [mm]
TIP_CL = dict(R1=0.50, R2=0.60)                   # cold radial tip clearance [mm]
PLAT_OVH = 4.5                                    # platform overhang beyond the blade LE / TE [mm] (> fillet radius)
DENSE, NPTS = (1500, 61), 200


def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def _wire(sec, delta=0.0):
    pts = sec.outline_offset(delta, *DENSE) if delta > 0 else sec.outline(*DENSE)[0]
    return GG.bs_wire(GG.resample_closed(pts, NPTS))


def _plane_wire(sec, n, delta=0.0):
    """end cap of a closed loft: the section outline moved radially onto the plane at distance n from the axis, normal to
    the radial direction at the section's mid angle (non-planar caps on r = const give invalid solids)"""
    pts = sec.outline_offset(delta, *DENSE) if delta > 0 else sec.outline(*DENSE)[0]
    pts = GG.resample_closed(pts, NPTS)
    th = np.arctan2(pts[:, 2], pts[:, 1]); tm = 0.5 * (th.min() + th.max())
    return GG.bs_wire(GG.project_to_plane(pts, lambda x: np.full_like(np.asarray(x, float), n), tm))


def _rev(poly):
    """solid of revolution about x of a closed (x, r) polygon"""
    App, Part, V = _fc()
    w = Part.makePolygon([V(x, r, 0) for x, r in poly] + [V(poly[0][0], poly[0][1], 0)])
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)


def _ext_section(sec, r_new):
    """copy of a design section (same angles / thickness) on another cylinder radius, same stacking rule"""
    a = (GG.Stream(r_const=r_new), sec.x_le, sec.x_te, sec.k1, sec.k2, sec.p, sec.tau, sec.rle, sec.tte, sec.sig_m)
    s0 = GG.Section(*a)
    if sec.k1 == 0.0:                                             # NGV: TE stacking
        return GG.Section(*a, -s0.th[-1])
    return GG.Section(*a, -s0.centroid()[1])


def fc_rotor_blade(row, secs):
    """rotor blade with an integral root fillet (sections follow the blade twist), buried cap below the platform, tip
    trimmed to the casing cone minus the tip clearance, axial trim at the platform ends"""
    App, Part, V = _fc()
    ss = sorted(secs); hub = secs[0.0]; nxt = secs[ss[1]]; R = FILLET[row]; rh = hub.r
    wires = []
    wires.append(_plane_wire(hub, rh - 2.5, R))                   # buried planar foot, fillet width
    for hk in GG.FILLET_H:
        h = hk * R / 0.8
        w = h / (nxt.r - hub.r); L = lambda a, b: a + w * (b - a)
        sec = GG.Section(GG.StreamOffset(h, r_cyl=rh), *(L(getattr(hub, k), getattr(nxt, k)) for k in
                         ('x_le', 'x_te', 'k1', 'k2', 'p', 'tau', 'rle', 'tte', 'sig_m', 'dth')))
        wires.append(_wire(sec, GG.fillet_offset(h, R)))
    for f in ss[1:]:
        wires.append(_wire(secs[f]))
    xt0, xt1 = X_LE[row] - PLAT_OVH, X_TE[row] + PLAT_OVH
    r_top = max(r_tip(xt0), r_tip(xt1))
    wires.append(_wire(_ext_section(secs[1.0], r_top + 1.0)))     # cylinder section above the casing: the tip cut stays
    wires.append(_plane_wire(secs[1.0], r_top + 4.0))             # between cylinder sections (clean intersection curve)
    b = Part.makeLoft(wires, True, False)
    if b.Volume < 0: b = Part.makeLoft(wires[::-1], True, False)
    trim = _rev([(xt0 + 0.05, rh - 10), (xt0 + 0.05, r_tip(xt0) - TIP_CL[row]), (xt1 - 0.05, r_tip(xt1) - TIP_CL[row]),
                 (xt1 - 0.05, rh - 10)])
    return b.common(trim)


def disc_profile(row):
    """bore-less disc (x, r) polygon: platform rim, web, solid hub boss; MAR-M247 integral with the blades"""
    rh = row_radius(row, 0.0); x0, x1 = X_LE[row] - PLAT_OVH, X_TE[row] + PLAT_OVH; xm = 0.5 * (x0 + x1)
    rim_d = 18.0 if row == 'R1' else 19.0; web = 18.0 if row == 'R1' else 20.0; hub_w = 42.0 if row == 'R1' else 46.0
    r_rim, r_hubb = rh - rim_d, 95.0
    return [(x0, rh), (x1, rh), (x1, r_rim + 4), (xm + web / 2 + 6, r_rim - 2), (xm + web / 2, r_rim - 10),
            (xm + web / 2, r_hubb + 12), (xm + hub_w / 2, r_hubb - 4), (xm + hub_w / 2, 0.0), (xm - hub_w / 2, 0.0),
            (xm - hub_w / 2, r_hubb - 4), (xm - web / 2, r_hubb + 12), (xm - web / 2, r_rim - 10),
            (xm - web / 2 - 6, r_rim - 2), (x0, r_rim + 4)]


def fc_ngv_vane(row, secs):
    App, Part, V = _fc()
    ss = sorted(secs)
    x0, x1 = X_LE[row], X_TE[row]
    r_in = min(r_hub(x0), r_hub(x1)) - 3.0; r_out = max(r_tip(x0), r_tip(x1)) + 3.0
    wires = [_plane_wire(secs[ss[0]], r_in)] + [_wire(secs[f]) for f in ss] + [_plane_wire(secs[ss[-1]], r_out)]
    v = Part.makeLoft(wires, True, False)
    if v.Volume < 0: v = Part.makeLoft(wires[::-1], True, False)
    return v


def ngv_rings(row, t_in=6.0, t_out=8.0, ext=4.0):
    x0, x1 = X_LE[row] - ext, X_TE[row] + ext
    inner = _rev([(x0, r_hub(x0) - t_in), (x1, r_hub(x1) - t_in), (x1, r_hub(x1)), (x0, r_hub(x0))])
    outer = _rev([(x0, r_tip(x0)), (x1, r_tip(x1)), (x1, r_tip(x1) + t_out), (x0, r_tip(x0) + t_out)])
    passage = _rev([(x0, r_hub(x0)), (x1, r_hub(x1)), (x1, r_tip(x1)), (x0, r_tip(x0))])
    return inner, outer, passage


def build_cad():
    App, Part, V = _fc()
    os.makedirs(OUT, exist_ok=True)
    rows = design_all()
    info = {}
    def save(name, s):
        s.exportStep(os.path.join(OUT, name + '.step')); s.exportBrep(os.path.join(OUT, name + '.brep'))
        vv, tt = s.tessellate(0.05); P = np.array([(p.x, p.y, p.z) for p in vv]); Tt = np.array(tt)
        vol = np.sum(np.einsum('ij,ij->i', P[Tt[:, 0]], np.cross(P[Tt[:, 1]], P[Tt[:, 2]]))) / 6
        info[name] = dict(valid=s.isValid(), solids=len(s.Solids), vol_mm3=vol, mass_kg=vol * 8.54e-6)   # MAR-M247 8.54 g/cc
        print('%-22s valid %s solids %d  vol %.0f cm3  mass %.2f kg' % (name, s.isValid(), len(s.Solids), vol / 1e3, vol * 8.54e-6), flush=True)
    for row in ('R1', 'R2'):
        blade = fc_rotor_blade(row, rows[row])
        disc = _rev(disc_profile(row)); disc.rotate(V(0, 0, 0), V(1, 0, 0), 180.0 / Z[row])
        piece = blade.cut(disc)
        save('A1000_%s_blade' % row, piece); save('A1000_%s_disc' % row, disc)
        if '--full' in sys.argv:
            w, B = disc, 6
            for k0 in range(0, Z[row], B):
                w = w.fuse([GG.rot_shape(piece, 360.0 * k / Z[row]) for k in range(k0, min(k0 + B, Z[row]))])
            try: w = w.removeSplitter()
            except Exception: pass
            save('A1000_%s_blisk' % row, w)
    for row in ('N1', 'N2'):
        vane = fc_ngv_vane(row, rows[row]); inner, outer, passage = ngv_rings(row)
        piece = vane.common(passage)
        save('A1000_%s_vane' % row, piece)
        rings = inner.fuse(outer); rings.rotate(V(0, 0, 0), V(1, 0, 0), 180.0 / Z[row])
        save('A1000_%s_rings' % row, rings)
        if '--full' in sys.argv:
            w, B = rings, 8
            for k0 in range(0, Z[row], B):
                w = w.fuse([GG.rot_shape(piece, 360.0 * k / Z[row]) for k in range(k0, min(k0 + B, Z[row]))])
            save('A1000_%s_ring' % row, w)
    json.dump(info, open(os.path.join(OUT, 'A1000_parts.json'), 'w'), indent=1, default=float)


if '--cad' in sys.argv:
    build_cad()
