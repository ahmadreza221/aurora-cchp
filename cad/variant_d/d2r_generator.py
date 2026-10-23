# GR180 version D2 - GENERATOR POD, buildable detail (d2g rev, 2026-10-23).
# Simplified pod: G-200 housing (one Al cup: shell + jacket bore + integral rear wall with the rear bearing seat) + G-202 front
# cover (end bell with the front bearing seat and all front ports) + G-201 glycol-jacket sleeve with the stator shrunk in.
# Rotor: d10 through-shaft with integral collar + d6 x 54 quill + AF6 socket hub (slides on the crowned AF6 engine-shaft nose,
# no adjustment), Sm2Co17 magnets on a steel carrier under a carbon sleeve, 1.4404 end rings = balance planes, 2 identical
# seal spacers, precision locknut; 2 identical SFD cartridges (front with a ground shim = locating, rear with a 60 N wave spring).
# Every fastener, pin, O-ring and fitting is modelled as a simple envelope and listed in docs/bom/variant_d2_generator_bom.csv.
# Numbers: cad/variant_d/d2g_layout.py (+ d2r_layout.py for the rotor), joints: sim/variant_d/d2g_joints.py.  ENG frame mm.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2r_generator.py
#   -> cad_out/variant_d/D2/GENERATOR/*.step (internals + fasteners), cad_out/variant_d/D2/POD/*.step (housing + front cover),
#      d2r_generator_parts.json, docs/bom/variant_d2_generator_bom.csv
import FreeCAD as App, Part, os, sys, json, math, csv
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2r_layout as L
import d2g_layout as G
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2', 'GENERATOR')
POD_OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2', 'POD')
for d in (OUT, POD_OUT):
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith('.step'):
            os.remove(os.path.join(d, f))
XA = V(1, 0, 0)


def rev(pts):
    p = [V(x, 0, r) for x, r in pts] + [V(pts[0][0], 0, pts[0][1])]
    return Part.Face(Part.makePolygon(p)).revolve(V(0, 0, 0), XA, 360)


def cyl(x0, x1, r, ri=0.0):
    s = Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), XA)
    return s.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), XA)) if ri > 0 else s


def hexprism(x0, x1, af, axis_x=True):
    r = af / math.sqrt(3)
    pts = [V(x0, r * math.cos(math.radians(30 + 60 * k)), r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0))


def rdir(a):
    return V(0, math.cos(math.radians(a)), math.sin(math.radians(a)))


def rad_cyl(x, a, r0, r1, rad):
    """cylinder of radius rad along the radial direction at angle a, from radius r0 to r1"""
    d = rdir(a)
    return Part.makeCylinder(rad, r1 - r0, V(x, 0, 0) + d * r0, d)


def seg(p0, p1, rad):
    a = V(*p0); b = V(*p1)
    return Part.makeCylinder(rad, (b - a).Length, a, b - a)


def ax_cyl(x0, x1, r_pos, a, rad):
    """axial cylinder at radius r_pos, angle a"""
    d = rdir(a)
    return Part.makeCylinder(rad, x1 - x0, V(x0, 0, 0) + d * r_pos, XA)


def screw_axial(x_face, r_pos, a, d, L, head_d, head_h, into=+1):
    """ISO 4762 / 7380 envelope: head outside the face, shank into the material (into=+1 -> towards +x)"""
    p = V(x_face, 0, 0) + rdir(a) * r_pos
    head = Part.makeCylinder(head_d / 2, head_h, p - XA * (head_h if into > 0 else 0) * 1.0, XA) if into > 0 else \
        Part.makeCylinder(head_d / 2, head_h, p, XA)
    shank = Part.makeCylinder(d / 2, L, p, XA * into)
    return head.fuse(shank)


def screw_z(x, y, z_face, d, L, head_d, head_h):
    """vertical screw, head on top of z_face, shank downwards"""
    head = Part.makeCylinder(head_d / 2, head_h, V(x, y, z_face), V(0, 0, 1))
    shank = Part.makeCylinder(d / 2, L, V(x, y, z_face - L), V(0, 0, 1))
    return head.fuse(shank)


parts = {}          # tag -> (shape, density g/cm3, out_dir)
BOM = []            # rows


def add(tag, shape, rho, bom, out=OUT):
    parts[tag] = (shape, rho, out)
    bom = dict(bom); bom['tag'] = tag.split('_')[0]; bom['model'] = tag; bom['out'] = out
    BOM.append(bom)


def bom_only(tag, **kw):
    kw['tag'] = tag; kw['model'] = ''; kw['out'] = ''
    BOM.append(kw)


# ================================================================== G-200 HOUSING (cup)
H = G.H
hp = [(H['x0'], H['bore1'][2]), (H['x0'], H['flange'][2]), (H['flange'][1], H['flange'][2]), (H['flange'][1], H['r_out']),
      (H['x1'], H['r_out']), (H['x1'], H['pocket'][3]), (H['pocket'][0], H['pocket'][3]), (H['pocket'][0], H['pocket'][2]),
      (H['x1'], H['pocket'][2]), (H['x1'], H['guard_cb'][2]), (H['guard_cb'][0], H['guard_cb'][2]), (H['guard_cb'][0], H['quill_bore'][2]),
      (H['quill_bore'][0], H['quill_bore'][2]), (H['quill_bore'][0], H['collar_seal'][2]), (H['collar_seal'][0], H['collar_seal'][2]),
      (H['collar_seal'][0], H['cart'][2]), (H['drain_space'][0], H['cart'][2]), (H['drain_space'][0], H['seal_r'][2]),
      (H['seal_r'][0], H['seal_r'][2]), (H['seal_r'][0], H['relief'][2]), (H['relief'][0], H['relief'][2]),
      (H['relief'][0], H['bore2'][2]), (H['bore2'][0], H['bore2'][2]), (H['bore2'][0], H['bore1'][2])]
hous = rev(hp)
cover_shape = None


