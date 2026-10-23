# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "gmsh", "matplotlib"]
# ///
"""GR180 version E - self-built high-speed PMG: electromagnetic design + verification (FEM) + DC-link window + losses.

Machine: cad/variant_e/eg_layout.py (EM, WIND).  Tools: sim/variant_e/eg_fem2d.py (2D nonlinear FEM, gmsh mesh) and
sim/variant_e/eg_bridge.py (generator + 6-pulse diode bridge + AFE-held DC link, time domain).
Steps
 1  FEM no-load (72 rotor positions): flux linkage, EMF waveform, gap field, cogging, stator iron B(t)
 2  FEM d/q inductance at rated current + numerical end-winding inductance (Neumann integrals, 48 coil ends, end-face image)
 3  winding resistance from the coil geometry (MLT), temperature
 4  diode-bridge operating points at 250 kW net (270 kW shaft), 306 kW (770 C, 30 C), 332.4 kW (850 C peak / cap), 335 kW
    (thermal rating); DC-link window for a standard 400 V AFE incl. cold / hot magnets, grid +10 %, part-load speed schedule,
    full-speed-no-load limit, motoring start, 690 V / transformer alternative, stack-length trade
 5  FEM load stepping (120 positions over one period) with the bridge current waveform: torque + ripple, saturation, core
    loss (Bertotti per harmonic and element), Litz proximity loss, magnet B in the rotor frame
 6  time-harmonic eddy FEM in the rotor frame (6f / 12f / 18f from the 5/7, 11/13, 17/19 current harmonics): Cu screen,
    steel shaft and (segmented) magnet losses
 7  windage (gap, end faces, steps), bearings -> loss table + efficiency; 3-phase short circuit; demagnetisation check
Run:  ~/micromamba/envs/gr180/bin/python sim/variant_e/eg_em.py   ->  sim/variant_e/eg_em.json   (~6 min)
"""
import json, math, os, sys, time
import numpy as np
from scipy.optimize import brentq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_e'))
sys.path.insert(0, HERE)
import eg_layout as EL                  # noqa: E402
import eg_fem2d as F                    # noqa: E402
import eg_bridge as BR                  # noqa: E402

EM, WIND = EL.EM, EL.WIND
f = EL.F_EL; w = 2 * math.pi * f
L_STK = EM['stack'] / 1e3
L_EFF = (EM['stack'] + EM['L_end_fringe']) / 1e3
K3D = L_EFF / L_STK
MU0 = F.MU0
T_MAG_HOT, T_MAG_COLD, T_CU, T_SHIELD = 100.0, 20.0, 120.0, 90.0   # design temperatures (C); eg_thermal.py checks them
CY = json.load(open(os.path.join(HERE, 'e_cycle.json')))
RHO_FE = 7650.0
SIG_CU20 = 5.8e7
# Bertotti coefficients (W/kg; f Hz, B T peak) fitted to typical catalogue data:
#   NO10 0.10 mm: W10/400 ~ 8.5, W10/1k ~ 27 W/kg  (order spec: W10/400 <= 10 W/kg guaranteed)
#   NO20 0.20 mm: W10/400 ~ 13.5, W10/1k ~ 50 W/kg
CORE = {'NO10': dict(kh=0.014, a=1.9, ke=4.1e-6, ka=2.8e-4), 'NO20': dict(kh=0.016, a=1.9, ke=1.65e-5, ka=5.6e-4)}
BUILD = dict(teeth=1.25, yoke=1.15)          # laser cut (edge damage in 8 mm teeth) + bonded stack, no welds / interlocks
P_GRID_MARGIN = dict(V_dc_min=660.0, V_dc_max_op=760.0, note='standard 400 V AFE (380-480/500 V class, e.g. ABB ACS880-207 / '
                     'Danfoss VACON NXA / Siemens S120 ALM / Inovance): DC must stay >= sqrt2 x 440 V x 1.06 = 660 V to export into a '
                     '400 V +10 % grid; upper operating limit 760 V (below the brake-chopper threshold ~780-800 V; check the datasheet)')


def Br_at(T):
    return EM['Br20'] * (1 + EM['alpha_Br'] * (T - 20.0))


def rho_cu(T):
    return 1.724e-8 * (1 + 0.00393 * (T - 20.0))


# ------------------------------------------------------------------ winding geometry, end winding, resistance
def winding_factors():
    Q, y = EM['slots'], EM['pitch']
    q = Q // 6
    out = {}
    for h in (1, 3, 5, 7, 11, 13, 23, 25):
        kd = math.sin(h * math.pi / 6) / (q * math.sin(h * math.pi / (6 * q)))
        kp = math.sin(h * y / (Q / 2) * math.pi / 2)
        out[h] = round(abs(kd * kp), 4)
    return out


def end_winding(k_img=0.4, gmr_mm=None, nseg=48):
    """3D filament model of the 48 coil ends (diamond shape: straight out of the slot, rise to the nose at the crossing
    angle, back down to the bottom layer of slot k + y); Neumann mutual inductances with a partial image in the laminated
    end face (k_img); returns the synchronous end-winding inductance per phase (paths in parallel) and the path length"""
    Q, y = EM['slots'], EM['pitch']
    rr = EL.conductor_radii()
    r_t, r_b = 0.5 * (rr[0] + rr[1]), 0.5 * (rr[2] + rr[3])
    ls, alpha = WIND['end_straight'], WIND['end_angle_deg']
    gmr = gmr_mm or 0.2235 * (WIND['ins_w'] + 2 * WIND['ins_h'])
    top, bot, ptop, pbot = F.winding_table(Q, y, EM['paths'])
    dphi = 2 * math.pi * y / Q
    rm = 0.5 * (r_t + r_b)
    hn = rm * dphi / 2 * math.tan(math.radians(alpha))
    L = EM['stack']

    def path(k, end):
        p0 = 2 * math.pi * (k + 0.5) / Q
        pts = [(0.0, p0, r_t), (ls, p0, r_t)]
        for s in np.linspace(0, 1, nseg + 1)[1:]:
            pts.append((ls + hn * (1 - abs(2 * s - 1)), p0 + dphi * s, r_t + (r_b - r_t) * s))
        pts.append((0.0, p0 + dphi, r_b))
        P = np.array([[x, r * math.cos(p), r * math.sin(p)] for (x, p, r) in pts])
        if end == 'rear':
            P[:, 0] = L + P[:, 0]
        else:
            P[:, 0] = -P[:, 0]; P = P[::-1]
        return P
    coils = [(k, end, path(k, end)) for k in range(Q) for end in ('front', 'rear')]
    mids, dls, cid = [], [], []
    for ci, (k, end, P) in enumerate(coils):
        mids.append(0.5 * (P[1:] + P[:-1])); dls.append(P[1:] - P[:-1]); cid += [ci] * (len(P) - 1)
    M_ = np.vstack(mids) * 1e-3; D = np.vstack(dls) * 1e-3; cid = np.array(cid)
    ends = np.array([0 if coils[c][1] == 'front' else 1 for c in cid])

    def mut(Ma, Da, Mb, Db):
        dd = Ma[:, None, :] - Mb[None, :, :]
        return MU0 / (4 * math.pi) * (Da @ Db.T) / np.sqrt((dd ** 2).sum(-1) + (gmr * 1e-3) ** 2)
    K = mut(M_, D, M_, D)
    for e, xp in ((0, 0.0), (1, L * 1e-3)):
        sel = ends == e
        Mi = M_[sel].copy(); Mi[:, 0] = 2 * xp - Mi[:, 0]; Di = D[sel].copy(); Di[:, 0] = -Di[:, 0]
        K[np.ix_(sel, sel)] += k_img * mut(M_[sel], D[sel], Mi, Di)
    nc = len(coils)
    Mc = np.zeros((nc, nc))
    idx = [np.where(cid == a)[0] for a in range(nc)]
    for a in range(nc):
        Ka = K[idx[a]]
        for b in range(nc):
            Mc[a, b] = Ka[:, idx[b]].sum()
    nt = EM['turns_coil']
    iph = [1.0, -0.5, -0.5]
    Ic = np.array([top[k][1] * iph[top[k][0]] / EM['paths'] * nt for (k, end, P) in coils])
    psi_c = nt * (Mc @ Ic)
    psi = sum(top[k][1] * psi_c[ci] for ci, (k, end, P) in enumerate(coils) if top[k][0] == 0 and ptop[k] == 0)
    lpath = float(np.mean([np.linalg.norm(np.diff(P, axis=0), axis=1).sum() for (k, end, P) in coils]))
    return dict(L_ew_H=float(psi), nose_height_mm=round(hn, 1), overhang_mm=round(ls + hn + WIND['ins_h'], 1), end_length_per_turn_mm=round(lpath, 1),
                r_top_mm=round(r_t, 2), r_bot_mm=round(r_b, 2), k_img=k_img, gmr_mm=round(gmr, 2))


