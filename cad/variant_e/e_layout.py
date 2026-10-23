# GR180 version E - master layout (pure Python, no FreeCAD): every axial station, radius and interface used by the
# CAD scripts (cad/variant_e/e_*.py) and by the rotor / thrust model (sim/variant_e/e_rotor.py).
# ENG frame (mm): x = engine axis, + downstream (generator -> compressor -> turbine -> exhaust), x = 0 at the compressor
# impeller TIP (exit centreline), y to the right looking downstream, z up; engine axis at z = 0.
# Numbers come from sim/variant_e/e_cycle.json, e_compressor.json, e_turbine.json, e_combustor.json, e_ducts.json,
# e_pmg.json (rounded to buildable sizes).  Bought parts (wheels, bearings, PMG active parts) are ENVELOPES until the
# supplier drawings arrive.
#
# Air path: plenum -> bellmouth -> impeller -> 17-vane radial diffuser -> 90 deg bend (axisymmetric, no scroll) ->
# 23 deswirl vanes -> annulus r 261..305 -> COOL CASING round the floating hot plenum -> up the can-combustor annulus ->
# dome -> liner -> diffusing transition -> hot plenum -> 19-vane nozzle -> turbine -> shroud/diffuser inlet ring ->
# fabricated 10 deg cone -> 90 deg vaned elbow -> DN450 flange (CHP).
import math

N_RUN = 35000.0                 # rpm (583 Hz, 2-pole PMG)
N_MAX = 35880.0                 # drive / control limit (598 Hz)
N_TRIP = 37800.0                # 108 % overspeed trip (fuel cut)

# ------------------------------------------------------------------ compressor (e_compressor.json)
COMP = dict(D2=270.0, b2=15.5, D1t=173.0, D1h=76.0, x_LE=-81.0, x_nose=-94.0, x_back_rim=11.75, x_hub_back=30.0,
            r_back_seal=35.0,               # back-face labyrinth on the slinger ring OD (net thrust stays forward, e_rotor.py)
            Z='9+9', beta2b=-38.0, eps=0.45,
            mass=5.6, x_cg=-18.0, Ip=0.032, It=0.020,            # Al 2618 wheel (est; the CAD solid is a blade-filled envelope)
            diffuser=dict(r3=146.0, r4=236.0, b3=14.8, Z=17), bend=dict(r_in=236.0, annulus=(261.0, 305.0), Z_deswirl=23, x_deswirl=(60.0, 100.0)))
COMP_CASE = dict(x_front=-150.0, bellmouth_r=300.0, flange_r=320.0, outer_r=330.0, rear_flange=(100.0, 115.0, 400.0))

# ------------------------------------------------------------------ core shaft (one piece with the friction-welded turbine stub)
SHAFT = [('hex_AF24_crowned', -140.0, -116.0, 12.8),    # quill drive (generator torque enters here, never through the nut)
         ('thread_M33x2', -116.0, -94.0, 15.5),
         ('compressor_seat_d40', -94.0, 30.0, 20.0),
         ('slinger_seat_d40', 30.0, 45.0, 20.0),
         ('front_journal_d40', 45.0, 75.0, 20.0),
         ('body_d40', 75.0, 197.5, 20.0),
         ('rear_journal_d40', 197.5, 212.5, 20.0),
         ('seal_runner_d50', 212.5, 240.0, 25.0),
         ('heat_dam_d50_30', 240.0, 248.0, 25.0)]      # hollow d50/30 stub, friction weld to the wheel hub at x 248
SLEEVE = dict(x0=75.0, x1=197.5, ro=30.0, ri=20.0)      # clamped 17-4PH spacer d60/40
NUT = dict(x0=-112.0, x1=-94.0, OD=56.0, mass=0.30, preload_kN=60.0)
SLINGER = dict(x0=30.0, x1=45.0, OD=70.0, mass=0.25)
X_BF = 60.0                     # front tandem pair centre (2 x 7008-E, x 45..75)
X_BR = 205.0                    # rear floating bearing (7008-C, x 197.5..212.5)
BRG = dict(d=40.0, D=68.0, B=15.0, C_dyn=20000.0, C0=10500.0, n_oil_limit=45000.0, model='FAG HCB7008-C/E-T-P4S (or SKF 7008 CE/HCP4A, GMN HY, NSK 7008 hybrid)')
CART = dict(OD=84.0, land=12.0, clearance=0.12, k_oring=3.0e6, bore=84.24)   # SFD cartridge (O-ring centred)
BH = dict(x0=45.0, x1=235.0, front_flange_r=165.0, body_r=100.0, rear_flange_r=150.0, x_rear_flange=215.0, seal_bore_r=25.4)

