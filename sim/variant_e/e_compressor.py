# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - centrifugal compressor meanline: bought turbocharger-class impeller + our vaned diffuser + axisymmetric collector.

Design point from sim/variant_e/e_cycle.json (30 C, 50 m, 3.0 kg/s, PR_tt 4.0, 35,000 rpm).  Steps:
  1. inducer: tip diameter for minimum relative tip Mach at the given hub (quill socket + nose nut, D1h 76 mm);
  2. impeller exit: backswept (beta2b -38 deg) main + splitter blades, Wiesner slip, b2 from the exit flow coefficient;
  3. losses (Oh, Yoon & Chung 1997 'optimum set': incidence, skin friction, blade loading, tip clearance, mixing,
     disc friction, recirculation, leakage) -> impeller efficiency and parasitic work;
  4. vaneless gap + 2.5D wedge vaned diffuser (prime vane count), loss coefficient from the inlet Mach / diffusion;
  5. axisymmetric collector: 90 deg bend + deswirl vanes + annulus into the cool casing (no scroll) -> stage efficiency.
Then a comparison with turbocharger frames whose published volume flow / pressure ratio bracket the stage (the
Accelleron TPS-F volume-flow chart, MAN/PBST TCR, MHI MET-SR/ER) - the wheel DIAMETERS of those frames are NOT
published: our D2 is an ESTIMATE to be replaced by the supplier drawing (then re-run this script with its geometry).

Run:  python3 sim/variant_e/e_compressor.py  ->  sim/variant_e/e_compressor.json
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e_props as gp                                                      # noqa: E402

CY = json.load(open(os.path.join(HERE, 'e_cycle.json')))
DP = CY['design_point']
N = 35000.0; OM = N * math.pi / 30
M = DP['air_kg_s']
T01 = DP['stations']['compressor_in']['T_C'] + 273.15
P01 = DP['stations']['compressor_in']['P_bar'] * 1e5
PR_TT = DP['PR']
air, _ = gp.moist_air(T01 - 0.4, P01, 0.40)
R = air.R

GEO = dict(D1h=76.0,            # hub at the inducer LE: AF19 quill socket in the nose + M24 nut seat (mm)
           beta2b=-38.0,        # blade exit angle from radial (backsweep)
           Z_main=9, Z_split=9, t_b=2.0, t_LE=1.0, eps=0.45,   # blade thickness at exit / LE, tip clearance mm
           Lz_over_D2=0.33, b2_over_D2=None, inc_opt=0.0,
           r3_over_r2=1.08,     # vaneless gap to the diffuser vane LE
           r4_over_r3=1.62, Z_vd=17, vd_div=9.0,   # vaned diffuser (wedge channels, 9 deg divergence)
           scroll_c=60.0, cone_D_out=254.0)


def static_from_total(T0, P0, c):
    T = air.T_from_h(air.h(T0) - c * c / 2, T0)
    P = P0 * math.exp((air.s0(T) - air.s0(T0)) / R)
    return T, P, P / (R * T)


def inducer(geo):
    """tip radius giving minimum relative Mach at the inducer tip (axial inflow, no prewhirl)"""
    rh = geo['D1h'] / 2e3
    best = None
    for k in range(300):
        rt = rh + 0.04 + k * 0.0003
        A = math.pi * (rt ** 2 - rh ** 2) * (1 - 0.04)                 # 4 % blade blockage at the LE
        c, ok = 100.0, True
        for _ in range(60):
            T, P, rho = static_from_total(T01, P01, c)
            c_new = M / (rho * A)
            if c_new > 300.0:
                ok = False
                break
            if abs(c_new - c) < 1e-4:
                break
            c = 0.5 * (c + c_new)
        if not ok:
            continue
        Wt = math.hypot(c, OM * rt)
        a = math.sqrt(air.gamma(T) * R * T)
        if best is None or Wt / a < best['M1t_rel']:
            best = dict(r1t=rt, r1h=rh, c1=c, T1=T, P1=P, rho1=rho, W1t=Wt, M1t_rel=Wt / a, a1=a, A1=A)
    return best


