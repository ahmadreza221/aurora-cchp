# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - high-speed PM generator (PMG, ~335 kW shaft continuous at 35,000 rpm) + power conversion.

2-pole surface-PM machine, 583 Hz: Sm2Co17 ring segments (parallel / diametral magnetisation) bonded on the d80 steel
rotor body, hoop-wound carbon sleeve (rotor OD 120 mm, 220 m/s), 2.5 mm mechanical gap, 24-slot stator of 0.20 mm
NO20 laminations in a water-glycol jacket, Litz winding.  Analytic magnetic circuit + loss estimates (no FEM yet) -
same method as sim/variant_d/d2r_pmg.py, scaled.

Power conversion (bought, industrial, no > 600 Hz frequency changer):
  PMG -> 6-pulse diode rectifier (blocks automatically below ~85 % speed) -> 750 V DC bus -> IGBT active front end
  'supply unit' + LCL filter -> 400 V 50 Hz grid;  start: a standard inverter module (<= 500 Hz) on the same DC bus
  motors the PMG to ~55 % speed (light-off ~22 %), then its contactor opens.
Rating: 335 kW shaft continuous = 315 kW grid-side gross (generator + converter peak/continuous limit, e_cycle).

Run:  python3 sim/variant_e/e_pmg.py  ->  sim/variant_e/e_pmg.json
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CY = json.load(open(os.path.join(HERE, 'e_cycle.json')))

N = 35000.0; w = N * math.pi / 30; f = N / 60
P_RATED = 335.0e3                                                   # shaft, continuous (= 315 kW grid-side gross)
P_DES = CY['design_point']['P_shaft_to_PMG_kW'] * 1e3
G = dict(rotor_OD=120.0, sleeve_t=6.0, magnet_ID=80.0, gap=2.5, stack=190.0, slots=24, stator_OD=240.0,
         endturn_axial=85.0, turns_per_phase=None, parallel_paths=2, fill=0.38, V_dc0_max=850.0)
SPEC = dict(Br20=1.10, alpha=-0.00035, T_mag=150.0, mu_r=1.05)    # Sm2Co17 (VAC VACOMAX 240 HR / Arnold Recoma 30 / Chinese 2:17 grade)


