#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP  E2 - recuperated combustion section: collector, bulkhead, combustor, pressure casing.

Pure python (no numpy).  Run:   python3 sim/engine/e2_combustor_calc.py
Writes:  sim/engine/e2_design.json   (geometry + hole pattern read by cad/engine/combustor_casing.py)
         sim/engine/e2_results.json  (all calculated values, used by docs/engine/E2_combustor_casing.md)

Design point = docs/06 sec.2 (continuous): 115k rpm, TIT 800 C, intake 15 C, 50 m, target efficiencies,
taken from sim/life_study.point() so E2 is consistent with the project cycle.
Frame: ENG (mm), x = tunnel front face, +x downstream, y north, z up.
Every correlation and every assumption is marked  # ASSUMPTION / # REF in the code.
"""
import math, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); SIM = os.path.dirname(HERE)
sys.path.insert(0, SIM)
import concept_study as cs   # noqa: E402  (project cycle)
import life_study as ls      # noqa: E402

SIG = 5.670e-8; RU = 8.314; R_AIR = 287.05; R_NG = 518.3
LHV = cs.LHV                 # 50 MJ/kg (project value; methane)
FAR_ST = 0.0584              # stoichiometric fuel/air, methane            # ASSUMPTION NG ~ CH4
CP_NG = 2450.0               # J/kgK natural gas ~400 K

# ----------------------------------------------------------------- properties of air / lean products
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
def h_air(T): return _interp(_H, T)            # J/kg rel. 298 K
def h_prod(T, f): return h_air(T) * (1 + 1.2 * f)   # ASSUMPTION lean CH4 products: cp ~ cp_air (1+1.2 f) (+4 % at phi 0.6)
def mu_air(T): return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)   # Sutherland
def k_air(T): return 0.0241 * (T / 273.15) ** 0.81                                     # fit, +-4 % 300-1500 K
def rho(P, T, R=R_AIR): return P / (R * T)

def T_burn(T_air, f, T_fuel=400.0, eta=1.0):
    """mixed-out adiabatic temperature of air at T_air + fuel/air ratio f (complete combustion, no dissociation)."""
    rhs = h_air(T_air) + f * (eta * LHV + CP_NG * (T_fuel - 298.0))
    lo, hi = 250.0, 2600.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if (1 + f) * h_prod(m, f) > rhs: hi = m
        else: lo = m
    return 0.5 * (lo + hi)

def S_L(phi, T, P):
    """laminar burning velocity CH4/air, Guelder (1984) fit, m/s; P in Pa.   REF Guelder, SAE 841000"""
    W, eta_, xi, a, b = 0.422, 0.15, 5.18, 2.0, -0.5
    return W * phi ** eta_ * math.exp(-xi * (phi - 1.075) ** 2) * (T / 300.0) ** a * (P / 101325.0) ** b

def tau_ign_SC(phi, T, P):
    """CH4 ignition delay, Spadaccini & Colket (1994) shock-tube fit, s.  Extrapolated below 1300 K (see doc)."""
    X_ch4 = phi / (9.52 + phi); X_o2 = 0.21 * (1 - X_ch4); C = P / (RU * T) * 1e-6   # mol/cm3
    return 1.77e-14 * math.exp(18693.0 / T) * (X_o2 * C) ** -1.05 * (X_ch4 * C) ** 0.66

# ----------------------------------------------------------------- 0. design point (project cycle)
DP = ls.point(115e3, 800, 'target', T_amb_C=15.0, alt_m=50.0, booster=False)
MA = DP['ma']; MF = DP['mf']; T2 = DP['T2']; T2R = DP['T2r']; TIT = 800 + 273.15
P_AMB = 101325.0 * (1 - 2.25577e-5 * 50.0) ** 5.25588
P2 = P_AMB * 0.99 * DP['PR']                  # compressor exit total (cycle definition: inlet loss 1 %)
P2R_CYCLE = P2 * (1 - 0.025)                  # recuperator cold side 2.5 % (cycle)
P3_CYCLE = DP['P3']                           # cycle: -4.5 % "combustor"  -> 2.874 bar
R = {}                                        # results
R['design_point'] = dict(ma=MA, mf=MF, T2_C=T2 - 273.15, T2r_C=T2R - 273.15, TIT_C=800.0, P2_bar=P2 / 1e5,
                         P2r_bar=P2R_CYCLE / 1e5, P3_bar=P3_CYCLE / 1e5, PR=DP['PR'], P_el_kW=DP['P_el'] / 1e3,
                         eta_el=DP['eta_el'], Q_fuel_kW=MF * LHV / 1e3, FAR=MF / MA, phi_overall=MF / MA / FAR_ST)

# ----------------------------------------------------------------- 1. geometry (ENG mm) - single source for the CAD
G = dict(
    # core references (build_gr180.py v13A, read-only)
    x_io_lip=-17.33, x_io_step=-11.33, x_io_end=-4.85, r_io_lip_o=53.0, r_io_lip_i=51.0, r_core=53.5,
    x_ch_exit=7.6, r_ch_i=45.5, r_ch_o=53.5, A_ch=13 * 113.63, n_ch=13,
    r_tunnel=10.5, x_tunnel_tube=(16.53, 92.96), r_tunnel_bore=8.5,
    x_ngv=94.8, r_ngv_o=36.35, r_ngv_rib=37.95, x_ngv_rib=(109.3, 110.8), x_ngv_end=118.8, r_ngv_in_i=21.25, r_ngv_in_o=22.25,
    x_ngv_inner_end=109.8, x_turb_exit=118.3, x_nut_end=126.8,
    # E2 collector (cold, 1.4404)
    x_drum_front=-30.0, t_front_wall=4.0, r_front_ring_o=60.0, r_lip_i=51.5, x_ring_lip=-20.33,
    r_drum_i=118.0, t_drum=2.5, x_mid_A=(14.0, 20.0), r_flange_o=138.0, pcd_mid=256.0, n_mid_bolts=16, d_mid_bolt=8,
    oring_x=-8.0,
    # bulkhead + insulation
    x_bh=21.0, t_bh=6.0, t_gasket=1.0, t_bh_ins=4.0, r_bh_bore=21.35, r_bh_hub_o=24.5, x_bh_hub_end=35.0,
    gas_entry_deg=180.0, r_gas_boss=(138.5, 158.0), rib_x=(14.0, 21.0), rib_w=10.0,
    # hot casing (1.4948)
    r_case_i=85.0, t_case=3.0, x_case_shell_end=100.0, t_rear_plate=5.0, r_rear_bore=38.1,
    x_rear_ring=(100.0, 116.0), x_e3_flange=(106.0, 116.0), r_e3_flange_o=88.0, pcd_e3=160.0, n_e3_bolts=16,
    e3_spigot_d=120.0, e3_spigot_depth=3.0, seal_groove_x=(112.5, 114.5), r_seal_groove=40.0,
    # combustor
    x_dome=42.9, t_dome=1.2, t_liner=1.0, r_li_o=21.1, r_lo_i=54.0, x_li_front=28.0, x_li_end=98.0,
    x_lo_cyl_end=82.0, x_lo_cone_end=92.0, r_lo_sleeve_i=36.5, x_lo_end=106.5,
    n_inj=8, r_inj=37.5, inj_a0_deg=0.0,
    r_baffle=68.0, t_baffle=0.8, x_baffle=(54.0, 96.0),
    # tunnel heat shield
    r_shield_i=17.3, t_shield=0.3, x_shield=(17.5, 92.0),
    # manifold
    x_manifold=17.5, r_manifold=37.5, d_manifold=7.0,
)
G['x_bh_back'] = G['x_bh'] + G['t_bh']                                   # 24.0
G['x_hot_flange'] = (G['x_bh_back'] + G['t_gasket'], G['x_bh_back'] + G['t_gasket'] + 6.0)   # 28..34
G['x_dome_hot'] = G['x_dome'] + G['t_dome']
G['r_lo_o'] = G['r_lo_i'] + G['t_liner']; G['r_li_i'] = G['r_li_o'] - G['t_liner']
H_DOME = G['r_lo_i'] - G['r_li_o']                                        # combustor annulus height (mm)

# ----------------------------------------------------------------- 2. pressure budget, collector aero
rho2 = rho(P2, T2)
A_ch = G['A_ch'] * 1e-6
V_ch = MA / (rho2 * A_ch); q_ch = 0.5 * rho2 * V_ch ** 2
# turning gap channel exit -> bulkhead face (radial turn into the drum) ; toroidal turning fairing on the bulkhead
gap = G['x_bh'] - G['x_ch_exit']
A_turn = 2 * math.pi * G['r_ch_o'] * gap * 1e-6
# toroidal turning fairing R8.5 on the bulkhead face (centre x21, r44) + front disc r60->70 at x7.6 = faired 90 deg bend
# followed by a vaneless radial diffuser (width = gap) to r70, then dump into the drum.
A_ann = math.pi * ((G['r_ch_o'] * 1e-3) ** 2 - (G['r_ch_i'] * 1e-3) ** 2)          # 2488 mm2 geometric annulus
q_ann = 0.5 * rho2 * (MA / (rho2 * A_ann)) ** 2
dP_mix = (1 - A_ch / A_ann) ** 2 * q_ch                                          # Borda-Carnot: 13 channel jets -> full annulus (land wakes)
A_r70 = 2 * math.pi * 0.070 * gap * 1e-3; q_r70 = 0.5 * rho2 * (MA / (rho2 * A_r70)) ** 2
dP_bend = 0.15 * q_ann + 0.20 * (q_ann - q_r70)                                  # ASSUMPTION faired bend K 0.15 + radial diffuser eff. 0.8 (Idelchik)
dP_turn = dP_mix + dP_bend + q_r70                                               # + dump of the r70 velocity into the drum
K_turn = dP_turn / q_ch
# drum: circumferential collection to C1 (two halves), then box exit and rect->DN100 transition (diffuser)
A_drum_half = (G['x_mid_A'][0] - G['x_drum_front'] - G['t_front_wall']) * (G['r_drum_i'] - G['r_front_ring_o'] - 2.5) * 1e-6
V_drum = MA / rho2 / (2 * A_drum_half); q_drum = 0.5 * rho2 * V_drum ** 2
C1_BOX = dict(x=(-26.0, 12.0), z=(-150.0, -30.0))          # rectangular collector exit (mm), +y direction
A_box = (C1_BOX['x'][1] - C1_BOX['x'][0]) * (C1_BOX['z'][1] - C1_BOX['z'][0]) * 1e-6
V_box = MA / rho2 / A_box; q_box = 0.5 * rho2 * V_box ** 2
DN100_ID = 114.3 - 2 * 3.05; A_dn100 = math.pi / 4 * (DN100_ID * 1e-3) ** 2
V_c1 = MA / rho2 / A_dn100; q_c1 = 0.5 * rho2 * V_c1 ** 2
dP_drum = 0.4 * q_box + 0.5 * q_drum             # ASSUMPTION collector (scroll-less plenum): acceleration/mixing into the C1 box
dP_c1_diff = (1 - 0.55) * (q_box - q_c1)         # rect->round transition AR %.1f, diffuser eff. 0.55
dP_coll = dP_turn + dP_drum + dP_c1_diff
dp_coll = dP_coll / P2
# alternative: no fairing, pure dump of the channel jets (upper bound)
dP_coll_dump = q_ch + dP_drum + dP_c1_diff
R['collector'] = dict(V_channels=V_ch, q_channels_kPa=q_ch / 1e3, turn_gap_mm=gap, K_turn=K_turn, dP_mix_wakes_kPa=dP_mix / 1e3, V_r70=MA / rho2 / A_r70, A_turn_mm2=A_turn * 1e6, V_turn=MA / rho2 / A_turn,
                      V_drum=V_drum, V_box=V_box, A_box_mm2=A_box * 1e6, V_C1_DN100=V_c1, dP_turn_kPa=dP_turn / 1e3, dP_drum_kPa=dP_drum / 1e3,
                      dP_C1_transition_kPa=dP_c1_diff / 1e3, dP_total_kPa=dP_coll / 1e3, dp_total_pct=dp_coll * 100,
                      dP_upper_bound_pure_dump_kPa=dP_coll_dump / 1e3, P_C1_bar=(P2 - dP_coll) / 1e5)

# hot side: recuperator returns at C2 (E4 budget 2.5 %), dump of the C2 port jet, perforated baffle
P_C2 = (P2 - dP_coll) * (1 - 0.025)
rhoR = rho(P_C2, T2R)
C2_BOX = dict(x=(36.0, 100.0), z=(15.0, 130.0))
A_c2box = (C2_BOX['x'][1] - C2_BOX['x'][0]) * (C2_BOX['z'][1] - C2_BOX['z'][0]) * 1e-6
DN125_ID = 139.7 - 2 * 3.4; A_dn125 = math.pi / 4 * (DN125_ID * 1e-3) ** 2
m_hot_guess = 0.94 * MA
V_c2 = m_hot_guess / rhoR / A_dn125; V_c2box = m_hot_guess / rhoR / A_c2box
dP_c2 = 0.2 * (0.5 * rhoR * V_c2box ** 2 - 0.5 * rhoR * V_c2 ** 2) + 0.5 * rhoR * V_c2box ** 2   # contraction + dump of the port jet
BAFFLE_OPEN = 0.40
A_baffle = 2 * math.pi * G['r_baffle'] * (G['x_baffle'][1] - G['x_baffle'][0]) * 1e-6 * BAFFLE_OPEN
V_baf = 0.70 * m_hot_guess / rhoR / A_baffle      # ~70 % of the hot air passes the perforated baffle (rest around its front end)
dP_baf = 1.6 * 0.5 * rhoR * V_baf ** 2 * 0.0 + 1.6 * 0.5 * rhoR * V_baf ** 2   # ASSUMPTION K=1.6 perforated plate 40 % open (Idelchik)
P_plenum = P_C2 - dP_c2 - dP_baf
DPL_HOT = 0.028                                    # design liner pressure drop / P_plenum  (hot side)
P_comb = P_plenum * (1 - DPL_HOT)
P_cold_annulus = P2 - dP_turn - 0.3 * dP_drum      # inner annulus is fed directly from the collector plenum
dP_inner = P_cold_annulus - P_comb
q_ngv = None
R['pressure'] = dict(P2=P2 / 1e5, P_C1=(P2 - dP_coll) / 1e5, P_C2=P_C2 / 1e5, dP_C2_port_kPa=dP_c2 / 1e3, V_C2_DN125=V_c2,
                     V_C2_port=V_c2box, A_C2_port_mm2=A_c2box * 1e6, dP_baffle_kPa=dP_baf / 1e3, V_baffle_holes=V_baf,
                     P_hot_plenum=P_plenum / 1e5, P_combustor=P_comb / 1e5, P_cold_inner_annulus=P_cold_annulus / 1e5,
                     dP_liner_hot_pct=DPL_HOT * 100, dP_liner_cold_side_pct=dP_inner / P_comb * 100,
                     dP_bulkhead_bar=(P_cold_annulus - P_plenum) / 1e5)

# ----------------------------------------------------------------- 3. air split, liner holes
# fractions of compressor air MA.  'src' hot = recuperated (566 C) air, cold = compressor air (165 C, bypasses recuperator)
SPLIT = dict(
    injectors=dict(f=0.140, src='hot', Cd=0.75, n=G['n_inj']),          # radial swirlers, partially premixed
    dome_cool=dict(f=0.030, src='hot', Cd=0.65, n=64),                    # effusion around the 8 cups (8 x 8)
    outer_film=dict(f=0.100, src='hot', Cd=0.65, n=4 * 56),               # 4 splash-cooled film rings
    secondary=dict(f=0.120, src='hot', Cd=0.61, n=24),                    # 3 per injector
    dilution=dict(f=None, src='hot', Cd=0.61, n=2 * 24),                  # remainder of hot air
    inner_film=dict(f=0.040, src='cold', Cd=0.65, n=4 * 16),              # cold bypass air (inner liner), 4 rows x 16
    leak_cold=dict(f=0.004, src='cold'),                                  # bulkhead piston ring 0.15 %, 8 stem grommets 0.15 %, UV purge 0.1 %
    ngv_purge=dict(f=0.008, src='cold'),                                  # inner cavity -> NGV inner ring / disc (as original GR180)
)
def beta_of(S): return sum(v['f'] for v in S.values() if v['src'] == 'cold' and v['f'] is not None)
def complete_split(S):
    S['dilution']['f'] = 1.0 - sum(v['f'] for k, v in S.items() if k != 'dilution')
    return S
complete_split(SPLIT)
rho_hot = rho(P_plenum, T2R); rho_cold = rho(P_cold_annulus, T2 + 40)
dP_hot = P_plenum - P_comb; dP_cold = P_cold_annulus - P_comb
HOLES = {}
for k, v in SPLIT.items():
    if 'Cd' not in v: continue
    rh, dp = (rho_hot, dP_hot) if v['src'] == 'hot' else (rho_cold, dP_cold)
    m = v['f'] * MA; Aeff = m / math.sqrt(2 * rh * dp); Ag = Aeff / v['Cd']
    d = math.sqrt(4 * Ag / v['n'] / math.pi) * 1e3 if k != 'injectors' else None
    HOLES[k] = dict(frac=v['f'], m=m, A_eff_mm2=Aeff * 1e6, A_geom_mm2=Ag * 1e6, n=v['n'], d_mm=d, V_jet=math.sqrt(2 * dp / rh))
# round to manufacturable diameters
def rnd(d, step=0.1): return round(d / step) * step
for k in ('dome_cool', 'outer_film', 'secondary', 'dilution', 'inner_film'):
    HOLES[k]['d_mm'] = rnd(HOLES[k]['d_mm'], 0.1)
R['combustor_T_ad_injector_K'] = None
# hole axial stations (ENG x, mm)
xd = G['x_dome_hot']
STATIONS = dict(outer_film=[xd + 1.8, xd + 12.0, xd + 23.0, G['x_lo_cyl_end'] + 1.5],
                secondary=[xd + 18.0], dilution=[xd + 28.0, xd + 35.0],
                inner_film=[xd + 1.5, xd + 13.0, xd + 25.0, xd + 37.0])
R['air_split'] = {k: v['f'] for k, v in SPLIT.items()}
R['holes'] = HOLES; R['hole_x'] = STATIONS

# jet penetration (Lefebvre / Norster) of secondary & dilution jets, one-sided from the outer liner
def gas_state_at(x):
    """cumulative air reaching the flame zone upstream of x and mixed-out gas temperature."""
    m = (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']) * MA
    Ti = ((SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']) * T2R) / (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f'])
    hsum = m * h_air(T2R)
    for key, src_T in (('outer_film', T2R), ('secondary', T2R), ('dilution', T2R), ('inner_film', T2 + 60)):
        xs = STATIONS[key]; fr = SPLIT[key]['f'] / len(xs)
        for xx in xs:
            if xx < x: m += fr * MA; hsum += fr * MA * h_air(src_T)
    Tair = _inv_h(hsum / m)
    f = MF / m
    return m, f, T_burn(Tair, f)
def _inv_h(h):
    lo, hi = 250.0, 2600.0
    for _ in range(50):
        mm = 0.5 * (lo + hi)
        if h_air(mm) > h: hi = mm
        else: lo = mm
    return 0.5 * (lo + hi)
A_L = math.pi * ((G['r_lo_i'] * 1e-3) ** 2 - (G['r_li_o'] * 1e-3) ** 2)
pen = {}
for key in ('secondary', 'dilution'):
    x = STATIONS[key][0]; m, f, Tg = gas_state_at(x)
    rg = rho(P_comb, Tg); Ug = (m + MF) / (rg * A_L)
    J = (2 * dP_hot) / (rg * Ug ** 2)
    dj = HOLES[key]['d_mm'] * math.sqrt(SPLIT[key]['Cd'])
    Ymax = 1.15 * dj * math.sqrt(J)                   # REF Lefebvre, Gas Turbine Combustion eq. 6.x (round jets, sin theta = 1)
    pen[key] = dict(x=x, T_gas_upstream=Tg, U_gas=Ug, J=J, d_jet=dj, Y_max_mm=Ymax, Y_over_H=Ymax / H_DOME)
R['jet_penetration'] = pen

# ----------------------------------------------------------------- 4. zones, residence time, loading, pattern factor
def annulus_area(ro, ri): return math.pi * ((ro * 1e-3) ** 2 - (ri * 1e-3) ** 2)
x_pz_end = STATIONS['secondary'][0]; x_sz_end = STATIONS['dilution'][0]; x_exit = G['x_ngv']
def vol(x0, x1):   # liner volume between x0..x1 (cylinder to x_lo_cyl_end, cone, sleeve)
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
# Lefebvre combustion loading parameter theta (b = 300), reference = casing annulus
A_ref = annulus_area(G['r_case_i'], G['r_tunnel']); D_ref = (G['r_case_i'] - G['r_tunnel']) * 1e-3
theta = P_plenum ** 1.75 * A_ref * D_ref ** 0.75 * math.exp(T2R / 300.0) / MA
heat_int = MF * LHV / (V_tot * P_comb / 1e5) / 1e6      # MW/(m3 bar)
q_ref = 0.5 * rho_hot * (MA / (rho_hot * A_ref)) ** 2
L_over_D = (x_exit - xd) / H_DOME
PF = 1 - math.exp(-1.0 / (0.070 * L_over_D * dP_hot / q_ref))   # REF Lefebvre pattern factor correlation
T_exit_mixed = gas_state_at(200.0)[2]
R['combustor'] = dict(H_dome_mm=H_DOME, L_liner_mm=x_exit - xd, L_over_H=L_over_D, A_liner_mm2=A_L * 1e6, V_liner_cm3=V_tot * 1e6,
                      zones=zones, tau_total_ms=tau_tot, theta_SI=theta, heat_release_MW_m3_bar=heat_int, q_ref_Pa=q_ref,
                      dPL_over_qref=dP_hot / q_ref, pattern_factor=PF, T_exit_mixed_C=T_exit_mixed - 273.15,
                      T_max_hotstreak_C=T_exit_mixed - 273.15 + PF * (T_exit_mixed - T2R),
                      phi_injector=MF / (SPLIT['injectors']['f'] * MA) / FAR_ST, phi_PZ=f_pz / FAR_ST, T_PZ_K=T_pz)


# ----------------------------------------------------------------- 5. injector (SLM IN625, radial swirler, partially premixed)
INJ = dict(n=G['n_inj'], n_vanes=10, vane_angle_deg=45.0, r_vane_exit=9.0, t_vane=0.8, cup_id=14.0, cup_len=6.0,
           centre_body_d=5.0, n_gas_holes=4, dP_gas_bar=0.25, T_gas_K=523.0, Cd_gas=0.75)
m_sw = SPLIT['injectors']['f'] * MA / INJ['n']
Aeff_sw = m_sw / math.sqrt(2 * rho_hot * dP_hot)
w_thr = (2 * math.pi * INJ['r_vane_exit'] / INJ['n_vanes']) * math.cos(math.radians(INJ['vane_angle_deg'])) - INJ['t_vane']
h_sw = Aeff_sw / 0.75 * 1e6 / (INJ['n_vanes'] * w_thr)
A_cup = math.pi / 4 * (INJ['cup_id'] ** 2 - INJ['centre_body_d'] ** 2) * 1e-6
U_cup = m_sw / (rho_hot * A_cup)
S_n = 2.0 / 3.0 * math.tan(math.radians(INJ['vane_angle_deg']))
t_premix = INJ['cup_len'] * 1e-3 / U_cup
m_gas_inj = MF / INJ['n']
P_man = P_comb + INJ['dP_gas_bar'] * 1e5
rho_g = rho(P_man, INJ['T_gas_K'], R_NG)
A_gas_eff = m_gas_inj / math.sqrt(2 * rho_g * INJ['dP_gas_bar'] * 1e5)
d_gas = math.sqrt(4 * A_gas_eff / INJ['Cd_gas'] / INJ['n_gas_holes'] / math.pi) * 1e3
d_gas_r = rnd(d_gas, 0.05)
phi_inj = MF / (SPLIT['injectors']['f'] * MA) / FAR_ST
SL_inj = S_L(phi_inj, T2R, P_comb)
alpha_mix = k_air(T2R) / (rho_hot * cp_air(T2R))
u_prime = 0.12 * math.hypot(U_cup, U_cup)            # ASSUMPTION 12 % turbulence of the swirled cup flow
S_T = SL_inj * (1 + 1.5 * (u_prime / SL_inj) ** 0.7)  # REF Damkoehler-type fit (Lipatnikov & Chomiak)
tau_w = 0.5 * 0.005 * rho_hot * (2 * U_cup ** 2)
g_wall = tau_w / mu_air(T2R); g_crit = 2 * SL_inj ** 2 / alpha_mix   # boundary-layer flashback (Lewis' gradient, x2 preheat margin)
tau_ig = tau_ign_SC(phi_inj, T2R, P_comb); tau_ig_hot = tau_ign_SC(phi_inj, T2R + 40, P_comb)
# lean blow-out: Damkoehler (PSR-type) for the cup recirculation zone, and literature for partially premixed preheated CH4
V_pz_inj = zones['primary']['V_cm3'] * 1e-6 / INJ['n']
def Da(phi, T_in=T2R, P=P_comb, m=None):
    m = m or (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']) * MA / INJ['n']
    Tpz = T_burn(T_in, phi * FAR_ST * SPLIT['injectors']['f'] / (SPLIT['injectors']['f'] + SPLIT['dome_cool']['f']))
    tres = V_pz_inj * rho(P, Tpz) / m
    sl = S_L(phi, T_in, P); al = k_air(T_in) / (rho(P, T_in) * cp_air(T_in))
    return tres / (al / sl ** 2)
phi_lbo_Da = None
for i in range(200):
    ph = 1.0 - i * 0.004
    if Da(ph) < 1.0: phi_lbo_Da = ph; break
INJ.update(m_air_g_s=m_sw * 1e3, A_eff_swirler_mm2=Aeff_sw * 1e6, throat_w_mm=w_thr, slot_h_mm=round(h_sw, 2), U_cup=U_cup,
           swirl_number=S_n, premix_time_ms=t_premix * 1e3, m_gas_g_s=m_gas_inj * 1e3, P_manifold_barg=(P_man - P_AMB) / 1e5,
           d_gas_hole_mm=d_gas_r, d_gas_exact=d_gas, phi_injector=phi_inj, S_L=SL_inj, S_T=S_T, flashback_margin_bulk=U_cup / S_T,
           g_wall=g_wall, g_crit=g_crit, flashback_margin_BL=g_wall / g_crit, tau_ign_ms=tau_ig * 1e3, tau_ign_plus40K_ms=tau_ig_hot * 1e3,
           autoign_margin=tau_ig / t_premix, autoign_margin_NG_C2_factor3=tau_ig / 3 / t_premix,
           Da_design=Da(phi_inj), phi_LBO_Damkoehler=phi_lbo_Da, phi_LBO_literature=0.32)
R['injector'] = INJ

# ----------------------------------------------------------------- 6. liner wall temperatures (Lefebvre & Herbert 1-D balance)
EPS_W = 0.80                    # oxidised Hastelloy-X (2.4665 / GH3536)
K_W = 22.0                      # W/mK at ~850 C
FILM = dict(s=1.5e-3, t_lip=0.8e-3)   # splash-ring slot height, lip thickness  # ASSUMPTION
FILM_DERATE = 0.65                    # ASSUMPTION: hole-fed splash rings + swirling PZ flow + jets: 65 % of the 2-D slot value
T_AD_INJ = None
def wall_T(Tg, f_local, lb, film_eta, Ta_film, h_film_C1, Ta_back, h_back, T_rad_sink, Z_back):
    """returns (Tw1, Tw2, q W/m2). Tg gas, film adiabatic wall via eta."""
    Pk = P_comb / 1e3
    eps_g = 1 - math.exp(-290.0 * Pk * 1.0 * math.sqrt(max(f_local, 1e-6) * lb) * Tg ** -1.5)
    Taw = Tg - film_eta * (Tg - Ta_film)
    t = 1.0e-3
    def resid(Tw1):
        R1 = 0.5 * SIG * (1 + EPS_W) * eps_g * Tg ** 1.5 * (Tg ** 2.5 - Tw1 ** 2.5)
        C1 = h_film_C1 * (Taw - Tw1)
        q = R1 + C1; Tw2 = Tw1 - q * t / K_W
        out = Z_back * SIG * (Tw2 ** 4 - T_rad_sink ** 4) + h_back * (Tw2 - Ta_back)
        return q - out, Tw2, q
    lo, hi = 300.0, Tg
    for _ in range(80):
        m = 0.5 * (lo + hi); r, _, _ = resid(m)
        if r > 0: lo = m
        else: hi = m
    r, Tw2, q = resid(0.5 * (lo + hi))
    return 0.5 * (lo + hi), Tw2, q, eps_g

def film_params(m_row, r_mm, Ta, x_from_slot, m_gas, Tg):
    """splash-ring film: slot velocity, blowing ratio, effectiveness, film heat transfer coefficient."""
    ra = rho(P_comb, Ta); s = FILM['s']
    Ua = m_row / (ra * 2 * math.pi * r_mm * 1e-3 * s)
    rg = rho(P_comb, Tg); Ug = m_gas / (rg * A_L)
    mb = ra * Ua / (rg * Ug)
    xs = max(x_from_slot, 1e-3) / s
    mu_r = (mu_air(Ta) / mu_air(Tg)) ** 0.15
    eta = (1.10 * mb ** 0.65 if mb < 1.3 else 1.28) * mu_r * xs ** -0.2 * (FILM['t_lip'] / s) ** -0.2   # REF Lefebvre eq. 9.x
    eta = min(eta, 1.0) * FILM_DERATE
    Rex = ra * Ua * x_from_slot / mu_air(Ta)
    h = 0.069 * k_air(Ta) / x_from_slot * Rex ** 0.7 if mb >= 1.3 else 0.10 * k_air(Ta) / x_from_slot * Rex ** 0.8 * xs ** -0.36
    return eta, h, mb

def annulus_h(m, ri_mm, ro_mm, T):
    A = annulus_area(ro_mm, ri_mm); Dh = 2 * (ro_mm - ri_mm) * 1e-3
    return 0.020 * k_air(T) / Dh ** 0.2 * (m / (A * mu_air(T))) ** 0.8          # REF Lefebvre C2 annulus correlation

def liner_profile(side, f_inner_film, T_shield_guess=600.0, T_case_side=860.0):
    """side 'outer' or 'inner'. returns list of stations (x, Tg, Tw1, film eta) and heat to the cold side."""
    rows = STATIONS['outer_film'] if side == 'outer' else STATIONS['inner_film']
    frac = SPLIT['outer_film']['f'] if side == 'outer' else f_inner_film
    m_row = frac * MA / len(rows)
    r_mm = G['r_lo_i'] if side == 'outer' else G['r_li_o']
    Ta_film = T2R if side == 'outer' else None
    lb = 3.4 * vol(xd, x_exit) / (2 * math.pi * (G['r_lo_i'] + G['r_li_o']) * 1e-3 * (x_exit - xd) * 1e-3)
    out = []; Qcold = 0.0; Tb = T2 + 8.0; m_b = None
    if side == 'inner':
        m_b = (f_inner_film + SPLIT['ngv_purge']['f']) * MA
    xs = [xd + 0.5 + i * 0.5 for i in range(int((x_exit - xd - 1) / 0.5))]
    for x in xs:
        prev = [r for r in rows if r <= x]
        if not prev: continue
        dx = (x - max(prev)) * 1e-3 + 2e-3          # distance from the slot lip (lip 2 mm long)
        m, f, Tg = gas_state_at(x)
        if x < STATIONS['secondary'][0]:          # PZ: swirl flames reach the walls -> near-wall gas halfway to T_ad(phi_inj)
            Tg = Tg + 0.5 * (T_AD_INJ - Tg)
        if side == 'outer':
            Ta = T2R; eta, hC1, mb = film_params(m_row, r_mm, Ta, dx, m + MF, Tg)
            m_an = 0.5 * sum(SPLIT[k]['f'] for k in ('outer_film', 'secondary', 'dilution')) * MA
            hb = annulus_h(m_an, G['r_lo_o'], G['r_baffle'], T2R)
            Tw1, Tw2, q, eg = wall_T(Tg, f, lb, eta, Ta, hC1, T2R, hb, T_shield_guess, 1 / (1 / EPS_W + 1 / 0.6 - 1))
        else:
            eta, hC1, mb = film_params(m_row, r_mm, Tb, dx, m + MF, Tg)
            n_up = len(prev); m_here = m_b - n_up * m_row * 0.0 - (n_up - 1) * m_row
            hb = annulus_h(max(m_here, 0.3 * m_b), G['r_shield_i'] + G['t_shield'], G['r_li_i'], Tb)
            Tw1, Tw2, q, eg = wall_T(Tg, f, lb, eta, Tb, hC1, Tb, hb, T_shield_guess, 1 / (1 / EPS_W + (G['r_li_i'] / G['r_shield_i']) * (1 / 0.5 - 1)))
            dA = 2 * math.pi * G['r_li_i'] * 1e-3 * 0.5e-3
            Qcold += q * dA
            Tb += q * dA / (max(m_here, 0.3 * m_b) * cp_air(Tb))
        out.append(dict(x=x, Tg=Tg, Tw=Tw1, eta=eta, m=mb, eps_g=eg))
    return out, Qcold, Tb

# choose the inner film (cold bypass) fraction: smallest that keeps the inner liner <= T_LIM
T_LIM_LINER = 850 + 273.15
T_AD_INJ = T_burn(T2R, MF / (SPLIT['injectors']['f'] * MA))
scan = []
for fi in [0.020 + 0.005 * i for i in range(9)]:
    prof, Qc, Tb_out = liner_profile('inner', fi)
    scan.append(dict(f_inner=fi, Tw_max_C=max(p['Tw'] for p in prof) - 273.15, Q_to_bypass_W=Qc, T_bypass_out_C=Tb_out - 273.15))
f_inner_ok = next((s['f_inner'] for s in scan if s['Tw_max_C'] + 273.15 <= T_LIM_LINER), scan[-1]['f_inner'])
SPLIT['inner_film']['f'] = f_inner_ok; complete_split(SPLIT)
HOLES['inner_film'].update(frac=f_inner_ok)
mi = f_inner_ok * MA; Aeff = mi / math.sqrt(2 * rho_cold * dP_cold); HOLES['inner_film'].update(
    m=mi, A_eff_mm2=Aeff * 1e6, A_geom_mm2=Aeff / 0.65 * 1e6, d_mm=rnd(math.sqrt(4 * Aeff / 0.65 / HOLES['inner_film']['n'] / math.pi) * 1e3, 0.05))
md = SPLIT['dilution']['f'] * MA; Aeff = md / math.sqrt(2 * rho_hot * dP_hot); HOLES['dilution'].update(
    frac=SPLIT['dilution']['f'], m=md, A_eff_mm2=Aeff * 1e6, A_geom_mm2=Aeff / 0.61 * 1e6, d_mm=rnd(math.sqrt(4 * Aeff / 0.61 / 48 / math.pi) * 1e3, 0.1))
prof_in, Q_bypass, Tb_out = liner_profile('inner', f_inner_ok)
prof_out, _, _ = liner_profile('outer', f_inner_ok)
R['liner_thermal'] = dict(inner_scan=scan, f_inner_film_chosen=f_inner_ok, inner_Tw_max_C=max(p['Tw'] for p in prof_in) - 273.15,
                          outer_Tw_max_C=max(p['Tw'] for p in prof_out) - 273.15, T_bypass_out_C=Tb_out - 273.15, Q_into_bypass_W=Q_bypass,
                          outer_profile=[(round(p['x'], 1), round(p['Tg'] - 273.15), round(p['Tw'] - 273.15), round(p['eta'], 2)) for p in prof_out[::6]],
                          inner_profile=[(round(p['x'], 1), round(p['Tg'] - 273.15), round(p['Tw'] - 273.15), round(p['eta'], 2)) for p in prof_in[::6]],
                          material='Hastelloy-X 2.4665 (VDM Nicrofer 4722Co) / GH3536, t = 1.0 mm', limit_C=T_LIM_LINER - 273.15)
R['air_split'] = {k: v['f'] for k, v in SPLIT.items()}
BETA = beta_of(SPLIT)

# ----------------------------------------------------------------- 7. cycle penalties (project cycle, recuperator at fixed UA)
def _eps_cf(NTU, Cr):
    if abs(1 - Cr) < 1e-6: return NTU / (1 + NTU)
    e = math.exp(-NTU * (1 - Cr)); return (1 - e) / (1 - Cr * e)
def cycle_e2(beta=0.0, dp_coll=0.0, dp_comb=0.045, Q_loss_W=0.0, UA=None):
    """sim/concept_study.cycle (arch 'fpt', target efficiencies) + recuperator bypass beta (cold air straight to the combustor),
    extra collector loss, combustor loss and extra heat loss.  UA=None -> fixed eps 0.90 (base)."""
    e = ls.EFF['target']; CPA, CPG, EXA, EXG = cs.CP_A, cs.CP_G, cs.EX_A, cs.EX_G
    Ta, Pa = 288.15, P_AMB; T1, P1 = Ta, Pa * 0.99; PR = DP['PR']; ma = MA
    T2_ = T1 * (1 + (PR ** EXA - 1) / e['eta_c']); w_c = CPA * (T2_ - T1)
    P2_ = P1 * PR; P3 = P2_ * (1 - dp_coll) * (1 - 0.025) * (1 - dp_comb)
    P_exit = Pa * (1 + 0.035 + 0.015 + 0.005); Th = 900.0; eps = 0.90
    for _ in range(80):
        f = 0.01 if _ == 0 else f
        mg = ma * (1 + f); Cc = (1 - beta) * ma * CPA; Ch = mg * CPG
        if UA is not None:
            Cmin, Cmax = min(Cc, Ch), max(Cc, Ch); eps = _eps_cf(UA / Cmin, Cmin / Cmax) * Cmin / Cc
        T2r_ = T2_ + eps * (Th - T2_)
        Tmix = (1 - beta) * T2r_ + beta * T2_
        f = (CPG * (TIT - Tmix) / (0.97 * LHV) * 1.02) + Q_loss_W / (ma * 0.97 * LHV)
        w_t = w_c / (0.985 * (1 + f)); T4 = TIT - w_t / CPG
        P4 = P3 * ((TIT - w_t / (CPG * e['eta_t'])) / TIT) ** (1 / EXG) * (1 - 0.015)
        w_pt = e['eta_pt'] * CPG * T4 * (1 - (P_exit / P4) ** EXG); Th = T4 - w_pt / CPG
    P_sh = ma * (1 + f) * w_pt * 0.985; P_el = P_sh * 0.95 * 0.96 - 450.0
    Q_rec = Cc * (T2r_ - T2_); T_stack = Th - Q_rec / (ma * (1 + f) * CPG)
    return dict(P_el=P_el, eta=P_el / (ma * f * LHV), mf=ma * f, T2r=T2r_, eps=eps, P3=P3, T_stack=T_stack, Q_fuel=ma * f * LHV)
base = cycle_e2()
Cc0 = MA * cs.CP_A; Ch0 = MA * (1 + base['mf'] / MA) * cs.CP_G
Cmin0, Cmax0 = min(Cc0, Ch0), max(Cc0, Ch0)
lo, hi = 0.1, 40.0
for _ in range(80):
    mid = 0.5 * (lo + hi)
    if _eps_cf(mid, Cmin0 / Cmax0) * Cmin0 / Cc0 < 0.90: lo = mid
    else: hi = mid
UA0 = 0.5 * (lo + hi) * Cmin0
dp_hot_side = 1 - (P_comb * (1 - 0.006)) / (P_C2 / (1 - 0.0) )   # C2 port + baffle + liner + NGV entry 0.6 %
case = {}
case['base (cycle model, 4.5 % combustor)'] = cycle_e2(UA=UA0)
case['E2 pressure losses only'] = cycle_e2(dp_coll=dp_coll, dp_comb=dp_hot_side, UA=UA0)
case['E2 bypass only (beta)'] = cycle_e2(beta=BETA, UA=UA0)
case['E2 collector loss only'] = cycle_e2(dp_coll=dp_coll, UA=UA0)
case['E2 complete (losses + beta + heat loss)'] = cycle_e2(beta=BETA, dp_coll=dp_coll, dp_comb=dp_hot_side, Q_loss_W=0.0, UA=UA0)
R['cycle'] = {k: dict(P_el_kW=v['P_el'] / 1e3, eta_el_pct=v['eta'] * 100, mf_g_s=v['mf'] * 1e3, T_rec_out_C=v['T2r'] - 273.15,
                      eps=v['eps'], P3_bar=v['P3'] / 1e5, T_stack_C=v['T_stack'] - 273.15) for k, v in case.items()}
R['cycle_UA_W_K'] = UA0; R['beta_recuperator_bypass'] = BETA; R['dp_hot_side_total_pct'] = dp_hot_side * 100

# ----------------------------------------------------------------- 8. tunnel / bearing thermal (options a, b, c)
TUN_PROF = [(0, 12.99), (2.0, 12.99), (2.0, 20.0), (7.03, 20.0), (16.53, 10.5), (92.96, 10.5), (95.3, 13.0), (99.3, 13.0), (99.3, 19.0),
            (103.3, 19.0), (103.3, 13.0), (107.3, 13.0)]
def tun_ro(x):
    for (x0, r0), (x1, r1) in zip(TUN_PROF[:-1], TUN_PROF[1:]):
        if x0 <= x <= x1 and x1 > x0: return r0 + (r1 - r0) * (x - x0) / (x1 - x0)
    return 13.0
def tun_ri(x): return 11.0 if (x < 11.3 or x > 97.3) else 8.5
K_AL = 150.0; H_OIL = 400.0; T_OIL = 90 + 273.15          # ASSUMPTION closed-loop oil: 70 C supply, bearing chamber ~90 C
Q_BRG = 50.0                                               # ASSUMPTION friction per 608 hybrid at 115k rpm, oil jet (W), half into the housing
def T_liner_inner_at(x):
    pts = [(p['x'], p['Tw']) for p in prof_in]
    if x <= pts[0][0]: return pts[0][1]
    for (a, ta), (b, tb) in zip(pts[:-1], pts[1:]):
        if a <= x <= b: return ta + (tb - ta) * (x - a) / (b - a)
    return pts[-1][1]
def tunnel_model(option, G_web, T_web):
    dx = 0.5; xs = [1.0 + dx * (i + 0.5) for i in range(int(106.0 / dx))]
    n = len(xs); T = [400.0] * n
    m_b = (SPLIT['inner_film']['f'] + SPLIT['ngv_purge']['f']) * MA
    Tb_in, Tb_out = T2 + 10.0, Tb_out_global
    for it in range(3000):
        maxd = 0.0
        for i, x in enumerate(xs):
            ro, ri = tun_ro(x) * 1e-3, tun_ri(x) * 1e-3
            Ao = 2 * math.pi * ro * dx * 1e-3; Ai = 2 * math.pi * ri * dx * 1e-3; Ax = math.pi * (ro ** 2 - ri ** 2)
            Gx = K_AL * Ax / (dx * 1e-3)
            num = H_OIL * Ai * T_OIL; den = H_OIL * Ai
            if i > 0: num += Gx * T[i - 1]; den += Gx
            if i < n - 1: num += Gx * T[i + 1]; den += Gx
            if (3.3 <= x <= 10.3) or (97.3 <= x <= 104.3): num += 0.5 * Q_BRG * dx / 7.0
            if 99.3 <= x <= 103.3: num += G_web * dx / 4.0 * T_web; den += G_web * dx / 4.0
            frac = min(max((x - 17.5) / (92.0 - 17.5), 0), 1); Tb = Tb_in + (Tb_out - Tb_in) * frac
            if x < 17.5:
                Tenv = T2 if option != 'b' else T2; h = 120.0; num += h * Ao * Tenv; den += h * Ao
            elif x > 92.0:
                Tenv = Tb_out if option != 'b' else T2R; h = 80.0; num += h * Ao * Tenv; den += h * Ao
            else:
                if option == 'a':      # cold bypass, bare tunnel: convection + liner radiation
                    hb = annulus_h(m_b, 10.5, G['r_li_i'], Tb)
                    Z = 1 / (1 / 0.2 + (10.5 / G['r_li_i']) * (1 / EPS_W - 1)); Tl = T_liner_inner_at(x) - 30
                    hr = Z * SIG * (Tl ** 2 + T[i] ** 2) * (Tl + T[i])
                    num += hb * Ao * Tb + hr * Ao * Tl; den += (hb + hr) * Ao
                elif option == 'c':    # cold bypass + polished shield r17.3 + dead air gap
                    hb = annulus_h(m_b, G['r_shield_i'] + G['t_shield'], G['r_li_i'], Tb)
                    Tl = T_liner_inner_at(x) - 30
                    Zls = 1 / (1 / 0.3 + (G['r_shield_i'] / G['r_li_i']) * (1 / EPS_W - 1))
                    Zst = 1 / (1 / 0.2 + (10.5 / G['r_shield_i']) * (1 / 0.3 - 1))
                    Ts = Tb + 50
                    for _ in range(30):
                        kg = k_air(0.5 * (Ts + T[i])); Ggap = 2 * math.pi * kg / math.log(G['r_shield_i'] / 10.5)   # W/mK per length
                        qin = Zls * SIG * (Tl ** 4 - Ts ** 4) * 2 * math.pi * G['r_shield_i'] * 1e-3
                        qgap = Ggap * (Ts - T[i]) + Zst * SIG * (Ts ** 4 - T[i] ** 4) * 2 * math.pi * 0.0105
                        qconv = hb * 2 * math.pi * (G['r_shield_i'] + 0.3) * 1e-3 * (Ts - Tb)
                        Ts += 0.3 * (qin - qgap - qconv) / (hb * 2 * math.pi * 0.0176 + Ggap)
                    kg = k_air(0.5 * (Ts + T[i])); Gl = (2 * math.pi * kg / math.log(G['r_shield_i'] / 10.5)) * dx * 1e-3
                    hr = Zst * SIG * (Ts ** 2 + T[i] ** 2) * (Ts + T[i]) * Ao
                    num += (Gl + hr) * Ts; den += Gl + hr
                    if i == 0 or True: tunnel_model.Ts_max = max(getattr(tunnel_model, 'Ts_max', 0), Ts)
                elif option == 'b':    # hot (566 C) inner annulus, 5 mm microporous + IN625 shield around the tube
                    kins = 0.030; Gl = 2 * math.pi * kins / math.log((10.5 + 5) / 10.5) * dx * 1e-3
                    num += Gl * T2R; den += Gl
            Tn = num / den; maxd = max(maxd, abs(Tn - T[i])); T[i] = Tn
        if maxd < 1e-3: break
    Qoil = sum(H_OIL * 2 * math.pi * tun_ri(x) * 1e-3 * dx * 1e-3 * (T[i] - T_OIL) for i, x in enumerate(xs))
    def Tat(a, b): return max(T[i] for i, x in enumerate(xs) if a <= x <= b) - 273.15
    return dict(T_tube_max_C=Tat(17.5, 92.0), T_front_brg_C=Tat(3.3, 10.3) + 10, T_rear_brg_C=Tat(97.3, 104.3) + 10,
                T_rear_flange_C=Tat(99.3, 103.3), Q_to_oil_W=Qoil + Q_BRG, Q_web_W=G_web * (T_web - (Tat(99.3, 103.3) + 273.15)))
Tb_out_global = Tb_out
G_WEB_ASIS = 1 / (1 / (3000 * 450e-6) + 1 / (20 * 2 * math.pi * 0.0201 * 0.0015 / 0.0023))     # contact 3000 W/m2K x 450 mm2 + web fin
G_WEB_BREAK = 0.12                                                                              # E1 thermal break (3-pad 1.4980 / ZrO2 spacer)
TUN = {}
for opt, Tweb in (('a', 750 + 273.15), ('b', 820 + 273.15), ('c', 750 + 273.15)):
    for lab, Gw in (('as-is NGV joint', G_WEB_ASIS), ('E1 thermal break', G_WEB_BREAK)):
        tunnel_model.Ts_max = 0
        TUN['%s / %s' % (opt, lab)] = dict(tunnel_model(opt, Gw, Tweb), T_shield_max_C=(tunnel_model.Ts_max - 273.15) if opt == 'c' else None)
def fuel_penalty_W(Q_W): return Q_W / 0.97
R['tunnel'] = dict(options=TUN, G_web_asis_W_K=G_WEB_ASIS, G_web_break_W_K=G_WEB_BREAK,
                   beta_a_c=BETA, beta_b=0.012, note='(b) keeps leak/purge 1.2 % but the NGV cavity is hot; (a),(c) beta = inner film + leaks + purge',
                   penalty_a_c=dict(dP_el_kW=(case['E2 bypass only (beta)']['P_el'] - case['base (cycle model, 4.5 % combustor)']['P_el']) / 1e3,
                                    deta_pts=(case['E2 bypass only (beta)']['eta'] - case['base (cycle model, 4.5 % combustor)']['eta']) * 100))
cb = cycle_e2(beta=0.012, UA=UA0)
R['tunnel']['penalty_b'] = dict(dP_el_kW=(cb['P_el'] - case['base (cycle model, 4.5 % combustor)']['P_el']) / 1e3,
                                deta_pts=(cb['eta'] - case['base (cycle model, 4.5 % combustor)']['eta']) * 100)

# ----------------------------------------------------------------- 9. hot casing temperature: liner -> perforated baffle -> casing
EPS_B, EPS_C = 0.6, 0.6           # oxidised 1.4948
T_lo_mean = sum(p['Tw'] for p in prof_out) / len(prof_out) - 25          # liner cold-side mean
q_ins_out = 300.0                 # W/m2 loss through the insulation (sec. 11), small
def casing_T(with_baffle):
    m_out = 0.94 * MA
    h_c = annulus_h(0.5 * m_out, G['r_baffle'] + G['t_baffle'], G['r_case_i'], T2R) + 15.0   # C2 jet stirring (+15)
    h_b = annulus_h(0.4 * m_out, G['r_lo_o'], G['r_baffle'], T2R) * 1.3                         # perforation jets on the baffle
    Tc, Tb = 900.0, 950.0
    for _ in range(4000):
        if with_baffle:
            Z1 = 1 / (1 / EPS_W + (G['r_lo_o'] / G['r_baffle']) * (1 / EPS_B - 1)) * (1 - BAFFLE_OPEN * 0.5)
            Z2 = 1 / (1 / EPS_B + (G['r_baffle'] / G['r_case_i']) * (1 / EPS_C - 1))
            q1 = Z1 * SIG * (T_lo_mean ** 4 - Tb ** 4) * G['r_lo_o'] / G['r_baffle']
            q2 = Z2 * SIG * (Tb ** 4 - Tc ** 4)
            Tb += 1e-3 * (q1 - q2 - h_b * (Tb - T2R) - h_c * (Tb - T2R))
            qdirect = BAFFLE_OPEN * 0.5 * 1 / (1 / EPS_W + (G['r_lo_o'] / G['r_case_i']) * (1 / EPS_C - 1)) * SIG * (T_lo_mean ** 4 - Tc ** 4) * G['r_lo_o'] / G['r_case_i']
            Tc += 1e-3 * (q2 * G['r_baffle'] / G['r_case_i'] + qdirect - h_c * (Tc - T2R) - q_ins_out)
        else:
            Z = 1 / (1 / EPS_W + (G['r_lo_o'] / G['r_case_i']) * (1 / EPS_C - 1))
            q = Z * SIG * (T_lo_mean ** 4 - Tc ** 4) * G['r_lo_o'] / G['r_case_i']
            Tc += 1e-3 * (q - h_c * (Tc - T2R) - q_ins_out); Tb = None
    return Tc, Tb, h_c
Tc_b, Tbaf, hc_ = casing_T(True); Tc_nb, _, _ = casing_T(False)
R['casing_thermal'] = dict(T_liner_cold_side_mean_C=T_lo_mean - 273.15, h_casing_inner=hc_, T_casing_with_baffle_C=Tc_b - 273.15,
                           T_baffle_C=Tbaf - 273.15, T_casing_without_baffle_C=Tc_nb - 273.15, design_metal_T_C=620.0)

# ----------------------------------------------------------------- 10. pressure casing (EN 13445-3 / ASME VIII-1 cross-check)
PS = 0.30            # MPa gauge design pressure: max P2 at 119k overspeed 3.27 bar abs -> 2.3 barg, + surge/relief margin
MAT = {
    '1.4404 (316L) @200C': dict(Rp1=147.0, Rm=430.0, f=None, creep=None),       # EN 10028-7 table values (approx.)
    '1.4948 (304H) @620C': dict(Rp1=108.0, Rm=330.0, creep=62.0),                # S_R,100kh: 600 C 74, 650 C 45 MPa (EN 10028-7 annex, interp.)
}
def f_aust(Rp1, Rm): return max(Rp1 / 1.5, min(Rp1 / 1.2, Rm / 3.0))      # EN 13445-3 6.4 austenitic, A>=35 %
f_cold = f_aust(147.0, 430.0)
f_hot_ti = f_aust(108.0, 330.0); f_hot_creep = 62.0 / 1.5               # EN 13445-3 19.5: SF 1.5 on mean creep rupture 100 kh
f_hot = min(f_hot_ti, f_hot_creep)
S_asme_304H = 9.3 * 6.894757                                              # ASME II-D SA-240 304H ~1110 F (interp.)
z_w = 0.85
def e_cyl(P, Di, f): return P * Di / (2 * f * z_w - P)
e_hot_req = e_cyl(PS, 2 * G['r_case_i'], min(f_hot, S_asme_304H))
e_drum_req = e_cyl(PS, 2 * G['r_drum_i'], f_cold)
def annular_plate_t(P, a, b, f, k=0.10):   # Roark, annular plate, both edges fixed, uniform load; sigma = k q a^2 / t^2 <= 1.5 f
    return math.sqrt(k * P * a ** 2 / (1.5 * f))
t_front_req = annular_plate_t(PS, G['r_drum_i'] + G['t_drum'], G['r_front_ring_o'], f_cold)
t_rear_req = annular_plate_t(PS, G['r_case_i'] + G['t_case'], G['r_rear_bore'] + 10, f_hot)
t_bh_req = annular_plate_t(PS, G['r_drum_i'], G['r_bh_hub_o'], f_aust(130.0, 400.0))   # accident case: hot side depressurised
# flanges & bolts (ASME VIII App.2 style, mica gasket KLINGER Milam PSS: m = 2.0, y = 20 MPa ASSUMED)
def flange(G_mm, N_mm, n_b, d_b, lever_mm, t_mm, f_fl, S_bolt):
    b = min(N_mm / 2, 6.35); Gm = G_mm * 1e-3
    Wm1 = math.pi / 4 * Gm ** 2 * PS * 1e6 + 2 * b * 1e-3 * math.pi * Gm * 2.0 * PS * 1e6
    Wm2 = math.pi * b * 1e-3 * Gm * 20e6
    W = max(Wm1, Wm2); A_root = {8: 32.8, 10: 52.3, 6: 17.9}[d_b] * 1e-6
    A_req = W / (S_bolt * 1e6); M = W * lever_mm * 1e-3 / (2 * math.pi * (G_mm / 2 + lever_mm) * 1e-3)
    sig = 6 * M / (t_mm * 1e-3) ** 2 / 1e6
    return dict(W_kN=W / 1e3, Wm1_kN=Wm1 / 1e3, Wm2_kN=Wm2 / 1e3, bolt_area_req_mm2=A_req * 1e6, bolt_area_avail_mm2=n_b * A_root * 1e6,
                sigma_ring_MPa=sig, f_allow_MPa=f_fl, ok=(n_b * A_root >= A_req) and sig <= 1.5 * f_fl)
FL_MID = flange(2 * 120.75, 4.5, G['n_mid_bolts'], 8, 7.0, 6.0, f_aust(120.0, 380.0), 150.0)    # ~450 C, 1.4980 bolts S ~150 MPa
FL_E3 = flange(137.0, 8.0, G['n_e3_bolts'], 8, 10.0, 10.0, f_hot, 110.0)                    # ~620 C, 1.4980 S ~110 MPa
# nozzle reinforcement (area replacement, EN 13445-3 9.5 simplified): C2 port 67 x 110 on the D170 shell, box walls 3 mm
d_open = C2_BOX['x'][1] - C2_BOX['x'][0]
A_req_n = d_open * e_hot_req
L_eff = math.sqrt((2 * G['r_case_i'] + G['t_case']) * G['t_case'])
A_avail_n = 2 * L_eff * (G['t_case'] - e_hot_req) + 2 * 3.0 * min(25.0, 2.5 * 3.0 * 4)
P_test = max(1.25 * PS * f_cold / f_hot, 1.43 * PS)
R['casing_mech'] = dict(PS_MPa=PS, f_cold_1_4404=f_cold, f_hot_time_indep=f_hot_ti, f_hot_creep=f_hot_creep, f_hot_design=min(f_hot, S_asme_304H),
                        S_ASME_304H=S_asme_304H, e_hot_req_mm=e_hot_req, e_hot_chosen=G['t_case'], e_drum_req_mm=e_drum_req, e_drum_chosen=G['t_drum'],
                        t_front_wall_req=t_front_req, t_front_wall=G['t_front_wall'], t_rear_plate_req=t_rear_req, t_rear_plate=G['t_rear_plate'],
                        t_bulkhead_req_accident=t_bh_req, t_bulkhead=G['t_bh'], flange_mid=FL_MID, flange_E2E3=FL_E3,
                        nozzle_C2_A_req_mm2=A_req_n, nozzle_C2_A_avail_mm2=A_avail_n, test_pressure_barg=P_test * 10,
                        PED='PS x V = %.1f bar.L < 25 (gas group 2) -> PED Art. 4(3) sound engineering practice' % (PS * 10 * 3.4))

# ----------------------------------------------------------------- 11. insulation, skin temperature, heat losses
def k_micro(Tm_C): return 0.020 + 3.0e-5 * Tm_C        # microporous (Promat MICROTHERM class), W/mK
def skin(r_in_mm, T_in_C, t_mm, T_amb_C, h_conv, eps=0.3):
    ri, ro = r_in_mm * 1e-3, (r_in_mm + t_mm) * 1e-3; Ts = T_amb_C + 20
    for _ in range(200):
        k = k_micro(0.5 * (T_in_C + Ts)); q_l = 2 * math.pi * k * (T_in_C - Ts) / math.log(ro / ri)
        q_out = 2 * math.pi * ro * (h_conv * (Ts - T_amb_C) + eps * SIG * ((Ts + 273.15) ** 4 - (T_amb_C + 273.15) ** 4))
        Ts += 0.02 * (q_l - q_out)
    return Ts, q_l
INS = {}
for lab, Tamb, h in (('ventilated package 45 C, h 20', 45.0, 20.0), ('still air 45 C, h 4', 45.0, 4.0), ('ventilated 35 C, h 20', 35.0, 20.0)):
    for t in (30, 40, 50, 60):
        INS['hot casing %s t=%d' % (lab, t)] = skin(G['r_case_i'] + G['t_case'], Tc_b - 273.15, t, Tamb, h)[0]
        INS['drum %s t=%d' % (lab, t)] = skin(G['r_drum_i'] + G['t_drum'], T2 - 273.15 + 5, t - 10 if t > 30 else 20, Tamb, h)[0]
T_HOT_INS, T_DRUM_INS = 50.0, 25.0
Ts_hot, ql_hot = skin(G['r_case_i'] + G['t_case'], Tc_b - 273.15, T_HOT_INS, 45.0, 20.0)
Ts_drum, ql_drum = skin(G['r_drum_i'] + G['t_drum'], T2 - 273.15 + 5, T_DRUM_INS, 45.0, 20.0)
L_hot = (G['x_case_shell_end'] - G['x_hot_flange'][0]) * 1e-3 + 0.03     # + flange/rear plate allowance
Q_hot = ql_hot * L_hot * 1.6          # x1.6: rear plate, flanges, C2 nozzle, bosses (thermal bridges)
Q_drum = ql_drum * 0.044 * 1.8
# bulkhead hot->cold leak (regenerative short circuit): 3 mm plate + 4 mm microporous, h 60/60
A_bh = math.pi * ((G['r_case_i'] * 1e-3) ** 2 - (G['r_bh_hub_o'] * 1e-3) ** 2)
U_bh = 1 / (1 / 60 + 1 / 60 + G['t_bh_ins'] * 1e-3 / k_micro(350))
Q_bh = U_bh * A_bh * (T2R - T2)
Q_li_front = 40 * 2 * math.pi * G['r_li_o'] * 1e-3 * (G['x_dome'] - G['x_li_front']) * 1e-3 * (T2R - T2)
R['insulation'] = dict(table=INS, chosen_hot_mm=T_HOT_INS, chosen_drum_mm=T_DRUM_INS, skin_hot_C=Ts_hot, skin_drum_C=Ts_drum,
                       skin_hot_still_air_C=skin(G['r_case_i'] + G['t_case'], Tc_b - 273.15, T_HOT_INS, 45.0, 4.0)[0],
                       Q_loss_hot_casing_W=Q_hot, Q_loss_drum_W=Q_drum, Q_bulkhead_leak_W=Q_bh, Q_inner_liner_front_leak_W=Q_li_front,
                       material='microporous (Promat MICROTHERM / Etex, BE) encapsulated, 0.5 mm 1.4301 cladding; AES blanket Morgan Superwool (UK) at joints')
Q_regen = (Q_bh + Q_li_front) * 0.9         # heat moved from hot to cold air before the recuperator: ~90 % of it is lost to the combustor
case['E2 complete (losses + beta + heat loss)'] = cycle_e2(beta=BETA, dp_coll=dp_coll, dp_comb=dp_hot_side, Q_loss_W=Q_hot + Q_regen, UA=UA0)
c0, c1 = case['base (cycle model, 4.5 % combustor)'], case['E2 complete (losses + beta + heat loss)']
R['cycle'] = {k: dict(P_el_kW=v['P_el'] / 1e3, eta_el_pct=v['eta'] * 100, mf_g_s=v['mf'] * 1e3, T_rec_out_C=v['T2r'] - 273.15,
                      eps=v['eps'], P3_bar=v['P3'] / 1e5, T_stack_C=v['T_stack'] - 273.15) for k, v in case.items()}
R['penalty_total'] = dict(dP_el_kW=(c1['P_el'] - c0['P_el']) / 1e3, deta_pts=(c1['eta'] - c0['eta']) * 100,
                          note='base already contains 2 % hot-section heat loss and 4.5 % combustor loss (cycle model)')

# ----------------------------------------------------------------- 12. thermal growth (cold 20 C -> design point)
A18 = 18.5e-6; A16 = 16.0e-6; A23 = 23.5e-6; A17 = 17.0e-6
x_fix = -4.0                                                     # front support leg (fixed point), drum bottom
GR = {}
GR['hot casing axial (mid flange -> rear ring x113)'] = (113 - 28) * A18 * (Tc_b - 293)
GR['collector axial (fixed leg -> mid flange)'] = (28 - x_fix) * A17 * (T2 - 293)
GR['casing rear ring axial vs fixed leg'] = GR['hot casing axial (mid flange -> rear ring x113)'] + GR['collector axial (fixed leg -> mid flange)']
GR['core: intake-outer lip -> NGV rib (Al tunnel ~130 C, NGV ~700 C)'] = (99.3 + 17.33) * A23 * 110 + 10 * 15e-6 * 680
GR['rear seal ring travel on NGV land (casing - core)'] = GR['casing rear ring axial vs fixed leg'] - GR['core: intake-outer lip -> NGV rib (Al tunnel ~130 C, NGV ~700 C)'] + (-17.33 - x_fix) * A17 * (T2 - 293) * -1
GR['liner axial, pin x50 -> outer sleeve end x106.5'] = (106.5 - 50) * A16 * (Tbaf - 293 + 150)
GR['liner axial, pin x50 -> inner liner end x98'] = (98 - 50) * A16 * (max(p['Tw'] for p in prof_in) - 293)
GR['liner radial outer r55'] = 55 * A16 * (max(p['Tw'] for p in prof_out) - 293)
GR['casing radial r88'] = 88 * A18 * (Tc_b - 293)
GR['rear ring bore r38 (1.4948) vs NGV rib r37.95 (IN713LC, ~720 C)'] = 38.1 * A18 * (Tc_b - 293) - 37.95 * 15.5e-6 * (720 + 273 - 293)
GR['C2 flange centre: dx'] = (65 - x_fix) * A17 * 0 + (65 - 28) * A18 * (Tc_b - 293) + GR['collector axial (fixed leg -> mid flange)']
GR['C2 flange centre: dy (nozzle 1.4948 ~560 C, length 185)'] = 185 * A18 * (T2R - 293)
GR['C1 flange centre: dy (nozzle 1.4404 165 C, length 185)'] = 185 * A17 * (T2 - 293)
GR['C1 flange centre: dx'] = (-7 - x_fix) * A17 * (T2 - 293)
R['thermal_growth_mm'] = GR

# ----------------------------------------------------------------- 13. gas manifold & supply
rho_ng_man = rho(P_man, 330.0, R_NG)
Q_ng = MF / rho_ng_man
def v_in(d_mm): return Q_ng / (math.pi / 4 * (d_mm * 1e-3) ** 2)
GAS = dict(P_manifold_barg=(P_man - P_AMB) / 1e5, supply_min_barg=3.5, regulator_margin_bar=3.5 - (P_man - P_AMB) / 1e5,
           Nm3_h=MF / 0.717 * 3600, DN15_ID_mm=16.1, V_DN15=v_in(16.1), feed_tube='radial drilled rib Ø5 (bulkhead cold face, south)', V_feed=v_in(5.0),
           ring='Ø7x0.8 (ID 5.4) torus r37.5 on the bulkhead', V_ring_half=v_in(5.4) / 2, stem='Ø6x0.8 (ID 4.4) x8', V_stem=v_in(4.4) / 8,
           maldistribution_pct=100 * 0.5 * rho_ng_man * (v_in(5.4) / 2) ** 2 / (INJ['dP_gas_bar'] * 1e5) / 2,
           gas_side_stiffness_dPgas_over_P=INJ['dP_gas_bar'] * 1e5 / P_comb)
R['gas'] = GAS

# ----------------------------------------------------------------- 14. ignition / light-off
LO = dict(N1_rpm=40e3, ma=0.075, P3_bar=1.25, T3_C=30.0, fuel_g_s=0.70)    # ASSUMPTION starter-assisted light-off point
LO['phi_injector'] = LO['fuel_g_s'] * 1e-3 / (SPLIT['injectors']['f'] * LO['ma']) / FAR_ST
LO['phi_overall'] = LO['fuel_g_s'] * 1e-3 / LO['ma'] / FAR_ST
LO['dP_liner_kPa'] = 1e-3 * dP_hot * (LO['ma'] / MA) ** 2 * (rho_hot / rho(LO['P3_bar'] * 1e5, LO['T3_C'] + 273.15))
LO['U_cup'] = U_cup * (LO['ma'] / MA) * (rho_hot / rho(LO['P3_bar'] * 1e5, LO['T3_C'] + 273.15))
LO['S_L'] = S_L(min(LO['phi_injector'], 1.4), LO['T3_C'] + 273.15, LO['P3_bar'] * 1e5)
LO['T_after_lightoff_C'] = T_burn(LO['T3_C'] + 273.15, LO['fuel_g_s'] * 1e-3 / LO['ma']) - 273.15
LO['MIE_quiescent_mJ'] = 0.30 * (1.0 / LO['P3_bar']) ** 2       # REF Lewis & von Elbe, CH4 phi~1, ~1/P^2
LO['MIE_flowing_mJ_est'] = LO['MIE_quiescent_mJ'] * 100          # ASSUMPTION x100 for u' ~ 3-5 m/s (Ballal & Lefebvre)
LO['exciter'] = 'capacitive-discharge industrial exciter >= 0.5 J/spark, 10-20 sparks/s (IGN-630), plug M14x1.25 surface gap'
R['ignition'] = LO

# ----------------------------------------------------------------- 15. outputs
G['C1'] = dict(box=C1_BOX, round_centre_xz=(-7.0, -90.0), DN=100, pipe_od=114.3, pipe_t=3.05, face_y=185.0, y_box=(60.0, 145.0), y_round=168.0)
G['C2'] = dict(box=C2_BOX, round_centre_xz=(68.0, 72.0), DN=125, pipe_od=139.7, pipe_t=3.4, face_y=185.0, y_box=(30.0, 145.0), y_round=168.0)
G['holes'] = {k: dict(n=HOLES[k]['n'], d=HOLES[k]['d_mm'], x=STATIONS.get(k)) for k in ('outer_film', 'secondary', 'dilution', 'inner_film', 'dome_cool')}
G['injector'] = dict(x_union=G['x_bh_back'], x_backplate=(G['x_bh_back'] + G['t_bh_ins'] + 2.0, G['x_bh_back'] + G['t_bh_ins'] + 5.0), n=INJ['n'], r=G['r_inj'], cup_id=INJ['cup_id'], cup_len=INJ['cup_len'], cb_d=INJ['centre_body_d'], n_vanes=INJ['n_vanes'],
                     vane_angle=INJ['vane_angle_deg'], r_vane_exit=INJ['r_vane_exit'], slot_h=max(INJ['slot_h_mm'], 2.0),
                     n_gas=INJ['n_gas_holes'], d_gas=INJ['d_gas_hole_mm'])
G['insulation'] = dict(hot=T_HOT_INS, drum=T_DRUM_INS)
R['geometry'] = G
json.dump(G, open(os.path.join(HERE, 'e2_design.json'), 'w'), indent=1, default=str)
json.dump(R, open(os.path.join(HERE, 'e2_results.json'), 'w'), indent=1, default=str)

def P(*a): print(*a)
if __name__ == '__main__':
    d = R['design_point']
    P('=== GR180-CCHP E2 combustion section - design point 115k / TIT 800 C (sim/life_study.point) ===')
    P('air %.4f kg/s  fuel %.3f g/s (%.1f kW)  T2 %.1f C  T2r %.1f C  P2 %.3f bar  phi_overall %.3f' % (d['ma'], d['mf'] * 1e3, d['Q_fuel_kW'], d['T2_C'], d['T2r_C'], d['P2_bar'], d['phi_overall']))
    c = R['collector']; p = R['pressure']
    P('\n-- pressure budget --')
    P('13 channels exit %.0f m/s, q %.1f kPa | collector: wakes %.1f + faired turn/diffuser/dump %.1f + drum %.1f + C1 transition %.1f = %.1f kPa (%.2f %%); pure dump would be %.1f kPa'
      % (c['V_channels'], c['q_channels_kPa'], c['dP_mix_wakes_kPa'], c['dP_turn_kPa'] - c['dP_mix_wakes_kPa'], c['dP_drum_kPa'], c['dP_C1_transition_kPa'], c['dP_total_kPa'], c['dp_total_pct'], c['dP_upper_bound_pure_dump_kPa']))
    P('C1 %.3f bar (DN100 %.1f m/s) -> recuperator -2.5 %% -> C2 %.3f bar (DN125 %.1f m/s, port %.1f m/s, -%.2f kPa) -> baffle -%.2f kPa -> plenum %.3f -> liner %.1f %% -> combustor %.3f bar'
      % (p['P_C1'], c['V_C1_DN100'], p['P_C2'], p['V_C2_DN125'], p['V_C2_port'], p['dP_C2_port_kPa'], p['dP_baffle_kPa'], p['P_hot_plenum'], p['dP_liner_hot_pct'], p['P_combustor']))
    P('cold inner annulus %.3f bar -> inner liner dp %.1f %% ; bulkhead dp %.3f bar' % (p['P_cold_inner_annulus'], p['dP_liner_cold_side_pct'], p['dP_bulkhead_bar']))
    P('\n-- air split (fraction of compressor air) and holes --')
    for k, v in HOLES.items():
        P('  %-11s %5.1f %%  n %3d  d %s mm  A_geom %.0f mm2  V_jet %.0f m/s' % (k, v['frac'] * 100, v['n'], ('%.2f' % v['d_mm']) if v['d_mm'] else 'swirler', v['A_geom_mm2'], v['V_jet']))
    P('  cold leaks %.1f %%, NGV cavity purge %.1f %%  -> recuperator bypass beta = %.1f %%' % (SPLIT['leak_cold']['f'] * 100, SPLIT['ngv_purge']['f'] * 100, BETA * 100))
    for k, v in R['jet_penetration'].items(): P('  %s jets: J %.0f, Ymax %.0f mm = %.2f H' % (k, v['J'], v['Y_max_mm'], v['Y_over_H']))
    cb_ = R['combustor']
    P('\n-- combustor --  H %.1f mm, L %.1f mm (L/H %.2f), V %.0f cm3, tau %.2f ms, theta %.2e, %.0f MW/m3bar, PF %.3f -> hot streak %.0f C'
      % (cb_['H_dome_mm'], cb_['L_liner_mm'], cb_['L_over_H'], cb_['V_liner_cm3'], cb_['tau_total_ms'], cb_['theta_SI'], cb_['heat_release_MW_m3_bar'], cb_['pattern_factor'], cb_['T_max_hotstreak_C']))
    for k, z in cb_['zones'].items(): P('   %-9s x %5.1f-%5.1f  V %4.0f cm3  phi %.2f  T %4.0f K  tau %.2f ms' % (k, z['x'][0], z['x'][1], z['V_cm3'], z['phi'], z['T_gas_K'], z['tau_ms']))
    i = R['injector']
    P('\n-- injector x%d (SLM IN625) --  air %.2f g/s, swirler A_eff %.1f mm2 -> %d vanes 45 deg, slot h %.2f mm, S %.2f, cup U %.0f m/s'
      % (i['n'], i['m_air_g_s'], i['A_eff_swirler_mm2'], i['n_vanes'], i['slot_h_mm'], i['swirl_number'], i['U_cup']))
    P('   gas %.3f g/s, %d x d%.2f, dP_gas %.2f bar -> manifold %.2f barg | phi_inj %.2f, S_L %.2f, S_T %.1f m/s, flashback margin bulk %.1f BL %.1f'
      % (i['m_gas_g_s'], i['n_gas_holes'], i['d_gas_hole_mm'], i['dP_gas_bar'], i['P_manifold_barg'], i['phi_injector'], i['S_L'], i['S_T'], i['flashback_margin_bulk'], i['flashback_margin_BL']))
    P('   premix time %.2f ms vs tau_ign(SC extrap.) %.1f ms -> margin %.0f (C2+ factor 3: %.0f); Da %.1f, phi_LBO Da %.2f / literature %.2f'
      % (i['premix_time_ms'], i['tau_ign_ms'], i['autoign_margin'], i['autoign_margin_NG_C2_factor3'], i['Da_design'], i['phi_LBO_Damkoehler'], i['phi_LBO_literature']))
    lt = R['liner_thermal']
    P('\n-- liner (Hastelloy-X 1.0) --  outer Tw max %.0f C, inner Tw max %.0f C (inner film %.1f %% cold), bypass out %.0f C, %.0f W into bypass'
      % (lt['outer_Tw_max_C'], lt['inner_Tw_max_C'], lt['f_inner_film_chosen'] * 100, lt['T_bypass_out_C'], lt['Q_into_bypass_W']))
    P('\n-- tunnel / bearings --')
    for k, v in R['tunnel']['options'].items():
        P('  %-26s tube %4.0f C  front brg %4.0f  rear brg %4.0f  rear flange %4.0f  oil %4.0f W  web %4.0f W %s' % (k, v['T_tube_max_C'], v['T_front_brg_C'], v['T_rear_brg_C'], v['T_rear_flange_C'], v['Q_to_oil_W'], v['Q_web_W'],
              ('shield %.0f C' % v['T_shield_max_C']) if v['T_shield_max_C'] else ''))
    P('  penalty (a)/(c) beta %.1f %%: %.2f kW, %.2f pts ; (b): %.2f kW, %.2f pts' % (BETA * 100, R['tunnel']['penalty_a_c']['dP_el_kW'], R['tunnel']['penalty_a_c']['deta_pts'], R['tunnel']['penalty_b']['dP_el_kW'], R['tunnel']['penalty_b']['deta_pts']))
    ct = R['casing_thermal']
    P('\n-- casing temperature --  with baffle %.0f C (baffle %.0f C), without %.0f C' % (ct['T_casing_with_baffle_C'], ct['T_baffle_C'], ct['T_casing_without_baffle_C']))
    m = R['casing_mech']
    P('-- casing mech --  f_hot %.1f MPa (creep), e_req %.2f mm (3.0 used); drum e_req %.2f (2.5); front wall %.2f (4.0); rear plate %.2f (5.0); bulkhead accident %.2f (3.0); test %.1f barg'
      % (m['f_hot_design'], m['e_hot_req_mm'], m['e_drum_req_mm'], m['t_front_wall_req'], m['t_rear_plate_req'], m['t_bulkhead_req_accident'], m['test_pressure_barg']))
    P('   mid flange %s' % {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m['flange_mid'].items()})
    P('   E2/E3 flange %s' % {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m['flange_E2E3'].items()})
    P('   C2 nozzle area: req %.0f mm2, avail %.0f mm2 ; %s' % (m['nozzle_C2_A_req_mm2'], m['nozzle_C2_A_avail_mm2'], m['PED']))
    n_ = R['insulation']
    P('-- insulation --  hot %d mm -> skin %.0f C (ventilated 45 C) / %.0f C still air; drum %d mm -> %.0f C; losses hot %.0f W, drum %.0f W, bulkhead leak %.0f W'
      % (n_['chosen_hot_mm'], n_['skin_hot_C'], n_['skin_hot_still_air_C'], n_['chosen_drum_mm'], n_['skin_drum_C'], n_['Q_loss_hot_casing_W'], n_['Q_loss_drum_W'], n_['Q_bulkhead_leak_W']))
    P('\n-- cycle --')
    for k, v in R['cycle'].items(): P('  %-42s P_el %5.2f kW  eta %5.2f %%  fuel %.3f g/s  T_rec %.0f C  eps %.3f  P3 %.3f bar' % (k, v['P_el_kW'], v['eta_el_pct'], v['mf_g_s'], v['T_rec_out_C'], v['eps'], v['P3_bar']))
    P('  TOTAL E2 penalty vs cycle model: %.2f kW, %.2f pts' % (R['penalty_total']['dP_el_kW'], R['penalty_total']['deta_pts']))
    P('\n-- thermal growth (mm) --')
    for k, v in GR.items(): P('  %-62s %+.2f' % (k, v))
    P('\n-- gas -- manifold %.2f barg (supply >= 3.5, margin %.2f bar), %.1f Nm3/h, DN15 %.1f m/s, ring %.1f m/s, stems %.1f m/s, maldistribution %.2f %%'
      % (GAS['P_manifold_barg'], GAS['regulator_margin_bar'], GAS['Nm3_h'], GAS['V_DN15'], GAS['V_ring_half'], GAS['V_stem'], GAS['maldistribution_pct']))
    P('-- light-off -- phi_inj %.2f, dP liner %.2f kPa, cup U %.1f m/s, T after %.0f C, MIE ~%.1f mJ flowing ~%.0f mJ' % (LO['phi_injector'], LO['dP_liner_kPa'], LO['U_cup'], LO['T_after_lightoff_C'], LO['MIE_quiescent_mJ'], LO['MIE_flowing_mJ_est']))
    P('\nwritten: sim/engine/e2_design.json, sim/engine/e2_results.json')
