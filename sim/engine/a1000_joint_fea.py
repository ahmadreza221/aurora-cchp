#!/usr/bin/env python3
"""AURORA-1000 phase 4: steady 3D FEA of the rotor joints (curvic couplings, bolted stud flanges) and of the ISFD rings.

Curvic couplings (all seven): CalculiX, C3D10, frictional surface-to-surface contact, cyclic sector
  compressor  stub - I1, I1 - spacer, spacer - I2, I2 - drum (36 teeth, central M42 tie bolt): one tooth pitch (10 deg)
              plus a hub segment on each side; the tie-bolt clamp is a load on the far face (a1000_rotor_stack.py states)
  turbine     drum - R1, R1 - spacer - R2, R2 - rear stub (48 teeth, 16 x M10 IN718 studs through the teeth): 3 teeth
              and 1 stud per 22.5 deg sector; the stud is a solid with a pre-tension section, fused into the threaded
              part over 0.4 d, nut bonded to the flange; R1 - R2 is one model with both curvic faces of the RT-107 ring
  Tooth form: Gleason-type flanks at 30 deg to the axis, constant whole depth h (cad/engine/a1000_rotor.py), straight
  radial teeth with half the circular pitch as the thickness at the pitch plane, root clearance 0.3 mm, root fillet,
  tip chamfer. (The CAD teeth are schematic: their tops sit on the opposite root land and the flanks do not touch.)
  Geometry is built in the "unrolled" space (x, r, s = r theta), where the flank and sector planes are planes, meshed by
  gmsh and mapped node by node (mid-side nodes included) to (x, r cos(s/r), r sin(s/r)): mating flanks are the image of
  the same plane on both parts, so they start closed. Matching (periodic) cyclic faces are tied by cylindrical equations.
  Load path per model (steps): assembly preload (a) -> axial / torsional stiffness increments -> 15,000 rpm at the
  design metal temperatures (b) -> 120 % overspeed 18,000 rpm (c) -> 15k + generator short-circuit torque 6 x rated (d)
  -> 15k + the bending moment of the 1st / 2nd critical passage at the damper clearance limit + 3 g (e), as the
  equivalent tension on the most loaded tooth (outer fibre, M r_o A / I). Far faces: the global radial growth of each
  body is prescribed there (thermal + centrifugal; blisk arm roots from the axisymmetric disc FEA), one side fixed in x
  and theta, the other carries clamp / thrust / torque.
  Reported per joint and case: flank pressure (mean, 99th percentile, max), stick / slip, tooth-root principal stress
  vs yield and LCF (start-stop range a -> b), coast-flank load left (separation margin), interface axial, bending and
  torsional stiffness (toothed model minus a solid-band reference), radial slip per start (fretting).
Bolted stud flanges: stud stress (mean + bending) vs yield and IN718 creep, flange opening, centring (no spigot: the
  radial teeth centre the parts; contact must stay on every tooth), fretting (slip per start and per revolution).
ISFD S-spring rings (JB1 / JB2): 2D plane-stress model (CPS6) of the ring as drawn (8 springs, webs with fillets);
  radial stiffness vs the rotor-dynamics value, spring stress at sag + orbit, Goodman, blade loss (damper bottomed),
  squeeze-film land and end-seal geometry.
Run:   python sim/engine/a1000_joint_fea.py --run <joint|all> [--level coarse|medium|fine]   (on the vast node, CCX=ccx)
       python sim/engine/a1000_joint_fea.py --isfd                                         (ISFD model)
       python sim/engine/a1000_joint_fea.py --post                                         (checks, JSON, plots)
Writes: sim/engine/fea/a1000_joint_fea.json, docs/img/a1000_joint_fea.png, docs/img/a1000_isfd_fea.png
"""
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_rotor as G                                       # noqa: E402  (geometry; G.RD = rotor dynamics, G.A = turbine)
sys.argv = _argv
RD = G.RD

CCX = os.environ.get('CCX', 'ccx')
RUNS = os.environ.get('A1000_P4_RUNS', os.path.join(ROOT, 'cad_out', 'fea_joints'))
OUT_JSON = os.path.join(HERE, 'fea', 'a1000_joint_fea.json')
STACK_JSON = os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')
DISC_FRD = os.path.join(ROOT, 'cad_out', 'fea_rotor', 'a1000_disc_%s_arms_%s.frd')
THREADS = int(os.environ.get('CCX_THREADS', 4))

N_OP, N_OS = 15000.0, 18000.0                                 # rated, 120 % overspeed
SC_FACTOR = 6.0                                               # generator short circuit: peak torque / rated
G_SHOCK = 3.0                                                 # gravity 1 g + 2 g allowance (as the rotor stack)
MU = 0.20                                                     # friction, ground flanks, dry (sensitivity 0.1 / 0.3)
K_PEN, K_STICK = 2.0e6, 1.0e5                                 # contact penalty / stick slope [N/mm3]
PHI = 30.0                                                    # curvic pressure angle (flank to the axis) [deg]
C_ROOT, RHO_F, TIP_CH = 0.30, float(os.environ.get('A1000_P4_RHO', 0.60)), 0.15   # root clearance, root fillet radius (ground;
                                                              # the R1.0 check run of drum_R1 sets A1000_P4_RHO=1.0), tip chamfer [mm]
STARTS_REQ = 10000


def om(N): return N * math.pi / 30.0


# ------------------------------------------------------------------------------------------------ materials
# E [MPa], mean CTE from 20 C [1/K], 0.2 % yield / UTS [MPa] (design minimum), density [t/mm3], Poisson, RA (LCF)
MAT = {
    'IN718':    dict(T=[20, 300, 500, 650], E=[200e3, 187e3, 177e3, 170e3], a=[12.8e-6, 13.5e-6, 14.0e-6, 14.4e-6],
                     Sy=[1030, 990, 960, 940], Su=[1240, 1170, 1130, 1100], rho=8.19e-9, nu=0.29, RA=0.25),
    'MAR-M247': dict(T=[20, 400, 600, 800], E=[200e3, 186e3, 176e3, 163e3], a=[11.0e-6, 12.6e-6, 13.4e-6, 14.4e-6],
                     Sy=[815, 790, 770, 740], Su=[965, 980, 1000, 900], rho=8.54e-9, nu=0.30, RA=0.06),
    'Ti64':     dict(T=[20, 150, 200, 300], E=[114e3, 107e3, 104e3, 98e3], a=[8.6e-6, 9.0e-6, 9.2e-6, 9.5e-6],
                     Sy=[825, 690, 640, 590], Su=[895, 780, 730, 690], rho=4.43e-9, nu=0.34, RA=0.25),
    '17-4PH':   dict(T=[20, 150, 300], E=[196e3, 191e3, 186e3], a=[10.8e-6, 11.0e-6, 11.3e-6],
                     Sy=[1000, 930, 880], Su=[1070, 1000, 950], rho=7.80e-9, nu=0.27, RA=0.35),
    '34CrNiMo6': dict(T=[20, 100, 200], E=[210e3, 205e3, 200e3], a=[11.5e-6, 12.0e-6, 12.5e-6],
                      Sy=[700, 670, 640], Su=[900, 870, 840], rho=7.85e-9, nu=0.29, RA=0.45),
    'Waspaloy': dict(T=[20, 540, 650, 760], E=[213e3, 185e3, 178e3, 170e3], a=[12.2e-6, 14.0e-6, 14.5e-6, 15.1e-6],
                     Sy=[795, 720, 690, 655], Su=[1240, 1140, 1100, 980], rho=8.19e-9, nu=0.30, RA=0.25),   # typical / AMS 5704 min
}


def mp(m, key, T): return float(np.interp(T, MAT[m]['T'], MAT[m][key]))


def manson(m, d_eps, T, s_max, s_mean=None):
    """LCF life [cycles]: Manson universal slopes + Morrow mean stress (default a 0 -> max -> 0 cycle, mean s_max / 2),
    factors 2 on strain / 20 on life (as sim/engine/a1000_turbine_checks.manson_cycles)"""
    Su, E = mp(m, 'Su', T), mp(m, 'E', T); D = -math.log(1 - MAT[m]['RA']); sm = 0.5 * s_max if s_mean is None else max(s_mean, 0.0)
    def N_of(de):
        lo, hi = 0.0, 12.0
        for _ in range(80):
            mid = 0.5 * (lo + hi); N = 10 ** mid
            if 3.5 * (Su - sm) / E * N ** -0.12 + D ** 0.6 * N ** -0.6 > de: lo = mid
            else: hi = mid
        return 10 ** lo
    return min(N_of(2 * d_eps), N_of(d_eps) / 20)


def u_disc(r, a, b, mat, T, N):
    """radial growth [mm] of a free rotating annular disc (plane stress, a..b) at r, thermal + centrifugal"""
    E, nu, rho = mp(mat, 'E', T), MAT[mat]['nu'], MAT[mat]['rho']; w2 = om(N) ** 2
    uc = rho * w2 / (8 * E) * r * ((3 + nu) * (1 - nu) * (a * a + b * b) + (3 + nu) * (1 + nu) * a * a * b * b / (r * r)
                                   - (1 - nu * nu) * r * r)
    return mp(mat, 'a', T) * (T - 20.0) * r + uc


# ------------------------------------------------------------------------------------------------ disc (blisk) arm roots
_DISC = {}


def disc_arm_growth(row, side, r, N):
    """radial growth [mm] of the cast blisk hub face at the arm root (r 58-66) from the axisymmetric disc FEA with arms
    (a1000_rotor_stack.py: cad_out/fea_rotor/a1000_disc_<row>_arms_<op|trip>.frd); thermal + centrifugal, the
    centrifugal part (op vs trip) scaled with N^2. side 'f' / 'a' = forward / aft hub face"""
    key = (row, side)
    if key not in _DISC:
        import e1_turbine_fea as F
        xf, xa = G.HUB[row]; xo = G.X_J['drum_R1'] if row == 'R1' else G.X_J['spc_R2']
        fits = {}
        for tag in ('op', 'trip'):
            nodes, bl = F.read_frd(DISC_FRD % (row, tag))
            U = [b for b in bl if b['name'].startswith('DISP')][-1]['data']
            y0 = min(p[1] for p in nodes.values())                     # local axial of the forward joint face
            yf = (xf if side == 'f' else xa) - xo + y0
            pts = [(p[0], U[n][0]) for n, p in nodes.items() if abs(p[1] - yf) < 1.2 and 57.0 < p[0] < 67.0]
            rr, uu = np.array(pts).T
            fits[tag] = np.polyfit(rr, uu, 1)
        _DISC[key] = fits
    f = _DISC[key]; uo, ut = np.polyval(f['op'], r), np.polyval(f['trip'], r)
    ucf = (ut - uo) / ((16500.0 / N_OP) ** 2 - 1.0)                   # centrifugal part at 15k
    if N <= 0: return 0.0 * r
    return uo + ucf * ((N / N_OP) ** 2 - 1.0)


# ================================================================================================ joint definitions
def stack():
    return json.load(open(STACK_JSON))


def joints():
    """the seven curvic interfaces in five models; parts as local axisymmetric segments (x, r) in the rotor frame"""
    tie = G.TIE; ch, cc = G.CURVIC_HOT, G.CURVIC_C; tf, rf = G.ARM['tf'], G.ARM['rf']
    hc = dict(stub_I1=2.4, I1_spc=3.0, spc_I2=2.6, I2_drum=3.2)        # CAD whole depths (a1000_rotor.build_rotor)
    xi1, xi2 = G.X_I1, G.X_I2; xj = G.X_J
    J = {}

    def comp(name, xp, ring, h, lo, hi, T_lo, T_hi, mat_lo, mat_hi, b_lo, b_hi):
        # lo / hi: (r_in, r_out, length) of the hub segment on each side; b_*: effective outer radius of the body for its
        # centrifugal growth (impellers: the radius that gives the FEA bore hoop stress, sec. 15.7)
        # an impeller hub segment (b beyond its own outer radius) grows like the whole impeller everywhere, not only at the
        # far cut: in-plane pseudo-expansion (cylindrical orthotropic, see write_deck), so the cut does not cone the segment
        J[name] = dict(kind='comp', N=ring['N'], n_sec=ring['N'], ri=ring['ri'], ro=ring['ro'], h=h, xp=xp,
                       parts=[dict(name='lo', mat=mat_lo, T=T_lo, poly=[(xp - h / 2 - lo[2], lo[0]), (xp - h / 2, lo[0]), (xp - h / 2, lo[1]),
                                                                       (xp - h / 2 - lo[2], lo[1])], far=xp - h / 2 - lo[2], b=b_lo, a=lo[0],
                                   disc=b_lo > lo[1] + 1.0, ro_seg=lo[1]),
                              dict(name='hi', mat=mat_hi, T=T_hi, poly=[(xp + h / 2, hi[0]), (xp + h / 2 + hi[2], hi[0]), (xp + h / 2 + hi[2], hi[1]),
                                                                       (xp + h / 2, hi[1])], far=xp + h / 2 + hi[2], b=b_hi, a=hi[0],
                                   disc=b_hi > hi[1] + 1.0, ro_seg=hi[1])],
                       curvics=[dict(xp=xp, ri=ring['ri'], ro=ring['ro'], N=ring['N'], h=h, lo=0, hi=1)], stud=None)
    b1, b2 = 198.0, 206.0                                             # Ti64 impellers: bore hoop 360 / 389 MPa at 15k
    comp('stub_I1', xi1[0], cc['stub_I1'], hc['stub_I1'], (23.0, 60.0, 24.0), (23.0, 60.0, 24.0), 60.0, 75.0, '34CrNiMo6', 'Ti64', 60.0, b1)
    # the front stub is a tube r 23-48 with a thin conical nose flare (r 48 at x 201 -> r 60 at x 203.5) under the outer
    # half of the tooth band (a1000_rotor.stub_profile): use the real outline, not a full ring
    xr = xi1[0] - hc['stub_I1'] / 2; sp_ = G.stub_profile(); x_fl = [p_ for p_ in sp_ if abs(p_[1] - 48.0) < 1e-6 and p_[0] > 190][0][0]
    J['stub_I1']['parts'][0].update(poly=[(xr - 24.0, 23.0), (xr, 23.0), (xr, 60.0), (xi1[0] - 1.5, 60.0), (x_fl, 48.0), (xr - 24.0, 48.0)],
                                    ro_seg=48.0, b=48.0)
    comp('I1_spc', xi1[1], cc['I1_spc'], hc['I1_spc'], (23.0, 76.0, 24.0), (23.0, 72.0, 24.0), 75.0, 120.0, 'Ti64', '17-4PH', b1, 75.0)
    comp('spc_I2', xi2[0], cc['spc_I2'], hc['spc_I2'], (23.0, 80.0, 24.0), (23.0, 80.0, 24.0), 120.0, 160.0, '17-4PH', 'Ti64', 80.0, b2)
    comp('I2_drum', xi2[1], cc['I2_drum'], hc['I2_drum'], (23.0, 90.0, 24.0), (50.0, 77.0, 24.0), 160.0, 230.0, 'Ti64', 'IN718', b2, 77.0)
    # hot joints: the cast blisk flange r 58-92 (9 mm) on its arm r 58-66 (13 mm cavity) to the hub face (far face);
    # drum flange r 50-92 on the drum neck r 50-60; rear-stub flange r 25-92 on its neck r 25(60)-60
    h = ch['h']
    def blisk_side(xp, sign, row, side):
        # sign +1: the blisk lies at x > xp; its root plane xp + h/2, flange back face xp + tf (CAD), arm root (hub face,
        # far face) xp + tf + cavity
        x0 = xp + sign * h / 2; x1 = xp + sign * tf; x2 = x1 + sign * G.ARM['cav']
        poly = [(x0, G.ARM['ri']), (x0, rf), (x1, rf), (x1, G.ARM['ro']), (x2, G.ARM['ro']), (x2, G.ARM['ri'])]
        if sign < 0: poly = poly[::-1]
        return dict(name=row, mat='MAR-M247', poly=poly, far=x2, row=row, side=side, a=G.ARM['ri'], back=x1)
    # drum - R1: drum (lo, threaded, studs from it) | R1 (hi, nuts aft of its flange in the cavity)
    xp = xj['drum_R1']
    drum = dict(name='drum', mat='IN718', far=xp - tf - 22.0, a=50.0, b=60.0,
                poly=[(xp - tf - 22.0, 50.0), (xp - h / 2, 50.0), (xp - h / 2, rf), (xp - tf, rf), (xp - tf, 60.0), (xp - tf - 22.0, 60.0)])
    J['drum_R1'] = dict(kind='hot', N=ch['N'], n_sec=G.STUD['n'], ri=ch['ri'], ro=ch['ro'], h=h, xp=xp, T=480.0,
                        parts=[dict(drum, T=480.0), dict(blisk_side(xp, +1, 'R1', 'f'), T=480.0)],
                        curvics=[dict(xp=xp, ri=ch['ri'], ro=ch['ro'], N=ch['N'], h=h, lo=0, hi=1)],
                        stud=dict(thread_part=0, nut_part=1, x_anchor=xp - h / 2 - 0.4 * G.STUD['d'], x_nut=xp + tf, dir=+1))
    # R1 - spacer - R2: R1 flange (lo, nut side, nut in front of it in the R1 aft cavity) | RT-107 ring | R2 flange (hi,
    # Heli-Coil, threaded)
    xa, xb = xj['R1_spc'], xj['spc_R2']; land = G.TSPC['land']
    ring = dict(name='spacer', mat='IN718', far=None, a=60.0, b=92.0,
                poly=[(xa + h / 2, 60.0), (xb - h / 2, 60.0), (xb - h / 2, rf), (xb - h / 2 - land, rf), (xb - h / 2 - land - 1.0, G.TSPC['ro']),
                      (xa + h / 2 + land + 1.0, G.TSPC['ro']), (xa + h / 2 + land, rf), (xa + h / 2, rf)])
    # phase 5 (docs/08 sec. 22): the interstage cavity runs ~730 C, so the RT-107 ring and the R1 - R2 studs / nuts are
    # Waspaloy with 20 kN preload (G.STUD_R12 when present)
    s12 = getattr(G, 'STUD_R12', dict(mat='Waspaloy', pre_kN=24.0)); T12 = 730.0      # (phase 5: 24 kN, 711 C steady)
    ring['mat'] = 'Waspaloy'
    J['R1_R2'] = dict(kind='hot', N=ch['N'], n_sec=G.STUD['n'], ri=ch['ri'], ro=ch['ro'], h=h, xp=xa, T=T12,
                      parts=[dict(blisk_side(xa, -1, 'R1', 'a'), T=T12), dict(ring, T=T12), dict(blisk_side(xb, +1, 'R2', 'f'), T=T12)],
                      curvics=[dict(xp=xa, ri=ch['ri'], ro=ch['ro'], N=ch['N'], h=h, lo=0, hi=1),
                               dict(xp=xb, ri=ch['ri'], ro=ch['ro'], N=ch['N'], h=h, lo=1, hi=2)],
                      stud=dict(thread_part=2, nut_part=0, x_anchor=xb + h / 2 + 0.4 * G.STUD['d'], x_nut=xa - tf, dir=-1,
                                mat=s12['mat'], pre_kN=s12['pre_kN']))
    # R2 - rear stub: R2 flange (lo, nut side) | rear stub (hi, threaded, studs from it)
    xp = xj['R2_stub']
    rs = dict(name='rear stub', mat='IN718', far=xp + tf + 14.0, a=25.0, b=60.0,
              poly=[(xp + h / 2, 25.0), (xp + tf + 14.0, 25.0), (xp + tf + 14.0, 50.0), (xp + tf + 3.0, 60.0),
                    (xp + tf, 60.0), (xp + tf, rf), (xp + h / 2, rf)])
    J['R2_stub'] = dict(kind='hot', N=ch['N'], n_sec=G.STUD['n'], ri=ch['ri'], ro=ch['ro'], h=h, xp=xp, T=485.0,     # phase 5: 470-500 C
                        parts=[dict(blisk_side(xp, -1, 'R2', 'a'), T=485.0), dict(rs, T=485.0)],
                        curvics=[dict(xp=xp, ri=ch['ri'], ro=ch['ro'], N=ch['N'], h=h, lo=0, hi=1)],
                        stud=dict(thread_part=1, nut_part=0, x_anchor=xp + h / 2 + 0.4 * G.STUD['d'], x_nut=xp - tf, dir=-1))
    return J