def port_features(body, where, x_surface_r):
    """bosses + threaded holes + passages for the ports on G-200 ('H') or G-202 ('C')"""
    fuse, cuts = [], []
    for name, (x, a, kind, w) in G.PORTS.items():
        if w != where:
            continue
        rb, rtop = G.BOSS[kind]
        fuse.append(rad_cyl(x, a, x_surface_r - 6.0, rtop, rb))
        if kind == 'g14':
            cuts.append(rad_cyl(x, a, rtop - 10.0, rtop + 1, 6.58))           # G1/4 (ISO 228-1) 10 deep, spot face d20
            if where == 'H':
                cuts.append(rad_cyl(x, a, G.J['r_out1'] - 2.0, rtop - 9.0, 2.5))   # d5 passage into the jacket groove
            else:
                cuts.append(rad_cyl(x, a, G.C['chamber'][2] - 1.0, rtop - 9.0, 2.5))  # d5 drain from the bearing chamber
        elif kind == 'g18':
            cuts.append(rad_cyl(x, a, rtop - 8.0, rtop + 1, 4.86))            # G1/8 8 deep
            r_in = (G.C['chamber'][2] - 1.0 if where == 'C' else G.H['cart'][2] - 1.0) if 'drain' in name else G.H['bore2'][2] - 1.0
            cuts.append(rad_cyl(x, a, r_in, rtop - 7.0, 2.0))                 # d4 passage
        elif kind == 'm8':
            cuts.append(rad_cyl(x, a, rtop - 8.0, rtop + 1, 4.0))             # M8x1 (ISO 6149-1 port) 8 deep
            if where == 'H':
                cuts.append(rad_cyl(x, a, G.H['cart'][2] - 1.0, rtop - 7.0, 1.0))   # d2 feed into the cartridge land
            else:
                xl = G.CART_FRONT_U0 + G.CART['feed_u']
                p0 = V(x, 0, 0) + rdir(a) * (rtop - 7.0); p1 = V(xl, 0, 0) + rdir(a) * (G.C['cart'][2] - 1.0)
                cuts.append(Part.makeCylinder(1.0, (p1 - p0).Length, p0, p1 - p0))  # inclined d2 feed to the land
        elif kind == 'pt':
            cuts.append(rad_cyl(x, a, 15.5, rtop + 1, 4.0))                  # blind M8x1, bottom 1.5 mm from the bore
        elif kind in ('pad', 'padc'):
            cuts.append(rad_cyl(x, a, rtop - 8.0, rtop + 1, 3.0))             # M6 Helicoil 1D, 8 deep blind
        elif kind == 'hall':
            cuts.append(rad_cyl(x, a, G.C['chamber'][2] - 1.0, rtop + 1, 4.0))  # M8x1 Hall sensor thread through to the chamber
    for f in fuse:
        body = body.fuse(f)
    body = body.removeSplitter()
    for c in cuts:
        body = body.cut(c)
    return body


hous = port_features(hous, 'H', H['r_out'])
hous = hous.cut(Part.makeBox(H['lead_slot'][1] - H['lead_slot'][0], 2 * H['lead_slot'][2], 20.0,
                             V(H['lead_slot'][0], -H['lead_slot'][2], 40.0)))                     # stator lead-out slot (top)
FH = G.FLANGE_HOLES; R_P = FH['pcd'] / 2
for a in FH['screws']:
    hous = hous.cut(ax_cyl(H['x0'], H['x0'] + 9.0, R_P, a, 2.5))        # M5 Helicoil 1.5D (7.5) in the flange, 9 drilled
for a in FH['dowels']:
    hous = hous.cut(ax_cyl(H['x0'], H['x0'] + 8.0, R_P, a, 2.0))        # d4 H7 dowel holes
for a in G.STRUT_ROOTS['ang']:
    hous = hous.cut(ax_cyl(H['x1'] - G.STRUT_ROOTS['depth'], H['x1'] + 1, G.STRUT_ROOTS['r'], a, 3.0))   # M6 Helicoil 2D
for a in G.FAIRING_HOLES['ang']:
    hous = hous.cut(ax_cyl(H['x1'] - G.FAIRING_HOLES['depth'], H['x1'] + 1, G.FAIRING_HOLES['r'], a, 2.0))  # M4 Helicoil 1.5D
for a in (0.0, 180.0):                                                    # 2 x M5 jack-out threads for the jacket/stator (plugged)
    hous = hous.cut(ax_cyl(H['bore2'][1], H['x1'] + 1, 46.5, a, 2.5))
for (x, y) in G.TBOX['screws']:                                           # 4 x M4 Helicoil for the terminal box (blind 5)
    zt = math.sqrt(H['r_out'] ** 2 - y ** 2)
    hous = hous.cut(Part.makeCylinder(2.0, 6.5, V(x, y, zt - 5.0), V(0, 0, 1)))
hous = hous.cut(ax_cyl(H['cart'][1], H['cart'][1] + 3.5, G.PIN_R, 45.0, 1.0))  # anti-rotation pin hole d2 (rear cartridge)
add('G-200_Pod_Housing', hous, 2.70, dict(
    description='Pod housing (cup): OD 110, front flange OD 128, jacket bore 98 H7 / 96 H7, integral rear wall with the rear bearing seat 28 H6, '
                'labyrinth bores, quill-guard counterbore, port bosses, lead-out slot, strut / fairing / box threads',
    qty=1, make_or_buy='make: CNC lathe (bores 98/96/28 and the 28 H6 seat in ONE clamping from the front) + 4th-axis milling of the bosses and holes',
    material_or_spec='EN AW-6082-T6 (AlSi1MgMn), bar d130 x 160 (or forged ring d130/40 x 160)', size_or_rating='d128 x 152 (x -260..-108)',
    supplier_candidates='bar: Hydro (NO), Constellium (FR), Alu Menziken (CH); machining: precision CNC shop',
    notes='coaxiality 28 H6 to 98 H7 <= 0.01; Helicoils: 6 x M5 (flange), 3 x M6 2D (struts), 3 x M4 (fairing), 4 x M4 (box), 1 x M6 (VE-012); '
          'hard-anodise not needed; O-ring bores Ra 0.8, edges of cross holes deburred R0.3'), out=POD_OUT)

# ================================================================== G-202 FRONT COVER (end bell)
C = G.C
cp = [(C['x0'], C['plug'][2]), (C['x0'], C['r_out']), (C['x_flange'][0], C['r_out']), (C['x_flange'][0], C['r_flange']),
      (C['x_flange'][1], C['r_flange']), (C['x_flange'][1], C['r_spigot']), (C['x_spigot'][1], C['r_spigot']),
      (C['x_spigot'][1], C['seal_r'][2]), (C['seal_r'][0], C['seal_r'][2]), (C['seal_r'][0], C['cart'][2]),
      (C['cart'][0], C['cart'][2]), (C['cart'][0], C['chamber'][2]), (C['chamber'][0], C['chamber'][2]),
      (C['chamber'][0], C['plug'][2])]
cov = rev(cp)
cov = port_features(cov, 'C', C['r_out'])
g0, g1, gd = C['face_oring_groove']
cov = cov.cut(cyl(C['x_flange'][1] - gd, C['x_flange'][1] + 0.01, g1, g0))           # face O-ring groove 103 x 1.8
for a in FH['screws']:
    cov = cov.cut(ax_cyl(C['x_flange'][0] - 1, C['x_flange'][1] + 1, R_P, a, 2.75))  # d5.5 through
for a in FH['dowels']:
    cov = cov.cut(ax_cyl(C['x_flange'][0] - 1, C['x_flange'][1] + 1, R_P, a, 2.0))   # d4 H7 through
for a in FH['jacks']:
    cov = cov.cut(ax_cyl(C['x_flange'][0] - 1, C['x_flange'][1] + 1, R_P, a, 2.5))   # M5 jack-off threads
cov = cov.cut(ax_cyl(C['cart'][0] - 3.5, C['cart'][0], G.PIN_R, 45.0, 1.0))           # anti-rotation pin hole (front cartridge)
add('G-202_Front_Cover', cov, 2.70, dict(
    description='Front cover / end bell: front bearing seat 28 H6, chamber for the locknut, labyrinth bore, M16x1.5 access plug, oil jet / drain, '
                'PT100, accelerometer pad, Hall sensor port, face O-ring groove, 6 x d5.5 + 2 dowels + 2 x M5 jack-off threads',
    qty=1, make_or_buy='make: CNC lathe (28 H6 seat and d98 g6 spigot in one clamping) + 4th-axis milling of bosses / holes; inclined d2 jet drilling',
    material_or_spec='EN AW-6082-T6, bar d130 x 32', size_or_rating='d128 x 28 (x -286..-258)',
    supplier_candidates='bar: Hydro (NO), Constellium (FR); machining: precision CNC shop',
    notes='replaces front end shield + bearing cover + nose cap (3 parts -> 1); spigot d98 g6 x 2 + 2 dowels -> front/rear bearing seats coaxial <= 0.015'),
    out=POD_OUT)