def meanline(geo=GEO, eta_guess=0.82):
    ind = inducer(geo)
    r1t, r1h, c1 = ind['r1t'], ind['r1h'], ind['c1']
    r1 = math.sqrt((r1t ** 2 + r1h ** 2) / 2)
    W1 = math.hypot(c1, OM * r1)
    beta1t = math.degrees(math.atan2(OM * r1t, c1))
    beta1rms = math.degrees(math.atan2(OM * r1, c1))
    # required actual stage work
    T02s = air.T_isentropic(T01, PR_TT)
    dh_is = air.h(T02s) - air.h(T01)
    Zeff = geo['Z_main'] + 0.75 * geo['Z_split']
    sigma = 1 - math.sqrt(math.cos(math.radians(abs(geo['beta2b'])))) / Zeff ** 0.7      # Wiesner
    tb = math.tan(math.radians(abs(geo['beta2b'])))
    eta_imp, paras = 0.90, 0.025
    for it in range(60):
        dh_act = dh_is / eta_guess                                       # total stage work (incl. parasitic)
        dh_eu = dh_act / (1 + paras)
        phi2 = 0.22                                                      # exit flow coefficient cm2/U2 (TC practice 0.20-0.25)
        U2 = (dh_eu / (sigma - phi2 * tb)) ** 0.5
        r2 = U2 / OM
        cm2 = phi2 * U2
        ct2 = sigma * U2 - cm2 * tb
        c2 = math.hypot(cm2, ct2)
        T02 = air.T_from_h(air.h(T01) + dh_act, T01)
        # impeller exit total pressure from the impeller efficiency
        P02 = P01 * math.exp((air.s0(air.T_from_h(air.h(T01) + eta_imp * dh_eu, T01)) - air.s0(T01)) / R)
        T2, P2, rho2 = static_from_total(T02, P02, c2)
        b2 = M / (rho2 * cm2 * 2 * math.pi * r2 * (1 - (geo['Z_main'] + geo['Z_split']) * geo['t_b'] / 1e3 / (2 * math.pi * r2)))
        W2 = math.hypot(cm2, U2 - ct2)
        alpha2 = math.degrees(math.atan2(ct2, cm2))
        a2 = math.sqrt(air.gamma(T2) * R * T2)
        # ---------------- losses (Oh, Yoon, Chung 1997)
        Lz = geo['Lz_over_D2'] * 2 * r2
        Lb = math.pi / 8 * (2 * r2 - (r1t + r1h) - b2 + 2 * Lz) * 2 / (math.cos(math.radians(beta1rms)) + math.cos(math.radians(abs(geo['beta2b']))))
        w2p = 2 * math.pi * r2 * math.cos(math.radians(abs(geo['beta2b']))) / Zeff          # passage width at the exit
        w1p = 2 * math.pi * r1 * math.cos(math.radians(beta1rms)) / Zeff                    # passage width at the inlet (rms)
        h1p = r1t - r1h
        Dh = 0.5 * (2 * w2p * b2 / (w2p + b2) + 2 * w1p * h1p / (w1p + h1p))
        nu = 1.6e-5
        Re = W1 * Dh / nu
        Cf = 0.0412 * Re ** -0.1925 if Re > 1e4 else 0.005
        Wbar = (2 * W2 + W1 + 0.5 * (math.hypot(c1, OM * r1t) + W1)) / 4
        dh_sf = 5.6 * Cf * (Lb / Dh) * Wbar ** 2 / 2 * 0.5
        Df = 1 - W2 / ind['W1t'] + 0.75 * dh_eu / U2 ** 2 / ((ind['W1t'] / W2) * (Zeff / math.pi * (1 - r1t / r2) + 2 * r1t / r2))
        dh_bl = 0.05 * Df ** 2 * U2 ** 2
        dh_inc = 0.5 * (W1 * math.sin(math.radians(geo['inc_opt'] + 2.0))) ** 2 * 0.6   # 2 deg off-optimum at the rms radius
        eps = geo['eps'] / 1e3
        dh_cl = 0.6 * eps / b2 * ct2 * math.sqrt(4 * math.pi / (b2 * Zeff) * (r1t ** 2 - r1h ** 2) / ((r2 - r1t) * (1 + rho2 / ind['rho1'])) * ct2 * c1)
        eps_w, bstar = 0.15, 1.0
        dh_mix = 1 / (1 + math.tan(math.radians(alpha2)) ** 2) * ((1 - eps_w - bstar) / (1 - eps_w)) ** 2 * c2 ** 2 / 2
        # parasitic
        rho_bar = 0.5 * (ind['rho1'] + rho2)
        Re_df = U2 * r2 / nu
        f_df = 0.0622 / Re_df ** 0.2
        dh_df = f_df * rho_bar * r2 ** 2 * U2 ** 3 / (4 * M)
        dh_rc = 8e-5 * math.sinh(3.5 * math.radians(alpha2) ** 3) * Df ** 2 * U2 ** 2
        dh_lk = 0.6 * eps / b2 * c2 * U2 * 0.08                              # (scaled Aungier leakage term, small for a shrouded-gap TC wheel)
        dh_sec = 0.020 * dh_eu                                            # secondary flow / jet-wake beyond the mixing model: calibration
                                                                         # to TC impeller test data (eta_imp,tt ~0.92-0.93 at PR 4), est
        int_loss = dh_inc + dh_sf + dh_bl + dh_cl + dh_mix + dh_sec
        paras_new = (dh_df + dh_rc + dh_lk) / dh_eu
        eta_imp_new = (dh_eu - int_loss) / dh_eu
        # ---------------- vaneless gap + vaned diffuser + scroll + cone
        r3 = r2 * geo['r3_over_r2']
        b3 = b2 * 0.95
        ct3 = ct2 * r2 / r3 * 0.98
        T3, P3, rho3 = static_from_total(T02, P02, math.hypot(ct3, 0.0))
        cm3 = M / (rho3 * 2 * math.pi * r3 * b3)
        c3 = math.hypot(ct3, cm3)
        T3, P3, rho3 = static_from_total(T02, P02, c3)
        M3 = c3 / math.sqrt(air.gamma(T3) * R * T3)
        alpha3 = math.degrees(math.atan2(ct3, cm3))
        r4 = r3 * geo['r4_over_r3']
        # channel area ratio of a wedge vaned diffuser (straight channels, divergence vd_div)
        throat = 2 * math.pi * r3 * math.cos(math.radians(alpha3)) / geo['Z_vd'] * 0.92
        L_ch = (r4 - r3) / math.cos(math.radians(0.5 * (alpha3 + 40.0)))
        AR_vd = (throat + 2 * L_ch * math.tan(math.radians(geo['vd_div'] / 2))) / throat
        c4 = c3 / AR_vd * 1.08                                           # blockage growth
        K_vgap = 0.03 + 0.02 * (r3 / r2 - 1) / 0.08                      # vaneless gap total-pressure loss / q2
        K_vd = 0.10 + 0.25 * max(M3 - 0.85, 0) ** 2 * 4                  # vaned diffuser loss / q3 (Mach penalty above 0.85)
        q2 = 0.5 * rho2 * c2 ** 2; q3 = 0.5 * rho3 * c3 ** 2
        T4, P4s, rho4 = static_from_total(T02, P02, c4)
        q4 = 0.5 * rho4 * c4 ** 2
        # axisymmetric collector (no scroll): 90 deg bend radial -> axial (K 0.20), 23-vane deswirl cascade (K 0.15) and the
        # residual head dumped in the cool casing (annulus r 261..305, ~13 m/s) -> K 0.45 on the vaned-diffuser exit head
        A_ann = math.pi * (0.305 ** 2 - 0.261 ** 2)
        c_ann = M / (rho4 * A_ann)
        dP_scroll = 0.45 * q4
        A_scroll, D_scroll = A_ann, 0.0
        c_pipe = c_ann
        P0_out = P02 - K_vgap * q2 - K_vd * q3 - dP_scroll
        T0_out = T02
        eta_stage = (air.h(air.T_isentropic(T01, P0_out / P01)) - air.h(T01)) / (air.h(T0_out) - air.h(T01))
        # adjust: we need PR_tt = 4.0 at the flange -> scale the work
        PR_got = P0_out / P01
        if abs(PR_got - PR_TT) < 1e-5 and abs(eta_imp_new - eta_imp) < 1e-6 and abs(paras_new - paras) < 1e-6:
            break
        eta_imp, paras = 0.5 * (eta_imp + eta_imp_new), 0.5 * (paras + paras_new)
        eta_guess = eta_stage
    U1t = OM * r1t
    out = dict(
        N_rpm=N, m_kg_s=M, T01_C=T01 - 273.15, P01_bar=P01 / 1e5, PR_tt=PR_TT, Q1_m3_s=M / (P01 / (R * T01)),
        work=dict(dh_is_kJ_kg=dh_is / 1e3, dh_actual_kJ_kg=dh_act / 1e3, dh_euler_kJ_kg=dh_eu / 1e3, parasitic_frac=paras,
                  work_factor_dh0_U2sq=dh_act / U2 ** 2, slip_sigma=sigma),
        inducer=dict(D1t_mm=2 * r1t * 1e3, D1h_mm=2 * r1h * 1e3, c1_m_s=c1, U1t_m_s=U1t, W1t_m_s=ind['W1t'], M1t_rel=ind['M1t_rel'],
                     beta1t_deg=beta1t, beta1rms_deg=beta1rms, hub_tip=r1h / r1t),
        impeller=dict(D2_mm=2 * r2 * 1e3, U2_m_s=U2, b2_mm=b2 * 1e3, b2_D2=b2 / (2 * r2), beta2b_deg=geo['beta2b'], Z=f"{geo['Z_main']}+{geo['Z_split']}",
                      Lz_mm=Lz * 1e3, eps_mm=geo['eps'], cm2=cm2, ct2=ct2, c2=c2, W2=W2, alpha2_deg=alpha2, M2_abs=c2 / a2,
                      de_Haller_W2_W1t=W2 / ind['W1t'], T2_C=T2 - 273.15, P2_bar=P2 / 1e5, Df=Df, eta_impeller_tt=eta_imp_new,
                      phi=M / (P01 / (R * T01)) / ((2 * r2) ** 2 * U2), Ns=OM * math.sqrt(M / (P01 / (R * T01))) / dh_is ** 0.75,
                      Mu2=U2 / math.sqrt(air.gamma(T01) * R * T01),
                      material='Al 2618-T61 forged, 5-axis milled (TC standard); tip speed %.0f m/s at T2 %.0f C is inside the TC range (<= 560 m/s Al at PR 4.5-5)' % (U2, T02 - 273.15)),
        losses_kJ_kg=dict(incidence=dh_inc / 1e3, skin_friction=dh_sf / 1e3, blade_loading=dh_bl / 1e3, clearance=dh_cl / 1e3, mixing=dh_mix / 1e3,
                          secondary_calibration=dh_sec / 1e3,
                          disc_friction=dh_df / 1e3, recirculation=dh_rc / 1e3, leakage=dh_lk / 1e3),
        diffuser=dict(r3_mm=r3 * 1e3, r4_mm=r4 * 1e3, b3_mm=b3 * 1e3, Z_vanes=geo['Z_vd'], alpha3_deg=alpha3, M3=M3, c3_m_s=c3, throat_mm=throat * 1e3,
                      AR=AR_vd, c4_m_s=c4, K_vaneless=K_vgap, K_vaned=K_vd,
                      build='17 straight wedge vanes (2.5D milled into the diffuser plate, 6082-T6), prime count vs 9+9 blades; LE re-cut ring option for matching'),
        collector=dict(type='axisymmetric 90 deg bend + 23 deswirl vanes (2.5D on the back-plate rim) + annulus r 261..305 into the cool casing (no scroll, no pipe)',
                       annulus_area_mm2=A_scroll * 1e6, c_annulus_m_s=c_pipe, K_on_q4=0.45,
                       note='a bought TC compressor casing (scroll) is the fallback if its inlet fits the annular plenum; then a DN250 pipe feeds the cool casing'),
        stage=dict(P0_out_bar=P0_out / 1e5, PR_tt=P0_out / P01, eta_tt_flange=eta_stage, T0_out_C=T0_out - 273.15,
                   dp_vaneless_kPa=K_vgap * q2 / 1e3, dp_vaned_kPa=K_vd * q3 / 1e3, dp_collector_kPa=dP_scroll / 1e3),
        cycle_assumed_eta_c=CY['budget_inputs']['eta_c'])
    return out


