# GR180 version D2 - natural-gas fuel system (FU-1xx): combustor gas manifold sized for ~7 g/s (replaces the v13A Ø5 ring,
# 12 x Ø1.1-ID needles and Ø6 feed that were sized for ~2.5 g/s), gas line from the train to the v13A casing bulkhead
# (under the core, up the +y side close to the casing), and the gas train on the AUX service panel (-y outer face):
# HV-601 ball valve -> FG-602 filter -> PT-601/PSL-602 -> PCV-605 regulator -> PT-604/PSH-603 -> XV-611 SSV1 -> PT-613
# -> XV-612 SSV2 -> FCV-620 proportional valve -> PT-605/TE-607 -> engine.  Bought items = catalogue-class envelopes.
# Numbers: sim/variant_d/d2a_aux_calc.py.  ENG frame mm.
# Run after d2a_skid.py: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2a_fuel.py -> cad_out/variant_d/D2/AUX/FU-*.step
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2a_common import *

clear_aux({'FU'})
CALC = json.load(open(os.path.join(ROOT, 'sim', 'variant_d', 'd2a_aux_calc.json')))
parts = {}

# ---------------------------------------------------------------- FU-110 combustor gas manifold (in the engine)
xr, rr = LY.X_RING, LY.R_RING
ro, ri = LY.RING['od'] / 2, LY.RING['id'] / 2
N = LY.NEEDLE
B = LY.BULKHEAD
fpts8 = [rad(B['x'], B['ang'], LY.R_UNION[0]), rad(B['x'], B['ang'], 48.4)]              # 8 x 0.5 through the bulkhead bore
fpts7 = [rad(B['x'], B['ang'], 48.4), rad(11.3, 56.0, 45.3), rad(xr, LY.TEE_ANG, rr)]       # 7 x 0.5 joggle to the ring (clears the cap x 18.3)
outer = [Part.makeTorus(rr, ro, V(xr, 0, 0), XA), tube_path(fpts8, LY.FEED['od'] / 2), tube_path(fpts7, 3.5)]
inner = [Part.makeTorus(rr, ri, V(xr, 0, 0), XA), tube_path(fpts8, LY.FEED['id'] / 2), tube_path(fpts7, 3.0)]
for k in range(N['n']):
    a0, a1 = rad(N['x0'], N['ang0'] + 30 * k, rr), rad(N['x1'], N['ang0'] + 30 * k, rr)
    outer.append(cyl(a0, a1, N['od'] / 2))
    inner.append(cyl(rad(N['x0'] - 0.5, N['ang0'] + 30 * k, rr), rad(N['x1'] + 0.5, N['ang0'] + 30 * k, rr), N['id'] / 2))
for a in (30.0, 150.0, 270.0):                                          # SS strip clips spot-welded to the cap front face (x 18.3)
    c = box(xr, 18.3, -1.5, 1.5, rr + ro - 0.2, rr + ro + 0.5)
    c.rotate(V(0, 0, 0), XA, a - 90.0)
    outer.append(c)
o = outer[0]
for s_ in outer[1:]:
    o = o.fuse(s_)
i_ = inner[0]
for s_ in inner[1:]:
    i_ = i_.fuse(s_)
man = o.cut(i_).removeSplitter()
parts['FU-110_Gas_Manifold_Ring_12_Needles'] = (man, man.Volume * 7.9e-6, 'make',
    'ring 7 x 0.5 1.4571 rolled to r 42.1 at x 11.7 (TIG butt), 12 needles 2.0 x 0.2 1.4301 (ID 1.6) brazed in, 10 mm into the vaporiser-stick '
    'mouths (sticks kept as gas premix tubes); feed 8 x 0.5 through the v13A M12x1 bulkhead (bore 8), inside a 7 x 0.5 joggle (clears the CC cap) joining the ring at 60 deg; '
    '3 strip clips to the cap; dp 0.27 bar at 15 C, 0.35 bar at 7.2 g/s; leak test 6 bar, flow-balance test (12 needles +/-5 %)',
    'needles: Goodfellow (UK) / Coopers Needle Works (UK) precision tube; local TIG + vacuum brazing')

