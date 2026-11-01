#!/usr/bin/env python3
"""AURORA-1000 combustor chemistry (Cantera, GRI-Mech 3.0) for sim/engine/a1000_combustor.py.

Needs Cantera (not in the gr180 env):  python -m venv --system-site-packages <dir> && <dir>/bin/pip install cantera
Run:    <dir>/bin/python sim/engine/a1000_combustor_chem.py        (~5 min, < 300 MB)
Writes: sim/engine/fea/a1000_combustor_chem.json  (read by a1000_combustor.py, which runs without Cantera)

Contents, all at the primary-zone pressure P_PZ, air + city gas at 15 C, adiabatic mixing of the two streams:
  flames    1-D freely propagating premixed flames over phi = 0.30..0.70 at the recuperator air temperatures of the load
            points (T2r from the cycle: 100 % load 886 K, hot day 892 K, 90 / 75 / 50 % load): S_L, T_ad, thermal
            diffusivity of the unburnt gas, flame thickness, NO / CO behind the flame; then a Lagrangian PFR of the burnt
            gas (primary zone) and instantaneous dilution to the turbine inlet temperature of that load point followed by a
            second PFR (dilution zone + scroll): NOx and CO in ppmvd at 15 % O2 against residence time
  ignition  constant-pressure ignition delay of the premixer mixture over phi = 0.1..1.5 and air 886..950 K, nominal
            and C2+-rich gas (auto-ignition margin of the premixer)
  psr       perfectly-stirred-reactor blow-out residence time against phi (lean blow-out margin of the flame anchor)
  staged    part load with only some premixers fuelled: the fuelled premixers burn at phi_f, the unfuelled premix air
            (at the recuperator air temperature) is entrained after 3 ms, the dilution air after the primary zone
GRI-Mech 3.0 is validated for methane / natural gas at 1-10 atm in flames; below 1000 K its ignition delays are
long against shock-tube data for gas with C2+ (factor 2-10): the margin is quoted against an assumed factor 10.
"""
import json
import math
import os
import sys
import time

import numpy as np
import cantera as ct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import a1000_combustor as C                                   # noqa: E402  (design point, gas, split; no Cantera there)

OUT = os.path.join(HERE, 'fea', 'a1000_combustor_chem.json')
MECH = 'gri30.yaml'
P_PZ = C.DP['P_pz']
AIR = 'O2:0.21, N2:0.79'                                        # dry air (humidity lowers NOx a little: conservative)
T_FUEL = 288.15
PHIS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
T_PZ_MS = [2.0, 5.0, 10.0, 15.0, 20.0, 30.0]                   # primary-zone residence times after the flame [ms]
T_DZ_MS = [2.0, 5.0, 10.0, 20.0, 30.0]                          # dilution zone + scroll [ms]
gas = ct.Solution(MECH)
iNO, iNO2, iCO, iO2, iH2O = (gas.species_index(s) for s in ('NO', 'NO2', 'CO', 'O2', 'H2O'))


def comp(name):
    return ', '.join('%s:%g' % kv for kv in C.GAS[name].items())


def mix(phi, T_air, fuel):
    """adiabatic mixture of air at T_air and fuel at 15 C at equivalence ratio phi -> gas state; returns fuel mass fraction"""
    gas.TPX = T_air, P_PZ, AIR; ha = gas.enthalpy_mass
    gas.TPX = T_FUEL, P_PZ, fuel; hf = gas.enthalpy_mass
    gas.set_equivalence_ratio(phi, fuel, AIR); Y = gas.Y.copy(); mf = gas.mixture_fraction(fuel, AIR)
    gas.HPY = (1 - mf) * ha + mf * hf, P_PZ, Y
    return mf


def ppm15(X):
    """(NOx, CO) in ppmvd at 15 % O2 from a mole-fraction vector"""
    dry = 1.0 - X[iH2O]; o2 = 100.0 * X[iO2] / dry
    k = (20.9 - 15.0) / max(20.9 - o2, 0.5)
    return (X[iNO] + X[iNO2]) / dry * 1e6 * k, X[iCO] / dry * 1e6 * k


