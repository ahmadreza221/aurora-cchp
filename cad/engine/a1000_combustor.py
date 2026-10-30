"""AURORA-1000 combustion system rev 1 (CAD): vertical DLE can, hot-gas scroll to NGV1, scroll pressure casing.
Sizes come from sim/engine/a1000_combustor.py (sim/engine/fea/a1000_combustor.json, block 'geometry'); run that first.

Parts (rotor frame mm, x = engine axis from the gearbox coupling face, z up; can axis vertical at x_can, y = 0):
  CB-301..303  can casing with the DN450 hot-air nozzle, base plate (seal around the neck), head cover   1.4948
  CB-310       7 premixers (centre pilot + 6 mains): mixing tube, centre body (fuel lance), 10 swirler vanes   IN625
  CB-320/321   liner (dome, primary zone, two dilution rows, exit cone, hula seal) and impingement sleeve  Hastelloy X
  CB-330/331   hot-gas casing in two halves: neck, two-branch scroll body, vaned radial passage, bend to NGV1   Haynes 230
  CB-332       22 deswirl vanes (cambered from the scroll swirl to radial, over-turned for the deviation)     Haynes 230
  CB-333       insulation cassettes on the outside of the hot-gas casing (microporous in foil)
  CB-340/341   scroll pressure casing (mid-casing) halves: eccentric shell, end plates, can nozzle, split flanges  P355NH
  CB-350       NGV1 interface leaf seals (hub, tip); CB-360 4 radial support pins; CB-370 fuel manifolds + igniter
Not modelled: impingement holes (perforation of CB-321, count in parts.json), DZ ribs, TBC, bolts, instrumentation.
Run:   freecadcmd -c "import sys; sys.argv=['a1000_combustor.py','--cad']; exec(open('cad/engine/a1000_combustor.py').read())"
       -> cad_out/engine/A1000_comb/*.step, fusion/A1000_comb/*.step + parts.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
GJ = json.load(open(os.path.join(ROOT, 'sim', 'engine', 'fea', 'a1000_combustor.json')))['geometry']


def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def revolve(poly):
    App, Part, V = _fc()
    pts = [V(x, 0, r) for x, r in poly]
    if (pts[0] - pts[-1]).Length > 1e-6: pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).revolve(V(0, 0, 0), V(1, 0, 0), 360.0)


def zcyl(r, z0, z1, x=None, y=0.0):
    App, Part, V = _fc()
    return Part.makeCylinder(r, z1 - z0, V(GJ['x_can'] if x is None else x, y, z0), V(0, 0, 1))


def ztube(ro, ri, z0, z1, x=None, y=0.0):
    return zcyl(ro, z0, z1, x, y).cut(zcyl(ri, z0 - 1, z1 + 1, x, y))


def box(x0, x1, y0, y1, z0, z1):
    App, Part, V = _fc()
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def half(shape, upper):
    return shape.common(box(-3000, 4000, -3000, 3000, 0.0 if upper else -3000.0, 3000.0 if upper else 0.0))


def offset_line(pts, d, side):
    """offset an (x, r) polyline by d to one side (side = +1 left of the direction of travel)"""
    out = []
    n = len(pts)
    for i in range(n):
        x0, r0 = pts[max(i - 1, 0)]; x1, r1 = pts[min(i + 1, n - 1)]
        tx, tr = x1 - x0, r1 - r0; L = math.hypot(tx, tr)
        nx, nr = -tr / L * side, tx / L * side
        out.append((pts[i][0] + d * nx, pts[i][1] + d * nr))
    return out


def strip(line, d0, d1, side):
    a = offset_line(line, d0, side); b = offset_line(line, d1, side)
    return revolve(a + b[::-1])


# ------------------------------------------------------------------------------------------------ hot-gas casing
def body_section(theta, grow, x_extra=0.0):
    """scroll body rectangle at angle theta (from +z towards +y), grown by 'grow' [mm] -> closed 3-D wire"""
    App, Part, V = _fc()
    ro = GJ['r_out'][str(int(theta))] if str(int(theta)) in GJ['r_out'] else None
    if ro is None:
        ks = sorted(int(k) for k in GJ['r_out']); lo = max(k for k in ks if k <= theta); hi = min(k for k in ks if k >= theta)
        ro = GJ['r_out'][str(lo)] if lo == hi else GJ['r_out'][str(lo)] + (GJ['r_out'][str(hi)] - GJ['r_out'][str(lo)]) * (theta - lo) / (hi - lo)
    x0, x1 = GJ['x_front'] - grow - x_extra, GJ['x_rear_s'] + grow
    r0, r1 = GJ['r_body_in'] - grow, ro + grow
    t = math.radians(theta)
    pts = [V(x, r * math.sin(t), r * math.cos(t)) for x, r in ((x0, r0), (x1, r0), (x1, r1), (x0, r1))]
    return Part.makePolygon(pts + [pts[0]])


def scroll_body(grow):
    App, Part, V = _fc()
    ths = list(range(0, 181, 10))
    right = Part.makeLoft([body_section(t, grow) for t in ths], True, False)
    left = right.mirror(V(0, 0, 0), V(0, 1, 0))
    return right.fuse(left).removeSplitter()


def neck(grow):
    """loft from a rectangle in the scroll top (x_front..x_rear_s, y +-neck_b) to the circle under the liner exit"""
    App, Part, V = _fc()
    n = 32; xc = GJ['x_can']
    x0, x1, b = GJ['x_front'] - grow + 3.0, GJ['x_rear_s'] + grow - 3.0, GJ['neck_b'] + grow   # 3 mm inside the body faces
    rc = (GJ['D_neck'] / 2 + grow) / math.cos(math.pi / n); xm = 0.5 * (x0 + x1); hx = 0.5 * (x1 - x0)   # polygon around the circle
    def rect(z, f):
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n; c, s = math.cos(a), math.sin(a)
            m = max(abs(c) / hx, abs(s) / b)                       # point on the rectangle along the ray
            xr, yr = xm + c / m, s / m
            xcirc, ycirc = xc + rc * c, rc * s
            pts.append(V(xr + (xcirc - xr) * f, yr + (ycirc - yr) * f, z))
        return Part.makePolygon(pts + [pts[0]])
    z0, zc, z1 = GJ['z_neck0'], GJ['z_neck_c'], GJ['z_neck1']        # round from zc up (through the casing nozzle)
    fs = [0.0, 0.25, 0.5, 0.72, 0.88, 0.97, 1.0]                    # ruled (no overshoot past the round part)
    secs = [rect(z0 + (zc - z0) * k / (len(fs) - 1), f) for k, f in enumerate(fs)] + [rect(z1, 1.0)]
    return Part.makeLoft(secs, True, True)


def transition_lines():
    hub = [tuple(p) for p in GJ['hub']]; tip = [tuple(p) for p in GJ['tip']]
    top = GJ['r_body_in'] + 5.0
    hub = [(GJ['x_front'], top)] + hub; tip = [(GJ['x_rear_t'], top)] + tip
    return hub, tip


def transition_gas():
    """vaned passage + bend; its top runs 1-3 mm inside the scroll body so no face is coplanar with the body front"""
    hub, tip = transition_lines()
    hub = [(GJ['x_front'] + 3.0, hub[0][1]), (GJ['x_front'], GJ['r_body_in'] - 3.0)] + hub[1:]
    return revolve(tip + hub[::-1])


def vane(k):
    """deswirl vane k: camber from LE (r_vane_le, alpha_in) to TE (r_vane_te, over-turned by half the deviation)"""
    App, Part, V = _fc()
    vq = GJ['vanes'][k]; th0 = math.radians(vq['theta'])
    a_le = math.radians(vq['alpha_in']); sgn = 1.0 if vq['alpha_in'] >= 0 else -1.0
    a_te = -sgn * math.radians(0.5 * vq['dev']) if abs(vq['alpha_in']) > 1e-6 else 0.0
    rs = [GJ['r_vane_le'] - (GJ['r_vane_le'] - GJ['r_vane_te']) * i / 16 for i in range(17)]
    phi = [0.0]
    for i in range(1, len(rs)):
        f = (i - 0.5) / 16; b = a_le + (a_te - a_le) * f
        phi.append(phi[-1] - math.tan(b) * (rs[i] - rs[i - 1]) / (0.5 * (rs[i] + rs[i - 1])))
    # shift so the camber line is centred on th0 at mid radius; thickness normal to the camber line (in the y-z plane)
    ph_mid = phi[8]
    pts_c = [(r, th0 + p - ph_mid) for r, p in zip(rs, phi)]
    def yz(r, a): return (r * math.sin(a), r * math.cos(a))
    half_t = GJ['t_vane'] / 2
    up, dn = [], []
    for i, (r, a) in enumerate(pts_c):
        j0, j1 = max(i - 1, 0), min(i + 1, len(pts_c) - 1)
        y0, z0 = yz(*pts_c[j0]); y1, z1 = yz(*pts_c[j1]); ty, tz = y1 - y0, z1 - z0; L = math.hypot(ty, tz)
        ny, nz = -tz / L, ty / L
        tt = half_t * (0.35 + 0.65 * math.sin(math.pi * min(1.0, (i + 0.6) / 16.5)))      # rounded LE / TE
        y, z = yz(r, a)
        up.append(V(GJ['x_front'] - 8, y + tt * ny, z + tt * nz)); dn.append(V(GJ['x_front'] - 8, y - tt * ny, z - tt * nz))
    w = Part.makePolygon(up + dn[::-1] + [up[0]])
    return Part.Face(w).extrude(V(GJ['x_rear_t'] - GJ['x_front'] + 16, 0, 0))


def hot_gas_casing():
    """returns (wall, vanes, insulation, gas)"""
    App, Part, V = _fc()
    t, ti = GJ['t_wall'], GJ['t_ins']
    hub, tip = transition_lines()
    gas = scroll_body(0.0).fuse(transition_gas()).fuse(neck(0.0))
    # transition walls: hub wall to the front cavity side, tip wall to the rear (air) side
    hw = strip(hub, 0.0, t, -1); tw = strip(tip, 0.0, t, 1)
    wall = scroll_body(t).fuse(neck(t)).fuse(hw).fuse(tw)
    wall = wall.cut(gas)
    # NGV1 end: open the annulus face, keep the walls
    x_ex = GJ['interfaces']['x_ngv_ring'] - 1.0
    wall = wall.cut(box(x_ex, x_ex + 50, -400, 400, -400, 400)).removeSplitter()
    ins = scroll_body(t + ti).fuse(neck(t + ti)).fuse(strip(hub, t, t + ti, -1)).fuse(strip(tip, t, t + ti, 1))
    ins = ins.cut(scroll_body(t).fuse(neck(t)).fuse(gas).fuse(hw).fuse(tw)).cut(box(x_ex - 2, x_ex + 50, -400, 400, -400, 400))
    ins = ins.cut(zcyl(GJ['D_neck'] / 2 + t + ti + 1, GJ['z_neck1'] - 35, GJ['z_neck1'] + 5))       # neck top: hula seal zone bare
    passage = transition_gas()                                     # vanes end on the wall faces (cast / welded integral)
    vanes = Part.makeCompound([vane(k).common(passage) for k in range(len(GJ['vanes']))])
    return wall, vanes, ins.removeSplitter(), gas


# ------------------------------------------------------------------------------------------------ can, liner, premixers
def can_parts():
    App, Part, V = _fc()
    st = GJ['stations']; xc = GJ['x_can']
    Rc = GJ['D_case'] / 2; tc = GJ['t_case']; zb = GJ['z_base']; zcov = st['z_cover']
    casing = ztube(Rc + tc, Rc, zb, zcov)
    casing = casing.fuse(ztube(Rc + 45, Rc, zb, zb + 25)).fuse(ztube(Rc + 55, Rc, zcov - 30, zcov))
    rn = GJ['D_hot_in'] / 2
    noz = Part.makeCylinder(rn + 8, Rc + 180.0, V(xc, 0, GJ['z_hot_in']), V(0, 1, 0)).fuse(
        Part.makeCylinder(rn + 50, 22.0, V(xc, Rc + 158.0, GJ['z_hot_in']), V(0, 1, 0)))
    noz = noz.cut(zcyl(Rc - 0.5, zb, zcov))
    casing = casing.fuse(noz).cut(Part.makeCylinder(rn, 600.0, V(xc, 0, GJ['z_hot_in']), V(0, 1, 0))).removeSplitter()
    r_hole = GJ['D_neck'] / 2 + GJ['t_wall'] + GJ['t_ins'] + 4
    base = ztube(Rc + 45, r_hole, zb - 20, zb)
    cover = zcyl(Rc + 55, zcov, zcov + GJ['t_cover'])
    pm = GJ['premixer']; Do, Dcb, Lmt = pm['D_o'], pm['D_cb'], pm['L_mt']
    pos = [(xc, 0.0)] + [(xc + GJ['r_ring_pm'] * math.cos(math.radians(60 * k + 30)), GJ['r_ring_pm'] * math.sin(math.radians(60 * k + 30))) for k in range(6)]
    for (x, y) in pos:
        cover = cover.cut(zcyl(Dcb / 2 + 2, zcov - 1, zcov + GJ['t_cover'] + 1, x, y))
    # premixers: mixing tube from the dome up, swirler, bellmouth; centre body = fuel lance through the cover
    zd = st['z_dome']; Lsw = 0.45 * Do; tw = 2.5
    pms = []
    for i, (x, y) in enumerate(pos):
        tube = ztube(Do / 2 + tw, Do / 2, zd, zd + Lmt + Lsw, x, y)
        bell = ztube(Do / 2 + tw + 10, Do / 2 + 0.5, zd + Lmt + Lsw, zd + Lmt + Lsw + 6, x, y)
        cb = zcyl(Dcb / 2, zd + 2, zcov, x, y).fuse(zcyl(Dcb / 2 + 2, zcov - 1, zcov + GJ['t_cover'] + 30, x, y))
        cb = cb.cut(zcyl(4.0, zd + 1, zd + 40, x, y))                                     # axial purge / pilot tip bore
        vanes = []
        for k in range(GJ['sw_vanes']):
            a = 2 * math.pi * k / GJ['sw_vanes']
            bl = Part.makeBox(Do / 2 - Dcb / 2 + 0.5, 1.6, Lsw / math.cos(math.radians(GJ['sw_angle'])),
                              V(Dcb / 2 - 0.2, -0.8, 0))
            bl.rotate(V(0, 0, 0), V(1, 0, 0), GJ['sw_angle'])
            bl = bl.common(Part.makeCylinder(Do / 2 + 0.3, Lsw, V(0, 0, 0), V(0, 0, 1)))
            bl.rotate(V(0, 0, 0), V(0, 0, 1), math.degrees(a)); bl.translate(V(x, y, zd + Lmt))
            vanes.append(bl)
        s = tube.fuse(bell).fuse(cb)
        for vv in vanes: s = s.fuse(vv)
        pms.append(s.removeSplitter())
    # liner: dome, cylinder PZ + DZ, exit cone, hula seal ring; stiffening rings on the PZ every 150 mm
    RL = GJ['D_L'] / 2; tL = GJ['t_L']
    liner = ztube(RL + tL, RL, st['z_dz0'], zd)
    z_c0 = GJ['z_exit'] + GJ['L_sleeve']
    cone = Part.makeCone(GJ['D_exit'] / 2 + tL, RL + tL, GJ['L_cone'], V(xc, 0, z_c0), V(0, 0, 1)).cut(
        Part.makeCone(GJ['D_exit'] / 2, RL, GJ['L_cone'], V(xc, 0, z_c0), V(0, 0, 1)))
    cone = cone.fuse(ztube(GJ['D_exit'] / 2 + tL, GJ['D_exit'] / 2, GJ['z_exit'], z_c0 + 0.5))           # exit sleeve
    dome = zcyl(RL + tL, zd, zd + 3.0)
    for (x, y) in pos: dome = dome.cut(zcyl(Do / 2 + 2.8, zd - 1, zd + 4, x, y))
    liner = liner.fuse(cone).fuse(dome)
    zr = st['z_pz0'] + 150.0
    while zr < zd - 60:
        liner = liner.fuse(ztube(RL + tL + 4, RL + tL - 0.1, zr - 3, zr + 3)); zr += 150.0
    hula = ztube(GJ['D_neck'] / 2 - 0.3, GJ['D_exit'] / 2 + tL - 0.1, GJ['z_exit'], GJ['z_exit'] + 35)   # spring fingers, fitted state
    liner = liner.fuse(hula)
    for row, zz in zip(GJ['dilution'], (st['z_pz0'] - 25.0, st['z_pz0'] - 70.0)):
        for k in range(row['n']):
            a = 2 * math.pi * (k + (0.5 if zz < st['z_pz0'] - 50 else 0.0)) / row['n']
            liner = liner.cut(Part.makeCylinder(row['d_mm'] / 2, 30.0, V(xc + (RL - 10) * math.cos(a), (RL - 10) * math.sin(a), zz),
                                                V(math.cos(a), math.sin(a), 0)))
    liner = liner.removeSplitter()
    # impingement sleeve: from below the dilution rows to the dome rim, closing rings to the liner at both ends
    Rs = RL + tL + GJ['g_inner']
    z_s0 = st['z_pz0'] - 100.0
    sleeve = ztube(Rs + GJ['t_sleeve'], Rs, z_s0, zd + 3).fuse(ztube(Rs + GJ['t_sleeve'], RL + tL, z_s0, z_s0 + 3)).fuse(
        ztube(Rs + GJ['t_sleeve'], RL + tL, zd, zd + 3)).removeSplitter()
    return dict(casing=casing, base=base, cover=cover, premixers=pms, liner=liner, sleeve=sleeve, pos=pos)


# ------------------------------------------------------------------------------------------------ mid-casing, seals, pins, manifolds
def mid_casing():
    App, Part, V = _fc()
    R, t, zc = GJ['R_mc'], GJ['t_mc'], GJ['z_mc']; x0, x1, te = GJ['x_mc0'], GJ['x_mc1'], GJ['t_end']
    def ecyl(r, xa, xb): return Part.makeCylinder(r, xb - xa, V(xa, 0, zc), V(1, 0, 0))
    shell = ecyl(R + t, x0 + te, x1 - te).cut(ecyl(R, x0 + te - 1, x1 - te + 1))
    front = ecyl(R + t, x0, x0 + te).cut(Part.makeCylinder(GJ['barrel']['r'] + 1.0, te + 2, V(x0 - 1, 0, 0), V(1, 0, 0)))
    rear = ecyl(R + t, x1 - te, x1).cut(Part.makeCylinder(GJ['cas']['ri'], te + 2, V(x1 - te - 1, 0, 0), V(1, 0, 0)))
    mc = shell.fuse(front).fuse(rear)
    # can nozzle on top + flange; the neck passes through it
    rn = GJ['r_noz']; z_top = zc + R
    noz = zcyl(rn + 12, z_top - 60, GJ['z_noz']).fuse(zcyl(rn + 80, GJ['z_noz'] - 20, GJ['z_noz']))
    mc = mc.fuse(noz).cut(zcyl(rn, z_top - 200, GJ['z_noz'] + 1))
    # horizontal split flanges (both sides)
    y_s = math.sqrt(R ** 2 - zc ** 2)
    for sy in (1, -1):
        y0, y1 = sorted((sy * (y_s - 5), sy * (y_s + t + 55)))
        mc = mc.fuse(box(x0, x1, y0, y1, -25, 25).cut(ecyl(R, x0 - 1, x1 + 1)))
    # end-plate stiffening ribs (12 radial ribs on each plate, outside)
    for xa, sgn in ((x0, -1), (x1, 1)):
        for k in range(12):
            a = 2 * math.pi * (k + 0.5) / 12
            r_in = GJ['barrel']['r'] + 5 if sgn < 0 else GJ['cas']['fl_r'] + 5
            rib = box(0, 40, -8, 8, r_in, R + t - 30)
            rib.rotate(V(0, 0, 0), V(1, 0, 0), math.degrees(a))
            rib.translate(V(xa - 40 if sgn < 0 else xa, 0, 0))
            mc = mc.fuse(rib)
    mc = mc.removeSplitter()
    return half(mc, True).removeSplitter(), half(mc, False).removeSplitter()


def seals_pins_manifolds(can):
    App, Part, V = _fc()
    I = GJ['interfaces']; x_ex = I['x_ngv_ring'] - 1.0
    # W-seals in the 1 mm face gap between the transition walls and the NGV1 ring faces (radial sliding allowed)
    xs0, xs1 = x_ex + 0.1, I['x_ngv_ring'] - 0.1
    seals = Part.makeCompound([revolve([(xs0, I['r_hub'] - 4.5), (xs1, I['r_hub'] - 4.5), (xs1, I['r_hub'] - 0.5), (xs0, I['r_hub'] - 0.5)]),
                               revolve([(xs0, I['r_tip'] + 0.5), (xs1, I['r_tip'] + 0.5), (xs1, I['r_tip'] + 4.5), (xs0, I['r_tip'] + 4.5)])])
    pins = []
    for th in (50.0, 130.0, 230.0, 310.0):
        t = math.radians(th); tt = th if th <= 180 else 360 - th
        ks = sorted(int(k) for k in GJ['r_out']); lo = max(k for k in ks if k <= tt); hi = min(k for k in ks if k >= tt)
        ro = GJ['r_out'][str(lo)] + (GJ['r_out'][str(hi)] - GJ['r_out'][str(lo)]) * ((tt - lo) / (hi - lo) if hi > lo else 0)
        r0 = ro + GJ['t_wall'] + 2.0; d = V(0, math.sin(t), math.cos(t))
        # distance to the eccentric mid-casing along the ray
        b = 2 * GJ['z_mc'] * math.cos(t); c = GJ['z_mc'] ** 2 - GJ['R_mc'] ** 2
        r1 = (b + math.sqrt(b * b - 4 * c)) / 2 + GJ['t_mc']
        p = Part.makeCylinder(10.0, r1 - r0 + 15, V(760.0, 0, 0) + d * r0, d).fuse(Part.makeCylinder(22.0, 12.0, V(760.0, 0, 0) + d * (r1 + 3), d))
        pins.append(p)
    st = GJ['stations']; zt = st['z_cover'] + GJ['t_cover']; xc = GJ['x_can']
    man = []
    for rr, tag in ((150.0, 'A/B'), (110.0, 'P')):
        tor = Part.makeTorus(rr, 14.0, V(xc, 0, zt + 60), V(0, 0, 1)); man.append(tor)
    for (x, y) in can['pos']:
        man.append(zcyl(8.0, zt + 30, zt + 60, x, y))
    ign = Part.makeCylinder(12.0, 260.0, V(xc + 0.0, 185.0, st['z_dome'] + 60), V(0, 0.15, 1))
    uv = [Part.makeCylinder(10.0, 240.0, V(xc + 185.0 * math.cos(a), 185.0 * math.sin(a), st['z_dome'] + 70), V(0, 0, 1)) for a in (math.radians(200), math.radians(340))]
    return seals, Part.makeCompound(pins), Part.makeCompound(man), Part.makeCompound([ign] + uv)


def build_all():
    out = {}
    wall, vanes, ins, gas = hot_gas_casing()
    out['CB-330 Hot-gas casing upper half (Haynes 230)'] = (half(wall, True).removeSplitter(), 'Haynes 230', 'hot')
    out['CB-331 Hot-gas casing lower half (Haynes 230)'] = (half(wall, False).removeSplitter(), 'Haynes 230', 'hot')
    out['CB-332 Deswirl vanes x%d (Haynes 230)' % len(GJ['vanes'])] = (vanes, 'Haynes 230', 'hot')
    out['CB-333 Scroll insulation cassettes'] = (ins, 'microporous + foil', 'insulation')
    can = can_parts()
    out['CB-301 Can casing (1.4948)'] = (can['casing'], '1.4948', 'casing')
    out['CB-302 Can base plate (1.4948)'] = (can['base'], '1.4948', 'casing')
    out['CB-303 Head cover (1.4948)'] = (can['cover'], '1.4948', 'casing')
    App, Part, V = _fc()
    out['CB-310 Premixers x7 (pilot + 6 mains, IN625)'] = (Part.makeCompound(can['premixers']), 'IN625', 'hot')
    out['CB-320 Liner (Hastelloy X + TBC)'] = (can['liner'], 'Hastelloy X', 'hot')
    out['CB-321 Impingement sleeve (Hastelloy X)'] = (can['sleeve'], 'Hastelloy X', 'hot')
    up, lo = mid_casing()
    seals, pins, man, ign = seals_pins_manifolds(can)
    # holes: pins through the insulation and the mid-casing shell, igniter / scanners through the head cover
    hole = lambda c: Part.makeCompound([sl.makeOffsetShape(0.6, 0.01) for sl in c.Solids])
    ph, ih = hole(pins), hole(ign)
    out['CB-333 Scroll insulation cassettes'] = (ins.cut(ph), 'microporous + foil', 'insulation')
    up, lo = up.cut(ph), lo.cut(ph)
    out['CB-303 Head cover (1.4948)'] = (out['CB-303 Head cover (1.4948)'][0].cut(ih), '1.4948', 'casing')
    out['CB-340 Scroll pressure casing upper half (P355NH)'] = (up, 'P355NH', 'casing')
    out['CB-341 Scroll pressure casing lower half (P355NH)'] = (lo, 'P355NH', 'casing')
    out['CB-350 NGV1 interface leaf seals'] = (seals, 'Haynes 25', 'hot')
    out['CB-360 Scroll support pins x4 (1.4980)'] = (pins, '1.4980 (A286)', 'casing')
    out['CB-370 Fuel manifolds P / A / B + lances'] = (man, '1.4404', 'aux')
    out['CB-371 Igniter + 2 UV flame scanners'] = (ign, 'bought in', 'aux')
    return out, gas


def main_cad():
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_comb'); out_f = os.path.join(ROOT, 'fusion', 'A1000_comb')
    os.makedirs(out_c, exist_ok=True); os.makedirs(out_f, exist_ok=True)
    rho = {'Haynes 230': 8970, '1.4948': 7900, 'IN625': 8440, 'Hastelloy X': 8220, 'P355NH': 7850, 'microporous + foil': 320,
           'Haynes 25': 9130, '1.4980 (A286)': 7940, '1.4404': 7950, 'bought in': 3000}
    parts, gas = build_all()
    info = {}
    for name, (s, mat, grp) in parts.items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(out_f, fn))
        bb = s.BoundBox
        info[name] = dict(step=fn, material=mat, group=grp, valid=s.isValid(), solids=len(s.Solids), mass_kg=round(s.Volume * 1e-9 * rho.get(mat, 7850), 2),
                          bbox=[round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)])
        print('%-52s %-5s solids %2d  %8.2f kg  x %.0f..%.0f  z %.0f..%.0f' % (name, s.isValid(), len(s.Solids), info[name]['mass_kg'],
                                                                             bb.XMin, bb.XMax, bb.ZMin, bb.ZMax), flush=True)
    gas.exportStep(os.path.join(out_c, 'hot_gas_volume.step'))
    st = GJ['stations']
    meta = dict(frame='rotor frame mm, z up; can axis vertical at x_can, y 0', x_can=GJ['x_can'],
                nozzle=dict(x=GJ['x_can'], y=GJ['D_case'] / 2 + 180.0, z=GJ['z_hot_in'], D=GJ['D_hot_in']),
                impingement_holes=GJ['impingement'], gas_volume_m3=gas.Volume * 1e-9, z_top=st['z_cover'] + GJ['t_cover'] + 90)
    json.dump(dict(meta, parts=info), open(os.path.join(out_f, 'parts.json'), 'w'), indent=1)


if '--cad' in sys.argv:
    main_cad()


# ------------------------------------------------------------------------------------------------ section drawing (--section)
def section():
    """docs/img/a1000_combustor_section.png: x-z section through the can axis (y = 0) and y-z section through the scroll
    (x = 600) from the STEP parts, with the rotor, hot section, NGV1 and compressor casing for context"""
    import glob
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    App, Part, V = _fc()
    pkg = json.load(open(os.path.join(ROOT, 'fusion', 'A1000_pkg', 'pkg.json')))
    def load(p, dx=0.0):
        s = Part.Shape(); s.read(p)
        if dx: s.translate(V(dx, 0, 0))
        return s
    col = {'hot': '#d9822b', 'casing': '#6b7280', 'insulation': '#f2d16b', 'aux': '#2f7d32', 'ctx': '#9aa3ad', 'rot': '#4b6cb7', 'ngv': '#b5462f'}
    comb = json.load(open(os.path.join(ROOT, 'fusion', 'A1000_comb', 'parts.json')))['parts']
    shapes = [(load(os.path.join(ROOT, 'fusion', 'A1000_comb', q['step'])), col[q['group']], 0.9) for q in comb.values()]
    for p in glob.glob(os.path.join(ROOT, 'fusion', 'A1000_hot', '*.step')): shapes.append((load(p), col['ctx'], 0.6))
    for nm in ('RT_105_Drum_IN718', 'A1000_R1_disc_with_arms__cast_MAR_M247', 'A1000_R2_disc_with_arms__cast_MAR_M247', 'RT_111_Studs___nuts_drum___R1__16_x_M10'):
        shapes.append((load(os.path.join(ROOT, 'fusion', 'A1000_rotor', nm + '.step')), col['rot'], 0.6))
    for nm in ('A1000_N1_rings', 'A1000_N2_rings'): shapes.append((load(os.path.join(ROOT, 'fusion', 'A1000', nm + '.step'), pkg['x_offset_turbine']), col['ngv'], 0.7))
    for nm in ('Compressor_casing', 'Exhaust_diffuser___5_struts'): shapes.append((load(os.path.join(ROOT, 'fusion', 'A1000_pkg', nm + '.step')), col['ctx'], 0.45))
    shapes.append((load(os.path.join(ROOT, 'fusion', 'A1000C', 'A1000_C2_hub.step')), col['rot'], 0.45))
    fig, ax = plt.subplots(1, 2, figsize=(15, 9), dpi=110, gridspec_kw=dict(width_ratios=[1.25, 1]))
    for a, (nrm, d, ij) in zip(ax, ((V(0, 1, 0), 0.0, (0, 2)), (V(1, 0, 0), 600.0, (1, 2)))):
        for s, c, al in shapes:
            for sol in s.Solids:                                   # per solid: faces with holes, then the outlines
                try:
                    wires = sol.slice(nrm, d)
                    if not wires: continue
                    face = Part.makeFace(wires, 'Part::FaceMakerBullseye')
                except Exception:
                    continue
                for f in face.Faces:
                    pts, tris = f.tessellate(0.3)
                    xy = [((p.x, p.y, p.z)[ij[0]], (p.x, p.y, p.z)[ij[1]]) for p in pts]
                    a.add_collection(PolyCollection([[xy[i] for i in t] for t in tris], facecolor=c, edgecolor='none', alpha=al))
                for w in wires:
                    q = w.discretize(Deflection=0.3)
                    a.plot([(p.x, p.y, p.z)[ij[0]] for p in q], [(p.x, p.y, p.z)[ij[1]] for p in q], 'k-', lw=0.3)
        a.set_aspect('equal'); a.grid(alpha=0.25)
    st = GJ['stations']
    ax[0].set_xlim(150, 1150); ax[0].set_ylim(-650, 2100); ax[0].set_xlabel('x [mm] (engine axis)'); ax[0].set_ylabel('z [mm]')
    ax[0].axhline(0, color='k', lw=0.5, ls='-.')
    for z, t in ((st['z_dome'], 'dome / premixer exits'), (st['z_pz0'], 'dilution rows'), (GJ['z_exit'], 'liner exit (hula seal)'),
                 (GJ['z_hot_in'], 'hot air in (DN450, +y)')):
        ax[0].annotate(t, (1035, z), fontsize=7, va='center')
    ax[0].annotate('NGV1', (680, 232), fontsize=7); ax[0].annotate('compressor', (330, 300), fontsize=7)
    ax[0].annotate('scroll (top / bottom)', (850, 600), fontsize=7); ax[0].annotate('scroll pressure casing', (700, -640), fontsize=7)
    ax[0].set_title('section y = 0 through the can axis', fontsize=10)
    ax[1].set_xlim(-720, 720); ax[1].set_ylim(-700, 900); ax[1].set_xlabel('y [mm] (+y: recuperator side)'); ax[1].set_ylabel('z [mm]')
    ax[1].set_title('section x = 600: two-branch scroll, 22 deswirl vanes, eccentric casing', fontsize=10)
    from matplotlib.patches import Patch
    ax[1].legend(handles=[Patch(color=col[k], label=l) for k, l in (('hot', 'hot parts (Haynes 230, Hastelloy X, IN625)'), ('insulation', 'insulation'),
                 ('casing', 'pressure casings (1.4948, P355NH)'), ('ngv', 'NGV rings'), ('rot', 'rotor'), ('ctx', 'hot section / compressor / exhaust'))],
                 fontsize=7, loc='lower right')
    fig.suptitle('AURORA-1000 combustion system rev 1 (cad/engine/a1000_combustor.py)', fontsize=11)
    fig.tight_layout(); out = os.path.join(ROOT, 'docs', 'img', 'a1000_combustor_section.png'); fig.savefig(out); print('wrote', out)


if '--section' in sys.argv:
    section()
