#!/usr/bin/env python3
"""AURORA-1000 exhaust diffuser + collector: steady incompressible RANS (OpenFOAM v2506, simpleFoam, k-omega SST, wall
functions), full 360 deg, three snappyHexMesh meshes for the mesh study.

Domain (sim/engine/a1000_exhaust.py GEO, rotor frame mm -> metres here): inlet annulus at the R2 exit (x 868, r 200.4 -
264.0) -> annular diffuser with the 4 cambered struts (8.5 deg casing cone, cylindrical hub) -> axial-radial bend (hub R130,
casing R35) -> radial diffuser to r 470 -> collector box (x 1110 - 1650, y -800 - 680, z -580 - 900, front and rear wells
inside r 470 are outside the gas) -> its open +y face -> 1 m straight outlet duct (outlet patch y 1680).
Fluid: flue gas at the R2 exit static state (rho, nu of a1000_exhaust.r2_exit), incompressible (inlet M 0.32: the loss
coefficient is referred to 0.5 rho c^2 of the inlet and applied to the compressible dynamic head in a1000_exhaust.py).
BCs: inlet fixed velocity profile (uniform c_x from the mass flow + the R2 section swirl, -11 to -12.5 deg), k from 7 %
turbulence, omega from a 6 mm length scale; outlet p = 0 (kinematic), inletOutlet for U / k / omega; walls no-slip + wall
functions (y+ 30-300 on the three meshes).
Meshes: background cell h0 = 32 / 24 / 18 mm (ratio 1.33); diffuser walls + region level 2, struts level 3; collector
level 0. Result: mass-averaged total-pressure drop inlet -> collector outlet flange (y 680) and to the strut exit plane.

Steps:  (local)   ~/micromamba/envs/gr180/bin/python sim/cfd/a1000_exhaust/make_case.py --write   -> case_<mesh>/ + run.sh
        (MacBook) rsync to ~/gr180_runs/a1000_exh/, ./run.sh <mesh> (gmsh STL, blockMesh, snappy, simpleFoam, post)
        (local)   rsync the small results back, make_case.py --collect   -> results.json (+ docs/img/a1000_exhaust_cfd.png)
Inside a case directory (MacBook): python make_case.py --geom | --inlet | --post   (reads geometry.json / inlet.json)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MESHES = dict(coarse=0.032, medium=0.024, fine=0.018)
ITERS = dict(coarse=1500, medium=1200, fine=1000)
NP = 6
HEADER = 'FoamFile\n{\n    version 2.0;\n    format ascii;\n    class %s;\n    object %s;\n}\n'


# ================================================================================================ local: write the cases
def write_cases():
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', 'engine')))
    import a1000_exhaust as E
    s = E.r2_exit()
    geo = dict(E.GEO, derived=E.derived(), strut_up=E.strut_section()[0], strut_lo=E.strut_section()[1])
    I = 0.07; L = 0.006
    k = 1.5 * (I * math.hypot(s['cx'], s['c_theta_mean'])) ** 2
    inlet = dict(cx=s['cx'], span=s['swirl_span'], c_theta=s['c_theta'], r_hub=E.GEO['r_hub'] * 1e-3, r_cas=E.GEO['r_cas_in'] * 1e-3,
                 nu=s['nu'], rho=s['rho'], k=k, omega=math.sqrt(k) / (0.09 ** 0.25 * L), m_kg_s=s['m_kg_s'], q_Pa=s['q_Pa'],
                 mach=s['mach'], P0_Pa=s['P0_Pa'], T0_K=s['T0_K'], area_m2=s['area_m2'])
    for name, h0 in MESHES.items():
        cd = os.path.join(HERE, 'case_' + name)
        os.makedirs(cd, exist_ok=True)
        json.dump(geo, open(os.path.join(cd, 'geometry.json'), 'w'), indent=1)
        json.dump(inlet, open(os.path.join(cd, 'inlet.json'), 'w'), indent=1)
        foam_files(cd, h0, inlet, ITERS[name], geo)
        with open(__file__) as f_in, open(os.path.join(cd, 'make_case.py'), 'w') as f_out:
            f_out.write(f_in.read())
    with open(os.path.join(HERE, 'run.sh'), 'w') as f:
        f.write(RUN_SH)
    os.chmod(os.path.join(HERE, 'run.sh'), 0o755)
    print('R2 exit: cx %.1f m/s, swirl %.1f..%.1f deg, rho %.4f, nu %.3e, k %.0f, omega %.0f -> cases %s'
          % (s['cx'], min(s['swirl_deg']), max(s['swirl_deg']), s['rho'], s['nu'], k, inlet['omega'], list(MESHES)))


def w(cd, rel, cls, body):
    p = os.path.join(cd, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(HEADER % (cls, os.path.basename(rel)) + body)


def foam_files(cd, h0, inl, n_iter, geo):
    bx = geo['box']; dd = geo['derived']
    b = dict(x0=(geo['x_in'] - 13.0) * 1e-3, x1=(bx['x1'] + 15.0) * 1e-3, y0=(bx['y0'] - 15.0) * 1e-3,
             y1=(bx['y1'] + geo['out_ext'] + 15.0) * 1e-3, z0=(bx['z0'] - 15.0) * 1e-3, z1=(bx['z1'] + 15.0) * 1e-3)
    n = [max(1, round((b[a + '1'] - b[a + '0']) / h0)) for a in 'xyz']
    w(cd, 'system/blockMeshDict', 'dictionary', '''scale 1;
vertices ( (%(x0)g %(y0)g %(z0)g) (%(x1)g %(y0)g %(z0)g) (%(x1)g %(y1)g %(z0)g) (%(x0)g %(y1)g %(z0)g)
           (%(x0)g %(y0)g %(z1)g) (%(x1)g %(y0)g %(z1)g) (%(x1)g %(y1)g %(z1)g) (%(x0)g %(y1)g %(z1)g) );
blocks ( hex (0 1 2 3 4 5 6 7) (%%d %%d %%d) simpleGrading (1 1 1) );
boundary ( background { type wall; faces ( (0 3 2 1) (4 5 6 7) (0 1 5 4) (2 3 7 6) (0 4 7 3) (1 2 6 5) ); } );
''' % b % tuple(n))
    w(cd, 'system/surfaceFeatureExtractDict', 'dictionary', '''fluid.stl
{
    extractionMethod extractFromSurface;
    includedAngle 150;
    writeObj no;
}
''')
    w(cd, 'system/snappyHexMeshDict', 'dictionary', '''castellatedMesh true;
snap true;
addLayers false;
geometry
{
    fluid.stl
    {
        type triSurfaceMesh;
        regions { inlet { name inlet; } outlet { name outlet; } struts { name struts; } diffuser { name diffuser; } collector { name collector; } }
    }
    diffZone { type searchableCylinder; point1 (0.860 0 0); point2 (%(xz)g 0 0); radius %(rz)g; }
}
castellatedMeshControls
{
    maxLocalCells 6000000;
    maxGlobalCells 12000000;
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features ( { file "fluid.eMesh"; level 2; } );
    refinementSurfaces
    {
        fluid.stl
        {
            level (0 0);
            regions
            {
                inlet { level (2 2); patchInfo { type patch; } }
                outlet { level (0 0); patchInfo { type patch; } }
                struts { level (3 3); patchInfo { type wall; } }
                diffuser { level (2 2); patchInfo { type wall; } }
                collector { level (0 1); patchInfo { type wall; } }
            }
        }
    }
    resolveFeatureAngle 30;
    refinementRegions { diffZone { mode inside; levels ((1e15 2)); } }
    locationInMesh (1.5513 -0.6987 0.7921);
    allowFreeStandingZoneFaces true;
}
snapControls
{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 60;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}
addLayersControls
{
    relativeSizes true; layers {} expansionRatio 1.2; finalLayerThickness 0.4; minThickness 0.1; nGrow 0; featureAngle 60;
    nRelaxIter 3; nSmoothSurfaceNormals 1; nSmoothNormals 3; nSmoothThickness 10; maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0; nLayerIter 50;
}
meshQualityControls
{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-18; minTetQuality 1e-15;
    minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05; minVolRatio 0.01; minTriangleTwist -1;
    nSmoothScale 4; errorReduction 0.75; relaxed { maxNonOrtho 75; }
}
mergeTolerance 1e-6;
''' % dict(xz=(dd['x_rw_exit'] + 15.0) * 1e-3, rz=(geo['r_exit'] + 15.0) * 1e-3))
    w(cd, 'system/decomposeParDict', 'dictionary', 'numberOfSubdomains %d;\nmethod scotch;\n' % NP)
    w(cd, 'system/fvSchemes', 'dictionary', '''ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; grad(U) cellLimited Gauss linear 1; grad(k) cellLimited Gauss linear 1; grad(omega) cellLimited Gauss linear 1; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) bounded Gauss limitedLinear 1;
    div(phi,omega) bounded Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.33; }
interpolationSchemes { default linear; }
snGradSchemes { default limited corrected 0.33; }
wallDist { method meshWave; }
''')
    w(cd, 'system/fvSolution', 'dictionary', '''solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent yes;
    residualControl { p 1e-5; U 1e-6; "(k|omega)" 1e-6; }
}
relaxationFactors { fields { p 0.9; } equations { U 0.7; "(k|omega)" 0.6; } }
''')
    fo = '''functions
{
    p0
    {
        type pressure; libs (fieldFunctionObjects); mode total; rho rhoInf; rhoInf 1; pRef 0; result p0;
        executeControl timeStep; executeInterval 1; writeControl writeTime;
    }
    ports
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet; operation weightedAverage;
        weightField phi; fields (p p0); writeFields false; executeControl timeStep; executeInterval 10; writeControl timeStep; writeInterval 10;
    }
    portsOut
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name outlet; operation weightedAverage;
        weightField phi; fields (p p0); writeFields false; executeControl timeStep; executeInterval 10; writeControl timeStep; writeInterval 10;
    }
    flow
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet; operation sum; fields (phi);
        writeFields false; executeControl timeStep; executeInterval 50; writeControl timeStep; writeInterval 50;
    }
    yPlus { type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }
    residuals { type solverInfo; libs (utilityFunctionObjects); fields (U p k omega); }
}
'''
    w(cd, 'system/controlDict', 'dictionary', '''application simpleFoam;
startFrom latestTime;
startTime 0;
stopAt endTime;
endTime %d;
deltaT 1;
writeControl timeStep;
writeInterval 500;
purgeWrite 2;
writeFormat binary;
writePrecision 8;
timeFormat general;
runTimeModifiable true;
%s''' % (n_iter, fo))
    w(cd, 'constant/transportProperties', 'dictionary', 'transportModel Newtonian;\nnu %.6e;\n' % inl['nu'])
    w(cd, 'constant/turbulenceProperties', 'dictionary', 'simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs off; }\n')
    walls = '"(struts|diffuser|collector)"'
    w(cd, '0.orig/U', 'volVectorField', '''dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    inlet { type fixedValue; value uniform (%g 0 0); }
    outlet { type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0); }
    %s { type noSlip; }
}
''' % (inl['cx'], walls))
    w(cd, '0.orig/p', 'volScalarField', '''dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    inlet { type zeroGradient; }
    outlet { type fixedValue; value uniform 0; }
    %s { type zeroGradient; }
}
''' % walls)
    for fld, val, wf, dim in (('k', inl['k'], 'kqRWallFunction', '[0 2 -2 0 0 0 0]'), ('omega', inl['omega'], 'omegaWallFunction', '[0 0 -1 0 0 0 0]')):
        w(cd, '0.orig/' + fld, 'volScalarField', '''dimensions %s;
internalField uniform %g;
boundaryField
{
    inlet { type fixedValue; value uniform %g; }
    outlet { type inletOutlet; inletValue uniform %g; value uniform %g; }
    %s { type %s; value uniform %g; }
}
''' % (dim, val, val, val, val, walls, wf, val))
    w(cd, '0.orig/nut', 'volScalarField', '''dimensions [0 2 -1 0 0 0 0];
internalField uniform 0;
boundaryField
{
    inlet { type calculated; value uniform 0; }
    outlet { type calculated; value uniform 0; }
    %s { type nutkWallFunction; value uniform 0; }
}
''' % walls)
    planes = ''.join('''    %s { type cuttingPlane; planeType pointAndNormal; pointAndNormalDict { point (%g %g %g); normal (%g %g %g); } interpolate true; }
''' % q for q in (('x0900', 0.900, 0, 0, 1, 0, 0), ('x1000', 1.000, 0, 0, 1, 0, 0), ('x1148', 1.148, 0, 0, 1, 0, 0),
                  ('y0', 0, 0, 0, 0, 1, 0), ('z0', 0, 0, 0, 0, 0, 1), ('xbox', 1.38, 0, 0, 1, 0, 0)))
    w(cd, 'system/sampleDict', 'dictionary', '''type surfaces;
libs (sampling);
surfaceFormat raw;
fields (p p0 U k);
surfaces
{
%s}
''' % planes)


RUN_SH = r'''#!/bin/bash
# AURORA-1000 exhaust CFD on the MacBook: ./run.sh <coarse|medium|fine> [map_from_case]
set -e
M=$1; MAP=$2
cd "$(dirname "$0")/case_$M"
OF=~/Applications/OpenFOAM-v2506.app/Contents/Resources/etc/openfoam
PY=~/micromamba/envs/gr180/bin/python
of() { $OF -c "$1" > "log.$2" 2>&1; }
date > log.start
if [ ! -f constant/polyMesh/owner ]; then
  $PY make_case.py --geom > log.geom 2>&1
  of "surfaceFeatureExtract" surfaceFeatureExtract
  of "blockMesh" blockMesh
  of "decomposePar -force" decomposePar.mesh
  of "mpirun -np 6 snappyHexMesh -overwrite -parallel" snappyHexMesh
  of "reconstructParMesh -constant" reconstructParMesh
  rm -rf processor*
  of "checkMesh -constant" checkMesh
fi
rm -rf 0 processor*; cp -r 0.orig 0
of "foamDictionary -entry writeFormat -set ascii system/controlDict" fd1
if [ -n "$MAP" ]; then of "mapFields ../case_$MAP -consistent -sourceTime latestTime" mapFields; fi
of "postProcess -func writeCellCentres -time 0" cellCentres
$PY make_case.py --inlet > log.inlet 2>&1
of "foamDictionary -entry writeFormat -set binary system/controlDict" fd2
of "decomposePar -force" decomposePar
of "mpirun -np 6 simpleFoam -parallel" simpleFoam
of "reconstructPar -latestTime" reconstructPar
rm -rf processor*
of "postProcess -func sampleDict -latestTime" sample
$OF -c "simpleFoam -postProcess -func yPlus -latestTime" > log.yPlus 2>&1 || true
$PY make_case.py --post > log.post 2>&1
date > log.end
'''


# ================================================================================================ MacBook: geometry (gmsh OCC)
def make_geometry():
    """fluid volume from geometry.json with gmsh OCC (mm), surface mesh -> constant/triSurface/fluid.stl (m) with the
    regions inlet / outlet / struts / diffuser / collector"""
    import gmsh
    g = json.load(open('geometry.json')); d = g['derived']; s = g['struts']; bx = g['box']
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 1)
    occ = gmsh.model.occ
    pts = []
    def P(x, r): t = occ.addPoint(x, 0, r); pts.append(t); return t
    a = math.radians(g['cone_deg'])
    p1 = P(g['x_in'], g['r_hub']); p2 = P(g['x_bend'], g['r_hub'])
    hc = P(*d['hub_c']); p3 = P(d['x_rw'], d['r_rw0'])
    p4 = P(d['x_rw_exit'], g['r_exit']); p5 = P(d['x_fw'], g['r_exit']); p6 = P(d['x_fw'], d['r_fw0'])
    cc = P(*d['cas_c']); p7 = P(d['x_cb'], d['r_cb']); p8 = P(g['x_in'], g['r_cas_in'])
    lines = [occ.addLine(p1, p2), occ.addCircleArc(p2, hc, p3), occ.addLine(p3, p4), occ.addLine(p4, p5), occ.addLine(p5, p6),
             occ.addCircleArc(p6, cc, p7), occ.addLine(p7, p8), occ.addLine(p8, p1)]
    surf = occ.addPlaneSurface([occ.addCurveLoop(lines)])
    dif = occ.revolve([(2, surf)], 0, 0, 0, 1, 0, 0, 2 * math.pi)
    dif = [e for e in dif if e[0] == 3]
    struts = []
    sec = g['strut_up'] + g['strut_lo'][::-1][:-1]                 # LE -> TE (upper), TE -> LE (lower)
    for k in range(s['n']):
        ph = math.radians(s['theta0'] + 360.0 * k / s['n'])
        er = (0, math.cos(ph), math.sin(ph)); et = (0, -math.sin(ph), math.cos(ph))
        tags = [occ.addPoint(x, s['r_in'] * er[1] + q * et[1], s['r_in'] * er[2] + q * et[2]) for x, q in sec]
        sp = occ.addSpline(tags + [tags[0]])
        sf = occ.addPlaneSurface([occ.addCurveLoop([sp])])
        ex = occ.extrude([(2, sf)], 0, (s['r_out'] - s['r_in']) * er[1], (s['r_out'] - s['r_in']) * er[2])
        struts += [e for e in ex if e[0] == 3]
    dif, _ = occ.cut(dif, struts)
    box = occ.addBox(bx['x0'], bx['y0'], bx['z0'], bx['x1'] - bx['x0'], bx['y1'] - bx['y0'], bx['z1'] - bx['z0'])
    core = occ.addCylinder(bx['x0'] - 10, 0, 0, bx['x1'] - bx['x0'] + 20, 0, 0, g['r_exit'])
    col, _ = occ.cut([(3, box)], [(3, core)])
    ext = occ.addBox(bx['x0'], bx['y1'], bx['z0'], bx['x1'] - bx['x0'], g['out_ext'], bx['z1'] - bx['z0'])
    fl, _ = occ.fuse(dif, col + [(3, ext)])
    occ.synchronize()
    gmsh.model.occ.removeAllDuplicates(); occ.synchronize()
    vols = gmsh.model.getEntities(3)
    print('volumes', vols, [occ.getMass(3, v[1]) * 1e-9 for v in vols])
    reg = {}
    for dim, tag in gmsh.model.getBoundary(vols, oriented=False):
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, tag)
        if xmax - xmin < 1e-3 and abs(xmin - g['x_in']) < 0.5: name = 'inlet'
        elif ymax - ymin < 1e-3 and abs(ymin - bx['y1'] - g['out_ext']) < 0.5: name = 'outlet'
        elif xmin > s['x_le'] - 2 and xmax < s['x_le'] + s['chord'] + 2 and max(ymax - ymin, zmax - zmin) < 200: name = 'struts'
        elif xmax < d['x_rw_exit'] + 1 and max(abs(ymin), abs(ymax), abs(zmin), abs(zmax)) < g['r_exit'] + 1: name = 'diffuser'
        else: name = 'collector'
        reg.setdefault(name, []).append(tag)
    print({k: len(v) for k, v in reg.items()})
    for name, tags in reg.items():
        size = dict(struts=3.0, diffuser=6.0, inlet=6.0).get(name, 25.0)
        for t in tags:
            gmsh.model.mesh.setSize(gmsh.model.getBoundary([(2, t)], recursive=True), size)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 36)
    gmsh.option.setNumber('Mesh.MeshSizeMax', 25.0); gmsh.option.setNumber('Mesh.MeshSizeMin', 1.5)
    gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 1)
    gmsh.model.mesh.generate(2)
    os.makedirs('constant/triSurface', exist_ok=True)
    with open('constant/triSurface/fluid.stl', 'w') as f:
        for name, tags in reg.items():
            f.write('solid %s\n' % name); nt = 0
            for t in tags:
                nodes, coords, _ = gmsh.model.mesh.getNodes(2, t, includeBoundary=True)
                xyz = {int(n): coords[3 * i:3 * i + 3] for i, n in enumerate(nodes)}
                types, _, conn = gmsh.model.mesh.getElements(2, t)
                for ty, cn in zip(types, conn):
                    if ty != 2: continue
                    for i in range(0, len(cn), 3):
                        A, B, C = (xyz[int(cn[i + j])] for j in range(3))
                        u = [B[j] - A[j] for j in range(3)]; v = [C[j] - A[j] for j in range(3)]
                        nn = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                        L = math.sqrt(sum(c * c for c in nn)) or 1.0
                        f.write(' facet normal %g %g %g\n  outer loop\n' % tuple(c / L for c in nn))
                        for q in (A, B, C): f.write('   vertex %.7g %.7g %.7g\n' % tuple(c * 1e-3 for c in q))
                        f.write('  endloop\n endfacet\n'); nt += 1
            f.write('endsolid %s\n' % name); print(name, nt, 'triangles')
    gmsh.finalize()


# ================================================================================================ MacBook: inlet profile
def read_patch_vectors(path, patch):
    """ascii volVectorField: the nonuniform value list of one patch"""
    import re
    txt = open(path).read()
    i = re.search(r'\n\s*%s\s*\n\s*\{' % patch, txt[txt.index('boundaryField'):]).end() + txt.index('boundaryField')
    m = re.compile(r'List<vector>\s*(\d+)\s*\(').search(txt, i)
    n = int(m.group(1))
    vals = re.findall(r'\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)', txt[m.end():m.end() + 80 * n + 1000])[:n]
    return [[float(v) for v in t] for t in vals]


def set_inlet():
    """0/U inlet: c_x uniform, c_theta(span) from the R2 sections (+theta from +y to +z)"""
    inl = json.load(open('inlet.json'))
    C = read_patch_vectors('0/C', 'inlet')
    sp, ct = inl['span'], inl['c_theta']
    def interp(s):
        s = min(max(s, sp[0]), sp[-1])
        for (s0, c0), (s1, c1) in zip(zip(sp, ct), zip(sp[1:], ct[1:])):
            if s0 <= s <= s1: return c0 + (c1 - c0) * (s - s0) / (s1 - s0)
        return ct[-1]
    rows = []
    for x, y, z in C:
        r = math.hypot(y, z); s = (r - inl['r_hub']) / (inl['r_cas'] - inl['r_hub']); c = interp(s)
        rows.append('(%.6g %.6g %.6g)' % (inl['cx'], -c * z / r, c * y / r))
    txt = open('0/U').read()
    i = txt.index('inlet', txt.index('boundaryField')); j = txt.index('}', i)
    new = 'inlet { type fixedValue; value nonuniform List<vector> %d (%s); }' % (len(rows), ' '.join(rows))
    open('0/U', 'w').write(txt[:i] + new + txt[j + 1:])
    print('inlet faces', len(rows))


# ================================================================================================ MacBook: post
def last_dat(fo):
    base = os.path.join('postProcessing', fo)
    times = sorted(os.listdir(base), key=float)
    rows = []
    for t in times:
        for fn in os.listdir(os.path.join(base, t)):
            if fn.endswith('.dat'):
                for line in open(os.path.join(base, t, fn)):
                    if line.startswith('#') or not line.strip(): continue
                    rows.append([float(v) for v in line.replace('(', ' ').replace(')', ' ').split()])
    return rows


def raw_planes(t=None):
    """sampleDict output of one time: {surface: {field: array (x y z values...)}} from <field>_<surface>.raw"""
    import numpy as np
    base = 'postProcessing/sampleDict'; t = t or sorted(os.listdir(base), key=float)[-1]; out = {}
    for fn in os.listdir(os.path.join(base, t)):
        if not fn.endswith('.raw'): continue
        fld, surf = fn[:-4].split('_', 1)
        out.setdefault(surf, {})[fld] = np.loadtxt(os.path.join(base, t, fn), comments='#')
    return out


def stations(g, q, t=None):
    """x planes in the annulus: Delaunay-triangulated cut-plane points (triangles across the struts / hub removed by
    edge length and radius), flux-weighted p0 and p, swirl angle, reverse-flow area fraction"""
    import numpy as np
    from scipy.spatial import Delaunay
    res = {}
    for surf, f in raw_planes(t).items():
        if not surf.startswith('x') or 'U' not in f: continue
        U = f['U']; y, z = U[:, 1], U[:, 2]; r = np.hypot(y, z)
        p0 = f['p0'][:, 3]; p = f['p'][:, 3]; ux, uy, uz = U[:, 3], U[:, 4], U[:, 5]
        x = float(U[0, 0]) * 1e3
        r_out = (g['r_cas_in'] + (x - g['x_in']) * math.tan(math.radians(g['cone_deg']))) * 1e-3 if x < g['x_bend'] + 5 else g['r_exit'] * 1e-3
        tri = Delaunay(np.c_[y, z]); T = tri.simplices
        P = np.c_[y, z][T]
        e = np.max([np.linalg.norm(P[:, a] - P[:, b], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)
        rc = np.hypot(P[:, :, 0].mean(1), P[:, :, 1].mean(1))
        h = np.median(e)
        keep = (e < 4 * h) & (rc > g['r_hub'] * 1e-3) & (rc < r_out)
        T, P = T[keep], P[keep]
        A = 0.5 * np.abs((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
        m = lambda v: v[T].mean(1)
        uxm = m(ux); yc, zc = P[:, :, 0].mean(1), P[:, :, 1].mean(1); rcc = np.hypot(yc, zc)
        ut = (-m(uy) * zc + m(uz) * yc) / rcc
        w = uxm * A
        res[surf] = dict(x_mm=x, area_m2=float(A.sum()), Q_m3s=float(w.sum()), p0=float((m(p0) * w).sum() / w.sum()),
                         p=float((m(p) * A).sum() / A.sum()), swirl_deg=float(np.degrees(np.arctan2((ut * w).sum(), (uxm * w).sum()))),
                         reverse_area=float(A[uxm < 0].sum() / A.sum()), n_tri=int(len(T)))
        res[surf]['zeta_from_inlet'] = None
    return res


def post():
    inl = json.load(open('inlet.json')); g = json.load(open('geometry.json'))
    a, b = last_dat('ports'), last_dat('portsOut')
    q = 0.5 * (inl['cx'] ** 2 + (sum(inl['c_theta']) / len(inl['c_theta'])) ** 2)
    hist = [(ra[0], (ra[2] - rb[2]) / q) for ra, rb in zip(a, b)]
    n = max(1, int(0.3 * len(hist))); tail = [h[1] for h in hist[-n:]]       # steady RANS oscillates: mean of the last 30 %
    zeta = sum(tail) / len(tail)
    res = dict(iterations=hist[-1][0], zeta_total=zeta, zeta_last=hist[-1][1], zeta_tail_min=min(tail), zeta_tail_max=max(tail), q_kin=q,
               p_in=a[-1][1], p0_in=a[-1][2], p_out=b[-1][1], p0_out=b[-1][2], cp_static=(b[-1][1] - a[-1][1]) / q,
               zeta_history=hist[::max(1, len(hist) // 60)])
    fl = last_dat('flow'); res['Q_inlet_m3_s'] = -fl[-1][1]
    import re
    cm = open('log.checkMesh').read(); res['cells'] = int(re.search(r'cells:\s+(\d+)', cm).group(1))
    res['mesh_ok'] = 'Mesh OK' in cm
    try:
        yp = open('log.yPlus').read()
        res['yplus'] = {m.group(1): dict(min=float(m.group(2)), max=float(m.group(3)), avg=float(m.group(4)))
                        for m in re.finditer(r'patch (\w+) y\+ : min = ([\d.eE+-]+), max = ([\d.eE+-]+), average = ([\d.eE+-]+)', yp)}
    except Exception:
        res['yplus'] = {}
    res['stations'] = stations(g, q)
    for v in res['stations'].values(): v['zeta_from_inlet'] = (res['p0_in'] - v['p0']) / q
    json.dump(res, open('result.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'zeta_history'}, indent=1))


def plot(fn='exhaust_cfd.png'):
    """MacBook, in a finished case: |U| on the y = 0 (x-z) and z = 0 (x-y) planes with the gas-path outline"""
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    g = json.load(open('geometry.json')); inl = json.load(open('inlet.json')); d = g['derived']; bx = g['box']
    pl = raw_planes()
    def prof():
        a = math.radians(g['cone_deg']); P = [(g['x_in'], g['r_hub']), (g['x_bend'], g['r_hub'])]
        hx, hr = d['hub_c']; P += [(hx + g['R_hub'] * math.sin(t), hr - g['R_hub'] * math.cos(t)) for t in np.linspace(0, math.pi / 2, 30)[1:]]
        P += [(d['x_rw_exit'], g['r_exit'])]
        C = [(g['x_in'], g['r_cas_in']), (d['x_cb'], d['r_cb'])]
        cx, cr = d['cas_c']; C += [(cx + g['R_cas'] * math.sin(t), cr - g['R_cas'] * math.cos(t)) for t in np.linspace(a, math.pi / 2, 30)[1:]]
        C += [(d['x_fw'], g['r_exit'])]
        return np.array(P), np.array(C)
    H, C = prof()
    fig, ax = plt.subplots(1, 2, figsize=(13, 7.2), dpi=110)
    for a_, (surf, i, j, lab) in zip(ax, (('y0', 0, 2, 'z'), ('z0', 0, 1, 'y'))):
        U = pl[surf]['U']; X, Y = U[:, i] * 1e3, U[:, j] * 1e3; mag = np.linalg.norm(U[:, 3:6], axis=1)
        tri = mtri.Triangulation(X, Y)
        P = np.c_[X, Y][tri.triangles]
        e = np.max([np.linalg.norm(P[:, k] - P[:, (k + 1) % 3], axis=1) for k in range(3)], axis=0)
        xc, yc = P[:, :, 0].mean(1), np.abs(P[:, :, 1].mean(1))
        inner = (xc < d['x_rw_exit'] + 5) & (yc < g['r_exit'] + 5)          # gas path: fine cells, struts / walls nearby
        tri.set_mask(np.where(inner, e > 30.0, e > 140.0))
        cs = a_.tricontourf(tri, mag, levels=np.linspace(0, 220, 23), cmap='viridis', extend='max')
        for sgn in (1, -1):
            a_.plot(H[:, 0], sgn * H[:, 1], 'w-', lw=1.2); a_.plot(C[:, 0], sgn * C[:, 1], 'w-', lw=1.2)
        a_.plot([bx['x0'], bx['x1'], bx['x1'], bx['x0'], bx['x0']], [bx[lab + '0'], bx[lab + '0'], bx[lab + '1'], bx[lab + '1'], bx[lab + '0']], 'w--', lw=0.8)
        a_.set_aspect('equal'); a_.set_xlabel('x [mm] (engine axis)'); a_.set_ylabel(lab + ' [mm]')
        a_.set_xlim(850, bx['x1'] + 20 if lab == 'z' else bx['x1'] + 20)
        a_.set_ylim(bx[lab + '0'] - 20, bx[lab + '1'] + (20 if lab == 'z' else 450))
    ax[0].set_title('y = 0: R2 exit -> struts (top / bottom) -> bend -> radial diffuser -> collector', fontsize=9)
    ax[1].set_title('z = 0: struts at +-y, collector outlet +y (recuperator side) -> 1 m duct', fontsize=9)
    fig.colorbar(cs, ax=ax, shrink=0.8, label='|U| [m/s]  (inlet c = %.0f m/s)' % math.hypot(inl['cx'], sum(inl['c_theta']) / len(inl['c_theta'])))
    fig.savefig(fn, bbox_inches='tight'); print('wrote', fn)


def collect():
    """local: fetch result.json of every finished mesh from the MacBook, assemble results.json"""
    import subprocess
    out = dict(design='B (hub R180 / casing R120 bend, radial diffuser to r 500)', meshes={},
               design_A_coarse=dict(note='first design: hub R130 / casing R35 bend, r_exit 470, coarse mesh 325k cells; '
                                         'separation at the convex casing corner, jet along the rear wall',
                                    zeta_mean=0.537, zeta_min=0.518, zeta_max=0.558, zeta_to_strut_exit=0.069, cp_strut_exit=0.378),
               design_C_coarse=dict(note='third design: B with a constant-area bend (casing R114, width 66 mm, parallel radial '
                                         'walls, AR 2.2), coarse mesh 333k cells: flow better attached, smaller exit area -> more dump loss',
                                    zeta_mean=0.483, zeta_min=0.461, zeta_max=0.496))
    for m in MESHES:
        cd = os.path.join(HERE, 'case_' + m)
        subprocess.run(['rsync', '-a', 'macbook:gr180_runs/a1000_exh/case_%s/result.json' % m, cd + '/'], capture_output=True)
        f = os.path.join(cd, 'result.json')
        if os.path.exists(f):
            r = json.load(open(f)); r.pop('zeta_history', None); out['meshes'][m] = r
    json.dump(out, open(os.path.join(HERE, 'results.json'), 'w'), indent=1)
    for m, r in out['meshes'].items():
        print('%-7s cells %8d  zeta %.4f (last 30 %%: %.4f..%.4f)  it %d' % (m, r['cells'], r['zeta_total'], r['zeta_tail_min'],
                                                                           r['zeta_tail_max'], r['iterations']))


if __name__ == '__main__':
    if '--collect' in sys.argv: collect()
    elif '--write' in sys.argv: write_cases()
    elif '--geom' in sys.argv: make_geometry()
    elif '--inlet' in sys.argv: set_inlet()
    elif '--post' in sys.argv: post()
    elif '--plot' in sys.argv: plot()