# ---------------------------------------------------------------- FU-111 gas line + PT-605/TE-607 tee, FU-112 braided hose + union
GL = LY.GAS_LINE
line = tube_path(LY.GAS_PATH, GL['od'] / 2, GL['id'] / 2)
tee = box(220.0, 250.0, -322.0, -292.0, 135.0, 165.0).cut(cyl((235.0, -330, 150.0), (235.0, -285, 150.0), GL['id'] / 2))
pt605 = cyl((235.0, -307.0, 165.0), (235.0, -307.0, 255.0), 13.5)          # PT-605 (Danfoss MBS 3000 class, hex 27)
te607 = cyl((250.0, -307.0, 150.0), (300.0, -307.0, 150.0), 4.0)           # TE-607 PT1000 in a thermowell
line = line.fuse([tee, pt605, te607]).removeSplitter()
parts['FU-111_Gas_Line_15x1_PT605_TE607'] = (line, 1.6 * 0.35 + 0.9, 'make',
    GL['spec'] + '; tee block 1.4404 with PT-605 manifold pressure (0-6 barg, 4-20 mA) and TE-607 PT1000 class A; '
    'route: panel outlet -> down -> under the core at x 100 -> up the +y side at y 64 (outside the intake filter zone)',
    'tube: Sandvik / Outokumpu; fittings VOSS (DE) or Walterscheid (DE); PT: Danfoss (DK) MBS 3000, Keller (CH); TE: WIKA (DE), JUMO (DE)')
hp = [p if p[0] != 'rad' else rad(p[1], p[2], p[3]) for p in LY.GAS_HOSE]
hose = tube_path(hp, 10.0, 6.0)
uni = hexbar(rad(B['x'], B['ang'], LY.R_UNION[0]), rad(B['x'], B['ang'], LY.R_UNION[1]), 22.0)
uni = uni.cut(cyl(rad(B['x'], B['ang'], LY.R_UNION[0] - 1), rad(B['x'], B['ang'], LY.R_UNION[1] + 1), 4.0))
parts['FU-112_Braided_Gas_Hose_DN12_Union'] = (hose.fuse(uni).removeSplitter(), 0.55, 'buy',
    'DN12 x 0.4 m stainless corrugated hose with braid, EN ISO 10380 / EN 14800 gas-approved, 24 deg cone ends; 8/15 reducing union '
    'on the bulkhead tube (takes engine growth + vibration)', 'Witzenmann (DE), Hydra; union VOSS (DE)')

# ---------------------------------------------------------------- gas train (service panel, -y outer face)
y, za, zb = LY.Y_GAS, LY.Z_A, LY.Z_B
R15 = 21.3 / 2
# FU-121 HV-601 ball valve Rp1/2 full bore + lever
hv = cyl((250.0, y, za), (300.0, y, za), 22.0).fuse(box(243.0, 292.0, y - 4, y + 4, -12.0, -4.0)).fuse(cyl((285.0, y, za + 20), (285.0, y, -11.0), 5.0))
parts['FU-121_HV601_Ball_Valve_DN15'] = (hv.removeSplitter(), 0.45, 'buy',
    'HV-601 manual gas ball valve Rp1/2 full bore, EN 331, PN16, yellow lever, lockable in OFF', 'Giacomini (IT), Genebre (ES), Pettinaroli (IT)')
fg = box(120.0, 240.0, y - 37.5, y + 37.5, za - 40.0, za + 54.0)
parts['FU-122_FG602_Gas_Filter_DN15_6bar'] = (fg, 0.9, 'buy',
    'FG-602 gas filter Rp1/2, pmax 6 bar, 20 um washable cartridge, test points (Madas FM DN15 6 bar: A 120 / B 75 / C 94 mm)',
    'Madas (IT) FM; Dungs GF high-pressure version (DE) if available')
