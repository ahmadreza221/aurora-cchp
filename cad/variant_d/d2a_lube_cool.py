# GR180 version D2 - closed-loop oil system (OL-2xx) for the 4 jet-lubricated 10x22x6 hybrid bearings (2 core + 2 generator)
# and the generator glycol loop (GC-3xx).
#   oil   : tank on the AUX deck (rear, 3 L VG32) with a submerged pressure gear pump + scavenge pump + spin-on 10 um filter +
#           coalescing mist separator on the lid -> Laminova oil/glycol cooler -> distribution block (PT-701, PSL-702, TE-708)
#           -> core feed (intake bulkhead 185 deg -> v13A 161 deg diffuser-land route) and the 2 pod jets (top, x -265.0 / -136);
#           drains: pod bottom (x -262 / -133) + core scavenge (bulkhead 275 deg -> 272 deg land) -> collector -> scavenge pump.
#   glycol: radiator (rear, blows +x) -> circulator -> PMG jacket (pod 135 deg ports) -> Laminova -> radiator; expansion tank on
#           the top run.  Numbers: sim/variant_d/d2a_aux_calc.json.  Pod ports: ported shell from d2r_generator.py (D2/POD).
# ENG frame mm.  Run after d2a_skid.py: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2a_lube_cool.py -> AUX/OL-*, GC-* .step
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2a_common import *

clear_aux({'OL', 'GC'})
CALC = json.load(open(os.path.join(ROOT, 'sim', 'variant_d', 'd2a_aux_calc.json')))
OIL, GLY = CALC['oil'], CALC['glycol']
parts = {}
ZD = LY.Z_DECK
P_, S_ = LY.LANE_OIL_P, LY.LANE_OIL_S
G1, G4 = LY.LANE_GLY_1, LY.LANE_GLY_4

# ---------------------------------------------------------------- oil module
T = LY.OIL_TANK
zl = ZD + T['dz']                                                      # lid top
tank = box(T['x0'], T['x0'] + T['dx'], T['y0'], T['y0'] + T['dy'], ZD, zl)
tank = tank.cut(box(T['x0'] + 3, T['x0'] + T['dx'] - 3, T['y0'] + 3, T['y0'] + T['dy'] - 3, ZD + 3, zl - 3))
tank = tank.fuse(cyl((T['x0'] + 20, T['y0'] + T['dy'], ZD + 60), (T['x0'] + 20, T['y0'] + T['dy'] + 8, ZD + 60), 12.0))   # sight glass
parts['OL-210_Oil_Tank_3L'] = (tank.removeSplitter(), 1.9 + 3.0 * 0.86, 'make',
    'Al 5083 3 mm TIG weldment 175 x 100 x 220 (3.85 L gross, 3.0 L ISO VG 32), baffle, sight glass, drain G1/4, LSL-707 float, TE-704 '
    'PT1000, EH-712 200 W heater, breather to the separator; lid carries the pump motors, filter and separator',
    'local Al fabricator; float switch Barksdale (DE) / Kobold (DE); heater Backer (SE)')
pp, ps = LY.OIL_PUMP_P, LY.OIL_PUMP_S
mp = cyl((pp['x'], pp['y'], zl), (pp['x'], pp['y'], zl + pp['h']), pp['r'])
parts['OL-211_Pressure_Pump_M710'] = (mp, 1.3, 'buy',
    'M-710 pressure pump: external gear pump ~1.0 cm3/rev submerged in the tank, vertical 24 V BLDC motor 60 W (speed loop on PT-701, '
    '2.5 barg), relief 4 bar; 2.5 L/min', 'pump: Marzocchi Pompe (IT) ALP0 class / Rickmeier (DE); motor: Dunkermotoren (DE) BG 45, maxon (CH)')
ms = cyl((ps['x'], ps['y'], zl), (ps['x'], ps['y'], zl + ps['h']), ps['r'])
parts['OL-212_Scavenge_Pump_M711'] = (ms, 1.4, 'buy',
    'M-711 scavenge pump: gear pump ~2.5 cm3/rev on the lid (suction from the drain collector, 3:1 scavenge ratio, 6 L/min oil+air), '
    '24 V BLDC 60 W', 'as M-710')
