# /// script
# requires-python = ">=3.9"
# dependencies = ["CoolProp"]
# ///
"""Variant B (GR180-STEAM): simple-cycle GR180 gas generator + E3 free power turbine/PMG + HRSG + extraction-condensing
steam turbine with its own high-speed PMG. The current recuperated design (variant A) stays the main line.

Gas side   concept_study.cycle(eps=0): same core, E1 and E3 as variant A (TIT 800 C, PR 3.1, 0.395 kg/s at 15 C);
           only E2 is re-sized for a 165 C combustor inlet and ~2.7x the fuel; E4 (recuperator) is replaced by the HRSG.
HRSG       drum type, 40 bar / 480 C superheat (capped 30 K below gas inlet), 15 K pinch, deaerated feed 105 C.
Turbine    multistage, eta_is 0.62 along one expansion line: 40 bar -> 1.3 bar (deaerator bleed) -> 0.8 bar (hot-water
           extraction, 93 C, drives the Yazaki 88/83 C absorption chillers) -> 0.08 bar condenser (cooling tower).
Modes      COND: all steam to the condenser (max electricity);  CHP: extraction to the hot-water heater, LP minimum flow
           15 % of inlet to keep the LP stages cool;  anything in between by the extraction valve.
Run:  uv run sim/variant_b/vb_cycle.py      (writes sim/variant_b/vb_results.json)
"""
import json, os, sys
from CoolProp.CoolProp import PropsSI as PS
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import concept_study as cs

LHV_VOL = 34.5e6                     # J/m3 city gas (same as the other studies)
CP_HR = 1110.0                       # exhaust cp, 600 -> 130 C
GT = dict(arch='fpt', PR=3.1, TIT=1073.15, eta_c=0.73, eta_t=0.82, eta_pt=0.78, eps=0.0, booster=False, P_amb=100725.0)
ETA_PMG, ETA_INV, ETA_MECH_ST = 0.975, 0.97, 0.98
P_HP, T_SH_MAX, P_DA, P_EX, P_C = 40e5, 480.0, 1.3e5, 0.8e5, 0.08e5
ETA_ST, PINCH, LP_MIN = 0.62, 15.0, 0.15
W = 'Water'

def h_line(h1, s1, p):
    """enthalpy on the turbine expansion line at pressure p (single eta_is from the inlet)."""
    return h1 - ETA_ST * (h1 - PS('H', 'P', p, 'S', s1, W))