def pfr(state_TPY, times_ms):
    """Lagrangian constant-pressure reactor from a state; (NOx, CO) ppm15 at the times"""
    gas.TPY = state_TPY
    r = ct.IdealGasConstPressureReactor(gas, clone=True); net = ct.ReactorNet([r])
    out = []
    for t in times_ms:
        net.advance(t * 1e-3)
        out.append(ppm15(r.phase.X) + (r.phase.T,))
    return out, (r.phase.T, r.phase.P, r.phase.Y.copy())


def dilute(state_TPY, T_air, T_target):
    """mix burnt gas with air (T_air) to reach T_target (mass-weighted enthalpy) -> new state, air mass per kg gas"""
    T, P, Y = state_TPY
    gas.TPY = T, P, Y; hb = gas.enthalpy_mass
    ga = ct.Solution(MECH); ga.TPX = T_air, P, AIR; ha = ga.enthalpy_mass; Ya = ga.Y
    lo, hi = 0.0, 50.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        Ym = (Y + m * Ya) / (1 + m); gas.HPY = (hb + m * ha) / (1 + m), P, Ym
        if gas.T > T_target: lo = m
        else: hi = m
    return (gas.T, P, gas.Y.copy()), 0.5 * (lo + hi)


def flame(phi, T_air, fuel):
    mix(phi, T_air, fuel)
    Tu = gas.T; rho_u = gas.density; alpha = gas.thermal_conductivity / (rho_u * gas.cp_mass)
    f = ct.FreeFlame(gas, width=0.02)
    f.set_refine_criteria(ratio=3, slope=0.08, curve=0.15)
    f.solve(loglevel=0, auto=True)
    T = f.T; x = f.grid
    dTdx = np.max(np.gradient(T, x)); delta = (T[-1] - T[0]) / dTdx
    end = (T[-1], f.P, f.Y[:, -1].copy())
    no_f, co_f = ppm15(f.X[:, -1])
    gas.TPY = end; gas.equilibrate('HP'); Tad = gas.T
    return dict(phi=phi, T_air=T_air, Tu=Tu, SL=float(f.velocity[0]), Tad=Tad, alpha_u=alpha, delta_L=delta,
                rho_u=rho_u, NOx_flame=no_f, CO_flame=co_f), end


def tau_ign(phi, T_air, fuel, tmax=20.0):
    mix(phi, T_air, fuel); T0 = gas.T
    r = ct.IdealGasConstPressureReactor(gas, clone=True); net = ct.ReactorNet([r])
    while net.time < tmax:
        net.step()
        if r.phase.T > T0 + 400.0: return net.time, T0
    return float('inf'), T0


def psr_burns(phi, T_air, fuel, tau):
    """steady PSR at residence time tau [s], started from the burnt state; True if still burning"""
    mix(phi, T_air, fuel); Tu = gas.T
    inlet = ct.Reservoir(gas)
    gas.equilibrate('HP'); Tad = gas.T
    r = ct.IdealGasReactor(gas, energy='on', clone=True); r.volume = 1e-4
    exhaust = ct.Reservoir(gas)
    mdot = r.mass / tau
    mfc = ct.MassFlowController(inlet, r, mdot=mdot)
    ct.PressureController(r, exhaust, primary=mfc, K=1e-5)
    net = ct.ReactorNet([r])
    net.advance(50 * tau)
    return r.phase.T > Tu + 0.5 * (Tad - Tu)


def psr_blowout(phi, T_air, fuel):
    lo, hi = 1e-6, 1e-1                                         # s: lo blows out, hi burns
    if not psr_burns(phi, T_air, fuel, hi): return float('inf')
    for _ in range(18):
        m = math.sqrt(lo * hi)
        if psr_burns(phi, T_air, fuel, m): hi = m
        else: lo = m
    return hi


