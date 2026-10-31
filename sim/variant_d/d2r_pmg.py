# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version D2 - high-speed PM generator (PMG) sizing for the front pod (D2R).

2-pole surface-PM machine at shaft speed (115k rpm, 1917 Hz): Sm2Co17 ring magnets (diametral / parallel magnetisation) on a
d20/d10 steel carrier, 3 mm hoop-wound carbon-fibre sleeve (rotor OD 36), 1.5 mm mechanical gap, 12-slot 0.1 mm-lamination
stator (bore 39, OD 88) in an aluminium glycol-jacket sleeve inside the d110 pod (pod bore 98).  Litz winding, 3-phase,
double layer, 5/6 pitch.  Analytic magnetic circuit + loss estimates (no FEM yet).

Run:  uv run sim/variant_d/d2r_pmg.py  ->  sim/variant_d/d2r_pmg.json
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'cad', 'variant_d'))
import d2r_layout as L                                                            # noqa: E402

N = L.N_RUN; w = N * 2 * math.pi / 60; f = N / 60                                 # 2 poles -> f = 1917 Hz
G = L.GEN
L_stk = (G['stack'][1] - G['stack'][0]) * 1e-3
r_c, r_m = G['magnet_r'][0] * 1e-3, G['magnet_r'][1] * 1e-3
r_s = G['sleeve_r'][1] * 1e-3; t_sl = r_s - r_m
R_bore = G['stator_id'] / 2e3; g_mech = R_bore - r_s
R_out = G['stator_od'] / 2e3
Q, m_ph = G['slots'], 3

# ------------------------------------------------------------------ magnetic circuit
Br20, alpha_Br, T_mag = 1.08, -0.00035, 150.0                                      # Sm2Co17 (e.g. VAC VACOMAX 225 HR / Arnold Recoma 28)
Br = Br20 * (1 + alpha_Br * (T_mag - 20))
mu_r = 1.05
t_m = r_m - r_c
kc = 1.06                                                                         # Carter, semi-closed slots, 2 mm openings
g_eff = (t_sl + g_mech) * kc
Bg = Br * t_m / (t_m + mu_r * g_eff)                                              # peak (sinusoidal, parallel magnetised 2-pole)
r_g = 0.5 * (r_s + R_bore)
phi = 2 * Bg * r_g * L_stk                                                        # flux per pole, Wb
q = Q / (2 * m_ph)
kd = math.sin(math.pi / 6) / (q * math.sin(math.pi / (6 * q)))                   # distribution factor, 60 deg phase belt
kp = math.sin(5 / 6 * math.pi / 2)
kw = kd * kp
N_ph = 20                                                                          # series turns / phase (4 coils x 5 turns)
E_ph = 4.44 * f * N_ph * kw * phi
E_ll = math.sqrt(3) * E_ph
P_rated, P_peak = 28.0e3, 31.0e3                                                  # shaft kW: 30 C site rated / 15 C chilled-intake peak
I_ph = P_rated / (3 * E_ph)
I_pk = P_peak / (3 * E_ph)
A_rms = 2 * m_ph * N_ph * I_ph / (math.pi * 2 * R_bore)
sigma = Bg * A_rms / math.sqrt(2) * kw                                            # tangential stress (id = 0)
T = P_rated / w
# ------------------------------------------------------------------ slots, copper
tau_s = 2 * math.pi * R_bore / Q
B_tooth, B_yoke = 1.45, 1.35
w_t = Bg * tau_s / B_tooth
yoke = phi / 2 / (B_yoke * L_stk)
d_slot = R_out - R_bore - yoke
A_slot = (math.pi * ((R_bore + d_slot) ** 2 - R_bore ** 2) - Q * w_t * d_slot) / Q
fill = 0.36                                                                        # Litz + liner
turns_per_slot = 2 * 5
A_cu_turn = A_slot * fill / turns_per_slot
J = I_ph / A_cu_turn
MLT = 2 * L_stk + 2 * 0.072                                                        # 2-pole end turns ~72 mm each end (est)
rho_cu = 1.72e-8 * (1 + 0.0039 * (130 - 20))
R_ph = rho_cu * N_ph * MLT / A_cu_turn * 1.15                                      # Litz AC factor 1.15 at 1.9 kHz (est)
P_cu = 3 * I_ph ** 2 * R_ph
# iron: 0.10 mm NO10 / 10JNEX900-class, ~45 W/kg at 1.9 kHz, 1.35-1.45 T (est from supplier curves)
rho_fe = 7650
V_fe = (math.pi * (R_out ** 2 - R_bore ** 2) - Q * A_slot) * L_stk
m_fe = rho_fe * V_fe
P_fe = 45.0 * m_fe
# windage: Couette in the air gap (Bilgen & Boulos) + end faces
mu_air, rho_air = 2.1e-5, 1.15
Re = rho_air * w * r_s * g_mech / mu_air
Cf = 0.065 * (g_mech / r_s) ** 0.3 * Re ** -0.2
P_wind = Cf * math.pi * rho_air * w ** 3 * r_s ** 4 * L_stk * 1.25                # +25 % end faces / seals
P_rotor = 80.0                                                                     # magnet + sleeve eddy (segmented magnets, carbon sleeve; est)
P_brg = 2 * 180.0                                                                  # two 71900 at 1.84e6 ndm, oil jet (est)
P_em = P_rated
eta_em = P_em / (P_em + P_cu + P_fe + P_rotor)
eta_gen_incl_mech = P_em / (P_em + P_cu + P_fe + P_rotor + P_wind + P_brg)
Q_jacket = P_cu + P_fe + 0.5 * (P_wind + P_rotor)
glycol_lpm = 1.8
dT_gly = Q_jacket / (glycol_lpm / 60 * 1.06 * 3400)
# ------------------------------------------------------------------ rotor mechanics (115k and 120 % spin test)
rho_m, rho_cf = 8400.0, 1600.0
def sleeve_stress(om):
    p_mag = rho_m * om ** 2 * (r_m ** 3 - r_c ** 3) / (3 * r_m)                    # magnet ring pressure on the sleeve (no hoop in segments)
    r_sm = r_m + t_sl / 2
    return p_mag, p_mag * r_sm / t_sl + rho_cf * om ** 2 * r_sm ** 2