def size(g=G, P=P_RATED):
    r_s = g['rotor_OD'] / 2e3; t_sl = g['sleeve_t'] / 1e3
    r_m = r_s - t_sl; r_c = g['magnet_ID'] / 2e3
    t_m = r_m - r_c
    R_b = r_s + g['gap'] / 1e3
    R_o = g['stator_OD'] / 2e3
    L = g['stack'] / 1e3
    Q = g['slots']
    Br = SPEC['Br20'] * (1 + SPEC['alpha'] * (SPEC['T_mag'] - 20))
    kc = 1.05
    g_eff = (t_sl + g['gap'] / 1e3) * kc
    Bg = Br * t_m / (t_m + SPEC['mu_r'] * g_eff)
    r_g = 0.5 * (r_s + R_b)
    phi = 2 * Bg * r_g * L
    q = Q / 6
    kd = math.sin(math.pi / 6) / (q * math.sin(math.pi / (6 * q)))
    kp = math.sin(10 / 12 * math.pi / 2)                             # 10/12 short pitch
    kw = kd * kp
    e_turn = 4.44 * f * kw * phi                                     # V per series turn per phase
    Nph = g['turns_per_phase'] or int(g['V_dc0_max'] / (1.35 * math.sqrt(3) * e_turn))   # no-load DC <= 850 V (400 V-class AFE)
    E_ph = e_turn * Nph
    E_ll = math.sqrt(3) * E_ph
    # inductance: magnetising (surface PM, effective gap incl. magnet) + slot + end-winding leakage (est)
    mu0 = 4e-7 * math.pi
    g_m = t_m / SPEC['mu_r'] + g_eff
    L_m = 3 / math.pi * mu0 * (kw * Nph) ** 2 * 2 * r_g * L / g_m       # surface PM, p = 1
    L_sl = 2 * mu0 * Nph ** 2 * L * 1.6 / q                              # slot leakage, permeance 1.6 (semi-closed)
    L_ew = 2 * mu0 * Nph ** 2 * 0.35 * (2.2 * g['endturn_axial'] / 1e3) / q
    L_s = L_m + L_sl + L_ew
    X_s = w * L_s
    # current at the rating (diode rectifier: pf ~0.95 fundamental)
    I_ph = P / (3 * E_ph * 0.95)
    A_rms = 2 * 3 * Nph * I_ph / (2 * math.pi * R_b)
    sigma = Bg * A_rms * kw / math.sqrt(2)
    T = P / w
    # slots and copper
    tau_s = 2 * math.pi * R_b / Q
    w_t = Bg * tau_s / 1.50
    yoke = phi / 2 / (1.40 * L)
    d_slot = R_o - R_b - yoke
    A_slot = (math.pi * ((R_b + d_slot) ** 2 - R_b ** 2) - Q * w_t * d_slot) / Q
    turns_slot = 2 * Nph * 3 / Q * g['parallel_paths']                 # double layer, conductors per slot
    A_cu = A_slot * g['fill'] / (turns_slot)
    I_path = I_ph / g['parallel_paths']
    J = I_path / A_cu
    MLT = 2 * L + 2 * (g['endturn_axial'] / 1e3 * 2.2)
    rho_cu = 1.72e-8 * (1 + 0.0039 * (140 - 20))
    R_path = rho_cu * Nph * MLT / A_cu * 1.20                        # Litz AC factor 1.20 at 583 Hz + PWM ripple (est)
    R_ph = R_path / g['parallel_paths']
    P_cu = 3 * I_ph ** 2 * R_ph
    # iron: 0.20 mm NO20 (Surahammar / JFE 20JNEH / Baosteel 20BW): ~55 W/kg teeth (1.5 T), ~45 W/kg yoke (1.4 T) at 583 Hz incl. x1.5 build factor (est)
    rho_fe = 7650
    m_teeth = Q * w_t * d_slot * L * rho_fe
    m_yoke = math.pi * (R_o ** 2 - (R_o - yoke) ** 2) * L * rho_fe
    P_fe = 55.0 * m_teeth + 45.0 * m_yoke
    # rotor eddy (segmented SmCo, carbon sleeve, diode-rectifier 5th/7th harmonics) and windage (gap Couette + ends + cooling air)
    P_rotor = 1.1e3
    mu_air, rho_air = 2.2e-5, 1.12
    Re = rho_air * w * r_s * (g['gap'] / 1e3) / mu_air
    Cf = 0.065 * (g['gap'] / 1e3 / r_s) ** 0.3 * Re ** -0.2
    P_wind = Cf * math.pi * rho_air * w ** 3 * r_s ** 4 * L * 1.6     # +60 % end faces, seals, axial cooling-air flow
    P_brg = 2 * 0.85e3                                               # 2 x 7008 hybrid at 35k, oil jet (e_rotor.py)
    loss = dict(copper=P_cu, iron=P_fe, rotor_eddy=P_rotor, windage=P_wind, bearings=P_brg)
    eta = P / (P + sum(loss.values()))
    eta_em = P / (P + P_cu + P_fe + P_rotor)
    # cooling
    Q_jacket = P_cu + P_fe + 0.3 * (P_rotor + P_wind)
    gly_lpm = 30.0
    dT_g = Q_jacket / (gly_lpm / 60 * 1.05 * 3500)
    # rotor mechanics: magnet pressure on the sleeve, sleeve hoop stress at 100 % and 120 % (spin test)
    rho_m, rho_cf = 8400.0, 1600.0

    def sleeve(om):
        p = rho_m * om ** 2 * (r_m ** 3 - r_c ** 3) / (3 * r_m)
        r_sm = r_m + t_sl / 2
        return p, p * r_sm / t_sl + rho_cf * om ** 2 * r_sm ** 2
    p100, s100 = sleeve(w); p120, s120 = sleeve(1.2 * w)
    interf = s120 / 140e9 * r_s * 1e3
    # diode rectifier: Vdc = 1.35 E_ll - 3 X I / pi (commutation) - 2 x 1.2 V
    I_dc = I_ph * math.pi / math.sqrt(6) / 0.98
    V_dc = 1.35 * E_ll - 3 * X_s * I_dc / math.pi - 2.4
    V_dc_noload = 1.35 * E_ll
    speed_conduct = 650.0 / V_dc_noload                              # fraction of speed where the bridge starts to conduct at a 650 V idle bus
    m_rotor = (7850 * math.pi * r_c ** 2 * (L + 2 * g['endturn_axial'] / 1e3 + 0.12) + rho_m * math.pi * (r_m ** 2 - r_c ** 2) * L
               + rho_cf * math.pi * (r_s ** 2 - r_m ** 2) * L)
    out = dict(
        rating=dict(P_shaft_continuous_kW=P / 1e3, P_shaft_design_kW=round(P_DES / 1e3, 1), torque_Nm=round(T, 1), poles=2, f_Hz=round(f, 1), N_rpm=N),
        geometry=dict(rotor_OD_mm=g['rotor_OD'], magnet_mm=[g['magnet_ID'], 2 * r_m * 1e3], magnet_t_mm=round(t_m * 1e3, 1), sleeve_t_mm=g['sleeve_t'],
                      gap_mm=g['gap'], stator_ID_mm=round(2 * R_b * 1e3, 1), stator_OD_mm=g['stator_OD'], stack_mm=g['stack'], slots=Q,
                      tooth_mm=round(w_t * 1e3, 2), yoke_mm=round(yoke * 1e3, 1), slot_depth_mm=round(d_slot * 1e3, 1), slot_area_mm2=round(A_slot * 1e6, 1),
                      endturn_axial_mm=g['endturn_axial'], rotor_mass_kg=round(m_rotor, 1), U_tip_m_s=round(w * r_s, 1),
                      L_over_D=round(g['stack'] / g['rotor_OD'], 2)),
        magnetics=dict(Br_150C=round(Br, 3), B_gap_peak_T=round(Bg, 3), flux_Wb=phi, kw=round(kw, 3), turns_per_phase=Nph, parallel_paths=g['parallel_paths'],
                       E_ph_V=round(E_ph, 1), E_ll_V=round(E_ll, 1), I_ph_A=round(I_ph, 1), A_rms_kA_m=round(A_rms / 1e3, 1), shear_kPa=round(sigma / 1e3, 1),
                       J_A_mm2=round(J / 1e6, 2), R_ph_mOhm=round(R_ph * 1e3, 2), L_s_uH=round(L_s * 1e6, 1), X_s_Ohm=round(X_s, 3),
                       x_pu=round(X_s * I_ph / E_ph, 3), torque_check_Nm=round(2 * math.pi * r_g ** 2 * L * sigma, 1),
                       winding='3-ph double layer 24 slots, 10/12 pitch, 2 parallel paths, Litz (0.2 mm strands), class H, vacuum-pressure impregnated'),
        losses_W={k: round(v) for k, v in loss.items()}, efficiency=dict(electromagnetic=round(eta_em, 4), incl_windage_bearings=round(eta, 4)),
        cooling=dict(jacket_heat_W=round(Q_jacket), glycol_L_min=gly_lpm, dT_K=round(dT_g, 1), inlet_C='<= 45',
                     rotor='filtered intake air drawn through the gap by the compressor-eye suction (~0.5 % of the air, ~3 kPa), magnets ~130-150 C (est); Sm2Co17 good to 300 C'),
        rotor_mech=dict(magnet_pressure_MPa_100=round(p100 / 1e6, 1), sleeve_hoop_MPa_100=round(s100 / 1e6), sleeve_hoop_MPa_120=round(s120 / 1e6),
                        allowable_MPa=1400, SF_120=round(1400e6 / s120, 2), sleeve_interference_mm=round(interf, 3),
                        build='Sm2Co17 segments (2 halves x 8 axial pieces), bonded on the d80 rotor body; T700/T800 carbon sleeve wound with pre-tension '
                              '(or pressed on a 1:200 taper); 1.4404 end rings = balance planes; balance G1 as an assembly'),
        conversion=dict(rectifier=dict(type='6-pulse diode bridge (or 12-pulse with a 2 x 3-ph winding)', V_dc_full_load=round(V_dc), V_dc_no_load=round(V_dc_noload),
                                       regulation_pct=round(100 * (1 - V_dc / V_dc_noload), 1),
                                       window='400 V-class AFE: DC >= ~620 V at full load, no-load <= 850 V (braking chopper clamps load rejection)',
                                       I_dc_A=round(I_dc), bridge_conducts_above_speed_pct=round(100 * speed_conduct, 1)),
                        dc_bus_V='620-850 (load dependent; AFE holds it, braking chopper at 860 V)', grid=dict(type='IGBT active front end supply unit + LCL filter, 400 V 50 Hz, ~350 kVA',
                                                candidates='ABB ACS880-207 IGBT supply unit (FI/CH), Danfoss VACON NXA AFE (FI/DK), Siemens SINAMICS S120 Active Line Module (DE), Ingeteam (ES), Inovance / INVT (CN)'),
                        start=dict(type='standard inverter module on the DC bus (<= 500 Hz output), 45 kW class, contactor to the PMG',
                                   to_speed_pct=55, f_max_Hz=round(0.55 * f), light_off_pct=22, energy='from the grid through the AFE (black start: 50 kWh battery on the DC bus, optional)'),
                        why='no frequency changer >= 600 Hz (dual-use 3A225); every block is a standard industrial product; the diode bridge blocks by itself while motoring',
                        efficiency=dict(rectifier=0.990, afe_lcl=0.980, total=0.970)),
        buy_options=['active parts (stator with winding + magnet rotor sleeve) made to this spec by a high-speed machine shop: e+a Elektromaschinen und Antriebe (CH)',
                     'complete HS machine: Safran GENeUS 300 (FR; 300 kW, 550-800 VDC with integrated active rectifier, ~40k rpm) - inquire 24/7 industrial rating, export',
                     'turbo-blower HS motor makers as a cross-check / supplier of the stator stack (KEBA LeviTurb 300 AT; Chinese maglev-blower motor makers - inquiry)'])
    return out


