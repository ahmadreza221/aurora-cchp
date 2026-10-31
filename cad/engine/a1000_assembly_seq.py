"""AURORA-1000 corrected build order (docs/08 sec. 19), read by cad/engine/a1000_assembly_check.py ('new') and mirrored
by the Fusion add-in fusion/AURORA1000_Animate.

Each move: (label, [(part-name prefix, half)], path). half None = whole part, 'L' / 'U' = the part cut at z = 0 (lower /
upper half: the machine splits it there), 'Sa:b' = solids a..b-1 of a compound (studs 0:16, nuts 16:32 of RT-11x).
path = offsets (dx, dy, dz[, dr]) from home, start first; the last point is where the parts stay (0 = home; R1, R2 and
the rear stub are parked 6 mm short so that a 6 mm nut fits in the 13 mm cavity and can be started on the stud tips, then
the nuts pull the part home; the drum - R1 nuts seat on R1 and move with it, the R1 - R2 and R2 - stub nuts seat on the
part already home); dr moves every solid along its own radial direction (nuts into the rotor cavities, scroll pins).

Build stand frame, gravity -z:
  A  rotor stack, balanced as one unit outside the engine
  B  lower shell on the stand: scroll pressure casing, scroll, turbine casing, compressor casing, inlet casing (phase 3),
     front bearing housing on its brackets, lower bearing halves, lower stator half-module (C1 + C2 with NGV1 / NGV2,
     shrouds, liners, diaphragms, support keys, pre-assembled on the bench: the carrier hooks are slid over the NGV rings
     axially there)
  C  rotor lowered in (rear stub on a tail-stock support tool until JB2 is in)
  D  upper halves (inlet casing after the compressor casing), upper scroll pins from outside, exhaust frame from the rear,
     JB2 seal ring and cartridge from the rear
  E  combustor can from above
  F  package (the core waits on the crane, parked 3 m up): base frame with the reservoir, pipe supports, lube module, lower
     plenum half; core lowered into it; FB oil block, the FB lines in two spools each (tunnel spool in through the open
     tunnel mouth, outer spool from above, union at the mouth); gearbox, generator, couplings through the open tunnel; upper
     plenum half; recuperator; the other lines (hoses are flexible: only their final position is checked)
"""
ROT = [('RT-1', None), ('A1000_R1 disc', None), ('Blisk 1 blade', None), ('A1000_R2 disc', None), ('Blisk 2 blade', None),
       ('Impeller', None)]
R1U = [('A1000_R1 disc', None), ('Blisk 1 blade', None)]
R2U = [('A1000_R2 disc', None), ('Blisk 2 blade', None)]
HOT = ['NGV1', 'HS-210', 'HS-211', 'HS-230', 'HS-231', 'CB-350', 'HS-220', 'HS-221', 'HS-222', 'HS-234', 'HS-232', 'HS-233', 'NGV2']
JB1 = ['JB1 integral', 'JB1 pad carrier', 'JB1 tilting', 'TB carrier', 'TB thrust pads']
COMP = ['Compressor casing', 'Diffuser', 'Return-channel']
CORE = (['RT-1', 'A1000_R', 'Blisk', 'Impeller', 'JB', 'TB ', 'FB-', 'HS-', 'NGV', 'Compressor casing', 'Diffuser', 'Return-channel',
         'CB-', 'Exhaust', 'EX-40', 'EX-41', 'EX-42', 'EX-43', 'IN-50'])
TUN = ['PL-02', 'PL-03', 'PL-05', 'PL-07', 'PL-09']                 # FB lines: tunnel spool 'T' + outer spool 'O'
PARK = (0, 0, 3000)                                                # core on the crane while the package is built
Z0, UP, DOWN = (0, 0, 0), (0, 0, 600), (0, 0, -600)
ST = (0, 0, 1500)                                                  # rotor stacking position, above the stand

