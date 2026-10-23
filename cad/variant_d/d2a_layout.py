"""GR180 version D2 - auxiliary systems (D2A) shared layout numbers (pure Python, no FreeCAD).

ENG frame, mm: x = engine axis (+ downstream), x = 0 at the shaft-tunnel spigot front face, z up, y = right-hand.
Used by cad/variant_d/d2a_*.py and sim/variant_d/d2a_aux_calc.py.

Layout rules (2026-10-23):
* everything auxiliary sits on ONE side skid on -y (AX-610, bolted to the FR-110 base frame, own AV mounts);
  +y and the space above the intake plenum stay free for the intake filter box (F7 V-cell 592 x 592 x 292 on TOP,
  intake rev 3: box x -493.5..113.5, y +/-321.5, z 105..527, lift-out space above): keep-out boxes KO_* below;
  near the engine every AUX item stays below the box floor (z < 105) and outside |y| < 321.5 above it;
* service side = -y outer face (gas panel, junction box); radiator at the rear end blowing +x (away from the intake);
* the gas line reaches the v13A casing gas bulkhead (x 14.9, 50.4 deg) UNDER the core and up the +y side close to the
  casing (y <= 65, z <= 62), so it never enters the filter-housing zone.
"""
import math

# ------------------------------------------------------------------ keep-out zones (intake filter housing, other session)
KO = {
    'KO_filter_box_rev3': ((-493.5, 113.5), (-321.5, 321.5), (105.0, 527.0)),
    'KO_filter_service_space': ((-590.0, 210.0), (-400.0, 400.0), (527.0, 887.0)),
    'KO_latch_ring': ((-593.5, 213.5), (-421.5, 421.5), (440.0, 530.0)),
    'KO_exhaust_jet': ((264.0, 664.0), (-150.0, 150.0), (-150.0, 150.0)),
}
FR110_X = (-225.0, 260.0)     # base frame ends (intake/frame rev 3, commit 77736d6); lifting lugs on the cross-member ends at y +/-150..160
BRIDGES_X = ((-170.0, -150.0), (160.0, 180.0))   # skid -> FR-110 -y rail (y -110) bridge brackets, clear of lugs / posts / pedestals

# ------------------------------------------------------------------ combustor gas manifold (replaces the v13A Ø5 ring / Ø0.8 needles / Ø6 feed)
X_RING = 11.7                 # v13A manifold plane (XCC - TS - 6.6)
R_RING = 42.1                 # vaporiser-stick circle (12 x Ø6x0.3 sticks at 15 + 30 k deg)
RING = dict(od=7.0, id=6.0, spec='ring 7 x 0.5 1.4571 (ID 6) at r 42.1, x 11.7')
NEEDLE = dict(n=12, od=2.0, id=1.6, L=15.6, x0=X_RING, x1=27.3, ang0=15.0,
              spec='12 needles 2.0 x 0.2 1.4301 precision tube (ID 1.6), 10 mm into each vaporiser-stick mouth (x 17.3)')
STICK_ID = 5.4
FEED = dict(od=8.0, id=6.5, L_m=0.10, spec='feed 8 x 0.5 1.4571 through the v13A M12x1 bulkhead (bore 8), 7 x 0.5 joggle inside, joins the ring at 60 deg')
BULKHEAD = dict(x=14.9, ang=50.4, r_nut_out=62.8)
TEE_ANG = 60.0

# ------------------------------------------------------------------ external gas line (train outlet -> casing bulkhead), under the core
GAS_LINE = dict(od=15.0, id=13.0, L_m=1.6, K_fittings=6 * 0.35 + 1.0, hose_id=12.0, hose_L_m=0.4,
                spec='1.4571 tube 15 x 1, DIN 2353 / ISO 8434-1 24 deg cone fittings (VOSS, DE); last 0.4 m DN12 stainless braided gas hose '
                     '(Witzenmann, DE) to an 8/15 reducing union on the bulkhead tube')
