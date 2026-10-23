"""Real-gas enthalpy of dry air and lean CH4 exhaust (ideal-gas mixture, cp(T) polynomials of Cengel Table A-2c).

Same property basis as sim/engine/e4_recuperator_calc.py (E4), so the cycle's as-built option and E4 give the same
recuperator duty and hot-outlet temperature.  T in K, h in J/kg (zero reference is arbitrary; use differences only).
"""
CPP = {'N2': (28.90, -0.1571e-2, 0.8081e-5, -2.873e-9, 28.013), 'O2': (25.48, 1.520e-2, -0.7155e-5, 1.312e-9, 31.999),
       'CO2': (22.26, 5.981e-2, -3.501e-5, 7.469e-9, 44.010), 'H2O': (32.24, 0.1923e-2, 1.055e-5, -3.595e-9, 18.015),
       'Ar': (20.786, 0.0, 0.0, 0.0, 39.948)}                                    # kJ/kmol K, M kg/kmol
M_CH4 = 16.043


def air_moles(m=1.0):
    Md = 0.7808 * 28.013 + 0.2095 * 31.999 + 0.0093 * 39.948 + 0.0004 * 44.010
    n = m / Md
    return {'N2': 0.7808 * n, 'O2': 0.2095 * n, 'Ar': 0.0093 * n, 'CO2': 0.0004 * n, 'H2O': 0.0}


class Gas:
    def __init__(self, moles):
        m = sum(v * CPP[k][4] for k, v in moles.items())
        self.w = {k: v * CPP[k][4] / m for k, v in moles.items()}

    def cp(self, T):
        return 1e3 * sum(w * (a + b * T + c * T * T + d * T ** 3) / M for k, w in self.w.items() for a, b, c, d, M in [CPP[k]])

    def h(self, T):
        return 1e3 * sum(w * (a * T + b * T * T / 2 + c * T ** 3 / 3 + d * T ** 4 / 4) / M
                         for k, w in self.w.items() for a, b, c, d, M in [CPP[k]])

    def T_of_h(self, hv, T=600.0):
        for _ in range(30):
            dT = (self.h(T) - hv) / self.cp(T)
            T -= dT
            if abs(dT) < 1e-7:
                break
        return T

    def cp_mean(self, T1, T2):
        return (self.h(T1) - self.h(T2)) / (T1 - T2)


AIR = Gas(air_moles())


def exhaust(far):
    """Products of 1 kg dry air + far kg CH4 (complete combustion)."""
    x = air_moles()
    nf = far / M_CH4
    x['O2'] -= 2 * nf
    x['CO2'] += nf
    x['H2O'] += 2 * nf
    return Gas(x)
