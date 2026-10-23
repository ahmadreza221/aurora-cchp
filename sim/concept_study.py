# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 generator concept study: which architecture reaches >20 kW(e) 3-phase, ~20 % electrical, >55 % total (CHP)?

Design-point cycle (ISA 15 C), air flow of the GR180 compressor at ~117-120k rpm (calibrated on Rutten's test data:
186 N @ 119k, EGT 720 C; 178 N @ 117k). Hot-section areas are assumed re-matched for each concept.

Run:  uv run sim/concept_study.py
"""
import math
import gas_props as GP

CP_A, G_A, R_A = 1005.0, 1.40, 287.0
CP_G, G_G = 1148.0, 1.333
CP_G_LOW = 1080.0           # exhaust cp in the 90-600 C hot-water HX range
LHV, R_CH4 = 50.0e6, 518.3
T0, P0 = 288.15, 101325.0
EX_A, EX_G = (G_A - 1) / G_A, (G_G - 1) / G_G

def gas_booster_kW(mf, p_out_bar_abs, p_in_bar_abs=1.03, T=293.0, eta=0.50):
    """Fuel-gas compressor from the low-pressure network to the burner manifold (isothermal / eta)."""
    return mf * R_CH4 * T * math.log(p_out_bar_abs / p_in_bar_abs) / eta / 1e3

def cycle(c):
    """Optional as-built keys (defaults = original constant-cp model): fpt_k (FPT aero-work factor), fpt_loss (W, FPT
    bearing/seal loss instead of the 1.5 % mechanical loss), eta_gen (PMG, default 0.95), real_cp (recuperator duty and
    exhaust temperatures with real cp(T), sim/gas_props.py) - see life_study.ASBUILT."""
    ma, PR, T3 = c['ma'], c['PR'], c['TIT']
    eps = c.get('eps', 0.0)
    dp_rc, dp_rh = (0.025, 0.035) if eps > 0 else (0.0, 0.0)
    Ta, Pa = c.get('T_amb', T0), c.get('P_amb', P0)
    T1, P1 = Ta, Pa * (1 - 0.01)
    T2 = T1 * (1 + (PR ** EX_A - 1) / c['eta_c']); w_c = CP_A * (T2 - T1)
    P2 = P1 * PR; P2r = P2 * (1 - dp_rc); P3 = P2r * (1 - 0.045)
    P_exit = Pa * (1 + dp_rh + 0.015 + 0.005)               # recuperator hot side + CHP water HX + stack
    T_hot_in = 900.0
    for _ in range(60):
        T2r = T2 + eps * (T_hot_in - T2)
        f = CP_G * (T3 - T2r) / (0.97 * LHV) * 1.02          # gas burner eta_b 0.97, +2 % hot-section heat loss through casing
        mg = ma * (1 + f)
        if c['arch'] == 'single':
            dh = CP_G * T3 * (1 - (P_exit / P3) ** EX_G); w_t = c['eta_t'] * dh
            T_hot = T3 - w_t / CP_G
            P_shaft = mg * w_t * 0.985 - ma * w_c
            psi = None
        else:                                                 # gas generator + free power turbine
            w_t = w_c / (0.985 * (1 + f)); T4 = T3 - w_t / CP_G
            P4 = P3 * ((T3 - w_t / (CP_G * c['eta_t'])) / T3) ** (1 / EX_G) * (1 - 0.015)   # + interduct
            dh = CP_G * T4 * (1 - (P_exit / P4) ** EX_G); w_pt = c['eta_pt'] * dh * c.get('fpt_k', 1.0)
            T_hot = T4 - w_pt / CP_G
            P_shaft = mg * w_pt * 0.985 if c.get('fpt_loss') is None else mg * w_pt - c['fpt_loss']
        T_hot_in = T_hot
    T_after_rec = T_hot - ma * CP_A * (T2r - T2) / (mg * CP_G)
    Q_rec = ma * CP_A * (T2r - T2)
    mf = ma * f
    if c.get('real_cp'):                                      # same temperatures 165 -> 566 / 610 C, real duty (E4)
        exh = GP.exhaust(f)
        Q_rec = ma * (GP.AIR.h(T2r) - GP.AIR.h(T2))
        T_after_rec = exh.T_of_h(exh.h(T_hot) - Q_rec / mg)
    P_el_gross = P_shaft * c.get('eta_gen', 0.95) * 0.96                        # high-speed PMG 95 % x active rectifier + 3-ph inverter 96 %
    P_aux = (gas_booster_kW(mf, P3 / 1e5 + 1.0) * 1e3 if c.get('booster', True) else 0.0) + 450.0  # booster + oil pump, ECU, fans, water pump
    P_net = P_el_gross - P_aux
    Q_fuel = mf * LHV
    Q_chp = mg * CP_G_LOW * max(T_after_rec - 363.0, 0) * 0.90  # water HX to 90 C stack, 10 % HX/piping losses
    if c.get('real_cp'):
        Q_chp = mg * max(exh.h(T_after_rec) - exh.h(363.0), 0) * 0.90
    return dict(P3=P3, P_shaft=P_shaft, P_el=P_net, P_aux=P_aux, eta_el=P_net / Q_fuel, Q_chp=Q_chp,
                eta_tot=(P_net + Q_chp) / Q_fuel, mf=mf, T2r=T2r, T_hot=T_hot, T_stack_in=T_after_rec, Q_fuel=Q_fuel,
                Q_rec=Q_rec, T2=T2, far=f)

CORE = dict(ma=0.40, PR=3.2)
CONCEPTS = [
    ('S0  GR180 core as-is + FPT + PMG (simple cycle)',          dict(CORE, arch='fpt', TIT=1110, eta_c=0.70, eta_t=0.80, eta_pt=0.72)),
    ('S1  as-is core + FPT + recuperator eps 0.85',              dict(CORE, arch='fpt', TIT=1110, eta_c=0.70, eta_t=0.80, eta_pt=0.72, eps=0.85)),
    ('S2  as-is core + FPT + recuperator eps 0.90',              dict(CORE, arch='fpt', TIT=1110, eta_c=0.70, eta_t=0.80, eta_pt=0.75, eps=0.90)),
    ('S3  TARGET: tuned core + FPT 0.78 + recup 0.90, TIT 850 C', dict(CORE, arch='fpt', TIT=1123, eta_c=0.73, eta_t=0.82, eta_pt=0.78, eps=0.90)),
    ('S4  same, single-shaft (Capstone-type), TIT 850 C',         dict(CORE, arch='single', TIT=1123, eta_c=0.73, eta_t=0.82, eps=0.90)),
    ('S5  pessimistic: as-is core, FPT 0.68, recup 0.85, 800 C',  dict(CORE, arch='fpt', TIT=1073, eta_c=0.69, eta_t=0.78, eta_pt=0.68, eps=0.85)),
]

def main():
    print('%-56s %7s %7s %7s %7s %7s %8s %7s %7s' % ('concept', 'shaft', 'P_el', 'eta_el', 'CHP', 'eta_tot', 'CH4', 'T_comb', 'T_rec'))
    print('%-56s %7s %7s %7s %7s %7s %8s %7s %7s' % ('', 'kW', 'net kW', '%', 'kW th', '%', 'Nm3/h', 'in C', 'hot C'))
    for name, c in CONCEPTS:
        r = cycle(c)
        print('%-56s %7.1f %7.1f %7.1f %7.0f %7.1f %8.1f %7.0f %7.0f' % (
            name, r['P_shaft'] / 1e3, r['P_el'] / 1e3, r['eta_el'] * 100, r['Q_chp'] / 1e3, r['eta_tot'] * 100,
            r['mf'] * 3600 / 0.717, r['T2r'] - 273.15, r['T_hot'] - 273.15))
    print('\nRecuperator duty for S3: %.0f kW heat transfer -> UA ~ NTU*C_min = %.1f kW/K; at U~100 W/m2K: ~%.0f m2 surface'
          % (cycle(CONCEPTS[3][1])['Q_rec'] / 1e3, 9.0 * 0.40 * CP_A / 1e3, 9.0 * 0.40 * CP_A / 100))
    print('\nSensitivity S3 (TARGET): net electrical efficiency / net power vs recuperator effectiveness and TIT')
    for eps in (0.80, 0.85, 0.90, 0.93):
        row = []
        for TIT in (1073, 1123, 1173, 1223):
            row.append('%5.1f%%/%4.1fkW' % (cycle(dict(CONCEPTS[3][1], eps=eps, TIT=TIT))['eta_el'] * 100,
                                            cycle(dict(CONCEPTS[3][1], eps=eps, TIT=TIT))['P_el'] / 1e3))
        print('  eps %.2f  TIT 800/850/900/950 C: %s' % (eps, '  '.join(row)))
    print('\nAir flow needed for 20 kW net (S3 specific power):  %.2f kg/s' % (0.40 * 20e3 / cycle(CONCEPTS[3][1])['P_el']))

if __name__ == '__main__':
    main()
