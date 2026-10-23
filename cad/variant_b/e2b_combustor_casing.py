# GR180 variant B (GR180-STEAM) subsystem E2-B - simple-cycle combustor: compact casing, injector carrier, liner, gas manifold.
# Scripted parametric FreeCAD model (Part workbench), ENG frame (mm): x downstream (east), y north, z up; x = 0 tunnel front.
# Same core (v13A), E1 and E3 as variant A; no recuperator, so no collector drum and no C1/C2 ports.  The E3 interduct flange is
# mated exactly as in E2 (E2 face x 115 + 1 mm gasket = E3 face x 116, 16 x M8 on PCD 160).  Variant A (cad/engine/
# combustor_casing.py) is not touched.
# Geometry comes from the design calculation (single source of truth):
#     python3 sim/variant_b/e2b_combustor_calc.py   -> sim/variant_b/e2b_design.json, e2b_results.json
# Run:
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/variant_b/e2b_combustor_casing.py
# Outputs (cad_out/variant_b/E2B/): E2B-xxx_<name>.step per part, E2B_assembly.step (ENG), E2B_assembly_ROOF.step, E2B_assembly.FCStd,
#     E2B_interfaces.json, E2B_checks.json, E2B_section.png, E2B_section_yz.png; docs/bom/variant_b_e2b_bom.csv.
# ROOF placement as variant A (docs/06 sec.1): X = 1.880 + x/1000, Y = 7.850 + y/1000, Z = 0.600 + z/1000 (variant-B roof layout not fixed yet).
import FreeCAD as App, Part, os, json, math, sys, csv
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles', False)
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'sim', 'variant_b', 'e2b_design.json')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.path.join(ROOT, 'cad_out', 'variant_b', 'E2B'); os.makedirs(OUT, exist_ok=True)
GG_ASM = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
G = json.load(open(os.path.join(ROOT, 'sim', 'variant_b', 'e2b_design.json')))
RS = json.load(open(os.path.join(ROOT, 'sim', 'variant_b', 'e2b_results.json')))
ROOF0 = (1880.0, 7850.0, 600.0)
def roof(p): return [round((ROOF0[0] + p[0]) / 1000, 4), round((ROOF0[1] + p[1]) / 1000, 4), round((ROOF0[2] + p[2]) / 1000, 4)]
log = []
def say(*a):
    s = ' '.join(str(v) for v in a); print(s); log.append(s); sys.stdout.flush()

# ---------------------------------------------------------------- helpers (as cad/engine/combustor_casing.py)
def P(x, r, th_deg):
    t = math.radians(th_deg); return V(x, r * math.cos(t), r * math.sin(t))
def rdir(th_deg):
    t = math.radians(th_deg); return V(0, math.cos(t), math.sin(t))
def rv(pts):
    w = Part.makePolygon([V(x, r, 0) for x, r in pts] + [V(pts[0][0], pts[0][1], 0)])
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)
def ring(x0, x1, ri, ro):
    c = Part.makeCylinder(ro, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return c.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), V(1, 0, 0))) if ri > 0 else c
def box(x0, x1, y0, y1, z0, z1): return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def cyl(r, p0, p1):
    d = p1 - p0; return Part.makeCylinder(r, d.Length, p0, d.normalize())
def radial_boss(x, th, r0, r1, rad): return Part.makeCylinder(rad, r1 - r0, P(x, r0, th), rdir(th))
def radial_hole(x, th, r0, r1, rad): return Part.makeCylinder(rad, r1 - r0, P(x, r0, th), rdir(th))
def hexprism(c, n, L_, af):
    n = n.normalize(); a = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0)
    e1 = n.cross(a).normalize(); e2 = n.cross(e1); R = af / math.sqrt(3)
    w = Part.makePolygon([c + e1 * (R * math.cos(math.radians(60 * k))) + e2 * (R * math.sin(math.radians(60 * k))) for k in range(7)])
    return Part.Face(w).extrude(n * L_)
def sector(x0, x1, r0, r1, a_c, w_deg):
    """annular sector solid (window cutter) centred on azimuth a_c (from +y toward +z)"""
    s = ring(x0, x1, r0, r1)
    w = Part.Face(Part.makePolygon([V(x0 - 1, 0, 0), V(x0 - 1, 2 * r1 * math.cos(math.radians(a_c - w_deg / 2)), 2 * r1 * math.sin(math.radians(a_c - w_deg / 2))),
                                    V(x0 - 1, 2 * r1 * math.cos(math.radians(a_c + w_deg / 2)), 2 * r1 * math.sin(math.radians(a_c + w_deg / 2))), V(x0 - 1, 0, 0)]))
    return s.common(w.extrude(V(x1 - x0 + 2, 0, 0)))

PARTS = {}
def add(tag, name, shp, mat, rho, group, qty=1, note=''):
    PARTS[tag] = dict(name=name, shape=shp, mat=mat, rho=rho, group=group, qty=qty, note=note)
    say('  %-8s %-26s valid %-5s solids %2d  vol %10.0f mm3  mass %7.3f kg' % (tag, name, shp.isValid(), len(shp.Solids), shp.Volume, shp.Volume * rho))
RHO = dict(S1_4404=7.98e-6, HX=8.22e-6, IN625=8.44e-6, SS316L=7.98e-6, ins=0.30e-6, mica=2.0e-6, FKM=1.9e-6, A286=7.94e-6, misc=3.0e-6)

XB0, XB1 = G['x_bh'], G['x_bh_back']; XF0, XF1 = G['x_hot_flange']; XM0, XM1 = G['x_mid_A']
RCI, TC = G['r_case_i'], G['t_case']; RCO = RCI + TC; RFO, PCD_M = G['r_flange_o'], G['pcd_mid']
XR0, XR1 = G['x_rear_ring']
NI, RI = G['n_inj'], G['r_inj']; A_INJ = [G['inj_a0_deg'] + 360.0 * k / NI for k in range(NI)]
xd, xdh = G['x_dome'], G['x_dome_hot']; INJ = G['injector']; HOLES = G['holes']
MID_A = [G['mid_bolt_a0_deg'] + 360.0 / G['n_mid_bolts'] * k for k in range(G['n_mid_bolts'])]
say('E2-B build: %d injectors r %.1f, casing r %.1f..%.1f x %.1f..%.1f, carrier x %.1f..%.1f, E3 face x %.1f' %
    (NI, RI, RCI, RCO, G['x_casing_front'], XR1, XB0, XB1, G['x_e3_face']))

