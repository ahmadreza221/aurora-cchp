# GR180 version D2 - GENERATOR pod internals (D2R): 2-pole Sm2Co17 PMG (rotor d36: magnets d20/d30 on a d20/d10 steel carrier,
# 3 mm carbon sleeve), 12-slot stator d39/d88 x 80 in an Al glycol-jacket sleeve (pressed in the d98 pod bore), d10
# through-shaft with integral collar + d6 x 58 quill + socket hub (internal AF6 on the crowned AF6 engine-shaft nose hex),
# two 10x22x6 hybrid bearings at x -266 / -136 in SFD cartridges, front / rear end shields with oil jets and labyrinths,
# front bearing cover, KM0 locknut, seal spacers, stationary quill guard tube, terminal box, glycol ports.
# Numbers: sim/variant_d/d2r_pmg.py, sim/variant_d/d2r_rotor.py; layout cad/variant_d/d2r_layout.py.  ENG frame mm.
# Pod shell = cad_out/variant_d/D-101 / D-102 (d_concept.py, bore 98, OD 110): needs 2 x G1/4 glycol ports, an M20 cable hole
# under the terminal box and 2 oil drains at the bottom (x -266 / -136) - listed in the BOM, not cut here.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2r_generator.py -> cad_out/variant_d/D2/GENERATOR/*.step + d2r_generator_parts.json
import FreeCAD as App, Part, os, sys, json, math
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2r_layout as L
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2', 'GENERATOR'); os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith('.step'):
        os.remove(os.path.join(OUT, f))
XA = V(1, 0, 0)


def rev(pts):
    p = [V(x, 0, r) for x, r in pts] + [V(pts[0][0], 0, pts[0][1])]
    return Part.Face(Part.makePolygon(p)).revolve(V(0, 0, 0), XA, 360)


def cyl(x0, x1, r, ri=0.0):
    s = Part.makeCylinder(r, x1 - x0, V(x0, 0, 0), XA)
    return s.cut(Part.makeCylinder(ri, x1 - x0 + 2, V(x0 - 1, 0, 0), XA)) if ri > 0 else s


def hexprism(x0, x1, af):
    r = af / math.sqrt(3)
    pts = [V(x0, r * math.cos(math.radians(30 + 60 * k)), r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0))


G = L.GEN
parts = {}
# ---------------------------------------------------------------- G-201 glycol jacket sleeve (Al), helical groove shown as rings
j0, j1 = G['jacket']
jk = cyl(j0, j1, G['jacket_r'][1], G['jacket_r'][0])
for k in range(9):                                                  # 9 turns pitch 11, groove 8 x 3 (helix modelled as rings)
    xg = j0 + 8.0 + 11.0 * k
    jk = jk.cut(cyl(xg, xg + 8.0, G['jacket_r'][1] + 1, G['groove_r']))
for xo in (j0 + 2.0, j1 - 4.5):                                     # O-ring grooves
    jk = jk.cut(cyl(xo, xo + 2.5, G['jacket_r'][1] + 1, G['jacket_r'][1] - 1.6))
parts['G-201_Glycol_Jacket_Sleeve'] = (jk, 2.70, 'Al 6082-T6 turned, helical groove 8 x 3 mm pitch 11 (9 turns), 2 x O-ring 94 x 2 EPDM, pressed in the pod bore 98 H7')

# ---------------------------------------------------------------- G-210 stator core + G-211 winding
s0, s1 = G['stack']
Rb, Ro = G['stator_id'] / 2, G['stator_od'] / 2
core = cyl(s0, s1, Ro, Rb)
slots, cu = [], []
d_slot, w_open, w_t = 17.3, 2.0, 3.63
for k in range(G['slots']):
    th = 2 * math.pi * (k + 0.5) / G['slots']
    # slot body: wedge between two teeth from r Rb+1 to Rb+d_slot, opening 2 mm at the bore
    pts = []
    r1, r2 = Rb + 1.0, Rb + d_slot
    for (r, side) in ((r1, -1), (r2, -1), (r2, 1), (r1, 1)):
        half = (2 * math.pi * r / G['slots'] - w_t) / 2 / r
        pts.append(V(s0 - 1, r * math.cos(th + side * half), r * math.sin(th + side * half)))
    body = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(s1 - s0 + 2, 0, 0))
    op = Part.makeBox(s1 - s0 + 2, 2.0, w_open, V(s0 - 1, Rb - 0.5, -w_open / 2))
    op.rotate(V(0, 0, 0), XA, math.degrees(th))
    slots.append(body.fuse(op))
    # copper inside the slot body (0.3 liner)
    pc = []
    for (r, side) in ((r1 + 0.3, -1), (r2 - 0.3, -1), (r2 - 0.3, 1), (r1 + 0.3, 1)):
        half = (2 * math.pi * r / G['slots'] - w_t) / 2 / r - 0.3 / r
        pc.append(V(s0, r * math.cos(th + side * half), r * math.sin(th + side * half)))
    cu.append(Part.Face(Part.makePolygon(pc + [pc[0]])).extrude(V(s1 - s0, 0, 0)))
