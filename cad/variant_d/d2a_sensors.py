# GR180 version D2 - ignition, sensors and electrical (SN-4xx, EL-5xx): igniter HT boot + ignition transformer IGN-630 and HT lead,
# UV flame sensor BE-631 on a sight tube, N1 speed (SE-001A Hall in G-203 via the D-102P gland, SE-001C turboSPEED blade-pass in a new
# M5 shroud port; SE-001B = converter back-EMF), TIT / EGT dual K thermocouples, casing P2 / T3 / buffer-air bosses, P2 transmitter,
# buffer-air line to the pod, accelerometers VE-010/011/012, generator-bearing PT100s, plenum T1/P1, junction box JB-1, cable tray,
# harness conduits and the PMG power cable.  Tags follow docs/electrical/02_io_list.csv where they exist.
# ENG frame mm.  Run after d2a_skid.py: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2a_sensors.py -> AUX/SN-*, EL-* .step
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2a_common import *

clear_aux({'SN', 'EL'})
parts = {}

# ---------------------------------------------------------------- ignition
xi = 30.8
boot = cyl(rad(xi, 330.0, 75.0), rad(xi, 330.0, 92.0), 6.0)   # boot over the plug terminal (r <= 74)
ht = tube_path([(25.0, -196.0, -80.0), (15.0, -150.0, -72.0), (15.0, 40.0, -72.0), (25.0, 72.0, -62.0), rad(xi, 330.0, 92.0)], 3.5)
tr = bx((LY.IGN_TRAFO['x'], LY.IGN_TRAFO['y'], LY.IGN_TRAFO['z']))
parts['SN-411_Ignition_Trafo_IGN630_HT_Lead'] = (comp([tr, ht, boot]), 1.6, 'buy',
    'IGN-630 electronic ignition transformer 230 VAC -> 2 x 7.5 kV (57 x 104 x 60 class) on the AUX deck, silicone HT lead 7 mm ~0.8 m '
    'under the core to the v13A 1/4-32 plug at 330 deg (kept), boot 12 x 21; spark 3-5 s per start, plug inspected every 500 h',
    'COFI (IT) TRK2 / BRAHMA (IT) TC1 class; HT lead Beru (DE)')
U = LY.UV
uv = cyl(rad(U['x'], U['ang'], U['r0']), rad(U['x'], U['ang'], U['r_tube']), 10.0).fuse(cyl(rad(U['x'], U['ang'], U['r_tube']), rad(U['x'], U['ang'], U['r_end']), 16.0))
parts['SN-412_UV_Flame_Sensor_BE631'] = (uv.removeSplitter(), 0.9, 'buy',
    'BE-631 UV flame sensor on a 65 mm stainless sight tube with heat-insulating coupling and quartz window, weld boss on the casing at '
    'x 40 / 210 deg (between vaporiser sticks 195 / 225 deg); drill d6 through the casing and CC outer liner; failsafe flame relay in B1/SR1',
    'Durag (DE) D-LX 100 UV, Siemens (DE) QRA2 + AGQ3; quartz window adapter by the maker')

# ---------------------------------------------------------------- speed
N = LY.N1_CORE
ds = cyl(rad(N['x'], N['ang'], N['r0']), rad(N['x'], N['ang'], N['r1']), 2.5)
ds = ds.fuse(tube_path([rad(N['x'], N['ang'], N['r1']), rad(-30.0, N['ang'], 58.0), rad(-30.0, N['ang'], 100.0)], 2.0))
ds = ds.fuse(hexbar(rad(-30.0, N['ang'], 100.0), rad(-30.0, N['ang'], 106.0), 14.0))
parts['SN-413_N1_Core_turboSPEED_SE001C'] = (ds.removeSplitter(), 0.3, 'buy',
    'SE-001C independent core speed: eddy-current blade-pass sensor DS05 (d3, 285 C, gap <= 2.2 mm to the Al inducer tips) in a NEW M5 port '
    'at x -20 / 300 deg in the v13A shroud, cable out through the spare 300 deg skirt / can bulkheads; DZ140 controller (pulse + 4-20 mA, 85 g) '
    'inside JB-1; SE-001A = Hall pickup in G-203 (magnet in the KM0 nut), SE-001B = converter back-EMF frequency',
    'Micro-Epsilon (DE) turboSPEED DZ140 + DS05')
hall = hexbar((-284.0, 0.0, 58.0), (-284.0, 0.0, 64.0), 15.0).fuse(cyl((-284.0, 0.0, 64.0), (-284.0, 0.0, 84.0), 3.0))
parts['SN-414_N1_Hall_SE001A_Gland'] = (hall.removeSplitter(), 0.05, 'buy',
    'SE-001A Hall speed/phase pickup (in the G-203 boss, magnet in the KM0 locknut) cable through an M12 gland in the D-102P front cap',
    'Melexis (BE) US5881 sensor, Lapp (DE) SKINTOP gland')

