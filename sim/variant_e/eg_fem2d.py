# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "gmsh", "matplotlib"]
# ///
"""GR180 version E - generator: small 2D finite-element library for the PMG cross-section (used by sim/variant_e/eg_em.py).

* geometry + mesh: gmsh (OCC) - shaft disk, parallel-magnetised Sm2Co17 ring, CFRP sleeve, 3-layer air gap (middle layer =
  Arkkio torque band), slotted stator (parallel teeth, semi-closed slots, 2 winding layers per slot), A = 0 on the stator OD
* nonlinear magnetostatics, A_z formulation, linear (P1) triangles, Newton-Raphson on nu(B^2) from B-H tables
  (NO10 / NO20 laminations x stacking factor, 42CrMo4 shaft), linear magnets (mu_r 1.05) with a rotating Br vector:
  the rotor (shaft + full magnet ring + sleeve) is axisymmetric, so turning the rotor = turning the magnetisation vector
  -> no remeshing, no sliding band
* time-harmonic eddy-current solve (complex A_z, rotor frame) for the solid-shaft losses from the diode-bridge current
  harmonics
* post: flux linkage per winding path, Arkkio torque, element B (stator iron loss), rotor-frame B at material points of
  the magnet ring (segment eddy loss)
Units: SI inside (m, T, A); geometry dict in mm.
"""
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from scipy.interpolate import PchipInterpolator

MU0 = 4e-7 * math.pi

# ------------------------------------------------------------------ B-H curves (DC magnetisation, typical catalogue values)
BH = {
    # fully processed NO 3 % Si, 0.10 / 0.20 mm (Cogent / Surahammar NO10 / NO20, JFE 10JNEX900 / 20JNEH1200, Baosteel B10AV / B20AV)
    'NO20': ([0, 20, 40, 60, 80, 100, 150, 200, 300, 500, 1000, 2500, 5000, 10000, 20000, 50000, 100000],
             [0, 0.30, 0.65, 0.88, 1.00, 1.08, 1.20, 1.27, 1.35, 1.43, 1.52, 1.62, 1.69, 1.77, 1.86, 2.00, 2.12]),
    'NO10': ([0, 20, 40, 60, 80, 100, 150, 200, 300, 500, 1000, 2500, 5000, 10000, 20000, 50000, 100000],
             [0, 0.27, 0.60, 0.84, 0.97, 1.05, 1.17, 1.24, 1.32, 1.40, 1.49, 1.59, 1.66, 1.74, 1.83, 1.98, 2.10]),
    # 42CrMo4 (1.7225) quenched + tempered, DC curve (rotor body)
    '42CrMo4': ([0, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000],
                [0, 0.25, 0.75, 1.10, 1.35, 1.55, 1.68, 1.80, 1.95, 2.08]),
}


class Reluctivity:
    """nu(b2) and dnu/db2 from a B-H table (pchip of nu over b2; mu0 continuation above the table)"""

    def __init__(self, name, stack=1.0):
        H, B = np.array(BH[name][0], float), np.array(BH[name][1], float) * stack + (1 - stack) * MU0 * np.array(BH[name][0], float)
        self.Bl, self.Hl = B[-1], H[-1]
        nu = np.empty_like(B)
        nu[1:] = H[1:] / B[1:]
        nu[0] = H[1] / B[1] * 1.0
        b2 = B ** 2
        self.f = PchipInterpolator(b2, nu, extrapolate=True)
        self.df = self.f.derivative()
        self.b2max = b2[-1]
        self.stack = stack

    def __call__(self, b2):
        b2 = np.asarray(b2, float)
        nu = self.f(np.minimum(b2, self.b2max))
        dnu = self.df(np.minimum(b2, self.b2max))
        hi = b2 > self.b2max
        if np.any(hi):
            b = np.sqrt(b2[hi])
            H = self.Hl + (b - self.Bl) / MU0
            nu[hi] = H / b
            # d(H/b)/d(b2) = (dH/db * b - H) / b^2 / (2b)
            dnu[hi] = (b / MU0 - H) / b ** 2 / (2 * b)
        return nu, dnu

    def mu_inc(self, b):
        """incremental relative permeability dB/dH / mu0 at |B| = b"""
        b = np.asarray(b, float)
        db = 1e-3
        nu1, _ = self(np.maximum(b - db, 0.0) ** 2)
        nu2, _ = self((b + db) ** 2)
        H1 = nu1 * np.maximum(b - db, 0.0); H2 = nu2 * (b + db)
        return (2 * db) / np.maximum(H2 - H1, 1e-9) / MU0


