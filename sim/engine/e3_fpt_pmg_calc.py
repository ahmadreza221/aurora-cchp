# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "matplotlib"]
# ///
"""GR180-CCHP subsystem E3 - interduct + free power turbine (FPT) + FPT/PMG rotor, bearings, seals, housings
+ 30 kW high-speed PM generator (PMG) + exhaust diffuser / radial collector.   Design calculation (single source of
truth for the geometry used by cad/engine/fpt_pmg.py).

Run (repo root):   uv run sim/engine/e3_fpt_pmg_calc.py
                   (plain `python3 sim/engine/e3_fpt_pmg_calc.py` also runs; without numpy the rotordynamic and blade
                    eigen-analyses and the plots are skipped)
Outputs:  cad_out/engine/E3/E3_calc_results.json   geometry + results (read by the CAD script)
          cad_out/engine/E3/E3_campbell.png         rotor Campbell diagram (damped, SFD supports)
          cad_out/engine/E3/E3_unbalance.png        unbalance response (G2.5)
          cad_out/engine/E3/E3_blade_campbell.png   FPT blade 1F/2F vs engine orders
Second pass: the CAD script writes cad_out/engine/E3/E3_massprops.json (measured mass / inertia of rotor parts);
re-running this script then uses the CAD values for J and the rotordynamic model.

Frames: ENG (mm, x downstream = east, y north, z up; x = 0 tunnel front face), ROOF = (1.880 + x/1000, 7.850 + y/1000,
0.600 + z/1000) m.   Units inside: SI unless a name ends in _mm.
Inputs: sim/gg_turbine_design.json (GG turbine exit), sim/life_study.point() (cycle back-pressure, required shaft power).
Loss model style = sim/gg_turbine_meanline.py (Soderberg + aspect ratio + Reynolds, TE blockage, tip clearance).
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SIM = os.path.join(ROOT, 'sim')
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'E3'); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, SIM)
try:
    import numpy as np
except ImportError:          # pure-python fallback: everything except eigen-analyses
    np = None

# ---------------------------------------------------------------------------------------------------------------
# 0. constants
# ---------------------------------------------------------------------------------------------------------------
CP, G = 1148.0, 1.333                     # combustion gas (same as GG meanline)
RG = CP * (G - 1) / G; EX = (G - 1) / G
N_DES = 60000.0                           # FPT / PMG design speed (rpm)
N_GOV = 65000.0                           # max governed speed (electrical docs)
N_TRIP = 71500.0                          # independent N2 overspeed trip (SMCU, electrical D8)
N_OS = 72000.0                            # 120 % overspeed design case (task)
N_SPIN = 78000.0                          # proof spin test = 120 % of max governed 65k (electrical 01 §5)
N_MIN_CONT = 48000.0                      # lowest CONTINUOUS N2 (B3 holds N2 >= 48k on load; 0-48k = start-up transit)
OMEGA = lambda n: n * 2 * math.pi / 60
ROT_FPT = -1                              # FPT turns COUNTER-clockwise seen from the intake (-theta about +x);
                                          # GG turns clockwise (+theta) -> counter-rotating spools
MU_AIR = lambda T: 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)

def interp(tab, x):
    """piecewise-linear table [(x, y), ...] (clamped)"""
    if x <= tab[0][0]: return tab[0][1]
    for (x0, y0), (x1, y1) in zip(tab[:-1], tab[1:]):
        if x0 <= x <= x1: return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tab[-1][1]

# IN718 (AMS 5662/5663, solution + double aged), conservative typical-minimum data, T in C, MPa / GPa / 1e-6/K
IN718 = dict(rho=8190.0,
             E=[(20, 200), (300, 187), (500, 177), (600, 171), (700, 165)],
             alpha=[(20, 12.8), (100, 13.0), (300, 13.5), (500, 14.4), (600, 14.8), (700, 15.4)],
             YS=[(20, 1034), (300, 965), (500, 930), (600, 895), (650, 860), (700, 800)],
             UTS=[(20, 1241), (300, 1170), (500, 1120), (600, 1080), (650, 1030), (700, 950)],
             k=[(20, 11.4), (300, 15.0), (500, 18.0), (700, 21.0)],
             # Larson-Miller (C = 20, T in K, t in h), rupture, generic literature curve (replace with mill data)
             LMP=[(900, 19.3e3), (700, 20.4e3), (550, 21.5e3), (400, 22.5e3), (250, 23.6e3), (150, 24.6e3)])

def lmp_in718(sig):
    t = IN718['LMP']
    if sig >= t[0][0]: return t[0][1]
    for (s0, p0), (s1, p1) in zip(t[:-1], t[1:]):
        if s1 <= sig <= s0:
            f = (math.log(s0) - math.log(sig)) / (math.log(s0) - math.log(s1)); return p0 + f * (p1 - p0)
    return t[-1][1]

def creep_life_h(sig, T_K):
    return 10 ** (lmp_in718(sig) / T_K - 20)

# ---------------------------------------------------------------------------------------------------------------
# 1. boundary conditions: GG turbine exit + cycle
# ---------------------------------------------------------------------------------------------------------------
GG = json.load(open(os.path.join(SIM, 'gg_turbine_design.json')))
MG = GG['mg']; T00 = GG['T03']; P00 = GG['P03']; CX0 = GG['Cx3']
X_GG_TE = 118.3                           # E1 rotor trailing edge / hub r 19.0 (ENG mm)
R_H0, R_T0 = 19.0, 35.35                  # interduct inlet: E1 hub at TE / GG NGV shroud bore (tip 35.15 + 0.20)
try:
    import life_study as L
    _p = L.point(115e3, 800, 'target', T_amb_C=15.0, alt_m=50.0, booster=False)
    P_SHAFT_CYCLE = _p['P_shaft']; T_HOT_CYCLE = _p['T_hot']
except Exception:                         # values of 2026-10-21 run
    P_SHAFT_CYCLE, T_HOT_CYCLE = 25635.7, 883.13
PA_SITE = 101325.0 * (1 - 2.25577e-5 * 50.0) ** 5.25588
P_EXIT = PA_SITE * (1 + 0.035 + 0.015 + 0.005)       # static at recuperator hot inlet H1 (cycle: recup + HX + stack)
P01_CYCLE = P00 * (1 - 0.015)                        # cycle assumed 1.5 % interduct loss
ETA_PT_CYCLE, ETA_MECH_CYCLE = 0.78, 0.985

# ---------------------------------------------------------------------------------------------------------------
# 2. axial stack (ENG x, mm) - one place for all stations
# ---------------------------------------------------------------------------------------------------------------
X = dict(
    id0=119.3,            # interduct inlet = stationary hub lip (1.0 mm behind E1 rotor TE at 118.3)
    flangeE2=116.0,       # E3 flange face = E2 rear-ring face x 115.0 + 1.0 mm gasket (sim/engine/e2_design.json: x_e3_face 115, OD 176, PCD 160, 16 x M8, spigot d120 x 3)
    tc_in=133.0,          # FPT-inlet thermocouples TE-510A/B + P45 static tap PT-524
    drum0=145.0,          # collector drum west wall (bolted to the interduct mid-flange)
    ngv_le=189.3,         # interduct exit = FPT NGV leading edge (interduct length 70.0)
    ngv_te=201.3,         # NGV axial chord 12.0
    rot_le=204.8,         # axial gap 3.5 (0.29 b_ngv)
    rot_te=216.8,         # rotor axial chord 12.0
    rad_w=231.0,          # radial diffuser west wall (shroud side)
    rad_e=253.0,          # radial diffuser east wall (hub side) -> channel width 22
    drum1=299.0,          # collector drum east wall
)
# radii (mm)
GEO = dict(
    ngv_hub_le=31.0, ngv_tip_le=46.5, ngv_hub_te=31.0, ngv_tip_te=51.5,
    rot_hub_le=31.0, rot_tip_le=51.5, rot_hub_te=27.5, rot_tip_te=56.0, tip_gap=0.30,
    rad_out=125.0, drum_ro=215.0, drum_hub_r=100.0,
    hub_bend_R=34.0, shroud_bend_R=10.0,
)

# ---------------------------------------------------------------------------------------------------------------
# 3. interduct (outward S-duct) GG exit -> FPT NGV
# ---------------------------------------------------------------------------------------------------------------
def s_curve(xi):            # smooth step, zero slope at both ends
    return 3 * xi ** 2 - 2 * xi ** 3

def interduct_walls(n=41):
    x0, x1 = X['id0'], X['ngv_le']; Lid = x1 - x0
    hub, cas = [], []
    for i in range(n):
        xi = i / (n - 1); x = x0 + Lid * xi; s = s_curve(xi)
        hub.append((x, R_H0 + (GEO['ngv_hub_le'] - R_H0) * s))
        cas.append((x, R_T0 + (GEO['ngv_tip_le'] - R_T0) * s))
    return hub, cas

def mass_flow_mach(A, P0, T0, m):
    """subsonic Mach number from m = A P0 /sqrt(R T0) sqrt(g) M (1+(g-1)/2 M^2)^-(g+1)/(2(g-1))"""
    lo, hi = 1e-4, 0.999
    for _ in range(80):
        M = 0.5 * (lo + hi)
        f = A * P0 / math.sqrt(RG * T0) * math.sqrt(G) * M * (1 + 0.5 * (G - 1) * M * M) ** (-(G + 1) / (2 * (G - 1)))
        if f > m: hi = M
        else: lo = M
    return M

def interduct():
    hub, cas = interduct_walls(61)
    Lid = X['ngv_le'] - X['id0']
    st = []
    for (x, rh), (_, rc) in zip(hub, cas):
        st.append(dict(x=x, rh=rh, rc=rc))
    # meridional slope of the mean line and normal flow area
    for i, s in enumerate(st):
        j0, j1 = max(i - 1, 0), min(i + 1, len(st) - 1)
        dx = st[j1]['x'] - st[j0]['x']
        sh = (st[j1]['rh'] - st[j0]['rh']) / dx; sc = (st[j1]['rc'] - st[j0]['rc']) / dx
        phi = math.atan(0.5 * (sh + sc)); s['phi'] = phi
        s['A'] = math.pi * (s['rc'] ** 2 - s['rh'] ** 2) * math.cos(phi) * 1e-6
        s['slope_hub_deg'] = math.degrees(math.atan(sh)); s['slope_cas_deg'] = math.degrees(math.atan(sc))
    A0, A1 = st[0]['A'], st[-1]['A']; AR = A1 / A0
    # flow (isentropic core) -> velocity, Cp distribution
    rho0 = None
    for s in st:
        M = mass_flow_mach(s['A'], P00, T00, MG)
        T = T00 / (1 + 0.5 * (G - 1) * M * M); V = M * math.sqrt(G * RG * T); p = P00 * (T / T00) ** (1 / EX)
        s.update(M=M, V=V, p=p, rho=p / (RG * T))
    q0 = 0.5 * st[0]['rho'] * st[0]['V'] ** 2
    for s in st: s['Cp'] = (s['p'] - st[0]['p']) / q0
    # separation / diffusion criteria
    Req = [math.sqrt(s['A'] / math.pi) * 1e3 for s in st]
    two_theta = 2 * math.degrees(math.atan((Req[-1] - Req[0]) / Lid))
    loc = max(2 * math.degrees(math.atan((Req[i + 1] - Req[i]) / (st[i + 1]['x'] - st[i]['x']))) for i in range(len(st) - 1))
    dRm_L = ((GEO['ngv_hub_le'] + GEO['ngv_tip_le']) / 2 - (R_H0 + R_T0) / 2) / Lid
    h0 = R_T0 - R_H0
    # loss: wall friction + diffusion (Sovran-Klomp effectiveness) + curvature/secondary + hub-lip cavity
    Cf = 0.0035
    Kf = 0.0
    for a, b in zip(st[:-1], st[1:]):
        ds = math.hypot(b['x'] - a['x'], 0.5 * (b['rh'] + b['rc'] - a['rh'] - a['rc'])) * 1e-3
        Dh = 2 * (0.5 * (a['rc'] - a['rh'] + b['rc'] - b['rh'])) * 1e-3 * math.cos(a['phi'])
        q = 0.25 * (a['rho'] * a['V'] ** 2 + b['rho'] * b['V'] ** 2)
        Kf += 4 * Cf * ds / Dh * q / q0
    eta_d = 0.85                       # S-duct, swirl-free inflow, 2theta_eq < 8 deg (Sovran & Klomp / ITD data)
    Kd = (1 - eta_d) * (1 - 1 / AR ** 2)
    Kc = 0.010 * (dRm_L / 0.2)         # S-bend secondary-flow loss, scaled on dR/L (ITD literature 0.005-0.02)
    Kcav = 0.005                        # stationary-lip / rotating-hub gap at the inlet
    K = Kf + Kd + Kc + Kcav
    dP0 = K * q0
    return dict(L_mm=Lid, A0_mm2=A0 * 1e6, A1_mm2=A1 * 1e6, AR=AR, two_theta_eq_deg=two_theta, two_theta_local_max_deg=loc,
                dRmean_over_L=dRm_L, L_over_h0=Lid / h0, max_wall_slope_deg=max(max(abs(s['slope_hub_deg']), abs(s['slope_cas_deg'])) for s in st),
                M_in=st[0]['M'], V_in=st[0]['V'], M_out=st[-1]['M'], V_out=st[-1]['V'], Cp_ideal=1 - 1 / AR ** 2,
                Cp_isentropic_core=st[-1]['Cp'], q_in=q0, K_friction=Kf, K_diffusion=Kd, K_curvature=Kc, K_cavity=Kcav,
                K_total=K, dP0=dP0, dP0_over_P0=dP0 / P00, P01=P00 - dP0, T01=T00,
                ok_separation=(two_theta <= 8.0 and dRm_L <= 0.35 and loc <= 12.0),
                hub=[(round(x, 3), round(r, 3)) for x, r in hub], cas=[(round(x, 3), round(r, 3)) for x, r in cas])

# ---------------------------------------------------------------------------------------------------------------
# 4. FPT meanline (3 radii, free vortex, zero exit swirl) + exhaust diffuser + collector
# ---------------------------------------------------------------------------------------------------------------
def soderberg(defl_deg, h, b_ax, Re):
    z0 = 0.04 + 0.06 * (defl_deg / 100.0) ** 2
    z1 = (1 + z0) * (0.993 + 0.075 * b_ax / h) - 1
    return z1 * (1e5 / Re) ** 0.25

def zweifel(s, b, a_in, a_out):           # angles from axial, rad, signed
    return 2 * s / b * math.cos(a_out) ** 2 * abs(math.tan(a_in) - math.tan(a_out))

FORBID = {3, 7, 29}                        # prime factors of GG NGV 21 / rotor 29
def allowed_count(z, other=None):
    def ok(n):
        f = {p for p in range(2, n + 1) if n % p == 0 and all(p % q for q in range(2, int(p ** 0.5) + 1))}
        if f & FORBID: return False
        if other and math.gcd(n, other) != 1: return False
        return n % 2 == 1                  # odd counts (no diametral symmetry with even struts / 2-lobe collector)
    for d in range(0, 20):
        for n in (z + d, z - d):
            if n > 9 and ok(n): return n
    return z

NGV_B, ROT_B = 12.0, 11.0                 # axial chords (mm): NGV constant; rotor = mean of the hub-tip taper below
ROT_B_HUB, ROT_B_TIP = 13.0, 9.0           # rotor axial chord at hub / tip (keeps the blade area taper ~0.4)
ZW_T = dict(ngv=0.90, rot=0.92)
TE_T = dict(ngv=0.50, rot=0.45)           # trailing-edge thickness (SLM NGV / 5-axis blisk)
K_TIP = 1.5                                # d(eta)/(gap/h) for an unshrouded blisk (Haller / Kacker-Okapuu range 1.2-2)
ETA_DIFF = 0.60                            # axial-radial exhaust diffuser effectiveness (Cp/Cp_ideal), data 0.55-0.75
K_PLENUM = 0.5                             # plenum circumferential-flow loss (x q_plenum)
K_OUTLET = 0.5                             # plenum -> DN250 outlet contraction (x q5)

def stage(P01, T01, W, N=N_DES, geo=GEO, Zn=None, Zr=None, verbose=False):
    """FPT stage + exhaust for a given Euler work W (J/kg). Returns stations, triangles, losses, exit static p5."""
    om = OMEGA(N)
    g = geo
    r = lambda mm: mm * 1e-3
    # stream-tube radii (equal-area) at rotor LE (2) and TE (3)
    def rad3(rh, rt):
        rm = math.sqrt(0.5 * (rh ** 2 + rt ** 2)); return [rh, rm, rt]
    R2 = [r(v) for v in rad3(g['rot_hub_le'], g['rot_tip_le'])]
    R3 = [r(v) for v in rad3(g['rot_hub_te'], g['rot_tip_te'])]
    A2 = math.pi * (R2[2] ** 2 - R2[0] ** 2); A3 = math.pi * (R3[2] ** 2 - R3[0] ** 2)
    K = W / om                                  # r*Ct2 = const (free vortex), Ct3 = 0  ->  W = om*K on every stream tube
    h_n = (g['ngv_tip_te'] - g['ngv_hub_te'] + g['ngv_tip_le'] - g['ngv_hub_le']) / 2
    h_r = (g['rot_tip_le'] - g['rot_hub_le'] + g['rot_tip_te'] - g['rot_hub_te']) / 2
    # ---- NGV exit
    Cx2, zn = 160.0, 0.10
    for _ in range(60):
        Ct2m = K / R2[1]; C2 = math.hypot(Ct2m, Cx2)
        T2 = T01 - C2 ** 2 / (2 * CP); T2s = T2 - zn * C2 ** 2 / (2 * CP)
        p2 = P01 * (T2s / T01) ** (1 / EX); rho2 = p2 / (RG * T2)
        Cx2n = MG / (rho2 * A2)
        a2 = math.atan2(Ct2m, Cx2)
        s_n = 2 * math.pi * R2[1] / (Zn or 19)
        c_n = NGV_B * 1e-3 / math.cos(0.5 * a2)
        Re_n = rho2 * C2 * c_n / MU_AIR(T2)
        o_n = s_n * math.cos(a2)
        zn_new = soderberg(math.degrees(a2), h_n, NGV_B, Re_n) + 0.2 * TE_T['ngv'] * 1e-3 / o_n
        if abs(Cx2n - Cx2) < 1e-4 and abs(zn_new - zn) < 1e-7: break
        Cx2 = 0.5 * (Cx2 + Cx2n); zn = zn_new
    # ---- rotor
    U2m, U3m = om * R2[1], om * R3[1]
    W2t = Ct2m - U2m; W2 = math.hypot(W2t, Cx2); b2 = math.atan2(W2t, Cx2)
    Cx3, zr = 150.0, 0.10
    tip_frac = K_TIP * g['tip_gap'] / h_r
    for _ in range(80):
        W3 = math.hypot(U3m, Cx3); b3 = math.atan2(-U3m, Cx3)
        # rothalpy (relative frame, radius change): T3 = T2 + (W2^2 - W3^2 + U3^2 - U2^2)/2cp
        T3 = T2 + (W2 ** 2 - W3 ** 2 + U3m ** 2 - U2m ** 2) / (2 * CP)
        T3s = T3 - zr * W3 ** 2 / (2 * CP)
        p3 = p2 * (T3s / T2) ** (1 / EX); rho3 = p3 / (RG * T3)
        Cx3n = MG / (rho3 * A3)
        s_r = 2 * math.pi * R3[1] / (Zr or 23)
        c_r = ROT_B * 1e-3 / math.cos(0.5 * (b2 + b3))
        Re_r = rho3 * W3 * c_r / MU_AIR(T3)
        o_r = s_r * math.cos(b3)
        zr_new = soderberg(math.degrees(abs(b2 - b3)), h_r, ROT_B, Re_r) + 0.2 * TE_T['rot'] * 1e-3 / o_r
        Zw_r = zweifel(2 * math.pi * R2[1] / (Zr or 23), ROT_B * 1e-3, b2, b3)
        zr_new *= (1 + 0.6 * max(Zw_r - 1.0, 0))
        if abs(Cx3n - Cx3) < 1e-4 and abs(zr_new - zr) < 1e-7: break
        Cx3 = 0.5 * (Cx3 + Cx3n); zr = zr_new
    # tip leakage: fraction of flow doing no work, mixed out at rotor exit
    W_act = W * (1 - tip_frac)
    T03 = T01 - W_act / CP
    # disk friction (front + rear face, enclosed rotating disk, Daily & Nece regime IV)
    rd = r(g['rot_hub_le']); nu2 = MU_AIR(T2) / rho2
    Re_d = om * rd ** 2 / nu2; Cm = 0.0622 / Re_d ** 0.2
    P_df = 2 * 0.5 * Cm * rho2 * om ** 3 * rd ** 5
    W_shaft_aero = W_act - P_df / MG
    # exit state: T3 (static) with real T03; recompute p3 consistent with leakage mixing (small)
    T3 = T03 - Cx3 ** 2 / (2 * CP); rho3 = p3 / (RG * T3)
    q3 = 0.5 * rho3 * Cx3 ** 2
    P03 = p3 * (T03 / T3) ** (1 / EX)
    # ---- exhaust: axial-radial diffuser -> plenum -> DN250 outlet
    A_rad = 2 * math.pi * r(g['rad_out']) * (X['rad_e'] - X['rad_w']) * 1e-3
    A3_cas = math.pi * (r(g['rot_tip_te'] + g['tip_gap']) ** 2 - R3[0] ** 2)
    AR_d = A_rad / A3_cas
    Cp_d = ETA_DIFF * (1 - 1 / AR_d ** 2)
    p4 = p3 + Cp_d * q3; V4 = Cx3 / AR_d * (rho3 / (p4 / (RG * T3)))
    A_pl = 2 * (g['drum_ro'] - g['rad_out']) * (X['drum1'] - X['drum0']) * 1e-6 * 0.75   # two half-plenums to the outlet
    rho4 = p4 / (RG * T03)
    V_pl = MG / (rho4 * A_pl); q_pl = 0.5 * rho4 * V_pl ** 2
    A5 = math.pi / 4 * 0.2604 ** 2                                                       # DN250 (273 x 6.3 -> ID 260.4)
    V5 = MG / (rho4 * A5); q5 = 0.5 * rho4 * V5 ** 2
    p5 = p4 - K_PLENUM * q_pl - (1 + K_OUTLET) * q5
    P05 = p5 + q5
    dh_is_ts = CP * T01 * (1 - (p5 / P01) ** EX)
    dh_is_tt = CP * T01 * (1 - (P03 / P01) ** EX)
    eta_ts = W_shaft_aero / dh_is_ts; eta_tt = W_shaft_aero / dh_is_tt
    # three-radius triangles
    rows = []
    for i, nm in enumerate(('hub', 'mean', 'tip')):
        U2, U3 = om * R2[i], om * R3[i]
        Ct2 = K / R2[i]; C2i = math.hypot(Ct2, Cx2)
        w2t = Ct2 - U2
        T2i = T01 - C2i ** 2 / (2 * CP)
        rows.append(dict(name=nm, r2=R2[i], r3=R3[i], U2=U2, U3=U3, Ct2=Ct2, Cx2=Cx2, Cx3=Cx3,
                         alpha2=math.degrees(math.atan2(Ct2, Cx2)), beta2=math.degrees(math.atan2(w2t, Cx2)),
                         beta3=math.degrees(math.atan2(-U3, Cx3)),
                         reaction=1 - (C2i ** 2 - Cx3 ** 2) / (2 * W),
                         M2=C2i / math.sqrt(G * RG * T2i), Mw2=math.hypot(w2t, Cx2) / math.sqrt(G * RG * T2i),
                         Mw3=math.hypot(U3, Cx3) / math.sqrt(G * RG * T3),
                         T0rel2=T2i + (w2t ** 2 + Cx2 ** 2) / (2 * CP)))
    return dict(W=W, W_act=W_act, W_shaft_aero=W_shaft_aero, P_df=P_df, tip_frac=tip_frac, Cx2=Cx2, Cx3=Cx3, C2m=C2,
                alpha2m=math.degrees(a2), beta2m=math.degrees(b2), beta3m=math.degrees(b3), T2=T2, p2=p2, rho2=rho2,
                T3=T3, p3=p3, rho3=rho3, P03=P03, T03=T03, q3=q3, zeta_ngv=zn, zeta_rot=zr, Re_ngv=Re_n, Re_rot=Re_r,
                c_ngv=c_n, c_rot=c_r, o_ngv=o_n, o_rot=o_r, s_ngv=s_n, s_rot=s_r, h_ngv=h_n, h_rot=h_r, Zw_rot=Zw_r,
                Zw_ngv=zweifel(s_n, NGV_B * 1e-3, 0.0, a2), A2=A2, A3=A3, U2m=U2m, U3m=U3m, psi=W / U2m ** 2,
                phi=Cx3 / U3m, AR_diff=AR_d, Cp_diff=Cp_d, p4=p4, V4=V4, V_plenum=V_pl, V5=V5, p5=p5, P05=P05,
                dh_is_ts=dh_is_ts, eta_ts=eta_ts, eta_tt=eta_tt, rows=rows,
                exit_KE_frac=0.5 * Cx3 ** 2 / dh_is_ts, U_over_C0=U2m / math.sqrt(2 * dh_is_ts),
                loss_ngv=zn * C2 ** 2 / 2, loss_rot=zr * W3 ** 2 / 2, loss_tip=tip_frac * W, loss_df=P_df / MG,
                loss_exit=0.5 * Cx3 ** 2 - (p5 - p3) / rho3)

def solve_stage(P01, T01, N=N_DES, Zn=None, Zr=None):
    """find Euler work W so that the static pressure at the H1 flange equals the cycle back-pressure P_EXIT"""
    lo, hi = 30e3, 100e3
    for _ in range(60):
        W = 0.5 * (lo + hi); s = stage(P01, T01, W, N, Zn=Zn, Zr=Zr)
        if s['p5'] > P_EXIT: lo = W
        else: hi = W
    return s

def blade_counts(P01, T01):
    s = solve_stage(P01, T01)
    rm2 = s['rows'][1]['r2']; a2 = math.radians(s['alpha2m'])
    b2, b3 = math.radians(s['beta2m']), math.radians(s['beta3m'])
    # Zweifel -> pitch -> count
    s_n = ZW_T['ngv'] * NGV_B * 1e-3 / (2 * math.cos(a2) ** 2 * abs(math.tan(a2)))
    s_r = ZW_T['rot'] * ROT_B * 1e-3 / (2 * math.cos(b3) ** 2 * abs(math.tan(b2) - math.tan(b3)))
    Zn = allowed_count(round(2 * math.pi * rm2 / s_n))
    Zr = allowed_count(round(2 * math.pi * rm2 / s_r), Zn)
    return Zn, Zr


# ---------------------------------------------------------------------------------------------------------------
# 5. FPT blade sections (shared with CAD) + blade structure
# ---------------------------------------------------------------------------------------------------------------
TC_ROOT, TC_TIP = 0.22, 0.05               # rotor t_max/c root / tip (5-axis blisk; area taper tip/root ~0.4)
TC_NGV = 0.22                              # NGV t/c (SLM, robust; no cooling)
AIRFOIL_AREA = 0.685                       # A = k c t   (NACA-type thickness, camber included)
AIRFOIL_IMIN = 0.040                       # I_min = k c t^3
DEV_DEG = 1.5                              # exit over-turning (deviation allowance) of metal angles

def free_vortex_angles(s, r_m, N=N_DES):
    """flow angles (deg, + = in the FPT rotation direction) on a cylindrical section of radius r_m (m)"""
    om = OMEGA(N); K = s['W'] / om
    Ct2 = K / r_m; U = om * r_m
    a2 = math.degrees(math.atan2(Ct2, s['Cx2']))
    b2 = math.degrees(math.atan2(Ct2 - U, s['Cx2']))
    b3 = math.degrees(math.atan2(-U, s['Cx3']))
    return a2, b2, b3

def rotor_sections(s, n=7):
    """cylindrical sections for the blisk blade, extended 1.2 mm beyond hub and tip (CAD trims with the annulus)"""
    rh = min(GEO['rot_hub_le'], GEO['rot_hub_te']) - 1.2; rt = max(GEO['rot_tip_le'], GEO['rot_tip_te']) + 0.25
    secs = []
    for i in range(n):
        r = rh + (rt - rh) * i / (n - 1)
        f = min(max((r - 29.25) / (53.75 - 29.25), 0.0), 1.0)
        _, b2, b3 = free_vortex_angles(s, r * 1e-3)
        tc = TC_ROOT + (TC_TIP - TC_ROOT) * f
        secs.append(dict(r=r, b_ax=ROT_B_HUB + (ROT_B_TIP - ROT_B_HUB) * f, ang_in=b2, ang_out=b3 - DEV_DEG, tc=tc, te=TE_T['rot']))
    return secs

def ngv_sections(s, n=5):
    rh = GEO['ngv_hub_le'] - 1.2; rt = max(GEO['ngv_tip_le'], GEO['ngv_tip_te']) + 1.2
    secs = []
    for i in range(n):
        r = rh + (rt - rh) * i / (n - 1)
        a2, _, _ = free_vortex_angles(s, r * 1e-3)
        secs.append(dict(r=r, b_ax=NGV_B, ang_in=0.0, ang_out=a2 + DEV_DEG, tc=TC_NGV, te=TE_T['ngv']))
    return secs

def blade_props(s, Zr):
    """spanwise blade model: radius, chord, thickness, area, I_min, stagger (root r 29.25 mid-chord, tip 53.75)"""
    r0, r1 = 29.25e-3, 53.75e-3; n = 25
    pts = []
    for i in range(n + 1):
        r = r0 + (r1 - r0) * i / n; f = i / n
        _, b2, b3 = free_vortex_angles(s, r)
        stag = math.atan(0.5 * (math.tan(math.radians(b2)) + math.tan(math.radians(b3))))
        c = (ROT_B_HUB + (ROT_B_TIP - ROT_B_HUB) * f) * 1e-3 / math.cos(stag); t = (TC_ROOT + (TC_TIP - TC_ROOT) * f) * c
        pts.append(dict(r=r, c=c, t=t, A=AIRFOIL_AREA * c * t, I=AIRFOIL_IMIN * c * t ** 3, stag=stag))
    return pts

def blade_stress(s, Zr, N):
    om = OMEGA(N); bp = blade_props(s, Zr); rho = IN718['rho']
    F = 0.0; m = 0.0; mr = 0.0; Ip = 0.0
    for a, b in zip(bp[:-1], bp[1:]):
        dr = b['r'] - a['r']; Am = 0.5 * (a['A'] + b['A']); rm = 0.5 * (a['r'] + b['r'])
        F += rho * om ** 2 * Am * rm * dr; m += rho * Am * dr; mr += rho * Am * dr * rm; Ip += rho * Am * dr * rm ** 2
    root = bp[0]
    sig_cf = F / root['A']
    # gas bending: tangential (torque) + axial force per blade, resultant at mid-span
    tau = MG * s['W'] / om * (N / N_DES) ** 0           # torque at design flow (conservative: same at overspeed)
    r_m = s['rows'][1]['r2']
    Ft = tau / (r_m * Zr)
    Fx = ((s['p2'] - s['p3']) * 0.5 * (s['A2'] + s['A3']) + MG * (s['Cx2'] - s['Cx3'])) / Zr
    h = bp[-1]['r'] - root['r']
    M = math.hypot(Ft, Fx) * h / 2
    sig_gas = M * (root['t'] / 2) / root['I']
    return dict(sig_cf=sig_cf / 1e6, sig_gas=sig_gas / 1e6, sig_root=(sig_cf + sig_gas) / 1e6, m_blade=m, r_cg=mr / m,
                Ip_blade=Ip, pull_one=F, root_c=root['c'], root_t=root['t'], tip_c=bp[-1]['c'], tip_t=bp[-1]['t'])

# ---------------------------------------------------------------------------------------------------------------
# 6. blisk disk: 1-D variable-thickness plane-stress solver (thermal + centrifugal + blade rim load)
# ---------------------------------------------------------------------------------------------------------------
DISK = dict(r_bore=5.25, hub_r=15.0, hub_h=23.0, web_r0=17.0, web_r1=22.0, web_h=8.0, rim_r0=24.5, rim_r=27.5, rim_h=16.0)
T_BORE_C, T_RIM_C = 500.0, 600.0           # steady metal temperatures (front cavity ~ T2 hub, Hirth heat-dam to the shaft)

def disk_h(r_mm):
    d = DISK
    if r_mm <= d['hub_r']: return d['hub_h']
    if r_mm <= d['web_r0']: return d['hub_h'] + (d['web_h'] - d['hub_h']) * (r_mm - d['hub_r']) / (d['web_r0'] - d['hub_r'])
    if r_mm <= d['web_r1']: return d['web_h']
    if r_mm <= d['rim_r0']: return d['web_h'] + (d['rim_h'] - d['web_h']) * (r_mm - d['web_r1']) / (d['rim_r0'] - d['web_r1'])
    return d['rim_h']

def disk_T(r_mm, hot=True):
    if not hot: return 20.0
    f = (r_mm - DISK['r_bore']) / (DISK['rim_r'] - DISK['r_bore'])
    return T_BORE_C + (T_RIM_C - T_BORE_C) * f ** 2

def disk_solve(N, rim_pull_total, hot=True, n=400):
    """integrate (u, F = h r sigma_r) from the bore; superpose to meet the rim radial load. Returns stresses (MPa)."""
    om = OMEGA(N); rho = IN718['rho']; nu = 0.29
    rb, ro = DISK['r_bore'] * 1e-3, DISK['rim_r'] * 1e-3
    sig_rim = rim_pull_total / (2 * math.pi * ro * DISK['rim_h'] * 1e-3)
    def run(u0, with_load):
        u, F = u0, 0.0; out = []
        dr = (ro - rb) / n
        def deriv(r, u, F):
            rmm = r * 1e3; h = disk_h(rmm) * 1e-3; T = disk_T(rmm, hot)
            E = interp(IN718['E'], T) * 1e9; a = interp(IN718['alpha'], T) * 1e-6 * (T - 20.0)
            sr = F / (h * r)
            st = E * (u / r - a) + nu * sr
            er = (sr - nu * st) / E + a
            body = rho * om ** 2 * r ** 2 * h if with_load else 0.0
            return er, h * st - body, sr, st
        r = rb
        for i in range(n):
            k1 = deriv(r, u, F); k2 = deriv(r + dr / 2, u + dr / 2 * k1[0], F + dr / 2 * k1[1])
            k3 = deriv(r + dr / 2, u + dr / 2 * k2[0], F + dr / 2 * k2[1]); k4 = deriv(r + dr, u + dr * k3[0], F + dr * k3[1])
            out.append((r, k1[2], k1[3], disk_h(r * 1e3) * 1e-3))
            u += dr / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]); F += dr / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]); r += dr
        d = deriv(r, u, F); out.append((r, d[2], d[3], disk_h(r * 1e3) * 1e-3))
        return out, F
    a0, Fa = run(0.0, True); b0, Fb = run(1e-5, True)
    # F(u0) linear: F = Fa + (Fb-Fa)/1e-5 * u0  -> target h*r*sig_rim at the rim
    target = DISK['rim_h'] * 1e-3 * ro * sig_rim
    u0 = (target - Fa) / ((Fb - Fa) / 1e-5)
    res, _ = run(u0, True)
    vm = [math.sqrt(sr ** 2 + st ** 2 - sr * st) for (_, sr, st, _) in res]
    num = sum(st * h for (_, _, st, h) in res); den = sum(h for (_, _, _, h) in res)
    i_max = max(range(len(vm)), key=lambda i: vm[i])
    return dict(sig_theta_bore=res[0][2] / 1e6, sig_vm_max=vm[i_max] / 1e6, r_vm_max_mm=res[i_max][0] * 1e3,
                sig_theta_avg=num / den / 1e6, sig_r_rim=sig_rim / 1e6,
                profile=[(round(r * 1e3, 2), round(sr / 1e6, 1), round(st / 1e6, 1)) for (r, sr, st, _) in res[::40]])

def disk_mass_props():
    """axisymmetric disk body (without blades): mass, Ip, It about own CG (x-axis = spin axis)"""
    rho = IN718['rho']; n = 200; m = Ip = 0.0; Iy = 0.0
    rb, ro = DISK['r_bore'] * 1e-3, DISK['rim_r'] * 1e-3
    for i in range(n):
        r = rb + (ro - rb) * (i + 0.5) / n; dr = (ro - rb) / n; h = disk_h(r * 1e3) * 1e-3
        dm = rho * 2 * math.pi * r * dr * h; m += dm; Ip += dm * r ** 2; Iy += dm * (r ** 2 / 2 + h ** 2 / 12)
    return m, Ip, Iy

# ---------------------------------------------------------------------------------------------------------------
# 7. blade vibration: tapered cantilever FE with centrifugal stiffening (min-inertia bending), Campbell vs EO
# ---------------------------------------------------------------------------------------------------------------
def blade_modes(s, Zr, N, nmodes=3, T_C=630.0):
    if np is None: return None
    bp = blade_props(s, Zr); rho = IN718['rho']; E = interp(IN718['E'], T_C) * 1e9; om = OMEGA(N)
    ne = len(bp) - 1; nd = 2 * (ne + 1)
    K = np.zeros((nd, nd)); M = np.zeros((nd, nd)); Kg = np.zeros((nd, nd))
    # centrifugal tension at each element (from tip)
    Ts = []
    for e in range(ne):
        T = 0.0
        for a, b in zip(bp[e:-1], bp[e + 1:]):
            T += rho * om ** 2 * 0.5 * (a['A'] + b['A']) * 0.5 * (a['r'] + b['r']) * (b['r'] - a['r'])
        Ts.append(T)
    soft = 0.0
    for e in range(ne):
        a, b = bp[e], bp[e + 1]; L = b['r'] - a['r']
        EI = E * 0.5 * (a['I'] + b['I']); mA = rho * 0.5 * (a['A'] + b['A']); cg = math.cos(0.5 * (a['stag'] + b['stag']))
        k = EI / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L], [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        m = mA * L / 420 * np.array([[156, 22 * L, 54, -13 * L], [22 * L, 4 * L * L, 13 * L, -3 * L * L], [54, 13 * L, 156, -22 * L], [-13 * L, -3 * L * L, -22 * L, 4 * L * L]])
        kg = Ts[e] / (30 * L) * np.array([[36, 3 * L, -36, 3 * L], [3 * L, 4 * L * L, -3 * L, -L * L], [-36, -3 * L, 36, -3 * L], [3 * L, -L * L, -3 * L, 4 * L * L]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += k + kg - 0.5 * om ** 2 * cg ** 2 * m   # + centrifugal stiffening, - partial spin softening
        M[np.ix_(idx, idx)] += m
    K, M = K[2:, 2:], M[2:, 2:]                                # clamped root
    w2 = np.linalg.eigvals(np.linalg.solve(M, K)); w2 = np.sort(np.real(w2[np.real(w2) > 0]))
    return [math.sqrt(v) / (2 * math.pi) for v in w2[:nmodes]]

def blade_campbell(s, Zr, Zn):
    if np is None: return None
    Ns = [0, 10e3, 20e3, 30e3, 40e3, 50e3, 60e3, 65e3, 72e3, 78e3]
    F = [blade_modes(s, Zr, n) for n in Ns]
    EOs = list(range(1, 11)) + [Zn, 21, 2 * Zn]
    cross = []
    for mi in range(2):
        f = [row[mi] for row in F]
        for eo in EOs:
            for (n0, f0), (n1, f1) in zip(zip(Ns[:-1], f[:-1]), zip(Ns[1:], f[1:])):
                g0, g1 = f0 - eo * n0 / 60, f1 - eo * n1 / 60
                if g0 * g1 <= 0 and n1 > 0:
                    nc = n0 + (n1 - n0) * g0 / (g0 - g1)
                    cross.append(dict(mode='1F' if mi == 0 else '2F', EO=eo, rpm=nc,
                                      in_continuous_range=N_MIN_CONT <= nc <= N_GOV, in_band_45_65k=45e3 <= nc <= 65e3))
    return dict(N=Ns, f=F, crossings=cross)

# ---------------------------------------------------------------------------------------------------------------
# 8. rotor axial thrust
# ---------------------------------------------------------------------------------------------------------------
P_BUF = 1.15e5        # buffer air between the hot labyrinth and the B1 oil seal (compressor-delivery bleed, orifice)
P_BC = 1.015e5        # bearing chambers / PMG cavity (breather to the oil tank, PT-709 <= 100 mbar g)
R_SEAL = dict(rim_front=30.0, rim_rear=27.0, lab=14.0, oil1=17.0, pmg1=17.0, pmg2=15.0)

def thrust(s, scale=1.0):
    r = lambda mm: mm * 1e-3
    K = s['W'] / OMEGA(N_DES); rho2 = s['rho2']; rm2 = s['rows'][1]['r2']
    p2h = s['p2'] - 0.5 * rho2 * K ** 2 * (1 / r(GEO['rot_hub_le']) ** 2 - 1 / rm2 ** 2)   # free-vortex radial equilibrium
    p_cf, p_cb = p2h, s['p3']
    A_gp = 0.5 * (s['A2'] + s['A3'])
    F_bl = (s['p2'] - s['p3']) * A_gp + MG * (s['Cx2'] - s['Cx3'])
    F_disk = (p_cf - p_cb) * math.pi * r(0.5 * (R_SEAL['rim_front'] + R_SEAL['rim_rear'])) ** 2
    F_lab = (p_cb - P_BUF) * math.pi * r(R_SEAL['lab']) ** 2
    F_oil = (P_BUF - P_BC) * math.pi * r(R_SEAL['oil1']) ** 2
    F = (F_bl + F_disk) * scale + F_lab + F_oil
    return dict(p_front_cavity=p_cf, p_back_cavity=p_cb, F_blades=F_bl, F_disk=F_disk, F_lab=F_lab, F_oil_seal=F_oil, F_net=F)

# ---------------------------------------------------------------------------------------------------------------
# 9. PMG: 2-pole surface-PM, SmCo + CF sleeve, 24 slots distributed winding (analytic sizing)
# ---------------------------------------------------------------------------------------------------------------
PMG = dict(P_out=30e3, N=N_DES, poles=2, Qs=24, pitch=10, z_slot=7, E_LL=360.0,
           r_shaft=15.0, h_mag=7.0, t_sleeve=3.0, g_mech=1.5, tooth_tip=1.0, wedge=1.0, b_tooth=3.0, b_open=2.0,
           Br20=1.06, aBr=-0.00035, T_mag=130.0, mu_r=1.05, Hcj20=1500e3, aHcj=-0.0025,
           J=7.0, fill=0.38, B_yoke=1.30, k_fe=0.95, T_wind=120.0,
           # core loss model fitted to 0.10 mm NO10 Si-steel: P(1T,400Hz)=9 W/kg, P(1T,1kHz)=25 W/kg; build factor 1.5
           kh=0.02083, ke=4.167e-6, build=1.5, rho_fe=7650.0,
           T_gly_in=40.0, gly_lpm=8.0)

def b_gap_2pole(Rr, Rm, Rs, Br, mur):
    """fundamental radial B at the stator bore, parallel-magnetised 2-pole ring on an iron shaft, iron stator (exact 2-D)"""
    a = Rm - Rr ** 2 / Rm; b = Rm - Rs ** 2 / Rm
    return 2 * Br / ((1 + Rs ** 2 / Rm ** 2) + mur * (abs(b) / a) * (1 + Rr ** 2 / Rm ** 2))

def pmg_design(gly_in=None):
    p = PMG; f = p['N'] / 60 * p['poles'] / 2; w = 2 * math.pi * f
    Rr = p['r_shaft']; Rm = Rr + p['h_mag']; Rsl = Rm + p['t_sleeve']; Rs = Rsl + p['g_mech']
    Br = p['Br20'] * (1 + p['aBr'] * (p['T_mag'] - 20))
    tau_s = 2 * math.pi * Rs / p['Qs']
    g_mag = (Rs - Rm) + p['h_mag'] / p['mu_r']
    gam = (p['b_open'] / g_mag) ** 2 / (5 + p['b_open'] / g_mag); kc = tau_s / (tau_s - gam * g_mag)
    B1 = b_gap_2pole(Rr, Rm, Rs, Br, p['mu_r']) / kc
    q = p['Qs'] / (3 * p['poles']); alpha = 2 * math.pi * p['poles'] / 2 / p['Qs']
    kd = math.sin(q * alpha / 2) / (q * math.sin(alpha / 2)); kp = math.sin(math.pi / 2 * p['pitch'] / (p['Qs'] / p['poles']))
    kw = kd * kp
    Nph = p['Qs'] * p['z_slot'] / (3 * 2)                        # double layer, 1 parallel path
    E_ph = p['E_LL'] / math.sqrt(3)
    L = E_ph / (4.44 * f * Nph * kw * B1 * 2 * Rs * 1e-3)
    L_stk = round(L * 1e3)                                       # mm
    Phi = B1 * 2 * Rs * 1e-3 * L_stk * 1e-3
    E_ph = 4.44 * f * Nph * kw * Phi; E_LL = E_ph * math.sqrt(3)
    # slot geometry
    r0 = Rs + p['tooth_tip'] + p['wedge']
    I = None
    # losses iterate (current depends on losses)
    P_em = p['P_out'] * 1.02
    for _ in range(5):
        I = P_em / (3 * E_ph)
        A_c = I / p['J']                                          # mm2 per conductor
        A_slot = p['z_slot'] * A_c / p['fill']
        ds = 1.0
        while (math.pi / p['Qs']) * ((r0 + ds) ** 2 - r0 ** 2) - p['b_tooth'] * ds < A_slot: ds += 0.1
        h_y = Phi / 2 / (p['B_yoke'] * L_stk * 1e-3 * p['k_fe']) * 1e3
        R_out = r0 + ds + h_y
        # copper
        r_ms = r0 + ds / 2; y_coil = p['pitch'] / p['Qs'] * 2 * math.pi * r_ms
        l_end = 1.2 * y_coil + 2 * 8.0; l_ax_end = 10.0 + 0.25 * y_coil
        MLT = 2 * L_stk + 2 * l_end
        rho_cu = 1.724e-8 * (1 + 0.00393 * (p['T_wind'] - 20))
        R_ph = rho_cu * Nph * MLT * 1e-3 / (A_c * 1e-6)
        k_ac = 1.10                                               # Litz 1 kHz + PWM ripple (32-40 kHz)
        P_cu = 3 * I ** 2 * R_ph * k_ac
        # iron
        B_t = B1 * tau_s / (p['b_tooth'] * p['k_fe'])
        V_t = p['Qs'] * p['b_tooth'] * ds * L_stk * 1e-9; V_y = math.pi * (R_out ** 2 - (r0 + ds) ** 2) * L_stk * 1e-9
        V_tip = (math.pi * (r0 ** 2 - Rs ** 2) - p['Qs'] * p['b_open'] * (r0 - Rs)) * L_stk * 1e-9
        pfe = lambda B: (p['kh'] * f + p['ke'] * f ** 2) * B ** 2
        m_t, m_y = (V_t + V_tip) * p['rho_fe'], V_y * p['rho_fe']
        P_fe = p['build'] * (m_t * pfe(B_t) + m_y * pfe(p['B_yoke']))
        # windage (Taylor-Couette gap, Bilgen-Boulos) + end faces + axial cooling throughflow
        rr = Rsl * 1e-3; gap = p['g_mech'] * 1e-3; T_air = 80 + 273.15; rho_a = 1.01e5 / (287 * T_air); mu = MU_AIR(T_air)
        om = OMEGA(p['N']); Re = rho_a * om * rr * gap / mu
        Cd = 0.065 * (gap / rr) ** 0.3 / Re ** 0.2
        L_rot = (L_stk + 8) * 1e-3
        P_wg = Cd * math.pi * rho_a * om ** 3 * rr ** 4 * L_rot
        Re_e = rho_a * om * rr ** 2 / mu; Cm = 0.0622 / Re_e ** 0.2
        P_we = 2 * 0.5 * Cm * rho_a * om ** 3 * rr ** 5
        m_air = 4.0e-3; P_wa = m_air * (om * rr) ** 2 * 0.5           # swirl given to the cooling air
        P_wind = 1.3 * (P_wg + P_we) + P_wa                            # 1.3: surface roughness / grooves
        P_rot_eddy = 40.0                                              # SmCo 8 x 8 segments, sleeve non-conductive (FEA)
        P_stray = 0.002 * p['P_out']
        P_loss = P_cu + P_fe + P_wind + P_rot_eddy + P_stray
        P_em = p['P_out'] + P_cu + P_fe + P_stray
    # inductance (synchronous: magnetising + 35 % leakage), short circuit, demagnetisation
    g_e = ((Rs - Rm) + p['h_mag'] / p['mu_r']) * 1e-3 * kc
    Lm = 6 / math.pi * 4e-7 * math.pi * (kw * Nph) ** 2 * Rs * 1e-3 * L_stk * 1e-3 / g_e
    Ls = 1.35 * Lm; X = w * Ls
    V_ph = math.hypot(E_ph - I * R_ph, X * I)
    I_sc = E_ph / math.hypot(X, R_ph)
    F_sc = 1.5 * 4 / math.pi * kw * Nph * math.sqrt(2) * I_sc / 2   # 3-phase MMF amplitude per pole (p = 1)
    H_demag = F_sc / (g_e + p['h_mag'] * 1e-3 / p['mu_r'])           # field driven through the magnet
    Hcj = p['Hcj20'] * (1 + p['aHcj'] * (p['T_mag'] - 20))
    # efficiency (electromagnetic, at terminals; bearings counted mechanically)
    P_shaft_in = p['P_out'] + P_loss
    eta = p['P_out'] / P_shaft_in
    # thermal: heat to glycol = stator losses + 50 % rotor losses + cone/heat-leak (from thermal section, ~ 0.2 kW)
    gly_in = p['T_gly_in'] if gly_in is None else gly_in
    Q_gly = P_cu + P_fe + P_stray + 0.5 * (P_wind + P_rot_eddy) + 200.0
    mdot = p['gly_lpm'] / 60 * 1.03 ; cpg = 3750.0
    dT_gly = Q_gly / (mdot * cpg)
    # jacket: helical channel 12 x 6 mm, 6 turns; h from Dittus-Boelter (30 % PG, 45 C)
    A_ch = 12e-3 * 6e-3; V_ch = mdot / 1030 / A_ch; Dh = 4 * A_ch / (2 * (12e-3 + 6e-3))
    nu_g, k_g, Pr = 1.6e-6, 0.48, 12.0
    Re_g = V_ch * Dh / nu_g; Nu = 0.023 * Re_g ** 0.8 * Pr ** 0.4; h_g = Nu * k_g / Dh
    A_wet = 6 * 2 * math.pi * (R_out + 3.0) * 1e-3 * 12e-3 * 1.5
    R_conv = 1 / (h_g * A_wet)
    R_cont = 1 / (5000 * 2 * math.pi * R_out * 1e-3 * L_stk * 1e-3)              # stator-jacket shrink fit
    R_yoke = math.log(R_out / (r0 + ds)) / (2 * math.pi * 28 * L_stk * 1e-3)      # laminations, radial k ~ 28
    R_slot = 0.6e-3 / (0.25 * p['Qs'] * 2 * (ds * 1e-3) * L_stk * 1e-3)           # liner + resin 0.6 mm, k 0.25
    T_gly_m = gly_in + dT_gly / 2
    T_yoke = T_gly_m + (P_cu + P_fe) * (R_conv + R_cont) + P_cu * R_yoke
    T_wind = T_yoke + P_cu * R_slot + 8.0                                             # + teeth conduction
    T_end_hot = T_wind + 15.0                                                         # end-winding hot spot (potted)
    dp_gly = 0.03 * (6 * 2 * math.pi * R_out * 1e-3) / Dh * 1030 * V_ch ** 2 / 2 + 3 * 1030 * V_ch ** 2 / 2
    return dict(f_e=f, poles=p['poles'], Qs=p['Qs'], q=q, kd=kd, kp=kp, kw=kw, N_ph=Nph, z_slot=p['z_slot'],
                R_shaft=Rr, R_mag=Rm, R_sleeve=Rsl, R_bore=Rs, R_slot_bottom=r0 + ds, R_out=R_out, L_stk=L_stk,
                slot_depth=ds, h_yoke=h_y, Br=Br, B1=B1, B_tooth=B_t, B_yoke=p['B_yoke'], kc=kc, Phi=Phi,
                E_ph=E_ph, E_LL=E_LL, I=I, A_cond=A_c, J=p['J'], A_slot=A_slot, R_ph=R_ph, MLT=MLT, l_end_ax=l_ax_end,
                elec_loading=6 * Nph * I / (2 * math.pi * Rs * 1e-3), shear_stress=None,
                P_cu=P_cu, P_fe=P_fe, m_teeth=m_t, m_yoke=m_y, P_wind=P_wind, P_rot_eddy=P_rot_eddy, P_stray=P_stray,
                P_loss=P_loss, eta=eta, Lm=Lm, Ls=Ls, X=X, V_ph=V_ph, I_sc=I_sc, H_demag=H_demag, Hcj_hot=Hcj,
                Q_glycol=Q_gly, gly_in=gly_in, dT_glycol=dT_gly, V_channel=V_ch, h_glycol=h_g, T_winding=T_wind,
                T_end_winding=T_end_hot, dp_glycol=dp_gly, torque=p['P_out'] / OMEGA(p['N']),
                m_air_gap=4.0e-3)

# ---------------------------------------------------------------------------------------------------------------
# 10. rotor sleeve: 1-D axisymmetric FE (shaft | segmented SmCo | hoop-wound CF), interference + speed + temperature
# ---------------------------------------------------------------------------------------------------------------
SLEEVE = dict(delta_d=0.180,          # diametral interference sleeve/magnet (mm), pressed or thermally assembled
              E_t=125e9, E_r=8e9, nu_tr=0.30, a_t=0.3e-6, a_r=30e-6, rho=1580.0, allow=1100e6, UTS_hoop=2200e6,
              T_ref=20.0)

def sleeve_fe(N, T_rotor=130.0, delta_d=None):
    if np is None: return None
    pm = PMG
    layers = [('shaft', 0.2e-3, pm['r_shaft'] * 1e-3, dict(Er=205e9, Et=205e9, nu=0.29, ar=12e-6, at=12e-6, rho=7850.0), 12),
              ('magnet', pm['r_shaft'] * 1e-3, (pm['r_shaft'] + pm['h_mag']) * 1e-3,
               dict(Er=150e9, Et=1.5e9, nu=0.01, ar=8e-6, at=11e-6, rho=8400.0), 10),   # segmented: ~no hoop stiffness
              ('sleeve', (pm['r_shaft'] + pm['h_mag']) * 1e-3, (pm['r_shaft'] + pm['h_mag'] + pm['t_sleeve']) * 1e-3,
               dict(Er=SLEEVE['E_r'], Et=SLEEVE['E_t'], nu=SLEEVE['nu_tr'] * SLEEVE['E_r'] / SLEEVE['E_t'],
                    ar=SLEEVE['a_r'], at=SLEEVE['a_t'], rho=SLEEVE['rho']), 10)]
    nodes = []; elems = []
    for li, (nm, ra, rb, mat, ne) in enumerate(layers):
        start = len(nodes)
        for k in range(ne + 1): nodes.append(ra + (rb - ra) * k / ne)
        for k in range(ne): elems.append((start + k, start + k + 1, mat, nm))
    nn = len(nodes); K = np.zeros((nn, nn)); Fv = np.zeros(nn)
    om = OMEGA(N); dT = T_rotor - SLEEVE['T_ref']
    gp = [(-1 / math.sqrt(3), 1.0), (1 / math.sqrt(3), 1.0)]
    for (i, j, mat, nm) in elems:
        ra, rb = nodes[i], nodes[j]; Lr = rb - ra
        # plane stress orthotropic: eps_r = s_r/Er - nu_tr s_t/Et ; eps_t = s_t/Et - nu_tr s_r/Et  (nu = nu_rt*Et/Er ...)
        Er, Et = mat['Er'], mat['Et']; nrt = mat['nu']                      # Poisson: eps_t = -nrt*s_r/Er
        S = np.array([[1 / Er, -nrt / Er], [-nrt / Er, 1 / Et]]); D = np.linalg.inv(S)
        eth = np.array([mat['ar'] * dT, mat['at'] * dT])
        for xi, wgt in gp:
            r = 0.5 * (ra + rb) + 0.5 * Lr * xi
            N1, N2 = (rb - r) / Lr, (r - ra) / Lr
            B = np.array([[-1 / Lr, 1 / Lr], [N1 / r, N2 / r]])
            dv = 2 * math.pi * r * 0.5 * Lr * wgt
            K[np.ix_([i, j], [i, j])] += B.T @ D @ B * dv
            Fv[[i, j]] += np.array([N1, N2]) * mat['rho'] * om ** 2 * r * dv + B.T @ D @ eth * dv
    # interfaces: duplicate nodes are coincident (layer ends) -> tie with penalty + interference at magnet/sleeve
    ties = []
    idx = 0
    for li, (nm, ra, rb, mat, ne) in enumerate(layers[:-1]):
        idx += ne + 1
        ties.append((idx - 1, idx, 0.0 if li == 0 else ((SLEEVE['delta_d'] if delta_d is None else delta_d) / 2 * 1e-3)))
    kp = 1e16
    for a, b, d in ties:            # u_b - u_a = d  (outer minus inner, interference = overlap -> outer pushed out)
        K[a, a] += kp; K[b, b] += kp; K[a, b] -= kp; K[b, a] -= kp
        Fv[a] -= kp * d; Fv[b] += kp * d
    # boundary: tiny inner radius node fixed radially (solid shaft centre)
    K[0, :] = 0; K[:, 0] = 0; K[0, 0] = 1.0; Fv[0] = 0.0
    u = np.linalg.solve(K, Fv)
    out = {}
    for (i, j, mat, nm) in elems:
        ra, rb = nodes[i], nodes[j]; Lr = rb - ra; r = 0.5 * (ra + rb)
        Er, Et = mat['Er'], mat['Et']; nrt = mat['nu']
        S = np.array([[1 / Er, -nrt / Er], [-nrt / Er, 1 / Et]]); D = np.linalg.inv(S)
        eps = np.array([(u[j] - u[i]) / Lr, 0.5 * (u[i] + u[j]) / r]) - np.array([mat['ar'] * dT, mat['at'] * dT])
        sr, st = D @ eps
        out.setdefault(nm, []).append((r, sr, st))
    p_ms = []
    for a, b, d in ties:
        p_ms.append(kp * (u[a] + d - u[b]) / (2 * math.pi * nodes[a]))      # contact pressure (+ = compression)
    sl = out['sleeve']; mg_ = out['magnet']
    return dict(N=N, T=T_rotor, sleeve_hoop_max=max(st for _, _, st in sl) / 1e6, sleeve_hoop_inner=sl[0][2] / 1e6,
                p_magnet_sleeve=p_ms[1] / 1e6, p_shaft_magnet=p_ms[0] / 1e6,
                magnet_sr_min=min(sr for _, sr, _ in mg_) / 1e6, magnet_sr_max=max(sr for _, sr, _ in mg_) / 1e6,
                u_sleeve_od_um=u[-1] * 1e6)

# ---------------------------------------------------------------------------------------------------------------
# 11. rotor layout (ENG x, mm): shaft profile, components, bearings - shared with the CAD
# ---------------------------------------------------------------------------------------------------------------
BRG1 = dict(name='B1', d=25.0, D=42.0, B=9.0, C=6.9e3, C0=3.7e3, dm=33.5, Z=16, Dw=4.763, alpha=15.0,
            desig='71905 class 25x42x9, 15 deg, hybrid Si3N4 balls, P4, outer-ring-guided PEEK/phenolic cage (locating)')
BRG2 = dict(name='B2', d=25.0, D=47.0, B=12.0, C=11.2e3, C0=5.9e3, dm=36.0, Z=14, Dw=6.35, alpha=15.0,
            desig='7005 class 25x47x12, 15 deg, hybrid Si3N4 balls, P4, outer-ring-guided cage (floating, spring preloaded)')
BRG = BRG1
SFD = dict(R=25.0, L=12.0, c=0.075, k_oring=2.0e6, m_cart=0.090)      # B1 damper journal R (OD 50), land, radial clearance
SFD2 = dict(R=27.5, L=12.0, c=0.075, k_oring=2.0e6, m_cart=0.110)     # B2 damper journal (OD 55)
F_PRELOAD = 200.0

def rotor_layout(pm):
    """axial positions of all rotor/stator items derived from the aero stations and the PMG stack length"""
    L = {}
    L['disk_front'] = X['rot_le'] - 1.3                 # rim front face (203.5)
    L['disk_rear_rim'] = X['rot_te'] + 1.7              # rim rear face (218.5)
    L['hub_front'] = L['disk_front'] - 4.5              # hub boss front face (199.0)
    L['hirth'] = L['hub_front'] + DISK['hub_h']         # Hirth face = sleeve front (222.0)
    L['nut0'] = L['hub_front'] - 6.0                    # nut 193-199
    L['stud0'] = L['nut0'] - 0.5                        # stud end
    L['sleeve1'] = L['hirth'] + 22.0                    # heat-dam sleeve end = B1 inner ring west face (244.0)
    L['b1_0'] = L['sleeve1']; L['b1_1'] = L['b1_0'] + BRG['B']; L['b1'] = 0.5 * (L['b1_0'] + L['b1_1'])
    L['shaft0'] = L['hirth'] + 1.0                      # shaft stub west face inside the sleeve
    L['shoulder1'] = L['b1_1']                          # step to the 30 mm body
    L['shield_front'] = L['b1_1'] + 13.0                # PMG front end-shield (B1 housing flange) 266
    L['stk0'] = L['shield_front'] + 10.0 + pm['l_end_ax'] + 2.0
    L['stk1'] = L['stk0'] + pm['L_stk']
    L['mag0'] = L['stk0'] - 2.0; L['mag1'] = L['stk1'] + 2.0
    L['slv0'] = L['mag0'] - 4.0; L['slv1'] = L['mag1'] + 4.0
    L['shield_rear'] = L['stk1'] + pm['l_end_ax'] + 2.0
    L['b2_0'] = L['shield_rear'] + 11.0; L['b2_1'] = L['b2_0'] + BRG2['B']; L['b2'] = 0.5 * (L['b2_0'] + L['b2_1'])
    L['nut2_0'] = L['b2_1'] + 1.0; L['nut2_1'] = L['nut2_0'] + 6.0
    L['tgt0'] = L['nut2_1'] + 2.0; L['tgt1'] = L['tgt0'] + 6.0
    L['shaft1'] = L['tgt1'] + 3.0
    L['cover1'] = L['shaft1'] + 14.0
    L['span'] = L['b2'] - L['b1']
    # shaft outer profile (x, r) - 34CrNiMo6; solid; M10x1.25 tapped 16 deep at the west end, M20x1 east
    sp = [(L['shaft0'], 0.0), (L['shaft0'], 10.0), (L['b1_0'], 10.0), (L['b1_0'], 12.5), (L['b1_1'], 12.5), (L['b1_1'], 15.0),
          (L['b2_0'] - 1.0, 15.0), (L['b2_0'] - 1.0, 12.5), (L['b2_1'] + 1.0, 12.5), (L['b2_1'] + 1.0, 10.0),
          (L['tgt0'], 10.0), (L['tgt0'], 9.0), (L['shaft1'], 9.0), (L['shaft1'], 0.0)]
    L['shaft_profile'] = sp
    return L

def rotor_components(s, Zr, bs, pm, L, massprops=None):
    """mass, x_cg, Ip, It (about own cg, transverse) of the rotor items; CAD-measured values override when present"""
    C = {}
    md, Ipd, Itd = disk_mass_props()
    mb = Zr * bs['m_blade']; Ipb = Zr * bs['Ip_blade']; Itb = 0.5 * Ipb
    x_disk = 0.5 * (L['hub_front'] + L['hirth']) * 0.4 + 0.5 * (L['disk_front'] + L['disk_rear_rim']) * 0.6
    C['FPT_blisk'] = (md + mb, x_disk, Ipd + Ipb, Itd + Itb)
    rho_n = IN718['rho']
    m_nut = rho_n * math.pi * (0.0075 ** 2 - 0.005 ** 2) * 0.006; C['FPT_nut'] = (m_nut, L['nut0'] + 3, 0.5 * m_nut * (0.0075 ** 2 + 0.005 ** 2), m_nut * 0.0075 ** 2 / 4)
    m_stud = rho_n * math.pi * 0.005 ** 2 * (L['shaft0'] + 16 - L['stud0']) * 1e-3
    C['tie_stud'] = (m_stud, 0.5 * (L['stud0'] + L['shaft0'] + 16), 0.5 * m_stud * 0.005 ** 2, m_stud * ((L['shaft0'] + 16 - L['stud0']) * 1e-3) ** 2 / 12)
    ls = (L['sleeve1'] - L['hirth']) * 1e-3; m_sl = rho_n * math.pi * (0.0135 ** 2 - 0.010 ** 2) * ls + rho_n * math.pi * (0.0175 ** 2 - 0.0135 ** 2) * 0.004
    C['heatdam_sleeve'] = (m_sl, 0.5 * (L['hirth'] + L['sleeve1']), m_sl * 0.0125 ** 2, m_sl * (0.0125 ** 2 / 2 + ls ** 2 / 12))
    for nm, xx, bb, ro_ in (('B1_inner', L['b1'], BRG1, 0.0145), ('B2_inner', L['b2'], BRG2, 0.0155)):
        m_ir = 7800 * math.pi * (ro_ ** 2 - 0.0125 ** 2) * bb['B'] * 1e-3 + 0.5 * bb['Z'] * 3200 * math.pi / 6 * (bb['Dw'] * 1e-3) ** 3
        C[nm] = (m_ir, xx, m_ir * ro_ ** 2, m_ir * (ro_ ** 2 / 2 + (bb['B'] * 1e-3) ** 2 / 12))
    Lm = (L['mag1'] - L['mag0']) * 1e-3; Rr, Rm, Rsl = pm['R_shaft'] * 1e-3, pm['R_mag'] * 1e-3, pm['R_sleeve'] * 1e-3
    m_mag = 8400 * math.pi * (Rm ** 2 - Rr ** 2) * Lm
    C['magnets'] = (m_mag, 0.5 * (L['mag0'] + L['mag1']), 0.5 * m_mag * (Rm ** 2 + Rr ** 2), m_mag * ((Rm ** 2 + Rr ** 2) / 4 + Lm ** 2 / 12))
    Ls_ = (L['slv1'] - L['slv0']) * 1e-3; m_sv = SLEEVE['rho'] * math.pi * (Rsl ** 2 - Rm ** 2) * Ls_
    m_er = 2 * 4430 * math.pi * (Rm ** 2 - Rr ** 2) * 0.004
    C['sleeve_endrings'] = (m_sv + m_er, 0.5 * (L['slv0'] + L['slv1']), m_sv * 0.5 * (Rsl ** 2 + Rm ** 2) + m_er * 0.5 * (Rm ** 2 + Rr ** 2),
                            (m_sv + m_er) * ((Rsl ** 2 + Rr ** 2) / 4 + Ls_ ** 2 / 12))
    m_nt = 7850 * math.pi * (0.016 ** 2 - 0.010 ** 2) * 0.006; C['B2_locknut'] = (m_nt, 0.5 * (L['nut2_0'] + L['nut2_1']), m_nt * 0.013 ** 2, m_nt * 0.013 ** 2 / 2)
    m_tg = 7850 * math.pi * (0.017 ** 2 - 0.009 ** 2) * 0.006 * 0.7; C['N2_target'] = (m_tg, 0.5 * (L['tgt0'] + L['tgt1']), m_tg * 0.013 ** 2, m_tg * 0.013 ** 2 / 2)
    # shaft (from its profile)
    m_sh = Ip_sh = 0.0; mx = 0.0; sp = L['shaft_profile']
    for (x0, r0), (x1, r1) in zip(sp[:-1], sp[1:]):
        if x1 > x0 and r0 == r1:
            dm = 7850 * math.pi * (r0 * 1e-3) ** 2 * (x1 - x0) * 1e-3; m_sh += dm; mx += dm * 0.5 * (x0 + x1); Ip_sh += 0.5 * dm * (r0 * 1e-3) ** 2
    C['shaft'] = (m_sh, mx / m_sh, Ip_sh, None)
    src = 'analytic'
    if massprops:
        for k, v in massprops.items():
            if k in C and v.get('mass_kg'):
                C[k] = (v['mass_kg'], v['x_cg_mm'], v['Ip_kgm2'], v['It_kgm2'] if C[k][3] is not None else None)
        src = 'CAD (cad_out/engine/E3/E3_massprops.json)'
    J = sum(c[2] for c in C.values()); m_tot = sum(c[0] for c in C.values())
    xcg = sum(c[0] * c[1] for c in C.values()) / m_tot
    return C, J, m_tot, xcg, src

# ---------------------------------------------------------------------------------------------------------------
# 12. bearings: loads, life, speed factor, friction, oil
# ---------------------------------------------------------------------------------------------------------------
def bearings(F_t, m_rot, xcg, L, N=N_DES, G_bal=2.5):
    om = OMEGA(N); g = 9.81
    a, b = L['b1'], L['b2']
    W1 = m_rot * g * (b - xcg) / (b - a); W2 = m_rot * g - W1
    e = G_bal * 1e-3 / om; Fu = m_rot * e * om ** 2
    Fr1, Fr2 = W1 + 0.5 * Fu, W2 + 0.5 * Fu
    Fa1, Fa2 = F_PRELOAD - F_t, F_PRELOAD                   # X arrangement: spring (at B2) pushes the shaft west, thrust east
    def P(Fr, Fa):
        e_ = 0.43; return Fr + 0 * Fa if Fa / max(Fr, 1e-6) <= e_ else 0.44 * Fr + 1.30 * Fa
    P1, P2 = P(Fr1, Fa1), P(Fr2, Fa2)
    L10 = lambda Pe, b=BRG1: (b['C'] / Pe) ** 3 * 1e6 / (N * 60)
    a_iso = 6.0                                             # hybrid, kappa ~ 2, filtration 6 um beta>=200 (ISO 281 a_ISO estimate)
    nu = 7.0                                                # cSt, MIL-PRF-23699 class ester at ~ 90 C
    f0 = 1.5                                                # controlled low-flow oil jet (under-race + side jet)
    M0 = lambda b: 1e-7 * f0 * (nu * N) ** (2 / 3) * b['dm'] ** 3   # N mm
    f1 = 0.001
    P_f1 = (M0(BRG1) + f1 * P1 * BRG1['dm']) * 1e-3 * om; P_f2 = (M0(BRG2) + f1 * P2 * BRG2['dm']) * 1e-3 * om
    # ball centrifugal force and minimum axial load (skid check) for B1
    mball = 3200 * math.pi / 6 * (BRG1['Dw'] * 1e-3) ** 3; om_c = 0.42 * om
    Fc = mball * om_c ** 2 * BRG1['dm'] / 2e3
    Fa_min = BRG1['Z'] * Fc * math.tan(math.radians(BRG1['alpha'])) * 0.5    # rule of thumb: half the ball centrifugal lift
    return dict(W1=W1, W2=W2, F_unbal=Fu, Fr1=Fr1, Fr2=Fr2, Fa1=Fa1, Fa2=Fa2, P1=P1, P2=P2, L10h_1=L10(P1), L10h_2=L10(P2, BRG2),
                a_ISO=a_iso, Lnm_1=a_iso * L10(P1), Lnm_2=a_iso * L10(P2, BRG2), ndm_60k=N * BRG2['dm'], ndm_72k=N_OS * BRG2['dm'],
                P_fric_B1=P_f1, P_fric_B2=P_f2, F_ball_centrifugal=Fc, Fa_min=Fa_min, B1_min_load_ok=Fa1 >= max(Fa_min, 40.0))

# ---------------------------------------------------------------------------------------------------------------
# 13. rotordynamics: beam FE + lumped disks + SFD supports (bearing - cartridge - O-ring centring || squeeze film)
# ---------------------------------------------------------------------------------------------------------------
E_SH, RHO_SH = 205e9, 7850.0
K_BRG = 30e6                                       # hybrid 71905 at 180 N preload, radial (N/m)
MU_OIL = 7.0e-6 * 950                               # Pa s at ~ 90 C

def sfd_damping(sf=None):
    sf = sf or SFD
    return math.pi * MU_OIL * sf['R'] * 1e-3 * (sf['L'] * 1e-3) ** 3 / (2 * (sf['c'] * 1e-3) ** 3)   # short bearing, pi-film

def beam_sections(L, pm):
    """(x0, x1, r_outer_structural, r_inner, added mass per length, added rotary inertia per length (transverse), added polar per length)"""
    segs = []
    # clamped front stack: nut | disk hub (r 15 / bore 5.25 + stud r 5) | Hirth | sleeve (r 13.5 on stub r 10)
    segs.append((L['stud0'], L['hub_front'], 5.0, 0.0, IN718['rho'] * math.pi * (0.0075 ** 2 - 0.005 ** 2), 0, 0))
    segs.append((L['hub_front'], L['hirth'], 13.0, 0.0, 0.0, 0, 0))              # disk hub + stud (eq. r 13, 70 % of r 15 stiffness)
    segs.append((L['hirth'], L['shaft0'], 11.0, 0.0, 0.0, 0, 0))                 # Hirth joint (compliant)
    segs.append((L['shaft0'], L['b1_0'], 11.5, 0.0, 0.0, 0, 0))                  # stub r 10 + clamped sleeve (eq. r 11.5)
    for (x0, r0), (x1, r1) in zip(L['shaft_profile'][:-1], L['shaft_profile'][1:]):
        if x1 > x0 and x0 >= L['b1_0'] - 1e-6 and r0 == r1:
            segs.append((x0, x1, r0, 0.0, 0.0, 0, 0))
    # PM rotor added mass (magnets + sleeve + end rings): no bending stiffness (segmented magnets, hoop-wound sleeve)
    Rr, Rm, Rsl = pm['R_shaft'] * 1e-3, pm['R_mag'] * 1e-3, pm['R_sleeve'] * 1e-3
    mpl = 8400 * math.pi * (Rm ** 2 - Rr ** 2) + SLEEVE['rho'] * math.pi * (Rsl ** 2 - Rm ** 2)
    ipl = 8400 * math.pi * (Rm ** 4 - Rr ** 4) / 4 + SLEEVE['rho'] * math.pi * (Rsl ** 4 - Rm ** 4) / 4
    out = []
    for (x0, x1, r, ri, ma, ia, pa) in segs:
        cuts = sorted(set([x0, x1] + [v for v in (L['slv0'], L['slv1']) if x0 < v < x1]))
        for a, b in zip(cuts[:-1], cuts[1:]):
            inside = L['slv0'] <= 0.5 * (a + b) <= L['slv1']
            out.append((a, b, r, ri, ma + (mpl if inside else 0.0), ia + (ipl if inside else 0.0), 2 * (ia + (ipl if inside else 0.0))))
    return out

def build_rotor(L, pm, comps, k_brg=K_BRG, k_sq=None, c_sfd=None, k_ump=None):
    segs = beam_sections(L, pm)
    pts = sorted(set([round(v, 3) for s_ in segs for v in s_[:2]] + [round(L['b1'], 3), round(L['b2'], 3)] +
                     [round(c[1], 3) for c in comps.values()]))
    xs = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil((b - a) / 5.0))); xs += [a + (b - a) * k / n for k in range(n)]
    xs = np.array(xs + [pts[-1]]) * 1e-3
    nn = len(xs); nd = 2 * nn + 2                       # + 2 cartridge translational DOFs
    K = np.zeros((nd, nd)); M = np.zeros((nd, nd)); P = np.zeros((nd, nd)); Cm = np.zeros((nd, nd)); Ks = np.zeros((nd, nd))
    def seg_at(xm):
        for s_ in segs:
            if s_[0] <= xm <= s_[1]: return s_
        return None
    for e in range(nn - 1):
        Le = xs[e + 1] - xs[e]; xm = 0.5 * (xs[e] + xs[e + 1]) * 1e3
        s_ = seg_at(xm)
        if s_ is None: continue
        r, ri, ma, ia, pa = s_[2] * 1e-3, s_[3] * 1e-3, s_[4], s_[5], s_[6]
        A = math.pi * (r ** 2 - ri ** 2); I = math.pi * (r ** 4 - ri ** 4) / 4
        E = E_SH if xm > L['shaft0'] else interp(IN718['E'], 450) * 1e9
        rho = RHO_SH if xm > L['shaft0'] else IN718['rho']
        k = E * I / Le ** 3 * np.array([[12, 6 * Le, -12, 6 * Le], [6 * Le, 4 * Le * Le, -6 * Le, 2 * Le * Le], [-12, -6 * Le, 12, -6 * Le], [6 * Le, 2 * Le * Le, -6 * Le, 4 * Le * Le]])
        mt = (rho * A + ma) * Le / 420 * np.array([[156, 22 * Le, 54, -13 * Le], [22 * Le, 4 * Le * Le, 13 * Le, -3 * Le * Le], [54, 13 * Le, 156, -22 * Le], [-13 * Le, -3 * Le * Le, -22 * Le, 4 * Le * Le]])
        Irot = rho * I + ia
        mr = Irot / (30 * Le) * np.array([[36, 3 * Le, -36, 3 * Le], [3 * Le, 4 * Le * Le, -3 * Le, -Le * Le], [-36, -3 * Le, 36, -3 * Le], [3 * Le, -Le * Le, -3 * Le, 4 * Le * Le]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += k; Ks[np.ix_(idx, idx)] += k
        M[np.ix_(idx, idx)] += mt + mr; P[np.ix_(idx, idx)] += 2 * mr
    node = lambda xmm: int(np.argmin(abs(xs - xmm * 1e-3)))
    for nm, (m, x, Ip, It) in comps.items():
        if nm == 'shaft' or nm in ('magnets', 'sleeve_endrings'): continue       # shaft and PM rotor are distributed
        i = node(x); M[2 * i, 2 * i] += m; M[2 * i + 1, 2 * i + 1] += (It or 0.0); P[2 * i + 1, 2 * i + 1] += Ip
    # supports: shaft node --k_brg-- cartridge (m_cart) --(k_oring || c_sfd)-- ground
    for j, (xb, sf) in enumerate(((L['b1'], SFD), (L['b2'], SFD2))):
        i = node(xb); h = 2 * nn + j
        kq = k_sq if k_sq is not None else sf['k_oring']
        cs = (sfd_damping(sf) if c_sfd is None else c_sfd)
        K[2 * i, 2 * i] += k_brg; K[h, h] += k_brg + kq; K[2 * i, h] -= k_brg; K[h, 2 * i] -= k_brg
        M[h, h] += sf['m_cart']; Cm[h, h] += cs
    # unbalanced magnetic pull (negative stiffness) spread over the magnet nodes
    if k_ump is None: k_ump = ump_stiffness(pm)
    if k_ump == 'off': k_ump = 0.0
    mag_nodes = [i for i in range(nn) if L['mag0'] <= xs[i] * 1e3 <= L['mag1']]
    for i in mag_nodes: K[2 * i, 2 * i] -= k_ump / len(mag_nodes)
    return xs, K, M, P, Cm, Ks, node

def ump_stiffness(pm):
    g_e = (pm['R_bore'] - pm['R_mag'] + PMG['h_mag'] / PMG['mu_r']) * 1e-3
    return math.pi * pm['R_bore'] * 1e-3 * pm['L_stk'] * 1e-3 * pm['B1'] ** 2 / (4e-7 * math.pi * g_e) * 0.5

def damped_modes(K, M, P, Cm, Omega):
    n = K.shape[0]
    Minv = np.linalg.inv(M)
    A = np.block([[np.zeros((n, n)), np.eye(n)], [-Minv @ K, -Minv @ (Cm - 1j * Omega * P)]])
    lam, V = np.linalg.eig(A)
    return lam, V[:n, :]

def rotordynamics(L, pm, comps):
    if np is None: return None
    xs, K, M, P, Cm, Ks, node = build_rotor(L, pm, comps)
    nn = len(xs)
    Ns = np.linspace(0, 110000, 111)
    camp = []
    for Nn in Ns:
        lam, V = damped_modes(K, M, P, Cm, OMEGA(Nn))
        keep = []
        for k in range(len(lam)):
            w = lam[k].imag; s_ = lam[k].real
            if abs(w) < 1.0 or abs(w) / (2 * math.pi) > 4000: continue
            v = V[:, k]; vs = v[:2 * nn]
            se_shaft = float(np.real(np.conj(vs) @ Ks[:2 * nn, :2 * nn] @ vs)); se_tot = float(np.real(np.conj(v) @ K @ v))
            zeta = -s_ / abs(lam[k])
            disp = np.abs(v[0:2 * nn:2]); imax = int(np.argmax(disp))
            keep.append(dict(f=w / (2 * math.pi), zeta=zeta, bend=se_shaft / max(abs(se_tot), 1e-30), xmax=xs[imax] * 1e3,
                             d1=float(np.abs(v[2 * node(L['b1'])])), d2=float(np.abs(v[2 * node(L['b2'])])),
                             ddisk=float(np.abs(v[2 * node(comps['FPT_blisk'][1])]))))
        keep.sort(key=lambda d: abs(d['f']))
        camp.append((Nn, keep))
    # forward synchronous criticals: f(Omega) - Omega/60 sign change, per forward mode index
    crit = []
    nf = min(len([d for d in camp[0][1] if d['f'] > 0]), 6)
    for mi in range(nf):
        prev = None
        for Nn, modes in camp:
            fw = sorted([d for d in modes if d['f'] > 0], key=lambda d: d['f'])
            if len(fw) <= mi: continue
            d = fw[mi]; gfun = d['f'] - Nn / 60
            if prev is not None and prev[1] > 0 >= gfun:
                Nc = prev[0] + (Nn - prev[0]) * prev[1] / (prev[1] - gfun)
                crit.append(dict(mode=mi + 1, rpm=Nc, zeta=d['zeta'], logdec=2 * math.pi * d['zeta'] / math.sqrt(max(1 - d['zeta'] ** 2, 1e-9)),
                                 shaft_strain_energy=d['bend'], x_max_mm=d['xmax'],
                                 type='bending' if d['bend'] > 0.5 else ('conical' if d['ddisk'] > 1.5 * max(d['d2'], 1e-30) else 'cylindrical/rigid')))
            prev = (Nn, gfun)
    # undamped free-free first bending (support stiffness -> 0) as an upper reference, and stiff-support case
    xs0, K0, M0_, P0_, C0_, Ks0, _ = build_rotor(L, pm, comps, k_brg=K_BRG, k_sq=1e3, c_sfd=0.0, k_ump='off')
    w2 = np.linalg.eigvals(np.linalg.solve(M0_, K0)); w2 = np.sort(np.real(w2[np.real(w2) > (2 * math.pi * 50) ** 2]))
    ff = [math.sqrt(v) * 60 / (2 * math.pi) for v in w2[:4]]                  # non-spinning, supports ~free
    xs1, K1, M1, P1, C1, Ks1, _ = build_rotor(L, pm, comps, k_brg=K_BRG, k_sq=1e10, c_sfd=0.0)
    w2 = np.linalg.eigvals(np.linalg.solve(M1 - P1, K1)); w2 = np.sort(np.real(w2[np.real(w2) > 1.0]))
    rigid = [math.sqrt(v) * 60 / (2 * math.pi) for v in w2[:3]]
    return dict(campbell=[(float(Nn), [(m['f'], m['zeta'], m['bend']) for m in modes]) for Nn, modes in camp],
                criticals=crit, free_free_rpm=ff, rigid_housing_criticals_rpm=rigid,
                k_brg=K_BRG, k_oring=SFD['k_oring'], c_sfd=sfd_damping(), c_sfd2=sfd_damping(SFD2), k_ump=ump_stiffness(pm), nodes=len(xs))

def unbalance_response(L, pm, comps, G_bal=2.5, phase=0.0):
    """G2.5 unbalance at the blisk and the PM rotor (equal e), amplitude at disk / bearings vs speed"""
    if np is None: return None
    xs, K, M, P, Cm, Ks, node = build_rotor(L, pm, comps)
    nd = K.shape[0]; out = []
    md = comps['FPT_blisk'][0]; mp = comps['magnets'][0] + comps['sleeve_endrings'][0]
    for Nn in np.linspace(2000, 80000, 157):
        Om = OMEGA(Nn); e = G_bal * 1e-3 / OMEGA(N_DES)
        F = np.zeros(nd, dtype=complex)
        F[2 * node(comps['FPT_blisk'][1])] += md * e * Om ** 2
        F[2 * node(comps['magnets'][1])] += mp * e * Om ** 2 * np.exp(1j * phase)
        Z = K - Om ** 2 * M + Om ** 2 * P + 1j * Om * Cm
        q = np.linalg.solve(Z, F)
        nn = len(xs)
        out.append(dict(N=float(Nn), disk_um=float(abs(q[2 * node(comps['FPT_blisk'][1])]) * 1e6),
                        b1_um=float(abs(q[2 * node(L['b1'])]) * 1e6), b2_um=float(abs(q[2 * node(L['b2'])]) * 1e6),
                        mag_um=float(abs(q[2 * node(comps['magnets'][1])]) * 1e6),
                        sfd1_ecc=float(abs(q[2 * nn]) / (SFD['c'] * 1e-3)), sfd2_ecc=float(abs(q[2 * nn + 1]) / (SFD['c'] * 1e-3)),
                        Fb1=float(abs(K_BRG * (q[2 * node(L['b1'])] - q[2 * nn]))), Fb2=float(abs(K_BRG * (q[2 * node(L['b2'])] - q[2 * nn + 1])))))
    return out

# ---------------------------------------------------------------------------------------------------------------
# 14. thermal barrier FPT -> B1 / PMG, oil and glycol heat loads
# ---------------------------------------------------------------------------------------------------------------
def thermal_barrier(brg):
    T_bore = T_BORE_C + 273.15; T_oil = 90 + 273.15
    # shaft path: Hirth contact (50 % tooth contact, h_c 3000) -> IN718 sleeve (22 mm) -> steel stub -> oil-jet cooled zone
    A_h = math.pi * (0.015 ** 2 - 0.009 ** 2) * 0.5; R_h = 1 / (3000 * A_h)
    R_sl = 0.022 / (interp(IN718['k'], 350) * math.pi * (0.0135 ** 2 - 0.010 ** 2))
    R_st = 0.010 / (40 * math.pi * 0.010 ** 2)
    R_oil = 1 / (3000 * math.pi * 0.030 * 0.015)
    Q_shaft = (T_bore - T_oil) / (R_h + R_sl + R_st + R_oil)
    T_b1_ir = T_oil + Q_shaft * R_oil + 0.5 * brg['P_fric_B1'] * 0.05 - 273.15
    # disk rear face -> heat shield (1.4828 0.8 mm + 3 mm ceramic paper k 0.08) -> B1 housing nose
    A_sh = math.pi * (0.026 ** 2 - 0.0145 ** 2); Q_shield = 0.08 * A_sh * (800 - 420) / 0.003
    # diffuser hub bell (hot, 883 K) -> 3 mm ceramic paper + 1.5 mm air -> B1 housing (~ 400 K)
    A_bell = 2 * math.pi * 0.034 * 0.032; Q_bell = (883 - 400) / (0.003 / (0.08 * A_bell) + 0.0015 / (0.045 * A_bell))
    # collector -> PMG support cone (IN625, t 1.5, L 50) + mica spacer (k 0.5, 3 mm)
    A_cone = 2 * math.pi * 0.090 * 0.0015
    R_cone = 0.050 / (16 * A_cone) + 0.003 / (0.5 * math.pi * (0.090 ** 2 - 0.080 ** 2))
    Q_cone = (883 - 320) / R_cone
    Q_B1_oil = Q_shaft + Q_shield + Q_bell + brg['P_fric_B1']
    Q_B2_oil = brg['P_fric_B2'] + 30.0
    cp_o, rho_o, dT_o = 1950.0, 950.0, 20.0
    lpm = lambda Q: Q / (cp_o * dT_o) / rho_o * 60e3
    return dict(Q_shaft_W=Q_shaft, T_B1_inner_ring_C=T_b1_ir, Q_heat_shield_W=Q_shield, Q_hub_bell_W=Q_bell, Q_cone_W=Q_cone,
                Q_B1_oil_W=Q_B1_oil, Q_B2_oil_W=Q_B2_oil, oil_B1_lpm=lpm(Q_B1_oil) + 0.10, oil_B2_lpm=lpm(Q_B2_oil) + 0.10,
                oil_total_lpm=lpm(Q_B1_oil) + lpm(Q_B2_oil) + 0.20, oil_dT=dT_o, oil_supply_barg=2.5)

# ---------------------------------------------------------------------------------------------------------------
# 15. seals (labyrinth leakage, Martin/Egli) and buffer air
# ---------------------------------------------------------------------------------------------------------------
def labyrinth(p_up, p_dn, T, r_mm, c_mm, n_teeth, alpha=0.70, carry=1.15):
    A = 2 * math.pi * r_mm * 1e-3 * c_mm * 1e-3
    pr = p_dn / p_up
    return alpha * carry * A * p_up * math.sqrt(max(1 - pr ** 2, 0) / (287 * T * (n_teeth - math.log(pr))))

def seals(th):
    p_cb = th['p_back_cavity']
    m_lab_hot = labyrinth(P_BUF, p_cb, 450, R_SEAL['lab'], 0.15, 4) if P_BUF > p_cb else -labyrinth(p_cb, P_BUF, 870, R_SEAL['lab'], 0.15, 4)
    m_oil1 = labyrinth(P_BUF, P_BC, 420, R_SEAL['oil1'], 0.12, 3)
    m_rim_rear = labyrinth(th['p_front_cavity'], p_cb, 880, R_SEAL['rim_front'], 0.5, 1)
    return dict(buffer_to_back_cavity_gs=m_lab_hot * 1e3, buffer_to_B1_chamber_gs=m_oil1 * 1e3,
                buffer_total_gs=(abs(m_lab_hot) + m_oil1) * 1e3, front_rim_leak_gs=m_rim_rear * 1e3,
                buffer_orifice_mm=math.sqrt(4 / math.pi * (abs(m_lab_hot) + m_oil1) / (0.62 * 0.0404 * 3.0e5 / math.sqrt(440.0))) * 1e3)

# ---------------------------------------------------------------------------------------------------------------
# 16. main: run everything, report, plots, JSON for the CAD
# ---------------------------------------------------------------------------------------------------------------
def hdr(t):
    print('\n' + t + '\n' + '-' * len(t))

def main():
    R = {}
    hdr('E3 boundary conditions')
    print('GG exit (sim/gg_turbine_design.json): m %.4f kg/s, T0 %.1f K (%.0f C), P0 %.0f Pa, Cx %.0f m/s, hub r %.1f / casing r %.2f mm'
          % (MG, T00, T00 - 273.15, P00, CX0, R_H0, R_T0))
    print('cycle (life_study.point 115k/800C/15C/50m): P_shaft %.2f kW, T_hot %.0f C, back-pressure at H1 %.0f Pa (%.4f bar)'
          % (P_SHAFT_CYCLE / 1e3, T_HOT_CYCLE - 273.15, P_EXIT, P_EXIT / 1e5))
    # cycle's own FPT inlet pressure (eta_t 0.82 vs E1 meanline eta_tt 0.809)
    T3c = 1073.15; dhc = GG['dh']
    P4_cyc = GG['P01'] * ((T3c - dhc / (CP * 0.82)) / T3c) ** (1 / EX) * 0.985
    print('note: cycle FPT inlet P4 = %.0f Pa (GG eta_t 0.82); E1 meanline gives P03 x 0.985 = %.0f Pa (eta_tt %.3f) -> %.2f %% lower'
          % (P4_cyc, P01_CYCLE, GG['eta_tt'], (1 - P01_CYCLE / P4_cyc) * 100))
    # ---- interduct
    idc = interduct(); R['interduct'] = idc
    hdr('1. Interduct (outward S-duct, stationary hub cone over the GG nut)')
    print('x %.1f -> %.1f mm (L %.0f), hub r %.1f -> %.1f, casing r %.2f -> %.1f; AR %.3f; L/h0 %.2f; dRmean/L %.3f; max wall slope %.1f deg'
          % (X['id0'], X['ngv_le'], idc['L_mm'], R_H0, GEO['ngv_hub_le'], R_T0, GEO['ngv_tip_le'], idc['AR'], idc['L_over_h0'],
             idc['dRmean_over_L'], idc['max_wall_slope_deg']))
    print('equivalent cone angle 2theta %.2f deg (limit 8), local max %.1f deg (limit 12) -> %s'
          % (idc['two_theta_eq_deg'], idc['two_theta_local_max_deg'], 'no separation expected' if idc['ok_separation'] else 'CHECK'))
    print('M %.3f -> %.3f, V %.0f -> %.0f m/s; loss K = friction %.3f + diffusion %.3f + curvature %.3f + lip cavity %.3f = %.3f q_in'
          % (idc['M_in'], idc['M_out'], idc['V_in'], idc['V_out'], idc['K_friction'], idc['K_diffusion'], idc['K_curvature'], idc['K_cavity'], idc['K_total']))
    print('total-pressure loss %.0f Pa = %.2f %% of P0 (cycle allowance 1.5 %%) -> FPT inlet P01 %.0f Pa'
          % (idc['dP0'], idc['dP0_over_P0'] * 100, idc['P01']))
    # ---- stage
    Zn, Zr = blade_counts(idc['P01'], idc['T01'])
    s = solve_stage(idc['P01'], idc['T01'], Zn=Zn, Zr=Zr); R['stage'] = s; R['Z_ngv'] = Zn; R['Z_rot'] = Zr
    hdr('2. FPT single-stage axial, %.0fk rpm (counter-rotating to the GG)' % (N_DES / 1e3))
    print('NGV %d vanes (SLM IN718), rotor %d blades (IN718 blisk) - coprime with each other and with GG 21/29' % (Zn, Zr))
    print('U_mean %.0f m/s (r_m2 %.1f mm), U/C0 %.3f, psi %.3f, phi %.3f, Zweifel NGV %.2f / rotor %.2f'
          % (s['U2m'], s['rows'][1]['r2'] * 1e3, s['U_over_C0'], s['psi'], s['phi'], s['Zw_ngv'], s['Zw_rot']))
    print('%-5s %6s %6s %7s %7s %7s %7s %6s %6s %6s %7s' % ('', 'r2 mm', 'U2', 'alpha2', 'beta2', 'beta3', 'R', 'M2', 'Mw2', 'Mw3', 'T0rel C'))
    for rw in s['rows']:
        print('%-5s %6.1f %6.0f %7.1f %7.1f %7.1f %7.3f %6.3f %6.3f %6.3f %7.0f' % (rw['name'], rw['r2'] * 1e3, rw['U2'], rw['alpha2'], rw['beta2'],
              rw['beta3'], rw['reaction'], rw['M2'], rw['Mw2'], rw['Mw3'], rw['T0rel2'] - 273.15))
    print('Cx2 %.0f, Cx3 %.0f m/s; exit swirl 0 (design); p2 %.0f, p3 %.0f, P03 %.0f Pa; T03 %.1f K (%.0f C)'
          % (s['Cx2'], s['Cx3'], s['p2'], s['p3'], s['P03'], s['T03'], s['T03'] - 273.15))
    print('loss zeta NGV %.3f (Re %.0f) | rotor %.3f (Re %.0f) | tip leakage %.1f %% | disk friction %.0f W'
          % (s['zeta_ngv'], s['Re_ngv'], s['zeta_rot'], s['Re_rot'], s['tip_frac'] * 100, s['P_df']))
    print('loss breakdown (kJ/kg): NGV %.2f, rotor %.2f, tip %.2f, disk %.2f, exit (after diffuser+collector) %.2f ; dh_is,ts %.2f'
          % (s['loss_ngv'] / 1e3, s['loss_rot'] / 1e3, s['loss_tip'] / 1e3, s['loss_df'] / 1e3, s['loss_exit'] / 1e3, s['dh_is_ts'] / 1e3))
    print('exhaust: axial-radial diffuser AR %.2f, Cp %.3f; plenum V %.0f m/s; DN250 V %.1f m/s; static at H1 %.0f Pa'
          % (s['AR_diff'], s['Cp_diff'], s['V_plenum'], s['V5'], s['p5']))
    P_aero = MG * s['W_shaft_aero']
    print('ETA_TT (stage) %.3f | ETA_TS (P01 -> H1 static, incl. diffuser+collector) %.3f (target >= 0.78)' % (s['eta_tt'], s['eta_ts']))
    # off-design: speed sweep at fixed NGV flow (incidence penalty) - quick U/C0 curve
    sweep = []
    for Nn in (40e3, 45e3, 50e3, 55e3, 60e3, 65e3, 70e3):
        st = stage(idc['P01'], idc['T01'], s['W'], N=Nn, Zn=Zn, Zr=Zr)
        # Euler work at other speed with the same NGV exit flow: W = U2*Ct2 (Ct3 != 0)
        om = OMEGA(Nn); K = s['W'] / OMEGA(N_DES)
        Wn = om * K - OMEGA(Nn) * s['rows'][1]['r3'] * (s['Cx3'] * math.tan(math.radians(s['beta3m'])) + om * s['rows'][1]['r3'])
        inc = math.degrees(math.atan2(K / s['rows'][1]['r2'] - om * s['rows'][1]['r2'], s['Cx2'])) - s['beta2m']
        z_inc = 0.8 * (math.sin(math.radians(inc))) ** 2
        Wn_eff = Wn - z_inc * 0.5 * (s['Cx2'] / math.cos(math.radians(s['beta2m']))) ** 2
        sweep.append(dict(N=Nn, eta_ts=s['eta_ts'] * Wn_eff / s['W'], incidence=inc))
    R['speed_sweep'] = sweep
    print('speed sweep (same gas path, incidence loss): ' + ', '.join('%.0fk %.3f (i %+.0f deg)' % (d['N'] / 1e3, d['eta_ts'], d['incidence']) for d in sweep))
    # ---- blade / disk structure
    hdr('3. Blisk structure (IN718, 5-axis), blade and disk')
    bs = blade_stress(s, Zr, N_DES); R['blade_60k'] = bs
    T_root = s['rows'][0]['T0rel2']; T_tip = s['rows'][2]['T0rel2']
    for Nn, lab in ((N_DES, '60k design'), (N_OS, '72k overspeed 120 %'), (N_SPIN, '78k proof spin (RT)')):
        b = blade_stress(s, Zr, Nn)
        T = 20.0 if Nn == N_SPIN else T_root - 273.15
        sg = b['sig_cf'] + (0 if Nn == N_SPIN else b['sig_gas'])
        R.setdefault('blade', {})[lab] = dict(b, T_C=T, sig=sg, YS=interp(IN718['YS'], T), margin=interp(IN718['YS'], T) / sg)
        print('%-22s root stress cf %.0f + gas %.0f = %.0f MPa @ %.0f C; 0.2%% YS %.0f -> SF %.2f'
              % (lab, b['sig_cf'], 0 if Nn == N_SPIN else b['sig_gas'], sg, T, interp(IN718['YS'], T), interp(IN718['YS'], T) / sg))
    life = creep_life_h(1.5 * (bs['sig_cf'] + bs['sig_gas']), T_root)
    life_mid = creep_life_h(1.5 * blade_stress(s, Zr, N_DES)['sig_cf'] * 0.55, s['rows'][1]['T0rel2'])
    R['creep'] = dict(root_life_h=life, mid_life_h=life_mid, T_root_C=T_root - 273.15, T_tip_C=T_tip - 273.15)
    print('blade: %d x %.2f g, r_cg %.1f mm, root chord %.1f / t %.2f mm, tip chord %.1f / t %.2f mm'
          % (Zr, bs['m_blade'] * 1e3, bs['r_cg'] * 1e3, bs['root_c'] * 1e3, bs['root_t'] * 1e3, bs['tip_c'] * 1e3, bs['tip_t'] * 1e3))
    print('creep (LMP C=20, stress x 1.5): root @ %.0f C -> %.1e h; mid-span -> %.1e h.  Relative T0 at tip %.0f C (IN718 long-term limit ~650 C)'
          % (T_root - 273.15, life, life_mid, T_tip - 273.15))
    md, Ipd, Itd = disk_mass_props()
    for Nn, lab, hot in ((N_DES, '60k', True), (N_OS, '72k', True), (N_SPIN, '78k spin RT', False)):
        pull = Zr * blade_stress(s, Zr, Nn)['pull_one']
        d = disk_solve(Nn, pull, hot=hot)
        Tb = T_BORE_C if hot else 20.0; Tr = T_RIM_C if hot else 20.0
        ys_b = interp(IN718['YS'], Tb); uts_avg = interp(IN718['UTS'], 0.5 * (Tb + Tr))
        dm = disk_solve(Nn, pull, hot=False)       # mechanical-only average hoop (burst)
        Nb = Nn * math.sqrt(0.85 * uts_avg / dm['sig_theta_avg'])
        R.setdefault('disk', {})[lab] = dict(d, YS_bore=ys_b, SF_yield=ys_b / d['sig_vm_max'], burst_rpm=Nb, burst_margin_vs_72k=Nb / N_OS)
        print('disk %-12s bore hoop %.0f MPa, max von Mises %.0f MPa @ r %.1f, avg hoop (mech) %.0f MPa; SF yield %.2f; burst %.0fk rpm (%.2f x 72k)'
              % (lab, d['sig_theta_bore'], d['sig_vm_max'], d['r_vm_max_mm'], dm['sig_theta_avg'], ys_b / d['sig_vm_max'], Nb / 1e3, Nb / N_OS))
    # ---- blade vibration
    bc = blade_campbell(s, Zr, Zn); R['blade_campbell'] = bc
    if bc:
        hdr('4. Blade vibration (tapered cantilever, centrifugal stiffening, 630 C)')
        print('1F / 2F: ' + ', '.join('%.0fk: %.0f / %.0f Hz' % (n / 1e3, f[0], f[1]) for n, f in zip(bc['N'], bc['f']) if n in (0, 60e3, 72e3)))
        cc = [c for c in bc['crossings'] if c['in_continuous_range']]
        print('EO crossings in 48-65k (continuous band): ' + (', '.join('%s EO%d @ %.1fk' % (c['mode'], c['EO'], c['rpm'] / 1e3) for c in cc) or 'none'))
        f60 = bc['f'][bc['N'].index(60e3)]
        print('NGV passing EO%d at 60k = %.0f Hz vs 2F %.0f Hz -> margin %.0f %%' % (Zn, Zn * 1000, f60[1], (Zn * 1000 / f60[1] - 1) * 100))
    # ---- thrust
    th = thrust(s); R['thrust'] = th
    hdr('5. Axial thrust (+ = east, downstream)')
    print('front cavity %.0f Pa, back cavity %.0f Pa, buffer %.0f Pa, bearing chambers %.0f Pa' % (th['p_front_cavity'], th['p_back_cavity'], P_BUF, P_BC))
    print('blades %+.0f N, disk faces %+.0f N, labyrinth %+.0f N, oil seal %+.0f N -> net %+.0f N east'
          % (th['F_blades'], th['F_disk'], th['F_lab'], th['F_oil_seal'], th['F_net']))
    # ---- PMG
    pm = pmg_design(); R['pmg'] = pm
    pm55 = pmg_design(gly_in=55.0)
    hdr('6. PMG 30 kW @ 60k, 2-pole SmCo surface PM, CF sleeve, 24 slots')
    print('f_e %.0f Hz (2-pole; 1192 Hz at 71.5k); rotor: shaft r %.1f, magnet r %.1f, sleeve r %.1f, bore r %.1f mm; stack %d mm; stator OD %.1f mm'
          % (pm['f_e'], pm['R_shaft'], pm['R_mag'], pm['R_sleeve'], pm['R_bore'], pm['L_stk'], 2 * pm['R_out']))
    print('B1 gap %.3f T (Br %.3f T @130 C), tooth %.2f T, yoke %.2f T; kw %.3f, N_ph %d (z_slot %d); E_LL %.0f V @60k; I %.1f A rms; J %.1f A/mm2; A %.0f A/m'
          % (pm['B1'], pm['Br'], pm['B_tooth'], pm['B_yoke'], pm['kw'], pm['N_ph'], pm['z_slot'], pm['E_LL'], pm['I'], pm['J'], pm['elec_loading']))
    tq = pm['torque']; tau = tq / (2 * math.pi * (pm['R_bore'] * 1e-3) ** 2 * pm['L_stk'] * 1e-3)
    pm['shear_stress'] = tau
    print('torque %.2f N m, air-gap shear %.1f kPa; Ls %.0f uH (X %.2f ohm), R_ph %.1f mohm; I_sc %.0f A (%.1f pu); |V_ph| %.0f V'
          % (tq, tau / 1e3, pm['Ls'] * 1e6, pm['X'], pm['R_ph'] * 1e3, pm['I_sc'], pm['I_sc'] / pm['I'], pm['V_ph']))
    print('losses: Cu %.0f, Fe %.0f, windage %.0f, rotor eddy %.0f, stray %.0f = %.0f W -> eta_PMG %.3f'
          % (pm['P_cu'], pm['P_fe'], pm['P_wind'], pm['P_rot_eddy'], pm['P_stray'], pm['P_loss'], pm['eta']))
    print('glycol %.0f L/min in %.0f C: Q %.0f W, dT %.1f K, channel V %.1f m/s, h %.0f W/m2K, dp %.0f Pa; winding %.0f C, end-winding hot spot %.0f C (55 C inlet: %.0f C)'
          % (PMG['gly_lpm'], pm['gly_in'], pm['Q_glycol'], pm['dT_glycol'], pm['V_channel'], pm['h_glycol'], pm['dp_glycol'], pm['T_winding'], pm['T_end_winding'], pm55['T_end_winding']))
    print('demagnetisation at 3-phase short circuit: H %.0f kA/m vs Hcj(130 C) %.0f kA/m -> SF %.1f'
          % (pm['H_demag'] / 1e3, pm['Hcj_hot'] / 1e3, pm['Hcj_hot'] / pm['H_demag']))
    sl = {}
    for Nn, T in ((0, 20.0), (N_DES, 130.0), (N_OS, 150.0), (N_SPIN, 20.0)):
        r_ = sleeve_fe(Nn, T)
        if r_: sl['%.0fk_%.0fC' % (Nn / 1e3, T)] = r_
    R['sleeve'] = sl
    if sl:
        print('CF sleeve (T700/epoxy hoop, t %.1f mm, diametral interference %.2f mm):' % (PMG['t_sleeve'], SLEEVE['delta_d']))
        for k, v in sl.items():
            print('  %-10s sleeve hoop max %.0f MPa (allow %.0f), contact magnet/sleeve %.1f MPa, shaft/magnet %.1f MPa'
                  % (k, v['sleeve_hoop_max'], SLEEVE['allow'] / 1e6, v['p_magnet_sleeve'], v['p_shaft_magnet']))
    # ---- layout, components, J
    L = rotor_layout(pm); R['layout'] = {k: v for k, v in L.items()}
    mp = None
    fmp = os.path.join(OUT, 'E3_massprops.json')
    if os.path.exists(fmp):
        try: mp = json.load(open(fmp))['rotor']
        except Exception: mp = None
    comps, J, m_rot, xcg, src = rotor_components(s, Zr, bs, pm, L, mp)
    R['rotor'] = dict(components={k: dict(mass_kg=v[0], x_cg_mm=v[1], Ip_kgm2=v[2], It_kgm2=v[3]) for k, v in comps.items()},
                      J_kgm2=J, mass_kg=m_rot, x_cg_mm=xcg, source=src,
                      E_kin_60k_kJ=0.5 * J * OMEGA(N_DES) ** 2 / 1e3, E_kin_72k_kJ=0.5 * J * OMEGA(N_OS) ** 2 / 1e3)
    hdr('7. Rotor (one shaft: FPT blisk west - B1 - PMG - B2 east)  [mass properties: %s]' % src)
    for k, v in comps.items():
        print('  %-16s %7.1f g @ x %6.1f  Ip %.3e' % (k, v[0] * 1e3, v[1], v[2]))
    print('rotor mass %.2f kg, x_cg %.1f; J = %.3e kg m2 (electrical assumption 8e-4); E_kin 60k %.1f kJ, 72k %.1f kJ'
          % (m_rot, xcg, J, R['rotor']['E_kin_60k_kJ'], R['rotor']['E_kin_72k_kJ']))
    print('bearing centres B1 x %.1f, B2 x %.1f (span %.1f); blisk overhang %.1f mm; rotor x %.1f .. %.1f'
          % (L['b1'], L['b2'], L['span'], L['b1'] - comps['FPT_blisk'][1], L['stud0'], L['shaft1']))
    # runaway times with the real J (same as electrical calc §2)
    rt = {}
    for P_ in (25.6e3, 30e3):
        for frac in (1.05, 1.10, 1.20):
            w0 = OMEGA(N_DES); rt['%.1fkW_%d%%' % (P_ / 1e3, round(frac * 100))] = 0.5 * J * w0 ** 2 * (frac ** 2 - 1) / P_ * 1e3
    R['runaway_ms'] = rt
    print('load-loss overspeed with the real J: ' + ', '.join('%s %.0f ms' % (k, v) for k, v in rt.items()))
    # ---- bearings
    br = bearings(th['F_net'], m_rot, xcg, L); R['bearings'] = br
    hdr('8. Bearings: B1 %s | B2 %s' % (BRG1['desig'], BRG2['desig']))
    print('preload spring %.0f N at B2 (floating), B1 locating; thrust %+.0f N -> axial B1 %.0f N / B2 %.0f N (min-load %.0f N: %s)'
          % (F_PRELOAD, th['F_net'], br['Fa1'], br['Fa2'], br['Fa_min'], 'OK' if br['B1_min_load_ok'] else 'LOW'))
    print('radial: weight %.1f / %.1f N + G2.5 unbalance %.1f N; P1 %.0f N, P2 %.0f N; L10h %.0f / %.0f h; L_nm (a_ISO %.0f) %.0f / %.0f h'
          % (br['W1'], br['W2'], br['F_unbal'], br['P1'], br['P2'], br['L10h_1'], br['L10h_2'], br['a_ISO'], br['Lnm_1'], br['Lnm_2']))
    print('n.dm %.2e (60k) / %.2e (72k) mm/min; friction %.0f + %.0f W (oil jet, ISO VG ~32 ester, f0 1.5)'
          % (br['ndm_60k'], br['ndm_72k'], br['P_fric_B1'], br['P_fric_B2']))
    # ---- rotordynamics
    rd = rotordynamics(L, pm, comps); R['rotordynamics'] = rd
    ub = unbalance_response(L, pm, comps, G_bal=6.3); ub2 = unbalance_response(L, pm, comps, G_bal=6.3, phase=math.pi)
    R['unbalance'] = ub; R['unbalance_out_of_phase'] = ub2
    if rd:
        hdr('9. Rotordynamics (SFD supports: O-ring centring %.1f N/um, SFD R %.0f L %.0f c %.3f mm, C %.0f N s/m; bearing %.0f N/um)'
            % (SFD['k_oring'] / 1e6, SFD['R'], SFD['L'], SFD['c'], rd['c_sfd'], K_BRG / 1e6))
        for c in rd['criticals']:
            print('  critical %d: %7.0f rpm  %-18s zeta %.3f (log dec %.2f), shaft strain energy %.0f %%, max deflection x %.0f'
                  % (c['mode'], c['rpm'], c['type'], c['zeta'], c['logdec'], c['shaft_strain_energy'] * 100, c['x_max_mm']))
        print('  non-spinning, free supports (bending): ' + ', '.join('%.0f' % v for v in rd['free_free_rpm'][:3]) + ' rpm')
        print('  same rotor on rigid housings (no SFD): ' + ', '.join('%.0f' % v for v in rd['rigid_housing_criticals_rpm']) + ' rpm')
        bend = [c for c in rd['criticals'] if c['type'] == 'bending']
        rigid = [c for c in rd['criticals'] if c['type'] != 'bending']
        fb = bend[0]['rpm'] if bend else None
        ffb = rd['free_free_rpm'][0] if rd['free_free_rpm'] else None
        R['rd_summary'] = dict(rigid_modes_rpm=[c['rpm'] for c in rigid], first_bending_rpm=fb, first_bending_nonspinning_rpm=ffb,
                               margin_bending_vs_72k=(fb / N_OS - 1) if fb else None,
                               margin_rigid_vs_min_cont=(1 - max([c['rpm'] for c in rigid]) / N_MIN_CONT) if rigid else None)
        print('  -> supercritical: rigid-body modes %s rpm (%.0f %% below the %.0fk minimum continuous speed); first bending critical (fwd, spinning) %s rpm = %s above 72k; non-spinning %.0f rpm (+%.0f %%)'
              % ('/'.join('%.0f' % c['rpm'] for c in rigid), 100 * R['rd_summary']['margin_rigid_vs_min_cont'] if rigid else 0, N_MIN_CONT / 1e3,
                 '%.0f' % fb if fb else '> 110000', ('%.0f %%' % (100 * R['rd_summary']['margin_bending_vs_72k'])) if fb else '> 53 %', ffb, 100 * (ffb / N_OS - 1)))
        pk = max(ub, key=lambda d: d['disk_um']); pk2 = max(ub2, key=lambda d: d['disk_um'])
        at60 = min(ub, key=lambda d: abs(d['N'] - N_DES))
        R['unbalance_summary'] = dict(G=6.3, peak_disk_um=pk['disk_um'], peak_rpm=pk['N'], peak_oop_um=pk2['disk_um'], peak_oop_rpm=pk2['N'],
                                      disk_60k_um=at60['disk_um'], sfd_ecc_60k=max(at60['sfd1_ecc'], at60['sfd2_ecc']), Fb_60k=max(at60['Fb1'], at60['Fb2']))
        print('  G6.3 (degraded) unbalance: peak disk amplitude %.1f um @ %.0f rpm (in-phase) / %.1f um @ %.0f (out-of-phase); at 60k disk %.2f um, SFD ecc %.3f, bearing force %.0f N'
              % (pk['disk_um'], pk['N'], pk2['disk_um'], pk2['N'], at60['disk_um'], max(at60['sfd1_ecc'], at60['sfd2_ecc']), max(at60['Fb1'], at60['Fb2'])))
        print('    vs FPT tip gap %.2f mm, PMG gap %.1f mm, labyrinth 0.15 mm' % (GEO['tip_gap'], PMG['g_mech']))
    # ---- thermal / seals
    tb = thermal_barrier(br); R['thermal'] = tb; sealr = seals(th); R['seals'] = sealr
    hdr('10. Thermal barrier, oil, seals')
    print('heat into B1 zone: shaft %.0f W (B1 inner ring ~%.0f C), shield %.0f W, hub bell %.0f W, bearing %.0f W -> oil %.0f W; B2 %.0f W; cone to PMG %.0f W'
          % (tb['Q_shaft_W'], tb['T_B1_inner_ring_C'], tb['Q_heat_shield_W'], tb['Q_hub_bell_W'], br['P_fric_B1'], tb['Q_B1_oil_W'], tb['Q_B2_oil_W'], tb['Q_cone_W']))
    print('oil (dT %.0f K, %.1f barg supply): B1 %.2f L/min, B2 %.2f L/min (incl. SFD 0.1 each) -> total %.2f L/min'
          % (tb['oil_dT'], tb['oil_supply_barg'], tb['oil_B1_lpm'], tb['oil_B2_lpm'], tb['oil_total_lpm']))
    print('buffer air (P2 bleed, orifice %.2f mm): to back cavity %.2f g/s, to B1 chamber %.2f g/s; PMG gap air %.1f g/s (48 V fan)'
          % (sealr['buffer_orifice_mm'], sealr['buffer_to_back_cavity_gs'], sealr['buffer_to_B1_chamber_gs'], pm['m_air_gap'] * 1e3))
    # ---- power balance
    P_mech = br['P_fric_B1'] + br['P_fric_B2'] + 15.0
    P_shaft = P_aero - P_mech
    P_el = P_shaft - pm['P_loss']
    R['power'] = dict(P_aero=P_aero, P_mech_loss=P_mech, P_shaft_to_PMG=P_shaft, P_PMG_terminals=P_el, eta_mech=P_shaft / P_aero,
                      P_shaft_cycle=P_SHAFT_CYCLE, eta_PMG=pm['eta'])
    hdr('11. Power balance at 60k')
    print('FPT aero %.2f kW - bearings/seals %.0f W = shaft %.2f kW (cycle %.2f kW, %+.1f %%) -> PMG terminals %.2f kW (eta_PMG %.3f)'
          % (P_aero / 1e3, P_mech, P_shaft / 1e3, P_SHAFT_CYCLE / 1e3, (P_shaft / P_SHAFT_CYCLE - 1) * 100, P_el / 1e3, pm['eta']))
    print('with the cycle FPT inlet pressure (GG eta_t 0.82): shaft %.2f kW'
          % (MG * solve_stage(P4_cyc * (1 - idc['dP0_over_P0'] + 0.015) if False else P4_cyc, T00, Zn=Zn, Zr=Zr)['W_shaft_aero'] / 1e3 - P_mech / 1e3))
    # ---- spin test / overspeed spec numbers
    R['overspeed'] = dict(N_design=N_DES, N_gov_max=N_GOV, N_trip=N_TRIP, N_120=N_OS, N_spin=N_SPIN)
    # ---- geometry for the CAD
    geo = dict(X=X, GEO=GEO, ROT_FPT=ROT_FPT, interduct_hub=idc['hub'], interduct_cas=idc['cas'], Z_ngv=Zn, Z_rot=Zr,
               rotor_sections=rotor_sections(s), ngv_sections=ngv_sections(s), DISK=DISK, layout=L,
               pmg=dict((k, pm[k]) for k in ('R_shaft', 'R_mag', 'R_sleeve', 'R_bore', 'R_slot_bottom', 'R_out', 'L_stk', 'Qs', 'l_end_ax')),
               pmg_slot=dict(b_tooth=PMG['b_tooth'], b_open=PMG['b_open'], tooth_tip=PMG['tooth_tip'], wedge=PMG['wedge']),
               BRG1=BRG1, BRG2=BRG2, SFD=SFD, SFD2=SFD2, R_SEAL=R_SEAL, F_PRELOAD=F_PRELOAD)
    R['geometry'] = geo
    json.dump(R, open(os.path.join(OUT, 'E3_calc_results.json'), 'w'), indent=1, default=float)
    print('\n-> %s' % os.path.join(OUT, 'E3_calc_results.json'))
    plots(R)
    return R

def plots(R):
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    except ImportError:
        print('(no matplotlib - plots skipped)'); return
    rd = R.get('rotordynamics')
    if rd:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for Nn, modes in rd['campbell']:
            for f, z, bend in modes:
                c = 'tab:blue' if f > 0 else 'tab:red'
                ax.scatter([Nn], [abs(f) * 60], s=6 + 60 * min(z, 0.5), c=c, marker='o' if bend < 0.5 else 's', alpha=0.7, lw=0)
        ax.plot([0, 110000], [0, 110000], 'k--', lw=1, label='1x synchronous')
        ax.axvspan(N_MIN_CONT, N_GOV, color='g', alpha=0.08, label='continuous 48-65k')
        ax.axvline(N_DES, c='g', ls=':', lw=1); ax.axvline(N_OS, c='r', ls=':', lw=1, label='72k (120 %)')
        for c in rd['criticals']:
            ax.plot(c['rpm'], c['rpm'], 'k*', ms=10)
            ax.annotate('%s %.0f rpm, zeta %.2f' % (c['type'], c['rpm'], c['zeta']), (c['rpm'], c['rpm']), xytext=(6, -12), textcoords='offset points', fontsize=7)
        ax.set_xlim(0, 110000); ax.set_ylim(0, 200000)
        ax.set_xlabel('FPT/PMG speed N2 [rpm]'); ax.set_ylabel('whirl frequency [cpm]')
        ax.set_title('E3 FPT/PMG rotor - damped Campbell (blue fwd, red bwd; o rigid-body, s bending; size ~ damping)', fontsize=9)
        ax.legend(fontsize=8, loc='upper left'); ax.grid(alpha=.3); fig.tight_layout()
        fig.savefig(os.path.join(OUT, 'E3_campbell.png'), dpi=120); plt.close(fig)
    ub = R.get('unbalance')
    if ub:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for key, lab in (('disk_um', 'FPT disk'), ('b1_um', 'B1'), ('b2_um', 'B2'), ('mag_um', 'PM rotor')):
            ax.semilogy([d['N'] for d in ub], [d[key] for d in ub], label=lab + ' (in-phase)')
        ax.semilogy([d['N'] for d in R['unbalance_out_of_phase']], [d['disk_um'] for d in R['unbalance_out_of_phase']], 'k--', label='FPT disk (out-of-phase)')
        ax.axhline(GEO['tip_gap'] * 1e3, c='r', ls=':', label='FPT tip gap'); ax.axvspan(N_MIN_CONT, N_GOV, color='g', alpha=0.08)
        ax.set_xlabel('N2 [rpm]'); ax.set_ylabel('amplitude 0-pk [um]'); ax.set_title('G6.3 unbalance response (disk + PM rotor planes, SFD supports)', fontsize=9)
        ax.legend(fontsize=7); ax.grid(alpha=.3, which='both'); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'E3_unbalance.png'), dpi=120); plt.close(fig)
    bc = R.get('blade_campbell')
    if bc:
        fig, ax = plt.subplots(figsize=(8, 5))
        for mi, lab in ((0, '1F'), (1, '2F')):
            ax.plot(bc['N'], [f[mi] for f in bc['f']], 'o-', label=lab)
        for eo in list(range(1, 11)) + [R['Z_ngv'], 21]:
            ax.plot([0, 80000], [0, eo * 80000 / 60], 'k-' if eo in (R['Z_ngv'], 21) else 'k:', lw=0.7)
            ax.text(80000 * 0.98, min(eo * 80000 / 60, 39000), 'EO%d' % eo, fontsize=6, ha='right')
        ax.axvspan(N_MIN_CONT, N_GOV, color='g', alpha=0.08); ax.set_ylim(0, 40000); ax.set_xlim(0, 80000)
        ax.set_xlabel('N2 [rpm]'); ax.set_ylabel('frequency [Hz]'); ax.set_title('FPT blade Campbell (beam model; blisk FEA to confirm)', fontsize=9)
        ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'E3_blade_campbell.png'), dpi=120); plt.close(fig)
    print('plots -> %s' % OUT)

if __name__ == '__main__':
    main()
