# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version D2 - radial-inflow turbine redone for a BOUGHT turbocharger turbine wheel (D4 ~78 mm, IN713C).

1. Design-point meanline (loss summation, Baines / Moustapha et al. 'Axial and Radial Turbines' 2003 correlations):
   plenum -> 17-vane radial nozzle ring -> vaneless gap -> 11-blade wheel (turbo-wheel class, no splitters) -> exducer
   -> exhaust diffuser. Work target 85 kW (compressor 59.5 + generator 25.5 kW shaft) at 115k rpm, TIT 800 C, 0.40 kg/s.
2. Electric output vs ambient (0/15/30/40/45 C) with sim/concept_study.cycle (arch 'single', eps 0), generator eta 0.95,
   converter 0.96, minus 0.6 kW auxiliaries, compressor scaled at constant physical speed (corrected-speed similarity).

Run:  uv run sim/variant_d/d2r_turbine.py   ->  sim/variant_d/d2r_turbine.json
All loss coefficients are textbook values for turbocharger-class wheels; the bought wheel's real geometry (supplier
drawing) replaces the assumed blade numbers before the nozzle ring is cut.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import concept_study as cs                                   # noqa: E402

CP, G, R = 1148.0, 1.333, 287.0
EXG = (G - 1) / G
MU = 4.3e-5                                                   # gas viscosity ~850 K

# ------------------------------------------------------------------ inputs
N = 115000.0; OM = N * 2 * math.pi / 60
M_GAS = 0.40                                                  # kg/s (air 0.395 + fuel)
T01 = 1073.15                                                 # TIT 800 C
P0_CORE = 2.87e5                                              # combustor exit total (docs/06 section 2)
DP_PLENUM = 0.015                                             # strut ring + turning plenum total-pressure loss
W_TARGET = 85.0e3                                             # turbine shaft work (compressor 59.5 + generator 25.5)
GEO = dict(D4=78.0, Z_R=11, D6t=70.0, D6h=21.0, Lz=34.0,      # wheel: HX40 / TD08-class high-flow trim (80 trim), no splitters
           b4=14.0,                                           # tip width at the inlet, b4/D4 0.18 (turbo-wheel typical 0.15-0.19)
           t_LE=1.2, t_TE=0.8, eps_a=0.35, eps_r=0.35, s_back=1.5,
           Z_N=17, r3_over_r4=1.10, r2_over_r3=1.32, t_vane_TE=0.6)
ZETA_N = 0.065                                                # nozzle + vaneless kinetic-energy loss coefficient
K_P, K_A, K_R, K_AR = 0.11, 0.4, 0.75, -0.3                   # Baines passage / clearance coefficients
CP_DIFF = 0.50                                                # exhaust diffuser static-pressure recovery (conical, 2x area)


def state(h0, c, P0, s_loss_h=0.0, T0ref=T01, P0ref=None):
    """static T, P from total enthalpy drop + loss: T = T0 - c^2/2cp; P from the isentropic temperature T - loss/cp."""
    T = h0 / CP - c * c / (2 * CP)
    Ts = T - s_loss_h / CP
    P = (P0ref or P0) * (Ts / T0ref) ** (1 / EXG)
    return T, P