SEQ = [
    # A rotor stack (the stub stands on the build table, everything else comes along the axis)
    ('A1 front stub + thrust collar', [('RT-101', None)], [(-200, 0, 1500), ST]),
    ('A2 impeller 1', [('Impeller 1', None)], [(400, 0, 1500), ST]),
    ('A3 compressor spacer RT-104', [('RT-104', None)], [(400, 0, 1500), ST]),
    ('A4 impeller 2', [('Impeller 2', None)], [(400, 0, 1500), ST]),
    ('A5 drum RT-105', [('RT-105', None)], [(400, 0, 1500), ST]),
    ('A6 tie bolt M42 (through the stub)', [('RT-102', None)], [(-800, 0, 1500), ST]),
    ('A7 tie-bolt nut', [('RT-103', None)], [(-200, 0, 1500), ST]),
    ('A8 studs drum - R1 into the drum flange', [('RT-111', 'S0:16')], [(80, 0, 1500), ST]),
    ('A9 R1 blisk onto the studs, parked 6 mm short', R1U, [(400, 0, 1500), (6, 0, 1500)]),
    ('A10 nuts drum - R1 in radially behind the stud tips, then 3 mm onto them', [('RT-111', 'S16:32')],
     [(9, 0, 1500, 150), (9, 0, 1500, 0), (6, 0, 1500, 0)]),
    ('A11 R1 pulled home by the nuts', R1U + [('RT-111', 'S16:32')], [(6, 0, 1500), ST]),
    ('A12 turbine spacer ring RT-107', [('RT-107', None)], [(400, 0, 1500), ST]),
    ('A13 R2 blisk with the R1 - R2 studs, parked 6 mm short', R2U + [('RT-112', 'S0:16')], [(400, 0, 1500), (6, 0, 1500)]),
    ('A14 nuts R1 - R2 in radially (R1 aft cavity), then 3 mm onto the stud tips (they seat on R1)', [('RT-112', 'S16:32')],
     [(-3, 0, 1500, 150), (-3, 0, 1500, 0), ST]),
    ('A15 R2 pulled home by the nuts', R2U + [('RT-112', 'S0:16')], [(6, 0, 1500), ST]),
    ('A16 rear stub with the R2 - stub studs, parked 6 mm short', [('RT-106', None), ('RT-113', 'S0:16')], [(400, 0, 1500), (6, 0, 1500)]),
    ('A17 nuts R2 - stub in radially (R2 aft cavity), then 3 mm onto the stud tips (they seat on R2)', [('RT-113', 'S16:32')],
     [(-3, 0, 1500, 150), (-3, 0, 1500, 0), ST]),
    ('A18 rear stub pulled home (rotor balanced as one unit)', [('RT-106', None), ('RT-113', 'S0:16')], [(6, 0, 1500), ST]),
    # B lower shell on the build stand
    ('B1 scroll pressure casing, lower half CB-341', [('CB-341', None)], [UP, Z0]),
    ('B2 hot-gas scroll lower half, deswirl vanes, insulation', [('CB-331', None), ('CB-332', 'L'), ('CB-333', 'L')], [UP, Z0]),
    ('B3 lower scroll support pins, radially through CB-341', [('CB-360', 'L')], [(0, 0, 0, 250), (0, 0, 0, 0)]),
    ('B4 turbine casing lower half HS-202 (bottom key cast on)', [('HS-202', None)], [UP, Z0]),
    ('B5 compressor casing lower half with its vanes', [(p, 'L') for p in COMP], [UP, Z0]),
    ('B5b inlet casing lower half IN-502 (lowered 15 mm forward, then slid back onto the compressor-casing spigot)',
     [('IN-502', None)], [(-15, 0, 600), (-15, 0, 0), Z0]),
    ('B6 front bearing housing lower half FB-2 onto the IN-502 brackets', [('FB-2', None)], [UP, Z0]),
    ('B7 lower halves of JB1 (ISFD, carrier, 2 pads) and of the thrust bearing', [(p, 'L') for p in JB1], [(0, 0, 300), Z0]),
    ('B8 lower stator half-module (C1 + C2, NGV1 / NGV2, shrouds, liners, diaphragms, support keys)',
     [(p, 'L') for p in HOT] + [('HS-240', None)], [UP, Z0]),
    # C the balanced rotor goes in as one unit
    ('C1 rotor lowered into the lower halves', ROT, [ST, Z0]),
    # D upper halves, exhaust frame, JB2
    ('D1 upper halves of JB1 and of the thrust bearing', [(p, 'U') for p in JB1], [(0, 0, 300), Z0]),
    ('D2 front bearing housing upper half FB-1', [('FB-1', None)], [UP, Z0]),
    ('D3 upper stator half-module', [(p, 'U') for p in HOT], [UP, Z0]),
    ('D4 compressor casing upper half', [(p, 'U') for p in COMP], [UP, Z0]),
    ('D4b inlet casing upper half IN-501 from above (hub wall over FB-1, spigot on the compressor casing)', [('IN-501', None)], [UP, Z0]),
    ('D5 turbine casing upper half HS-201 (top key into the carrier slot)', [('HS-201', None)], [UP, Z0]),
    ('D6 hot-gas scroll upper half, deswirl vanes, insulation', [('CB-330', None), ('CB-332', 'U'), ('CB-333', 'U')], [UP, Z0]),
    ('D7 scroll pressure casing upper half CB-340', [('CB-340', None)], [UP, Z0]),
    ('D8 upper scroll support pins, radially through CB-340', [('CB-360', 'U')], [(0, 0, 0, 250), (0, 0, 0, 0)]),
    ('D9 exhaust air manifold EX-401 from the rear (phase 2)', [('EX-401', None)], [(700, 0, 0), Z0]),
    ('D10 exhaust frame from the rear over the tail-stock tool (phase 2: EX-410 + shield + leaf seals)',
     [('Exhaust diffuser', None), ('EX-410', None), ('EX-411', None), ('EX-413', None), ('EX-414', None)], [(700, 0, 0), Z0]),
    ('D11 frame pins EX-402, radially through the manifold', [('EX-402', None)], [(0, 0, 0, 250), (0, 0, 0, 0)]),
    ('D12 JB2 split seal ring, lower half (along the axis below the shaft, then up)', [('JB2 front seal', 'L')], [(250, 0, -70), (0, 0, -70), Z0]),
    ('D13 JB2 split seal ring, upper half', [('JB2 front seal', 'U')], [(250, 0, 70), (0, 0, 70), Z0]),
    ('D14 JB2 cartridge with the frame support ring EX-412 from the rear (keys through the hub slots)',
     [('JB2 bearing', None), ('JB2 integral', None), ('JB2 pad carrier', None), ('JB2 tilting', None), ('JB2 heat shield', None),
      ('EX-412', None)], [(400, 0, 0), Z0]),
    ('D15 JB2 end cover', [('JB2 end cover', None)], [(200, 0, 0), Z0]),
    ('D16 exhaust collector, hub cover, transition (phase 2)', [('Exhaust collector', None), ('EX-420', None), ('EX-421', None),
                                                                ('EX-430', None)], [(700, 0, 0), Z0]),
    # E combustor
    ('E1 can base plate + can casing', [('CB-302', None), ('CB-301', None)], [(0, 0, 1300), Z0]),
    ('E2 liner + impingement sleeve (welded unit)', [('CB-320', None), ('CB-321', None)], [(0, 0, 1300), Z0]),
    ('E3 head cover + premixers', [('CB-303', None), ('CB-310', None)], [(0, 0, 1000), Z0]),
    ('E4 igniter along its own axis (15 % tilt toward +y)', [('CB-371', 'S0:1')], [(0, 44.5, 296.7), Z0]),
    ('E4b UV flame scanners from above', [('CB-371', 'S1:3')], [(0, 0, 500), Z0]),
    ('E5 fuel manifolds, pigtails, bulkhead', [('CB-370', None)], [(0, 0, 500), Z0]),
    # F package: the core waits on the crane; base frame, supports, lube module and the lower plenum half first
    ('F0 engine core lifted off the build stand (parked 3 m up)', [(p, None) for p in CORE], [Z0, PARK]),
    ('F1 base frame with the oil reservoir', [('Base frame', None), ('LO-100', None)], [(0, 0, -800), Z0]),
    ('F2 pipe supports onto the base frame', [('PL-90', None)], [(0, 0, 600), Z0]),
    ('F3 JB2 drain: rigid spool onto its supports from above (it lies under the scroll casing and the plenum box)',
     [('PL-06', 'N:960:1100:-100:100:-700:-500')], [(0, 0, 600), Z0]),
    ('F4 lube module', [('Lube oil module', None)], [(0, -800, 0), Z0]),
    ('F5 plenum lower half IN-511 (phase 3)', [('IN-511', None)], [(0, 0, 1200), Z0]),
    ('F6 engine core lowered into the plenum lower half and onto the base frame', [(p, None) for p in CORE], [PARK, Z0]),
    ('F7 FB oil block in front of the plenum', [('PL-01', None)], [(0, 0, 600), Z0]),
    ('F8 tunnel spools of the JB1 / TB oil lines: in through the tunnel mouth and the IN-502 bracket windows',
     [('PL-02', 'T'), ('PL-03', 'T')], [(-300, 0, 0), Z0]),
    ('F9 tunnel spool of the FB drain: in through the tunnel mouth, the DN40 ends slide under the socket faces', [('PL-05', 'T')],
     [(-300, 0, 0), Z0]),
    ('F10 tunnel spool of the FB vent: in 5 mm high, then down onto the FB-1 boss', [('PL-07', 'T')], [(-300, 0, 5), (0, 0, 5), Z0]),
    ('F11 tunnel spool of the buffer air: in through the tunnel mouth (its end slides along the FB-2 boss face)', [('PL-09', 'T')],
     [(-300, 0, 0), Z0]),
    ('F12 outer spools of the FB oil, drain and vent lines from above (unions at the tunnel mouth and on the oil block)',
     [(p, 'O') for p in TUN[:4]], [(0, 0, 700), Z0]),
    ('F13 buffer air: riser spool and the run along the plenum side from above', [('PL-09', 'B:-200:-146:-800:-200:-200:620'),
                                                                                  ('PL-09', 'B:-146:300:-800:-600:400:620')], [(0, 0, 700), Z0]),
    ('F14 buffer air: valve block and the tap spool from -y, under the can base plate', [('PL-09', 'B:300:420:-800:50:480:620')],
     [(0, -700, 0), Z0]),
    ('F15 gearbox + starter', [('Epicyclic', None), ('Starter', None)], [(0, 0, 800), Z0]),
    ('F16 generator', [('Synchronous generator', None)], [(0, 0, 800), Z0]),
    ('F17 high-speed coupling from above through the open tunnel', [('High-speed coupling', None)], [(0, 0, 700), Z0]),
    ('F18 low-speed coupling', [('Low-speed coupling', None)], [(0, 0, 400), Z0]),
    ('F19 plenum upper half IN-510 + filter-house adapter IN-520 (phase 3)', [('IN-510', None), ('IN-520', None)], [(0, 0, 1200), Z0]),
    ('F20 recuperator, ducts, BOV, economizer + stack (phase 2)', [('Recuperator', None), ('EX-44', None), ('EX-45', None),
                                                                   ('EX-46', None), ('EX-47', None)], [(0, 1400, 0), Z0]),
    ('F21 JB2 vent: rigid spool from -y, 20 mm high over the deck, then down', [('PL-08', 'N:980:1100:-660:-500:-40:40')],
     [(0, -400, 20), (0, 0, 20), Z0]),
    ('F22 JB2 drain and vent hoses at the struts (flexible: final position only)', [('PL-06', 'B:960:1100:-100:100:-700:-500'),
                                                                                    ('PL-08', 'B:980:1100:-660:-500:-40:40')], [Z0]),
    ('F23 JB2 oil line: rigid spool along the scroll casing from -y', [('PL-04', 'N:930:1012:-30:30:560:650')], [(0, -500, 0), Z0]),
    ('F24 JB2 oil hose down to the top strut (flexible: final position only)', [('PL-04', 'B:930:1012:-30:30:560:650')], [Z0]),
    ('F25 gas valve block from -y (under the exhaust collector)', [('PL-10', 'B:995:1305:-1205:-895:-705:-295')], [(0, -600, 0), Z0]),
    ('F26 fuel hoses to the CB-370 drops (flexible: final position only)', [('PL-10', 'N:995:1305:-1205:-895:-705:-295')], [Z0]),
    ('F27 gearbox oil feed from above', [('PL-13', None)], [(0, 0, 600), Z0]),
    ('F28 combustor drains + drain pot from -y', [('PL-12', None)], [(0, -500, 0), Z0]),
]
