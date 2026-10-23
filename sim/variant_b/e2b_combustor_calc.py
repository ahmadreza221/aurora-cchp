#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP variant B (GR180-STEAM)  E2-B - simple-cycle combustor: compact casing, injector carrier plate, liner.

No recuperator: compressor air (165 C) goes from the 13 diffuser channels straight into the combustor.  Same core, E1 and E3
as variant A; E2-B mates the E3 interduct flange exactly like E2 (E2 face x 115 + 1 mm gasket = E3 face x 116, 16 x M8,
PCD 160).  Variant A (sim/engine/e2_combustor_calc.py) is not touched; its physics and the liner geometry are reused here.

Pure python (no numpy).  Run:   python3 sim/variant_b/e2b_combustor_calc.py
Writes:  sim/variant_b/e2b_design.json   (geometry read by cad/variant_b/e2b_combustor_casing.py)
         sim/variant_b/e2b_results.json  (all calculated values, used by docs/variant_b/03_e2b_combustor.md)
Design point = docs/variant_b/00_concept.md / sim/variant_b/vb_cycle.py: concept_study.cycle, arch fpt, eps 0, PR 3.1,
TIT 800 C, intake 15 C, 0.395 kg/s, target efficiencies.  Frame: ENG (mm), x = tunnel front face, +x downstream, y north, z up.
Every correlation and assumption is marked  # ASSUMPTION / # REF.
"""
import math, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); SIM = os.path.dirname(HERE)
sys.path.insert(0, SIM)
import concept_study as cs   # noqa: E402  (project cycle)

SIG = 5.670e-8; RU = 8.314; R_AIR = 287.05; R_NG = 518.3
LHV = cs.LHV                 # 50 MJ/kg (project value; methane)
FAR_ST = 0.0584              # stoichiometric fuel/air, methane            # ASSUMPTION NG ~ CH4
CP_NG = 2450.0

# ----------------------------------------------------------------- properties (same tables as sim/engine/e2_combustor_calc.py)
_CP = [(250, 1003), (300, 1005), (400, 1014), (500, 1030), (600, 1051), (700, 1075), (800, 1099), (900, 1121), (1000, 1142),
       (1100, 1161), (1200, 1179), (1300, 1197), (1400, 1214), (1500, 1230), (1600, 1244), (1800, 1268), (2000, 1288),
       (2200, 1305), (2600, 1335)]   # REF: air tables (Incropera A.4 / NASA), J/kgK
def _interp(tab, x):
    if x <= tab[0][0]: return tab[0][1]
    for (x0, y0), (x1, y1) in zip(tab[:-1], tab[1:]):
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tab[-1][1]
def cp_air(T): return _interp(_CP, T)
_H = [(298.0, 0.0)]
for _T in range(300, 2601, 10):
    _H.append((float(_T), _H[-1][1] + 0.5 * (cp_air(_H[-1][0]) + cp_air(_T)) * (_T - _H[-1][0])))
def h_air(T): return _interp(_H, T)
def h_prod(T, f): return h_air(T) * (1 + 1.2 * f)        # ASSUMPTION lean CH4 products
def mu_air(T): return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)
def k_air(T): return 0.0241 * (T / 273.15) ** 0.81
def rho(P, T, R=R_AIR): return P / (R * T)
def T_burn(T_air, f, T_fuel=300.0, eta=1.0):
    rhs = h_air(T_air) + f * (eta * LHV + CP_NG * (T_fuel - 298.0))
    lo, hi = 250.0, 2600.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if (1 + f) * h_prod(m, f) > rhs: hi = m
        else: lo = m
    return 0.5 * (lo + hi)
def _inv_h(h):
    lo, hi = 250.0, 2600.0
    for _ in range(50):
        mm = 0.5 * (lo + hi)
        if h_air(mm) > h: hi = mm
        else: lo = mm
    return 0.5 * (lo + hi)
def S_L(phi, T, P):          # REF Guelder (1984) CH4/air
    W, eta_, xi, a, b = 0.422, 0.15, 5.18, 2.0, -0.5
    return W * phi ** eta_ * math.exp(-xi * (phi - 1.075) ** 2) * (T / 300.0) ** a * (P / 101325.0) ** b
def tau_ign_SC(phi, T, P):   # REF Spadaccini & Colket (1994), extrapolated below 1300 K
    X_ch4 = phi / (9.52 + phi); X_o2 = 0.21 * (1 - X_ch4); C = P / (RU * T) * 1e-6
    return 1.77e-14 * math.exp(18693.0 / T) * (X_o2 * C) ** -1.05 * (X_ch4 * C) ** 0.66

# ----------------------------------------------------------------- 0. design point (variant-B cycle, eps = 0)
GT = dict(arch='fpt', PR=3.1, TIT=1073.15, eta_c=0.73, eta_t=0.82, eta_pt=0.78, eps=0.0, booster=False, P_amb=100725.0)
DPB = cs.cycle(dict(GT, ma=0.395, T_amb=288.15))
MA = 0.395; MF = DPB['mf']; T2 = DPB['T2']; TIT = GT['TIT']
P_AMB = GT['P_amb']; P2 = P_AMB * 0.99 * GT['PR']; P3_CYCLE = DPB['P3']
R = {}
R['design_point'] = dict(ma=MA, mf=MF, T2_C=T2 - 273.15, TIT_C=TIT - 273.15, P2_bar=P2 / 1e5, P3_cycle_bar=P3_CYCLE / 1e5,
                         Q_fuel_kW=MF * LHV / 1e3, FAR=MF / MA, phi_overall=MF / MA / FAR_ST, T_FPT_exit_C=DPB['T_hot'] - 273.15,
                         P_shaft_kW=DPB['P_shaft'] / 1e3, source='concept_study.cycle(arch fpt, eps 0, PR 3.1, TIT 800 C, 15 C) = vb_cycle.py')

# ----------------------------------------------------------------- 1. geometry (ENG mm) - single source for the CAD
E2A = json.load(open(os.path.join(SIM, 'engine', 'e2_design.json')))      # variant-A geometry: liner, rear ring, core refs (read only)
KEEP_FROM_A = ('x_io_lip', 'x_io_step', 'x_io_end', 'r_io_lip_o', 'r_io_lip_i', 'r_core', 'x_ch_exit', 'r_ch_i', 'r_ch_o', 'A_ch', 'n_ch',
               'x_diff_back', 'r_tunnel', 'x_tunnel_tube', 'r_tunnel_bore', 'x_ngv', 'r_ngv_o', 'r_ngv_rib', 'x_ngv_rib', 'x_ngv_end',
               'r_ngv_in_i', 'r_ngv_in_o', 'x_ngv_inner_end', 'x_turb_exit', 'x_nut_end',
               'x_ring_lip', 'r_lip_i', 'r_ring_bore', 'oring_x', 'r_front_ring_o',
               'r_rear_bore', 'x_rear_ring', 'r_e3_flange_o', 'pcd_e3', 'n_e3_bolts', 'd_e3_bolt', 'e3_bolt_a0_deg', 'e3_spigot_d',
               'e3_spigot_depth', 'e3_groove_ri', 'x_e3_face', 't_e3_gasket', 'seal_groove_x', 'r_seal_groove', 'gasket_e3_r', 'x_e3_flange',
               'x_dome', 't_dome', 't_liner', 'r_li_o', 'r_lo_i', 'x_li_front', 'x_li_end', 'x_lo_cyl_end', 'x_lo_cone_end', 'r_lo_sleeve_i',
               'x_lo_end', 'n_inj', 'r_inj', 'inj_a0_deg', 'x_liner_pins', 'n_liner_pins', 'a_liner_pins',
               'r_shield_i', 't_shield', 'x_shield', 'x_igniter', 'a_igniter', 'x_uv', 'a_uv', 'x_p3', 'a_p3', 'x_twall', 'a_twall', 'z_skid',
               'foot_w', 'x_bh_hub_end', 'r_bh_bore', 't_gasket')
G = {k: E2A[k] for k in KEEP_FROM_A}
G.update(
    # front casing (1.4404, cold 165 C): the variant-A front ring (bore r 53.55 over the intake-outer, stop lip r 51.5, O-ring x -8)
    # continues as a 3 mm cone to the shell r 72/75 at x 3 (the diffuser OD r 53.5 ends at x 7.6), shell to the flange x 14..20.
    x_casing_front=-30.0, x_cone=(-4.85, 3.0), r_case_i=72.0, t_case=3.0, x_mid_A=(14.0, 20.0), r_flange_o=96.0, pcd_mid=168.0,
    n_mid_bolts=16, d_mid_bolt=8, mid_bolt_a0_deg=11.25,
    # injector carrier plate (1.4404, 6 mm, x 21..27): replaces the variant-A bulkhead; both faces see compressor air.
    # 7 air windows (sectors r 46..68, 40 deg, centred between the injectors), hub sleeve to x 35 (inner-liner slip joint),
    # 7 stem bores, 3 core-retainer fingers to the diffuser back plate (x 2.0) with 0.3 mm play.
    x_bh=21.0, t_bh=6.0, r_bh_hub_o=23.0, n_windows=7, window_r=(46.0, 68.0), window_deg=40.0,
    retainer_r=24.5, retainer_d=6.0, retainer_a_deg=(30.0, 150.0, 270.0), retainer_gap=0.3,
    # gas manifold (316L): torus 12 x 1 at x 15 / r 37.5 on the carrier front face, 7 stems 8 x 1, feed tube 12 x 1 from the torus
    # (south) radially at x 15 to r 64, then out to the front-casing boss at x 8 (DIN 2353 L12); clears the diffuser (x <= 7.6)
    x_manifold=15.0, r_manifold=37.5, d_manifold=12.0, t_manifold=1.0, d_stem=8.0, t_stem=1.0, gas_entry_deg=180.0, x_gas_boss=8.0,
    d_feed=12.0, t_feed=1.0, r_feed_knee=64.0,
    # rear casing: flange x 28..34, shell r 72/75 x 34..100, rear ring x 100..115 = variant A (E3 flange)
    x_case_shell_end=100.0,
    # ports on the front casing (compressor delivery): P2 PT-521, T2 TE-502, E3 buffer-air bleed
    x_p2=10.0, a_p2=120.0, x_t2=10.0, a_t2=60.0, x_bleed=10.0, a_bleed=150.0,
    # front foot (engine axial fixed point) under the front-casing shell
    x_foot=(2.5, 10.5),
    insulation=dict(rear=25.0),
    # rear bore: the casing runs ~280 C (variant A ~580 C), so the IN713LC NGV rib (~720 C) grows 0.2 mm more than the bore;
    # cold radial clearance 0.5 (A: 0.15) keeps ~0.3 mm hot.  The piston-ring groove (r 38.45..40) and the E3 flange are unchanged.
    r_rear_bore=38.45,
)
G['x_bh_back'] = G['x_bh'] + G['t_bh']
G['x_hot_flange'] = (G['x_bh_back'] + G['t_gasket'], G['x_bh_back'] + G['t_gasket'] + 6.0)
G['x_dome_hot'] = G['x_dome'] + G['t_dome']
G['r_lo_o'] = G['r_lo_i'] + G['t_liner']; G['r_li_i'] = G['r_li_o'] - G['t_liner']
H_DOME = G['r_lo_i'] - G['r_li_o']

# ----------------------------------------------------------------- 2. pressure budget (diffuser exit -> dump -> carrier windows -> liner)
rho2 = rho(P2, T2)
A_ch = G['A_ch'] * 1e-6; V_ch = MA / (rho2 * A_ch); q_ch = 0.5 * rho2 * V_ch ** 2
A_ann = math.pi * ((G['r_ch_o'] * 1e-3) ** 2 - (G['r_ch_i'] * 1e-3) ** 2)
q_ann = 0.5 * rho2 * (MA / (rho2 * A_ann)) ** 2
dP_wakes = (1 - A_ch / A_ann) ** 2 * q_ch                            # REF Borda-Carnot: 13 jets -> annulus (as variant A)
A_plen = math.pi * ((G['r_case_i'] * 1e-3) ** 2 - ((G['r_manifold'] + G['d_manifold'] / 2) * 1e-3) ** 2)
dP_dump = (1 - A_ann / A_plen) ** 2 * q_ann                           # sudden expansion annulus -> front plenum
A_win = G['n_windows'] * G['window_deg'] / 360.0 * math.pi * ((G['window_r'][1] * 1e-3) ** 2 - (G['window_r'][0] * 1e-3) ** 2)
q_win = 0.5 * rho2 * (MA / (rho2 * A_win)) ** 2
dP_win = 1.0 * q_win                                                  # ASSUMPTION K 1.0 (thick-plate windows, dump behind)
P_plenum = P2 - dP_wakes - dP_dump - dP_win
DPL = 0.030                                                           # design liner pressure drop / P_plenum (cold inlet: 3 %)
P_comb = P_plenum * (1 - DPL)
dP_L = P_plenum - P_comb
A_out = math.pi * ((G['r_case_i'] * 1e-3) ** 2 - (G['r_lo_o'] * 1e-3) ** 2)
R['pressure'] = dict(P2=P2 / 1e5, V_channels=V_ch, q_channels_kPa=q_ch / 1e3, dP_wakes_kPa=dP_wakes / 1e3, V_annulus=MA / (rho2 * A_ann),
                     dP_dump_kPa=dP_dump / 1e3, A_windows_mm2=A_win * 1e6, V_windows=MA / (rho2 * A_win), dP_windows_kPa=dP_win / 1e3,
                     P_plenum=P_plenum / 1e5, dP_liner_pct=DPL * 100, P_combustor=P_comb / 1e5,
                     dp_total_pct=(P2 - P_comb) / P2 * 100, dp_cycle_budget_pct=4.5, P3_cycle=P3_CYCLE / 1e5,
                     V_outer_annulus=0.45 * MA / (rho2 * A_out), upper_bound_pure_dump_kPa=(q_ch + dP_win) / 1e3)

# ----------------------------------------------------------------- 3. air split and liner holes (all air at T2)
SPLIT = dict(
    injectors=dict(f=0.310, Cd=0.75, n=G['n_inj']),            # radial swirlers, partially premixed (phi_inj 0.85: Da 5 with the cold inlet)
    dome_cool=dict(f=0.030, Cd=0.65, n=8 * G['n_inj']),         # effusion, 8 holes around each cup
    outer_film=dict(f=0.100, Cd=0.65, n=4 * 56),                # 4 rows x 56 (2 splash lips in the PZ); 10 % keeps the outer liner < 830 C
    inner_film=dict(f=0.060, Cd=0.65, n=4 * 15),                # 4 rows x 15 (15 = not 4-per-rev; inner liner now carries a larger film)
    secondary=dict(f=0.140, Cd=0.61, n=3 * G['n_inj']),         # 21, 3 per injector
    dilution=dict(f=None, Cd=0.61, n=6 * G['n_inj']),           # 42, 2 rows x 21, remainder
    leak=dict(f=0.004), ngv_purge=dict(f=0.008),                # carrier/hub leaks, NGV inner cavity purge (as variant A)
)
SPLIT['dilution']['f'] = 1.0 - sum(v['f'] for k, v in SPLIT.items() if k != 'dilution')
rho_c = rho(P_plenum, T2); V_jet = math.sqrt(2 * dP_L / rho_c)
def rnd(d, step=0.1): return round(d / step) * step
HOLES = {}
for k, v in SPLIT.items():
    if 'Cd' not in v: continue
    m = v['f'] * MA; Aeff = m / math.sqrt(2 * rho_c * dP_L); Ag = Aeff / v['Cd']
    d = None if k == 'injectors' else rnd(math.sqrt(4 * Ag / v['n'] / math.pi) * 1e3, 0.05 if k in ('inner_film', 'outer_film', 'dome_cool') else 0.1)
    HOLES[k] = dict(frac=v['f'], m=m, A_eff_mm2=Aeff * 1e6, A_geom_mm2=Ag * 1e6, n=v['n'], d_mm=d, V_jet=V_jet)
xd = G['x_dome_hot']
STATIONS = dict(outer_film=[xd + 1.8, xd + 12.0, xd + 23.0, G['x_lo_cyl_end'] + 1.5], secondary=[xd + 18.0], dilution=[xd + 28.0, xd + 35.0],
                inner_film=[xd + 1.5, xd + 13.0, xd + 25.0, xd + 37.0])
R['air_split'] = {k: v['f'] for k, v in SPLIT.items()}; R['holes'] = HOLES; R['hole_x'] = STATIONS

def gas_state_at(x):
    m = (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']) * MA; hsum = m * h_air(T2)
    for key in ('outer_film', 'inner_film', 'secondary', 'dilution'):
        xs = STATIONS[key]; fr = SPLIT[key]['f'] / len(xs)
        for xx in xs:
            if xx < x: m += fr * MA; hsum += fr * MA * h_air(T2)
    f = MF / m
    return m, f, T_burn(_inv_h(hsum / m), f)
def annulus_area(ro, ri): return math.pi * ((ro * 1e-3) ** 2 - (ri * 1e-3) ** 2)
A_L = annulus_area(G['r_lo_i'], G['r_li_o'])
pen = {}
for key in ('secondary', 'dilution'):
    x = STATIONS[key][0]; m, f, Tg = gas_state_at(x); rg = rho(P_comb, Tg); Ug = (m + MF) / (rg * A_L)
    J = (2 * dP_L) / (rg * Ug ** 2); dj = HOLES[key]['d_mm'] * math.sqrt(SPLIT[key]['Cd'])
    Ymax = 1.15 * dj * math.sqrt(J)                                   # REF Lefebvre (one-sided round jets)
    S = 2 * math.pi * G['r_lo_i'] / (HOLES[key]['n'] / len(STATIONS[key]))
    pen[key] = dict(x=x, T_gas_upstream=Tg, U_gas=Ug, J=J, d_jet=dj, Y_max_mm=Ymax, Y_over_H=Ymax / H_DOME, Holdeman_C=S / H_DOME * math.sqrt(J))
R['jet_penetration'] = pen

# ----------------------------------------------------------------- 4. zones, residence time, loading, pattern factor
x_pz_end, x_sz_end, x_exit = STATIONS['secondary'][0], STATIONS['dilution'][0], G['x_ngv']
def vol(x0, x1):
    n = 40; V = 0.0
    for i in range(n):
        xa = x0 + (x1 - x0) * (i + 0.5) / n
        if xa <= G['x_lo_cyl_end']: ro = G['r_lo_i']
        elif xa <= G['x_lo_cone_end']: ro = G['r_lo_i'] + (G['r_lo_sleeve_i'] - G['r_lo_i']) * (xa - G['x_lo_cyl_end']) / (G['x_lo_cone_end'] - G['x_lo_cyl_end'])
        else: ro = G['r_lo_sleeve_i']
        V += annulus_area(ro, G['r_li_o']) * (x1 - x0) / n * 1e-3
    return V
zones = {}
for nm, (xa, xb) in (('primary', (xd, x_pz_end)), ('secondary', (x_pz_end, x_sz_end)), ('dilution', (x_sz_end, x_exit))):
    V = vol(xa, xb); m, f, Tg = gas_state_at(0.5 * (xa + xb)); rg = rho(P_comb, Tg)
    zones[nm] = dict(x=(xa, xb), V_cm3=V * 1e6, T_gas_K=Tg, phi=f / FAR_ST, m=m, tau_ms=V * rg / (m + MF) * 1e3)
V_tot = vol(xd, x_exit); tau_tot = sum(z['tau_ms'] for z in zones.values())
m_pz, f_pz, T_pz = gas_state_at(x_pz_end - 0.1)
A_ref = annulus_area(G['r_case_i'], G['r_tunnel']); D_ref = (G['r_case_i'] - G['r_tunnel']) * 1e-3
theta = P_plenum ** 1.75 * A_ref * D_ref ** 0.75 * math.exp(T2 / 300.0) / MA      # REF Lefebvre theta (b = 300)
RA = json.load(open(os.path.join(SIM, 'engine', 'e2_results.json')))
theta_A = RA['combustor']['theta_SI']
heat_int = MF * LHV / (V_tot * P_comb / 1e5) / 1e6
q_ref = 0.5 * rho_c * (MA / (rho_c * A_ref)) ** 2
L_over_H = (x_exit - xd) / H_DOME
PF = 1 - math.exp(-1.0 / (0.070 * L_over_H * dP_L / q_ref))                     # REF Lefebvre pattern factor
T_exit_mixed = gas_state_at(200.0)[2]
T_exit_cycle = T_burn(T2, MF / MA, eta=0.97 / 1.02)                         # cycle allowances: burner eta 0.97, 2 % casing heat loss
T_AD_INJ = T_burn(T2, MF / (SPLIT['injectors']['f'] * MA))
R['combustor'] = dict(H_dome_mm=H_DOME, L_liner_mm=x_exit - xd, L_over_H=L_over_H, V_liner_cm3=V_tot * 1e6, zones=zones, tau_total_ms=tau_tot,
                      theta_SI=theta, theta_ratio_to_variant_A=theta / theta_A, heat_release_MW_m3_bar=heat_int, q_ref_Pa=q_ref,
                      dPL_over_qref=dP_L / q_ref, pattern_factor=PF, T_exit_mixed_C=T_exit_mixed - 273.15, T_exit_with_cycle_eta_C=T_exit_cycle - 273.15,
                      T_max_hotstreak_C=T_exit_mixed - 273.15 + PF * (T_exit_mixed - T2), phi_injector=MF / (SPLIT['injectors']['f'] * MA) / FAR_ST,
                      phi_PZ=f_pz / FAR_ST, T_PZ_K=T_pz, T_ad_injector_K=T_AD_INJ)

# ----------------------------------------------------------------- 5. injector (SLM IN625, radial swirler, partially premixed), x7
INJ = dict(n=G['n_inj'], n_vanes=10, vane_angle_deg=45.0, r_vane_exit=9.5, r_sw=13.5, t_vane=0.8, cup_id=16.0, cup_len=6.0,
           centre_body_d=5.0, n_gas_holes=6, dP_gas_bar=0.25, T_gas_K=300.0, Cd_gas=0.75)
m_sw = SPLIT['injectors']['f'] * MA / INJ['n']
Aeff_sw = m_sw / math.sqrt(2 * rho_c * dP_L)
w_thr = (2 * math.pi * INJ['r_vane_exit'] / INJ['n_vanes']) * math.cos(math.radians(INJ['vane_angle_deg'])) - INJ['t_vane']
h_sw = Aeff_sw / 0.75 * 1e6 / (INJ['n_vanes'] * w_thr)
A_cup = math.pi / 4 * (INJ['cup_id'] ** 2 - INJ['centre_body_d'] ** 2) * 1e-6
U_cup = m_sw / (rho_c * A_cup); S_n = 2.0 / 3.0 * math.tan(math.radians(INJ['vane_angle_deg']))
t_premix = INJ['cup_len'] * 1e-3 / U_cup
m_gas_inj = MF / INJ['n']; P_man = P_comb + INJ['dP_gas_bar'] * 1e5; rho_g = rho(P_man, INJ['T_gas_K'], R_NG)
A_gas_eff = m_gas_inj / math.sqrt(2 * rho_g * INJ['dP_gas_bar'] * 1e5)
d_gas = math.sqrt(4 * A_gas_eff / INJ['Cd_gas'] / INJ['n_gas_holes'] / math.pi) * 1e3
phi_inj = MF / (SPLIT['injectors']['f'] * MA) / FAR_ST
SL_inj = S_L(phi_inj, T2, P_comb); u_p = 0.12 * math.hypot(U_cup, U_cup)
S_T = SL_inj * (1 + 1.5 * (u_p / SL_inj) ** 0.7)                     # REF Damkoehler-type fit
alpha = k_air(T2) / (rho_c * cp_air(T2)); tau_w = 0.5 * 0.005 * rho_c * (2 * U_cup ** 2)
g_wall = tau_w / mu_air(T2); g_crit = 2 * SL_inj ** 2 / alpha
tau_ig = tau_ign_SC(phi_inj, T2, P_comb)
V_pz_inj = zones['primary']['V_cm3'] * 1e-6 / INJ['n']
def Da(phi):
    m = (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']) * MA / INJ['n']
    Tpz = T_burn(T2, phi * FAR_ST * SPLIT['injectors']['f'] / (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']))
    tres = V_pz_inj * rho(P_comb, Tpz) / m; sl = S_L(phi, T2, P_comb); al = k_air(T2) / (rho(P_comb, T2) * cp_air(T2))
    return tres / (al / sl ** 2)
phi_lbo = next((1.2 - i * 0.004 for i in range(300) if Da(1.2 - i * 0.004) < 1.0), None)
INJ.update(m_air_g_s=m_sw * 1e3, A_eff_swirler_mm2=Aeff_sw * 1e6, throat_w_mm=w_thr, slot_h_mm=round(h_sw, 2), U_cup=U_cup, swirl_number=S_n,
           premix_time_ms=t_premix * 1e3, m_gas_g_s=m_gas_inj * 1e3, P_manifold_barg=(P_man - P_AMB) / 1e5, d_gas_hole_mm=rnd(d_gas, 0.05),
           d_gas_exact=d_gas, phi_injector=phi_inj, S_L=SL_inj, S_T=S_T, flashback_margin_bulk=U_cup / S_T, flashback_margin_BL=g_wall / g_crit,
           tau_ign_ms=tau_ig * 1e3, autoign_margin=tau_ig / t_premix, Da_design=Da(phi_inj), phi_LBO_Damkoehler=phi_lbo,
           phi_LBO_literature_cold_inlet=0.45)
R['injector'] = INJ

# ----------------------------------------------------------------- 6. liner wall temperatures (Lefebvre & Herbert 1-D, as variant A, coolant at T2)
EPS_W, K_W = 0.80, 22.0; FILM = dict(s=1.5e-3, t_lip=0.8e-3); FILM_DERATE = 0.65
def wall_T(Tg, f_local, lb, film_eta, Ta_film, h_film, Ta_back, h_back, T_sink, Z_back):
    Pk = P_comb / 1e3
    eps_g = 1 - math.exp(-290.0 * Pk * 1.0 * math.sqrt(max(f_local, 1e-6) * lb) * Tg ** -1.5)
    Taw = Tg - film_eta * (Tg - Ta_film); t = 1.0e-3
    def resid(Tw1):
        q = 0.5 * SIG * (1 + EPS_W) * eps_g * Tg ** 1.5 * (Tg ** 2.5 - Tw1 ** 2.5) + h_film * (Taw - Tw1)
        Tw2 = Tw1 - q * t / K_W
        return q - (Z_back * SIG * (Tw2 ** 4 - T_sink ** 4) + h_back * (Tw2 - Ta_back)), Tw2, q
    lo, hi = 300.0, Tg
    for _ in range(80):
        m = 0.5 * (lo + hi); r, _, _ = resid(m)
        if r > 0: lo = m
        else: hi = m
    r, Tw2, q = resid(0.5 * (lo + hi))
    return 0.5 * (lo + hi), Tw2, q, eps_g
def film_params(m_row, r_mm, Ta, dx, m_gas, Tg):
    ra = rho(P_comb, Ta); s = FILM['s']; Ua = m_row / (ra * 2 * math.pi * r_mm * 1e-3 * s)
    rg = rho(P_comb, Tg); Ug = m_gas / (rg * A_L); mb = ra * Ua / (rg * Ug); xs = max(dx, 1e-3) / s
    eta = (1.10 * mb ** 0.65 if mb < 1.3 else 1.28) * (mu_air(Ta) / mu_air(Tg)) ** 0.15 * xs ** -0.2 * (FILM['t_lip'] / s) ** -0.2
    eta = min(eta, 1.0) * FILM_DERATE; Rex = ra * Ua * dx / mu_air(Ta)
    h = 0.069 * k_air(Ta) / dx * Rex ** 0.7 if mb >= 1.3 else 0.10 * k_air(Ta) / dx * Rex ** 0.8 * xs ** -0.36
    return eta, h, mb
def annulus_h(m, ri, ro, T):
    A = annulus_area(ro, ri); Dh = 2 * (ro - ri) * 1e-3
    return 0.020 * k_air(T) / Dh ** 0.2 * (m / (A * mu_air(T))) ** 0.8          # REF Lefebvre annulus correlation
def liner_profile(side):
    rows = STATIONS['outer_film'] if side == 'outer' else STATIONS['inner_film']
    m_row = SPLIT[side + '_film']['f'] * MA / len(rows)
    r_mm = G['r_lo_i'] if side == 'outer' else G['r_li_o']
    lb = 3.4 * vol(xd, x_exit) / (2 * math.pi * (G['r_lo_i'] + G['r_li_o']) * 1e-3 * (x_exit - xd) * 1e-3)
    out = []
    for x in [xd + 0.5 + i * 0.5 for i in range(int((x_exit - xd - 1) / 0.5))]:
        prev = [r for r in rows if r <= x]
        if not prev: continue
        dx = (x - max(prev)) * 1e-3 + 2e-3
        m, f, Tg = gas_state_at(x)
        if x < STATIONS['secondary'][0]: Tg = Tg + 0.5 * (T_AD_INJ - Tg)     # PZ: swirl flames reach the walls
        eta, hC1, mb = film_params(m_row, r_mm, T2, dx, m + MF, Tg)
        if side == 'outer':
            m_an = (SPLIT['outer_film']['f'] + SPLIT['secondary']['f'] + SPLIT['dilution']['f']) * MA * 0.6
            hb = annulus_h(m_an, G['r_lo_o'], G['r_case_i'], T2)
            Z = 1 / (1 / EPS_W + (G['r_lo_o'] / G['r_case_i']) * (1 / 0.6 - 1))
            Tw1, Tw2, q, eg = wall_T(Tg, f, lb, eta, T2, hC1, T2, hb, T2 + 80, Z)
        else:
            m_b = (SPLIT['inner_film']['f'] + SPLIT['ngv_purge']['f']) * MA
            hb = annulus_h(m_b, G['r_shield_i'] + G['t_shield'], G['r_li_i'], T2)
            Z = 1 / (1 / EPS_W + (G['r_li_i'] / G['r_shield_i']) * (1 / 0.5 - 1))
            Tw1, Tw2, q, eg = wall_T(Tg, f, lb, eta, T2, hC1, T2, hb, T2 + 150, Z)
        out.append(dict(x=x, Tg=Tg, Tw=Tw1, eta=eta, eps_g=eg))
    return out
prof_out, prof_in = liner_profile('outer'), liner_profile('inner')
R['liner_thermal'] = dict(outer_Tw_max_C=max(p['Tw'] for p in prof_out) - 273.15, inner_Tw_max_C=max(p['Tw'] for p in prof_in) - 273.15,
                          outer_profile=[(round(p['x'], 1), round(p['Tg'] - 273.15), round(p['Tw'] - 273.15), round(p['eta'], 2)) for p in prof_out[::6]],
                          inner_profile=[(round(p['x'], 1), round(p['Tg'] - 273.15), round(p['Tw'] - 273.15), round(p['eta'], 2)) for p in prof_in[::6]],
                          material='Hastelloy X 2.4665 (VDM Nicrofer 4722Co), t = 1.0 mm', limit_C=850.0, variant_A_outer_C=RA['liner_thermal']['outer_Tw_max_C'])

# ----------------------------------------------------------------- 7. casing temperature, pressure design, flanges, insulation
T_lo_mean = sum(p['Tw'] for p in prof_out) / len(prof_out) - 20
h_c = annulus_h(0.6 * MA, G['r_lo_o'], G['r_case_i'], T2)
Tc = 500.0
for _ in range(4000):
    Z = 1 / (1 / EPS_W + (G['r_lo_o'] / G['r_case_i']) * (1 / 0.6 - 1))
    Tc += 1e-3 * (Z * SIG * (T_lo_mean ** 4 - Tc ** 4) * G['r_lo_o'] / G['r_case_i'] - h_c * (Tc - T2) - 150.0)
PS = 0.30                                                                    # MPa gauge design pressure (as variant A)
def f_aust(Rp1, Rm): return max(Rp1 / 1.5, min(Rp1 / 1.2, Rm / 3.0))       # EN 13445-3 austenitic, A >= 35 %
f_case = f_aust(140.0, 430.0)                                                # 1.4404 at ~250 C (EN 10028-7, approx.)
z_w = 0.85
e_req = PS * 2 * G['r_case_i'] / (2 * f_case * z_w - PS)
def flange(G_mm, N_mm, n_b, d_b, lever_mm, t_mm, f_fl, S_bolt):
    b = min(N_mm / 2, 6.35); Gm = G_mm * 1e-3
    Wm1 = math.pi / 4 * Gm ** 2 * PS * 1e6 + 2 * b * 1e-3 * math.pi * Gm * 2.0 * PS * 1e6; Wm2 = math.pi * b * 1e-3 * Gm * 20e6
    W = max(Wm1, Wm2); A_root = {8: 32.8, 10: 52.3, 6: 17.9}[d_b] * 1e-6
    sig = 6 * (W * lever_mm * 1e-3 / (2 * math.pi * (G_mm / 2 + lever_mm) * 1e-3)) / (t_mm * 1e-3) ** 2 / 1e6
    return dict(W_kN=W / 1e3, bolt_area_req_mm2=W / (S_bolt * 1e6) * 1e6, bolt_area_avail_mm2=n_b * A_root * 1e6, sigma_ring_MPa=sig, f_allow_MPa=f_fl,
                ok=(n_b * A_root >= W / (S_bolt * 1e6)) and sig <= 1.5 * f_fl)
G['gasket_mid_r'] = (G['r_case_i'] + 0.5, G['r_case_i'] + 5.0)
FL_MID = flange(sum(G['gasket_mid_r']), 4.5, G['n_mid_bolts'], 8, G['pcd_mid'] / 2 - 0.5 * sum(G['gasket_mid_r']), 6.0, f_case, 160.0)
FL_E3 = flange(sum(G['gasket_e3_r']), 8.0, G['n_e3_bolts'], 8, G['pcd_e3'] / 2 - 0.5 * sum(G['gasket_e3_r']), 12.0, f_aust(118.0, 380.0), 130.0)
def k_micro(Tm_C): return 0.020 + 3.0e-5 * Tm_C
def skin(r_in, T_in, t, T_amb=45.0, h=20.0, eps=0.3):
    ri, ro = r_in * 1e-3, (r_in + t) * 1e-3; Ts = T_amb + 20
    for _ in range(300):
        k = k_micro(0.5 * (T_in + Ts)); ql = 2 * math.pi * k * (T_in - Ts) / math.log(ro / ri)
        Ts += 0.02 * (ql - 2 * math.pi * ro * (h * (Ts - T_amb) + eps * SIG * ((Ts + 273.15) ** 4 - (T_amb + 273.15) ** 4)))
    return Ts, ql
Ts_rear, ql_rear = skin(G['r_case_i'] + G['t_case'], Tc - 273.15, G['insulation']['rear'])
Q_case = ql_rear * 0.066 * 1.6 + 2 * math.pi * 0.075 * 0.04 * 20 * (T2 - 273.15 - 45) * 1.5     # insulated rear casing + bare front casing
R['casing'] = dict(T_casing_C=Tc - 273.15, h_casing=h_c, material='1.4404 (316L) throughout (cold side 165 C, metal ~%.0f C)' % (Tc - 273.15),
                   PS_MPa=PS, f_MPa=f_case, e_req_mm=e_req, e_chosen=G['t_case'], test_pressure_barg=1.43 * PS * 10,
                   PED='PS x V = %.1f bar.L < 25 -> PED Art. 4(3)' % (PS * 10 * math.pi * (G['r_case_i'] * 1e-2) ** 2 * 1.30),
                   flange_mid=FL_MID, flange_E2E3=FL_E3, insulation_rear_mm=G['insulation']['rear'], skin_rear_C=Ts_rear, Q_loss_W=Q_case)

# ----------------------------------------------------------------- 8. cycle effect of the E2-B pressure loss (concept_study.cycle, eps 0)
def cycle_b(dp_comb):
    c = dict(GT, ma=MA, T_amb=288.15); e = c
    T1, P1 = 288.15, P_AMB * 0.99; T2_ = T1 * (1 + (e['PR'] ** cs.EX_A - 1) / e['eta_c']); w_c = cs.CP_A * (T2_ - T1)
    P3 = P1 * e['PR'] * (1 - dp_comb); P_exit = P_AMB * (1 + 0.015 + 0.005)
    f = cs.CP_G * (TIT - T2_) / (0.97 * LHV) * 1.02
    w_t = w_c / (0.985 * (1 + f)); T4 = TIT - w_t / cs.CP_G
    P4 = P3 * ((TIT - w_t / (cs.CP_G * e['eta_t'])) / TIT) ** (1 / cs.EX_G) * (1 - 0.015)
    w_pt = e['eta_pt'] * cs.CP_G * T4 * (1 - (P_exit / P4) ** cs.EX_G)
    return MA * (1 + f) * w_pt * 0.985
P_sh0, P_sh1 = cycle_b(0.045), cycle_b((P2 - P_comb) / P2 + 0.006)          # + NGV entry 0.6 %
R['cycle'] = dict(P_shaft_cycle_kW=P_sh0 / 1e3, P_shaft_E2B_kW=P_sh1 / 1e3, dP_shaft_kW=(P_sh1 - P_sh0) / 1e3,
                  dp_E2B_incl_NGV_entry_pct=((P2 - P_comb) / P2 + 0.006) * 100, note='fuel unchanged at fixed TIT; the FPT expansion ratio carries the loss')

# ----------------------------------------------------------------- 9. thermal growth, gas manifold, light-off
A17, A16 = 17.0e-6, 16.0e-6
GR = {'casing axial (front foot x 8 -> rear ring x 113)': (113 - 8) * A17 * (Tc - 293),
      'core intake-outer lip -> NGV rib': (99.3 + 17.33) * 23.5e-6 * 110 + 10 * 15e-6 * 680,
      'liner radial outer r55': 55 * A16 * (max(p['Tw'] for p in prof_out) - 293),
      'casing radial r75': 75 * A17 * (Tc - 293),
      'rear ring bore (1.4404) vs NGV rib r37.95 (IN713LC ~720 C), growth difference': G['r_rear_bore'] * A17 * (Tc - 293 + 60) - 37.95 * 15.5e-6 * (720 + 273 - 293)}
GR['rear bore / NGV rib hot radial clearance'] = (G['r_rear_bore'] - G['r_ngv_rib']) + GR['rear ring bore (1.4404) vs NGV rib r37.95 (IN713LC ~720 C), growth difference']
GR['rear seal ring travel on NGV land'] = GR['casing axial (front foot x 8 -> rear ring x 113)'] - GR['core intake-outer lip -> NGV rib']
R['thermal_growth_mm'] = GR
rho_ng = rho(P_man, 300.0, R_NG); Q_ng = MF / rho_ng
def v_in(d_mm): return Q_ng / (math.pi / 4 * (d_mm * 1e-3) ** 2)
GAS = dict(P_manifold_barg=(P_man - P_AMB) / 1e5, supply_min_barg=3.5, regulator_margin_bar=3.5 - (P_man - P_AMB) / 1e5, Nm3_h=MF / 0.717 * 3600,
           feed='Ø%.0fx%.1f 316L, DIN 2353 L%.0f' % (G['d_feed'], G['t_feed'], G['d_feed']), V_feed=v_in(G['d_feed'] - 2 * G['t_feed']),
           ring='torus Ø%.0fx%.0f r %.1f x %.1f' % (G['d_manifold'], G['t_manifold'], G['r_manifold'], G['x_manifold']),
           V_ring_half=v_in(G['d_manifold'] - 2 * G['t_manifold']) / 2, V_stem=v_in(G['d_stem'] - 2 * G['t_stem']) / G['n_inj'],
           maldistribution_pct=100 * 0.5 * rho_ng * (v_in(G['d_manifold'] - 2 * G['t_manifold']) / 2) ** 2 / (INJ['dP_gas_bar'] * 1e5) / 2,
           note='2.7 x the variant-A fuel: torus 12x1 (A: 8x0.8), stems 8x1 (A: 6x0.8), feed 12x1 (A: 10x1), 6 gas holes per injector (A: 4)')
R['gas'] = GAS
LO = dict(N1_rpm=40e3, ma=0.075, P3_bar=1.25, T3_C=30.0, fuel_g_s=0.90)                  # ASSUMPTION starter-assisted light-off
LO['phi_injector'] = LO['fuel_g_s'] * 1e-3 / (SPLIT['injectors']['f'] * LO['ma']) / FAR_ST
LO['phi_overall'] = LO['fuel_g_s'] * 1e-3 / LO['ma'] / FAR_ST
LO['U_cup'] = U_cup * (LO['ma'] / MA) * (rho_c / rho(LO['P3_bar'] * 1e5, LO['T3_C'] + 273.15))
LO['S_L'] = S_L(min(LO['phi_injector'], 1.4), LO['T3_C'] + 273.15, LO['P3_bar'] * 1e5)
LO['T_after_lightoff_C'] = T_burn(LO['T3_C'] + 273.15, LO['fuel_g_s'] * 1e-3 / LO['ma']) - 273.15
LO['note'] = 'same exciter/plug as variant A (IGN-630); light-off fuel raised to 0.9 g/s because 35 % of the air passes the injectors (A: 14 %)'
R['ignition'] = LO

# ----------------------------------------------------------------- 10. outputs
G['holes'] = {k: dict(n=HOLES[k]['n'], d=HOLES[k]['d_mm'], x=STATIONS.get(k)) for k in ('outer_film', 'secondary', 'dilution', 'inner_film', 'dome_cool')}
G['injector'] = dict(x_union=G['x_bh_back'], x_backplate=(G['x_bh_back'] + 6.0, G['x_bh_back'] + 9.0), n=INJ['n'], r=G['r_inj'], cup_id=INJ['cup_id'],
                     cup_len=INJ['cup_len'], cb_d=INJ['centre_body_d'], n_vanes=INJ['n_vanes'], vane_angle=INJ['vane_angle_deg'],
                     r_vane_exit=INJ['r_vane_exit'], r_sw=INJ['r_sw'], slot_h=INJ['slot_h_mm'], n_gas=INJ['n_gas_holes'], d_gas=INJ['d_gas_hole_mm'])
R['geometry'] = G
json.dump(G, open(os.path.join(HERE, 'e2b_design.json'), 'w'), indent=1, default=str)
json.dump(R, open(os.path.join(HERE, 'e2b_results.json'), 'w'), indent=1, default=str)

def P(*a): print(*a)
if __name__ == '__main__':
    d = R['design_point']; p = R['pressure']
    P('=== GR180 variant B  E2-B simple-cycle combustor - 115k / TIT 800 C / 15 C (concept_study.cycle, eps 0) ===')
    P('air %.3f kg/s  fuel %.3f g/s (%.1f kW)  T2 %.1f C  P2 %.3f bar  phi_overall %.3f  FPT exit %.0f C' % (d['ma'], d['mf'] * 1e3, d['Q_fuel_kW'], d['T2_C'], d['P2_bar'], d['phi_overall'], d['T_FPT_exit_C']))
    P('\n-- pressure --  channels %.0f m/s (q %.1f kPa): wakes %.2f + dump %.2f + carrier windows %.2f (%.0f m/s) kPa -> plenum %.3f bar -> liner %.1f %% -> combustor %.3f bar'
      % (p['V_channels'], p['q_channels_kPa'], p['dP_wakes_kPa'], p['dP_dump_kPa'], p['dP_windows_kPa'], p['V_windows'], p['P_plenum'], p['dP_liner_pct'], p['P_combustor']))
    P('   total %.2f %% (cycle budget 4.5 %%, cycle P3 %.3f bar); pure-dump upper bound %.1f kPa' % (p['dp_total_pct'], p['P3_cycle'], p['upper_bound_pure_dump_kPa']))
    P('\n-- air split / holes --  (jets %.0f m/s)' % V_jet)
    for k, v in HOLES.items():
        P('  %-11s %5.1f %%  n %3d  d %s mm  A_geom %.0f mm2' % (k, v['frac'] * 100, v['n'], ('%.2f' % v['d_mm']) if v['d_mm'] else 'swirler', v['A_geom_mm2']))
    for k, v in pen.items(): P('  %s jets: J %.0f, Ymax/H %.2f, Holdeman C %.2f' % (k, v['J'], v['Y_over_H'], v['Holdeman_C']))
    c = R['combustor']
    P('\n-- combustor --  tau %.2f ms, theta %.2e (%.2f x variant A), %.0f MW/m3bar, PF %.3f, T exit %.1f C (eta_b 0.97 + 2 %% loss: %.1f C), hot streak %.0f C, phi_inj %.2f, phi_PZ %.2f, T_PZ %.0f K'
      % (c['tau_total_ms'], c['theta_SI'], c['theta_ratio_to_variant_A'], c['heat_release_MW_m3_bar'], c['pattern_factor'], c['T_exit_mixed_C'], c['T_exit_with_cycle_eta_C'], c['T_max_hotstreak_C'],
         c['phi_injector'], c['phi_PZ'], c['T_PZ_K']))
    for k, z in c['zones'].items(): P('   %-9s V %4.0f cm3  phi %.2f  T %4.0f K  tau %.2f ms' % (k, z['V_cm3'], z['phi'], z['T_gas_K'], z['tau_ms']))
    i = R['injector']
    P('\n-- injector x7 --  air %.1f g/s, slot h %.2f mm, cup ID %.0f U %.0f m/s, S %.2f | gas %.3f g/s, %d x d%.2f, manifold %.2f barg'
      % (i['m_air_g_s'], i['slot_h_mm'], i['cup_id'], i['U_cup'], i['swirl_number'], i['m_gas_g_s'], i['n_gas_holes'], i['d_gas_hole_mm'], i['P_manifold_barg']))
    P('   flashback bulk %.1f BL %.1f, autoign margin %.1e, Da %.1f, phi_LBO Da %.2f (literature, cold inlet ~0.45)' % (i['flashback_margin_bulk'], i['flashback_margin_BL'], i['autoign_margin'], i['Da_design'], i['phi_LBO_Damkoehler'] or -1))
    lt = R['liner_thermal']; cs_ = R['casing']
    P('\n-- liner --  outer Tw max %.0f C (variant A %.0f), inner %.0f C' % (lt['outer_Tw_max_C'], lt['variant_A_outer_C'], lt['inner_Tw_max_C']))
    P('-- casing --  %.0f C, e_req %.2f mm (3.0), mid flange %s, E2/E3 flange %s, skin %.0f C, loss %.0f W'
      % (cs_['T_casing_C'], cs_['e_req_mm'], cs_['flange_mid']['ok'], cs_['flange_E2E3']['ok'], cs_['skin_rear_C'], cs_['Q_loss_W']))
    cy = R['cycle']
    P('-- cycle --  shaft %.2f kW (cycle model %.2f): %+.2f kW for dp %.2f %%' % (cy['P_shaft_E2B_kW'], cy['P_shaft_cycle_kW'], cy['dP_shaft_kW'], cy['dp_E2B_incl_NGV_entry_pct']))
    g = R['gas']
    P('-- gas --  manifold %.2f barg (margin %.2f), %.1f Nm3/h, feed %.1f m/s, ring %.1f m/s, stems %.1f m/s, maldistribution %.2f %%'
      % (g['P_manifold_barg'], g['regulator_margin_bar'], g['Nm3_h'], g['V_feed'], g['V_ring_half'], g['V_stem'], g['maldistribution_pct']))
    P('-- light-off --  phi_inj %.2f, cup U %.1f m/s, T after %.0f C' % (LO['phi_injector'], LO['U_cup'], LO['T_after_lightoff_C']))
    P('-- growth (mm) --  ' + ', '.join('%s %+.2f' % kv for kv in GR.items()))
    P('\nwritten: sim/variant_b/e2b_design.json, sim/variant_b/e2b_results.json')
