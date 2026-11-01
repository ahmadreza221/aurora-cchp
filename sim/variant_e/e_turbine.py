# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - radial-inflow turbine for a BOUGHT turbocharger-class cast wheel (D4 ~288 mm) + 2.5D nozzle ring,
checked at the 770 C design point and at the 850 C peak (same hardware), plus creep-life estimates.

Meanline: same loss set as sim/variant_d/d2r_turbine.py (Baines / Moustapha et al. 2003: nozzle, incidence, passage,
tip clearance, trailing edge, disc friction, exit kinetic energy).  For each operating point the work is solved so the
exducer static pressure equals the cycle value (diffuser credited in the cycle) -> eta_ts, flow function, throat.
Gas: CH4-equivalent products from e_props (cp at the mean expansion temperature).

Life (ESTIMATE): Larson-Miller (C = 20) for IN713LC (wheel) and alloy X / 2.4665 (nozzle vanes) with stresses from
simple rotor / vane models and metal temperatures from the relative total temperatures.  Replace with the supplier's
FEA + material data.

Run:  python3 sim/variant_e/e_turbine.py  ->  sim/variant_e/e_turbine.json   (imports e_cycle for the 850 C point)
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e_props as gp                                                      # noqa: E402
import e_cycle as ec                                                      # noqa: E402

N = ec.N_D; OM = N * math.pi / 30
MU = 4.0e-5                                                               # gas viscosity ~800 K
GEO = dict(D4=288.0, Z_R=12, D6t=232.0, D6h=75.0, Lz=92.0, b4=30.0,      # TPS57/61-F, TCR18/20 class (ESTIMATE), 12 blades, no splitters
           t_LE=3.0, t_TE=2.0, eps_a=0.55, eps_r=0.55, s_back=3.0,
           Z_N=19, r3_over_r4=1.10, r2_over_r3=1.30, t_vane_TE=1.2)
ZETA_N = 0.06
K_P, K_A, K_R, K_AR = 0.11, 0.4, 0.75, -0.3


def gas(r):
    prod = r['prod']
    Tm = 0.5 * (r['TIT'] + r['T06'])
    cp = prod.cp(Tm)
    return cp, prod.R, cp / (cp - prod.R)


