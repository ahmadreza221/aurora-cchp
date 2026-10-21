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
CP_GAS = C.CP_LOW / 1e3                                     # 1.080 kJ/kg K exhaust (same as cchp_study)
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

def engine_case(T_in, TIT=800):
    c = C.cchp(115e3, TIT, 'target', T_in=T_in)
    r = c['r']
    mg = r['ma'] + r['mf']
    T_ex = r['T_stack_in'] - 273.15
    coil = RS.inlet_coil_kW(r['ma'], RS.OUT['T'], RS.OUT['w'], T_in) if T_in < RS.OUT['T'] else 0.0
    P = c['P_net'] - (0.35e3 if T_in < RS.OUT['T'] else 0)
    return dict(T_in=T_in, TIT=TIT, ma=r['ma'], mf=r['mf'], mg=mg, T_ex=T_ex,
                Q_gas=mg * CP_GAS * (T_ex - 100.0), Q_hw=c['Q_hw'] / 1e3, Q_cool=c['Q_cool'] * DER / 1e3,
                coil=coil, P_net=P / 1e3, F=c['F'] / 1e3, P_aux_engine=r['P_aux'] / 1e3)

DESIGN = engine_case(15.0)                                  # summer design: intake chilled to 15 C
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

def design_hx():
    mw = DESIGN['Q_gas'] / (CPW * (HW_SUPPLY - HW_RETURN))
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
        dp_hx_path = (0.8 * q_h + 0.6 * q_face_h * 2 + r['dp_g'] + (0.02 * 5 / D_stack + 1.0) * q_c)
        dp_bypass = 0.8 * q_h + 1.2 * q_h + (0.02 * 6 / D_stack + 1.0) * q_h
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

