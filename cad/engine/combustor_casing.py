# GR180-CCHP subsystem E2 - recuperated annular combustor + pressure casing + compressor-exit collector.
# Scripted parametric FreeCAD model (Part workbench), ENG frame (mm): x downstream (east), y north, z up; x = 0 tunnel front.
# Geometry comes from the design calculation (single source of truth):
#     python3 sim/engine/e2_combustor_calc.py      -> sim/engine/e2_design.json, sim/engine/e2_results.json
# Run:
#     LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/engine/combustor_casing.py
# Outputs (cad_out/engine/E2/): E2-xxx_<name>.step per part, E2_assembly.step (ENG), E2_assembly_ROOF.step (ROOF, mm),
#     E2_assembly.FCStd, E2_interfaces.json, E2_checks.json (interference vs the v13A core + E2 internal), E2_section.png,
#     docs/bom/engine_E2_bom.csv (BOM with CAD masses).
# ROOF placement: X = 1.880 + x/1000, Y = 7.850 + y/1000, Z = 0.600 + z/1000 (m)  (docs/06_master_design.md sec.1).
import FreeCAD as App, Part, os, json, math, sys, csv
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles', False)
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'sim', 'engine', 'e2_design.json')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'E2'); os.makedirs(OUT, exist_ok=True)
GG_ASM = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
G = json.load(open(os.path.join(ROOT, 'sim', 'engine', 'e2_design.json')))
RS = json.load(open(os.path.join(ROOT, 'sim', 'engine', 'e2_results.json')))
ROOF0 = (1880.0, 7850.0, 600.0)                    # ENG origin in ROOF (mm)
def roof(p): return [round((ROOF0[0] + p[0]) / 1000, 4), round((ROOF0[1] + p[1]) / 1000, 4), round((ROOF0[2] + p[2]) / 1000, 4)]
log = []
def say(*a):
    s = ' '.join(str(v) for v in a); print(s); log.append(s); sys.stdout.flush()

# ---------------------------------------------------------------- helpers
def P(x, r, th_deg):                                   # polar point about the x axis; theta from +y toward +z
    t = math.radians(th_deg); return V(x, r * math.cos(t), r * math.sin(t))
def rdir(th_deg):
    t = math.radians(th_deg); return V(0, math.cos(t), math.sin(t))
def rv(pts):                                           # revolve a closed (x, r) polygon about x
    w = Part.makePolygon([V(x, r, 0) for x, r in pts] + [V(pts[0][0], pts[0][1], 0)])
    return Part.Face(w).revolve(V(0, 0, 0), V(1, 0, 0), 360)
def ring(x0, x1, ri, ro):
    c = Part.makeCylinder(ro, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
    return c.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), V(1, 0, 0))) if ri > 0 else c
def cylx(r, x0, x1): return Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), V(1, 0, 0))
def box(x0, x1, y0, y1, z0, z1): return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def cyl(r, p0, p1):
    d = p1 - p0; return Part.makeCylinder(r, d.Length, p0, d.normalize())
def tube(ro, ri, p0, p1):
    n = (p1 - p0).normalize(); return cyl(ro, p0, p1).cut(cyl(ri, p0 - n, p1 + n))
def radial_boss(x, th, r0, r1, rad, bore=0.0, r_bore0=None):
    b = Part.makeCylinder(rad, r1 - r0, P(x, r0, th), rdir(th))
    if bore > 0:
        rb = r_bore0 if r_bore0 is not None else r0 - 1
        b = b.cut(Part.makeCylinder(bore, r1 - rb + 2, P(x, rb, th), rdir(th)))
    return b
def radial_hole(x, th, r0, r1, rad): return Part.makeCylinder(rad, r1 - r0, P(x, r0, th), rdir(th))
def hexprism(c, n, L_, af, rot_ref=None):
    """hexagon prism, axis n through c, across flats af, length L_"""
    n = n.normalize(); a = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0)
    e1 = n.cross(a).normalize(); e2 = n.cross(e1); R = af / math.sqrt(3)
    w = Part.makePolygon([c + e1 * (R * math.cos(math.radians(60 * k))) + e2 * (R * math.sin(math.radians(60 * k))) for k in range(7)])
    return Part.Face(w).extrude(n * L_)
def rect_wire(y, x0, x1, z0, z1):
    return Part.makePolygon([V(x0, y, z0), V(x1, y, z0), V(x1, y, z1), V(x0, y, z1), V(x0, y, z0)])
def circ_wire(y, xc, zc, r, n=48):
    return Part.Wire(Part.makeCircle(r, V(xc, y, zc), V(0, 1, 0)))
def plate_flange(c, n, D, bore, K, nb, dh, b, a0=None):
    """EN 1092-1 style flange disc: centre c (back face), normal n (towards the face), OD D, bore, bolt circle K."""
    f = Part.makeCylinder(D / 2, b, c, n).cut(Part.makeCylinder(bore / 2, b + 2, c - n, n))
    a = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0)
    e1 = n.cross(a).normalize(); e2 = n.cross(e1)
    a0 = 0.5 if a0 is None else a0
    for k in range(nb):
        ph = 2 * math.pi * (k + a0) / nb
        f = f.cut(Part.makeCylinder(dh / 2, b + 2, c - n + e1 * (K / 2 * math.cos(ph)) + e2 * (K / 2 * math.sin(ph)), n))
    return f

PARTS = {}            # tag -> dict(name, shape, material, rho [kg/mm3], group, qty)
def add(tag, name, shp, mat, rho, group, qty=1, note=''):
    PARTS[tag] = dict(name=name, shape=shp, mat=mat, rho=rho, group=group, qty=qty, note=note)
    say('  %-7s %-26s valid %-5s solids %2d  vol %10.0f mm3  mass %7.3f kg' % (tag, name, shp.isValid(), len(shp.Solids), shp.Volume, shp.Volume * rho))
RHO = dict(S1_4404=7.98e-6, S1_4948=7.90e-6, HX=8.22e-6, IN625=8.44e-6, SS316L=7.98e-6, S355=7.85e-6, ins=0.30e-6, mica=2.0e-6,
           FKM=1.9e-6, A286=7.94e-6, misc=3.0e-6)

# ---------------------------------------------------------------- key numbers from e2_design.json
XB0, XB1 = G['x_bh'], G['x_bh_back']                       # bulkhead 21..27
XF0, XF1 = G['x_hot_flange']                               # hot flange 28..34
XM0, XM1 = G['x_mid_A']                                    # drum flange 10..20
RDI, TD = G['r_drum_i'], G['t_drum']; RDO = RDI + TD       # drum 118 / 120.5
RCI, TC = G['r_case_i'], G['t_case']; RCO = RCI + TC       # casing 85 / 88
RFO, PCD_M = G['r_flange_o'], G['pcd_mid']
XR0, XR1 = G['x_rear_ring']                                # rear ring 100..115
C1, C2 = G['C1'], G['C2']
NI, RI = G['n_inj'], G['r_inj']
A_INJ = [G['inj_a0_deg'] + 360.0 * k / NI for k in range(NI)]
xd, xdh = G['x_dome'], G['x_dome_hot']
INJ = G['injector']; HOLES = G['holes']
say('E2 build: %d injectors r %.1f, drum r %.1f..%.1f x %.1f..%.1f, casing r %.1f..%.1f x %.1f..%.1f, E3 face x %.1f' %
    (NI, RI, RDI, RDO, G['x_drum_front'], XM1, RCI, RCO, XF0, XR1, G['x_e3_face']))

# =====================================================================================================================
# E2-101 compressor-delivery collector drum (1.4404): machined front ring + front wall + rolled shell + 10 mm flange + bosses
xdf = G['x_drum_front']
front_ring = rv([(xdf, G['r_lip_i']), (G['x_ring_lip'] + 3.0, G['r_lip_i']), (G['x_ring_lip'] + 3.0, G['r_ring_bore']),
                 (G['x_io_end'], G['r_ring_bore']), (G['x_io_end'], G['r_front_ring_o']), (xdf, G['r_front_ring_o'])])
