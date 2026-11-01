# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - ducts: large low-loss intake plenum with a filter-bank interface, deswirl annulus + cool pressure
casing + combustor annulus (no discharge pipe), transition duct + 360 deg hot plenum, long conical exhaust diffuser + elbow.
1-D loss budget (incompressible loss coefficients on the local dynamic head, Idelchik / Miller values; filter media
linear in flow) checked against the cycle budget in sim/variant_e/e_cycle.json:
    intake <= 0.25 % (mid-life filters) | casing path 0.8 % | transition + plenum 1.0 % | diffuser Cp 0.62, elbow K 0.20.
Accuracy ~ +/-30 %; ESTIMATES, confirm on the rig (static taps / rakes are in the CAD).

Run:  python3 sim/variant_e/e_ducts.py  ->  sim/variant_e/e_ducts.json
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CY = json.load(open(os.path.join(HERE, 'e_cycle.json')))
CO = json.load(open(os.path.join(HERE, 'e_compressor.json')))
TU = json.load(open(os.path.join(HERE, 'e_turbine.json')))
CB = json.load(open(os.path.join(HERE, 'e_combustor.json')))
DP = CY['design_point']; BUD = CY['budget_inputs']
P_AMB = DP['stations']['ambient']['P_bar'] * 1e5
M = DP['air_kg_s']
R_AIR = 288.9
pi = math.pi
q = lambda rho, V: 0.5 * rho * V * V

# ================================================================ INTAKE
FILT = dict(bank=(3, 3), cell=592, pitch=610, rated_m3_h=3400.0,
            fine=dict(cls='ISO ePM1 55 % (F7) compact V-cell 592x592x292 (Camfil Opakfil / Hi-Flo, Freudenberg Viledon, MANN+HUMMEL)',
                      dp_rated_initial=95.0, dp_change_at_our_flow=120.0),
            pre=dict(cls='ISO coarse 60 % (G4) panel 592x592x48', dp_rated_initial=45.0, dp_change_at_our_flow=60.0),
            hood_Pa=20.0)
INTAKE = dict(plenum_inner=dict(x=1900.0, y=1900.0, z=1300.0), pod_OD=340.0, radial_gap_r=320.0, radial_gap_h=230.0,
              eye=dict(D1t=CO['meanline']['inducer']['D1t_mm'], D1h=CO['meanline']['inducer']['D1h_mm']),
              K_bellmouth=0.006, K_quill_guard=0.002, K_gap=0.5)


def intake(T_C=30.0, m=M):
    rho = P_AMB / (R_AIR * (T_C + 273.15))
    Q = m / rho
    n = FILT['bank'][0] * FILT['bank'][1]
    Qc = Q * 3600 / n
    f = Qc / FILT['rated_m3_h']
    el = []
    el.append(('weather hood + louvres (plant scope, allowance)', FILT['hood_Pa'], FILT['hood_Pa'], FILT['hood_Pa']))
    for k in ('pre', 'fine'):
        d0 = FILT[k]['dp_rated_initial'] * f
        d1 = FILT[k]['dp_change_at_our_flow']
        el.append(('%s x %d at %.0f m3/h (%.0f %% of rating)' % (FILT[k]['cls'], n, Qc, 100 * f), d0, 0.5 * (d0 + d1), d1))
    A_pl = INTAKE['plenum_inner']['x'] * INTAKE['plenum_inner']['y'] / 1e6
    V_pl = Q / A_pl
    el.append(('clean chamber dump (V %.1f m/s, K 1.0)' % V_pl, q(rho, V_pl), q(rho, V_pl), q(rho, V_pl)))
    A_gap = 2 * pi * INTAKE['radial_gap_r'] / 1e3 * INTAKE['radial_gap_h'] / 1e3
    V_gap = Q / A_gap
    d = INTAKE['K_gap'] * q(rho, V_gap)
    el.append(('round the pod + radial gap pod tail -> bellmouth (V %.1f m/s, K %.1f)' % (V_gap, INTAKE['K_gap']), d, d, d))
    A_eye = pi / 4 * ((INTAKE['eye']['D1t'] / 1e3) ** 2 - (INTAKE['eye']['D1h'] / 1e3) ** 2) * 0.96
    V_eye = m / (rho * 0.94 * A_eye)
    d = INTAKE['K_bellmouth'] * q(rho, V_eye)
    el.append(('bellmouth + annular contraction to the eye (V %.0f m/s, K %.3f)' % (V_eye, INTAKE['K_bellmouth']), d, d, d))
    d = INTAKE['K_quill_guard'] * q(rho, V_eye)
    el.append(('quill guard tube / hub fairing friction (K %.3f)' % INTAKE['K_quill_guard'], d, d, d))
    tot = [sum(e[i] for e in el) for i in (1, 2, 3)]
    return dict(T_C=T_C, Q_m3_s=Q, cells=n, per_cell_m3_h=Qc, elements=[dict(item=e[0], clean_Pa=round(e[1], 1), mid_life_Pa=round(e[2], 1),
                                                                          change_out_Pa=round(e[3], 1)) for e in el],
                total_Pa=dict(clean=round(tot[0], 1), mid_life=round(tot[1], 1), change_out=round(tot[2], 1)),
                total_pct=dict(clean=round(100 * tot[0] / P_AMB, 3), mid_life=round(100 * tot[1] / P_AMB, 3), change_out=round(100 * tot[2] / P_AMB, 3)),
                cycle_budget_pct=100 * BUD['dp_inlet'],
                filter_flange=dict(opening_mm=[FILT['bank'][0] * FILT['pitch'], FILT['bank'][1] * FILT['pitch']], face='top of the plenum (+z)',
                                   frame='EN ISO 16890 / EN 1822 holding frames 610 x 610 pitch, 9 cells, knife-edge seals, filter house + hood = plant scope'))


