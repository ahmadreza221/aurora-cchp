#!/usr/bin/env python3
"""GR180-CCHP  E4 RECUPERATOR - thermal-hydraulic sizing, construction comparison, mechanical life, transients.

Run (pure python3 >= 3.9, no third-party packages):
    python3 sim/engine/e4_recuperator_calc.py            # full report, writes cad_out/engine/E4/E4_calc_results.json
    python3 sim/engine/e4_recuperator_calc.py --quick    # skips the fin-geometry search (uses the frozen design)

Design point = docs/06 sec.2 continuous point, taken directly from sim/life_study.point(115k rpm, TIT 800 C,
intake 15 C, 50 m, no booster, 'target' efficiencies).  The recuperator is sized with REAL gas properties:
  * cp(T) of N2/O2/Ar/CO2/H2O from Cengel Table A-2c polynomials, exhaust composition from 2.24 g/s CH4 burnt in
    0.395 kg/s air; transport properties: Sutherland (air) for both streams (lean exhaust, error < 3 %).
  * NOTE: the project cycle (concept_study.cycle) uses constant cp (air 1005, gas 1148 J/kgK).  With those the duty is
    159 kW and the hot outlet 262 C; with real cp the SAME temperatures 165->566 C / 610 C give 169 kW, a hot outlet
    of ~220 C and a capacity-rate ratio Cr = 0.97 (not 0.87), i.e. NTU ~8.1 instead of ~6.  We size for the real case.

Methods (all documented in docs/engine/E4_recuperator.md):
  * 1-D counterflow marching model with local properties (exact exponential element), offset-strip-fin j/f of
    Manglik & Bergles (1995), fin efficiency tanh(mL)/mL, Kroeger longitudinal-conduction penalty, maldistribution
    and fouling allowances; crossflow distributor zones credited with 50 % of the counterflow UA.
  * Delta-p: core friction + Kays & London entrance/exit + acceleration, distributors, headers, plenums, ducts, bellows.
  * Constructions compared: (a) brazed plate-fin OSF, (b) welded primary surface (cross-wavy), (c) SLM gyroid 316L,
    (d) small-tube shell-and-tube.
  * Life: Larson-Miller creep (347H), 1-D transient core model for start / trip / stop -> thermal fatigue at the
    header and plenum welds (Manson universal slopes + 10 % rule), oxidation allowance, thermal growth -> bellows.
  * Cycle impact via concept_study.cycle (its fixed dp line is parameterised at import; identical at defaults).
"""
import math, json, os, sys, inspect, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'sim'))
import concept_study as cs          # noqa: E402
import life_study as lsd            # noqa: E402

OUT_DIR = os.path.join(ROOT, 'cad_out', 'engine', 'E4')
QUICK = '--quick' in sys.argv
RES = {}                                        # everything that goes to the JSON
def sec(t): print('\n' + '=' * 100 + '\n' + t + '\n' + '=' * 100)

# =====================================================================================================================
# 0. Design point from the project cycle
# =====================================================================================================================
N1, TIT_C, TAMB_C, ALT = 115e3, 800.0, 15.0, 50.0
DP = lsd.point(N1, TIT_C, 'target', T_amb_C=TAMB_C, alt_m=ALT, booster=False)
PA = 101325.0 * (1 - 2.25577e-5 * ALT) ** 5.25588
P2 = PA * (1 - 0.01) * DP['PR']                    # compressor delivery = recuperator cold inlet
PH_OUT = PA * (1 + 0.015 + 0.005)                  # recuperator hot outlet (CHP HX + stack downstream)
PH_IN = PA * (1 + 0.035 + 0.015 + 0.005)           # FPT exit = recuperator hot inlet
M_C, M_F = DP['ma'], DP['mf']
M_H = M_C + M_F
TC_IN, TC_OUT_SPEC, TH_IN = DP['T2'], DP['T2r'], DP['T_hot']
EPS_SPEC = (TC_OUT_SPEC - TC_IN) / (TH_IN - TC_IN)
DPC_MAX, DPH_MAX = 0.025 * P2, 0.035 * PA          # exactly the cycle-model definition (dp_rc of P2, dp_rh of p_amb)

# =====================================================================================================================
# 1. Gas properties (real cp, composition)
# =====================================================================================================================
CPP = {'N2': (28.90, -0.1571e-2, 0.8081e-5, -2.873e-9, 28.013), 'O2': (25.48, 1.520e-2, -0.7155e-5, 1.312e-9, 31.999),
       'CO2': (22.26, 5.981e-2, -3.501e-5, 7.469e-9, 44.010), 'H2O': (32.24, 0.1923e-2, 1.055e-5, -3.595e-9, 18.015),
       'Ar': (20.786, 0.0, 0.0, 0.0, 39.948)}                                    # Cengel A-2c, kJ/kmol K
OMEGA = 0.0          # intake humidity [kg/kg dry]; the cycle model is dry. 0.010 (coil exit) changes eps by < 0.0005

def air_moles(m, omega=OMEGA):
    Md = 0.7808 * 28.013 + 0.2095 * 31.999 + 0.0093 * 39.948 + 0.0004 * 44.010
    md = m / (1 + omega); n = md / Md
    return {'N2': 0.7808 * n, 'O2': 0.2095 * n, 'Ar': 0.0093 * n, 'CO2': 0.0004 * n, 'H2O': md * omega / 18.015}

class Gas:
    def __init__(self, moles):
        self.m = sum(v * CPP[k][4] for k, v in moles.items())
        self.w = {k: v * CPP[k][4] / self.m for k, v in moles.items()}
        self.R = 8314.462 / (self.m / sum(moles.values()))
        self.y = {k: v / sum(moles.values()) for k, v in moles.items()}
    def cp(self, T):
        return 1e3 * sum(w * (a + b * T + c * T * T + d * T ** 3) / M for k, w in self.w.items() for a, b, c, d, M in [CPP[k]])
    def h(self, T):
        return 1e3 * sum(w * (a * T + b * T * T / 2 + c * T ** 3 / 3 + d * T ** 4 / 4) / M
                         for k, w in self.w.items() for a, b, c, d, M in [CPP[k]])
    def T_of_h(self, hv, T=600.0):
        for _ in range(30):
            dT = (self.h(T) - hv) / self.cp(T); T -= dT
            if abs(dT) < 1e-7: break
        return T

def mu(T): return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)          # Sutherland
def kgas(T): return 0.0241 * (T / 273.15) ** 1.5 * (273.15 + 194.0) / (T + 194.0)

AIR = Gas(air_moles(M_C))
_ex = air_moles(M_C); _nf = M_F / 16.043
_ex['O2'] -= 2 * _nf; _ex['CO2'] += _nf; _ex['H2O'] += 2 * _nf
EXH = Gas(_ex)

# metals (temperature T in C)
def k347(Tc): return 14.6 + 0.0145 * Tc
def cp347(Tc): return 500.0 + 0.17 * Tc
def E347(Tc): return (195.0 - 0.075 * Tc) * 1e3          # MPa
def a347(Tc): return (16.0 + 0.0034 * Tc) * 1e-6          # mean 20..T
RHO = {'347H': 7960.0, 'IN625': 8440.0, '316L': 7990.0, 'S355': 7850.0, 'BNi2': 7900.0}

# =====================================================================================================================
# 2. Heat-transfer surfaces
# =====================================================================================================================
class OSF:
    """Offset strip fin, Manglik & Bergles (1995) j and f (Fanning), Re on Dh = 4shl/[2(sl+hl+th)+ts]."""
    kind = 'OSF'
    def __init__(self, name, p, t, b, l, mat='347H'):
        self.name, self.p, self.t, self.b, self.l, self.mat = name, p, t, b, l, mat
        self.s, self.h = p - t, b - t
        s, h = self.s, self.h
        A = 2 * (s * l + h * l + t * h) + t * s
        self.Dh = 4 * s * h * l / A
        self.sigma = s * h / (p * b)                       # free-flow area / layer frontal area
        self.beta = A / (p * b * l)                        # wetted area / layer volume  [m2/m3]
        self.ffin = (2 * h * l + 2 * t * h + t * s) / A    # secondary (fin) share of the area
        self.metal = t * (b + s) / (p * b)                 # fin metal volume fraction of the layer
        self.fpi = 25.4e-3 / p
    def jf(self, Re, Pr=0.7):
        a, d, g = self.s / self.h, self.t / self.l, self.t / self.s
        j = 0.6522 * Re ** -0.5403 * a ** -0.1541 * d ** 0.1499 * g ** -0.0678 * \
            (1 + 5.269e-5 * Re ** 1.340 * a ** 0.504 * d ** 0.456 * g ** -1.055) ** 0.1
        f = 9.6243 * Re ** -0.7422 * a ** -0.1856 * d ** 0.3053 * g ** -0.2659 * \
            (1 + 7.669e-8 * Re ** 4.429 * a ** 0.920 * d ** 3.767 * g ** 0.236) ** 0.1
        return j, f
    def eta_o(self, hc, Tm_C):
        m = math.sqrt(2 * hc / (k347(Tm_C) * self.t) * (1 + self.t / self.l))
        mL = m * (self.b / 2 - self.t)
        return 1 - self.ffin * (1 - math.tanh(mL) / mL)
    def desc(self):
        return '%s: OSF p %.2f mm (%.1f fpi), t %.2f, b %.2f, strip %.1f -> Dh %.2f mm, sigma %.3f, beta %.0f m2/m3' % (
            self.name, self.p * 1e3, self.fpi, self.t * 1e3, self.b * 1e3, self.l * 1e3, self.Dh * 1e3, self.sigma, self.beta)

class Duct:
    """Generic laminar duct surface with constant fRe and Nu times enhancement (primary surface: eta_o = 1)."""
    kind = 'duct'
    def __init__(self, name, Dh, fRe, Nu, Ef=1.0, Eh=1.0):
        self.name, self.Dh, self.fRe, self.Nu, self.Ef, self.Eh = name, Dh, fRe, Nu, Ef, Eh
    def jf(self, Re, Pr=0.7):
        f_lam = self.fRe / Re; f_turb = 0.079 * Re ** -0.25
        Nu = self.Nu * self.Eh
        if Re > 2300: Nu = max(Nu, 0.023 * Re ** 0.8 * Pr ** 0.4)
        return Nu / (Re * Pr ** (1 / 3)), max(f_lam, f_turb) * self.Ef
    def eta_o(self, hc, Tm_C): return 1.0

class Gyroid:
    """Sheet-gyroid TPMS (SLM).  Nu = 0.325 Re^0.70 Pr^0.36, f_Darcy = 2.577 Re^-0.095 (fit of published gyroid
    channel data, e.g. Iyer et al. 2022 - uncertainty +-30 %, must be verified on a printed coupon)."""
    kind = 'TPMS'
    def __init__(self, name, a, t):
        self.name, self.a, self.t = name, a, t
        self.Sv = 3.091 / a                                       # gyroid area per volume
        self.phi = (1 - t * self.Sv) / 2                          # each fluid's volume fraction
        self.Dh = 4 * self.phi / self.Sv
    def jf(self, Re, Pr=0.7):
        Nu = 0.325 * Re ** 0.70 * Pr ** 0.36
        return Nu / (Re * Pr ** (1 / 3)), 2.577 * Re ** -0.095 / 4
    def eta_o(self, hc, Tm_C): return 1.0