og = ring(G['oring_x'] - 1.2, G['oring_x'] + 1.2, G['r_ring_bore'] - 0.5, G['r_ring_bore'] + 2.05)        # O-ring groove (bore)
front_ring = front_ring.cut(og)
front_wall = ring(xdf, xdf + G['t_front_wall'], G['r_front_ring_o'] - 0.5, RDO)
shell = ring(xdf + G['t_front_wall'] - 0.5, XM0, RDI, RDO)
dflange = ring(XM0, XM1, RDI, RFO)
for k in range(G['n_mid_bolts']):                          # 16 blind M8 tapped holes from the rear face (tap drill 6.8, depth 9)
    dflange = dflange.cut(Part.makeCylinder(3.4, 9.0 + 0.01, P(XM1 - 9.0, PCD_M / 2, G['mid_bolt_a0_deg'] + 360.0 / G['n_mid_bolts'] * k), V(1, 0, 0)))
# bosses: gas feed (x 0, south), E3 buffer-air bleed, P2 tap (PT-521)
BOSS_DRUM = [('gas', G['x_gas_boss'], G['gas_entry_deg'], 9.0, 14.0, 5.0),          # (key, x, azimuth, boss radius, height, bore radius)
             ('bleed', G['x_bleed'], G['a_bleed'], 7.0, 12.0, 2.5),
             ('p2', G['x_p2'], G['a_p2'], 7.0, 12.0, 1.5)]
bosses = [radial_boss(x, a, RDO - 1.5, RDO + h, rb) for _, x, a, rb, h, _ in BOSS_DRUM]
drum = front_ring.fuse([front_wall, shell, dflange] + bosses)
for _, x, a, rb, h, bo in BOSS_DRUM:
    drum = drum.cut(radial_hole(x, a, RDI - 2, RDO + h + 1, bo))
# C1 opening in the shell (inside of the C1 ear)
c1_in = box(C1['rect_x'][0], C1['rect_x'][1], 0.0, C1['y_rect'] + 1, C1['rect_z'][0], C1['rect_z'][1])
drum = drum.cut(c1_in)
drum = drum.removeSplitter()
add('E2-101', 'Collector_Drum', drum, '1.4404 (316L): machined front ring, 4 mm front wall, 2.5 mm rolled shell, 10 mm flange, TIG',
    RHO['S1_4404'], 'cold')

# ---------------------------------------------------------------- E2-102 C1 outlet nozzle (ear + rect->round transition + DN100 PN16 flange)
t1 = C1['t_wall']; x0, x1 = C1['rect_x']; z0, z1 = C1['rect_z']; yr, yt = C1['y_rect'], C1['y_trans']
ro1 = C1['pipe_od'] / 2; ri1 = ro1 - C1['pipe_t']; xc1, zc1 = C1['round_centre_xz']
ear_o = box(x0 - t1, x1 + t1, -t1, yr, z0 - t1, z1 + t1)
ear_i = box(x0, x1, -t1 - 1, yr + 1, z0, z1)
ear = ear_o.cut(ear_i).cut(Part.makeCylinder(RDO - 0.5, 400, V(-200, 0, 0), V(1, 0, 0)))
tr_o = Part.makeLoft([rect_wire(yr, x0 - t1, x1 + t1, z0 - t1, z1 + t1), circ_wire(yt, xc1, zc1, ro1)], True, True)
tr_i = Part.makeLoft([rect_wire(yr - 0.01, x0, x1, z0, z1), circ_wire(yt + 0.01, xc1, zc1, ri1)], True, True)
trans = tr_o.cut(tr_i)
yfl = C1['face_y'] - C1['flange'][4]
stub = tube(ro1, ri1, V(xc1, yt, zc1), V(xc1, yfl, zc1))
D_, K_, nb_, dh_, b_ = C1['flange']
fl1 = plate_flange(V(xc1, yfl, zc1), V(0, 1, 0), D_, 2 * ri1, K_, nb_, dh_, b_)
c1n = ear.fuse([trans, stub, fl1]).removeSplitter()
add('E2-102', 'C1_Outlet_Nozzle', c1n, '1.4404 sheet 2.5 mm + EN 10217-7 pipe 114.3x2 + EN 1092-1 type 11 DN100 PN16 flange, TIG to E2-101',
    RHO['S1_4404'], 'cold')

# ---------------------------------------------------------------- E2-103 front support foot (engine axial fixed point)
fx0, fx1 = G['x_foot']; zs = G['z_skid']; fw = G['foot_w']
foot = box(fx0, fx1, -fw / 2, fw / 2, zs + 10.0, -60.0).cut(Part.makeCylinder(RDO, 400, V(-200, 0, 0), V(1, 0, 0)))
base = box(fx0 - 32.0, fx1 + 32.0, -fw / 2, fw / 2, zs, zs + 10.0)
for sy in (-1, 1):
    for sx in (-1, 1):
        base = base.cut(box(-4 + sx * 24 - 6.5, -4 + sx * 24 + 6.5, sy * 100 - 7, sy * 100 + 7, zs - 1, zs + 11))   # 4 x M12 slots (axial)
gus = []
for sy in (-1, 1):                                         # two gussets (x 0..30) against axial loads
    w = Part.makePolygon([V(fx1, sy * 95, zs + 10), V(fx1 + 30, sy * 95, zs + 10), V(fx1, sy * 95, zs + 150), V(fx1, sy * 95, zs + 10)])
    gus.append(Part.Face(w).extrude(V(0, -sy * 8, 0)))
foot = foot.fuse([base] + gus).removeSplitter()
add('E2-103', 'Front_Foot_FixedPoint', foot, '1.4404 plate 8 mm + base 10 mm, 2 gussets, TIG to the drum; 4 x M12 to the E5 skid', RHO['S1_4404'], 'support')

# =====================================================================================================================
# E2-110 bulkhead (1.4948, 6 mm): clamped rim, hub sleeve, 7 injector bores, 3 core-retainer fingers
bh = ring(XB0, XB1, G['r_bh_bore'], RFO).fuse(ring(XB1, G['x_bh_hub_end'], G['r_bh_bore'], G['r_bh_hub_o']))
for k in range(G['n_mid_bolts']):
    bh = bh.cut(Part.makeCylinder(4.5, 10, P(XB0 - 1, PCD_M / 2, G['mid_bolt_a0_deg'] + 360.0 / G['n_mid_bolts'] * k), V(1, 0, 0)))
for a in A_INJ:
    bh = bh.cut(Part.makeCylinder(3.2, 10, P(XB0 - 1, RI, a), V(1, 0, 0)))                 # stem bores 6.4
x_ret0 = G['x_diff_back'] + G['retainer_gap']
fing = [Part.makeCylinder(G['retainer_d'] / 2, XB0 - x_ret0 + 0.5, P(x_ret0, G['retainer_r'], a), V(1, 0, 0)) for a in G['retainer_a_deg']]
bh = bh.fuse(fing).removeSplitter()
add('E2-110', 'Bulkhead', bh, '1.4948 (304H) plate 6 mm, machined; 3 retainer fingers IN625 pins pressed/welded', RHO['S1_4948'], 'hot')

# E2-111 bulkhead hot-face heat shield: 4 mm microporous + 0.5 mm IN625 cover, holes for the 7 union nuts
shd = ring(XB1, XB1 + G['t_bh_ins'] + 0.5, G['r_bh_hub_o'] + 0.3, RCI - 0.5)
for a in A_INJ:
    shd = shd.cut(Part.makeCylinder(9.0, 10, P(XB1 - 1, RI, a), V(1, 0, 0)))
add('E2-111', 'Bulkhead_HeatShield', shd, 'microporous panel 4 mm (Promat MICROTHERM) + IN625 0.5 mm cover, 6 tack studs', RHO['ins'] * 1.6, 'hot')

