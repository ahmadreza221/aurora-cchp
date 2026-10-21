"""GR180-CCHP electrical package (EL) — FreeCAD envelope models.

Builds (ROOF frame, docs/06_master_design.md §1; FreeCAD units mm, 1 m = 1000 mm):
  * EL_ER.step            electrical room: hybrid inverter HI-1, 20 kWh HV battery, 48 V battery, ECU cabinet CP-E (B1, B5, chargers,
                          switch, router, HMI), MDB (grid incomer, ATS-1, SPD, meters), AUX-DB, B6-E box, DC junction DCJ-1, MET,
                          fire panel FCP + call point outside the door
  * EL_ROOF.step          roof cabinets RP-1 (B2, B4, SR1) and RP-2 (PEB: B3, B3b, contactors), brake resistors RB-1, DC isolator
                          DCD-1, earth bar MEB-R, junction box JB-E on the EP-1 north face, support frame + sun canopy,
                          B6-R DIN modules + Riverdi HMI inside the HVAC panel BOP-R
  * EL_ROUTE.step         cable trays, walk-over cover, roof riser, ER ladders, ER -> hall tray (~30 m roof -> ER)
  * EL_ER_ROOM_REF.step   reference walls of the assumed electrical room (for the site assembly)
  * EL_ALL.step           everything above
and cad_out/electrical/electrical_interfaces.json + clash report (electrical items against each other and against the
HVAC roof layout sim/hvac/roof_layout.json).

Run:  LANG=en_US.UTF-8 /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd cad/electrical/el_build.py
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'cad_out', 'electrical')
sys.path.insert(0, HERE)
import el_items as E  # noqa: E402

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Import  # noqa: E402

M = 1000.0
DOC = App.newDocument('GR180_EL')
GROUPS = {}            # assembly name -> list of objects
REGISTRY = []          # (assembly, label, bbox in m, top_level_tag) for clash checks


def V(x, y, z):
    return App.Vector(x * M, y * M, z * M)


def add(assembly, label, shape, tag=None):
    o = DOC.addObject('Part::Feature', label.replace(' ', '_').replace('/', '_').replace('.', '_'))
    o.Label = label
    o.Shape = shape
    GROUPS.setdefault(assembly, []).append(o)
    bb = shape.BoundBox
    REGISTRY.append((assembly, label, (bb.XMin / M, bb.YMin / M, bb.ZMin / M, bb.XMax / M, bb.YMax / M, bb.ZMax / M), tag))
    return o


def box(x0, y0, z0, w, d, h):
    return Part.makeBox(w * M, d * M, h * M, V(x0, y0, z0))


def shell(x0, y0, z0, w, d, h, t=0.0025):
    outer = box(x0, y0, z0, w, d, h)
    inner = box(x0 + t, y0 + t, z0 + t, w - 2 * t, d - 2 * t, h - 2 * t)
    return outer.cut(inner)


class Cab:
    """Enclosure with a local frame: u = left->right seen from the front, v = from back wall towards the door, z = up."""

    def __init__(self, assembly, tag, env, front, label=None, t=0.0025):
        self.a, self.tag, self.front, self.t = assembly, tag, front, t
        x0, y0, z0, w, d, h = env
        self.env = env
        # width along u, depth along v
        if front in ('S', 'N'):
            self.U, self.Dp = w, d
        else:
            self.U, self.Dp = d, w
        self.H = h
        body_d = self.Dp - 0.02          # door 20 mm thick envelope incl. handle stand-off
        lab = label or tag
        add(assembly, '%s body' % lab, self._shell(body_d), tag)
        add(assembly, '%s door' % lab, self.local(0, body_d, 0, self.U, 0.02, h), tag)

    def _shell(self, body_d):
        t = self.t
        outer = box(*self.to_global(0, 0, 0, self.U, body_d, self.H))
        inner = box(*self.to_global(t, t, t, self.U - 2 * t, body_d, self.H - 2 * t))      # open towards the door
        return outer.cut(inner)

    def to_global(self, u0, v0, z0, du, dv, dz):
        x0, y0, zc, w, d, h = self.env
        if self.front == 'S':
            return (x0 + u0, y0 + d - v0 - dv, zc + z0, du, dv, dz)
        if self.front == 'N':
            return (x0 + w - u0 - du, y0 + v0, zc + z0, du, dv, dz)
        if self.front == 'E':
            return (x0 + v0, y0 + u0, zc + z0, dv, du, dz)
        return (x0 + w - v0 - dv, y0 + d - u0 - du, zc + z0, dv, du, dz)       # 'W'

    def local(self, u0, v0, z0, du, dv, dz):
        return box(*self.to_global(u0, v0, z0, du, dv, dz))

    def part(self, label, u0, v0, z0, du, dv, dz):
        return add(self.a, '%s / %s' % (self.tag, label), self.local(u0, v0, z0, du, dv, dz))

    def plate(self):
        t = self.t
        return self.part('mounting plate', t + 0.02, t + 0.005, t + 0.03, self.U - 2 * t - 0.04, 0.003, self.H - 2 * t - 0.06)

    def din(self, label, z, u0=None, length=None, n=0, mod_w=0.018, mod_d=0.07, mod_h=0.09):
        """DIN rail at height z with n modules of width mod_w (envelope of MCBs / terminals / relays)."""
        u0 = self.t + 0.04 if u0 is None else u0
        length = (self.U - 2 * self.t - 0.08) if length is None else length
        self.part('%s rail' % label, u0, 0.012, z, length, 0.0075, 0.035)
        if n:
            self.part('%s (%d modules)' % (label, n), u0 + 0.01, 0.02, z - (mod_h - 0.035) / 2, min(n * mod_w, length - 0.02), mod_d, mod_h)

    def board(self, name, u0, z0, standoff=0.012):
        b = E.BOARDS[name]
        L, W, H = b['L'] / M, b['W'] / M, b['H'] / M
        self.part('%s PCB' % name, u0, 0.008 + standoff, z0, L, 0.0016, W)
        self.part('%s components' % name, u0 + 0.005, 0.008 + standoff + 0.0016, z0 + 0.005, L - 0.01, H, W - 0.01)


def env(tag):
    return E.PLACE[tag]


# =============================================================================== electrical room
def build_er():
    A = 'EL_ER'
    g = E.DIM
    # HI-1 hybrid inverter (wall, north) + battery
    x0, y0, z0, w, d, h = env('HI-1')
    add(A, 'HI-1 hybrid inverter (%s)' % g['HI-1']['src'].split(':')[-1].strip(), box(x0, y0, z0, w, d, h), 'HI-1')
    x0, y0, z0, w, d, h = env('BAT-1')
    add(A, 'BAT-1 rack 3U-LRACK (Deye BOS-G20)', shell(x0, y0, z0, w, d, h, 0.003), 'BAT-1')
    for i in range(4):
        add(A, 'BAT-1 module BOS-GM5.1 %d (5.12 kWh, 440x133x570)' % (i + 1), box(x0 + 0.045, y0 + 0.016, z0 + 0.10 + i * 0.30, 0.440, 0.570, 0.133), 'BAT-1')
    add(A, 'BAT-1 HV control box HVB750V/100A-EU (440x150x570)', box(x0 + 0.045, y0 + 0.016, z0 + 0.10 + 4 * 0.30, 0.440, 0.570, 0.150), 'BAT-1')
    for tagc in ('CHG-48', 'CHG-48B'):
        x0, y0, z0, w, d, h = env(tagc)
        add(A, '%s 48 V charger Victron Smart IP43 48/13 (wall)' % tagc, box(x0, y0, z0, w, d, h), tagc)
    # DC junction DCJ-1 (wall box)
    c = Cab(A, 'DCJ-1', env('DCJ-1'), 'S', 'DCJ-1 DC junction (SPD-DC2 T2, gPV fuses 2P 50 A, isolator)')
    c.plate(); c.din('DCJ-1 SPD + fuse holders', 0.30, n=8, mod_w=0.018)
    # ECU cabinet CP-E (floor, west wall, door east)
    c = Cab(A, 'CP-E', env('CP-E'), 'E', 'CP-E ECU cabinet Rittal VX25 600x2000x500')
    c.plate()
    c.board('B1', 0.06, 1.55)
    c.board('B5', 0.32, 1.60)
    c.part('network switch Westermo Lynx L205-S1 (DIN, 52x100x101)', 0.06, 0.02, 1.30, 0.052, 0.101, 0.100)
    c.part('router Teltonika RUTX11 (static IP + LTE, SMS; 95x115x44)', 0.20, 0.02, 1.30, 0.115, 0.044, 0.095)
    c.din('ORing module + DC-DC 48/24 V PULS CD10.242 x2', 1.05, n=3, mod_w=0.045, mod_d=0.12, mod_h=0.125)
    c.din('interposing relays Finder 34.51 (K-LS, K-SP, INV, EH-950)', 0.80, n=20, mod_w=0.0062)
    c.din('48 V / 24 V DC MCBs', 0.62, n=14)
    c.din('terminals field / W1xx', 0.42, n=28, mod_w=0.0062)
    c.din('terminals W103 / W109 / W124', 0.24, n=28, mod_w=0.0062)
    c.part('cable entry + gland plate (bottom)', 0.01, 0.015, 0.003, c.U - 0.02, c.Dp - 0.04, 0.025)
    hd = E.DISPLAYS['HMI-B5']
    c.part('HMI-B5 10.1" touch display on door', (c.U - hd['w']) / 2, c.Dp - 0.02 - hd['d'] + 0.02, 1.35, hd['w'], hd['d'] - 0.02, hd['h'])
    # 48 V battery box
    x0, y0, z0, w, d, h = env('BAT-2')
    add(A, 'BAT-2 box 48 V 100 Ah LFP + Class-T fuse', shell(x0, y0, z0, w, d, h), 'BAT-2')
    add(A, 'BAT-2 48 V LFP 19" module (442 x 420 x 161 mm class)', box(x0 + 0.04, y0 + 0.08, z0 + 0.05, 0.420, 0.442, 0.161), 'BAT-2')
    # MDB (east wall, door west): grid incomer, zero-export CT, SPD T1+2, JT-920, HI-1 GRID MCB, LOAD MCCB, ATS-1, K-NPE, JT-901, Q1/Q2
    c = Cab(A, 'MDB', env('MDB'), 'W', 'MDB main board Rittal AX 1000x1000x300 (grid + ATS-1)')
    c.plate()
    c.part('MCCB grid incomer 63 A 4P', 0.05, 0.02, 0.70, 0.14, 0.10, 0.16)
    c.part('ATS-1 Socomec ATyS p M 4P 63 A (324x245; I = HI-1 LOAD, II = grid bypass)', 0.30, 0.02, 0.62, 0.324, 0.15, 0.245)
    c.part('MCCB HI-1 LOAD output 63 A 4P', 0.70, 0.02, 0.70, 0.14, 0.10, 0.16)
    c.din('SPD T1+2 TN-S + MCB HI-1 GRID + K-NPE + monitoring relay', 0.45, n=24)
    c.din('Q1 company feeder 50 A 4P, Q2 AUX-DB 32 A 4P, CT blocks', 0.22, n=20)
    c.part('JT-920 grid meter (door)', 0.20, c.Dp - 0.10, 0.80, 0.096, 0.08, 0.096)
    c.part('JT-901 LOAD meter Janitza UMG 96-PA (door)', 0.60, c.Dp - 0.10, 0.80, 0.096, 0.08, 0.096)
    # AUX-DB
    c = Cab(A, 'AUX-DB', env('AUX-DB'), 'W', 'AUX-DB plant auxiliaries Rittal AX 600x800x250')
    c.plate(); c.din('MCB + RCD (BOP-R 32 A, FCP, chargers, FCU-E/EF-E, EH-950 SSR)', 0.55, n=22)
    c.din('meters JT-902..905 (DIN)', 0.30, n=4, mod_w=0.072, mod_d=0.07, mod_h=0.09)
    # B6-E box with its DIN modules
    c = Cab(A, 'B6-E-BOX', env('B6-E-BOX'), 'N', 'B6-E HVAC indoor controller box Rittal AX 600x600x210')
    c.plate()
    u = 0.04
    for m in E.B6_CONFIG['B6-E']:
        b = E.BOARDS[m]
        c.part('B6-E %s module' % m, u, 0.015, 0.22, b['W'] / M, b['H'] / M, b['L'] / M)
        u += b['W'] / M + 0.002
    c.din('B6-E terminals + 24 V PSU', 0.08, n=24, mod_w=0.0062)
    # MET, FCP, call point
    x0, y0, z0, w, d, h = env('MET')
    add(A, 'MET main earth terminal bar (W113 to MEB-R, PE of all boards)', box(x0, y0, z0, w, d, h), 'MET')
    x0, y0, z0, w, d, h = env('FCP')
    add(A, 'FCP fire detection + extinguishing control panel (corridor, outside ER door)', box(x0, y0, z0, w, d, h), 'FCP')
    x0, y0, z0, w, d, h = env('MCP-ER')
    add(A, 'HS-893 manual release (yellow) + HS-895 abort (blue) + HS-891 (red) at ER door', box(x0, y0, z0, w * 3.3, d, h), 'MCP-ER')


# =============================================================================== roof
def build_roof():
    A = 'EL_ROOF'
    f = E.FRAME
    # frame: 4 posts, 2 back rails, canopy
    p = f['post']
    for (x, y) in ((f['x0'], f['y0']), (f['x1'] - p, f['y0']), (f['x0'], f['y1'] - p), (f['x1'] - p, f['y1'] - p)):
        add(A, 'FR-E1 post 60x60 galv.', box(x, y, 0.0, p, p, f['z_top']), 'FR-E1')
    for z in (0.45, 1.55):
        add(A, 'FR-E1 rail C-channel z %.2f' % z, box(f['x0'], f['y1'] - 0.04, z, f['x1'] - f['x0'], 0.04, 0.06), 'FR-E1')
    add(A, 'FR-E1 sun canopy 4 mm', box(1.20, 9.20, f['z_top'], 1.78, 0.65, f['canopy_t']), 'FR-E1')
    # RP-2 = PEB rectifier cabinet (door south)
    c = Cab(A, 'RP-2', env('RP-2'), 'S', 'RP-2 PEB rectifier cabinet stainless IP66 800x1000x400')
    c.plate()
    c.part('cold plate (glycol, B3 -> PMG -> OC-1 loop)', 0.05, 0.011, 0.08, 0.36, 0.012, 0.32)
    c.board('B3-PWR', 0.05, 0.08, standoff=0.015)
    c.board('B3-CTRL', 0.45, 0.70)
    c.board('B3B', 0.45, 0.45)
    c.part('K-DC+ Schaltbau C195 A (143x142x68)', 0.05, 0.02, 0.60, 0.068, 0.142, 0.143)
    c.part('K-DC- Schaltbau C195 A', 0.13, 0.02, 0.60, 0.068, 0.142, 0.143)
    c.part('K-PRE + R_PRE 2x50 ohm', 0.21, 0.02, 0.60, 0.09, 0.10, 0.12)
    c.part('K-BR (NC) AC contactor 63 A', 0.05, 0.02, 0.82, 0.07, 0.12, 0.12)
    c.part('CM choke 3~ (PMG side)', 0.15, 0.02, 0.82, 0.16, 0.12, 0.10)
    c.din('SPD-DC1 T1+2 1000 V + 24 V supply + terminals', 0.92, u0=0.40, length=0.36, n=14)
    # RP-1 = control cabinet (door south)
    c = Cab(A, 'RP-1', env('RP-1'), 'S', 'RP-1 roof control cabinet stainless IP66 600x800x300')
    c.plate()
    c.board('B2', 0.03, 0.45)
    c.board('B4', 0.03, 0.18)
    c.din('SR1 Pilz PNOZ m B0 (45 mm) + 3x PNOZ m EF 16DI/4DI4DOR (22.5 mm)', 0.68, u0=0.26, length=0.30, n=5, mod_w=0.0225, mod_d=0.12, mod_h=0.1014)
    c.din('DC-DC 48/24 V + fibre switch + data SPD', 0.08, u0=0.26, length=0.30, n=5, mod_w=0.05, mod_d=0.11, mod_h=0.10)
    c.din('terminals (W1xx, W116, sensors)', 0.40, u0=0.26, length=0.30, n=40, mod_w=0.0062)
    # DCD-1, MEB-R, RB-1, JB-E
    x0, y0, z0, w, d, h = env('DCD-1')
    add(A, 'DCD-1 DC isolator 1000 V 50 A IP66 (lockable)', box(x0, y0, z0, w, d, h), 'DCD-1')
    x0, y0, z0, w, d, h = env('MEB-R')
    add(A, 'MEB-R main earth bar roof + test link (earth-well conductor W118 >= 50 mm2)', box(x0, y0, z0, w, d, h), 'MEB-R')
    x0, y0, z0, w, d, h = env('RB-1')
    add(A, 'RB-1 braking resistor enclosure (R_BR1 ~18-20 ohm bank + R_BR2 8 ohm tier), IP23', box(x0, y0, z0, w, d, h), 'RB-1')
    add(A, 'RB-1 rain hood', box(x0 - 0.03, y0 - 0.03, z0 + h, w + 0.06, d + 0.06, 0.06), 'RB-1')
    for (dx, dy) in ((0, 0), (w - 0.04, 0), (0, d - 0.04), (w - 0.04, d - 0.04)):
        add(A, 'RB-1 foot', box(x0 + dx, y0 + dy, 0.0, 0.04, 0.04, z0), 'RB-1')
    x0, y0, z0, w, d, h = env('JB-E')
    add(A, 'JB-E junction box stainless on EP-1 north face (sensor / valve wiring)', box(x0, y0, z0, w, d, h), 'JB-E')
    # B6-R modules on a DIN rail inside the HVAC panel BOP-R + Riverdi HMI on its door
    r = E.B6R_RAIL
    x = r['x0']
    add(A, 'B6-R DIN rail in BOP-R (HVAC panel)', box(x, r['y'] + 0.12, r['z'] + 0.04, 0.70, 0.0075, 0.035), 'B6-R')
    for m in E.B6_CONFIG['B6-R']:
        b = E.BOARDS[m]
        add(A, 'B6-R %s module' % m, box(x, r['y'] + 0.0, r['z'], b['W'] / M, b['H'] / M, b['L'] / M), 'B6-R')
        x += b['W'] / M + 0.002
    hd = E.DISPLAYS['HMI-B6R']
    add(A, 'HMI-B6R Riverdi 10.1" STM32 touch display on BOP-R door', box(7.40, 9.20 - 0.016, 1.30, hd['w'], 0.016, hd['h']), 'HMI-B6R')
    # roof call points
    add(A, 'HS-892 manual release (yellow) + HS-894 abort (blue) + HS-891 (red), on frame west face', box(1.18, 9.40, 1.20, 0.06, 0.30, 0.09), 'MCP-R')


# =============================================================================== cable route
def seg_box(p0, p1, w, h, z=None):
    """Axis-aligned tray segment between 2 points (2D with fixed z, or 3D vertical)."""
    if len(p0) == 2:
        (x0, y0), (x1, y1) = p0, p1
        if abs(y1 - y0) < 1e-9:      # along x
            return box(min(x0, x1), y0 - w / 2, z, abs(x1 - x0) + w / 2, w, h), abs(x1 - x0)
        return box(x0 - w / 2, min(y0, y1), z, w, abs(y1 - y0) + w / 2, h), abs(y1 - y0)
    (x0, y0, z0), (x1, y1, z1) = p0, p1
    return box(x0 - w / 2, y0 - w / 2, min(z0, z1), w, w, abs(z1 - z0)), abs(z1 - z0)


def build_route():
    A = 'EL_ROUTE'
    lengths = {}
    for r in E.ROUTE:
        L = 0.0
        for p0, p1 in zip(r['pts'][:-1], r['pts'][1:]):
            shp, l = seg_box(p0, p1, r['w'], r['h'], r['z'])
            L += l
            add(A, '%s %s %dx%d mm' % (r['id'], r['kind'], r['w'] * M, r['h'] * M), shp, r['id'])
        lengths[r['id']] = L
        if r['kind'] in ('tray', 'ladder') and r['z'] is not None and r['z'] > 0:      # roof supports every 1.5 m
            pts = r['pts']
            for p0, p1 in zip(pts[:-1], pts[1:]):
                n = int(math.dist(p0, p1) // 1.5)
                for k in range(n + 1):
                    t = k / max(n, 1)
                    x, y = p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])
                    add(A, '%s support (concrete block + rail)' % r['id'], box(x - 0.05, y - r['w'] / 2, 0.0, 0.10, r['w'], r['z']), r['id'])
    return lengths


def build_room_ref():
    A = 'EL_ER_ROOM_REF'
    er, t = E.ER, E.ER['wall']
    x0, y0, z0, w, d, h = er['x0'], er['y0'], er['z0'], er['w'], er['d'], er['h']
    add(A, 'ER floor slab (reference)', box(x0 - t, y0 - t, z0 - 0.15, w + 2 * t, d + 2 * t, 0.15))
    add(A, 'ER north wall (ref)', box(x0 - t, y0 + d, z0, w + 2 * t, t, h))
    add(A, 'ER west wall (ref)', box(x0 - t, y0, z0, t, d, h))
    add(A, 'ER east wall (ref)', box(x0 + w, y0, z0, t, d, h))
    d0, d1 = er['door']
    add(A, 'ER south wall west of door (ref)', box(x0 - t, y0 - t, z0, d0 - x0 + t, t, h))
    add(A, 'ER south wall east of door (ref)', box(d1, y0 - t, z0, x0 + w - d1 + t, t, h))
    add(A, 'ER south wall over door (ref)', box(d0, y0 - t, z0 + 2.1, d1 - d0, t, h - 2.1))
    add(A, 'ER roof slab (ref)', box(x0 - t, y0 - t, z0 + h, w + 2 * t, d + 2 * t, 0.3))


# =============================================================================== checks, interfaces, export
def clash_check():
    """Top-level item envelopes (one per tag) against each other and against the HVAC roof layout."""
    tops = {}
    for i_reg, (a, lab, bb, tag) in enumerate(REGISTRY):
        if tag is None or a == 'EL_ER_ROOM_REF':
            continue
        key = tag if tag != 'FR-E1' else '%s#%s %d' % (tag, lab, i_reg)     # frame parts checked one by one
        x0, y0, z0, x1, y1, z1 = bb
        if key in tops:
            X0, Y0, Z0, X1, Y1, Z1 = tops[key]
            tops[key] = (min(X0, x0), min(Y0, y0), min(Z0, z0), max(X1, x1), max(Y1, y1), max(Z1, z1))
        else:
            tops[key] = bb
    hv = json.load(open(os.path.join(ROOT, 'sim', 'hvac', 'roof_layout.json')))['equipment']
    others = {}
    for k, e in hv.items():
        if e.get('kind') in ('rect', 'circle') and e['h'] > 0:
            if e['kind'] == 'circle':
                r = e['w'] / 2
                others['HVAC:' + k] = (e['x'] - r, e['y'] - r, 0.0, e['x'] + r, e['y'] + r, e['h'])
            else:
                others['HVAC:' + k] = (e['x'], e['y'], 0.0, e['x'] + e['w'], e['y'] + e['d'], e['h'])

    def ov(a, b, tol=0.001):
        return all(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) > tol for i in range(3))
    allowed = {('JB-E', 'HVAC:EP-1'), ('B6-R', 'HVAC:BOP-R'), ('HMI-B6R', 'HVAC:BOP-R'), ('C-R3', 'HVAC:EP-1')}
    res = []
    keys = sorted(tops)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            fa, fb = a.split('#')[0], b.split('#')[0]
            if ov(tops[a], tops[b]) and not (fa == fb or
                                             {fa, fb} <= {'T-R1', 'T-R2', 'V-R4', 'L-E1', 'L-E2', 'T-H1'}):
                res.append('%s x %s' % (a, b))
        for b, bb in others.items():
            if ov(tops[a], bb) and (a, b) not in allowed:
                res.append('%s x %s' % (a, b))
    # internal: parts inside the same enclosure must not overlap each other
    inner = {}
    for a_, lab, bb, tag in REGISTRY:
        if ' / ' in lab:
            inner.setdefault(lab.split(' / ')[0], []).append((lab, bb))
    for cab, parts in inner.items():
        for i, (la, ba) in enumerate(parts):
            for lb, bb in parts[i + 1:]:
                if ov(ba, bb):
                    res.append('inside %s: %s x %s' % (cab, la.split(' / ')[1], lb.split(' / ')[1]))
    return tops, res


def main():
    os.makedirs(OUT, exist_ok=True)
    build_er()
    build_roof()
    lengths = build_route()
    build_room_ref()
    for a, objs in GROUPS.items():
        Import.export(objs, os.path.join(OUT, a + '.step'))
    Import.export([o for a, objs in GROUPS.items() if a != 'EL_ER_ROOM_REF' for o in objs], os.path.join(OUT, 'EL_ALL.step'))
    DOC.saveAs(os.path.join(OUT, 'GR180_EL.FCStd'))
    tops, clashes = clash_check()
    route_roof_er = lengths['T-R1'] + lengths['V-R4'] + lengths['L-E1'] * 0.5
    ifc = dict(frame='ROOF (docs/06_master_design.md §1), m', generated_by='cad/electrical/el_build.py', interfaces=[
        dict(name='EL-PMG-POWER', at=[2.70, 8.10, 0.60], dir='-x (into EP-1 east terminal box)', size='3x16 mm2 shielded + PE (W008), <= 3 m',
             counterpart='E3/E5 PMG terminal box on EP-1 east face'),
        dict(name='EL-JB-E', at=[1.80, 8.50, 0.50], dir='+y (box on EP-1 north face)', size='JB-E 400x300x150 mm', counterpart='E5 package: leave the face clear, glands down'),
        dict(name='EL-RP2-GLYCOL', at=[1.55, 9.55, 0.50], dir='-z (bottom gland plate of RP-2)', size='DN15 supply + return, glycol <= 40 C design (ALM 58 C)',
             counterpart='glycol loop B3 -> PMG -> OC-1 (docs/hvac, E5)'),
        dict(name='EL-MEB-R', at=[1.56, 9.32, 0.34], dir='—', size='earth-well conductor W118 >= 50 mm2 Cu via test link', counterpart='dedicated earth well (site)'),
        dict(name='EL-BOP-R-FEED', at=[7.40, 9.88, 0.12], dir='-y into BOP-R bottom', size='W006 5G10 + W115/W116 + W121', counterpart='HVAC panel BOP-R'),
        dict(name='EL-B6R-RAIL', at=[E.B6R_RAIL['x0'], E.B6R_RAIL['y'], E.B6R_RAIL['z']], dir='DIN rail, 0.70 m long, 0.11 m deep', size='12 B6-R modules',
             counterpart='HVAC panel BOP-R must reserve 0.75 m x 0.25 m x 0.15 m rail space + door cut-out for HMI-B6R 260x170 mm'),
        dict(name='EL-FS1-RELEASE', at=[3.30, 9.30, 1.00], dir='to FS-1 cabinet', size='W121 PH120 2x1.5 per actuator (XY-888A/C, PSL-890A/C, ZSC-899A)', counterpart='docs/hvac/08 FS-1'),
        dict(name='EL-ROOF-PENETRATION', at=[-17.25, 9.88, 0.0], dir='-z into ER', size='sleeve 300x300 mm with rain cap', counterpart='site/building (S)'),
        dict(name='EL-ER-ROOM', at=[E.ER['x0'], E.ER['y0'], E.ER['z0']], dir='+x +y +z', size='%.1f x %.1f x %.1f m clear (ASSUMED)' % (E.ER['w'], E.ER['d'], E.ER['h']),
             counterpart='site/building (S); HVAC FS-2 agent mass scales with room volume'),
        dict(name='EL-HALL-DB', at=[0.30, 8.70, -1.9], dir='hall west wall', size='W005 5G10 + W109 25x0.75', counterpart='company DB (existing)'),
        dict(name='EL-GRID-INCOMER', at=[E.PLACE['MDB'][0], E.PLACE['MDB'][1] + 0.5, E.ER['z0']], dir='from utility meter', size='W018 per existing connection',
             counterpart='utility connection (site)'),
    ], route_lengths_m=lengths, roof_to_er_route_m=round(route_roof_er, 1), clashes=clashes,
        items={k: [round(v, 3) for v in bb] for k, bb in sorted(tops.items()) if '#' not in k})
    json.dump(ifc, open(os.path.join(OUT, 'electrical_interfaces.json'), 'w'), indent=1, ensure_ascii=False)
    print('objects: %d in %d assemblies; route lengths %s; roof->ER route ~%.1f m' % (sum(len(v) for v in GROUPS.values()), len(GROUPS),
          {k: round(v, 1) for k, v in lengths.items()}, route_roof_er))
    print('clashes: %s' % (clashes or 'none'))


COLORS = {'HI-1': '#2b6cb0', 'BAT-1': '#2f855a', 'BAT-2': '#38a169', 'CP-E': '#a0aec0', 'MDB': '#cbd5e0', 'AUX-DB': '#cbd5e0',
          'B6-E-BOX': '#cbd5e0', 'DCJ-1': '#ed8936', 'FCP': '#e53e3e', 'MCP-ER': '#e53e3e', 'MCP-R': '#e53e3e', 'MET': '#b7791f',
          'RP-1': '#a0aec0', 'RP-2': '#718096', 'RB-1': '#c05621', 'DCD-1': '#ed8936', 'MEB-R': '#b7791f', 'JB-E': '#a0aec0',
          'FR-E1': '#4a5568', 'B6-R': '#805ad5', 'HMI-B6R': '#1a202c'}


def render():
    """Isometric PNG renders and plan views (matplotlib inside FreeCAD's Python)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    hv = json.load(open(os.path.join(ROOT, 'sim', 'hvac', 'roof_layout.json')))['equipment']

    def faces(o):
        pts, tris = o.Shape.tessellate(5.0)
        return [[(pts[i].x / M, pts[i].y / M, pts[i].z / M) for i in t] for t in tris]

    def draw(ax, objs, color_of, alpha=1.0):
        def is_bg(o):
            return o.Label.endswith(' body') or 'mounting plate' in o.Label
        bodies = [o for o in objs if is_bg(o)]
        rest = [o for o in objs if not is_bg(o)]
        for o in bodies:                                   # enclosures transparent so the boards inside are visible
            f = faces(o)
            if f:
                ax.add_collection3d(Poly3DCollection(f, facecolor=color_of(o), edgecolor='none', alpha=0.10, linewidths=0, zorder=0))
        for o in rest:
            f = faces(o)
            if f:
                ax.add_collection3d(Poly3DCollection(f, facecolor=color_of(o), edgecolor='#2d3748', alpha=alpha, linewidths=0.1))

    def color(o):
        lab0 = o.Label
        for key, col in (('PCB', '#22543d'), ('components', '#48bb78'), (' rail', '#a0aec0'), ('modules', '#4a5568'), ('module', '#6b46c1'),
                         ('Schaltbau', '#c53030'), ('contactor', '#c53030'), ('cold plate', '#3182ce'), ('display', '#1a202c'),
                         ('meter', '#2c5282'), ('MCCB', '#2d3748'), ('ATS-1', '#dd6b20'), ('switch', '#2b6cb0'), ('router', '#2b6cb0'),
                         ('mounting plate', '#edf2f7'), ('choke', '#975a16')):
            if key in lab0:
                return col
        for a, lab, bb, tag in REGISTRY:
            if lab == o.Label:
                if 'door' in lab:
                    return '#e2e8f0'
                if tag in ('T-R1', 'T-R2', 'C-R3', 'V-R4', 'L-E1', 'L-E2', 'T-H1'):
                    return '#718096'
                return COLORS.get(tag, '#a0aec0')
        return '#a0aec0'

    def hvac_boxes(ax):
        for k, e in hv.items():
            if e.get('h', 0) <= 0:
                continue
            if e['kind'] == 'circle':
                x0, y0, w, d = e['x'] - e['w'] / 2, e['y'] - e['w'] / 2, e['w'], e['w']
            else:
                x0, y0, w, d = e['x'], e['y'], e['w'], e['d']
            b = box(x0, y0, 0, w, d, e['h'])
            pts, tris = b.tessellate(10.0)
            ax.add_collection3d(Poly3DCollection([[(pts[i].x / M, pts[i].y / M, pts[i].z / M) for i in t] for t in tris],
                                                 facecolor='#e2e8f0', edgecolor='#a0aec0', alpha=0.25, linewidths=0.2))
            ax.text(x0 + w / 2, y0 + d / 2, e['h'] + 0.1, k, fontsize=6, color='#4a5568')

    def no_doors(objs):
        return [o for o in objs if ' door' not in o.Label]

    # roof isometric (doors hidden to show the boards)
    fig = plt.figure(figsize=(12, 7)); ax = fig.add_subplot(projection='3d')
    hvac_boxes(ax)
    draw(ax, no_doors(GROUPS['EL_ROOF']) + [o for o in GROUPS['EL_ROUTE'] if o.Shape.BoundBox.ZMin >= -1], color)
    ax.set_xlim(0, 10); ax.set_ylim(0, 10.5); ax.set_zlim(0, 4); ax.set_box_aspect((10, 10.5, 4)); ax.view_init(28, -60)
    ax.set_title('GR180-CCHP electrical on the roof (ROOF frame, m): RP-1, RP-2 (PEB), RB-1, frame + canopy, trays, B6-R in BOP-R; HVAC in grey')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'EL_roof_iso.png'), dpi=140); plt.close(fig)
    # roof close-up of the cabinets
    fig = plt.figure(figsize=(10, 7)); ax = fig.add_subplot(projection='3d')
    draw(ax, no_doors(GROUPS['EL_ROOF']), color)
    ax.set_xlim(1.0, 3.2); ax.set_ylim(8.4, 10.1); ax.set_zlim(0, 2.2); ax.set_box_aspect((2.2, 1.7, 2.2)); ax.view_init(18, -70)
    ax.set_title('RP-2 (B3 power stage, controller, B3b, contactors) and RP-1 (B2, B4, SR1) — doors removed')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'EL_roof_cabinets.png'), dpi=140); plt.close(fig)
    # electrical room
    er = E.ER
    fig = plt.figure(figsize=(11, 8)); ax = fig.add_subplot(projection='3d')
    draw(ax, GROUPS['EL_ER_ROOM_REF'][:4], lambda o: '#f7fafc', alpha=0.15)
    draw(ax, no_doors(GROUPS['EL_ER']) + [o for o in GROUPS['EL_ROUTE'] if o.Shape.BoundBox.XMax < -16.5], color)
    ax.set_xlim(er['x0'] - 0.3, er['x0'] + er['w'] + 0.3); ax.set_ylim(er['y0'] - 0.6, er['y0'] + er['d'] + 0.2)
    ax.set_zlim(er['z0'], er['z0'] + er['h'] + 0.4); ax.set_box_aspect((er['w'] + 0.6, er['d'] + 0.8, er['h'] + 0.4)); ax.view_init(30, -55)
    ax.set_title('Electrical room (assumed 3.5 x 3.0 x 2.5 m): HI-1, 20 kWh HV battery, CP-E (B1, B5, HMI), MDB + ATS-1, AUX-DB, B6-E, FCP outside')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'EL_room_iso.png'), dpi=140); plt.close(fig)
    # plan views (top) with tags
    for name, objs, xl, yl in (('EL_plan_roof', GROUPS['EL_ROOF'] + GROUPS['EL_ROUTE'], (-0.2, 10.2), (-0.2, 10.4)),
                               ('EL_plan_room', GROUPS['EL_ER'] + GROUPS['EL_ROUTE'], (er['x0'] - 0.5, er['x0'] + er['w'] + 0.5), (er['y0'] - 0.6, er['y0'] + er['d'] + 0.3))):
        fig, ax = plt.subplots(figsize=(10, 9))
        if name == 'EL_plan_roof':
            for k, e in hv.items():
                if e['kind'] == 'circle':
                    ax.add_patch(plt.Circle((e['x'], e['y']), e['w'] / 2, fc='#edf2f7', ec='#a0aec0'))
                    ax.text(e['x'], e['y'], k, fontsize=7, ha='center', va='center', color='#4a5568')
                elif e['kind'] == 'rect':
                    ax.add_patch(plt.Rectangle((e['x'], e['y']), e['w'], e['d'], fc='#edf2f7', ec='#a0aec0'))
                    ax.text(e['x'] + e['w'] / 2, e['y'] + e['d'] / 2, k, fontsize=7, ha='center', va='center', color='#4a5568')
        seen = set()
        for o in objs:
            bb = o.Shape.BoundBox
            if bb.XMax / M < xl[0] or bb.XMin / M > xl[1]:
                continue
            tag = next((t for a, lab, b, t in REGISTRY if lab == o.Label), None)
            ax.add_patch(plt.Rectangle((bb.XMin / M, bb.YMin / M), bb.XLength / M, bb.YLength / M, fc=COLORS.get(tag, '#cbd5e0'),
                                       ec='#2d3748', lw=0.3, alpha=0.6))
            if tag and tag not in seen and ' / ' not in o.Label:
                seen.add(tag)
                ax.text(bb.Center.x / M, bb.Center.y / M, tag, fontsize=7, ha='center', va='center', weight='bold')
        ax.set_xlim(*xl); ax.set_ylim(*yl); ax.set_aspect('equal'); ax.grid(lw=0.2)
        ax.set_xlabel('x east [m] (ROOF frame)'); ax.set_ylabel('y north [m]')
        ax.set_title('%s — electrical (coloured), HVAC (grey)' % name)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, name + '.svg')); fig.savefig(os.path.join(OUT, name + '.png'), dpi=120); plt.close(fig)


main()
render()