# ================================================================== G-201 JACKET SLEEVE
J = G.J
jk = rev([(J['x0'], J['r_in']), (J['x0'], J['r_out1']), (J['x_step'], J['r_out1']), (J['x_step'], J['r_out2']),
          (J['x1'], J['r_out2']), (J['x1'], J['r_in'])])
for k in range(J['turns']):
    xg = J['x_first'] + J['pitch'] * k
    jk = jk.cut(cyl(xg, xg + J['groove_w'], J['r_out1'] + 1, J['r_out1'] - J['groove_d']))
jk = jk.cut(cyl(J['oring_front'][0], J['oring_front'][1], J['r_out1'] + 1, J['r_out1'] - J['oring_front'][2]))
jk = jk.cut(cyl(J['oring_rear'][0], J['oring_rear'][1], J['r_out2'] + 1, J['r_out2'] - J['oring_rear'][2]))
add('G-201_Glycol_Jacket_Sleeve', jk, 2.70, dict(
    description='Glycol jacket sleeve: helical groove 8 x 3 mm, pitch 10.5, 8 turns (thread-milled / single-point turned), 2 O-ring grooves; stator shrunk in',
    qty=1, make_or_buy='make: CNC lathe (helix single-point turned like a coarse thread)', material_or_spec='EN AW-6082-T6, tube d100/80 x 100 (or bar d100)',
    size_or_rating='d98 / 96 / ID 88 H6 x 96', supplier_candidates='tube: Alu Menziken (CH), Hydro (NO)',
    notes='press fit in G-200: d98 n6 / H7 (front land) and d96 n6 / H7 (rear land); stator shrink fit 0.10-0.13 mm diametral (heat sleeve to 130 C)'))

# ================================================================== G-210 STATOR CORE + G-211 WINDING
S = L.GEN
s0, s1 = S['stack']
Rb, Ro = S['stator_id'] / 2, S['stator_od'] / 2
core = cyl(s0, s1, Ro, Rb)
slots, cu = [], []
d_slot, w_open, w_t = 17.3, 2.0, 3.63
for k in range(S['slots']):
    th = 2 * math.pi * (k + 0.5) / S['slots']
    pts = []
    r1, r2 = Rb + 1.0, Rb + d_slot
    for (r, side) in ((r1, -1), (r2, -1), (r2, 1), (r1, 1)):
        half = (2 * math.pi * r / S['slots'] - w_t) / 2 / r
        pts.append(V(s0 - 1, r * math.cos(th + side * half), r * math.sin(th + side * half)))
    body = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(s1 - s0 + 2, 0, 0))
    op = Part.makeBox(s1 - s0 + 2, 2.0, w_open, V(s0 - 1, Rb - 0.5, -w_open / 2))
    op.rotate(V(0, 0, 0), XA, math.degrees(th))
    slots.append(body.fuse(op))
    pc = []
    for (r, side) in ((r1 + 0.3, -1), (r2 - 0.3, -1), (r2 - 0.3, 1), (r1 + 0.3, 1)):
        half = (2 * math.pi * r / S['slots'] - w_t) / 2 / r - 0.3 / r
        pc.append(V(s0, r * math.cos(th + side * half), r * math.sin(th + side * half)))
    cu.append(Part.Face(Part.makePolygon(pc + [pc[0]])).extrude(V(s1 - s0, 0, 0)))
core = core.cut(Part.makeCompound(slots))
add('G-210_Stator_Core_12slot', core, 7.65, dict(
    description='Stator core 12 slots, ID 39 / OD 88 x 80, self-bonding laminations (no welding seams, no key)', qty=1,
    make_or_buy='buy as a bonded stack (laser cut 0.10 mm + backlack bonding) to our drawing', material_or_spec='NO10 / 10JNEX900 0.10 mm, backlack bonded',
    size_or_rating='88 h6 / 39 x 80', supplier_candidates='Kienle + Spiess (DE), Euro Group (IT); steel Cogent / Surahammar (SE), JFE (JP)',
    notes='OD ground 88.10-88.13 after bonding for the shrink fit'))
ew = [cyl(a, b, S['endwind_r'][1], S['endwind_r'][0]) for (a, b) in S['endwind']]
add('G-211_Stator_Winding_Litz', Part.makeCompound(cu).fuse(ew).removeSplitter(), 2.6, dict(
    description='Stator winding: 3-ph double layer, 12 coils x 5 turns, 5/6 pitch, Litz, slot liners Nomex 0.2, vacuum-potted end turns, '
                '3 x PT100 + 1 PTC in the end turns, leads 3 x 6 mm2 + 8 signal wires out through the lead-out slot', qty=1,
    make_or_buy='make: local motor-rewind shop (wound after the core is shrunk into G-201)', material_or_spec='Litz 0.1 mm strands, class H',
    size_or_rating='20 turns/phase, 425 V ll at 115k, 38 A', supplier_candidates='Litz: Pack Feindraehte (DE), Elektrisola (DE); resin Elantas (DE); Nomex alt.: Krempel (DE)',
    notes='end-turn envelope modelled solid'))

# ================================================================== SFD cartridges (identical) + spacer + wave spring + bearings + pins + O-rings
CA = G.CART


def cartridge(u0, sgn):
    """sgn = +1: u grows towards +x (front cartridge, lip in front); -1: towards -x (rear, lip at the rear)"""
    xa, xb = sorted((u0, u0 + sgn * CA['L']))
    c = cyl(xa, xb, CA['r_out'], CA['r_bore'])
    la, lb = sorted((u0, u0 + sgn * CA['lip']))
    c = c.fuse(cyl(la, lb, CA['r_bore'] + 0.01, CA['r_lip']))
    for (ga, gb) in CA['grooves']:
        xa_, xb_ = sorted((u0 + sgn * ga, u0 + sgn * gb))
        c = c.cut(cyl(xa_, xb_, CA['r_out'] + 1, CA['groove_r']))
    xf = u0 + sgn * CA['feed_u']
    c = c.cut(Part.makeCylinder(0.4, 6, V(xf, 0, 9.0), V(0, 0, 1)))                          # d0.8 jet (top, from the land)
    c = c.cut(Part.makeBox(CA['L'] + 2, CA['slot_w'], CA['slot_d'] + 1.0, V(xa - 1, -CA['slot_w'] / 2, -CA['r_bore'] - CA['slot_d'])))  # drain slot
    slot = Part.makeBox(CA['lip'] + 0.02, 2.2, 3.2, V(la - 0.01, -1.1, G.PIN_R - 1.5))
    slot.rotate(V(0, 0, 0), XA, 45.0 - 90.0)
    c = c.cut(slot)                                                                         # anti-rotation slot in the lip
    return c.removeSplitter()