tA = box(75.0, 110.0, y - 18, y + 18, za - 18, za + 18)
parts['FU-123_Tap_Block_A_PT601_PSL602'] = (tA, 0.35, 'make',
    '1.4404 tee block Rp1/2 with G1/4 impulse port to instrument block A (PT-601 supply pressure, PSL-602 low-gas switch 3.3 barg)', 'local CNC')
pcv = box(-70.0, 55.0, y - 35, y + 35, za - 35, za + 25).fuse(cyl((-7.5, y, za + 25), (-7.5, y, za + 145), 55.0))
parts['FU-124_PCV605_Gas_Regulator_3.2barg'] = (pcv.removeSplitter(), 2.6, 'buy',
    'PCV-605 direct-acting gas pressure regulator Rp1/2, inlet 3.5-5 barg, set 3.2 barg (+/-5 %), lock-up, spring range 2-4 bar, '
    'max 36 Nm3/h at dp 0.3 bar (confirm sizing with the maker)', 'Pietro Fiorentini (IT), Madas (IT) RG/2MC high-pressure range, Mankenberg (DE)')
ssv = lambda xa: box(xa, xa + 90.0, y - 40, y + 40, zb - 40, zb + 40).fuse(cyl((xa + 45, y, zb + 40), (xa + 45, y, zb + 140), 37.5))
parts['FU-126_XV611_SSV1_EN161_DN15'] = (ssv(-105.0).removeSplitter(), 5.4, 'buy',
    'XV-611 safety shut-off valve 1 (SSV1), EN 161 class A group 2, DN15, 0-10 bar, NC, 24 VDC 40 W, closing < 1 s, POC switch ZSC-611 '
    '(Busch-Jost 23/08 EN161 stainless body: 5.4 kg)', 'Busch-Jost (DE) series 23/08 EN161; GSR (DE); Elektrogas (IT) 6-bar range')
tB = box(-10.0, 25.0, y - 18, y + 18, zb - 18, zb + 18).fuse(cyl((7.5, y, zb + 18), (7.5, y, zb + 108), 13.5))
parts['FU-127_Tap_Block_PT613_Proving'] = (tB.removeSplitter(), 0.45, 'make',
    '1.4404 tee block with PT-613 (0-6 barg) between the SSVs: valve-proving pressure test every start', 'local CNC; PT Danfoss (DK) / Keller (CH)')
parts['FU-128_XV612_SSV2_EN161_DN15'] = (ssv(30.0).removeSplitter(), 5.4, 'buy',
    'XV-612 safety shut-off valve 2 (SSV2), as SSV1, POC ZSC-612', 'Busch-Jost (DE) series 23/08 EN161; GSR (DE); Elektrogas (IT)')
fcv = box(135.0, 215.0, y - 30, y + 30, zb - 30, zb + 30).fuse(cyl((175.0, y, zb + 30), (175.0, y, zb + 140), 30.0))
parts['FU-129_FCV620_Proportional_Valve'] = (fcv.removeSplitter(), 4.0, 'buy',
    'FCV-620 direct-acting proportional solenoid valve G1/2, orifice ~8 mm, Kvs ~1.6, NC, 24 VDC PWM with Bürkert 8605 current driver; '
    'required Kv 0.81 at full flow (authority 2x); turndown ~10:1 (light-off 0.7 g/s); not a safety valve',
    'Bürkert (DE) Type 2836 (+8605); confirm the gas pressure rating for the chosen orifice')
pipes = []
for (a, b) in ((300.0, 306.0), (240.0, 250.0), (110.0, 120.0), (55.0, 75.0), (LY.X_RISER, -70.0)):
    pipes.append(cyl((a, y, za), (b, y, za), R15))
