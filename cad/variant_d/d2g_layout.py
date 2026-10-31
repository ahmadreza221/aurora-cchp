"""GR180 version D2 - generator pod buildable detail (d2g, 2026-10-23): numbers shared by cad/variant_d/d2r_generator.py
and sim/variant_d/d2g_joints.py.  ENG frame mm (x = engine axis downstream, z up).  Pure Python.

Simplified pod = 3 housing parts instead of 6:
  G-200 housing (cup: shell + jacket bore + integral rear wall with the rear bearing seat, strut / fairing threads)
  G-202 front cover (end bell: front bearing seat, oil / sensor ports, access plug; replaces end shield + cover + nose cap)
  G-201 glycol jacket sleeve (helical groove, stator shrunk in)
Kept interfaces: OD 110 at the FR-170 cradle (x -220..-190) and at the intake lip seal (x -130..-128), rear face x -108
(3 INT-115 strut roots M6 at r 51.2 / 90-210-330 deg, 3 INT-120 fairing M4 at r 45.25 / 30-150-270 deg), quill socket on
the engine-shaft crowned AF6 hex, AUX port positions where they fit (moved ports listed in MOVED_PORTS).
"""
import math

# ------------------------------------------------------------------ housing G-200 (Al 6082-T6, bar d130 x 160)
H = dict(x0=-260.0, x1=-108.0, r_out=55.0,
         flange=(-260.0, -252.0, 64.0),                 # front flange x, r_out (OD 128)
         bore1=(-260.0, -165.0, 49.0),                  # d98 H7: jacket seat
         bore2=(-165.0, -146.0, 48.0),                  # d96 H7: jacket rear O-ring land + lead-out chamber
         relief=(-146.0, -144.5, 10.5),
         seal_r=(-144.5, -141.5, 7.85),                 # rear seal spacer labyrinth
         drain_space=(-141.5, -140.0, 14.0),
         cart=(-140.0, -130.5, 14.0),                   # rear SFD cartridge bore d28 H6
         collar_seal=(-130.5, -124.0, 7.85),            # collar labyrinth
         quill_bore=(-124.0, -116.0, 9.0),
         guard_cb=(-116.0, -108.0, 10.0),               # d20 H7 counterbore for the quill guard tube
         pocket=(-123.0, -108.0, 20.0, 40.0),           # rear-face lightening pocket r 20..40, 15 deep
         lead_slot=(-157.5, -149.5, 12.0),              # x0, x1, half width (top, through the wall)
         pcd_front=120.0)
STRUT_ROOTS = dict(r=51.2, ang=(90.0, 210.0, 330.0), thread='M6', depth=12.0)
FAIRING_HOLES = dict(r=45.25, ang=(30.0, 150.0, 270.0), thread='M4', depth=6.0)

# ------------------------------------------------------------------ front cover G-202 (Al 6082-T6, bar d130 x 32)
C = dict(x0=-286.0, x_flange=(-264.0, -260.0), x_spigot=(-260.0, -258.0), r_out=55.0, r_flange=64.0, r_spigot=49.0,
         plug=(-286.0, -282.0, 8.0),                    # M16x1.5 access plug (rotor turning / Hall-free check)
         chamber=(-282.0, -271.5, 11.5),                # front bearing chamber (locknut d18 inside)
         cart=(-271.5, -262.0, 14.0),                   # front SFD cartridge bore d28 H6
         seal_r=(-262.0, -258.0, 7.85),
         face_oring_groove=(51.3, 53.9, 1.30))          # r_in, r_out, depth in the flange rear face (x -260)
FLANGE_HOLES = dict(pcd=120.0, screws=(0, 60, 120, 180, 240, 300), dowels=(30, 210), jacks=(150, 330))

# ------------------------------------------------------------------ jacket G-201 (Al 6082-T6, tube d100/80 or bar d100)
J = dict(x0=-256.0, x1=-160.0, r_in=44.0, r_out1=49.0, r_out2=48.0, x_step=-165.0,
         turns=8, pitch=10.5, groove_w=8.0, groove_d=3.0, x_first=-248.0,
         oring_front=(-253.6, -250.0, 2.05), oring_rear=(-164.4, -160.8, 2.05))

# ------------------------------------------------------------------ SFD cartridge G-230 (identical front / rear), local u from the lip end
CART = dict(L=9.5, r_out=13.9, r_bore=11.0, r_lip=9.6, lip=1.0, grooves=((1.0, 3.4), (6.0, 8.4)), groove_r=12.45,
            feed_u=4.7, slot_w=3.0, slot_d=0.8)