# E2-115 gas manifold (316L): torus 8x0.8 + 7 stems 6x0.8 + feed tube 10x1 to the drum boss
xm, rm, dm, tm = G['x_manifold'], G['r_manifold'], G['d_manifold'], G['t_manifold']
tor_o = Part.makeTorus(rm, dm / 2, V(xm, 0, 0), V(1, 0, 0)); tor_i = Part.makeTorus(rm, dm / 2 - tm, V(xm, 0, 0), V(1, 0, 0))
x_stem1 = INJ['x_backplate'][0] + 1.0
stems_o = [Part.makeCylinder(3.0, x_stem1 - xm, P(xm, RI, a), V(1, 0, 0)) for a in A_INJ]
stems_i = [Part.makeCylinder(2.2, x_stem1 - xm + 1, P(xm, RI, a), V(1, 0, 0)) for a in A_INJ]
pf0 = P(xm, rm, G['gas_entry_deg']); pf1 = P(G['x_gas_boss'], RDO + 2.0, G['gas_entry_deg'])
nf = (pf1 - pf0).normalize()
feed_o = cyl(G['d_feed'] / 2, pf0, pf1); feed_i = cyl(G['d_feed'] / 2 - G['t_feed'], pf0, pf1 + nf * 1)
man = tor_o.fuse(stems_o + [feed_o]).cut(Part.makeCompound([tor_i, feed_i] + stems_i))
man = man.cut(Part.makeCylinder(RDO + 50, 60, V(-30, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(RDI, 60, V(-30, 0, 0), V(1, 0, 0))))   # trimmed at the shell bore
add('E2-115', 'Gas_Manifold', man, '316L tube 8x0.8 torus + 7 stems 6x0.8 (threaded M8x0.75 ends) + feed 10x1, TIG/orbital welded, He-leak tested',
    RHO['SS316L'], 'gas')

# E2-120 injector heads x7 (SLM IN625): union nut, backplate, 10 radial vanes 45 deg, centre body, front plate, cup
def injector(a):
    c = P(0, RI, a); ax = V(1, 0, 0)
    def at(x): return V(x, c.y, c.z)
    xu0, xu1 = INJ['x_union'], INJ['x_backplate'][0]
    xb0, xb1 = INJ['x_backplate']; xv1 = xb1 + INJ['slot_h']; xcup1 = xdh + 0.2
    r_sw = 13.0
    nut = hexprism(at(xu0 + 0.1), ax, xu1 - xu0 - 0.1, 14.0).cut(Part.makeCylinder(3.05, 20, at(xu0 - 1), ax))
    back = Part.makeCylinder(r_sw, xb1 - xb0, at(xb0), ax)
    cb = Part.makeCylinder(INJ['cb_d'] / 2, xv1 + 2.0 - xb1, at(xb1), ax)
    front = Part.makeCylinder(r_sw, 1.0, at(xv1), ax).cut(Part.makeCylinder(INJ['cup_id'] / 2, 4, at(xv1 - 1), ax))
    cup = Part.makeCylinder(INJ['cup_id'] / 2 + 1.0, xcup1 - xv1, at(xv1), ax).cut(Part.makeCylinder(INJ['cup_id'] / 2, xcup1 - xv1 + 2, at(xv1 - 1), ax))
    vanes = []
    for k in range(INJ['n_vanes']):
        v = Part.makeBox(r_sw - INJ['r_vane_exit'], 0.8, xv1 - xb1, V(INJ['r_vane_exit'], -0.4, 0))      # local: radial along +x, axial along +z
        v.rotate(V(INJ['r_vane_exit'], 0, 0), V(0, 0, 1), -INJ['vane_angle'])                          # 45 deg lean -> swirl
        v.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / INJ['n_vanes'])
        vanes.append(v)
    vc = Part.makeCompound(vanes).common(Part.makeCylinder(r_sw, xv1 - xb1, V(0, 0, 0), V(0, 0, 1)))
    # local (x radial, z axial) -> ENG: z -> +x axis, placed at the injector centre
    vc.Placement = App.Placement(V(xb1, c.y, c.z), App.Rotation(V(0, 0, 1), V(1, 0, 0)))
    head = back.fuse([cb, front, cup, vc]).cut(Part.makeCylinder(2.2, 4.0, at(xb0 - 0.5), ax))      # gas passage from the stem
    for k in range(INJ['n_gas']):                                                                    # 4 radial gas holes in the centre body
        th = 45.0 + 90.0 * k
        d_ = V(0, math.cos(math.radians(th)), math.sin(math.radians(th)))
        head = head.cut(Part.makeCylinder(INJ['d_gas'] / 2, 4.0, at(xb1 + 0.6 * INJ['slot_h']), d_))
    return nut.fuse(head)
inj = Part.makeCompound([injector(a) for a in A_INJ])
add('E2-120', 'Injector_Heads_x7', inj, 'IN625 SLM (iDesign3D) + HIP + AMS 5666 solution HT, swirler/cup machined; union nut IN625 bar', RHO['IN625'], 'gas',
    qty=NI, note='7 identical heads in one STEP')

# =====================================================================================================================
# E2-130 liner assembly (Hastelloy X 2.4665, 1.0 mm): outer liner + cone + sleeve, dome, inner liner, splash lips, holes, pin pads
tl = G['t_liner']; rlo_i, rlo_o = G['r_lo_i'], G['r_lo_o']; rli_o, rli_i = G['r_li_o'], G['r_li_i']
x_cyl1, x_cone1, x_lo1 = G['x_lo_cyl_end'], G['x_lo_cone_end'], G['x_lo_end']; rsl = G['r_lo_sleeve_i']
outer = rv([(xd, rlo_i), (x_cyl1, rlo_i), (x_cone1, rsl), (x_lo1, rsl), (x_lo1, rsl + tl), (x_cone1, rsl + tl), (x_cyl1, rlo_o), (xd, rlo_o)])
dome = ring(xd, xdh, rli_o - 0.01, rlo_i + 0.01)
inner = ring(G['x_li_front'], G['x_li_end'], rli_i, rli_o)
lips = []
for xr in HOLES['outer_film']['x'][:2]:                                     # splash lips on the 2 cylindrical PZ rows (rows 3-4: plain effusion)
    lips.append(ring(xr - 1.6, xr - 0.8, rlo_i - 2.3, rlo_i + 0.01)); lips.append(ring(xr - 1.6, xr + 4.0, rlo_i - 2.3, rlo_i - 1.5))
for xr in HOLES['inner_film']['x']:
    lips.append(ring(xr - 1.6, xr - 0.8, rli_o - 0.01, rli_o + 2.3)); lips.append(ring(xr - 1.6, xr + 4.0, rli_o + 1.5, rli_o + 2.3))
pads = [radial_boss(G['x_liner_pins'], a, rlo_o - 0.3, rlo_o + 3.0, 6.0) for a in G['a_liner_pins']]
liner = outer.fuse([dome, inner] + lips + pads)
H = []                                                                       # hole cutters
for a in A_INJ:
    H.append(Part.makeCylinder(8.2, 4, P(xd - 1, RI, a), V(1, 0, 0)))                       # cup holes 16.4 (floating cups)
    for k in range(8):                                                                      # 8 effusion holes per cup on r 11
        th = math.radians(22.5 + 45 * k); yy = RI + 11.0 * math.cos(th); zz = 11.0 * math.sin(th)
        p = P(xd - 1, 0, 0) + V(0, yy * math.cos(math.radians(a)) - zz * math.sin(math.radians(a)), yy * math.sin(math.radians(a)) + zz * math.cos(math.radians(a)))
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
    H.append(radial_hole(x, a, rlo_i - 2.5, rlo_o + 1.0, 4.0))                              # igniter / UV sight holes 8
for a in G['a_liner_pins']:
    H.append(radial_hole(G['x_liner_pins'], a, rlo_o + 0.5, rlo_o + 4.0, 3.1))               # blind pin holes in the pads
liner = liner.cut(Part.makeCompound(H))
add('E2-130', 'Liner_Assembly', liner, 'Hastelloy X 2.4665 (VDM Nicrofer 4722Co) 1.0 mm, rolled/spun + TIG, laser-drilled holes; option YSZ TBC on the PZ',
    RHO['HX'], 'hot', note='holes: dome 7 cups + %d effusion, outer film %d, secondary %d, dilution %d, inner film %d' %
    (8 * NI, HOLES['outer_film']['n'], HOLES['secondary']['n'], HOLES['dilution']['n'], HOLES['inner_film']['n']))

# E2-131 liner location pins x3 (IN625), E2-132 tunnel heat shield (IN625 0.3, polished), E2-140 perforated baffle (1.4948 0.8)
pins = []
for a in G['a_liner_pins']:
    pins.append(radial_boss(G['x_liner_pins'], a, rlo_o + 0.6, RCO + 9.0, 3.0).fuse(radial_boss(G['x_liner_pins'], a, RCO + 9.0, RCO + 13.0, 6.0)))
