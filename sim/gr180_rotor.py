# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "matplotlib"]
# ///
"""GR180 rotor dynamics: Euler-Bernoulli beam FE of the shaft + rigid disks (compressor, turbine, nose cone, nut,
bearing inner rings, spacers) with gyroscopic effect, on two 608 bearing springs.
Campbell diagram (forward/backward whirl) and forward synchronous critical speeds.

Run:  uv run sim/gr180_rotor.py
Units: SI inside (m, kg, N). Geometry in assembly coords (mm) from build_gr180.py v12; mass properties from
sim/geometry_measured.json (measure_geometry.py) when present.
Variant 'gen_front': a high-speed PM generator rotor overhung in front of the compressor (single-shaft generator idea).
"""
import json, math, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
E_STEEL, RHO_STEEL = 205e9, 7850.0
N_RUN = 120000.0

# shaft outer profile (shaft local x, radius) from build_gr180.py, assembly offset -51 mm
t7 = math.tan(math.radians(7)); rm = 7.0; re_ = rm - 18 * t7
PROFILE = [(0, 3), (15, 3), (15, 3.5), (49, 3.5), (49, 4), (60.1, 4), (60.1, re_), (76, rm), (127, rm), (145, re_), (145, 4), (166, 4), (166, 3), (179.8, 3)]
OFF = -51.0
def shaft_r(xa):
    x = xa - OFF
    for (x0, r0), (x1, r1) in zip(PROFILE[:-1], PROFILE[1:]):
        if x0 <= x <= x1 and x1 > x0: return r0 + (r1 - r0) * (x - x0) / (x1 - x0)
    return 3.0
THREAD_EFF = {(-51.0, -36.0): 2.46, (115.0, 128.8): 2.46}   # M6x1 minor radius ~ effective bending radius
# clamped stacks (nose-cone nut -> compressor -> shim -> front 608 IR; turbine nut -> turbine hub -> rear 608 IR -> spacer):
# preloaded hubs add bending stiffness. 'clamped' = shaft section replaced by an equivalent radius (judgement, ~half of hub wall)
CLAMPED = {(-36.0, 9.1): 5.5, (94.0, 121.8): 5.0}

# ---- lumped disks: name -> (mass kg, x_cg mm, Ip kg m2, It kg m2)
def disks_from_json():
    f = os.path.join(HERE, 'geometry_measured.json')
    D = {}
    if os.path.exists(f):
        mp = json.load(open(f))['rotor_parts']
        for n, d in mp.items():
            if n == 'Shaft': continue
            D[n] = (d['mass_g'] * 1e-3, d['x_cg'], d['Ip_gmm2'] * 1e-9, d['It_gmm2'] * 1e-9)
    else:   # fallback estimates
        D = {'Compressor': (0.102, -12.0, 4.0e-5, 2.5e-5), 'Turbine': (0.150, 114.5, 1.2e-4, 6.5e-5),
             'NoseCone': (0.006, -45.0, 2.0e-7, 3.0e-7), 'TurbineNut': (0.003, 124.8, 6e-8, 6e-8)}
    # bearing inner rings Ø12.1/8 x7 + half the balls, steel (not in asm_parts as separate solids)
    m_ir = RHO_STEEL * math.pi / 4 * (12.1e-3**2 - 8e-3**2) * 7e-3 + 0.5 * 7 * 3300 * math.pi / 6 * (3.969e-3)**3
    for n, x in (('FrontBearing_IR', 5.6), ('RearBearing_IR', 103.8)):
        D[n] = (m_ir, x, 0.5 * m_ir * (6.05e-3**2 + 4e-3**2), m_ir * (3 * (6.05e-3**2 + 4e-3**2) + 7e-3**2) / 12)
    return D

def gen_rotor(length_mm=30.0, d_mm=22.0, gap_mm=6.0, x_front=-61.9):
    """PM rotor (NdFeB + carbon sleeve) overhung in front of the nose cone, solid cylinder approximation."""
    r = d_mm / 2e3; L = length_mm / 1e3; m = 7600 * math.pi * r**2 * L
    x_cg = x_front - gap_mm - length_mm / 2
    return m, x_cg, 0.5 * m * r**2, m * (3 * r**2 + L**2) / 12, x_front - gap_mm - length_mm

