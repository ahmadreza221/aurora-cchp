#!/usr/bin/env python3
"""GR180 version C2 = version C (compact turbo-generator) + compact recuperator R-C2 (eps ~0.80) on the exhaust outlet
+ low-pressure hot-water heat exchanger HX-C2 (90/70 C) on the recuperator hot outlet.  Combustor = E2 (variant A) with
re-arranged C1/C2 ports (E2-C2).  Variants A, B and C files are read only.

Pure python (no numpy).  Run:   python3 sim/variant_c2/c2_calc.py
Writes:  sim/variant_c2/c2_design.json  (geometry for cad/variant_c2/*.py)
         sim/variant_c2/c2_results.json (all values for docs/variant_c2/00_design.md)

Method
  * Cycle: the project gas-generator + FPT model (sim/concept_study.cycle, constant cp, target efficiencies, TIT 800 C,
    PR 3.1) with the ACTUAL pressure losses of E2 (sim/engine/e2_results.json), the version-C compact exhaust
    (sim/variant_c/c_exhaust_results.json), R-C2 and HX-C2, the E2 recuperator bypass (3.2 %) and the E3 buffer bleed.
  * R-C2: the variant-A E4 plate-fin model (sim/engine/e4_recuperator_calc.py: real gas properties, Manglik & Bergles
    OSF, marching counterflow, Kroeger conduction, maldistribution allowance, Kays & London entrance/exit, distributors)
    re-used for eps_net 0.80 with a LOW hot-side pressure-drop budget (FPT back-pressure).
  * HX-C2: helically finned stainless tubes in the exhaust duct above R-C2 (Briggs & Young heat transfer), counterflow
    serpentine water circuit 70 -> 90 C, atmospheric-pressure hot water (PN6 rating, no steam).
Every assumption is marked # ASSUMPTION.
"""
import math, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SIM = os.path.dirname(HERE); ROOT = os.path.dirname(SIM)
sys.path.insert(0, SIM)
import concept_study as cs   # noqa: E402

E2R = json.load(open(os.path.join(SIM, 'engine', 'e2_results.json')))
CEX = json.load(open(os.path.join(SIM, 'variant_c', 'c_exhaust_results.json')))
P_AMB = 100725.0                     # Pa, 50 m site (project value)
LHV = cs.LHV; LHV_VOL = 34.5e6       # J/kg, J/m3 city gas (as vb_cycle.py)
ETA_PMG, ETA_INV, AUX_W = 0.975, 0.97, 450.0 + 250.0      # E3 PMG, grid inverter; ECU/oil/fans + hot-water pump
R = {}

# =====================================================================================================================
# 1. pressure-loss budget (fractions)
# =====================================================================================================================
DP = dict(collector_E2=E2R['collector']['dp_total_pct'] / 100,            # compressor exit -> C1 (E2 drum, ear, transition)
          comb_hot_E2=E2R['dp_hot_side_total_pct'] / 100 - E2R['pressure']['dP_baffle_kPa'] * 1e3 / (E2R['pressure']['P_C2'] * 1e5),   # C2 port + liner + NGV entry (C2: no baffle)
          exhaust_box_C=CEX.get('aero', {}).get('dp_static_pct', 0.894) / 100 if 'aero' in CEX else 0.00894,
          rec_cold=0.015, rec_hot=0.009, hx_hot=0.003, stack=0.002)       # R-C2 / HX-C2 / outlet: first guesses, replaced by section 5
BETA = E2R['beta_recuperator_bypass']; BLEED = E2R['bleed_E3_buffer']['frac']

