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
# rev 3 (blade FEA): NGV2 33 -> 47 vanes with the NGV1 axial chord (26 mm instead of 37): EO33 hit the R2 3rd mode
# (8,282 Hz at 15k: +0.4 %) and the R1 2nd mode (-7.7 %); EO47 = 11,750 Hz lies in the gaps R1 F2-F3 (7,615-14,044 Hz)
# and R2 F5-F6 (10,109-14,560 Hz), margins >= 14 %; same Zweifel band, 11 mm shorter turbine, weaker potential field on R1
CX_ROW['N2'] = 26.0
X_LE = dict(N1=0.0)
X_LE['R1'] = X_LE['N1'] + CX_ROW['N1'] + GAP1
X_LE['N2'] = X_LE['R1'] + CX_ROW['R1'] + GAP2
X_LE['R2'] = X_LE['N2'] + CX_ROW['N2'] + GAP3
X_TE = {k: X_LE[k] + CX_ROW[k] for k in X_LE}
H_ST = [(X_LE['N1'], S1['h_ngv_in'] * 1e3), (X_TE['N1'] + GAP1 / 2, S1['h_ngv_out'] * 1e3),
        (X_TE['R1'] + GAP2 / 2, S1['h_rot_out'] * 1e3), (X_TE['N2'] + GAP3 / 2, S2['h_ngv_out'] * 1e3),
        (X_TE['R2'], S2['h_rot_out'] * 1e3)]
Z = dict(N1=S1['Z_ngv'], R1=S1['Z_rot'], N2=S2['Z_ngv'], R2=S2['Z_rot'])
# rev 2: NGV1 47 -> 43 vanes: 2 x 47 = EO94 crossed R1 F6 at 15,300 rpm (+2 % at 15k); 43 keeps EO43 / EO86 >= 11 % away
Z['N1'] = 43
Z['N2'] = 47
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
    c = CX_ROW[row] * (1 - CX_TAPER[row] * f)
    t0, t1 = ROT_TAU[row]
    return dict(tau=t0 - (t0 - t1) * f, rle=(0.045 - 0.015 * f) * c, tte=1.0 - 0.25 * f, sig_m=0.32 + 0.06 * f, p=2.0 - 0.4 * f)


# rotor taper for the creep life of the uncooled blades (rev 2, 2026-10-29): root net-section stress R1 129 -> ~105 MPa
ROT_TAU = dict(R1=(0.21, 0.07), R2=(0.20, 0.06))                 # max thickness / chord at hub, tip
CX_TAPER = dict(R1=0.15, R2=0.25, N1=0.0, N2=0.0)                # axial chord at the tip = (1 - taper) x hub (LE line fixed)


def x_te_of(row, f):
    return X_LE[row] + CX_ROW[row] * (1 - CX_TAPER[row] * f)


def design_row(row, spans=SPANS):
    secs = {}
    for f in spans:
        r = row_radius(row, f); q = params(row, f); st = GG.Stream(r_const=r)
        x0, x1 = X_LE[row], x_te_of(row, f)
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
        # (sections sit on the mid-chord radii; the throat lies at the TE, where the flared annulus is taller: span-scaled)
        rr = [secs[f].r for f in rs]; oo = [secs[f].o for f in rs]
        A = Z[row] * np.trapezoid(oo, rr) if hasattr(np, 'trapezoid') else Z[row] * np.trapz(oo, rr)
        xm = 0.5 * (X_LE[row] + X_TE[row]); A *= height(X_TE[row]) / height(xm)
        print('    throat area %.0f cm2' % (A / 100) + (' (meanline %.0f)' % ((S1 if row == 'N1' else S2)['A_throat_ngv'] * 1e4)
                                                     if row.startswith('N') else ''))
        out[row] = dict(Z=Z[row], x_le=X_LE[row], x_te=X_TE[row], throat_cm2=A / 100,
                        sections=[dict(span=f, r=secs[f].r, flow_in=secs[f].flow_in, flow_out=secs[f].flow_out,
                                       k1=secs[f].k1, k2=secs[f].k2, gauging=secs[f].gauging, dev=secs[f].dev,
                                       o_s=secs[f].o / secs[f].pitch, chord=secs[f].chord, tmax=secs[f].tmax_mm,
                                       zweifel=secs[f].zweifel, M_exit=secs[f].M_exit_row, tte=secs[f].tte,
                                       rle=secs[f].rle) for f in rs])
    out['annulus'] = dict(stations=H_ST, rm=RM)
    path = os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')       # atomic: readers never see a half-written file
    with open(path + '.tmp', 'w') as f:
        json.dump(out, f, indent=1, default=float)
    os.replace(path + '.tmp', path)
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