f = LY.OIL_FILTER
flt = cyl((f['x'], f['y'], zl), (f['x'], f['y'], zl + 30), 32.0).fuse(cyl((f['x'], f['y'], zl + 30), (f['x'], f['y'], zl + f['h']), f['r']))
parts['OL-213_Oil_Filter_10um_PDS703'] = (flt.removeSplitter(), 0.9, 'buy',
    'spin-on 10 um filter (beta10 >= 200) with head, bypass 2.5 bar, electrical clogging switch PDS-703', 'Argo-Hytos (DE/CZ), Hydac (DE), MP Filtri (IT)')
sp = LY.SEPARATOR
sep = cyl((sp['x'], sp['y'], zl), (sp['x'], sp['y'], zl + sp['h']), sp['r']).fuse(cyl((sp['x'], sp['y'], zl + sp['h']), (sp['x'], sp['y'], zl + sp['h'] + 60), 6.0))
parts['OL-215_Oil_Mist_Separator'] = (sep.removeSplitter(), 0.7, 'buy',
    'coalescing oil-mist separator >= 30 m3/h on the tank lid (drains straight back into the tank), vent pipe 12 mm to the enclosure exhaust; '
    'carries the labyrinth air (7.4 g/s with the D2R labyrinths, ~2.4 g/s with core piston rings)', 'MANN+HUMMEL (DE) ProVent class, UFI (IT), Hydac (DE)')
L = LY.LAMINOVA
lam = cyl((L['x0'], L['y'], L['z']), (L['x1'], L['y'], L['z']), L['r'])
for xs in (L['x0'] + 10, L['x1'] - 10):                                    # glycol stubs (top): out at x0 end, in at x1 end
    lam = lam.fuse(cyl((xs, L['y'], L['z'] + L['r'] - 2), (xs, L['y'], -50.0), 6.0))
for xs in (L['x0'] + 25, L['x1'] - 25):                                    # oil stubs (-y side)
    lam = lam.fuse(cyl((xs, L['y'] - L['r'] + 2, L['z']), (xs, L['y'] - L['r'] - 8, L['z']), 5.0))
parts['OL-214_Oil_Cooler_Laminova_C43'] = (lam.removeSplitter(), 1.2, 'buy',
    'oil-to-glycol tube cooler (Laminova C43 class, 120 mm core): 1.5 kW at oil 2 L/min 85 -> 60 C, glycol 2.5 L/min (UA needed ~%d W/K)'
    % OIL['cooler']['UA_W_K_needed_at_30C'], 'Laminova (SE); alt. SWEP (SE) B5 brazed plate')
C = LY.COLLECTOR
col = cyl((C['x0'], C['y'], C['z']), (C['x1'], C['y'], C['z']), C['r'])
parts['OL-216_Scavenge_Collector'] = (col, 0.35, 'make',
    '1.4404 tube 32 x 2 x 60 with 3 inlets (core scavenge, pod drains, spare) and the scavenge-pump suction; lowest point of the oil return, '
    'TE-705 (core) / TE-706 (generator) in the inlets', 'local')
M = LY.OIL_MANIFOLD
man = bx((M['x'], M['y'], M['z']))
man = man.fuse(cyl((-42.0, -195.0, -95.0), (-42.0, -168.0, -95.0), 13.5))   # PT-701 (horizontal, +y)
man = man.fuse(cyl((-18.0, -195.0, -95.0), (-18.0, -168.0, -95.0), 11.0))   # PSL-702 switch (hex 22, +y)
parts['OL-217_Oil_Distribution_Block'] = (man.removeSplitter(), 0.9, 'make',
    'Al 6082 block 40 x 30 x 30: inlet from the cooler, 2 outlets (core / pod) with fixed restrictors to share the flow, PT-701 0-10 barg, '
    'PSL-702 low-oil switch (1.0 barg, trips the fuel via SR1), TE-708 supply PT1000', 'block local; PT Danfoss (DK) MBS 3000; PSL Barksdale (DE) / Suco (DE)')