def cycle(T_amb_C, eps, dp, ma15=0.395, T_stack_C=100.0):
    """gas generator + FPT, constant cp (concept_study constants), returns dict.  eps = recuperator effectiveness on the
    cold side; the bypass beta (E2 cold inner film + leaks) and the E3 buffer bleed as in sim/engine/e2_combustor_calc."""
    CPA, CPG, EXA, EXG = cs.CP_A, cs.CP_G, cs.EX_A, cs.EX_G
    Ta = T_amb_C + 273.15; ma = ma15 * 288.15 / Ta; mc = ma * (1 - BLEED)
    T1, P1 = Ta, P_AMB * 0.99; PR = 3.1; TIT = 1073.15; eta_c, eta_t, eta_pt = 0.73, 0.82, 0.78
    T2 = T1 * (1 + (PR ** EXA - 1) / eta_c); w_c = CPA * (T2 - T1); P2 = P1 * PR
    P3 = P2 * (1 - dp['collector_E2']) * (1 - dp['rec_cold']) * (1 - dp['comb_hot_E2'])
    P_exit = P_AMB * (1 + dp['exhaust_box_C'] + dp['rec_hot'] + dp['hx_hot'] + dp['stack'])
    Th = 880.0
    for it in range(80):
        f = 0.01 if it == 0 else f
        T2r = T2 + eps * (Th - T2)
        Tmix = ((mc - BETA * ma) * T2r + BETA * ma * T2) / mc
        f = CPG * (TIT - Tmix) / (0.97 * LHV) * 1.02
        mg = mc * (1 + f)
        w_t = w_c * ma / (0.985 * mc * (1 + f)); T4 = TIT - w_t / CPG
        P4 = P3 * ((TIT - w_t / (CPG * eta_t)) / TIT) ** (1 / EXG) * (1 - 0.015)
        w_pt = eta_pt * CPG * T4 * (1 - (P_exit / P4) ** EXG); T5 = T4 - w_pt / CPG
        Th = (mg * CPG * T5 + BLEED * ma * CPA * T2) / (mg * CPG + BLEED * ma * CPA)
    Q_rec = (mc - BETA * ma) * CPA * (T2r - T2)
    T_rec_hot_out = Th - Q_rec / (mg * CPG + BLEED * ma * CPA)
    P_shaft = mg * w_pt * 0.985
    P_el = P_shaft * ETA_PMG * ETA_INV - AUX_W
    mf = mc * f; Q_fuel = mf * LHV
    Q_hw = (mg + BLEED * ma) * cs.CP_G_LOW * max(T_rec_hot_out - (T_stack_C + 273.15), 0.0) * 0.97     # 3 % casing/piping loss
    return dict(T_amb_C=T_amb_C, ma=ma, mf=mf, mg=mg + BLEED * ma, T2=T2, P2=P2, T2r=T2r, P3=P3, T5=T5, Th_in=Th, P_exit=P_exit,
                T_rec_hot_out=T_rec_hot_out, Q_rec=Q_rec, P_shaft=P_shaft, P_el=P_el, Q_fuel=Q_fuel, gas_m3h=Q_fuel / LHV_VOL * 3600,
                eta_el=P_el / Q_fuel, Q_hw=Q_hw, eta_tot=(P_el + Q_hw) / Q_fuel, T_stack_C=T_stack_C)

# =====================================================================================================================
# 2. R-C2 core model (copied from sim/engine/e4_recuperator_calc.py, same equations; design point = C2 cycle at 15 C)
# =====================================================================================================================
EPS_NET = 0.80
CPP = {'N2': (28.90, -0.1571e-2, 0.8081e-5, -2.873e-9, 28.013), 'O2': (25.48, 1.520e-2, -0.7155e-5, 1.312e-9, 31.999),
       'CO2': (22.26, 5.981e-2, -3.501e-5, 7.469e-9, 44.010), 'H2O': (32.24, 0.1923e-2, 1.055e-5, -3.595e-9, 18.015),
       'Ar': (20.786, 0.0, 0.0, 0.0, 39.948)}                                    # Cengel A-2c, kJ/kmol K
def air_moles(m):
    Md = 0.7808 * 28.013 + 0.2095 * 31.999 + 0.0093 * 39.948 + 0.0004 * 44.010; n = m / Md
    return {'N2': 0.7808 * n, 'O2': 0.2095 * n, 'Ar': 0.0093 * n, 'CO2': 0.0004 * n, 'H2O': 0.0}
class Gas:
    def __init__(self, moles):
        self.m = sum(v * CPP[k][4] for k, v in moles.items()); self.w = {k: v * CPP[k][4] / self.m for k, v in moles.items()}
        self.R = 8314.462 / (self.m / sum(moles.values()))
    def cp(self, T): return 1e3 * sum(w * (a + b * T + c * T * T + d * T ** 3) / M for k, w in self.w.items() for a, b, c, d, M in [CPP[k]])
    def h(self, T): return 1e3 * sum(w * (a * T + b * T * T / 2 + c * T ** 3 / 3 + d * T ** 4 / 4) / M for k, w in self.w.items() for a, b, c, d, M in [CPP[k]])
    def T_of_h(self, hv, T=600.0):
        for _ in range(30):
            dT = (self.h(T) - hv) / self.cp(T); T -= dT
            if abs(dT) < 1e-7: break
        return T
def mu(T): return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)
def kgas(T): return 0.0241 * (T / 273.15) ** 1.5 * (273.15 + 194.0) / (T + 194.0)
def k347(Tc): return 14.6 + 0.0145 * Tc
RHO = {'347H': 7960.0, 'IN625': 8440.0, '316L': 7990.0, '1.4301': 7900.0, 'S355': 7850.0}

class OSF:
    def __init__(self, name, p, t, b, l):
        self.name, self.p, self.t, self.b, self.l = name, p, t, b, l
        self.s, self.h = p - t, b - t; s, h = self.s, self.h
        A = 2 * (s * l + h * l + t * h) + t * s
        self.Dh = 4 * s * h * l / A; self.sigma = s * h / (p * b); self.beta = A / (p * b * l)
        self.ffin = (2 * h * l + 2 * t * h + t * s) / A; self.metal = t * (b + s) / (p * b)
    def jf(self, Re, Pr=0.7):                                                    # REF Manglik & Bergles (1995)
        a, d, g = self.s / self.h, self.t / self.l, self.t / self.s
        j = 0.6522 * Re ** -0.5403 * a ** -0.1541 * d ** 0.1499 * g ** -0.0678 * (1 + 5.269e-5 * Re ** 1.340 * a ** 0.504 * d ** 0.456 * g ** -1.055) ** 0.1
        f = 9.6243 * Re ** -0.7422 * a ** -0.1856 * d ** 0.3053 * g ** -0.2659 * (1 + 7.669e-8 * Re ** 4.429 * a ** 0.920 * d ** 3.767 * g ** 0.236) ** 0.1
        return j, f
    def eta_o(self, hc, Tm_C):
        m = math.sqrt(2 * hc / (k347(Tm_C) * self.t) * (1 + self.t / self.l)); mL = m * (self.b / 2 - self.t)
        return 1 - self.ffin * (1 - math.tanh(mL) / mL)
