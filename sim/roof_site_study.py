# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Rooftop installation in Borazjan: engine breathes OUTDOOR air (summer design ~46 C), intake chilled with our own
absorption-chiller water; chilled-water budget split between engine intake, the 10x10x2.5 m hall and the electrical room.
Run:  python3 sim/roof_site_study.py
"""
import math
import cchp_study as C

def w_sat(T):                      # kg/kg at 101.3 kPa
    p = 0.61094 * math.exp(17.625 * T / (T + 243.04)); return 0.622 * p / (101.325 - p)
def h(T, w): return 1.006 * T + w * (2501 + 1.86 * T)          # kJ/kg dry air

OUT = dict(T=46.0, w=0.0150)        # Borazjan summer design (assumed): 46 C DB, ~27 C WB
IN_HALL = dict(T=24.0, w=0.0093)    # 24 C / 50 % RH

def inlet_coil_kW(ma, T_out, w_out, T_coil):
    w2 = min(w_out, w_sat(T_coil)); return ma * (h(T_out, w_out) - h(T_coil, w2))

def hall_load(insulated_roof=True, people=10, equip_kW=3.0, win_m2=8.0):
    A_roof, walls = 100.0, 4 * 10 * 2.5 - win_m2
    q = {}
    q['roof'] = (0.45 if insulated_roof else 2.0) * A_roof * 35.0 / 1e3          # CLTD ~35 K (sun + rooftop plant)
    q['walls'] = 1.2 * walls * 15.0 / 1e3
    q['windows'] = (win_m2 * 300 * 0.6 + win_m2 * 5.7 * (OUT['T'] - IN_HALL['T'])) / 1e3
    q['people'] = people * 130 / 1e3
    q['lighting'] = 100 * 10 / 1e3
    q['equipment'] = equip_kW
    m_fa = people * 0.010 * 1.15                                                   # 10 L/s per person fresh air
    q['fresh air'] = m_fa * (h(OUT['T'], OUT['w']) - h(IN_HALL['T'], IN_HALL['w']))
    q['infiltration'] = 0.3 * 250 / 3600 * 1.15 * (h(OUT['T'], OUT['w']) - h(IN_HALL['T'], IN_HALL['w']))
    tot = sum(q.values()) * 1.10
    return q, tot

if __name__ == '__main__':
    C.CHILLER['Q_heat_max'] = 75.3e3; DER = 0.92
    print('ROOF: outdoor %.0f C / w %.1f g/kg; chiller pair SC10+SC5 class, cooling water 32 C' % (OUT['T'], OUT['w'] * 1e3))
    for Tc in (15.0, 20.0, 25.0, 46.0):
        c = C.cchp(115e3, 800, 'target', T_in=Tc)
        ma = c['r']['ma']; coil = inlet_coil_kW(ma, OUT['T'], OUT['w'], Tc) if Tc < OUT['T'] else 0.0
        cool = c['Q_cool'] * DER; P = c['P_net'] - (0.35e3 if Tc < OUT['T'] else 0)
        print('  intake %4.0f C: P_el net %5.1f kW, eta_el %4.1f %% | chiller %4.1f kW -> intake coil %4.1f kW, left for building %4.1f kW'
              % (Tc, P / 1e3, P / c['F'] * 100, cool / 1e3, coil, cool / 1e3 - coil))
    for ins in (True, False):
        q, tot = hall_load(insulated_roof=ins)
        print('\nHALL 10x10x2.5 m (%s roof): ' % ('insulated' if ins else 'UNinsulated') + ', '.join('%s %.1f' % (k, v) for k, v in q.items())
              + ' kW -> design %.1f kW (%.1f TR), chilled water %.1f m3/h at dT 5 K' % (tot, tot / 3.517, tot / (4.19 * 5) * 3.6))
