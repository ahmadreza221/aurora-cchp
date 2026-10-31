#!/usr/bin/env python3
"""AURORA-1000 rotor stack and bearings (rotor rev 1), geometry in cad/engine/a1000_rotor.py:
  1. why the blisks stay bore-less (disc FEA of a bored variant, --bore-study)
  2. torque and axial thrust along the rotor; balance-piston radius on the drum; thrust-bearing load
  3. compressor tie bolt: stiffness, preload through assembly / cold start / steady / hot shutdown, with the Poisson
     shortening of the spinning hubs; required clamp of every curvic joint (torque incl. generator short circuit,
     bending, axial load); curvic flank pressure
  4. hot joints (16 x M10 studs through bolted curvics on the cast arm flanges): preload, thermal change, torque
  5. disc FEA (CalculiX CAX6) of both blisks with the new cast arms: hub, arm root, flange hoop at the stud holes, LCF
  6. tilting-pad journals and thrust bearing: film, temperature rise, oil flow, power loss; squeeze-film dampers and
     integral S-spring damper rings; rotor dynamics of the detailed stack (sim/engine/a1000_rotordynamics.py solver)
  7. bearing losses against the cycle's mechanical-loss allowance
  8. transient axial thrust through trips, surge, start and stop (sim/engine/a1000_thrust_transient.py, run from here
     after the steady results are written): its checks join this list
Run:    python sim/engine/a1000_rotor_stack.py [--bore-study]    (numpy, scipy, matplotlib; CCX = ccx path, gmsh for the FEA)
Writes: sim/engine/fea/a1000_rotor_stack.json, docs/img/a1000_rotor_stack.png (+ the transient JSON and plot)
"""
import json
import math
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine')); sys.path.insert(0, os.path.join(ROOT, 'sim'))
_parts = os.path.join(ROOT, 'cad_out', 'engine', 'A1000', 'A1000_parts.json')
if not os.path.exists(_parts):                                  # the disc FEA reads the blade masses from the CAD export
    os.makedirs(os.path.dirname(_parts), exist_ok=True); shutil.copyfile(os.path.join(ROOT, 'fusion', 'A1000', 'parts.json'), _parts)
import a1000_rotor as G                                       # noqa: E402  (geometry; imports a1000_rotordynamics as RD)
RD, A = G.RD, G.A
import a1000_disc_fea as DF                                   # noqa: E402
import a1000_turbine_checks as TC                             # noqa: E402  (manson_cycles, material tables)
import e1_turbine_fea as F                                    # noqa: E402

ML = RD.ML
N_OP, N_TRIP = 15000.0, 16500.0
OM = N_OP * 2 * math.pi / 60
P_AMB = 100.7e3                                                # site 50 m
OUT_FEA = os.path.join(ROOT, 'cad_out', 'fea_rotor')
KT_HOLE = 2.6                                                  # stud hole in a hoop field (round hole, Kt 3, chamfered/cold-worked)


def lin(T, Ts, Vs):
    return float(np.interp(T, Ts, Vs))


# materials: E [MPa], mean expansion 20 -> T [1/K], 0.2 % yield [MPa], density [kg/m3], Poisson
MAT = {
    'IN718':     dict(E=([20, 400, 650], [200e3, 184e3, 172e3]), a=([20, 300, 650], [12.8e-6, 13.5e-6, 14.4e-6]),
                      Sy=([20, 400, 650], [1030., 980., 940.]), rho=8190., nu=0.29),
    '34CrNiMo6': dict(E=([20, 200], [210e3, 200e3]), a=([20, 200], [11.5e-6, 12.5e-6]), Sy=([20, 200], [700., 640.]), rho=7850., nu=0.29),
    '17-4PH':    dict(E=([20, 300], [196e3, 186e3]), a=([20, 300], [10.8e-6, 11.3e-6]), Sy=([20, 300], [1000., 880.]), rho=7800., nu=0.27),
    'Al2618':    dict(E=([20, 150], [74e3, 69e3]), a=([20, 150], [22.3e-6, 23.4e-6]), Sy=([20, 100, 150], [330., 305., 280.]), rho=2760., nu=0.33),
    'Ti64':      dict(E=([20, 200], [114e3, 104e3]), a=([20, 200], [8.6e-6, 9.2e-6]), Sy=([20, 200], [880., 690.]), rho=4430., nu=0.34),
    'MAR-M247':  dict(E=(list(DF.MAT_T), list(DF.MAT_E)), a=(list(DF.MAT_T), list(DF.MAT_A)), Sy=(list(DF.MAT_T), list(DF.MAT_YS)),
                      rho=8540., nu=0.30),
}


def mp(m, key, T): return lin(T, *MAT[m][key])


# ================================================================================================ 2. loads
def states():
    """static pressures [Pa abs] and temperatures along the gas path at the design point (meanline)"""
    c1, c2 = ML['compressor']; T = ML['turbine']; s1, s2 = T['stages']; m = ML['ma']
    out = dict(m_air=m, m_gas=m * 1.0084)                    # + fuel (~0.84 %)
    for k, st in (('c1', c1), ('c2', c2)):
        g = 1.4; T1 = st['T01'] - st['c1'] ** 2 / 2010.0; rho1 = st['P01'] / (287.0 * st['T01'])
        p1 = st['P01'] - 0.5 * rho1 * st['c1'] ** 2
        T2 = st['T02'] / (1 + 0.2 * st['M2'] ** 2)
        p2 = st['P01'] * (1 + min(st['eta'] + 0.06, 0.94) * (T2 - st['T01']) / st['T01']) ** 3.5
        out[k] = dict(p_eye=p1, p2=p2, T2=T2, rho2=p2 / (287.0 * T2), r1h=st['r1h'] * 1e3, r1t=st['r1t'] * 1e3,
                      r2=st['D2'] / 2 * 1e3, c1=st['c1'], P=m * st['dh0'], T01=st['T01'], T02=st['T02'])
    gg, cp = 1.33, 1170.0
    for k, st in (('t1', s1), ('t2', s2)):
        p_ngv = st['P0_in'] * 0.985 / (1 + 0.5 * (gg - 1) * st['M2'] ** 2) ** (gg / (gg - 1))
        C3 = T['Cx'] / math.cos(math.radians(8.5)); T3 = st['T0_out'] - C3 ** 2 / (2 * cp)
        M3 = C3 / math.sqrt(gg * cp * (gg - 1) / gg * T3)
        p3 = st['P0_out'] / (1 + 0.5 * (gg - 1) * M3 ** 2) ** (gg / (gg - 1))
        out[k] = dict(p_ngv=p_ngv, p3=p3, P=out['m_gas'] * cp * (st['T0_in'] - st['T0_out']), T0_in=st['T0_in'])
    out['p_cd'] = c2['P02']                                     # compressor delivery (total)
    # impeller detail design (sim/a1000_impeller_design.json, compressor rev 1) replaces the meanline radii and pressures
    det = os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')
    if os.path.exists(det):
        D = json.load(open(det))
        for k, key in (('c1', 'C1'), ('c2', 'C2')):
            g, pf = D['stages'][key]['geometry'], D['stages'][key]['performance']; im = pf['impeller']
            P01 = pf['P01']; c1v = D['stages'][key]['inducer']['c1']
            rho1 = P01 / (287.0 * pf['T01'])
            out[k].update(p_eye=P01 - 0.5 * rho1 * c1v ** 2, p2=im['P2'], T2=im['T2'], rho2=im['P2'] / (287.0 * im['T2']), r1h=g['r1h'],
                          r1t=g['r1t'], r2=g['r2'], c1=c1v, P=m * (im['dh0'] if 'dh0' in im else out[k]['P'] / m))
        out['p_cd'] = D['stages']['C2']['performance']['diffuser']['P04'] * (1 - D['overall'].get('collector_dP0', 0.0))
        out['detail'] = True
    return out


def vortex_force(p_tip, rho, r_tip, r_in, k=0.45):
    """axial force [N] of a rotor-stator cavity on the rotor face from r_in to r_tip (gauge pressure, core swirl k)"""
    a, b = r_in * 1e-3, r_tip * 1e-3; v2 = (k * OM * b) ** 2; pg = p_tip - P_AMB
    # p(r) = p_tip - rho/2 (k om)^2 (b^2 - r^2)
    return math.pi * ((pg - 0.5 * rho * v2) * (b * b - a * a) + 0.5 * rho * (k * OM) ** 2 * (b ** 4 - a ** 4) / 2)


def r2_force(p_in, r_in, p_out, r_out):
    """axial force [N] of a pressure rising with r^2 from p_in at r_in to p_out at r_out (impeller hub surface, gauge)"""
    a, b = r_in * 1e-3, r_out * 1e-3; pi_, po = p_in - P_AMB, p_out - P_AMB
    B = (po - pi_) / (b * b - a * a); Aa = pi_ - B * a * a
    return math.pi * (Aa * (b * b - a * a) + B * (b ** 4 - a ** 4) / 2)