# mesh levels: flank / fillet / tooth body / far body element size [mm]
LEVELS = dict(coarse=dict(fl=0.70, fi=0.26, te=1.0, bo=3.0), medium=dict(fl=0.50, fi=0.18, te=0.8, bo=2.5),
              fine=dict(fl=0.35, fi=0.12, te=0.6, bo=2.0),
              hcoarse=dict(fl=1.00, fi=0.36, te=1.3, bo=3.5),                 # 3-tooth stud sectors (SPOOLES memory / time)
              hvcoarse=dict(fl=1.30, fi=0.48, te=1.7, bo=4.0, stud=1.7))


# ================================================================================================ geometry + mesh (gmsh)
# unrolled space: gmsh (X, Y, Z) = (x, r, s = r theta); planes through the x axis s = k r are the meridian planes theta = k
TAN = math.tan(math.radians(PHI))


def gap_poly(cv, part_is_lo, r, th_g):
    """(x, s) outline of one tooth gap of a part at radius r (gap centre angle th_g): root, straight flanks at PHI to the
    axis, tip chamfer at 60 deg, open above the tip"""
    N, h, xp = cv['N'], cv['h'], cv['xp']
    eb, et = -h / 2, h / 2 - C_ROOT; ec = et - TIP_CH
    g = lambda e: math.pi * r / (2 * N) + e * TAN
    gc = g(ec) + TIP_CH * math.tan(math.radians(60.0))
    pts = [(eb, -g(eb)), (eb, g(eb)), (ec, g(ec)), (et, gc), (et + 1.5, gc), (et + 1.5, -gc), (et, -gc), (ec, -g(ec))]
    sg = 1.0 if part_is_lo else -1.0
    return [(xp + sg * e, th_g * r + s) for e, s in pts]


def flank_test(cv, part_is_lo, th_list, x, r, s, tol=2e-3):
    """True if (x, r, s) lies on a straight contact flank of one of the gaps th_list of this part"""
    N, h, xp = cv['N'], cv['h'], cv['xp']
    e = (x - xp) if part_is_lo else (xp - x)
    eb, ec = -h / 2, h / 2 - C_ROOT - TIP_CH
    if not (eb + RHO_F * math.tan(math.radians(30.0)) * math.cos(math.radians(PHI)) - 1e-3 <= e <= ec + 1e-3): return False
    g = math.pi * r / (2 * N) + e * TAN
    return any(abs(abs(s - t * r) - g) < tol for t in th_list)


def stud_section(a, n=48):
    """preimage in the (r, s) plane of a circle of radius a around (r 76, theta 0): closed list of (r, s)"""
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n; y, z = G.STUD['r'] + a * math.cos(t), a * math.sin(t)
        r = math.hypot(y, z); out.append((r, r * math.atan2(z, y)))
    return out


def _curves_of(v):
    import gmsh
    cs = set()
    for _, sf in gmsh.model.getBoundary(v, combined=False, oriented=False):
        for _, c in gmsh.model.getBoundary([(2, sf)], combined=False, oriented=False): cs.add(abs(c))
    return sorted(cs)


def _samples(tag, n=4):
    import gmsh
    lo, hi = gmsh.model.getParametrizationBounds(2, tag)
    uv = []
    for a in np.linspace(0.15, 0.85, n):
        for b in np.linspace(0.15, 0.85, n): uv += [lo[0] + (hi[0] - lo[0]) * a, lo[1] + (hi[1] - lo[1]) * b]
    return np.array(gmsh.model.getValue(2, tag, uv)).reshape(-1, 3)


def build_mesh(name, J, level, solid_band=False):
    """gmsh model of joint J in the unrolled space (x, r, s); returns nodes (real space), tets, part of each tet and the
    surface sets {name: [(tri corner nodes...)]} / node sets"""
    import gmsh
    L = LEVELS[level]
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0); gmsh.option.setNumber('General.NumThreads', THREADS)
    gmsh.model.add(name); occ = gmsh.model.occ
    th = math.pi / J['n_sec']                                          # sector half angle
    pitch = 2 * math.pi / J['N']
    lo0 = 0.0 if J['kind'] == 'comp' else pitch / 2                    # lo-part tooth at theta 0 (comp) / 3.75 deg (hot)
    xs = [x for p in J['parts'] for x, _ in p['poly']]; x_lo, x_hi = min(xs) - 15, max(xs) + 15
    rmax = 100.0; S = th * rmax + 5.0

    def wedge():
        a = math.atan(th)                                            # the plane s = th r (theta = th)
        b1 = occ.addBox(x_lo, -2 * rmax, -4 * S, x_hi - x_lo, 4 * rmax, 4 * S); occ.rotate([(3, b1)], 0, 0, 0, 1, 0, 0, a)
        b2 = occ.addBox(x_lo, -2 * rmax, 0.0, x_hi - x_lo, 4 * rmax, 4 * S); occ.rotate([(3, b2)], 0, 0, 0, 1, 0, 0, -a)
        w, _ = occ.intersect([(3, b1)], [(3, b2)]); return w

    def gaps_of(part_is_lo):
        base = lo0 + (0.5 * pitch if part_is_lo else 0.0)             # gap centres of the lo part lie between its teeth
        k0 = int(math.floor(-th / pitch)) - 1; k1 = int(math.ceil(th / pitch)) + 1
        return [base + k * pitch for k in range(k0, k1 + 1)]

    def gap_prism(cv, part_is_lo, th_g):
        wires = []
        for r in (cv['ri'] - 1.0, cv['ro'] + 1.0):
            pp = [occ.addPoint(x, r, s) for x, s in gap_poly(cv, part_is_lo, r, th_g)]
            wires.append(occ.addWire([occ.addLine(pp[i], pp[(i + 1) % len(pp)]) for i in range(len(pp))]))
        v = occ.addThruSections(wires, makeSolid=True, makeRuled=True)
        occ.synchronize()
        xb = cv['xp'] + (-1 if part_is_lo else 1) * cv['h'] / 2
        edges = [c for c in _curves_of(v) if (lambda bb: abs(bb[0] - xb) < 1e-6 and abs(bb[3] - xb) < 1e-6 and
                                                 bb[4] - bb[1] > cv['ro'] - cv['ri'])(gmsh.model.getBoundingBox(1, c))]
        assert len(edges) == 2, edges
        return occ.fillet([v[0][1]], edges, [RHO_F], removeVolume=True)

    def section_prism(a, xa, xb_):
        pp = [occ.addPoint(min(xa, xb_), r, s) for r, s in stud_section(a)]
        ff = occ.addPlaneSurface([occ.addCurveLoop([occ.addSpline(pp + [pp[0]])])])
        return [e for e in occ.extrude([(2, ff)], abs(xb_ - xa), 0, 0) if e[0] == 3]

    vols = []
    for ip, P in enumerate(J['parts']):
        pts = [occ.addPoint(x, r, -S) for x, r in P['poly']]
        f = occ.addPlaneSurface([occ.addCurveLoop([occ.addLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))])])
        body = [e for e in occ.extrude([(2, f)], 0, 0, 2 * S) if e[0] == 3]
        for cv in J['curvics']:
            for is_lo, idx in ((True, cv['lo']), (False, cv['hi'])):
                if idx != ip: continue
                xb = cv['xp'] + (-1 if is_lo else 1) * cv['h'] / 2
                xt = cv['xp'] + (1 if is_lo else -1) * (cv['h'] / 2 - C_ROOT)
                if solid_band:                                       # reference: the lo part fills the band solid
                    if not is_lo: continue
                    xt = cv['xp'] + cv['h'] / 2
                band = [(3, occ.addBox(min(xb, xt), cv['ri'], -S, abs(xt - xb), cv['ro'] - cv['ri'], 2 * S))]
                if not solid_band:
                    pr = []
                    for tg in gaps_of(is_lo): pr += gap_prism(cv, is_lo, tg)
                    band, _ = occ.cut(band, pr)
                body, _ = occ.fuse(body, band)
        body, _ = occ.intersect(body, wedge())
        if J['stud']:
            st = J['stud']; xs_ = [x for x, _ in P['poly']]
            if ip == st['thread_part']:                               # clearance hole through the band, 0.4 d into the body
                xr = [cv['xp'] + (-1 if cv['lo'] == ip else 1) * cv['h'] / 2 for cv in J['curvics'] if ip in (cv['lo'], cv['hi'])][0]
                far_side = 1 if st['x_anchor'] > xr else -1
                hx0, hx1 = sorted((st['x_anchor'], xr - far_side * 4.0))
            else:
                hx0, hx1 = min(xs_) - 4.0, max(xs_) + 4.0
            body, _ = occ.cut(body, section_prism(G.STUD['hole'] / 2, hx0, hx1))
        vols.append([t for _, t in body])
    stud_vols = []
    if J['stud']:
        st = J['stud']; d_eq = math.sqrt(4 * 61.2 / math.pi)         # MJ10x1.25 stress area 61.2 mm2
        sv = section_prism(d_eq / 2, st['x_anchor'], st['x_nut'] + st['dir'] * (G.STUD['nut_h'] + 2.0))
        nut = section_prism(7.0, st['x_nut'], st['x_nut'] + st['dir'] * G.STUD['nut_h'])
        sv, _ = occ.fuse(sv, nut)
        xpre = 0.5 * (st['x_anchor'] + st['x_nut'])
        disk = occ.addDisk(xpre, G.STUD['r'], 0.0, 5.0, 5.0, zAxis=[1, 0, 0], xAxis=[0, 1, 0])
        _, mp_ = occ.fragment(sv, [(2, disk)])
        sv = [e for e in mp_[0] if e[0] == 3] + [e for m in mp_[1:len(sv)] for e in m if e[0] == 3]
        tp = st['thread_part']; n_tp = len(vols[tp])
        _, mp_ = occ.fragment([(3, t) for t in vols[tp]], sv)
        vols[tp] = [t for m in mp_[:n_tp] for _, t in m]
        stud_vols = sorted(set(t for m in mp_[n_tp:] for _, t in m) - set(vols[tp]))
    occ.synchronize()
    stray = [(2, t) for _, t in gmsh.model.getEntities(2) if not gmsh.model.getAdjacencies(2, t)[0].size]
    if stray: occ.remove(stray, recursive=True); occ.synchronize()
    # ------------------------------------------------------------------ classify surfaces
    surf = {}                                                         # name -> [surface tags]
    def add(k, t): surf.setdefault(k, []).append(t)
    flank_s, fillet_s = [], []
    part_surfs = []
    def plane_of(t):
        c = np.array(occ.getCenterOfMass(2, t))
        try:
            uv = gmsh.model.getParametrization(2, t, list(c)); return c, np.array(gmsh.model.getNormal(t, list(uv)))
        except Exception:
            return c, np.array([0.0, 0.0, 0.0])
    def on_plane(c, nrm, grad, val):
        g = np.array(grad, float); g /= np.linalg.norm(g)
        return abs(val) < 1e-4 * max(1.0, abs(c[1])) and abs(abs(np.dot(g, nrm)) - 1.0) < 1e-6
    for ip, vv in enumerate(vols):
        ss = sorted(set(abs(t) for _, t in gmsh.model.getBoundary([(3, v) for v in vv], combined=True, oriented=False)))
        part_surfs.append(ss)
        far = J['parts'][ip].get('far')
        for t in ss:
            c, nrm = plane_of(t); x, r, s_ = c
            if on_plane(c, nrm, (0, th, 1), s_ + th * r): add('cycL_%d' % ip, t); continue
            if on_plane(c, nrm, (0, -th, 1), s_ - th * r): add('cycR_%d' % ip, t); continue
            if far is not None and on_plane(c, nrm, (1, 0, 0), x - far): add('far_%d' % ip, t); continue
            hit = False
            for k, cv in enumerate(J['curvics']):
                for is_lo, idx in ((True, cv['lo']), (False, cv['hi'])):
                    if idx != ip: continue
                    sg = 1.0 if is_lo else -1.0; e = sg * (x - cv['xp'])
                    if not (-cv['h'] / 2 + 0.2 < e < cv['h'] / 2 - C_ROOT - TIP_CH - 0.05): continue
                    for tg in gaps_of(is_lo):
                        for sd in (1, -1):                  # flank: s - tg r - sd (pi r / 2N + e tan) = 0
                            q = math.pi / (2 * cv['N'])
                            if on_plane(c, nrm, (-sd * sg * TAN, -tg - sd * q, 1), s_ - tg * r - sd * (q * r + e * TAN)):
                                add('%s_%d' % ('slave' if is_lo else 'master', k), t); flank_s.append(t); hit = True
            if hit: continue
            if solid_band and abs(abs(nrm[0]) - 1.0) < 1e-6:
                for k, cv in enumerate(J['curvics']):
                    if abs(x - (cv['xp'] + cv['h'] / 2)) < 1e-6 and cv['ri'] - 1e-3 < r < cv['ro'] + 1e-3 and ip in (cv['lo'], cv['hi']):
                        add('%s_%d' % ('tieM' if ip == cv['lo'] else 'tieS', k), t)
            if abs(nrm[0]) < 0.99 and any(abs(x - (cv['xp'] + sg * cv['h'] / 2)) < RHO_F + 0.05 and cv['ri'] - 1.1 < r < cv['ro'] + 1.1
                                          for cv in J['curvics'] for sg in (-1, 1)):
                add('fillet_%d' % ip, t); fillet_s.append(t)
        if J['stud'] and ip == J['stud']['nut_part']:
            xn = J['stud']['x_nut']
            for t in ss:
                bb = gmsh.model.getBoundingBox(2, t)
                if abs(bb[0] - xn) < 1e-3 and abs(bb[3] - xn) < 1e-3: add('nutseat', t)
    if J['stud']:
        xn = J['stud']['x_nut']; xpre = 0.5 * (J['stud']['x_anchor'] + xn)
        ss = sorted(set(abs(t) for _, t in gmsh.model.getBoundary([(3, v) for v in stud_vols], combined=False, oriented=False)))
        for t in ss:
            bb = gmsh.model.getBoundingBox(2, t)
            if abs(bb[0] - xn) < 1e-3 and abs(bb[3] - xn) < 1e-3: add('nutface', t)
            if abs(bb[0] - xpre) < 1e-3 and abs(bb[3] - xpre) < 1e-3: add('pre', t)
    # ------------------------------------------------------------------ periodic cyclic faces (affine s -> s + 2 th r)
    T = [1, 0, 0, 0, 0, 1, 0, 0, 0, 2 * th, 1, 0, 0, 0, 0, 1]
    for ip in range(len(vols)):
        Ls, Rs = surf.get('cycL_%d' % ip, []), surf.get('cycR_%d' % ip, [])
        def key(t, shift):
            c = np.array(gmsh.model.occ.getCenterOfMass(2, t)); c[2] += shift * 2 * th * c[1]; return c
        for tl in Ls:
            cl = key(tl, 1)
            tr = min(Rs, key=lambda t: np.linalg.norm(key(t, 0) - cl))
            if np.linalg.norm(key(tr, 0) - cl) > 1e-3: raise RuntimeError('no periodic partner for surface %d' % tl)
            gmsh.model.mesh.setPeriodic(2, [tr], [tl], T)
    # ------------------------------------------------------------------ size fields
    fm = gmsh.model.mesh.field
    def thr(sfs, hmin, d0, d1):
        fd = fm.add('Distance'); fm.setNumbers(fd, 'SurfacesList', sfs); fm.setNumber(fd, 'Sampling', 30)
        ft = fm.add('Threshold'); fm.setNumber(ft, 'InField', fd)
        for k, v in (('SizeMin', hmin), ('SizeMax', L['bo']), ('DistMin', d0), ('DistMax', d1)): fm.setNumber(ft, k, v)
        return ft
    fl = [thr(flank_s, L['fl'], 0.3, 4.0), thr(fillet_s, L['fi'], 0.25, 3.0)]
    bx = fm.add('Box')
    xb = [cv['xp'] for cv in J['curvics']]
    for k, v in (('VIn', L['te']), ('VOut', L['bo']), ('XMin', min(xb) - J['h'] - 1), ('XMax', max(xb) + J['h'] + 1),
                 ('YMin', J['ri'] - 2), ('YMax', J['ro'] + 2), ('ZMin', -S), ('ZMax', S)):
        fm.setNumber(bx, k, v)
    fl.append(bx)
    if J['stud']:
        fs = fm.add('Box')
        for k, v in (('VIn', L.get('stud', 1.0)), ('VOut', L['bo']), ('XMin', -1e4), ('XMax', 1e4), ('YMin', G.STUD['r'] - 8), ('YMax', G.STUD['r'] + 8),
                     ('ZMin', -8), ('ZMax', 8)): fm.setNumber(fs, k, v)
        fl.append(fs)
    fmin = fm.add('Min'); fm.setNumbers(fmin, 'FieldsList', fl); fm.setAsBackgroundMesh(fmin)
    for k, v in (('Mesh.MeshSizeExtendFromBoundary', 0), ('Mesh.MeshSizeFromPoints', 0), ('Mesh.MeshSizeFromCurvature', 0),
                 ('Mesh.ElementOrder', 2), ('Mesh.SecondOrderLinear', 0), ('Mesh.OptimizeNetgen', 1), ('Mesh.Algorithm3D', 10)):
        gmsh.option.setNumber(k, v)
    gmsh.model.mesh.generate(3)
    # ------------------------------------------------------------------ extract
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    nid = {int(t): i for i, t in enumerate(nt)}
    tets, tpart = [], []
    allv = [(ip, v) for ip, vv in enumerate(vols) for v in vv] + [(len(vols), v) for v in stud_vols]
    for ip, v in allv:
        et, etag, en = gmsh.model.mesh.getElements(3, v)
        for k, typ in enumerate(et):
            if typ != 11: continue
            e = np.array(en[k], dtype=np.int64).reshape(-1, 10)
            tets.append(e); tpart += [ip] * len(e)
    tets = np.vstack(tets)
    faces = {}
    for k, tags in surf.items():
        tri = []
        for t in tags:
            et, _, en = gmsh.model.mesh.getElements(2, t)
            for j, typ in enumerate(et):
                if typ == 9: tri.append(np.array(en[j], dtype=np.int64).reshape(-1, 6))
        faces[k] = np.vstack(tri) if tri else np.zeros((0, 6), np.int64)
    gmsh.finalize()
    # map to the real space: (x, r, s) -> (x, r cos(s / r), r sin(s / r))
    x, r, s = xyz[:, 0], xyz[:, 1], xyz[:, 2]; t_ = s / r
    X = np.column_stack([x, r * np.cos(t_), r * np.sin(t_)])
    return dict(tags=np.asarray(nt, dtype=np.int64), X=X, U=xyz, tets=tets, tpart=np.array(tpart), faces=faces, th=th,
                n_parts=len(vols))