def tower_cold_water(S, L_kgs, Q_kW, WB):
    Lr = S * TOWER_RATING['L_per_ton'] * 995 / 3600
    G = Lr / TOWER_RATING['LG']
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
    hx = design_hx()
    r, m = hx['design'], hx['mass']
    ex = exhaust_system(hx)
    dpt = dew_points(DESIGN)
    print('\n[1] EXHAUST/WATER HX  HX-1  (316L helical-finned tubes, counter-cross-flow, gas 1 pass, water %d passes)' % hx['Nr'])
    print('  duty (gas side) %.1f kW, water %.2f kg/s (%.1f m3/h) %.0f->%.0f C, gas %.0f->100 C' % (
        DESIGN['Q_gas'], hx['mw'], m3h(hx['mw'], 87), HW_RETURN, HW_SUPPLY, DESIGN['T_ex']))
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
    sel = None
    for S in TOWER_SIZES:
        t = tower_cold_water(S, L_cw, Q_rej, WB_TOWER + WB_RECIRC)
        if t['Tc'] <= CW_SUPPLY:
            sel = t
            break
    print('\n[3] COOLING TOWER CT-1 (open, counterflow, induced draft, FRP round)')
    print('  rating basis %.0f/%.0f/%.0f C, %.2f m3/h per nominal ton, L/G %.1f -> rated KaV/L %.3f' % (
        TOWER_RATING['Th'], TOWER_RATING['Tc'], TOWER_RATING['WB'], TOWER_RATING['L_per_ton'], TOWER_RATING['LG'], NTU_RATED))
    print('  duty %.1f kW, water %.1f m3/h, range %.2f K, design WB %.1f C (+%.1f recirculation)' % (
        Q_rej, L_cw / 0.995 * 3.6, sel['rng'], WB_TOWER, WB_RECIRC))
    fan_kW, dia, hgt, op_kg = TOWER_SIZES[sel['S']]
    print('  SELECT nominal %d ton class: cold water %.2f C, approach %.2f K, L/G %.2f, fan %.1f kW, ~D%.2f x %.2f m, ~%d kg op' % (
        sel['S'], sel['Tc'], sel['approach'], sel['LG'], fan_kW, dia, hgt, op_kg))
    wbsens = []
    print('  wet-bulb sensitivity (heat in %.1f kW):' % DESIGN['Q_hw'])
    print('    %5s %7s %7s %7s %7s %7s %8s' % ('WB', 'CW in', 'COP', 'cool', 'coil15', 'bldg', 'surplus'))
    for wb in (24.0, 26.0, 27.0, 28.0, 29.0, 30.0):
        tw = tower_cold_water(sel['S'], L_cw, Q_rej, wb + WB_RECIRC)
        Tcw = max(tw['Tc'], 26.0)
        cc = chiller_pair(DESIGN['Q_hw'], hy['T_ch_in'], Tcw)
        coil = RS.inlet_coil_kW(DESIGN['ma'], DB_SUMMER, w_from_wb(DB_SUMMER, wb), 15.0)
        wbsens.append(dict(WB=wb, Tcw=Tcw, cop=cc['cop'], cool=cc['Q_cool'], coil=coil, bldg=cc['Q_cool'] - coil,
                           surplus=cc['surplus']))
        print('    %5.1f %7.2f %7.3f %7.1f %7.1f %7.1f %8.1f' % (wb, Tcw, cc['cop'], cc['Q_cool'], coil, cc['Q_cool'] - coil,
                                                              cc['surplus']))
    E_max, T_air_out = evaporation(sel['G'], sel['LG'], sel['rng'], WB_TOWER)
    hfg = 2501 - 2.36 * 34
    E_nom = Q_rej / hfg * 3600
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
    # HX-4: engine auxiliary glycol loop (PMG + rectifier + oil cooler, docs/electrical 5xx) into the cooling water in
    # summer; glycol 40 -> 35 C needs CW at ~32 C, a dry cooler alone cannot do it at 46 C. DC-1 dry cooler for winter.
    Q_aux = 3.5
    V_aux = Q_aux / (CPW * 3.0) / 0.995 * 3.6
    lm4 = ((40 - 35.0) - (35 - 32.0)) / math.log((40 - 35.0) / (35 - 32.0))
    t4 = tower_cold_water(sel['S'], L_cw + V_aux / 3.6 * 0.995, Q_rej + Q_aux, WB_TOWER + WB_RECIRC)
    print('  HX-4 glycol/CW plate HX: %.1f kW, glycol 40->35 C, CW %.2f m3/h 32->35 C, LMTD %.1f K, UA %.0f W/K;'
          ' tower with HX-4: %.1f kW -> cold water %.2f C (selection unchanged)' % (
              Q_aux, V_aux, lm4, Q_aux * 1e3 / lm4, Q_rej + Q_aux, t4['Tc']))
    out['tower'] = dict(sel=sel, fan_kW=fan_kW, hx4=dict(Q=Q_aux, V=V_aux, LMTD=lm4, UA=Q_aux * 1e3 / lm4, Tc=t4['Tc'],
                                                          Q_tot=Q_rej + Q_aux), dia=dia, height=hgt, op_kg=op_kg, L_kgs=L_cw, V_m3h=L_cw / 0.995 * 3.6,
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
    V_hall = hall_unins / (CPW * 5) / rho_w(10) * 3600
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
        ('L-CH-08', 'CHW electrical-room branch', V_er, 10, 15.0, 'route length ASSUMED'),
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
    pumps = [  # tag, service, m3/h, T, list of (item, kPa), duty, control
        ('P-1A/B', 'HW primary through HX-1 (twin head)', hy['V1'], 87,
         [('pipe L-HW-01', P['L-HW-01']['dp']), ('HX-1 water side', r['dp_w']), ('LLH-1 + air/dirt separator', 8),
          ('strainer (dirty)', 10), ('check + isolation', 6), ('flow meter', 2)], 'duty/standby, ECM const. flow'),
        ('P-2A', 'HW secondary to CH-1', CHILLERS['CH-1']['hw'] * 3.6, 86,
         [('pipe L-HW-02/03', P['L-HW-02']['dp'] + P['L-HW-03']['dp']), ('CH-1 generator', CHILLERS['CH-1']['dp_hw']),
          ('strainer', 10), ('check + isolation', 6), ('balancing valve', 8)], 'on with CH-1, ECM'),
        ('P-2B', 'HW secondary to CH-2', CHILLERS['CH-2']['hw'] * 3.6, 86,
         [('pipe L-HW-02/04', P['L-HW-02']['dp'] + P['L-HW-04']['dp']), ('CH-2 generator', CHILLERS['CH-2']['dp_hw']),
          ('strainer', 10), ('check + isolation', 6), ('balancing valve', 8)], 'on with CH-2, ECM'),
        ('P-3', 'DHW / heating branch', P['L-HW-05']['Q'], 80,
         [('pipe L-HW-05', P['L-HW-05']['dp']), ('HX-2/HX-3 plate HX', 25), ('V-PRI 3-way', 15), ('strainer', 10),
          ('check + isolation', 6)], 'on demand, ECM'),
        ('P-4A', 'CHW primary CH-1', CHILLERS['CH-1']['chw'] * 3.6, 10,
         [('pipe L-CH-01', P['L-CH-01']['dp']), ('CH-1 evaporator', CHILLERS['CH-1']['dp_chw']), ('strainer', 10),
          ('check + isolation', 6), ('balancing valve', 8), ('MV-CH1 isolation', 3)], 'on with CH-1 + 15 min run-on'),
        ('P-4B', 'CHW primary CH-2', CHILLERS['CH-2']['chw'] * 3.6, 10,
         [('pipe L-CH-02', P['L-CH-02']['dp']), ('CH-2 evaporator', CHILLERS['CH-2']['dp_chw']), ('strainer', 10),
          ('check + isolation', 6), ('balancing valve', 8), ('MV-CH2 isolation', 3)], 'on with CH-2 + 15 min run-on'),
        ('P-5A/B', 'CHW secondary distribution (twin head)', V_sec, 10,
         [('pipe L-CH-03', P['L-CH-03']['dp']), ('pipe L-CH-05/06/07 (hall index)', P['L-CH-05']['dp'] + P['L-CH-06']['dp'] + P['L-CH-07']['dp']),
          ('FCU coil', 30), ('PICV', 25), ('strainer', 10), ('check + changeover valves', 12), ('air/dirt separator', 3)],
         'duty/standby, ECM dp-control (VFD)'),
        ('P-6A/B', 'condenser water (tower)', L_cw / 0.995 * 3.6, 34,
         [('pipe L-CW-01/02', P['L-CW-01']['dp'] + P['L-CW-02']['dp']), ('CH-1 absorber+condenser', CHILLERS['CH-1']['dp_cw']),
          ('basket strainer', 10), ('check + isolation', 6), ('balancing valve', 8), ('tower static lift + nozzles', 40)],
         'duty/standby, VFD set to rated flow'),
    ]
    pump_out = {}
    print('\n[6] PUMPS')
    for tag, svc, Q, T, items, ctl in pumps:
        H_kPa = sum(v for _, v in items) * 1.10
        P_hyd = Q / 3600 * H_kPa * 1e3
        eta = eta_ww(P_hyd)
        kW = P_hyd / eta / 1e3
        pump_out[tag] = dict(service=svc, Q=Q, H_kPa=H_kPa, H_m=H_kPa / (rho_w(T) * 9.81e-3), P_hyd=P_hyd, eta=eta, kW=kW,
                             items=items, control=ctl, T=T)
        print('  %-7s %-40s %6.2f m3/h  H %5.1f kPa (%4.1f m)  P_hyd %4.0f W  eta_ww %.2f -> %.2f kW  [%s]' % (
            tag, svc, Q, H_kPa, pump_out[tag]['H_m'], P_hyd, eta, kW, ctl))
        print('          ' + ', '.join('%s %.0f' % (n, v) for n, v in items) + ' kPa, +10 %')
    out['pumps'] = pump_out
    # alternative: one constant-flow HW loop (no low-loss header) through HX-1 and both chiller generators
    V_single = hy['V2']
    r_single = hx_rate(HXG, hx['Nt'], hx['Lt'], hx['Nr'], DESIGN['mg'], DESIGN['T_ex'], hy['m2'], 83.0)
    H_single = (P['L-HW-01']['dp'] * (V_single / hy['V1']) ** 2 + r_single['dp_w'] + CHILLERS['CH-1']['dp_hw'] + 10 + 6 + 8) * 1.10
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
    n_fcu, cfm = 4, 800
    V_fcu = n_fcu * cfm * 1.699 / 3600 * 1.18
    x_fa = m_fa / V_fcu
    T_ea = RS.IN_HALL['T'] + x_fa * (DB_SUMMER - RS.IN_HALL['T'])
    w_ea = RS.IN_HALL['w'] + x_fa * (w_from_wb(DB_SUMMER, WB_TOWER) - RS.IN_HALL['w'])
    cf_mix, cf_room = fcu_factor(T_ea, w_ea), fcu_factor(RS.IN_HALL['T'], RS.IN_HALL['w'])
    need = hall_unins / n_fcu / cf_mix
    nom, fanAC, fanEC = FCU_CLASSES[cfm]
    q_lat = (10 * 0.055 + m_fa * 2450 * (w_from_wb(DB_SUMMER, WB_TOWER) - RS.IN_HALL['w']) + 0.35) * 1.1
    cond_hall = q_lat / 2450 * 3600
    print('\n[9] HALL FAN COILS (10 x 10 x 2.5 m): load %.1f kW uninsulated / %.1f kW insulated roof' % (hall_unins, hall_ins))
    print('  fresh air 100 L/s mixed at the FCUs -> entering %.1f C / %.1f g/kg; capacity factor vs 27/19 rating %.2f (room air only %.2f)' % (
        T_ea, w_ea * 1e3, cf_mix, cf_room))
    print('  need %.1f kW nominal per unit x %d -> select %d x %d CFM class (%.1f kW nominal, ~%.1f kW on site), water %.2f m3/h each,'
          ' fan %d W AC / %d W EC' % (need, n_fcu, n_fcu, cfm, nom, nom * cf_mix, V_hall / n_fcu, fanAC, fanEC))
    print('  latent load ~%.1f kW -> hall condensate ~%.1f L/h; air changes %.0f /h' % (q_lat, cond_hall, n_fcu * cfm * 1.699 / 250))
    fcu_pos = [(2.5, 0.4, 'S wall, throw N'), (7.5, 0.4, 'S wall, throw N'), (2.5, 9.6, 'N wall, throw S'), (7.5, 9.6, 'N wall, throw S')]
    out['fcu'] = dict(n=n_fcu, cfm=cfm, nominal=nom, site=nom * cf_mix, cf_mix=cf_mix, cf_room=cf_room, T_ea=T_ea, w_ea=w_ea,
                      need=need, V_each=V_hall / n_fcu, fanAC=fanAC, fanEC=fanEC, cond=cond_hall, q_lat=q_lat, pos=fcu_pos)
    er_nom, _, er_fan = FCU_CLASSES[400]
    print('  ELECTRICAL ROOM: load ~%.1f kW -> FCU-E 400 CFM high-wall (%.1f kW nominal, ~%.1f kW at 25 C/50 %%) + DX split 12 kBTU/h'
          ' (T3 tropical) as automatic standby' % (elec_room, er_nom, er_nom * fcu_factor(25.0, w_from_rh(25.0, 0.5))))
    out['elec_room'] = dict(load=elec_room, fcu_nom=er_nom, fcu_site=er_nom * fcu_factor(25.0, w_from_rh(25.0, 0.5)))

    # ---------------------------------------------------------------- electrical loads
    pk = {t: p['kW'] for t, p in pump_out.items()}
    loads = [  # tag, description, connected kW, summer running kW, winter running kW, supply, board
        ('P-1A/B', 'HW primary pump, twin ECM', pk['P-1A/B'] * 1.6, pk['P-1A/B'], pk['P-1A/B'], '1~230 V', 'B6-R'),
        ('P-2A', 'HW pump CH-1', pk['P-2A'] * 1.5, pk['P-2A'], 0, '1~230 V', 'B6-R'),
        ('P-2B', 'HW pump CH-2', pk['P-2B'] * 1.5, pk['P-2B'], 0, '1~230 V', 'B6-R'),
        ('P-3', 'DHW/heating branch pump', max(pk['P-3'] * 1.5, 0.1), pk['P-3'] * 0.3, pk['P-3'], '1~230 V', 'B6-R'),
        ('P-4A', 'CHW primary CH-1', pk['P-4A'] * 1.5, pk['P-4A'], 0, '1~230 V', 'B6-R'),
        ('P-4B', 'CHW primary CH-2', pk['P-4B'] * 1.5, pk['P-4B'], 0, '1~230 V', 'B6-R'),
        ('P-5A/B', 'CHW secondary twin ECM (dp control)', pk['P-5A/B'] * 1.6, pk['P-5A/B'] * 0.8, pk['P-5A/B'] * 0.4, '1~230 V', 'B6-R'),
        ('P-6A/B', 'condenser-water pump + VFD', pk['P-6A/B'] * 1.4, pk['P-6A/B'], 0, '3~400 V', 'B6-R'),
        ('CT-1 fan', 'tower fan + VFD', fan_kW, fan_kW * 0.75, 0, '3~400 V', 'B6-R'),
        ('CH-1', 'chiller controls/pumps (internal)', CHILLERS['CH-1']['el'], CHILLERS['CH-1']['el'], 0, '1~230 V', 'B6-R'),
        ('CH-2', 'chiller controls/pumps (internal)', CHILLERS['CH-2']['el'], CHILLERS['CH-2']['el'], 0, '1~230 V', 'B6-R'),
        ('D-801', 'exhaust diverter actuator (spring return)', 0.02, 0.01, 0.01, '24 VAC via SR1 safety output', 'B4/SR1'),
        ('WT-1', 'dosing pumps x3 + conductivity controller + BD valve', 0.10, 0.05, 0.01, '1~230 V', 'B6-R'),
        ('F-SS', 'side-stream separator purge valve', 0.01, 0.005, 0, '24 VDC', 'B6-R'),
        ('RO-1', 'RO unit 300 L/h (indoor), ~40 % duty', 0.75, 0.30, 0.05, '1~230 V', 'B6-E'),
        ('P-9', 'make-up / permeate booster to roof', 0.37, 0.10, 0.02, '1~230 V', 'B6-E'),
        ('P-7', 'DHW tank charging / circulation', 0.06, 0.03, 0.06, '1~230 V', 'B6-E'),
        ('EH-1301', 'tower basin heater (freeze, standby)', 1.5, 0, 0.05, '1~230 V', 'B6-R'),
        ('HT-1', 'heat tracing make-up/CW lines 30 m x 20 W/m', 0.6, 0, 0.05, '1~230 V', 'B6-R'),
        ('BOP-R', 'roof BOP panel: B6-R, PSU, meters, panel fan', 0.08, 0.08, 0.06, '1~230 V', 'B6-R'),
        ('DC-1', 'aux glycol dry cooler EC fans (winter / backup)', 0.35, 0.05, 0.15, '1~230 V', 'B6-R'),
        ('FCU-1..4', 'hall fan coils 4 x 800 CFM (EC motors)', 4 * fanEC / 1e3, 4 * fanEC / 1e3 * 0.7, 4 * fanEC / 1e3 * 0.4, '1~230 V', 'building'),
        ('ERV-1', 'energy-recovery ventilator 500 m3/h (option)', 0.18, 0.15, 0.10, '1~230 V', 'building'),
        ('FCU-E', 'electrical-room fan coil EC', er_fan / 1e3, er_fan / 1e3, 0.0, '1~230 V', 'B6-E'),
        ('AC-E', 'electrical-room DX split standby 12 kBTU/h', 1.5, 0.0, 0.3, '1~230 V', 'B6-E'),
        ('EF-E', 'battery/electrical-room exhaust fan', 0.03, 0.03, 0.03, '1~230 V', 'B6-E'),
    ]
    plant = [l for l in loads if l[6] != 'building']
    s_conn = sum(l[2] for l in loads)
    s_sum = sum(l[3] for l in loads)
    s_win = sum(l[4] for l in loads)
    s_plant = sum(l[3] for l in plant)
    s_plant_w = sum(l[4] for l in plant)
    assumed = C.AUX_CCHP / 1e3                               # 'pumps + tower fan' in cchp_study; the extra 0.35 kW of
    P_corr = DESIGN['P_net'] + assumed - s_plant             # roof_site_study stays as the intake-coil air-side loss
    annual = (s_sum * SUMMER_FRACTION + s_win * (1 - SUMMER_FRACTION)) * HOURS_YEAR
    print('\n[10] ELECTRICAL LOAD OF HVAC ITEMS (kW)')
    print('  %-10s %-52s %6s %7s %7s  %-26s %s' % ('tag', 'item', 'conn.', 'summer', 'winter', 'supply', 'board'))
    for l in loads:
        print('  %-10s %-52s %6.2f %7.2f %7.2f  %-26s %s' % l)
    print('  %-63s %6.2f %7.2f %7.2f' % ('TOTAL', s_conn, s_sum, s_win))
    print('  plant-side parasitic (excl. hall FCUs/ERV) summer %.2f kW, winter %.2f kW; annual HVAC energy ~%.0f MWh' % (
        s_plant, s_plant_w, annual / 1e3))
    print('  cchp_study AUX_CCHP assumed %.2f kW -> corrected net to company loads %.1f kW (docs/03: %.1f kW)' % (
        assumed, P_corr, DESIGN['P_net']))
    bldg_cool = ch['Q_cool'] - coil_doc
    print('  building cooling %.1f kW displaces ~%.1f kW of split-AC electricity (COP %.1f)' % (
        bldg_cool, bldg_cool / C.COP_SPLIT, C.COP_SPLIT))
    out['electrical'] = dict(loads=[dict(tag=l[0], item=l[1], conn=l[2], summer=l[3], winter=l[4], supply=l[5], board=l[6])
                                    for l in loads], conn=s_conn, summer=s_sum, winter=s_win, plant_summer=s_plant,
                             plant_winter=s_plant_w, assumed=assumed, P_net_doc=DESIGN['P_net'], P_net_corr=P_corr,
                             annual_MWh=annual / 1e3, bldg_cool=bldg_cool, split_saved=bldg_cool / C.COP_SPLIT)

    path = os.path.join(HERE, 'hvac_results.json')
    with open(path, 'w') as fh:
        json.dump(out, fh, indent=1, default=float)
    print('\nwritten %s' % os.path.relpath(path, os.getcwd()))

if __name__ == '__main__':
    main()