def annulus(p, ri, ro):
    return (p - P_AMB) * math.pi * ((ro * 1e-3) ** 2 - (ri * 1e-3) ** 2)


def thrust(S, r_bp, scale=1.0):
    """axial forces on the rotor [N], + = aft (toward the turbine); scale multiplies all gauge pressures and momentum
    (part load ~ (load)^1 on the pressure ratios, rough)"""
    c1, c2, t1, t2 = S['c1'], S['c2'], S['t1'], S['t2']
    r_seal_in, r_spc = 48.0, 75.0                              # inlet seal on the stub, interstage seal on the spacer
    r_s2 = G.ARM['rf'] + 1.0                                     # interstage (under NGV2) labyrinth: rev 6 fins on the R1 - R2 spacer
    r_rear = 56.0                                               # rear oil/air seal on the rear stub
    rh1, rt1 = A.row_radius('R1', 0.0), A.row_radius('R1', 1.0); rh2, rt2 = A.row_radius('R2', 0.0), A.row_radius('R2', 1.0)
    p_cf = t1['p_ngv'] * 1.04                                   # turbine front cavity: purge 4 % above the NGV1 exit static
    p_12 = t1['p3'] * 1.03; p_2f = t2['p_ngv'] * 1.03; p_ra = t2['p3'] * 1.02
    f = dict()
    f['imp 1 hub surface'] = r2_force(c1['p_eye'], r_seal_in, c1['p2'], c1['r2'])
    f['imp 1 inlet momentum'] = S['m_air'] * c1['c1']
    f['imp 1 back face'] = -vortex_force(c1['p2'], c1['rho2'], c1['r2'], r_spc)
    f['spacer step (imp 2 eye)'] = -annulus(c2['p_eye'], c2['r1h'], r_spc)
    f['imp 2 hub surface'] = r2_force(c2['p_eye'], c2['r1h'], c2['p2'], c2['r2'])
    f['imp 2 inlet momentum'] = S['m_air'] * c2['c1']
    # back face: vortex cavity from the tip to the labyrinth at BACKFACE r_seal, inside it the pressurised cavity fed with
    # compressor-delivery air (diffuser exit static ~ 97 % of P02) down to the drum balance seal r_bp
    rs = G.BACKFACE['r_seal']; p_feed = 0.97 * S['p_cd']
    f['imp 2 back face (pressurised)'] = -annulus(p_feed, r_bp, rs)
    f['imp 2 back face (vortex)'] = -vortex_force(c2['p2'], c2['rho2'], c2['r2'], rs)
    f['turbine front cavity (balance)'] = annulus(p_cf, r_bp, rh1)
    f['R1 blade row'] = (t1['p_ngv'] - t1['p3']) * math.pi * ((rt1 * 1e-3) ** 2 - (rh1 * 1e-3) ** 2)
    f['R1 aft cavity'] = -annulus(p_12, r_s2, rh1)
    f['R2 front cavity'] = annulus(p_2f, r_s2, rh2)
    f['R2 blade row'] = (t2['p_ngv'] - t2['p3']) * math.pi * ((rt2 * 1e-3) ** 2 - (rh2 * 1e-3) ** 2)
    f['R2 aft cavity'] = -annulus(p_ra, r_rear, rh2)
    f = {k: v * scale for k, v in f.items()}
    return f, sum(f.values()), dict(p_cf=p_cf, p_12=p_12, p_2f=p_2f, p_ra=p_ra)


# ================================================================================================ 3. compressor stack
def stack_parts(T):
    """clamped compressor stack between the nut face (x 48) and the drum bulkhead thread centre: (name, x0, x1, A_eff mm2,
    material, T [C], Poisson shortening at 15k [mm]); T = dict of part temperatures"""
    om2 = OM ** 2
    def spin_short(mat, a, b, r, L, b_eff):
        nu, E, rho = MAT[mat]['nu'], mp(mat, 'E', T.get(mat, 20)), MAT[mat]['rho']
        srt = rho * om2 * ((3 + nu) / 4 * ((a * 1e-3) ** 2 + (b_eff * 1e-3) ** 2) - (1 + 3 * nu) / 4 * (r * 1e-3) ** 2) / 1e6
        return nu * srt / E * L, srt
    c1, c2 = ML['compressor']
    xi1, xi2 = G.X_I1, G.X_I2; xbh = G.TIE['x_end'] - G.TIE['thread_len'] / 2
    P = []
    P.append(('front stub', 48.0, xi1[0], math.pi * (48 ** 2 - 23 ** 2), '34CrNiMo6', T['stub'], 0.0))   # rev 1.3: journal r 45, shoulders r 48
    s, _ = spin_short('Al2618', 23.0, 0, 42.0, xi1[1] - xi1[0], 0.75 * c1['D2'] / 2 * 1e3)
    P.append(('impeller 1 hub', xi1[0], xi1[1], math.pi * (55 ** 2 - 23 ** 2), 'Al2618', T['imp1'], s))
    P.append(('spacer', xi1[1], xi2[0], math.pi * (58 ** 2 - 23 ** 2), '17-4PH', T['spacer'], 0.0))
    s, _ = spin_short('Ti64', 23.0, 0, 45.0, xi2[1] - xi2[0], 0.75 * c2['D2'] / 2 * 1e3)
    P.append(('impeller 2 hub', xi2[0], xi2[1], math.pi * (58 ** 2 - 23 ** 2), 'Ti64', T['imp2'], s))
    s, _ = spin_short('IN718', 70.0, 0, 77.5, xbh - xi2[1], 85.0)
    P.append(('drum to bulkhead', xi2[1], xbh, math.pi * (85 ** 2 - 70 ** 2), 'IN718', T['drum'], s))
    return P


T_SS = dict(stub=60.0, imp1=75.0, spacer=120.0, imp2=160.0, drum=230.0, bolt=None)   # steady metal temperatures [C]


def tie_bolt(T_parts, T_bolt, spin=True):
    """free length mismatch [mm] (stack minus bolt, + = preload rises), compliances [mm/N]"""
    tb = G.TIE; x0, x1 = tb['x_nut'][1], tb['x_end'] - tb['thread_len'] / 2
    Ash = math.pi / 4 * tb['shank'] ** 2; Ath = math.pi / 4 * (tb['d'] - 0.9382 * tb['pitch']) ** 2
    Lth = 0.4 * tb['d'] * 2                                     # effective engaged-thread lengths (VDI 2230, nut + bulkhead)
    Eb = mp('IN718', 'E', T_bolt)
    cb = (x1 - x0) / (Eb * Ash) + Lth / (Eb * Ath)
    parts = stack_parts(T_parts)
    cs = sum((x1_ - x0_) / (mp(m, 'E', Tp) * Ae) for _, x0_, x1_, Ae, m, Tp, _ in parts) + 4 * 0.5e-7   # + 4 curvic contacts
    d_stack = sum(mp(m, 'a', Tp) * (Tp - 20) * (x1_ - x0_) for _, x0_, x1_, _, m, Tp, _ in parts)
    d_spin = -sum(s for *_, s in parts) if spin else 0.0
    d_bolt = mp('IN718', 'a', T_bolt) * (T_bolt - 20) * (x1 - x0)
    return d_stack + d_spin - d_bolt, cb, cs, parts, Ash


def mass_by_x():
    """(mass kg, x mm) items of the detailed rotor (for gravity bending and polar inertia shares)"""
    items = []
    R = RD.rotor('A')
    for k in ('coupling', 'impeller1', 'impeller2', 'blisk1', 'blisk2'):
        d = R['discs'][k]; items.append((d['m'], d['x'], d.get('Ip', 0.0), k))
    for name, f, mat, rho in G.ROTOR_PARTS:
        V, xc = G.poly_area_props(f()); items.append((V * 1e-9 * rho, xc, 0.0, name))
    for row in ('R1', 'R2'):
        Va, xa = G.poly_area_props(G.disc_profile_arms(row)); Vd, xd = G.poly_area_props([(x + G.X_OFF, r) for x, r in A.disc_profile(row)])
        items.append(((Va - Vd) * 1e-9 * 8540, (Va * xa - Vd * xd) / (Va - Vd), 0.0, row + ' arms'))
    return items


def gravity_moment(x, g_factor=3.0):
    """bending moment [Nm] at x from the rotor weight on the two journals (simply supported), x g_factor (1 g + 2 g
    transport / seismic / shock allowance)"""
    it = mass_by_x(); xb1, xb2 = G.X_BRG
    W = sum(m for m, *_ in it) * 9.81; xc = sum(m * xx for m, xx, *_ in it) / sum(m for m, *_ in it)
    R1 = W * (xb2 - xc) / (xb2 - xb1)
    M = R1 * max(0.0, x - xb1) * 1e-3 - sum(m * 9.81 * max(0.0, x - xx) * 1e-3 for m, xx, *_ in it)
    return abs(M) * g_factor


