# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - bill of materials -> docs/bom/variant_e_bom.csv (schema of docs/06_master_design.md section 5):
    tag,description,qty,make_or_buy,material_or_spec,size_or_rating,supplier_candidates,mass_kg,model_file,notes
Rows 1..57: every CAD part (sim/variant_e/e_cad_summary.json, written by cad/variant_e/e_check.py).  Further rows: parts
that are not modelled (fasteners, seals, oil / glycol / gas systems, drive cabinet, sensors, controls, consumables).
No US suppliers (excluded on purpose: Napier (Wabtec), Garrett, BorgWarner, Cummins/Holset, Calnetix, Arnold Magnetics,
Haynes, Special Metals, Honeywell / Elster / Kromschroder, Maxitrol, SWEP (Dover), Unifrax, Kaydon, Woodward, Altronic).
Run:  python3 sim/variant_e/e_bom.py
"""
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
S = json.load(open(os.path.join(HERE, 'e_cad_summary.json')))

SUP = {   # supplier candidates per CAD tag prefix (make parts: shop type)
    'E-R100': 'Accelleron (CH) TPS52/57-F spare wheel; MAN ES / PBS Turbo (DE/CZ) TCR16/18; MHI-MME (JP) MET18-22; Chinese TC makers (milled 2618 wheels)',
    'E-T101': 'Accelleron (CH) TPS57/61-F; MAN ES / PBST (DE/CZ) TCR18/20; MHI (JP); IHI (JP); Changzhou E&E Turbo-Power (CN, cast K418 + friction welding)',
    'E-R110a': 'Schaeffler FAG (DE), SKF (SE), GMN (DE), NSK (JP), ZWZ / LYC (CN)', 'E-R110b': 'same as E-R110a', 'E-R111': 'same as E-R110a',
    'E-G140': 'same as E-R110a', 'E-G141': 'same as E-R110a',
    'E-B122': 'Lesjofors (SE), Scherdel (DE)', 'E-K150': 'NGK (JP) industrial plug + MOTORTECH (DE) coil', 'E-K160': 'DURAG (DE), Siemens (DE)',
    'E-G120': 'Surahammars Bruk (SE), Kienle+Spiess (DE), Euro Group (IT), Baosteel (CN)',
    'E-G131': 'magnets VAC (DE) / Shin-Etsu (JP) / Ningbo Ketian (CN); sleeve: e+a (CH) or a CFRP winding shop; Toray T700 fibre (JP)',
    'E-G135': 'SKF (SE) / FAG (DE) KM7 locknut', 'E-F130': 'Trelleborg (SE), Vibracoustic (DE), Getzner (AT)',
    'E-G121': 'winding shop (local) or e+a (CH) active-parts kit'}
SHOP = {'ROTOR': 'precision CNC turning + grinding shop (user), heat treat + nitriding (local)', 'COMPRESSOR': 'CNC turning + 4-axis milling shop; forgings: local or Otto Fuchs (DE)',
        'BEARING': 'precision CNC turning + internal grinding', 'TURBINE': 'CNC shop; alloy plate / forgings VDM Metals (DE), Aubert & Duval (FR); sheet fabrication + TIG (local)',
        'COMBUSTOR': 'pipe / flange fabrication (PED), sheet laser + rolling + TIG; alloy sheet VDM Metals (DE)', 'EXHAUST': 'sheet fabrication (1.4828), local',
        'GENERATOR': 'CNC turning shop; Al bar / tube local', 'INTAKE': 'sheet-metal shop (laser, brake, MAG)', 'FRAME': 'steel fabrication shop, hot-dip galvanising'}
MAT = {'Al': 'EN AW-6082-T6 (wheel: 2618-T61)', 'steel': 'steel (42CrMo4 QT / P265GH / S355 per part)', '17-4PH': '1.4542 (17-4PH) H1025', 'IN625': '2.4856',
       'alloyX': '2.4665 (alloy X)', 'N75': '2.4951 (alloy 75)', 'IN713LC': 'IN713LC / K418 cast', '1.4828': '1.4828 (309-type heat resistant)', 'stainless': '1.4301 / 1.4404',
       'bearing': 'hybrid: Si3N4 balls, 100Cr6 / Cronidur rings, P4', 'lam': '0.20 mm NO20 electrical steel', 'winding': 'Cu Litz, class H', 'SmCo+CF': 'Sm2Co17 + carbon/epoxy', 'rubber': 'NR / steel'}


def qty_of(name):
    m = re.search(r'_x(\d+)', name)
    return int(m.group(1)) if m else 1


def size_of(bb):
    return '%.0f x %.0f x %.0f mm (bbox)' % (bb[0][1] - bb[0][0], bb[1][1] - bb[1][0], bb[2][1] - bb[2][0])


rows = []
for key, p in S['parts'].items():
    sub, name = key.split('/')
    tag = name.split('_')[0]
    buy = p['make_buy'].startswith('buy')
    rows.append(dict(tag=tag, description='%s: %s' % (name.split('_', 1)[1].replace('_', ' '), p['desc']), qty=qty_of(name),
                     make_or_buy=p['make_buy'], material_or_spec=MAT.get(p['material'], p['material']), size_or_rating=size_of(p['bbox']),
                     supplier_candidates=SUP.get(tag, SUP.get(tag[:6], '' if buy else SHOP.get(sub, ''))), mass_kg=p['mass_kg'], model_file=p['step'],
                     notes=('%s; ' % p['note'] if p['note'] else '') + 'subsystem %s, mass from %s' % (sub, p['mass_source'])))

X = [  # not modelled: tag, description, qty, make/buy, spec, size, suppliers, mass, notes
    ('E-R105', 'piston rings for the turbine-end seal runner d50 (3 grooves)', 3, 'buy', 'TC piston ring, spheroidal cast iron / Ni-resist', 'd50.8 x 2', 'TC maker spare (Accelleron / MAN-PBST), Chinese TC aftermarket', 0.01, 'seal bore E-B110 x 222..235'),
    ('E-R106', 'balancing: rotor G1 (core) / G1 (generator) as assemblies, high-speed balance of the core stack', 1, 'service', 'ISO 21940-11 G1', '35,000 rpm', 'Schenck (DE) service / own balancing machine', 0.0, 'mark angles; re-balance after any wheel change'),
    ('E-R107', 'friction / EB weld of the turbine wheel to E-R101 + journals ground to the wheel', 1, 'service', 'turbo practice', '-', 'wheel supplier (Changzhou E&E CN / TC maker)', 0.0, 'spin test 120 % (42,000 rpm) after welding'),
    ('E-B130', 'O-rings for the 4 SFD cartridges', 8, 'buy', 'FKM 75 ShA', '84 x 3 (ID 78)', 'Freudenberg (DE), Trelleborg (SE), ERIKS (NL)', 0.01, 'stiffness ~3 N/um per cartridge - measure on a rig'),
    ('E-B131', 'oil-jet nozzles (core 3, generator 2) + gallery plugs', 5, 'make', '1.4404, d1.2 jets', 'M8x1', 'precision CNC', 0.01, '2.5 barg, ~2.5 L/min per bearing'),
    ('E-B132', 'anti-rotation pins for the cartridges', 4, 'buy', 'ISO 8734 hardened dowel', 'd4 x 12', 'Bossard (CH), Wurth (DE)', 0.0, ''),
    ('E-B133', 'load washer behind the front cartridge (thrust measurement, rig + field)', 1, 'buy', 'piezo / strain-gauge ring', 'ID 70 OD 84, 5 kN', 'Kistler (CH), HBK (DE)', 0.05, 'net thrust must stay forward at all points'),
    ('E-H100', 'flange bolts: inlet cover / plenum (16 x M12), outer casing / cool casing (16 x M20 A193 B16 + nuts), BH / back plate (12 x M12), BH / heat shield (12 x M10 A286)', 1, 'buy',
     'ISO 4762 / 4014 12.9, A193 B16, A286 hot', 'set', 'Bossard (CH), Wurth (DE), Bohlhoff (DE)', 8.0, 'torques in the assembly procedure (docs/variant_e/00 section 7)'),
    ('E-H101', 'gaskets: cool-casing flange (spiral wound), DN300 PN10 x 2 (spiral wound), DN450 PN6 exhaust (graphite / mica), cone/elbow flange', 5, 'buy', 'EN 1514-2 spiral wound 1.4541/graphite', 'DN300, DN450, d800', 'Klinger (AT), Frenzelit (DE)', 3.0, ''),
    ('E-H102', 'piston-ring seals hot side: transition / plenum (d274), shroud / cool-casing rear wall (d282), cone collar (d282)', 3, 'buy / make', '2.4665 split ring', 'd274-282 x 3', 'local CNC', 0.2, 'allow 2-4 mm thermal growth'),
    ('E-H103', 'thermal insulation: hot plenum / cool casing inside (ceramic paper), exhaust cone + elbow outside (100 mm blanket + 1.4301 cladding)', 1, 'buy', 'AES / PCW blanket 128 kg/m3', '~8 m2', 'Morgan Thermal Ceramics (UK), Promat (BE), RATH (AT)', 45.0, 'touch temperature < 60 C'),
    ('E-L100', 'lube-oil unit: 80 L tank, pressure + scavenge gear-pump set 30 L/min (motor 0.75 kW), duplex 10 um filter, relief / pressure-control valve, heater 1 kW', 1, 'buy', 'ISO VG 32 synthetic turbine oil', '30 L/min, 2.5 barg', 'Rickmeier / KRACHT (DE) pumps, HYDAC / Argo-Hytos (DE) filters', 85.0, 'feed/drain lines through the top / bottom deswirl vanes; breather to a mist separator'),
    ('E-L101', 'rundown oil accumulator / gravity tank for coast-down after a black-out (35k -> 0 in ~3-5 min)', 1, 'buy', 'bladder accumulator 10 L + check valve', '10 L, 4 bar', 'HYDAC (DE), Bosch Rexroth (DE)', 15.0, 'mandatory for rolling bearings at 35k without grid'),
    ('E-L102', 'oil / glycol plate heat exchanger (~8 kW) + thermostatic valve', 1, 'buy', 'brazed plate 1.4401', '8 kW', 'Alfa Laval (SE), Kelvion (DE), Funke (DE)', 6.0, ''),
    ('E-L103', 'oil-mist separator on the bearing-chamber vent', 1, 'buy', 'coalescer', '100 L/min air', 'Hengst (DE), UT99 (CH)', 4.0, ''),
    ('E-L104', 'synthetic turbine oil first fill', 90, 'buy', 'ISO VG 32 (Shell Turbo T32 / Castrol Perfecto T32 / TotalEnergies Preslia GT)', 'L', 'Shell (NL/UK), Castrol (UK), TotalEnergies (FR)', 78.0, 'change by analysis, ~8000 h'),
    ('E-W100', 'glycol loop: pump (0.4 kW), 3-way valve, expansion vessel, dry cooler ~35 kW (PMG 4 + converter 10 + oil 8 kW + margin) with EC fans', 1, 'buy', 'MEG 35 %', '30-60 L/min, inlet <= 45 C', 'Grundfos (DK) / Wilo (DE); Guntner (DE), LU-VE (IT), Thermokey (IT)', 180.0, 'fans ~1.1 kW in the aux budget'),
    ('E-G190', 'power cables PMG -> drive cabinet (3 x 2 x 120 mm2, EMC screened, 1 kV) + glands', 1, 'buy', 'NSGAFOU / EMC', '~15 m', 'Nexans (FR), Lapp (DE), Prysmian (IT)', 60.0, ''),
    ('E-D100', 'drive cabinet: 6-pulse diode bridge (or 12-pulse) 500 A, DC link, 400 V-class IGBT active front end supply unit + LCL filter (~350 kVA), DC fuses, main breaker', 1, 'buy',
     '400 V 50 Hz grid side, DC 620-850 V', '315 kW continuous, eta 0.97', 'ABB ACS880-207 (FI/CH), Danfoss VACON NXA (DK/FI), Siemens SINAMICS S120 ALM (DE), Ingeteam (ES), Inovance (CN); diodes Semikron Danfoss / Infineon (DE)', 450.0,
     'no frequency changer >= 600 Hz (dual-use 3A225); grid code / protection relay per the utility'),
    ('E-D101', 'start inverter module on the DC bus (<= 500 Hz, ~45-75 kW) + contactor to the PMG terminals', 1, 'buy', 'standard inverter unit', '45-75 kW, f_out <= 320 Hz', 'ABB ACS880-104, Danfoss VACON NXI, Siemens S120 Motor Module', 60.0, 'motors to ~55 % speed, light-off ~22 %, opens before the diode bridge conducts (~79 %)'),
    ('E-D102', 'braking chopper + resistor (load rejection, ~350 kW for 3 s)', 1, 'buy', 'IGBT chopper + air resistor', '350 kW / 3 s', 'Danotherm (DK), Cressall (UK), ABB / Danfoss option', 90.0, 'clamps the DC bus at ~860 V, fuel cut within 0.1 s'),
    ('E-D103', 'black-start battery on the DC bus (optional)', 1, 'buy', 'LFP 50 kWh, 650-800 V', '50 kWh', 'BYD (CN), CATL (CN), Northvolt (SE)', 450.0, 'only if the site must start without the grid'),
    ('E-C100', 'engine control unit (own board, KiCad) + safety PLC: speed / TIT / overspeed / flame / gas / oil / vibration trips, sequencer, power control', 1, 'make + buy',
     'own STM32-class ECU + SIL2 safety relay / PLC', '-', 'own design; PLC: Siemens S7-1500F (DE), B&R (AT), Pilz (DE)', 15.0, 'overspeed trip 37,800 rpm (108 %) independent of the ECU'),
    ('E-S100', 'speed pickups (2 core on the nut wheel / 2 generator on the speed wheel)', 4, 'buy', 'eddy-current / Hall, 1-4 kHz', 'M12 x 1', 'Jaquet (CH), Braun (DE)', 0.4, ''),
    ('E-S101', 'EGT thermocouples in the diffuser inlet (TIT calculated from EGT + P3)', 6, 'buy', 'type K mineral-insulated d3, 2.4816 sheath', '0-1000 C', 'JUMO (DE), Endress+Hauser (CH), Thermo-Electra (NL)', 0.6, ''),
    ('E-S102', 'pressure transmitters: P1 (plenum), P2, P3, P4 (nozzle), p6, filter dp, gas, oil', 8, 'buy', '4-20 mA, 0.25 %', 'various', 'WIKA (DE), Keller (CH), Danfoss (DK)', 2.0, ''),
    ('E-S103', 'vibration: 2 accelerometers on the bearing housing, 2 on the pod; bearing RTDs PT100 x 5', 9, 'buy', 'IEPE 100 mV/g; PT100 class A', '-', 'Hansford (UK), Bruel & Kjaer Vibro (DE/DK), IFM (DE)', 1.0, 'trend for the bearing exchange plan'),
    ('E-S104', 'gas flow meter (thermal mass or Coriolis), gas temperature', 1, 'buy', 'DN25-40', '0-300 m3/h', 'Endress+Hauser (CH), KROHNE (DE)', 6.0, 'heat-rate monitoring'),
    ('E-F100', 'gas train: ball valve, filter 50 um, 2 safety shut-off valves (class A), pressure regulator, metering valve (actuated), pressure switches, vent valve, flame arrestor', 1, 'buy',
     'EN 161 / EN 88-1 / EN 746-2', 'DN40, 200-240 m3/h, 3.5-5 barg in', 'Dungs (DE), Pietro Fiorentini (IT), Madas (IT), Siemens (DE) VGD + SKP actuators', 45.0, 'leak test 1.5 x; gas need 3.73 barg at the skid'),
    ('E-F101', 'gas booster (on demand when the supply < 3.8 barg), oil-free, with bypass', 1, 'buy', 'oil-free piston / scroll gas compressor, ATEX', '~240 m3/h, +0.5..1 bar, ~1-3 kW', 'Haug Kompressoren (CH), Mehrer (DE), Bauer (DE)', 120.0, 'runs ~never at 4 barg nominal supply'),
    ('E-I130', 'filter cells: 9 x G4 panel 592 x 592 x 48 + 9 x F7 (ISO ePM1 55 %) V-cell 592 x 592 x 292', 18, 'buy', 'EN ISO 16890', '3400 m3/h rated each (used at 31 %)', 'Camfil (SE), Freudenberg Viledon (DE), MANN+HUMMEL (DE)', 90.0, 'change F7 at ~120 Pa (our flow); filter house + weather hood = plant scope'),
    ('E-I131', 'plenum access door with seal + latch, intake silencer splitters (optional)', 1, 'make', '1.4301', '600 x 1000', 'sheet-metal shop', 25.0, 'pod removal path'),
    ('E-P100', 'acoustic / weather enclosure with ventilation fan (~1 kW) and fire detection', 1, 'make / buy', 'galvanised steel + mineral wool', '~5 x 2.6 x 3 m', 'local package builder', 1500.0, 'NEXT STEP - not designed in this round'),
    ('E-P101', 'exhaust CHP heat exchanger / absorption-chiller generator (DN450 inlet), stack', 1, 'buy', '~1.4 MW at 525 C -> 90 C', '3.0 kg/s', 'plant scope (docs/hvac)', 0.0, 'back pressure <= 1.2 kPa (cycle basis)'),
]
for r in X:
    rows.append(dict(tag=r[0], description=r[1], qty=r[2], make_or_buy=r[3], material_or_spec=r[4], size_or_rating=r[5], supplier_candidates=r[6], mass_kg=r[7], model_file='', notes=r[8]))

out = os.path.join(ROOT, 'docs', 'bom', 'variant_e_bom.csv')
cols = ['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes']
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
cad_m = sum(r['mass_kg'] for r in rows[:len(S['parts'])])
ext_m = sum(r['mass_kg'] * (1 if r['tag'] not in ('E-L104',) else 1) for r in rows[len(S['parts']):] if r['tag'] not in ('E-P100', 'E-D103'))
print('BOM rows %d (CAD %d + other %d); CAD mass %.0f kg, non-CAD %.0f kg (without enclosure / battery) -> %s' % (
    len(rows), len(S['parts']), len(rows) - len(S['parts']), cad_m, ext_m, os.path.relpath(out, ROOT)))
json.dump(dict(rows=len(rows), cad_rows=len(S['parts']), cad_mass_kg=round(cad_m), non_cad_mass_kg_excl_enclosure_battery=round(ext_m),
               make=sum(1 for r in rows if str(r['make_or_buy']).startswith('make')), buy=sum(1 for r in rows if str(r['make_or_buy']).startswith('buy')),
               service=sum(1 for r in rows if str(r['make_or_buy']).startswith('service'))), open(os.path.join(HERE, 'e_bom.json'), 'w'), indent=1)