# path points (x, y, z): train outlet elbow -> inner side of the panel -> down -> along -x -> +y under the casing -> up the +y side
GAS_PATH = [(235.0, -395.0, 150.0), (235.0, -320.0, 150.0), (235.0, -320.0, -110.0), (70.0, -320.0, -110.0),
            (70.0, 64.0, -110.0), (70.0, 64.0, 40.0)]   # crosses under the core between FR-120 (x <= 47.6) and the FR-160 posts (x >= 90)
R_UNION = (80.0, 96.0)        # 8/15 reducing union on the bulkhead tube (along the 50.4 deg bulkhead axis)
GAS_HOSE = [(70.0, 64.0, 40.0), (70.0, 64.0, 50.0), (40.0, 67.6, 74.0), ('rad', 14.9, 50.4, 106.0), ('rad', 14.9, 50.4, 96.0)]

# ------------------------------------------------------------------ gas train on the outer face of the AUX skid (service side -y)
PANEL = dict(x=(-140.0, 315.0), y=(-338.0, -335.0), z=(-120.0, 300.0))
Y_GAS = -395.0                # pipe axis
Z_A, Z_B = -60.0, 150.0       # row A (supply -> regulator, flow -x), row B (SSV1 -> SSV2 -> FCV, flow +x)
X_RISER = -125.0
GAS_TRAIN_KV = [('HV-601 ball valve DN15', 20.0), ('FG-602 filter DN15 20 um', 6.0), ('PCV-605 regulator', None),
                ('XV-611 SSV1 DN15', 4.5), ('XV-612 SSV2 DN15', 4.5), ('piping/fittings DN15', 8.0), ('FCV-620', None)]
FCV_KVS = 1.6                 # Bürkert 2836 class, orifice ~8 mm (confirm Kvs / pressure rating at 4 bar gas)

# ------------------------------------------------------------------ AUX skid (AX-610) - RHS 60 x 40 x 3 like FR-110
SKID = dict(x=(-300.0, 425.0), y=(-460.0, -160.0), z_top=-126.0, h=60.0, w=40.0)
DECK = dict(x=(-300.0, 425.0), y=(-420.0, -200.0), t=3.0)
DECK_HOLES = [(306.0, -395.0, 15.0)]          # (x, y, r): gas inlet hose from below
AV = [(-270.0, -440.0), (-270.0, -180.0), (395.0, -440.0), (395.0, -180.0)]

# ------------------------------------------------------------------ oil module (rear inner deck x > 113.5: no height limit) + front low units
Z_DECK = -123.0
OIL_TANK = dict(x0=125.0, y0=-305.0, dx=175.0, dy=100.0, dz=220.0)          # 3.85 L gross, 3.0 L oil; lid z 97
OIL_PUMP_P = dict(x=150.0, y=-280.0, r=22.5, h=90.0)      # vertical 24 V BLDC motor on the lid, gear pump submerged
OIL_PUMP_S = dict(x=195.0, y=-280.0, r=22.5, h=90.0)      # scavenge gear pump + motor on the lid (suction from the collector)
OIL_FILTER = dict(x=160.0, y=-225.0, r=30.0, h=150.0)     # spin-on 10 um filter + head on the lid
SEPARATOR = dict(x=262.0, y=-250.0, r=40.0, h=130.0)      # coalescing oil-mist separator on the lid (drains back into the tank)
LAMINOVA = dict(x0=-135.0, x1=-15.0, y=-270.0, z=-90.0, r=28.0)              # oil<->glycol tube cooler, horizontal (front, low)
COLLECTOR = dict(x0=-135.0, x1=-75.0, y=-200.0, z=-107.0, r=16.0)            # scavenge drain collector (lowest point)
OIL_MANIFOLD = dict(x=(-55.0, -15.0), y=(-225.0, -195.0), z=(-110.0, -80.0))  # PT-701 / PSL-702 / TE-708 distribution block
LANE_OIL_P = (-188.0, -30.0)    # (y, z) oil pressure lane
LANE_OIL_S = (-188.0, -60.0)    # scavenge lane
LANE_GLY_1 = (-159.0, 20.0)     # radiator -> pump suction (between the skid and FR-110)
LANE_GLY_4 = (-159.0, 45.0)     # oil cooler -> radiator inlet