def frames():
    """turbocharger frames that bracket the stage (published flow / PR; diameters are our ESTIMATE)"""
    return [
        dict(maker='Accelleron (CH)', series='TPS-F (TPS52-F / TPS57-F)', published='400-3300 kW engines, PR <= 5.2 (Al wheel), compressor peak eta > 84 %, '
              'splitter backswept wheels, mixed-flow turbine + nozzle ring, plain bearings on squeeze film; volume-flow chart puts ~2.6 m3/s between TPS52 and TPS57',
             source='https://accelleron.com/content/dam/accelleronind/documents/TPS-F-Brochure.pdf', fit='first choice (spare-part wheels: compressor + turbine shaft&wheel)'),
        dict(maker='MAN Energy Solutions / PBS Turbo (DE/CZ)', series='TCR14-TCR18', published='TCR family 390-6700 kW engines, PR 4.7 (5.2-5.4 special), radial turbine, optional VTG nozzle',
             source='MAN ES TCR brochure (via nauticexpo) / Riviera news', fit='alternative; PBST (Velka Bites, CZ) also builds small gas turbines'),
        dict(maker='MHI-MME (JP)', series='MET-SRC / MET-ER (MET18SRC, MET16ER)', published='radial turbocharger for 4-stroke engines; MET16ER ~1000 kW system',
             source='https://www.mhi.com/news/1808302131.html', fit='alternative (ask for MET18-22 class wheels)'),
        dict(maker='Chinese makers (Hunan Tyen, Changzhou E&E Turbo-Power, ZJ/ Wuxi licensed lines)', series='TPS/TCR-equivalent large radial TCs, spare wheels',
             published='not verified (no datasheet found)', source='-', fit='cost option: wheels + friction welding to our shaft (as D2)'),
        dict(maker='EXCLUDED', series='Napier (UK) - owned by Wabtec (US) since 2013; Garrett / BorgWarner / Cummins Holset (US)', published='-',
             source='https://napier-turbochargers.com/news/the-sale-of-napier-turbochargers-to-wabtec-corporation', fit='no US suppliers')]


