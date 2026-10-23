# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - 250 kW(e) continuous single-shaft gas-turbine generator: cycle, design point, ambient table,
TIT 770 / 850 C matching with surge margin, efficiency budget.

Architecture (same as D2, scaled and built from industrial parts): front PMG pod in a large low-loss intake plenum,
quill (hex) drive into the compressor nose, single-stage centrifugal compressor (bought turbocharger-class Al wheel,
vaned diffuser + scroll), single vertical reverse-flow CAN combustor inside a COOL pressure casing (compressor air
wraps the hot parts), 360 deg hot plenum + 2.5D nozzle ring, single-stage radial/mixed-flow turbine (bought
turbocharger-class cast wheel), long low-loss conical exhaust diffuser + elbow, oil-jet hybrid ball bearings on SFDs.
Simple cycle (no recuperator); exhaust heat goes to the CHP / absorption chiller downstream (plant scope).

Design rules (user + coordinator, 2026-10-23):
  * 250 kW net electric CONTINUOUS at 30 C ambient, Borazjan 50 m, 40 % RH; aero sized at TIT 770 C (life priority),
    PR 4.0, air ~3 kg/s;  hardware (hot-section materials, matching, generator + converter 315 kW) good for TIT 850 C
    as a hot-weather / peak margin without hardware changes;
  * intake total-pressure loss <= 0.25 % (large filter interface), low-loss exhaust (back pressure costs ~2x inlet loss);
  * electrical frequency < 600 Hz (2-pole PMG at <= 35,880 rpm): standard industrial regenerative drives
    (<= 598 Hz output) qualify and the converter is not a > 600 Hz 'frequency changer' (dual-use list 3A225).
Real-gas properties (sim/variant_e/e_props.py): moist air, CH4-equivalent city gas, LHV 34.5 MJ/m3.
Off-design: generic turbocharger compressor map (speed lines in head/flow coefficients, 14 % head rise to surge) +
choked-nozzle turbine flow function (ellipse law) + U/C0 efficiency parabola.  ESTIMATE - replace with supplier maps.

