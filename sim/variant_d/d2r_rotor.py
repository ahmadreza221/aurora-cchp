# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy"]
# ///
"""GR180 version D2 - rotor & bearings check (D2R): coupled beam model of the ENGINE rotor (new continuous shaft d10 journals,
clamped d16 body sleeve, d18 stub, compressor, bought turbine wheel) and the GENERATOR rotor (PMG on its own shaft, integral
d6 x 58 quill) joined at the crowned-hex coupling (pin: shear, no moment), four 10x22x6 hybrid bearings on squeeze-film
dampers 1-2 N/um.  Same method as sim/gr180_rotor.py (Euler-Bernoulli FE + rotary inertia + gyroscopics), plus damped
eigenvalues at 115k with an estimated SFD damping, axial thrust, labyrinth leakage, bearing loads/life, quill and shaft stress.

Run:  uv run sim/variant_d/d2r_rotor.py   ->  sim/variant_d/d2r_rotor.json
Geometry: cad/variant_d/d2r_layout.py (ENG mm).  Estimates are marked est; replace with supplier data / tests.
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_d'))
import d2r_layout as L                                                            # noqa: E402

E_ST, RHO_ST = 205e9, 7850.0
E_IN718, RHO_IN718 = 200e9, 8190.0
RHO_SMCO = 8400.0
MM = 1e-3


# ------------------------------------------------------------------ rotor description: segments (x0, x1 [mm], ro, ri [mm], E, rho, Efac)
def engine_rotor(sleeve_fac=0.7, wheel_m=0.45, clamped=False):
    seg = []
    for name, x0, x1, r in L.SHAFT:
        seg.append((x0, x1, r, 0.0, E_ST, RHO_ST, 1.0))
    if clamped:                                                                  # compressor hub stiffens its seat (judgement)
        seg.append((L.COMP['x0'], 3.3, 6.5, 5.0, E_ST, 1.0, 1.0))
    s = L.SLEEVE
    seg.append((s['x0'], s['x1'], s['ro'], s['ri'], E_ST, RHO_ST, sleeve_fac))  # clamped body sleeve (tie-bolt stack)
    seg.append((133.0, 140.0, 11.0, 0.0, E_ST, 300.0, 1.0))                      # wheel hub (mass in the lumped wheel; token density)
    seg.append((140.0, 145.3, 9.0, 0.0, E_ST, 300.0, 1.0))
    # lumped (mass kg, x mm, Ip, It)
    ir = 0.004                                                                    # 71900 inner ring + half the balls (est)
    disks = {'compressor': (L.COMP['mass'], L.COMP['x_cg'], L.COMP['Ip'], L.COMP['It']),
             'clamp_nut': (0.0062, -40.0, 1.8e-7, 1.4e-7), 'washer': (0.0007, -35.5, 3e-8, 2e-8), 'shim': (0.0003, 3.55, 1e-9, 1e-9),
             'brg_IR_front': (ir, L.X_BF, 1.6e-7, 1.0e-7), 'brg_IR_rear': (ir, L.X_BR, 1.6e-7, 1.0e-7),
             'turbine_wheel': (wheel_m, 145.3, 1.73e-4 * wheel_m / 0.416, 1.32e-4 * wheel_m / 0.416)}
    return seg, disks


def generator_rotor(sleeve='carbon', clamp_fac=0.7):
    seg = []
    for name, x0, x1, r in L.GSHAFT:
        ri = 3.3 if 'socket' in name else 0.0
        seg.append((x0, x1, r, ri, E_ST, RHO_ST, 1.0))
    for name, x0, x1, ri, ro in L.GCLAMP:
        seg.append((x0, x1, ro, ri, E_ST, RHO_ST, clamp_fac if 'spacer' in name else 0.0))
    G = L.GEN
    c0, c1 = G['carrier']
    seg.append((c0, c1, G['carrier_r'][1], G['carrier_r'][0], E_ST, RHO_ST, clamp_fac))     # magnet carrier (clamped stack)
    m0, m1 = G['magnet']; ec = G['endcap']
    seg.append((m0, m1, G['magnet_r'][1], G['magnet_r'][0], 120e9, RHO_SMCO, 0.0))   # SmCo: mass only (segmented, no bending)
    if sleeve == 'inconel':
        seg.append((m0 - ec, m1 + ec, G['sleeve_r'][1], G['sleeve_r'][0], E_IN718, RHO_IN718, 0.5))
    else:                                                                             # hoop-wound carbon: axial E ~15 GPa
        seg.append((m0 - ec, m1 + ec, G['sleeve_r'][1], G['sleeve_r'][0], 15e9, 1600.0, 1.0))
    seg.append((m0 - ec, m0, G['sleeve_r'][0], G['magnet_r'][0], 110e9, 4430.0, 0.5))   # Ti end rings
    seg.append((m1, m1 + ec, G['sleeve_r'][0], G['magnet_r'][0], 110e9, 4430.0, 0.5))
    ir = 0.004
    disks = {'brg_IR_front': (ir, L.X_GF, 1.6e-7, 1.0e-7), 'brg_IR_rear': (ir, L.X_GR, 1.6e-7, 1.0e-7)}
    return seg, disks


def mesh(seg, disks, extra_x, h=4.0):
    xs = set()
    for s in seg:
        xs.update([s[0], s[1]])
    xs.update(round(d[1], 3) for d in disks.values())
    xs.update(extra_x)
    xs = sorted(xs)
    fine = []
    for a, b in zip(xs[:-1], xs[1:]):
        n = max(1, int(math.ceil((b - a) / h)))
        fine += [a + (b - a) * k / n for k in range(n)]
    return np.array(fine + [xs[-1]])


def assemble(seg, disks, xn):
    nn = len(xn); nd = 2 * nn
    K = np.zeros((nd, nd)); M = np.zeros((nd, nd)); P = np.zeros((nd, nd))
    for e in range(nn - 1):
        a, b = xn[e], xn[e + 1]; xm = 0.5 * (a + b); Lm = (b - a) * MM
        EI = 0.0; mA = 0.0; mI = 0.0
        for (x0, x1, ro, ri, E, rho, fac) in seg:
            if x0 <= xm <= x1:
                I = math.pi / 4 * ((ro * MM) ** 4 - (ri * MM) ** 4); A = math.pi * ((ro * MM) ** 2 - (ri * MM) ** 2)
                EI += E * I * fac; mA += rho * A; mI += rho * I
        if EI <= 0:
            EI = E_ST * math.pi / 4 * (3e-3) ** 4
        L_ = Lm
        k = EI / L_ ** 3 * np.array([[12, 6 * L_, -12, 6 * L_], [6 * L_, 4 * L_ * L_, -6 * L_, 2 * L_ * L_],
                                      [-12, -6 * L_, 12, -6 * L_], [6 * L_, 2 * L_ * L_, -6 * L_, 4 * L_ * L_]])
        m = mA * L_ / 420 * np.array([[156, 22 * L_, 54, -13 * L_], [22 * L_, 4 * L_ * L_, 13 * L_, -3 * L_ * L_],
                                      [54, 13 * L_, 156, -22 * L_], [-13 * L_, -3 * L_ * L_, -22 * L_, 4 * L_ * L_]])
        mr = mI / (30 * L_) * np.array([[36, 3 * L_, -36, 3 * L_], [3 * L_, 4 * L_ * L_, -3 * L_, -L_ * L_],
                                        [-36, -3 * L_, 36, -3 * L_], [3 * L_, -L_ * L_, -3 * L_, 4 * L_ * L_]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += k; M[np.ix_(idx, idx)] += m + mr; P[np.ix_(idx, idx)] += 2 * mr
    for n, (m_, x, Ip, It) in disks.items():
        i = int(np.argmin(abs(xn - x)))
        M[2 * i, 2 * i] += m_; M[2 * i + 1, 2 * i + 1] += It; P[2 * i + 1, 2 * i + 1] += Ip
    return K, M, P


def system(kb=1e6, cb=300.0, sleeve_fac=0.7, wheel_m=0.45, gen_sleeve='carbon', gen_clamp_fac=0.7, pin=True, clamped=False):
    se, de = engine_rotor(sleeve_fac, wheel_m, clamped)
    sg, dg = generator_rotor(gen_sleeve, gen_clamp_fac)
    x_pin = 0.5 * (L.QUILL['hex'][0] + L.QUILL['hex'][1])
    xe = mesh(se, de, [L.X_BF, L.X_BR, x_pin])
    xg = mesh(sg, dg, [L.X_GF, L.X_GR, x_pin])
    Ke, Me, Pe = assemble(se, de, xe)
    Kg, Mg, Pg = assemble(sg, dg, xg)
    ng, ne = Kg.shape[0], Ke.shape[0]
    n = ng + ne
    K = np.zeros((n, n)); M = np.zeros((n, n)); P = np.zeros((n, n)); C = np.zeros((n, n))
    K[:ng, :ng] = Kg; M[:ng, :ng] = Mg; P[:ng, :ng] = Pg
    K[ng:, ng:] = Ke; M[ng:, ng:] = Me; P[ng:, ng:] = Pe
    bearings = {}
    for tag, xb, off, xs_ in (('gen_front', L.X_GF, 0, xg), ('gen_rear', L.X_GR, 0, xg), ('core_front', L.X_BF, ng, xe), ('core_rear', L.X_BR, ng, xe)):
        i = off + 2 * int(np.argmin(abs(xs_ - xb)))
        K[i, i] += kb; C[i, i] += cb; bearings[tag] = i
    if pin:                                                                       # crowned hex: lateral tie, rotations free
        ig = 2 * int(np.argmin(abs(xg - x_pin))); ie = ng + 2 * int(np.argmin(abs(xe - x_pin)))
        kp = 5e8
        K[ig, ig] += kp; K[ie, ie] += kp; K[ig, ie] -= kp; K[ie, ig] -= kp
    X = np.concatenate([xg, xe]); owner = ['gen'] * len(xg) + ['eng'] * len(xe)
    return K, M, P, C, X, owner, bearings


def criticals(K, M, P, X, owner, n_modes=8):
    w2, Vv = np.linalg.eig(np.linalg.solve(M - P, K))
    ok = (np.abs(np.imag(w2)) < 1e-6 * np.abs(w2)) & (np.real(w2) > 0)
    w2, Vv = np.real(w2[ok]), np.real(Vv[:, ok]); o = np.argsort(w2)[:n_modes]
    out = []
    for i in o:
        rpm = math.sqrt(w2[i]) * 60 / (2 * math.pi)
        tr = np.abs(Vv[0::2, i]); j = int(np.argmax(tr))
        sh = Vv[0::2, i] / Vv[2 * j, i]
        eng = float(np.sum(np.abs(sh[[k for k in range(len(owner)) if owner[k] == 'eng']]) ** 2))
        gen = float(np.sum(np.abs(sh[[k for k in range(len(owner)) if owner[k] == 'gen']]) ** 2))
        out.append(dict(rpm=round(rpm), x_max_mm=round(float(X[j]), 1), rotor=owner[j], eng_share=round(eng / (eng + gen), 2)))
    return out


def damped(K, M, P, C, Om, X, owner, nmax=8):
    n = K.shape[0]
    Mi = np.linalg.inv(M)
    A = np.block([[np.zeros((n, n)), np.eye(n)], [-Mi @ K, -Mi @ (C - 1j * Om * P)]])
    s, Vv = np.linalg.eig(A)
    res = []
    for i in range(len(s)):
        w = s[i].imag
        if w <= 1.0:
            continue
        rpm = w * 60 / (2 * math.pi)
        if rpm > 400000:
            continue
        zeta = -s[i].real / abs(s[i])
        tr = np.abs(Vv[:n:2, i]); j = int(np.argmax(tr))
        res.append(dict(rpm=round(rpm), zeta=round(float(zeta), 3), x_max_mm=round(float(X[j]), 1), rotor=owner[j]))
    res.sort(key=lambda d: d['rpm'])
    return res[:nmax]


# ------------------------------------------------------------------ axial thrust (gauge to the bearing-chamber pressure)
def thrust():
    """Rotor axial force [N], + = rearward (towards the turbine). Pressures bar abs, design point 115k, 15 C intake."""
    w = 115000 * 2 * math.pi / 60
    pch = 1.05e5                                                    # bearing chamber (vented to tank + breather)
    # compressor (v13A: tip r 37, inducer tip r 28.1, PR 3.1, impeller-exit static ~2.15 bar, inlet static 0.92 bar)
    r2, r1t, rseal_c = 37e-3, 28.1e-3, 11.2e-3
    p1, p2s, ma, c1x = 0.92e5, 2.15e5, 0.395, 150.0
    rho2 = p2s / (287 * 400)
    def integ(f, a, b, n=200):
        h = (b - a) / n
        return sum(f(a + (k + 0.5) * h) * 2 * math.pi * (a + (k + 0.5) * h) * h for k in range(n))
    F_front = integ(lambda r: p1 - pch, 0, r1t) + integ(lambda r: p1 + (p2s - p1) * (r - r1t) / (r2 - r1t) - pch, r1t, r2) + ma * c1x
    pb = lambda r: p2s - 0.5 * rho2 * (0.45 * w) ** 2 * (r2 ** 2 - r ** 2)          # back-face cavity, core swirl ratio 0.45
    F_back_c = integ(lambda r: pb(r) - pch, rseal_c, r2)
    F_c = F_front - F_back_c                                                         # + rearward
    # turbine (meanline: p4 1.83 bar, p6 1.00 bar, c6 297 m/s, 0.40 kg/s); back face cavity fed by buffer air, vented into the rotor inlet
    T = json.load(open(os.path.join(HERE, 'd2r_turbine.json')))['meanline']
    r4, r6t, rs_t = L.WHEEL['D4'] / 2e3, L.WHEEL['D6t'] / 2e3, 7.6e-3              # rear labyrinth on the d14 runner
    p4, p6, c6, m = T['rotor_inlet']['P4_bar'] * 1e5, T['rotor_exit']['P6_bar'] * 1e5, T['rotor_exit']['c6_m_s'], T['m_gas_kg_s']
    rho4 = T['rotor_inlet']['rho4']
    pbt = lambda r: p4 + 0.04e5 - 0.5 * rho4 * (0.5 * w) ** 2 * (r4 ** 2 - r ** 2)
    F_back_t = integ(lambda r: pbt(r) - pch, rs_t, r4)
    F_front_t = integ(lambda r: p6 - pch, 0, r6t) + integ(lambda r: p6 + (p4 - p6) * (r - r6t) / (r4 - r6t) - pch, r6t, r4) + m * c6
    F_t = F_back_t - F_front_t
    # nose: drive cup / quill float friction (crowned hex sliding, mu 0.15 on the drive force 2.12 N.m / r 3.5 mm)
    F_quill = 0.15 * 2.12 / 3.0e-3 / 2
    net = F_c + F_t
    # sensitivity: turbine back-face cavity pressure raised by the buffer-air orifices (thrust trim), compressor cavity swirl
    sens = {}
    for dp in (0.0, 0.05e5, 0.10e5, 0.20e5):
        Fb = integ(lambda r: pbt(r) + dp - pch, rs_t, r4 - 2e-3) + integ(lambda r: pbt(r) - pch, r4 - 2e-3, r4)
        sens['turbine_cavity_+%.2fbar' % (dp / 1e5)] = round(F_c + Fb - F_front_t)
    for k in (0.35, 0.55):
        pbk = lambda r: p2s - 0.5 * rho2 * (k * w) ** 2 * (r2 ** 2 - r ** 2)
        sens['compressor_cavity_swirl_%.2f' % k] = round(F_front - integ(lambda r: pbk(r) - pch, rseal_c, r2) + F_t)
    return dict(F_compressor_N=round(F_c), F_turbine_N=round(F_t), net_N=round(net), sensitivity_net_N=sens,
                quill_slip_force_N=round(F_quill), direction='rearward (+x)' if net > 0 else 'forward (-x)',
                design='keep the net rotor thrust FORWARD (-x) 20..80 N at all points: front 71900 is the locating bearing for forward '
                       'thrust (OR -> cartridge front lip -> pressed + Loctite seal/retainer ring R-131), the rear spring (40 N) pushes the '
                       'shaft forward too, so both bearings stay loaded; trim on the rig with the 6 x M4 orifice screws in T-116 '
                       '(turbine back-face cavity pressure) and measure with a load washer behind the front cartridge',
                note='p_chamber 1.05 bar; compressor back-face seal r 11.2 (front labyrinth), turbine back-face seal r 7.6; '
                     'cavity swirl 0.45/0.5 of rotor speed (est). Trim with the turbine back-face seal radius / back-face scallop if test thrust differs')


# ------------------------------------------------------------------ labyrinth leakage (Martin / Egli, straight-through)
def lab(D_mm, c_mm, n, p1, p2, T, kc=1.3):
    A = math.pi * D_mm * c_mm * 1e-6
    return 0.65 * kc * A * math.sqrt((p1 ** 2 - p2 ** 2) / (n * 287 * T))


def main():
    out = dict(title='GR180 D2R rotor & bearings check', date='2026-10-23', script='sim/variant_d/d2r_rotor.py',
               model='coupled engine + generator beam FE, gyroscopics, crowned-hex pin at x %.1f' % (0.5 * sum(L.QUILL['hex'])))
    # masses
    for tag, (seg, dk) in (('engine', engine_rotor()), ('generator', generator_rotor())):  # noqa
        ms = sum(rho * math.pi * ((ro * MM) ** 2 - (ri * MM) ** 2) * (x1 - x0) * MM for (x0, x1, ro, ri, E, rho, f) in seg)
        md = sum(d[0] for d in dk.values())
        out['mass_%s_kg' % tag] = round(ms + md, 3)
    print('rotor masses: engine %.3f kg, generator (incl. quill) %.3f kg' % (out['mass_engine_kg'], out['mass_generator_kg']))
    cases = {}
    print('\nForward synchronous critical speeds [rpm] (x of max deflection, rotor):')
    for lab_, kw in (('base 1 N/um', dict(kb=1e6)), ('base 2 N/um', dict(kb=2e6)), ('stiff 10 N/um (ref)', dict(kb=10e6)),
                     ('1 N/um, quill end free', dict(kb=1e6, pin=False)), ('2 N/um, stacks loose (fac 0.3)', dict(kb=2e6, sleeve_fac=0.3, gen_clamp_fac=0.3)),
                     ('2 N/um, stacks solid (fac 1)', dict(kb=2e6, sleeve_fac=1.0, gen_clamp_fac=1.0)), ('2 N/um, wheel 0.55 kg', dict(kb=2e6, wheel_m=0.55)),
                     ('2 N/um, PMG Inconel sleeve', dict(kb=2e6, gen_sleeve='inconel')), ('2 N/um, compressor hub clamped', dict(kb=2e6, clamped=True)),
                     ('1 N/um, stacks loose, wheel 0.55', dict(kb=1e6, sleeve_fac=0.3, gen_clamp_fac=0.3, wheel_m=0.55))):
        K, M, P, C, X, own, br = system(**kw)
        cr = criticals(K, M, P, X, own)
        cases[lab_] = cr
        flag = lambda r: (' !RUN' if abs(r - L.N_RUN) < 0.15 * L.N_RUN else '') + (' !BAND' if L.BAND[0] <= r <= L.BAND[1] else '')
        print('  %-32s %s' % (lab_, ' | '.join('%6.0fk@%s%.0f%s' % (c['rpm'] / 1e3, c['rotor'][0], c['x_max_mm'], flag(c['rpm'])) for c in cr[:7])))
    out['criticals'] = cases
    # margins for the base cases
    marg = {}
    for lab_ in ('base 1 N/um', 'base 2 N/um'):
        cr = [c['rpm'] for c in cases[lab_]]
        above = [c for c in cr if c > L.N_RUN]; below = [c for c in cr if c <= L.N_RUN]
        marg[lab_] = dict(highest_below_run=max(below) if below else None, lowest_above_run=min(above) if above else None,
                          margin_above_pct=round(100 * (min(above) / L.N_RUN - 1), 1) if above else None,
                          margin_below_pct=round(100 * (1 - max(below) / L.N_RUN), 1) if below else None,
                          in_85_95k=[c for c in cr if L.BAND[0] <= c <= L.BAND[1]])
    out['margins'] = marg
    print('\nmargins:', json.dumps(marg))
    # damped eigenvalues at run speed with an SFD damping estimate
    print('\nDamped whirl modes at 115k (SFD c = 300 N s/m each, est):')
    dm = {}
    for kb in (1e6, 2e6):
        K, M, P, C, X, own, br = system(kb=kb, cb=300.0)
        d = damped(K, M, P, C, L.N_RUN * 2 * math.pi / 60, X, own)
        dm['%.0f N/um' % (kb / 1e6)] = d
        print('  %.0f N/um: %s' % (kb / 1e6, ' | '.join('%.0fk z%.3f %s%.0f' % (m['rpm'] / 1e3, m['zeta'], m['rotor'][0], m['x_max_mm']) for m in d)))
    out['damped_115k_c300'] = dm
    out['sfd'] = dict(clearance_mm=L.SFD_C, land_mm=6.0, journal_D_mm=L.CART_OD, oil='VG32 at ~70 C, mu ~0.012 Pa s',
                      c_short_open_Ns_m=round(0.012 * math.pi * 14e-3 * (6e-3) ** 3 / (0.1e-3) ** 3),
                      c_sealed_long_Ns_m=round(12 * math.pi * 0.012 * (14e-3) ** 3 * 6e-3 / (0.1e-3) ** 3),
                      used_Ns_m=300, centring='2 x FKM O-ring 1.5 mm CS per cartridge (k ~1-2 N/um, measure on a rig), anti-rotation pin')
    # thrust
    th = thrust(); out['axial_thrust'] = th
    print('\nAxial thrust: compressor %+d N, turbine %+d N, net %+d N (%s); quill slip %d N' % (
        th['F_compressor_N'], th['F_turbine_N'], th['net_N'], th['direction'], th['quill_slip_force_N']))
    # bearing loads and life
    pre = 40.0
    Fa_front = pre + abs(min(th['net_N'], 0))
    C_dyn, C0 = 3000.0, 1300.0                                    # 71900 C hybrid P4 (est from catalogues)
    W_unb = lambda m: m * 9.81 + m * (2.5e-3 * 1e-3 * 1000 / 0.45) * 0  # placeholder (gravity only; unbalance in notes)
    Fr_front = 0.5 * 9.81 * 0.30 + 15; Fr_rear = 9.81 * 0.75 + 25           # static weight share + unbalance (G2.5) est
    def P_eq(Fr, Fa):
        e = 0.43
        return Fr if Fa / max(Fr, 1e-6) <= e else 0.44 * Fr + 1.30 * Fa
    life = {}
    for tag, Fr, Fa in (('core_front', Fr_front, Fa_front), ('core_rear', Fr_rear, pre), ('gen_front', 0.5 * 9.81 * 0.68 + 15, pre),
                        ('gen_rear', 0.5 * 9.81 * 0.68 + 15, pre)):
        Pq = P_eq(Fr, Fa)
        L10 = (C_dyn / Pq) ** 3 * 1e6 / (60 * L.N_RUN)
        life[tag] = dict(Fr_N=round(Fr, 1), Fa_N=round(Fa, 1), P_N=round(Pq, 1), L10_h=round(L10), L10m_aISO4_h=round(4 * L10))
    for Fa in (60.0, 100.0, 140.0):
        Pq = P_eq(Fr_front, Fa)
        life['core_front_if_Fa_%d' % Fa] = dict(Fa_N=Fa, P_N=round(Pq, 1), L10_h=round((C_dyn / Pq) ** 3 * 1e6 / (60 * L.N_RUN)))
    out['bearing_life'] = dict(C_N=C_dyn, preload_N=pre, cases=life, X=0.44, Y=1.30, e=0.43,
                               plan='replace at 8000 h + vibration trend (01 section 2); |net thrust| <= 60 N keeps L10m (aISO 4) >= 10,000 h')
    print('bearings:', {k: (v['P_N'], v['L10_h']) for k, v in life.items()})
    # seals
    seals = dict(core_front=dict(D=22.4, c=0.20, teeth=3, p1=2.0e5, p2=1.05e5, T=420.0),
                 core_rear=dict(D=15.2, c=0.20, teeth=4, p1=2.6e5, p2=1.05e5, T=480.0),
                 gen_front=dict(D=15.2, c=0.25, teeth=3, p1=1.10e5, p2=1.05e5, T=330.0),
                 gen_rear=dict(D=18.6, c=0.25, teeth=3, p1=1.10e5, p2=1.05e5, T=330.0))
    for k, s in seals.items():
        s['leak_g_s'] = round(1e3 * lab(s['D'], s['c'], s['teeth'], s['p1'], s['p2'], s['T']), 2)
    out['seals'] = dict(cases=seals, note='straight-through labyrinths (teeth on the rotor), air buffered: flow always INTO the oil chamber; '
                        'generator chambers buffered with ~5 kPa filtered intake air (pod) so oil mist cannot reach the air gap')
    print('seal leakage g/s:', {k: v['leak_g_s'] for k, v in seals.items()})
    # quill / shafts
    T_gen = 25.5e3 / (L.N_RUN * 2 * math.pi / 60)
    d = L.QUILL['waist_d'] * MM
    tau = 16 * T_gen / (math.pi * d ** 3)
    Lq = (L.QUILL['waist'][1] - L.QUILL['waist'][0]) * MM
    I = math.pi * d ** 4 / 64; mlin = RHO_ST * math.pi * d ** 2 / 4
    f_pp = (math.pi / 2) / Lq ** 2 * math.sqrt(E_ST * I / mlin) * 60
    k_ax = E_ST * math.pi * d ** 2 / 4 / Lq
    T_turb = 85e3 / (L.N_RUN * 2 * math.pi / 60)
    out['quill'] = dict(waist_d_mm=6.0, free_length_mm=round(Lq * 1e3, 1), torque_rated_Nm=round(T_gen, 2), tau_rated_MPa=round(tau / 1e6, 1),
                        tau_fault_x4_MPa=round(4 * tau / 1e6, 1), first_bending_pinned_rpm=round(f_pp), axial_stiffness_N_um=round(k_ax / 1e6, 1),
                        hex='crowned external AF6 x 11.5 on the engine-shaft nose (nitrided) in the internal AF6 socket of the quill hub (nitrided 17-4PH), float +/-0.5 mm',
                        hex_contact_p_MPa_rated=round(T_gen / (0.3 * 5.75e-3 * (6e-3) ** 2) / 1e6, 1), hex_contact_p_MPa_fault=round(4 * T_gen / (0.3 * 5.75e-3 * (6e-3) ** 2) / 1e6, 1))
    out['engine_shaft'] = dict(T_turbine_Nm=round(T_turb, 2), tau_rear_journal_d10_MPa=round(16 * T_turb / (math.pi * 1e-6) / 1e6, 1),
                               clamp_preload_kN=6.0, sigma_M8_thread_root_MPa=round(6e3 / (math.pi / 4 * (6.65e-3) ** 2) / 1e6), sigma_d10_MPa=round(6e3 / (math.pi * 25e-6) / 1e6),
                               compressor_bore='reamed 7 -> 10 H6 (no sleeve): d10 seat = 2.4x the bending stiffness of d8; bore hoop stress +<2 %, rear spigot wall 1.5 mm (r 5..6.49) carries only the clamp',
                               nut_torque_Nm=round(0.2 * 6e3 * 8e-3, 1), compressor_torque_Nm=round(59.5e3 / (L.N_RUN * 2 * math.pi / 60), 2),
                               friction_capacity_Nm=round(6e3 * 0.15 * (6.5e-3 + 5.8e-3), 2),
                               hex_AF6_drive='generator torque enters the shaft through the AF6 hex (never through the nut or the LH thread)')
    print('quill: tau %.0f MPa rated / %.0f fault, bending %.0f rpm, axial %.0f N/um' % (out['quill']['tau_rated_MPa'], out['quill']['tau_fault_x4_MPa'],
                                                                                         f_pp, k_ax / 1e6))
    json.dump(out, open(os.path.join(HERE, 'd2r_rotor.json'), 'w'), indent=1)
    print('-> sim/variant_d/d2r_rotor.json')


if __name__ == '__main__':
    main()