add('E2-131', 'Liner_Pins_x3', Part.makeCompound(pins), 'IN625 bar Ø6, head Ø12; locked by the boss cap nut (not modelled)', RHO['IN625'], 'hot', qty=3)
xs0, xs1 = G['x_shield']; rs0 = G['r_shield_i']
shield = ring(xs0, xs1, rs0, rs0 + G['t_shield'])
add('E2-132', 'Tunnel_HeatShield', shield, 'IN625 0.3 mm, electropolished, dimple spacers to the tunnel (dead-air gap r 10.5..17.3)', RHO['IN625'], 'hot')
xb0_, xb1_ = G['x_baffle']; rb_ = G['r_baffle']
baf = ring(xb0_, xb1_, rb_, rb_ + G['t_baffle'])
tabs = []
for k in range(6):
    t_ = Part.makeBox(6.0, 2.0, RCI - (rb_ + G['t_baffle']) + 0.4, V(xb1_ - 6.0, -1.0, rb_ + G['t_baffle'] - 0.2))
    t_.rotate(V(0, 0, 0), V(1, 0, 0), 30.0 + 60.0 * k - 90.0); tabs.append(t_)
baf = baf.fuse(tabs)
for a in G['a_twall']:
    baf = baf.cut(radial_hole(G['x_twall'], a, rb_ - 1, rb_ + 2, 2.0))                     # TE-507 sheath passages
for x, a, rh in ((G['x_igniter'], G['a_igniter'], 7.5), (G['x_uv'], G['a_uv'], 8.0)):
    baf = baf.cut(radial_hole(x, a, rb_ - 1, rb_ + 2, rh))                                  # igniter / UV sight-tube clearance
add('E2-140', 'Perforated_Baffle', baf, '1.4948 sheet 0.8 mm, 40 % open (Ø3 holes, not modelled), 6 tabs welded to the casing', RHO['S1_4948'] * 0.6, 'hot')

# =====================================================================================================================
# E2-150 hot pressure casing (1.4948): flange, shell, solid rear ring (E2/E3 flange), bosses
hfl = ring(XF0, XF1, RCI, RFO)
for k in range(G['n_mid_bolts']):
    hfl = hfl.cut(Part.makeCylinder(4.5, 10, P(XF0 - 1, PCD_M / 2, G['mid_bolt_a0_deg'] + 360.0 / G['n_mid_bolts'] * k), V(1, 0, 0)))
hshell = ring(XF1 - 0.5, XR0 + 0.5, RCI, RCO)
rring = ring(XR0, XR1, G['r_rear_bore'], G['r_e3_flange_o'])
rring = rring.cut(ring(XR1 - G['e3_spigot_depth'], XR1 + 1, G['e3_groove_ri'], G['e3_spigot_d'] / 2))         # spigot groove (OD 120 H7)
rring = rring.cut(ring(G['seal_groove_x'][0], G['seal_groove_x'][1], G['r_rear_bore'] - 0.5, G['r_seal_groove']))  # piston-ring groove
for k in range(G['n_e3_bolts']):                                                                                # 16 x M8 blind tapped, depth 14
    rring = rring.cut(Part.makeCylinder(3.4, 14.01, P(XR1 - 14.0, G['pcd_e3'] / 2, G['e3_bolt_a0_deg'] + 360.0 / G['n_e3_bolts'] * k), V(1, 0, 0)))
BOSS_CASE = [  # key, x, azimuth, boss radius, top radius, bore radius
    ('igniter', G['x_igniter'], G['a_igniter'], 13.0, RCO + 12.0, 6.0),
    ('uv', G['x_uv'], G['a_uv'], 15.0, RCO + 14.0, 7.0),
    ('p3', G['x_p3'], G['a_p3'], 7.0, RCO + 10.0, 1.5),
    ('t3', G['x_t3'], G['a_t3'], 10.0, RCO + 12.0, 1.6),
    ('tw1', G['x_twall'], G['a_twall'][0], 7.0, RCO + 10.0, 0.6),
    ('tw2', G['x_twall'], G['a_twall'][1], 7.0, RCO + 10.0, 0.6)] + \
    [('pin%d' % i, G['x_liner_pins'], a, 8.0, RCO + 9.0, 3.05) for i, a in enumerate(G['a_liner_pins'])]
cb = [radial_boss(x, a, RCO - 1.5, rt, rb) for _, x, a, rb, rt, _ in BOSS_CASE]
case = hfl.fuse([hshell, rring] + cb)
for _, x, a, rb, rt, bo in BOSS_CASE:
    case = case.cut(radial_hole(x, a, RCI - 2, rt + 1, bo))
c2_in = box(C2['rect_x'][0], C2['rect_x'][1], 0.0, C2['y_rect'] + 1, C2['rect_z'][0], C2['rect_z'][1])
case = case.cut(c2_in).removeSplitter()
add('E2-150', 'Hot_Pressure_Casing', case, '1.4948 (304H): flange + rolled 3 mm shell + forged/machined rear ring, TIG, PWHT none; hydro 11.1 barg',
    RHO['S1_4948'], 'hot')

# E2-151 C2 inlet duct (1.4948 3 mm) + rectangular flange (E2/E4)
t2 = C2['t_wall']; ax0, ax1 = C2['rect_x']; az0, az1 = C2['rect_z']; y2r = C2['y_rect']; y2f = C2['face_y']; rim = C2['rect_flange_rim']
d_o = box(ax0 - t2, ax1 + t2, -t2, y2r, az0 - t2, az1 + t2)
d_i = box(ax0, ax1, -t2 - 1, y2r + 1, az0, az1)
duct = d_o.cut(d_i).cut(Part.makeCylinder(RCO - 0.5, 300, V(-100, 0, 0), V(1, 0, 0)))
rfl = box(ax0 - rim, ax1 + rim, y2r, y2f, az0 - rim, az1 + rim).cut(box(ax0, ax1, y2r - 1, y2f + 1, az0, az1))
bx = (ax0 - rim / 2, ax1 + rim / 2); bz = (az0 - rim / 2, az1 + rim / 2)
C2_BOLTS = [(bx[0], bz[0]), (bx[1], bz[0]), (bx[0], bz[1]), (bx[1], bz[1]), (0.5 * sum(bx), bz[0]), (0.5 * sum(bx), bz[1])]
for f in (1 / 3, 2 / 3): C2_BOLTS += [(bx[0], bz[0] + f * (bz[1] - bz[0])), (bx[1], bz[0] + f * (bz[1] - bz[0]))]
for bx_, bz_ in C2_BOLTS:
    rfl = rfl.cut(Part.makeCylinder(5.5, 20, V(bx_, y2r - 1, bz_), V(0, 1, 0)))
c2d = duct.fuse(rfl).removeSplitter()
add('E2-151', 'C2_Inlet_Duct_RectFlange', c2d, '1.4948 sheet 3 mm box duct + 15 mm rectangular flange (10 x M10 clearance), TIG to E2-150',
    RHO['S1_4948'], 'hot')

# =====================================================================================================================
# insulation envelopes (removable, microporous + 0.5 mm 1.4301 cladding): hot casing 50 mm, drum 25 mm
ti_h, ti_d = G['insulation']['hot'], G['insulation']['drum']
ins_h = ring(C2['rect_x'][0] - C2['t_wall'] + 0.5, XR0, RCO, RCO + ti_h)      # starts behind the mid-flange nuts/studs
ins_h = ins_h.cut(box(ax0 - t2 - 3, ax1 + t2 + 3, -t2 - 3, y2r + 5, az0 - t2 - 3, az1 + t2 + 3))
for _, x, a, rb, rt, bo in BOSS_CASE: ins_h = ins_h.cut(radial_boss(x, a, RCO - 1, RCO + ti_h + 2, rb + 2.0))
ins_d = ring(xdf + G['t_front_wall'], XM0, RDO, RDO + ti_d)
ins_d = ins_d.cut(box(x0 - t1 - 3, x1 + t1 + 3, -t1 - 3, yr + 5, z0 - t1 - 3, z1 + t1 + 3)).cut(box(fx0 - 3, fx1 + 3, -fw, fw, zs - 1, -60))
for _, x, a, rb, h, bo in BOSS_DRUM: ins_d = ins_d.cut(radial_boss(x, a, RDO - 1, RDO + ti_d + 2, rb + 2.0))
ins_d = ins_d.cut(cyl(G['d_feed'] / 2 + 3, pf0, pf1 + nf * 60))
add('E2-160', 'Insulation_HotCasing', ins_h, 'microporous 50 mm (Promat MICROTHERM Overstitched) in 0.5 mm 1.4301 cladding, 2 half shells', RHO['ins'] * 1.3, 'ins')
add('E2-161', 'Insulation_Drum', ins_d, 'microporous 25 mm in 0.5 mm 1.4301 cladding, 2 half shells', RHO['ins'] * 1.3, 'ins')

