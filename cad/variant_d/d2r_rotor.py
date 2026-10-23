# GR180 version D2 - ROTOR & core bearings (D2R): new continuous engine shaft (crowned AF6 nose hex for the quill socket,
# M8x1 LH clamp nut, d10 compressor seat = compressor bore reamed 7 -> 10 H6, d10 journals, clamped d16/d10 body sleeve,
# d14 seal runner with 4 labyrinth teeth, d18 stub friction-welded to the bought turbine wheel), two 10x22x6 hybrid 15 deg
# P4 bearings in squeeze-film-damper cartridges (2 FKM O-rings each, 0.10 mm film, oil jet), new shaft tunnel with the v13A
# front flange, front seal / retainer ring, rear wave spring, oil feed + scavenge tubes to the rear bearing.
# Numbers: sim/variant_d/d2r_rotor.py; layout cad/variant_d/d2r_layout.py.  ENG frame mm, x = engine axis.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2r_rotor.py -> cad_out/variant_d/D2/ROTOR/*.step + d2r_rotor_parts.json
import FreeCAD as App, Part, os, sys, json, math
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d')
sys.path.insert(0, HERE)
import d2r_layout as L
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2', 'ROTOR'); os.makedirs(OUT, exist_ok=True)
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


def hexprism(x0, x1, af, corner_d=None):
    r = af / math.sqrt(3)
    pts = [V(x0, r * math.cos(math.radians(30 + 60 * k)), r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    h = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(x1 - x0, 0, 0))
    return h.common(cyl(x0, x1, corner_d / 2)) if corner_d else h


parts = {}
# ---------------------------------------------------------------- R-101 engine shaft
segs = [s for s in L.SHAFT if not s[0].startswith('crowned')]
prof = [(segs[0][1], 0.0)]
for name, x0, x1, r in segs:
    prof += [(x0, r), (x1, r)]
prof += [(segs[-1][2], 0.0)]
shaft = rev(prof)
hx = L.QUILL['hex']
shaft = shaft.fuse(hexprism(hx[0], hx[1], L.QUILL['hex_AF'], 6.8))
for k in range(4):                                                     # labyrinth teeth on the d14 runner (in the T-116 seal bore)
    xt = 107.8 + 1.2 * k
    shaft = shaft.fuse(cyl(xt, xt + 0.5, 7.6, 6.9))
shaft = shaft.removeSplitter()
parts['R-101_Engine_Shaft_d10'] = (shaft, 7.85, '42CrMo4 QT (or 17-4PH H1025), journals induction-hardened + ground, nose hex nitrided + crowned')

S = L.SLEEVE
parts['R-102_Body_Sleeve_d16'] = (cyl(S['x0'], S['x1'], S['ro'], S['ri']), 7.8, '17-4PH H1025, faces ground parallel 2 um, clamped between the bearing IRs')
parts['R-103_Shim_IR_Spacer'] = (cyl(L.SHIM['x0'], L.SHIM['x1'], L.SHIM['ro'], L.SHIM['ri']), 7.85, '100Cr6 hardened, ground')
W_ = L.WASHER
parts['R-104_Clamp_Washer'] = (cyl(W_['x0'], W_['x1'], W_['ro'], W_['ri']), 7.85, '100Cr6 / 17-4PH hardened, ground both faces')
N_ = L.NUT
nut = hexprism(N_['x0'], N_['x1'], N_['AF'], 14.6).cut(cyl(N_['x0'] - 1, N_['x1'] + 1, 4.0))   # threads modelled at the major diameter
parts['R-105_Clamp_Nut_M8x1_LH'] = (nut, 7.85, 'M8x1 LH thin nut AF13 x 7.5, 17-4PH or A286 (balance grade), RPM magnet pocket opposite a balance slug')

# ---------------------------------------------------------------- R-110/111 bearings 10x22x6 hybrid (envelopes: rings + ball/cage band)
def bearing(xc):
    x0, x1 = xc - 3.0, xc + 3.0
    ir = cyl(x0, x1, 6.7, 5.0)
    orr = cyl(x0, x1, 11.0, 9.3)
    balls = cyl(xc - 1.6, xc + 1.6, 9.3, 6.7)
    return ir.fuse(orr).fuse(balls).removeSplitter()
parts['R-110_Bearing_Front_71900_hybrid'] = (bearing(L.X_BF), 6.0, '10x22x6 hybrid 15 deg P4, locating (forward thrust)')
parts['R-111_Bearing_Rear_71900_hybrid'] = (bearing(L.X_BR), 6.0, '10x22x6 hybrid 15 deg P4, floating, spring-preloaded forward')

# ---------------------------------------------------------------- R-112/113 SFD cartridges (land OD 27.80 in bore 28.00)
RC = L.CART_OD / 2 - L.SFD_C


def cartridge(x0, x1, lips, grooves):
    c = cyl(x0, x1, RC, 11.0)
    for (a, b) in lips:
        c = c.fuse(cyl(a, b, 11.0 + 0.01, 9.6))
    for (a, b) in grooves:
        c = c.cut(cyl(a, b, RC + 1, 12.7))
    c = c.cut(Part.makeCylinder(0.4, 5, V(0.5 * (x0 + x1), 0, 9.0), V(0, 0, 1)))       # oil-jet / film feed hole (top)
    c = c.cut(Part.makeCylinder(1.0, 5, V(0.5 * (x0 + x1), 0, -14.5), V(0, 0, 1)))      # drain (bottom)
    return c.removeSplitter()
fc = (2.8, 11.0)
parts['R-112_SFD_Cartridge_Front'] = (cartridge(fc[0], fc[1], [(2.8, 3.8)], [(3.9, 5.3), (8.5, 9.9)]), 7.85,
                                      '17-4PH H1025 / 100Cr6, bore 22 H5 for the OR (locating), land 27.80 g4, 2 O-ring grooves, anti-rotation pin')
rc = (95.8, 107.3)
parts['R-113_SFD_Cartridge_Rear'] = (cartridge(rc[0], rc[1], [(95.8, 96.8), (105.3, 107.3)], [(97.6, 99.0), (102.6, 104.0)]), 7.85,
                                     '17-4PH H1025, OR sliding fit 22 H5/h5 (floating), land 27.80, 2 O-ring grooves')
parts['R-114_Retaining_Ring_Front_OR'] = (cyl(9.8, 10.6, 11.0, 9.6), 7.85, 'internal retaining ring for bore 22 (spiral, Smalley-type flat wire, EU equiv.) holds the locating OR')
orings = [cyl(a + 0.05, b - 0.05, RC + 0.10, 12.75) for (a, b) in [(3.9, 5.3), (8.5, 9.9), (97.6, 99.0), (102.6, 104.0)]]
parts['R-116_SFD_O-rings_FKM_x4'] = (Part.makeCompound(orings), 1.9, 'FKM 75 Sh, 25.0 x 1.5 (sets support stiffness 1-2 N/um; measure)')
parts['R-117_Wave_Spring_Rear_40N'] = (cyl(103.8, 105.3, 11.0, 9.6), 7.85, 'single-turn wave spring 22 x 19.2, 40 N at 1.5 mm, 17-7PH')

# ---------------------------------------------------------------- R-120 shaft tunnel D2 (v13A front flange interface, new bores)
T = L.TUNNEL
outer = [(2.0, 14.0), (2.0, 20.0), (7.0, 20.0), (17.0, 11.0), (92.0, 11.0), (95.8, 17.5), (107.3, 17.5), (107.3, 14.0),
         (95.8, 14.0), (95.8, 9.0), (11.0, 9.0), (11.0, 14.0)]
tun = rev(outer)
tun = tun.cut(Part.makeCylinder(0.75, 12, V(L.X_BF, 0, 12.0), V(0, 0, 1)))       # front oil-jet feed (top)
tun = tun.cut(Part.makeCylinder(1.5, 12, V(L.X_BF, 0, -21.0), V(0, 0, 1)))       # front scavenge (bottom)
tun = tun.cut(Part.makeCylinder(0.75, 6, V(L.X_BR, 0, 13.0), V(0, 0, 1)))        # rear jet feed (top, from R-121)
tun = tun.cut(Part.makeCylinder(1.5, 6, V(L.X_BR, 0, -18.5), V(0, 0, 1)))        # rear scavenge (bottom, to R-122)
parts['R-120_Shaft_Tunnel_D2'] = (tun, 7.85, '1.4057 / 17-4PH turned, bores 28 H6 ground coaxial 5 um, v13A flange & bolt pattern')
parts['R-121_Rear_Oil_Feed_Tube_d4'] = (Part.makeCylinder(2.0, 91.5 - 18.0, V(18.0, 0, 14.2), XA).cut(Part.makeCylinder(1.5, 80, V(17, 0, 14.2), XA)),
                                        7.9, '1.4571 tube 4 x 0.5, brazed into the tunnel flange drilling and the rear-ramp boss')
parts['R-122_Rear_Scavenge_Tube_d6'] = (Part.makeCylinder(3.0, 91.0 - 18.0, V(18.0, 0, -14.5), XA).cut(Part.makeCylinder(2.5, 80, V(17, 0, -14.5), XA)),
                                        7.9, '1.4571 tube 6 x 0.5, bottom (6 o clock), to the scavenge pump')
SF = L.SEAL_F
ring = rev([(SF['x0'], SF['ri']), (SF['x0'], SF['ro']), (2.0, SF['ro']), (2.0, SF['flange_ro']), (2.8, SF['flange_ro']), (2.8, SF['ri'])])
for k in range(2):                                                    # 2 grooves -> 3 teeth in the bore (labyrinth on the compressor boss)
    xg = 0.25 + 0.75 * k
    ring = ring.cut(cyl(xg, xg + 0.4, 11.7, 0.0).cut(cyl(xg - 1, xg + 1, 11.19)))
parts['R-131_Front_Seal_Retainer_Ring'] = (ring.removeSplitter(), 7.85, '17-4PH, 3-tooth labyrinth ID 22.4 on the compressor boss d21.9, pressed + Loctite 638 into the tunnel (retains the front cartridge)')

# ---------------------------------------------------------------- compressor with the new bore (v13A part reamed 7 -> 10 H6)
comp = Part.read(os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts', 'Compressor.step'))
comp = comp.cut(cyl(L.COMP['x0'] - 1, L.COMP['x1'] + 1, L.COMP['bore_new'] / 2))
parts['R-100_Compressor_v13A_bored_d10'] = (comp, 2.77, 'v13A compressor, bore reamed 7 -> 10 H6, re-balanced G1 (2618-T61 / 7075-T6 as built)')

info = dict(note='D2R rotor + core bearing parts', frame='ENG mm', parts={})
mass_rot = 0.0
for k, (s, rho, spec) in parts.items():
    s.exportStep(os.path.join(OUT, k + '.step'))
    bb = s.BoundBox
    m = s.Volume * rho * 1e-6
    info['parts'][k] = dict(valid=s.isValid(), x=[round(bb.XMin, 2), round(bb.XMax, 2)],
                            r=round(max(abs(bb.YMax), abs(bb.YMin), abs(bb.ZMax), abs(bb.ZMin)), 2), mass_kg=round(m, 4), spec=spec)
    if k[:5] in ('R-100', 'R-101', 'R-102', 'R-103', 'R-104', 'R-105'):
        mass_rot += m
    print('%-36s valid %s  x %.1f..%.1f  %.4f kg' % (k, s.isValid(), bb.XMin, bb.XMax, m))
info['rotating_mass_excl_wheel_bearings_kg'] = round(mass_rot, 3)
json.dump(info, open(os.path.join(OUT, 'd2r_rotor_parts.json'), 'w'), indent=1)
print('rotating (shaft+sleeve+shim+washer+nut+compressor) %.3f kg -> %s' % (mass_rot, OUT))