SEG_N = (12, 88, 88, 12)                          # points: TE cap (to suction), suction side, pressure side, TE cap (back)


def _consistent_points(sec, delta=0.0):
    """outline resampled PER SEGMENT (TE half-cap, upper side, lower side, TE half-cap) at even arc length with fixed point
    counts: every section has the same topology, so the loft rulings join TE to TE and LE to LE. A global arc-length
    resample shifts the TE cap points between sections of very different chord / thickness and folds the loft at the TE
    (gmsh then fails with intersecting facets)."""
    pts, side, xis = sec.outline(*DENSE)
    if delta > 0: pts = sec.outline_offset(delta, *DENSE)
    i_up0 = int(np.argmax(side == 1)); i_lo0 = int(np.argmax(side == -1)); i_cap2 = len(side) - int(np.argmax(side[::-1] != 0))
    segs = [pts[:i_up0 + 1], pts[i_up0:i_lo0], pts[i_lo0 - 1:i_cap2], np.vstack([pts[i_cap2 - 1:], pts[:1]])]
    out = []
    for seg, n in zip(segs, SEG_N):
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(seg, axis=0), axis=1))]
        t = np.linspace(0, d[-1], n + 1)[:-1]
        out.append(np.stack([np.interp(t, d, seg[:, k]) for k in range(3)], 1))
    return np.vstack(out)


def _wire(sec, delta=0.0):
    return GG.bs_wire(_consistent_points(sec, delta))


def _plane_wire(sec, n, delta=0.0):
    """end cap of a closed loft: the section outline moved radially onto the plane at distance n from the axis, normal to
    the radial direction at the section's mid angle (non-planar caps on r = const give invalid solids)"""
    pts = _consistent_points(sec, delta)
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


CAD_N = 7                                          # rotor CAD sections above the root fillet


def rotor_cad_spans(row):
    """loft sections for the rotor CAD: hub + sections EVENLY spaced from the fillet top to the tip. The design spans
    (0, .25, .5, .75, 1) after the closely spaced fillet sections made the B-spline loft overshoot between 0.25 and 0.5 span,
    and the 1 mm trailing edge folded through itself (Netgen / gmsh: self-intersecting facets at r 227 mm, x 57 mm on R1)"""
    xm = 0.5 * (X_LE[row] + X_TE[row]); ff = max(GG.FILLET_H) * FILLET[row] / 0.8 / height(xm)
    return [0.0] + [ff + k * (1 - ff) / CAD_N for k in range(1, CAD_N)] + [1.0]


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