# ================================================================================================ loads
_STACK_MOD = None


def stack_mod():
    global _STACK_MOD
    if _STACK_MOD is None:
        _a = list(sys.argv); sys.argv = [sys.argv[0]]
        import a1000_rotor_stack as S
        sys.argv = _a; _STACK_MOD = S
    return _STACK_MOD


def tie_bolt_states():
    """tie-bolt clamp [N]: assembly, steady 15k, 18k overspeed (Poisson shortening of the spinning hubs x 1.44), and the
    load factor Phi = kb / (kb + ks) for external axial loads"""
    S = stack_mod(); R = stack(); tb = R['tie_bolt']; Tss = S.T_SS
    Tp = dict(Tss, **{'34CrNiMo6': Tss['stub'], 'Al2618': Tss['imp1'], '17-4PH': Tss['spacer'], 'Ti64': Tss['imp2'], 'IN718': Tss['drum']})
    d1, cb, cs, _, _ = S.tie_bolt(Tp, tb['T_bolt_ss'], True)
    d0 = S.tie_bolt(Tp, tb['T_bolt_ss'], False)[0]
    F_ss = tb['preload_assembly_N'] + d1 / (cb + cs)
    F_os = F_ss + (d1 - d0) * ((N_OS / N_OP) ** 2 - 1.0) / (cb + cs)
    return dict(assembly=tb['preload_assembly_N'], steady=F_ss, overspeed=F_os, min=min(tb['states'].values()),
                phi=tb['k_bolt'] / (tb['k_bolt'] + tb['k_stack']), k_bolt=tb['k_bolt'], k_stack=tb['k_stack'])


def bending_moments():
    """bending moment [Nm] at each joint plane: (i) passage of the 1st / 2nd critical with the unbalance (mid + conical
    API distributions) scaled until the damper orbit reaches the SFD clearance (the physical limit: the damper bottoms)
    and (ii) G_SHOCK x gravity; the rotor dynamics of the detailed stack (a1000_rotor_stack.detailed_rotor), moment from
    the beam curvature E I (theta_2 - theta_1) / l at the joint"""
    S = stack_mod(); R = stack()
    Rd = S.detailed_rotor(None); sp = R['rotordynamics']['nominal']['support']
    x = RD.mesh_nodes(Rd); M, K, C, Gm = RD.assemble(Rd, x, sp)
    W1, W2, xcg = RD.journal_loads(Rd)
    crit = [c['N'] for c in R['rotordynamics']['nominal']['criticals']][:2]
    nh = len(Rd['brg']); hdof = [2 * len(x) + i for i in range(nh)]
    xj = dict(stub_I1=G.X_I1[0], I1_spc=G.X_I1[1], spc_I2=G.X_I2[0], I2_drum=G.X_I2[1], drum_R1=G.X_J['drum_R1'],
              R1_spc=G.X_J['R1_spc'], spc_R2=G.X_J['spc_R2'], R2_stub=G.X_J['R2_stub'])
    E_hot = dict(marm247=170e9, in718=175e9)
    def moment_at(q, xx):
        i = int(np.searchsorted(x, xx)) - 1; i = min(max(i, 0), len(x) - 2)
        xm = 0.5 * (x[i] + x[i + 1]); s = [s for s in Rd['seg'] if s[0] - 1e-6 <= xm <= s[1] + 1e-6][0]
        E = E_hot.get(s[4], RD.MAT[s[4]][1]); I = math.pi / 64 * ((s[2] * 1e-3) ** 4 - (s[3] * 1e-3) ** 4)
        return abs(E * I * (q[2 * i + 3] - q[2 * i + 1]) / ((x[i + 1] - x[i]) * 1e-3))
    cases = dict(mid=[(xcg, 0.0, W1 + W2)], conical=[(Rd['discs']['impeller1']['x'], 0.0, W1), (Rd['discs']['blisk2']['x'], math.pi, W2)])
    out = {k: dict(dyn=0.0) for k in xj}; info = []
    for Nc in crit:
        Om = Nc * math.pi / 30
        for cname, locs in cases.items():
            F = np.zeros(len(M), complex)
            for xl, ph, Wk in locs:
                U = 6350 * Wk / RD.N_MCS * 1e-6; j = int(np.argmin(abs(x - xl))); F[2 * j] += U * Om * Om * np.exp(1j * ph)
            q = np.linalg.solve(K - Om * Om * M + 1j * Om * C + Om * Om * Gm, F)
            orb = max(abs(q[h]) for h in hdof); sc = G.SFD['c'] * 1e-3 / orb
            info.append(dict(N=Nc, case=cname, damper_orbit_api_um=orb * 1e6, scale_to_clearance=sc))
            for k, xx in xj.items(): out[k]['dyn'] = max(out[k]['dyn'], moment_at(q * sc, xx))
    for k, xx in xj.items():
        out[k]['grav'] = S.gravity_moment(xx, G_SHOCK); out[k]['total'] = out[k]['dyn'] + out[k]['grav']
    return out, info


A_PSEUDO = 1.0e-5                                             # in-plane pseudo-expansion of an impeller hub segment [1/K]


def pseudo_T(P, J, N, hot):
    """pseudo-temperature of an impeller hub segment: in-plane strain = (impeller growth - the segment's own centrifugal
    growth) / r at the curvic mean radius"""
    if not hot and N <= 0: return 20.0
    rm = 0.5 * (J['ri'] + J['ro']); T = P['T'] if hot else 20.0
    u = u_disc(rm, P['a'], P['b'], P['mat'], T, N) - (u_disc(rm, P['a'], P['ro_seg'], P['mat'], 20.0, N) if N > 0 else 0.0)
    return 20.0 + u / rm / A_PSEUDO


def growth(P, r, N, T):
    """prescribed radial growth [mm] of a part's far face at radius r"""
    if N <= 0 and T <= 20.0: return 0.0 * r
    if P.get('row'): return disc_arm_growth(P['row'], P['side'], r, N)
    return u_disc(r, P['a'], P['b'], P['mat'], T, N)


# ================================================================================================ CalculiX deck
FACE_IDX = (('S1', (0, 1, 2)), ('S2', (0, 3, 1)), ('S3', (1, 3, 2)), ('S4', (2, 3, 0)))


def ccx_tets(m):
    """gmsh TET10 -> C3D10 mid-side order (0-1, 1-2, 2-0, 0-3, 1-3, 2-3), matched by position in the unrolled space"""
    U = m['U']; idx = {int(t): i for i, t in enumerate(m['tags'])}
    T = np.vectorize(idx.get)(m['tets'])
    cn, md = T[:, :4], T[:, 4:]
    want = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]
    out = np.empty((len(T), 10), np.int64); out[:, :4] = m['tets'][:, :4]
    P = U[md]                                                          # (n, 6, 3)
    for j, (a, b) in enumerate(want):
        c = 0.5 * (U[cn[:, a]] + U[cn[:, b]])
        k = np.argmin(np.linalg.norm(P - c[:, None, :], axis=2), axis=1)
        out[:, 4 + j] = m['tets'][np.arange(len(T)), 4 + k]
    return out


def face_map(tets):
    fm = {}
    for i, e in enumerate(tets, 1):
        for sn, (a, b, c) in FACE_IDX: fm[tuple(sorted((e[a], e[b], e[c])))] = (i, sn)
    return fm


def surf_faces(m, fm, key, side_test=None):
    out = []
    for tri in m['faces'].get(key, []):
        k = tuple(sorted(tri[:3]))
        if k in fm: out.append(fm[k])
    return out


def tributary(m, key):
    """nodal area weights of a surface (quadratic triangles: corners 0, mid-side nodes A / 3)"""
    X = {int(t): m['X'][i] for i, t in enumerate(m['tags'])} if '_Xd' not in m else m['_Xd']
    m['_Xd'] = X; w = {}
    for tri in m['faces'].get(key, []):
        a, b, c = (X[int(t)] for t in tri[:3]); A = 0.5 * np.linalg.norm(np.cross(b - a, c - a))
        for t in tri[3:]: w[int(t)] = w.get(int(t), 0.0) + A / 3
        for t in tri[:3]: w.setdefault(int(t), 0.0)
    return w


def cyc_pairs(m, ip):
    """matching node pairs (left, right) of part ip on the cyclic faces (periodic mesh: right = left rotated by 2 th)"""
    from scipy.spatial import cKDTree
    X = m['_Xd']; th = m['th']
    nl = sorted(set(int(t) for tri in m['faces'].get('cycL_%d' % ip, []) for t in tri))
    nr = sorted(set(int(t) for tri in m['faces'].get('cycR_%d' % ip, []) for t in tri))
    c, s = math.cos(2 * th), math.sin(2 * th)
    PL = np.array([X[k] for k in nl]); PL = np.column_stack([PL[:, 0], c * PL[:, 1] - s * PL[:, 2], s * PL[:, 1] + c * PL[:, 2]])
    d, j = cKDTree(np.array([X[k] for k in nr])).query(PL)
    assert d.max() < 1e-4, 'cyclic faces do not match (%.2e mm)' % d.max()
    return [(nl[i], nr[j[i]]) for i in range(len(nl))]