core = core.cut(Part.makeCompound(slots))
parts['G-210_Stator_Core_12slot'] = (core, 7.65, '0.10 mm NO10 (Cogent/Surahammar SE) or 10JNEX900 (JFE, JP) laminations, laser cut + bonded stack 80 mm, shrunk into G-201')
ew = [cyl(a, b, G['endwind_r'][1], G['endwind_r'][0]) for (a, b) in G['endwind']]
parts['G-211_Stator_Winding_Litz'] = (Part.makeCompound(cu).fuse(ew).removeSplitter(), 2.6,
                                      'Litz 0.1 mm strands, 12 coils x 5 turns, 3-ph 5/6 pitch, class H, vacuum-potted end turns, 3 x PT100 + 1 x PTC')

# ---------------------------------------------------------------- rotor
c0, c1 = G['carrier']
m0, m1 = G['magnet']; ec = G['endcap']
parts['G-220_Magnet_Carrier'] = (cyl(c0, c1, G['carrier_r'][1], G['carrier_r'][0]), 7.85, '42CrMo4 QT, bore 10 H5 (light interference), faces ground')
parts['G-221_Magnets_Sm2Co17'] = (cyl(m0, m1, G['magnet_r'][1], G['magnet_r'][0]), 8.4, 'Sm2Co17 ring 20/30 x 82, 2 halves x 4 axial segments, diametral magnetisation, bonded')
parts['G-222_Carbon_Sleeve'] = (cyl(m0 - ec, m1 + ec, G['sleeve_r'][1], G['sleeve_r'][0]), 1.6, 'T700/T800 hoop-wound carbon-epoxy 3 mm, 0.08 mm interference')
parts['G-223_End_Rings_Ti_x2'] = (Part.makeCompound([cyl(m0 - ec, m0, G['sleeve_r'][0], G['magnet_r'][0]), cyl(m1, m1 + ec, G['sleeve_r'][0], G['magnet_r'][0])]),
                                  4.43, 'Ti6Al4V end rings (balance correction drillings)')

# ---------------------------------------------------------------- G-224 generator through-shaft with integral collar, quill, socket hub
prof = [(L.GSHAFT[0][1], 0.0)]
for name, x0, x1, r in L.GSHAFT:
    prof += [(x0, r), (x1, r)]
prof += [(L.GSHAFT[-1][2], 0.0)]
gs = rev(prof)
for xt in (-130.8, -129.6):                                          # collar labyrinth teeth (in the G-204 seal bore r 7.85)
    gs = gs.fuse(cyl(xt, xt + 0.5, 7.6, 6.9))
sk = L.QUILL['socket']
gs = gs.cut(hexprism(sk[0], sk[1] + 0.01, L.QUILL['hex_AF'] + 0.04))   # internal AF6 socket (0.02 flank clearance each side)
parts['G-224_Gen_Shaft_Quill_d6x58'] = (gs.removeSplitter(), 7.8,
                                        '17-4PH H900 (or 34CrNiMo6 QT), one piece: d10 shaft + collar + d6 x 58 waist (R3, shot-peened) + socket hub OD12 '
                                        'with internal AF6 (wire-EDM, nitrided/DLC)')
for name, x0, x1, ri, ro in L.GCLAMP:
    if 'locknut' in name:
        parts['G-225_Locknut_KM0'] = (cyl(x0, x1, ro, ri), 7.85, 'precision locknut KM0 M10x0.75 (or GUK/ KMT0 type), 4 mm')
    elif 'front' in name:
        s = cyl(x0, x1, ro, ri)
        for k in range(3):
            s = s.fuse(cyl(x0 + 1.0 + 1.6 * k, x0 + 1.5 + 1.6 * k, 7.6, 6.9))
        parts['G-226_Seal_Spacer_Front'] = (s.removeSplitter(), 7.85, '17-4PH, 3 labyrinth teeth')
    else:
        s = cyl(x0, x1, ro, ri)
        for k in range(3):
            s = s.fuse(cyl(x0 + 1.0 + 1.6 * k, x0 + 1.5 + 1.6 * k, 7.6, 6.9))
        parts['G-227_Seal_Spacer_Rear'] = (s.removeSplitter(), 7.85, '17-4PH, 3 labyrinth teeth')