# =====================================================================================================================
# E2B-101 front casing (1.4404): front ring (as E2) + 3 mm cone over the diffuser + shell r 72/75 + 6 mm flange, bosses
xf = G['x_casing_front']; xc0, xc1 = G['x_cone']
inner = [(xf, G['r_lip_i']), (G['x_ring_lip'] + 3.0, G['r_lip_i']), (G['x_ring_lip'] + 3.0, G['r_ring_bore']), (xc0, G['r_ring_bore']), (xc1, RCI), (XM0, RCI)]
outer = [(XM0, RCO), (xc1 + 1.2, RCO), (xc0 + 1.2, G['r_front_ring_o']), (xf, G['r_front_ring_o'])]
fcase = rv(inner + outer)
fcase = fcase.fuse(ring(XM0, XM1, RCI, RFO))
fcase = fcase.cut(ring(G['oring_x'] - 1.2, G['oring_x'] + 1.2, G['r_ring_bore'] - 0.5, G['r_ring_bore'] + 2.05))
for a in MID_A:
    fcase = fcase.cut(Part.makeCylinder(3.4, 9.01, P(XM1 - 9.0, PCD_M / 2, a), V(1, 0, 0)))          # blind M8 x 9 from the rear face
BOSS_F = [('gas', G['x_gas_boss'], G['gas_entry_deg'], 11.0, 14.0, 6.6), ('bleed', G['x_bleed'], G['a_bleed'], 6.0, 12.0, 2.5),
          ('p2', G['x_p2'], G['a_p2'], 6.0, 12.0, 1.5), ('t2', G['x_t2'], G['a_t2'], 6.0, 12.0, 1.6)]
fcase = fcase.fuse([radial_boss(x, a, RCO - 1.5, RCO + h, rb) for _, x, a, rb, h, _ in BOSS_F])
for _, x, a, rb, h, bo in BOSS_F:
    fcase = fcase.cut(radial_hole(x, a, RCI - 2, RCO + h + 1, bo))
fcase = fcase.removeSplitter()
add('E2B-101', 'Front_Casing', fcase, '1.4404 (316L): turned front ring + spun 3 mm cone + rolled shell + 6 mm flange, TIG, 5-axis finish', RHO['S1_4404'], 'case')

# E2B-103 front foot (engine axial fixed point) under the front-casing shell
fx0, fx1 = G['x_foot']; zs = G['z_skid']; fw = G['foot_w']
foot = box(fx0, fx1, -fw / 2, fw / 2, zs + 10.0, -40.0).cut(Part.makeCylinder(RCO, 400, V(-200, 0, 0), V(1, 0, 0)))
base = box(fx0 - 32.0, fx1 + 32.0, -fw / 2, fw / 2, zs, zs + 10.0)
xc_ = 0.5 * (fx0 + fx1)
for sy in (-1, 1):
    for sx in (-1, 1):
        base = base.cut(box(xc_ + sx * 24 - 6.5, xc_ + sx * 24 + 6.5, sy * 100 - 7, sy * 100 + 7, zs - 1, zs + 11))
gus = []
for sy in (-1, 1):
    w = Part.makePolygon([V(fx0, sy * 95, zs + 10), V(fx0 - 30, sy * 95, zs + 10), V(fx0, sy * 95, zs + 150), V(fx0, sy * 95, zs + 10)])
    gus.append(Part.Face(w).extrude(V(0, -sy * 8, 0)))
foot = foot.fuse([base] + gus).removeSplitter()
add('E2B-103', 'Front_Foot_FixedPoint', foot, '1.4404 plate 8 mm + base 10 mm, 2 gussets, TIG to E2B-101; 4 x M12 to the skid', RHO['S1_4404'], 'support')

# =====================================================================================================================
# E2B-110 injector carrier plate (1.4404, 6 mm): clamped rim, 7 air windows, hub sleeve, 7 stem bores, 3 core-retainer fingers
cp = ring(XB0, XB1, G['r_bh_bore'], RFO).fuse(ring(XB1, G['x_bh_hub_end'], G['r_bh_bore'], G['r_bh_hub_o']))
for a in MID_A:
    cp = cp.cut(Part.makeCylinder(4.5, 10, P(XB0 - 1, PCD_M / 2, a), V(1, 0, 0)))
for a in A_INJ:
    cp = cp.cut(Part.makeCylinder(G['d_stem'] / 2 + 0.2, 10, P(XB0 - 1, RI, a), V(1, 0, 0)))
win = [sector(XB0 - 1, XB1 + 1, G['window_r'][0], G['window_r'][1], a + 180.0 / NI, G['window_deg']) for a in A_INJ]
cp = cp.cut(Part.makeCompound(win))
x_ret0 = G['x_diff_back'] + G['retainer_gap']
cp = cp.fuse([Part.makeCylinder(G['retainer_d'] / 2, XB0 - x_ret0 + 0.5, P(x_ret0, G['retainer_r'], a), V(1, 0, 0)) for a in G['retainer_a_deg']])
cp = cp.removeSplitter()
add('E2B-110', 'Injector_Carrier_Plate', cp, '1.4404 plate 8 mm, 5-axis machined (7 windows, 40 % of the annulus open), 3 IN625 retainer pins',
    RHO['S1_4404'], 'case')