def staged(case):
    """part load: fuelled premixers at phi_f; the unfuelled premix air joins after 3 ms, the dilution air after the PZ"""
    fuel = comp('nominal')
    _, end = flame(case['phi_f'], case['T_air'], fuel)
    s1, st = pfr(end, [3.0])
    if case['x_unf'] > 0:                                       # unfuelled premix air per kg of fuelled premix gas
        T, P, Y = st; gas.TPY = T, P, Y; hb = gas.enthalpy_mass
        ga = ct.Solution(MECH); ga.TPX = case['T_air'], P, AIR
        m = case['x_unf']; Ym = (Y + m * ga.Y) / (1 + m)
        gas.HPY = (hb + m * ga.enthalpy_mass) / (1 + m), P, Ym; st = (gas.T, P, gas.Y.copy())
    s2, st = pfr(st, [case['tau_pz_ms'] - 3.0])
    T_pz = st[0]
    st, _ = dilute(st, case['T_air'] + 10.0, case['TIT'])
    s3, _ = pfr(st, T_DZ_MS)
    return dict(case, T_pz_end=T_pz, NOx_pz=s2[0][0], CO_pz=s2[0][1], exit=[dict(t_ms=t, NOx=a, CO=b) for t, (a, b, _) in zip(T_DZ_MS, s3)])


