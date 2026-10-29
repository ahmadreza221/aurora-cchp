#!/usr/bin/env python3
"""AURORA-1000 turbine: summary of the structural checks (design review sheet) from the FE results.

Inputs (run first):  sim/engine/a1000_blade_fea.py R1 / R2   -> fea/a1000_blade_R1.json, _R2.json, a1000_R?_15k.frd
                     sim/engine/a1000_disc_fea.py           -> fea/a1000_disc.json
                     sim/engine/a1000_rotordynamics.py      -> fea/a1000_rotordynamics.json
Checks:
  blades  creep rupture of the net section above the fillet (Larson-Miller, 1.25 x stress), yield of the peak,
          engine-order interference at 15,000 rpm, allowable vibratory stress (Goodman), gas bending (estimate)
  discs   yield margin, burst margin (mean hoop, 85 % UTS), creep at the critical point (1.25 x stress)
  rotor   critical speeds vs API 617 separation margins, unbalance response
  tips    running tip clearance budget: disc rim growth (FE: centrifugal + thermal) + blade stretch (FE) + blade thermal
          growth vs the growth of the shroud carrier; carrier temperature needed for the target running clearance
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
from mw1_concept_study import mar_m247_rupture_hours           # noqa: E402
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_turbine as A                                     # noqa: E402
sys.argv = _argv

LIFE_TARGET = 1.0e5                                            # h, hot-section design life (with 1.25 x stress)
MAT_T = np.array([20., 400., 600., 800., 900., 1000.])
MAT_UTS = np.array([965., 980., 1000., 965., 830., 650.])      # MAR-M247 cast, typical
MAT_ALPHA = np.array([11.0, 12.6, 13.4, 14.4, 15.0, 15.6]) * 1e-6   # mean CTE from 20 C
SIG_E = dict(R1=200.0, R2=230.0)                               # HCF 1e7, R = -1, cast surface, at the metal temperature [MPa]
ALPHA_CARRIER = 17.8e-6                                        # shroud carrier 1.4828 (X15CrNiSi20-12), mean 20..500 C
TARGET_CLEAR = dict(R1=0.45, R2=0.55)                          # running tip clearance target [mm] (~1.3 % / 1.0 % of height)


MAT_E = np.array([200e3, 186e3, 176e3, 163e3, 156e3, 148e3])  # MPa (same table as the FE models)
RA = 0.06                                                      # reduction of area, cast MAR-M247 at 600-800 C (typical)
STARTS_REQ = 10000                                             # start-stop cycles: ~1 a day for 27 years


def manson_cycles(d_eps, T):
    """LCF life by Manson's universal slopes, d_eps = 3.5 Su/E N^-0.12 + D^0.6 N^-0.6, with the design factors
    2 on strain / 20 on life (the smaller life)"""
    Su, E = float(np.interp(T, MAT_T, MAT_UTS)), float(np.interp(T, MAT_T, MAT_E)); D = -math.log(1 - RA)
    def N_of(de):
        lo, hi = 0.0, 12.0
        for _ in range(80):
            m = 0.5 * (lo + hi); N = 10 ** m
            if 3.5 * Su / E * N ** -0.12 + D ** 0.6 * N ** -0.6 > de: lo = m
            else: hi = m
        return 10 ** lo
    return min(N_of(2 * d_eps), N_of(d_eps) / 20)


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
    disc = load('a1000_disc.json'); rd = load('a1000_rotordynamics.json')
    for row in ('R1', 'R2'):
        b = load('a1000_blade_%s.json' % row)
        if b is None: print('%s: blade FEA results missing' % row); continue
        T = b['metal_C']; s = b['stress']
        uts = float(np.interp(T, MAT_T, MAT_UTS))
        s_root = s['srr_root_mean']
        life = mar_m247_rupture_hours(1.25 * s_root, T + 273.15)
        life_nom = mar_m247_rupture_hours(s_root, T + 273.15)
        # spanwise: creep of the higher sections (stress falls faster than the temperature: root governs)
        span_life = {k: mar_m247_rupture_hours(1.25 * v, T + 273.15) for k, v in s.items() if k.startswith('srr_mean_') and v}
        y_margin = b['yield_MPa'] / s['vm_max']
        # Goodman: allowable alternating stress at the root mean section and at the peak (local) point
        sa_root = SIG_E[row] * (1 - s_root / uts); sa_peak = SIG_E[row] * max(0.0, 1 - s['vm_max'] / uts)
        crit = b['critical']
        # stator orders: strong = 1 x NPF of the adjacent rows (10 %), weak = 2 x NPF and wakes through two rows (5 %)
        v = b.get('vanes', {}); n1, n2 = v.get('N1', 43), v.get('N2', 47)
        strong = (n1, n2) if row == 'R1' else (n2,)
        weak = (2 * n1,) if row == 'R1' else (n1, 2 * n2)
        mg = lambda eos: min((abs(r['margin']) for r in b['interference'] if r['eo'] in eos), default=None)
        worst, worst_weak, worst_low = mg(strong), mg(weak), mg((1, 2, 3, 4, 5))
        # gas bending: tangential force per blade from the stage work, at mid span (estimate, section modulus ~ 0.1 c t^2)
        mdot = 6.32 * 1.017; dh = A.ML['turbine']['dh_tot'] / 2; U_m = A.RM * 1e-3 * A.OM
        Ft = mdot * dh / U_m / A.Z[row]                         # N per blade (torque / (r_m Z))
        h = (A.row_radius(row, 1.0) - A.row_radius(row, 0.0)) * 1e-3
        des = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))[row]['sections'][0]
        Wz = 0.10 * des['chord'] * des['tmax'] ** 2 * 1e-9      # m3 about the weak axis (thin cambered section)
        s_gas = Ft * h / 2 / Wz / 1e6
        out['blades'][row] = dict(metal_C=T, sigma_root_mean=s_root, sigma_root_max=s['srr_root_max'], vm_max=s['vm_max'],
                                  vm_p99=s['vm_p99'], creep_life_h=life_nom, creep_life_h_x125=life, span_creep_x125=span_life,
                                  yield_margin_peak=y_margin, goodman_allow_root=sa_root, goodman_allow_peak=sa_peak,
                                  interference_critical=crit, worst_margin_npf=worst, worst_margin_weak=worst_weak,
                                  worst_margin_low_orders=worst_low,
                                  gas_force_N=Ft, gas_bending_MPa=s_gas, freqs_15k=b['freqs'][str(15000)])
        rows += [('%s blade creep (root, x1.25 stress)' % row, life, LIFE_TARGET, 'h', life >= LIFE_TARGET, '%.0f MPa @ %.0f C' % (s_root, T)),
                 ('%s blade peak / yield' % row, y_margin, 1.0, '-', y_margin >= 1.0, 'vm %.0f MPa (local, fillet/TE)' % s['vm_max']),
                 ('%s blade EO margin, NPF %s' % (row, '/'.join(map(str, strong))), 100 * worst, 10.0, '%', worst >= 0.10,
                  'NGV wakes / potential field, at 15k (rigid hub)'),
                 ('%s blade EO margin, weak %s' % (row, '/'.join(map(str, weak))), 100 * worst_weak, 5.0, '%', worst_weak >= 0.05,
                  '2 x NPF, wakes through 2 rows'),
                 ('%s blade EO margin (EO 1-5)' % row, 100 * worst_low if worst_low is not None else float('nan'), 10.0, '%',
                  worst_low is not None and worst_low >= 0.10, 'low orders')]
        print('%s blade: root net section %.0f MPa (max %.0f) at %.0f C -> creep %.1e h (%.1e h x1.25); peak vm %.0f MPa '
              '(margin %.2f); Goodman allow %.0f MPa (root) / %.0f MPa (peak); gas bending ~%.0f MPa (F %.0f N); '
              'EO margin NPF %.1f %%, weak orders %.1f %%, EO1-5 %.1f %%' % (
                  row, s_root, s['srr_root_max'], T, life_nom, life, s['vm_max'], y_margin, sa_root, sa_peak, s_gas, Ft,
                  100 * worst, 100 * worst_weak, 100 * worst_low))
        # tip clearance budget
        if disc:
            d = disc['%s_op' % row]
            stretch = blade_tip_stretch(row)
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
            rows.append(('%s tip carrier temperature' % row, 20 + dT_need, 520.0, 'C', 20 + dT_need <= 520.0,
                         'needed for %.2f mm running' % TARGET_CLEAR[row]))
    if disc:
        for row in ('R1', 'R2'):
            d, t = disc['%s_op' % row], disc['%s_trip' % row]
            out['discs'][row] = dict(op=d, trip=t)
            rows += [('%s disc yield margin (trip)' % row, t['margin_yield'], 1.0, '-', t['margin_yield'] >= 1.0, 'vm %.0f MPa' % t['vm_max']),
                     ('%s disc burst / 15k' % row, d['burst_ratio'], 1.22 * 1.10, 'x', d['burst_ratio'] >= 1.22 * 1.10, '>= 1.22 x trip'),
                     ('%s disc creep (x1.25 stress)' % row, d['creep_life_h_x125'], LIFE_TARGET, 'h',
                      d['creep_life_h_x125'] >= LIFE_TARGET, '%.0f MPa @ %.0f C' % (d['creep_vm'], d['creep_T']))]
            # LCF of a start-stop cycle 0 -> 15,000 rpm (+ thermal) -> 0 at the peak point and at the centre (elastic range)
            for lab, sv, T in (('peak', d['vm_max'], d['T_at_max']), ('centre', d['vm_centre'], d['T_centre'])):
                de = sv / float(np.interp(T, MAT_T, MAT_E)); Nl = manson_cycles(de, T)
                out['discs'][row]['lcf_%s' % lab] = dict(vm=sv, T=T, d_eps=de, cycles=Nl)
                rows.append(('%s disc LCF starts (%s)' % (row, lab), Nl, STARTS_REQ, 'cyc', Nl >= STARTS_REQ,
                             '%.0f MPa @ %.0f C, de %.2f %%, factors 2 / 20' % (sv, T, 100 * de)))
                print('%s disc LCF %s: %.0f MPa at %.0f C, strain range %.3f %% -> %.1e starts' % (row, lab, sv, T, 100 * de, Nl))
    if rd:
        sel = rd[rd['selected']]
        for c in sel['damped_criticals']:
            rows.append(('rotor critical %.0f rpm (AF %.1f)' % (c['N'], c['AF']), c['SM'], c['SM_req'], '%', c['ok'],
                         'mode %d, log dec %.2f' % (c['mode'], c['logdec'])))
        amax = max(sel['amp_max_operating_um'].values()); lim = 25.4 * math.sqrt(12000 / 15750.0)
        rows.append(('rotor unbalance response (API)', amax, lim, 'um', amax <= lim, 'pk-pk at the journals'))
        out['rotor'] = dict(selected=rd['selected'], criticals=sel['damped_criticals'], amp_max_um=amax, limit_um=lim)
    out['sheet'] = [dict(test=t, value=v, limit=l, unit=u, ok=bool(o), note=n) for t, v, l, u, o, n in rows]
    json.dump(out, open(os.path.join(FEA, 'a1000_turbine_checks.json'), 'w'), indent=1, default=float)
    print('\n%-42s %12s %12s  %s' % ('check', 'value', 'limit', 'result'))
    for t, v, l, u, o, n in rows:
        fmt = (lambda z: '%.2e' % z) if u in ('h', 'cyc') else (lambda z: '%.2f' % z if abs(z) < 10 else '%.0f' % z)
        print('%-42s %10s %-2s %10s %-2s %s  %s' % (t, fmt(v), u, fmt(l), u, 'PASS' if o else 'FAIL', n))
    plot(rows)


def plot(rows):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 0.42 * len(rows) + 1.4), dpi=110)
    ys = np.arange(len(rows))[::-1]
    for y, (t, v, l, u, o, n) in zip(ys, rows):
        # margin ratio: >1 passes (for the carrier temperature and the vibration the limit is an upper bound)
        upper = u in ('C', 'um')
        if u == '%': ratio = (v + 1e-9) / l if l > 0 else 2.0 + min(v / 50, 1.0)
        elif upper: ratio = l / v
        elif u in ('h', 'cyc'): ratio = math.log10(max(v, 1.0)) / math.log10(l)
        else: ratio = v / l
        ratio = min(ratio, 3.0)
        ax.barh(y, ratio, color='#2e7d32' if o else '#c62828', alpha=0.85)
        lab = ('%.1e %s' % (v, u)) if u in ('h', 'cyc') else ('%.2f %s' % (v, u) if abs(v) < 10 else '%.0f %s' % (v, u))
        ax.text(min(ratio, 3.0) + 0.03, y, '%s   (%s)' % (lab, n), va='center', fontsize=7.5)
    ax.axvline(1.0, color='k', lw=1.2)
    ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(0, 4.6); ax.set_xlabel('margin ratio (value / requirement; lives and cycles on a log scale; 1 = limit)')
    ax.set_title('AURORA-1000 turbine design checks (FE: CalculiX; green = pass)', fontsize=11)
    ax.grid(axis='x', alpha=0.3); fig.tight_layout()
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_turbine_checks.png')); print('written docs/img/a1000_turbine_checks.png')


if __name__ == '__main__':
    main()
