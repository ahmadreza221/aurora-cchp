#!/usr/bin/env python3
"""AURORA-1000 blisk discs (R1, R2): axisymmetric CalculiX analysis (CAX6) of the bore-less cast MAR-M247 disc at 15,000 rpm
and at the 16,500 rpm trip speed: centrifugal load of the disc, blade pull on the platform, steady radial temperature field
(rim at the platform metal temperature, centre cooled by compressor purge air) -> von Mises, mean hoop stress, burst margin.

Run:  python sim/engine/a1000_disc_fea.py            (CCX = path to ccx; needs a1000 blade masses from A1000_parts.json)
Writes: sim/engine/fea/a1000_disc.json
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
import e1_turbine_fea as F                                    # noqa: E402
sys.argv_saved = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_turbine as A                                     # noqa: E402
sys.argv = sys.argv_saved

FEA = os.path.join(HERE, 'fea')
PARTS = json.load(open(os.path.join(ROOT, 'cad_out', 'engine', 'A1000', 'A1000_parts.json')))
MAT_T = np.array([20., 400., 600., 800., 900.])
MAT_E = np.array([200e3, 186e3, 176e3, 163e3, 156e3])
MAT_A = np.array([11.0, 12.6, 13.4, 14.4, 15.0]) * 1e-6
MAT_YS = np.array([815., 800., 820., 830., 770.])
MAT_UTS = np.array([965., 980., 1000., 965., 830.])
RHO = 8.54e-9
TEMP = dict(R1=(450.0, 800.0), R2=(420.0, 690.0))          # (centre, rim) metal temperature [C]


def mesh(poly, h=2.0):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0); gmsh.model.add('disc')
    pts = [gmsh.model.occ.addPoint(r, x, 0, h) for x, r in poly]      # ccx axisymmetric: x = radius, y = axial
    lines = [gmsh.model.occ.addLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    s = gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(lines)]); gmsh.model.occ.synchronize()
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', h); gmsh.option.setNumber('Mesh.ElementOrder', 2)
    gmsh.option.setNumber('Mesh.SecondOrderLinear', 1); gmsh.model.mesh.generate(2)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(9)                     # 6-node triangles
    gmsh.finalize()
    nodes = {int(t): xyz[i][:2] for i, t in enumerate(nt)}
    els = []
    for e in en.reshape(-1, 6).astype(int):
        a, b, c = e[:3]
        area = 0.5 * ((nodes[b][0] - nodes[a][0]) * (nodes[c][1] - nodes[a][1]) - (nodes[c][0] - nodes[a][0]) * (nodes[b][1] - nodes[a][1]))
        els.append(list(e) if area > 0 else [a, c, b, e[5], e[4], e[3]])
    return nodes, els


def run(row, N, tag):
    poly = A.disc_profile(row); nodes, els = mesh(poly)
    rh = A.row_radius(row, 0.0); x0, x1 = A.X_LE[row] - A.PLAT_OVH, A.X_TE[row] + A.PLAT_OVH
    # blade pull per blade: mass and centroid radius of the blade piece (above the platform)
    m_b = PARTS['A1000_%s_blade' % row]['mass_kg']
    r_cg = 0.5 * (A.row_radius(row, 0.0) + A.row_radius(row, 1.0)) - 0.10 * (A.row_radius(row, 1.0) - A.row_radius(row, 0.0))
    om = N * 2 * math.pi / 60
    Fb = m_b * r_cg * 1e-3 * om**2                                    # N
    Zb = A.Z[row]
    Tc, Tr = TEMP[row]
    Tn = {k: Tc + (Tr - Tc) * (v[0] / rh) ** 2 for k, v in nodes.items()}
    # consistent nodal forces on the platform top edge (r = rh): total = Z * Fb (full 360 deg in ccx axisymmetric)
    cl = {}; L = 0.0
    for e in els:
        for (i, j, m) in ((0, 1, 3), (1, 2, 4), (2, 0, 5)):
            a, b = nodes[e[i]], nodes[e[j]]
            if abs(a[0] - rh) < 1e-6 and abs(b[0] - rh) < 1e-6:
                dl = abs(a[1] - b[1]); L += dl
                for n_, w in ((e[i], 1 / 6), (e[j], 1 / 6), (e[m], 2 / 3)): cl[n_] = cl.get(n_, 0.0) + w * dl
    cl = {k: v / L * Zb * Fb for k, v in cl.items()}
    job = 'a1000_disc_%s_%s' % (row, tag)
    with open(os.path.join(FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f\n' % (k, v[0], v[1]) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=CAX6, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        fix = min(nodes, key=lambda k: nodes[k][0] + abs(nodes[k][1] - 0.5 * (x0 + x1)) * 0.01)
        f.write('*NSET, NSET=NFIX\n%d,\n' % fix)
        f.write('*MATERIAL, NAME=MARM247\n*ELASTIC\n' + ''.join('%.1f, 0.30, %.1f\n' % (e, t) for e, t in zip(MAT_E, MAT_T)))
        f.write('*EXPANSION, ZERO=20.\n' + ''.join('%.3e, %.1f\n' % (a, t) for a, t in zip(MAT_A, MAT_T)))
        f.write('*DENSITY\n%.3e\n*SOLID SECTION, ELSET=EALL, MATERIAL=MARM247\n' % RHO)
        f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 20.\n*BOUNDARY\nNFIX, 2, 2, 0.\n')
        f.write('*STEP\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 0., 1., 0.\n' % om**2)
        f.write('*CLOAD\n' + ''.join('%d, 1, %.4f\n' % (k, v) for k, v in cl.items()))
        f.write('*TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, Tn[k]) for k in nodes))
        f.write('*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n')
    F.run_ccx(job, threads=4)
    _, blocks = F.read_frd(os.path.join(FEA, job + '.frd'))
    S = [b for b in blocks if b['name'].startswith('STRESS')][-1]['data']
    vm = {k: float(F.vm(np.array(v[:6]))) for k, v in S.items()}
    kmax = max(vm, key=vm.get)
    # mean hoop stress (area weighted over the nodes ~ uniform mesh) for the burst margin
    hoop = np.array([S[k][2] for k in S]); sh_mean = float(np.mean(hoop))
    T_max = Tn[kmax]
    ys = float(np.interp(T_max, MAT_T, MAT_YS))
    T_mean = float(np.mean(list(Tn.values())))
    uts_mean = float(np.interp(T_mean, MAT_T, MAT_UTS))
    burst = N * math.sqrt(0.85 * uts_mean / sh_mean)                 # mean-hoop burst criterion (85 % UTS, cast)
    centre = min(S, key=lambda k: nodes[k][0] + 0.01 * abs(nodes[k][1] - 0.5 * (x0 + x1)))
    return dict(row=row, N=N, blade_pull_N=Fb, vm_max=vm[kmax], vm_max_at=[float(c) for c in nodes[kmax]], T_at_max=T_max,
                ys_at_max=ys, margin_yield=ys / vm[kmax], hoop_mean=sh_mean, burst_rpm=burst, burst_ratio=burst / 15000.0,
                vm_centre=vm[centre], T_centre=Tc, disc_mass_kg=PARTS['A1000_%s_disc' % row]['mass_kg'])


def main():
    out = {}
    for row in ('R1', 'R2'):
        for N, tag in ((15000.0, 'op'), (16500.0, 'trip')):
            r = run(row, N, tag); out['%s_%s' % (row, tag)] = r
            print('%s %5.0f rpm: blade pull %.1f kN x %d, vm max %.0f MPa at r %.0f x %.0f (T %.0f C, YS %.0f -> margin %.2f), '
                  'centre %.0f MPa, mean hoop %.0f MPa, burst %.0f rpm (%.2fx), disc %.1f kg' % (
                      row, N, r['blade_pull_N'] / 1e3, A.Z[row], r['vm_max'], r['vm_max_at'][0], r['vm_max_at'][1], r['T_at_max'],
                      r['ys_at_max'], r['margin_yield'], r['vm_centre'], r['hoop_mean'], r['burst_rpm'], r['burst_ratio'],
                      r['disc_mass_kg']), flush=True)
    json.dump(out, open(os.path.join(FEA, 'a1000_disc.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