def fRe_rect(alpha):          # Shah & London fully-developed laminar rectangular duct, alpha <= 1
    return 24 * (1 - 1.3553 * alpha + 1.9467 * alpha ** 2 - 1.7012 * alpha ** 3 + 0.9564 * alpha ** 4 - 0.2537 * alpha ** 5)

# =====================================================================================================================
# 3. Core model: per unit length quantities -> marching solver
# =====================================================================================================================
class Core:
    """Ac/Ah free-flow areas, Pc/Ph wetted area per unit length, Ak metal cross-section (longitudinal conduction),
    Rw wall resistance per unit length [mK/W], Lcf counterflow length, Ld crossflow distributor zone length (each end)."""
    def __init__(self, name, sc, sh, Ac, Ah, Pc, Ph, Ak, Rw, Lcf, Ld, frontal_h, mass_core, dims, extra=None):
        self.__dict__.update(dict(name=name, sc=sc, sh=sh, Ac=Ac, Ah=Ah, Pc=Pc, Ph=Ph, Ak=Ak, Rw=Rw, Lcf=Lcf, Ld=Ld,
                                  frontal_h=frontal_h, mass_core=mass_core, dims=dims, extra=extra or {}))
        self.Gc, self.Gh = M_C / Ac, M_H / Ah

RF_H, RF_C = 2.0e-5, 0.0               # fouling allowances [m2K/W] (lean natural-gas exhaust / filtered air)
CREDIT_D = 0.5                         # share of counterflow UA credited to the crossflow distributor zones
DEPS_MAL = 0.004                       # effectiveness allowance for header/plenum maldistribution (+-10 % layer flow)

def local(core, Tc, Th):
    """local film coefficients and UA per unit length."""
    Rec, Reh = core.Gc * core.sc.Dh / mu(Tc), core.Gh * core.sh.Dh / mu(Th)
    Prc, Prh = mu(Tc) * AIR.cp(Tc) / kgas(Tc), mu(Th) * EXH.cp(Th) / kgas(Th)
    jc, fc = core.sc.jf(Rec, Prc); jh, fh = core.sh.jf(Reh, Prh)
    hc = jc * core.Gc * AIR.cp(Tc) / Prc ** (2 / 3); hh = jh * core.Gh * EXH.cp(Th) / Prh ** (2 / 3)
    Tm = 0.5 * (Tc + Th) - 273.15
    eoc, eoh = core.sc.eta_o(hc, Tm), core.sh.eta_o(hh, Tm)
    UA = 1.0 / (1 / (eoc * hc * core.Pc) + RF_C / core.Pc + core.Rw + RF_H / core.Ph + 1 / (eoh * hh * core.Ph))
    return dict(Rec=Rec, Reh=Reh, hc=hc, hh=hh, eoc=eoc, eoh=eoh, fc=fc, fh=fh, UA=UA, jc=jc, jh=jh)

def march_from_hot(core, Tc_out, dx=0.004, Lmax=3.0):
    """Required counterflow length for a given cold outlet temperature (hot end known: Th_in, Tc_out)."""
    Th, Tc, x = TH_IN, Tc_out, 0.0
    dpc = dph = 0.0; prof = []
    rc = P2 / (AIR.R * Tc); rh = PH_IN / (EXH.R * Th)
    while Tc > TC_IN and x < Lmax:
        L = local(core, Tc, Th)
        Cc, Ch = M_C * AIR.cp(Tc), M_H * EXH.cp(Th)
        k = L['UA'] * (1 / Ch - 1 / Cc); dT0 = Th - Tc
        q = L['UA'] * dT0 * ((1 - math.exp(-k * dx)) / k if abs(k * dx) > 1e-12 else dx)
        Tcn = Tc - q / Cc
        if Tcn < TC_IN:                        # partial last step
            fr = (Tc - TC_IN) / (Tc - Tcn); dxe = dx * fr; q *= fr; Tcn = TC_IN
        else:
            dxe = dx
        rho_c = P2 / (AIR.R * Tc); rho_h = PH_OUT / (EXH.R * Th)
        dpc += 4 * L['fc'] * dxe / core.sc.Dh * core.Gc ** 2 / (2 * rho_c)
        dph += 4 * L['fh'] * dxe / core.sh.Dh * core.Gh ** 2 / (2 * rho_h)
        prof.append((x, Th, Tc, L)); Th -= q / Ch; Tc = Tcn; x += dxe
    return dict(L=x, Th_out=Th, dpc=dpc, dph=dph, prof=prof)

def kroeger_penalty(NTU, lam):
    """Kroeger (1967) balanced counterflow: eps(lam=0) - eps(lam)."""
    if lam <= 0: return 0.0
    ln = lam * NTU; r = math.sqrt(ln / (1 + ln))
    phi = r * math.tanh(NTU / (r * (1 + ln)))
    e0 = NTU / (1 + NTU); e1 = 1 - 1 / (1 + NTU * (1 + lam * phi) / (1 + ln))
    return e0 - e1

def entrance_exit(G, sigma, rho_in, rho_out):
    """Kays & London (laminar) core entrance/exit + acceleration.  Kc, Ke approximated from K&L Fig. 5-3."""
    Kc = 0.8 - 0.4 * sigma; Ke = (1 - sigma) ** 2 - 0.25 * sigma
    return G ** 2 / 2 * ((1 - sigma ** 2 + Kc) / rho_in + 2 * (1 / rho_out - 1 / rho_in) - (1 - sigma ** 2 - Ke) / rho_out)

def size_core(core, eps_net):
    """Find the counterflow length so that the NET effectiveness (after conduction + maldistribution) = eps_net.
    Returns core with Lcf set and a result dict."""
    deps = DEPS_MAL + 0.002
    for _ in range(4):
        e_raw = min(eps_net + deps, 0.985)
        Tc_out = TC_IN + e_raw * (TH_IN - TC_IN)
        m = march_from_hot(core, Tc_out)
        Leff = m['L']
        core.Lcf = max(Leff - 2 * CREDIT_D * core.Ld, 0.02)
        Ltot = core.Lcf + 2 * core.Ld + 2 * core.extra.get('end_bar', 0.0)
        UA = sum(p[3]['UA'] for p in m['prof']) * Leff / max(len(m['prof']), 1)
        Cmin = M_C * AIR.cp(0.5 * (TC_IN + Tc_out))
        NTU = UA / Cmin
        lam = k347(350) * core.Ak / (Ltot * Cmin)
        dcond = kroeger_penalty(NTU, lam)
        deps = DEPS_MAL + dcond
    return finish(core, m, e_raw, NTU, lam, dcond, UA)

def finish(core, m, e_raw, NTU, lam, dcond, UA):
    Ltot = core.Lcf + 2 * core.Ld + 2 * core.extra.get('end_bar', 0.0)
    Tc_out = TC_IN + e_raw * (TH_IN - TC_IN)
    # hot side: friction over the full length (distributor zones have the same hot fin) + entrance/exit/acceleration
    dph_f = m['dph'] * Ltot / m['L']
    rh_in, rh_out = PH_IN / (EXH.R * TH_IN), PH_OUT / (EXH.R * m['Th_out'])
    sig_h = core.Ah / core.frontal_h
    dph_ee = entrance_exit(core.Gh, sig_h, rh_in, rh_out)
    # cold side core: friction (counterflow part only; the distributor zones are computed in the header model)
    dpc_f = m['dpc'] * core.Lcf / m['L']
    rc_in, rc_out = P2 / (AIR.R * TC_IN), P2 / (AIR.R * Tc_out)
    dpc_acc = core.Gc ** 2 * (1 / rc_out - 1 / rc_in)
    prof = m['prof']
    res = dict(eps_raw=e_raw, eps_net=e_raw - DEPS_MAL - dcond, dcond=dcond, lam=lam, NTU=NTU, UA=UA,
               Th_out=m['Th_out'], Tc_out=Tc_out, Q=M_C * (AIR.h(Tc_out) - AIR.h(TC_IN)), Leff=m['L'], Lcf=core.Lcf,
               Ltot=Ltot, dph_core=dph_f + dph_ee, dph_fric=dph_f, dph_ee=dph_ee, dpc_core=dpc_f + dpc_acc,
               Rec=(prof[-1][3]['Rec'], prof[0][3]['Rec']), Reh=(prof[-1][3]['Reh'], prof[0][3]['Reh']),
               hc=(prof[-1][3]['hc'], prof[0][3]['hc']), hh=(prof[-1][3]['hh'], prof[0][3]['hh']),
               eoc=(prof[-1][3]['eoc'], prof[0][3]['eoc']), eoh=(prof[-1][3]['eoh'], prof[0][3]['eoh']),
               Ac_area=core.Pc * (core.Lcf + 2 * core.Ld), Ah_area=core.Ph * Ltot, prof=prof)
    return res

# ---------------------------------------------------------------------------------------------------------------------
# (a) plate-fin builder
# ---------------------------------------------------------------------------------------------------------------------
T_P, T_CAP, W_SB = 0.40e-3, 2.0e-3, 5.0e-3          # parting sheet, cap sheet, side-bar width
L_WIN = 0.085                                         # cold window / distributor-zone length (each end)
EB_HOT, EB_COLD = 0.040, 0.022                       # cold-layer end bars at the hot / cold face (window starts this far inside;
END_BAR = 0.5 * (EB_HOT + EB_COLD)                    #  sized so the header half-pipes R75 / R62 stay inside the core faces)

def plate_fin(fc, fh, W, nc, Lcf=0.3, Ld=L_WIN, name='a'):
    nh = nc + 1                                       # outermost layers are hot (low-pressure) layers
    Wf = W - 2 * W_SB
    H = nc * fc.b + nh * fh.b + (nc + nh - 1) * T_P + 2 * T_CAP
    Ac, Ah = nc * Wf * fc.b * fc.sigma, nh * Wf * fh.b * fh.sigma
    Pc, Ph = nc * Wf * fc.b * fc.beta, nh * Wf * fh.b * fh.beta
    nps = nc + nh - 1
    Ak = nps * W * T_P + 2 * W * T_CAP + nc * Wf * fc.b * fc.metal + nh * Wf * fh.b * fh.metal + (nc * fc.b + nh * fh.b) * 2 * W_SB
    Rw = T_P / (k347(400) * nps * Wf)
    c = Core(name, fc, fh, Ac, Ah, Pc, Ph, Ak, Rw, Lcf, Ld, frontal_h=W * H, mass_core=0, dims=dict(W=W, H=H, nc=nc, nh=nh),
             extra=dict(end_bar=END_BAR))
    return c

def plate_fin_mass(core):
    fc, fh, W, nc, nh = core.sc, core.sh, core.dims['W'], core.dims['nc'], core.dims['nh']
    Ltot, Wf, Ld = core.Lcf + 2 * core.Ld + 2 * END_BAR, W - 2 * W_SB, core.Ld
    nps = nc + nh - 1
    r = RHO['347H']
    m = dict(fins_cold=r * nc * Wf * fc.b * fc.metal * core.Lcf,
             dist_fins_cold=r * nc * Wf * fc.b * (0.15e-3 * (fc.b + 1.85e-3) / (2.0e-3 * fc.b)) * 2 * Ld,
             fins_hot=r * nh * Wf * fh.b * fh.metal * Ltot,
             parting_sheets=r * nps * W * Ltot * T_P, cap_sheets=r * 2 * W * Ltot * T_CAP,
             side_bars=r * (nc * fc.b + nh * fh.b) * 2 * W_SB * Ltot, end_bars_cold=r * nc * fc.b * END_BAR * Wf * 2)
    m['braze_BNi2'] = 0.035 * sum(m.values())
    m['total'] = sum(m.values())
    return m

