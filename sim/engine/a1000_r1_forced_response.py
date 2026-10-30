#!/usr/bin/env python3
"""AURORA-1000 R1 blisk: forced response at EO24 / EO48 / EO96 from the unsteady stator forcing (CFD) on the coupled
blade-disc cyclic modes (CalculiX), rev 5 vane counts NGV1 48 / NGV2 24.

1. Modes (--modes): the R1 cyclic sector of a1000_blisk_cyclic.py (same mesh, temperatures, NLGEOM prestress at
   15,000 rpm), one perturbation *FREQUENCY step per nodal diameter that the orders reach (EO k -> ND k mod 59 folded:
   EO24 -> ND24, EO48 -> ND11, EO96 -> ND22), with displacement and stress output. Both modes of each cos / sin pair are
   kept. Mass norm u^T M u from our own consistent C3D10 mass matrix (independent of the CalculiX normalisation).
2. Forcing: harmonics of the blade-surface pressure of one R1 blade in the 2-D mid-span URANS (sim/cfd/a1000_r1_forcing,
   rhoPimpleFoam, sliding 4 NGV1 : 5 R1 : 2 NGV2 sector) at 24 / 48 / 96 x shaft frequency, as complex p(s) on the
   pressure and suction sides vs the surface fraction s (LE 0 -> TE 1). Applied on the 3-D blade surface at the same
   (side, s) at every radius, coherent over the span (no spanwise phase, upper estimate).
3. Response of a tuned traveling-wave mode u at resonance: q = u^H f / (u^H M u 2 zeta w^2); vibratory stress =
   |sigma_u q| (von Mises of the harmonic amplitude, max over the cycle); off resonance the 1-dof factor
   1 / |1 - r^2 + 2 i zeta r| at the grid-band edges. Mistuning amplification MISTUNE on top.
4. Damping: material / structural 0.05-0.3 % of critical (cast MAR-M247 blisk, no friction joints) + aero damping by
   piston theory (p' = rho a v_n on both blade sides: zeta_a = sum rho a |u_n|^2 dA / (2 w u^T M u), local rho, a from
   the CFD); quoted, credited only at its lower half.
5. Criterion (replaces the 5 % frequency rule of EO96): resonant root stress x mistuning <= Goodman allowable / 2
   (sim/engine/a1000_turbine_checks.py: R1 root 32 MPa) at the lower-bound damping.
Run:  CCX=~/micromamba/envs/gr180/bin/ccx python sim/engine/a1000_r1_forced_response.py --modes   (~15 min, 4 threads)
      python sim/engine/a1000_r1_forced_response.py            (post: needs sim/cfd/a1000_r1_forcing/forcing.json)
Writes: sim/engine/fea/a1000_R1_modes.npz (not in git), sim/engine/fea/a1000_R1_forced_response.json,
        docs/img/a1000_R1_forced_response.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import e1_turbine_fea as F                                    # noqa: E402  (ccx runner, frd reader, von Mises)
import a1000_blisk_cyclic as BC                               # noqa: E402  (sector mesh, temperatures, materials)

FEA = os.path.join(HERE, 'fea')
CAD = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
FORCING = os.path.join(ROOT, 'sim', 'cfd', 'a1000_r1_forcing', 'forcing.json')
NPZ = os.path.join(FEA, 'a1000_R1_modes.npz')
N_OP, Z = 15000.0, 59
BAND = (14700.0, 15300.0)
# (EO, ND, families solved, family of interest): the nearest coupled family of each order (a1000_blisk_R1_cyclic.json)
ORDERS = [(24, 24, 2, 1), (48, 11, 4, 3), (96, 22, 7, 6)]
ZETA = (0.0005, 0.001, 0.003)                                  # material / structural damping range (critical ratio)
MISTUNE = 1.5                                                  # mistuning amplification (blisk, controlled tolerances)
GOODMAN_ROOT = None                                            # read from fea/a1000_turbine_checks.json
ROOT_BAND = 0.20                                               # root region: lowest 20 % of the blade span


# ------------------------------------------------------------------------------------------------ C3D10 mass matrix
def _tet10_mass_ref():
    """consistent mass matrix of the 10-node tetrahedron on the unit reference tet (volume 1/6), CalculiX node order
    (corners 1-4, mid 1-2, 2-3, 3-1, 1-4, 2-4, 3-4), by a collapsed Gauss rule (exact for the quartic integrand)"""
    g, w = np.polynomial.legendre.leggauss(6); g = 0.5 * (g + 1); w = 0.5 * w
    M = np.zeros((10, 10))
    for a, wa in zip(g, w):
        for b, wb in zip(g, w):
            for c, wc in zip(g, w):
                x = a; y = b * (1 - a); z = c * (1 - a) * (1 - b); J = (1 - a) ** 2 * (1 - b)
                L = (1 - x - y - z, x, y, z)
                N = np.array([L[0] * (2 * L[0] - 1), L[1] * (2 * L[1] - 1), L[2] * (2 * L[2] - 1), L[3] * (2 * L[3] - 1),
                              4 * L[0] * L[1], 4 * L[1] * L[2], 4 * L[2] * L[0], 4 * L[0] * L[3], 4 * L[1] * L[3], 4 * L[2] * L[3]])
                M += wa * wb * wc * J * np.outer(N, N)
    return M


def mass_norm(xyz, conn, u, rho):
    """u^T M u (u: (n_nodes, 3) indexed like xyz, conn: (n_el, 10) indices); straight-sided (affine) tets"""
    Mr = _tet10_mass_ref()
    p = xyz[conn[:, :4]]
    V = np.abs(np.einsum('ij,ij->i', np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), p[:, 3] - p[:, 0])) / 6.0
    ue = u[conn]                                                # (n_el, 10, 3)
    return float(np.sum(6 * rho * V * np.einsum('eia,ij,eja->e', ue.conj(), Mr, ue)).real)


def boundary_t6(conn):
    """outer faces of a C3D10 mesh as 6-node triangles (c1 c2 c3 m12 m23 m31) + the opposite corner of the element (for
    the outward normal), from the faces used by one element only"""
    fc = [((0, 1, 2), (4, 5, 6), 3), ((0, 3, 1), (7, 8, 4), 2), ((1, 3, 2), (8, 9, 5), 0), ((2, 3, 0), (9, 7, 6), 1)]
    seen = {}
    for e in conn:
        for (a, b, c), (m1, m2, m3), o in fc:
            key = tuple(sorted((e[a], e[b], e[c])))
            if key in seen: seen[key] = None
            else: seen[key] = (e[a], e[b], e[c], e[m1], e[m2], e[m3], e[o])
    return np.array([v for v in seen.values() if v is not None])


# ------------------------------------------------------------------------------------------------ 1. modes
def solve_modes():
    meta = json.load(open(os.path.join(CAD, 'A1000_R1_sector.json')))
    _argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
    sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine')); import a1000_turbine as A   # noqa: E401
    sys.argv = _argv
    meta['rh'] = A.row_radius('R1', 0.0)
    nodes, els, nl, nr = BC.mesh(os.path.join(CAD, 'A1000_R1_sector.step'), meta['theta0_deg'], meta['pitch_deg'],
                                 meta['rh'], BC.ROWS['R1'])
    print('R1 sector mesh: %d nodes, %d C3D10' % (len(nodes), len(els)), flush=True)
    # the input of a1000_blisk_cyclic.run() with one perturbation step per order and U / S output
    BC.ND_STEPS['R1'] = [(nd, nd, fam) for _, nd, fam, _ in ORDERS]
    job = 'a1000_cyc_R1_fr'
    run_ccx, parse = BC.F.run_ccx, BC.C.parse_dat              # write the deck only (no solve)
    BC.F.run_ccx, BC.C.parse_dat = (lambda *a, **k: None), (lambda p: {})
    try:
        BC.run('R1', nodes, els, nl, nr, meta, [nd for _, nd, _, _ in ORDERS], 'fr_tmp')
    finally:
        BC.F.run_ccx, BC.C.parse_dat = run_ccx, parse
    src = os.path.join(FEA, 'a1000_cyc_R1_fr_tmp.inp')
    deck = open(src).read().replace('*SELECT CYCLIC SYMMETRY MODES', '*NODE FILE\nU\n*EL FILE\nS\n*SELECT CYCLIC SYMMETRY MODES')
    deck = deck.replace('*STATIC\n', '*STATIC\n*NODE FILE\nU\n*EL FILE\nS\n', 1)
    open(os.path.join(FEA, job + '.inp'), 'w').write(deck)
    F.run_ccx(job, threads=int(os.environ.get('CCX_THREADS', 4)))
    freq = []                                                  # (nd, mode, Hz) in output order
    for line in open(os.path.join(FEA, job + '.dat')):
        p = line.split()
        if len(p) == 6 and p[0].isdigit() and p[1].isdigit(): freq.append((int(p[0]), int(p[1]), float(p[4])))
    nd_, blocks = F.read_frd(os.path.join(FEA, job + '.frd'))
    ids = np.array(sorted(nodes)); idx = {k: i for i, k in enumerate(ids)}
    xyz = np.array([nodes[k] for k in ids]); conn = np.array([[idx[k] for k in e] for e in els])
    def arr(b, nc):
        a = np.zeros((len(ids), nc))
        for k, v in b['data'].items():
            if k in idx: a[idx[k]] = v[:nc]
        return a
    U = [b for b in blocks if b['name'].startswith('DISP')]; S = [b for b in blocks if b['name'].startswith('STRESS')]
    print('frd: %d DISP, %d STRESS blocks, %d eigenvalues in the .dat; frd node count %d' % (len(U), len(S), len(freq), len(nd_)), flush=True)
    s_static = arr(S[0], 6)                                    # first block: the NLGEOM static step
    U, S = U[1:], S[1:]
    out = dict(xyz=xyz, conn=conn, s_static_vm=F.vm(s_static), rh=meta['rh'], nl=np.array([idx[k] for k in nl]),
               nr=np.array([idx[k] for k in nr]), freq=np.array([f for _, _, f in freq]),
               nd=np.array([n for n, _, _ in freq]))
    keep = []
    for i, (n, m, f) in enumerate(freq):
        eo = [o for o in ORDERS if o[1] == n][0]
        fam = (i - next(j for j, q in enumerate(freq) if q[0] == n)) // 2 + 1
        if fam != eo[3]: continue
        out['u_%d_%d' % (n, len(keep))] = arr(U[i], 3); out['s_%d_%d' % (n, len(keep))] = arr(S[i], 6)
        keep.append((n, fam, f, i))
    out['keep'] = np.array([(n, fam, f) for n, fam, f, _ in keep])
    np.savez_compressed(NPZ, **out)
    print('kept modes (ND, family, Hz):', [(n, fam, round(f)) for n, fam, f, _ in keep], '->', NPZ, flush=True)


# ------------------------------------------------------------------------------------------------ 2. forcing on the FE blade
def _turbine():
    _argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
    sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine')); import a1000_turbine as A   # noqa: E401
    sys.argv = _argv
    return A


def outline_param(P, q):
    """parameter tau in [0, 1) of the point of the closed polyline P (N, 2) nearest to each q (M, 2): (i + t) / N, and the
    distance (the outline runs TE -> +theta side -> LE -> -theta side -> TE, a1000_turbine / gg_turbine Section.outline)"""
    out_t, out_d = np.zeros(len(q)), np.zeros(len(q))
    B = np.roll(P, -1, 0); dv = B - P; L2 = (dv ** 2).sum(1)
    for k in range(0, len(q), 2000):
        qq = q[k:k + 2000]
        t = np.clip(((qq[:, None, :] - P[None]) * dv[None]).sum(2) / L2[None], 0, 1)
        D = ((P[None] + t[..., None] * dv[None] - qq[:, None, :]) ** 2).sum(2); i = D.argmin(1); j = np.arange(len(qq))
        out_t[k:k + 2000] = (i + t[j, i]) / len(P); out_d[k:k + 2000] = np.sqrt(D[j, i])
    return out_t, out_d


def blade_faces(d, A):
    """blade surface of the sector (both blade halves: the cut planes run through blade 0 and blade +1), with the
    outward normal, area, outline parameter tau at the local span section and the half (0: blade 0, 1: blade +1)"""
    xyz, conn = d['xyz'], d['conn']; tri = boundary_t6(conn)
    cut = np.zeros(len(xyz), bool); cut[d['nl']] = True; cut[d['nr']] = True
    c = xyz[tri[:, :3]].mean(1)
    n = np.cross(xyz[tri[:, 1]] - xyz[tri[:, 0]], xyz[tri[:, 2]] - xyz[tri[:, 0]]); area = 0.5 * np.linalg.norm(n, axis=1)
    n /= (2 * area)[:, None]; n *= np.sign(((c - xyz[tri[:, 6]]) * n).sum(1))[:, None]
    r = np.hypot(c[:, 1], c[:, 2]); th = np.arctan2(c[:, 2], c[:, 1])
    nrad = np.abs(n[:, 1] * np.cos(th) + n[:, 2] * np.sin(th))
    rh = np.array([A.r_hub(x) for x in c[:, 0]])
    keep = (r > rh + 0.2) & (nrad < 0.8) & ~cut[tri[:, :3]].all(1)
    tri, c, n, area, r, th = tri[keep], c[keep], n[keep], area[keep], r[keep], th[keep]
    pitch = 2 * math.pi / Z; half = (th > pitch / 2).astype(int); th0 = th - half * pitch
    spans = np.linspace(0, 1, 21); secs = A.design_row('R1', list(spans))
    xm = 0.5 * (A.X_LE['R1'] + A.X_TE['R1']); f = np.clip((r - A.r_hub(xm)) / A.height(xm), 0, 1)
    k = np.rint(f * 20).astype(int); tau = np.zeros(len(c)); dist = np.zeros(len(c))
    for j, sp in enumerate(spans):
        m = k == j
        if not m.any(): continue
        s = secs[sp]; pts = s.outline(140, 21)[0]; P = np.c_[pts[:, 0], s.r * np.arctan2(pts[:, 2], pts[:, 1])]
        tau[m], dist[m] = outline_param(P, np.c_[c[m, 0], s.r * th0[m]])
    # airfoil + root fillet (R 3 mm) only: the platform end faces (4.5 mm overhang, axial normals) lie further out
    a = dist < 3.5
    return dict(tri=tri[a], c=c[a], n=n[a], area=area[a], r=r[a], half=half[a], tau=tau[a], dist=dist[a], span=f[a])


def nodal_load(bf, p_hat, phase1, n_nodes):
    """complex nodal forces [N] of the harmonic pressure p_hat(tau) [MPa] on the blade faces (T6 with straight sides:
    a uniform face pressure goes to the mid-side nodes, A/3 each); faces of the blade +1 half carry the interblade phase"""
    pf = p_hat(bf['tau']) * np.where(bf['half'] == 1, phase1, 1.0)
    Fv = -(pf * bf['area'])[:, None] * bf['n']
    f = np.zeros((n_nodes, 3), complex)
    for j in (3, 4, 5): np.add.at(f, bf['tri'][:, j], Fv / 3.0)
    return f


def response(d, bf, nd, sign, p_hat, f_mode, rho_a):
    """resonant response of the traveling-wave mode U = u1 + sign i u2 (sector phase exp(-sign i sigma)) to the blade
    pressure p_hat; returns modal quantities and the nodal vibratory von Mises per unit of 1 / (2 zeta)"""
    keys = sorted(k for k in d.files if k.startswith('u_%d_' % nd))
    u1, u2 = d[keys[0]], d[keys[1]]; s1, s2 = d[keys[0].replace('u_', 's_')], d[keys[1].replace('u_', 's_')]
    U = u1 + sign * 1j * u2; S = s1 + sign * 1j * s2
    sig = 2 * math.pi * nd / Z; ph = np.exp(-sign * 1j * sig)            # blade +1 relative to blade 0
    f = nodal_load(bf, p_hat, ph, len(U))
    Q = np.sum(U.conj() * f); m = mass_norm(d['xyz'], d['conn'], U, 8.54e-9)
    w = 2 * math.pi * f_mode
    Un = np.einsum('fa,fa->f', U[bf['tri'][:, 3:6]].mean(1), bf['n'])     # face-normal mode displacement
    zeta_a = rho_a * np.sum(np.abs(Un) ** 2 * bf['area']) / (2 * w * m)    # piston theory, both blade sides
    q1 = abs(Q) / (m * w * w)                                             # x 1 / (2 zeta) at resonance
    phs = np.exp(1j * np.linspace(0, math.pi, 13))[:, None, None]
    blade = d['blade_nodes']
    vm = F.vm(np.real(S[blade][None] * q1 * phs)).max(0)                  # max over the cycle
    return dict(Q=Q, m=m, q1=q1, zeta_aero=zeta_a, vm1=vm, U=U)


def post():
    A = _turbine()
    d = dict(np.load(NPZ))
    xyz = d['xyz']; r = np.hypot(xyz[:, 1], xyz[:, 2]); rh = np.array([A.r_hub(x) for x in xyz[:, 0]])
    hx = np.array([A.height(x) for x in xyz[:, 0]])
    blade = np.where(r > rh + 0.05)[0]; d['blade_nodes'] = blade
    root = (r[blade] - rh[blade]) < ROOT_BAND * hx[blade]
    class _D(dict):
        files = property(lambda s: list(s.keys()))
    d = _D(d)
    bf = blade_faces(d, A)
    print('blade faces %d (blade 0 / +1 halves %d / %d), area %.0f mm2, max distance to the section %.2f mm' % (
        len(bf['tri']), (bf['half'] == 0).sum(), (bf['half'] == 1).sum(), bf['area'].sum(), bf['dist'].max()), flush=True)
    fc = json.load(open(FORCING))
    chk = json.load(open(os.path.join(FEA, 'a1000_turbine_checks.json')))
    g_root = chk['blades']['R1']['goodman_allow_root']
    rho_a = fc['rho_a_mid'] * 1e-12 * 1e3                                 # kg/m2/s -> t/mm2/s
    # the 2-D section passes ~6 % less than the meanline flow at the meanline pressures: forcing scaled with the dynamic
    # pressure (mass flow ratio squared, conservative)
    kq = max(1.0, (fc['flow']['mdot_meanline'] / fc['flow']['mdot_annulus_equiv']) ** 2)
    res = dict(goodman_root=g_root, limit=g_root / 2, mistune=MISTUNE, zeta=list(ZETA), forcing_scale=kq, orders={})
    for eo, nd, fam, fam_i in ORDERS:
        h = fc['harmonics'][str(eo)]; tau_c = np.array(fc['tau']); o = np.argsort(tau_c)
        pr, pi_ = np.array(h['re'])[o] * 1e-6 * kq, np.array(h['im'])[o] * 1e-6 * kq
        tt = np.r_[tau_c[o] - 1, tau_c[o], tau_c[o] + 1]
        p_hat = lambda t, pr=pr, pi_=pi_: np.interp(t, tt, np.r_[pr, pr, pr]) + 1j * np.interp(t, tt, np.r_[pi_, pi_, pi_])
        k = [q for q in d['keep'] if int(q[0]) == nd][0]; fm = float(k[2])
        # EO k: blade j leads blade 0 by exp(i k 2 pi j / Z): ND phase +sigma for k mod Z < Z/2, else -sigma
        sign = -1 if (eo % Z) < Z / 2 else +1
        R_ = response(d, bf, nd, sign, p_hat, fm, rho_a); Ro = response(d, bf, nd, -sign, p_hat, fm, rho_a)
        vm1 = R_['vm1']; i_pk = int(np.argmax(vm1)); i_rt = int(np.argmax(np.where(root, vm1, 0)))
        fb = [eo * n / 60 for n in BAND]; rb = [x / fm for x in fb]
        # below the grid band the order is crossed during start / stop only: forcing ~ dynamic pressure ~ (N / N_op)^2
        # (similar velocity triangles, density taken as at the design point: an upper estimate)
        kst = min(1.0, (fm * 60 / eo / N_OP) ** 2)
        def amp(rr, z): return 2 * z / abs(1 - rr * rr + 2j * z * rr)       # relative to resonance
        rows = []
        for z in ZETA:
            zt = z + R_['zeta_aero'] / 2                                    # aero damping: half credited
            s_root, s_pk = vm1[i_rt] / (2 * zt), vm1[i_pk] / (2 * zt)
            s_band = s_root * max(amp(x, zt) for x in rb) if (rb[0] - 1) * (rb[1] - 1) > 0 else s_root
            rows.append(dict(zeta_mech=z, zeta_total=zt, root_res=s_root, peak_res=s_pk, root_band=s_band,
                             root_res_mist=MISTUNE * s_root, root_band_mist=MISTUNE * s_band,
                             root_start_mist=MISTUNE * s_root * kst))
        pk = xyz[blade[i_pk]]; rt = xyz[blade[i_rt]]
        res['orders'][str(eo)] = dict(
            eo=eo, nd=nd, family=fam_i, f_mode=fm, f_band=fb, margin_band=[(fm - x) / x for x in fb],
            n_res_rpm=fm * 60 / eo, startup_forcing_factor=kst, Q_N_mm=abs(R_['Q']), Q_other_direction=abs(Ro['Q']), modal_mass=R_['m'],
            zeta_aero_piston=R_['zeta_aero'], p_rms_kPa=float(np.sqrt(np.mean(pr ** 2 + pi_ ** 2) / 2) * 1e3),
            peak_at=dict(x=float(pk[0]), r=float(np.hypot(pk[1], pk[2])), span=float((np.hypot(pk[1], pk[2]) - A.r_hub(pk[0])) / A.height(pk[0]))),
            root_at=dict(x=float(rt[0]), r=float(np.hypot(rt[1], rt[2]))), stress=rows)
        print('EO%-3d ND%-2d F%d %7.0f Hz (resonance at %.0f rpm, band margin %+.1f / %+.1f %%): |Q| %.3g N mm (other '
              'direction %.3g), zeta_aero(piston) %.4f %%' % (eo, nd, fam_i, fm, fm * 60 / eo, 100 * (fm - fb[0]) / fb[0],
                                                               100 * (fm - fb[1]) / fb[1], abs(R_['Q']), abs(Ro['Q']),
                                                               100 * R_['zeta_aero']), flush=True)
        for q in rows:
            print('   zeta %.2f %% (+aero/2 -> %.3f %%): root %.2f MPa at resonance (x%.1f mistuning %.2f), peak %.2f MPa '
                  '(span %.2f); in the grid band %.3f MPa' % (100 * q['zeta_mech'], 100 * q['zeta_total'], q['root_res'],
                                                              MISTUNE, q['root_res_mist'], q['peak_res'],
                                                              res['orders'][str(eo)]['peak_at']['span'], q['root_band']), flush=True)
    json.dump(res, open(os.path.join(FEA, 'a1000_R1_forced_response.json'), 'w'), indent=1, default=float)
    plot(res, fc)


def plot(res, fc):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=110)
    N = np.linspace(10000, 16000, 1201)
    for i, eo in enumerate(('24', '48', '96')):                 # speed sweep: steady-state response, zeta 0.1 % + aero / 2
        q = res['orders'][eo]; r1 = q['stress'][1]; zt = r1['zeta_total']; fm = q['f_mode']
        rr = int(eo) * N / 60 / fm
        a1.plot(N, MISTUNE * r1['root_res'] * (N / N_OP) ** 2 * 2 * zt / np.abs(1 - rr ** 2 + 2j * zt * rr), color='C%d' % i,
                label='EO%s -> ND%d F%d: resonance %.0f rpm' % (eo, q['nd'], q['family'], q['n_res_rpm']))
    a1.axvspan(*BAND, color='C2', alpha=0.12, zorder=0); a1.text(BAND[0] + 30, 0.012, 'grid band', fontsize=8)
    a1.axhline(res['goodman_root'], color='k', lw=1.2); a1.axhline(res['limit'], color='k', ls='--', lw=1)
    a1.set_yscale('log'); a1.set_ylim(0.01, 2000); a1.set_xlim(N[0], N[-1]); a1.grid(alpha=0.3, which='both')
    a1.set_xlabel('rotor speed [rpm] (forcing ~ (N / 15,000)^2, mode frequencies at 15,000 rpm)')
    a1.set_ylabel('R1 root vibratory stress, x%.1f mistuning [MPa]' % MISTUNE); a1.legend(fontsize=8, loc='upper left')
    a1.set_title('R1 forced response vs speed (zeta 0.1 %% + aero; CFD forcing x%.2f to the meanline flow)' % res['forcing_scale'],
                 fontsize=10)
    z = np.linspace(0.0003, 0.004, 60)
    for i, eo in enumerate(('24', '48', '96')):
        q = res['orders'][eo]; s1 = q['stress'][0]['root_res'] * 2 * q['stress'][0]['zeta_total']
        a2.plot(100 * z, MISTUNE * s1 / (2 * (z + q['zeta_aero_piston'] / 2)), color='C%d' % i,
                label='EO%s -> ND%d F%d (%.0f Hz)' % (eo, q['nd'], q['family'], q['f_mode']))
    a2.axhline(res['goodman_root'], color='k', lw=1.2); a2.text(0.01, res['goodman_root'] * 1.04, 'Goodman allowable %.0f MPa' % res['goodman_root'], fontsize=8)
    a2.axhline(res['limit'], color='k', ls='--', lw=1); a2.text(0.01, res['limit'] * 1.04, 'limit = Goodman / 2', fontsize=8)
    a2.axvspan(100 * ZETA[0], 100 * ZETA[-1], color='0.9', zorder=0)
    a2.set_xlabel('mechanical damping zeta [% of critical] (+ half the piston-theory aero damping)')
    a2.set_ylabel('resonant vibratory stress, R1 root, x%.1f mistuning [MPa]' % MISTUNE); a2.set_yscale('log')
    a2.grid(alpha=0.3, which='both'); a2.legend(fontsize=8); a2.set_xlim(0, 100 * z[-1])
    a2.set_title('R1 resonant root stress vs damping (design-point forcing; cyclic blisk modes, CalculiX)', fontsize=10)
    fig.tight_layout(); png = os.path.join(ROOT, 'docs', 'img', 'a1000_R1_forced_response.png'); fig.savefig(png)
    print('written', png)


if __name__ == '__main__':
    if '--modes' in sys.argv:
        solve_modes()
    else:
        post()