def curvic_ring_clamp(ri, ro, M, T, Fax_tension, phi=30.0):
    """clamp [N] a curvic ring needs: no gap under bending (F/A >= M c / I), torque separating force T/r_pd tan(phi),
    and a tensile axial load through the joint"""
    a, b = ri * 1e-3, ro * 1e-3; Ar = math.pi * (b * b - a * a); I = math.pi / 4 * (b ** 4 - a ** 4)
    F_b = M * b * Ar / I; F_t = T / (0.5 * (a + b)) * math.tan(math.radians(phi))
    return F_b + F_t + max(0.0, Fax_tension), dict(bending=F_b, torque=F_t, axial=max(0.0, Fax_tension))


def curvic_flank_pressure(F_ax, T, ri, ro, N, h=None, phi=30.0):
    """mean flank contact pressure [MPa]: clamp (both flanks) + torque on the drive flank; tooth height 0.35 x the
    circular pitch at the pitch diameter (unless h is given), ground flanks bearing over 75 % of the height, flanks at
    phi to the axis"""
    F = ro - ri; r_pd = 0.5 * (ri + ro) * 1e-3
    h = h or 0.35 * math.pi * 2 * r_pd * 1e3 / N; hc = 0.75 * h
    A_fl = N * F * hc / math.cos(math.radians(phi))              # one flank per tooth [mm2]
    N_clamp = F_ax / (2 * math.sin(math.radians(phi)))            # per flank side
    N_torque = T / r_pd / math.cos(math.radians(phi))
    return (N_clamp + N_torque) / A_fl


# ================================================================================================ 6. bearings
def _walther_fit():
    t1, n1, t2, n2 = 313.15, 32.0, 373.15, 5.4
    y1, y2 = math.log10(math.log10(n1 + 0.7)), math.log10(math.log10(n2 + 0.7))
    B = (y1 - y2) / (math.log10(t2) - math.log10(t1)); A_ = y1 + B * math.log10(t1)
    return A_, B


def visc(T):
    """ISO VG 32 dynamic viscosity [Pa s]: Walther fit through 32 cSt at 40 C and 5.4 cSt at 100 C, 860 kg/m3"""
    A_, B_ = _walther_fit(); nu = 10 ** (10 ** (A_ - B_ * math.log10(T + 273.15))) - 0.7
    return nu * 1e-6 * 860.0


RHO_OIL, CP_OIL, T_OIL_IN = 860.0, 2000.0, 50.0


def turb_factor(Re):
    """friction increase in turbulent / transitional films (Constantinescu, fitted), laminar below Re 1000"""
    return 1.0 if Re < 1000 else 1.0 + 0.0012 * (Re ** 0.94 - 1000 ** 0.94)


def journal(W, D=None, L=None, m_pre=0.3, cb_ratio=1.4e-3, n_pad=None, arc=None, dT_oil=20.0):
    """tilting-pad journal, load between pads: minimum film (tilting-slider model, W_bar 0.06), pad film stiffness at
    the preloaded position, power loss (Petroff on the pad arc x turbulence), oil flow for dT_oil, Babbitt temperature.
    Pads from G.JOURNAL (sec. 19: 4 pads x 65 deg, load between pads, so the horizontal split runs between pads; rev 1.3:
    5 x 52 deg): the two loaded pads sit at +-180/n from the load line, the sum of cos^2 over the pads is n / 2"""
    D = D or G.JOURNAL['D']; L = L or G.JOURNAL['L']; R = D / 2e3; Lm = L * 1e-3
    n_pad = n_pad or G.JOURNAL.get('n_pad', 5); arc = arc or G.JOURNAL.get('arc', 52.0)
    U = OM * R; Cb = cb_ratio * R; Cp = Cb / (1 - m_pre); B = R * math.radians(arc)
    T_eff = T_OIL_IN + 0.6 * dT_oil + 10.0; mu = visc(T_eff)
    Wbar = 0.06
    W_pad = W / (2 * math.cos(math.radians(180.0 / n_pad)))
    h_load = B * math.sqrt(Wbar * mu * U * Lm / W_pad)
    h_min = min(h_load, Cb)
    W_p0 = Wbar * mu * U * B ** 2 * Lm / Cb ** 2                   # each pad at the preloaded concentric position
    K = n_pad / 2.0 * 2 * W_p0 / Cb                               # sum cos^2 = n / 2, pad k = 2 W / h (W ~ 1 / h^2)
    h_eff = 0.5 * (Cb + Cp); Re = RHO_OIL * U * h_eff / mu
    A_f = n_pad * B * Lm
    P = mu * U ** 2 * A_f / h_eff * turb_factor(Re)
    Q = P / (RHO_OIL * CP_OIL * dT_oil)
    return dict(D=D, L=L, n_pad=n_pad, arc=arc, U=U, unit_load_MPa=W / (D * L), Cb_um=Cb * 1e6, Cp_um=Cp * 1e6, mu=mu, T_eff=T_eff, h_min_um=h_min * 1e6,
                K=K, C=K / OM * 0.6, Re=Re, P_kW=P / 1e3, Q_lpm=Q * 6e4, T_babbitt=T_OIL_IN + 2.2 * dT_oil, W=W)


def thrust_bearing(W, ri=None, ro=None, n=None, n_in=None, fill=0.80, dT_oil=20.0):
    """double-acting tilting-pad thrust bearing: unit load, minimum film of the loaded side (tilting slider, W_bar 0.05),
    power loss of the loaded side + the inactive side (n_in pads of the same size in the rest of the 0.30 mm end play)
    x turbulence, oil flow"""
    ri = (ri or G.THRUST['ri']) * 1e-3; ro = (ro or G.THRUST['ro']) * 1e-3; n = n or G.THRUST['n']; n_in = n_in or G.THRUST['n_in']
    rm = 0.5 * (ri + ro); U = OM * rm; B = rm * 2 * math.pi / n * fill; Lr = ro - ri
    A_side = n * B * Lr
    T_eff = T_OIL_IN + 0.6 * dT_oil + 12.0; mu = visc(T_eff)
    W_pad = max(W, 1.0) / n
    h_min = B * math.sqrt(0.05 * mu * U * Lr / W_pad)
    h_m = 1.8 * h_min; Re = RHO_OIL * U * h_m / mu
    P_load = mu * U ** 2 * A_side / h_m * turb_factor(Re)
    h_i = 0.30e-3 - h_min                                         # inactive side: axial end play 0.30 mm
    P_in = n_in / n * mu * U ** 2 * A_side / h_i * turb_factor(RHO_OIL * U * h_i / mu)
    P = P_load + P_in; Q = P / (RHO_OIL * CP_OIL * dT_oil)
    return dict(ri=ri * 1e3, ro=ro * 1e3, n=n, n_in=n_in, U_mean=U, area_mm2=A_side * 1e6, unit_load_MPa=W / A_side / 1e6, h_min_um=h_min * 1e6,
                Re=Re, P_kW=P / 1e3, P_loaded_kW=P_load / 1e3, Q_lpm=Q * 6e4, W=W, cap_kN=2.0e6 * A_side / 1e3,
                cap_reverse_kN=2.0e6 * A_side * n_in / n / 1e3)


def sfd_cage():
    """squeeze-film damper (short bearing, full film with O-ring end seals; pi-film / cavitated = half) and the integral
    S-spring centring springs of the ISFD ring: n curved beams (length l, radial thickness t, axial width = the land),
    fixed-guided, radial stiffness n / 2 x E w t^3 / l^3 (to be confirmed by a FE model of the EDM ring)"""
    s, q = G.SFD, G.ISFD; mu = visc(70.0)
    R, L, cl = s['R'] * 1e-3, s['L'] * 1e-3, s['c'] * 1e-3
    C_full = math.pi * mu * R * L ** 3 / cl ** 3
    E = 196e9; t = q['t'] * 1e-3; l = q['l'] * 1e-3; w = (s['L'] + 8.0) * 1e-3
    k = q['n'] / 2 * E * w * t ** 3 / l ** 3
    return dict(C_full=C_full, C_pi=0.5 * C_full, k=k, mu=mu, E=E, t=t, l=l, c=cl)


def cage_stress(k_info, W_static, orbit):
    E, t, l = k_info['E'], k_info['t'], k_info['l']
    d_static = W_static / k_info['k']                            # sag (taken out by an eccentric ring bore at assembly)
    s_alt = 3 * E * t * orbit / l ** 2 / 1e6                      # fixed-guided beam, end deflection = orbit radius
    return dict(sag_um=d_static * 1e6, s_alt_MPa=s_alt, s_mean_MPa=3 * E * t * d_static / l ** 2 / 1e6)


