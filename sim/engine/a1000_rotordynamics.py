#!/usr/bin/env python3
"""AURORA-1000 rotor dynamics: single-shaft rotor (gearbox coupling, thrust collar, 2 centrifugal impellers, spacer drum,
2 cast MAR-M247 blisks, rear stub) on two tilting-pad journal bearings.

Model: Timoshenko beam elements (shear, rotary inertia, distributed gyroscopics) in complex coordinates
(u = y + i z, phi = du/dx), valid for an axisymmetric rotor on isotropic bearings (tilting pads are nearly isotropic).
Discs (impellers, blisks, collar, coupling hub) are rigid lumped masses m, Id, Ip from their axisymmetric profiles; the
shaft elements through a disc hub carry its stiffness but no mass (the hub mass is in the lump).
    M q'' + (C - i Omega G) q' + K q = F,   forward whirl = Im(s) > 0
Outputs: damped whirl frequencies and log decrements vs speed (Campbell), undamped critical-speed map vs bearing
stiffness, API 617 unbalance response (amplification factor, separation margin, peak amplitude), mode shapes.
Two bearing layouts are compared: A = between bearings (rear bearing in the exhaust hub, 5 struts), B = turbine overhung.

Run:    python sim/engine/a1000_rotordynamics.py         (numpy + matplotlib)
Writes: sim/engine/fea/a1000_rotordynamics.json, docs/img/a1000_rotordynamics.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_turbine as A                                     # noqa: E402
sys.argv = _argv

ML = json.load(open(os.path.join(ROOT, 'sim', 'mw1_meanline.json')))
PARTS = os.path.join(ROOT, 'cad_out', 'engine', 'A1000', 'A1000_parts.json')
N_OP, N_MCS, N_TRIP = 15000.0, 15750.0, 16500.0               # rated, max continuous (105 %), trip (110 %)
MAT = dict(steel=(7850., 205e9), in718=(8190., 185e9), ti64=(4430., 105e9), al2618=(2760., 70e9), marm247=(8540., 180e9))
NU = 0.30


# ------------------------------------------------------------------------------------------------ lumped discs
def axisym(poly, rho, res=0.25):
    """mass [kg], axial centroid [mm], Ip, Id about the own centroid [kg m2] of a solid of revolution of an (x, r) polygon"""
    from matplotlib.path import Path
    P = np.asarray(poly, float); path = Path(P)
    xs = np.arange(P[:, 0].min(), P[:, 0].max(), res) + res / 2; rs = np.arange(0, P[:, 1].max(), res) + res / 2
    X, Rr = np.meshgrid(xs, rs); inside = path.contains_points(np.c_[X.ravel(), Rr.ravel()]).reshape(X.shape)
    dV = 2 * np.pi * Rr * res * res * 1e-9                       # m3 per cell
    m = rho * np.sum(dV * inside); xc = np.sum(X * dV * inside) * rho / m
    Ip = rho * np.sum((Rr * 1e-3) ** 2 * dV * inside)
    Id = rho * np.sum(((Rr * 1e-3) ** 2 / 2 + ((X - xc) * 1e-3) ** 2) * dV * inside)
    return m, xc, Ip, Id


def ring(m, r_mm):
    """thin ring of point masses (blades) about the axis: Ip, Id"""
    r = r_mm * 1e-3; return m * r * r, m * r * r / 2


def impeller(st, x0, rho, bore=24.0):
    """open centrifugal impeller: elliptic hub contour from the inducer hub (axial) to the tip (radial), flat back face,
    tip disc thickness 7 mm, + blades (full + splitter, 2.5-3 mm) lumped as a ring at mid radius"""
    r2 = st['D2'] / 2 * 1e3; r1h = st['r1h'] * 1e3; r1t = st['r1t'] * 1e3; b2 = st['b2'] * 1e3
    L = 0.30 * 2 * r2; tb = 7.0
    hub = [(x0 + (L - tb) * math.sin(p), r1h + (r2 - r1h) * (1 - math.cos(p))) for p in np.linspace(0, math.pi / 2, 30)]
    poly = [(x0, bore)] + hub + [(x0 + L, r2), (x0 + L, bore)]
    m, xc, Ip, Id = axisym(poly, rho)
    # blades: meridional area between hub and shroud (inducer tip r1t -> exit width b2) x thickness x count
    A_mer = 0.55 * (r1t - r1h) * L + 0.5 * b2 * (r2 - r1t)
    mb = rho * A_mer * 2.8 * 26 * 1e-9                         # 13 full + 13 splitter blades
    ip, idd = ring(mb, 0.5 * (r1h + r2))
    return dict(m=m + mb, x=(m * xc + mb * (x0 + 0.5 * L)) / (m + mb), Ip=Ip + ip, Id=Id + idd, L=L, r2=r2, poly=poly)


def blisk(row, x_off):
    """cast blisk: disc profile from cad/engine/a1000_turbine.py + blades (mass from the CAD export) as a ring"""
    poly = [(x + x_off, r) for x, r in A.disc_profile(row)]
    m, xc, Ip, Id = axisym(poly, MAT['marm247'][0])
    mb1 = None
    for src in (PARTS, os.path.join(ROOT, 'fusion', 'A1000', 'parts.json')):    # CAD output, else the committed copy
        try:
            mb1 = json.load(open(src))['A1000_%s_blade' % row]['mass_kg']; break
        except (OSError, KeyError):
            pass
    mb1 = mb1 if mb1 is not None else dict(R1=0.034, R2=0.135)[row]
    rh, rt = A.row_radius(row, 0.0), A.row_radius(row, 1.0); mb = A.Z[row] * mb1
    ip, idd = ring(mb, rh + 0.42 * (rt - rh))
    hw = A.DISC[row]['hub_w']; xm = 0.5 * (A.X_LE[row] + A.X_TE[row]) + x_off
    return dict(m=m + mb, x=xc, Ip=Ip + ip, Id=Id + idd, hub=(xm - hw / 2, xm + hw / 2), r_boss=A.DISC[row]['r_boss'], poly=poly,
                m_blades=mb)


IMP_CAD = [os.path.join(ROOT, 'cad_out', 'engine', 'A1000', 'A1000_C_parts.json'), os.path.join(ROOT, 'fusion', 'A1000C', 'parts.json')]
IMP_DES = os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')


def impeller_detail():
    """detail-design impellers (cad/engine/a1000_impeller.py): mass, x_cg, Ip, Id of hub + 13 blades + 13 splitters from the
    CAD, position, inducer hub radius and bore from sim/a1000_impeller_design.json; None without them (concept profiles)"""
    src = next((p for p in IMP_CAD if os.path.exists(p)), None)
    if src is None or not os.path.exists(IMP_DES): return None
    d = json.load(open(src)); des = json.load(open(IMP_DES))['stages']; out = {}
    for k in ('C1', 'C2'):
        r = d['A1000_%s_rotor' % k] if 'A1000_%s_rotor' % k in d else d['rotor'][k]; gm = des[k]['geometry']
        out[k] = dict(m=r['m'], x=r['x_cg'], Ip=r['Ip'], Id=r['Id'], L=gm['L'], x0=gm['x0'], r1h=gm['r1h'], r_bore=gm['r_bore'],
                      poly=[tuple(q) for q in gm['hub_profile']],
                      mat={'Al 2618-T61': 'al2618', 'Ti-6Al-4V': 'ti64'}[des[k]['material']])
    return out


# ------------------------------------------------------------------------------------------------ rotor layout [mm]
def rotor(layout='A'):
    c1, c2 = ML['compressor']
    det = impeller_detail()
    if det:                                                      # detail design (impeller 2 shorter, spacer longer; the
        i1, i2 = det['C1'], det['C2']                            # rear face of impeller 2 and the turbine unchanged)
        x_i1 = (i1['x0'], i1['x0'] + i1['L']); x_i2 = (i2['x0'], i2['x0'] + i2['L'])
    else:
        i1 = impeller(c1, 205.0, MAT['al2618'][0]); x_i1 = (205.0, 205.0 + i1['L'])
        x0_2 = x_i1[1] + 50.0                                    # return channel / interstage seal
        i2 = impeller(c2, x0_2, MAT['ti64'][0]); x_i2 = (x0_2, x0_2 + i2['L'])
    # impeller bodies in the beam model: detail = nose diameter 2 r1h over the tie-bolt bore; concept = mean of r1h, 60 mm
    od1, id1 = (2 * i1['r1h'], 2 * i1['r_bore']) if det else (2 * 0.5 * (c1['r1h'] * 1e3 + 60.0), 48.0)
    od2, id2 = (2 * i2['r1h'], 2 * i2['r_bore']) if det else (2 * 0.5 * (c2['r1h'] * 1e3 + 65.0), 48.0)
    # turbine: R1 disc hub front face 175 mm behind impeller 2 (diffuser, combustor-to-NGV1 scroll, drum seals)
    hw1 = A.DISC['R1']['hub_w']; xm1 = 0.5 * (A.X_LE['R1'] + A.X_TE['R1'])
    x_off = x_i2[1] + 175.0 - (xm1 - hw1 / 2)
    b1 = blisk('R1', x_off); b2 = blisk('R2', x_off)
    collar = dict(m=MAT['steel'][0] * math.pi * (0.110**2 - 0.055**2) * 0.025, x=160.0)
    collar['Ip'], collar['Id'] = collar['m'] * (0.110**2 + 0.055**2) / 2, collar['m'] * (3 * (0.110**2 + 0.055**2) + 0.025**2) / 12
    coup = dict(m=6.0, x=0.0, Ip=0.012, Id=0.008)               # diaphragm coupling half (to the gearbox), overhung
    discs = dict(coupling=coup, collar=collar, impeller1=i1, impeller2=i2, blisk1=b1, blisk2=b2)
    # shaft segments: (x0, x1, OD, ID, material, carries mass)
    seg = [(0.0, 100.0, 80.0, 0.0, 'steel', True),
           (100.0, 205.0, 110.0, 0.0, 'steel', True),
           (x_i1[0], x_i1[1], od1, id1, i1['mat'] if det else 'al2618', False),
           (x_i1[1], x_i2[0], 150.0, 48.0, 'steel', True),          # interstage spacer (curvic both ends)
           (x_i2[0], x_i2[1], od2, id2, i2['mat'] if det else 'ti64', False),
           (x_i2[1], b1['hub'][0], 170.0, 120.0, 'in718', True),     # compressor-turbine drum, tie bolt inside
           (b1['hub'][0], b1['hub'][1], 2 * b1['r_boss'], 0.0, 'marm247', False),
           (b1['hub'][1], b2['hub'][0], 180.0, 120.0, 'in718', True),  # interstage spacer under NGV2
           (b2['hub'][0], b2['hub'][1], 2 * b2['r_boss'], 0.0, 'marm247', False)]
    x_end = b2['hub'][1]
    # tie bolt: 48 mm, preloaded, from the collar to a nut in the blisk-1 hub (mass only; stiffness in the drums)
    tie = (160.0, b1['hub'][0] + 20.0, 48.0)
    if layout == 'A':
        seg += [(x_end, x_end + 115.0, 110.0, 50.0, 'in718', True)]   # rear stub shaft to the exhaust-hub bearing
        brg = [110.0, x_end + 80.0]
    else:
        brg = [110.0, x_i2[1] + 60.0]                                 # bearing 2 between compressor and turbine
    return dict(seg=seg, discs=discs, brg=brg, tie=tie, layout=layout)


# ------------------------------------------------------------------------------------------------ FE matrices
def mesh_nodes(R, dl=20.0):
    xs = {0.0}
    for s in R['seg']:
        n = max(1, int(math.ceil((s[1] - s[0]) / dl)))
        xs.update(np.linspace(s[0], s[1], n + 1).round(4))
    xs.update(round(d['x'], 4) for d in R['discs'].values()); xs.update(round(b, 4) for b in R['brg'])
    return np.array(sorted(xs))


def assemble(R, x, sup):
    """complex-coordinate matrices; with a squeeze-film damper (sup has 'ks') each bearing gets a housing DOF:
    journal -(oil film kb, cb)- housing (mh) -(centering spring ks, SFD cs)- ground"""
    n = len(x); nh = len(R['brg']) if 'ks' in sup else 0; N = 2 * n + nh
    M = np.zeros((N, N)); K = np.zeros((N, N)); G = np.zeros((N, N)); C = np.zeros((N, N))
    E_hot = dict(marm247=170e9, in718=175e9)                    # at the hub metal temperatures (~450-550 C)
    for i in range(n - 1):
        xa, xb = x[i], x[i + 1]; xm = 0.5 * (xa + xb); l = (xb - xa) * 1e-3
        s = [s for s in R['seg'] if s[0] - 1e-6 <= xm <= s[1] + 1e-6][0]
        OD, ID, mat, wm = s[2] * 1e-3, s[3] * 1e-3, s[4], s[5]
        rho, E = MAT[mat]; E = E_hot.get(mat, E)
        Gs = E / (2 * (1 + NU)); A_ = math.pi / 4 * (OD**2 - ID**2); I = math.pi / 64 * (OD**4 - ID**4)
        k_sh = 6 * (1 + NU) / (7 + 6 * NU) if ID == 0 else 0.5    # Timoshenko shear coefficient
        phi = 12 * E * I / (k_sh * Gs * A_ * l * l)
        Ke = E * I / ((1 + phi) * l**3) * np.array([[12, 6 * l, -12, 6 * l], [6 * l, (4 + phi) * l * l, -6 * l, (2 - phi) * l * l],
                                                      [-12, -6 * l, 12, -6 * l], [6 * l, (2 - phi) * l * l, -6 * l, (4 + phi) * l * l]])
        Mt = rho * A_ * l / 420 * np.array([[156, 22 * l, 54, -13 * l], [22 * l, 4 * l * l, 13 * l, -3 * l * l],
                                             [54, 13 * l, 156, -22 * l], [-13 * l, -3 * l * l, -22 * l, 4 * l * l]])
        Mr = rho * I / (30 * l) * np.array([[36, 3 * l, -36, 3 * l], [3 * l, 4 * l * l, -3 * l, -l * l],
                                             [-36, -3 * l, 36, -3 * l], [3 * l, -l * l, -3 * l, 4 * l * l]])
        d = [2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3]
        K[np.ix_(d, d)] += Ke
        f = 1.0 if wm else 0.02                                   # hub segments: mass in the disc lump (2 % keeps M regular)
        M[np.ix_(d, d)] += f * (Mt + Mr); G[np.ix_(d, d)] += f * 2 * Mr
    # tie bolt mass (lumped on the nodes it spans)
    t0, t1, dt = R['tie']; mt = MAT['steel'][0] * math.pi / 4 * (dt * 1e-3) ** 2 * (t1 - t0) * 1e-3
    on = [j for j in range(n) if t0 <= x[j] <= t1]
    for j in on: M[2 * j, 2 * j] += mt / len(on)
    for d_ in R['discs'].values():
        j = int(np.argmin(abs(x - d_['x'])))
        M[2 * j, 2 * j] += d_['m']; M[2 * j + 1, 2 * j + 1] += d_['Id']; G[2 * j + 1, 2 * j + 1] += d_['Ip']
    for ib, b in enumerate(R['brg']):
        j = 2 * int(np.argmin(abs(x - b)))
        if nh:
            h = 2 * n + ib
            for Mx, v in ((K, sup['kb']), (C, sup['cb'])):
                Mx[j, j] += v; Mx[h, h] += v; Mx[j, h] -= v; Mx[h, j] -= v
            K[h, h] += sup['ks']; C[h, h] += sup['cs']; M[h, h] += sup['mh']
        else:
            K[j, j] += sup['kb']; C[j, j] += sup['cb']
    return M, K, C, G


def eig(M, K, C, G, Om):
    N = len(M); Mi = np.linalg.inv(M)
    Aa = np.block([[np.zeros((N, N)), np.eye(N)], [-Mi @ K, -Mi @ (C - 1j * Om * G)]])
    s, V = np.linalg.eig(Aa)
    return s, V[:N]


def whirl(R, sup, speeds, nf=5):
    x = mesh_nodes(R); M, K, C, G = assemble(R, x, sup)
    out = []
    for N in speeds:
        Om = N * 2 * math.pi / 60; s, V = eig(M, K, C, G, Om)
        # oscillatory forward modes only: the SFD housing roots are overdamped (log dec >> 10, no resonance)
        fw = sorted([(si.imag / 2 / math.pi, -2 * math.pi * si.real / abs(si.imag), V[:, k]) for k, si in enumerate(s)
                     if si.imag > 1.0 and -2 * math.pi * si.real / si.imag < 10.0], key=lambda t: t[0])[:nf]
        bw = sorted([(-si.imag / 2 / math.pi, -2 * math.pi * si.real / abs(si.imag)) for si in s
                     if si.imag < -1.0 and 2 * math.pi * si.real / si.imag < 10.0])[:nf]
        out.append(dict(N=N, fw=[(f, d) for f, d, _ in fw], bw=bw, shapes=[v for _, _, v in fw]))
    return x, out


def undamped_criticals(R, kb, nf=4):
    """synchronous forward critical speeds on rigid supports of stiffness kb: (K - w^2 (M - G)) q = 0 (Omega = w)"""
    x = mesh_nodes(R); M, K, C, G = assemble(R, x, dict(kb=kb, cb=0.0))
    w2 = np.linalg.eigvals(np.linalg.solve(M - G, K))
    w2 = np.sort(w2.real[(w2.real > 0) & (abs(w2.imag) < 1e-6 * abs(w2.real) + 1e-9)])
    return [math.sqrt(v) * 60 / 2 / math.pi for v in w2[:nf]]


def api_sm(Nc, af):
    """separation margin [%] from the operating range (95 % rated .. MCS) and the API 617 requirement"""
    lo = 0.95 * N_OP
    sm = 100 * (lo - Nc) / lo if Nc < lo else (100 * (Nc - N_MCS) / N_MCS if Nc > N_MCS else -0.0)
    if af < 2.5: req = 0.0
    elif Nc < lo: req = 17 * (1 - 1 / (af - 1.5))
    else: req = min(10 + 17 * (1 - 1 / (af - 1.5)), 26.0)
    return sm, req


def damped_criticals(R, sup, nmax=26000.0, nf=6):
    """1X crossings of the damped forward whirl frequencies: critical speed, log decrement, AF ~ pi / logdec"""
    speeds = np.arange(250.0, nmax + 1, 250.0)
    x, wh = whirl(R, sup, speeds, nf)
    out = []
    for m in range(nf):
        if any(len(w['fw']) <= m for w in wh): break
        f = np.array([w['fw'][m][0] for w in wh]); d = np.array([w['fw'][m][1] for w in wh]); g = f - speeds / 60
        for i in range(len(speeds) - 1):
            if g[i] > 0 >= g[i + 1]:
                t = g[i] / (g[i] - g[i + 1]); Nc = speeds[i] + t * (speeds[i + 1] - speeds[i]); dl = d[i] + t * (d[i + 1] - d[i])
                af = math.pi / dl if dl > 0 else float('inf'); sm, req = api_sm(Nc, af)
                out.append(dict(mode=m + 1, N=float(Nc), f_Hz=float(Nc / 60), logdec=float(dl), AF=float(af), SM=sm, SM_req=req,
                                ok=bool(sm >= req)))
    return out


def rotor_mass(R):
    m = sum(d['m'] for d in R['discs'].values())
    for s in R['seg']:
        if s[5]: m += MAT[s[4]][0] * math.pi / 4 * ((s[2] * 1e-3) ** 2 - (s[3] * 1e-3) ** 2) * (s[1] - s[0]) * 1e-3
    t0, t1, dt = R['tie']
    return m + MAT['steel'][0] * math.pi / 4 * (dt * 1e-3) ** 2 * (t1 - t0) * 1e-3


def journal_loads(R):
    """static journal loads [kg] of the two bearings from the mass distribution (statics)"""
    items = [(d['m'], d['x']) for d in R['discs'].values()]
    for s_ in R['seg']:
        if s_[5]: items.append((MAT[s_[4]][0] * math.pi / 4 * ((s_[2] * 1e-3) ** 2 - (s_[3] * 1e-3) ** 2) * (s_[1] - s_[0]) * 1e-3,
                                0.5 * (s_[0] + s_[1])))
    t0, t1, dt = R['tie']; items.append((MAT['steel'][0] * math.pi / 4 * (dt * 1e-3) ** 2 * (t1 - t0) * 1e-3, 0.5 * (t0 + t1)))
    m = sum(a for a, _ in items); xc = sum(a * b for a, b in items) / m; x1, x2 = R['brg']
    W1 = m * (x2 - xc) / (x2 - x1)
    return W1, m - W1, xc


def unbalance(R, sup, speeds, cases):
    """API 617 unbalance response, U = 6350 W / N_MCS [g mm] per plane with W the journal static load the plane is based
    on [kg]: cases = {name: [(x, phase, W_kg), ...]} (rev 4: the single-plane mode-1 case uses the sum of both journal
    loads at the antinode; rev 1-3 applied the per-journal amount, about half the API requirement); journal amplitudes"""
    x = mesh_nodes(R); M, K, C, G = assemble(R, x, sup)
    jb = [2 * int(np.argmin(abs(x - b))) for b in R['brg']]
    res = {}
    for name, locs in cases.items():
        amp = []
        for N in speeds:
            Om = N * 2 * math.pi / 60; F = np.zeros(len(M), complex)
            for xl, ph, Wk in locs:
                U = 6350 * Wk / N_MCS * 1e-6                       # kg m
                j = int(np.argmin(abs(x - xl))); F[2 * j] += U * Om * Om * np.exp(1j * ph)
            q = np.linalg.solve(K - Om * Om * M + 1j * Om * C + Om * Om * G, F)
            amp.append([2 * abs(q[j]) * 1e6 for j in jb])         # peak-to-peak [um]
        res[name] = np.array(amp)
    W1, W2, xc = journal_loads(R)
    return res, {k: [6350 * Wk / N_MCS for _, _, Wk in v] for k, v in cases.items()}, (W1, W2)


# ------------------------------------------------------------------------------------------------ main
# tilting-pad journals 110 mm x 55 mm (light load, preload 0.3): oil film stiffness / damping incl. the pedestal;
# SFD option: squeeze-film damper (OD 150 mm, land 30 mm, clearance 0.15 mm) on a squirrel-cage centering spring
# sfd_lo: cavitated pi-film / hot oil (~70 C) gives about half the SFD damping (review): sensitivity case
SUP = dict(rigid=dict(kb=1.2e8, cb=6.0e4), sfd=dict(kb=1.2e8, cb=6.0e4, ks=2.5e7, cs=3.0e4, mh=8.0),
           sfd_lo=dict(kb=1.2e8, cb=6.0e4, ks=2.5e7, cs=1.2e4, mh=8.0))
CONF = {'A': ('A', 'rigid'), 'A-SFD': ('A', 'sfd'), 'A-SFD-lo': ('A', 'sfd_lo'), 'B': ('B', 'rigid'), 'B-SFD': ('B', 'sfd')}
SEL = 'A-SFD'
API_LIM = 25.4 * math.sqrt(12000 / N_MCS)                     # API 617 unbalance-response limit [um pk-pk]


def main():
    res = {}; plot_data = {}
    speeds = np.arange(0, 22001, 500.0); fine = np.arange(500, 22001, 50.0)
    kmap = np.logspace(6.7, 9.7, 31)
    cmap = {lay: [undamped_criticals(rotor(lay), k) for k in kmap] for lay in ('A', 'B')}
    for name, (lay, sk) in CONF.items():
        R = rotor(lay); sup = SUP[sk]
        x, wh = whirl(R, sup, speeds)
        dc = damped_criticals(R, sup)
        W1, W2, xcg = journal_loads(R)
        cases = dict(mid=[(xcg, 0.0, W1 + W2)],                                   # mode 1: one plane at the antinode
                     conical=[(R['discs']['impeller1']['x'], 0.0, W1), (R['discs']['blisk2']['x'], math.pi, W2)],
                     turbine=[(R['discs']['blisk2']['x'], 0.0, 2 * W2)])
        ub, U, W = unbalance(R, sup, fine, cases)
        amp_max = {c: float(a[(fine >= 0.95 * N_OP) & (fine <= N_TRIP)].max()) for c, a in ub.items()}
        amp_all = {c: float(a.max()) for c, a in ub.items()}
        res[name] = dict(layout=lay, support=sup, bearings=R['brg'], rotor_mass_kg=rotor_mass(R),
                         discs={k: dict(m=v['m'], x=v['x'], Ip=v['Ip'], Id=v['Id']) for k, v in R['discs'].items()},
                         damped_criticals=dc, unbalance_U_gmm=U, journal_load_kg=W, amp_max_operating_um=amp_max,
                         amp_max_any_um=amp_all, whirl=[dict(N=w['N'], fw=w['fw'], bw=w['bw']) for w in wh])
        plot_data[name] = (R, x, wh, ub)
        w15 = [w for w in wh if w['N'] == N_OP][0]
        print('%-9s bearings x = %s mm, rotor %.0f kg, journal loads %.0f / %.0f kg, U %s g mm' % (
            name, ', '.join('%.0f' % b for b in R['brg']), rotor_mass(R), W[0], W[1],
            '; '.join('%s %s' % (k, '/'.join('%.0f' % u for u in v)) for k, v in U.items())))
        print('      whirl at 15,000 rpm: %s' % ', '.join('%.0f Hz (ld %.2f)' % fd for fd in w15['fw']))
        for c in dc:
            print('      critical %6.0f rpm  mode %d  log dec %5.2f  AF %5.1f  SM %5.1f %%  API req %4.1f %%  %s' % (
                c['N'], c['mode'], c['logdec'], c['AF'], c['SM'], c['SM_req'], 'OK' if c['ok'] else 'FAIL'))
        print('      max journal vibration %s um pk-pk in 95 %%..trip (any speed %s), API limit %.1f um' % (
            '/'.join('%.1f' % v for v in amp_max.values()), '/'.join('%.1f' % v for v in amp_all.values()), API_LIM))
    res['critical_speed_map'] = dict(k=list(kmap), A=cmap['A'], B=cmap['B'])
    res['selected'] = SEL
    print('disc lumps: ' + ', '.join('%s %.1f kg Ip %.3f Id %.3f' % (k, v['m'], v['Ip'], v['Id'])
                                     for k, v in res['A']['discs'].items()))
    plot(res, plot_data, speeds, fine, kmap, cmap)
    json.dump(res, open(os.path.join(HERE, 'fea', 'a1000_rotordynamics.json'), 'w'), indent=1, default=float)


def plot(res, pdat, speeds, fine, kmap, cmap):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle
    fig = plt.figure(figsize=(15, 10.5), dpi=110)
    R, x, wh, ub = pdat[SEL]
    ax = fig.add_axes([0.05, 0.58, 0.56, 0.36])
    for s in R['seg']:
        ax.add_patch(Rectangle((s[0], s[3] / 2), s[1] - s[0], (s[2] - s[3]) / 2, fc='#c8c8c8', ec='k', lw=0.5))
    for k in ('impeller1', 'impeller2', 'blisk1', 'blisk2'):
        d = R['discs'][k]; ax.add_patch(Polygon(d['poly'], fc='#7fb2e5' if 'imp' in k else '#e59a7f', ec='k', lw=0.6))
        ax.text(d['x'], 12, '%s\n%.0f kg' % (k, d['m']), ha='center', fontsize=7)
    for b in R['brg']:
        ax.add_patch(Rectangle((b - 27, 55), 54, 16, fc='#2e7d32', ec='k')); ax.add_patch(Rectangle((b - 15, 71), 30, 10, fc='#f9a825', ec='k'))
    ax.text(R['brg'][0], 86, 'tilting pad + SFD', ha='center', fontsize=7); ax.text(R['brg'][1], 86, 'exhaust-hub brg', ha='center', fontsize=7)
    w15 = [w for w in wh if w['N'] == N_OP][0]
    n = len(x)
    for k, (v, (f, dl)) in enumerate(zip(w15['shapes'][:3], w15['fw'][:3])):
        u = v[0:2 * n:2]; u = (u * np.exp(-1j * np.angle(u[np.argmax(abs(u))]))).real; u = u / max(abs(u))
        ax.plot(x, 300 + 45 * u, lw=1.6, label='mode %d: %.0f Hz at 15k rpm, log dec %.2f' % (k + 1, f, dl))
    ax.axhline(300, color='k', lw=0.5)
    ax.set_xlim(-20, x[-1] + 20); ax.set_ylim(0, 380); ax.set_aspect('equal'); ax.legend(fontsize=7, loc='upper left')
    ax.set_title('Selected rotor (layout A, between bearings, SFD supports), to scale [mm], whirl mode shapes', fontsize=10)
    ax2 = fig.add_axes([0.67, 0.58, 0.30, 0.36])
    for name, st, lw in (('A', '--', 0.9), (SEL, '-', 1.7)):
        wh_ = res[name]['whirl']
        for m in range(4):
            ax2.plot(speeds / 1e3, [w['fw'][m][0] for w in wh_], st, color='C%d' % m, lw=lw, label='%s fw%d' % (name, m + 1))
        for c in res[name]['damped_criticals']:
            ax2.plot(c['N'] / 1e3, c['f_Hz'], 'o', color='k' if name == SEL else 'grey', ms=5)
    ax2.plot(speeds / 1e3, speeds / 60, 'k-', lw=0.8, label='1X')
    ax2.axvspan(0.95 * N_OP / 1e3, N_TRIP / 1e3, color='tab:green', alpha=0.15, label='operating..trip')
    ax2.set_ylim(0, 500); ax2.set_xlabel('speed [k rpm]'); ax2.set_ylabel('forward whirl [Hz]'); ax2.grid(alpha=0.3)
    ax2.legend(fontsize=6, ncol=2); ax2.set_title('Campbell: rigid supports (dashed) vs SFD (solid)', fontsize=10)
    ax3 = fig.add_axes([0.05, 0.07, 0.40, 0.42])
    for lay, st in (('A', '-'), ('B', ':')):
        cm = np.array([c[:3] + [np.nan] * (3 - len(c)) for c in cmap[lay]])
        for m in range(3): ax3.semilogx(kmap, cm[:, m], st, color='C%d' % m, lw=1.5, label='%s crit %d' % (lay, m + 1))
    ax3.axhspan(0.95 * N_OP, N_TRIP, color='tab:green', alpha=0.15)
    s_ = SUP['sfd']; k_ser = 1 / (1 / s_['kb'] + 1 / s_['ks'])
    ax3.axvline(SUP['rigid']['kb'], color='k', lw=0.8, ls='--'); ax3.text(SUP['rigid']['kb'], 38000, ' rigid pedestal', fontsize=7)
    ax3.axvline(k_ser, color='tab:orange', lw=1.2); ax3.text(k_ser, 36000, ' SFD + spring', fontsize=7, color='tab:orange')
    ax3.set_ylim(0, 40000); ax3.set_xlabel('support stiffness per bearing [N/m]'); ax3.set_ylabel('undamped critical speed [rpm]')
    ax3.grid(alpha=0.3, which='both'); ax3.legend(fontsize=7, loc='center right')
    ax3.set_title('Critical speed map (A between bearings solid, B turbine overhung dotted)', fontsize=10)
    ax4 = fig.add_axes([0.53, 0.07, 0.44, 0.42])
    for name, st in (('A', '--'), (SEL, '-')):
        ub_ = pdat[name][3]
        for k, (c, a) in enumerate(ub_.items()):
            ax4.semilogy(fine / 1e3, a.max(axis=1), st, color='C%d' % k, lw=1.4 if name == SEL else 0.9, label='%s %s' % (name, c))
    ax4.axhline(API_LIM, color='tab:red', lw=1, label='API 617 limit %.0f um' % API_LIM)
    ax4.axvspan(0.95 * N_OP / 1e3, N_TRIP / 1e3, color='tab:green', alpha=0.15)
    ax4.set_xlabel('speed [k rpm]'); ax4.set_ylabel('journal vibration, worse bearing [um pk-pk]'); ax4.grid(alpha=0.3, which='both')
    ax4.legend(fontsize=7, ncol=2); ax4.set_title('Unbalance response, U = 6350 W/N per case (API 617)', fontsize=10)
    fig.suptitle('AURORA-1000 rotor dynamics (Timoshenko FE, gyroscopic, tilting-pad %.1e N/m; SFD %.1e N/m, %.0e Ns/m)' % (
        SUP['rigid']['kb'], SUP['sfd']['ks'], SUP['sfd']['cs']), fontsize=12)
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_rotordynamics.png')); print('written docs/img/a1000_rotordynamics.png')


if __name__ == '__main__':
    main()
