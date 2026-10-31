"""AURORA-1000 compressor: meridional section (plane z = 0, upper half) of the package parts around the two impellers.

Reads fusion/A1000_pkg/pkg.json + the STEP parts it references (A1000_STEP=1 run of cad/engine/a1000_viewer_export.py):
impellers (hub, blades, splitters), compressor casing (shroud walls, vaned diffusers, crossover, diaphragm, return channel,
collector), diffuser / return-channel vanes, shaft pieces and bearings.
Run:    freecadcmd -c "exec(open('cad/engine/a1000_compressor_section.py').read())"     (GR180_ROOT = repo root)
Writes: docs/img/a1000_compressor_section.png
"""
import json
import os

import FreeCAD as App
import Part
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                    # noqa: E402

ROOT = os.environ.get('GR180_ROOT') or os.getcwd()
PKG = os.path.join(ROOT, 'fusion', 'A1000_pkg')
V = App.Vector
COL = {'comp': ('tab:blue', 'impellers (hub, ruled blades, splitters)'), 'casing': ('0.35', 'casing, diaphragm, collector'),
       'diff': ('tab:orange', 'diffuser / return-channel vanes (cut)'), 'rotor': ('tab:green', 'shaft, spacer, drum'),
       'bearing': ('goldenrod', 'bearings')}
pkg = json.load(open(os.path.join(PKG, 'pkg.json')))
fig, ax = plt.subplots(figsize=(15, 9), dpi=110)
seen = set()
for p in pkg['parts']:
    if p['group'] not in COL: continue
    s = Part.Shape(); s.read(os.path.normpath(os.path.join(PKG, p['step']))); s.translate(V(p['dx'], 0, 0))
    for ang in p['inst']:
        q = s.copy(); q.rotate(V(0, 0, 0), V(1, 0, 0), ang)
        for w in q.slice(V(0, 0, 1), 0.0):
            pts = w.discretize(Distance=0.8)
            if max(v.y for v in pts) < 0: continue
            c, lab = COL[p['group']]
            ax.plot([v.x for v in pts], [v.y for v in pts], '-', lw=0.7, color=c, label=None if lab in seen else lab)
            seen.add(lab)
ax.set_xlim(60, 600); ax.set_ylim(0, 490); ax.set_aspect('equal'); ax.grid(alpha=0.3)
ax.set_xlabel('x, engine axis from the gearbox coupling face [mm]'); ax.set_ylabel('radius [mm]')
ST = json.load(open(os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')))['stages']
lab = lambda k: '%s\n%s, D%.0f' % (ST[k]['name'].lower(), ST[k]['material'], 2 * ST[k]['geometry']['r2'])
for x, r, t in ((250, 30, lab('C1')), (450, 30, lab('C2')), (300, 300, 'vaned\ndiffuser 1'),
                (361, 250, 'return\nchannel'), (330, 400, 'crossover'), (505, 330, 'vaned\ndiffuser 2'), (505, 430, 'collector')):
    ax.text(x, r, t, fontsize=8, ha='center', bbox=dict(fc='white', ec='none', alpha=0.7))
ax.legend(fontsize=8, loc='upper left')
ax.set_title('AURORA-1000 two-stage centrifugal compressor: meridional section through the package parts (plane z = 0)', fontsize=10)
fig.tight_layout(); png = os.path.join(ROOT, 'docs', 'img', 'a1000_compressor_section.png'); fig.savefig(png); print('written', png)
