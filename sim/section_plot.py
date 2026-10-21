# Half-section plot of the assembly (z = 0 plane) from per-part STEP files - visual check of the stack-up.
# Run:  GR180_ROOT=<folder with asm_parts/> freecadcmd sim/section_plot.py    -> <root>/section_xy.json (+ .png if matplotlib)
import FreeCAD as App, Part, os, json, sys
V = App.Vector
ROOT = os.environ.get('GR180_ROOT', os.getcwd()); ASM = os.path.join(ROOT, 'asm_parts')
XMIN, XMAX = float(os.environ.get('XMIN', '-65')), float(os.environ.get('XMAX', '135'))
out = {}
for f in sorted(os.listdir(ASM)):
    if not f.endswith('.step'): continue
    s = Part.Shape(); s.read(os.path.join(ASM, f))
    try:
        cut = s.slice(V(0, 0, 1), 0.0)            # wires of the section with the plane z = 0
    except Exception:
        continue
    polys = []
    for w in cut:
        pts = [(p.x, p.y) for p in w.discretize(Deflection=0.02)]
        if pts: polys.append(pts)
    out[f[:-5]] = polys
    print('section', f[:-5], len(polys)); sys.stdout.flush()
json.dump(out, open(os.path.join(ROOT, 'section_xy.json'), 'w'))
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(22, 9))
    cmap = plt.get_cmap('tab20')
    for i, (n, polys) in enumerate(sorted(out.items())):
        for k, pts in enumerate(polys):
            xs, ys = zip(*pts)
            ax.fill(xs, ys, color=cmap(i % 20), alpha=0.45, lw=0.4, ec='k', label=n if k == 0 else None)
    ax.set_aspect('equal'); ax.set_xlim(XMIN, XMAX); ax.set_ylim(-5, 58); ax.grid(alpha=0.25)
    ax.set_title('GR180 v13A half-section (z = 0, upper half), mm'); ax.legend(fontsize=6, ncol=6, loc='upper left')
    fn = os.path.join(ROOT, 'section_v13A.png'); fig.savefig(fn, dpi=110, bbox_inches='tight'); print('png', fn)
except ImportError:
    print('no matplotlib in FreeCAD python - plot section_xy.json separately')