# ================================================================ CASING PATH (deswirl annulus -> cool casing -> combustor dome)
def casing_path():
    T2 = DP['stations']['compressor_out']['T_C'] + 273.15
    P2 = DP['stations']['compressor_out']['P_bar'] * 1e5
    rho = P2 / (R_AIR * T2)
    A_ann = pi * (0.305 ** 2 - 0.261 ** 2)
    V_ann = M / (rho * A_ann)
    el = []
    el.append(('deswirl-annulus exit r 261..305 (V %.1f m/s) dumped into the cool pressure casing (K 1.0) - bend + deswirl are in eta_c' % V_ann, 1.0 * q(rho, V_ann)))
    V_cc = 9.0
    el.append(('flow round the floating hot plenum (gap ~27 mm, V ~%.0f m/s, K 1.5)' % V_cc, 1.5 * q(rho, V_cc)))
    V_an = CB['design_770']['casing']['annulus_velocity_m_s']
    el.append(('entry into the combustor annulus + annulus friction + 180 deg turn at the dome (V %.0f m/s, K 1.6)' % V_an, 1.6 * q(rho, V_an)))
    V_pipe = V_ann
    tot = sum(e[1] for e in el)
    return dict(elements=[dict(item=e[0], dp_Pa=round(e[1])) for e in el], total_Pa=round(tot), total_pct=round(100 * tot / P2, 3),
                cycle_budget_pct=100 * BUD['dp_casing'], annulus_velocity_m_s=round(V_pipe, 1))


# ================================================================ TRANSITION + HOT PLENUM
def transition():
    T4 = DP['stations']['nozzle_in']['T_C'] + 273.15
    P4 = DP['stations']['nozzle_in']['P_bar'] * 1e5
    rho = P4 / (292.3 * T4)
    mg = M * (1 - BUD['leak_lost'] - BUD['buffer']) + DP['fuel_kg_s']
    D_L = CB['design_770']['liner']['D_mm'] / 1e3
    A_tr = math.pi / 4 * 0.270 ** 2                                          # transition exit: diffusing cone d210 -> d270 into the plenum top
    V_L = mg / (rho * pi / 4 * D_L ** 2)
    V_tr = mg / (rho * A_tr)
    el = [('liner exit -> diffusing conical transition (d210 -> d270, AR 1.65, half angle 9 deg, K 0.25 on the head drop)', 0.25 * (q(rho, V_L) - q(rho, V_tr)) + 0.05 * q(rho, V_L)),
          ('dump into the 360 deg hot plenum (K 0.95)', 0.95 * q(rho, V_tr)),
          ('plenum distribution round the nozzle ring (V ~15 m/s, K 1.0)', 1.0 * q(rho, 15.0))]
    tot = sum(e[1] for e in el)
    return dict(elements=[dict(item=e[0], dp_Pa=round(e[1])) for e in el], total_Pa=round(tot), total_pct=round(100 * tot / P4, 3),
                cycle_budget_pct=100 * BUD['dp_transition'], V_liner_m_s=round(V_L, 1), V_transition_m_s=round(V_tr, 1),
                note='single-entry plenum: circumferential TIT / pressure non-uniformity to be checked by CFD (OpenFOAM, as D2 open item)')


# ================================================================ EXHAUST
EXH = dict(D_in=TU['geometry']['D6t'], D_hub=TU['geometry']['D6h'], two_theta=10.0, D_out=420.0, eta_d=0.70, K_elbow=0.12,
           elbow='90 deg, R/D 1.5, 5 segments + 2 turning vanes, DN450 (457 x 6.3) 1.4828', flange='DN450 PN6 EN 1092-1 (verify)')


