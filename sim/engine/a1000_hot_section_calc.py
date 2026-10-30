#!/usr/bin/env python3
"""AURORA-1000 hot section rev 1 (geometry cad/engine/a1000_hot_section.py):
  1. shroud carriers: steady metal temperature from the hot-gas side (honeycomb + backing) and the compressor-delivery air
     on the outside (annular channel between carrier and outer casing; the gap sets the cooling) -> running tip clearance;
     the channel gap of each carrier is sized for the clearance target of sim/engine/a1000_turbine_checks.py
  2. tip-clearance transients (first-order lags: blades, disc, carrier): cold start to full load, and a hot restart after
     a shutdown -> pinch (rub into the abradable honeycomb) and the restart inhibit time
  3. outer casing (EN-GJS-400-18LT at compressor delivery): pressure stress, split-flange bolts, centring pins, NGV gas loads
  4. secondary air: labyrinth leakage (Martin, with carry-over) of the drum balance seal, the back-face seal and the
     interstage seal -> purge fractions
Run:    python sim/engine/a1000_hot_section_calc.py           (numpy, matplotlib)
Writes: sim/engine/fea/a1000_hot_section.json, docs/img/a1000_hot_section.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine')); sys.path.insert(0, HERE)
import a1000_hot_section as H                                 # noqa: E402
G, A = H.G, H.A
ML = G.RD.ML
TIPS = json.load(open(os.path.join(HERE, 'fea', 'a1000_turbine_checks.json')))['tips']
DISC = json.load(open(os.path.join(HERE, 'fea', 'a1000_disc.json')))
STACK = json.load(open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')))

ALPHA_C = 17.8e-6                                               # 1.4828 mean 20..500 C (as the tip-clearance budget)
P_CD, T_CD = ML['compressor'][1]['P02'], ML['compressor'][1]['T02']            # compressor delivery [Pa, K]
M_AIR = ML['ma']
S1, S2 = ML['turbine']['stages']
# gas temperature seen by the shroud (rotor-relative total at the tip, slightly below the hub value) and the gas-side
# heat transfer: tip-gap flow h ~ 1500 W/m2K through 4 mm honeycomb (k_eff ~ 2 W/mK incl. radiation) + 3 mm backing
T_GAS = dict(R1=S1['T_rel_rotor_in'] - 273.15 - 25.0, R2=S2['T_rel_rotor_in'] - 273.15 - 25.0)
H_GAS, K_HC, K_BACK = 1500.0, 2.0, 22.0


def air_props(T_K, p):
    rho = p / (287.0 * T_K); mu = 1.716e-5 * (T_K / 273.15) ** 1.5 * (383.55 / (T_K + 110.4)); k = 0.0241 * (T_K / 273.15) ** 0.81
    return rho, mu, k


def h_channel(gap_mm, r_mm, m_dot):
    """Dittus-Boelter in the annular channel outside a carrier: all the compressor delivery flow passes it"""
    rho, mu, k = air_props(T_CD, P_CD); g = gap_mm * 1e-3; Dh = 2 * g; Ac = 2 * math.pi * r_mm * 1e-3 * g
    v = m_dot / (rho * Ac); Re = rho * v * Dh / mu
    Nu = 0.023 * Re ** 0.8 * 0.7 ** 0.4
    dp = 0.316 * Re ** -0.25 * 0.25 / Dh * 0.5 * rho * v * v
    return Nu * k / Dh, v, Re, dp


def carrier_T(row, gap_mm, r_mm):
    hg = 1.0 / (1.0 / H_GAS + H.HC['t'] * 1e-3 / K_HC + H.HC['back'] * 1e-3 / K_BACK)
    hc, v, Re, dp = h_channel(gap_mm, r_mm, M_AIR)
    Tc = (hg * T_GAS[row] + hc * (T_CD - 273.15)) / (hg + hc)
    return Tc, hg, hc, v, dp


def size_gap(row, r_mm):
    """channel gap [mm] that puts the carrier at the temperature the tip-clearance budget needs"""
    T_need = TIPS[row]['carrier_T_needed_C']
    gs = np.linspace(5.0, 120.0, 400); Ts = [carrier_T(row, g, r_mm)[0] for g in gs]
    return float(np.interp(T_need, Ts, gs)), T_need


def transient(row, tau, t_off=None, dt=1.0, t_end=3600.0):
    """clearance [mm] vs time after a start at full load (speed and gas temperature stepped at t = 0, worst case).
    t_off = None: cold start; else a hot restart t_off seconds after a shutdown from steady running (standstill cooling
    with tau['*_off'])."""
    tp = TIPS[row]; r = tp['casing_r']
    mech = DISC['%s_op_mech' % row]['u_rim_mm'] + tp['blade_stretch']
    disc_th = tp['disc_rim_growth'] - DISC['%s_op_mech' % row]['u_rim_mm']; blade_th = tp['blade_thermal']
    carr = ALPHA_C * r * (TIPS[row]['carrier_T_needed_C'] - 20.0)
    if t_off is None:
        b0 = d0 = c0 = 0.0
    else:
        b0 = math.exp(-t_off / tau['blade_off']); d0 = math.exp(-t_off / tau['disc_off']); c0 = math.exp(-t_off / tau['carrier_off'])
    t = np.arange(0.0, t_end + dt, dt)
    fb = 1 - (1 - b0) * np.exp(-t / tau['blade']); fd = 1 - (1 - d0) * np.exp(-t / tau['disc']); fc = 1 - (1 - c0) * np.exp(-t / tau['carrier'])
    clr = tp['cold_clearance'] + carr * fc - (mech + blade_th * fb + disc_th * fd)
    return t, clr


def labyrinth(p_up, p_dn, T_K, r_mm, cl_mm, n, Cd=0.70, carry=1.15):
    """Martin's formula with a carry-over factor: leakage [kg/s]"""
    A_ = 2 * math.pi * r_mm * 1e-3 * cl_mm * 1e-3; pr = p_dn / p_up
    return carry * Cd * A_ * p_up / math.sqrt(287.0 * T_K) * math.sqrt((1 - pr * pr) / (n - math.log(pr)))


