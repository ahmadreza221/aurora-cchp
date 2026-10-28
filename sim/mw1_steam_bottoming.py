# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "iapws"]
# ///
"""AURORA-1000 with a steam bottoming cycle: which gas-turbine cycle + steam turbine gives 1000 kWe NET at the
lowest gas use (Borazjan, 20 kV grid). Gas turbine from sim/mw1_concept_study.py, steam with IAPWS-97.

Steam cycle: single-pressure HRSG (superheater, evaporator, economiser; pinch 15 K, approach 5 K, stack >= 100 C,
deaerator 105 C), condensing steam turbine (isentropic 0.70 for 100-500 kW class, geared to 1500 rpm), condenser at
50 C (cooling tower, Borazjan summer wet bulb ~28-29 C), generator + gear 0.94, feed pump 0.65, cooling-tower fans and
condensate pumps 2 % of the condenser heat.  An ORC (13 % of the recovered heat) is listed for comparison.
Run:  python3 sim/mw1_steam_bottoming.py        writes sim/mw1_steam_results.json
"""
import json
import math
import os

from iapws import IAPWS97

import mw1_concept_study as G

HERE = os.path.dirname(os.path.abspath(__file__))
P_TARGET = 1000e3
T_COND = 323.15
ETA_ST, ETA_GEN_ST, ETA_PUMP = 0.70, 0.94, 0.65
PINCH, APPROACH, T_STACK_MIN, T_DEA = 15.0, 5.0, 373.15, 378.15
SITE = 'design_chilled'
EXTRA_DP_HRSG = 0.010        # HRSG gas-side pressure drop (fraction of ambient) added to the turbine back pressure


def steam_cycle(m_g, gas, T_g_in, p_MPa):
    """steam power from an exhaust stream m_g [kg/s] of Mix gas at T_g_in [K]; returns dict or None if infeasible"""
    sat = IAPWS97(P=p_MPa, x=0); Tsat = sat.T
    if T_g_in < Tsat + PINCH + 20: return None
    T_sh = min(T_g_in - 25.0, 723.15)
    if T_sh < Tsat + 10: return None
    sh = IAPWS97(P=p_MPa, T=T_sh)
    h_eco_out = IAPWS97(P=p_MPa, T=Tsat - APPROACH).h * 1e3
    q_hi = m_g * (gas.h(T_g_in) - gas.h(Tsat + PINCH))          # superheater + evaporator duty
    ms = q_hi / (sh.h * 1e3 - h_eco_out)
    fw = IAPWS97(P=p_MPa, T=T_DEA)
    q_eco = ms * (h_eco_out - fw.h * 1e3)
    h_stack = gas.h(Tsat + PINCH) - q_eco / m_g
    T_stack = gas.T_of_h(h_stack, 420.0)
    if T_stack < T_STACK_MIN:                                     # economiser limited by the stack -> less steam
        q_tot = m_g * (gas.h(T_g_in) - gas.h(T_STACK_MIN))
        ms = q_tot / (sh.h * 1e3 - fw.h * 1e3); T_stack = T_STACK_MIN
    q_in = ms * (sh.h * 1e3 - fw.h * 1e3)
    p_c = IAPWS97(T=T_COND, x=0).P
    s_exp = IAPWS97(P=p_c, s=sh.s)
    h_ex = sh.h - ETA_ST * (sh.h - s_exp.h)
    ex = IAPWS97(P=p_c, h=h_ex)
    w_t = ms * (sh.h - h_ex) * 1e3
    cond = IAPWS97(T=T_COND, x=0)
    w_p = ms * cond.v * (p_MPa - p_c) * 1e6 / ETA_PUMP
    q_cond = ms * (h_ex - cond.h) * 1e3
    P_net = w_t * ETA_GEN_ST - w_p - 0.02 * q_cond
    return dict(p_bar=p_MPa * 10, T_sh_C=T_sh - 273.15, ms=ms, q_in=q_in, T_stack_C=T_stack - 273.15, x_exit=ex.x,
                P_gross=w_t * ETA_GEN_ST, P_net=P_net, q_cond=q_cond, eta_rankine=P_net / q_in)


