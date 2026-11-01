#!/usr/bin/env python3
"""AURORA-1000 start line: off-design matching of the single-shaft set (2-stage centrifugal compressor, recuperator cold
during the start, combustor, 2-stage axial turbine, gearbox, generator not connected) during the unloaded acceleration
from starter cut-out to full speed no load.

Compressor: generic speed lines of a backswept centrifugal stage pair scaled from the design point (sim/mw1_meanline.json
compressor): work coefficient falling with the flow coefficient (40 deg backsweep: d(psi)/psi = 0.35 x (1 - phi/phi_d)),
efficiency parabola in phi/phi_d with a small speed penalty, surge at phi/phi_d = 0.80 on every speed line (a map is not
available: an approximation, its spread is carried by the TIT range of the schedule).
Turbine: row-by-row meanline (NGV1, R1, NGV2, R2 at the mean radius): fixed exit flow angles (design: subsonic exits),
throat-equivalent annulus areas, profile losses as a fraction of the row's dynamic head, calibrated to the design point
(mass flow and stage exit pressures of sim/a1000_turbine_design / a1000_turbine.T['stages']).
Pressure losses: intake and the cold side of recuperator + combustor (6.4 % at design) and the hot side + stack (7.5 %)
scaled with the corrected flow squared. Recuperator cold (start): combustor inlet = compressor exit temperature.
Shaft: polar inertia of the HS rotor (a1000_rotordynamics.json discs + shaft) + gearbox + generator rotor through 10:1;
mechanical losses ~ n^2.

Used by sim/engine/a1000_r1_eo24_options.py (the R1 EO24 start-up crossing): the flow state at the crossing speed for the
CFD forcing (sim/cfd/a1000_r1_forcing/make_case.py with A1000_CFD_RPM / _P0 / _T0 / _POUT), and the acceleration rate.
Run:    python sim/engine/a1000_startup.py        (prints the design check and the start line)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_turbine as A                                     # noqa: E402
sys.argv = _argv

ML = json.load(open(os.path.join(ROOT, 'sim', 'mw1_meanline.json')))
C1, C2 = ML['compressor']
CP_A, GAM_A = 1005.0, 1.40; KA = (GAM_A - 1) / GAM_A
CP, GAM = A.CP_G, A.GAM; KG = (GAM - 1) / GAM; RG = CP * KG
P_AMB, T_AMB = 101325.0, 288.15
M_AIR = ML['ma']                                               # kg/s air at design
FAR = 0.017                                                    # fuel / air at design (turbine flow = 1.017 x air)
PR_D = C2['P02'] / C1['P01']                                   # 3.80
W_D = C1['dh0'] + C2['dh0']                                    # J/kg compressor work at design
ETA_CD = (CP_A * T_AMB * (PR_D ** KA - 1)) / W_D               # equivalent total efficiency
DP_IN = 1 - C1['P01'] / P_AMB                                  # intake loss at design
S1, S2 = A.T['stages']
DP_COLD = 1 - S1['P0_in'] / C2['P02']                          # recuperator cold side + combustor
DP_HOT = S2['P0_out'] / P_AMB - 1                              # recuperator hot side + stack
TIT_D = S1['T0_in']
T_RCX = 860.0                                                  # K combustor inlet at design (recuperator air exit)
C_PSI, E_ETA, S_ETA, X_SURGE = 0.35, 0.8, 0.3, 0.80
# polar inertia at the HS shaft [kg m2]: rotor discs (a1000_rotordynamics.json) + shaft ~0.06; gearbox HS side 0.03;
# generator rotor (4-pole 1250 kVA, ~18 kg m2) + LS coupling 0.5 at 1500 rpm through 10:1
J_GEN_LS, RATIO = 18.5, 10.0
P_MECH_D = 22e3                                                # W bearings + gearbox + generator windage at 15,000 rpm


def j_total():
    rd = json.load(open(os.path.join(HERE, 'fea', 'a1000_rotordynamics.json')))
    ip = sum(v['Ip'] for v in rd['A']['discs'].values())
    return ip + 0.06 + 0.03 + J_GEN_LS / RATIO ** 2


# ------------------------------------------------------------------------------------------------ compressor
def compressor(n, x):
    """corrected speed n, flow coefficient ratio x = (m / m_d) / n -> (PR, work J/kg, eta, m kg/s)"""
    w = W_D * n * n * (1 + C_PSI * (1 - x)) * (T_AMB / T_AMB)
    eta = ETA_CD * (1 - E_ETA * (x - 1) ** 2 - S_ETA * (1 - n) ** 2)
    pr = (1 + eta * w / (CP_A * T_AMB)) ** (1 / KA)
    return pr, w, eta, M_AIR * n * x


# ------------------------------------------------------------------------------------------------ turbine (meanline)
ALPHA = dict(N1=math.radians(A.T['alpha2']), R1=math.radians(A.T['beta3']), N2=math.radians(A.T['alpha2']),
             R2=math.radians(A.T['beta3']))
H_EXIT = dict(N1=S1['h_ngv_out'], R1=S1['h_rot_out'], N2=S2['h_ngv_out'], R2=S2['h_rot_out'])
Y_ROW = dict(N1=0.02, R1=0.0, N2=0.03, R2=0.0)                  # rotor losses calibrated below
CAL = dict(kA=1.0)


def _row_exit(P0, T0, m, area, Y):
    """exit static state of a row from its inlet total state (row frame): rho V A = m on the subsonic branch; loss as a
    fraction Y of the dynamic head (P0' = P0 - Y (P0 - p)); returns p, T, V (None if the row cannot pass m)"""
    def mdot(p):
        P0e = P0 - Y * (P0 - p); T = T0 * (p / P0e) ** KG; V = math.sqrt(max(0.0, 2 * CP * (T0 - T)))
        return p / (RG * T) * V * area, T, V
    # maximum of rho V on p in (0.3 P0, P0): critical pressure ratio
    pc = P0 * (2 / (GAM + 1)) ** (1 / KG)
    if mdot(pc)[0] < m: return None
    lo, hi = pc, P0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if mdot(mid)[0] > m: lo = mid
        else: hi = mid
    p = 0.5 * (lo + hi); _, T, V = mdot(p)
    return p, T, V


def turbine(P0, T0, m, n):
    """row-by-row at speed fraction n; returns dict of stations (static p, T, velocities, Mach) and the exit total state"""
    U = A.OM * n * A.RM * 1e-3
    st = {}; P0a, T0a = P0, T0; Ctheta_in = 0.0
    for row in ('N1', 'R1', 'N2', 'R2'):
        a = ALPHA[row]; area = 2 * math.pi * A.RM * 1e-3 * H_EXIT[row] * math.cos(a) * CAL['kA']
        if row[0] == 'N':
            r = _row_exit(P0a, T0a, m, area, Y_ROW[row])
            if r is None: return None
            p, T, V = r; Cx, Ct = V * math.cos(a), V * math.sin(a)
        else:
            # relative inlet state from the absolute state at the previous row exit
            Wx, Wt = Cx, Ct - U; Tin = T; T0r = Tin + (Wx * Wx + Wt * Wt) / (2 * CP); P0r = p * (T0r / Tin) ** (1 / KG)
            r = _row_exit(P0r, T0r, m, area, Y_ROW[row])
            if r is None: return None
            p, T, W = r; Cx, Ct = W * math.cos(a), U - W * math.sin(a)
        C = math.hypot(Cx, Ct); T0a = T + C * C / (2 * CP); P0a = p * (T0a / T) ** (1 / KG)
        st[row] = dict(p=p, T=T, Cx=Cx, Ct=Ct, C=C, M=C / math.sqrt(GAM * RG * T), P0=P0a, T0=T0a, rho=p / (RG * T))
    st['work'] = CP * (T0 - T0a); st['U'] = U
    return st


def turbine_flow(P0, T0, P0_exit, n):
    """mass flow that the turbine passes for the inlet total state and the exit total pressure (bisection on m)"""
    lo, hi = 0.2, 12.0
    for _ in range(70):
        m = 0.5 * (lo + hi); s = turbine(P0, T0, m, n)
        if s is None or s['R2']['P0'] < P0_exit: hi = m
        else: lo = m
    m = 0.5 * (lo + hi); return m, turbine(P0, T0, m, n)


def calibrate():
    """rotor losses from the design stage exit pressures, then the area factor from the design mass flow"""
    m_d = M_AIR * (1 + FAR)
    for _ in range(4):
        for row, P_target in (('R1', S1['P0_out']), ('R2', S2['P0_out'])):
            lo, hi = 0.0, 0.3
            for _ in range(50):
                Y_ROW[row] = 0.5 * (lo + hi); s = turbine(S1['P0_in'], S1['T0_in'], m_d, 1.0)
                if s is None or s[row]['P0'] < P_target: hi = Y_ROW[row]
                else: lo = Y_ROW[row]
        lo, hi = 0.8, 1.2
        for _ in range(50):
            CAL['kA'] = 0.5 * (lo + hi); m, _ = turbine_flow(S1['P0_in'], S1['T0_in'], S2['P0_out'], 1.0)
            if m < m_d: lo = CAL['kA']
            else: hi = CAL['kA']
    return turbine(S1['P0_in'], S1['T0_in'], m_d, 1.0)


# ------------------------------------------------------------------------------------------------ matching
def match(n, tit, T1=T_AMB):
    """unloaded operating point at mechanical speed fraction n and turbine inlet temperature tit [K] (cold recuperator):
    compressor point x on the speed line such that the turbine passes the compressor flow; returns the state or None"""
    nc = n * math.sqrt(T_AMB / T1)
    def resid(x):
        pr, w, eta, m = compressor(nc, x); m *= math.sqrt(T_AMB / T1)
        q = (m / M_AIR) ** 2; T2 = T1 + w / CP_A
        P1 = P_AMB * (1 - DP_IN * q); P2 = P1 * pr
        P0t = P2 * (1 - DP_COLD * q * (C2['P02'] / P2) ** 2 * (T2 + tit) / (T_RCX + TIT_D))
        Pex = P_AMB * (1 + DP_HOT * q * (tit / TIT_D))
        mt, s = turbine_flow(P0t, tit, Pex, n)
        return mt - m * (1 + FAR * (tit - T2) / (TIT_D - T_RCX)), (pr, w, eta, m, P1, P2, P0t, Pex, s)
    lo, hi = X_SURGE * 0.9, 1.3
    rl, rh = resid(lo)[0], resid(hi)[0]
    if rl * rh > 0: return None
    for _ in range(50):
        mid = 0.5 * (lo + hi); r = resid(mid)[0]
        if (r > 0) == (rl > 0): lo, rl = mid, r
        else: hi = mid
    x = 0.5 * (lo + hi); _, (pr, w, eta, m, P1, P2, P0t, Pex, s) = resid(x)
    prs = compressor(nc, X_SURGE)[0]
    sm = (prs / (X_SURGE * nc)) / (pr / (x * nc)) - 1
    mt = m * (1 + FAR * (tit - T1 - w / CP_A) / (TIT_D - T_RCX))
    P_t = mt * s['work']; P_c = m * w; P_mech = P_MECH_D * n ** 2
    J = j_total(); om = A.OM * n
    P_ex = P_t - P_c - P_mech
    return dict(n=n, rpm=15000 * n, tit=tit, x=x, pr=pr, eta_c=eta, m_air=m, m_t=mt, P0_turb=P0t, P_exit=Pex,
                p_ngv2_exit=s['N2']['p'], P0_ngv2_in=s['R1']['P0'], T0_ngv2_in=s['R1']['T0'], surge_margin=sm,
                P_turb=P_t, P_comp=P_c, P_mech=P_mech, P_excess=P_ex, J=J, accel_rpm_s=P_ex / (J * om) * 60 / (2 * math.pi),
                rows={k: v for k, v in s.items() if isinstance(v, dict)}, U=s['U'])


def q_ngv2(st):
    """dynamic head at the NGV2 exit (mean radius), Pa: the scale of its potential field"""
    r = st['rows']['N2']; return 0.5 * r['rho'] * r['C'] ** 2


def design():
    s = calibrate(); m = M_AIR * (1 + FAR)
    return dict(rows=s, m=m, P0=S1['P0_in'], T0=S1['T0_in'], p_ngv2_exit=s['N2']['p'],
                q_ngv2=0.5 * s['N2']['rho'] * s['N2']['C'] ** 2)


if __name__ == '__main__':
    d = design()
    print('turbine calibration: rotor losses R1 %.3f R2 %.3f, area factor %.3f' % (Y_ROW['R1'], Y_ROW['R2'], CAL['kA']))
    for row in ('N1', 'R1', 'N2', 'R2'):
        r = d['rows'][row]
        print('  %s exit: p %.0f Pa, T %.0f K, C %.0f m/s (Cx %.0f), M %.3f, P0 %.0f' % (row, r['p'], r['T'], r['C'], r['Cx'], r['M'], r['P0']))
    print('  design NGV2 exit static p %.0f Pa (make_case P4_ ~ %.0f), dynamic head %.0f Pa' % (d['p_ngv2_exit'], 0, d['q_ngv2']))
    chk = match(1.0, TIT_D)
    print('design match check: x %.3f PR %.3f m %.3f kg/s, P_excess %.0f kW (the generator load), J %.2f kg m2' % (
        chk['x'], chk['pr'], chk['m_air'], chk['P_excess'] / 1e3, chk['J']))
    for tit_c in (450, 550, 650, 750, 850, 950):
        s = match(12270 / 15000, tit_c + 273.15)
        if s is None: print('TIT %d C: no match' % tit_c); continue
        print('12,270 rpm TIT %3d C: x %.3f PR %.2f m %.2f kg/s SM %4.1f %%, P0t %.3f bar, NGV2 exit p %.3f bar, '
              'q_NGV2 %.0f Pa (x%.2f design), excess %4.0f kW, accel %4.0f rpm/s' % (
                  tit_c, s['x'], s['pr'], s['m_air'], 100 * s['surge_margin'], s['P0_turb'] / 1e5, s['p_ngv2_exit'] / 1e5,
                  q_ngv2(s), q_ngv2(s) / d['q_ngv2'], s['P_excess'] / 1e3, s['accel_rpm_s']))