Run:  python3 sim/variant_e/e_cycle.py  ->  sim/variant_e/e_cycle.json
"""
import json, math, os, sys, copy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import e_props as gp                                                   # noqa: E402

P_SITE = gp.site_pressure(50.0)
RH = 0.40
N_D = 35000.0                                                          # rpm, 2-pole PMG -> 583.3 Hz
N_MAX_DRIVE = 598.0 * 60                                               # 35,880 rpm: drive output-frequency limit
T_DES, TIT_DES, TIT_PEAK, PR_DES = 303.15, 1043.15, 1123.15, 4.0
P_NET_TARGET = 250.0e3
P_EL_CAP = 315.0e3                                                     # PMG + converter rating (grid-side gross electric)
MA_DES = 3.0                                                           # kg/s humid air at the design point

# ------------------------------------------------------------------ component budget (expected values; see meanlines)
B = dict(
    dp_inlet=0.0025,          # filter bank (mid-life) + plenum + bellmouth + pod/quill guard, fraction of P_amb at design flow
    dT_inlet=0.4,             # K, PMG pod skin + gap air heat into the intake
    eta_c=0.800,              # compressor total-total, inlet flange -> scroll exit (TC-class Al wheel, vaned diffuser)
    dp_casing=0.008,          # scroll exit -> cool pressure casing -> combustor annulus (fraction of P2)
    dp_liner=0.030,           # can liner (mixing / dilution jets)
    dp_transition=0.010,      # transition duct + 360 deg hot-plenum dump
    eta_b=0.995, q_loss=0.006,  # gas burner efficiency; casing heat loss (cool casing, insulated) fraction of fuel heat
    leak_lost=0.004,          # labyrinth leakage into the vented bearing chambers (lost)
    buffer=0.005, buffer_work=0.5,  # turbine back-face buffer/cooling air, rejoins at the rotor inlet, ~half the work
    eta_ts=0.810,             # turbine, nozzle-inlet total -> exducer static (exit KE counted as loss)
    A6=0.03597,               # exducer annulus area m2 (D6t 232 / D6h 75 minus TE blockage, e_turbine.py)
    cp_diff=0.62, AR_diff=3.4, K_elbow=0.20,
    dp_down=1200.0,           # Pa: CHP heat exchanger / absorption-chiller generator + stack (plant scope)
    mech_core=2.43e3,         # W: 3 core bearings (tandem pair + floating) at 35k, oil jet (e_rotor.py)
    pmg_fixed=dict(iron=1.60e3, rotor_eddy=1.10e3, windage=2.21e3, bearings=1.59e3),   # W at 35k (e_pmg.py, e_rotor.py)
    pmg_cu_rated=1.26e3, pmg_rated=335.0e3,                            # copper W at the rated shaft power (e_pmg.py)
    conv_fixed=0.006, conv_prop=0.024,                                 # converter loss = 0.6 % of rating + 2.4 % of load
    aux=dict(oil_pumps=0.70e3, glycol_pump=0.40e3, radiator_fans=1.10e3, enclosure_fan=1.00e3, ecu_ignition_valves=0.40e3),
    booster_on=True,          # gas booster running (supply at the 3.5 barg minimum) - conservative rating
)
GAS_SUPPLY_BARG = (3.5, 4.0, 5.0)


def booster_W(m_fuel, p_need_abs, p_sup_abs):
    """oil-free gas booster from supply to the required manifold pressure (isothermal / 0.45 overall)"""
    if p_need_abs <= p_sup_abs:
        return 0.0
    return m_fuel * 518.3 * 303.0 * math.log(p_need_abs / p_sup_abs) / 0.45


def run(ma, T_amb=T_DES, TIT=TIT_DES, PR=PR_DES, N=N_D, eta_c=None, eta_ts=None, b=None, P_amb=P_SITE, rh=RH):
    """one cycle evaluation for a given (humid) air mass flow ma [kg/s] and compressor PR (total-total)."""
    b = b or B
    eta_c = eta_c or b['eta_c']; eta_ts = eta_ts or b['eta_ts']
    air, w = gp.moist_air(T_amb, P_amb, rh)
    rho_amb = P_amb / (air.R * T_amb)
    # inlet: loss scales with the dynamic head of the volume flow (mid-life filter, ~quadratic incl. media)
    Q_D = 3.0 / (P_SITE / (air.R * T_DES))
    dp_in = b['dp_inlet'] * P_SITE * (ma / rho_amb / Q_D) ** 2 * (rho_amb / (P_SITE / (air.R * T_DES)))
    P1 = P_amb - dp_in; T1 = T_amb + b['dT_inlet']
    h1 = air.h(T1)
    T2s = air.T_isentropic(T1, PR)
    h2 = h1 + (air.h(T2s) - h1) / eta_c
    T2 = air.T_from_h(h2, T2s)
    P2 = P1 * PR
    W_c = ma * (h2 - h1)
    P3c = P2 * (1 - b['dp_casing'])                                     # combustor inlet
    P03 = P3c * (1 - b['dp_liner']) * (1 - b['dp_transition'])          # nozzle inlet total
    # combustion (air entering the liner = ma minus leakage and buffer air)
    m_comb = ma * (1 - b['leak_lost'] - b['buffer'])
    far = 0.015
    for _ in range(40):
        prod = gp.products(air, far)
        far_new = (prod.h(TIT) - air.h(T2)) / (b['eta_b'] * gp.LHV * (1 - b['q_loss']) - prod.h(TIT))
        if abs(far_new - far) < 1e-9:
            break
        far = far_new
    mf = m_comb * far
    mg = m_comb + mf
    prod = gp.products(air, far)
    # turbine: nozzle-inlet total -> exducer static p6; diffuser recovery lowers p6 below the exhaust flange pressure
    h03 = prod.h(TIT)
    p6 = P_amb + b['dp_down']
    for _ in range(40):
        T6s = prod.T_isentropic(TIT, p6 / P03)
        dh_is = h03 - prod.h(T6s)
        w_t = eta_ts * dh_is
        h6_0 = h03 - w_t                                                # exducer exit total enthalpy (adiabatic)
        T06 = prod.T_from_h(h6_0, T6s)
        # static exit state: c6 from continuity
        c6 = 150.0
        for _ in range(30):
            T6 = prod.T_from_h(h6_0 - c6 * c6 / 2, T06)
            rho6 = p6 / (prod.R * T6)
            c6n = (mg + ma * b['buffer']) / (rho6 * b['A6'])
            if abs(c6n - c6) < 0.01:
                break
            c6 = 0.5 * (c6 + c6n)
        q6 = 0.5 * rho6 * c6 * c6
        q_ex = q6 / b['AR_diff'] ** 2
        p6n = P_amb + b['dp_down'] + b['K_elbow'] * q_ex - b['cp_diff'] * q6
        if abs(p6n - p6) < 0.5:
            p6 = p6n
            break
        p6 = 0.5 * (p6 + p6n)
    # buffer air (compressor delivery) does ~half the rotor work on its own enthalpy
    w_buf = b['buffer_work'] * eta_ts * (h2 - air.h(air.T_isentropic(T2, p6 / P2))) * 0.6
    W_t = mg * w_t + ma * b['buffer'] * max(w_buf, 0.0)
    # exhaust mixed-out (main gas + buffer air), total temperature at the flange
    m_ex = mg + ma * b['buffer']
    ex = gp.Mix({k: (mg * prod.y.get(k, 0) + ma * b['buffer'] * air.y.get(k, 0)) for k in set(prod.y) | set(air.y)})
    h_ex = (mg * h6_0 + ma * b['buffer'] * (h2 - max(w_buf, 0.0))) / m_ex
    T_ex = ex.T_from_h(h_ex, T06)
    # shaft -> electric
    nr = N / N_D
    P_mech = b['mech_core'] * nr ** 1.7
    P_shaft = W_t - W_c - P_mech                                        # into the PMG through the quill
    fix = sum(b['pmg_fixed'].values()) * nr ** 1.8
    cu = b['pmg_cu_rated'] * (P_shaft / b['pmg_rated'] / max(nr, 0.3)) ** 2
    P_ac = P_shaft - fix - cu
    P_conv_loss = b['conv_fixed'] * P_EL_CAP + b['conv_prop'] * P_ac
    P_el = P_ac - P_conv_loss                                           # grid side, gross of auxiliaries
    Q_fuel = mf * gp.LHV
    # gas pressure: manifold = combustor inlet + injector 0.30 bar; train (filter, 2 SSV, regulator, metering) 0.45 bar
    p_need = P3c + 0.30e5 + 0.45e5
    boost = booster_W(mf, p_need, P_amb + GAS_SUPPLY_BARG[0] * 1e5) if b['booster_on'] else 0.0
    P_aux = sum(b['aux'].values()) + boost
    P_net = P_el - P_aux
    rho1 = P1 / (air.R * T1)
    return dict(ma=ma, w_humidity=w, T_amb_C=T_amb - 273.15, P_amb=P_amb, dp_inlet_Pa=dp_in, dp_inlet_pct=100 * dp_in / P_amb,
                T1=T1, P1=P1, PR=PR, eta_c=eta_c, T2=T2, P2=P2, W_c=W_c, P3c=P3c, P03=P03, TIT=TIT, far=far, mf=mf, mg=mg,
                eta_ts=eta_ts, dh_is_t=dh_is, w_t=w_t, T06=T06, T6=T6, p6=p6, c6=c6, q6=q6, PRt_ts=P03 / p6, W_t=W_t,
                m_exhaust=m_ex, T_exhaust=T_ex, P_mech=P_mech, P_shaft=P_shaft, P_pmg_loss=fix + cu, P_ac=P_ac,
                P_conv_loss=P_conv_loss, P_el_gross=P_el, P_aux=P_aux, P_booster=boost, P_net=P_net, Q_fuel=Q_fuel,
                eta_el=P_net / Q_fuel, eta_shaft=(W_t - W_c) / Q_fuel, gas_m3_h=Q_fuel / gp.LHV_VOL * 3600,
                p_gas_need_barg=(p_need - P_amb) / 1e5, Q1_m3_s=ma / rho1, air=air, prod=prod,
                FF=mg * math.sqrt(TIT) / P03, mc=ma * math.sqrt(T1 / T_DES) / (P1 / P_SITE),
                u_t=N / math.sqrt(dh_is), N=N)


def cons_budget():
    """conservative component set (everything worse at once) - used to SIZE the air flow so 250 kW is guaranteed"""
    bb = copy.deepcopy(B)
    bb.update(dict(eta_c=0.78, eta_ts=0.79, dp_inlet=0.004, dp_liner=0.035, cp_diff=0.50, dp_down=1800.0, mech_core=3.5e3,
                   conv_prop=0.030, q_loss=0.01))
    bb['pmg_fixed'] = {k: v * 1.3 for k, v in B['pmg_fixed'].items()}
    bb['aux'] = {k: v * 1.3 for k, v in B['aux'].items()}
    return bb


def design():
    """design air flow 3.0 kg/s (coordinator input 2026-10-23): with the EXPECTED components the machine gives ~285 kW
    at 30 C / 770 C (250 kW at ~735 C); with the CONSERVATIVE set (cons_budget) 250 kW needs ~800 C - inside the
    850 C hardware rating.  The geometry (turbine throat, compressor) is laid out for the expected efficiencies."""
    return run(MA_DES)


def solve(f, a, b, tol=1e-6, it=40):
    """Illinois false position on f(x) = 0 in [a, b] -> (x, payload of the last call)"""
    fa, pa = f(a); fb, pb = f(b)
    if fa * fb > 0:
        return (a, pa) if abs(fa) < abs(fb) else (b, pb)
    side = 0
    for _ in range(it):
        c = (a * fb - b * fa) / (fb - fa)
        fc, pc = f(c)
        if abs(fc) < tol or abs(b - a) < tol * max(1.0, abs(c)):
            return c, pc
        if fc * fb > 0:
            b, fb = c, fc
            if side == -1:
                fa *= 0.5
            side = -1
        else:
            a, fa = c, fc
            if side == 1:
                fb *= 0.5
            side = 1
    return c, pc


D = design()
A_ = D['air']
DH_IS_C_D = A_.h(A_.T_isentropic(D['T1'], PR_DES)) - A_.h(D['T1'])

# ------------------------------------------------------------------ generic map
MAP = dict(x_s=0.80, psi_s=1.14, x_ch=1.07, a_flow=1.40, eta_flow=1.2, eta_speed=0.5)


def map_point(x, n, T1):
    """speed line n (corrected, 1 = design), relative flow x (1 = design flow at that speed's reference) ->
    corrected flow, isentropic head, efficiency"""
    m = MAP
    xs = m['x_s']
    xch = m['x_ch'] + 0.15 * max(0.0, 1 - n) - 0.10 * max(0.0, n - 1)
    psi = m['psi_s'] - (m['psi_s'] - 1.0) * ((x - xs) / (1 - xs)) ** 2
    if x > xch:
        psi_ch = m['psi_s'] - (m['psi_s'] - 1.0) * ((xch - xs) / (1 - xs)) ** 2
        psi = max(psi_ch - 6.0 * (x - xch), 0.2)                       # choke wall
    dh_is = psi * n * n * DH_IS_C_D * T1 / D['T1']
    eta = B['eta_c'] * (1 - m['eta_flow'] * (x - 1) ** 2) * (1 - m['eta_speed'] * (n - 1) ** 2)
    mc = x * D['mc'] * n ** m['a_flow']
    return mc, dh_is, eta, xch


def surge_margin(n, T1, x_op, PR_op):
    """SM at constant corrected speed: (PR_surge - PR_op) / PR_op, and the flow-ratio form (PR/m)_s/(PR/m)_op - 1"""
    mc_s, dh_s, _, _ = map_point(MAP['x_s'], n, T1)
    PR_s = math.exp((A_.s0(A_.T_from_h(A_.h(T1) + dh_s, T1)) - A_.s0(T1)) / A_.R)
    mc_op = map_point(x_op, n, T1)[0]
    return 100 * (PR_s - PR_op) / PR_op, 100 * ((PR_s / mc_s) / (PR_op / mc_op) - 1), PR_s


def offdesign(T_amb, TIT, N=N_D, b=None, P_amb=P_SITE):
    """match compressor (map) and turbine (FF ellipse law + U/C0 efficiency) at physical speed N"""
    b = b or B
    T1 = T_amb + b['dT_inlet']
    n = (N / N_D) / math.sqrt(T1 / D['T1'])
    air, _ = gp.moist_air(T_amb, P_amb, RH)

    def resid(x):
        mc, dh_is, eta, _ = map_point(x, n, T1)
        T2s = air.T_from_h(air.h(T1) + dh_is, T1)
        PR = math.exp((air.s0(T2s) - air.s0(T1)) / air.R)
        # corrected flow -> physical (P1 depends on the inlet loss which depends on the flow: iterate twice)
        ma = mc * math.sqrt(D['T1'] / T1) * (P_amb - D['dp_inlet_Pa']) / P_SITE
        for _ in range(2):
            r0 = run(ma, T_amb, TIT, PR, N, eta_c=eta, eta_ts=b['eta_ts'], b=b, P_amb=P_amb)
            ma = mc * math.sqrt(D['T1'] / T1) * r0['P1'] / P_SITE
        u = r0['u_t'] / D['u_t']
        eta_t = b['eta_ts'] * (1 - 1.8 * (u - 1) ** 2)
        r = run(ma, T_amb, TIT, PR, N, eta_c=eta, eta_ts=eta_t, b=b, P_amb=P_amb)
        ell = lambda prt: math.sqrt(max(1 - 1 / prt ** 2, 1e-9))
        FF_turb = D['FF'] * ell(r['PRt_ts']) / ell(D['PRt_ts'])
        r['x'] = x; r['n_corr'] = n
        return r['FF'] / FF_turb - 1, r

    x, r = solve(lambda x: resid(x), MAP['x_s'] - 0.06, MAP['x_ch'] + 0.15, tol=2e-5)
    sm_n, sm_m, PR_s = surge_margin(n, T1, r['x'], r['PR'])
    r['SM_const_speed_pct'] = sm_n; r['SM_flow_ratio_pct'] = sm_m; r['PR_surge'] = PR_s
    return r


def capped(T_amb, TIT, cap=P_EL_CAP, b=None):
    """100 % speed; if the grid-side gross power exceeds the PMG/converter rating, lower the TIT (not the speed:
    a lower corrected speed at a high T3/T1 would move the compressor towards surge)"""
    r = offdesign(T_amb, TIT, N_D, b)
    r['speed_pct'] = 100.0
    if r['P_el_gross'] <= cap:
        return r
    T3, _ = solve(lambda T3: (offdesign(T_amb, T3, N_D, b)['P_el_gross'] / cap - 1, None), 850.0, TIT, tol=2e-4, it=25)
    r = offdesign(T_amb, T3, N_D, b)
    r['speed_pct'] = 100.0
    return r


def row(r, label=''):
    return dict(case=label, T_amb_C=round(r['T_amb_C'], 1), TIT_C=round(r['TIT'] - 273.15, 0), speed_rpm=round(r['N']),
                speed_pct=round(r.get('speed_pct', 100 * r['N'] / N_D), 1), air_kg_s=round(r['ma'], 3), PR=round(r['PR'], 3),
                eta_c=round(r['eta_c'], 4), eta_ts=round(r['eta_ts'], 4), P_shaft_kW=round(r['P_shaft'] / 1e3, 1),
                P_el_gross_kW=round(r['P_el_gross'] / 1e3, 1), P_aux_kW=round(r['P_aux'] / 1e3, 2), P_net_kW=round(r['P_net'] / 1e3, 1),
                fuel_kW=round(r['Q_fuel'] / 1e3, 1), gas_m3_h=round(r['gas_m3_h'], 1), eta_el_pct=round(100 * r['eta_el'], 2),
                T_exhaust_C=round(r['T_exhaust'] - 273.15, 1), m_exhaust_kg_s=round(r['m_exhaust'], 3),
                heat_to_90C_kW=round(r['m_exhaust'] * 1.10 * (r['T_exhaust'] - 363.15), 0),
                SM_pct=round(r.get('SM_const_speed_pct', float('nan')), 1), SM_flow_ratio_pct=round(r.get('SM_flow_ratio_pct', float('nan')), 1),
                gas_need_barg=round(r['p_gas_need_barg'], 2), booster_kW=round(r['P_booster'] / 1e3, 2))


def budget():
    """efficiency waterfall: switch each loss off alone and report the gain in eta_el at the design flow / PR"""
    base = run(D['ma'])
    out = []
    ideal = copy.deepcopy(B)
    toggles = [('compressor eta_c 0.80 -> 1', dict(eta_c=1.0)), ('turbine eta_ts 0.81 -> 1', dict(eta_ts=1.0)),
               ('intake loss 0.25 % -> 0', dict(dp_inlet=0.0)), ('combustor path dp 4.8 % -> 0', dict(dp_casing=0.0, dp_liner=0.0, dp_transition=0.0)),
               ('exhaust back pressure (CHP 1.2 kPa) -> 0', dict(dp_down=0.0)), ('diffuser REMOVED (Cp 0.62 -> 0): shows its value', dict(cp_diff=0.0)),
               ('burner eta 0.995 + heat loss 0.6 % -> ideal', dict(eta_b=1.0, q_loss=0.0)), ('seal leakage + buffer air -> 0', dict(leak_lost=0.0, buffer=0.0)),
               ('core bearings -> 0', dict(mech_core=0.0)), ('PMG losses -> 0', dict(pmg_fixed=dict(a=0.0), pmg_cu_rated=0.0)),
               ('converter losses -> 0', dict(conv_fixed=0.0, conv_prop=0.0)), ('auxiliaries -> 0', dict(aux=dict(a=0.0), booster_on=False)),
               ('gas booster off (supply >= 4.0 barg)', dict(booster_on=False))]
    for lab, mod in toggles:
        bb = copy.deepcopy(B); bb.update(mod)
        kw = {}
        if 'eta_c' in mod:
            kw['eta_c'] = mod['eta_c']
        if 'eta_ts' in mod:
            kw['eta_ts'] = mod['eta_ts']
        r = run(D['ma'], b=bb, **kw)
        out.append(dict(loss=lab, eta_el_if_removed_pct=round(100 * r['eta_el'], 2), gain_points=round(100 * (r['eta_el'] - base['eta_el']), 2),
                        P_net_if_removed_kW=round(r['P_net'] / 1e3, 1)))
    # ideal machine at the same PR / TIT (Brayton with real gas, no losses at all)
    bb = copy.deepcopy(ideal)
    bb.update(dict(dp_inlet=0.0, dp_casing=0.0, dp_liner=0.0, dp_transition=0.0, dp_down=0.0, cp_diff=0.0, eta_b=1.0, q_loss=0.0, leak_lost=0.0,
                   buffer=0.0, mech_core=0.0, pmg_fixed=dict(a=0.0), pmg_cu_rated=0.0, conv_fixed=0.0, conv_prop=0.0, aux=dict(a=0.0), booster_on=False))
    ri = run(D['ma'], eta_c=1.0, eta_ts=1.0, b=bb)
    return dict(base_eta_el_pct=round(100 * base['eta_el'], 2), ideal_brayton_same_PR_TIT_pct=round(100 * ri['eta_el'], 2), toggles=out)


def conservative(T_amb=T_DES, TIT=TIT_DES):
    """margin check: everything 'worse' at once, at the design air flow"""
    return run(D['ma'], T_amb=T_amb, TIT=TIT, eta_c=0.78, eta_ts=0.79, b=cons_budget())


def tit_for_power(T_amb, P=P_NET_TARGET, N=N_D):
    """turbine inlet temperature needed for a given net power at 100 % speed (constant-power operation)"""
    T3, _ = solve(lambda T3: (offdesign(T_amb, T3, N)['P_net'] / P - 1, None), 900.0, 1173.15, tol=2e-4, it=25)
    r = offdesign(T_amb, T3, N); r['speed_pct'] = 100 * N / N_D
    return r


def main():
    d = D
    print('VERSION E design point, EXPECTED components (30 C, 50 m, 40 %% RH, TIT %.0f C, PR %.2f, %d rpm); air flow sized so the '
          'CONSERVATIVE set gives 250 kW' % (TIT_DES - 273.15, PR_DES, N_D))
    print('  air %.3f kg/s (%.2f m3/s at the compressor face)  fuel %.4f kg/s = %.1f m3/h  FAR %.4f' % (
        d['ma'], d['Q1_m3_s'], d['mf'], d['gas_m3_h'], d['far']))
    print('  inlet loss %.0f Pa (%.2f %%)  P1 %.3f bar  T2 %.1f C  P2 %.3f bar  W_c %.1f kW' % (
        d['dp_inlet_Pa'], d['dp_inlet_pct'], d['P1'] / 1e5, d['T2'] - 273.15, d['P2'] / 1e5, d['W_c'] / 1e3))
    print('  combustor in %.3f bar, nozzle-inlet total %.3f bar, PR_t,ts %.3f, dh_is %.1f kJ/kg, w_t %.1f kJ/kg, W_t %.1f kW' % (
        d['P3c'] / 1e5, d['P03'] / 1e5, d['PRt_ts'], d['dh_is_t'] / 1e3, d['w_t'] / 1e3, d['W_t'] / 1e3))
    print('  exducer: c6 %.0f m/s, p6 %.3f bar (diffuser Cp %.2f), T06 %.1f C; exhaust %.3f kg/s at %.1f C' % (
        d['c6'], d['p6'] / 1e5, B['cp_diff'], d['T06'] - 273.15, d['m_exhaust'], d['T_exhaust'] - 273.15))
    print('  shaft into PMG %.1f kW, PMG loss %.2f, conv loss %.2f, el gross %.1f, aux %.2f (booster %.2f), NET %.1f kW, eta_el %.2f %%' % (
        d['P_shaft'] / 1e3, d['P_pmg_loss'] / 1e3, d['P_conv_loss'] / 1e3, d['P_el_gross'] / 1e3, d['P_aux'] / 1e3, d['P_booster'] / 1e3,
        d['P_net'] / 1e3, 100 * d['eta_el']))
    print('  gas need at the skid %.2f barg (manifold + 0.45 bar train)' % d['p_gas_need_barg'])
    # sizes (first estimate, refined by the meanlines)
    om = N_D * 2 * math.pi / 60
    lam = 0.715                                                          # work input factor dh0/U2^2, backswept + splitters (e_compressor.py)
    U2 = math.sqrt(d['W_c'] / d['ma'] / lam)
    D2 = 2 * U2 / om
    Ns_c = om * math.sqrt(d['Q1_m3_s']) / DH_IS_C_D ** 0.75
    C0 = math.sqrt(2 * d['dh_is_t'])
    U4 = 0.63 * C0
    D4 = 2 * U4 / om
    sizes = dict(N_rpm=N_D, f_el_Hz_2pole=N_D / 60, compressor=dict(U2_m_s=round(U2, 1), D2_mm=round(D2 * 1e3, 1), Ns=round(Ns_c, 3),
                                                                     phi=round(d['Q1_m3_s'] / ((D2 ** 2) * U2), 4), work_factor=lam),
                 turbine=dict(C0_m_s=round(C0, 1), U4_at_UC0_063=round(U4, 1), D4_mm=round(D4 * 1e3, 1)))
    print('  sizes: compressor U2 %.0f m/s D2 %.0f mm Ns %.2f | turbine C0 %.0f m/s, U4 %.0f (U/C0 0.63) D4 %.0f mm' % (
        U2, D2 * 1e3, Ns_c, C0, U4, D4 * 1e3))

    # ambient table: TIT 770 (rated), uncapped at 100 % speed and capped at the 315 kW electric rating; TIT 850 peak
    tab770, tab770cap, tab850, tab250, tabcons = [], [], [], [], []
    for tc in (0, 15, 30, 40, 45):
        T = tc + 273.15
        r = offdesign(T, TIT_DES); r['speed_pct'] = 100.0
        tab770.append(row(r, 'TIT 770, 100 % speed'))
        tab770cap.append(row(capped(T, TIT_DES), 'TIT <= 770, el <= 315 kW'))
        tab850.append(row(capped(T, TIT_PEAK), 'TIT <= 850 (peak), el <= 315 kW'))
        rr = tit_for_power(T)
        tab250.append(row(rr, '250 kW net, TIT as needed'))
        rc = conservative(T, TIT_DES)
        tabcons.append(dict(T_amb_C=tc, P_net_kW_at_design_flow=round(rc['P_net'] / 1e3, 1), eta_el_pct=round(100 * rc['eta_el'], 2)))
    print('\nAmbient table (net after all auxiliaries incl. gas booster; 50 m, 40 % RH):')
    hdr = '  %-34s %5s %5s %6s %6s %6s %6s %7s %7s %6s %7s %6s %5s'
    print(hdr % ('case', 'T_amb', 'TIT', 'speed', 'air', 'PR', 'net', 'gas', 'eta_el', 'T_exh', 'm_exh', 'SM', 'heat'))
    for t in (tab770, tab770cap, tab850, tab250):
        for r in t:
            print('  %-34s %5.0f %5.0f %5.1f%% %6.3f %6.3f %6.1f %7.1f %6.2f%% %6.0f %7.3f %5.1f%% %5.0f' % (
                r['case'], r['T_amb_C'], r['TIT_C'], r['speed_pct'], r['air_kg_s'], r['PR'], r['P_net_kW'], r['gas_m3_h'], r['eta_el_pct'],
                r['T_exhaust_C'], r['m_exhaust_kg_s'], r['SM_pct'], r['heat_to_90C_kW']))
    # matching check at 30 C: 770 vs 850 C at the same speed
    m770 = offdesign(T_DES, TIT_DES); m850 = offdesign(T_DES, TIT_PEAK)
    match = dict(TIT_770=row(m770, '30 C, 100 %, TIT 770'), TIT_850=row(m850, '30 C, 100 %, TIT 850 (no cap)'),
                 note='same hardware (fixed nozzle throat): raising TIT at constant speed moves the compressor up its speed line '
                      '(flow down, PR up); the surge margin drops from %.1f to %.1f %% (constant-speed definition)' % (
                          m770['SM_const_speed_pct'], m850['SM_const_speed_pct']))
    print('\nMatching at 30 C, 35,000 rpm: TIT 770 -> x %.3f PR %.3f air %.3f SM %.1f %% | TIT 850 -> x %.3f PR %.3f air %.3f SM %.1f %%, net %.1f kW (uncapped)' % (
        m770['x'], m770['PR'], m770['ma'], m770['SM_const_speed_pct'], m850['x'], m850['PR'], m850['ma'], m850['SM_const_speed_pct'], m850['P_net'] / 1e3))
    bud = budget()
    print('\nEfficiency budget (design point %.2f %%; ideal real-gas Brayton at PR 4 / 770 C: %.2f %%):' % (bud['base_eta_el_pct'], bud['ideal_brayton_same_PR_TIT_pct']))
    for t in bud['toggles']:
        print('  %-46s %+.2f points  (-> %.2f %%)' % (t['loss'], t['gain_points'], t['eta_el_if_removed_pct']))
    cons = conservative()
    cons850 = conservative(T_DES, TIT_PEAK)
    t_c, _ = solve(lambda T3: (conservative(T_DES, T3)['P_net'] / P_NET_TARGET - 1, None), 1000.0, 1173.15, tol=1e-4)
    print('Conservative set at 30 C: 770 C -> %.1f kW, 850 C -> %.1f kW (%.2f %%); 250 kW needs TIT %.0f C (fixed design flow; hardware rated 850 C)' % (
        cons['P_net'] / 1e3, cons850['P_net'] / 1e3, 100 * cons850['eta_el'], t_c - 273.15))
    print('\nConservative case (eta_c 0.78, eta_ts 0.79, inlet 0.4 %%, liner 3.5 %%, diffuser Cp 0.50, CHP 1.8 kPa, +30 %% mech/PMG/aux, converter 97 %%):'
          ' net %.1f kW, eta_el %.2f %% (target 10.8 %%: margin %.2f points)' % (cons['P_net'] / 1e3, 100 * cons['eta_el'], 100 * cons['eta_el'] - 10.8))
    # gas pressure need vs supply
    gas = []
    for pb in GAS_SUPPLY_BARG:
        bb = copy.deepcopy(B)
        r = run(d['ma'], b=bb)
        need = r['p_gas_need_barg']
        bw = booster_W(r['mf'], (need * 1e5 + P_SITE), P_SITE + pb * 1e5)
        gas.append(dict(supply_barg=pb, need_barg=round(need, 2), booster_kW=round(bw / 1e3, 2),
                        net_kW_booster_as_needed=round((r['P_net'] + r['P_booster'] - bw) / 1e3, 1)))
    print('gas supply:', gas)
    # comparison with the user's quick scan (concept_study.cycle)
    try:
        import concept_study as cs
        cs_r = cs.cycle(dict(ma=1.0, PR=4.0, TIT=1123.15, eta_c=0.78, eta_t=0.84, arch='single', eps=0.0, T_amb=303.15, P_amb=P_SITE, booster=False))
        cs_770 = cs.cycle(dict(ma=1.0, PR=4.0, TIT=1043.15, eta_c=0.80, eta_t=0.81, arch='single', eps=0.0, T_amb=303.15, P_amb=P_SITE, booster=False))
        comp = dict(user_scan_850C_078_084=dict(eta_shaft_pct=round(100 * cs_r['P_shaft'] / cs_r['Q_fuel'], 2), eta_el_pct=round(100 * cs_r['eta_el'], 2),
                                                note='concept_study: cp_g 1148, eta_b 0.97 + 2 % heat loss, gen 0.95 x conv 0.96, 0.45 kW aux per kg/s'),
                    concept_study_770C_080_081=dict(eta_shaft_pct=round(100 * cs_770['P_shaft'] / cs_770['Q_fuel'], 2), eta_el_pct=round(100 * cs_770['eta_el'], 2)))
    except Exception as e:                                               # pragma: no cover
        comp = dict(error=str(e))
    print('concept_study comparison:', comp)

    st = lambda T: round(T - 273.15, 1)
    res = dict(
        title='GR180 version E - 250 kW(e) single-shaft gas-turbine generator: cycle, ambient table, matching, efficiency budget',
        date='2026-10-23', script='sim/variant_e/e_cycle.py',
        basis=dict(site='Borazjan, 50 m (P %.0f Pa), 40 %% RH' % P_SITE, rating='250 kW net continuous at 30 C, TIT 770 C (aero design point)',
                   peak='TIT 850 C with the same hardware (hot-weather / peak margin), PMG + converter 315 kW electric',
                   gas='city gas LHV 34.5 MJ/m3 (CH4-equivalent products, %.2f MJ/kg)' % (gp.LHV / 1e6),
                   speed='35,000 rpm = 583 Hz (2-pole PMG): < 598 Hz drive limit / < 600 Hz dual-use threshold',
                   properties='real-gas ideal mixtures (e_props.py)', map='generic TC compressor map (14 % head rise to surge), choked-nozzle turbine (ellipse law) - ESTIMATE'),
        budget_inputs={k: v for k, v in B.items()},
        design_point=dict(air_kg_s=round(d['ma'], 4), Q1_m3_s=round(d['Q1_m3_s'], 3), humidity_kg_kg=round(d['w_humidity'], 4),
                          stations=dict(ambient=dict(T_C=st(T_DES), P_bar=round(P_SITE / 1e5, 4)),
                                        compressor_in=dict(T_C=st(d['T1']), P_bar=round(d['P1'] / 1e5, 4), dp_Pa=round(d['dp_inlet_Pa'])),
                                        compressor_out=dict(T_C=st(d['T2']), P_bar=round(d['P2'] / 1e5, 4)),
                                        combustor_in=dict(T_C=st(d['T2']), P_bar=round(d['P3c'] / 1e5, 4)),
                                        nozzle_in=dict(T_C=st(d['TIT']), P_bar=round(d['P03'] / 1e5, 4)),
                                        exducer=dict(T_static_C=st(d['T6']), T_total_C=st(d['T06']), p_static_bar=round(d['p6'] / 1e5, 4), c_m_s=round(d['c6'], 1)),
                                        exhaust_flange=dict(T_C=st(d['T_exhaust']), m_kg_s=round(d['m_exhaust'], 4))),
                          PR=PR_DES, eta_c=B['eta_c'], eta_ts=B['eta_ts'], W_compressor_kW=round(d['W_c'] / 1e3, 1), W_turbine_kW=round(d['W_t'] / 1e3, 1),
                          P_mech_core_kW=round(d['P_mech'] / 1e3, 2), P_shaft_to_PMG_kW=round(d['P_shaft'] / 1e3, 1), PMG_loss_kW=round(d['P_pmg_loss'] / 1e3, 2),
                          converter_loss_kW=round(d['P_conv_loss'] / 1e3, 2), P_el_gross_kW=round(d['P_el_gross'] / 1e3, 1), P_aux_kW=round(d['P_aux'] / 1e3, 2),
                          P_booster_kW=round(d['P_booster'] / 1e3, 2), P_net_kW=round(d['P_net'] / 1e3, 1), fuel_kg_s=round(d['mf'], 5),
                          fuel_kW=round(d['Q_fuel'] / 1e3, 1), gas_m3_h=round(d['gas_m3_h'], 1), far=round(d['far'], 5), eta_el_pct=round(100 * d['eta_el'], 2),
                          eta_shaft_pct=round(100 * d['eta_shaft'], 2), heat_to_90C_kW=round(d['m_exhaust'] * 1.10 * (d['T_exhaust'] - 363.15)),
                          gas_need_at_skid_barg=round(d['p_gas_need_barg'], 2), turbine_flow_function=d['FF'], corrected_air_kg_s=d['mc'],
                          torque_turbine_Nm=round(d['W_t'] / (N_D * math.pi / 30), 1), torque_PMG_Nm=round(d['P_shaft'] / (N_D * math.pi / 30), 1)),
        sizes_first_estimate=sizes,
        rating=dict(P_net_rated_kW=250.0, sized_with='conservative component set (cons_budget) gives 250 kW at 30 C / 770 C',
                    expected_at_770C_30C_kW=round(D['P_net'] / 1e3, 1), TIT_for_250kW_expected=tab250,
                    conservative_ambient_TIT770_fixed_flow=tabcons),
        ambient_table_TIT770_100pct=tab770, ambient_table_TIT770_capped=tab770cap, ambient_table_TIT850_peak_capped=tab850,
        matching_770_vs_850=match, efficiency_budget=bud,
        conservative_case=dict(P_net_kW=round(cons['P_net'] / 1e3, 1), eta_el_pct=round(100 * cons['eta_el'], 2),
                               margin_to_10_8_points=round(100 * cons['eta_el'] - 10.8, 2),
                               P_net_kW_TIT850=round(cons850['P_net'] / 1e3, 1), eta_el_pct_TIT850=round(100 * cons850['eta_el'], 2),
                               TIT_for_250kW_C=round(t_c - 273.15, 1),
                               inputs='eta_c 0.78, eta_ts 0.79, inlet 0.4 %, liner 3.5 %, diffuser Cp 0.50, CHP 1.8 kPa, +30 % bearings/PMG fixed/aux, converter 3.6 %'),
        gas_supply=gas, concept_study_comparison=comp,
        components=dict(
            compressor='bought TC-class Al 2618 (forged, 5-axis milled) backswept splitter impeller D2 ~276 mm (TPS52/57-F, TCR16/18, MET18-22 class - ESTIMATE, '
                       'verify with supplier drawing), our 17-vane 2.5D diffuser + axisymmetric bend / 23 deswirl vanes straight into the cool casing (no scroll, '
                       'no pipe); the TC maker\'s scroll casing + DN250 pipe is the fallback',
            combustor='single vertical reverse-flow can (Kawasaki M1A-style) on the cool casing, DN300 casing, liner d210 x 588 Nimonic 75, axial swirler + '
                      'central gas lance (partially premixed diffusion flame), conical transition d210 -> d270 into the floating hot plenum',
            turbine='bought TC-class cast IN713LC radial/mixed-flow wheel D4 ~285-290 mm friction-welded to our shaft by the supplier; '
                    '2.5D nozzle ring (alloy X / 2.4665) in a floating hot plenum inside the cool pressure casing',
            generator='2-pole SmCo PMG 335 kW shaft continuous at 35k rpm (583 Hz): own design, active parts from a high-speed machine shop '
                      '(e+a CH, or similar) or a bought HS machine (Safran GENeUS 300 FR - inquire 24/7 rating); diode bridge + 400 V AFE supply unit, '
                      'start inverter <= 500 Hz (e_pmg.py)',
            bearings='4 + 1 hybrid ceramic angular-contact spindle bearings 40x68x15 (7008 class) on O-ring SFDs, closed oil-jet, VG 32',
            coupling='D2 idea scaled: bolted d30 quill with an AF24 socket sliding on the crowned AF24 hex of the core-shaft nose (+/-1 mm float, no adjustment)'),
    )
    json.dump(res, open(os.path.join(HERE, 'e_cycle.json'), 'w'), indent=1, default=lambda o: None)
    print('-> sim/variant_e/e_cycle.json')


if __name__ == '__main__':
    main()