FIN_C = OSF('C-OSF 1.2/2.0', 1.20e-3, 0.10e-3, 2.00e-3, 3.0e-3)                  # as E4
FIN_HS = {'H-OSF 1.6/3.8': OSF('H-OSF 1.6/3.8', 1.60e-3, 0.12e-3, 3.80e-3, 3.2e-3),           # as E4
          'H-OSF 2.0/5.0': OSF('H-OSF 2.0/5.0', 2.00e-3, 0.12e-3, 5.00e-3, 3.2e-3)}           # taller, more open hot fin (low dp)
T_P, T_CAP, W_SB = 0.40e-3, 2.0e-3, 5.0e-3; L_WIN = 0.070; EB_HOT, EB_COLD = 0.030, 0.020; END_BAR = 0.5 * (EB_HOT + EB_COLD)
RF_H, RF_C, CREDIT_D, DEPS_MAL = 2.0e-5, 0.0, 0.35, 0.004      # distributor credit 0.35 (E4: 0.5): the windows are a larger share here

class Core:
    def __init__(self, **k): self.__dict__.update(k)
def plate_fin(fc, fh, W, nc):
    nh = nc + 1; Wf = W - 2 * W_SB
    H = nc * fc.b + nh * fh.b + (nc + nh - 1) * T_P + 2 * T_CAP
    nps = nc + nh - 1
    return Core(sc=fc, sh=fh, Ac=nc * Wf * fc.b * fc.sigma, Ah=nh * Wf * fh.b * fh.sigma, Pc=nc * Wf * fc.b * fc.beta, Ph=nh * Wf * fh.b * fh.beta,
                Ak=nps * W * T_P + 2 * W * T_CAP + nc * Wf * fc.b * fc.metal + nh * Wf * fh.b * fh.metal + (nc * fc.b + nh * fh.b) * 2 * W_SB,
                Rw=T_P / (k347(400) * nps * Wf), Ld=L_WIN, Lcf=0.2, frontal_h=W * H, W=W, H=H, nc=nc, nh=nh)

def design_point():
    c15 = cycle(15.0, EPS_NET, DP)
    return c15
def setup(c):
    global M_C, M_F, M_H, TC_IN, TH_IN, P2, PH_IN, PH_OUT, AIR, EXH
    M_C = c['ma'] * (1 - BLEED) - BETA * c['ma']; M_F = c['mf']; M_H = c['mg']
    TC_IN, TH_IN, P2 = c['T2'], c['Th_in'], c['P2'] * (1 - DP['collector_E2'])
    PH_IN = P_AMB * (1 + DP['rec_hot'] + DP['hx_hot'] + DP['stack']); PH_OUT = P_AMB * (1 + DP['hx_hot'] + DP['stack'])
    AIR = Gas(air_moles(M_C)); ex = air_moles(M_H - M_F); nf = M_F / 16.043
    ex['O2'] -= 2 * nf; ex['CO2'] += nf; ex['H2O'] += 2 * nf; EXH = Gas(ex)

def local(core, Tc, Th):
    Gc, Gh = M_C / core.Ac, M_H / core.Ah
    Rec, Reh = Gc * core.sc.Dh / mu(Tc), Gh * core.sh.Dh / mu(Th)
    Prc, Prh = mu(Tc) * AIR.cp(Tc) / kgas(Tc), mu(Th) * EXH.cp(Th) / kgas(Th)
    jc, fc = core.sc.jf(Rec, Prc); jh, fh = core.sh.jf(Reh, Prh)
    hc = jc * Gc * AIR.cp(Tc) / Prc ** (2 / 3); hh = jh * Gh * EXH.cp(Th) / Prh ** (2 / 3)
    Tm = 0.5 * (Tc + Th) - 273.15; eoc, eoh = core.sc.eta_o(hc, Tm), core.sh.eta_o(hh, Tm)
    UA = 1.0 / (1 / (eoc * hc * core.Pc) + RF_C / core.Pc + core.Rw + RF_H / core.Ph + 1 / (eoh * hh * core.Ph))
    return dict(Rec=Rec, Reh=Reh, hc=hc, hh=hh, fc=fc, fh=fh, UA=UA, Gc=Gc, Gh=Gh)
