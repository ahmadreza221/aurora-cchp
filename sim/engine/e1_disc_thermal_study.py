#!/usr/bin/env python3
"""GR180-CCHP E1 - turbine disc: steady thermal field (CalculiX) -> thermo-mechanical stress, current bore vs bore-less disc.

The axisymmetric study in e1_turbine_fea.py prescribes a linear metal temperature (bore 450 C -> platform 730 C). Here the
temperature comes from a steady heat-conduction run with estimated boundary conditions (two sets, to show the sensitivity),
and a bore-less variant (wheel welded to a stub shaft, turbocharger practice) is compared with the current Ø8 bore.
Boundary conditions are ESTIMATES (no CFD / test data yet): replace with measured or CFD cavity temperatures and h.

  platform (blade root)       fixed 730 C (as e1_turbine_fea.T_BLADE)
  front face (bearing-tunnel / buffer air), rear face (exhaust-side cavity), bore + sleeve (into shaft / 608 ring): film

Run:  python sim/engine/e1_disc_thermal_study.py [--opt | --rear]  (CCX = path to ccx; gmsh python module required)
  default  current bore vs bore-less (DISC profile), nominal + hot BC sets
  --opt    bore-less web study (web thickness, web fillet, hub shoulders), nominal BCs
  --rear   rear-face protection on the bore-less w6/R4 disc: baseline, heat shield, cooling bleed, both
  --creep  creep FEA (Norton law fitted to the IN713LC Larson-Miller curve, Monkman-Grant), 10 000 / 50 000 h at 115k
Writes sim/engine/fea/thermo_study.json, boreless_opt.json, rear_cooling_study.json, creep_study.json
"""
import itertools
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import e1_turbine_fea as F                               # noqa: E402  (mesh, ccx, material, axisym_run)
import life_study as LS                                  # noqa: E402  (IN713LC Larson-Miller)
G = F.G

BCS = {'nominal': dict(Tf=250, hf=400, Tr=600, hr=150, Tb=150, hb=1500),     # C, W/m2K
       'hot':     dict(Tf=450, hf=200, Tr=650, hr=150, Tb=250, hb=800)}
T_PLAT = 730.0
BORELESS_W6R4 = dict(r_bore=0.0, xf_w=110.6, xr_w=116.6, R_web=4.0)
# rear-face options (front / sink as 'nominal'): rear gas temperature C, h W/m2K -- ESTIMATES, to be replaced by CFD
REAR = {'baseline (exhaust cavity)': (600, 150), 'heat shield': (450, 80), 'cooling bleed ~0.5-1 %': (250, 400),
        'shield + bleed': (220, 300)}


MONKMAN_GRANT = 0.05      # eps_dot_min * t_rupture for Ni superalloys (0.02-0.1): minimum creep rate from rupture life


def norton_cards():
    """*CREEP, LAW=NORTON (eps_dot = A sigma^n, MPa, 1/s) fitted per temperature to the life_study Larson-Miller curve."""
    lines = []
    for T in (450, 500, 550, 600, 650, 700, 750, 800):
        sg = np.array([350., 450., 550., 650.])
        ed = MONKMAN_GRANT / (np.array([LS.creep_hours(x, T + 273.15) for x in sg]) * 3600.0)
        n, lnA = np.polyfit(np.log(sg), np.log(ed), 1)
        lines.append('%.5e, %.4f, 0., %.1f\n' % (math.exp(lnA), n, T))
    return '*CREEP, LAW=NORTON\n' + ''.join(lines)


def boundary_edges(els):
    cnt = {}
    for ei, e in enumerate(els, 1):
        for fi, (i, j, m) in enumerate(((0, 1, 3), (1, 2, 4), (2, 0, 5)), 1):
            cnt.setdefault(tuple(sorted((e[i], e[j]))), []).append((ei, fi, e[i], e[j], e[m]))
    return [v[0] for v in cnt.values() if len(v) == 1]


