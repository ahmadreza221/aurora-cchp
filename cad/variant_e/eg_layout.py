"""GR180 version E - detailed self-built high-speed PM generator (EG, 2026-10-24): every number shared by the CAD builder
(cad/variant_e/eg_generator.py), the checks (eg_check.py) and the analyses (sim/variant_e/eg_*.py).  Pure Python.

ENG frame (mm): x = engine axis, + downstream (generator -> compressor), x = 0 at the compressor impeller tip, z up.
The generator sits in front of the compressor inside the intake plenum; its rear (compressor) end carries the d30 quill
whose AF24 socket slides on the crowned hex of the core-shaft nose (e_layout.QUILL - unchanged).

Electromagnetic design (sim/variant_e/eg_em.py, FEM-verified):
  2-pole surface PM, 35,000 rpm, 583.3 Hz; Sm2Co17 ring (parallel / diametral magnetisation) 74/106 x 272 on a 1.5 mm CuCr1Zr screen, under a 7 mm
  hoop-wound carbon sleeve (rotor OD 120, 220 m/s), 3.0 mm mechanical gap, 24-slot stator 126/262 x 270 of 0.10 mm NO10
  bonded laminations, 24 open slots, double-layer lap winding 10/12 pitch, 2 turns / coil (form-wound diamond coils of
  compacted rectangular Litz 0.20 mm, one conductor per turn = transposed by construction), 2 parallel paths -> 8 series
  turns / phase, VPI class H.
"""
import math

N_RUN = 35000.0
F_EL = N_RUN / 60.0                       # 2-pole -> 583.3 Hz

# ------------------------------------------------------------------ electromagnetic cross-section (mm)
EM = dict(
    rotor_OD=120.0,            # over the CFRP sleeve (ground)
    sleeve_t=7.0,              # T700S/T800S hoop-wound carbon / high-Tg epoxy
    magnet_OD=106.0, magnet_ID=74.0,   # Sm2Co17 ring, 16 mm thick (nominal; OD ground with the 1:500 press-fit taper)
    shield_t=1.5,              # CuCr1Zr eddy-current screen sleeve 71/74 shrunk on the steel shaft (diode-bridge 6f / 12f harmonics)
    magnet_L=272.0,            # stack + 1 mm overhang per end
    L_end_fringe=4.0,          # 3D: effective length = stack + 4 mm (end fringing minus magnet-end leakage to the shaft; +/-2 % EMF)
    gap=3.0,                   # mechanical (sleeve OD to stator bore)
    bore=126.0, stator_OD=262.0, stack=270.0,
    slots=24, slot_shape='open_rect',
    slot_w=8.6, wedge_h=3.8, slot_depth=37.0,   # open parallel-sided slot: form-wound rectangular litz, glass-epoxy wedge in 2 dovetail notches
    pitch=10, turns_coil=2, paths=2, layers=2,
    lam='NO10', lam_t=0.10, stack_factor=0.95,
    Br20=1.10, alpha_Br=-0.00035, mu_r=1.05,          # Sm2Co17 minimum Br (typ. 1.12): VACOMAX 240 HR / YXG-32H class
    sigma_SmCo=1.18e6, sigma_shaft20=4.5e6)
EM['N_ph'] = EM['turns_coil'] * EM['slots'] // 3 // EM['paths']   # series turns per phase (per path)


def em_geom(**over):
    """dict for the FEM mesher (eg_fem2d.build_mesh)"""
    g = dict(rotor_OD=EM['rotor_OD'], magnet_OD=EM['magnet_OD'], magnet_ID=EM['magnet_ID'], bore=EM['bore'],
             stator_OD=EM['stator_OD'], slots=EM['slots'], slot_shape=EM['slot_shape'], slot_w=EM['slot_w'],
             wedge_h=EM['wedge_h'], slot_depth=EM['slot_depth'], shield_t=EM['shield_t'])
    g.update(over)
    return g