# ------------------------------------------------------------------ geometry + mesh
def slot_outline(G):
    """local slot polygon pieces (slot centred on +x): returns dict of point lists (mm) for 'air' (opening + wedge),
    'top' and 'bot' winding layers.  G['slot_shape'] = 'open_rect' (parallel-sided open slot of width slot_w: form-wound
    rectangular litz, wedge zone wedge_h) or 'semi_closed' (parallel teeth of width tooth_w, opening slot_open)"""
    if G.get('slot_shape', 'semi_closed') == 'open_rect':
        Rb, bs, hw, hs = G['bore'] / 2, G['slot_w'], G['wedge_h'], G['slot_depth']
        yb = bs / 2
        xb = math.sqrt(Rb ** 2 - yb ** 2)
        r1, r2 = Rb + hw, Rb + hs
        x1, x2 = math.sqrt(r1 ** 2 - yb ** 2), math.sqrt(r2 ** 2 - yb ** 2)
        xm = 0.5 * (x1 + x2)
        air = [(xb, -yb), (x1, -yb), (x1, yb), (xb, yb)]
        top = [(x1, -yb), (xm, -yb), (xm, yb), (x1, yb)]
        bot = [(xm, -yb), (x2, -yb), (x2, yb), (xm, yb)]
        return dict(air=air, top=top, bot=bot, r_split=math.hypot(xm, yb), r1=r1, r2=r2, A_layer_mm2=(xm - x1) * bs,
                    A_winding_mm2=(x2 - x1) * bs, w_top=bs, w_bot=bs, arc_bore=(xb, yb),
                    tooth_w_bore=2 * math.pi * Rb / G['slots'] - bs, tooth_w_root=2 * math.pi * r2 / G['slots'] - bs)
    Q, Rb, wt = G['slots'], G['bore'] / 2, G['tooth_w']
    a = math.pi / Q
    h0, h1, hs = G['tip_h'], G['wedge_h'], G['slot_depth']
    b0 = G['slot_open']
    r_tip, r1, r2 = Rb + h0, Rb + h0 + h1, Rb + hs

    def side(r, s):          # point on the slot side line (parallel tooth) at radius r, s = +1 upper side
        t = math.sqrt(r * r - (wt / 2) ** 2)
        x = t * math.cos(a) + (wt / 2) * math.sin(a)
        y = t * math.sin(a) - (wt / 2) * math.cos(a)
        rr = math.hypot(x, y)            # rescale to exactly r
        return (x * r / rr, s * y * r / rr)

    yb = b0 / 2
    xb = math.sqrt(Rb ** 2 - yb ** 2)
    air = [(xb, -yb), (math.sqrt(r_tip ** 2 - yb ** 2), -yb), side(r1, -1), side(r1, 1), (math.sqrt(r_tip ** 2 - yb ** 2), yb), (xb, yb)]
    # equal-area split of the winding region
    def area(ra, rb_):
        return 0.5 * (ra + rb_) * 0  # placeholder (computed numerically below)

    def poly_area(p):
        return 0.5 * abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))))
    full = poly_area([side(r1, -1), side(r2, -1), side(r2, 1), side(r1, 1)])
    lo, hi = r1, r2
    for _ in range(60):
        rm = 0.5 * (lo + hi)
        if poly_area([side(r1, -1), side(rm, -1), side(rm, 1), side(r1, 1)]) < 0.5 * full:
            lo = rm
        else:
            hi = rm
    rm = 0.5 * (lo + hi)
    top = [side(r1, -1), side(rm, -1), side(rm, 1), side(r1, 1)]
    bot = [side(rm, -1), side(r2, -1), side(r2, 1), side(rm, 1)]
    return dict(air=air, top=top, bot=bot, r_split=rm, r1=r1, r2=r2, A_layer_mm2=poly_area(top), A_winding_mm2=full,
                w_top=2 * side(r1, 1)[1], w_bot=2 * side(r2, 1)[1], arc_bore=(xb, yb))