# ------------------------------------------------------------------ glycol loop
GLYCOL = dict(flow_L_min=2.5, hose_id=8.0, hose_od=15.0, hose_L_m=4.5)
JACKET = dict(turns=8, pitch=10.5, groove_w=8.0, groove_d=3.0, d_mean=92.0)   # G-201 after the D2A lead-out change
RADIATOR = dict(x0=370.0, w=280.0, h=320.0, t=52.0, y0=-455.0, z0=-110.0, area_density_m2_m3=900.0, U_air_W_m2K=40.0, air_m3_h=1300.0)
FAN = dict(x0=318.0, x1=370.0, r=155.0)
GLY_PUMP = dict(x0=-285.0, x1=-155.0, y0=-305.0, y1=-213.0, z1=2.0)         # wet-rotor circulator envelope (ports at the x ends)
EXP_TANK = dict(x0=360.0, x1=430.0, y0=-330.0, y1=-250.0, z0=240.0, z1=340.0)

# ------------------------------------------------------------------ electrical
JB = dict(x=(-300.0, -150.0), y=(-460.0, -340.0), z=(-100.0, 200.0))        # 300 x 150 x 120 steel terminal box, door -y
TRAY = dict(x=(-255.0, 380.0), y=(-330.0, -290.0), z=(-170.0, -140.0))      # cable tray under the deck, between the end cross members
IGN_TRAFO = dict(x=(0.0, 57.0), y=(-300.0, -196.0), z=(-123.0, -63.0))   # on the AUX deck, front (HT lead ~0.8 m under the core)

# ------------------------------------------------------------------ engine-side sensor / port positions (ENG)
CASING_BOSSES = {'PT-521 P2 static tap M8x1': (75.0, 200.0), 'TE-502 T3 TC M8x1': (90.0, 200.0),
                 'buffer-air bleed M8x1 (orifice 2.2)': (105.0, 200.0)}
UV = dict(x=55.0, ang=180.0, r0=55.0, r_tube=150.0, r_end=250.0)          # between sticks 165 / 195 deg
POD_PORTS = {   # name: (x, angle deg, kind)
    'glycol in G1/4': (-244.0, 135.0, 'g14'), 'glycol out G1/4': (-170.5, 135.0, 'g14'),
    'oil jet front M8x1': (-265.0, 90.0, 'm8'), 'oil jet rear M8x1': (-136.0, 90.0, 'm8s'),
    'oil drain front G1/4': (-262.0, 270.0, 'g14'), 'oil drain rear G1/8': (-139.0, 270.0, 'g18'),
    'PT100 front bearing M8x1': (-262.0, 225.0, 'm8'), 'PT100 rear bearing M8x1': (-137.0, 225.0, 'm8s'),
    'VE-011 accelerometer M6 pad': (-250.0, 180.0, 'pad'), 'VE-012 accelerometer M6 pad': (-145.0, 180.0, 'pad'),
    'buffer air G1/8': (-153.0, 210.0, 'g18'), 'stator lead-out (potted)': (-153.5, 90.0, 'lead'),
}
TBOX_D2A = dict(x=(-210.0, -146.0), y=(-26.0, 26.0), z=(55.0, 85.0))       # G-240 moved over the lead-out (was x -232..-168)
GLYCOL_PORTS_D2A = (-244.0, -170.5)                                          # over groove 0 / groove 7 of the 8-turn jacket
JACKET_X1_D2A = -160.0                                                       # jacket rear end (was -148): lead-out gap x -160..-146


def P(x, r, ang_deg):
    a = math.radians(ang_deg)
    return (x, r * math.cos(a), r * math.sin(a))
