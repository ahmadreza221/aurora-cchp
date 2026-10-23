"""GR180 version D2 - auxiliary systems 1-D sizing (D2A): natural-gas fuel system, closed-loop oil, generator glycol loop,
electrical aux load.  Pure Python (no FreeCAD).  Numbers marked est are engineering estimates, not supplier data.

Run: python3 sim/variant_d/d2a_aux_calc.py  -> sim/variant_d/d2a_aux_calc.json
Inputs: sim/variant_d/d2r_turbine.json (cycle vs ambient, fuel kW), sim/variant_d/d2r_pmg.json (PMG losses),
        sim/variant_d/d2r_rotor.json (seal leakage), cad/variant_d/d2a_layout.py (line lengths, geometry).
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_d'))
import d2a_layout as LY

TUR = json.load(open(os.path.join(HERE, 'd2r_turbine.json')))
PMG = json.load(open(os.path.join(HERE, 'd2r_pmg.json')))
ROT = json.load(open(os.path.join(HERE, 'd2r_rotor.json')))

# ------------------------------------------------------------------ gas properties (project basis: methane; city gas within +/-5 %)
LHV = 50.0e6            # J/kg (project value, sim/engine/e2_combustor_calc.py)
RHO_N = 0.717           # kg/Nm3 (0 C, 1.01325 bar)
R_NG = 518.3            # J/kg K
KAPPA = 1.31
MU_NG = 1.1e-5          # Pa s
P_AMB = 100726.0        # Pa (50 m)
T_GAS = 303.15          # K
P_SUP_NOM_G, P_SUP_MIN_G = 4.0e5, 3.5e5      # Pa gauge (city gas from the MW station, docs/03)
P_REG_G = 3.2e5          # regulator set point (gauge)


def nm3h(m_kg_s):
    return m_kg_s / RHO_N * 3600.0


# ------------------------------------------------------------------ 1. fuel flow vs ambient (cycle from the D2R turbine study)
fuel_rows = []
for rd, rb in zip(TUR['electric_vs_ambient_diffuser'], TUR['electric_vs_ambient_bare_eta_ts']):
    mf = rd['fuel_kW'] * 1e3 / LHV
    p2 = rd['PR'] * P_AMB * (1 - 0.0053)            # intake loss 0.53 % (d2_intake_exhaust_calc)
    fuel_rows.append(dict(T_amb_C=rd['T_amb_C'], PR=rd['PR'], P2_bara=round(p2 / 1e5, 3), fuel_kW=rd['fuel_kW'],
                          fuel_g_s=round(mf * 1e3, 2), gas_Nm3_h=round(nm3h(mf), 1),
                          P_el_net_kW_diffuser=rd['P_el_net_kW'], P_el_net_kW_bare=rb['P_el_net_kW'],
                          eta_el_pct_diffuser=rd['eta_el_net_pct'], T_exhaust_C=rd['T_exhaust_C']))
MF_MAX = max(r['fuel_g_s'] for r in fuel_rows) * 1e-3 * 1.10        # 0 C + 10 % (transient over-fuelling on acceleration)
P2_MAX = max(r['P2_bara'] for r in fuel_rows) * 1e5
MF_LIGHT = 0.70e-3                                                 # light-off (sim/engine/e2: 0.7 g/s)


# ------------------------------------------------------------------ 2. injector: 12 needles into the 12 v13A vaporiser sticks (now gas premix tubes)
def needle_dp(m_tot, p_back, d=LY.NEEDLE['id'], L=LY.NEEDLE['L'], n=LY.NEEDLE['n']):
    """manifold pressure needed for m_tot through n needles (entry K 0.5 + friction + exit dump 1.0), compressible
    expansion factor Y; returns dict."""
    A = math.pi * (d * 1e-3) ** 2 / 4
    m = m_tot / n
    pm = p_back * 1.05
    for _ in range(60):
        rho = pm / (R_NG * T_GAS)
        Re = 4 * m / (math.pi * d * 1e-3 * MU_NG)
        f = 0.316 / Re ** 0.25 if Re > 3000 else 64 / max(Re, 1)
        K = 0.5 + f * L / d + 1.0
        x = (pm - p_back) / pm
        Y = 1 - 0.41 * x / KAPPA
        dp = K * (m / (A * Y)) ** 2 / (2 * rho)
        pm = p_back + dp
    v = m / (rho * A)
    return dict(m_needle_g_s=round(m * 1e3, 3), P_manifold_bara=round(pm / 1e5, 3), dP_bar=round((pm - p_back) / 1e5, 3),
                dP_over_P=round((pm - p_back) / p_back, 3), v_m_s=round(v, 1), Mach=round(v / math.sqrt(KAPPA * R_NG * T_GAS), 2),
                Re=round(Re), K=round(K, 2))


inj = {}
for r in fuel_rows:
    inj['%d_C' % r['T_amb_C']] = needle_dp(r['fuel_g_s'] * 1e-3, r['P2_bara'] * 1e5 * 0.99)
inj['max_design'] = needle_dp(MF_MAX, P2_MAX * 0.99)
inj['light_off'] = needle_dp(MF_LIGHT, 1.02e5 * 1.15)
inj['v13A_needles_id1.1_at_max'] = needle_dp(MF_MAX, P2_MAX * 0.99, d=1.1)
# ring distribution: one feed (at 60 deg), half the flow each way in a d7x0.5 ring (ID 6)
pm_max = inj['max_design']['P_manifold_bara'] * 1e5
rho_m = pm_max / (R_NG * T_GAS)
A_ring = math.pi * (LY.RING['id'] * 1e-3) ** 2 / 4
v_ring = MF_MAX / 2 / (rho_m * A_ring)
q_ring = 0.5 * rho_m * v_ring ** 2
dp_inj = inj['max_design']['dP_bar'] * 1e5
ring = dict(ring=LY.RING['spec'], v_ring_m_s=round(v_ring, 1), q_ring_Pa=round(q_ring), needle_dp_Pa=round(dp_inj),
            maldistribution_pct_est=round(100 * 0.5 * q_ring / dp_inj, 1),
            v13A_ring_d5_v_m_s=round(MF_MAX / 2 / (rho_m * math.pi * 0.004 ** 2 / 4), 1))
# premix tube (vaporiser stick) equivalence ratio: air through the stick at ~3 % liner dp (est)
stick_A = math.pi * (LY.STICK_ID * 1e-3) ** 2 / 4
rho3 = P2_MAX / (287.0 * 430.0)
m_air_stick = 0.75 * stick_A * math.sqrt(2 * rho3 * 0.03 * P2_MAX)
phi_stick = (MF_MAX / 12) / m_air_stick / 0.0584
stick = dict(stick_id_mm=LY.STICK_ID, m_air_per_stick_g_s=round(m_air_stick * 1e3, 2), phi_in_stick_at_max=round(phi_stick, 2),
             note='phi in the stick is far above the methane rich limit (~1.7): no flame inside the stick, it burns at the stick exit '
                  'with the primary-zone air (vaporiser-stick practice); the gas jet also entrains air (ejector)')


# ------------------------------------------------------------------ 3. gas line + train pressure budget at max flow and minimum supply
def line_dp(m, p1, d_mm, L_m, K_fit=0.0, f_extra=1.0):
    A = math.pi * (d_mm * 1e-3) ** 2 / 4
    rho = p1 / (R_NG * T_GAS)
    v = m / (rho * A)
    Re = 4 * m / (math.pi * d_mm * 1e-3 * MU_NG)
    f = 0.316 / Re ** 0.25 * f_extra
    return (f * L_m / (d_mm * 1e-3) + K_fit) * 0.5 * rho * v ** 2, v


def kv_dp(Qn, kv, p2):        # EN 60534 gas, subcritical: Qn = 514 Kv sqrt(dp p2 / (rho_n T)) (dp, p2 bar, Qn m3/h)
    return (Qn / (514 * kv)) ** 2 * RHO_N * T_GAS / (p2 / 1e5) * 1e5


Qn_max = nm3h(MF_MAX)
train = []
p = P_AMB + P_SUP_MIN_G
for name, kv in LY.GAS_TRAIN_KV:
    if name.startswith('PCV'):
        dp = p - (P_AMB + P_REG_G)
        p = P_AMB + P_REG_G
        train.append(dict(item=name, dp_bar=round(dp / 1e5, 3), p_out_barg=round((p - P_AMB) / 1e5, 3), note='needs >= 0.3 bar to regulate'))
        continue
    if name.startswith('FCV'):
        train.append(dict(item=name, dp_bar=None, p_in_barg=round((p - P_AMB) / 1e5, 3)))
        p_fcv_in = p
        continue
    dp = kv_dp(Qn_max, kv, p)
    p -= dp
    train.append(dict(item=name, Kv=kv, dp_bar=round(dp / 1e5, 4), p_out_barg=round((p - P_AMB) / 1e5, 3)))
dp_ext, v_ext = line_dp(MF_MAX, pm_max, LY.GAS_LINE['id'], LY.GAS_LINE['L_m'], K_fit=LY.GAS_LINE['K_fittings'])
dp_hose, v_hose = line_dp(MF_MAX, pm_max, LY.GAS_LINE['hose_id'], LY.GAS_LINE['hose_L_m'], f_extra=2.5)
dp_feed, v_feed = line_dp(MF_MAX, pm_max, LY.FEED['id'], LY.FEED['L_m'], K_fit=1.2)
p_after_fcv_needed = pm_max + dp_ext + dp_hose + dp_feed
dp_fcv = p_fcv_in - p_after_fcv_needed
Kv_fcv_req = Qn_max / (514 * math.sqrt(dp_fcv / 1e5 * (p_after_fcv_needed / 1e5) / (RHO_N * T_GAS)))
gas = dict(
    Qn_max_Nm3_h=round(Qn_max, 1), m_max_g_s=round(MF_MAX * 1e3, 2), supply_min_barg=P_SUP_MIN_G / 1e5, regulator_set_barg=P_REG_G / 1e5,
    train_at_max_flow_min_supply=train,
    line_engine=dict(spec=LY.GAS_LINE['spec'], v_m_s=round(v_ext, 1), dp_bar=round(dp_ext / 1e5, 3),
                     flex_hose_dp_bar=round(dp_hose / 1e5, 3), feed_d8_dp_bar=round(dp_feed / 1e5, 3), feed_v_m_s=round(v_feed, 1)),
    manifold_max_bara=round(pm_max / 1e5, 3), FCV_inlet_barg=round((p_fcv_in - P_AMB) / 1e5, 3),
    FCV_dp_available_bar=round(dp_fcv / 1e5, 3), FCV_Kv_required=round(Kv_fcv_req, 2), FCV_Kv_selected=LY.FCV_KVS,
    FCV_authority_ok=bool(LY.FCV_KVS >= 1.25 * Kv_fcv_req),
    light_off_Nm3_h=round(nm3h(MF_LIGHT), 1), turndown=round(MF_MAX / MF_LIGHT, 1),
    v_train_DN15_m_s=round(MF_MAX / ((P_AMB + P_SUP_MIN_G) / (R_NG * T_GAS)) / (math.pi * 0.0161 ** 2 / 4), 1),
    valve_proving=dict(volume_between_SSV_L=0.08, test='close SSV2, open SSV1 2 s, close: PT-613 must hold (SSV2 tight); vent via FCV->engine '
                       'during pre-purge, then PT-613 must stay ~0 (SSV1 tight); 10 s each, every start (EN 1643 principle, burner-control logic in B1/SR1)'),
    pressure_switch_settings=dict(PSL_602_barg=3.3, PSH_603_barg=3.8, note='PSL before the regulator (supply), PSH after it (regulator failure); manual reset'),
    note='regulator set 3.2 barg leaves 0.3 bar to the 3.5 barg supply minimum (PSL-602 trips at 3.3); the FCV meters the flow (speed/power governor in B1), '
         'manifold pressure PT-605 is the fuel-flow observer (needles calibrated on the rig)')


# ------------------------------------------------------------------ 4. oil system (4 x 10x22x6 hybrid, jets)
RHO_OIL, CP_OIL = 860.0, 2000.0
NU70 = 11.5e-6                   # VG32 at 70 C (m2/s)
n = 115000.0
w = n * 2 * math.pi / 60
dm = 16.0                        # mm (10 / 22)
brg = {}
for f0 in (2.0, 3.0):
    M0 = 1e-7 * f0 * (NU70 * 1e6 * n) ** (2 / 3) * dm ** 3            # N mm, Palmgren viscous term
    M1 = 0.001 * 100.0 * dm                                         # N mm, load term (P ~100 N, f1 0.001)
    brg['f0_%.0f' % f0] = round((M0 + M1) * 1e-3 * w)
P_brg = brg['f0_3']                                                 # W per bearing (design, est)
Cd_jet, d_jet = 0.70, 0.8e-3
q_jet = Cd_jet * math.pi * d_jet ** 2 / 4 * math.sqrt(2 * 2.5e5 / RHO_OIL)          # m3/s per jet at 2.5 barg
Q_oil = 4 * q_jet
seal = ROT['seals']['cases']
air_core = seal['core_front']['leak_g_s'] + seal['core_rear']['leak_g_s']
air_gen = seal['gen_front']['leak_g_s'] + seal['gen_rear']['leak_g_s']
Q_heat = dict(bearing_friction_W=4 * P_brg, core_hot_end_soak_W_est=400, core_buffer_air_W_est=round(0.5 * air_core * 1e-3 * 1010 * 65),
              generator_W_est=50)
Q_oil_tot = sum(Q_heat.values())
dT_oil = Q_oil_tot / (Q_oil * RHO_OIL * CP_OIL)
# core scavenge + vent passage through the 272 deg diffuser land (tube 5 x 0.5, ID 4, ~0.25 m incl. tunnel drillings)
A_v = math.pi * 0.004 ** 2 / 4
K_v = 1.5 + 0.03 * 0.25 / 0.004
m_vent_10kPa = A_v * math.sqrt(2 * 1.05 * 1e4 / K_v)
dp_vent_design = (air_core * 1e-3 / m_vent_10kPa) ** 2 * 1e4
A_need = air_core * 1e-3 / math.sqrt(2 * 1.05 * 5e3 / K_v)
oil = dict(
    oil='ISO VG 32 synthetic turbine oil (e.g. FUCHS Renolin / Shell Turbo S4 class; EU blender)',
    bearing_friction_W_each_est=brg, jet=dict(d_mm=0.8, Cd=Cd_jet, p_barg=2.5, L_min_each=round(q_jet * 6e4, 2),
                                              note='0.5 L/min per jet at 2.5 barg; for the D2R target 0.3 L/min run ~0.9 barg or use d0.6 jets (set on the rig)'),
    feed_L_min=round(Q_oil * 6e4, 2), heat_W=Q_heat, heat_total_W=round(Q_oil_tot), design_cooler_W=2000,
    dT_oil_K=round(dT_oil, 1), T_supply_C=60, T_return_mean_C=round(60 + dT_oil),
    pressure_pump=dict(type='external gear pump ~1.0 cm3/rev on a 24 V BLDC motor, submerged in the tank', Q_L_min=2.5, p_barg=3.0,
                       hydraulic_W=round(3e5 * 2.5 / 6e4), motor_W=60, control='speed loop on PT-701 (2.5 barg), relief 4 bar'),
    scavenge_pump=dict(type='gear pump ~2.5 cm3/rev, 24 V BLDC, on the tank lid, suction from the drain collector',
                       Q_L_min=round(3 * Q_oil * 6e4, 1), scavenge_ratio=3.0, motor_W=60),
    tank=dict(gross_L=round(LY.OIL_TANK['dx'] * LY.OIL_TANK['dy'] * LY.OIL_TANK['dz'] * 1e-6, 2), oil_charge_L=3.0,
              dwell_min=round(2.0 / (Q_oil * 6e4), 2), heater_W=200, note='baffle, sight glass, float LSL-707, TE-704, drain'),
    filter=dict(rating='10 um, beta10 >= 200, bypass 2.5 bar, electrical clogging switch PDS-703', dp_clean_bar=0.1),
    cooler=dict(type='oil-to-glycol tube cooler (Laminova C43 class, SE)', UA_W_K_needed_at_30C=None),
    breather=dict(air_in_g_s_labyrinths=round(air_core + air_gen, 1), m3_h_at_80C=round((air_core + air_gen) * 1e-3 / 1.0 * 3600, 1),
                  air_in_g_s_with_core_piston_rings=round(1.0 + air_gen, 1),
                  separator='coalescing oil-mist separator >= 30 m3/h, drain to the scavenge collector, vent outside the enclosure'),
    core_vent=dict(passage='one tube 5 x 0.5 (ID 4) in the re-drilled 272 deg diffuser land (Ø5.2 in a 9.2 mm land)',
                   air_g_s_at_10kPa=round(m_vent_10kPa * 1e3, 2), core_labyrinth_air_g_s=round(air_core, 1),
                   chamber_overpressure_kPa_with_labyrinths=round(dp_vent_design / 1e3), area_needed_mm2_at_5kPa=round(A_need * 1e6),
                   verdict='NOT OK with the D2R labyrinths (6 g/s): the chamber would pressurise and stop the buffer flow. '
                           'D2R must cut the core seal air to <= ~1 g/s (turbo piston rings / carbon ring on the d14 runner and the '
                           'compressor boss) or open a vent passage of >= ~90 mm2 (not possible through one diffuser land)'))
# cooler UA at the 30 C site point (glycol from the PMG jacket)
# filled in after the glycol loop below


# ------------------------------------------------------------------ 5. generator glycol loop
RHO_G, CP_G, NU_G = 1035.0, 3700.0, 2.2e-6      # 40 % propylene glycol at ~45 C
Q_pmg = PMG['cooling']['jacket_heat_W'] * 1.1    # +10 % (peak 31 kW)
Q_gly = Q_pmg + oil['design_cooler_W'] * 0.75     # oil heat at design (1.5 kW)
V_g = LY.GLYCOL['flow_L_min'] / 6e4
mg = V_g * RHO_G
dT_g = Q_gly / (mg * CP_G)


def duct_dp(V, A, Dh, L, K=0.0):
    v = V / A
    Re = v * Dh / NU_G
    f = 64 / Re if Re < 2300 else 0.316 / Re ** 0.25
    return (f * L / Dh + K) * 0.5 * RHO_G * v ** 2, v, Re


J = LY.JACKET
A_j = J['groove_w'] * J['groove_d'] * 1e-6
Dh_j = 4 * A_j / (2 * (J['groove_w'] + J['groove_d']) * 1e-3)
L_j = J['turns'] * math.pi * J['d_mean'] * 1e-3
dp_j, v_j, Re_j = duct_dp(V_g, A_j, Dh_j, L_j, K=2.0)
dp_h, v_h, Re_h = duct_dp(V_g, math.pi * (LY.GLYCOL['hose_id'] * 1e-3) ** 2 / 4, LY.GLYCOL['hose_id'] * 1e-3, LY.GLYCOL['hose_L_m'], K=6 * 0.4 + 4 * 1.5)
dp_items = dict(jacket_helix=dp_j, hoses_fittings=dp_h, laminova_glycol_side=5e3, radiator=6e3, pod_ports_G1_4=4 * 0.5 * RHO_G * (V_g / (math.pi * 0.006 ** 2 / 4)) ** 2)
dp_g = sum(dp_items.values())
# radiator (est): eps-NTU, crossflow, compact Al bar-plate core
R = LY.RADIATOR
A_air = R['area_density_m2_m3'] * R['w'] * R['h'] * R['t'] * 1e-9
UA = R['U_air_W_m2K'] * A_air
C_air = R['air_m3_h'] / 3600 * 1.13 * 1007
C_g = mg * CP_G
Cmin, Cmax = min(C_air, C_g), max(C_air, C_g)
NTU = UA / Cmin
cr = Cmin / Cmax
eps = 1 - math.exp(NTU ** 0.22 / cr * (math.exp(-cr * NTU ** 0.78) - 1))
ITD = Q_gly / (eps * Cmin)
gly_rows = []
for Tamb in (30.0, 46.0):
    T_in_rad = Tamb + ITD
    T_sup = T_in_rad - dT_g
    gly_rows.append(dict(T_amb_C=Tamb, T_glycol_supply_C=round(T_sup, 1), T_after_PMG_C=round(T_sup + Q_pmg / (mg * CP_G), 1),
                         T_radiator_in_C=round(T_in_rad, 1)))
glycol = dict(
    fluid='40 % inhibited propylene glycol (Clariant Antifrogen L class)', flow_L_min=LY.GLYCOL['flow_L_min'],
    heat_W=dict(PMG_jacket=round(Q_pmg), oil_cooler=round(oil['design_cooler_W'] * 0.75), total=round(Q_gly)), dT_K=round(dT_g, 1),
    order='pump -> PMG jacket (coldest) -> oil cooler -> radiator -> expansion tank / pump suction',
    jacket=dict(turns=J['turns'], pitch_mm=J['pitch'], groove='%g x %g mm' % (J['groove_w'], J['groove_d']), v_m_s=round(v_j, 2), Re=round(Re_j),
                dp_kPa=round(dp_j / 1e3, 1)),
    dp_kPa={k: round(v / 1e3, 1) for k, v in dp_items.items()}, dp_total_kPa=round(dp_g / 1e3, 1), head_m=round(dp_g / (RHO_G * 9.81), 2),
    pump=dict(type='wet-rotor circulator with PWM input (Grundfos UPM3 FLEX AS 15-75 130 class, DK), 230 V', head_max_m=7.5, P_W='4-52'),
    radiator=dict(core_mm='%d x %d x %d' % (R['w'], R['h'], R['t']), air_m3_h=R['air_m3_h'], UA_W_K_est=round(UA), NTU=round(NTU, 2),
                  eps=round(eps, 2), ITD_K=round(ITD, 1), fan='305 mm 24 V axial fan, brushless PWM (SPAL class, IT), 30-150 W'),
    temperatures=gly_rows,
    volume_L_est=1.5, expansion=dict(dV_cm3=round(1500 * 6.0e-4 * 70), tank_L=1.0, cap_bar=1.0),
    note='supply 38-39 C at the 30 C site (PMG design 35-40 C); 54-55 C at 46 C roof air: stator/magnet run ~15 K warmer (Sm2Co17 OK, '
         'EMF -0.5 %); connect to the plant glycol loop (DC-1/HX-4) later if wanted')
# cooler UA at the 30 C site point
T_g_in = gly_rows[0]['T_after_PMG_C']
T_g_out = T_g_in + oil['design_cooler_W'] * 0.75 / (mg * CP_G)
T_o_in, T_o_out = oil['T_return_mean_C'], oil['T_supply_C']
d1, d2 = T_o_in - T_g_out, T_o_out - T_g_in
lmtd = (d1 - d2) / math.log(d1 / d2)
oil['cooler']['UA_W_K_needed_at_30C'] = round(oil['design_cooler_W'] * 0.75 / lmtd)
oil['cooler']['LMTD_K'] = round(lmtd, 1)
oil['cooler']['oil_supply_at_46C_air_C_est'] = round(gly_rows[1]['T_after_PMG_C'] + 12, 0)


# ------------------------------------------------------------------ 6. electrical aux load (24 VDC / 230 VAC from the AUX-DB)
loads = dict(oil_pressure_pump=40, oil_scavenge_pump=40, glycol_pump=25, radiator_fan_avg=70, SSV_holding_2x=2 * 40, FCV_PWM=12,
             sensors_JB_transmitters=25, UV_flame_cell=5, n1_speed_electronics=5)
peak = dict(oil_pressure_pump=60, oil_scavenge_pump=60, glycol_pump=52, radiator_fan=150, SSV_2x=80, FCV=24, sensors=25, UV=5, n1=5,
            oil_heater=200, ignition_transformer_start=120)
elec = dict(continuous_W=loads, continuous_total_W=sum(loads.values()), peak_W=peak, peak_total_W=sum(peak.values()),
            cycle_allowance_W=600, note='cycle P_net already subtracts 0.6 kW aux (d2r_turbine.json cycle_basis): the D2A load fits')

out = dict(
    title='GR180 D2 auxiliary systems 1-D sizing (fuel / oil / glycol / electrical)', date='2026-10-23', script='sim/variant_d/d2a_aux_calc.py',
    basis=dict(LHV_MJ_kg=LHV / 1e6, rho_n=RHO_N, gas='project basis methane; Iranian city gas LHV/rho within ~5 %', supply='4 barg nominal, 3.5 barg min'),
    fuel_vs_ambient=fuel_rows, fuel_design_max_g_s=round(MF_MAX * 1e3, 2), fuel_design_max_Nm3_h=round(nm3h(MF_MAX), 1),
    injector=dict(spec=LY.NEEDLE['spec'], cases=inj, ring=ring, premix_stick=stick, feed=LY.FEED['spec']),
    gas_system=gas, oil=oil, glycol=glycol, electrical=elec)
json.dump(out, open(os.path.join(HERE, 'd2a_aux_calc.json'), 'w'), indent=1)

print('fuel vs ambient:')
for r in fuel_rows:
    print('  %3d C  PR %.3f  P2 %.2f bara  %.2f g/s  %.1f Nm3/h  P_el %.1f / %.1f kW' % (r['T_amb_C'], r['PR'], r['P2_bara'], r['fuel_g_s'],
          r['gas_Nm3_h'], r['P_el_net_kW_diffuser'], r['P_el_net_kW_bare']))
print('design max %.2f g/s = %.1f Nm3/h' % (MF_MAX * 1e3, nm3h(MF_MAX)))
for k, v in inj.items():
    print('  injector %-26s pm %.3f bara  dp %.3f bar  v %.0f m/s  M %.2f' % (k, v['P_manifold_bara'], v['dP_bar'], v['v_m_s'], v['Mach']))
print('ring v %.1f m/s q %d Pa -> maldistribution ~%.1f %%' % (v_ring, q_ring, ring['maldistribution_pct_est']))
print('gas: FCV in %.2f barg, dp %.2f bar, Kv req %.2f (sel %.2f)  ext line v %.0f m/s dp %.3f bar' % (
    gas['FCV_inlet_barg'], gas['FCV_dp_available_bar'], gas['FCV_Kv_required'], LY.FCV_KVS, v_ext, dp_ext / 1e5))
for t in train:
    print('   ', t)
print('oil: friction/brg %s W, feed %.2f L/min, heat %d W, dT %.1f K, core vent %.2f g/s @10 kPa (need %.1f) -> dp %d kPa' % (
    brg, Q_oil * 6e4, Q_oil_tot, dT_oil, m_vent_10kPa * 1e3, air_core, dp_vent_design / 1e3))
print('glycol: %d W, %.1f L/min, dT %.1f K, dp %.1f kPa (%.2f m), radiator NTU %.2f eps %.2f ITD %.1f K' % (
    Q_gly, LY.GLYCOL['flow_L_min'], dT_g, dp_g / 1e3, dp_g / (RHO_G * 9.81), NTU, eps, ITD), gly_rows)
print('oil cooler UA %s W/K, LMTD %s' % (oil['cooler']['UA_W_K_needed_at_30C'], oil['cooler']['LMTD_K']))
print('electrical continuous %d W, peak %d W' % (elec['continuous_total_W'], elec['peak_total_W']))