def resistance(T, l_end_mm):
    MLT = 2 * (EM['stack'] + l_end_mm) / 1e3
    A = WIND['Cu_mm2'] * 1e-6
    R_path = rho_cu(T) * EM['N_ph'] * MLT / A
    R_lead = rho_cu(T) * 2 * 0.6 / (2 * 70e-6)           # 2 leads per phase (line + star side), 0.6 m each, 2 x 70 mm2 silicone cable
    return dict(MLT_m=MLT, R_ph=R_path / EM['paths'] + R_lead, R_ph_winding=R_path / EM['paths'], R_lead=R_lead)


# ------------------------------------------------------------------ losses helpers
def core_density(Bx, By, grade):
    """W/kg per element from B(t) over one period (rows = elements, columns = time samples)"""
    c = CORE[grade]
    n = Bx.shape[1]
    p = np.zeros(Bx.shape[0])
    for comp in (Bx, By):
        Fh = np.abs(np.fft.rfft(comp, axis=1)) * 2 / n
        Fh[:, 0] = 0.0
        fh = np.arange(Fh.shape[1]) * f
        p += (c['kh'] * fh * Fh ** c['a'] + c['ke'] * (fh * Fh) ** 2 + c['ka'] * (fh * Fh) ** 1.5).sum(1)
    return p


def plate_k(a, b):
    a, b = min(a, b), max(a, b)
    s = sum(math.tanh(n * math.pi * b / (2 * a)) / n ** 5 for n in range(1, 60, 2))
    return 1 - 192 / math.pi ** 5 * (a / b) * s


def skin_F(a, delta):
    xi = a / delta
    if xi < 1e-3:
        return 1.0
    return 3 / xi * (math.sinh(xi) - math.sin(xi)) / (math.cosh(xi) - math.cos(xi))


def segment_density(Br_amp, Bt_amp, omega, r_m, n_circ, l_ax):
    """resistance-limited eddy loss density (W/m3) in a rectangular magnet segment (skin correction per dimension):
    radial B -> loops in the theta-z plane (arc width x axial length), tangential B -> loops in the r-z plane"""
    sig = EM['sigma_SmCo']
    delta = math.sqrt(2 / (omega * MU0 * EM['mu_r'] * sig))
    tm = (EM['magnet_OD'] - EM['magnet_ID']) / 2e3
    wseg = 2 * math.pi * r_m / n_circ
    a1, b1 = sorted((wseg, l_ax)); a2, b2 = sorted((tm, l_ax))
    return sig * omega ** 2 / 24 * (Br_amp ** 2 * a1 ** 2 * plate_k(a1, b1) * skin_F(a1, delta) + Bt_amp ** 2 * a2 ** 2 * plate_k(a2, b2) * skin_F(a2, delta))


def air_props(T_C, p=1.02e5):
    Tk = T_C + 273.15
    mu = 1.716e-5 * (Tk / 273.15) ** 1.5 * (273.15 + 110.4) / (Tk + 110.4)
    return p / (287.05 * Tk), mu


def windage(m_air=0.045, T_air=60.0, rough=1.10):
    """gap: Bilgen & Boulos C_M = 0.065 (g/R)^0.3 Re^-0.2, P = 0.5 C_M pi rho w^3 R^4 L (x Yamada axial-flow factor);
    rotor end faces: enclosed disk regime IV (Daily & Nece) C_M = 0.051 (s/R)^0.1 Re^-0.2 per disk (both sides);
    shaft steps in the end spaces + labyrinths: same gap formula with the local clearance"""
    rho, mu = air_props(T_air)
    R, g = EM['rotor_OD'] / 2e3, EM['gap'] / 1e3
    Ls = (EM['magnet_L'] + 2 * EL_endring()) / 1e3
    Re = rho * w * R * g / mu
    Cm = 0.065 * (g / R) ** 0.3 * Re ** -0.2
    v_ax = m_air / (rho * math.pi * ((R + g) ** 2 - R ** 2))
    Re_a = 2 * g * v_ax * rho / mu
    k_ax = (1 + (8 * Re_a / (7 * Re)) ** 2) ** 0.38
    P_gap = 0.5 * Cm * math.pi * rho * w ** 3 * R ** 4 * Ls * rough * k_ax
    # end faces: annulus r 35.5..60, axial clearance to the end-bell hub nose s = 6 mm
    s = 6e-3
    Re_d = rho * w * R ** 2 / mu
    Cmd = 0.051 * (s / R) ** 0.1 * Re_d ** -0.2
    r_in = EM['magnet_ID'] / 2e3 - EM['shield_t'] / 1e3
    P_face = 2 * 0.5 * (0.5 * Cmd) * rho * w ** 3 * (R ** 5 - r_in ** 5)
    # shaft steps d60 x 2 x 25 mm in the hub bore (radial clearance 7 mm) + labyrinths d50 x 2 x 25 mm (0.3 mm)
    P_step = 0.0
    for (Rs, gs, Lx) in ((0.030, 0.007, 0.050), (0.025, 0.0003, 0.012)):     # d60 steps; labyrinth tooth lands only (2 x 6 x 1 mm)
        Re_s = rho * w * Rs * gs / mu
        Cs = 0.065 * (gs / Rs) ** 0.3 * Re_s ** -0.2 if Re_s > 1e4 else 2 * (gs / Rs) ** -1 / Re_s * 1.0
        P_step += 0.5 * Cs * math.pi * rho * w ** 3 * Rs ** 4 * Lx
    return dict(gap_W=P_gap, end_faces_W=P_face, steps_labyrinths_W=P_step, total_W=P_gap + P_face + P_step, Re_theta=Re, Re_axial=Re_a,
                axial_flow_factor=k_ax, C_M=Cm, v_axial_m_s=v_ax, air_C=T_air, m_air_kg_s=m_air)