# ---------------------------------------------------------------- oil lines (OD: pressure 8 x 1, scavenge 10 x 1, drains 12 x 1 hose)
lines_p = [
    [(f['x'], f['y'] + f['r'] + 2, zl + 15), (f['x'], P_[0], zl + 15), (f['x'], P_[0], P_[1]), (-5.0, P_[0], P_[1]), (-5.0, -312.0, P_[1]),
     (L['x1'] - 25, -312.0, L['z']), (L['x1'] - 25, L['y'] - L['r'] - 8, L['z'])],                                                             # filter -> cooler
    [(L['x0'] + 25, L['y'] - L['r'] - 8, L['z']), (L['x0'] + 25, -312.0, L['z']), (L['x0'] + 25, -312.0, -55.0), (-70.0, -225.0, -55.0),
     (-70.0, -210.0, -95.0), (M['x'][0], -210.0, -95.0)],                                                                                          # cooler -> block
    [(-25.0, -210.0, M['z'][1]), (-25.0, -210.0, -40.0), (-30.0, -150.0, -10.0), rad(-30.0, 185.0, 107.0)],                                      # block -> core feed
    [(-45.0, -210.0, M['z'][1]), (-45.0, -210.0, 85.0), (-150.0, -210.0, 85.0), (-150.0, -40.0, 85.0), (-265.0, -40.0, 85.0), (-265.0, 0.0, 85.0), (-265.0, 0.0, 67.0)],
    [(-150.0, -40.0, 85.0), (-136.0, -40.0, 85.0), (-136.0, 0.0, 85.0), (-136.0, 0.0, 67.0)],
]
lp = comp([tube_path(p, 4.0) for p in lines_p])
parts['OL-220_Oil_Feed_Lines_8x1'] = (lp, 1.2, 'make',
    '1.4571 tube 8 x 1, DIN 2353 24 deg fittings (VOSS): filter -> cooler -> block -> core bulkhead (185 deg) and over the pod (y -40, z 85, '
    'below the filter-box floor) to the 2 jets', 'tube Sandvik (SE); fittings VOSS (DE)')
lines_s = [
    [(-262.0, 0.0, -73.0), (-262.0, 0.0, -82.0), (-262.0, -70.0, -92.0), (-139.0, -70.0, -98.0), (-125.0, -170.0, -103.0), (-120.0, -170.0, -107.0), (-120.0, -182.0, -107.0)],
    [(-139.0, 0.0, -71.0), (-139.0, 0.0, -85.0), (-139.0, -70.0, -98.0)],
    [rad(-30.0, 275.0, 107.0), rad(-30.0, 275.0, 115.0), (-30.0, -150.0, -112.0), (-90.0, -170.0, -112.0), (-90.0, -182.0, -112.0)],
]
ls = comp([tube_path(p, 6.0) for p in lines_s])
lsp = tube_path([(C['x1'] + 2, C['y'], C['z']), (C['x1'] + 7, C['y'], C['z']), (C['x1'] + 15, S_[0], S_[1]), (205.0, S_[0], S_[1]), (205.0, S_[0], zl + 20), (205.0, ps['y'] + 30, zl + 20)], 5.0)
parts['OL-221_Oil_Drain_Scavenge_Lines'] = (comp([ls, lsp]), 1.3, 'make',
    'gravity drains 12 x 1 (pod G1/4 bottom ports, core 275 deg bulkhead) falling continuously to the collector; suction line 10 x 1 to '
    'the scavenge pump; TE-705/706 in the collector inlets', 'tube Sandvik (SE); fittings VOSS (DE)')

# ---------------------------------------------------------------- pod oil fittings + core oil tubes inside the intake
pf = []
for x in (-265.0, -136.0):                                                  # jet feed: M8x1 straight fitting on the shell boss + internal tube
    pf.append(hexbar((x, 0.0, 60.0), (x, 0.0, 67.0), 10.0))
pf.append(cyl((-265.0, 0.0, 44.5), (-265.0, 0.0, 49.0), 1.5, 1.0))        # front: shell -> G-202 web drilling
pf.append(cyl((-136.0, 0.0, 21.0), (-136.0, 0.0, 49.0), 1.5, 1.0))        # rear: shell -> G-204 hub drilling across the cavity
pf.append(hexbar((-262.0, 0.0, -61.0), (-262.0, 0.0, -66.0), 17.0))        # front drain G1/4 hose-barb fitting
pf.append(cyl((-262.0, 0.0, -66.0), (-262.0, 0.0, -73.0), 6.0, 4.0))
pf.append(hexbar((-139.0, 0.0, -60.0), (-139.0, 0.0, -65.0), 14.0))        # rear drain G1/8 (next to the plenum wall x -130)
pf.append(cyl((-139.0, 0.0, -65.0), (-139.0, 0.0, -71.0), 6.0, 4.0))
parts['OL-222_Pod_Oil_Fittings'] = (comp(pf), 0.25, 'buy',
    '2 x M8x1 straight fittings (jets) + 2 internal 3 x 0.5 feed tubes (shell -> end-shield drillings), 2 x G1/4 drain elbows; '
    'the G-202 / G-204 jet drillings meet the tubes at x -265.0 / -136 (D2R detail)', 'VOSS (DE) fittings; tubes local')