def main():
    res = dict(rev='hot section rev 1', checks=[])
    def check(test, value, limit, unit, ok, note=''):
        res['checks'].append(dict(test=test, value=value, limit=limit, unit=unit, ok=bool(ok), note=note))
        print('  %-52s %10.4g %-4s (limit %.4g) %s  %s' % (test, value, unit, limit, 'OK' if ok else 'FAIL', note))
    # ------------------------------------------------------------------ 1. carriers
    print('1. shroud carriers (1.4828) cooled outside by the compressor delivery air (%.2f bar, %.0f C, %.2f kg/s)' % (P_CD / 1e5, T_CD - 273.15, M_AIR))
    car = {}
    for row, ro in (('R1', H.C1['ro']), ('R2', H.C2['ro'])):
        g, T_need = size_gap(row, ro)
        g = round(g)
        Tc, hg, hc, v, dp = carrier_T(row, g, ro)
        car[row] = dict(gap_mm=g, T_carrier=Tc, T_needed=T_need, h_gas=hg, h_air=hc, v_air=v, dp_Pa=dp, T_gas=T_GAS[row])
        clr = TIPS[row]['cold_clearance'] + ALPHA_C * TIPS[row]['casing_r'] * (Tc - 20) - TIPS[row]['rotor_growth']
        car[row]['running_clearance'] = clr
        print('   %s: gas %.0f C, h_gas %.0f / h_air %.0f W/m2K (channel gap %d mm, %.0f m/s, dp %.0f Pa) -> carrier %.0f C (needed %.0f) -> '
              'running clearance %.2f mm' % (row, T_GAS[row], hg, hc, g, v, dp, Tc, T_need, clr))
        check('%s running tip clearance' % row, clr, TIPS[row]['target_running'] - 0.05, 'mm', abs(clr - TIPS[row]['target_running']) <= 0.05,
              'target %.2f, channel gap %d mm' % (TIPS[row]['target_running'], g))
        check('%s carrier metal temperature' % row, Tc, 600.0, 'C', Tc <= 600.0, '1.4828 lightly loaded ring')
    res['carriers'] = car
    # ------------------------------------------------------------------ 2. transients
    print('2. tip-clearance transients')
    tc = {}
    for row, t_car in (('R1', H.C1['ro'] - H.C1['ri']), ('R2', H.C2['ro'] - H.C2['ri'])):
        hsum = car[row]['h_gas'] + car[row]['h_air']
        tau = dict(blade=25.0, disc=900.0, carrier=7900 * 560 * (t_car + H.HC['back']) * 1e-3 / hsum,
                   blade_off=600.0, disc_off=5400.0, carrier_off=1500.0)
        t, cs = transient(row, tau)
        cold_min = float(cs.min())
        rest = {}
        for toff in (5 * 60, 15 * 60, 30 * 60, 60 * 60, 120 * 60, 240 * 60):
            _, cr = transient(row, tau, toff); rest[toff] = float(cr.min())
        rub = [k for k, v in sorted(rest.items()) if v < 0.0]
        window = (rub[0] / 60, rub[-1] / 60) if rub else None             # restart times after shutdown that rub [min]
        tc[row] = dict(tau_s=tau, cold_start_min=cold_min, hot_restart_min=rest, rub_window_min=window, curve=[(float(a), float(b)) for a, b in zip(t[::30], cs[::30])])
        print('   %s: carrier tau %.0f s; cold start: min clearance %.2f mm; hot restart min clearance %s; rubs for restarts %s' % (
            row, tau['carrier'], cold_min, ', '.join('%d min %.2f' % (k / 60, v) for k, v in rest.items()),
            '%.0f-%.0f min after shutdown' % window if window else 'never'))
        check('%s cold start: minimum tip clearance' % row, cold_min, 0.0, 'mm', cold_min >= 0.0, 'carrier faster than the disc')
        worst = min(rest.values())
        check('%s hot restart: worst rub into the honeycomb' % row, -min(0.0, worst), 0.5, 'mm', -min(0.0, worst) <= 0.5,
              'abradable honeycomb; restart inhibit %s' % ('%.0f min - %.0f h after a trip' % (window[0], window[1] / 60) if window else 'none'))
    res['transients'] = tc
    # ------------------------------------------------------------------ 3. casing, bolts, pins, NGV loads
    print('3. outer casing, bolts, pins')
    c = H.CAS; pg = P_CD - 100.7e3; ri = c['ri'] * 1e-3; t = c['t'] * 1e-3
    s_hoop = pg * ri / t / 1e6
    L = (c['x1'] - c['x0']) * 1e-3
    F_side = pg * ri * L                                          # split-line separating force per side
    n_b = int((c['x1'] - c['x0'] - 40) // c['pitch']) + 1
    As16 = 157.0; F_pre = 0.7 * 640.0 * As16                    # M16 8.8 at 70 % of proof
    gasket = 2.5
    check('outer casing hoop stress / allowable (EN-GJS-400-18LT, 80 MPa)', s_hoop / 80.0, 1.0, '-', s_hoop <= 80.0, '%.1f MPa at %.2f bar g' % (s_hoop, pg / 1e5))
    check('split-flange bolts: clamp / (2.5 x pressure load)', n_b * F_pre / (gasket * F_side), 1.0, '-', n_b * F_pre >= gasket * F_side,
          '%d x M16 8.8 per side, pitch %.0f mm' % (n_b, c['pitch']))
    # NGV gas loads (axial: static pressure drop x annulus; torque: change of r c_theta x mass flow) -> keys and hooks
    m_g = M_AIR * 1.0084
    def ngv_axial(st, x0, x1):
        p_in = st['P0_in'] * 0.98; p_out = st['P0_in'] * 0.985 / (1 + 0.165 * st['M2'] ** 2) ** 4.03
        return (p_in - p_out) * math.pi * ((A.r_tip(x0) * 1e-3) ** 2 - (A.r_hub(x0) * 1e-3) ** 2)
    Fa1 = ngv_axial(S1, A.X_LE['N1'], A.X_TE['N1']); Fa2 = ngv_axial(S2, A.X_LE['N2'], A.X_TE['N2'])
    T1 = STACK['torque_Nm']['rated']['drum_R1'] - STACK['torque_Nm']['rated']['R1_R2']; T2 = STACK['torque_Nm']['rated']['R1_R2']
    res['ngv_loads'] = dict(N1_axial_N=Fa1, N2_axial_N=Fa2, N1_torque_Nm=T1, N2_torque_Nm=T2)
    print('   NGV1 axial %.1f kN, torque %.0f Nm; NGV2 axial %.1f kN, torque %.0f Nm (to the carriers, then the pins)' % (Fa1 / 1e3, T1, Fa2 / 1e3, T2))
    # pins: torque + axial + weight of the hot inner structure shared by 8 pins (each takes load in its tangential and axial
    # direction only, radial sliding), single shear, 1.4980 (A286) at ~ 400 C, allowable shear 0.4 x 600 MPa
    W_hot = 9.81 * 70.0
    F_t = (T1 + T2) / (H.FLANGE_C['ro'] * 1e-3); F_pin = math.hypot(F_t, Fa1 + Fa2) / (H.PIN['n'] / 2) + W_hot / 2
    tau_pin = F_pin / (math.pi / 4 * (H.PIN['d'] * 1e-3) ** 2) / 1e6
    check('centring pin shear / allowable (A286, 240 MPa)', tau_pin / 240.0, 1.0, '-', tau_pin <= 240.0, '%.0f MPa, %d pins Ø%.0f' % (tau_pin, H.PIN['n'], H.PIN['d']))
    dr = ALPHA_C * H.FLANGE_C['ro'] * (car['R1']['T_carrier'] - 20) - 11.5e-6 * (H.CAS['ri'] + H.CAS['t']) * (T_CD - 273.15 - 20)
    res['pins'] = dict(shear_MPa=tau_pin, radial_slide_mm=dr)
    print('   pin shear %.0f MPa; radial sliding of the carriers on the pins %.2f mm (hot)' % (tau_pin, dr))
    res['casing'] = dict(hoop_MPa=s_hoop, bolts_per_side=n_b, F_side_N=F_side)
    # ------------------------------------------------------------------ 4. secondary air
    print('4. secondary air (labyrinths, clearance 0.30 mm)')
    th = STACK['thrust']['cavities']; p_feed = 0.97 * P_CD; p2s = STACK['thrust']['states']['c2']['p2']
    flows = dict(
        drum_balance_seal=labyrinth(p_feed, th['p_cf'], T_CD, G.BAL_SEAL_R, 0.30, 6),
        backface_seal_r200=labyrinth(p_feed, p2s, T_CD, G.BACKFACE['r_seal'], 0.30, 4),
        interstage_seal=labyrinth(th['p_12'], th['p_2f'], S1['T0_out'] - 30, H.SEAL['ri'], 0.30, 4))
    res['secondary_air'] = {k: dict(kg_s=v, pct=100 * v / M_AIR) for k, v in flows.items()}
    for k, v in flows.items():
        print('   %-22s %.3f kg/s = %.2f %% of the air' % (k, v, 100 * v / M_AIR))
    purge = flows['drum_balance_seal'] + flows['interstage_seal']
    check('turbine purge + interstage leakage', 100 * purge / M_AIR, 1.5, '%', 100 * purge / M_AIR <= 1.5, 'drum balance seal feeds the turbine front cavity')
    print('checks: %d of %d pass' % (sum(c_['ok'] for c_ in res['checks']), len(res['checks'])))
    json.dump(res, open(os.path.join(HERE, 'fea', 'a1000_hot_section.json'), 'w'), indent=1, default=float)
    plot(res)


def plot(res):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.2), dpi=110)
    ax = axs[0]
    for row, col in (('R1', 'tab:red'), ('R2', 'tab:blue')):
        tc = res['transients'][row]; cv = np.array(tc['curve'])
        ax.plot(cv[:, 0] / 60, cv[:, 1], color=col, lw=1.8, label='%s cold start' % row)
        tau = tc['tau_s']
        for toff, ls in ((15 * 60, '--'), (60 * 60, ':')):
            t, cr = transient(row, tau, toff)
            ax.plot(t / 60, cr, color=col, ls=ls, lw=1.2, label='%s hot restart after %d min' % (row, toff / 60))
        ax.axhline(TIPS[row]['target_running'], color=col, lw=0.6)
    ax.axhline(0, color='k', lw=0.8); ax.set_xlim(0, 40); ax.set_xlabel('time after light-off at full load [min]')
    ax.set_ylabel('tip clearance [mm] (< 0: rub into the honeycomb)'); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    ax.set_title('Tip clearance transients (carrier, blade and disc lags)', fontsize=10)
    ax = axs[1]; ax.axis('off')
    rows = [(c['test'][:50], '%.3g %s' % (c['value'], c['unit']), 'OK' if c['ok'] else 'FAIL') for c in res['checks']]
    tbl = ax.table(cellText=rows, colLabels=['check', 'value', ''], loc='upper center', cellLoc='left', colWidths=[0.72, 0.18, 0.10])
    tbl.auto_set_font_size(False); tbl.set_fontsize(7.5); tbl.scale(1, 1.3)
    for (i, j), cell in tbl.get_celld().items():
        if i > 0 and j == 2: cell.set_facecolor('#c8e6c9' if rows[i - 1][2] == 'OK' else '#ffcdd2')
    car = res['carriers']
    ax.set_title('Hot section rev 1: carriers R1 %.0f C (gap %d mm), R2 %.0f C (gap %d mm); %d of %d checks pass' % (
        car['R1']['T_carrier'], car['R1']['gap_mm'], car['R2']['T_carrier'], car['R2']['gap_mm'], sum(c['ok'] for c in res['checks']),
        len(res['checks'])), fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_hot_section.png')); print('written docs/img/a1000_hot_section.png')


if __name__ == '__main__':
    main()
