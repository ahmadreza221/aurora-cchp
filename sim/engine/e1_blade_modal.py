#!/usr/bin/env python3
"""GR180-CCHP E1 - rotor blade natural frequencies with centrifugal stiffening, Campbell diagram (CalculiX + gmsh).

One blade (with its root fillet, the part above the hub surface) fixed on the hub surface (rigid disc: frequencies slightly
high vs the real blisk, where disc flexibility lowers the low nodal-diameter modes), metal at the blade temperature.
Per speed: nonlinear static step with the centrifugal load (NLGEOM) -> *FREQUENCY step on the pre-stressed blade.

Excitations (engine orders): 1-4 (unbalance, inlet / combustor non-uniformity), 8 (E2 injectors), 21 (NGV vanes), 42.

Input:  blade STEP (default cad_out/engine/E1/E1_blade_piece.step; written by cad/engine/gg_turbine.py tooling or
        any FreeCAD run that exports the blade piece: blade_f.cut(disc_f), largest solid)
Run:    python sim/engine/e1_blade_modal.py [blade.step]      (CCX = path to ccx; gmsh python module)
Writes: sim/engine/fea/blade_modal.json, cad_out/engine/E1/E1_blade_campbell.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import e1_turbine_fea as F                                   # noqa: E402  (ccx runner, material tables)
G = F.G

T_BLADE = 730.0                                              # C, uniform blade metal temperature (F.T_BLADE)
SPEEDS = [0.0, 40e3, 80e3, 100e3, 115e3, 120e3, 130e3]
N_MODES = 8
EO = [1, 2, 3, 4, 8, 21, 42]
N_OP = (100e3, 120e3)                                        # continuous operating band (design 115k, trip 120k)
H_MESH = 0.30


def mesh(step):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('blade'); gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', H_MESH)
    gmsh.option.setNumber('Mesh.CharacteristicLengthMin', 0.5 * H_MESH)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.model.mesh.generate(3)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(11)            # 10-node tetrahedra
    gmsh.finalize()
    nodes = {int(t): xyz[i] for i, t in enumerate(nt)}
    els = []
    for e in en.reshape(-1, 10).astype(int):
        c = list(e[:4]); mids = list(e[4:])
        def mid(a, b):                                       # the mid-edge node of corners a, b (ordering independent)
            p = 0.5 * (nodes[a] + nodes[b])
            return min(mids, key=lambda m: np.linalg.norm(nodes[m] - p))
        # CalculiX C3D10: corners 1-4, then edges 1-2, 2-3, 3-1, 1-4, 2-4, 3-4
        els.append(c + [mid(c[0], c[1]), mid(c[1], c[2]), mid(c[2], c[0]), mid(c[0], c[3]), mid(c[1], c[3]), mid(c[2], c[3])])
    return nodes, els


def base_nodes(nodes, tol=0.01):
    """nodes on the hub surface (the blade piece is cut by the disc there)"""
    out = []
    for k, p in nodes.items():
        x, r = p[0], math.hypot(p[1], p[2])
        if r <= float(G.r_hub(np.clip(x, G.X_PF, G.X_PR))) + tol:
            out.append(k)
    return out


def run_speed(nodes, els, base, N, tag):
    E = float(np.interp(T_BLADE, F.MAT_T, F.MAT_E))
    om = N * 2 * math.pi / 60.0
    job = 'modal_' + tag
    with open(os.path.join(F.FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NBASE\n' + ''.join('%d,\n' % k for k in base))
        f.write('*MATERIAL, NAME=IN713LC\n*ELASTIC\n%.1f, %.3f\n*DENSITY\n%.3e\n' % (E, F.MAT_NU, F.RHO))
        f.write('*SOLID SECTION, ELSET=EALL, MATERIAL=IN713LC\n*BOUNDARY\nNBASE, 1, 3, 0.\n')
        if N > 0:
            f.write('*STEP, NLGEOM\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n*END STEP\n' % om**2)
        f.write('*STEP%s\n*FREQUENCY\n%d\n*NODE FILE\nU\n*END STEP\n' % ('' if N == 0 else ', PERTURBATION', N_MODES))
    F.run_ccx(job, threads=4)
    freqs = []
    with open(os.path.join(F.FEA, job + '.dat')) as fd:
        txt = fd.read()
    blk = txt.split('E I G E N V A L U E   O U T P U T')[-1]
    for line in blk.splitlines():
        p = line.split()
        if len(p) == 5 and p[0].isdigit():
            freqs.append(float(p[3]))                        # MODE, EIGENVALUE, OMEGA rad/s, OMEGA Hz (real), imag
    return freqs[:N_MODES]


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'cad_out', 'engine', 'E1', 'E1_blade_piece.step')
    nodes, els = mesh(step)
    base = base_nodes(nodes)
    print('mesh: %d nodes, %d C3D10, %d base nodes (hub surface)' % (len(nodes), len(els), len(base)), flush=True)
    table = {}
    for N in SPEEDS:
        fr = run_speed(nodes, els, base, N, '%dk' % (N / 1e3))
        table[N] = fr
        print('%6.0fk rpm: ' % (N / 1e3) + '  '.join('F%d %6.0f' % (i + 1, f) for i, f in enumerate(fr)), flush=True)
    # crossings with the engine orders inside / near the operating band
    cross = []
    sp = np.array(SPEEDS)
    for m in range(N_MODES):
        fm = np.array([table[N][m] for N in SPEEDS])
        for eo in EO:
            g = fm - eo * sp / 60.0
            for i in range(len(sp) - 1):
                if g[i] * g[i + 1] <= 0 and g[i] != g[i + 1]:
                    Nc = sp[i] + (sp[i + 1] - sp[i]) * g[i] / (g[i] - g[i + 1])
                    fc = np.interp(Nc, sp, fm)
                    margin = min(abs(Nc - N_OP[0]), abs(Nc - N_OP[1])) / 1e3 if not (N_OP[0] <= Nc <= N_OP[1]) else 0.0
                    cross.append(dict(mode=m + 1, eo=eo, N=Nc, f=fc, in_band=N_OP[0] <= Nc <= N_OP[1], margin_k=margin))
    print('crossings (mode x EO): ' + ('none' if not cross else ''))
    for c in sorted(cross, key=lambda c: c['N']):
        print('  F%d x EO%-2d at %6.1fk rpm (%5.0f Hz)%s' % (c['mode'], c['eo'], c['N'] / 1e3, c['f'],
              '  <-- IN OPERATING BAND' if c['in_band'] else '  (%.1fk outside the band)' % c['margin_k']))
    # 115k margins to the nearest EO line per mode
    print('design 115k: frequency margin to the nearest EO line')
    for m in range(N_MODES):
        f = table[115e3][m]; n_rev = 115e3 / 60
        eo_near = min(EO, key=lambda e: abs(f - e * n_rev))
        print('  F%d %6.0f Hz = %5.2f x rev; nearest EO%-2d (%6.0f Hz): margin %+5.1f %%' % (m + 1, f, f / n_rev, eo_near, eo_near * n_rev,
                                                                                         100 * (f - eo_near * n_rev) / (eo_near * n_rev)))
    json.dump(dict(speeds=SPEEDS, freqs={str(int(k)): v for k, v in table.items()}, crossings=cross, T_blade=T_BLADE, mesh_h=H_MESH),
              open(os.path.join(F.FEA, 'blade_modal.json'), 'w'), indent=1, default=float)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
    spk = sp / 1e3
    for m in range(N_MODES):
        ax.plot(spk, [table[N][m] for N in SPEEDS], 'o-', lw=1.8, label='F%d' % (m + 1))
    nn = np.linspace(0, max(SPEEDS), 50)
    for eo in EO:
        ax.plot(nn / 1e3, eo * nn / 60, 'k--' if eo in (21, 42) else 'k:', lw=0.9)
        y = eo * nn[-1] / 60
        if y < ax.get_ylim()[1] * 1.6: ax.text(nn[-1] / 1e3, y, ' EO%d' % eo, fontsize=8, va='center')
    ax.axvspan(N_OP[0] / 1e3, N_OP[1] / 1e3, color='tab:green', alpha=0.12, label='operating band')
    ax.axvline(115, color='tab:green', lw=1)
    top = max(max(v) for v in table.values()) * 1.1
    ax.set_ylim(0, top); ax.set_xlim(0, max(SPEEDS) / 1e3 * 1.08)
    ax.set_xlabel('rotor speed [k rpm]'); ax.set_ylabel('frequency [Hz]')
    ax.set_title('GR180 E1 rotor blade Campbell diagram (blade on rigid hub, %d C)' % T_BLADE); ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3); fig.tight_layout()
    png = os.path.join(ROOT, 'cad_out', 'engine', 'E1', 'E1_blade_campbell.png'); os.makedirs(os.path.dirname(png), exist_ok=True)
    fig.savefig(png); print('written', png)


if __name__ == '__main__':
    main()