def write_deck(path, name, J, m, steps, solid_band=False):
    """steps: list of dict(name, N, T (per part list), ur (per far part: {node: u_r}), Fax (per loaded part, N per sector,
    + = tension), Tq (N mm per sector), pre (stud force N or 'fix'), out)"""
    tets = ccx_tets(m); fm = face_map(tets); tributary(m, 'far_0')
    used = set(int(k) for k in np.unique(tets)); X = {k: v for k, v in m['_Xd'].items() if k in used}   # (free geometry nodes out)
    np_ = m['n_parts']; tp = m['tpart']
    lines = ['** AURORA-1000 joint %s (%s)\n' % (name, 'solid band' if solid_band else 'curvic contact')]
    lines.append('*NODE, NSET=NALL\n' + ''.join('%d, %.7f, %.7f, %.7f\n' % (k, *v) for k, v in X.items()))
    pre_node = max(X) + 1; dup = {}
    if J['stud']:
        # stud pre-tension: the nodes of the stud cut plane are duplicated on the nut side and tied to the anchor side by
        # u_dup - u_orig + dir u_pre = 0 (x) and u_dup = u_orig (y, z): u_pre > 0 removes stud length at the cut (overlap ->
        # tension); a force on the reference node sets the preload, later steps fix it. (*PRE-TENSION SECTION on the shared nodes of the gmsh fragment released
        # the preload after the first step.)
        xpre = 0.5 * (J['stud']['x_anchor'] + J['stud']['x_nut']); dr = J['stud']['dir']
        cut = set(int(n) for tri in m['faces'].get('pre', []) for n in tri)
        nxt = pre_node + 1
        for n in sorted(cut): dup[n] = nxt; nxt += 1
        for i in np.nonzero(tp == np_)[0]:
            e = tets[i]; xc = np.mean([m['_Xd'][int(n)][0] for n in e[:4]])
            if (xc - xpre) * dr > 0: tets[i] = [dup.get(int(n), int(n)) for n in e]
        lines.append('*NODE, NSET=NPRE\n%d, %.4f, %.4f, 0.0\n' % (pre_node, xpre, G.STUD['r']))
        lines.append('*NODE, NSET=NDUP\n' + ''.join('%d, %.7f, %.7f, %.7f\n' % (d_, *m['_Xd'][n]) for n, d_ in dup.items()))
    mats = [P['mat'] for P in J['parts']] + [(J['stud'] or {}).get('mat', 'IN718')]   # studs: IN718 (R1 - R2: Waspaloy)
    for ip in range(np_ + (1 if J['stud'] else 0)):
        ids = np.nonzero(tp == ip)[0]
        if not len(ids): continue
        lines.append('*ELEMENT, TYPE=C3D10, ELSET=P%d\n' % ip + ''.join('%d, %s\n' % (i + 1, ', '.join(map(str, tets[i]))) for i in ids))
    lines.append('*ORIENTATION, NAME=CYL, SYSTEM=CYLINDRICAL\n0., 0., 0., 1., 0., 0.\n')
    for ip, mname in enumerate(mats):
        if ip > np_ or (ip == np_ and not J['stud']): continue
        q = MAT[mname]; disc = ip < np_ and J['parts'][ip].get('disc')
        if disc:                                       # constant E at the metal temperature, in-plane pseudo-expansion only
            T0 = J['parts'][ip]['T']
            lines.append('*MATERIAL, NAME=M%d\n*ELASTIC\n%.1f, %.3f\n' % (ip, mp(mname, 'E', T0), q['nu']))
            lines.append('*EXPANSION, TYPE=ORTHO, ZERO=20.\n%.4e, %.4e, 0.\n' % (A_PSEUDO, A_PSEUDO))
            lines.append('*DENSITY\n%.4e\n*SOLID SECTION, ELSET=P%d, MATERIAL=M%d, ORIENTATION=CYL\n' % (q['rho'], ip, ip))
            continue
        lines.append('*MATERIAL, NAME=M%d\n*ELASTIC\n' % ip + ''.join('%.1f, %.3f, %.1f\n' % (e, q['nu'], t) for e, t in zip(q['E'], q['T'])))
        lines.append('*EXPANSION, ZERO=20.\n' + ''.join('%.4e, %.1f\n' % (a, t) for a, t in zip(q['a'], q['T'])))
        lines.append('*DENSITY\n%.4e\n*SOLID SECTION, ELSET=P%d, MATERIAL=M%d\n' % (q['rho'], ip, ip))
    # cyclic equations (cylindrical DOF), far-face sets without the dependent (left) nodes
    pairs = [pq for ip in range(np_) for pq in cyc_pairs(m, ip)]
    dep = set(a for a, _ in pairs)
    far = {ip: [k for k in tributary(m, 'far_%d' % ip) if k not in dep] for ip in range(np_) if 'far_%d' % ip in m['faces']}
    trn = sorted(set(k for pq in pairs for k in pq) | set(k for v in far.values() for k in v))
    lines.append('*NSET, NSET=NTRN\n' + ''.join('%d,\n' % k for k in trn) + '*TRANSFORM, NSET=NTRN, TYPE=C\n0., 0., 0., 1., 0., 0.\n')
    lines.append('*EQUATION\n' + ''.join('2\n%d, %d, 1., %d, %d, -1.\n' % (a, d, b, d) for a, b in pairs for d in (1, 2, 3)))
    for ip, v in far.items(): lines.append('*NSET, NSET=FAR%d\n' % ip + ''.join('%d,\n' % k for k in v))
    # contact or tie between the flanks
    for k, cv in enumerate(J['curvics']):
        sl, ms = surf_faces(m, fm, 'slave_%d' % k), surf_faces(m, fm, 'master_%d' % k)
        if solid_band:                                               # solid band bonded to the other part's root land
            ts, tm = surf_faces(m, fm, 'tieS_%d' % k), surf_faces(m, fm, 'tieM_%d' % k)
            lines.append('*SURFACE, NAME=TS%d, TYPE=ELEMENT\n' % k + ''.join('%d, %s\n' % f for f in ts))
            lines.append('*SURFACE, NAME=TM%d, TYPE=ELEMENT\n' % k + ''.join('%d, %s\n' % f for f in tm))
            lines.append('*TIE, NAME=BAND%d, POSITION TOLERANCE=0.05, ADJUST=NO\nTS%d, TM%d\n' % (k, k, k))
            continue
        lines.append('*SURFACE, NAME=SL%d, TYPE=ELEMENT\n' % k + ''.join('%d, %s\n' % f for f in sl))
        lines.append('*SURFACE, NAME=MA%d, TYPE=ELEMENT\n' % k + ''.join('%d, %s\n' % f for f in ms))
        lines.append('*CONTACT PAIR, INTERACTION=SI, TYPE=SURFACE TO SURFACE\nSL%d, MA%d\n' % (k, k))
    if not solid_band:
        lines.append('*SURFACE INTERACTION, NAME=SI\n*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR\n%.3e, 0.1\n*FRICTION\n%.3f, %.3e\n'
                     % (K_PEN, MU, K_STICK))
    if J['stud']:
        # nut bearing face bonded to the flange back face: each nut-face node follows the flange triangle it lies on
        # (linear interpolation on the corner nodes; ccx *TIE generated no MPC for this pair)
        Xd = m['_Xd']; seat = m['faces']['nutseat']; C3 = np.array([[Xd[int(n)] for n in tri[:3]] for tri in seat])
        eqs = []
        for n in sorted(set(int(v) for tri in m['faces']['nutface'] for v in tri)):
            q = Xd[n]; best = None
            for k_, (a, b, c) in enumerate(C3):
                v0, v1, v2 = b[1:] - a[1:], c[1:] - a[1:], q[1:] - a[1:]
                d_ = v0[0] * v1[1] - v0[1] * v1[0]
                l1 = (v2[0] * v1[1] - v2[1] * v1[0]) / d_; l2 = (v0[0] * v2[1] - v0[1] * v2[0]) / d_; l0 = 1 - l1 - l2
                mn = min(l0, l1, l2)
                if best is None or mn > best[0]: best = (mn, k_, (l0, l1, l2))
            mn, k_, w = best
            if mn < -0.05: continue                                    # off the seat (inside the hole)
            ids = [int(v) for v in seat[k_][:3]]
            for dof in (1, 2, 3):
                terms = [(n, dof, 1.0)] + [(i_, dof, -w_) for i_, w_ in zip(ids, w) if abs(w_) > 1e-9]
                eqs.append('%d\n' % len(terms) + ', '.join('%d, %d, %.8f' % t for t in terms) + '\n')
        lines.append('*EQUATION\n' + ''.join(eqs))
        lines.append('*EQUATION\n' + ''.join('3\n%d, 1, 1., %d, 1, -1., %d, 1, %.1f\n2\n%d, 2, 1., %d, 2, -1.\n2\n%d, 3, 1., %d, 3, -1.\n'
                                             % (d_, n, pre_node, dr, d_, n, d_, n) for n, d_ in dup.items()))
    lines.append('*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 20.\n')
    allP = list(range(np_ + (1 if J['stud'] else 0)))
    npart = {}
    for i in np.argsort(tp)[::-1]:
        for n in tets[i]: npart[int(n)] = min(int(tp[i]), np_ - 1) if not J['stud'] else (J['stud']['thread_part'] if tp[i] == np_ else int(tp[i]))
    fixed_part = 0
    for st in steps:
        inc = 1.0 if st['name'].endswith(('_dF', '_dT')) else 0.5          # stiffness probes: one increment
        lines.append('** step %s\n*STEP, INC=200\n*STATIC\n%.2f, 1., 1e-5, 1.\n' % (st['name'], inc))
        if st.get('N', 0) > 0:
            lines.append('*DLOAD\n' + ''.join('P%d, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n' % (ip, om(st['N']) ** 2) for ip in allP))
        else:
            lines.append('*DLOAD, OP=NEW\n')
        lines.append('*TEMPERATURE\n' + ''.join('%d, %.1f\n' % (k, st['T'][npart[k]]) for k in X)
                     + ''.join('%d, %.1f\n' % (d_, st['T'][npart[n]]) for n, d_ in dup.items()))
        lines.append('*BOUNDARY, OP=NEW\n')
        for ip, nodes in far.items():
            ur = st['ur'][ip]
            lines.append(''.join('%d, 1, 1, %.6e\n' % (k, ur[k]) for k in nodes))
            if ip == fixed_part: lines.append('FAR%d, 2, 3, 0.\n' % ip)
        if J['stud']:
            lines.append('%d, 2, 3, 0.\n' % pre_node)
            if st['pre'] == 'fix': lines.append('*BOUNDARY, FIXED\n%d, 1, 1\n' % pre_node)
        lines.append('*CLOAD, OP=NEW\n')
        if J['stud'] and st['pre'] != 'fix': lines.append('%d, 1, %.3f\n' % (pre_node, st['pre']))
        lp = [ip for ip in far if ip != fixed_part][0]
        w = tributary(m, 'far_%d' % lp); w = {k: v for k, v in w.items() if k in set(far[lp])}
        W = sum(w.values()); Wr2 = sum(v * (X[k][1] ** 2 + X[k][2] ** 2) for k, v in w.items())
        sgn_out = 1.0 if J['parts'][lp]['far'] > J['parts'][fixed_part]['far'] else -1.0
        for k, v in w.items():
            if v == 0.0: continue
            r = math.hypot(X[k][1], X[k][2]); fx = sgn_out * st['Fax'] * v / W; ft = st['Tq'] * v * r / Wr2
            lines.append('%d, 3, %.6e\n%d, 2, %.6e\n' % (k, fx, k, ft))
        if J['stud'] and st['pre'] == 'fix':
            lines.append('*NODE PRINT, NSET=NPRE\nRF, U\n')
        lines.append('*NODE FILE, FREQUENCY=100\nU, RF\n*EL FILE, FREQUENCY=100\nS\n')
        if not solid_band: lines.append('*CONTACT FILE, FREQUENCY=100\nCDIS, CSTR\n')
        lines.append('*END STEP\n')
    open(path, 'w').write(''.join(lines))
    return dict(pre_node=pre_node, far={k: list(v) for k, v in far.items()}, fixed=fixed_part, loaded=lp)


# ================================================================================================ load steps and runs
def joint_loads(name, J, Mb=None):
    """per-joint loads (full ring): clamp / stud preload, torque rated and short circuit, thrust tension, bending"""
    R = stack(); tq = R['torque_Nm']
    key = dict(R1_R2='R1_R2').get(name, name)
    T_r = tq['rated'].get(key, 0.0) if name != 'R2_stub' else 0.0
    T_5 = tq['max_short_circuit'].get(key, 0.0)
    T_sc = T_r + SC_FACTOR / 5.0 * (T_5 - T_r)                         # stack: 5 x rated at the coupling, shared by inertia
    if Mb is None: Mb = json.load(open(OUT_JSON)).get('bending_moments', {}) if os.path.exists(OUT_JSON) else {}
    mk = ['R1_spc', 'spc_R2'] if name == 'R1_R2' else [name]
    M_e = max(Mb[k]['total'] for k in mk) if Mb else 0.0
    a, b = J['ri'], J['ro']; A_r = math.pi * (b * b - a * a); I = math.pi / 4 * (b ** 4 - a ** 4)
    F_bend = M_e * 1e3 * b * A_r / I                                     # equivalent ring force, outer fibre [N]
    if J['kind'] == 'comp':
        tb = tie_bolt_states(); fax = R['tie_bolt']['required'][name]['Fax']
        return dict(T_r=T_r, T_sc=T_sc, M_e=M_e, F_bend=F_bend, fax=fax, C_a=tb['assembly'], C_b=tb['steady'] - (1 - tb['phi']) * fax,
                    C_c=tb['overspeed'] - (1 - tb['phi']) * fax, tb=tb)
    hj = R['hot_joints']['joints'][name]
    return dict(T_r=T_r, T_sc=T_sc, M_e=M_e, F_bend=F_bend, fax=hj['parts']['axial'], F_pre=J['stud'].get('pre_kN', G.STUD['pre_kN']) * 1e3)


def make_steps(name, J, m, ld, solid_band=False):
    n = J['n_sec']; X = m['_Xd']
    far_nodes = {ip: list(tributary(m, 'far_%d' % ip).keys()) for ip in range(m['n_parts']) if 'far_%d' % ip in m['faces']}
    def Tlist(N, hot):
        return [pseudo_T(P, J, N, hot) if P.get('disc') else (P['T'] if hot else 20.0) for P in J['parts']]
    def ur(N, T):
        hot = not (isinstance(T, list) and all(t == 20.0 for t in T))
        out = {}
        for ip, nodes in far_nodes.items():
            P = J['parts'][ip]; rr = np.array([math.hypot(X[k][1], X[k][2]) for k in nodes])
            out[ip] = dict(zip(nodes, growth(P, rr, N, P['T'] if hot else 20.0)))
        return out
    Tps = Tlist(N_OP, True)
    cold = [20.0] * len(J['parts'])
    Tos = Tlist(N_OS, True)
    st = []
    if J['kind'] == 'comp':
        dF = 0.10 * ld['C_a']
        st.append(dict(name='a', N=0, T=cold, ur=ur(0, cold), Fax=-ld['C_a'] / n, Tq=0.0))
        st.append(dict(name='a_dF', N=0, T=cold, ur=ur(0, cold), Fax=-(ld['C_a'] - dF) / n, Tq=0.0))
        st.append(dict(name='a_dT', N=0, T=cold, ur=ur(0, cold), Fax=-ld['C_a'] / n, Tq=ld['T_r'] * 1e3 / n))
        b = dict(name='b', N=N_OP, T=Tps, ur=ur(N_OP, Tps), Fax=-ld['C_b'] / n, Tq=ld['T_r'] * 1e3 / n)
        st += [b, dict(b, name='b_dF', Fax=-(ld['C_b'] - dF) / n)]
        if not solid_band:                                          # e, c, d follow each other (absolute loads)
            st += [dict(b, name='e', Fax=-(ld['C_b'] - ld['F_bend']) / n), dict(b, name='c', N=N_OS, T=Tos, ur=ur(N_OS, Tps), Fax=-ld['C_c'] / n),
                   dict(b, name='d', Tq=ld['T_sc'] * 1e3 / n)]
    else:
        dF = 0.10 * G.STUD['n'] * ld['F_pre']                              # stiffness probe: 10 % of the total clamp
        Tq_probe = ld['T_r'] if ld['T_r'] > 0 else 300.0
        st.append(dict(name='a', N=0, T=cold, ur=ur(0, cold), Fax=0.0, Tq=0.0, pre=ld['F_pre']))
        st.append(dict(name='a_dF', N=0, T=cold, ur=ur(0, cold), Fax=dF / n, Tq=0.0, pre='fix'))
        st.append(dict(name='a_dT', N=0, T=cold, ur=ur(0, cold), Fax=0.0, Tq=Tq_probe * 1e3 / n, pre='fix'))
        b = dict(name='b', N=N_OP, T=Tps, ur=ur(N_OP, Tps), Fax=ld['fax'] / n, Tq=ld['T_r'] * 1e3 / n, pre='fix')
        st += [b, dict(b, name='b_dF', Fax=(ld['fax'] + dF) / n)]
        if not solid_band:
            st += [dict(b, name='e', Fax=(ld['fax'] + ld['F_bend']) / n), dict(b, name='c', N=N_OS, ur=ur(N_OS, Tps)),
                   dict(b, name='d', Tq=ld['T_sc'] * 1e3 / n)]
    for s in st: s.setdefault('pre', None)
    return st


def run_joint(name, level='medium', solid_band=False, threads=None):
    J = joints()[name]; tag = '%s_%s%s%s' % (name, level, '_solid' if solid_band else '', os.environ.get('A1000_P4_TAGSUFFIX', ''))
    d = os.path.join(RUNS, tag); os.makedirs(d, exist_ok=True)
    t0 = time.time(); m = build_mesh(tag, J, level, solid_band)
    tributary(m, 'far_0')
    ld = joint_loads(name, J)
    steps = make_steps(name, J, m, ld, solid_band)
    info = write_deck(os.path.join(d, 'job.inp'), name, J, m, steps, solid_band)
    t1 = time.time()
    print('%s: %d nodes, %d tets, mesh + deck %.0f s' % (tag, len(m['X']), len(m['tets']), t1 - t0), flush=True)
    np.savez_compressed(os.path.join(d, 'mesh.npz'), tags=m['tags'], X=m['X'], tets=m['tets'], tpart=m['tpart'],
                        **{'f_' + k: v for k, v in m['faces'].items()})
    json.dump(dict(info=info, loads={k: v for k, v in ld.items() if k != 'tb'}, steps=[s['name'] for s in steps],
                   step_loads=[{k: v for k, v in s.items() if k not in ('ur', 'T')} for s in steps], level=level, solid=solid_band,
                   n_nodes=len(m['X']), n_tets=len(m['tets'])), open(os.path.join(d, 'meta.json'), 'w'), indent=1, default=float)
    th = threads or THREADS
    env = dict(os.environ, OMP_NUM_THREADS=str(th), CCX_NPROC_EQUATION_SOLVER=str(th), CCX_NPROC_RESULTS=str(th))
    with open(os.path.join(d, 'ccx.log'), 'w') as lg:
        p = subprocess.run([CCX, '-i', 'job'], cwd=d, env=env, stdout=lg, stderr=subprocess.STDOUT)
    ok = 'Job finished' in open(os.path.join(d, 'ccx.log')).read()
    print('%s: ccx %s in %.0f s' % (tag, 'finished' if ok else 'FAILED', time.time() - t1), flush=True)
    open(os.path.join(d, 'done'), 'w').write('ok' if ok else 'fail')
    return ok