def meanline(geo=GEO, W=W_TARGET, m=M_GAS, cp_diff=None):
    g = dict(geo)
    cp_diff = g.pop('cp_diff', CP_DIFF) if cp_diff is None else cp_diff
    r4, r6t, r6h = g['D4'] / 2e3, g['D6t'] / 2e3, g['D6h'] / 2e3
    r6 = math.sqrt((r6t ** 2 + r6h ** 2) / 2)
    b6 = r6t - r6h
    U4, U6, U6t = OM * r4, OM * r6, OM * r6t
    P01 = P0_CORE * (1 - DP_PLENUM)
    h01 = CP * T01
    # first guesses
    dh_df = 2e3; b4 = 0.012; rho6 = 0.40
    for _ in range(80):
        dh_shaft = W / m
        dh_eu = dh_shaft + dh_df                                  # Euler work = shaft work + disc friction
        ct4 = dh_eu / U4                                          # zero exit swirl
        # rotor inlet: pick b4 for the target absolute flow angle
        b4 = g['b4'] / 1e3
        block4 = 1 - g['Z_R'] * g['t_LE'] / 1e3 / (2 * math.pi * r4)
        rho4 = 0.7
        for _ in range(30):
            cm4 = m / (rho4 * 2 * math.pi * r4 * b4 * block4)
            c4 = math.hypot(ct4, cm4)
            r3 = r4 * g['r3_over_r4']
            ct3 = ct4 * r4 / r3 * 1.02                            # vaneless friction: 2 % angular-momentum loss
            # nozzle exit
            cm3 = cm4 * r4 / r3
            c3 = math.hypot(ct3, cm3)
            dh_N = ZETA_N * c3 ** 2 / 2
            T3, P3 = state(h01, c3, P01, dh_N)
            T4, P4 = state(h01, c4, P01, dh_N)
            rho4 = P4 / (R * T4)
        wt4 = ct4 - U4
        W4 = math.hypot(cm4, wt4)
        beta4 = math.degrees(math.atan2(wt4, cm4))
        ct4_opt = U4 * (1 - 0.63 * math.pi / g['Z_R'] / (1 + 0.0))  # Stanitz slip -> optimum incidence
        beta4_opt = math.degrees(math.atan2(ct4_opt - U4, cm4))
        dh_inc = 0.5 * (W4 * math.sin(math.radians(beta4 - beta4_opt))) ** 2
        # rotor exit
        A6 = math.pi * (r6t ** 2 - r6h ** 2) * (1 - g['Z_R'] * g['t_TE'] / 1e3 / (math.pi * (r6t + r6h)))
        c6 = m / (rho6 * A6)
        W6 = math.hypot(c6, U6); W6t = math.hypot(c6, U6t)
        beta6 = math.degrees(math.atan2(U6, c6))
        # passage loss (Baines)
        Lh = math.pi / 4 * ((g['Lz'] / 1e3 - b4 / 2) + (r4 - r6t - b6 / 2))
        Dh = 0.5 * (4 * math.pi * r4 * b4 / (2 * math.pi * r4 + g['Z_R'] * b4)
                    + 2 * math.pi * (r6t ** 2 - r6h ** 2) / (math.pi * (r6t - r6h) + g['Z_R'] * b6))
        chord = math.hypot(g['Lz'] / 1e3, r4 - r6)
        dh_p = K_P * (Lh / Dh + 0.68 * (1 - (r6 / r4) ** 2) * math.cos(math.radians(beta6)) / (b6 / chord)) \
            * 0.5 * (W4 ** 2 + W6 ** 2)
        # tip clearance (Baines)
        Ca = (1 - r6t / r4) / (cm4 * b4)
        Cr = (r6t / r4) * (g['Lz'] / 1e3 - b4) / (c6 * r6 * b6)
        ea, er = g['eps_a'] / 1e3, g['eps_r'] / 1e3
        dh_cl = U4 ** 3 * g['Z_R'] / (8 * math.pi) * (K_A * ea * Ca + K_R * er * Cr + K_AR * math.sqrt(ea * er * Ca * Cr))
        # trailing edge
        dh_te = 0.5 * W6 ** 2 * (g['Z_R'] * g['t_TE'] / 1e3 / (math.pi * (r6t + r6h) * math.cos(math.radians(beta6)))) ** 2
        # exit state
        h06 = h01 - dh_eu
        dh_int = dh_N + dh_inc + dh_p + dh_cl + dh_te
        dh_is_ts = dh_eu + dh_int + c6 ** 2 / 2
        T6 = h06 / CP - c6 ** 2 / (2 * CP)
        if dh_is_ts >= 0.75 * h01:
            raise ValueError('exducer choked / no solution')
        P6 = P01 * (1 - dh_is_ts / h01) ** (1 / EXG)
        rho6_new = P6 / (R * T6)
        # disc friction on the plain back face (Daily & Nece regime IV: Cm = 0.051 (s/r)^0.1 Re^-0.2, P = Cm rho/2 U^3 r^2)
        rho_m = rho4
        Re = rho_m * U4 * r4 / MU
        Cm = 0.051 * (g['s_back'] / 1e3 / r4) ** 0.1 / Re ** 0.2
        dh_df_new = Cm * 0.5 * rho_m * U4 ** 3 * r4 ** 2 / m
        if abs(rho6_new - rho6) < 1e-6 and abs(dh_df_new - dh_df) < 1:
            break
        rho6 = 0.5 * (rho6 + rho6_new); dh_df = dh_df_new
    eta_ts = dh_shaft / dh_is_ts
    # diffuser: static rise Cp * q6 lowers the exducer static for the same outlet static -> more isentropic drop available
    P_diff_out = P6 + cp_diff * rho6 * c6 ** 2 / 2
    dh_is_diff = h01 * (1 - (P_diff_out / P0_CORE) ** EXG)
    eta_ts_diff = dh_shaft / dh_is_diff                        # combustor-exit total -> diffuser-exit static (what the cycle's P3 -> P_exit sees)
    eta_ts_core = dh_shaft / (h01 * (1 - (P6 / P0_CORE) ** EXG))  # combustor-exit total -> exducer static (plenum loss charged)
    C0 = math.sqrt(2 * dh_is_ts)
    a6 = math.sqrt(G * R * T6)
    T4 = T01 - (ct4 ** 2 + cm4 ** 2) / (2 * CP)
    # nozzle ring
    r2 = r3 * g['r2_over_r3']
    alpha3 = math.degrees(math.atan2(ct3, cm3))
    pitch3 = 2 * math.pi * r3 / g['Z_N']
    throat = pitch3 * math.cos(math.radians(alpha3)) - g['t_vane_TE'] / 1e3
    chord_N = (r2 - r3) / math.cos(math.radians(0.5 * (alpha3 + 45)))   # inlet metal angle ~45 deg (plenum swirl-free -> mild)
    a3 = math.sqrt(G * R * T3)
    out = dict(
        N_rpm=N, m_gas_kg_s=m, T01_C=T01 - 273.15, P01_bar_after_plenum=P01 / 1e5, W_shaft_kW=W / 1e3,
        dh_shaft_kJ_kg=dh_shaft / 1e3, dh_euler_kJ_kg=dh_eu / 1e3,
        wheel=dict(D4_mm=g['D4'], b4_mm=round(b4 * 1e3, 2), Z_blades=g['Z_R'], splitters=0, D6t_mm=g['D6t'], D6h_mm=g['D6h'],
                   trim=round(100 * (g['D6t'] / g['D4']) ** 2, 1), Lz_mm=g['Lz'], eps_axial_mm=g['eps_a'], eps_radial_mm=g['eps_r'],
                   U4_m_s=U4, U6t_m_s=U6t, psi=dh_eu / U4 ** 2, phi=c6 / U4, U_over_C0=U4 / C0,
                   Ns_rad=OM * math.sqrt(m / rho6) / dh_is_ts ** 0.75),
        rotor_inlet=dict(alpha4_deg=math.degrees(math.atan2(ct4, cm4)), ct4=ct4, cm4=cm4, c4=math.hypot(ct4, cm4), W4=W4, beta4_deg=beta4,
                         beta4_opt_deg=beta4_opt, T4_C=T4 - 273.15, P4_bar=P4 / 1e5, rho4=rho4, M4_abs=math.hypot(ct4, cm4) / math.sqrt(G * R * T4)),
        rotor_exit=dict(c6_m_s=c6, W6rms=W6, W6tip=W6t, Mrel6_tip=W6t / a6, beta6rms_deg=beta6, T6_C=T6 - 273.15,
                        P6_bar=P6 / 1e5, rho6=rho6, A6_mm2=A6 * 1e6, KE6_kJ_kg=c6 ** 2 / 2e3),
        nozzle=dict(Z_vanes=g['Z_N'], r_in_mm=r2 * 1e3, r_out_mm=r3 * 1e3, b_mm=round(b4 * 1e3, 2), alpha3_deg=alpha3,
                    c3_m_s=c3, M3=c3 / a3, throat_mm=throat * 1e3, chord_mm=chord_N * 1e3,
                    solidity=chord_N / pitch3, P3_bar=P3 / 1e5,
                    vane_count_logic='17 prime, odd, not a multiple of 11 blades, no 4/rev; |17-11|=6, |17-22|=5, |34-33|=1 only at 2nd vane harmonic (weak); NPF 17x1917 Hz = 32.6 kHz'),
        losses_kJ_kg=dict(nozzle=dh_N / 1e3, incidence=dh_inc / 1e3, passage=dh_p / 1e3, clearance=dh_cl / 1e3,
                          trailing_edge=dh_te / 1e3, disc_friction=dh_df / 1e3, exit_KE=c6 ** 2 / 2e3),
        dh_is_ts_kJ_kg=dh_is_ts / 1e3, PR_ts=P01 / P6, PR_ts_from_core=P0_CORE / P6,
        eta_ts=eta_ts, eta_ts_from_core_exit=eta_ts_core, eta_tt_approx=dh_shaft / (dh_is_ts - c6 ** 2 / 2), eta_ts_with_diffuser=eta_ts_diff,
        diffuser_Cp=cp_diff, P_diffuser_exit_bar=P_diff_out / 1e5,
    )
    return out


