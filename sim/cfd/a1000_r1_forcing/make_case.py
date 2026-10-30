#!/usr/bin/env python3
"""AURORA-1000 rev 5: unsteady blade forcing on R1 from NGV1 (48 vanes: EO48, EO96) and NGV2 (24 vanes: EO24) by a
2-D mid-span URANS of the NGV1 - R1 - NGV2 rows (OpenFOAM v2606, rhoPimpleFoam, sliding mesh).

Domain: blade-to-blade surface at the mean radius rm = 231.7 mm, unrolled (x axial, y = rm theta), sector of 30 deg =
4 NGV1 (pitch exact) : 5 R1 (scaled pitch: 60 instead of 59 blades, 1.7 % smaller pitch, same profile) : 2 NGV2
(exact). The stators are exact, so the rotor sees the true 48 / 96 / 24 x shaft frequencies.
Sections: cad/engine/a1000_turbine.py design_row(row, [0.5]) (the CAD mid-span sections), CAD clocking (TE of vane 0 of
both NGVs at theta 0). Quasi-3-D stream tube: one cell in z, z thickness = 0.25 x annulus height h(x) (24.6 -> 31.1 ->
38.1 -> 49.4 mm, constant behind NGV2), symmetry on both z faces, so the axial velocity follows the meanline (Cx ~ 182 m/s)
instead of doubling with the density drop.
Mesh: gmsh 2-D (quad-dominant, boundary layer on the blades, 0.25 mm in the NGV1 wake / R1 region) extruded one layer;
three blocks joined by two cyclicPeriodicAMI interfaces (x 26 and 58.5 mm); the R1 block moves at U = omega rm =
364 m/s (+y = direction of rotation); periodic sides cyclic (translational, one sector).
Gas: perfect gas, cp 1170, gamma 1.33 (R 290), mu 4.7e-5 Pa s, Pr 0.7; kOmegaSST, Spalding wall function.
BCs: inlet total p 3.547 bar / total T 1223.15 K axial (950 C, meanline P0_in), outlet mean static p set for the
meanline NGV2 exit (P_OUT); walls adiabatic.
Run:  ~/micromamba/envs/gr180/bin/python sim/cfd/a1000_r1_forcing/make_case.py [--mesh-only] [--run] [--post]
      A1000_CFD_NP (processors, default 6), A1000_CFD_T1 (startup end time [s]), A1000_CFD_T2 (sampling length [s]).
Writes: sim/cfd/a1000_r1_forcing/case/ (not in git), forcing.json (harmonics of the R1 blade pressure), docs/img plot.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CASE = os.path.join(HERE, 'case')
OF = os.environ.get('OF', '/Applications/OpenFOAM-v2606.app/Contents/Resources/etc/openfoam')
NP = int(os.environ.get('A1000_CFD_NP', 6))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_turbine as A                                     # noqa: E402
sys.argv = _argv

RM = A.RM                                                      # mm
N_SECT = 12                                                    # 30 deg sector
P_SECT = 2 * math.pi * RM / N_SECT                             # mm
ROWS = dict(N1=dict(n=4), R1=dict(n=5), N2=dict(n=2))          # blades per sector (R1: 60 equivalent, scaled pitch)
U_ROT = A.OM * RM * 1e-3                                       # m/s
X_IN, X_I1, X_I2 = -35.0, A.X_TE['N1'] + A.GAP1 / 2, 0.5 * (A.x_te_of('R1', 0.5) + A.X_LE['N2'])
X_OUT = A.X_TE['N2'] + 50.0
ZSCALE = 0.25
ST1, ST2 = A.T['stages']
P0_IN, T0_IN = ST1['P0_in'], ST1['T0_in']
CP, GAM = A.CP_G, A.GAM; RG = CP * (GAM - 1) / GAM


def _static(T0, P0, C, loss=0.0):
    T = T0 - C * C / (2 * CP); return T, P0 * (1 - loss) * (T / T0) ** (GAM / (GAM - 1))


T2_, P2_ = _static(ST1['T0_in'], ST1['P0_in'], ST1['C2'], 0.02)               # NGV1 exit
T3_, P3_ = _static(ST2['T0_in'], ST2['P0_in'], math.hypot(A.CX, A.CT3_M))      # R1 exit
T4_, P4_ = _static(ST2['T0_in'], ST2['P0_in'], ST2['C2'], 0.03)               # NGV2 exit
P_OUT = float(os.environ.get('A1000_CFD_POUT', P4_))


def zthick(x):
    """z thickness [mm] of the quasi-3-D stream tube: ZSCALE x annulus height, constant behind NGV2"""
    return ZSCALE * A.height(min(max(x, A.X_LE['N1']), A.X_TE['N2']))


def sections():
    out = {}
    for row in ROWS:
        s = A.design_row(row, [0.5])[0.5]
        pts, side, xis = s.outline(140, 21)
        x = pts[:, 0]; y = RM * np.arctan2(pts[:, 2], pts[:, 1])
        Zs = 60 if row == 'R1' else A.Z[row]
        out[row] = dict(x=x, y=y, side=side, xc=s.xc, yc=RM * s.th, k1=s.k1, k2=s.k2, pitch=2 * math.pi * RM / Zs,
                        x_le=float(x.min()), x_te=float(x.max()), chord=s.chord)
    return out


def per_line(sec, x0, x1, L=8.0):
    """mid-passage periodic boundary between blade -1 and blade 0: camber line - pitch / 2, extended along the metal
    angles with a slope fading over L [mm]"""
    xc, yc = sec['xc'], sec['yc']; t1, t2 = math.tan(math.radians(sec['k1'])), math.tan(math.radians(sec['k2']))
    xs = np.unique(np.r_[np.linspace(x0, xc[0], max(3, int((xc[0] - x0) / 1.0))) if x0 < xc[0] else [],
                         np.linspace(max(x0, xc[0]), min(x1, xc[-1]), 40),
                         np.linspace(xc[-1], x1, max(3, int((x1 - xc[-1]) / 1.0))) if x1 > xc[-1] else []])
    xs = xs[(xs >= x0) & (xs <= x1)]
    y = np.interp(xs, xc, yc)
    up = xs < xc[0]; dn = xs > xc[-1]
    y[up] = yc[0] - t1 * L * (1 - np.exp(-(xc[0] - xs[up]) / L))
    y[dn] = yc[-1] + t2 * L * (1 - np.exp(-(xs[dn] - xc[-1]) / L))
    return xs, y - sec['pitch'] / 2


# ------------------------------------------------------------------------------------------------ mesh (gmsh)
def mesh(path):
    import gmsh
    S = sections()
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0); gmsh.model.add('a1000_r1')
    occ = gmsh.model.occ
    blocks = dict(N1=(X_IN, X_I1), R1=(X_I1, X_I2), N2=(X_I2, X_OUT))
    info = {}
    for row, (x0, x1) in blocks.items():
        sec = S[row]; xs, yb = per_line(sec, x0, x1)
        pb = [occ.addPoint(x, y, 0) for x, y in zip(xs, yb)]
        pt = [occ.addPoint(x, y + P_SECT, 0) for x, y in zip(xs, yb)]
        cb, ct = occ.addSpline(pb), occ.addSpline(pt)
        cl, cr = occ.addLine(pb[0], pt[0]), occ.addLine(pb[-1], pt[-1])
        loop = occ.addCurveLoop([cb, cr, ct, cl])
        holes, bl = [], []
        for k in range(ROWS[row]['n']):
            q = [occ.addPoint(x, y + k * sec['pitch'], 0) for x, y in zip(sec['x'], sec['y'])]
            c = occ.addSpline(q + [q[0]]); bl.append(c); holes.append(occ.addCurveLoop([c]))
        surf = occ.addPlaneSurface([loop] + holes)
        info[row] = dict(cb=cb, ct=ct, cl=cl, cr=cr, blades=bl, surf=surf, yb0=float(yb[0]), yb1=float(yb[-1]))
    occ.synchronize()
    for row, d in info.items():
        gmsh.model.mesh.setPeriodic(1, [d['ct']], [d['cb']], [1, 0, 0, 0, 0, 1, 0, P_SECT, 0, 0, 1, 0, 0, 0, 0, 1])
    # sizes [mm]: blades 0.12 (LE / TE) growing to the block size; NGV1 wake + R1 0.25; NGV2 0.45; inlet / outlet coarse
    fl = gmsh.model.mesh.field
    allb = [c for d in info.values() for c in d['blades']]
    fd = fl.add('Distance'); fl.setNumbers(fd, 'CurvesList', allb); fl.setNumber(fd, 'Sampling', 400)
    ft = fl.add('Threshold'); fl.setNumber(ft, 'InField', fd)
    for k, v in (('SizeMin', 0.12), ('SizeMax', 1.6), ('DistMin', 0.3), ('DistMax', 8.0)): fl.setNumber(ft, k, v)
    boxes = []
    for (xa, xb, h) in ((X_IN - 1, -6.0, 1.2), (-6.0, 14.0, 0.40), (14.0, X_I2 + 2, 0.25), (X_I2 - 2, A.X_TE['N2'] + 6, 0.45),
                        (A.X_TE['N2'] + 6, X_OUT + 1, 0.9)):
        b = fl.add('Box')
        for k, v in (('VIn', h), ('VOut', 5.0), ('XMin', xa), ('XMax', xb), ('YMin', -400.0), ('YMax', 400.0),
                     ('ZMin', -1.0), ('ZMax', 1.0)): fl.setNumber(b, k, v)
        boxes.append(b)
    fm = fl.add('Min'); fl.setNumbers(fm, 'FieldsList', [ft] + boxes); fl.setAsBackgroundMesh(fm)
    blf = fl.add('BoundaryLayer'); fl.setNumbers(blf, 'CurvesList', allb)
    for k, v in (('Size', 0.015), ('Ratio', 1.25), ('Thickness', 0.30), ('Quads', 1)): fl.setNumber(blf, k, v)
    fl.setAsBoundaryLayer(blf)
    for k, v in (('Mesh.MeshSizeExtendFromBoundary', 0), ('Mesh.MeshSizeFromPoints', 0), ('Mesh.MeshSizeFromCurvature', 0),
                 ('Mesh.Algorithm', 6), ('Mesh.RecombineAll', 1), ('Mesh.RecombinationAlgorithm', 1),
                 ('Mesh.MshFileVersion', 2.2), ('Mesh.SaveAll', 0)):
        gmsh.option.setNumber(k, v)
    # one structured layer in z
    ext = occ.extrude([(2, d['surf']) for d in info.values()], 0, 0, 1.0, numElements=[1], recombine=True)
    occ.synchronize()
    tops = [ext[i - 1][1] for i, e in enumerate(ext) if e[0] == 3]
    vols = {row: ext[[i for i, e in enumerate(ext) if e[0] == 3][j]][1] for j, row in enumerate(info)}
    lat = {}
    for dim, tag in gmsh.model.getEntities(2):
        bnd = [abs(t) for _, t in gmsh.model.getBoundary([(2, tag)], oriented=False)]
        for row, d in info.items():
            for key in ('cb', 'ct', 'cl', 'cr'):
                if d[key] in bnd and tag != d['surf']: lat[(row, key)] = tag
            for k, c in enumerate(d['blades']):
                if c in bnd and tag != d['surf']: lat[(row, 'b%d' % k)] = tag
    def pg(dim, tags, name): gmsh.model.setPhysicalName(dim, gmsh.model.addPhysicalGroup(dim, tags), name)
    pg(2, [lat[('N1', 'cl')]], 'g_inlet'); pg(2, [lat[('N2', 'cr')]], 'g_outlet')
    pg(2, [lat[('N1', 'b%d' % k)] for k in range(ROWS['N1']['n'])], 'g_N1_wall')
    pg(2, [lat[('N2', 'b%d' % k)] for k in range(ROWS['N2']['n'])], 'g_N2_wall')
    for k in range(ROWS['R1']['n']): pg(2, [lat[('R1', 'b%d' % k)]], 'g_R1_b%d' % k)
    for row in info:
        pg(2, [lat[(row, 'cb')]], 'g_per%s_lo' % row); pg(2, [lat[(row, 'ct')]], 'g_per%s_hi' % row)
    pg(2, [lat[('N1', 'cr')]], 'g_ami1_s'); pg(2, [lat[('R1', 'cl')]], 'g_ami1_r')
    pg(2, [lat[('R1', 'cr')]], 'g_ami2_r'); pg(2, [lat[('N2', 'cl')]], 'g_ami2_s')
    pg(2, [d['surf'] for d in info.values()], 'g_front'); pg(2, tops, 'g_back')
    for row, v in vols.items(): pg(3, [v], row)
    gmsh.model.mesh.generate(3)
    gmsh.write(path)
    n3 = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
    gmsh.finalize()
    json.dump(dict(rm=RM, p_sect=P_SECT, u_rot=U_ROT, x=[X_IN, X_I1, X_I2, X_OUT],
                   rows={r: dict(n=ROWS[r]['n'], pitch=S[r]['pitch'], x_le=S[r]['x_le'], x_te=S[r]['x_te'], chord=S[r]['chord'],
                                 k1=S[r]['k1'], k2=S[r]['k2'], x=S[r]['x'].tolist(), y=S[r]['y'].tolist(), side=S[r]['side'].tolist())
                         for r in ROWS}),
              open(os.path.join(HERE, 'geometry.json'), 'w'), indent=0)
    print('gmsh: %d cells, blocks x %.1f / %.1f / %.1f / %.1f mm, sector %.2f mm, U_rot %.1f m/s' % (
        n3, X_IN, X_I1, X_I2, X_OUT, P_SECT, U_ROT), flush=True)


# ------------------------------------------------------------------------------------------------ OpenFOAM case
HEADER = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       %s;\n    object      %s;\n}\n'


def w(rel, cls, body):
    path = os.path.join(CASE, rel); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w').write(HEADER % (cls, os.path.basename(rel)) + body)


def sh(cmd, log):
    with open(os.path.join(CASE, log), 'w') as f:
        p = subprocess.run([OF, '-c', 'cd "%s" && %s' % (CASE, cmd)], stdout=f, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        print(open(os.path.join(CASE, log)).read()[-3000:]); raise RuntimeError('failed: ' + cmd)


def read_vectors(path):
    txt = open(path).read(); m = re.search(r'\n(\d+)\s*\n\(\s*\n', txt); n = int(m.group(1)); body = txt[m.end():]
    return np.array(re.findall(r'\(([-\d.eE+]+) ([-\d.eE+]+) ([-\d.eE+]+)\)', body[:body.find('\n)')])[:n], float)


def remap_points():
    """mm -> m and z = 0 / 1 -> 0 / zthick(x)"""
    path = os.path.join(CASE, 'constant', 'polyMesh', 'points'); txt = open(path).read()
    m = re.search(r'\n(\d+)\s*\n\(\s*\n', txt); n = int(m.group(1))
    P = read_vectors(path); assert len(P) == n
    z = P[:, 2] * np.array([zthick(x) for x in P[:, 0]])
    Q = np.c_[P[:, 0], P[:, 1], z] * 1e-3
    open(path, 'w').write(txt[:m.end()] + ''.join('(%.9g %.9g %.9g)\n' % tuple(q) for q in Q) + ')\n')


def create_patch():
    pv = P_SECT * 1e-3
    ent = []
    for row in ROWS:
        for a, b, sgn in (('lo', 'hi', 1), ('hi', 'lo', -1)):
            ent.append('    { name per%s_%s; patchInfo { type cyclic; neighbourPatch per%s_%s; transform translational; '
                       'separationVector (0 %.9g 0); } constructFrom patches; patches (g_per%s_%s); }' % (row, a, row, b, sgn * pv, row, a))
    for i, (a, b) in enumerate((('ami1_s', 'ami1_r'), ('ami2_r', 'ami2_s'))):
        for p, q in ((a, b), (b, a)):
            ent.append('    { name %s; patchInfo { type cyclicPeriodicAMI; inGroups (cyclicAMI); neighbourPatch %s; '
                       'periodicPatch perR1_lo; maxIter 200; AMIMethod faceAreaWeightAMI2D; } constructFrom patches; patches (g_%s); }' % (p, q, p))
    for nm, tp in [('inlet', 'patch'), ('outlet', 'patch'), ('N1_wall', 'wall'), ('N2_wall', 'wall'), ('front', 'symmetry'),
                   ('back', 'symmetry')] + [('R1_b%d' % k, 'wall') for k in range(ROWS['R1']['n'])]:
        ent.append('    { name %s; patchInfo { type %s; } constructFrom patches; patches (g_%s); }' % (nm, tp, nm))
    w('system/createPatchDict', 'dictionary', 'pointSync false;\nmatchTolerance 1e-4;\npatches\n(\n%s\n);\n' % '\n'.join(ent))


def controls(t_end, ddt, sample_from, dt=5e-7, conv='linearUpwind', wint=1e-4):
    nb = ROWS['R1']['n']
    forces = ''.join('    F_b%d { type forces; libs (forces); patches (R1_b%d); rho rho; CofR (0 0 0); writeControl timeStep; '
                     'writeInterval 1; log false; }\n' % (k, k) for k in range(nb))
    w('system/controlDict', 'dictionary', '''application     rhoPimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         %.6g;
deltaT          %.4g;
adjustTimeStep  no;
writeControl    adjustable;
writeInterval   %.4g;
purgeWrite      3;
writeFormat     ascii;
writePrecision  9;
timeFormat      general;
timePrecision   9;
runTimeModifiable true;

functions
{
    mdot_in  { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet;  operation sum; fields (phi); writeControl timeStep; writeInterval 20; log false; writeFields false; }
    mdot_out { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name outlet; operation sum; fields (phi); writeControl timeStep; writeInterval 20; log false; writeFields false; }
    n1_exit  { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name ami1_s; operation weightedAreaAverage; weightField phi; fields (p T U); writeControl timeStep; writeInterval 20; log false; writeFields false; }
    r1_exit  { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name ami2_s; operation weightedAreaAverage; weightField phi; fields (p T U); writeControl timeStep; writeInterval 20; log false; writeFields false; }
    outlet_avg { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name outlet; operation weightedAreaAverage; weightField phi; fields (p T U); writeControl timeStep; writeInterval 20; log false; writeFields false; }
%s    blade_p
    {
        type surfaces; libs (sampling); timeStart %.6g; writeControl timeStep; writeInterval 2; surfaceFormat raw; interpolationScheme cell;
        fields (p);
        surfaces { R1 { type patch; patches ("R1_b.*"); interpolate false; triangulate false; } }
    }
}
''' % (t_end, dt, wint, forces, sample_from))
    w('system/fvSchemes', 'dictionary', '''ddtSchemes      { default %s; }
gradSchemes     { default Gauss linear; grad(U) cellLimited Gauss linear 1; grad(h) cellLimited Gauss linear 1; grad(k) cellLimited Gauss linear 1; grad(omega) cellLimited Gauss linear 1; }
divSchemes
{
    default         none;
    div(phi,U)      %s;
    div(phi,h)      %s;
    div(phi,K)      Gauss linear;
    div(phi,k)      Gauss upwind;
    div(phi,omega)  Gauss upwind;
    div(meshPhi,p)  Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes   { default limited corrected 0.5; }
wallDist        { method meshWave; updateInterval 0; }   // blades translate rigidly: y fixed
''' % (ddt, 'Gauss linearUpwindV grad(U)' if conv == 'linearUpwind' else 'Gauss upwind',
       'Gauss linearUpwind grad(h)' if conv == 'linearUpwind' else 'Gauss upwind'))
    w('system/fvSolution', 'dictionary', '''solvers
{
    "rho.*"         { solver diagonal; }
    "pcorr.*"       { solver GAMG; smoother GaussSeidel; tolerance 1e-6; relTol 0; }
    p               { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.01; }
    pFinal          { $p; relTol 0; }
    "(U|h|k|omega)" { solver PBiCGStab; preconditioner DILU; tolerance 1e-9; relTol 0.05; }
    "(U|h|k|omega)Final" { solver PBiCGStab; preconditioner DILU; tolerance 1e-9; relTol 0; }
}

PIMPLE
{
    nOuterCorrectors 2;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
    momentumPredictor yes;
    transonic       no;
    correctPhi      no;
    moveMeshOuterCorrectors no;
    pMin            5e4;
    pMax            6e5;
}

relaxationFactors { equations { ".*" 1; } }
''')
    # all AMI faces on one processor: cyclicPeriodicAMI fails when its interface is distributed (v2606: unallocated
    # mapDistribute in the periodic-transform loop)
    w('system/decomposeParDict', 'dictionary', 'numberOfSubdomains %d;\nmethod scotch;\n'
      'constraints { ami { type singleProcessorFaceSets; sets ((amiFaces -1)); enabled true; } }\n' % NP)
    w('system/topoSetDict', 'dictionary', 'actions\n(\n    { name amiFaces; type faceSet; action new; source patchToFace; '
      'patch "ami.*"; }\n);\n')


def constant():
    w('constant/thermophysicalProperties', 'dictionary', '''thermoType
{
    type            hePsiThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}
mixture
{
    specie          { molWeight %.4f; }
    thermodynamics  { Cp %.1f; Hf 0; }
    transport       { mu 4.7e-05; Pr 0.70; }
}
''' % (8314.46 / RG, CP))
    w('constant/turbulenceProperties', 'dictionary', 'simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs off; }\n')
    w('constant/dynamicMeshDict', 'dictionary', '''dynamicFvMesh   dynamicMotionSolverFvMesh;
solver          solidBody;
solidBodyCoeffs
{
    cellZone        R1;
    solidBodyMotionFunction linearMotion;
    linearMotionCoeffs { velocity (0 %.4f 0); }
}
''' % U_ROT)


def fields():
    """initial fields from the meanline stations (x [mm]): static p, T and the absolute swirl, Cx = 182 m/s"""
    C = read_vectors(os.path.join(CASE, '0', 'C')) * 1e3
    xs = [X_IN, 0.0, A.X_TE['N1'], A.X_LE['R1'], A.x_te_of('R1', 0.5), A.X_LE['N2'], A.X_TE['N2'], X_OUT]
    pp = [P0_IN * 0.975, P0_IN * 0.975, P2_, P2_, P3_, P3_, P4_, P4_]
    TT = [T0_IN - A.CX ** 2 / (2 * CP)] * 2 + [T2_, T2_, T3_, T3_, T4_, T4_]
    ct = [0.0, 0.0, A.CT2_M, A.CT2_M, A.CT3_M, A.CT3_M, A.CT2_M, A.CT2_M]
    x = C[:, 0]; p = np.interp(x, xs, pp); T = np.interp(x, xs, TT); uy = np.interp(x, xs, ct)
    def sc(v): return 'nonuniform List<scalar>\n%d\n(\n%s)' % (len(v), ''.join('%.6g\n' % q for q in v))
    def vc(v): return 'nonuniform List<vector>\n%d\n(\n%s)' % (len(v), ''.join('(%.5g %.5g 0)\n' % tuple(q) for q in v))
    nb = ROWS['R1']['n']
    common = '    "per.*" { type cyclic; }\n    "ami.*" { type cyclicAMI; }\n    "(front|back)" { type symmetry; }\n'
    walls = '"(N1_wall|N2_wall|R1_b.*)"'
    k_in = 1.5 * (0.05 * A.CX) ** 2
    w('0/p', 'volScalarField', '''dimensions [1 -1 -2 0 0 0 0];
internalField %s;
boundaryField
{
    inlet  { type totalPressure; p0 uniform %.1f; psi thermo:psi; gamma %.3f; value uniform %.1f; }
    outlet { type fixedMean; meanValue %.1f; value uniform %.1f; }
    %s { type zeroGradient; }
%s}
''' % (sc(p), P0_IN, GAM, P0_IN * 0.975, P_OUT, P_OUT, walls, common))
    w('0/T', 'volScalarField', '''dimensions [0 0 0 1 0 0 0];
internalField %s;
boundaryField
{
    inlet  { type totalTemperature; T0 uniform %.2f; psi thermo:psi; gamma %.3f; value uniform %.2f; }
    outlet { type inletOutlet; inletValue uniform %.1f; value uniform %.1f; }
    %s { type zeroGradient; }
%s}
''' % (sc(T), T0_IN, GAM, T0_IN, T4_, T4_, walls, common))
    w('0/U', 'volVectorField', '''dimensions [0 1 -1 0 0 0 0];
internalField %s;
boundaryField
{
    inlet  { type pressureInletOutletVelocity; value uniform (%.1f 0 0); }
    outlet { type inletOutlet; inletValue uniform (0 0 0); value uniform (%.1f %.1f 0); }
    "(N1_wall|N2_wall)" { type noSlip; }
    "R1_b.*" { type movingWallVelocity; value uniform (0 0 0); }
%s}
''' % (vc(np.c_[np.full_like(x, A.CX), uy]), A.CX, A.CX, A.CT2_M, common))
    for name, dim, val, inl, wall in (
            ('k', '[0 2 -2 0 0 0 0]', k_in, 'turbulentIntensityKineticEnergyInlet; intensity 0.05', 'kqRWallFunction'),
            ('omega', '[0 0 -1 0 0 0 0]', math.sqrt(k_in) / (0.09 ** 0.25 * 0.003), 'turbulentMixingLengthFrequencyInlet; mixingLength 0.003', 'omegaWallFunction'),
            ('nut', '[0 2 -1 0 0 0 0]', 0.0, 'calculated', 'nutUSpaldingWallFunction'),
            ('alphat', '[1 -1 -1 0 0 0 0]', 0.0, 'calculated', 'compressible::alphatWallFunction; Prt 0.85')):
        outl = 'calculated' if name in ('nut', 'alphat') else 'inletOutlet; inletValue uniform %.6g' % val
        w('0/' + name, 'volScalarField', '''dimensions %s;
internalField uniform %.6g;
boundaryField
{
    inlet  { type %s; value uniform %.6g; }
    outlet { type %s; value uniform %.6g; }
    %s { type %s; value uniform %.6g; }
%s}
''' % (dim, val, inl, val, outl, val, walls, wall, val, common))


def build():
    if os.path.isdir(CASE): shutil.rmtree(CASE)
    os.makedirs(os.path.join(CASE, 'system')); os.makedirs(os.path.join(CASE, 'constant'))
    mesh(os.path.join(CASE, 'a1000_r1.msh'))
    t1 = float(os.environ.get('A1000_CFD_T1', 1.6e-3))
    controls(t1, 'Euler', 1.0); constant(); create_patch()
    sh('gmshToFoam a1000_r1.msh', 'log.gmshToFoam')
    remap_points()
    sh('createPatch -overwrite', 'log.createPatch')
    sh('checkMesh', 'log.checkMesh')
    os.makedirs(os.path.join(CASE, '0'), exist_ok=True)
    sh('postProcess -func writeCellCentres -time 0', 'log.cellCentres')
    fields()
    print(open(os.path.join(CASE, 'log.checkMesh')).read()[-1600:])


def run(stage):
    t1 = float(os.environ.get('A1000_CFD_T1', 1.6e-3)); t2 = float(os.environ.get('A1000_CFD_T2', 3.4e-4))
    if stage == 0:                                              # gentle start from the meanline field: 0.1 us, upwind
        controls(2e-5, 'Euler', 1.0, dt=1e-7, conv='upwind', wint=1e-5)
        sh('topoSet', 'log.topoSet'); sh('decomposePar -force', 'log.decomposePar')
    elif stage == 1:
        controls(t1, 'Euler', 1.0)
    else:                                                       # sampling: 2 nd order in time, blade pressure every 1 us
        controls(t1 + t2 + 2e-5, 'backward', t1 + 2e-5)
    sh('mpirun -np %d rhoPimpleFoam -parallel' % NP, 'log.rhoPimpleFoam.%d' % stage)


# ------------------------------------------------------------------------------------------------ post-processing
EO_BASE = 24                                                   # all rotor-frame unsteadiness is periodic at 24 x shaft


def _dat(name, fname='surfaceFieldValue.dat'):
    """rows of a function-object .dat (all restart folders, time-sorted, vectors flattened)"""
    d = os.path.join(CASE, 'postProcessing', name); rows = {}
    for t in os.listdir(d):
        for fn in os.listdir(os.path.join(d, t)):
            if fn != fname: continue
            for line in open(os.path.join(d, t, fn)):
                if line.startswith('#') or not line.strip(): continue
                v = [float(q) for q in line.replace('(', ' ').replace(')', ' ').split()]
                rows[v[0]] = v
    return np.array([rows[k] for k in sorted(rows)])


def harmonic_fit(t, y, eos, base_eo=EO_BASE, nh=16):
    """least-squares fit of mean + linear drift + the harmonics n x base_eo (n = 1..nh) of the shaft frequency; returns
    {eo: complex amplitude} with y = Re(sum A exp(i w t)) (non-integer windows are fine)"""
    om = A.OM; cols = [np.ones_like(t), (t - t.mean()) / (np.ptp(t) or 1)]
    for n in range(1, nh + 1):
        w_ = n * base_eo * om; cols += [np.cos(w_ * t), np.sin(w_ * t)]
    M = np.array(cols).T; c, *_ = np.linalg.lstsq(M, y, rcond=None)
    out = {}
    for n in range(1, nh + 1):
        a, b = c[2 * n:2 * n + 2]; out[n * base_eo] = a - 1j * b       # a cos + b sin = Re((a - i b) e^{iwt})
    return {k: out[k] for k in eos}, c[0], y - M @ c


def outline_param(P, q):
    B = np.roll(P, -1, 0); dv = B - P; L2 = (dv ** 2).sum(1)
    t = np.clip(((q[:, None, :] - P[None]) * dv[None]).sum(2) / L2[None], 0, 1)
    D = ((P[None] + t[..., None] * dv[None] - q[:, None, :]) ** 2).sum(2); i = D.argmin(1); j = np.arange(len(q))
    return (i + t[j, i]) / len(P), np.sqrt(D[j, i])


def post():
    geo = json.load(open(os.path.join(HERE, 'geometry.json'))); g = geo['rows']['R1']
    P0 = np.c_[g['x'], g['y']]; pitch = g['pitch']; U = geo['u_rot']
    sdir = os.path.join(CASE, 'postProcessing', 'blade_p')
    times = sorted((float(t), t) for t in os.listdir(sdir))
    def read_raw(tdir):
        fn = [f for f in os.listdir(os.path.join(sdir, tdir)) if f.endswith('.raw')][0]
        return np.loadtxt(os.path.join(sdir, tdir, fn), comments='#')
    first = read_raw(times[0][1]); t0 = times[0][0]
    xy = first[:, :2] * 1e3; xy[:, 1] -= U * t0 * 1e3                  # back to the t = 0 rotor position [mm]
    blade = np.rint((xy[:, 1] - np.interp(xy[:, 0], P0[:, 0][np.argsort(P0[:, 0])], P0[:, 1][np.argsort(P0[:, 0])])) / pitch).astype(int)
    tau, dist = np.zeros(len(xy)), np.zeros(len(xy))
    for k in range(ROWS['R1']['n']):
        m = blade == k
        tau[m], dist[m] = outline_param(P0 + [0, k * pitch], xy[m])
    print('blade-pressure faces %d, blades %s, max distance to the outline %.3f mm, %d samples %.1f..%.1f us' % (
        len(xy), np.bincount(blade).tolist(), dist.max(), len(times), 1e6 * times[0][0], 1e6 * times[-1][0]), flush=True)
    t = np.array([q[0] for q in times]); p = np.array([read_raw(q[1])[:, 3] for q in times])      # (nt, nfaces)
    eos = (24, 48, 72, 96, 120, 144)
    H = {k: np.zeros(len(xy), complex) for k in eos}; pm = np.zeros(len(xy)); rms_res = 0.0
    half = len(t) // 2; Ha = {k: np.zeros(len(xy), complex) for k in eos}; Hb = {k: np.zeros(len(xy), complex) for k in eos}
    for j in range(len(xy)):
        h, mean, res = harmonic_fit(t, p[:, j], eos); pm[j] = mean; rms_res = max(rms_res, np.std(res))
        for k in eos: H[k][j] = h[k]
        ha, _, _ = harmonic_fit(t[:half], p[:half, j], eos); hb, _, _ = harmonic_fit(t[half:], p[half:, j], eos)
        for k in eos: Ha[k][j] = ha[k]; Hb[k][j] = hb[k]
    # blade-to-blade: align each blade's harmonic on blade 0 (one phase per blade and order), average the complex values
    out = dict(tau=[], harmonics={}, blades=ROWS['R1']['n'])
    tg = np.linspace(0, 1, 400, endpoint=False)
    def on_grid(vals, m):
        o = np.argsort(tau[m]); tt = np.r_[tau[m][o] - 1, tau[m][o], tau[m][o] + 1]; v = vals[m][o]
        return np.interp(tg, tt, np.r_[v.real, v.real, v.real]) + 1j * np.interp(tg, tt, np.r_[v.imag, v.imag, v.imag])
    stats = {}
    for k in eos:
        G = [on_grid(H[k], blade == b) for b in range(ROWS['R1']['n'])]
        ref = G[0]; al = [Gi * np.exp(-1j * np.angle(np.sum(Gi * ref.conj()))) for Gi in G]
        avg = np.mean(al, 0); amp_b = [float(np.sqrt(np.mean(np.abs(a_) ** 2))) for a_ in al]
        conv = float(np.sqrt(np.mean(np.abs(on_grid(Ha[k] - Hb[k], blade == 0)) ** 2)) / max(amp_b[0], 1e-9))
        out['harmonics'][str(k)] = dict(re=avg.real.tolist(), im=avg.imag.tolist(), rms_Pa=float(np.sqrt(np.mean(np.abs(avg) ** 2))),
                                        rms_per_blade_Pa=amp_b, max_Pa=float(np.abs(avg).max()), period_change=conv)
        stats[k] = (np.sqrt(np.mean(np.abs(avg) ** 2)), np.abs(avg).max(), min(amp_b), max(amp_b), conv)
    out['tau'] = tg.tolist(); out['p_mean_Pa'] = on_grid(pm + 0j, blade == 0).real.tolist(); out['fit_residual_max_Pa'] = rms_res
    # blade forces (forces function objects: total = pressure + viscous), per unit span of the z slab
    zb = zthick(0.5 * (A.X_LE['R1'] + A.x_te_of('R1', 0.5))) * 1e-3
    fh = {}
    for b in range(ROWS['R1']['n']):
        d = _dat('F_b%d' % b, 'force.dat'); d = d[(d[:, 0] >= t[0]) & (d[:, 0] <= t[-1])]
        for comp, col in (('x', 1), ('y', 2)):
            h, mean, _ = harmonic_fit(d[:, 0], d[:, col] / zb, eos)
            fh.setdefault(comp, []).append(dict(mean=mean, **{str(k): abs(h[k]) for k in eos}))
    out['force_per_span'] = {c_: {key: float(np.mean([q[key] for q in v])) for key in v[0]} for c_, v in fh.items()}
    # flow check at the NGV1 / R1 interface and the outlet
    n1 = _dat('n1_exit'); n1 = n1[(n1[:, 0] >= t[0])].mean(0); pS, TS, ux, uy = n1[1], n1[2], n1[3], n1[4]
    rho = pS / (RG * TS); a_ = math.sqrt(GAM * RG * TS)
    mi = _dat('mdot_in'); mi = -mi[mi[:, 0] >= t[0], 1].mean() * N_SECT / ZSCALE        # annulus equivalent [kg/s]
    flow = dict(ngv1_exit_p=pS, ngv1_exit_T=TS, ngv1_exit_alpha=math.degrees(math.atan2(uy, ux)),
                ngv1_exit_mach=math.hypot(ux, uy) / a_, r1_beta_in=math.degrees(math.atan2(uy - U, ux)),
                r1_beta_in_design=geo['rows']['R1']['k1'], mdot_annulus_equiv=mi, mdot_meanline=A.ML['ma'] * 1.017)
    out['flow'] = flow; out['rho_a_mid'] = rho * a_
    json.dump(out, open(os.path.join(HERE, 'forcing.json'), 'w'), indent=0)
    print('flow: NGV1 exit p %.0f Pa, T %.0f K, alpha %.1f deg, Mach %.3f; R1 relative inlet %.1f deg (metal %.1f); mass flow '
          '(annulus equivalent) %.2f kg/s (meanline %.2f)' % (pS, TS, flow['ngv1_exit_alpha'], flow['ngv1_exit_mach'],
                                                           flow['r1_beta_in'], flow['r1_beta_in_design'], mi, flow['mdot_meanline']))
    for k, (rm_, mx, lo, hi, cv) in stats.items():
        print('EO%-3d blade pressure harmonic: rms %.2f kPa, max %.2f kPa (blades %.2f..%.2f rms), change between the two '
              'periods %.0f %%; tangential force %.1f N/m (steady %.0f N/m)' % (k, rm_ / 1e3, mx / 1e3, lo / 1e3, hi / 1e3,
                                                                                 100 * cv, out['force_per_span']['y'][str(k)],
                                                                                 out['force_per_span']['y']['mean']))
    print('fit residual (max over faces, rms) %.0f Pa; written %s' % (rms_res, os.path.join(HERE, 'forcing.json')))


def _internal(path, vector=False):
    txt = open(path).read(); m = re.search(r'internalField\s+nonuniform\s+List<\w+>\s*\n?(\d+)\s*\n?\(', txt)
    n = int(m.group(1)); body = txt[m.end():]
    if vector:
        return np.array(re.findall(r'\(([-\d.eE+]+) ([-\d.eE+]+) ([-\d.eE+]+)\)', body[:body.find('\n)')])[:n], float)
    return np.array(body[:body.find(')')].split()[:n], float)


def plot_field():
    """Mach number (absolute frame in the stators, relative in R1) at the latest written time, with the R1 blade-pressure
    harmonics of forcing.json -> docs/img/a1000_r1_forcing_cfd.png"""
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    tdirs = sorted((float(t), t) for t in os.listdir(os.path.join(CASE, 'processor0')) if re.match(r'^[\d.e-]+$', t) and float(t) > 0)
    tl = tdirs[-1][1]
    sh('reconstructPar -time %s -fields "(U T)"' % tl, 'log.reconstructPar')
    C = read_vectors(os.path.join(CASE, '0', 'C')); U = _internal(os.path.join(CASE, tl, 'U'), True)
    T = _internal(os.path.join(CASE, tl, 'T'))
    zt = open(os.path.join(CASE, 'constant', 'polyMesh', 'cellZones')).read()
    m = re.search(r'R1\s*\{[^}]*?cellLabels\s+List<label>\s*(\d+)\s*\(([^)]*)\)', zt, re.S)
    r1 = np.zeros(len(C), bool); r1[np.array(m.group(2).split(), int)] = True
    t = float(tl); y = C[:, 1].copy(); y[r1] += U_ROT * t; Ur = U.copy(); Ur[r1, 1] -= U_ROT
    y = (y - (-P_SECT * 1e-3 / 2)) % (P_SECT * 1e-3) - P_SECT * 1e-3 / 2              # wrap into one sector
    Ma = np.hypot(Ur[:, 0], Ur[:, 1]) / np.sqrt(GAM * RG * T)
    fc = json.load(open(os.path.join(HERE, 'forcing.json')))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6.2), dpi=110, gridspec_kw=dict(width_ratios=[1.25, 1]))
    for k in (-1, 0, 1):
        sc = a1.scatter(C[:, 0] * 1e3, (y + k * P_SECT * 1e-3) * 1e3, c=Ma, s=0.4, cmap='viridis', vmin=0, vmax=1.0, lw=0, rasterized=True)
    a1.set_xlim(X_IN, X_OUT); a1.set_ylim(-P_SECT * 0.75, P_SECT * 0.75); a1.set_aspect('equal')
    plt.colorbar(sc, ax=a1, shrink=0.8, label='Mach (absolute in NGV1 / NGV2, relative in R1)')
    a1.set_xlabel('x [mm]'); a1.set_ylabel('r theta at r = %.1f mm [mm]' % RM)
    a1.set_title('2-D mid-span URANS, t = %.3f ms: 4 NGV1 : 5 R1 (scaled) : 2 NGV2, R1 at %.0f m/s' % (t * 1e3, U_ROT), fontsize=9)
    tau = np.array(fc['tau'])
    for i, (eo, lab) in enumerate((('24', 'EO24: NGV2 potential field'), ('48', 'EO48: NGV1 wake + 2 x NGV2'),
                                   ('96', 'EO96: 2 x NGV1 wake'))):
        h = fc['harmonics'][eo]; a2.plot(tau, np.hypot(h['re'], h['im']) / 1e3, color='C%d' % i, label=lab)
    a2.axvline(0.5, color='0.6', lw=0.8); a2.text(0.5, a2.get_ylim()[1] * 0.95, ' LE', fontsize=8)
    a2.set_xlabel('R1 surface: TE 0 -> +theta (suction) side -> LE 0.5 -> -theta (pressure) side -> TE 1')
    a2.set_ylabel('harmonic amplitude of the blade pressure [kPa]'); a2.grid(alpha=0.3); a2.legend(fontsize=8)
    a2.set_title('R1 unsteady pressure (mid-span, mean of 5 blades)', fontsize=9)
    fig.tight_layout(); png = os.path.join(ROOT, 'docs', 'img', 'a1000_r1_forcing_cfd.png'); fig.savefig(png); print('written', png)


if __name__ == '__main__':
    if '--post' in sys.argv:
        post()
        if '--plot' in sys.argv: plot_field()
        sys.exit(0)
    if '--run' not in sys.argv: build()
    if '--mesh-only' in sys.argv: sys.exit(0)
    if '--run' in sys.argv:
        for st in os.environ.get('A1000_CFD_STAGE', '0,1,2').split(','): run(int(st))
