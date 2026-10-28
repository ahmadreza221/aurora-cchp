# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "iapws"]
# ///
"""AURORA-1000 first-cut meanline design: 2-stage centrifugal compressor + 2-stage axial turbine at 15,000 rpm,
plus the CCHP heat balance (exhaust -> hot water -> LiBr absorption chiller -> turbine inlet chilling + cold store).

Compressor stages: inducer sized for minimum relative tip Mach, Wiesner slip, 40 deg backsweep, vaned diffuser,
return channel between the stages. Turbine stages: repeating-stage velocity triangles at the mean radius, constant
axial velocity, zero exit swirl, Zweifel blade counts, NGV throat areas.
Run:  python3 sim/mw1_meanline.py        writes sim/mw1_meanline.json
"""
import json
import math
import os

import mw1_concept_study as G

HERE = os.path.dirname(os.path.abspath(__file__))
N = 15000.0
W = N * 2 * math.pi / 60
AUX_CCHP = 20e3                    # chiller solution pump, hot / chilled / cooling water pumps, tower fans
P_NET = 1000e3 + AUX_CCHP          # gas turbine net incl. the CCHP auxiliaries
CASE = dict(G.ARCH['R38'], eta_c=0.838, eta_t=0.901)


def compressor_stage(air, T01, P01, m, pr, eta, Z=(13, 13), backsweep=40.0, hub_ratio=0.38, name=''):
    """single centrifugal stage; returns geometry and states"""
    cp = air.cp(T01); g = cp / (cp - air.R)
    T02s = air.T_isentropic(T01, pr); dh0 = (air.h(T02s) - air.h(T01)) / eta
    T02 = air.T_of_h(air.h(T01) + dh0, T02s)
    # inducer: choose tip radius for minimum relative Mach at the shroud (no prewhirl)
    best = None
    for r1t in [0.05 + 0.002 * i for i in range(120)]:
        r1h = hub_ratio * r1t; A1 = math.pi * (r1t**2 - r1h**2)
        c1 = 100.0; ok = True
        for _ in range(60):
            T1 = T01 - c1**2 / (2 * cp); rho1 = P01 * (T1 / T01) ** (g / (g - 1)) / (air.R * T1)
            c1n = m / (rho1 * A1)
            if c1n > 260.0: ok = False; break                 # inducer too small (near choke)
            c1 = 0.5 * (c1 + c1n)
        if not ok or c1 > 0.75 * math.sqrt(g * air.R * T1): continue
        w1t = math.hypot(c1, W * r1t); M1rel = w1t / math.sqrt(g * air.R * T1)
        if best is None or M1rel < best['M1rel']:
            best = dict(r1t=r1t, r1h=r1h, c1=c1, M1rel=M1rel, beta1t=math.degrees(math.atan2(W * r1t, c1)))
    # exit: Wiesner slip with backsweep, work = sigma U2^2 (1 - phi2 tan(beta2))
    Zt = sum(Z); b2b = math.radians(backsweep)
    sigma = 1 - math.sqrt(math.cos(b2b)) / Zt ** 0.7
    phi2 = 0.28                                                # cm2 / U2
    U2 = math.sqrt(dh0 / (sigma * (1 - phi2 * math.tan(b2b))) / 1.02)   # 2 % disc friction + recirculation
    r2 = U2 / W
    cm2 = phi2 * U2; ct2 = sigma * U2 * (1 - phi2 * math.tan(b2b))
    c2 = math.hypot(cm2, ct2); T2 = T02 - c2**2 / (2 * cp)
    P02 = P01 * pr                                            # stage total pressure (efficiency includes diffuser)
    # static at impeller exit ~ total-to-static with impeller efficiency ~ eta + 0.06
    P2 = P01 * (1 + min(eta + 0.06, 0.94) * (T2 - T01) / T01) ** (g / (g - 1))
    rho2 = P2 / (air.R * T2); b2 = m / (rho2 * cm2 * 2 * math.pi * r2 * 0.92)          # 8 % blockage
    M2 = c2 / math.sqrt(g * air.R * T2)
    alpha2 = math.degrees(math.atan2(ct2, cm2))
    return dict(name=name, pr=pr, eta=eta, T01=T01, T02=T02, P01=P01, P02=P02, dh0=dh0, U2=U2, D2=2 * r2, b2=b2,
                r1t=best['r1t'], r1h=best['r1h'], D1t=2 * best['r1t'], M1rel_tip=best['M1rel'], beta1t=best['beta1t'],
                c1=best['c1'], sigma=sigma, M2=M2, alpha2=alpha2, Z=Z, backsweep=backsweep,
                diffuser=dict(r3_r2=1.10, r4_r2=1.60, vanes=19, alpha3=alpha2 - 2.0), slip=sigma)