# =====================================================================================================================
# seals, gaskets, fasteners (buy items, modelled for clearance)
gk1 = ring(XM1, XB0, 118.5, 123.0); gk2 = ring(XB1, XF0, 118.5, 123.0)
add('E2-170', 'MidFlange_Gaskets_x2', Part.makeCompound([gk1, gk2]), 'KLINGER Milam PSS 1 mm (mica) / Thermiculite 815, ID 237 / OD 246', RHO['mica'], 'seal', qty=2)
pr = ring(G['seal_groove_x'][0] + 0.05, G['seal_groove_x'][1] - 0.05, G['r_ngv_o'] + 0.10, G['r_seal_groove'] - 0.1)
add('E2-171', 'RearSeal_PistonRing', pr, 'IN718 split piston ring, step gap, 2 x 3.5 radial (seals on the GG NGV shroud OD 72.7)', RHO['IN625'], 'seal')
orr = ring(G['oring_x'] - 0.9, G['oring_x'] + 0.9, G['r_core'] + 0.08, G['r_core'] + 1.85)
add('E2-172', 'Front_Oring', orr, 'FKM 75 Sh A O-ring 107.32 x 1.78 (ISO 3601), 200 C', RHO['FKM'], 'seal')
studs = []
for k in range(G['n_mid_bolts']):
    a = G['mid_bolt_a0_deg'] + 360.0 / G['n_mid_bolts'] * k
    c = P(0, PCD_M / 2, a)
    studs.append(Part.makeCylinder(4.0, 43.5 - (XM1 - 8.5), V(XM1 - 8.5, c.y, c.z), V(1, 0, 0)))
    studs.append(Part.makeCylinder(8.0, 1.6, V(XF1 + 0.01, c.y, c.z), V(1, 0, 0)))                       # washer
    studs.append(hexprism(V(XF1 + 1.61, c.y, c.z), V(1, 0, 0), 6.5, 13.0).cut(Part.makeCylinder(4.0, 8, V(XF1 + 1, c.y, c.z), V(1, 0, 0))))
add('E2-173', 'MidFlange_Studs_Nuts_x16', Part.makeCompound(studs), 'M8 studs 1.4980 (A286) L 35 + silver-plated nuts 1.4980 + washers', RHO['A286'], 'fastener', qty=16)

# =====================================================================================================================
# instruments / igniter (buy, envelope models)
def probe(x, a, r0, segs):
    """radial envelope: list of (length, radius) segments starting at r0"""
    s, r = [], r0
    for L_, rad in segs:
        s.append(Part.makeCylinder(rad, L_, P(x, r, a), rdir(a))); r += L_
    return Part.makeCompound(s)
inst = {}
inst['E2-501'] = ('IGN-630_Igniter_Plug', probe(G['x_igniter'], G['a_igniter'], rlo_o + 0.5, [(RCO + 12.0 - rlo_o - 0.5, 5.5), (12.0, 10.4), (40.0, 8.0), (30.0, 9.0)]),
                  'surface-gap igniter plug M14x1.25, Ni/Pt electrode, ceramic insulator; HT lead to the exciter IGN-630', 'Bosch industrial (DE) / Brahma (IT) electrode type')
inst['E2-502'] = ('BE-631_UV_Sight_Sensor', probe(G['x_uv'], G['a_uv'], rlo_o + 0.5, [(RCO + 14.0 - rlo_o - 0.5, 6.0), (25.0, 14.0), (20.0, 12.0), (95.0, 22.0)]),
                  'UV flame sensor Durag D-LX 100 UV on a cooled sight tube Ø12 + quartz window adapter (air-purged from the casing)', 'Durag (DE)')
inst['E2-503'] = ('PT-522_P3_Tap', probe(G['x_p3'], G['a_p3'], RCO + 10.0, [(15.0, 6.0), (40.0, 3.0)]), 'P3 static tap 1/8" + snubber coil to PT-522 (0-6 bar abs)', 'Voss (DE) fitting; transmitter in EL scope')
inst['E2-504'] = ('TE-506_T3_Plenum_TC', probe(G['x_t3'], G['a_t3'], RCI - 10.0, [(RCO + 12.0 - RCI + 10.0, 1.5), (18.0, 7.0), (60.0, 4.0)]),
                  'type K class 1, MI Ø3 Inconel 600, immersion 10 mm into the hot plenum (NEW tag TE-506: T3 combustor inlet)', 'Roessel Messtechnik (DE)')
for i, (tg, a) in enumerate((('E2-505', G['a_twall'][0]), ('E2-506', G['a_twall'][1]))):
    inst[tg] = ('TE-507%s_Liner_Wall_TC' % 'AB'[i], probe(G['x_twall'], a, rlo_o + 0.2, [(RCO + 10.0 - rlo_o - 0.2, 0.5), (18.0, 5.0), (50.0, 3.0)]),
                'type K MI Ø1.0 Inconel 600, tip brazed to the outer liner PZ (commissioning, NEW tag TE-507%s)' % 'AB'[i], 'Roessel Messtechnik (DE) / TC Mess- und Regeltechnik (DE)')
inst['E2-507'] = ('PT-521_P2_Tap', probe(G['x_p2'], G['a_p2'], RDO + 12.0, [(15.0, 6.0), (40.0, 3.0)]), 'P2 tap + 300 mm sense line to PT-521 (0-6 bar abs)', 'Voss (DE)')
inst['E2-508'] = ('Gas_Inlet_Fitting_L10', probe(G['x_gas_boss'], G['gas_entry_deg'], RDO + 14.0, [(24.0, 11.0), (40.0, 5.0)]), 'DIN 2353 L10 bulkhead union 316, gas from PT-605 / FCV-620', 'Voss (DE) / Stauff (DE)')
inst['E2-509'] = ('Buffer_Air_Fitting_L6', probe(G['x_bleed'], G['a_bleed'], RDO + 12.0, [(18.0, 7.0), (40.0, 3.0)]), 'DIN 2353 L6 union 316 -> E3-606 orifice/filter -> E3 B1 seal', 'Voss (DE) / Stauff (DE)')
for tg, (nm, shp, desc, sup) in inst.items():
    add(tg, nm, shp, desc, RHO['misc'], 'sensor', note=sup)

# =====================================================================================================================
# checks: E2 vs GG core (kept parts must not be touched), E2 internal pairs (only the listed joints may touch/overlap)
def overlap(a, b):
    if not a.BoundBox.intersect(b.BoundBox): return 0.0
    try: return a.common(b).Volume
    except Exception: return -1.0
KEPT = ('Intake', 'IntakeOuter', 'Compressor', 'Diffuser', 'Shaft', 'ShaftTunnel', 'NGV', 'Turbine', 'TurbineNut', 'NoseCone', 'Starter',
        'RPM_Sensor', 'RPM_Magnet', 'Balance_Slug', 'FrontBearing_608_hybrid_8x22x7', 'RearBearing_608_hybrid_8x22x7', 'FrontBearing_Oring',
        'WaveSpring_22x16_free3_0_inst2_8')
REPLACED = ('Casing', 'CC_FrontCap', 'CC_Inner', 'CC_Outer', 'CC_RearCone', 'CC_Vaporisers', 'GasBulkhead', 'Igniter', 'SupplyLines', 'SupplySeals',
            'Exhaust', 'EGT_Probe', 'Fasteners')
GG = {}
for n in KEPT + ('Fasteners',):
    f = os.path.join(GG_ASM, n + '.step')
    if os.path.exists(f):
        s = Part.Shape(); s.read(f); GG[n] = s
