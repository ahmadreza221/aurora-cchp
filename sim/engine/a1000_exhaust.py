"""AURORA-1000 exhaust (phase 2): diffuser with the JB2 rear-bearing frame, exhaust collector, compressor-air manifold and
the recuperator ducting; the cycle's assumed pressure losses are replaced by computed ones.

Station 4 is the R2 exit at the as-built design point (TIT at the R1 creep limit, docs/08 sec. 17). The gas path:
  frame       one hot casting (1.4848): outer cone (8.5 deg) + 4 cambered struts + hub (JB2 seat), floating on 7 radial pins
  bend        axial -> radial, hub R180 (concave), casing R120 (convex), then a radial diffuser out to r 500
  collector   box round the radial diffuser exit, open on the +y face (recuperator hot inlet hood, fabric joint)
The diffuser + collector loss is the steady RANS result of sim/cfd/a1000_exhaust/make_case.py (OpenFOAM v2506 on the
MacBook, three meshes); the ducts use the correlations named in DUCT_REFS.
Frame: rotor frame mm (x = engine axis from the gearbox coupling face, z up, +theta from +y to +z = rotation).
Run:  ~/micromamba/envs/gr180/bin/python sim/engine/a1000_exhaust.py      writes sim/engine/fea/a1000_exhaust.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'sim'))

OMEGA = 15000.0 * 2 * math.pi / 60
TUR = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
CFD_RES = os.path.join(ROOT, 'sim', 'cfd', 'a1000_exhaust', 'results.json')

# ------------------------------------------------------------------------------------------------ gas path geometry
# R2 TE x 865.25, hub r 200.43, tip r 262.99 (a1000_rotor.X_OFF + a1000_turbine annulus); R2 shroud ends at TE + 3
GEO = dict(
    x_in=868.0, r_hub=200.4, r_cas_in=264.0,          # exhaust inlet: hub flush with the R2 platform, casing 0.4 mm over the shroud
    cone_deg=8.5,                                      # casing half angle up to the bend (hub cylindrical)
    x_bend=1150.0, R_hub=180.0, R_cas=120.0,           # bend (design B of three, sec. 18.4): hub radius (concave), casing radius (convex)
    b_rad=80.0, r_exit=500.0, rear_rise=20.0,          # radial part: width at the bend exit, exit radius, rear-wall set-back
    struts=dict(n=4, theta0=0.0, x_le=920.0, chord=225.0, t_c=0.22, t_te=4.0, alpha_le=-12.0, r_in=180.0, r_out=330.0),
    box=dict(x0=1170.0, x1=1750.0, y0=-850.0, y1=700.0, z0=-580.0, z1=950.0),   # collector inner faces; +y face open
    out_ext=1000.0,                                    # CFD only: straight outlet duct beyond the +y face
)


GEO_A = dict(GEO, R_hub=130.0, R_cas=35.0, b_rad=95.0, r_exit=470.0, rear_rise=25.0,
             box=dict(x0=1110.0, x1=1650.0, y0=-800.0, y1=680.0, z0=-580.0, z1=900.0))     # first design (rejected, sec. 18)
GEO_C = dict(GEO, R_hub=180.0, R_cas=114.0, b_rad=66.0, r_exit=500.0, rear_rise=0.0)                 # third design (constant-area bend, rejected)


def derived(g=GEO):
    """bend and radial-wall points of the gas path [mm]"""
    ta = math.tan(math.radians(g['cone_deg'])); sa, ca = math.sin(math.radians(g['cone_deg'])), math.cos(math.radians(g['cone_deg']))
    hub_c = (g['x_bend'], g['r_hub'] + g['R_hub'])                 # hub arc centre
    x_rw = g['x_bend'] + g['R_hub']                                 # rear wall (hub side) at the bend exit
    x_fw = x_rw - g['b_rad']                                        # front wall (casing side), flat radial plane
    x_cb = x_fw - g['R_cas'] + g['R_cas'] * sa                      # casing bend start on the cone
    r_cb = g['r_cas_in'] + (x_cb - g['x_in']) * ta
    cas_c = (x_cb - g['R_cas'] * sa, r_cb + g['R_cas'] * ca)        # casing arc centre
    return dict(hub_c=hub_c, x_rw=x_rw, x_fw=x_fw, x_cb=x_cb, r_cb=r_cb, cas_c=cas_c, r_fw0=cas_c[1], r_rw0=hub_c[1],
                x_rw_exit=x_rw + g['rear_rise'], tan_cone=ta)


def r_cas(x, g=GEO):
    """casing radius on the cone"""
    return g['r_cas_in'] + (x - g['x_in']) * math.tan(math.radians(g['cone_deg']))


def profile(g=GEO, n_arc=24):
    """closed (x, r) polygon of the gas path (for areas / plots; the CFD and CAD use true arcs)"""
    d = derived(g); hx, hr = d['hub_c']; cx, cr = d['cas_c']
    p = [(g['x_in'], g['r_hub']), (g['x_bend'], g['r_hub'])]
    p += [(hx + g['R_hub'] * math.sin(t), hr - g['R_hub'] * math.cos(t)) for t in [0.5 * math.pi * k / n_arc for k in range(1, n_arc + 1)]]
    p += [(d['x_rw_exit'], g['r_exit']), (d['x_fw'], g['r_exit'])]
    a0 = math.radians(g['cone_deg'])
    p += [(cx + g['R_cas'] * math.sin(t), cr - g['R_cas'] * math.cos(t)) for t in
          [0.5 * math.pi - (0.5 * math.pi - a0) * k / n_arc for k in range(n_arc + 1)]]
    return p + [(g['x_in'], g['r_cas_in'])]


def strut_section(g=GEO, n=60):
    """cambered strut section in the (x, s) plane, s = tangential offset [mm] (+s = +theta): NACA 4-digit thickness with a
    t_te blunt trailing edge, parabolic-slope camber line from alpha_le (R2 exit swirl, -theta) to 0 deg (axial) at the TE"""
    s = g['struts']; c, t = s['chord'], s['t_c'] * s['chord']; ta = math.tan(math.radians(s['alpha_le']))
    up, lo = [], []
    for k in range(n + 1):
        xi = 0.5 * (1 - math.cos(math.pi * k / n))
        yt = 5 * t * (0.2969 * math.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1036 * xi ** 4) + 0.5 * s['t_te'] * xi
        yc = c * ta * (xi - 0.5 * xi ** 2); dy = ta * (1 - xi); ang = math.atan(dy)
        x = s['x_le'] + c * xi
        up.append((x - yt * math.sin(ang), yc + yt * math.cos(ang)))
        lo.append((x + yt * math.sin(ang), yc - yt * math.cos(ang)))
    return up, lo


# ------------------------------------------------------------------------------------------------ station 4 (R2 exit)
def r2_exit(dps=None):
    """R2 exit state at the as-built design point, TIT at the R1 creep limit. dps: cycle dp_* overrides (fractions).
    Returns mass flow, total / static state, axial velocity, swirl profile, Mach, dynamic head."""
    import a1000_performance as P
    import mw1_concept_study as G
    cur, ma, pm = P.asbuilt_case(5)                                 # meanline + compressor + turbine + combustor + bearings
    t_life = P.bisect(lambda t: P.LIFE_TARGET - P.r1_creep_life(t)[1], cur['TIT'] - 20, cur['TIT'] + 120)
    c = dict(cur, TIT=t_life, **(dps or {}))
    r = G.cycle(c, P.SITE)
    gp = r['gas']; T0 = r['T4']; P0 = r['P_back']
    m = ma * (1 - G.BASE['leak']) * (1 + r['far'])                  # turbine flow (leakage air re-joins later)
    cp = gp.cp(T0); R = gp.R; gam = cp / (cp - R)
    A = math.pi * (GEO['r_cas_in'] ** 2 - GEO['r_hub'] ** 2) * 1e-6
    sec = TUR['R2']['sections']
    rs = [q['r'] for q in sec]; span = [(r_ - rs[0]) / (rs[-1] - rs[0]) for r_ in rs]
    cx = 180.0
    for _ in range(60):                                           # c_x from continuity with the swirl of the R2 sections
        ct = [OMEGA * q['r'] * 1e-3 + cx * math.tan(math.radians(q['flow_out'])) for q in sec]
        ct_m = sum(ct) / len(ct)
        c2 = cx ** 2 + ct_m ** 2
        T = T0 - c2 / (2 * cp); p = P0 * (T / T0) ** (gam / (gam - 1)); rho = p / (R * T)
        cx_new = m / (rho * A)
        if abs(cx_new - cx) < 1e-6: break
        cx = cx_new
    alpha = [math.degrees(math.atan2(v, cx)) for v in ct]
    M = math.sqrt(c2 / (gam * R * T))
    mu = 1.458e-6 * T ** 1.5 / (T + 110.4)                         # Sutherland (air; lean flue gas within ~3 %)
    return dict(m_kg_s=m, m_air_kg_s=ma, T0_K=T0, P0_Pa=P0, T_K=T, p_Pa=p, rho=rho, cp=cp, R=R, gamma=gam, cx=cx,
                c_theta_mean=ct_m, swirl_span=span, swirl_deg=alpha, c_theta=ct, mach=M, q_Pa=0.5 * rho * c2, mu=mu, nu=mu / rho,
                area_m2=A, TIT_C=t_life - 273.15, T5_K=r['T5'], m_ex_kg_s=r['m_ex'] * ma, P_ATM=G.P_ATM, P2_Pa=r['P2'],
                T2_K=r['T2'], T2r_K=r['T2r'], T6_K=r['T6'], P3_Pa=r['P3'], cycle=r, gas=gp, air=r['air'])




# ------------------------------------------------------------------------------------------------ frame, manifold, layout
# compressor air leaves the hot-section channels through the scroll-casing rear-plate bore (r 322, x 903-928) into the
# manifold (bolted on the rear plate, 24 x M16 on r 535); the frame floats on 7 radial pins put in from outside through
# sleeves in the manifold into bosses on the frame (x 1085); the rim carries the rear leaf seal, the front leaf seal runs
# on the C2 rear face
MAN = dict(x0=928.0, x1=1100.0, r_o=500.0, t=14.0, rim_ri=340.0, rim_ro=400.0, rim_x=(1070.0, 1100.0), x_pin=1085.0, n_pin=8,
           d_pin=24.0, r_seal_front=283.0, r_seal_rear=330.0, shield_gap=10.0, r_bore=322.0, r_bolt=535.0, port=(150.0, 600.0))
MAN['pin_deg'] = [22.5 + 45.0 * k for k in range(8) if k != 7]  # 7 pins: none under the air port (-60..+9 deg)
MAN['n_pin'] = len(MAN['pin_deg'])
JB2_MOUNT = dict(r_ring_i=130.0, r_ring_o=150.0, r_hub_bore=185.0, n_key=8, key_w=16.0, x=(925.0, 985.0), x_brg=955.25,
                 pad=3.0)                                        # keys in through slots, 3 mm mica pad under each key (heat to JB2)
RECUP = dict(x0=-900.0, x1=1900.0, y0=1150.0, y1=2350.0, z0=-700.0, z1=900.0, moved_y=300.0)    # envelope, +300 mm in y
# duct centre lines [mm]; DN: (OD, ID) of schedule 10S pipe; elbow radius R/D per corner
DN = {125: (141.3, 134.5), 200: (219.1, 211.6), 350: (355.6, 336.6), 450: (457.0, 438.0), 800: (813.0, 797.0)}
TH_N = math.atan2(-360.0, 760.0)                                   # manifold port direction (+y, below the split line)
COLD_PIPE = dict(DN=350, pts=[(1017.0, MAN['r_o'] * math.cos(TH_N), MAN['r_o'] * math.sin(TH_N)), (925.0, 760.0, -360.0),
                              (-700.0, 760.0, -360.0), (-700.0, RECUP['y0'] - 30.0, -360.0)], RD=(1.0, 1.0), insul=30.0, x_bov=-450.0)
HOT_PIPE = dict(DN=450, pts=[(665.0, 590.0, 1140.0), (665.0, 1028.0, 1140.0), (665.0, 1028.0, 2050.0), (1500.0, 1650.0, 2050.0),
                             (1500.0, 1650.0, RECUP['z1'] + 30.0)], RD=(1.0, 1.0, 1.0), insul=50.0)
BOV_LINE = dict(DN=200, valve_DN=125, pts=[(-450.0, 760.0, -360.0), (-450.0, 760.0, 1050.0), (-450.0, RECUP['y0'], 1050.0)], RD=(1.5,))
STACK = dict(DN=800, x=-500.0, y=1750.0, z0=1500.0, z1=5000.0, econ=dict(x0=-900.0, x1=-100.0, z0=900.0, z1=1500.0))
DUCT_REFS = dict(
    friction='Darcy-Weisbach, Haaland (1983) friction factor, roughness 0.05 mm (drawn stainless / new steel pipe)',
    elbow='Crane TP-410 (2009): 90 deg long-radius elbow R/D 1.5, K = 14 f_T',
    tee_bellows='Idelchik (2008) diagram 7-21 (run of a tee, branch closed) K 0.05; EJMA: bellows with internal sleeve K 0.05',
    plenum='Idelchik (2008) ch. 7: annular collecting plenum with one side outlet, K 1.2 on the nozzle head; '
           'partly diffused entry 0.6 of the entry head (Idelchik ch. 5, short annular diffuser into a chamber)',
    channel_entry='Idelchik (2008) diagram 6-? (180 deg turn into an annular channel round a rounded flange) K 0.5 on the channel head',
    stack='exit loss 1.0 q, absorptive splitter silencer 150 Pa (vendor design value), stack draft (rho_amb - rho_gas) g H',
    recuperator='vendor flange-to-flange value, ASSUMED: air side 1.5 %, gas side 2.0 % of the inlet total pressure '
                '(primary-surface counterflow core at effectiveness 0.90; microturbine practice sum 3-5 %: McDonald 2003, '
                'Utriainen & Sunden 2002)',
    economizer='hot-water economizer gas side ASSUMED 500 Pa (finned tube, ~8 m/s face velocity; vendor to confirm)')


def haaland(Re, D, eps=0.05e-3):
    return (-1.8 * math.log10((eps / D / 3.7) ** 1.11 + 6.9 / Re)) ** -2


def path_len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def pipe_loss(m, rho, mu, dn, pts, RD=None, extra_K=0.0, extra=''):
    """straight lengths + an elbow at every interior corner (Crane: K = 14 f_T at R/D 1.5, 20 f_T at R/D 1) + extra K"""
    D = DN[dn][1] * 1e-3; A = math.pi / 4 * D ** 2; V = m / (rho * A); q = 0.5 * rho * V ** 2
    Re = rho * V * D / mu; f = haaland(Re, D); fT = haaland(1e8, D)
    L = path_len(pts) * 1e-3; n_el = len(pts) - 2; RD = RD or (1.5,) * n_el
    K_el = sum(14 * fT if rd >= 1.5 else 20 * fT for rd in RD[:n_el])
    K = f * L / D + K_el + extra_K
    return dict(V=V, q_Pa=q, Re=Re, f=f, L_m=L, elbows=n_el, K_elbows=K_el, K=K, dp_Pa=K * q, note=extra)


def strut_count_check():
    """R2 EO margins from the strut potential field (upstream of R2): strong 1x n (10 %), weak 2-4x n (5 %), in the grid
    band 14,700-15,300 rpm, against the first three blade-disc families of the R2 cyclic model"""
    R2 = json.load(open(os.path.join(HERE, 'fea', 'a1000_blisk_R2_cyclic.json')))
    fr = {int(k): v for k, v in R2['freqs'].items()}; Z = R2['Z']
    out = {}
    for n in (4, 5, 6, 7, 8):
        rows = []
        for k in (1, 2, 3, 4):
            eo = k * n; nd = eo % Z; nd = min(nd, Z - nd)
            if nd not in fr: nd_use = max(fr)                             # families are flat above ND 10 (asymptote)
            else: nd_use = nd
            worst = None
            for fam, f in enumerate(fr[nd_use][:3]):
                for rpm in (14700.0, 15300.0):
                    m_ = (eo * rpm / 60.0 - f) / f
                    if worst is None or abs(m_) < abs(worst[0]): worst = (m_, fam + 1, f, rpm)
            need = 0.10 if k == 1 else 0.05
            rows.append(dict(EO=eo, ND=nd, ND_used=nd_use, margin=worst[0], family=worst[1], f_Hz=worst[2], need=need, ok=abs(worst[0]) >= need))
        out[n] = dict(rows=rows, ok=all(r['ok'] for r in rows))
    return out


def strut_design(s):
    """services, cavity, load and support stiffness of the 4 struts (cast 1.4848 at ~680 C); JB2 seat and frame on radial
    keys (a key slides radially, so only the keys across the load direction carry it: k = n/2 x key bending stiffness)"""
    st = GEO['struts']; t = st['t_c'] * st['chord']; wall = 6.5; cav = t - 2 * wall
    services = {'+z (top)': 'oil supply DN15 (OD 21.3) to the JB2 inlet boss (pads + ISFD, ~10 l/min)',
                '-z (bottom)': 'the strut cavity itself is the JB2 oil drain (36 x ~120 mm, vertical, no buffer orifice), '
                               'short DN25 sleeve from the JB2 drain boss, DN50 drain from the strut root through the manifold',
                '-y': 'bearing-chamber vent DN25 (OD 33.7) to the oil-tank demister',
                '+y': 'sensor leads in a 12 mm conduit (2 proximity probes, 2 pad thermocouples, spare)',
                '+z, +y, -y': 'buffer / cooling air from the manifold, one d 4 mm orifice in each strut root (sec. buffer_air)'}
    W = 1664.0; hub = 35.0 * 9.81                                    # JB2 static load (a1000_rotor_stack.json), hub + housing weight
    F = 5.0 * (W + hub)                                             # design: 5 x static (unbalance, seismic, handling)
    A_sec = 2 * st['chord'] * 0.75 * wall * 1e-6                    # hollow section, two walls over ~75 % of the chord
    sig = F / (2 * A_sec) / 1e6                                     # two struts in line with the load
    E = 150e9; L = (r_cas(st['x_le'] + 0.3 * st['chord']) - GEO['r_hub']) * 1e-3
    k_frame = 2 * E * A_sec / L                                     # in-line pair (the cross pair adds bending, ignored)
    def keys(n, w, h, l): I = l * w ** 3 / 12 * 1e-12; return n / 2 * 3 * 200e9 * I / (h * 1e-3) ** 3
    k_jb2 = keys(JB2_MOUNT['n_key'], JB2_MOUNT['key_w'], JB2_MOUNT['r_hub_bore'] - JB2_MOUNT['r_ring_o'], 40.0)
    Ip = math.pi * (MAN['d_pin'] * 1e-3) ** 4 / 64
    k_rim = MAN['n_pin'] / 2 * 3 * 200e9 * Ip / ((MAN['rim_ri'] - 325.0) * 1e-3) ** 3     # pins across the load, 15 mm free span
    k_ser = 1 / (1 / k_frame + 1 / k_jb2 + 1 / k_rim)
    return dict(n=st['n'], chord_mm=st['chord'], t_mm=t, t_c=st['t_c'], cavity_mm=cav, wall_mm=wall, services=services,
                load_N=F, sigma_MPa=sig, k_frame_N_m=k_frame, k_jb2_keys_N_m=k_jb2, k_rim_keys_N_m=k_rim, k_support_N_m=k_ser,
                k_isfd_N_m=3.1e7, stiffness_ratio=k_ser / 3.1e7,
                blockage_max=st['n'] * t / (2 * math.pi * 0.5 * (GEO['r_hub'] + r_cas(st['x_le'] + 0.3 * st['chord']))))


def buffer_air(d_or=4.0, n_or=3, n_teeth=5, c_lab=(0.25, 0.5)):
    """hub-cavity buffer / cooling air: choked feed orifices from P2 in three strut roots; outflow through a 5-tooth
    labyrinth on the R2 rear flange (r 92, Martin) to the R2 rear cavity (~1.00 bar) and the hub-rear slip joint (rope
    packing ~10 mm2) to the collector (~1.03 bar). Returns feed flow and cavity pressure for the running clearances."""
    P2, T2, R, g = 3.79e5, 452.0, 287.0, 1.4
    A = n_or * math.pi / 4 * (d_or * 1e-3) ** 2
    mf = 0.8 * A * P2 * math.sqrt(g / (R * T2)) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    out = {}
    for c in c_lab:
        A_l = math.pi * 0.184 * c * 1e-3
        lo, hi = 1.01e5, 3.0e5
        for _ in range(60):
            pc = 0.5 * (lo + hi)
            q = A_l * pc / math.sqrt(R * 450.0) * math.sqrt((1 - (1.0e5 / pc) ** 2) / (n_teeth - math.log(1.0e5 / pc)))
            q += 0.65 * 10e-6 * math.sqrt(2 * pc / (R * 450.0) * max(pc - 1.03e5, 0.0))
            lo, hi = (pc, hi) if q < mf else (lo, pc)
        out['c_%.2f_mm' % c] = pc / 1e5
    return dict(orifices='%d x d %.1f mm' % (n_or, d_or), feed_g_s=1e3 * mf, feed_pct_air=100 * mf / 6.22, cavity_bar=out,
                labyrinth='%d teeth on the R2 rear flange r 92, honeycomb land in the hub front wall' % n_teeth,
                note='inside the 0.66 % joint share of the 1.5 % cycle leakage allowance (sec. 17)')


def frame_loads(s):
    """axial load on the floating frame: compressor air (P2) on its outer face between the two leaf seals against the gas
    side; shear in the 7 radial pins (half of them carry the load, conservative) with the weight and 5 x JB2 load"""
    dP = s['P2_Pa'] - s['p_Pa']
    F_air = dP * math.pi * ((MAN['r_seal_rear'] * 1e-3) ** 2 - (MAN['r_seal_front'] * 1e-3) ** 2)
    F_pin = math.hypot(F_air, 5 * (1664.0 + 120.0 * 9.81)) / (MAN['n_pin'] / 2)
    tau = F_pin / (math.pi / 4 * MAN['d_pin'] ** 2)
    return dict(dP_Pa=dP, F_axial_aft_N=F_air, F_pin_N=F_pin, tau_pin_MPa=tau)


def cold_side(s):
    """compressor delivery (collector exit) -> recuperator air inlet flange, and recuperator air outlet -> can nozzle"""
    from mw1_concept_study import P_ATM                               # noqa: F401
    air = s['air']; m = s['m_air_kg_s'] * (1 - 0.015)
    T2, P2 = s['T2_K'], s['P2_Pa']; rho2 = P2 / (air.R * T2); mu2 = 1.458e-6 * T2 ** 1.5 / (T2 + 110.4)
    HS = json.load(open(os.path.join(HERE, 'fea', 'a1000_hot_section.json')))['carriers']
    v1, v2 = HS['R1']['v_air'], HS['R2']['v_air']
    it = {}
    it['scroll casing -> C1 channel entry (turn round the casing front flange)'] = dict(K=0.5, q_Pa=0.5 * rho2 * v1 ** 2, note='channel_entry')
    it['C1 + C2 channels (sec. 14)'] = dict(K=None, q_Pa=None, dp_Pa=HS['R1']['dp_Pa'] + HS['R2']['dp_Pa'], note='a1000_hot_section.json')
    A_ann = math.pi * ((MAN['r_bore'] * 1e-3) ** 2 - ((r_cas(900.0) + 7 + MAN['shield_gap'] + 1.5) * 1e-3) ** 2)
    v_ann = m / (rho2 * A_ann)
    it['C2 exit -> manifold (annulus over the frame heat shield, partly diffused)'] = dict(K=0.6, q_Pa=0.5 * rho2 * v_ann ** 2, note='plenum', V=v_ann)
    D = DN[350][1] * 1e-3; v_n = m / (rho2 * math.pi / 4 * D ** 2)
    v_p = m / (rho2 * MAN['port'][0] * MAN['port'][1] * 1e-6)
    it['manifold -> port %.0f x %.0f -> rect-round elbow -> DN350 (collection 1.5 q, elbow 0.3 q)' % MAN['port']] = dict(K=1.8, q_Pa=0.5 * rho2 * v_n ** 2, note='plenum', V=v_n, V_port=v_p)
    p = pipe_loss(m, rho2, mu2, 350, COLD_PIPE['pts'][1:], RD=COLD_PIPE['RD'][1:], extra_K=0.05 + 0.05, extra='BOV tee run, pressure-balanced joint')
    it['cold pipe DN350 (%.1f m, R/D 1 elbow, BOV tee, pressure-balanced joint)' % p['L_m']] = p
    for v in it.values():
        if v.get('dp_Pa') is None: v['dp_Pa'] = v['K'] * v['q_Pa']
    dp_in = sum(v['dp_Pa'] for v in it.values())
    core = 0.015 * (P2 - dp_in)
    # hot air: recuperator outlet -> can nozzle flange (the nozzle dump is in the combustor budget, sec. 16.7)
    Th = s['T2r_K']; Ph = P2 - dp_in - core; rhoh = Ph / (air.R * Th); muh = 1.458e-6 * Th ** 1.5 / (Th + 110.4)
    hp = pipe_loss(m, rhoh, muh, 450, HOT_PIPE['pts'], RD=HOT_PIPE['RD'], extra_K=2 * 0.05, extra='two gimbal joints with sleeves')
    it_h = {'hot air pipe DN450 (%.1f m, 3 elbows R/D 1, gimbal pair)' % hp['L_m']: hp}
    ducts = dp_in + hp['dp_Pa']
    return dict(items=it, items_hot=it_h, core_Pa=core, ducts_Pa=ducts, total_Pa=ducts + core, P2_Pa=P2,
                dp_rec_c=(ducts + core) / P2, ducts_pct=100 * ducts / P2, core_pct=100 * core / P2, m_kg_s=m, rho2=rho2, V_annulus=v_ann)


def hot_side(s, zeta):
    """R2 exit -> stack exit: diffuser + collector (CFD), recuperator gas side (vendor), economizer (vendor), stack"""
    gp = s['gas']; m = s['m_ex_kg_s']
    dif = zeta * s['q_Pa']
    P_r = s['P0_Pa'] - dif
    core = 0.020 * P_r
    T_st = 363.15 + 5.0; rho_st = s['P_ATM'] / (gp.R * T_st); D = DN[800][1] * 1e-3; A = math.pi / 4 * D ** 2
    V = m / (rho_st * A); q = 0.5 * rho_st * V ** 2; mu = 1.458e-6 * T_st ** 1.5 / (T_st + 110.4)
    H = (STACK['z1'] - STACK['z0']) * 1e-3; f = haaland(rho_st * V * D / mu, D)
    rho_amb = s['P_ATM'] / (287.05 * 288.15)
    stack = f * H / D * q + 150.0 + 1.0 * q - (rho_amb - rho_st) * 9.81 * (STACK['z1'] - RECUP['z1']) * 1e-3
    econ = 500.0
    items = {'diffuser + struts + bend + radial diffuser + collector + transition (CFD)': dif,
             'recuperator gas side (vendor, assumed 2.0 %)': core, 'hot-water economizer (vendor, assumed)': econ,
             'stack DN800 + silencer + exit - draft': stack}
    total = sum(items.values())
    return dict(items_Pa=items, total_Pa=total, dp_exh=(dif + econ + stack) / s['P_ATM'], dp_rec_h=core / s['P_ATM'],
                stack=dict(V=V, q_Pa=q, H_m=H, draft_Pa=(rho_amb - rho_st) * 9.81 * (STACK['z1'] - RECUP['z1']) * 1e-3))


def volumes():
    """gas volumes for the phase-1 transient model (VOL A / B)"""
    man = math.pi * ((MAN['r_o'] * 1e-3) ** 2 - 0.300 ** 2) * (MAN['x1'] - MAN['x0']) * 1e-3
    cold = math.pi / 4 * (DN[350][1] * 1e-3) ** 2 * path_len(COLD_PIPE['pts']) * 1e-3
    hot = math.pi / 4 * (DN[450][1] * 1e-3) ** 2 * path_len(HOT_PIPE['pts']) * 1e-3
    mid = math.pi * 0.650 ** 2 * 0.473 - math.pi * (0.638 ** 2 - 0.455 ** 2) * 0.271 - math.pi * 0.392 ** 2 * 0.473    # scroll casing free volume (estimate)
    return dict(manifold_m3=man, cold_pipe_m3=cold, hot_pipe_m3=hot, scroll_casing_free_m3_est=mid,
                A_estimate_m3=man + cold + mid + 0.03, A_phase1_m3=0.9, B_ducts_m3=hot, B_phase1_m3=2.4,
                note='A = manifold + cold pipe + scroll-casing free volume (estimate) + compressor collector 0.03; B needs the '
                     'recuperator air-side volume from the vendor (+ hot pipe, can, scroll)')


def thermal():
    """cold -> hot displacements at the interfaces [mm] (20 C assembly). Frame 1.4848 alpha 17.5e-6 at 680 C, scroll /
    manifold casings EN-GJS / P355NH 12e-6 at 185 C, C2 1.4828 17e-6 at 500 C, collector 1.4828 17.5e-6 at 680 C"""
    aF, TF = 17.5e-6, 660.0; aC, TC = 12.0e-6, 165.0; a2, T2 = 17.0e-6, 480.0; D = derived()
    r = {}
    r['frame on the radial pins: radial slide'] = MAN['rim_ri'] * (aF * TF - aC * TC)
    c2_aft = (875.0 - 733.75) * a2 * T2; fr_fwd = (MAN['x_pin'] - 875.0) * aF * TF; pins = (MAN['x_pin'] - 733.75) * aC * TC
    r['front leaf seal on the C2 rear face: axial closure'] = c2_aft + fr_fwd - pins
    r['front leaf seal: radial slide'] = MAN['r_seal_front'] * (aF * TF - a2 * T2)
    r['rear leaf seal on the manifold rim: radial slide (pins 15 mm ahead, ~0 axial)'] = MAN['r_seal_rear'] * (aF * TF - aC * TC)
    eng = (MAN['x_pin'] - 200.0) * aC * TC
    r['frame rear end (x 1250) -> collector front ring: axial'] = eng + (D['x_fw'] - MAN['x_pin']) * aF * TF
    r['collector +y face (centre-line supported, keyed at y 0)'] = 680.0 * aF * TF
    r['cold pipe run 1.7 m: own growth'] = 1694.0 * aC * TC
    r['recuperator cold inlet relative to its rear fixed point (x 1700 -> -700, ~250 K mean rise)'] = 2400.0 * 17e-6 * 250.0
    r['hot air pipe own growth (1.4948 at 626 C)'] = path_len(HOT_PIPE['pts']) * 17.5e-6 * 606.0
    r['can nozzle up (scroll casing + can casing)'] = 772.0 * aC * TC + (1140.0 - 772.0) * 17.5e-6 * 600.0
    joints = [
        ('frame <-> manifold casing', '7 radial pins A286 dia 24 (x 1085), put in from outside through sleeves: centre + torque + 25 kN aft air load', 'radial %.1f' % r['frame on the radial pins: radial slide']),
        ('frame front <-> C2 rear face', 'leaf seal Haynes 25 (as CB-350), travel 4 mm', 'axial %.1f, radial %.1f' % (r['front leaf seal on the C2 rear face: axial closure'], r['front leaf seal: radial slide'])),
        ('frame <-> manifold rear rim', 'leaf seal Haynes 25, radial sliding', 'radial %.1f' % r['rear leaf seal on the manifold rim: radial slide (pins 15 mm ahead, ~0 axial)']),
        ('frame rear flange <-> collector front ring', 'spigot slip joint 25 mm engagement + ceramic rope', 'axial %.1f' % r['frame rear end (x 1250) -> collector front ring: axial']),
        ('collector -> recuperator gas inlet', 'rectangular fabric expansion joint 540 x 1480, 300 mm long', 'y %.0f + recuperator ~10, x ~%.0f' % (r['collector +y face (centre-line supported, keyed at y 0)'], 2400.0 * 17e-6 * 250.0 * 0.4)),
        ('cold pipe DN350', 'one pressure-balanced in-line joint (no thrust on the manifold)', 'axial %.0f' % (r['recuperator cold inlet relative to its rear fixed point (x 1700 -> -700, ~250 K mean rise)'] + eng - r['cold pipe run 1.7 m: own growth'])),
        ('hot air pipe DN450', 'gimbal pair (tied, takes the 3.6 bar thrust) in the 1.15 m vertical leg', 'pipe growth %.0f, nozzle up %.1f' % (r['hot air pipe own growth (1.4948 at 626 C)'], r['can nozzle up (scroll casing + can casing)'])),
        ('BOV dump line DN200', 'one tied lateral joint at the economizer inlet', 'small (cold except during a trip)'),
        ('recuperator gas outlet -> economizer / stack', 'fabric joint (vendor scope)', '~10')]
    return dict(displacements_mm=r, joints=joints)


def cfd_result():
    """mesh study of sim/cfd/a1000_exhaust (results.json from make_case.py --collect): Richardson extrapolation over the
    three meshes (ratio 1.33) when monotonic, else the fine value with the spread as the uncertainty"""
    if not os.path.exists(CFD_RES):
        return None
    R = json.load(open(CFD_RES)); z = {k: v['zeta_total'] for k, v in R['meshes'].items()}
    out = dict(meshes=R['meshes'], zeta=z)
    if all(k in z for k in ('coarse', 'medium', 'fine')):
        z1, z2, z3 = z["fine"], z["medium"], z["coarse"]; r = 4.0 / 3.0
        e21, e32 = z2 - z1, z3 - z2
        if e21 * e32 > 0 and abs(e21) > 1e-6:
            p = math.log(abs(e32 / e21)) / math.log(r); p = min(max(p, 0.5), 4.0)
            ext = z1 - e21 / (r ** p - 1); gci = 1.25 * abs(e21 / z1) / (r ** p - 1)
            out.update(order=p, zeta_extrapolated=ext, gci_fine=gci, zeta_design=z1, convergence='monotonic')
        else:
            out.update(zeta_design=z1, gci_fine=abs(max(z.values()) - min(z.values())) / z1, convergence='oscillatory')
    else:
        k = 'fine' if 'fine' in z else ('medium' if 'medium' in z else 'coarse')
        out.update(zeta_design=z[k], convergence='incomplete (%s only)' % ', '.join(z))
    return out


def main():
    cfd = cfd_result()
    zeta = cfd['zeta_design'] if cfd else 0.45
    s0 = r2_exit()
    dps = {}
    for _ in range(4):                                             # back pressure <-> station-4 density / dynamic head
        s = r2_exit(dps)
        hs = hot_side(s, zeta); cs = cold_side(s)
        dps = dict(dp_exh=hs['dp_exh'], dp_rec_h=hs['dp_rec_h'], dp_rec_c=cs['dp_rec_c'])
    sc = strut_count_check(); sd = strut_design(s); fl = frame_loads(s); th = thermal(); vol = volumes(); ba = buffer_air()
    import mw1_concept_study as G
    old = dict(dp_exh=G.BASE['dp_exh'], dp_rec_h=G.BASE['dp_rec_h'], dp_rec_c=G.BASE['dp_rec_c'])
    out = dict(station4=dict({k: v for k, v in s0.items() if k not in ('cycle', 'gas', 'air')}),
               station4_new=dict({k: v for k, v in s.items() if k not in ('cycle', 'gas', 'air')}),
               geometry=dict(GEO, derived=derived(), area_in_m2=s['area_m2'],
                             area_strut_te_m2=math.pi * ((r_cas(GEO['struts']['x_le'] + GEO['struts']['chord']) * 1e-3) ** 2 - (GEO['r_hub'] * 1e-3) ** 2),
                             area_exit_m2=2 * math.pi * GEO['r_exit'] * 1e-3 * (GEO['b_rad'] + GEO['rear_rise']) * 1e-3),
               cfd=cfd, zeta_used=zeta, hot=hs, cold=cs, dps_new=dps, dps_old=old, struts=dict(count=sc, design=sd), buffer_air=ba,
               frame=fl, manifold=MAN, jb2_mount=JB2_MOUNT, layout=dict(recuperator=RECUP, cold_pipe=COLD_PIPE, hot_pipe=HOT_PIPE,
               bov=BOV_LINE, stack=STACK), thermal=th, volumes=vol, refs=DUCT_REFS)
    out['geometry']['AR_exit'] = out['geometry']['area_exit_m2'] / s['area_m2']
    with open(os.path.join(HERE, 'fea', 'a1000_exhaust.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print('station 4 (R2 exit, TIT %.0f C): m %.3f kg/s, T0 %.0f K, P0 %.0f Pa, c_x %.1f, swirl %.1f..%.1f deg, M %.3f, q %.0f Pa'
          % (s['TIT_C'], s['m_kg_s'], s['T0_K'], s['P0_Pa'], s['cx'], min(s['swirl_deg']), max(s['swirl_deg']), s['mach'], s['q_Pa']))
    print('areas: in %.4f, strut TE %.4f, exit %.4f m2 (AR %.2f)' % (s['area_m2'], out['geometry']['area_strut_te_m2'],
                                                                   out['geometry']['area_exit_m2'], out['geometry']['AR_exit']))
    print('CFD zeta %.3f (%s)' % (zeta, cfd['convergence'] if cfd else 'no CFD yet, placeholder'))
    print('hot side [Pa]:'); [print('  %-75s %7.0f' % (k, v)) for k, v in hs['items_Pa'].items()]
    print('  total %.0f Pa: dp_exh %.4f (was %.3f), dp_rec_h %.4f (was %.3f)' % (hs['total_Pa'], dps['dp_exh'], old['dp_exh'], dps['dp_rec_h'], old['dp_rec_h']))
    print('cold side [Pa]:')
    for k, v in list(cs['items'].items()) + list(cs['items_hot'].items()):
        print('  %-75s %7.0f   (K %s, q %s)' % (k, v['dp_Pa'], '%.2f' % v['K'] if v.get('K') else '-', '%.0f' % v['q_Pa'] if v.get('q_Pa') else '-'))
    print('  recuperator air side (vendor, assumed 1.5 %%) %.0f Pa; ducts %.2f %% + core %.2f %% = dp_rec_c %.4f (was %.3f)'
          % (cs['core_Pa'], cs['ducts_pct'], cs['core_pct'], dps['dp_rec_c'], old['dp_rec_c']))
    print('struts: %s' % {n: v['ok'] for n, v in sc.items()})
    for r_ in sc[4]['rows']: print('  4 struts EO%d ND%d margin %+.1f %% (family %d, need %.0f %%)' % (r_['EO'], r_['ND'], 100 * r_['margin'], r_['family'], 100 * r_['need']))
    print('strut design: t %.1f mm, cavity %.1f, sigma %.1f MPa, support stiffness %.2e N/m (%.0f x ISFD)' % (sd['t_mm'], sd['cavity_mm'], sd['sigma_MPa'], sd['k_support_N_m'], sd['stiffness_ratio']))
    print('frame: air force aft %.1f kN, pin load %.1f kN, pin shear %.1f MPa' % (fl['F_axial_aft_N'] / 1e3, fl['F_pin_N'] / 1e3, fl['tau_pin_MPa']))
    print('volumes:', {k: round(v, 3) if isinstance(v, float) else v for k, v in vol.items() if k != 'note'})
    print('thermal [mm]:'); [print('  %-80s %6.1f' % (k, v)) for k, v in th['displacements_mm'].items()]


if __name__ == '__main__':
    main()
