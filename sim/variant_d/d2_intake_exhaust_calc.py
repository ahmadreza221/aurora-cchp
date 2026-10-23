"""GR180 version D2 - intake plenum, compact exhaust and base frame: 1-D loss / sizing numbers for the CAD
(cad/variant_d/d2_intake.py, d2_exhaust.py, d2_frame.py).

Run (repo root):  python3 sim/variant_d/d2_intake_exhaust_calc.py   ->  sim/variant_d/d2_intake_exhaust_calc.json
Frame: ENG mm (x = engine axis, + downstream, z up).  Basis: sim/variant_d/d_decisions.json (coaxial GT filter
cartridge 445/324 x 660 around the generator pod, DN200 PN6 elbow up + bellows) and the D radial meanline
(cad/variant_d/d_radial_turbine.py: 0.40 kg/s, T04 800 C, P04 2.87 bar, eta_ts 0.80, exducer 74/22 mm).
Method: incompressible loss coefficients on the local dynamic head (Idelchik / Miller style values, Gibson's
conical-diffuser factors with a 1.4 penalty for the turbine-exit profile + hub wake).  Accuracy ~ +/-30 %.
All values are ESTIMATES for layout and part choice; confirm on the test bench (static taps are in the CAD).
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
R_AIR, CP_G, G_G, R_G = 287.0, 1148.0, 1.333, 287.0
P_AMB = 101325.0 * (1 - 2.25577e-5 * 50.0) ** 5.25588          # 50 m site
DEC = json.load(open(os.path.join(HERE, 'd_decisions.json')))
pi = math.pi


def ann(ro, ri=0.0):                       # annulus area m2 from radii in mm
    return pi * ((ro / 1e3) ** 2 - (ri / 1e3) ** 2)


# =========================================================== INTAKE (geometry = cad/variant_d/d2_intake.py)
GEO_IN = dict(r_pod=55.0, r_tube_sheet_opening=162.0, x_tube_sheet_face=-136.0, x_pod_rear=-108.0, x_dish_face=-46.3,
              r_lip=47.5, r_fairing_max=61.0, x_fairing_end=-102.0, fairing_R=15.0, plenum_fillet_R=40.0,
              guard_r=100.0, guard_x=[-118.0, -46.3], strut_d=8.0, n_struts=3, cartridge=dict(OD=445, ID=324, L=660))
m_air = DEC['design_point']['air_kg_s']                          # 0.395


def intake_losses(T_C, m=m_air, cart='pair_cyl_cyl_F9'):
    rho = P_AMB / (R_AIR * (T_C + 273.15))
    Q = m / rho
    q = lambda A: 0.5 * rho * (Q / A) ** 2
    g = GEO_IN
    gap = g['x_dish_face'] - g['x_pod_rear']                    # 61.7 mm radial-gap width
    el = []
    # filter cartridge (research estimate scaled with Q^1, linear media law); none in build 1
    dp_c = {'pair_cyl_cyl_F9': 69.0, 'single_cyl_F9': 138.0, 'none': 0.0}[cart] * (Q * 3600 / DEC['intake_filter']['flow_m3_h'])
    el.append(('filter cartridge (%s, clean)' % cart, None, None, dp_c))
    A_bore = ann(g['r_tube_sheet_opening'], g['r_pod'])
    el.append(('bore annulus 324/110 + terminal box blockage (Cd 1, 50x30 mm)', Q / A_bore, None,
               1.0 * (0.05 * 0.03) / A_bore * q(A_bore) + 0.02 * 0.6 / (2 * (0.162 - 0.055)) * q(A_bore)))
    el.append(('3 yoke legs d12 in the tube-sheet opening (Cd 1.2)', Q / A_bore, None, 1.2 * 3 * 0.012 * 0.107 / A_bore * q(A_bore)))
    A_t1 = 2 * pi * 0.110 * gap / 1e3                             # turn 1 (axial -> radial in) at mean r ~110 mm
    el.append(('turn 1 axial->radial (pod tail fairing R15 / plenum fillet R40), K 0.4', Q / A_t1, 0.4, 0.4 * q(A_t1)))
    A_g = 2 * pi * g['guard_r'] / 1e3 * (g['guard_x'][1] - g['guard_x'][0]) / 1e3 + ann(g['guard_r'], 62.5)
    f = 0.69                                                      # woven 6 mm opening, 1.0 mm wire (Idelchik screen)
    K_s = 1.3 * (1 - f) + (1 / f - 1) ** 2
    el.append(('FOD guard (6 mm mesh, f 0.69, cylinder r100 + front ring), K %.2f' % K_s, Q / A_g, K_s, K_s * q(A_g)))
    A_s = 2 * pi * 0.052 * gap / 1e3
    blk = g['n_struts'] * g['strut_d'] / 1e3 * gap / 1e3 / A_s
    el.append(('3 pod struts d8 across the radial gap (Cd 1.2, blockage %.3f)' % blk, Q / A_s, None, 1.2 * blk * q(A_s)))
    A_l = 2 * pi * g['r_lip'] / 1e3 * gap / 1e3
    el.append(('turn 2 radial->axial round the v13A intake lip, K 0.3', Q / A_l, 0.3, 0.3 * q(A_l)))
    A_th = ann(30.0, 9.0)
    common = 0.02 * q(A_th)
    tot = sum(e[3] for e in el)
    return dict(T_C=T_C, rho=round(rho, 4), Q_m3_s=round(Q, 4), Q_m3_h=round(Q * 3600), elements=[
        dict(name=n, v_m_s=None if v is None else round(v, 2), K=k, dp_Pa=round(d, 1)) for n, v, k, d in el],
        housing_dp_Pa=round(tot - dp_c, 1), total_dp_Pa=round(tot, 1), total_pct_of_p_amb=round(100 * tot / P_AMB, 3),
        eye_contraction_common_with_v13A_Pa=round(common, 0), throat_v_m_s=round(Q / A_th, 1))


IN = dict(geometry=GEO_IN, p_amb_Pa=round(P_AMB),
          site_30C_pair=intake_losses(30.0), site_30C_single=intake_losses(30.0, cart='single_cyl_F9'),
          build1_no_cartridge_30C=intake_losses(30.0, cart='none'), chilled_15C_pair=intake_losses(15.0),
          change_out_dp_Pa=DEC['intake_filter']['change_out_dp_Pa'], budget_Pa=DEC['intake_filter']['inlet_loss_budget_Pa'],
          rule_of_thumb='each 1 kPa of inlet loss ~ -1.2..-1.5 % shaft power (~0.3 kW of 25 kW net) [est]')
IN['dirty_at_change_out_Pa'] = round(IN['site_30C_pair']['housing_dp_Pa'] + IN['change_out_dp_Pa'])
IN['interface'] = dict(name='FI-1 tube sheet', opening_ID_mm=324, gasket_face='flat annulus r 162..226 on the -x face',
                       sheet_OD_mm=500, thickness_mm=6, x_face=GEO_IN['x_tube_sheet_face'], yoke='3 legs M12 on r 150, 120 deg (not 4)',
                       cartridge='Camfil CamPulse GTC 445/324 x 660 class, F9; pair (cyl/cyl, 1320 mm) for 70 Pa',
                       note='the cartridge face seals on the tube sheet; yoke legs pass inside the cartridge bore; closed end cap at the front')

# =========================================================== EXHAUST
N = 115000.0; m_g = 0.40; T04 = 1073.15; P04 = 2.87e5; eta_ts = 0.80
W = 59.5e3 + 25.5e3
dh0 = W / m_g; dh_is = dh0 / eta_ts
PR_ts = (1 - dh_is / (CP_G * T04)) ** (-G_G / (G_G - 1))
T6 = T04 - dh0 / CP_G; P6 = P04 / PR_ts                           # meanline: P6 static = back pressure at the flange
D6T = float(os.environ.get('GR180_D2_EXD_D', '74.0')); D6H = 22.0  # exducer tip / hub (bought wheel: ~64, hub ~20)
X6 = float(os.environ.get('GR180_D2_EXD_X', '199.0'))
D_SH = D6T + 0.8                                                  # shroud bore (0.4 mm tip clearance)
rho6 = P6 / (R_G * T6)
A6 = ann(D6T / 2, D6H / 2)
c6 = m_g / (rho6 * A6)
q6 = 0.5 * rho6 * c6 ** 2
a6 = math.sqrt(G_G * R_G * T6)
DN = {'DN150': 164.3, 'DN200': 215.1, 'DN250': 269.0}             # ID of 168.3/219.1/273 x 2.0 stainless tube
ELBOW_R = {'DN150': 152.4, 'DN200': 203.2, 'DN250': 254.0}         # B16.9 SR (R/D ~ 1)
P0_6 = P6 + q6


def gibson(two_theta):                     # Gibson's factor for conical diffusers (loss = k (1 - A1/A2)^2 q1)
    pts = [(5, .13), (7.5, .14), (10, .16), (15, .27), (20, .43), (25, .62), (30, .81), (40, 1.03), (50, 1.12), (60, 1.13), (90, 1.07), (180, 1.0)]
    for (a0, k0), (a1, k1) in zip(pts, pts[1:]):
        if a0 <= two_theta <= a1:
            return k0 + (k1 - k0) * (two_theta - a0) / (a1 - a0)
    return pts[-1][1]


def exhaust(L_d, two_theta, dn='DN200', expansion='45deg_cone', name=None, K_elbow=0.25):
    """short conical diffuser (L_d, 2theta) from the shroud bore -> expansion cone to the elbow ID -> SR elbow up."""
    D1 = D_SH
    D2 = D1 + 2 * L_d * math.tan(math.radians(two_theta / 2)) if L_d > 0 else D1
    De = DN[dn]
    D2 = min(D2, De)
    A1, A2, Ae = ann(D1 / 2), ann(D2 / 2), ann(De / 2)
    rho = rho6
    el = []
    el.append(('hub dump at the exducer exit (annulus -> full bore)', q6 * (1 - A6 / A1) ** 2))
    q1 = q6 * (A6 / A1) ** 2
    if L_d > 0:
        el.append(('conical diffuser 2theta %.0f deg, L %.0f, D %.1f -> %.1f (Gibson x1.4)' % (two_theta, L_d, D1, D2),
                   1.4 * gibson(two_theta) * (1 - A1 / A2) ** 2 * q1))
    q2 = q1 * (A1 / A2) ** 2
    k_exp = 1.0 if expansion == '45deg_cone' else 1.4 * gibson(expansion)
    el.append(('expansion D %.0f -> %s ID %.1f (%s)' % (D2, dn, De, expansion), k_exp * (1 - A2 / Ae) ** 2 * q2))
    qe = q2 * (A2 / Ae) ** 2
    el.append(('%s 90 deg SR elbow up R %.0f, K %.2f (distorted inflow)' % (dn, ELBOW_R[dn], K_elbow), K_elbow * qe))
    loss = sum(e[1] for e in el)
    # flange static held at the meanline P6 (same back pressure): exducer static drops by the recovery
    dp6 = qe + loss - q6                                           # p6 - p_flange  (negative = recovery)
    dW = -m_g * eta_ts * dp6 / rho6 / 1e3                          # small-signal extra turbine work, kW
    length = (L_d + (De - D2) / 2 / math.tan(math.radians(45)) + 40 + ELBOW_R[dn] + De / 2 + 2)
    return dict(name=name or 'L%.0f_%.0fdeg_%s' % (L_d, two_theta, dn), L_diffuser=L_d, two_theta=two_theta, D_in=round(D1, 1),
                D_diff_exit=round(D2, 1), DN=dn, elbow_R=ELBOW_R[dn],
                elements=[dict(name=n, dp_Pa=round(d)) for n, d in el], dp0_total_Pa=round(loss),
                dp0_pct_of_P0=round(100 * loss / P0_6, 2), duct_elbow_plus_exit_q_Pa=round(K_elbow * qe + qe),
                duct_pct_of_P0=round(100 * (K_elbow * qe + qe) / P0_6, 3), v_elbow_m_s=round(math.sqrt(2 * qe / rho), 1),
                p6_minus_p_flange_Pa=round(dp6), turbine_work_gain_vs_dump_kW=round(dW, 2),
                x_extent_from_exducer_mm=round(length))


sweep = [exhaust(L, t) for L in (0, 60, 80, 100, 120, 150, 200) for t in (12, 14, 16, 18, 20)]
best = min(s['p6_minus_p_flange_Pa'] for s in sweep)
# compact choice: shortest diffuser within 0.8 kPa of the best recovery in the sweep (~0.6 kW)
ok = [s for s in sweep if s['p6_minus_p_flange_Pa'] <= best + 800]
choice = min(ok, key=lambda s: (s['L_diffuser'], -s['two_theta']))
baseline_long_cone = exhaust(144, 25.0, 'DN150', name='D2 RT-180 long cone (2theta ~25 deg, 74.8 -> 139) + DN150 flange')
baseline_long_cone['note'] = 'RT-180 ends in a flange with no elbow; elbow loss counted for comparison'
dn150 = exhaust(choice['L_diffuser'], choice['two_theta'], 'DN150', name='same diffuser, DN150 elbow')
EX = dict(meanline=dict(T6_C=round(T6 - 273.15, 1), P6_bar=round(P6 / 1e5, 4), rho6=round(rho6, 4), c6_m_s=round(c6, 1),
                        M6=round(c6 / a6, 3), q6_Pa=round(q6), P0_6_bar=round(P0_6 / 1e5, 4), exducer_D=[D6T, D6H], x_exducer_exit=X6,
                        Q_flange_m3_s=round(m_g / rho6, 3)),
          choice=choice, alt_DN150=dn150, baseline_D2_long_cone=baseline_long_cone,
          no_diffuser=exhaust(0, 0, 'DN200', name='no diffuser: exducer dumps into the DN200 elbow'),
          sweep=[{k: s[k] for k in ('name', 'D_diff_exit', 'dp0_total_Pa', 'p6_minus_p_flange_Pa', 'turbine_work_gain_vs_dump_kW',
                                     'x_extent_from_exducer_mm')} for s in sweep],
          flange=dict(std='EN 1092-1 type 01 PN6 DN200', D=320, K=280, bolts='8 x M16', hole=18, b=20, face='+z'),
          criterion='duct (elbow + exit dynamic head) <= 1 %% of P0: %.2f %% for DN200 (%.2f %% for DN150)' % (
              choice['duct_pct_of_P0'], dn150['duct_pct_of_P0']),
          note='q6 at the exducer is ~10 % of P0; the meanline (eta_ts 0.80, p6 = back pressure) throws it away. The '
               'short diffuser + dump into the DN200 elbow recovers most of it (p6 below the flange static), which is a '
               'GAIN vs the meanline; the dp0 numbers are internal losses of that recovery, not extra back pressure.')
for D_alt in (64.0,):                                              # bought wheel: exducer ~64 mm (d_decisions)
    A6a = ann(D_alt / 2, 10.0); c6a = m_g / (rho6 * A6a)
    EX['bought_wheel_exducer_%d' % D_alt] = dict(c6_m_s=round(c6a, 1), q6_Pa=round(0.5 * rho6 * c6a ** 2),
                                                 note='higher exit q -> the diffuser matters even more; rerun with GR180_D2_EXD_D=64')

# =========================================================== FRAME: thermal growth + mounts (est)
ALPHA = 17.5e-6
growth = dict(front_fixed_x=-130, core_casing_x=[-8, 116], core_casing_T_C=350, plenum_T_C=750, exhaust_T_C=600)
dx_collar = (124 * (350 - 30) + 20 * (750 - 30)) * ALPHA
x_lug = -130 + 0                                                    # filled in by the frame script (reported there)
dx_exh = dx_collar + (choice['L_diffuser'] + 100) * (600 - 30) * ALPHA
FR = dict(axial_growth_at_rear_collar_mm=round(dx_collar, 2), axial_growth_at_exhaust_lugs_mm=round(dx_exh, 2),
          radial_growth_plenum_mm=round(84 * (750 - 30) * ALPHA, 2), slot_length_each_side_mm=6.0,
          mass_est_kg=dict(engine_core=11.0, generator_pod=9.0, intake=6.5, exhaust=7.0, frame=16.0, cartridge_pair=24.0),
          mounts='4 x elastomer mounts, static deflection ~2.5 mm -> f_n ~ 10 Hz (est); run 1917 Hz: isolation > 99.9 %')
tot_m = sum(FR['mass_est_kg'].values())
FR['load_per_mount_N'] = round(tot_m * 9.81 / 4)
FR['f_n_Hz_est'] = round(15.76 / math.sqrt(2.5), 1)

OUT = dict(title='GR180 D2 intake / exhaust / frame 1-D numbers', date='2026-10-23', frame='ENG mm',
           intake=IN, exhaust=EX, frame_supports=FR)
json.dump(OUT, open(os.path.join(HERE, 'd2_intake_exhaust_calc.json'), 'w'), indent=1)

if __name__ == '__main__':
    for k in ('site_30C_pair', 'build1_no_cartridge_30C'):
        r = IN[k]
        print('INTAKE %s: Q %.3f m3/s  housing %.0f Pa  total %.0f Pa (%.2f %%)' % (k, r['Q_m3_s'], r['housing_dp_Pa'], r['total_dp_Pa'], r['total_pct_of_p_amb']))
        for e in r['elements']:
            print('   %-80s %6.1f Pa' % (e['name'], e['dp_Pa']))
    print('EXHAUST meanline q6 %.0f Pa (M %.2f), P0_6 %.3f bar' % (q6, c6 / a6, P0_6 / 1e5))
    for s in (choice, dn150, baseline_long_cone, EX['no_diffuser']):
        print('  %-70s dp0 %5d Pa (%.2f %%) duct %.2f %%  p6-pfl %6d Pa  dW %+.2f kW  x-ext %d' % (
            s['name'], s['dp0_total_Pa'], s['dp0_pct_of_P0'], s['duct_pct_of_P0'], s['p6_minus_p_flange_Pa'],
            s['turbine_work_gain_vs_dump_kW'], s['x_extent_from_exducer_mm']))
    print('FRAME growth collar %.2f mm, exhaust lugs %.2f mm, load/mount %d N' % (dx_collar, dx_exh, FR['load_per_mount_N']))