def main():
    o = size()
    print(json.dumps({k: o[k] for k in ('geometry', 'magnetics', 'losses_W', 'efficiency', 'cooling', 'rotor_mech')}, indent=1))
    print('conversion:', json.dumps(o['conversion']['rectifier']))
    o['design_point_losses_W'] = {k: v for k, v in o['losses_W'].items()}
    d = size(P=P_DES)
    o['at_design_shaft_power'] = dict(P_shaft_kW=round(P_DES / 1e3, 1), losses_W=d['losses_W'], efficiency=d['efficiency'], V_dc=d['conversion']['rectifier']['V_dc_full_load'])
    o['title'] = 'GR180 version E high-speed PMG + power conversion'; o['date'] = '2026-10-23'; o['script'] = 'sim/variant_e/e_pmg.py'; o['inputs'] = dict(G=G, SPEC=SPEC)
    json.dump(o, open(os.path.join(HERE, 'e_pmg.json'), 'w'), indent=1)
    print('at design %.1f kW: losses %s eta %.4f Vdc %d' % (P_DES / 1e3, d['losses_W'], d['efficiency']['incl_windage_bearings'], d['conversion']['rectifier']['V_dc_full_load']))
    print('-> sim/variant_e/e_pmg.json')


if __name__ == '__main__':
    main()