def bearing(xc):
    return cyl(xc - 3, xc + 3, 6.7, 5.0).fuse(cyl(xc - 3, xc + 3, 11.0, 9.3)).fuse(cyl(xc - 1.6, xc + 1.6, 9.3, 6.7)).removeSplitter()
parts['G-230_Bearing_Front_71900_hybrid'] = (bearing(L.X_GF), 6.0, '10x22x6 hybrid 15 deg P4, locating')
parts['G-231_Bearing_Rear_71900_hybrid'] = (bearing(L.X_GR), 6.0, '10x22x6 hybrid 15 deg P4, floating + 40 N wave spring')
RC = L.CART_OD / 2 - L.SFD_C


def cartridge(x0, x1, lips, grooves):
    c = cyl(x0, x1, RC, 11.0)
    for (a, b) in lips:
        c = c.fuse(cyl(a, b, 11.01, 9.6))
    for (a, b) in grooves:
        c = c.cut(cyl(a, b, RC + 1, 12.7))
    c = c.cut(Part.makeCylinder(0.4, 5, V(0.5 * (x0 + x1), 0, 9.0), V(0, 0, 1)))
    c = c.cut(Part.makeCylinder(1.0, 5, V(0.5 * (x0 + x1), 0, -14.5), V(0, 0, 1)))
    return c.removeSplitter()
parts['G-232_SFD_Cartridge_Front'] = (cartridge(-270.0, -262.0, [(-270.0, -269.0), (-263.0, -262.0)], [(-268.6, -267.2), (-264.8, -263.4)]), 7.85,
                                      '17-4PH H1025, land 27.80, OR clamped (locating) between the front lip and a retaining ring (rear stop modelled as a lip), 2 FKM O-rings 25 x 1.5')
parts['G-233_SFD_Cartridge_Rear'] = (cartridge(-141.0, -131.0, [(-131.8, -131.0)], [(-138.6, -137.2), (-134.8, -133.4)]), 7.85,
                                     '17-4PH H1025, open at the front (rotor + bearing enter from the front), OR sliding (floating), land 27.80, 2 FKM O-rings')
parts['G-234_Wave_Spring_Rear_40N'] = (cyl(-133.0, -131.8, 11.0, 9.6), 7.85, 'wave spring 22 x 19.2, 40 N')

# ---------------------------------------------------------------- end shields + front cover
f0, f1 = G['front_shield']
fs = rev([(f0, 7.85), (f0, 49.0), (f0 + 5.0, 49.0), (f0 + 5.0, 44.5), (f0 + 6.0, 44.5), (f0 + 6.0, 21.0), (f1, 21.0), (f1, 7.85)])
fs = fs.cut(cyl(f0 - 1, -262.0, 14.0))                                   # cartridge bore 28 H6 (x -272..-262)
fs = fs.cut(Part.makeCylinder(0.75, 30, V(L.X_GF, 0, 14.0), V(0, 0, 1)))   # oil-jet feed from the top
fs = fs.cut(Part.makeCylinder(2.0, 40, V(L.X_GF + 3.0, 0, -46.0), V(0, 0, 1)))   # drain to the pod bottom
parts['G-202_Front_End_Shield'] = (fs, 2.70, 'Al 6082-T6 (or 1.4057) turned, cartridge bore 28 H6, labyrinth bore 15.7, oil jet + drain, spigot in the pod bore 98')
cv = rev([(-282.0, 0.0), (-282.0, 22.0), (f0, 22.0), (f0, 14.2), (-280.0, 14.2), (-280.0, 0.0)])
cv = cv.fuse(Part.makeCylinder(3.0, 10.0, V(-276.0, 0, 18.0), V(0, 0, 1)))    # speed / phase pickup boss (Hall on the locknut magnet)
parts['G-203_Front_Bearing_Cover'] = (cv.removeSplitter(), 2.70, 'Al 6082-T6, closes the front bearing chamber, Hall speed pickup boss, 4 x M4 to G-202')
r0, r1 = G['rear_shield']
rs = rev([(r0, 10.5), (r0, 49.0), (r0 + 5.0, 49.0), (r0 + 5.0, 44.5), (r0 + 6.0, 44.5), (r0 + 6.0, 21.0), (-126.0, 21.0),
          (-126.0, 49.0), (r1, 49.0), (r1, 9.0), (-126.0, 9.0), (-126.0, 7.85), (-130.9, 7.85), (-130.9, 14.0), (-141.0, 14.0), (-141.0, 7.85), (-144.5, 7.85), (-144.5, 10.5)])   # 10.5 relief round the carrier end