chk = dict(core_kept={}, core_info={}, internal=[], clearances={}, replaced_core_parts=list(REPLACED))
for n, s in GG.items():
    hits = {}
    for t, p in PARTS.items():
        v = overlap(p['shape'], s)
        if abs(v) > 1e-3: hits[t] = round(v, 3)
    (chk['core_kept'] if n in KEPT else chk['core_info'])[n] = hits
    if n == 'Fasteners':          # solids 0-5 (x < -40, starter/intake screws) are kept; 6-9 (x 112-119.5, r 44) held Rutten's casing to the exhaust cone
        hk = {t: round(sum(sl.common(p['shape']).Volume for sl in s.Solids if sl.BoundBox.XMax < 0), 3) for t, p in PARTS.items()}
        chk['core_kept']['Fasteners (front, kept)'] = {t: v for t, v in hk.items() if v > 1e-3}
    say('core %-14s vs E2: %s' % (n, hits if hits else 'no interference'))
JOINTS = {('E2-101', 'E2-102'), ('E2-101', 'E2-103'), ('E2-101', 'E2-115'), ('E2-101', 'E2-508'), ('E2-101', 'E2-509'), ('E2-101', 'E2-507'),
          ('E2-101', 'E2-172'), ('E2-101', 'E2-173'), ('E2-110', 'E2-173'), ('E2-150', 'E2-173'), ('E2-101', 'E2-170'), ('E2-110', 'E2-170'),
          ('E2-150', 'E2-170'), ('E2-110', 'E2-111'), ('E2-110', 'E2-115'), ('E2-110', 'E2-120'), ('E2-115', 'E2-120'), ('E2-111', 'E2-120'),
          ('E2-130', 'E2-120'), ('E2-130', 'E2-131'), ('E2-150', 'E2-131'), ('E2-150', 'E2-140'), ('E2-150', 'E2-151'), ('E2-150', 'E2-171'),
          ('E2-110', 'E2-130'), ('E2-160', 'E2-150'), ('E2-110', 'E2-132'), ('E2-161', 'E2-101'), ('E2-161', 'E2-102'), ('E2-161', 'E2-103'), ('E2-160', 'E2-151')}
tags = sorted(PARTS)
for i, a in enumerate(tags):
    for b in tags[i + 1:]:
        v = overlap(PARTS[a]['shape'], PARTS[b]['shape'])
        if v > 1.0 or v < 0:
            rec = dict(a=a, b=b, vol_mm3=round(v, 2), expected=((a, b) in JOINTS or (b, a) in JOINTS or PARTS[a]['group'] == 'sensor' or PARTS[b]['group'] == 'sensor'))
            chk['internal'].append(rec)
bad = [r for r in chk['internal'] if not r['expected']]
say('E2 internal overlaps > 1 mm3: %d (unexpected %d) %s' % (len(chk['internal']), len(bad), bad[:10]))
def dist(a, b):
    try: return a.distToShape(b)[0]
    except Exception: return -1
for a, b, what in (('E2-130', 'NGV', 'outer sleeve / NGV shroud (slip)'), ('E2-130', 'ShaftTunnel', 'inner liner / tunnel'),
                   ('E2-132', 'ShaftTunnel', 'heat shield / tunnel'), ('E2-110', 'Diffuser', 'retainer fingers / diffuser back face'),
                   ('E2-115', 'Diffuser', 'manifold / diffuser'), ('E2-150', 'NGV', 'rear bore / NGV rib'), ('E2-171', 'NGV', 'piston ring / NGV shroud'),
                   ('E2-101', 'IntakeOuter', 'front ring bore / intake outer'), ('E2-130', 'Turbine', 'liner / GG turbine')):
    if b in GG: chk['clearances'][what] = round(dist(PARTS[a]['shape'], GG[b]), 3)
for a, b, what in (('E2-102', 'E2-173', 'C1 ear / mid-flange stud ends'), ('E2-151', 'E2-173', 'C2 duct / mid-flange nuts'),
                   ('E2-120', 'E2-110', 'swirler head / bulkhead hub'), ('E2-120', 'E2-130', 'cup / dome hole')):
    chk['clearances'][what] = round(dist(PARTS[a]['shape'], PARTS[b]['shape']), 3)
say('clearances (mm): ' + ', '.join('%s %.2f' % kv for kv in chk['clearances'].items()))
json.dump(chk, open(os.path.join(OUT, 'E2_checks.json'), 'w'), indent=1)

# =====================================================================================================================
# exports: per-part STEP, assembly (ENG) + ROOF placement, FCStd
for t, p in PARTS.items():
    p['shape'].exportStep(os.path.join(OUT, '%s_%s.step' % (t, p['name'])))
asm = Part.makeCompound([p['shape'] for p in PARTS.values()])
asm.exportStep(os.path.join(OUT, 'E2_assembly.step'))
asm_r = asm.copy(); asm_r.translate(V(*ROOF0)); asm_r.exportStep(os.path.join(OUT, 'E2_assembly_ROOF.step'))
doc = App.newDocument('E2_Combustor_Casing')
for t, p in PARTS.items():
    o = doc.addObject('Part::Feature', t.replace('-', '_')); o.Shape = p['shape']; o.Label = '%s %s' % (t, p['name'])
doc.recompute(); doc.saveAs(os.path.join(OUT, 'E2_assembly.FCStd'))
bb = asm.BoundBox
say('assembly bbox x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f mm  -> ROOF X %.3f..%.3f m' % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax,
    (ROOF0[0] + bb.XMin) / 1e3, (ROOF0[0] + bb.XMax) / 1e3))

# =====================================================================================================================
# interfaces (names carrying C1 / C2 are read by cad/engine/recuperator.py: ENG_mm is converted with its own transform)
pr_ = RS['pressure']; dp_ = RS['design_point']
def itf(name, pos, direction, size, counterpart, **kw):
    d = dict(name=name, ENG_mm=[round(v, 2) for v in pos], ROOF_m=roof(pos), direction=direction, size=size, counterpart=counterpart); d.update(kw); return d
IF = []
IF.append(itf('C1 compressor-delivery outlet (to E4 cold inlet)', [xc1, C1['face_y'], zc1], [0, 1, 0],
              'EN 1092-1 type 11 DN100 PN16 weld-neck, face y %.0f (D 220, K 180, 8 x M16 holes 18, straddling the vertical); pipe 114.3 x 2.0' % C1['face_y'],
              'E4 cold-inlet spool E4-SP-C1 (straight: flange axis = E4 top-header axis, ENG z %.1f)' % zc1,
              fluid='air %.3f kg/s, %.0f C, %.3f bar abs (after the collector, -%.2f %%)' % (dp_['ma'], dp_['T2_C'], pr_['P_C1'], RS['collector']['dp_total_pct']),
              design='3.0 barg / 250 C', movement_mm=dict(dx=round(RS['thermal_growth_mm']['C1 flange centre: dx'], 2),
                                                          dy=round([v for k, v in RS['thermal_growth_mm'].items() if k.startswith('C1 flange centre: dy')][0], 2)),
              status='E2 published 2026-10-23; E4 adopts'))
IF.append(itf('C2 recuperated-air inlet (from E4 cold outlet)', [0.5 * (ax0 + ax1), y2f, 0.5 * (az0 + az1)], [0, 1, 0],
              'RECTANGULAR flange, face y %.0f: duct inside %.0f (x) x %.0f (z) mm, flange %.0f x %.0f x %.0f thick, %d x M10 (holes 11) on the rim centre line, '
              'sheet gasket 8 wide (Thermiculite 815 / Milam PSS); a round DN125 flange does not fit (E3 drum cover r 235 at x 145, E3 H1 flange)' %
              (y2f, ax1 - ax0, az1 - az0, ax1 - ax0 + 2 * rim, az1 - az0 + 2 * rim, C2['rect_flange_t'], len(C2_BOLTS)),
              'E4 cold-outlet spool E4-SP-C2: rectangular flange + rect-to-round transition to the DN125 bellows on axis ENG x %.0f / z %.1f (E4 bottom header)' %
              tuple(C2['round_axis_xz_E4']),
              rect_inner_mm=[ax1 - ax0, az1 - az0], rect_flange_mm=[ax1 - ax0 + 2 * rim, az1 - az0 + 2 * rim], rect_bolts_xz_mm=[[round(a, 1), round(b, 1)] for a, b in C2_BOLTS],
              round_axis_ENG_mm=[C2['round_axis_xz_E4'][0], None, C2['round_axis_xz_E4'][1]],
              fluid='air %.3f kg/s, %.0f C, %.3f bar abs' % (dp_['ma'] * (1 - RS['beta_recuperator_bypass']), dp_['T2r_C'], pr_['P_C2']),
              design='3.0 barg / 620 C', movement_mm=dict(dx=round(RS['thermal_growth_mm']['C2 flange centre: dx'], 2),
                                                          dy=round([v for k, v in RS['thermal_growth_mm'].items() if k.startswith('C2 flange centre: dy')][0], 2)),
              status='E2 published 2026-10-23; E4 adopts (E4 owns the C1/C2 bolting and gaskets)'))
