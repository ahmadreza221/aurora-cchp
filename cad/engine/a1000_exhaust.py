"""AURORA-1000 exhaust and recuperator ducting (phase 2, docs/08 sec. 18): CAD of the parts from the design in
sim/engine/a1000_exhaust.py (GEO, MAN, JB2_MOUNT, layout).

Parts (rotor frame mm, x = engine axis, z up):
  EX-401  air manifold casing      EN-GJS-400-18LT  bolted on the scroll-casing rear plate (x 928), outer shell r 500,
                                                    rear wall + rim (x 1070-1100), 7 pin sleeves, port 150 x 600 at -25 deg
  EX-402  frame pins x7            A286             radial pins put in from outside through sleeves in the manifold
  EX-410  exhaust frame            1.4848 cast      cone 8.5 deg + R120 casing bend + radial flange, 4 cambered hollow struts,
                                                    hub r 200.4 with the JB2 key slots, front lip / seal flange, 7 pin bosses
  EX-411  frame heat shield        1.4828 sheet     10 mm off the cone in the manifold (ceramic paper behind)
  EX-412  JB2 support ring + keys  1.4313           clamps the JB2 cartridge housing (r 130), 8 radial keys into the hub slots
  EX-413  front leaf seal          Haynes 25        on the frame front flange, runs on the C2 rear face (x 875)
  EX-414  rear leaf seal           Haynes 25        on the manifold rim, runs on the frame rear flange
  EX-420  exhaust collector        1.4828 plate     box x 1170-1750 with the front / rear wells, hub cap (R180 bend + rear
                                                    cone), front ring, outlet frame (+y), centre-line support lugs
  EX-421  hub access cover         1.4828           bolted in the hub cap, reached from the rear well (JB2 inspection)
  EX-430  exhaust transition       1.4828 + fabric  collector +y face -> recuperator gas inlet hood (y 1150)
  EX-440  cold air pipe DN350      P265GH           manifold port -> recuperator air inlet; BOV tee
  EX-441  BOV DN125 + dump DN200   1.4541           to the economizer inlet plenum (start bleed / trip blow-off)
  EX-450  hot air pipe DN450       1.4948           recuperator air outlet -> can nozzle (x 665, y 590, z 1140), gimbal pair
  EX-460  recuperator (bought in)  AISI 347         envelope 2.8 x 1.2 x 1.6 m moved +300 mm in y, nozzles as specified
  EX-470  economizer + stack DN800 bought in        on the recuperator gas outlet (top, front end)
Run on the MacBook:  ~/micromamba/envs/fc/bin/freecadcmd -c "import sys; sys.argv=['x','--cad']; exec(open('cad/engine/a1000_exhaust.py').read())"
  --cad    -> cad_out/engine/A1000_exh/*.step, fusion/A1000_exh/*.step + parts.json
  --check  interference with the rotor, hot section and combustor parts (fusion/A1000_rotor, A1000_hot, A1000_comb)
Locally (no FreeCAD):  python3 cad/engine/a1000_exhaust.py --pkg   -> fusion/A1000_pkg/pkg.json entries
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'sim', 'engine'))
import a1000_exhaust as E                                         # noqa: E402

G, D, MAN, JB, ST = E.GEO, E.derived(), E.MAN, E.JB2_MOUNT, E.GEO['struts']
OUT_F = os.path.join(ROOT, 'fusion', 'A1000_exh')
RHO = {'EN-GJS-400-18LT': 7100, 'A286': 7940, '1.4848 cast': 7750, '1.4828': 7900, '1.4313': 7700, 'Haynes 25': 9130,
       'P265GH': 7850, '1.4541': 7900, '1.4948': 7900, 'bought in': 0}
T_CAS = 8.0                                                       # frame casing / hub wall [mm]
T_COL = 6.0                                                       # collector plate [mm]


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
    return revolve([(x0, ri), (x1, ri), (x1, ro), (x0, ro)])


def box(x0, x1, y0, y1, z0, z1):
    App, Part, Vv = _fc()
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vv(x0, y0, z0))


def arc(c, R, a0, a1, n=20):
    """points on an (x, r) arc about c from angle a0 to a1 [rad], angle from +r towards +x"""
    return [(c[0] + R * math.sin(a0 + (a1 - a0) * k / n), c[1] - R * math.cos(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def fuse(shapes):
    s = shapes[0]
    for q in shapes[1:]: s = s.fuse(q)
    return s.removeSplitter()


# ================================================================================================ frame (EX-410)
def strut_prisms(r0, r1, solid=True):
    """4 prismatic struts (or their cavities: section offset 6.5 mm inside, 12-65 % chord) along e_r from r0 to r1"""
    App, Part, Vv = _fc()
    up, lo = E.strut_section()
    xi = [(x - ST['x_le']) / ST['chord'] for x, _ in up]
    if solid:
        sec = up + lo[::-1][1:-1]
    else:
        sec = [(x, s - 6.5) for (x, s), k in zip(up, xi) if 0.12 <= k <= 0.65]
        sec += [(x, s + 6.5) for (x, s), k in zip(lo, xi) if 0.12 <= k <= 0.65][::-1]
    out = []
    for k in range(ST['n']):
        ph = math.radians(ST['theta0'] + 360.0 * k / ST['n'])
        er = Vv(0, math.cos(ph), math.sin(ph)); et = Vv(0, -math.sin(ph), math.cos(ph))
        P = [Vv(x, 0, 0) + er * r0 + et * q for x, q in sec]
        c = Part.BSplineCurve(); c.interpolate(P, PeriodicFlag=True)
        out.append(Part.Face(Part.Wire(c.toShape())).extrude(er * (r1 - r0)))
    return out


def local_box(x0, lx, lt, lr, r0, ph, t0=None):
    """box lx (axial) x lt (tangential, centred unless t0: from -t0 to lt - t0) x lr (radial, outward from r0) at angle ph;
    local axes (x, -e_theta, e_r) form a right-handed set"""
    App, Part, Vv = _fc()
    er = Vv(0, math.cos(ph), math.sin(ph)); et = Vv(0, -math.sin(ph), math.cos(ph))
    b = Part.makeBox(lx, lt, lr)
    b.Placement = App.Placement(Vv(x0, 0, 0) + er * r0 + et * (lt / 2 if t0 is None else lt - t0), App.Rotation(Vv(1, 0, 0), et * -1.0, er, 'XYZ'))
    return b


def radial_cyl(rad, r0, r1, ph, x=None):
    App, Part, Vv = _fc()
    er = Vv(0, math.cos(ph), math.sin(ph))
    return Part.makeCylinder(rad, r1 - r0, Vv(MAN['x_pin'] if x is None else x, 0, 0) + er * r0, er)


def frame():
    """hot casting: casing (front lip, cone, R120 bend, radial flange), hub, 4 hollow struts, key bosses, seal flanges"""
    App, Part, Vv = _fc()
    a = math.radians(G['cone_deg']); ca, sa = math.cos(a), math.sin(a)
    cc, Rc = D['cas_c'], G['R_cas']
    gas = [(876.0, E.r_cas(876.0)), (D['x_cb'], D['r_cb'])] + arc(cc, Rc, a, 0.5 * math.pi)[1:] + [(D['x_fw'], 440.0)]
    back = [(D['x_fw'] - T_CAS, 440.0)] + arc(cc, Rc - T_CAS, 0.5 * math.pi, a)[:-1] + \
           [(D['x_cb'] - T_CAS * sa, D['r_cb'] + T_CAS * ca), (876.0, E.r_cas(876.0) + T_CAS / ca)]
    cas = revolve(gas + back)
    lip = tube(872.0, 880.0, 269.0, E.r_cas(872.0) + 0.2)
    fl_front = tube(885.0, 893.0, 300.0, 272.0)
    fl_rear = tube(1102.0, 1110.0, 345.0, E.r_cas(1102.0) + 4.0)
    hub = tube(890.0, G['x_bend'], G['r_hub'], G['r_hub'] - T_CAS).fuse(tube(890.0, 896.0, G['r_hub'] - 1.0, 100.0))
    hub = hub.fuse(tube(JB['x'][0], JB['x'][1], G['r_hub'] - 1.0, JB['r_hub_bore']))
    body = fuse([cas, lip, fl_front, fl_rear, hub])
    inside = revolve([(860.0, 0.0), (1150.0, 0.0), (1150.0, E.r_cas(1150.0) + T_CAS / ca), (860.0, E.r_cas(860.0) + T_CAS / ca)])
    for s in strut_prisms(G['r_hub'] - T_CAS + 0.5, 335.0): body = body.fuse(s.common(inside))
    for ph in [math.radians(a) for a in MAN['pin_deg']]:            # bosses for the radial pins (sliding fit, radial hole)
        body = body.fuse(local_box(MAN['x_pin'] - 20.0, 40.0, 40.0, 30.0, 295.0, ph)).cut(radial_cyl(MAN['d_pin'] / 2 + 0.1, 300.0, 340.0, ph))
    for c in strut_prisms(G['r_hub'] - T_CAS - 3.0, 336.0, solid=False): body = body.cut(c)
    for k in range(JB['n_key']):                                     # JB2 key through-slots in the hub bore ring (slide-on)
        ph = 2 * math.pi * (k + 0.5) / JB['n_key']
        body = body.cut(local_box(JB['x'][0] - 1.0, JB['x'][1] - JB['x'][0] + 2.0, JB['key_w'] + 0.2, 8.0, JB['r_hub_bore'] - 1.0, ph))
    return body.removeSplitter()


def heat_shield():
    a = math.radians(G['cone_deg'])
    off = (T_CAS + E.MAN['shield_gap']) / math.cos(a)
    x0, x1 = 895.0, 1060.0
    s = revolve([(x0, E.r_cas(x0) + off), (x1, E.r_cas(x1) + off), (x1, E.r_cas(x1) + off + 1.0), (x0, E.r_cas(x0) + off + 1.0)])
    for k in range(ST['n']):
        s = s.cut(local_box(955.0, 100.0, 70.0, 80.0, 270.0, math.radians(ST['theta0'] + 360.0 * k / ST['n']), t0=50.0))
    return s


def jb2_ring():
    """ring on the JB2 cartridge housing (r 130), oil-inlet hole on top; 8 keys on 3 mm mica pads (k <= 2 W/mK: the
    hub runs at ~640 C, bare keys would carry ~1.9 kW into the housing) in the through-slots of the hub bore"""
    App, Part, Vv = _fc()
    s = tube(JB['x'][0], JB['x'][1], JB['r_ring_o'], JB['r_ring_i'])
    s = s.cut(radial_cyl(14.0, 120.0, 160.0, 0.5 * math.pi, x=JB['x_brg']))                     # JB2 oil inlet boss (top)
    s = s.cut(radial_cyl(20.0, 120.0, 160.0, 1.5 * math.pi, x=JB['x_brg'] + 20.0))              # rev 1.3 housing drain boss (bottom)
    pads, keys = [], []
    for k in range(JB['n_key']):
        ph = 2 * math.pi * (k + 0.5) / JB['n_key']
        pads.append(local_box(JB['x'][0] + 10.0, 40.0, JB['key_w'], JB['pad'], JB['r_ring_o'], ph))
        keys.append(local_box(JB['x'][0] + 10.0, 40.0, JB['key_w'], JB['r_hub_bore'] + 4.0 - JB['r_ring_o'] - JB['pad'],
                              JB['r_ring_o'] + JB['pad'], ph))
    return Part.makeCompound([s.removeSplitter()] + pads + keys)


# ================================================================================================ manifold (EX-401)
def manifold():
    App, Part, Vv = _fc()
    x0, x1, ro, t = MAN['x0'], MAN['x1'], MAN['r_o'], MAN['t']
    rx0, rx1 = MAN['rim_x']
    s = revolve([(x0, ro), (x0, 560.0), (x0 + 20.0, 560.0), (x0 + 20.0, ro + t), (x1, ro + t), (x1, MAN['rim_ri']),
                 (rx0, MAN['rim_ri']), (rx0, MAN['rim_ro']), (x1 - t, MAN['rim_ro']), (x1 - t, ro)])
    s = s.cut([Part.makeCylinder(9.0, 22.0, Vv(x0 - 1.0, 535.0 * math.cos(2 * math.pi * (k + 0.5) / 24), 535.0 * math.sin(2 * math.pi * (k + 0.5) / 24)), Vv(1, 0, 0)) for k in range(24)])
    # port 150 x 600 at TH_N with a short square stub to r 560
    th = E.TH_N; pw, pl = MAN['port'][0], MAN['port'][1]
    xc = E.COLD_PIPE['pts'][0][0]
    stub = local_box(xc - pw / 2 - t, pw + 2 * t, pl + 2 * t, 80.0, ro - 10.0, th)
    hole = local_box(xc - pw / 2, pw, pl, 120.0, ro - 30.0, th)
    s = s.fuse(stub).cut(hole).cut(tube(x0 + 1.0, x1 - t, ro, MAN['rim_ro'] + 0.01).cut(tube(rx0 - 0.01, x1, MAN['rim_ro'] + 0.02, 0.0)))
    # key pockets in the rim
    for ph in [math.radians(a) for a in MAN['pin_deg']]:            # pin sleeves rim -> shell, outer bosses, through holes
        s = s.fuse(radial_cyl(22.0, MAN['rim_ro'] - 2.0, MAN['r_o'] + 2.0, ph)).fuse(radial_cyl(25.0, MAN['r_o'] + MAN['t'] - 2.0, MAN['r_o'] + MAN['t'] + 16.0, ph))
        s = s.cut(radial_cyl(MAN['d_pin'] / 2 + 0.1, MAN['rim_ri'] - 1.0, MAN['r_o'] + MAN['t'] + 17.0, ph))
    return s.removeSplitter()


def frame_pins():
    """8 radial pins dia 24 (A286): from the frame boss (r 302) out through the rim and sleeve to a head on the shell boss"""
    App, Part, Vv = _fc()
    r_top = MAN['r_o'] + MAN['t'] + 16.0
    ps = [radial_cyl(MAN['d_pin'] / 2, 302.0, r_top, math.radians(a)).fuse(radial_cyl(20.0, r_top, r_top + 10.0, math.radians(a)))
          for a in MAN['pin_deg']]
    return Part.makeCompound(ps)


def leaf_seals():
    front = revolve([(876.0, 278.0), (877.2, 278.0), (884.0, 292.0), (885.0, 292.0), (885.0, 299.0), (884.0, 299.0), (876.0, 283.0)])
    rear = revolve([(1100.0, 352.0), (1100.0, 338.0), (1101.9, 326.5), (1101.9, 326.0), (1101.2, 326.0), (1100.6, 337.0), (1100.6, 352.0)])
    return front, rear


# ================================================================================================ collector (EX-420)
def collector():
    App, Part, Vv = _fc()
    b = G['box']; t = T_COL; re = G['r_exit']
    outer = box(b['x0'] - t, b['x1'] + t, b['y0'] - t, b['y1'], b['z0'] - t, b['z1'] + t)
    inner = box(b['x0'], b['x1'], b['y0'], b['y1'] + 1.0, b['z0'], b['z1'])
    s = outer.cut(inner)
    s = s.cut(tube(b['x0'] - t - 1.0, D['x_fw'], re, 0.0)).cut(tube(D['x_rw_exit'], b['x1'] + t + 1.0, re, 0.0))
    s = s.fuse(tube(b['x0'] - t, D['x_fw'], re + t, re))                                        # front well
    s = s.fuse(tube(D['x_rw_exit'] - 2.0, b['x1'] + t, re + t, re))                             # rear well
    s = s.fuse(tube(D['x_fw'] - t, D['x_fw'], re + t, 441.0)).fuse(tube(D['x_fw'] - 20.0, D['x_fw'] - t, 445.0, 441.0))   # front ring + lip
    hc, Rh = D['hub_c'], G['R_hub']
    t0 = math.asin(4.0 / Rh)                                                                       # 4 mm gap to the frame hub end
    gas = arc(hc, Rh, t0, 0.5 * math.pi) + [(D['x_rw_exit'], re)]
    dx = D['x_rw_exit'] - D['x_rw']; dr = re - D['r_rw0']; n = math.hypot(dx, dr)
    back = [(D['x_rw_exit'] + t * dr / n, re), (D['x_rw'] + t * dr / n, D['r_rw0'] - t * dx / n)] + arc(hc, Rh + t, 0.5 * math.pi, t0)[1:]
    cap = revolve(gas + back)
    cap = cap.fuse(tube(1135.0, 1162.0, 192.0, 186.0)).fuse(tube(1154.0, 1168.0, G['r_hub'] - 2.0, 150.0))   # lip in the frame hub, cover flange
    s = s.fuse(cap).fuse(tube(D['x_rw_exit'] - 3.0, D['x_rw_exit'] + 9.0, re + 3.0, re - 3.0))         # weld ring cap -> rear well
    # outlet frame (+y) and centre-line lugs
    fr = box(b['x0'] - t - 50.0, b['x1'] + t + 50.0, b['y1'], b['y1'] + 12.0, b['z0'] - t - 50.0, b['z1'] + t + 50.0).cut(
        box(b['x0'], b['x1'], b['y1'] - 1.0, b['y1'] + 13.0, b['z0'], b['z1']))
    lug1 = box(b['x0'] + 20.0, b['x0'] + 140.0, b['y0'] - t - 120.0, b['y0'] - t, -30.0, 30.0)
    lug2 = box(b['x0'] + 20.0, b['x0'] + 140.0, b['y1'] + 12.0, b['y1'] + 132.0, -30.0, 30.0)
    key = box(0.5 * (b['x0'] + b['x1']) - 60.0, 0.5 * (b['x0'] + b['x1']) + 60.0, -20.0, 20.0, b['z0'] - t - 60.0, b['z0'] - t)
    return fuse([s, fr, lug1, lug2, key])


def hub_cover():
    return tube(1168.0, 1174.0, G['r_hub'] - T_COL - 1.0, 0.0)


def transition():
    b = G['box']; t = T_COL; y0, y1 = b['y1'] + 12.0, E.RECUP['y0']
    o = box(b['x0'] - t, b['x1'] + t, y0, y1, b['z0'] - t, b['z1'] + t)
    i = box(b['x0'], b['x1'], y0 - 1.0, y1 + 1.0, b['z0'], b['z1'])
    fr = [box(b['x0'] - t - 50.0, b['x1'] + t + 50.0, yy, yy + 12.0, b['z0'] - t - 50.0, b['z1'] + t + 50.0).cut(
        box(b['x0'], b['x1'], yy - 1.0, yy + 13.0, b['z0'], b['z1'])) for yy in (y0, y1 - 12.0)]
    return fuse([o.cut(i)] + fr)


# ================================================================================================ pipes
def pipe(pts, od, t, R=None):
    """tube along a polyline: straight runs + spherical corner pieces (the elbows are drawn as forged ball joints; the
    loss calculation uses the real elbow radii)"""
    App, Part, Vv = _fc()
    P = [Vv(*p) for p in pts]
    def body(r):
        parts = []
        for a, b in zip(P, P[1:]):
            d = b - a; parts.append(Part.makeCylinder(r, d.Length, a, d))
        parts += [Part.makeSphere(r, q) for q in P[1:-1]]
        return fuse(parts)
    return body(od / 2).cut(body(od / 2 - t)).removeSplitter()


def cold_pipe():
    App, Part, Vv = _fc()
    od = E.DN[350][0]; pts = E.COLD_PIPE['pts']
    th = E.TH_N; er = Vv(0, math.cos(th), math.sin(th)); et = Vv(0, -math.sin(th), math.cos(th))
    p0 = Vv(*pts[0]) + er * 70.0                                     # after the manifold stub (r 570)
    p1 = Vv(*pts[1])
    # rectangular-to-round transition: loft from the port rectangle (x 1017, r 570) to the pipe circle (x of P1, r 690),
    # shifted forward so the round pipe stays ahead of the collector flange (x 1114)
    pw, pl = MAN['port']
    def rect(c, w, l):
        q = [c + Vv(-w / 2, 0, 0) - et * (l / 2), c + Vv(w / 2, 0, 0) - et * (l / 2), c + Vv(w / 2, 0, 0) + et * (l / 2), c + Vv(-w / 2, 0, 0) + et * (l / 2)]
        return Part.makePolygon(q + [q[0]])
    c2 = Vv(p1.x, 0, 0) + er * 690.0
    lo = Part.makeLoft([rect(p0, pw + 12.0, pl + 12.0), Part.Wire(Part.makeCircle(od / 2, c2, er))], True)
    li = Part.makeLoft([rect(p0 - er * 1.0, pw, pl), Part.Wire(Part.makeCircle(od / 2 - 4.0, c2 + er * 1.0, er))], True)
    trans = lo.cut(li)
    run = pipe([(c2.x, c2.y, c2.z), (p1.x, p1.y, p1.z)] + [tuple(p) for p in pts[2:]], od, 5.0, R=od)
    # BOV tee branch DN125 at x_bov (up)
    xb = E.COLD_PIPE['x_bov']; yb, zb = pts[1][1], pts[1][2]
    br = Part.makeCylinder(E.DN[125][0] / 2, 260.0, Vv(xb, yb, zb), Vv(0, 0, 1)).cut(Part.makeCylinder(E.DN[125][1] / 2, 262.0, Vv(xb, yb, zb - 1), Vv(0, 0, 1)))
    br = br.cut(Part.makeCylinder(od / 2 - 5.0, 1000.0, Vv(xb - 500.0, yb, zb), Vv(1, 0, 0)))
    pbj = Part.makeCylinder(od / 2 + 25.0, 420.0, Vv(-150.0, yb, zb), Vv(1, 0, 0)).cut(Part.makeCylinder(od / 2 - 2.0, 422.0, Vv(-151.0, yb, zb), Vv(1, 0, 0)))
    return fuse([trans, run, br, pbj])


def bov():
    App, Part, Vv = _fc()
    p = E.BOV_LINE['pts']; xb, yb, zb = p[0]
    valve = box(xb - 130.0, xb + 130.0, yb - 110.0, yb + 110.0, zb + 260.0, zb + 520.0).fuse(
        Part.makeCylinder(70.0, 300.0, Vv(xb, yb, zb + 520.0), Vv(0, 0, 1)))                      # body + actuator
    line = pipe([(xb, yb, zb + 520.0)] + [tuple(q) for q in p[1:]], E.DN[200][0], 4.0, R=1.5 * E.DN[200][0])
    return valve.fuse(line).removeSplitter()


def hot_pipe():
    App, Part, Vv = _fc()
    od = E.DN[450][0]; pts = E.HOT_PIPE['pts']
    s = pipe(pts, od, 6.0, R=od)
    x, y, z0 = pts[-2]
    for zz in (1350.0, 1650.0):                                       # gimbal pair in the vertical leg
        s = s.fuse(Part.makeCylinder(od / 2 + 30.0, 150.0, Vv(x, y, zz), Vv(0, 0, 1)).cut(Part.makeCylinder(od / 2 - 3.0, 182.0, Vv(x, y, zz - 1.0), Vv(0, 0, 1))))
    return s.removeSplitter()


def recuperator():
    App, Part, Vv = _fc()
    R_ = E.RECUP; b = G['box']
    s = box(R_['x0'], R_['x1'], R_['y0'], R_['y1'], R_['z0'], R_['z1'])
    s = s.fuse(box(b['x0'] - 60.0, b['x1'] + 60.0, R_['y0'] + 0.5, R_['y0'] + 200.0, b['z0'] - 60.0, b['z1'] + 60.0))      # gas inlet hood
    x, y, z = E.COLD_PIPE['pts'][-1]
    s = s.fuse(Part.makeCylinder(E.DN[350][0] / 2 + 40.0, R_['y0'] - y + 1.0, Vv(x, y, z), Vv(0, 1, 0)))       # nozzle flange
    x, y, z = E.HOT_PIPE['pts'][-1]
    s = s.fuse(Part.makeCylinder(E.DN[450][0] / 2 + 40.0, z - R_['z1'] + 1.0, Vv(x, y, R_['z1'] - 1.0), Vv(0, 0, 1)))
    return s


def econ_stack():
    App, Part, Vv = _fc()
    R_, S = E.RECUP, E.STACK
    s = box(S['econ']['x0'], S['econ']['x1'], R_['y0'], R_['y1'], S['econ']['z0'], S['econ']['z1'])
    s = s.fuse(Part.makeCylinder(E.DN[800][0] / 2, S['z1'] - S['z0'], Vv(S['x'], S['y'], S['z0']), Vv(0, 0, 1)))
    s = s.fuse(Part.makeCylinder(E.DN[800][0] / 2 + 200.0, 2000.0, Vv(S['x'], S['y'], S['z0'] + 600.0), Vv(0, 0, 1)))   # silencer
    return s


# ================================================================================================ build / export
def build_all():
    fs, ss = leaf_seals()
    return {
        'EX-401 Air manifold casing (EN-GJS-400-18LT)': (manifold(), 'EN-GJS-400-18LT', 'casing'),
        'EX-402 Frame pins x7 (A286)': (frame_pins(), 'A286', 'casing'),
        'EX-410 Exhaust frame, 4 struts (1.4848 cast)': (frame(), '1.4848 cast', 'exhaust'),
        'EX-411 Frame heat shield (1.4828)': (heat_shield(), '1.4828', 'exhaust'),
        'EX-412 JB2 support ring + 8 keys (1.4313)': (jb2_ring(), '1.4313', 'bearing'),
        'EX-413 Front leaf seal (Haynes 25)': (fs, 'Haynes 25', 'exhaust'),
        'EX-414 Rear leaf seal (Haynes 25)': (ss, 'Haynes 25', 'exhaust'),
        'EX-420 Exhaust collector (1.4828)': (collector(), '1.4828', 'exhaust'),
        'EX-421 Hub access cover (1.4828)': (hub_cover(), '1.4828', 'exhaust'),
        'EX-430 Exhaust transition + fabric joint': (transition(), '1.4828', 'recup'),
        'EX-440 Cold air pipe DN350 + BOV tee (P265GH)': (cold_pipe(), 'P265GH', 'recup'),
        'EX-441 BOV DN125 + dump line DN200': (bov(), '1.4541', 'recup'),
        'EX-450 Hot air pipe DN450 + gimbal pair (1.4948)': (hot_pipe(), '1.4948', 'recup'),
        'EX-460 Recuperator (bought in)': (recuperator(), 'bought in', 'recup'),
        'EX-470 Economizer + stack DN800 (bought in)': (econ_stack(), 'bought in', 'recup'),
    }


MASS_FIX = {'EX-460 Recuperator (bought in)': 2500.0, 'EX-470 Economizer + stack DN800 (bought in)': 1400.0}
DESC = {
    'EX-401': 'compressor-air manifold: bolted on the scroll-casing rear plate (24 x M16 on r 535), port 150 x 600 to the DN350 '
              'pipe, 7 pin sleeves, rear rim with the rear leaf seal; 3.8 bar, 185 C',
    'EX-402': '7 radial pins dia 24 (45 deg pitch, none under the air port), put in from outside: centre the hot frame, carry '
              'the 25 kN aft air load and the torque, let it grow 3.3 mm radially',
    'EX-410': 'hot one-piece frame: R2 exit -> 8.5 deg cone with 4 cambered hollow struts (top oil in, bottom = drain, -y vent, '
              '+y sensors, buffer air d 4 orifices) -> R120 axial-radial bend; hub carries JB2 on keys; floats on 7 radial pins',
    'EX-411': 'keeps the frame cone hot (uniform with the struts) in the manifold air; ceramic paper behind',
    'EX-412': 'clamps the JB2 cartridge housing; 8 radial keys on 3 mm mica pads in through-slots of the hub (frame slides on '
              'from the rear), retaining ring; JB2 drain / vent bosses behind the ring (x >= 1004)',
    'EX-413': 'C2 rear face <-> frame: 2.9 mm axial closure hot, radial sliding',
    'EX-414': 'manifold rim <-> frame rear flange: radial sliding 3.2 mm',
    'EX-420': 'collector box 0.58 x 1.55 x 1.53 m with front / rear wells, hub cap (R180 bend + rear cone), radial diffuser to r 500, '
              'open +y face; centre-line lugs, bottom key; 100 mm external insulation (not modelled)',
    'EX-421': 'bolted cover in the hub cap, reached from the rear well: JB2 rear inspection without removing the collector',
    'EX-430': 'collector +y face -> recuperator gas inlet hood, 300 mm fabric expansion joint',
    'EX-440': 'manifold port -> rect-round elbow -> DN350 run at y 760 / z -360 -> recuperator air inlet; pressure-balanced joint',
    'EX-441': 'blow-off / start-bleed valve DN125 on the cold pipe; dump DN200 into the economizer inlet plenum (sparger)',
    'EX-450': 'recuperator air outlet (top, rear) -> can nozzle DN450; 3 elbows R/D 1, gimbal pair in the vertical leg; 626 C',
    'EX-460': 'primary-surface counterflow core, eff 0.90, 3.0 MW; gas in at the rear (side hood), out at the front (top); air in '
              'front (side), out rear (top); moved +300 mm in y for the pipe lane',
    'EX-470': 'hot-water economizer 95/75 C (~1 MW) on the recuperator gas outlet, stack DN800 to z 5000 with silencer',
}


def main_cad():
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_exh')
    os.makedirs(out_c, exist_ok=True); os.makedirs(OUT_F, exist_ok=True)
    info = {}
    for name, (s, mat, grp) in build_all().items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(OUT_F, fn))
        bb = s.BoundBox
        m = MASS_FIX.get(name, s.Volume * 1e-9 * RHO.get(mat, 7850))
        info[name] = dict(step=fn, material=mat, group=grp, valid=s.isValid(), solids=len(s.Solids), mass_kg=round(m, 2),
                          desc=DESC[name[:6]], bbox=[round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)])
        print('%-50s %-5s solids %2d  %8.2f kg  x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f' % (name, s.isValid(), len(s.Solids), m,
              bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), flush=True)
    json.dump(dict(frame='rotor frame mm, x = engine axis, z up', geometry=dict(G, derived=D), manifold=MAN, parts=info),
              open(os.path.join(OUT_F, 'parts.json'), 'w'), indent=1)


def check():
    """common volumes of the exhaust parts with the rotor, hot-section and combustor parts (STEP in fusion/)"""
    App, Part, Vv = _fc()
    import glob
    mine = {}
    for name, q in json.load(open(os.path.join(OUT_F, 'parts.json')))['parts'].items():
        s = Part.Shape(); s.read(os.path.join(OUT_F, q['step'])); mine[name] = s
    others = {}
    for d in ('A1000_rotor', 'A1000_hot', 'A1000_comb'):
        for p in sorted(glob.glob(os.path.join(ROOT, 'fusion', d, '*.step'))):
            s = Part.Shape(); s.read(p); others['%s/%s' % (d, os.path.basename(p))] = s
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
            except Exception as e: v = -1.0
            if abs(v) > 1.0: res.append((a, b, v))
    for a, b, v in res: print('INTERFERENCE %-50s %-70s %10.0f mm3' % (a, b, v))
    print('checked %d own parts against %d own + %d others: %d interferences' % (len(mine), len(mine), len(others), len(res)))
    json.dump([dict(a=a, b=b, mm3=v) for a, b, v in res], open(os.path.join(OUT_F, 'interference.json'), 'w'), indent=1)


def update_pkg():
    """fusion/A1000_pkg/pkg.json: the concept placeholders of the exhaust and the recuperator ducting are replaced by the
    EX-4xx parts (step ../A1000_exh/<file>, names, masses)"""
    pp = os.path.join(ROOT, 'fusion', 'A1000_pkg', 'pkg.json')
    pkg = json.load(open(pp)); parts = json.load(open(os.path.join(OUT_F, 'parts.json')))['parts']
    old = ('Exhaust diffuser + 5 struts', 'Exhaust collector', 'Recuperator ducts', 'Recuperator (bought in)')
    keep = [e for e in pkg['parts'] if e['name'] not in old and not e['name'].startswith('EX-4')]
    idx = next((i for i, e in enumerate(pkg['parts']) if e['name'] in old), len(keep))
    new = [dict(name=n, group=q['group'], inst=[0.0], desc=q['desc'], material=q['material'], mass_kg=q['mass_kg'],
                step='../A1000_exh/' + q['step'], dx=0.0) for n, q in parts.items()]
    pkg['parts'] = keep[:idx] + new + keep[idx:]
    json.dump(pkg, open(pp, 'w'), indent=1)
    print('pkg.json: removed %s, added %d EX-4xx parts (%d parts now)' % (', '.join(old), len(new), len(pkg['parts'])))


if '--cad' in sys.argv:
    main_cad()
if '--check' in sys.argv:
    check()
if '--pkg' in sys.argv:
    update_pkg()
