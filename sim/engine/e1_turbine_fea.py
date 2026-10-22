# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "gmsh", "matplotlib"]
# ///
"""GR180-CCHP E1 - structural verification of the cast IN713LC gas-generator turbine blisk (CalculiX + gmsh).

Steps (all decks / results under sim/engine/fea/, plots + summary under cad_out/engine/E1/):
  --opt    axisymmetric (CAX6) disc study: web position / thickness / rim lips vs bore + burst targets (blades = rim load)
  --3d     1/29 cyclic-symmetry sector (C3D10, periodic gmsh mesh of cad_out/engine/E1/fea_sector.step written by
           cad/engine/gg_turbine.py): 115k hot, 120k hot (trip), 138k cold (spin test) and hot, 115k cold (burst method)
  --modal  prestressed cyclic modal analysis (nodal diameters 0..14) at 0 / 60k / 115k / 138k -> Campbell + interference
  --life   creep (Larson-Miller, IN713LC curve of sim/life_study.py), LCF (Manson universal slopes + SWT), tip growth,
           NGV bore recommendation
  (no flag = all)
Run:  uv run --with numpy --with gmsh --with matplotlib python sim/engine/e1_turbine_fea.py

Units in the decks: mm, N, t (tonne), s, MPa, degC.  Rotation +theta about +x (clockwise seen from the intake).
"""
import os, sys, json, math, subprocess, time, re
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
import gg_turbine as G                                   # profile, blade design, envelope (pure python part)