# ================================================================================================ rotor dynamics
def detailed_rotor(sup):
    """RD rotor dict with the detailed stack (segments, collar and stud lumps); impellers and blisks as in RD"""
    R = RD.rotor('A')
    xi1, xi2 = G.X_I1, G.X_I2; xj = G.X_J; b1, b2 = G.HUB['R1'], G.HUB['R2']
    D, L = G.JOURNAL['D'], G.JOURNAL['L']; xb1, xb2 = G.X_BRG; c1, c2 = ML['compressor']
    af, fl = 2 * G.ARM['ro'], 2 * G.ARM['rf']
    xn = G.TIE['x_nut'][1]                                       # end of the nut pocket (bore 70 in front of it)
    dc = 2 * (G.THRUST['ri'] - 4.0)                              # collar shoulders (the collar itself is a lumped disc)
    seg = [(0.0, 14.0, 160.0, 70.0, 'steel', True), (14.0, xb1 - L / 2 - 6, D - 4, 70.0, 'steel', True),
           (xb1 - L / 2 - 6, xn, D, 70.0, 'steel', True), (xn, xb1 + L / 2 + 6, D, 46.0, 'steel', True),
           (xb1 + L / 2 + 6, G.COLLAR['x0'], dc, 46.0, 'steel', True), (G.COLLAR['x0'], G.COLLAR['x1'], dc, 46.0, 'steel', True),
           (G.COLLAR['x1'], xi1[0], dc, 46.0, 'steel', True),
           (xi1[0], xi1[1], 2 * 0.5 * (c1['r1h'] * 1e3 + 60.0), 46.0, 'al2618', False),
           (xi1[1], xi2[0], 124.0, 46.0, 'steel', True),
           (xi2[0], xi2[1], 2 * 0.5 * (c2['r1h'] * 1e3 + 65.0), 46.0, 'ti64', False),
           (xi2[1], xi2[1] + 20, 170.0, 100.0, 'in718', True), (xi2[1] + 20, xj['drum_R1'] - 78, 170.0, 140.0, 'in718', True),
           (xj['drum_R1'] - 78, xj['drum_R1'] - 38, 140.0, 42.0, 'in718', True), (xj['drum_R1'] - 38, xj['drum_R1'] - 9, 120.0, 100.0, 'in718', True),
           (xj['drum_R1'] - 9, xj['drum_R1'], fl, 100.0, 'in718', True),
           (xj['drum_R1'], xj['drum_R1'] + 9, fl, 116.0, 'marm247', True), (xj['drum_R1'] + 9, b1[0], af, 116.0, 'marm247', True),
           (b1[0], b1[1], 170.0, 0.0, 'marm247', False),
           (b1[1], b1[1] + 13, af, 116.0, 'marm247', True), (b1[1] + 13, xj['R1_spc'], fl, 116.0, 'marm247', True),
           (xj['R1_spc'], xj['spc_R2'], 2 * G.TSPC['ro'], 2 * G.TSPC['ri'], 'in718', True),       # rev 6 spacer ring (waist)
           (xj['spc_R2'], b2[0] - 13, fl, 116.0, 'marm247', True), (b2[0] - 13, b2[0], af, 116.0, 'marm247', True),
           (b2[0], b2[1], 170.0, 0.0, 'marm247', False),
           (b2[1], b2[1] + 13, af, 116.0, 'marm247', True), (b2[1] + 13, xj['R2_stub'] + 9, fl, 100.0, 'in718', True),
           (xj['R2_stub'] + 9, xj['R2_stub'] + 14, 120.0, 50.0, 'in718', True), (xj['R2_stub'] + 14, xb2 - L / 2 - 6, D - 1, 50.0, 'in718', True),
           (xb2 - L / 2 - 6, xb2 + L / 2 + 6, D, 50.0, 'in718', True), (xb2 + L / 2 + 6, xb2 + L / 2 + 30, D - 8, 50.0, 'in718', True)]
    if 'marm247' not in RD.MAT: RD.MAT['marm247'] = (8540., 180e9)
    discs = dict(R['discs'])
    ro_, ri_ = G.COLLAR['ro'] * 1e-3, dc / 2e3
    mc = 7850 * math.pi * (ro_ ** 2 - ri_ ** 2) * (G.COLLAR['x1'] - G.COLLAR['x0']) * 1e-3
    discs['collar'] = dict(m=mc, x=0.5 * (G.COLLAR['x0'] + G.COLLAR['x1']), Ip=mc * (ro_ ** 2 + ri_ ** 2) / 2, Id=mc * (ro_ ** 2 + ri_ ** 2) / 4)
    for k, (x0, x1, xn, dn) in G.STUD_SETS.items():                # 16 studs + nuts, 0.045 kg each at the rev 1 length 26 mm
        ms = 16 * (0.045 + 8190 * math.pi / 4 * (G.STUD['d'] * 1e-3) ** 2 * (x1 - x0 - 26.0) * 1e-3); r = G.STUD['r'] * 1e-3
        discs['studs ' + k] = dict(m=ms, x=0.5 * (x0 + x1), Ip=ms * r * r, Id=ms * r * r / 2)
    tie = (G.TIE['x_nut'][0], G.TIE['x_end'], G.TIE['shank'])
    return dict(seg=seg, discs=discs, brg=list(G.X_BRG), tie=tie, layout='A-detailed')


# ================================================================================================ 5. disc FEA with arms
def disc_fea(rows=('R1', 'R2')):
    os.makedirs(OUT_FEA, exist_ok=True); F.FEA = OUT_FEA; DF.FEA = OUT_FEA
    orig = A.disc_profile
    A.disc_profile = lambda row, P=None: [(x - G.X_OFF, r) for x, r in G.disc_profile_arms(row)]
    res = {}
    try:
        for row in rows:
            for N, tag in ((N_OP, 'op'), (N_TRIP, 'trip')):
                r = DF.run(row, N, 'arms_' + tag)
                nodes = read_inp_nodes(os.path.join(OUT_FEA, 'a1000_disc_%s_arms_%s.inp' % (row, tag)))
                _, blocks = F.read_frd(os.path.join(OUT_FEA, 'a1000_disc_%s_arms_%s.frd' % (row, tag)))
                S = [b for b in blocks if b['name'].startswith('STRESS')][-1]['data']
                vm = {k: float(F.vm(np.array(v[:6]))) for k, v in S.items()}
                Tc, Tp, ne = DF.TEMP[row]; rh = A.row_radius(row, 0.0)
                Tn = lambda k: Tc + (Tp - Tc) * (nodes[k][0] / rh) ** ne
                # arm region: nodes outside the hub faces (|x - xm| > hw), r < flange OD
                xm = 0.5 * (A.X_LE[row] + A.X_TE[row]); hw = A.DISC[row]['hub_w'] / 2
                arm = [k for k in S if abs(nodes[k][1] - xm) > hw - 4.0 and nodes[k][0] < G.ARM['rf'] + 1 and nodes[k][0] > G.ARM['ri'] - 1]
                k_arm = max(arm, key=lambda k: vm[k])
                fl = [k for k in S if abs(nodes[k][1] - xm) > hw + G.ARM['cav'] + 0.5 and abs(nodes[k][0] - G.STUD['r']) < 1.5]
                hoop_fl = max(S[k][2] for k in fl)
                hub = [k for k in S if abs(nodes[k][1] - xm) <= hw - 4.0 and nodes[k][0] < 60.0]
                k_hub = max(hub, key=lambda k: vm[k])
                res['%s_%s' % (row, tag)] = dict(vm_max=r['vm_max'], vm_max_at=r['vm_max_at'], T_at_max=r['T_at_max'],
                                                 margin_yield=r['margin_yield'], burst_ratio=r['burst_ratio'],
                                                 vm_hub=vm[k_hub], hub_at=list(map(float, nodes[k_hub])), T_hub=Tn(k_hub),
                                                 vm_arm=vm[k_arm], arm_at=list(map(float, nodes[k_arm])), T_arm=Tn(k_arm),
                                                 hoop_flange_studs=hoop_fl, T_flange=Tn(fl[0]), u_rim_mm=r['u_rim_mm'])
                print('  %s %5.0f rpm: vm max %.0f MPa at r %.0f x %.0f, margin %.2f, burst %.2f | hub %.0f | arm %.0f at r %.0f x %.0f | '
                      'flange hoop at studs %.0f MPa' % (row, N, r['vm_max'], r['vm_max_at'][0], r['vm_max_at'][1], r['margin_yield'],
                                                         r['burst_ratio'], vm[k_hub], vm[k_arm], nodes[k_arm][0], nodes[k_arm][1], hoop_fl), flush=True)
    finally:
        A.disc_profile = orig
    return res