cf = cartridge(G.CART_FRONT_U0, +1)
cr = cartridge(G.CART_REAR_U0, -1)
add('G-230_SFD_Cartridge_x2', Part.makeCompound([cf, cr]), 7.8, dict(
    description='SFD bearing cartridge (identical part front / rear): bore 22 H5, land 27.80 g5 (0.10 mm film in the 28 H6 seat), 2 O-ring grooves, '
                'd0.8 oil jet from the land, 3 mm drain slot, lip with an anti-rotation slot', qty=2,
    make_or_buy='make: lathe + internal / external grinding', material_or_spec='17-4PH H1025 (1.4542) bar d30', size_or_rating='d27.8 / 22 x 9.5',
    supplier_candidates='bar: Deutsche Edelstahlwerke (DE), Ugitech (FR); precision CNC shop',
    notes='front: lip forward + 1.5 mm ground shim G-232 (locating by the rear spring preload); rear: lip rearward + wave spring G-233'))
add('G-232_Front_Bearing_Shim', cyl(G.FRONT_SPACER['x0'], G.FRONT_SPACER['x1'], G.FRONT_SPACER['r_out'], G.FRONT_SPACER['r_in']), 7.85, dict(
    description='Ground shim 22/19.2 x 1.5 (front cartridge, between the lip and the outer ring; grind to set the rotor axial position)', qty=1,
    make_or_buy='make: surface-ground washer', material_or_spec='1.4034 hardened or 100Cr6', size_or_rating='22 / 19.2 x 1.50 (+/-0.005)',
    supplier_candidates='precision CNC shop', notes='set the magnet-to-stator axial centring to +/-0.3 mm'))
WS = G.WAVE_SPRING
add('G-233_Wave_Spring_Rear_60N', cyl(WS['x0'], WS['x1'], WS['r_out'], WS['r_in']), 7.85, dict(
    description='Single-turn wave spring OD 21.8 / ID 19.2, 60 N at 1.5 mm working height (rear bearing preload)', qty=1, make_or_buy='buy',
    material_or_spec='17-7PH / 1.4568', size_or_rating='bore 22, 60 N', supplier_candidates='TFC (UK) Crest-to-Crest, Gutekunst (DE)',
    notes='constant-force preload; replace with the bearings'))


def bearing(xc):
    return cyl(xc - 3, xc + 3, 6.7, 5.0).fuse(cyl(xc - 3, xc + 3, 11.0, 9.3)).fuse(cyl(xc - 1.6, xc + 1.6, 9.3, 6.7)).removeSplitter()
add('G-231_Bearing_71900_hybrid_x2', Part.makeCompound([bearing(G.X_GF), bearing(G.X_GR)]), 6.0, dict(
    description='Spindle bearing 10x22x6 hybrid (Si3N4 balls) 15 deg, P4, single, universal', qty=2, make_or_buy='buy',
    material_or_spec='rings 100Cr6, balls Si3N4, PEEK/phenolic cage', size_or_rating='71900 C / P4, n.dm 1.84e6',
    supplier_candidates='FAG HCB71900-C-T-P4S (DE), SKF 71900 CE/HCP4A (SE), GMN HY S61900 C TA (DE), NSK (JP)',
    notes='shaft d10 js4, cartridge bore 22 H5; replace every 8000 h'))
pins = [ax_cyl(G.CART_FRONT_U0 - 2.0, G.CART_FRONT_U0 + 1.0, G.PIN_R, 45.0, 1.0),
        ax_cyl(G.CART_REAR_U0 - 1.0, G.CART_REAR_U0 + 2.0, G.PIN_R, 45.0, 1.0)]
add('G-234_Dowel_ISO8734_2x6_x2', Part.makeCompound(pins), 7.8, dict(
    description='Anti-rotation pin, cartridge -> housing / cover', qty=2, make_or_buy='buy', material_or_spec='ISO 8734 2 m6 x 6, 1.4034 hardened',
    size_or_rating='d2 x 6', supplier_candidates='Bossard (CH), Boellhoff (DE), Halder (DE)', notes='pressed into the housing / cover, 1 mm into the lip slot'))


def oring_rect(xa, xb, ri, ro):
    return cyl(xa + 0.15, xb - 0.15, ro, ri)


ors = []
for (u0, sgn) in ((G.CART_FRONT_U0, 1), (G.CART_REAR_U0, -1)):
    for (ga, gb) in CA['grooves']:
        xa_, xb_ = sorted((u0 + sgn * ga, u0 + sgn * gb))
        ors.append(oring_rect(xa_, xb_, CA['groove_r'], L.CART_OD / 2))
add('G-235_O-ring_23.6x1.8_FKM_x4', Part.makeCompound(ors), 1.9, dict(
    description='SFD centring O-rings (4 = 2 per cartridge)', qty=4, make_or_buy='buy',
    material_or_spec='ISO 3601-1 23.6 x 1.80 class A, FKM 75 ShA', size_or_rating='groove d24.9 x 2.4 wide, squeeze 14 %, stretch 5.5 %',
    supplier_candidates='Freudenberg (DE), Trelleborg (SE), COG (DE)', notes='sets 1-2 N/um support stiffness (measure); replace at every bearing change'))
oj = [oring_rect(J['oring_front'][0], J['oring_front'][1], J['r_out1'] - J['oring_front'][2], J['r_out1']),
      oring_rect(J['oring_rear'][0], J['oring_rear'][1], J['r_out2'] - J['oring_rear'][2], J['r_out2'])]
add('G-236_O-rings_Jacket_92.5x2.65_90x2.65', Part.makeCompound(oj), 1.2, dict(
    description='Jacket O-rings: front 92.5 x 2.65 (bore 98), rear 90 x 2.65 (bore 96; stepped bore so no O-ring crosses a port)', qty=2,
    make_or_buy='buy', material_or_spec='ISO 3601-1 92.5 x 2.65 + 90 x 2.65 class A, EPDM 70 (glycol)',
    size_or_rating='groove depth 2.05, width 3.6, squeeze 23 %', supplier_candidates='Freudenberg (DE), Trelleborg (SE), COG (DE)', notes=''))
add('G-237_O-ring_Face_103x1.8', cyl(C['x_flange'][1] - gd, C['x_flange'][1], g1 - 0.15, g0 + 0.15), 1.9, dict(
    description='Face O-ring front cover / housing (seals the rotor cavity)', qty=1, make_or_buy='buy',
    material_or_spec='ISO 3601-1 103 x 1.80 class A, FKM 75', size_or_rating='groove d102.6 / 107.8 x 1.30 deep', supplier_candidates='Freudenberg (DE), COG (DE)', notes=''))

# ================================================================== ROTOR
c0, c1 = S['carrier']
m0, m1 = S['magnet']; ec = S['endcap']
add('G-220_Magnet_Carrier', cyl(c0, c1, S['carrier_r'][1], S['carrier_r'][0]), 7.85, dict(
    description='Magnet carrier d20 / bore 10 x 112', qty=1, make_or_buy='make: lathe + cylindrical grind (OD 20 h5, bore 10 H5)',
    material_or_spec='42CrMo4 QT (1.7225), bar d22', size_or_rating='d20/10 x 112', supplier_candidates='Ovako (SE), DEW (DE); precision CNC shop',
    notes='bore 10 -0.004/-0.010 on the shaft 10 js4 (2.8-11.3 um interference): heat the carrier assembly to 150 C; 60 N.m slip torque'))