def cold_distributors(core, res):
    """Crossflow distributor zones (cold side), windows on one face of the layer.  Plain rectangular distributor fin
    p 2.0, t 0.15 mm; flow traverses the layer width W with linearly decreasing mass flux (mean G^2 factor 1/3)."""
    fc, W, nc = core.sc, core.dims['W'], core.dims['nc']
    p, t = 2.0e-3, 0.15e-3; s, h = p - t, fc.b - t
    sig = s * h / (p * fc.b); Dh = 4 * s * h / (2 * (s + h))
    Aw = nc * core.Ld * fc.b * sig
    G = M_C / Aw
    out = {}
    for tag, T, Kturn in (('inlet', TC_IN, 1.2), ('outlet', res['Tc_out'], 1.0)):
        rho = P2 / (AIR.R * T); Re = G * Dh / mu(T)
        f = max(fRe_rect(min(s, h) / max(s, h)) / Re, 0.079 * Re ** -0.25)
        q = G ** 2 / (2 * rho)
        out[tag] = dict(G=G, Re=Re, q=q, dp=(4 * f * W / Dh / 3 + Kturn) * q, v=G / rho)
    out['total'] = out['inlet']['dp'] + out['outlet']['dp']
    out['window_area'] = Aw
    return out

# =====================================================================================================================
# 4. Construction comparison
# =====================================================================================================================
def run_comparison(eps_net, W):
    sec('4. CONSTRUCTION COMPARISON  (same duty, eps_net %.3f, core dp budgets: hot <= %.0f Pa, cold <= %.0f Pa, layer width/depth W = %.2f m)'
        % (eps_net, DPH_CORE, DPC_CORE, W))
    out = {}
    # ---- (a) plate-fin, chosen fins (see section 5) -------------------------------------------------------------
    ca = plate_fin(FIN_C, FIN_H, W, NC_DESIGN, Ld=L_WIN); ra = size_core(ca, eps_net)
    ma = plate_fin_mass(ca)
    out['a'] = dict(name='(a) brazed plate-fin OSF, counterflow + crossflow headers', W=W, H=ca.dims['H'], L=ra['Ltot'],
                    vol=W * ca.dims['H'] * ra['Ltot'], Ac=ra['Ac_area'], Ah=ra['Ah_area'], mass=ma['total'],
                    dph=ra['dph_core'], dpc=ra['dpc_core'] + cold_distributors(ca, ra)['total'], eps=ra['eps_net'],
                    Dh='%.2f/%.2f' % (FIN_C.Dh * 1e3, FIN_H.Dh * 1e3), mat='347H, BNi-2 vacuum braze')
    # ---- (b) primary surface, cross-wavy (Capstone-like) foil 0.10 mm ------------------------------------------
    tf, bc, bh, phiA = 0.10e-3, 1.0e-3, 1.8e-3, 1.25
    sc = Duct('PS-air', 2 * bc / phiA, 14.0, 3.0, Ef=2.4, Eh=2.0); sh = Duct('PS-gas', 2 * bh / phiA, 14.0, 3.0, Ef=2.4, Eh=2.0)
    best = None
    for npair in range(40, 400, 4):
        Hs = npair * (bc + bh + 2 * tf) + 2 * 1.0e-3
        Ac, Ah = npair * W * bc, npair * W * bh
        Pc = Ph = npair * 2 * phiA * W
        Ak = npair * 2 * phiA * W * tf
        c = Core('b', sc, sh, Ac, Ah, Pc, Ph, Ak, tf / (k347(400) * npair * 2 * phiA * W), 0.3, 0.06, W * Hs, 0, dict(W=W, H=Hs))
        r = size_core(c, eps_net)
        dpc = r['dpc_core'] * 1.25          # + cell-inlet manifold / turning (approx.)
        if r['dph_core'] <= DPH_CORE and dpc <= DPC_CORE:
            mass = RHO['347H'] * npair * 2 * phiA * W * r['Ltot'] * tf * 1.20        # + 20 % cell edge bars/welds
            best = dict(name='(b) welded primary surface, cross-wavy foil cells', W=W, H=Hs, L=r['Ltot'], vol=W * Hs * r['Ltot'],
                        Ac=r['Ac_area'], Ah=r['Ah_area'], mass=mass, dph=r['dph_core'], dpc=dpc, eps=r['eps_net'],
                        Dh='%.2f/%.2f' % (sc.Dh * 1e3, sh.Dh * 1e3), mat='347 foil 0.10 mm, laser/microplasma welded', npair=npair)
            break
    out['b'] = best
    # ---- (c) SLM gyroid 316L -----------------------------------------------------------------------------------
    gy = Gyroid('gyroid a4.0/t0.35', 4.0e-3, 0.35e-3)
    best = None
    for Hs in [0.30 + 0.02 * i for i in range(60)]:
        Af = W * Hs
        c = Core('c', gy, gy, gy.phi * Af, gy.phi * Af, gy.Sv * Af, gy.Sv * Af, Af * (1 - 2 * gy.phi),
                 gy.t / (16.0 * gy.Sv * Af), 0.3, 0.04, Af, 0, dict(W=W, H=Hs))
        r = size_core(c, eps_net)
        if r['dph_core'] <= DPH_CORE and r['dpc_core'] * 1.3 <= DPC_CORE:
            V = Af * r['Ltot']
            mass = RHO['316L'] * V * (1 - 2 * gy.phi) * 1.45          # + 45 % integrated manifolds / module flanges
            nmod = math.ceil(Hs / 0.20) * math.ceil(W / 0.20) * math.ceil(r['Ltot'] / 0.20)
            best = dict(name='(c) SLM gyroid TPMS modules, 316L (<=200 mm cubes)', W=W, H=Hs, L=r['Ltot'], vol=V, Ac=r['Ac_area'],
                        Ah=r['Ah_area'], mass=mass, dph=r['dph_core'], dpc=r['dpc_core'] * 1.3, eps=r['eps_net'],
                        Dh='%.2f/%.2f' % (gy.Dh * 1e3, gy.Dh * 1e3), mat='SLM 316L, walls 0.35 mm', modules=nmod)
            break
    out['c'] = best
    # ---- (d) shell-and-tube, small tubes 6 x 0.3 -----------------------------------------------------------------
    do, ti, P = 6.0e-3, 0.30e-3, 7.5e-3
    di = do - 2 * ti
    Acell = math.sqrt(3) / 2 * P ** 2
    Dh_s = 4 * (Acell - math.pi * do ** 2 / 4) / (math.pi * do)
    st_t = Duct('tube', di, 16.0, 4.36 * 1.15)                        # +15 % developing-flow
    st_s = Duct('shell', Dh_s, 18.5, 7.0, Ef=1.4, Eh=1.2)             # axial bundle P/D 1.25 + rod baffles
    best = None
    for Hs in [0.30 + 0.02 * i for i in range(80)]:
        N = int(W * Hs / Acell)
        c = Core('d', st_t, st_s, N * math.pi * di ** 2 / 4, N * (Acell - math.pi * do ** 2 / 4), N * math.pi * di,
                 N * math.pi * do, N * math.pi * (do ** 2 - di ** 2) / 4, ti / (k347(400) * N * math.pi * (do - ti)), 0.3, 0.10,
                 W * Hs, 0, dict(W=W, H=Hs))
        r = size_core(c, eps_net)
        if r['dph_core'] * 1.2 <= DPH_CORE and r['dpc_core'] <= DPC_CORE:
            mt = RHO['347H'] * N * math.pi * (do ** 2 - di ** 2) / 4 * r['Ltot']
            mts = RHO['347H'] * 2 * W * Hs * 0.020 * 0.65                 # 2 tubesheets 20 mm, 35 % holes
            msh = RHO['347H'] * 2 * (W + Hs) * r['Ltot'] * 3e-3 + 0.3 * mt  # shell + rod baffles
            best = dict(name='(d) shell-and-tube, %d tubes 6x0.3 mm, rod baffles' % N, W=W, H=Hs, L=r['Ltot'], vol=W * Hs * r['Ltot'],
                        Ac=r['Ac_area'], Ah=r['Ah_area'], mass=mt + mts + msh, dph=r['dph_core'] * 1.2, dpc=r['dpc_core'],
                        eps=r['eps_net'], Dh='%.2f/%.2f' % (di * 1e3, Dh_s * 1e3), mat='347H tubes, 2N tube-sheet joints', ntubes=N)
            break
    out['d'] = best
    print('%-58s %6s %6s %6s %7s %6s %6s %7s %6s %6s %6s %s' % ('construction', 'W m', 'H m', 'L m', 'vol L', 'Ac m2', 'Ah m2', 'core kg',
                                                                'dph Pa', 'dpc Pa', 'eps', 'Dh c/h mm'))
    for k in 'abcd':
        o = out[k]
        if o is None: print(k, 'no feasible design in range'); continue
        print('%-58s %6.3f %6.3f %6.3f %7.1f %6.1f %6.1f %7.1f %6.0f %6.0f %6.3f %s' % (o['name'][:58], o['W'], o['H'], o['L'], o['vol'] * 1e3,
              o['Ac'], o['Ah'], o['mass'], o['dph'], o['dpc'], o['eps'], o['Dh']))
    # qualitative matrix (scores 1..5, weights sum 1)
    crit = [('life: thermal fatigue + creep + oxidation at 610 C, 60 kh', 0.25), ('leak tightness / reliability', 0.15),
            ('thermal performance / compactness', 0.15), ('mass', 0.05), ('manufacture in Iran or non-US import', 0.20),
            ('inspection & repair', 0.10), ('schedule / development risk', 0.10)]
    sc_ = {'a': [4, 4, 5, 4, 3, 3, 3], 'b': [5, 4, 4, 5, 1, 2, 1], 'c': [2, 2, 3, 3, 3, 1, 2], 'd': [4, 3, 2, 1, 4, 4, 4]}
    print('\nDecision matrix (1 = poor .. 5 = best)')
    print('%-58s %5s %4s %4s %4s %4s' % ('criterion', 'wt', 'a', 'b', 'c', 'd'))
    for i, (cn, w) in enumerate(crit):
        print('%-58s %5.2f %4d %4d %4d %4d' % (cn, w, sc_['a'][i], sc_['b'][i], sc_['c'][i], sc_['d'][i]))
    tot = {k: sum(w * sc_[k][i] for i, (cn, w) in enumerate(crit)) for k in 'abcd'}
    print('%-58s %5s %4.2f %4.2f %4.2f %4.2f' % ('WEIGHTED SCORE', '', tot['a'], tot['b'], tot['c'], tot['d']))
    print('-> (a) chosen.  (b) is the best life concept but needs foil-folding dies + automated edge welding that no non-US\n'
          '   supplier offers for this size; (c) has 0.35 mm SLM 316L walls (porosity, low creep ductility at 600 C) and\n'
          '   ~%s printed modules; (d) is the most rugged but ~%.0fx heavier and does not fit the slab envelope.'
          % (out['c']['modules'] if out['c'] else '?', (out['d']['mass'] / out['a']['mass']) if out['d'] else 0))
    RES['comparison'] = dict(table={k: {kk: vv for kk, vv in (out[k] or {}).items()} for k in 'abcd'},
                             criteria=crit, scores=sc_, weighted=tot, chosen='a')
    return out