ct = [tube_path([(-18.0, 47.2 * math.cos(math.radians(161.2)), 47.2 * math.sin(math.radians(161.2))), rad(-30.0, 161.2, 47.2), rad(-30.0, 185.0, 58.0), rad(-30.0, 185.0, 100.0)], 2.0, 1.5),
      tube_path([rad(-18.0, 272.0, 47.2), rad(-30.0, 272.0, 47.2), rad(-30.0, 275.0, 58.0), rad(-30.0, 275.0, 100.0)], 3.0, 2.5)]
for a in (185.0, 275.0):
    ct.append(hexbar(rad(-30.0, a, 100.0), rad(-30.0, a, 106.0), 17.0))    # bulkhead unions on the can bosses
parts['OL-224_Core_Oil_Tubes_Intake'] = (comp(ct), 0.15, 'make',
    'core oil feed 4 x 0.5 (v13A 161 deg diffuser-land route -> skirt / can bulkheads 185 deg) and scavenge + vent 6 x 0.5 (272 deg land, '
    're-drilled 6.2, -> 275 deg bulkheads, carries the 2 core-bearing TCs TE-724/725 alongside); FKM grommets in the d9 bulkhead holes; '
    'inside the core the routes continue to the tunnel-flange drillings (D2R detail); the IntakeOuter bosses are re-drilled 4.2 / 6.2',
    'tube Sandvik (SE); local bending + brazing')

# ---------------------------------------------------------------- glycol loop
R = LY.RADIATOR
rx0, rx1 = R['x0'], R['x0'] + R['t']
ry0, ry1 = R['y0'], R['y0'] + R['w']
rz0, rz1 = R['z0'], R['z0'] + R['h']
xm = 0.5 * (rx0 + rx1)
rad_ = box(rx0, rx1, ry0, ry1, rz0, rz1)
rad_ = rad_.fuse(cyl((xm, ry1 - 15, rz0 + 10), (xm, ry1 + 5, rz0 + 10), 8.0))       # outlet (bottom, +y tank) to y -170
rad_ = rad_.fuse(cyl((xm, ry0 + 10, rz1 - 2), (xm, ry0 + 10, rz1 + 5), 8.0))       # inlet (top, -y tank)
parts['GC-310_Radiator_Core'] = (rad_.removeSplitter(), 2.6, 'buy',
    'Al bar-and-plate glycol/air core 280 x 320 x 52 with side tanks, 2.0 kW at ITD ~21 K, 1300 m3/h (NTU ~1.05, eps 0.58: est); '
    'outlet bottom +y, inlet top -y, vent at the top', 'AKG Thermotechnik (DE), Setrab (SE) ProLine core, Bowman (UK)')
fan = cyl((LY.FAN['x0'] + 8, 0.5 * (ry0 + ry1), 0.5 * (rz0 + rz1)), (LY.FAN['x1'] - 4, 0.5 * (ry0 + ry1), 0.5 * (rz0 + rz1)), 138.0)
parts['GC-311_Radiator_Fan_305_24V'] = (fan, 1.4, 'buy',
    '305 mm axial fan 24 V brushless with PWM (DC-1-FAN tag), pusher, 1300 m3/h at ~100 Pa, 30-150 W; air leaves +x (away from the intake)',
    'SPAL (IT) brushless 12-inch range, ebm-papst (DE) W3G/W1G 300')
gp = LY.GLY_PUMP
pump = box(gp['x0'] + 15, gp['x1'] - 15, gp['y0'], gp['y1'], ZD, gp['z1'])
for xe in (gp['x0'], gp['x1']):
    pump = pump.fuse(cyl((xe, 0.5 * (gp['y0'] + gp['y1']), -60.0), (gp['x0'] + 15 if xe == gp['x0'] else gp['x1'] - 15, 0.5 * (gp['y0'] + gp['y1']), -60.0), 12.0))