def march(core, Tc_out, dx=0.003):
    Th, Tc, x, dpc, dph, prof = TH_IN, Tc_out, 0.0, 0.0, 0.0, []
    while Tc > TC_IN and x < 2.0:
        L = local(core, Tc, Th); Cc, Ch = M_C * AIR.cp(Tc), M_H * EXH.cp(Th)
        k = L['UA'] * (1 / Ch - 1 / Cc); q = L['UA'] * (Th - Tc) * ((1 - math.exp(-k * dx)) / k if abs(k * dx) > 1e-12 else dx)
        Tcn = Tc - q / Cc
        if Tcn < TC_IN: fr = (Tc - TC_IN) / (Tc - Tcn); dxe = dx * fr; q *= fr; Tcn = TC_IN
        else: dxe = dx
        dpc += 4 * L['fc'] * dxe / core.sc.Dh * L['Gc'] ** 2 / (2 * P2 / (AIR.R * Tc))
        dph += 4 * L['fh'] * dxe / core.sh.Dh * L['Gh'] ** 2 / (2 * PH_OUT / (EXH.R * Th))
        prof.append(L); Th -= q / Ch; Tc = Tcn; x += dxe
    return dict(L=x, Th_out=Th, dpc=dpc, dph=dph, prof=prof)
def kroeger(NTU, lam):
    if lam <= 0: return 0.0
    ln = lam * NTU; r = math.sqrt(ln / (1 + ln)); phi = r * math.tanh(NTU / (r * (1 + ln)))
    return NTU / (1 + NTU) - (1 - 1 / (1 + NTU * (1 + lam * phi) / (1 + ln)))
def entrance_exit(G, sigma, rin, rout):
    Kc = 0.8 - 0.4 * sigma; Ke = (1 - sigma) ** 2 - 0.25 * sigma
    return G ** 2 / 2 * ((1 - sigma ** 2 + Kc) / rin + 2 * (1 / rout - 1 / rin) - (1 - sigma ** 2 - Ke) / rout)
def size(core, eps_net):
    deps = DEPS_MAL + 0.002
    for _ in range(4):
        e_raw = min(eps_net + deps, 0.98); Tc_out = TC_IN + e_raw * (TH_IN - TC_IN)
        m = march(core, Tc_out); core.Lcf = max(m['L'] - 2 * CREDIT_D * core.Ld, 0.02)
        Ltot = core.Lcf + 2 * core.Ld + 2 * END_BAR
        UA = sum(p['UA'] for p in m['prof']) * m['L'] / len(m['prof']); Cmin = M_C * AIR.cp(0.5 * (TC_IN + Tc_out))
        NTU = UA / Cmin; lam = k347(350) * core.Ak / (Ltot * Cmin); dcond = kroeger(NTU, lam); deps = DEPS_MAL + dcond
    Gh = M_H / core.Ah; dph = m['dph'] * Ltot / m['L'] + entrance_exit(Gh, core.Ah / core.frontal_h, PH_IN / (EXH.R * TH_IN), PH_OUT / (EXH.R * m['Th_out']))
    Gc = M_C / core.Ac; dpc = m['dpc'] * core.Lcf / m['L'] + Gc ** 2 * (1 / (P2 / (AIR.R * Tc_out)) - 1 / (P2 / (AIR.R * TC_IN)))
    # cold crossflow distributors (plain fin p 2.0 / t 0.15) over the layer width W, Kturn 1.2 in / 1.0 out
    p_, t_ = 2.0e-3, 0.15e-3; s_, h_ = p_ - t_, core.sc.b - t_; sig = s_ * h_ / (p_ * core.sc.b); Dh = 4 * s_ * h_ / (2 * (s_ + h_))
    Aw = core.nc * core.Ld * core.sc.b * sig; Gw = M_C / Aw; dist = 0.0
    for T, K in ((TC_IN, 1.2), (Tc_out, 1.0)):
        rho = P2 / (AIR.R * T); Re = Gw * Dh / mu(T); a = min(s_, h_) / max(s_, h_)
        fRe = 24 * (1 - 1.3553 * a + 1.9467 * a ** 2 - 1.7012 * a ** 3 + 0.9564 * a ** 4 - 0.2537 * a ** 5)
        f = max(fRe / Re, 0.079 * Re ** -0.25); dist += (4 * f * core.W / Dh / 3 + K) * Gw ** 2 / (2 * rho)
    Wf, nc, nh = core.W - 2 * W_SB, core.nc, core.nh; r = RHO['347H']
    mass = dict(fins_cold=r * nc * Wf * core.sc.b * core.sc.metal * core.Lcf, dist_fins=r * nc * Wf * core.sc.b * 0.081 * 2 * core.Ld,
                fins_hot=r * nh * Wf * core.sh.b * core.sh.metal * Ltot, parting_sheets=r * (nc + nh - 1) * core.W * Ltot * T_P,
                cap_sheets=r * 2 * core.W * Ltot * T_CAP, side_bars=r * (nc * core.sc.b + nh * core.sh.b) * 2 * W_SB * Ltot,
                end_bars=r * nc * core.sc.b * END_BAR * Wf * 2)
    mass['braze_BNi2'] = 0.035 * sum(mass.values()); mass['total'] = sum(mass.values())
    Q = M_C * (AIR.h(Tc_out) - AIR.h(TC_IN))
    return dict(W=core.W, H=core.H, nc=core.nc, nh=core.nh, fin_hot=core.sh.name, Lcf=core.Lcf, Ld=core.Ld, Ltot=Ltot, end_bar=END_BAR,
                eps_raw=e_raw, eps_net=e_raw - DEPS_MAL - dcond, NTU=NTU, UA=UA, lam=lam, dcond=dcond, Q_kW=Q / 1e3,
                Tc_out_C=Tc_out - 273.15 - (e_raw - (e_raw - DEPS_MAL - dcond)) * (TH_IN - TC_IN) * 0, Th_out_C=m['Th_out'] - 273.15,
                Tc_out_net_C=TC_IN + (e_raw - DEPS_MAL - dcond) * (TH_IN - TC_IN) - 273.15,
                dph_core_Pa=dph, dpc_core_Pa=dpc, dpc_dist_Pa=dist, Gh=Gh, Gc=Gc, Reh=(m['prof'][-1]['Reh'], m['prof'][0]['Reh']),
                Rec=(m['prof'][-1]['Rec'], m['prof'][0]['Rec']), area_cold=core.Pc * (core.Lcf + 2 * core.Ld), area_hot=core.Ph * Ltot,
                mass=mass, window_area=Aw, vol_L=core.W * core.H * Ltot * 1e3)

