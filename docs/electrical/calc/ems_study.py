# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP energy management (EMS): net electric power vs cooling for each EMS mode.

Source of truth for the HVAC side (chillers, pumps, tower, hall, auxiliary power) is the HVAC session's mode model:
sim/hvac/hvac_results.json ['modes'] (written by sim/hvac/hvac_design.py, same Borazjan design hour 46 C DB / 28 C WB).
This script adds only the ENGINE-side levers the ECU owns, using the same cycle model (sim/life_study.py):
  * intake set-point T1 = 12 C instead of 15 C in MAX-POWER (more coil load, taken from the hall share)
  * peak TIT 815 C in MAX-POWER (counted by the life counter)
and the break-even of the intake coil versus outdoor temperature, plus an AUTO example.
Rev 3 (user's real loads, grid as automatic backup with zero export, 20 kWh HV battery):
  * v1 zero-export / island part-load operating points for the real site load (5 kW typical, 8 kW peak)
  * cooling available at part load (exhaust heat scaled from the HVAC design point) and the hall share left after the coil
  * v2 grid export at full power
Run:  python3 docs/electrical/calc/ems_study.py      (re-run after python3 sim/hvac/hvac_design.py)
"""
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'sim'))
sys.path.insert(0, os.path.join(ROOT, 'sim', 'hvac'))
import hvac_design as H      # noqa: E402
import life_study as L       # noqa: E402

RES = json.load(open(os.path.join(ROOT, 'sim', 'hvac', 'hvac_results.json')))
MODES = RES['modes']
COP_SPLIT = 2.6              # company split/packaged AC at ~45 C (cchp_study.COP_SPLIT)
COIL_DP_PENALTY = 0.35       # kW, intake-coil air-side pressure drop (roof_site_study), same as the HVAC model


def p_eng(T1, TIT=800):
    """AC power after the engine's own auxiliaries, intake air at T1 (same basis as MODES[...]['P_eng'])."""
    r = L.point(115e3, TIT, 'target', T_amb_C=T1, alt_m=H.ALT, booster=False)
    return r['P_el'] / 1e3 - COIL_DP_PENALTY, r['ma']


def engine_levers():
    base = MODES['MAX-POWER']
    p15, ma15 = p_eng(15.0)
    rows = []
    for lab, T1, TIT in (('MAX-POWER (HVAC model, T1 15 C)', 15.0, 800), ('MAX-POWER, T1 12 C', 12.0, 800),
                         ('MAX-POWER, T1 12 C + TIT 815 C', 12.0, 815)):
        p, ma = p_eng(T1, TIT)
        coil = H.coil_kW(T1, ma)
        d_coil = coil - base['coil']
        hall = max(base['hall'] - d_coil, 0.0)
        coil_short = max(d_coil - base['hall'], 0.0)          # coil limited by CH-1 if the hall share is exhausted
        dP = p - p15
        net = base['net'] + dP
        rows.append(dict(mode=lab, T1=T1, TIT=TIT, P_eng=base['P_eng'] + dP, coil=coil, hall=hall, aux=base['aux'], net=net,
                         el_eq=net + (hall + base['er']) / COP_SPLIT, note='coil short %.1f kW' % coil_short if coil_short > 0.1 else ''))
    return rows


SITE_KW = dict(typical=5.0, peak=8.0)      # user: 1 pump 3 kW (VFD), 3 split AC 12k BTU, lamps, PCs, fridge, TV
CTRL_KW = 0.3                               # 48 V chargers, controls, network, HMI (on AC)
CHARGE_KW = 2.0                             # battery recharge allowance while running
RATIO_COOL_PER_QCHP = None                  # filled from the HVAC design point (cooling / recoverable heat)


def pel(n, tit, t1=15.0):
    return L.point(n, tit, 'target', T_amb_C=t1, alt_m=H.ALT, booster=False)['P_el'] / 1e3


def bisect(f, lo, hi, target):
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return 0.5 * (lo + hi)


def operating_point(p_target, tit_part=750.0, n_min=100e3):
    """Best-efficiency way to make p_target (kW AC): lowest core speed at TIT_part (recuperated cycle: high TIT, low speed is
    most efficient); below P(n_min, TIT_part) lower the TIT at n_min (speed-line data start at 100k); above P(115k, TIT_part)
    raise TIT towards 800 C at 115k."""
    if p_target <= pel(n_min, tit_part):
        return n_min, bisect(lambda t: pel(n_min, t), 550.0, tit_part, p_target)
    if p_target <= pel(115e3, tit_part):
        return bisect(lambda n: pel(n, tit_part), n_min, 115e3, p_target), tit_part
    return 115e3, bisect(lambda t: pel(115e3, t), tit_part, 800.0, min(p_target, pel(115e3, 800.0)))


def part_load():
    full = L.point(115e3, 800, 'target', T_amb_C=15.0, alt_m=H.ALT, booster=False)
    bal = MODES['BALANCED']
    k_cool = bal['cool'] / (full['Q_chp'] / 1e3)
    aux = bal['aux'] + CTRL_KW
    print('\nv1: grid as automatic backup, ZERO EXPORT (and island in a grid outage): turbine follows the site load')
    print('  HVAC aux %.2f kW (BALANCED) + controls %.1f kW; cooling per kW of recoverable heat %.3f (HVAC design point %.1f kW / %.1f kW)'
          % (bal['aux'], CTRL_KW, k_cool, bal['cool'], full['Q_chp'] / 1e3))
    print('  %-26s %6s | %5s %5s | %6s %6s | %6s %6s %6s %6s | %9s' % ('case', 'P_req', 'N1 k', 'TIT', 'P_el', 'eta', 'Q_rec', 'cool', 'coil', 'hall', 'blade h'))
    print('  (rule: TIT 750 C and the lowest speed; below 13.7 kW lower TIT at 100k; peak TIT 800 C only for export)')
    rows = []
    for lab, site, chg in (('typical 5 kW', SITE_KW['typical'], 0.0), ('typical + recharge', SITE_KW['typical'], CHARGE_KW),
                           ('peak 8 kW', SITE_KW['peak'], 0.0), ('peak + recharge', SITE_KW['peak'], CHARGE_KW)):
        p_req = site + aux + chg
        n, tit = operating_point(p_req)
        r = L.point(n, tit, 'target', T_amb_C=15.0, alt_m=H.ALT, booster=False)
        cool = k_cool * r['Q_chp'] / 1e3
        coil = H.coil_kW(15.0, r['ma'])
        hall = max(cool - coil, 0.0)
        rows.append(dict(case=lab, P_req=p_req, N1=n, TIT=tit, P_el=r['P_el'] / 1e3, eta=r['eta_el'], Q_rec=r['Q_chp'] / 1e3,
                         cool=cool, coil=coil, hall=hall, life=min(r['life_blade'], 9.99e6)))
        print('  %-26s %6.1f | %5.1f %5.0f | %6.1f %5.1f%% | %6.1f %6.1f %6.1f %6.1f | %9.0f' % (
            lab, p_req, n / 1e3, tit, r['P_el'] / 1e3, r['eta_el'] * 100, r['Q_chp'] / 1e3, cool, coil, hall, min(r['life_blade'], 9.99e6)))
    n, tit = 100e3, 750.0
    r = L.point(n, tit, 'target', T_amb_C=15.0, alt_m=H.ALT, booster=False)
    print('  alternative for low load: 100k / 750 C = %.1f kW at %.1f %% and the surplus into the battery / EH-950 (battery cycling ~12 %% loss)'
          % (r['P_el'] / 1e3, r['eta_el'] * 100))
    print('  hall cooling demand (insulated hall, HVAC rev B): %.1f kW -> the gap is covered by the 3 company split ACs, whose extra'
          % bal['hall'])
    print('  electric load raises the turbine set-point and therefore the exhaust heat: the loop is self-balancing (06 §5-b)')
    print('\nv2: grid export (after the DG permit): turbine at 115k / 800 C, HVAC BALANCED')
    for lab, site in (('typical', SITE_KW['typical']), ('peak', SITE_KW['peak'])):
        exp = bal['net'] - CTRL_KW - site
        print('  site %-8s %4.1f kW -> export %5.1f kW (net after HVAC %.1f kW); MAX-POWER T1 12 C with the hall empty: export %5.1f kW'
              % (lab, site, exp, bal['net'], MODES['MAX-POWER T1=12C']['net'] - CTRL_KW - site if 'MAX-POWER T1=12C' in MODES else float('nan')))
    return rows


def main():
    print('EMS modes at the Borazjan summer design hour (DB %.0f C / WB %.0f C). HVAC side from sim/hvac/hvac_results.json.'
          % (H.DB_SUMMER, H.WB_TOWER))
    print('net = AC power left for the company after engine and HVAC auxiliaries; el-eq = net + (hall + elec-room cooling)/COP %.1f\n'
          % COP_SPLIT)
    print('%-34s %-10s %5s %6s %6s %6s %6s %6s %6s %7s' % ('mode', 'chillers', 'T1', 'P_eng', 'cool', 'coil', 'hall', 'unmet', 'aux', 'NET'))
    for k, m in MODES.items():
        print('%-34s %-10s %5s %6.1f %6.1f %6.1f %6.1f %6.1f %6.2f %7.2f' % (
            k, '+'.join(m['chillers']) or '-', '%.0f' % m['T1'] if m['T1'] else 'out', m['P_eng'], m['cool'], m['coil'], m['hall'],
            m['hall_unmet'], m['aux'], m['net']))
    print('\nengine-side levers in MAX-POWER (ECU): CH-1 only, hall gets the rest of CH-1')
    print('%-34s %5s %5s %6s %6s %6s %6s %7s %7s  %s' % ('mode', 'T1', 'TIT', 'P_eng', 'coil', 'hall', 'aux', 'NET', 'el-eq', 'note'))
    lev = engine_levers()
    for r in lev:
        print('%-34s %5.0f %5d %6.1f %6.1f %6.1f %6.2f %7.2f %7.1f  %s' % (r['mode'], r['T1'], r['TIT'], r['P_eng'], r['coil'], r['hall'],
                                                                     r['aux'], r['net'], r['el_eq'], r['note']))
    b = MODES['BALANCED']['net']
    print('\nnet gain vs BALANCED (%.2f kW): ' % b + ', '.join('%s %+.2f' % (k, m['net'] - b) for k, m in MODES.items() if k != 'BALANCED')
          + ', ' + ', '.join('%s %+.2f' % (r['mode'], r['net'] - b) for r in lev[1:]))

    hall_off, nocool = MODES['MAX-POWER-HALL-OFF'], MODES['NO-COOLING']
    d_aux = hall_off['aux'] - nocool['aux']
    print('\nbreak-even of the intake coil: CH-1 for the coil only (aux %.2f kW) vs NO-COOLING (aux %.2f kW), engine at 15 C vs outdoor:'
          % (hall_off['aux'], nocool['aux']))
    print('  %5s | %6s %6s | %6s | %s' % ('DB', 'P_15C', 'P_out', 'gain', 'verdict'))
    p15 = p_eng(15.0)[0]
    for DB in (46, 42, 38, 34, 30, 26, 22, 20, 18):
        pout = p_eng(float(DB))[0]
        gain = p15 - pout - d_aux
        print('  %5.0f | %6.1f %6.1f | %+6.1f | %s' % (DB, p15, pout, gain, 'run CH-1 for the coil' if gain > 0.3 else 'coil not worth it'))
    print('  (aux difference held at the design-hour value; HVAC season changeover 16/20 C with 48 h hold covers the low end)')

    print('\nAUTO example, summer noon, company demand 20.0 kW:')
    for k in ('BALANCED',):
        print('  BALANCED      net %.1f kW -> deficit %.1f kW from the battery' % (MODES[k]['net'], 20.0 - MODES[k]['net']))
    for r in lev:
        print('  %-30s net %.1f kW -> deficit %+.1f kW' % (r['mode'], r['net'], 20.0 - r['net']))
    pl = part_load()
    out = dict(design=dict(DB=H.DB_SUMMER, WB=H.WB_TOWER), part_load_v1=pl, hvac_modes={k: {kk: m[kk] for kk in ('chillers', 'T1', 'P_eng', 'cool', 'coil',
               'hall', 'hall_unmet', 'aux', 'net', 'el_equiv')} for k, m in MODES.items()}, engine_levers=lev)
    json.dump(out, open(os.path.join(os.path.dirname(__file__), 'ems_results.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
