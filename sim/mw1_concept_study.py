# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "matplotlib"]
# ///
"""AURORA-1000: concept study for a ~1 MWe natural-gas turbine generator set (geared, grid-connected, 24/7).

Cycle model with real-gas properties (NIST Shomate polynomials per species, humid air, CH4 combustion products),
component losses, a gas-supply pressure limit (city gas 3.5 barg minimum at the site, no booster), architecture
comparison, then a meanline-level sizing of the chosen machine for several shaft speeds (centrifugal compressor,
integrally cast axial turbine blisks, epicyclic / parallel gearbox to a 1500 rpm synchronous generator), blade
stress and creep life, recuperator size and a cost estimate.

References for the market comparison (public data): OPRA OP16 (1.9 MWe, radial, PR 6.7, 26,000 rpm, 25-26 %),
Kawasaki M1A-17 (1.7 MWe, 2-stage centrifugal PR 10.5, 3-stage axial turbine, 22,000 rpm, 26-27 %),
Aurelia A400 (400 kWe, two-spool intercooled recuperated, ~40 %), Capstone C1000 (10 x 100 kW recuperated, ~33 %).
Run:  python3 sim/mw1_concept_study.py          writes sim/mw1_results.json and docs/img/mw1_*.png
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
RU = 8.314462618

# ------------------------------------------------------------------------------------------------ gas properties
# NIST Shomate coefficients: (Tmin, Tmax, A, B, C, D, E, F, G, H); t = T/1000; cp J/mol K, H kJ/mol, S J/mol K
SHOMATE = {
    'N2': [(100, 500, 28.98641, 1.853978, -9.647459, 16.63537, 0.000117, -8.671914, 226.4168, 0.0),
           (500, 2000, 19.50583, 19.88705, -8.598535, 1.369784, 0.527601, -4.935202, 212.3900, 0.0)],
    'O2': [(100, 700, 31.32234, -20.23531, 57.86644, -36.50624, -0.007374, -8.903471, 246.7945, 0.0),
           (700, 2000, 30.03235, 8.772972, -3.988133, 0.788313, -0.741599, -11.32468, 236.1663, 0.0)],
    'CO2': [(100, 1200, 24.99735, 55.18696, -33.69137, 7.948387, -0.136638, -403.6075, 228.2431, -393.5224),
            (1200, 6000, 58.16639, 2.720074, -0.492289, 0.038844, -6.447293, -425.9186, 263.6125, -393.5224)],
    'H2O': [(100, 1700, 30.09200, 6.832514, 6.793435, -2.534480, 0.082139, -250.8810, 223.3967, -241.8264),
            (1700, 6000, 41.96426, 8.622053, -1.499780, 0.098119, -11.15764, -272.1797, 219.7809, -241.8264)],
}
MW = dict(N2=28.0134, O2=31.9988, CO2=44.0095, H2O=18.0153, Ar=39.948, CH4=16.043)


def _sp(name, T):
    """sensible enthalpy H-H298 [J/mol] and absolute entropy S [J/mol K] of one species"""
    if name == 'Ar':
        return 20.786 * (T - 298.15), 154.8 + 20.786 * math.log(T / 298.15)
    for lo, hi, A, B, C, D, E, F, G, Hh in SHOMATE[name]:
        if T <= hi or (lo, hi) == SHOMATE[name][-1][:2]:
            t = T / 1000.0
            h = A * t + B * t**2 / 2 + C * t**3 / 3 + D * t**4 / 4 - E / t + F - Hh
            s = A * math.log(t) + B * t + C * t**2 / 2 + D * t**3 / 3 - E / (2 * t**2) + G
            return h * 1000.0, s


class Mix:
    """ideal-gas mixture of fixed composition (mole fractions); mass-specific properties"""
    def __init__(self, x):
        tot = sum(x.values()); self.x = {k: v / tot for k, v in x.items()}
        self.M = sum(self.x[k] * MW[k] for k in self.x) / 1000.0           # kg/mol
        self.R = RU / self.M

    def h(self, T):
        return sum(self.x[k] * _sp(k, T)[0] for k in self.x) / self.M

    def s0(self, T):
        return sum(self.x[k] * _sp(k, T)[1] for k in self.x) / self.M

    def cp(self, T):
        return (self.h(T + 0.5) - self.h(T - 0.5))

    def T_of_h(self, h, T=800.0):
        for _ in range(60):
            dT = (h - self.h(T)) / self.cp(T); T += dT
            if abs(dT) < 1e-6: break
        return T

    def T_isentropic(self, T1, pr):
        """T after an isentropic pressure change by the ratio pr = p2/p1"""
        target = self.s0(T1) + self.R * math.log(pr); T = T1 * pr ** (self.R / self.cp(T1))
        for _ in range(60):
            dT = (target - self.s0(T)) / (self.cp(T) / T); T += dT
            if abs(dT) < 1e-7: break
        return T


def humid_air(T_amb, RH, P):
    psat = 610.94 * math.exp(17.625 * (T_amb - 273.15) / (T_amb - 273.15 + 243.04))
    xw = RH * psat / P
    dry = dict(N2=0.78084, O2=0.20946, Ar=0.00934, CO2=0.00036)
    return {k: v * (1 - xw) for k, v in dry.items()} | {'H2O': xw}


def products(x_air, far_molar):
    """CH4 + 2 O2 -> CO2 + 2 H2O; far_molar = mol CH4 per mol humid air"""
    x = dict(x_air); n = far_molar
    x['O2'] -= 2 * n; x['CO2'] += n; x['H2O'] += 2 * n
    return x


# ------------------------------------------------------------------------------------------------ site and fuel
LHV_VOL = 34.5e6                 # J/Sm3 city gas (project spec)
LHV_CH4 = 50.0e6                 # J/kg, fuel modelled as CH4 for the products; volume via LHV_VOL
GAS_SUPPLY_BARG_MIN = 3.5        # site station: 4 bar, minimum 3.5 bar (docs/03_system_spec.md)
P_ATM = 100725.0                 # 50 m altitude
SITES = dict(ISO=(288.15, 0.60), design_chilled=(288.15, 0.90), borazjan_hot=(319.15, 0.30))
# design_chilled: intake chilled to 15 C by an absorption chiller on exhaust heat (project CCHP concept) -> humid


def p3_max_no_booster(dp_valves=0.40e5, dp_injector_frac=0.12):
    """highest combustor pressure the station supply can feed: supply - fuel train - injector pressure drop"""
    p_man = (GAS_SUPPLY_BARG_MIN * 1e5 + P_ATM) - dp_valves
    return p_man / (1 + dp_injector_frac)


def gas_booster_power(mf, p_out, p_in, T=293.0, eta=0.55):
    """screw/reciprocating booster, polytropic with intercooling ~ isothermal / eta"""
    if p_out <= p_in: return 0.0
    R = RU / (MW['CH4'] / 1000)
    return mf * R * T * math.log(p_out / p_in) / eta


# ------------------------------------------------------------------------------------------------ cycle
BASE = dict(dp_inlet=0.010, dp_rec_c=0.025, dp_comb=0.040, dp_rec_h=0.035, dp_exh=0.015, eta_b=0.995, q_loss=0.005,
            leak=0.015, eta_mech=0.994, eta_gear=0.985, eta_gen=0.972, aux_frac=0.015, eps=0.0, ic=None)


def cycle(c, site='design_chilled'):
    """per kg/s of compressor air. c: PR, TIT [K], eta_c (tt, overall), eta_t (tt, overall), eps, ic (intercooler:
    dict(T_out, dp, split)), booster (bool). Returns specific net electric power and state data."""
    c = dict(BASE, **c)
    T0, RH = SITES[site]
    xa = humid_air(T0, RH, P_ATM); air = Mix(xa)
    P1 = P_ATM * (1 - c['dp_inlet']); T1 = T0
    # compressor (optionally two-stage with an intercooler between the stages)
    if c['ic']:
        pr1 = c['PR'] ** c['ic'].get('split', 0.5)
        T2a = T1 + (air.T_isentropic(T1, pr1) - T1) / c['eta_c']
        w_c = air.h(T2a) - air.h(T1)
        Tic = c['ic']['T_out']; P_ic = P1 * pr1 * (1 - c['ic']['dp'])
        pr2 = P1 * c['PR'] / P_ic
        T2 = Tic + (air.T_isentropic(Tic, pr2) - Tic) / c['eta_c']
        w_c += air.h(T2) - air.h(Tic)
        q_ic = air.h(T2a) - air.h(Tic)
    else:
        T2 = T1 + (air.T_isentropic(T1, c['PR']) - T1) / c['eta_c']
        w_c = air.h(T2) - air.h(T1); q_ic = 0.0
    P2 = P1 * c['PR']
    ma_core = 1.0 - c['leak']                                   # leakage / disc purge bypasses the turbine work
    P2r = P2 * (1 - c['dp_rec_c'] * (c['eps'] > 0)); P3 = P2r * (1 - c['dp_comb'])
    P_back = P_ATM * (1 + c['dp_exh'] + c['dp_rec_h'] * (c['eps'] > 0))
    T5 = 900.0; far = 0.02
    for _ in range(80):
        T2r = T2 + c['eps'] * (T5 - T2) if c['eps'] > 0 else T2
        # combustor energy balance -> molar fuel/air ratio
        for _ in range(30):                                    # f = (dh_p - dh_a) / (LHV eta - dh_p), products of f
            gp = Mix(products(xa, far * air.M / (MW['CH4'] / 1000)))
            dhp = gp.h(c['TIT']) - gp.h(298.15); dha = air.h(T2r) - air.h(298.15)
            far_new = (dhp - dha) / (LHV_CH4 * c['eta_b'] * (1 - c['q_loss']) - dhp)
            if abs(far_new - far) < 1e-10: far = far_new; break
            far = far_new
        mg = ma_core * (1 + far)
        T4s = gp.T_isentropic(c['TIT'], P_back / P3)
        dh_t = c['eta_t'] * (gp.h(c['TIT']) - gp.h(T4s))
        T4 = gp.T_of_h(gp.h(c['TIT']) - dh_t, T4s)
        # leakage air re-joins the exhaust before the recuperator
        h_mix = (mg * gp.h(T4) + c['leak'] * air.h(T2)) / (mg + c['leak'])
        T5_new = gp.T_of_h(h_mix, T4)
        if abs(T5_new - T5) < 0.01: T5 = T5_new; break
        T5 = T5_new
    q_rec = ma_core * (air.h(T2r) - air.h(T2)) if c['eps'] > 0 else 0.0
    m_ex = mg + c['leak']
    T6 = gp.T_of_h(gp.h(T5) - q_rec / m_ex, T5)                # recuperator hot exit (stack / CHP inlet)
    P_shaft = mg * dh_t - w_c
    mf = ma_core * far
    p_booster = gas_booster_power(mf, P3 * 1.12 + 0.40e5, GAS_SUPPLY_BARG_MIN * 1e5 + P_ATM) if c.get('booster') else 0.0
    P_el = P_shaft * c['eta_mech'] * c['eta_gear'] * c['eta_gen']
    P_net = P_el * (1 - c['aux_frac']) - p_booster
    Q_fuel = mf * LHV_CH4
    feasible_gas = c.get('booster') or P3 <= p3_max_no_booster()
    return dict(P_net=P_net, P_shaft=P_shaft, w_c=w_c, w_t=dh_t * mg, eta_el=P_net / Q_fuel, Q_fuel=Q_fuel, mf=mf,
                T2=T2, T2r=T2r, T4=T4, T5=T5, T6=T6, P2=P2, P3=P3, q_rec=q_rec, q_ic=q_ic, booster=p_booster,
                feasible_gas=feasible_gas, m_ex=m_ex, far=far, gas=gp, air=air, P_back=P_back, T1=T1, P1=P1)


def size_for(c, P_target=1000e3, site='design_chilled'):
    r = cycle(c, site); ma = P_target / r['P_net']
    return r, ma


# ------------------------------------------------------------------------------------------------ architectures
ARCH = {
    'SC10': dict(name='simple cycle PR 10.5, TIT 1050 C (Kawasaki M1A-17 / OPRA class)', PR=10.5, TIT=1323.15,
                 eta_c=0.80, eta_t=0.87, booster=True),
    'R38': dict(name='recuperated PR 3.8, TIT 950 C, no gas booster (proposed)', PR=3.8, TIT=1223.15, eta_c=0.82,
                eta_t=0.88, eps=0.90),
    'R45b': dict(name='recuperated PR 4.5, TIT 950 C + small gas booster', PR=4.5, TIT=1223.15, eta_c=0.82,
                 eta_t=0.88, eps=0.90, booster=True),
    'R38_1000': dict(name='recuperated PR 3.8, TIT 1000 C (coated blisk, shorter life)', PR=3.8, TIT=1273.15,
                     eta_c=0.82, eta_t=0.88, eps=0.90),
    'ICR': dict(name='intercooled recuperated PR 7, TIT 1000 C + booster (Aurelia class, 2 spools)', PR=7.0,
                TIT=1273.15, eta_c=0.83, eta_t=0.88, eps=0.90, booster=True, ic=dict(T_out=313.15, dp=0.02)),
}


def pr_sweep():
    out = {}
    for TIT in (1173.15, 1223.15, 1273.15):
        rows = []
        for PR in np.arange(2.6, 7.01, 0.2):
            r = cycle(dict(PR=PR, TIT=TIT, eta_c=0.82, eta_t=0.88, eps=0.90))
            rows.append((float(PR), r['eta_el'], r['P_net'] / 1e3, r['P3'] / 1e5))
        out['%.0f' % (TIT - 273.15)] = rows
    return out


# ------------------------------------------------------------------------------------------------ machine sizing
def compressor_options(r, ma, rpms):
    """single- vs two-stage centrifugal at each speed. Efficiency from a Balje/Rodgers-type specific speed curve."""
    air = r['air']; T1, P1 = r['T1'], r['P1']
    rho1 = P1 / (air.R * T1); Q1 = ma / rho1
    dh_is = air.h(air.T_isentropic(T1, r['P2'] / P1)) - air.h(T1)
    res = []
    for n in rpms:
        w = n * 2 * math.pi / 60
        for stages in (1, 2):
            dh_st = dh_is / stages
            Ns = w * math.sqrt(Q1) / dh_st ** 0.75 if stages == 1 else w * math.sqrt(Q1 / 1.6) / dh_st ** 0.75
            eta = 0.845 - 0.20 * math.log(Ns / 0.72) ** 2 - (0.01 if stages == 1 and dh_st > 160e3 else 0.0)
            if stages == 2: eta += 0.008                     # lower Mach per stage, better diffusion
            U2 = math.sqrt(dh_st / eta / 0.72)               # work coefficient ~0.72 with backsweep 35-40 deg
            D2 = 2 * U2 / w
            mat = 'Al 2618-T61' if (U2 <= 470 and r['T2'] < 470) else ('Ti-6Al-4V' if U2 <= 560 else 'too fast')
            res.append(dict(rpm=n, stages=stages, Ns=Ns, eta=eta, U2=U2, D2=D2, material=mat))
    return res


def turbine_options(r, ma, rpms, psi_max=1.9, Cx=180.0, clearance=0.40e-3, U_hub_max=None):
    """integrally cast axial turbine (blisks): number of stages, mean radius, blade heights, efficiency (Smith-chart
    fit + tip clearance + low aspect ratio penalties), root stress (P/A with taper factor 0.6) and AN2."""
    gp = r['gas']; mg = ma * (1 - BASE['leak']) * (1 + r['far'])
    dh_tot = gp.h(ARCH_SEL['TIT']) - gp.h(r['T4'])
    res = []
    for n in rpms:
        w = n * 2 * math.pi / 60
        for z in (1, 2, 3, 4):
            dh_st = dh_tot / z
            # choose U_mean for the loading limit, capped by a mean blade speed of 420 m/s (cast MAR-M247 blisk)
            Um = min(math.sqrt(dh_st / 1.25), 420.0)
            psi = dh_st / Um**2
            if psi > psi_max + 1e-9:
                Um = math.sqrt(dh_st / psi_max); psi = psi_max
            rm = Um / w
            # blade heights: inlet of stage 1 rotor and exit of last stage
            P3, T3 = r['P3'], ARCH_SEL['TIT']
            T_in1 = T3 - 0.5 * dh_st / gp.cp(T3)
            P_in1 = P3 * (T_in1 / T3) ** (gp.cp(T3) / gp.R / 0.92)
            rho_in = P_in1 / (gp.R * T_in1)
            h1 = mg / (rho_in * Cx * 2 * math.pi * rm)
            rho_ex = r['P_back'] * 1.03 / (gp.R * r['T4'])
            h_ex = mg / (rho_ex * Cx * 1.10 * 2 * math.pi * rm)
            phi = Cx / Um
            eta0 = 0.935 - 0.045 * (psi - 1.2) ** 2 - 0.10 * (phi - 0.55) ** 2     # Smith chart, large-scale
            d_clear = 1.6 * clearance / h1 * (1.0 if z == 1 else 0.7)               # shrouds-less blisks, rows avg
            d_ar = 0.015 if h1 < 0.020 else (0.008 if h1 < 0.030 else 0.0)           # secondary loss of short blades
            eta = eta0 - d_clear - d_ar - 0.004 * (z - 1)                            # interstage seals / leakage
            rt, rh = rm + h_ex / 2, rm - h_ex / 2
            A_ex = 2 * math.pi * rm * h_ex
            sigma_root = 8500 * w**2 * A_ex / (2 * math.pi) * 0.60 / 1e6              # last-stage blade root P/A, MPa
            rt1, rh1 = rm + h1 / 2, rm - h1 / 2
            sigma_root1 = 8500 * w**2 * (2 * math.pi * rm * h1) / (2 * math.pi) * 0.60 / 1e6
            res.append(dict(rpm=n, stages=z, Um=Um, psi=psi, phi=phi, rm=rm, h1=h1, h_ex=h_ex, hub_tip1=rh1 / rt1,
                            hub_tip_ex=rh / rt, eta=eta, sigma_root_last=sigma_root, sigma_root_first=sigma_root1,
                            AN2=A_ex * n**2, U_tip_ex=w * rt))
    return res


# Larson-Miller master curve, equiaxed cast MAR-M247 (TYPICAL), P = T (20 + log10 t) / 1000, T [K], t [h]. Consistent
# with the handbook 100 / 1000 h rupture strengths at 760-980 C (Nickel Institute 393 / ASM vol. 1, quoted from memory: the
# primary tables could not be read from this environment) and with > 1500 h at 871 C / 250 MPa (Pan et al., Metals 13,
# 2023). Rev 4 (review): the earlier 3-anchor fit did not pass through its anchors and was optimistic below ~200 MPa.
LMP_P = (22.5, 24.0, 25.5, 27.0, 28.0, 29.0, 30.0)
LMP_S = (700.0, 560.0, 420.0, 260.0, 190.0, 135.0, 95.0)


def mar_m247_rupture_stress(P, curve='min'):
    """rupture stress [MPa] at Larson-Miller parameter P; curve 'typical' or 'min' (design minimum: 0.8 x typical stress,
    a further 10 % knock-down from P 28 to 29 and above for long-term ageing and the low-stress data scatter)"""
    lp, ls = np.array(LMP_P), np.log10(LMP_S)
    if P <= lp[0]: v = ls[0] + (ls[1] - ls[0]) / (lp[1] - lp[0]) * (P - lp[0])
    elif P >= lp[-1]: v = ls[-1] + (ls[-1] - ls[-2]) / (lp[-1] - lp[-2]) * (P - lp[-1])
    else: v = float(np.interp(P, lp, ls))
    s = 10 ** v
    if curve == 'min':
        s *= 0.8 * (1.0 - 0.1 * min(max(P - 28.0, 0.0), 1.0))
    return s


def mar_m247_rupture_hours(sigma_MPa, T_K, curve='min'):
    """rupture life [h] at stress sigma and metal temperature T_K on the 'min' (design) or 'typical' curve"""
    lo, hi = 15.0, 34.0
    for _ in range(80):
        m = 0.5 * (lo + hi)
        if mar_m247_rupture_stress(m, curve) > sigma_MPa: lo = m
        else: hi = m
    return 10 ** (0.5 * (lo + hi) * 1000.0 / T_K - 20.0)


def gearbox(rpm_in, P_kW, n_out=1500):
    ratio = rpm_in / n_out
    if ratio <= 7.5:
        kind = 'single-stage parallel-shaft (double helical)'
    elif ratio <= 13:
        kind = 'single-stage epicyclic (star) or two-stage parallel-shaft'
    else:
        kind = 'two-stage epicyclic or compound parallel-shaft'
    pitchline = None
    return dict(ratio=ratio, kind=kind, eta=0.985 if ratio <= 13 else 0.980, loss_kW=P_kW * (1 - (0.985 if ratio <= 13 else 0.98)))


def recuperator(r, ma, U=120.0):
    air = r['air']
    C_cold = ma * (1 - BASE['leak']) * air.cp(0.5 * (r['T2'] + r['T2r']))
    C_hot = r['m_ex'] * ma * r['gas'].cp(0.5 * (r['T5'] + r['T6']))
    Cmin, Cmax = min(C_cold, C_hot), max(C_cold, C_hot); Cr = Cmin / Cmax
    eps = ARCH_SEL['eps']
    NTU = math.log((1 - eps * Cr) / (1 - eps)) / (1 - Cr) if Cr < 0.999 else eps / (1 - eps)
    UA = NTU * Cmin; A = UA / U
    return dict(Q_kW=r['q_rec'] * ma / 1e3, NTU=NTU, UA_kW_K=UA / 1e3, area_m2=A,
                mass_t=A * 2 * 0.10e-3 * 7900 * 1.9 / 1000 + 1.2)   # 0.1 mm 347 foil both sides x1.9 structure + casing


# ------------------------------------------------------------------------------------------------ main
ARCH_SEL = ARCH['R38']
RPMS = [12000, 15000, 18000, 21000]
SEL_RPM = 15000


def main():
    out = dict(p3_max_no_booster_bar=p3_max_no_booster() / 1e5, architectures={})
    print('Gas supply %.1f barg min -> highest combustor pressure without a booster: %.2f bar abs' %
          (GAS_SUPPLY_BARG_MIN, p3_max_no_booster() / 1e5))
    print('\n%-72s %6s %6s %6s %6s %7s %6s %6s' % ('architecture (1000 kWe net, intake chilled to 15 C)', 'air', 'eta_el',
          'gas', 'P3', 'T_exh', 'boost', 'gasOK'))
    for k, c in ARCH.items():
        r, ma = size_for(c)
        gas = r['Q_fuel'] * ma / LHV_VOL * 3600
        row = dict(name=c['name'], ma=ma, eta_el=r['eta_el'], gas_m3h=gas, P3_bar=r['P3'] / 1e5, T_exh_C=r['T6'] - 273.15,
                   booster_kW=r['booster'] * ma / 1e3, gas_ok=bool(r['feasible_gas']), T4_C=r['T4'] - 273.15,
                   q_rec_kW=r['q_rec'] * ma / 1e3)
        out['architectures'][k] = row
        print('%-72s %6.2f %6.1f %6.0f %6.2f %7.0f %6.1f %6s' % (c['name'], ma, r['eta_el'] * 100, gas, r['P3'] / 1e5,
              r['T6'] - 273.15, r['booster'] * ma / 1e3, 'yes' if r['feasible_gas'] else 'NO'))
    # ambient sensitivity of the proposed machine (fixed air flow at the chilled design)
    r0, ma0 = size_for(ARCH_SEL)
    print('\nProposed R38 at fixed corrected flow:')
    out['ambient'] = {}
    for site in SITES:
        r = cycle(ARCH_SEL, site)
        T0 = SITES[site][0]
        ma_s = ma0 * math.sqrt(288.15 / T0)                     # constant corrected flow (fixed speed, choked turbine)
        P = r['P_net'] * ma_s
        out['ambient'][site] = dict(P_kW=P / 1e3, eta=r['eta_el'])
        print('  %-16s %6.0f kWe  eta %5.1f %%' % (site, P / 1e3, r['eta_el'] * 100))
    # CHP: exhaust heat to an absorption chiller / hot water down to 90 C
    r = r0; ma = ma0
    gp = r['gas']; Q_chp = r['m_ex'] * ma * (gp.h(r['T6']) - gp.h(363.15)) * 0.92
    print('  CHP heat (exhaust %.0f C -> 90 C): %.0f kW, total efficiency %.1f %%' %
          (r['T6'] - 273.15, Q_chp / 1e3, (1000e3 + Q_chp) / (r['Q_fuel'] * ma) * 100))
    out['chp'] = dict(Q_kW=Q_chp / 1e3, eta_tot=(1000e3 + Q_chp) / (r['Q_fuel'] * ma), T_exh_C=r['T6'] - 273.15)
    # sizing
    comp = compressor_options(r, ma, RPMS); turb = turbine_options(r, ma, RPMS)
    print('\nCompressor options (PR %.1f, %.2f kg/s):' % (ARCH_SEL['PR'], ma))
    for o in comp:
        print('  %5.0f rpm %d-stage  Ns %.2f  eta %.3f  U2 %3.0f m/s  D2 %3.0f mm  %s' % (
            o['rpm'], o['stages'], o['Ns'], o['eta'], o['U2'], o['D2'] * 1e3, o['material']))
    print('\nAxial turbine options (cast blisks):')
    for o in turb:
        if o['stages'] == 1 and o['psi'] > 1.89: flag = '  (overloaded)'
        else: flag = ''
        print('  %5.0f rpm %d st  Um %3.0f  psi %.2f  phi %.2f  Dm %3.0f mm  h1 %4.1f / hex %4.1f mm  hub/tip %.2f/%.2f  '
              'eta %.3f  root %3.0f/%3.0f MPa%s' % (o['rpm'], o['stages'], o['Um'], o['psi'], o['phi'], 2 * o['rm'] * 1e3,
              o['h1'] * 1e3, o['h_ex'] * 1e3, o['hub_tip1'], o['hub_tip_ex'], o['eta'], o['sigma_root_first'],
              o['sigma_root_last'], flag))
    out['compressor'] = comp; out['turbine'] = turb
    # selected point
    sel_rpm = SEL_RPM
    cs_ = [o for o in comp if o['rpm'] == sel_rpm and o['stages'] == 2][0]
    ts_ = [o for o in turb if o['rpm'] == sel_rpm and o['stages'] == 2][0]
    gb = gearbox(sel_rpm, r['P_shaft'] * ma / 1e3)
    rec = recuperator(r, ma)
    # creep life of stage-1 rotor blades: metal ~ relative total temperature - 0 (uncooled) + pattern factor margin
    # rotor-relative total temperature at stage-1 inlet ~ TIT - 0.55 x stage-1 work (absolute kinetic energy above the
    # relative one) + 25 K radial / circumferential pattern margin; the blade root (max stress) sits ~30 K cooler
    T_rel = ARCH_SEL['TIT'] - 0.5 * (ARCH_SEL['TIT'] - r['T4']) * 0.55 + 25.0
    T_root = T_rel - 30.0
    life = mar_m247_rupture_hours(ts_['sigma_root_first'] * 1.5, T_root, 'typical')
    life_last = mar_m247_rupture_hours(ts_['sigma_root_last'] * 1.5, r['T4'] + 40 - 30, 'typical')
    # cycle with the component efficiencies the sizing supports (selected compressor / turbine, -1.5 pt margin)
    r_tgt, ma_tgt = size_for(dict(ARCH_SEL, eta_c=cs_['eta'] - 0.015, eta_t=ts_['eta'] - 0.015))
    out['selected'] = dict(rpm=sel_rpm, compressor=cs_, turbine=ts_, gearbox=gb, recuperator=rec,
                           blade1_metal_C=T_rel - 273.15, blade1_rupture_h_x1p5=life, blade_last_rupture_h_x1p5=life_last,
                           ma=ma, eta_el=r['eta_el'], gas_m3h=r['Q_fuel'] * ma / LHV_VOL * 3600, blade1_root_C=T_root - 273.15,
                           eta_el_target=r_tgt['eta_el'], ma_target=ma_tgt,
                           gas_m3h_target=r_tgt['Q_fuel'] * ma_tgt / LHV_VOL * 3600)
    print('\nSelected: %d rpm, 2-stage centrifugal (D2 %.0f mm, %s) + 2-stage cast axial turbine (Dm %.0f mm)' %
          (sel_rpm, cs_['D2'] * 1e3, cs_['material'], ts_['rm'] * 2e3))
    print('  gearbox: ratio %.1f, %s, loss %.0f kW' % (gb['ratio'], gb['kind'], gb['loss_kW']))
    print('  recuperator: %.0f kW, NTU %.1f, %.0f m2, ~%.1f t' % (rec['Q_kW'], rec['NTU'], rec['area_m2'], rec['mass_t']))
    print('  stage-1 blade metal ~%.0f C (root %.0f C), root %.0f MPa -> rupture life at 1.5x stress: %.2g h; last stage %.2g h' % (
        T_rel - 273.15, T_root - 273.15, ts_['sigma_root_first'], life, life_last))
    print('  cycle with the sized components (eta_c %.3f, eta_t %.3f): eta_el %.1f %%, air %.2f kg/s, gas %.0f m3/h' % (
        cs_['eta'] - 0.015, ts_['eta'] - 0.015, r_tgt['eta_el'] * 100, ma_tgt, r_tgt['Q_fuel'] * ma_tgt / LHV_VOL * 3600))
    for n_ in RPMS:
        t2 = [o for o in turb if o['rpm'] == n_ and o['stages'] == 2][0]
        print('    %5d rpm: stage-1 root %3.0f MPa -> life at 1.5x stress %.2g h' % (
            n_, t2['sigma_root_first'], mar_m247_rupture_hours(t2['sigma_root_first'] * 1.5, T_root, 'typical')))
    out['pr_sweep'] = pr_sweep()
    json.dump(out, open(os.path.join(HERE, 'mw1_results.json'), 'w'), indent=1, default=float)
    plots(out)


def plots(out):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    img = os.path.join(ROOT, 'docs', 'img'); os.makedirs(img, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=130)
    for TIT, rows in out['pr_sweep'].items():
        a = np.array(rows); ax.plot(a[:, 0], a[:, 1] * 100, lw=2, label='TIT %s °C' % TIT)
    p3m = out['p3_max_no_booster_bar']
    ax.axvline(3.85, color='k', ls='--', lw=1)
    ax.text(3.9, ax.get_ylim()[0] + 0.5, 'gas-supply limit\n(no booster)', fontsize=8)
    ax.set_xlabel('compressor pressure ratio'); ax.set_ylabel('net electric efficiency [%]')
    ax.set_title('Recuperated single-shaft (ε 0.90, ηc 0.82, ηt 0.88), intake 15 °C, 1 MWe')
    ax.grid(alpha=0.3); ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(img, 'mw1_eta_vs_pr.png')); plt.close(fig)


if __name__ == '__main__':
    main()
