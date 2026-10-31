"""AURORA-1000 engine piping (docs/08 sec. 19): oil supply / drain / vent, buffer and cooling air, fuel hoses and the gas
valve block, combustor drains, the oil reservoir in the base frame, pipe supports.
Sizes from sim/engine/a1000_lube_piping.py (sim/engine/fea/a1000_lube_piping.json); end points from the bearing CAD
(cad/engine/a1000_rotor.py: front bearing housing FB-1 / FB-2, JB2 cartridge), the combustor CAD (CB-341 drain bosses,
CB-370 drops) and the exhaust frame of phase 2 (cad/engine/a1000_exhaust.py: strut services oil top, drain bottom, vent
-y; the BOV DN125 line EX-441 and the JB2 cooling air through the strut roots are phase 2's).

Layout rules:
  service side   all oil, fuel and drain lines run on the -y side and under the engine; +y is left to the recuperator
                 ducts (phase 2). Nothing crosses the vertical lift path of an upper casing half (|y| < 662 above the axis)
                 or the axial path of the exhaust frame except the lines that end on it (disconnected first).
  disconnects    at every module boundary, so modules come apart without cutting: inlet-plenum wall bulkhead unions
                 (FBH oil, vent, buffer air), DN65 flange under the plenum (FBH drain), flexible hose at each exhaust-strut
                 exit (JB2 oil, drain, vent), unions at the fuel drops
                 (z 900) and at the bulkhead on the head cover, unions at the CB-341 drain bosses
  flexibility    the hot end (exhaust frame, ~3 mm axial / radial growth) and the can head (+14 mm) are reached through
                 braided hoses; cold lines are rigid with clamps <= 1.5 m (tube) /
                 2.5 m (pipe)
  slope          drains and vents fall continuously to the reservoir (>= 1:50; the drains reach 10-35 %)
  standards      tubes 1.4404 seamless (EN 10216-5) with ISO 8434-1 24 deg cone fittings (series L); pipes DN25-DN125 1.4404
                 10S with EN 1092-1 PN16 flanges; hoses ISO 10380 stainless braided (PTFE liner for oil, gas: EN 14800 type)
Frame: rotor frame mm, x = engine axis from the gearbox coupling face, z up. Run (FreeCAD):
  freecadcmd -c "import sys; sys.argv=['a1000_piping.py','--cad']; exec(open('cad/engine/a1000_piping.py').read())"
  -> cad_out/engine/A1000_pipe/*.step, fusion/A1000_pipe/*.step + parts.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LP = json.load(open(os.path.join(ROOT, 'sim', 'engine', 'fea', 'a1000_lube_piping.json')))
OD = dict(DN15=21.3, DN25=33.7, DN32=42.4, DN50=60.3, DN65=76.1, DN125=139.7, DN250=273.0)

# end points (from the CAD scripts; checked by cad/engine/a1000_assembly_check.py)
FBH_IN = dict(JB1=(65.0, -148.0, -45.0), TB=(126.0, -148.0, -45.0))      # FB-2 inlet boss faces (-y)
FBH_DRAIN = (126.0, 0.0, -189.0)                                        # FB-2 DN65 flange face
FBH_VENT = (132.0, 0.0, 154.0)                                          # FB-1 DN25 boss top
FBH_BUF = (148.15, -101.8, -101.8)                                      # FB-2 buffer-air boss face (225 deg)
PLENUM_Y, PLENUM_Z = 400.0, 400.0                                       # inlet plenum walls (+-y, floor)
JB2_X = dict(oil=955.25, drain=1005.0, vent=1005.0)                     # JB2 ports (cad/engine/a1000_rotor.py jb2_cartridge)
STRUT = dict(oil=90.0, drain=270.0, vent=180.0)                         # strut services (exhaust frame EX-410, phase 2)
R_STRUT_OUT = 545.0                                                     # hose ends, clear of the frame manifold shell (r 500-510)
RES = dict(x=(-540.0, 200.0), y=(-940.0, 790.0), z=(-985.0, -715.0))    # reservoir between the base-frame beams (clear of the
                                                                        # recuperator support frame at y >= 800)
Z_DECK = -700.0
JUNCTION = (40.0, 160.0, -650.0, -450.0)                                # oil distribution block: x0, x1, y, z
STAGE1_TAP = (360.0, 0.0, 500.0)                                        # DN25 boss on the compressor casing top (phase 7)
GVB = (1000.0, 1300.0, -1200.0, -900.0, -700.0, -300.0)                 # gas valve block envelope (bought in)
DRAIN_POT = (780.0, -900.0, -640.0)


def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def polar(x, r, deg):
    a = math.radians(deg); return (x, r * math.cos(a), r * math.sin(a))


def route(pts, d):
    """solid rod of OD d along a polyline (pipe envelope), spheres at the corners"""
    App, Part, V = _fc()
    pieces = []
    for a, b in zip(pts[:-1], pts[1:]):
        va, vb = V(*a), V(*b); L = (vb - va).Length
        if L < 1e-6: continue
        pieces.append(Part.makeCylinder(d / 2, L, va, (vb - va).normalize()))
    pieces += [Part.makeSphere(d / 2, V(*p)) for p in pts[1:-1]]
    return pieces[0].multiFuse(pieces[1:]) if len(pieces) > 1 else pieces[0]


def fitting(p, q, d, L=30.0):
    """union / flange body (d) of length L at p, along the direction to q"""
    App, Part, V = _fc()
    vp, vq = V(*p), V(*q); u = (vq - vp).normalize()
    return Part.makeCylinder(d / 2, L, vp - u * (L / 2), u)


def hose(pts, d):
    """braided hose (shown as a rod of its OD) with end fittings"""
    s = route(pts, d)
    return s.fuse(fitting(pts[0], pts[1], d + 10.0, 40.0)).fuse(fitting(pts[-1], pts[-2], d + 10.0, 40.0))


def box(x0, x1, y0, y1, z0, z1):
    App, Part, V = _fc()
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def support(p, d, z_base=Z_DECK, side=None):
    """pipe support: clamp ring round the pipe at p and a post down to z_base (or across to y side=(y, axis 'y'))"""
    App, Part, V = _fc()
    x, y, z = p
    if side is None:
        post = box(x - 20, x + 20, y - 20, y + 20, z_base, z - d / 2 - 2)
    else:
        y1 = side
        post = box(x - 20, x + 20, min(y, y1), max(y, y1), z - 20, z + 20)
    return post


def lines():
    """{name: (shape, material, group, description)}"""
    App, Part, V = _fc()
    b = LP['bearings']; out = {}
    od_h = LP['oil_header']['tube_OD']
    x0j, x1j, yj, zj = JUNCTION
    # ---- oil supply: lube module -> junction block -> JB1, TB (through the plenum wall) and JB2 (to the 198 deg strut)
    hdr = route([(-150.0, yj, zj), (x0j, yj, zj)], od_h).fuse(box(x0j, x1j, yj - 25, yj + 25, zj - 25, zj + 25))
    out['PL-01 Oil supply header + distribution block (tube %d x 2)' % od_h] = (hdr, '1.4404', 'pipe',
        'lube module -> distribution block under the inlet plenum; PCV on the module holds %.1f bar(g) here' % LP['lube_module']['header_barg'])
    for tag, key in (('PL-02', 'JB1'), ('PL-03', 'TB')):
        od = b[key]['supply_tube_OD']; xi, yi, zi = FBH_IN[key]
        pts = [(xi, yj, zj + 25), (xi, yj, zi), (xi, -PLENUM_Y - 40, zi), (xi, yi, zi)]
        s = route(pts, od).fuse(fitting((xi, -PLENUM_Y, zi), (xi, 0, zi), od + 14, 24.0)).fuse(fitting((xi, yi, zi), (xi, yi - 1, zi), od + 10, 20.0))
        out['%s Oil to %s (tube %d x %.1f, orifice %s mm)' % (tag, key, od, 1.5, b[key]['orifice_mm'])] = (s, '1.4404', 'pipe',
            'bulkhead union in the plenum wall (y -400) = module disconnect; 24 deg cone union on the FB-2 boss')
    od = b['JB2']['supply_tube_OD']; pe = polar(JB2_X['oil'], R_STRUT_OUT + 45.0, STRUT['oil']); xr = 990.0   # behind the CB-340
                                                                        # ribs; clear of the manifold top (z <= 560)
    s = route([(x1j, yj, zj), (xr, yj, zj), (xr, -740.0, zj), (xr, -740.0, 640.0), (xr, 0.0, 640.0), (xr, 0.0, pe[2] + 40.0)], od)
    s = s.fuse(hose([(xr, 0.0, pe[2] + 40.0), (pe[0], pe[1], pe[2] + 40.0), pe], od + 8.0))   # DN15 through the strut: phase 2
    out['PL-04 Oil to JB2 (tube %d x 1.5, hose at the top strut)' % od] = (s, '1.4404', 'pipe',
        'along the -y side outside the scroll casing, over the frame behind the scroll-casing ribs; braided hose at the strut exit; tube through the strut')
    # ---- drains: FBH DN65 straight down into the reservoir; JB2 DN50 from the bottom strut, falling ~11 % to the reservoir
    d65 = OD['DN65']; xd, yd, zd = FBH_DRAIN
    s = route([(xd, yd, zd), (xd, yd, RES['z'][1] + 5)], d65).fuse(fitting((xd, yd, -PLENUM_Z - 10), (xd, yd, 0), 185.0, 18.0))
    out['PL-05 FBH drain DN65 (to the reservoir)'] = (s, '1.4404', 'pipe', 'flange DN65 PN16 under the plenum floor = disconnect; vertical, no trap')
    d50 = OD['DN50']; pe = polar(JB2_X['drain'], R_STRUT_OUT, 270.0)
    s = hose([pe, (pe[0], 0.0, -640.0)], d50 + 8).fuse(route([(pe[0], 0.0, -640.0), (260.0, 0.0, -680.0), (170.0, 150.0, -684.0),
                                                            (170.0, 150.0, RES['z'][1] + 1)], d50))   # the strut cavity is the drain;
                                                                        # 24 mm under the combustor drains (z -585)
    out['PL-06 JB2 drain DN50 (hose at the bottom strut, 11 % fall)'] = (s, '1.4404', 'pipe',
        'PTFE-lined braided hose DN50 at the strut exit, then rigid under the scroll casing (60 mm below it) to the reservoir')
    # ---- vents: FBH DN25 from the top of FB-1 through the +y plenum wall straight down; JB2 DN32 from the 126 deg strut
    d25 = OD['DN25']; xv, yv, zv = FBH_VENT
    s = route([(xv, yv, zv), (xv, yv, zv + 40), (xv, PLENUM_Y + 70, zv + 40), (xv, PLENUM_Y + 70, RES['z'][1] + 5)], d25)
    s = s.fuse(fitting((xv, PLENUM_Y, zv + 40), (xv, 0, zv + 40), d25 + 14, 24.0))
    out['PL-07 FBH vent DN25 (to the reservoir)'] = (s, '1.4404', 'pipe', 'union on FB-1 (opened to lift the upper half) and at the plenum wall; falls to the tank')
    d32 = OD['DN32']; pe = polar(JB2_X['vent'], R_STRUT_OUT, STRUT['vent']); xv2 = 1030.0; yv = -730.0   # 80 mm off PL-04
    s = hose([pe, (xv2, -640.0, pe[2])], d32 + 8).fuse(route([(xv2, -640.0, pe[2]), (xv2, yv, pe[2]), (xv2, yv, -600.0),
                                                              (220.0, yv, -675.0), (180.0, yv, -680.0), (180.0, yv, RES['z'][1] + 1)], d32))
    out['PL-08 JB2 vent DN32 (hose at the -y strut, falls to the reservoir)'] = (s, '1.4404', 'pipe',
        'high point at the strut exit, then a continuous fall; the reservoir carries the mist separator')
    # ---- buffer air: stage-1 tap -> isolation valve + orifice -> TB rear seal (in under the plenum floor); the JB2 shield /
    # buffer air comes from the frame manifold through the strut roots (phase 2)
    a = LP['air_lines']; od_b = a['TB_buffer']['tube_OD']
    t = STAGE1_TAP; y_air = -720.0; x_dn, z_lo = 100.0, -540.0       # down outside the plenum, in under its floor
    pa = (FBH_BUF[0], -330.0, -330.0)                                 # on the boss axis (225 deg), inside the plenum
    s = route([t, (t[0], 0.0, t[2] + 60), (t[0], y_air, t[2] + 60), (x_dn, y_air, t[2] + 60), (x_dn, y_air, z_lo),
               (FBH_BUF[0], -330.0, z_lo), pa, FBH_BUF], od_b)
    s = s.fuse(fitting((FBH_BUF[0], -330.0, -PLENUM_Z), (FBH_BUF[0], -330.0, 0), od_b + 14, 24.0))
    s = s.fuse(box(t[0] - 40, t[0] + 40, y_air - 40, y_air + 40, t[2] + 20, t[2] + 100))         # valve + orifice block
    out['PL-09 Buffer air from stage 1 to the TB rear seal (tube %d)' % od_b] = (s, '1.4404', 'pipe',
        'tap DN25 on the return channel (phase 7 boss), isolation valve + orifice, %.0f g/s; union under the plenum floor'
        % a['TB_buffer']['m_g_s'])
    # ---- fuel: gas valve block (bought in) on the skid, 4 braided hoses up to the drops of CB-370 at z 900
    f = LP['fuel']['circuits']; x_can = 665.0
    s = box(GVB[0], GVB[1], GVB[2], GVB[3], GVB[4], GVB[5])
    s = s.fuse(route([(0.5 * (GVB[0] + GVB[1]), -1250.0, -500.0), (0.5 * (GVB[0] + GVB[1]), GVB[2], -500.0)], OD['DN50']))
    for k, (c, dx) in enumerate((('P', -60.0), ('A', -20.0), ('B1', 20.0), ('B2', 60.0))):
        od = f[c]['tube_OD']; top = (x_can + dx, -460.0, 858.0)          # union of the CB-370 drop at z 880-900
        bot = (GVB[0] + 60.0 + 60.0 * k, GVB[3] - 40.0, GVB[5])
        y_out = -770.0 - 10.0 * k                                        # outside the scroll-casing split flanges (y -708)
        s = s.fuse(hose([top, (top[0], y_out, top[2]), (top[0], y_out, -100.0), (bot[0], bot[1], bot[2] + 150.0), bot], od + 6.0))
    out['PL-10 Fuel hoses P / A / B1 / B2 + gas valve block (bought in)'] = (s, '1.4404 / bought in', 'pipe',
        'valve block: 2 shut-off valves + vent (double block and bleed), 4 staging valves; hoses take the can growth (+14 mm); unions at z 900')
    # ---- combustor drains DN15: scroll (sleeve through the CB-341 bottom) and the air side -> drain pot on the deck
    d15 = 18.0; pot = DRAIN_POT
    s = Part.makeCylinder(75.0, 200.0, V(pot[0], pot[1], Z_DECK), V(0, 0, 1))
    for xs in (700.0, 860.0):
        s = s.fuse(route([(xs, 0.0, -576.0), (xs, 0.0, -585.0), (xs, pot[1], -585.0), (pot[0], pot[1], -585.0), (pot[0], pot[1], Z_DECK + 200)], d15))
    out['PL-12 Combustor drains DN15 + drain pot'] = (s, '1.4404', 'pipe',
        'normally open, air-operated valves close at light-off (fail open); closed drain pot with a level switch')
    # ---- gearbox oil feed from the module, reservoir in the base frame, supports
    s = route([(-300.0, -450.0, zj + 100), (-300.0, -420.0, zj + 100), (-600.0, -420.0, zj + 100)], od_h)   # from the module's +y face
    out['PL-13 Gearbox oil feed (tube %d x 2)' % od_h] = (s, '1.4404', 'pipe', 'to the gearbox jets (bought-in gearbox interface); the gearbox drains straight down into the reservoir')
    r = RES
    res = box(r['x'][0], r['x'][1], r['y'][0], r['y'][1], r['z'][0], r['z'][1]).cut(
        box(r['x'][0] + 6, r['x'][1] - 6, r['y'][0] + 6, r['y'][1] - 6, r['z'][0] + 6, r['z'][1] - 6))
    out['LO-100 Oil reservoir in the base frame (%d l)' % LP['reservoir']['volume_l']] = (res, '1.4301', 'aux',
        'between the base-frame beams under the coupling and the gearbox; returns enter through the deck; heater, level, mist separator on the module')
    sup = []                                                          # posts to the base-frame deck under the long runs
    zv = lambda x0, z0, x1, z1, x: z0 + (z1 - z0) * (x - x0) / (x1 - x0)
    for p, dd in (((-50.0, yj, zj), od_h), ((500.0, yj, zj), b['JB2']['supply_tube_OD']),
                  ((600.0, 0.0, zv(JB2_X['drain'], -640.0, 260.0, -680.0, 600.0)), d50),
                  ((600.0, -730.0, zv(1030.0, -600.0, 220.0, -675.0, 600.0)), d32)):
        sup.append(support(p, dd))
    out['PL-90 Pipe supports (posts to the base frame)'] = (Part.makeCompound(sup), 'S235', 'pipe', 'clamps <= 1.5 m (tube) / 2.5 m (pipe) apart')
    return out


def main_cad():
    App, Part, V = _fc()
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_pipe'); out_f = os.path.join(ROOT, 'fusion', 'A1000_pipe')
    os.makedirs(out_c, exist_ok=True); os.makedirs(out_f, exist_ok=True)
    info = {}
    for name, (s, mat, grp, desc) in lines().items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(out_f, fn))
        bb = s.BoundBox
        info[name] = dict(step=fn, material=mat, group=grp, desc=desc, valid=s.isValid(), solids=len(s.Solids),
                          bbox=[round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)])
        print('%-62s %-5s solids %2d  x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f' % (name, s.isValid(), len(s.Solids), bb.XMin, bb.XMax,
                                                                               bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), flush=True)
    json.dump(dict(frame='rotor frame mm, z up', parts=info), open(os.path.join(out_f, 'parts.json'), 'w'), indent=1)


if '--cad' in sys.argv:
    main_cad()