def build(D, kb_front, kb_rear, x_start=-51.0, x_end=128.8, clamped=False):
    xs = sorted(set([x_start, x_end] + [round(d[1], 3) for d in D.values()] + [5.6, 103.8] +
                    [OFF + p[0] for p in PROFILE if x_start <= OFF + p[0] <= x_end]))
    fine = []
    for a, b in zip(xs[:-1], xs[1:]):
        n = max(1, int(math.ceil((b - a) / 4.0)))
        fine += [a + (b - a) * k / n for k in range(n)]
    xs = np.array(fine + [xs[-1]]) * 1e-3
    nn = len(xs); ndof = 2 * nn
    K = np.zeros((ndof, ndof)); M = np.zeros((ndof, ndof)); P = np.zeros((ndof, ndof))
    for e in range(nn - 1):
        L = xs[e + 1] - xs[e]; xm = 0.5 * (xs[e] + xs[e + 1]) * 1e3
        r = shaft_r(xm) * 1e-3
        for (a, b), rr in THREAD_EFF.items():
            if a <= xm <= b: r = rr * 1e-3
        if clamped:
            for (a, b), rr in CLAMPED.items():
                if a <= xm <= b: r = max(r, rr * 1e-3)
        if xm < -51.0: r = 4.0e-3                                   # generator stub shaft (variant only)
        A = math.pi * r**2; I = math.pi * r**4 / 4
        k = E_STEEL * I / L**3 * np.array([[12, 6*L, -12, 6*L], [6*L, 4*L*L, -6*L, 2*L*L], [-12, -6*L, 12, -6*L], [6*L, 2*L*L, -6*L, 4*L*L]])
        m = RHO_STEEL * A * L / 420 * np.array([[156, 22*L, 54, -13*L], [22*L, 4*L*L, 13*L, -3*L*L], [54, 13*L, 156, -22*L], [-13*L, -3*L*L, -22*L, 4*L*L]])
        mr = RHO_STEEL * I / (30 * L) * np.array([[36, 3*L, -36, 3*L], [3*L, 4*L*L, -3*L, -L*L], [-36, -3*L, 36, -3*L], [3*L, -L*L, -3*L, 4*L*L]])
        idx = [2*e, 2*e+1, 2*e+2, 2*e+3]
        K[np.ix_(idx, idx)] += k; M[np.ix_(idx, idx)] += m + mr; P[np.ix_(idx, idx)] += 2 * mr
    def node(xmm): return int(np.argmin(abs(xs - xmm * 1e-3)))
    for n, (m, x, Ip, It) in D.items():
        i = node(x); M[2*i, 2*i] += m; M[2*i+1, 2*i+1] += It; P[2*i+1, 2*i+1] += Ip
    K[2*node(5.6), 2*node(5.6)] += kb_front; K[2*node(103.8), 2*node(103.8)] += kb_rear
    return xs, K, M, P

def whirl(K, M, P, Omega):
    """complex-coordinate isotropic rotor: (K + w*Omega*P - w^2 M) q = 0 ; w>0 forward, w<0 backward"""
    n = K.shape[0]
    A = np.block([[np.zeros((n, n)), np.eye(n)], [K, Omega * P]])
    B = np.block([[np.eye(n), np.zeros((n, n))], [np.zeros((n, n)), M]])
    w = np.linalg.eigvals(np.linalg.solve(B, A))
    w = np.real(w[np.abs(np.imag(w)) < 1e-6 * (1 + np.abs(w))])
    return np.sort(w)

def criticals(K, M, P, n_modes=4, xs=None):
    """forward synchronous critical speeds: K q = w^2 (M - P) q  (gyroscopic term at w = Omega).
    With xs: also returns where each mode has its largest deflection (mm)."""
    w2, V = np.linalg.eig(np.linalg.solve(M - P, K))
    ok = (np.abs(np.imag(w2)) < 1e-6 * np.abs(w2)) & (np.real(w2) > 0)
    w2, V = np.real(w2[ok]), np.real(V[:, ok]); o = np.argsort(w2)[:n_modes]
    rpm = np.sqrt(w2[o]) * 60 / (2 * math.pi)
    if xs is None: return rpm
    loc = [xs[int(np.argmax(np.abs(V[0::2, i])))] * 1e3 for i in o]
    return rpm, loc

