# GR180-CCHP subsystem E1 - gas-generator turbine stage for casting (IN713LC): NGV (21 vanes) + integral blisk (29 blades).
#
# Realises sim/gg_turbine_design.json (meanline, free vortex, axial exit) as real 3-D airfoils, builds the final machined and
# the as-cast (stock) solids in the ENG frame (x = tunnel front face, x downstream, mm), a 1/29 sector for CalculiX, checks
# throats / clearances / interference, and writes STEP + E1_interfaces.json + section PNG + 2-D drawings.
#
# Run (full build, ~10 min):
#   LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/engine/gg_turbine.py
# Aero part only (no FreeCAD, any python with numpy):  python cad/engine/gg_turbine.py --aero
# Env: GR180_ROOT (project root, default = two levels above this file), E1_FAST=1 (skip slow slicing / full-wheel checks)
#
# Rotation: CLOCKWISE seen from the intake = +theta about +x (theta = atan2(z, y)). NGV turns the flow to +theta,
# rotor exit relative flow is -theta. Angles in degrees from the axial (meridional) direction, + = +theta.
import os, sys, json, math
import numpy as np
_trapz = getattr(np, 'trapezoid', None) or np.trapz      # numpy 1.x / 2.x

def _root():
    if os.environ.get('GR180_ROOT'): return os.path.abspath(os.environ['GR180_ROOT'])
    try: return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    except NameError: return os.getcwd()
ROOT = _root()
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'E1')
FEA_DIR = os.path.join(ROOT, 'sim', 'engine', 'fea')
ASM = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
ML = json.load(open(os.path.join(ROOT, 'sim', 'gg_turbine_design.json')))
FAST = os.environ.get('E1_FAST', '0') == '1'

# ======================================================================================== stage data (meanline)
N_RPM = ML['N_rpm']; OM = N_RPM * 2 * math.pi / 60.0
CX2, CX3 = ML['Cx2'], ML['Cx3']                      # m/s, uniform (free vortex) NGV exit / rotor exit
K_SW = ML['dh'] / ML['U_m'] * ML['r_m']              # r*C_theta2 [m2/s] (free vortex)
Z_NGV, Z_ROT = ML['Z_ngv'], ML['Z_rot']               # 21 / 29
assert (Z_NGV, Z_ROT) == (21, 29)

# ======================================================================================== envelope (ENG mm)
X_NGV = 94.80                      # NGV front face (local u = x - X_NGV)
NGV_LE, NGV_TE = 98.80, 108.30     # vane LE / TE (axial chord 9.5, TE stacking line radial at x 108.3)
R_NGV_HUB = 22.25                  # inner ring OD (Ø44.5)
R_NGV_SHR = 35.35                  # aero shroud radius used for the vane design (final cold bore set from FEA, see NGV_BORE_R)
R_TIP = 35.15                      # rotor tip radius (ground after casting)
X_HUB = 104.30                     # wheel front face (on the rear 608 inner ring)
HUB_L = 14.51                      # hub length -> nut seat x 118.81
X_PF, X_PR = 110.10, 119.40        # rotor platform front / rear edge (front: 0.30 axial gap to the NGV inner ring end x 109.8)
X_FL0, X_FL1, R_H0, R_H1 = 110.30, 118.60, 22.10, 19.00   # hub flare r 22.1 -> 19.0 (C1 smooth-step) across the row
ROT_LE = (111.20, 110.95)          # rotor LE (hub, tip): hub set back so the R0.8 root fillet stays on the platform
ROT_TE = (118.70, 117.60)          # rotor TE (hub, tip): tip chord shortened for blade taper (root stress), 1.2 inside the shroud end x 118.8
FILLET_ROT, FILLET_NGV = 0.80, 1.00

def r_hub(x):
    """Rotor hub (platform) radius [mm] at axial x: C1 smooth step 22.1 -> 19.0 between X_FL0 and X_FL1."""
    t = np.clip((np.asarray(x, float) - X_FL0) / (X_FL1 - X_FL0), 0.0, 1.0)
    return R_H0 - (R_H0 - R_H1) * (3 * t**2 - 2 * t**3)
def dr_hub(x):
    x = np.asarray(x, float); t = (x - X_FL0) / (X_FL1 - X_FL0)
    return np.where((t > 0) & (t < 1), -(R_H0 - R_H1) * (6 * t - 6 * t**2) / (X_FL1 - X_FL0), 0.0)

# ======================================================================================== flow angles
def alpha2(r_mm):           # NGV exit absolute flow angle (deg, +theta)
    return math.degrees(math.atan2(K_SW / (r_mm * 1e-3), CX2))
def beta2(r_mm):            # rotor inlet relative angle at the inlet radius
    return math.degrees(math.atan2(K_SW / (r_mm * 1e-3) - OM * r_mm * 1e-3, CX2))
def beta3(r_mm):            # rotor exit relative angle at the exit radius of the same stream surface (C_theta3 = 0)
    return math.degrees(math.atan2(-OM * r_mm * 1e-3, CX3))
CP_G, GAM = 1148.0, 1.333; R_G = CP_G * (GAM - 1) / GAM
def mach_ngv_exit(r_mm):
    C2 = math.hypot(CX2, K_SW / (r_mm * 1e-3)); T2 = ML['T01'] - C2**2 / (2 * CP_G); return C2 / math.sqrt(GAM * R_G * T2)
def mach_rot_exit(r_mm):
    W3 = math.hypot(CX3, OM * r_mm * 1e-3); return W3 / math.sqrt(GAM * R_G * ML['T3'])
def carter_mach_factor(M):
    """Carter's rule is a low-speed correlation; deviation fades linearly to 0 between M = 0.5 and 1.0 (Ainley-Mathieson)."""
    return min(max((1.0 - M) / 0.5, 0.0), 1.0)

# ======================================================================================== stream surfaces
class Stream:
    """Meridional stream surface r(x). Cylinder (NGV) or rotor surface at span fraction s of the flared annulus
    (equal-area split between the hub contour r_hub(x) and the tip cylinder, = equal mass for uniform Cx)."""
    def __init__(self, r_const=None, s=None):
        self.rc, self.s = r_const, s
    def r(self, x):
        x = np.asarray(x, float)
        if self.rc is not None: return np.full_like(x, self.rc)
        rh = r_hub(x); return np.sqrt(rh**2 + self.s * (R_TIP**2 - rh**2))
    def dr(self, x):
        x = np.asarray(x, float)
        if self.rc is not None: return np.zeros_like(x)
        rh = r_hub(x); return rh * dr_hub(x) * (1 - self.s) / self.r(x)

class StreamOffset(Stream):
    """Surface at constant radial height h above the rotor hub contour (h > 0) or at radius r0 + h on a cylinder (NGV)."""
    def __init__(self, h, r_cyl=None):
        Stream.__init__(self); self.h, self.rcyl = h, r_cyl
    def r(self, x):
        x = np.asarray(x, float)
        return np.full_like(x, self.rcyl + self.h) if self.rcyl is not None else r_hub(x) + self.h
    def dr(self, x):
        x = np.asarray(x, float)
        return np.zeros_like(x) if self.rcyl is not None else dr_hub(x)

def fillet_offset(h, R):
    """Extra half-thickness of a concave circular fillet of radius R at height h above the wall."""
    return R - math.sqrt(max(R**2 - (R - h)**2, 0.0)) if h < R else 0.0
FILLET_H = (0.0, 0.12, 0.30, 0.55, 0.90)        # root-fillet section heights [x R/0.8]

def thickness_coeffs(rle, tmax, sig_m, tte_half, S):
    """Half-thickness h(sig) = S*(a0*sqrt(sig) + a1*sig + a2*sig^2 + a3*sig^3), sig = arc-length fraction along the camber.
    LE curvature radius rle, maximum tmax/2 at sig_m (zero slope there), h(1) = tte_half."""
    a0 = math.sqrt(2 * rle / S)
    Ym, Ye = tmax / 2 / S, tte_half / S
    A = np.array([[sig_m, sig_m**2, sig_m**3], [1, 2 * sig_m, 3 * sig_m**2], [1, 1, 1]])
    b = np.array([Ym - a0 * math.sqrt(sig_m), -a0 / (2 * math.sqrt(sig_m)), Ye - a0])
    return (a0,) + tuple(np.linalg.solve(A, b))

