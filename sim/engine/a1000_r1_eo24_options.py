#!/usr/bin/env python3
"""AURORA-1000 R1 blisk, EO24 (NGV2 potential field) on ND24 F1 (flap, 4,908 Hz at 15,000 rpm): the start-up crossing at
~12,270 rpm (docs/08 sec. 12.4.1). Comparison of four fixes with numbers:

1. Accept the crossing on the start line: forcing from the 2-D URANS at the start-line state of the crossing (CFD variant
   'st' of sim/cfd/a1000_r1_forcing/make_case.py, state from sim/engine/a1000_startup.py), transient passage through the
   resonance at the acceleration rate (envelope equation of the modal oscillator under a linear frequency sweep), the
   crossing speed band from the blade metal temperature (E(T)), HCF at the start-up state (cold blade: Goodman intercept
   = UTS, mean stress ~ N^2; Basquin / Miner over the cycles of 10,000 starts, accel + decel), LCF interaction.
2. NGV2 vane count (NGV1 = 48 kept): sim/engine/a1000_vane_count.py --n1 48 with the start-up crossings of the R1 flap
   families; the forcing of a count N2 scaled from the CFD by the potential-field decay exp(-k g) with k ~ 2 pi / s and the
   start-line dynamic head at its crossing speed.
3. Friction damping (under-platform damper, ring damper in the rim): the damping needed, against what the ND24 F1 mode
   offers to a damper at the rim / platform (modal strain and kinetic energy fractions from the cyclic mode,
   sim/engine/fea/a1000_R1_modes.npz) and the frequency-shift bound of a friction contact.
4. Larger R1 - NGV2 axial gap: forcing from the CFD variant 'st_g20' (+20 mm) against 'st' -> decay rate, gap needed.
Criterion as in a1000_r1_forced_response.py: resonant root stress x1.5 mistuning at the lower-bound damping (0.05 % +
half the piston aero damping) <= allowable / 2; the allowable is the Goodman amplitude at the state where the resonance
is met (design point: 31.6 MPa; start-up: cold blade, below).
Rev 6: option 4 (+25 mm) is in the CAD (a1000_turbine.DGAP2). The options stay compared at the rev 5 gap (9 mm at the hub);
the start-line crossings of the check sheet (orders_start) use the start-line CFD at the CAD gap (variant st_g25, the CAD
annulus), which is also compared with the decay-rate prediction of option 4.
Run:    python sim/engine/a1000_r1_eo24_options.py   (needs fea/a1000_R1_modes.npz, the CFD forcing files of the variants)
Writes: sim/engine/fea/a1000_R1_eo24_options.json, docs/img/a1000_R1_eo24_options.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import a1000_r1_forced_response as FR                         # noqa: E402  (modes, blade faces, modal response)
import a1000_startup as SU                                     # noqa: E402  (start-line matching)
from a1000_disc_fea import MAT_T, MAT_E                       # noqa: E402

FEA = FR.FEA
CFD = os.path.dirname(FR.FORCING)
EO, ND, FAM = 24, 24, 1
N_OP = 15000.0
STARTS = 10000
T_BLADE_DES = 870.0                                            # C, R1 metal temperature of the cyclic modes
ZETA = FR.ZETA
MISTUNE = FR.MISTUNE
# HCF of cast MAR-M247 (a1000_turbine_checks SIG_E: Smid et al. 2016, 2e7 cycles, R = -1, x0.8 cast surface)
HCF_T = np.array([20., 650., 800., 900.]); HCF_S = 0.8 * np.array([190., 190., 220., 200.])   # 650 C value below 650 C
UTS_T = np.array([20., 400., 600., 800., 900., 1000.]); UTS = np.array([965., 980., 1000., 900., 724., 550.])
N_E, M_BASQ = 2e7, 11.0                                        # Basquin: N = N_E (s_e / s_a)^M below the 2e7 strength
ACCEL_NOM = 150.0                                              # rpm/s, start schedule 60 -> 100 % in ~40 s
ACCEL_FAST = (500.0, 1000.0, 1500.0)                           # rpm/s, fast unloaded acceleration through the band
TIT_START = 650.0 + 273.15                                     # K, start-line TIT of the CFD state
K_CF = 0.996                                                   # less centrifugal stiffening at ~82 % speed (blade FEA: F1
                                                               # 5,186 Hz at 15,000 rpm, 5,165 Hz at 12,270 rpm)
# recommendation (option 4): the extra gap that passes the start-up limit at the lower-bound damping AND the design-point
# limit (hot blade, creep-rupture Goodman) at the upper-bound damping, rounded up to 5 mm
GAP_ROUND = 5.0


# ------------------------------------------------------------------------------------------------ helpers
def E_of(T): return float(np.interp(T, MAT_T, MAT_E))


def sweep_peak(zeta, a, n_eval=1):
    """modal oscillator x'' + 2 zeta x' + x = cos(psi), psi' = 1 + a tau (frequency swept through resonance at the
    dimensionless rate a = d(Omega)/dt / w_n^2): envelope equation 2 i W A' + (1 - W^2 + 2 i zeta W) A = 1 (slowly varying
    amplitude, light damping). Returns (peak |A| x 2 zeta, i.e. relative to the steady resonance; cycles with |A| above
    50 % / 90 % of the steady resonant amplitude; cycles with |A| above 50 % of the transient peak)"""
    span = 40 * zeta + 8 * math.sqrt(a)                         # frequency window around the resonance
    t0, t1 = -span / a, span / a
    h = min(0.05 / max(zeta, math.sqrt(a)), 0.2 / span)
    n = int((t1 - t0) / h) + 1; h = (t1 - t0) / n
    W0 = 1 + a * t0; A = 1 / (1 - W0 * W0 + 2j * zeta * W0)     # quasi-steady start
    def f(t, A):
        W = 1 + a * t; return (1 - (1 - W * W + 2j * zeta * W) * A) / (2j * W)
    amp = np.empty(n + 1); amp[0] = abs(A); t = t0
    for i in range(n):
        k1 = f(t, A); k2 = f(t + h / 2, A + h / 2 * k1); k3 = f(t + h / 2, A + h / 2 * k2); k4 = f(t + h, A + h * k3)
        A += h / 6 * (k1 + 2 * k2 + 2 * k3 + k4); t += h; amp[i + 1] = abs(A)
    res = 1 / (2 * zeta); pk = amp.max()
    cyc = lambda thr: float(np.sum(amp >= thr) * h / (2 * math.pi))
    return pk / res, cyc(0.5 * res), cyc(0.9 * res), cyc(0.5 * pk), amp / res, h


def goodman_start(T_metal, s_mean):
    """Goodman amplitude [MPa] at a short transient: HCF strength at the metal temperature, mean-stress intercept UTS"""
    return float(np.interp(T_metal, HCF_T, HCF_S)) * max(0.0, 1 - s_mean / float(np.interp(T_metal, UTS_T, UTS)))


def miner(cyc_amp, s_e):
    """damage of the cycles (list of (n, amplitude MPa)) on the Basquin line through (N_E, s_e), no endurance limit"""
    return sum(n / (N_E * (s_e / s) ** M_BASQ) for n, s in cyc_amp if s > 0)


# ------------------------------------------------------------------------------------------------ modal forcing (CFD)
class Modal:
    def __init__(self):
        self.A = FR._turbine()
        d = dict(np.load(FR.NPZ)); xyz = d['xyz']
        r = np.hypot(xyz[:, 1], xyz[:, 2]); rh = np.array([self.A.r_hub(x) for x in xyz[:, 0]])
        hx = np.array([self.A.height(x) for x in xyz[:, 0]])
        blade = np.where(r > rh + 0.05)[0]; d['blade_nodes'] = blade
        self.root = (r[blade] - rh[blade]) < FR.ROOT_BAND * hx[blade]
        class _D(dict):
            files = property(lambda s: list(s.keys()))
        self.d = _D(d); self.bf = FR.blade_faces(self.d, self.A); self.r, self.rh = r, rh
        k = [q for q in d['keep'] if int(q[0]) == ND][0]; self.f_mode = float(k[2])

    def eo24(self, forcing_file, scale=1.0):
        return self.order(forcing_file, EO, ND, scale)

    def order(self, forcing_file, eo, nd, scale=1.0):
        """root vibratory stress per 1 / (2 zeta) [MPa] and the piston aero damping of the EO24 harmonic of a CFD forcing
        file, with the meanline flow correction kq of a1000_r1_forced_response (mass flow ratio squared)"""
        fc = json.load(open(forcing_file))
        kq = max(1.0, (fc['flow']['mdot_meanline'] / fc['flow']['mdot_annulus_equiv']) ** 2) * scale
        h = fc['harmonics'][str(eo)]; tau_c = np.array(fc['tau']); o = np.argsort(tau_c)
        pr, pi_ = np.array(h['re'])[o] * 1e-6 * kq, np.array(h['im'])[o] * 1e-6 * kq
        tt = np.r_[tau_c[o] - 1, tau_c[o], tau_c[o] + 1]
        p_hat = lambda t: np.interp(t, tt, np.r_[pr, pr, pr]) + 1j * np.interp(t, tt, np.r_[pi_, pi_, pi_])
        rho_a = fc['rho_a_mid'] * 1e-9
        fm = float([q for q in self.d['keep'] if int(q[0]) == nd][0][2])
        R = FR.response(self.d, self.bf, nd, -1 if (eo % FR.Z) < FR.Z / 2 else 1, p_hat, fm, rho_a)
        vm1 = R['vm1']; i_rt = int(np.argmax(np.where(self.root, vm1, 0)))
        return dict(root1=float(vm1[i_rt]), zeta_aero=float(R['zeta_aero']), kq=kq, f_mode=fm, Q=float(abs(R['Q'])), q1=float(R['q1']),
                    p_rms_kPa=float(np.sqrt(np.mean(pr ** 2 + pi_ ** 2) / 2) * 1e3), U=R['U'], fc=fc)

    def energy_fractions(self, U):
        """kinetic-energy (|U|^2 mass weighted, lumped per node by the element volumes) fractions of the mode: airfoil,
        platform + rim (within 15 mm below the hub line), disc below"""
        xyz, conn = self.d['xyz'], self.d['conn']
        p = xyz[conn[:, :4]]
        V = np.abs(np.einsum('ij,ij->i', np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), p[:, 3] - p[:, 0])) / 6.0
        w = np.zeros(len(xyz)); np.add.at(w, conn.ravel(), np.repeat(V / 10, 10))
        ke = w * np.sum(np.abs(U) ** 2, 1); dr = self.r - self.rh
        out = dict(airfoil=float(ke[dr > 0.05].sum()), rim=float(ke[(dr <= 0.05) & (dr > -15)].sum()),
                   disc=float(ke[dr <= -15].sum()))
        tot = sum(out.values()); return {k: v / tot for k, v in out.items()}, float(np.abs(U)[(dr <= 0.05) & (dr > -15)].max()), float(np.abs(U).max())


# ------------------------------------------------------------------------------------------------ main
def main():
    out = dict(eo=EO, nd=ND, family=FAM, starts=STARTS, mistune=MISTUNE, zeta=list(ZETA))
    base = json.load(open(os.path.join(FEA, 'a1000_R1_forced_response.json')))['orders'][str(EO)]
    chk = json.load(open(os.path.join(FEA, 'a1000_turbine_checks.json')))['blades']['R1']
    g_des = chk['goodman_allow_root']; s_root_des = chk['sigma_root']
    M = Modal(); fm = M.f_mode; out['f_mode'] = fm; out['goodman_design'] = g_des
    print('ND%d F%d %.0f Hz (15,000 rpm, blade %.0f C); design-point Goodman %.1f MPa (root mean %.0f MPa)' % (
        ND, FAM, fm, T_BLADE_DES, g_des, s_root_des), flush=True)

    # ---- forcing: design (existing CFD), start line (variant st), start line + 20 mm gap (st_g20)
    des = M.eo24(FR.FORCING)
    var = {}
    g_cad = M.A.DGAP2; tag_cad = 'st_g%.0f' % g_cad if g_cad else 'st'
    for tag in ('st', 'st_g20', tag_cad):
        fn = os.path.join(CFD, 'forcing_%s.json' % tag)
        if os.path.exists(fn) and tag not in var: var[tag] = M.eo24(fn)
    def stress(F, z): return MISTUNE * F['root1'] / (2 * (z + F['zeta_aero'] / 2))
    print('EO24 root stress per 1/(2 zeta): design %.4f MPa (p_rms %.2f kPa, zeta_a %.3f %%)%s' % (
        des['root1'], des['p_rms_kPa'], 100 * des['zeta_aero'],
        ''.join('; %s %.4f (p_rms %.2f kPa, zeta_a %.3f %%)' % (k, v['root1'], v['p_rms_kPa'], 100 * v['zeta_aero']) for k, v in var.items())),
        flush=True)
    out['forcing'] = {k: dict(root_per_1_over_2zeta=v['root1'], zeta_aero=v['zeta_aero'], p_rms_kPa=v['p_rms_kPa'], kq=v['kq'],
                              state=v['fc'].get('state'), resonant_root_mist=[stress(v, z) for z in ZETA])
                      for k, v in dict(design=des, **var).items()}

    # ---- start line: state at the crossing speeds, acceleration, dynamic head of NGV2
    dsg = SU.design()
    st_cfd = SU.match(12270 / N_OP, TIT_START)
    line = []
    for T_m in (20.0, 200.0, 400.0, 600.0, 870.0):
        f = fm * math.sqrt(E_of(T_m) / E_of(T_BLADE_DES)) * K_CF
        n_x = f * 60 / EO / N_OP
        rows = {}
        for tit_c in (450.0, 650.0, 850.0):
            s = SU.match(n_x, tit_c + 273.15)
            if s: rows[tit_c] = dict(q_ratio=SU.q_ngv2(s) / SU.q_ngv2(st_cfd), accel=s['accel_rpm_s'], sm=s['surge_margin'])
        line.append(dict(T_metal=T_m, f_mode=f, rpm=n_x * N_OP, tit=rows))
    # deceleration after the fuel is shut off (normal stop after the cool-down at full speed no load): turbine inlet =
    # compressor exit + the heat left in the recuperator, ~200 C at the crossing -> ~ -300 rpm/s, dynamic head ~0.9 x start
    dec = SU.match(12270 / N_OP, 200.0 + 273.15)
    out['start_line'] = dict(cfd_state=dict(rpm=12270, tit=TIT_START, P0=st_cfd['P0_turb'], p_ngv2_exit=st_cfd['p_ngv2_exit'],
                                            m=st_cfd['m_t'], accel_rpm_s=st_cfd['accel_rpm_s'], surge_margin=st_cfd['surge_margin'],
                                            q_ngv2_ratio_to_design=SU.q_ngv2(st_cfd) / dsg['q_ngv2']),
                             crossing=line, J=st_cfd['J'], decel=dict(rpm_s=dec['accel_rpm_s'], q_ratio=SU.q_ngv2(dec) / SU.q_ngv2(st_cfd)))
    print('start line at 12,270 rpm, TIT %.0f C: P0 %.3f bar, NGV2 exit %.3f bar, q_NGV2 x%.2f design, max accel %.0f rpm/s '
          '(surge margin %.0f %%)' % (TIT_START - 273.15, st_cfd['P0_turb'] / 1e5, st_cfd['p_ngv2_exit'] / 1e5,
                                      SU.q_ngv2(st_cfd) / dsg['q_ngv2'], st_cfd['accel_rpm_s'], 100 * st_cfd['surge_margin']))
    for c in line:
        print('   blade %3.0f C: F1 %.0f Hz -> crossing %.0f rpm; q_NGV2 x%s of the CFD state; accel at TIT 450/650/850 C %s rpm/s' % (
            c['T_metal'], c['f_mode'], c['rpm'], '/'.join('%.2f' % v['q_ratio'] for v in c['tit'].values()),
            '/'.join('%.0f' % v['accel'] for v in c['tit'].values())))

    # ---- option 1: start-line crossing with the start-line forcing, transient passage, HCF / LCF
    F_st = var.get('st')
    if F_st is None:                                            # no CFD yet: design forcing x dynamic-head ratio
        F_st = dict(des, root1=des['root1'] * SU.q_ngv2(st_cfd) / dsg['q_ngv2'], zeta_aero=des['zeta_aero'] * 0.7)
        print('   (no start-line CFD: design forcing x q ratio %.2f)' % (SU.q_ngv2(st_cfd) / dsg['q_ngv2']))
    om_n = 2 * math.pi * fm
    o1 = dict(rates={}, criteria=[])
    for z in ZETA:
        zt = z + F_st['zeta_aero'] / 2
        for rate in (ACCEL_NOM,) + ACCEL_FAST:
            a = EO * 2 * math.pi * rate / 60 / om_n ** 2
            pk, c50, c90, c50p, _, _ = sweep_peak(zt, a)
            o1['rates'].setdefault('%.2f' % (100 * z), {})['%.0f' % rate] = dict(peak_ratio=pk, cycles_50=c50, cycles_90=c90,
                                                                               cycles_50_peak=c50p, zeta_total=zt)
    # HCF at the crossing for blade temperatures 20..870 C (the crossing speed moves with E(T)); forcing x q ratio
    for c in line:
        T_m, n_rpm = c['T_metal'], c['rpm']
        s_mean = s_root_des * (n_rpm / N_OP) ** 2
        ga = goodman_start(T_m, s_mean); lim = ga / 2
        q_r = c['tit'].get(650.0, {}).get('q_ratio', 1.0)
        for z in ZETA:
            zt = z + F_st['zeta_aero'] / 2
            s_ss = MISTUNE * F_st['root1'] * q_r / (2 * zt)
            s_dec = s_ss * SU.q_ngv2(dec) / SU.q_ngv2(st_cfd)
            for rate in (ACCEL_NOM, ACCEL_FAST[1]):
                r_ = o1['rates']['%.2f' % (100 * z)]['%.0f' % rate]
                s_pk = s_ss * r_['peak_ratio']
                # Miner: accel crossing (rate) + decel crossing (~1000 rpm/s), cycles as the time history of |A|
                dmg = 0.0
                for rr, s_x in ((rate, s_ss), (-dec['accel_rpm_s'], s_dec)):
                    a = EO * 2 * math.pi * rr / 60 / om_n ** 2
                    _, _, _, _, amp, h = sweep_peak(zt, a)
                    amp_s = amp * s_x / (1 - s_mean / float(np.interp(T_m, UTS_T, UTS)))   # Goodman-equivalent, R = -1
                    ncyc = h / (2 * math.pi)
                    s_e = float(np.interp(T_m, HCF_T, HCF_S))
                    dmg += float(np.sum(ncyc / (N_E * (s_e / np.maximum(2 * amp_s, 1e-9)) ** M_BASQ)))   # factor 2 on stress
                o1['criteria'].append(dict(T_metal=T_m, rpm=n_rpm, zeta_mech=z, accel=rate, s_mean=s_mean, goodman=ga,
                                           limit=lim, peak=s_pk, steady=s_ss, ok=s_pk <= lim, miner_10k_starts=dmg * STARTS))
    # LCF of the start-stop cycle with the crossing on top: range max(root stress at 15k, mean + vibratory peak) -
    # min(0, mean - peak), Manson-Morrow with the factors 2 / 20 (a1000_turbine_checks.manson_cycles)
    import a1000_turbine_checks as TC
    o1['lcf'] = []
    for q in o1['criteria']:
        if q['accel'] != ACCEL_NOM: continue
        s_hi = max(s_root_des, q['s_mean'] + q['peak']); s_lo = min(0.0, q['s_mean'] - q['peak'])
        o1['lcf'].append(dict(T_metal=q['T_metal'], zeta_mech=q['zeta_mech'], s_range=s_hi - s_lo,
                              cycles=TC.manson_cycles((s_hi - s_lo) / E_of(q['T_metal']), q['T_metal'], s_hi)))
    out['option1'] = o1
    wl = min(o1['lcf'], key=lambda q: q['cycles'])
    print('option 1 LCF: worst start-stop range with the crossing %.0f MPa (blade %.0f C, zeta %.2f %%) -> %.1e starts (Manson-Morrow 2/20)' % (
        wl['s_range'], wl['T_metal'], 100 * wl['zeta_mech'], wl['cycles']))
    print('option 1 (start-line forcing, crossing): x1.5 mistuning; peak / Goodman/2 (start state) and Miner (stress x2, 10k starts):')
    for q in o1['criteria']:
        if q['accel'] != ACCEL_NOM and q['T_metal'] not in (20.0, 870.0): continue
        print('   blade %3.0f C (%5.0f rpm, mean %3.0f MPa, Goodman/2 %4.1f) zeta %.2f %% accel %4.0f rpm/s: steady %5.1f, peak %5.1f MPa '
              '-> %s, Miner %.2g' % (q['T_metal'], q['rpm'], q['s_mean'], q['limit'], 100 * q['zeta_mech'], q['accel'], q['steady'],
                                     q['peak'], 'ok' if q['ok'] else 'FAIL', q['miner_10k_starts']))

    # worst blade temperature: largest steady resonant stress / start-up limit (zeta 0.05 %)
    def worst(z):
        cr = [q for q in o1['criteria'] if q['zeta_mech'] == z and q['accel'] == ACCEL_NOM]
        return max(cr, key=lambda q: q['steady'] / q['limit'])
    lim_st = min(q['limit'] for q in o1['criteria'])

    # ---- option 4: gap (CFD decay rate)
    if 'st' in var and 'st_g20' in var:
        ratio = var['st_g20']['root1'] / var['st']['root1']; k = -math.log(ratio) / 20.0; theory = False
    else:
        k = 24 / M.A.RM; ratio = math.exp(-20 * k); theory = True                 # potential theory, k = 2 pi / s
    need = {}
    for z in ZETA:
        w_ = worst(z)
        need['%.2f' % (100 * z)] = dict(start=max(0.0, math.log(w_['steady'] / w_['limit']) / k),
                                        design_allowable=max(0.0, math.log(w_['steady'] / (g_des / 2)) / k),
                                        worst_T_metal=w_['T_metal'], steady=w_['steady'], limit=w_['limit'])
    zl, zh = '%.2f' % (100 * ZETA[0]), '%.2f' % (100 * ZETA[-1])
    rec = GAP_ROUND * math.ceil(max(need[zl]['start'], need[zh]['design_allowable']) / GAP_ROUND)
    out['recommended_gap_mm'] = rec
    out['option4'] = o4 = dict(ratio_20mm=ratio, k_per_mm=k, k_theory=24 / M.A.RM, from_theory=theory, gap_needed_mm=need,
                               recommended_mm=rec, with_recommended={z_: dict(steady=v['steady'] * math.exp(-k * rec), limit=v['limit'],
                                                                              design_limit=g_des / 2) for z_, v in need.items()},
                               gap_now_mm=dict(hub=float(M.A.X_LE5['N2'] - M.A.X_TE['R1']), mid=float(M.A.X_LE5['N2'] - M.A.x_te_of('R1', 0.5)),
                                               tip=float(M.A.X_LE5['N2'] - M.A.x_te_of('R1', 1.0))),
                               gap_cad_mm=dict(hub=float(M.A.X_LE['N2'] - M.A.X_TE['R1']), mid=float(M.A.X_LE['N2'] - M.A.x_te_of('R1', 0.5)),
                                               tip=float(M.A.X_LE['N2'] - M.A.x_te_of('R1', 1.0))))
    print('option 4 (gap): forcing x%.3f at +20 mm -> decay %.4f /mm (potential theory 2 pi / s = %.4f)%s; extra gap needed '
          '(start allowable / design allowable): %s' % (ratio, k, 24 / M.A.RM, ' [theory: CFD pair missing]' if theory else '',
                                                     ', '.join('zeta %s %%: %.0f / %.0f mm' % (k_, v['start'], v['design_allowable'])
                                                               for k_, v in need.items())))
    print('   recommended: +%.0f mm -> worst resonant root stress %s MPa (zeta %s %%) vs start-up limit %.0f / design limit %.1f MPa' % (
        rec, '/'.join('%.1f' % v['steady'] for v in o4['with_recommended'].values()), '/'.join(o4['with_recommended']),
        lim_st, g_des / 2))
    # rev 6: the CAD gap, start-line CFD on the CAD annulus against the prediction (decay rate from the 0 / +20 mm pair)
    if g_cad and tag_cad in var and 'st' in var:
        rc = var[tag_cad]['root1'] / var['st']['root1']
        o4['cad'] = dict(dgap_mm=g_cad, ratio_cfd=rc, ratio_pred=math.exp(-k * g_cad), k_eff_per_mm=-math.log(rc) / g_cad,
                         zeta_aero=var[tag_cad]['zeta_aero'],
                         steady={z_: v['steady'] * rc * (var['st']['zeta_aero'] / 2 + float(z_) / 100) / (var[tag_cad]['zeta_aero'] / 2 + float(z_) / 100)
                                 for z_, v in need.items()})
        print('   CAD gap +%.0f mm (CFD %s): EO24 forcing x%.4f of +0 (predicted x%.4f, effective decay %.4f / mm) -> worst resonant root '
              'stress %s MPa (zeta %s %%)' % (g_cad, tag_cad, rc, math.exp(-k * g_cad), o4['cad']['k_eff_per_mm'],
                                              '/'.join('%.1f' % v for v in o4['cad']['steady'].values()), '/'.join(o4['cad']['steady'])))
    if '--rotor' in sys.argv:
        o4['rotor'] = rotor_gap(sorted({0.0, 10.0, 20.0, 30.0, rec}))
        for dg, v in o4['rotor'].items():
            print('   R1-R2 spacer +%s mm: criticals %s rpm, bending separation %.1f %% (API %.1f %%), rotor %.1f kg' % (
                dg, ' / '.join('%.0f' % c for c in v['N']), v['SM_bend'], v['SM_req_bend'], v['mass']))

    # ---- option 3: damping needed, damper access of the mode
    ef, u_rim, u_max = M.energy_fractions(des['U'])
    need_z = {}
    for lab in ('start', 'design_allowable'):
        need_z[lab] = max(MISTUNE * F_st['root1'] * c['tit'].get(650.0, {}).get('q_ratio', 1.0) /
                          (2 * (min(q['limit'] for q in o1['criteria'] if q['T_metal'] == c['T_metal']) if lab == 'start' else g_des / 2))
                          for c in line) - F_st['zeta_aero'] / 2
    # what a friction damper can add: modal strain-energy bound zeta <= eta_max / 2 x (energy share of the damped region),
    # eta_max ~0.5 for an optimally slipping Coulomb contact; the platform + rim share of the flap mode is the region
    zeta_damper_max = 0.5 / 2 * ef['rim']
    out['option3'] = dict(zeta_total_needed=need_z, ke_fraction=ef, rim_to_max_displacement=u_rim / u_max,
                          zeta_damper_max=zeta_damper_max)
    print('option 3 (damping): total zeta needed %.2f %% (start allowable) / %.2f %% (design allowable); mode KE fractions '
          'airfoil %.4f, platform + rim %.5f, disc %.6f; rim / max displacement %.3f -> friction damper at the rim / platform '
          '<= %.3f %%' % (100 * need_z['start'], 100 * need_z['design_allowable'], ef['airfoil'], ef['rim'], ef['disc'],
                          u_rim / u_max, 100 * zeta_damper_max))

    # ---- all R1 orders of the forced-response analysis at the start-line forcing (check sheet: crossings below the band)
    # (rev 6: at the CAD gap, variant st_g25; the rev 5 start-line forcing 'st' when that CFD is missing)
    out['orders_start'] = {}
    tag_os = tag_cad if tag_cad in var else 'st'
    out['orders_start_forcing'] = 'forcing_%s.json' % tag_os
    if tag_os != tag_cad: print('   WARNING: start-line CFD at the CAD gap (%s) missing: orders_start on the rev 5 forcing' % tag_cad)
    for eo, nd, _, fam in FR.ORDERS:
        if not var.get(tag_os): break
        R = M.order(os.path.join(CFD, 'forcing_%s.json' % tag_os), eo, nd)
        n_x = R['f_mode'] * 60 / eo
        rows = []
        for T_m in (20.0, 870.0):
            n_T = n_x * math.sqrt(E_of(T_m) / E_of(T_BLADE_DES)) * K_CF
            st_T = next(m for m in (SU.match(n_T / N_OP, t) for t in (TIT_START, TIT_START - 200)) if m)
            q_r = SU.q_ngv2(st_T) / SU.q_ngv2(st_cfd)
            rows.append(dict(T_metal=T_m, rpm=n_T, q_ratio=q_r, limit=goodman_start(T_m, s_root_des * (n_T / N_OP) ** 2) / 2,
                             root_res_mist=[MISTUNE * R['root1'] * q_r / (2 * (z + R['zeta_aero'] / 2)) for z in ZETA]))
        out['orders_start'][str(eo)] = dict(eo=eo, nd=nd, family=fam, f_mode=R['f_mode'], zeta_aero=R['zeta_aero'], rows=rows)
        print('   start-line forcing (%s) EO%-2d ND%-2d F%d (%.0f Hz, zeta_a %.3f %%): %s' % (tag_os, eo, nd, fam, R['f_mode'], 100 * R['zeta_aero'],
              '; '.join('blade %.0f C %.0f rpm: %s MPa vs %.0f' % (r['T_metal'], r['rpm'], '/'.join('%.1f' % v for v in r['root_res_mist']),
                                                                    r['limit']) for r in rows)))

    json.dump(out, open(os.path.join(FEA, 'a1000_R1_eo24_options.json'), 'w'), indent=1, default=float)

    # ---- option 2: NGV2 count with NGV1 = 48 (a1000_vane_count.py --n1 48 reads the json just written)
    import a1000_vane_count as VC
    scan = VC.main(48)
    o2 = []
    for r in sorted(scan, key=lambda r: r['n2']):
        f1 = [c for c in r['startup'] if 'sigma' in c]
        o2.append(dict(n2=r['n2'], band=r['band_verdict'], band_ok=r['band_verdict'].startswith('ok'), cx2_mm=r['cx2_mm'],
                       sec_loss=r['ko_sec_N2'], flap=[dict(order=c['order'], eo=c['eo'], rpm=c['rpm'], sigma=c['sigma'], ok=c['ok'],
                                                          fail=c['fail']) for c in f1],
                       worst_flap=max((c['sigma'][0] for c in f1), default=0.0)))
    out['option2'] = dict(n1=48, scan=o2, start_limit=lim_st,
                          feasible=[q['n2'] for q in o2 if q['band_ok'] and q['worst_flap'] <= lim_st])
    print('option 2 (NGV2 count, NGV1 48): band rules pass for N2 = %s; R1 flap start crossing <= %.0f MPa at zeta 0.05 %% for '
          'N2 = %s; both: %s' % ([q['n2'] for q in o2 if q['band_ok']], lim_st, [q['n2'] for q in o2 if q['worst_flap'] <= lim_st],
                                out['option2']['feasible'] or 'none'))
    json.dump(out, open(os.path.join(FEA, 'a1000_R1_eo24_options.json'), 'w'), indent=1, default=float)
    print('written', os.path.join(FEA, 'a1000_R1_eo24_options.json'))
    plot(out)
    return out


def rotor_gap(dgs):
    """rotor dynamics (a1000_rotordynamics.py, layout A + SFD) with NGV2 / R2 moved aft by dg from rev 5 (longer R1 - R2
    spacer and rear stub position): damped criticals, separation margin of the bending mode (the beam model of the rev 5
    study: use the relative change on the detailed stack of a1000_rotor_stack.py)"""
    import a1000_rotordynamics as RD
    A = RD.A; keys = [('X_LE', 'N2'), ('X_TE', 'N2'), ('X_LE', 'R2'), ('X_TE', 'R2')]
    old = {k: getattr(A, k[0])[k[1]] for k in keys}; res = {}
    try:
        for dg in dgs:
            for k in keys: getattr(A, k[0])[k[1]] = old[k] - A.DGAP2 + dg                  # dg over rev 5
            R = RD.rotor('A'); dc = RD.damped_criticals(R, RD.SUP[RD.CONF[RD.SEL][1]], nmax=34000.0)
            b = max(dc, key=lambda c: c['N'])
            res['%.0f' % dg] = dict(N=[c['N'] for c in dc], SM_bend=b['SM'], SM_req_bend=b['SM_req'], ok=all(c['ok'] for c in dc),
                                    mass=RD.rotor_mass(R), bearings=R['brg'])
    finally:
        for k in keys: getattr(A, k[0])[k[1]] = old[k]
    return res


def plot(out):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(14, 9.6), dpi=110); (a1, a2), (a3, a4) = ax
    o1, o4 = out['option1'], out['option4']; lim = min(q['limit'] for q in o1['criteria'])
    gd = out['option3'].get('goodman_design', None)
    # (1) transient passage: peak / steady resonance vs acceleration rate
    rates = np.array([50, 100, 150, 250, 400, 600, 1000, 1500, 2500, 4000.0])
    fm = out['f_mode']; om_n = 2 * math.pi * fm
    for i, z in enumerate(ZETA):
        zt = z + out['forcing']['st' if 'st' in out['forcing'] else 'design']['zeta_aero'] / 2
        pk = [sweep_peak(zt, EO * 2 * math.pi * r / 60 / om_n ** 2)[0] for r in rates]
        a1.semilogx(rates, pk, 'o-', ms=3, color='C%d' % i, label='zeta %.2f %% (+ aero / 2: %.3f %%)' % (100 * z, 100 * zt))
    a1.axvspan(100, 250, color='0.9', zorder=0); a1.text(105, 0.32, 'start schedule', fontsize=8)
    a1.axvline(out['start_line']['cfd_state']['accel_rpm_s'], color='k', ls=':', lw=1)
    a1.text(out['start_line']['cfd_state']['accel_rpm_s'] * 1.05, 0.32, 'max at TIT 650 C', fontsize=8)
    a1.set_ylim(0.3, 1.02); a1.grid(alpha=0.3, which='both'); a1.legend(fontsize=8, loc='lower left')
    a1.set_xlabel('acceleration through 12,270 rpm [rpm/s]'); a1.set_ylabel('transient peak / steady resonant amplitude')
    a1.set_title('1. Fast crossing: EO24 x ND24 F1 (%.0f Hz), linear sweep' % fm, fontsize=10)
    # (2) gap: steady resonant root stress (worst blade temperature) vs extra gap
    g = np.linspace(0, 40, 81)
    for i, z in enumerate(ZETA):
        n = o4['gap_needed_mm']['%.2f' % (100 * z)]
        a2.semilogy(g, n['steady'] * np.exp(-o4['k_per_mm'] * g), color='C%d' % i, label='zeta %.2f %%' % (100 * z))
        if o4.get('cad'):
            a2.semilogy([o4['cad']['dgap_mm']], [o4['cad']['steady']['%.2f' % (100 * z)]], 'o', color='C%d' % i, ms=6, mec='k',
                        label='CFD at the CAD gap' if i == 0 else None)
    a2.axhline(lim, color='k', lw=1.2); a2.text(1, lim * 1.07, 'start-up limit (cold blade Goodman / 2) %.0f MPa' % lim, fontsize=8)
    a2.axhline(out['goodman_design'] / 2, color='k', ls='--', lw=1)
    a2.text(1, out['goodman_design'] / 2 * 1.07, 'design-point limit %.1f MPa' % (out['goodman_design'] / 2), fontsize=8)
    if out.get('recommended_gap_mm'):
        a2.axvline(out['recommended_gap_mm'], color='0.3', lw=6, alpha=0.25)
        a2.text(out['recommended_gap_mm'] + 0.7, a2.get_ylim()[1] * 0.5, 'recommended +%.0f mm' % out['recommended_gap_mm'], fontsize=8)
    a2.grid(alpha=0.3, which='both'); a2.legend(fontsize=8)
    gc = o4.get('gap_cad_mm')
    a2.set_xlabel('extra R1 TE - NGV2 LE axial gap [mm] (rev 5 %.0f / %.0f / %.0f mm hub / mid / tip%s)' % (
        o4['gap_now_mm']['hub'], o4['gap_now_mm']['mid'], o4['gap_now_mm']['tip'],
        '; CAD rev 6 %.0f / %.0f / %.0f' % (gc['hub'], gc['mid'], gc['tip']) if gc else ''))
    a2.set_ylabel('R1 root stress at resonance, x%.1f mistuning [MPa]' % MISTUNE)
    a2.set_title('4. Larger gap: start-line CFD forcing, decay %.3f / mm%s' % (o4['k_per_mm'], ' (theory)' if o4['from_theory'] else
                                                                              ' (CFD 0 / +20 mm)'), fontsize=10)
    # (3) NGV2 count
    o2 = out.get('option2', {}).get('scan', [])
    if o2:
        n2 = [q['n2'] for q in o2]; wf = [max(q['worst_flap'], 0.5) for q in o2]
        a3.bar(n2, wf, color=['#2e7d32' if q['band_ok'] else '#c62828' for q in o2], alpha=0.8); a3.set_xticks(n2[::2])
        a3.axhline(lim, color='k', lw=1.2); a3.set_yscale('log'); a3.set_xlabel('NGV2 vane count (NGV1 = 48)')
        a3.set_ylabel('R1 flap start crossing, zeta 0.05 %% [MPa]')
        a3.set_title('2. NGV2 count: green = grid-band rules (R1 + R2) pass, red = fail', fontsize=10); a3.grid(alpha=0.3, which='both')
    # (4) damping
    o3 = out['option3']; nz = o3['zeta_total_needed']
    a4.bar([0, 1, 2], [100 * nz['start'], 100 * nz['design_allowable'], 100 * o3['zeta_damper_max']], color=['C0', 'C0', 'C3'], alpha=0.8)
    a4.axhspan(100 * ZETA[0], 100 * ZETA[-1], color='0.9', zorder=0); a4.text(2.05, 100 * ZETA[-1] * 0.8, 'cast blisk, no joints', fontsize=8)
    a4.set_xticks([0, 1, 2]); a4.set_xticklabels(['needed\n(start-up limit)', 'needed\n(design limit)', 'friction damper\nat rim / platform (bound)'])
    a4.set_yscale('log'); a4.set_ylabel('total damping [% of critical]'); a4.grid(alpha=0.3, which='both')
    a4.set_title('3. Damping: ND24 F1 energy share in platform + rim %.3f %%' % (100 * o3['ke_fraction']['rim']), fontsize=10)
    fig.suptitle('AURORA-1000 R1 EO24 start-up crossing: options (x%.1f mistuning, cold-blade start-up Goodman / 2)' % MISTUNE, fontsize=11)
    fig.tight_layout(); png = os.path.join(ROOT, 'docs', 'img', 'a1000_R1_eo24_options.png'); fig.savefig(png); print('written', png)


if __name__ == '__main__':
    main()
