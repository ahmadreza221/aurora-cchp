#!/usr/bin/env python3
"""AURORA-1000 compressor impellers: structural checks with CalculiX (gmsh, C3D10, 1/13 cyclic sector).

Model: sector of cad/engine/a1000_impeller.py --sector (hub between two warped mid-passage cut surfaces + 1 main blade +
1 splitter with root fillets). The cut faces are tied by *CYCLIC SYMMETRY MODEL (13 sectors). Supports: the rear curvic
ring (radial teeth, radii of the rotor stack) holds the axial and tangential displacements, radial growth free; the front
face is free.
Steady metal temperature: hub T_bore -> T_tip (quadratic in r), blades from the inducer to the exit (linear in r).
Load cases (static, NLGEOM, centrifugal):
  op       15,000 rpm, design temperatures (inlet 15 C, chilled): von Mises, mean hoop (burst), LCF
  op_mech  15,000 rpm, E(T) without thermal strain: creep (primary stress)
  hot      15,000 rpm, hot day without inlet chilling (46 C inlet), mechanical: creep
  trip     16,500 rpm (110 %), design temperatures: yield margin, burst margin (area-mean hoop, 85 % UTS)
  spin     18,112 rpm (115 % of MCS 15,750), 20 C: overspeed / spin test, mean section stresses below yield
Modes: prestressed *FREQUENCY per nodal diameter (ND 0-6) at 0, 7,500, 12,000, 15,000, 16,500 rpm -> Campbell and ZZENF
against the engine orders: inlet EO 1-4, own vaned diffuser Z_d and 2 Z_d, stage 2 also the return-channel vanes Z_r (and
2 Z_r) and the stage-1 diffuser wakes Z_d1. EO k excites ND = k mod 13, folded to 0..6.
Vane-count scan (--post): margins of Z_d = 11..31 (strong 1 x, weak 2 x) on the computed families -> diffuser choice.
Materials (typical / design minimum, to be replaced by the forging supplier's certified data):
  Al 2618-T61 (RR58) die forging: UTS 440 / YS 370 MPa typical at 20 C, design minimum UTS 400 / YS 320 (AMS 4132 class);
            x 0.95 / 0.94 at 100 C, 0.80 / 0.82 at 150 C, 0.55 at 200 C (long exposure). Creep rupture: Larson-Miller
            (C = 20) fitted to the EN AW-2618A T61 test matrix of Han et al., Data in Brief 62 (2025) 112054 (BAM; stresses
            chosen from a literature compilation for 50 / 500 / 5,000 / 50,000 h at 160-230 C); minimum curve = 0.85 x
            stress; below the data (P < 9,400) the curve is extrapolated and capped at the UTS.
  Ti-6Al-4V annealed forging (AMS 4928 class): UTS 895 / YS 825 MPa minimum at 20 C, 780 / 690 at 150 C, 730 / 640 at
            200 C; creep negligible below ~300 C, sustained peak <= 0.8 YS (cold dwell)
Run:    python sim/engine/a1000_impeller_fea.py [C1|C2] [--static] [--modal] [--high] [--post]     (CCX = path to ccx)
        --high: families above 6 kHz at 15k (2 x vane orders); --post: checks from the saved results only
Writes: sim/engine/fea/a1000_impeller_<C1|C2>.json, docs/img/a1000_impeller_<C1|C2>_fea.png, docs/img/a1000_impeller_vanes.png
"""
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
import e1_turbine_fea as F                                    # noqa: E402  (ccx runner, frd reader, von Mises)
import e1_blisk_cyclic as CY                                  # noqa: E402  (parse_dat: ND / family table)
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_impeller as IMP                                  # noqa: E402
sys.argv = _argv

CAD = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
FEA = os.path.join(HERE, 'fea')
N_OP, N_MCS, N_TRIP = 15000.0, 15750.0, 16500.0
OM_N = N_OP * math.pi / 30
N_SPIN = 1.15 * N_MCS
SPEEDS = [0.0, 15000.0]                                       # modal solves; Campbell by Southwell (f^2 = f0^2 + S N^2)
BAND = (0.98, 1.02)                                           # grid-frequency band of the constant-speed set
NDS = tuple(int(v) for v in os.environ.get('A1000_NDS', '0,6').split(','))   # nodal diameters solved (13 sectors: 0..6)
FAM = dict(C1=12, C2=12)                                      # mode families per nodal diameter (0 / 15k / 16.5k rpm)
F_HIGH = dict(C1=(6000.0, 16), C2=(6000.0, 16))                  # high band at 15k: lower bound [Hz], families
H = dict(C1=dict(blade=1.8, hub=5.0), C2=dict(blade=1.5, hub=5.0))   # element size [mm], stress mesh
H_MODAL = dict(C1=dict(blade=2.6, hub=7.0), C2=dict(blade=2.2, hub=7.0))   # modal mesh (SPOOLES only in this ccx build)
# curvic rings (ri, ro) [mm] on the front / rear face (rotor stack cad/engine/a1000_rotor.py CURVIC_C: 36 teeth, 30 deg)
CURVIC = dict(C1=((44.0, 58.0), (50.0, 70.0)), C2=((52.0, 72.0), (55.0, 75.0)))
# metal temperatures [C]: hub bore, hub tip (back-face cavity), blades at the LE / exit; design (chilled inlet 15 C) and
# hot day without inlet chilling (46 C inlet: +39 / +50 K at the stage exits)
TEMP = dict(C1=dict(design=(60.0, 95.0, 20.0, 88.0), hot=(100.0, 135.0, 50.0, 128.0)),
            C2=dict(design=(150.0, 185.0, 95.0, 178.0), hot=(195.0, 235.0, 135.0, 228.0)))