if __name__ == '__main__' and '--run' in sys.argv:
    a = sys.argv[sys.argv.index('--run') + 1]
    lev = sys.argv[sys.argv.index('--level') + 1] if '--level' in sys.argv else 'medium'
    names = list(joints()) if a == 'all' else a.split(',')
    for nm in names:
        run_joint(nm, lev, solid_band='--solid' in sys.argv)


# ================================================================================================ results
def read_frd_steps(path, want=('DISP', 'STRESS', 'CONTACT')):
    """last increment of every step: {step: {block: (node ids, values)}} from an ASCII .frd"""
    out = {}; cur = None; step = None; rows = None
    with open(path) as f:
        for line in f:
            if line.startswith('    1PSTEP'):
                step = int(line.split()[3]); continue
            if line.startswith(' -4'):
                nm = line.split()[1]; cur = nm if nm in want else None; rows = [] if cur else None; continue
            if cur is None: continue
            if line.startswith(' -1'):
                rows.append(line)
            elif line.startswith(' -3'):
                ids = np.array([int(r[3:13]) for r in rows])
                nv = (len(rows[0].rstrip('\n')) - 13) // 12
                vals = np.array([[float(r[13 + 12 * k:25 + 12 * k]) for k in range(nv)] for r in rows])
                out.setdefault(step, {})[cur] = (ids, vals); cur = None
    return out


def principal(Sv):
    """max principal and von Mises of (n, 6) stresses xx yy zz xy yz zx"""
    T = np.zeros((len(Sv), 3, 3))
    T[:, 0, 0], T[:, 1, 1], T[:, 2, 2] = Sv[:, 0], Sv[:, 1], Sv[:, 2]
    T[:, 0, 1] = T[:, 1, 0] = Sv[:, 3]; T[:, 1, 2] = T[:, 2, 1] = Sv[:, 4]; T[:, 0, 2] = T[:, 2, 0] = Sv[:, 5]
    ev = np.linalg.eigvalsh(T)
    vmv = np.sqrt(0.5 * ((ev[:, 0] - ev[:, 1]) ** 2 + (ev[:, 1] - ev[:, 2]) ** 2 + (ev[:, 2] - ev[:, 0]) ** 2))
    return ev[:, 2], vmv


def read_dat_rf(path, node):
    """reaction force of node (pre-tension node) per step from the .dat (*NODE PRINT RF), in step order"""
    out = []; on = False
    for line in open(path):
        if 'forces (fx,fy,fz)' in line: on = True; continue
        if on:
            p = line.split()
            if len(p) == 4 and p[0] == str(node): out.append(float(p[1])); on = False
    return out


def post_joint(tag, J, ld):
    """contact, root stress, separation, stiffness, slip and stud results of one run directory"""
    d = os.path.join(RUNS, tag); meta = json.load(open(os.path.join(d, 'meta.json')))
    z = np.load(os.path.join(d, 'mesh.npz')); tags = z['tags']; X = z['X']; ix = {int(t): i for i, t in enumerate(tags)}
    faces = {k[2:]: z[k] for k in z.files if k.startswith('f_')}
    names = meta['steps']; R = read_frd_steps(os.path.join(d, 'job.frd'))
    st = {nm: R[i + 1] for i, nm in enumerate(names) if (i + 1) in R}
    n = J['n_sec']; res = dict(level=meta['level'], n_nodes=meta['n_nodes'], steps={})
    # case e by superposition: e = b + (F_bend / dF) (b_dF - b), where b_dF is the computed 15k state with the extra axial
    # tension dF (contact stays closed there). Used when the run carried no bending (M_e = 0 at run time) - all runs of
    # 2026-10-31 except the direct check spc_I2 'e' run
    sl0 = meta['step_loads']; nm0 = meta['steps']
    if meta['loads'].get('F_bend', 0.0) == 0.0 and ld.get('F_bend', 0.0) > 0 and 'b_dF' in st and 'b' in st:
        dF = abs(sl0[nm0.index('b_dF')]['Fax'] - sl0[nm0.index('b')]['Fax']) * n; kf = ld['F_bend'] / dF
        e = {}
        for blk in st['b']:
            ib, vb = st['b'][blk]; idf, vdf = st['b_dF'][blk]
            m_ = dict(zip(idf.tolist(), range(len(idf)))); jj = np.array([m_.get(int(k), -1) for k in ib])
            v = vb.copy(); ok_ = jj >= 0; v[ok_] = vb[ok_] + kf * (vdf[jj[ok_]] - vb[ok_])
            if blk == 'CONTACT': v[:, 3] = np.maximum(v[:, 3], 0.0)
            e[blk] = (ib, v)
        if 'e' in st: st['e_unload'] = st['e']                       # the run's own e = back to the b loads after b_dF
        st['e'] = e; res['e_superposition'] = dict(dF=dF, F_bend=ld['F_bend'], factor=kf)
    def field(nm, blk, comp=None):
        ids, v = st[nm][blk]; keep = np.array([int(k) in ix for k in ids])
        a = np.zeros((len(tags), v.shape[1])); a[[ix[int(k)] for k in ids[keep]]] = v[keep]
        return a if comp is None else a[:, comp]
    # ---------------------------------------------------------------- stiffness from the far faces
    loaded = meta['info']['loaded']; fixed = meta['info']['fixed']
    fl = np.array([ix[k] for k in meta['info']['far'][str(loaded)]])
    def face_motion(nm):
        u = field(nm, 'DISP')[fl]; P = X[fl]; r = np.hypot(P[:, 1], P[:, 2]); th = np.arctan2(P[:, 2], P[:, 1])
        ut = -np.sin(th) * u[:, 1] + np.cos(th) * u[:, 2]
        return float(np.mean(u[:, 0])), float(np.mean(ut / r))
    sl = [s_ for s_ in meta['step_loads']]
    def dload(a, b, key): return (sl[names.index(b)][key] - sl[names.index(a)][key])
    k = {}
    for a_, b_ in (('a', 'a_dF'), ('b', 'b_dF')):
        if a_ in st and b_ in st:
            dx = face_motion(b_)[0] - face_motion(a_)[0]; dF = dload(a_, b_, 'Fax') * n
            sgn = 1.0 if J['parts'][loaded]['far'] > J['parts'][fixed]['far'] else -1.0
            k['axial_' + a_] = abs(dF / (sgn * dx)) if dx else float('nan')                 # N/mm, full ring
    if 'a_dT' in st:
        dth = face_motion('a_dT')[1] - face_motion('a')[1]; dT = dload('a', 'a_dT', 'Tq') * n
        k['torsion_a'] = abs(dT / dth) * 1e-3 if dth else float('nan')                    # N m / rad
    res['stiffness_model'] = k
    if meta['solid']: return res
    # ---------------------------------------------------------------- contact
    for kc, cv in enumerate(J['curvics']):
        tri = faces['slave_%d' % kc]
        Pc = X[np.vectorize(ix.get)(tri[:, :3])]                                           # (n, 3, 3)
        nrm = np.cross(Pc[:, 1] - Pc[:, 0], Pc[:, 2] - Pc[:, 0]); A = 0.5 * np.linalg.norm(nrm, axis=1); nrm /= (2 * A)[:, None]
        cen = Pc.mean(axis=1); thc = np.arctan2(cen[:, 2], cen[:, 1]); et = np.column_stack([0 * thc, -np.sin(thc), np.cos(thc)])
        side = np.sign(np.sum(nrm * et, axis=1))                                           # +1 / -1: the two flanks
        rc = np.hypot(cen[:, 1], cen[:, 2])
        mids = np.vectorize(ix.get)(tri[:, 3:])
        # tooth index of each slave triangle (by the angle of its flank centre, lo-part tooth centres)
        pitch = 2 * math.pi / J['N']; lo0 = 0.0 if J['kind'] == 'comp' else pitch / 2
        tooth = np.round((thc - side * 0 - lo0) / pitch).astype(int)
        A_ov = (cv['h'] - 2 * C_ROOT - 2 * TIP_CH) / (cv['h'] - C_ROOT - TIP_CH - RHO_F * 0.5)   # overlapping share of a flank
        out = {}
        for nm in names:
            if nm not in st: continue
            C = field(nm, 'CONTACT'); p = C[:, 3]; tau = np.hypot(C[:, 4], C[:, 5]); slip = C[:, 1:3]
            w = np.repeat(A[:, None] / 3, 3, axis=1)                                         # mid-side node weights
            pm = p[mids]; Fs = {sd: float(np.sum((w * pm)[side == sd])) for sd in (-1, 1)}
            Fax = {sd: float(np.sum((w * pm)[side == sd] * np.abs(nrm[side == sd, 0])[:, None])) for sd in (-1, 1)}
            nodes = np.unique(mids); pn = p[nodes]; tn = tau[nodes]
            wn = np.zeros(len(tags)); np.add.at(wn, mids.ravel(), w.ravel()); wn = wn[nodes]
            on = pn > 0.5
            stick_slip = (tn >= 0.97 * MU * pn) & on
            per_tooth = {}
            for t_ in np.unique(tooth):
                for sd in (-1, 1):
                    mk = (tooth == t_) & (side == sd)
                    if mk.any(): per_tooth['%d%s' % (t_, '+' if sd > 0 else '-')] = float(np.sum((w * pm)[mk]))
            out[nm] = dict(F_side=Fs, Fax_side=Fax, p_mean=float(np.sum(pn[on] * wn[on]) / max(np.sum(wn[on]), 1e-9)),
                           p99=float(np.percentile(pn[on], 99)) if on.any() else 0.0, p_max=float(pn.max()),
                           p95=float(np.percentile(pn[on], 95)) if on.any() else 0.0,
                           area_contact=float(np.sum(wn[on]) / np.sum(wn) / A_ov), slip_share=float(np.sum(wn[stick_slip]) / max(np.sum(wn[on]), 1e-9)),
                           per_tooth=per_tooth, slip=slip[nodes], pn=pn)
        # drive / coast from the torque step
        sd_drive = 1 if out['d']['F_side'][1] - out['b']['F_side'][1] > out['d']['F_side'][-1] - out['b']['F_side'][-1] else -1
        if kc == 0:                                                       # flank pressure map (plot): drive flank, cases b / d / e
            nd = np.unique(mids[side == sd_drive]); q = X[nd]
            np.savez_compressed(os.path.join(d, 'map.npz'), r=np.hypot(q[:, 1], q[:, 2]), x=q[:, 0], th=np.arctan2(q[:, 2], q[:, 1]),
                                **{'p_' + nm: field(nm, 'CONTACT')[nd, 3] for nm in ('a', 'b', 'd', 'e') if nm in st},
                                **{'t_' + nm: np.hypot(*field(nm, 'CONTACT')[nd, 4:6].T) for nm in ('a', 'b', 'd', 'e') if nm in st})
        for nm, o in out.items():
            o['drive'] = o['F_side'][sd_drive]; o['coast'] = o['F_side'][-sd_drive]
            o['coast_frac'] = o['coast'] / out['a']['coast']
            o['tooth_coast_min_frac'] = min(v / out['a']['per_tooth'][kk] for kk, v in o['per_tooth'].items() if out['a']['per_tooth'].get(kk, 0) > 0
                                            and (kk.endswith('+') == (sd_drive < 0)))
            o['tooth_any_min_frac'] = min(v / out['a']['per_tooth'][kk] for kk, v in o['per_tooth'].items() if out['a']['per_tooth'].get(kk, 0) > 0)
        # slip per start (a -> b) and per revolution (gravity share of the bending case)
        on_b = out['b']['pn'] > 0.5
        ds = np.linalg.norm(out['b']['slip'] - out['a']['slip'], axis=1)
        a_, b_ = J['ri'], J['ro']; Ar = math.pi * (b_ * b_ - a_ * a_); Ir = math.pi / 4 * (b_ ** 4 - a_ ** 4)
        Fg1 = stack_mod().gravity_moment(cv['xp'], 1.0) * 1e3 * b_ * Ar / Ir                # 1 g gravity: equivalent ring tension
        dFp = abs(sl[names.index('b_dF')]['Fax'] - sl[names.index('b')]['Fax']) * n
        # cyclic (reversible) slip: unloading b_dF -> b (the run's own step e when it carried no bending); the first loading
        # b -> b_dF also holds the one-way ratchet of a contact that is in radial gross slip after the start
        if 'e_unload' in st:
            Cu = field('e_unload', 'CONTACT')[np.unique(mids)][:, 1:3]
            de = np.linalg.norm(Cu - out['b_dF']['slip'], axis=1)
        else:
            de = np.linalg.norm(out['b_dF']['slip'] - out['b']['slip'], axis=1)
        g1 = Fg1 / dFp
        res.setdefault('contact', {})[kc] = dict(
            cases={nm: {kk: vv for kk, vv in o.items() if kk not in ('slip', 'pn')} for nm, o in out.items()},
            slip_per_start_um=dict(max=float(ds[on_b].max() * 1e3), p99=float(np.percentile(ds[on_b], 99) * 1e3), mean=float(ds[on_b].mean() * 1e3)),
            slip_per_rev_um=dict(max=float(de.max() * 1e3 * g1), p99=float(np.percentile(de, 99) * 1e3 * g1), mean=float(de.mean() * 1e3 * g1)),
            sd_drive=sd_drive)
    # ---------------------------------------------------------------- tooth root stress (fillet nodes)
    root = {}
    for ip, P in enumerate(J['parts']):
        key = 'fillet_%d' % ip
        if key not in faces: continue
        nodes = np.unique(np.vectorize(ix.get)(faces[key]))
        # evaluation 1 mm away from the sharp model edges (drawing: R0.5 edge break at the tooth ends and the stud holes):
        # the tooth-band ends r = ri / ro and the stud-hole edge
        q = X[nodes]; rr = np.hypot(q[:, 1], q[:, 2])
        far_h = (rr > J['ri'] + 1.0) & (rr < J['ro'] - 1.0)
        if J['stud']:
            th = np.arctan2(q[:, 2], q[:, 1]); dh = np.hypot(rr * np.cos(th) - G.STUD['r'], rr * np.sin(th))
            far_h &= dh > G.STUD['hole'] / 2 + 1.0
        o = {}
        for nm in names:
            if nm not in st: continue
            s1, sv = principal(field(nm, 'STRESS')[nodes])
            o[nm] = dict(s1=float(s1[far_h].max()), vm=float(sv[far_h].max()), s1_all=float(s1.max()), vm_all=float(sv.max()),
                         s1_nodes=s1)
        T = P['T']; m = P['mat']; E = mp(m, 'E', T)
        sa, sb = o['a']['s1_nodes'], o['b']['s1_nodes']
        rng = np.abs(sb - sa); i = int(np.argmax(np.where(far_h, rng, 0)))
        N_ss = manson(m, rng[i] / E, T, max(sa[i], sb[i]), 0.5 * (sa[i] + sb[i]))
        sd_ = o['d']['s1_nodes']; rd = np.abs(sd_ - sa); j = int(np.argmax(np.where(far_h, rd, 0)))
        N_sc = manson(m, rd[j] / E, T, max(sa[j], sd_[j]), 0.5 * (sa[j] + sd_[j]))
        vmax = max(o[nm]['vm'] for nm in o); vb = max(o[nm]['vm'] for nm in ('a', 'b', 'e') if nm in o)
        vr = max(o[nm]['vm'] for nm in ('c', 'd') if nm in o)
        root[P['name']] = dict(mat=m, T=T, cases={nm: {kk: vv for kk, vv in v.items() if kk != 's1_nodes'} for nm, v in o.items()},
                               range_ab=float(rng[i]), lcf_starts=N_ss, range_ad=float(rd[j]), lcf_short_circuits=N_sc,
                               yield_margin=mp(m, 'Sy', T) / vb, vm_steady=vb, rare_margin=mp(m, 'Su', T) / vr, vm_rare=vr, vm_max=vmax)
    res['root'] = root
    # ---------------------------------------------------------------- studs
    if J['stud']:
        rf = read_dat_rf(os.path.join(d, 'job.dat'), meta['info']['pre_node'])
        fixed_steps = [nm for nm, s_ in zip(names, sl) if s_.get('pre') == 'fix']
        Fst = dict(a=ld['F_pre']); Fst.update({nm: abs(v) for nm, v in zip(fixed_steps, rf)})
        tp = z['tpart']; tets = z['tets']
        sn = np.unique(np.vectorize(ix.get)(tets[tp == len(J['parts'])]))
        q = X[sn]; rr = np.hypot(q[:, 1] - 0, q[:, 2]); dax = np.hypot(q[:, 1] - G.STUD['r'], q[:, 2])
        x0, x1 = J['stud']['x_anchor'], J['stud']['x_nut']; dr = J['stud']['dir']
        shank = (dax < 4.5) & ((q[:, 0] - x0) * dr > 1.5) & ((x1 - q[:, 0]) * dr > 1.5)
        so = {}
        for nm in names:
            if nm not in st: continue
            S_ = field(nm, 'STRESS')[sn]; s1, sv = principal(S_)
            sec = {}
            for lab, xs_ in (('nut', x1 - dr * 2.0), ('anchor', x0 + dr * 2.0), ('mid', 0.5 * (x0 + x1))):
                mk = shank & (np.abs(q[:, 0] - xs_) < 0.8)
                sx = S_[mk, 0]; sec[lab] = dict(mean=float(np.mean(sx)), max=float(np.max(sx)), bend=float(np.max(sx) - np.mean(sx)))
            so[nm] = dict(F=sec['mid']['mean'] * 61.2, F_rf=Fst.get(nm, float('nan')), sections=sec, vm_shank_max=float(sv[shank].max()))
        res['stud'] = so
    return res