# ------------------------------------------------------------------ winding (rewind-shop spec, sim/variant_e/eg_em.py)
# 24 form-wound diamond coils, 2 turns each, one compacted rectangular Litz conductor per turn; 4 conductors stacked
# radially per slot (2 per layer); open slot 8.6 x 37.
WIND = dict(
    strands=1260, strand_d=0.20, strand_od=0.226,        # grade-2 enamel, thermal class 200 (polyesterimide + polyamide-imide)
    construction='7 x 180 x 0.20 (180-strand bunches, 7 bunches rope-laid, compacted), lay 30 / 60 mm',
    bare_w=7.30, bare_h=7.65,                            # compacted rectangle (tangential x radial), Cu fill 0.71
    ins_w=7.70, ins_h=8.05,                              # + polyimide tape 2 x 25 um half-lap + glass-yarn serving
    liner=0.31,                                          # Nomex-Kapton-Nomex (NKN) 0.31 slot liner (ground wall)
    separator=0.50,                                      # NKN 0.5 between the layers (+ 2 slot PT100 positions)
    wedge_t=3.0,                                         # glass-epoxy EP GC 203 (IEC 60893) wedge in dovetail notches
    end_straight=12.0, end_angle_deg=32.0,               # straight extension out of the slot, crossing angle of the diamond
    lead_end='front',                                    # series / parallel connections + 6 leads on the front end winding
)
WIND['Cu_mm2'] = WIND['strands'] * math.pi / 4 * WIND['strand_d'] ** 2


def conductor_radii():
    """mean radius of the 4 conductors in a slot (mm), top layer first"""
    r = EM['bore'] / 2 + EM['wedge_h'] + 0.2                 # wedge + top filler
    out = []
    for k in range(4):
        if k == 2:
            r += WIND['separator']
        out.append(r + WIND['ins_h'] / 2)
        r += WIND['ins_h']
    return out

# ==================================================================== mechanical layout (ENG x, mm)
# Re-entrant end-bell hubs: the bearings sit inside the end-winding envelope (short rotor, bearing span 385 mm).
# Rear bearing kept at x -400 and the quill socket / core hex unchanged (e_layout.QUILL socket -165..-117, hex -140..-117).
X_GR = -400.0                       # rear (floating) bearing centre, 7008-C + 300 N wave spring
X_SR = -457.5                       # stator stack rear face  (= X_GR - 57.5)
X_SF = X_SR - EM['stack']           # stator stack front face -727.5
X_GF = X_SF - 57.5                  # front (locating) bearing centre, 7008-E: -785.0
EW_OVER = 88.2                      # end-winding overhang from the stack faces (eg_em.json)
BRG = dict(d=40.0, D=68.0, B=15.0, model='FAG HCB7008-E/C-T-P4S hybrid (or SKF 7008 CE/HCP4A, GMN HY S 7008, NSK 7008 hybrid, ZWZ / LYC hybrid)')

# rotor (x0, x1, r) - generator shaft 42CrMo4 QT, one piece
ROT = dict(
    magnets=(X_SF - 1.0, X_SR + 1.0), endring_L=12.0, endring_mat='1.4404 (non-magnetic), balance planes (radial holes d4, <= 3 deep)',
    sleeve=(X_SF - 13.0, X_SR + 13.0), screen=(X_SF - 13.0, X_SR + 13.0),
    shaft=[('front_end_thread_M35x1.5', -812.0, -800.0, 17.5), ('speed_wheel_seat_d38', -800.0, -792.5, 19.0), ('front_journal_d40', -792.5, -777.5, 20.0),
           ('front_seal_land_d50', -777.5, -741.0, 25.0), ('magnet_body_d71', -741.0, -444.0, 35.5), ('rear_seal_land_d50', -444.0, -407.5, 25.0),
           ('rear_journal_d40', -407.5, -392.5, 20.0), ('rear_thread_M35x1.5', -392.5, -380.5, 17.5),
           ('relief_d32', -380.5, -378.5, 16.0), ('quill_taper_1to10_d33_30.6', -378.5, -354.5, 16.5)],
    taper=dict(x_large=-378.5, x_small=-354.5, d_large=33.0, d_small=30.6, ratio='1:10 on diameter', pull_bolt='ISO 4762 M12x1.25 x 45 12.9, 60 kN'),
    nut=dict(name='precision lock nut M35x1.5, OD 52, B 12, 2 radial clamping screws (Spieth MSF 35x1.5 (DE) / SKF KMD 7 class)', OD=52.0, B=12.0,
             x_front=(-812.0, -800.0), x_rear=(-392.5, -380.5)),
    speed_wheel=dict(x=(-800.0, -792.5), OD=60.0, teeth='4 teeth + 1 phase notch, 1.4057 QT'),
)
QUILL_EG = dict(hub=(-378.5, -344.5), hub_OD=56.0, waist=(-344.5, -165.0), waist_d=30.0, bore_d=19.0, socket=(-165.0, -117.0), socket_OD=56.0,
                hex_engage=(-140.0, -117.0), float_mm=1.0, mat='34CrNiMo6 QT, waist shot-peened, socket rotary-broached + plasma nitrided')

