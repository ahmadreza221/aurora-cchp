"""AURORA-1000 design-point performance with the detail-design results in place of the meanline assumptions.

The meanline cycle (sim/mw1_meanline.py, R38: PR 3.8, TIT 950 C, eta_c 0.838, eta_t 0.901) sized the air flow for
1,000 kW to the grid. The engine geometry is now fixed, so the air flow is held at that value and each detail result
is put into the cycle in turn (cumulative), giving a waterfall of grid power and electric efficiency:
  1. compressor   : overall PR and eta to the collector flange (sim/a1000_impeller_design.json, cad/engine/a1000_impeller.py)
  2. turbine      : row-chord changes of rev 5 (cad/engine/a1000_turbine.py notes: NGV2 26 -> 49 mm -0.8 pt, NGV1
                    26 -> 22 mm +0.3 pt) and the duct friction of the R1-NGV2 gap +25 mm (docs/08 12.4.2)
  3. combustor    : total pressure loss inlet nozzle -> NGV1 (sim/engine/fea/a1000_combustor.json)
  4. bearings     : journals + thrust + seals in kW (sim/engine/fea/a1000_rotor_stack.json) in place of eta_mech 0.994
  5. exhaust      : diffuser + collector (CFD), recuperator ducting (correlations), recuperator core / economizer
                    (vendor assumptions) in place of dp_exh 1.5 %, dp_rec_h 3.5 %, dp_rec_c 2.5 % (sim/engine/fea/a1000_exhaust.json)
Secondary air stays at the cycle allowance of 1.5 % (bypasses the turbine work); the labyrinths of the hot section use
part of it (sim/engine/fea/a1000_hot_section.json), the rest is for the NGV half-joint strip seals and other joints.
Then the TIT that brings the grid power back to 1,000 kW at the same air flow.
Run:  python3 sim/engine/a1000_performance.py      writes sim/engine/fea/a1000_performance.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'sim'))

import mw1_concept_study as G                                    # noqa: E402
import mw1_meanline as MLM                                       # noqa: E402
from mw1_concept_study import mar_m247_rupture_hours             # noqa: E402

SITE = 'design_chilled'
IMP = json.load(open(os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')))
TUR = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
ML = json.load(open(os.path.join(ROOT, 'sim', 'mw1_meanline.json')))
COMB = json.load(open(os.path.join(HERE, 'fea', 'a1000_combustor.json')))
RS = json.load(open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')))
HOT = json.load(open(os.path.join(HERE, 'fea', 'a1000_hot_section.json')))
TC = json.load(open(os.path.join(HERE, 'fea', 'a1000_turbine_checks.json')))
EXH = os.path.join(HERE, 'fea', 'a1000_exhaust.json')
LIFE_TARGET = 1.0e5                                              # h, R1 creep on the minimum curve (a1000_turbine_checks.py)
D_ETA_T_CHORDS = -0.008 + 0.003                                  # rev 5 row chords (Kacker-Okapuu secondary loss)
DGAP = 25.0                                                      # mm, R1 TE - NGV2 LE added (EO24 fix)
CF = 0.003                                                       # endwall skin friction


def gap_eta_loss():
    """total-pressure loss of the extra R1-NGV2 duct (two endwalls, Dh = 2 h) as a turbine efficiency change"""
    s1 = ML['turbine']['stages'][0]; c = ML['turbine']['Cx'] / math.cos(math.radians(8.5))      # alpha3 = -8.5 deg
    g = 1.33; T = s1['T0_out'] - c ** 2 / 2 / 1150.0; M = c / math.sqrt(g * 287.0 * T)
    st = TUR['annulus']['stations']; x_te = TUR['R1']['x_te']
    h = next(h0 + (h1 - h0) * (x_te - x0) / (x1 - x0) for (x0, h0), (x1, h1) in zip(st, st[1:]) if x0 <= x_te <= x1)
    dp0 = 4 * CF * DGAP / (2 * h) * g / 2 * M ** 2
    pr_t = ML['turbine']['stages'][0]['P0_in'] / ML['turbine']['stages'][-1]['P0_out']
    k = (g - 1) / g
    d_eta = -k * dp0 * s1['T0_out'] / (s1['T0_in'] * (1 - pr_t ** -k))
    return dict(M=M, h_mm=h, dp0_frac=dp0, d_eta_t=d_eta)


def point(case, ma, p_mech_W):
    """grid power [W] and efficiency at air flow ma; mechanical losses in W when given, else eta_mech of the cycle"""
    c = dict(G.BASE, **case)
    if p_mech_W is not None:
        c['eta_mech'] = 1.0
    r = G.cycle(c, SITE)
    p_shaft = r['P_shaft'] * ma - (p_mech_W or 0.0)
    p_el = p_shaft * c['eta_mech'] * c['eta_gear'] * c['eta_gen'] * (1 - c['aux_frac'])
    p_grid = p_el - MLM.AUX_CCHP
    q_fuel = r['Q_fuel'] * ma
    hw = MLM.cchp(r, ma)
    return dict(P_grid_kW=p_grid / 1e3, eta_el=p_el / q_fuel, eta_el_grid=p_grid / q_fuel, fuel_kW=q_fuel / 1e3,
                gas_Sm3_h=q_fuel / COMB['design_point']['LHV_MJ_Sm3'] / 1e6 * 3600, T_exh_C=r['T6'] - 273.15,
                q_hotwater_kW=hw['q_hotwater_kW'], q_cooling_kW=hw['q_cooling_kW'],
                eta_total=(p_grid + hw['q_hotwater_kW'] * 1e3) / q_fuel, P3_bar=r['P3'] / 1e5, TIT_C=c['TIT'] - 273.15)


def bisect(f, lo, hi):
    """root of an increasing f on [lo, hi]"""
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return 0.5 * (lo + hi)


def r1_creep_life(tit):
    """R1 root creep life on the minimum curve when the TIT moves: the uncooled hub runs at the relative total
    temperature, which scales with the TIT at a fixed speed (velocity triangles hardly change)"""
    b = TC['blades']['R1']; T0 = b['T_root_C'] + 273.15
    T = T0 * tit / MLM.CASE['TIT']
    return T - 273.15, mar_m247_rupture_hours(b['sigma_root'], T)


def asbuilt_steps():
    """meanline case, air flow, R1-NGV2 gap loss and the cumulative detail-design steps (name, case update, P_mech W)"""
    case = dict(MLM.CASE)
    r0 = G.cycle(case, SITE); ma = MLM.P_NET / r0['P_net']
    gap = gap_eta_loss()
    steps = [('meanline (R38: eta_c 0.838, eta_t 0.901, dp_comb 4.0 %, eta_mech 0.994)', {}, None)]
    o = IMP['overall']
    steps.append(('compressor detail: PR %.3f, eta %.3f to the collector' % (o['PR'], o['eta']),
                  dict(PR=o['PR'], eta_c=o['eta']), None))
    d_eta_t = D_ETA_T_CHORDS + gap['d_eta_t']
    steps.append(('turbine rev 5 chords %+.1f pt, R1-NGV2 gap +25 mm %+.2f pt' % (100 * D_ETA_T_CHORDS, 100 * gap['d_eta_t']),
                  dict(eta_t=case['eta_t'] + d_eta_t), None))
    dpc = COMB['pressure']['total_pct'] / 100
    steps.append(('combustor + scroll to NGV1: dP0 %.2f %%' % (100 * dpc), dict(dp_comb=dpc), None))
    p_mech = RS['losses']['total_kW'] * 1e3
    steps.append(('bearings + seals %.1f kW (cycle allowance %.1f kW)' % (RS['losses']['total_kW'], RS['losses']['cycle_allowance_kW']),
                  {}, p_mech))
    if os.path.exists(EXH):                                      # phase 2 (sim/engine/a1000_exhaust.py): computed duct losses
        ex = json.load(open(EXH))['dps_new']
        steps.append(('exhaust + recuperator ducting: dp_exh %.2f %%, dp_rec_h %.2f %%, dp_rec_c %.2f %% (was 1.5 / 3.5 / 2.5)'
                      % (100 * ex['dp_exh'], 100 * ex['dp_rec_h'], 100 * ex['dp_rec_c']), dict(ex), None))
    return case, ma, gap, steps


def asbuilt_case(n_steps=None):
    """cycle case, air flow and P_mech [W] after the first n_steps detail steps (all when None)"""
    case, ma, gap, steps = asbuilt_steps()
    cur, pm = dict(case), None
    for name, upd, pm_new in steps[:n_steps]:
        cur.update(upd); pm = pm_new if pm_new is not None else pm
    return cur, ma, pm


def main():
    case, ma, gap, steps = asbuilt_steps()
    rows, cur, pm = [], dict(case), None
    for name, upd, pm_new in steps:
        cur.update(upd); pm = pm_new if pm_new is not None else pm
        rows.append(dict(step=name, **point(cur, ma, pm)))
    t_req = bisect(lambda t: point(dict(cur, TIT=t), ma, pm)['P_grid_kW'] - 1000.0, case['TIT'] - 20, case['TIT'] + 120)
    t_life = bisect(lambda t: LIFE_TARGET - r1_creep_life(t)[1], case['TIT'] - 20, case['TIT'] + 120)
    fix = dict(step='as built, TIT raised to %.0f C for 1,000 kW' % (t_req - 273.15), **point(dict(cur, TIT=t_req), ma, pm))
    fix['R1_root_C'], fix['R1_creep_h_min'] = r1_creep_life(t_req)
    lim = dict(step='as built, TIT %.0f C (R1 creep 1e5 h, min curve)' % (t_life - 273.15), **point(dict(cur, TIT=t_life), ma, pm))
    lim['R1_root_C'], lim['R1_creep_h_min'] = r1_creep_life(t_life)
    sec = HOT['secondary_air']
    sec_pct = sec['drum_balance_seal']['pct'] + sec['interstage_seal']['pct']
    out = dict(air_kg_s=ma, site=SITE, gap=gap, case_asbuilt=dict(PR=cur['PR'], eta_c=cur['eta_c'], eta_t=cur['eta_t'],
               dp_comb=cur['dp_comb'], P_mech_kW=pm / 1e3, leak=G.BASE['leak'], dp_exh=cur.get('dp_exh', G.BASE['dp_exh']),
               dp_rec_h=cur.get('dp_rec_h', G.BASE['dp_rec_h']), dp_rec_c=cur.get('dp_rec_c', G.BASE['dp_rec_c'])), waterfall=rows, tit_for_1MW=fix,
               dTIT_K=t_req - case['TIT'], tit_life_limit=lim, dTIT_life_K=t_life - case['TIT'],
               shortfall_at_life_limit_kW=1000.0 - lim['P_grid_kW'],
               secondary_air=dict(allowance_pct=100 * G.BASE['leak'], labyrinths_bypassing_turbine_pct=sec_pct,
                                  left_for_joints_pct=100 * G.BASE['leak'] - sec_pct,
                                  backface_recirculation_pct=sec['backface_seal_r200']['pct']),
               open=['compressor inlet plenum and radial-inlet bend loss (cycle dp_inlet 1.0 % kept)',
                     'recuperator core dp (vendor quote; assumed 1.5 % air / 2.0 % gas) and economizer gas side (assumed 500 Pa)',
                     'turbine tip clearance 0.46 / 0.55 mm against the meanline eta_t (no row-by-row loss model yet)',
                     'disc windage of the turbine cavities', 'NGV half-joint strip seal leakage (inside the 1.5 % allowance)'])
    with open(os.path.join(HERE, 'fea', 'a1000_performance.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print('AURORA-1000 design point (%s), air %.3f kg/s fixed by the meanline sizing' % (SITE, ma))
    print('R1-NGV2 gap +25 mm: M %.2f, h %.1f mm, dP0 %.3f %%, d eta_t %+.3f pt' % (gap['M'], gap['h_mm'], 100 * gap['dp0_frac'],
                                                                                     100 * gap['d_eta_t']))
    print('%-78s %7s %6s %6s %6s %6s %6s' % ('step (cumulative)', 'P_grid', 'eta_el', 'd_pt', 'T_exh', 'gas', 'eta_tot'))
    prev = None
    for r in rows + [lim, fix]:
        d = 0.0 if prev is None else 100 * (r['eta_el_grid'] - prev)
        print('%-78s %7.1f %6.2f %+6.2f %6.1f %6.1f %6.1f' % (r['step'][:78], r['P_grid_kW'], 100 * r['eta_el_grid'], d,
                                                             r['T_exh_C'], r['gas_Sm3_h'], 100 * r['eta_total']))
        prev = r['eta_el_grid'] if r in rows else prev
    for r in (lim, fix):
        print('  %s: R1 root %.0f C, creep life %.0f h (min curve, target %.0f h)' % (r['step'], r['R1_root_C'],
                                                                                    r['R1_creep_h_min'], LIFE_TARGET))
    s = out['secondary_air']
    print('secondary air: allowance %.2f %%, hot-section labyrinths bypassing the turbine %.2f %%, left for joints %.2f %%'
          % (s['allowance_pct'], s['labyrinths_bypassing_turbine_pct'], s['left_for_joints_pct']))


if __name__ == '__main__':
    main()