add('G-221_Magnets_Sm2Co17', cyl(m0, m1, S['magnet_r'][1], S['magnet_r'][0]), 8.4, dict(
    description='Rotor magnets Sm2Co17, ring 20/30 x 82 as 2 half shells x 4 axial pieces, diametral (2-pole) magnetisation', qty=1, make_or_buy='buy',
    material_or_spec='Sm2Co17, Br >= 1.08 T, Hcj >= 1800 kA/m, Ni-free (bonded)', size_or_rating='ID 20.05 / OD 30.08 (ground for the sleeve) x 82',
    supplier_candidates='VAC VACOMAX (DE), Magnetfabrik Bonn (DE), Shin-Etsu (JP)', notes='bonded with Loctite AA 326 + activator 7649 (Henkel DE)'))
add('G-222_Carbon_Sleeve', cyl(m0 - ec, m1 + ec, S['sleeve_r'][1], S['sleeve_r'][0]), 1.6, dict(
    description='Retaining sleeve, hoop-wound carbon fibre 3 mm, pressed on the ground magnets (0.08 mm diametral interference)', qty=1,
    make_or_buy='buy (wound tube, ID ground) + press on a 1:200 conical mandrel', material_or_spec='T700 / T800 carbon-epoxy, Tg >= 180 C',
    size_or_rating='ID 30.00 / OD 36.00 x 88', supplier_candidates='fibre Toray (JP); tubes CG Tec (DE), Carbon-Werke (DE)',
    notes='hoop 417 MPa at 115k / 600 MPa at 138k, allowable 1600 MPa; OD finish-ground after pressing'))
add('G-223_End_Rings_x2', Part.makeCompound([cyl(m0 - ec, m0, S['sleeve_r'][0], S['magnet_r'][0]), cyl(m1, m1 + ec, S['sleeve_r'][0], S['magnet_r'][0])]),
    7.95, dict(description='Magnet end rings = balance planes 1 / 2 (radial d2 balance drillings, max 1.5 deep)', qty=2,
               make_or_buy='make: lathe', material_or_spec='1.4404 (non-magnetic), bar d32', size_or_rating='d30/20 x 3',
               supplier_candidates='precision CNC shop', notes='pressed on the carrier, Loctite 648'))
gs = [(L.GSHAFT[0][1], 0.0)]
for name, x0, x1, r in L.GSHAFT:
    gs += [(x0, r), (x1, r)]
gs += [(L.GSHAFT[-1][2], 0.0)]
sh = rev(gs)
for xt in (-129.5, -128.0, -126.5):
    sh = sh.fuse(cyl(xt, xt + 0.5, 7.6, 6.9))
skt = L.QUILL['socket']
sh = sh.cut(hexprism(skt[0], skt[1] + 0.01, L.QUILL['hex_AF'] + 0.02))                    # AF6 socket (rotary broached)
sh = sh.cut(Part.makeCone(3.47, 4.05, 1.0, V(skt[1] - 1.0, 0, 0), XA))                   # 30 deg lead-in at the socket mouth
sh = sh.cut(Part.makeCylinder(3.05, 2.0, V(skt[0] - 2.0, 0, 0), XA))                      # d6.1 pre-drill run-out for the rotary broach
sh = sh.cut(hexprism(L.GSHAFT[0][1] - 0.01, L.GSHAFT[0][1] + 6.0, 5.0))                     # AF5 turning socket in the front end
add('G-224_Gen_Shaft_Quill_d6x54', sh.removeSplitter(), 7.8, dict(
    description='Generator through-shaft d10 + collar d14 (3 teeth) + quill waist d6 x 54 + socket hub OD 12 with internal AF6 x 12 (30 deg lead-in) '
                '+ AF5 turning socket in the front end; one piece', qty=1,
    make_or_buy='make: lathe + cylindrical grinding (journals d10 js4, waist polished Ra 0.2, R3 fillets, shot-peened); AF6 and AF5 rotary-broached; '
                'socket plasma-nitrided', material_or_spec='17-4PH H1025 (1.4542), bar d16 x 245', size_or_rating='d14 / 10 / 6 x 235.5',
    supplier_candidates='bar: DEW (DE), Ugitech (FR); rotary broach Hommel+Keller (DE); nitriding Buderus / Bodycote-EU (DE)',
    notes='the quill is a fuse: tau 50 MPa rated, 200 MPa at a x4 fault; a broken quill = replace this part (rebalance the rotor)'))
for name, x0, x1, ri, ro in L.GCLAMP:
    if 'locknut' in name:
        nut = cyl(x0, x1, G.LOCKNUT['r_out'], ri).cut(hexprism(x0 - 1, x1 + 1, 30.0).cut(hexprism(x0 - 2, x1 + 2, 16.0)))   # AF16 flats
        add('G-225_Locknut_M10x0.75_OD18', nut, 7.85, dict(
            description='Rotor locknut M10x0.75, OD 18 x 6 with AF16 flats, 2 radial M3 locking set screws (ISO 4026 M3x4 A4 with a brass pad), '
                        '2 x Sm2Co5 d3 x 2 Hall-target magnets bonded in the front face at r 7', qty=1,
            make_or_buy='make: lathe + mill flats (OD 18 passes the cartridge lip; standard KM0 + MB0 washer would not)',
            material_or_spec='17-4PH H1025, bar d20', size_or_rating='M10x0.75 6H, 10 N.m (stack clamp ~6 kN), set screws 0.6 N.m',
            supplier_candidates='precision CNC shop; set screws Bossard (CH)', notes='right-hand thread is fine (no drive torque through it)'))
    elif 'front' in name:
        sp = []
        for (xa, xb) in ((-263.0, -257.0), (-145.0, -139.0)):
            s_ = cyl(xa, xb, ro, ri)
            for k in range(3):
                s_ = s_.fuse(cyl(xa + 1.0 + 1.6 * k, xa + 1.5 + 1.6 * k, 7.6, 6.9))
            sp.append(s_.removeSplitter())
        add('G-226_Seal_Spacer_x2', Part.makeCompound(sp), 7.8, dict(
            description='Seal spacer d14 / 10 x 6 with 3 labyrinth teeth d15.2 (identical front / rear)', qty=2, make_or_buy='make: lathe + grind faces',
            material_or_spec='17-4PH H1025, bar d16', size_or_rating='d15.2/10 x 6', supplier_candidates='precision CNC shop',
            notes='faces parallel 2 um (stack element); radial clearance to the d15.7 bores 0.25'))

# ================================================================== QUILL GUARD, TERMINAL BOX, FITTINGS, PLUGS
QG = G.QUILL_GUARD
add('G-150_Quill_Guard_Tube', cyl(QG['x0'], QG['x1'], QG['r_out'], QG['r_in']), 2.70, dict(
    description='Quill guard: plain tube 20 x 1.5 x 52, pressed 8 mm into the housing rear-face counterbore (Loctite 638), stationary', qty=1,
    make_or_buy='make: cut from tube + face', material_or_spec='EN AW-6060-T66 tube 20 x 1.5', size_or_rating='d20 x 1.5 x 52',
    supplier_candidates='Alu Menziken (CH), local', notes='was a flanged part with 3 screws'))
