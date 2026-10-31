"""AURORA-1000 assembly feasibility check (docs/08 sec. 19): every part of fusion/A1000_pkg/pkg.json is moved along its
insertion path in the build order and checked step by step against the parts already installed (not only at the final
position).

Model:
  parts      the STEP files of pkg.json in the package frame (dx shift, blade / vane instances turned about the X axis)
  units      parts that are one physical piece (blisk = disc + blades, NGV casting = rings + vanes, impeller = hub + blades
             + splitters, compressor casing + its machined vanes) are not checked against each other
  halves     a part split on the horizontal plane in the machine is cut at z = 0 here; ('name', 'L') is the lower half
             (z <= 0), 'U' the upper half, None the whole part; ('name', 'S0:16') takes solids 0..15 of a compound (studs
             and nuts of one STEP)
  moves      SEQ: (label, [(part prefix, half)], path); path = offsets (dx, dy, dz[, dr]) from the final position, the
             last one is where the parts stay (0 = home; a part may be parked short of home and pushed home by a later
             move); dr moves each solid along its own radial direction (nuts entering a rotor cavity, radial pins)
  sweep      the parts move along the polyline; positions every STEP_MM and at 30 / 20 / 15 / 10 / 6 / 3 / 1.5 / 0.5 mm
             before the end of each segment; at each position the common volume with every installed solid is measured
             (bounding box and annulus [x, r] prefilters) and above VOL_TOL it is a clash; the end position is the static
             check of the part (designed contacts give ~0)
  frame      build stand: the lower casing halves stay put, the rotor is lowered (-z) into them, upper halves come down,
             axial modules slide along x; gravity -z
Run (conda env fc, MacBook or the cloud node; NPROC processes: one per move, heaviest first; FCCMD = freecadcmd path):
  freecadcmd -c "import sys; sys.argv=['x','--sweep','v12']; exec(open('cad/engine/a1000_assembly_check.py').read())"
  freecadcmd -c "import sys; sys.argv=['x','--sweep','new']; exec(open('cad/engine/a1000_assembly_check.py').read())"
  -> sim/engine/fea/a1000_assembly_check_<seq>.json
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PKG_DIR = os.path.join(ROOT, 'fusion', 'A1000_pkg')
VOL_TOL = 5.0                       # mm3: below this a common volume is numerical noise of the STEP surfaces / tangent faces
STEP_MM = 40.0
NEAR = (30.0, 20.0, 15.0, 10.0, 6.0, 3.0, 1.5, 0.5)
NPROC = int(os.environ.get('NPROC', '3'))

UNITS = [('NGV1 rings', 'NGV1 vane'), ('NGV2 rings', 'NGV2 vane'), ('A1000_R1 disc', 'Blisk 1 blade'),
         ('A1000_R2 disc', 'Blisk 2 blade'), ('Impeller 1 hub', 'Impeller 1 blade', 'Impeller 1 splitter'),
         ('Impeller 2 hub', 'Impeller 2 blade', 'Impeller 2 splitter'),
         ('Compressor casing', 'Diffuser 1 vane', 'Diffuser 2 vane', 'Return-channel vane'),
         ('HS-211 Honeycomb', 'HS-211 Shroud backing'), ('HS-221 Honeycomb', 'HS-221 Shroud backing'),
         ('HS-230', 'HS-231'), ('HS-232', 'HS-233')]

# ------------------------------------------------------------------------------------------------ build orders
XA, XF, ZD, ZU = (650, 0, 0), (-650, 0, 0), (0, 0, -900), (0, 0, 900)
ROTOR = ['RT-', 'A1000_R1 disc', 'A1000_R2 disc', 'Blisk 1 blade', 'Blisk 2 blade', 'Impeller']

# the add-in order of package v12 (fusion/AURORA1000_Animate, 40 moves) as it is, each move along its fly-in offset
SEQ_V12 = [
    ('1 front stub + collar', [('RT-101', None)], [XF, (0, 0, 0)]),
    ('1 impeller 1', [('Impeller 1', None)], [XA, (0, 0, 0)]),
    ('1 spacer RT-104', [('RT-104', None)], [XA, (0, 0, 0)]),
    ('1 impeller 2', [('Impeller 2', None)], [XA, (0, 0, 0)]),
    ('1 drum RT-105', [('RT-105', None)], [XA, (0, 0, 0)]),
    ('1 tie bolt', [('RT-102', None)], [(-1100, 0, 0), (0, 0, 0)]),
    ('1 tie-bolt nut', [('RT-103', None)], [(-450, 0, 0), (0, 0, 0)]),
    ('2 R1 blisk', [('A1000_R1 disc', None), ('Blisk 1 blade', None)], [XA, (0, 0, 0)]),
    ('2 studs + nuts drum - R1', [('RT-111', None)], [(300, 0, 0), (0, 0, 0)]),
    ('2 spacer ring RT-107', [('RT-107', None)], [XA, (0, 0, 0)]),
    ('2 R2 blisk', [('A1000_R2 disc', None), ('Blisk 2 blade', None)], [XA, (0, 0, 0)]),
    ('2 studs + nuts R1 - R2', [('RT-112', None)], [(300, 0, 0), (0, 0, 0)]),
    ('2 rear stub', [('RT-106', None)], [XA, (0, 0, 0)]),
    ('2 studs + nuts R2 - stub', [('RT-113', None)], [(300, 0, 0), (0, 0, 0)]),
    ('3 thrust bearing (axial from the front)', [('TB ', None)], [(-600, 0, 0), (0, 0, 0)]),
    ('3 journal bearing 1 (axial from the front)', [('JB1', None)], [(-700, 0, 0), (0, 0, 0)]),
    ('3 journal bearing 2 (axial from the rear)', [('JB2', None)], [(700, 0, 0), (0, 0, 0)]),
    ('4 HS-202 lower casing (from below)', [('HS-202', None)], [ZD, (0, 0, 0)]),
    ('4 compressor casing (whole, from below)', [('Compressor casing', None), ('Diffuser', None), ('Return-channel', None)], [ZD, (0, 0, 0)]),
    ('4 front diaphragm (whole, from below)', [('HS-230', None), ('HS-231', None)], [ZD, (0, 0, 0)]),
    ('4 NGV1 + C1 + R1 shroud (whole, from below)', [('NGV1', None), ('HS-210', None), ('HS-211', None)], [ZD, (0, 0, 0)]),
    ('4 gap liner + gap ring (whole, from below)', [('HS-222', None), ('HS-234', None)], [ZD, (0, 0, 0)]),
    ('4 NGV2 + C2 + R2 shroud (whole, from below)', [('NGV2', None), ('HS-220', None), ('HS-221', None)], [ZD, (0, 0, 0)]),
    ('4 interstage diaphragm (whole, from below)', [('HS-232', None), ('HS-233', None)], [ZD, (0, 0, 0)]),
    ('4 radial pins x8 (from above)', [('HS-240', None)], [(0, 0, 600), (0, 0, 0)]),
    ('4 HS-201 upper casing (from above)', [('HS-201', None)], [ZU, (0, 0, 0)]),
    ('5 scroll lower halves CB-341 + CB-331 (from below)', [('CB-341', None), ('CB-331', None)], [ZD, (0, 0, 0)]),
    ('5 deswirl vanes, leaf seals, scroll pins', [('CB-332', None), ('CB-350', None), ('CB-360', None)], [(0, 0, 600), (0, 0, 0)]),
    ('5 scroll upper halves + insulation', [('CB-330', None), ('CB-333', None), ('CB-340', None)], [ZU, (0, 0, 0)]),
    ('5 can casing + base plate', [('CB-301', None), ('CB-302', None)], [(0, 0, 1300), (0, 0, 0)]),
    ('5 impingement sleeve + liner', [('CB-321', None), ('CB-320', None)], [(0, 0, 1300), (0, 0, 0)]),
    ('5 head cover + premixers', [('CB-303', None), ('CB-310', None)], [(0, 0, 1000), (0, 0, 0)]),
    ('5 fuel manifolds, igniter, UV', [('CB-370', None), ('CB-371', None)], [(0, 0, 800), (0, 0, 0)]),
    ('5 air inlet plenum', [('Air inlet', None)], [(0, 0, 1100), (0, 0, 0)]),
    ('5 exhaust diffuser + collector', [('Exhaust', None)], [(1000, 0, 0), (0, 0, 0)]),
    ('5 recuperator + ducts', [('Recuperator', None)], [(0, 1400, 0), (0, 0, 0)]),
    ('5 HS coupling, gearbox, starter', [('High-speed coupling', None), ('Epicyclic', None), ('Starter', None)], [(-900, 0, 0), (0, 0, 0)]),
    ('5 LS coupling + generator', [('Low-speed coupling', None), ('Synchronous generator', None)], [(-1300, 0, 0), (0, 0, 0)]),
    ('5 lube oil module', [('Lube oil', None)], [(0, -1000, 0), (0, 0, 0)]),
    ('5 base frame', [('Base frame', None)], [(0, 0, -1100), (0, 0, 0)]),
]

SEQS = dict(v12=SEQ_V12)
try:                                                                # the corrected build order (sec. 19), see the module
    sys.path.insert(0, HERE)
    import a1000_assembly_seq as _AS                                # noqa: E402
    SEQS['new'] = _AS.SEQ
except ImportError:
    pass


# ------------------------------------------------------------------------------------------------ geometry
def log(s):
    print(s, flush=True)


def load_pkg():
    import FreeCAD as App, Part
    V = App.Vector
    pkg = json.load(open(os.path.join(PKG_DIR, 'pkg.json')))
    out, cache = {}, {}
    for p in pkg['parts']:
        fn = os.path.normpath(os.path.join(PKG_DIR, p['step']))
        if fn not in cache:
            s = Part.Shape(); s.read(fn); cache[fn] = s
        base = cache[fn].copy(); base.translate(V(p.get('dx', 0.0), 0, 0))
        sols = []
        for a in p['inst']:
            c = base.copy()
            if a: c.rotate(V(0, 0, 0), V(1, 0, 0), a)
            sols += c.Solids
        out[p['name']] = sols
    return out


def unit_of(name):
    for i, u in enumerate(UNITS):
        if name.startswith(u): return i
    return None


def half(sols, which):
    """solids cut at z = 0: 'L' keeps z <= 0, 'U' z >= 0; 'Sa:b' solids a..b-1"""
    import FreeCAD as App, Part
    V = App.Vector
    if which is None: return list(sols)
    if which.startswith('S'):
        a, b = which[1:].split(':'); return list(sols[int(a):int(b)])
    box = Part.makeBox(8000, 8000, 4000, V(-4000, -4000, 0.0 if which == 'U' else -4000.0))
    out = []
    for s in sols:
        bb = s.BoundBox
        if (which == 'U' and bb.ZMin >= -1e-6) or (which == 'L' and bb.ZMax <= 1e-6): out.append(s); continue
        if (which == 'U' and bb.ZMax <= 1e-6) or (which == 'L' and bb.ZMin >= -1e-6): continue
        out += [c for c in s.common(box).Solids if c.Volume > 1e-3]
    return out


class Piece:
    """one solid with its annulus bounds about the X axis (x0, x1, rmin, rmax) at the home position"""
    def __init__(self, name, solid):
        import FreeCAD as App, Part
        self.name, self.s = name, solid
        bb = solid.BoundBox
        self.bb = (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)
        self.rmax = math.sqrt(max(bb.YMin ** 2, bb.YMax ** 2) + max(bb.ZMin ** 2, bb.ZMax ** 2))
        if bb.YMin <= 0 <= bb.YMax and bb.ZMin <= 0 <= bb.ZMax:
            ax = Part.LineSegment(App.Vector(bb.XMin - 1, 0, 0), App.Vector(bb.XMax + 1, 0, 0)).toShape()
            try:
                self.rmin = max(0.0, solid.distToShape(ax)[0] - 0.01)
            except Exception:
                self.rmin = 0.0
        else:                                                          # distance from the axis to the box
            dy = 0.0 if bb.YMin <= 0 <= bb.YMax else min(abs(bb.YMin), abs(bb.YMax))
            dz = 0.0 if bb.ZMin <= 0 <= bb.ZMax else min(abs(bb.ZMin), abs(bb.ZMax))
            self.rmin = math.hypot(dy, dz)
        c = solid.BoundBox.Center
        rr = math.hypot(c.y, c.z)
        self.radial = (0.0, c.y / rr, c.z / rr) if rr > 1e-6 else (0.0, 0.0, 1.0)
        self.unit = unit_of(name)


def offset_of(p, o):
    """absolute translation of piece p for a path point o = (dx, dy, dz[, dr])"""
    dr = o[3] if len(o) > 3 else 0.0
    return (o[0] + dr * p.radial[0], o[1] + dr * p.radial[1], o[2] + dr * p.radial[2])


def bounds_at(p, d):
    x0, x1, y0, y1, z0, z1 = p.bb
    e = math.hypot(d[1], d[2])
    return (x0 + d[0], x1 + d[0], y0 + d[1], y1 + d[1], z0 + d[2], z1 + d[2], max(0.0, p.rmin - e), p.rmax + e)


def may_touch(a, b, g=0.05):
    return not (a[1] < b[0] - g or b[1] < a[0] - g or a[3] < b[2] - g or b[3] < a[2] - g or a[5] < b[4] - g or b[5] < a[4] - g or
                a[7] < b[6] - g or b[7] < a[6] - g)


def common_at(pa, da, pb, db):
    import FreeCAD as App
    a = pa.s.copy(); a.translate(App.Vector(*da))
    b = pb.s
    if any(abs(v) > 1e-9 for v in db):
        b = pb.s.copy(); b.translate(App.Vector(*db))
    try:
        return a.common(b).Volume
    except Exception:
        return -1.0


def positions(path):
    """sample points along the polyline (start -> end): every STEP_MM and NEAR before the end of each segment"""
    pts = []
    for k in range(len(path) - 1):
        a, b = list(path[k]) + [0.0] * (4 - len(path[k])), list(path[k + 1]) + [0.0] * (4 - len(path[k + 1]))
        L = math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(4)))
        if L < 1e-9: continue
        # a straight vertical drop of a half can only meet radially interleaved features near its end: coarser far field
        step = 3 * STEP_MM if abs(b[2] - a[2]) > 0.99 * L else STEP_MM
        ds = sorted({L} | {L - s for s in NEAR if s < L} | {i * step for i in range(int(L / step) + 1)})
        for s in ds:
            pts.append(tuple(a[i] + (b[i] - a[i]) * s / L for i in range(4)))
    return pts


def run_move(P, seq, k):
    """sweep move k of seq: installed = moves 0..k-1 at their last offsets; returns the move's result dict"""
    state = {}                                                         # (part name, half) -> pieces; + ('off',) -> offset
    label, parts, path = seq[k]
    moving = []

    def keys_for(n, hf):
        """a whole-part entry moves every half / subset of that part already installed"""
        if hf is None:
            ks = [key for key in state if len(key) == 2 and key[0] == n]
            if ks: return ks
        return [(n, hf)]
    for j in range(k + 1):
        lab, prts, pth = seq[j]
        for pref, hf in prts:
            names = [n for n in P if n.startswith(pref)]
            for n in names:
                for key in keys_for(n, hf):
                    if j < k:
                        if key not in state: state[key] = [Piece(n, s) for s in half(P[n], key[1])]
                        state[key + ('off',)] = pth[-1]
                    elif key not in moving:
                        moving.append(key)
    # a part moved again (pushed home) is not installed while it moves
    moving_keys = set(moving)
    inst = [(pc, state[key + ('off',)]) for key in state if len(key) == 2 and key not in moving_keys for pc in state[key]]
    mov = []
    for key in moving:
        pcs = state[key] if key in state else [Piece(key[0], s) for s in half(P[key[0]], key[1])]
        mov += pcs
    t0 = time.time()
    res = dict(label=label, parts=sorted({n for n, _ in moving}), path=[list(p) for p in path], clashes=[], final_overlaps=[])
    if not mov:
        res['note'] = 'no parts matched'; return res
    pts = positions(path)
    worst = {}
    done = set()                                                       # pairs already found clashing: first hit is reported
    for q in pts:
        at_end = q == tuple(list(path[-1]) + [0.0] * (4 - len(path[-1])))
        for pa in mov:
            da = offset_of(pa, q); ba = bounds_at(pa, da)
            for pb, ob in inst:
                if pa.unit is not None and pa.unit == pb.unit: continue
                if not at_end and (id(pa), id(pb)) in done: continue
                db = offset_of(pb, ob)
                if not may_touch(ba, bounds_at(pb, db)): continue
                v = common_at(pa, da, pb, db)
                if v > VOL_TOL:
                    key = (pa.name, pb.name)
                    dist = math.sqrt(sum((q[i] - path[-1][i] if i < len(path[-1]) else q[i]) ** 2 for i in range(4)))
                    if at_end:
                        res['final_overlaps'].append(dict(a=pa.name, b=pb.name, vol_mm3=round(v, 1)))
                    else:
                        done.add((id(pa), id(pb)))
                        if key not in worst or v > worst[key]['vol_mm3']:
                            worst[key] = dict(a=pa.name, b=pb.name, vol_mm3=round(v, 1), at=[round(x, 1) for x in q], before_end_mm=round(dist, 1))
    res['clashes'] = sorted(worst.values(), key=lambda c: -c['vol_mm3'])
    # one entry per part pair in the final overlaps (several solids of a pair)
    fo = {}
    for c in res['final_overlaps']:
        kk = (c['a'], c['b']); fo[kk] = fo.get(kk, 0.0) + c['vol_mm3']
    res['final_overlaps'] = [dict(a=a, b=b, vol_mm3=round(v, 1)) for (a, b), v in fo.items()]
    res['n_positions'] = len(pts); res['n_moving'] = len(mov); res['n_installed'] = len(inst); res['s'] = round(time.time() - t0, 1)
    return res