# E2B-115 gas manifold (316L): torus 12x1, 7 stems 8x1, feed 16x1.5 to the front-casing boss
xm, rm, dm, tm = G['x_manifold'], G['r_manifold'], G['d_manifold'], G['t_manifold']
ds, ts = G['d_stem'], G['t_stem']
tor_o = Part.makeTorus(rm, dm / 2, V(xm, 0, 0), V(1, 0, 0)); tor_i = Part.makeTorus(rm, dm / 2 - tm, V(xm, 0, 0), V(1, 0, 0))
x_stem1 = INJ['x_backplate'][0] + 1.0
st_o = [Part.makeCylinder(ds / 2, x_stem1 - xm, P(xm, RI, a), V(1, 0, 0)) for a in A_INJ]
st_i = [Part.makeCylinder(ds / 2 - ts, x_stem1 - xm + 1, P(xm, RI, a), V(1, 0, 0)) for a in A_INJ]
pf0 = P(xm, rm, G['gas_entry_deg']); pfk = P(xm, G['r_feed_knee'], G['gas_entry_deg']); pf1 = P(G['x_gas_boss'], RCO + 2.0, G['gas_entry_deg'])
nf = (pf1 - pfk).normalize(); rfo, rfi = G['d_feed'] / 2, G['d_feed'] / 2 - G['t_feed']
feed_o = [cyl(rfo, pf0, pfk), Part.makeSphere(rfo, pfk), cyl(rfo, pfk, pf1)]; feed_i = [cyl(rfi, pf0, pfk), Part.makeSphere(rfi, pfk), cyl(rfi, pfk, pf1 + nf)]
man = tor_o.fuse(st_o + feed_o).cut(Part.makeCompound([tor_i] + feed_i + st_i))
man = man.cut(Part.makeCylinder(RCO + 60, 60, V(-30, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(RCI, 60, V(-30, 0, 0), V(1, 0, 0))))
add('E2B-115', 'Gas_Manifold', man, '316L torus 12x1 + 7 stems 8x1 (M10x1 ends) + feed 12x1 with one bend, orbital TIG, He-leak tested', RHO['SS316L'], 'gas')

# E2B-120 injector heads x7 (SLM IN625)
def injector(a):
    c = P(0, RI, a); ax = V(1, 0, 0)
    def at(x): return V(x, c.y, c.z)
    xu0, xu1 = INJ['x_union'], INJ['x_backplate'][0]; xb0, xb1 = INJ['x_backplate']; xv1 = xb1 + INJ['slot_h']; xcup1 = xdh + 0.2
    r_sw = INJ['r_sw']
    nut = hexprism(at(xu0 + 0.1), ax, xu1 - xu0 - 0.1, 16.0).cut(Part.makeCylinder(ds / 2 + 0.05, 20, at(xu0 - 1), ax))
    back = Part.makeCylinder(r_sw, xb1 - xb0, at(xb0), ax)
    cb = Part.makeCylinder(INJ['cb_d'] / 2, xv1 + 2.0 - xb1, at(xb1), ax)
    front = Part.makeCylinder(r_sw, 1.0, at(xv1), ax).cut(Part.makeCylinder(INJ['cup_id'] / 2, 4, at(xv1 - 1), ax))
    cup = Part.makeCylinder(INJ['cup_id'] / 2 + 1.0, xcup1 - xv1, at(xv1), ax).cut(Part.makeCylinder(INJ['cup_id'] / 2, xcup1 - xv1 + 2, at(xv1 - 1), ax))
    vanes = []
    for k in range(INJ['n_vanes']):
        v = Part.makeBox(r_sw - INJ['r_vane_exit'], 0.8, xv1 - xb1, V(INJ['r_vane_exit'], -0.4, 0))
        v.rotate(V(INJ['r_vane_exit'], 0, 0), V(0, 0, 1), -INJ['vane_angle']); v.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / INJ['n_vanes'])
        vanes.append(v)
    vc = Part.makeCompound(vanes).common(Part.makeCylinder(r_sw, xv1 - xb1, V(0, 0, 0), V(0, 0, 1)))
    vc.Placement = App.Placement(V(xb1, c.y, c.z), App.Rotation(V(0, 0, 1), V(1, 0, 0)))
    head = back.fuse([cb, front, cup, vc]).cut(Part.makeCylinder(ds / 2 - ts, 4.0, at(xb0 - 0.5), ax))
    for k in range(INJ['n_gas']):
        th = 30.0 + 360.0 / INJ['n_gas'] * k
        head = head.cut(Part.makeCylinder(INJ['d_gas'] / 2, 4.0, at(xb1 + 0.6 * INJ['slot_h']), V(0, math.cos(math.radians(th)), math.sin(math.radians(th)))))
    return nut.fuse(head)
add('E2B-120', 'Injector_Heads_x7', Part.makeCompound([injector(a) for a in A_INJ]), 'IN625 SLM + HIP + solution HT; swirler/cup/thread machined; flow-tested',
    RHO['IN625'], 'gas', qty=NI, note='7 identical heads in one STEP')

# =====================================================================================================================
# E2B-130 liner (Hastelloy X 1.0): geometry as variant A, holes re-sized for the cold inlet
tl = G['t_liner']; rlo_i, rlo_o = G['r_lo_i'], G['r_lo_o']; rli_o, rli_i = G['r_li_o'], G['r_li_i']
x_cyl1, x_cone1, x_lo1 = G['x_lo_cyl_end'], G['x_lo_cone_end'], G['x_lo_end']; rsl = G['r_lo_sleeve_i']
outer_l = rv([(xd, rlo_i), (x_cyl1, rlo_i), (x_cone1, rsl), (x_lo1, rsl), (x_lo1, rsl + tl), (x_cone1, rsl + tl), (x_cyl1, rlo_o), (xd, rlo_o)])
dome = ring(xd, xdh, rli_o - 0.01, rlo_i + 0.01)
inner_l = ring(G['x_li_front'], G['x_li_end'], rli_i, rli_o)
lips = []
for xr in HOLES['outer_film']['x'][:2]:
    lips.append(ring(xr - 1.6, xr - 0.8, rlo_i - 2.3, rlo_i + 0.01)); lips.append(ring(xr - 1.6, xr + 4.0, rlo_i - 2.3, rlo_i - 1.5))
for xr in HOLES['inner_film']['x']:
    lips.append(ring(xr - 1.6, xr - 0.8, rli_o - 0.01, rli_o + 2.3)); lips.append(ring(xr - 1.6, xr + 4.0, rli_o + 1.5, rli_o + 2.3))
pads = [radial_boss(G['x_liner_pins'], a, rlo_o - 0.3, rlo_o + 3.0, 6.0) for a in G['a_liner_pins']]
liner = outer_l.fuse([dome, inner_l] + lips + pads)
H = []
r_cup_hole = INJ['cup_id'] / 2 + 1.0 + 0.2
for a in A_INJ:
    H.append(Part.makeCylinder(r_cup_hole, 4, P(xd - 1, RI, a), V(1, 0, 0)))
    for k in range(8):
        th = math.radians(22.5 + 45 * k); yy = RI + 11.0 * math.cos(th); zz = 11.0 * math.sin(th)
        p = V(xd - 1, yy * math.cos(math.radians(a)) - zz * math.sin(math.radians(a)), yy * math.sin(math.radians(a)) + zz * math.cos(math.radians(a)))
        H.append(Part.makeCylinder(HOLES['dome_cool']['d'] / 2, 4, p, V(1, 0, 0)))