STARTS_REQ = 10000
LIFE_REQ = 1.0e5
# vibration (rev 1): the impellers carry ~2.5 modes per kHz in every ND above 1.6 kHz, so no vane count clears all of them
# by 10 %. Criteria: (1) frequency margin to the FUNDAMENTAL families (first N_FUND of the excited ND: main-blade and
# splitter first bending, first disc-coupled mode), strong 10 % / weak 5 %; (2) for the nearest of ALL families, an upper
# bound of the resonant vibratory stress <= Goodman / 2 (as the turbine's interaction-order estimate):
#   sigma_vib = sigma_TE x (dp / q_cf) x 1 / (2 zeta) x MISTUNE, full modal participation
#   sigma_TE  steady blade peak (exit root, FE) from the centrifugal plate load q_cf = rho t_TE w^2 r2 sin(beta2)
#   dp        diffuser potential field at the impeller exit: A_POT x q3 x exp(-k Z (r3 / r2 - 1)), k = harmonic;
#             upstream vane wakes (return channel, diffuser 1 through the return channel): A_WAKE x q1 at the inducer
N_FUND = 3
ZETA, MISTUNE = 0.003, 1.5                                     # damping (material + aero, integral impeller), mistuning
A_POT, A_WAKE = 0.4, 0.05
SIG_E = {'Al 2618-T61': 100.0, 'Ti-6Al-4V': 380.0}             # 1e7 R = -1 fatigue strength, machined surface (x 0.8) [MPa]
PAR = int(os.environ.get('A1000_PAR', 3))                       # ccx jobs at a time (SPOOLES: ~3-5 GB each on the stress mesh)
THREADS = int(os.environ.get('CCX_THREADS', 3))

# ------------------------------------------------------------------------------------------------ materials
MATS = {
    'Al 2618-T61': dict(name='AL2618', T=np.array([20., 100., 150., 200.]), E=np.array([74e3, 71e3, 68e3, 64e3]), nu=0.33,
                        alpha=np.array([22.3, 23.0, 23.5, 24.0]) * 1e-6, rho=2.76e-9,
                        UTS=np.array([400., 380., 320., 220.]), YS=np.array([320., 300., 262., 176.]), RA=0.15),
    'Ti-6Al-4V': dict(name='TI64', T=np.array([20., 100., 150., 200., 250.]), E=np.array([114e3, 110e3, 107e3, 105e3, 102e3]),
                      nu=0.34, alpha=np.array([8.8, 9.0, 9.2, 9.4, 9.6]) * 1e-6, rho=4.43e-9,
                      UTS=np.array([895., 830., 780., 730., 700.]), YS=np.array([825., 740., 690., 640., 610.]), RA=0.30)}
MAT = {k: MATS[v['mat']] for k, v in IMP.ST.items()}             # material of each impeller (cad/engine/a1000_impeller.py)
# Al 2618A T61 creep-rupture design points (Han et al. 2025, BAM test matrix): (T [C], stress [MPa], rupture time [h])
AL_RUPTURE = [(160, 157, 5e4), (160, 202, 5e3), (160, 255, 500), (160, 290, 50), (180, 105, 5e4), (180, 152, 5e3),
              (180, 197, 500), (180, 242, 50), (190, 79, 5e4), (190, 128, 5e3), (190, 181, 500), (190, 230, 50),
              (230, 40, 5e4), (230, 70, 5e3), (230, 100, 500), (230, 140, 50)]


def lmp_fit():
    """Larson-Miller constant C and quadratic log10(stress) vs P fit through the Al 2618A points"""
    best = None
    for C in np.arange(14.0, 26.01, 0.25):
        P = np.array([(T + 273.15) * (C + math.log10(t)) for T, s, t in AL_RUPTURE]); y = np.log10([s for _, s, _ in AL_RUPTURE])
        c = np.polyfit(P, y, 2); res = float(np.sum((np.polyval(c, P) - y) ** 2))
        if best is None or res < best[0]: best = (res, C, c, P.min(), P.max())
    return dict(C=best[1], coef=best[2].tolist(), P_range=(best[3], best[4]), rms=math.sqrt(best[0] / len(AL_RUPTURE)))


LMP = lmp_fit()


def al_rupture_stress(T_C, hours, curve='min'):
    P = (T_C + 273.15) * (LMP['C'] + math.log10(hours))
    s = 10 ** np.polyval(LMP['coef'], max(P, LMP['P_range'][0] - 600.0))    # quadratic held flat 600 below the data
    s = min(s, float(np.interp(T_C, MATS['Al 2618-T61']['T'], MATS['Al 2618-T61']['UTS'])) / 0.85)
    return s * (0.85 if curve == 'min' else 1.0)


def al_rupture_hours(sigma, T_C, curve='min'):
    lo, hi = 0.0, 12.0
    if al_rupture_stress(T_C, 10 ** hi, curve) > sigma: return 1e12
    for _ in range(80):
        m = 0.5 * (lo + hi)
        if al_rupture_stress(T_C, 10 ** m, curve) > sigma: lo = m
        else: hi = m
    return 10 ** lo


def prop(key, name, T):
    m = MAT[key]; return float(np.interp(T, m['T'], m[name]))


def manson_cycles(key, d_eps, T, s_max):
    """start-stop LCF (0 -> max -> 0) by Manson's universal slopes, Morrow mean stress (s_max / 2), factors 2 on strain /
    20 on life (the smaller), as sim/engine/a1000_turbine_checks.py"""
    Su, E = prop(key, 'UTS', T), prop(key, 'E', T); D = -math.log(1 - MAT[key]['RA']); sm = 0.5 * s_max
    def N_of(de):
        lo, hi = 0.0, 12.0
        for _ in range(80):
            mm = 0.5 * (lo + hi); N = 10 ** mm
            if 3.5 * (Su - sm) / E * N ** -0.12 + D ** 0.6 * N ** -0.6 > de: lo = mm
            else: hi = mm
        return 10 ** lo
    return min(N_of(2 * d_eps), N_of(d_eps) / 20)


# ------------------------------------------------------------------------------------------------ geometry helpers
class Geo:
    def __init__(self, key):
        self.key = key; self.meta = json.load(open(os.path.join(CAD, 'A1000_%s_sector.json' % key)))
        self.imp = IMP.Impeller(key); self.cs = IMP.CutSurface(self.imp)
        self.pitch = 2 * math.pi / self.meta['Z']

    def r_hub(self, x):
        H = self.imp.H; return np.interp(x, H[:, 0], H[:, 1], left=H[0, 1], right=1e9)

    def is_blade(self, p):
        x, r = p[0], math.hypot(p[1], p[2]); return x < self.imp.xh2 - 0.05 and r > self.r_hub(x) + 0.3

    def cut_offset(self, p):
        """theta - theta_cut(x, r), wrapped to (-pi, pi]"""
        x, r = p[0], math.hypot(p[1], p[2]); d = math.atan2(p[2], p[1]) - float(self.cs.theta(x, r))
        return (d + math.pi) % (2 * math.pi) - math.pi