rs = rs.cut(Part.makeCylinder(0.75, 30, V(L.X_GR, 0, 14.0), V(0, 0, 1)))
rs = rs.cut(Part.makeCylinder(2.0, 40, V(L.X_GR - 3.0, 0, -46.0), V(0, 0, 1)))
parts['G-204_Rear_End_Shield'] = (rs, 2.70, 'Al 6082-T6 (or 1.4057), cartridge bore 28 H6, labyrinth bores 15.7 / 18 (collar), oil jet + drain, rear face on the pod rear plate')

# ---------------------------------------------------------------- quill guard, terminal box, glycol ports
QG = L.QUILL_GUARD
qg = cyl(QG['x0'], QG['x1'], QG['ro'], QG['ri']).fuse(cyl(QG['x0'], QG['x0'] + 2.0, QG['flange_r'], QG['ri'])).removeSplitter()
parts['G-150_Quill_Guard_Tube'] = (qg, 2.70, 'Al 6060 tube 20 x 1.5 + flange, 3 x M4 to the pod rear plate; stationary fairing round the quill in the intake')
tb = L.TBOX
box = Part.makeBox(tb['x'][1] - tb['x'][0], tb['y'][1] - tb['y'][0], tb['z'][1] - tb['z'][0], V(tb['x'][0], tb['y'][0], tb['z'][0]))
box = box.cut(Part.makeBox(tb['x'][1] - tb['x'][0] - 6, tb['y'][1] - tb['y'][0] - 6, tb['z'][1] - tb['z'][0] - 3,
                           V(tb['x'][0] + 3, tb['y'][0] + 3, tb['z'][0] + 3)))
box = box.cut(Part.makeCylinder(55.0, tb['x'][1] - tb['x'][0] + 2, V(tb['x'][0] - 1, 0, 0), XA))   # saddle on the d110 pod
gland = Part.makeCylinder(10.0, 8.0, V(tb['x'][1], 0, 70.0), XA)
parts['G-240_Terminal_Box'] = (box.fuse(gland).removeSplitter(), 2.70,
                               'Al box 64 x 52 x 30 (IP65) saddled on the pod: 3 x M6 phase studs on a PEEK block, PT100/PTC terminals, M32 EMC gland, lid')
ports = [Part.makeCylinder(6.0, 12.0, V(x, 0, 55.0), V(0, 0, 1)) for x in L.GLYCOL_PORTS]
parts['G-241_Glycol_Port_Fittings_x2'] = (Part.makeCompound(ports), 7.9, '2 x G1/4 straight fittings 1.4404 for 8 mm hose, in the pod shell over the jacket groove ends')

info = dict(note='D2R generator pod internals', frame='ENG mm', parts={})
mrot = 0.0
for k, (s, rho, spec) in parts.items():
    s.exportStep(os.path.join(OUT, k + '.step'))
    bb = s.BoundBox
    m = s.Volume * rho * 1e-6
    info['parts'][k] = dict(valid=s.isValid(), x=[round(bb.XMin, 2), round(bb.XMax, 2)],
                            r=round(max(abs(bb.YMax), abs(bb.YMin), abs(bb.ZMax), abs(bb.ZMin)), 2), mass_kg=round(m, 4), spec=spec)
    if k[:5] in ('G-220', 'G-221', 'G-222', 'G-223', 'G-224', 'G-225', 'G-226', 'G-227'):
        mrot += m
    print('%-36s valid %s  x %.1f..%.1f  %.4f kg' % (k, s.isValid(), bb.XMin, bb.XMax, m))
info['generator_rotor_mass_kg'] = round(mrot, 3)
json.dump(info, open(os.path.join(OUT, 'd2r_generator_parts.json'), 'w'), indent=1)
print('generator rotor (excl. bearings) %.3f kg -> %s' % (mrot, OUT))
