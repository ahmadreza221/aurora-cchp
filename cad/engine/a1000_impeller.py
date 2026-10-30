"""AURORA-1000 two-stage centrifugal compressor (15,000 rpm): impeller detail design, vaned diffusers, return channel and CAD.

Source of the stage data: sim/mw1_meanline.json (python3 sim/mw1_meanline.py): D2, U2, b2, PR, eta, 13 + 13 blades, 40 deg
backsweep. The detail design keeps those and sets:
  meridional  hub and shroud (blade tip) as cubic Bezier curves, axial at the leading edge, radial at the exit. The two
              curves share the Bezier parameter t, with equal dx/dt at the LE and equal dr/dt at the exit
  blades      RULED surfaces (5-axis flank milling): every blade side is a set of straight lines from hub(t) to shroud(t).
              Shroud blade angle beta_s(t) prescribed (Bezier), hub wrap theta_h = theta_s + d(t), d(0) = d'(0) = d'(1) = 0:
              the LE rulings are radial (no centrifugal bending in the inducer, hub angle follows tan(beta) ~ r like the
              inlet flow) and the hub angle at the exit equals the shroud angle (backsweep). Normal thickness at hub and
              shroud; elliptic LE, TE cut by the r2 cylinder (turned)
  splitters   the main-blade camber shifted by half a pitch, starting at u_split of the meridional length
  checks      inducer (incidence, relative Mach), inducer throat and choke margin, passage area and blade loading
              (Stanitz pressure/suction-side velocities), ruled-surface twist (flank-milling deviation)
  1-D model   Wiesner slip with the effective blade count; Oh / Yoon / Chung (1997) loss set (incidence, blade loading,
              skin friction, clearance, mixing; disc friction, recirculation, leakage), vaneless gap (Stanitz friction),
              vaned diffuser (2-D channel effectiveness), return channel and collector losses -> PR and eta vs the meanline
  diffuser    vaned (machined vanes, parallel walls, pinched vaneless gap), count chosen against impeller resonance
              (sim/engine/a1000_impeller_fea.py --post)
  layout      rotor frame of sim/engine/a1000_rotordynamics.py (mm, x from the gearbox coupling face). Both impellers keep
              their envelopes (x 205 .. 205 + 0.30 D2, spacer 50 mm, 0.30 D2): the rotor stack (cad/engine/a1000_rotor.py)
              and the turbine do not move; impeller 2 has a 29.5 mm rotating nose under the return-channel bend
Frame: x axial (flow +x), r radial [mm], +theta = direction of rotation (same as cad/engine/a1000_turbine.py).
Run:  python cad/engine/a1000_impeller.py                 design report -> sim/a1000_impeller_design.json,
                                                          docs/img/a1000_impeller_design.png
      freecadcmd -c "import sys; sys.argv=['x','--cad']; exec(open('cad/engine/a1000_impeller.py').read())"   CAD
      ... sys.argv=['x','--sector']                     1/13 cyclic sectors for CalculiX (sim/engine/a1000_impeller_fea.py)
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'sim'))
ML = json.load(open(os.path.join(ROOT, 'sim', 'mw1_meanline.json')))
N_RPM = ML['rpm']; OM = N_RPM * 2 * math.pi / 60
MA = ML['ma']                                                     # compressor air [kg/s]
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
JSON = os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')
_argv = list(sys.argv); sys.argv = [sys.argv[0]]
import mw1_meanline as MLM                                       # noqa: E402
import mw1_concept_study as G                                    # noqa: E402
sys.argv = _argv
AIR = G.cycle(MLM.CASE, 'design_chilled')['air']                 # humid air (NIST Shomate), as the meanline
RG = AIR.R
C1, C2 = ML['compressor']

# ------------------------------------------------------------------------------------------------ layout (rotor frame, mm)
X0_1 = 205.0; L_1 = 0.30 * C1['D2'] * 1e3                         # sim/engine/a1000_rotordynamics.py rotor(): unchanged
X_END_2 = X0_1 + L_1 + 50.0 + 0.30 * C2['D2'] * 1e3               # rear face of impeller 2 (drum / turbine unchanged)
L_2 = 0.30 * C2['D2'] * 1e3                                       # impeller 2 keeps its envelope (spacer 50 mm, rotor stack);
                                                                  # the blades need 100 mm, the nose takes the rest (29.5 mm):
                                                                  # the return-channel bend sits over the rotating nose
# Stage parameters (detail design choices; the meanline values are read from sim/mw1_meanline.json):
#  r1h     inducer hub radius: impeller 1 sits on the D110 journal / thrust shaft (static inlet hub seals at r ~57-62),
#          impeller 2 behind the return-channel bend over the D150 interstage spacer (diaphragm seal at r ~77):
#          meanline hub ratios 0.38 / 0.45 (r1h 48.6 / 49.5 mm) do not clear the shafts. r1t re-optimised (min W1t).
#  nose    rotating nose ahead of the blade LE; t_tip axial hub thickness at r2 (flat, turned back face)
#  r_bore  tie-bolt bore (rotor stack cad/engine/a1000_rotor.py: M42 tie bolt, BORE_IMP 46 mm)
#  a_s,c_s shroud Bezier shape: P1 at a_s of the axial length (axial tangent), P2 at c_s of the radial rise below r2
#  beta_s  shroud blade angle Bezier values at t = 1/3, 2/3 (t = 0: inlet blade angle, t = 1: backsweep)
#  d_te    hub-shroud wrap offset at the TE [deg] (TE rake), d(t) = d_te (3t^2 - 2t^3)
#  th_h/s  normal thickness hub / shroud: LE, max (from s = 0.35), TE [mm]
#  clr     cold tip clearance [mm]; Zd, Zr: diffuser / return-channel vanes (impeller resonance, a1000_impeller_fea.py)
#  mat     impeller 1 Ti-6Al-4V (rev 1; meanline Al 2618-T61): in Al the tie-bolt bore runs at 216-236 MPa hoop at
#          U2 334 m/s -> 6,300-9,200 start-stop cycles (Manson-Morrow, factors 2 / 20) against 10,000, and the front curvic
#          (rotor stack) at 0.97 of its flank limit; a back-face recess (p['recess'] = depth, min. wall, inner radius)
#          lowered the bore to 166 MPa but made the hub disc bend (1.4 mm axial at the blade tip, 266 MPa at the recess
#          floor, trip yield margin 0.97). Ti-6Al-4V on the same geometry: ~47,000 cycles, curvic 0.35 of the limit
# D2, b2 (rev 1, sized with the 1-D model below): the meanline sets the work with sigma (1 - phi2 tan(beta2)); Wiesner's
# slip factor is defined as sigma = 1 - c_slip / U2, i.e. c_theta2 = sigma U2 - c_m2 tan(beta2), which is ~3 % less work
# at phi2 0.28; with the effective blade count of the part-length splitters (Z_eff 22.1, sigma 0.900 instead of 0.911)
# and the real exit blockage (blades 2.2-6 mm: 15 % instead of 8 %) D2 413 / 448 gave PR 1.87 / 1.83 (3.29 overall).
# D2 is raised at the meanline backsweep, blade count and speed until the stage-1 total pressure at the diffuser exit is
# the meanline PR 2.008 and the stage-2 collector flange is at 3.8 x the stage-1 inlet (incl. the return-channel and
# collector losses); b2 from phi2 = c_m2 / U2 = 0.30.
ST = dict(
    C1=dict(key='C1', ml=C1, name='Impeller 1', mat='Ti-6Al-4V', rho=4430.0, x0=X0_1, L=L_1, D2=426.0, b2=33.5,
            r1h=60.0, nose=10.0, t_tip=8.0, r_bore=23.0, clr=0.50, a_s=0.60, c_s=0.45, hub_mid=(1.0, 0.10),
            beta_s=(None, 52.0, 42.0), inc=2.0, d_te=0.0, th_h=(2.4, 4.5, 6.0), th_s=(1.4, 2.4, 2.2), le_ratio=2.0,
            u_split=0.30, pinch=0.92, r3=1.10, r4=1.58, alpha4b=53.0, Zd=19, vane=(1.6, 7.0, 2.2), Zr=17),
    C2=dict(key='C2', ml=C2, name='Impeller 2', mat='Ti-6Al-4V', rho=4430.0, x0=X_END_2 - L_2, L=L_2, D2=476.0, b2=16.5,
            r1h=80.0, nose=29.5, t_tip=7.0, r_bore=23.0, clr=0.40, a_s=0.60, c_s=0.45, hub_mid=(1.0, 0.25),
            beta_s=(None, 52.0, 42.0), inc=2.0, d_te=0.0, th_h=(2.0, 3.6, 5.0), th_s=(1.2, 2.0, 1.8), le_ratio=2.0,
            u_split=0.30, pinch=0.92, r3=1.10, r4=1.55, alpha4b=53.0, Zd=19, vane=(1.4, 5.5, 1.8), Zr=None),
)
Z_MAIN = 13
RET = dict(b=40.0, wall=10.0, gap_back=2.5, R_in=12.0, r6_over_r1t=1.20, vane=(2.0, 8.0, 2.0))   # return channel 1 -> 2


# ------------------------------------------------------------------------------------------------ helpers
def bez(P, t):
    """Bezier curve of any degree (Bernstein form): P (n+1, 2) poles, t array -> (len(t), 2)"""
    t = np.asarray(t, float)[..., None]; P = np.asarray(P, float); n = len(P) - 1
    return sum(math.comb(n, i) * (1 - t) ** (n - i) * t ** i * P[i] for i in range(n + 1))


def dbez(P, t):
    P = np.asarray(P, float); n = len(P) - 1
    return n * bez(np.diff(P, axis=0), t) if n > 1 else np.broadcast_to(n * (P[1] - P[0]), (len(np.atleast_1d(t)), 2))


def bez1(v, t):
    t = np.asarray(t, float); return (1 - t) ** 3 * v[0] + 3 * (1 - t) ** 2 * t * v[1] + 3 * (1 - t) * t ** 2 * v[2] + t ** 3 * v[3]


def cumtrapz(y, x):
    return np.r_[0.0, np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(x))]


def gam(T):
    cp = AIR.cp(T); return cp, cp / (cp - RG)


def inducer(T01, P01, m, r1h, step=0.25e-3):
    """inducer tip radius for the minimum relative tip Mach number at a fixed hub radius (axial inflow, 2 % blockage)"""
    cp, g = gam(T01); best = None
    for r1t in np.arange(r1h + 0.03, 0.25, step):
        A1 = math.pi * (r1t ** 2 - r1h ** 2) * 0.98; c1 = 100.0; ok = True
        for _ in range(80):
            T1 = T01 - c1 ** 2 / (2 * cp); rho1 = P01 * (T1 / T01) ** (g / (g - 1)) / (RG * T1); c1n = m / (rho1 * A1)
            if c1n > 260.0: ok = False; break                         # inducer too small (near choke)
            c1 = 0.5 * (c1 + c1n)
        if not ok or c1 > 0.75 * math.sqrt(g * RG * T1): continue
        M1r = math.hypot(c1, OM * r1t) / math.sqrt(g * RG * T1)
        if best is None or M1r < best[1]: best = (r1t, M1r, c1)
    return best


# ------------------------------------------------------------------------------------------------ impeller geometry
class Impeller:
    """meridional contours, camber (ruled), thickness and the blade outlines of one stage (all lengths mm, angles rad)"""
    NT = 601

    def __init__(self, key):
        p = self.p = ST[key]; ml = p['ml']; self.key = key
        self.r2 = p.get('D2', ml['D2'] * 1e3) / 2; self.b2 = p.get('b2', ml['b2'] * 1e3); self.beta2 = math.radians(ml['backsweep'])
        self.r1h = p['r1h']
        r1t, self.M1rel_opt, _ = inducer(ml['T01'], ml['P01'], MA, p['r1h'] * 1e-3)
        self.r1t = round(r1t * 1e3 * 2) / 2                         # 0.5 mm
        self.x0, self.L = p['x0'], p['L']
        self.xle = self.x0 + p['nose']; self.xh2 = self.x0 + self.L - p['t_tip']; self.xs2 = self.xh2 - self.b2
        # shroud: cubic; hub: quartic with a free middle pole (px, pr in the hub's box) for the passage-area distribution;
        # end poles from the matching conditions (dx/dt at t = 0 and dr/dt at t = 1 equal on hub and shroud)
        a_s, c_s = p['a_s'], p['c_s']; px, pr = p['hub_mid']
        Lxs, Lxh, dRs, dRh = self.xs2 - self.xle, self.xh2 - self.xle, self.r2 - self.r1t, self.r2 - self.r1h
        a_h = 3 * a_s * Lxs / (4 * Lxh); c_h = 3 * c_s * dRs / (4 * dRh)
        self.Ps = np.array([(self.xle, self.r1t), (self.xle + a_s * Lxs, self.r1t), (self.xs2, self.r2 - c_s * dRs), (self.xs2, self.r2)])
        self.Ph = np.array([(self.xle, self.r1h), (self.xle + a_h * Lxh, self.r1h), (self.xle + px * Lxh, self.r1h + pr * dRh),
                            (self.xh2, self.r2 - c_h * dRh), (self.xh2, self.r2)])
        self.t = np.linspace(0, 1, self.NT)
        self.H, self.S = bez(self.Ph, self.t), bez(self.Ps, self.t)
        self.dH, self.dS = dbez(self.Ph, self.t), dbez(self.Ps, self.t)
        self.mh = cumtrapz(np.linalg.norm(self.dH, axis=1), self.t); self.ms = cumtrapz(np.linalg.norm(self.dS, axis=1), self.t)
        self.g_ext = np.linalg.norm(self.dS[-1])                    # dm/dt at the exit (hub = shroud)
        # inlet flow angles at hub / shroud (axial inflow, c1 from continuity with 2 % blockage)
        cp, g = gam(ml['T01']); A1 = math.pi * ((self.r1t * 1e-3) ** 2 - (self.r1h * 1e-3) ** 2) * 0.98; c1 = 100.0
        for _ in range(80):
            T1 = ml['T01'] - c1 ** 2 / (2 * cp); rho1 = ml['P01'] * (T1 / ml['T01']) ** (g / (g - 1)) / (RG * T1)
            c1 = 0.5 * (c1 + MA / (rho1 * A1))
        self.c1, self.T1, self.rho1 = c1, T1, rho1
        self.beta1f_s = math.atan(OM * self.r1t * 1e-3 / c1); self.beta1f_h = math.atan(OM * self.r1h * 1e-3 / c1)
        inc = math.radians(p['inc'])
        b1s = self.beta1f_s + inc
        bs = p['beta_s']
        self.beta_s = np.radians(bez1([math.degrees(b1s), bs[1], bs[2], ml['backsweep']], self.t))
        ths_d = -np.tan(self.beta_s) * np.linalg.norm(self.dS, axis=1) / self.S[:, 1]
        self.th_s = cumtrapz(ths_d, self.t)
        dte = math.radians(p['d_te'])
        self.dlt = dte * (3 * self.t ** 2 - 2 * self.t ** 3); ddlt = dte * (6 * self.t - 6 * self.t ** 2)
        self.th_h = self.th_s + self.dlt
        thh_d = ths_d + ddlt
        self.beta_h = np.arctan(-thh_d * self.H[:, 1] / np.linalg.norm(self.dH, axis=1))
        self.u_h = self.mh / self.mh[-1]; self.u_s = self.ms / self.ms[-1]
        self.t_split = float(np.interp(p['u_split'], self.u_s, self.t))
        self.rake = math.degrees(math.atan(self.r2 * (self.th_s[-1] - self.th_h[-1]) / self.b2))

    # -------------------------------------------------------------------- per-contour data
    def contour(self, side):
        return (self.H, self.dH, self.mh, self.th_h, self.beta_h, self.p['th_h']) if side == 'hub' else \
               (self.S, self.dS, self.ms, self.th_s, self.beta_s, self.p['th_s'])

    def xr_of_m(self, side, m):
        """(x, r) on the hub / shroud line at meridional distance m from the LE; axial upstream (m < 0), radial beyond r2"""
        C, _, mm, *_ = self.contour(side); m = np.atleast_1d(np.asarray(m, float))
        x = np.interp(m, mm, C[:, 0]); r = np.interp(m, mm, C[:, 1])
        lo = m < 0; x[lo] = C[0, 0] + m[lo]; r[lo] = C[0, 1]
        hi = m > mm[-1]; x[hi] = C[-1, 0]; r[hi] = C[-1, 1] + (m[hi] - mm[-1])
        return x, r

    def thick(self, side, t, t_start=0.0, ramp=None):
        """normal thickness at parameter t; the splitter (t_start > 0) starts with the LE thickness and blends into the
        main-blade distribution within 0.15 of the meridional length"""
        _, _, mm, _, _, (tle, tmx, tte) = self.contour(side)
        u = np.interp(np.minimum(t, 1.0), self.t, mm) / mm[-1]
        sm = 0.35
        tm = np.where(u < sm, tle + (tmx - tle) * 0.5 * (1 - np.cos(np.pi * u / sm)), tmx + (tte - tmx) * (u - sm) / (1 - sm))
        if t_start > 0:
            u0 = float(np.interp(t_start, self.t, mm)) / mm[-1]
            w = np.clip((u - u0) / 0.15, 0, 1); blend = 0.5 * (1 - np.cos(np.pi * w))
            tm = tle + (tm - tle) * blend
        return tm

    def camber(self, side, t):
        """camber point (m, theta, beta) at parameter t, extended radially beyond t = 1 (beta = backsweep)"""
        C, dC, mm, th, be, _ = self.contour(side); t = np.atleast_1d(np.asarray(t, float))
        m = np.interp(t, self.t, mm); T = np.interp(t, self.t, th); B = np.interp(t, self.t, be)
        hi = t > 1.0
        if hi.any():
            dm = (t[hi] - 1.0) * self.g_ext; r = self.r2 + dm
            m[hi] = mm[-1] + dm; B[hi] = self.beta2; T[hi] = th[-1] - math.tan(self.beta2) * np.log(r / self.r2)
        return m, T, B

    def outline(self, side, t0=0.0, t1=None, n_side=110, n_le=14, n_te=6, theta_shift=0.0, dl=0.0):
        """closed blade outline on the hub or shroud line as two halves (suction side, pressure side), both running from
        the LE nose to the TE tip point, same point count and parameter correspondence on hub and shroud (ruled loft).
        dl > 0: outline offset outward by dl (root-fillet sections; the LE ellipse grows by dl on both axes).
        Returns two (n, 3) arrays of (x, r, theta)."""
        t1 = 1.0 + 4.0 / self.g_ext if t1 is None else t1              # 4 mm beyond r2 (cut by the r2 cylinder)
        ts = t0 + (t1 - t0) * (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n_side)))   # clustered at LE and TE
        m, th, be = self.camber(side, ts)
        tn = self.thick(side, ts, t_start=t0) + 2 * dl
        _, r_c = self.xr_of_m(side, m)
        def at(mq, yq):                                                # local (m, r theta) offset -> (x, r, theta)
            x_, r_ = self.xr_of_m(side, mq); return np.c_[x_, r_, yq / r_]
        halves = []
        for sgn in (-1, 1):                                            # -1 suction side (-theta), +1 pressure side
            sd = at(m + sgn * tn / 2 * np.sin(be), r_c * th + sgn * tn / 2 * np.cos(be))
            sd[:, 2] = (r_c * th + sgn * tn / 2 * np.cos(be)) / sd[:, 1]
            # LE quarter ellipse: nose (phi = 0) -> side start (phi = sgn pi/2)
            b_e = tn[0] / 2; a_e = self.p['le_ratio'] * (b_e - dl) + dl; ph = np.linspace(0, sgn * np.pi / 2, n_le)[:-1]
            dm_ = -a_e * np.cos(ph) * math.cos(be[0]) + b_e * np.sin(ph) * math.sin(be[0])
            dy_ = a_e * np.cos(ph) * math.sin(be[0]) + b_e * np.sin(ph) * math.cos(be[0])
            le = at(m[0] + dm_, r_c[0] * th[0] + dy_); le[:, 2] = (r_c[0] * th[0] + dy_) / le[:, 1]
            # TE quarter circle: side end -> tip point on the camber extension
            rt = tn[-1] / 2; ph = np.linspace(sgn * np.pi / 2, 0, n_te)[1:]
            dm_ = rt * np.cos(ph) * math.cos(be[-1]) + rt * np.sin(ph) * math.sin(be[-1])
            dy_ = -rt * np.cos(ph) * math.sin(be[-1]) + rt * np.sin(ph) * math.cos(be[-1])
            te = at(m[-1] + dm_, r_c[-1] * th[-1] + dy_); te[:, 2] = (r_c[-1] * th[-1] + dy_) / te[:, 1]
            h = np.vstack([le, sd, te]); h[:, 2] += theta_shift
            halves.append(h)
        return halves

    def blades(self):
        """{'main': (hub halves, shroud halves), 'split': ...}: outlines in (x, r, theta)"""
        out = {}
        for name, t0, sh, n in (('main', 0.0, 0.0, 120), ('split', self.t_split, math.pi / Z_MAIN, 90)):
            out[name] = (self.outline('hub', t0, theta_shift=sh, n_side=n), self.outline('shroud', t0, theta_shift=sh, n_side=n))
        return out

    # -------------------------------------------------------------------- casing and hub profiles
    def casing(self, n=80):
        """casing wall over the blade tips: shroud line offset by the clearance (normal to the line)"""
        d = self.dS / np.linalg.norm(self.dS, axis=1)[:, None]; nrm = np.c_[-d[:, 1], d[:, 0]]     # left normal (outward)
        C = self.S + self.p['clr'] * nrm
        idx = np.linspace(0, self.NT - 1, n).astype(int)
        return C[idx]

    def back_face(self):
        """back-face points from the tip band (r2 - 1) down to the bore: flat (turned), or with the turned recess of
        p['recess'] = (depth, minimum wall to the hub flow line, inner radius): mass taken out between the curvic land and
        the tip band lowers the bore hoop stress (start-stop LCF of the Al impeller)"""
        xb = self.x0 + self.L; rb = self.p['r_bore']; rec = self.p.get('recess')
        if not rec:
            return [(xb, self.r2 - 1.0), (xb, rb)]
        d, wmin, rc = rec
        rs = np.linspace(self.r2 - 1.0, rc, 90); xh = np.interp(rs, self.H[:, 1], self.H[:, 0])
        cap = np.maximum(xb - xh - wmin, 0.0)                         # wall to the hub flow line >= wmin
        ramp = 0.5 * (1 - np.cos(np.pi * np.clip((rs - rc) / 14.0, 0, 1)))   # R ~ 7 blend into the curvic land
        dep = np.minimum(d * ramp, cap)
        dep = np.convolve(np.pad(dep, 4, mode='edge'), np.ones(9) / 9, 'valid')   # smooth the wall-limited part
        return [(xb - q, r) for q, r in zip(dep, rs)] + [(xb, rb)]

    def hub_profile(self):
        """closed (x, r) polygon of the hub body (the hub flow line as dense points): nose, hub line, tip band, back face
        (flat or recessed), bore; small edge breaks at the nose and the back-face corner"""
        p = self.p; rb = p['r_bore']; ch = 0.5
        line = self.H[::6]
        poly = [(self.x0, rb), (self.x0, self.r1h - ch), (self.x0 + ch, self.r1h)] + [tuple(q) for q in line] + \
               [(self.x0 + self.L - 1.0, self.r2)] + [tuple(map(float, q)) for q in self.back_face()]
        return poly

    # -------------------------------------------------------------------- 3-D helpers
    def cart(self, xrt):
        xrt = np.asarray(xrt); return np.c_[xrt[:, 0], xrt[:, 1] * np.cos(xrt[:, 2]), xrt[:, 1] * np.sin(xrt[:, 2])]

    def ruling_point(self, side_pts_h, side_pts_s, v):
        """points at ruling parameter v (0 hub, 1 shroud) between corresponding hub / shroud outline points (Cartesian)"""
        Hc, Sc = self.cart(side_pts_h), self.cart(side_pts_s)
        return Hc + np.asarray(v)[..., None] * (Sc - Hc)


# ------------------------------------------------------------------------------------------------ aerodynamic checks
def passage(imp):
    """quasi-orthogonal (ruling) passage area, mean relative velocity, Stanitz blade loading on hub and shroud"""
    ml = imp.p['ml']; T01, P01 = ml['T01'], ml['P01']; cp, g = gam(T01); h01 = cp * T01
    t = imp.t
    Hc = imp.cart(np.c_[imp.H, imp.th_h]); Sc = imp.cart(np.c_[imp.S, imp.th_s])
    span = np.linalg.norm(Sc - Hc, axis=1)                             # ruling length [mm]
    rbar = 0.5 * (imp.H[:, 1] + imp.S[:, 1])
    # meridional width normal to the mean flow: ruling length x cos(angle between the ruling and the meridional normal)
    dmean = 0.5 * (imp.dH / np.linalg.norm(imp.dH, axis=1)[:, None] + imp.dS / np.linalg.norm(imp.dS, axis=1)[:, None])
    dmean /= np.linalg.norm(dmean, axis=1)[:, None]
    q = imp.S - imp.H; wn = np.abs(q[:, 0] * (-dmean[:, 1]) + q[:, 1] * dmean[:, 0])
    Zl = np.where(t >= imp.t_split, 2 * Z_MAIN, Z_MAIN)
    bm = 0.5 * (imp.beta_h + imp.beta_s); tm = 0.5 * (imp.thick('hub', t) + imp.thick('shroud', t))
    tsp = np.where(t >= imp.t_split, 0.5 * (imp.thick('hub', t, imp.t_split) + imp.thick('shroud', t, imp.t_split)), 0.0)
    blk = Z_MAIN * (tm + tsp) / (2 * np.pi * rbar * np.cos(bm))     # blade blockage (main + splitter)
    A = 2 * np.pi * rbar * wn * (1 - blk) * 0.96 * 1e-6                # 4 % end-wall boundary-layer blockage [m2]
    U = OM * rbar * 1e-3
    W = np.full_like(t, 150.0)
    for _ in range(60):                                                # rothalpy: h = h01 + (U^2 - W^2) / 2
        T = (h01 + 0.5 * (U ** 2 - W ** 2)) / cp
        rho = P01 * (T / T01) ** (g / (g - 1)) / (RG * T) * 0.98       # ~2 % entropy rise mid-passage
        Wm = MA / (rho * A); W = 0.5 * (W + Wm / np.cos(bm))
    res = {}
    for side, C, be, mm in (('hub', imp.H, imp.beta_h, imp.mh), ('shroud', imp.S, imp.beta_s, imp.ms)):
        r = C[:, 1] * 1e-3; Ws = Wm / np.cos(be); ct = OM * r - Wm * np.tan(be)
        rct = r * ct; dm = mm * 1e-3
        k = 15; rct = np.convolve(np.pad(rct, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')   # smooth (splitter LE)
        dW = 2 * np.pi / Zl * np.gradient(rct, dm)
        res[side] = dict(m=mm, W=Ws, Wss=Ws + dW / 2, Wps=Ws - dW / 2)
    return dict(A=A, W=W, Wm=Wm, rho=rho, span=span, wn=wn, res=res)


def throat(imp, n_span=11):
    """inducer throat between the main blades: in each span strip the minimum distance (developed blade-to-blade plane at
    the LE radius) from the LE of blade k to the suction side (the -theta face) of blade k+1, the blade ahead in the
    direction of rotation; choke flow in the relative frame"""
    ml = imp.p['ml']; T01, P01 = ml['T01'], ml['P01']; cp, g = gam(T01)
    ts = np.linspace(0, 0.5, 400); fs = np.linspace(0, 1, n_span)
    o, ds_, Tr, Pr = [], [], [], []
    for f in fs:
        # streamline f: points along the rulings of the camber surface
        Hc = imp.cart(np.c_[bez(imp.Ph, ts), np.interp(ts, imp.t, imp.th_h)])
        Sc = imp.cart(np.c_[bez(imp.Ps, ts), np.interp(ts, imp.t, imp.th_s)])
        P = Hc + f * (Sc - Hc); x = P[:, 0]; r = np.hypot(P[:, 1], P[:, 2]); th = np.arctan2(P[:, 2], P[:, 1])
        m = cumtrapz(np.hypot(np.gradient(x), np.gradient(r)), np.arange(len(x)).astype(float))
        r0 = r[0]; y = r0 * th                                         # developed at the LE radius
        tn = (1 - f) * imp.thick('hub', ts) + f * imp.thick('shroud', ts)
        dy = np.gradient(y, m); be = np.arctan(-dy)
        ss = np.c_[m - tn / 2 * np.sin(be), y + 2 * np.pi * r0 / Z_MAIN - tn / 2 * np.cos(be)]   # suction side of blade k+1
        le = np.array([m[0], y[0]])                                    # LE of blade k
        d = np.linalg.norm(ss - le, axis=1); o.append(d.min())
        U = OM * r0 * 1e-3; T1 = imp.T1; W1 = math.hypot(imp.c1, U)
        Tr.append(T1 + W1 ** 2 / (2 * cp)); P1 = P01 * (T1 / T01) ** (g / (g - 1)); Pr.append(P1 * (Tr[-1] / T1) ** (g / (g - 1)))
        ds_.append(r0)
    rr = np.array(ds_); o = np.array(o)
    # span length at the LE (radial LE ruling)
    dl = np.gradient(rr)
    A_th = Z_MAIN * np.sum(o * dl) * 1e-6
    fchoke = math.sqrt(g / RG) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    m_ch = Z_MAIN * np.sum(o * dl * 1e-6 * np.array(Pr) / np.sqrt(np.array(Tr)) * fchoke) * 0.97   # 3 % BL blockage
    A1 = math.pi * ((imp.r1t * 1e-3) ** 2 - (imp.r1h * 1e-3) ** 2)
    beta_rms = math.atan(OM * math.sqrt(0.5 * (imp.r1t ** 2 + imp.r1h ** 2)) * 1e-3 / imp.c1)
    return dict(o_mm=o.tolist(), r_mm=rr.tolist(), A_throat_cm2=A_th * 1e4, A1_cm2=A1 * 1e4,
                throat_capture=A_th / (A1 * math.cos(beta_rms)), m_choke=m_ch, choke_margin=m_ch / MA)


def ruled_twist(imp):
    """twist of the ruled blade surface: angle between the surface normals at the hub and shroud ends of each ruling;
    flank-milling deviation of a cylindrical / conical cutter of radius R placed tangent at mid-ruling ~ R (1 - cos(tw/2))"""
    out = {}
    for name, (hh, ss) in imp.blades().items():
        tw = []
        for k in (0, 1):
            Hc, Sc = imp.cart(hh[k]), imp.cart(ss[k])
            n0 = None
            for P in (Hc, Sc):
                tg = np.gradient(P, axis=0); ru = Sc - Hc
                n = np.cross(tg, ru); n /= np.linalg.norm(n, axis=1)[:, None]
                n0 = n if n0 is None else n0
                last = n
            ang = np.degrees(np.arccos(np.clip(np.sum(n0 * last, axis=1), -1, 1)))
            tw.append(ang[15:-8])                                   # sides only (LE / TE caps excluded)
        tw = np.concatenate(tw)
        out[name] = dict(twist_max_deg=float(tw.max()), twist_mean_deg=float(tw.mean()),
                         dev_R3_mm=float(3.0 * (1 - math.cos(math.radians(tw.max()) / 2))))
    return out


# ------------------------------------------------------------------------------------------------ 1-D performance model
def slip_wiesner(beta2, Z):
    return 1 - math.sqrt(math.cos(beta2)) / Z ** 0.7


def friction_cf(Re, rough_rel):
    """Fanning friction coefficient (Haaland)"""
    fD = (-1.8 * math.log10((rough_rel / 3.7) ** 1.11 + 6.9 / Re)) ** -2
    return fD / 4


def vaneless(T0, P0, r_a, r_b, b_a, b_b, cm, ct, n=200, Cf=0.005):
    """Stanitz vaneless space with wall friction; returns (P0, c_m, c_theta, P, T) at r_b"""
    cp, g = gam(T0); rs = np.linspace(r_a, r_b, n); s = 0.0
    m = MA; P0_ = P0
    for i in range(n - 1):
        r, dr = rs[i], rs[i + 1] - rs[i]; b = b_a + (b_b - b_a) * (r - r_a) / (r_b - r_a)
        c = math.hypot(cm, ct); T = T0 - c ** 2 / (2 * cp)
        ds = Cf * c ** 3 / (cm * b) * dr / T                         # entropy rise per unit mass [J/kg K]
        P0_ *= math.exp(-ds / RG)
        rn = rs[i + 1]; bn = b_a + (b_b - b_a) * (rn - r_a) / (r_b - r_a)
        rct = r * ct - Cf * c * ct * r / (b * cm) * dr * r          # angular momentum loss by friction
        ct = rct / rn
        for _ in range(20):
            c = math.hypot(cm, ct); T = T0 - c ** 2 / (2 * cp); P = P0_ * (T / T0) ** (g / (g - 1))
            cm = m / (P / (RG * T) * 2 * math.pi * rn * bn * 0.95)  # 5 % wall blockage
    c = math.hypot(cm, ct); T = T0 - c ** 2 / (2 * cp); P = P0_ * (T / T0) ** (g / (g - 1))
    return P0_, cm, ct, P, T


def diffuser_channel(st, r3, r4, b, Zd, alpha3, alpha4b, vane):
    """2-D channel of a vaned diffuser: throat width at the vane LE, exit width, area ratio, equivalent divergence angle
    2 theta = 2 atan((W2 - W1) / 2L), length / throat width; effectiveness from the 2-D diffuser data trend"""
    tle, tmx, tte = vane
    w1 = 2 * math.pi * r3 * math.cos(alpha3) / Zd - 0.5 * (tle + tmx) * 0.5
    w2 = 2 * math.pi * r4 * math.cos(alpha4b) / Zd - tte
    L = (r4 - r3) / math.cos(0.5 * (alpha3 + alpha4b))
    AR = w2 / w1; tt = 2 * math.degrees(math.atan((w2 - w1) / (2 * L)))
    return dict(w_throat=w1, w_exit=w2, L=L, L_W1=L / w1, AR=AR, two_theta=tt, aspect=b / w1,
                solidity=Zd * L / (2 * math.pi * r3))


def stage_performance(imp, pas, thr, T01=None, P01=None):
    """1-D stage model at the design point: impeller (slip + Oh et al. 1997 losses), vaneless gap, vaned diffuser"""
    p = imp.p; ml = p['ml']; T01 = T01 or ml['T01']; P01 = P01 or ml['P01']
    cp, g = gam(T01); r2 = imp.r2 * 1e-3; b2 = imp.b2 * 1e-3; U2 = OM * r2
    r1t, r1h = imp.r1t * 1e-3, imp.r1h * 1e-3; rr1 = math.sqrt(0.5 * (r1t ** 2 + r1h ** 2))
    c1 = imp.c1; T1 = imp.T1; rho1 = imp.rho1
    W1t, W1h, W1r = math.hypot(c1, OM * r1t), math.hypot(c1, OM * r1h), math.hypot(c1, OM * rr1)
    Lm = 0.5 * (imp.mh[-1] + imp.ms[-1]) * 1e-3
    Z_eff = Z_MAIN + Z_MAIN * (1 - p['u_split'])
    sigma = slip_wiesner(imp.beta2, Z_eff); eps_lim = math.exp(-8.16 * math.cos(imp.beta2) / Z_eff)
    t2 = 0.5 * (p['th_h'][2] + p['th_s'][2]) * 1e-3
    blk2 = 2 * Z_MAIN * t2 / (2 * math.pi * r2 * math.cos(imp.beta2)) + 0.04       # blades + 4 % wall
    # incidence at rms (blade angle at rms from the ruled camber: tan beta ~ r)
    beta1b_r = math.atan(math.tan(imp.beta_s[0]) * rr1 / r1t); beta1f_r = math.atan(OM * rr1 / c1)
    eta_imp = 0.92; cm2 = 0.28 * U2
    for _ in range(50):
        ct2 = U2 * (sigma - cm2 / U2 * math.tan(imp.beta2))
        dhE = U2 * ct2
        c2 = math.hypot(cm2, ct2); W2 = math.hypot(cm2, U2 - ct2)
        T02 = T01 + dhE / cp; T2 = T02 - c2 ** 2 / (2 * cp)
        # impeller static pressure from the impeller total-to-total efficiency (iterated)
        P02i = P01 * (1 + eta_imp * dhE / (cp * T01)) ** (g / (g - 1))
        P2 = P02i * (T2 / T02) ** (g / (g - 1)); rho2 = P2 / (RG * T2)
        cm2 = 0.5 * (cm2 + MA / (rho2 * 2 * math.pi * r2 * b2 * (1 - blk2)))
        # ---- losses (Oh, Yoon & Chung 1997 'optimum set')
        L_inc = 0.6 * (W1r * math.sin(beta1f_r - beta1b_r)) ** 2 / 2
        Df = 1 - W2 / W1t + 0.75 * dhE / U2 ** 2 / ((W1t / W2) * (Z_eff / math.pi * (1 - r1t / r2) + 2 * r1t / r2))
        L_bl = 0.05 * Df ** 2 * U2 ** 2
        Dh = float(np.mean(pas['Dh'])) * 1e-3
        Wbar = (c1 + c2 + W1t + 2 * W1h + 3 * W2) / 8
        nu = 1.8e-5 / (0.5 * (rho1 + rho2)); Re = Wbar * Dh / nu
        Cf = friction_cf(Re, 1.6e-6 / Dh)                              # Ra 1.6 um (milled + polished)
        L_sf = 2 * Cf * Lm / Dh * Wbar ** 2
        eps = p['clr'] * 1e-3
        L_cl = 0.6 * eps / b2 * ct2 * math.sqrt(4 * math.pi / (b2 * Z_eff) * (r1t ** 2 - r1h ** 2) /
                                                ((r2 - r1t) * (1 + rho2 / rho1)) * ct2 * c1)
        a2 = math.atan2(ct2, cm2); ew = 0.20                           # Johnston-Dean, wake fraction 0.2, b* = 1
        L_mix = (ew / (1 - ew)) ** 2 * cm2 ** 2 / 2
        L_int = L_inc + L_bl + L_sf + L_cl + L_mix
        Re_df = U2 * r2 / (1.8e-5 / rho2)
        f_df = 2.67 / Re_df ** 0.5 if Re_df < 3e5 else 0.0622 / Re_df ** 0.2
        L_df = f_df * 0.5 * (rho1 + rho2) * r2 ** 2 * U2 ** 3 / (4 * MA)
        L_rc = 8e-5 * math.sinh(3.5 * a2 ** 3) * Df ** 2 * U2 ** 2
        rbar, bbar = 0.5 * (rr1 + r2), 0.5 * ((r1t - r1h) + b2)
        dP_cl = MA * (r2 * ct2) / (Z_eff * rbar * bbar * Lm)
        U_cl = 0.816 * math.sqrt(2 * dP_cl / rho2); m_cl = rho2 * Z_eff * eps * Lm * U_cl
        L_lk = m_cl * U_cl * U2 / (2 * MA)
        L_par = L_df + L_rc + L_lk
        dh0 = dhE + L_par
        eta_new = (dhE - L_int) / dh0
        eta_imp = 0.5 * (eta_imp + eta_new)
    T02 = T01 + dh0 / cp
    T02s = AIR.T_of_h(AIR.h(T01) + dhE - L_int, T01 + (dhE - L_int) / cp)
    P02 = P01 * math.exp((AIR.s0(T02s) - AIR.s0(T01)) / RG)
    # the impeller total pressure: isentropic work dhE - L_int on the total temperature rise dh0
    c2 = math.hypot(cm2, ct2); T2 = T02 - c2 ** 2 / (2 * cp); P2 = P02 * (T2 / T02) ** (g / (g - 1))
    M2 = c2 / math.sqrt(g * RG * T2); a2 = math.degrees(math.atan2(ct2, cm2))
    imp_out = dict(sigma=sigma, Z_eff=Z_eff, eps_lim=eps_lim, r1t_r2=r1t / r2, dhE=dhE, dh0=dh0, cm2=cm2, ct2=ct2, c2=c2,
                   W2=W2, W1t=W1t, DR=W1t / W2, M2=M2, alpha2=a2, T02=T02, P02=P02, T2=T2, P2=P2, eta_imp=eta_imp,
                   Df=Df, blk2=blk2, losses=dict(incidence=L_inc, blade_loading=L_bl, skin_friction=L_sf, clearance=L_cl,
                                                 mixing=L_mix, disc_friction=L_df, recirculation=L_rc, leakage=L_lk),
                   phi2=cm2 / U2, beta1b_rms=math.degrees(beta1b_r), beta1f_rms=math.degrees(beta1f_r), Re=Re, Cf=Cf)
    # ---- vaneless gap r2 -> r3 (pinched: b3 = pinch b2)
    r3 = p['r3'] * r2; b3 = p['pinch'] * b2
    P03, cm3, ct3, P3, T3 = vaneless(T02, P02, r2, r3, b2, b3, cm2, ct2)
    c3 = math.hypot(cm3, ct3); al3 = math.atan2(ct3, cm3); M3 = c3 / math.sqrt(g * RG * T3)
    # ---- vaned diffuser r3 -> r4 (parallel walls b3); deviation 3 deg, incidence -1 deg on the vane LE
    r4 = p['r4'] * r2; al4b = math.radians(p['alpha4b']); al4 = al4b + math.radians(3.0)
    ch = diffuser_channel(st=None, r3=r3 * 1e3, r4=r4 * 1e3, b=b3 * 1e3, Zd=p['Zd'], alpha3=al3, alpha4b=al4b, vane=p['vane'])
    Cp_id = 1 - 1 / ch['AR'] ** 2
    eff = 0.80 - 0.025 * max(0.0, ch['two_theta'] - 9.0)            # 2-D channel, ~10 % inlet blockage
    Cp = Cp_id * eff
    q3 = P03 - P3
    Cf_d = 0.005; dP0_fr = 4 * Cf_d * ch['L'] / (2 * ch['w_throat'] * b3 * 1e3 / (ch['w_throat'] + b3 * 1e3)) * 0.4 * q3
    P4 = P3 + Cp * q3; P04_ = P03 - (Cp_id - Cp) * q3 - dP0_fr
    # exit state from continuity at r4 with the exit flow angle
    cm4 = 40.0
    for _ in range(40):
        ct4 = cm4 * math.tan(al4); c4 = math.hypot(cm4, ct4); T4 = T02 - c4 ** 2 / (2 * cp)
        P4 = P04_ * (T4 / T02) ** (g / (g - 1)); cm4 = 0.5 * (cm4 + MA / (P4 / (RG * T4) * 2 * math.pi * r4 * b3 * 0.95))
    M_th = None
    # throat Mach of the diffuser channel (isentropic from P03, T02 with the throat blockage 8 %)
    A_th = p['Zd'] * ch['w_throat'] * 1e-3 * b3 * 0.92
    ff = MA * math.sqrt(T02) / (P03 * A_th)
    fm = lambda M: math.sqrt(g / RG) * M * (1 + (g - 1) / 2 * M * M) ** (-(g + 1) / (2 * (g - 1)))
    lo, hi = 0.05, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi); lo, hi = (mid, hi) if fm(mid) < ff else (lo, mid)
    M_th = lo if fm(1.0) > ff else float('nan')
    dif = dict(r3=r3 * 1e3, r4=r4 * 1e3, b3=b3 * 1e3, alpha3=math.degrees(al3), alpha3b=math.degrees(al3) - (-1.0),
               alpha4b=p['alpha4b'], alpha4=math.degrees(al4), M3=M3, P03=P03, P3=P3, Cp_ideal=Cp_id, Cp=Cp, eff=eff,
               P04=P04_, P4=P4, c4=c4, T4=T4, M_throat=M_th, choke_margin_throat=fm(1.0) / ff, Zd=p['Zd'], vane=p['vane'], **ch)
    T02s_st = AIR.T_isentropic(T01, P04_ / P01)
    eta_st = (AIR.h(T02s_st) - AIR.h(T01)) / (AIR.h(T02) - AIR.h(T01))
    return dict(impeller=imp_out, diffuser=dif, PR_tt=P04_ / P01, eta_tt=eta_st, T02=T02, P04=P04_, T01=T01, P01=P01)


# ------------------------------------------------------------------------------------------------ design report
def hydraulic_diameter(imp, pas):
    t = imp.t; Zl = np.where(t >= imp.t_split, 2 * Z_MAIN, Z_MAIN)
    rbar = 0.5 * (imp.H[:, 1] + imp.S[:, 1]); bm = 0.5 * (imp.beta_h + imp.beta_s)
    s = 2 * np.pi * rbar * np.cos(bm) / Zl - 0.5 * (imp.thick('hub', t) + imp.thick('shroud', t))
    d = pas['wn']; return 2 * s * d / (s + d)


def design():
    imps = {k: Impeller(k) for k in ST}
    out = dict(rpm=N_RPM, ma=MA, layout=dict(x0_1=X0_1, L_1=L_1, x0_2=ST['C2']['x0'], L_2=L_2, x_end_2=X_END_2), stages={})
    perf = {}
    for k, imp in imps.items():
        pas = passage(imp); pas['Dh'] = hydraulic_diameter(imp, pas)
        thr = throat(imp); tw = ruled_twist(imp)
        T01 = P01 = None
        if k == 'C2':                                                  # stage-2 inlet from the stage-1 exit + return channel
            T01, P01 = perf['C1']['T02'], perf['C1']['P_rc_out']
        pf = stage_performance(imp, pas, thr, T01, P01)
        if k == 'C1':
            d = pf['diffuser']; cp, g = gam(d['T4'])
            rho4 = d['P4'] / (RG * d['T4']); q4 = 0.5 * rho4 * d['c4'] ** 2
            K_rc = 0.45                                               # U-bend 0.15 + deswirl vanes / 90 deg bend 0.30
            pf['P_rc_out'] = d['P04'] - K_rc * q4; pf['K_rc'] = K_rc; pf['dP0_rc_frac'] = K_rc * q4 / d['P04']
        else:
            d = pf['diffuser']; rho4 = d['P4'] / (RG * d['T4']); q4 = 0.5 * rho4 * d['c4'] ** 2
            K_col = 0.60                                              # discharge collector + DN300 outlet
            pf['P_col'] = d['P04'] - K_col * q4; pf['dP0_col_frac'] = K_col * q4 / d['P04']
        perf[k] = pf
        ml = imp.p['ml']
        A2 = 2 * math.pi * imp.r2 * imp.b2; A1 = math.pi * (imp.r1t ** 2 - imp.r1h ** 2)
        out['stages'][k] = dict(
            name=imp.p['name'], material=imp.p['mat'], rho=imp.p['rho'],
            geometry=dict(r1h=imp.r1h, r1t=imp.r1t, r2=imp.r2, b2=imp.b2, x0=imp.x0, L=imp.L, x_le=imp.xle, x_h2=imp.xh2,
                          x_s2=imp.xs2, r_bore=imp.p['r_bore'], t_tip=imp.p['t_tip'], clearance=imp.p['clr'],
                          hub_poles=imp.Ph.tolist(), shroud_poles=imp.Ps.tolist(), L_z_D2=(imp.xh2 - imp.xle) / (2 * imp.r2),
                          m_hub=imp.mh[-1], m_shroud=imp.ms[-1], A2_A1=A2 / A1, wrap_deg=math.degrees(imp.th_s[-1]),
                          rake_deg=imp.rake, t_split=imp.t_split, u_split=imp.p['u_split'],
                          thickness_hub=imp.p['th_h'], thickness_shroud=imp.p['th_s'],
                          hub_profile=[[round(a, 3), round(b, 3)] for a, b in imp.hub_profile()],
                          casing=imp.casing(60).round(3).tolist()),
            inducer=dict(c1=imp.c1, beta1_flow_tip=math.degrees(imp.beta1f_s), beta1_flow_hub=math.degrees(imp.beta1f_h),
                         beta1_blade_tip=math.degrees(imp.beta_s[0]), beta1_blade_hub=math.degrees(imp.beta_h[0]),
                         M1rel_tip=imp.M1rel_opt, meanline_r1t=ml['r1t'] * 1e3, meanline_r1h=ml['r1h'] * 1e3,
                         meanline_M1rel=ml['M1rel_tip']),
            throat=thr, twist=tw,
            loading=dict(Wss_max_W2_shroud=float(pas['res']['shroud']['Wss'][imp.t > 0.10].max() / pf['impeller']['W2']),
                         Wps_min_hub=float(pas['res']['hub']['Wps'].min()), Wps_min_shroud=float(pas['res']['shroud']['Wps'].min()),
                         area_ratio_min=float(pas['A'].min() / pas['A'][0])),
            beta=dict(t=imp.t[::20].tolist(), hub=np.degrees(imp.beta_h[::20]).tolist(), shroud=np.degrees(imp.beta_s[::20]).tolist(),
                      theta_hub=np.degrees(imp.th_h[::20]).tolist(), theta_shroud=np.degrees(imp.th_s[::20]).tolist()),
            performance=pf, meanline=dict(PR=ml['pr'], eta=ml['eta'], sigma=ml['sigma'], T02=ml['T02']))
        imp._pas = pas
    # overall
    o1, o2 = perf['C1'], perf['C2']
    PR_tot = o2['P_col'] / o1['P01']
    T2s = AIR.T_isentropic(o1['T01'], PR_tot)
    eta_tot = (AIR.h(T2s) - AIR.h(o1['T01'])) / (AIR.h(o2['T02']) - AIR.h(o1['T01']))
    cyc0 = G.cycle(MLM.CASE, 'design_chilled'); cyc1 = G.cycle(dict(MLM.CASE, eta_c=eta_tot), 'design_chilled')
    out['overall'] = dict(PR=PR_tot, eta=eta_tot, T_out=o2['T02'], meanline_PR=MLM.CASE['PR'], meanline_eta=MLM.CASE['eta_c'],
                          return_channel_dP0=o1['dP0_rc_frac'], collector_dP0=o2['dP0_col_frac'],
                          eta_el_meanline=cyc0['eta_el'], eta_el_detail=cyc1['eta_el'],
                          P_net_ratio=cyc1['P_net'] / cyc0['P_net'])
    out['return_channel'] = return_channel(imps, perf)
    out['inlet'] = inlet(imps['C1'])
    with open(JSON + '.tmp', 'w') as f:
        json.dump(out, f, indent=1, default=float)
    os.replace(JSON + '.tmp', JSON)
    return imps, out


def return_channel(imps, perf):
    """crossover (U-bend) and return channel between stage 1 and 2: walls in the rotor frame, deswirl vane angles"""
    i1, i2 = imps['C1'], imps['C2']; d1 = perf['C1']['diffuser']
    b_d = d1['b3']; r4 = d1['r4']; x_dif = (i1.xs2, i1.xs2 + b_d)          # diffuser channel (shroud wall, hub wall)
    x_dia0 = i1.x0 + i1.L + RET['gap_back']; x_rc0 = x_dia0 + RET['wall']; x_rc1 = x_rc0 + RET['b']
    # U-bend: from the diffuser channel (x_dif) at r4 to the return channel (x_rc0 .. x_rc1), concentric arcs
    xc = 0.5 * (x_dif[0] + x_rc1); R_out = 0.5 * (x_rc1 - x_dif[0]); R_inn = 0.5 * (x_rc0 - x_dif[1])
    # 90 deg bend into the stage-2 inducer: inner (shroud-side) wall radius R_in round the centre (x_rc1 + R_in, r1t2 + R_in)
    cx, cr = x_rc1 + RET['R_in'], i2.r1t + RET['R_in']
    r6 = RET['r6_over_r1t'] * i2.r1t
    # flow: angular momentum r c_theta conserved through the U-bend (friction neglected), deswirl to zero at r6
    cp, g = gam(d1['T4']); rho4 = d1['P4'] / (RG * d1['T4'])
    rct = r4 * 1e-3 * d1['c4'] * math.sin(math.radians(d1['alpha4']))
    r5 = r4; cm5 = MA / (rho4 * 2 * math.pi * r5 * 1e-3 * RET['b'] * 1e-3 * 0.95); ct5 = rct / (r5 * 1e-3)
    alpha5 = math.degrees(math.atan2(ct5, cm5))
    cm6 = MA / (rho4 * 2 * math.pi * r6 * 1e-3 * RET['b'] * 1e-3 * 0.95)
    return dict(x_diffuser=x_dif, x_diaphragm=(x_dia0, x_rc0), x_channel=(x_rc0, x_rc1), r4=r4, bend_centre_x=xc,
                R_bend_out=R_out, R_bend_in=R_inn, inlet_bend_centre=(cx, cr), R_inlet_bend_in=RET['R_in'],
                R_inlet_bend_out=RET['R_in'] + RET['b'], r5=r5, r6=r6, alpha5=alpha5, alpha6=0.0, cm5=cm5, cm6=cm6,
                Zr=ST['C1']['Zr'], vane=RET['vane'],
                static_hub_end=(i2.xle - 7.0, i2.r1h + 2.0),             # static hub lip over the rotating nose (2 mm gap)
                nose_front=(i2.x0 - 2.0, i2.r1h + 2.0))                  # diaphragm face ahead of impeller 2


def rotor_constants(*names):
    """constants of the rotor stack (cad/engine/a1000_rotor.py) read from its source (no import: that module builds its
    own CAD when run with --cad)"""
    import ast
    tree = ast.parse(open(os.path.join(HERE, 'a1000_rotor.py')).read()); out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


# stage-1 radial inlet, shroud side [mm]: the channel is as wide as the inducer LE allows (the bend must turn axial ahead of
# x_le); the hub fairing's steep part (r 95-130) still leaves a 9 % area dip (min 0.91 of the inducer annulus, rotor side)
INLET = dict(x_shroud_wall=204.0, R_bend=10.0, r_entry=260.0, lip=12.0)


def inlet(imp):
    """stage-1 radial-to-axial inlet: hub side = the bearing-housing fairing of the rotor stack (INLET_HUB, a radial face
    at x 157 above it), shroud side = radial wall at x_shroud_wall, bend of radius R_bend into the inducer casing.
    Passage area along the hub line (normal distance to the shroud wall) against the inducer annulus"""
    hub = [tuple(q) for q in rotor_constants('INLET_HUB')['INLET_HUB']] + [(imp.x0, imp.r1h)]
    xs, R = INLET['x_shroud_wall'], INLET['R_bend']; rc = imp.r1t + imp.p['clr']; cx, cr = xs + R, rc + R
    arc = [(cx - R * math.cos(a), cr - R * math.sin(a)) for a in np.linspace(0, math.pi / 2, 16)]
    shroud = [(xs, INLET['r_entry'])] + arc + [(imp.xle, rc)]
    # area: distance from each hub point to the shroud polyline x 2 pi r_mean
    S = np.array(shroud); A1 = math.pi * (rc ** 2 - imp.r1h ** 2)
    seg = lambda p, a, b: np.linalg.norm(p - (a + np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0, 1) * (b - a)))
    stations = []
    for hp in [np.array(h) for h in hub] + [np.array((hub[0][0], r)) for r in (200.0, INLET['r_entry'])]:
        d = min(seg(hp, S[i], S[i + 1]) for i in range(len(S) - 1))
        stations.append(dict(x=float(hp[0]), r=float(hp[1]), width=d, area_ratio=2 * math.pi * (hp[1] + d / 2) * d / A1))
    A_entry = 2 * math.pi * INLET['r_entry'] * (xs - hub[0][0])
    return dict(hub=hub, shroud=shroud, x_hub_wall=hub[0][0], A1_mm2=A1, entry_area_ratio=A_entry / A1,
                min_area_ratio=min(q['area_ratio'] for q in stations), stations=stations, **INLET)


def report(imps, out):
    print('AURORA-1000 compressor @ %.0f rpm, air %.3f kg/s' % (N_RPM, MA))
    for k, s in out['stages'].items():
        g_, ind, th, pf, ml = s['geometry'], s['inducer'], s['throat'], s['performance'], s['meanline']
        im, di = pf['impeller'], pf['diffuser']
        print('%s (%s): r1h %.1f r1t %.1f (meanline %.1f / %.1f)  D2 %.1f  b2 %.2f  L_z/D2 %.3f  wrap %.1f deg  rake %.1f deg' % (
            s['name'], s['material'], g_['r1h'], g_['r1t'], ind['meanline_r1h'], ind['meanline_r1t'], 2 * g_['r2'], g_['b2'],
            g_['L_z_D2'], g_['wrap_deg'], g_['rake_deg']))
        print('   inducer: c1 %.1f m/s  flow angle hub/tip %.1f/%.1f  blade %.1f/%.1f  M1rel tip %.3f (meanline %.3f)' % (
            ind['c1'], ind['beta1_flow_hub'], ind['beta1_flow_tip'], ind['beta1_blade_hub'], ind['beta1_blade_tip'],
            ind['M1rel_tip'], ind['meanline_M1rel']))
        print('   throat: o %s mm, A_th %.0f cm2 (A1 %.0f), throat/capture %.3f, choke margin %.3f' % (
            '/'.join('%.1f' % v for v in th['o_mm'][::2]), th['A_throat_cm2'], th['A1_cm2'], th['throat_capture'], th['choke_margin']))
        print('   loading: Wss,max/W2 (shroud) %.2f, Wps min hub/shroud %.0f/%.0f m/s, min area ratio %.2f; twist main %.1f deg '
              '(dev R3 %.3f mm), splitter %.1f deg' % (s['loading']['Wss_max_W2_shroud'], s['loading']['Wps_min_hub'],
              s['loading']['Wps_min_shroud'], s['loading']['area_ratio_min'], s['twist']['main']['twist_max_deg'],
              s['twist']['main']['dev_R3_mm'], s['twist']['split']['twist_max_deg']))
        print('   impeller: slip %.4f (Z_eff %.1f, meanline %.4f)  dhE %.0f  dh0 %.0f J/kg  W1t/W2 %.2f  Df %.3f  eta_imp %.3f  '
              'M2 %.2f  alpha2 %.1f  phi2 %.3f' % (im['sigma'], im['Z_eff'], ml['sigma'], im['dhE'], im['dh0'], im['DR'], im['Df'],
              im['eta_imp'], im['M2'], im['alpha2'], im['phi2']))
        print('   losses [J/kg]: ' + ', '.join('%s %.0f' % (a, b) for a, b in im['losses'].items()))
        print('   diffuser Zd %d: r3 %.1f r4 %.1f b %.1f  alpha3 %.1f M3 %.2f  throat w %.1f M %.2f  AR %.2f  2theta %.1f  '
              'L/W1 %.1f  Cp %.2f (ideal %.2f)' % (di['Zd'], di['r3'], di['r4'], di['b3'], di['alpha3'], di['M3'], di['w_throat'],
              di['M_throat'], di['AR'], di['two_theta'], di['L_W1'], di['Cp'], di['Cp_ideal']))
        print('   STAGE: PR_tt %.3f (meanline %.3f)  eta_tt %.3f (meanline %.3f)  T02 %.1f C' % (
            pf['PR_tt'], ml['PR'], pf['eta_tt'], ml['eta'], pf['T02'] - 273.15))
    o = out['overall']
    print('overall to the collector flange: PR %.3f (meanline %.2f), eta %.3f (meanline %.3f), return channel dP0 %.2f %%, '
          'collector %.2f %%; cycle eta_el %.2f %% (meanline %.2f %%), net power per kg air x %.3f' % (
              o['PR'], o['meanline_PR'], o['eta'], o['meanline_eta'], 100 * o['return_channel_dP0'], 100 * o['collector_dP0'],
              100 * o['eta_el_detail'], 100 * o['eta_el_meanline'], o['P_net_ratio']))
    il = out['inlet']
    print('inlet (radial, hub = rotor fairing): channel x %.0f..%.0f, entry r %.0f (area %.2f x inducer), min area ratio along the '
          'bend %.2f' % (il['x_hub_wall'], il['x_shroud_wall'], il['r_entry'], il['entry_area_ratio'], il['min_area_ratio']))
    rc = out['return_channel']
    print('return channel: diffuser x %.1f..%.1f, diaphragm %.1f..%.1f, channel %.1f..%.1f, r5 %.0f -> r6 %.0f, alpha5 %.1f deg, '
          'cm5 %.0f cm6 %.0f m/s' % (*rc['x_diffuser'], *rc['x_diaphragm'], *rc['x_channel'], rc['r5'], rc['r6'], rc['alpha5'],
                                     rc['cm5'], rc['cm6']))


def plot(imps, out):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(16, 10), dpi=110)
    ax = fig.add_axes([0.04, 0.40, 0.45, 0.55])
    for k, imp in imps.items():
        hp = np.array(imp.hub_profile()); ax.fill(hp[:, 0], hp[:, 1], color='#9db7d6' if k == 'C1' else '#b9b2c8', ec='k', lw=0.6)
        ax.plot(imp.S[:, 0], imp.S[:, 1], 'k-', lw=1.0); cas = imp.casing(); ax.plot(cas[:, 0], cas[:, 1], 'k--', lw=0.6)
        for tt in np.linspace(0, 1, 11):
            i = int(tt * (imp.NT - 1)); ax.plot([imp.H[i, 0], imp.S[i, 0]], [imp.H[i, 1], imp.S[i, 1]], color='0.6', lw=0.5)
        i = int(imp.t_split * (imp.NT - 1)); ax.plot([imp.H[i, 0], imp.S[i, 0]], [imp.H[i, 1], imp.S[i, 1]], 'r-', lw=1.0)
        d = out['stages'][k]['performance']['diffuser']
        ax.add_patch(plt.Rectangle((imp.xs2, d['r3']), d['b3'], d['r4'] - d['r3'], fc='#e8c27a', ec='k', lw=0.5))
        ax.text(imp.xle, 15, '%s\n%s' % (imp.p['name'], imp.p['mat']), fontsize=8)
    rc = out['return_channel']
    ax.add_patch(plt.Rectangle((rc['x_channel'][0], rc['r6']), RET['b'], rc['r5'] - rc['r6'], fc='#cfe3c0', ec='k', lw=0.5))
    ax.set_aspect('equal'); ax.set_xlim(190, 530); ax.set_ylim(0, 380); ax.grid(alpha=0.3)
    ax.set_title('Meridional view (rotor frame, mm): hub, blade tip, casing (dashed), rulings, splitter LE (red), '
                 'vaned diffusers, return-channel vanes', fontsize=9)
    ax2 = fig.add_axes([0.55, 0.70, 0.42, 0.25])
    for k, imp in imps.items():
        ls = '-' if k == 'C1' else '--'
        ax2.plot(imp.u_h, np.degrees(imp.beta_h), 'b' + ls, label='%s hub' % k); ax2.plot(imp.u_s, np.degrees(imp.beta_s), 'r' + ls, label='%s shroud' % k)
        ax2.plot(imp.u_s, -np.degrees(imp.th_s), 'g' + ls, lw=0.8, label='%s wrap (deg)' % k)
    ax2.set_xlabel('meridional fraction'); ax2.set_ylabel('blade angle from meridional [deg]'); ax2.grid(alpha=0.3); ax2.legend(fontsize=7, ncol=3)
    ax3 = fig.add_axes([0.55, 0.40, 0.42, 0.25])
    for k, imp in imps.items():
        ls = '-' if k == 'C1' else '--'; pas = imp._pas
        for side, c in (('hub', 'b'), ('shroud', 'r')):
            r = pas['res'][side]; u = r['m'] / r['m'][-1]
            ax3.plot(u, r['Wss'], c + ls, lw=1.2, label='%s %s SS' % (k, side)); ax3.plot(u, r['Wps'], c + ls, lw=0.7, label='%s %s PS' % (k, side))
    ax3.set_xlabel('meridional fraction'); ax3.set_ylabel('relative velocity [m/s] (Stanitz)'); ax3.grid(alpha=0.3); ax3.legend(fontsize=6, ncol=4)
    ax4 = fig.add_axes([0.06, 0.06, 0.40, 0.27])
    names = list(out['stages']['C1']['performance']['impeller']['losses'])
    xx = np.arange(len(names))
    for j, k in enumerate(('C1', 'C2')):
        L = out['stages'][k]['performance']['impeller']['losses']
        dh = out['stages'][k]['performance']['impeller']['dh0']
        ax4.bar(xx + 0.4 * j, [100 * L[n] / dh for n in names], 0.4, label=k)
    ax4.set_xticks(xx + 0.2); ax4.set_xticklabels(names, rotation=20, fontsize=8); ax4.set_ylabel('% of stage work'); ax4.legend(); ax4.grid(alpha=0.3)
    ax4.set_title('Impeller losses (Oh et al. 1997 set)', fontsize=9)
    ax5 = fig.add_axes([0.55, 0.06, 0.42, 0.27]); ax5.axis('off')
    rows = []
    for k, s in out['stages'].items():
        pf = s['performance']
        rows.append([k, '%.3f / %.3f' % (pf['PR_tt'], s['meanline']['PR']), '%.3f / %.3f' % (pf['eta_tt'], s['meanline']['eta']),
                     '%.3f / %.3f' % (pf['impeller']['sigma'], s['meanline']['sigma']), '%.2f' % s['inducer']['M1rel_tip'],
                     '%.2f' % s['throat']['choke_margin'], '%d' % pf['diffuser']['Zd'], '%.1f' % pf['diffuser']['two_theta']])
    o = out['overall']
    rows.append(['all', '%.3f / %.2f' % (o['PR'], o['meanline_PR']), '%.3f / %.3f' % (o['eta'], o['meanline_eta']), '', '', '', '', ''])
    tb = ax5.table(cellText=rows, colLabels=['stage', 'PR tt (1-D / meanline)', 'eta tt', 'slip', 'M1rel', 'choke', 'Zd', '2theta'],
                   loc='center'); tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1, 1.6)
    fig.suptitle('AURORA-1000 compressor impellers: ruled (flank-milled) blades, 13 + 13, 40 deg backsweep, 15,000 rpm', fontsize=12)
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_impeller_design.png')); print('written docs/img/a1000_impeller_design.png')


if __name__ == '__main__' and '--cad' not in sys.argv and '--sector' not in sys.argv and '--quiet' not in sys.argv:
    _imps, _out = design()
    report(_imps, _out)
    plot(_imps, _out)


# ================================================================================================ CAD (FreeCAD)
FILLET = dict(C1=5.0, C2=4.0)                   # blade root fillet = ball radius of the tapered flank-milling cutter [mm]
EXT_LO, EXT_HI = 4.0, 3.0                       # ruling extension below the hub / above the blade tip before trimming [mm]


def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def _curve(P, prm):
    App, Part, V = _fc()
    c = Part.BSplineCurve(); c.interpolate([V(*map(float, p)) for p in P], Parameters=[float(u) for u in prm]); return c


def _params(*curves):
    """common interpolation parameters of corresponding point lists (mean chord length): every curve of a blade gets the
    same knot vector, so the ruled surfaces can be built pole by pole"""
    d = np.mean([np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))] for c in curves], axis=0)
    return d / d[-1]


def _ruled(c1, c2):
    """ruled face between two B-spline curves with the same degree and knots: straight lines c1(u) -> c2(u) exactly by
    parameter (Part.makeRuledSurface re-parametrises, and its rulings drifted until the two blade sides crossed)"""
    App, Part, V = _fc()
    s = Part.BSplineSurface()
    s.buildFromPolesMultsKnots([[p, q] for p, q in zip(c1.getPoles(), c2.getPoles())], c1.getMultiplicities(), [2, 2],
                               c1.getKnots(), [0.0, 1.0], False, False, c1.Degree, 1)
    return s.toShape()


def _closed_solid(groups):
    """solid from groups of sections; a section = (suction half, pressure half) as (n, 3) Cartesian arrays running from the
    LE nose to the TE tip point, the last section of a group = the first of the next. One B-spline curve per section half
    (common knots for all), ruled faces between consecutive sections (each group must have two sections) and ruled end
    caps between the two halves; sewn: the end wires are not planar, a solid loft cannot cap them"""
    App, Part, V = _fc()
    secs = [groups[0][0]] + [s_ for g in groups for s_ in g[1:]]
    prm = _params(*[s_[k] for s_ in secs for k in (0, 1)])
    C = [[_curve(s_[k], prm) for k in (0, 1)] for s_ in secs]
    faces = [_ruled(C[i][k], C[i + 1][k]) for i in range(len(secs) - 1) for k in (0, 1)]
    faces += [_ruled(C[i][0], C[i][1]) for i in (0, len(secs) - 1)]
    sh = Part.Shell(faces); sh.sewShape()
    so = Part.Solid(sh if sh.ShapeType == 'Shell' else Part.Shell(sh.Faces))
    if so.Volume < 0: so.reverse()
    if not so.isValid():                                           # (the caps' nose / TE edges are degenerate: no isClosed)
        raise RuntimeError('blade solid invalid')
    return so


def _rev_wire(edges_or_pts, angle=360.0):
    """solid of revolution about x of a closed meridional (x, r) outline given as a list of items: (x, r) points (joined
    by lines) or ('bez', poles) Bezier curves"""
    App, Part, V = _fc()
    es, cur = [], None
    for it in edges_or_pts:
        if isinstance(it, tuple) and it and it[0] == 'bez':
            P = [V(float(x), float(r), 0) for x, r in it[1]]
            if cur is not None and (cur - P[0]).Length > 1e-9: es.append(Part.LineSegment(cur, P[0]).toShape())
            b = Part.BezierCurve(); b.setPoles(P); es.append(b.toShape()); cur = P[-1]
        else:
            p = V(float(it[0]), float(it[1]), 0)
            if cur is not None and (cur - p).Length > 1e-9: es.append(Part.LineSegment(cur, p).toShape())
            if cur is None: first = p
            cur = p
    if (cur - first).Length > 1e-9: es.append(Part.LineSegment(cur, first).toShape())
    f = Part.Face(Part.Wire(Part.__sortEdges__(es)))
    return f.revolve(V(0, 0, 0), V(1, 0, 0), angle)


def fc_hub(imp):
    """turned hub: nose (edge break), hub flow line (quartic Bezier), tip band at r2, back face (flat or recessed), bore"""
    p = imp.p; rb = p['r_bore']; ch = 0.5; xb = imp.x0 + imp.L     # nose edge break 0.5: flush with the stub / spacer (r1h)
    return _rev_wire([(imp.x0, rb), (imp.x0, imp.r1h - ch), (imp.x0 + ch, imp.r1h), ('bez', imp.Ph.tolist()),
                      (xb - 1.0, imp.r2)] + [tuple(map(float, q)) for q in imp.back_face()])


def fc_trim(imp):
    """region of the blades: below the blade-tip line (shroud Bezier), r <= r2, ahead of the back face"""
    xb = imp.x0 + imp.L
    return _rev_wire([(imp.x0 + 0.2, 5.0), (imp.x0 + 0.2, imp.r1t), (imp.xle, imp.r1t), ('bez', imp.Ps.tolist()),
                      (xb + 5.0, imp.r2), (xb + 5.0, 5.0)])


def fc_blade(imp, name, hub_h, shr_h, R):
    """blade piece: ruled from the top of the root fillet (height R along the rulings) to above the tip (both sides straight
    lines hub -> tip, 5-axis flank milling), root fillet below (loft through sections offset by R - sqrt(R^2 - (R - h)^2)
    at height h, the ball of the cutter), trimmed to the blade-tip line and r2, minus the hub"""
    t0 = 0.0 if name == 'main' else imp.t_split; sh = 0.0 if name == 'main' else math.pi / Z_MAIN
    n_side = len(hub_h[0]) - 18
    def at(v_mm, hh, ss):                                          # points v_mm along each ruling from the hub point
        return [hh[k] + v_mm * (ss[k] - hh[k]) / np.linalg.norm(ss[k] - hh[k], axis=1)[:, None] for k in (0, 1)]
    def thick_outline(dl):                                         # hub / shroud outlines offset outward by dl
        return ([imp.cart(q) for q in imp.outline('hub', t0, theta_shift=sh, n_side=n_side, dl=dl)],
                [imp.cart(q) for q in imp.outline('shroud', t0, theta_shift=sh, n_side=n_side, dl=dl)])
    Hc, Sc = [imp.cart(h) for h in hub_h], [imp.cart(s) for s in shr_h]
    # fillet as ruled bands between offset sections (a single B-spline loft through them gave solids OCC rejects); no section
    # exactly on the hub surface (an edge lying in the hub face made the hub cut return nothing)
    fillet = []
    for h in [-EXT_LO, -0.4] + [R * (1 - math.cos(a)) for a in np.linspace(0.12, math.pi / 2 * 0.97, 9)]:
        dl = R if h <= 0 else R - math.sqrt(max(R * R - (R - h) ** 2, 0.0))
        hh, ss = thick_outline(dl); fillet.append(at(h, hh, ss))
    sec_R = at(R, Hc, Sc); fillet.append(sec_R)
    top = [Sc[k] + EXT_HI * (Sc[k] - Hc[k]) / np.linalg.norm(Sc[k] - Hc[k], axis=1)[:, None] for k in (0, 1)]
    b = _closed_solid([[a_, b_] for a_, b_ in zip(fillet[:-1], fillet[1:])] + [[sec_R, top]])
    b = b.common(fc_trim(imp)).cut(fc_hub(imp))
    if b.Volume <= 0 or not b.isValid() or len(b.Solids) != 1:
        raise RuntimeError('%s %s blade piece invalid (vol %.1f, solids %d)' % (imp.key, name, b.Volume, len(b.Solids)))
    return b.Solids[0]


def build_cad(full=False):
    App, Part, V = _fc()
    os.makedirs(OUT, exist_ok=True)
    imps = {k: Impeller(k) for k in ST}
    info = {}
    def save(name, s, rho):
        s.exportStep(os.path.join(OUT, name + '.step')); s.exportBrep(os.path.join(OUT, name + '.brep'))
        info[name] = dict(valid=s.isValid(), solids=len(s.Solids), vol_mm3=s.Volume, mass_kg=s.Volume * rho * 1e-9, rho=rho,
                          bbox=[s.BoundBox.XMin, s.BoundBox.XMax, s.BoundBox.YMin, s.BoundBox.YMax, s.BoundBox.ZMin, s.BoundBox.ZMax])
        print('%-22s valid %s solids %d  vol %.0f cm3  mass %.3f kg' % (name, s.isValid(), len(s.Solids), s.Volume / 1e3,
                                                                       s.Volume * rho * 1e-9), flush=True)
    for k, imp in imps.items():
        rho = imp.p['rho']; R = FILLET[k]
        hub = curvics(k, fc_hub(imp)); save('A1000_%s_hub' % k, hub, rho)
        bl = imp.blades()
        pieces = {}
        for nm, tag in (('main', 'blade'), ('split', 'splitter')):
            pc = fc_blade(imp, nm, bl[nm][0], bl[nm][1], R); pieces[nm] = pc
            save('A1000_%s_%s' % (k, tag), pc, rho)
        # rotor lump for the rotor dynamics: hub + 13 blades + 13 splitters (13-fold pattern: transverse inertia isotropic)
        tot_m = 0.0; mx = 0.0; Ip = 0.0; parts = [(hub, 1)] + [(pieces[n], Z_MAIN) for n in pieces]
        for s_, n in parts:
            m = s_.Volume * 1e-9 * rho; tot_m += n * m; mx += n * m * s_.CenterOfMass.x
        xcg = mx / tot_m; Id = 0.0
        for s_, n in parts:
            m = s_.Volume * 1e-9 * rho; c = s_.CenterOfMass; M = s_.MatrixOfInertia; f = rho * 1e-9 * 1e-6   # mm^5 -> kg m2
            Ixx = M.A11 * f + m * (c.y ** 2 + c.z ** 2) * 1e-6
            Iyy = M.A22 * f + m * ((c.x - xcg) ** 2 + c.z ** 2) * 1e-6; Izz = M.A33 * f + m * ((c.x - xcg) ** 2 + c.y ** 2) * 1e-6
            Ip += n * Ixx; Id += n * 0.5 * (Iyy + Izz)
        info['A1000_%s_rotor' % k] = dict(m=tot_m, x_cg=xcg, Ip=Ip, Id=Id, x0=imp.x0, L=imp.L, r2=imp.r2)
        print('%s impeller: %.2f kg, x_cg %.1f mm, Ip %.4f, Id %.4f kg m2' % (k, tot_m, xcg, Ip, Id), flush=True)
        if full:
            w = hub
            for nm, sh0 in (('main', 0.0), ('split', 0.0)):
                w = w.fuse([GG_rot(pieces[nm], 360.0 * j / Z_MAIN) for j in range(Z_MAIN)])
            save('A1000_%s_impeller' % k, w.removeSplitter(), rho)
    json.dump(info, open(os.path.join(OUT, 'A1000_C_parts.json'), 'w'), indent=1, default=float)


# curvic couplings on the hub faces: (rotor-stack band, face, side of the impeller, tooth height, phase); the rotor parts
# (cad/engine/a1000_rotor.py) carry the other half with the opposite side and phase, so the teeth mesh
CURVIC_FACES = dict(C1=[('stub_I1', 'front', +1, 2.4, 0.5), ('I1_spc', 'rear', -1, 3.0, 0.0)],
                    C2=[('spc_I2', 'front', +1, 2.6, 0.5), ('I2_drum', 'rear', -1, 3.2, 0.0)])


def curvics(key, hub):
    _a = list(sys.argv); sys.argv = [sys.argv[0]]                   # (a1000_rotor builds its own CAD with --cad)
    if HERE not in sys.path: sys.path.insert(0, HERE)
    import a1000_rotor as RT
    sys.argv = _a
    imp = Impeller(key)
    for band, face, side, h, phase in CURVIC_FACES[key]:
        c = RT.CURVIC_C[band]; xj = imp.x0 if face == 'front' else imp.x0 + imp.L
        hub = RT.curvic_face(hub, xj, side, c['ri'], c['ro'], c['N'], h, phase)
    hub = hub.removeSplitter()
    return hub.Solids[0] if len(hub.Solids) == 1 else hub


def GG_rot(sh, deg):
    App, Part, V = _fc(); q = sh.copy(); q.rotate(V(0, 0, 0), V(1, 0, 0), deg); return q


# ------------------------------------------------------------------------------------------------ cyclic sector (FEA)
PITCH = 2 * math.pi / Z_MAIN


class CutSurface:
    """sector boundary theta_cut(x, r) through the hub body: on the hub surface mid-way between the splitter of the
    previous pitch and the main blade (theta_hub_camber(t) - pi / 26); inside the body the value of the hub point on the
    same ray from a pivot outside the body (behind the back face, below the bore), so the surface never touches a blade"""
    def __init__(self, imp):
        self.imp = imp
        self.pv = np.array([imp.x0 + imp.L + 40.0, imp.p['r_bore'] - 40.0])
        d = imp.H - self.pv; self.phi = np.arctan2(d[:, 1], d[:, 0])
        if not np.all(np.diff(self.phi) < 0): raise RuntimeError('cut-surface fan not monotonic')
        self.thc = imp.th_h - math.pi / (2 * Z_MAIN)

    def theta(self, x, r):
        phi = np.arctan2(np.asarray(r) - self.pv[1], np.asarray(x) - self.pv[0])
        return np.interp(-phi, -self.phi, self.thc)              # clamped: nose side t = 0, back side t = 1


def build_sector(key):
    """1/13 cyclic sector: hub between the two warped cut surfaces + main blade + splitter (no blade is cut)"""
    App, Part, V = _fc()
    imp = Impeller(key); cs = CutSurface(imp)
    hub = Part.Shape(); hub.read(os.path.join(OUT, 'A1000_%s_hub.brep' % key))
    bl = Part.Shape(); bl.read(os.path.join(OUT, 'A1000_%s_blade.brep' % key))
    sp = Part.Shape(); sp.read(os.path.join(OUT, 'A1000_%s_splitter.brep' % key))
    v_exp = hub.Volume / Z_MAIN + bl.Volume + sp.Volume
    xa, xb = imp.x0 - 3.0, imp.x0 + imp.L + 3.0; ra, rb = imp.p['r_bore'] - 3.0, imp.r2 + 15.0
    xs = np.linspace(xa, xb, 48); rs = np.linspace(ra, rb, 40)
    grid = [[V(x, r * math.cos(cs.theta(x, r)), r * math.sin(cs.theta(x, r))) for r in rs] for x in xs]
    su = Part.BSplineSurface(); su.interpolate(grid)
    fL = su.toShape(); fR = fL.copy(); fR.rotate(V(0, 0, 0), V(1, 0, 0), math.degrees(PITCH))
    side = [Part.makeRuledSurface(eL, eR) for eL, eR in zip(fL.Edges, fR.Edges)]
    sh = Part.Shell([fL, fR] + side); sh.sewShape()
    W = Part.Solid(sh if sh.ShapeType == 'Shell' else Part.Shell(sh.Faces))
    if W.Volume < 0: W.reverse()
    print('%s wedge: valid %s, vol %.0f cm3 (1/13 annulus %.0f)' % (key, W.isValid(), W.Volume / 1e3,
          math.pi * (rb ** 2 - ra ** 2) * (xb - xa) / Z_MAIN / 1e3), flush=True)
    hs = hub.common(W)
    sec = hs.fuse([bl, sp]).removeSplitter()
    sols = [q for q in sec.Solids if abs(q.Volume) > 1.0]
    print('%s sector: solids %d, vol %.0f mm3 (expected %.0f), valid %s' % (key, len(sols), sum(abs(q.Volume) for q in sols),
          v_exp, sec.isValid()), flush=True)
    if len(sols) != 1 or abs(sols[0].Volume - v_exp) > 0.01 * v_exp: raise SystemExit('sector check failed')
    sols[0].exportStep(os.path.join(OUT, 'A1000_%s_sector.step' % key))
    json.dump(dict(key=key, Z=Z_MAIN, pitch_deg=math.degrees(PITCH), pivot=cs.pv.tolist(), phi=cs.phi.tolist(),
                   theta_cut=cs.thc.tolist(), vol_mm3=sols[0].Volume, r_bore=imp.p['r_bore'], x0=imp.x0, L=imp.L, r2=imp.r2,
                   rho=imp.p['rho']),
              open(os.path.join(OUT, 'A1000_%s_sector.json' % key), 'w'), indent=1)


if '--cad' in sys.argv:
    build_cad(full='--full' in sys.argv)
if '--sector' in sys.argv:
    for k_ in [a for a in sys.argv if a in ST] or list(ST):
        build_sector(k_)