CART_FRONT_U0 = -271.5      # lip end x, u grows towards +x (lip in front)
CART_REAR_U0 = -130.5       # lip end x, u grows towards -x (lip at the rear)
X_GF, X_GR = -266.0, -136.0

# ------------------------------------------------------------------ ports (x, angle deg, kind) - AUX positions kept where possible
PORTS = {
    'glycol in G1/4':            (-244.0, 135.0, 'g14', 'H'),
    'glycol out G1/4':           (-170.5, 135.0, 'g14', 'H'),
    'oil jet rear M8x1':         (-136.0, 90.0, 'm8', 'H'),
    'oil drain rear G1/8':       (-141.0, 270.0, 'g18', 'H'),
    'PT100 rear bearing M8x1':   (-137.0, 225.0, 'pt', 'H'),
    'VE-012 accelerometer M6':   (-145.0, 180.0, 'pad', 'H'),
    'buffer air G1/8':           (-153.0, 210.0, 'g18', 'H'),
    'oil jet front M8x1':        (-276.0, 90.0, 'm8', 'C'),
    'oil drain front G1/8':      (-277.0, 270.0, 'g18', 'C'),
    'PT100 front bearing M8x1':  (-276.0, 225.0, 'pt', 'C'),
    'VE-011 accelerometer M6':   (-277.0, 180.0, 'padc', 'C'),
    'Hall speed sensor M8x1':    (-277.0, 0.0, 'hall', 'C'),
}
BOSS = {'g14': (10.0, 61.0), 'g18': (7.0, 60.0), 'm8': (6.0, 60.0), 'pt': (6.0, 60.0), 'pad': (10.0, 58.0), 'padc': (8.0, 58.0), 'hall': (6.0, 60.0)}  # (boss r, top radius)
MOVED_PORTS = {'oil jet front M8x1': 'x -265 -> -276 (now on the front cover G-202)',
               'oil drain front': 'G1/4 at x -262 -> G1/8 at x -277 (front cover)', 'PT100 front bearing M8x1': 'x -262 -> -276 (front cover)',
               'VE-011 accelerometer M6': 'x -250 -> -277 (front cover, pad d16)', 'oil drain rear G1/8': 'x -139 -> -141 (hole into the drain space)',
               'VE-012 accelerometer M6': 'pad d26 -> d20',
               'Hall speed sensor': 'G-203 boss x -276 / gland in the D-102P cap x -284 -> M8x1 sensor port x -277 at 0 deg (+y) on G-202, reads 2 magnets in the locknut',
               'terminal box': 'z 55..85 -> 55..95 (40 mm tall for the M25 EMC gland), x -210..-146 unchanged, gland on the front face at z 75'}
LEAD_OUT_X = -153.5

# ------------------------------------------------------------------ terminal box (milled Al 6082)
PIN_R = 12.75              # anti-rotation pin radius (front: shoulder x -271.5 in G-202, rear: shoulder x -130.5 in G-200)
TBOX = dict(x=(-210.0, -146.0), y=(-26.0, 26.0), z_gasket=(55.0, 56.0), z_body=(56.0, 92.0), z_lid=(93.0, 96.0), wall=3.0, floor_top=60.0,
            screws=((-200.0, 12.0), (-200.0, -12.0), (-162.0, 12.0), (-162.0, -12.0)),        # 4 x M4 floor screws into the housing
            lid_screws=((-204.0, 20.0), (-204.0, -20.0), (-152.0, 20.0), (-152.0, -20.0)),   # 4 x M3 into the corner columns
            gland_power=(0.0, 76.0, 'M25x1.5'), gland_signal=(-180.0, 76.0, 'M16x1.5'))   # power: front face (y, z); signal: +y side wall (x, z)

# ------------------------------------------------------------------ rotor-side small parts
LOCKNUT = dict(x0=-275.0, x1=-269.0, r_out=9.0, thread='M10x0.75')   # OD 18 so it passes the cartridge lip (r 9.6)
FRONT_SPACER = dict(x0=-270.5, x1=-269.0, r_in=9.6, r_out=11.0)     # 1.5 mm ground shim between the cartridge lip and the front OR
WAVE_SPRING = dict(x0=-133.0, x1=-131.5, r_in=9.6, r_out=11.0, F_N=60.0)
QUILL_GUARD = dict(x0=-116.0, x1=-64.0, r_in=8.5, r_out=10.0)