def worker(seq_name, ks, out_path):
    P = load_pkg()
    seq = SEQS[seq_name]
    out = []
    for k in ks:
        r = run_move(P, seq, k); r['k'] = k; out.append(r)
        log('%2d %-55s %3d pos  clashes %d  final %d  %.0f s' % (k, r['label'][:55], r.get('n_positions', 0), len(r['clashes']),
                                                                  len(r['final_overlaps']), r.get('s', 0)))
        for c in r['clashes'][:6]:
            log('     CLASH %-45s x %-45s %9.1f mm3 at %s (%.1f mm before the end)' % (c['a'][:45], c['b'][:45], c['vol_mm3'], c['at'], c['before_end_mm']))
        for c in r['final_overlaps'][:6]:
            log('     FINAL %-45s x %-45s %9.1f mm3' % (c['a'][:45], c['b'][:45], c['vol_mm3']))
        json.dump(out, open(out_path, 'w'), indent=1)


def static_all(out_path, only=(), part=(0, 1)):
    """every pair of parts at home (one-piece units skipped): designed fits give ~0, anything above VOL_TOL is listed;
    only: name prefixes - then just the pairs with at least one such part (a re-check after a change);
    part (w, n): this process takes the rows i with i % n == w (the driver merges the parts)"""
    P = load_pkg()
    pcs = [Piece(n, s) for n in P for s in P[n]]
    hits = {}
    t0 = time.time()
    for i, a in enumerate(pcs):
        if i % part[1] != part[0]: continue
        ba = bounds_at(a, (0, 0, 0))
        for b in pcs[i + 1:]:
            if a.name == b.name or (a.unit is not None and a.unit == b.unit): continue
            if only and not (a.name.startswith(only) or b.name.startswith(only)): continue
            if not may_touch(ba, bounds_at(b, (0, 0, 0))): continue
            v = common_at(a, (0, 0, 0), b, (0, 0, 0))
            if v > VOL_TOL:
                k = tuple(sorted((a.name, b.name))); hits[k] = hits.get(k, 0.0) + v
    res = [dict(a=a, b=b, vol_mm3=round(v, 1)) for (a, b), v in sorted(hits.items(), key=lambda kv: -kv[1])]
    json.dump(dict(parts=len(P), solids=len(pcs), vol_tol_mm3=VOL_TOL, overlaps=res, s=round(time.time() - t0)), open(out_path, 'w'), indent=1)
    log('static part %d/%d: %d pairs, %.0f s' % (part[0], part[1], len(res), time.time() - t0))