# ================================================================================================ ISFD ring (2D)
ISFD_MAT = dict(E=196e3, nu=0.27, Su=965.0, Sy=795.0, Se=300.0)   # 17-4PH H1100 (AMS 5643 min); Se: 10^7, R = -1, smooth ~450 MPa
                                                                  # x 0.75 wire-EDM surface (skim cuts, recast removed) x 0.9 size
RHO_S = 0.8                                                       # fillet radius at the web roots [mm] (wire-EDM corner radius)


def isfd_geometry(q=None):
    """ring as drawn (cad/engine/a1000_rotor.journal_parts): inner ring ri..ri + 4, outer ring ro - 6..ro, n curved beams
    (radial thickness t, arc span) at mid radius, a web of 3 deg to the inner ring at the beam start and one to the outer
    ring at the beam end; springs from ISFD_CLOCK + 360 / n k"""
    q = dict(dict(ri=74.0, ro=92.0, n=8, t=4.2, span=30.0), **(q or {})); q['kind'] = 'beam'
    r1, r2 = q['ri'] + 4.0, q['ro'] - 6.0
    rb0 = 0.5 * (r1 + r2) - q['t'] / 2; rb1 = rb0 + q['t']
    return dict(q, r1=r1, r2=r2, rb0=rb0, rb1=rb1, w_web=3.0, Lf=43.0)


def isfd_pieces(g):
    """annular sectors (r0, r1, a0, a1) of the springs. kind 'beam' (as drawn): one circumferential beam per spring, a
    3 deg web to the inner ring at its start, one to the outer ring at its end. kind 'hairpin': inner arm from a web on
    the inner ring at angle a, a U-turn at a + span, outer arm back to a web on the outer ring at a (both directions of
    the spring bend: radial load bends the arms, tangential load bends them through the couple of the arm forces)"""
    out = []; w = g['w_web']
    for k in range(g['n']):
        a = G.ISFD_CLOCK + 360.0 / g['n'] * k; sp = g['span']
        if g.get('kind', 'beam') == 'beam':
            out += [(g['rb0'], g['rb1'], a, a + sp), (g['r1'] - 0.5, g['rb0'] + 0.5, a, a + w), (g['rb1'] - 0.5, g['r2'] + 0.5, a + sp - w, a + sp)]
        else:
            out += [(g['rA0'], g['rA1'], a, a + sp), (g['rB0'], g['rB1'], a, a + sp), (g['rA0'], g['rB1'], a + sp - g['w_u'], a + sp),
                    (g['r1'] - 0.5, g['rA0'] + 0.5, a, a + w), (g['rB1'] - 0.5, g['r2'] + 0.5, a, a + w)]
    return out


def isfd_corners(g):
    """re-entrant corners (r, angle, dr, angle side) that get a RHO_S fillet"""
    out = []; w = g['w_web']; rho = RHO_S
    for k in range(g['n']):
        a = G.ISFD_CLOCK + 360.0 / g['n'] * k; sp = g['span']
        if g.get('kind', 'beam') == 'beam':
            out += [(g['r1'], a, rho, -1), (g['r1'], a + w, rho, +1), (g['rb0'], a + w, -rho, +1),
                    (g['rb1'], a + sp - w, rho, -1), (g['r2'], a + sp - w, -rho, -1), (g['r2'], a + sp, -rho, +1)]
        else:
            u = sp - g['w_u']
            out += [(g['r1'], a, rho, -1), (g['r1'], a + w, rho, +1), (g['rA0'], a + w, -rho, +1),          # inner web
                    (g['r2'], a, -rho, -1), (g['r2'], a + w, -rho, +1), (g['rB1'], a + w, rho, +1),          # outer web
                    (g['rA1'], a + u, rho, -1), (g['rB0'], a + u, -rho, -1)]                                # U-turn
    return out


def isfd_hairpin(t=2.4, span=34.0, gap=1.6, w_web=4.0, w_u=4.0, t_ring=3.0, n=8):
    """hairpin spring layout in the drawn envelope ri 74 / ro 92 (inner / outer ring t_ring)"""
    q = dict(ri=G.ISFD['ri'], ro=G.ISFD['ro']); q.update(n=n, t=t, span=span)
    r1, r2 = q['ri'] + t_ring, q['ro'] - t_ring
    gm = (r2 - r1) - 2 * t - 2 * gap                                     # gap between the arms
    rA0 = r1 + gap; rA1 = rA0 + t; rB0 = rA1 + gm; rB1 = rB0 + t
    return dict(q, kind='hairpin', r1=r1, r2=r2, rA0=rA0, rA1=rA1, rB0=rB0, rB1=rB1, gap=gap, gap_m=gm, w_web=w_web, w_u=w_u,
                Lf=G.ISFD.get('Lf', 43.0), t_ring=t_ring)


def isfd_mesh(g, h=0.35, h_f=None):
    import gmsh
    h_f = h_f or h / 3
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0); gmsh.model.add('isfd'); occ = gmsh.model.occ
    def sector(r0, r1, a0, a1):
        a0, a1 = math.radians(a0), math.radians(a1)
        p = [occ.addPoint(r0 * math.cos(a0), r0 * math.sin(a0), 0), occ.addPoint(r1 * math.cos(a0), r1 * math.sin(a0), 0),
             occ.addPoint(r1 * math.cos(a1), r1 * math.sin(a1), 0), occ.addPoint(r0 * math.cos(a1), r0 * math.sin(a1), 0)]
        c0 = occ.addPoint(0, 0, 0)
        l = [occ.addLine(p[0], p[1]), occ.addCircleArc(p[1], c0, p[2]), occ.addLine(p[2], p[3]), occ.addCircleArc(p[3], c0, p[0])]
        return (2, occ.addPlaneSurface([occ.addCurveLoop(l)]))
    def ring(r0, r1):
        a = occ.addDisk(0, 0, 0, r1, r1); b = occ.addDisk(0, 0, 0, r0, r0)
        out, _ = occ.cut([(2, a)], [(2, b)]); return out
    def patch(rc, ac, dr, da_sign):
        """fillet filler in a re-entrant corner at (rc, ac deg): material grows to radius rc + dr (dr signed) and to the
        angle side da_sign; the filler is the corner square minus the disk tangent to both edges"""
        rho = RHO_S; da = math.degrees(rho / rc)
        sq = sector(min(rc, rc + dr), max(rc, rc + dr), min(ac, ac + da_sign * da), max(ac, ac + da_sign * da))
        rcc = rc + dr; acc = math.radians(ac + da_sign * da)
        dk = occ.addDisk(rcc * math.cos(acc), rcc * math.sin(acc), 0, rho, rho)
        out, _ = occ.cut([sq], [(2, dk)]); return out
    parts = ring(g['ri'], g['r1']) + ring(g['r2'], g['ro'])
    for pc in isfd_pieces(g): parts.append(sector(*pc))
    for cr in isfd_corners(g): parts += patch(*cr)
    body, _ = occ.fuse(parts[:1], parts[1:])
    occ.synchronize()
    curves = [c for _, c in gmsh.model.getEntities(1)]
    def on_r(c, r):
        lo, hi = gmsh.model.getParametrizationBounds(1, c)
        P = np.array(gmsh.model.getValue(1, c, list(np.linspace(lo[0], hi[0], 5)))).reshape(-1, 3)
        return bool(np.all(np.abs(np.hypot(P[:, 0], P[:, 1]) - r) < 1e-4))
    inner = [c for c in curves if on_r(c, g['ri'])]; outer = [c for c in curves if on_r(c, g['ro'])]
    fd = gmsh.model.mesh.field.add('Distance'); gmsh.model.mesh.field.setNumbers(fd, 'CurvesList', [c for c in curves if c not in inner + outer])
    ft = gmsh.model.mesh.field.add('Threshold'); gmsh.model.mesh.field.setNumber(ft, 'InField', fd)
    for k_, v in (('SizeMin', h_f), ('SizeMax', h * 3), ('DistMin', 0.1), ('DistMax', 2.0)): gmsh.model.mesh.field.setNumber(ft, k_, v)
    gmsh.model.mesh.field.setAsBackgroundMesh(ft)
    for k_, v in (('Mesh.MeshSizeExtendFromBoundary', 0), ('Mesh.MeshSizeFromPoints', 0), ('Mesh.ElementOrder', 2),
                  ('Mesh.SecondOrderLinear', 0), ('Mesh.Algorithm', 6), ('Mesh.HighOrderOptimize', 2)): gmsh.option.setNumber(k_, v)
    gmsh.model.mesh.generate(2)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(9)
    def cn(cs):
        s = set()
        for c in cs:
            n_, _, _ = gmsh.model.mesh.getNodes(1, c, includeBoundary=True); s.update(int(v) for v in n_)
        return sorted(s)
    ni, no = cn(inner), cn(outer)
    gmsh.finalize()
    tri = np.asarray(en, np.int64).reshape(-1, 6); ix = {int(t): i for i, t in enumerate(nt)}
    P = xyz[np.vectorize(ix.get)(tri[:, :3])]
    neg = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1])) < 0
    tri[neg] = tri[neg][:, [0, 2, 1, 5, 4, 3]]                      # counter-clockwise for CPS6
    return dict(tags=np.asarray(nt, np.int64), X=xyz[:, :2], tri=tri, inner=ni, outer=no)


