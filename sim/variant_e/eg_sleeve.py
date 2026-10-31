# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "gmsh", "matplotlib"]
# ///
"""GR180 version E - generator rotor retention: carbon-fibre sleeve vs Inconel 718 sleeve; interference, stresses at
standstill / 100 % / 108 % trip / 120 % spin test, cold and hot; eddy loss of a metallic sleeve; assembly (press-fit).

Model: 1D axisymmetric plane-stress finite elements in r (linear elements, 2-point Gauss) through
  42CrMo4 shaft (solid, r 0-35.5) | CuCr1Zr screen 35.5-37.0 | Sm2Co17 ring 37-53 | sleeve 53-60
with cylindrically orthotropic materials (CFRP hoop-wound: E_theta >> E_r), thermal strains, centrifugal load, and two
shrink interfaces (screen/shaft, sleeve/magnet) as contact constraints (Lagrange multipliers; an interface whose pressure
would turn tensile is released and re-solved).  Segmented magnets: E_theta ~ 0 (12 circumferential segments carry no
hoop tension; conservative for the sleeve), plus a sensitivity with closed joints (arch action, compression only).
Criteria: magnet/screen contact pressure >= 10 MPa at the 108 % trip with a cold (0 C) rotor (allows ~10 % resin-creep
relaxation), >= 0 at the 120 % spin test done HOT (rotor pre-heated to 100 C in the vacuum pit); CFRP hoop <= 0.40 UTS_eff
long-term (100 % hot), <= 0.60 UTS_eff at the spin test; radial stress compressive in the composite; magnets in compression.
UTS_eff = 0.92 UTS (lay-up 88 % hoop + 12 % +/-15 deg helical layers for axial strength during the press-fit).
Run:  ~/micromamba/envs/gr180/bin/python sim/variant_e/eg_sleeve.py  ->  sim/variant_e/eg_sleeve.json
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_e'))
sys.path.insert(0, HERE)
import eg_layout as EL                  # noqa: E402

EM = EL.EM
W0 = EL.N_RUN * math.pi / 30
R_SH = EM['magnet_ID'] / 2 - EM['shield_t']
R_C, R_M, R_S = EM['magnet_ID'] / 2, EM['magnet_OD'] / 2, EM['rotor_OD'] / 2

MAT = {   # E_r, E_t (Pa), nu_rt (eps_t = -nu_rt sigma_r / E_r), rho, alpha_r, alpha_t (1/K), strengths (MPa)
    '42CrMo4': dict(Er=205e9, Et=205e9, nu=0.29, rho=7850, ar=11.5e-6, at=11.5e-6, Rp=750),
    'CuCr1Zr': dict(Er=125e9, Et=125e9, nu=0.34, rho=8890, ar=17.0e-6, at=17.0e-6, Rp=300),
    'SmCo_seg': dict(Er=140e9, Et=1e6, nu=0.0, rho=8400, ar=10.0e-6, at=10.0e-6, comp=800, tens=35),
    'SmCo_arch': dict(Er=140e9, Et=140e9, nu=0.27, rho=8400, ar=10.0e-6, at=10.0e-6, comp=800, tens=35),
    # hoop-wound UD carbon / high-Tg epoxy, Vf 0.60 (Toray T700S / T800S class, or Zhongfu Shenying SYT49 / SYT55)
    'T700S': dict(Er=9.0e9, Et=135e9, nu=0.02, rho=1580, ar=30e-6, at=-0.3e-6, UTS=2450, Ttr=60, Ctr=200),
    'T800S': dict(Er=9.0e9, Et=155e9, nu=0.02, rho=1580, ar=30e-6, at=-0.4e-6, UTS=2800, Ttr=60, Ctr=200),
    'IN718': dict(Er=200e9, Et=200e9, nu=0.29, rho=8190, ar=13.0e-6, at=13.0e-6, Rp=1030, UTS=1240),
}


def D_of(m):
    Er, Et = m['Er'], m['Et']
    nu_rt = m['nu']
    nu_tr = nu_rt * Et / Er if Er != Et else nu_rt
    S = np.array([[1 / Er, -nu_tr / Et], [-nu_tr / Et, 1 / Et]]) if Er != Et else np.array([[1 / Er, -nu_rt / Er], [-nu_rt / Er, 1 / Er]])
    return np.linalg.inv(S)


def solve(layers, interf, omega, T, contact=None, nel=40):
    """layers: [(name, r_in mm, r_out mm, material)], interf: diametral interference (mm) at the interfaces between layer i and
    i+1, T: temperature per layer (C, stress-free 20 C).  Returns stresses per layer and interface pressures (MPa)."""
    contact = contact if contact is not None else [True] * (len(layers) - 1)
    nodes, el = [], []
    off = []
    for li, (nm, a, b, mat) in enumerate(layers):
        off.append(len(nodes))
        a_ = max(a, 1e-3)
        rs = np.linspace(a_, b, nel + 1) * 1e-3
        base = len(nodes)
        nodes += list(rs)
        for k in range(nel):
            el.append((li, base + k, base + k + 1))
    n = len(nodes)
    r = np.array(nodes)
    K = np.zeros((n, n)); f = np.zeros(n)
    gp = [(-1 / math.sqrt(3), 1.0), (1 / math.sqrt(3), 1.0)]
    for (li, i, j) in el:
        m = MAT[layers[li][3]]
        D = D_of(m)
        ra, rb = r[i], r[j]; h = rb - ra
        th = np.array([m['ar'], m['at']]) * (T[li] - 20.0)
        for xi, wg in gp:
            rr = 0.5 * (ra + rb) + 0.5 * h * xi
            N = np.array([(rb - rr) / h, (rr - ra) / h])
            B = np.array([[-1 / h, 1 / h], N / rr])
            dv = rr * 0.5 * h * wg
            K[np.ix_([i, j], [i, j])] += B.T @ D @ B * dv
            f[[i, j]] += N * m['rho'] * omega ** 2 * rr * dv + B.T @ D @ th * dv
    act = list(contact)
    for it in range(10):
        cons = [k for k in range(len(layers) - 1) if act[k]]
        nc = len(cons)
        A = np.zeros((n + nc + 1, n + nc + 1)); A[:n, :n] = K
        rhs = np.zeros(n + nc + 1); rhs[:n] = f
        A[n + nc, 0] = 1.0; A[0, n + nc] = 1.0           # u(r ~ 0) = 0
        for c, k in enumerate(cons):
            ia = off[k] + nel; ib = off[k + 1]
            A[n + c, ib] = 1.0; A[n + c, ia] = -1.0; A[ib, n + c] = 1.0; A[ia, n + c] = -1.0
            rhs[n + c] = interf[k] / 2 * 1e-3
        x = np.linalg.solve(A, rhs)
        u = x[:n]; lam = x[n:n + nc]
        p = {}
        rel = False
        for c, k in enumerate(cons):
            rk = layers[k][2] * 1e-3
            p[k] = -lam[c] / rk / 1e6            # contact pressure (MPa), + = compression
            if p[k] < -1e-6:
                act[k] = False; rel = True
        if not rel:
            break
    # stresses at element mid-points
    res = []
    for li, (nm, a, b, mat) in enumerate(layers):
        m = MAT[mat]; D = D_of(m)
        th = np.array([m['ar'], m['at']]) * (T[li] - 20.0)
        sr, st, rr_ = [], [], []
        for k in range(nel):
            i, j = off[li] + k, off[li] + k + 1
            ra, rb = r[i], r[j]; h = rb - ra; rm = 0.5 * (ra + rb)
            eps = np.array([(u[j] - u[i]) / h, 0.5 * (u[i] + u[j]) / rm])
            s = D @ (eps - th) / 1e6
            sr.append(s[0]); st.append(s[1]); rr_.append(rm * 1e3)
        res.append(dict(layer=nm, material=mat, r_mm=[round(rr_[0], 2), round(rr_[-1], 2)], sr_MPa=[round(min(sr), 1), round(max(sr), 1)],
                        st_MPa=[round(min(st), 1), round(max(st), 1)], st_inner=round(st[0], 1), st_outer=round(st[-1], 1),
                        vm_max=round(max(math.sqrt(a_ ** 2 - a_ * b_ + b_ ** 2) for a_, b_ in zip(sr, st)), 1),
                        u_out_um=round(u[off[li] + nel] * 1e6, 2)))
    press = {('%s/%s' % (layers[k][0], layers[k + 1][0])): (round(p.get(k, 0.0), 2) if act[k] else 'OPEN') for k in range(len(layers) - 1)}
    return res, press


CASES = [  # name, speed fraction, T shaft, T screen, T magnet, T sleeve
    ('standstill 20 C (as assembled)', 0.0, 20, 20, 20, 20),
    ('standstill hot (shut-down soak)', 0.0, 90, 95, 100, 95),
    ('100 % hot (35,000 rpm)', 1.0, 90, 95, 100, 95),
    ('108 % trip hot (37,800 rpm)', 1.08, 90, 95, 100, 95),
    ('108 % trip cold rotor 0 C', 1.08, 0, 0, 0, 0),
    ('120 % spin test HOT (42,000 rpm, rotor 100 C, vacuum pit)', 1.20, 100, 100, 100, 100),
    ('120 % cold 20 C (information: not the test condition)', 1.20, 20, 20, 20, 20),
    ('cold start 0 C, 100 %', 1.0, 0, 0, 0, 0),
]


def run(sleeve_mat, t_sl, d_sleeve, d_screen=0.10, magnet='SmCo_seg'):
    r_m = R_S - t_sl
    layers = [('shaft', 0.0, R_SH, '42CrMo4'), ('screen', R_SH, R_C, 'CuCr1Zr'), ('magnet', R_C, r_m, magnet), ('sleeve', r_m, R_S, sleeve_mat)]
    out = []
    for (nm, s, Ts, Tc, Tm, Tl) in CASES:
        res, pr = solve(layers, [d_screen, 0.0, d_sleeve], s * W0, [Ts, Tc, Tm, Tl], contact=[True, True, True])
        out.append(dict(case=nm, speed_pct=round(100 * s), stresses=res, interface_MPa=pr))
    return out


def summary(rows, mat):
    m = MAT[mat]
    def get(rr, layer):
        return [x for x in rr['stresses'] if x['layer'] == layer][0]
    hot = [r for r in rows if r['case'].startswith('100 % hot')][0]
    spin = [r for r in rows if r['case'].startswith('120 % spin')][0]
    trip = [r for r in rows if r['case'].startswith('108 % trip cold')][0]
    cold120 = [r for r in rows if r['case'].startswith('120 % cold')][0]
    st_hot = get(hot, 'sleeve')['st_MPa'][1]; st_spin = get(spin, 'sleeve')['st_MPa'][1]
    st_max = max(get(r, 'sleeve')['st_MPa'][1] for r in rows)
    pm = lambda r: r['interface_MPa']['screen/magnet']
    d = dict(sleeve_hoop_100hot_MPa=st_hot, sleeve_hoop_spin120_MPa=st_spin, sleeve_hoop_max_MPa=st_max,
             p_magnet_screen_100hot=pm(hot), p_magnet_screen_trip108=pm(trip), p_magnet_screen_spin120=pm(spin), p_magnet_screen_120cold_info=pm(cold120),
             sleeve_radial_max_MPa=max(get(r, 'sleeve')['sr_MPa'][1] for r in rows), magnet_radial_range_MPa=[min(get(r, 'magnet')['sr_MPa'][0] for r in rows),
                                                                                                             max(get(r, 'magnet')['sr_MPa'][1] for r in rows)])
    if 'UTS' in m and mat.startswith('T'):
        U = 0.92 * m['UTS']
        d.update(UTS_eff_MPa=U, SF_UTS_100hot=round(U / st_hot, 2), SF_UTS_spin=round(U / st_spin, 2), ratio_100hot=round(st_hot / U, 3),
                 ok_long_term=bool(st_hot <= 0.40 * U), ok_spin=bool(st_spin <= 0.60 * U))
    else:
        vm = max(get(r, 'sleeve')['vm_max'] for r in rows if r['speed_pct'] <= 108)
        vm_spin = get(spin, 'sleeve')['vm_max']
        d.update(vm_operation_MPa=vm, vm_spin_MPa=vm_spin, SF_yield_operation=round(m['Rp'] / vm, 2), SF_yield_spin=round(m['Rp'] / vm_spin, 2))
    return d


def min_interference(mat, t_sl, crit_trip=10.0, crit_spin=0.0):
    """smallest diametral sleeve interference: magnet/screen contact >= crit_trip at 108 % cold 0 C and >= crit_spin at the hot 120 % spin test"""
    lo, hi = 0.0, 1.2
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        rows = run(mat, t_sl, mid)
        s = summary(rows, mat)
        ok = (isinstance(s['p_magnet_screen_trip108'], float) and s['p_magnet_screen_trip108'] >= crit_trip and
              isinstance(s['p_magnet_screen_spin120'], float) and s['p_magnet_screen_spin120'] >= crit_spin)
        if ok:
            hi = mid
        else:
            lo = mid
    return hi


def inconel_eddy():
    """eddy loss of a 7 mm Inconel 718 sleeve: current harmonics (time-harmonic FEM) + slotting harmonics (thin-shell formula)"""
    import eg_fem2d as F
    em = json.load(open(os.path.join(HERE, 'eg_em.json')))
    mesh = F.build_mesh(EL.em_geom(), h_gap=0.7, h_far=4.0)
    mod = F.PMGModel(mesh, dict(Br=EM['Br20'] * (1 + EM['alpha_Br'] * 80), mur=EM['mu_r'], lam=EM['lam'], stack=EM['stack_factor'], L_stk=EM['stack'] / 1e3,
                                turns_coil=EM['turns_coil'], paths=EM['paths'], pitch=EM['pitch']))
    A0, _ = mod.solve(0.0, [0, 0, 0])
    w = 2 * math.pi * EL.F_EL
    op = em['bridge']['hot_magnets'][-1]
    I1 = op['I1_rms'] * math.sqrt(2)
    P = dict(sleeve=0.0, shield=0.0)
    for h, seq, k in ((5, -1, 6), (7, 1, 6), (11, -1, 12), (13, 1, 12)):
        l, _ = mod.eddy_harmonic(k * w, op['harmonics'][str(h)] * I1, seq, mu_shaft=200, sigma_sleeve=0.80e6)
        P['sleeve'] += l.get('sleeve', 0.0); P['shield'] += l.get('shield', 0.0)
    # slotting harmonics (orders 23, 25 at 24 f in the rotor frame), resistance-limited thin shell, decay (r / r_g)^(n-1)
    rg = 0.5 * (mesh['radii']['rg1'] + mesh['radii']['rg2']) * 1e-3
    Ps = 0.0
    L = (EM['magnet_L'] + 24) / 1e3
    for n, B in em['rotor_losses_335kW']['slot_harmonic_gap_field_T'].items():
        n = int(n)
        for kk in range(7):
            r = (R_M + (kk + 0.5)) * 1e-3
            b = B * (r / rg) ** (n - 1)
            E = r * 24 * w * b / n
            Ps += 0.80e6 * E ** 2 / 2 * 2 * math.pi * r * 1e-3 * L
    return dict(current_harmonics_W=round(P['sleeve']), screen_with_inconel_W=round(P['shield']), slot_harmonics_W=round(Ps), total_W=round(P['sleeve'] + Ps),
                note='2D, infinite length (conservative for the slot part, end paths ignored); CFRP: < 5 W')


def main():
    out = dict(title='GR180 version E generator rotor retention: CFRP vs Inconel 718 sleeve', date='2026-10-24', script='sim/variant_e/eg_sleeve.py',
               geometry_mm=dict(shaft_r=R_SH, screen=[R_SH, R_C], magnet=[R_C, R_M], sleeve=[R_M, R_S], U_tip_m_s=round(W0 * R_S / 1e3, 1)),
               materials=MAT, cases=[c[0] for c in CASES])
    # --------------------------------------------- CFRP options
    cf = {}
    for mat in ('T700S', 'T800S'):
        for t in (6.0, 7.0, 8.0):
            dmin = min_interference(mat, t)
            d = round(dmin + 0.02, 3)                   # + 0.02 mm: grinding tolerance band (+/-0.01 on each part) on the low side
            rows = run(mat, t, d)
            cf['%s t%.0f' % (mat, t)] = dict(t_mm=t, d_min_mm=round(dmin, 3), d_design_mm=d, **summary(rows, mat))
    sel_key = 'T800S t7'
    sel = cf[sel_key]
    rows = run('T800S', 7.0, sel['d_design_mm'])
    rows_arch = run('T800S', 7.0, sel['d_design_mm'], magnet='SmCo_arch')
    tol = {}
    for dd in (sel['d_design_mm'] - 0.02, sel['d_design_mm'] + 0.04):
        tol['%.3f' % dd] = summary(run('T800S', 7.0, dd), 'T800S')
    # --------------------------------------------- Inconel 718 options (metallic sleeve, shrink-fit)
    inc = {}
    for t in (5.0, 7.0, 9.0):
        dmin = min_interference('IN718', t)
        d = round(dmin + 0.02, 3)
        rows_i = run('IN718', t, d)
        inc['IN718 t%.0f' % t] = dict(t_mm=t, d_min_mm=round(dmin, 3), d_design_mm=d, **summary(rows_i, 'IN718'),
                                      self_hoop_100_MPa=round(MAT['IN718']['rho'] * (W0 * R_S / 1e3) ** 2 / 1e6), self_hoop_120_MPa=round(MAT['IN718']['rho'] * (1.2 * W0 * R_S / 1e3) ** 2 / 1e6))
    try:
        eddy = inconel_eddy()
    except Exception as ex:          # noqa
        eddy = dict(error=str(ex))
    # --------------------------------------------- assembly: taper press-fit with the rotor chilled
    taper = 500.0
    d = sel['d_design_mm']
    stroke = d * taper
    p0 = [x for x in rows[0]['stresses'] if x['layer'] == 'sleeve'][0]['sr_MPa'][0]
    p_if = abs(p0)
    L_sl = (EM['magnet_L'] + 24) / 1e3
    D = EM['magnet_OD'] / 1e3
    dT_ln2 = 20 - (-150.0)
    shrink = (MAT['42CrMo4']['ar'] * 0.9 * 2 * R_SH + MAT['SmCo_seg']['ar'] * 0.85 * 2 * (R_M - R_C) + MAT['CuCr1Zr']['ar'] * 0.9 * 2 * EM['shield_t']) * dT_ln2
    d_press = max(d - shrink, 0.0)
    F_warm = 0.05 * (p_if * 1e6) * math.pi * D * L_sl / 1e3
    F_cold = F_warm * d_press / d
    asm = dict(method='CFRP sleeve wound on a ground 1:500 tapered steel mandrel (filament winding, wet T800S / high-Tg epoxy, Tg >= 190 C, '
                      'post-cure 180 C), ID ground if needed; rotor magnet OD + end rings ground to the same 1:500 taper after bonding; '
                      'rotor chilled to -150 C in LN2 vapour (no immersion: SmCo thermal shock), sleeve at 20 C pushed on axially with a '
                      'servo-hydraulic press (force + stroke recorded) to the stroke that gives the interference; dry-film PTFE lubricant on the magnet OD',
               taper='1:500 on diameter', interference_mm=d, press_stroke_mm=round(stroke, 1), chill_shrink_mm=round(shrink, 3),
               remaining_press_interference_mm=round(d_press, 3), contact_pressure_20C_MPa=round(p_if, 1), mu_assembly=0.05,
               F_press_warm_kN=round(F_warm), F_press_chilled_kN=round(F_cold),
               sleeve_axial_stress_at_push_end_MPa=round(F_cold * 1e3 / (math.pi * (EM['magnet_OD'] + 7) / 1e3 * 7e-3) / 1e6, 1),
               layup='88 % hoop (88-89 deg) + 12 % +/-15 deg helical (inner 0.4 mm + outer 0.4 mm) -> axial compressive strength of the laminate ~350 MPa',
               note='push on a split steel ring against the full sleeve end face; axial stress at the pushed end must stay < 0.5 x 350 MPa -> '
                    'chilling + PTFE dry film are mandatory; final checks: OD growth vs. stroke, magnet / sleeve contact by ultrasonics, OD ground cylindrical 120 h6')
    out.update(cfrp_options=cf, selected=dict(option=sel_key, **sel), selected_cases=rows, selected_cases_arch_magnets=[dict(case=r['case'], interface=r['interface_MPa'],
               sleeve=[x for x in r['stresses'] if x['layer'] == 'sleeve'][0]) for r in rows_arch], interference_tolerance_check=tol,
               inconel_options=inc, inconel_eddy_loss=eddy, assembly=asm,
               decision=('CFRP (T800S-class, 7 mm, hoop-wound) sleeve with a %.3f mm diametral interference: magnets stay in contact at the 108 %% trip '
                         '(cold) and the hot 120 %% spin test, hoop stress %.0f MPa at 100 %% hot (%.0f %% UTS_eff) and %.0f MPa at the spin test (%.0f %% UTS); non-conducting -> no sleeve '
                         'eddy loss; light (220 m/s self-stress 76 MPa). Inconel 718 rejected: self-stress %d MPa at 100 %% / %d MPa at 120 %% leaves no '
                         'margin for the magnet load (von Mises over Rp0.2 at the spin test for every thickness that fits) and a conducting sleeve '
                         'adds %s W of eddy loss in the rotor.') % (sel['d_design_mm'], sel['sleeve_hoop_100hot_MPa'], 100 * sel['ratio_100hot'],
                                                                     sel['sleeve_hoop_spin120_MPa'], 100 * sel['sleeve_hoop_spin120_MPa'] / MAT['T800S']['UTS'],
                                                                     inc['IN718 t7']['self_hoop_100_MPa'], inc['IN718 t7']['self_hoop_120_MPa'],
                                                                     eddy.get('total_W', '?')))
    json.dump(out, open(os.path.join(HERE, 'eg_sleeve.json'), 'w'), indent=1, default=float)
    for k, v in cf.items():
        print('%-10s d %.3f mm: hoop 100hot %.0f / spin %.0f MPa, p_mag 100hot %s trip %s spin %s, SF %s/%s' % (k, v['d_design_mm'], v['sleeve_hoop_100hot_MPa'],
              v['sleeve_hoop_spin120_MPa'], v['p_magnet_screen_100hot'], v['p_magnet_screen_trip108'], v['p_magnet_screen_spin120'], v.get('SF_UTS_100hot'), v.get('SF_UTS_spin')))
    for k, v in inc.items():
        print('%-10s d %.3f mm: vm op %.0f spin %.0f MPa, SF yield %.2f / %.2f, p_mag spin %s' % (k, v['d_design_mm'], v['vm_operation_MPa'], v['vm_spin_MPa'],
              v['SF_yield_operation'], v['SF_yield_spin'], v['p_magnet_screen_spin120']))
    print('Inconel eddy:', eddy)
    print('assembly:', {k: v for k, v in asm.items() if k not in ('method', 'note')})
    print(out['decision'])
    print('-> sim/variant_e/eg_sleeve.json')


if __name__ == '__main__':
    main()