class Section:
    """One blade section on a stream surface, built in the conformal plane (m' = int dm/r, theta) so angles are exact.
    k1, k2: inlet / exit metal angles (deg); p: camber loading exponent (kappa = k1 + (k2-k1)*(1-(1-xi)^p));
    tau = tmax / true chord; rle = LE radius; tte = TE thickness (round TE); sig_m = max-thickness position."""
    NC = 401
    def __init__(self, st, x_le, x_te, k1, k2, p, tau, rle, tte, sig_m, theta_shift=0.0):
        self.st, self.x_le, self.x_te = st, x_le, x_te
        self.k1, self.k2, self.p, self.tau, self.rle, self.tte, self.sig_m = k1, k2, p, tau, rle, tte, sig_m
        self.dth = theta_shift
        self.build()
    def build(self):
        st = self
        # camber line end set back so the round TE cap ends at x_te
        xe = self.x_te - 0.5 * self.tte * math.cos(math.radians(self.k2))
        x = np.linspace(self.x_le, xe, self.NC)
        r = self.st.r(x); dr = self.st.dr(x)
        dm = np.sqrt(1 + dr**2)
        mp = np.concatenate([[0.0], np.cumsum(0.5 * (dm[1:] / r[1:] + dm[:-1] / r[:-1]) * np.diff(x))])   # conformal m'
        xi = mp / mp[-1]
        kap = np.radians(self.k1 + (self.k2 - self.k1) * (1 - (1 - xi)**self.p))
        th = np.concatenate([[0.0], np.cumsum(0.5 * (np.tan(kap[1:]) + np.tan(kap[:-1])) * np.diff(mp))])
        th += self.dth
        ds = r * np.sqrt(np.gradient(mp)**2 + np.gradient(th)**2)          # physical arc length along the camber
        s_ph = np.concatenate([[0.0], np.cumsum(0.5 * (ds[1:] + ds[:-1]))])
        S = s_ph[-1]
        sig = s_ph / S
        # true chord: LE -> TE distance on the developed surface (local radius)
        rm = 0.5 * (r[0] + r[-1]); dmm = _trapz(dm, x)
        self.chord = math.hypot(dmm, rm * (th[-1] - th[0])) + 0.5 * self.tte
        self.S = S
        a = thickness_coeffs(self.rle, self.tau * self.chord, self.sig_m, 0.5 * self.tte, S)
        h = S * (a[0] * np.sqrt(sig) + a[1] * sig + a[2] * sig**2 + a[3] * sig**3)
        self.h, self.sig, self.kap, self.mp, self.th, self.xc, self.r_c, self.xi = h, sig, kap, mp, th, x, r, xi
        self.hmin_ok = bool(np.all(h[1:] > 0))
        self.tmax_mm = 2 * h.max()
        # m'(x) inverse for mapping back
        self._mp_of_x = (x, mp)
    def mp_to_x(self, mpv):
        x, mp = self._mp_of_x
        # extend linearly beyond the ends (LE nose / TE cap stick out a little)
        x0 = np.interp(mpv, mp, x)
        lo = mpv < mp[0]; hi = mpv > mp[-1]
        g0 = (x[1] - x[0]) / (mp[1] - mp[0]); g1 = (x[-1] - x[-2]) / (mp[-1] - mp[-2])
        x0 = np.where(lo, x[0] + (mpv - mp[0]) * g0, x0); x0 = np.where(hi, x[-1] + (mpv - mp[-1]) * g1, x0)
        return x0
    def outline(self, n_side=70, n_te=11):
        """Closed outline (no duplicate end point) as (N,3) ENG xyz, starting at the TE, upper (+theta) side to the LE,
        lower side back. Returns pts, side tag (+1 upper, -1 lower, 0 TE cap) and camber fraction xi per point."""
        u = np.linspace(0, 1, n_side + 1)
        sg = 0.5 * (1 - np.cos(np.pi * u))                       # cluster at LE and TE
        sg = sg ** 1.15
        sigv = sg[::-1]                                          # TE -> LE
        def at(sv):
            mpv = np.interp(sv, self.sig, self.mp); thv = np.interp(sv, self.sig, self.th)
            kv = np.interp(sv, self.sig, self.kap); hv = np.interp(sv, self.sig, self.h)
            rv = self.st.r(self.mp_to_x(mpv))
            return mpv, thv, kv, hv, rv
        mpv, thv, kv, hv, rv = at(sigv)
        up = np.stack([mpv - hv / rv * np.sin(kv), thv + hv / rv * np.cos(kv)], 1)           # +theta side
        mpl, thl, kl, hl, rl = at(sg)
        lo = np.stack([mpl + hl / rl * np.sin(kl), thl - hl / rl * np.cos(kl)], 1)            # -theta side
        # TE cap: semicircle around the camber end (conformal plane, radius tte/2 / r)
        mpe, the, ke, re = self.mp[-1], self.th[-1], self.kap[-1], self.st.r(self.x_te)
        rr = 0.5 * self.tte / re
        ang = np.linspace(-math.pi / 2, math.pi / 2, n_te + 2)[1:-1]     # from lower to upper
        cap = np.stack([mpe + rr * (np.cos(ang) * math.cos(ke) - np.sin(ang) * math.sin(ke)),
                        the + rr * (np.cos(ang) * math.sin(ke) + np.sin(ang) * math.cos(ke))], 1)
        capm = cap[n_te // 2:]                                   # TE mid -> upper
        capl = cap[:n_te // 2]                                   # lower -> TE mid
        P = np.vstack([capm, up[:-1] if False else up, lo[1:], capl])
        xi_up = np.interp(sigv, self.sig, self.xi); xi_lo = np.interp(sg, self.sig, self.xi)
        side = np.concatenate([np.zeros(len(capm)), np.ones(len(up)), -np.ones(len(lo) - 1), np.zeros(len(capl))])
        xis = np.concatenate([np.ones(len(capm)), xi_up, xi_lo[1:], np.ones(len(capl))])
        xx = self.mp_to_x(P[:, 0]); rr_ = self.st.r(xx)
        pts = np.stack([xx, rr_ * np.cos(P[:, 1]), rr_ * np.sin(P[:, 1])], 1)
        return pts, side, xis
    def outline_offset(self, delta, n_side=70, n_te=11):
        """Outline offset outward by delta [mm] (normal offset in the conformal plane, delta/r)."""
        pts, side, xis = self.outline(n_side, n_te)
        if delta <= 0: return pts
        x = pts[:, 0]; th = np.arctan2(pts[:, 2], pts[:, 1]); r = np.hypot(pts[:, 1], pts[:, 2])
        mp = np.interp(x, self.xc, self.mp) + np.where(x < self.xc[0], (x - self.xc[0]) / r, 0) + np.where(x > self.xc[-1], (x - self.xc[-1]) / r, 0)
        P = np.stack([mp, th], 1)
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0); T /= np.linalg.norm(T, axis=1)[:, None]
        Nrm = np.stack([T[:, 1], -T[:, 0]], 1)
        A = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        if A < 0: Nrm = -Nrm                       # outward normal for a counter-clockwise outline
        Q = P + Nrm * (delta / r)[:, None]
        xq = self.mp_to_x(Q[:, 0]); rq = self.st.r(xq)
        return np.stack([xq, rq * np.cos(Q[:, 1]), rq * np.sin(Q[:, 1])], 1)
    def te_point(self):
        x = self.x_te - 0.5 * self.tte * math.cos(math.radians(self.k2)); r = float(self.st.r(x)); t = self.th[-1]
        return np.array([x, r * math.cos(t), r * math.sin(t)])
    def centroid(self):
        """Area centroid of the section (physical area weighting r^2 in the conformal plane): (x_c, theta_c, area mm2)."""
        pts, _, _ = self.outline(120, 15)
        xx = pts[:, 0]; th = np.arctan2(pts[:, 2], pts[:, 1])
        mpv = np.interp(xx, self.xc, self.mp)            # inside the camber range; ends are tiny
        rr = np.hypot(pts[:, 1], pts[:, 2])
        # polygon (mp, th) with weight r^2 (dA_phys = r^2 dm' dtheta)
        xs, ys = mpv, th
        cr = xs * np.roll(ys, -1) - np.roll(xs, -1) * ys
        A = 0.5 * cr.sum(); cx = ((xs + np.roll(xs, -1)) * cr).sum() / (6 * A); cy = ((ys + np.roll(ys, -1)) * cr).sum() / (6 * A)
        r2 = np.mean(rr**2)
        return float(np.interp(cx, self.mp, self.xc)), float(cy), abs(A) * r2

def rot_x(P, a):
    c, s = math.cos(a), math.sin(a)
    return np.stack([P[:, 0], c * P[:, 1] - s * P[:, 2], s * P[:, 1] + c * P[:, 2]], 1)

def throat(sec, Z, sign):
    """Throat o: min distance from this blade's TE (cap centre, minus TE radius) to the neighbouring blade.
    sign = +1: flow leaves to +theta (NGV) -> neighbour at +pitch; -1 (rotor) -> neighbour at -pitch.
    Returns o [mm], local pitch at the TE [mm], camber fraction xi of the contact point on the neighbour."""
    pts, side, xis = sec.outline(400, 21)
    nb = rot_x(pts, sign * 2 * math.pi / Z)
    te = sec.te_point()
    d = np.linalg.norm(nb - te, axis=1)
    i = int(np.argmin(d))
    pitch = 2 * math.pi * math.hypot(te[1], te[2]) / Z
    return d[i] - 0.5 * sec.tte, pitch, xis[i], nb[i]

# ======================================================================================== NGV design
NGV_SPANS = [R_NGV_HUB, 24.87, 27.49, 30.11, 32.73, R_NGV_SHR]          # 6 design radii (+ 2 extension sections)
NGV_EXT = (21.55, 36.05)                                                  # buried in the inner / outer ring (fillet base)
def ngv_params(r):
    f = (r - R_NGV_HUB) / (R_NGV_SHR - R_NGV_HUB)
    return dict(tmax=1.55 - 0.15 * f, rle=0.60, tte=0.50, sig_m=0.30, p=1.9)

CARTER_M = 0.19     # Carter's rule for accelerating (turbine) cascades: delta = m * theta_u * (s/c), theta_u = uncovered turning
# Exit metal angle rule: the camber TE angle kappa2 is iterated until the THROAT gauging angle acos(o/s) equals the
# free-vortex flow angle + Carter deviation. (With 0.45-0.5 mm cast TEs the camber TE angle is then smaller than the flow
# angle: cos(gauging) ~ cos(kappa2) - (t_TE + t_SS(throat))/s.)

def _solve_section(make, flow_abs, Z, sign, p, k1, kap_sign, M_exit=0.0):
    """make(k2) -> Section. Find k2 such that acos(o/s) = |flow| + delta_Carter. Returns section and bookkeeping."""
    dev = 1.0
    k2 = flow_abs * kap_sign
    for outer in range(12):
        target = math.cos(math.radians(flow_abs + dev))
        # secant on k2 for o/s = target
        ka, kb = k2, k2 - 3.0 * kap_sign
        def f(k):
            sec = make(k); o, s, xi, _ = throat(sec, Z, sign); return o / s - target, sec, o, s, xi
        fa, *_ = f(ka); fb, *_ = f(kb)
        for _ in range(30):
            if abs(fb - fa) < 1e-12: break
            kc = kb - fb * (kb - ka) / (fb - fa)
            ka, fa = kb, fb; kb = kc; fb, sec, o, s, xi_t = f(kb)
            if abs(fb) < 2e-4: break
        k2 = kb
        th_u = abs(k2 - (k1 + (k2 - k1) * (1 - (1 - xi_t)**p)))
        dev_c = CARTER_M * th_u * (s / sec.chord)
        dev_new = dev_c * carter_mach_factor(M_exit)
        conv = abs(dev_new - dev) < 0.01
        dev = dev_new
        if conv: break
    sec.dev, sec.o, sec.pitch, sec.xi_t, sec.theta_u, sec.dev_carter, sec.M_exit = dev, o, s, xi_t, th_u, dev_c, M_exit
    sec.gauging = math.degrees(math.acos(o / s))
    return sec

def design_ngv(verbose=False):
    secs = {}
    for r in sorted(NGV_SPANS + list(NGV_EXT)):
        rd = min(max(r, R_NGV_HUB), R_NGV_SHR)           # extension sections reuse the endwall design
        a2 = alpha2(rd); q = ngv_params(rd)
        def make(k2, r=r, q=q):
            c0 = Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, k2, q['p'], 0.12, q['rle'], q['tte'], q['sig_m'])
            tau = q['tmax'] / c0.chord
            sec = Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, k2, q['p'], tau, q['rle'], q['tte'], q['sig_m'])
            return Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, k2, q['p'], tau, q['rle'], q['tte'], q['sig_m'], -sec.th[-1])  # TE stacking
        if r in NGV_EXT:   # copy the endwall section geometry (same angles) at the extension radius
            ref = secs.get(R_NGV_HUB if r < R_NGV_HUB else None)
        sec = _solve_section(make, a2, Z_NGV, +1, q['p'], 0.0, +1, mach_ngv_exit(rd))
        sec.flow_out = a2
        secs[r] = sec
    # extension sections: same metal angles as the endwall sections (no extrapolated twist)
    for r, rw in ((NGV_EXT[0], R_NGV_HUB), (NGV_EXT[1], R_NGV_SHR)):
        w = secs[rw]; q = ngv_params(rw)
        sec = Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, w.k2, q['p'], w.tau, q['rle'], q['tte'], q['sig_m'])
        sec = Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, w.k2, q['p'], w.tau, q['rle'], q['tte'], q['sig_m'], -sec.th[-1])
        sec.flow_out, sec.dev, sec.o, sec.pitch, sec.xi_t, sec.theta_u, sec.gauging = w.flow_out, w.dev, w.o, w.pitch, w.xi_t, w.theta_u, w.gauging
        sec.dev_carter, sec.M_exit = w.dev_carter, w.M_exit
        secs[r] = sec
    return secs