def EL_endring():
    return 12.0


def bearings_W():
    import importlib
    sys.path.insert(0, HERE)
    er = importlib.import_module('e_rotor')
    m_rot = 32.0                                    # generator rotor + quill (eg_rotor.py gives the exact value)
    Fr = 0.5 * m_rot * 9.81 + 40.0
    return dict(front_W=er.friction_W(Fr, 350.0), rear_W=er.friction_W(Fr, 300.0), Fr_N=Fr, note='Palmgren, VG32 oil jet, 300 N spring preload (+50 N locating), e_rotor.friction_W')


# ------------------------------------------------------------------ FEM sweeps
def build_model(T_mag, h_gap=0.7):
    mesh = F.build_mesh(EL.em_geom(), h_gap=h_gap, h_far=4.0)
    mod = F.PMGModel(mesh, dict(Br=Br_at(T_mag), mur=EM['mu_r'], lam=EM['lam'], stack=EM['stack_factor'], L_stk=L_STK,
                                turns_coil=EM['turns_coil'], paths=EM['paths'], pitch=EM['pitch']))
    return mesh, mod


def sweep(mod, n, cur=None, Br=None, mag_pts=None):
    """rotor angles theta_k = 2 pi k / n; cur(theta) -> i_abc (motor convention, A); returns psi(3, n), torque(n), iron / slot
    element B(t), magnet rotor-frame B at material points"""
    th = 2 * np.pi * np.arange(n) / n
    iron, slots = mod.reg['iron'], np.concatenate([mod.reg['slot_top'], mod.reg['slot_bot']])
    psi = np.zeros((3, n)); T = np.zeros(n)
    BxI = np.zeros((len(iron), n)); ByI = np.zeros((len(iron), n))
    BxS = np.zeros((len(slots), n)); ByS = np.zeros((len(slots), n))
    Bm = None
    if mag_pts is not None:
        Bm = np.zeros((2, len(mag_pts), n))
    A = None; its = []
    for k, t in enumerate(th):
        i = [0.0, 0.0, 0.0] if cur is None else cur(t)
        A, info = mod.solve(t, i, A0=A, Br=Br)
        its.append(info['iters'])
        psi[:, k] = mod.flux_linkage(A)[:, 0]
        T[k] = mod.torque(A)
        Bx, By = mod.B_of(A)
        BxI[:, k], ByI[:, k] = Bx[iron], By[iron]
        BxS[:, k], ByS[:, k] = Bx[slots], By[slots]
        if mag_pts is not None:
            r, ph0 = mag_pts[:, 0], mag_pts[:, 1]
            ph = ph0 + t
            pts = np.stack([r * np.cos(ph), r * np.sin(ph)], 1)
            tri = mod.find(pts)
            bx, by = Bx[tri], By[tri]
            Bm[0, :, k] = bx * np.cos(ph) + by * np.sin(ph)
            Bm[1, :, k] = -bx * np.sin(ph) + by * np.cos(ph)
    return dict(theta=th, psi=psi, T=T, BxI=BxI, ByI=ByI, BxS=BxS, ByS=ByS, Bm=Bm, iron=iron, slots=slots, newton=float(np.mean(its)))


def iron_loss(mod, S, grade=None):
    grade = grade or EM['lam']
    e = S['iron']
    p = core_density(S['BxI'], S['ByI'], grade)
    m = mod.area[e] * L_STK * EM['stack_factor'] * RHO_FE
    r = np.hypot(mod.cen[e, 0], mod.cen[e, 1]) * 1e3
    yoke = r > EM['bore'] / 2 + EM['slot_depth']
    Pt = float((p * m)[~yoke].sum() * BUILD['teeth']); Py = float((p * m)[yoke].sum() * BUILD['yoke'])
    b = np.sqrt(S['BxI'] ** 2 + S['ByI'] ** 2).max(1)
    return dict(teeth_W=Pt, yoke_W=Py, total_W=Pt + Py, m_teeth_kg=float(m[~yoke].sum()), m_yoke_kg=float(m[yoke].sum()),
                B_teeth_max_T=float(b[~yoke].max()), B_teeth_p95_T=float(np.percentile(b[~yoke], 95)), B_yoke_max_T=float(b[yoke].max()),
                B_yoke_p50_T=float(np.percentile(b[yoke], 50)), grade=grade, build_factor=BUILD)


def proximity_loss(mod, S, T_cu=T_CU, l_end_mm=300.0):
    e = S['slots']
    n = S['BxS'].shape[1]
    d = WIND['strand_d'] * 1e-3
    sig = 1 / rho_cu(T_cu)
    dB2 = 0.0
    for comp in (S['BxS'], S['ByS']):
        Fh = np.fft.rfft(comp, axis=1) * 2 / n
        h = np.arange(Fh.shape[1])
        dB2 = dB2 + ((h * w) ** 2 * np.abs(Fh) ** 2 / 2).sum(1)
    k_cu = 4 * WIND['Cu_mm2'] / (EM['slot_w'] * (EM['slot_depth'] - EM['wedge_h']))
    P_slot = float((sig * d ** 2 / 16 * dB2 * mod.area[e] * k_cu).sum() * L_STK)
    P_end = 0.3 * P_slot * l_end_mm / EM['stack']       # end-winding field ~ 0.55 x slot field (est)
    return dict(slot_W=P_slot, end_W=P_end, total_W=P_slot + P_end, k_cu_slot=k_cu)


def mag_points(nr=4, nphi=48):
    rc, rm = EM['magnet_ID'] / 2e3, EM['magnet_OD'] / 2e3
    pts = []
    for i in range(nr):
        r = rc + (i + 0.5) * (rm - rc) / nr
        for j in range(nphi):
            pts.append((r, 2 * np.pi * j / nphi))
    return np.array(pts)


SEGMENTATIONS = [(12, 272.0), (12, 20.0), (12, 10.0), (12, 5.0), (12, 2.0), (16, 2.0), (24, 5.0), (8, 2.0)]