nrow = HOLES['outer_film']['n'] // len(HOLES['outer_film']['x'])
for i, xr in enumerate(HOLES['outer_film']['x']):
    rr = rlo_i if xr <= x_cyl1 else rlo_i + (rsl - rlo_i) * (xr - x_cyl1) / (x_cone1 - x_cyl1)
    for k in range(nrow): H.append(radial_hole(xr, 360.0 * (k + 0.5 * i) / nrow, rr - 0.5, rr + 2.0, HOLES['outer_film']['d'] / 2))
for k in range(HOLES['secondary']['n']):
    H.append(radial_hole(HOLES['secondary']['x'][0], A_INJ[0] + 360.0 * k / HOLES['secondary']['n'], rlo_i - 0.5, rlo_o + 1.0, HOLES['secondary']['d'] / 2))
nd = HOLES['dilution']['n'] // len(HOLES['dilution']['x'])
for i, xr in enumerate(HOLES['dilution']['x']):
    for k in range(nd): H.append(radial_hole(xr, A_INJ[0] + 360.0 * (k + 0.5 + 0.5 * i) / nd, rlo_i - 0.5, rlo_o + 1.0, HOLES['dilution']['d'] / 2))
ni = HOLES['inner_film']['n'] // len(HOLES['inner_film']['x'])
for i, xr in enumerate(HOLES['inner_film']['x']):
    for k in range(ni): H.append(radial_hole(xr, 360.0 * (k + 0.5 * i) / ni, rli_i - 1.0, rli_o + 0.5, HOLES['inner_film']['d'] / 2))
for x, a in ((G['x_igniter'], G['a_igniter']), (G['x_uv'], G['a_uv'])):
    H.append(radial_hole(x, a, rlo_i - 2.5, rlo_o + 1.0, 4.0))
for a in G['a_liner_pins']:
    H.append(radial_hole(G['x_liner_pins'], a, rlo_o + 0.5, rlo_o + 4.0, 3.1))
liner = liner.cut(Part.makeCompound(H))
add('E2B-130', 'Liner_Assembly', liner, 'Hastelloy X 2.4665 1.0 mm (same tooling as variant A), laser-drilled holes re-sized for the 165 C inlet', RHO['HX'], 'hot',
    note='holes: dome 7 cups Ø%.1f + %d effusion Ø%.2f, outer film %d x Ø%.2f, secondary %d x Ø%.1f, dilution %d x Ø%.1f, inner film %d x Ø%.2f' %
    (2 * r_cup_hole, HOLES['dome_cool']['n'], HOLES['dome_cool']['d'], HOLES['outer_film']['n'], HOLES['outer_film']['d'], HOLES['secondary']['n'],
     HOLES['secondary']['d'], HOLES['dilution']['n'], HOLES['dilution']['d'], HOLES['inner_film']['n'], HOLES['inner_film']['d']))
pins = [radial_boss(G['x_liner_pins'], a, rlo_o + 0.6, RCO + 9.0, 3.0).fuse(radial_boss(G['x_liner_pins'], a, RCO + 9.0, RCO + 13.0, 6.0)) for a in G['a_liner_pins']]
add('E2B-131', 'Liner_Pins_x3', Part.makeCompound(pins), 'IN625 bar Ø6, head Ø12', RHO['IN625'], 'hot', qty=3)
xs0, xs1 = G['x_shield']
add('E2B-132', 'Tunnel_HeatShield', ring(xs0, xs1, G['r_shield_i'], G['r_shield_i'] + G['t_shield']), 'IN625 0.3 mm, electropolished, dimple spacers', RHO['IN625'], 'hot')

# =====================================================================================================================
# E2B-150 rear pressure casing (1.4404): flange, shell r 72/75, solid rear ring = E2/E3 flange (as variant A, bore r 38.45)
hfl = ring(XF0, XF1, RCI, RFO)
for a in MID_A:
    hfl = hfl.cut(Part.makeCylinder(4.5, 10, P(XF0 - 1, PCD_M / 2, a), V(1, 0, 0)))
rring = ring(XR0, XR1, G['r_rear_bore'], G['r_e3_flange_o'])
rring = rring.cut(ring(XR1 - G['e3_spigot_depth'], XR1 + 1, G['e3_groove_ri'], G['e3_spigot_d'] / 2))
rring = rring.cut(ring(G['seal_groove_x'][0], G['seal_groove_x'][1], G['r_rear_bore'] - 0.5, G['r_seal_groove']))
for k in range(G['n_e3_bolts']):
    rring = rring.cut(Part.makeCylinder(3.4, 14.01, P(XR1 - 14.0, G['pcd_e3'] / 2, G['e3_bolt_a0_deg'] + 360.0 / G['n_e3_bolts'] * k), V(1, 0, 0)))
BOSS_R = [('igniter', G['x_igniter'], G['a_igniter'], 13.0, RCO + 12.0, 6.0), ('uv', G['x_uv'], G['a_uv'], 15.0, RCO + 14.0, 7.0),
          ('p3', G['x_p3'], G['a_p3'], 7.0, RCO + 10.0, 1.5), ('tw1', G['x_twall'], G['a_twall'][0], 7.0, RCO + 10.0, 0.6),
          ('tw2', G['x_twall'], G['a_twall'][1], 7.0, RCO + 10.0, 0.6)] + \
         [('pin%d' % i, G['x_liner_pins'], a, 8.0, RCO + 9.0, 3.05) for i, a in enumerate(G['a_liner_pins'])]
case = hfl.fuse([ring(XF1 - 0.5, XR0 + 0.5, RCI, RCO), rring] + [radial_boss(x, a, RCO - 1.5, rt, rb) for _, x, a, rb, rt, _ in BOSS_R])
for _, x, a, rb, rt, bo in BOSS_R:
    case = case.cut(radial_hole(x, a, RCI - 2, rt + 1, bo))
case = case.removeSplitter()
add('E2B-150', 'Rear_Pressure_Casing', case, '1.4404: flange + rolled 3 mm shell + machined rear ring (E2/E3 flange as variant A), TIG; hydro 4.3 barg',
    RHO['S1_4404'], 'case')