TB = G.TBOX
bx0, bx1 = TB['x']; by0, by1 = TB['y']; bz0, bz1 = TB['z_body']; w = TB['wall']
box = Part.makeBox(bx1 - bx0, by1 - by0, bz1 - bz0 + 2.0, V(bx0, by0, bz0 - 8.0))
box = box.cut(Part.makeCylinder(bz0, bx1 - bx0 + 2, V(bx0 - 1, 0, 0), XA))                         # saddle r 56 (on a 1 mm gasket)
box = box.cut(Part.makeBox(bx1 - bx0 + 2, by1 - by0 + 2, 10.0, V(bx0 - 1, by0 - 1, bz1)))          # trim top to z 92
pocket = Part.makeBox(bx1 - bx0 - 2 * w, by1 - by0 - 2 * w, bz1 - TB['floor_top'] + 1, V(bx0 + w, by0 + w, TB['floor_top']))
for (cx, cy) in TB['lid_screws']:                                                                  # keep 6 x 6 corner columns
    pocket = pocket.cut(Part.makeBox(6.0, 6.0, 40.0, V(cx - 3.0, cy - 3.0, TB['floor_top'] - 1)))
box = box.cut(pocket)
box = box.cut(Part.makeBox(G.H['lead_slot'][1] - G.H['lead_slot'][0] + 1.0, 2 * G.H['lead_slot'][2] + 1.0, 20.0,
                           V(G.H['lead_slot'][0] - 0.5, -G.H['lead_slot'][2] - 0.5, 45.0)))       # opening over the lead-out slot
for (x, y) in TB['screws']:
    box = box.cut(Part.makeCylinder(2.25, 20.0, V(x, y, 45.0), V(0, 0, 1)))                         # d4.5 floor holes
for (cx, cy) in TB['lid_screws']:
    box = box.cut(Part.makeCylinder(1.5, 8.0, V(cx, cy, bz1 - 7.9), V(0, 0, 1)))                    # M3 Helicoil 1.5D
box = box.cut(Part.makeCylinder(12.5, 6.0, V(bx0 - 1, TB['gland_power'][0], TB['gland_power'][1]), XA))             # M25 (front face)
box = box.cut(Part.makeCylinder(8.0, 6.0, V(TB['gland_signal'][0], by1 - 4.0, TB['gland_signal'][1]), V(0, 1, 0)))   # M16 (+y side)
for (x, y) in ((-192.0, 8.0), (-172.0, 8.0)):
    box = box.cut(Part.makeCylinder(2.0, 4.0, V(x, y, TB['floor_top'] - 3.9), V(0, 0, 1)))          # M4 tapped (PEEK block)
add('G-240_Terminal_Box_Body', box.removeSplitter(), 2.70, dict(
    description='Terminal box body: milled pocket 58 x 46 x 32, 3 mm walls, saddle r 56 underside, opening over the lead-out slot, '
                '4 corner columns (M3 Helicoil for the lid), 4 x d4.5 floor holes, M25 + M16 gland holes in the front face', qty=1,
    make_or_buy='make: 3-axis CNC mill from a block', material_or_spec='EN AW-6082-T6, block 70 x 55 x 50', size_or_rating='64 x 52 x 36',
    supplier_candidates='precision CNC shop', notes='IP66 with gaskets G-243 / G-244'))
add('G-241_Terminal_Box_Lid', Part.makeBox(bx1 - bx0, by1 - by0, 3.0, V(bx0, by0, TB['z_lid'][0])).cut(
    Part.makeCompound([Part.makeCylinder(1.7, 5.0, V(cx, cy, TB['z_lid'][0] - 1), V(0, 0, 1)) for (cx, cy) in TB['lid_screws']])), 2.70, dict(
    description='Terminal box lid 64 x 52 x 3', qty=1, make_or_buy='make: laser / mill', material_or_spec='EN AW-5754 sheet 3 mm',
    size_or_rating='64 x 52 x 3', supplier_candidates='local', notes='4 x d3.4'))
STUDS = ((-189.0, -8.0), (-182.0, 8.0), (-175.0, -8.0))
blk = Part.makeBox(28.0, 32.0, 10.0, V(-196.0, -16.0, TB['floor_top'])).cut(
    Part.makeCompound([Part.makeCylinder(2.2, 12, V(x, y, TB['floor_top'] - 1), V(0, 0, 1)) for (x, y) in ((-192.0, 8.0), (-172.0, 8.0))] +
                      [Part.makeCylinder(3.0, 12, V(x, y, TB['floor_top'] - 1), V(0, 0, 1)) for (x, y) in STUDS]))
add('G-242_Terminal_Block_PEEK', blk, 1.32, dict(
    description='Phase terminal block 28 x 32 x 10 with 3 pressed-in M6 brass studs (G-251, triangle pitch 14-17), 2 x M4 to the box floor', qty=1,
    make_or_buy='make: mill', material_or_spec='PEEK natural (or PA66-GF30)', size_or_rating='28 x 32 x 10', supplier_candidates='Ensinger (DE), Roechling (DE)', notes=''))
gk = Part.makeBox(bx1 - bx0, by1 - by0, 20.0, V(bx0, by0, 40.0)).common(cyl(bx0, bx1, 56.0, 55.0))
gk = gk.cut(Part.makeBox(bx1 - bx0 - 2 * w, by1 - by0 - 2 * w, 30.0, V(bx0 + w, by0 + w, 35.0)))
add('G-243_Gasket_Box_Base', gk, 1.2, dict(description='Box base gasket, 1 mm EPDM die-cut frame (saddle)', qty=1, make_or_buy='buy (die-cut)',
                                          material_or_spec='EPDM 60 ShA sheet 1 mm', size_or_rating='64 x 52 frame 3 wide', supplier_candidates='Freudenberg (DE), local gasket cutter', notes=''))
gl = Part.makeBox(bx1 - bx0, by1 - by0, 1.0, V(bx0, by0, TB['z_body'][1])).cut(Part.makeBox(bx1 - bx0 - 2 * w, by1 - by0 - 2 * w, 3.0, V(bx0 + w, by0 + w, TB['z_body'][1] - 1)))
for (cx, cy) in TB['lid_screws']:
    gl = gl.fuse(Part.makeBox(6.0, 6.0, 1.0, V(cx - 3.0, cy - 3.0, TB['z_body'][1]))).cut(Part.makeCylinder(1.7, 3, V(cx, cy, TB['z_body'][1] - 1), V(0, 0, 1)))
add('G-244_Gasket_Box_Lid', gl.removeSplitter(), 1.2, dict(description='Lid gasket 1 mm EPDM die-cut', qty=1, make_or_buy='buy (die-cut)',
                                                          material_or_spec='EPDM 60 ShA 1 mm', size_or_rating='64 x 52', supplier_candidates='local gasket cutter', notes=''))