def read_inp_nodes(path):
    nodes = {}; on = False
    for line in open(path):
        if line.startswith('*'):
            on = line.upper().startswith('*NODE') and 'FILE' not in line.upper(); continue
        if on:
            p = line.split(','); nodes[int(p[0])] = (float(p[1]), float(p[2]))
    return nodes


def bore_study():
    """bored blisk variants (bore r 25 mm, hub +0 / +20 / +30 mm wide, boss r 85 / 100): why the discs stay bore-less"""
    os.makedirs(OUT_FEA, exist_ok=True); F.FEA = OUT_FEA; DF.FEA = OUT_FEA
    orig = A.disc_profile; out = {}
    def bored(rb, dw=0.0, boss=None):
        def prof(row, P=None):
            q = dict(A.DISC[row]); q['hub_w'] += dw
            if boss: q['r_boss'] = boss
            return [(x, max(r, rb)) for x, r in orig(row, q)]
        return prof
    try:
        for name, prof in (('bore-less (rev 5)', orig), ('bore r25', bored(25.0)), ('bore r25, hub +20', bored(25.0, 20.0)),
                           ('bore r25, hub +30, boss r100', bored(25.0, 30.0, 100.0))):
            A.disc_profile = prof
            for row in ('R1', 'R2'):
                r = DF.run(row, N_OP, 'bore_op'); t = DF.run(row, N_TRIP, 'bore_trip')
                de = r['vm_max'] / lin(r['T_at_max'], TC.MAT_T, TC.MAT_E)
                out['%s %s' % (name, row)] = dict(vm=r['vm_max'], r=r['vm_max_at'][0], trip_margin=t['margin_yield'], burst=r['burst_ratio'],
                                                  lcf=TC.manson_cycles(de, r['T_at_max'], r['vm_max']))
                print('  %-30s %s vm %.0f MPa at r %.0f, trip margin %.2f, burst %.2f, LCF %.1e' % (
                    name, row, r['vm_max'], r['vm_max_at'][0], t['margin_yield'], r['burst_ratio'], out['%s %s' % (name, row)]['lcf']), flush=True)
    finally:
        A.disc_profile = orig
    return out