# ======================================================================================== rotor design
# 7 design stream surfaces (+ extensions below the hub / above the tip), denser at the hub where the blade twists fastest. With
# only 5 (and the loft starting at s 0.25) the CAD surface strayed up to ~1 mm from the design between them (bumps on the blade);
# now <= 0.1 mm for s >= 0.19, 0.37 mm just above the root fillet. 12 spans fit even closer but break the 29-blade fuse.
ROT_SPANS = [0.0, 0.125, 0.25, 0.375, 0.50, 0.75, 1.0]
ROT_LOFT_MIN_S = 0.10                               # design sections used in the loft start above the root fillet (h 0.9 mm)
ROT_EXT = (-0.04, 1.05)
def rot_params(s):
    sc = min(max(s, 0.0), 1.0)
    # t/c 0.22 at the root -> 0.068 at the tip (strong outer taper keeps the root P/A ~290 MPa @115k), LE radius 0.36 -> 0.18,
    # cast TE 0.48 -> 0.45 mm, max thickness at 32-38 % of the camber, camber loading exponent 2.0 (hub) -> 1.6 (tip)
    return dict(tau=0.068 + 0.152 * (1 - sc)**2.2, rle=0.36 - 0.18 * sc, tte=0.48 - 0.03 * sc, sig_m=0.32 + 0.06 * sc, p=2.0 - 0.4 * sc)

def rot_le_te(s):
    return ROT_LE[0] + (ROT_LE[1] - ROT_LE[0]) * s, ROT_TE[0] + (ROT_TE[1] - ROT_TE[0]) * s

def stream_radii(s):
    st = Stream(s=s); le, te = rot_le_te(s)
    return float(st.r(le)), float(st.r(te))