def mesh(g, h=None):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.add('sector'); gmsh.model.occ.importShapes(os.path.join(CAD, 'A1000_%s_sector.step' % g.key))
    gmsh.model.occ.synchronize()
    def samples(tag):
        lo, hi = gmsh.model.getParametrizationBounds(2, tag)
        return [gmsh.model.getValue(2, tag, [lo[0] + (hi[0] - lo[0]) * a, lo[1] + (hi[1] - lo[1]) * b])
                for a in (0.15, 0.5, 0.85) for b in (0.15, 0.5, 0.85)]
    faces = [t for _, t in gmsh.model.getEntities(2)]
    left, right, blade = [], [], []
    for t in faces:
        ps = samples(t); off = [g.cut_offset(p) for p in ps]     # (cut surface = B-spline fit of theta_cut: <= 0.01 rad)
        if all(abs(o) < 0.015 for o in off): left.append(t)
        elif all(abs(o - g.pitch) < 0.015 for o in off): right.append(t)
        elif sum(g.is_blade(p) for p in ps) >= 5: blade.append(t)
    if not left or not right: raise RuntimeError('cut faces: left %s right %s' % (left, right))
    a = g.pitch; c, s = math.cos(a), math.sin(a)
    if len(left) == len(right):
        def com(t): return np.array(gmsh.model.occ.getCenterOfMass(2, t))
        pairs = []
        for tl in left:
            p = com(tl); q = np.array([p[0], c * p[1] - s * p[2], s * p[1] + c * p[2]])
            pairs.append((tl, min(right, key=lambda t: np.linalg.norm(com(t) - q))))
        try:
            gmsh.model.mesh.setPeriodic(2, [tr for _, tr in pairs], [tl for tl, _ in pairs],
                                        [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1])
        except Exception as e:
            print('  periodic mesh not set (%s): the *TIE interpolates' % e)
    h = h or H[g.key]
    fd = gmsh.model.mesh.field.add('Distance'); gmsh.model.mesh.field.setNumbers(fd, 'FacesList', blade)
    ft = gmsh.model.mesh.field.add('Threshold'); gmsh.model.mesh.field.setNumber(ft, 'InField', fd)
    for k, v in (('SizeMin', h['blade']), ('SizeMax', h['hub']), ('DistMin', 3.0), ('DistMax', 30.0)):
        gmsh.model.mesh.field.setNumber(ft, k, v)
    gmsh.model.mesh.field.setAsBackgroundMesh(ft)
    gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 0); gmsh.option.setNumber('Mesh.MeshSizeFromPoints', 0)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 0)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.option.setNumber('Mesh.OptimizeNetgen', 1)
    gmsh.model.mesh.generate(3)
    def surf_nodes(tags):
        out = set()
        for t in tags:
            nt, _, _ = gmsh.model.mesh.getNodes(2, t, includeBoundary=True); out.update(int(v) for v in nt)
        return sorted(out)
    nl, nr = surf_nodes(left), surf_nodes(right)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(11)
    gmsh.finalize()
    nodes = {int(t): xyz[i] for i, t in enumerate(nt)}
    els = []
    for e in en.reshape(-1, 10).astype(int):
        cn = list(e[:4]); mids = list(e[4:])
        def mid(p, q):
            m = 0.5 * (nodes[p] + nodes[q]); return min(mids, key=lambda k: np.linalg.norm(nodes[k] - m))
        els.append(cn + [mid(cn[0], cn[1]), mid(cn[1], cn[2]), mid(cn[2], cn[0]), mid(cn[0], cn[3]), mid(cn[1], cn[3]), mid(cn[2], cn[3])])
    return nodes, els, nl, nr


def temperature(g, p, case):
    Tb, Tt, Tle, Tex = TEMP[g.key][case]; imp = g.imp
    x, r = p[0], math.hypot(p[1], p[2])
    if g.is_blade(p):
        return Tle + (Tex - Tle) * min(max((r - imp.r1h) / (imp.r2 - imp.r1h), 0.0), 1.0)
    s = min(max((r - imp.p['r_bore']) / (imp.r2 - imp.p['r_bore']), 0.0), 1.0)
    return Tb + (Tt - Tb) * s * s


