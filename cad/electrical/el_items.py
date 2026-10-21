"""GR180-CCHP electrical package (EL): single source of truth for the 3D envelope models and the BOM.

Pure Python (no FreeCAD import) so that both the FreeCAD scripts (cad/electrical/*.py) and the BOM writer (el_bom.py)
use the same data. Coordinates: ROOF frame of docs/06_master_design.md §1 (m; x east, y north, z up, origin SW roof corner
on the finished roof surface). Every placement is an axis-aligned envelope: (x0, y0, z0) = min corner, (w, d, h) = size along
x, y, z in m.

Purchased items are envelopes with outer dimensions from the manufacturer datasheet (`src` says which; 'estimate' = not yet
confirmed). Change dimensions only here, then re-run cad/electrical/build_all.py and el_bom.py.
"""

# ------------------------------------------------------------------ electrical room (ER) location — ASSUMPTION (05 §0)
# Ground floor level with the hall (hall floor z = -2.8, roof slab underside -0.3), 3.5 x 3.0 m, clear height 2.5 m,
# west of the plant roof so that the roof -> ER cable route is ~30 m (user: "the electrical room is ~30 m from the roof").
ER = dict(x0=-20.5, y0=7.0, z0=-2.8, w=3.5, d=3.0, h=2.5, wall=0.2, door=(-19.0, -18.1))
HALL_DB = dict(x0=0.15, y0=8.6, z0=-2.8 + 0.9, w=0.6, d=0.2, h=0.8)   # company DB on the hall west wall (assumed)

# ------------------------------------------------------------------ envelope dimensions of purchased equipment (m)
# (w, d, h) as installed: w along the wall, d = depth from the wall, h = height. src: datasheet | distributor | estimate
DIM = {
    'HI-1': dict(w=0.527, d=0.294, h=0.894, kg=80.0, src='datasheet: Deye SUN-30K-SG01HP3-EU-BM3 527x894x294 mm, 80 kg (09/2026)'),
    'BAT-1': dict(w=0.530, d=0.602, h=1.629, kg=240.0, src='datasheet: Deye BOS-G20 = 4x BOS-GM5.1 + HVB750V/100A-EU in 3U-LRACK, 530x1629x602 mm, 240 kg'),
    'BAT-2': dict(w=0.600, d=0.500, h=0.500, kg=55.0, src='box with 1x Pylontech US5000 (datasheet 442x162x420 mm, 40 kg) + Class-T fuse'),
    'CHG-48': dict(w=0.249, d=0.116, h=0.180, kg=2.7, src='datasheet: Victron Smart IP43 Charger 48/13 (249x180x116 mm)'),
    'CP-E': dict(w=0.600, d=0.500, h=2.000, kg=180.0, src='Rittal VX25 600x2000x500 (VX 8605.000), equipped'),
    'MDB': dict(w=1.000, d=0.300, h=1.200, kg=110.0, src='datasheet: Rittal AX 1213.000 1000x1200x300 (71.5 kg empty), equipped'),
    'AUX-DB': dict(w=0.600, d=0.250, h=0.800, kg=50.0, src='datasheet: Rittal AX 1058.000 600x800x250 (30 kg empty), equipped'),
    'B6-E-BOX': dict(w=0.600, d=0.210, h=0.600, kg=25.0, src='Rittal AX 600x600x210, equipped (part no. to confirm)'),
    'DCJ-1': dict(w=0.400, d=0.200, h=0.500, kg=9.0, src='Rittal AX 400x500x200, equipped (part no. to confirm)'),
    'MET': dict(w=0.500, d=0.060, h=0.080, kg=3.0, src='Cu bar 500x50x10 on insulators (DEHN / OBO)'),
    'FCP': dict(w=0.505, d=0.125, h=0.375, kg=6.5, src='datasheet: Siemens Sinteso XC10 extinguishing control panel 505x375x125 mm'),
    'MCP': dict(w=0.090, d=0.060, h=0.090, kg=0.3, src='EN 54-11 call point'),
    'RP-1': dict(w=0.600, d=0.400, h=0.800, kg=65.0, src='Rittal AX 600x800x400 (AX 1059.000 size; stainless 1.4301 variant to confirm), equipped'),
    'RP-2': dict(w=0.800, d=0.300, h=1.000, kg=120.0, src='Rittal AX 800x1000x300 (AX 1180.000 size; stainless variant + cold plate), equipped (PEB)'),
    'RB-1': dict(w=1.060, d=0.540, h=0.800, kg=95.0, src='make: R_BR1 + R_BR2 resistor banks in one IP23 enclosure; footprint from Schneider VW3A7790 '
                                                          '(1060x565x540, 3x6.7 ohm 20 kW IP23) + R_BR2 tier — confirm with Danotherm / Frizlen'),
    'DCD-1': dict(w=0.300, d=0.200, h=0.400, kg=4.0, src='IP66 DC isolator 1000 V 50 A in enclosure (ABB OTDC class)'),
    'JB-E': dict(w=0.400, d=0.150, h=0.300, kg=8.0, src='Rittal KX stainless 400x300x150 junction box'),
    'MEB-R': dict(w=0.400, d=0.060, h=0.080, kg=2.5, src='Cu bar 400x50x10 + test link'),
}