def magnet_loss_stepping(Bm, pts, n_circ, l_ax_mm, orders=None):
    """from the magnetostatic stepping (no screening by the Cu shield): rotor-frame harmonics of B_r, B_theta"""
    n = Bm.shape[2]
    Fr = np.abs(np.fft.rfft(Bm[0], axis=1)) * 2 / n; Ft = np.abs(np.fft.rfft(Bm[1], axis=1)) * 2 / n
    p = np.zeros(len(pts))
    for h in range(1, Fr.shape[1]):
        if orders is not None and h not in orders:
            continue
        for j in range(len(pts)):
            p[j] += segment_density(Fr[j, h], Ft[j, h], h * w, pts[j, 0], n_circ, l_ax_mm / 1e3)
    V = math.pi * ((EM['magnet_OD'] / 2e3) ** 2 - (EM['magnet_ID'] / 2e3) ** 2) * EM['magnet_L'] / 1e3
    return float(p.mean() * V)


def magnet_loss_slot(Bgap_h, r_g, n_circ, l_ax_mm, nr=8):
    """stator-slotting harmonics: gap-field spatial orders n = Q -/+ 1 (amplitude Bgap_h[n] at radius r_g) are seen by the
    rotor at Q x f; in the (linear, mu_r ~1) magnet / sleeve region they decay as (r / r_g)^(n - 1) with |B_r| = |B_theta|"""
    rc, rm = EM['magnet_ID'] / 2e3, EM['magnet_OD'] / 2e3
    Q = EM['slots']
    P = 0.0
    for k in range(nr):
        r = rc + (k + 0.5) * (rm - rc) / nr
        dV = 2 * math.pi * r * (rm - rc) / nr * EM['magnet_L'] / 1e3
        for n, B in Bgap_h.items():
            b = B * (r / r_g) ** (n - 1)
            P += segment_density(b, b, Q * w, r, n_circ, l_ax_mm / 1e3) * dV
    return float(P)


def magnet_loss_harmonic(mod, A, omega_r, n_circ, l_ax_mm):
    """from a time-harmonic (screened) solution: element phasors of B_r, B_theta in the magnet ring"""
    e = mod.reg['magnet']
    Bx, By = mod.B_of(A)
    cx, cy = mod.cen[e, 0], mod.cen[e, 1]
    r = np.hypot(cx, cy)
    br = np.abs((Bx[e] * cx + By[e] * cy) / r); bt = np.abs((-Bx[e] * cy + By[e] * cx) / r)
    p = np.array([segment_density(br[k], bt[k], omega_r, r[k], n_circ, l_ax_mm / 1e3) for k in range(len(e))])
    return float((p * mod.area[e]).sum() * EM['magnet_L'] / 1e3)


# ------------------------------------------------------------------ bridge helpers
def bridge(E_ll, Ls, R, V, s=1.0, periods=22, steps=900):
    a, _ = BR.run_point(E_ll * s, f * s, Ls, R, V, periods=periods, steps=steps)
    return a


def vdc_for(P_em_kW, E_ll, Ls, R, s=1.0):
    """V_dc at which the bridge takes P_em (EMF x current) = P_em_kW"""
    fun = lambda V: bridge(E_ll, Ls, R, V, s)['P_em_kW'] - P_em_kW
    lo, hi = 0.55 * 1.35 * E_ll * s, math.sqrt(2) * E_ll * s - 1.0
    V = brentq(fun, lo, hi, xtol=0.5)
    return V, bridge(E_ll, Ls, R, V, s, periods=30, steps=1800)


