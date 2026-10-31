"""AURORA-1000 air inlet (phase 3): filter-house flange, plenum, radial inlet with the front-bearing struts and the bellmouth
to the impeller-1 eye; the cycle's assumed inlet loss (dp_inlet 1.0 %) is replaced by an assumed filter-house part and a
computed plenum + radial-inlet part.

The shaft and the high-speed coupling leave forward through the inlet, so the inlet is radial:
  plenum      welded steel box, split at the centre line (upper half carries the filter-house flange on top); its inner
              wall is a dry tunnel (r 290) round the front bearing housing FB-1 / FB-2 and the coupling, open to the front,
              at ambient pressure: all bearing services leave forward through it, none crosses the inlet air
  inlet casing one EN-GJS casting per half: hub wall (x 157, seals on the FB fairing face), front lip R40 into the tunnel,
              4 struts across the radial slot (45 / 135 / 225 / 315 deg, the split runs between them), shroud wall
              (x 204, = the plenum rear wall) with the bellmouth corner into the inducer shroud r 137.5, spigot nose into
              the compressor casing; the FB-2 centre-line feet bolt onto two brackets of the lower half
  eye         impeller-1 LE x 215, hub r 60 / shroud r 137.5 (sim/a1000_impeller_design.json), hub side = FB fairing
              INLET_HUB of cad/engine/a1000_rotor.py
Loss = filter house + silencer + inlet-air cooler (ASSUMED, vendor) + plenum + slot + struts + bend + bellmouth (steady
RANS of sim/cfd/a1000_inlet/make_case.py, OpenFOAM v2506, three meshes). The loss coefficient zeta is referred to the
eye dynamic head 0.5 rho c^2 (incompressible CFD at the eye density) and applied to the compressible eye head here.
Result (docs/08 sec. 20): design A zeta_eye 0.104 / 0.080 / 0.071 on 1.1 / 2.2 / 4.8 M cells (GCI 10 %), 560 Pa; the bend
is tight with the current rotor (58 mm from the hub wall to the LE for a 77.5 mm eye: tip inflow 20-40 deg inward, shroud
separation in the bladeless annulus). Rejected: bottom splitter (B), turning ring (C). What-if E (front bearings and
coupling 25 mm forward, a rotor change) halves the loss on the coarse mesh.
Frame: rotor frame mm (x = engine axis from the gearbox coupling face, z up, +theta from +y to +z = rotation).
Run:  ~/micromamba/envs/gr180/bin/python sim/engine/a1000_inlet.py      writes sim/engine/fea/a1000_inlet.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'sim'))

IMP = json.load(open(os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')))
C1 = json.load(open(os.path.join(HERE, 'fea', 'a1000_impeller_C1.json')))
CFD_RES = os.path.join(ROOT, 'sim', 'cfd', 'a1000_inlet', 'results.json')
RPM = 15000.0
G1 = IMP['stages']['C1']['geometry']

# ------------------------------------------------------------------------------------------------ gas path geometry
# hub side: the FB fairing (cad/engine/a1000_rotor.py INLET_HUB) from the hub wall (157, 150) to the impeller nose (205, 60);
# shroud side: radial wall at x 204, bellmouth corner into the inducer shroud r 137.5 that ends 1 mm before the LE
GEO = dict(
    x_le=G1['x_le'], r_eye_hub=G1['r1h'], r_eye_shr=G1['r1t'] + G1['clearance'], x_nose=G1['x0'],
    hub=[tuple(p) for p in IMP['inlet']['hub']],
    x_hub=157.0, x_shr=204.0,                          # hub wall (front) and shroud wall (rear, = plenum rear wall) planes
    corner=dict(kind='arc', R=10.0),                   # bellmouth corner on the shroud (design A: R10 of sec. 15.6)
    R_T=290.0, R_lip=40.0,                             # dry tunnel radius round FB-1 / FB-2 and the coupling, front lip radius
    struts=dict(n=4, theta0=45.0, r_le=240.0, r_te=165.0, t_c=0.21, t_te=2.0),     # symmetric, radial chord, axial span
    box=dict(x0=-140.0, x1=204.0, y0=-540.0, y1=540.0, z0=-620.0, z1=600.0),       # plenum inner faces; top = filter-house flange
    splitter=None,                                     # bottom splitter plate (y = 0 below the tunnel), only if CFD needs it
    duct_ext=400.0, x_out=400.0,                       # CFD only: duct stub above the flange, eye annulus to the outlet
)
GEO['x_end'] = GEO['x_le'] - 1.0                       # bellmouth tangent point (inducer shroud cylinder from here)
# envelope limits next to the plenum (phase 2: DN350 cold-air pipe at y 760 / z -360 with 30 mm insulation; lube module
# x <= -150 at y <= -450; gearbox flange r 370 at x <= -240; skid top z -700)
DESIGN = 'A'                                           # the design carried into the cycle (CFD mesh study)
# annular turning ring in the bend (design C): mean line radial at the slot mid-plane from r_le down to r_te + a_r, then a
# quarter ellipse (a_x = x_te - x_mid, a_r) to axial at (x_te, r_te); r_te splits the eye area in two halves; held by the
# 4 struts (r 165-240), which pass through it
RING = dict(x_mid=180.5, r_le=200.0, x_te=208.0, r_te=106.0, a_r=35.0, t=6.0, t_te=1.5, L_te=18.0)
# what-if E (needs a rotor / FB change, not in this phase): JB1 + thrust bearing + coupling 25 mm forward, so the FB rear
# wall and the hub wall move to x 132; the FB fairing is stretched axially from (157..205) to (132..205); the slot keeps
# its 47 mm width and the shroud corner grows to R35 (shroud wall x 179)
DX_E = 25.0
HUB_E = [(205.0 - (205.0 - x) * (205.0 - (157.0 - DX_E)) / (205.0 - 157.0), r) for x, r in GEO['hub']]
DESIGNS = dict(A=GEO, B=dict(GEO, splitter=dict(t=8.0)), C=dict(GEO, ring=RING),
               D=dict(GEO, ring=dict(RING, r_le=215.0, x_te=209.0, a_r=48.0, r_te=104.0)),
               E=dict(GEO, hub=HUB_E, x_hub=157.0 - DX_E, x_shr=204.0 - DX_E, corner=dict(kind='arc', R=10.0 + DX_E),
                      box=dict(GEO['box'], x1=204.0 - DX_E)))
DESIGN_NOTES = dict(A='4 struts, R10 shroud corner (sec. 15.6 contour), no splitter',
                    B='A + 8 mm bottom splitter plate (y = 0, plenum floor up to the slot entry radius)',
                    C='A + annular turning ring in the bend (mid-slot x 180.5 from r 200, quarter ellipse to x 208 / r 106)',
                    D='C with a longer, gentler ring: LE r 215, ellipse a_r 48 to x 209 / r 104 (stopped: C showed the limit)',
                    E='what-if: FB / thrust bearing 25 mm forward (rotor change): hub wall x 132, stretched fairing, shroud R35 at x 179')
ENVELOPE = dict(cold_pipe_y_min=760.0 - 355.6 / 2 - 30.0, lube_module_x_max=-150.0, gearbox_x_max=-240.0, skid_top_z=-700.0)

# filter house, inlet-air cooler and silencer (vendor; ASSUMED, flange-to-flange values at the design flow 5.3 m3/s)
FILTER_HOUSE = [  # (item, clean Pa, change-out Pa, note)
    ('weather hood, rain louvre, bird screen', 50.0, 50.0, '2.5 m/s face'),
    ('stage 1: F7 (ePM1 55 %) compact pocket filters', 90.0, 250.0, 'EN 779 / ISO 16890, change-out at 250 Pa'),
    ('stage 2: F9 (ePM1 85 %) V-cell filters', 130.0, 400.0, 'change-out at 400 Pa'),
    ('inlet-air cooler (chilled-water coil, 15 C off-coil) + droplet eliminator', 180.0, 180.0, '2.5 m/s face, wet coil'),
    ('inlet silencer (splitter)', 100.0, 100.0, 'vendor design value'),
    ('duct, transition and fabric joint to the plenum flange', 50.0, 50.0, '~12 m/s'),
]
FILTER_BASIS = 0.5                                     # rating basis: clean + 50 % of the filter rise (mid-life)
REFS = dict(
    filters='ISO 16890 / EN 779 F7 + F9 two-stage static filtration for gas turbines: clean 80-150 Pa per stage, change-out '
            '250-450 Pa (filter makers\' GT data); rating basis mid-life',
    plenum='Idelchik (2008) ch. 7: side-fed annular collecting chamber; radial-inlet practice: plenum velocity <= ~1/3 of the '
           'slot entry velocity, slot / eye area 2-3, rounded hub-side lip',
    struts='streamlined struts, Cd ~0.06-0.10 on the frontal area at Re ~1e5 (Hoerner 1965)',
    bend='accelerating 90 deg annular bend into the eye: K 0.03-0.08 on the eye head (radial inlets of centrifugal compressors)',
)


def corner_pts(g=GEO, n=24):
    """shroud bellmouth corner (x, r) from the radial wall to the inducer shroud cylinder, ending at x_end"""
    c = g['corner']; r_s = g['r_eye_shr']; xe = g['x_end']
    if c['kind'] == 'arc':
        R = c['R']; xc, rc = xe, r_s + R
        return [(xc - R * math.cos(t), rc - R * math.sin(t)) for t in [0.5 * math.pi * k / n for k in range(n + 1)]]
    # 'ellipse': semi-axes a_x (axial, = xe - x_shr) and a_r (radial); curvature radius a_r^2 / a_x at the wall,
    # a_x^2 / a_r at the shroud cylinder
    ax, ar = xe - g['x_shr'], c['a_r']
    return [(xe - ax * math.cos(t), r_s + ar - ar * math.sin(t)) for t in [0.5 * math.pi * k / n for k in range(n + 1)]]


def shroud_profile(g=GEO):
    """shroud side (x, r): plenum rear wall at the box edge -> radial wall -> corner -> inducer shroud to the LE"""
    c = corner_pts(g)
    return [(g['x_shr'], 520.0)] + c + [(g['x_le'], g['r_eye_shr'])]


def hub_profile(g=GEO, n=12):
    """hub side (x, r): tunnel cylinder -> front lip -> hub wall -> FB fairing -> impeller nose -> eye hub at the LE"""
    R, L = g['R_T'], g['R_lip']; xc, rc = g['x_hub'] - L, R - L
    lip = [(xc + L * math.sin(t), rc + L * math.cos(t)) for t in [0.5 * math.pi * k / n for k in range(n + 1)]]
    return [(g['box']['x0'], R)] + lip + list(g['hub']) + [(g['x_le'], g['r_eye_hub'])]


def strut_section(g=GEO, n=40):
    """symmetric strut section in the (r, s) plane, s = tangential offset [mm]: NACA 4-digit thickness from the LE (outer
    radius, the flow runs inward) to the TE (inner radius) with a t_te blunt TE; extruded across the slot (x)"""
    s = g['struts']; c = s['r_le'] - s['r_te']; t = s['t_c'] * c
    up = []
    for k in range(n + 1):
        xi = 0.5 * (1 - math.cos(math.pi * k / n))
        yt = 5 * t * (0.2969 * math.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1036 * xi ** 4) + 0.5 * s['t_te'] * xi
        up.append((s['r_le'] - c * xi, yt))
    return up, [(r, -q) for r, q in up]


def ring_section(g=GEO, n=24):
    """closed (x, r) outline of the turning ring: mean line offset by +-t/2 normal to it, round LE (at r_le, facing the
    inflow), TE tapered to t_te over the last L_te"""
    q = g['ring']; ax, ar = q['x_te'] - q['x_mid'], q['a_r']
    m = [(q['x_mid'], q['r_le'] - (q['r_le'] - q['r_te'] - ar) * k / n) for k in range(n)]
    m += [(q['x_te'] - ax * math.cos(t), q['r_te'] + ar - ar * math.sin(t)) for t in [0.5 * math.pi * k / n for k in range(n + 1)]]
    s = [0.0]
    for a, b in zip(m, m[1:]): s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    L = s[-1]; front, rear = [], []                                  # front: hub side (-x of the radial part), rear: shroud side
    for i, (x, r) in enumerate(m):
        j0, j1 = max(i - 1, 0), min(i + 1, len(m) - 1)
        tx, tr = m[j1][0] - m[j0][0], m[j1][1] - m[j0][1]; tl = math.hypot(tx, tr); nx, nr = tr / tl, -tx / tl   # left of the flow
        th = q['t'] if s[i] < L - q['L_te'] else q['t_te'] + (q['t'] - q['t_te']) * (L - s[i]) / q['L_te']
        front.append((x - 0.5 * th * nx, r - 0.5 * th * nr)); rear.append((x + 0.5 * th * nx, r + 0.5 * th * nr))
    le = [(q['x_mid'] - 0.5 * q['t'] * math.cos(t), q['r_le'] + 0.5 * q['t'] * math.sin(t)) for t in [math.pi * k / 8 for k in range(1, 8)]]
    if front[0][0] > rear[0][0]: front, rear = rear, front
    return [front[-1]] + front[::-1][1:] + le + rear + []


# ------------------------------------------------------------------------------------------------ flow along the path
def air_state():
    """design air: humid air 15 C / 90 % (design_chilled), flow of the impeller design, eye area"""
    import mw1_concept_study as G
    air = G.Mix(G.humid_air(288.15, 0.90, G.P_ATM))
    A1 = math.pi * (GEO['r_eye_shr'] ** 2 - GEO['r_eye_hub'] ** 2) * 1e-6
    return dict(m=IMP['ma'], T0=288.15, P_atm=G.P_ATM, R=air.R, cp=air.cp(288.15), A_eye=A1)


def eye_state(P0, a=None):
    """compressible eye state (uniform axial flow over A_eye) for the plenum total pressure P0"""
    a = a or air_state(); cp, R = a['cp'], a['R']; g = cp / (cp - R); T0 = a['T0']
    c = 120.0
    for _ in range(60):
        T = T0 - c * c / (2 * cp); p = P0 * (T / T0) ** (g / (g - 1)); rho = p / (R * T)
        c_new = a['m'] / (rho * a['A_eye'])
        if abs(c_new - c) < 1e-9: break
        c = c_new
    M = c / math.sqrt(g * R * T); mu = 1.458e-6 * T ** 1.5 / (T + 110.4)
    q_inc = 0.5 * rho * c * c
    return dict(c=c, T=T, p=p, rho=rho, M=M, q_inc=q_inc, q_comp=P0 - p, mu=mu, nu=mu / rho, gamma=g, P0=P0, T0=T0)


def filter_house():
    rows = [dict(item=i, clean_Pa=c, dirty_Pa=d, design_Pa=c + FILTER_BASIS * (d - c), note=n) for i, c, d, n in FILTER_HOUSE]
    tot = {k: sum(r[k] for r in rows) for k in ('clean_Pa', 'dirty_Pa', 'design_Pa')}
    return dict(rows=rows, total=tot, basis='clean + %.0f %% of the filter rise (mid-life)' % (100 * FILTER_BASIS))


def stations(P0):
    """1-D velocities along the path at the plenum total pressure P0 (incompressible at the local density estimate)"""
    a = air_state(); e = eye_state(P0, a); g = GEO; b = g['box']
    rho0 = P0 / (a['R'] * a['T0']); Q0 = a['m'] / rho0
    depth = (b['x1'] - b['x0']) * 1e-3
    out = dict(Q_plenum_m3_s=Q0, rho_plenum=rho0, eye=e)
    out['flange_m_s'] = Q0 / (depth * (b['y1'] - b['y0']) * 1e-3)
    out['side_gap_m_s'] = 0.25 * Q0 / (depth * (b['y1'] - g['R_T']) * 1e-3)        # a quarter of the flow passes z = 0 on each side
    w = (g['x_shr'] - g['x_hub']) * 1e-3
    for name, r in (('slot_entry', g['R_T'] - g['R_lip']), ('strut_le', g['struts']['r_le']), ('strut_te', g['struts']['r_te']),
                    ('bend_start', 150.0)):
        A = 2 * math.pi * r * 1e-3 * w
        if name.startswith('strut'):
            t = g['struts']['t_c'] * (g['struts']['r_le'] - g['struts']['r_te']) if name == 'strut_le' else g['struts']['t_te']
            A -= g['struts']['n'] * t * 1e-3 * w if name == 'strut_te' else 0.0
        out[name] = dict(r_mm=r, area_m2=A, c_m_s=Q0 / A * rho0 / rho0, area_ratio_eye=A / a['A_eye'])
    st = g['struts']; t = st['t_c'] * (st['r_le'] - st['r_te'])
    r_m = 0.5 * (st['r_le'] + st['r_te'])
    out['strut_blockage_max'] = st['n'] * t / (2 * math.pi * r_m)
    return out


def correlation_losses(P0):
    """1-D estimate for comparison with the CFD (Pa): plenum turning, lip entry, struts, bend + bellmouth, eye friction"""
    s = stations(P0); rho = s['rho_plenum']; e = s['eye']; st = GEO['struts']
    q = lambda c: 0.5 * rho * c * c
    t = st['t_c'] * (st['r_le'] - st['r_te']); r_m = 0.5 * (st['r_le'] + st['r_te'])
    c_m = s['Q_plenum_m3_s'] / (2 * math.pi * r_m * 1e-3 * (GEO['x_shr'] - GEO['x_hub']) * 1e-3)
    d = dict(plenum=1.0 * q(s['side_gap_m_s']),                                  # side-fed collecting chamber, ~1 head
             lip_entry=0.03 * q(s['slot_entry']['c_m_s']),                        # rounded lip r/b 0.85
             struts=st['n'] * 0.08 * t / (2 * math.pi * r_m) * q(c_m),            # drag of the 4 struts at the mid-chord speed
             bend=0.05 * e['q_inc'])                                              # accelerating bend + bellmouth corner
    d['total'] = sum(d.values()); d['zeta_eye'] = d['total'] / e['q_inc']
    return d


# ------------------------------------------------------------------------------------------------ struts: count, structure
def strut_count_check():
    """impeller-1 EO margins from the strut wakes / potential field: strong 1 x n (10 %), weak 2 x n (5 %) in the grid band
    14,700-15,300 rpm against the first three families of the C1 cyclic model (EO k excites ND k mod 13, folded)"""
    fr = {int(k): v for k, v in C1['freqs']['15000'].items()}; Z = 13
    out = {}
    for n in (3, 4, 5, 6, 7, 8):
        rows = []
        for k in (1, 2):
            eo = k * n; nd = eo % Z; nd = min(nd, Z - nd)
            worst = None
            for fam, f in enumerate(fr[nd][:3]):
                for rpm in (14700.0, 15300.0):
                    m_ = (eo * rpm / 60.0 - f) / f
                    if worst is None or abs(m_) < abs(worst[0]): worst = (m_, fam + 1, f, rpm)
            need = 0.10 if k == 1 else 0.05
            rows.append(dict(EO=eo, ND=nd, margin=worst[0], family=worst[1], f_Hz=worst[2], need=need, ok=abs(worst[0]) >= need))
        out[n] = dict(rows=rows, ok=all(r['ok'] for r in rows))
    return out


def strut_design():
    """loads and support stiffness of the front bearing housing on the inlet casing: FB-2 feet -> 2 brackets on the lower
    hub wall -> hub wall ring -> 4 struts (in shear across the 47 mm slot) -> shroud wall -> spigot nose / compressor casing"""
    rs = json.load(open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')))
    W = rs['bearings']['journal'][0]['W']                           # JB1 static load [N]
    m_fb = 40.0; m_cpl = 12.0                                       # FB-1 + FB-2 with pads and rings; half the HS coupling
    F_v = 5.0 * (W + (m_fb + m_cpl) * 9.81)                        # design: 5 x static (unbalance, seismic, handling)
    F_ax = 6.4e3                                                    # thrust upper bound, phase 1 (forward); aft worst 5.2 kN
    st = GEO['struts']; c = st['r_le'] - st['r_te']; t = st['t_c'] * c; h = GEO['x_shr'] - GEO['x_hub']
    E = 169e9; G_ = E / 2.6                                         # EN-GJS-400-18
    A_s = 0.68 * c * t * 1e-6                                       # NACA section area
    I_s = 0.035 * c * t ** 3 * 1e-12                                # bending about the chord line (thin axis)
    # vertical load: each strut is a fixed-fixed beam across the slot (span h); along its chord (radial) it is stiff
    # (strong axis + shear), across it (tangential) soft; struts at 45 deg share a vertical load by cos^2 / sin^2
    I_r = A_s * (c * 1e-3) ** 2 / 16.0                              # about the thickness axis (radial bending)
    k_beam = lambda I: 1.0 / (h ** 3 * 1e-9 / (12 * E * I) + h * 1e-3 / (G_ * A_s / 1.2))
    k_r, k_t = k_beam(I_r), k_beam(I_s)
    k_struts = sum(k_r * math.sin(math.radians(a_)) ** 2 + k_t * math.cos(math.radians(a_)) ** 2
                   for a_ in [st['theta0'] + 360.0 * k / st['n'] for k in range(st['n'])])
    tau = F_v / (4 * A_s / 1.2) / 1e6
    sig_ax = F_ax / (4 * A_s) / 1e6
    # brackets: FB-2 foot pads on 2 cantilevers from the hub wall (x 143 -> 55, 60 x 55 mm section); hub wall ring 16 mm
    Lb, bb, hb = 0.088, 0.055, 0.060
    k_br = 2 * 3 * E * (bb * hb ** 3 / 12) / Lb ** 3
    k_ring = 2.5e9                                                  # hub-wall ring between pads and struts (16 mm, ribbed), estimate
    k_ser = 1.0 / (1 / k_struts + 1 / k_br + 1 / k_ring)
    return dict(n=st['n'], theta_deg=[st['theta0'] + 360.0 * k / st['n'] for k in range(st['n'])], chord_mm=c, t_mm=t,
                span_mm=h, load_vertical_N=F_v, load_axial_N=F_ax, tau_MPa=tau, sigma_axial_MPa=sig_ax, k_struts_N_m=k_struts,
                k_brackets_N_m=k_br, k_ring_N_m=k_ring, k_support_N_m=k_ser, k_isfd_N_m=3.1e7, stiffness_ratio=k_ser / 3.1e7,
                services='none: the struts are solid. Oil supply (JB1, TB), buffer air, drain DN65, vent DN25 and the sensor '
                         'leads leave the front bearing housing forward through the dry tunnel (ambient, open at x -140), '
                         'so no line crosses the filtered air and no strut seal is needed')


def thermal():
    """cold part: inlet air 15 C (chilled) / up to 46 C (unchilled summer); FB housing ~60-70 C (oil drain)"""
    a = 11.0e-6; dT = 45.0
    return dict(dT_FB_vs_casing_K=dT, feet_span_growth_mm=a * dT * 2 * 185.0, spigot_r130_growth_mm=a * dT * 130.0,
                note='FB-2 feet: centre-line support; the foot bolts need slotted holes in y (or a bottom centre key) so the '
                     'housing grows sideways without moving the axis; hub-wall seal face on the FB fairing (r 130-150) has '
                     '0.5 mm radial clearance and a cord O-ring, it does not locate')


# ------------------------------------------------------------------------------------------------ CFD and the cycle
def cfd_result():
    """mesh study of sim/cfd/a1000_inlet (results.json): Richardson extrapolation over three meshes (ratio 1.33) when
    monotonic, else the fine value with the spread as the uncertainty"""
    if not os.path.exists(CFD_RES):
        return None
    R = json.load(open(CFD_RES)); z = {k: v['zeta_eye'] for k, v in R['meshes'].items()}
    out = dict(design=R.get('design'), meshes=R['meshes'], zeta=z, designs=R.get('designs', {}))
    if all(k in z for k in ('coarse', 'medium', 'fine')):
        z1, z2, z3 = z['fine'], z['medium'], z['coarse']; r = 4.0 / 3.0
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
    a = air_state(); fh = filter_house(); cfd = cfd_result()
    zeta = cfd['zeta_design'] if cfd else None
    corr = None
    dps = {}
    for case in ('clean', 'design', 'dirty'):
        dp_f = fh['total'][case + '_Pa']; P0 = a['P_atm'] - dp_f
        e = eye_state(P0, a)
        if corr is None: corr = correlation_losses(P0)
        z = zeta if zeta is not None else corr['zeta_eye']
        dp_ours = z * e['q_comp']
        dps[case] = dict(dp_filter_Pa=dp_f, dp_ours_Pa=dp_ours, dp_total_Pa=dp_f + dp_ours, dp_inlet=(dp_f + dp_ours) / a['P_atm'],
                         eye=e, zeta_eye=z)
    st = stations(a['P_atm'] - fh['total']['design_Pa'])
    out = dict(geometry=dict(GEO, shroud=shroud_profile(), hub_path=hub_profile(), strut_up=strut_section()[0],
                             strut_lo=strut_section()[1], envelope=ENVELOPE),
               air=a, stations=st, filter_house=fh, correlations=corr, cfd=cfd, zeta_used=zeta if zeta is not None else corr['zeta_eye'],
               zeta_source='CFD (%s)' % cfd['convergence'] if cfd else '1-D correlations (no CFD yet)',
               losses=dps, dps_new=dict(dp_inlet=dps['design']['dp_inlet']), dps_old=dict(dp_inlet=0.010),
               struts=dict(count=strut_count_check(), design=strut_design()), thermal=thermal(), refs=REFS)
    with open(os.path.join(HERE, 'fea', 'a1000_inlet.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    e = dps['design']['eye']
    print('eye: c %.1f m/s, M %.3f, rho %.4f, q_inc %.0f Pa, q_comp %.0f Pa (P0 %.0f Pa)' % (e['c'], e['M'], e['rho'], e['q_inc'],
                                                                                          e['q_comp'], e['P0']))
    print('plenum: Q %.2f m3/s, flange %.1f m/s, side gap %.1f m/s; slot entry %.1f m/s (A/A_eye %.2f), strut LE %.1f, TE %.1f, '
          'bend start %.1f m/s (A/A_eye %.2f); strut blockage %.1f %%'
          % (st['Q_plenum_m3_s'], st['flange_m_s'], st['side_gap_m_s'], st['slot_entry']['c_m_s'], st['slot_entry']['area_ratio_eye'],
             st['strut_le']['c_m_s'], st['strut_te']['c_m_s'], st['bend_start']['c_m_s'], st['bend_start']['area_ratio_eye'],
             100 * st['strut_blockage_max']))
    print('correlations: ' + ', '.join('%s %.0f Pa' % (k, v) for k, v in corr.items() if k != 'zeta_eye') + ', zeta_eye %.4f' % corr['zeta_eye'])
    print('zeta used %.4f (%s)' % (out['zeta_used'], out['zeta_source']))
    for case, d in dps.items():
        print('%-6s filter house %4.0f Pa + ours %4.0f Pa = %4.0f Pa -> dp_inlet %.3f %% (cycle 1.0 %%)'
              % (case, d['dp_filter_Pa'], d['dp_ours_Pa'], d['dp_total_Pa'], 100 * d['dp_inlet']))
    sc = out['struts']['count']
    print('strut count vs impeller-1 families: ' + ', '.join('%d %s (EO%d %+.0f %%)' % (n, 'ok' if v['ok'] else 'no', v['rows'][0]['EO'],
                                                                                       100 * v['rows'][0]['margin']) for n, v in sc.items()))
    sd = out['struts']['design']
    print('struts: chord %.0f, t %.1f, span %.0f mm; tau %.2f MPa, axial %.2f MPa; support k %.2e N/m = %.0f x ISFD'
          % (sd['chord_mm'], sd['t_mm'], sd['span_mm'], sd['tau_MPa'], sd['sigma_axial_MPa'], sd['k_support_N_m'], sd['stiffness_ratio']))


if __name__ == '__main__':
    main()