def isfd_run(g, h, tag, d):
    """two linear solves: inner ring moved by 0.01 mm in x and in y; returns k [N/mm] per direction and the stress fields
    per unit displacement at the nodes"""
    os.makedirs(d, exist_ok=True)
    m = isfd_mesh(g, h)
    X = {int(t): m['X'][i] for i, t in enumerate(m['tags'])}
    L = ['*NODE, NSET=NALL\n' + ''.join('%d, %.7f, %.7f\n' % (k, *v) for k, v in X.items())]
    L.append('*ELEMENT, TYPE=CPS6, ELSET=EALL\n' + ''.join('%d, %s\n' % (i + 1, ', '.join(map(str, e))) for i, e in enumerate(m['tri'])))
    L.append('*NSET, NSET=NIN\n' + ''.join('%d,\n' % k for k in m['inner']) + '*NSET, NSET=NOUT\n' + ''.join('%d,\n' % k for k in m['outer']))
    L.append('*MATERIAL, NAME=PH\n*ELASTIC\n%.1f, %.3f\n*SOLID SECTION, ELSET=EALL, MATERIAL=PH\n%.3f\n' % (ISFD_MAT['E'], ISFD_MAT['nu'], g['Lf']))
    for dx, dy in ((0.01, 0.0), (0.0, 0.01)):
        L.append('*STEP\n*STATIC\n*BOUNDARY, OP=NEW\nNOUT, 1, 2, 0.\nNIN, 1, 1, %.4f\nNIN, 2, 2, %.4f\n' % (dx, dy))
        L.append('*NODE PRINT, NSET=NIN, TOTALS=ONLY\nRF\n*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n')
    open(os.path.join(d, tag + '.inp'), 'w').write(''.join(L))
    env = dict(os.environ, OMP_NUM_THREADS=str(THREADS))
    subprocess.run([CCX, '-i', tag], cwd=d, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    rf = []; on = False
    for line in open(os.path.join(d, tag + '.dat')):
        if 'total force' in line: on = True; continue
        if on and line.strip():
            rf.append([float(v) for v in line.split()[:2]]); on = False
    R = read_frd_steps(os.path.join(d, tag + '.frd'), want=('STRESS',))
    ids = R[1]['STRESS'][0]; Sx = R[1]['STRESS'][1] / 0.01; Sy = R[2]['STRESS'][1] / 0.01   # per mm
    P = np.array([X[int(k)] for k in ids])
    kx, ky = abs(rf[0][0]) / 0.01, abs(rf[1][1]) / 0.01                                      # N / mm
    return dict(kx=kx, ky=ky, k_cross=abs(rf[0][1]) / 0.01, n_nodes=len(X), ids=ids, P=P, Sx=Sx, Sy=Sy)


def isfd_orbit_stress(r, sag_mm, e_mm, n_t=72):
    """stress history at every node for the static sag (downward, -y) plus a circular synchronous orbit e: max principal
    range / mean and peak von Mises; 2D components xx yy zz xy (plane stress)"""
    tt = np.linspace(0, 2 * math.pi, n_t, endpoint=False)
    s1max = np.full(len(r['ids']), -1e9); s1min = np.full(len(r['ids']), 1e9); s3max = s1max.copy(); s3min = s1min.copy(); vmax = np.zeros(len(r['ids']))
    for t in tt:
        S = -sag_mm * r['Sy'] + e_mm * (math.cos(t) * r['Sx'] + math.sin(t) * r['Sy'])
        sxx, syy, sxy = S[:, 0], S[:, 1], S[:, 3]
        c = 0.5 * (sxx + syy); rad = np.hypot(0.5 * (sxx - syy), sxy); s1, s3 = c + rad, c - rad
        s1max, s1min = np.maximum(s1max, s1), np.minimum(s1min, s1); s3max, s3min = np.maximum(s3max, s3), np.minimum(s3min, s3)
        vmax = np.maximum(vmax, np.sqrt(s1 ** 2 - s1 * s3 + s3 ** 2))
    gm = []
    for hi, lo in ((s1max, s1min), (s3max, s3min)):
        sa, sm = 0.5 * (hi - lo), 0.5 * (hi + lo)
        gm.append(sa / ISFD_MAT['Se'] + np.maximum(sm, 0.0) / ISFD_MAT['Su'])
    g_ = np.maximum(gm[0], gm[1]); i = int(np.argmax(g_))
    sa_ = 0.5 * (s1max - s1min)[i] if gm[0][i] >= gm[1][i] else 0.5 * (s3max - s3min)[i]
    sm_ = 0.5 * (s1max + s1min)[i] if gm[0][i] >= gm[1][i] else 0.5 * (s3max + s3min)[i]
    return dict(vm_max=float(vmax.max()), at=r['P'][int(np.argmax(vmax))].tolist(), goodman_factor=float(1 / g_[i]), s_a=float(sa_), s_m=float(sm_))


def isfd_design():
    """the ISFD of cad/engine/a1000_rotor.py (ISFD / SFD dicts): hairpin springs if ISFD['kind'] == 'hairpin', else the
    drawn single-beam ring"""
    q = G.ISFD
    if q.get('kind') == 'hairpin':
        return isfd_hairpin(t=q['t'], span=q['span'], gap=q['gap'], w_web=q['w_web'], w_u=q['w_u'], t_ring=q['t_ring'], n=q['n'])
    return isfd_geometry()


def damper_orbits():
    """damper (housing DOF) orbit amplitudes [mm] at 95 % .. 110 % speed for the API 617 unbalance cases of the rotor
    stack, nominal support"""
    S = stack_mod(); R = stack()
    Rd = S.detailed_rotor(None); sp = R['rotordynamics']['nominal']['support']
    x = RD.mesh_nodes(Rd); M, K, C, Gm = RD.assemble(Rd, x, sp)
    W1, W2, xcg = RD.journal_loads(Rd); nx = len(x)
    cases = dict(mid=[(xcg, 0.0, W1 + W2)], conical=[(Rd['discs']['impeller1']['x'], 0.0, W1), (Rd['discs']['blisk2']['x'], math.pi, W2)],
                 turbine=[(Rd['discs']['blisk2']['x'], 0.0, 2 * W2)])
    amp = [0.0, 0.0]
    for N in np.arange(0.95 * N_OP, 1.10 * N_OP + 1, 250.0):
        Om = N * math.pi / 30
        for locs in cases.values():
            F = np.zeros(len(M), complex)
            for xl, ph, Wk in locs:
                U = 6350 * Wk / RD.N_MCS * 1e-6; j = int(np.argmin(abs(x - xl))); F[2 * j] += U * Om * Om * np.exp(1j * ph)
            q = np.linalg.solve(K - Om * Om * M + 1j * Om * C + Om * Om * Gm, F)
            for i in range(2): amp[i] = max(amp[i], abs(q[2 * nx + i]) * 1e3)
    return dict(JB1=amp[0], JB2=amp[1], W_N=[W1 * 9.81, W2 * 9.81])


def isfd_damping(g, mu=None):
    """squeeze-film damping of the 4 pads (short bearing per pad, open ends): C = mu R L^3 / c^3 sum int cos^2; pi film = C / 2;
    end leakage conductance and the land pressure for the feed flow"""
    s = G.SFD; mu = mu or stack_mod().visc(70.0)
    R, L, c = s['R'] * 1e-3, s['L'] * 1e-3, s['c'] * 1e-3
    th = [math.radians(G.ISFD_CLOCK + g['span'] + 360.0 / g['n'] * (k + 0.5) - g['span'] / 2) for k in range(g['n'])]
    b = math.radians(s['pad'])
    I = sum(b / 2 + math.sin(b) * math.cos(2 * t) / 2 for t in th)            # sum of int cos^2 over the pads
    C = mu * R * L ** 3 / c ** 3 * I
    G_leak = g['n'] * 2 * c ** 3 * (R * b) / (12 * mu * L / 2)               # m3 / (s Pa), both ends of every pad
    return dict(C_full=C, C_pi=0.5 * C, mu=mu, pads=g['n'], pad_deg=s['pad'], R_mm=s['R'], L_mm=s['L'], c_mm=s['c'], G_leak=G_leak,
                p_land_bar_per_lpm=1.0 / 6e4 / G_leak / 1e5)


def isfd_main():
    d = os.path.join(RUNS, 'isfd'); os.makedirs(d, exist_ok=True)
    out = dict(material=ISFD_MAT, fillet_mm=RHO_S)
    # as drawn (rotor rev 1.3 / sec. 19): 8 single beams
    g0 = isfd_geometry(dict(n=8, t=4.2, span=30.0))
    r0 = isfd_run(g0, 0.5, 'drawn', d)
    o0 = isfd_orbit_stress(r0, 1184.0 / (0.5 * (r0['kx'] + r0['ky'])), 0.13)
    out['as_drawn'] = dict(n=8, t=4.2, span=30.0, k_N_m=0.5 * (r0['kx'] + r0['ky']) * 1e3, k_formula_N_m=31414273.66,
                           vm_bottomed=o0['vm_max'], film_gap='none (the beams sit 1.9 mm from both rings)')
    print('ISFD as drawn: k %.3e N/m (FE) vs %.3e (beam formula used in the rotor dynamics)' % (out['as_drawn']['k_N_m'], out['as_drawn']['k_formula_N_m']))
    g = isfd_design(); conv = []
    for h in (0.7, 0.5, 0.35, 0.25):
        r = isfd_run(g, h, 'hp_h%g' % h, d)
        orb = damper_orbits() if not conv else orb
        res = dict(h=h, n_nodes=r['n_nodes'], k=0.5 * (r['kx'] + r['ky']) * 1e3, aniso=abs(r['kx'] - r['ky']) / r['kx'],
                   vm_bottom=isfd_orbit_stress(r, orb['W_N'][1] / (0.5 * (r['kx'] + r['ky'])), G.SFD['c'])['vm_max'])
        conv.append(res); print('  hairpin h %.2f: %d nodes, k %.4e N/m, peak vm at sag + c %.1f MPa' % (h, r['n_nodes'], res['k'], res['vm_bottom']))
    out['convergence'] = conv
    k = conv[-1]['k'] * 1e-3                                                   # N/mm
    out['design'] = dict(g, k_N_m=conv[-1]['k'])
    cases = {}
    for brg, W in (('JB1', orb['W_N'][0]), ('JB2', orb['W_N'][1])):
        sag = W / k
        for lab, e in (('static sag', 0.0), ('sag + API 1x orbit', orb[brg]), ('sag + 0.5 c orbit (continuous, robust)', 0.5 * G.SFD['c']),
                       ('blade loss: damper bottomed (sag + c)', G.SFD['c'])):
            o = isfd_orbit_stress(r, sag, e); o.update(sag_um=sag * 1e3, orbit_um=e * 1e3)
            cases['%s | %s' % (brg, lab)] = o
            print('  %s %-40s sag %.1f um orbit %.2f um: vm %.0f MPa, Goodman factor %.2f' % (brg, lab, sag * 1e3, e * 1e3, o['vm_max'], o['goodman_factor']))
    out['cases'] = cases; out['orbits'] = orb
    out['damping'] = isfd_damping(g)
    print('  pads: C full film %.0f / pi film %.0f Ns/m' % (out['damping']['C_full'], out['damping']['C_pi']))
    return out


if __name__ == '__main__' and '--isfd' in sys.argv:
    o = isfd_main()
    R_ = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
    R_['isfd'] = o; json.dump(R_, open(OUT_JSON, 'w'), indent=1, default=lambda v: v.tolist() if hasattr(v, 'tolist') else float(v))


# ================================================================================================ checks, JSON, plots
RUN_LEVEL = dict(stub_I1='medium', I1_spc='coarse', spc_I2='coarse', I2_drum='coarse', drum_R1='hcoarse', R2_stub='hcoarse',
                 R1_R2='hvcoarse')
RUN_LEVEL.update(dict(kv.split('=') for kv in os.environ.get('A1000_P4_LEVELS', '').split(',') if '=' in kv))   # override
CONV = dict(stub_I1=('coarse', 'medium', 'fine'), drum_R1=('hvcoarse', 'hcoarse'))
# IN718 stress rupture, typical (Larson-Miller, C = 20): P = T[K] (20 + log10 t) / 1000 -> stress [MPa]; 1000-h points
# 538 / 593 / 649 / 704 / 760 C ~ 1000 / 860 / 690 / 480 / 280 MPa (to be replaced by the stud supplier's certified data)
LMP_IN718 = ([18.65, 19.92, 21.21, 22.47, 23.76], [1000.0, 860.0, 690.0, 480.0, 280.0])




def _done(tag):
    f = os.path.join(RUNS, tag, 'done'); return os.path.exists(f) and open(f).read() == 'ok'


def hot_root_design(out, Mb):
    """root-radius study of the hot curvics: tooth-root stress ratios R1.0 / R0.6 per material from the drum_R1 pair
    (hvcoarse, same loads); reported, not applied (the MAR-M247 flange peak is membrane / coning, not the fillet)"""
    if not (_done('drum_R1_hvcoarse') and _done('drum_R1_hvcoarse_r10')): return None
    Jd = joints()['drum_R1']; ld = joint_loads('drum_R1', Jd, Mb)
    r6, r10 = post_joint('drum_R1_hvcoarse', Jd, ld)['root'], post_joint('drum_R1_hvcoarse_r10', Jd, ld)['root']
    rat = {}
    for pn in r6:
        a, b = r6[pn], r10[pn]
        rat['MAR-M247' if a['mat'] == 'MAR-M247' else 'other'] = dict(
            s=b['cases']['b']['s1'] / a['cases']['b']['s1'], rng=b['range_ab'] / a['range_ab'], rng_sc=b['range_ad'] / a['range_ad'],
            vm=b['vm_steady'] / a['vm_steady'], rare=b['vm_rare'] / a['vm_rare'])
    return rat


def rupture_in718(T, hours=1e5):
    return float(np.interp((T + 273.15) * (20 + math.log10(hours)) / 1000, *LMP_IN718))


def rd_with_joints(kb):
    """critical speeds of the detailed rotor with the curvic joints as rotational springs: at each joint plane a 2 mm piece
    of the beam gets the flexibility l / EI + 1 / k_theta (kb: {joint plane x: k_theta N m / rad}); nominal ISFD support"""
    S = stack_mod(); R = stack()
    Rd = S.detailed_rotor(None); sp = R['rotordynamics']['nominal']['support']
    E_hot = dict(marm247=170e9, in718=175e9); seg = []
    cuts = sorted(set(c for x in kb for c in (x - 1.0, x + 1.0)))
    for sg in Rd['seg']:
        pts = [sg[0]] + [c for c in cuts if sg[0] + 1e-6 < c < sg[1] - 1e-6] + [sg[1]]
        for a, b in zip(pts[:-1], pts[1:]):
            piece = (a, b) + tuple(sg[2:]); xm = 0.5 * (a + b)
            for x, k in kb.items():
                if x - 1.0 <= xm <= x + 1.0 and k > 0:                       # the 2 mm window carries 1 / k
                    E = E_hot.get(sg[4], RD.MAT[sg[4]][1]); I = math.pi / 64 * ((sg[2] * 1e-3) ** 4 - (sg[3] * 1e-3) ** 4)
                    l = (b - a) * 1e-3; Ie = l / (E * (l / (E * I) + (l / 2e-3) / k))
                    od = ((Ie * 64 / math.pi) + (sg[3] * 1e-3) ** 4) ** 0.25 * 1e3
                    piece = (a, b, od) + tuple(sg[3:])
            seg.append(piece)
    Rj = dict(Rd, seg=seg)
    return [dict(N=c['N'], AF=c['AF'], SM=c['SM'], SM_req=c['SM_req'], ok=c['ok']) for c in RD.damped_criticals(Rj, sp)]


def post_all():
    J = joints()
    Mb, info = bending_moments()
    R = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
    R.update(bending_moments=Mb, bending_info=info, tie_bolt=tie_bolt_states(), settings=dict(mu=MU, k_pen=K_PEN, k_stick=K_STICK,
             phi=PHI, c_root=C_ROOT, rho_fillet=RHO_F, tip_chamfer=TIP_CH, sc_factor=SC_FACTOR, N_os=N_OS, levels=LEVELS))
    out = {}; chk = []
    def check(test, value, limit, unit, ok, note=''):
        chk.append(dict(test=test, value=float(value), limit=float(limit), unit=unit, ok=bool(ok), note=note))
        print('  %-62s %10.4g %-4s (limit %.4g) %s  %s' % (test, value, unit, limit, 'OK' if ok else 'FAIL', note))
    for name, Jn in J.items():
        ld = joint_loads(name, Jn, Mb); lev = RUN_LEVEL[name]
        tag = '%s_%s' % (name, lev)
        if not os.path.exists(os.path.join(RUNS, tag, 'done')) or open(os.path.join(RUNS, tag, 'done')).read() != 'ok':
            print('  (no complete results for %s)' % tag); continue
        r = post_joint(tag, Jn, ld)
        sol = os.path.join(RUNS, tag + '_solid')
        if os.path.exists(os.path.join(sol, 'job.frd')):
            rs = post_joint(tag + '_solid', Jn, ld)['stiffness_model']
            k = {}
            for kk in ('axial_a', 'axial_b'):
                if kk in r['stiffness_model'] and kk in rs:
                    ci = 1 / r['stiffness_model'][kk] - 1 / rs[kk]
                    k['interface_' + kk] = 1 / ci if ci > 0 else float('inf')
            if 'torsion_a' in rs: k['interface_torsion_a'] = 1 / max(1 / r['stiffness_model']['torsion_a'] - 1 / rs['torsion_a'], 1e-30)
            a_, b_ = Jn['ri'], Jn['ro']; ia = (a_ * a_ + b_ * b_) / 4                     # I / A of the tooth ring [mm2]
            for kk in ('a', 'b'):
                if 'interface_axial_' + kk in k: k['interface_bending_' + kk] = k['interface_axial_' + kk] * ia * 1e-3   # N m / rad
            k['solid'] = rs; r['stiffness'] = k
        # case e from a direct run with the real bending moment when there is one (<tag>_bend; same model, e solved, not
        # superposed): the compressor check run showed the superposition under-predicts the coast-flank unloading
        bt = os.path.join(RUNS, tag.replace('_' + lev, '_coarse') + '_bend') if J[name]['kind'] == 'comp' else None
        if bt and os.path.exists(os.path.join(bt, 'done')) and open(os.path.join(bt, 'done')).read() == 'ok':
            rb = post_joint(os.path.basename(bt), Jn, ld)
            for kc in r['contact']:
                r['contact'][kc]['cases']['e'] = rb['contact'][kc]['cases']['e']
            for pn in r['root']:
                rt, rbt = r['root'][pn], rb['root'][pn]
                rt['cases']['e'] = rbt['cases']['e']
                rt['vm_steady'] = max(rt['cases'][c]['vm'] for c in ('a', 'b', 'e'))
                rt['yield_margin'] = mp(rt['mat'], 'Sy', rt['T']) / rt['vm_steady']
            r['e_direct'] = os.path.basename(bt); r.pop('e_superposition', None)
        r['loads'] = {kk: vv for kk, vv in ld.items() if kk != 'tb'}
        out[name] = r
        # ------------------------------------------------ checks per joint
        for kc, cv in enumerate(Jn['curvics']):
            C = r['contact'][str(kc)] if str(kc) in r['contact'] else r['contact'][kc]
            cs = C['cases']; lab = name if len(Jn['curvics']) == 1 else '%s (face %d)' % (name, kc + 1)
            mats = [Jn['parts'][cv['lo']], Jn['parts'][cv['hi']]]
            Sy = min(mp(P['mat'], 'Sy', P['T']) for P in mats)
            sep = min(cs[c]['coast_frac'] for c in ('b', 'c', 'd', 'e') if c in cs)
            wc = min(('b', 'c', 'd', 'e'), key=lambda c: cs[c]['coast_frac'] if c in cs else 9)
            check('%s: coast-flank load left / assembly (min over b-e)' % lab, sep, 0.20, '-', sep >= 0.20, 'worst case %s' % wc)
            tm = min(cs[c]['tooth_any_min_frac'] for c in cs)
            check('%s: every tooth flank keeps contact (min load share)' % lab, tm, 0.0, '-', tm > 0.0, 'centring by the teeth (no spigot)')
            pm = max(cs[c]['p_mean'] for c in cs); p95 = max(cs[c]['p95'] for c in cs); p99 = max(cs[c]['p99'] for c in cs)
            check('%s: mean flank pressure / 0.6 Sy' % lab, pm / (0.6 * Sy), 1.0, '-', pm <= 0.6 * Sy, '%.0f MPa' % pm)
            check('%s: 95th-percentile flank pressure / 1.6 Sy' % lab, p95 / (1.6 * Sy), 1.0, '-', p95 <= 1.6 * Sy,
                  '%.0f MPa; p99 %.0f MPa at the flank edges (flat model flanks; drawing: crowning / edge relief)' % (p95, p99))
            sr = C['slip_per_rev_um']['p99']
            ti = any(P['mat'] == 'Ti64' for P in mats)                 # Ti64 flanks: CuNiIn + MoS2 (anti-fretting) specified
            lim = 25.0 if ti else 5.0
            check('%s: flank slip per revolution, 99th percentile (1 g bending)' % lab, sr, lim, 'um', sr <= lim,
                  'fretting; %s; max %.1f um at single nodes' % ('Ti64 flanks CuNiIn + MoS2 (25 um)' if ti else 'uncoated (5 um)',
                                                               C['slip_per_rev_um']['max']))
        for pn, rt in r['root'].items():
            check('%s %s: tooth-root yield margin, Sy / local peak (a, b, e)' % (name, pn), rt['yield_margin'], 1.0, '-', rt['yield_margin'] >= 1.0,
                  '%.0f MPa vm, %s' % (rt['vm_steady'], rt['mat']))
            check('%s %s: overspeed / short circuit, Su / local peak (c, d)' % (name, pn), rt['rare_margin'], 1.0, '-', rt['rare_margin'] >= 1.0,
                  '%.0f MPa vm (one-off events: local yield allowed)' % rt['vm_rare'])
            check('%s %s: tooth-root LCF starts (a -> b)' % (name, pn), rt['lcf_starts'], STARTS_REQ, 'cyc', rt['lcf_starts'] >= STARTS_REQ,
                  'range %.0f MPa' % rt['range_ab'])
            check('%s %s: tooth-root LCF, short circuits (a -> d)' % (name, pn), rt['lcf_short_circuits'], 100, 'cyc', rt['lcf_short_circuits'] >= 100,
                  'range %.0f MPa' % rt['range_ad'])
        if 'stud' in r:
            T = Jn['T']; so = r['stud']; sm_ = Jn['stud'].get('mat', 'IN718')
            F_run = json.load(open(os.path.join(RUNS, tag, 'meta.json')))['loads'].get('F_pre', ld['F_pre'])
            if abs(F_run - ld['F_pre']) > 1.0:                         # run at another preload: stud stresses scaled (preload-
                kp = ld['F_pre'] / F_run                               # dominated); the clamp results stay (lower preload =
                for s_ in so.values():                                 # conservative for separation)
                    s_['F'] *= kp; s_['vm_shank_max'] *= kp
                    for v in s_['sections'].values():
                        for kk in ('mean', 'max', 'bend'): v[kk] *= kp
                r['stud_scaled_from_kN'] = F_run / 1e3
            smax = max(max(v['max'] for v in s_['sections'].values()) for s_ in so.values())
            smean = max(max(v['mean'] for v in s_['sections'].values()) for s_ in so.values())
            fmin = min(s_['F'] for s_ in so.values() if s_['F'] == s_['F']) / ld['F_pre']
            check('%s studs: peak (mean + bending) / 0.9 Sy' % name, smax / (0.9 * mp(sm_, 'Sy', T)), 1.0, '-', smax <= 0.9 * mp(sm_, 'Sy', T),
                  '%.0f MPa at %.0f C, %s' % (smax, T, sm_))
            if sm_ == 'IN718':                                         # (Waspaloy R1 - R2 studs: relaxation and re-torque, sec. 22)
                sr_ = rupture_in718(T)
                check('%s studs: mean stress / (rupture 1e5 h / 1.5)' % name, smean / (sr_ / 1.5), 1.0, '-', smean <= sr_ / 1.5,
                      '%.0f MPa vs %.0f MPa (IN718, %.0f C)' % (smean, sr_, T))
            check('%s studs: min stud force / preload' % name, fmin, 0.5, '-', fmin >= 0.5, 'before the 10 % relaxation allowance')
    # hot joints: root-radius study (R1.0 vs R0.6 on drum_R1), reported only
    rat = hot_root_design(out, Mb)
    if rat: R['hot_root_ratio_R10_R06'] = rat
    # mesh convergence
    conv = {}
    for name, levs in CONV.items():
        rows = []
        for lev in levs:
            tag = '%s_%s' % (name, lev)
            if not os.path.exists(os.path.join(RUNS, tag, 'done')) or open(os.path.join(RUNS, tag, 'done')).read() != 'ok': continue
            try:
                rr = post_joint(tag, J[name], joint_loads(name, J[name], Mb))
            except Exception as e:
                print('  convergence %s: %s' % (tag, e)); continue
            pk = max(v['cases']['b']['s1'] for v in rr['root'].values())
            c0 = rr['contact'][0] if 0 in rr['contact'] else rr['contact']['0']
            rows.append(dict(level=lev, n_nodes=rr['n_nodes'], root_s1_b=pk, p_mean_b=c0['cases']['b']['p_mean'],
                             coast_frac_d=c0['cases']['d']['coast_frac'] if 'd' in c0['cases'] else None))
        conv[name] = rows
        if len(rows) >= 2:
            d_ = abs(rows[-1]['root_s1_b'] - rows[-2]['root_s1_b']) / rows[-1]['root_s1_b']
            check('mesh convergence %s: peak root stress, last refinement' % name, 100 * d_, 10.0, '%', d_ <= 0.10,
                  '%s -> %s' % (rows[-2]['level'], rows[-1]['level']))
    R['convergence'] = conv
    # ISFD
    if 'isfd' in R:
        I = R['isfd']; k_rd = 31414273.66
        kfe = I['design']['k_N_m']
        check('ISFD radial stiffness, 2D FE / rotor-dynamics value', kfe / k_rd, 1.0, '-', abs(kfe / k_rd - 1) <= 0.10,
              '%.3e N/m; as drawn (8 beams) %.2e' % (kfe, I['as_drawn']['k_N_m']))
        cv_ = I['convergence']; dk = abs(cv_[-1]['vm_bottom'] - cv_[-2]['vm_bottom']) / cv_[-1]['vm_bottom']
        check('ISFD mesh convergence: peak stress, last refinement', 100 * dk, 5.0, '%', dk <= 0.05, '%d -> %d nodes' % (cv_[-2]['n_nodes'], cv_[-1]['n_nodes']))
        for brg in ('JB1', 'JB2'):
            bl = I['cases']['%s | blade loss: damper bottomed (sag + c)' % brg]
            check('ISFD %s spring stress, blade loss (bottomed) / 0.9 YS' % brg, bl['vm_max'] / (0.9 * ISFD_MAT['Sy']), 1.0, '-',
                  bl['vm_max'] <= 0.9 * ISFD_MAT['Sy'], '%.0f MPa' % bl['vm_max'])
            for lab in ('sag + API 1x orbit', 'sag + 0.5 c orbit (continuous, robust)'):
                o = I['cases']['%s | %s' % (brg, lab)]
                check('ISFD %s Goodman factor, %s' % (brg, lab), o['goodman_factor'], 1.5, '-', o['goodman_factor'] >= 1.5,
                      'Se %.0f / Su %.0f MPa' % (ISFD_MAT['Se'], ISFD_MAT['Su']))
        dmp = I['damping']
        check('ISFD land: film gap c in the ring (pads, CAD = model)', G.SFD['c'], 0.10, 'mm', G.ISFD.get('kind') == 'hairpin' and G.SFD['c'] >= 0.10,
              '%d pads x %.0f deg, R %.0f, L %.0f, open ends' % (dmp['pads'], dmp['pad_deg'], dmp['R_mm'], dmp['L_mm']))
    R['joints'] = out; R['checks'] = chk
    if os.environ.get('A1000_P4_NO_RD') != '1':
        rd_joints(R, check)
    R['checks'] = chk
    json.dump(R, open(OUT_JSON, 'w'), indent=1, default=lambda v: v.tolist() if hasattr(v, 'tolist') else float(v))
    print('checks: %d of %d pass' % (sum(c['ok'] for c in chk), len(chk)))
    return R


def rd_joints(R, check):
    """rotor dynamics with the joint bending flexibilities (15k interface values; the compressor joints sit on hub
    segments of the beam model, the hot joints on the flanges)"""
    out = R['joints']
    xj = dict(stub_I1=[G.X_I1[0]], I1_spc=[G.X_I1[1]], spc_I2=[G.X_I2[0]], I2_drum=[G.X_I2[1]], drum_R1=[G.X_J['drum_R1']],
              R1_R2=[G.X_J['R1_spc'], G.X_J['spc_R2']], R2_stub=[G.X_J['R2_stub']])
    kb = {}
    for nm, xs in xj.items():
        k_ = out.get(nm, {}).get('stiffness', {}).get('interface_bending_b')
        if k_ and math.isfinite(k_):
            for x in xs: kb[x] = k_ * (2.0 if nm == 'R1_R2' else 1.0)            # R1 - R2: two faces in the model's one value
    if kb:
        cr = rd_with_joints(kb); R['rd_with_joints'] = dict(k_theta=kb, criticals=cr)
        base = stack()['rotordynamics']['nominal']['criticals']
        for c0, c1 in zip(base, cr):
            print('  critical %.0f -> %.0f rpm with the joint flexibilities (SM %.1f %%, req %.1f %%)' % (c0['N'], c1['N'], c1['SM'], c1['SM_req']))
        b3 = [c for c in cr if c['N'] > N_OP]
        if b3:
            check('bending critical with joint flexibilities: separation margin', b3[0]['SM'], b3[0]['SM_req'], '%', b3[0]['ok'],
                  '%.0f rpm (rigid joints %.0f)' % (b3[0]['N'], [c for c in base if c['N'] > N_OP][0]['N']))


if __name__ == '__main__' and '--post' in sys.argv:
    post_all()

if __name__ == '__main__' and '--rd' in sys.argv:                  # (re)do only the rotor dynamics with the joint springs
    R_ = json.load(open(OUT_JSON)); ck = [c for c in R_['checks'] if not c['test'].startswith('bending critical with joint')]
    def _check(test, value, limit, unit, ok, note=''):
        ck.append(dict(test=test, value=float(value), limit=float(limit), unit=unit, ok=bool(ok), note=note))
        print('  %-62s %10.4g %-4s (limit %.4g) %s  %s' % (test, value, unit, limit, 'OK' if ok else 'FAIL', note))
    rd_joints(R_, _check); R_['checks'] = ck
    json.dump(R_, open(OUT_JSON, 'w'), indent=1, default=lambda v: v.tolist() if hasattr(v, 'tolist') else float(v))
    print('checks: %d of %d pass' % (sum(c['ok'] for c in ck), len(ck)))


def plot_all(R):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(16, 10), dpi=110)
    J = joints(); names = [n for n in J if n in R.get('joints', {})]
    # (a) flank pressure map of the drum - R1 drive flanks, case b and d
    for i, (nm, case) in enumerate((('drum_R1', 'b'), ('drum_R1', 'd'))):
        ax = fig.add_axes([0.05 + 0.25 * i, 0.55, 0.15, 0.38])
        f = os.path.join(RUNS, '%s_%s' % (nm, RUN_LEVEL[nm]), 'map.npz')
        if os.path.exists(f):
            z = np.load(f); ok = z['p_' + case] > 0.5
            sc = ax.scatter(np.degrees(z['th']), z['r'], c=z['p_' + case], s=4, cmap='viridis', vmin=0)
            ax.scatter(np.degrees(z['th'][~ok]), z['r'][~ok], s=2, c='#d0d0d0')
            plt.colorbar(sc, ax=ax, label='flank pressure [MPa]', pad=0.03, fraction=0.12)
            ax.add_patch(plt.Circle((0.0, G.STUD['r']), 0.1, fill=False))
        ax.set_xlabel('angle [deg] (stud at 0)'); ax.set_ylabel('r [mm]')
        ax.set_title('drum - R1 drive flanks, %s\n(%s)' % (case, dict(b='15k, rated torque', d='15k, short circuit 6 x')[case]), fontsize=9)
    # (b) separation margins
    ax = fig.add_axes([0.58, 0.58, 0.40, 0.35])
    labs, sep, tm = [], [], []
    for nm in names:
        for kc, C in sorted(R['joints'][nm]['contact'].items()):
            labs.append(nm if len(J[nm]['curvics']) == 1 else '%s-%d' % (nm, int(kc) + 1))
            sep.append([C['cases'][c]['coast_frac'] for c in ('b', 'c', 'd', 'e')])
    sep = np.array(sep); w = 0.2
    for j, (c, col) in enumerate(zip(('b 15k', 'c 18k', 'd short circuit', 'e bending'), ('tab:blue', 'tab:orange', 'tab:red', 'tab:green'))):
        ax.bar(np.arange(len(labs)) + (j - 1.5) * w, sep[:, j], w, label=c, color=col)
    ax.axhline(0.2, color='k', ls='--', lw=0.8, label='limit 0.2'); ax.set_xticks(range(len(labs))); ax.set_xticklabels(labs, rotation=30, fontsize=8)
    ax.set_ylabel('coast-flank load / assembly'); ax.legend(fontsize=7, ncol=3); ax.grid(alpha=0.3)
    ax.set_title('Separation margin: coast-flank load left (1 = assembly)', fontsize=9)
    # (c) tooth-root margins
    ax = fig.add_axes([0.05, 0.08, 0.42, 0.36])
    rl, ym, lc = [], [], []
    for nm in names:
        for pn, rt in R['joints'][nm]['root'].items():
            rl.append('%s\n%s' % (nm, pn)); ym.append(rt['yield_margin']); lc.append(math.log10(rt['lcf_starts']))
    ax.bar(np.arange(len(rl)) - 0.2, ym, 0.4, label='yield margin (local peak)', color='tab:purple')
    ax2 = ax.twinx(); ax2.bar(np.arange(len(rl)) + 0.2, lc, 0.4, label='log10 LCF starts', color='tab:gray')
    ax.axhline(1.0, color='tab:purple', ls='--', lw=0.8); ax2.axhline(4.0, color='tab:gray', ls='--', lw=0.8)
    ax.set_xticks(range(len(rl))); ax.set_xticklabels(rl, rotation=60, fontsize=6); ax.set_ylabel('Sy / vm max'); ax2.set_ylabel('log10 starts')
    ax.set_title('Tooth root (fillet R %.1f): yield margin and start-stop LCF' % RHO_F, fontsize=9); ax.grid(alpha=0.3)
    # (d) stiffness table
    ax = fig.add_axes([0.55, 0.06, 0.42, 0.40]); ax.axis('off')
    rows = []
    for nm in names:
        k = R['joints'][nm].get('stiffness', {})
        rows.append([nm, '%.2e' % k.get('interface_axial_a', float('nan')), '%.2e' % k.get('interface_axial_b', float('nan')),
                     '%.2e' % k.get('interface_bending_b', float('nan')), '%.2e' % k.get('interface_torsion_a', float('nan'))])
    t = ax.table(cellText=rows, colLabels=['joint', 'axial cold [N/mm]', 'axial 15k [N/mm]', 'bending 15k [Nm/rad]', 'torsion [Nm/rad]'],
                 bbox=[0, 0, 1, 1], cellLoc='center'); t.auto_set_font_size(False); t.set_fontsize(8)
    ax.set_title('Interface stiffness (toothed joint minus a solid band)', fontsize=9)
    fig.suptitle('AURORA-1000 phase 4: curvic joints, 3D cyclic sectors with friction (CalculiX)', fontsize=11)
    fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_joint_fea.png')); plt.close(fig)
    # ISFD figure
    if 'isfd' in R:
        I = R['isfd']; g = isfd_design(); d = os.path.join(RUNS, 'isfd'); r = isfd_run(g, 0.35, 'plot', d)
        sag = I['orbits']['W_N'][1] / (I['design']['k_N_m'] * 1e-3)
        S = -sag * r['Sy'] + G.SFD['c'] * r['Sy'] * -1
        vmv = np.sqrt(S[:, 0] ** 2 - S[:, 0] * S[:, 1] + S[:, 1] ** 2 + 3 * S[:, 3] ** 2)
        fig = plt.figure(figsize=(15, 7), dpi=110)
        ax = fig.add_axes([0.03, 0.08, 0.45, 0.84]); sc = ax.scatter(r['P'][:, 0], r['P'][:, 1], c=vmv, s=0.3, cmap='inferno')
        plt.colorbar(sc, ax=ax, label='von Mises [MPa]'); ax.set_aspect('equal')
        from matplotlib.patches import Wedge
        for k in range(g['n']):                                        # damper pads (inner ring, not in the spring FE)
            a = G.ISFD_CLOCK + 360.0 / g['n'] * k
            ax.add_patch(Wedge((0, 0), G.SFD['R'] - G.SFD['c'], a + g['span'] + 1.5, a + 360.0 / g['n'] - 1.5, width=G.SFD['R'] - G.SFD['c'] - g['r1'],
                               fc='#bbbbbb', ec='none', alpha=0.6))
        ax.set_title('ISFD: 4 hairpin springs (FE) + 4 damper pads (grey)\nJB2 sag + c downward (damper bottomed): %.0f MPa peak' % vmv.max(), fontsize=9)
        ax = fig.add_axes([0.55, 0.55, 0.40, 0.37])
        cv = I['convergence']; ax.plot([c['n_nodes'] for c in cv], [c['k'] / 1e7 for c in cv], 'o-', label='k [1e7 N/m]')
        ax.plot([c['n_nodes'] for c in cv], [c['vm_bottom'] / 100 for c in cv], 's-', label='peak vm, bottomed [100 MPa]')
        ax.axhline(3.1414, color='k', ls='--', lw=0.8, label='rotor dynamics 3.14e7 N/m'); ax.set_xscale('log'); ax.legend(fontsize=8)
        ax.set_xlabel('nodes'); ax.grid(alpha=0.3); ax.set_title('mesh convergence (as drawn, 8 beams: k = %.2e N/m)' % I['as_drawn']['k_N_m'], fontsize=9)
        ax = fig.add_axes([0.55, 0.08, 0.40, 0.37]); ax.axis('off')
        rows = [[k_.replace(' | ', ': '), '%.0f' % v['vm_max'], '%.1f' % v['goodman_factor']] for k_, v in I['cases'].items()]
        t = ax.table(cellText=rows, colLabels=['case', 'vm max [MPa]', 'Goodman'], bbox=[0, 0, 1, 1], colWidths=[0.7, 0.15, 0.15])
        t.auto_set_font_size(False); t.set_fontsize(7)
        fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_isfd_fea.png')); plt.close(fig)


if __name__ == '__main__' and '--plot' in sys.argv:
    plot_all(json.load(open(OUT_JSON)))
