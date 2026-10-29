#!/usr/bin/env python3
"""AURORA-1000 turbine blades: centrifugal stress (NLGEOM) and natural frequencies with stress stiffening -> Campbell
diagram and engine-order interference (CalculiX + gmsh). Same method as sim/engine/e1_blade_modal.py (blade on a rigid hub,
metal at the rotor-relative gas temperature, MAR-M247), for the two rotor rows R1 / R2.

Excitations (engine orders): 1-4 (single can combustor, inlet distortion), 5 (exhaust struts), the NGV counts upstream /
downstream (R1: 47 N1 wakes, 33 N2 potential field; R2: 33 N2 wakes, 47 N1 wakes carried through) and 2x the upstream count.
Operating speed 15,000 rpm fixed (grid frequency +-2 %), overspeed trip 16,500 rpm; start-up crossings below 14,000 rpm are
passed in seconds.
Input:  cad_out/engine/A1000/A1000_R1_blade.step, A1000_R2_blade.step   (cad/engine/a1000_turbine.py --cad)
Run:    python sim/engine/a1000_blade_fea.py [R1|R2]    (CCX = path to ccx)
Writes: sim/engine/fea/a1000_blade_<row>.json, cad_out/engine/A1000/A1000_<row>_campbell.png
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

DES = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
FEA = os.path.join(HERE, 'fea')
N_OP, N_TRIP = 15000.0, 16500.0
SPEEDS = [0.0, 5000.0, 10000.0, 13000.0, 15000.0, 16500.0]
N_MODES = 8
# MAR-M247 (cast, equiaxed): typical data; E [MPa] vs T [C]
MAT_T = np.array([20., 400., 600., 800., 900., 1000.])
MAT_E = np.array([200e3, 186e3, 176e3, 163e3, 156e3, 148e3])
MAT_YS = np.array([815., 800., 820., 830., 770., 590.])        # 0.2 % yield, typical
RHO = 8.54e-9                                                   # t/mm3
ROWS = dict(R1=dict(T=870.0, EO=[1, 2, 3, 4, 5, 33, 47, 94], h=0.8),
            R2=dict(T=735.0, EO=[1, 2, 3, 4, 5, 33, 47, 66], h=1.1))


def mesh(step, h):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('blade'); gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', h); gmsh.option.setNumber('Mesh.CharacteristicLengthMin', 0.15 * h)
    gmsh.option.setNumber('Mesh.Algorithm', 1); gmsh.option.setNumber('Mesh.Algorithm3D', 4)   # MeshAdapt + Frontal: the
    # Delaunay / HXT defaults fail on the thin round TE (surface facets intersect near the TE at mid span)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.model.mesh.generate(3)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(11)
    gmsh.finalize()
    nodes = {int(t): xyz[i] for i, t in enumerate(nt)}
    els = []
    for e in en.reshape(-1, 10).astype(int):
        c = list(e[:4]); mids = list(e[4:])
        def mid(a, b):
            p = 0.5 * (nodes[a] + nodes[b]); return min(mids, key=lambda m: np.linalg.norm(nodes[m] - p))
        els.append(c + [mid(c[0], c[1]), mid(c[1], c[2]), mid(c[2], c[0]), mid(c[0], c[3]), mid(c[1], c[3]), mid(c[2], c[3])])
    return nodes, els


def run(nodes, els, base, N, tag, T, static_out=False):
    E = float(np.interp(T, MAT_T, MAT_E)); om = N * 2 * math.pi / 60
    job = 'a1000_%s' % tag
    with open(os.path.join(FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NBASE\n' + ''.join('%d,\n' % k for k in base))
        f.write('*MATERIAL, NAME=MARM247\n*ELASTIC\n%.1f, 0.30\n*DENSITY\n%.3e\n' % (E, RHO))
        f.write('*SOLID SECTION, ELSET=EALL, MATERIAL=MARM247\n*BOUNDARY\nNBASE, 1, 3, 0.\n')
        if N > 0:
            f.write('*STEP, NLGEOM\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n' % om**2)
            f.write('*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n' if static_out else '*END STEP\n')
        f.write('*STEP%s\n*FREQUENCY\n%d\n*END STEP\n' % ('' if N == 0 else ', PERTURBATION', N_MODES))
    F.run_ccx(job, threads=4)
    txt = open(os.path.join(FEA, job + '.dat')).read().split('E I G E N V A L U E   O U T P U T')[-1]
    fr = []
    for line in txt.splitlines():
        p = line.split()
        if len(p) == 5 and p[0].isdigit(): fr.append(float(p[3]))
    res = dict(freqs=fr[:N_MODES])
    if static_out:
        _, blocks = F.read_frd(os.path.join(FEA, job + '.frd'))
        S = [b for b in blocks if b['name'].startswith('STRESS')][0]['data']
        vm = {k: float(F.vm(np.array(v[:6]))) for k, v in S.items()}
        k_max = max(vm, key=vm.get)
        res.update(vm_max=vm[k_max], vm_max_at=[float(c) for c in nodes[k_max]])
        # mean radial stress over a plane 1 fillet radius above the hub (gross section, = P/A check)
        res['vm_p99'] = float(np.percentile(list(vm.values()), 99.0))
    return res


def main():
    row = sys.argv[1] if len(sys.argv) > 1 else 'R1'
    cfg = ROWS[row]
    rh = DES[row]['sections'][0]['r']
    nodes, els = mesh(os.path.join(OUT, 'A1000_%s_blade.step' % row), cfg['h'])
    base = [k for k, p in nodes.items() if math.hypot(p[1], p[2]) <= rh + 0.02]
    print('%s mesh: %d nodes, %d C3D10, %d base nodes, metal %.0f C' % (row, len(nodes), len(els), len(base), cfg['T']), flush=True)
    table, stress = {}, None
    for N in SPEEDS:
        r = run(nodes, els, base, N, '%s_%dk' % (row, N / 1e3), cfg['T'], static_out=(N == N_OP))
        table[N] = r['freqs']
        if N == N_OP: stress = r
        print('  %6.0f rpm: ' % N + ' '.join('%7.0f' % f for f in r['freqs']), flush=True)
    ys = float(np.interp(cfg['T'], MAT_T, MAT_YS))
    print('  15k: von Mises max %.0f MPa at r %.1f (99th pct %.0f); yield %.0f MPa at %.0f C' % (
        stress['vm_max'], math.hypot(*stress['vm_max_at'][1:]), stress['vm_p99'], ys, cfg['T']))
    sp = np.array(SPEEDS); res = []
    for m in range(N_MODES):
        fm = np.array([table[N][m] for N in SPEEDS])
        f_op = float(np.interp(N_OP, sp, fm))
        for eo in cfg['EO']:
            fe = eo * N_OP / 60
            marg = (f_op - fe) / fe
            g = fm - eo * sp / 60
            cross = [float(sp[i] + (sp[i + 1] - sp[i]) * g[i] / (g[i] - g[i + 1])) for i in range(len(sp) - 1)
                     if g[i] * g[i + 1] < 0]
            res.append(dict(mode=m + 1, eo=eo, f_op=f_op, margin=marg, crossings=cross))
    crit = [r for r in res if abs(r['margin']) < 0.10 or any(14000 <= c <= N_TRIP for c in r['crossings'])]
    print('  interference at 15,000 rpm (|margin| < 10 %% or crossing 14k-16.5k):')
    for r in crit:
        print('    F%d x EO%-3d  f %7.0f Hz  margin %+5.1f %%  crossings %s' % (
            r['mode'], r['eo'], r['f_op'], 100 * r['margin'], ', '.join('%.0f' % c for c in r['crossings']) or '-'))
    json.dump(dict(row=row, speeds=SPEEDS, freqs={str(int(k)): v for k, v in table.items()}, stress=stress, yield_MPa=ys,
                   metal_C=cfg['T'], interference=res, critical=crit), open(os.path.join(FEA, 'a1000_blade_%s.json' % row), 'w'),
              indent=1, default=float)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 7), dpi=120)
    for m in range(N_MODES):
        ax.plot(sp / 1e3, [table[N][m] for N in SPEEDS], 'o-', lw=1.6, label='F%d' % (m + 1))
    nn = np.linspace(0, N_TRIP * 1.05, 50); top = max(max(v) for v in table.values()) * 1.1
    for eo in cfg['EO']:
        ax.plot(nn / 1e3, eo * nn / 60, 'k--' if eo > 10 else 'k:', lw=0.8)
        y = eo * nn[-1] / 60
        if y < top: ax.text(nn[-1] / 1e3, y, ' EO%d' % eo, fontsize=8, va='center')
    ax.axvline(N_OP / 1e3, color='tab:green', lw=1.5, label='operating 15,000 rpm'); ax.axvline(N_TRIP / 1e3, color='tab:red', lw=1, ls='--', label='trip')
    ax.set_ylim(0, top); ax.set_xlim(0, N_TRIP * 1.1 / 1e3); ax.grid(alpha=0.3); ax.legend(fontsize=8, loc='upper left')
    ax.set_xlabel('speed [k rpm]'); ax.set_ylabel('frequency [Hz]')
    ax.set_title('AURORA-1000 %s blade Campbell diagram (MAR-M247 %.0f C, rigid hub)' % (row, cfg['T']))
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'A1000_%s_campbell.png' % row)); print('  written')


if __name__ == '__main__':
    main()