def meanline(geo, W, m, T01, P0, CP, R, G, P6_target=None):
    EXG = (G - 1) / G
    r4, r6t, r6h = geo['D4'] / 2e3, geo['D6t'] / 2e3, geo['D6h'] / 2e3
    r6 = math.sqrt((r6t ** 2 + r6h ** 2) / 2)
    b6 = r6t - r6h
    U4, U6, U6t = OM * r4, OM * r6, OM * r6t
    h01 = CP * T01
    dh_df = 1e3; rho6 = 0.43; b4 = geo['b4'] / 1e3
    for _ in range(100):
        dh_shaft = W / m
        dh_eu = dh_shaft + dh_df
        ct4 = dh_eu / U4
        block4 = 1 - geo['Z_R'] * geo['t_LE'] / 1e3 / (2 * math.pi * r4)
        rho4 = 1.0
        r3 = r4 * geo['r3_over_r4']
        for _ in range(40):
            cm4 = m / (rho4 * 2 * math.pi * r4 * b4 * block4)
            c4 = math.hypot(ct4, cm4)
            ct3 = ct4 * r4 / r3 * 1.02
            cm3 = cm4 * r4 / r3
            c3 = math.hypot(ct3, cm3)
            dh_N = ZETA_N * c3 ** 2 / 2
            T4 = T01 - c4 ** 2 / (2 * CP)
            P4 = P0 * ((T4 - dh_N / CP) / T01) ** (1 / EXG)
            rho4n = P4 / (R * T4)
            if abs(rho4n - rho4) < 1e-7:
                break
            rho4 = rho4n
        T3 = T01 - c3 ** 2 / (2 * CP)
        P3 = P0 * ((T3 - dh_N / CP) / T01) ** (1 / EXG)
        wt4 = ct4 - U4
        W4 = math.hypot(cm4, wt4)
        beta4 = math.degrees(math.atan2(wt4, cm4))
        ct4_opt = U4 * (1 - 0.63 * math.pi / geo['Z_R'])
        beta4_opt = math.degrees(math.atan2(ct4_opt - U4, cm4))
        dh_inc = 0.5 * (W4 * math.sin(math.radians(beta4 - beta4_opt))) ** 2
        A6 = math.pi * (r6t ** 2 - r6h ** 2) * (1 - geo['Z_R'] * geo['t_TE'] / 1e3 / (math.pi * (r6t + r6h)))
        c6 = m / (rho6 * A6)
        W6 = math.hypot(c6, U6); W6t = math.hypot(c6, U6t)
        beta6 = math.degrees(math.atan2(U6, c6))
        Lh = math.pi / 4 * ((geo['Lz'] / 1e3 - b4 / 2) + (r4 - r6t - b6 / 2))
        Dh = 0.5 * (4 * math.pi * r4 * b4 / (2 * math.pi * r4 + geo['Z_R'] * b4)
                    + 2 * math.pi * (r6t ** 2 - r6h ** 2) / (math.pi * (r6t - r6h) + geo['Z_R'] * b6))
        chord = math.hypot(geo['Lz'] / 1e3, r4 - r6)
        dh_p = K_P * (Lh / Dh + 0.68 * (1 - (r6 / r4) ** 2) * math.cos(math.radians(beta6)) / (b6 / chord)) * 0.5 * (W4 ** 2 + W6 ** 2)
        Ca = (1 - r6t / r4) / (cm4 * b4)
        Cr = (r6t / r4) * (geo['Lz'] / 1e3 - b4) / (c6 * r6 * b6)
        ea, er = geo['eps_a'] / 1e3, geo['eps_r'] / 1e3
        dh_cl = U4 ** 3 * geo['Z_R'] / (8 * math.pi) * (K_A * ea * Ca + K_R * er * Cr + K_AR * math.sqrt(ea * er * Ca * Cr))
        dh_te = 0.5 * W6 ** 2 * (geo['Z_R'] * geo['t_TE'] / 1e3 / (math.pi * (r6t + r6h) * math.cos(math.radians(beta6)))) ** 2
        h06 = h01 - dh_eu
        dh_int = dh_N + dh_inc + dh_p + dh_cl + dh_te
        dh_is_ts = dh_eu + dh_int + c6 ** 2 / 2
        T6 = h06 / CP - c6 ** 2 / (2 * CP)
        P6 = P0 * (1 - dh_is_ts / h01) ** (1 / EXG)
        rho6n = P6 / (R * T6)
        Re = rho4 * U4 * r4 / MU
        Cm = 0.051 * (geo['s_back'] / 1e3 / r4) ** 0.1 / Re ** 0.2
        dh_dfn = Cm * 0.5 * rho4 * U4 ** 3 * r4 ** 2 / m
        if abs(rho6n - rho6) < 1e-7 and abs(dh_dfn - dh_df) < 0.1:
            break
        rho6 = 0.5 * (rho6 + rho6n); dh_df = dh_dfn
    eta_ts = dh_shaft / dh_is_ts
    C0 = math.sqrt(2 * dh_is_ts)
    r2 = r3 * geo['r2_over_r3']
    alpha3 = math.degrees(math.atan2(ct3, cm3))
    pitch3 = 2 * math.pi * r3 / geo['Z_N']
    throat = pitch3 * math.cos(math.radians(alpha3)) - geo['t_vane_TE'] / 1e3
    a3 = math.sqrt(G * R * T3)
    T0rel4 = T4 + W4 ** 2 / (2 * CP)
    T0rel6m = T6 + W6 ** 2 / (2 * CP)
    return dict(
        W_kW=W / 1e3, m_kg_s=m, T01_C=T01 - 273.15, P01_bar=P0 / 1e5, dh_shaft_kJ_kg=dh_shaft / 1e3, eta_ts=eta_ts,
        eta_tt=dh_shaft / (dh_is_ts - c6 ** 2 / 2), U4_m_s=U4, U6t_m_s=U6t, U_over_C0=U4 / C0, psi=dh_eu / U4 ** 2, phi=c6 / U4,
        Ns=OM * math.sqrt(m / rho6) / dh_is_ts ** 0.75, PR_ts=P0 / P6, P6_bar=P6 / 1e5, T6_C=T6 - 273.15, c6_m_s=c6,
        Mrel6_tip=W6t / math.sqrt(G * R * T6), beta6rms_deg=beta6, A6_m2=A6,
        rotor_inlet=dict(alpha4_deg=math.degrees(math.atan2(ct4, cm4)), beta4_deg=beta4, beta4_opt_deg=beta4_opt, c4=c4, W4=W4, cm4=cm4,
                         M4=c4 / math.sqrt(G * R * T4), P4_bar=P4 / 1e5, T4_C=T4 - 273.15, T0rel4_C=T0rel4 - 273.15),
        T0rel6_rms_C=T0rel6m - 273.15,
        nozzle=dict(Z=geo['Z_N'], r_in_mm=r2 * 1e3, r_out_mm=r3 * 1e3, b_mm=geo['b4'], alpha3_deg=alpha3, c3=c3, M3=c3 / a3, throat_mm=throat * 1e3,
                    throat_area_mm2=throat * geo['Z_N'] * b4 * 1e6, P3_bar=P3 / 1e5),
        losses_kJ_kg=dict(nozzle=dh_N / 1e3, incidence=dh_inc / 1e3, passage=dh_p / 1e3, clearance=dh_cl / 1e3, trailing_edge=dh_te / 1e3,
                          disc_friction=dh_df / 1e3, exit_KE=c6 ** 2 / 2e3),
        flow_function=m * math.sqrt(T01) / P0)