IF.append(itf('IF-E2E3 rear flange (E2 side)', [G['x_e3_face'], 0, 0], [1, 0, 0],
              'E2 face x %.1f + 1.0 mm gasket (E3-605) = E3 face x %.1f; OD %.0f, PCD %.0f, %d x M8 blind tapped (depth 14) in the E2 ring, phase %.2f deg; '
              'annular spigot groove r %.1f..%.1f (OD 120 H7) x %.1f..%.1f for the E3 spigot OD 120 h7 x 3; piston ring E2-171 in the bore groove x %.1f..%.1f r %.1f' %
              (G['x_e3_face'], G['x_e3_face'] + G['t_e3_gasket'], 2 * G['r_e3_flange_o'], G['pcd_e3'], G['n_e3_bolts'], G['e3_bolt_a0_deg'], G['e3_groove_ri'],
               G['e3_spigot_d'] / 2, XR1 - G['e3_spigot_depth'], XR1, G['seal_groove_x'][0], G['seal_groove_x'][1], G['r_seal_groove']),
              'E3-101 front flange (cad/engine/fpt_pmg.py): face x 116.0, studs/nuts E3-602, gasket E3-605',
              calc=RS['casing_mech']['flange_E2E3'], status='coincident with E3 (E3 face 116.0 = E2 face 115.0 + gasket)'))
IF.append(itf('Gas inlet (fuel)', [G['x_gas_boss'], *list(P(0, RDO + 14.0, G['gas_entry_deg']))[1:]], list(rdir(G['gas_entry_deg'])),
              'DIN 2353 L10 (M16x1.5) on the drum boss; %.3f g/s natural gas, manifold %.2f barg at the design point' % (dp_['mf'] * 1e3, RS['gas']['P_manifold_barg']),
              'E5 gas train after FCV-620 / PT-605 (flexible stainless hose DN8)'))
IF.append(itf('Compressor-delivery bleed (E3 B1 buffer air)', [G['x_bleed'], *list(P(0, RDO + 12.0, G['a_bleed']))[1:]], list(rdir(G['a_bleed'])),
              'M12x1.5 boss, DIN 2353 L6; %.1f g/s at P2' % RS['bleed_E3_buffer']['g_s'], 'E3 "Buffer air to B1 seal annulus" via E3-606 orifice + filter'))
for key, tag, txt in (('p2', 'PT-521', 'P2 tap M10x1, 300 mm sense line'), ):
    x_, a_ = G['x_p2'], G['a_p2']
    IF.append(itf('Sensor %s P2 tap' % tag, [x_, *list(P(0, RDO + 12.0, a_))[1:]], list(rdir(a_)), txt, 'B2 per docs/electrical/02_io_list'))
for x_, a_, nm, txt in ((G['x_igniter'], G['a_igniter'], 'IGN-630 igniter plug', 'M14x1.25 boss, plug tip flush with the liner'),
                        (G['x_uv'], G['a_uv'], 'BE-631 UV flame sensor', 'sight tube Ø12 + quartz window, Durag D-LX 100 UV'),
                        (G['x_p3'], G['a_p3'], 'PT-522 P3 tap', 'M10x1 boss, 1/8" tube'),
                        (G['x_t3'], G['a_t3'], 'TE-506 T3 plenum TC (new tag)', 'M8x1 compression boss, MI Ø3'),
                        (G['x_twall'], G['a_twall'][0], 'TE-507A liner wall TC (new tag)', 'M6x0.75 boss, MI Ø1'),
                        (G['x_twall'], G['a_twall'][1], 'TE-507B liner wall TC (new tag)', 'M6x0.75 boss, MI Ø1')):
    IF.append(itf('Sensor ' + nm, [x_, *list(P(0, RCO + 12.0, a_))[1:]], list(rdir(a_)), txt, 'B2 / SR1 per docs/electrical/02_io_list'))
IF.append(itf('Front foot (engine axial fixed point)', [0.5 * (fx0 + fx1), 0, zs], [0, 0, -1],
              'base %.0f x %.0f x 10, 4 x M12 in axial slots (y +-100)' % (fx1 - fx0 + 64, fw), 'E5 skid rail (top ENG z -400 = ROOF Z 0.200); E3 feet are flexures'))
info = dict(subsystem='E2 recuperated annular combustor + pressure casing + compressor-exit collector', frame='ENG mm; ROOF = (1.880 + x/1000, 7.850 + y/1000, 0.600 + z/1000) m',
            source='cad/engine/combustor_casing.py + sim/engine/e2_combustor_calc.py',
            envelope_ENG_mm=[[round(bb.XMin, 1), round(bb.YMin, 1), round(bb.ZMin, 1)], [round(bb.XMax, 1), round(bb.YMax, 1), round(bb.ZMax, 1)]],
            envelope_ROOF_m=[roof([bb.XMin, bb.YMin, bb.ZMin]), roof([bb.XMax, bb.YMax, bb.ZMax])],
            design_point=dict(T_in_C=dp_['T2r_C'], P_C2_bar=pr_['P_C2'], P_combustor_bar=pr_['P_combustor'], TIT_C=dp_['TIT_C'], fuel_g_s=dp_['mf'] * 1e3,
                              T_exit_mixed_C=RS['combustor']['T_exit_mixed_C'], pattern_factor=RS['combustor']['pattern_factor'],
                              liner_Tw_max_C=dict(outer=RS['liner_thermal']['outer_Tw_max_C'], inner=RS['liner_thermal']['inner_Tw_max_C'])),
            replaced_core_parts=list(REPLACED), interfaces=IF)
json.dump(info, open(os.path.join(OUT, 'E2_interfaces.json'), 'w'), indent=1, ensure_ascii=False)
say('interfaces -> %s (%d entries)' % (os.path.join(OUT, 'E2_interfaces.json'), len(IF)))

# =====================================================================================================================
# section plot z = 0 (matplotlib if available)
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(16, 9))
    COL = dict(cold=(0.2, 0.45, 0.85), hot=(0.85, 0.40, 0.15), gas=(0.1, 0.6, 0.2), support=(0.5, 0.5, 0.5), ins=(0.85, 0.80, 0.55),
               seal=(0.6, 0.2, 0.6), fastener=(0.3, 0.3, 0.3), sensor=(0.9, 0.1, 0.1))
    def draw(shp, col, lw=0.8):
        try: sec = shp.slice(V(0, 0, 1), 0.0)
        except Exception: return
        for w in sec:
            for e in w.Edges:
                pts = e.discretize(24); ax.plot([p.x for p in pts], [p.y for p in pts], color=col, lw=lw)
    for n in ('Intake', 'IntakeOuter', 'Compressor', 'Diffuser', 'ShaftTunnel', 'Shaft', 'NGV', 'Turbine', 'TurbineNut', 'NoseCone'):
        if n in GG: draw(GG[n], (0.6, 0.6, 0.6), 0.5)
    for t, p in PARTS.items(): draw(p['shape'], COL.get(p['group'], 'k'))
    sec_c = Part.makeCompound([p['shape'] for t, p in PARTS.items()])
    ax.set_aspect('equal'); ax.grid(alpha=0.3)
    ax.set_xlabel('ENG x [mm] (east, downstream)  -  ROOF X = 1.880 + x/1000'); ax.set_ylabel('ENG y [mm] (north)')
    ax.set_title('GR180-CCHP E2 combustor + casing + collector, section z = 0 (core in grey); C1/C2 are north (+y) at z %.1f / %.1f' % (zc1, 0.5 * (az0 + az1)))
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'E2_section.png'), dpi=120)
    # second view: section x = 70 (through the C2 duct) and x = -10 (C1 ear) in the y-z plane
    fig2, axs = plt.subplots(1, 2, figsize=(14, 7))
    for axx, xc_, ttl in ((axs[0], -10.0, 'x = -10 (drum, C1 ear)'), (axs[1], 70.0, 'x = 70 (hot casing, C2 duct)')):
        for t, p in PARTS.items():
            try: sec = p['shape'].slice(V(1, 0, 0), xc_)
            except Exception: continue
            for w in sec:
                for e in w.Edges:
                    pts = e.discretize(24); axx.plot([q.y for q in pts], [q.z for q in pts], color=COL.get(p['group'], 'k'), lw=0.8)
        axx.set_aspect('equal'); axx.grid(alpha=0.3); axx.set_title(ttl); axx.set_xlabel('ENG y [mm] (north)'); axx.set_ylabel('ENG z [mm] (up)')
    fig2.tight_layout(); fig2.savefig(os.path.join(OUT, 'E2_section_yz.png'), dpi=110)
    say('section -> %s' % os.path.join(OUT, 'E2_section.png'))