# insulation (removable, microporous 25 mm in 0.5 mm 1.4301 cladding) on the rear casing, behind the mid-flange nuts
ti = G['insulation']['rear']
ins = ring(XF1 + 10.0, XR0, RCO, RCO + ti)
for _, x, a, rb, rt, bo in BOSS_R: ins = ins.cut(radial_boss(x, a, RCO - 1, RCO + ti + 2, rb + 2.0))
add('E2B-160', 'Insulation_RearCasing', ins, 'microporous 25 mm (Promat MICROTHERM) in 0.5 mm 1.4301 cladding, 2 half shells', RHO['ins'] * 1.3, 'ins')

# seals, gaskets, fasteners
gr = G['gasket_mid_r']
add('E2B-170', 'MidFlange_Gaskets_x2', Part.makeCompound([ring(XM1, XB0, gr[0], gr[1]), ring(XB1, XF0, gr[0], gr[1])]),
    'KLINGER Milam PSS 1 mm / Thermiculite 815, ID %.0f OD %.0f' % (2 * gr[0], 2 * gr[1]), RHO['mica'], 'seal', qty=2)
add('E2B-171', 'RearSeal_PistonRing', ring(G['seal_groove_x'][0] + 0.05, G['seal_groove_x'][1] - 0.05, G['r_ngv_o'] + 0.10, G['r_seal_groove'] - 0.1),
    'IN718 split piston ring, step gap (seals on the GG NGV shroud OD 72.7)', RHO['IN625'], 'seal')
add('E2B-172', 'Front_Oring', ring(G['oring_x'] - 0.9, G['oring_x'] + 0.9, G['r_core'] + 0.08, G['r_core'] + 1.85), 'FKM O-ring 107.32 x 1.78, 200 C',
    RHO['FKM'], 'seal')
studs = []
for a in MID_A:
    c = P(0, PCD_M / 2, a)
    studs += [Part.makeCylinder(4.0, 43.5 - (XM1 - 8.5), V(XM1 - 8.5, c.y, c.z), V(1, 0, 0)), Part.makeCylinder(7.5, 1.6, V(XF1 + 0.01, c.y, c.z), V(1, 0, 0)),
              hexprism(V(XF1 + 1.61, c.y, c.z), V(1, 0, 0), 6.5, 13.0).cut(Part.makeCylinder(4.0, 8, V(XF1 + 1, c.y, c.z), V(1, 0, 0)))]
add('E2B-173', 'MidFlange_Studs_Nuts_x16', Part.makeCompound(studs), 'M8 studs A4-80 L 35 + nuts + washers (casing ~290 C)', RHO['A286'], 'fastener', qty=16)

# instruments / igniter (buy, envelope models)
def probe(x, a, r0, segs):
    s, r = [], r0
    for L_, rad in segs:
        s.append(Part.makeCylinder(rad, L_, P(x, r, a), rdir(a))); r += L_
    return Part.makeCompound(s)
inst = {
 'E2B-501': ('IGN-630_Igniter_Plug', probe(G['x_igniter'], G['a_igniter'], rlo_o + 0.5, [(RCO + 12.0 - rlo_o - 0.5, 5.5), (12.0, 10.4), (40.0, 8.0), (30.0, 9.0)]),
             'surface-gap igniter plug M14x1.25 (as variant A)', 'Bosch industrial (DE) / Brahma (IT)'),
 'E2B-502': ('BE-631_UV_Sight_Sensor', probe(G['x_uv'], G['a_uv'], rlo_o + 0.5, [(RCO + 14.0 - rlo_o - 0.5, 6.0), (25.0, 14.0), (20.0, 12.0), (95.0, 22.0)]),
             'UV flame sensor Durag D-LX 100 UV on a sight tube Ø12 + quartz window', 'Durag (DE)'),
 'E2B-503': ('PT-522_P3_Tap', probe(G['x_p3'], G['a_p3'], RCO + 10.0, [(15.0, 6.0), (40.0, 3.0)]), 'P3 tap 1/8" to PT-522', 'Voss (DE)'),
 'E2B-505': ('TE-507A_Liner_Wall_TC', probe(G['x_twall'], G['a_twall'][0], rlo_o + 0.2, [(RCO + 10.0 - rlo_o - 0.2, 0.5), (18.0, 5.0), (50.0, 3.0)]),
             'type K MI Ø1.0, tip brazed to the outer liner PZ (commissioning)', 'Roessel Messtechnik (DE)'),
 'E2B-506': ('TE-507B_Liner_Wall_TC', probe(G['x_twall'], G['a_twall'][1], rlo_o + 0.2, [(RCO + 10.0 - rlo_o - 0.2, 0.5), (18.0, 5.0), (50.0, 3.0)]),
             'type K MI Ø1.0, tip brazed to the outer liner PZ (commissioning)', 'Roessel Messtechnik (DE)'),
 'E2B-507': ('PT-521_P2_Tap', probe(G['x_p2'], G['a_p2'], RCO + 12.0, [(15.0, 6.0), (40.0, 3.0)]), 'P2 tap + 300 mm sense line to PT-521', 'Voss (DE)'),
 'E2B-508': ('Gas_Inlet_Fitting_L12', probe(G['x_gas_boss'], G['gas_entry_deg'], RCO + 14.0, [(26.0, 11.0), (40.0, 6.0)]), 'DIN 2353 L12 bulkhead union 316', 'Voss (DE) / Stauff (DE)'),
 'E2B-509': ('Buffer_Air_Fitting_L6', probe(G['x_bleed'], G['a_bleed'], RCO + 12.0, [(18.0, 7.0), (40.0, 3.0)]), 'DIN 2353 L6 -> E3-606 -> E3 B1 seal', 'Voss (DE)'),
 'E2B-510': ('TE-502_T2_TC', probe(G['x_t2'], G['a_t2'], RCI - 12.0, [(RCO + 12.0 - RCI + 12.0, 1.5), (18.0, 7.0), (60.0, 4.0)]),
             'T2 = combustor inlet: type K MI Ø3, immersion 12 mm (TE-502 moves here from the E4 header in variant B)', 'Roessel Messtechnik (DE)'),
}
for tg, (nm, shp, desc, sup) in inst.items():
    add(tg, nm, shp, desc, RHO['misc'], 'sensor', note=sup)