FCCMD = os.environ.get('FCCMD', os.path.expanduser('~/micromamba/envs/fc/bin/freecadcmd'))


def run_pool(jobs, nproc):
    """run [(tag, argv list)] as freecadcmd subprocesses, nproc at a time, in the given order (heaviest first)"""
    import subprocess
    todo, running = list(jobs), []
    while todo or running:
        while todo and len(running) < nproc:
            tag, argv = todo.pop(0)
            code = "import sys; sys.argv=%r; exec(open('cad/engine/a1000_assembly_check.py').read())" % (['x'] + argv)
            running.append(subprocess.Popen(['nice', '-n', os.environ.get('NICE', '15'), FCCMD, '-c', code], cwd=ROOT,
                                            stdout=open(os.path.join(ROOT, '_asm_%s.log' % tag), 'w'), stderr=subprocess.STDOUT))
        time.sleep(2)
        running = [p for p in running if p.poll() is None]


# heaviest moves first (rotor or big casings against many installed solids), so the pool ends together
HEAVY = ('C1 ', 'D3 ', 'D4 ', 'B8 ', 'F5 ', 'B5 ', 'D1 ', 'B7 ', 'A13', 'A9 ', 'A14', 'A10')

if '--static' in sys.argv:
    _only = tuple(a[len('--only='):] for a in sys.argv if a.startswith('--only='))
    out = os.path.join(ROOT, 'sim', 'engine', 'fea', 'a1000_assembly_static%s.json' % ('_recheck' if _only else ''))
    if '--part' in sys.argv:
        w, n = (int(v) for v in sys.argv[sys.argv.index('--part') + 1].split('/'))
        static_all(out + '.%d' % w, _only, (w, n))
    else:
        t0 = time.time()
        run_pool([('static_%d' % w, ['--static', '--part', '%d/%d' % (w, NPROC)] + ['--only=' + o for o in _only]) for w in range(NPROC)], NPROC)
        hits = {}
        for w in range(NPROC):
            for o in json.load(open(out + '.%d' % w))['overlaps']:
                k = (o['a'], o['b']); hits[k] = hits.get(k, 0.0) + o['vol_mm3']
            os.remove(out + '.%d' % w)
        res = [dict(a=a, b=b, vol_mm3=round(v, 1)) for (a, b), v in sorted(hits.items(), key=lambda kv: -kv[1])]
        for r in res:
            log('  STATIC %-55s %-55s %10.1f mm3' % (r['a'][:55], r['b'][:55], r['vol_mm3']))
        json.dump(dict(vol_tol_mm3=VOL_TOL, overlaps=res, s=round(time.time() - t0), only=list(_only)), open(out, 'w'), indent=1)
        log('static: %d overlapping pairs, %.0f s' % (len(res), time.time() - t0))

