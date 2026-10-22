#!/usr/bin/env python3
"""GR180-CCHP E1 - bore-less blisk modes by cyclic symmetry (CalculiX + gmsh): nodal diameters 0-14, ZZENF / interference check.

Model: 1/29 sector = disc cut by two radial planes +-pitch/2 about the blade-root footprint (they clear the fillet foot by
0.33 deg; cyclic symmetry only needs periodic cut faces, the blade above the hub may lean over them) + the blade piece,
built by tooling around cad/engine/gg_turbine.py (cad_out/engine/E1/E1_sector_boreless.step + .json with theta0 / pitch).
Periodic mesh on the cut faces; held at the weld face to the shaft (x 104.3, r <= 4: ND >= 2 exact, ND 0/1 couple with the
shaft, see sim/gr180_rotor.py). Metal temperature by radius (disc axis 480 C -> hub 730 C, blade 730 C) for E(T), no
thermal stress. Per speed: NLGEOM static (centrifugal) -> perturbation *FREQUENCY, nodal diameters 0..14.

Engine order k excites nodal diameter n = k mod 29 folded to 0..14 (n = min(k mod 29, 29 - k mod 29)).
Run:    python sim/engine/e1_blisk_cyclic.py            (CCX = path to ccx; gmsh python module)
Writes: sim/engine/fea/blisk_cyclic.json, cad_out/engine/E1/E1_blisk_zzenf.png
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
G = F.G

Z = G.Z_ROT
SPEEDS = [0.0, 115e3]                                        # others by f^2 = f0^2 + k N^2 (centrifugal stiffening)
N_PER_ND = 5
EO = [1, 2, 3, 4, 7, 21, 42]
H_MESH = 0.50
T_AXIS, T_HUB = 480.0, 730.0


def nd_of(k):
    m = k % Z
    return min(m, Z - m)


def mesh(step, theta0, pitch):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('sector'); gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
    def on_plane(tag, th):
        b = gmsh.model.getBoundingBox(2, tag)
        pts = gmsh.model.getValue(2, tag, [0.5, 0.5]) if False else None
        # sample the surface: all its boundary points must lie on the plane through the x axis at angle th
        nodes = []
        for dim, t in gmsh.model.getBoundary([(2, tag)], recursive=True):
            nodes.append(gmsh.model.getValue(0, t, []))
        n = np.array([-math.sin(th), math.cos(th)])          # plane normal in (y, z)
        return len(nodes) >= 3 and all(abs(p[1] * n[0] + p[2] * n[1]) < 1e-3 for p in nodes)
    th0, th1 = math.radians(theta0), math.radians(theta0 + pitch)
    left = [t for _, t in gmsh.model.getEntities(2) if on_plane(t, th0)]
    right = [t for _, t in gmsh.model.getEntities(2) if on_plane(t, th1)]
    if len(left) != len(right) or not left:
        raise RuntimeError('cut faces not found: left %s right %s' % (left, right))
    a = math.radians(pitch); c, s = math.cos(a), math.sin(a)
    gmsh.model.mesh.setPeriodic(2, right, left, [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1])
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', H_MESH); gmsh.option.setNumber('Mesh.CharacteristicLengthMin', 0.3 * H_MESH)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.model.mesh.generate(3)
    def surf_nodes(tags):
        out = set()
        for t in tags:
            nt, _, _ = gmsh.model.mesh.getNodes(2, t, includeBoundary=True); out.update(int(v) for v in nt)
        return sorted(out)
    nl, nr = surf_nodes(left), surf_nodes(right)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(11)
    gmsh.finalize()
    nodes = {int(t): xyz[i] for i, t in enumerate(nt)}
    els = []
    for e in en.reshape(-1, 10).astype(int):
        cn = list(e[:4]); mids = list(e[4:])
        def mid(p, q):
            m = 0.5 * (nodes[p] + nodes[q]); return min(mids, key=lambda k: np.linalg.norm(nodes[k] - m))
        els.append(cn + [mid(cn[0], cn[1]), mid(cn[1], cn[2]), mid(cn[2], cn[0]), mid(cn[0], cn[3]), mid(cn[1], cn[3]), mid(cn[2], cn[3])])
    return nodes, els, nl, nr


def temperature(p):
    x, r = p[0], math.hypot(p[1], p[2])
    rh = float(G.r_hub(np.clip(x, G.X_PF, G.X_PR)))
    return T_HUB if r >= rh else T_AXIS + (T_HUB - T_AXIS) * r / rh


def run(nodes, els, nl, nr, N, tag):
    om = N * 2 * math.pi / 60.0
    dep = set(nr)                                            # dependent cut-face nodes follow their tied partners (no SPC on them)
    weld = [k for k, p in nodes.items() if abs(p[0] - G.X_HUB) < 1e-3 and math.hypot(p[1], p[2]) <= 4.0 + 1e-6 and k not in dep]
    job = 'cyc_' + tag
    with open(os.path.join(F.FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NLEFT\n' + ''.join('%d,\n' % k for k in nl) + '*NSET, NSET=NRIGHT\n' + ''.join('%d,\n' % k for k in nr))
        f.write('*NSET, NSET=NWELD\n' + ''.join('%d,\n' % k for k in weld))
        f.write('*SURFACE, NAME=SLEFT, TYPE=NODE\nNLEFT\n*SURFACE, NAME=SRIGHT, TYPE=NODE\nNRIGHT\n')
        f.write('*TIE, NAME=CYC, CYCLIC SYMMETRY, ADJUST=NO\nSRIGHT, SLEFT\n')
        f.write('*CYCLIC SYMMETRY MODEL, N=%d, NGRAPH=1, TIE=CYC\n0., 0., 0., 1., 0., 0.\n' % Z)
        f.write('*MATERIAL, NAME=IN713LC\n*ELASTIC\n' + ''.join('%.1f, %.3f, %.1f\n' % (e, F.MAT_NU, t) for e, t in zip(F.MAT_E, F.MAT_T)))
        f.write('*DENSITY\n%.3e\n*SOLID SECTION, ELSET=EALL, MATERIAL=IN713LC\n' % F.RHO)
        f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\n' + ''.join('%d, %.1f\n' % (k, temperature(p)) for k, p in nodes.items()))
        f.write('*BOUNDARY\nNWELD, 1, 3, 0.\n')
        if N > 0:
            f.write('*STEP, NLGEOM\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n*END STEP\n' % om**2)
        f.write('*STEP%s\n*FREQUENCY\n%d\n*SELECT CYCLIC SYMMETRY MODES, NMIN=0, NMAX=%d\n*END STEP\n'
                % ('' if N == 0 else ', PERTURBATION', N_PER_ND, Z // 2))
    F.run_ccx(job, threads=4)
    txt = open(os.path.join(F.FEA, job + '.dat')).read()
    res = {}
    for blk in txt.split('E I G E N V A L U E   O U T P U T')[1:]:
        nd = None
        head = blk[:400].upper()
        for line in blk.splitlines()[:12]:
            if 'NODAL DIAMETER' in line.upper():
                try: nd = int(line.split()[-1])
                except ValueError: pass
        fr = []
        for line in blk.splitlines():
            p = line.split()
            if len(p) == 5 and p[0].isdigit():
                fr.append(float(p[3]))
            elif fr and p and not p[0].replace('.', '').isdigit():
                if len(fr) >= N_PER_ND: break
        if nd is None: nd = len(res)
        res[nd] = fr[:N_PER_ND]
    return res, len(weld)


def main():
    step = os.path.join(ROOT, 'cad_out', 'engine', 'E1', 'E1_sector_boreless.step')
    meta = json.load(open(os.path.join(ROOT, 'cad_out', 'engine', 'E1', 'E1_sector_boreless.json')))
    nodes, els, nl, nr = mesh(step, meta['theta0_deg'], meta['pitch_deg'])
    print('sector mesh: %d nodes, %d C3D10, cut faces %d / %d nodes' % (len(nodes), len(els), len(nl), len(nr)), flush=True)
    table = {}
    for N in SPEEDS:
        res, nw = run(nodes, els, nl, nr, N, '%dk' % (N / 1e3))
        table[N] = res
        print('%5.0fk rpm (weld nodes %d):' % (N / 1e3, nw), flush=True)
        for nd in sorted(res):
            print('   ND %2d: %s' % (nd, '  '.join('%7.0f' % f for f in res[nd])), flush=True)
    # interference: EO k at speed N excites ND nd_of(k) at k*N/60
    print('interference check (mode family m of ND n vs EO k with n = k folded), margin at 115k and crossings 100-120k:')
    hits = []
    for k in EO:
        n = nd_of(k)
        for m in range(N_PER_ND):
            f0, f1 = table[0.0][n][m], table[115e3][n][m]
            sp = np.linspace(0.0, 130e3, 131); fs = np.sqrt(f0**2 + (f1**2 - f0**2) * (sp / 115e3)**2)
            g = fs - k * sp / 60.0
            f115 = table[115e3][n][m]; marg = (f115 - k * 115e3 / 60) / (k * 115e3 / 60)
            cr = [sp[i] + (sp[i + 1] - sp[i]) * g[i] / (g[i] - g[i + 1]) for i in range(len(sp) - 1) if g[i] * g[i + 1] <= 0 and g[i] != g[i + 1]]
            cr_band = [c for c in cr if 100e3 <= c <= 120e3]
            if abs(marg) < 0.25 or cr_band:
                hits.append((k, n, m + 1, f115, marg, cr_band))
                print('  EO%-2d -> ND%-2d family %d: %7.0f Hz at 115k, margin %+6.1f %%%s' % (k, n, m + 1, f115, 100 * marg,
                      ('  CROSSING at %s k rpm' % ', '.join('%.1f' % (c / 1e3) for c in cr_band)) if cr_band else ''), flush=True)
    json.dump(dict(speeds=SPEEDS, freqs={str(int(N)): {str(n): v for n, v in r.items()} for N, r in table.items()},
                   hits=hits, mesh_h=H_MESH), open(os.path.join(F.FEA, 'blisk_cyclic.json'), 'w'), indent=1, default=float)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
    r115 = table[115e3]; nds = sorted(r115)
    for m in range(N_PER_ND):
        ax.plot(nds, [r115[n][m] for n in nds], 'o-', lw=1.6, label='family %d' % (m + 1))
    for k in EO:
        n = nd_of(k); fk = k * 115e3 / 60
        ax.plot([n], [fk], 'kx', ms=11, mew=2); ax.annotate(' EO%d' % k, (n, fk), fontsize=9)
        ax.fill_between([n - 0.3, n + 0.3], fk * 0.9, fk * 1.1, color='k', alpha=0.08)
    ax.set_xlabel('nodal diameter'); ax.set_ylabel('frequency at 115k rpm [Hz]'); ax.set_xticks(range(0, Z // 2 + 1))
    ax.set_title('GR180 E1 bore-less blisk: ZZENF (interference) at 115k, x = engine-order excitation (+-10 %% band)')
    ax.grid(alpha=0.3); ax.legend(fontsize=8); fig.tight_layout()
    png = os.path.join(ROOT, 'cad_out', 'engine', 'E1', 'E1_blisk_zzenf.png'); fig.savefig(png); print('written', png)


if __name__ == '__main__':
    main()