# ------------------------------------------------------------------ placements (ROOF frame, m)
erx, ery, erz = ER['x0'], ER['y0'], ER['z0']
ER_N = ery + ER['d']          # north wall inner face y = 10.0
ER_E = erx + ER['w']          # east wall inner face x = -17.0


def wall_n(tag, x0, z0):      # on the north wall, front facing south
    g = DIM[tag]; return (x0, ER_N - g['d'], z0, g['w'], g['d'], g['h'])


def wall_e(tag, y0, z0):      # on the east wall, front facing west (w runs along y)
    g = DIM[tag]; return (ER_E - g['d'], y0, z0, g['d'], g['w'], g['h'])


def wall_w(tag, y0, z0):      # on the west wall, front facing east
    g = DIM[tag]; return (erx, y0, z0, g['d'], g['w'], g['h'])


def wall_s(tag, x0, z0, inside=True):
    g = DIM[tag]
    return (x0, ery, z0, g['w'], g['d'], g['h']) if inside else (x0, ery - ER['wall'] - g['d'], z0, g['w'], g['d'], g['h'])


PLACE = {
    # electrical room
    'HI-1': wall_n('HI-1', erx + 0.20, erz + 0.80),
    'BAT-1': wall_n('BAT-1', erx + 1.05, erz),
    'DCJ-1': wall_n('DCJ-1', erx + 1.85, erz + 0.90),
    'CP-E': wall_w('CP-E', ery + 0.45, erz),
    'BAT-2': wall_w('BAT-2', ery + 1.35, erz),
    'CHG-48': wall_w('CHG-48', ery + 1.38, erz + 0.75),
    'CHG-48B': wall_w('CHG-48', ery + 1.68, erz + 0.75),
    'MDB': wall_e('MDB', ery + 1.80, erz + 0.60),
    'AUX-DB': wall_e('AUX-DB', ery + 0.90, erz + 0.70),
    'B6-E-BOX': wall_s('B6-E-BOX', ER_E - 0.95, erz + 0.90),
    'MET': wall_s('MET', ER_E - 0.95, erz + 0.30),
    'FCP': wall_s('FCP', ER['door'][0] - 0.55, erz + 1.20, inside=False),
    'MCP-ER': wall_s('MCP', ER['door'][1] + 0.15, erz + 1.30, inside=False),
    # roof (north of EP-1; EP-1 service strip y 8.5-9.3 kept clear; FS-1 at x 3.0-3.6 not touched)
    'RP-2': (1.35, 9.45, 0.50) + tuple(DIM['RP-2'][k] for k in ('w', 'd', 'h')),
    'RP-1': (2.25, 9.35, 0.70) + tuple(DIM['RP-1'][k] for k in ('w', 'd', 'h')),
    'DCD-1': (1.40, 9.55, 0.06, 0.30, 0.20, 0.40),
    'MEB-R': (1.36, 9.30, 0.30, 0.40, 0.05, 0.08),
    'RB-1': (5.85, 9.20, 0.15) + tuple(DIM['RB-1'][k] for k in ('w', 'd', 'h')),
    'JB-E': (1.60, 8.50, 0.35, 0.40, 0.15, 0.30),          # on the EP-1 north face (package interface, docs/06 §3)
}

# support frame and canopy for RP-1/RP-2 (make: galvanised steel), legs + rails + canopy
FRAME = dict(x0=1.25, x1=2.95, y0=9.28, y1=9.80, z_top=2.05, post=0.06, canopy_t=0.004)

# ------------------------------------------------------------------ cable route (polyline centrelines, ROOF frame, m)
# tray width / height in m; 'tray' = perforated cable tray on supports, 'ladder' = cable ladder, 'riser' = vertical sleeve/shaft,
# 'cover' = walk-over cable cover (roof, across the EP-1 service strip), 'conduit' = steel conduit
ROUTE = [
    dict(id='T-R1', kind='tray', w=0.20, h=0.06, z=0.12, pts=[(2.85, 9.90), (0.20, 9.90), (-17.25, 9.90)],
         note='roof tray 200x60 with divider along the north edge (behind the FR-E1 posts), supports every 1.5 m; c2 data cables in a '
              'separate earthed 50 mm steel conduit strapped to the tray (05 §1)'),
    dict(id='T-R2', kind='tray', w=0.15, h=0.06, z=0.12, pts=[(2.95, 9.90), (5.95, 9.90), (7.40, 9.90)],
         note='roof tray east: RB-1 (W009/W010), BOP-R (W006, W115, W116), FS-1 (W121)'),
    dict(id='C-R3', kind='cover', w=0.30, h=0.05, z=0.0, pts=[(2.45, 9.30), (2.45, 8.50)],
         note='walk-over cable cover across the EP-1 service strip: RP-1 -> JB-E, RP-2 -> PMG terminal (W008, W011)'),
    dict(id='V-R4', kind='riser', w=0.30, h=0.30, z=None, pts=[(-17.25, 9.85, 0.12), (-17.25, 9.85, -0.49)],
         note='roof penetration sleeve with rain cap into the ER ceiling'),
    dict(id='L-E1', kind='ladder', w=0.30, h=0.06, z=-0.55, pts=[(-17.25, 9.85), (-20.35, 9.85)],
         note='ER cable ladder under the ceiling, drops to HI-1, BAT-1, DCJ-1, MDB, CP-E'),
    dict(id='L-E2', kind='ladder', w=0.30, h=0.06, z=-0.55, pts=[(-20.35, 9.85), (-20.35, 7.40)],
         note='ER cable ladder, west wall'),
    dict(id='T-H1', kind='tray', w=0.20, h=0.06, z=-0.55, pts=[(-17.25, 8.00), (0.30, 8.00), (0.30, 8.70)],
         note='ER -> hall company DB (W005, W109) in the corridor ceiling'),
]

