# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - self-built generator BOM -> docs/bom/variant_e_generator_bom.csv (same schema as variant_e_bom.csv):
    tag,description,qty,make_or_buy,material_or_spec,size_or_rating,supplier_candidates,mass_kg,model_file,notes
Rows 1..n: every CAD part of cad_out/variant_e/GENERATOR/e_generator_parts.json (cad/variant_e/eg_generator.py; a copy is
kept in sim/variant_e/eg_cad_parts.json).  Further rows: raw materials / semi-finished items to order, winding materials,
cooling loop, sensors, electrical items, services, consumables and assembly tools.  No US suppliers or US-owned brands
(e.g. aramid / polyimide insulation from JP / CN / DE makers instead of the US trademarks).
Supersedes the generator rows E-G110..E-G180 and E-W100 (generator share) of docs/bom/variant_e_bom.csv.
Run:  python3 sim/variant_e/eg_bom.py
"""
import csv, json, os, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'cad_out', 'variant_e', 'GENERATOR', 'e_generator_parts.json')
COPY = os.path.join(HERE, 'eg_cad_parts.json')
if os.path.exists(SRC):
    shutil.copy(SRC, COPY)
S = json.load(open(COPY))
TH = json.load(open(os.path.join(HERE, 'eg_thermal.json')))
EMJ = json.load(open(os.path.join(HERE, 'eg_em.json')))

MAT = {'Al': 'EN AW-6082-T6', 'steel': 'steel (42CrMo4 QT / 34CrNiMo6 QT / S355 / 1.4034 per part)', 'stainless': '1.4301 / 1.4404 / A4', '17-4PH': '1.4542 (17-4PH) H1025',
       'bearing': 'hybrid: Si3N4 balls, 100Cr6 / Cronidur rings, P4', 'lam10': 'NO10 0.10 mm, backlack bonded', 'cu_slot': 'Cu Litz 1260 x 0.20 + insulation', 'litz_ew': 'Cu Litz + VPI resin',
       'CuCrZr': 'CuCr1Zr (CW106C)', 'SmCo': 'Sm2Co17 laminated', 'CFRP': 'T800S / high-Tg epoxy', 'GFRP': 'glass-epoxy EP GC 203 (IEC 60893)', 'PEEK': 'PEEK + CuZn39Pb3',
       'bronze': 'CuSn12', 'FKM': 'FKM 75', 'EPDM': 'EPDM 70 (peroxide)', 'filter': 'ePM1 80 % (F9)'}


def qty_of(name):
    m = re.search(r'_x(\d+)', name)
    return int(m.group(1)) if m else 1


rows = []
for name, p in S['parts'].items():
    tag = name.split('_')[0]
    bb = p['bbox']
    size = '%.0f x %.0f x %.0f mm (bbox)' % (bb[0][1] - bb[0][0], bb[1][1] - bb[1][0], bb[2][1] - bb[2][0])
    sup = p['note'] if ('(' in p['note'] and any(c in p['note'] for c in ('DE', 'JP', 'CN', 'SE', 'CH', 'IT'))) else ''
    rows.append(dict(tag=tag, description='%s: %s' % (name.split('_', 1)[1].replace('_', ' '), p['desc']), qty=qty_of(name), make_or_buy=p['make_buy'],
                     material_or_spec=MAT.get(p['material'], p['material']), size_or_rating=size,
                     supplier_candidates=sup or ('own 5-axis CNC (user)' if p['make_buy'].startswith('make') else ''), mass_kg=p['mass_kg'], model_file=p['step'],
                     notes=('%s; ' % p['note'] if p['note'] and not sup else '') + 'mass from %s' % p['mass_source']))

cu_len = 24 * 2 * EMJ['winding']['MLT_m'] * 1.12 + 6 * 1.0
X = [  # tag, description, qty, make/buy, spec, size, suppliers, mass, notes
    # ---------------- raw material / semi-finished to order (for the CAD 'make' parts)
    ('E-G300', 'raw material: 6082-T6 forged ring d340/280 x 480 (housing) + 2 forged discs d340 x 110 (end bells) + tube d300/250 x 350 (jacket) + bar d130 (caps, hood, box)', 1, 'buy',
     'EN AW-6082-T6 (EN 755 / EN 586 forgings)', '~160 kg stock', 'Hydro (NO), Constellium (FR), Otto Fuchs (DE), AMAG (AT)', 160.0, 'machined on the user 5-axis CNC; ~25 % yield'),
    ('E-G301', 'raw material: 42CrMo4 +QT bar d80 x 500 (shaft), 34CrNiMo6 +QT d60 x 280 (quill), 1.4404 d110 x 40 (end rings), 1.4542 d90 x 80 (cartridges)', 1, 'buy',
     'EN 10083-3, ultrasonic tested (EN 10228-3 class 3)', 'see description', 'Deutsche Edelstahlwerke (DE), Saarstahl (DE), Ugitech (FR), Ovako (SE)', 35.0, '3.1 certificates'),
    ('E-G302', 'raw material: CuCr1Zr (CW106C) tube / bar d80/68 x 310, solution annealed + aged', 1, 'buy', 'EN 12163 / 12167, 75 % IACS, Rp0.2 >= 270', 'd80 x 310', 'KME (DE), Wieland (DE), Aurubis (DE)', 3.5, ''),
    # ---------------- winding (rewind shop)
    ('E-G310', 'compacted rectangular Litz conductor 1260 x 0.20 mm (7 x 180 bunches), bare 7.30 x 7.65, insulated 7.70 x 8.05 (polyimide tape 2 x 25 um half-lap + glass serving)', round(cu_len), 'buy',
     'strands IEC 60317-0-2 grade 2, thermal class 200; Cu fill 0.71; DC R <= 0.443 mOhm/m at 20 C', 'm', 'Elektrisola (DE), Pack Feindraehte (DE), Rudolf Pack (DE), Furukawa Magnet Wire (JP)', round(cu_len * 0.39, 1),
     'length = 24 coils x 2 turns x MLT 1.104 m + 12 % + leads; polyimide film Kaneka Apical / Ube Upilex (JP)'),
    ('E-G311', 'slot liner + layer separator: aramid / polyimide / aramid (APA) laminate 0.31 mm (liners) and 0.50 mm (separators), class H 180', 2, 'buy', 'IEC 60626-3, class H',
     '2 m2', 'Krempel (DE) AKAFLEX APA with Yantai Tayho Metastar (CN) / Teijin (JP) aramid + Kaneka (JP) polyimide; Von Roll (CH)', 1.2, 'US trademark aramid / polyimide papers excluded on purpose'),
    ('E-G312', 'end-winding insulation: aramid paper 0.25 phase separators, glass-fibre tape (bands), polyester-free glass lacing cord, Litz lead sleeving (glass / silicone)', 1, 'buy',
     'class H', 'set', 'Krempel (DE), Von Roll (CH), Isovolta (AT)', 1.5, ''),
    ('E-G313', 'VPI resin class H (solvent-free epoxy / polyesterimide), 2 cycles + bake 160 C', 1, 'buy / service', 'IEC 60455, class H 180', '~20 kg in tank / 3 kg retained',
     'Elantas (DE) Elmotherm / Von Roll (CH) Damisol, at the rewind shop', 3.0, 'stator wound in the jacket after the shrink fit'),
    ('E-G314', 'lead cables 6 x 2 x 70 mm2 silicone (SiHF / Radox 180 C) 1 m + Cu tube lugs brazed to the coil ends, star bar Cu 30 x 5', 1, 'buy', 'EN 50525, 1.8 / 3 kV', '6 x 2 x 70 mm2 x 1 m',
     'Huber+Suhner (CH) Radox, Lapp (DE) Oelflex Heat, Klauke (DE) lugs', 9.0, ''),
    ('E-G315', 'winding PT100: 6 slot RTDs (flat 3 x 10 x 100, class A, 3-wire, between the layers at mid-stack, 2 per phase) + 4 end-winding RTDs (coil noses)', 10, 'buy',
     'IEC 60751 class A, 3-wire, PTFE / glass leads 1.5 m', '-50..200 C', 'Jumo (DE), WIKA (DE), Heraeus Nexensos (DE)', 0.2, '3 slot + 2 end-winding duty, rest spare'),
    # ---------------- magnets, sleeve services
    ('E-G320', 'magnetising + laminating of the 12 Sm2Co17 arc segments (136 x 2 mm slices each, insulating epoxy >= 1 kOhm, ground to arc 37.03 / 53.0 + taper allowance), marked magnetisation angle', 1, 'service (magnet maker)',
     'Br 1.10-1.13 T, HcJ >= 1990 kA/m, Hk/HcJ >= 0.70, (BH)max >= 230 kJ/m3, tol. arc +/-0.02, length +/-0.05', '12 segments', 'Shin-Etsu (JP), Ningbo Yunsheng (CN), Hangzhou Permanent Magnet Group (CN), VAC (DE)', 0.0,
     'order spec docs/variant_e/02_generator.md section 5'),
    ('E-G321', 'CFRP sleeve winding on a 1:500 tapered mandrel + post-cure + ID / OD grinding, rotor press-fit (rotor chilled -150 C, 320 kN press, stroke-controlled interference 0.57 +/-0.02)', 1, 'service',
     'T800S (or T700S) / epoxy Tg >= 190 C, Vf 0.60, 88 % hoop + 12 % +/-15 deg', 'ID 106 x 7 x 296', 'e+a Elektromaschinen (CH), BUCCI Composites (IT), CompoTech (CZ), Toray (JP) fibre', 0.0, 'eg_sleeve.json'),
    ('E-G322', 'hot spin test 120 % (42,000 rpm, rotor 100 C, vacuum pit, 2 min) + OD growth / balance check before / after', 1, 'service', 'IEC 60034-1 clause 9.7 / API 541-like', '42,000 rpm',
     'Schenck RoTec (DE) spin test centre, e+a (CH)', 0.0, 'acceptance: no permanent OD growth > 5 um, balance change < G1'),
    ('E-G323', 'balancing of the rotor assembly G1 (2 planes, soft-bearing machine), re-check after the spin test (acceptance G2.5)', 1, 'service', 'ISO 21940-11', 'U_G1 = 7.3 g mm',
     'Schenck (DE), CIMAT (PL), own machine', 0.0, 'eg_rotor.json'),
    ('E-G324', 'stator stack: OD cylindrical grinding after bonding (262.240 0/-0.025)', 1, 'service', 'Ra 0.8', 'd262 x 270', 'lamination maker or local grinding shop', 0.0, ''),
    # ---------------- generator glycol loop (dedicated, eg_thermal.json)
    ('E-G330', 'dry cooler for the generator loop: %s' % TH['dry_cooler']['spec'], 1, 'buy', 'design duty %d W at 47 C air, glycol 55 C supply' % TH['dry_cooler']['design_duty_W'],
     'UA >= 450 W/K', 'Guentner (DE), LU-VE (IT), Thermokey (IT), Kelvion (DE)', 45.0, 'replaces the generator share of E-W100'),
    ('E-G331', 'glycol pump ECM wet-rotor 30 L/min at 105 kPa, 0-10 V speed', 1, 'buy', 'PN10, 110 C', '%d W' % TH['pump']['P_el_W'], 'Grundfos (DK) MAGNA3 25-120 / Wilo (DE) Stratos MAXO', 9.0, ''),
    ('E-G332', '3-way mixing valve DN25 kvs 6.3 + modulating actuator 0-10 V (30 s)', 1, 'buy', 'PN10', 'DN25', 'ESBE (SE) VRG131 + ARA, Belimo (CH)', 3.0, 'L1 supply-temperature loop'),
    ('E-G333', 'expansion vessel 12 L + safety valve 3 bar + fill / drain + automatic air vent + Y-strainer 0.5 mm + 2 kW immersion heater (cold start / anti-condensation)', 1, 'buy', 'PN6', '12 L',
     'Reflex (DE), Flamco (NL), Afriso (DE)', 12.0, ''),
    ('E-G334', 'glycol vortex flow meter + flow switch, 4-20 mA', 1, 'buy', '5-60 L/min', 'DN20', 'Huba Control (CH) 210, SIKA (DE) VVX', 0.6, 'FT-G01'),
    ('E-G335', 'glycol piping DN25 stainless 1.4404 press-fit (2 x 10 m) + insulated hoses to the pod (2 x 1.5 m, EPDM), isolating ball valves', 1, 'buy', 'PN10', '2 x 10 m',
     'Geberit Mapress (CH), Viega (DE)', 25.0, ''),
    ('E-G336', 'MEG 35 % vol inhibited (first fill ~30 L)', 30, 'buy', 'Antifrogen N / Glysantin G48', 'L', 'Clariant (CH/DE), BASF (DE)', 31.0, ''),
    ('E-G337', 'glycol PT100 sensors (pod in / out, supply after the valve, return) in thermowells', 4, 'buy', 'IEC 60751 class A, 4-wire', 'G1/2 thermowell', 'Jumo (DE), WIKA (DE)', 0.6, 'TT-G01..04'),
    ('E-G338', 'leak detection: expansion-tank level switch + float switch on the pod leak-off drains', 2, 'buy', '24 V dc', '-', 'Jola (DE), Kobold (DE)', 0.4, 'LS-G01 / LS-G02'),
    # ---------------- cooling air
    ('E-G340', 'cooling-air dp transmitter (filter + generator) 0-5 kPa + filter dp switch', 2, 'buy', '4-20 mA', '0-5 kPa', 'Huba Control (CH) 699, Kalinsky (DE)', 0.4, 'PDT-A01'),
    ('E-G341', 'cooling-air PT100 (blower outlet, generator air outlet)', 2, 'buy', 'class A', 'M10 probe', 'Jumo (DE)', 0.2, ''),
    # ---------------- electrical (generator side of the converter)
    ('E-G350', 'contactor K1 (generator -> diode bridge) 500 A AC-1 / 690 V and K2 (generator -> start inverter) 150 A, mechanically interlocked', 1, 'buy', 'IEC 60947-4-1', '500 A + 150 A',
     'ABB (CH/SE) AF-series, Siemens (DE) 3RT', 12.0, 'K2 opens before K1 closes at 55 % speed'),
    ('E-G351', 'sine filter for the start inverter (<= 500 Hz output, 150 A, f_sw 4-8 kHz): protects the Litz winding from PWM edges and keeps the start rotor losses low', 1, 'buy',
     'dU/dt < 500 V/us, THD_u < 5 %', '150 A, 690 V', 'Schaffner (CH) FN5040HV, Block (DE), Mdexx (DE)', 45.0, 'only in the start path'),
    ('E-G352', 'insulation monitoring device on the IT DC link (generator + bridge + AFE)', 1, 'buy', 'IEC 61557-8', '0-1000 V dc', 'Bender (DE) iso685', 0.5, 'alarm 100 kOhm / trip 30 kOhm'),
    ('E-G353', 'cable glands M40 EMC (3) + M25 signal (2) + EMC screen clamps', 5, 'buy', 'IP68', 'M40 / M25', 'Pflitsch (DE) blueglobe, Lapp (DE) Skintop', 0.6, 'power cables: E-G190 of variant_e_bom.csv'),
    ('E-G354', 'signal cabling: 22 x PT100 / IR / speed / vibration cores, screened, to the ECU / PLC', 1, 'buy', 'LiYCY', '~25 m', 'Lapp (DE), Helukabel (DE)', 4.0, ''),
    # ---------------- consumables
    ('E-G360', 'adhesives / locking: Loctite AA 326 + 7649 (magnets), 648 (end rings), 243 (screws), MoS2 paste (pull bolt), PTFE dry film (sleeve press), silicone grease (EPDM O-rings)', 1, 'buy',
     '-', 'set', 'Henkel (DE), Klueber Lubrication (DE), OKS (DE)', 1.0, ''),
    ('E-G361', 'oil-jet nozzles d1.2 (2) + oil hoses DN8 / DN12 to the lube unit (feed 2 x, drain 2 x)', 1, 'make / buy', '1.4404, ISO 6149-3', 'set', 'own CNC; hoses Hydac (DE)', 1.5,
     'generator jets 2.5 L/min each at 2.5 barg from E-L100'),
    # ---------------- assembly tools (make)
    ('E-G370', 'tool: stator shrink oven / heater ring 180 C for the jacket + lifting mandrel for the stator stack', 1, 'make / buy', '-', 'd300', 'local', 0.0, ''),
    ('E-G371', 'tool: rotor insertion guide (PTFE film 0.5 mm in the gap + guide plates on both spigots with bronze bushes on the journals) - magnetic pull 0.13 N/um', 1, 'make', 'Al + PTFE', '-', 'own CNC', 0.0, ''),
    ('E-G372', 'tool: LN2-vapour chill box for the rotor (-150 C) + 100 t servo press with stroke / force recording + split push ring for the sleeve', 1, 'service / make', '-', '-', 'sleeve supplier or local press shop', 0.0, ''),
    ('E-G373', 'tool: AF10 x 300 hex bit + torque wrench 20-200 N.m (pull bolt through the hollow quill), M14 jacking screw, KMD hook spanner, bearing induction heater 80 C', 1, 'buy',
     '-', '-', 'Hazet (DE), Gedore (DE), SKF (SE) TIH', 0.0, ''),
    ('E-G374', 'tool: pod slide-out rails + 2 t chain hoist / jib in the plenum, alignment dial-indicator bracket on the quill socket', 1, 'make', 'S355', '-', 'own', 0.0, ''),
]
for t, d, q, mb, spec, size, sup, m, n in X:
    rows.append(dict(tag=t, description=d, qty=q, make_or_buy=mb, material_or_spec=spec, size_or_rating=size, supplier_candidates=sup, mass_kg=m, model_file='', notes=n))

out = os.path.join(ROOT, 'docs', 'bom', 'variant_e_generator_bom.csv')
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=['tag', 'description', 'qty', 'make_or_buy', 'material_or_spec', 'size_or_rating', 'supplier_candidates', 'mass_kg', 'model_file', 'notes'])
    w.writeheader()
    for r in rows:
        w.writerow(r)
US = ['DuPont', 'Nomex', 'Kapton', 'Parker', 'Swagelok', 'Garrett', 'Calnetix', 'Arnold', 'Honeywell', 'Woodward', 'Huntsman', 'Araldite', '3M', 'Grainger', 'Seeger', 'Emhart', 'PCB Piezo', 'Kaydon', 'Timken']
txt = open(out).read()
bad = [u for u in US if u in txt]
cad = sum(1 for r in rows if r['model_file'])
print('rows %d (CAD %d, other %d); CAD mass %.1f kg; US names found: %s' % (len(rows), cad, len(rows) - cad, sum(float(r['mass_kg']) for r in rows if r['model_file']), bad))
print('->', os.path.relpath(out, ROOT), '+ sim/variant_e/eg_cad_parts.json')
