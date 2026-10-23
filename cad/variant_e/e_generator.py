# GR180 version E - GENERATOR pod: 335 kW 2-pole PMG (sim/variant_e/e_pmg.json) on its own feet in the intake plenum,
# bolted d30 quill with an AF24 socket that slides on the crowned hex of the core-shaft nose, stationary guard tube.
# Housing (Al) + glycol jacket + 2 end bells; rotor = integral d80 magnet body, 2 hybrid 7008 bearings in SFD cartridges.
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_e/e_generator.py  -> cad_out/variant_e/GENERATOR/*.step
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_e'))
from e_common import *
import e_layout as L

G = Parts('GENERATOR')
G.add('E-G111_Front_End_Bell', rev([(-900.0, 0.0), (-900.0, 160.0), (-800.0, 160.0), (-800.0, 30.4), (-810.0, 30.4), (-810.0, 42.12), (-845.0, 42.12),
                                     (-845.0, 40.0), (-890.0, 40.0), (-890.0, 0.0)]), 'Al',
      'front end bell: SFD bore 84.24 (locating bearing), oil jet + drain, Hall speed pickup, spigot into the housing', 'make (6082-T6 bar d330, CNC turning)')
hs = cyl(-800.0, -435.0, 160.0, 140.0)
for xb in (-780.0, -455.0):
    hs = hs.fuse(rad_cyl(xb, 90.0, 150.0, 185.0, 15.0)).cut(rad_cyl(xb, 90.0, 130.0, 190.0, 6.6))
G.add('E-G110_Pod_Housing', hs, 'Al', 'pod housing tube OD 320 / bore 280 H7 with 2 glycol ports G1/2', 'make (6082-T6 thick tube or forged ring, CNC turning)')
G.add('E-G112_Glycol_Jacket', cyl(-790.0, -445.0, 140.0, 120.0), 'Al', 'glycol jacket sleeve (helical groove 12 x 6, 4 O-rings), stator shrunk in', 'make (6082 tube, turned)')
G.add('E-G113_Rear_End_Bell', rev([(-435.0, 30.4), (-435.0, 160.0), (-370.0, 160.0), (-370.0, 40.0), (-382.0, 40.0), (-382.0, 42.12), (-415.0, 42.12), (-415.0, 30.4)]),
      'Al', 'rear end bell: SFD bore (floating bearing + wave spring), labyrinth to the rotor, guard-tube flange face', 'make (6082-T6, CNC turning)')
G.add('E-G120_Stator_Core', cyl(-710.0, -520.0, 120.0, 62.5), 'lam', 'stator core 24 slots, bore 125, OD 240, stack 190 (0.20 mm NO20 laminations, bonded)',
      'buy (lamination stack from a motor-lamination maker: Surahammar SE / Kienle+Spiess DE / Baosteel CN)')
G.add('E-G121_Winding_End_Turns', fuse_all([cyl(-790.0, -710.0, 118.0, 64.0), cyl(-520.0, -445.0, 118.0, 64.0)]), 'winding',
      'Litz winding 3-ph, 2 parallel paths, end turns (envelopes), VPI class H, 3 x PT100', 'make (winding shop) - or with the active-parts kit (e+a CH)')
gs = rev([(-880.0, 0.0), (-880.0, 15.0), (-860.0, 15.0), (-860.0, 17.5), (-837.5, 17.5), (-837.5, 20.0), (-822.5, 20.0), (-822.5, 30.0), (-740.0, 30.0), (-740.0, 40.0),
          (-490.0, 40.0), (-490.0, 30.0), (-407.5, 30.0), (-407.5, 20.0), (-392.5, 20.0), (-392.5, 28.0), (-385.0, 28.0), (-385.0, 0.0)])
G.add('E-G130_Generator_Shaft', gs, 'steel', 'generator shaft, integral d80 magnet body, d40 journals, quill flange face (6 x M8 + 2 dowels)', 'make (42CrMo4 QT, turn + grind)')
G.add('E-G131_Magnets_Sleeve', cyl(-722.0, -508.0, 60.0, 40.0), 'SmCo+CF', 'Sm2Co17 segments 80/108 x 190 + T700 carbon sleeve 6 mm (OD 120) + 1.4404 end rings (envelope)',
      'buy magnets (VAC DE / Shin-Etsu JP / Chinese 2:17) + sleeve winding (e+a CH or local CFRP shop)')
G.add('E-G135_KM7_Nut_Speed_Wheel', fuse_all([cyl(-860.0, -848.0, 29.0, 17.5), cyl(-880.0, -870.0, 35.0, 15.0)]), 'steel', 'precision locknut KM7 + 2-tooth speed / phase wheel', 'buy nut (SKF KMT 7 / FAG) + make wheel', mass=0.35)
G.add('E-G140_Bearing_7008E_front', cyl(-837.5, -822.5, 34.0, 20.0), 'bearing', 'hybrid 7008-E locating', 'buy', mass=0.21, note=L.BRG['model'])
G.add('E-G141_Bearing_7008C_rear', cyl(-407.5, -392.5, 34.0, 20.0), 'bearing', 'hybrid 7008-C floating + wave spring', 'buy', mass=0.21, note=L.BRG['model'])
G.add('E-G142_SFD_Cartridge_Front', rev([(-845.0, 31.0), (-845.0, 42.0), (-815.0, 42.0), (-815.0, 34.0), (-841.0, 34.0), (-841.0, 31.0)]), '17-4PH', 'front SFD cartridge (same OD as the core cartridges)', 'make')
G.add('E-G143_SFD_Cartridge_Rear', rev([(-415.0, 34.0), (-415.0, 42.0), (-388.0, 42.0), (-388.0, 31.0), (-391.0, 31.0), (-391.0, 34.0)]), '17-4PH', 'rear SFD cartridge', 'make')
q = rev([(-385.0, 0.0), (-385.0, 35.0), (-373.0, 35.0), (-373.0, 15.0), (-165.0, 15.0), (-165.0, 28.0), (-117.0, 28.0), (-117.0, 0.0)])   # 1 mm float to the thread shoulder
q = q.cut(hexprism(-141.0, -115.0, 24.2)).cut(cyl(-160.0, -140.0, 10.0))
G.add('E-G150_Quill_AF24_Socket', q, 'steel', 'quill d30 x 208 with flange (6 x M8 12.9 + 2 dowels to the shaft) and AF24 socket (rotary-broached, nitrided), float +/-1 mm',
      'make (34CrNiMo6 QT, turn + grind + broach; shot-peened waist)')
G.add('E-G160_Quill_Guard_Tube', fuse_all([cyl(-370.0, -98.0, 38.0, 33.0), cyl(-370.0, -360.0, 60.0, 33.0)]), 'stainless',
      'stationary quill guard d76 (continues the impeller hub line), flanged to the rear end bell', 'make (1.4301 tube + turned flange)')
tb = box(-700.0, -560.0, -80.0, 80.0, 160.0, 260.0).fuse(box(-700.0, -560.0, -80.0, 80.0, 130.0, 160.0).cut(cyl(-710.0, -550.0, 160.0)))
G.add('E-G170_Terminal_Box', tb, 'Al', 'terminal box: 3 power studs M12 on PEEK, PT100 / PTC, M50 EMC glands for 3 x 240 mm2 (or 2 x 120 per phase)', 'make (6082 block, milled)')
feet = []
for xf in L.POD['feet_x']:
    feet.append(box(xf - 40.0, xf + 40.0, -120.0, 120.0, -647.0, -110.0).cut(cyl(xf - 50.0, xf + 50.0, 160.0))
                .cut(box(xf - 25.0, xf + 25.0, -105.0, 105.0, -632.0, -200.0)))
G.add('E-G180_Pod_Saddles_x2', fuse_all(feet), 'steel', '2 saddle feet on the plenum floor (shims + jack bolts for alignment to the core shaft; slide-out rails for removal)', 'make (S355 plate, welded)')
G.save(dict(pmg='sim/variant_e/e_pmg.json'))