grom = Part.makeBox(G.H['lead_slot'][1] - G.H['lead_slot'][0], 2 * G.H['lead_slot'][2], 55.0 - 48.6, V(G.H['lead_slot'][0], -G.H['lead_slot'][2], 48.6))
grom = grom.cut(Part.makeCylinder(48.5, 30, V(G.H['lead_slot'][0] - 1, 0, 0), XA))
add('G-245_Lead-out_Seal', grom, 1.2, dict(description='Lead-out seal: silicone potting in the 8 x 24 slot round the 3 phase leads + signal wires', qty=1,
                                          make_or_buy='make in place (pot after winding)', material_or_spec='RTV-2 silicone, 200 C', size_or_rating='8 x 24 x 6',
                                          supplier_candidates='Wacker Elastosil RT 601 (DE)', notes=''))

# ---------------------------------------------------------------- fasteners / purchased small parts (envelopes)
f = [screw_axial(C['x_flange'][0], R_P, a, 5.0, 12.0, 8.5, 5.0, +1) for a in FH['screws']]
add('G-250_Screws_ISO4762_M5x12_x6', Part.makeCompound(f), 7.9, dict(
    description='Front cover -> housing: 6 x ISO 4762 M5 x 12 A4-80 + 6 x Helicoil M5 x 1.5D (free-running, 1.4301) in G-200', qty=6, make_or_buy='buy',
    material_or_spec='ISO 4762 A4-80 + HELICOIL plus free-running M5 x 1.5D (DIN 8140, 1.4301)', size_or_rating='4.2 N.m (preload ~4.3 kN), Loctite 243',
    supplier_candidates='Bossard (CH), Boellhoff (DE), Wuerth (DE)', notes='tighten crosswise in 2 steps'))
dw = [ax_cyl(C['x_flange'][0], C['x_flange'][0] + 12.0, R_P, a, 2.0) for a in FH['dowels']]
add('G-252_Dowels_ISO8734_4x12_x2', Part.makeCompound(dw), 7.8, dict(
    description='Cover / housing alignment dowels', qty=2, make_or_buy='buy', material_or_spec='ISO 8734 4 m6 x 12, 1.4034 hardened',
    size_or_rating='d4 x 12 (8 in G-200, 4 in G-202)', supplier_candidates='Bossard (CH), Halder (DE)', notes='pressed in G-200 (H7), slip in G-202 (H7)'))
bs = []
for (x, y) in TB['screws']:
    bs.append(screw_z(x, y, TB['floor_top'], 4.0, 10.0, 7.6, 2.2))
add('G-253_Screws_ISO7380_M4x10_x4', Part.makeCompound(bs), 7.9, dict(
    description='Terminal box -> housing: 4 x ISO 7380 M4 x 10 A4-80 + 4 x Helicoil M4 x 1D (blind 5.0) in G-200', qty=4, make_or_buy='buy',
    material_or_spec='ISO 7380-1 A4-80, Helicoil M4 x 4', size_or_rating='1.7 N.m, Loctite 243', supplier_candidates='Bossard (CH), Wuerth (DE)', notes=''))
ls = [screw_z(cx, cy, TB['z_lid'][1], 3.0, 8.0, 5.7, 1.65) for (cx, cy) in TB['lid_screws']]
add('G-254_Screws_ISO7380_M3x8_x4', Part.makeCompound(ls), 7.9, dict(
    description='Lid screws 4 x ISO 7380 M3 x 8 A4-80 + 4 x Helicoil M3 x 1.5D in the box columns', qty=4, make_or_buy='buy',
    material_or_spec='ISO 7380-1 A4-80', size_or_rating='0.6 N.m', supplier_candidates='Bossard (CH), Wuerth (DE)', notes=''))
ps = [screw_z(x, y, TB['floor_top'] + 10.0, 4.0, 13.0, 7.6, 2.2) for (x, y) in ((-192.0, 8.0), (-172.0, 8.0))]
add('G-255_Screws_ISO7380_M4x12_x2', Part.makeCompound(ps), 7.9, dict(
    description='PEEK block -> box floor: 2 x ISO 7380 M4 x 14 A2-70, tapped direct in the 4 mm Al floor, Loctite 243', qty=2,
    make_or_buy='buy', material_or_spec='ISO 7380-1 A2-70', size_or_rating='0.8 N.m', supplier_candidates='Bossard (CH), Wuerth (DE)', notes=''))
st = []
for (x, y) in STUDS:
    st.append(Part.makeCylinder(3.0, 20.0, V(x, y, TB['floor_top']), V(0, 0, 1)).fuse(
        Part.makeCylinder(5.5, 5.0, V(x, y, TB['floor_top'] + 10.0), V(0, 0, 1))))
add('G-251_Phase_Studs_M6_x3', Part.makeCompound(st), 8.5, dict(
    description='3 x M6 x 20 brass studs (knurled, pressed in G-242) + 6 x ISO 4032 M6 brass nuts + 6 x ISO 7089 washers + 3 spring washers; '
                'winding leads and the power cable on DIN 46234 M6 ring lugs', qty=3, make_or_buy='buy',
    material_or_spec='CuZn39Pb3 brass studs / nuts, Sn-plated', size_or_rating='M6, nuts 2.0 N.m', supplier_candidates='Wuerth (DE), Bossard (CH); lugs Klauke (DE)', notes=''))
gp = Part.makeCylinder(15.0, 18.0, V(bx0 - 18.0, TB['gland_power'][0], TB['gland_power'][1]), XA)
gs_ = Part.makeCylinder(10.0, 15.0, V(TB['gland_signal'][0], by1, TB['gland_signal'][1]), V(0, 1, 0))
add('G-256_Cable_Glands_M25_M16', Part.makeCompound([gp, gs_]), 3.0, dict(
    description='EMC cable glands: M25 x 1.5 (power, clamping 11-17, 360 deg shield contact) + M16 x 1.5 (PT100/PTC signal) with lock nuts', qty=2,
    make_or_buy='buy', material_or_spec='nickel-plated brass, IP68', size_or_rating='M25x1.5 / M16x1.5', supplier_candidates='Lapp SKINTOP MS-SC-M (DE), Pflitsch blueglobe (DE)',
    notes='power cable 3 x 6 mm2 + PE shielded (e.g. Lapp OELFLEX SERVO 2YSLCY-JB 4G6) -> AUX EL-513 re-route to the front face z 76'))
fit = []
for name, (x, a, kind, w) in G.PORTS.items():
    if kind == 'g14' and 'glycol' in name:
        rt = G.BOSS[kind][1]
        fit.append(rad_cyl(x, a, rt, rt + 6.0, 7.5).fuse(rad_cyl(x, a, rt + 6.0, rt + 24.0, 5.0)))
add('G-257_Glycol_Hose_Nipples_G14_x2', Part.makeCompound(fit), 8.5, dict(
    description='Glycol ports: 2 x straight hose nipple G1/4 male (ISO 228-1, ED seal ISO 1179-2 form E) for 8 mm ID hose + hose clips', qty=2,
    make_or_buy='buy', material_or_spec='1.4404 or nickel-plated brass, EPDM ED ring', size_or_rating='G1/4 - 8 mm, 15 N.m',
    supplier_candidates='Landefeld (DE), Riegler (DE); clips Oetiker (CH)', notes='at 135 deg, x -244 (in) / -170.5 (out), towards the AUX skid'))