# =====================================================================================================================
# 3. HX-C2: helically finned tubes in the duct above R-C2 (gas up, water serpentine counterflow 70 -> 90 C)
# =====================================================================================================================
HX = dict(Do=16.0e-3, t_tube=1.0e-3, fin_D=34.0e-3, fin_t=0.4e-3, fin_pitch=3.0e-3, Pt=38.0e-3, Pl=33.0e-3, T_w_in=70.0, T_w_out=90.0,
          K_row=0.45)          # ASSUMPTION K_row: staggered helically finned tubes, per row on the max velocity (ESCOA/VDI range 0.3-0.6)
def hx_size(m_g, T_in_C, T_out_C, width_x, depth_y):
    cp = 1080.0; Q = m_g * cp * (T_in_C - T_out_C)
    m_w = Q / (4190.0 * (HX['T_w_out'] - HX['T_w_in']))
    dT1, dT2 = T_in_C - HX['T_w_out'], T_out_C - HX['T_w_in']; LMTD = (dT1 - dT2) / math.log(dT1 / dT2)
    Tm = 0.5 * (T_in_C + T_out_C) + 273.15; rho = P_AMB / (287.0 * Tm)
    n_tr = int(depth_y / HX['Pt']); A_face = width_x * depth_y
    hf = 0.5 * (HX['fin_D'] - HX['Do']); s = HX['fin_pitch'] - HX['fin_t']
    A_min = A_face - n_tr * width_x * (HX['Do'] + 2 * hf * HX['fin_t'] / HX['fin_pitch'])
    Vmax = m_g / (rho * A_min); Re = rho * Vmax * HX['Do'] / mu(Tm); Pr = 0.70
    Nu = 0.134 * Re ** 0.681 * Pr ** (1 / 3) * (s / hf) ** 0.2 * (s / HX['fin_t']) ** 0.1134          # REF Briggs & Young (1963)
    h = Nu * kgas(Tm) / HX['Do']
    m_fin = math.sqrt(2 * h / (16.0 * HX['fin_t'])); r1, r2 = HX['Do'] / 2, HX['fin_D'] / 2
    Lc = (r2 - r1) * (1 + 0.35 * math.log(r2 / r1)); eta_f = math.tanh(m_fin * Lc) / (m_fin * Lc)     # ASSUMPTION Schmidt approx.
    nfin = 1 / HX['fin_pitch']; A_fin = nfin * 2 * math.pi / 4 * (HX['fin_D'] ** 2 - HX['Do'] ** 2); A_bare = math.pi * HX['Do'] * (1 - nfin * HX['fin_t'])
    A_per_m = A_fin + A_bare; eta_o = 1 - A_fin / A_per_m * (1 - eta_f)
    h_w = 3000.0                                                                              # ASSUMPTION water side, Re ~ 2e4 in 14 mm tube
    U_per_m = 1 / (1 / (eta_o * h * A_per_m) + 1 / (h_w * math.pi * (HX['Do'] - 2 * HX['t_tube'])) + 2e-4 / A_per_m)   # + gas fouling
    L_tube = Q / (U_per_m * LMTD); n_rows = math.ceil(L_tube / (n_tr * width_x))
    dp = n_rows * HX['K_row'] * 0.5 * rho * Vmax ** 2
    m_metal = (math.pi * (HX['Do'] - HX['t_tube']) * HX['t_tube'] + nfin * math.pi / 4 * (HX['fin_D'] ** 2 - HX['Do'] ** 2) * HX['fin_t']) * RHO['1.4301'] * n_rows * n_tr * width_x
    V_w_DN32 = m_w / 975.0 / (math.pi / 4 * 0.0372 ** 2)
    return dict(Q_kW=Q / 1e3, m_w_kg_s=m_w, m3_h=m_w / 975 * 3600, LMTD=LMTD, Vmax=Vmax, Re=Re, h_gas=h, eta_fin=eta_f, U_per_m=U_per_m,
                L_tube_m=L_tube, n_tubes_per_row=n_tr, n_rows=n_rows, height_m=n_rows * HX['Pl'], dp_Pa=dp, mass_tubes_kg=m_metal,
                V_water_DN32=V_w_DN32, n_passes=n_rows, note='serpentine: one tube row = one pass, %d parallel tubes per row' % n_tr)

