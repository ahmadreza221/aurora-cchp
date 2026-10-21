# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib"]
# ///
"""GR180 0-D cycle model: turbojet matching from the CAD flow areas + generator variants.

Run:  uv run sim/gr180_cycle.py            (or: python3 sim/gr180_cycle.py  -> no plots)

Matching (classic gas-generator approach):
  * compressor: pressure ratio PR, efficiency eta_c  -> T2, specific work w_c
  * NGV sets the mass flow: Euler work with axial exit  w_t = U_m * C1_theta,
    C1 = C1_theta / sin(alpha1), alpha1 = acos(A_throat / A_annulus)  ->  mdot = rho1 * C1 * A_throat
  * propelling nozzle (A9) must swallow the same flow at (P4, T4)
  -> for each PR the TIT that satisfies both is found by bisection; PR is then chosen so that
     thrust = 176.5 N (README design value). Everything not measured from the CAD is an ASSUMPTION (see A dict).
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# ------------------------------------------------------------------ constants
R_AIR, CP_A, G_A = 287.0, 1005.0, 1.40
CP_G, G_G = 1148.0, 1.333
R_G = CP_G * (G_G - 1) / G_G
LHV_CH4 = 50.0e6           # J/kg methane
RHO_N_CH4 = 0.717          # kg/Nm3
T_AMB, P_AMB = 288.15, 101325.0

# ------------------------------------------------------------------ geometry (CAD v12; overwritten by measure_geometry.py output)
G = {
    'N_rpm': 120000.0,
    'D2_comp': 74.0e-3,                       # compressor tip
    'r_ind_tip': 27.8e-3, 'r_ind_hub': 8.95e-3,  # inducer LE (tip 0.3 inside the Ø56.2 shroud, hub = nose Ø17.9)
    'b2': 6.48e-3, 'b_diff': 7.0e-3,          # impeller exit width (GR180 Compressor.pdf: 6.48, rim 1.2) vs diffuser passage 7.0
    'r_t_hub': 22.1e-3, 'r_t_tip': 35.15e-3,  # turbine blade root / tip
    'A_ngv_ann': math.pi * (35.25**2 - 22.25**2) * 1e-6,
    'A_ngv_throat': None,                     # measured -> else from assumed 68 deg exit angle
    'A9': math.pi / 4 * 55.4**2 * 1e-6,       # nozzle exit Ø55.4 (inner cone ends 13.6 mm upstream)
}
mfile = os.path.join(HERE, 'geometry_measured.json')
if os.path.exists(mfile):
    m = json.load(open(mfile))
    G['A_ngv_throat'] = m['NGV']['throat_area_mm2'] * 1e-6
    G['A_rot_throat'] = m['Turbine']['throat_area_mm2'] * 1e-6
    d = [r for r in m['Diffuser']['rows'] if r.get('o_min')]
    if d: G['A_diff_throat'] = len(m['Diffuser']['rows']) and d[0]['n'] * d[0]['o_min'] * m['Diffuser']['passage_height_mm'] * 1e-6
    G['measured'] = True
if not G.get('A_ngv_throat'):
    G['A_ngv_throat'] = G['A_ngv_ann'] * math.cos(math.radians(66.0))
    G['measured'] = False

# ------------------------------------------------------------------ assumptions (all editable)
A = {
    'eta_c': 0.72,      # compressor total-to-total incl. vaned diffuser (turned-down Schwitzer wheel)
    'dp_in': 0.01,      # bellmouth/intake total-pressure loss
    'dp_cc': 0.06,      # combustor (liner hole area ~2230 mm2, Cd 0.6 -> ~6 %)
    'eta_b': 0.95,      # combustion efficiency (gas in vaporiser sticks)
    'eta_ngv': 0.94,    # NGV kinetic-energy efficiency
    'eta_t': 0.80,      # turbine total-to-total
    'eta_m': 0.98,      # bearings/windage
    'dp_exh': 0.02,     # turbine-exit cone + 3 struts
    'eta_n': 0.95, 'cd_n': 0.97,
    'thrust_target': 176.5,
}

def U(r): return G['N_rpm'] * 2 * math.pi / 60 * r

def nozzle_flow(A, Pt, Tt, Pa, R, g):
    if Pt <= Pa: return 0.0, 1.0
    pr = max(Pa / Pt, (2 / (g + 1)) ** (g / (g - 1)))
    return A * Pt / math.sqrt(R * Tt) * math.sqrt(2 * g / (g - 1) * (pr ** (2 / g) - pr ** ((g + 1) / g))), pr

def gas_generator(PR, T3, a=A, w_extra=0.0):
    """Gas-generator state for compressor PR and TIT T3. w_extra = additional shaft work per kg AIR (single-shaft gen)."""
    T1, P1 = T_AMB, P_AMB * (1 - a['dp_in'])
    T2 = T1 * (1 + (PR ** ((G_A - 1) / G_A) - 1) / a['eta_c'])
    P2 = P1 * PR
    w_c = CP_A * (T2 - T1)
    P3 = P2 * (1 - a['dp_cc'])
    f = CP_G * (T3 - T2) / (a['eta_b'] * LHV_CH4)
    w_t = (w_c / a['eta_m'] + w_extra) / (1 + f)          # per kg gas
    T4 = T3 - w_t / CP_G
    T4s = T3 - w_t / (CP_G * a['eta_t'])
    P4 = P3 * (T4s / T3) ** (G_G / (G_G - 1))
    # NGV: Euler with axial exit at mean radius
    r_m = math.sqrt((G['r_t_hub']**2 + G['r_t_tip']**2) / 2)
    Um = U(r_m)
    alpha1 = math.acos(G['A_ngv_throat'] / G['A_ngv_ann'])
    C1 = w_t / Um / math.sin(alpha1)
    T1n = T3 - C1**2 / (2 * CP_G)
    T1ns = T3 - C1**2 / (2 * CP_G * a['eta_ngv'])
    P1n = P3 * (T1ns / T3) ** (G_G / (G_G - 1))
    M1 = C1 / math.sqrt(G_G * R_G * T1n)
    mg = P1n / (R_G * T1n) * C1 * G['A_ngv_throat']
    if M1 > 1:   # NGV choked -> flow capacity limit
        mg = G['A_ngv_throat'] * P3 / math.sqrt(T3) * math.sqrt(G_G / R_G) * (2 / (G_G + 1)) ** ((G_G + 1) / (2 * (G_G - 1)))
    return dict(PR=PR, T1=T1, T2=T2, P2=P2, w_c=w_c, P3=P3, T3=T3, f=f, w_t=w_t, T4=T4, P4=P4, Um=Um,
                alpha1=math.degrees(alpha1), C1=C1, M_ngv=M1, mg=mg, ma=mg / (1 + f), psi=w_t / Um**2)

def match_turbojet(PR, a=A):
    """TIT at which NGV flow == nozzle flow (both carry the same gas mass flow)."""
    def resid(T3):
        s = gas_generator(PR, T3, a)
        mn, _ = nozzle_flow(G['A9'] * a['cd_n'], s['P4'] * (1 - a['dp_exh']), s['T4'], P_AMB, R_G, G_G)
        return s['mg'] - mn
    lo, hi = 700.0, 1600.0
    if resid(lo) * resid(hi) > 0: return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if resid(lo) * resid(mid) <= 0: hi = mid
        else: lo = mid
    s = gas_generator(PR, 0.5 * (lo + hi), a)
    P4n = s['P4'] * (1 - a['dp_exh'])
    _, pr = nozzle_flow(G['A9'], P4n, s['T4'], P_AMB, R_G, G_G)
    V9 = math.sqrt(2 * CP_G * a['eta_n'] * s['T4'] * (1 - pr ** ((G_G - 1) / G_G)))
    P9 = P4n * pr
    F = s['mg'] * V9 + (P9 - P_AMB) * G['A9']
    s.update(V9=V9, F=F, mf=s['ma'] * s['f'], P4n=P4n)
    return s

def calibrate(a=A):
    """PR (and operating point) that gives the README thrust with the CAD flow areas."""
    f = lambda PR: (match_turbojet(PR, a) or {'F': float('nan')})['F'] - a['thrust_target']
    grid = [1.6 + 0.02 * k for k in range(146)]
    vals = [f(p) for p in grid]
    br = [(grid[i], grid[i + 1]) for i in range(len(grid) - 1) if vals[i] == vals[i] and vals[i + 1] == vals[i + 1] and vals[i] * vals[i + 1] <= 0]
    if not br: raise RuntimeError('thrust target not reachable with this geometry/assumptions')
    lo, hi = br[0]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
    return match_turbojet(0.5 * (lo + hi), a)

def compressor_checks(s):
    U2 = U(G['D2_comp'] / 2)
    mu = s['w_c'] / U2**2                                   # work input coefficient (slip+backsweep+parasitic)
    A1 = math.pi * (G['r_ind_tip']**2 - G['r_ind_hub']**2) * 0.92   # 8 % blade blockage
    rho1 = P_AMB / (R_AIR * T_AMB); cx = 0
    for _ in range(20):
        cx = s['ma'] / (rho1 * A1); T = T_AMB - cx**2 / (2 * CP_A); rho1 = P_AMB * (T / T_AMB) ** 3.5 / (R_AIR * T)
    Wt = math.hypot(cx, U(G['r_ind_tip']))
    # impeller exit: radial velocity needed to pass the flow through b2 (8 % blockage), flow coefficient phi2 = Cr2/U2
    T2t, P2t = s['T2'], s['P2']; A2 = 2 * math.pi * G['D2_comp'] / 2 * G['b2'] * 0.92
    Ct2 = s['w_c'] / U2                                        # Euler: tangential exit velocity from the work
    def flux(Cr):
        T2s = T2t - (Cr**2 + Ct2**2) / (2 * CP_A)
        if T2s <= 50: return 0.0
        return P2t * (T2s / T2t) ** 3.5 / (R_AIR * T2s) * 0.95 * Cr * A2
    Cr2, peak = None, 0.0
    for k in range(1, 800):
        fl = flux(k); peak = max(peak, fl)
        if fl >= s['ma']: Cr2 = float(k); break
    out = dict(U2=U2, mu=mu, cx1=cx, M_rel_tip=Wt / math.sqrt(G_A * R_AIR * T), diff_width_ratio=G['b_diff'] / G['b2'],
               Cr2=Cr2, phi2=(Cr2 / U2) if Cr2 else None, mdot_max_b2=peak, mdot_at_phi03=flux(0.3 * U2))
    if G.get('A_diff_throat'):   # vaned-diffuser throat Mach (static ~ P2 - 15 %, T ~ T2 - 25 K)
        Tth = T2t - 25; rho = 0.85 * P2t / (R_AIR * Tth); Vth = s['ma'] / (rho * G['A_diff_throat'] * 0.95)
        out.update(A_diff=G['A_diff_throat'], M_diff=Vth / math.sqrt(G_A * R_AIR * Tth))
    return out

# ------------------------------------------------------------------ generator variants
def chain(P_shaft, gear_stages):
    eta_gb = 0.975 ** gear_stages
    eta_gen, eta_pe = 0.94, 0.955
    return P_shaft * eta_gb * eta_gen * eta_pe, eta_gb * eta_gen * eta_pe

def free_power_turbine(s, eta_ts=0.72, dp_duct=0.02, P_exit=P_AMB):
    """Gas generator unchanged (FPT NGV area chosen = old nozzle -> same P4, T4). Expansion to ambient static."""
    P4 = s['P4n'] * (1 - dp_duct)
    dh_is = CP_G * s['T4'] * (1 - (P_exit / P4) ** ((G_G - 1) / G_G))
    w = eta_ts * dh_is
    T5 = s['T4'] - w / CP_G
    return dict(P_shaft=s['mg'] * w, dh_is=dh_is, T5=T5, C0=math.sqrt(2 * dh_is))

def single_shaft(PR, T3, ma, eta_t=0.76, dp_exh_diff=0.03, a=A):
    """One turbine drives compressor + generator, exhaust diffused to ambient (no thrust). Same PR, TIT, air flow."""
    s = gas_generator(PR, T3, a)
    P_exit = P_AMB * (1 + dp_exh_diff)
    dh_is = CP_G * T3 * (1 - (P_exit / s['P3']) ** ((G_G - 1) / G_G))
    w_t = eta_t * dh_is
    w_net = w_t * (1 + s['f']) * a['eta_m'] - s['w_c']    # per kg air
    return dict(P_shaft=ma * w_net, psi=w_t / s['Um']**2, T4=T3 - w_t / CP_G, w_t=w_t)

def recuperated_fpt(s, eps=0.85, dp_rec=0.03, eta_ts=0.72):
    """FPT + recuperator: exhaust preheats compressor delivery air; same TIT and air flow, recuperator dp both sides."""
    T2, T3, ma = s['T2'], s['T3'], s['ma']
    T5 = s['T4'] - 50
    for _ in range(30):
        T2r = T2 + eps * (T5 - T2)
        f = CP_G * (T3 - T2r) / (A['eta_b'] * LHV_CH4)
        # extra cold-side loss lowers P3/P4 roughly by dp_rec, hot side raises FPT back-pressure
        P4 = s['P4n'] * (1 - dp_rec) * (1 - 0.02)
        dh_is = CP_G * s['T4'] * (1 - (P_AMB * (1 + dp_rec) / P4) ** ((G_G - 1) / G_G))
        w = eta_ts * dh_is
        T5 = s['T4'] - w / CP_G
    mf = ma * f
    return dict(P_shaft=ma * (1 + f) * w, mf=mf, T2r=T2r, T_stack=T5 - (T2r - T2) * CP_A / CP_G)

# ------------------------------------------------------------------ report
def fmt_pt(s):
    return ('PR %.2f | air %.3f kg/s | TIT %.0f K (%.0f C) | EGT(T4) %.0f K (%.0f C) | P4 %.2f bar | thrust %.1f N | '
            'CH4 %.2f g/s = %.1f Nm3/h | fuel power %.0f kW' % (
             s['PR'], s['ma'], s['T3'], s['T3'] - 273.15, s['T4'], s['T4'] - 273.15, s['P4'] / 1e5, s['F'],
             s['mf'] * 1e3, s['mf'] * 3600 / RHO_N_CH4, s['mf'] * LHV_CH4 / 1e3))

def main():
    out = {}
    print('=' * 100)
    print('GR180 cycle model  (geometry %s)' % ('MEASURED from CAD' if G['measured'] else 'ASSUMED'))
    print('NGV throat %.0f mm2 of annulus %.0f mm2 -> exit angle %.1f deg ; nozzle A9 %.0f mm2' % (
        G['A_ngv_throat'] * 1e6, G['A_ngv_ann'] * 1e6, math.degrees(math.acos(G['A_ngv_throat'] / G['A_ngv_ann'])), G['A9'] * 1e6))
    print('-' * 100)
    print('1) TURBOJET operating point that gives 176.5 N with this NGV/nozzle (eta_c sensitivity):')
    base = None
    for ec in (0.68, 0.72, 0.76):
        a = dict(A, eta_c=ec)
        s = calibrate(a); c = compressor_checks(s)
        print('  eta_c %.2f: %s' % (ec, fmt_pt(s)))
        print('             work coeff mu=%.2f (U2 %.0f m/s) | inducer tip rel. Mach %.2f | NGV exit Mach %.2f, alpha1 %.1f | turbine psi %.2f'
              % (c['mu'], c['U2'], c['M_rel_tip'], s['M_ngv'], s['alpha1'], s['psi']))
        if ec == A['eta_c']: base, cb = s, c
    out['turbojet'] = base
    print('  -> diffuser passage / impeller exit width = %.1f / %.1f = %.2f  (design rule ~1.0-1.15)' % (G['b_diff'] * 1e3, G['b2'] * 1e3, cb['diff_width_ratio']))
    if cb['Cr2']:
        print('  -> impeller exit radial velocity Cr2 = %.0f m/s, phi2 = %.2f (normal 0.25-0.35)' % (cb['Cr2'], cb['phi2']))
    else:
        print('  -> impeller exit b2=%.1f mm CANNOT pass %.0f g/s (exit choke at ~%.0f g/s)' % (G['b2'] * 1e3, cb.get('ma', 0) or 0, cb['mdot_max_b2'] * 1e3))
    print('  -> with b2=%.1f mm the flow at a normal phi2=0.3 is only ~%.0f g/s; b2 needed for %.0f g/s at phi2 0.3: ~%.1f mm'
          % (G['b2'] * 1e3, cb['mdot_at_phi03'] * 1e3, base['ma'] * 1e3, G['b2'] * 1e3 * base['ma'] / cb['mdot_at_phi03']))
    if 'M_diff' in cb:
        print('  -> vaned-diffuser throat %.0f mm2 (13 x o x 7.0): throat Mach ~%.2f (keep < 0.8)' % (cb['A_diff'] * 1e6, cb['M_diff']))
    print('-' * 100)
    print('2) FREE POWER TURBINE (gas generator unchanged) + gearbox + generator:')
    rows = []
    for eta in (0.60, 0.70, 0.78):
        p = free_power_turbine(base, eta_ts=eta)
        for stages, label in ((0, 'direct high-speed PMG'), (2, '2-stage gearbox -> 3000 rpm')):
            Pel, ech = chain(p['P_shaft'], stages)
            eff = Pel / (base['mf'] * LHV_CH4)
            rows.append((eta, label, p['P_shaft'], Pel, eff))
            print('  eta_FPT %.2f  %-30s shaft %5.1f kW -> electric %5.1f kW  | electrical efficiency %4.1f %%  | FPT exit %.0f C'
                  % (eta, label, p['P_shaft'] / 1e3, Pel / 1e3, eff * 100, p['T5'] - 273.15))
    p = free_power_turbine(base, eta_ts=0.70)
    print('  FPT speed for U/C0 = 0.60 (C0 = %.0f m/s):' % p['C0'])
    for Dm in (60, 70, 80, 90):
        n = 0.60 * p['C0'] / (math.pi * Dm * 1e-3) * 60
        print('     mean Ø%d mm -> %6.0f rpm | ratio to 3000 rpm %5.1f:1, to 24000 rpm %4.1f:1' % (Dm, n, n / 3000, n / 24000))
    out['fpt'] = rows
    print('-' * 100)
    print('3) SINGLE SHAFT (power taken from the compressor shaft, nozzle replaced by exhaust diffuser):')
    for et in (0.72, 0.76, 0.80):
        q = single_shaft(base['PR'], base['T3'], base['ma'], eta_t=et)
        Pel, _ = chain(q['P_shaft'], 0)
        print('  eta_t %.2f: shaft %.1f kW, electric %.1f kW (eff %.1f %%), turbine loading psi %.2f (now %.2f), EGT %.0f C'
              % (et, q['P_shaft'] / 1e3, Pel / 1e3, Pel / (base['mf'] * LHV_CH4) * 100, q['psi'], base['psi'], q['T4'] - 273.15))
    print('-' * 100)
    print('4) FPT + RECUPERATOR (eps 0.85, dp 3 % each side), eta_FPT 0.70, direct PMG:')
    r = recuperated_fpt(base, eps=0.85, eta_ts=0.70)
    Pel, _ = chain(r['P_shaft'], 0)
    print('  fuel %.2f g/s (was %.2f) | shaft %.1f kW | electric %.1f kW | efficiency %.1f %% | compressor air preheated to %.0f C'
          % (r['mf'] * 1e3, base['mf'] * 1e3, r['P_shaft'] / 1e3, Pel / 1e3, Pel / (r['mf'] * LHV_CH4) * 100, r['T2r'] - 273.15))
    print('-' * 100)
    p = free_power_turbine(base, eta_ts=0.70)
    q_heat = base['mg'] * CP_G * (p['T5'] - 393.0) * 0.85
    print('5) CHP: heat recoverable from FPT exhaust down to 120 C (HX 85 %%): %.0f kW thermal' % (q_heat / 1e3))
    print('   gas demand at full power %.1f Nm3/h at >= %.1f barg manifold -> needs a booster compressor or CNG supply'
          % (base['mf'] * 3600 / RHO_N_CH4, 3.0))
    json.dump({k: v for k, v in out.items()}, open(os.path.join(HERE, 'cycle_results.json'), 'w'), indent=1, default=float)
    try:
        plot(base)
    except ImportError:
        print('(matplotlib not available -> no plots; run with: uv run sim/gr180_cycle.py)')

def plot(base):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    PRs = [1.8 + 0.05 * k for k in range(40)]
    pts = [match_turbojet(p) for p in PRs]
    pts = [(p, s) for p, s in zip(PRs, pts) if s]
    ax[0].plot([p for p, _ in pts], [s['F'] for _, s in pts], label='thrust [N]')
    ax[0].plot([p for p, _ in pts], [s['T3'] - 273.15 for _, s in pts], label='TIT [°C]')
    ax[0].plot([p for p, _ in pts], [s['ma'] * 1000 for _, s in pts], label='air flow [g/s]')
    ax[0].axvline(base['PR'], ls='--', c='gray'); ax[0].set_xlabel('compressor pressure ratio'); ax[0].legend(); ax[0].grid(alpha=.3)
    ax[0].set_title('Turbojet operating line (CAD NGV + nozzle areas)')
    etas = [0.55 + 0.01 * k for k in range(31)]
    for st, lab in ((0, 'direct PMG'), (2, '2-stage gearbox')):
        ax[1].plot(etas, [chain(free_power_turbine(base, e)['P_shaft'], st)[0] / 1e3 for e in etas], label=lab)
    ax[1].set_xlabel('free power turbine efficiency (total-static)'); ax[1].set_ylabel('electric power [kW]')
    ax[1].set_title('Generator output, gas generator at 176.5 N point'); ax[1].legend(); ax[1].grid(alpha=.3)
    fig.tight_layout(); fn = os.path.join(HERE, 'gr180_cycle.png'); fig.savefig(fn, dpi=120); print('plot ->', fn)

if __name__ == '__main__':
    main()