# =====================================================================================================================
# checks vs the core and internal
def overlap(a, b):
    if not a.BoundBox.intersect(b.BoundBox): return 0.0
    try: return a.common(b).Volume
    except Exception: return -1.0
KEPT = ('Intake', 'IntakeOuter', 'Compressor', 'Diffuser', 'Shaft', 'ShaftTunnel', 'NGV', 'Turbine', 'TurbineNut', 'NoseCone', 'Starter',
        'RPM_Sensor', 'RPM_Magnet', 'Balance_Slug', 'FrontBearing_608_hybrid_8x22x7', 'RearBearing_608_hybrid_8x22x7', 'FrontBearing_Oring',
        'WaveSpring_22x16_free3_0_inst2_8')
GG = {}
for n in KEPT:
    f = os.path.join(GG_ASM, n + '.step')
    if os.path.exists(f): s = Part.Shape(); s.read(f); GG[n] = s
f = os.path.join(GG_ASM, 'Fasteners.step')
if os.path.exists(f):
    s = Part.Shape(); s.read(f); GG['Fasteners_front'] = Part.makeCompound([x for x in s.Solids if x.BoundBox.XMax < 0])
chk = dict(core_kept={}, internal=[], clearances={})
for n, s in GG.items():
    hits = {t: round(overlap(p['shape'], s), 3) for t, p in PARTS.items()}
    hits = {k: v for k, v in hits.items() if abs(v) > 1e-3}
    chk['core_kept'][n] = hits
    say('core %-14s vs E2-B: %s' % (n, hits if hits else 'no interference'))
JOINTS = {('E2B-101', 'E2B-103'), ('E2B-101', 'E2B-115'), ('E2B-101', 'E2B-172'), ('E2B-101', 'E2B-173'), ('E2B-110', 'E2B-173'), ('E2B-150', 'E2B-173'),
          ('E2B-101', 'E2B-170'), ('E2B-110', 'E2B-170'), ('E2B-150', 'E2B-170'), ('E2B-110', 'E2B-115'), ('E2B-110', 'E2B-120'), ('E2B-115', 'E2B-120'),
          ('E2B-130', 'E2B-120'), ('E2B-130', 'E2B-131'), ('E2B-150', 'E2B-131'), ('E2B-150', 'E2B-171'), ('E2B-110', 'E2B-130'), ('E2B-150', 'E2B-160')}
tags = sorted(PARTS)
for i, a in enumerate(tags):
    for b in tags[i + 1:]:
        v = overlap(PARTS[a]['shape'], PARTS[b]['shape'])
        if v > 1.0 or v < 0:
            chk['internal'].append(dict(a=a, b=b, vol_mm3=round(v, 2), expected=((a, b) in JOINTS or (b, a) in JOINTS or 'sensor' in (PARTS[a]['group'], PARTS[b]['group']))))
bad = [r for r in chk['internal'] if not r['expected']]
say('E2-B internal overlaps > 1 mm3: %d (unexpected %d) %s' % (len(chk['internal']), len(bad), bad[:10]))
def dist(a, b):
    try: return a.distToShape(b)[0]
    except Exception: return -1
for a, b, what in (('E2B-130', 'NGV', 'outer sleeve / NGV shroud (slip)'), ('E2B-150', 'NGV', 'rear bore / NGV rib'), ('E2B-171', 'NGV', 'piston ring / NGV shroud'),
                   ('E2B-110', 'Diffuser', 'retainer fingers / diffuser back plate'), ('E2B-115', 'Diffuser', 'manifold / diffuser'),
                   ('E2B-101', 'Diffuser', 'front-casing cone / diffuser'), ('E2B-130', 'ShaftTunnel', 'inner liner / tunnel')):
    if b in GG: chk['clearances'][what] = round(dist(PARTS[a]['shape'], GG[b]), 3)
for a, b, what in (('E2B-120', 'E2B-110', 'swirler head / carrier hub'), ('E2B-120', 'E2B-130', 'cup / dome hole'), ('E2B-115', 'E2B-110', 'manifold / carrier plate (contact by design)')):
    chk['clearances'][what] = round(dist(PARTS[a]['shape'], PARTS[b]['shape']), 3)
say('clearances (mm): ' + ', '.join('%s %.2f' % kv for kv in chk['clearances'].items()))
json.dump(chk, open(os.path.join(OUT, 'E2B_checks.json'), 'w'), indent=1)

# exports
for t, p in PARTS.items():
    p['shape'].exportStep(os.path.join(OUT, '%s_%s.step' % (t, p['name'])))
asm = Part.makeCompound([p['shape'] for p in PARTS.values()])
asm.exportStep(os.path.join(OUT, 'E2B_assembly.step'))
asm_r = asm.copy(); asm_r.translate(V(*ROOF0)); asm_r.exportStep(os.path.join(OUT, 'E2B_assembly_ROOF.step'))
doc = App.newDocument('E2B_Combustor_Casing')
for t, p in PARTS.items():
    o = doc.addObject('Part::Feature', t.replace('-', '_')); o.Shape = p['shape']; o.Label = '%s %s' % (t, p['name'])
doc.recompute(); doc.saveAs(os.path.join(OUT, 'E2B_assembly.FCStd'))
bb = asm.BoundBox
say('assembly bbox x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f mm' % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))

# interfaces
dp_ = RS['design_point']; pr_ = RS['pressure']
def itf(name, pos, direction, size, counterpart, **kw):
    d = dict(name=name, ENG_mm=[round(v, 2) for v in pos], ROOF_m=roof(pos), direction=direction, size=size, counterpart=counterpart); d.update(kw); return d