# =====================================================================================================================
# 5. Main design (a)
# =====================================================================================================================
EPS_NET_TARGET = 0.905           # guaranteed (net) effectiveness, >= 0.90 required
# Delta-p allocation inside the cycle budgets (rest: headers, plenums, ducts, bellows - computed in section 6)
DPH_CORE, DPC_CORE = 2600.0, 5200.0
T_HDR = 1.5e-3                   # cold header wall (half-pipe R70); thin = fast thermal response
RAMP_K_MIN = 15.0                # ECU limit for TOT (TE-505) rate of change above 300 C, start and normal stop
W_DESIGN = 0.25                  # layer width (= depth of the slab in ROOF y); see layout in docs/engine
FIN_C = OSF('C-OSF 1.2/2.0', 1.20e-3, 0.10e-3, 2.00e-3, 3.0e-3)
FIN_H = OSF('H-OSF 1.6/3.8', 1.60e-3, 0.12e-3, 3.80e-3, 3.2e-3)
NC_DESIGN = 96

def fin_search():
    sec('5a. FIN / CORE SEARCH (plate-fin, 347, t_fin 0.10 cold / 0.12 hot, W = %.2f m, eps_net %.3f)' % (W_DESIGN, EPS_NET_TARGET))
    colds = [OSF('C-OSF 1.0/1.6', 1.0e-3, 0.10e-3, 1.6e-3, 2.5e-3), OSF('C-OSF 1.2/2.0', 1.2e-3, 0.10e-3, 2.0e-3, 3.0e-3),
             OSF('C-OSF 1.4/2.4', 1.4e-3, 0.10e-3, 2.4e-3, 3.2e-3)]
    hots = [OSF('H-OSF 1.4/3.0', 1.4e-3, 0.12e-3, 3.0e-3, 3.0e-3), OSF('H-OSF 1.6/3.8', 1.6e-3, 0.12e-3, 3.8e-3, 3.2e-3),
            OSF('H-OSF 1.8/4.5', 1.8e-3, 0.12e-3, 4.5e-3, 3.5e-3)]
    for f in colds + hots: print('  ' + f.desc())
    print('\n  %-15s %-15s %4s %6s %6s %6s %7s %7s %7s %7s' % ('cold fin', 'hot fin', 'nc', 'H m', 'Lcf m', 'Ltot', 'vol L', 'mass kg', 'dph Pa', 'dpc Pa'))
    rows = []
    for fc in colds:
        for fh in hots:
            for nc in range(40, 132, 4):
                c = plate_fin(fc, fh, W_DESIGN, nc); r = size_core(c, EPS_NET_TARGET)
                dpc = r['dpc_core'] + cold_distributors(c, r)['total']
                if r['dph_core'] <= DPH_CORE and dpc <= DPC_CORE:
                    m = plate_fin_mass(c)['total']
                    rows.append((m, fc.name, fh.name, nc, c.dims['H'], r['Lcf'], r['Ltot'], W_DESIGN * c.dims['H'] * r['Ltot'] * 1e3, r['dph_core'], dpc))
                    print('  %-15s %-15s %4d %6.3f %6.3f %6.3f %7.1f %7.1f %7.0f %7.0f' % (fc.name, fh.name, nc, c.dims['H'], r['Lcf'],
                                                                                          r['Ltot'], rows[-1][7], m, r['dph_core'], dpc))
                    break
    rows.sort()
    print('\n  lightest feasible: %s + %s, nc %d (%.1f kg).  Selected: %s + %s, nc %d, because (1) cold Dh >= 1.3 mm\n'
          '  (braze-fillet clogging, contamination), (2) total core length <= 0.45 m (x-space between E3 flange H1 and the\n'
          '  exhaust flange at x 2.70, see layout) and (3) 1.6 mm hot pitch (cleaning by air lance, 0.12 mm fins).'
          % (rows[0][1], rows[0][2], rows[0][3], rows[0][0], FIN_C.name, FIN_H.name, NC_DESIGN))
    RES['fin_search'] = [dict(mass=r[0], cold=r[1], hot=r[2], nc=r[3], H=r[4], Lcf=r[5], Ltot=r[6], vol_L=r[7], dph=r[8], dpc=r[9]) for r in rows]

def rate(core, Lcf, N=120):
    """Forward rating of a FIXED geometry (shooting on the hot outlet temperature)."""
    core.Lcf = Lcf
    Leff = Lcf + 2 * CREDIT_D * core.Ld
    dx = Leff / N
    def run(Th_out):
        Th, Tc = Th_out, TC_IN
        for i in range(N):
            if Th <= Tc: return -1e9, Tc
            L = local(core, Tc, Th)
            Cc, Ch = M_C * AIR.cp(Tc), M_H * EXH.cp(Th)
            k = L['UA'] * (1 / Ch - 1 / Cc)
            q = L['UA'] * (Th - Tc) * ((math.exp(k * dx) - 1) / k if abs(k * dx) > 1e-12 else dx)
            Tc += q / Cc; Th += q / Ch
            if Th > TH_IN + 100: return 1e9, Tc
        return Th, Tc
    lo, hi = TC_IN + 0.5, TH_IN - 0.5
    for _ in range(50):
        mid = 0.5 * (lo + hi); Th1, Tc1 = run(mid)
        if Th1 > TH_IN: hi = mid
        else: lo = mid
    return (Tc1 - TC_IN) / (TH_IN - TC_IN), mid

