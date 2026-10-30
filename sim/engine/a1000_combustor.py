#!/usr/bin/env python3
"""AURORA-1000 combustion system rev 1: one external vertical can (lean premixed, DLE) and the hot-gas scroll to NGV1.

PART A (this block) is imported by sim/engine/a1000_combustor_chem.py (Cantera) and by cad/engine/a1000_combustor.py:
design point from the project cycle, city gas, air split, load points, staged part-load cases.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'sim')); sys.path.insert(0, HERE)
import mw1_concept_study as G                                 # noqa: E402  (cycle)
import mw1_meanline as M                                      # noqa: E402  (selected case, 1 MW net)

FEA = os.path.join(HERE, 'fea')
CHEM_JSON = os.path.join(FEA, 'a1000_combustor_chem.json')
OUT_JSON = os.path.join(FEA, 'a1000_combustor.json')
IMG = os.path.join(ROOT, 'docs', 'img', 'a1000_combustor.png')

# ------------------------------------------------------------------------------------------------ city gas
# ASSUMPTION: no site analysis yet. Nominal = South-Pars-type grid gas matched to the project LHV (34.5 MJ/Sm3, 15 C);
# rich = high-C2+ excursion (LNG-like) for the auto-ignition / flashback sensitivity. C4+ lumped into C3H8 (GRI 3.0).
GAS = dict(nominal=dict(CH4=0.875, C2H6=0.050, C3H8=0.020, N2=0.045, CO2=0.010),
           rich=dict(CH4=0.820, C2H6=0.100, C3H8=0.050, N2=0.020, CO2=0.010))
_HC = dict(CH4=(1, 4, 802.3), C2H6=(2, 6, 1428.6), C3H8=(3, 8, 2043.1))          # C, H atoms, LHV kJ/mol
_W = dict(CH4=16.043, C2H6=30.069, C3H8=44.096, N2=28.013, CO2=44.010)
W_AIR = 28.85                                                                       # dry air O2 0.21 / N2 0.79


def fuel_props(name):
    x = GAS[name]; W = sum(v * _W[s] for s, v in x.items())
    lhv = sum(v * _HC[s][2] for s, v in x.items() if s in _HC)                     # kJ/mol
    o2 = sum(v * (_HC[s][0] + _HC[s][1] / 4) for s, v in x.items() if s in _HC)
    return dict(W=W, LHV=lhv / W * 1e6, LHV_Sm3=lhv / 23.645, f_st=W / (o2 / 0.21 * W_AIR),
                rho_std=W / 23.645)                                                 # J/kg, MJ/Sm3, -, kg/Sm3 (15 C, 1 atm)


FUEL = fuel_props('nominal')

# ------------------------------------------------------------------------------------------------ design point
_r = G.cycle(M.CASE, 'design_chilled')
MA = M.P_NET / _r['P_net']                                     # compressor air [kg/s]
DPT = dict(ma=MA, m_can=MA * (1 - G.BASE['leak']), T_in=_r['T2r'], T2=_r['T2'], P2=_r['P2'],
           P_in=_r['P2'] * (1 - G.BASE['dp_rec_c']), P3=_r['P3'], TIT=M.CASE['TIT'], Q_fuel=_r['Q_fuel'] * MA,
           dp_budget=G.BASE['dp_comb'])
DPT['m_fuel'] = DPT['Q_fuel'] / FUEL['LHV']
DPT['phi_ov'] = DPT['m_fuel'] / DPT['m_can'] / FUEL['f_st']
DPT['gas_Sm3_h'] = DPT['m_fuel'] / FUEL['rho_std'] * 3600
DP = dict(P_pz=DPT['P_in'] * (1 - 0.031))                      # liner (primary-zone) pressure, from the budget below

# ------------------------------------------------------------------------------------------------ air split (of the can air)
# premixers 30.5 %: phi_pz = phi_ov / 0.305 ~ 0.47 -> T_ad ~ 1860 K at 886 K air (Cantera); the rest is impingement
# cooling air for the primary-zone liner that then enters as dilution air (double-annulus scheme, see PART B)
SPLIT = dict(premix=0.305, dilution=0.665, seals=0.015, purge=0.015)
N_PM = 7                                                       # 1 pilot premixer (centre) + 6 mains
STAGES = dict(P=[0], A=[1, 3, 5], B1=[2], B2=[4, 6])          # fuel circuits; premixer 0 centre, 1..6 on the ring
N_OPTIONS = (7, 5, 4)                                          # fuelled premixers: P+A+B1+B2, P+A+B1, P+A


# ------------------------------------------------------------------------------------------------ load points
def load_points():
    """constant speed, constant air flow: load is set by TIT (cycle at fixed PR; P3 scaled with the NGV flow function)"""
    out = {}
    for key, tit in (('100', 1223.15), ('90', 1173.15), ('75', 1073.15), ('50', 923.15)):
        r = G.cycle(dict(M.CASE, TIT=tit), 'design_chilled')
        out[key] = dict(TIT=tit, T_air=r['T2r'], P_net_kW=r['P_net'] * MA / 1e3, load=r['P_net'] / _r['P_net'],
                        Q_fuel_kW=r['Q_fuel'] * MA / 1e3, P3=DPT['P3'] * math.sqrt(tit / DPT['TIT']))
        out[key]['phi_ov'] = out[key]['Q_fuel_kW'] * 1e3 / FUEL['LHV'] / DPT['m_can'] / FUEL['f_st']
    r = G.cycle(M.CASE, 'borazjan_hot')
    out['hot'] = dict(TIT=DPT['TIT'], T_air=r['T2r'], P_net_kW=r['P_net'] * MA / 1e3, load=r['P_net'] / _r['P_net'],
                      Q_fuel_kW=r['Q_fuel'] * MA / 1e3, P3=DPT['P3'])
    out['hot']['phi_ov'] = out['hot']['Q_fuel_kW'] * 1e3 / FUEL['LHV'] / DPT['m_can'] / FUEL['f_st']
    return out


LOAD = load_points()
LOAD_AIR = {k: (v['T_air'], v['TIT']) for k, v in LOAD.items()}
TAU_PZ_MS = 20.0                                               # primary-zone residence time used for the staged CRN


def staged_cases():
    """part load with pilot + stage A (4 premixers) or all 7 fuelled; the CRN in a1000_combustor_chem.py"""
    cases = []
    for key in ('90', '75', '50'):
        phi_all = LOAD[key]['phi_ov'] / SPLIT['premix']
        for n in (7, 6, 5, 4):
            phi_f = phi_all * N_PM / n
            if phi_f > 0.80: continue
            cases.append(dict(load=key, n_fuelled=n, phi_f=phi_f, T_air=LOAD[key]['T_air'], TIT=LOAD[key]['TIT'],
                              x_unf=(N_PM - n) / n, tau_pz_ms=TAU_PZ_MS))
    return cases


# ================================================================================================ PART B (calculation)
# Layout (rotor frame mm, x = engine axis from the gearbox coupling face, z up; can axis vertical):
#   can        vertical, above the turbine inlet. Hot air (recuperator, 613 C) enters at the can bottom, rises in the
#              OUTER annulus (casing - impingement sleeve); over the primary zone part of it jets through the sleeve onto
#              the liner (impingement), the spent air runs DOWN the inner gap and enters the liner through the dilution
#              holes; the rest reaches the head end and feeds the 7 premixers. The premix air never touches the hot
#              liner, so its temperature (auto-ignition, flame speed) is the recuperator outlet temperature.
#   scroll     hot-gas casing (Haynes 230, uncooled, insulated outside): neck from the liner exit down into a two-branch
#              scroll (both branches from the top to the bottom) over the turbine outer casing, a vaned (22 deswirl
#              vanes) inward radial passage and an accelerating bend into the NGV1 annulus. NGV1 keeps its axial inlet.
#   mid-casing scroll pressure casing (P355NH, cool): compressor delivery air (175 C) from the collector flows around the
#              scroll, under its body along the hot-section outer casing and around that casing's front flange into the
#              carrier channels (the hot-section rev 1 interface is unchanged); the scroll walls only see the combustor
#              pressure drop (~0.2 bar), the mid-casing carries the 2.8 bar(g)
SIG = 5.670e-8
R_AIR = 287.05
_CP = [(300, 1005), (400, 1014), (500, 1030), (600, 1051), (700, 1075), (800, 1099), (900, 1121), (1000, 1142),
       (1100, 1161), (1200, 1179), (1300, 1197), (1400, 1214), (1500, 1230), (1600, 1244), (1800, 1268), (2000, 1288)]


def cp_air(T):
    for (t0, c0), (t1, c1) in zip(_CP[:-1], _CP[1:]):
        if T <= t1: return c0 + (c1 - c0) * (T - t0) / (t1 - t0)
    return _CP[-1][1]


def mu_air(T): return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)
def k_air(T): return 0.0241 * (T / 273.15) ** 0.81
def rho(P, T): return P / (R_AIR * T)


def interfaces():
    """hot section / rotor / compressor concept faces this design must meet"""
    sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
    import a1000_hot_section as H                              # noqa: E402  (imports a1000_rotor as H.G)
    A, o = H.A, H.G.X_OFF
    # compressor rev 1 (sim/a1000_impeller_design.json): barrel and discharge collector as cad/engine/a1000_viewer_export.py
    ID = json.load(open(os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')))
    g1, g2 = ID['stages']['C1']['geometry'], ID['stages']['C2']['geometry']
    d1, d2 = ID['stages']['C1']['performance']['diffuser'], ID['stages']['C2']['performance']['diffuser']
    xsd2 = g2['x_s2'] + (g2['b2'] - d2['b3']); r_col = d2['r4'] + 45.0; x_col = 0.5 * (xsd2 + g2['x_h2'])
    R_out = max(d1['r4'] + ID['return_channel']['R_bend_out'] + 25.0, r_col + 38.0 + 12.0)
    x_le = A.X_LE['N1'] + o
    return dict(x_ngv_le=x_le, x_ngv_ring=x_le - 4.0, r_hub=A.r_hub(A.X_LE['N1']), r_tip=A.r_tip(A.X_LE['N1']),
                cas=dict(H.CAS), c1=dict(H.C1), x_pin=H.X_PIN, x_drum_r1=H.G.X_J['drum_R1'], r_drum=85.0,
                barrel=dict(x1=g2['x0'] + g2['L'] + 30.0, r=R_out + 12.0, x_coll=x_col, r_coll=r_col, R_coll=38.0),
                T2=DPT['T2'], P2=DPT['P2'])


# ------------------------------------------------------------------------------------------------ geometry (single source)
GEO = dict(
    # liner + can (z up from the engine axis; can axis at x_can, y 0)
    x_can=665.0, D_L=420.0, t_L=1.6, tbc=0.4, L_pz=400.0, L_dz=400.0, D_exit=356.0, z_exit=830.0, L_sleeve=55.0, L_cone=40.0,
    g_inner=22.0, t_sleeve=2.0, D_case=620.0, t_case=10.0, z_base=800.0, H_plenum=200.0, t_cover=50.0,
    D_hot_in=438.0, z_hot_in=1140.0,                               # DN450 hot-air nozzle (+y side, towards the recuperator)
    imp_d=6.0, imp_xd=3.2,                                          # impingement holes and pitch / d
    rib_dz=dict(e=2.5, p=25.0),                                     # DZ liner outside: circumferential ribs
    n_dil=(18, 18), sw_vanes=10, sw_angle=35.0, nu_cb=0.42, L_mt_D=2.2, fuel_holes=10,
    r_ring_pm=128.0,                                               # main premixer pitch circle (6 x 60 deg)
    # hot-gas casing (gas-side surfaces)
    x_front=564.0, x_rear_t=632.0, x_rear_s=835.0, r_body_in=455.0, r_vane_le=425.0, r_vane_te=315.0, w_te=46.0,
    R_tip_bend=28.0, V_s=60.0, h_min=30.0, n_vanes=22, t_vane=8.0, t_wall=5.0, t_ins=12.0, rib_pitch=70.0,
    neck_b=195.0, z_neck0=560.0, z_neck_c=730.0, D_neck=360.0, z_neck1=860.0,
    # mid-casing (eccentric cylinder) and its end plates
    x_mc0=430.0, x_mc1=903.0, t_mc=12.0, t_end=25.0, R_mc=650.0, z_mc=110.0, r_noz=205.0, z_noz=780.0,
)


def liner_stations():
    g = GEO
    z_dz0 = g['z_exit'] + g['L_sleeve'] + g['L_cone']; z_pz0 = z_dz0 + g['L_dz']; z_dome = z_pz0 + g['L_pz']
    return dict(z_dz0=z_dz0, z_pz0=z_pz0, z_dome=z_dome, z_cover=z_dome + g['H_plenum'], z_top=z_dome + g['H_plenum'] + g['t_cover'])


def scroll_area(theta_deg, Q):
    """circumferential flow area needed in one branch at theta (0 top .. 180 bottom) [m2]"""
    return Q / 2 * max(0.0, 1 - theta_deg / 180.0) / GEO['V_s']


def r_out(theta_deg, Q):
    """scroll body outer (gas-side) radius [mm]: body x_front..x_rear_s, r_body_in..r_out + the throat strip"""
    g = GEO
    a_throat = (g['x_rear_t'] - g['x_front']) * (g['r_body_in'] - g['r_vane_le']) * 1e-6
    w = (g['x_rear_s'] - g['x_front']) * 1e-3
    h = max(g['h_min'], (scroll_area(theta_deg, Q) - a_throat) / w * 1e3)
    return g['r_body_in'] + h


def x_front_at(r):
    """front (hub-side) wall of the vaned passage: x_front above the vane LE, converging to x_rear_t - w_te at the TE"""
    g = GEO
    if r >= g['r_vane_le']: return g['x_front']
    x_te = g['x_rear_t'] - g['w_te']
    if r <= g['r_vane_te']: return x_te
    return g['x_front'] + (x_te - g['x_front']) * (g['r_vane_le'] - r) / (g['r_vane_le'] - g['r_vane_te'])


def meridional(I, n=24):
    """gas-side hub and tip curves of the transition (x, r) from the vane LE down to the NGV1 ring face"""
    g = GEO; x_ex = I['x_ngv_ring'] - 1.0
    x_te = g['x_rear_t'] - g['w_te']; a = 640.0 - x_te; b = g['r_vane_te'] - I['r_hub']
    hub = [(x_front_at(r), r) for r in np.linspace(g['r_vane_le'], g['r_vane_te'], 6)]
    hub += [(640.0 - a * math.cos(t), g['r_vane_te'] - b * math.sin(t)) for t in np.linspace(0, math.pi / 2, n)[1:]]
    hub += [(x_ex, I['r_hub'])]
    Rt = g['R_tip_bend']; xc, rc = g['x_rear_t'] + Rt, I['r_tip'] + Rt
    tip = [(g['x_rear_t'], r) for r in np.linspace(g['r_vane_le'], rc, 6)]
    tip += [(xc - Rt * math.cos(t), rc - Rt * math.sin(t)) for t in np.linspace(0, math.pi / 2, n)[1:]]
    tip += [(x_ex, I['r_tip'])]
    return hub, tip


# ------------------------------------------------------------------------------------------------ chemistry lookups
def chem():
    if not os.path.exists(CHEM_JSON):
        raise SystemExit('run sim/engine/a1000_combustor_chem.py first (Cantera)')
    return json.load(open(CHEM_JSON))


def _interp_log(xs, ys, x):
    ys = np.maximum(np.asarray(ys, float), 1e-6)
    return float(np.exp(np.interp(x, xs, np.log(ys))))


def flame_at(CH, load, phi, key='SL'):
    fl = sorted([f for f in CH['flames'] if f['load'] == load], key=lambda f: f['phi'])
    return float(np.interp(phi, [f['phi'] for f in fl], [f[key] for f in fl]))


def emissions(CH, load, phi_m, t_pz, t_dz, S=0.0):
    """NOx (after t_pz in the primary zone) and CO (after the dilution zone + scroll, t_dz) in ppmvd @ 15 % O2 for a
    premixer mean phi_m with spatial unmixedness S = sigma_phi / phi (Gaussian, each pocket burns on its own)"""
    fl = sorted([f for f in CH['flames'] if f['load'] == load], key=lambda f: f['phi'])
    ph = [f['phi'] for f in fl]
    nox = [_interp_log(CH['t_pz_ms'], [p['NOx'] for p in f['pz']], t_pz) for f in fl]
    co = [_interp_log(CH['t_dz_ms'], [p['CO'] for p in f['dz']], t_dz) if 'dz' in f else 1e4 for f in fl]
    if S <= 0: return _interp_log(ph, nox, phi_m), _interp_log(ph, co, phi_m)
    xs = np.linspace(-3, 3, 61); w = np.exp(-xs ** 2 / 2); w /= w.sum()
    phis = np.clip(phi_m * (1 + S * xs), ph[0], ph[-1])
    return (float(sum(wi * _interp_log(ph, nox, p) for wi, p in zip(w, phis))),
            float(sum(wi * _interp_log(ph, co, p) for wi, p in zip(w, phis))))


def tau_ign_min(CH, gas, T_air, phi_max=1.0):
    rows = [r for r in CH['ignition'] if r['gas'] == gas and r['phi'] <= phi_max]
    Ts = sorted({r['T_air'] for r in rows})
    per_T = [min(r['tau_s'] for r in rows if r['T_air'] == T) for T in Ts]
    return _interp_log(Ts, per_T, T_air)


def phi_lbo(CH, load, tau_rz_ms, margin=3.0):
    """leanest phi whose PSR blow-out time is below tau_rz / margin (flame anchor in the recirculation zones)"""
    rows = sorted([r for r in CH['psr'] if r['load'] == load], key=lambda r: r['phi'])
    ph = [r['phi'] for r in rows]; tb = [r['tau_bo_ms'] for r in rows]
    target = tau_rz_ms / margin
    for i in range(len(ph) - 1):
        if tb[i] >= target >= tb[i + 1]:
            f = (math.log(target) - math.log(tb[i])) / (math.log(tb[i + 1]) - math.log(tb[i]))
            return ph[i] + f * (ph[i + 1] - ph[i])
    return ph[0] if tb[0] < target else ph[-1]


# ------------------------------------------------------------------------------------------------ the calculation
def design():
    I = interfaces(); CH = chem(); g = GEO; R = {}; checks = []
    GEO['x_mc1'] = I['cas']['x1'] + GEO['t_end']                  # rear plate bolts on the hot-section casing rear flange

    def check(name, value, limit, ok, unit=''):
        checks.append(dict(name=name, value=value, limit=limit, ok=bool(ok), unit=unit))

    m = DPT['m_can']; T_in = DPT['T_in']; P_in = DPT['P_in']; mf = DPT['m_fuel']; m_ex = m + mf
    rho_in = rho(P_in, T_in)
    R['design_point'] = dict(m_can=m, T_in_C=T_in - 273.15, P_in_bar=P_in / 1e5, P3_bar=DPT['P3'] / 1e5, TIT_C=DPT['TIT'] - 273.15,
                             m_fuel=mf, Q_fuel_kW=DPT['Q_fuel'] / 1e3, gas_Sm3_h=DPT['gas_Sm3_h'], phi_overall=DPT['phi_ov'],
                             LHV_MJ_kg=FUEL['LHV'] / 1e6, LHV_MJ_Sm3=FUEL['LHV_Sm3'], f_st=FUEL['f_st'],
                             chem_fuel=CH['fuel'], dp_budget=DPT['dp_budget'])
    # ---------------------------------------------------------------------------------------------- 1. air split, phi
    m_pm = SPLIT['premix'] * m; m_dil = SPLIT['dilution'] * m
    phi_pz = mf / m_pm / FUEL['f_st']
    T_ad = flame_at(CH, '100', phi_pz, 'Tad'); T_u = flame_at(CH, '100', phi_pz, 'Tu')
    R['split'] = dict(SPLIT, m_premix=m_pm, m_dilution=m_dil, phi_pz=phi_pz, T_ad_K=T_ad, T_mix_K=T_u)
    # ---------------------------------------------------------------------------------------------- 2. pressure budget
    DPF = dict(premixer=0.028, impingement=0.008)               # design choices (fractions of P_in)
    dp = {}
    A_noz = math.pi / 4 * (g['D_hot_in'] * 1e-3) ** 2; V_noz = m / (rho_in * A_noz)
    dp['inlet nozzle dump'] = 1.0 * 0.5 * rho_in * V_noz ** 2
    D_s = (g['D_L'] + 2 * g['t_L'] + 2 * g['g_inner'] + 2 * g['t_sleeve']) * 1e-3
    A_out = math.pi / 4 * ((g['D_case'] * 1e-3) ** 2 - D_s ** 2); V_out = m / (rho_in * A_out)
    Dh_out = g['D_case'] * 1e-3 - D_s
    Re_o = rho_in * V_out * Dh_out / mu_air(T_in); f_o = 0.316 * Re_o ** -0.25
    L_case = (liner_stations()['z_dome'] - g['z_base']) * 1e-3
    dp['outer annulus + head turn'] = (f_o * L_case / Dh_out + 1.0 * (SPLIT['premix'] + SPLIT['purge']) ** 2) * 0.5 * rho_in * V_out ** 2
    dp['premixers'] = DPF['premixer'] * P_in
    # liner: heat addition in the PZ (momentum: rho u^2 (T_ad / T_u - 1)) and the radial dilution jets, whose dynamic
    # head is lost while the mixture accelerates to the liner exit velocity
    T_ex = DPT['TIT']; A_L = math.pi / 4 * (g['D_L'] * 1e-3) ** 2; rho_ex = rho(P_in * 0.965, T_ex)
    V_L = m_ex / (rho_ex * A_L)
    T_ad0 = flame_at(chem(), '100', mf / (SPLIT['premix'] * m) / FUEL['f_st'], 'Tad'); rho_u0 = rho(P_in * 0.97, 850.0)
    u_u = SPLIT['premix'] * m / (rho_u0 * A_L); rho_pz0 = rho(P_in * 0.97, T_ad0); u_pz = (SPLIT['premix'] * m + mf) / (rho_pz0 * A_L)
    dp['liner heat addition + DZ mixing'] = rho_u0 * u_u ** 2 * (T_ad0 / 850.0 - 1) + max(0.0, 0.5 * rho_ex * V_L ** 2 - 0.5 * rho_pz0 * u_pz ** 2)
    # exit cone + neck + T split into the two scroll branches (profiled splitter vane): K on the neck head
    Q_g = m_ex / rho(DPT['P3'] * 1.005, T_ex)
    A_nk = (g['x_rear_s'] - g['x_front']) * 1e-3 * 2 * g['neck_b'] * 1e-3; V_nk = Q_g / A_nk
    A_ex = math.pi / 4 * (g['D_exit'] * 1e-3) ** 2; V_lex = Q_g / A_ex
    rho_g = m_ex / Q_g
    dp['liner exit + neck'] = 0.05 * 0.5 * rho_g * V_lex ** 2 + max(0.0, 1 - A_ex / A_nk) ** 2 * 0.5 * rho_g * V_lex ** 2 * 0.3
    dp['scroll T split'] = 0.50 * 0.5 * rho_g * V_nk ** 2
    # scroll: friction along half a branch (mean path) + forward migration from the body into the vaned throat
    Vs = g['V_s']; th = np.linspace(5, 175, 18); r_c = np.mean([0.5 * (g['r_body_in'] + r_out(t, Q_g)) for t in th])
    A_mean = np.mean([scroll_area(t, Q_g) for t in th]); w_b = (g['x_rear_s'] - g['x_front']) * 1e-3
    Dh_s = 4 * A_mean / (2 * (w_b + A_mean / w_b))
    L_br = math.pi * r_c * 1e-3 / 2
    Re_s = rho_g * Vs * Dh_s / 4.9e-5; f_s = 0.316 * Re_s ** -0.25
    dp['scroll friction'] = f_s * L_br / Dh_s * 0.5 * rho_g * Vs ** 2
    dp['scroll forward migration'] = 0.30 * 0.5 * rho_g * Vs ** 2
    # deswirl cascade: free vortex from the body centroid to the vane LE, radial at the TE (Lieblein diffusion factor)
    r_le, r_te = g['r_vane_le'] * 1e-3, g['r_vane_te'] * 1e-3
    w_le = (g['x_rear_t'] - g['x_front']) * 1e-3; w_te = g['w_te'] * 1e-3
    ct1 = Vs * r_c * 1e-3 / r_le; cr1 = Q_g / (2 * math.pi * r_le * w_le); V1 = math.hypot(ct1, cr1)
    cr2 = Q_g / (2 * math.pi * r_te * w_te); V2 = cr2
    alpha1 = math.degrees(math.atan2(ct1, cr1))
    pitch = 2 * math.pi * 0.5 * (r_le + r_te) / g['n_vanes']
    chord = (r_le - r_te) / math.cos(math.radians(alpha1 / 2))
    sigma = chord / pitch
    DF = 1 - V2 / V1 + ct1 / (2 * sigma * V1)
    omega = 0.025 + 0.15 * max(0.0, DF - 0.3)                                 # profile + low-aspect-ratio end-wall loss
    dp['deswirl vanes (22)'] = omega * 0.5 * rho_g * V1 ** 2
    # bend + approach to NGV1 (accelerating): K = 0.03 of the NGV1 inlet dynamic head
    A_ngv = math.pi * ((I['r_tip'] * 1e-3) ** 2 - (I['r_hub'] * 1e-3) ** 2); V_ngv = Q_g / A_ngv
    dp['bend + NGV1 approach'] = 0.03 * 0.5 * rho_g * V_ngv ** 2
    dp_tot = sum(dp.values())
    R['pressure'] = dict(items_kPa={k: v / 1e3 for k, v in dp.items()}, items_pct={k: 100 * v / P_in for k, v in dp.items()},
                         total_pct=100 * dp_tot / P_in, budget_pct=100 * DPT['dp_budget'], P3_reached_bar=(P_in - dp_tot) / 1e5,
                         P3_cycle_bar=DPT['P3'] / 1e5, V=dict(nozzle=V_noz, outer_annulus=V_out, liner_exit=V_lex, neck=V_nk, scroll=Vs,
                                                              vane_in=V1, vane_out=V2, ngv_in=V_ngv, liner_dz=V_L))
    check('combustor + scroll total pressure loss', 100 * dp_tot / P_in, 100 * DPT['dp_budget'], dp_tot / P_in <= DPT['dp_budget'], '%')
    # cycle effect of the loss difference (dp_comb in the project cycle)
    r_dp = G.cycle(dict(M.CASE, dp_comb=dp_tot / P_in), 'design_chilled')
    R['pressure']['eta_el_effect_pt'] = 100 * (r_dp['eta_el'] - _r['eta_el'])
    # ---------------------------------------------------------------------------------------------- 3. premixers
    rho_pm = rho(P_in * 0.995, T_u)
    k_sw = 1.15 * (1 + math.tan(math.radians(g['sw_angle'])) ** 2)            # dump of axial + swirl head, vanes, tube
    U_ex = math.sqrt(2 * DPF['premixer'] * P_in / (k_sw * rho_pm))
    A_one = m_pm / N_PM / (rho_pm * U_ex); nu = g['nu_cb']
    D_o = math.sqrt(4 * A_one / (math.pi * (1 - nu ** 2))); D_cb = nu * D_o
    L_mt = g['L_mt_D'] * D_o; L_sw = 0.45 * D_o
    S_n = 2 / 3 * (1 - nu ** 3) / (1 - nu ** 2) * math.tan(math.radians(g['sw_angle']))
    tau_pm = (L_mt + L_sw) / U_ex + 0.6e-3                                    # + swirler passage / fuel jet mixing
    Dh_pm = D_o - D_cb; Re_pm = rho_pm * U_ex * Dh_pm / mu_air(T_u)
    f_pm = 0.316 * Re_pm ** -0.25; tau_w = f_pm / 8 * rho_pm * U_ex ** 2; g_wall = tau_w / mu_air(T_u)
    # fuel injection through the swirler vanes (10 holes per premixer)
    p_local = P_in - dp['inlet nozzle dump'] - dp['outer annulus + head turn'] - 0.5 * rho_pm * (U_ex * 0.8) ** 2
    dP_f = 0.30e5; p_man = p_local + dP_f
    rho_f = p_man * FUEL['W'] / (8314.46 * 288.15)
    V_f = 0.80 * math.sqrt(2 * dP_f / rho_f)
    A_holes = mf / N_PM / (rho_f * V_f); d_hole = math.sqrt(4 * A_holes / g['fuel_holes'] / math.pi)
    J = rho_f * V_f ** 2 / (rho_pm * (0.8 * U_ex) ** 2)
    y_pen = 1.6 * d_hole * J ** 0.5 * 8.0 ** (1 / 3)                         # Holdeman-type, at x/d = 8
    p_supply = G.GAS_SUPPLY_BARG_MIN * 1e5 + G.P_ATM - 0.40e5 - 0.03e5        # station min - valve train - lances
    R['premixer'] = dict(n=N_PM, D_o_mm=D_o * 1e3, D_cb_mm=D_cb * 1e3, L_mt_mm=L_mt * 1e3, U_ex=U_ex, swirl_number=S_n,
                         tau_res_ms=tau_pm * 1e3, Re=Re_pm, g_wall=g_wall, fuel=dict(dP_bar=dP_f / 1e5, holes=g['fuel_holes'],
                         d_mm=d_hole * 1e3, V=V_f, J=J, penetration_mm=y_pen * 1e3, gap_mm=Dh_pm * 1e3 / 2, p_manifold_bar=p_man / 1e5,
                         p_available_bar=p_supply / 1e5, margin_bar=(p_supply - p_man) / 1e5))
    check('fuel supply margin, no booster (100 %)', (p_supply - p_man) / 1e5, 0.05, p_supply - p_man >= 0.05e5, 'bar')
    check('fuel jet penetration / passage half-gap', y_pen / (Dh_pm / 2), 0.6, 0.6 <= y_pen / (Dh_pm / 2) <= 1.4, '-')
    # ---------------------------------------------------------------------------------------------- 4. flashback, auto-ignition
    phi_hi = phi_pz * (1 + 3 * 0.06)                                             # +3 sigma of the unmixedness
    fb = {}
    for case, (load, gas, phi) in dict(design=('100', 'nominal', phi_pz), unmixed_peak=('100', 'nominal', phi_hi),
                                       hot_day=('hot', 'nominal', phi_hi), transient=('hot', 'nominal', 0.65)).items():
        SL = flame_at(CH, load, phi, 'SL'); al = flame_at(CH, load, phi, 'alpha_u')
        fb[case] = dict(phi=phi, SL=SL, alpha=al)
    rich = sorted([f for f in CH['flames_rich'] if abs(f['T_air'] - LOAD['hot']['T_air']) < 1], key=lambda f: f['phi'])
    fb['rich_gas_transient'] = dict(phi=0.65, SL=float(np.interp(0.65, [f['phi'] for f in rich], [f['SL'] for f in rich])),
                                    alpha=float(np.interp(0.65, [f['phi'] for f in rich], [f['alpha_u'] for f in rich])))
    for k, v in fb.items():
        v['g_c_turb'] = 0.64 * v['SL'] ** 2 / v['alpha']                       # confined turbulent BL flashback (10 x Lewis-von Elbe)
        v['bl_margin'] = g_wall / v['g_c_turb']
        u_p = 0.12 * U_ex; l_t = 0.1 * Dh_pm
        v['S_T'] = 0.52 * u_p ** 0.75 * v['SL'] ** 0.5 * v['alpha'] ** -0.25 * l_t ** 0.25 + v['SL']   # Zimont
        v['core_margin'] = U_ex / v['S_T']
    R['flashback'] = fb
    check('boundary-layer flashback g_wall / g_c (rich gas, phi 0.65, hot day)', fb['rich_gas_transient']['bl_margin'], 3.0,
          fb['rich_gas_transient']['bl_margin'] >= 3.0, '-')
    check('core flashback U / S_T (rich gas, phi 0.65, hot day)', fb['rich_gas_transient']['core_margin'], 3.0,
          fb['rich_gas_transient']['core_margin'] >= 3.0, '-')
    check('swirl number with centre-body purge jet (CIVB)', S_n, 0.60, S_n <= 0.60, '-')
    ai = {}
    for case, (gas, T) in dict(design=('nominal', T_in), hot_day=('nominal', LOAD['hot']['T_air']),
                               hot_day_rich=('rich', LOAD['hot']['T_air']), air_plus_25K_rich=('rich', LOAD['hot']['T_air'] + 25.0)).items():
        t = tau_ign_min(CH, gas, T); ai[case] = dict(T_air=T, tau_ign_s=t, ratio=t / tau_pm, ratio_gri_x10=t / 10 / tau_pm)
    R['autoignition'] = ai
    check('auto-ignition delay / premixer residence (rich gas, hot day + 25 K, GRI / 10)', ai['air_plus_25K_rich']['ratio_gri_x10'], 10.0,
          ai['air_plus_25K_rich']['ratio_gri_x10'] >= 10.0, '-')
    # ---------------------------------------------------------------------------------------------- 5. liner volumes, emissions
    ls = liner_stations()
    V_pz = A_L * g['L_pz'] * 1e-3; V_dz = A_L * g['L_dz'] * 1e-3
    rho_pz = rho(P_in * 0.968, T_ad); tau_pz = V_pz * rho_pz / (m_pm + mf)
    rho_dz = rho(P_in * 0.967, 0.5 * (T_ad + T_ex)); tau_dz = V_dz * rho_dz / m_ex
    V_scroll = 2 * sum(scroll_area(t, Q_g) * math.radians(10) * 0.5 * (g['r_body_in'] + r_out(t, Q_g)) * 1e-3
                       for t in np.arange(5, 180, 10)) + 0.03
    tau_sc = V_scroll * rho_g / m_ex
    em = {}
    for S in (0.0, 0.06, 0.10):
        nox, co = emissions(CH, '100', phi_pz, tau_pz * 1e3, (tau_dz + tau_sc) * 1e3, S)
        em['S=%.2f' % S] = dict(NOx=nox, CO=co)
    nox_hot, co_hot = emissions(CH, 'hot', LOAD['hot']['phi_ov'] / SPLIT['premix'], tau_pz * 1e3, (tau_dz + tau_sc) * 1e3, 0.10)
    em['hot_day S=0.10'] = dict(NOx=nox_hot, CO=co_hot)
    R['liner'] = dict(D_L=g['D_L'], L_pz=g['L_pz'], L_dz=g['L_dz'], V_pz_m3=V_pz, V_dz_m3=V_dz, tau_pz_ms=tau_pz * 1e3, tau_dz_ms=tau_dz * 1e3,
                      V_scroll_m3=V_scroll, tau_scroll_ms=tau_sc * 1e3, U_ref_pz=(m_pm + mf) / (rho_pz * A_L), stations=ls)
    R['emissions_100'] = em
    check('NOx at 100 % load, unmixedness 0.10, hot day', nox_hot, 25.0, nox_hot < 25.0, 'ppm @15 % O2')
    check('CO at 100 % load, unmixedness 0.10', em['S=0.10']['CO'], 10.0, em['S=0.10']['CO'] < 10.0, 'ppm @15 % O2')
    # lean blow-out margin of the anchor (centre-body wake + outer recirculation)
    tau_rz = 2 * D_cb / (0.3 * U_ex)
    lbo = {k: phi_lbo(CH, k, tau_rz * 1e3) for k in ('100', '50')}
    R['lbo'] = dict(tau_rz_ms=tau_rz * 1e3, phi_lbo_100=lbo['100'], phi_lbo_50=lbo['50'], margin_100=phi_pz / lbo['100'])
    check('lean blow-out margin phi / phi_LBO (100 %)', phi_pz / lbo['100'], 1.25, phi_pz / lbo['100'] >= 1.25, '-')
    R['_keep'] = dict(I=I, CH=CH, U_ex=U_ex, D_o=D_o, D_cb=D_cb, Q_g=Q_g, rho_g=rho_g, T_ad=T_ad, phi_pz=phi_pz, m_pm=m_pm,
                      m_dil=m_dil, DPF=DPF, dp=dp, dp_tot=dp_tot, tau_pz=tau_pz, tau_dz=tau_dz, tau_sc=tau_sc, V_ngv=V_ngv,
                      ct1=ct1, cr1=cr1, alpha1=alpha1, DF=DF, sigma=sigma, chord=chord, A_L=A_L, V_L=V_L, rho_pm=rho_pm, T_u=T_u,
                      dP_f=dP_f, p_local=p_local, p_supply=p_supply, lbo=lbo)
    R['scroll'] = dict(Q_m3s=Q_g, V_s=Vs, r_c_mm=r_c, alpha_vane_in_deg=alpha1, c_theta_in=ct1, c_r_in=cr1, V1=V1, V2=V2, DF=DF,
                       omega=omega, sigma=sigma, chord_mm=chord * 1e3, n_vanes=g['n_vanes'],
                       r_out_mm={str(t): r_out(t, Q_g) for t in range(0, 181, 15)})
    check('deswirl vane diffusion factor (Lieblein)', DF, 0.55, DF <= 0.55, '-')
    check('deswirl vane de Haller V2 / V1', V2 / V1, 0.72, V2 / V1 >= 0.72, '-')
    return R, checks


def lefebvre_wall(Tg, q_fa, P, Dl, m_g, A_g, F_conv, h_c, Tc, T_sink, eps_sink, t_tbc, t_m):
    """1-D liner wall balance (Lefebvre & Herbert): gas radiation + convection in = conduction through TBC + metal =
    cold-side convection + radiation out. Returns (T_tbc surface, T_metal hot side, T_metal cold side, q W/m2)"""
    k_tbc, k_m, eps_w = 1.0, 24.0, 0.45
    mu_g = mu_air(Tg) * 1.02; k_g = k_air(Tg) * 1.05
    lb = 0.6 * Dl
    eps_g = 1 - math.exp(-290.0 * P / 1e3 * 1.0 * (q_fa * lb) ** 0.5 * Tg ** -1.5)
    def q_in(Tw1):
        R1 = 0.5 * SIG * (1 + eps_w) * eps_g * Tg ** 1.5 * (Tg ** 2.5 - Tw1 ** 2.5)
        C1 = 0.020 * k_g / Dl ** 0.2 * (m_g / (A_g * mu_g)) ** 0.8 * (Tg - Tw1) * F_conv
        return R1 + C1
    Rw = t_tbc / k_tbc + t_m / k_m
    lo, hi = Tc, Tg
    for _ in range(80):
        Tw1 = 0.5 * (lo + hi); q = q_in(Tw1); Tw2 = Tw1 - q * Rw
        q_out = h_c * (Tw2 - Tc) + SIG * eps_sink * (Tw2 ** 4 - T_sink ** 4)
        if q_out > q: hi = Tw1
        else: lo = Tw1
    return Tw1, Tw1 - q * t_tbc / k_tbc, Tw2, q


def design2(R, checks):
    def check(name, value, limit, ok, unit=''):
        checks.append(dict(name=name, value=value, limit=limit, ok=bool(ok), unit=unit))
    K = R['_keep']; g = GEO; I = K['I']; CH = K['CH']
    m = DPT['m_can']; T_in = DPT['T_in']; P_in = DPT['P_in']; mf = DPT['m_fuel']; m_ex = m + mf; T_ex = DPT['TIT']
    ls = R['liner']['stations']; Dl = g['D_L'] * 1e-3; A_L = K['A_L']
    # ---------------------------------------------------------------------------------------------- 6. impingement sleeve
    dP_imp = K['DPF']['impingement'] * P_in; rho_c = rho(P_in * 0.99, T_in)
    U_j = math.sqrt(2 * dP_imp / rho_c); A_imp = K['m_dil'] / (0.80 * rho_c * U_j)
    D_s = (g['D_L'] + 2 * g['t_L'] + 2 * g['g_inner']) * 1e-3
    A_sl = math.pi * D_s * g['L_pz'] * 1e-3
    d_j = g['imp_d'] * 1e-3; n_imp = int(round(A_imp / (math.pi / 4 * d_j ** 2)))
    xd = math.sqrt(A_sl / n_imp) / d_j
    Z = g['g_inner'] * 1e-3; zd = Z / d_j
    Re_j = rho_c * U_j * d_j / mu_air(T_in); Pr = 0.70
    Nu1 = 0.363 * Re_j ** 0.727 * Pr ** (1 / 3) * xd ** -0.554 * xd ** -0.422 * zd ** 0.068
    h_j = Nu1 * k_air(T_in) / d_j; G_j = rho_c * U_j * 0.80
    # gap crossflow pressure loss (spent air running down to the dilution holes)
    A_gap = math.pi * (D_s - Z) * Z; G_cmax = K['m_dil'] / A_gap
    Re_g = G_cmax * 2 * Z / mu_air(T_in + 20); dP_gap = 0.316 * Re_g ** -0.25 * g['L_pz'] * 1e-3 / (2 * Z) * G_cmax ** 2 / (2 * rho_c) / 3
    dP_dil = K['DPF']['premixer'] * P_in - dP_imp - dP_gap
    # ---------------------------------------------------------------------------------------------- 7. liner wall temperatures
    rows = []; T_c = T_in; m_pz = K['m_pm'] + mf
    q_fa = mf / K['m_pm']
    n_st = 18; z_pz = np.linspace(ls['z_dome'] - 10, ls['z_pz0'] + 10, n_st)
    for z in z_pz:
        s = (ls['z_dome'] - z) / g['L_pz']                                     # 0 dome .. 1 dilution end
        Gc = G_cmax * s
        deg = 1 - 0.596 * xd ** -0.103 * xd ** -0.380 * zd ** 0.803 * (Gc / G_j) ** 0.561 if Gc > 0 else 1.0
        h_imp = h_j * max(0.30, deg)
        h_ch = 1.3 * 0.023 * (max(Gc, 1.0) * 2 * Z / mu_air(T_c)) ** 0.8 * Pr ** 0.4 * k_air(T_c) / (2 * Z)
        h_c = max(h_imp, h_ch)
        F = 2.0 if s < 0.6 * g['D_L'] / g['L_pz'] else 1.5                       # flame / recirculation zone near the dome
        Tw1, Tm, Tw2, q = lefebvre_wall(K['T_ad'], q_fa, P_in * 0.968, Dl, m_pz, A_L, F, h_c, T_c, T_c + 20, 0.5,
                                        g['tbc'] * 1e-3, g['t_L'] * 1e-3)
        rows.append(dict(zone='PZ', z=z, Tg=K['T_ad'], h_c=h_c, Tc=T_c, T_tbc=Tw1, T_metal=Tm, T_cold=Tw2, q_kW=q / 1e3))
        T_c += q * math.pi * Dl * g['L_pz'] * 1e-3 / n_st / (K['m_dil'] * cp_air(T_c))
    T_dil = T_c
    # DZ: outer annulus (all the can air, circumferential ribs) + radiation to the casing
    A_dz = math.pi / 4 * ((g['D_case'] * 1e-3) ** 2 - (Dl + 2 * g['t_L'] * 1e-3) ** 2); Dh_dz = g['D_case'] * 1e-3 - Dl
    G_dz = m / A_dz; h_dz = 2.2 * 0.023 * (G_dz * Dh_dz / mu_air(T_in)) ** 0.8 * Pr ** 0.4 * k_air(T_in) / Dh_dz
    z_dz = np.linspace(ls['z_pz0'] - 80, ls['z_dz0'] + 10, 10)
    for z in z_dz:
        xi = (ls['z_pz0'] - 60 - z) / g['D_L']
        Tg = T_ex + (K['T_ad'] - T_ex) * 0.45 * math.exp(-max(xi, 0) / 0.35)
        Tw1, Tm, Tw2, q = lefebvre_wall(Tg, mf / m, P_in * 0.966, Dl, m_ex, A_L, 1.3, h_dz, T_in, T_in + 15, 0.55,
                                        g['tbc'] * 1e-3, g['t_L'] * 1e-3)
        rows.append(dict(zone='DZ', z=z, Tg=Tg, h_c=h_dz, Tc=T_in, T_tbc=Tw1, T_metal=Tm, T_cold=Tw2, q_kW=q / 1e3))
    T_max_metal = max(r['T_metal'] for r in rows); T_max_tbc = max(r['T_tbc'] for r in rows)
    Q_liner = sum(r['q_kW'] for r in rows if r['zone'] == 'PZ') * math.pi * Dl * g['L_pz'] * 1e-3 / n_st
    R['cooling'] = dict(impingement=dict(n_holes=n_imp, d_mm=g['imp_d'], x_over_d=xd, z_over_d=zd, U_jet=U_j, Re_j=Re_j, h_jet=h_j,
                                         dP_pct=100 * dP_imp / P_in, gap_dP_pct=100 * dP_gap / P_in, Gc_over_Gj_max=G_cmax / G_j),
                        dz=dict(h=h_dz, V_annulus=G_dz / rho_c), T_dilution_air_K=T_dil, Q_liner_PZ_kW=Q_liner, wall=rows,
                        T_metal_max_C=T_max_metal - 273.15, T_tbc_max_C=T_max_tbc - 273.15)
    check('liner metal temperature max (Hastelloy X, under 0.4 mm TBC)', T_max_metal - 273.15, 870.0, T_max_metal - 273.15 <= 870.0, 'C')
    check('TBC surface temperature max (YSZ)', T_max_tbc - 273.15, 1150.0, T_max_tbc - 273.15 <= 1150.0, 'C')
    # ---------------------------------------------------------------------------------------------- 8. dilution holes, pattern factor
    rho_d = rho(P_in * 0.985, T_dil); Cd = 0.62
    U_d = math.sqrt(2 * dP_dil / rho_d); A_dil = K['m_dil'] / (Cd * rho_d * U_d)
    n1, n2 = g['n_dil']; a1 = A_dil * 2 / 3 / n1; a2 = A_dil / 3 / n2
    d1 = math.sqrt(4 * a1 / math.pi); d2 = math.sqrt(4 * a2 / math.pi)
    rho_pz = rho(P_in * 0.968, K['T_ad']); U_g = (K['m_pm'] + mf) / (rho_pz * A_L)
    J = rho_d * U_d ** 2 / (rho_pz * U_g ** 2)
    Y1 = 1.15 * math.sqrt(Cd) * d1 * J ** 0.5; Y2 = 1.15 * math.sqrt(Cd) * d2 * J ** 0.5
    A_ref = math.pi / 4 * (g['D_case'] * 1e-3) ** 2; q_ref = m ** 2 / (2 * rho(P_in, T_in) * A_ref ** 2)
    LD = (g['L_pz'] + g['L_dz']) / g['D_L']
    PF_liner = 1 - math.exp(-1.0 / (0.070 * LD * (K['DPF']['premixer'] * P_in / q_ref)))
    # scroll mixing: path half a branch on average, hydraulic diameter of the mean section
    Dh_s = 0.20; L_path = math.pi * R['scroll']['r_c_mm'] * 1e-3 / 2
    PF_ngv = PF_liner * math.exp(-0.10 * L_path / Dh_s)
    RTDF = 0.5 * PF_ngv
    T_hot = T_ex + PF_ngv * (T_ex - T_in)
    R['dilution'] = dict(dP_pct=100 * dP_dil / P_in, A_m2=A_dil, rows=[dict(n=n1, d_mm=d1 * 1e3, Y_max_mm=Y1 * 1e3), dict(n=n2, d_mm=d2 * 1e3, Y_max_mm=Y2 * 1e3)],
                         J=J, U_jet=U_d, q_ref_Pa=q_ref, dPL_over_qref=K['DPF']['premixer'] * P_in / q_ref, L_over_D=LD)
    R['pattern'] = dict(PF_liner_exit=PF_liner, PF_ngv1=PF_ngv, RTDF_ngv1=RTDF, T_max_ngv1_C=T_hot - 273.15)
    check('dilution jet penetration, large row (Y_max / R_liner)', Y1 / (Dl / 2), 0.8, 0.8 <= Y1 / (Dl / 2) <= 1.4, '-')
    check('pattern factor at NGV1 (hot streak <= 1000 C)', PF_ngv, 0.15, PF_ngv <= 0.15, '-')
    # ---------------------------------------------------------------------------------------------- 9. scroll uniformity, swirl, heat loss
    q_s = 0.5 * K['rho_g'] * g['V_s'] ** 2
    dp_var = K['dp']['scroll friction'] + 0.3 * q_s                             # static-pressure spread top .. bottom
    dp_drive = 0.5 * K['rho_g'] * K['V_ngv'] ** 2 + K['dp']['deswirl vanes (22)'] + K['dp']['bend + NGV1 approach']
    dm = 0.5 * dp_var / dp_drive
    # deviation of the deswirl vanes (Carter): over-turned TE metal angle; residual swirl at NGV1 from +-3 deg off-design
    dev = 0.23 * K['alpha1'] / math.sqrt(K['sigma'])
    ct_te = R['pressure']['V']['vane_out'] * math.tan(math.radians(3.0))
    sw_ngv = math.degrees(math.atan(ct_te * g['r_vane_te'] / (0.5 * (I['r_hub'] + I['r_tip'])) / K['V_ngv']))
    # hot-gas casing walls: area, insulation (microporous 12 mm, k 0.030 W/mK at ~550 C mean) -> heat to the compressor air
    th = np.arange(5, 180, 10); dth = math.radians(10)
    A_body = 0.0
    for t in th:
        ro = r_out(t, K['Q_g']) * 1e-3; ri = g['r_body_in'] * 1e-3; w = (g['x_rear_s'] - g['x_front']) * 1e-3
        A_body += 2 * dth * (0.5 * (ro ** 2 - ri ** 2) * 2 + (ro + ri) * w)
    A_trans = 2 * math.pi * 0.5 * (g['r_vane_le'] + 300) * 1e-3 * 0.25 * 2
    A_neck = 2 * (0.29 + 0.39) * 0.32
    A_hot = A_body + A_trans + A_neck
    U = 1 / (1 / 150.0 + g['t_wall'] * 1e-3 / 22.0 + g['t_ins'] * 1e-3 / 0.030 + 1 / 40.0)
    Q_sc = U * A_hot * (T_ex - DPT['T2'])
    A_can = math.pi * (g['D_case'] + 2 * g['t_case']) * 1e-3 * (ls['z_top'] - g['z_base']) * 1e-3 + 2 * math.pi / 4 * 0.7 ** 2
    Q_can = A_can * (T_in - 313.0) / (0.10 / 0.07 + 1 / 8.0)
    r_ql = G.cycle(dict(M.CASE, q_loss=max(G.BASE['q_loss'], (Q_sc * 0.9 + Q_can) / DPT['Q_fuel'])), 'design_chilled')   # cycle has 0.5 %
    R['scroll'].update(mass_flow_spread_pct=100 * dm, vane_deviation_deg=dev, residual_swirl_ngv1_deg=sw_ngv, A_hot_m2=A_hot, U_W_m2K=U,
                       Q_loss_scroll_kW=Q_sc / 1e3, Q_loss_can_kW=Q_can / 1e3, T_rise_compressor_air_K=Q_sc / (DPT['ma'] * 1020.0),
                       eta_el_effect_pt=100 * (r_ql['eta_el'] - G.cycle(M.CASE, 'design_chilled')['eta_el']))
    check('NGV1 inlet mass-flow spread around the annulus', 100 * dm, 3.0, 100 * dm <= 3.0, '%')
    check('NGV1 inlet residual swirl (deswirl vanes 3 deg off)', sw_ngv, 3.0, abs(sw_ngv) <= 3.0, 'deg')
    check('heat loss scroll + can vs cycle allowance (0.5 % of fuel)', (Q_sc * 0.9 + Q_can) / DPT['Q_fuel'] * 100, 0.5,
          (Q_sc * 0.9 + Q_can) / DPT['Q_fuel'] <= 0.005, '% fuel')
    # ---------------------------------------------------------------------------------------------- 10. part load, staging, ignition
    tab = []
    T50, T100 = LOAD['50']['T_air'], LOAD['100']['T_air']
    for key in ('100', '90', '75', '50'):
        L = LOAD[key]; phi_all = L['phi_ov'] / SPLIT['premix']
        lbo_k = K['lbo']['50'] + (K['lbo']['100'] - K['lbo']['50']) * (L['T_air'] - T50) / (T100 - T50)
        opts = []
        for n in N_OPTIONS:
            phi_f = phi_all * N_PM / n
            if n == 7 and key in ('100', '90', '75', '50'):
                nox, co = emissions(CH, key, phi_f, K['tau_pz'] * 1e3, (K['tau_dz'] + K['tau_sc']) * 1e3, 0.06)
            else:
                st = [s for s in CH['staged'] if s['load'] == key and s['n_fuelled'] == n]
                if not st: continue
                ex = st[0]['exit']; t = (K['tau_dz'] + K['tau_sc']) * 1e3
                nox = _interp_log([e['t_ms'] for e in ex], [e['NOx'] for e in ex], t)
                co = _interp_log([e['t_ms'] for e in ex], [e['CO'] for e in ex], t)
            # fuel pressure: casing and NGV pressure fall with TIT at constant speed (turbine flow function)
            pr = L['P3'] / DPT['P3']; mfp = L['Q_fuel_kW'] * 1e3 / FUEL['LHV'] / n
            dPf = K['dP_f'] * (mfp / (mf / N_PM)) ** 2 / pr
            p_need = K['p_local'] * pr + dPf
            ok = (phi_f >= 1.15 * lbo_k) and (phi_f <= 0.62) and (nox < 25.0) and (co < 50.0) and (p_need <= K['p_supply'])
            opts.append(dict(n_fuelled=n, phi_f=phi_f, phi_lbo=lbo_k, NOx=nox, CO=co, fuel_dP_bar=dPf / 1e5,
                             fuel_margin_bar=(K['p_supply'] - p_need) / 1e5, ok=bool(ok)))
        sel = next((o for o in opts if o['ok']), None)
        tab.append(dict(load=key, load_frac=L['load'], P_net_kW=L['P_net_kW'], TIT_C=L['TIT'] - 273.15, T_air_C=L['T_air'] - 273.15,
                        phi_all=phi_all, options=opts, selected=sel['n_fuelled'] if sel else None))
        check('part load %s %%: a stage setting with NOx < 25, CO < 50, phi >= 1.15 phi_LBO' % key, sel['n_fuelled'] if sel else 0,
              'n = 7, 5 or 4', sel is not None, 'premixers')
    pil = [p for p in CH['pilot_diffusion'] if p['load'] == '50' and p['t_ms'] == 1.0][0]['EI_NOx_g_kg']
    # light-off: ~20 % speed, cold recuperator, diffusion tip in the pilot premixer at local phi ~ 1
    m_lo = 0.20 * DPT['ma']; m_pil_air = m_lo * SPLIT['premix'] / N_PM
    mf_lo = 1.0 * FUEL['f_st'] * m_pil_air * 1.5
    R['part_load'] = dict(table=tab, pilot_diffusion_EI_g_kg=pil, staging='circuits P (centre) + A (3) + B1 (1) + B2 (2); diffusion tip in P for light-off and < 45 % load',
                          light_off=dict(speed_frac=0.20, m_air=m_lo, m_fuel_g_s=mf_lo * 1e3, Q_fuel_kW=mf_lo * FUEL['LHV'] / 1e3,
                                         phi_overall=mf_lo / m_lo / FUEL['f_st'], U_pilot=m_pil_air / (rho(1.12e5, 313.0) * math.pi / 4 *
                                         ((K['D_o']) ** 2 - K['D_cb'] ** 2))))
    # ---------------------------------------------------------------------------------------------- 11. mechanical
    mech = {}
    p_g = 3.5e5                                                                   # design gauge pressure (station max 4 barg - 0.5)
    f_can = 40.0e6                                                                # 1.4948 at 640 C: R_u,100kh ~ 60 MPa / 1.5 (ASSUMPTION)
    t_can = p_g * g['D_case'] * 1e-3 / (2 * f_can * 0.85 - p_g)
    mech['can_casing'] = dict(material='1.4948 (X6CrNi18-10)', T_design_C=640, t_req_mm=t_can * 1e3, t_mm=g['t_case'],
                              sigma_hoop_MPa=p_g * g['D_case'] / 2 / g['t_case'] / 1e6)
    t_cov = g['D_case'] * 1e-3 * math.sqrt(0.30 * p_g / f_can)
    mech['head_cover'] = dict(t_req_mm=t_cov * 1e3, t_mm=g['t_cover'])
    E_hx = 150e9; tD = g['t_L'] / g['D_L']; Lr = 150.0 / g['D_L']
    p_cr = 2.42 * E_hx * tD ** 2.5 / ((1 - 0.3 ** 2) ** 0.75 * (Lr - 0.45 * tD ** 0.5))
    dp_L = K['DPF']['premixer'] * P_in
    mech['liner_buckling'] = dict(p_cr_MPa=p_cr / 1e6, dp_kPa=dp_L / 1e3, ratio=p_cr / dp_L, ring_pitch_mm=150.0)
    dp_sc = DPT['P2'] - (P_in - K['dp_tot'])                                       # compressor air outside - gas inside
    s_pan = 0.5 * dp_sc * (g['rib_pitch'] / g['t_wall']) ** 2
    s_mem = dp_sc * 0.55 / (g['t_wall'] * 1e-3)
    mech['scroll_wall'] = dict(material='Haynes 230 sheet (alt. cast 1.4852)', dp_kPa=dp_sc / 1e3, panel_bending_MPa=s_pan / 1e6,
                               membrane_MPa=s_mem / 1e6, allow_MPa_950C_100kh=3.0)
    f_mc = 170e6; R_mc = g['R_mc'] * 1e-3
    t_mc = p_g * 2 * R_mc / (2 * f_mc * 0.85 - p_g)
    F_split = p_g * 2 * R_mc * (g['x_mc1'] - g['x_mc0']) * 1e-3
    n_b = max(math.ceil(F_split / (0.5 * 640e6 * 245e-6 / 1.5) / 2) * 2, 2 * math.ceil((g['x_mc1'] - g['x_mc0']) / 100.0))   # strength / gasket pitch
    mech['mid_casing'] = dict(material='P355NH', t_req_mm=t_mc * 1e3, t_mm=g['t_mc'], sigma_hoop_MPa=p_g * R_mc / (g['t_mc'] * 1e-3) / 1e6,
                              split_force_kN=F_split / 1e3, split_bolts_M20_10_9=n_b)
    # thermal growth: scroll (Haynes 230 at ~945 C) vs NGV1 rings; neck / liner hula seal
    a230, a247, aHX, a48 = 16.6e-6, 14.6e-6, 16.0e-6, 18.6e-6
    d_scroll_ngv = I['r_tip'] * (a230 * 922 - a247 * 925) 
    up_neck = (g['z_neck1'] - 0) * a230 * 922 - g['z_mc'] * 0
    dz_case = (ls['z_top'] - g['z_base']) * a48 * 590
    dz_liner = (ls['z_dome'] - g['z_exit']) * aHX * 800
    travel = up_neck - (dz_case - dz_liner)
    cone_gap = g['z_exit'] + g['L_sleeve'] - g['z_neck1']
    mech['thermal'] = dict(cone_to_neck_cold_mm=cone_gap, cone_to_neck_hot_mm=cone_gap - travel, ngv1_interface_dr_mm=d_scroll_ngv, neck_top_rise_mm=up_neck, can_head_rise_mm=dz_case, liner_growth_mm=dz_liner,
                           hula_seal_overlap_change_mm=travel, hula_overlap_cold_mm=30.0, hula_overlap_hot_mm=30.0 + travel,
                           scroll_radial_growth_mm=R['scroll']['r_out_mm']['90'] * a230 * 922)
    R['mechanical'] = mech
    check('can casing wall >= required (1.4948 creep)', g['t_case'], t_can * 1e3, g['t_case'] >= t_can * 1e3, 'mm')
    check('head cover thickness >= required', g['t_cover'], t_cov * 1e3, g['t_cover'] >= t_cov * 1e3, 'mm')
    check('liner external-pressure buckling p_cr / dp (elastic, creep knock-down 10)', p_cr / dp_L, 10.0, p_cr / dp_L >= 10.0, '-')
    check('scroll wall panel bending at 950 C (rib pitch %d mm)' % g['rib_pitch'], s_pan / 1e6, 3.0, s_pan / 1e6 <= 3.0, 'MPa')
    check('mid-casing wall >= required', g['t_mc'], t_mc * 1e3, g['t_mc'] >= t_mc * 1e3, 'mm')
    check('hula seal stays engaged hot (overlap > 10 mm)', 30.0 + travel, 10.0, 30.0 + travel >= 10.0, 'mm')
    check('liner exit cone clears the neck top hot', cone_gap - travel, 5.0, cone_gap - travel >= 5.0, 'mm')
    return R, checks


def vane_angle(theta_deg, alpha1):
    """deswirl vane inlet metal angle vs scroll angle: +alpha1 on the +y branch, -alpha1 on the -y branch, 0 at the
    top splitter and at the bottom where the branches meet (linear ramps over 20 deg)"""
    t = theta_deg % 360.0; s = 1.0 if t <= 180.0 else -1.0; u = t if t <= 180.0 else 360.0 - t
    return s * alpha1 * min(1.0, u / 20.0, (180.0 - u) / 20.0)


def cad_geometry(R):
    K = R['_keep']; I = K['I']; ls = R['liner']['stations']
    hub, tip = meridional(I)
    n = GEO['n_vanes']
    return dict(GEO, interfaces={k: v for k, v in I.items() if not isinstance(v, dict)}, cas=I['cas'], barrel=I['barrel'],
                stations=ls, hub=hub, tip=tip, Q_g=K['Q_g'], r_out={str(t): r_out(t, K['Q_g']) for t in range(0, 181, 10)},
                premixer=dict(D_o=K['D_o'] * 1e3, D_cb=K['D_cb'] * 1e3, L_mt=R['premixer']['L_mt_mm']),
                dilution=R['dilution']['rows'], impingement=dict(n=R['cooling']['impingement']['n_holes'], d=GEO['imp_d']),
                vanes=[dict(theta=360.0 * k / n, alpha_in=vane_angle(360.0 * k / n, K['alpha1']),
                            dev=R['scroll']['vane_deviation_deg']) for k in range(n)])


def plot(R):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    CH = R['_keep']['CH']
    fig, ax = plt.subplots(2, 2, figsize=(12, 8.5), dpi=110)
    a = ax[0, 0]
    for key, c in (('100', 'C3'), ('75', 'C1'), ('50', 'C0')):
        fl = sorted([f for f in CH['flames'] if f['load'] == key], key=lambda f: f['phi'])
        ph = [f['phi'] for f in fl]
        a.semilogy(ph, [_interp_log(CH['t_pz_ms'], [p['NOx'] for p in f['pz']], R['liner']['tau_pz_ms']) for f in fl], c + '-',
                   label='NOx, air %.0f C (%s %%)' % (fl[0]['T_air'] - 273.15, key))
        a.semilogy(ph, [_interp_log(CH['t_dz_ms'], [p['CO'] for p in f['dz']], R['liner']['tau_dz_ms'] + R['liner']['tau_scroll_ms'])
                        if 'dz' in f else np.nan for f in fl], c + '--', label='CO at NGV1 (%s %%)' % key)
    a.axhline(25, color='k', lw=0.8); a.axvline(R['split']['phi_pz'], color='C3', lw=0.8, ls=':')
    a.text(0.31, 28, 'NOx limit 25 ppm', fontsize=8)
    a.set_xlabel('premixer equivalence ratio'); a.set_ylabel('ppmvd @ 15 % O2'); a.set_ylim(0.1, 1000); a.grid(alpha=0.3)
    a.legend(fontsize=7, ncol=2); a.set_title('Cantera GRI 3.0: flame + PZ %.0f ms + dilution' % R['liner']['tau_pz_ms'], fontsize=10)
    a = ax[0, 1]
    w = R['cooling']['wall']; z = [r['z'] for r in w]
    for k, lab, c in (('Tg', 'gas', 'C3'), ('T_tbc', 'TBC surface', 'C1'), ('T_metal', 'metal (hot side)', 'k'), ('Tc', 'coolant', 'C0')):
        a.plot([r[k] - 273.15 for r in w], z, c, marker='.', label=lab)
    a.axvline(870, color='k', lw=0.8, ls='--'); a.text(875, z[-1], 'Hastelloy X limit', fontsize=8, rotation=90)
    a.axhline(R['liner']['stations']['z_pz0'], color='grey', lw=0.6); a.text(620, R['liner']['stations']['z_pz0'] + 8, 'dilution holes', fontsize=8)
    a.set_xlabel('temperature [C]'); a.set_ylabel('height above the engine axis z [mm]'); a.grid(alpha=0.3); a.legend(fontsize=8)
    a.set_title('liner: impingement-cooled PZ, ribbed DZ, 0.4 mm TBC', fontsize=10)
    a = ax[1, 0]
    th = np.arange(0, 181, 5); Q = R['_keep']['Q_g']
    a.plot(th, [r_out(t, Q) for t in th], 'C3', label='scroll body outer radius (gas side)')
    a.axhline(GEO['r_body_in'], color='C0', label='body inner wall (over the outer casing)')
    a.axhline(GEO['r_vane_le'], color='C2', ls='--', label='deswirl vane LE / TE')
    a.axhline(GEO['r_vane_te'], color='C2', ls='--')
    a.axhline(GEO['R_mc'], color='k', ls=':', label='mid-casing radius (centre z +%d)' % GEO['z_mc'])
    a2 = a.twinx(); a2.plot(th, [vane_angle(t, R['_keep']['alpha1']) for t in th], 'C1', lw=0.8); a2.set_ylabel('vane inlet angle [deg]', color='C1')
    a.set_xlabel('scroll angle from the top [deg] (mirror for the other branch)'); a.set_ylabel('r [mm]'); a.grid(alpha=0.3); a.legend(fontsize=7, loc='lower left')
    a.set_title('two-branch scroll, V = %.0f m/s, 22 deswirl vanes' % GEO['V_s'], fontsize=10)
    a = ax[1, 1]
    tab = R['part_load']['table']
    for n, c in ((7, 'C3'), (5, 'C2'), (4, 'C0')):
        xs = [t['load_frac'] * 100 for t in tab for o in t['options'] if o['n_fuelled'] == n]
        a.plot(xs, [o['phi_f'] for t in tab for o in t['options'] if o['n_fuelled'] == n], c + 'o-', label='phi, %d premixers fuelled' % n)
    a.plot([t['load_frac'] * 100 for t in tab], [t['options'][0]['phi_lbo'] * 1.15 for t in tab], 'k--', label='1.15 x phi_LBO')
    a.axhline(0.62, color='grey', ls=':', label='phi max (NOx / flashback)')
    for t in tab:
        if t['selected']: a.annotate('n=%d' % t['selected'], (t['load_frac'] * 100, 0.30), fontsize=8, ha='center')
    a.set_xlabel('electric load [%]'); a.set_ylabel('equivalence ratio in the fuelled premixers'); a.grid(alpha=0.3); a.legend(fontsize=7)
    a.set_title('part load at constant speed: staging P + A + B1 + B2', fontsize=10)
    fig.suptitle('AURORA-1000 combustion system rev 1 (sim/engine/a1000_combustor.py)', fontsize=11)
    fig.tight_layout(); fig.savefig(IMG); plt.close(fig)


def main():
    R, checks = design()
    R, checks = design2(R, checks)
    geo = cad_geometry(R)
    plot(R)
    out = {k: v for k, v in R.items() if k != '_keep'}
    out['rev'] = 1
    out['checks'] = checks
    out['geometry'] = geo
    json.dump(out, open(OUT_JSON, 'w'), indent=1, default=float)
    sp = R['split']; pr = R['pressure']; pm = R['premixer']
    print('design point: can air %.3f kg/s at %.0f C / %.3f bar, fuel %.4f kg/s (%.0f Sm3/h), phi overall %.3f' % (
        DPT['m_can'], DPT['T_in'] - 273.15, DPT['P_in'] / 1e5, DPT['m_fuel'], DPT['gas_Sm3_h'], DPT['phi_ov']))
    print('split: premix %.1f %% -> phi %.3f, T_ad %.0f K (mix %.0f K); dilution %.1f %%' % (100 * SPLIT['premix'], sp['phi_pz'], sp['T_ad_K'],
                                                                                         sp['T_mix_K'], 100 * SPLIT['dilution']))
    print('pressure loss %.2f %% of %.2f %% (eta_el %+.2f pt):' % (pr['total_pct'], pr['budget_pct'], pr['eta_el_effect_pt']))
    for k, v in pr['items_pct'].items(): print('   %-28s %5.2f %%' % (k, v))
    print('premixers %d x D %.0f / %.0f mm, U %.0f m/s, S %.2f, tau %.2f ms; fuel %d x %.2f mm, dP %.2f bar, J %.1f, margin %.2f bar' % (
        pm['n'], pm['D_o_mm'], pm['D_cb_mm'], pm['U_ex'], pm['swirl_number'], pm['tau_res_ms'], pm['fuel']['holes'], pm['fuel']['d_mm'],
        pm['fuel']['dP_bar'], pm['fuel']['J'], pm['fuel']['margin_bar']))
    for k, v in R['flashback'].items():
        print('   flashback %-20s phi %.2f SL %.2f m/s  BL margin %5.0f  core margin %4.1f' % (k, v['phi'], v['SL'], v['bl_margin'], v['core_margin']))
    for k, v in R['autoignition'].items():
        print('   auto-ignition %-18s air %.0f K  tau %.3f s  ratio %6.0f (GRI/10: %4.0f)' % (k, v['T_air'], v['tau_ign_s'], v['ratio'], v['ratio_gri_x10']))
    L = R['liner']; print('liner D %d, PZ %d (%.1f ms), DZ %d (%.1f ms), scroll %.1f ms; LBO phi %.3f (margin %.2f)' % (
        L['D_L'], L['L_pz'], L['tau_pz_ms'], L['L_dz'], L['tau_dz_ms'], L['tau_scroll_ms'], R['lbo']['phi_lbo_100'], R['lbo']['margin_100']))
    for k, v in R['emissions_100'].items(): print('   100 %% %-14s NOx %5.2f  CO %6.2f ppm @15 %% O2' % (k, v['NOx'], v['CO']))
    c = R['cooling']; print('cooling: %d impingement holes d %.0f (x/d %.1f, z/d %.1f, %.0f m/s), liner metal max %.0f C, TBC %.0f C, liner heat %.0f kW' % (
        c['impingement']['n_holes'], c['impingement']['d_mm'], c['impingement']['x_over_d'], c['impingement']['z_over_d'], c['impingement']['U_jet'],
        c['T_metal_max_C'], c['T_tbc_max_C'], c['Q_liner_PZ_kW']))
    d = R['dilution']; print('dilution dP %.2f %%: %s; J %.0f; PF liner %.3f -> NGV1 %.3f (T max %.0f C), RTDF %.3f' % (
        d['dP_pct'], ', '.join('%d x d%.0f (Y %.0f mm)' % (r['n'], r['d_mm'], r['Y_max_mm']) for r in d['rows']), d['J'],
        R['pattern']['PF_liner_exit'], R['pattern']['PF_ngv1'], R['pattern']['T_max_ngv1_C'], R['pattern']['RTDF_ngv1']))
    s = R['scroll']; print('scroll: Q %.2f m3/s, r_out top %.0f / side %.0f / bottom %.0f; vanes alpha_in %.0f deg, DF %.2f, sigma %.2f, chord %.0f;'
                           ' spread %.1f %%, swirl %.1f deg; heat loss %.1f + %.1f kW (%+.2f pt)' % (
        s['Q_m3s'], s['r_out_mm']['0'], s['r_out_mm']['90'], s['r_out_mm']['180'], s['alpha_vane_in_deg'], s['DF'], s['sigma'], s['chord_mm'],
        s['mass_flow_spread_pct'], s['residual_swirl_ngv1_deg'], s['Q_loss_scroll_kW'], s['Q_loss_can_kW'], s['eta_el_effect_pt']))
    for t in R['part_load']['table']:
        print('   load %3.0f %% (TIT %.0f, air %.0f C): ' % (100 * t['load_frac'], t['TIT_C'], t['T_air_C']) +
              ' | '.join('n %d phi %.2f (LBO %.2f) NOx %.1f CO %.0f %s' % (o['n_fuelled'], o['phi_f'], o['phi_lbo'], o['NOx'], o['CO'], 'ok' if o['ok'] else '--')
                         for o in t['options']))
    for k, v in R['mechanical'].items(): print('   %-16s %s' % (k, {a: (round(b, 2) if isinstance(b, float) else b) for a, b in v.items()}))
    n_ok = sum(c['ok'] for c in checks)
    print('checks %d / %d pass' % (n_ok, len(checks)))
    for c in checks:
        if not c['ok']: print('   FAIL %-70s %s (limit %s)' % (c['name'], round(c['value'], 3) if isinstance(c['value'], float) else c['value'], c['limit']))
    print('wrote', OUT_JSON, IMG)


if __name__ == '__main__':
    main()