# ------------------------------------------------------------------ cycle vs ambient
P_SITE = 101325 * (1 - 2.25577e-5 * 50) ** 5.25588         # 50 m
REF = dict(T=288.15, P=101325.0, ma=0.395, PR=3.1, W_c=59.5e3)
ETA_C = REF['T'] * (REF['PR'] ** cs.EX_A - 1) / (REF['W_c'] / REF['ma'] / cs.CP_A)


def compressor_at(T_amb, P_amb):
    """constant physical 115k rpm: corrected speed Nc ~ 1/sqrt(T); corrected flow ~ Nc, head (PR^x - 1) ~ Nc^2."""
    s2 = REF['T'] / T_amb
    ma = REF['ma'] * (P_amb / REF['P']) * math.sqrt(REF['T'] / T_amb) * math.sqrt(s2)
    PR = (1 + (REF['PR'] ** cs.EX_A - 1) * s2) ** (1 / cs.EX_A)
    return ma, PR


def sweep(eta_t, eta_d_ref=None, uc0_ref=None, label=''):
    rows = []
    for tc in (0, 15, 30, 40, 45):
        T = tc + 273.15
        ma, PR = compressor_at(T, P_SITE)
        c = dict(ma=ma, PR=PR, TIT=T01, eta_c=ETA_C, eta_t=eta_t, arch='single', eps=0.0, T_amb=T, P_amb=P_SITE, booster=False)
        r = cs.cycle(c)
        # mild U/C0 correction of the turbine efficiency off the 15 C point (parabola, 1.5*(dv)^2)
        if uc0_ref:
            dh = cs.CP_G * T01 * (1 - (P_SITE * 1.02 / r['P3']) ** cs.EX_G)
            uc0 = (OM * GEO['D4'] / 2e3) / math.sqrt(2 * dh)
            c['eta_t'] = eta_t * (1 - 1.5 * (uc0 / uc0_ref - 1) ** 2)
            r = cs.cycle(c)
        P_gen_shaft = r['P_shaft']
        P_el_gross = P_gen_shaft * 0.95 * 0.96
        P_net = P_el_gross - 600.0
        W_c = ma * cs.CP_A * (r['T2'] - T)
        rows.append(dict(T_amb_C=tc, ma_kg_s=round(ma, 4), PR=round(PR, 3), eta_t_used=round(c['eta_t'], 4),
                         W_compressor_kW=round(W_c / 1e3, 2), W_turbine_kW=round((P_gen_shaft + W_c) / 1e3, 2),
                         P_gen_shaft_kW=round(P_gen_shaft / 1e3, 2), P_el_gross_kW=round(P_el_gross / 1e3, 2),
                         P_el_net_kW=round(P_net / 1e3, 2), fuel_kW=round(r['Q_fuel'] / 1e3, 1),
                         eta_el_net_pct=round(100 * P_net / r['Q_fuel'], 2), T_exhaust_C=round(r['T_hot'] - 273.15, 0)))
    return rows