IF = [itf('IF-E2E3 rear flange (E2-B side)', [G['x_e3_face'], 0, 0], [1, 0, 0],
          'identical to variant A: E2-B face x %.1f + 1.0 mm gasket (E3-605) = E3 face x %.1f; OD %.0f, PCD %.0f, %d x M8 blind tapped (depth 14), phase %.2f deg; '
          'spigot groove r %.1f..%.1f x %.1f..%.1f; piston ring E2B-171; rear bore r %.2f (A: 38.10, colder casing)' %
          (G['x_e3_face'], G['x_e3_face'] + G['t_e3_gasket'], 2 * G['r_e3_flange_o'], G['pcd_e3'], G['n_e3_bolts'], G['e3_bolt_a0_deg'], G['e3_groove_ri'],
           G['e3_spigot_d'] / 2, XR1 - G['e3_spigot_depth'], XR1, G['r_rear_bore']), 'E3-101 front flange (unchanged)', calc=RS['casing']['flange_E2E3']),
      itf('Core front (intake-outer)', [G['x_ring_lip'], 0, 0], [-1, 0, 0], 'front ring bore r 53.55 over the intake-outer OD 107 (x -11.33..-4.85), stop lip r 51.5, O-ring x -8 (as variant A)',
          'core v13A IntakeOuter; 3 retainer fingers on E2B-110 to the diffuser back plate (x 2.0, 0.3 mm)'),
      itf('Gas inlet (fuel)', [G['x_gas_boss'], *list(P(0, RCO + 14.0, G['gas_entry_deg']))[1:]], list(rdir(G['gas_entry_deg'])),
          'DIN 2353 L12 (M18x1.5) on the front-casing boss; %.2f g/s natural gas (%.1f Nm3/h), manifold %.2f barg' % (dp_['mf'] * 1e3, RS['gas']['Nm3_h'], RS['gas']['P_manifold_barg']),
          'variant-B gas train (larger than variant A: ~31 m3/h)'),
      itf('Compressor-delivery bleed (E3 B1 buffer air)', [G['x_bleed'], *list(P(0, RCO + 12.0, G['a_bleed']))[1:]], list(rdir(G['a_bleed'])), 'M12x1.5, DIN 2353 L6',
          'E3 buffer air via E3-606')]
for x_, a_, nm, txt in ((G['x_igniter'], G['a_igniter'], 'IGN-630 igniter plug', 'M14x1.25'), (G['x_uv'], G['a_uv'], 'BE-631 UV flame sensor', 'sight tube Ø12 + quartz window'),
                        (G['x_p3'], G['a_p3'], 'PT-522 P3 tap', 'M10x1'), (G['x_twall'], G['a_twall'][0], 'TE-507A liner wall TC', 'M6x0.75'),
                        (G['x_twall'], G['a_twall'][1], 'TE-507B liner wall TC', 'M6x0.75'), (G['x_p2'], G['a_p2'], 'PT-521 P2 tap', 'M10x1'),
                        (G['x_t2'], G['a_t2'], 'TE-502 T2 TC', 'M8x1, MI Ø3')):
    IF.append(itf('Sensor ' + nm, [x_, *list(P(0, RCO + 12.0, a_))[1:]], list(rdir(a_)), txt, 'B2 / SR1 per docs/electrical/02_io_list'))
IF.append(itf('Front foot (engine axial fixed point)', [0.5 * (fx0 + fx1), 0, zs], [0, 0, -1], 'base %.0f x %.0f x 10, 4 x M12 in axial slots' % (fx1 - fx0 + 64, fw),
              'variant-B skid rail (ENG z -400, as variant A)'))
info = dict(subsystem='E2-B simple-cycle combustor (variant B, GR180-STEAM)', frame='ENG mm; ROOF = (1.880 + x/1000, 7.850 + y/1000, 0.600 + z/1000) m (as variant A)',
            source='cad/variant_b/e2b_combustor_casing.py + sim/variant_b/e2b_combustor_calc.py',
            envelope_ENG_mm=[[round(bb.XMin, 1), round(bb.YMin, 1), round(bb.ZMin, 1)], [round(bb.XMax, 1), round(bb.YMax, 1), round(bb.ZMax, 1)]],
            design_point=dict(T_in_C=dp_['T2_C'], P_combustor_bar=pr_['P_combustor'], dp_total_pct=pr_['dp_total_pct'], TIT_C=dp_['TIT_C'], fuel_g_s=dp_['mf'] * 1e3,
                              T_exit_with_cycle_eta_C=RS['combustor']['T_exit_with_cycle_eta_C'], pattern_factor=RS['combustor']['pattern_factor'],
                              liner_Tw_max_C=dict(outer=RS['liner_thermal']['outer_Tw_max_C'], inner=RS['liner_thermal']['inner_Tw_max_C'])),
            replaced_core_parts=['Casing', 'CC_FrontCap', 'CC_Inner', 'CC_Outer', 'CC_RearCone', 'CC_Vaporisers', 'GasBulkhead', 'Igniter', 'SupplyLines',
                                 'SupplySeals', 'Exhaust (by E3)', 'EGT_Probe', 'Fasteners x 112-119.5'], interfaces=IF)
json.dump(info, open(os.path.join(OUT, 'E2B_interfaces.json'), 'w'), indent=1, ensure_ascii=False)
say('interfaces -> %s (%d entries)' % (os.path.join(OUT, 'E2B_interfaces.json'), len(IF)))

# sections
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    COL = dict(case=(0.2, 0.45, 0.85), hot=(0.85, 0.40, 0.15), gas=(0.1, 0.6, 0.2), support=(0.5, 0.5, 0.5), ins=(0.85, 0.80, 0.55), seal=(0.6, 0.2, 0.6),
               fastener=(0.3, 0.3, 0.3), sensor=(0.9, 0.1, 0.1))
    fig, ax = plt.subplots(figsize=(14, 8))
    def draw(axx, shp, col, plane, lw=0.8):
        try: sec = shp.slice(*plane)
        except Exception: return
        for w in sec:
            for e in w.Edges:
                pts = e.discretize(24)
                if plane[0].z: axx.plot([p.x for p in pts], [p.y for p in pts], color=col, lw=lw)
                else: axx.plot([p.y for p in pts], [p.z for p in pts], color=col, lw=lw)
    for n in ('Intake', 'IntakeOuter', 'Compressor', 'Diffuser', 'ShaftTunnel', 'Shaft', 'NGV', 'Turbine', 'TurbineNut', 'NoseCone'):
        if n in GG: draw(ax, GG[n], (0.6, 0.6, 0.6), (V(0, 0, 1), 0.0), 0.5)
    for t, p in PARTS.items(): draw(ax, p['shape'], COL.get(p['group'], 'k'), (V(0, 0, 1), 0.0))
    ax.set_aspect('equal'); ax.grid(alpha=0.3); ax.set_xlabel('ENG x [mm]'); ax.set_ylabel('ENG y [mm]')
    ax.set_title('GR180 variant B  E2-B simple-cycle combustor, section z = 0 (core in grey)')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'E2B_section.png'), dpi=120)
    fig2, axs = plt.subplots(1, 2, figsize=(14, 7))
    for axx, xc2, ttl in ((axs[0], 24.0, 'x = 24 (injector carrier plate, 7 air windows)'), (axs[1], 62.1, 'x = 62.1 (secondary holes)')):
        for t, p in PARTS.items(): draw(axx, p['shape'], COL.get(p['group'], 'k'), (V(1, 0, 0), xc2))
        axx.set_aspect('equal'); axx.grid(alpha=0.3); axx.set_title(ttl); axx.set_xlabel('ENG y [mm]'); axx.set_ylabel('ENG z [mm]')
    fig2.tight_layout(); fig2.savefig(os.path.join(OUT, 'E2B_section_yz.png'), dpi=110)
    say('sections -> E2B_section.png, E2B_section_yz.png')
