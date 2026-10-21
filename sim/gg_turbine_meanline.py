# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 gas-generator turbine stage (NGV + rotor) - meanline / 3-radius design for the 24/7 CCHP rating.

Design point: N1 = 115k rpm, TIT = 800 C, intake chilled to 15 C, 50 m, recuperated cycle (sim/life_study.py point()).
Annulus kept from the tested hardware (rotor blade root Ø44.2, tip Ø70.3; NGV hub Ø44.5, shroud = tip + clearance) so the
existing tunnel/NGV/exhaust envelopes stay valid. Free-vortex swirl, axial exit (C2theta = 0, clean inflow to the FPT).
Blade counts from Zweifel loading, losses from Soderberg (Dixon) + aspect-ratio/Reynolds corrections + tip-clearance loss.
The tested JetMax geometry is checked against the measured CAD throats (NGV 1264 mm2, rotor 1530 mm2).

Run:  python3 sim/gg_turbine_meanline.py      -> sim/gg_turbine_design.json
"""
import json, math, os
import life_study as L

HERE = os.path.dirname(os.path.abspath(__file__))
CP, G = 1148.0, 1.333
R = CP * (G - 1) / G
N_RPM = 115e3; OM = N_RPM * 2 * math.pi / 60
R_HUB, R_TIP = 22.10e-3, 35.15e-3          # rotor blade root / tip (TW70 annulus, kept)
R_HUB_N, R_TIP_N = 22.25e-3, 35.35e-3      # NGV annulus (shroud = tip + 0.20 clearance)
R_HUB_EXIT = 19.0e-3                       # rotor hub radius at the trailing edge: flared hub lowers exit Cx (phi 1.10 -> 0.85)
TIP_GAP = 0.20e-3
ZW_TARGET = {'NGV': 0.85, 'ROTOR': 1.05}   # aft-loaded rotor profile, 29 blades (castable)
CHORD_AX = {'NGV': 9.5e-3, 'ROTOR': 8.2e-3}  # axial chords that fit the stack (NGV ring 15.0, rotor rim within the NGV shroud)
TE_THK = {'NGV': 0.50e-3, 'ROTOR': 0.45e-3}  # cast trailing edges (investment casting minimum ~0.4-0.5 mm)

def mu_gas(T):   # Sutherland, combustion gas ~ air
    return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)

def soderberg(defl_deg, h, b_ax, Re):
    """Soderberg nominal loss + aspect-ratio + Reynolds correction (Dixon & Hall, Fluid Mechanics..., ch.4)."""
    z0 = 0.04 + 0.06 * (defl_deg / 100.0) ** 2
    z1 = (1 + z0) * (0.993 + 0.075 * b_ax / h) - 1
    return z1 * (1e5 / Re) ** 0.25

def zweifel_pitch(Z, b_ax, a_in, a_out):  # angles from axial, signed, rad
    return Z * b_ax / (2 * math.cos(a_out) ** 2 * abs(math.tan(a_in) - math.tan(a_out)))

def design(verbose=True):
    p = L.point(N_RPM, 800, 'target', T_amb_C=15.0, alt_m=50.0, booster=False)
    ma, f = p['ma'], p['mf'] / p['ma']
    mg = ma * (1 + f)
    T01 = 800 + 273.15
    P01 = p['P3']
    w_c = 1005.0 * (p['T2'] - 288.15)
    dh = w_c / (0.985 * (1 + f))                         # turbine specific work per kg gas
    r_m = math.sqrt((R_HUB**2 + R_TIP**2) / 2); U_m = OM * r_m
    out = dict(N_rpm=N_RPM, mg=mg, T01=T01, P01=P01, dh=dh, r_m=r_m, U_m=U_m, psi=dh / U_m**2)
    # ---- iterate stage efficiency for exit state
    eta = 0.82
    for _ in range(20):
        T03 = T01 - dh / CP
        T03s = T01 - dh / (CP * eta)
        P03 = P01 * (T03s / T01) ** (G / (G - 1))
        # NGV exit (station 2) at mean: C2theta = dh/U_m
        Ct2m = dh / U_m
        A2 = math.pi * (R_TIP_N**2 - R_HUB_N**2)
        Cx2 = 250.0
        for _ in range(40):
            C2 = math.hypot(Ct2m, Cx2); T2 = T01 - C2**2 / (2 * CP)
            T2s = T01 - C2**2 / (2 * CP * 0.95); P2 = P01 * (T2s / T01) ** (G / (G - 1))
            rho2 = P2 / (R * T2); Cx2 = mg / (rho2 * A2)
        # rotor exit (station 3), axial
        A3 = math.pi * (R_TIP**2 - R_HUB_EXIT**2); Cx3 = 300.0
        for _ in range(40):
            T3 = T03 - Cx3**2 / (2 * CP); P3 = P03 * (T3 / T03) ** (G / (G - 1)); rho3 = P3 / (R * T3); Cx3 = mg / (rho3 * A3)
        rows = []; loss_n = loss_r = 0.0
        h_n, h_r = R_TIP_N - R_HUB_N, R_TIP - R_HUB
        for name, r in (('hub', R_HUB), ('mean', r_m), ('tip', R_TIP)):
            U = OM * r; Ct2 = Ct2m * r_m / r                 # free vortex
            a2 = math.atan2(Ct2, Cx2)                        # NGV exit flow angle
            Wt2 = Ct2 - U; b2 = math.atan2(Wt2, Cx2)         # rotor inlet relative angle
            b3 = math.atan2(-U, Cx3)                         # rotor exit relative angle (C3theta = 0)
            react = 1 - Ct2 / (2 * U)
            M2 = math.hypot(Ct2, Cx2) / math.sqrt(G * R * T2); Mw3 = math.hypot(U, Cx3) / math.sqrt(G * R * T3)
            rows.append(dict(r=r, U=U, a2=math.degrees(a2), b2=math.degrees(b2), b3=math.degrees(b3), R=react, M2=M2, Mw3=Mw3))
        mid = rows[1]
        a2, b2, b3 = math.radians(mid['a2']), math.radians(mid['b2']), math.radians(mid['b3'])
        # blade counts (Zweifel at mean)
        s_n = zweifel_pitch(ZW_TARGET['NGV'], CHORD_AX['NGV'], 0.0, a2)
        s_r = zweifel_pitch(ZW_TARGET['ROTOR'], CHORD_AX['ROTOR'], b2, b3)
        Z_n = max(11, round(2 * math.pi * r_m / s_n)); Z_r = max(17, round(2 * math.pi * r_m / s_r))
        if Z_n % 2 == 0: Z_n += 1
        while any(Z_r % k == 0 and Z_n % k == 0 for k in range(2, 30)) or Z_r % 2 == 0: Z_r += 1
        s_r = 2 * math.pi * r_m / Z_r; s_n = 2 * math.pi * r_m / Z_n
        # chords (true) and Reynolds
        c_n = CHORD_AX['NGV'] / math.cos(0.5 * a2); c_r = CHORD_AX['ROTOR'] / math.cos(0.5 * (b2 + b3))
        C2 = math.hypot(Ct2m, Cx2); W3 = math.hypot(OM * r_m, Cx3)
        Re_n = rho2 * C2 * c_n / mu_gas(T2); Re_r = rho3 * W3 * c_r / mu_gas(T3)
        z_n = soderberg(math.degrees(a2), h_n, CHORD_AX['NGV'], Re_n)
        z_r = soderberg(math.degrees(abs(b2 - b3)), h_r, CHORD_AX['ROTOR'], Re_r)
        # trailing-edge blockage loss (simple: ~ 0.2 * (t/o) ) and tip clearance (Ainley-ish: 1.2 * gap/h of work)
        o_n = s_n * math.cos(a2); o_r = s_r * math.cos(b3)
        Zw_r = 2 * s_r / CHORD_AX['ROTOR'] * math.cos(b3)**2 * abs(math.tan(b2) - math.tan(b3))
        z_r *= (1 + 0.6 * max(Zw_r - 1.0, 0))      # over-loading penalty (same as legacy evaluation)
        z_n += 0.2 * TE_THK['NGV'] / o_n; z_r += 0.2 * TE_THK['ROTOR'] / o_r
        tip = 1.2 * TIP_GAP / h_r
        # total-to-total efficiency (Dixon eq. for stage)
        T2_ = T2; T3_ = T3
        num = z_r * W3**2 / 2 + z_n * C2**2 / 2 * (T3_ / T2_)
        eta_new = (1 / (1 + num / dh)) * (1 - tip)
        if abs(eta_new - eta) < 1e-5: eta = eta_new; break
        eta = eta_new
    A_thr_n = Z_n * o_n * h_n; A_thr_r = Z_r * o_r * h_r
    out.update(Zw_rot=Zw_r, eta_tt=eta, phi=Cx3 / U_m, R_mean=mid['R'], rows=rows, Z_ngv=Z_n, Z_rot=Z_r, c_ngv=c_n, c_rot=c_r,
               pitch_ngv=2 * math.pi * r_m / Z_n, pitch_rot=2 * math.pi * r_m / Z_r, throat_ngv_mm2=A_thr_n * 1e6,
               throat_rot_mm2=A_thr_r * 1e6, Re_ngv=Re_n, Re_rot=Re_r, zeta_ngv=z_n, zeta_rot=z_r, tip_loss=tip,
               Cx2=Cx2, Cx3=Cx3, T2=T2, T3=T3, P2=P2, P3=P3, P03=P03, T03=T03, ma=ma)
    # tested hardware (JetMax TW70 23 blades / NGV 15 vanes, chords 6.7 / ~9.7) evaluated with the same loss model
    def legacy():
        zr = 23; zn = 15
        s_r = 2 * math.pi * r_m / zr; s_n = 2 * math.pi * r_m / zn
        Zr = 2 * s_r / 6.45e-3 * math.cos(b3)**2 * abs(math.tan(b2) - math.tan(b3))
        Zn = 2 * s_n / 9.7e-3 * math.cos(a2)**2 * abs(math.tan(0) - math.tan(a2))
        zn_ = soderberg(math.degrees(a2), h_n, 9.7e-3, Re_n) * (1 + 0.6 * max(Zn - 1.0, 0)) + 0.2 * 0.8e-3 / (s_n * math.cos(a2))
        zr_ = soderberg(math.degrees(abs(b2 - b3)), h_r, 6.45e-3, Re_r) * (1 + 0.6 * max(Zr - 1.0, 0)) + 0.2 * 0.8e-3 / (s_r * math.cos(b3))
        num = zr_ * W3**2 / 2 + zn_ * C2**2 / 2 * (T3 / T2)
        return dict(Z_zweifel_rot=Zr, Z_zweifel_ngv=Zn, eta_tt=(1 / (1 + num / dh)) * (1 - 1.2 * TIP_GAP / h_r))
    out['legacy_TW70'] = legacy()
    if verbose: report(out)
    json.dump(out, open(os.path.join(HERE, 'gg_turbine_design.json'), 'w'), indent=1, default=float)
    return out

def report(o):
    print('GR180 gas-generator turbine @ %.0fk rpm, TIT %.0f C, m_gas %.3f kg/s, P01 %.2f bar' % (o['N_rpm'] / 1e3, o['T01'] - 273.15, o['mg'], o['P01'] / 1e5))
    print('  work %.1f kJ/kg | U_mean %.0f m/s | loading psi %.2f | flow phi %.2f | reaction(mean) %.2f | PR_tt %.2f'
          % (o['dh'] / 1e3, o['U_m'], o['psi'], o['phi'], o['R_mean'], o['P01'] / o['P03']))
    print('  %-5s %6s %8s %8s %8s %7s %6s %6s' % ('', 'U', 'alpha2', 'beta2', 'beta3', 'R', 'M2', 'Mw3'))
    for r in o['rows']:
        print('  %-5s %6.0f %8.1f %8.1f %8.1f %7.2f %6.2f %6.2f' % (('hub', 'mean', 'tip')[o['rows'].index(r)], r['U'], r['a2'], r['b2'], r['b3'], r['R'], r['M2'], r['Mw3']))
    print('  NGV : %d vanes, true chord %.1f mm, pitch %.2f mm, Re %.0f, zeta %.3f, throat %.0f mm2 (tested 1264)'
          % (o['Z_ngv'], o['c_ngv'] * 1e3, o['pitch_ngv'] * 1e3, o['Re_ngv'], o['zeta_ngv'], o['throat_ngv_mm2']))
    print('  ROT : %d blades, true chord %.1f mm, pitch %.2f mm, Re %.0f, zeta %.3f, throat %.0f mm2 (tested 1530), tip loss %.1f %%'
          % (o['Z_rot'], o['c_rot'] * 1e3, o['pitch_rot'] * 1e3, o['Re_rot'], o['zeta_rot'], o['throat_rot_mm2'], o['tip_loss'] * 100))
    print('  stage eta_tt (new design) = %.3f   |   legacy TW70/NGV70 (23/15, Zweifel rot %.2f / ngv %.2f) = %.3f'
          % (o['eta_tt'], o['legacy_TW70']['Z_zweifel_rot'], o['legacy_TW70']['Z_zweifel_ngv'], o['legacy_TW70']['eta_tt']))

if __name__ == '__main__':
    design()