def design_rotor(verbose=False):
    secs = {}
    for s in sorted(ROT_SPANS):
        st = Stream(s=s); le, te = rot_le_te(s)
        r_in, r_out = stream_radii(s)
        b2, b3 = beta2(r_in), beta3(r_out)
        q = rot_params(s)
        def make(k2, st=st, le=le, te=te, b2=b2, q=q):
            sec = Section(st, le, te, b2, k2, q['p'], q['tau'], q['rle'], q['tte'], q['sig_m'])
            xc, tc, A = sec.centroid()
            return Section(st, le, te, b2, k2, q['p'], q['tau'], q['rle'], q['tte'], q['sig_m'], -tc)   # centroid stacking (theta)
        sec = _solve_section(make, abs(b3), Z_ROT, -1, q['p'], b2, -1, mach_rot_exit(r_out))
        sec.flow_in, sec.flow_out, sec.r_in, sec.r_out, sec.span = b2, b3, r_in, r_out, s
        secs[s] = sec
    # extensions: linear extrapolation of the metal angles / thickness in span (smooth loft), buried in hub / trimmed at tip
    for s, (sa, sb) in ((ROT_EXT[0], (0.0, 0.25)), (ROT_EXT[1], (0.75, 1.0))):
        A, B = secs[sa], secs[sb]; w = (s - sa) / (sb - sa)
        lin = lambda a, b: a + w * (b - a)
        st = Stream(s=s); le, te = rot_le_te(s)
        args = (st, le, te, lin(A.k1, B.k1), lin(A.k2, B.k2), lin(A.p, B.p), lin(A.tau, B.tau), lin(A.rle, B.rle),
                max(lin(A.tte, B.tte), 0.40), lin(A.sig_m, B.sig_m))
        sec = Section(*args); xc, tc, _ = sec.centroid(); sec = Section(*args, -tc)
        sec.flow_in, sec.flow_out, sec.span = sec.k1, sec.k2, s
        sec.dev = sec.o = sec.pitch = sec.xi_t = sec.theta_u = sec.gauging = float('nan')
        secs[s] = sec
    return secs

# ======================================================================================== 1-D checks
def throat_area_ngv(secs):
    """Throat area from the design sections: Z * int o(r) dr between the endwalls (sections at the design radii)."""
    rs = sorted(r for r in secs if R_NGV_HUB - 1e-6 <= r <= R_NGV_SHR + 1e-6)
    o = [secs[r].o for r in rs]
    return Z_NGV * _trapz(o, rs)

def throat_area_rot(secs):
    """Rotor: o(s) integrated along the TE line (hub r ~19.0 -> tip 35.15) and, for the meanline comparison, over the
    inlet-annulus span definition used in gg_turbine_meanline.py (Z * o_mean * (R_TIP - 22.1))."""
    ss = sorted(s for s in secs if -1e-6 <= s <= 1 + 1e-6)
    pts = np.array([secs[s].te_point() for s in ss])
    rr = np.hypot(pts[:, 1], pts[:, 2]); xx = pts[:, 0]
    dl = np.hypot(np.diff(rr), np.diff(xx))
    o = np.array([secs[s].o for s in ss])
    A_te = Z_ROT * np.sum(0.5 * (o[1:] + o[:-1]) * dl)
    A_ml = Z_ROT * np.mean(o) * (R_TIP - R_H0)
    return A_te, A_ml

def required_throats():
    rr = np.linspace(R_NGV_HUB, R_NGV_SHR, 400) * 1e-3
    a = np.arctan2(K_SW / rr, CX2)
    A_n = _trapz(2 * math.pi * rr * np.cos(a), rr) * 1e6
    rr = np.linspace(R_H1, R_TIP, 400) * 1e-3
    b = np.arctan2(OM * rr, CX3)
    A_r = _trapz(2 * math.pi * rr * np.cos(b), rr) * 1e6
    return A_n, A_r

def am_exit_angle(o_s, M):
    """Ainley-Mathieson exit angle from o/s (deg): M<=0.5: -11.15 + 1.154 acos(o/s); M=1: acos(o/s); linear between."""
    a1 = math.degrees(math.acos(o_s)); a0 = -11.15 + 1.154 * a1
    w = min(max((M - 0.5) / 0.5, 0.0), 1.0)
    return a0 + w * (a1 - a0)

def passage_check(sec, Z, sign):
    """Blade-to-blade passage width along the passage: distance from this blade's surface facing the neighbour
    (side == sign) to the neighbour, for camber fractions 0.05..0.85. Returns (min width, xi at min)."""
    pts, side, xis = sec.outline(300, 15)
    nb = rot_x(pts, sign * 2 * math.pi / Z)
    widths = []
    for i in np.where(side == sign)[0]:
        if xis[i] > 0.85 or xis[i] < 0.05: continue
        widths.append((np.linalg.norm(nb - pts[i], axis=1).min(), xis[i]))
    return min(widths)

RHO_IN713 = 8.00e-9   # t/mm3

def blade_pull_estimate(rot, N=N_RPM):
    """1-D blade root stress: sigma(s=0) = rho*om^2 * int A(r) r dr / A_root, A(r) from the design sections at their
    centroid radii (linear between, tip section extended to R_TIP)."""
    ss = sorted(s for s in rot if -1e-6 <= s <= 1 + 1e-6)
    A = []; R = []
    for s in ss:
        sec = rot[s]; pts, _, _ = sec.outline(120, 15); A.append(sec.centroid()[2]); R.append(np.mean(np.hypot(pts[:, 1], pts[:, 2])))
    R.append(R_TIP); A.append(A[-1])
    rr = np.linspace(R[0], R_TIP, 300); aa = np.interp(rr, R, A)
    om = N * 2 * math.pi / 60
    F = RHO_IN713 * om**2 * _trapz(aa * rr, rr)          # N (t*mm/s2)
    return F / A[0], F, A[0], A[-2] / A[0], R[0]

def aero_report(ngv, rot, verbose=True):
    A_n_req, A_r_req = required_throats()
    A_n = throat_area_ngv(ngv)
    A_r_te, A_r_ml = throat_area_rot(rot)
    rep = dict(NGV=[], ROT=[], A_ngv=A_n, A_ngv_cosrule=A_n_req, A_ngv_meanline=ML['throat_ngv_mm2'],
               A_rot_te=A_r_te, A_rot_inlet_span=A_r_ml, A_rot_cosrule=A_r_req, A_rot_meanline=ML['throat_rot_mm2'])
    for r in sorted(ngv):
        s = ngv[r]
        if not (R_NGV_HUB - 1e-6 <= r <= R_NGV_SHR + 1e-6): continue
        M2 = s.M_exit
        rep['NGV'].append(dict(r=r, M2=s.M_exit, dev_carter=s.dev_carter, alpha2_flow=s.flow_out, gauging=s.gauging, kappa2=s.k2, dev=s.dev, theta_u=s.theta_u, chord=s.chord,
                               tmax=s.tmax_mm, tmax_c=s.tmax_mm / s.chord, o=s.o, pitch=s.pitch, o_s=s.o / s.pitch,
                               cos_a2=math.cos(math.radians(s.flow_out)), passage_min=passage_check(s, Z_NGV, +1)[0], alpha2_AM=am_exit_angle(s.o / s.pitch, M2),
                               zweifel=2 * s.pitch / (NGV_TE - NGV_LE) * math.cos(math.radians(s.flow_out))**2 * abs(math.tan(math.radians(s.flow_out)))))
    for sp in sorted(rot):
        s = rot[sp]
        if not (-1e-6 <= sp <= 1 + 1e-6): continue
        Mw3 = s.M_exit
        xc, tc, A = s.centroid()
        le, te = rot_le_te(sp)
        b2, b3 = math.radians(s.flow_in), math.radians(s.flow_out)
        pitch_m = 2 * math.pi * 0.5 * (s.r_in + s.r_out) / Z_ROT
        rep['ROT'].append(dict(s=sp, Mw3=s.M_exit, dev_carter=s.dev_carter, gauging=s.gauging, r_in=s.r_in, r_out=s.r_out, beta2=s.flow_in, beta3=s.flow_out, kappa1=s.k1, kappa2=s.k2,
                               dev=s.dev, theta_u=s.theta_u, bx=te - le, chord=s.chord, tmax=s.tmax_mm, tmax_c=s.tmax_mm / s.chord,
                               o=s.o, pitch_te=s.pitch, o_s=s.o / s.pitch, cos_b3=math.cos(b3),
                               beta3_AM=-am_exit_angle(min(s.o / s.pitch, 0.999), Mw3), x_centroid=xc, area=A,
                               zweifel=2 * pitch_m / (te - le) * math.cos(b3)**2 * abs(math.tan(b2) - math.tan(b3)),
                               passage_min=passage_check(s, Z_ROT, -1)[0], passage_xi=passage_check(s, Z_ROT, -1)[1]))
    sb, F, Ar, tap, r0 = blade_pull_estimate(rot)
    rep.update(sigma_root_1D=sb, blade_pull_N=F, A_root=Ar, area_taper=tap)
    if verbose:
        print('Rotor blade 1-D: root area %.2f mm2 (r_c %.2f), tip/root area %.2f, pull %.0f N/blade, sigma_root P/A %.0f MPa @115k'
              % (Ar, r0, tap, F, sb))
        print('NGV  %d vanes  LE x%.2f TE x%.2f (TE stacked)' % (Z_NGV, NGV_LE, NGV_TE))
        print('   r     a2flow gaug  kap2   dev  th_u  chord  tmax t/c    o     s    o/s  cos(a2) a2(AM)  Zw   pmin')
        for q in rep['NGV']:
            print('  %5.2f %6.1f %5.1f %6.1f %5.2f %5.1f %6.2f %5.2f %4.2f %5.2f %5.2f %5.3f %6.3f %6.1f %5.2f %5.2f' % (
                q['r'], q['alpha2_flow'], q['gauging'], q['kappa2'], q['dev'], q['theta_u'], q['chord'], q['tmax'], q['tmax_c'], q['o'], q['pitch'],
                q['o_s'], q['cos_a2'], q['alpha2_AM'], q['zweifel'], q['passage_min']))
        print('   (M2 / Carter low-speed dev: ' + ', '.join('%.2f/%.2f' % (q['M2'], q['dev_carter']) for q in rep['NGV']) + ')')
        print('ROTOR %d blades' % Z_ROT)
        print('   s   r_in  r_out  b2    b3   gaug kap1  kap2   dev  th_u  bx   chord tmax  t/c   o    s_te  o/s  cos(b3) b3(AM) xcen  area  Zw   pmin')
        for q in rep['ROT']:
            print('  %4.2f %5.2f %5.2f %5.1f %6.1f %5.1f %5.1f %6.1f %4.2f %5.1f %4.2f %5.2f %4.2f %4.2f %5.2f %5.2f %5.3f %5.3f %6.1f %6.2f %5.2f %4.2f %4.2f' % (
                q['s'], q['r_in'], q['r_out'], q['beta2'], q['beta3'], q['gauging'], q['kappa1'], q['kappa2'], q['dev'], q['theta_u'], q['bx'],
                q['chord'], q['tmax'], q['tmax_c'], q['o'], q['pitch_te'], q['o_s'], q['cos_b3'], q['beta3_AM'], q['x_centroid'], q['area'],
                q['zweifel'], q['passage_min']))
        print('   (Mw3 / Carter low-speed dev / xi of passage min: ' + ', '.join('%.2f/%.2f/%.2f' % (q['Mw3'], q['dev_carter'], q['passage_xi']) for q in rep['ROT']) + ')')
        print('Throat NGV  : sections %.0f mm2 | cos-rule (free vortex) %.0f | meanline %.0f' % (A_n, A_n_req, ML['throat_ngv_mm2']))
        print('Throat ROTOR: along TE (hub 19.0..tip) %.0f mm2 | cos-rule flared exit %.0f | inlet-span definition %.0f | meanline %.0f'
              % (A_r_te, A_r_req, A_r_ml, ML['throat_rot_mm2']))
    return rep