def exhaust():
    t = TU['design_770']
    rho6 = t['P6_bar'] * 1e5 / (292.3 * (t['T6_C'] + 273.15))
    c6 = t['c6_m_s']
    L = (EXH['D_out'] - EXH['D_in']) / 2 / math.tan(math.radians(EXH['two_theta'] / 2))
    A_in = pi / 4 * ((EXH['D_in'] / 1e3) ** 2 - (EXH['D_hub'] / 1e3) ** 2)
    A_out = pi / 4 * (EXH['D_out'] / 1e3) ** 2
    AR = A_out / A_in
    Cp_i = 1 - 1 / AR ** 2
    Cp = EXH['eta_d'] * Cp_i
    q6 = q(rho6, c6)
    V_out = c6 / AR
    q_out = q(rho6 * 1.01, V_out)
    d_elbow = EXH['K_elbow'] * q_out
    loss_diff = (Cp_i - Cp) * q6
    return dict(L_mm=round(L), AR=round(AR, 2), Cp_ideal=round(Cp_i, 3), Cp=round(Cp, 3), q6_Pa=round(q6), recovery_Pa=round(Cp * q6),
                diffuser_loss_Pa=round(loss_diff), exit_V_m_s=round(V_out, 1), exit_q_Pa=round(q_out), elbow_dp_Pa=round(d_elbow),
                cycle_assumed=dict(Cp=BUD['cp_diff'], AR=BUD['AR_diff'], K_elbow=BUD['K_elbow'], dp_down_Pa=BUD['dp_down']),
                p6_vs_ambient_Pa=round(BUD['dp_down'] + d_elbow - Cp * q6), geometry=EXH,
                tail_cone='rotating nose cone on the turbine nut (d75 -> 0 over 90 mm) - no stationary struts in the hot exhaust',
                build='2 rolled 1.4828 3 mm cone sections, PN6-type ring flanges, piston-ring slip joint to the exducer shroud, sliding feet; '
                      'outside: 100 mm ceramic-fibre blanket + 1.4301 cladding (touch < 60 C)')


def main():
    res = dict(title='GR180 version E ducts: intake plenum + filter interface, casing path, transition / plenum, exhaust diffuser', date='2026-10-23',
               script='sim/variant_e/e_ducts.py')
    res['intake_30C'] = intake(30.0)
    res['intake_0C_max_flow'] = intake(0.0, CY['ambient_table_TIT770_capped'][0]['air_kg_s'])
    res['casing_path'] = casing_path()
    res['transition_plenum'] = transition()
    res['exhaust'] = exhaust()
    i = res['intake_30C']
    print('INTAKE (30 C, %.2f m3/s, %d cells x %.0f m3/h):' % (i['Q_m3_s'], i['cells'], i['per_cell_m3_h']))
    for e in i['elements']:
        print('  %-92s clean %5.1f  mid %5.1f  change %5.1f Pa' % (e['item'], e['clean_Pa'], e['mid_life_Pa'], e['change_out_Pa']))
    print('  TOTAL clean %.0f / mid-life %.0f / change-out %.0f Pa = %.3f / %.3f / %.3f %%  (cycle budget %.2f %%)' % (
        i['total_Pa']['clean'], i['total_Pa']['mid_life'], i['total_Pa']['change_out'], i['total_pct']['clean'], i['total_pct']['mid_life'],
        i['total_pct']['change_out'], i['cycle_budget_pct']))
    for k in ('casing_path', 'transition_plenum'):
        c = res[k]
        print('%s:' % k.upper())
        for e in c['elements']:
            print('  %-100s %6d Pa' % (e['item'], e['dp_Pa']))
        print('  TOTAL %d Pa = %.3f %% (cycle budget %.2f %%)' % (c['total_Pa'], c['total_pct'], c['cycle_budget_pct']))
    e = res['exhaust']
    print('EXHAUST: cone 2theta %.0f deg, d%.0f/%.0f -> d%.0f, L %d mm, AR %.2f, Cp %.3f (ideal %.3f) [cycle %.2f], q6 %d Pa, recovery %d Pa, '
          'diffuser loss %d Pa, exit %.0f m/s, elbow %d Pa, p6 - p_amb %+d Pa' % (
              EXH['two_theta'], EXH['D_in'], EXH['D_hub'], EXH['D_out'], e['L_mm'], e['AR'], e['Cp'], e['Cp_ideal'], BUD['cp_diff'], e['q6_Pa'],
              e['recovery_Pa'], e['diffuser_loss_Pa'], e['exit_V_m_s'], e['elbow_dp_Pa'], e['p6_vs_ambient_Pa']))
    json.dump(res, open(os.path.join(HERE, 'e_ducts.json'), 'w'), indent=1)
    print('-> sim/variant_e/e_ducts.json')


if __name__ == '__main__':
    main()