def main():
    ml = meanline()
    w, ri, re_, nz, L = ml['wheel'], ml['rotor_inlet'], ml['rotor_exit'], ml['nozzle'], ml['losses_kJ_kg']
    print('D2R radial turbine meanline (bought wheel D4 %.0f, %d blades, exducer %.0f/%.0f, trim %.0f)'
          % (w['D4_mm'], w['Z_blades'], w['D6t_mm'], w['D6h_mm'], w['trim']))
    print('  U4 %.0f m/s  psi %.3f  phi %.3f  U/C0 %.3f  Ns %.2f  b4 %.1f mm' % (w['U4_m_s'], w['psi'], w['phi'], w['U_over_C0'], w['Ns_rad'], w['b4_mm']))
    print('  rotor inlet: alpha4 %.0f  beta4 %.1f (opt %.1f)  M4 %.2f  P4 %.2f bar  T4 %.0f C'
          % (ri['alpha4_deg'], ri['beta4_deg'], ri['beta4_opt_deg'], ri['M4_abs'], ri['P4_bar'], ri['T4_C']))
    print('  exit: c6 %.0f m/s  Mrel tip %.2f  beta6rms %.0f  T6 %.0f C  P6 %.3f bar' % (re_['c6_m_s'], re_['Mrel6_tip'], re_['beta6rms_deg'], re_['T6_C'], re_['P6_bar']))
    print('  nozzle: %d vanes r %.1f->%.1f mm, b %.1f, alpha3 %.1f deg, M3 %.2f, throat %.2f mm, solidity %.2f'
          % (nz['Z_vanes'], nz['r_in_mm'], nz['r_out_mm'], nz['b_mm'], nz['alpha3_deg'], nz['M3'], nz['throat_mm'], nz['solidity']))
    print('  losses kJ/kg: ' + '  '.join('%s %.1f' % (k, v) for k, v in L.items()))
    print('  dh_is,ts %.1f kJ/kg  PR_ts %.2f (from core exit %.2f)  eta_ts %.3f (from core exit %.3f)  eta_tt %.3f  eta_ts incl. diffuser Cp %.2f: %.3f'
          % (ml['dh_is_ts_kJ_kg'], ml['PR_ts'], ml['PR_ts_from_core'], ml['eta_ts'], ml['eta_ts_from_core_exit'], ml['eta_tt_approx'], CP_DIFF, ml['eta_ts_with_diffuser']))
    # alternatives (sensitivity) - wheel trim and blade count
    alts = {}
    for lab, mod in (('D4 76 trim 72 (HX40 76/64.5)', dict(D4=76.0, D6t=64.5)), ('D4 80 trim 76 (80/69.7)', dict(D4=80.0, D6t=69.7)),
                     ('D4 78 trim 84 (78/71.5)', dict(D6t=71.5)), ('12 blades', dict(Z_R=12)), ('clearance 0.5 mm', dict(eps_a=0.5, eps_r=0.5)), ('b4 12 mm', dict(b4=12.0)),
                     ('D4 78 trim 76 (78/68)', dict(D6t=68.0)), ('diffuser Cp 0.35', dict(cp_diff=0.35))):
        g = dict(GEO); g.update(mod)
        try:
            a = meanline(g)
        except ValueError as e:
            alts[lab] = dict(error=str(e)); print('  alt %-30s %s' % (lab, e)); continue
        alts[lab] = dict(eta_ts=round(a['eta_ts'], 4), eta_ts_diff=round(a['eta_ts_with_diffuser'], 4), c6=round(a['rotor_exit']['c6_m_s'], 1),
                         PR_ts=round(a['PR_ts_from_core'], 3), U_over_C0=round(a['wheel']['U_over_C0'], 3))
        print('  alt %-30s eta_ts %.3f  with diffuser %.3f  c6 %.0f  PR_ts(core) %.2f' % (lab, a['eta_ts'], a['eta_ts_with_diffuser'], a['rotor_exit']['c6_m_s'], a['PR_ts_from_core']))
    # cycle sweep with the diffuser-credited efficiency (what the cycle's static exit sees) and the bare eta_ts
    uc0_ref = w['U_over_C0']
    rows = sweep(ml['eta_ts_with_diffuser'], uc0_ref=uc0_ref)
    rows_bare = sweep(ml['eta_ts'], uc0_ref=uc0_ref)
    print('\nElectric output (concept_study.cycle single-shaft, eps 0, gen 0.95 x conv 0.96, -0.6 kW aux), eta_c %.3f:' % ETA_C)
    print('  T_amb  ma     PR    eta_t   W_c    W_t    gen-shaft  el-net  eta_el  T_exh  | bare eta_ts: el-net')
    for r, rb in zip(rows, rows_bare):
        print('  %4d  %.3f  %.2f  %.3f  %5.1f  %5.1f  %6.1f  %7.1f  %5.1f%%  %4.0f   | %5.1f' % (
            r['T_amb_C'], r['ma_kg_s'], r['PR'], r['eta_t_used'], r['W_compressor_kW'], r['W_turbine_kW'], r['P_gen_shaft_kW'],
            r['P_el_net_kW'], r['eta_el_net_pct'], r['T_exhaust_C'], rb['P_el_net_kW']))
    res = dict(title='GR180 D2R radial turbine for a bought turbo wheel: meanline + electric output vs ambient', date='2026-10-23',
               script='sim/variant_d/d2r_turbine.py', meanline=ml, alternatives=alts,
               compressor_model=dict(ref=REF, eta_c=ETA_C, law='constant physical speed; corrected flow ~ Nc, (PR^x-1) ~ Nc^2'),
               cycle_basis='concept_study.cycle arch single, eps 0, booster False (4 bar gas), P_exit = 1.02 Pa (HX + stack), site 50 m; P_net = P_gen_shaft*0.95*0.96 - 0.6 kW',
               electric_vs_ambient_diffuser=rows, electric_vs_ambient_bare_eta_ts=rows_bare)
    json.dump(res, open(os.path.join(HERE, 'd2r_turbine.json'), 'w'), indent=1)
    print('-> sim/variant_d/d2r_turbine.json')


if __name__ == '__main__':
    main()
