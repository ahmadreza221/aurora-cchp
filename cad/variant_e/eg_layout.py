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
