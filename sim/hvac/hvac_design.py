# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP facility / HVAC sizing for the Borazjan rooftop plant.

Takes the engine/chiller numbers straight from sim/cchp_study.py and sim/roof_site_study.py (same model as
docs/03 sections 2-A, 8 and 9) and sizes the water side around them:
  1. exhaust/water HX (helical-finned 316L tube bank, Briggs-Young / Robinson-Briggs), diverter + stack
  2. absorption chiller pair (SC10 + SC5 class) at Borazjan conditions, wet-bulb sensitivity
  3. cooling tower (Merkel), evaporation, blowdown, RO-blend make-up
  4. pipe sizes, pump heads and power, expansion vessels, insulation
  5. hall fan coils, electrical-room cooler
  6. electrical load of every HVAC item, corrected net power
Results are printed and written to sim/hvac/hvac_results.json (read by the docs in docs/hvac/).
Catalogue values marked APPROX must be replaced by the supplier's datasheet before ordering.
Run:  python3 sim/hvac/hvac_design.py
"""
import json
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cchp_study as C          # noqa: E402
import life_study as L          # noqa: E402
import gas_props as GP          # noqa: E402
import roof_site_study as RS    # noqa: E402

# ----------------------------------------------------------------------------------------------- site
ALT = 70.0                                                  # Borazjan, m
P_ATM = 101.325 * (1 - 2.25577e-5 * ALT) ** 5.25588         # kPa
DB_SUMMER = 46.0                                            # summer design dry bulb (docs/03 sec 9)
WB_TOWER = 28.0                                             # cooling-tower design wet bulb (docs/03 sec 8, ASSUMED)
WB_RECIRC = 0.5                                             # rooftop plume-recirculation allowance on the tower inlet
CW_SUPPLY = 32.0                                            # cooling water to the chillers (docs/03 sec 8)
DER = 0.92                                                  # chiller derate at 32 C cooling water (roof_site_study)
CPW = 4.19                                                  # kJ/kg K
CP_GAS = C.CP_LOW / 1e3                                     # replaced below DESIGN by the real mean cp over the HX-1 range
HOURS_YEAR = 8000.0                                         # 24/7 with maintenance stops (docs/03 sec 4)
SUMMER_FRACTION = 0.70                                      # cooling season Apr-Nov
EC_PER_TDS = 1 / 0.65                                       # uS/cm per ppm TDS (typical 0.55-0.75 ppm per uS/cm)

# ----------------------------------------------------------------------------------- psychrometrics
def p_ws(T):                                                # kPa, same Magnus fit as roof_site_study
    return 0.61094 * math.exp(17.625 * T / (T + 243.04))

def w_sat(T, P=P_ATM):
    p = p_ws(T)
    return 0.622 * p / (P - p)

def h_air(T, w):                                            # kJ/kg dry air
    return 1.006 * T + w * (2501 + 1.86 * T)

def h_sat(T, P=P_ATM):
    return h_air(T, w_sat(T, P))

def w_from_wb(Tdb, Twb, P=P_ATM):
    ws = w_sat(Twb, P)
    return ((2501 - 2.326 * Twb) * ws - 1.006 * (Tdb - Twb)) / (2501 + 1.86 * Tdb - 4.186 * Twb)

def w_from_rh(T, rh, P=P_ATM):
    p = rh * p_ws(T)
    return 0.622 * p / (P - p)

def dew_point(w, P=P_ATM):
    pv = w * P / (0.622 + w)
    a = math.log(pv / 0.61094)
    return 243.04 * a / (17.625 - a)

def t_sat_from_h(h, P=P_ATM):
    lo, hi = -10.0, 80.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if h_sat(mid, P) < h else (lo, mid)
    return 0.5 * (lo + hi)

# ------------------------------------------------------------------------------------ water, gas
def rho_w(T):
    return 1000 * (1 - (T + 288.9414) / (508929.2 * (T + 68.12963)) * (T - 3.9863) ** 2)

def mu_w(T):
    return 2.414e-5 * 10 ** (247.8 / (T + 273.15 - 140))

def k_w(T):
    return 0.5706 + 0.001756 * T - 6.46e-6 * T * T

def gas_props(T_C):                                         # lean NG exhaust ~ air
    Tk = T_C + 273.15
    mu = 1.716e-5 * (Tk / 273.15) ** 1.5 * (273.15 + 110.4) / (Tk + 110.4)
    k = 0.0241 * (Tk / 273.15) ** 0.81
    rho = P_ATM * 1e3 / (287.0 * Tk)
    return mu, k, rho, 0.70

def m3h(m_kgs, T):
    return m_kgs / rho_w(T) * 3600

# ------------------------------------------------------------------------------ engine design data
C.CHILLER['Q_heat_max'] = 75.3e3                            # SC10 + SC5 class (roof_site_study)

def engine_case(T_in, TIT=800, N=115e3):
    c = C.cchp(N, TIT, 'target', T_in=T_in)
    r = c['r']
    mg = r['ma'] + r['mf']
    T_ex = r['T_stack_in'] - 273.15
    coil = RS.inlet_coil_kW(r['ma'], RS.OUT['T'], RS.OUT['w'], T_in) if T_in < RS.OUT['T'] else 0.0
    P = c['P_net'] - (0.35e3 if T_in < RS.OUT['T'] else 0)
    exh = GP.exhaust(r['far'])                              # as-built engine: real cp(T) (docs/08_design_point_update.md)
    return dict(T_in=T_in, TIT=TIT, N=N, ma=r['ma'], mf=r['mf'], mg=mg, T_ex=T_ex,
                cp_gas=exh.cp_mean(T_ex + 273.15, 373.15) / 1e3,
                Q_gas=mg * (exh.h(T_ex + 273.15) - exh.h(373.15)) / 1e3, Q_hw=c['Q_hw'] / 1e3, Q_cool=c['Q_cool'] * DER / 1e3,
                coil=coil, P_net=P / 1e3, F=c['F'] / 1e3, P_aux_engine=r['P_aux'] / 1e3, P_shaft=r['P_shaft'] / 1e3)

DESIGN = engine_case(15.0)                                  # summer design: intake chilled to 15 C
CP_GAS = DESIGN['cp_gas']                                   # 1.037 kJ/kg K real (constant-cp model had 1.080)
CASES = {'design 15C intake': DESIGN, 'spec nominal 22C': engine_case(22.0),
         'no intake coil 46C': engine_case(46.0), 'peak 815C, 15C intake': engine_case(15.0, 815)}

# ---------------------------------------------------------------------------------- 1. exhaust HX
HXG = dict(do=0.0254, tw=0.00165, hf=0.0110, tf=0.0008, nf=197.0,      # 1" 316L tube, solid helical 316L fins 5 fpi
           St=0.056, Sl=0.0485, k=16.5, rho=7950.0)                    # staggered pitches
R_FOUL_GAS, R_FOUL_W = 0.0005, 0.0001                                  # m2K/W (NG exhaust / treated closed loop)
HW_SUPPLY, HW_RETURN = 90.0, 83.0

def fin_geom(g):
    do, hf, tf, nf = g['do'], g['hf'], g['tf'], g['nf']
    Df = do + 2 * hf
    Af = nf * (2 * math.pi / 4 * (Df ** 2 - do ** 2) + math.pi * Df * tf)   # m2 per m of tube
    Ab = math.pi * do * (1 - nf * tf)
    di = do - 2 * g['tw']
    return dict(Df=Df, Af=Af, Ab=Ab, Ao=Af + Ab, Ai=math.pi * di, di=di, s=1 / nf - tf,
                proj=do + 2 * hf * tf * nf, Sd=math.hypot(g['St'] / 2, g['Sl']))

def hx_rate(g, Nt, Lt, Nr, mg, Tg_in, mw, Tw_in, ua_factor=1.0):
    """Rating of the finned bank as a multi-pass cross-counterflow HX (Nr passes ~ counterflow)."""
    f = fin_geom(g)
    A_min = Nt * Lt * min(g['St'] - f['proj'], 2 * (f['Sd'] - f['proj']))
    G = mg / A_min
    Tg_out, Tw_out = 100.0, Tw_in + 7.0
    for _ in range(4):
        Tgm = 0.5 * (Tg_in + Tg_out)
        mu, kg, rho_g, Pr = gas_props(Tgm)
        Re = G * g['do'] / mu
        Nu = 0.134 * Re ** 0.681 * Pr ** (1 / 3) * (f['s'] / g['hf']) ** 0.2 * (f['s'] / g['tf']) ** 0.1134
        ho = Nu * kg / g['do']
        m = math.sqrt(2 * ho / (g['k'] * g['tf']))
        ro, re = g['do'] / 2, f['Df'] / 2 + g['tf'] / 2
        phi = (re / ro - 1) * (1 + 0.35 * math.log(re / ro))
        eta_f = math.tanh(m * ro * phi) / (m * ro * phi)
        eta_o = 1 - f['Af'] / f['Ao'] * (1 - eta_f)
        Twm = 0.5 * (Tw_in + Tw_out)
        A_flow = Nt * math.pi / 4 * f['di'] ** 2
        v_w = mw / rho_w(Twm) / A_flow
        Re_w = rho_w(Twm) * v_w * f['di'] / mu_w(Twm)
        Pr_w = mu_w(Twm) * CPW * 1e3 / k_w(Twm)
        fw = (0.79 * math.log(Re_w) - 1.64) ** -2
        Nu_w = fw / 8 * (Re_w - 1000) * Pr_w / (1 + 12.7 * math.sqrt(fw / 8) * (Pr_w ** (2 / 3) - 1))
        hi = Nu_w * k_w(Twm) / f['di']
        R_m = (1 / (eta_o * ho * f['Ao']) + R_FOUL_GAS / (eta_o * f['Ao'])
               + math.log(g['do'] / f['di']) / (2 * math.pi * g['k']) + R_FOUL_W / f['Ai'] + 1 / (hi * f['Ai']))
        L_tot = Nt * Lt * Nr
        UA = L_tot / R_m * ua_factor
        Cg, Cw = mg * CP_GAS * 1e3, mw * CPW * 1e3
        Cmin, Cmax = min(Cg, Cw), max(Cg, Cw)
        Cr, NTU = Cmin / Cmax, UA / Cmin
        eps = (1 - math.exp(-NTU * (1 - Cr))) / (1 - Cr * math.exp(-NTU * (1 - Cr)))
        Q = eps * Cmin * (Tg_in - Tw_in)
        Tg_out, Tw_out = Tg_in - Q / Cg, Tw_in + Q / Cw
    rho_in, rho_out = gas_props(Tg_in)[2], gas_props(Tg_out)[2]
    f_rb = 18.93 * Re ** -0.316 * (g['St'] / g['do']) ** -0.927 * (g['St'] / f['Sd']) ** 0.515
    dp_g = Nr * f_rb * G ** 2 / (2 * rho_g) + G ** 2 * (1 / rho_out - 1 / rho_in)
    dp_w = Nr * (fw * Lt / f['di'] + 1.0) * rho_w(Twm) * v_w ** 2 / 2 + 1.5 * rho_w(Twm) * v_w ** 2 / 2
    t_wall_cold = Tw_in + (Tg_out - Tw_in) * (R_FOUL_W / f['Ai'] + 1 / (hi * f['Ai'])) / R_m * 1.5
    return dict(Q=Q / 1e3, Tg_out=Tg_out, Tw_out=Tw_out, UA=UA, U_o=1 / (R_m * f['Ao']), A_o=L_tot * f['Ao'],
                ho=ho, hi=hi, eta_f=eta_f, eta_o=eta_o, G=G, Re=Re, v_w=v_w, dp_g=dp_g, dp_w=dp_w / 1e3,
                A_min=A_min, L_tot=L_tot, t_wall_cold=t_wall_cold)

def hx_mass(g, L_tot, Nt, Lt, Nr):
    f = fin_geom(g)
    tube = math.pi * (g['do'] - g['tw']) * g['tw'] * g['rho']
    fins = g['nf'] * math.pi / 4 * (f['Df'] ** 2 - g['do'] ** 2) * g['tf'] * g['rho']
    core = L_tot * (tube + fins)
    W, H, D = Nt * g['St'], Lt, Nr * g['Sl'] + 0.10
    casing = 2 * (W * D + H * D) * 0.003 * g['rho'] + 2 * (W + H) * 0.15 * 0.003 * g['rho'] * 2   # 3 mm 316L box
    headers = 0.25 * core
    water = L_tot * math.pi / 4 * f['di'] ** 2 * 1.3 * 1000
    insul = 2 * (W * D + H * D + W * H) * 0.10 * 120                # 100 mm mineral wool + cladding
    return dict(core=core, dry=core + casing + headers + insul, water=water,
                op=core + casing + headers + insul + water, W=W, H=H, D=D)

TOWER_KEEP = 60            # ton class of rev B, kept after the engine update for the same reasons as HX-1
HX1_KEEP = (8, 0.60, 15)   # tubes/row, tube length m, rows: rev B geometry (sized for 69 kW at the old 262 C exhaust), kept after
                           # the engine update (docs/08): with the as-built 219 C exhaust it reaches ~92 C gas exit and it can carry the fuel boost (sec. 14b)

def design_hx(fixed=None):
    mw = DESIGN['Q_gas'] / (CPW * (HW_SUPPLY - HW_RETURN))
    if fixed:
        Nt, Lt, Nr = fixed
        r = hx_rate(HXG, Nt, Lt, Nr, DESIGN['mg'], DESIGN['T_ex'], mw, HW_RETURN, ua_factor=0.9)
        return dict(Nt=Nt, Lt=Lt, Nr=Nr, mw=mw, design=r, mass=hx_mass(HXG, r['L_tot'], Nt, Lt, Nr))
    best = None
    for Nt in range(5, 15):
        for Lt in (0.5, 0.6, 0.7, 0.8):
            for Nr in range(4, 40):
                r = hx_rate(HXG, Nt, Lt, Nr, DESIGN['mg'], DESIGN['T_ex'], mw, HW_RETURN, ua_factor=0.9)
                if r['Tg_out'] <= 100.0:
                    break
            else:
                continue
            mass = hx_mass(HXG, r['L_tot'], Nt, Lt, Nr)
            if r['dp_g'] > 450 or not 0.6 <= r['v_w'] <= 1.2 or mass['D'] > 0.85:
                continue                                     # gas dp, water velocity, core depth <= 0.85 m
            if best is None or mass['dry'] < best[4] - 1e-9:
                best = (Nt, Lt, Nr, r, mass['dry'])
    Nt, Lt, Nr, r, _ = best
    return dict(Nt=Nt, Lt=Lt, Nr=Nr, mw=mw, design=r, mass=hx_mass(HXG, r['L_tot'], Nt, Lt, Nr))

def exhaust_system(hx):
    """Diverter + duct + stack pressure drop (HX path and bypass path), stack sizing."""
    D_stack = 0.250                                          # DN250 316L, double wall
    A = math.pi / 4 * D_stack ** 2
    out = {}
    for name, c in CASES.items():
        mg, Tin = c['mg'], c['T_ex']
        r = hx_rate(HXG, hx['Nt'], hx['Lt'], hx['Nr'], mg, Tin, hx['mw'], HW_RETURN)
        rho_h, rho_c = gas_props(Tin)[2], gas_props(r['Tg_out'])[2]
        q_h = 0.5 * rho_h * (mg / rho_h / A) ** 2
        q_c = 0.5 * rho_c * (mg / rho_c / A) ** 2
        A_face = hx['Nt'] * HXG['St'] * hx['Lt']
        q_face_h = 0.5 * rho_h * (mg / rho_h / A_face) ** 2
        K_sil = 1.0                                          # SL-101 absorptive silencer in the common stack
        dp_hx_path = (0.8 * q_h + 0.6 * q_face_h * 2 + r['dp_g'] + (0.02 * 5 / D_stack + 1.0 + K_sil) * q_c)
        dp_bypass = 0.8 * q_h + 1.2 * q_h + (0.02 * 6 / D_stack + 1.0 + K_sil) * q_h
        out[name] = dict(T_in=Tin, mg=mg, Q_gas_to_water=r['Q'], Tg_out=r['Tg_out'], Tw_out=r['Tw_out'],
                         dp_core=r['dp_g'], dp_hx_path=dp_hx_path, dp_bypass=dp_bypass,
                         dp_pct=dp_hx_path / (P_ATM * 10), v_stack=mg / rho_c / A, v_stack_bypass=mg / rho_h / A)
    return out

def dew_points(c):
    """Water and sulphuric-acid dew points of the exhaust (Verhoff-Banchero), two fuel-sulphur levels."""
    m_h2o = c['mf'] * 36 / 16 + c['ma'] * RS.w_sat(15.0)
    x_h2o = (m_h2o / 18) / (c['mg'] / 28.9)
    Td_w = dew_point(0.622 * x_h2o / (1 - x_h2o) * 1.0, P_ATM)
    res = dict(x_h2o=x_h2o, Td_water=Td_w)
    Nm3_fuel = c['mf'] / 0.717
    Nm3_exh = c['mg'] / 1.293
    for S_mg in (20.0, 200.0):                                # mg S per Nm3 gas (odorised pipeline / upset)
        so2_ppm = Nm3_fuel * S_mg * 1e-3 / 32 * 22.414e-3 / Nm3_exh * 1e6 * 1e-3 * 1e3
        so3_ppm = 0.03 * so2_ppm
        p_h2o = x_h2o * P_ATM * 7.50062                       # mmHg
        p_so3 = so3_ppm * 1e-6 * P_ATM * 7.50062
        inv = 2.276 - 0.0294 * math.log(p_h2o) - 0.0858 * math.log(p_so3) + 0.0062 * math.log(p_h2o) * math.log(p_so3)
        res['S%.0f' % S_mg] = dict(SO2_ppm=so2_ppm, SO3_ppm=so3_ppm, T_acid=1000 / inv - 273.15)
    return res

# --------------------------------------------------------------------------------- 2. chillers
CHILLERS = {   # APPROX catalogue values (Yazaki WFC-SC brochure class) - replace with the supplier datasheet
    'CH-1': dict(model='WFC-SC10 class', Qc=35.2, Qh=50.2, hw=2.40, chw=1.52, cw=5.10,
                 dp_hw=90.0, dp_chw=57.0, dp_cw=84.0, el=0.21, dims=(0.76, 0.97, 1.90), dry=455, op=560),
    'CH-2': dict(model='WFC-SC5 class', Qc=17.6, Qh=25.1, hw=1.20, chw=0.77, cw=2.55,
                 dp_hw=90.0, dp_chw=56.0, dp_cw=47.0, el=0.05, dims=(0.594, 0.744, 1.756), dry=365, op=420),
}

# Equipment package. 'A' = first issue (catalogue dp, 40 t tower at full fan, balancing valves throttling the ECM pumps).
# 'B' = low-aux selection (recommended): purchase-spec dp caps on the chillers, ECM/VFD flow setting instead of balancing
# valves, oversize strainers and low-loss checks, larger tower with low-head (gravity / low-pressure) distribution and EC
# fan sized for the design at 60 % fan speed, low-dp FCU coils and PICVs, CW flow trimmed to 85 % of rated (maker approval).
PKG = {
    'A': dict(label='rev A (first issue)', ch_dp=None, strainer=10, check=6, balance=8, tower_static=40, fcu_dp=30,
              picv_dp=25, dp_sp=65, tower_fan_speed=1.0, cw_frac=1.0, ro_kW=0.30, coil_dp=40, hx4=False),
    'B': dict(label='rev B low-aux (recommended)', ch_dp=dict(hw=50.0, chw=40.0, cw=50.0), strainer=5, check=4, balance=0,
              tower_static=25, fcu_dp=20, picv_dp=20, dp_sp=50, tower_fan_speed=0.60, cw_frac=0.85, ro_kW=0.15, coil_dp=30,
              hx4=True),
}
REV = 'B'                                                   # design basis of this issue
CW_MIN, CW_MAX_PART = 26.0, 33.0                            # crystallisation floor; CW ceiling for one part-loaded chiller

def ch_dp(tag, key, pkg):
    v = CHILLERS[tag]['dp_' + key]
    cap = PKG[pkg]['ch_dp']
    return min(v, cap[key]) if cap else v

def chiller_pair(Q_heat_avail, T_hw_in, T_cw_in):
    """Heat-limited LiBr pair. COP law anchored to docs/03 (0.70 x 0.92 at 32 C cooling water)."""
    Qmax = 75.3 * (1 + 0.033 * (T_hw_in - 88.0)) * (1 - 0.06 * (T_cw_in - 31.0))
    Q_in = min(Q_heat_avail, Qmax)
    cop = 0.70 * (1 - 0.08 * (T_cw_in - 31.0))
    return dict(Q_in=Q_in, Q_cool=Q_in * cop, cop=cop, Qmax=Qmax, surplus=Q_heat_avail - Q_in)

def hw_hydraulics(Q):
    m1 = DESIGN['Q_gas'] / (CPW * 7.0)                       # primary (P-1) mass flow, fixed
    m2 = sum(c['hw'] for c in CHILLERS.values()) * rho_w(85) / 1e3
    T_ret = HW_SUPPLY - Q / (CPW * m1)
    T_ch_in = (m1 * HW_SUPPLY + (m2 - m1) * T_ret) / m2 if m2 > m1 else HW_SUPPLY
    return dict(m1=m1, m2=m2, V1=m3h(m1, 87), V2=m3h(m2, 87), T_ret=T_ret, T_ch_in=T_ch_in, dT_ch=Q / (CPW * m2))

# ------------------------------------------------------------------------------ 3. cooling tower
TOWER_RATING = dict(Th=37.0, Tc=32.0, WB=27.0, LG=1.2, L_per_ton=0.78)  # Taiwanese FRP round-tower basis, APPROX
TOWER_SIZES = {  # nominal ton: (fan kW, diameter m, height m, operating kg) APPROX (Liang Chi LBC class)
    30: (0.75, 1.40, 1.90, 450), 40: (1.1, 1.60, 1.95, 600), 50: (1.5, 1.88, 2.00, 760), 60: (1.5, 1.88, 2.10, 820),
    70: (2.2, 2.20, 2.15, 950), 80: (2.2, 2.20, 2.25, 1050), 100: (2.2, 2.40, 2.35, 1250), 125: (3.7, 2.80, 2.45, 1550)}

def merkel(Tc, Th, WB, LG, n=40):
    h_in = h_sat(WB)
    def f(T):
        d = h_sat(T) - (h_in + LG * CPW * (T - Tc))
        return CPW / d if d > 0 else float('inf')
    hstep = (Th - Tc) / n
    s = f(Tc) + f(Th) + sum((4 if i % 2 else 2) * f(Tc + i * hstep) for i in range(1, n))
    return s * hstep / 3

NTU_RATED = merkel(TOWER_RATING['Tc'], TOWER_RATING['Th'], TOWER_RATING['WB'], TOWER_RATING['LG'])

def tower_cold_water(S, L_kgs, Q_kW, WB, fan=1.0):
    Lr = S * TOWER_RATING['L_per_ton'] * 995 / 3600
    G = Lr / TOWER_RATING['LG'] * fan                       # air flow proportional to fan speed
    LG = L_kgs / G
    ntu_av = NTU_RATED * (LG / TOWER_RATING['LG']) ** -0.6
    rng = Q_kW / (L_kgs * CPW)
    lo, hi = WB + 0.3, WB + 20.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if merkel(mid, mid + rng, WB, LG) > ntu_av else (lo, mid)
    Tc = 0.5 * (lo + hi)
    return dict(S=S, G=G, LG=LG, ntu=ntu_av, Tc=Tc, Th=Tc + rng, rng=rng, approach=Tc - WB)

def evaporation(G, LG, rng, WB, Tdb=DB_SUMMER):
    h_in = h_sat(WB)
    h_out = h_in + LG * CPW * rng
    T_out = t_sat_from_h(h_out)
    return G * (w_sat(T_out) - w_from_wb(Tdb, WB)) * 3600, T_out

# ------------------------------------------------------------------------------- 4. hydraulics
DN_ID = {15: 15.8, 20: 20.9, 25: 26.6, 32: 35.1, 40: 40.9, 50: 52.5, 65: 62.7, 80: 77.9, 100: 102.3, 125: 128.2}
DN_OD = {15: 21.3, 20: 26.7, 25: 33.4, 32: 42.2, 40: 48.3, 50: 60.3, 65: 73.0, 80: 88.9, 100: 114.3, 125: 141.3}
R_MAX = 250.0                                               # Pa/m, 24/7 operation -> generous pipes

def pipe_R(Q_m3h, DN, T, eps=4.5e-5):
    D = DN_ID[DN] / 1e3
    v = Q_m3h / 3600 / (math.pi / 4 * D * D)
    Re = rho_w(T) * v * D / mu_w(T)
    f = 0.25 / math.log10(eps / (3.7 * D) + 5.74 / Re ** 0.9) ** 2
    return v, f / D * rho_w(T) * v * v / 2

def size_pipe(Q_m3h, T):
    for DN in DN_ID:
        v, R = pipe_R(Q_m3h, DN, T)
        if R <= R_MAX and v <= (1.2 if DN <= 50 else 1.8):
            return DN, v, R
    raise ValueError(Q_m3h)

def eta_ww(P_hyd_W):                                        # wire-to-water, ECM/IE4 + VFD small pumps
    return max(0.25, min(0.60, 0.25 + 0.08 * math.log(max(P_hyd_W, 10) / 10)))

# ------------------------------------------------------------------------------- 5. fan coils
FCU_CLASSES = {  # CFM: (nominal total kW at 27/19 C, water 7/12 C; fan W high speed AC / EC) APPROX
    400: (3.9, 65, 35), 600: (5.9, 95, 50), 800: (7.6, 130, 65), 1000: (9.4, 160, 80), 1200: (11.2, 190, 95)}

def fcu_factor(T_ea, w_ea, T_w_mean=9.5):
    h_ref = h_sat(T_w_mean + 2.0)
    return (h_air(T_ea, w_ea) - h_ref) / (h_sat(19.0) - h_ref)

def insul_thk(OD_mm, T_f, T_a, RH, k, h_s, need_dp=True, P=P_ATM):
    Td = dew_point(w_from_rh(T_a, RH, P), P)
    for t in (9, 13, 19, 25, 32, 40, 50, 60, 75):
        r1, r2 = OD_mm / 2000, OD_mm / 2000 + t / 1000
        R = math.log(r2 / r1) / (2 * math.pi * k) + 1 / (h_s * 2 * math.pi * r2)
        q = (T_a - T_f) / R
        Ts = T_a - q / (h_s * 2 * math.pi * r2)
        if not need_dp or Ts >= Td + 1.0:
            return t, Ts, q, Td
    return None, Ts, q, Td

# ------------------------------------------------------------------- 6. engine glycol loop and oil cooler
def bearing_loss_W(n_rpm, dm_mm, nu_cSt=10.0, f0=4.0):
    """Palmgren speed-dependent friction of an oil-jet lubricated ball bearing: M0 = 1e-7 f0 (nu n)^2/3 dm^3 [N mm]."""
    M0 = 1e-7 * f0 * (nu_cSt * n_rpm) ** (2 / 3) * dm_mm ** 3
    return M0 / 1e3 * n_rpm * 2 * math.pi / 60

def glycol_loop(case):
    """Engine auxiliary loop (docs/electrical M-751, TE-GLY, DC-1): rectifier B3 -> PMG jacket -> oil cooler OC-1 -> DC-1
    (adiabatic pre-cooling pads) -> HX-4 trim when the tower runs. docs/electrical: TE-GLY ALM 58 / FSD 65 C; docs/06 section 2: PMG glycol 35-40 C target."""
    core = 2 * bearing_loss_W(115e3, 15.0)                  # 2 x 608 hybrid 8x22x7 (dm 15 mm), turbine oil ~10 cSt
    fpt = 334.0 + 338.0                                     # FPT/PMG bearings B1 + B2 (E3, docs/engine/E3_fpt_pmg.md), if they join
    soak, pump = 400.0, 50.0                                # turbine-side heat soak into the oil (estimate), M-710 pump
    oil_core = (core + soak + pump) / 1e3                   # confirmed: closed-loop pressurised oil on the core 608s
    oil_all = oil_core + fpt / 1e3
    oil_design = math.ceil(oil_core * 1.25 * 10) / 10       # OC-1 sized for the core system (+25 %)
    pmg = 0.844                                             # PMG jacket heat to glycol at the design point (E3 sec. 11-4)
    rect = case['P_shaft'] * L.ASBUILT['eta_gen'] * 0.015   # SiC active rectifier ~1.5 % of the PMG terminal power
    panels = 0.2                                            # air/water coolers of RP-1 / PEB (docs/electrical)
    Q_gly = pmg + rect + oil_core + panels
    Q_des = 4.0                                             # DC-1 design (FPT/PMG oil, 30 kW core later)
    m_g, cp_g = 15.0 / 60 * 1.03, 3.85                      # 30 % PG, 15 L/min
    # DC-1 coil sized dry for Q_des at 46 C air with glycol supply 55 C (UA fixed by this)
    T_sup_dry = 55.0
    T_ret_dry = T_sup_dry + Q_des / (m_g * cp_g)
    m_air = Q_des / (1.006 * 5.0)
    d1, d2 = T_ret_dry - (DB_SUMMER + 5.0), T_sup_dry - DB_SUMMER
    lm = (d1 - d2) / math.log(d1 / d2)
    UA = Q_des * 1e3 / lm
    # rating with the actual load: dry at 46 C, and with adiabatic pads (eff 0.75) at 46 C / WB 28 C

    def rate(Q, T_air):
        Cg, Ca = m_g * cp_g * 1e3, m_air * 1006.0
        Cmin, Cmax = min(Cg, Ca), max(Cg, Ca)
        Cr, NTU = Cmin / Cmax, UA / Cmin
        eps = (1 - math.exp(-NTU * (1 - Cr))) / (1 - Cr * math.exp(-NTU * (1 - Cr)))
        T_in_g = T_air + Q * 1e3 / (eps * Cmin)             # glycol into DC-1 for this duty
        return T_in_g - Q * 1e3 / Cg                        # glycol supply
    T_pad = DB_SUMMER - 0.75 * (DB_SUMMER - WB_TOWER)
    T_sup_dry_act = rate(Q_gly, DB_SUMMER)
    T_sup_pad = rate(Q_gly, T_pad)
    pad_water = m_air * 1.006 * (DB_SUMMER - T_pad) / 2420 * 3600   # L/h evaporated at the design hour
    V_air = m_air / 1.09 * 3600
    fan_W = m_air / 1.09 * 120.0 / 0.45                     # +pad pressure drop
    # oil cooler: oil 100 -> 70 C; glycol enters after B3 + PMG (pads in summer)
    T_g_oc = T_sup_pad + (rect + pmg + panels) / (m_g * cp_g)
    T_g_oc_out = T_g_oc + oil_design / (m_g * cp_g)
    lm_oc = ((100 - T_g_oc_out) - (70 - T_g_oc)) / math.log((100 - T_g_oc_out) / (70 - T_g_oc))
    m_oil = oil_design / (1.95 * 30.0)
    return dict(core_bearings=core / 1e3, fpt_bearings=fpt / 1e3, soak=soak / 1e3, oil_pump=pump / 1e3, oil_core=oil_core,
                oil_all=oil_all, oil_design=oil_design, oil_design_with_fpt=math.ceil(oil_all * 1.25 * 10) / 10,
                oil_flow_Lmin=m_oil / 0.85 * 60, pmg=pmg, rect=rect, panels=panels, Q_gly=Q_gly, Q_des=Q_des,
                glycol_Lmin=15.0, dc1_UA=UA, dc1_LMTD=lm, T_sup_dry=T_sup_dry_act, T_sup_pad=T_sup_pad, T_pad_air=T_pad,
                pad_water_Lh=pad_water, dc1_air_m3h=V_air, dc1_fan_W=fan_W, T_glycol_at_oc=T_g_oc, oc_LMTD=lm_oc,
                oc_UA=oil_design * 1e3 / lm_oc)

# --------------------------------------------------------------------------- 7. pumps per package
def build_pumps(rev, P, hx_dp_w, hy, V_sec, L_cw, V_hx4):
    k = PKG[rev]
    st, ck, bal = k['strainer'], k['check'], k['balance']
    return [  # tag, service, m3/h, T, items, control, static kPa (not scaled with flow)
        ('P-1A/B', 'HW primary through HX-1 (twin head)', hy['V1'], 87,
         [('pipe L-HW-01', P['L-HW-01']['dp']), ('HX-1 water side', hx_dp_w), ('LLH-1 + air/dirt separator', 8),
          ('strainer', st), ('check + isolation', ck), ('flow meter', 2)], 'duty/standby, ECM const. flow', 0.0),
        ('P-2A', 'HW secondary to CH-1', CHILLERS['CH-1']['hw'] * 3.6, 86,
         [('pipe L-HW-02/03', P['L-HW-02']['dp'] + P['L-HW-03']['dp']), ('CH-1 generator', ch_dp('CH-1', 'hw', rev)),
          ('strainer', st), ('check + isolation', ck), ('balancing valve', bal)], 'on with CH-1, ECM const. flow', 0.0),
        ('P-2B', 'HW secondary to CH-2', CHILLERS['CH-2']['hw'] * 3.6, 86,
         [('pipe L-HW-02/04', P['L-HW-02']['dp'] + P['L-HW-04']['dp']), ('CH-2 generator', ch_dp('CH-2', 'hw', rev)),
          ('strainer', st), ('check + isolation', ck), ('balancing valve', bal)], 'on with CH-2, ECM const. flow', 0.0),
        ('P-3', 'DHW / heating branch', P['L-HW-05']['Q'], 80,
         [('pipe L-HW-05', P['L-HW-05']['dp']), ('HX-2/HX-3 plate HX', 25), ('V-PRI 3-way', 15), ('strainer', st),
          ('check + isolation', ck)], 'on demand, ECM', 0.0),
        ('P-4A', 'CHW primary CH-1', CHILLERS['CH-1']['chw'] * 3.6, 10,
         [('pipe L-CH-01', P['L-CH-01']['dp']), ('CH-1 evaporator', ch_dp('CH-1', 'chw', rev)), ('strainer', st),
          ('check + isolation', ck), ('balancing valve', bal), ('MV-CH1E isolation', 3)], 'on with CH-1 + 15 min run-on', 0.0),
        ('P-4B', 'CHW primary CH-2', CHILLERS['CH-2']['chw'] * 3.6, 10,
         [('pipe L-CH-02', P['L-CH-02']['dp']), ('CH-2 evaporator', ch_dp('CH-2', 'chw', rev)), ('strainer', st),
          ('check + isolation', ck), ('balancing valve', bal), ('MV-CH2E isolation', 3)], 'on with CH-2 + 15 min run-on', 0.0),
        ('P-5A/B', 'CHW secondary distribution (twin head)', V_sec, 10,
         [('pipe L-CH-03', P['L-CH-03']['dp']), ('pipe index: hall L-CH-05/06/07 or elec room L-CH-08',
                                                 max(P['L-CH-05']['dp'] + P['L-CH-06']['dp'] + P['L-CH-07']['dp'], P['L-CH-08']['dp'])),
          ('FCU coil', k['fcu_dp']), ('PICV', k['picv_dp']), ('strainer', st), ('check + changeover valves', 8 + ck),
          ('air/dirt separator', 3)], 'duty/standby, ECM dp-control', 0.0),
        ('P-6A/B', 'condenser water (tower)', L_cw / 0.995 * 3.6 * k['cw_frac'] + (V_hx4 if k['hx4'] else 0.0), 34,
         [('pipe L-CW-01/02', (P['L-CW-01']['dp'] + P['L-CW-02']['dp']) * k['cw_frac'] ** 2),
          ('CH-1 absorber+condenser', ch_dp('CH-1', 'cw', rev) * k['cw_frac'] ** 2),   # rated-flow dp scaled to trimmed flow
          ('basket strainer', st), ('check + isolation', ck), ('balancing valve (CH-2 branch)', max(bal, 5) * k['cw_frac'] ** 2),
          ('tower static lift + distribution', k['tower_static'])], 'duty/standby, VFD on flow set-point',
         k['tower_static'] * 1.10),
    ]

def pump_kW(Q, H_kPa):
    if Q <= 0:
        return 0.0
    Ph = Q / 3600 * H_kPa * 1e3
    return Ph / eta_ww(Ph) / 1e3

# ----------------------------------------------------------------------- 8. operating modes (power priority)
MODE_SPEC = {   # chillers, CW flow fraction (None = package), tower fan rule, hall rule, intake-coil set-point
    'MAX-COOLING': dict(ch=('CH-1', 'CH-2'), cw=1.0, fan='max', hall='first', T1=15.0, defer=False),
    'BALANCED':    dict(ch=('CH-1', 'CH-2'), cw=None, fan='hold', hall='rest', T1=15.0, defer=False),
    'MAX-POWER':   dict(ch=('CH-1',), cw=None, fan='hold', hall='rest', T1=15.0, defer=True),
    'MAX-POWER T1=12C': dict(ch=('CH-1',), cw=None, fan='hold', hall='rest', T1=12.0, defer=True),   # EMS merit step 4
    'MAX-POWER-HALL-OFF': dict(ch=('CH-1',), cw=None, fan='min', hall='off', T1=15.0, defer=True),     # Q_HALL_MAX_PCT = 0
    'NO-COOLING':  dict(ch=(), cw=0.0, fan='off', hall='off', T1=None, defer=True),
}
ALT_SPEC = {     # single SC10-class chiller option (CH-2 not installed)
    'SINGLE BALANCED':    dict(ch=('CH-1',), cw=None, fan='hold', hall='rest', T1=15.0, defer=False),
    'SINGLE MAX-COOLING': dict(ch=('CH-1',), cw=1.0, fan='max', hall='rest', T1=15.0, defer=False),
    'BALANCED COLD-CW':   dict(ch=('CH-1', 'CH-2'), cw=1.0, fan='max', hall='rest', T1=15.0, defer=False),  # heat-limited: buy COP
}
ER_LOAD = 2.5
HALL_DEMAND = None                                          # set in main (insulated roof, design hour)

def coil_kW(T_sp, ma):
    return RS.inlet_coil_kW(ma, RS.OUT['T'], RS.OUT['w'], T_sp) if T_sp < RS.OUT['T'] else 0.0

def plant_solve(active, Q_hw_avail, demand, cw_frac, fan, ctx):
    """Chillers + LLH mixing + tower, iterated: returns cooling actually produced and the loop temperatures."""
    m1 = ctx['m1']
    m2 = sum(CHILLERS[t]['hw'] for t in active) * rho_w(85) / 1e3
    L_ch = sum(CHILLERS[t]['cw'] for t in active) * 0.995 * cw_frac
    L = L_ch + ctx['L_hx4']
    el = sum(CHILLERS[t]['el'] for t in active)
    Tc, Q_in, cool = CW_SUPPLY, 0.6 * Q_hw_avail, 0.0
    for _ in range(40):
        T_ret = HW_SUPPLY - Q_in / (CPW * m1)
        T_ch_in = (m1 * HW_SUPPLY + (m2 - m1) * T_ret) / m2 if m2 > m1 else HW_SUPPLY
        rng_ch = (Q_in + cool + el) / (L_ch * CPW)
        T_eff = Tc + 0.5 * (rng_ch - ctx['rng_ref'])        # range penalty of a trimmed CW flow
        cop = 0.70 * (1 - 0.08 * (T_eff - 31.0))
        Qmax = sum(CHILLERS[t]['Qh'] for t in active) * (1 + 0.033 * (T_ch_in - 88.0)) * (1 - 0.06 * (T_eff - 31.0))
        cap = min(Q_hw_avail, Qmax) * cop
        cool = min(cap, demand)
        Q_in = cool / cop
        Q_rej = Q_in + cool + el + ctx['Q_hx4']
        Tc_new = max(tower_cold_water(ctx['S'], L, Q_rej, WB_TOWER + WB_RECIRC, fan)['Tc'], CW_MIN)
        if abs(Tc_new - Tc) < 1e-4:
            Tc = Tc_new
            break
        Tc = 0.5 * (Tc + Tc_new)
    return dict(cool=cool, cap=cap, Q_in=Q_in, cop=cop, Tc=Tc, T_ch_in=T_ch_in, Q_rej=Q_rej, L=L, L_ch=L_ch,
                rng=rng_ch, surplus=Q_hw_avail - Q_in)

def boosted(case, ctx):
    """Extra hot-water heat Q_hw_add (kW) bought with fuel at eta_add (heat-shortfall options, section 16)."""
    q = ctx.get('Q_hw_add', 0.0)
    return dict(case, Q_hw=case['Q_hw'] + q, F=case['F'] + q / ctx.get('eta_add', 0.90)) if q else case

def run_mode(mode, ctx):
    sp = MODE_SPEC[mode] if mode in MODE_SPEC else ALT_SPEC[mode]
    pk = PKG[ctx['rev']]
    active = sp['ch']
    cw = pk['cw_frac'] if sp['cw'] is None else sp['cw']
    hall_dem = HALL_DEMAND
    if not active:
        case = boosted(engine_case(46.0, ctx.get('TIT', 800), ctx.get('N', 115e3)), ctx)
        res = dict(cool=0.0, cap=0.0, Q_in=0.0, cop=0.0, Tc=float('nan'), Q_rej=0.0, L=0.0, rng=0.0, surplus=case['Q_hw'])
        T1, fan, coil, hall = 46.0, 0.0, 0.0, 0.0
    else:
        T1 = sp['T1']
        for _ in range(8):
            case = boosted(engine_case(T1, ctx.get('TIT', 800), ctx.get('N', 115e3)), ctx)
            coil = coil_kW(T1, case['ma'])
            demand = coil + ER_LOAD + (0.0 if sp['hall'] == 'off' else hall_dem)
            prio = coil + ER_LOAD                               # intake coil and electrical room come first

            def solve(f):
                return plant_solve(active, case['Q_hw'], demand, cw, f, ctx)
            if sp['fan'] == 'max':
                fan = 1.0
            else:
                target = CW_SUPPLY if sp['fan'] == 'hold' else CW_MAX_PART
                lo, hi = 0.25, 1.0
                if solve(lo)['Tc'] <= target and (sp['fan'] == 'hold' or solve(lo)['cool'] >= prio - 1e-6):
                    hi = lo
                for _ in range(30):
                    if hi - lo < 1e-3:
                        break
                    mid = 0.5 * (lo + hi)
                    r_ = solve(mid)
                    ok = r_['Tc'] <= target and (sp['fan'] == 'hold' or r_['cool'] >= prio - 1e-6)
                    lo, hi = (lo, mid) if ok else (mid, hi)
                fan = hi
            res = solve(fan)
            if sp['hall'] == 'first':                       # comfort first: the coil takes what is left
                left = res['cool'] - ER_LOAD - hall_dem
                if left >= coil - 1e-6 or T1 >= 45.9:
                    break
                lo_t, hi_t = T1, 45.9
                for _ in range(40):
                    mid = 0.5 * (lo_t + hi_t)
                    lo_t, hi_t = (mid, hi_t) if coil_kW(mid, case['ma']) > max(left, 0.0) else (lo_t, mid)
                if abs(hi_t - T1) < 0.02:
                    break
                T1 = hi_t
            else:
                break
        hall = 0.0 if sp['hall'] == 'off' else max(0.0, min(hall_dem, res['cool'] - coil - ER_LOAD))
    # tower water use (evaporation: latent-only estimate .. saturated-exit bound at this fan speed)
    if active:
        tw = tower_cold_water(ctx['S'], res['L'], res['Q_rej'], WB_TOWER + WB_RECIRC, fan)
        E_lo = res['Q_rej'] / (2501 - 2.36 * 34) * 3600
        E_hi = evaporation(tw['G'], tw['LG'], tw['rng'], WB_TOWER)[0]
    else:
        E_lo = E_hi = 0.0
    # auxiliary power, itemised (plant side)
    P = ctx['pumps']
    a = {}
    a['P-1'] = pump_kW(P['P-1A/B']['Q'], P['P-1A/B']['H_kPa']) if active else pump_kW(P['P-1A/B']['Q'] * 0.4, P['P-1A/B']['H_kPa'] * 0.16)
    a['P-2A'] = P['P-2A']['kW'] if 'CH-1' in active else 0.0
    a['P-2B'] = P['P-2B']['kW'] if 'CH-2' in active else 0.0
    a['P-4A'] = P['P-4A']['kW'] if 'CH-1' in active else 0.0
    a['P-4B'] = P['P-4B']['kW'] if 'CH-2' in active else 0.0
    if active:
        q5 = (coil + ER_LOAD + hall) / (CPW * 5.0) * 3.6
        f5 = q5 / P['P-5A/B']['Q']
        a['P-5'] = pump_kW(q5, pk['dp_sp'] + (P['P-5A/B']['H_kPa'] - pk['dp_sp']) * f5 ** 2)
        q6 = res['L'] / 0.995 * 3.6
        st6 = P['P-6A/B']['static']
        a['P-6'] = pump_kW(q6, st6 + (P['P-6A/B']['H_kPa'] - st6) * (cw / ctx['cw_des']) ** 2)
        a['CT fan'] = ctx['fan_kW'] * fan ** 3
    else:
        a['P-5'] = a['P-6'] = a['CT fan'] = 0.0
    a['chillers'] = sum(CHILLERS[t]['el'] for t in active)
    a['RO-1 + P-9'] = 0.0 if sp['defer'] else pk['ro_kW'] + 0.04    # P-9 lifts ~0.35 m3/h by ~12 m in bursts
    a['DHW P-3/P-7'] = 0.02 + (0.0 if sp['defer'] else 0.03)
    a['WT-1, F-SS, D-101, BOP-R'] = (0.05 + 0.005 if active else 0.0) + 0.01 + 0.08
    a['elec room'] = (0.04 if active else 1.30) + 0.03     # FCU-E (or AC-E DX when no chilled water) + EF-E
    aux = sum(a.values())
    bldg_fans = (0.18 * hall / hall_dem + (0.15 if sp['hall'] != 'off' else 0.05)) if hall_dem else 0.0
    P_eng = case['P_net'] + C.AUX_CCHP / 1e3                # engine before HVAC aux (keeps the 0.35 kW coil air-side loss)
    net = P_eng - aux
    eq = net + hall / C.COP_SPLIT - bldg_fans
    unmet = hall_dem - hall
    return dict(mode=mode, chillers=list(active), T1=T1, fan=fan, cw_frac=cw if active else 0.0, Tc=res['Tc'],
                Q_hw=case['Q_hw'], Q_in=res['Q_in'], surplus=res['surplus'], cop=res['cop'], cool=res['cool'], coil=coil,
                er=ER_LOAD, hall=hall, hall_unmet=unmet, P_eng=P_eng, aux=aux, aux_items=a, net=net, bldg_fans=bldg_fans,
                el_equiv=eq, el_equiv_split=eq - unmet / C.COP_SPLIT, F=case['F'], eta_el=net / case['F'],
                E_lo=E_lo, E_hi=E_hi, makeup=0.5 * (E_lo + E_hi) * 3.5 / 2.5,
                eta_useful=(net + res['Q_in'] + 0.0) / case['F'])

# ------------------------------------------------------------------- 9. clean-agent fire suppression
FK_K1, FK_K2 = 0.0664, 0.0002741                            # FK-5-1-12 specific vapour volume S = k1 + k2 T (m3/kg)

def fk_mass(V, C_pct, T_min):
    """NFPA 2001 / ISO 14520 total flooding: W = V/S * C/(100-C)."""
    return V / (FK_K1 + FK_K2 * T_min) * C_pct / (100.0 - C_pct)

def fk_conc(W, V, T):
    x = W * (FK_K1 + FK_K2 * T) / V
    return 100.0 * x / (1.0 + x)

# ----------------------------------------------------------------------------------- main
def main():
    out = {'site': dict(alt=ALT, P_atm=P_ATM, DB=DB_SUMMER, WB_tower=WB_TOWER, CW_supply=CW_SUPPLY)}
    print('=' * 100)
    print('GR180-CCHP facility/HVAC sizing - Borazjan rooftop (P_atm %.2f kPa)' % P_ATM)
    print('=' * 100)
    print('\n[0] ENGINE CASES (from sim/cchp_study.py + roof_site_study.py, 115k rpm, target parts)')
    print('  %-24s %6s %7s %7s %7s %7s %7s %6s' % ('case', 'mg', 'T_ex', 'Q_gas', 'Q_hw', 'Q_cool', 'coil', 'P_net'))
    for k, c in CASES.items():
        print('  %-24s %6.3f %7.1f %7.1f %7.1f %7.1f %7.1f %6.1f' % (k, c['mg'], c['T_ex'], c['Q_gas'], c['Q_hw'],
              c['Q_cool'], c['coil'], c['P_net']))
    out['cases'] = CASES

    # ---------------------------------------------------------------- HX
    hx_min = design_hx()                                    # smallest bank that meets the 100 C basis (for reference)
    hx = design_hx(fixed=HX1_KEEP)
    r, m = hx['design'], hx['mass']
    ex = exhaust_system(hx)
    dpt = dew_points(DESIGN)
    print('\n[1] EXHAUST/WATER HX  HX-1  (316L helical-finned tubes, counter-cross-flow, gas 1 pass, water %d passes)' % hx['Nr'])
    print('  duty (gas side) %.1f kW, water %.2f kg/s (%.1f m3/h) %.0f->%.0f C, gas %.0f->100 C (basis; kept rev B bank reaches %.0f C'
          ' with 10 %% UA margin; smallest bank for the basis would be %d x %d x %.2f m, %.0f kg dry)' % (
        DESIGN['Q_gas'], hx['mw'], m3h(hx['mw'], 87), HW_RETURN, HW_SUPPLY, DESIGN['T_ex'], r['Tg_out'], hx_min['Nt'], hx_min['Nr'],
        hx_min['Lt'], hx_min['mass']['dry']))
    lm = ((DESIGN['T_ex'] - HW_SUPPLY) - (100 - HW_RETURN)) / math.log((DESIGN['T_ex'] - HW_SUPPLY) / (100 - HW_RETURN))
    print('  LMTD (counterflow) %.1f K; required UA %.0f W/K (+10 %% margin)' % (lm, DESIGN['Q_gas'] * 1e3 / lm / 0.9))
    print('  geometry: %d tubes/row x %d rows, tube length %.2f m, OD %.1f mm x %.2f, fins %.0f/m x %.1f x %.1f mm' % (
        hx['Nt'], hx['Nr'], hx['Lt'], HXG['do'] * 1e3, HXG['tw'] * 1e3, HXG['nf'], HXG['hf'] * 1e3, HXG['tf'] * 1e3))
    print('  core W x H x D = %.2f x %.2f x %.2f m; finned area %.1f m2; total tube %.1f m' % (
        m['W'], m['H'], m['D'], r['A_o'], r['L_tot']))
    print('  h_gas %.1f W/m2K, fin eff %.2f, surface eff %.2f, h_water %.0f W/m2K (v %.2f m/s), U_o %.1f W/m2K' % (
        r['ho'], r['eta_f'], r['eta_o'], r['hi'], r['v_w'], r['U_o']))
    print('  gas dp core %.0f Pa; water dp %.1f kPa; mass core %.0f kg, dry %.0f kg, water %.0f L, operating %.0f kg' % (
        r['dp_g'], r['dp_w'], m['core'], m['dry'], m['water'], m['op']))
    print('  cold-end tube wall ~%.0f C; exhaust H2O %.1f %% -> water dew point %.0f C; acid dew point %.0f C (20 mgS/Nm3), %.0f C (200 mgS/Nm3)' % (
        r['t_wall_cold'], dpt['x_h2o'] * 100, dpt['Td_water'], dpt['S20']['T_acid'], dpt['S200']['T_acid']))
    print('  rating (clean, P-1 flow fixed, water in %.0f C):' % HW_RETURN)
    for k, e in ex.items():
        print('    %-24s gas %5.1f C %.3f kg/s -> %5.1f C | water out %5.1f C | %5.1f kW | dp core %3.0f Pa, HX path %3.0f Pa (%.2f %%), bypass %3.0f Pa | stack %4.1f/%4.1f m/s' % (
            k, e['T_in'], e['mg'], e['Tg_out'], e['Tw_out'], e['Q_gas_to_water'], e['dp_core'], e['dp_hx_path'],
            e['dp_pct'], e['dp_bypass'], e['v_stack'], e['v_stack_bypass']))
    print('  cycle model budget (concept_study): 1.5 %% CHP HX + 0.5 %% stack = %.0f Pa -> margin OK' % (0.02 * P_ATM * 1e3))
    out['hx'] = dict(Nt=hx['Nt'], Nr=hx['Nr'], Lt=hx['Lt'], mw=hx['mw'], V_m3h=m3h(hx['mw'], 87), LMTD=lm,
                     geom=HXG, design=r, mass=m, rating=ex, dew=dpt, Q_design=DESIGN['Q_gas'])

    # ---------------------------------------------------------------- chillers
    hy = hw_hydraulics(DESIGN['Q_hw'])
    ch = chiller_pair(DESIGN['Q_hw'], hy['T_ch_in'], CW_SUPPLY)
    print('\n[2] ABSORPTION CHILLERS CH-1 %s + CH-2 %s (single-effect LiBr, hot water)' % (
        CHILLERS['CH-1']['model'], CHILLERS['CH-2']['model']))
    print('  HW primary (P-1) %.1f m3/h %.0f/%.1f C -> low-loss header -> chiller secondary %.1f m3/h, chiller in %.1f C, dT %.1f K' % (
        hy['V1'], HW_SUPPLY, hy['T_ret'], hy['V2'], hy['T_ch_in'], hy['dT_ch']))
    print('  at Borazjan design (CW %.0f C): heat in %.1f kW (max %.1f), COP %.3f -> cooling %.1f kW (docs/03: 42.4)' % (
        CW_SUPPLY, ch['Q_in'], ch['Qmax'], ch['cop'], ch['Q_cool']))
    Q_rej = ch['Q_in'] + ch['Q_cool'] + sum(c['el'] for c in CHILLERS.values())
    print('  heat rejection to tower %.1f kW' % Q_rej)
    for t, c in CHILLERS.items():
        print('  %s %-15s %4.1f kW cool / %4.1f kW heat rated | HW %.2f L/s (%.2f m3/h) | CHW %.2f L/s (%.2f m3/h) | CW %.2f L/s (%.2f m3/h) | %.0f kg op' % (
            t, c['model'], c['Qc'], c['Qh'], c['hw'], c['hw'] * 3.6, c['chw'], c['chw'] * 3.6, c['cw'], c['cw'] * 3.6, c['op']))
    out['chillers'] = dict(units=CHILLERS, hw=hy, design=ch, Q_rej=Q_rej)

    # ---------------------------------------------------------------- tower
    L_cw = sum(c['cw'] for c in CHILLERS.values()) * 995 / 1e3
    gl = glycol_loop(DESIGN)
    pk = PKG[REV]
    V_hx4 = gl['Q_gly'] / (CPW * 3.0) / 0.995 * 3.6         # HX-4 trim of the engine glycol loop into the CW
    L_hx4 = V_hx4 / 3.6 * 0.995 if pk['hx4'] else 0.0
    Q_hx4 = gl['Q_gly'] if pk['hx4'] else 0.0

    def select_tower(L, Q, fan):
        for S_ in TOWER_SIZES:
            t_ = tower_cold_water(S_, L, Q, WB_TOWER + WB_RECIRC, fan)
            if t_['Tc'] <= CW_SUPPLY:
                return t_
    selA = select_tower(L_cw, Q_rej, 1.0)
    sel = select_tower(L_cw * pk['cw_frac'] + L_hx4, Q_rej + Q_hx4, pk['tower_fan_speed'])
    sel_rule = sel['S']
    if sel['S'] < TOWER_KEEP:
        sel = tower_cold_water(TOWER_KEEP, L_cw * pk['cw_frac'] + L_hx4, Q_rej + Q_hx4, WB_TOWER + WB_RECIRC, pk['tower_fan_speed'])
    print('\n[3] COOLING TOWER CT-1 (open, induced draft, FRP; %s)' % pk['label'])
    if sel_rule != sel['S']:
        print('  as-built engine: the rule alone gives %d ton; the %d ton class is KEPT (fuel-boost option 14b, wet-bulb margin,'
              ' unchanged plant model)' % (sel_rule, sel['S']))
    print('  rev A rule: Tc <= %.0f C at full fan, rated CW flow -> %d ton class; rev B rule: Tc <= %.0f C at %.0f %% fan,'
          ' %.0f %% CW flow + HX-4 -> %d ton class' % (CW_SUPPLY, selA['S'], CW_SUPPLY, pk['tower_fan_speed'] * 100,
                                                     pk['cw_frac'] * 100, sel['S']))
    print('  rating basis %.0f/%.0f/%.0f C, %.2f m3/h per nominal ton, L/G %.1f -> rated KaV/L %.3f' % (
        TOWER_RATING['Th'], TOWER_RATING['Tc'], TOWER_RATING['WB'], TOWER_RATING['L_per_ton'], TOWER_RATING['LG'], NTU_RATED))
    print('  duty %.1f kW (chillers %.1f + HX-4 %.1f), water %.1f m3/h, range %.2f K, design WB %.1f C (+%.1f recirculation)' % (
        Q_rej + Q_hx4, Q_rej, Q_hx4, (L_cw * pk['cw_frac'] + L_hx4) / 0.995 * 3.6, sel['rng'], WB_TOWER, WB_RECIRC))
    fan_kW, dia, hgt, op_kg = TOWER_SIZES[sel['S']]
    sel_full = tower_cold_water(sel['S'], L_cw * pk['cw_frac'] + L_hx4, Q_rej + Q_hx4, WB_TOWER + WB_RECIRC, 1.0)
    print('  SELECT nominal %d ton class (EC/VFD fan %.1f kW, low-head distribution): cold water %.2f C at %.0f %% fan'
          ' (%.2f C at full fan), approach %.2f K, ~D%.2f x %.2f m, ~%d kg op' % (
              sel['S'], fan_kW, sel['Tc'], pk['tower_fan_speed'] * 100, sel_full['Tc'], sel['approach'], dia, hgt, op_kg))
    wbsens = []
    print('  wet-bulb sensitivity (heat in %.1f kW, selected tower at full fan):' % DESIGN['Q_hw'])
    print('    %5s %7s %7s %7s %7s %7s %8s' % ('WB', 'CW in', 'COP', 'cool', 'coil15', 'bldg', 'surplus'))
    for wb in (24.0, 26.0, 27.0, 28.0, 29.0, 30.0):
        tw = tower_cold_water(sel['S'], L_cw * pk['cw_frac'] + L_hx4, Q_rej + Q_hx4, wb + WB_RECIRC, 1.0)
        Tcw = max(tw['Tc'], 26.0)
        cc = chiller_pair(DESIGN['Q_hw'], hy['T_ch_in'], Tcw)
        coil = RS.inlet_coil_kW(DESIGN['ma'], DB_SUMMER, w_from_wb(DB_SUMMER, wb), 15.0)
        wbsens.append(dict(WB=wb, Tcw=Tcw, cop=cc['cop'], cool=cc['Q_cool'], coil=coil, bldg=cc['Q_cool'] - coil,
                           surplus=cc['surplus']))
        print('    %5.1f %7.2f %7.3f %7.1f %7.1f %7.1f %8.1f' % (wb, Tcw, cc['cop'], cc['Q_cool'], coil, cc['Q_cool'] - coil,
                                                              cc['surplus']))
    E_max, T_air_out = evaporation(sel_full['G'], sel_full['LG'], sel_full['rng'], WB_TOWER)
    hfg = 2501 - 2.36 * 34
    E_nom = (Q_rej + Q_hx4) / hfg * 3600
    drift = L_cw * 3600 * 2e-5
    wb_rows = []
    print('  evaporation: %.0f L/h (heat/latent, docs/03 basis) .. %.0f L/h (Merkel, saturated exit %.1f C, 46 C dry inlet air)' % (
        E_nom, E_max, T_air_out))
    print('  drift (0.002 %%) %.1f L/h' % drift)
    print('    %6s %8s %9s %9s %10s %10s' % ('cycles', 'circ ppm', 'circ uS/cm', 'blowdown', 'make-up', 'make-up'))
    for cyc in (3.0, 3.5, 4.0):
        for E in (E_nom, E_max):
            B = E / (cyc - 1) - drift
            M = E + B + drift
            wb_rows.append(dict(cycles=cyc, E=E, B=B, M=M, tds=400 * cyc, ec=400 * cyc * EC_PER_TDS))
            print('    %6.1f %8.0f %9.0f %7.0f L/h %7.0f L/h %6.1f m3/d' % (cyc, 400 * cyc, 400 * cyc * EC_PER_TDS, B, M, M * 24 / 1e3))
    # RO blend to meet the chiller-maker (JRA GL-02) circulating limit 800 uS/cm
    ec_city, ec_ro, cyc_ro, rec = 400 * EC_PER_TDS, 20.0, 3.5, 0.60
    ec_blend = 800.0 / cyc_ro
    x_ro = (ec_city - ec_blend) / (ec_city - ec_ro)
    ro_rows = []
    for E in (E_nom, E_max):
        M = E * cyc_ro / (cyc_ro - 1)
        perm = x_ro * M
        feed = perm / rec
        ro_rows.append(dict(E=E, M=M, perm=perm, feed=feed, reject=feed - perm, city=(1 - x_ro) * M + feed))
    print('  RO-blend option (circ <= 800 uS/cm at %.1f cycles): make-up %.0f uS/cm, RO share %.0f %%, RO permeate %.0f..%.0f L/h,'
          ' city water %.0f..%.0f L/h' % (cyc_ro, ec_blend, x_ro * 100, ro_rows[0]['perm'], ro_rows[1]['perm'],
                                          ro_rows[0]['city'], ro_rows[1]['city']))
    lm4 = ((45 - 35.0) - (40 - 32.0)) / math.log((45 - 35.0) / (40 - 32.0))
    print('  HX-4 (optional trim of the engine glycol loop): %.1f kW, glycol 45->40 C, CW %.2f m3/h 32->35 C, LMTD %.1f K,'
          ' UA %.0f W/K' % (gl['Q_gly'], V_hx4, lm4, gl['Q_gly'] * 1e3 / lm4))
    out['tower'] = dict(sel=sel, sel_full=sel_full, selA=selA, fan_kW=fan_kW, fan_speed_design=pk['tower_fan_speed'],
                        hx4=dict(Q=gl['Q_gly'], V=V_hx4, LMTD=lm4, UA=gl['Q_gly'] * 1e3 / lm4, active=pk['hx4']),
                        Q_tot=Q_rej + Q_hx4, cw_frac=pk['cw_frac'],
                        dia=dia, height=hgt, op_kg=op_kg, L_kgs=L_cw, V_m3h=L_cw / 0.995 * 3.6,
                        Q_rej=Q_rej, wb_sens=wbsens, E_nom=E_nom, E_max=E_max, drift=drift, water=wb_rows,
                        ro=dict(ec_city=ec_city, ec_blend=ec_blend, x_ro=x_ro, cycles=cyc_ro, rows=ro_rows),
                        NTU_rated=NTU_RATED)

    # ---------------------------------------------------------------- loads on the chilled water
    hall_ins = RS.hall_load(True)[1]
    hall_unins = RS.hall_load(False)[1]
    coil_doc = DESIGN['coil']
    coil_28 = RS.inlet_coil_kW(DESIGN['ma'], DB_SUMMER, w_from_wb(DB_SUMMER, WB_TOWER), 15.0)
    elec_room = 2.5
    V_coil = coil_28 / (CPW * 5) / rho_w(10) * 3600
    V_hall = hall_ins / (CPW * 5) / rho_w(10) * 3600                  # roof insulated (user)
    V_er = 3.9 * 0.75 / (CPW * 5) / rho_w(10) * 3600
    V_sec = V_coil + V_hall + V_er
    V_pri = sum(c['chw'] for c in CHILLERS.values()) * 3.6
    cond_coil = DESIGN['ma'] * (w_from_wb(DB_SUMMER, WB_TOWER) - w_sat(15.0)) * 3600
    print('\n[4] CHILLED-WATER BUDGET 7/12 C: intake coil %.1f kW (docs basis) / %.1f kW (WB 28) | hall %.1f (ins.) / %.1f (unins.) |'
          ' elec room %.1f | chillers %.1f kW' % (coil_doc, coil_28, hall_ins, hall_unins, elec_room, ch['Q_cool']))
    print('  flows: primary (chiller rated) %.2f m3/h, secondary design %.2f m3/h (coil %.2f, hall %.2f, elec %.2f)' % (
        V_pri, V_sec, V_coil, V_hall, V_er))
    print('  intake-coil condensate %.1f L/h (to tower basin as low-TDS make-up)' % cond_coil)
    out['chw'] = dict(coil_doc=coil_doc, coil_28=coil_28, hall_ins=hall_ins, hall_unins=hall_unins, elec_room=elec_room,
                      V_coil=V_coil, V_hall=V_hall, V_er=V_er, V_sec=V_sec, V_pri=V_pri, cond_coil=cond_coil)

    # ---------------------------------------------------------------- pipes
    lines = [  # tag, service, m3/h, T, length one way (m), note
        ('L-HW-01', 'HW primary HX-1 <-> LLH-1', hy['V1'], 87, 6.0, 'steel A106 Sch40, mineral wool 50 mm + Al'),
        ('L-HW-02', 'HW header LLH-1 -> chillers', hy['V2'], 86, 2.0, ''),
        ('L-HW-03', 'HW CH-1 branch (P-2A)', CHILLERS['CH-1']['hw'] * 3.6, 86, 4.0, ''),
        ('L-HW-04', 'HW CH-2 branch (P-2B)', CHILLERS['CH-2']['hw'] * 3.6, 86, 4.0, ''),
        ('L-HW-05', 'DHW/heating branch (P-3) to indoor DHW tank', 30.0 / (CPW * 20) * 3.6, 80, 15.0, '30 kW at 90/70 C'),
        ('L-CH-01', 'CHW primary CH-1 <-> TK-1 (P-4A)', CHILLERS['CH-1']['chw'] * 3.6, 10, 5.0, 'steel Sch40, elastomeric + Al'),
        ('L-CH-02', 'CHW primary CH-2 <-> TK-1 (P-4B)', CHILLERS['CH-2']['chw'] * 3.6, 10, 5.0, ''),
        ('L-CH-03', 'CHW secondary TK-1 -> header (P-5)', V_sec, 10, 3.0, ''),
        ('L-CH-04', 'CHW intake coil CC-1 branch', V_coil, 10, 5.0, ''),
        ('L-CH-05', 'CHW hall main: roof 6 m + riser 3.5 m', V_hall, 10, 9.5, 'roof outdoor part + riser'),
        ('L-CH-06', 'CHW hall distribution, 2 FCUs', V_hall / 2, 10, 9.0, 'indoor, elastomeric'),
        ('L-CH-07', 'CHW hall distribution, last FCU', V_hall / 4, 10, 7.0, ''),
        ('L-CH-08', 'CHW electrical-room branch', V_er, 10, 30.0, 'route ~30 m (user)'),
        ('L-CW-01', 'CW tower <-> chiller header (P-6)', L_cw / 0.995 * 3.6, 34, 8.0, 'steel Sch40 galv./epoxy or PP-RCT'),
        ('L-CW-02', 'CW CH-1 branch', CHILLERS['CH-1']['cw'] * 3.6, 34, 3.0, ''),
        ('L-CW-03', 'CW CH-2 branch', CHILLERS['CH-2']['cw'] * 3.6, 34, 3.0, ''),
        ('L-CW-04', 'CW side-stream separator', 0.08 * L_cw / 0.995 * 3.6, 34, 3.0, '~8 % of circulation'),
        ('L-MU-01', 'tower make-up (RO blend) from indoor tank', 0.5, 25, 20.0, 'PP-R PN16, heat-traced on roof'),
    ]
    pipes = {}
    print('\n[5] LINE LIST (Sch40 ID; R <= %.0f Pa/m, v <= 1.2 m/s up to DN50 / 1.8 m/s above)' % R_MAX)
    for tag, svc, Q, T, L, note in lines:
        DN, v, R = size_pipe(Q, T)
        pipes[tag] = dict(service=svc, Q=Q, T=T, L=L, DN=DN, v=v, R=R, dp=R * 2 * L * 1.5 / 1e3, note=note,
                          vol=math.pi / 4 * (DN_ID[DN] / 1e3) ** 2 * 2 * L * 1e3)
        print('  %-8s %-45s %6.2f m3/h DN%-3d v %.2f m/s R %3.0f Pa/m, 2x%4.1f m -> %5.1f kPa (x1.5 fittings)' % (
            tag, svc, Q, DN, v, R, L, pipes[tag]['dp']))
    out['pipes'] = pipes

    # ---------------------------------------------------------------- pumps
    P = pipes
    pumps = build_pumps(REV, P, r['dp_w'], hy, V_sec, L_cw, V_hx4)
    pumpsA = build_pumps('A', P, r['dp_w'], hy, V_sec, L_cw, V_hx4)
    def pump_table(plist):
        po = {}
        for tag, svc, Q, T, items, ctl, static in plist:
            H_kPa = sum(v for _, v in items) * 1.10
            P_hyd = Q / 3600 * H_kPa * 1e3
            eta = eta_ww(P_hyd)
            po[tag] = dict(service=svc, Q=Q, H_kPa=H_kPa, H_m=H_kPa / (rho_w(T) * 9.81e-3), P_hyd=P_hyd, eta=eta,
                           kW=P_hyd / eta / 1e3, items=items, control=ctl, T=T, static=static)
        return po
    pump_out, pump_A = pump_table(pumps), pump_table(pumpsA)
    print('\n[6] PUMPS (%s; design flow, +10 %% head margin)' % pk['label'])
    for tag, p_ in pump_out.items():
        print('  %-7s %-40s %6.2f m3/h  H %5.1f kPa (%4.1f m)  P_hyd %4.0f W  eta_ww %.2f -> %.2f kW (rev A %.2f)  [%s]' % (
            tag, p_['service'], p_['Q'], p_['H_kPa'], p_['H_m'], p_['P_hyd'], p_['eta'], p_['kW'], pump_A[tag]['kW'], p_['control']))
        print('          ' + ', '.join('%s %.0f' % (n, v) for n, v in p_['items']) + ' kPa, +10 %')
    out['pumps'] = pump_out
    out['pumps_revA'] = pump_A
    # alternative: one constant-flow HW loop (no low-loss header) through HX-1 and both chiller generators
    V_single = hy['V2']
    r_single = hx_rate(HXG, hx['Nt'], hx['Lt'], hx['Nr'], DESIGN['mg'], DESIGN['T_ex'], hy['m2'], 83.0)
    H_single = (P['L-HW-01']['dp'] * (V_single / hy['V1']) ** 2 + r_single['dp_w'] + ch_dp('CH-1', 'hw', REV) + pk['strainer']
                + pk['check'] + pk['balance']) * 1.10
    Ph_single = V_single / 3600 * H_single * 1e3
    kW_single = Ph_single / eta_ww(Ph_single) / 1e3
    kW_ps = pump_out['P-1A/B']['kW'] + pump_out['P-2A']['kW'] + pump_out['P-2B']['kW']
    print('  alternative single HW loop: %.1f m3/h x %.0f kPa -> %.2f kW vs primary/secondary P-1+P-2A+P-2B %.2f kW' % (
        V_single, H_single, kW_single, kW_ps))
    out['hw_single_loop'] = dict(V=V_single, H_kPa=H_single, kW=kW_single, kW_primary_secondary=kW_ps)

    # ---------------------------------------------------------------- expansion
    def vessel(Vs, Tmax, p0, psv, name):
        e = rho_w(10) / rho_w(Tmax) - 1
        Ve = e * Vs
        Vwr = max(0.005 * Vs, 3.0)
        pe = psv - 0.5
        Vn = (Ve + Vwr) * (pe + 1) / (pe - p0)
        size = next(s for s in (8, 12, 18, 25, 35, 50, 80, 100, 140, 200) if s >= Vn * 1.1)
        return dict(name=name, Vs=Vs, Tmax=Tmax, e=e, Ve=Ve, Vwr=Vwr, p0=p0, pe=pe, psv=psv, Vn=Vn, size=size)
    V_hw = (m['water'] + 200 + 20 + 10 + 5 + sum(P[t]['vol'] for t in P if t.startswith('L-HW')))
    V_chw = (500 + 15 + 4 * 2.5 + 1.5 + 15 + 8 + 3 + sum(P[t]['vol'] for t in P if t.startswith('L-CH')))
    ets = [vessel(V_hw, 98.0, 1.0, 5.5, 'ET-1 hot water (with intermediate vessel, return 83 C > 70 C)'),
           vessel(V_chw, 50.0, 1.0, 5.5, 'ET-2 chilled water / winter heating')]
    print('\n[7] EXPANSION VESSELS (EN 12828)')
    for v in ets:
        print('  %-60s Vs %4.0f L, e %.4f, Ve %4.1f L, p0 %.1f bar, PSV %.1f bar -> Vn %4.1f L -> select %d L' % (
            v['name'], v['Vs'], v['e'], v['Ve'], v['p0'], v['psv'], v['Vn'], v['size']))
    out['expansion'] = ets

    # ---------------------------------------------------------------- insulation
    print('\n[8] INSULATION')
    ins = {}
    for where, Ta, RH, hs in (('roof (35 C / 70 % humid hour)', 35.0, 0.70, 6.0), ('roof (35 C / 80 % worst hour)', 35.0, 0.80, 6.0),
                              ('indoor hall (26 C / 60 %)', 26.0, 0.60, 8.0)):
        for DN in (25, 40, 50, 65):
            t, Ts, q, Td = insul_thk(DN_OD[DN], 7.0, Ta, RH, 0.036, hs)
            ins['%s DN%d' % (where.split(')')[0] + ')', DN)] = dict(t=t, Ts=Ts, q=q, Td=Td)
            print('  CHW 7 C %-32s DN%-3d dew pt %.1f C -> elastomeric >= %s mm (surface %.1f C, gain %.1f W/m)' % (
                where, DN, Td, t, Ts, q))
    gain_roof = sum(insul_thk(DN_OD[P[t]['DN']], 9.5, 40.0, 0.3, 0.036, 6.0, False)[2] * 2 * P[t]['L']
                    for t in ('L-CH-01', 'L-CH-02', 'L-CH-03', 'L-CH-04', 'L-CH-05'))
    for DN in (50, 65):
        R_ins = math.log((DN_OD[DN] / 2 + 50) / (DN_OD[DN] / 2)) / (2 * math.pi * 0.040)
        R_s = 1 / (6.0 * 2 * math.pi * (DN_OD[DN] / 2000 + 0.05))
        q = (90 - 30) / (R_ins + R_s)
        print('  HW 90 C DN%d, mineral wool 50 mm + Al cladding (30 C air): loss %.0f W/m, cladding %.1f C' % (DN, q, 30 + q * R_s))
    hw_loss = sum((87 - 35) / (math.log((DN_OD[P[t]['DN']] / 2 + 50) / (DN_OD[P[t]['DN']] / 2)) / (2 * math.pi * 0.040)
                               + 1 / (6.0 * 2 * math.pi * (DN_OD[P[t]['DN']] / 2000 + 0.05))) * 2 * P[t]['L']
                  for t in ('L-HW-01', 'L-HW-02', 'L-HW-03', 'L-HW-04'))
    print('  roof CHW piping heat gain ~%.2f kW (40 C, 40 mm); roof HW piping loss ~%.2f kW (50 mm)' % (gain_roof / 1e3, hw_loss / 1e3))
    out['insulation'] = dict(table=ins, chw_gain_kW=gain_roof / 1e3, hw_loss_kW=hw_loss / 1e3)

    # ---------------------------------------------------------------- fan coils
    m_fa = 10 * 0.010 * 1.15
    n_fcu = 4
    for cfm in FCU_CLASSES:                                 # smallest class that carries the insulated-roof load
        V_fcu = n_fcu * cfm * 1.699 / 3600 * 1.18
        x_fa = m_fa / V_fcu
        T_ea = RS.IN_HALL['T'] + x_fa * (DB_SUMMER - RS.IN_HALL['T'])
        w_ea = RS.IN_HALL['w'] + x_fa * (w_from_wb(DB_SUMMER, WB_TOWER) - RS.IN_HALL['w'])
        cf_mix, cf_room = fcu_factor(T_ea, w_ea), fcu_factor(RS.IN_HALL['T'], RS.IN_HALL['w'])
        need = hall_ins / n_fcu / cf_mix
        if FCU_CLASSES[cfm][0] >= need:
            break
    nom, fanAC, fanEC = FCU_CLASSES[cfm]
    need_unins = hall_unins / n_fcu / cf_mix
    q_lat = (10 * 0.055 + m_fa * 2450 * (w_from_wb(DB_SUMMER, WB_TOWER) - RS.IN_HALL['w']) + 0.35) * 1.1
    cond_hall = q_lat / 2450 * 3600
    print('\n[9] HALL FAN COILS (10 x 10 x 2.5 m): load %.1f kW uninsulated / %.1f kW insulated roof' % (hall_unins, hall_ins))
    print('  fresh air 100 L/s mixed at the FCUs -> entering %.1f C / %.1f g/kg; capacity factor vs 27/19 rating %.2f (room air only %.2f)' % (
        T_ea, w_ea * 1e3, cf_mix, cf_room))
    print('  insulated roof: need %.1f kW nominal per unit x %d -> select %d x %d CFM class (%.1f kW nominal, ~%.1f kW on site),'
          ' water %.2f m3/h each, fan %d W AC / %d W EC (uninsulated would need %.1f kW -> 800 CFM)' % (
              need, n_fcu, n_fcu, cfm, nom, nom * cf_mix, V_hall / n_fcu, fanAC, fanEC, need_unins))
    print('  latent load ~%.1f kW -> hall condensate ~%.1f L/h; air changes %.0f /h' % (q_lat, cond_hall, n_fcu * cfm * 1.699 / 250))
    fcu_pos = [(2.5, 0.4, 'S wall, throw N'), (7.5, 0.4, 'S wall, throw N'), (2.5, 9.6, 'N wall, throw S'), (7.5, 9.6, 'N wall, throw S')]
    out['fcu'] = dict(n=n_fcu, cfm=cfm, nominal=nom, site=nom * cf_mix, cf_mix=cf_mix, cf_room=cf_room, T_ea=T_ea, w_ea=w_ea,
                      need=need, V_each=V_hall / n_fcu, fanAC=fanAC, fanEC=fanEC, cond=cond_hall, q_lat=q_lat, pos=fcu_pos)
    er_nom, _, er_fan = FCU_CLASSES[400]
    print('  ELECTRICAL ROOM: load ~%.1f kW -> FCU-E 400 CFM high-wall (%.1f kW nominal, ~%.1f kW at 25 C/50 %%) + DX split 12 kBTU/h'
          ' (T3 tropical) as automatic standby' % (elec_room, er_nom, er_nom * fcu_factor(25.0, w_from_rh(25.0, 0.5))))
    out['elec_room'] = dict(load=elec_room, fcu_nom=er_nom, fcu_site=er_nom * fcu_factor(25.0, w_from_rh(25.0, 0.5)))

    # ---------------------------------------------------------------- engine glycol loop and oil cooler
    print('\n[10] ENGINE GLYCOL LOOP AND OIL COOLER (interface with docs/electrical M-751 / TE-GLY / DC-1-FAN)')
    print('  oil heat: 2 x 608 core bearings %.2f kW (115k rpm, oil jet), heat soak %.2f, oil pump %.2f -> %.2f kW;'
          ' with FPT/PMG bearings on the same oil %.2f kW -> oil cooler design %.1f kW, oil ~%.1f L/min 100->70 C' % (
              gl['core_bearings'], gl['soak'], gl['oil_pump'], gl['oil_core'], gl['oil_all'], gl['oil_design'], gl['oil_flow_Lmin']))
    print('  glycol loop heat: PMG %.2f + rectifier %.2f + oil (core) %.2f + panels %.2f = %.2f kW -> DC-1 design %.1f kW' % (
        gl['pmg'], gl['rect'], gl['oil_core'], gl['panels'], gl['Q_gly'], gl['Q_des']))
    print('  DC-1 (UA %.0f W/K, air %.0f m3/h, EC fans ~%.0f W): glycol supply %.1f C dry at 46 C; %.1f C with adiabatic pads'
          ' (air %.1f C, ~%.0f L/h water at the design hour) -> PMG 35-40 C target (docs/06) met without the tower; dry is still < ALM 58 C' % (
              gl['dc1_UA'], gl['dc1_air_m3h'], gl['dc1_fan_W'], gl['T_sup_dry'], gl['T_sup_pad'], gl['T_pad_air'], gl['pad_water_Lh']))
    print('  OC-1 oil cooler (core 608 system): %.1f kW design (%.1f kW if FPT/PMG bearings join), oil ~%.1f L/min 100->70 C,'
          ' glycol in %.1f C, LMTD %.1f K, UA %.0f W/K (brazed PHE)' % (
              gl['oil_design'], gl['oil_design_with_fpt'], gl['oil_flow_Lmin'], gl['T_glycol_at_oc'], gl['oc_LMTD'], gl['oc_UA']))
    out['glycol'] = gl

    # ---------------------------------------------------------------- operating modes
    global HALL_DEMAND
    HALL_DEMAND = hall_ins                                  # roof insulated (user answer)
    rng_ref = Q_rej / (L_cw * CPW)
    def make_ctx(rev, S, fkW, po):
        k = PKG[rev]
        return dict(rev=rev, m1=hy['m1'], rng_ref=rng_ref, S=S, fan_kW=fkW, cw_des=k['cw_frac'],
                    L_hx4=L_hx4 if k['hx4'] else 0.0, Q_hx4=Q_hx4 if k['hx4'] else 0.0, pumps=po)
    ctx = make_ctx(REV, sel['S'], fan_kW, pump_out)
    ctxA = make_ctx('A', selA['S'], TOWER_SIZES[selA['S']][0], pump_A)
    modes = {m: run_mode(m, ctx) for m in MODE_SPEC}
    balA = run_mode('BALANCED', ctxA)
    print('\n[11] OPERATING MODES at Borazjan summer design (46 C / WB %.0f C, hall %.1f kW, %s)' % (WB_TOWER, HALL_DEMAND, pk['label']))
    print('  %-18s %-9s %5s %5s %5s %5s | %6s %6s %6s | %6s %6s %6s %6s | %6s %6s' % (
        'mode', 'chillers', 'T1', 'CW', 'fan', 'CWfl', 'P_eng', 'aux', 'NET', 'cool', 'coil', 'hall', 'unmet', 'el-eq', 'eta_el'))
    for m, x in list(modes.items()) + [('rev A BAL', balA)]:
        print('  %-18s %-9s %5.1f %5.1f %4.0f%% %4.0f%% | %6.1f %6.2f %6.1f | %6.1f %6.1f %6.1f %6.1f | %6.1f %5.1f%%' % (
            m, '+'.join(c[-1] for c in x['chillers']) or '-', x['T1'], x['Tc'], x['fan'] * 100, x['cw_frac'] * 100,
            x['P_eng'], x['aux'], x['net'], x['cool'], x['coil'], x['hall'], x['hall_unmet'], x['el_equiv'], x['eta_el'] * 100))
    print('  aux items (kW):')
    for m, x in modes.items():
        print('    %-18s ' % m + ', '.join('%s %.2f' % (k, v) for k, v in x['aux_items'].items() if v > 0.004))
    print('    %-18s ' % 'rev A BAL' + ', '.join('%s %.2f' % (k, v) for k, v in balA['aux_items'].items() if v > 0.004))
    print('  tower water (make-up at 3.5 cycles, mid of latent..saturated estimate): ' + ', '.join(
        '%s %.0f L/h' % (m, x['makeup']) for m, x in modes.items()))
    print('  el-eq = NET + hall cooling / %.1f (split-AC electricity avoided) - hall FCU/ERV fans; unmet hall load would cost'
          ' a further unmet/%.1f kW if split ACs carry it' % (C.COP_SPLIT, C.COP_SPLIT))
    out['modes'] = modes
    out['modes_revA_balanced'] = balA

    # ---------------------------------------------------------------- electrical loads (summer = BALANCED mode)
    bal = modes['BALANCED']
    ai = bal['aux_items']
    pk_ = {t: p_['kW'] for t, p_ in pump_out.items()}
    loads = [  # tag, description, connected kW, summer running kW, winter running kW, supply, board
        ('P-1A/B', 'HW primary pump, twin ECM', pk_['P-1A/B'] * 1.6, ai['P-1'], ai['P-1'], '1~230 V', 'B6-R'),
        ('P-2A', 'HW pump CH-1, ECM const. flow', pk_['P-2A'] * 1.5, ai['P-2A'], 0, '1~230 V', 'B6-R'),
        ('P-2B', 'HW pump CH-2, ECM const. flow', pk_['P-2B'] * 1.5, ai['P-2B'], 0, '1~230 V', 'B6-R'),
        ('P-3', 'DHW/heating branch pump', max(pk_['P-3'] * 1.5, 0.1), 0.02, pk_['P-3'], '1~230 V', 'B6-R'),
        ('P-4A', 'CHW primary CH-1, ECM const. flow', pk_['P-4A'] * 1.5, ai['P-4A'], 0, '1~230 V', 'B6-R'),
        ('P-4B', 'CHW primary CH-2, ECM const. flow', pk_['P-4B'] * 1.5, ai['P-4B'], 0, '1~230 V', 'B6-R'),
        ('P-5A/B', 'CHW secondary twin ECM (dp control)', pk_['P-5A/B'] * 1.6, ai['P-5'], pk_['P-5A/B'] * 0.4, '1~230 V', 'B6-R'),
        ('P-6A/B', 'condenser-water pump + VFD', pk_['P-6A/B'] * 1.4, ai['P-6'], 0, '3~400 V', 'B6-R'),
        ('CT-1 fan', 'tower EC/VFD fan', fan_kW, ai['CT fan'], 0, '3~400 V', 'B6-R'),
        ('CH-1', 'chiller controls/pumps (internal)', CHILLERS['CH-1']['el'], CHILLERS['CH-1']['el'], 0, '1~230 V', 'B6-R'),
        ('CH-2', 'chiller controls/pumps (internal)', CHILLERS['CH-2']['el'], CHILLERS['CH-2']['el'], 0, '1~230 V', 'B6-R'),
        ('D-101', 'exhaust diverter actuator (spring return)', 0.02, 0.01, 0.01, '24 VAC from K-EX (SR1-O6)', 'B6-R/SR1'),
        ('WT-1', 'dosing pumps x3 + conductivity controller + BD valve', 0.10, 0.05, 0.01, '1~230 V', 'B6-R'),
        ('F-SS', 'side-stream separator purge valve', 0.01, 0.005, 0, '24 VDC', 'B6-R'),
        ('RO-1', 'softener + RO 400 L/h ULP (indoor), deferrable', 0.60, pk['ro_kW'], 0.03, '1~230 V', 'B6-E'),
        ('P-9', 'make-up / permeate booster to roof, deferrable', 0.37, 0.04, 0.02, '1~230 V', 'B6-E'),
        ('P-7', 'DHW tank charging / circulation', 0.06, 0.03, 0.06, '1~230 V', 'B6-E'),
        ('EH-301', 'tower basin heater (freeze, standby)', 1.5, 0, 0.05, '1~230 V', 'B6-R'),
        ('HT-1', 'heat tracing make-up/CW lines 30 m x 20 W/m', 0.6, 0, 0.05, '1~230 V', 'B6-R'),
        ('BOP-R', 'roof BOP panel: B6-R, PSU, meters, panel fan', 0.08, 0.08, 0.06, '1~230 V', 'B6-R'),
        ('DC-1', 'engine glycol dry cooler EC fans (fed from BOP-R, in engine P_aux)', gl['dc1_fan_W'] / 1e3, 0.05, 0.10,
         '1~230 V', 'B4 (engine)'),
        ('FCU-1..4', 'hall fan coils 4 x %d CFM (EC motors)' % cfm, 4 * fanEC / 1e3, bal['bldg_fans'] - 0.15, 4 * fanEC / 1e3 * 0.4,
         '1~230 V', 'building'),
        ('ERV-1', 'energy-recovery ventilator 500 m3/h, CO2 control', 0.18, 0.15, 0.10, '1~230 V', 'building'),
        ('FCU-E', 'electrical-room fan coil EC', er_fan / 1e3, 0.04, 0.0, '1~230 V', 'B6-E'),
        ('AC-E', 'electrical-room DX split standby 12 kBTU/h', 1.5, 0.0, 0.3, '1~230 V', 'B6-E'),
        ('EF-E', 'battery/electrical-room exhaust fan', 0.03, 0.03, 0.03, '1~230 V', 'B6-E'),
    ]
    plant = [l for l in loads if l[6] not in ('building', 'B4 (engine)')]
    s_conn = sum(l[2] for l in loads)
    s_sum = sum(l[3] for l in loads)
    s_win = sum(l[4] for l in loads)
    s_plant = sum(l[3] for l in plant)
    s_plant_w = sum(l[4] for l in plant)
    assumed = C.AUX_CCHP / 1e3                               # 'pumps + tower fan' in cchp_study; the extra 0.35 kW of
    P_corr = DESIGN['P_net'] + assumed - s_plant             # roof_site_study stays as the intake-coil air-side loss
    annual = (s_sum * SUMMER_FRACTION + s_win * (1 - SUMMER_FRACTION)) * HOURS_YEAR
    print('\n[12] ELECTRICAL LOAD OF HVAC ITEMS (kW; summer = BALANCED mode at design)')
    print('  %-10s %-60s %6s %7s %7s  %-26s %s' % ('tag', 'item', 'conn.', 'summer', 'winter', 'supply', 'board'))
    for l in loads:
        print('  %-10s %-60s %6.2f %7.2f %7.2f  %-26s %s' % l)
    print('  %-71s %6.2f %7.2f %7.2f' % ('TOTAL', s_conn, s_sum, s_win))
    print('  plant-side parasitic (excl. hall FCUs/ERV and engine DC-1) summer %.2f kW (rev A %.2f), winter %.2f kW;'
          ' annual HVAC energy ~%.0f MWh' % (s_plant, balA['aux'], s_plant_w, annual / 1e3))
    print('  cchp_study AUX_CCHP assumed %.2f kW -> corrected net to company loads %.1f kW (docs/03: %.1f kW; rev A %.1f kW)' % (
        assumed, P_corr, DESIGN['P_net'], balA['net']))
    bldg_cool = bal['hall'] + ER_LOAD
    print('  building cooling %.1f kW displaces ~%.1f kW of split-AC electricity (COP %.1f)' % (
        bldg_cool, bldg_cool / C.COP_SPLIT, C.COP_SPLIT))
    out['electrical'] = dict(loads=[dict(tag=l[0], item=l[1], conn=l[2], summer=l[3], winter=l[4], supply=l[5], board=l[6])
                                    for l in loads], conn=s_conn, summer=s_sum, winter=s_win, plant_summer=s_plant,
                             plant_winter=s_plant_w, assumed=assumed, P_net_doc=DESIGN['P_net'], P_net_corr=P_corr,
                             annual_MWh=annual / 1e3, bldg_cool=bldg_cool, split_saved=bldg_cool / C.COP_SPLIT,
                             revA_aux=balA['aux'], revA_net=balA['net'])

    # ---------------------------------------------------------------- water options with softened make-up
    print('\n[13] TOWER MAKE-UP WITH SOFTENER (hardness < 100 ppm; sewer discharge allowed): BALANCED mode, 5600 h/yr cooling')
    E = 0.5 * (modes['BALANCED']['E_lo'] + modes['BALANCED']['E_hi'])
    ec_city, ec_ro = 400 * EC_PER_TDS, 20.0                 # softening swaps Ca/Mg for Na: conductivity ~unchanged
    regen = 0.04                                            # softener regeneration + rinse, fraction of softened water
    rec_ro = 0.75                                           # softened feed -> higher RO recovery than 0.60
    def option(name, C, limit_ec, use_ro):
        M = E * C / (C - 1)
        if use_ro:
            x = (ec_city - limit_ec / C) / (ec_city - ec_ro)
            perm = x * M
            feed = perm / rec_ro
            soft = (1 - x) * M + feed
        else:
            x, perm, feed, soft = 0.0, 0.0, 0.0, M
        city = soft * (1 + regen)
        sewer = (M - E) + (feed - perm) + soft * regen
        return dict(name=name, cycles=C, limit=limit_ec, ro_share=x, makeup=M, city=city, sewer=sewer, perm=perm,
                    ro_kW=perm / 1e3 * 0.7, city_m3y=city * 5600 / 1e3, sewer_m3y=sewer * 5600 / 1e3)
    opts = [option('softened only, chiller limit 800 uS/cm (JRA)', 800 / ec_city, 800, False),
            option('softened only, chiller limit 2000 uS/cm (if maker allows)', 2000 / ec_city, 2000, False),
            option('softened only, chiller limit 3000 uS/cm (if maker allows)', 3000 / ec_city, 3000, False),
            option('softener + RO blend, 800 uS/cm, 3.5 cycles (rev B)', 3.5, 800, True),
            option('softener + RO blend, 800 uS/cm, 6 cycles (recommended for JRA)', 6.0, 800, True),
            option('softener + RO blend, 800 uS/cm, 8 cycles', 8.0, 800, True)]
    print('  evaporation (mid estimate) %.0f L/h' % E)
    print('  %-62s %6s %6s %7s %7s %7s %7s %8s' % ('option', 'cycles', 'RO %', 'make-up', 'city', 'sewer', 'RO kW', 'city m3/y'))
    for o in opts:
        print('  %-62s %6.2f %5.0f%% %7.0f %7.0f %7.0f %7.2f %8.0f' % (o['name'], o['cycles'], o['ro_share'] * 100, o['makeup'],
                                                                o['city'], o['sewer'], o['ro_kW'], o['city_m3y']))
    out['water_soft'] = dict(E=E, options=opts, regen=regen, rec_ro=rec_ro)

    # ---------------------------------------------------------------- single SC10 vs pair, island part load
    print('\n[14] RE-CHECK: insulated hall %.1f kW -> single SC10-class chiller or SC10 + SC5?' % hall_ins)
    L_single = CHILLERS['CH-1']['cw'] * 0.995 * pk['cw_frac'] + L_hx4
    Q_single = 50.2 + 50.2 * 0.644 + CHILLERS['CH-1']['el'] + Q_hx4
    sel_s = select_tower(L_single, Q_single, pk['tower_fan_speed'])
    fan_s = TOWER_SIZES[sel_s['S']][0]
    ctxS = make_ctx(REV, sel_s['S'], fan_s, pump_out)
    single = {m: run_mode(m, ctxS) for m in ('SINGLE BALANCED', 'SINGLE MAX-COOLING')}
    demand = DESIGN['coil'] + ER_LOAD + hall_ins
    print('  demand at design: coil %.1f + elec room %.1f + hall %.1f = %.1f kW (coil %.1f at WB 28)' % (
        DESIGN['coil'], ER_LOAD, hall_ins, demand, coil_28))
    print('  single SC10 -> tower %d ton class (fan %.1f kW, ~%d kg): ' % (sel_s['S'], fan_s, TOWER_SIZES[sel_s['S']][3]) + '; '.join(
        '%s: cool %.1f kW, hall %.1f (unmet %.1f), aux %.2f, net %.1f' % (m, x['cool'], x['hall'], x['hall_unmet'], x['aux'], x['net'])
        for m, x in single.items()))
    b = modes['BALANCED']
    print('  pair (rev B) BALANCED: cool %.1f kW, hall %.1f (unmet %.1f), aux %.2f, net %.1f' % (
        b['cool'], b['hall'], b['hall_unmet'], b['aux'], b['net']))
    part = {}
    for N_, TIT_ in ((100e3, 750), (105e3, 750)):
        for label, cx, md in (('pair', ctx, 'BALANCED'), ('single', ctxS, 'SINGLE BALANCED')):
            cxp = dict(cx, N=N_, TIT=TIT_)
            x = run_mode(md, cxp)
            part['%dk/%d %s' % (N_ / 1e3, TIT_, label)] = x
    print('  island v1 part load (T1 15 C, BALANCED rules):')
    for k, x in part.items():
        print('    %-20s Q_hw %.1f kW, P_eng (gross before HVAC) %.1f kW, cool %.1f = coil %.1f + elec %.1f + hall %.1f (unmet %.1f),'
              ' aux %.2f, net %.1f kW' % (k, x['Q_hw'], x['P_eng'], x['cool'], x['coil'], x['er'], x['hall'], x['hall_unmet'],
                                          x['aux'], x['net']))
    out['recheck'] = dict(demand=demand, coil_28=coil_28, tower_single=sel_s, tower_single_fan_kW=fan_s,
                          tower_single_kg=TOWER_SIZES[sel_s['S']][3], tower_single_dia=TOWER_SIZES[sel_s['S']][1],
                          single=single, pair_balanced=b, part=part)

    # ---------------------------------------------------------------- heat shortfall with the as-built engine
    print('\n[14b] HEAT SHORTFALL (as-built engine, exhaust %.0f C): can SC10 + SC5 still carry the hall %.1f kW? options'
          % (DESIGN['T_ex'], hall_ins))
    b = modes['BALANCED']
    print('  BALANCED: hot water %.1f kW of %.1f kW chiller heat capacity -> HEAT-limited, not chiller-limited; cooling %.1f kW'
          ' = coil %.1f + elec room %.1f + hall %.1f (unmet %.1f)' % (b['Q_in'], ch['Qmax'], b['cool'], b['coil'], b['er'], b['hall'],
                                                                     b['hall_unmet']))
    opt = {}
    def row(key, lab, m, fuel_add=0.0, note=''):
        opt[key] = dict(label=lab, T1=m['T1'], cool=m['cool'], hall=m['hall'], unmet=m['hall_unmet'], aux=m['aux'], net=m['net'],
                        net_hall=m['net'] - m['hall_unmet'] / C.COP_SPLIT, F=m['F'], fuel_add=fuel_add, note=note)
    row('O0', 'BALANCED as is (coil first, T1 15 C)', b, note='hall short; company split ACs cover the rest')
    row('O1', 'MAX-COOLING (hall first, coil takes the rest)', modes['MAX-COOLING'], note='no hardware')
    # O2: keep the original 69 kW HX-1 (8 tubes/row) -> lower gas exit; O2b: same + hot water 85/78 C
    big = hx_rate(HXG, hx['Nt'], hx['Lt'], hx['Nr'], DESIGN['mg'], DESIGN['T_ex'], hx['mw'], HW_RETURN)
    sel_r = hx_rate(HXG, hx_min['Nt'], hx_min['Lt'], hx_min['Nr'], DESIGN['mg'], DESIGN['T_ex'], hx['mw'], HW_RETURN)
    big78 = hx_rate(HXG, hx['Nt'], hx['Lt'], hx['Nr'], DESIGN['mg'], DESIGN['T_ex'], hx['mw'], 78.0)
    for key, lab, r_ in (('O2', 'credit of the kept HX-1 (8 x 15 x 0.6 m) vs the 100 C basis', big), ('O2b', 'same + hot water 85/78 C', big78)):
        q = (r_['Q'] - sel_r['Q']) * 0.95
        row(key, lab, run_mode('BALANCED', dict(ctx, Q_hw_add=q, eta_add=1e9)),
            note='gas out %.0f C, +%.1f kW heat%s' % (r_['Tg_out'], q, ', chiller COP at 85 C to be confirmed' if key == 'O2b' else ''))
    # O3: fuel-fired boost sized for zero hall shortfall in BALANCED (recuperator cold-side bypass in the engine, or duct burner)
    lo, hi = 0.0, 30.0
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if run_mode('BALANCED', dict(ctx, Q_hw_add=mid))['hall_unmet'] > 0.05 else (lo, mid)
    q3 = hi
    m3 = run_mode('BALANCED', dict(ctx, Q_hw_add=q3))
    row('O3', 'fuel boost to zero shortfall (recup. bypass / duct burner)', m3, q3 / 0.90,
        note='+%.1f kW heat, HX-1 duty %.1f kW' % (q3, DESIGN['Q_gas'] + q3 / 0.95))
    # O4: electric trim (small air-cooled chiller on the CHW loop or the company split ACs), COP 2.6 at 46 C
    o4 = dict(b, net=b['net'] - b['hall_unmet'] / C.COP_SPLIT, hall=b['hall'] + b['hall_unmet'], hall_unmet=0.0)
    row('O4', 'BALANCED + electric trim for the shortfall (COP %.1f)' % C.COP_SPLIT, o4, note='%.1f kW electric' % (b['hall_unmet'] / C.COP_SPLIT))
    # O5: heat-limited plant -> colder cooling water raises the COP: BALANCED rules with full tower fan and 100 % CW flow
    m5 = run_mode('BALANCED COLD-CW', ctx)
    row('O5', 'BALANCED + full tower fan / 100 % CW (cold CW, higher COP)', m5,
        note='CW %.1f C, COP %.3f; +%.1f kW cooling for +%.2f kW aux' % (m5['Tc'], m5['cop'], m5['cool'] - b['cool'], m5['aux'] - b['aux']))
    print('  %-4s %-58s %5s %6s %6s %6s %6s %7s %7s %7s  %s' % ('', 'option', 'T1', 'cool', 'hall', 'unmet', 'aux', 'NET', 'NET*',
                                                              'fuel', 'note'))
    for k, o in opt.items():
        print('  %-4s %-58s %5.1f %6.1f %6.1f %6.1f %6.2f %7.2f %7.2f %7.1f  %s' % (k, o['label'], o['T1'], o['cool'], o['hall'], o['unmet'],
              o['aux'], o['net'], o['net_hall'], o['F'], o['note']))
    print('  * NET with the whole hall covered (unmet part by split ACs at COP %.1f): the fair comparison; fuel in kW' % C.COP_SPLIT)
    out['shortfall'] = dict(Q_in=b['Q_in'], Qmax=ch['Qmax'], options=opt, Q_boost=q3, HX1_kept=big, HX1_kept78=big78,
                           HX1_min=dict(Nt=hx_min['Nt'], Nr=hx_min['Nr'], Lt=hx_min['Lt'], dry=hx_min['mass']['dry']))

    # ---------------------------------------------------------------- fire suppression (FK-5-1-12)
    print('\n[15] FIRE SUPPRESSION, clean agent FK-5-1-12 (NFPA 2001 / ISO 14520 total flooding)')
    V_enc = 1.4 * 0.9 * 1.3                                 # engine enclosure gross volume (docs/03 sec 6)
    V_er = 3.5 * 3.0 * 3.0                                  # electrical room, ASSUMED
    W1 = fk_mass(V_enc, 5.9, 5.0)                           # class B (heptane 4.5 % x 1.3); hot surfaces -> 2nd shot
    W2 = fk_mass(V_er, 5.3, 18.0)                           # class A higher hazard / electrical, occupiable
    print('  engine enclosure (hot + gas zones) %.2f m3: 5.9 %% at 5 C -> %.2f kg per shot; main + reserve shot (2 cylinders);'
          ' %.1f %% at 60 C (unoccupied)' % (V_enc, W1, fk_conc(W1, V_enc, 60.0)))
    print('  electrical room %.1f m3 (ASSUMED 3.5 x 3.0 x 3.0 m): 5.3 %% at 18 C -> %.1f kg; %.1f %% at 35 C (NOAEL 10 %%)' % (
        V_er, W2, fk_conc(W2, V_er, 35.0)))
    out['fire'] = dict(V_enc=V_enc, V_er=V_er, W_enc=W1, W_er=W2, C_enc_60=fk_conc(W1, V_enc, 60.0), C_er_35=fk_conc(W2, V_er, 35.0))

    path = os.path.join(HERE, 'hvac_results.json')
    with open(path, 'w') as fh:
        json.dump(out, fh, indent=1, default=float)
    print('\nwritten %s' % os.path.relpath(path, os.getcwd()))

if __name__ == '__main__':
    main()