def main():
    ml = meanline()
    i, im, d, sc, st = ml['inducer'], ml['impeller'], ml['diffuser'], ml['collector'], ml['stage']
    print('Version E compressor meanline (%.3f kg/s, PR_tt %.2f, %d rpm)' % (M, PR_TT, N))
    print('  inducer D1t %.1f / D1h %.0f mm, c1 %.0f m/s, U1t %.0f, W1t %.0f, M1t,rel %.3f, beta1t %.1f' % (
        i['D1t_mm'], i['D1h_mm'], i['c1_m_s'], i['U1t_m_s'], i['W1t_m_s'], i['M1t_rel'], i['beta1t_deg']))
    print('  impeller D2 %.1f mm, U2 %.0f m/s, b2 %.1f mm (b2/D2 %.3f), Lz %.0f, alpha2 %.1f, M2 %.2f, W2/W1t %.2f, phi %.4f, Ns %.3f, Mu2 %.2f, work factor %.3f, slip %.3f' % (
        im['D2_mm'], im['U2_m_s'], im['b2_mm'], im['b2_D2'], im['Lz_mm'], im['alpha2_deg'], im['M2_abs'], im['de_Haller_W2_W1t'], im['phi'],
        im['Ns'], im['Mu2'], ml['work']['work_factor_dh0_U2sq'], ml['work']['slip_sigma']))
    print('  losses kJ/kg: ' + '  '.join('%s %.2f' % (k, v) for k, v in ml['losses_kJ_kg'].items()))
    print('  impeller eta_tt %.3f, parasitic %.1f %%' % (im['eta_impeller_tt'], 100 * ml['work']['parasitic_frac']))
    print('  diffuser r3 %.0f r4 %.0f b3 %.1f, %d vanes, alpha3 %.1f, M3 %.2f, AR %.2f, c4 %.0f m/s' % (
        d['r3_mm'], d['r4_mm'], d['b3_mm'], d['Z_vanes'], d['alpha3_deg'], d['M3'], d['AR'], d['c4_m_s']))
    print('  collector: bend + deswirl, annulus c %.1f m/s' % sc['c_annulus_m_s'])
    print('  STAGE PR_tt %.3f, eta_tt (to the annulus exit) %.3f  [cycle assumes %.3f]; dp vaneless %.1f / vaned %.1f / bend+deswirl %.1f kPa' % (
        st['PR_tt'], st['eta_tt_flange'], ml['cycle_assumed_eta_c'], st['dp_vaneless_kPa'], st['dp_vaned_kPa'], st['dp_collector_kPa']))
    alts = {}
    for lab, mod in (('beta2b -30', dict(beta2b=-30.0)), ('beta2b -45', dict(beta2b=-45.0)), ('clearance 0.7 mm', dict(eps=0.7)),
                     ('7+7 blades', dict(Z_main=7, Z_split=7)), ('D1h 90 mm', dict(D1h=90.0)), ('vaneless gap r3/r2 1.12', dict(r3_over_r2=1.12))):
        g = dict(GEO); g.update(mod)
        a = meanline(g)
        alts[lab] = dict(D2_mm=round(a['impeller']['D2_mm'], 1), eta_tt=round(a['stage']['eta_tt_flange'], 4), M1t_rel=round(a['inducer']['M1t_rel'], 3),
                         U2=round(a['impeller']['U2_m_s'], 1))
        print('  alt %-24s D2 %.1f  U2 %.0f  eta_tt %.3f  M1t %.3f' % (lab, a['impeller']['D2_mm'], a['impeller']['U2_m_s'], a['stage']['eta_tt_flange'], a['inducer']['M1t_rel']))
    res = dict(title='GR180 version E compressor meanline (TC-class impeller + vaned diffuser + bend/deswirl collector)', date='2026-10-23',
               script='sim/variant_e/e_compressor.py', geometry_inputs=GEO, meanline=ml, alternatives=alts, frames=frames(),
               buy_spec='Al 2618-T61 forged & 5-axis milled backswept splitter impeller, D2 ~%.0f mm, inducer ~%.0f mm, b2 ~%.0f mm, rated >= 38,500 rpm '
                        '(110 %%) with burst / spin data, Campbell (17 diffuser vanes, 9 scroll-tongue / strut orders), bore to our shaft H6 or bore-less '
                        'with our stub (drawing from the supplier, then re-run this script)' % (im['D2_mm'], i['D1t_mm'], im['b2_mm']))
    json.dump(res, open(os.path.join(HERE, 'e_compressor.json'), 'w'), indent=1)
    print('-> sim/variant_e/e_compressor.json')


if __name__ == '__main__':
    main()