# end bells (Al 6082-T6), hubs re-entrant
EB = dict(front=dict(disk=(X_SF - 98.0 - 14.0, X_SF - 98.0), hub_nose=X_SF - 13.0 - 6.0, cap=(X_SF - 112.0 - 12.0, X_SF - 112.0)),
          rear=dict(disk=(X_SR + 98.0, X_SR + 98.0 + 14.0), hub_nose=X_SR + 13.0 + 6.0),
          hub_r=52.0, hub_bore_cart=42.12, spigot_front_r=145.0, spigot_rear_r=143.0, spigot_L=14.0, flange_r=165.0,
          air_holes=dict(n=12, d=22.0, r=115.0), ir_port_r=58.0)
# housing (Al 6082-T6 thick tube): bore 290 H7 front + jacket seat, shoulder to 286 H7 at the rear (jacket stop)
HOUS = dict(x=(EB['front']['disk'][1], EB['rear']['disk'][0]), r_out=165.0, bore_front_r=145.0, bore_rear_r=143.0, x_shoulder=-422.5,
            bolts=dict(n=16, size='M10', pcd=310.0, helicoil='M10 x 1.5D'), dowels=2)
JACK = dict(x=(-762.5, -422.5), r_in=EM['stator_OD'] / 2, r_groove=137.0, r_out=145.0, channel=(-742.5, -442.5), groove_w=18.0, groove_d=8.0, land=5.0,
            starts=2, oring_lands=((-762.5, -742.5), (-442.5, -422.5)), shrink_interference=(0.18, 0.24))
GUARD = dict(x=(EB['rear']['disk'][1], -98.0), OD=76.0, ID=66.0, flange_r=60.0, flange_t=10.0, vents=4)
TBOX = dict(x=(-820.0, -690.0), y=(-100.0, 100.0), z=(HOUS['r_out'], 300.0), window=(-815.0, -770.0, 30.0))
SADDLE = dict(x=(-660.0, -405.0), w=80.0, z_floor=-647.0, cradle_r=HOUS['r_out'], base=(-1160.0, -190.0))
BLOWER = dict(x=(-1150.0, -915.0), y=(-150.0, 150.0), z=(-150.0, 150.0), duct_d=80.0, outlet_z=100.0)
HOOD = dict(x=(EB['front']['disk'][0] - 40.0, EB['front']['disk'][0]), r=138.0, r_in=66.0, screw_r=124.0)

# values for cad/variant_e/e_layout.py when GEN_DETAILED = True (e_rotor.py format)
E_GEN = dict(stack=(X_SF, X_SR), rotor_OD=EM['rotor_OD'], magnet=(EM['magnet_ID'], EM['magnet_OD']), endring=12.0, stator_ID=EM['bore'],
             stator_OD=EM['stator_OD'], endturn=EW_OVER, body_r=35.5, step_r=25.0, journal_r=20.0, x_g=0.5 * (X_SF + X_SR),
             jacket_r=(EM['stator_OD'] / 2, 145.0), housing_r=(145.0, HOUS['r_out']))
E_GSHAFT = [(n, x0, x1, r) for (n, x0, x1, r) in ROT['shaft']]
E_POD = dict(x=(HOOD['x'][0], EB['rear']['disk'][1]), OD=2 * HOUS['r_out'], end_bell_front=EB['front']['disk'], end_bell_rear=EB['rear']['disk'],
             guard=dict(x=GUARD['x'], OD=GUARD['OD'], ID=GUARD['ID']), feet_x=SADDLE['x'])
E_QUILL = dict(flange=(QUILL_EG['hub'][0], QUILL_EG['hub'][1], QUILL_EG['hub_OD'] / 2), waist=QUILL_EG['waist'], waist_d=QUILL_EG['waist_d'],
               socket=QUILL_EG['socket'], socket_OD=QUILL_EG['socket_OD'], hex_engage=QUILL_EG['hex_engage'], float_mm=1.0,
               bolts='taper 1:10 + central M12x1.25 12.9 pull bolt (through the hollow quill)')
