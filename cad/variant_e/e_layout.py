# GR180 version E - master layout (pure Python, no FreeCAD): every axial station, radius and interface used by the
# CAD scripts (cad/variant_e/e_*.py) and by the rotor / thrust model (sim/variant_e/e_rotor.py).
# ENG frame (mm): x = engine axis, + downstream (generator -> compressor -> turbine -> exhaust), x = 0 at the compressor
# impeller TIP (exit centreline), y to the right looking downstream, z up; engine axis at z = 0.
# Numbers come from sim/variant_e/e_cycle.json, e_compressor.json, e_turbine.json, e_combustor.json, e_ducts.json,
# e_pmg.json (rounded to buildable sizes).  Bought parts (wheels, bearings, PMG active parts) are ENVELOPES until the
# supplier drawings arrive.
import math

N_RUN = 35000.0                 # rpm (583 Hz, 2-pole PMG)
N_MAX = 35880.0                 # drive / control limit (598 Hz)
N_TRIP = 37800.0                # 108 % overspeed trip (fuel cut)

# ------------------------------------------------------------------ compressor (e_compressor.json)
COMP = dict(D2=270.0, b2=15.5, D1t=173.0, D1h=76.0, x_LE=-81.0, x_nose=-94.0, x_back_rim=11.5, x_hub_back=30.0,
            r_back_seal=35.0,               # back-face labyrinth on the impeller hub boss (net thrust stays forward, e_rotor.py)
            Z='9+9', beta2b=-38.0, eps=0.45,
            mass=5.6, x_cg=-18.0, Ip=0.032, It=0.020,            # Al 2618 wheel envelope (est from the CAD volume)
            diffuser=dict(r3=146.0, r4=236.0, b3=14.8, Z=17), scroll=dict(r_c=300.0, D_exit=146.0, D_pipe=254.0))
COMP_CASE = dict(x_front=-150.0, x_rear=20.0, r_shroud_LE=86.5, scroll_OD=700.0)

# ------------------------------------------------------------------ core shaft (one piece with the friction-welded turbine stub)
# (name, x0, x1, radius)  - solid sections; the clamped spacer sleeve is listed separately
SHAFT = [('hex_AF24_crowned', -140.0, -116.0, 12.8),    # quill drive (generator torque enters here, never through the nut)
         ('thread_M33x2', -116.0, -94.0, 15.5),
         ('compressor_seat_d40', -94.0, 30.0, 20.0),
         ('slinger_seat_d40', 30.0, 45.0, 20.0),
         ('front_journal_d40', 45.0, 75.0, 20.0),
         ('body_d40', 75.0, 197.5, 20.0),
         ('rear_journal_d40', 197.5, 212.5, 20.0),
         ('seal_runner_d50', 212.5, 240.0, 25.0),
         ('heat_dam_d50_30', 240.0, 250.0, 25.0)]      # hollow d50/30 stub, friction weld at x ~248
SLEEVE = dict(x0=75.0, x1=197.5, ro=30.0, ri=20.1)      # clamped 17-4PH spacer d60/40.2
NUT = dict(x0=-112.0, x1=-94.0, OD=56.0, mass=0.30, preload_kN=60.0)
SLINGER = dict(x0=30.0, x1=45.0, OD=62.0, mass=0.18)
X_BF = 60.0                     # front tandem pair centre (2 x 7008-E, x 45..75)
X_BR = 205.0                    # rear floating bearing (7008-C, x 197.5..212.5)
BRG = dict(d=40.0, D=68.0, B=15.0, C_dyn=20000.0, C0=10500.0, n_oil_limit=45000.0, model='FAG HCB7008-C/E-T-P4S (or SKF 7008 CE/HCP4A, GMN HY, NSK 7008 hybrid)')
CART = dict(OD=84.0, land=12.0, clearance=0.12, k_oring=3.0e6)   # SFD cartridge (O-ring centred)