# ======================================================================================== disc (meridional profile)
# Envelope (drawing): hub 104.30..118.81 (14.51), front sleeve Ø12.8 x 4.3 on the 608 inner ring, Ø8 bore (14.0 shaft pilot),
# rear boss Ø13 nut seat. Clearances: tunnel spigot end x 107.3 (r 11-13) -> disc front face >= 108.3 there; NGV inner ring end
# x 109.8 (r 21.25-22.25) -> platform front face x 110.1; old exhaust cone x 120.31 (r 7-26) -> platform rear x 119.4.
# Web parameters were chosen with the axisymmetric study in sim/engine/e1_turbine_fea.py (--opt); values below = selected design.
DISC = dict(xf_w=111.60, xr_w=115.60, r_web=15.0, x_boss=118.50, r_lip_f=19.70, r_lip_r=17.30, R_web=2.5, r_hf=6.4, r_hr=6.5)
# Bore-less disc (sim/engine/e1_disc_thermal_study.py): solid hub, web 6 mm, R4 web fillets. Hot 115k peak 615 MPa (margin 1.13 to
# minimum yield), burst 201k, creep (reference stress) >= 1e6 h; the Ø8 bore reached 957-1172 MPa hot. The wheel is friction
# welded to the shaft at the sleeve front face (x 104.3); no rear nut / thread (fc_shaft_welded).
DISC_BORELESS = dict(r_bore=0.0, xf_w=110.6, xr_w=116.6, R_web=4.0)

def _fillet_corner(P0, V, P1, R, kind):
    """Corner at V between segments P0-V and V-P1. kind 'f' fillet radius R, 'c' chamfer length R. Returns (t0, mid, t1)."""
    P0, V, P1 = map(np.asarray, (P0, V, P1))
    d0 = (P0 - V) / np.linalg.norm(P0 - V); d1 = (P1 - V) / np.linalg.norm(P1 - V)
    if kind == 'c':
        return V + R * d0, None, V + R * d1
    phi = math.acos(np.clip(np.dot(d0, d1), -1, 1))          # interior angle between the two edges
    L = R / math.tan(phi / 2)
    t0, t1 = V + L * d0, V + L * d1
    bis = (d0 + d1) / np.linalg.norm(d0 + d1)
    C = V + bis * (R / math.sin(phi / 2))
    mid = C - bis * R
    return t0, mid, t1

def flare_bezier():
    """Hub flare as an exact cubic Bezier (smooth step r_hub(x)): control points (x, r)."""
    L = X_FL1 - X_FL0
    return [(X_FL0, R_H0), (X_FL0 + L / 3, R_H0), (X_FL0 + 2 * L / 3, R_H1), (X_FL1, R_H1)]

def disc_profile(kind='final', P=None):
    """Meridional outline (x, r) of the wheel body (without blades) as primitives, counter-clockwise.
    kind: 'final' (machined) or 'cast' (with machining stock). Returns list of ('L', p0, p1) | ('A', p0, pm, p1) | ('B', ctrl)."""
    P = dict(DISC, **(P or {}))
    ck = kind == 'cast'
    rb = 3.00 if ck else 4.00                   # bore: cast Ø6 pilot hole, machined Ø8
    if 'r_bore' in P: rb = max(P['r_bore'] - (1.0 if ck else 0.0), 0.0)   # r_bore 0: bore-less disc (wheel welded to a stub shaft)
    kb = 'c' if rb > 0 else None                # no chamfer on the axis
    xf = X_HUB - (0.50 if ck else 0.0)          # sleeve front face
    rs = 6.40 + (0.50 if ck else 0.0)           # sleeve OD Ø12.8 (pilot / bearing-ring shoulder)
    xb = X_HUB + HUB_L + (0.50 if ck else 0.0)  # nut seat face
    rbo = 6.50 + (0.50 if ck else 0.0)          # boss OD Ø13
    xpf = X_PF - (0.30 if ck else 0.0)          # platform front face (axial gap to the NGV ring) machined
    pts = [  # vertex, corner kind, size
        ((xf, rb), kb, 0.30), ((xb, rb), kb, 0.30), ((xb, rbo), 'c', 0.20), ((P['x_boss'], rbo), 'f', 0.60),
        ] + ([((P['x_boss'], P['r_hr']), 'f', 1.0)] if P['r_hr'] > rbo + 0.8 else []) + [
        ((P['xr_w'], P['r_web']), 'f', P['R_web']), ((X_PR, P['r_lip_r']), 'f', 0.40), ((X_PR, R_H1), 'f', 0.30),
        ('FLARE',),
        ((xpf, R_H0), 'f', 0.15), ((xpf, P['r_lip_f']), 'f', 0.40), ((P['xf_w'], P['r_web']), 'f', P['R_web'])
        ] + ([((108.60, P['r_hf']), 'f', 1.0)] if P['r_hf'] > rs + 0.8 else []) + [
        ((108.60, rs), 'f', 0.80), ((xf, rs), 'c', 0.30)]
    # explicit vertex list with the flare as two straight run-outs + bezier
    V = []
    for q in pts:
        if q[0] == 'FLARE':
            V.append(((X_FL1, R_H1), None, 0)); V.append(('BEZ',)); V.append(((X_FL0, R_H0), None, 0))
        else:
            V.append(q)
    # build primitives
    verts = [v for v in V if v[0] != 'BEZ']
    n = len(verts)
    corner = {}
    for i, (pt, kd, sz) in enumerate(verts):
        if kd is None: continue
        prv = verts[i - 1][0]; nxt = verts[(i + 1) % n][0]
        corner[i] = _fillet_corner(prv, pt, nxt, sz, kd)
    prims = []
    def start_of(i): return corner[i][2] if i in corner else np.array(verts[i][0], float)
    def end_of(i): return corner[i][0] if i in corner else np.array(verts[i][0], float)
    ib = [k for k, v in enumerate(V) if v[0] == 'BEZ'][0]          # bezier sits between verts index ib-1 and ib (in verts numbering)
    for i in range(n):
        j = (i + 1) % n
        a, b = start_of(i), end_of(j)
        if i == ib - 1:            # segment from (X_FL1,R_H1) to (X_FL0,R_H0) is the flare (reverse direction)
            prims.append(('B', flare_bezier()[::-1]))
        elif np.linalg.norm(b - a) > 1e-6:
            prims.append(('L', tuple(a), tuple(b)))
        if j in corner:
            t0, m, t1 = corner[j]
            if m is None: prims.append(('L', tuple(t0), tuple(t1)))
            else: prims.append(('A', tuple(t0), tuple(m), tuple(t1)))
    return prims

