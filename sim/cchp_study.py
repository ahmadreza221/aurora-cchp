# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP: electricity + absorption cooling (+ domestic hot water) at the customer site.

Exhaust after the recuperator -> exhaust/water HX -> hot-water loop 90/83 C -> single-effect LiBr chiller
(Yazaki WFC-SC10 class: 35 kW cooling from 50.2 kW heat at 88/83 C, COP 0.70) -> surplus heat to a DHW tank.
Site: intake 22 C after evaporative cooler (30 C room), 50 m, city gas >= 3.5 barg (no booster).
Engine = as-built E3/E4 model (life_study.ASBUILT): the exhaust leaves the recuperator at ~219 C, not 262 C, and the
water-HX heat uses real cp(T) (docs/08_design_point_update.md).  asbuilt=False reproduces the original issue.
Run:  python3 sim/cchp_study.py
"""
import gas_props as GP
import life_study as L

CP_LOW = 1080.0
CHILLER = dict(name='WFC-SC10 class', Q_heat_max=50.2e3, COP=0.70, Q_cool_max=35.2e3)
AUX_CCHP = 1.3e3        # hot-water, chilled-water and cooling-water pumps + cooling-tower fan
COP_SPLIT = 2.6         # gas-type (split/packaged) coolers at ~45 C outdoor

def cchp(N, TIT, eff='target', T_in=22.0, n_chillers=1, T_exh_out_C=100.0, asbuilt=True):
    r = L.point(N, TIT, eff, T_amb_C=T_in, alt_m=50.0, booster=False, asbuilt=asbuilt)
    mg = r['ma'] + r['mf']
    if asbuilt:
        Q_hw = mg * (GP.exhaust(r['far']).h(r['T_stack_in']) - GP.exhaust(r['far']).h(T_exh_out_C + 273.15)) * 0.95
    else:
        Q_hw = mg * CP_LOW * (r['T_stack_in'] - (T_exh_out_C + 273.15)) * 0.95
    Q_ch = min(Q_hw, n_chillers * CHILLER['Q_heat_max'])
    Q_cool = Q_ch * CHILLER['COP']
    Q_dhw = Q_hw - Q_ch
    P_net = r['P_el'] - AUX_CCHP
    saved = Q_cool / COP_SPLIT
    F = r['Q_fuel']
    return dict(r=r, Q_hw=Q_hw, Q_cool=Q_cool, Q_dhw=Q_dhw, P_net=P_net, saved=saved,
                eta_el=P_net / F, eta_useful=(P_net + Q_ch + Q_dhw) / F, eta_el_equiv=(P_net + saved) / F, F=F)

if __name__ == '__main__':
    print('%-34s %6s %6s %6s %6s %6s | %6s %6s %6s' % ('case', 'P_el', 'cool', 'DHW', 'saved', 'fuel', 'eta_el', 'useful', 'el-eq'))
    print('%-34s %6s %6s %6s %6s %6s | %6s %6s %6s' % ('', 'kW', 'kW', 'kW', 'kWe', 'kW', '%', '%', '%'))
    for lab, N, T, e in (('115k/800C target (continuous)', 115e3, 800, 'target'), ('115k/815C target (peak)', 115e3, 815, 'target'),
                         ('115k/800C as-is parts', 115e3, 800, 'as-is'), ('110k/800C target (economy)', 110e3, 800, 'target')):
        c = cchp(N, T, e)
        print('%-34s %6.1f %6.1f %6.1f %6.1f %6.0f | %6.1f %6.1f %6.1f' % (lab, c['P_net'] / 1e3, c['Q_cool'] / 1e3, c['Q_dhw'] / 1e3,
              c['saved'] / 1e3, c['F'] / 1e3, c['eta_el'] * 100, c['eta_useful'] * 100, c['eta_el_equiv'] * 100))
    c0 = cchp(115e3, 800, asbuilt=False)
    print('original constant-cp issue, 115k/800C: P_el %.1f kW, cooling %.1f kW, exhaust %.0f C' % (
        c0['P_net'] / 1e3, c0['Q_cool'] / 1e3, c0['r']['T_stack_in'] - 273.15))
    c = cchp(115e3, 800)
    print('\nexhaust into water HX %.0f C -> 100 C; hot-water heat %.1f kW; cooling-tower rejection ~%.0f kW'
          % (c['r']['T_stack_in'] - 273.15, c['Q_hw'] / 1e3, (c['Q_cool'] + min(c['Q_hw'], CHILLER['Q_heat_max'])) / 1e3))
    print('useful = (P_el + heat to chiller + DHW)/fuel ; el-eq = (P_el + electricity no longer used by split coolers)/fuel')