except Exception as ex:
    say('section plot skipped: %s' % ex)

# =====================================================================================================================
# BOM (docs/06 sec.5 schema)
MB = {
 'E2-101': ('make', 'sheet-metal + TIG; front ring and flange turned/milled after welding (5-axis), blind M8 x 9 tapped', 'local precision CNC + TIG shop; sheet Outokumpu (FI) / Aperam (BE)', 'cold 165 C; leak test 1.43 x PS'),
 'E2-102': ('make', 'laser-cut + press-brake ear and transition, EN 1092-1 flange bought (Erne Fittings AT / Kuehnle DE)', 'local TIG shop', 'welded to E2-101 before final machining'),
 'E2-103': ('make', 'laser-cut plates + TIG; slots milled', 'local', 'axial fixed point of the whole engine'),
 'E2-110': ('make', '5-axis CNC from 1.4948 plate 8 mm (bulkhead) + 3 IN625 pins', 'local precision CNC', 'flatness 0.05 on both gasket faces'),
 'E2-111': ('buy', 'cut microporous panel + IN625 0.5 cover sheet (laser)', 'Promat (BE/DE); IN625 sheet VDM Metals (DE)', 'replace at hot-section overhaul'),
 'E2-115': ('make', 'tube bending + orbital TIG, stems threaded M8x0.75, He leak test 1e-6 mbar.l/s', 'local; tube Sandvik (SE) 316L seamless', 'pressure test 6 barg'),
 'E2-120': ('make', 'SLM IN625 + HIP + solution HT; swirler throats/cup/thread machined; flow test each head (Cd)', 'iDesign3D (IR) SLM IN625; powder Sandvik Osprey (SE)', 'matched set: flow within +-2 %'),
 'E2-130': ('make', 'rolled/spun Hastelloy X 1.0 mm, TIG, laser-drilled holes, splash lips brazed; optional YSZ TBC 0.2 mm on PZ', 'sheet VDM Metals (DE) Nicrofer 4722Co; laser drilling local', 'life item: inspect 8,000 h'),
 'E2-131': ('make', 'turned IN625 bar', 'local', '3 per engine'),
 'E2-132': ('make', 'IN625 0.3 mm rolled, seam-welded, electropolished, dimple spacers', 'local; foil VDM Metals (DE)', ''),
 'E2-140': ('make', 'perforated 1.4948 sheet 0.8 mm (Ø3, 40 % open) rolled + seam weld, 6 tabs', 'perforated sheet RMIG (DK) / local', ''),
 'E2-150': ('make', 'ring forging 1.4948 (rear ring) + rolled 3 mm shell + flange plate, TIG; 5-axis finish; hydro 11.1 barg', 'forging Boehler (AT) / local; sheet Outokumpu', 'PED Art. 4(3) SEP'),
 'E2-151': ('make', 'laser-cut 1.4948 3 mm box duct + 15 mm flange plate (machined flat), TIG to E2-150', 'local', 'hot 566 C'),
 'E2-160': ('buy', 'microporous half shells in 0.5 mm 1.4301 cladding, quick-release latches', 'Promat MICROTHERM (BE/DE); cladding local', 'skin <= 60 C at 45 C enclosure air'),
 'E2-161': ('buy', 'microporous half shells in cladding', 'Promat (BE/DE)', ''),
 'E2-170': ('buy', 'KLINGER Milam PSS 1 mm / Thermiculite 815, ring ID 237 OD 246', 'Klinger (AT) / Flexitallic (UK)', 'replace at each opening'),
 'E2-171': ('make', 'IN718 ring turned + split, step gap 0.2', 'local; IN718 bar VDM Metals (DE)', 'or carbon/graphite ring Schunk (DE)'),
 'E2-172': ('buy', 'FKM O-ring 107.32 x 1.78', 'Freudenberg (DE) / Trelleborg (SE)', ''),
 'E2-173': ('buy', 'M8 studs 1.4980 (A286) + nuts + washers, anti-seize Ni', 'Boellhoff (DE) / Bossard (CH)', 'torque per VDI 2230'),
}
rows = [['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes']]
for t, p in PARTS.items():
    m = p['shape'].Volume * p['rho']; q = p['qty']
    unit_m = m / q if q > 1 else m
    bb_ = p['shape'].BoundBox
    size = '%.0f x %.0f x %.0f mm (bbox)' % (bb_.XLength, bb_.YLength, bb_.ZLength)
    mf = 'cad_out/engine/E2/%s_%s.step' % (t, p['name'])
    if p['group'] == 'sensor':
        rows.append([t, p['name'].replace('_', ' '), 1, 'buy', p['mat'], size, p['note'], 0.15, mf, 'envelope model; instrument counted in the electrical I/O list'])
        continue
    mk, spec, sup, note = MB.get(t, ('make', p['mat'], 'local', ''))
    rows.append([t, p['name'].replace('_', ' '), q, mk + ': ' + spec, p['mat'], size, sup, round(unit_m, 3), mf, (p['note'] + '; ' if p['note'] else '') + note])
EXTRA = [
 ['E2-601', 'Liner pin cap nuts M10x1 + lock wire', 3, 'buy', 'IN718 / 1.4980', 'M10x1', 'Boellhoff (DE)', 0.01, '', 'on E2-150 pin bosses'],
 ['E2-602', 'Instrument boss fittings (M14x1.25 igniter seal ring, M10x1 / M8x1 / M6x0.75 TC and tap compression fittings)', 8, 'buy', '316 / Cu seal rings', 'DIN 2353 / DIN 7603', 'Voss (DE) / Stauff (DE)', 0.02, '', ''],
 ['E2-603', 'Quartz window + purge-air adapter for BE-631', 1, 'buy', 'fused silica, 1.4404 holder', '1" thread', 'Durag (DE) accessory', 0.2, '', 'window purged by casing air (no external air)'],
 ['E2-604', 'Flexible gas hose DN8 316 braided, L 500, DIN 2353 L10 ends (E5 gas train -> E2-508)', 1, 'buy', '1.4404 corrugated + braid, EN ISO 10380', 'PN 16', 'Witzenmann (DE) / BOA (DE)', 0.3, '', 'decouples engine growth from the skid gas train'],
 ['E2-605', 'Hydro / He leak test + PMI + RT of the casing seams (services)', 1, 'buy', 'EN 13445-5 practice', '11.1 barg hydro', 'TUV Nord / TUV Austria (local branch)', 0, '', 'documentation for PED Art. 4(3)'],
 ['E2-606', 'Injector flow-bench calibration (set of 7)', 1, 'buy', 'air flow, Cd and swirl number check', '', 'university lab / local', 0, '', 'match within +-2 %'],
]
rows += EXTRA
os.makedirs(os.path.join(ROOT, 'docs', 'bom'), exist_ok=True)
with open(os.path.join(ROOT, 'docs', 'bom', 'engine_E2_bom.csv'), 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(rows)
tot = sum(p['shape'].Volume * p['rho'] for p in PARTS.values()) + sum(r[7] * (r[2] if isinstance(r[2], int) else 1) for r in EXTRA)
say('BOM -> %s (%d rows); E2 total mass %.1f kg' % (os.path.join(ROOT, 'docs', 'bom', 'engine_E2_bom.csv'), len(rows) - 1, tot))
open(os.path.join(OUT, 'E2_build.log'), 'w').write('\n'.join(log) + '\n')