def solve_point(r, geo=GEO):
    """work for the cycle's exducer static pressure (main gas only; buffer air is in the cycle)"""
    CP, R, G = gas(r)
    m = r['mg']
    lo, hi = 0.6 * r['mg'] * r['w_t'], 1.2 * r['mg'] * r['w_t']
    for _ in range(60):
        W = 0.5 * (lo + hi)
        a = meanline(geo, W, m, r['TIT'], r['P03'], CP, R, G)
        if a['P6_bar'] * 1e5 > r['p6']:
            lo = W                                                        # not enough expansion: more work
        else:
            hi = W
    a = meanline(geo, 0.5 * (lo + hi), m, r['TIT'], r['P03'], CP, R, G)
    a['gas'] = dict(cp=CP, R=R, gamma=G)
    a['cycle_eta_ts'] = r['eta_ts']
    return a


# ------------------------------------------------------------------ life (Larson-Miller, C = 20, LMP in 1000 K units)
IN713LC = [(23.3, 650.0), (24.0, 550.0), (25.0, 400.0), (26.0, 280.0), (27.0, 180.0), (28.0, 110.0)]      # MPa rupture (est, cast)
ALLOY_X = [(23.8, 165.0), (25.2, 110.0), (26.3, 70.0), (27.6, 41.0), (28.9, 25.0)]                          # 2.4665 sheet/plate (est)


def lmp_of(stress, curve):
    for (p0, s0), (p1, s1) in zip(curve[:-1], curve[1:]):
        if s1 <= stress <= s0:
            return p0 + (p1 - p0) * math.log(s0 / stress) / math.log(s0 / s1)
    p0, s0 = curve[-1] if stress < curve[-1][1] else curve[0]
    return p0


def life_h(stress, T_metal_K, curve, sf=1.25):
    P = lmp_of(stress * sf, curve) * 1e3
    return 10 ** (P / T_metal_K - 20)