CCX = os.environ.get('CCX', '/Applications/FreeCAD.app/Contents/Resources/bin/ccx')
FEA = os.path.join(ROOT, 'sim', 'engine', 'fea')
OUT = os.path.join(ROOT, 'cad_out', 'engine', 'E1')
os.makedirs(FEA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
N_DES, N_TRIP, N_SPIN = 115e3, 120e3, 138e3
def omega(N): return N * 2 * math.pi / 60.0

# ===================================================================================== IN713LC (cast, typical values)
# Sources (no US-origin data needed for the product; values are typical and must be replaced by the foundry's certified
# test-bar data): Nickel Institute publ. 393 "High-temperature, high-strength nickel base alloys" (IN-713LC / 713C data:
# density 8.00, RT tensile 895/750 MPa, 538 C 895/760 MPa, dynamic modulus and mean expansion of 713C), Larson-Miller curve as
# in sim/life_study.py. Minimum (design) strength = typical x (AMS-type test-bar minima 760/690 MPa at RT):
# UTS_min = 0.85 UTS_typ, YS_min = 0.92 YS_typ.
MAT_T = np.array([20., 200., 400., 538., 650., 760., 870.])
MAT_E = np.array([199e3, 192e3, 182e3, 175e3, 168e3, 161e3, 152e3])        # MPa
MAT_NU = 0.30
MAT_ALPHA = np.array([10.4, 11.4, 12.7, 13.4, 14.1, 14.9, 15.8]) * 1e-6    # mean (secant) from 20 C, 1/K
MAT_YS = np.array([750., 745., 740., 760., 755., 740., 560.])              # 0.2 % yield, typical
MAT_UTS = np.array([895., 885., 880., 895., 895., 870., 690.])              # typical
MAT_K = np.array([10.9, 13.3, 16.0, 17.8, 19.5, 21.4, 23.5])                # W/mK (reference only)
RHO = 8.00e-9                                                                # t/mm3
RA = 0.12                                                                    # reduction of area (cast, typical 10-15 %)
KD_UTS, KD_YS = 0.85, 0.92
def E_(T): return float(np.interp(T, MAT_T, MAT_E))
def YS(T, minimum=True): return float(np.interp(T, MAT_T, MAT_YS)) * (KD_YS if minimum else 1.0)
def UTS(T, minimum=True): return float(np.interp(T, MAT_T, MAT_UTS)) * (KD_UTS if minimum else 1.0)

def material_cards():
    s = '*MATERIAL, NAME=IN713LC\n*ELASTIC\n'
    s += ''.join('%.1f, %.3f, %.1f\n' % (e, MAT_NU, t) for e, t in zip(MAT_E, MAT_T))
    s += '*EXPANSION, ZERO=20.\n' + ''.join('%.4e, %.1f\n' % (a, t) for a, t in zip(MAT_ALPHA, MAT_T))
    s += '*DENSITY\n%.3e\n' % RHO
    return s

# ===================================================================================== thermal field (steady, prescribed)
T_BORE, T_BLADE = 450.0, 730.0
def T_field(x, r):
    """Steady metal temperature: bore (r 4) 450 C -> platform (r_hub(x)) 730 C linear in r, blade 730 C (user spec)."""
    rh = G.r_hub(np.clip(x, G.X_PF, G.X_PR))
    f = np.clip((np.asarray(r) - 4.0) / (rh - 4.0), 0.0, 1.0)
    return T_BORE + (T_BLADE - T_BORE) * f

# ===================================================================================== CalculiX helpers
def run_ccx(job, cwd=None, threads=8):
    cwd = cwd or FEA                 # resolved at call time (FEA may be redirected)
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), CCX_NPROC_EQUATION_SOLVER=str(threads))
    t0 = time.time()
    p = subprocess.run([CCX, '-i', job], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = p.stdout
    open(os.path.join(cwd, job + '.log'), 'w').write(log)
    if 'ERROR' in log.upper() and 'Job finished' not in log:
        print(log[-3000:]); raise RuntimeError('ccx failed: ' + job)
    return time.time() - t0, log

def read_frd(path):
    """Parse an ASCII .frd: returns list of blocks {name, step, time, ncomp, data{node: array}}, and nodes {id: xyz}."""
    nodes = {}; blocks = []; cur = None
    with open(path) as f:
        mode = None
        for line in f:
            if line.startswith('    2C'): mode = 'nodes'; continue
            if line.startswith('    1PSTEP'): continue
            if line.startswith('  100CL'):
                tm = float(line[12:25]); stp = int(line[58:63]) if len(line) > 63 and line[58:63].strip() else 0
                cur = dict(time=tm, step=stp, header=line, data={}); mode = 'res0'; continue
            if mode == 'nodes':
                if line.startswith(' -1'):
                    nid = int(line[3:13]); nodes[nid] = np.array([float(line[13 + 12 * k:25 + 12 * k]) for k in range(3)])
                elif line.startswith(' -3'): mode = None
                continue
            if mode == 'res0' and line.startswith(' -4'):
                cur['name'] = line[5:13].strip(); mode = 'res'; continue
            if mode == 'res':
                if line.startswith(' -5'): continue
                if line.startswith(' -1'):
                    nid = int(line[3:13]); vals = line[13:].rstrip('\n')
                    n = len(vals) // 12
                    cur['data'][nid] = np.array([float(vals[12 * k:12 * k + 12]) for k in range(n)])
                elif line.startswith(' -2'):
                    nid = None
                elif line.startswith(' -3'):
                    blocks.append(cur); mode = None
    return nodes, blocks

def read_dat_stresses(path, key='stresses (elem, integ.pnt.'):
    """*EL PRINT stresses: {elem: [[sxx syy szz sxy sxz syz] per ip]} of the LAST block with this header."""
    out = {}; blk = None
    with open(path) as f:
        for line in f:
            if key in line: blk = {}; out = blk; continue
            if blk is None: continue
            p = line.split()
            if not p: continue
            if len(p) == 8:
                try:
                    e = int(p[0]); v = [float(x) for x in p[2:]]
                    blk.setdefault(e, []).append(v); continue
                except ValueError: pass
            blk = None
    return out

def vm(s):   # s: (...,6) xx yy zz xy xz yz  (frd order for 3D: SXX SYY SZZ SXY SYZ SZX)
    s = np.asarray(s)
    return np.sqrt(0.5 * ((s[..., 0] - s[..., 1])**2 + (s[..., 1] - s[..., 2])**2 + (s[..., 2] - s[..., 0])**2)
                   + 3 * (s[..., 3]**2 + s[..., 4]**2 + s[..., 5]**2))

# ===================================================================================== axisymmetric disc study
def axisym_mesh(P, h=0.25):
    import gmsh
    poly = G.sample_profile(G.disc_profile('final', P), ds=0.12)
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0); gmsh.model.add('ax')
    # CCX axisymmetric: X = radius, Y = axial (ENG x)
    pts = [gmsh.model.occ.addPoint(r, x, 0, h) for (x, r) in poly]
    lines = [gmsh.model.occ.addLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    cl = gmsh.model.occ.addCurveLoop(lines); sf = gmsh.model.occ.addPlaneSurface([cl]); gmsh.model.occ.synchronize()
    gmsh.option.setNumber('Mesh.CharacteristicLengthMax', h); gmsh.option.setNumber('Mesh.ElementOrder', 2)
    gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.model.mesh.generate(2)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(9)
    gmsh.finalize()
    nodes = {int(t): xyz[i, :2] for i, t in enumerate(nt)}
    els = en.reshape(-1, 6).astype(int)
    # orientation: positive area in (X=r, Y=x)
    out = []
    for e in els:
        a, b, c = (nodes[e[0]], nodes[e[1]], nodes[e[2]])
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            e = [e[0], e[2], e[1], e[5], e[4], e[3]]
        out.append(list(e))
    return nodes, out

def axisym_run(P, N, hot, tag, h=0.25, Fblade=None, Tn=None):
    """Tn: optional nodal temperatures {node: C} on this mesh (from a thermal run) instead of the prescribed T_field."""
    nodes, els = axisym_mesh(P, h)
    Tnode = (Tn if Tn is not None else {k: float(T_field(v[1], v[0])) for k, v in nodes.items()}) if hot else None
    rot = AXI_ROT
    om = omega(N)
    F = (Fblade if Fblade is not None else AXI_F115) * (N / N_DES)**2       # blade pull per blade
    # platform faces under the blades (x between hub LE and TE) -> outward traction
    le_h, te_h = G.ROT_LE[0], G.ROT_TE[0]
    # platform edges under the blades (x between hub LE and TE): radial blade pull as consistent nodal forces (quadratic edge:
    # 1/6, 2/3, 1/6). CalculiX axisymmetric convention: concentrated forces are given for the full 360 deg (checked in --opt).
    cl = {}; Aplat = 0.0
    edge_nodes = ((0, 1, 3), (1, 2, 4), (2, 0, 5))
    for ei, e in enumerate(els, 1):
        for (i, j, m) in edge_nodes:
            a, b = nodes[e[i]], nodes[e[j]]
            xm, rm = 0.5 * (a[1] + b[1]), 0.5 * (a[0] + b[0])
            if le_h <= xm <= te_h and abs(a[0] - G.r_hub(a[1])) < 0.02 and abs(b[0] - G.r_hub(b[1])) < 0.02:
                dA = 2 * math.pi * rm * math.hypot(a[0] - b[0], a[1] - b[1]); Aplat += dA
                for n_, w in ((e[i], 1 / 6), (e[j], 1 / 6), (e[m], 2 / 3)): cl[n_] = cl.get(n_, 0.0) + w * dA
    q = G.Z_ROT * F / Aplat
    cl = {k: v * q * AXI_CLOAD_SCALE for k, v in cl.items()}
    job = 'axi_' + tag
    with open(os.path.join(FEA, job + '.inp'), 'w') as f:
        f.write('** GR180 E1 axisymmetric disc study %s, N=%.0f rpm, hot=%s, blade pull %.0f N x %d on %.0f mm2 -> q %.2f MPa\n'
                % (tag, N, hot, F, G.Z_ROT, Aplat, q))
        f.write('*NODE, NSET=NALL\n' + ''.join('%d, %.6f, %.6f\n' % (k, v[0], v[1]) for k, v in nodes.items()))
        f.write('*ELEMENT, TYPE=CAX6, ELSET=EALL\n' + ''.join('%d, %s\n' % (i, ', '.join(map(str, e))) for i, e in enumerate(els, 1)))
        face = [k for k, v in nodes.items() if abs(v[1] - G.X_HUB) < 1e-4]
        fix = [min(face, key=lambda k: abs(nodes[k][0] - 5.2))]          # one ring on the sleeve face (axial rigid body only)
        f.write('*NSET, NSET=NFIX\n' + ''.join('%d,\n' % k for k in fix))
        f.write(material_cards() + '*SOLID SECTION, ELSET=EALL, MATERIAL=IN713LC\n')
        f.write('*INITIAL CONDITIONS, TYPE=TEMPERATURE\nNALL, 20.\n*BOUNDARY\nNFIX, 2, 2, 0.\n')
        f.write('*STEP\n*STATIC\n*DLOAD\nEALL, CENTRIF, %.6e, 0., 0., 0., 0., 1., 0.\n' % om**2)
        f.write('*CLOAD\n' + ''.join('%d, 1, %.4f\n' % (k, v) for k, v in cl.items()))
        if hot:
            f.write('*TEMPERATURE\n' + ''.join('%d, %.2f\n' % (k, Tnode[k]) for k in nodes))
        f.write('*NODE FILE\nU\n*EL FILE\nS\n*EL PRINT, ELSET=EALL\nS\n*END STEP\n')
    dt, log = run_ccx(job)
    nd, blocks = read_frd(os.path.join(FEA, job + '.frd'))
    S = [b for b in blocks if b.get('name') == 'STRESS'][-1]['data']
    U = [b for b in blocks if b.get('name') == 'DISP'][-1]['data']
    ip = read_dat_stresses(os.path.join(FEA, job + '.dat'))
    # bore: nodes at r = 4 inside the fit length
    rb = dict(G.DISC, **(P or {})).get('r_bore', 4.0)          # bore surface, or the axis of a bore-less disc
    bore = [k for k, v in nodes.items() if abs(v[0] - rb) < 1e-3 and G.X_HUB + 0.4 < v[1] < G.X_HUB + G.HUB_L - 0.4]
    s_hoop_bore = max(S[k][2] for k in bore)
    vm_all = {k: vm(np.array([S[k][0], S[k][1], S[k][2], S[k][3], 0, 0])) for k in S}
    vm_bore = max(vm_all[k] for k in bore)
    # area-averaged hoop stress (meridional section, from integration points)
    A = 0.0; SA = 0.0; TA = 0.0
    for ei, e in enumerate(els, 1):
        a, b, c = nodes[e[0]], nodes[e[1]], nodes[e[2]]
        ar = 0.5 * abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        sh = np.mean([v[2] for v in ip[ei]])
        A += ar; SA += sh * ar; TA += (np.mean([Tnode[n_] for n_ in e[:3]]) if hot else 20.0) * ar
    hoop_avg = SA / A; T_avg = TA / A if hot else 20.0
    # web / rim peak
    vmax = max(vm_all.values()); kmax = max(vm_all, key=vm_all.get)
    A_mer, xc, rc = G.polygon_area_centroid(G.sample_profile(G.disc_profile('final', P)))
    res = dict(tag=tag, N=N, hot=hot, q=q, bore_hoop=s_hoop_bore, bore_vm=vm_bore, hoop_avg=hoop_avg, T_avg=T_avg,
               vm_max=vmax, vm_max_at=tuple(nodes[kmax]), disc_mass_g=2 * math.pi * rc * A_mer * RHO * 1e6,
               u_rim=float(np.mean([U[k][0] for k, v in nodes.items() if abs(v[0] - G.r_hub(v[1])) < 0.02 and le_h < v[1] < te_h])),
               ccx_s=dt)
    return res

AXI_ROT = None
AXI_CLOAD_SCALE = 1.0
AXI_F115 = None

def axisym_study():
    global AXI_F115
    rot = G.design_rotor()
    sb, F, Ar, tap, r0 = G.blade_pull_estimate(rot)
    AXI_F115 = F * 1.08          # + root fillets / platform-above-hub share (~8 %, checked by the 3-D sector)
    print('blade pull (1-D) %.0f N @115k (+8 %% fillets -> %.0f N)' % (F, AXI_F115))
    base = dict(G.DISC)
    cases = []
    # web centre at r 15 (xm) and thickness (w15), boss / rear face at r 6.5 (x_boss), rim lips
    # stage 1 (36 cases, web centre / thickness / boss / web fillet) selected xf 111.6, xr 115.6, boss 118.5, R_web 2.5;
    # stage 2: hub shoulders (front face at x 108.6 up to r_hf, rear face at the boss x up to r_hr) and web thickness
    stage = os.environ.get('E1_OPT_STAGE', '2')
    if stage == '1':
        for xm in (113.6, 114.4, 115.2):
            for w15 in (4.0, 5.0, 6.0):
                for xb in (117.9, 118.5):
                    for Rw in (1.5, 2.5):
                        cases.append(dict(base, xf_w=xm - w15 / 2, xr_w=xm + w15 / 2, x_boss=xb, R_web=Rw, r_hf=6.4, r_hr=6.5))
    else:
        for w15, xm in ((4.0, 113.6), (5.0, 113.9)):
            for rhf in (6.4, 9.5, 11.5):
                for rhr in (6.5, 9.5, 11.5):
                    cases.append(dict(base, xf_w=xm - w15 / 2, xr_w=xm + w15 / 2, x_boss=118.5, R_web=2.5, r_hf=rhf, r_hr=rhr))
    rows = []
    for i, P in enumerate(cases):
        tag = 'opt%02d' % i
        try:
            h = axisym_run(P, N_DES, True, tag + 'h')
            c = axisym_run(P, N_DES, False, tag + 'c')
            s = axisym_run(P, N_SPIN, False, tag + 's')
        except Exception as ex:
            print('case', i, 'failed', ex); continue
        burst = N_DES * math.sqrt(0.85 * UTS(h['T_avg']) / c['hoop_avg'])
        row = dict(i=i, P={k: P[k] for k in ('xf_w', 'xr_w', 'x_boss', 'r_lip_f', 'r_lip_r', 'R_web', 'r_hf', 'r_hr')}, mass_g=h['disc_mass_g'],
                   vm_max_115c=c['vm_max'], vm_max_115c_at=c['vm_max_at'], bore_vm_115c=c['bore_vm'],
                   bore_hoop_115h=h['bore_hoop'], bore_vm_115h=h['bore_vm'], bore_vm_138c=s['bore_vm'], vm_max_115h=h['vm_max'],
                   vm_max_at=h['vm_max_at'], hoop_avg_115c=c['hoop_avg'], T_avg=h['T_avg'], burst_rpm=burst, u_rim_115h=h['u_rim'])
        rows.append(row)
        print('%2d hub r %.1f/%.1f xf %.1f xr %.1f | disc %.1f g | 115c bore vm %4.0f hoop %4.0f max %4.0f @(%.1f,%.1f) | 115h bore vm %4.0f max %4.0f | 138c bore vm %4.0f | burst %.0fk (%.2f)' % (
              i, P['r_hf'], P['r_hr'], P['xf_w'], P['xr_w'], row['mass_g'], c['bore_vm'], c['bore_hoop'], c['vm_max'], c['vm_max_at'][1], c['vm_max_at'][0],
              h['bore_vm'], h['vm_max'], s['bore_vm'], burst / 1e3, burst / N_DES), flush=True)
    json.dump(dict(F_blade_115=AXI_F115, rows=rows), open(os.path.join(FEA, 'axisym_study_stage%s.json' % stage), 'w'), indent=1, default=float)
    return rows

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--opt' in args:
        axisym_study()
