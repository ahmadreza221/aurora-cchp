#!/usr/bin/env python3
"""AURORA-1000: choice of the NGV1 / NGV2 vane counts against the rotor-blade frequencies (interference at 15,000 rpm).

Excitations of the rotors by the stator rows:
  R1: N1 wakes (strong, 10 % margin), N2 potential field (9 mm gap: 10 %), 2 x N1 wakes (weak, 5 %). The 2nd harmonic of
      the N2 potential field is not counted: it decays upstream as exp(-4 pi g / s) = 0.026 at g = 9 mm, s = 31 mm
      (1st harmonic: 0.16), negligible forcing (rev 4)
  R2: N2 wakes (strong, 10 %), N1 wakes carried through R1 / N2 (weak, 5 %), 2 x N2 (weak, 5 %)
Margins are the worst over the grid band 14,700-15,300 rpm (0 when the order crosses a mode inside the band). Strong
orders are checked against every mode; weak orders against the coupled modes below 1.05 x the rigid-hub blade mode
WEAK_MODES (rev 5: a family index would skip blade modes at low ND, where disc modes interleave; the dense higher modes
have small modal forces at 2 x NPF: they are left to the forced-response analysis and the tip-timing test).
Frequencies: coupled blade-disc families from the cyclic blisk model (sim/engine/a1000_blisk_cyclic.py) for the nodal
diameter each order reaches; an order whose nodal diameter was not solved is UNKNOWN (rev 4: rev 3 scored it 100 %), and
the rigid-hub blade modes (sim/engine/a1000_blade_fea.py) are shown beside it as an indication only. An order above the
highest computed mode is also UNKNOWN.
R1 also sees the 2nd harmonic of the N2 potential field when it is not negligible: exp(-4 pi g / s) >= 0.05 (a few
large-pitch vanes), then 2 x N2 is a weak order on R1. Vane-vane interaction: the N1 wakes chopped by the N2 vanes (and the
N2 field seen through R1) carry the circumferential order |N1 - N2| on both rotors (rev 5). Its forcing is of second order
(product of the N1 wake left after two rows and the N2 clocking modulation, ~1e-2 of the N2 wake): it must not cross a mode
of the first WEAK_MODES families inside the grid band (REQ_INT), the response near the band edges is left to the
forced-response estimate and the tip-timing test.
Aero limits: Zweifel of the vane rows scaled from the design (Zw ~ pitch / cx): 0.70 <= Zw <= 1.12, the axial chord is
scaled up to keep Zw <= 1.12 (N1 up to x1.1, N2 up to x1.7: the low counts with long chords pay a secondary loss, reported
as the Kacker-Okapuu aspect-ratio factor f(h/c) relative to the design); vane count differs from the downstream blade
count by >= 4 (low-ND disc excitation, noise).
Run:    python3 sim/engine/a1000_vane_count.py
Writes: sim/engine/fea/a1000_vane_count.json
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FEA = os.path.join(HERE, 'fea')
N_OP = 15000.0
BAND = (0.98, 1.02)
DES = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
Z_R = dict(R1=DES['R1']['Z'], R2=DES['R2']['Z'])
ZW_LIM = (0.70, 1.12)
CS_MAX = dict(N1=1.10, N2=1.70)          # largest axial-chord scale of the vane rows
WEAK_MODES = 6                           # weak orders: coupled modes below 1.05 x the rigid-hub blade mode 6 (F_LIM)
F_LIM = {}
REQ_INT = 0.001                          # interaction order |N1 - N2|: outside the grid band (no crossing in 14.7-15.3k)
GAP_R1_N2 = 9.0                          # R1 TE - NGV2 LE [mm] (potential-field decay)
RM = DES['annulus']['rm']


def ko_far(hc):
    """Kacker-Okapuu secondary-loss aspect-ratio factor"""
    return (1 - 0.25 * (2 - hc) ** 0.5) / hc if hc <= 2 else 1 / hc


def hc_of(row):
    sec = DES[row]['sections']; st = DES['annulus']['stations']
    xm = 0.5 * (DES[row]['x_le'] + DES[row]['x_te'])
    h = float(__import__('numpy').interp(xm, [a for a, b in st], [b for a, b in st]))
    return h / (sum(x['chord'] for x in sec) / len(sec))


def load(name):
    p = os.path.join(FEA, name)
    return json.load(open(p)) if os.path.exists(p) else None


def band_margin(fl, k, req=0.10):
    """(worst signed margin over the band, frequency) of order k against the frequency list fl; None if the modes do not
    reach above the order and the computed ones do not already fail it (unknown)"""
    if not fl: return None
    best = None
    for f in fl:
        mb = [(f - k * b * N_OP / 60) / (k * b * N_OP / 60) for b in BAND]
        m = 0.0 if mb[0] * mb[1] <= 0 else min(mb, key=abs)
        if best is None or abs(m) < abs(best[0]): best = (m, f)
    if max(fl) < k * BAND[1] * N_OP / 60 * 1.05 and abs(best[0]) >= req: return None
    return best


def band_margin_lim(fl, k):
    """band margin against the given (first few) modes only; an order above all of them passes with the gap to the top one"""
    if not fl: return None
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
    F_LIM[row] = 1.05 * rig[WEAK_MODES - 1] if rig else float('inf')
    return tab, rig, nd


def main():
    src = {r: sources(r) for r in ('R1', 'R2')}
    print('cyclic NDs solved: R1 %s, R2 %s' % (sorted(src['R1'][0]), sorted(src['R2'][0])))
    zw1 = [s['zweifel'] for s in DES['N1']['sections']]; zw2 = [s['zweifel'] for s in DES['N2']['sections']]
    Z1_0, Z2_0 = DES['N1']['Z'], DES['N2']['Z']
    res = []
    cx1_0, cx2_0 = (DES[r]['x_te'] - DES[r]['x_le'] for r in ('N1', 'N2'))
    hc1_0, hc2_0 = hc_of('N1'), hc_of('N2')
    def scale(zw, n, n0, row):
        z = [v * n0 / n for v in zw]; cs = max(1.0, max(z) / ZW_LIM[1])
        return (cs, (min(z) / cs, max(z) / cs)) if min(z) / cs >= ZW_LIM[0] and cs <= CS_MAX[row] else (None, None)
    for n1 in range(20, 56):
        cs1, z1 = scale(zw1, n1, Z1_0, 'N1')
        if cs1 is None: continue
        for n2 in range(20, 56):
            cs, z2 = scale(zw2, n2, Z2_0, 'N2')
            if cs is None: continue
            if abs(n2 - Z_R['R2']) < 4 or abs(n1 - Z_R['R1']) < 4 or abs(n2 - Z_R['R1']) < 4: continue
            checks = [('R1', 'N1', n1, 0.10), ('R1', 'N2', n2, 0.10), ('R1', '2N1', 2 * n1, 0.05),
                      ('R2', 'N2', n2, 0.10), ('R2', 'N1', n1, 0.05), ('R2', '2N2', 2 * n2, 0.05)]
            pf2 = math.exp(-4 * math.pi * GAP_R1_N2 / (2 * math.pi * RM / n2))
            if pf2 >= 0.05: checks.insert(3, ('R1', '2N2', 2 * n2, 0.05))
            if abs(n1 - n2) > 5: checks += [('R1', 'N1-N2', abs(n1 - n2), REQ_INT), ('R2', 'N1-N2', abs(n1 - n2), REQ_INT)]
            ms, need = [], set()
            for row, lab, k, req in checks:
                tab, rig, nd = src[row]
                nm = WEAK_MODES if req < 0.10 else None              # weak and interaction orders: first blade modes
                fl_all = tab.get(nd(k))
                fl_c = (fl_all if nm is None else [f for f in fl_all if f <= F_LIM[row]] or fl_all[:1]) if fl_all else None
                cy = (band_margin(fl_c, k, req) if nm is None else band_margin_lim(fl_c, k)) if fl_c else None
                if cy and nm and max(fl_all) < min(k * BAND[1] * N_OP / 60 * 1.05, F_LIM[row]) and abs(cy[0]) >= req:
                    cy = None                                        # the computed families stop short: unknown
                rg = band_margin(rig, k) if nm is None else band_margin_lim(rig[:nm], k)
                if cy is None: need.add((row, nd(k)))
                ms.append(dict(row=row, order=lab, eo=k, nd=nd(k), req=req, cyclic=cy, rigid=rg))
            known = [m for m in ms if m['cyclic'] is not None]
            ratio = min((abs(m['cyclic'][0]) / m['req'] for m in known), default=float('nan'))
            ratio_rig = min((abs(m['rigid'][0]) / m['req'] if m['rigid'] else 0.0 for m in ms))
            if not need: pass
            res.append(dict(n1=n1, n2=n2, cx1_scale=cs1, cx2_scale=cs, cx1_mm=cx1_0 * cs1, cx2_mm=cx2_0 * cs,
                            ko_sec_N1=ko_far(hc1_0 / cs1) / ko_far(hc1_0), ko_sec_N2=ko_far(hc2_0 / cs) / ko_far(hc2_0),
                            ratio_cyclic=ratio, ratio_rigid=ratio_rig, complete=not need,
                            need_nd=sorted(need), zw1=z1, zw2=z2, checks=ms))
    cur = [r for r in res if r['n1'] == Z1_0 and r['n2'] == Z2_0]
    print('current N1 %d / N2 %d:' % (Z1_0, Z2_0))
    for r in cur:
        for m in r['checks']:
            cy = ('%+6.1f %% (%.0f Hz)' % (100 * m['cyclic'][0], m['cyclic'][1])) if m['cyclic'] else 'UNKNOWN (ND %d not solved / not reached)' % m['nd']
            rg = ('%+6.1f %%' % (100 * m['rigid'][0])) if m['rigid'] else 'not reached'
            print('   %s %-3s EO%-3d -> ND%-2d need %2.0f %%: cyclic %s; rigid hub %s' % (m['row'], m['order'], m['eo'], m['nd'],
                                                                                     100 * m['req'], cy, rg))
    ok = sorted([r for r in res if r['complete'] and r['ratio_cyclic'] >= 1.0],
                key=lambda r: (round(r['ko_sec_N2'] + r['ko_sec_N1'], 2), -r['ratio_cyclic']))
    print('feasible on solved cyclic data (all orders known, all margins met), least secondary loss first:')
    for r in ok[:12]:
        worst = min((m for m in r['checks'] if m['cyclic']), key=lambda m: abs(m['cyclic'][0]) / m['req'])
        print('  N1 %2d (cx %.1f, sec. loss x%.2f)  N2 %2d (cx %.1f, sec. loss x%.2f)  min margin/required %.2f (%s %s)'
              '  Zw N1 %.2f-%.2f  N2 %.2f-%.2f' % (r['n1'], r['cx1_mm'], r['ko_sec_N1'], r['n2'], r['cx2_mm'], r['ko_sec_N2'],
                                                 r['ratio_cyclic'], worst['row'], worst['order'], *r['zw1'], *r['zw2']))
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
