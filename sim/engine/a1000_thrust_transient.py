#!/usr/bin/env python3
"""AURORA-1000 transient axial thrust (rotor rev 1.3) and both sides of the thrust bearing (8 aft pads, n_in forward pads).

Lumped model, state = speed, two gas volumes, two rotor cavities, gas / wall / recuperator temperatures, governor, surge:
  compressor  speed lines of sim/engine/a1000_startup.py rescaled to the impeller detail design (PR 3.805, 165.9 kJ/kg),
              surge at the peak (x 0.80), choke at the diffuser throats (x 1.10, then stage 2 throttles), deep surge as a
              collapse of the pressure rise (G -> g_s in tau_s) with the plenum blowing back through the stalled stages;
              stage pressures (eyes, impeller tips) from the design log-fractions of the overall ratio
  volume A    collector + scroll pressure body + turbine outer casing + pipe to the recuperator (compressor delivery)
  volume B    recuperator cold side + hot pipe + combustor + scroll; A -> B and B -> NGV1 quadratic losses (2.7 / 3.9 %)
  blow-off    valve from A to the stack (trip and shutdown): needed, see BOV in the results
  turbine     row by row (a1000_startup.turbine) tabulated on corrected speed and expansion ratio: flow, row exit statics, work
  cavities    impeller 2 back face (feed orifice from A, r 200 labyrinth to the impeller tip, r 85 drum balance seal) and the
              turbine front cavity (balance seal in, rim seal out to the NGV1 exit); Martin labyrinths as in
              sim/engine/a1000_hot_section_calc.py, feed and rim areas set by the steady design pressures of the stack model;
              the other cavities follow the gas path (purge overpressure as in a1000_rotor_stack.thrust())
  heat        fuel shut-off (dead time + line bleed), combustor lag, scroll / liner / NGV1 metal giving heat back, recuperator
              air exit with the matrix lag (bought unit, eps 0.89 from the design temperatures)
  shaft       rotor + gearbox + generator (a1000_startup.j_total), grid-locked while the breaker is closed, reverse-power
              relay, starter, PI speed governor at no load
  forces      the 14 terms of a1000_rotor_stack.thrust() from the transient pressures, each scaled to its steady stack value
              at the design point (the model gives +2.46 kN aft there); + = aft (toward the turbine)
  bearing     unit load and minimum film of the loaded side at the instantaneous speed (a1000_rotor_stack.thrust_bearing
              formulas); transient criterion <= 3.5 MPa and >= 10 um on both sides (as the back-face-feed-lost case)
Cases: (a) load rejection + fuel trip (breaker open), (b) fuel trip with the breaker closed, (c) surge at full load,
       (d) start-up to full load, (e) normal shutdown and coast-down; plus volume / valve / surge-depth sensitivities.
Run:    python sim/engine/a1000_thrust_transient.py      (numpy, scipy, matplotlib)
Writes: sim/engine/fea/a1000_thrust_transient.json, docs/img/a1000_thrust_transient.png
"""
import json
import math
import os
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import fsolve

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_rotor_stack as RS                                # noqa: E402  (steady thrust terms, bearing formulas, geometry)
import a1000_startup as SU                                    # noqa: E402  (speed lines, row-by-row turbine, inertia)
sys.argv = _argv
G, A = RS.G, RS.A

