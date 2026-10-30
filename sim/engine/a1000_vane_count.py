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
Rev 6 (R1 EO24 start-up crossing, sim/engine/a1000_r1_eo24_options.py): --n1 48 keeps NGV1 and scans NGV2 12-40 (the
NGV2 axial chord may then also shrink to x0.8 to keep Zw >= 0.70 above 27 vanes); R1 2 x N1 = EO96 is closed by the
forced response for 48 vanes (sec. 12.4.1); the strong stator orders that cross blade families on the start line (40 % of
N_OP up to the band) are listed, and the R1 flap (family 1) crossings by the NGV2 potential field (1st and, when counted,
2nd harmonic) get a resonant-stress estimate scaled from the start-line CFD of N2 = 24: dynamic head of NGV2 at the
crossing speed (a1000_startup.py) x potential-field decay over the R1 surface exp(-(k - k24) d), k = n / r_m, d = distance
to the NGV2 LE (EO24 pressure distribution of the CFD as the weight; 2nd harmonic: x0.5 at the LE plane, decay 2k),
against the start-up allowable (Goodman / 2 of the cold blade, a1000_R1_eo24_options.json).
Run:    python3 sim/engine/a1000_vane_count.py [--n1 48]
Writes: sim/engine/fea/a1000_vane_count.json (--n1 48: a1000_vane_count_n1_48.json)
"""
import json
import math
import os
import sys

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
N_START = 0.40                           # rev 6: start-line crossings from 40 % speed up to the band
CS_MIN = dict(N1=1.0, N2=0.8)            # rev 6, --n1 only: shortest NGV axial chord (high counts, Zw >= 0.70)
FR_CLOSED = {48: (('R1', '2N1'),)}       # orders closed by the forced response for that NGV1 count (EO96, sec. 12.4.1)
CFD = os.path.join(ROOT, 'sim', 'cfd', 'a1000_r1_forcing')


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


def startup_model():
    """rev 6: resonant root stress [MPa] of an R1 flap crossing on the start line by the h-th harmonic of an N2-vane
    potential field at rpm, scaled from the start-line CFD of 24 vanes (a1000_R1_eo24_options.json); None if missing"""
    opt = load('a1000_R1_eo24_options.json')
    if not opt: return None
    import numpy as np
    sys.path.insert(0, HERE); import a1000_startup as SU
    fc = json.load(open(os.path.join(CFD, 'forcing.json'))); g = json.load(open(os.path.join(CFD, 'geometry.json')))['rows']
    x = np.array(g['R1']['x']); tau = np.array(fc['tau']); h = fc['harmonics']['24']
    xt = np.interp(tau, np.arange(len(x) + 1) / len(x), np.r_[x, x[:1]]); d = g['N2']['x_le'] - xt
    w = np.hypot(h['re'], h['im'])
    F = opt['forcing'].get('st') or opt['forcing']['design']
    s24 = F['resonant_root_mist']; rpm24 = (F.get('state') or {}).get('rpm', 12270.0)
    lim = min(q['limit'] for q in opt['option1']['criteria'])
    tit = opt['start_line']['cfd_state']['tit']; cache = {}; SU.design()          # (calibrates the turbine meanline)
    def q(rpm):
        k = round(rpm, -1)
        if k not in cache:                                  # low speeds: the schedule TIT falls (no match at the CFD TIT)
            st = next(m for m in (SU.match(k / N_OP, t) for t in (tit, tit - 100, tit - 200, tit - 300)) if m)
            cache[k] = SU.q_ngv2(st)
        return cache[k]
    def sigma(n2, harm, rpm):
        D = float(np.sum(w * np.exp(-(harm * n2 - 24) / RM * d)) / np.sum(w)) * (0.5 if harm == 2 else 1.0)
        return [v * q(rpm) / q(rpm24) * D for v in s24], D
    return dict(sigma=sigma, limit=lim, zeta=opt['zeta'])


def main(n1_fix=None):
    src = {r: sources(r) for r in ('R1', 'R2')}
    smod = startup_model() if n1_fix else None
    print('cyclic NDs solved: R1 %s, R2 %s' % (sorted(src['R1'][0]), sorted(src['R2'][0])))
    zw1 = [s['zweifel'] for s in DES['N1']['sections']]; zw2 = [s['zweifel'] for s in DES['N2']['sections']]
    Z1_0, Z2_0 = DES['N1']['Z'], DES['N2']['Z']
    res = []
    cx1_0, cx2_0 = (DES[r]['x_te'] - DES[r]['x_le'] for r in ('N1', 'N2'))
    hc1_0, hc2_0 = hc_of('N1'), hc_of('N2')
    def scale(zw, n, n0, row):
        z = [v * n0 / n for v in zw]; cs = max(1.0, max(z) / ZW_LIM[1])
        if n1_fix and min(z) < ZW_LIM[0]: cs = max(CS_MIN[row], min(z) / ZW_LIM[0])     # rev 6: shorter chord
        return (cs, (min(z) / cs, max(z) / cs)) if (min(z) / cs >= ZW_LIM[0] - 1e-9 and max(z) / cs <= ZW_LIM[1] + 1e-9
                                                    and CS_MIN[row] <= cs <= CS_MAX[row]) else (None, None)
    for n1 in ([n1_fix] if n1_fix else range(20, 56)):
        cs1, z1 = scale(zw1, n1, Z1_0, 'N1')
        if cs1 is None: continue
        for n2 in (range(12, 41) if n1_fix else range(20, 56)):
            cs, z2 = scale(zw2, n2, Z2_0, 'N2')
            if cs is None: continue
            if abs(n2 - Z_R['R2']) < 4 or abs(n1 - Z_R['R1']) < 4 or abs(n2 - Z_R['R1']) < 4: continue
            checks = [('R1', 'N1', n1, 0.10), ('R1', 'N2', n2, 0.10), ('R1', '2N1', 2 * n1, 0.05),
                      ('R2', 'N2', n2, 0.10), ('R2', 'N1', n1, 0.05), ('R2', '2N2', 2 * n2, 0.05)]
            pf2 = math.exp(-4 * math.pi * GAP_R1_N2 / (2 * math.pi * RM / n2))
            if pf2 >= 0.05: checks.insert(3, ('R1', '2N2', 2 * n2, 0.05))
            if abs(n1 - n2) > 5 and abs(n1 - n2) not in (n1, n2): checks += [('R1', 'N1-N2', abs(n1 - n2), REQ_INT), ('R2', 'N1-N2', abs(n1 - n2), REQ_INT)]
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
                ms.append(dict(row=row, order=lab, eo=k, nd=nd(k), req=req, cyclic=cy, rigid=rg,
                               closed_by_forced_response=(row, lab) in (FR_CLOSED.get(n1, ()) if n1_fix else ())))
            # rev 6: start-line crossings of the strong orders (+ the 2nd potential harmonic on R1)
            su = []
            for row, lab, k, req in (checks if n1_fix else ()):
                if req < 0.10 and (row, lab) != ('R1', '2N2'): continue
                tab, rig, nd = src[row]
                for fam, f in enumerate(tab.get(nd(k)) or [], 1):
                    rpm = 60 * f / k
                    if not N_START * N_OP <= rpm < BAND[0] * N_OP: continue
                    c = dict(row=row, order=lab, eo=k, nd=nd(k), family=fam, f=f, rpm=rpm)
                    if smod and row == 'R1' and lab in ('N2', '2N2') and fam == 1:
                        sg, D = smod['sigma'](n2, 2 if lab == '2N2' else 1, rpm)
                        c.update(sigma=sg, decay=D, ok=sg[0] <= smod['limit'], fail=sg[-1] > smod['limit'])
                    su.append(c)
            known = [m for m in ms if m['cyclic'] is not None and not m['closed_by_forced_response']]
            ratio = min((abs(m['cyclic'][0]) / m['req'] for m in known), default=float('nan'))
            ratio_rig = min((abs(m['rigid'][0]) / m['req'] if m['rigid'] else 0.0 for m in ms))
            if not need: pass
            res.append(dict(n1=n1, n2=n2, cx1_scale=cs1, cx2_scale=cs, cx1_mm=cx1_0 * cs1, cx2_mm=cx2_0 * cs,
                            ko_sec_N1=ko_far(hc1_0 / cs1) / ko_far(hc1_0), ko_sec_N2=ko_far(hc2_0 / cs) / ko_far(hc2_0),
                            ratio_cyclic=ratio, ratio_rigid=ratio_rig, complete=not need,
                            need_nd=sorted(need), zw1=z1, zw2=z2, checks=ms, startup=su))
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
        worst = min((m for m in r['checks'] if m['cyclic'] and not m.get('closed_by_forced_response')),
                    key=lambda m: abs(m['cyclic'][0]) / m['req'])
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
    if n1_fix:
        lim = smod['limit'] if smod else float('nan')
        print('NGV1 = %d kept, NGV2 scan: in-band rules (R1 + R2, EO96 closed by forced response); start-line crossings of the '
              'strong orders (%.0f %% speed to the band); R1 flap by the N2 potential field: resonant root stress x1.5 '
              'mistuning at zeta %s %% vs start-up Goodman/2 %.0f MPa' % (
                  n1_fix, 100 * N_START, '/'.join('%.2g' % (100 * z) for z in (smod['zeta'] if smod else ())), lim))
        for r in sorted(res, key=lambda r: r['n2']):
            bad = [m for m in r['checks'] if m['cyclic'] and not m['closed_by_forced_response'] and abs(m['cyclic'][0]) < m['req']]
            band = ('ok (min margin / required %.2f)' % r['ratio_cyclic'] if r['complete'] and not bad else
                    'FAIL ' + ', '.join('%s %s EO%d %+.1f %%' % (m['row'], m['order'], m['eo'], 100 * m['cyclic'][0]) for m in bad[:3])
                    if bad else 'UNKNOWN (%s)' % ', '.join('%s ND%d' % q for q in r['need_nd']))
            f1 = [c for c in r['startup'] if 'sigma' in c]
            f1s = '; '.join('%s EO%d at %.0f rpm: %s MPa%s' % (c['order'], c['eo'], c['rpm'], '/'.join('%.0f' % v for v in c['sigma']),
                                                             ' ok' if c['ok'] else (' FAIL' if c['fail'] else ' marginal')) for c in f1) or 'no R1 flap crossing'
            other = ['%s %s F%d %.0f' % (c['row'], c['order'], c['family'], c['rpm']) for c in r['startup'] if 'sigma' not in c]
            r['band_verdict'] = band
            print('  N2 %2d (cx %4.1f mm x%.2f, Zw %.2f-%.2f, sec. loss x%.2f): band %s\n        R1 flap: %s\n        other '
                  'crossings (rpm): %s' % (r['n2'], r['cx2_mm'], r['cx2_scale'], *r['zw2'], r['ko_sec_N2'], band, f1s,
                                           ', '.join(other) or '-'))
        json.dump(dict(band=BAND, n1=n1_fix, start_limit=lim, scan=sorted(res, key=lambda r: r['n2'])),
                  open(os.path.join(FEA, 'a1000_vane_count_n1_%d.json' % n1_fix), 'w'), indent=1, default=float)
        return res
    json.dump(dict(band=BAND, current=cur, feasible=ok, candidates=cand[:20]),
              open(os.path.join(FEA, 'a1000_vane_count.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main(int(sys.argv[sys.argv.index('--n1') + 1]) if '--n1' in sys.argv else None)
