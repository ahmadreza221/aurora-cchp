# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP continuous design point (docs/06_master_design.md sec. 2): original constant-cp cycle vs as-built engine.

As-built = life_study.ASBUILT: E3 FPT/PMG (shaft 24.86 kW, terminals 24.11 kW) and E4 recuperator (eps 0.905, real cp).
Site-level numbers (cooling, HVAC aux, net to the company) come from sim/hvac/hvac_results.json (run hvac_design.py first).
Change log of every number: docs/08_design_point_update.md.
Run:  python3 sim/design_point.py
"""
import json
import os

import gas_props as GP
import life_study as L

HERE = os.path.dirname(os.path.abspath(__file__))
LHV_CITY = 34.5e6            # J/m3, city gas (docs/07_scaleup_210kW.md); the cycle itself burns CH4 at 50 MJ/kg
ETA_REC, ETA_INV = 0.985, 0.96 / 0.985   # B3 active rectifier; inverter (the cycle's 0.96 covers both)


def engine(asbuilt):
    r = L.point(115e3, 800, 'target', T_amb_C=15.0, alt_m=50.0, booster=False, asbuilt=asbuilt)
    mg = r['ma'] + r['mf']
    if asbuilt:
        exh = GP.exhaust(r['far'])
        q_hx1 = mg * (exh.h(r['T_stack_in']) - exh.h(373.15))
    else:
        q_hx1 = mg * 1080.0 * (r['T_stack_in'] - 373.15)
    eta_gen = L.ASBUILT['eta_gen'] if asbuilt else 0.95
    p_term = r['P_shaft'] * eta_gen
    return dict(ma=r['ma'], mg=mg, T2=r['T2'] - 273.15, P2=101325 * (1 - 2.25577e-5 * 50) ** 5.25588 * 0.99 * r['PR'] / 1e5,
                T2r=r['T2r'] - 273.15, P3=r['P3'] / 1e5, eps=r['eps'], T_hot=r['T_hot'] - 273.15, T_ex=r['T_stack_in'] - 273.15,
                Q_rec=r['Q_rec'] / 1e3, P_shaft=r['P_shaft'] / 1e3, P_term=p_term / 1e3, P_dc=p_term * ETA_REC / 1e3,
                P_ac=p_term * 0.96 / 1e3, P_aux=r['P_aux'] / 1e3, P_net=r['P_el'] / 1e3, eta_el=r['eta_el'] * 100,
                mf=r['mf'] * 1e3, Q_fuel=r['Q_fuel'] / 1e3, Nm3h=r['mf'] * 3600 / 0.717, city_m3h=r['Q_fuel'] * 3600 / LHV_CITY,
                Q_hx1=q_hx1 / 1e3, Q_hw=q_hx1 * 0.95 / 1e3, Q_chp=r['Q_chp'] / 1e3, eta_tot=r['eta_tot'] * 100)


ROWS = [('air flow', 'ma', 'kg/s', '%.4f'), ('exhaust gas flow', 'mg', 'kg/s', '%.4f'),
        ('compressor exit T2', 'T2', 'C', '%.1f'), ('compressor exit P2', 'P2', 'bar abs', '%.3f'),
        ('recuperator effectiveness (net)', 'eps', '-', '%.3f'), ('recuperator cold exit T2r (combustor inlet)', 'T2r', 'C', '%.1f'),
        ('combustor exit P3 (TIT 800 C)', 'P3', 'bar abs', '%.3f'), ('FPT exit = recuperator hot inlet', 'T_hot', 'C', '%.1f'),
        ('recuperator hot exit -> D-101 -> HX-1', 'T_ex', 'C', '%.1f'), ('recuperator duty', 'Q_rec', 'kW', '%.1f'),
        ('FPT shaft power', 'P_shaft', 'kW', '%.2f'), ('PMG terminal power', 'P_term', 'kW', '%.2f'),
        ('DC into the inverter (rectifier 0.985)', 'P_dc', 'kW', '%.2f'), ('AC out of the inverter', 'P_ac', 'kW', '%.2f'),
        ('engine auxiliaries (oil pump, ECU, fans)', 'P_aux', 'kW', '%.2f'), ('NET electric at the engine (before HVAC)', 'P_net', 'kW', '%.2f'),
        ('electrical efficiency (LHV)', 'eta_el', '%', '%.1f'), ('fuel CH4', 'mf', 'g/s', '%.3f'), ('fuel power (LHV)', 'Q_fuel', 'kW', '%.1f'),
        ('gas, CH4 basis (0.717 kg/Nm3)', 'Nm3h', 'Nm3/h', '%.2f'), ('gas, city gas LHV 34.5 MJ/m3', 'city_m3h', 'm3/h', '%.2f'),
        ('exhaust heat to HX-1, gas side to 100 C', 'Q_hx1', 'kW', '%.1f'), ('hot water from HX-1 (x 0.95)', 'Q_hw', 'kW', '%.1f'),
        ('CHP heat to 90 C (x 0.90, cycle def.)', 'Q_chp', 'kW', '%.1f'), ('total efficiency (P_net + CHP heat)/fuel', 'eta_tot', '%', '%.1f')]


def main():
    old, new = engine(False), engine(True)
    print('Design point 115k rpm / TIT 800 C / intake 15 C (chilled) / 50 m / no booster, target component efficiencies')
    print('%-46s %8s %10s %10s %9s' % ('', 'unit', 'original', 'as-built', 'change'))
    for lab, k, u, f in ROWS:
        d = new[k] - old[k]
        print('%-46s %8s %10s %10s %9s' % (lab, u, f % old[k], f % new[k], ('%+.2f' % d) if abs(d) > 5e-4 else '0'))
    path = os.path.join(HERE, 'hvac', 'hvac_results.json')
    if os.path.exists(path):
        res = json.load(open(path))
        print('\nSite, Borazjan design hour 46 C DB / 28 C WB (sim/hvac/hvac_results.json, as-built engine):')
        for m in ('MAX-COOLING', 'BALANCED', 'MAX-POWER', 'MAX-POWER T1=12C', 'MAX-POWER-HALL-OFF', 'NO-COOLING'):
            x = res['modes'][m]
            print('  %-20s T1 %4.1f C | cooling %4.1f (coil %4.1f, hall %4.1f, unmet %4.1f) | HVAC aux %.2f | NET %5.2f kW' % (
                m, x['T1'], x['cool'], x['coil'], x['hall'], x['hall_unmet'], x['aux'], x['net']))


if __name__ == '__main__':
    main()