pipes.append(cyl((LY.X_RISER, y, za), (LY.X_RISER, y, zb), R15))
pipes += [Part.makeSphere(R15, V(LY.X_RISER, y, za)), Part.makeSphere(R15, V(LY.X_RISER, y, zb))]
for (a, b) in ((LY.X_RISER, -105.0), (-15.0, -10.0), (25.0, 30.0), (120.0, 135.0), (215.0, 235.0)):
    pipes.append(cyl((a, y, zb), (b, y, zb), R15))
pipes.append(Part.makeSphere(R15, V(235.0, y, zb)))
pipes.append(cyl((306.0, y, za), (306.0, y, -235.0), 11.0))                # inlet riser from the site (through the deck)
pipes.append(Part.makeSphere(11.0, V(306.0, y, za)))
pipes.append(cyl((LY.X_RISER, y, 40.0), (LY.X_RISER, -352.0, 40.0), 4.0))  # riser tap -> instrument block B
pipes.append(tube_path([(LY.X_RISER, -350.0, 40.0), (LY.X_RISER, -350.0, 100.0), (252.0, -350.0, 100.0), (252.0, -350.0, 170.0)], 3.0, 2.0))
# impulse tubes 6 x 1 to the instrument blocks (A: from FU-123, B: from the riser tap, run behind the panel edge)
imp = tube_path([(92.5, y + 18, za), (92.5, -350.0, za), (92.5, -350.0, -5.0), (252.0, -350.0, -5.0), (252.0, -350.0, 50.0)], 3.0, 2.0)
pipes.append(imp)
tr = comp(pipes)
parts['FU-130_Train_Piping_DN15'] = (tr, 2.2, 'make',
    'DN15 1.4571 seamless 21.3 x 2 nipples, 2 x 90 deg elbows, inlet riser from the site connection under the skid (Rp1/2 union, '
    'site flex hose by the plant), impulse tubes 6 x 1 to the instrument blocks; all threads with gas-approved sealant (EN 751-1)',
    'tube Sandvik (SE) / Outokumpu (FI); fittings VOSS (DE), Georg Fischer (CH) malleable for screwed parts')
iA = box(255.0, 315.0, -405.0, -341.0, 0.0, 112.0)
parts['FU-140_Instrument_Block_A_PT601_PSL602'] = (iA, 1.1, 'buy',
    'instrument block A on the panel: PT-601 supply pressure 0-10 barg 4-20 mA + PSL-602 low-gas pressure switch EN 1854 (3.3 barg, '
    'manual reset) on a 2-port manifold with isolation needle valve', 'PT: Danfoss MBS 3000 (DK), WIKA A-10 (DE); PSL: Dungs GW high-pressure (DE), GSR (DE)')
iB = box(255.0, 315.0, -405.0, -341.0, 118.0, 230.0)
parts['FU-141_Instrument_Block_B_PT604_PSH603'] = (iB, 1.1, 'buy',
    'instrument block B: PT-604 regulated pressure 0-6 barg + PSH-603 high-gas pressure switch EN 1854 (3.8 barg, manual reset)',
    'as block A')

export(parts, 'FUEL', dict(title='GR180 D2 natural-gas fuel system', frame='ENG mm', calc='sim/variant_d/d2a_aux_calc.json',
                           order='HV-601 > FG-602 > PT-601/PSL-602 > PCV-605 > PT-604/PSH-603 > XV-611 > PT-613 > XV-612 > FCV-620 > PT-605/TE-607 > FU-111/112 > bulkhead > FU-110',
                           fuel=dict(g_s_15C=CALC['fuel_vs_ambient'][1]['fuel_g_s'], Nm3_h_15C=CALC['fuel_vs_ambient'][1]['gas_Nm3_h'],
                                     design_max_g_s=CALC['fuel_design_max_g_s'], design_max_Nm3_h=CALC['fuel_design_max_Nm3_h']),
                           site_connection=dict(at=[306.0, LY.Y_GAS, -235.0], size='Rp1/2 union under the skid, 3.5-5 barg, plant HV/flex hose upstream')),
       'd2a_fuel_parts.json')