if '--sweep' in sys.argv:
    seq_name = sys.argv[sys.argv.index('--sweep') + 1]
    only = [int(a) for i, a in enumerate(sys.argv) if a.isdigit() and sys.argv[i - 1] not in ('--worker', '--move')]
    seq = SEQS[seq_name]
    if '--move' in sys.argv:
        k = int(sys.argv[sys.argv.index('--move') + 1])
        worker(seq_name, [k], os.path.join(ROOT, 'sim', 'engine', 'fea', '_asm_%s_m%02d.json' % (seq_name, k)))
    else:
        ks = [k for k in range(len(seq)) if not only or k in only]
        ks.sort(key=lambda k: (0 if seq[k][0].startswith(HEAVY) else 1, k))
        run_pool([('%s_m%02d' % (seq_name, k), ['--sweep', seq_name, '--move', str(k)]) for k in ks], NPROC)
        allr = []
        for k in ks:
            fn = os.path.join(ROOT, 'sim', 'engine', 'fea', '_asm_%s_m%02d.json' % (seq_name, k))
            if os.path.exists(fn): allr += json.load(open(fn)); os.remove(fn)
        allr.sort(key=lambda r: r['k'])
        n_cl = sum(1 for r in allr if r['clashes']); n_fo = sum(1 for r in allr if r['final_overlaps'])
        json.dump(dict(sequence=seq_name, moves=len(allr), moves_with_clash=n_cl, moves_with_final_overlap=n_fo, vol_tol_mm3=VOL_TOL,
                       results=allr), open(os.path.join(ROOT, 'sim', 'engine', 'fea', 'a1000_assembly_check_%s.json' % seq_name), 'w'), indent=1)
        log('%s: %d moves, %d with clashes on the way, %d with overlaps at the end' % (seq_name, len(allr), n_cl, n_fo))
