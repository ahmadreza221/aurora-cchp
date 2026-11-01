#!/usr/bin/env python3
"""GR180-CCHP E1 - rotor blade forced response at resonance (modal superposition, CalculiX + gmsh) driven by the NGV wake.

1. Blade (cad_out/engine/E1/E1_blade_piece.step, on a rigid hub, 730 C) prestressed at N (NLGEOM) -> *FREQUENCY
   (PERTURBATION): mass-normalised mode shapes phi_r and modal stresses sigma_r (CalculiX normalises phi^T M phi = 1).
2. Unit excitation: 1 MPa acting tangentially on one blade side (projected area |n_theta| dA, the gust lift direction).
   Generalised force Q_r = sum F_i . phi_r,i; resonant modal amplitude q_r = Q_r / (2 zeta omega_r^2);
   resonant dynamic stress per MPa of forcing = q_r * max vm(sigma_r).
3. Forcing amplitude of engine order k from the NGV wake (sim/cfd/e1_stage/ngv_results.json, harmonic k/21 of the
   pitchwise distribution at the rotor inlet plane): Sears gust lift dp = pi rho W v_perp |S(kr)| plus the static-pressure
   harmonic (half, phase-shifted across the passage); |S| ~ 1/sqrt(2 pi kr) for the reduced frequency kr = omega c / 2W.
4. Allowable dynamic stress: 1/3 of the 730 C high-cycle fatigue strength of cast IN713LC (~200 MPa at 1e7, R = -1)
   -> 65 MPa; reported as the forcing margin.
Run:  CCX=... python sim/engine/e1_forced_response.py [--N 109600] [--zeta 0.001]
Writes: sim/engine/fea/forced_response.json
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import e1_turbine_fea as F                                   # noqa: E402
import e1_blade_modal as BM                                  # noqa: E402
G = F.G

N_MODES = 8
ZETA = 0.001              # modal damping ratio (cast IN713LC material + small aero damping; blisk: no friction damping)
SIG_ALLOW = 65.0          # MPa dynamic, 1/3 of ~200 MPa HCF strength at 730 C
H_MESH = 0.30


def mesh_with_surface(step):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('blade'); gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', H_MESH)
    gmsh.option.setNumber('Mesh.CharacteristicLengthMin', 0.5 * H_MESH)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.model.mesh.generate(3)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(11)
    tt, tn = gmsh.model.mesh.getElementsByType(9)             # 6-node surface triangles
    gmsh.finalize()
    nodes = {int(t): xyz[i] for i, t in enumerate(nt)}
    els = []
    for e in en.reshape(-1, 10).astype(int):
        c = list(e[:4]); mids = list(e[4:])
        def mid(a, b):
            p = 0.5 * (nodes[a] + nodes[b]); return min(mids, key=lambda m: np.linalg.norm(nodes[m] - p))
        els.append(c + [mid(c[0], c[1]), mid(c[1], c[2]), mid(c[2], c[0]), mid(c[0], c[3]), mid(c[1], c[3]), mid(c[2], c[3])])
    tris = tn.reshape(-1, 6).astype(int)
    return nodes, els, tris


def unit_load(nodes, tris):
    """Nodal forces (N) of 1 MPa acting in -theta on the blade side with n_theta > 0 (projected area); T6 consistent
    loads for a uniform traction: corners 0, mid-side nodes A/3."""
    Fn = {}
    area_side = 0.0
    for t in tris:
        a, b, c = (nodes[t[0]], nodes[t[1]], nodes[t[2]])
        cen = (a + b + c) / 3.0
        r = math.hypot(cen[1], cen[2])
        if r < float(G.r_hub(np.clip(cen[0], G.X_PF, G.X_PR))) + 0.05 or r > G.R_TIP - 0.05:
            continue
        n = np.cross(b - a, c - a); A = 0.5 * np.linalg.norm(n)
        if A < 1e-12:
            continue
        n = n / (2 * A)
        th = math.atan2(cen[2], cen[1])
        et = np.array([0.0, -math.sin(th), math.cos(th)])
        nth = float(np.dot(n, et))
        if abs(nth) < 0.3:
            continue
        # one side only: the outward normal is not guaranteed by gmsh, so select the side by the sign of n.e_theta of the
        # outward normal estimated from the local blade thickness direction (cen relative to the camber mid-point)
        side = 1 if nth > 0 else -1
        Fn.setdefault('A', []).append((t, A * abs(nth), side, et))
    # pick the side with the larger projected area (pressure side of the cambered blade)
    sides = {1: 0.0, -1: 0.0}
    for t, Ap, s, et in Fn['A']:
        sides[s] += Ap
    s_use = max(sides, key=sides.get)
    loads = {}
    for t, Ap, s, et in Fn['A']:
        if s != s_use:
            continue
        f = -Ap * et                                          # 1 MPa x mm2 = 1 N, in -theta
        for k in t[3:]:
            loads[k] = loads.get(k, np.zeros(3)) + f / 3.0
        area_side += Ap
    return loads, area_side, sides


def run_modes(nodes, els, base, N, tag):
    E = float(np.interp(BM.T_BLADE, F.MAT_T, F.MAT_E)); om = N * 2 * math.pi / 60.0
    job = 'fr_' + tag
    with open(os.path.join(F.FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NBASE\n' + ''.join('%d,\n' % k for k in base))
        f.write('*MATERIAL, NAME=IN713LC\n*ELASTIC\n%.1f, %.3f\n*DENSITY\n%.3e\n' % (E, F.MAT_NU, F.RHO))
        f.write('*SOLID SECTION, ELSET=EALL, MATERIAL=IN713LC\n*BOUNDARY\nNBASE, 1, 3, 0.\n')
        f.write('*STEP, NLGEOM\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n*END STEP\n' % om**2)
        f.write('*STEP, PERTURBATION\n*FREQUENCY\n%d\n*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n' % N_MODES)
    F.run_ccx(job, threads=int(os.environ.get('E1_THREADS', 4)))
    freqs = []
    blk = open(os.path.join(F.FEA, job + '.dat')).read().split('E I G E N V A L U E   O U T P U T')[-1]
    for line in blk.splitlines():
        p = line.split()
        if len(p) == 5 and p[0].isdigit():
            freqs.append(float(p[3]))
    nd, blocks = F.read_frd(os.path.join(F.FEA, job + '.frd'))
    U = [b['data'] for b in blocks if b.get('name') == 'DISP'][-N_MODES:]
    S = [b['data'] for b in blocks if b.get('name') == 'STRESS'][-N_MODES:]
    return freqs[:N_MODES], U, S


def wake_forcing(eo, N):
    """pressure-difference amplitude (MPa) on the rotor blade from harmonic eo of the NGV wake at the rotor inlet"""
    f = os.path.join(ROOT, 'sim', 'cfd', 'e1_stage', 'ngv_results.json')
    if not os.path.exists(f):
        return None
    d = json.load(open(f)).get('harmonics')
    if not d or str(eo) not in d['by_eo']:
        return None
    h = d['by_eo'][str(eo)]
    rho, W, c = d['rho'], d['W'], d['chord_m']
    om = 2 * math.pi * eo * N / 60.0
    kr = om * c / (2 * W)
    S_sears = 1.0 / math.sqrt(2 * math.pi * kr) if kr > 0.5 else 1.0 / (1 + 2 * math.pi * kr) ** 0.5
    dp_gust = math.pi * rho * W * h['v_perp'] * S_sears
    dp = dp_gust + 0.5 * h['p']
    return dict(kr=kr, sears=S_sears, dp_gust_Pa=dp_gust, p_harm_Pa=h['p'], dp_Pa=dp, dp_MPa=dp * 1e-6, v_perp=h['v_perp'])


def main():
    a = sys.argv[1:]
    N = float(a[a.index('--N') + 1]) if '--N' in a else 109.6e3
    zeta = float(a[a.index('--zeta') + 1]) if '--zeta' in a else ZETA
    step = os.path.join(ROOT, 'cad_out', 'engine', 'E1', 'E1_blade_piece.step')
    nodes, els, tris = mesh_with_surface(step)
    base = BM.base_nodes(nodes)
    loads, Aside, sides = unit_load(nodes, tris)
    print('blade mesh %d nodes, %d C3D10, %d surface T6; loaded side projected area %.1f mm2 (sides %s)' % (
        len(nodes), len(els), len(tris), Aside, {k: round(v, 1) for k, v in sides.items()}), flush=True)
    freqs, U, S = run_modes(nodes, els, base, N, '%dk' % round(N / 1e3))
    res = dict(N=N, zeta=zeta, sig_allow=SIG_ALLOW, area_side_mm2=Aside, modes=[])
    rev = N / 60.0
    for r in range(len(freqs)):
        w = 2 * math.pi * freqs[r]
        Q = sum(float(np.dot(Fv, U[r][k][:3])) for k, Fv in loads.items() if k in U[r])
        q = abs(Q) / (2 * zeta * w * w)
        svm = {k: float(F.vm(np.array(v[:6]))) for k, v in S[r].items()}
        kmax = max(svm, key=svm.get)
        s_per_MPa = q * svm[kmax]
        eo = round(freqs[r] / rev)
        fw = wake_forcing(eo, N) if eo % 21 == 0 else None
        row = dict(mode=r + 1, f_Hz=freqs[r], eo_nearest=eo, Q_N=Q, stress_per_MPa=s_per_MPa,
                   stress_per_kPa=s_per_MPa * 1e-3, peak_at=[float(c) for c in nodes[kmax]],
                   dp_allow_kPa=SIG_ALLOW / s_per_MPa * 1e3 if s_per_MPa > 0 else None)
        if fw:
            row.update(forcing=fw, sigma_dyn=s_per_MPa * fw['dp_MPa'], margin=SIG_ALLOW / (s_per_MPa * fw['dp_MPa']) if fw['dp_MPa'] > 0 else None)
        res['modes'].append(row)
        print('F%d %7.0f Hz (EO %.2f) | resonant stress %.2f MPa per kPa forcing (zeta %.4f) | forcing allowed for %.0f MPa: %.2f kPa%s' % (
            r + 1, freqs[r], freqs[r] / rev, row['stress_per_kPa'], zeta, SIG_ALLOW, row['dp_allow_kPa'],
            ('  | EO%d wake: dp %.2f kPa (Sears %.3f, k %.1f) -> %.1f MPa, margin %.1f' % (
                eo, fw['dp_Pa'] / 1e3, fw['sears'], fw['kr'], row['sigma_dyn'], row['margin'])) if fw else ''), flush=True)
    json.dump(res, open(os.path.join(F.FEA, 'forced_response.json'), 'w'), indent=1, default=float)
    print('written', os.path.join(F.FEA, 'forced_response.json'))


if __name__ == '__main__':
    main()