def classify(nodes, edges, P):
    """Boundary edges -> platform / sink (bore, sleeve OD, sleeve face) / front / rear / axis."""
    rb = P.get('r_bore', 4.0)
    xm_disc = 0.5 * (P['xf_w'] + P['xr_w'])
    out = {'plat': [], 'sink': [], 'front': [], 'rear': [], 'axis': []}
    for ed in edges:
        A, B = nodes[ed[2]], nodes[ed[3]]
        r, x = 0.5 * (A[0] + B[0]), 0.5 * (A[1] + B[1])
        if abs(A[0]) < 1e-6 and abs(B[0]) < 1e-6:
            out['axis'].append(ed)
        elif G.X_PF - 0.05 <= x <= G.X_PR + 0.05 and abs(r - float(G.r_hub(np.clip(x, G.X_PF, G.X_PR)))) < 0.03:
            out['plat'].append(ed)
        elif (rb > 0 and abs(r - rb) < 1e-3) or (abs(r - 6.40) < 0.03 and x < 108.6) or abs(x - G.X_HUB) < 1e-3:
            out['sink'].append(ed)
        elif x < xm_disc:
            out['front'].append(ed)
        else:
            out['rear'].append(ed)
    return out


def thermal(nodes, els, P, bc, tag):
    """Steady conduction (CAX6), returns {node: T C}. Units mm-t-s: k [W/mK] = [mW/mm K], h [W/m2K] x 1e-3."""
    E = classify(nodes, boundary_edges(els), P)
    job = 'th_' + tag
    with open(os.path.join(F.FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f\n' % (k, v[0], v[1]) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=CAX6, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        plat = sorted({n for ed in E['plat'] for n in ed[2:]})
        f.write('*NSET, NSET=NPLAT\n' + ''.join('%d,\n' % k for k in plat))
        f.write('*MATERIAL, NAME=IN713LC\n*CONDUCTIVITY\n' + ''.join('%.2f, %.1f\n' % (k, t) for k, t in zip(F.MAT_K, F.MAT_T)))
        f.write('*SOLID SECTION, ELSET=EALL, MATERIAL=IN713LC\n*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 400.\n')
        f.write('*STEP\n*HEAT TRANSFER, STEADY STATE\n*BOUNDARY\nNPLAT, 11, 11, %.1f\n*FILM\n' % T_PLAT)
        for key, T, h in (('front', bc['Tf'], bc['hf']), ('rear', bc['Tr'], bc['hr']), ('sink', bc['Tb'], bc['hb'])):
            f.write(''.join('%d, F%d, %.1f, %.4e\n' % (ed[0], ed[1], T, h * 1e-3) for ed in E[key]))
        f.write('*NODE FILE\nNT\n*END STEP\n')
    F.run_ccx(job, threads=4)
    nd, blocks = F.read_frd(os.path.join(F.FEA, job + '.frd'))
    return {k: float(v[0]) for k, v in [b for b in blocks if b.get('name') == 'NDTEMP'][-1]['data'].items()}


def case(P, bcname, tag, cold=True):
    nodes, els = F.axisym_mesh(P, 0.25)          # deterministic: axisym_run meshes the same profile identically
    Tn = thermal(nodes, els, P, BCS[bcname], tag)
    hot = F.axisym_run(P, F.N_DES, True, tag + '_h', Tn=Tn)
    c = F.axisym_run(P, F.N_DES, False, tag + '_c') if cold else None
    k = min(nodes, key=lambda n: math.hypot(nodes[n][0] - hot['vm_max_at'][0], nodes[n][1] - hot['vm_max_at'][1]))
    return dict(P=P, bc=bcname, T_min=min(Tn.values()), T_peak=Tn[k], hot=hot, cold=c,
                burst_k=F.N_DES * math.sqrt(0.85 * F.UTS(hot['T_avg']) / (c or hot)['hoop_avg']) / 1e3,
                ys_peak=F.YS(Tn[k]), creep_h_peak=LS.creep_hours(hot['vm_max'], Tn[k] + 273.15))


def report(tag, r):
    h, c = r['hot'], r['cold']
    print('%-32s peak hot %4.0f MPa at (r %.1f, x %.1f) %3.0f C, bore/centre %4.0f | cold peak %s | YSmin %3.0f -> margin %.2f'
          ' | burst %.0fk | local creep %.0f h' % (tag, h['vm_max'], h['vm_max_at'][0], h['vm_max_at'][1], r['T_peak'], h['bore_vm'],
                                                  '%4.0f' % c['vm_max'] if c else '  - ', r['ys_peak'], r['ys_peak'] / h['vm_max'],
                                                  r['burst_k'], r['creep_h_peak']), flush=True)


def main():
    rot = G.design_rotor()
    sb, Fp, Ar, tap, r0 = G.blade_pull_estimate(rot)
    F.AXI_ROT, F.AXI_F115 = rot, Fp * 1.08
    print('blade pull %.0f N (+8 %% fillets -> %.0f N)' % (Fp, F.AXI_F115))
    if '--creep' in sys.argv:
        out = {}
        cards = norton_cards()
        # bore-less only: the current Ø8 bore is above yield (1172 MPa), outside the creep-law fit (350-650 MPa)
        for name, P in (('boreless_w6R4', dict(G.DISC, **BORELESS_W6R4)),):
            nodes, els = F.axisym_mesh(P, 0.25)
            Tn = thermal(nodes, els, P, BCS['nominal'], 'cr_' + name)
            el = F.axisym_run(P, F.N_DES, True, 'cr_%s_0h' % name, Tn=Tn)
            for hrs in (10000.0, 50000.0):
                r = F.axisym_run(P, F.N_DES, True, 'cr_%s_%dh' % (name, hrs), Tn=Tn, creep=dict(cards=cards, hours=hrs))
                print('%-14s %6.0f h: creep strain max %.3f %% at (r %.1f, x %.1f) | peak vM %4.0f -> %4.0f MPa | bore/centre %4.0f -> %4.0f'
                      ' | rim growth %.4f -> %.4f mm (creep +%.4f)' % (
                          name, hrs, 100 * r.get('peeq_max', float('nan')), *r.get('peeq_at', (float('nan'),) * 2)[:2], el['vm_max'],
                          r['vm_max'], el['bore_vm'], r['bore_vm'], el['u_rim'], r['u_rim'], r['u_rim'] - el['u_rim']), flush=True)
                out['%s_%dh' % (name, hrs)] = dict(elastic=el, creep=r)
        json.dump(out, open(os.path.join(F.FEA, 'creep_study.json'), 'w'), indent=1, default=float)
        return
    if '--rear' in sys.argv:
        rows = {}
        P = dict(G.DISC, **BORELESS_W6R4)
        for k, (Tr, hr) in REAR.items():
            BCS['rear_case'] = dict(BCS['nominal'], Tr=Tr, hr=hr)
            tag = 'rear_' + ''.join(c for c in k.split()[0] if c.isalnum())
            r = case(P, 'rear_case', tag, cold=False)
            print('%-26s rear %3d C h %3d:' % (k, Tr, hr), end=' ')
            report(tag, r)
            rows[k] = r
        json.dump(rows, open(os.path.join(F.FEA, 'rear_cooling_study.json'), 'w'), indent=1, default=float)
        return
    if '--opt' in sys.argv:
        rows = []
        xm = 113.6
        for w, Rw, rhr, rhf in itertools.product((4.0, 5.0, 6.0), (2.5, 4.0), (6.5, 9.5), (6.4, 9.5)):
            P = dict(G.DISC, r_bore=0.0, xf_w=xm - w / 2, xr_w=xm + w / 2, R_web=Rw, r_hr=rhr, r_hf=rhf)
            tag = 'bl_w%.0f_R%.1f_hr%.1f_hf%.1f' % (w, Rw, rhr, rhf)
            try:
                r = case(P, 'nominal', tag)
            except Exception as ex:          # invalid profile combination (fillets overlap) -> skipped, reported
                print(tag, 'failed:', str(ex)[:100])
                continue
            report(tag, r)
            rows.append(dict(tag=tag, **r))
        json.dump(rows, open(os.path.join(F.FEA, 'boreless_opt.json'), 'w'), indent=1, default=float)
        return
    res = {}
    for name, P in (('bore', dict(G.DISC)), ('boreless', dict(G.DISC, r_bore=0.0)),
                    ('boreless_w6R4', dict(G.DISC, r_bore=0.0, xf_w=110.6, xr_w=116.6, R_web=4.0))):
        for bcname in ('nominal', 'hot'):
            tag = '%s_%s' % (name, bcname)
            r = case(P, bcname, tag, cold=bcname == 'nominal')
            report(tag, r)
            res[tag] = r
    json.dump(res, open(os.path.join(F.FEA, 'thermo_study.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
