# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy"]
# ///
"""GR180 version E - rotor & bearings sanity check: coupled beam model of the CORE rotor (shaft d40 journals + clamped
d60 sleeve, TC-class compressor wheel overhung in front, cast turbine wheel overhung at the rear, friction-welded d50
heat dam) and the GENERATOR rotor (integral d80 magnet body, d40 journals, bolted d30 quill) joined at the crowned
AF24 hex (pin: shear, no moment); 4 support stations (core front tandem pair, core rear, generator front, generator
rear) on O-ring-centred squeeze-film dampers.  Same method as sim/variant_d/d2r_rotor.py (Euler-Bernoulli FE, rotary
inertia, gyroscopics, damped eigenvalues), plus axial thrust (trimmed with the compressor back-face seal radius),
bearing loads / L10 life / friction, quill and shaft stresses.

Run:  python3 sim/variant_e/e_rotor.py  ->  sim/variant_e/e_rotor.json
Geometry: cad/variant_e/e_layout.py (ENG mm).  All values are estimates - replace with supplier data and rig tests.
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_e'))
import e_layout as L                                                              # noqa: E402

E_ST, RHO_ST = 205e9, 7850.0
MM = 1e-3
CO = json.load(open(os.path.join(HERE, 'e_compressor.json')))['meanline']
TU = json.load(open(os.path.join(HERE, 'e_turbine.json')))
OM = L.N_RUN * math.pi / 30


def core_rotor(sleeve_fac=0.5, wheel_m=None, comp_m=None):
    seg = [(x0, x1, r, 0.0, E_ST, RHO_ST, 1.0) for (n, x0, x1, r) in L.SHAFT if 'heat_dam' not in n]
    seg.append((240.0, 250.0, 25.0, 15.0, E_ST, RHO_ST, 1.0))                     # hollow heat dam d50/30
    s = L.SLEEVE
    seg.append((s['x0'], s['x1'], s['ro'], s['ri'], E_ST, RHO_ST, sleeve_fac))
    seg.append((250.0, 300.0, 45.0, 0.0, E_ST, 50.0, 1.0))                         # turbine hub stiffness (mass lumped)
    seg.append((-94.0, 30.0, 32.0, 20.0, 72e9, 10.0, 0.3))                         # compressor hub on the seat (partial stiffening)
    wm = wheel_m or L.TURB['mass']; cm = comp_m or L.COMP['mass']
    ir = 0.07
    disks = {'compressor': (cm, L.COMP['x_cg'], L.COMP['Ip'] * cm / L.COMP['mass'], L.COMP['It'] * cm / L.COMP['mass']),
             'nut': (L.NUT['mass'], -103.0, 1.5e-4, 1.0e-4), 'slinger': (L.SLINGER['mass'], 37.5, 1.2e-4, 0.8e-4),
             'brg_IR_front_pair': (2 * ir, L.X_BF, 2.4e-4, 1.6e-4), 'brg_IR_rear': (ir, L.X_BR, 1.2e-4, 0.8e-4),
             'turbine_wheel': (wm, L.TURB['x_cg'], L.TURB['Ip'] * wm / L.TURB['mass'], L.TURB['It'] * wm / L.TURB['mass'])}
    return seg, disks


def gen_rotor(clamp_fac=1.0):
    seg = [(x0, x1, r, 0.0, E_ST, RHO_ST, 1.0) for (n, x0, x1, r) in L.GSHAFT]
    G = L.GEN
    m0, m1 = G['stack']; ec = G['endring']
    seg.append((m0, m1, G['magnet'][1] / 2, G['magnet'][0] / 2, 120e9, 8400.0, 0.0))    # SmCo: mass only (segmented)
    seg.append((m0 - ec, m1 + ec, G['rotor_OD'] / 2, G['magnet'][1] / 2, 15e9, 1600.0, 1.0))  # carbon sleeve (axial E low)
    seg.append((m0 - ec, m0, G['magnet'][1] / 2, G['magnet'][0] / 2, 193e9, 7950.0, 0.3))    # 1.4404 end rings
    seg.append((m1, m1 + ec, G['magnet'][1] / 2, G['magnet'][0] / 2, 193e9, 7950.0, 0.3))
    q = L.QUILL
    seg.append((q['flange'][0], q['flange'][1], q['flange'][2], 0.0, E_ST, RHO_ST, clamp_fac))
    seg.append((q['waist'][0], q['waist'][1], q['waist_d'] / 2, 0.0, E_ST, RHO_ST, 1.0))
    seg.append((q['socket'][0], q['socket'][1], q['socket_OD'] / 2, 12.5, E_ST, RHO_ST, 1.0))
    ir = 0.07
    disks = {'brg_IR_front': (ir, L.X_GF, 1.2e-4, 0.8e-4), 'brg_IR_rear': (ir, L.X_GR, 1.2e-4, 0.8e-4),
             'KM7_nut_speed_wheel': (0.25, -862.0, 1.5e-4, 1.0e-4)}
    return seg, disks


def mesh(seg, disks, extra_x, h=8.0):
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
            EI = E_ST * math.pi / 4 * (10e-3) ** 4
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


X_PIN = 0.5 * (L.QUILL['hex_engage'][0] + L.QUILL['hex_engage'][1])


def system(kb=3e6, cb=3000.0, sleeve_fac=0.5, wheel_m=None, comp_m=None, pin=True, kb_core=None):
    se, de = core_rotor(sleeve_fac, wheel_m, comp_m)
    sg, dg = gen_rotor()
    xe = mesh(se, de, [L.X_BF, L.X_BR, X_PIN])
    xg = mesh(sg, dg, [L.X_GF, L.X_GR, X_PIN])
    Ke, Me, Pe = assemble(se, de, xe)
    Kg, Mg, Pg = assemble(sg, dg, xg)
    ng, ne = Kg.shape[0], Ke.shape[0]
    n = ng + ne
    K = np.zeros((n, n)); M = np.zeros((n, n)); P = np.zeros((n, n)); C = np.zeros((n, n))
    K[:ng, :ng] = Kg; M[:ng, :ng] = Mg; P[:ng, :ng] = Pg
    K[ng:, ng:] = Ke; M[ng:, ng:] = Me; P[ng:, ng:] = Pe
    for tag, xb, off, xs_, kk in (('gen_front', L.X_GF, 0, xg, kb), ('gen_rear', L.X_GR, 0, xg, kb),
                                  ('core_front', L.X_BF, ng, xe, (kb_core or kb) * 1.5), ('core_rear', L.X_BR, ng, xe, kb_core or kb)):
        i = off + 2 * int(np.argmin(abs(xs_ - xb)))
        K[i, i] += kk; C[i, i] += cb
    if pin:
        ig = 2 * int(np.argmin(abs(xg - X_PIN))); ie = ng + 2 * int(np.argmin(abs(xe - X_PIN)))
        kp = 2e9
        K[ig, ig] += kp; K[ie, ie] += kp; K[ig, ie] -= kp; K[ie, ig] -= kp
    X = np.concatenate([xg, xe]); owner = ['gen'] * len(xg) + ['eng'] * len(xe)
    return K, M, P, C, X, owner


def criticals(K, M, P, X, owner, n_modes=8):
    w2, Vv = np.linalg.eig(np.linalg.solve(M - P, K))
    ok = (np.abs(np.imag(w2)) < 1e-6 * np.abs(w2)) & (np.real(w2) > 0)
    w2, Vv = np.real(w2[ok]), np.real(Vv[:, ok]); o = np.argsort(w2)[:n_modes]
    out = []
    for i in o:
        rpm = math.sqrt(w2[i]) * 60 / (2 * math.pi)
        tr = np.abs(Vv[0::2, i]); j = int(np.argmax(tr))
        out.append(dict(rpm=round(rpm), x_max_mm=round(float(X[j]), 1), rotor=owner[j]))
    return out


def damped(K, M, P, C, Om, X, owner, nmax=10):
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
        if rpm > 150000:
            continue
        zeta = -s[i].real / abs(s[i])
        tr = np.abs(Vv[:n:2, i]); j = int(np.argmax(tr))
        res.append(dict(rpm=round(rpm), zeta=round(float(zeta), 3), x_max_mm=round(float(X[j]), 1), rotor=owner[j]))
    res.sort(key=lambda d: d['rpm'])
    return res[:nmax]


# ------------------------------------------------------------------ axial thrust (+ = rearward / +x), gauge to the bearing chamber
def integ(f, a, b, n=300):
    h = (b - a) / n
    return sum(f(a + (k + 0.5) * h) * 2 * math.pi * (a + (k + 0.5) * h) * h for k in range(n))


def thrust(r_sc=L.COMP['r_back_seal'], r_st=L.TURB['r_back_seal'], t=None, scale_c=1.0, speed=1.0, p_ref=1.02e5):
    """compressor: shroud side p1 -> p2 (quadratic in r), inflow momentum, back-face cavity with core swirl 0.5;
    turbine: back-face cavity at p4 + 0.05 bar (buffer air) with swirl 0.5 down to the piston-ring seal, blade side
    p6 -> p4, exducer at p6, exit momentum.  scale_c / speed scale the compressor pressure rise for off-design."""
    t = t or TU['design_770']
    w = OM * speed
    r1t, r1h, r2 = CO['inducer']['D1t_mm'] / 2e3, CO['inducer']['D1h_mm'] / 2e3, CO['impeller']['D2_mm'] / 2e3
    P01 = CO['P01_bar'] * 1e5
    p1 = P01 - 0.5 * 1.10 * CO['inducer']['c1_m_s'] ** 2
    p2 = P01 + (CO['impeller']['P2_bar'] * 1e5 - P01) * scale_c
    rho2 = p2 / (288.9 * (CO['impeller']['T2_C'] + 273.15))
    m = CO['m_kg_s'] * math.sqrt(scale_c)
    F_front = integ(lambda r: p1 - p_ref, 0, r1t) + integ(lambda r: p1 + (p2 - p1) * (r * r - r1t ** 2) / (r2 ** 2 - r1t ** 2) - p_ref, r1t, r2) \
        + m * CO['inducer']['c1_m_s'] * math.sqrt(scale_c)
    pb = lambda r: p2 - 0.5 * rho2 * (0.5 * w) ** 2 * (r2 ** 2 - r ** 2)
    F_back = integ(lambda r: pb(r) - p_ref, r_sc / 1e3, r2)
    F_c = F_front - F_back
    r4, r6t = L.TURB['D4'] / 2e3, L.TURB['D6t'] / 2e3
    p4, p6 = t['rotor_inlet']['P4_bar'] * 1e5, t['P6_bar'] * 1e5
    rho4 = p4 / (292.3 * (t['rotor_inlet']['T4_C'] + 273.15))
    pbt = lambda r: p4 + 0.05e5 - 0.5 * rho4 * (0.5 * w) ** 2 * (r4 ** 2 - r ** 2)
    F_back_t = integ(lambda r: pbt(r) - p_ref, r_st / 1e3, r4)
    F_blade = integ(lambda r: p6 - p_ref, 0, r6t) + integ(lambda r: p6 + (p4 - p6) * (r * r - r6t ** 2) / (r4 ** 2 - r6t ** 2) - p_ref, r6t, r4) \
        + t['m_kg_s'] * t['c6_m_s']
    F_t = F_back_t - F_blade
    return dict(F_compressor_N=round(F_c), F_turbine_N=round(F_t), net_N=round(F_c + F_t))


def trim_seal():
    """compressor back-face seal radius that puts the net thrust at -500 N (forward) at the 770 C design point"""
    lo, hi = 30.0, 125.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if thrust(r_sc=mid)['net_N'] < -500:
            lo = mid                  # larger seal radius -> less back-face area -> less forward force
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ------------------------------------------------------------------ bearings
def P_eq(Fr, Fa, angle='E'):
    if angle == 'E':
        e, X, Y = 0.68, 0.41, 0.87
    else:
        e, X, Y = 0.47, 0.44, 1.19
    return Fr if Fa / max(Fr, 1e-6) <= e else X * Fr + Y * Fa


def L10h(C, P, n=L.N_RUN):
    return (C / P) ** 3 * 1e6 / (60 * n)


def friction_W(Fr, Fa, n=L.N_RUN, nu=12.0, f0=2.0):
    """Palmgren: viscous M0 = 1e-7 f0 (nu n)^(2/3) dm^3, load M1 = f1 P1 dm (N mm), oil jet, VG32 at ~70 C"""
    dm = 0.5 * (L.BRG['d'] + L.BRG['D'])
    M0 = 1e-7 * f0 * (nu * n) ** (2 / 3) * dm ** 3
    P1 = max(3.3 * Fa - 0.1 * Fr, Fr)
    M1 = 0.0007 * P1 * dm
    return (M0 + M1) * 1e-3 * n * math.pi / 30


def static_loads():
    """reaction forces of the two rotors under gravity (rigid beams on 2 supports)"""
    se, de = core_rotor()
    items = [(sum(RHO_ST * math.pi * ((ro * MM) ** 2 - (ri * MM) ** 2) * (x1 - x0) * MM for (x0, x1, ro, ri, E, rho, f) in se if rho > 1000) , 100.0)]
    items += [(d[0], d[1]) for d in de.values()]
    W = sum(m for m, x in items) * 9.81
    Mx = sum(m * 9.81 * x for m, x in items)
    R_rear = (Mx - W * L.X_BF) / (L.X_BR - L.X_BF); R_front = W - R_rear
    sg, dg = gen_rotor()
    gi = [(sum(rho * math.pi * ((ro * MM) ** 2 - (ri * MM) ** 2) * (x1 - x0) * MM for (x0, x1, ro, ri, E, rho, f) in sg), L.GEN['x_g'])]
    gi += [(d[0], d[1]) for d in dg.values()]
    Wg = sum(m for m, x in gi) * 9.81
    Mg = sum(m * 9.81 * x for m, x in gi)
    Rg_rear = (Mg - Wg * L.X_GF) / (L.X_GR - L.X_GF); Rg_front = Wg - Rg_rear
    return dict(core_mass_kg=round(W / 9.81, 2), gen_mass_kg=round(Wg / 9.81, 2), core_front_N=round(R_front), core_rear_N=round(R_rear),
                gen_front_N=round(Rg_front), gen_rear_N=round(Rg_rear))


def main():
    out = dict(title='GR180 version E rotor & bearings check', date='2026-10-23', script='sim/variant_e/e_rotor.py',
               model='coupled core + generator beam FE with gyroscopics, crowned-hex pin at x %.0f, 4 SFD support stations' % X_PIN)
    st = static_loads(); out['static'] = st
    print('rotor masses: core %.1f kg, generator incl. quill %.1f kg; static reactions core F/R %d/%d N, gen F/R %d/%d N' % (
        st['core_mass_kg'], st['gen_mass_kg'], st['core_front_N'], st['core_rear_N'], st['gen_front_N'], st['gen_rear_N']))
    cases = {}
    lo, hi = L.OP_RANGE
    print('\nForward critical speeds [rpm] (x of max deflection, rotor); operating range %.0f-%.0f rpm:' % lo_hi if False else
          '\nForward critical speeds [rpm]; operating range %.0f-%.0f rpm (55-108 %%):' % (lo, hi))
    for lab_, kw in (('SFD 3 N/um (base)', dict(kb=3e6)), ('SFD 1.5 N/um', dict(kb=1.5e6)), ('SFD 6 N/um', dict(kb=6e6)),
                     ('rigid 50 N/um (ref)', dict(kb=50e6)), ('3 N/um, sleeve loose 0.2', dict(kb=3e6, sleeve_fac=0.2)),
                     ('3 N/um, turbine wheel 20 kg', dict(kb=3e6, wheel_m=20.0)), ('3 N/um, no quill pin', dict(kb=3e6, pin=False))):
        K, M, P, C, X, own = system(**kw)
        cr = criticals(K, M, P, X, own)
        cases[lab_] = cr
        flag = lambda r: ' !OPR' if lo <= r <= hi else ''
        print('  %-30s %s' % (lab_, ' | '.join('%5.1fk@%s%.0f%s' % (c['rpm'] / 1e3, c['rotor'][0], c['x_max_mm'], flag(c['rpm'])) for c in cr[:8])))
    out['criticals'] = cases
    marg = {}
    for lab_ in ('SFD 3 N/um (base)', 'SFD 1.5 N/um', 'SFD 6 N/um'):
        cr = [c['rpm'] for c in cases[lab_]]
        above = [c for c in cr if c > hi]; below = [c for c in cr if c < lo]; inside = [c for c in cr if lo <= c <= hi]
        marg[lab_] = dict(highest_below_55pct=max(below) if below else None, lowest_above_108pct=min(above) if above else None,
                          margin_above_run_pct=round(100 * (min(above) / L.N_RUN - 1), 1) if above else None, inside_operating_range=inside)
    out['margins'] = marg
    print('margins:', json.dumps(marg))
    dm = {}
    for kb in (3e6,):
        K, M, P, C, X, own = system(kb=kb, cb=3000.0)
        d = damped(K, M, P, C, OM, X, own)
        dm['%.0f N/um' % (kb / 1e6)] = d
        print('damped at 35k (c 3000 N s/m per SFD): ' + ' | '.join('%.1fk z%.3f %s%.0f' % (m['rpm'] / 1e3, m['zeta'], m['rotor'][0], m['x_max_mm']) for m in d))
    out['damped_35k'] = dm
    R = L.CART['OD'] / 2e3; Ld = L.CART['land'] / 1e3; c = L.CART['clearance'] / 1e3; mu = 0.012
    out['sfd'] = dict(cartridge_OD_mm=L.CART['OD'], land_mm=L.CART['land'], clearance_mm=L.CART['clearance'],
                      c_short_open_Ns_m=round(mu * math.pi * R * Ld ** 3 / c ** 3), c_sealed_long_Ns_m=round(12 * math.pi * mu * R ** 3 * Ld / c ** 3),
                      used_Ns_m=3000, centring='2 x FKM O-rings 84 x 3 per cartridge (k ~3 N/um, measure), anti-rotation pin, jet + SFD feed from one gallery')
    # thrust
    r_sc = L.COMP['r_back_seal']
    r_trim = trim_seal()
    th = thrust(r_sc=r_sc)
    th850 = thrust(r_sc=r_sc, t=TU['peak_850'], scale_c=(4.093 - 1.005) / (4.002 - 1.005))
    th_idle = thrust(r_sc=r_sc, scale_c=0.25, speed=0.55, t=dict(TU['design_770'], rotor_inlet=dict(TU['design_770']['rotor_inlet'], P4_bar=1.30, T4_C=480.0),
                                                                    P6_bar=1.01, m_kg_s=1.6, c6_m_s=110.0))
    sens = {}
    for lab_, kw in (('compressor cavity swirl 0.4', None), ('seal radius -5 mm', dict(r_sc=r_sc - 5)), ('seal radius +5 mm', dict(r_sc=r_sc + 5)),
                     ('turbine seal r 35', dict(r_sc=r_sc, r_st=35.0))):
        if kw:
            sens[lab_] = thrust(**kw)['net_N']
    out['axial_thrust'] = dict(compressor_back_seal_r_mm=round(r_sc, 1), seal_r_for_minus_500N_mm=round(r_trim, 1), design_770=th, peak_850=th850, idle_55pct=th_idle, sensitivity_net_N=sens,
                               design='net FORWARD (-x) 300-800 N at all points: front tandem pair (2 x 7008-E, 25 deg) locates; rear 7008-C floats with '
                                      'a 300 N wave-spring preload; trim with the compressor back-face labyrinth radius (impeller back-face land) and the '
                                      'turbine back-face buffer orifice; measure with a load washer behind the front cartridge on the rig')
    print('\naxial thrust (back-face seal r %.1f mm): 770 C %s | 850 C %s | idle %s | sens %s' % (r_sc, th, th850, th_idle, sens))
    # bearing life + friction
    pre = 300.0
    life = {}
    for tag, Fr, Fa, ang, share in (('core_front_pair (per bearing, 60 % share)', 0.5 * st['core_front_N'] + 40, abs(min(th['net_N'], 0)) + pre, 'E', 0.6),
                                    ('core_rear', st['core_rear_N'] + 60, pre, 'C', 1.0),
                                    ('gen_front (locating)', st['gen_front_N'] + 40, pre + 50, 'E', 1.0),
                                    ('gen_rear (floating)', st['gen_rear_N'] + 40, pre, 'C', 1.0)):
        Fa_b = Fa * share if 'pair' in tag else Fa
        Pq = P_eq(Fr, Fa_b, ang)
        C_ = L.BRG['C_dyn'] * (0.95 if ang == 'E' else 1.0)
        l10 = L10h(C_, Pq)
        life[tag] = dict(Fr_N=round(Fr), Fa_N=round(Fa_b), P_N=round(Pq), L10_h=round(l10), L10m_aISO3_h=round(3 * l10),
                         friction_W=round(friction_W(Fr, Fa_b)), n_dm=round(L.N_RUN * 0.5 * (L.BRG['d'] + L.BRG['D'])),
                         speed_pct_of_oil_limit=round(100 * L.N_RUN / (L.BRG['n_oil_limit'] * (0.95 if ang == 'E' else 1.0)), 1))
    th850_fa = abs(min(th850['net_N'], 0)) + pre
    life['core_front_pair at 850 C'] = dict(Fa_N=round(0.6 * th850_fa), L10m_aISO3_h=round(3 * L10h(0.95 * L.BRG['C_dyn'], P_eq(0.5 * st['core_front_N'] + 40, 0.6 * th850_fa, 'E'))))
    out['bearings'] = dict(type=L.BRG['model'], d_D_B=[L.BRG['d'], L.BRG['D'], L.BRG['B']], C_dyn_N=L.BRG['C_dyn'], preload_N=pre, cases=life,
                           friction_total_core_W=round(2 * life['core_front_pair (per bearing, 60 % share)']['friction_W'] + life['core_rear']['friction_W']),
                           friction_total_gen_W=round(life['gen_front (locating)']['friction_W'] + life['gen_rear (floating)']['friction_W']),
                           plan='replace all 5 bearings at 24,000 h (L10m aISO 3 >= 2x that) with vibration trending; same part number in all positions',
                           oil='ISO VG 32 synthetic turbine oil (Shell Turbo T32 / Castrol Perfecto T / TotalEnergies Preslia), 2.5 barg jets, ~2.5 L/min per bearing + SFD feed, 10 um filter')
    for k, v in life.items():
        print('  %-44s %s' % (k, v))
    # quill / shafts
    T_gen = 335e3 / OM
    d = L.QUILL['waist_d'] * MM
    tau = 16 * T_gen / (math.pi * d ** 3)
    Lq = (L.QUILL['waist'][1] - L.QUILL['waist'][0]) * MM
    I = math.pi * d ** 4 / 64; mlin = RHO_ST * math.pi * d ** 2 / 4
    f_pp = (math.pi / 2) / Lq ** 2 * math.sqrt(E_ST * I / mlin) * 60
    k_ax = E_ST * math.pi * d ** 2 / 4 / Lq
    T_turb = 970e3 / OM
    out['quill'] = dict(waist_d_mm=L.QUILL['waist_d'], free_length_mm=round(Lq * 1e3), torque_rated_Nm=round(T_gen, 1), tau_rated_MPa=round(tau / 1e6, 1),
                        tau_fault_x5_MPa=round(5 * tau / 1e6, 1), first_bending_pinned_rpm=round(f_pp), axial_stiffness_N_um=round(k_ax / 1e6),
                        hex='crowned external AF24 x 24 on the core-shaft nose (gas-nitrided 31CrMoV9) in the internal AF24 socket of the quill (rotary-broached, '
                            'nitrided 34CrNiMo6); float +/-1 mm; contact pressure %.0f MPa rated / %.0f fault' % (
                                T_gen / (0.3 * 0.020 * 0.024 ** 2) / 1e6, 5 * T_gen / (0.3 * 0.020 * 0.024 ** 2) / 1e6),
                        flange=L.QUILL['bolts'], friction_capacity_Nm=round(6 * 25e3 * 0.15 * 0.026))
    out['core_shaft'] = dict(T_turbine_peak_Nm=round(T_turb, 1), tau_d40_MPa=round(16 * T_turb / (math.pi * 0.04 ** 3) / 1e6, 1),
                             clamp_kN=L.NUT['preload_kN'], sigma_d40_clamp_MPa=round(L.NUT['preload_kN'] * 1e3 / (math.pi * 0.02 ** 2) / 1e6, 1),
                             compressor_friction_capacity_Nm=round(0.15 * L.NUT['preload_kN'] * 1e3 * (0.022 + 0.025)),
                             compressor_torque_Nm=round(560e3 / OM, 1), material='42CrMo4 QT (Rp0.2 >= 750) shaft; heat dam / stub friction-welded to the wheel by the supplier')
    print('quill:', out['quill']['tau_rated_MPa'], 'MPa rated,', out['quill']['first_bending_pinned_rpm'], 'rpm pinned bending')
    json.dump(out, open(os.path.join(HERE, 'e_rotor.json'), 'w'), indent=1)
    print('-> sim/variant_e/e_rotor.json')


if __name__ == '__main__':
    main()
