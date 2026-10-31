"""GR180 version E - real-gas properties for the cycle and the meanlines (sim/variant_e/*.py).

Ideal-gas mixtures of N2, O2, Ar, CO2, H2O with temperature-dependent cp (tabulated, standard ideal-gas tables,
250-1500 K, piecewise linear -> exact h(T) and s0(T) integrals).  Moist inlet air (relative humidity), city gas
burnt as CH4-equivalent (products per kg fuel from CH4 stoichiometry; LHV on a mass basis matched to the city-gas
volumetric LHV 34.5 MJ/m3).  Reference state for enthalpy: 298.15 K (h = 0 for every species).
"""
import math

RU = 8314.46
M = dict(N2=28.013, O2=31.999, Ar=39.948, CO2=44.010, H2O=18.015)
TN = [250, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500]
CP = {                                                     # kJ/(kg K), ideal gas
    'N2': [1.039, 1.040, 1.044, 1.056, 1.075, 1.098, 1.121, 1.145, 1.167, 1.186, 1.204, 1.219, 1.232, 1.244],
    'O2': [0.913, 0.918, 0.941, 0.972, 1.003, 1.031, 1.054, 1.074, 1.090, 1.103, 1.115, 1.125, 1.134, 1.143],
    'Ar': [0.5203] * 14,
    'CO2': [0.791, 0.846, 0.939, 1.014, 1.075, 1.126, 1.169, 1.204, 1.234, 1.259, 1.280, 1.298, 1.313, 1.326],
    'H2O': [1.855, 1.864, 1.901, 1.954, 2.015, 2.080, 2.147, 2.216, 2.284, 2.350, 2.413, 2.471, 2.526, 2.576]}
DRY_AIR = dict(N2=0.7552, O2=0.2314, Ar=0.0129, CO2=0.0005)
LHV_VOL = 34.5e6                                           # J/m3 city gas (user), standard m3
RHO_GAS = 0.726                                            # kg/m3 at the same reference -> LHV_mass 47.5 MJ/kg
LHV = LHV_VOL / RHO_GAS
FUEL_PRODUCTS = dict(CO2=2.744, H2O=2.246, O2=-3.990)      # kg per kg fuel (CH4-equivalent)
STOICH_FAR = DRY_AIR['O2'] / 3.990                        # kg fuel / kg dry air (~0.058)
T_REF = 298.15

# --------------------------------------------------------------- per-species cumulative integrals on the nodes
_H, _S = {}, {}
for sp in CP:
    c = [v * 1e3 for v in CP[sp]]
    H = [0.0]; S = [0.0]
    for k in range(len(TN) - 1):
        a, b = TN[k], TN[k + 1]
        sl = (c[k + 1] - c[k]) / (b - a)
        H.append(H[-1] + c[k] * (b - a) + 0.5 * sl * (b - a) ** 2)
        A0 = c[k] - sl * a
        S.append(S[-1] + A0 * math.log(b / a) + sl * (b - a))
    _H[sp], _S[sp] = H, S


def _seg(T):
    if T <= TN[0]:
        return 0
    if T >= TN[-1]:
        return len(TN) - 2
    for k in range(len(TN) - 1):
        if TN[k] <= T <= TN[k + 1]:
            return k
    return len(TN) - 2


def _hs_sp(sp, T):
    k = _seg(T)
    a = TN[k]
    c0 = CP[sp][k] * 1e3; c1 = CP[sp][k + 1] * 1e3
    sl = (c1 - c0) / (TN[k + 1] - a)
    h = _H[sp][k] + c0 * (T - a) + 0.5 * sl * (T - a) ** 2
    A0 = c0 - sl * a
    s = _S[sp][k] + A0 * math.log(T / a) + sl * (T - a)
    return h, s, c0 + sl * (T - a)


_HREF = {sp: _hs_sp(sp, T_REF)[0] for sp in CP}


class Mix:
    """ideal-gas mixture given by mass fractions"""

    def __init__(self, y):
        tot = sum(y.values())
        self.y = {k: v / tot for k, v in y.items() if v > 0}
        self.R = RU * sum(v / M[k] for k, v in self.y.items())

    def h(self, T):
        return sum(v * (_hs_sp(k, T)[0] - _HREF[k]) for k, v in self.y.items())

    def s0(self, T):
        return sum(v * _hs_sp(k, T)[1] for k, v in self.y.items())

    def cp(self, T):
        return sum(v * _hs_sp(k, T)[2] for k, v in self.y.items())

    def gamma(self, T):
        c = self.cp(T)
        return c / (c - self.R)

    def T_from_h(self, h, T0=600.0):
        T = T0
        for _ in range(60):
            dT = (self.h(T) - h) / self.cp(T)
            T -= dT
            if abs(dT) < 1e-6:
                break
        return T

    def T_isentropic(self, T1, pr):
        """temperature after an isentropic change by pressure ratio pr = p2/p1"""
        target = self.s0(T1) + self.R * math.log(pr)
        T = T1 * pr ** (0.28 if pr > 1 else 0.25)
        for _ in range(80):
            f = self.s0(T) - target
            T -= f / (self.cp(T) / T)
            if abs(f) < 1e-7:
                break
        return T


def p_sat(T):
    """water saturation pressure [Pa], Magnus (0-60 C)"""
    tc = T - 273.15
    return 610.94 * math.exp(17.625 * tc / (tc + 243.04))


def moist_air(T, P, RH):
    w = 0.622 * RH * p_sat(T) / (P - RH * p_sat(T))          # kg water / kg dry air
    y = dict(DRY_AIR); y['H2O'] = w
    return Mix(y), w


def products(air, far):
    """combustion products of 1 kg of (moist) air + far kg fuel"""
    y = {k: v for k, v in air.y.items()}
    for k, v in FUEL_PRODUCTS.items():
        y[k] = y.get(k, 0.0) + far * v
    return Mix(y)


def site_pressure(z=50.0):
    return 101325.0 * (1 - 2.25577e-5 * z) ** 5.25588


if __name__ == '__main__':
    a, w = moist_air(303.15, site_pressure(), 0.40)
    p = products(a, 0.015)
    for T in (303.15, 500.0, 800.0, 1043.15, 1123.15):
        print('T %.0f  cp_air %.1f gamma %.4f | cp_prod %.1f gamma %.4f R %.1f' % (T, a.cp(T), a.gamma(T), p.cp(T), p.gamma(T), p.R))
    print('w = %.4f, R_air %.1f, LHV mass %.2f MJ/kg' % (w, a.R, LHV / 1e6))