except Exception as ex:
    say('section plot skipped: %s' % ex)

# BOM (docs/06 sec.5 schema)
MB = {
 'E2B-101': ('make', 'turned front ring + spun cone + rolled shell + flange, TIG, 5-axis finish; blind M8 x 9', 'local precision CNC + TIG; sheet Outokumpu (FI) / Aperam (BE)', 'cold 165 C; hydro 4.3 barg'),
 'E2B-103': ('make', 'laser-cut plates + TIG; slots milled', 'local', 'axial fixed point of the engine'),
 'E2B-110': ('make', '5-axis CNC from 1.4404 plate 8 mm; 3 IN625 pins', 'local precision CNC', 'flatness 0.05 both faces'),
 'E2B-115': ('make', 'tube bending + orbital TIG, stems threaded M10x1, He leak test', 'local; tube Sandvik (SE) 316L', 'pressure test 6 barg'),
 'E2B-120': ('make', 'SLM IN625 + HIP + solution HT; swirler/cup/thread machined; flow test each head', 'iDesign3D (IR) SLM IN625; powder Sandvik Osprey (SE)', 'matched set +-2 %'),
 'E2B-130': ('make', 'as variant A (same tooling), holes per sim/variant_b/e2b_design.json', 'sheet VDM Metals (DE) Nicrofer 4722Co', 'inspect 8,000 h'),
 'E2B-131': ('make', 'turned IN625 bar', 'local', ''),
 'E2B-132': ('make', 'IN625 0.3 mm rolled, electropolished', 'foil VDM Metals (DE)', ''),
 'E2B-150': ('make', 'flange + rolled shell + machined rear ring, TIG; hydro 4.3 barg', 'local; ring forging Boehler (AT)', 'PED Art. 4(3) SEP'),
 'E2B-160': ('buy', 'microporous half shells in cladding', 'Promat MICROTHERM (BE/DE)', 'skin ~54 C'),
 'E2B-170': ('buy', 'KLINGER Milam PSS 1 mm / Thermiculite 815', 'Klinger (AT) / Flexitallic (UK)', 'replace at each opening'),
 'E2B-171': ('make', 'IN718 ring, split, step gap', 'local; bar VDM Metals (DE)', ''),
 'E2B-172': ('buy', 'FKM O-ring 107.32 x 1.78', 'Freudenberg (DE) / Trelleborg (SE)', ''),
 'E2B-173': ('buy', 'M8 studs A4-80 + nuts + washers', 'Bossard (CH) / Wuerth (DE)', 'VDI 2230'),
}
rows = [['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes']]
for t, p in PARTS.items():
    m = p['shape'].Volume * p['rho']; q = p['qty']; bb_ = p['shape'].BoundBox
    size = '%.0f x %.0f x %.0f mm (bbox)' % (bb_.XLength, bb_.YLength, bb_.ZLength); mf = 'cad_out/variant_b/E2B/%s_%s.step' % (t, p['name'])
    if p['group'] == 'sensor':
        rows.append([t, p['name'].replace('_', ' '), 1, 'buy', p['mat'], size, p['note'], 0.15, mf, 'envelope model; instrument in the electrical I/O list']); continue
    mk, spec, sup, note = MB.get(t, ('make', p['mat'], 'local', ''))
    rows.append([t, p['name'].replace('_', ' '), q, mk + ': ' + spec, p['mat'], size, sup, round(m / q if q > 1 else m, 3), mf, (p['note'] + '; ' if p['note'] else '') + note])
EXTRA = [['E2B-601', 'Liner pin cap nuts M10x1 + lock wire', 3, 'buy', 'IN718 / 1.4980', 'M10x1', 'Boellhoff (DE)', 0.01, '', ''],
         ['E2B-602', 'Instrument boss fittings and seal rings', 9, 'buy', '316 / Cu', 'DIN 2353 / DIN 7603', 'Voss (DE) / Stauff (DE)', 0.02, '', ''],
         ['E2B-603', 'Quartz window + purge adapter for BE-631', 1, 'buy', 'fused silica, 1.4404', '1"', 'Durag (DE)', 0.2, '', ''],
         ['E2B-604', 'Flexible gas hose DN10 316 braided, L 500, DIN 2353 L12 ends', 1, 'buy', '1.4404 corrugated + braid, EN ISO 10380', 'PN 16', 'Witzenmann (DE) / BOA (DE)', 0.5, '', ''],
         ['E2B-605', 'Hydro / He leak test + PMI (services)', 1, 'buy', 'EN 13445-5 practice', '4.3 barg hydro', 'TUV Austria / TUV Nord (local)', 0, '', ''],
         ['E2B-606', 'Injector flow-bench calibration (set of 7)', 1, 'buy', 'Cd and swirl check', '', 'university lab / local', 0, '', '']]
rows += EXTRA
with open(os.path.join(ROOT, 'docs', 'bom', 'variant_b_e2b_bom.csv'), 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(rows)
tot = sum(p['shape'].Volume * p['rho'] for p in PARTS.values()) + sum(r[7] * r[2] for r in EXTRA)
say('BOM -> docs/bom/variant_b_e2b_bom.csv (%d rows); E2-B total mass %.1f kg' % (len(rows) - 1, tot))
open(os.path.join(OUT, 'E2B_build.log'), 'w').write('\n'.join(log) + '\n')