def write_deck(g, nodes, els, nl, nr, job, N, case, thermal=True, freq=None, T_override=None, nlgeom=False, f_lo=None):
    key = g.key; m = MAT[key]; imp = g.imp; om = N * 2 * math.pi / 60.0
    dep = set(nr)
    xb = imp.x0 + imp.L; (ri, ro) = CURVIC[key][1]
    rear = [k for k, p in nodes.items() if abs(p[0] - xb) < 1e-3 and ri - 1e-3 <= math.hypot(p[1], p[2]) <= ro + 1e-3 and k not in dep]
    cut = dep | set(nl)                                            # (an equation on a cyclic-MPC node would chain MPCs)
    Tn = {k: (T_override if T_override is not None else temperature(g, p, case)) for k, p in nodes.items()}
    with open(os.path.join(FEA, job + '.inp'), 'w') as f:
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f, %.6f\n' % (k, *v) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=C3D10, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        f.write('*NSET, NSET=NLEFT\n' + ''.join('%d,\n' % k for k in nl) + '*NSET, NSET=NRIGHT\n' + ''.join('%d,\n' % k for k in nr))
        f.write('*NSET, NSET=NREAR\n' + ''.join('%d,\n' % k for k in rear))
        sl = set(nl); facets = []
        for i, e in enumerate(els, 1):
            for sn, (a_, b_, c_) in (('S1', (0, 1, 2)), ('S2', (0, 3, 1)), ('S3', (1, 3, 2)), ('S4', (2, 3, 0))):
                if e[a_] in sl and e[b_] in sl and e[c_] in sl: facets.append('%d, %s\n' % (i, sn))
        f.write('*SURFACE, NAME=SLEFT, TYPE=ELEMENT\n' + ''.join(facets) + '*SURFACE, NAME=SRIGHT, TYPE=NODE\nNRIGHT\n')
        f.write('*TIE, NAME=CYC, CYCLIC SYMMETRY, ADJUST=NO\nSRIGHT, SLEFT\n')
        f.write('*CYCLIC SYMMETRY MODEL, N=%d, NGRAPH=1, TIE=CYC\n0., 0., 0., 1., 0., 0.\n' % g.meta['Z'])
        f.write('*MATERIAL, NAME=%s\n*ELASTIC\n' % m['name'] + ''.join('%.1f, %.3f, %.1f\n' % (e, m['nu'], t) for e, t in zip(m['E'], m['T'])))
        f.write('*EXPANSION, ZERO=20.\n' + ''.join('%.4e, %.1f\n' % (a, t) for a, t in zip(m['alpha'], m['T'])))
        f.write('*DENSITY\n%.3e\n*SOLID SECTION, ELSET=EALL, MATERIAL=%s\n' % (m['rho'], m['name']))
        # rear curvic: axial fixed, tangential fixed (u_theta = -sin th u_y + cos th u_z = 0), radial free
        f.write('*BOUNDARY\nNREAR, 1, 1, 0.\n*EQUATION\n')
        for k in rear:
            if k in cut: continue
            p = nodes[k]; th = math.atan2(p[2], p[1])
            if abs(math.cos(th)) > abs(math.sin(th)): f.write('2\n%d, 3, %.8f, %d, 2, %.8f\n' % (k, math.cos(th), k, -math.sin(th)))
            else: f.write('2\n%d, 2, %.8f, %d, 3, %.8f\n' % (k, -math.sin(th), k, math.cos(th)))
        if thermal:
            f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 20.\n')
        else:
            f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, Tn[k]) for k in nodes))
        # stresses: linear static (SPOOLES, the only direct solver in this ccx build; ~5 min on the stress mesh, the
        # iterative solver was slower); modes: NLGEOM static (stress stiffening) + perturbation frequency, modal mesh
        f.write('*STEP, NLGEOM\n*STATIC\n' if nlgeom else '*STEP\n*STATIC\n')
        if om > 0: f.write('*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 1., 0., 0.\n' % om ** 2)
        if thermal: f.write('*TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, Tn[k]) for k in nodes))
        f.write('*END STEP\n' if freq else '*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n')   # (outputs would carry into
        if freq:                                                                          # the modes: GB of mode stresses)
            f.write('*STEP, PERTURBATION\n*FREQUENCY\n%d%s\n*SELECT CYCLIC SYMMETRY MODES, NMIN=%d, NMAX=%d\n*END STEP\n'
                    % (2 * freq, ', %.1f' % f_lo if f_lo else '', NDS[0], NDS[1]))
    return Tn


# ------------------------------------------------------------------------------------------------ static post-processing
def tet_volume(P):
    return abs(np.dot(P[1] - P[0], np.cross(P[2] - P[0], P[3] - P[0]))) / 6.0


def static_post(g, nodes, els, Tn, job, N, case):
    key = g.key; imp = g.imp
    nfrd, blocks = F.read_frd(os.path.join(FEA, job + '.frd'))
    S = [b for b in blocks if b['name'].startswith('STRESS')][-1]['data']
    U = [b for b in blocks if b['name'].startswith('DISP')][-1]['data']
    vm = {k: float(F.vm(np.array(v[:6]))) for k, v in S.items()}
    def hoop(k):
        p = nodes[k]; th = math.atan2(p[2], p[1]); e = np.array([0.0, -math.sin(th), math.cos(th)]); s = S[k]
        T = np.array([[s[0], s[3], s[5]], [s[3], s[1], s[4]], [s[5], s[4], s[2]]]); return float(e @ T @ e)
    # element classes and volumes (hub body / blades), mean hoop over the hub meridional section (weights V / r)
    hub_w = hub_h = 0.0; vol = []
    for e in els:
        P = np.array([nodes[n] for n in e[:4]]); c = P.mean(0); V = tet_volume(P); r = math.hypot(c[1], c[2])
        isb = g.is_blade(c); vol.append((V, isb, e))
        if not isb:
            hm = np.mean([hoop(n) for n in e[:4]]); hub_w += V / r; hub_h += hm * V / r
    sh_mean = hub_h / hub_w
    # peak von Mises (exclude nodes on the dependent cut face: interpolated MPC nodes can show spikes)
    cand = {k: v for k, v in vm.items() if k in nodes}
    kmax = max(cand, key=cand.get); pmax = nodes[kmax]
    # 99.5th percentile (volume weighted) of the element-mean von Mises: the bulk stress (peak relaxes locally)
    em = sorted(((np.mean([vm[n] for n in e[:4]]), V) for V, _, e in vol), key=lambda t: t[0])
    cv = np.cumsum([v for _, v in em]); p995 = em[int(np.searchsorted(cv, 0.995 * cv[-1]))][0]
    # bore: hoop stress at the bore (r = r_bore) nodes, max
    rb = imp.p['r_bore']; bore = [k for k, p in nodes.items() if abs(math.hypot(p[1], p[2]) - rb) < 0.05]
    s_bore = max(hoop(k) for k in bore) if bore else float('nan')
    # blade: peak von Mises on blade nodes; exit-tip growth (radial and axial at the shroud TE corner)
    bl = [k for k, p in nodes.items() if g.is_blade(p)]
    kb = max(bl, key=lambda k: vm[k])
    tip = min(bl, key=lambda k: abs(math.hypot(nodes[k][1], nodes[k][2]) - imp.r2) + abs(nodes[k][0] - imp.xs2))
    pt = nodes[tip]; th = math.atan2(pt[2], pt[1]); ut = U[tip]
    u_rad = float(ut[1] * math.cos(th) + ut[2] * math.sin(th)); u_ax = float(ut[0])
    ind = min(bl, key=lambda k: abs(nodes[k][0] - imp.xle) + abs(math.hypot(nodes[k][1], nodes[k][2]) - imp.r1t))
    pi_ = nodes[ind]; thi = math.atan2(pi_[2], pi_[1]); ui = U[ind]; u_ind = float(ui[1] * math.cos(thi) + ui[2] * math.sin(thi))
    T_mean = float(np.mean([Tn[k] for k in nodes])); T_max = Tn[kmax]
    out = dict(case=case, N=N, vm_max=vm[kmax], vm_max_at=dict(x=float(pmax[0]), r=float(math.hypot(pmax[1], pmax[2])),
               blade=g.is_blade(pmax), T=T_max), vm_p995=p995, vm_blade_max=vm[kb],
               vm_blade_at=dict(x=float(nodes[kb][0]), r=float(math.hypot(nodes[kb][1], nodes[kb][2])), T=Tn[kb]),
               hoop_mean=sh_mean, hoop_bore=s_bore, T_mean=T_mean, u_tip_radial=u_rad, u_tip_axial=u_ax, u_inducer_radial=u_ind)
    ys = prop(key, 'YS', T_max); uts_m = prop(key, 'UTS', T_mean)
    out.update(ys_at_max=ys, margin_yield=ys / vm[kmax], burst_rpm=N * math.sqrt(0.85 * uts_m / sh_mean) if N > 0 else None)
    if N > 0: out['burst_ratio_op'] = out['burst_rpm'] / N_OP
    # node data for plots
    out['_plot'] = dict(x=[float(nodes[k][0]) for k in vm], r=[float(math.hypot(nodes[k][1], nodes[k][2])) for k in vm],
                        vm=[vm[k] for k in vm], T=[Tn[k] for k in vm])
    if MAT[key]['name'] == 'AL2618':                           # creep: rupture life (minimum curve) at the peak and the bulk
        crit = min(vm, key=lambda k: al_rupture_hours(vm[k], Tn[k]))
        out['creep_peak_h'] = al_rupture_hours(vm[crit], Tn[crit]); out['creep_peak_at'] = dict(vm=vm[crit], T=Tn[crit])
        out['creep_bulk_h'] = al_rupture_hours(p995, max(Tn.values()))
        out['creep_hoop_h'] = al_rupture_hours(sh_mean, T_mean)
    return out


def run_static(g, mesh_data, case_list):
    nodes, els, nl, nr = mesh_data; res = {}
    def one(c):
        tag, N, case, thermal, T0 = c; job = 'a1000_imp_%s_%s' % (g.key, tag)
        Tn = write_deck(g, nodes, els, nl, nr, job, N, case, thermal=thermal, T_override=T0)
        F.run_ccx(job, threads=THREADS)
        r = static_post(g, nodes, els, Tn, job, N, case); r['thermal'] = thermal; return tag, r
    with ThreadPoolExecutor(PAR) as ex:
        for tag, r in ex.map(one, case_list): res[tag] = r
    return res


def run_modal(g, mesh_data):
    nodes, els, nl, nr = mesh_data; table = {}
    def one(N):
        job = 'a1000_imp_%s_modal_%dk' % (g.key, round(N / 1e3)) if N > 0 else 'a1000_imp_%s_modal_0' % g.key
        write_deck(g, nodes, els, nl, nr, job, N, 'design', thermal=False, freq=FAM[g.key], nlgeom=True)
        F.run_ccx(job, threads=THREADS)
        return N, CY.parse_dat(os.path.join(FEA, job + '.dat'))
    with ThreadPoolExecutor(PAR) as ex:
        for N, t in ex.map(one, SPEEDS): table[N] = t
    return table


def run_modal_high(g, mesh_data, N=N_OP):
    """families above F_HIGH[key] at 15,000 rpm (shift of the eigen solver): the weak 2 x vane orders lie above the first
    FAM families; speed effect over the +-2 % band neglected (stress stiffening there ~0.1 %)"""
    nodes, els, nl, nr = mesh_data; job = 'a1000_imp_%s_modal_hi' % g.key
    lo, nf = F_HIGH[g.key]
    write_deck(g, nodes, els, nl, nr, job, N, 'design', thermal=False, freq=nf, nlgeom=True, f_lo=lo)
    F.run_ccx(job, threads=THREADS)
    return {nd: [f for f in v if f >= 0.98 * lo] for nd, v in CY.parse_dat(os.path.join(FEA, job + '.dat')).items()}


# ------------------------------------------------------------------------------------------------ vibration checks
def nd_of(k, Z=13):
    m = k % Z; return min(m, Z - m)


def orders(key):
    """(strong, weak) engine orders on the impeller"""
    zd = IMP.ST[key]['Zd']
    if key == 'C1':
        return [zd], [1, 2, 3, 4, 2 * zd]
    zr, zd1 = IMP.ST['C1']['Zr'], IMP.ST['C1']['Zd']
    strong = [zd, zr]
    return strong, [k for k in dict.fromkeys([1, 2, 3, 4, 2 * zd, 2 * zr, zd1]) if k not in strong]


def southwell(table, nd, fam):
    """f(N) of a family from the solved speeds: least-squares f^2 = f0^2 + S N^2 (Southwell); None if not solved at all"""
    sp = sorted(table); fs = [table[s][nd][fam] for s in sp if len(table[s].get(nd, [])) > fam]
    if len(fs) < len(sp): return None
    c = np.polyfit(np.array(sp) ** 2, np.array(fs) ** 2, 1)
    return lambda N: math.sqrt(max(np.polyval(c, N * N), 1.0))


HIGH = {}                                                       # key -> {nd: [Hz]} of the high-band run at 15k


def band_margin(table, k, N_ref=N_OP, key=None, fams=None):
    """smallest |f - k N / 60| / (k N / 60) over the grid band, against all families of ND(k) (Southwell in speed) and
    the high-band families at 15k (constant over the band); returns (margin, family, f)"""
    nd = nd_of(k); best = (9.0, None, None)
    for j, f in enumerate([] if fams else HIGH.get(key, {}).get(nd, [])):
        for N in np.linspace(BAND[0] * N_ref, BAND[1] * N_ref, 9):
            fk = k * N / 60; m = (f - fk) / fk
            if abs(m) < abs(best[0]): best = (m, 'hi%d' % (j + 1), f)
    nf = max(len(table[s].get(nd, [])) for s in table)
    for fam in range(min(nf, fams or nf)):
        fn = southwell(table, nd, fam)
        if fn is None: continue
        for N in np.linspace(BAND[0] * N_ref, BAND[1] * N_ref, 9):
            f = fn(N); fk = k * N / 60; m = (f - fk) / fk
            if abs(m) < abs(best[0]): best = (m, fam + 1, f)
    return best


def covered(table, k, key=None):
    nd = nd_of(k); f15 = list(table[N_OP].get(nd, [])) + list(HIGH.get(key, {}).get(nd, []))
    return bool(f15) and max(f15) > 1.12 * k * N_OP / 60


def vane_scan(tables):
    """1 x and 2 x margins of diffuser counts 11..31 on each impeller; return-channel counts on impeller 2"""
    out = {}
    for key, tab in tables.items():
        rows = []
        for z in range(11, 32):
            m1 = band_margin(tab, z, key=key); m2 = band_margin(tab, 2 * z, key=key)
            rows.append(dict(Z=z, m1=m1[0], f1=m1[2], fam1=m1[1], m2=m2[0], f2=m2[2], fam2=m2[1], cov2=covered(tab, 2 * z, key),
                             nd1=nd_of(z), nd2=nd_of(2 * z)))
        out[key] = rows
    return out


# ------------------------------------------------------------------------------------------------ main
def summary(g, st, table):
    key = g.key; al = MAT[key]['name'] == 'AL2618'
    out = dict(key=key, material=MAT[key]['name'], lmp=LMP if al else None, static={}, checks=[])
    for tag, r in st.items():
        out['static'][tag] = {k: v for k, v in r.items() if k != '_plot'}
    op, trip, spin, mech, hot = st['op'], st['trip'], st['spin'], st['op_mech'], st['hot']
    chk = out['checks']
    def add(name, val, lim, unit, ok, note=''):
        chk.append(dict(test=name, value=val, limit=lim, unit=unit, ok=bool(ok), note=note))
    add('peak von Mises / yield at 15k (local)', op['margin_yield'], 1.0, '-', op['margin_yield'] >= 1.0,
        '%.0f MPa at x %.0f r %.0f (%s), %.0f C' % (op['vm_max'], op['vm_max_at']['x'], op['vm_max_at']['r'],
                                                 'blade' if op['vm_max_at']['blade'] else 'hub', op['vm_max_at']['T']))
    add('peak von Mises / yield at trip (local)', trip['margin_yield'], 1.0, '-', trip['margin_yield'] >= 1.0, '%.0f MPa' % trip['vm_max'])
    add('burst / trip (area-mean hoop, 85 % UTS)', trip['burst_rpm'] / N_TRIP, 1.22, 'x', trip['burst_rpm'] / N_TRIP >= 1.22,
        'burst %.0f rpm, mean hoop %.0f MPa at trip' % (trip['burst_rpm'], trip['hoop_mean']))
    ys20 = prop(key, 'YS', 20.0)
    add('spin test 115 % MCS: bulk (99.5 %) vm / yield (20 C)', ys20 / spin['vm_p995'], 1.0, '-', ys20 / spin['vm_p995'] >= 1.0,
        '%.0f rpm, bulk %.0f MPa, mean hoop %.0f MPa, local peak %.0f MPa' % (N_SPIN, spin['vm_p995'], spin['hoop_mean'], spin['vm_max']))
    # LCF: start-stop 0 -> 15k (total stress incl. thermal), peak node, elastic strain range (Neuber if above yield)
    s = op['vm_max']; T = op['vm_max_at']['T']; E = prop(key, 'E', T); ys = prop(key, 'YS', T)
    de = s / E if s <= ys else (ys + math.sqrt(max(s * s - ys * ys, 0.0))) / E   # Neuber-like, conservative
    n = manson_cycles(key, de, T, min(s, ys))
    add('LCF start-stop cycles (peak, Manson-Morrow 2/20)', n, STARTS_REQ, 'cyc', n >= STARTS_REQ,
        'vm %.0f MPa, strain range %.3f %%' % (s, 100 * de))
    out['lcf'] = dict(vm=s, T=T, d_eps=de, cycles=n)
    if al:
        add('creep rupture, bulk 99.5 % vm, design (min curve)', mech['creep_bulk_h'], LIFE_REQ, 'h', mech['creep_bulk_h'] >= LIFE_REQ,
            '%.0f MPa at %.0f C' % (mech['vm_p995'], TEMP[key]['design'][1]))
        add('creep rupture, local peak, design (min curve)', mech['creep_peak_h'], LIFE_REQ, 'h', mech['creep_peak_h'] >= LIFE_REQ,
            '%.0f MPa at %.0f C (relaxes; information)' % (mech['creep_peak_at']['vm'], mech['creep_peak_at']['T']))
        add('creep rupture, bulk 99.5 % vm, hot day no chilling (min)', hot['creep_bulk_h'], LIFE_REQ, 'h', hot['creep_bulk_h'] >= LIFE_REQ,
            '%.0f MPa at %.0f C' % (hot['vm_p995'], TEMP[key]['hot'][1]))
        add('creep rupture, mean hoop, hot day (min curve)', hot['creep_hoop_h'], LIFE_REQ, 'h', hot['creep_hoop_h'] >= LIFE_REQ,
            '%.0f MPa at %.0f C (mean)' % (hot['hoop_mean'], hot['T_mean']))
    else:
        r_ = hot['vm_max'] / prop(key, 'YS', hot['vm_max_at']['T'])
        add('Ti-6Al-4V sustained peak / yield, hot day (dwell <= 0.8)', r_, 0.8, '-', r_ <= 0.8, 'creep negligible below ~300 C')
    strong, weak = orders(key); out['orders'] = dict(strong=strong, weak=weak)
    des = json.load(open(IMP.JSON))['stages']; sd = des[key]; dfu = sd['performance']['diffuser']; gm = sd['geometry']
    gam_ = 1.39
    q3 = 0.5 * gam_ * dfu['P3'] * dfu['M3'] ** 2                       # dynamic head at the diffuser vane LE [Pa]
    ind = sd['inducer']; p1 = sd['performance']['P01']; T1 = sd['performance']['T01']
    q1 = 0.5 * p1 / (287.0 * T1) * (ind['c1'] ** 2 + (OM_N * gm['r1t'] * 1e-3) ** 2)   # inducer-tip relative head
    r32 = dfu['r3'] / gm['r2'] - 1.0
    rho = MAT[key]['rho'] * 1e12; t_te = 0.5 * (gm['thickness_hub'][2] + gm['thickness_shroud'][2]) * 1e-3
    q_cf = rho * t_te * OM_N ** 2 * gm['r2'] * 1e-3 * math.sin(math.radians(40.0))
    s_te = mech['vm_blade_max']; T_te = mech['vm_blade_at']['T']
    s_goodman = SIG_E[sd['material']] * (1 - s_te / prop(key, 'UTS', T_te))
    out['forced'] = dict(q3=q3, q1=q1, q_cf=q_cf, sigma_TE=s_te, goodman=s_goodman, zeta=ZETA, mistune=MISTUNE)
    zd1, zr = IMP.ST['C1']['Zd'], IMP.ST['C1']['Zr']
    def dp_of(k):
        """unsteady pressure amplitude of order k on this impeller and its source"""
        zd = IMP.ST[key]['Zd']
        if k == zd: return A_POT * q3 * math.exp(-zd * r32), 'diffuser potential'
        if k == 2 * zd: return 0.5 * A_POT * q3 * math.exp(-2 * zd * r32), 'diffuser potential, 2nd harmonic'
        if key == 'C2' and k == zr: return A_WAKE * q1, 'return-channel vane wakes'
        if key == 'C2' and k == 2 * zr: return 0.5 * A_WAKE * q1, 'return-channel wakes, 2nd harmonic'
        if key == 'C2' and k == zd1: return 0.2 * A_WAKE * q1, 'diffuser-1 wakes through the return channel'
        return 0.02 * q1, 'inlet distortion'
    for k in strong + weak:
        weak_k = k not in strong; lab = 'strong' if not weak_k else ('inlet' if k <= 4 else 'weak')
        req = 0.10 if (not weak_k or k <= 4) else 0.05
        mf = band_margin(table, k, key=key, fams=N_FUND)
        add('EO%d (ND %d) margin to the fundamental families, %s' % (k, nd_of(k), lab), 100 * abs(mf[0]), 100 * req, '%',
            abs(mf[0]) >= req and mf[1] is not None, 'family %s %.0f Hz' % (mf[1], mf[2] or 0) if mf[1] else 'ND NOT COMPUTED')
        if k > 4:
            ma = band_margin(table, k, key=key); dp, src = dp_of(k)
            sv = s_te * dp / q_cf / (2 * ZETA) * MISTUNE
            add('EO%d resonant stress bound (%s)' % (k, src), sv, s_goodman / 2, 'MPa', sv <= s_goodman / 2 and ma[1] is not None,
                'nearest family %s %.0f Hz (%+.1f %%), dp %.0f Pa' % (ma[1], ma[2] or 0, 100 * ma[0], dp))
    out['freqs'] = {str(int(N)): {str(nd): v for nd, v in t.items()} for N, t in table.items()}
    return out


def plot(g, st, table, summ):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    key = g.key; imp = g.imp
    fig = plt.figure(figsize=(17, 10), dpi=100)
    ax = fig.add_axes([0.04, 0.53, 0.30, 0.40]); p = st['op']['_plot']
    sc = ax.scatter(p['x'], p['r'], c=p['vm'], s=1.5, cmap='turbo', vmin=0, vmax=max(p['vm']))
    fig.colorbar(sc, ax=ax, label='von Mises [MPa]'); ax.set_aspect('equal'); ax.grid(alpha=0.3)
    ax.set_title('%s at 15,000 rpm: von Mises (all nodes, meridional projection)' % key, fontsize=9)
    ax = fig.add_axes([0.38, 0.53, 0.28, 0.40])
    t15 = table[N_OP]; strong, weak = summ['orders']['strong'], summ['orders']['weak']
    for fam in range(FAM[key]):
        pts = [(nd, t15[nd][fam]) for nd in sorted(t15) if len(t15[nd]) > fam]
        if pts: ax.plot(*zip(*pts), 'o-', ms=4, lw=0.6, color='C%d' % (fam % 10))
    top = max(max(v) for v in t15.values()) * 1.05
    for k in strong + weak:
        fk = k * N_OP / 60
        if fk > top: continue
        ax.plot([nd_of(k)], [fk], 'kx' if k in strong else 'bx', ms=10, mew=2); ax.annotate(' EO%d' % k, (nd_of(k), fk), fontsize=8)
        ax.fill_between([nd_of(k) - 0.3, nd_of(k) + 0.3], fk * (0.9 if k in strong else 0.95), fk * (1.1 if k in strong else 1.05),
                        color='k' if k in strong else 'b', alpha=0.12)
    ax.set_xlabel('nodal diameter'); ax.set_ylabel('frequency at 15,000 rpm [Hz]'); ax.set_ylim(0, top); ax.grid(alpha=0.3)
    ax.set_title('ZZENF (cyclic, hub + blade + splitter): x strong (+-10 %%), blue weak (+-5 %%)', fontsize=9)
    ax = fig.add_axes([0.71, 0.53, 0.27, 0.40]); sp = sorted(table)
    Ns = np.linspace(0, 17500, 36)
    for nd in sorted({nd_of(k) for k in strong + weak}):
        for fam in range(FAM[key]):
            fn = southwell(table, nd, fam)
            if fn: ax.plot(Ns / 1e3, [fn(N) for N in Ns], '-', lw=0.8, color='C%d' % (nd % 10))
    for k in strong + weak:
        ax.plot(np.array([0, 17.5]), np.array([0, 17500]) * k / 60, 'k-' if k in strong else 'b--', lw=0.7)
        if k * 16500 / 60 < top: ax.text(16.6, k * 16500 / 60, 'EO%d' % k, fontsize=7)
    ax.axvspan(BAND[0] * 15, BAND[1] * 15, color='tab:green', alpha=0.2); ax.axvline(16.5, color='r', lw=0.8)
    ax.set_xlim(0, 17.5); ax.set_ylim(0, top); ax.set_xlabel('speed [k rpm]'); ax.set_ylabel('Hz'); ax.grid(alpha=0.3)
    ax.set_title('Campbell (Southwell fit through 0 / 15k / 16.5k): families of the excited NDs (colour = ND)', fontsize=9)
    ax = fig.add_axes([0.04, 0.05, 0.92, 0.40]); ax.axis('off')
    rows = [[c['test'], ('%.3g' % c['value']), ('%.3g' % c['limit']), c['unit'], 'OK' if c['ok'] else 'FAIL', c['note']] for c in summ['checks']]
    tb = ax.table(cellText=rows, colLabels=['check', 'value', 'limit', 'unit', 'result', 'note'], loc='upper center',
                  colWidths=[0.30, 0.07, 0.07, 0.04, 0.05, 0.42])
    tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1, 1.25)
    for i, c in enumerate(summ['checks'], 1):
        tb[i, 4].set_facecolor('#c8e6c9' if c['ok'] else '#ffcdd2')
    fig.suptitle('AURORA-1000 %s (%s, D2 %.0f mm, 13 + 13 blades): CalculiX cyclic sector' % (imp.p['name'], imp.p['mat'], 2 * imp.r2), fontsize=12)
    png = os.path.join(ROOT, 'docs', 'img', 'a1000_impeller_%s_fea.png' % key); fig.savefig(png); print('written', png)