def life(a, label):
    rho = 7910.0
    U4 = a['U4_m_s']
    rh_r4 = 0.32                                                           # blade root radius / tip radius at the inducer (est)
    sig_root = 0.5 * rho * U4 ** 2 * (1 - rh_r4 ** 2) * 0.55 / 1e6          # tapered radial blade, root at the hub
    sig_rim = 0.16 * rho * U4 ** 2 / 1e6                                   # scalloped back-disc rim / blade fillet at r4 (est)
    T_root = 0.5 * (a['rotor_inlet']['T0rel4_C'] + a['T0rel6_rms_C']) - 30.0 + 273.15
    T_rim = a['rotor_inlet']['T0rel4_C'] - 25.0 + 273.15
    L_root = life_h(sig_root, T_root, IN713LC); L_rim = life_h(sig_rim, T_rim, IN713LC)
    # nozzle vane: bending from the blade-row force, metal = peak gas (pattern factor 0.15) - 60 K film / radiation
    T_peak_gas = a['T01_C'] + 0.15 * (a['T01_C'] - 212.0)
    T_vane = T_peak_gas - 60.0 + 273.15
    sig_vane = 18.0                                                         # MPa, est (chord 45 x t 5, dp ~0.6 bar)
    L_vane = life_h(sig_vane, T_vane, ALLOY_X, sf=1.5)
    return dict(case=label, wheel_blade_root=dict(stress_MPa=round(sig_root), T_metal_C=round(T_root - 273.15), creep_life_h=L_root),
                wheel_rim=dict(stress_MPa=round(sig_rim), T_metal_C=round(T_rim - 273.15), creep_life_h=L_rim),
                nozzle_vane=dict(stress_MPa=sig_vane, T_peak_gas_C=round(T_peak_gas), T_metal_C=round(T_vane - 273.15), creep_life_h=L_vane),
                basis='IN713LC cast (est. LMP curve), SF 1.25 on stress; alloy X SF 1.5; C = 20')