# ---------------------------------------------------------------- temperatures, pressures
tit = cyl((138.0, 0.0, 80.0), (138.0, 0.0, 95.0), 6.0).fuse(cyl((138.0, 0.0, 95.0), (138.0, 0.0, 125.0), 8.0))
egt = cyl(rad(229.0, 45.0, 79.0), rad(229.0, 45.0, 105.0), 7.0).fuse(cyl(rad(229.0, 45.0, 105.0), rad(229.0, 45.0, 130.0), 10.0))
parts['SN-415_TIT_EGT_Dual_K_TE504_TE505'] = (comp([tit, egt]), 0.4, 'buy',
    'TE-504A/B: dual K class 1 MI 3 mm Inconel 600, ungrounded, in the T-120 M8x1 boss (x 138, top, tip in the plenum r ~68); '
    'TE-505A/B: dual K MI 4.5 mm in the EX-110 M14x1.5 boss (x 229, 45 deg) through the insulation; compression fittings, transition heads',
    'WIKA (DE) TC80, Rössel (DE), JUMO (DE)')
cb = []
for name, (x, a) in LY.CASING_BOSSES.items():
    cb.append(cyl(rad(x, a, 55.0), rad(x, a, 61.0), 6.0))
    cb.append(hexbar(rad(x, a, 61.0), rad(x, a, 68.0), 12.0))
p2 = tube_path([rad(60.0, 200.0, 68.0), rad(60.0, 200.0, 76.0), (60.0, -100.0, -45.0), (78.0, -205.0, -45.0), (78.0, -216.0, -45.0)], 3.0)
pt521 = cyl((78.0, -230.0, -100.0), (78.0, -230.0, -10.0), 13.5)
t3 = tube_path([rad(70.0, 200.0, 68.0), rad(70.0, 200.0, 76.0), (70.0, -110.0, -20.0), (70.0, -180.0, -12.0)], 2.0)
parts['SN-416_Casing_Bosses_P2_T3_Buffer'] = (comp(cb + [p2, pt521, t3]), 0.8, 'make+buy',
    '3 weld bosses d12 on the casing at 200 deg (x 60 PT-521 P2 tap, x 70 TE-502 T3 TC 1.5 mm, x 80 buffer-air bleed), M8x1 fittings; '
    'P2 sense line 6 x 1 (> 300 mm, cools the air) to PT-521 0-6 bar abs on the AUX deck; T3 MI cable to the harness',
    'bosses local (TIG, 1.4301); PT-521 Keller (CH) PA-21Y / WIKA (DE) S-20; TC WIKA / JUMO (DE)')
buf = tube_path([rad(80.0, 200.0, 68.0), rad(80.0, 200.0, 76.0), (80.0, -110.0, -30.0), (-120.0, -110.0, -30.0), (-153.0, -95.0, -45.0), rad(-153.0, 210.0, 70.0)], 3.0)
orf = cyl((-20.0, -110.0, -30.0), (-60.0, -110.0, -30.0), 9.0)
bfit = hexbar(rad(-153.0, 210.0, 60.0), rad(-153.0, 210.0, 66.0), 12.0)
parts['SN-417_Buffer_Air_Line_Pod'] = (comp([buf, orf, bfit]), 0.25, 'make',
    'generator labyrinth buffer air: compressor-delivery bleed (casing boss x 80) -> 25 um sintered filter + d2.2 orifice (~1.4 g/s, '
    '~+5 kPa in the pod) -> 6 x 1 tube -> pod G1/8 port x -153 / 210 deg (rotor cavity, flows through both generator labyrinths into the '
    'bearing chambers)', 'filter + orifice: Hy-Lok (KR) / Ham-Let (IL) or local; tube Sandvik (SE)')
acc = []
acc.append(box(2.0, 22.0, -92.0, -72.0, -12.0, 12.0))                          # VE-010 block on the INT-112 rear face (x -2.4)
acc.append(cyl((12.0, -92.0, 0.0), (12.0, -137.0, 0.0), 12.0))
for x in (-250.0, -145.0):                                                     # VE-011 / VE-012 on the pod pads (180 deg)
    acc.append(cyl((x, -58.0, 0.0), (x, -103.0, 0.0), 12.0))
parts['SN-418_Accelerometers_VE010_011_012'] = (comp(acc), 0.5, 'buy',
    'VE-010 core (radial, on a 20 x 20 x 24 block welded to the INT-112 rear face, 180 deg), VE-011 / VE-012 generator front / rear '
    '(radial, M6 stud on the pod pads x -250 / -145): IEPE 100 mV/g, +/-50 g, 2 Hz-10 kHz, M12 connector (1x and 1917 Hz tracking in B2)',
    'Hansford Sensors (UK) HS-100, IFM (DE) VSA, Brüel & Kjær (DK) 4533')
pt = []
for x in (-262.0, -137.0):
    pt.append(cyl(rad(x, 225.0, 21.5), rad(x, 225.0, 49.0), 1.5))             # PT100 sheath d3 into the end-shield hub
    pt.append(hexbar(rad(x, 225.0, 60.0), rad(x, 225.0, 66.0), 10.0))
    pt.append(cyl(rad(x, 225.0, 66.0), rad(x, 225.0, 86.0), 5.0))