parts['GC-312_Glycol_Circulator_M751'] = (pump.removeSplitter(), 2.1, 'buy',
    'M-751 wet-rotor circulator 130 mm, G1 unions, PWM input, 230 V 4-52 W, max head 7.5 m (loop needs %.1f m at %.1f L/min)' % (GLY['head_m'], GLY['flow_L_min']),
    'Grundfos (DK) UPM3 FLEX AS 15-75 130; Wilo (DE) Para 15-130/7')
e = LY.EXP_TANK
et = box(e['x0'], e['x1'], e['y0'], e['y1'], e['z0'], e['z1']).fuse(cyl((0.5 * (e['x0'] + e['x1']), 0.5 * (e['y0'] + e['y1']), e['z1']), (0.5 * (e['x0'] + e['x1']), 0.5 * (e['y0'] + e['y1']), e['z1'] + 20), 18.0))
et = et.fuse(cyl((396.0, -290.0, G4[1] + 180.0 + 7.5), (396.0, -290.0, e['z0']), 6.0))
parts['GC-313_Expansion_Tank_1L'] = (et.removeSplitter(), 0.6, 'buy',
    '1.0 L PP expansion tank with 1.0 bar pressure cap, LSL-756 level switch, on the top run of the loop (highest point); PT-755 / TE-754 '
    'in the loop', 'MAHLE / Behr (DE) truck expansion-tank class, Reflex (DE)')
ztop = G4[1] + 180.0                                                          # top run above the shroud
hoses = [
    [(xm, ry1 + 5, rz0 + 10), (xm, G1[0], rz0 + 10), (385.0, G1[0], G1[1]), (-145.0, G1[0], G1[1]), (-145.0, -259.0, -60.0), (gp['x1'], -259.0, -60.0)],   # radiator -> pump
    [(gp['x0'], -259.0, -60.0), (-293.0, -259.0, -60.0), (-293.0, -259.0, 40.0), (-293.0, -120.0, 52.0), (-244.0, -120.0, 52.0), rad(-244.0, 135.0, 80.0), rad(-244.0, 135.0, 71.0)],  # pump -> PMG
    [rad(-170.5, 135.0, 71.0), rad(-170.5, 135.0, 80.0), (-170.5, -150.0, 56.6), (-170.5, -255.0, 56.6), (L['x1'] - 10, -255.0, 10.0), (L['x1'] - 10, L['y'], 10.0), (L['x1'] - 10, L['y'], -50.0)],  # PMG -> cooler
    [(L['x0'] + 10, L['y'], -50.0), (L['x0'] + 10, L['y'], -20.0), (L['x0'] + 10, G4[0], G4[1]), (305.0, G4[0], G4[1]), (305.0, G4[0], ztop), (396.0, G4[0], ztop), (396.0, ry0 + 10, ztop), (xm, ry0 + 10, rz1 + 5)],  # cooler -> radiator
]
gh = comp([tube_path(p, 7.5) for p in hoses])
parts['GC-314_Glycol_Hoses_8mm'] = (gh, 1.9, 'buy',
    'EPDM coolant hose 8 x 15 (peroxide-cured, 40 %% PG, 120 C) with clamps / push-on barbs, ~%.1f m; G1/4 barbs at the pod, '
    'G1 unions at the circulator' % LY.GLYCOL['hose_L_m'], 'ContiTech (DE), Semperit (AT), Trelleborg (SE)')

export(parts, 'LUBE_COOL', dict(title='GR180 D2 closed-loop oil + generator glycol loop', frame='ENG mm', calc='sim/variant_d/d2a_aux_calc.json',
                                oil=dict(feed_L_min=OIL['feed_L_min'], heat_W=OIL['heat_total_W'], dT_K=OIL['dT_oil_K'], charge_L=3.0),
                                glycol=dict(flow_L_min=GLY['flow_L_min'], heat_W=GLY['heat_W']['total'], head_m=GLY['head_m'],
                                            T_supply_C=[t['T_glycol_supply_C'] for t in GLY['temperatures']])),
       'd2a_lube_cool_parts.json')