def turbine_design(gas, T03, P03, P_out, m, eta, z=2, reaction=0.45, zweifel=0.85):
    """repeating axial stages at the mean radius; constant Cx, zero exit swirl after the last rotor"""
    dh_tot = eta * (gas.h(T03) - gas.h(gas.T_isentropic(T03, P_out / P03)))
    dh = dh_tot / z
    psi = 1.25; Um = math.sqrt(dh / psi); rm = Um / W
    phi = 0.50; Cx = phi * Um
    # repeating stage: alpha1 = alpha3 (exit swirl ~0 for the last; small for stage 1 to keep repeating)
    # psi = 2(1 - R) + 2 phi tan(alpha1)... with alpha1 = 0: tan(alpha2) = (psi/2 + 1 - R)/phi
    tan_a2 = (psi / 2 + 1 - reaction) / phi
    tan_b2 = tan_a2 - 1 / phi
    tan_b3 = (psi / 2 + reaction) / phi                       # rotor exit relative angle (magnitude)
    a2, b2_, b3 = math.degrees(math.atan(tan_a2)), math.degrees(math.atan(tan_b2)), math.degrees(math.atan(tan_b3))
    stages = []; T0, P0 = T03, P03
    for k in range(z):
        cp = gas.cp(T0); g = cp / (cp - gas.R)
        T0e = gas.T_of_h(gas.h(T0) - dh, T0 - dh / cp)
        T0es = gas.T_of_h(gas.h(T0) - dh / eta, T0 - dh / cp / eta)
        P0e = P0 * math.exp((gas.s0(T0es) - gas.s0(T0)) / gas.R)
        # NGV exit (station 2)
        C2 = Cx / math.cos(math.radians(a2)); T2 = T0 - C2**2 / (2 * cp)
        P2 = P0 * (1 - 0.03) * (T2 / T0) ** (g / (g - 1))
        rho2 = P2 / (gas.R * T2); M2 = C2 / math.sqrt(g * gas.R * T2)
        # inlet (station 1) and exit (station 3) heights
        T1 = T0 - Cx**2 / (2 * cp); rho1 = P0 * (T1 / T0) ** (g / (g - 1)) / (gas.R * T1)
        T3 = T0e - Cx**2 / (2 * cp); rho3 = P0e * (T3 / T0e) ** (g / (g - 1)) / (gas.R * T3)
        h1, h2, h3 = (m / (r * Cx * 2 * math.pi * rm) for r in (rho1, rho2, rho3))
        W3 = Cx / math.cos(math.radians(b3)); M3rel = W3 / math.sqrt(g * gas.R * T3)
        # Zweifel: pitch/axial chord = Z / (2 cos^2(a_out) (tan a_in + tan a_out))
        s_cx_n = zweifel / (2 * math.cos(math.radians(a2))**2 * (math.tan(math.radians(a2)) + 0))
        s_cx_r = zweifel / (2 * math.cos(math.radians(b3))**2 * (abs(tan_b2) + tan_b3))
        cx_n = max(0.85 * 0.5 * (h1 + h2), 0.026); cx_r = max(0.75 * 0.5 * (h2 + h3), 0.024)   # castable chords, AR ~1.2
        Zn = round(2 * math.pi * rm / (s_cx_n * cx_n)); Zr = round(2 * math.pi * rm / (s_cx_r * cx_r))
        if Zn % 2 == 0: Zn += 1                                  # odd vane counts vs blade counts (EO spread)
        o_throat = 2 * math.pi * rm / Zn * math.cos(math.radians(a2))
        A_throat = Zn * o_throat * h2
        stages.append(dict(stage=k + 1, T0_in=T0, P0_in=P0, T0_out=T0e, P0_out=P0e, C2=C2, M2=M2, M3rel=M3rel,
                           h_ngv_in=h1, h_ngv_out=h2, h_rot_out=h3, Z_ngv=Zn, Z_rot=Zr, cx_ngv=cx_n, cx_rot=cx_r,
                           A_throat_ngv=A_throat, T_rel_rotor_in=T2 + (Cx**2 + (C2 * math.sin(math.radians(a2)) - Um)**2) / (2 * cp)))
        T0, P0 = T0e, P0e
    return dict(Um=Um, Dm=2 * rm, psi=psi, phi=phi, reaction=reaction, Cx=Cx, alpha2=a2, beta2=b2_, beta3=b3,
                stages=stages, dh_tot=dh_tot)


def cchp(r, ma):
    gp = r['gas']; m = r['m_ex'] * ma
    q_hw = m * (gp.h(r['T6']) - gp.h(363.15)) * 0.95
    cop = 0.70; q_cool = q_hw * cop
    # inlet chilling 46 C / 30 % RH -> 15 C saturated (psychrometrics, kJ/kg dry air)
    def W(T, RH, P=100.725):
        ps = 0.61094 * math.exp(17.625 * T / (T + 243.04)); return 0.622 * RH * ps / (P - RH * ps)
    def h(T, w): return 1.006 * T + w * (2501 + 1.86 * T)
    w1, w2 = W(46, 0.30), W(15, 1.0)
    q_inlet = ma / (1 + w2) * (h(46, w1) - h(15, w2)) * 1e3
    condensate = ma / (1 + w2) * (w1 - w2)
    return dict(q_hotwater_kW=q_hw / 1e3, hotwater_flow_kg_s=q_hw / (4190 * 20), q_cooling_kW=q_cool / 1e3,
                q_inlet_chill_peak_kW=q_inlet / 1e3, q_coldstore_summer_kW=(q_cool - q_inlet) / 1e3,
                q_coldstore_winter_kW=q_cool / 1e3, tower_reject_kW=(q_hw + q_cool) / 1e3,
                condensate_l_h=condensate * 3600, fuel_kW=r['Q_fuel'] * ma / 1e3,
                eta_total=(1000e3 + q_hw) / (r['Q_fuel'] * ma))