def main():
    r770 = ec.D
    r850 = ec.offdesign(ec.T_DES, ec.TIT_PEAK)
    a = solve_point(r770)
    b = solve_point(r850)
    for lab, x in (('770 C design', a), ('850 C peak (same hardware)', b)):
        ri, nz, L = x['rotor_inlet'], x['nozzle'], x['losses_kJ_kg']
        print('%s: m %.3f kg/s, T01 %.0f C, P0 %.3f bar, W %.1f kW' % (lab, x['m_kg_s'], x['T01_C'], x['P01_bar'], x['W_kW']))
        print('  U4 %.0f m/s  U/C0 %.3f  psi %.3f  phi %.3f  Ns %.3f   eta_ts %.4f (cycle %.4f)  eta_tt %.4f  PR_ts %.3f' % (
            x['U4_m_s'], x['U_over_C0'], x['psi'], x['phi'], x['Ns'], x['eta_ts'], x['cycle_eta_ts'], x['eta_tt'], x['PR_ts']))
        print('  rotor inlet alpha4 %.1f beta4 %.1f (opt %.1f) M4 %.2f T0rel4 %.0f C | exit c6 %.0f m/s Mrel6t %.2f T6 %.0f C' % (
            ri['alpha4_deg'], ri['beta4_deg'], ri['beta4_opt_deg'], ri['M4'], ri['T0rel4_C'], x['c6_m_s'], x['Mrel6_tip'], x['T6_C']))
        print('  nozzle %d vanes r %.0f->%.0f b %.0f alpha3 %.1f M3 %.2f throat %.2f mm (area %.0f mm2)' % (
            nz['Z'], nz['r_in_mm'], nz['r_out_mm'], nz['b_mm'], nz['alpha3_deg'], nz['M3'], nz['throat_mm'], nz['throat_area_mm2']))
        print('  losses kJ/kg: ' + '  '.join('%s %.1f' % (k, v) for k, v in L.items()))
    la, lb = life(a, 'TIT 770 C'), life(b, 'TIT 850 C')
    for l in (la, lb):
        print('life %s: blade root %d MPa @ %d C -> %.2e h | rim %d MPa @ %d C -> %.2e h | nozzle vane @ %d C -> %.2e h' % (
            l['case'], l['wheel_blade_root']['stress_MPa'], l['wheel_blade_root']['T_metal_C'], l['wheel_blade_root']['creep_life_h'],
            l['wheel_rim']['stress_MPa'], l['wheel_rim']['T_metal_C'], l['wheel_rim']['creep_life_h'], l['nozzle_vane']['T_metal_C'],
            l['nozzle_vane']['creep_life_h']))
    # life-consumption factor: 1 h at 850 C = k h at 770 C (rim location, governing)
    k = min(la['wheel_rim']['creep_life_h'], la['wheel_blade_root']['creep_life_h']) / min(lb['wheel_rim']['creep_life_h'], lb['wheel_blade_root']['creep_life_h'])
    print('wheel creep: 1 h at 850 C consumes the life of %.0f h at 770 C' % k)
    alts = {}
    for lab, mod in (('D4 280', dict(D4=280.0)), ('D4 300', dict(D4=300.0)), ('13 blades', dict(Z_R=13)), ('clearance 0.8', dict(eps_a=0.8, eps_r=0.8)),
                     ('exducer 240/80', dict(D6t=240.0, D6h=80.0)), ('b4 26', dict(b4=26.0))):
        g = dict(GEO); g.update(mod)
        x = solve_point(r770, g)
        alts[lab] = dict(eta_ts=round(x['eta_ts'], 4), U_over_C0=round(x['U_over_C0'], 3), c6=round(x['c6_m_s'], 1), T0rel4_C=round(x['rotor_inlet']['T0rel4_C'], 1))
        print('  alt %-14s eta_ts %.4f  U/C0 %.3f  c6 %.0f  T0rel4 %.0f' % (lab, x['eta_ts'], x['U_over_C0'], x['c6_m_s'], x['rotor_inlet']['T0rel4_C']))
    res = dict(title='GR180 version E radial turbine (bought TC-class wheel) at 770 C design and 850 C peak', date='2026-10-23',
               script='sim/variant_e/e_turbine.py', geometry=GEO, design_770=a, peak_850=b, alternatives=alts, life=[la, lb],
               life_consumption_850_vs_770=k,
               matching=dict(throat_area_mm2=a['nozzle']['throat_area_mm2'], flow_function_770=a['flow_function'], flow_function_850=b['flow_function'],
                             note='fixed nozzle throat (no VTG): the 850 C point is the cycle off-design match (e_cycle.offdesign) - flow function '
                                  'changes only through the ellipse law; surge margin is in e_cycle.json'),
               wheel_spec='BUY: cast IN713LC (or K418 / MAR-M247 for margin) radial or mixed-flow TC turbine wheel D4 ~288 mm, 12 blades, exducer ~232/75, '
                          'friction / EB-welded by the supplier to our 42CrMo4 / IN718 stub shaft; max permitted speed >= 38,500 rpm (110 %%) at 750 C metal; '
                          'spin test 120 %% (42,000 rpm); supplier FEA + Campbell for 19 nozzle vanes and 1 combustor inlet (single can)',
               nozzle_spec='MAKE: 19 straight 2.5D vanes milled from one 2.4665 (alloy X) ring + bolted 2.4665 cover plate; throat set by a re-cut '
                           'vane trailing edge if the rig shows a mismatch; inner/outer piston-ring seals to the floating hot plenum')
    json.dump(res, open(os.path.join(HERE, 'e_turbine.json'), 'w'), indent=1, default=str)
    print('-> sim/variant_e/e_turbine.json')


if __name__ == '__main__':
    main()