# ------------------------------------------------------------------ turbine (e_turbine.json)
TURB = dict(D4=288.0, b4=30.0, D6t=232.0, D6h=75.0, Lz=92.0, Z=12, x_back=250.0, x_exit=342.0, x_nose=360.0,
            mass=15.0, x_cg=276.0, Ip=0.105, It=0.066,           # cast IN713LC wheel envelope (est, solid scalloped hub)
            r_back_seal=27.0,                                    # piston-ring seal on the d50 seal runner (thrust model)
            nozzle=dict(Z=19, r_in=206.0, r_out=158.0, b=30.0, alpha3=75.4, throat=12.0))
HOT = dict(plenum_r=(215.0, 335.0), plenum_x=(232.0, 330.0), transition_xy=(320.0, 160.0))
COOL_CASE = dict(OD=880.0, t=8.0, x_front=220.0, x_rear=470.0, top_port_D=323.9)   # cool pressure casing (compressor air round the hot parts)

# ------------------------------------------------------------------ can combustor (e_combustor.json) - vertical, axis at x = X_CAN, y = 0
X_CAN = 290.0
CAN = dict(casing_OD=323.9, casing_t=7.1, z_base=440.0, z_top=1320.0, liner_D=210.0, liner_L=588.0, z_liner_exit=520.0,
           dome_z=1180.0, flange='DN300 PN10 EN 1092-1 (OD 445, PCD 400, 12 x M20)')

# ------------------------------------------------------------------ exhaust (e_ducts.json)
EXH = dict(x0=342.0, D_in=232.0, D_out=420.0, L=1074.0, elbow_D=438.0, elbow_R=660.0, flange='DN450 PN6')
EXH['x1'] = EXH['x0'] + EXH['L']

# ------------------------------------------------------------------ generator pod (e_pmg.json)
GEN = dict(stack=(-710.0, -520.0), rotor_OD=120.0, magnet=(80.0, 108.0), endring=12.0, stator_ID=125.0, stator_OD=240.0,
           endturn=85.0, body_r=40.0, step_r=30.0, journal_r=20.0, x_g=-615.0)
X_GF = -830.0                   # generator front bearing (locating, 7008-E)
X_GR = -400.0                   # generator rear bearing (floating, 7008-C + wave spring)
GSHAFT = [('speed_wheel_stub_d30', -880.0, -860.0, 15.0), ('thread_M36x1.5_KM7', -860.0, -837.5, 17.5),
          ('front_journal_d40', -837.5, -822.5, 20.0), ('seal_step_d60', -822.5, -740.0, 30.0),
          ('magnet_body_d80', -740.0, -490.0, 40.0), ('seal_step_d60', -490.0, -407.5, 30.0),
          ('rear_journal_d40', -407.5, -392.5, 20.0), ('collar_d56', -392.5, -385.0, 28.0)]
QUILL = dict(flange=(-385.0, -373.0, 35.0), waist=(-373.0, -165.0), waist_d=30.0, socket=(-165.0, -116.0), socket_OD=56.0,
             hex_engage=(-140.0, -116.0), float_mm=1.0, bolts='6 x M8 12.9 + 2 dowels d6 on PCD 52')
POD = dict(x_front=-900.0, x_rear=-370.0, OD=320.0, guard=dict(x0=-370.0, x1=-100.0, OD=76.0, ID=66.0))

# ------------------------------------------------------------------ intake plenum (e_ducts.json)
PLENUM = dict(x0=-2060.0, x1=-150.0, y=(-950.0, 950.0), z=(-650.0, 650.0), filter_opening=(1830.0, 1830.0), wall=3.0)

# ------------------------------------------------------------------ frame / supports
FRAME = dict(z_top=-760.0, rhs=(200.0, 100.0, 6.3), x=(-2100.0, 1900.0), y_rail=550.0, av_mounts=8)
AXIS_ABOVE_FLOOR = 1000.0

BAND = (0.15 * N_RUN, 0.95 * N_RUN)   # no lateral mode allowed inside 15-95 % ... checked as 'outside the operating range 55-108 %'
OP_RANGE = (0.55 * N_RUN, 1.08 * N_RUN)
