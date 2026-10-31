"""AURORA-1000 air inlet (phase 3, docs/08 sec. 20): CAD of the parts from the design in sim/engine/a1000_inlet.py (GEO).

Parts (rotor frame mm, x = engine axis, z up; all split at the centre line z = 0 where they surround the shaft):
  IN-501  inlet casing, upper half   EN-GJS-400-18   hub wall (x 143-157, bore r 130.5 over the FB OD, seal face on the FB
  IN-502  inlet casing, lower half                   fairing), front lip R40 + tunnel flange ring, 2 of the 4 struts,
                                                     shroud wall (x 204-222) with the bellmouth corner, spigot recess r 150
                                                     on the compressor casing, flush rim for the plenum rear plate; the
                                                     lower half carries the two FB-2 foot brackets (L section, M16)
  IN-510  plenum box, upper half     S235JR 6 mm     welded box x -146..210, y +-546, z 0..612, filter-house flange on top,
                                                     dry-tunnel half r 284-290, split flanges, 2 lifting lugs
  IN-511  plenum box, lower half     S235JR 6 mm     same below z 0, 4 feet to the skid, drain boss at the low point
  IN-520  filter-house adapter       S235JR + fabric 300 mm frame on the top flange with the fabric expansion joint
Run on the MacBook:  nice ~/micromamba/envs/fc/bin/freecadcmd -c "import sys; sys.argv=['x','--cad']; exec(open('cad/engine/a1000_inlet.py').read())"
  --cad    -> cad_out/engine/A1000_inl/*.step, fusion/A1000_inl/*.step + parts.json
  --check  interference with the rotor + front bearing (fusion/A1000_rotor), impellers (fusion/A1000C), the exhaust cold
           pipe (fusion/A1000_exh/EX_440), the engine piping of sec. 19 (fusion/A1000_pipe) and the package placeholders
           (coupling, compressor casing, gearbox, lube module, skid)
Locally (no FreeCAD):  python3 cad/engine/a1000_inlet.py --pkg   -> fusion/A1000_pkg/pkg.json entries
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'sim', 'engine'))
import a1000_inlet as E                                           # noqa: E402

G = E.DESIGNS[E.DESIGN]; ST = G['struts']; BX = G['box']
OUT_F = os.path.join(ROOT, 'fusion', 'A1000_inl')
RHO = {'EN-GJS-400-18': 7100, 'S235JR': 7850, 'S235JR + fabric': 7850}
T_P = 6.0                                                         # plenum plate [mm]
CAS = dict(x_front=143.0, r_bore=130.5, x_land=97.0, r_land_in=276.0, x_ring=109.0, r_ring_in=250.0, r_ring_box=253.0,  # box ring: 3 mm
           # over the PL-05 DN40 drain branches (bottom r ~250 at x 83-88)
           x_rear=222.0, r_rim=460.0, r_rim_o=480.0, x_rim=210.0, r_spig=150.0, x_spig=214.0,
           r_bolt_cc=440.0, n_bolt_cc=24, r_bolt_box=470.0, n_bolt_box=24)
BRK = dict(x=(55.0, 143.0), y=(160.0, 215.0), z_pad=(-36.0, -20.0), web_y=(199.0, 215.0), z_web=-110.0, holes_x=(70.0, 120.0), y_hole=185.0,
           key_x=(87.0, 103.0), key_d=6.0)                     # transverse key slot under each FB-2 foot (axial location, sec. 19)


def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def V(x, y, z):
    return _fc()[0].Vector(x, y, z)


def revolve(poly):
    App, Part, Vv = _fc()
    pts = [Vv(x, 0, r) for x, r in poly]
    if (pts[0] - pts[-1]).Length > 1e-6: pts.append(pts[0])
    s = Part.Face(Part.makePolygon(pts)).revolve(Vv(0, 0, 0), Vv(1, 0, 0), 360)
    return s if s.Volume > 0 else s.reversed()


def tube(x0, x1, ro, ri=0.0):
    App, Part, Vv = _fc()
    s = Part.makeCylinder(ro, x1 - x0, Vv(x0, 0, 0), Vv(1, 0, 0))
    return s.cut(Part.makeCylinder(ri, x1 - x0, Vv(x0, 0, 0), Vv(1, 0, 0))) if ri > 0 else s


def box(x0, x1, y0, y1, z0, z1):
    App, Part, Vv = _fc()
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vv(x0, y0, z0))


def arc(c, R, a0, a1, n=16):
    """(x, r) points on an arc about c, angle a from +r towards +x [deg]"""
    return [(c[0] + R * math.sin(math.radians(a0 + (a1 - a0) * k / n)), c[1] + R * math.cos(math.radians(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def fuse(shapes):
    s = shapes[0]
    for q in shapes[1:]: s = s.fuse(q)
    return s.removeSplitter()


def halves(s):
    """lower (z < 0) and upper (z > 0) parts of a shape split at the centre line"""
    big = 5000.0
    return s.common(box(-big, big, -big, big, -big, 0.0)), s.common(box(-big, big, -big, big, 0.0, big))


def axial_holes(x0, x1, r, d, n, phase):
    App, Part, Vv = _fc()
    return [Part.makeCylinder(d / 2, x1 - x0, Vv(x0, r * math.cos(math.radians(phase + 360.0 * k / n)),
                                                r * math.sin(math.radians(phase + 360.0 * k / n))), Vv(1, 0, 0)) for k in range(n)]


# ================================================================================================ inlet casing (IN-501/502)
def struts():
    """4 solid struts: the a1000_inlet section (radial chord r_le -> r_te, tangential thickness) extruded across the slot
    and 7 / 6 mm into the hub wall / shroud wall"""
    App, Part, Vv = _fc()
    up, lo = E.strut_section(G)
    sec = up + lo[::-1][1:-1]
    out = []
    for k in range(ST['n']):
        ph = math.radians(ST['theta0'] + 360.0 * k / ST['n'])
        er = Vv(0, math.cos(ph), math.sin(ph)); et = Vv(0, -math.sin(ph), math.cos(ph))
        x0 = G['x_hub'] - 7.0
        P = [Vv(x0, 0, 0) + er * r + et * q for r, q in sec]
        c = Part.BSplineCurve(); c.interpolate(P, PeriodicFlag=True)
        out.append(Part.Face(Part.Wire(c.toShape())).extrude(Vv(G['x_shr'] - G['x_hub'] + 13.0, 0, 0)))
    return out


def casing_full():
    """one-piece inlet casing before the split: front body (hub wall + lip + tunnel ring), shroud wall + bellmouth, struts"""
    App, Part, Vv = _fc()
    L, R = G['R_lip'], G['R_T']; xc, rc = G['x_hub'] - L, R - L
    t_lip = L - (R - CAS['r_land_in'])                               # inner (dry-side) arc radius: 14 mm wall
    front = [(G['x_hub'], CAS['r_bore']), (G['x_hub'], rc)] + arc((xc, rc), L, 90.0, 0.0)[1:] + \
            [(CAS['x_land'], R), (CAS['x_land'], CAS['r_ring_in']), (CAS['x_ring'], CAS['r_ring_in']), (CAS['x_ring'], CAS['r_land_in']),
             (xc, CAS['r_land_in'])] + arc((xc, rc), t_lip, 0.0, 90.0)[1:] + [(CAS['x_front'], rc), (CAS['x_front'], CAS['r_bore'])]
    cp = E.corner_pts(G)                                             # (x_shr, r0) ... (x_end, r_eye_shr)
    rear = [cp[0], (G['x_shr'], CAS['r_rim']), (CAS['x_rim'], CAS['r_rim']), (CAS['x_rim'], CAS['r_rim_o']),
            (CAS['x_rear'], CAS['r_rim_o']), (CAS['x_rear'], CAS['r_spig']), (CAS['x_spig'], CAS['r_spig'])] + cp[::-1][:-1]
    parts = [revolve(front), revolve(rear)] + struts()
    if G.get('ring'): parts.append(revolve(E.ring_section(G)))       # turning ring, carried by the 4 struts
    s = fuse(parts)
    # 24 x M12 blind from the back into the compressor casing flange face; 24 x M10 in the rim step for the plenum rear plate;
    # 16 x M10 in the tunnel ring
    cut = axial_holes(CAS['x_rear'] - 14.0, CAS['x_rear'] + 1.0, CAS['r_bolt_cc'], 10.2, CAS['n_bolt_cc'], 7.5)
    cut += axial_holes(CAS['x_rim'] - 0.5, CAS['x_rim'] + 10.0, CAS['r_bolt_box'], 8.5, CAS['n_bolt_box'], 7.5)
    cut += axial_holes(CAS['x_land'] - 1.0, CAS['x_ring'] + 1.0, 263.0, 8.5, 16, 11.25)
    for c in cut: s = s.cut(c)
    return s


def split_lugs_casing():
    """bolted split lugs: hub-wall front face (dry side) at y +-205..245 and the tunnel ring at y +-232..250"""
    out = []
    for sy in (1, -1):
        out.append(box(125.0, CAS['x_front'] + 1.0, min(sy * 205.0, sy * 245.0), max(sy * 205.0, sy * 245.0), -18.0, 18.0))
        out.append(box(CAS['x_land'], CAS['x_ring'], min(sy * 232.0, sy * 251.0), max(sy * 232.0, sy * 251.0), -14.0, 14.0))
    return out


def lug_holes():
    App, Part, Vv = _fc()
    out = []
    for sy in (1, -1):
        out.append(Part.makeCylinder(6.5, 60.0, Vv(134.0, sy * 225.0, -30.0), Vv(0, 0, 1)))
        out.append(Part.makeCylinder(5.5, 60.0, Vv(103.0, sy * 241.0, -30.0), Vv(0, 0, 1)))
    return out


def brackets():
    """FB-2 foot brackets on the lower half: L section (pad under the foot, outer web), cantilevered from the hub-wall front
    face; window inside the L for the FB-2 oil-inlet fittings (-y side) leaving forward; 2 x M16 per foot; a transverse
    key slot 16 x 6 across each pad matches the slot in the FB-2 foot (loose key, axial location; the feet slide in y)"""
    App, Part, Vv = _fc()
    out = []
    for sy in (1, -1):
        ys = lambda a, b: (min(sy * a, sy * b), max(sy * a, sy * b))
        pad = box(BRK['x'][0], BRK['x'][1] + 1.0, *ys(*BRK['y']), *BRK['z_pad'])
        web = box(BRK['x'][0], BRK['x'][1] + 1.0, *ys(*BRK['web_y']), BRK['z_web'], BRK['z_pad'][0] + 0.5)
        b = pad.fuse(web)
        for xh in BRK['holes_x']:
            b = b.cut(Part.makeCylinder(7.0, 20.0, Vv(xh, sy * BRK['y_hole'], BRK['z_pad'][0] - 2.0), Vv(0, 0, 1)))
        b = b.cut(box(BRK['key_x'][0], BRK['key_x'][1], *ys(BRK['y'][0] - 1.0, BRK['web_y'][0]), BRK['z_pad'][1] - BRK['key_d'], BRK['z_pad'][1] + 1.0))
        out.append(b)
    return out


def casing_halves():
    App, Part, Vv = _fc()
    s = fuse([casing_full()] + split_lugs_casing())
    for h in lug_holes(): s = s.cut(h)
    lo, up = halves(s)
    lo = fuse([lo] + brackets())
    # lifting: 2 x M16 radial tapped holes in the rim of the upper half (+-30 deg from the top)
    for a in (60.0, 120.0):
        ph = math.radians(a); er = Vv(0, math.cos(ph), math.sin(ph))
        up = up.cut(Part.makeCylinder(7.0, 30.0, Vv(0.5 * (CAS['x_rim'] + CAS['x_rear']), 0, 0) + er * (CAS['r_rim_o'] - 28.0), er))
    return lo, up


# ================================================================================================ plenum box (IN-510/511)
def plenum_full():
    """welded box: front plate (tunnel hole), rear plate (hole for the casing rim, flush), sides, bottom, top flange, dry
    tunnel r 284-290 with its rear flange ring onto the casing tunnel ring, split flange bars at z 0"""
    App, Part, Vv = _fc()
    x0, x1, y1, z0, z1, t = BX['x0'], BX['x1'], BX['y1'], BX['z0'], BX['z1'], T_P
    R = G['R_T']
    parts = [box(x0 - t, x0, -y1 - t, y1 + t, z0 - t, z1).cut(Part.makeCylinder(R - t, 3 * t, Vv(x0 - 2 * t, 0, 0), Vv(1, 0, 0))),
             box(x1, x1 + t, -y1 - t, y1 + t, z0 - t, z1).cut(Part.makeCylinder(CAS['r_rim'] + 1.0, 3 * t, Vv(x1 - t, 0, 0), Vv(1, 0, 0))),
             box(x0 - t, x1 + t, y1, y1 + t, z0 - t, z1), box(x0 - t, x1 + t, -y1 - t, -y1, z0 - t, z1),
             box(x0 - t, x1 + t, -y1 - t, y1 + t, z0 - t, z0),
             box(x0 - 26.0, x1 + 26.0, -y1 - 26.0, y1 + 26.0, z1, z1 + 12.0).cut(box(x0, x1, -y1, y1, z1 - 1.0, z1 + 13.0)),
             tube(x0, CAS['x_land'], R, R - t), tube(CAS['x_land'] - 12.0, CAS['x_land'], R - t, CAS['r_ring_box'])]
    for sy in (1, -1):
        ys = lambda a, b: (min(sy * a, sy * b), max(sy * a, sy * b))
        parts += [box(x0 - t, x1 + t, *ys(y1 + t, y1 + t + 40.0), -10.0, 10.0),            # side split flanges (outside)
                  box(x0 - t - 20.0, x0 - t, *ys(R - t, 440.0), -10.0, 10.0),              # front plate split flange (clear of the lube module)
                  box(x1 + t, x1 + t + 20.0, *ys(CAS['r_rim_o'] + 1.0, y1 + t), -10.0, 10.0),  # rear plate split flange
                  box(x0, CAS['x_land'] - 12.0, *ys(CAS['r_ring_in'], R - t), -10.0, 10.0)]  # tunnel split flanges (dry side)
    if G.get('splitter'):
        sp = box(x0, x1, -0.5 * G['splitter']['t'], 0.5 * G['splitter']['t'], z0, -(R - G['R_lip']) - 4.0)
        parts.append(sp.cut(revolve([(x0 - 1, 0), (x0 - 1, R), (G['x_hub'] - G['R_lip'], R)] + arc((G['x_hub'] - G['R_lip'], R - G['R_lip']),
                                    G['R_lip'], 0.0, 90.0)[1:] + [(x1 + 1, R - G['R_lip']), (x1 + 1, 0)])))
    s = fuse(parts)
    cut = axial_holes(CAS['x_land'] - 13.0, CAS['x_land'] + 1.0, 263.0, 11.0, 16, 11.25)
    cut += axial_holes(x1 - 1.0, x1 + t + 1.0, CAS['r_bolt_box'], 11.0, CAS['n_bolt_box'], 7.5)
    for c in cut: s = s.cut(c)
    return s


def plenum_halves():
    App, Part, Vv = _fc()
    lo, up = halves(plenum_full())
    x0, x1, y1, z0, t = BX['x0'], BX['x1'], BX['y1'], BX['z0'], T_P
    feet = [box(xa, xa + 60.0, min(sy * 380.0, sy * 460.0), max(sy * 380.0, sy * 460.0), E.ENVELOPE['skid_top_z'], z0 - t + 0.5)
            for xa in (x0 + 20.0, x1 - 80.0) for sy in (1, -1)]
    drain = Part.makeCylinder(20.0, 20.0, Vv(30.0, 0, z0 - t - 19.5), Vv(0, 0, 1))
    lo = fuse([lo] + feet + [drain]).cut(Part.makeCylinder(9.0, 40.0, Vv(30.0, 0, z0 - 30.0), Vv(0, 0, 1)))
    lugs = [box(0.0, 60.0, min(sy * (y1 + t), sy * (y1 + t + 14.0)), max(sy * (y1 + t), sy * (y1 + t + 14.0)), BX['z1'] - 90.0, BX['z1'] + 12.0)
            .cut(Part.makeCylinder(16.0, 40.0, Vv(30.0, sy * (y1 + t) - 10.0 * (1 if sy < 0 else -1) - 10.0, BX['z1'] - 50.0), Vv(0, 1, 0)))
            for sy in (1, -1)]
    up = fuse([up] + lugs)
    return lo, up


def adapter():
    """filter-house adapter: 300 mm rectangular frame on the top flange, flanged both ends (fabric joint inside the frame)"""
    x0, x1, y1, z1, t = BX['x0'], BX['x1'], BX['y1'], BX['z1'] + 12.0, T_P
    frame = box(x0 - t, x1 + t, -y1 - t, y1 + t, z1, z1 + 300.0).cut(box(x0, x1, -y1, y1, z1 - 1.0, z1 + 301.0))
    fl = [box(x0 - 26.0, x1 + 26.0, -y1 - 26.0, y1 + 26.0, z, z + 12.0).cut(box(x0, x1, -y1, y1, z - 1.0, z + 13.0)) for z in (z1, z1 + 288.0)]
    return fuse([frame] + fl)


def build_all():
    lo, up = casing_halves()
    plo, pup = plenum_halves()
    return {
        'IN-501 Inlet casing, upper half (EN-GJS-400-18)': (up, 'EN-GJS-400-18', 'casing'),
        'IN-502 Inlet casing, lower half + FB-2 foot brackets (EN-GJS-400-18)': (lo, 'EN-GJS-400-18', 'casing'),
        'IN-510 Plenum box, upper half + filter-house flange (S235JR)': (pup, 'S235JR', 'casing'),
        'IN-511 Plenum box, lower half + feet (S235JR)': (plo, 'S235JR', 'casing'),
        'IN-520 Filter-house adapter + fabric joint': (adapter(), 'S235JR + fabric', 'aux'),
    }


DESC = {
    'IN-501': 'upper half: hub wall x 143-157 (bore r 130.5 over FB, cord O-ring on the FB fairing face), front lip R40, '
              'struts at 45 / 135 deg (solid, chord 75, t 16), shroud wall x 204-222 with the R10 bellmouth corner into the '
              'inducer shroud r 137.5, spigot recess r 150 on the compressor casing, 24 x M12 from the back; lifts off after '
              'the plenum upper half',
    'IN-502': 'lower half as IN-501 with the struts at 225 / 315 deg and two L brackets for the FB-2 centre-line feet '
              '(pad z -20, 2 x M16 each, transverse key slot 16 x 6 at x 87-103, window for the oil-inlet fittings)',
    'IN-510': 'welded box 6 mm: plenum x -140..204, y +-540, z 0..600, filter-house flange 1080 x 344 on top, dry tunnel half '
              'r 290 round FB-1 and the coupling, bolted flush onto the casing rim (24 x M10) and the tunnel ring (16 x M10)',
    'IN-511': 'lower half of the box down to z -620, 4 feet to the skid, washing / condensate drain at the low point; the dry '
              'tunnel half carries no penetration: the FB services leave forward through the tunnel (open at x -140)',
    'IN-520': 'rectangular frame 300 mm with the fabric expansion joint to the filter-house duct (F7 + F9, inlet-air cooler, '
              'silencer: vendor)',
}


def main_cad():
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_inl')
    os.makedirs(out_c, exist_ok=True); os.makedirs(OUT_F, exist_ok=True)
    info = {}
    for name, (s, mat, grp) in build_all().items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(OUT_F, fn))
        bb = s.BoundBox
        m = s.Volume * 1e-9 * RHO.get(mat, 7850)
        info[name] = dict(step=fn, material=mat, group=grp, valid=s.isValid(), solids=len(s.Solids), mass_kg=round(m, 2),
                          desc=DESC[name[:6]], bbox=[round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)])
        print('%-70s %-5s solids %2d  %8.2f kg  x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f' % (name, s.isValid(), len(s.Solids), m,
              bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), flush=True)
    json.dump(dict(frame='rotor frame mm, x = engine axis, z up', design=E.DESIGN, geometry=dict(G, shroud=E.shroud_profile(G),
              hub_path=E.hub_profile(G)), casing=CAS, brackets=BRK, parts=info), open(os.path.join(OUT_F, 'parts.json'), 'w'), indent=1)


def check():
    """common volumes of the inlet parts with each other, the rotor and front-bearing parts, the impellers, the exhaust cold
    pipe and the package placeholders next to the inlet"""
    App, Part, Vv = _fc()
    import glob
    mine = {}
    for name, q in json.load(open(os.path.join(OUT_F, 'parts.json')))['parts'].items():
        s = Part.Shape(); s.read(os.path.join(OUT_F, q['step'])); mine[name] = s
    paths = sorted(glob.glob(os.path.join(ROOT, 'fusion', 'A1000_rotor', '*.step'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'fusion', 'A1000C', '*.step'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'fusion', 'A1000_exh', 'EX_440*.step'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'fusion', 'A1000_pipe', '*.step'))) + \
        [os.path.join(ROOT, 'fusion', 'A1000_pkg', f) for f in ('High_speed_coupling.step', 'Compressor_casing.step',
                                                               'Epicyclic_gearbox_10_1.step', 'Lube_oil_module.step', 'Base_frame__skid.step')]
    others = {}
    for p in paths:
        if not os.path.exists(p): continue
        s = Part.Shape(); s.read(p); others['%s/%s' % (os.path.basename(os.path.dirname(p)), os.path.basename(p))] = s
    res = []
    names = list(mine)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not mine[a].BoundBox.intersect(mine[b].BoundBox): continue
            v = mine[a].common(mine[b]).Volume
            if v > 1.0: res.append((a, b, v))
        for b, sb in others.items():
            if not mine[a].BoundBox.intersect(sb.BoundBox): continue
            try: v = mine[a].common(sb).Volume
            except Exception: v = -1.0
            if abs(v) > 1.0: res.append((a, b, v))
            print('  %-40s %-70s %10.0f' % (a[:40], b, v), flush=True)
    for a, b, v in res: print('INTERFERENCE %-50s %-70s %10.0f mm3' % (a, b, v))
    print('checked %d own parts against %d own + %d others: %d interferences' % (len(mine), len(mine), len(others), len(res)))
    json.dump([dict(a=a, b=b, mm3=v) for a, b, v in res], open(os.path.join(OUT_F, 'interference.json'), 'w'), indent=1)


def update_pkg():
    """fusion/A1000_pkg/pkg.json: the concept placeholder 'Air inlet plenum + bellmouth' is replaced by the IN-5xx parts
    (step ../A1000_inl/<file>, names, masses); every other entry is left as it is"""
    pp = os.path.join(ROOT, 'fusion', 'A1000_pkg', 'pkg.json')
    pkg = json.load(open(pp)); parts = json.load(open(os.path.join(OUT_F, 'parts.json')))['parts']
    old = ('Air inlet plenum + bellmouth',)
    keep = [e for e in pkg['parts'] if e['name'] not in old and not e['name'].startswith('IN-5')]
    idx = next((i for i, e in enumerate(pkg['parts']) if e['name'] in old or e['name'].startswith('IN-5')), len(keep))
    new = [dict(name=n, group=q['group'], inst=[0.0], desc=q['desc'], material=q['material'], mass_kg=q['mass_kg'],
                step='../A1000_inl/' + q['step'], dx=0.0) for n, q in parts.items()]
    pkg['parts'] = keep[:idx] + new + keep[idx:]
    json.dump(pkg, open(pp, 'w'), indent=1)
    print('pkg.json: removed %s, added %d IN-5xx parts (%d parts now)' % (', '.join(old), len(new), len(pkg['parts'])))


if '--cad' in sys.argv:
    main_cad()
if '--check' in sys.argv:
    check()
if '--pkg' in sys.argv:
    update_pkg()