def sample_profile(prims, ds=0.15):
    """Polyline (x, r) sampling of the primitives (closed, no duplicate)."""
    out = []
    for pr in prims:
        if pr[0] == 'L':
            a, b = np.array(pr[1]), np.array(pr[2]); n = max(1, int(np.linalg.norm(b - a) / ds))
            out += [tuple(a + (b - a) * k / n) for k in range(n)]
        elif pr[0] == 'A':
            a, m, b = map(np.array, pr[1:])
            # circle through 3 points
            ax, ay = a; bx, by = m; cx, cy = b
            d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
            ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
            uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
            R = math.hypot(ax - ux, ay - uy)
            t0 = math.atan2(ay - uy, ax - ux); tm = math.atan2(by - uy, bx - ux); t1 = math.atan2(cy - uy, cx - ux)
            # choose direction through the mid point
            def unwrap(t, ref): return ref + ((t - ref + math.pi) % (2 * math.pi) - math.pi)
            tm = unwrap(tm, t0); t1 = unwrap(t1, tm)
            n = max(2, int(abs(t1 - t0) * R / ds) + 1)
            out += [(ux + R * math.cos(t0 + (t1 - t0) * k / n), uy + R * math.sin(t0 + (t1 - t0) * k / n)) for k in range(n)]
        else:
            c = np.array(pr[1]); n = max(8, int(9.0 / ds))
            for k in range(n):
                t = k / n
                B = (1 - t)**3 * c[0] + 3 * (1 - t)**2 * t * c[1] + 3 * (1 - t) * t**2 * c[2] + t**3 * c[3]
                out.append(tuple(B))
    return out

def polygon_area_centroid(poly):
    P = np.array(poly); x, y = P[:, 0], P[:, 1]; x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y; A = 0.5 * cr.sum()
    return A, ((x + x1) * cr).sum() / (6 * A), ((y + y1) * cr).sum() / (6 * A)

# ======================================================================================== FreeCAD geometry
NGV_BORE_R_DEFAULT = R_NGV_SHR      # cold NGV shroud bore radius; replaced by the FEA recommendation (E1_fea_results.json)
TIP_STOCK, CAST_SHROUD_STOCK = 0.30, 0.30

def ngv_bore_r():
    f = os.path.join(OUT, 'E1_fea_results.json')
    if os.path.exists(f):
        try: return float(json.load(open(f))['clearance']['ngv_bore_r_cold_recommended'])
        except Exception: pass
    return NGV_BORE_R_DEFAULT

def project_to_plane(pts, n_of_x, theta_m=0.0):
    """Move points along the local radial direction e_r(theta_m) onto n = n_of_x(x) (t and x kept) -> planar section."""
    c, s_ = math.cos(theta_m), math.sin(theta_m)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    t = -y * s_ + z * c
    n2 = n_of_x(x)
    return np.stack([x, n2 * c - t * s_, n2 * s_ + t * c], 1)

def hub_cap_plane():
    """Plane below the hub under the rotor blade (n linear in x): 0.6 below the hub at the hub LE, 0.8 below at the hub TE."""
    xa, xb = ROT_LE[0], ROT_TE[0]
    na, nb = float(r_hub(xa)) - 0.6, float(r_hub(xb)) - 0.8
    return lambda x: na + (nb - na) * (np.asarray(x) - xa) / (xb - xa)

def camber_theta(sec, x):
    """Camber-line theta of a section at axial x (held constant outside LE..TE)."""
    return np.interp(x, sec.xc, sec.th)

def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector

def resample_closed(P, n=240):
    """Closed outline (no duplicate end point) resampled at equal arc length, seam point kept. The NGV fillet offsets spread the
    TE-cap points and bunch the concave side; interpolating them as they are puts small loops into the B-spline."""
    Q = np.vstack([P, P[:1]]); d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n + 1)[:-1]
    return np.stack([np.interp(t, d, Q[:, k]) for k in range(3)], 1)

def bs_wire(pts):
    """Closed, non-periodic B-spline interpolation (seam at the TE mid-point; periodic curves break ThruSections)."""
    App, Part, V = _fc()
    P = [V(*map(float, p)) for p in pts]
    c = Part.BSplineCurve(); c.interpolate(P + [P[0]], PeriodicFlag=False)
    return Part.Wire([c.toShape()])

def rev_prims(prims):
    App, Part, V = _fc()
    edges = []
    for pr in prims:
        if pr[0] == 'L': edges.append(Part.LineSegment(V(pr[1][0], pr[1][1], 0), V(pr[2][0], pr[2][1], 0)).toShape())
        elif pr[0] == 'A': edges.append(Part.Arc(V(pr[1][0], pr[1][1], 0), V(pr[2][0], pr[2][1], 0), V(pr[3][0], pr[3][1], 0)).toShape())
        else:
            b = Part.BezierCurve(); b.setPoles([V(p[0], p[1], 0) for p in pr[1]]); edges.append(b.toShape())
    w = Part.Wire(Part.__sortEdges__(edges))
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)

def cyl(r, x0, x1):
    App, Part, V = _fc(); return Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
def ring(ri, ro, x0, x1):
    return cyl(ro, x0, x1).cut(cyl(ri, x0, x1))
def rot_shape(sh, deg):
    App, Part, V = _fc(); q = sh.copy(); q.rotate(V(0, 0, 0), V(1, 0, 0), deg); return q

def fc_blade(rot):
    """Single rotor blade loft (centroids stacked on +y, theta = 0) with the integral R0.8 root fillet, trimmed at R_TIP
    (final) and R_TIP + TIP_STOCK (cast). Returns blade_raw, blade_f, blade_c."""
    App, Part, V = _fc()
    ss = sorted(rot); hub = rot[0.0]
    root = []
    for hk in FILLET_H:
        h = hk * FILLET_ROT / 0.8
        sec = Section(StreamOffset(h), hub.x_le, hub.x_te, hub.k1, hub.k2, hub.p, hub.tau, hub.rle, hub.tte, hub.sig_m, hub.dth)
        root.append(sec.outline_offset(fillet_offset(h, FILLET_ROT)))
    capH = project_to_plane(root[0], hub_cap_plane())
    capT = project_to_plane(rot[1.0].outline()[0], lambda x: np.full_like(np.asarray(x, float), R_TIP + 1.25))
    wires = [bs_wire(capH)] + [bs_wire(p_) for p_ in root] + [bs_wire(rot[s_].outline()[0]) for s_ in ss if s_ >= ROT_LOFT_MIN_S] + [bs_wire(capT)]
    blade_raw = Part.makeLoft(wires, True, False)
    if blade_raw.Volume < 0: blade_raw.reverse()
    # axial trim to the platform: the root fillet foot otherwise overhangs the platform edges (TE ~0.4-0.65 mm into the rear
    # cavity, LE sliver into the 0.30 mm gap to the NGV ring); the fillet now runs out at the platform edges. Trim planes 0.02 mm
    # inside the edges: planes coincident with the disc faces break the 29-blade fuse
    e = 0.02
    return (blade_raw, blade_raw.common(cyl(R_TIP, X_PF + e, X_PR - e)), blade_raw.common(cyl(R_TIP + TIP_STOCK, X_PF - 0.30 + e, X_PR - e)),
            len(wires))

