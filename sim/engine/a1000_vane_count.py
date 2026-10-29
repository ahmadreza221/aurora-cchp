#!/usr/bin/env python3
"""AURORA-1000: choice of the NGV1 / NGV2 vane counts against the rotor-blade frequencies (interference at 15,000 rpm).

Excitations of the rotors by the stator rows:
  R1: N1 wakes (strong, 10 % margin), N2 potential field (9 mm gap: 10 %), 2 x N1 (weak, 5 %)
  R2: N2 wakes (strong, 10 %), N1 wakes carried through R1 / N2 (weak, 5 %), 2 x N2 (weak, 5 %)
Frequencies: blade modes at 15,000 rpm from the cyclic blisk model (sim/engine/a1000_blisk_cyclic.py, the families of the
nodal diameter each order reaches) when available, else the rigid-hub blade model (sim/engine/a1000_blade_fea.py).
Aero limits: Zweifel of the vane rows scaled from the design (Zw ~ pitch / cx): 0.70 <= Zw <= 1.12 (axial chord scale
allowed 0.9 .. 1.2 for N2); vane count differs from the downstream blade count by >= 4 (low-ND disc excitation, noise).
Run:    python3 sim/engine/a1000_vane_count.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FEA = os.path.join(HERE, 'fea')
N_OP = 15000.0
DES = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
Z_R = dict(R1=DES['R1']['Z'], R2=DES['R2']['Z'])
ZW_LIM = (0.70, 1.12)


def freqs(row):
    """{eo -> list of frequencies [Hz] that order can excite at 15,000 rpm}, source"""
    cyc = os.path.join(FEA, 'a1000_blisk_%s_cyclic.json' % row)
    if os.path.exists(cyc):
        c = json.load(open(cyc)); Z = c['Z']; tab = {int(k): v for k, v in c['freqs'].items()}
        def f(k):
            m = k % Z; n = min(m, Z - m); return tab.get(n, [])
        return f, 'cyclic'
    b = json.load(open(os.path.join(FEA, 'a1000_blade_%s.json' % row)))
    fr = b['freqs'][str(int(N_OP))]
    return (lambda k: fr), 'rigid hub'


def margin(fl, k):
    fe = k * N_OP / 60
    return min((abs(f - fe) / fe, f) for f in fl) if fl else (1.0, None)


def main():
    fR1, s1 = freqs('R1'); fR2, s2 = freqs('R2')
    print('frequencies: R1 %s, R2 %s' % (s1, s2))
    zw1 = [s['zweifel'] for s in DES['N1']['sections']]; zw2 = [s['zweifel'] for s in DES['N2']['sections']]
    Z1_0, Z2_0 = DES['N1']['Z'], DES['N2']['Z']
    res = []
    for n1 in range(36, 53):
        z1 = [z * Z1_0 / n1 for z in zw1]
        if not (ZW_LIM[0] <= min(z1) and max(z1) <= ZW_LIM[1]): continue
        for n2 in range(24, 45):
            # N2 axial chord scale to bring the Zweifel band inside the limits (if needed)
            z2 = [z * Z2_0 / n2 for z in zw2]
            cs = 1.0
            if max(z2) > ZW_LIM[1]: cs = max(z2) / ZW_LIM[1]
            if min(z2) / cs < ZW_LIM[0] or cs > 1.2: continue
            if abs(n2 - Z_R['R2']) < 4 or abs(n1 - Z_R['R1']) < 4 or abs(n2 - Z_R['R1']) < 4: continue
            checks = [('R1', 'N1', n1, 0.10, fR1), ('R1', 'N2', n2, 0.10, fR1), ('R1', '2N1', 2 * n1, 0.05, fR1),
                      ('R2', 'N2', n2, 0.10, fR2), ('R2', 'N1', n1, 0.05, fR2), ('R2', '2N2', 2 * n2, 0.05, fR2)]
            ms = [(row, lab, k, req, *margin(fn(k), k)) for row, lab, k, req, fn in checks]
            ratio = min(m / req for _, _, _, req, m, _ in ms)
            res.append(dict(n1=n1, n2=n2, cx2_scale=cs, ratio=ratio, zw1=(min(z1), max(z1)),
                            zw2=(min(z2) / cs, max(z2) / cs), checks=ms))
    ok = sorted([r for r in res if r['ratio'] >= 1.0], key=lambda r: (abs(r['n1'] - Z1_0) + abs(r['n2'] - Z2_0) + 4 * (r['cx2_scale'] - 1), -r['ratio']))
    print('current N1 %d / N2 %d:' % (Z1_0, Z2_0))
    cur = [r for r in res if r['n1'] == Z1_0 and r['n2'] == Z2_0]
    for r in cur:
        for row, lab, k, req, m, f in r['checks']:
            print('   %s %-3s EO%-3d margin %5.1f %% (need %2.0f %%) nearest %s Hz' % (row, lab, k, 100 * m, 100 * req, '%.0f' % f if f else '-'))
    print('feasible (all margins met), closest to the current design first:')
    for r in ok[:12]:
        print('  N1 %2d  N2 %2d  (N2 cx x%.2f)  min margin/required %.2f   Zw N1 %.2f-%.2f  N2 %.2f-%.2f   %s' % (
            r['n1'], r['n2'], r['cx2_scale'], r['ratio'], *r['zw1'], *r['zw2'],
            '  '.join('%s/%s %.0f%%' % (row, lab, 100 * m) for row, lab, k, req, m, f in r['checks'])))
    json.dump(dict(source=dict(R1=s1, R2=s2), current=cur, feasible=ok), open(os.path.join(FEA, 'a1000_vane_count.json'), 'w'),
              indent=1, default=float)


if __name__ == '__main__':
    main()
