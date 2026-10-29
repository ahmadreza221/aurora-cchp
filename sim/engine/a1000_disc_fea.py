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
sys.path.insert(0, os.path.join(ROOT, 'sim'))
from mw1_concept_study import mar_m247_rupture_hours           # noqa: E402  (Larson-Miller fit, cast MAR-M247)
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
# (centre, platform, exponent n): T(r) = Tc + (Tp - Tc) (r / r_hub)^n. Blisk 1 front face, rim cavity and rim slots are
# purged with compressor delivery air (~1.2 % of the air flow at 175 C through holes in the drum): steep gradient under
# the platform. DESIGN REQUIREMENT (to be confirmed by a CHT analysis): R1 slot bottom <= 710 C (n = 6 gives 713 C);
# at 737 C (n = 4) the slot-bottom creep life is 3.3e4 h with 1.25 x stress, at 710 C 1.5e5 h.
TEMP = dict(R1=(450.0, 800.0, 6.0), R2=(420.0, 690.0, 2.0))
# rim thermal-relief slots: one EDM slot between each pair of blades, from the platform down to SLOT mm below it, ending
# in a 3 mm drilled hole (seal pin in the slot). Above the slot bottom the rim carries no hoop stress: modelled as an
# orthotropic band with 1 % hoop modulus (axisymmetric frame 1 = radial, 2 = axial, 3 = hoop). Without slots the 800 C
# platform is held by the cooler web: ~520 MPa thermal hoop stress at the platform (creep / TMF cracking of the rim).
SLOT = dict(R1=10.0, R2=10.0)


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