def fc_disc(kind='final', P=None):
    """Revolved wheel body; the revolve seam is put mid-passage (rotated by half a pitch)."""
    App, Part, V = _fc()
    d_ = rev_prims(disc_profile(kind, P)); d_.rotate(V(0, 0, 0), V(1, 0, 0), 180.0 / Z_ROT); return d_

def fc_shaft_welded():
    """GR180 shaft (build_gr180.py profile, silver steel -> 42CrMo4 Q+T for welding) cut at the wheel's front face and inertia /
    friction welded to the bore-less wheel there: rear 608 journal Ø8 x 97.3..104.3, weld face Ø8 at x 104.3 (flash removed,
    0.5 mm relief on the wheel face inside the 608 inner-ring contact). ENG frame."""
    App, Part, V = _fc()
    SH_OFF = 97.30 - 145.0                       # shaft local 145 (rear shoulder) on the rear 608 front face (build_gr180.py)
    x_w = X_HUB - SH_OFF                         # weld face in shaft local x (152.0)
    re_, rm = 11.0 / 2, 15.5 / 2
    pts = [(0, 0), (0, 3), (15, 3), (15, 3.5), (49, 3.5), (49, 4), (58, 4), (58, re_), (76, rm), (127, rm), (145, re_), (145, 4),
           (x_w, 4), (x_w, 0)]
    w = Part.makePolygon([V(SH_OFF + a, r, 0) for a, r in pts] + [V(SH_OFF + pts[0][0], pts[0][1], 0)])
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)

def fc_full_wheel(disc, piece, Z=Z_ROT):
    App, Part, V = _fc()
    w = disc                 # one blade at a time: a single 29-shape fuse of the 12-span blades needs > 14 GB
    for k in range(Z):
        w = w.fuse(rot_shape(piece, 360.0 * k / Z)); __import__('gc').collect()
    try: w = w.removeSplitter()
    except Exception: pass
    return w

def sector_theta_table(rot):
    """Mid-passage boundary theta_left(x, r) of the 1/29 sector (left face = camber theta - half pitch), smoothed in x."""
    sec_list = [rot[s_] for s_ in sorted(rot) if 0 <= s_ <= 1]; s_vals = [s_ for s_ in sorted(rot) if 0 <= s_ <= 1]
    half = math.pi / Z_ROT
    xs = np.concatenate([[102.5, 106.0, 109.0, 110.3], np.linspace(110.8, 119.0, 42), [119.5, 120.5, 122.0]])
    rr_st = np.array([1.5, 8.0, 14.0, 17.5, 19.0, 20.5, 22.0, 24.0, 26.5, 29.0, 31.5, 34.0, 36.0, 38.0, 41.0])
    def theta_mid(x, r):
        rh = float(r_hub(np.clip(x, X_PF, X_PR)))
        sp = np.clip((r**2 - rh**2) / (R_TIP**2 - rh**2), 0.0, 1.0)
        return float(np.interp(sp, s_vals, [float(camber_theta(sc, x)) for sc in sec_list]))
    TH = np.array([[theta_mid(x, r) for r in rr_st] for x in xs])
    TH = np.vstack([TH[:1], (TH[:-2] + 2 * TH[1:-1] + TH[2:]) / 4, TH[-1:]])
    return xs, rr_st, TH - half, half

def fc_sector_tool(rot, ruled=True):
    """Periodic wedge tool (r 1.5..41, x 102.5..122) whose side faces follow the mid-passage: left face theta_L(x, r),
    right face = left rotated by one pitch (exactly periodic). Loft of planar x-sections (ruled -> no wiggles)."""
    App, Part, V = _fc()
    xs, rr_st, THL, half = sector_theta_table(rot)
    sec_wires = []
    for i, x in enumerate(xs):
        thL = THL[i]; thR = thL + 2 * half
        pl = [V(float(x), float(r * math.cos(t)), float(r * math.sin(t))) for r, t in zip(rr_st, thL)]
        prr = [V(float(x), float(r * math.cos(t)), float(r * math.sin(t))) for r, t in zip(rr_st[::-1], thR[::-1])]
        cL = Part.BSplineCurve(); cL.interpolate(pl); cR = Part.BSplineCurve(); cR.interpolate(prr)
        ro, ri = rr_st[-1], rr_st[0]
        a_out = Part.Arc(pl[-1], V(float(x), ro * math.cos(thL[-1] + half), ro * math.sin(thL[-1] + half)), prr[0])
        a_in = Part.Arc(prr[-1], V(float(x), ri * math.cos(thL[0] + half), ri * math.sin(thL[0] + half)), pl[0])
        sec_wires.append(Part.Wire([cL.toShape(), a_out.toShape(), cR.toShape(), a_in.toShape()]))
    tool = Part.makeLoft(sec_wires, True, ruled)
    if tool.Volume < 0: tool.reverse()
    return tool, (xs, rr_st, THL, half)

def fc_sector(w1f, rot, log=print):
    """1/29 cyclic sector of the single-blade wheel for CalculiX (periodic side faces mid-passage)."""
    App, Part, V = _fc()
    best = None
    for ruled in (True, False):
        tool, tab = fc_sector_tool(rot, ruled)
        wedge_vol = tab[3] * (tab[1][-1]**2 - tab[1][0]**2) * (tab[0][-1] - tab[0][0])
        ok_tool = tool.isValid() and abs(tool.Volume / wedge_vol - 1) < 0.05
        sec = w1f.common(tool)
        sols = [s for s in sec.Solids if s.Volume > 1.0]
        vol = sum(s.Volume for s in sols)
        log('sector tool ruled=%s valid %s vol %.0f (wedge %.0f) -> sector solids %d vol %.1f (x%d = %.0f vs single-blade wheel %.0f)'
            % (ruled, ok_tool, tool.Volume, wedge_vol, len(sols), vol, Z_ROT, Z_ROT * vol, w1f.Volume))
        if len(sols) == 1 and ok_tool and sols[0].isValid():
            best = (sols[0], tab); break
    if best is None: raise RuntimeError('FEA sector boolean failed')
    sec, (xs, rr_st, THL, half) = best
    json.dump(dict(xs=xs.tolist(), r=rr_st.tolist(), theta_left=THL.tolist(), Z=Z_ROT, note='left boundary theta(x,r); right = left + 2pi/Z'),
              open(os.path.join(FEA_DIR, 'sector_boundary.json'), 'w'), indent=1)
    return sec

def ngv_body(kind, RB):
    """NGV rings + web (revolved), local u = x - X_NGV. kind 'final' / 'cast'. Returns (body, bore radius)."""
    App, Part, V = _fc()
    ck = kind == 'cast'
    def rvp(pts):
        # counter-clockwise in (u, r): a clockwise profile revolves into an inside-out solid (booleans then drop the ring)
        if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) < 0: pts = pts[::-1]
        return Part.Face(Part.makePolygon([V(X_NGV + u, r, 0) for u, r in pts] + [V(X_NGV + pts[0][0], pts[0][1], 0)])).revolve(V(0, 0, 0), V(1, 0, 0), 360)
    rb = RB - (CAST_SHROUD_STOCK if ck else 0.0)
    u_web0 = 8.5 - (0.5 if ck else 0.0); r_web_b = 13.0 - (0.5 if ck else 0.0); u_in1 = 15.0 + (0.3 if ck else 0.0)
    u_f = 0.0 - (0.3 if ck else 0.0)                                   # front land face (machined datum)
    r_rib = 37.95 + (0.3 if ck else 0.0); u_r0, u_r1 = 14.5 - (0.3 if ck else 0.0), 16.0 + (0.3 if ck else 0.0)   # rib faces / OD machined
    chl = (36.05 - rb) / math.tan(math.radians(26))
    outer = rvp([(chl, rb), (u_f, 36.05 - (chl - u_f) * math.tan(math.radians(26)) if False else 36.05), (u_f, 36.35), (u_r0, 36.35), (u_r0, r_rib), (u_r1, r_rib), (u_r1, 36.35), (24.0, 36.35), (24.0, rb)])
    inner = rvp([(0, 21.25), (0, 22.25), (u_in1, 22.25), (u_in1, 21.25)])
    web = rvp([(u_web0, r_web_b), (u_web0, 21.3), (10.0, 21.3), (10.0, r_web_b)])
    return outer.fuse([inner, web]), rb