def main():
    t0 = time.time()
    out = dict(mech=MECH, P_pz_bar=P_PZ / 1e5, gas=C.GAS, phis=PHIS, t_pz_ms=T_PZ_MS, t_dz_ms=T_DZ_MS)
    # ---------------------------------------------------------------------------------------------- fuel properties
    props = {}
    for name in C.GAS:
        fuel = comp(name)
        gas.TPX = 298.15, ct.one_atm, fuel; Wf = gas.mean_molecular_weight; X = dict(zip(gas.species_names, gas.X))
        n = {e: sum(x * gas.n_atoms(s, e) for s, x in X.items() if x > 0) for e in ('C', 'H', 'O')}
        h = lambda s: gas.species(s).thermo.h(298.15)                       # J/kmol
        h_fuel = sum(x * h(s) for s, x in X.items() if x > 0)
        nO2 = n['C'] + n['H'] / 4 - n['O'] / 2                              # inert CO2 in the fuel cancels
        lhv_mol = h_fuel + nO2 * h('O2') - n['C'] * h('CO2') - n['H'] / 2 * h('H2O')
        gas.set_equivalence_ratio(1.0, fuel, AIR); mf = gas.mixture_fraction(fuel, AIR)
        v_std = 8314.46 * 288.15 / 101325.0                                 # m3/kmol at 15 C, 1 atm
        props[name] = dict(W=Wf, LHV_MJ_kg=lhv_mol / Wf / 1e6, LHV_MJ_Sm3=lhv_mol / v_std / 1e6, f_st=mf / (1 - mf),
                           Wobbe_MJ_Sm3=lhv_mol / v_std / 1e6 / math.sqrt(Wf / 28.96))
        print('%-8s W %.2f  LHV %.2f MJ/kg  %.2f MJ/Sm3  f_st %.4f  Wobbe %.1f' % (name, Wf, props[name]['LHV_MJ_kg'],
              props[name]['LHV_MJ_Sm3'], props[name]['f_st'], props[name]['Wobbe_MJ_Sm3']), flush=True)
    out['fuel'] = props
    # ---------------------------------------------------------------------------------------------- flames + PFR
    fl = []
    for key, (T_air, TIT) in C.LOAD_AIR.items():
        for phi in PHIS:
            try:
                d, end = flame(phi, T_air, comp('nominal'))
            except Exception as e:                                               # noqa: BLE001  (very lean, cold air)
                print('flame failed', key, phi, e); continue
            s, st = pfr(end, T_PZ_MS)
            d['pz'] = [dict(t_ms=t, NOx=a, CO=b, T=T) for t, (a, b, T) in zip(T_PZ_MS, s)]
            # dilution after 15 ms of primary zone (design value checked in a1000_combustor.py)
            _, st15 = pfr(end, [15.0])
            if TIT < st15[0] - 20:
                std, _ = dilute(st15, T_air + 10.0, TIT)
                s2, _ = pfr(std, T_DZ_MS)
                d['dz'] = [dict(t_ms=t, NOx=a, CO=b) for t, (a, b, _) in zip(T_DZ_MS, s2)]
            d['load'] = key; d['TIT'] = TIT
            fl.append(d)
            print('%-6s T_air %4.0f phi %.2f  Tu %4.0f  SL %.3f  Tad %4.0f  NOx %5.2f (15ms %5.2f)  CO15ms %7.1f  %3.0fs' % (
                key, T_air, phi, d['Tu'], d['SL'], d['Tad'], d['NOx_flame'], d['pz'][3]['NOx'], d['pz'][3]['CO'], time.time() - t0), flush=True)
    out['flames'] = fl
    rich = []
    for T_air in (C.LOAD_AIR['100'][0], C.LOAD_AIR['hot'][0]):
        for phi in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70):
            d, _ = flame(phi, T_air, comp('rich')); rich.append(d)
    out['flames_rich'] = rich
    print('rich-gas flames done %.0fs' % (time.time() - t0), flush=True)
    # ---------------------------------------------------------------------------------------------- ignition delay
    ign = []
    for name in ('nominal', 'rich'):
        for T_air in (886.0, 892.0, 910.0, 950.0):
            for phi in (0.1, 0.2, 0.3, 0.45, 0.7, 1.0, 1.5):
                ti, T0 = tau_ign(phi, T_air, comp(name))
                ign.append(dict(gas=name, T_air=T_air, phi=phi, T_mix=T0, tau_s=ti))
    out['ignition'] = ign
    print('ignition done %.0fs' % (time.time() - t0), flush=True)
    # ---------------------------------------------------------------------------------------------- PSR blow-out
    psr = []
    for key in ('100', '50'):
        T_air = C.LOAD_AIR[key][0]
        for phi in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60):
            psr.append(dict(load=key, T_air=T_air, phi=phi, tau_bo_ms=psr_blowout(phi, T_air, comp('nominal')) * 1e3))
            print('psr', key, phi, '%.3f ms' % psr[-1]['tau_bo_ms'], flush=True)
    out['psr'] = psr
    # ---------------------------------------------------------------------------------------------- pilot diffusion tip
    pil = []                                                    # stoichiometric burning for t, then quenched by dilution
    for key in ('100', '75', '50'):
        T_air = C.LOAD_AIR[key][0]; mf = mix(1.0, T_air, comp('nominal'))
        _, end = flame(1.0, T_air, comp('nominal'))
        for t in (0.5, 1.0, 2.0):
            _, st = pfr(end, [t]); Y = st[2]
            pil.append(dict(load=key, t_ms=t, EI_NOx_g_kg=(Y[iNO] / 30.006 + Y[iNO2] / 46.006) * 46.006 / mf * 1e3))
    out['pilot_diffusion'] = pil
    print('pilot EI', [round(p['EI_NOx_g_kg'], 2) for p in pil], flush=True)
    # ---------------------------------------------------------------------------------------------- staged part load
    out['staged'] = [staged(c) for c in C.staged_cases()]
    for s in out['staged']:
        print('staged %-5s n %d phi_f %.2f  NOx %.1f  CO(10 ms) %.1f' % (s['load'], s['n_fuelled'], s['phi_f'], s['exit'][2]['NOx'], s['exit'][2]['CO']), flush=True)
    json.dump(out, open(OUT, 'w'), indent=1)
    print('wrote %s  (%.0f s)' % (OUT, time.time() - t0))


if __name__ == '__main__':
    if '--staged' in sys.argv:                                  # only redo the staged part-load cases (new split / tau)
        out = json.load(open(OUT)); out['staged'] = [staged(c) for c in C.staged_cases()]
        json.dump(out, open(OUT, 'w'), indent=1); print('staged cases updated')
    else:
        main()