# =====================================================================================================================
# 4. iterate: cycle -> R-C2 size (search) -> HX -> pressure losses -> cycle
# =====================================================================================================================
DPH_CORE_MAX = 0.010 * P_AMB           # budget: R-C2 hot core <= 1.0 % p_amb (0.75 % needs a ~90 L core: section 4 sweep in the doc)
DPC_MAX = 0.015                         # R-C2 cold side incl. distributors, headers and risers <= 1.5 % P2
best = None
for it in range(3):
    c15 = design_point(); setup(c15)
    cands = []
    for Lw in (0.05, 0.06, 0.07, 0.08, 0.10):
      for fname, fh in FIN_HS.items():
        for W in (0.25, 0.30, 0.35, 0.40):
            for nc in range(50, 96, 5):
                core = plate_fin(FIN_C, fh, W, nc); core.Ld = Lw
                if core.H > 0.62: continue                          # stack along x from x -80 (C1 nozzle x -11)
                r_ = size(core, EPS_NET)
                r_['fin_c'] = FIN_C.name
                dpc_tot = r_['dpc_core_Pa'] + r_['dpc_dist_Pa'] + 1500.0              # + headers, risers, bellows (section 6 estimate)
                ok = r_['dph_core_Pa'] <= DPH_CORE_MAX and dpc_tot <= DPC_MAX * P2 and r_['Lcf'] >= 0.5 * r_['Ld']   # keep a real counterflow section (the crossflow-zone credit is an estimate)
                cands.append((ok, r_['vol_L'] if ok else 1e9, r_))
    cands.sort(key=lambda t: (not t[0], t[1]))
    best = cands[0][2]
    # update the losses with the sized core, HX and outlet; re-run the cycle
    hx = hx_size(M_H, best['Th_out_C'], 100.0, best['H'], best['W'])
    DP['rec_hot'] = best['dph_core_Pa'] / P_AMB + 0.0012              # + inlet plenum/perforated plate + outlet hood (~120 Pa)
    DP['rec_cold'] = (best['dpc_core_Pa'] + best['dpc_dist_Pa'] + 1500.0) / P2
    DP['hx_hot'] = hx['dp_Pa'] / P_AMB
R['dp'] = {k: v * 100 for k, v in DP.items()}
R['dp']['FPT_back_pressure_total_pct'] = (DP['exhaust_box_C'] + DP['rec_hot'] + DP['hx_hot'] + DP['stack']) * 100
R['dp']['compressor_to_combustor_pct'] = (1 - (1 - DP['collector_E2']) * (1 - DP['rec_cold']) * (1 - DP['comb_hot_E2'])) * 100
R['R_C2'] = {k: v for k, v in best.items()}
R['R_C2']['candidates_ok'] = sum(1 for c in cands if c[0]); R['R_C2']['budget'] = dict(dph_core_max_Pa=DPH_CORE_MAX, dpc_max_pct=DPC_MAX * 100)
c15 = cycle(15.0, best['eps_net'], DP)
hx = hx_size(c15['mg'], best['Th_out_C'], 100.0, best['H'], best['W'])
R['HX_C2'] = hx

# =====================================================================================================================
# 5. performance at 15 / 30 / 40 C (fixed geometry; eps from the 15 C sizing, constant-cp cycle; real-gas HX duty at 15 C)
# =====================================================================================================================
rows = []
K_HW = hx['Q_kW'] * 1e3 / c15['Q_hw']                                         # real-gas / constant-cp hot-water duty (15 C)
for T in (15.0, 30.0, 40.0):
    c = cycle(T, best['eps_net'], DP)
    c['Q_hw_cycle_model'] = c['Q_hw']; c['Q_hw'] = c['Q_hw'] * K_HW; c['eta_tot'] = (c['P_el'] + c['Q_hw']) / c['Q_fuel']
    c['Q_cooling_absorption'] = 0.70 * c['Q_hw']                                 # single-effect absorption chiller COP ~0.7 (as vb_cycle)
    rows.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()})
R['performance'] = rows
R['K_hot_water_real_over_cycle'] = K_HW
R['performance_note'] = ('constant-cp project cycle (concept_study constants) with the actual E2 / C exhaust / R-C2 / HX-C2 losses; '
                         'Q_hw = cycle value x %.3f (real-gas / constant-cp at 15 C), to a 100 C stack.' % K_HW + ' Real-gas R-C2 hot outlet at 15 C: %.0f C '
                         '(cycle model %.0f C) -> HX-C2 real duty %.1f kW' % (best['Th_out_C'], rows[0]['T_rec_hot_out'] - 273.15, hx['Q_kW']))