def build_mesh(G, h_gap=0.6, h_far=4.0, verbose=False):
    """returns dict: p (n,2) m, t (m,3), region (m,) str-coded int, region names, slot/layer ids per element"""
    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber('General.Terminal', 1 if verbose else 0)
    gmsh.model.add('pmg')
    occ = gmsh.model.occ
    rc, rm, rs = G['magnet_ID'] / 2, G['magnet_OD'] / 2, G['rotor_OD'] / 2
    Rb, Ro = G['bore'] / 2, G['stator_OD'] / 2
    g = Rb - rs
    rg1, rg2 = rs + g / 3, rs + 2 * g / 3
    rsh = rc - G.get('shield_t', 0.0)          # Cu-alloy eddy-current screen between the steel shaft and the magnets
    radii = ([rsh] if rsh < rc - 1e-6 else []) + [rc, rm, rs, rg1, rg2, Rb]
    disks = [occ.addDisk(0, 0, 0, r, r) for r in radii]
    stator = occ.addDisk(0, 0, 0, Ro, Ro)
    so = slot_outline(G)
    slot_surfs = []
    Q = G['slots']
    for k in range(Q):
        ang = 2 * math.pi * (k + 0.5) / Q
        ca, sa = math.cos(ang), math.sin(ang)
        rot = lambda p: (p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca)
        for name in ('air', 'top', 'bot'):
            pts = [rot(p) for p in so[name]]
            if name == 'air':        # make the opening edge an arc on the bore circle
                pt = [occ.addPoint(x, y, 0) for (x, y) in pts]
                c0 = occ.addPoint(0, 0, 0)
                lines = [occ.addLine(pt[i], pt[i + 1]) for i in range(len(pt) - 1)]
                arc = occ.addCircleArc(pt[-1], c0, pt[0])
                loop = occ.addCurveLoop(lines + [arc])
            else:
                pt = [occ.addPoint(x, y, 0) for (x, y) in pts]
                lines = [occ.addLine(pt[i], pt[(i + 1) % len(pt)]) for i in range(len(pt))]
                loop = occ.addCurveLoop(lines)
            slot_surfs.append(((k, name), occ.addPlaneSurface([loop])))
    occ.synchronize()
    tools = [(2, d) for d in disks] + [(2, s) for _, s in slot_surfs]
    out, omap = occ.fragment([(2, stator)], tools)
    occ.synchronize()
    # classify surfaces by centre of mass
    surfs = gmsh.model.getEntities(2)
    names = ['shaft', 'magnet', 'sleeve', 'gap1', 'gap2', 'gap3', 'iron'] + ['slot_air', 'slot_top', 'slot_bot', 'shield']
    cls = {}
    slot_of = {}
    ring_names = ([(rsh, 'shaft'), (rc, 'shield')] if rsh < rc - 1e-6 else [(rc, 'shaft')]) + [(rm, 'magnet'), (rs, 'sleeve'), (rg1, 'gap1'), (rg2, 'gap2'), (Rb, 'gap3'), (Ro, 'iron')]
    for (_, s) in surfs:
        cx, cy, _ = occ.getCenterOfMass(2, s)
        r = math.hypot(cx, cy)
        if r < 1e-3:              # axisymmetric piece (disk / annulus / slotted iron): classify by the outer radius
            bb = occ.getBoundingBox(2, s)
            ro_ = 0.5 * (bb[3] - bb[0])
            cls[s] = min(ring_names, key=lambda t: abs(t[0] - ro_))[1]
        else:                     # slot piece
            ang = math.atan2(cy, cx) % (2 * math.pi)
            k = int(round(ang / (2 * math.pi / Q) - 0.5)) % Q
            if r < so['r1'] - 0.1:
                cls[s] = 'slot_air'
            elif r < so['r_split']:
                cls[s] = 'slot_top'
            else:
                cls[s] = 'slot_bot'
            slot_of[s] = k
    # mesh size: distance from the gap curves
    gap_curves = []
    for (_, s) in surfs:
        if cls[s] in ('gap1', 'gap2', 'gap3'):
            gap_curves += [c[1] for c in gmsh.model.getBoundary([(2, s)], oriented=False)]
    f1 = gmsh.model.mesh.field.add('Distance')
    gmsh.model.mesh.field.setNumbers(f1, 'CurvesList', list(set(gap_curves)))
    gmsh.model.mesh.field.setNumber(f1, 'Sampling', 400)
    f2 = gmsh.model.mesh.field.add('Threshold')
    gmsh.model.mesh.field.setNumber(f2, 'InField', f1)
    gmsh.model.mesh.field.setNumber(f2, 'SizeMin', h_gap)
    gmsh.model.mesh.field.setNumber(f2, 'SizeMax', h_far)
    gmsh.model.mesh.field.setNumber(f2, 'DistMin', 0.5)
    gmsh.model.mesh.field.setNumber(f2, 'DistMax', 30.0)
    gmsh.model.mesh.field.setAsBackgroundMesh(f2)
    gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 0)
    gmsh.option.setNumber('Mesh.MeshSizeFromPoints', 0)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 0)
    gmsh.option.setNumber('Mesh.Algorithm', 6)
    gmsh.model.mesh.generate(2)
    tags, coords, _ = gmsh.model.mesh.getNodes()
    idx = {t: i for i, t in enumerate(tags)}
    P = coords.reshape(-1, 3)[:, :2] * 1e-3
    T, R, SL = [], [], []
    for (_, s) in surfs:
        et, etags, enodes = gmsh.model.mesh.getElements(2, s)
        for typ, en in zip(et, enodes):
            if typ != 2:
                continue
            tri = np.array([idx[n] for n in en]).reshape(-1, 3)
            T.append(tri)
            R += [names.index(cls[s])] * len(tri)
            SL += [slot_of.get(s, -1)] * len(tri)
    gmsh.finalize()
    T = np.vstack(T)
    # orient counter-clockwise
    x, y = P[T, 0], P[T, 1]
    ar = 0.5 * ((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
    neg = ar < 0
    T[neg] = T[neg][:, [0, 2, 1]]
    # drop unused nodes
    used = np.unique(T)
    remap = -np.ones(len(P), int); remap[used] = np.arange(len(used))
    P = P[used]; T = remap[T]
    return dict(p=P, t=T, region=np.array(R), names=names, slot=np.array(SL), so=so, G=G, radii=dict(rsh=rsh, rc=rc, rm=rm, rs=rs, rg1=rg1, rg2=rg2, Rb=Rb, Ro=Ro))


# ------------------------------------------------------------------ winding (2-pole, double layer, Q slots, coil pitch y)
def winding_table(Q, pitch_slots, paths=2):
    """return list per slot: (phase index 0..2 / sign) for top and bottom layer, and path id (0 / 1) - 60 deg phase belts,
    double layer, top layer of slot k and bottom layer of slot k + y belong to the same coil"""
    q = Q // 6
    top = []
    for k in range(Q):
        belt = k // q                     # 6 belts of q slots: A+, C-, B+, A-, C+, B- (2-pole)
        phase, sign = [(0, 1), (2, -1), (1, 1), (0, -1), (2, 1), (1, -1)][belt]
        top.append((phase, sign))
    bot = [None] * Q
    for k in range(Q):
        ph, s = top[k]
        bot[(k + pitch_slots) % Q] = (ph, -s)     # return conductor of the coil
    # path: coil k (top layer in slot k) belongs to path 0 for the + belt group, 1 for the - belt group
    path_top = [0 if top[k][1] > 0 else 1 for k in range(Q)]
    path_bot = [path_top[(k - pitch_slots) % Q] for k in range(Q)]
    return top, bot, path_top, path_bot


class PMGModel:
    def __init__(self, mesh, mat):
        """mat: dict(Br, mur, lam, stack, shaft='42CrMo4', L_stk m, turns_coil, paths, pitch)"""
        self.m = mesh; self.mat = mat
        P, T = mesh['p'], mesh['t']
        self.P, self.T = P, T
        x, y = P[T, 0], P[T, 1]
        self.b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], 1)
        self.c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], 1)
        self.area = 0.5 * (self.b[:, 0] * self.c[:, 1] - self.b[:, 1] * self.c[:, 0])
        self.cen = np.stack([x.mean(1), y.mean(1)], 1)
        nm = mesh['names']; R = mesh['region']
        self.reg = {n: np.where(R == i)[0] for i, n in enumerate(nm)}
        self.N = len(P)
        r = np.hypot(P[:, 0], P[:, 1])
        self.fixed = np.where(r > mesh['radii']['Ro'] * 1e-3 * (1 - 1e-6))[0]
        self.free = np.setdiff1d(np.arange(self.N), self.fixed)
        self.nu_iron = Reluctivity(mat['lam'], mat['stack'])
        self.nu_shaft = Reluctivity(mat.get('shaft', '42CrMo4'))
        self.nu_mag = 1.0 / (MU0 * mat['mur'])
        # sparse pattern
        I = np.repeat(T, 3, axis=1).ravel(); J = np.tile(T, (1, 3)).ravel()
        self.I, self.J = I, J
        # elementary geometric matrices M_e = (c c^T + b b^T) / (4 A^2) ; K_e = nu * A * M_e
        self.Me = (np.einsum('ei,ej->eij', self.c, self.c) + np.einsum('ei,ej->eij', self.b, self.b)) / (4 * self.area[:, None, None] ** 2)
        # winding
        Q = mesh['G']['slots']
        top, bot, ptop, pbot = winding_table(Q, mat['pitch'], mat['paths'])
        self.wt = (top, bot, ptop, pbot)
        slot = mesh['slot']
        self.layer_el = {}
        for k in range(Q):
            for lay, name in (('top', 'slot_top'), ('bot', 'slot_bot')):
                e = self.reg[name][slot[self.reg[name]] == k]
                self.layer_el[(k, lay)] = e
        self.A_layer = {kl: self.area[e].sum() for kl, e in self.layer_el.items()}
        self.nonlin = np.concatenate([self.reg['iron'], self.reg['shaft']])
        self.nu_lin = np.full(len(T), 1.0 / MU0)
        self.nu_lin[self.reg['magnet']] = self.nu_mag

    # -------------------------------------------------------------- sources
    def current_density(self, i_abc):
        """element J_z (A/m2) for phase currents i_abc (A, phase total; split equally over the parallel paths)"""
        Jz = np.zeros(len(self.T))
        top, bot, ptop, pbot = self.wt
        nc, a = self.mat['turns_coil'], self.mat['paths']
        Q = len(top)
        for k in range(Q):
            for lay, (ph, s) in (('top', top[k]), ('bot', bot[k])):
                e = self.layer_el[(k, lay)]
                Jz[e] = s * nc * (i_abc[ph] / a) / self.A_layer[(k, lay)]
        return Jz

    def rhs(self, theta, i_abc, Br=None):
        Br = self.mat['Br'] if Br is None else Br
        f = np.zeros(self.N)
        Jz = self.current_density(i_abc)
        fe = (Jz * self.area / 3.0)[:, None] * np.ones((1, 3))
        np.add.at(f, self.T, fe)
        e = self.reg['magnet']
        brx, bry = Br * math.cos(theta), Br * math.sin(theta)
        fm = self.nu_mag * (brx * self.c[e] - bry * self.b[e]) / 2.0
        np.add.at(f, self.T[e], fm)
        return f

    # -------------------------------------------------------------- nonlinear solve
    def B_of(self, A):
        Ae = A[self.T]
        Bx = (self.c * Ae).sum(1) / (2 * self.area)
        By = -(self.b * Ae).sum(1) / (2 * self.area)
        return Bx, By

    def solve(self, theta, i_abc, A0=None, Br=None, tol=1e-7, maxit=40, frozen_nu=None):
        f = self.rhs(theta, i_abc, Br)
        A = np.zeros(self.N) if A0 is None else A0.copy()
        it_iron, it_shaft = self.reg['iron'], self.reg['shaft']
        for it in range(maxit):
            Bx, By = self.B_of(A)
            b2 = Bx ** 2 + By ** 2
            nu = self.nu_lin.copy(); dnu = np.zeros(len(self.T))
            if frozen_nu is None:
                nu[it_iron], dnu[it_iron] = self.nu_iron(b2[it_iron])
                nu[it_shaft], dnu[it_shaft] = self.nu_shaft(b2[it_shaft])
            else:
                nu = frozen_nu
            MA = np.einsum('eij,ej->ei', self.Me, A[self.T])                 # M_e A_e
            Ke = (nu * self.area)[:, None, None] * self.Me
            r_e = (nu * self.area)[:, None] * MA
            Je = Ke + (2 * dnu * self.area)[:, None, None] * np.einsum('ei,ej->eij', MA, MA)
            res = np.zeros(self.N); np.add.at(res, self.T, r_e)
            res -= f
            Jm = sp.csr_matrix((Je.ravel(), (self.I, self.J)), shape=(self.N, self.N))
            fr = self.free
            rn = np.linalg.norm(res[fr]) / max(np.linalg.norm(f[fr]), 1e-12)
            if rn < tol:
                break
            dA = np.zeros(self.N)
            dA[fr] = spl.spsolve(Jm[fr][:, fr].tocsc(), -res[fr])
            A = A + dA
            if frozen_nu is not None:
                break
        self.last_nu = nu
        return A, dict(iters=it + 1, res=float(rn))

    # -------------------------------------------------------------- post
    def flux_linkage(self, A):
        """per phase, per path (Wb-turns), L_stk from mat"""
        Ae = A[self.T].mean(1) * self.area
        top, bot, ptop, pbot = self.wt
        nc, L = self.mat['turns_coil'], self.mat['L_stk']
        psi = np.zeros((3, self.mat['paths']))
        for k in range(len(top)):
            for lay, (ph, s), pth in (('top', top[k], ptop[k]), ('bot', bot[k], pbot[k])):
                e = self.layer_el[(k, lay)]
                psi[ph, pth] += s * nc * L * Ae[e].sum() / self.A_layer[(k, lay)]
        return psi

    def torque(self, A):
        e = self.reg['gap2']
        Bx, By = self.B_of(A)
        cx, cy = self.cen[e, 0], self.cen[e, 1]
        r = np.hypot(cx, cy)
        br = (Bx[e] * cx + By[e] * cy) / r
        bt = (-Bx[e] * cy + By[e] * cx) / r
        r1, r2 = self.m['radii']['rg1'] * 1e-3, self.m['radii']['rg2'] * 1e-3
        return self.mat['L_stk'] / (MU0 * (r2 - r1)) * np.sum(br * bt * r * self.area[e])

    def gap_field(self, A, r_mm=None, n=720):
        """radial / tangential B on a circle in the middle of the air gap"""
        rr = (self.m['radii']['rg1'] + self.m['radii']['rg2']) / 2 if r_mm is None else r_mm
        ph = np.linspace(0, 2 * np.pi, n, endpoint=False)
        pts = np.stack([rr * 1e-3 * np.cos(ph), rr * 1e-3 * np.sin(ph)], 1)
        tri = self.find(pts)
        Bx, By = self.B_of(A)
        bx, by = Bx[tri], By[tri]
        return ph, bx * np.cos(ph) + by * np.sin(ph), -bx * np.sin(ph) + by * np.cos(ph)

    def find(self, pts):
        if not hasattr(self, '_tf'):
            import matplotlib.tri as mtri
            self._tri = mtri.Triangulation(self.P[:, 0], self.P[:, 1], self.T)
            self._tf = self._tri.get_trifinder()
        return self._tf(pts[:, 0], pts[:, 1])

    # -------------------------------------------------------------- time-harmonic eddy currents in the rotor frame
    def eddy_harmonic(self, omega_r, I_amp, sequence=+1, mu_shaft=None, sigma_shaft=3.5e6, sigma_mag=0.0, sigma_shield=3.6e7, sigma_sleeve=0.0):
        """complex A for a balanced 3-ph current set of amplitude I_amp (peak, phase total) at the rotor-frame angular
        frequency omega_r (rotating 2-pole field forward (+1) or backward (-1)); linear: iron nu from the last nonlinear
        solve (self.last_nu), shaft incremental mu_shaft.  Returns loss per region (W, stack length) and the solution."""
        nu = self.last_nu.copy()
        if mu_shaft is not None:
            nu[self.reg['shaft']] = 1.0 / (MU0 * mu_shaft)
        Ke = (nu * self.area)[:, None, None] * self.Me
        sig = np.zeros(len(self.T))
        sig[self.reg['shaft']] = sigma_shaft
        sig[self.reg['magnet']] = sigma_mag
        sig[self.reg['shield']] = sigma_shield
        sig[self.reg['sleeve']] = sigma_sleeve
        Mloc = np.array([[2, 1, 1], [1, 2, 1], [1, 1, 2]]) / 12.0
        Me = (sig * self.area)[:, None, None] * Mloc[None]
        K = sp.csr_matrix((Ke.ravel(), (self.I, self.J)), shape=(self.N, self.N))
        Mm = sp.csr_matrix((Me.ravel(), (self.I, self.J)), shape=(self.N, self.N))
        ph = [1.0, np.exp(-1j * sequence * 2 * np.pi / 3), np.exp(1j * sequence * 2 * np.pi / 3)]
        Jz = np.zeros(len(self.T), complex)
        for k in range(3):
            ik = [0, 0, 0]; ik[k] = 1.0
            Jz += self.current_density(ik) * I_amp * ph[k]
        f = np.zeros(self.N, complex)
        np.add.at(f, self.T, (Jz * self.area / 3.0)[:, None] * np.ones((1, 3)))
        Asys = (K + 1j * omega_r * Mm).tocsc()
        fr = self.free
        A = np.zeros(self.N, complex)
        A[fr] = spl.spsolve(Asys[fr][:, fr], f[fr])
        # induced current density per element (centroid), J = -j w sigma A ; loss = sum |J|^2 / (2 sigma) * area * L
        Ae = A[self.T].mean(1)
        loss = {}
        for name in ('shaft', 'magnet', 'shield', 'sleeve'):
            e = self.reg[name]
            if len(e) and sig[e[0]] > 0:
                # element-wise exact integral of |A|^2 over P1: A^H Mloc A * area
                Al = A[self.T[e]]
                q = np.real(np.einsum('ei,ij,ej->e', np.conj(Al), Mloc, Al)) * self.area[e]
                loss[name] = float(0.5 * omega_r ** 2 * sig[e[0]] * q.sum() * self.mat['L_stk'])
        return loss, A