def main():
    D = disks_from_json()
    print('Rotor parts (mass g, x_cg mm):', ', '.join('%s %.1f@%.1f' % (n, d[0] * 1e3, d[1]) for n, d in D.items()))
    print('Total rotor mass %.0f g; bearing span %.1f mm; turbine overhang %.1f mm; compressor overhang %.1f mm'
          % (sum(d[0] for d in D.values()) * 1e3 + RHO_STEEL * 1e-9 * 15331.4 * 1e3, 103.8 - 5.6, D['Turbine'][1] - 103.8, 5.6 - D['Compressor'][1]))
    cases = [('soft front (O-ring 0.5 N/um), rear 10 N/um', 0.5e6, 10e6), ('stiff both 10 N/um', 10e6, 10e6),
             ('very stiff 30 N/um', 30e6, 30e6), ('soft both 1 N/um', 1e6, 1e6)]
    res = {}
    for clamped in (False, True):
        print('\nForward synchronous critical speeds [rpm] (run %.0f rpm) - %s; (x = max deflection, mm):'
              % (N_RUN, 'CLAMPED hub stacks stiffen the shaft' if clamped else 'BARE shaft (conservative)'))
        for lab, kf, kr in cases:
            xs, K, M, P = build(D, kf, kr, clamped=clamped)
            c, loc = criticals(K, M, P, xs=xs)
            res[('clamped ' if clamped else 'bare ') + lab] = c.tolist()
            print('  %-44s %s' % (lab, ' | '.join('%7.0f@x%-4.0f%s' % (v, l, ' <--' if abs(v - N_RUN) < 0.2 * N_RUN else '')
                                                  for v, l in zip(c, loc))))
    print('\nVariant: PM generator rotor Ø22x30 (%.0f g) overhung 6 mm ahead of the nose cone (single-shaft generator):'
          % (gen_rotor()[0] * 1e3))
    m, x, Ip, It, xf = gen_rotor()
    D2 = dict(D); D2['PM_rotor'] = (m, x, Ip, It)
    for lab, kf, kr in cases:
        xs, K, M, P = build(D2, kf, kr, x_start=xf, clamped=True)
        c, loc = criticals(K, M, P, xs=xs)
        print('  %-44s %s' % (lab, ' | '.join('%7.0f@x%-4.0f%s' % (v, l, ' <--' if abs(v - N_RUN) < 0.2 * N_RUN else '') for v, l in zip(c, loc))))
    json.dump(res, open(os.path.join(HERE, 'rotor_results.json'), 'w'), indent=1)
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        xs, K, M, P = build(D, 10e6, 10e6, clamped=True)
        Om = np.linspace(0, 160000, 81) * 2 * math.pi / 60
        fig, ax = plt.subplots(figsize=(8, 5))
        for O in Om:
            w = whirl(K, M, P, O) * 60 / (2 * math.pi)
            w = w[np.abs(w) < 400000]
            ax.plot([O * 60 / (2 * math.pi)] * len(w[w > 0]), w[w > 0], 'b.', ms=3)
            ax.plot([O * 60 / (2 * math.pi)] * len(w[w < 0]), -w[w < 0], 'r.', ms=2)
        ax.plot([0, 160000], [0, 160000], 'k--', lw=1, label='1x synchronous')
        ax.axvline(N_RUN, c='gray', ls=':', label='120k rpm run')
        ax.set_ylim(0, 400000); ax.set_xlabel('rotor speed [rpm]'); ax.set_ylabel('whirl frequency [rpm]')
        ax.set_title('GR180 Campbell diagram (bearings 10 N/µm): blue forward, red backward'); ax.legend(); ax.grid(alpha=.3)
        fig.tight_layout(); fn = os.path.join(HERE, 'gr180_campbell.png'); fig.savefig(fn, dpi=120); print('plot ->', fn)
    except ImportError:
        pass

if __name__ == '__main__':
    main()