def fc_vane(ngv, rb):
    """Single NGV vane loft (TE stacked at theta 0) with integral R1.0 fillets to both rings, buried in the rings."""
    App, Part, V = _fc()
    hubs, shr = ngv[R_NGV_HUB], ngv[R_NGV_SHR]
    def mk(w, r):
        # TE stacking at this radius (as design_ngv): reusing w.dth of the end section rotates the fillet sections off the
        # vane (~1 deg at the hub) and twists the loft into an invalid solid
        s0 = Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, w.k2, w.p, w.tau, w.rle, w.tte, w.sig_m)
        return Section(Stream(r_const=r), NGV_LE, NGV_TE, 0.0, w.k2, w.p, w.tau, w.rle, w.tte, w.sig_m, -s0.th[-1])
    # fillet foot sections (h = 0) sunk 0.05 mm into the rings: a section edge lying exactly on the ring cylinder makes the
    # vane/ring boolean fail (invalid NGV solid); the sunk part is fused away, the visible fillet is unchanged
    sink = lambda hk: -0.05 if hk == 0 else 0.0
    inner = [resample_closed(mk(hubs, R_NGV_HUB + hk * FILLET_NGV / 0.8 + sink(hk)).outline_offset(fillet_offset(hk * FILLET_NGV / 0.8, FILLET_NGV)))
             for hk in FILLET_H]
    outer = [resample_closed(mk(shr, rb - hk * FILLET_NGV / 0.8 - sink(hk)).outline_offset(fillet_offset(hk * FILLET_NGV / 0.8, FILLET_NGV)))
             for hk in FILLET_H][::-1]
    r_in_max, r_out_min = R_NGV_HUB + FILLET_H[-1] * FILLET_NGV / 0.8 + 1.0, rb - FILLET_H[-1] * FILLET_NGV / 0.8 - 1.0
    mids = [ngv[r].outline()[0] for r in sorted(ngv) if r_in_max < r < r_out_min]
    # end caps on true planes (normal at the section's mid angle, radial projection), buried in the rings: caps on r = const
    # are not planar, give invalid faces and an unorientable vane. Hub: vane spans ~23 deg -> r <= 21.40 / cos(12) = 21.9 < 22.25
    def flat(P, c):
        th = np.arctan2(P[:, 2], P[:, 1]); tm = 0.5 * (th.min() + th.max()); d = th - tm
        return np.stack([P[:, 0], c * np.cos(tm) - c * np.tan(d) * np.sin(tm), c * np.sin(tm) + c * np.tan(d) * np.cos(tm)], 1)
    capI = flat(inner[0], 21.40)
    capO = flat(outer[-1], rb + 0.15)
    vw = [bs_wire(capI)] + [bs_wire(p_) for p_ in inner + mids + outer] + [bs_wire(capO)]
    v_ = Part.makeLoft(vw, True, False)
    if v_.Volume < 0:        # loft in the other order instead of reverse(): a reversed shell breaks the ring booleans
        v_ = Part.makeLoft(vw[::-1], True, False)
    if not v_.isValid():     # end caps (buried in the rings) have self-intersecting outlines; repair keeps the volume
        v_.fix(1e-4, 1e-5, 1e-3)
    return v_, len(vw)

def fc_ngv(ngv, kind, RB):
    """Complete NGV ring (21 vanes). Returns (ngv_shape, n_sections, vane_piece)."""
    App, Part, V = _fc()
    body, rb = ngv_body(kind, RB)
    vane, nsec = fc_vane(ngv, rb)
    piece = vane.common(ring(21.3, rb + 0.65, X_NGV, X_NGV + 24)).cut(body)
    body.rotate(V(0, 0, 0), V(1, 0, 0), 180.0 / Z_NGV)
    n = body.fuse([rot_shape(piece, 360.0 * k / Z_NGV) for k in range(Z_NGV)])
    if kind == 'final':
        for k in range(6):
            a = math.radians(60 * k)
            n = n.cut(Part.makeCylinder(1.6, 3.0, V(102.8, 16 * math.cos(a), 16 * math.sin(a)), V(1, 0, 0)))
    try: n = n.removeSplitter()
    except Exception: pass
    return n, nsec, piece

def fc_build(verbose=True, parts=('wheel', 'sector', 'ngv')):
    App, Part, V = _fc()
    T0 = __import__('time').time()
    def log(*a):
        if verbose: print('[%5.0fs]' % (__import__('time').time() - T0), *a); sys.stdout.flush()
    os.makedirs(OUT, exist_ok=True); os.makedirs(FEA_DIR, exist_ok=True)
    ngv = design_ngv(); rot = design_rotor(); rep = aero_report(ngv, rot, verbose=verbose)
    R = dict(rep=rep, ngv=ngv, rot=rot, log=log, ngv_bore_r=ngv_bore_r())
    blade_raw, blade_f, blade_c, nw = fc_blade(rot)
    log('rotor blade loft (%d sections, integral root fillet R%.1f) valid %s vol %.1f' % (nw, FILLET_ROT, blade_raw.isValid(), blade_raw.Volume))
    disc_f, disc_c = fc_disc('final'), fc_disc('cast')
    log('disc final vol %.0f mm3, cast %.0f' % (disc_f.Volume, disc_c.Volume))
    w1f = disc_f.fuse(blade_f)
    piece_f = blade_f.cut(disc_f); piece_c = blade_c.cut(disc_c)
    log('single-blade wheel valid %s; blade above hub vol final %.2f cast %.2f mm3' % (w1f.isValid(), piece_f.Volume, piece_c.Volume))
    R.update(blade=blade_f, piece=piece_f, piece_c=piece_c, w1f=w1f, disc_f=disc_f, disc_c=disc_c)
    if 'sector' in parts:
        sector = fc_sector(w1f, rot, log)
        sector.exportStep(os.path.join(OUT, 'fea_sector.step'))
        log('FEA sector written: valid %s vol %.1f faces %d' % (sector.isValid(), sector.Volume, len(sector.Faces)))
        R['sector'] = sector
    if 'wheel' in parts:
        wheel_f = fc_full_wheel(disc_f, piece_f); log('full wheel final: valid %s, solids %d, vol %.0f' % (wheel_f.isValid(), len(wheel_f.Solids), wheel_f.Volume))
        wheel_c = fc_full_wheel(disc_c, piece_c); log('full wheel cast : valid %s, solids %d, vol %.0f' % (wheel_c.isValid(), len(wheel_c.Solids), wheel_c.Volume))
        R.update(wheel_f=wheel_f, wheel_c=wheel_c)
    if 'ngv' in parts:
        RB = R['ngv_bore_r']
        ngv_f, nsec, vpiece = fc_ngv(ngv, 'final', RB); log('NGV final: vane loft %d sections, valid %s, solids %d, vol %.0f, bore r %.3f' % (nsec, ngv_f.isValid(), len(ngv_f.Solids), ngv_f.Volume, RB))
        ngv_c, _, _ = fc_ngv(ngv, 'cast', RB); log('NGV cast : valid %s, vol %.0f' % (ngv_c.isValid(), ngv_c.Volume))
        R.update(ngv_f=ngv_f, ngv_c=ngv_c, vane_piece=vpiece)
    return R

if __name__ == '__main__' and '--aero' in sys.argv:
    ngv = design_ngv(); rot = design_rotor(); aero_report(ngv, rot)
    for k in ('final', 'cast'):
        A, xc, rc = polygon_area_centroid(sample_profile(disc_profile(k)))
        print('disc profile %-5s: meridional area %.1f mm2, centroid x %.2f r %.2f, volume %.0f mm3' % (k, A, xc, rc, 2 * math.pi * rc * A))
    sys.exit(0)

MODE = os.environ.get('E1_MODE', 'full')     # full | test-sector | aero (freecadcmd passes no CLI flags)
if __name__ == '__main__' and MODE == 'test-sector':
    R = fc_build(parts=('sector',))
    sys.exit(0)
