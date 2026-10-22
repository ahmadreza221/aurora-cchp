#!/usr/bin/env python3
"""GR180-CCHP E1 - 3-D stress of the bore-less blisk by a 1/29 cyclic-symmetry sector (CalculiX + gmsh): blade root
fillet, platform, web fillet; tip growth (hot tip clearance); start-stop LCF estimate at the stress peaks.

Model: cad_out/engine/E1/E1_sector_boreless.step (+ .json: planar cut planes theta0 / pitch) written by
cad/engine/e1_sector_tool.py = bore-less disc sector + whole blade with its R0.8 root fillet. Periodic C3D10 mesh with
curvature refinement in the fillets; cyclic-symmetry tie on the cut faces; held at the weld face (x 104.3, r <= 4).
Loads: centrifugal (CENTRIF) at N; hot cases with the prescribed steady metal field of e1_turbine_fea.T_field (bore 450 C
-> platform 730 C, blade 730 C) and thermal expansion from 20 C (thermal + centrifugal stress), NLGEOM.
Support: weld face (x 104.3, r <= 4) held AXIALLY only; the cyclic tie of the two cut planes through the axis pins the
axis nodes radially (u_right = R u_left on a node in both sets -> u_y = u_z = 0), so no rigid mode remains and the hub
face is free to expand thermally (a full 3-DOF fix there gave a fictitious 4000 MPa thermal peak at the weld face).
Cases: 115k hot (design), 120k hot (trip), 138k cold (spin test), 115k cold.
Run:    CCX=~/micromamba/envs/gr180/bin/ccx python sim/engine/e1_sector_stress.py [--h 0.5] [--hmin 0.12] [--curv 24]
            [--cases 115h,120h,138c,115c] [--tag name]   (tag: job / json suffix for mesh-convergence runs)
Writes: sim/engine/fea/sector_stress.json, cad_out/engine/E1/E1_sector_vm_<case>.png, cad_out/engine/E1/E1_fea_results.json
        (clearance.ngv_bore_r_cold_recommended, read by cad/engine/gg_turbine.py ngv_bore_r()).
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import e1_turbine_fea as F                                   # noqa: E402  (material, T_field, ccx runner, frd reader)
G = F.G

Z = G.Z_ROT
CASES = {'115h': (115e3, True), '120h': (120e3, True), '138c': (138e3, False), '115c': (115e3, False)}
H_MESH = 0.50
H_MIN = 0.12
CURV = 24            # elements per 2 pi of curvature (fillets R0.8 -> ~0.2 mm elements)
T_SHROUD = (500.0, 600.0, 650.0, 700.0, 750.0)   # NGV shroud ring metal temperature assumptions for the hot tip clearance
T_SHROUD_DESIGN = 650.0              # uncooled ring in ~800 C gas: design assumption for the cold-bore recommendation (measure on the stand)
HOT_CLEARANCE_MIN = 0.12             # mm, wanted minimum hot running clearance at the tip


def mesh(step, theta0, pitch, h=H_MESH, hmin=H_MIN, curv=CURV):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('sector'); gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()

    def on_plane(tag, th):
        nodes = []
        for dim, t in gmsh.model.getBoundary([(2, tag)], recursive=True):
            nodes.append(gmsh.model.getValue(0, t, []))
        n = np.array([-math.sin(th), math.cos(th)])
        return len(nodes) >= 3 and all(abs(p[1] * n[0] + p[2] * n[1]) < 1e-3 for p in nodes)
    th0, th1 = math.radians(theta0), math.radians(theta0 + pitch)
    left = [t for _, t in gmsh.model.getEntities(2) if on_plane(t, th0)]
    right = [t for _, t in gmsh.model.getEntities(2) if on_plane(t, th1)]
    if len(left) != len(right) or not left:
        raise RuntimeError('cut faces not found: left %s right %s' % (left, right))
    a = math.radians(pitch); c, s = math.cos(a), math.sin(a)
    gmsh.model.mesh.setPeriodic(2, right, left, [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1])
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', h); gmsh.option.setNumber('Mesh.CharacteristicLengthMin', hmin)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', curv)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.option.setNumber('Mesh.Algorithm3D', 10)            # HXT (fast, parallel)
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


def write_deck(job, nodes, els, nl, nr, N, hot):
    om = F.omega(N)
    dep = set(nr)
    weld = [k for k, p in nodes.items() if abs(p[0] - G.X_HUB) < 1e-3 and math.hypot(p[1], p[2]) <= 4.0 + 1e-6 and k not in dep]
    # rigid rotation about x is not removed by the axial support: hold one weld-face node tangentially (node near theta 0,
    # largest r -> its z DOF is tangential)
    k_t = max(weld, key=lambda k: nodes[k][1] - 10.0 * abs(nodes[k][2]))
    with open(os.path.join(F.FEA, job + '.inp'), 'w') as f:
        f.write('** GR180 E1 bore-less blisk 1/29 sector, N %.0f rpm, hot %s\n' % (N, hot))
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NLEFT\n' + ''.join('%d,\n' % k for k in nl) + '*NSET, NSET=NRIGHT\n' + ''.join('%d,\n' % k for k in nr))
        f.write('*NSET, NSET=NWELD\n' + ''.join('%d,\n' % k for k in weld))
        f.write('*SURFACE, NAME=SLEFT, TYPE=NODE\nNLEFT\n*SURFACE, NAME=SRIGHT, TYPE=NODE\nNRIGHT\n')
        f.write('*TIE, NAME=CYC, CYCLIC SYMMETRY, ADJUST=NO\nSRIGHT, SLEFT\n')
        f.write('*CYCLIC SYMMETRY MODEL, N=%d, NGRAPH=1, TIE=CYC\n0., 0., 0., 1., 0., 0.\n' % Z)
        f.write(F.material_cards() + '*SOLID SECTION, ELSET=EALL, MATERIAL=IN713LC\n')
        f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 20.\n*BOUNDARY\nNWELD, 1, 1, 0.\n%d, 3, 3, 0.\n' % k_t)
        f.write('*STEP, NLGEOM, INC=200\n*STATIC\n0.2, 1.0, 0.02, 0.5\n')
        f.write('*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n' % om**2)
        if hot:
            f.write('*TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, float(F.T_field(p[0], math.hypot(p[1], p[2])))) for k, p in nodes.items()))
        f.write('*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n')
    return weld


def post(job, nodes, meta, N, hot):
    nd, blocks = F.read_frd(os.path.join(F.FEA, job + '.frd'))
    S = [b for b in blocks if b.get('name') == 'STRESS'][-1]['data']
    U = [b for b in blocks if b.get('name') == 'DISP'][-1]['data']
    ks = sorted(S)
    P = np.array([nodes[k] for k in ks]); x = P[:, 0]; r = np.hypot(P[:, 1], P[:, 2]); th = np.degrees(np.arctan2(P[:, 2], P[:, 1]))
    sv = F.vm(np.array([S[k] for k in ks]))
    T = np.array([float(F.T_field(xi, ri)) for xi, ri in zip(x, r)]) if hot else np.full(len(ks), 20.0)
    ys = np.array([F.YS(t) for t in T])
    rh = np.array([float(G.r_hub(np.clip(xi, G.X_PF, G.X_PR))) for xi in x])
    tl, th_hi = meta['footprint_deg']
    inblade = (th >= tl - 0.5) & (th <= th_hi + 0.5) & (x >= G.X_PF) & (x <= G.X_PR)
    reg = {
        'blade_root_fillet': inblade & (r >= rh - 0.05) & (r <= rh + 1.3),
        'blade_above_fillet': (r > rh + 1.3) & (r <= G.R_TIP + 0.1) & (x >= G.X_PF),
        'platform_lips': (r >= 17.0) & (r < rh - 0.05) & (x >= G.X_PF) & (x <= G.X_PR),
        'web': (r >= 8.0) & (r < 17.0) & (x > G.X_HUB + 3.0) & (x < G.X_PR),
        'hub_sleeve_boss': (r < 8.0),
        'all': np.ones(len(ks), bool),
    }
    out = {}
    for name, m in reg.items():
        if not m.any():
            continue
        i = np.argmax(np.where(m, sv, -1))
        out[name] = dict(vm_max=float(sv[i]), at_x=float(x[i]), at_r=float(r[i]), at_theta=float(th[i]), T=float(T[i]),
                         ys_min=float(ys[i]), margin=float(ys[i] / sv[i]) if sv[i] > 0 else None, n_nodes=int(m.sum()))
        if name in ('blade_root_fillet', 'web'):
            idx = np.argsort(np.where(m, sv, -1))[::-1][:8]
            out[name]['top'] = [dict(vm=float(sv[j]), x=float(x[j]), r=float(r[j]), theta=float(th[j])) for j in idx]
            # 99th percentile in the region: a single-node spike vs a real hot zone
            out[name]['vm_p99'] = float(np.percentile(sv[m], 99.0)); out[name]['vm_p95'] = float(np.percentile(sv[m], 95.0))
    # radial growth
    ur = np.array([(nodes[k][1] * U[k][1] + nodes[k][2] * U[k][2]) / max(math.hypot(nodes[k][1], nodes[k][2]), 1e-9) for k in ks])
    tip = r >= G.R_TIP - 0.05
    plat = (np.abs(r - rh) < 0.05) & (x >= G.X_PF) & (x <= G.X_PR)
    out['growth'] = dict(tip_ur_max=float(ur[tip].max()), tip_ur_mean=float(ur[tip].mean()), tip_ur_min=float(ur[tip].min()),
                         platform_ur_mean=float(ur[plat].mean()), weld_face_ur_max=float(ur[r < 4.1].max()) if (r < 4.1).any() else None)
    # mean radial (pull) stress at the blade root section: nodes in the fillet band, radial component sigma_rr
    sel = reg['blade_root_fillet']
    s6 = np.array([S[k] for k in ks])
    cth, sth = P[:, 1] / np.maximum(r, 1e-9), P[:, 2] / np.maximum(r, 1e-9)
    # sigma_rr = syy c^2 + szz s^2 + 2 syz c s  (frd order xx yy zz xy yz zx)
    srr = s6[:, 1] * cth**2 + s6[:, 2] * sth**2 + 2 * s6[:, 4] * cth * sth
    out['blade_root_srr_mean'] = float(srr[sel & (r > rh + 0.6) & (r < rh + 1.3)].mean()) if (sel & (r > rh + 0.6)).any() else None
    return out, dict(x=x, r=r, th=th, vm=sv)


def plot(case, pt, meta):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 6), dpi=110)
    sc = ax[0].scatter(pt['x'], pt['r'], c=pt['vm'], s=2, cmap='turbo', vmin=0, vmax=max(700, pt['vm'].max()))
    ax[0].set_xlabel('x [mm]'); ax[0].set_ylabel('r [mm]'); ax[0].set_title('von Mises, all nodes (meridional projection)'); ax[0].set_aspect('equal')
    plt.colorbar(sc, ax=ax[0], label='MPa')
    sel = pt['r'] > 18.5
    sc2 = ax[1].scatter(pt['th'][sel], pt['r'][sel], c=pt['vm'][sel], s=3, cmap='turbo', vmin=0, vmax=max(700, pt['vm'].max()))
    ax[1].set_xlabel('theta [deg]'); ax[1].set_ylabel('r [mm]'); ax[1].set_title('blade + platform (r > 18.5), fillet footprint %.1f..%.1f deg' % tuple(meta['footprint_deg']))
    plt.colorbar(sc2, ax=ax[1], label='MPa')
    fig.suptitle('GR180 E1 bore-less blisk sector, case %s' % case); fig.tight_layout()
    png = os.path.join(F.OUT, 'E1_sector_vm_%s.png' % case); fig.savefig(png); plt.close(fig); return png


def lcf_universal_slopes(sigma_max, T):
    """Manson universal slopes, fully-reversed equivalent of a 0 -> sigma_max start/stop cycle (elastic, Neuber not
    applied below yield): de_t = 3.5 (UTS/E) N^-0.12 + ef^0.6 N^-0.6, ef = ln(1/(1-RA)). Returns N (cycles) for the
    strain range sigma_max/E (zero-to-max; conservative: treated as the full range) and with the 2x strain factor."""
    E = F.E_(T); uts = F.UTS(T, minimum=False); ef = math.log(1.0 / (1.0 - F.RA))
    de = sigma_max / E
    def life(d):
        lo, hi = 1.0, 1e9
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            if 3.5 * (uts / E) * mid**-0.12 + ef**0.6 * mid**-0.6 > d: lo = mid
            else: hi = mid
        return math.sqrt(lo * hi)
    return dict(strain_range=de, N=life(de), N_2x_strain=life(2 * de))


def main():
    args = sys.argv[1:]
    h = float(args[args.index('--h') + 1]) if '--h' in args else H_MESH
    hmin = float(args[args.index('--hmin') + 1]) if '--hmin' in args else H_MIN
    curv = float(args[args.index('--curv') + 1]) if '--curv' in args else CURV
    tag = args[args.index('--tag') + 1] if '--tag' in args else ''
    cases = args[args.index('--cases') + 1].split(',') if '--cases' in args else ['115h', '120h', '138c', '115c']
    step = os.path.join(F.OUT, 'E1_sector_boreless.step')
    meta = json.load(open(os.path.join(F.OUT, 'E1_sector_boreless.json')))
    t0 = time.time()
    nodes, els, nl, nr = mesh(step, meta['theta0_deg'], meta['pitch_deg'], h, hmin, curv)
    print('sector mesh: %d nodes, %d C3D10, cut faces %d / %d nodes (%.0f s)' % (len(nodes), len(els), len(nl), len(nr), time.time() - t0), flush=True)
    res = dict(mesh=dict(nodes=len(nodes), elements=len(els), h=h, h_min=hmin, curvature=curv), sector=meta, cases={})
    for case in cases:
        N, hot = CASES[case]
        job = 'sec_' + case + (('_' + tag) if tag else '')
        write_deck(job, nodes, els, nl, nr, N, hot)
        dt, log = F.run_ccx(job, threads=max(1, (os.cpu_count() or 4) - 2))
        out, pt = post(job, nodes, meta, N, hot)
        out['N'] = N; out['hot'] = hot; out['ccx_s'] = dt
        for key in ('blade_root_fillet', 'web', 'all'):
            if key in out:
                out[key]['lcf'] = lcf_universal_slopes(out[key]['vm_max'], out[key]['T'])
        out['png'] = plot(case + (('_' + tag) if tag else ''), pt, meta)
        res['cases'][case] = out
        print('case %s (%.0fk rpm, %s): ccx %.0f s' % (case, N / 1e3, 'hot' if hot else 'cold', dt))
        for key in ('blade_root_fillet', 'blade_above_fillet', 'platform_lips', 'web', 'hub_sleeve_boss', 'all'):
            if key in out:
                o = out[key]
                print('   %-20s vm_max %6.0f MPa at x %.2f r %.2f th %6.2f deg (T %.0f C, YS_min %.0f, margin %.2f)%s' % (
                    key, o['vm_max'], o['at_x'], o['at_r'], o['at_theta'], o['T'], o['ys_min'], o['margin'] or 0,
                    ('  p99 %.0f p95 %.0f' % (o['vm_p99'], o['vm_p95'])) if 'vm_p99' in o else ''), flush=True)
                if 'top' in o:
                    print('      top: ' + '; '.join('%.0f@(%.2f, %.2f, %.1f)' % (t['vm'], t['x'], t['r'], t['theta']) for t in o['top'][:5]), flush=True)
        g = out['growth']
        print('   tip radial growth %.4f .. %.4f mm (mean %.4f), platform %.4f; blade root sigma_rr mean %s MPa' % (
            g['tip_ur_min'], g['tip_ur_max'], g['tip_ur_mean'], g['platform_ur_mean'],
            ('%.0f' % out['blade_root_srr_mean']) if out['blade_root_srr_mean'] is not None else '-'), flush=True)
    # hot tip clearance (design case 115h): cold 0.20 mm; shroud ring grows alpha(T) * r * dT
    if '115h' in res['cases']:
        g = res['cases']['115h']['growth']['tip_ur_max']
        cl = {}
        for Ts in T_SHROUD:
            a = float(np.interp(Ts, F.MAT_T, F.MAT_ALPHA)); ds = a * G.ngv_bore_r() * (Ts - 20.0)
            cl[str(int(Ts))] = dict(shroud_growth=ds, tip_growth=g, hot_clearance=G.ngv_bore_r() - G.R_TIP + ds - g)
        # recommended cold bore for HOT_CLEARANCE_MIN at the design shroud temperature; never below the current design bore
        a = float(np.interp(T_SHROUD_DESIGN, F.MAT_T, F.MAT_ALPHA)); ds = a * G.ngv_bore_r() * (T_SHROUD_DESIGN - 20.0)
        rec = G.R_TIP + g - ds + HOT_CLEARANCE_MIN
        res['clearance'] = dict(cold_design=G.ngv_bore_r() - G.R_TIP, by_shroud_T=cl, hot_clearance_min_wanted=HOT_CLEARANCE_MIN,
                                T_shroud_design=T_SHROUD_DESIGN, ngv_bore_r_for_design_T=float(rec),
                                ngv_bore_r_cold_recommended=float(max(rec, G.ngv_bore_r())),
                                note='cold bore never below the current design; re-evaluate with the measured NGV ring temperature')
        print('hot tip clearance at 115k: ' + ', '.join('shroud %s C: %.3f mm' % (k, v['hot_clearance']) for k, v in cl.items()))
        print('recommended cold NGV bore r: %.3f mm (current %.3f)' % (res['clearance']['ngv_bore_r_cold_recommended'], G.ngv_bore_r()))
        if not tag:
            json.dump(dict(clearance=res['clearance'], source='sim/engine/e1_sector_stress.py'), open(os.path.join(F.OUT, 'E1_fea_results.json'), 'w'), indent=1)
    out_json = os.path.join(F.FEA, 'sector_stress%s.json' % (('_' + tag) if tag else ''))
    json.dump(res, open(out_json, 'w'), indent=1, default=float)
    print('written', out_json)


if __name__ == '__main__':
    main()
