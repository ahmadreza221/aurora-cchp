#!/usr/bin/env python3
"""AURORA-1000 blisks: coupled blade-disc modes by cyclic symmetry (CalculiX + gmsh) -> ZZENF interference diagram.

The rigid-hub blade analysis (a1000_blade_fea.py) misses the disc: low nodal diameters couple the blades with the web
(umbrella / ND modes), which the low engine orders (EO 1-5: can combustor, inlet, exhaust struts) excite.
Model: 1/Z sector = disc between r = 60 mm (held at the curvic hub faces) and the platform + blade piece
(cad/engine/a1000_turbine.py --sector: A1000_<row>_sector.step + .json). Periodic mesh on the two cut planes (faces paired
by their rotated centroids), fine near the blade, coarse in the web. Metal temperature: blade at the rotor-relative gas
temperature, disc field as in a1000_disc_fea.py (E(T) only, no thermal stress). NLGEOM centrifugal static at 15,000 rpm ->
perturbation *FREQUENCY per nodal diameter.
Engine order k excites ND n = k mod Z folded to 0..Z/2.
Run:    python sim/engine/a1000_blisk_cyclic.py [R1|R2]       (CCX = path to ccx)
        ... [R1|R2] --post      re-score the saved families against the current vane counts (no solve)
Writes: sim/engine/fea/a1000_blisk_<row>_cyclic.json, docs/img/a1000_<row>_zzenf.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import e1_turbine_fea as F                                    # noqa: E402  (ccx runner)
import e1_blisk_cyclic as C                                   # noqa: E402  (parse_dat: ND / family table from the .dat)
from a1000_disc_fea import TEMP as DISC_TEMP, MAT_T, MAT_E, RHO   # noqa: E402

CAD = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
FEA = os.path.join(HERE, 'fea')
N_OP = 15000.0
FAM = dict(R1=7, R2=10)                                       # most mode families per nodal diameter (plot)
# nodal-diameter groups solved (nmin, nmax, families): each ND costs ~4 min on this sector, so only the NDs the engine
# orders reach (+ one high ND for the blade-alone limit), with as many families as reach the order's frequency
# rev 4: ALL nodal diameters (complete ZZENF), so the vane counts can be chosen on coupled data (rev 3 solved only the NDs
# of the current orders and the vane-count scan then had no data for the alternatives); R1 7 families reach ~29 kHz
# (2 x NPF), R2 10 families ~20 kHz (its 2 x NPF orders are checked on the high-ND families + the 16 rigid-hub modes)
# (R2 first ran ND 0-5, 7-8, 11-14; rev 5 added ND 6, 9, 10 with A1000_ND for the vane-count choice: ND 0-14 solved,
# ND 15-18 not needed by EO 1-5, 29, 39, 58, 10)
ND_STEPS = dict(R1=[(0, 29, 7)], R2=[(0, 5, 6), (6, 14, 10)])
# A1000_ND="6:6:10" solves only these groups (nmin:nmax:families, comma separated) and merges them into the saved json
ND_ADD = [tuple(int(v) for v in g.split(':')) for g in os.environ.get('A1000_ND', '').split(',') if g]
ROWS = dict(R1=dict(T=870.0, h_blade=1.0, h_disc=5.0), R2=dict(T=735.0, h_blade=1.3, h_disc=6.0))
NGV = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
Z_N1, Z_N2 = NGV['N1']['Z'], NGV['N2']['Z']
_DZ = [abs(Z_N1 - Z_N2)] if abs(Z_N1 - Z_N2) > 5 and abs(Z_N1 - Z_N2) not in (Z_N1, Z_N2) else []   # vane-vane order
EO = dict(R1=[1, 2, 3, 4, 5, Z_N1, Z_N2, 2 * Z_N1, 2 * Z_N2] + _DZ, R2=[1, 2, 3, 4, 5, Z_N2, Z_N1, 2 * Z_N2] + _DZ)


def nd_of(k, Z):
    m = k % Z
    return min(m, Z - m)


def mesh(step, theta0, pitch, rh, cfg):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('sector'); gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
    def on_plane(tag, th):
        """face lies in the plane through the x axis at angle th: its vertices AND interior samples (a curved blade-skin
        patch bounded only by the cut curves has all its vertices on the plane; taken as a cut face it was tied and
        suppressed the blade flap mode: family 1 at 7.7 kHz instead of ~4.5 kHz)"""
        n = np.array([-math.sin(th), math.cos(th)])
        d = lambda p: abs(p[1] * n[0] + p[2] * n[1])
        pts = [gmsh.model.getValue(0, t, []) for _, t in gmsh.model.getBoundary([(2, tag)], recursive=True)]
        if len(pts) < 3 or any(d(p) > 1e-3 for p in pts): return False
        lo, hi = gmsh.model.getParametrizationBounds(2, tag)
        uv = [(lo[0] + (hi[0] - lo[0]) * a, lo[1] + (hi[1] - lo[1]) * b) for a in (0.2, 0.5, 0.8) for b in (0.2, 0.5, 0.8)]
        return all(d(gmsh.model.getValue(2, tag, list(q))) < 1e-3 for q in uv)
    th0, th1 = math.radians(theta0), math.radians(theta0 + pitch)
    faces = [t for _, t in gmsh.model.getEntities(2)]
    left = [t for t in faces if on_plane(t, th0)]; right = [t for t in faces if on_plane(t, th1)]
    if not left or not right:
        raise RuntimeError('cut faces: left %s right %s' % (left, right))
    a = math.radians(pitch); c, s = math.cos(a), math.sin(a)
    if len(left) == len(right):                                # periodic mesh when the cut faces split alike on both planes;
        def com(t): return np.array(gmsh.model.occ.getCenterOfMass(2, t))   # otherwise the *TIE interpolates (non-matching)
        pairs = []                                             # right face = left face rotated by +pitch about x
        for tl in left:
            p = com(tl); q = np.array([p[0], c * p[1] - s * p[2], s * p[1] + c * p[2]])
            tr = min(right, key=lambda t: np.linalg.norm(com(t) - q)); pairs.append((tl, tr))
        gmsh.model.mesh.setPeriodic(2, [tr for _, tr in pairs], [tl for tl, _ in pairs],
                                    [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1])
    # size: h_blade on / near the blade surfaces (all faces above the platform), growing to h_disc in the web
    blade_faces = [t for t in faces if t not in left and t not in right and
                   min(math.hypot(*gmsh.model.getValue(0, v, [])[1:]) for _, v in gmsh.model.getBoundary([(2, t)], recursive=True))
                   > rh - 0.3]
    fd = gmsh.model.mesh.field.add('Distance'); gmsh.model.mesh.field.setNumbers(fd, 'FacesList', blade_faces)
    ft = gmsh.model.mesh.field.add('Threshold'); gmsh.model.mesh.field.setNumber(ft, 'InField', fd)
    for k, v in (('SizeMin', cfg['h_blade']), ('SizeMax', cfg['h_disc']), ('DistMin', 2.0), ('DistMax', 25.0)):
        gmsh.model.mesh.field.setNumber(ft, k, v)
    gmsh.model.mesh.field.setAsBackgroundMesh(ft)
    gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 0); gmsh.option.setNumber('Mesh.MeshSizeFromPoints', 0)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 0)
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


def run(row, nodes, els, nl, nr, meta, nds, tag):
    cfg = ROWS[row]; Z = meta['Z']; om = N_OP * 2 * math.pi / 60.0
    Tc, Tp, ne = DISC_TEMP[row]; rh = meta['rh']
    def temp(p):
        r = math.hypot(p[1], p[2]); return cfg['T'] if r > rh + 0.5 else Tc + (Tp - Tc) * (r / rh) ** ne
    dep = set(nr)
    hub = [k for k, p in nodes.items() if math.hypot(p[1], p[2]) <= meta['r_in'] + 1e-3 and k not in dep]
    job = 'a1000_cyc_%s_%s' % (row, tag)
    with open(os.path.join(FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NLEFT\n' + ''.join('%d,\n' % k for k in nl) + '*NSET, NSET=NRIGHT\n' + ''.join('%d,\n' % k for k in nr))
        f.write('*NSET, NSET=NHUB\n' + ''.join('%d,\n' % k for k in hub))
        # independent side as element faces (C3D10 S1 = 1-2-3, S2 = 1-4-2, S3 = 2-4-3, S4 = 3-4-1): the dependent nodes
        # are interpolated on it, so the two cut-face meshes need not match
        sl = set(nl); facets = []
        for i, e in enumerate(els, 1):
            for sn, (a_, b_, c_) in (('S1', (0, 1, 2)), ('S2', (0, 3, 1)), ('S3', (1, 3, 2)), ('S4', (2, 3, 0))):
                if e[a_] in sl and e[b_] in sl and e[c_] in sl: facets.append('%d, %s\n' % (i, sn))
        f.write('*SURFACE, NAME=SLEFT, TYPE=ELEMENT\n' + ''.join(facets) + '*SURFACE, NAME=SRIGHT, TYPE=NODE\nNRIGHT\n')
        f.write('*TIE, NAME=CYC, CYCLIC SYMMETRY, ADJUST=NO\nSRIGHT, SLEFT\n')
        f.write('*CYCLIC SYMMETRY MODEL, N=%d, NGRAPH=1, TIE=CYC\n0., 0., 0., 1., 0., 0.\n' % Z)
        f.write('*MATERIAL, NAME=MARM247\n*ELASTIC\n' + ''.join('%.1f, 0.30, %.1f\n' % (e, t) for e, t in zip(MAT_E, MAT_T)))
        f.write('*DENSITY\n%.3e\n*SOLID SECTION, ELSET=EALL, MATERIAL=MARM247\n' % RHO)
        f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\n' + ''.join('%d, %.1f\n' % (k, temp(p)) for k, p in nodes.items()))
        f.write('*BOUNDARY\nNHUB, 1, 3, 0.\n')
        f.write('*STEP, NLGEOM\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n*END STEP\n' % om**2)
        for n0, n1, fam in ND_STEPS[row]:                      # one perturbation step per group (cos / sin copies: 2 x fam)
            f.write('*STEP, PERTURBATION\n*FREQUENCY\n%d\n*SELECT CYCLIC SYMMETRY MODES, NMIN=%d, NMAX=%d\n*END STEP\n'
                    % (2 * fam, n0, n1))
    F.run_ccx(job, threads=int(os.environ.get('CCX_THREADS', 4)))
    return {nd: v for nd, v in C.parse_dat(os.path.join(FEA, job + '.dat')).items() if nd in nds}


def main():
    row = sys.argv[1] if len(sys.argv) > 1 else 'R1'
    out = os.path.join(FEA, 'a1000_blisk_%s_cyclic.json' % row)
    if '--post' in sys.argv:                                  # re-score the saved families against the current vane counts
        d = json.load(open(out))
        return post(row, d['Z'], {int(k): v for k, v in d['freqs'].items()}, d['mesh'], out)
    meta = json.load(open(os.path.join(CAD, 'A1000_%s_sector.json' % row)))
    sys.argv_saved = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
    sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine')); import a1000_turbine as A   # noqa: E401
    sys.argv = sys.argv_saved
    meta['rh'] = A.row_radius(row, 0.0); Z = meta['Z']
    nodes, els, nl, nr = mesh(os.path.join(CAD, 'A1000_%s_sector.step' % row), meta['theta0_deg'], meta['pitch_deg'],
                              meta['rh'], ROWS[row])
    print('%s sector mesh: %d nodes, %d C3D10, cut faces %d / %d nodes' % (row, len(nodes), len(els), len(nl), len(nr)), flush=True)
    if ND_ADD: ND_STEPS[row] = ND_ADD
    nd_all = sorted({n for n0, n1, _ in ND_STEPS[row] for n in range(n0, n1 + 1)})
    table = run(row, nodes, els, nl, nr, meta, nd_all, '15k' if not ND_ADD else '15k_add')
    if len(table) < len(nd_all):
        raise RuntimeError('cyclic frequency step returned %d of %d nodal diameters (ccx killed? see the .log)' % (len(table), len(nd_all)))
    if ND_ADD and os.path.exists(out):
        old = {int(k): v for k, v in json.load(open(out))['freqs'].items()}
        table = {**old, **table}
    post(row, Z, table, dict(nodes=len(nodes), elements=len(els)), out)


def post(row, Z, table, mesh_info, out):
    for nd in sorted(table):
        print('   ND %2d: %s' % (nd, '  '.join('%7.0f' % f for f in table[nd])), flush=True)
    hits = []
    print('interference at 15,000 rpm (EO k -> ND n, |margin| < 10 %):')
    for k in EO[row]:
        n = nd_of(k, Z); fk = k * N_OP / 60
        for m, f in enumerate(table.get(n, [])):
            marg = (f - fk) / fk
            if abs(marg) < 0.10:
                hits.append(dict(eo=k, nd=n, family=m + 1, f=f, margin=marg))
                print('  EO%-3d -> ND%-2d family %d: %7.0f Hz vs %7.0f Hz, margin %+6.1f %%' % (k, n, m + 1, f, fk, 100 * marg))
    near = {k: min(((abs(f - k * N_OP / 60) / (k * N_OP / 60), m + 1, f) for m, f in enumerate(table.get(nd_of(k, Z), []))),
                   default=None) for k in EO[row]}
    json.dump(dict(row=row, Z=Z, N=N_OP, eo=EO[row], freqs={str(n): v for n, v in table.items()}, hits=hits,
                   nearest={str(k): v for k, v in near.items()}, mesh=mesh_info),
              open(out, 'w'), indent=1, default=float)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 7), dpi=120)
    for m in range(FAM[row]):
        pts = [(n, table[n][m]) for n in sorted(table) if len(table[n]) > m]
        if pts: ax.plot(*zip(*pts), 'o', ms=5, color='C%d' % (m % 10), label='family %d' % (m + 1))
    top = max(max(v) for v in table.values()) * 1.05
    for k in EO[row]:
        n = nd_of(k, Z); fk = k * N_OP / 60
        if fk > top: continue
        ax.plot([n], [fk], 'kx', ms=11, mew=2); ax.annotate(' EO%d' % k, (n, fk), fontsize=9)
        ax.fill_between([n - 0.35, n + 0.35], fk * 0.9, fk * 1.1, color='k', alpha=0.10)
    ax.set_xlabel('nodal diameter'); ax.set_ylabel('frequency at 15,000 rpm [Hz]'); ax.set_ylim(0, top)
    ax.set_xticks(sorted(table)); ax.set_xlim(-0.5, Z // 2 + 0.5); ax.grid(alpha=0.3); ax.legend(fontsize=8, loc='upper left')
    ax.set_title('AURORA-1000 %s blisk (%d blades, cyclic symmetry, disc included): ZZENF at 15,000 rpm, x = EO (+-10 %%)'
                 % (row, Z), fontsize=10)
    fig.tight_layout(); png = os.path.join(ROOT, 'docs', 'img', 'a1000_%s_zzenf.png' % row); fig.savefig(png); print('written', png)


if __name__ == '__main__':
    main()