def plant(T_amb_C, mode):
    T_amb = T_amb_C + 273.15
    g = cs.cycle(dict(GT, ma=0.395 * 288.15 / T_amb, T_amb=T_amb))
    ma = 0.395 * 288.15 / T_amb; mg = ma + g['mf']
    T_g = g['T_hot'] - 273.15                                    # FPT exit = HRSG inlet
    P_gt_el = g['P_shaft'] * ETA_PMG * ETA_INV
    # --- HRSG: superheater + evaporator above the pinch, economiser below
    T_sh = min(T_SH_MAX, T_g - 30.0)
    Ts = PS('T', 'P', P_HP, 'Q', 0, W) - 273.15
    h1 = PS('H', 'P', P_HP, 'T', T_sh + 273.15, W); s1 = PS('S', 'P', P_HP, 'T', T_sh + 273.15, W)
    h_sl = PS('H', 'P', P_HP, 'Q', 0, W)
    h_fw = PS('H', 'P', P_HP, 'T', 105.0 + 273.15, W)           # feed pump outlet ~ deaerator 105 C
    m_s = mg * CP_HR * (T_g - (Ts + PINCH)) / (h1 - h_sl)
    Q_eco = m_s * (h_sl - h_fw)
    T_stack = Ts + PINCH - Q_eco / (mg * CP_HR)
    Q_hrsg = m_s * (h1 - h_fw)
    # --- turbine expansion line
    h_da, h_ex, h_c = h_line(h1, s1, P_DA), h_line(h1, s1, P_EX), h_line(h1, s1, P_C)
    hf_da, hf_ex, hf_c = (PS('H', 'P', p, 'Q', 0, W) for p in (P_DA, P_EX, P_C))
    v_da = 1 / PS('D', 'P', P_DA, 'Q', 0, W)
    w_fp = v_da * (P_HP - P_DA) / 0.55                          # feed pump, J/kg
    # deaerator bleed m_b heats the returning condensate (condenser + hot-water heater drains) to saturation at 1.3 bar
    m_lp_frac = 1.0 if mode == 'COND' else LP_MIN
    for _ in range(30):
        m_b = getattr(plant, '_mb', 0.05 * m_s)
        m_after = m_s - m_b
        m_lp = min(m_after, m_lp_frac * m_s) if mode == 'CHP' else m_after
        m_x = m_after - m_lp
        h_ret = (m_lp * hf_c + m_x * hf_ex) / max(m_after, 1e-9)
        m_b_new = m_after * (hf_da - h_ret) / (h_da - hf_da)
        plant._mb = m_b_new
        if abs(m_b_new - m_b) < 1e-7: break
    del plant._mb
    W_st = m_s * (h1 - h_da) + (m_s - m_b) * (h_da - h_ex) + m_lp * (h_ex - h_c)
    P_st_el = W_st * ETA_MECH_ST * ETA_PMG * ETA_INV
    Q_cond = m_lp * (h_c - hf_c)
    Q_hw = m_x * (h_ex - hf_ex) * 0.97                          # to the 88/83 C hot-water loop
    Q_dhw = mg * CP_HR * max(T_stack - 95.0, 0) * 0.9           # stack economiser -> 60 C domestic hot water
    # --- auxiliaries (W)
    aux = dict(gt=450.0, feed_pump=m_s * w_fp, condensate=150.0, tower=0.017 * Q_cond + (300.0 if Q_cond > 0 else 0),
               hot_water_pump=300.0 if Q_hw > 0 else 0.0, water_treatment=300.0)
    P_aux = sum(aux.values())
    P_net = P_gt_el + P_st_el - P_aux
    Q_fuel = g['Q_fuel']
    cooling = 0.70 * Q_hw
    return dict(T_amb_C=T_amb_C, mode=mode, air_kg_s=round(ma, 3), fuel_kW=Q_fuel / 1e3, gas_m3h=Q_fuel / LHV_VOL * 3600,
                T_hrsg_in_C=T_g, T_sh_C=T_sh, T_sat_C=Ts, T_stack_C=T_stack, steam_kg_h=m_s * 3600, bleed_kg_h=m_b * 3600,
                extraction_kg_h=m_x * 3600, Q_hrsg_kW=Q_hrsg / 1e3, P_gt_el_kW=P_gt_el / 1e3, P_st_el_kW=P_st_el / 1e3,
                P_aux_kW=P_aux / 1e3, P_net_kW=P_net / 1e3, Q_cond_kW=Q_cond / 1e3, Q_hotwater_88C_kW=Q_hw / 1e3,
                cooling_kW=cooling / 1e3, Q_dhw_60C_kW=Q_dhw / 1e3, eta_el=P_net / Q_fuel,
                eta_total=(P_net + Q_hw + Q_dhw) / Q_fuel, aux_W={k: round(v) for k, v in aux.items()})

def main():
    rows = [plant(t, m) for t in (15.0, 30.0, 40.0) for m in ('COND', 'CHP')]
    hdr = ('amb', 'mode', 'gas', 'GT el', 'ST el', 'aux', 'NET', 'eta_el', 'hot w.', 'cool', 'DHW', 'eta_tot', 'steam', 'stack')
    print('%4s %5s %6s %6s %6s %5s %6s %6s %7s %6s %5s %7s %6s %5s' % hdr)
    print('%4s %5s %6s %6s %6s %5s %6s %6s %7s %6s %5s %7s %6s %5s' % ('C', '', 'm3/h', 'kW', 'kW', 'kW', 'kW', '%', 'kW', 'kW', 'kW', '%', 'kg/h', 'C'))
    for r in rows:
        print('%4.0f %5s %6.1f %6.1f %6.1f %5.1f %6.1f %6.1f %7.0f %6.0f %5.0f %7.1f %6.0f %5.0f' % (
            r['T_amb_C'], r['mode'], r['gas_m3h'], r['P_gt_el_kW'], r['P_st_el_kW'], r['P_aux_kW'], r['P_net_kW'],
            r['eta_el'] * 100, r['Q_hotwater_88C_kW'], r['cooling_kW'], r['Q_dhw_60C_kW'], r['eta_total'] * 100,
            r['steam_kg_h'], r['T_stack_C']))
    r = rows[0]
    print('\n15 C COND: HRSG in %.0f C, superheat %.0f C, sat %.0f C, HRSG duty %.0f kW, condenser %.0f kW, aux %s'
          % (r['T_hrsg_in_C'], r['T_sh_C'], r['T_sat_C'], r['Q_hrsg_kW'], r['Q_cond_kW'], r['aux_W']))
    json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vb_results.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
