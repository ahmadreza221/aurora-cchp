"""GR180 version D2 - compact intake plenum, compact coaxial exhaust and base frame: 1-D loss / sizing numbers for the
CAD (cad/variant_d/d2_intake.py, d2_exhaust.py, d2_frame.py).  Revision 2 (2026-10-23, user feedback):
  * intake = closed plenum OD 180 round the radial inlet gap with ONE side port (+y) DN150 for the user's own filter
    (the coaxial GT cartridge / tube sheet of rev 1 is dropped);
  * exhaust = short conical diffuser behind the exducer + straight coaxial DN125 / DN150 stub (no elbow), bolted to the
    D2R turbine shroud flange (OD 104, 6 x M6 PCD 94, x 176, bore 70.7; commit 20686b0).

Run (repo root):  python3 sim/variant_d/d2_intake_exhaust_calc.py   ->  sim/variant_d/d2_intake_exhaust_calc.json
Frame: ENG mm (x = engine axis, + downstream, z up).
Basis: air 0.395 kg/s (sim/variant_d/d_decisions.json), site 30 C / 50 m; turbine exit from the D2R meanline
(sim/variant_d/d2r_turbine.json @ 20686b0: 0.40 kg/s, c6 296.6 m/s, T6 576 C, P6 1.000 bar, A6 3286 mm2, eta_ts 0.755).
Method: incompressible loss coefficients on the local dynamic head (Idelchik / Miller style values; Gibson's conical
diffuser factors x1.4 for the turbine-exit profile + hub wake; a side-entry plenum model for the single port).
Accuracy ~ +/-30 % (side-entry plenum ~ +/-50 %).  All values are ESTIMATES; confirm on the bench (taps are in the CAD).
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
R_AIR = 287.0
P_AMB = 101325.0 * (1 - 2.25577e-5 * 50.0) ** 5.25588          # 50 m site
pi = math.pi


def ann(ro, ri=0.0):                       # annulus area m2 from radii in mm
    return pi * ((ro / 1e3) ** 2 - (ri / 1e3) ** 2)


# =========================================================== INTAKE (geometry = cad/variant_d/d2_intake.py)
GEO_IN = dict(housing_OD=180.0, r_wet=88.0, x_front_wall=-130.0, x_rear_ring=[-8.4, -2.4], r_pod=55.0, x_pod_rear=-108.0,
              x_dish_face=-46.3, r_lip=47.5, dish_rim_r=68.0, skirt_r=62.0, x_skirt=[-44.3, -8.4],
              port=dict(dir='+y', DN=150, tube='168.3 x 2', ID=164.3, flange='PN6 DN150 drilling (D265 K225 8 x M16), 8 mm',
                        window='stadium 112 (x) x 170 (z) on the can, centre x -71', window_mm2=112 * (170 - 112) + pi * 56 ** 2,
                        y_flange_face=240.0, length_from_can_OD=150.0),
              guard=dict(where='disc in the DN150 spigot at y 200', mesh='8 mm opening / 1.0 mm wire 1.4301', f=(8 / 9.0) ** 2),
              strut_d=8.0, n_struts=3)
m_air = 0.395


def plenum_section_mm2(r_wet):
    """meridional area of one half of the plenum available for the circumferential (round-the-pod) flow."""
    g = GEO_IN
    return ((r_wet - g['r_pod']) * (g['x_pod_rear'] - g['x_front_wall'] - 2) +
            (r_wet - g['r_lip']) * (g['x_dish_face'] - g['x_pod_rear']) +
            (r_wet - g['skirt_r']) * (-14.4 - g['x_skirt'][0]))


def intake_losses(T_C, r_wet=None, m=m_air):
    g = GEO_IN; r_wet = r_wet or g['r_wet']
    rho = P_AMB / (R_AIR * (T_C + 273.15))
    Q = m / rho
    qv = lambda V: 0.5 * rho * V * V
    gap = g['x_dish_face'] - g['x_pod_rear']
    el = []
    V_sp = Q / ann(g['port']['ID'] / 2)
    f = g['guard']['f']; K_s = 1.3 * (1 - f) + (1 / f - 1) ** 2
    el.append(('FOD guard disc in the DN150 spigot (8/1.0 mesh, f %.2f), K %.2f' % (f, K_s), V_sp, K_s * qv(V_sp)))
    V_w = Q / (g['port']['window_mm2'] / 1e6)
    el.append(('spigot round -> stadium window (contraction), K 0.05', V_w, 0.05 * qv(V_w)))
    el.append(('window dump into the plenum, K 1.0', V_w, 1.0 * qv(V_w)))
    A_c = plenum_section_mm2(r_wet) / 1e6
    V_c = 0.5 * Q / A_c                                            # half the flow goes round each side, max at the window
    el.append(('round-the-pod distribution (50 %% of the flow, V_c,max %.0f m/s, K 0.6, linear feed -> 1/3)' % V_c, V_c,
               0.5 * 0.6 * qv(V_c) / 3.0))
    A_t = 2 * pi * 0.075 * gap / 1e3
    el.append(('turn into the radial gap (pod tail fairing R15 / dish rim lip), K 0.4', Q / A_t, 0.4 * qv(Q / A_t)))
    A_s = 2 * pi * 0.052 * gap / 1e3
    blk = g['n_struts'] * g['strut_d'] / 1e3 * gap / 1e3 / A_s
    el.append(('3 pod struts d8 across the radial gap (Cd 1.2)', Q / A_s, 1.2 * blk * qv(Q / A_s)))
    A_l = 2 * pi * g['r_lip'] / 1e3 * gap / 1e3
    el.append(('turn radial -> axial round the v13A intake lip, K 0.3', Q / A_l, 0.3 * qv(Q / A_l)))
    tot = sum(e[2] for e in el)
    return dict(T_C=T_C, rho=round(rho, 4), Q_m3_s=round(Q, 4), Q_m3_h=round(Q * 3600), housing_OD=2 * r_wet + 4,
                elements=[dict(name=n, v_m_s=round(v, 1), dp_Pa=round(d, 1)) for n, v, d in el],
                total_dp_Pa=round(tot), total_pct_of_p_amb=round(100 * tot / P_AMB, 3),
                power_cost_kW_est=round(tot / 1000 * 1.35 / 100 * 25.5, 2),
                eye_contraction_common_with_v13A_Pa=round(0.02 * qv(Q / ann(30.0, 9.0))))


IN = dict(geometry=GEO_IN, p_amb_Pa=round(P_AMB), site_30C=intake_losses(30.0), chilled_15C=intake_losses(15.0),
          option_OD220_30C=intake_losses(30.0, r_wet=108.0),
          rev1_axisymmetric_coaxial_cartridge_housing_Pa=101,
          notes=['user filter dp is NOT included (his filter); budget for the whole inlet ~1000 Pa',
                 'single side port -> circumferential distortion at the eye (not in the 1-D number); check with a 4-probe rake',
                 'largest item = window dump: the window is limited to 112 mm by the housing length (front wall x -130 '
                 'behind the pod glycol port x -152 / terminal box, rear ring at the core front); a longer housing would '
                 'let the port open as a full DN150 circle',
                 'power cost: ~1.35 % shaft power per 1 % inlet loss (est), on 25.5 kW generator shaft'])

# =========================================================== EXHAUST (coaxial, D2R turbine)
TURB = dict(m=0.40, c6=296.574, T6_C=576.25, P6=1.00043e5, rho6=0.41039, A6_mm2=3286.49, eta_ts=0.755,
            x_flange=176.0, bore=70.7, flange_OD=104.0, bolts='6 x M6 on PCD 94 (start 30 deg)', source='d2r_turbine.json @ 20686b0')
for k, env in (('x_flange', 'GR180_D2_EXD_X'), ('bore', 'GR180_D2_EXD_D')):
    if os.environ.get(env):
        TURB[k] = float(os.environ[env])
m_g, rho6 = TURB['m'], TURB['rho6']
q6 = 0.5 * rho6 * TURB['c6'] ** 2
A6 = TURB['A6_mm2'] / 1e6
P0_6 = TURB['P6'] + q6
DN = {'DN125': dict(tube='139.7 x 2', ID=135.7, OD=139.7, fl=dict(D=240, K=200, n=8, hole=18, bolt='M16', b=12)),
      'DN150': dict(tube='168.3 x 2', ID=164.3, OD=168.3, fl=dict(D=265, K=225, n=8, hole=18, bolt='M16', b=12))}


def gibson(two_theta):                     # Gibson's factor for conical diffusers (loss = k (1 - A1/A2)^2 q1)
    pts = [(5, .13), (7.5, .14), (10, .16), (15, .27), (20, .43), (25, .62), (30, .81), (40, 1.03), (50, 1.12), (60, 1.13), (90, 1.07), (180, 1.0)]
    for (a0, k0), (a1, k1) in zip(pts, pts[1:]):
        if a0 <= two_theta <= a1:
            return k0 + (k1 - k0) * (two_theta - a0) / (a1 - a0)
    return pts[-1][1]


def kW(dp):                                 # small-signal turbine work for a change of exducer static pressure
    return m_g * TURB['eta_ts'] * dp / rho6 / 1e3


def exhaust(L_d, two_theta, dn):
    D1 = TURB['bore']; De = DN[dn]['ID']
    D2 = min(D1 + 2 * L_d * math.tan(math.radians(two_theta / 2)), De) if L_d > 0 else D1
    A1, A2, Ae = ann(D1 / 2), ann(D2 / 2), ann(De / 2)
    el = [('hub dump at the exducer exit (annulus -> full bore)', q6 * (1 - A6 / A1) ** 2)]
    q1 = q6 * (A6 / A1) ** 2
    if L_d > 0:
        el.append(('conical diffuser 2theta %.0f, L %.0f, D %.1f -> %.1f (Gibson x1.4)' % (two_theta, L_d, D1, D2),
                   1.4 * gibson(two_theta) * (1 - A1 / A2) ** 2 * q1))
    q2 = q1 * (A1 / A2) ** 2
    el.append(('45 deg step D %.1f -> %s ID %.1f (dump)' % (D2, dn, De), (1 - A2 / Ae) ** 2 * q2))
    qe = q2 * (A2 / Ae) ** 2
    el.append(('straight stub L40 friction (f 0.02)', 0.02 * 40 / De * qe))
    loss = sum(e[1] for e in el)
    tot_with_exit = loss + qe                                      # flange velocity assumed lost downstream
    return dict(name='L%.0f_%.0fdeg_%s' % (L_d, two_theta, dn), L_diffuser=L_d, two_theta=two_theta, DN=dn, D_in=D1,
                D_diff_exit=round(D2, 1), D_stub=De, elements=[dict(name=n, dp_Pa=round(d)) for n, d in el],
                dp0_internal_Pa=round(loss), q_flange_Pa=round(qe), v_flange_m_s=round(math.sqrt(2 * qe / rho6), 1),
                dp0_incl_exit_Pa=round(tot_with_exit), pct_of_P0=round(100 * tot_with_exit / P0_6, 2),
                Cp_system=round((q6 - tot_with_exit) / q6, 3),
                cost_vs_ideal_kW=round(kW(tot_with_exit), 2), gain_vs_no_diffuser_dump_kW=round(kW(q6 - tot_with_exit), 2))


L_MAX = 80.0
sweep = [exhaust(L, t, dn) for dn in DN for L in (0, 40, 60, 70, 80) for t in (10, 12, 14, 16, 18, 20, 22, 25)]
best = {dn: min([s for s in sweep if s['DN'] == dn and s['L_diffuser'] <= L_MAX], key=lambda s: s['dp0_incl_exit_Pa']) for dn in DN}
delta = best['DN125']['cost_vs_ideal_kW'] - best['DN150']['cost_vs_ideal_kW']
pick = 'DN125' if delta <= 1.5 else 'DN150'
EX = dict(turbine=TURB, q6_Pa=round(q6), P0_6_bar=round(P0_6 / 1e5, 4), Q_m3_s=round(m_g / rho6, 3),
          best_DN125=best['DN125'], best_DN150=best['DN150'], DN125_minus_DN150_kW=round(delta, 2),
          rule='DN150 only if DN125 costs > 1.5 kW more', choice=best[pick], DN_choice=pick, flange=DN[pick],
          no_diffuser={dn: exhaust(0, 0, dn) for dn in DN},
          longer_diffuser_ref={dn: min([s for s in sweep if s['DN'] == dn], key=lambda s: s['dp0_incl_exit_Pa']) for dn in DN},
          sweep=[{k: s[k] for k in ('name', 'D_diff_exit', 'dp0_incl_exit_Pa', 'cost_vs_ideal_kW', 'gain_vs_no_diffuser_dump_kW')}
                 for s in sweep],
          note='cost_vs_ideal = turbine work lost vs a perfect exhaust (all q6 recovered); the flange dynamic head is '
               'counted as lost (free discharge / silencer). With a dump the optimum stub area is ~2 x the diffuser exit '
               'area, which is why DN125 beats DN150 here.')

# =========================================================== FRAME: thermal growth + mounts (est)
ALPHA = 17.5e-6
dx_turb = (124 * (350 - 30) + 20 * (700 - 30)) * ALPHA             # front fixed point x -5 -> turbine pads x 135
dx_exh = dx_turb + (best[pick]['L_diffuser'] + 140) * (576 - 30) * ALPHA
FR = dict(fixed_point='intake rear ring foot at x -5 (core front)', axial_growth_at_turbine_pads_mm=round(dx_turb, 2),
          axial_growth_at_exhaust_lugs_mm=round(dx_exh, 2), slot_free_each_side_mm=dict(turbine_pedestal=3.0, exhaust_lug=8.0),
          mass_est_kg=dict(engine_core=11.0, generator_pod=9.0, turbine_stage=3.5, intake=6.1, exhaust=4.2, frame=11.6))
FR['load_per_mount_N'] = round(sum(FR['mass_est_kg'].values()) * 9.81 / 4)
FR['f_n_Hz_est'] = round(15.76 / math.sqrt(2.0), 1)

OUT = dict(title='GR180 D2 intake / exhaust / frame 1-D numbers (rev 2: compact side-port plenum, coaxial exhaust)',
           date='2026-10-23', frame='ENG mm', intake=IN, exhaust=EX, frame_supports=FR)
json.dump(OUT, open(os.path.join(HERE, 'd2_intake_exhaust_calc.json'), 'w'), indent=1)

if __name__ == '__main__':
    r = IN['site_30C']
    print('INTAKE OD180 side port DN150: Q %.3f m3/s  dp %d Pa (%.2f %%, ~%.2f kW)' % (r['Q_m3_s'], r['total_dp_Pa'], r['total_pct_of_p_amb'], r['power_cost_kW_est']))
    for e in r['elements']:
        print('   %-90s %5.1f m/s %6.1f Pa' % (e['name'], e['v_m_s'], e['dp_Pa']))
    print('   OD220 option: %d Pa' % IN['option_OD220_30C']['total_dp_Pa'])
    print('EXHAUST q6 %.0f Pa, P0_6 %.3f bar' % (q6, P0_6 / 1e5))
    for s in (best['DN125'], best['DN150'], EX['no_diffuser']['DN125'], EX['longer_diffuser_ref']['DN125']):
        print('  %-22s Dd %5.1f  internal %5d  q_fl %4d (v %4.1f)  total %5d Pa (%.2f %%)  Cp %.2f  cost %.2f kW  gain %.2f kW' % (
            s['name'], s['D_diff_exit'], s['dp0_internal_Pa'], s['q_flange_Pa'], s['v_flange_m_s'], s['dp0_incl_exit_Pa'],
            s['pct_of_P0'], s['Cp_system'], s['cost_vs_ideal_kW'], s['gain_vs_no_diffuser_dump_kW']))
    print('  DN125 - DN150 = %+.2f kW -> %s' % (delta, pick))
    print('FRAME growth turbine pads %.2f mm, exhaust lugs %.2f mm, load/mount %d N' % (dx_turb, dx_exh, FR['load_per_mount_N']))
