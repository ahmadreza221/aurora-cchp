# GR180 version E - CORE: rotor (ROTOR), compressor casing (COMPRESSOR), bearing housing + SFD cartridges (BEARING),
# hot section + cool pressure casing (TURBINE).  Numbers: cad/variant_e/e_layout.py (from sim/variant_e/*.json).
# Bought wheels and bearings are ENVELOPES (blade-filled solids of revolution, mass given separately).
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_e/e_core.py  -> cad_out/variant_e/{ROTOR,COMPRESSOR,BEARING,TURBINE}/*.step
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
from e_common import *
import e_layout as L

# ================================================================== ROTOR
R = Parts('ROTOR')
prof = [(-116.0, 0.0), (-116.0, 15.5), (-94.0, 15.5), (-94.0, 20.0), (212.5, 20.0), (212.5, 25.0), (248.0, 25.0), (248.0, 15.0), (240.0, 15.0), (240.0, 0.0)]
shaft = rev(prof).fuse(hexprism(-140.0, -116.0, 24.0))
R.add('E-R101_Core_Shaft', shaft, 'steel', 'core shaft: crowned AF24 drive hex, M33x2 clamp thread, d40 seat + journals, d50 seal runner (3 piston-ring grooves), '
      'd50/30 heat dam; 42CrMo4 QT, journals ground, hex gas-nitrided; turbine wheel friction-welded at x 248 by the supplier', 'make (turn + grind) / weld by wheel supplier')
c = L.COMP
pts = [(-94.0, 20.0), (-94.0, 30.0), (-81.0, 38.0), (-81.0, 86.5)]
pts += [(-81.0 + 73.25 * math.sin(math.radians(t)), 135.0 - 48.5 * math.cos(math.radians(t))) for t in range(3, 91, 3)]
pts += [(7.75, 135.0), (11.75, 135.0), (30.0, 52.0), (30.0, 20.0)]
R.add('E-R100_Compressor_Wheel_D270_env', rev(pts), 'Al', 'compressor impeller D2 270, inducer 173/76, b2 15.5, 9+9 backswept -38 deg (ENVELOPE, blades filled)',
      'buy (TC-class spare wheel, bored H6 to d40)', mass=c['mass'], note='Al 2618-T61; Accelleron TPS52/57-F, MAN/PBST TCR16/18, MHI MET18-22 class (diameter ESTIMATE)')
R.add('E-R102_Spacer_Sleeve', cyl(75.0, 197.5, 30.0, 20.0), '17-4PH', 'clamped spacer sleeve d60/40 x 122.5 between the bearings (stiffens the stack)', 'make (turn + grind faces)')
R.add('E-R103_Slinger_Seal_Ring', cyl(30.0, 45.0, 35.0, 20.0), '17-4PH', 'oil slinger + back-face labyrinth ring d70/40 x 15 (r_seal 35, thrust trim)', 'make')
R.add('E-R104_Clamp_Nut_M33', cyl(-112.0, -94.0, 28.0, 15.5), 'steel', 'clamp nut M33x2, OD 56 x 18, 60 kN preload (hydraulic stretch or heat)', 'make (34CrNiMo6)')
for tag, x0, x1, dsc in (('E-R110a_Bearing_7008E_front1', 45.0, 60.0, 'front tandem pair #1'), ('E-R110b_Bearing_7008E_front2', 60.0, 75.0, 'front tandem pair #2'),
                         ('E-R111_Bearing_7008C_rear', 197.5, 212.5, 'rear floating')):
    R.add(tag, cyl(x0, x1, 34.0, 20.0), 'bearing', 'hybrid ceramic angular-contact spindle bearing 40x68x15, %s (envelope)' % dsc, 'buy', mass=0.21,
          note=L.BRG['model'])
t = L.TURB
pts = [(248.0, 0.0), (248.0, 25.0), (250.0, 27.0), (250.0, 144.0), (280.0, 144.0)]
pts += [(342.0 - 62.0 * math.cos(math.radians(a)), 144.0 - 28.0 * math.sin(math.radians(a))) for a in range(3, 91, 3)]
pts += [(342.0, 37.5), (360.0, 22.0), (360.0, 0.0)]
R.add('E-T101_Turbine_Wheel_D288_env', rev(pts), 'IN713LC', 'radial/mixed-flow turbine wheel D4 288, b4 30, exducer 232/75, 12 blades, nose cone (ENVELOPE, blades filled)',
      'buy (TC-class cast wheel, friction-welded to E-R101 by the supplier)', mass=t['mass'], note='cast IN713LC / K418 (MAR-M247 option); TPS57/61-F, TCR18/20 class (ESTIMATE)')
R.save(dict(rotor_mass_core_kg=round(sum(r['mass_kg'] for r in R.rows.values()), 2)))

# ================================================================== COMPRESSOR CASING
C = Parts('COMPRESSOR')
pts = [(-100.0 + 50.0 * math.cos(math.radians(a)), 305.0 + 213.0 * math.sin(math.radians(a))) for a in range(180, 271, 5)]
pts += [(-81.0, 86.95)]
pts += [(-81.0 + 72.8 * math.sin(math.radians(a)), 135.0 - 48.05 * math.cos(math.radians(a))) for a in range(3, 91, 3)]
pts += [(-8.2, 137.0), (-7.4, 137.0), (-7.4, 236.0), (-40.0, 236.0), (-40.0, 200.0), (-75.0, 150.0), (-120.0, 260.0), (-135.0, 330.0), (-150.0, 330.0)]
cover = rev(pts)
cover = cut_all(cover, bolt_circle_holes(-150.0, -135.0, 636.0, 16, 13.0, 11.25))
C.add('E-C110_Inlet_Shroud_Cover', cover, 'Al', 'inlet cover: elliptic bellmouth (r 305 -> 92), shroud contour (0.45 mm tip gap), diffuser front wall x -7.4, '
      'front flange to the plenum rear wall (16 x M12)', 'make (6082-T6 forged disc d660 x 150, CNC turning; shroud finish-turned with the wheel drawing)')
pts = [(-40.0, 236.0), (-7.4, 236.0), (-7.4, 245.0)]
pts += [(52.6 - 60.0 * math.cos(math.radians(a)), 245.0 + 60.0 * math.sin(math.radians(a))) for a in range(5, 91, 5)]
pts += [(115.0, 305.0), (115.0, 400.0), (100.0, 400.0), (100.0, 320.0), (52.6, 320.0)]
pts += [(52.6 - 75.0 * math.cos(math.radians(a)), 245.0 + 75.0 * math.sin(math.radians(a))) for a in range(85, -1, -5)]
pts += [(-40.0, 262.0)]
outer = rev(pts)
for s in (1, -1):
    outer = outer.fuse(box(50.0, 95.0, (314.0 if s > 0 else -400.0), (400.0 if s > 0 else -314.0), -30.0, 30.0))
outer = cut_all(outer, bolt_circle_holes(100.0, 115.0, 760.0, 16, 22.0, 11.25))
C.add('E-C150_Outer_Casing_Bend', outer, 'steel', 'outer casing: outer wall of the 90 deg bend (R60) + annulus r 305, rear flange to the cool casing (16 x M20), '
      'front spigot on the inlet cover; 2 trunnion pads = FIXED engine support', 'make (P355NL1 forged ring d820 x 160, CNC turning + milling of the pads)')
pts = [(7.4, 137.0), (7.4, 236.0)]
pts += [(32.4 - 25.0 * math.cos(math.radians(a)), 236.0 + 25.0 * math.sin(math.radians(a))) for a in range(5, 91, 5)]
pts += [(112.0, 261.0), (112.0, 241.0), (60.0, 241.0), (45.0, 190.0), (45.0, 36.0), (32.0, 36.0), (32.0, 54.0), (13.75, 137.0)]
bp = rev(pts)
dv = vane_row(17, -7.4, 7.4, 146.0, 236.0, 73.6, 1.5, 12.0)
bp = fuse_all([bp] + dv)
desw = []
for k in range(23):
    v = box(60.0, 100.0, -2.0, 2.0, 255.0, 311.0)
    v.rotate(V(80.0, 0, 0), V(0, 0, 1), 20.0)
    v = v.common(cyl(55.0, 105.0, 305.0, 261.0))
    v.rotate(V(0, 0, 0), XA, 360.0 * k / 23)
    desw.append(v)
bp = fuse_all([bp] + desw)
C.add('E-C130_Back_Plate_Diffuser_Deswirl', bp, 'Al', 'back plate: wheel back-face wall (2 mm gap), 17 straight wedge diffuser vanes (r 146 -> 236, 2.5D), inner wall of the bend, '
      '23 deswirl vanes in the annulus r 261..305 (4th-axis 2.5D), back-face labyrinth bore r 36', 'make (6082-T6 forged disc d620 x 120, CNC turning + 2.5D / 4-axis milling)')
C.save()

# ================================================================== BEARING HOUSING + SFD
B = Parts('BEARING')
pts = [(45.0, 42.12), (45.0, 165.0), (60.0, 165.0), (60.0, 100.0), (215.0, 100.0), (215.0, 150.0), (235.0, 150.0), (235.0, 25.4), (222.0, 25.4),
       (222.0, 35.0), (216.0, 35.0), (216.0, 42.12), (190.0, 42.12), (190.0, 60.0), (80.0, 60.0), (80.0, 42.12)]
bh = rev(pts)
bh = cut_all(bh, bolt_circle_holes(45.0, 60.0, 300.0, 12, 13.0, 15.0) + bolt_circle_holes(215.0, 235.0, 270.0, 12, 11.0, 15.0))
bh = bh.cut(rad_cyl(130.0, -90.0, 50.0, 110.0, 8.0)).cut(rad_cyl(60.0, 90.0, 35.0, 170.0, 3.0)).cut(rad_cyl(205.0, 90.0, 35.0, 110.0, 3.0))
B.add('E-B110_Bearing_Housing', bh, 'steel', 'bearing housing: front flange to the back plate (12 x M12), bores 84.24 H6 for the SFD cartridges ground in one setting, '
      'rear flange for the heat shield / nozzle stack (12 x M10), seal bore d50.8 (piston rings), oil-jet drillings, drain d16 at the bottom', 'make (42CrMo4 forged bar d340 x 200, CNC turning + drilling)')
pts = [(45.0, 34.0), (45.0, 42.0), (77.0, 42.0), (77.0, 30.5), (75.0, 30.5), (75.0, 34.0)]
B.add('E-B120_SFD_Cartridge_Front', rev(pts), '17-4PH', 'front SFD cartridge for the tandem pair: OD 84 (0.12 mm film), 2 O-ring grooves (FKM 84x3), jet holes, anti-rotation pin', 'make')
pts = [(190.0, 30.5), (190.0, 42.0), (216.0, 42.0), (216.0, 34.0), (192.0, 34.0), (192.0, 30.5)]
B.add('E-B121_SFD_Cartridge_Rear', rev(pts), '17-4PH', 'rear SFD cartridge (floating bearing), same OD/O-rings as the front', 'make')
B.add('E-B122_Wave_Spring_Rear', cyl(192.0, 197.5, 34.0, 30.6), 'steel', 'wave spring 300 N preload on the rear bearing outer ring (envelope)', 'buy', mass=0.02,
      note='Smalley / Rotor Clip-type crest-to-crest wave spring - EU: Barnes Group? NO (US); use SPIROL? NO (US) -> Lesjöfors (SE) or Scherdel (DE)')
B.save()

# ================================================================== TURBINE HOT SECTION + COOL CASING
T = Parts('TURBINE')
T.add('E-T110_Heat_Shield_Support', cyl(235.0, 247.0, 214.0, 27.0), 'IN625', 'turbine-end heat shield + nozzle support: 2 x 1.5 mm IN625 discs with ceramic paper, '
      'bolted to the bearing-housing rear flange; bore r 27 round the seal runner', 'make (sheet + TIG, turned rims)', mass=4.5)
nz = fuse_all([cyl(247.0, 250.0, 214.0, 150.0), cyl(280.0, 283.0, 214.0, 150.0)] + vane_row(19, 250.0, 280.0, 158.0, 206.0, 75.4, 1.2, 6.0))
T.add('E-T120_Nozzle_Ring_19v', nz, 'alloyX', '19-vane radial nozzle ring: straight 2.5D vanes (r 206 -> 158, alpha3 75 deg, throat ~12 mm, b 30) between two side plates',
      'make (2.4665 forged ring, 3-axis pocket milling; cover plate bolted)')
pts = [(342.0 - 61.45 * math.cos(math.radians(a)), 144.0 - 27.45 * math.sin(math.radians(a))) for a in range(0, 91, 3)]
pts += [(360.0, 116.55), (495.0, 128.36), (495.0, 140.0), (300.0, 140.0), (295.0, 150.0), (295.0, 214.0), (283.0, 214.0), (283.0, 150.0), (280.55, 150.0)]
T.add('E-T130_Shroud_Diffuser_Inlet', rev(pts), 'IN625', 'turbine shroud (0.55 mm tip gap, shimmed) + diffuser inlet ring to x 495 (5 deg); '
      'piston-ring seal in the cool-casing rear wall; flange to the nozzle front plate', 'make (2.4856 forged ring, CNC turning)')
hp = cyl(140.0, 430.0, 345.0, 214.0).cut(cyl(143.0, 427.0, 342.0, 217.0))
hp = hp.cut(cyl(247.0, 283.0, 218.0, 210.0)).cut(zcyl(L.X_CAN, 0.0, 290.0, 360.0, L.HOT['inlet_r']))
T.add('E-T140_Hot_Plenum', hp, 'alloyX', 'floating 360 deg hot plenum (3 mm alloy X): round top inlet d280 for the transition (piston ring), '
      'inner slot feeding the nozzle ring; radially free inside the cool casing', 'make (rolled + pressed sheet, TIG; inner rings turned)')
cc = fuse_all([cyl(128.0, 470.0, 380.0, 372.0), cyl(115.0, 128.0, 400.0, 305.0), cyl(470.0, 480.0, 380.0, 141.0)])
cc = cc.cut(zcyl(L.X_CAN, 0.0, 300.0, 400.0, 155.0))
stub = zcyl(L.X_CAN, 0.0, 330.0, 420.0, 161.95, 154.85).cut(cyl(100.0, 500.0, 372.0))
flange = zcyl(L.X_CAN, 0.0, 420.0, 440.0, 222.5, 155.0)
cc = fuse_all([cc, stub, flange])
for s in (1, -1):
    cc = cc.fuse(box(270.0, 300.0, (370.0 if s > 0 else -420.0), (420.0 if s > 0 else -370.0), -20.0, 20.0))
cc = cut_all(cc, bolt_circle_holes(115.0, 128.0, 760.0, 16, 22.0, 11.25))
T.add('E-T150_Cool_Pressure_Casing', cc, 'steel', 'cool pressure casing OD 760 x 8 (compressor air ~212 C, 4 bar round the hot parts): front flange to the outer casing, '
      'rear wall with the shroud seal bore, DN300 PN10 combustor stub, 2 SLIDING support pads', 'make (P265GH plate rolled + welded, flanges turned; PED cat. II)')
T.save()
print('CORE done')