c0 = cycle(15.0, 0.80, dict(DP, collector_E2=0.0, comb_hot_E2=0.045, rec_cold=0.025, rec_hot=0.035, exhaust_box_C=0.0, hx_hot=0.015, stack=0.005))
R['reference_concept_model_15C'] = dict(P_el_kW=c0['P_el'] / 1e3, eta_el=c0['eta_el'], note='same function with the concept_study default losses')

# =====================================================================================================================
# 6. layout (ENG mm) for the CAD: R-C2 sits on the version-C DN200 outlet (x 201.5, face z 390), hot gas UP
# =====================================================================================================================
H_mm, W_mm, L_mm = best['H'] * 1e3, best['W'] * 1e3, best['Ltot'] * 1e3
X0 = -80.0                                           # core west face (stack along x): C1 nozzle at x -11 needs >= 70 mm to the end cap
LAY = dict(
    exhaust_flange=dict(x=201.5, z=390.0, DN=200, D=320.0, K=280.0, n=8, hole=18.0, pipe_od=219.1),
    # DN200 PN6 flange + bought standard axial expansion joint + round-to-rectangle transition with a perforated plate (no box plenum, no skirt)
    inlet=dict(z_flange=(390.0, 410.0), z_joint=(410.0, 470.0), z_trans=(470.0, 560.0), perf_plate_z=548.0, wall=3.0),
    # ONE brazed plate-fin block (bought to our drawing), 20 mm bolting frames top and bottom, bolt-on header boxes over the cold windows
    core=dict(x=(X0, X0 + H_mm), y=(-W_mm / 2, W_mm / 2), z=(570.0, 570.0 + L_mm), frame=20.0, frame_rim=25.0, stack_axis='x', layer_width_axis='y',
              flow='+z (hot up, cold down)', window_len=best['Ld'] * 1e3, end_bar=best['end_bar'] * 1e3, n_modules=1),
    headers=dict(north=dict(y=(W_mm / 2, 360.0), nozzle_xy=(-9.0, 290.0), DN=100), south=dict(y=(-W_mm / 2, -410.0), nozzle_xy=(55.0, -340.0), DN=125),
                 height=110.0, wall=3.0, note='box header bolted (gasket) to the core side frame around the cold window, nozzle + flange on its BOTTOM'),
    # bought standard finned-tube exhaust economiser (envelope): rectangular inlet flange on the core top frame, DN200 outlet on top
    hx=dict(z=(570.0 + L_mm + 20.0, 570.0 + L_mm + 20.0 + 520.0), body_x=(X0 - 10.0, X0 + H_mm + 10.0), body_y=(-W_mm / 2 - 20.0, W_mm / 2 + 20.0),
            cone_h=80.0, water_DN=32, duty_kW=hx['Q_kW'], rows=hx['n_rows'], tubes_per_row=hx['n_tubes_per_row']),
    stack=dict(DN=200, D=320.0),
    risers=dict(C1=dict(xy=(-9.0, 290.0), DN=100, hose_L=300.0), C2=dict(xy=(55.0, -340.0), DN=125, hose_L=300.0)),
    insulation=dict(recup_mm=50.0, headers_mm=30.0, risers_C1_mm=20.0, risers_C2_mm=30.0),
    frame=dict(rails_y=(-110.0, 110.0), rails_x=(-230.0, 590.0), x_cols=(-200.0, 560.0), y_cols=(-185.0, 185.0), z_top=(380.0, 420.0), z_base=(-310.0, -250.0)),
)
LAY['core']['z_hdr_top'] = LAY['core']['z'][1] - LAY['core']['end_bar'] - LAY['core']['window_len'] / 2
LAY['core']['z_hdr_bot'] = LAY['core']['z'][0] + LAY['core']['end_bar'] + LAY['core']['window_len'] / 2
R['layout'] = LAY
# E2-C2 port changes (relative to sim/engine/e2_design.json)
E2C2 = dict(C1=dict(side='north, boot up', rect_x=(-26.0, 7.5), rect_z=(-40.0, 115.0), boot_y=(230.0, 350.0), boot_x=(-69.0, 51.0), boot_z_top=130.0,
                    nozzle_xy=(-9.0, 290.0), face_z=170.0, DN=100, PN=16, pipe_od=114.3, pipe_t=2.0, flange=(220.0, 180.0, 8, 18.0, 20.0), t_wall=2.5,
                    y_rect=230.0, face_y=290.0, round_centre_xz=(-9.0, 170.0),
                    why='ear north at mid-height, boot turns UP outside the exhaust insulation (|y| > 211 above z 200); round DN100 flange only'),
            C2=dict(side='south, boot up', rect_x=(47.0, 95.0), rect_z=(-239.0, -40.0), boot_y=(290.0, 390.0), boot_x=(5.0, 105.0),
                    nozzle_xy=(55.0, -340.0), face_z=2.0, DN=125, PN=16, pipe_od=139.7, pipe_t=2.0, flange=(250.0, 210.0, 8, 18.0, 22.0), t_wall=3.0,
                    y_rect=-290.0, face_y=-340.0, round_axis_xz=(55.0, 2.0),
                    why='south duct (x 47..95 clears the mid-flange nuts and the exhaust insulation x >= 116), boot turns UP at y -340; round DN125 flange only'))
