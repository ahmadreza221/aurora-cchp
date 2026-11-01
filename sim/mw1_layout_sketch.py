"""AURORA-1000 layout sketch (to scale, side elevation + rotor meridional half-section) from sim/mw1_results.json.
Run:  python3 sim/mw1_layout_sketch.py      writes docs/img/mw1_layout.png
"""
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
R = json.load(open(os.path.join(HERE, 'mw1_results.json')))
S = R['selected']; C = S['compressor']; T = S['turbine']

COL = dict(gen='#4c72b0', gear='#8172b2', comp='#55a868', comb='#dd8452', turb='#c44e52', rec='#937860', duct='#8c8c8c')


def box(ax, x, y, w, h, c, label, fs=8, txt='white'):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.01,rounding_size=0.05', fc=c, ec='k', lw=0.8))
    ax.text(x + w / 2, y + h / 2, label, ha='center', va='center', fontsize=fs, color=txt, weight='bold')


def main():
    fig = plt.figure(figsize=(15, 8.5), dpi=130)
    # ---- side elevation of the package (m)
    ax = fig.add_axes([0.04, 0.42, 0.92, 0.54])
    ax.add_patch(Rectangle((0, -0.15), 9.2, 0.15, fc='#d0d0d0', ec='k', lw=0.6)); ax.text(4.6, -0.08, 'base skid', ha='center', fontsize=7)
    zc = 0.85                                                       # shaft height
    box(ax, 0.2, zc - 0.65, 2.2, 1.3, COL['gen'], 'Synchronous generator\n1250 kVA, 4-pole, 1500 rpm\n0.4 / 6.3 kV')
    box(ax, 2.6, zc - 0.45, 0.8, 0.9, COL['gear'], 'Epicyclic\ngearbox\n15000 / 1500\n(10 : 1)', fs=7)
    box(ax, 3.55, zc - 0.55, 0.55, 1.1, COL['duct'], 'air\ninlet', fs=7)
    dc = C['D2']
    box(ax, 4.1, zc - dc * 0.85, 0.75, dc * 1.7, COL['comp'], '2-stage\ncentrifugal\ncompressor\nPR 3.8', fs=7)
    box(ax, 4.95, zc + 0.35, 0.5, 1.05, COL['comb'], 'can\ncombustor\nDLE', fs=7)
    dt = 2 * T['rm'] + T['h_ex']
    box(ax, 4.9, zc - dt * 0.65, 0.55, dt * 1.3, COL['turb'], '2-stage\naxial\nturbine\n(cast\nblisks)', fs=7)
    ax.add_patch(Polygon([[5.45, zc - 0.3], [6.1, zc - 0.5], [6.1, zc + 0.5], [5.45, zc + 0.3]], fc=COL['duct'], ec='k', lw=0.8))
    ax.text(5.77, zc, 'exhaust\ndiffuser', ha='center', va='center', fontsize=6.5, color='white')
    box(ax, 6.2, 0.0, 2.8, 2.1, COL['rec'], 'Recuperator\nε 0.90, %.1f MW\n~%.0f m², 3-5 t\n→ exhaust %.0f °C\nto CHP / absorption chiller' %
        (S['recuperator']['Q_kW'] / 1e3, S['recuperator']['area_m2'], R['chp']['T_exh_C']), fs=7.5)
    ax.plot([0.1, 6.1], [zc, zc], 'k-.', lw=0.7)
    ax.annotate('', xy=(5.45, zc + 0.9), xytext=(6.2, 1.75), arrowprops=dict(arrowstyle='->', color='#dd8452', lw=1.5))
    ax.text(5.5, 1.95, 'hot air 613 °C → combustor', fontsize=7, color='#dd8452')
    ax.set_xlim(-0.1, 9.4); ax.set_ylim(-0.3, 2.5); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('AURORA-1000 — single shaft 15,000 rpm, recuperated, geared 1 MWe set (side elevation, to scale, m)', fontsize=11)
    # ---- rotor half section (mm)
    bx = fig.add_axes([0.06, 0.04, 0.6, 0.36])
    r2 = C['D2'] / 2 * 1e3; rm = T['rm'] * 1e3; h1, hx = T['h1'] * 1e3, T['h_ex'] * 1e3
    bx.add_patch(Rectangle((0, 0), 820, 45, fc='#b0b0b0', ec='k', lw=0.6))                        # shaft / tie bolt
    for i, x0 in enumerate((40, 220)):                                                            # impellers
        bx.add_patch(Polygon([[x0, 45], [x0, 95], [x0 + 60, 130], [x0 + 110, r2 * 0.98], [x0 + 130, r2], [x0 + 130, 45]],
                             fc=COL['comp'], ec='k', lw=0.8))
        bx.text(x0 + 65, 70, 'impeller %d\nØ%.0f' % (i + 1, 2 * r2), ha='center', fontsize=7)
        bx.add_patch(Rectangle((x0 + 132, r2 * 0.92), 40, r2 * 0.14, fc='#dddddd', ec='k', lw=0.5))   # vaned diffuser
    xs = [560, 680]; hs = [h1, 0.5 * (h1 + hx)]
    for i, (x0, hh) in enumerate(zip(xs, hs)):
        bx.add_patch(Rectangle((x0 - 55, rm - hh / 2 - 1), 30, hh * 1.05, fc='#f0a0a0', ec='k', lw=0.5))   # NGV
        bx.add_patch(Rectangle((x0, 45), 40, rm - hh / 2 - 45, fc='#e8c0c0', ec='k', lw=0.6))            # disc
        bx.add_patch(Rectangle((x0, rm - hh / 2), 40, hh, fc=COL['turb'], ec='k', lw=0.8))                # blades
        bx.text(x0 + 20, rm + hh / 2 + 10, 'blisk %d\nh %.0f' % (i + 1, hh), ha='center', fontsize=7)
    bx.text(625, 20, 'curvic couplings + central tie bolt', ha='center', fontsize=7)
    bx.text(440, r2 + 30, 'casing → can combustor → NGV1', ha='center', fontsize=7)
    bx.set_xlim(-10, 860); bx.set_ylim(0, max(r2, rm + hx) + 70); bx.set_aspect('equal')
    bx.set_xlabel('axial [mm]'); bx.set_ylabel('radius [mm]')
    bx.set_title('Rotor half-section: 2 centrifugal impellers (Ti / Al) + 2 vacuum-cast MAR-M247 blisks (Dm %.0f mm)' % (2 * rm),
                 fontsize=9)
    # ---- key numbers
    tx = fig.add_axes([0.69, 0.04, 0.29, 0.36]); tx.axis('off')
    a = R['architectures']['R38']
    lines = ['Design point (intake 15 °C, 50 m)',
             'net electric output     1000 kW',
             'electric efficiency     %.1f-%.1f %%' % (S['eta_el'] * 100, S['eta_el_target'] * 100),
             'gas (city gas)          %.0f-%.0f m³/h, no booster' % (S['gas_m3h_target'], S['gas_m3h']),
             'air flow                %.1f kg/s' % S['ma_target'],
             'PR / TIT                3.8 / 950 °C',
             'exhaust after recup.    %.0f °C' % R['chp']['T_exh_C'],
             'CHP heat (→ 90 °C)      %.0f kW' % R['chp']['Q_kW'],
             'total efficiency (CHP)  ~%.0f %%' % (R['chp']['eta_tot'] * 100),
             'hot day 46 °C, no chill %.0f kW' % R['ambient']['borazjan_hot']['P_kW'],
             'blisk-1 root stress     %.0f MPa' % T['sigma_root_first']]
    tx.text(0, 1, '\n'.join(lines), va='top', family='monospace', fontsize=8.5)
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'mw1_layout.png')); print('written docs/img/mw1_layout.png')


if __name__ == '__main__':
    main()
