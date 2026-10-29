#!/usr/bin/env python3
"""AURORA-1000: choice of the NGV1 / NGV2 vane counts against the rotor-blade frequencies (interference at 15,000 rpm).

Excitations of the rotors by the stator rows:
  R1: N1 wakes (strong, 10 % margin), N2 potential field (9 mm gap: 10 %), 2 x N1 and 2 x N2 (weak, 5 %)
  R2: N2 wakes (strong, 10 %), N1 wakes carried through R1 / N2 (weak, 5 %), 2 x N2 (weak, 5 %)
Margins are the worst over the grid band 14,700-15,300 rpm (0 when the order crosses a mode inside the band).
Frequencies: coupled blade-disc families from the cyclic blisk model (sim/engine/a1000_blisk_cyclic.py) for the nodal
diameter each order reaches; an order whose nodal diameter was not solved is UNKNOWN (rev 4: rev 3 scored it 100 %), and
the rigid-hub blade modes (sim/engine/a1000_blade_fea.py) are shown beside it as an indication only. An order above the
highest computed mode is also UNKNOWN.
Aero limits: Zweifel of the vane rows scaled from the design (Zw ~ pitch / cx): 0.70 <= Zw <= 1.12 (axial chord scale
allowed 0.9 .. 1.2 for N2); vane count differs from the downstream blade count by >= 4 (low-ND disc excitation, noise).
Run:    python3 sim/engine/a1000_vane_count.py
Writes: sim/engine/fea/a1000_vane_count.json
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FEA = os.path.join(HERE, 'fea')
N_OP = 15000.0
BAND = (0.98, 1.02)
DES = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
Z_R = dict(R1=DES['R1']['Z'], R2=DES['R2']['Z'])
ZW_LIM = (0.70, 1.12)


def load(name):
    p = os.path.join(FEA, name)
    return json.load(open(p)) if os.path.exists(p) else None


def band_margin(fl, k):
    """(worst signed margin over the band, frequency) of order k against the frequency list fl; None if not covered"""
    if not fl or max(fl) < k * BAND[1] * N_OP / 60 * 1.05: return None
    best = None
    for f in fl:
        mb = [(f - k * b * N_OP / 60) / (k * b * N_OP / 60) for b in BAND]
        m = 0.0 if mb[0] * mb[1] <= 0 else min(mb, key=abs)
        if best is None or abs(m) < abs(best[0]): best = (m, f)
    return best


def sources(row):
    c = load('a1000_blisk_%s_cyclic.json' % row)
    tab = {int(k): v for k, v in c['freqs'].items()} if c else {}
    b = load('a1000_blade_%s.json' % row)
    rig = b['freqs'][str(int(N_OP))] if b else []
    Z = Z_R[row]
    def nd(k): m = k % Z; return min(m, Z - m)
    return tab, rig, nd


def main():
    src = {r: sources(r) for r in ('R1', 'R2')}
    print('cyclic NDs solved: R1 %s, R2 %s' % (sorted(src['R1'][0]), sorted(src['R2'][0])))
    zw1 = [s['zweifel'] for s in DES['N1']['sections']]; zw2 = [s['zweifel'] for s in DES['N2']['sections']]
    Z1_0, Z2_0 = DES['N1']['Z'], DES['N2']['Z']
    res = []
    for n1 in range(36, 53):
        z1 = [z * Z1_0 / n1 for z in zw1]
        if not (ZW_LIM[0] <= min(z1) and max(z1) <= ZW_LIM[1]): continue
        for n2 in range(24, 56):
            z2 = [z * Z2_0 / n2 for z in zw2]
            cs = 1.0
            if max(z2) > ZW_LIM[1]: cs = max(z2) / ZW_LIM[1]
            if min(z2) / cs < ZW_LIM[0] or cs > 1.2: continue
            if abs(n2 - Z_R['R2']) < 4 or abs(n1 - Z_R['R1']) < 4 or abs(n2 - Z_R['R1']) < 4: continue
            checks = [('R1', 'N1', n1, 0.10), ('R1', 'N2', n2, 0.10), ('R1', '2N1', 2 * n1, 0.05), ('R1', '2N2', 2 * n2, 0.05),
                      ('R2', 'N2', n2, 0.10), ('R2', 'N1', n1, 0.05), ('R2', '2N2', 2 * n2, 0.05)]
            ms, need = [], set()
            for row, lab, k, req in checks:
                tab, rig, nd = src[row]
                cy = band_margin(tab.get(nd(k)), k) if nd(k) in tab else None
                rg = band_margin(rig, k)
                if cy is None: need.add((row, nd(k)))
                ms.append(dict(row=row, order=lab, eo=k, nd=nd(k), req=req, cyclic=cy, rigid=rg))
            known = [m for m in ms if m['cyclic'] is not None]
            ratio = min((abs(m['cyclic'][0]) / m['req'] for m in known), default=float('nan'))
            ratio_rig = min((abs(m['rigid'][0]) / m['req'] if m['rigid'] else 0.0 for m in ms))
            res.append(dict(n1=n1, n2=n2, cx2_scale=cs, ratio_cyclic=ratio, ratio_rigid=ratio_rig, complete=not need,
                            need_nd=sorted(need), zw1=(min(z1), max(z1)), zw2=(min(z2) / cs, max(z2) / cs), checks=ms))
    cur = [r for r in res if r['n1'] == Z1_0 and r['n2'] == Z2_0]
    print('current N1 %d / N2 %d:' % (Z1_0, Z2_0))
    for r in cur:
        for m in r['checks']:
            cy = ('%+6.1f %% (%.0f Hz)' % (100 * m['cyclic'][0], m['cyclic'][1])) if m['cyclic'] else 'UNKNOWN (ND %d not solved / not reached)' % m['nd']
            rg = ('%+6.1f %%' % (100 * m['rigid'][0])) if m['rigid'] else 'not reached'
            print('   %s %-3s EO%-3d -> ND%-2d need %2.0f %%: cyclic %s; rigid hub %s' % (m['row'], m['order'], m['eo'], m['nd'],
                                                                                     100 * m['req'], cy, rg))
    ok = sorted([r for r in res if r['complete'] and r['ratio_cyclic'] >= 1.0],
                key=lambda r: (abs(r['n1'] - Z1_0) + abs(r['n2'] - Z2_0) + 4 * (r['cx2_scale'] - 1), -r['ratio_cyclic']))
    print('feasible on solved cyclic data (all orders known, all margins met):')
    for r in ok[:10]:
        print('  N1 %2d  N2 %2d  (N2 cx x%.2f)  min margin/required %.2f  Zw N1 %.2f-%.2f  N2 %.2f-%.2f' % (
            r['n1'], r['n2'], r['cx2_scale'], r['ratio_cyclic'], *r['zw1'], *r['zw2']))
    cand = sorted([r for r in res if not r['complete'] and r['ratio_rigid'] >= 1.0 and
                   (r['ratio_cyclic'] != r['ratio_cyclic'] or r['ratio_cyclic'] >= 1.0)],
                  key=lambda r: (len(r['need_nd']), -min(r['ratio_rigid'], 2.0)))
    print('candidates passing on the rigid hub and on the solved NDs, NDs still to solve:')
    for r in cand[:10]:
        print('  N1 %2d  N2 %2d  rigid ratio %.2f, cyclic ratio (solved) %s, need %s' % (
            r['n1'], r['n2'], r['ratio_rigid'], '%.2f' % r['ratio_cyclic'] if r['ratio_cyclic'] == r['ratio_cyclic'] else '-',
            ', '.join('%s ND%d' % q for q in r['need_nd'])))
    json.dump(dict(band=BAND, current=cur, feasible=ok, candidates=cand[:20]),
              open(os.path.join(FEA, 'a1000_vane_count.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