# ================================================================================================ main
def main():
    res = dict(rev='rotor rev 1', checks=[])
    chk = res['checks']
    def check(test, value, limit, unit, ok, note=''):
        chk.append(dict(test=test, value=value, limit=limit, unit=unit, ok=bool(ok), note=note))
        print('  %-48s %10.4g %-4s (limit %.4g) %s  %s' % (test, value, unit, limit, 'OK' if ok else 'FAIL', note))
    if '--bore-study' in sys.argv:
        print('1. bored blisk variants'); res['bore_study'] = bore_study()
    else:
        old = os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')
        if os.path.exists(old): res['bore_study'] = json.load(open(old)).get('bore_study')
    S = states()
    # ------------------------------------------------------------------ torque
    P_c1, P_c2, P_t1, P_t2 = S['c1']['P'] * 1.02, S['c2']['P'] * 1.02, S['t1']['P'], S['t2']['P']   # + 2 % disc friction
    T = lambda P: P / OM
    tq = dict(R2=T(P_t2), R1_R2=T(P_t2), drum_R1=T(P_t1 + P_t2), I2_drum=T(P_t1 + P_t2), spc_I2=T(P_t1 + P_t2 - P_c2),
              I1_spc=T(P_t1 + P_t2 - P_c2), stub_I1=T(P_t1 + P_t2 - P_c2 - P_c1))
    # generator short circuit: 5 x rated coupling torque at the coupling, shared by the polar inertia in front of each joint
    it = mass_by_x(); Ip_tot = sum(ip for _, _, ip, _ in it)
    def ip_aft(x): return sum(ip for m, xx, ip, n in it if xx > x)
    dT_sc = 5.0 * tq['stub_I1']
    xjoint = dict(stub_I1=G.X_I1[0], I1_spc=G.X_I1[1], spc_I2=G.X_I2[0], I2_drum=G.X_I2[1], drum_R1=G.X_J['drum_R1'],
                  R1_R2=G.X_J['R1_spc'], R2_stub=G.X_J['R2_stub'])            # R1 - R2: the front curvic of the spacer (more aft inertia)
    tq_max = {k: tq.get(k, 0.0) + dT_sc * ip_aft(x) / Ip_tot for k, x in xjoint.items()}
    res['torque_Nm'] = dict(rated=tq, max_short_circuit=tq_max, P_kW=dict(c1=P_c1 / 1e3, c2=P_c2 / 1e3, t1=P_t1 / 1e3, t2=P_t2 / 1e3,
                                                                           shaft=(P_t1 + P_t2 - P_c1 - P_c2) / 1e3))
    print('2. power: compressor %.0f + %.0f kW, turbine %.0f + %.0f kW, shaft %.0f kW; coupling torque %.0f Nm' % (
        P_c1 / 1e3, P_c2 / 1e3, P_t1 / 1e3, P_t2 / 1e3, (P_t1 + P_t2 - P_c1 - P_c2) / 1e3, tq['stub_I1']))
    # ------------------------------------------------------------------ thrust and balance piston
    scan = []
    for rbp in np.arange(70.0, 141.0, 5.0):
        _, Fn, _ = thrust(S, rbp); scan.append((rbp, Fn))
    r_bp = G.BAL_SEAL_R
    f_parts, F_net, cav = thrust(S, r_bp)
    cases = {'design (100 %)': F_net, 'part load (~60 %)': thrust(S, r_bp, 0.6)[1], 'idle (~15 %)': thrust(S, r_bp, 0.15)[1]}
    W_thr = max(abs(v) for v in cases.values())
    # failure case: impeller 2 back-face feed lost (pipe break / blocked feed): the whole back face down to the balance seal
    # runs as a free vortex cavity
    c2s = S['c2']
    F_lost = (F_net - f_parts['imp 2 back face (pressurised)'] - f_parts['imp 2 back face (vortex)']
              - vortex_force(c2s['p2'], c2s['rho2'], c2s['r2'], r_bp))
    res['thrust'] = dict(balance_seal_r=r_bp, parts=f_parts, net=F_net, cases=cases, scan=scan, cavities=cav, states=S,
                         backface_feed_lost=F_lost)
    print('   axial thrust (+ aft) at balance seal r %.0f: %s -> net %.1f kN' % (r_bp, ', '.join('%s %.1f' % (k, v / 1e3) for k, v in f_parts.items()), F_net / 1e3))
    print('   balance-seal scan: ' + ', '.join('r%.0f %.1f kN' % (r, f / 1e3) for r, f in scan))
    # cumulative axial load aft of each compressor joint (the collar holds the rotor at the front): + = joint in tension
    order = list(f_parts.items())
    def aft_of(names): return sum(v for k, v in order if any(k.startswith(n) for n in names))
    fax = dict(stub_I1=aft_of(['imp 1', 'spacer', 'imp 2', 'turbine', 'R1', 'R2']), I1_spc=aft_of(['spacer', 'imp 2', 'turbine', 'R1', 'R2']),
               spc_I2=aft_of(['imp 2', 'turbine', 'R1', 'R2']), I2_drum=aft_of(['turbine', 'R1', 'R2']),
               drum_R1=aft_of(['R1', 'R2']) + f_parts['turbine front cavity (balance)'] * 0.7, R1_R2=aft_of(['R2']), R2_stub=f_parts['R2 aft cavity'])
    # ------------------------------------------------------------------ compressor tie bolt
    print('3. compressor stack, tie bolt M42 IN718')
    Tb_ss = None
    pp = stack_parts(dict(T_SS, **{'34CrNiMo6': T_SS['stub'], 'Al2618': T_SS['imp1'], '17-4PH': T_SS['spacer'], 'Ti64': T_SS['imp2'], 'IN718': T_SS['drum']}))
    Lsum = sum(x1 - x0 for _, x0, x1, *_ in pp)
    Tb_ss = sum((x1 - x0) * Tp for _, x0, x1, _, _, Tp, _ in pp) / Lsum - 5.0          # bolt: length-weighted stack mean - 5 K
    def tparts(f_stack):
        return dict(stub=20 + f_stack * (T_SS['stub'] - 20), imp1=20 + f_stack * (T_SS['imp1'] - 20), spacer=20 + f_stack * (T_SS['spacer'] - 20),
                    imp2=20 + f_stack * (T_SS['imp2'] - 20), drum=20 + f_stack * (T_SS['drum'] - 20))
    STATES = {'assembly (20 C, 0 rpm)': (0.0, 0.0, False), 'cold start (stack 90 %, bolt 30 %, 15k)': (0.9, 0.3, True),
              'steady 15k': (1.0, 1.0, True), 'hot shutdown (stack 40 %, bolt 85 %, 0 rpm)': (0.4, 0.85, False),
              'hot restart (stack 100 %, bolt 85 %, 15k)': (1.0, 0.85, True)}
    def stack_T(f): return dict(tparts(f), **{'34CrNiMo6': 20 + f * 40, 'Al2618': 20 + f * 55, '17-4PH': 20 + f * 100, 'Ti64': 20 + f * 140,
                                              'IN718': 20 + f * 210})
    Fpre = G.TIE['pre_kN'] * 1e3
    pre = {}
    for k, (fs, fb, spin) in STATES.items():
        d, cb, cs, parts, Ash = tie_bolt(stack_T(fs), 20 + fb * (Tb_ss - 20), spin)
        pre[k] = Fpre + d / (cb + cs)
    cb0, cs0 = tie_bolt(stack_T(0), 20, False)[1:3]
    # required clamp per compressor joint (worst of rated + short circuit)
    req = {}
    for j, ring in G.CURVIC_C.items():
        M = gravity_moment(xjoint[j])
        F_r, br = curvic_ring_clamp(ring['ri'], ring['ro'], M, tq_max[j], fax[j])
        req[j] = dict(F=F_r, parts=br, M=M, T=tq_max[j], Fax=fax[j])
    F_req = max(v['F'] for v in req.values())
    F_min, F_max = min(pre.values()), max(pre.values())
    sb_max = F_max / Ash
    res['tie_bolt'] = dict(preload_assembly_N=Fpre, k_bolt=1 / cb0, k_stack=1 / cs0, T_bolt_ss=Tb_ss, states=pre, required=req, F_req=F_req)
    for k, v in pre.items(): print('   %-46s preload %.0f kN' % (k, v / 1e3))
    for j, v in req.items():
        print('   joint %-8s needs %.0f kN (bending %.0f at M %.0f Nm, torque %.0f at %.0f Nm, axial %.0f)' % (
            j, v['F'] / 1e3, v['parts']['bending'] / 1e3, v['M'], v['parts']['torque'] / 1e3, v['T'], v['parts']['axial'] / 1e3))
    check('tie bolt: min clamp / required (all states)', F_min / F_req, 1.25, '-', F_min / F_req >= 1.25, 'min %.0f kN, required %.0f kN' % (F_min / 1e3, F_req / 1e3))
    check('tie bolt: max shank stress / 0.75 Sy', sb_max / (0.75 * mp('IN718', 'Sy', Tb_ss)), 1.0, '-', sb_max <= 0.75 * mp('IN718', 'Sy', Tb_ss),
          '%.0f MPa (shank %.0f mm)' % (sb_max, G.TIE['shank']))
    # curvic flank pressure at max clamp; impeller 1 (Al) is the soft one
    cpres = {}
    for j, ring in G.CURVIC_C.items():
        cpres[j] = curvic_flank_pressure(F_max, tq_max[j], ring['ri'], ring['ro'], ring['N'])
    res['curvic_compressor'] = dict(rings=G.CURVIC_C, flank_MPa=cpres)
    lim_al, lim_ti = 0.6 * mp('Al2618', 'Sy', T_SS['imp1']), 0.6 * mp('Ti64', 'Sy', T_SS['imp1'])
    p_f, p_r = cpres['stub_I1'], cpres['I1_spc']
    res['curvic_compressor']['impeller1'] = dict(front=p_f, rear=p_r, limit_Al2618=lim_al, limit_Ti64=lim_ti)
    det = os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')
    mat1 = json.load(open(det))['stages']['C1']['material'] if os.path.exists(det) else 'Al 2618'
    lim1 = lim_ti if mat1.startswith('Ti') else lim_al
    res['curvic_compressor']['impeller1']['material'] = mat1
    check('impeller 1 front curvic (%s) / 0.6 Sy' % mat1, p_f / lim1, 1.0, '-', p_f <= lim1,
          '%.0f MPa on r %.0f-%.0f%s' % (p_f, G.CURVIC_C['stub_I1']['ri'], G.CURVIC_C['stub_I1']['ro'], '' if mat1.startswith('Ti') else
                                        '; Al 2618 would need Ti-6Al-4V (%.2f)' % (p_f / lim_ti)))
    check('impeller 1 rear curvic (%s) / 0.6 Sy' % mat1, p_r / lim1, 1.0, '-', p_r <= lim1, '%.0f MPa' % p_r)
    p_o = max(cpres['spc_I2'], cpres['I2_drum'])
    check('impeller 2 curvics, Ti-6Al-4V / 0.6 Sy', p_o / (0.6 * mp('Ti64', 'Sy', T_SS['imp2'])), 1.0, '-', p_o <= 0.6 * mp('Ti64', 'Sy', T_SS['imp2']),
          '%.0f MPa' % p_o)
    # ------------------------------------------------------------------ hot joints
    print('4. hot joints, 16 x M10 IN718 studs')
    st = G.STUD; As = 61.2                                     # MJ10x1.25 stress area [mm2]
    Fs = st['pre_kN'] * 1e3; F_hot = st['n'] * Fs
    hot = {}
    for j, T_j in (('drum_R1', 480.0), ('R1_R2', 500.0), ('R2_stub', 460.0)):
        # grip: the two flanges; R1 - R2 (rev 6) also the IN718 spacer ring (no mismatch with the IN718 studs over its length)
        L_spc = G.L_TSPC if j == 'R1_R2' else 0.0
        Lg = 2 * G.ARM['tf'] + L_spc; Lst = Lg + 0.8 * st['d']; ks = mp('IN718', 'E', 500) * As / Lst
        kf = 3.0 * ks
        dmis = (mp('IN718', 'a', T_j) - 0.5 * (mp('IN718', 'a', T_j) + mp('MAR-M247', 'a', T_j))) * (T_j - 20) * Lg
        if j == 'R1_R2': dmis = (mp('IN718', 'a', T_j) - mp('MAR-M247', 'a', T_j)) * (T_j - 20) * (Lg - L_spc)
        dF_ss = -dmis / (1 / ks + 1 / kf)
        dF_tr = -(mp('IN718', 'a', T_j) * 60.0 * Lg) / (1 / ks + 1 / kf)            # studs 60 K hotter than the flanges
        relax = 0.10 * Fs                                         # IN718 stress relaxation at ~500 C over 30,000 h (re-torque at HSI)
        F_min_s = Fs + min(0.0, dF_ss) + dF_tr - relax
        M = max(gravity_moment(x) for x in ((G.X_J['R1_spc'], G.X_J['spc_R2']) if j == 'R1_R2' else (xjoint[j],)))
        F_r, br = curvic_ring_clamp(G.CURVIC_HOT['ri'], G.CURVIC_HOT['ro'], M, tq_max[j], max(0.0, fax[j]))
        x0s, x1s = G.STUD_SETS[dict(drum_R1='drum - R1', R1_R2='R1 - R2', R2_stub='R2 - rear stub')[j]][:2]
        hot[j] = dict(T=T_j, grip_mm=Lg, stud_mm=x1s - x0s,
                      dF_steady_N=dF_ss, dF_transient_N=dF_tr, F_min_total=F_min_s * st['n'], required=F_r, parts=br,
                      stud_stress=(Fs + max(0.0, dF_ss)) / As, flank=curvic_flank_pressure(F_hot, tq_max[j], G.CURVIC_HOT['ri'], G.CURVIC_HOT['ro'],
                                                                                         G.CURVIC_HOT['N']))
        print('   %-8s %3.0f C: stud %.0f mm (grip %.0f), preload %.0f kN, thermal %+.1f / transient %+.1f kN per stud; min clamp %.0f kN '
              'vs required %.0f kN; stud %.0f MPa; flank %.0f MPa' % (j, T_j, x1s - x0s, Lg, Fs / 1e3, dF_ss / 1e3, dF_tr / 1e3,
                                                                     F_min_s * st['n'] / 1e3, F_r / 1e3, hot[j]['stud_stress'], hot[j]['flank']))
        check('hot joint %s: min clamp / required' % j, F_min_s * st['n'] / F_r, 1.25, '-', F_min_s * st['n'] / F_r >= 1.25,
              'after 10 % relaxation and a 60 K stud lag')
    check('hot studs: stress / 0.7 Sy(500 C)', max(v['stud_stress'] for v in hot.values()) / (0.7 * mp('IN718', 'Sy', 500)), 1.0, '-',
          max(v['stud_stress'] for v in hot.values()) <= 0.7 * mp('IN718', 'Sy', 500), 'MJ10x1.25, %.0f kN' % (Fs / 1e3))
    res['hot_joints'] = dict(stud=st, curvic=G.CURVIC_HOT, joints=hot, x=G.X_J)
    # ------------------------------------------------------------------ disc FEA with arms
    print('5. blisks with cast arms: axisymmetric FEA (CalculiX)')
    fea = disc_fea()
    res['disc_fea_arms'] = fea
    for row in ('R1', 'R2'):
        op, tr = fea['%s_op' % row], fea['%s_trip' % row]
        check('%s disc+arms yield margin (trip)' % row, tr['margin_yield'], 1.0, '-', tr['margin_yield'] >= 1.0, 'vm %.0f MPa' % tr['vm_max'])
        check('%s disc+arms burst / 15k' % row, op['burst_ratio'], 1.342, 'x', op['burst_ratio'] >= 1.342, '')
        for lab, sv, Tt, kt in (('hub peak', op['vm_hub'], op['T_hub'], 1.0), ('arm root', op['vm_arm'], op['T_arm'], 1.0),
                                ('flange stud hole', op['hoop_flange_studs'], op['T_flange'], KT_HOLE)):
            s = abs(sv) * kt; de = s / lin(Tt, TC.MAT_T, TC.MAT_E); Nl = TC.manson_cycles(de, Tt, s)
            op['lcf_' + lab.replace(' ', '_')] = dict(s=s, T=Tt, cycles=Nl)
            check('%s LCF starts (%s)' % (row, lab), Nl, TC.STARTS_REQ, 'cyc', Nl >= TC.STARTS_REQ, '%.0f MPa%s @ %.0f C' % (s, ' (Kt %.1f)' % kt if kt > 1 else '', Tt))
    # ------------------------------------------------------------------ bearings
    print('6. bearings')
    sfd = sfd_cage()
    Rd = detailed_rotor(None)
    W1, W2, xcg = RD.journal_loads(Rd)
    U_api = [6350 * w / RD.N_MCS for w in (W1, W2)]                       # g mm
    Fdyn = [4 * u * 1e-6 * OM ** 2 for u in U_api]                        # 4 x API residual unbalance, N
    jb = [journal(W1 * 9.81 + Fdyn[0]), journal(W2 * 9.81 + Fdyn[1])]
    tb = thrust_bearing(W_thr * 1.5)
    tb_d = thrust_bearing(abs(F_net))
    tb_f = thrust_bearing(abs(F_lost))
    for i, b in enumerate(jb):
        print('   journal %d: W %.0f N, %.2f MPa, U %.0f m/s, h_min %.0f um, Cb %.0f um, Re %.0f, K %.2e N/m, loss %.1f kW, oil %.0f l/min' % (
            i + 1, b['W'], b['unit_load_MPa'], b['U'], b['h_min_um'], b['Cb_um'], b['Re'], b['K'], b['P_kW'], b['Q_lpm']))
    print('   thrust (design %.1f kN, sized for %.1f kN): %.2f MPa, U %.0f m/s, h_min %.0f um, Re %.0f, loss %.1f kW (design point), oil %.0f l/min' % (
        abs(F_net) / 1e3, W_thr * 1.5 / 1e3, tb['unit_load_MPa'], tb['U_mean'], tb['h_min_um'], tb['Re'], tb_d['P_kW'], tb_d['Q_lpm']))
    check('thrust bearing unit load at 1.5 x max thrust', tb['unit_load_MPa'], 2.0, 'MPa', tb['unit_load_MPa'] <= 2.0, '%d pads r %.0f-%.0f' % (tb['n'], tb['ri'], tb['ro']))
    check('thrust bearing min film at 1.5 x max thrust', tb['h_min_um'], 20.0, 'um', tb['h_min_um'] >= 20.0, '')
    print('   back-face feed lost: %.1f kN -> %.2f MPa, h_min %.0f um; inactive side %d pads, %.1f kN at 2 MPa (reverse)' % (
        abs(F_lost) / 1e3, tb_f['unit_load_MPa'], tb_f['h_min_um'], tb_f['n_in'], tb_f['cap_reverse_kN']))
    check('thrust bearing unit load, back-face feed lost', tb_f['unit_load_MPa'], 3.5, 'MPa', tb_f['unit_load_MPa'] <= 3.5,
          '%.1f kN, failure case (trip, no 1.5 x)' % (abs(F_lost) / 1e3))
    check('thrust bearing min film, back-face feed lost', tb_f['h_min_um'], 10.0, 'um', tb_f['h_min_um'] >= 10.0, '')
    for i, b in enumerate(jb):
        check('journal %d min film' % (i + 1), b['h_min_um'], 25.0, 'um', b['h_min_um'] >= 25.0, '%.2f MPa' % b['unit_load_MPa'])
    # squeeze-film damper + integral S-springs
    orbit = 0.8 * G.SFD['c'] * 1e-3
    cs = [cage_stress(sfd, w * 9.81, orbit) for w in (W1, W2)]
    s_cage = max(c['s_alt_MPa'] for c in cs)
    check('ISFD spring alternating stress / endurance (17-4PH H1100, 500 MPa / 2)', s_cage / 250.0, 1.0, '-', s_cage <= 250.0,
          'orbit 80 %% of the damper clearance, %d springs t %.1f l %.0f mm' % (G.ISFD['n'], G.ISFD['t'], G.ISFD['l']))
    print('   SFD R %.0f L %.0f c %.2f: C %.2e (full film) / %.2e (pi film) Ns/m; ISFD k %.2e N/m, sag %.0f / %.0f um, spring stress %.0f MPa alt' % (
        G.SFD['R'], G.SFD['L'], G.SFD['c'], sfd['C_full'], sfd['C_pi'], sfd['k'], cs[0]['sag_um'], cs[1]['sag_um'], s_cage))
    res['bearings'] = dict(journal=jb, thrust_sized=tb, thrust_design=tb_d, thrust_feed_lost=tb_f, sfd=sfd, cage=cs, journal_loads_kg=[W1, W2],
                           U_api_gmm=U_api)
    # ------------------------------------------------------------------ rotor dynamics of the detailed stack
    print('   rotor dynamics (detailed stack, bearing K from the pad model, SFD + cage)')
    sup = dict(kb=0.5 * (jb[0]['K'] + jb[1]['K']), cb=0.5 * (jb[0]['C'] + jb[1]['C']), ks=sfd['k'], cs=sfd['C_full'], mh=6.0)
    sup_lo = dict(sup, cs=sfd['C_pi'])
    rd = {}
    for name, sp in (('nominal', sup), ('pi-film SFD', sup_lo)):
        dc = RD.damped_criticals(Rd, sp)
        cases = dict(mid=[(xcg, 0.0, W1 + W2)], conical=[(Rd['discs']['impeller1']['x'], 0.0, W1), (Rd['discs']['blisk2']['x'], math.pi, W2)],
                     turbine=[(Rd['discs']['blisk2']['x'], 0.0, 2 * W2)])
        fine = np.arange(500, 20001, 100.0)
        ub, U, _ = RD.unbalance(Rd, sp, fine, cases)
        amp = {c: float(a[(fine >= 0.95 * N_OP) & (fine <= N_TRIP)].max()) for c, a in ub.items()}
        rd[name] = dict(support=sp, criticals=dc, amp_um=amp, rotor_mass=RD.rotor_mass(Rd))
        print('   %-12s rotor %.0f kg; criticals %s; journal vibration %s um (API limit %.0f)' % (
            name, RD.rotor_mass(Rd), ', '.join('%.0f rpm (AF %.1f, SM %.0f %% / req %.0f %%)' % (c['N'], c['AF'], c['SM'], c['SM_req']) for c in dc),
            '/'.join('%.1f' % v for v in amp.values()), RD.API_LIM))
        for c in dc:
            check('critical %.0f rpm (%s): separation margin' % (c['N'], name), c['SM'], c['SM_req'], '%', c['ok'], 'AF %.1f, log dec %.2f' % (c['AF'], c['logdec']))
        check('API unbalance response (%s)' % name, max(amp.values()), RD.API_LIM, 'um', max(amp.values()) <= RD.API_LIM, 'pk-pk at the journals')
    res['rotordynamics'] = rd
    res['rotor_segments'] = Rd['seg']
    # ------------------------------------------------------------------ losses
    P_brg = jb[0]['P_kW'] + jb[1]['P_kW'] + tb_d['P_kW']
    P_seal = 2.0                                                          # oil / air labyrinth windage (estimate)
    allowance = (1 - 0.994) * (P_t1 + P_t2 - P_c1 - P_c2) / 1e3
    res['losses'] = dict(journals_kW=jb[0]['P_kW'] + jb[1]['P_kW'], thrust_kW=tb_d['P_kW'], seals_kW=P_seal, total_kW=P_brg + P_seal,
                         cycle_allowance_kW=allowance, oil_lpm=jb[0]['Q_lpm'] + jb[1]['Q_lpm'] + tb_d['Q_lpm'],
                         d_eta_el_pt=-(P_brg + P_seal - allowance) * 0.97 * 0.985 / ML['cchp']['fuel_kW'] * 100)
    print('7. bearing + seal losses %.1f kW (journals %.1f, thrust %.1f) vs cycle allowance (eta_mech 0.994) %.1f kW -> %.2f pt electrical '
          'efficiency; oil flow %.0f l/min' % (P_brg + P_seal, res['losses']['journals_kW'], tb_d['P_kW'], allowance, res['losses']['d_eta_el_pt'],
                                               res['losses']['oil_lpm']))
    # ------------------------------------------------------------------ interfaces for the impeller design
    res['interfaces'] = dict(
        frame='rotor frame of sim/engine/a1000_rotordynamics.py, mm',
        impeller1=dict(x_front=G.X_I1[0], x_rear=G.X_I1[1], bore=G.BORE_IMP, curvic_front=G.CURVIC_C['stub_I1'], curvic_rear=G.CURVIC_C['I1_spc']),
        impeller2=dict(x_front=G.X_I2[0], x_rear=G.X_I2[1], bore=G.BORE_IMP, curvic_front=G.CURVIC_C['spc_I2'], curvic_rear=G.CURVIC_C['I2_drum']),
        clamp_kN=dict(assembly=Fpre / 1e3, min=F_min / 1e3, max=F_max / 1e3), torque_Nm=dict(I1=tq['stub_I1'], I2=tq['spc_I2'],
                                                                                            short_circuit_factor=5.0),
        tie_bolt='M42x3 IN718, shank %.0f mm, lands %.1f mm at x %s' % (G.TIE['shank'], G.TIE['land'], list(G.TIE['lands'])),
        blisk_arms=dict(ri=G.ARM['ri'], ro=G.ARM['ro'], flange_od=2 * G.ARM['rf'], flange_t=G.ARM['tf'], cavity=G.ARM['cav'], joints_x=G.X_J,
                        studs='16 x MJ10x1.25 IN718 on PCD %.0f' % (2 * G.STUD['r'])))
    json.dump(res, open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json'), 'w'), indent=1, default=float)   # read by the transient
    # ------------------------------------------------------------------ transient thrust
    print('8. transient axial thrust (sim/engine/a1000_thrust_transient.py)')
    import a1000_thrust_transient as TT                      # noqa: E402
    tr = TT.main()
    for c in tr['checks']:
        check(c['test'], c['value'], c['limit'], c['unit'], c['ok'], c['note'])
    res['thrust_transient'] = dict(worst=tr['worst'], bound=tr['bound'], bov=tr['bov'], results='sim/engine/fea/a1000_thrust_transient.json')
    n_ok = sum(c['ok'] for c in chk)
    print('checks: %d of %d pass' % (n_ok, len(chk)))
    json.dump(res, open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json'), 'w'), indent=1, default=float)
    plot(res, Rd)


def plot(res, Rd):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle
    fig = plt.figure(figsize=(16, 11), dpi=110)
    ax = fig.add_axes([0.04, 0.47, 0.92, 0.48])
    col = {'RT-101': '#9aa4b2', 'RT-102': '#c9a227', 'RT-103': '#c9a227', 'RT-104': '#9aa4b2', 'RT-105': '#b07aa1', 'RT-106': '#9aa4b2',
           'RT-107': '#b07aa1'}
    for name, f, mat, rho in G.ROTOR_PARTS:
        p = f(); c = col[name[:6]]
        for sg in (1, -1):
            ax.add_patch(Polygon([(x, sg * r) for x, r in p], closed=True, fc=c, ec='k', lw=0.5, alpha=0.95))
        ax.text(G.poly_area_props(p)[1], max(r for _, r in p) + 6, name.split(' ', 1)[1].replace(' + ', '\n+ '), ha='center', fontsize=6.5)
    for row in ('R1', 'R2'):
        p = G.disc_profile_arms(row)
        for sg in (1, -1):
            ax.add_patch(Polygon([(x, sg * r) for x, r in p], closed=True, fc='#e59a7f', ec='k', lw=0.5))
        ax.text(G.HUB[row][0] + 28, 262, 'blisk %s\n(cast arms + flanges)' % row, ha='center', fontsize=7)
    for row in ('R1', 'R2'):
        rh, rt = A.row_radius(row, 0.0), A.row_radius(row, 1.0); xl = A.X_LE[row] + G.X_OFF; xt = A.X_TE[row] + G.X_OFF
        for sg in (1, -1): ax.add_patch(Rectangle((xl, sg * rh if sg > 0 else -rt), xt - xl, rt - rh, fc='#d0d4dc', ec='k', lw=0.4))
    for k, d in Rd['discs'].items():
        if k.startswith('impeller'):
            for sg in (1, -1): ax.add_patch(Polygon([(x, sg * r) for x, r in RD.rotor('A')['discs'][k]['poly']], fc='#7fb2e5', ec='k', lw=0.4, alpha=0.6))
    for x in G.X_J.values():
        for sg in (1, -1): ax.plot([x, x], [sg * 60, sg * 92], color='r', lw=1.0)
    for xb in G.X_BRG:
        for sg in (1, -1):
            R_j = G.JOURNAL['D'] / 2
            ax.add_patch(Rectangle((xb - G.JOURNAL['L'] / 2, sg * R_j if sg > 0 else -R_j - 10), G.JOURNAL['L'], 10, fc='#2e7d32', ec='k', lw=0.5))
            ax.add_patch(Rectangle((xb - G.SFD['L'] / 2, sg * 74 if sg > 0 else -80), G.SFD['L'], 6, fc='#f9a825', ec='k', lw=0.5))
    for sg in (1, -1):
        ax.add_patch(Rectangle((G.COLLAR['x0'] - 14, sg * G.THRUST['ri'] if sg > 0 else -G.THRUST['ro']), 14, G.THRUST['ro'] - G.THRUST['ri'], fc='#2e7d32', ec='k', lw=0.5))
        ax.add_patch(Rectangle((G.COLLAR['x1'], sg * G.THRUST['ri'] if sg > 0 else -G.THRUST['ro']), 14, G.THRUST['ro'] - G.THRUST['ri'], fc='#2e7d32', ec='k', lw=0.5))
    ax.axhline(0, color='k', lw=0.4, ls='-.')
    ax.set_xlim(-20, 1000); ax.set_ylim(-280, 290); ax.set_aspect('equal'); ax.set_xlabel('x [mm] (rotor frame)')
    ax.set_title('AURORA-1000 rotor rev 1 (to scale): compressor stack on one M42 tie bolt; blisks joined by cast arm flanges + 16 x M10 '
                 'studs (red: joints); journals (green) in ISFD damper rings (yellow); thrust bearing on the integral collar', fontsize=9.5)
    # thrust bars
    ax2 = fig.add_axes([0.05, 0.07, 0.36, 0.33])
    fp = res['thrust']['parts']; ks = list(fp.keys()); vs = [fp[k] / 1e3 for k in ks]
    ax2.barh(range(len(ks)), vs, color=['tab:red' if v > 0 else 'tab:blue' for v in vs])
    ax2.set_yticks(range(len(ks))); ax2.set_yticklabels(ks, fontsize=7); ax2.axvline(0, color='k', lw=0.6)
    ax2.set_xlabel('axial force on the rotor [kN] (+ aft)'); ax2.grid(alpha=0.3)
    ax2.set_title('Axial thrust at 15,000 rpm: net %.1f kN (balance seal r %.0f mm)' % (res['thrust']['net'] / 1e3, res['thrust']['balance_seal_r']), fontsize=9)
    ax3 = fig.add_axes([0.47, 0.07, 0.18, 0.33])
    st = res['tie_bolt']['states']; ax3.bar(range(len(st)), [v / 1e3 for v in st.values()], color='tab:olive')
    ax3.axhline(res['tie_bolt']['F_req'] / 1e3, color='r', lw=1, label='required clamp')
    ax3.set_xticks(range(len(st))); ax3.set_xticklabels([k.split(' (')[0] for k in st], rotation=35, ha='right', fontsize=7)
    ax3.set_ylabel('tie-bolt preload [kN]'); ax3.legend(fontsize=7); ax3.grid(alpha=0.3)
    ax3.set_title('Tie bolt through the transients', fontsize=9)
    ax4 = fig.add_axes([0.69, 0.03, 0.30, 0.40]); ax4.axis('off')
    rows = [(c['test'][:46], '%.3g %s' % (c['value'], c['unit']), 'OK' if c['ok'] else 'FAIL') for c in res['checks']]
    tbl = ax4.table(cellText=rows, colLabels=['check', 'value', ''], cellLoc='left', colWidths=[0.70, 0.20, 0.10], bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False); tbl.set_fontsize(min(6.2, 6.2 * 36 / len(rows)))
    for (i, j), cell in tbl.get_celld().items():
        if i > 0 and j == 2: cell.set_facecolor('#c8e6c9' if rows[i - 1][2] == 'OK' else '#ffcdd2')
    ax4.set_title('Checks: %d of %d pass' % (sum(c['ok'] for c in res['checks']), len(res['checks'])), fontsize=9)
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_rotor_stack.png')); print('written docs/img/a1000_rotor_stack.png')


if __name__ == '__main__':
    main()
