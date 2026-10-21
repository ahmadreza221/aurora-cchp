# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Scale-up study: what a ~210 kW(e) machine looks like, with/without a bottoming ORC and with heat to households.

Uses concept_study.cycle (same thermodynamics as the GR180-CCHP studies). Site: Borazjan, intake chilled to 15 C, 50 m.
Cases
  A  GR180 technology scaled up 1:1 (eta_c .73, eta_t .82, FPT .78, TIT 800 C, PR 3.1, recuperator 0.90)
  B  200-kW-class technology (Capstone C200-like): single shaft, eta_c .80, eta_t .86, TIT 950 C, PR 4.3, eps 0.90
  C  B + ORC on the recuperator exhaust, max power (condensing ~35 C, eta_ORC 12 %)
  D  B + ORC in CHP mode (condensing ~70 C, eta_ORC 8 %, condenser heat 60-65 C to households)
  E  B, all exhaust heat to households (hot water 80/60 C), no ORC
  F  B without recuperator (simple cycle, exhaust ~560 C) + ORC (eta_ORC 18 %)
  M  10-11 GR180-CCHP units in parallel (modular, what we are building now)
Run:  python3 sim/scaleup_210kw_study.py
"""
import math
import concept_study as cs

LHV_NG = 34.5e6          # J/m3 city gas
TARGET = 210e3           # W net electric
CP_LOW = 1080.0
HH = dict(dhw_kwh_day=6.5, heat_kwh_day_winter=20.0, cool_kw_peak=8.0)   # per household (4 persons, ~100 m2, Borazjan)

def run(c, eta_gen=0.96, eta_pe=0.975, aux_frac=0.03):
    """per kg/s of air: gross shaft -> electric, exhaust state; scaled later to TARGET net."""
    r = cs.cycle(dict(c, ma=1.0, T_amb=288.15, P_amb=100725.0, booster=False))
    P_el = r['P_shaft'] * eta_gen * eta_pe
    booster = cs.gas_booster_kW(r['mf'], r['P3'] / 1e5 + 1.0, p_in_bar_abs=4.5) * 1e3 if c.get('need_booster') else 0.0
    P_net = P_el * (1 - aux_frac) - max(booster, 0.0)
    mg = 1.0 + r['mf']
    return dict(P_net=P_net, mf=r['mf'], T_exh=r['T_stack_in'], mg=mg, Q_fuel=r['Q_fuel'], P3=r['P3'], booster=booster)

def size(c, orc=None, chp_to=None, label=''):
    s = run(c)
    # ORC on the exhaust (cooled to 100 C), optional
    q_orc_in = s['mg'] * CP_LOW * max(s['T_exh'] - 373.15, 0) if orc else 0.0
    p_orc = q_orc_in * (orc['eta'] if orc else 0.0) * 0.97
    ma = TARGET / (s['P_net'] + p_orc)                       # air flow that gives 210 kW net in total
    fuel = s['Q_fuel'] * ma
    P_gt, P_orc = s['P_net'] * ma, p_orc * ma
    if orc and orc.get('chp'):
        heat = q_orc_in * (1 - orc['eta']) * 0.92 * ma           # ORC condenser heat at 60-65 C
    elif chp_to:
        heat = s['mg'] * CP_LOW * max(s['T_exh'] - chp_to, 0) * 0.92 * ma
    else:
        heat = 0.0
    D2 = math.sqrt(ma / 91.8 * 4 / math.pi)                   # compressor tip Ø at the GR180 specific flow (kg/s per m2 of D2)
    PR = c['PR']; eta_c = c['eta_c']
    U2 = math.sqrt(1005 * 288.15 * (PR ** 0.2857 - 1) / eta_c / 0.75)
    rpm = U2 / (math.pi * D2) * 60
    return dict(label=label, ma=ma, P_gt=P_gt, P_orc=P_orc, P_net=P_gt + P_orc, fuel=fuel, gas=fuel / LHV_NG * 3600,
                eta_el=(P_gt + P_orc) / fuel, heat=heat, eta_tot=(P_gt + P_orc + heat) / fuel, T_exh=s['T_exh'] - 273.15,
                D2=D2 * 1e3, rpm=rpm, U2=U2, P3=s['P3'] / 1e5, Q_rec=None, booster=s['booster'] * ma)

A = dict(arch='fpt', PR=3.1, TIT=1073.15, eta_c=0.73, eta_t=0.82, eta_pt=0.78, eps=0.90)
B = dict(arch='single', PR=4.3, TIT=1223.15, eta_c=0.80, eta_t=0.86, eps=0.90, need_booster=True)
Bsc = dict(arch='single', PR=4.3, TIT=1223.15, eta_c=0.80, eta_t=0.86, eps=0.0, need_booster=True)

def main():
    rows = [size(A, label='A  GR180 tech scaled (FPT, 800 C, PR 3.1)'),
            size(B, label='B  200-kW class (single shaft, 950 C, PR 4.3)'),
            size(B, orc=dict(eta=0.12), label='C  B + ORC (max power)'),
            size(B, orc=dict(eta=0.08, chp=True), label='D  B + ORC in CHP mode (60-65 C heat)'),
            size(B, chp_to=353.15, label='E  B + heat to households (80/60 C)'),
            size(Bsc, orc=dict(eta=0.18), label='F  B no recuperator + ORC')]
    print('%-44s %6s %6s %6s %6s %7s %6s %6s %6s %6s %6s %6s' % ('case', 'air', 'P_GT', 'P_ORC', 'fuel', 'gas', 'eta_el', 'heat', 'eta_t', 'T_exh', 'D2', 'rpm'))
    print('%-44s %6s %6s %6s %6s %7s %6s %6s %6s %6s %6s %6s' % ('', 'kg/s', 'kW', 'kW', 'kW', 'm3/h', '%', 'kW', '%', 'C', 'mm', 'k'))
    for r in rows:
        print('%-44s %6.2f %6.0f %6.0f %6.0f %7.1f %6.1f %6.0f %6.0f %6.0f %6.0f %6.1f' % (
            r['label'], r['ma'], r['P_gt'] / 1e3, r['P_orc'] / 1e3, r['fuel'] / 1e3, r['gas'], r['eta_el'] * 100, r['heat'] / 1e3,
            r['eta_tot'] * 100, r['T_exh'], r['D2'], r['rpm'] / 1e3))
    # modular: 11 x GR180-CCHP (net 19.4 kW each with HVAC aux 1.3 kW per sim/cchp_study.py)
    n = math.ceil(210 / 19.4)
    print('%-44s %6.2f %6.0f %6s %6.0f %7.1f %6.1f %6.0f %6.0f %6s %6s %6s' % (
        'M  %d x GR180-CCHP units (modular)' % n, 0.395 * n, 19.4 * n, '-', 107 * n, 11.7 * n, 19.4 / 107 * 100, 66.6 * n,
        (19.4 + 66.6) / 107 * 100, '262', '74', '115'))
    print('\nHouseholds served by the useful heat (per household: DHW %.1f kWh/day, winter heating %.0f kWh/day, summer cooling %.0f kW peak, absorption COP 0.70):'
          % (HH['dhw_kwh_day'], HH['heat_kwh_day_winter'], HH['cool_kw_peak']))
    for r in rows:
        if r['heat'] <= 0: continue
        q = r['heat'] / 1e3
        print('  %-44s heat %4.0f kW -> DHW %5.0f households | winter heating %4.0f | summer cooling (absorption, %3.0f kW cold) %3.0f'
              % (r['label'], q, q * 24 / HH['dhw_kwh_day'], q * 24 / HH['heat_kwh_day_winter'], q * 0.7 if r['label'][0] == 'E' else q * 0.0,
                 (q * 0.7 / HH['cool_kw_peak']) if r['label'][0] == 'E' else 0))
    q = 66.6
    print('  %-44s heat %4.0f kW -> DHW %5.0f households | winter heating %4.0f | summer cooling (absorption, %3.0f kW cold) %3.0f'
          % ('GR180-CCHP single unit (today)', q, q * 24 / HH['dhw_kwh_day'], q * 24 / HH['heat_kwh_day_winter'], q * 0.7, q * 0.7 / HH['cool_kw_peak']))
    return rows

if __name__ == '__main__':
    main()
