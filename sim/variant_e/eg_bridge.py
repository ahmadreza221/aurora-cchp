# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""GR180 version E - generator + 6-pulse diode bridge + DC link held by the AFE: time-domain circuit model (library used by
sim/variant_e/eg_em.py; run alone for a quick check).

Circuit (per phase, star point floating): e_x(t) - R i_x - L_s di_x/dt = v_x - v_n ; terminals a, b, c -> 6 diodes
(smooth piecewise-linear: V_f 1.0 V, r_on 1 mOhm) -> DC+ / DC- -> optional DC choke L_dc, R_dc -> ideal DC source V_dc (the
AFE regulates the DC link; its capacitor is stiff at the bridge time scale).  Backward Euler, Newton per step on the 9
unknowns [i_a, i_b, i_c, i_dc, v_a, v_b, v_c, v_n, v_p] (v_m = 0).  EMF from the FEM (pure sine for the ring magnet; a
harmonic list can be given).  Outputs per run: mean DC current / power, phase current rms + harmonics, EMF power, torque
ripple, commutation overlap.
"""
import math
import numpy as np

VF, RON, GOFF, SMOOTH = 1.0, 1.0e-3, 1.0e-7, 0.02


def g(v):
    """smooth diode current and conductance"""
    z = (v - VF) / SMOOTH
    sp = np.where(z > 30, z, np.log1p(np.exp(np.minimum(z, 30))))
    sg = 1.0 / (1.0 + np.exp(-np.clip(z, -60, 60)))
    return SMOOTH * sp / RON + GOFF * v, sg / RON + GOFF


def simulate(E_ll, f, L_s, R, V_dc, L_dc=0.0, R_dc=0.0, periods=40, steps=900, harm=None, i0=None, record=True):
    """E_ll: rms line-line EMF (V) at frequency f (Hz); harm: {h: (rel amplitude, phase rad)} EMF harmonics"""
    w = 2 * math.pi * f
    T = 1.0 / f; dt = T / steps
    Epk = E_ll * math.sqrt(2.0 / 3.0)
    Ld = max(L_dc, 1e-7)
    x = np.zeros(9)
    if i0 is not None:
        x[:4] = i0
    ph = np.array([0.0, -2 * math.pi / 3, 2 * math.pi / 3])
    nsteps = periods * steps
    keep = steps if record else 0
    rec = np.zeros((keep, 8)) if record else None
    for n in range(nsteps):
        t = (n + 1) * dt
        e = Epk * np.cos(w * t + ph)
        if harm:
            for h, (a, p) in harm.items():
                e = e + Epk * a * np.cos(h * (w * t + ph) + p)
        xo = x.copy()
        for it in range(25):
            ia, ib, ic, idc, va, vb, vc, vn, vp = x
            iv = np.array([ia, ib, ic]); vv = np.array([va, vb, vc])
            gp, dgp = g(vv - vp)          # top diodes x -> p
            gm, dgm = g(-vv)              # bottom diodes m -> x
            F = np.zeros(9); Jm = np.zeros((9, 9))
            for k in range(3):
                F[k] = L_s / dt * (iv[k] - xo[k]) + R * iv[k] - e[k] + (vv[k] - vn)
                Jm[k, k] = L_s / dt + R; Jm[k, 4 + k] = 1.0; Jm[k, 7] = -1.0
            F[3] = Ld / dt * (idc - xo[3]) + R_dc * idc - vp + V_dc
            Jm[3, 3] = Ld / dt + R_dc; Jm[3, 8] = -1.0
            for k in range(3):
                F[4 + k] = iv[k] - gp[k] + gm[k]
                Jm[4 + k, k] = 1.0; Jm[4 + k, 4 + k] = -dgp[k] - dgm[k]; Jm[4 + k, 8] = dgp[k]
            F[7] = gp.sum() - idc
            Jm[7, 4:7] = dgp; Jm[7, 8] = -dgp.sum(); Jm[7, 3] = -1.0
            F[8] = iv.sum(); Jm[8, 0:3] = 1.0
            dx = np.linalg.solve(Jm, -F)
            # limit voltage steps for robustness
            dx[4:] = np.clip(dx[4:], -50.0, 50.0)
            x = x + dx
            if np.max(np.abs(dx[:4])) < 1e-6 and np.max(np.abs(dx[4:])) < 1e-6:
                break
        if record and n >= nsteps - keep:
            rec[n - (nsteps - keep)] = [t, x[0], x[1], x[2], x[3], e[0], e[1], e[2]]
    return rec, x


def analyse(rec, f, V_dc, R):
    t, ia, ib, ic, idc = rec[:, 0], rec[:, 1], rec[:, 2], rec[:, 3], rec[:, 4]
    ea, eb, ec = rec[:, 5], rec[:, 6], rec[:, 7]
    n = len(t)
    Idc = idc.mean()
    p_em = ea * ia + eb * ib + ec * ic
    w = 2 * math.pi * f
    Fa = np.fft.rfft(ia) / n * 2
    I1 = abs(Fa[1]) / math.sqrt(2)
    Irms = math.sqrt(np.mean(ia ** 2))
    harm = {h: round(float(abs(Fa[h]) / abs(Fa[1])), 4) for h in (5, 7, 11, 13, 17, 19, 23, 25) if h < len(Fa)}
    Te = p_em / w
    Ft = np.fft.rfft(Te) / n * 2
    # displacement: angle between EMF a and current a fundamental
    Fe = np.fft.rfft(ea) / n * 2
    phi = math.degrees(np.angle(Fa[1]) - np.angle(Fe[1]))
    # conduction: fraction of the period with |i_a| > 1 % of peak
    cond = float(np.mean(np.abs(ia) > 0.01 * np.max(np.abs(ia))))
    return dict(V_dc=V_dc, I_dc=float(Idc), P_dc_kW=float(V_dc * Idc / 1e3), P_em_kW=float(p_em.mean() / 1e3), I_rms=Irms, I1_rms=I1,
                harmonics=harm, thd_pct=float(100 * math.sqrt(sum(v * v for v in harm.values()))), disp_deg=phi % 360 if phi % 360 < 180 else phi % 360 - 360,
                torque_mean=float(Te.mean()), torque_ripple_6f_pct=float(100 * abs(Ft[6]) / Te.mean()) if Te.mean() > 1 else 0.0,
                torque_pp_pct=float(100 * (Te.max() - Te.min()) / Te.mean()) if Te.mean() > 1 else 0.0, conduction_frac=cond,
                P_cu_W=float(3 * Irms ** 2 * R))


def run_point(E_ll, f, L_s, R, V_dc, L_dc=0.0, R_dc=0.0, i0=None, periods=40, steps=900):
    rec, x = simulate(E_ll, f, L_s, R, V_dc, L_dc, R_dc, periods=periods, steps=steps, i0=i0)
    a = analyse(rec, f, V_dc, R)
    return a, x


def vdc_for_power(P_kW, E_ll, f, L_s, R, L_dc=0.0, R_dc=0.0, lo=None, hi=None, tol_kW=0.5):
    """bisection on V_dc for a DC power P_kW (power falls with V_dc)"""
    lo = lo or 0.80 * 1.35 * E_ll * 0.6
    hi = hi or math.sqrt(2) * E_ll - 2.0
    x0 = None
    res = None
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        a, x0 = run_point(E_ll, f, L_s, R, mid, L_dc, R_dc, i0=None, periods=30)
        res = a
        if a['P_dc_kW'] > P_kW:
            lo = mid
        else:
            hi = mid
        if abs(a['P_dc_kW'] - P_kW) < tol_kW:
            break
    return res


if __name__ == '__main__':
    a, _ = run_point(610.0, 583.33, 110e-6, 2.2e-3, 690.0)
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items()})