p115, s115 = sleeve_stress(w)
p138, s138 = sleeve_stress(1.2 * w)
cf_strength = 1600e6                                                                # hoop-wound T700/T800 epoxy, allowable 1.6 GPa (UTS ~2.4)
interference_mm = s138 / 135e9 * r_s * 1e3                                          # pre-stress so contact holds at 138k (E_hoop 135 GPa)
U_tip = w * r_s
out = dict(title='GR180 D2R PMG sizing (front pod, 115k rpm)', date='2026-10-23', script='sim/variant_d/d2r_pmg.py',
           rating=dict(P_shaft_rated_kW=P_rated / 1e3, P_shaft_peak_kW=P_peak / 1e3, torque_Nm=round(T, 2), poles=2, f_Hz=round(f, 1),
                       note='rated = 30 C site (turbine study 25.9 kW shaft); peak 31 kW at 15 C chilled intake; above that limit TIT / power'),
           geometry=dict(rotor_OD_mm=2 * r_s * 1e3, magnet_mm=[2 * r_c * 1e3, 2 * r_m * 1e3], sleeve_t_mm=t_sl * 1e3, gap_mech_mm=round(g_mech * 1e3, 2),
                         stator_ID_mm=2 * R_bore * 1e3, stator_OD_mm=2 * R_out * 1e3, stack_mm=L_stk * 1e3, slots=Q,
                         tooth_mm=round(w_t * 1e3, 2), yoke_mm=round(yoke * 1e3, 2), slot_depth_mm=round(d_slot * 1e3, 2), slot_area_mm2=round(A_slot * 1e6, 1),
                         jacket='Al 6082-T6 sleeve ID 88 / OD 98 with a 3 mm deep helical glycol groove, pressed in the pod bore 98, 2 O-rings each end',
                         pod_OD_mm=110),
           magnetics=dict(Br_at_150C=round(Br, 3), B_gap_peak_T=round(Bg, 3), flux_Wb=phi, kw=round(kw, 3), turns_per_phase=N_ph,
                          E_ph_V=round(E_ph, 1), E_ll_V=round(E_ll, 1), I_ph_rated_A=round(I_ph, 1), I_ph_peak_A=round(I_pk, 1),
                          A_rms_kA_m=round(A_rms / 1e3, 1), shear_stress_kPa=round(sigma / 1e3, 1), J_A_mm2=round(J / 1e6, 2),
                          R_ph_mOhm=round(R_ph * 1e3, 1), winding='3-ph double layer, 12 coils x 5 turns, 5/6 pitch, Litz 0.1 mm strands, class H, vacuum-potted'),
           losses_W=dict(copper=round(P_cu), iron=round(P_fe), rotor_eddy=P_rotor, windage=round(P_wind), bearings=P_brg),
           efficiency=dict(electromagnetic=round(eta_em, 4), incl_windage_bearings=round(eta_gen_incl_mech, 4), cycle_uses=0.95),
           cooling=dict(jacket_heat_W=round(Q_jacket), glycol_L_min=glycol_lpm, dT_K=round(dT_gly, 1), inlet_C='35-40',
                        rotor='rotor heat (eddy + half the windage) crosses the gap to the stator; magnet ~130-150 C (est) - Sm2Co17 good to 300 C'),
           rotor=dict(U_tip_m_s=round(U_tip), magnet_pressure_MPa_115k=round(p115 / 1e6, 1), sleeve_hoop_MPa_115k=round(s115 / 1e6),
                      sleeve_hoop_MPa_138k=round(s138 / 1e6), sleeve_allowable_MPa=cf_strength / 1e6, SF_138k=round(cf_strength / s138, 2),
                      sleeve_interference_mm=round(interference_mm, 3),
                      build='Sm2Co17 ring segments (2 halves x 4 axial pieces, diametral magnetisation), bonded on the d20 carrier; '
                            'T700 carbon sleeve wound with pre-tension or pressed on a 1:200 taper; Ti6Al4V end rings; balance G1 as an assembly'),
           converter=dict(type='4-quadrant machine-side AFE (motoring start), sensorless FOC, f_out >= 2 kHz, f_sw >= 24 kHz (SiC)',
                          DC_link_V='~650-750 V', start='motoring 5-8 kW short-time (01 section 6)'))
print(json.dumps({k: out[k] for k in ('geometry', 'magnetics', 'losses_W', 'efficiency', 'cooling', 'rotor')}, indent=1))
json.dump(out, open(os.path.join(HERE, 'd2r_pmg.json'), 'w'), indent=1)
print('-> sim/variant_d/d2r_pmg.json')