def best_steam(m_g, gas, T_g_in):
    best = None
    for p_bar in (5, 8, 10, 15, 20, 25, 30, 40, 50):
        s = steam_cycle(m_g, gas, T_g_in, p_bar / 10.0)
        if s and s['x_exit'] > 0.85 and (best is None or s['P_net'] > best['P_net']):
            best = s
    return best


def combined(c, bottom='steam'):
    c = dict(c); c['dp_exh'] = G.BASE['dp_exh'] + (EXTRA_DP_HRSG if bottom else 0.0)
    r = G.cycle(c, SITE)                                          # per kg/s air
    gas, m_ex = r['gas'], r['m_ex']
    if bottom == 'steam':
        s = best_steam(m_ex, gas, r['T6'])
        p_b = s['P_net'] if s else 0.0
    elif bottom == 'orc':
        q = m_ex * (gas.h(r['T6']) - gas.h(373.15)); p_b = 0.13 * q * 0.96; s = dict(P_net=p_b, q_in=q)
    else:
        s, p_b = None, 0.0
    ma = P_TARGET / (r['P_net'] + p_b)
    fuel = r['Q_fuel'] * ma
    return dict(ma=ma, P_gt=r['P_net'] * ma, P_bot=p_b * ma, eta=P_TARGET / fuel, gas_m3h=fuel / G.LHV_VOL * 3600,
                T_exh_gt=r['T6'] - 273.15, booster_kW=r['booster'] * ma / 1e3, steam={k: (v * ma if k in
                ('ms', 'q_in', 'P_gross', 'P_net', 'q_cond') else v) for k, v in (s or {}).items()}, P3=r['P3'] / 1e5)


CASES = [
    ('A', 'recuperated GT alone, PR 3.8 / 950 C (proposed AURORA-1000)', dict(G.ARCH['R38'], eta_c=0.838, eta_t=0.901), None),
    ('B', 'A + small steam turbine on the 250 C exhaust', dict(G.ARCH['R38'], eta_c=0.838, eta_t=0.901), 'steam'),
    ('C', 'A + ORC on the 250 C exhaust (comparison)', dict(G.ARCH['R38'], eta_c=0.838, eta_t=0.901), 'orc'),
    ('D', 'partial recuperator eps 0.60 + steam turbine', dict(G.ARCH['R38'], eta_c=0.838, eta_t=0.901, eps=0.60), 'steam'),
    ('E', 'no recuperator, PR 3.8 / 950 C (no booster) + steam turbine', dict(G.ARCH['R38'], eta_c=0.838, eta_t=0.901, eps=0.0), 'steam'),
    ('F', 'no recuperator, PR 8 / 1000 C + gas booster + steam turbine', dict(PR=8.0, TIT=1273.15, eta_c=0.83, eta_t=0.89,
                                                                             booster=True), 'steam'),
    ('G', 'no recuperator, PR 12 / 1100 C (cooled blades) + booster + steam', dict(PR=12.0, TIT=1373.15, eta_c=0.82,
                                                                                  eta_t=0.88, booster=True, leak=0.05), 'steam'),
]


def main():
    out = {}
    print('%-3s %-62s %5s %6s %6s %6s %6s %7s %6s %6s %6s' % ('', 'case (1000 kWe net total)', 'air', 'P_GT', 'P_bot', 'eta',
          'gas', 'T_exh', 'p_st', 'T_sh', 'boost'))
    for key, name, c, bot in CASES:
        r = combined(c, bot)
        st = r['steam']
        print('%-3s %-62s %5.2f %6.0f %6.0f %6.1f %6.0f %7.0f %6s %6s %6.1f' % (
            key, name, r['ma'], r['P_gt'] / 1e3, r['P_bot'] / 1e3, r['eta'] * 100, r['gas_m3h'], r['T_exh_gt'],
            '%.0f' % st['p_bar'] if 'p_bar' in st else '-', '%.0f' % st['T_sh_C'] if 'T_sh_C' in st else '-', r['booster_kW']))
        out[key] = dict(name=name, **{k: v for k, v in r.items()})
    json.dump(out, open(os.path.join(HERE, 'mw1_steam_results.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
