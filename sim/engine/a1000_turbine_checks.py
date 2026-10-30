#!/usr/bin/env python3
"""AURORA-1000 turbine: summary of the structural checks (design review sheet) from the FE results.

Inputs (run first):  sim/engine/a1000_blade_fea.py R1 / R2   -> fea/a1000_blade_R1.json, _R2.json, a1000_R?_15k.frd
                     sim/engine/a1000_blisk_cyclic.py R1 / R2 -> fea/a1000_blisk_R?_cyclic.json (coupled blade-disc modes)
                     sim/engine/a1000_disc_fea.py           -> fea/a1000_disc.json (total and mechanical-only solutions)
                     sim/engine/a1000_rotordynamics.py      -> fea/a1000_rotordynamics.json
                     sim/engine/a1000_r1_forced_response.py -> fea/a1000_R1_forced_response.json (CFD forcing on the
                                                               cyclic modes; R1 EO96 is judged on it, not on its margin)
Checks (rev 4, after the adversarial review):
  blades  creep rupture of the net section above the fillet on the design MINIMUM Larson-Miller curve, at the hub
          rotor-relative total temperature; net-section stress = max(FE band mean, P/A from the design sections);
          yield of the peak; engine-order interference over the +-2 % grid band on the coupled (cyclic) blisk modes:
          strong 1 x NPF 10 % against all modes, weak orders 5 % against the modes below 1.05 x blade mode 6, the
          vane-vane interaction |N1 - N2| outside the band + forced-response estimate (rev 5; rigid-hub margins shown
          for reference only); allowable vibratory stress (Goodman, mean-stress intercept = 1e5 h minimum rupture
          strength in the creep range); forced response of R1 at EO24 / 48 / 96 (CFD forcing, design point, x1.5
          mistuning, damping 0.05-0.3 % + aero): resonant root stress <= Goodman / 2, PASS at the lower-bound damping,
          FAIL above it even at the upper one, else marginal; R1 EO96 (2 x NGV1, 4.9 % from ND22 F6) is judged on it
          (FR_CRITERION), its frequency margin is shown for reference only
  discs   yield margin at trip (total stress), burst (area-mean hoop, 85 % UTS), creep on the PRIMARY (mechanical)
          stress, LCF of the start-stop cycle (total stress; Manson universal slopes + Morrow mean stress, factors 2 on
          strain / 20 on life; NASA Grainex MAR-M247 disk data at 649 C as a cross-check)
  rotor   critical speeds vs API 617 separation margins, unbalance response
  tips    running tip clearance budget -> shroud-carrier temperature requirement
Writes: sim/engine/fea/a1000_turbine_checks.json, docs/img/a1000_turbine_checks.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FEA = os.path.join(HERE, 'fea')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'sim')); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
import e1_turbine_fea as F                                    # noqa: E402
from mw1_concept_study import mar_m247_rupture_hours, mar_m247_rupture_stress   # noqa: E402
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_turbine as A                                     # noqa: E402
sys.argv = _argv

LIFE_TARGET = 1.0e5                                            # h, hot-section design life (minimum rupture curve)
MAT_T = np.array([20., 400., 600., 800., 900., 1000.])
MAT_UTS = np.array([965., 980., 1000., 900., 724., 550.])      # MAR-M247 cast, typical (rev 4 data search)
MAT_ALPHA = np.array([11.0, 12.6, 13.4, 14.4, 15.0, 15.6]) * 1e-6   # mean CTE from 20 C
# HCF 2e7, R = -1, smooth: 190 (650 C) / 220 (800 C) / 200 MPa (900 C) (Smid et al. 2016); x 0.8 for the cast surface
SIG_E = dict(R1=165.0, R2=170.0)
BAND = (0.98, 1.02)                                            # grid-frequency speed band of the constant-speed set
WEAK_MODES = 6                                                 # weak orders (2 x NPF, wakes through 2 rows): coupled modes
                                                               # below 1.05 x the rigid-hub blade mode 6 (rev 5)
REQ_INT = 0.001                                                # vane-vane interaction |N1 - N2|: no crossing in the grid band
# forced-response estimate of the interaction order: unsteady load = A_INT x steady gas load (upper estimate: the N1 wake
# left after two rows ~10 % of the N2 wake, clocking modulation <= 10 % of it; N2 wake unsteady load ~10 % of the steady),
# blisk damping ZETA (material + aero, lower bound), mistuning amplification MISTUNE; limit = Goodman allowable / 2
A_INT, ZETA, MISTUNE = 0.01, 0.002, 1.5
# orders judged by the forced response of a1000_r1_forced_response.py (CFD forcing on the cyclic modes) instead of the
# frequency margin (rev 5); its other orders are listed for reference
FR_CRITERION = dict(R1=(96,))
ALPHA_CARRIER = 17.8e-6                                        # shroud carrier 1.4828 (X15CrNiSi20-12), mean 20..500 C
CARRIER_T_MAX = 600.0                                          # 1.4828 lightly loaded ring, cooled by compressor air: max design T
TARGET_CLEAR = dict(R1=0.45, R2=0.55)                          # running tip clearance target [mm] (~1.3 % / 1.0 % of height)


MAT_E = np.array([200e3, 186e3, 176e3, 163e3, 156e3, 148e3])  # MPa (same table as the FE models)
RA = 0.06                                                      # reduction of area, cast MAR-M247 at 600-800 C (typical)
STARTS_REQ = 10000                                             # start-stop cycles: ~1 a day for 27 years


def manson_cycles(d_eps, T, s_max=None):
    """LCF life of a 0 -> max -> 0 cycle by Manson's universal slopes with Morrow's mean-stress correction on the elastic
    term (mean stress = s_max / 2), d_eps = 3.5 (Su - sm) / E N^-0.12 + D^0.6 N^-0.6, with the design factors 2 on strain /
    20 on life (the smaller life)"""
    Su, E = float(np.interp(T, MAT_T, MAT_UTS)), float(np.interp(T, MAT_T, MAT_E)); D = -math.log(1 - RA)
    sm = 0.5 * (s_max if s_max is not None else d_eps * E)
    def N_of(de):
        lo, hi = 0.0, 12.0
        for _ in range(80):
            m = 0.5 * (lo + hi); N = 10 ** m
            if 3.5 * (Su - sm) / E * N ** -0.12 + D ** 0.6 * N ** -0.6 > de: lo = m
            else: hi = m
        return 10 ** lo
    return min(N_of(2 * d_eps), N_of(d_eps) / 20)


def grainex_lb_cycles(d_eps):
    """cross-check: NASA TM-2004-212985 (Delgado et al.), cast Grainex MAR-M247 disk, 649 C, R = 0: total strain range
    0.5 % -> 665 cycles = lower bound of the 99.95 % prediction interval (bolt-hole initiation); scaled with N ~ de^-10
    (elastic-dominated regime, Basquin b ~ -0.1). Data quoted from the abstract (primary table not read)."""
    return 665.0 * (0.5 / (100 * d_eps)) ** 10


def t0rel_hub_C(row):
    """rotor-relative total temperature at the hub section [C] from the design velocity triangles"""
    st = A.S1 if row == 'R1' else A.S2; r = A.row_radius(row, 0.0); U = A.OM * r * 1e-3
    C2 = math.hypot(A.CX, A.ct2(r)); W2 = math.hypot(A.CX, A.ct2(r) - U)
    return st['T0_in'] - C2 ** 2 / (2 * A.CP_G) + W2 ** 2 / (2 * A.CP_G) - 273.15


def blade_PA(row, n=41):
    """net-section mean radial stress above the root fillet from the design sections: rho w^2 int A r dr / A(r0) [MPa]"""
    sp = list(np.linspace(0, 1, n)); secs = A.design_row(row, sp); rho = 8.54e-9; om = A.OM
    rr, AA = [], []
    for f in sp:
        sc = secs[f]; pts = sc.outline(*A.DENSE)[0]; th = np.arctan2(pts[:, 2], pts[:, 1])
        x, y = pts[:, 0], sc.r * th; ar = 0.5 * abs(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
        rr.append(sc.r); AA.append(ar)
    rr, AA = np.array(rr), np.array(AA)
    r0 = rr[0] + 1.125 * A.FILLET[row]                             # top of the root fillet
    m = rr >= r0; rs = np.r_[r0, rr[m]]; As = np.r_[np.interp(r0, rr, AA), AA[m]]
    F_ = rho * om ** 2 * (np.trapezoid(As * rs, rs) if hasattr(np, 'trapezoid') else np.trapz(As * rs, rs))
    return F_ / As[0], As[0]


def cyclic_margins(row, eos, f_lim=None):
    """band margins of engine orders eos against the coupled blade-disc families (fea/a1000_blisk_<row>_cyclic.json);
    f_lim: weak orders, only the modes below f_lim (the band of the first WEAK_MODES blade modes: at low ND the disc modes
    interleave, so a family index would miss blade modes); covered = the computed families reach above the order or f_lim"""
    c = load('a1000_blisk_%s_cyclic.json' % row)
    if not c: return None
    Z = c['Z']; tab = {int(k): v for k, v in c['freqs'].items()}; out = {}
    for k in eos:
        m = k % Z; nd = min(m, Z - m)
        if nd not in tab: out[k] = None; continue
        fk = k * BAND[1] * 15000 / 60 * 1.05
        fl = [f for f in tab[nd] if f_lim is None or f <= f_lim] or tab[nd][:1]
        best = None
        for fam, f in enumerate(fl):
            mb = [(f - k * b * 15000 / 60) / (k * b * 15000 / 60) for b in BAND]
            mbs = 0.0 if mb[0] * mb[1] <= 0 else min(mb, key=abs)
            if best is None or abs(mbs) < abs(best[0]): best = (mbs, fam + 1, f, nd)
        covered = max(tab[nd]) > (fk if f_lim is None else min(fk, f_lim))
        out[k] = dict(margin=best[0], family=best[1], f=best[2], nd=best[3], covered=covered)
    return out


def load(name):
    p = os.path.join(FEA, name)
    return json.load(open(p)) if os.path.exists(p) else None


def blade_tip_stretch(row):
    """mean radial displacement of the blade tip nodes in the 15,000 rpm static step (FE, blade on a rigid platform)"""
    frd = os.path.join(FEA, 'a1000_%s_15k.frd' % row)
    if not os.path.exists(frd): return None
    nodes, blocks = F.read_frd(frd)
    U = [b for b in blocks if b['name'].startswith('DISP')][0]['data']
    rr = {k: math.hypot(p[1], p[2]) for k, p in nodes.items()}
    r_top = max(rr.values()); tip = [k for k in U if rr[k] > r_top - 1.0]
    ur = [(U[k][1] * nodes[k][1] + U[k][2] * nodes[k][2]) / rr[k] for k in tip]
    return float(np.mean(ur))


def main():
    out = dict(blades={}, discs={}, rotor={}, tips={})
    rows = []                                                  # (test, value, limit, unit, ok, note) for the sheet / plot
    disc = load('a1000_disc.json'); rd = load('a1000_rotordynamics.json'); prev = load('a1000_turbine_checks.json')
    for row in ('R1', 'R2'):
        b = load('a1000_blade_%s.json' % row)
        if b is None: print('%s: blade FEA results missing' % row); continue
        T = b['metal_C']; s = b['stress']
        T_root = t0rel_hub_C(row)
        s_pa, A_net = blade_PA(row)
        s_root = max(s['srr_root_mean'], s_pa)
        life = mar_m247_rupture_hours(s_root, T_root + 273.15); life_typ = mar_m247_rupture_hours(s_root, T_root + 273.15, 'typical')
        s_allow = mar_m247_rupture_stress((T_root + 273.15) * (20 + 5) / 1000)          # 1e5 h, minimum curve
        y_margin = b['yield_MPa'] / s['vm_max']
        # Goodman: mean-stress intercept = 1e5 h minimum rupture strength at the metal temperature (creep range)
        sa_root = SIG_E[row] * max(0.0, 1 - s_root / s_allow)
        sa_peak = SIG_E[row] * max(0.0, 1 - s['vm_max'] / mar_m247_rupture_stress((T + 273.15) * 25 / 1000))
        crit = b['critical']
        # stator orders: strong = 1 x NPF of the adjacent rows (10 %), weak = 2 x NPF and wakes through two rows (5 %)
        v = b.get('vanes', {}); n1, n2 = v.get('N1', 43), v.get('N2', 47)
        strong = (n1, n2) if row == 'R1' else (n2,)
        # R1: the 2nd harmonic of the downstream N2 potential field decays as exp(-4 pi g / s) (47 vanes: 0.026, not
        # counted); the 29 long-chord vanes of rev 5 (s = 50 mm): 0.105 -> 2 x N2 is a weak order on R1
        pf2 = math.exp(-4 * math.pi * A.GAP2 / (2 * math.pi * A.RM / n2))
        weak = ((2 * n1,) + ((2 * n2,) if pf2 >= 0.05 else ())) if row == 'R1' else (n1, 2 * n2)
        # vane-vane interaction (N1 wakes chopped by NGV2): circumferential order |N1 - N2| on both rotors, second-order
        # forcing: no crossing of the first WEAK_MODES families inside the grid band (forced response / tip timing beyond)
        inter = (abs(n1 - n2),) if abs(n1 - n2) > 5 and abs(n1 - n2) not in (n1, n2) else ()   # (<= 5: EO 1-5; = N2: NPF)
        key = 'margin_band' if 'margin_band' in b['interference'][0] else 'margin'
        mg = lambda eos, nm=None: min((abs(r[key]) for r in b['interference'] if r['eo'] in eos and (nm is None or r['mode'] <= nm)),
                                      default=float('nan'))
        # weak orders against the first WEAK_MODES modes (the dense higher modes: forced response / tip timing)
        worst, worst_weak, worst_low = mg(strong), mg(weak, WEAK_MODES), mg((1, 2, 3, 4, 5))
        weak_cov = True
        f_lim = 1.05 * b['freqs'][str(15000)][WEAK_MODES - 1]          # band of the first WEAK_MODES blade modes
        cyc = cyclic_margins(row, list(strong) + [1, 2, 3, 4, 5]); cyc_w = cyclic_margins(row, weak + inter, f_lim)
        # gas bending: tangential force per blade from the stage work, at mid span (estimate, section modulus ~ 0.1 c t^2)
        mdot = 6.32 * 1.017; dh = A.ML['turbine']['dh_tot'] / 2; U_m = A.RM * 1e-3 * A.OM
        Ft = mdot * dh / U_m / A.Z[row]                         # N per blade (torque / (r_m Z))
        h = (A.row_radius(row, 1.0) - A.row_radius(row, 0.0)) * 1e-3
        des = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))[row]['sections'][0]
        Wz = 0.10 * des['chord'] * des['tmax'] ** 2 * 1e-9      # m3 about the weak axis (thin cambered section)
        s_gas = Ft * h / 2 / Wz / 1e6
        out['blades'][row] = dict(metal_C=T, T_root_C=T_root, sigma_root_fe=s['srr_root_mean'], sigma_root_PA=s_pa,
                                  sigma_root=s_root, A_net_mm2=A_net, sigma_allow_1e5h_min=s_allow, creep_life_h_min=life,
                                  creep_life_h_typ=life_typ, vm_max=s['vm_max'], vm_p99=s['vm_p99'], yield_margin_peak=y_margin,
                                  goodman_allow_root=sa_root, goodman_allow_peak=sa_peak, interference_critical=crit,
                                  worst_margin_npf=worst, worst_margin_weak=worst_weak, worst_margin_low_orders=worst_low,
                                  weak_orders_covered=weak_cov, cyclic=cyc, cyclic_weak=cyc_w, weak_orders=weak,
                                  potential_2xN2_decay=pf2 if row == 'R1' else None, gas_force_N=Ft, gas_bending_MPa=s_gas,
                                  freqs_15k=b['freqs'][str(15000)])
        # rigid-hub margins: shown for reference only (ok = None) when the coupled blisk model exists, which governs: the
        # disc lowers the low-ND families and the rigid hub is not the engine (rev 5)
        info = (lambda ok: None) if cyc else (lambda ok: ok)
        rows += [('%s blade creep (root, min curve)' % row, life, LIFE_TARGET, 'h', life >= LIFE_TARGET,
                  '%.0f MPa (FE %.0f / P/A %.0f) @ %.0f C; allow %.0f' % (s_root, s['srr_root_mean'], s_pa, T_root, s_allow)),
                 ('%s blade peak / yield' % row, y_margin, 1.0, '-', y_margin >= 1.0, 'vm %.0f MPa (local, fillet/TE)' % s['vm_max']),
                 ('%s blade EO margin, NPF %s' % (row, '/'.join(map(str, strong))), 100 * worst, 10.0, '%', info(worst >= 0.10),
                  'rigid hub, worst over 14.7-15.3k rpm'),
                 ('%s blade EO margin, weak %s' % (row, '/'.join(map(str, weak))), 100 * worst_weak, 5.0, '%',
                  info(worst_weak >= 0.05 and weak_cov), 'rigid hub, band, modes 1-%d' % WEAK_MODES),
                 ('%s blade EO margin (EO 1-5)' % row, 100 * worst_low, 10.0, '%', info(worst_low >= 0.10), 'rigid hub, band')]
        # orders closed by the forced-response analysis (a1000_r1_forced_response.py): the frequency margin is shown for
        # reference, the criterion is the resonant root stress (rev 5: R1 EO96, 2 x NGV1 at 4.9 % from ND22 F6)
        fr = load('a1000_%s_forced_response.json' % row) or {}
        fr_eos = tuple(int(k) for k in FR_CRITERION.get(row, ()) if str(k) in fr.get('orders', {}))
        if cyc:
            for lab, eos, req, src in (('NPF', strong, 0.10, cyc), ('weak', weak, 0.05, cyc_w), ('N1-N2', inter, REQ_INT, cyc_w),
                                       ('EO 1-5', (1, 2, 3, 4, 5), 0.10, cyc)):
                if lab == 'weak' and fr_eos:                       # forced-response orders: margin for reference only
                    for k in fr_eos:
                        q = (src or {}).get(k)
                        if q: rows.append(('%s blisk (cyclic) EO margin, EO%d' % (row, k), 100 * abs(q['margin']), 100 * req, '%',
                                           None, 'ND %d family %d %.0f Hz; criterion: forced response' % (q['nd'], q['family'], q['f'])))
                    eos = tuple(k for k in eos if k not in fr_eos)
                if not eos: continue
                missing = [k for k in eos if not src.get(k)]
                ms = [src[k] for k in eos if src.get(k)]
                if not ms: continue
                w = min(ms, key=lambda q: abs(q['margin'])); cov = all(q['covered'] for q in ms) and not missing
                rows.append(('%s blisk (cyclic) EO margin, %s %s' % (row, lab, '/'.join(map(str, eos))) if lab != 'EO 1-5' else
                             '%s blisk (cyclic) EO margin, EO 1-5' % row, 100 * abs(w['margin']), 100 * req, '%',
                             abs(w['margin']) >= req and cov,
                             'ND %d family %d %.0f Hz%s%s%s' % (w['nd'], w['family'], w['f'], '' if req >= 0.10 else ', modes < %.0f Hz' % f_lim,
                                                               '; outside the band, %+.1f %% at 15k' % (100 * (w['f'] - eos[0] * 250.0) / (eos[0] * 250.0))
                                                               if lab == 'N1-N2' else '', '' if cov else '; NOT COVERED')))
        for k in inter:
            q = (cyc_w or {}).get(k)
            if not q: continue
            amp = lambda r: 1.0 / math.hypot(1 - r * r, 2 * ZETA * r)
            rb = [k * b * 250.0 / q['f'] for b in BAND]             # frequency ratio at the band edges
            r_w = 1.0 if (rb[0] - 1) * (rb[1] - 1) <= 0 else min(rb, key=lambda r: abs(r - 1))
            s_band, s_res, s_op = (s_gas * A_INT * amp(r) * MISTUNE for r in (r_w, 1.0, k * 250.0 / q['f']))
            out['blades'][row]['interaction_forced_response'] = dict(eo=k, nd=q['nd'], family=q['family'], f=q['f'],
                                                                     sigma_band=s_band, sigma_resonance=s_res, sigma_15k=s_op,
                                                                     A_int=A_INT, zeta=ZETA, mistune=MISTUNE)
            rows.append(('%s EO%d (N1-N2) forced response, estimate' % (row, k), s_band, sa_root / 2, 'MPa', s_band <= sa_root / 2,
                         'worst in band (15k %.1f, resonance %.1f MPa); %.0f %% load, zeta %.3f, x%.1f mistuning; Goodman/2' % (
                             s_op, s_res, 100 * A_INT, ZETA, MISTUNE)))
        # forced response from the CFD forcing on the cyclic modes: resonant root stress (design-point forcing, x mistuning)
        # vs Goodman / 2 over the damping range: PASS if it passes at the lower-bound damping, FAIL if it fails even at the
        # upper one, otherwise marginal (shown as reference: tip-timing decides)
        for k in sorted((int(q) for q in fr.get('orders', {})), key=lambda q: -q):
            q = fr['orders'][str(k)]; st = q['stress']; lim = fr['limit']
            out['blades'][row].setdefault('forced_response', {})[str(k)] = q
            ok = True if st[0]['root_res_mist'] <= lim else (False if st[-1]['root_res_mist'] > lim else None)
            v = st[0] if ok else (st[-1] if ok is False else st[1])
            rows.append(('%s EO%d resonance, %s (root)' % (row, k, 'band' if BAND[0] * 15000 <= q['n_res_rpm'] <= BAND[1] * 15000
                                                         else 'crossed at %.0f rpm' % q['n_res_rpm']),
                         v['root_res_mist'], lim, 'MPa', ok,
                         'ND%d F%d %.0f Hz; zeta %s %% + aero: %s MPa; x%.1f mistuning; in band %.2f MPa; Goodman/2%s' % (
                             q['nd'], q['family'], q['f_mode'], '/'.join('%.2g' % (100 * r['zeta_mech']) for r in st),
                             '/'.join('%.0f' % r['root_res_mist'] if r['root_res_mist'] >= 10 else '%.1f' % r['root_res_mist']
                                      for r in st), fr['mistune'], st[0]['root_band_mist'],
                             '' if ok is not None else '; MARGINAL')))
        print('%s blade: net section %.0f MPa (FE %.0f, P/A %.0f) at %.0f C (hub T0rel) -> min-curve life %.1e h (typ %.1e), '
              'allowable 1e5 h %.0f MPa; peak vm %.0f (margin %.2f); Goodman allow %.0f MPa root / %.0f peak; gas bending ~%.0f MPa; '
              'EO band margins NPF %.1f %%, weak %.1f %%, EO1-5 %.1f %%' % (
                  row, s_root, s['srr_root_mean'], s_pa, T_root, life, life_typ, s_allow, s['vm_max'], y_margin, sa_root, sa_peak,
                  s_gas, 100 * worst, 100 * worst_weak, 100 * worst_low))
        # tip clearance budget
        if disc:
            d = disc['%s_op' % row]
            stretch = blade_tip_stretch(row)
            if stretch is None:                                # .frd not kept (not in git): the stretch of the last run
                stretch = ((prev or {}).get('tips', {}).get(row) or {}).get('blade_stretch')
            rh, rt = A.row_radius(row, 0.0), A.row_radius(row, 1.0)
            a_b = float(np.interp(T, MAT_T, MAT_ALPHA)); th = a_b * (T - 20) * (rt - rh)
            rotor = d['u_rim_mm'] + (stretch or 0.0) + th
            r_cas = max(A.r_tip(A.X_LE[row]), A.r_tip(A.X_TE[row]))
            cold = A.TIP_CL[row]
            dT_need = (rotor + TARGET_CLEAR[row] - cold) / (ALPHA_CARRIER * r_cas)
            out['tips'][row] = dict(disc_rim_growth=d['u_rim_mm'], blade_stretch=stretch, blade_thermal=th, rotor_growth=rotor,
                                    cold_clearance=cold, casing_r=r_cas, target_running=TARGET_CLEAR[row],
                                    carrier_T_needed_C=20 + dT_need)
            print('   tip clearance: disc rim %.2f + blade stretch %.2f + blade thermal %.2f = rotor %.2f mm; cold %.2f mm -> '
                  'shroud carrier (1.4828) must run at %.0f C for %.2f mm running clearance' % (
                      d['u_rim_mm'], stretch or 0.0, th, rotor, cold, 20 + dT_need, TARGET_CLEAR[row]))
            rows.append(('%s tip carrier temperature' % row, 20 + dT_need, CARRIER_T_MAX, 'C', 20 + dT_need <= CARRIER_T_MAX,
                         'needed for %.2f mm running (requirement)' % TARGET_CLEAR[row]))
    if disc:
        for row in ('R1', 'R2'):
            d, t, dm = disc['%s_op' % row], disc['%s_trip' % row], disc.get('%s_op_mech' % row, disc['%s_op' % row])
            out['discs'][row] = dict(op=d, trip=t, op_mech=dm)
            rows += [('%s disc yield margin (trip)' % row, t['margin_yield'], 1.0, '-', t['margin_yield'] >= 1.0, 'vm %.0f MPa (total)' % t['vm_max']),
                     ('%s disc burst / 15k' % row, d['burst_ratio'], 1.22 * 1.10, 'x', d['burst_ratio'] >= 1.22 * 1.10, '>= 1.22 x trip, area-mean hoop'),
                     ('%s disc creep (primary, min curve)' % row, dm['creep_life_h'], LIFE_TARGET, 'h',
                      dm['creep_life_h'] >= LIFE_TARGET, '%.0f MPa @ %.0f C, r %.0f' % (dm['creep_vm'], dm['creep_T'], dm['creep_at'][0]))]
            # LCF of a start-stop cycle 0 -> 15,000 rpm (+ thermal) -> 0 (total stress, elastic range, Morrow mean stress)
            pts = [('peak', d['vm_max'], d['T_at_max'], 1.0, True), ('centre', d['vm_centre'], d['T_centre'], 1.0, True)]
            if d.get('plat_hoop'):
                # platform: thermal (strain-controlled) hoop x Kt 1.3 at the blade fillets, 690-800 C: the mean stress relaxes,
                # out-of-phase TMF of cast MAR-M247 follows the isothermal strain-life at T_max (Boismier & Sehitoglu 1990):
                # no tensile mean-stress correction
                pts.append(('platform', d['plat_hoop']['min'], d['plat_hoop']['T'], 1.3, False))
            for lab, sv, T, kt, mean in pts:
                sv = abs(sv) * kt
                de = sv / float(np.interp(T, MAT_T, MAT_E)); Nl = manson_cycles(de, T, sv if mean else 0.0); Ng = grainex_lb_cycles(de)
                out['discs'][row]['lcf_%s' % lab] = dict(vm=sv, T=T, Kt=kt, d_eps=de, cycles=Nl, grainex_lb=Ng)
                rows.append(('%s disc LCF starts (%s)' % (row, lab), Nl, STARTS_REQ, 'cyc', Nl >= STARTS_REQ,
                             '%.0f MPa%s @ %.0f C, de %.2f %%; Grainex LB %.1e' % (sv, ' (Kt %.1f)' % kt if kt > 1 else '', T, 100 * de, Ng)))
                print('%s disc LCF %s: %.0f MPa at %.0f C, strain range %.3f %% -> %.1e starts (Manson-Morrow, 2/20); '
                      'Grainex 649 C lower bound %.1e' % (row, lab, sv, T, 100 * de, Nl, Ng))
    if rd:
        sel = rd[rd['selected']]
        for c in sel['damped_criticals']:
            rows.append(('rotor critical %.0f rpm (AF %.1f)' % (c['N'], c['AF']), c['SM'], c['SM_req'], '%', c['ok'],
                         'mode %d, log dec %.2f' % (c['mode'], c['logdec'])))
        amax = max(sel['amp_max_operating_um'].values()); lim = 25.4 * math.sqrt(12000 / 15750.0)
        rows.append(('rotor unbalance response (API)', amax, lim, 'um', amax <= lim, 'pk-pk at the journals'))
        out['rotor'] = dict(selected=rd['selected'], criticals=sel['damped_criticals'], amp_max_um=amax, limit_um=lim)
    out['sheet'] = [dict(test=t, value=v, limit=l, unit=u, ok=None if o is None else bool(o), note=n) for t, v, l, u, o, n in rows]
    json.dump(out, open(os.path.join(FEA, 'a1000_turbine_checks.json'), 'w'), indent=1, default=float)
    print('\n%-44s %12s %12s  %s' % ('check', 'value', 'limit', 'result'))
    for t, v, l, u, o, n in rows:
        fmt = (lambda z: '%.2e' % z) if u in ('h', 'cyc') else (lambda z: '%.2f' % z if abs(z) < 10 else '%.0f' % z)
        print('%-44s %10s %-3s %10s %-3s %s  %s' % (t, fmt(v), u, fmt(l), u, 'info' if o is None else ('PASS' if o else 'FAIL'), n))
    crit = [r for r in rows if r[4] is not None]
    print('%d checks, %d pass, %d fail (+ %d for reference)' % (len(crit), sum(1 for r in crit if r[4]),
                                                               sum(1 for r in crit if not r[4]), len(rows) - len(crit)))
    plot(rows)


def plot(rows):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 0.42 * len(rows) + 1.4), dpi=110)
    ys = np.arange(len(rows))[::-1]
    for y, (t, v, l, u, o, n) in zip(ys, rows):
        # margin ratio: >1 passes (for the carrier temperature and the vibration the limit is an upper bound)
        upper = u in ('C', 'um', 'MPa')
        if u == '%': ratio = (v + 1e-9) / l if l > 0 else 2.0 + min(v / 50, 1.0)
        elif upper: ratio = l / v
        elif u in ('h', 'cyc'): ratio = math.log10(max(v, 1.0)) / math.log10(l)
        else: ratio = v / l
        ratio = min(ratio, 3.0)
        ax.barh(y, ratio, color='#9e9e9e' if o is None else ('#2e7d32' if o else '#c62828'), alpha=0.85)
        lab = ('%.1e %s' % (v, u)) if u in ('h', 'cyc') else ('%.2f %s' % (v, u) if abs(v) < 10 else '%.0f %s' % (v, u))
        ax.text(min(ratio, 3.0) + 0.03, y, '%s   (%s)' % (lab, n), va='center', fontsize=7.5)
    ax.axvline(1.0, color='k', lw=1.2)
    ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(0, 4.6); ax.set_xlabel('margin ratio (value / requirement; lives and cycles on a log scale; 1 = limit)')
    ax.set_title('AURORA-1000 turbine design checks (FE: CalculiX; green = pass, grey = reference only)', fontsize=11)
    ax.grid(axis='x', alpha=0.3); fig.tight_layout()
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_turbine_checks.png')); print('written docs/img/a1000_turbine_checks.png')


if __name__ == '__main__':
    main()