parts['SN-419_Gen_Bearing_PT100_TE722_723'] = (comp(pt), 0.15, 'buy',
    'TE-722 / TE-723 generator bearing temperatures: PT100 class A d3 spring-loaded sheath to the end-shield hub next to the SFD cartridge, '
    'M8x1 compression fitting on the pod boss (225 deg); core bearings TE-724 / 725: d1.0 K MI thermocouples in the tunnel flange, routed '
    'with the core scavenge tube (275 deg bulkhead)', 'WIKA (DE), JUMO (DE), Rössel (DE)')
t1 = hexbar(rad(-110.0, 225.0, 101.0), rad(-110.0, 225.0, 108.0), 14.0).fuse(cyl(rad(-110.0, 225.0, 108.0), rad(-110.0, 225.0, 128.0), 7.0))
parts['SN-420_Plenum_T1_P1_Tap'] = (t1.removeSplitter(), 0.15, 'buy',
    'TE-501 T1 PT1000 probe + plenum static tap (PDT-526 / filter dp) on a tee in the INT-110 P-tap boss (x -110, 225 deg)', 'WIKA (DE), Huba (CH) 699 dp')

# ---------------------------------------------------------------- electrical
J = LY.JB
jb = bx((J['x'], J['y'], J['z']))
for xg in (-285.0, -265.0, -205.0, -185.0, -165.0):
    jb = jb.fuse(cyl((xg, -400.0, J['z'][0]), (xg, -400.0, J['z'][0] - 20.0), 10.0))
parts['EL-510_Junction_Box_JB1'] = (jb.removeSplitter(), 4.5, 'buy',
    'JB-1 sheet-steel terminal box 300 x 150 x 120 IP66 (door -y), DIN rail: ~120 terminals (Phoenix PT push-in), TC compensating '
    'terminals, 24 VDC distribution with fuses, shield clamps; 5 x M25 EMC glands at the bottom; field signals -> B2 (cabinet) via 2 multicore '
    'screened cables; PMG power and HT lead do NOT enter JB-1', 'Rittal (DE) KL, Spelsberg (DE); terminals Phoenix Contact (DE); glands Lapp (DE) SKINTOP')
T = LY.TRAY
tray = bx((T['x'], T['y'], T['z'])).cut(box(T['x'][0] - 1, T['x'][1] + 1, T['y'][0] + 2, T['y'][1] - 2, T['z'][0] + 2, T['z'][1] + 1))
tray = tray.fuse(tube_path([(-200.0, -322.0, -140.0), (-200.0, -322.0, 20.0), (-170.0, -300.0, 20.0), (-170.0, -110.0, 20.0)], 12.5))
tray = tray.fuse(tube_path([(105.0, -290.0, -140.0), (105.0, -290.0, -10.0), (105.0, -130.0, -10.0), (229.0, -130.0, -10.0), (229.0, -130.0, 110.0)], 12.5))
tray = tray.fuse(tube_path([(-200.0, -322.0, -140.0), (-200.0, -322.0, -120.0)], 12.5))
tray = tray.fuse(tube_path([(-235.0, -310.0, -155.0), (-235.0, -400.0, -155.0), (-235.0, -400.0, -122.0)], 12.5))   # tray -> JB-1 glands
parts['EL-512_Cable_Tray_Harness_Conduits'] = (tray.removeSplitter(), 3.2, 'buy',
    'galvanised cable tray 40 x 30 under the deck + PA12 corrugated conduits NW 25 (signal harness): cold harness to the pod / core break-out '
    '(x -170, y -110), hot harness along y -125 to the turbine / exhaust TCs (MI cables beyond), riser into JB-1',
    'tray OBO Bettermann (DE); conduit PMA (CH) / Reiku (DE)')
pc = tube_path([(-218.0, 0.0, 70.0), (-228.0, 0.0, 70.0), (-235.0, 30.0, 72.0), (-312.0, 30.0, 72.0), (-312.0, 30.0, -60.0), (-312.0, -170.0, -60.0)], 10.0)
parts['EL-513_PMG_Power_Cable_Route'] = (pc, 2.0, 'buy',
    'PMG power cable 4G10 mm2 screened (EMC, 1 kV, 2 kHz fundamental), from the G-240 front gland round the pod nose (clear of the pod '
    'slide path) to the skid front edge -> B3 converter indoors (~30 m); separate route from the signal harness',
    'Lapp (DE) ÖLFLEX SERVO FD 796 CP, HELUKABEL (DE) TOPFLEX EMV')

export(parts, 'SENSORS_ELECTRICAL', dict(title='GR180 D2 ignition, sensors, junction box, cable routing', frame='ENG mm',
                                        io='tags per docs/electrical/02_io_list.csv; D2-specific: SE-001C, TE-722..725, VE-012, BE-631 sight tube'),
       'd2a_sensors_parts.json')