plug = Part.makeCylinder(8.0, 4.0, V(C['x0'], 0, 0), XA).fuse(Part.makeCylinder(11.0, 3.0, V(C['x0'] - 3.0, 0, 0), XA))
add('G-258_Plug_DIN908_M16x1.5', plug, 7.85, dict(
    description='Front access plug DIN 908 M16 x 1.5 with ED sealing ring: remove to turn the rotor with an AF5 key (hex alignment) or to push the front cartridge out',
    qty=1, make_or_buy='buy', material_or_spec='DIN 908 steel zinc-plated + ED ring NBR/FKM', size_or_rating='M16x1.5, 25 N.m',
    supplier_candidates='Landefeld (DE), Riegler (DE)', notes=''))
jp = [ax_cyl(H['x1'] - 6.0, H['x1'], 46.5, a, 2.5) for a in (0.0, 180.0)]
add('G-259_Jack-hole_Plugs_M5_x2', Part.makeCompound(jp), 7.9, dict(
    description='2 x ISO 4026 M5 x 6 A4 set screws + Loctite 542 sealing the jacket jack-out holes in the rear face', qty=2, make_or_buy='buy',
    material_or_spec='ISO 4026 A4', size_or_rating='M5 x 6, 1.3 N.m', supplier_candidates='Bossard (CH), Wuerth (DE)', notes='remove only to push the jacket + stator out'))

# ---------------------------------------------------------------- bom-only items (Helicoil kits, adhesives, consumables, tools)
bom_only('G-260', description='Helicoil plus free-running inserts (1.4301): 6 x M5x1.5D (flange), 3 x M6x2D (struts), 3 x M4x1.5D (fairing), '
                              '4 x M4x1D (box), 2 x M6x1D (VE-011/012), 4 x M3x1.5D (lid), 2 x M5x1.5D (jack-off, G-202)', qty=24, make_or_buy='buy',
         material_or_spec='DIN 8140, 1.4301', size_or_rating='M3..M6', supplier_candidates='Boellhoff HELICOIL (DE)', mass_kg=0.01,
         notes='install with the Boellhoff hand tool, break the tang; tap STI per Boellhoff table')
bom_only('G-261', description='Adhesives / thread-lockers: Loctite 243 (screws), 638 (guard tube), 648 (end rings), 542 (jack plugs), AA 326 + 7649 (magnets)',
         qty=1, make_or_buy='buy', material_or_spec='Henkel Loctite', size_or_rating='', supplier_candidates='Henkel (DE)', mass_kg=0, notes='')
bom_only('G-262', description='Hall target magnets in the locknut: 2 x Sm2Co5 d3 x 2 (N/S opposite), bonded Loctite AA 326', qty=2, make_or_buy='buy',
         material_or_spec='SmCo5', size_or_rating='d3 x 2', supplier_candidates='VAC (DE), Magnetfabrik Bonn (DE)', mass_kg=0.0003, notes='2 pulses/rev; balance-neutral pair')
bom_only('G-263', description='Ring lugs DIN 46234 M6 for 6 mm2 (3 winding + 3 cable) + 8-pole spring terminal block for 3 x PT100 + PTC (Phoenix Contact PTFIX / WAGO 2002)',
         qty=1, make_or_buy='buy', material_or_spec='Sn-plated Cu / PA', size_or_rating='', supplier_candidates='Klauke (DE), Phoenix Contact (DE), WAGO (DE)', mass_kg=0.03, notes='')
bom_only('G-264', description='Generator rotor balancing service: 2 planes (G-223 end rings), G1 target / G2.5 limit at 115k, on its own bearings', qty=1,
         make_or_buy='service', material_or_spec='ISO 21940-11', size_or_rating='U_per <= 0.056 g.mm total (G1)', supplier_candidates='Schenck RoTec (DE) machine or local turbo-balancing shop',
         mass_kg=0, notes='re-balance after any magnet / sleeve / shaft work')

# ================================================================== EXPORT + JSON + BOM
info = dict(note='D2 generator pod, buildable detail (d2g rev)', frame='ENG mm', parts={})
mtot, mx = 0.0, 0.0
mrot = 0.0
ROT = ('G-220', 'G-221', 'G-222', 'G-223', 'G-224', 'G-225', 'G-226')
for k, (s, rho, out) in parts.items():
    s.exportStep(os.path.join(out, k + '.step'))
    bb = s.BoundBox
    m = s.Volume * rho * 1e-6
    sols = s.Solids if s.Solids else [s]
    vt = sum(so.Volume for so in sols)
    xc = sum(so.Volume * so.CenterOfMass.x for so in sols) / vt if vt > 0 else bb.Center.x
    info['parts'][k] = dict(valid=s.isValid(), dir=os.path.relpath(out, ROOT), x=[round(bb.XMin, 2), round(bb.XMax, 2)],
                            z=[round(bb.ZMin, 1), round(bb.ZMax, 1)], mass_kg=round(m, 4), x_cg=round(xc, 1))
    mtot += m; mx += m * xc
    if k[:5] in ROT:
        mrot += m
    print('%-44s valid %s  x %.1f..%.1f  %.4f kg' % (k, s.isValid(), bb.XMin, bb.XMax, m))
info['pod_mass_kg'] = round(mtot, 3)
info['pod_x_cg'] = round(mx / mtot, 1)
info['generator_rotor_mass_kg'] = round(mrot, 3)
info['moved_aux_ports'] = G.MOVED_PORTS
info['ports'] = {k: dict(x=v[0], angle_deg=v[1], kind=v[2], part='G-200' if v[3] == 'H' else 'G-202') for k, v in G.PORTS.items()}
json.dump(info, open(os.path.join(OUT, 'd2r_generator_parts.json'), 'w'), indent=1)
json.dump(dict(note='D2 pod shell = G-200 housing + G-202 front cover (d2g rev, replaces D-101P / D-102P); ports and moves listed', ports=info['ports'],
               moved=G.MOVED_PORTS, valid=[info['parts']['G-200_Pod_Housing']['valid'], info['parts']['G-202_Front_Cover']['valid']],
               mass_kg_Al=[info['parts']['G-200_Pod_Housing']['mass_kg'], info['parts']['G-202_Front_Cover']['mass_kg']]),
          open(os.path.join(POD_OUT, 'd2a_pod_ports.json'), 'w'), indent=1)
print('pod total %.3f kg, x_cg %.1f, rotor %.3f kg' % (mtot, mx / mtot, mrot))

rows = []
for b in BOM:
    k = b['model']
    mass = b.get('mass_kg', '')
    mf = ''
    if k:
        q = b['qty'] if isinstance(b['qty'], int) else 1
        mass = round(info['parts'][k]['mass_kg'] / max(q, 1), 4)                       # per unit
        mf = os.path.relpath(os.path.join(b['out'], k + '.step'), ROOT)
    rows.append([b['tag'], b['description'], b['qty'], b['make_or_buy'], b['material_or_spec'], b['size_or_rating'],
                 b['supplier_candidates'], mass, mf, b.get('notes', '')])
with open(os.path.join(ROOT, 'docs', 'bom', 'variant_d2_generator_bom.csv'), 'w', newline='') as fh:
    wcsv = csv.writer(fh)
    wcsv.writerow(['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes'])
    wcsv.writerows(rows)
print('BOM rows', len(rows), '-> docs/bom/variant_d2_generator_bom.csv')