def round_polygon(poly, radii, n=10):
    """replace each vertex of a closed polygon by a tangent circular arc of radius radii[i] (0 = sharp)"""
    P = np.array(poly, float); out = []
    for i in range(len(P)):
        R = radii[i]; a, v, c = P[i - 1], P[i], P[(i + 1) % len(P)]
        if R <= 0: out.append(tuple(v)); continue
        u1 = (a - v) / np.linalg.norm(a - v); u2 = (c - v) / np.linalg.norm(c - v)
        ang = math.acos(np.clip(u1 @ u2, -1, 1)); d = R / math.tan(ang / 2)
        d = min(d, 0.45 * np.linalg.norm(a - v), 0.45 * np.linalg.norm(c - v)); R = d * math.tan(ang / 2)
        p1, p2 = v + u1 * d, v + u2 * d
        bis = (u1 + u2) / np.linalg.norm(u1 + u2); ctr = v + bis * R / math.sin(ang / 2)
        t1, t2 = math.atan2(*(p1 - ctr)[::-1]), math.atan2(*(p2 - ctr)[::-1])
        dt = (t2 - t1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            t = t1 + dt * k / n; out.append((ctr[0] + R * math.cos(t), ctr[1] + R * math.sin(t)))
    return out


DISC = dict(R1=dict(rim_d=16.0, t_rim=16.0, t_hub=40.0, r_web_in=110.0, hub_w=56.0, r_boss=85.0, R_rim=10.0, R_hub=28.0),
            R2=dict(rim_d=17.0, t_rim=18.0, t_hub=46.0, r_web_in=110.0, hub_w=62.0, r_boss=85.0, R_rim=10.0, R_hub=30.0))


def disc_profile(row, P=None):
    """bore-less disc (x, r) polygon: platform rim, web tapered from the rim to the hub (constant-strength trend), large
    fillets, solid hub boss; cast MAR-M247 integral with the blades"""
    q = dict(DISC[row], **(P or {}))
    rh = row_radius(row, 0.0); x0, x1 = X_LE[row] - PLAT_OVH, X_TE[row] + PLAT_OVH; xm = 0.5 * (x0 + x1)
    r_rim = rh - q['rim_d']; tr, th, hw = q['t_rim'] / 2, q['t_hub'] / 2, q['hub_w'] / 2
    poly = [(x0, rh), (x1, rh), (x1, r_rim + 6), (xm + tr, r_rim - 4), (xm + th, q['r_web_in']), (xm + hw, q['r_boss']),
            (xm + hw, 0.0), (xm - hw, 0.0), (xm - hw, q['r_boss']), (xm - th, q['r_web_in']), (xm - tr, r_rim - 4), (x0, r_rim + 6)]
    radii = [0, 0, 3.0, q['R_rim'], q['R_hub'], 8.0, 0, 0, 8.0, q['R_hub'], q['R_rim'], 3.0]
    return round_polygon(poly, radii)


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
    for row in ('R1', 'R2'): rows[row] = design_row(row, rotor_cad_spans(row))
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


R_IN_SECTOR = 60.0                                 # cyclic sector: inner cut of the disc (held at the curvic hub faces)


def build_sector(row):
    """1/Z cyclic-symmetry sector of a blisk for CalculiX (sim/engine/a1000_blisk_cyclic.py): disc between r = R_IN_SECTOR and
    the platform, cut by two radial planes one pitch apart through the blade stacking line; the sector is
    (disc + blades -1, 0, +1) x wedge, so both cut faces match exactly"""
    App, Part, V = _fc()
    # the exported pieces (--cad) are used, the same as in the blade FEA; booleans on the re-read BREPs are also the robust
    # ones (the in-memory pieces gave empty fuse results for R2)
    piece = Part.Shape(); piece.read(os.path.join(OUT, 'A1000_%s_blade.brep' % row))
    disc = Part.Shape(); disc.read(os.path.join(OUT, 'A1000_%s_disc.brep' % row))
    rh = row_radius(row, 0.0)
    th = []
    for f in piece.Faces:
        u0, u1, v0, v1 = f.ParameterRange
        for i in range(31):
            for j in range(31):
                p = f.valueAt(u0 + (u1 - u0) * i / 30, v0 + (v1 - v0) * j / 30)
                if math.hypot(p.y, p.z) <= rh + 0.25 and f.isInside(p, 1e-4, True): th.append(math.atan2(p.z, p.y))
    pitch = 2 * math.pi / Z[row]; th_lo, th_hi = min(th), max(th)
    # cut planes near the centroid stacking line (theta = 0) of blade 0 and blade +1: the blades are cut where they are
    # thickest at every span (a plane between the roots crosses the thin LE / TE of a neighbour: invalid sliver fuse).
    # The disc is fused with blades -1, 0, +1 first and the wedge taken from that (fusing the disc sector with the cut blade
    # fragments returned reversed / empty solids for R2); a result failing the volume check is retried at an offset.
    poly = disc_profile(row); xa, xb = min(x for x, r in poly) - 2.0, max(x for x, r in poly) + 2.0
    Rw = rh + 80.0
    blades = []
    for k in (-1, 0, 1):
        bk = piece.copy(); bk.rotate(V(0, 0, 0), V(1, 0, 0), math.degrees(k * pitch)); blades.append(bk)
    full = disc.fuse(blades)
    hole = Part.makeCylinder(R_IN_SECTOR, xb - xa, V(xa, 0, 0), V(1, 0, 0))
    def n_cut_faces(q, th):                                      # faces lying in the plane through the axis at angle th
        nrm = (-math.sin(th), math.cos(th))
        return sum(1 for f in q.Faces if all(abs(v.Point.y * nrm[0] + v.Point.z * nrm[1]) < 1e-4 for v in f.Vertexes))
    for theta0 in [math.radians(a) for a in (0.0, 0.35, -0.35, 0.7, -0.7)]:
        tri = Part.makePolygon([V(xa, 0, 0), V(xa, Rw * math.cos(theta0), Rw * math.sin(theta0)),
                                V(xa, Rw * math.cos(theta0 + pitch), Rw * math.sin(theta0 + pitch)), V(xa, 0, 0)])
        wedge = Part.Face(tri).extrude(V(xb - xa, 0, 0))
        disc_cut = disc.common(wedge).cut(hole)
        v_exp = disc_cut.Volume + piece.Volume
        ok = lambda q: len(q.Solids) == 1 and q.isValid() and abs(abs(q.Solids[0].Volume) - v_exp) < 0.05 * v_exp
        sector = full.common(wedge).cut(hole)
        try:                                                      # merge the coplanar cut faces (one face per cut plane)
            s2 = sector.removeSplitter()
            if ok(s2): sector = s2
        except Exception: pass
        nl_, nr_ = n_cut_faces(sector, theta0), n_cut_faces(sector, theta0 + pitch)
        if ok(sector): break     # cut faces may split differently on the two planes: CalculiX ties non-matching meshes
        print('  theta0 %.2f deg: %d solids %s, cut faces %d / %d, retry' % (
            math.degrees(theta0), len(sector.Solids), [round(q.Volume) for q in sector.Solids], nl_, nr_), flush=True)
    clear = min(th_lo - theta0, theta0 + pitch - th_hi)
    sols = [q for q in sector.Solids if abs(q.Volume) > 1.0]      # (a reversed solid reports a negative volume)
    print('%s sector: solids %d, vol %.0f mm3 (disc %.0f + blade %.0f), valid %s' % (
        row, len(sols), sum(abs(q.Volume) for q in sols), disc_cut.Volume, piece.Volume, sector.isValid()), flush=True)
    if len(sols) != 1: raise SystemExit('sector is not a single solid')
    os.makedirs(OUT, exist_ok=True)
    sols[0].exportStep(os.path.join(OUT, 'A1000_%s_sector.step' % row))
    print('%s cut faces on the planes: %d / %d' % (row, nl_, nr_), flush=True)
    json.dump(dict(row=row, Z=Z[row], theta0_deg=math.degrees(theta0), pitch_deg=math.degrees(pitch), r_in=R_IN_SECTOR,
                   clearance_deg=math.degrees(clear), vol_mm3=abs(sols[0].Volume)),
              open(os.path.join(OUT, 'A1000_%s_sector.json' % row), 'w'), indent=1)


if '--cad' in sys.argv:
    build_cad()
if '--sector' in sys.argv:
    for row_ in [a for a in sys.argv if a in ('R1', 'R2')] or ['R1', 'R2']:
        build_sector(row_)
