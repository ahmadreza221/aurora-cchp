# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy"]
# ///
"""GR180 version E - detailed generator rotor in the E shaft system: lateral critical speeds (coupled core + generator beam
FE with gyroscopics, crowned-hex pin to the core rotor, 4 SFD supports - functions of sim/variant_e/e_rotor.py), damped
modes at 35k, free-free bending of the generator rotor alone (rigid-rotor balancing check), unbalanced magnetic pull,
torsional mode of the quill system, gravity / UMP bearing loads, L10 life and friction, balancing specification
(ISO 21940-11) and the quill / taper / pull-bolt check.
Run:  python3 sim/variant_e/eg_rotor.py  ->  sim/variant_e/eg_rotor.json
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_e'))
sys.path.insert(0, HERE)
import eg_layout as EG                                         # noqa: E402
import e_rotor as ER                                           # noqa: E402  (core rotor model, FE helpers)

E_ST, RHO_ST = 205e9, 7850.0
EM, ROT, Q = EG.EM, EG.ROT, EG.QUILL_EG
OM = EG.N_RUN * math.pi / 30
OP = (0.55 * EG.N_RUN, 1.08 * EG.N_RUN)


def gen_rotor():
    seg = []
    for (n, x0, x1, r) in ROT['shaft']:
        rr = 15.9 if 'taper' in n else r
        seg.append((x0, x1, rr, 0.0, E_ST, RHO_ST, 1.0))
    s0, s1 = ROT['screen']
    rsh = EM['magnet_ID'] / 2 - EM['shield_t']
    seg.append((s0, s1, EM['magnet_ID'] / 2, rsh, 125e9, 8890.0, 0.5))                                  # CuCr1Zr screen (shrunk: half stiffness)
    m0, m1 = ROT['magnets']
    seg.append((m0, m1, EM['magnet_OD'] / 2, EM['magnet_ID'] / 2, 140e9, 8400.0, 0.0))                  # laminated SmCo: mass only
    seg.append((s0, m0, EM['magnet_OD'] / 2, EM['magnet_ID'] / 2, 193e9, 7950.0, 0.3))                   # end rings
    seg.append((m1, s1, EM['magnet_OD'] / 2, EM['magnet_ID'] / 2, 193e9, 7950.0, 0.3))
    seg.append((s0, s1, EM['rotor_OD'] / 2, EM['magnet_OD'] / 2, 12e9, 1580.0, 1.0))                     # CFRP sleeve (axial E ~12 GPa)
    seg.append((Q['hub'][0], Q['hub'][1], Q['hub_OD'] / 2, 15.9, E_ST, RHO_ST, 1.0))
    seg.append((Q['waist'][0], Q['waist'][1], Q['waist_d'] / 2, Q['bore_d'] / 2, E_ST, RHO_ST, 1.0))
    seg.append((Q['socket'][0], Q['socket'][1], Q['socket_OD'] / 2, 12.5, E_ST, RHO_ST, 1.0))
    ir = 0.07
    disks = {'brg_IR_front': (ir, EG.X_GF, 1.2e-4, 0.8e-4), 'brg_IR_rear': (ir, EG.X_GR, 1.2e-4, 0.8e-4),
             'nut_front+speed_wheel': (0.26, -803.0, 2.0e-4, 1.2e-4), 'nut_rear': (0.13, -386.5, 1.0e-4, 0.6e-4), 'pull_bolt': (0.06, -350.0, 1e-6, 1e-6)}
    return seg, disks


def mass_props(seg, disks):
    m = 0.0; mx = 0.0; Ip = 0.0; It_cg = None
    items = []
    for (x0, x1, ro, ri, E, rho, fac) in seg:
        if rho < 100:
            continue
        mm = rho * math.pi * ((ro / 1e3) ** 2 - (ri / 1e3) ** 2) * (x1 - x0) / 1e3
        items.append((mm, 0.5 * (x0 + x1), 0.5 * mm * ((ro / 1e3) ** 2 + (ri / 1e3) ** 2), (x1 - x0) / 1e3, ro, ri))
    for k, (mm, x, ip, it) in disks.items():
        items.append((mm, x, ip, 0.0, 0.0, 0.0))
    m = sum(i[0] for i in items); xg = sum(i[0] * i[1] for i in items) / m
    Ip = sum(i[2] for i in items)
    It = sum(i[0] * ((i[1] - xg) / 1e3) ** 2 + i[0] * ((i[3]) ** 2 / 12 + ((i[4] / 1e3) ** 2 + (i[5] / 1e3) ** 2) / 4) for i in items)
    return dict(mass_kg=m, x_cg=xg, Ip_kgm2=Ip, It_kgm2=It)


def system(kb=3e6, cb=3000.0, k_ump=0.0, pin=True, kb_core=None):
    se, de = ER.core_rotor()
    sg, dg = gen_rotor()
    xe = ER.mesh(se, de, [ER.L.X_BF, ER.L.X_BR, ER.X_PIN])
    xg = ER.mesh(sg, dg, [EG.X_GF, EG.X_GR, ER.X_PIN, ROT['magnets'][0], ROT['magnets'][1]])
    Ke, Me, Pe = ER.assemble(se, de, xe)
    Kg, Mg, Pg = ER.assemble(sg, dg, xg)
    ng, ne = Kg.shape[0], Ke.shape[0]
    n = ng + ne
    K = np.zeros((n, n)); M = np.zeros((n, n)); P = np.zeros((n, n)); C = np.zeros((n, n))
    K[:ng, :ng] = Kg; M[:ng, :ng] = Mg; P[:ng, :ng] = Pg
    K[ng:, ng:] = Ke; M[ng:, ng:] = Me; P[ng:, ng:] = Pe
    for xb, off, xs_, kk in ((EG.X_GF, 0, xg, kb), (EG.X_GR, 0, xg, kb), (ER.L.X_BF, ng, xe, (kb_core or kb) * 1.5), (ER.L.X_BR, ng, xe, kb_core or kb)):
        i = off + 2 * int(np.argmin(abs(xs_ - xb)))
        K[i, i] += kk; C[i, i] += cb
    if k_ump:
        sel = [j for j in range(len(xg)) if ROT['magnets'][0] <= xg[j] <= ROT['magnets'][1]]
        for j in sel:
            K[2 * j, 2 * j] -= k_ump / len(sel)
    if pin:
        ig = 2 * int(np.argmin(abs(xg - ER.X_PIN))); ie = ng + 2 * int(np.argmin(abs(xe - ER.X_PIN)))
        kp = 2e9
        K[ig, ig] += kp; K[ie, ie] += kp; K[ig, ie] -= kp; K[ie, ig] -= kp
    X = np.concatenate([xg, xe]); owner = ['gen'] * len(xg) + ['eng'] * len(xe)
    return K, M, P, C, X, owner, (Kg, Mg, Pg, xg)


def free_free_gen(with_quill=False):
    sg, dg = gen_rotor()
    if not with_quill:
        sg = [s for s in sg if s[1] <= Q['hub'][0] + 0.1]
        dg = {k: v for k, v in dg.items() if k != 'pull_bolt'}
    xg = ER.mesh(sg, dg, [EG.X_GF, EG.X_GR])
    K, M, P = ER.assemble(sg, dg, xg)
    w2 = np.linalg.eigvals(np.linalg.solve(M, K))
    w2 = np.sort(np.real(w2[np.abs(np.imag(w2)) < 1e-6 * np.abs(w2) + 1e-9]))
    fl = [math.sqrt(v) * 60 / (2 * math.pi) for v in w2 if v > 1e2]
    return [round(v) for v in fl[:3]]


def ump_stiffness():
    em = json.load(open(os.path.join(HERE, 'eg_em.json')))
    Bg = em['no_load']['B_gap_fund_T']
    r = (EM['bore'] / 2 + EM['rotor_OD'] / 2) / 4e3
    Lm = EM['stack'] / 1e3
    g_m = (EM['bore'] - EM['magnet_OD']) / 2e3 + (EM['magnet_OD'] - EM['magnet_ID']) / 2e3 / EM['mu_r']
    k = math.pi * r * Lm * Bg ** 2 / (2 * 4e-7 * math.pi * g_m)
    return k, dict(B_gap_T=Bg, g_magnetic_mm=round(g_m * 1e3, 1), k_N_um=round(k / 1e6, 3), F_at_0p1mm_N=round(k * 1e-4, 1))


def main():
    out = dict(title='GR180 version E detailed generator rotor in the shaft system', date='2026-10-24', script='sim/variant_e/eg_rotor.py',
               model='coupled core (e_rotor.core_rotor) + detailed generator rotor beam FE, gyroscopics, crowned-hex pin at x %.1f, SFD O-ring supports' % ER.X_PIN)
    sg, dg = gen_rotor()
    mp = mass_props(sg, dg)
    mq = mass_props([s for s in sg if s[0] >= Q['hub'][0] - 0.1], {})
    out['generator_rotor'] = dict(mass_kg=round(mp['mass_kg'], 2), x_cg_mm=round(mp['x_cg'], 1), Ip_kgm2=round(mp['Ip_kgm2'], 4), It_kgm2=round(mp['It_kgm2'], 4),
                                  Ip_over_It=round(mp['Ip_kgm2'] / mp['It_kgm2'], 3), quill_kg=round(mq['mass_kg'], 2), bearing_span_mm=EG.X_GR - EG.X_GF,
                                  shaft_length_mm=ROT['shaft'][-1][2] - ROT['shaft'][0][1], segments=[list(s) for s in sg])
    k_ump, ump = ump_stiffness()
    out['unbalanced_magnetic_pull'] = ump
    print('generator rotor %.2f kg (quill %.2f), x_cg %.1f, Ip %.4f It %.4f; UMP %.3f N/um' % (mp['mass_kg'], mq['mass_kg'], mp['x_cg'], mp['Ip_kgm2'], mp['It_kgm2'], k_ump / 1e6))
    lo, hi = OP
    cases = {}
    for lab, kw in (('SFD 3 N/um (base)', dict(kb=3e6)), ('SFD 3 N/um + UMP', dict(kb=3e6, k_ump=k_ump)), ('SFD 1.5 N/um', dict(kb=1.5e6)),
                    ('SFD 6 N/um', dict(kb=6e6)), ('rigid 50 N/um (ref)', dict(kb=50e6)), ('3 N/um, no quill pin', dict(kb=3e6, pin=False))):
        K, M, P, C, X, own, _ = system(**kw)
        cr = ER.criticals(K, M, P, X, own, n_modes=9)
        cases[lab] = cr
        print('  %-26s %s' % (lab, ' | '.join('%5.1fk@%s%.0f%s' % (c['rpm'] / 1e3, c['rotor'][0], c['x_max_mm'], ' !OPR' if lo <= c['rpm'] <= hi else '') for c in cr)))
    out['criticals'] = cases
    marg = {}
    for lab in ('SFD 3 N/um (base)', 'SFD 3 N/um + UMP', 'SFD 1.5 N/um', 'SFD 6 N/um'):
        cr = [c['rpm'] for c in cases[lab]]
        above = [c for c in cr if c > hi]; below = [c for c in cr if c < lo]
        marg[lab] = dict(highest_below_55pct=max(below) if below else None, lowest_above_108pct=min(above) if above else None,
                         margin_above_run_pct=round(100 * (min(above) / EG.N_RUN - 1), 1) if above else None, inside_operating_range=[c for c in cr if lo <= c <= hi])
    out['margins'] = marg
    K, M, P, C, X, own, _ = system(kb=3e6, k_ump=k_ump)
    dmp = ER.damped(K, M, P, C, OM, X, own, nmax=10)
    out['damped_35k'] = dmp
    print('damped @35k:', ' | '.join('%.1fk z%.3f %s%.0f' % (m['rpm'] / 1e3, m['zeta'], m['rotor'][0], m['x_max_mm']) for m in dmp))
    ff = free_free_gen()
    ffq = free_free_gen(with_quill=True)
    out['free_free_generator_rotor_rpm'] = dict(without_quill=ff, with_quill=ffq, note='with the quill the first flexible mode is the quill / socket cantilever; '
                                                'in service the socket is pinned on the core hex (coupled model above)')
    out['rigid_rotor_check'] = dict(first_bending_free_free_rpm=ff[0] if ff else None, ratio_to_run=round(ff[0] / EG.N_RUN, 2) if ff else None,
                                    verdict='rigid rotor (ISO 21940-11): n_run < 0.5 x first bending -> 2-plane low-speed balancing valid' if ff and ff[0] > 2 * EG.N_RUN
                                    else 'quasi-rigid: low-speed 2-plane balance + check at speed')
    print('free-free generator rotor bending (no quill / with quill):', ff, ffq)
    # torsion: generator rotor + quill (hollow) + core rotor
    G = 80e9
    Jq = math.pi / 32 * ((Q['waist_d'] / 1e3) ** 4 - (Q['bore_d'] / 1e3) ** 4)
    Lq = (Q['waist'][1] - Q['waist'][0]) / 1e3
    kt = G * Jq / Lq
    Jg = mp['Ip_kgm2']
    se, de = ER.core_rotor()
    Jc = sum(d[2] for d in de.values()) + sum(rho * math.pi / 2 * ((ro / 1e3) ** 4 - (ri / 1e3) ** 4) * (x1 - x0) / 1e3 for (x0, x1, ro, ri, E, rho, f) in se if rho > 1000)
    ft = math.sqrt(kt * (1 / Jg + 1 / Jc)) / (2 * math.pi)
    T_rated = 335e3 / OM
    em = json.load(open(os.path.join(HERE, 'eg_em.json')))
    T_sc = em['short_circuit']['T_peak_Nm']
    f_sc = EG.F_EL
    trans = 1.0 / abs(1 - (f_sc / ft) ** 2)
    tau = lambda T: 16 * T * (Q['waist_d'] / 1e3) / (math.pi * ((Q['waist_d'] / 1e3) ** 4 - (Q['bore_d'] / 1e3) ** 4)) / 1e6
    out['torsion'] = dict(k_quill_Nm_rad=round(kt), J_gen_kgm2=round(Jg, 4), J_core_kgm2=round(Jc, 4), f_mode_Hz=round(ft, 1), mode_rpm_equiv=round(ft * 60),
                          speed_at_1x_crossing_pct=round(100 * ft * 60 / EG.N_RUN, 1),
                          excitations=dict(ripple_6f_Hz=round(6 * EG.F_EL), ripple_6f_pct=em['load_335kW']['ripple_6f_pct'], separation_6f=round(6 * EG.F_EL / ft, 1),
                                           start_inverter='6f of the start inverter crosses the mode at %.0f rpm (%.1f %% speed, low torque, fast pass)' % (ft * 60 / 6, 100 * ft * 60 / 6 / EG.N_RUN)),
                          tau_rated_MPa=round(tau(T_rated), 1), tau_sc_transmitted_MPa=round(tau(T_rated + T_sc * trans), 1), sc_transmissibility=round(trans, 3),
                          tau_5x_rated_MPa=round(tau(5 * T_rated), 1), allowable_MPa='34CrNiMo6 QT Rp0.2 >= 800 -> tau_allow ~ 230 (static), fatigue tau_A ~ 160 (shot-peened)')
    # taper + pull bolt
    F_b = 60e3; alpha = math.atan(1 / 20.0); mu = 0.15
    rm = (ROT['taper']['d_large'] + ROT['taper']['d_small']) / 4e3
    T_cap = mu * F_b * rm / (math.sin(alpha) + mu * math.cos(alpha))
    A_c = math.pi * 2 * rm * (ROT['taper']['x_small'] - ROT['taper']['x_large']) / 1e3
    p_c = F_b / (A_c * (math.sin(alpha) + mu * math.cos(alpha)))
    out['quill_taper'] = dict(taper='1:10 on diameter, d33 -> d30.6 x 24', pull_bolt=ROT['taper']['pull_bolt'], preload_kN=F_b / 1e3,
                              torque_capacity_Nm=round(T_cap), over_5x_rated=round(T_cap / (5 * T_rated), 2), contact_pressure_MPa=round(p_c / 1e6, 1),
                              hub_hoop_MPa=round(p_c * (28 ** 2 + 16 ** 2) / (28 ** 2 - 16 ** 2) / 1e6, 1),
                              tightening='through the hollow quill (bore d19) with an AF10 x 300 hex bit + torque wrench; release: M14 jacking screw through the same bore')
    # bearing loads: gravity reactions + UMP at 0.1 mm eccentricity + unbalance G2.5
    Wg = mp['mass_kg'] * 9.81
    xg_ = mp['x_cg']
    Rr = Wg * (xg_ - EG.X_GF) / (EG.X_GR - EG.X_GF); Rf = Wg - Rr
    U_g25 = 2.5e-3 / OM * mp['mass_kg']               # kg m
    F_unb = U_g25 * OM ** 2
    F_ump = k_ump * 1e-4
    life = {}
    for tag, Fr, Fa, ang in (('front (locating, 7008-E)', Rf + 0.5 * (F_ump + F_unb), 350.0, 'E'), ('rear (floating, 7008-C)', Rr + 0.5 * (F_ump + F_unb), 300.0, 'C')):
        Pq = ER.P_eq(Fr, Fa, ang)
        Cd = ER.L.BRG['C_dyn'] * (0.95 if ang == 'E' else 1.0)
        l10 = ER.L10h(Cd, Pq)
        life[tag] = dict(Fr_N=round(Fr), Fa_N=Fa, P_N=round(Pq), L10_h=round(l10), L10m_aISO3_h=round(3 * l10), friction_W=round(ER.friction_W(Fr, Fa)),
                         ndm=round(EG.N_RUN * 0.5 * (EG.BRG['d'] + EG.BRG['D'])))
    out['bearings'] = dict(type=EG.BRG['model'], preload='300 N wave spring on the rear outer ring (floating) -> both bearings loaded; front locating (OR clamped)',
                           static=dict(front_N=round(Rf), rear_N=round(Rr)), F_unbalance_G2p5_N=round(F_unb, 1), F_ump_0p1mm_N=round(F_ump, 1), cases=life,
                           oil='ISO VG 32 synthetic, jet 2.5 L/min per bearing at 2.5 barg (d1.2 nozzle aimed at the IR / cage gap, 15 deg), SFD feed from the same gallery, '
                               'drain d12 at the hub bottom; oil in 55 C; replace both at 24,000 h with the core set', replace_h=24000)
    # balancing (ISO 21940-11)
    planes = dict(front=ROT['sleeve'][0] + 6.0, rear=ROT['sleeve'][1] - 6.0)
    bal = {}
    for G_ in (1.0, 2.5):
        U = G_ * 1e-3 / OM * mp['mass_kg'] * 1e6          # g mm
        a = (mp['x_cg'] - planes['front']) / (planes['rear'] - planes['front'])
        bal['G%.1f' % G_] = dict(U_total_gmm=round(U, 2), e_per_um=round(G_ * 1e-3 / OM * 1e6, 3), U_front_gmm=round(U * (1 - a), 2), U_rear_gmm=round(U * a, 2))
    out['balancing'] = dict(standard='ISO 21940-11 (rigid rotor)', target='G1.0 (assembled rotor incl. bearings IR, nuts, speed wheel, quill)', acceptance='G2.5 max after the spin test',
                            planes_x_mm=planes, correction='radial holes d4 (max 3 deep, 12 positions) in the 1.4404 end rings at r 50 (magnet OD side), or grub-screw weights M5 in the end-ring face',
                            values=bal, procedure='1) balance the shaft + screen (G2.5), 2) magnets + end rings + sleeve -> balance G1 on the bearing journals (soft-bearing machine, '
                                                    '2 planes, 600-1500 rpm), 3) quill fitted on the taper (marked angle) -> check G1, 4) hot spin test 120 %, 5) re-check G1 / G2.5 acceptance, '
                                                    'record run-out of the socket <= 10 um TIR', machine='Schenck (DE) HM / CIMAT (PL) / own soft-bearing machine; spin pit: Schenck RoTec (DE) service')
    json.dump(out, open(os.path.join(HERE, 'eg_rotor.json'), 'w'), indent=1, default=float)
    print('margins:', json.dumps(marg))
    print('torsion:', out['torsion'])
    print('taper:', out['quill_taper'])
    print('bearings:', life)
    print('balance:', bal)
    print('-> sim/variant_e/eg_rotor.json')


if __name__ == '__main__':
    main()