# ------------------------------------------------------------------ turbine (e_turbine.json)
TURB = dict(D4=288.0, b4=30.0, D6t=232.0, D6h=75.0, Lz=92.0, Z=12, x_back=250.0, x_exit=342.0, x_nose=360.0,
            mass=15.0, x_cg=276.0, Ip=0.105, It=0.066,           # cast IN713LC wheel (est; CAD = blade-filled envelope)
            r_back_seal=27.0,                                    # piston-ring seal on the d50 seal runner (thrust model)
            nozzle=dict(Z=19, r_in=206.0, r_out=158.0, b=30.0, alpha3=75.4, throat=12.0, x=(247.0, 283.0), r_plate=(150.0, 214.0)),
            clearance=0.55)
HEAT_SHIELD = dict(x=(235.0, 247.0), r=(27.0, 214.0))
SHROUD = dict(x0=280.0, x1=495.0, r_out=140.0, half_angle=5.0, flange=(283.0, 295.0, 214.0))
X_CAN = 285.0
HOT = dict(r=(214.0, 345.0), x=(140.0, 430.0), wall=3.0, inlet_r=140.0)            # floating hot plenum; round top inlet d280 (transition d274 + piston ring)
COOL_CASE = dict(r_in=372.0, t=8.0, x=(115.0, 480.0), front_wall_r=305.0, rear_bore_r=141.0, stub_top=440.0)

# ------------------------------------------------------------------ can combustor (e_combustor.json) - vertical, axis at x = X_CAN, y = 0
CAN = dict(casing_OD=323.9, casing_t=7.1, z_flange_lo=440.0, z_flange_hi=1180.0, flange_OD=445.0, flange_t=20.0, cover_t=25.0,
           liner_D=210.0, liner_t=1.5, z_liner_exit=520.0, liner_L=588.0, z_transition_end=320.0, transition_D_out=270.0,
           holes=dict(primary=(8, 23.3, 1030.0), secondary=(12, 17.4, 925.0), dilution=(10, 28.0, 720.0)),
           flange='DN300 PN10 EN 1092-1 (OD 445, PCD 400, 12 x M20)')

# ------------------------------------------------------------------ exhaust (e_ducts.json)
EXH = dict(x0=485.0, x1=1475.0, r_in=128.0, r_out=214.0, t=3.0, collar=(485.0, 525.0), elbow_r=219.0, elbow_R=450.0, elbow_t=6.3,
           flange=dict(name='DN450 PN6 EN 1092-1 (verify: OD 640, PCD 585, 16 x M20)', OD=640.0, t=22.0))

# ------------------------------------------------------------------ generator pod (e_pmg.json)
GEN = dict(stack=(-710.0, -520.0), rotor_OD=120.0, magnet=(80.0, 108.0), endring=12.0, stator_ID=125.0, stator_OD=240.0,
           endturn=85.0, body_r=40.0, step_r=30.0, journal_r=20.0, x_g=-615.0, jacket_r=(120.0, 140.0), housing_r=(140.0, 160.0))
X_GF = -830.0                   # generator front bearing (locating, 7008-E)
X_GR = -400.0                   # generator rear bearing (floating, 7008-C + wave spring)
GSHAFT = [('speed_wheel_stub_d30', -880.0, -860.0, 15.0), ('thread_M36x1.5_KM7', -860.0, -837.5, 17.5),
          ('front_journal_d40', -837.5, -822.5, 20.0), ('seal_step_d60', -822.5, -740.0, 30.0),
          ('magnet_body_d80', -740.0, -490.0, 40.0), ('seal_step_d60', -490.0, -407.5, 30.0),
          ('rear_journal_d40', -407.5, -392.5, 20.0), ('collar_d56', -392.5, -385.0, 28.0)]
QUILL = dict(flange=(-385.0, -373.0, 35.0), waist=(-373.0, -165.0), waist_d=30.0, socket=(-165.0, -117.0), socket_OD=56.0,
             hex_engage=(-140.0, -117.0), float_mm=1.0, bolts='6 x M8 12.9 + 2 dowels d6 on PCD 52')
POD = dict(x=(-900.0, -370.0), OD=320.0, end_bell_front=(-900.0, -800.0), end_bell_rear=(-435.0, -370.0),
           guard=dict(x=(-370.0, -98.0), OD=76.0, ID=66.0), feet_x=(-770.0, -470.0))

# ------------------------------------------------------------------ intake plenum (e_ducts.json)
PLENUM = dict(x=(-2060.0, -150.0), y=(-950.0, 950.0), z=(-650.0, 650.0), wall=3.0, filter_opening=(1830.0, 1830.0), bellmouth_hole_r=322.0)

# ------------------------------------------------------------------ frame / supports
FRAME = dict(z_top=-650.0, rhs=(200.0, 100.0, 6.3), x=(-2100.0, 2000.0), y_rail=550.0, av_mounts=8, av_h=100.0)
AXIS_ABOVE_FLOOR = 960.0

OP_RANGE = (0.55 * N_RUN, 1.08 * N_RUN)