def main():
    r = G.cycle(CASE, 'design_chilled'); ma = P_NET / r['P_net']
    air, gas = r['air'], r['gas']
    m_core = ma * (1 - G.BASE['leak'])
    # compressor: split PR so both stages have about the same work; return channel 1.5 % total pressure loss
    pr_tot = CASE['PR']; pr1 = math.sqrt(pr_tot) * 1.03; pr2 = pr_tot / pr1 / (1 - 0.015)
    s1 = compressor_stage(air, r['T1'], r['P1'], ma, pr1, 0.86, name='stage 1 (Al 2618)')
    T01b = s1['T02']; P01b = r['P1'] * pr1 * (1 - 0.015)
    s2 = compressor_stage(air, T01b, P01b, ma, pr2, 0.85, hub_ratio=0.45, name='stage 2 (Ti-6Al-4V)')
    mg = m_core * (1 + r['far'])
    t = turbine_design(gas, CASE['TIT'], r['P3'], r['P_back'] * 1.02, mg, CASE['eta_t'])
    c = cchp(r, ma)
    out = dict(rpm=N, ma=ma, eta_el=r['eta_el'], compressor=[s1, s2], turbine=t, cchp=c,
               gas_m3h=r['Q_fuel'] * ma / G.LHV_VOL * 3600)
    print('AURORA-1000 @ %.0f rpm: air %.2f kg/s (GT net %.0f kW incl. %.0f kW CCHP aux), eta_el %.1f %%, gas %.0f m3/h' % (
        N, ma, P_NET / 1e3, AUX_CCHP / 1e3, r['eta_el'] * 100, out['gas_m3h']))
    for s in (s1, s2):
        print('  %-20s PR %.2f eta %.2f  D1t %3.0f mm (hub %3.0f)  Mrel1 %.2f  beta1t %.0f  D2 %3.0f mm  U2 %3.0f  b2 %4.1f mm  '
              'M2 %.2f  alpha2 %.0f  blades %d+%d  T02 %.0f C' % (s['name'], s['pr'], s['eta'], s['D1t'] * 1e3,
              2 * s['r1h'] * 1e3, s['M1rel_tip'], s['beta1t'], s['D2'] * 1e3, s['U2'], s['b2'] * 1e3, s['M2'], s['alpha2'],
              s['Z'][0], s['Z'][1], s['T02'] - 273.15))
    print('  turbine: Dm %.0f mm  Um %.0f  psi %.2f phi %.2f R %.2f  alpha2 %.1f  beta2 %.1f  beta3 %.1f' % (
        t['Dm'] * 1e3, t['Um'], t['psi'], t['phi'], t['reaction'], t['alpha2'], t['beta2'], t['beta3']))
    for st in t['stages']:
        print('   stage %d: T0 %.0f->%.0f C  P0 %.2f->%.2f bar  M2 %.2f  M3rel %.2f  h %.1f/%.1f/%.1f mm  NGV %d  rotor %d  '
              'cx %.0f/%.0f mm  throat %.0f cm2  T_rel %.0f C' % (st['stage'], st['T0_in'] - 273.15, st['T0_out'] - 273.15,
              st['P0_in'] / 1e5, st['P0_out'] / 1e5, st['M2'], st['M3rel'], st['h_ngv_in'] * 1e3, st['h_ngv_out'] * 1e3,
              st['h_rot_out'] * 1e3, st['Z_ngv'], st['Z_rot'], st['cx_ngv'] * 1e3, st['cx_rot'] * 1e3,
              st['A_throat_ngv'] * 1e4, st['T_rel_rotor_in'] - 273.15))
    print('  CCHP: hot water %.0f kW (%.1f kg/s 95/75 C) -> LiBr %.0f kW cooling; inlet chilling peak %.0f kW; cold store '
          'summer %.0f / winter %.0f kW; tower %.0f kW; condensate %.0f l/h; total eff %.1f %%' % (
              c['q_hotwater_kW'], c['hotwater_flow_kg_s'], c['q_cooling_kW'], c['q_inlet_chill_peak_kW'],
              c['q_coldstore_summer_kW'], c['q_coldstore_winter_kW'], c['tower_reject_kW'], c['condensate_l_h'],
              c['eta_total'] * 100))
    json.dump(out, open(os.path.join(HERE, 'mw1_meanline.json'), 'w'), indent=1, default=lambda o: float(o) if isinstance(o, (int, float)) else str(o))


if __name__ == '__main__':
    main()