# ------------------------------------------------------------------ PCB / module envelopes (mm) for the cabinet models
# (length, width, max component height above board, thickness) ; holder = enclosure the board sits in
BOARDS = {
    'B1':      dict(L=220, W=160, H=25, holder='CP-E', kicad='electronics/b1_ecu', desc='ECU: STM32H743 + NXP S32K144 SMCU, 4-layer'),
    'B2':      dict(L=220, W=160, H=22, holder='RP-1', kicad='electronics/b2_sio', desc='sensor I/O: STM32H743 + 2x STM32F373 AFE'),
    'B4':      dict(L=200, W=160, H=35, holder='RP-1', kicad='electronics/b4_drv', desc='drivers: STM32G474 + 4x 6EDL7141 BLDC + 16 HS outputs'),
    'B3-CTRL': dict(L=160, W=100, H=18, holder='RP-2', kicad='electronics/b3_rect', desc='rectifier controller on DC- potential: STM32G474 (HRTIM)'),
    'B3-PWR':  dict(L=300, W=220, H=90, holder='RP-2', kicad='electronics/b3_rect', desc='SiC power stage: 7x IMZA120R020M1H on cold plate, DC link, gate drivers'),
    'B3B':     dict(L=200, W=120, H=60, holder='RP-2', kicad='electronics/b3_rect', desc='independent brake: Semikron SKD 30/12 + IGBT + STGAP2'),
    'B5':      dict(L=100, W=72, H=25, holder='CP-E', kicad=None, desc='HMI: Toradex Verdin iMX8M Plus SoM on Toradex Mallow carrier (bought for v1; custom carrier later)'),
    'B6-CPU':  dict(L=100, W=90, H=110, holder='DIN', kicad='electronics/b6_bop', desc='B6 CPU module, 90 mm DIN housing'),
    'B6-AIT16': dict(L=100, W=45, H=110, holder='DIN', kicad='electronics/b6_bop', desc='B6 16x RTD/TC module'),
    'B6-AIU16': dict(L=100, W=45, H=110, holder='DIN', kicad='electronics/b6_bop', desc='B6 16x 4-20 mA / 0-10 V module'),
    'B6-DI16': dict(L=100, W=45, H=110, holder='DIN', kicad='electronics/b6_bop', desc='B6 16x DI module'),
    'B6-DO16': dict(L=100, W=67.5, H=110, holder='DIN', kicad='electronics/b6_bop', desc='B6 16x relay module'),
    'B6-AO8':  dict(L=100, W=45, H=110, holder='DIN', kicad='electronics/b6_bop', desc='B6 8x AO module'),
}
B6_CONFIG = {'B6-R': ['B6-CPU', 'B6-AIT16', 'B6-AIT16', 'B6-AIU16', 'B6-AIU16', 'B6-DI16', 'B6-DI16', 'B6-DI16',
                      'B6-DO16', 'B6-DO16', 'B6-DO16', 'B6-AO8'],
             'B6-E': ['B6-CPU', 'B6-AIT16', 'B6-AIU16', 'B6-DI16', 'B6-DO16', 'B6-AO8']}
# B6-R sits in the HVAC panel BOP-R (docs/hvac: x 7.0-8.2, y 9.2-9.65, h 2.0): DIN rail at this position (ROOF, m)
B6R_RAIL = dict(x0=7.08, y=9.52, z=1.25)
DISPLAYS = {
    'HMI-B5': dict(w=0.259, d=0.040, h=0.177, holder='CP-E', src='datasheet: DATA MODUL easyTOUCH 10.1" eTD101W3201 259x177x18.9 mm'),
    'HMI-B6R': dict(w=0.258, d=0.036, h=0.169, holder='BOP-R', src='datasheet: Riverdi RVT101HVSNWC00-B 257.96x168.6x15.5 mm (sun-readable variant to confirm)'),
}