def run(row, N, tag, thermal=True, temp=None, slot=None):
    """one axisymmetric solve. thermal=False: same E(T) field but no thermal strain (primary stress for creep / burst);
    temp = (Tc, Tp, n) and slot [mm] override TEMP / SLOT (design studies)"""
    poly = A.disc_profile(row); nodes, els = mesh(poly)
    rh = A.row_radius(row, 0.0); x0, x1 = A.X_LE[row] - A.PLAT_OVH, A.X_TE[row] + A.PLAT_OVH
    # blade pull per blade: mass and centroid radius of the blade piece (above the platform)
    m_b = PARTS['A1000_%s_blade' % row]['mass_kg']
    r_cg = 0.5 * (A.row_radius(row, 0.0) + A.row_radius(row, 1.0)) - 0.10 * (A.row_radius(row, 1.0) - A.row_radius(row, 0.0))
    om = N * 2 * math.pi / 60
    Fb = m_b * r_cg * 1e-3 * om**2                                    # N
    Zb = A.Z[row]
    Tc, Tr, ne = temp or TEMP[row]
    sl = SLOT[row] if slot is None else slot
    Tn = {k: Tc + (Tr - Tc) * (v[0] / rh) ** ne for k, v in nodes.items()}
    # consistent nodal forces on the platform top edge (r = rh): total = Z * Fb (full 360 deg in ccx axisymmetric)
    cl = {}; L = 0.0
    for e in els:
        for (i, j, m) in ((0, 1, 3), (1, 2, 4), (2, 0, 5)):
            a, b = nodes[e[i]], nodes[e[j]]
            if abs(a[0] - rh) < 1e-6 and abs(b[0] - rh) < 1e-6:
                dl = abs(a[1] - b[1]); L += dl
                for n_, w in ((e[i], 1 / 6), (e[j], 1 / 6), (e[m], 2 / 3)): cl[n_] = cl.get(n_, 0.0) + w * dl
    cl = {k: v / L * Zb * Fb for k, v in cl.items()}
    job = 'a1000_disc_%s_%s%s' % (row, tag, '' if thermal else '_mech')
    r_slot = rh - sl
    e_slot = [i for i, e in enumerate(els, 1) if sl > 0 and np.mean([nodes[n_][0] for n_ in e[:3]]) > r_slot]
    with open(os.path.join(FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f\n' % (k, v[0], v[1]) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=CAX6, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        fix = min(nodes, key=lambda k: nodes[k][0] + abs(nodes[k][1] - 0.5 * (x0 + x1)) * 0.01)
        f.write('*NSET, NSET=NFIX\n%d,\n' % fix)
        e_full = sorted(set(range(1, len(els) + 1)) - set(e_slot))
        f.write('*ELSET, ELSET=EFULL\n' + ''.join('%d,\n' % i for i in e_full))
        if e_slot: f.write('*ELSET, ELSET=ESLOT\n' + ''.join('%d,\n' % i for i in e_slot))
        f.write('*MATERIAL, NAME=MARM247\n*ELASTIC\n' + ''.join('%.1f, 0.30, %.1f\n' % (e, t) for e, t in zip(MAT_E, MAT_T)))
        f.write('*EXPANSION, ZERO=20.\n' + ''.join('%.3e, %.1f\n' % (a, t) for a, t in zip(MAT_A, MAT_T)))
        f.write('*DENSITY\n%.3e\n' % RHO)
        f.write('*MATERIAL, NAME=MARM247S\n*ELASTIC, TYPE=ENGINEERING CONSTANTS\n' + ''.join(
            '%.1f, %.1f, %.1f, 0.30, 0.30, 0.30, %.1f, %.1f\n%.1f, %.1f\n' % (e, e, 0.01 * e, e / 2.6, 0.01 * e / 2.6, 0.01 * e / 2.6, t)
            for e, t in zip(MAT_E, MAT_T)))
        f.write('*EXPANSION, ZERO=20.\n' + ''.join('%.3e, %.1f\n' % (a, t) for a, t in zip(MAT_A, MAT_T)))
        f.write('*DENSITY\n%.3e\n' % RHO)
        f.write('*SOLID SECTION, ELSET=EFULL, MATERIAL=MARM247\n')
        if e_slot: f.write('*SOLID SECTION, ELSET=ESLOT, MATERIAL=MARM247S\n')
        if thermal:
            f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 20.\n')
        else:                                                      # E(T) at the running temperature, no thermal strain
            f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, Tn[k]) for k in nodes))
        f.write('*BOUNDARY\nNFIX, 2, 2, 0.\n')
        f.write('*STEP\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 0., 1., 0.\n' % om**2)
        f.write('*CLOAD\n' + ''.join('%d, 1, %.4f\n' % (k, v) for k, v in cl.items()))
        if thermal: f.write('*TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, Tn[k]) for k in nodes))
        f.write('*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n')
    F.run_ccx(job, threads=4)
    _, blocks = F.read_frd(os.path.join(FEA, job + '.frd'))
    S = [b for b in blocks if b['name'].startswith('STRESS')][-1]['data']
    U = [b for b in blocks if b['name'].startswith('DISP')][-1]['data']
    k_rim = min(nodes, key=lambda k: abs(nodes[k][0] - rh) + 0.01 * abs(nodes[k][1] - 0.5 * (x0 + x1)))
    u_rim = float(U[k_rim][0])                                        # radial growth of the platform
    vm = {k: float(F.vm(np.array(v[:6]))) for k, v in S.items()}
    kmax = max(vm, key=vm.get)
    # volume-weighted mean hoop stress (frd axisymmetric: component 3 = hoop) of the hoop-carrying section (below the
    # slot bottom) for the burst margin; thermal hoop stress self-equilibrates, so mech-only and total give ~ the same mean
    wsum = hsum = 0.0
    slot_set = set(e_slot)
    for i, e in enumerate(els, 1):
        if i in slot_set: continue
        (ra, xa), (rb, xb), (rc, xc) = nodes[e[0]], nodes[e[1]], nodes[e[2]]
        area = 0.5 * abs((rb - ra) * (xc - xa) - (rc - ra) * (xb - xa)); rcen = (ra + rb + rc) / 3
        hsum += area * rcen * float(np.mean([S[n_][2] for n_ in e])); wsum += area * rcen
    sh_mean = hsum / wsum
    T_max = Tn[kmax]
    ys = float(np.interp(T_max, MAT_T, MAT_YS))
    T_mean = float(np.mean(list(Tn.values())))
    uts_mean = float(np.interp(T_mean, MAT_T, MAT_UTS))
    burst = N * math.sqrt(0.85 * uts_mean / sh_mean)                 # mean-hoop burst criterion (85 % UTS, cast)
    centre = min(S, key=lambda k: nodes[k][0] + 0.01 * abs(nodes[k][1] - 0.5 * (x0 + x1)))
    # creep: minimum Larson-Miller rupture life over the section (stress x 1.25), the two sharp platform-end corners
    # excluded (singular); meaningful on the mechanical (primary) solution
    corners = [(rh, x0), (rh, x1)]
    ok = [k for k in vm if min(math.hypot(nodes[k][0] - a, nodes[k][1] - b) for a, b in corners) > 2.0]
    k_cr = min(ok, key=lambda k: mar_m247_rupture_hours(1.25 * vm[k], Tn[k] + 273.15))
    life = mar_m247_rupture_hours(vm[k_cr], Tn[k_cr] + 273.15); life125 = mar_m247_rupture_hours(1.25 * vm[k_cr], Tn[k_cr] + 273.15)
    # nominal (smeared) hoop stress across the slot-bottom ligament (r = r_slot +- 0.75 mm): the keyhole sees Kt x this
    sb = [k for k in S if abs(nodes[k][0] - r_slot) < 0.75] if sl > 0 else []
    slot_hoop = dict(min=min(S[k][2] for k in sb), max=max(S[k][2] for k in sb), mean=float(np.mean([S[k][2] for k in sb])),
                     T=float(Tc + (Tr - Tc) * (r_slot / rh) ** ne)) if sb else None
    # platform edge: hoop stress at the platform top surface between the blade LE / TE lines (unslotted designs)
    pf = [k for k in S if abs(nodes[k][0] - rh) < 0.3 and min(abs(nodes[k][1] - x0), abs(nodes[k][1] - x1)) > 2.0]
    plat_hoop = dict(min=min(S[k][2] for k in pf), max=max(S[k][2] for k in pf), T=Tr) if pf else None
    return dict(row=row, N=N, thermal=thermal, temp=[Tc, Tr, ne], slot_mm=sl, blade_pull_N=Fb, vm_max=vm[kmax],
                vm_max_at=[float(c) for c in nodes[kmax]], T_at_max=T_max, sxx_at_max=[float(c) for c in S[kmax][:4]],
                u_rim_mm=u_rim, creep_life_h=life, creep_life_h_x125=life125, creep_at=[float(c) for c in nodes[k_cr]],
                creep_vm=vm[k_cr], creep_T=Tn[k_cr], slot_hoop=slot_hoop, plat_hoop=plat_hoop,
                ys_at_max=ys, margin_yield=ys / vm[kmax], hoop_mean=sh_mean, burst_rpm=burst, burst_ratio=burst / 15000.0,
                vm_centre=vm[centre], T_centre=Tc, disc_mass_kg=PARTS['A1000_%s_disc' % row]['mass_kg'])


def summary(r):
    return ('%s %5.0f rpm %-5s: vm max %.0f MPa at r %.0f x %.0f (T %.0f C, margin %.2f), centre %.0f, mean hoop %.0f, '
            'burst %.2fx, rim growth %.2f mm, creep-critical r %.0f (%.0f MPa, %.0f C): %.1e h (x1.25 %.1e h)%s%s' % (
                r['row'], r['N'], 'total' if r['thermal'] else 'mech', r['vm_max'], r['vm_max_at'][0], r['vm_max_at'][1],
                r['T_at_max'], r['margin_yield'], r['vm_centre'], r['hoop_mean'], r['burst_ratio'], r['u_rim_mm'],
                r['creep_at'][0], r['creep_vm'], r['creep_T'], r['creep_life_h'], r['creep_life_h_x125'],
                ', slot bottom hoop %.0f..%.0f MPa at %.0f C' % (r['slot_hoop']['min'], r['slot_hoop']['max'], r['slot_hoop']['T'])
                if r['slot_hoop'] else '',
                ', platform hoop %.0f..%.0f MPa' % (r['plat_hoop']['min'], r['plat_hoop']['max']) if r['plat_hoop'] else ''))


def main():
    out = {}
    for row in ('R1', 'R2'):
        for N, tag in ((15000.0, 'op'), (16500.0, 'trip')):
            for th in (True, False):
                r = run(row, N, tag, thermal=th); out['%s_%s%s' % (row, tag, '' if th else '_mech')] = r
                print(summary(r), flush=True)
    json.dump(out, open(os.path.join(FEA, 'a1000_disc.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