# ---------------------------------------------------------------------------------------------------------------------
def main_design():
    global M_C, M_H
    sec('5. SELECTED DESIGN (a): brazed plate-fin, OSF both sides, 347H, 2 modules, hot gas straight east (H1 -> plenum -> core -> EXH),'
        ' cold air via south-face crossflow headers')
    core = plate_fin(FIN_C, FIN_H, W_DESIGN, NC_DESIGN)
    r = size_core(core, EPS_NET_TARGET)
    # round the counterflow length up to 5 mm and re-rate the fixed geometry
    Lcf = math.ceil(r['Lcf'] / 0.005) * 0.005
    e_raw_fixed, Th_out_fixed = rate(core, Lcf)
    core.Lcf = Lcf
    Tc_out_fixed = TC_IN + e_raw_fixed * (TH_IN - TC_IN)
    m = march_from_hot(core, Tc_out_fixed)
    r = finish(core, m, e_raw_fixed, r['NTU'], r['lam'], kroeger_penalty(r['NTU'], k347(350) * core.Ak / ((Lcf + 2 * core.Ld) * M_C * AIR.cp(640))), r['UA'])
    dist = cold_distributors(core, r)
    mass = plate_fin_mass(core)
    H, W, Ltot = core.dims['H'], W_DESIGN, r['Ltot']
    print('  ' + FIN_C.desc()); print('  ' + FIN_H.desc())
    print('  Correlations: Manglik & Bergles (1995) OSF  j = 0.6522 Re^-0.5403 a^-0.1541 d^0.1499 g^-0.0678 [1+5.269e-5 Re^1.340 a^0.504 d^0.456 g^-1.055]^0.1')
    print('                                              f = 9.6243 Re^-0.7422 a^-0.1856 d^0.3053 g^-0.2659 [1+7.669e-8 Re^4.429 a^0.920 d^3.767 g^0.236]^0.1')
    print('                (a = s/h, d = t/l, g = t/s), fin efficiency tanh(mL)/mL with L = b/2 - t, k_347(T)')
    print('  Layers: %d cold + %d hot (outermost = hot), parting sheet %.2f mm, cap sheet %.1f mm, side bars %.0f mm' % (
        core.dims['nc'], core.dims['nh'], T_P * 1e3, T_CAP * 1e3, W_SB * 1e3))
    print('  CORE: width W (ROOF y) %.3f m x stack H (ROOF z, layers horizontal) %.3f m x length L (ROOF x, hot flows east) %.3f m'
          % (W, H, Ltot))
    print('        = counterflow %.3f + 2 x %.3f distributor zones + end bars %.3f (hot face) / %.3f (cold face)' % (r['Lcf'], core.Ld, EB_HOT, EB_COLD))
    print('        built as 2 identical brazed modules of %d+%d layers (stack %.3f m each), stacked and welded at the cap sheets'
          % (core.dims['nc'] // 2, core.dims['nc'] // 2 + 1, H / 2))
    print('  Hot frontal area %.4f m2, free-flow cold %.4f / hot %.4f m2, G cold %.1f / hot %.1f kg/m2s' % (core.frontal_h, core.Ac, core.Ah, core.Gc, core.Gh))
    print('  Wetted area: cold %.1f m2, hot %.1f m2 (total %.1f m2), area density %.0f m2/m3' % (r['Ac_area'], r['Ah_area'],
          r['Ac_area'] + r['Ah_area'], (r['Ac_area'] + r['Ah_area']) / (W * H * Ltot)))
    print('  Re cold %.0f..%.0f, hot %.0f..%.0f (laminar/transitional OSF regime)' % (r['Rec'][0], r['Rec'][1], r['Reh'][0], r['Reh'][1]))
    print('  h cold %.0f..%.0f, hot %.0f..%.0f W/m2K, eta_o cold %.3f..%.3f, hot %.3f..%.3f' % (r['hc'][0], r['hc'][1], r['hh'][0], r['hh'][1],
          r['eoc'][0], r['eoc'][1], r['eoh'][0], r['eoh'][1]))
    print('  UA %.0f W/K, NTU %.2f (on C_cold), Cr %.3f, lambda (long. conduction) %.4f -> d_eps %.4f' % (
        r['UA'], r['NTU'], (M_C * AIR.cp(640)) / (M_H * EXH.cp(690)), r['lam'], r['dcond']))
    print('  EFFECTIVENESS: clean %.4f, net (- %.3f maldistribution - %.4f conduction) = %.4f  -> T_cold,out %.1f C, T_hot,out %.1f C, Q %.1f kW'
          % (r['eps_raw'], DEPS_MAL, r['dcond'], r['eps_net'], r['Tc_out'] - 273.15, r['Th_out'] - 273.15, r['Q'] / 1e3))
    Tc_net = TC_IN + r['eps_net'] * (TH_IN - TC_IN)
    Q_net = M_C * (AIR.h(Tc_net) - AIR.h(TC_IN)); Th_net = EXH.T_of_h(EXH.h(TH_IN) - Q_net / M_H)
    print('  -> guaranteed (net) point: T2r %.1f C, hot out %.1f C, Q %.1f kW' % (Tc_net - 273.15, Th_net - 273.15, Q_net / 1e3))
    print('  Core dp: hot %.0f Pa (friction %.0f + entrance/exit/accel %.0f), cold %.0f Pa (counterflow) + distributors %.0f (in %.0f / out %.0f)'
          % (r['dph_core'], r['dph_fric'], r['dph_ee'], r['dpc_core'], dist['total'], dist['inlet']['dp'], dist['outlet']['dp']))
    print('  Cold window: %.4f m2 per end, %.1f m/s in / %.1f m/s out' % (dist['window_area'], dist['inlet']['v'], dist['outlet']['v']))
    print('  Core mass (347H): ' + ', '.join('%s %.1f' % (k, v) for k, v in mass.items()) + ' kg')
    # metal temperature profile (for creep/oxidation)
    prof = m['prof']
    Tm_hot = 0.5 * (prof[0][1] + prof[0][2]) - 273.15
    Tm_cold = 0.5 * (prof[-1][1] + prof[-1][2]) - 273.15
    print('  Metal temperature: hot end ~%.0f C, cold end ~%.0f C' % (Tm_hot, Tm_cold))
    # part load check
    print('  Part load (same geometry): ', end='')
    pl = []
    for frac in (1.0, 0.75, 0.5):
        mc0, mh0 = M_C, M_H
        M_C, M_H = mc0 * frac, mh0 * frac
        core.Gc, core.Gh = M_C / core.Ac, M_H / core.Ah
        e, _ = rate(core, Lcf, N=60)
        pl.append((frac, e)); print('flow %.0f %% -> eps_clean %.3f; ' % (frac * 100, e), end='')
        M_C, M_H = mc0, mh0
        core.Gc, core.Gh = M_C / core.Ac, M_H / core.Ah
    print()
    RES['design'] = dict(fin_cold=vars(FIN_C) | {}, fin_hot=vars(FIN_H) | {}, nc=core.dims['nc'], nh=core.dims['nh'], t_p=T_P, t_cap=T_CAP,
                         w_sb=W_SB, W=W, H=H, Lcf=r['Lcf'], Ld=core.Ld, end_bar=END_BAR, eb_hot=EB_HOT, eb_cold=EB_COLD, Ltot=Ltot, n_modules=2,
                         t_header=T_HDR, Ac=core.Ac, Ah=core.Ah,
                         area_cold=r['Ac_area'], area_hot=r['Ah_area'], UA=r['UA'], NTU=r['NTU'], lam=r['lam'],
                         eps_clean=r['eps_raw'], eps_net=r['eps_net'], Tc_out_C=r['Tc_out'] - 273.15, Th_out_C=r['Th_out'] - 273.15,
                         Q_kW=r['Q'] / 1e3, Tc_out_net_C=Tc_net - 273.15, Th_out_net_C=Th_net - 273.15, Q_net_kW=Q_net / 1e3,
                         dph_core=r['dph_core'], dpc_core=r['dpc_core'], dpc_dist=dist['total'], Re_c=r['Rec'], Re_h=r['Reh'],
                         h_c=r['hc'], h_h=r['hh'], mass_core=mass, Tm_hot_end_C=Tm_hot, Tm_cold_end_C=Tm_cold, part_load=pl,
                         window_area=dist['window_area'])
    for kk in ('fin_cold', 'fin_hot'):
        RES['design'][kk] = {k: v for k, v in RES['design'][kk].items() if isinstance(v, (int, float, str))}
    return core, r, dist, mass, prof

# =====================================================================================================================
# 6. Headers, plenums, ducts -> total dp (geometry mirrors cad/engine/recuperator.py)
# =====================================================================================================================
PIPE = {'DN100': (114.3e-3, 2.0e-3), 'DN125': (139.7e-3, 2.0e-3), 'DN250': (273.0e-3, 2.0e-3), 'DN15': (21.3e-3, 2.0e-3)}
def pipe_A(dn): D, t = PIPE[dn]; return math.pi * (D - 2 * t) ** 2 / 4

def system_dp(core, r, dist):
    sec('6. HEADERS, PLENUMS, DUCTS - TOTAL PRESSURE LOSS (E4 scope: flange C1->C2 and H1->exhaust flange)')
    H, W = core.dims['H'], W_DESIGN
    rows = []
    def add(side, item, K, q, extra=0.0, note=''):
        rows.append((side, item, K, q, K * q + extra, note))
    # ---------- cold ----------
    rc1 = P2 / (AIR.R * TC_IN); rc2 = P2 / (AIR.R * r['Tc_out'])
    q1 = (M_C / pipe_A('DN100')) ** 2 / (2 * rc1); q2 = (M_C / pipe_A('DN125')) ** 2 / (2 * rc2)
    R_hdr = 0.070                                              # header half-pipe inner radius (CAD: header R70)
    A_hdr = math.pi * R_hdr ** 2 / 2 * 1.0
    qh1 = (M_C / 2 / A_hdr) ** 2 / (2 * rc1); qh2 = (M_C / 2 / A_hdr) ** 2 / (2 * rc2)
    R_hdr_ci, R_hdr_co = 0.062, 0.075                      # header half-pipe radii (CAD)
    A_ci, A_co = math.pi * R_hdr_ci ** 2 / 2, math.pi * R_hdr_co ** 2 / 2
    qh1 = (M_C / 2 / A_ci) ** 2 / (2 * rc1); qh2 = (M_C / 2 / A_co) ** 2 / (2 * rc2)
    Lc1, Lc2 = 1.30, 0.95                                    # duct lengths (CAD routes)
    add('cold', 'C1 duct DN100 (L %.2f m, 4 mitred bends R/D 0.9, bellows with liner)' % Lc1, 0.02 * Lc1 / 0.110 + 4 * 0.30 + 0.10, q1)
    add('cold', 'entry into cold-inlet header (tee split, sudden expansion)', 1.0, q1)
    add('cold', 'cold-inlet header along stack (friction + turning into windows)', 0.6, qh1)
    add('cold', 'core: inlet distributors (window, 90 deg turn, plain fin)', 0, 0, dist['inlet']['dp'])
    add('cold', 'core: counterflow OSF friction + acceleration', 0, 0, r['dpc_core'])
    add('cold', 'core: outlet distributors', 0, 0, dist['outlet']['dp'])
    add('cold', 'cold-outlet header -> DN125 nozzle (merge, contraction)', 0.6, qh2, 0.5 * q2)
    add('cold', 'C2 duct DN125 (L %.2f m, 3 mitred bends R/D 0.7, bellows with liner)' % Lc2, 0.02 * Lc2 / 0.136 + 3 * 0.40 + 0.10, q2)
    # ---------- hot ----------
    rh1 = PH_IN / (EXH.R * TH_IN); rh2 = PH_OUT / (EXH.R * r['Th_out'])
    qd1 = (M_H / pipe_A('DN250')) ** 2 / (2 * rh1); qd2 = (M_H / pipe_A('DN250')) ** 2 / (2 * rh2)
    qface1 = (M_H / (W * H)) ** 2 / (2 * rh1)
    phi_pp = 0.55
    K_pp = (0.707 * (1 - phi_pp) ** 0.375 + 1 - phi_pp) ** 2 / phi_pp ** 2    # Idelchik thin perforated plate
    add('hot', 'H1 bellows spool DN250 (IN625, flow liner, L 0.10 m)', 0.10, qd1)
    add('hot', 'dump into inlet plenum + 90 deg turn (vane cascade)', 1.0 + 0.35, qd1)
    add('hot', 'perforated distributor plate phi %.2f (at core face velocity)' % phi_pp, K_pp, qface1)
    add('hot', 'core: OSF friction + entrance/exit + acceleration', 0, 0, r['dph_core'])
    add('hot', 'outlet hood: collection + contraction to DN250 (short box)', 0.60, qd2)
    add('hot', 'exhaust spigot + bellows with liner to the package flange', 0.10, qd2)
    tot = {'cold': 0.0, 'hot': 0.0}
    print('  %-5s %-70s %6s %7s %8s' % ('side', 'item', 'K', 'q Pa', 'dp Pa'))
    for side, item, K, q, dp, note in rows:
        tot[side] += dp
        print('  %-5s %-70s %6.2f %7.1f %8.0f' % (side, item, K, q, dp))
    print('  COLD total %.0f Pa = %.2f %% of P2 (budget 2.5 %% = %.0f Pa)' % (tot['cold'], tot['cold'] / P2 * 100, DPC_MAX))
    print('  HOT  total %.0f Pa = %.2f %% of inlet, %.2f %% of p_amb as in the cycle (budget 3.5 %% p_amb = %.0f Pa)' % (
        tot['hot'], tot['hot'] / PH_IN * 100, tot['hot'] / PA * 100, DPH_MAX))
    print('  Velocities: DN100 %.1f m/s, DN125 %.1f m/s, H1 DN250 %.1f m/s, exhaust DN250 %.1f m/s, core face (hot in) %.1f m/s' % (
        M_C / rc1 / pipe_A('DN100'), M_C / rc2 / pipe_A('DN125'), M_H / rh1 / pipe_A('DN250'), M_H / rh2 / pipe_A('DN250'), M_H / rh1 / (W * H)))
    print('  Maldistribution indicators: header dynamic pressure / core cold dp = %.2f (inlet) %.2f (outlet) (< 0.15 ok);'
          ' (plate + core hot dp) / plenum inlet q = %.0f (> 10 ok)' % (qh1 / (r['dpc_core'] + dist['total']), qh2 / (r['dpc_core'] + dist['total']),
                                                                   (K_pp * qface1 + r['dph_core']) / qd1))
    RES['dp'] = dict(rows=[dict(side=a, item=b, K=c, q=d, dp=e) for a, b, c, d, e, f in rows], cold_Pa=tot['cold'], hot_Pa=tot['hot'],
                     cold_pct_P2=tot['cold'] / P2 * 100, hot_pct_inlet=tot['hot'] / PH_IN * 100, hot_pct_pamb=tot['hot'] / PA * 100,
                     perforated_plate_porosity=phi_pp)
    return tot

# =====================================================================================================================
# 7. Cycle sensitivity with concept_study.cycle
# =====================================================================================================================
def make_cycle_dp():
    src = inspect.getsource(cs.cycle)
    old = "dp_rc, dp_rh = (0.025, 0.035) if eps > 0 else (0.0, 0.0)"
    assert old in src, 'concept_study.cycle changed - update the patch'
    new = "dp_rc, dp_rh = (c.get('dp_rc', 0.025), c.get('dp_rh', 0.035)) if eps > 0 else (0.0, 0.0)"
    ns = dict(cs.__dict__)
    exec(src.replace(old, new).replace('def cycle(', 'def cycle_dp('), ns)
    return ns['cycle_dp']

def cycle_sensitivity(tot, eps_net):
    sec('7. CYCLE IMPACT (concept_study.cycle at the docs/06 design point: 115k rpm, TIT 800 C, intake 15 C, 50 m, no booster)')
    cyc = make_cycle_dp()
    th = (TAMB_C + 273.15) / 288.15; de = (1 - 2.25577e-5 * ALT) ** 5.25588
    PR, ma_c = lsd.line(N1 / math.sqrt(th)); ma = ma_c * de / math.sqrt(th)
    base = dict(lsd.EFF['target'], arch='fpt', ma=ma, PR=PR, TIT=TIT_C + 273.15, eps=0.90, T_amb=TAMB_C + 273.15, P_amb=101325.0 * de, booster=False)
    r0 = cs.cycle(base); r0p = cyc(base)
    assert abs(r0['P_el'] - r0p['P_el']) < 1e-6, 'patched cycle differs at defaults'
    def show(tag, c):
        r = cyc(c)
        print('  %-46s P_el %6.2f kW (%+5.2f)  fuel %6.1f kW (%+5.2f)  eta_el %5.2f %% (%+5.2f pt)  T2r %5.1f C' % (
            tag, r['P_el'] / 1e3, (r['P_el'] - r0['P_el']) / 1e3, r['Q_fuel'] / 1e3, (r['Q_fuel'] - r0['Q_fuel']) / 1e3,
            r['eta_el'] * 100, (r['eta_el'] - r0['eta_el']) * 100, r['T2r'] - 273.15))
        return r
    out = {}
    out['base'] = show('baseline eps 0.90, dp 2.5 % / 3.5 %', base)
    out['eps-0.01'] = show('eps -0.01 (0.89)', dict(base, eps=0.89))
    out['dpc+1'] = show('cold dp +1 %-point (3.5 % of P2)', dict(base, dp_rc=0.035))
    out['dph+1'] = show('hot dp +1 %-point (4.5 % of p_amb)', dict(base, dp_rh=0.045))
    out['both+1'] = show('both +1 %-point', dict(base, dp_rc=0.035, dp_rh=0.045))
    out['eps+0.01'] = show('eps +0.01 (0.91)', dict(base, eps=0.91))
    dpc_f, dph_f = tot['cold'] / P2, tot['hot'] / PA
    out['E4'] = show('E4 as designed: eps %.3f, dp %.2f %% / %.2f %%' % (eps_net, dpc_f * 100, dph_f * 100),
                     dict(base, eps=eps_net, dp_rc=dpc_f, dp_rh=dph_f))
    d = lambda k: ((out[k]['P_el'] - r0['P_el']) / 1e3, (out[k]['Q_fuel'] - r0['Q_fuel']) / 1e3, (out[k]['eta_el'] - r0['eta_el']) * 100,
                   (out[k]['eta_el'] - r0['eta_el']) * r0['Q_fuel'] / 1e3)
    print('  => sensitivity                 dP_el kW   dfuel kW   d_eta pt   P_el-equivalent at constant fuel kW')
    for tag, k in (('eps -0.01', 'eps-0.01'), ('cold dp +1 %-point', 'dpc+1'), ('hot dp +1 %-point', 'dph+1')):
        print('     %-26s %9.2f %10.2f %10.2f %12.2f' % ((tag,) + d(k)))
    print('     At fixed TIT an effectiveness loss costs FUEL (the FPT power is set by TIT and pressures), a pressure loss costs\n'
          '     POWER (lower FPT expansion ratio).  1 %-point of cold dp ~ 1 %-point of hot dp ~ 0.7 kW / 0.5 pt;\n'
          '     0.01 of eps ~ 2.2 kW fuel ~ 0.4 pt.')
    RES['cycle'] = {k: dict(P_el_kW=v['P_el'] / 1e3, eta_el=v['eta_el'], T2r_C=v['T2r'] - 273.15, T_hot_C=v['T_hot'] - 273.15)
                    for k, v in out.items()}
    RES['cycle']['per_unit'] = {k: dict(zip(('dP_el_kW', 'dfuel_kW', 'deta_pt', 'Pel_equiv_kW'), d(k))) for k in ('eps-0.01', 'dpc+1', 'dph+1')}
    return out

# =====================================================================================================================
# 8. Mechanical: pressure stresses, creep, oxidation
# =====================================================================================================================
LMP_347H = [(250, 19900), (200, 20575), (132, 21825), (82, 23075), (47, 24325), (25, 25575)]   # (MPa, T_K(20+log t_h))
def creep_hours(sig, T_C):
    pts = LMP_347H
    if sig >= pts[0][0]: P = pts[0][1]
    elif sig <= pts[-1][0]: P = pts[-1][1] + (math.log(pts[-1][0]) - math.log(sig)) / (math.log(pts[-2][0]) - math.log(pts[-1][0])) * (pts[-1][1] - pts[-2][1])
    else:
        for (s0, p0), (s1, p1) in zip(pts[:-1], pts[1:]):
            if s1 <= sig <= s0:
                P = p0 + (math.log(s0) - math.log(sig)) / (math.log(s0) - math.log(s1)) * (p1 - p0); break
    return 10 ** (P / (T_C + 273.15) - 20)

P_DES_COLD, P_DES_HOT = 0.35, 0.03          # MPa gauge design pressures: cold 3.5 barg (surge/overspeed), hot 0.3 barg
def mechanical(core, r, Tm_hot):
    sec('8. MECHANICAL: pressure stresses, creep (Larson-Miller 347H, C = 20, stress x 1.5), oxidation')
    fc, fh = core.sc, core.sh
    dp_op = (P2 - PH_IN) / 1e6
    items = []
    def it(name, sig_op, sig_des, T, note=''):
        life = creep_hours(1.5 * max(sig_op, 0.5), T)
        items.append((name, sig_op, sig_des, T, life, note))
    it('cold fin tension (Δp across parting sheets)', dp_op * fc.p / fc.t, P_DES_COLD * fc.p / fc.t, Tm_hot)
    it('parting sheet bending between fin legs', 0.5 * dp_op * (fc.s / T_P) ** 2, 0.5 * P_DES_COLD * (fc.s / T_P) ** 2, Tm_hot)
    it('braze joint fin/sheet (fillet ~0.3 mm/leg)', dp_op * fc.p / 0.3e-3, P_DES_COLD * fc.p / 0.3e-3, Tm_hot)
    it('hot fin compression (buckling margin: Euler >> 50x)', dp_op * fh.p / fh.t, P_DES_COLD * fh.p / fh.t, Tm_hot)
    Rh, th = 0.075, T_HDR
    pg_c = (P2 - PA) / 1e6
    it('cold-outlet header R75 x %.1f hoop (566 C), membrane' % (th * 1e3), pg_c * Rh / th, P_DES_COLD * Rh / th, r['Tc_out'] - 273.15)
    it('  same, header/core weld toe (secondary x3, creep uses x1)', pg_c * Rh / th, 3 * P_DES_COLD * Rh / th, r['Tc_out'] - 273.15)
    it('hot inlet plenum 3 mm walls, ribs @150 mm (plate, 0.07 barg op.)', 0.5 * 0.007 * (150 / 3) ** 2, 0.5 * P_DES_HOT * (150 / 3) ** 2, TH_IN - 273.15)
    it('H1 duct DN250 x 2 hoop + dead weight bending', 0.007 * 136 / 2 + 6.0, P_DES_HOT * 136 / 2 + 6.0, TH_IN - 273.15)
    it('C2 duct DN125 x 2 hoop (566 C)', pg_c * 69 / 2, P_DES_COLD * 69 / 2, r['Tc_out'] - 273.15)
    print('  %-60s %8s %8s %6s %14s' % ('item', 'op MPa', 'des MPa', 'T C', 'creep rupt. h'))
    for n, so, sd, T, life, note in items:
        print('  %-60s %8.2f %8.1f %6.0f %14s' % (n, so, sd, T, ('%.2e' % life) if life < 1e9 else '> 1e9'))
    print('  Proof/leak test: cold side 5.3 barg hydro (1.5 x 3.5) or 4.6 barg pneumatic, hot side 0.45 barg; He leak test per module.')
    print('  347H allowable (ASME II-D class) at 600 C ~ 85 MPa; all design stresses are below it; creep life >> 60,000 h for all\n'
          '  primary loads.  Creep is therefore NOT the design driver - thermal fatigue at start/stop and fin oxidation are.')
    # Robinson damage over a 60 kh mission (90 % at 610 C, 10 % at 625 C peak mode) for the worst item
    worst = max(items, key=lambda x: 1 / x[4])
    D = 0.9 * 60e3 / creep_hours(1.5 * worst[1], worst[3]) + 0.1 * 60e3 / creep_hours(1.5 * worst[1], worst[3] + 15)
    print('  Robinson creep damage, worst item "%s", 60 kh (10 %% in 815 C peak mode, +15 K): D = %.2e (<< 1)' % (worst[0].strip(), D))
    # oxidation of fins (parabolic, Cr2O3-former; water vapour accelerates: kp x 10 vs dry air)
    print('\n  Oxidation allowance (hot fins 0.12 mm, both faces in exhaust, metal %.0f C):' % Tm_hot)
    ox = []
    for tag, kp in (('dry-air kp 1e-14 g2/cm4s', 1e-14), ('humid exhaust kp 1e-13 (design)', 1e-13), ('breakaway onset kp 1e-12', 1e-12)):
        dm = math.sqrt(kp * 60e3 * 3600)                    # g/cm2
        rec = dm * (104 / 48) / 7.96 * 1e4                  # um metal per face (Cr2O3)
        ox.append((tag, rec)); print('    %-36s metal recession %.1f um/face -> %.0f %% of the hot fin after 60 kh' % (tag, rec, 2 * rec / (FIN_H.t * 1e6) * 100))
    print('  -> 0.12 mm hot fins (not 0.10) and metal <= 600 C keep the design case at ~%.0f %% section loss; breakaway is excluded\n'
          '     by the stabilised 18/10 grade below ~620 C metal.  Upgrade path if TOT is raised > 650 C: alloy 625 core.' % (2 * ox[1][1] / (FIN_H.t * 1e6) * 100))
    RES['mech'] = dict(items=[dict(item=a.strip(), sig_op=b, sig_des=c, T_C=d, creep_h=min(e, 1e12)) for a, b, c, d, e, f in items],
                       robinson_D=D, oxidation_um_per_face=dict((a, b) for a, b in ox))

# =====================================================================================================================
# 9. Transients: 1-D transient core model -> thermal fatigue at the header and plenum welds
# =====================================================================================================================
def transients(core, r, mass):
    sec('9. TRANSIENTS & THERMAL FATIGUE (1-D transient counterflow core, quasi-steady gas, header / skirt / side-bar nodes)')
    N = 24
    M_matrix = mass['total']
    Ci = M_matrix * cp347(400) / N
    eoh = 0.5 * (r['eoh'][0] + r['eoh'][1]); eoc = 0.5 * (r['eoc'][0] + r['eoc'][1])
    Gh0 = eoh * 0.5 * (r['hh'][0] + r['hh'][1]) * r['Ah_area'] / N         # W/K per cell, hot side, design flow
    Gc0 = eoc * 0.5 * (r['hc'][0] + r['hc'][1]) * r['Ac_area'] / N
    # hot-end attachments: (1) cold-outlet header half-pipe R70 x 1.5 mm, inside h ~100 W/m2K (window jets), insulated outside
    #                      (2) hot-inlet plenum skirt 1.2 mm U-lip, gas side h ~45 W/m2K, insulated outside (compliant)
    t_hdr, h_hdr, t_sk, h_sk = T_HDR, 120.0, 1.2e-3, 45.0
    tau_hdr = RHO['347H'] * cp347(500) * t_hdr / h_hdr
    tau_sk = RHO['347H'] * cp347(500) * t_sk / h_sk
    def sim(Tg_f, Tc_f, m_f, t_end, T0=None, dt=0.1):
        Tm = list(T0[0]) if T0 else [30.0] * N
        Thd, Tsk = (T0[1], T0[2]) if T0 else (30.0, 30.0)
        out = dict(hdr=[0.0, 0.0], sk=[0.0, 0.0], bar=[0.0, 0.0], t=[], Tm0=[], Tg=[])
        t = 0.0; k = 0
        def upd(key, v):
            out[key][0] = max(out[key][0], v); out[key][1] = min(out[key][1], v)
        while t <= t_end:
            mf = max(m_f(t), 0.05)
            Gh = Gh0 * mf ** 0.46; Gc = Gc0 * mf ** 0.46
            Ch = M_H * mf * EXH.cp(700); Cc = M_C * mf * AIR.cp(600)
            eh = 1 - math.exp(-Gh / Ch); ec = 1 - math.exp(-Gc / Cc)
            Tg = Tg_f(t); Th = Tg; qh = [0.0] * N
            for i in range(N):
                q = Ch * eh * (Th - Tm[i]); qh[i] = q; Th -= q / Ch
            Tc = Tc_f(t); qc = [0.0] * N
            for i in range(N - 1, -1, -1):
                q = Cc * ec * (Tm[i] - Tc); qc[i] = q; Tc += q / Cc
            for i in range(N):
                Tm[i] += dt * (qh[i] - qc[i]) / Ci
            Thd += dt * (Tc - Thd) / (tau_hdr / mf ** 0.8)
            Tsk += dt * (Tg - Tsk) / (tau_sk / mf ** 0.8)
            upd('hdr', Tm[0] - Thd); upd('sk', Tm[0] - Tsk)
            upd('bar', 0.35 * (Tg - Tc))                 # hot-layer vs cold-layer side bars at the hot end
            if k % 100 == 0: out['t'].append(t); out['Tm0'].append(Tm[0]); out['Tg'].append(Tg)
            t += dt; k += 1
        out['Tm_final'] = (Tm, Thd, Tsk)
        out['final'] = dict(hdr=Tm[0] - Thd, sk=Tm[0] - Tsk, bar=0.35 * (Tg - Tc))
        return out
    ramp = lambda T0, T1, rate, t: min(T1, T0 + rate * t) if T1 > T0 else max(T1, T0 - rate * t)
    ss = sim(lambda t: TH_IN - 273.15, lambda t: TC_IN - 273.15, lambda t: 1.0, 1500.0)
    steady = ss['final']
    T0 = ss['Tm_final']
    RAMP = RAMP_K_MIN / 60.0                             # K/s, ECU limit on TE-505 above 300 C
    TSTOP = 210.0 / RAMP + 30.0
    cases = {
        'start_ecu': ('start, ECU: TOT 150->610 C at %.0f K/min, flow 30->100 %% in 600 s' % RAMP_K_MIN,
                      lambda t: ramp(150, 610, RAMP, t), lambda t: ramp(40, 165, 0.3, t), lambda t: min(1.0, 0.3 + 0.7 * t / 600), 2400, None),
        'start_fast': ('start, uncontrolled: TOT 150->610 C in 60 s',
                       lambda t: ramp(150, 610, 460 / 60, t), lambda t: ramp(40, 165, 1.5, t), lambda t: min(1.0, 0.3 + 0.7 * t / 90), 1500, None),
        'stop_ecu': ('normal stop: TOT 610->400 C at %.0f K/min, then fuel off, spool-down' % RAMP_K_MIN,
                     lambda t: ramp(610, 400, RAMP, t) if t < TSTOP else 165 + (400 - 120 - 165) * math.exp(-(t - TSTOP) / 300),
                     lambda t: 165.0 if t < TSTOP else ramp(165, 40, 2.0, t - TSTOP),
                     lambda t: 1.0 - 0.6 * min(1.0, t / TSTOP) if t < TSTOP else max(0.15, 0.4 - 0.25 * (t - TSTOP) / 40), TSTOP + 1500, T0),
        'trip': ('trip from full load: TOT -200 K in 3 s, -> 165 C (tau 300 s), flow -> 15 % in 40 s',
                 lambda t: 165 + (610 - 200 * min(1, t / 3) - 165) * math.exp(-t / 300), lambda t: ramp(165, 40, 2.0, t),
                 lambda t: max(0.15, 1 - 0.85 * t / 40), 1200, T0)}
    print('  core matrix %.1f kg (%.0f kJ/K), cell tau %.1f s, global core tau M c / C_min %.0f s; header %.1f mm tau %.0f s; plenum skirt'
          ' 1.2 mm tau %.0f s' % (M_matrix, M_matrix * cp347(400) / 1e3, Ci / (Gh0 + Gc0), M_matrix * cp347(400) / (M_C * AIR.cp(600)), T_HDR * 1e3, tau_hdr, tau_sk))
    sims = {}
    print('  %-80s %13s %13s %13s' % ('case  (max / min temperature difference, K)', 'core-header', 'core-skirt', 'side bars'))
    for key, (name, Tg, Tc, mf, tend, Ti) in cases.items():
        o = sim(Tg, Tc, mf, tend, Ti); sims[key] = o
        print('  %-80s %6.0f/%6.0f %6.0f/%6.0f %6.0f/%6.0f' % (name[:80], o['hdr'][0], o['hdr'][1], o['sk'][0], o['sk'][1], o['bar'][0], o['bar'][1]))
    print('  steady state (design): core-header %.0f K, core-skirt %.0f K, side bars %.0f K' % (steady['hdr'], steady['sk'], steady['bar']))
    # ---- fatigue: Manson universal slopes for 347H at 600 C + Manson 10 %-rule (creep-fatigue), Miner sum
    Su, E, RA = 420.0, E347(600), 0.55; D = math.log(1 / (1 - RA))
    def Nf(de):
        lo, hi = 1.0, 1e14
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            if 3.5 * Su / E * mid ** -0.12 + D ** 0.6 * mid ** -0.6 > de: lo = mid
            else: hi = mid
        return mid
    loc = {'hdr': ('cold-outlet header / core weld', 0.5, 1.5), 'sk': ('hot-plenum U-skirt / core weld', 0.15, 1.5),
           'bar': ('side-bar stack braze (hot vs cold layer)', 0.5, 1.5)}
    years = 60e3 / 8000
    pairs = [('A: ECU start + normal stop', 'start_ecu', 'stop_ecu', 52 * years), ('B: ECU start + trip', 'start_ecu', 'trip', 25 * years),
             ('C: uncontrolled start + trip (to be prevented)', 'start_fast', 'trip', 0)]
    print('\n  Fatigue (strain range = Kw * Kc * alpha * dT_range / (1-nu); Universal Slopes 347H 600 C; 10 %-rule; Miner):')
    print('  %-44s %-42s %8s %10s %10s %6s' % ('location', 'cycle pair', 'de %', 'N_10%', 'n in 60kh', 'D'))
    Dsum = {}; table = []
    for lk, (lname, Kc, Kw) in loc.items():
        Dsum[lk] = 0.0
        for pname, a1, a2, n in pairs:
            hi_ = max(sims[a1][lk][0], sims[a2][lk][0], steady[lk]); lo_ = min(sims[a1][lk][1], sims[a2][lk][1], steady[lk])
            de = Kw * Kc * a347(550) * (hi_ - lo_) / 0.7
            N10 = 0.1 * Nf(de)
            Dsum[lk] += n / N10
            table.append(dict(location=lname, pair=pname, dT_range=hi_ - lo_, strain=de, N_10pct=N10, n=n))
            print('  %-44s %-42s %8.3f %10.3g %10.0f %6.3f' % (lname, pname, de * 100, N10, n, n / N10))
    print('  Miner sums (A + B, 10 %-rule):  ' + ',  '.join('%s %.3f' % (loc[k][0].split(' /')[0].split(' (')[0], v) for k, v in Dsum.items()))
    print('  Requirement: D <= 0.5 (factor 2 on cycles on top of the 10 %-rule ~ factor 20 overall, ASME-NH-like).')
    nC = {lk: [t for t in table if t['location'] == loc[lk][0] and t['pair'].startswith('C')][0]['N_10pct'] for lk in loc}
    ratio = [t for t in table if t['location'] == loc['hdr'][0] and t['pair'].startswith('A')][0]['N_10pct'] / nC['hdr']
    print('  One uncontrolled start + trip consumes as much life as %.1f normal (A) cycles at the header weld -> ECU interlock:\n'
          '  TE-505 rate <= %.0f K/min above 300 C (warm-up at idle), cool-down ramp to idle before fuel-off, purge/crank\n'
          '  air only after TOT < 250 C, alarm if TE-505 - TE-503 > 150 K during a start.' % (ratio, RAMP_K_MIN))
    RES['transient'] = dict(cases={k: dict(name=cases[k][0], core_header=sims[k]['hdr'], core_skirt=sims[k]['sk'], side_bars=sims[k]['bar'])
                                   for k in cases}, steady=steady, fatigue=table, miner=Dsum, ramp_K_per_min=RAMP_K_MIN,
                            tau=dict(header_s=tau_hdr, skirt_s=tau_sk, core_global_s=M_matrix * cp347(400) / (M_C * AIR.cp(600))),
                            history_start_ecu=dict(t=sims['start_ecu']['t'], Tm_hot_end=sims['start_ecu']['Tm0'], TOT=sims['start_ecu']['Tg']))
    return sims

# =====================================================================================================================
# 10. Thermal growth -> bellows; insulation; supports; hot-side purge volume
# =====================================================================================================================
def growth_insulation(core, r, tot):
    sec('10. THERMAL GROWTH, BELLOWS, INSULATION, SUPPORTS, PURGE')
    H, W, L = core.dims['H'], W_DESIGN, r['Ltot']
    Tm_avg = 0.5 * (RES['design']['Tm_hot_end_C'] + RES['design']['Tm_cold_end_C'])
    W, H, L = W_DESIGN, core.dims['H'], r['Ltot']
    # layout (cad/engine/recuperator.py): core x 2.075..2.52 (hot face west), z 0.45..1.09; FIXED POINT = hot-end cradle beam
    # (x ~2.13, centre y, core bottom z 0.45).  Core grows east (+x) and up (+z); plenum grows west from the core face.
    al = a347
    Tm_core = Tm_avg
    dx_core = al(Tm_core) * L * (Tm_core - 20) * 1e3                  # east face of the core vs fixed point
    dz_core = al(Tm_core) * H * (Tm_core - 20) * 1e3                   # top of the core (stack height)
    dy_core = al(590) * W * (590 - 20) * 1e3
    dz_plenum = al(600) * 0.15 * (600 - 20) * 1e3
    print('  Fixed point: hot-end cradle beam (x 2.13, core bottom).  Free growth: core length +%.1f mm (x, east), stack +%.1f mm (z),'
          ' width %.1f mm (y); plenum +%.1f mm (z at H1 height)' % (dx_core, dz_core, dy_core, dz_plenum))
    # engine flange movements (E3 published H1; E2 requested C1/C2), radial casing growth + axial from the engine feet
    eng = {'C1': (0.5, 0.0, -1.8), 'C2': (1.0, 0.0, 1.9), 'H1': (2.5, 3.1, 0.0)}
    e4 = {'C1': (al(300) * 0.34 * 280 * 1e3, -1.0, 0.3), 'C2': (0.6, -2.0, al(570) * 0.50 * 550 * 1e3),
          'H1': (-al(600) * 0.22 * 580 * 1e3, -al(600) * 0.125 * 580 * 1e3, dz_plenum), 'EXH': (dx_core + 0.6, 0.0, al(215) * 0.35 * 195 * 1e3)}
    duct = {'C1': (al(165) * 0.77 * 145 * 1e3, 0, 0), 'C2': (al(566) * 0.40 * 546 * 1e3, 0, 0), 'H1': (0, 0, 0)}
    bel = {}
    print('  %-5s %-26s %-26s %-26s %-34s' % ('joint', 'engine flange move mm', 'E4 nozzle move mm', 'own duct growth mm', 'bellows axial / lateral (x1.5 + 3 mm)'))
    axis = {'C1': 0, 'C2': 0, 'H1': 1}                                 # bellows axis: C1/C2 in the east-running leg (x), H1 along y
    for k in ('C1', 'C2', 'H1'):
        de = [e4[k][i] - eng[k][i] + duct[k][i] for i in range(3)]
        ax = abs(de[axis[k]]); lat = math.sqrt(sum(de[i] ** 2 for i in range(3) if i != axis[k]))
        bel[k] = (1.5 * ax + 3, 1.5 * lat + 3)
        print('  %-5s %-26s %-26s %-26s axial +-%.1f / lateral +-%.1f mm' % (k, '%.1f, %.1f, %.1f' % eng[k], '%.1f, %.1f, %.1f' % e4[k],
              '%.1f, %.1f, %.1f' % duct[k], bel[k][0], bel[k][1]))
    bel['EXH'] = (1.5 * e4['EXH'][0] + 3, 1.5 * e4['EXH'][2] + 3)
    print('  EXH   E4 own growth x %.1f / z %.1f mm -> bellows axial +-%.1f / lateral +-%.1f mm; the package sits on spring isolators:\n'
          '        HVAC must add a flexible joint on its side (axial +-15, lateral +-25 mm, e.g. fabric expansion joint).' % (
              e4['EXH'][0], e4['EXH'][2], bel['EXH'][0], bel['EXH'][1]))
    # insulation: microporous (Promat MICROTHERM class) + 0.5 mm stainless cladding; skin <= 60 C at 40 C enclosure air
    def k_mp(Tm): return 0.020 + 1.6e-5 * Tm
    def skin(Tin, t, Tamb, ho=10.0):
        Ts = Tamb + 10
        for _ in range(60):
            km = k_mp(0.5 * (Tin + Ts)); q = (Tin - Ts) / (t / km)
            Ts = Tamb + q / ho
        return Ts, q
    comp = [('H1 duct + bellows + hot-inlet plenum (610 C)', TH_IN - 273.15), ('cold-outlet header + C2 duct (566 C)', r['Tc_out'] - 273.15),
            ('core block (590..195 C, design 590 C bottom third)', RES['design']['Tm_hot_end_C']),
            ('outlet hood + exhaust duct (%.0f C)' % (r['Th_out'] - 273.15), r['Th_out'] - 273.15),
            ('cold-inlet header + C1 duct (165 C)', TC_IN - 273.15)]
    ins = {}
    print('  %-52s %6s %7s %8s %8s %8s' % ('component', 'T C', 't mm', 'skin@40', 'skin@46', 'q W/m2'))
    for name, T in comp:
        t = 0.010
        while skin(T, t, 40.0)[0] > 60.0: t += 0.005
        s40, q = skin(T, t, 40.0); s46, _ = skin(T, t, 46.0)
        ins[name] = t
        print('  %-52s %6.0f %7.0f %8.1f %8.1f %8.0f' % (name, T, t * 1e3, s40, s46, q))
    print('  Insulation = microporous silica panels/quilts (Promat MICROTHERM / PROMALIGHT class, EU) in a 0.5 mm 1.4301\n'
          '  cladding with lock-seams; removable boxes on flanges/bellows (stainless mesh + glass-cloth blankets).  Skin <= 60 C\n'
          '  at 40 C enclosure air (E5 ventilation, h_out 10 W/m2K); at 46 C roof air the skin reaches ~66 C (enclosure =\n'
          '  touch barrier, doors interlocked).')
    # heat loss
    A_total = 2 * (W + 0.14) * (H + 0.1) + 2 * (W + H + 0.2) * (L + 0.40) + 1.2
    Q_loss = A_total * 200
    print('  Total insulated area ~%.1f m2, heat loss ~%.2f kW (%.2f %% of duty) - inside the 2 %% hot-section loss of the cycle model' % (
        A_total, Q_loss / 1e3, Q_loss / RES['design']['Q_kW'] / 1e3 * 100))
    # supports
    m_wet = RES.get('mass_assembly_est', 0.0)
    print('  Supports: the core sits on a cradle of 2 transverse beams (hot end = FIXED/pinned, cold end = sliding in x) with\n'
          '  6 mm mica/vermiculite pads; plenum and hood stand on their own sliding legs (graphite-bronze slide plates + 25 mm\n'
          '  calcium-silicate thermal-break pads).  Skirts and bellows carry no load.  Low, wide block (z 0.45-1.09): no sway\n'
          '  struts needed; seismic hold-downs on all legs (slotted holes + clips).  First natural frequency > 30 Hz.')
    # purge volume (hot side), ISO 21789: purge before ignition
    V_hot = 0.10 * pipe_A('DN250') + W * (H + 0.04) * 0.34 + core.Ah * L + (W + 0.15) * H * 0.05 + 0.10 * pipe_A('DN250')
    print('  Hot-side volume E4 (H1 duct, plenum, core, hood, exhaust spool) ~%.3f m3 -> include in the ECU purge (>= 5 volume\n'
          '  changes of the whole exhaust path incl. HX-1, D-101 in bypass) before every light-off.' % V_hot)
    RES['growth'] = dict(dz_core_mm=dz_core, dx_core_mm=dx_core, dy_core_mm=dy_core, dz_plenum_mm=dz_plenum, fixed_point='hot-end cradle beam',
                         bellows={k: dict(axial_mm=v[0], lateral_mm=v[1]) for k, v in bel.items()}, engine_flange_moves_assumed=eng,
                         e4_nozzle_moves=e4)
    RES['insulation'] = dict(thickness_m={k: v for k, v in ins.items()}, Q_loss_kW=Q_loss / 1e3, k_microporous='0.020+1.6e-5*Tmean[C] W/mK',
                             skin_criterion='<= 60 C at 40 C enclosure air, h_out 10 W/m2K')
    RES['purge_volume_m3'] = V_hot

# =====================================================================================================================
def main():
    t0 = time.time()
    sec('0. DESIGN POINT (sim/life_study.point 115k / 800 C / 15 C / 50 m, target efficiencies, no booster)')
    print('  air %.4f kg/s, fuel %.2f g/s, gas %.4f kg/s;  T2 %.1f C, T2r(spec) %.1f C, TOT %.1f C  -> eps_spec %.4f' % (
        M_C, M_F * 1e3, M_H, TC_IN - 273.15, TC_OUT_SPEC - 273.15, TH_IN - 273.15, EPS_SPEC))
    print('  P2 %.3f bar, hot in %.4f / out %.4f bar abs;  budgets: cold 2.5 %% P2 = %.0f Pa, hot 3.5 %% p_amb = %.0f Pa (%.2f %% of inlet)' % (
        P2 / 1e5, PH_IN / 1e5, PH_OUT / 1e5, DPC_MAX, DPH_MAX, DPH_MAX / PH_IN * 100))
    print('  cycle-model (constant cp) duty %.1f kW, hot outlet %.1f C' % (DP['Q_rec'] / 1e3, DP['T_stack_in'] - 273.15))
    sec('1-3. REAL-GAS ENERGY BALANCE AND REQUIRED NTU')
    print('  exhaust composition (mole): ' + ', '.join('%s %.4f' % (k, v) for k, v in EXH.y.items()))
    Q = M_C * (AIR.h(TC_OUT_SPEC) - AIR.h(TC_IN)); Th_out = EXH.T_of_h(EXH.h(TH_IN) - Q / M_H)
    Cc = Q / (TC_OUT_SPEC - TC_IN); Ch = Q / (TH_IN - Th_out); Cr = Cc / Ch
    NTU_req = math.log((1 - EPS_SPEC * Cr) / (1 - EPS_SPEC)) / (1 - Cr)
    print('  real cp: cp_air(165..566) %.1f, cp_gas(%.0f..610) %.1f J/kgK;  Q = %.1f kW, hot outlet %.1f C, C_cold %.0f, C_hot %.0f W/K, Cr %.3f'
          % (Cc / M_C, Th_out - 273.15, Ch / M_H, Q / 1e3, Th_out - 273.15, Cc, Ch, Cr))
    print('  required NTU for eps %.3f, pure counterflow, mean properties: %.2f   (constant-cp cycle model: Cr %.3f -> NTU %.2f)' % (
        EPS_SPEC, NTU_req, M_C * 1005 / (M_H * 1148), math.log((1 - EPS_SPEC * M_C * 1005 / (M_H * 1148)) / (1 - EPS_SPEC)) / (1 - M_C * 1005 / (M_H * 1148))))
    print('  ** Interface note for HVAC/HX-1: with real gas properties the exhaust leaves E4 at ~%.0f C, not 262 C (same energy,\n'
          '     different cp).  HX-1 heat to 90 C stack: %.1f kW (real) vs %.1f kW (constant-cp model).' % (
              Th_out - 273.15, M_H * (EXH.h(Th_out) - EXH.h(363.15)) / 1e3, M_H * 1080 * (DP['T_stack_in'] - 363.15) / 1e3))
    RES['design_point'] = dict(m_air=M_C, m_fuel=M_F, m_gas=M_H, T2_C=TC_IN - 273.15, T2r_spec_C=TC_OUT_SPEC - 273.15, TOT_C=TH_IN - 273.15,
                               eps_spec=EPS_SPEC, P2_bar=P2 / 1e5, Ph_in_bar=PH_IN / 1e5, Ph_out_bar=PH_OUT / 1e5, dpc_max_Pa=DPC_MAX,
                               dph_max_Pa=DPH_MAX, Q_cycle_model_kW=DP['Q_rec'] / 1e3, Th_out_cycle_model_C=DP['T_stack_in'] - 273.15,
                               Q_real_kW=Q / 1e3, Th_out_real_C=Th_out - 273.15, Cr_real=Cr, NTU_required=NTU_req)
    if not QUICK: fin_search()
    core, r, dist, mass, prof = main_design()
    tot = system_dp(core, r, dist)
    run_comparison(EPS_NET_TARGET, W_DESIGN)
    cycle_sensitivity(tot, r['eps_net'])
    mechanical(core, r, RES['design']['Tm_hot_end_C'])
    transients(core, r, mass)
    growth_insulation(core, r, tot)
    sec('SUMMARY')
    d = RES['design']
    print('  Construction: brazed plate-fin, offset strip fins both sides, 347H/BNi-2, 2 modules, counterflow with crossflow cold headers')
    print('  Core %.3f (W, ROOF y) x %.3f (stack, ROOF z) x %.3f m (flow, ROOF x); %d+%d layers; area %.1f + %.1f m2; core %.1f kg'
          % (d['W'], d['H'], d['Ltot'], d['nc'], d['nh'], d['area_cold'], d['area_hot'], d['mass_core']['total']))
    print('  eps clean %.3f / net %.3f;  dp cold %.2f %% (%.0f Pa), hot %.2f %% of inlet (%.0f Pa);  Q %.0f kW;  hot out %.0f C'
          % (d['eps_clean'], d['eps_net'], RES['dp']['cold_pct_P2'], RES['dp']['cold_Pa'], RES['dp']['hot_pct_inlet'], RES['dp']['hot_Pa'],
             d['Q_net_kW'], d['Th_out_net_C']))
    c = RES['cycle']
    print('  Cycle: P_el %.2f kW / eta %.2f %% (baseline %.2f kW / %.2f %%)' % (c['E4']['P_el_kW'], c['E4']['eta_el'] * 100,
                                                                         c['base']['P_el_kW'], c['base']['eta_el'] * 100))
    print('  runtime %.0f s' % (time.time() - t0))
    os.makedirs(OUT_DIR, exist_ok=True)
    def clean(o):
        if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items() if k != 'prof'}
        if isinstance(o, (list, tuple)): return [clean(v) for v in o]
        if isinstance(o, float): return round(o, 6)
        return o
    with open(os.path.join(OUT_DIR, 'E4_calc_results.json'), 'w') as f:
        json.dump(clean(RES), f, indent=1, ensure_ascii=False)
    print('  wrote', os.path.join(OUT_DIR, 'E4_calc_results.json'))

if __name__ == '__main__':
    main()
