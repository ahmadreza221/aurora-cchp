"""GR180 version D2 rotor / turbine / generator (D2R) - shared layout numbers (pure Python, no FreeCAD).

ENG frame, mm: x = engine axis (downstream +), x = 0 at the shaft-tunnel spigot front face, z up (docs/06 section 1).
Used by cad/variant_d/d2r_turbine.py, d2r_rotor.py, d2r_generator.py, d2r_check.py and sim/variant_d/d2r_rotor.py.
Core reference parts: cad_out/v13A/asm_parts (casing ends x 116, rear flange r 39..48, 4 x M5 on PCD 88 at 45/135/225/315 deg).
Pod shell reference: cad_out/variant_d/D-101 / D-102 (d_concept.py): bore r 49, outer r 55, rear plate x -123..-108 (bore r 9).
"""

# ------------------------------------------------------------------ speeds / design point
N_RUN = 115000.0
BAND = (85000.0, 95000.0)

# ------------------------------------------------------------------ core bearings (decisions: 10x22x6 hybrid 15 deg, P4)
BRG = dict(d=10.0, D=22.0, B=6.0)
X_BF, X_BR = 6.8, 100.8                     # core front (locating) / rear (floating, spring) bearing centres
X_GF, X_GR = -266.0, -136.0                 # generator front / rear bearing centres
CART_OD = 28.0                              # SFD cartridge outer diameter (bore 28.0 H6, land 27.80 -> 0.10 radial film)
SFD_C = 0.10                                # squeeze-film radial clearance

# ------------------------------------------------------------------ core rotor (R) - engine shaft profile (x0, x1, radius)
SHAFT = [  # front -> rear
    ('hex AF6 drive (turned corners d6.6)', -56.0, -43.5, 3.0),
    ('M8x1 LH thread', -43.5, -35.5, 4.0),
    ('compressor seat d8 g5', -35.5, 3.3, 4.0),
    ('d10 journal / tie section', 3.3, 103.8, 5.0),
    ('d14 seal runner (4 labyrinth teeth to d15.2)', 103.8, 112.0, 7.0),
    ('d18 turbine stub (heat dam)', 112.0, 133.0, 9.0),
]
SHAFT_NOSE_X = -56.0
COMP = dict(x0=-34.72, x1=3.3, bore_new=8.0, mass=0.1039, x_cg=-9.5, Ip=4.27e-5, It=2.78e-5)   # v13A compressor, bore 7 -> 8 H6
NUT = dict(x0=-41.72, x1=-34.72, AF=13.0)                     # M8x1 LH thin clamp nut
CUP = dict(x0=-70.0, x1=-43.0, r=7.0, socket_AF=7.0, socket_x=(-70.0, -58.0), web=(-58.0, -56.0), hex_AF=6.0)
SHIM = dict(x0=3.3, x1=3.8, ri=5.0, ro=6.5)                   # compressor -> front bearing IR spacer
SLEEVE = dict(x0=9.8, x1=97.8, ri=5.0, ro=8.0)                # clamped body sleeve d16/d10 (17-4PH): realises the 'd16 body'
WHEEL = dict(x_back=133.0, D4=78.0, b4=14.0, D6t=70.0, D6h=21.0, x_exit=169.0, x_nose=175.0, Z=11,
             mass_est=0.45, rim=2.0)                          # bought IN713C turbo wheel, friction-welded to the d18 stub
TUNNEL = dict(x0=0.0, x1=107.3, bore_mid_r=9.0, out_mid_r=11.0, cart_bore_r=14.0, rear_out_r=17.5,
              front_cart=(2.0, 11.0), rear_cart=(95.8, 107.3))
SEAL_F = dict(x0=-0.2, x1=2.8, ri=11.2, ro=12.95, flange_ro=13.95, flange_x=(2.0, 2.8))   # front labyrinth ring round the compressor boss r 10.94

# ------------------------------------------------------------------ turbine (T)
CASING_FACE_X = 116.0
FLANGE_BOLTS = dict(n=4, pcd=88.0, size='M5', ang0=45.0)
SPIDER = dict(x0=95.0, x1=118.0, r_in_wall=(21.25, 22.25), r_out_wall=(35.35, 36.35), flange=(116.0, 118.0, 36.35, 48.0),
              n_struts=7, strut_x=(105.0, 115.0), strut_t=2.5, web_x=(103.0, 105.0), seal_disc_x=(107.3, 112.0), seal_bore_r=7.85)
NOZZLE = dict(Z=17, r_in=56.6, r_out=42.9, x0=135.0, x1=149.0, plate_front=(132.0, 135.0), plate_rear=(149.0, 152.0),
              plate_r=(40.0, 58.0), plate_rear_ri=42.6)
HOUSING = dict(x0=118.0, x1=155.0, shell_ri=70.0, shell_ro=73.0, front_wall=(118.0, 121.0), lip_ri=38.5,
               rear_wall=(152.0, 155.0), rear_ri=44.0, mount_pad=dict(x=(128.0, 142.0), y_out=85.0, z=(-10.0, 10.0)))
SHROUD = dict(x0=149.0, x_exit=169.0, x_end=176.0, clr=0.35, t=3.0, flange=(172.0, 176.0, 52.0), bolts=dict(n=6, pcd=94.0, size='M6'))
EXHAUST_START = dict(x=176.0, ID=2 * (35.0 + 0.35), flange_OD=104.0, bolts='6 x M6 on PCD 94')

# ------------------------------------------------------------------ generator (G)
POD = dict(bore_r=49.0, outer_r=55.0, rear_plate_x=(-123.0, -108.0), rear_plate_bore_r=9.0, shell_x0=-273.0)
GEN = dict(stack=(-239.0, -163.0), stator_od=88.0, stator_id=39.0, slots=12,
           endwind=((-255.0, -239.0), (-163.0, -148.0)), endwind_r=(20.5, 40.0),
           rotor_od=36.0, magnet=(-240.0, -162.0), magnet_r=(10.0, 15.0), sleeve_r=(15.0, 18.0), endcap=3.0,
           jacket=(-256.0, -148.0), jacket_r=(44.0, 49.0), groove_r=46.0,
           front_shield=(-272.0, -258.0), front_cover=(-281.0, -272.0), rear_shield=(-146.0, -123.0))
GSHAFT = [  # generator shaft with integral quill (x0, x1, radius)
    ('M10x0.75 thread (front locknut KM0)', -278.0, -269.0, 5.0),
    ('d10 front journal', -269.0, -263.0, 5.0),
    ('d14 seal runner', -263.0, -257.0, 7.0),
    ('d20 hub', -257.0, -145.0, 10.0),
    ('d14 seal runner', -145.0, -139.0, 7.0),
    ('d10 rear journal', -139.0, -133.0, 5.0),
    ('M10x0.75 thread (rear locknut KM0, seal runner)', -133.0, -128.5, 5.0),
    ('fillet d10 -> d6', -128.5, -126.0, 4.0),
    ('quill waist d6', -126.0, -69.0, 3.0),
    ('shoulder', -69.0, -68.0, 4.05),
    ('crowned hex AF7', -68.0, -59.0, 3.5),
]
QUILL = dict(waist_d=6.0, waist=(-126.0, -69.0), hex_AF=7.0, hex=(-68.0, -59.0), float_mm=0.5)
QUILL_GUARD = dict(x0=-108.0, x1=-74.0, ri=8.5, ro=10.0, flange_r=16.0)
TBOX = dict(x=(-232.0, -168.0), y=(-26.0, 26.0), z=(55.0, 85.0))
GLYCOL_PORTS = (-250.0, -152.0)