def main():
    t0 = time.time()
    out = dict(title='GR180 version E self-built HS PMG - electromagnetic design, FEM verification, DC-link window, losses', date='2026-10-24',
               script='sim/variant_e/eg_em.py', layout='cad/variant_e/eg_layout.py', tools='eg_fem2d.py (2D nonlinear FEM, gmsh) + eg_bridge.py (diode bridge)')
    wf = winding_factors()
    ew = end_winding()
    ew_sens = {'k_img 0': end_winding(k_img=0.0)['L_ew_H'], 'k_img 1': end_winding(k_img=1.0)['L_ew_H']}
    RR = resistance(T_CU, ew['end_length_per_turn_mm'])
    R20 = resistance(20.0, ew['end_length_per_turn_mm'])
    print('end winding L_ew %.1f uH (k_img 0..1: %.1f..%.1f), overhang %.0f mm, end length/turn %.0f mm; MLT %.3f m, R_ph %.2f mOhm @%d C' % (
        ew['L_ew_H'] * 1e6, ew_sens['k_img 0'] * 1e6, ew_sens['k_img 1'] * 1e6, ew['overhang_mm'], ew['end_length_per_turn_mm'], RR['MLT_m'], RR['R_ph'] * 1e3, T_CU))

    mesh, mod = build_model(T_MAG_HOT)
    G = EL.em_geom(); so = mesh['so']
    out['mesh'] = dict(nodes=len(mesh['p']), triangles=len(mesh['t']), h_gap_mm=0.7, regions={n: int((mesh['region'] == i).sum()) for i, n in enumerate(mesh['names'])})
    # ---------------- 1 no load
    NL = sweep(mod, 72)
    pa = NL['psi'][0]
    X1 = np.fft.rfft(pa)
    a0 = -float(np.angle(X1[1]))
    Psi2D = 2 * abs(X1[1]) / len(pa)
    harm_psi = {h: round(float(abs(X1[h]) / abs(X1[1]) * h), 5) for h in (3, 5, 7, 11, 13, 23, 25)}   # EMF harmonic ratio = h x psi ratio
    Psi = Psi2D * K3D
    E_ph = w * Psi / math.sqrt(2); E_ll = math.sqrt(3) * E_ph
    E_ll_cold = E_ll * Br_at(T_MAG_COLD) / Br_at(T_MAG_HOT)
    A0, _ = mod.solve(a0, [0, 0, 0])
    ph, br, bt = mod.gap_field(A0)
    Fg = np.fft.rfft(br) * 2 / len(br)
    cog = NL['T']
    nl_iron = iron_loss(mod, NL)
    print('no load %d C: Psi %.4f Wb (2D %.4f), E_ll %.1f V (cold %.1f), B_gap1 %.3f T, cogging pp %.3f N.m, iron %.0f W (teeth %.0f yoke %.0f) [%.0f s]' % (
        T_MAG_HOT, Psi, Psi2D, E_ll, E_ll_cold, abs(Fg[1]), cog.max() - cog.min(), nl_iron['total_W'], nl_iron['teeth_W'], nl_iron['yoke_W'], time.time() - t0))

    # ---------------- 2 inductance (FEM, rated current, d/q at theta = a0)
    a = 2 * np.pi / 3

    def iabc_dq(id_, iq, th):
        return [id_ * np.cos(th - a0 - k * a) - iq * np.sin(th - a0 - k * a) for k in (0, 1, -1)]

    def dq(A, th):
        p = mod.flux_linkage(A)[:, 0]
        d = 2 / 3 * sum(p[j] * np.cos(th - a0 - kk * a) for j, kk in enumerate((0, 1, -1)))
        q = -2 / 3 * sum(p[j] * np.sin(th - a0 - kk * a) for j, kk in enumerate((0, 1, -1)))
        return d, q
    Irat = 370.0 * math.sqrt(2)
    d0, q0 = dq(A0, a0)
    Ad, _ = mod.solve(a0, iabc_dq(-0.5 * Irat, 0, a0), A0); dm, _ = dq(Ad, a0)
    Aq, _ = mod.solve(a0, iabc_dq(0, Irat, a0), A0); _, qq = dq(Aq, a0)
    Ld2 = (dm - d0) / (-0.5 * Irat); Lq2 = (qq - q0) / Irat
    L2D = 0.5 * (Ld2 + Lq2)
    Ls = L2D * K3D + ew['L_ew_H']
    print('L_d %.1f L_q %.1f uH (2D), L_ew %.1f -> L_s %.1f uH, X_s %.3f Ohm' % (Ld2 * 1e6, Lq2 * 1e6, ew['L_ew_H'] * 1e6, Ls * 1e6, w * Ls))

    # ---------------- first-pass loss estimates for the power balance
    wind = windage(); brg = bearings_W()
    P_mech = wind['total_W'] + brg['front_W'] + brg['rear_W']
    P_rot_est, P_fe_est = 150.0, nl_iron['total_W'] * 1.08
    R_ph = RR['R_ph']
    OPS = [('250 kW net (rated, TIT 730 C, 30 C)', CY['rating']['TIT_for_250kW_expected'][2]['P_shaft_kW']),
           ('770 C design point, 30 C', CY['design_point']['P_shaft_to_PMG_kW']),
           ('850 C peak / 315 kW el cap', CY['ambient_table_TIT850_peak_capped'][2]['P_shaft_kW']),
           ('thermal rating 335 kW shaft', 335.0)]

    def op_points(E, Lsx, R, P_fe, P_rot, label='hot'):
        res = []
        for name, Ps in OPS:
            Pem = Ps - (P_mech + P_fe + P_rot) / 1e3
            V, b = vdc_for(Pem, E, Lsx, R)
            res.append(dict(case=name, P_shaft_kW=round(Ps, 1), P_em_kW=round(Pem, 1), V_dc=round(V, 1), I_dc=round(b['I_dc'], 1), P_dc_kW=round(b['P_dc_kW'], 1),
                            I_rms=round(b['I_rms'], 1), I1_rms=round(float(b['I1_rms']), 1), harmonics=b['harmonics'], thd_pct=round(b['thd_pct'], 1),
                            disp_deg=round(b['disp_deg'], 1), torque_ripple_6f_pct=round(b['torque_ripple_6f_pct'], 1), torque_pp_pct=round(b['torque_pp_pct'], 1),
                            x_pu=round(w * Lsx * b['I1_rms'] / (E / math.sqrt(3)), 3), P_cu_W=round(3 * b['I_rms'] ** 2 * R), magnets=label))
        return res
    ops = op_points(E_ll, Ls, R_ph, P_fe_est, P_rot_est)
    for o in ops:
        print('  %-38s V_dc %.0f V, I_rms %.0f A, 5th %.3f 7th %.3f, x %.2f pu' % (o['case'], o['V_dc'], o['I_rms'], o['harmonics'][5], o['harmonics'][7], o['x_pu']))

    # ---------------- 5 load stepping at the thermal rating (335 kW) with the bridge current waveform
    oR = ops[-1]
    rec, _ = BR.simulate(E_ll, f, Ls, R_ph, oR['V_dc'], periods=30, steps=1800)
    tt = (rec[:, 0] - rec[0, 0])
    Tp = 1 / f

    def cur(theta):
        phase = (theta - a0 + np.pi / 2) % (2 * np.pi)
        tq = phase / w
        return [-float(np.interp(tq, tt, rec[:, 1 + k], period=Tp)) for k in range(3)]     # motor convention
    mp = mag_points()
    LD = sweep(mod, 120, cur=cur, mag_pts=mp)
    T_load = LD['T'] * K3D
    ld_iron = iron_loss(mod, LD)
    prox = proximity_loss(mod, LD, l_end_mm=ew['end_length_per_turn_mm'])
    Fq = np.fft.rfft(T_load) / len(T_load) * 2
    print('load 335 kW: FEM torque %.1f N.m (expected %.1f), ripple pp %.1f %%, 6f %.1f %%, iron %.0f W (teeth B max %.2f T), proximity %.0f W [%.0f s]' % (
        T_load.mean(), -oR['P_em_kW'] * 1e3 / w, 100 * (T_load.max() - T_load.min()) / abs(T_load.mean()), 100 * abs(Fq[6]) / abs(T_load.mean()),
        ld_iron['total_W'], ld_iron['B_teeth_max_T'], prox['total_W'], time.time() - t0))
    mag_step = {('%d x %g' % s): round(magnet_loss_stepping(LD['Bm'], mp, *s, orders={6, 12, 18}), 1) for s in SEGMENTATIONS}
    r_g = 0.5 * (mesh['radii']['rg1'] + mesh['radii']['rg2']) * 1e-3
    Bslot = {n: float(abs(Fg[n])) for n in (EM['slots'] - 1, EM['slots'] + 1)}
    mag_slot = {('%d x %g' % s): round(magnet_loss_slot(Bslot, r_g, *s), 3) for s in SEGMENTATIONS}

    # ---------------- 6 time-harmonic eddy (screened rotor) for the current harmonics
    mod.solve(a0, iabc_dq(0, Irat * 0.9, a0), A0)            # freeze iron nu near the loaded operating point
    mu_sh = float(np.median(mod.nu_shaft.mu_inc(np.hypot(*mod.B_of(A0))[mod.reg['shaft']])))
    mu_sh = min(mu_sh, 300.0)

    def eddy_set(op, shield_sigma=3.6e7):
        I1pk = op['I1_rms'] * math.sqrt(2)
        tot = dict(shield=0.0, shaft=0.0); mag = {('%d x %g' % s): 0.0 for s in SEGMENTATIONS}
        per = {}
        for h, seq, k in ((5, -1, 6), (7, 1, 6), (11, -1, 12), (13, 1, 12), (17, -1, 18), (19, 1, 18)):
            Ih = op['harmonics'][h] * I1pk
            l, A = mod.eddy_harmonic(k * w, Ih, seq, mu_shaft=mu_sh, sigma_shaft=EM['sigma_shaft20'] / (1 + 0.0045 * (T_SHIELD - 20)),
                                     sigma_shield=shield_sigma)
            for kk in ('shield', 'shaft'):
                tot[kk] += l.get(kk, 0.0) * K3D
            per[h] = {kk: round(v * K3D, 1) for kk, v in l.items()}
            for s in SEGMENTATIONS:
                mag['%d x %g' % s] += magnet_loss_harmonic(mod, A, k * w, *s)
        return tot, {k: round(v, 1) for k, v in mag.items()}, per
    ed, mag_h, ed_per = eddy_set(oR)
    ed_noshield, _, _ = eddy_set(oR, shield_sigma=0.0)
    SEG = (12, 2.0)
    seg_key = '%d x %g' % SEG
    P_mag = mag_h[seg_key] + mag_slot[seg_key]
    print('rotor (335 kW): Cu screen %.0f W, shaft %.1f W (without screen: shaft %.0f W); magnets %s: %.1f W (harmonic) + %.2f W (slot) [%.0f s]' % (
        ed['shield'], ed['shaft'], ed_noshield['shaft'], seg_key, mag_h[seg_key], mag_slot[seg_key], time.time() - t0))

    # ---------------- second pass: updated losses -> bridge operating points (hot and cold magnets)
    P_rot = ed['shield'] + ed['shaft'] + P_mag + 5.0
    P_fe = ld_iron['total_W']
    ops = op_points(E_ll, Ls, R_ph, P_fe, P_rot)
    ops_cold = op_points(E_ll_cold, Ls, R_ph, P_fe, P_rot, label='cold 20 C')
    E_ll_120 = E_ll * Br_at(120.0) / Br_at(T_MAG_HOT)
    ops_120 = op_points(E_ll_120, Ls, R_ph, P_fe, P_rot, label='120 C')

    # ---------------- 4 DC window: P(V) at 100 % speed, part-load speed schedule, FSNL, start, alternatives
    PV = []
    for V in (660, 680, 700, 720, 740, 760, 780, 800, 840, 880):
        if V < math.sqrt(2) * E_ll - 2:
            b = bridge(E_ll, Ls, R_ph, V)
            PV.append(dict(V_dc=V, P_dc_kW=round(b['P_dc_kW'], 1), I_rms=round(b['I_rms'], 1)))
    Vmax = P_GRID_MARGIN['V_dc_max_op']
    sched = []
    for P in (60.0, 100.0, 150.0, 200.0, 250.0):
        try:
            s = brentq(lambda s_: bridge(E_ll, Ls, R_ph, Vmax, s_)['P_dc_kW'] - P, Vmax / (math.sqrt(2) * E_ll) + 1e-3, 1.0, xtol=2e-3)
            sched.append(dict(P_dc_kW=P, speed_pct=round(100 * s, 1), rpm=round(EL.N_RUN * s), f_Hz=round(f * s, 1), V_dc=Vmax))
        except ValueError:
            sched.append(dict(P_dc_kW=P, speed_pct=100.0, note='reachable at 100 %% speed with V_dc <= %.0f V' % Vmax))
    n_fsnl_hot = Vmax / (math.sqrt(2) * E_ll); n_fsnl_cold = Vmax / (math.sqrt(2) * E_ll_cold)
    V_inv = 0.95 * P_GRID_MARGIN['V_dc_min'] / math.sqrt(2) * 0.97
    E55 = 0.55 * E_ll_cold
    I_st = 60e3 / (math.sqrt(3) * 0.55 * E_ll)
    V_req = math.hypot(E55 + I_st * R_ph * math.sqrt(3), I_st * math.sqrt(3) * 0.55 * w * Ls)
    start = dict(speed_pct=55, f_Hz=round(0.55 * f, 1), E_ll_cold_V=round(E55, 1), motoring_current_A=round(I_st), V_ll_required=round(V_req, 1),
                 inverter_max_V_ll=round(V_inv, 1), ok=V_req < V_inv, bridge_blocks=math.sqrt(2) * E55 < P_GRID_MARGIN['V_dc_min'],
                 bridge_cut_in_speed_pct_at_660V=round(100 * P_GRID_MARGIN['V_dc_min'] / (math.sqrt(2) * E_ll_cold), 1),
                 sequence='K2 (start inverter + sine filter) closed, K1 (diode bridge) open: motor 0 -> 55 %% (light-off ~22 %%); open K2, close K1 '
                          '(bridge blocks: sqrt2 x E(55 %%) = %.0f V < 660 V); GT accelerates on fuel with the AFE holding V_dc at 760 V: no export below '
                          '%.0f %% speed (hot magnets), then the load ramps in with speed; the speed controller sets V_dc, the fuel controller sets TIT / power' % (
                              math.sqrt(2) * E55, 100 * n_fsnl_hot))
    # alternative: 690 V-class AFE on a 400/525 V transformer, rewound stator N_ph = 12 (3 turns / coil), shorter stack
    alt = {}
    for Lst in (220.0, 230.0):
        sc = 1.5 * (Lst + EM['L_end_fringe']) / (EM['stack'] + EM['L_end_fringe'])
        E_a = E_ll * sc
        Ls_a = 2.25 * (L2D * K3D * sc / 1.5 + ew['L_ew_H'])
        R_a = 2.25 * R_ph * (Lst + ew['end_length_per_turn_mm']) / (EM['stack'] + ew['end_length_per_turn_mm'])
        Vs = []
        for name, Ps in OPS[1:3]:
            V, b = vdc_for(Ps - (P_mech + P_fe + P_rot) / 1e3, E_a, Ls_a, R_a)
            Vs.append(round(V))
        alt['stack %.0f' % Lst] = dict(N_ph=12, E_ll_V=round(E_a), L_s_uH=round(Ls_a * 1e6, 1), V_dc_306_332=Vs, sqrt2_E=round(math.sqrt(2) * E_a),
                                        window='690 V-class AFE on a 525 V winding: 870-1100 V', fsnl_speed_pct=round(100 * 1100 / (math.sqrt(2) * E_a), 1))
    alt_note = ('690 V-class AFE + 400/525 V 350 kVA transformer: wider window (1100/870 = 1.26) -> export from ~10 % load at 100 % speed, but '
                '+1.2 % loss (~4 kW), +~1.1 t, +cost, rewound stator (3 turns / coil); the 400 V AFE + part-load speed schedule is preferred '
                'for 24/7 base load at 250-315 kW el')
    # stack-length trade (same cross-section, 1.5 mm screen)
    trade = []
    for Lst in (250.0, 260.0, 270.0, 280.0):
        sc = (Lst + EM['L_end_fringe']) / (EM['stack'] + EM['L_end_fringe'])
        E_t = E_ll * sc
        Ls_t = L2D * K3D * sc + ew['L_ew_H']
        R_t = resistance(T_CU, ew['end_length_per_turn_mm'])['R_ph'] * (Lst + ew['end_length_per_turn_mm']) / (EM['stack'] + ew['end_length_per_turn_mm'])
        row = dict(stack_mm=Lst, E_ll_V=round(E_t, 1), L_s_uH=round(Ls_t * 1e6, 1))
        for name, Ps in (OPS[0], OPS[2]):
            V, b = vdc_for(Ps - (P_mech + P_fe + P_rot) / 1e3, E_t, Ls_t, R_t)
            row['V_dc_%d' % round(Ps)] = round(V)
        trade.append(row)
    print('trade:', trade)

    # ---------------- 7 short circuit, demagnetisation
    Isc_pk = Psi / Ls
    T_sc = 1.5 * Psi ** 2 / Ls
    # transient with R (dq, sudden 3-ph short at full speed): i_d, i_q from zero
    dt = 1 / f / 400; idd = iqq = 0.0; Tmax = 0.0; Imax = 0.0
    for k in range(40000):
        did = (-R_ph * idd + w * Ls * iqq) / Ls
        diq = (-R_ph * iqq - w * Ls * idd - w * Psi) / Ls
        idd += did * dt; iqq += diq * dt
        Tmax = max(Tmax, abs(1.5 * Psi * iqq)); Imax = max(Imax, math.hypot(idd, iqq) * 1.0)
    mesh150, mod150 = mesh, mod
    Idem = -2.0 * Psi / Ls
    e = mod.reg['magnet']
    dem = {}
    for Tm in (100.0, 120.0, 150.0):
        Ad, _ = mod.solve(a0, iabc_dq(Idem, 0, a0), A0, Br=Br_at(Tm))
        Bx, By = mod.B_of(Ad)
        Bpar = Bx[e] * math.cos(a0) + By[e] * math.sin(a0)
        HcJ = 1990e3 * (1 - 0.0019 * (Tm - 20)); Hk = 0.70 * HcJ
        Bk = Br_at(Tm) - MU0 * EM['mu_r'] * Hk
        frac = float(mod.area[e][Bpar < Bk].sum() / mod.area[e].sum())
        dem['%d C' % Tm] = dict(B_parallel_min_T=round(float(Bpar.min()), 3), B_parallel_p01_T=round(float(np.percentile(Bpar, 1)), 3), HcJ_kA_m=round(HcJ / 1e3),
                                Hk_kA_m=round(Hk / 1e3), B_knee_T=round(Bk, 3), volume_below_knee_pct=round(100 * frac, 3))
    sc = dict(I_ss_rms=round(Isc_pk / math.sqrt(2)), I_ss_pu=round(Isc_pk / math.sqrt(2) / ops[-1]['I1_rms'], 2), I_peak_transient_A=round(Imax),
              T_peak_Nm=round(Tmax, 1), T_peak_over_rated=round(Tmax / (335e3 / w), 2), T_ideal_Nm=round(T_sc, 1),
              note='SPM without damper circuits: no subtransient; torque alternates at the stator frequency (583 Hz, far above the 166 Hz quill mode); '
                   'converter-side faults are cleared by the DC fuses / AFE; quill and hex sized for x5 rated (e_rotor.json)')
    demag = dict(case='sudden 3-ph terminal short at 35,000 rpm, first transient peak i_d = -2 Psi / L_s (worst instant, no decay)', i_d_peak_A=round(Idem),
                 grade='Sm2Co17 YXG-32H class: Br 1.10-1.13 T, HcJ >= 1990 kA/m at 20 C (beta -0.19 %/K), squareness Hk >= 0.70 HcJ', by_temperature=dem)
    print('short circuit: I_ss %d A rms (%.1f pu), I_peak %d A, T_peak %.0f N.m (%.1f x rated); demag i_d %d A: %s' % (
        sc['I_ss_rms'], sc['I_ss_pu'], sc['I_peak_transient_A'], sc['T_peak_Nm'], sc['T_peak_over_rated'], Idem, dem))

    # ---------------- losses and efficiency per operating point
    I335 = ops[-1]['I1_rms']
    losses = []
    for o in ops:
        kI = (o['I1_rms'] / I335) ** 2
        hsum = sum((o['harmonics'][h] * o['I1_rms']) ** 2 for h in (5, 7, 11, 13, 17, 19))
        hsum0 = sum((ops[-1]['harmonics'][h] * I335) ** 2 for h in (5, 7, 11, 13, 17, 19))
        kh = hsum / hsum0
        P_cu = 3 * o['I_rms'] ** 2 * R_ph
        P_fe_o = nl_iron['total_W'] + (ld_iron['total_W'] - nl_iron['total_W']) * kI
        P_px = prox['total_W'] * kI
        P_sh = (ed['shield'] + ed['shaft']) * kh
        P_mg = mag_h[seg_key] * kh + mag_slot[seg_key]
        L_ = dict(copper_dc_W=round(P_cu), litz_proximity_W=round(P_px), iron_W=round(P_fe_o), magnets_W=round(P_mg, 1), cu_screen_and_shaft_W=round(P_sh),
                  sleeve_end_rings_W=5, windage_W=round(wind['total_W']), bearings_W=round(brg['front_W'] + brg['rear_W']))
        tot_em = P_cu + P_px + P_fe_o + P_mg + P_sh + 5
        tot = tot_em + wind['total_W'] + brg['front_W'] + brg['rear_W']
        Ps = o['P_shaft_kW'] * 1e3
        losses.append(dict(case=o['case'], P_shaft_kW=o['P_shaft_kW'], losses_W=L_, total_W=round(tot), P_terminals_kW=round((Ps - tot) / 1e3, 2),
                           eta_generator=round((Ps - tot) / Ps, 4), eta_electromagnetic=round((Ps - wind['total_W'] - brg['front_W'] - brg['rear_W'] - tot_em) /
                                                                                              (Ps - wind['total_W'] - brg['front_W'] - brg['rear_W']), 4),
                           rotor_heat_W=round(P_mg + P_sh + 5), stator_heat_W=round(P_cu + P_px + P_fe_o)))
    for l in losses:
        print('  %-38s losses %5d W  eta %.4f  (%s)' % (l['case'], l['total_W'], l['eta_generator'], l['losses_W']))

    # ---------------- masses (active parts)
    rc, rm, rs = EM['magnet_ID'] / 2e3, EM['magnet_OD'] / 2e3, EM['rotor_OD'] / 2e3
    m_mag = 8400 * math.pi * (rm ** 2 - rc ** 2) * EM['magnet_L'] / 1e3
    m_cu_slot = 8900 * 24 * 4 * WIND['Cu_mm2'] * 1e-6 * L_STK
    m_cu_end = 8900 * 24 * 4 * WIND['Cu_mm2'] * 1e-6 * ew['end_length_per_turn_mm'] / 1e3 * 2 / 2
    masses = dict(magnets_kg=round(m_mag, 2), cu_screen_kg=round(8900 * math.pi * (rc ** 2 - (rc - EM['shield_t'] / 1e3) ** 2) * EM['magnet_L'] / 1e3, 2),
                  sleeve_kg=round(1580 * math.pi * (rs ** 2 - rm ** 2) * (EM['magnet_L'] + 24) / 1e3, 2), iron_teeth_kg=round(ld_iron['m_teeth_kg'], 1),
                  iron_yoke_kg=round(ld_iron['m_yoke_kg'], 1), copper_slot_kg=round(m_cu_slot, 1), copper_end_kg=round(m_cu_end, 1))

    out.update(
        design_temperatures_C=dict(magnet_hot=T_MAG_HOT, magnet_cold=T_MAG_COLD, copper=T_CU, screen=T_SHIELD),
        geometry=dict(EM=EM, slot=dict(r1_mm=round(so['r1'], 2), r2_mm=round(so['r2'], 2), A_winding_mm2=round(so['A_winding_mm2'], 1),
                                       tooth_w_bore_mm=round(so['tooth_w_bore'], 2), tooth_w_root_mm=round(so['tooth_w_root'], 2)),
                      L_eff_mm=EM['stack'] + EM['L_end_fringe'], U_tip_m_s=round(w * rs, 1), masses=masses),
        winding=dict(WIND=WIND, N_ph_series=EM['N_ph'], paths=EM['paths'], coils=24, turns_coil=EM['turns_coil'], pitch='10/12 (1-11)', winding_factors=wf,
                     end_winding=ew, end_winding_sensitivity_uH={k: round(v * 1e6, 1) for k, v in ew_sens.items()},
                     MLT_m=round(RR['MLT_m'], 4), R_ph_20C_mOhm=round(R20['R_ph'] * 1e3, 3), R_ph_hot_mOhm=round(R_ph * 1e3, 3), R_lead_mOhm=round(RR['R_lead'] * 1e3, 3),
                     J_A_mm2_at_335kW=round(ops[-1]['I_rms'] / EM['paths'] / WIND['Cu_mm2'], 2),
                     A_rms_kA_m=round(6 * EM['N_ph'] * ops[-1]['I_rms'] / (math.pi * EM['bore'] / 1e3) / 1e3, 1)),
        no_load=dict(T_magnet_C=T_MAG_HOT, Br_T=round(Br_at(T_MAG_HOT), 4), Psi_peak_Wb=round(Psi, 5), Psi_2D_Wb=round(Psi2D, 5), E_ph_V=round(E_ph, 1),
                     E_ll_V=round(E_ll, 1), E_ll_cold_20C_V=round(E_ll_cold, 1), E_ll_120C_V=round(E_ll_120, 1), emf_harmonics_ratio=harm_psi,
                     B_gap_fund_T=round(float(abs(Fg[1])), 4), B_gap_harm_pct={h: round(float(100 * abs(Fg[h]) / abs(Fg[1])), 2) for h in (3, 5, 7, 23, 25)},
                     cogging_pp_Nm=round(float(cog.max() - cog.min()), 4), iron_loss=nl_iron, a0_deg=round(math.degrees(a0), 2), newton_iters=NL['newton']),
        inductance=dict(L_d_2D_uH=round(Ld2 * 1e6, 2), L_q_2D_uH=round(Lq2 * 1e6, 2), L_end_uH=round(ew['L_ew_H'] * 1e6, 2), L_s_uH=round(Ls * 1e6, 2),
                        X_s_Ohm=round(w * Ls, 4), x_pu_335kW=ops[-1]['x_pu']),
        bridge=dict(model='eg_bridge.py: 6-pulse diodes (1.0 V + 1 mOhm), stiff AFE DC link, no DC choke (the 98 uH machine inductance smooths the current)',
                    hot_magnets=ops, cold_magnets=ops_cold, magnets_120C=ops_120,
                    window=dict(limits=P_GRID_MARGIN, P_vs_Vdc_100pct=PV, partload_speed_schedule=sched, fsnl_max_speed_pct=dict(hot=round(100 * n_fsnl_hot, 1),
                                cold=round(100 * n_fsnl_cold, 1)), start=start, alternative_690V=alt, alternative_note=alt_note, stack_trade=trade,
                                verdict='standard 400 V AFE works at 250 / 306 / 332 kW shaft at 100 %% speed for magnets 20-120 C (V_dc in the 660-760 V band); '
                                        'below ~%.0f kW the speed is lowered (schedule); full-speed no-load is not possible (sqrt2 E > 760 V) -> idle at <= %.0f %% speed' % (
                                            [p['P_dc_kW'] for p in PV if p['V_dc'] == 760][0] if any(p['V_dc'] == 760 for p in PV) else 0, 100 * n_fsnl_hot))),
        load_335kW=dict(T_fem_Nm=round(float(T_load.mean()), 2), T_expected_Nm=round(-oR['P_em_kW'] * 1e3 / w, 2),
                        ripple_pp_pct=round(float(100 * (T_load.max() - T_load.min()) / abs(T_load.mean())), 2), ripple_6f_pct=round(float(100 * abs(Fq[6]) / abs(T_load.mean())), 2),
                        iron_loss=ld_iron, proximity=prox, newton_iters=LD['newton']),
        rotor_losses_335kW=dict(screen_W=round(ed['shield'], 1), shaft_W=round(ed['shaft'], 1), shaft_without_screen_W=round(ed_noshield['shaft'], 1),
                                per_harmonic=ed_per, mu_shaft_incremental=round(mu_sh, 1), magnets_by_segmentation_harmonic_W=mag_h,
                                magnets_slot_harmonics_W=mag_slot, slot_harmonic_gap_field_T={str(k): round(v, 5) for k, v in Bslot.items()},
                                magnets_unscreened_stepping_6_12_18f_W=mag_step,
                                stepping_note='magnetostatic stepping (no Cu-screen reaction) used only for the physical current-harmonic orders 6/12/18; '
                                              'higher orders in the sampled rotor-frame B are P1-mesh noise', chosen_segmentation=dict(n_circ=SEG[0], lamination_mm=SEG[1],
                                note='each 30 deg arc segment laminated from 2 mm axial slices bonded with an insulating epoxy layer (>= 1 kOhm between slices)'),
                                sleeve_note='CFRP: carbon fibres conduct along the hoop only; the axial current path is the resin (~1e2 S/m) -> < 5 W'),
        losses=losses, windage=wind, bearings=brg, short_circuit=sc, demagnetisation=demag,
        vs_preliminary=dict(e_pmg_json='sim/variant_e/e_pmg.json: stack 190, 10 turns, x 0.46 pu, V_dc 617 V at 335 kW (below a 400 V AFE window), windage 2.2 kW '
                                       '(factor 2 too high: P = 0.5 C_M pi rho w^3 R^4 L), no rotor eddy screen'),
        runtime_s=round(time.time() - t0))
    json.dump(out, open(os.path.join(HERE, 'eg_em.json'), 'w'), indent=1, default=float)
    print('-> sim/variant_e/eg_em.json  (%.0f s)' % (time.time() - t0))


if __name__ == '__main__':
    main()
