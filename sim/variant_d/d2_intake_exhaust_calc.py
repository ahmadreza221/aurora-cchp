"""GR180 version D2 - compact intake plenum + top V-cell filter box, short coaxial exhaust diffuser, base frame with
a generator-pod support: 1-D loss / sizing numbers for the CAD (cad/variant_d/d2_intake.py, d2_exhaust.py, d2_frame.py).
Revision 3 (2026-10-23, user feedback):
  * intake = closed plenum OD 180 round the radial inlet gap; the filter is an F7 V-cell 592 x 592 x 292 in a minimal
    sheet-metal box ON TOP of the plenum (clean chamber + 45 deg tapered collar into a top opening 112 x 170);
  * exhaust = short conical diffuser bolted to the D2R turbine shroud flange (x 176, bore 70.7, 6 x M6 PCD 94), ending
    at the diffuser exit with a slim ring flange (no stub / no DN125 flange);
  * frame = generator-pod weight-relief cradle (struts stay the locator) + 4 posts for the filter box.

Run (repo root):  python3 sim/variant_d/d2_intake_exhaust_calc.py   ->  sim/variant_d/d2_intake_exhaust_calc.json
Frame: ENG mm (x = engine axis, + downstream, z up).
Basis: air 0.395 kg/s (sim/variant_d/d_decisions.json), site 30 C / 50 m; turbine exit from the D2R meanline
(sim/variant_d/d2r_turbine.json @ 20686b0: 0.40 kg/s, c6 296.6 m/s, T6 576 C, P6 1.000 bar, A6 3286 mm2, eta_ts 0.755).
Method: incompressible loss coefficients on the local dynamic head (Idelchik / Miller style values; Gibson's conical
diffuser factors x1.4 for the turbine-exit profile + hub wake; a single-entry plenum model).  Filter: linear media law
from the maker's rating (F7 V-cell ~90 Pa at 3400 m3/h, change-out 450 Pa at rated flow).
Accuracy ~ +/-30 % (single-entry plenum ~ +/-50 %).  All values are ESTIMATES; confirm on the bench (taps are in the CAD).
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
              top_opening=dict(dir='+z', centre_x=-71.0, size_mm=[112, 170], area_mm2=112 * 170 - (4 - pi) * 8 ** 2,
                               collar='straight to z 90 + 45 deg frustum to 188 x 246 at z 128, flange z 128..130'),
              filter=dict(type='F7 (ISO ePM1 50-65 %) V-cell with header, 4 V-banks', size=[592, 592, 292], header_mm=25,
                          rated_m3_h=3400, dp_rated_initial_Pa=90, dp_rated_final_Pa=450, orientation='face up (+z), header up'),
              box=dict(inner=[600, 600], centre_x=-190.0, floor_z=130.0, clean_chamber_mm=70, lid_top_z=527.0),
              guard=dict(where='panel on the box floor over the 188 x 246 opening', mesh='8 mm opening / 1.0 mm wire 1.4301', f=(8 / 9.0) ** 2),
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
    fl = g['filter']; bx = g['box']
    V_face = Q / (0.592 * 0.592)
    el.append(('inlet grille, expanded metal (f 0.7, K 0.6)', V_face, 0.6 * qv(V_face)))
    dp_f0 = fl['dp_rated_initial_Pa'] * Q * 3600 / fl['rated_m3_h']
    dp_f1 = fl['dp_rated_final_Pa'] * Q * 3600 / fl['rated_m3_h']
    el.append(('F7 V-cell, CLEAN (%.0f Pa at %d m3/h, linear)' % (fl['dp_rated_initial_Pa'], fl['rated_m3_h']), V_face, dp_f0))
    A_cc = 2 * (0.188 + 0.246) * bx['clean_chamber_mm'] / 1e3
    el.append(('clean chamber -> collar mouth (K 0.5)', Q / A_cc, 0.5 * qv(Q / A_cc)))
    f = g['guard']['f']; K_s = 1.3 * (1 - f) + (1 / f - 1) ** 2
    V_g = Q / (0.188 * 0.246)
    el.append(('FOD guard panel on the box floor (8/1.0 mesh, f %.2f), K %.2f' % (f, K_s), V_g, K_s * qv(V_g)))
    V_w = Q / (g['top_opening']['area_mm2'] / 1e6)
    el.append(('45 deg tapered collar 188 x 246 -> 112 x 170 (contraction), K 0.1', V_w, 0.1 * qv(V_w)))
    el.append(('collar dump into the plenum, K 1.0', V_w, 1.0 * qv(V_w)))
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
    housing = tot - dp_f0
    return dict(T_C=T_C, rho=round(rho, 4), Q_m3_s=round(Q, 4), Q_m3_h=round(Q * 3600), filter_face_v_m_s=round(V_face, 2),
                elements=[dict(name=n, v_m_s=round(v, 1), dp_Pa=round(d, 1)) for n, v, d in el],
                housing_dp_Pa=round(housing), filter_clean_Pa=round(dp_f0), filter_change_out_Pa=round(dp_f1),
                total_clean_Pa=round(tot), total_dirty_Pa=round(housing + dp_f1),
                total_clean_pct=round(100 * tot / P_AMB, 3), total_dirty_pct=round(100 * (housing + dp_f1) / P_AMB, 3),
                power_cost_clean_kW_est=round(tot / P_AMB * 1.35 * 25.5, 2),
                power_cost_dirty_kW_est=round((housing + dp_f1) / P_AMB * 1.35 * 25.5, 2),
                eye_contraction_common_with_v13A_Pa=round(0.02 * qv(Q / ann(30.0, 9.0))))


IN = dict(geometry=GEO_IN, p_amb_Pa=round(P_AMB), site_30C=intake_losses(30.0), chilled_15C=intake_losses(15.0),
          rev2_side_DN150_port_housing_Pa=531, rev1_axisymmetric_housing_Pa=101,
          orientation=dict(choice='TOP (+z), cell face up, header up',
                           why=['no extra floor area: the 592 x 592 box sits over the pod / plenum inside the package width',
                                'a side (+y) box cannot hang below the axis (592 mm square vs 239 mm axis height) - it would '
                                'stand on the floor and add ~0.6 x 0.45 m of footprint',
                                'gravity seats the header on the gasket (dirty-side pressure also pushes it down)',
                                'change = open 4 toggle latches, lift the lid, lift the cell straight out (no tools)',
                                'box kept forward over the cool generator pod (rear wall x 111.5, turbine housing from x 118)']),
          notes=['single top opening -> circumferential distortion at the eye (not in the 1-D number); check with a 4-probe rake',
                 'largest item = collar dump into the plenum (opening limited to 112 mm by the plenum length)',
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
    """dn = 'DN125' / 'DN150': 45 deg step into a straight stub (rev 2); dn = 'none': the exhaust ends at the diffuser exit
    with a slim ring flange (rev 3) and the diffuser-exit dynamic head is dumped."""
    D1 = TURB['bore']; De = DN[dn]['ID'] if dn in DN else 1e9
    D2 = min(D1 + 2 * L_d * math.tan(math.radians(two_theta / 2)), De) if L_d > 0 else D1
    A1, A2, Ae = ann(D1 / 2), ann(D2 / 2), ann(De / 2)
    el = [('hub dump at the exducer exit (annulus -> full bore)', q6 * (1 - A6 / A1) ** 2)]
    q1 = q6 * (A6 / A1) ** 2
    if L_d > 0:
        el.append(('conical diffuser 2theta %.0f, L %.0f, D %.1f -> %.1f (Gibson x1.4)' % (two_theta, L_d, D1, D2),
                   1.4 * gibson(two_theta) * (1 - A1 / A2) ** 2 * q1))
    q2 = q1 * (A1 / A2) ** 2
    if dn in DN:
        el.append(('45 deg step D %.1f -> %s ID %.1f (dump)' % (D2, dn, De), (1 - A2 / Ae) ** 2 * q2))
        qe = q2 * (A2 / Ae) ** 2
        el.append(('straight stub L40 friction (f 0.02)', 0.02 * 40 / De * qe))
    else:
        qe = q2
    loss = sum(e[1] for e in el)
    tot_with_exit = loss + qe                                      # flange velocity assumed lost downstream
    return dict(name='L%.0f_%.0fdeg_%s' % (L_d, two_theta, dn), L_diffuser=L_d, two_theta=two_theta, DN=dn, D_in=D1,
                D_diff_exit=round(D2, 1), D_stub=De if dn in DN else None, elements=[dict(name=n, dp_Pa=round(d)) for n, d in el],
                dp0_internal_Pa=round(loss), q_flange_Pa=round(qe), v_flange_m_s=round(math.sqrt(2 * qe / rho6), 1),
                dp0_incl_exit_Pa=round(tot_with_exit), pct_of_P0=round(100 * tot_with_exit / P0_6, 2),
                Cp_system=round((q6 - tot_with_exit) / q6, 3),
                cost_vs_ideal_kW=round(kW(tot_with_exit), 2), gain_vs_no_diffuser_dump_kW=round(kW(q6 - tot_with_exit), 2))


L_MAX = 80.0
ANG = (10, 12, 14, 16, 18, 20, 22, 25, 30)
sweep = [exhaust(L, t, dn) for dn in list(DN) + ['none'] for L in (0, 40, 60, 70, 80) for t in ANG]
best = {dn: min([s for s in sweep if s['DN'] == dn and s['L_diffuser'] <= L_MAX], key=lambda s: s['dp0_incl_exit_Pa'])
        for dn in list(DN) + ['none']}
choice = best['none']
EX = dict(turbine=TURB, q6_Pa=round(q6), P0_6_bar=round(P0_6 / 1e5, 4), Q_m3_s=round(m_g / rho6, 3),
          choice=choice, end='diffuser exit, slim ring flange OD 128 (6 x M6 on PCD 116) - no stub, no PN flange',
          end_ring=dict(OD=128.0, t=6.0, bolts='6 x M6 on PCD 116 (30 deg start)', note='for a future pipe; or weld a V-band lip'),
          rev2_DN125_stub=best['DN125'], rev2_DN150_stub=best['DN150'],
          cost_of_dropping_the_stub_kW=round(choice['cost_vs_ideal_kW'] - best['DN125']['cost_vs_ideal_kW'], 2),
          by_length={'L%d' % L: min([s for s in sweep if s['DN'] == 'none' and s['L_diffuser'] == L], key=lambda s: s['dp0_incl_exit_Pa'])['cost_vs_ideal_kW']
                     for L in (0, 40, 60, 70, 80)},
          sweep=[{k: s[k] for k in ('name', 'D_diff_exit', 'dp0_incl_exit_Pa', 'cost_vs_ideal_kW', 'gain_vs_no_diffuser_dump_kW')}
                 for s in sweep],
          note='cost_vs_ideal = turbine work lost vs a perfect exhaust (all q6 recovered); the exit dynamic head is counted as '
               'lost (free discharge into the enclosure / a large duct). The rev-2 DN125 stub was NOT neutral: its sudden '
               'expansion (area ratio ~2) recovered about half of the diffuser-exit q (Borda), which is the kW difference '
               'listed. If a pipe of ~2x the diffuser exit area (DN125) is bolted on later, that recovery comes back.')

# =========================================================== FRAME: thermal growth, mounts, pod support (est)
ALPHA = 17.5e-6
dx_turb = (124 * (350 - 30) + 20 * (700 - 30)) * ALPHA             # front fixed point x -5 -> turbine pads x 135
dx_exh = dx_turb + 70 * (576 - 30) * ALPHA                          # -> exhaust lugs on the diffuser (x ~204)
GEN_JSON = os.path.join(HERE, '..', '..', 'cad_out', 'variant_d', 'D2', 'GENERATOR', 'd2r_generator_parts.json')
pod_parts = {}
if os.path.exists(GEN_JSON):
    pod_parts = {k: (v['mass_kg'], 0.5 * (v['x'][0] + v['x'][1])) for k, v in json.load(open(GEN_JSON))['parts'].items()
                 if 'Quill_Guard' not in k}
else:                                                               # fallback: main items of the D2R generator (306a7f4)
    pod_parts = {'stator+winding': (2.36, -201.0), 'rotor': (0.67, -195.0), 'end shields': (0.36, -205.0), 'other': (0.5, -200.0)}
pod_parts['D-101 pod shell (Al, 376 cm3)'] = (1.02, -190.5)
pod_parts['D-102 front cap (Al)'] = (0.03, -285.0)
m_pod = sum(m for m, x in pod_parts.values())
x_cg = sum(m * x for m, x in pod_parts.values()) / m_pod
POD = dict(mass_kg=round(m_pod, 2), x_cg=round(x_cg, 1), weight_N=round(m_pod * 9.81, 1),
           concept='weight-relief cradle: the 3 intake struts (INT-115) stay the ONLY locator of the pod (alignment to the '
                   'core / quill set once on the bench, short stiff chain pod-struts-rear ring-core); the cradle only carries '
                   'the weight through a soft elastomer pad on a PTFE slide plate, preloaded by a jack screw - free in x and '
                   'y, soft in z -> no double constraint, frame / mount deflection does not reach the quill',
           cradle_x=[-220.0, -190.0], preload_N=round(m_pod * 9.81, 0), pad_stiffness_N_mm=40.0,
           pad_deflection_mm=round(m_pod * 9.81 / 40.0, 2),
           load_change_per_0p1mm_frame_motion_N=round(40.0 * 0.1, 1),
           strut_moment_without_cradle_Nm=round(abs(m_pod * 9.81 * (-108.0 - x_cg)) / 1000, 2))
FR = dict(fixed_point='intake rear ring foot at x -5 (core front)', axial_growth_at_turbine_pads_mm=round(dx_turb, 2),
          axial_growth_at_exhaust_lugs_mm=round(dx_exh, 2), slot_free_each_side_mm=dict(turbine_pedestal=3.0, exhaust_lug=8.0),
          pod_support=POD,
          mass_est_kg=dict(engine_core=11.0, generator_pod=round(m_pod, 1), turbine_stage=3.5, intake=4.3, filter_box_lid_latches=9.3,
                           v_cell=5.5, exhaust=1.3, frame_and_supports=15.8))
FR['load_per_mount_N'] = round(sum(FR['mass_est_kg'].values()) * 9.81 / 4)
FR['f_n_Hz_est'] = round(15.76 / math.sqrt(2.0), 1)

OUT = dict(title='GR180 D2 intake / exhaust / frame 1-D numbers (rev 3: top V-cell box, diffuser-only exhaust, pod cradle)',
           date='2026-10-23', frame='ENG mm', intake=IN, exhaust=EX, frame_supports=FR)
json.dump(OUT, open(os.path.join(HERE, 'd2_intake_exhaust_calc.json'), 'w'), indent=1)

if __name__ == '__main__':
    r = IN['site_30C']
    print('INTAKE top V-cell box: Q %.3f m3/s (%d m3/h), face %.2f m/s' % (r['Q_m3_s'], r['Q_m3_h'], r['filter_face_v_m_s']))
    for e in r['elements']:
        print('   %-80s %5.1f m/s %6.1f Pa' % (e['name'], e['v_m_s'], e['dp_Pa']))
    print('   housing %d Pa, filter clean %d / change-out %d Pa -> total clean %d Pa (%.2f %%, %.2f kW), dirty %d Pa (%.2f %%, %.2f kW)' % (
        r['housing_dp_Pa'], r['filter_clean_Pa'], r['filter_change_out_Pa'], r['total_clean_Pa'], r['total_clean_pct'],
        r['power_cost_clean_kW_est'], r['total_dirty_Pa'], r['total_dirty_pct'], r['power_cost_dirty_kW_est']))
    print('EXHAUST q6 %.0f Pa, P0_6 %.3f bar' % (q6, P0_6 / 1e5))
    for s in (choice, best['DN125'], best['DN150']):
        print('  %-22s Dd %5.1f  internal %5d  q_exit %4d (v %4.1f)  total %5d Pa (%.2f %%)  Cp %.2f  cost %.2f kW  gain %.2f kW' % (
            s['name'], s['D_diff_exit'], s['dp0_internal_Pa'], s['q_flange_Pa'], s['v_flange_m_s'], s['dp0_incl_exit_Pa'],
            s['pct_of_P0'], s['Cp_system'], s['cost_vs_ideal_kW'], s['gain_vs_no_diffuser_dump_kW']))
    print('  dropping the DN125 stub costs %+.2f kW; cost by length %s' % (EX['cost_of_dropping_the_stub_kW'], EX['by_length']))
    print('POD %.2f kg, CG x %.1f, strut moment w/o cradle %.2f N.m' % (m_pod, x_cg, POD['strut_moment_without_cradle_Nm']))
    print('FRAME growth turbine pads %.2f mm, exhaust lugs %.2f mm, load/mount %d N' % (dx_turb, dx_exh, FR['load_per_mount_N']))