E2C2['a_liner_pins'] = (30.0, 160.0, 300.0)                                       # variant A 255 deg is inside the south C2 duct
R['construction_comparison_eps080'] = dict(note='E4 model (sim/engine/e4_recuperator_calc.run_comparison) at eps 0.80 / 0.75, hot <= 1000 Pa, cold <= 2400 Pa, W 0.30',
    plate_fin_OSF=dict(vol_L=50.0, core_kg=129.1), primary_surface_welded=dict(vol_L=36.1, core_kg=28.6, note='foil folding dies + automated edge welding'),
    straight_tube_6x0p3=dict(vol_L=167.9, core_kg=270.6, tubes=3941, eps075_vol_L=130.0, eps075_kg=215.8), SLM_gyroid=dict(vol_L=31.8, core_kg=99.6))
A_c2 = (E2C2['C2']['rect_x'][1] - E2C2['C2']['rect_x'][0]) * (E2C2['C2']['rect_z'][1] - E2C2['C2']['rect_z'][0]) * 1e-6
rhoR = c15['P2'] * 0.95 / (287.0 * c15['T2r'])
E2C2['C2_port_velocity'] = (c15['ma'] * (1 - BETA)) / (rhoR * A_c2); E2C2['C2_port_dump_kPa'] = 0.5 * rhoR * E2C2['C2_port_velocity'] ** 2 / 1e3
R['E2_C2'] = E2C2
json.dump(dict(layout=LAY, E2_C2=E2C2, R_C2={k: best[k] for k in ('W', 'H', 'nc', 'nh', 'fin_hot', 'Lcf', 'Ld', 'Ltot', 'end_bar')},
               HX_C2=dict(HX, **{k: hx[k] for k in ('n_tubes_per_row', 'n_rows', 'm3_h')})),
          open(os.path.join(HERE, 'c2_design.json'), 'w'), indent=1)
json.dump(R, open(os.path.join(HERE, 'c2_results.json'), 'w'), indent=1, default=str)

if __name__ == '__main__':
    b = best
    print('=== GR180 C2: version C + R-C2 (eps %.3f) + HX-C2 ===' % b['eps_net'])
    print('losses %%: %s' % {k: round(v, 2) for k, v in R['dp'].items()})
    print('R-C2: fin %s, W %.3f x H(stack) %.3f x L %.3f m (Lcf %.3f), %d+%d layers, %.0f L, core %.1f kg, NTU %.2f, eps %.3f, Q %.1f kW, Tc_out %.0f C, Th_out %.0f C'
          % (b['fin_hot'], b['W'], b['H'], b['Ltot'], b['Lcf'], b['nc'], b['nh'], b['vol_L'], b['mass']['total'], b['NTU'], b['eps_net'], b['Q_kW'], b['Tc_out_net_C'], b['Th_out_C']))
    print('      dp hot core %.0f Pa, cold core %.0f + distributors %.0f Pa; feasible candidates %d' % (b['dph_core_Pa'], b['dpc_core_Pa'], b['dpc_dist_Pa'], R['R_C2']['candidates_ok']))
    print('HX-C2: Q %.1f kW, water %.2f m3/h (DN32 %.2f m/s), %d rows x %d tubes, height %.0f mm, Vmax %.1f m/s, h %.0f, dp %.0f Pa, tubes %.1f kg'
          % (hx['Q_kW'], hx['m3_h'], hx['V_water_DN32'], hx['n_rows'], hx['n_tubes_per_row'], hx['height_m'] * 1e3, hx['Vmax'], hx['h_gas'], hx['dp_Pa'], hx['mass_tubes_kg']))
    for r in rows:
        print('  %4.0f C: P_shaft %.2f kW, P_el %.2f kW, gas %.2f m3/h (%.1f kW), eta_el %.1f %%, Q_hw %.1f kW, eta_tot %.1f %%, T2r %.0f C, TOT %.0f C, rec hot out %.0f C'
              % (r['T_amb_C'], r['P_shaft'] / 1e3, r['P_el'] / 1e3, r['gas_m3h'], r['Q_fuel'] / 1e3, r['eta_el'] * 100, r['Q_hw'] / 1e3, r['eta_tot'] * 100,
                 r['T2r'] - 273.15, r['Th_in'] - 273.15, r['T_rec_hot_out'] - 273.15))
    print('reference (concept_study default losses, same function): %.2f kW, %.1f %%' % (c0['P_el'] / 1e3, c0['eta_el'] * 100))
    print('E2-C2: C2 port %.1f m/s, dump %.2f kPa' % (E2C2['C2_port_velocity'], E2C2['C2_port_dump_kPa']))
    print('layout: core x %.0f..%.0f, y %.0f..%.0f, z %.0f..%.0f; HX z %.0f..%.0f' % (LAY['core']['x'] + LAY['core']['y'] + LAY['core']['z'] + LAY['hx']['z']))