def plot_vanes(scan):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(14, 5), dpi=100)
    for ax, (key, rows) in zip(axs, scan.items()):
        z = [r['Z'] for r in rows]
        ax.bar(np.array(z) - 0.2, [100 * abs(r['m1']) for r in rows], 0.4, label='1 x Z (strong, need 10 %)')
        ax.bar(np.array(z) + 0.2, [100 * abs(r['m2']) for r in rows], 0.4, label='2 x Z (weak, need 5 %)')
        ax.axhline(10, color='C0', lw=0.8); ax.axhline(5, color='C1', lw=0.8); ax.set_ylim(0, 40)
        ax.axvline(IMP.ST[key]['Zd'], color='k', ls='--', lw=1)
        ax.set_xlabel('vane count'); ax.set_ylabel('band margin to the nearest mode [%]'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
        ax.set_title('%s: diffuser vane count vs impeller modes (dashed = chosen)' % key, fontsize=9)
    fig.tight_layout(); png = os.path.join(ROOT, 'docs', 'img', 'a1000_impeller_vanes.png'); fig.savefig(png); print('written', png)


def main():
    keys = [a for a in sys.argv[1:] if a in IMP.ST] or list(IMP.ST)
    do_static = '--static' in sys.argv or not any(a in sys.argv for a in ('--modal', '--post', '--high'))
    do_modal = '--modal' in sys.argv or not any(a in sys.argv for a in ('--static', '--post', '--high'))
    do_high = '--high' in sys.argv
    for key in keys:
        g = Geo(key); path = os.path.join(FEA, 'a1000_impeller_%s.json' % key)
        old = json.load(open(path)) if os.path.exists(path) else {}
        st, table, minfo = None, None, dict(old.get('mesh', {}))
        if do_static:
            md = mesh(g, H[key]); minfo['stress'] = dict(nodes=len(md[0]), elements=len(md[1]), h=H[key])
            print('%s stress mesh: %d nodes, %d C3D10, cut faces %d / %d nodes' % (key, len(md[0]), len(md[1]), len(md[2]),
                                                                                  len(md[3])), flush=True)
            st = run_static(g, md, [('op', N_OP, 'design', True, None), ('op_mech', N_OP, 'design', False, None),
                                    ('hot', N_OP, 'hot', False, None), ('trip', N_TRIP, 'design', True, None),
                                    ('spin', N_SPIN, 'design', False, 20.0)])
            json.dump(st, open(path[:-5] + '_static_raw.json', 'w'), default=float)
        elif os.path.exists(path[:-5] + '_static_raw.json'):
            st = json.load(open(path[:-5] + '_static_raw.json'))
        if do_modal:
            mm = mesh(g, H_MODAL[key]); minfo['modal'] = dict(nodes=len(mm[0]), elements=len(mm[1]), h=H_MODAL[key])
            print('%s modal mesh: %d nodes, %d C3D10' % (key, len(mm[0]), len(mm[1])), flush=True)
            table = run_modal(g, mm)
            if NDS != (0, 6) and os.path.exists(path[:-5] + '_modes_raw.json'):   # partial ND run: merge with the saved set
                old_t = {float(N): {int(nd): v for nd, v in t.items()} for N, t in json.load(open(path[:-5] + '_modes_raw.json')).items()}
                table = {N: {**old_t.get(N, {}), **t} for N, t in table.items()}
            json.dump({str(int(N)): {str(nd): v for nd, v in t.items()} for N, t in table.items()},
                      open(path[:-5] + '_modes_raw.json', 'w'))
        elif os.path.exists(path[:-5] + '_modes_raw.json'):
            table = {float(N): {int(nd): v for nd, v in t.items()} for N, t in json.load(open(path[:-5] + '_modes_raw.json')).items()}
        if do_high:
            mh = mesh(g, H_MODAL[key]); HIGH[key] = run_modal_high(g, mh)
            json.dump({str(nd): v for nd, v in HIGH[key].items()}, open(path[:-5] + '_modes_high.json', 'w'))
        elif os.path.exists(path[:-5] + '_modes_high.json'):
            HIGH[key] = {int(nd): v for nd, v in json.load(open(path[:-5] + '_modes_high.json')).items()}
        if table is None or not os.path.exists(path[:-5] + '_static_raw.json'):
            print('%s: static or modal results missing, no summary yet' % key); continue
        summ = summary(g, st, table)
        summ['mesh'] = minfo
        json.dump(summ, open(path, 'w'), indent=1, default=float)
        print('\n%s checks:' % key)
        for c in summ['checks']:
            print('  %-58s %10.4g  limit %8.4g %-4s %s  %s' % (c['test'], c['value'], c['limit'], c['unit'], 'OK  ' if c['ok'] else 'FAIL', c['note']))
        for N in sorted(table):
            print('  %5.0f rpm: ' % N + '  '.join('ND%d %s' % (nd, '/'.join('%.0f' % f for f in table[N][nd][:6])) for nd in sorted(table[N])))
        plot(g, st, table, summ)
    tabs = {}
    for key in IMP.ST:
        p = os.path.join(FEA, 'a1000_impeller_%s_modes_raw.json' % key)
        if os.path.exists(p):
            tabs[key] = {float(N): {int(nd): v for nd, v in t.items()} for N, t in json.load(open(p)).items()}
            ph = p.replace('_modes_raw', '_modes_high')
            if os.path.exists(ph): HIGH[key] = {int(nd): v for nd, v in json.load(open(ph)).items()}
    if tabs:
        scan = vane_scan(tabs); json.dump(scan, open(os.path.join(FEA, 'a1000_impeller_vane_scan.json'), 'w'), indent=1, default=float)
        for key, rows in scan.items():
            print('%s vane scan (1x / 2x band margin %%): ' % key + '  '.join('%d: %.0f/%.0f%s' % (r['Z'], 100 * abs(r['m1']), 100 * abs(r['m2']),
                  '' if r['cov2'] else '?') for r in rows))
        plot_vanes(scan)


if __name__ == '__main__':
    main()
