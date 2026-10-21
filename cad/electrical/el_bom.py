"""GR180-CCHP electrical BOM -> docs/bom/electrical_bom.csv (columns per docs/06_master_design.md §5).

Sources: cad/electrical/el_items.py (equipment envelopes, boards), docs/electrical/02_io_list.csv (field devices),
docs/electrical/05_cable_schedule.md (cables, summarised here), docs/electrical/04_component_selection.md (makes).
No US-origin suppliers. Run:  python3 cad/electrical/el_bom.py
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import el_items as E  # noqa: E402

OUT = os.path.join(ROOT, 'docs', 'bom', 'electrical_bom.csv')
COLS = ['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes']
ROWS = []
STEP_ER, STEP_ROOF, STEP_ROUTE = 'cad_out/electrical/EL_ER.step', 'cad_out/electrical/EL_ROOF.step', 'cad_out/electrical/EL_ROUTE.step'


def row(tag, desc, qty, mob, spec, size, sup, kg, model='', notes=''):
    ROWS.append(dict(tag=tag, description=desc, qty=qty, make_or_buy=mob, material_or_spec=spec, size_or_rating=size,
                     supplier_candidates=sup, mass_kg=kg, model_file=model, notes=notes))


def kg(tag):
    return E.DIM[tag]['kg']


# ------------------------------------------------------------------ power conversion and storage (ER)
row('HI-1', 'three-phase hybrid inverter: GRID port (zero export via CT/meter), backup LOAD port (UPS), GEN port, 2 HV battery inputs, 3 MPPT '
    '(B3 DC, PV emulation 720 V)', 1, 'buy', 'EN 50549, VDE-AR-N 4105, IEC 62116/61727, IEC 62109-1/2; 100 % unbalanced (each phase <= 50 % rated); '
    'peak 1.5x rated 10 s; MPPT 150-850 V (full load 360-850 V), 1000 V max, 3x 36 A; battery 160-800 V, 2x 50 A; IP65',
    '30 kW / 33 kVA, grid pass-through 200 A', 'Deye SUN-30K-SG01HP3-EU-BM3 (CN; reference - only candidate with a seamless LOAD port at this size). '
    'European alternatives with non-seamless backup: SMA Sunny Tripower Hybrid X 30 + SMA Backup (DE), KOSTAL PLENTICORE G3 L 20 + BackUp Switch (DE)',
    kg('HI-1'), STEP_ER, E.DIM['HI-1']['src'] + '; UPS transfer time not in the datasheet (retailers: < 4 ms) - verify; both battery inputs '
    'paralleled to the one BOS-G20 stack per the Deye manual (verify)')
row('BAT-1', 'main battery HV LFP 20.48 kWh (user decision): 4x BOS-GM5.1 + HV control box HVB750V/100A-EU in 3U-LRACK', 1, 'buy',
    'LFP, 204.8 V nominal (166-234 V), 100 A nominal / 125 A 2 min, >= 6000 cycles, IEC 62619, VDE 2510-50, UN38.3, CAN to HI-1',
    '20.48 kWh, ~20 kW', 'Deye BOS-G20 (CN, on the Deye compatibility list); alt. BYD Battery-Box Premium HVM 22.1 (CN) only with Kostal/Fronius/SMA',
    kg('BAT-1'), STEP_ER, E.DIM['BAT-1']['src'])
row('BAT-2', '48 V essential-bus battery (controls, safety, post-lube, starter) in steel box with Class-T fuse', 1, 'buy',
    'LFP 48 V 100 Ah, CAN/RS-485 BMS', '4.8-5.1 kWh', 'Pylontech US5000 (CN); Victron Lithium NG 2x 25.6 V 100 Ah (NL); BMZ (DE)', kg('BAT-2'), STEP_ER)
row('CHG-48', '48 V battery chargers 230 VAC -> 54 V, N+1 with ORing (wall, next to BAT-2)', 2, 'buy', 'LFP charge profile, relay/Bluetooth status',
    '13 A each', 'Victron Smart IP43 Charger 48/13 (NL)', 2.7, STEP_ER, E.DIM['CHG-48']['src'])
row('DCDC-24', 'DC-DC 48 V -> 24 V DIN rail (ER and RP-1)', 2, 'buy', 'input 36-75 V, isolated', '24 V 10 A', 'PULS CD10.242 (DE); Traco TEP (CH)', 0.52,
    STEP_ER + ', ' + STEP_ROOF)
# ------------------------------------------------------------------ distribution, protection, metering (ER)
row('MDB', 'main distribution board: grid incomer MCCB 63 A 4P, SPD T1+2, zero-export CT, JT-920, HI-1 GRID MCB/RCD, LOAD MCCB 63 A, ATS-1, '
    'K-NPE, Q1 50 A, Q2 32 A, JT-901', 1, 'make', 'Rittal AX 1213.000 1000x1200x300 + IEC 61439-2 assembly', '400/230 V 63 A, Icw per site',
    'Rittal; ABB / Siemens / Schneider / Hager devices', kg('MDB'), STEP_ER)
row('ATS-1', 'automatic transfer switch, source I = HI-1 LOAD port, source II = grid (bypass on inverter fault), position 0 on FZ2 fire',
    1, 'buy', 'IEC 60947-6-1, mechanically interlocked break-before-make, position-0 input', '63 A 4P', 'Socomec ATyS p M 4P 63 A 9384 4006 (FR); ABB TruONE (CH/SE)',
    4.3, STEP_ER, 'dims 324x245 mm (distributor; depth to confirm)')
row('K-NPE', 'N-PE bonding contactor on the LOAD side in backup mode (driven by the inverter island signal)', 1, 'buy', 'AC-1, aux contact', '40 A 2P',
    'Siemens 3RT / ABB AF / Schneider TeSys', 0.4, STEP_ER, '01 §9')
row('AUX-DB', 'plant auxiliary board: BOP-R feeder 32 A + RCD, FCP circuit (locked), chargers, FCU-E/EF-E/AC-E, EH-950 SSR feeder, JT-902..905', 1, 'make',
    'Rittal AX 1058.000 600x800x250 + IEC 61439-3', '32 A', 'Rittal; ABB / Siemens / Hager', kg('AUX-DB'), STEP_ER)
row('DCJ-1', 'DC junction: SPD-DC2 Type 2 1000 V, gPV fuses 2P, isolator, W001 -> W002 split to 2 MPPT', 1, 'make', 'Rittal AX 400x500x200', '1000 V DC 50 A',
    'Mersen / SIBA fuses; DEHN / Phoenix / OBO / Citel SPD', kg('DCJ-1'), STEP_ER)
row('SPD-AC', 'AC surge protective devices: T1+2 at MDB grid incomer and BOP-R/RP-2, T2 at company DB', 3, 'buy', 'IEC 61643-11, TN-S 3+1', 'Iimp 12.5 kA/pole (T1)',
    'DEHN DEHNcombo / DEHNguard; Phoenix FLT-SEC; OBO; Citel', 1.0, STEP_ER)
row('SPD-DC', 'PV DC surge protective devices 1000 V: SPD-DC1 T1+2 (RP-2), SPD-DC2 T2 (DCJ-1)', 2, 'buy', 'EN 50539-11 / IEC 61643-31', 'Ucpv >= 1000 V',
    'DEHN DEHNcombo YPV; Phoenix VAL-MS DC-PV', 0.6, STEP_ER + ', ' + STEP_ROOF)
row('SPD-DATA', 'data / safety-loop SPDs at both ends of roof <-> ER copper cables (CAN, RS-422, W103 safety loop)', 12, 'buy', 'IEC 61643-21', '—',
    'DEHN BLITZDUCTOR XT; Phoenix TERMITRAB / PLUGTRAB', 0.1, '', '')
row('JT-901', 'meter HI-1 LOAD port (all loads), per-phase I/P/Q at 4 Hz', 1, 'buy', 'class 0.5S, Modbus RTU', '3~ CT 100/5 A', 'Janitza UMG 96-PA (DE)', 0.5, STEP_ER)
row('JT-920', 'grid incomer meter (zero-export supervision, later export)', 1, 'buy', 'class 0.5S, bidirectional, Modbus RTU', '3~ CT 100/5 A',
    'Janitza UMG 96-PA (DE); Carlo Gavazzi EM24 (CH/IT)', 0.5, STEP_ER)
row('JT-902..905', 'sub-meters AUX-DB (total), hall FCU+ERV, indoor HVAC aux, EH-950', 4, 'buy', 'class 1, Modbus RTU, DIN', '1~/3~', 'Carlo Gavazzi EM340 / EM111; ABB B23',
    0.3, STEP_ER)
row('JT-911..914', 'company load-group meters with split-core CTs (per phase)', 4, 'buy', 'class 1, Modbus RTU', '3~ CT 63/5 A', 'Carlo Gavazzi EM24-DIN + CTV split-core', 0.4, '',
    'in the company DB (hall)')
row('CT-ZE', 'zero-export CT / smart meter of the hybrid inverter at the grid incomer', 1, 'buy', 'per inverter make', '3~', 'inverter make (CHNT DTSU666 for Deye; '
    'KOSTAL Smart Energy Meter for Kostal)', 0.5, STEP_ER)
row('IPR-1', 'interface protection relay (NS protection) for grid export, v2', 1, 'buy', 'EN 50549-1 / VDE-AR-N 4105, 27/59/81, ROCOF', '3~',
    'Ziehl UFR1001E (DE); Bender GridGuard (DE)', 0.3, '', 'v2 only, if the DSO requires an external relay')
row('MON-GRID', 'grid presence / phase monitoring relay (XS-GRID)', 1, 'buy', '3~ U/f window relay', '400 V', 'Finder 70.31 (IT); Ziehl (DE)', 0.1, STEP_ER)
row('K-LS1..4', 'load-shedding contactors in the company DB', 4, 'buy', 'AC-3 + aux contact, 24 VDC coil', '25-40 A 4P', 'Siemens 3RT / ABB AF / Schneider TeSys', 0.5, '',
    'company DB (hall)')
row('K-SP1..3', 'start-permission contactors for the 3 wall split ACs (outdoor unit supply), with manual bypass switch', 3, 'buy', 'AC-3, 24 VDC coil, aux contact',
    '16 A 2P', 'Finder 22.32 / Siemens 5TT', 0.2, '', 'company DB (hall); 06 §7')
row('MET', 'main earth terminal bar ER', 1, 'buy', 'Cu bar on insulators', '500x50x10', 'DEHN / OBO', kg('MET'), STEP_ER)
# ------------------------------------------------------------------ control cabinets and boards
row('CP-E', 'ECU cabinet: B1, B5, HMI-B5 on door, chargers, DC-DC, switch, router, relays, 48 V MCBs, terminals', 1, 'make',
    'Rittal VX25 600x2000x500 IP55 + IEC 61439', '24/48 VDC', 'Rittal; Phoenix / Weidmüller / WAGO terminals; Finder relays', kg('CP-E'), STEP_ER)
row('RP-1', 'roof control cabinet: B2, B4, SR1 (Pilz PNOZmulti 2), DC-DC 48/24, fibre switch, data SPD, terminals', 1, 'make',
    'Rittal AX 600x800x400 (stainless 1.4301 variant) IP66, under the FR-E1 canopy', '24/48 VDC', 'Rittal; Pilz; Phoenix', kg('RP-1'), STEP_ROOF)
row('RP-2', 'roof PEB rectifier cabinet: B3 power stage on glycol cold plate, B3 controller, B3b, K-DC+/K-DC-/K-PRE, K-BR, CM choke, SPD-DC1',
    1, 'make', 'Rittal AX 800x1000x300 (stainless variant) IP66 + glycol cold plate', '30 kW, 1000 V DC', 'Rittal; Schaltbau; Semikron; Infineon', kg('RP-2'), STEP_ROOF)
row('B6-E-BOX', 'B6-E indoor HVAC controller enclosure with DIN rail, 24 V PSU, terminals', 1, 'make', 'Rittal AX 600x600x210', '24 VDC', 'Rittal; Phoenix', kg('B6-E-BOX'), STEP_ER)
row('SR1', 'configurable safety relay PL e: PNOZ m B0 base (772100) + 2x PNOZ m EF 16DI (772140) + PNOZ m EF 4DI4DOR (772143): SI01..SI24, O1..O8',
    1, 'buy', 'EN ISO 13849 PL e / IEC 62061 SIL CL 3', '24 V', 'Pilz PNOZmulti 2 (DE); Phoenix PSR-TRISAFE; Siemens 3SK2', 0.85, STEP_ROOF)
row('K-VS', 'enclosure-fan cut-off contactor for extinguishing (SR1 O7)', 1, 'buy', 'force-guided aux, 24 VDC', '48 VDC 20 A', 'Finder / Siemens 3RT DC', 0.3, STEP_ROOF)
for b, d in E.BOARDS.items():
    qty = sum(cfg.count(b) for cfg in E.B6_CONFIG.values()) if b.startswith('B6-') else 1
    if d['kicad'] is None:
        row(b, d['desc'], qty, 'buy', 'Toradex Mallow carrier board (Verdin), 24 V input via DIN DC-DC', '%d x %d mm' % (d['L'], d['W']), 'Toradex (CH)', 0.15,
            STEP_ER, 'v1 bought; custom KiCad carrier in a later revision')
        continue
    row(b, 'PCB assembly — ' + d['desc'], qty, 'make', 'FR-4 Tg170, ENIG, IPC-A-610 class 2, conformal coat IPC-CC-830 (roof boards); European parts (04)',
        '%d x %d mm' % (d['L'], d['W']), 'JLCPCB / Eurocircuits (BE) / Würth Elektronik (DE) PCB + assembly; consigned EU parts',
        round(d['L'] * d['W'] * 2.2e-6 + 0.05, 2), STEP_ER if d['holder'] in ('CP-E',) else STEP_ROOF,
        'component BOM: %s/out/*_bom.csv; KiCad project %s' % (d['kicad'], d['kicad']))
row('DIN-HSG-B6', 'B6 module DIN housings with T-bus connectors (90 / 67.5 / 45 mm)', sum(len(v) for v in E.B6_CONFIG.values()), 'buy',
    'Phoenix Contact ICS / ME-MAX housings + ME 22,5 TBUS', 'per module width', 'Phoenix Contact (DE)', 0.08, STEP_ROOF + ', ' + STEP_ER)
row('HMI-B5', '10.1" industrial touch display on CP-E door (B5 HMI)', 1, 'buy', 'IPS 1280x800 LVDS, PCAP, optical bonding, >= 500 nit', '10.1"',
    'DATA MODUL easyTOUCH eTD101W3201 (DE); Distec POS-PRO 10.1 (DE)', 0.93, STEP_ER, E.DISPLAYS['HMI-B5']['src'])
row('SOM-B5', 'NXP i.MX 8M Plus system-on-module for B5 (4 GB, 32 GB eMMC, industrial temp.)', 1, 'buy', 'Toradex Verdin iMX8M Plus Q 4GB IT', 'SODIMM-260',
    'Toradex (CH); Phytec phyCORE-i.MX 8M Plus (DE)', 0.02, STEP_ER)
row('NVME-B5', 'industrial NVMe SSD with power-loss protection', 1, 'buy', 'M.2 2280', '256 GB', 'Swissbit (CH)', 0.01, STEP_ER)
row('HMI-B6R', 'B6 touch HMI on BOP-R door: STM32 embedded display, TouchGFX firmware (ours)', 1, 'buy', 'STM32H757, IPS 1280x800, PCAP, optical bonding',
    '10.1"', 'Riverdi RVT101HVSNWC00-B (PL)', 0.52, STEP_ROOF, E.DISPLAYS['HMI-B6R']['src'])
row('NET-SW', 'managed industrial Ethernet switch with SFP (ER and RP-1)', 2, 'buy', 'VLAN, -40..+70 C', '4-5 ports + SFP',
    'Westermo Lynx L205-S1 (SE); Phoenix FL SWITCH 2105 (DE)', 0.7, STEP_ER + ', ' + STEP_ROOF)
row('RTR-1', 'router: fixed internet (static IP) WAN + LTE failover, WireGuard server, SMS modem', 1, 'buy', 'Teltonika RUTX11', 'LTE Cat 6', 'Teltonika (LT)', 0.5, STEP_ER)
row('VPS', 'VPS outside Iran: Telegram relay + data mirror + backup (service)', 1, 'buy', 'Linux VPS, 2 vCPU', 'yearly', 'Hetzner (DE); OVH (FR)', 0, '', 'service')
# ------------------------------------------------------------------ roof power
row('RB-1', 'braking resistors R_BR1 18-20 ohm (>= 400 kJ, 36 kW/10 s, 6 kW cont.) + R_BR2 8 ohm in one IP23 enclosure with rain hood, thermal switch TSH-860',
    1, 'make', 'stainless edge-wound / grid elements, 1000 V DC insulation; reference envelope Schneider VW3A7790 (3x6.7 ohm, 20 kW, IP23)', '1000 V DC',
    'Danotherm (DK); Frizlen (DE); Cressall (UK); Schneider VW3A7790 (FR) as R_BR1 basis', kg('RB-1'), STEP_ROOF, E.DIM['RB-1']['src'])
row('DCD-1', 'DC isolator 1000 V 50 A 2P lockable IP66 (roof, before W001)', 1, 'buy', 'IEC 60947-3 DC-PV2', '1000 V 50 A', 'ABB OTDC; Santon (NL)', kg('DCD-1'), STEP_ROOF)
row('K-DC', 'DC main contactors K-DC+ / K-DC- and pre-charge K-PRE', 3, 'buy', 'C195 A/24EV, 24 V DC coil, aux contact', '>= 1000 V DC 50 A',
    'Schaltbau C195 (DE)', 2.0, STEP_ROOF, 'datasheet 143x142x68 mm')
row('K-BR', 'PMG brake contactor with NC main contacts (independent brake B3b)', 1, 'buy', 'AC-1 NC', '400 V 63 A', 'Siemens 3RT / ABB / Schneider', 0.9, STEP_ROOF)
row('JB-E', 'junction box on EP-1 north face (sensor / valve wiring, M12 bulkheads)', 1, 'make', 'Rittal KX stainless 400x300x150 IP66', '—', 'Rittal; Phoenix; Lapp',
    kg('JB-E'), STEP_ROOF, 'package interface docs/06 §3')
row('MEB-R', 'roof main earth bar with test link for the earth-well conductor', 1, 'buy', 'Cu bar + disconnecting test link', '400x50x10', 'DEHN / OBO', kg('MEB-R'), STEP_ROOF)
row('FR-E1', 'support frame + 4 mm sun canopy for RP-1 / RP-2 / DCD-1 / MEB-R', 1, 'make', 'hot-dip galvanised steel S235, 60x60 posts, C-channel rails, bolted to '
    'concrete blocks (no roof penetration)', '1.7 x 0.5 x 2.05 m', 'local fabrication', 85.0, STEP_ROOF)
# ------------------------------------------------------------------ cable route
for r in E.ROUTE:
    import math
    L = sum(math.dist(p0, p1) for p0, p1 in zip(r['pts'][:-1], r['pts'][1:]))
    spec = {'tray': 'perforated cable tray HDG, with divider and lid on the roof', 'ladder': 'cable ladder HDG', 'cover': 'walk-over cable cover, '
            'aluminium, anti-slip', 'riser': 'roof penetration sleeve 300x300 with rain cap + fire-stop'}[r['kind']]
    row(r['id'], r['note'], round(L * 1.1, 1) if r['kind'] != 'riser' else 1, 'buy', spec, '%d x %d mm' % (r['w'] * 1000, r['h'] * 1000),
        'OBO Bettermann MKS 620/630 FS, ladder LG 60 NS FS 300 (DE); Niedax (DE)', round(L * {'tray': 4.0, 'ladder': 5.0, 'cover': 3.0, 'riser': 15.0}[r['kind']], 1),
        STEP_ROUTE, 'qty in m (+10 %)' if r['kind'] != 'riser' else '')
row('CND-C2', 'separate earthed steel conduit for c2 data cables along T-R1 (05 §1)', 25, 'buy', 'galvanised steel conduit EN 61386', '50 mm', 'OBO; Dietzel (AT)', 30.0, '',
    'qty in m')
# ------------------------------------------------------------------ cables (05 §6, +15 %)
CABLES = [
    ('W001', 'H1Z2Z2-K 1x16 (DC 720-780 V roof -> ER)', 80, 'EN 50618, 1.5 kV DC', '1x16 mm2'), ('W002/W009/W010', 'H1Z2Z2-K / silicone 1x6', 30, 'EN 50618', '1x6 mm2'),
    ('W003', 'HV battery cable kit (manufacturer)', 1, 'kit', '2x 1x35 mm2'), ('W004/W019/W020', 'N2XH-J 5G16 LSZH', 15, '0.6/1 kV', '5G16'),
    ('W018', 'NYY-J 5G16 grid incomer (per site)', 10, '0.6/1 kV', '5G16'), ('W005', 'N2XH-J / NYY-J 5G10 to company DB', 25, '0.6/1 kV', '5G10'),
    ('W006', 'NYY-J 5G10 UV-resistant AUX-DB -> BOP-R', 40, '0.6/1 kV', '5G10'), ('W007', 'H07RN-F 1x25 48 V roof feeder', 80, '450/750 V', '1x25'),
    ('W022', 'H07RN-F 1x35 48 V battery', 5, '450/750 V', '1x35'), ('W008', 'symmetric shielded VFD/servo cable, heat resistant (PMG)', 4, 'ÖLFLEX HEAT 180 EMC class', '3x16 + 3G2.5'),
    ('W011', 'silicone shielded 1x10 (PMG -> K-BR -> B3b)', 6, '1.8 kV', '1x10'), ('W012-W016', 'engine package power/control cables (BLDC, valves, igniter, fans)', 40,
                                                                                      'oil/UV resistant, shielded', '3G1.0..3x6'),
    ('W113', 'H07V-K green-yellow 1x25 (MEB-R -> MET)', 45, '450/750 V', '1x25'), ('W118', 'earth-well conductor Cu 1x50 + mechanical protection', 10, 'bare / H07V-K', '1x50'),
    ('W119', 'H07V-K green-yellow 1x16 roof bonding', 30, '450/750 V', '1x16'), ('W101', 'CAN cable 120 ohm 2x2x0.5 shielded', 100, 'UNITRONIC BUS CAN class', '2x2x0.5'),
    ('W102/W105/W106/W123', 'LiYCY-TP 2x2x0.5 / 4x2x0.5', 130, 'shielded twisted pair', '2x2x0.5, 4x2x0.5'), ('W103', 'LiYCY 12x1.0 safety loop', 40, 'shielded', '12x1.0'),
    ('W116', 'LiYCY 18x1.0 RP-1 <-> BOP-R', 15, 'shielded', '18x1.0'), ('W109/W124', 'LiYCY 25x0.75 + 12x0.75', 35, 'shielded', '25x0.75'),
    ('W104', 'fibre OM3 4-core armoured outdoor', 45, 'LC duplex', '4 x 50/125'), ('W112/W115', 'Cat6A S/FTP', 30, 'LSZH', 'Cat6A'),
    ('W120', 'fire-resistant cable PH120 2x1.5 shielded (FCP loops)', 250, 'EN 50200 PH120 / IEC 60331', '2x1.5'),
    ('W121', 'fire-resistant cable PH120 2x1.5 / 4x1.5 (release circuits, interface relays)', 150, 'EN 50200 PH120', '2x1.5, 4x1.5'),
    ('KX', 'thermocouple extension KX class 1 2x0.5, FEP in hot zone', 60, 'IEC 60584-3', '2x0.5'),
]
for tag, desc, q, spec, size in CABLES:
    row(tag, desc, q, 'buy', spec, size, 'Lapp (DE); Helukabel (DE); Prysmian (IT); Nexans (FR)', '', '', 'qty in m incl. 15 % (05 §6)' if tag not in ('W003',) else 'kit')
# ------------------------------------------------------------------ fire detection and release control (07)
row('FCP', 'fire detection + extinguishing control panel (2 extinguishing zones FZ1/FZ2 + detection zone FZ3), GSM/IP dialler', 1, 'buy',
    'EN 54-2/4 + EN 12094-1, addressable, 2 loops', '230 VAC + 2x 12 V battery', 'Siemens Sinteso XC10 (DE/CH, reference) or FC2020 + extinguishing module; '
    'Minimax FMZ 5000 (DE); Bosch FPA-1000 (DE); Hekatron Integral (DE)', kg('FCP'), STEP_ER, E.DIM['FCP']['src'])
# ------------------------------------------------------------------ field devices from the I/O list (one row per tag)
SUP = [
    (r'^TE-.*TC|TC type K', 'WIKA TC80 (DE); Rössel (DE); JUMO (DE); TC Direct (UK)'), (r'PT1000|RTD', 'WIKA (DE); JUMO (DE)'),
    (r'^(PT|PDT|PSL|PSH|PDSL)-', 'Keller (CH); WIKA (DE); Danfoss (DK); Huba (CH)'), (r'^SE-', 'Melexis US5881 (BE) / Micro-Epsilon DZ140 (DE)'),
    (r'^VE-', 'Hansford HS-100 (UK); IFM VSA (DE)'), (r'^BE-', 'Durag D-LX 100 UV (DE); Siemens QRA2 (DE)'), (r'^BS-', 'IR3 flame detector EN 54-10 (Siemens / Bosch / Hekatron)'),
    (r'^(TSH-87|TSH-884)', 'EN 54-5 heat detector (FCP make)'), (r'^SD-', 'EN 54-7 optical smoke detector (FCP make)'), (r'^AT-82', 'Dräger Polytron 5310 (DE); Crowcon Xgard IQ (UK)'),
    (r'^AT-885', 'Dräger Polytron 8000 H2 + CO (DE)'), (r'^(XV-61|XV-62|XV-021|FCV)', 'GSR (DE); Dungs (DE); Bürkert (DE)'), (r'^FT-6|^FQ-', 'Bürkert 8746 (DE); E+H t-mass (CH)'),
    (r'^ZS-81|^ESD|^HS-84', 'Schmersal (DE); Euchner (DE); Pilz (DE); Siemens 3SU1'), (r'^HS-89', 'EN 54-11 / EN 12094-3 manual stations (FCP make)'),
    (r'^XY-888|^PS-889|^PSL-890|^ZSC-899', 'per listed extinguishing system (docs/hvac/08 supplier)'), (r'^MT-', 'E+E EE33 (AT); Vaisala HMP7 (FI)'),
    (r'^M-0|^M-7|^M-8', 'maxon (CH); Dunkermotoren (DE); ebm-papst (DE)'), (r'^IGN', 'COFI / BRAHMA (IT)'), (r'^LT-|^LSL-', 'Baumer (CH); Gems-free: WIKA (DE)'),
    (r'^XA-', 'Werma (DE); Pfannenberg (DE)'), (r'^FT-75', 'IFM SM (DE); Bürkert (DE)'), (r'^ZC-|^ZT-|^ZSO-', 'Belimo (CH)'), (r'^FD-', 'pressure-operated damper (E5 package)'),
]
SKIP_BOARDS = ('B6-R', 'B6-E')
n_dev = 0
with open(os.path.join(ROOT, 'docs', 'electrical', '02_io_list.csv'), encoding='utf-8') as f:
    for r in csv.DictReader(f):
        tag, board, ch, sig = r['tag'], r['board'], r['channel'], r['signal']
        if board in SKIP_BOARDS or ch.startswith('internal') or ch.startswith('ETH') or 'Modbus' in sig or 'CAN' in sig and board == 'B1':
            continue
        if re.match(r'^(INV|BMS|UPS|JT|B3|XS-85|XS-87|K-LS|ZS-LS|ZS-ATS|XA-ATS|ZS-NPE|XS-GRID|XS-IPR|XS-SPD|EH-|ENG-RUN|K-EX|K-VS|K-SP|ZS-SP|VFD|SD-E|EMS|BOP|XA-BLD|TT-ER|TE-835)', tag):
            continue
        # equipment supplied with the package systems (E5: gas train, oil system, starter, enclosure fans, dampers) or by HVAC
        if re.match(r'^(XV-|FCV-|M-|IGN-|FD-|DC-1-FAN|ZC-101|ZT-101|ZSO-101|TSHH-111|PSH-111|FSL-111|XY-888|PS-889|PSL-890|ZSC-899)', tag):
            continue
        sup = next((s for pat, s in SUP if re.search(pat, tag) or re.search(pat, sig)), 'per 04 §7')
        m = re.search(r'(\d+)\.\.(\d+)', tag)
        qty = int(m.group(2)) - int(m.group(1)) + 1 if m else 1
        row(tag, r['description'], qty, 'buy', sig, r['range'], sup, '', 'in the EP-1 package model (E5)' if r['location'].startswith('بام: ناحیهٔ') else '',
            'field device per 02_io_list (%s %s); supplied by EL, installed by E5/HVAC; their BOMs must not duplicate' % (board, ch))
        n_dev += 1
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for r in ROWS:
        w.writerow(r)
print('wrote %s: %d rows (%d field devices from the I/O list); not in this BOM: valves, pumps, starter, igniter, enclosure fans and dampers '
      '(E5 package), HVAC devices and the extinguishing hardware (docs/hvac)' % (os.path.relpath(OUT, ROOT), len(ROWS), n_dev))