P_AMB, T_AMB, R = SU.P_AMB, SU.T_AMB, 287.0
CPA, CPG, KA = SU.CP_A, SU.CP, SU.KA
M_D = SU.M_AIR                                                # 6.317 kg/s design air
OM_D = RS.OM                                                  # 15,000 rpm
J = SU.j_total()                                              # kg m2 at the HS shaft (rotor + gearbox + generator / 10^2)
STACK = json.load(open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')))
P_BRG = STACK['losses']['total_kW'] * 1e3                     # rotor bearings + seals at 15k (rev 1.3)
TIT_D, TIT_R = SU.TIT_D, 1243.15                              # stack design point 950 C; rating 985 kW at 970 C (docs/08 17)
P_SH_R = 985e3 / (0.985 * 0.97)                               # gearbox input at the rating (gearbox, generator efficiencies)
P_NL = 18e3                                                   # gearbox + generator no-load losses at 15k
LHV = 47.1e6

# compressor (detail design, sim/a1000_impeller_design.json)
IMP = json.load(open(os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')))['stages']
_c1, _c2 = IMP['C1']['performance'], IMP['C2']['performance']
P01_D, PCD_D = _c1['P01'], _c2['P_col']
PR_D = PCD_D / P01_D
W_DET = _c1['impeller']['dh0'] + _c2['impeller']['dh0']
ETA_DET = CPA * T_AMB * (PR_D ** KA - 1) / W_DET
DP_IN = 1 - P01_D / P_AMB
_L = math.log(PR_D)
H01_2 = math.log(_c2['P01'] / P01_D) / _L                     # log-fraction of the overall ratio at the stage 2 inlet
H21 = math.log(_c1['impeller']['P2'] / P01_D) / _L            # ... impeller 1 tip static
H22 = math.log(_c2['impeller']['P2'] / P01_D) / _L            # ... impeller 2 tip static
A2 = math.log(_c2['impeller']['P2'] / _c2['P01']) / math.log(PCD_D / _c2['P01'])   # within stage 2 (choke throttling)
T21_D, T012_D, T22_D, TCD_D = _c1['impeller']['T2'], _c2['T01'], _c2['impeller']['T2'], _c2['T02']
C11_D, C12_D = IMP['C1']['inducer']['c1'], IMP['C2']['inducer']['c1']
X_S, X_CH = SU.X_SURGE, 1.10                                  # surge (peak of the speed line), choke (diffuser throats 1.09/1.12)
C_SURGE = 8.5e-3                                              # m2: stalled stages as an orifice (design flow at the stage 2
                                                              # diffuser inlet dynamic head)
# gas volumes, losses, temperatures
VOL = dict(A=0.9, B=2.4, bf=1.0e-3, cf=3.0e-3)                # m3 (estimates, see SENS)
T_B, T_CF, N_POLY = 820.0, 650.0, 1.2                         # mass-mean temperature of B, front cavity; polytropic exponent
DP_COMB = 0.039                                               # combustor + scroll (docs/08 16.7)
DP_AB = 1 - SU.S1['P0_in'] / (PCD_D * (1 - DP_COMB))          # collector -> combustor inlet (recuperator cold side + pipes)
DP_HOT = SU.DP_HOT
T_RCX_D = 886.15                                              # recuperator air exit at 950 C (docs/08 16.1: 613 C)
# heat
TAU_C, FUEL_DEAD, FUEL_TAU = 0.05, 0.03, 0.06                 # combustor lag; fuel shut-off dead time, line bleed [s]
C_W, HA_W = 110e3, 1.8e3                                      # scroll + liner + NGV1 metal [J/K], gas-side hA at design [W/K]
TAU_R = 75.0                                                  # recuperator matrix lag at design flow [s]
# blow-off valve (A -> stack), trip / shutdown command
BOV = dict(D=0.125, Cd=0.80, dead=0.05, open=0.15)            # DN125, dead time, stroke [s]
# protection, control
RP_KW, RP_DELAY = 30.0, 2.0                                   # reverse power -3 % for 2 s opens the breaker
KP_GOV, KI_GOV = 4600.0, 900.0                                # K per unit speed error (and per s)
P_ST, N_ST, N_CUT = 70e3, 0.25, 0.60                          # starter power, full power from, cut-out
SURGE = dict(g=0.40, tau=0.020, t_det=0.10, C=C_SURGE)        # retained fraction of the pressure rise, collapse, detection
SENS = dict(vol_A=(0.5, 2.0), vol_B=(0.5, 2.0), cavities=(0.33, 3.0), bov_open=(0.10, 0.40), surge_g=(0.0, 0.20, 0.60),
            surge_tau=(0.010, 0.040), surge_reverse=(0.25,), surge_bound=(0.25,))
# surge_reverse: x the back-flow area of the stalled stages (the plenum holds while the stage pressures collapse);
# surge_bound: g 0 and x 0.25 together
UNIT_LIM, FILM_LIM = 3.5, 10.0                                # transient criterion (as the back-face-feed-lost case)

# thrust geometry (as in a1000_rotor_stack.thrust())
R_SEAL_IN, R_SPC, R_REAR = 48.0, 75.0, 56.0
R_S2 = G.ARM['rf'] + 1.0
RH1, RT1 = A.row_radius('R1', 0.0), A.row_radius('R1', 1.0)
RH2, RT2 = A.row_radius('R2', 0.0), A.row_radius('R2', 1.0)
R2_1, R2_2 = IMP['C1']['geometry']['r2'], IMP['C2']['geometry']['r2']
R1H_2 = IMP['C2']['geometry']['r1h']


# ================================================================================================ elements
def ssqrt(rho, d, eps=20.0):
    """signed sqrt(rho |d|), linear below eps Pa (orifice flow without the infinite slope at zero)"""
    return d / math.sqrt(abs(d) + eps) * math.sqrt(max(rho, 1e-6))


def lab(p1, p2, T, r_mm, cl_mm, n, Cd=0.70, carry=1.15):
    """Martin labyrinth with carry-over (as a1000_hot_section_calc.labyrinth), signed: + from p1 to p2"""
    sg = 1.0 if p1 >= p2 else -1.0
    pu, pd = (p1, p2) if p1 >= p2 else (p2, p1)
    A_ = 2 * math.pi * r_mm * 1e-3 * cl_mm * 1e-3; pr = pd / pu; x = 1 - pr * pr
    x = x * x / math.sqrt(x * x + 1e-10)                       # linear near zero flow
    return sg * carry * Cd * A_ * pu / math.sqrt(R * T) * math.sqrt(x / (n - math.log(pr)))


def orifice(p_up, T, p_dn, area):
    """compressible orifice [kg/s], choked below 0.528"""
    pr = max(min(p_dn / p_up, 1.0), 0.0); g = 1.4
    psi = 0.6847 if pr < 0.5283 else math.sqrt(2 * g / (g - 1) * max(pr ** (2 / g) - pr ** ((g + 1) / g), 0.0))
    return area * p_up / math.sqrt(R * T) * psi


def cmap(n, x):
    """detail-design speed line: corrected speed n, flow ratio x -> (PR collector / inlet, work J/kg, eta)"""
    w = W_DET * n * n * (1 + SU.C_PSI * (1 - x))
    eta = ETA_DET * (1 - SU.E_ETA * (x - 1) ** 2 - SU.S_ETA * (1 - n) ** 2)
    return (1 + eta * w / (CPA * T_AMB)) ** (1 / KA), w, eta


def stations(n, x, P1, pr, w, PA=None):
    """compressor station pressures / temperatures for overall ratio pr; PA below the choke ratio: stage 2 throttles"""
    L = math.log(max(pr, 1.0 + 1e-9)); wr = w / W_DET
    P012 = P1 * math.exp(H01_2 * L)
    p21 = P1 * math.exp(H21 * L)
    if PA is None:
        p22 = P1 * math.exp(H22 * L); Pcd = P1 * pr
    else:
        pi2 = max(PA / P012, 0.7); p22 = P012 * pi2 ** A2; Pcd = PA
    T21 = T_AMB + (T21_D - T_AMB) * wr; T012 = T_AMB + (T012_D - T_AMB) * wr
    T22 = T_AMB + (T22_D - T_AMB) * wr; Tcd = T_AMB + (TCD_D - T_AMB) * wr
    m = M_D * n * x * P1 / P01_D
    c11 = C11_D * n * x * P01_D / P1
    c12 = C12_D * n * x * (_c2['P01'] / P012) * (T012 / T012_D)
    pe1 = P1 - 0.5 * P1 / (R * T_AMB) * c11 ** 2
    pe2 = P012 - 0.5 * P012 / (R * T012) * c12 ** 2
    return dict(m=m, P1=P1, pe1=pe1, p21=p21, rho21=p21 / (R * T21), P012=P012, pe2=pe2, p22=p22, rho22=p22 / (R * T22),
                Pcd=Pcd, Tcd=Tcd, c11=c11, c12=c12, w=w, x=x)


def compressor(n, PA, Gs, stall):
    """compressor state for delivery pressure PA; Gs = fraction of the pressure rise left (surge), stall = deep surge"""
    n = max(n, 1e-3)
    if stall:                                                 # deep surge: the plenum blows back through the stalled stages
        P1 = P_AMB * (1 - DP_IN * (n * X_S) ** 2)
        pr, w, eta = cmap(n, X_S); st = stations(n, X_S, P1, pr, w)
        p21, p22 = st['p21'], st['p22']
        for k in ('pe1', 'p21', 'P012', 'pe2', 'p22', 'Pcd'):
            st[k] = P1 + Gs * (st[k] - P1)
        st['rho21'] *= st['p21'] / p21; st['rho22'] *= st['p22'] / p22
        d = st['Pcd'] - PA
        rho = P1 / (R * T_AMB) if d > 0 else PA / (R * st['Tcd'])
        m = min(SURGE['C'] * math.sqrt(2.0) * ssqrt(rho, d), M_D * n * X_S)
        st.update(m=m, sm=-1.0, surge=True, choke=False)
        st['P_c'] = 1.02 * (max(m, 0.0) * w + (1 - Gs) * 0.30 * 1.02 * M_D * W_DET * n ** 3)
        return st
    def Pdel(x):
        P1 = P_AMB * (1 - DP_IN * (n * x) ** 2); pr, w, eta = cmap(n, x)
        return P1 * (1 + Gs * (pr - 1)), P1, pr, w
    hi_p, *_ = Pdel(X_S); lo_p, *_ = Pdel(X_CH)
    surge = choke = False
    if PA >= hi_p:
        x = X_S; surge = True
    elif PA <= lo_p:
        x = X_CH; choke = True
    else:
        a, b = X_S, X_CH
        for _ in range(40):
            mid = 0.5 * (a + b)
            if Pdel(mid)[0] > PA: a = mid
            else: b = mid
        x = 0.5 * (a + b)
    _, P1, pr, w = Pdel(x)
    pr_e = 1 + Gs * (pr - 1)
    st = stations(n, x, P1, pr_e, w, PA if choke else None)
    prs = Pdel(X_S)[0] / P1
    st.update(sm=prs * x / (pr_e * X_S) - 1, surge=surge, choke=choke)
    st['P_c'] = 1.02 * st['m'] * w
    return st


# ================================================================================================ turbine table
NC = np.linspace(0.0, 1.5, 31)                                # corrected speed n sqrt(TIT_D / T0)
UU = np.linspace(0.0, 2.0, 41)                                # sqrt(expansion ratio - 1)


def turb_point(nc, er):
    """(corrected flow at 1 bar / TIT_D, p_N1 / P0, p_R1 / P0, p_N2 / P0, p_R2 / P0, work / cp T0) at nc, P0 / P_exit"""
    if er <= 1.0 + 1e-9: return (0.0, 1.0, 1.0, 1.0, 1.0, 0.0)
    P0, T0 = 1e5, TIT_D
    lo, hi, best = 0.0, 12.0, None
    for _ in range(60):
        m = 0.5 * (lo + hi); s = SU.turbine(P0, T0, m, nc)
        if s is None or s['R2']['P0'] < P0 / er: hi = m
        else: lo, best = m, s
    if best is None: return (0.0, 1.0, 1.0, 1.0, 1.0, 0.0)
    return (lo, best['N1']['p'] / P0, best['R1']['p'] / P0, best['N2']['p'] / P0, best['R2']['p'] / P0, best['work'] / (CPG * T0))


def build_table():
    SU.calibrate()
    return np.array([[turb_point(nc, 1 + u * u) for u in UU] for nc in NC])


TAB = None


def tab(nc, er):
    """bilinear interpolation in the turbine table"""
    i = min(max(nc / (NC[1] - NC[0]), 0.0), len(NC) - 1.001); j = min(max(math.sqrt(max(er - 1, 0.0)) / (UU[1] - UU[0]), 0.0), len(UU) - 1.001)
    i0, j0 = int(i), int(j); fi, fj = i - i0, j - j0
    T = TAB
    return (T[i0, j0] * (1 - fi) * (1 - fj) + T[i0 + 1, j0] * fi * (1 - fj) + T[i0, j0 + 1] * (1 - fi) * fj + T[i0 + 1, j0 + 1] * fi * fj)


# ================================================================================================ model
CAL = dict(K_A=1.0, K_T=1.0, EPS=0.9, A_F=4e-4, A_RIM=2e-4, C_AB=1.0, MT_D=M_D, TTEX_D=930.0, P0T_D=SU.S1['P0_in'], K={})


def gas(t, y, md):
    """all algebraic quantities of the state y in mode md"""
    n, PA, PB, pbf, pcf, Tg, Tw, Tr, z, Gs = y
    n = max(n, 1e-3); Gs = min(max(Gs, 0.0), 1.0)
    c = compressor(n, PA, Gs, md.get('stall', False))
    Tcd = c['Tcd']
    # recuperator cold side + pipes A -> B (signed), turbine (B -> NGV1 through the combustor loss)
    dAB = PA - PB
    mAB = CAL['C_AB'] * ssqrt(PA / (R * Tcd) if dAB >= 0 else PB / (R * Tr), dAB)
    T0 = max(Tg, 250.0); nct = n * math.sqrt(TIT_D / T0)
    mt = CAL['MT_D'] * PB / CAL['P0T_D']; P0t = PB * (1 - DP_COMB); Pex = P_AMB * (1 + DP_HOT)
    for _ in range(3):
        er = max(P0t / Pex, 1.0); tb = tab(nct, er)
        mt = CAL['K_A'] * tb[0] * P0t / 1e5 * math.sqrt(TIT_D / T0)
        q = (mt / CAL['MT_D']) ** 2
        P0t = PB * (1 - DP_COMB * q * (T0 / TIT_D) * (CAL['P0T_D'] / max(P0t, 1e4)) ** 2)
        Pex = P_AMB * (1 + DP_HOT * q * T0 / TIT_D)
    pN1, pR1, pN2, pR2 = (tb[k] * P0t for k in (1, 2, 3, 4))
    wf = tb[5]; T_tex = T0 * (1 - wf)
    P_t = CAL['K_T'] * mt * CPG * T0 * wf
    # blow-off valve
    a_bov = 0.0
    if md.get('t_bov') is not None:
        a_bov = min(max((t - md['t_bov'] - BOV['dead']) / BOV['open'], 0.0), 1.0)
    elif md.get('start_bleed'):                                 # start: partly open, closing between 75 and 85 % speed
        a_bov = START['bleed'] * min(max((0.85 - n) / 0.10, 0.0), 1.0)
    m_bov = orifice(PA, Tcd, P_AMB, BOV['Cd'] * math.pi / 4 * BOV['D'] ** 2 * a_bov) if a_bov > 0 else 0.0
    # heat: walls, fuel
    mtg = max(mt, 0.02 * CAL['MT_D'])
    Qw = HA_W * (max(mt, 0.0) / CAL['MT_D']) ** 0.8 * (Tw - Tg)
    if md.get('t_trip') is not None and t >= md['t_trip']:
        dt = t - md['t_trip'] - FUEL_DEAD
        HR = md['HR0'] * (1.0 if dt < 0 else math.exp(-dt / FUEL_TAU))
        Tg_t = Tr + (HR + Qw) / (mtg * CPG)
    else:
        Tg_t = max(tit_cmd(t, y, md), Tr + Qw / (mtg * CPG))
        HR = max(0.0, mtg * CPG * (Tg - Tr) - Qw)
    mf = HR / LHV
    # cavities
    m200 = lab(pbf, c['p22'], Tcd, G.BACKFACE['r_seal'], 0.30, 4)
    m85 = lab(pbf, pcf, Tcd, G.BAL_SEAL_R, 0.30, 6)
    dF = PA - pbf; mfeed = CAL['A_F'] * ssqrt(PA / (R * Tcd) if dF >= 0 else pbf / (R * Tcd), dF)
    dR = pcf - pN1; mrim = CAL['A_RIM'] * ssqrt(pcf / (R * T_CF) if dR >= 0 else pN1 / (R * T0), dR)
    # shaft
    S = P_t - c['P_c'] - P_BRG * n * n                          # gearbox input
    P_el = S - P_NL * n * n - 0.027 * abs(S)
    P_st = min(P_ST * n / N_ST, P_ST) if md.get('starter') and n < N_CUT else 0.0
    return dict(n=n, c=c, PA=PA, PB=PB, pbf=pbf, pcf=pcf, mAB=mAB, mt=mt, P0t=P0t, Pex=Pex, pN1=pN1, pR1=pR1, pN2=pN2, pR2=pR2,
                T0=T0, T_tex=T_tex, P_t=P_t, m_bov=m_bov, a_bov=a_bov, Qw=Qw, Tg_t=Tg_t, HR=HR, mf=mf, m200=m200, m85=m85,
                mfeed=mfeed, mrim=mrim, S=S, P_el=P_el, P_st=P_st, Tcd=Tcd, Tw=Tw, Tr=Tr, Gs=Gs)


def tit_cmd(t, y, md):
    """TIT command of the fuel control: constant, ramp, start schedule or speed governor (no load)"""
    k = md.get('tit', ('const', TIT_R))
    if k[0] == 'const': return k[1]
    if k[0] == 'ramp':                                         # ('ramp', t0, T0, t1, T1)
        _, t0, a, t1, b = k; f = min(max((t - t0) / (t1 - t0), 0.0), 1.0); return a + f * (b - a)
    if k[0] == 'start':                                        # ('start', t_lightoff, T_lightoff, rate, T_max), eased to the
        _, t0, a, rate, b = k                                  # no-load TIT from 92 % speed
        f = min(max((y[0] - 0.92) / 0.08, 0.0), 1.0)
        return min(a + rate * (t - t0), b + f * (START['T_fsnl'] - b))
    if k[0] == 'gov':                                          # ('gov', feed-forward TIT, max TIT)
        return min(max(k[1] + KP_GOV * (1.0 - y[0]) + y[8], 400.0), k[2])
    raise ValueError(k)


def rhs(t, y, md):
    g = gas(t, y, md); c = g['c']
    n, PA, PB, pbf, pcf, Tg, Tw, Tr, z, Gs = y
    Tcd = g['Tcd']
    dPA = N_POLY * R * Tcd / VOL['A'] * (c['m'] + g['m200'] - g['mAB'] - g['m_bov'] - g['mfeed'])
    dPB = N_POLY * R * T_B / VOL['B'] * (g['mAB'] + g['mf'] - g['mt'])
    dpbf = N_POLY * R * Tcd / VOL['bf'] * (g['mfeed'] - g['m200'] - g['m85'])
    dpcf = N_POLY * R * T_CF / VOL['cf'] * (g['m85'] - g['mrim'])
    dTg = (g['Tg_t'] - Tg) / TAU_C
    dTw = -g['Qw'] / C_W
    dTr = (Tcd + CAL['EPS'] * (g['T_tex'] - Tcd) - Tr) / (TAU_R * CAL['MT_D'] / max(abs(g['mAB']), 0.1 * CAL['MT_D']))
    if md.get('breaker') or md.get('hold'):
        dn = 0.0
    else:
        dn = (g['S'] - P_NL * g['n'] ** 2 + g['P_st']) / (J * g['n'] * OM_D * OM_D)
    dz = 0.0
    k = md.get('tit', ('const',))
    if k[0] == 'gov':
        u = k[1] + KP_GOV * (1.0 - n) + z
        if 400.0 < u < k[2] or (u >= k[2] and n > 1.0) or (u <= 400.0 and n < 1.0): dz = KI_GOV * (1.0 - n)
    dG = ((SURGE['g'] if md.get('stall') else 1.0) - Gs) / SURGE['tau']
    return [dn, dPA, dPB, dpbf, dpcf, dTg, dTw, dTr, dz, dG]


# ================================================================================================ forces, bearing
def vortex(p_tip, rho, r_tip, r_in, om, k=0.45):
    a, b = r_in * 1e-3, r_tip * 1e-3; v2 = (k * om * b) ** 2; pg = p_tip - P_AMB
    return math.pi * ((pg - 0.5 * rho * v2) * (b * b - a * a) + 0.5 * rho * (k * om) ** 2 * (b ** 4 - a ** 4) / 2)


def r2f(p_in, r_in, p_out, r_out):
    a, b = r_in * 1e-3, r_out * 1e-3; pi_, po = p_in - P_AMB, p_out - P_AMB
    B = (po - pi_) / (b * b - a * a); Aa = pi_ - B * a * a
    return math.pi * (Aa * (b * b - a * a) + B * (b ** 4 - a ** 4) / 2)


def ann(p, ri, ro):
    return (p - P_AMB) * math.pi * ((ro * 1e-3) ** 2 - (ri * 1e-3) ** 2)


def force_terms(g):
    """the terms of a1000_rotor_stack.thrust() [N, + aft] from the transient pressures (before the design scaling)"""
    c, om = g['c'], g['n'] * OM_D
    sp = min(max((g['P0t'] - P_AMB) / (CAL['P0T_D'] - P_AMB), 0.0), 2.0)   # purge overpressure ~ the turbine pressure level
    p12, p2f, pra = g['pR1'] * (1 + 0.03 * sp), g['pN2'] * (1 + 0.03 * sp), g['pR2'] * (1 + 0.02 * sp)
    m = abs(c['m'])
    f = dict()
    f['imp 1 hub surface'] = r2f(c['pe1'], R_SEAL_IN, c['p21'], R2_1)
    f['imp 1 inlet momentum'] = m * c['c11']
    f['imp 1 back face'] = -vortex(c['p21'], c['rho21'], R2_1, R_SPC, om)
    f['spacer step (imp 2 eye)'] = -ann(c['pe2'], R1H_2, R_SPC)
    f['imp 2 hub surface'] = r2f(c['pe2'], R1H_2, c['p22'], R2_2)
    f['imp 2 inlet momentum'] = m * c['c12']
    f['imp 2 back face (pressurised)'] = -ann(g['pbf'], G.BAL_SEAL_R, G.BACKFACE['r_seal'])
    f['imp 2 back face (vortex)'] = -vortex(c['p22'], c['rho22'], R2_2, G.BACKFACE['r_seal'], om)
    f['turbine front cavity (balance)'] = ann(g['pcf'], G.BAL_SEAL_R, RH1)
    f['R1 blade row'] = (g['pN1'] - g['pR1']) * math.pi * ((RT1 * 1e-3) ** 2 - (RH1 * 1e-3) ** 2)
    f['R1 aft cavity'] = -ann(p12, R_S2, RH1)
    f['R2 front cavity'] = ann(p2f, R_S2, RH2)
    f['R2 blade row'] = (g['pN2'] - g['pR2']) * math.pi * ((RT2 * 1e-3) ** 2 - (RH2 * 1e-3) ** 2)
    f['R2 aft cavity'] = -ann(pra, R_REAR, RH2)
    return f


def thrust_of(g):
    f = force_terms(g)
    return sum(CAL['K'][k] * v for k, v in f.items())


def pad_side(F, n, n_pads):
    """unit load [MPa] and minimum film [um] of one side carrying F [N] at speed fraction n (pads of the 8-pad size,
    a1000_rotor_stack.thrust_bearing: tilting slider W_bar 0.05, oil at the loaded-side effective temperature)"""
    ri, ro = G.THRUST['ri'] * 1e-3, G.THRUST['ro'] * 1e-3; rm = 0.5 * (ri + ro); Lr = ro - ri
    B = rm * 2 * math.pi / G.THRUST['n'] * 0.80; U = max(n, 1e-4) * OM_D * rm
    mu = RS.visc(RS.T_OIL_IN + 0.6 * 20.0 + 12.0)
    unit = abs(F) / (n_pads * B * Lr) / 1e6
    h = min(B * math.sqrt(0.05 * mu * U * Lr / max(abs(F) / n_pads, 1.0)), 0.30e-3) * 1e6
    return unit, h


# ================================================================================================ steady states, calibration
Y_NAMES = ['n', 'PA', 'PB', 'pbf', 'pcf', 'Tg', 'Tw', 'Tr', 'z', 'G']


def steady(n, Tg, md, guess=None, Tr=None):
    """steady state at speed n and gas temperature Tg (speed held); Tr = recuperator air exit (None: its own steady value)"""
    y = list(guess) if guess is not None else [n, PCD_D, PCD_D * (1 - DP_AB), 0.97 * PCD_D, 1.04 * 2.6e5, Tg, Tg, T_RCX_D, 0.0, 1.0]
    y[0], y[5], y[6], y[9] = n, Tg, Tg, 1.0
    if Tr is not None: y[7] = Tr
    md = dict(md, breaker=True, tit=('const', Tg))
    for _ in range(30):
        def res(p):
            yy = list(y); yy[1:5] = p
            d = rhs(0.0, yy, md)
            return [d[1] / 1e3, d[2] / 1e3, d[3] / 1e4, d[4] / 1e4]
        p, info, ok, msg = fsolve(res, y[1:5], full_output=True)
        y[1:5] = list(p)
        if Tr is not None: break
        g = gas(0.0, y, md); Tr_new = g['Tcd'] + CAL['EPS'] * (g['T_tex'] - g['Tcd'])
        if abs(Tr_new - y[7]) < 0.01: break
        y[7] = Tr_new
    return y


def calibrate():
    """turbine flow / work factors, seal areas and recuperator effectiveness from the design point; per-term force scales"""
    global TAB
    TAB = build_table()
    # design state at x = 1: compressor, cavity targets of the stack model
    P1 = P01_D; pr, w, _ = cmap(1.0, 1.0); c = stations(1.0, 1.0, P1, pr, w)
    PA = c['Pcd']; PB = PA * (1 - DP_AB); P0t = PB * (1 - DP_COMB); Pex = P_AMB * (1 + DP_HOT)
    tb = tab(1.0, P0t / Pex)
    pbf, Tcd = 0.97 * PA, c['Tcd']
    pN1 = tb[1] * P0t; pcf = 1.04 * pN1
    m200 = lab(pbf, c['p22'], Tcd, G.BACKFACE['r_seal'], 0.30, 4); m85 = lab(pbf, pcf, Tcd, G.BAL_SEAL_R, 0.30, 6)
    CAL['A_F'] = (m200 + m85) / ssqrt(PA / (R * Tcd), PA - pbf)
    CAL['A_RIM'] = m85 / ssqrt(pcf / (R * T_CF), pcf - pN1)
    mAB = c['m'] - m85
    mt = mAB / (1 - CPG * (TIT_D - T_RCX_D) / LHV)
    CAL['C_AB'] = mAB / ssqrt(PA / (R * Tcd), PA - PB)
    CAL['K_A'] = mt / (tb[0] * P0t / 1e5)
    CAL['MT_D'], CAL['P0T_D'] = mt, P0t
    CAL['TTEX_D'] = TIT_D * (1 - tb[5])
    CAL['EPS'] = (T_RCX_D - Tcd) / (CAL['TTEX_D'] - Tcd)
    # design steady (950 C) and rating steady (970 C): turbine work factor from the 985 kW rating
    yd = steady(1.0, TIT_D, {}, Tr=T_RCX_D)
    yr = steady(1.0, TIT_R, {}, guess=yd)
    gr = gas(0.0, yr, dict(breaker=True, tit=('const', TIT_R)))
    CAL['K_T'] *= (gr['c']['P_c'] + P_BRG + P_SH_R) / gr['P_t']
    # per-term force scales: the stack terms at its design point over the model terms at the design steady state
    S = RS.states(); f_st, F_st, _ = RS.thrust(S, G.BAL_SEAL_R)
    gd = gas(0.0, yd, dict(breaker=True, tit=('const', TIT_D)))
    f_m = force_terms(gd)
    CAL['K'] = {k: f_st[k] / f_m[k] for k in f_st}
    return yd, yr, gd, f_st, F_st




# ================================================================================================ simulation
ATOL = [1e-7, 1.0, 1.0, 1.0, 1.0, 1e-3, 1e-3, 1e-3, 1e-3, 1e-6]
_LAST = [None]


def chain(segments, y0, t_start=0.0):
    """integrate segments in turn: name, md (dict or f(t0, y)), t_end (value or f(t0)), optional event (f(t, y, md)) with
    direction, stop (end the run when the event fires), group (an event ends the rest of its group), skip_if (f(t0, y, md):
    the event condition already holds, go on with the next group), init (f(t0, y, md)), max_step"""
    T, Y, M, log = [], [], [], []
    t0, y, skip = t_start, list(y0), None
    for seg in segments:
        if skip is not None and seg.get('group') == skip: continue
        md = seg['md'](t0, y) if callable(seg['md']) else seg['md']
        if seg.get('skip_if') and seg['skip_if'](t0, y, md):
            log.append(dict(name=seg['name'], t0=t0, t1=t0, event=True, nfev=0)); _LAST[0] = md
            if seg.get('group'): skip = seg['group']
            continue
        t_end = seg['t_end'](t0) if callable(seg['t_end']) else seg['t_end']
        if seg.get('init'): y = seg['init'](t0, y, md)
        evs = None
        if seg.get('event'):
            ev = (lambda f, m: (lambda t, yy: f(t, yy, m)))(seg['event'], md)
            ev.terminal, ev.direction = True, seg.get('direction', 0); evs = [ev]
        sol = solve_ivp(lambda t, yy: rhs(t, yy, md), (t0, t_end), y, method='LSODA', max_step=seg.get('max_step', 0.25), events=evs,
                        rtol=1e-6, atol=ATOL, first_step=1e-5)
        T.append(sol.t); Y.append(sol.y.T); M += [md] * len(sol.t)
        log.append(dict(name=seg['name'], t0=t0, t1=float(sol.t[-1]), event=bool(sol.status == 1), nfev=int(sol.nfev)))
        _LAST[0] = md
        t0, y = float(sol.t[-1]), list(sol.y[:, -1])
        if sol.status == 1:
            if seg.get('stop'): break
            if seg.get('group'): skip = seg['group']
        elif sol.status < 0:
            raise RuntimeError('%s: %s' % (seg['name'], sol.message))
    return np.concatenate(T), np.vstack(Y), M, log


def post(t, Y, M, stride=1):
    """time histories: force, speed, pressures, bearing load / film of the loaded side"""
    keys = ('t', 'n', 'F', 'PA', 'PB', 'pbf', 'pcf', 'p22', 'TIT', 'Tr', 'P_el', 'm_c', 'm_bov', 'sm', 'unit', 'film', 'aft')
    out = {k: [] for k in keys}
    for i in list(range(0, len(t), stride)) + ([len(t) - 1] if (len(t) - 1) % stride else []):
        g = gas(t[i], Y[i], M[i]); F = thrust_of(g)
        u, h = pad_side(F, g['n'], G.THRUST['n'] if F >= 0 else G.THRUST['n_in'])
        for k, v in (('t', t[i]), ('n', g['n']), ('F', F), ('PA', g['PA']), ('PB', g['PB']), ('pbf', g['pbf']), ('pcf', g['pcf']),
                     ('p22', g['c']['p22']), ('TIT', g['T0']), ('Tr', g['Tr']), ('P_el', g['P_el'] if M[i].get('breaker') else 0.0),
                     ('m_c', g['c']['m']), ('m_bov', g['m_bov']), ('sm', g['c']['sm']), ('unit', u), ('film', h), ('aft', F >= 0)):
            out[k].append(float(v))
    return {k: np.array(v) for k, v in out.items()}


def peaks(h):
    """peak aft and forward force with the speed and time at each (F_min: lowest force above 50 % speed, + = no reversal;
    F_low: largest |F| below 50 % speed); worst unit load and film of each side (|F| > 200 N)"""
    F, n, t = h['F'], h['n'], h['t']
    ia = int(np.argmax(F)); iw = int(np.argmin(np.where(n >= 0.50, F, 1e12)))
    res = dict(F_aft_max=float(max(F[ia], 0.0)), n_at_aft=float(n[ia]), t_at_aft=float(t[ia]), F_fwd_max=float(min(F[iw], 0.0)),
               F_min=float(F[iw]), n_at_fwd=float(n[iw]), t_at_fwd=float(t[iw]), n_max=float(n.max()), t_n_max=float(t[int(np.argmax(n))]),
               sm_min=float(h['sm'].min()), t_end=float(t[-1]), n_end=float(n[-1]),
               F_low=float(np.abs(np.where(n < 0.50, F, 0.0)).max()))
    for side, sel in (('aft', (h['aft'] > 0.5) & (np.abs(F) > 200.0)), ('fwd', (h['aft'] < 0.5) & (np.abs(F) > 200.0))):
        if sel.any():
            iu = int(np.argmax(np.where(sel, h['unit'], -1.0))); ih = int(np.argmin(np.where(sel, h['film'], 1e9)))
            res[side] = dict(unit_max=float(h['unit'][iu]), F_at_unit=float(F[iu]), n_at_unit=float(n[iu]), film_min=float(h['film'][ih]),
                             F_at_film=float(F[ih]), n_at_film=float(n[ih]), t_at_film=float(t[ih]), loaded=True)
        else:
            res[side] = dict(unit_max=0.0, film_min=300.0, loaded=False)
    return res


# -------------------------------------------------------------------------------------------- protection and sequences
def trip_md(base, t_trip, y, bov=True):
    """mode after a fuel trip at t_trip: flame heat release before the trip, blow-off command at the same time"""
    md = dict(base, t_trip=t_trip, t_bov=t_trip if bov else None)
    g = gas(t_trip, y, dict(base, t_trip=None, t_bov=None))
    md['HR0'] = max(0.0, max(g['mt'], 0.02 * CAL['MT_D']) * CPG * (y[5] - y[7]) - g['Qw'])
    return md


def ev_speed(level):
    return lambda t, y, md: y[0] - level


def ev_reverse_power(t, y, md):
    return gas(t, y, md)['P_el'] + RP_KW * 1e3


def ev_recover(t, y, md):
    """deep surge ends when the plenum has blown down below the shut-off pressure of the stalled stages (forward flow again)"""
    return y[1] - compressor(y[0], y[1], min(max(y[9], 0.0), 1.0), True)['Pcd']


def rp_and_coast(t_end, fast=0.01):
    """reverse-power relay (event, then RP_DELAY) and the coast-down with the breaker open"""
    return [dict(name='until reverse power', md=lambda t0, y: _LAST[0], t_end=lambda t0: t0 + 120.0, event=ev_reverse_power, direction=-1,
                 max_step=fast, skip_if=lambda t0, y, md: ev_reverse_power(t0, y, md) < 0),
            dict(name='relay delay', md=lambda t0, y: _LAST[0], t_end=lambda t0: t0 + RP_DELAY, max_step=fast),
            dict(name='breaker open, coast-down', md=lambda t0, y: dict(_LAST[0], breaker=False), t_end=t_end, event=ev_speed(0.02),
                 direction=-1, stop=True, max_step=0.05)]


def case_a(y0, bov=True, t_end=900.0, t_fast=3.0):
    """(a) load rejection + fuel trip at the rating: breaker, fuel and BOV commands at t 0"""
    base = dict(breaker=False, tit=('const', TIT_R))
    segs = [dict(name='load rejection + trip', md=lambda t0, y: trip_md(base, 0.0, y, bov), t_end=t_fast, max_step=2e-3)]
    if t_end > t_fast:
        segs.append(dict(name='coast-down', md=lambda t0, y: _LAST[0], t_end=t_end, event=ev_speed(0.02), direction=-1, stop=True,
                         max_step=0.05))
    return chain(segs, y0)


def case_b(y0, t_end=900.0, t_fast=3.0):
    """(b) fuel trip with the breaker closed: the grid holds the speed until the reverse-power relay opens the breaker"""
    base = dict(breaker=True, tit=('const', TIT_R))
    segs = [dict(name='trip, breaker closed', md=lambda t0, y: trip_md(base, 0.0, y), t_end=1.0, max_step=2e-3, event=ev_reverse_power,
                 direction=-1, group='rp')]
    segs += [dict(s, group='rp') if s['name'] == 'until reverse power' else s for s in rp_and_coast(t_end)]
    if t_end <= t_fast: segs = segs[:1] + [dict(name='closed', md=lambda t0, y: _LAST[0], t_end=t_fast, max_step=2e-3)]
    return chain(segs, y0)


def case_c(y0, t_end=900.0, t_fast=3.0):
    """(c) deep surge at the rating, breaker closed: pressure rise collapses (SURGE g, tau), detection trips fuel + BOV
    at t_det, the compressor recovers when the plenum has blown down"""
    g0 = gas(0.0, y0, dict(breaker=True, tit=('const', TIT_R)))
    HR0 = max(0.0, g0['mt'] * CPG * (y0[5] - y0[7]) - g0['Qw'])
    base = dict(breaker=True, tit=('const', TIT_R), stall=True, t_trip=SURGE['t_det'], t_bov=SURGE['t_det'], HR0=HR0)
    segs = [dict(name='deep surge', md=base, t_end=2.0, event=ev_recover, direction=-1, max_step=5e-4)]
    if t_end > t_fast:
        segs += [dict(name='recovered', md=lambda t0, y: dict(_LAST[0], stall=False), t_end=lambda t0: max(t_fast, t0 + 0.5), max_step=2e-3,
                      event=ev_reverse_power, direction=-1, group='rp', skip_if=lambda t0, y, md: ev_reverse_power(t0, y, md) < 0)]
        segs += [dict(s, group='rp') if s['name'] == 'until reverse power' else s for s in rp_and_coast(t_end)]
    else:
        segs += [dict(name='recovered', md=lambda t0, y: dict(_LAST[0], stall=False), t_end=lambda t0: max(t_fast, t0 + 0.5), max_step=2e-3)]
    return chain(segs, y0)


def case_d():
    """(d) start-up: starter to 20 % (purge), light-off, acceleration (starter to 60 %, BOV 30 % open as start bleed to 75-85 %
    speed), no-load governor, sync, load ramp"""
    y0 = [0.02, P_AMB, P_AMB, P_AMB, P_AMB, T_AMB, T_AMB, T_AMB, 0.0, 1.0]
    tit_now = lambda y: y[5]
    segs = [dict(name='starter to 20 %', md=dict(starter=True, start_bleed=True, tit=('const', T_AMB)), t_end=60.0, event=ev_speed(0.20),
                 direction=1),
            dict(name='purge', md=dict(starter=True, start_bleed=True, hold=True, tit=('const', T_AMB)), t_end=lambda t0: t0 + 5.0),
            dict(name='light-off, acceleration', md=lambda t0, y: dict(starter=True, start_bleed=True,
                                                                       tit=('start', t0, START['T_lo'], START['rate'], START['T_acc'])),
                 t_end=lambda t0: t0 + 120.0, event=ev_speed(0.99), direction=1, max_step=0.02),
            dict(name='no load (governor)', md=lambda t0, y: dict(tit=('gov', tit_now(y), START['T_acc'])), t_end=lambda t0: t0 + 30.0,
                 init=lambda t0, y, md: y[:8] + [0.0, 1.0], max_step=0.02),
            dict(name='sync, load ramp', md=lambda t0, y: dict(breaker=True, tit=('ramp', t0, y[5], t0 + START['t_ramp'], TIT_R)),
                 t_end=lambda t0: t0 + START['t_ramp'] + 300.0, init=lambda t0, y, md: [1.0] + y[1:], max_step=0.5)]
    return chain(segs, y0)


START = dict(T_lo=470.0, rate=30.0, T_acc=923.15, T_fsnl=720.0, bleed=0.30, t_ramp=300.0)   # BOV 30 % open to 75-85 % speed
STOP = dict(t_unload=300.0, T_min=923.15, t_cool=300.0)


def case_e(y0, t_end=1500.0):
    """(e) normal stop: unload to the minimum DLE load (TIT 650 C) with the breaker closed, cool-down, fuel off + BOV,
    reverse power opens the breaker, coast-down"""
    segs = [dict(name='unload', md=dict(breaker=True, tit=('ramp', 0.0, TIT_R, STOP['t_unload'], STOP['T_min'])), t_end=STOP['t_unload'],
                 max_step=0.5),
            dict(name='cool-down at minimum load', md=dict(breaker=True, tit=('const', STOP['T_min'])),
                 t_end=STOP['t_unload'] + STOP['t_cool'], max_step=0.5),
            dict(name='fuel off + BOV', md=lambda t0, y: trip_md(dict(breaker=True, tit=('const', STOP['T_min'])), t0, y),
                 t_end=lambda t0: t0 + 1.0, max_step=2e-3, event=ev_reverse_power, direction=-1, group='rp')]
    segs += [dict(s, group='rp') if s['name'] == 'until reverse power' else s for s in rp_and_coast(t_end)]
    return chain(segs, y0)


# -------------------------------------------------------------------------------------------- blow-off valve sizing
def bov_scan(yr):
    """steady gearbox-input surplus at 15k with the fuel off and the recuperator at its full-load temperature (gas = recuperator
    air + 60 K from the hot scroll / liner): without BOV and with BOV sizes; + = the engine still accelerates"""
    Tr = yr[7]; out = {}
    for D in (None, 0.080, 0.100, 0.125, 0.150):
        md = dict(t_bov=-10.0) if D else {}
        saved = BOV['D']; BOV['D'] = D or saved
        y = steady(1.0, Tr + 60.0, md, guess=yr, Tr=Tr)
        g = gas(0.0, y, dict(md, breaker=True, tit=('const', Tr + 60.0)))
        out['none' if D is None else 'DN%d' % round(D * 1e3)] = dict(surplus_kW=(g['S'] - P_NL) / 1e3, m_bov=g['m_bov'], PA=g['PA'],
                                                                      m_c=g['c']['m'], m_t=g['mt'])
        BOV['D'] = saved
    return out


# ================================================================================================ main
def summary_line(name, pk):
    return ('%-34s aft max %6.2f kN @ %5.0f rpm | min %6.2f kN @ %5.0f rpm | speed max %5.0f rpm | aft %.2f MPa / %3.0f um | '
            'fwd %.2f MPa / %3.0f um | SM min %.0f %%' % (name, pk['F_aft_max'] / 1e3, pk['n_at_aft'] * 15000, pk['F_min'] / 1e3,
                                                     pk['n_at_fwd'] * 15000, pk['n_max'] * 15000, pk['aft']['unit_max'], pk['aft']['film_min'],
                                                     pk['fwd']['unit_max'], pk['fwd']['film_min'], 100 * pk['sm_min']))


def main():
    res = dict(rev='rotor rev 1.3, thrust bearing %d + %d pads r %.0f-%.0f' % (G.THRUST['n'], G.THRUST['n_in'], G.THRUST['ri'], G.THRUST['ro']),
               checks=[])
    chk = res['checks']
    def check(test, value, limit, unit, ok, note=''):
        chk.append(dict(test=test, value=value, limit=limit, unit=unit, ok=bool(ok), note=note))
        print('  %-52s %10.4g %-4s (limit %.4g) %s  %s' % (test, value, unit, limit, 'OK' if ok else 'FAIL', note))
    print('1. calibration (turbine table, seals, recuperator, rating, force terms)')
    yd, yr, gd, f_st, F_st = calibrate()
    res['_yr'] = yr
    F_d = thrust_of(gd)
    gr = gas(0.0, yr, dict(breaker=True, tit=('const', TIT_R))); F_r = thrust_of(gr)
    res['calibration'] = dict(K_A=CAL['K_A'], K_T=CAL['K_T'], eps_recuperator=CAL['EPS'], A_feed_mm2=CAL['A_F'] * 1e6, A_rim_mm2=CAL['A_RIM'] * 1e6,
                              force_scales=CAL['K'], J=J, volumes=VOL, design=dict(F=F_d, x=gd['c']['x'], PA=gd['PA'], pbf=gd['pbf'], pcf=gd['pcf']),
                              rating=dict(F=F_r, x=gr['c']['x'], PA=gr['PA'], TIT=TIT_R, T_rcx=yr[7], P_el_kW=gr['P_el'] / 1e3, sm=gr['c']['sm']))
    print('   J %.2f kg m2; flow factor %.3f, work factor %.3f, eps %.3f; feed %.0f mm2, rim %.0f mm2' % (
        J, CAL['K_A'], CAL['K_T'], CAL['EPS'], CAL['A_F'] * 1e6, CAL['A_RIM'] * 1e6))
    print('   force scales: ' + ', '.join('%s %.3f' % (k, v) for k, v in CAL['K'].items()))
    print('   design 950 C: F %.2f kN (stack %.2f), x %.3f; rating 970 C: F %.2f kN, P_el %.0f kW, recuperator air %.0f C, SM %.0f %%' % (
        F_d / 1e3, F_st / 1e3, gd['c']['x'], F_r / 1e3, gr['P_el'] / 1e3, yr[7] - 273.15, 100 * gr['c']['sm']))
    print('2. blow-off valve: steady surplus at 15k, fuel off, hot recuperator')
    res['bov_scan'] = bov_scan(yr)
    for k, v in res['bov_scan'].items():
        print('   %-6s surplus %+6.0f kW (BOV %.2f kg/s, delivery %.2f bar, compressor %.2f kg/s, turbine %.2f kg/s)' % (
            k, v['surplus_kW'], v['m_bov'], v['PA'] / 1e5, v['m_c'], v['m_t']))
    print('3. cases')
    cases = {}
    runs = [('a: load rejection + trip', lambda: case_a(yr)), ('a0: same, without BOV (10 s)', lambda: case_a(yr, bov=False, t_end=10.0)),
            ('b: trip, breaker closed', lambda: case_b(yr)), ('c: surge at full load', lambda: case_c(yr)),
            ('d: start-up to full load', case_d), ('e: normal stop', lambda: case_e(yr))]
    hist = {}
    for name, f in runs:
        t, Y, M, log = f()
        h = post(t, Y, M); pk = peaks(h)
        cases[name] = dict(peaks=pk, segments=log)
        hist[name] = h
        print('   ' + summary_line(name, pk))
        print('      segments: ' + '; '.join('%s %.2f-%.2f s%s' % (s['name'], s['t0'], s['t1'], ' (event)' if s['event'] else '') for s in log))
    res['cases'] = cases
    # sensitivities of the fast phases (first 3 s) of a, b, c
    print('4. sensitivities (first 3 s of a, b, c)')
    sens = {}
    base_vol, base_bov, base_s = dict(VOL), dict(BOV), dict(SURGE)
    def set_(key, f):
        VOL.update(base_vol); BOV.update(base_bov); SURGE.update(base_s)
        if key == 'vol_A': VOL['A'] = base_vol['A'] * f
        elif key == 'vol_B': VOL['B'] = base_vol['B'] * f
        elif key == 'cavities': VOL['bf'] = base_vol['bf'] * f; VOL['cf'] = base_vol['cf'] * f
        elif key == 'bov_open': BOV['open'] = f
        elif key == 'surge_g': SURGE['g'] = f
        elif key == 'surge_tau': SURGE['tau'] = f
        elif key == 'surge_reverse': SURGE['C'] = C_SURGE * f
        elif key == 'surge_bound': SURGE['C'] = C_SURGE * f; SURGE['g'] = 0.0
    for key, fs in SENS.items():
        for fv in fs:
            set_(key, fv)
            for cn, f in (('a', case_a), ('b', case_b), ('c', case_c)):
                if key.startswith('surge') and cn != 'c': continue
                t, Y, M, log = f(yr, t_end=3.0)
                hh = post(t, Y, M, stride=2); pk = peaks(hh)
                if key == 'surge_bound': hist['c bound'] = hh
                sens['%s %s %s%g' % (cn, key, 'x' if key in ('vol_A', 'vol_B', 'cavities', 'surge_reverse', 'surge_bound') else '= ', fv)] = pk
                print('   %-24s %s' % ('%s %s %g' % (cn, key, fv), summary_line('', pk)[35:]))
    VOL.update(base_vol); BOV.update(base_bov); SURGE.update(base_s)
    res['sensitivity'] = sens
    # ------------------------------------------------------------------ checks (worst of the cases and the sensitivities)
    allp = [c['peaks'] for k, c in cases.items() if not k.startswith('a0')] + list(sens.values())
    fu = max(p['fwd']['unit_max'] for p in allp); fh = min(p['fwd']['film_min'] for p in allp)
    au = max(p['aft']['unit_max'] for p in allp); ah = min(p['aft']['film_min'] for p in allp)
    F_fwd = min(p['F_fwd_max'] for p in allp); F_aft = max(p['F_aft_max'] for p in allp)
    nmax = max(c['peaks']['n_max'] for k, c in cases.items() if not k.startswith('a0'))
    print('5. checks (worst of the five cases and the sensitivity runs)')
    check('transient thrust, forward side %d pads: unit load' % G.THRUST['n_in'], fu, UNIT_LIM, 'MPa', fu <= UNIT_LIM,
          'peak forward %.1f kN' % (-F_fwd / 1e3))
    check('transient thrust, forward side: min film', fh, FILM_LIM, 'um', fh >= FILM_LIM, 'at the instantaneous speed')
    check('transient thrust, aft side %d pads: unit load' % G.THRUST['n'], au, UNIT_LIM, 'MPa', au <= UNIT_LIM, 'peak aft %.1f kN' % (F_aft / 1e3))
    check('transient thrust, aft side: min film', ah, FILM_LIM, 'um', ah >= FILM_LIM, 'at the instantaneous speed')
    check('load rejection overspeed / trip speed', nmax * 15000 / RS.N_TRIP, 1.0, '-', nmax * 15000 <= RS.N_TRIP,
          'peak %.0f rpm (BOV DN%d)' % (nmax * 15000, round(BOV['D'] * 1e3)))
    # upper bound: both stages lose all pressure rise at once while the plenum and both cavities keep the rating pressures
    yb = list(res['_yr']); yb[9] = 0.0
    gb = gas(0.0, yb, dict(breaker=True, tit=('const', TIT_R), stall=True)); Fb = thrust_of(gb)
    ub, hb = pad_side(Fb, 1.0, G.THRUST['n_in'])
    res['bound'] = dict(F=Fb, unit=ub, film=hb, note='surge bound: stages fully collapsed, plenum and cavities frozen at the rating')
    check('forward side, bound (stages collapsed, cavities frozen)', ub, UNIT_LIM, 'MPa', ub <= UNIT_LIM and hb >= FILM_LIM,
          '%.1f kN, film %.0f um' % (-Fb / 1e3, hb))
    smin = min(c['peaks']['sm_min'] for k, c in cases.items() if k[0] in 'abde')
    check('no surge in trips, start and stop: min surge margin', 100 * smin, 0.0, '%', smin > 0.0, 'cases a, b, d, e')
    res['worst'] = dict(F_fwd=F_fwd, F_aft=F_aft, fwd_unit=fu, fwd_film=fh, aft_unit=au, aft_film=ah, n_max=nmax, sm_min=smin)
    res['bov'] = dict(BOV, location='compressor delivery volume (collector / scroll pressure body) to the stack')
    res['model'] = dict(volumes_m3=VOL, T_B=T_B, T_cf=T_CF, n_poly=N_POLY, dp_AB=DP_AB, dp_comb=DP_COMB, tau_c=TAU_C, fuel=(FUEL_DEAD, FUEL_TAU),
                        walls=dict(C=C_W, hA=HA_W), tau_recuperator=TAU_R, surge=SURGE, start=START, stop=STOP, reverse_power=(RP_KW, RP_DELAY),
                        starter=(P_ST, N_ST, N_CUT), x_surge=X_S, x_choke=X_CH)
    print('checks: %d of %d pass' % (sum(c['ok'] for c in chk), len(chk)))
    res['rating_state'] = dict(zip(Y_NAMES, res.pop('_yr')))
    json.dump(res, open(os.path.join(HERE, 'fea', 'a1000_thrust_transient.json'), 'w'), indent=1, default=float)
    plot(res, hist)
    return res


def plot(res, hist):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(3, 2, figsize=(15, 11), dpi=100)
    keys = [k for k in hist if not k.startswith('a0') and k != 'c bound']
    lim_f = UNIT_LIM * G.THRUST['n_in'] * (0.5 * (G.THRUST['ri'] + G.THRUST['ro'])) * 2 * math.pi / G.THRUST['n'] * 0.8 * (G.THRUST['ro'] - G.THRUST['ri'])
    lim_a = lim_f * G.THRUST['n'] / G.THRUST['n_in']
    for ax, k in zip(axs.flat, keys):
        h = hist[k]; t = h['t']
        ax.plot(t, h['F'] / 1e3, color='tab:red', lw=1.2, label='axial force [kN] (+ aft)')
        if k[0] == 'c' and 'c bound' in hist:
            hb = hist['c bound']
            ax.plot(hb['t'], hb['F'] / 1e3, color='tab:purple', lw=1.0, ls='--', label='bound: g 0, back-flow x 0.25')
            ax.legend(loc='lower right', fontsize=7)
        ax.axhline(0, color='k', lw=0.5)
        ax.axhline(-lim_f / 1e3, color='tab:blue', ls='--', lw=0.8, label='forward %d pads at %.1f MPa' % (G.THRUST['n_in'], UNIT_LIM))
        ax.axhline(lim_a / 1e3, color='tab:red', ls='--', lw=0.8, label='aft %d pads at %.1f MPa' % (G.THRUST['n'], UNIT_LIM))
        ax.set_ylim(-1.15 * lim_f / 1e3, max(1.15 * h['F'].max() / 1e3, 6.0))
        ax2 = ax.twinx(); ax2.plot(t, h['n'] * 15000, color='tab:green', lw=1.0, label='speed [rpm]'); ax2.set_ylim(0, 17500)
        ax2.axhline(RS.N_TRIP, color='tab:green', ls=':', lw=0.8)
        pk = res['cases'][k]['peaks']
        if k[0] != 'd':
            ax.set_xscale('symlog', linthresh=1.0); ax.set_xlim(0, max(t[-1], 10.0))
        ax.set_title('%s: max %.1f kN @ %.0f rpm, min %.1f kN @ %.0f rpm, film fwd %.0f / aft %.0f um' % (
            k, pk['F_aft_max'] / 1e3, pk['n_at_aft'] * 15000, pk['F_min'] / 1e3, pk['n_at_fwd'] * 15000, pk['fwd']['film_min'],
            pk['aft']['film_min']), fontsize=8.5)
        ax.set_xlabel('time [s]' + (' (linear to 1 s, then log)' if k[0] != 'd' else ''), fontsize=8); ax.grid(alpha=0.3)
        ax.set_ylabel('axial force [kN]', fontsize=8); ax2.set_ylabel('speed [rpm]', fontsize=8)
        if k[0] == 'a':
            ax.legend(loc='lower left', fontsize=7); ax2.legend(loc='lower right', fontsize=7)
    ax = axs.flat[-1]; ax.axis('off')
    rows = [(c['test'][:50], '%.3g %s' % (c['value'], c['unit']), 'OK' if c['ok'] else 'FAIL') for c in res['checks']]
    rows += [('', '', '')] + [('BOV %s: surplus at 15k, fuel off' % k, '%+.0f kW' % v['surplus_kW'], '') for k, v in res['bov_scan'].items()]
    tbl = ax.table(cellText=rows, colLabels=['check', 'value', ''], loc='upper center', cellLoc='left', colWidths=[0.70, 0.20, 0.10])
    tbl.auto_set_font_size(False); tbl.set_fontsize(7.5); tbl.scale(1, 1.25)
    for (i, j), cell in tbl.get_celld().items():
        if i > 0 and j == 2 and i - 1 < len(res['checks']): cell.set_facecolor('#c8e6c9' if rows[i - 1][2] == 'OK' else '#ffcdd2')
    ax.set_title('Transient thrust checks (worst of cases + sensitivities): %d of %d pass' % (sum(c['ok'] for c in res['checks']), len(res['checks'])),
                 fontsize=9)
    fig.suptitle('AURORA-1000 transient axial thrust, rotor rev 1.3, thrust bearing %d aft + %d forward pads (r %.0f-%.0f)' % (
        G.THRUST['n'], G.THRUST['n_in'], G.THRUST['ri'], G.THRUST['ro']), fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_thrust_transient.png')); print('written docs/img/a1000_thrust_transient.png')


if __name__ == '__main__':
    main()
