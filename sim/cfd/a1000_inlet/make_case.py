#!/usr/bin/env python3
"""AURORA-1000 air inlet: steady incompressible RANS (OpenFOAM v2506, simpleFoam, k-omega SST, wall functions) of the
plenum, the radial slot with the 4 front-bearing struts, the bend and the bellmouth to the impeller-1 eye; full 360 deg,
three snappyHexMesh meshes for the mesh study and coarse-mesh design variants.

Domain (sim/engine/a1000_inlet.py GEO, rotor frame mm -> metres here): uniform inflow at the top of a 400 mm duct stub on
the filter-house flange -> plenum box (x -140..204, y +-540, z -620..600) round the dry tunnel (r 290, open to the front,
not meshed) -> front lip R40 -> radial slot x 157..204 with the 4 struts (45 / 135 / 225 / 315 deg) -> bend (hub: FB
fairing, shroud: bellmouth corner) -> eye annulus r 60..137.5 (no blades), straight to the outlet at x 400.
Fluid: humid air at the eye static density (incompressible; zeta is referred to 0.5 c^2 of the bulk eye velocity and applied
to the compressible eye head in a1000_inlet.py).
BCs: inlet fixed uniform velocity, 5 % turbulence, 50 mm length scale (filter-house wake); outlet p = 0 (kinematic),
inletOutlet for U / k / omega; walls no-slip + wall functions.
Meshes: background h0 = 28 / 21 / 15.75 mm (ratio 1.33); slot + bend region level 3, bend / eye walls and struts level 4,
plenum walls level 1.
Result: mass-averaged total-pressure loss inlet -> eye plane (x 215, impeller LE) and at the slot entry (r 270) and after
the struts (r 152); at the eye: DC60, swirl angle by sector, radial profiles, axial-velocity uniformity.

Steps:  (local) ~/micromamba/envs/gr180/bin/python sim/cfd/a1000_inlet/make_case.py --write [design] [meshes]
                -> case_<design>_<mesh>/ + run.sh  (design A, B, ... of a1000_inlet.DESIGNS; meshes coarse,medium,fine)
        (vast)  rsync to /root/runs/a1000_inl/, OF=openfoam2506 PY=python3 NP=32 ./run.sh <design>_<mesh>
        (local) rsync the small results back, make_case.py --collect   -> results.json (+ docs/img/a1000_inlet_cfd.png)
Inside a case directory: python make_case.py --geom | --post | --plot   (reads geometry.json / inlet.json)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MESHES = dict(coarse=0.028, medium=0.021, fine=0.01575)
ITERS = dict(coarse=1500, medium=1500, fine=1200)                 # fine: mapped from the medium result
NP = 32
HEADER = 'FoamFile\n{\n    version 2.0;\n    format ascii;\n    class %s;\n    object %s;\n}\n'


# ================================================================================================ local: write the cases
def write_cases(design='A', meshes=None):
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', 'engine')))
    import a1000_inlet as E
    g = E.DESIGNS[design]
    a = E.air_state(); fh = E.filter_house()
    e = E.eye_state(a['P_atm'] - fh['total']['design_Pa'], a)
    b = g['box']
    Q = a['m'] / e['rho']; A_in = (b['x1'] - b['x0']) * (b['y1'] - b['y0']) * 1e-6
    I, L = 0.05, 0.05; U = Q / A_in
    k = 1.5 * (I * U) ** 2
    A_eye = a['A_eye']
    inlet = dict(U=U, Q=Q, nu=e['nu'], rho=e['rho'], k=k, omega=math.sqrt(k) / (0.09 ** 0.25 * L), m_kg_s=a['m'],
                 A_eye=A_eye, c_eye=Q / A_eye, q_eye_kin=0.5 * (Q / A_eye) ** 2, q_comp_Pa=e['q_comp'], M_eye=e['M'], design=design)
    geo = dict(g, shroud=E.shroud_profile(g), hub_path=E.hub_profile(g), strut_up=E.strut_section(g)[0])
    if g.get('ring'): geo['ring_path'] = E.ring_section(g)
    for name in (meshes or list(MESHES)):
        cd = os.path.join(HERE, 'case_%s_%s' % (design, name))
        os.makedirs(cd, exist_ok=True)
        json.dump(geo, open(os.path.join(cd, 'geometry.json'), 'w'), indent=1)
        json.dump(inlet, open(os.path.join(cd, 'inlet.json'), 'w'), indent=1)
        foam_files(cd, MESHES[name], inlet, ITERS[name], geo)
        with open(__file__) as f_in, open(os.path.join(cd, 'make_case.py'), 'w') as f_out:
            f_out.write(f_in.read())
    with open(os.path.join(HERE, 'run.sh'), 'w') as f:
        f.write(RUN_SH)
    os.chmod(os.path.join(HERE, 'run.sh'), 0o755)
    print('design %s: inflow %.2f m/s (Q %.3f m3/s at rho %.4f), eye bulk c %.1f m/s, nu %.3e, k %.3f, omega %.1f -> %s'
          % (design, U, Q, e['rho'], Q / A_eye, e['nu'], k, inlet['omega'], meshes or list(MESHES)))


def w(cd, rel, cls, body):
    p = os.path.join(cd, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(HEADER % (cls, os.path.basename(rel)) + body)


def foam_files(cd, h0, inl, n_iter, geo):
    bx = geo['box']
    b = dict(x0=(bx['x0'] - 13.0) * 1e-3, x1=(geo['x_out'] + 13.0) * 1e-3, y0=(bx['y0'] - 13.0) * 1e-3,
             y1=(bx['y1'] + 13.0) * 1e-3, z0=(bx['z0'] - 13.0) * 1e-3, z1=(bx['z1'] + geo['duct_ext'] + 13.0) * 1e-3)
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
    r_slot = (geo['R_T'] + 10.0) * 1e-3
    w(cd, 'system/snappyHexMeshDict', 'dictionary', '''castellatedMesh true;
snap true;
addLayers false;
geometry
{
    fluid.stl
    {
        type triSurfaceMesh;
        regions { inlet { name inlet; } outlet { name outlet; } struts { name struts; } bend { name bend; } casing { name casing; } plenum { name plenum; } }
    }
    slotZone { type searchableCylinder; point1 (%(xs0)g 0 0); point2 (%(xs1)g 0 0); radius %(rs)g; }
    eyeZone { type searchableCylinder; point1 (0.150 0 0); point2 (%(xo)g 0 0); radius 0.160; }
}
castellatedMeshControls
{
    maxLocalCells 8000000;
    maxGlobalCells 30000000;
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features ( { file "fluid.eMesh"; level 3; } );
    refinementSurfaces
    {
        fluid.stl
        {
            level (1 1);
            regions
            {
                inlet { level (1 1); patchInfo { type patch; } }
                outlet { level (3 3); patchInfo { type patch; } }
                struts { level (4 4); patchInfo { type wall; } }
                bend { level (4 4); patchInfo { type wall; } }
                casing { level (3 3); patchInfo { type wall; } }
                plenum { level (1 1); patchInfo { type wall; } }
            }
        }
    }
    resolveFeatureAngle 30;
    refinementRegions { slotZone { mode inside; levels ((1e15 3)); } eyeZone { mode inside; levels ((1e15 3)); } }
    locationInMesh (0.0313 0.0117 0.4513);
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
''' % dict(xs0=(geo['x_hub'] - geo['R_lip'] - 10.0) * 1e-3, xs1=(geo['x_shr'] + 5.0) * 1e-3, rs=r_slot, xo=(geo['x_out'] + 5.0) * 1e-3))
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
    eye
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType sampledSurface; name eyePlane;
        sampledSurfaceDict { type cuttingPlane; planeType pointAndNormal; pointAndNormalDict { point (%(xle)g 0 0); normal (1 0 0); } interpolate false; }
        operation weightedAreaAverage; weightField U; fields (p0 p); writeFields false;
        executeControl timeStep; executeInterval 10; writeControl timeStep; writeInterval 10;
    }
    flow
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet; operation sum; fields (phi);
        writeFields false; executeControl timeStep; executeInterval 50; writeControl timeStep; writeInterval 50;
    }
    yPlus { type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }
    residuals { type solverInfo; libs (utilityFunctionObjects); fields (U p k omega); }
}
''' % dict(xle=geo['x_le'] * 1e-3)
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
    walls = '"(struts|bend|casing|plenum)"'
    w(cd, '0.orig/U', 'volVectorField', '''dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    inlet { type fixedValue; value uniform (0 0 %g); }
    outlet { type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0); }
    %s { type noSlip; }
}
''' % (-inl['U'], walls))
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
    xs = 0.5 * (geo['x_hub'] + geo['x_shr']) * 1e-3
    planes = ''.join('''    %s { type cuttingPlane; planeType pointAndNormal; pointAndNormalDict { point (%g %g %g); normal (%g %g %g); } interpolate true; }
''' % q for q in (('x%03d' % geo['x_le'], geo['x_le'] * 1e-3, 0, 0, 1, 0, 0), ('x212', 0.212, 0, 0, 1, 0, 0),
                  ('x260', 0.260, 0, 0, 1, 0, 0), ('xslot', xs, 0, 0, 1, 0, 0), ('xplen', 0.030, 0, 0, 1, 0, 0),
                  ('y0', 0, 0, 0, 0, 1, 0), ('z0', 0, 0, 0, 0, 0, 1)))
    cyl = ''.join('''    %s { type distanceSurface; distance 0; signed true; cell false; surfaceType searchableCylinder; surfaceName %s;
          point1 (%g 0 0); point2 (%g 0 0); radius %g; }
''' % (nm, nm, (geo['x_hub'] - 5.0) * 1e-3, (geo['x_shr'] + 5.0) * 1e-3, r * 1e-3) for nm, r in (('r270', 270.0), ('r152', 152.0)))
    w(cd, 'system/sampleDict', 'dictionary', '''type surfaces;
libs (sampling);
surfaceFormat raw;
fields (p p0 U k);
surfaces
{
%s%s}
''' % (planes, cyl))


RUN_SH = r'''#!/bin/bash
# AURORA-1000 inlet CFD: ./run.sh <design>_<mesh> [map_from_case]   e.g. ./run.sh A_coarse
# on the vast node: OF=openfoam2506 PY=python3 NP=32 ./run.sh A_medium A_coarse
set -e
M=$1; MAP=$2
cd "$(dirname "$0")/case_$M"
OF=${OF:-openfoam2506}
PY=${PY:-python3}
NP=${NP:-32}
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
of() { $OF -c "$1" > "log.$2" 2>&1; }
perl -pi -e "s/^numberOfSubdomains .*/numberOfSubdomains $NP;/" system/decomposeParDict
date > log.start
if [ ! -f constant/polyMesh/owner ]; then
  $PY make_case.py --geom > log.geom 2>&1
  of "surfaceFeatureExtract" surfaceFeatureExtract
  of "blockMesh" blockMesh
  of "decomposePar -force" decomposePar.mesh
  of "mpirun -np $NP snappyHexMesh -overwrite -parallel" snappyHexMesh
  of "reconstructParMesh -constant" reconstructParMesh
  rm -rf processor*
  of "checkMesh -constant" checkMesh
fi
rm -rf 0 processor*; cp -r 0.orig 0
if [ -n "$MAP" ]; then
  of "foamDictionary -entry writeFormat -set ascii system/controlDict" fd1
  of "mapFields ../case_$MAP -consistent -sourceTime latestTime" mapFields
  of "foamDictionary -entry writeFormat -set binary system/controlDict" fd2
fi
of "decomposePar -force" decomposePar
of "mpirun -np $NP simpleFoam -parallel" simpleFoam
of "reconstructPar -latestTime" reconstructPar
rm -rf processor*
of "postProcess -func sampleDict -latestTime" sample
$OF -c "simpleFoam -postProcess -func yPlus -latestTime" > log.yPlus 2>&1 || true
$PY make_case.py --post > log.post 2>&1
date > log.end
'''


# ================================================================================================ node: geometry (gmsh OCC)
def make_geometry():
    """fluid volume from geometry.json with gmsh OCC (mm), surface mesh -> constant/triSurface/fluid.stl (m) with the
    regions inlet / outlet / struts / bend / casing / plenum"""
    import gmsh
    g = json.load(open('geometry.json')); bx = g['box']; s = g['struts']
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 1)
    occ = gmsh.model.occ

    def revolve(poly):
        """closed (x, r) polygon -> solid of revolution about x (straight segments; arcs are finely sampled)"""
        tags = [occ.addPoint(x, 0, r) for x, r in poly]
        lines = [occ.addLine(tags[i], tags[(i + 1) % len(tags)]) for i in range(len(tags))]
        sf = occ.addPlaneSurface([occ.addCurveLoop(lines)])
        return [e for e in occ.revolve([(2, sf)], 0, 0, 0, 1, 0, 0, 2 * math.pi) if e[0] == 3]

    box = occ.addBox(bx['x0'], bx['y0'], bx['z0'], bx['x1'] - bx['x0'], bx['y1'] - bx['y0'], bx['z1'] - bx['z0'])
    duct = occ.addBox(bx['x0'], bx['y0'], bx['z1'], bx['x1'] - bx['x0'], bx['y1'] - bx['y0'], g['duct_ext'])
    sh = [tuple(p) for p in g['shroud']][1:]                          # corner start on the radial wall ... LE
    eye = revolve([(g['x_shr'], 0.0)] + sh + [(g['x_out'], g['r_eye_shr']), (g['x_out'], 0.0)])
    hp = [tuple(p) for p in g['hub_path']]
    hub = revolve([(bx['x0'] - 10.0, 0.0), (bx['x0'] - 10.0, g['R_T'])] + hp[1:] + [(g['x_out'] + 10.0, g['r_eye_hub']),
                                                                                    (g['x_out'] + 10.0, 0.0)])
    cut = hub
    sec = [tuple(p) for p in g['strut_up']]
    sec = sec + [(r, -q) for r, q in sec[::-1][1:-1]]                 # LE -> TE (upper), TE -> LE (lower)
    for k in range(s['n']):
        ph = math.radians(s['theta0'] + 360.0 * k / s['n'])
        er = (math.cos(ph), math.sin(ph)); et = (-math.sin(ph), math.cos(ph))
        x0 = g['x_hub'] - 3.0
        tags = [occ.addPoint(x0, r * er[0] + q * et[0], r * er[1] + q * et[1]) for r, q in sec]
        sp = occ.addSpline(tags + [tags[0]])
        sf = occ.addPlaneSurface([occ.addCurveLoop([sp])])
        cut += [e for e in occ.extrude([(2, sf)], g['x_shr'] - g['x_hub'] + 6.0, 0, 0) if e[0] == 3]
    if g.get('ring_path'):
        cut += revolve([tuple(p) for p in g['ring_path']])
    if g.get('splitter'):
        t = g['splitter']['t']
        z_top = -(g['R_T'] - g['R_lip']) - 4.0                         # up to the slot entry radius (under the tunnel / lip)
        cut.append((3, occ.addBox(bx['x0'] - 1.0, -0.5 * t, bx['z0'] - 1.0, g['x_shr'] - bx['x0'] + 2.0, t, z_top - bx['z0'] + 1.0)))
    fl, _ = occ.fuse([(3, box)], [(3, duct)] + eye)
    fl, _ = occ.cut(fl, cut)
    occ.synchronize()
    occ.removeAllDuplicates(); occ.synchronize()
    vols = gmsh.model.getEntities(3)
    print('volumes', vols, [occ.getMass(3, v[1]) * 1e-9 for v in vols])
    reg = {}
    ztop = bx['z1'] + g['duct_ext']
    rb = [tuple(p) for p in g.get('ring_path', [])]
    rx0, rx1, rr1 = (min(p[0] for p in rb), max(p[0] for p in rb), max(p[1] for p in rb)) if rb else (0, 0, 0)
    for dim, tag in gmsh.model.getBoundary(vols, oriented=False):
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, tag)
        rmax = max(abs(ymin), abs(ymax), abs(zmin), abs(zmax))
        if zmax - zmin < 1e-3 and abs(zmin - ztop) < 0.5: name = 'inlet'
        elif xmax - xmin < 1e-3 and abs(xmin - g['x_out']) < 0.5: name = 'outlet'
        elif xmin > g['x_hub'] - 1 and xmax < g['x_shr'] + 1 and xmax - xmin > 5 and max(ymax - ymin, zmax - zmin) < 120: name = 'struts'
        elif rb and xmin > rx0 - 0.5 and xmax < rx1 + 0.5 and rmax < rr1 + 0.5: name = 'struts'      # turning ring
        elif xmin > g['x_hub'] - 1 and rmax < max(g['r_eye_shr'] + 25.0, g['shroud'][1][1] + 2.0): name = 'bend'
        elif xmin > g['x_hub'] - g['R_lip'] - 1 and xmax < g['x_hub'] + 1 and rmax < g['R_T'] + 1: name = 'casing'
        else: name = 'plenum'
        reg.setdefault(name, []).append(tag)
    print({k: len(v) for k, v in reg.items()})
    for name, tags in reg.items():
        size = dict(struts=1.5, bend=2.5, outlet=4.0, casing=5.0).get(name, 25.0)
        for t in tags:
            gmsh.model.mesh.setSize(gmsh.model.getBoundary([(2, t)], recursive=True), size)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 36)
    gmsh.option.setNumber('Mesh.MeshSizeMax', 25.0); gmsh.option.setNumber('Mesh.MeshSizeMin', 1.0)
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


# ================================================================================================ node: post
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


def tri_annulus(y, z, r_in, r_out):
    """Delaunay triangles of cut-plane points inside an annulus (long edges across walls removed); areas and centroids"""
    import numpy as np
    from scipy.spatial import Delaunay
    T = Delaunay(np.c_[y, z]).simplices; P = np.c_[y, z][T]
    e = np.max([np.linalg.norm(P[:, a] - P[:, b], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)
    yc, zc = P[:, :, 0].mean(1), P[:, :, 1].mean(1); rc = np.hypot(yc, zc)
    keep = (e < 4 * np.median(e)) & (rc > r_in) & (rc < r_out)
    T, P = T[keep], P[keep]
    A = 0.5 * np.abs((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1]) - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
    return T, A, P[:, :, 0].mean(1), P[:, :, 1].mean(1)


def eye_metrics(f, g, q, n_sec=72, n_rad=10):
    """eye plane: flux-weighted p0, swirl (+ = with the rotation, +theta from +y to +z), DC60 = (p0_mean - min 60 deg
    sector) / q, sector swirl range, radial profiles, axial-velocity uniformity index"""
    import numpy as np
    U = f['U']; y, z = U[:, 1], U[:, 2]
    r_in, r_out = g['r_eye_hub'] * 1e-3, g['r_eye_shr'] * 1e-3
    T, A, yc, zc = tri_annulus(y, z, r_in, r_out)
    m = lambda v: v[T].mean(1)
    ux = m(U[:, 3]); uy, uz = m(U[:, 4]), m(U[:, 5]); p0 = m(f['p0'][:, 3]); p = m(f['p'][:, 3])
    rc = np.hypot(yc, zc); th = np.degrees(np.arctan2(zc, yc)) % 360.0
    ut = (-uy * zc + uz * yc) / rc; ur = (uy * yc + uz * zc) / rc
    wgt = ux * A; W = wgt.sum()
    p0m = (p0 * wgt).sum() / W
    cxm = (ux * A).sum() / A.sum()
    sec = np.floor(th / (360.0 / n_sec)).astype(int) % n_sec
    s_p0 = np.array([(p0[sec == k] * A[sec == k]).sum() / A[sec == k].sum() for k in range(n_sec)])
    s_sw = np.array([np.degrees(np.arctan2((ut[sec == k] * wgt[sec == k]).sum(), (ux[sec == k] * wgt[sec == k]).sum())) for k in range(n_sec)])
    s_cx = np.array([(ux[sec == k] * A[sec == k]).sum() / A[sec == k].sum() for k in range(n_sec)])
    nw = n_sec // 6
    roll = np.array([np.mean(np.take(s_p0, range(k, k + nw), mode='wrap')) for k in range(n_sec)])
    k60 = int(np.argmin(roll))
    s_mean = (s_p0 * np.bincount(sec, weights=A, minlength=n_sec)).sum() / A.sum()
    rb = np.linspace(r_in, r_out, n_rad + 1); ri = np.clip(np.digitize(rc, rb) - 1, 0, n_rad - 1)
    rad = []
    for k in range(n_rad):
        s_ = ri == k
        rad.append(dict(r_mm=float(0.5 * (rb[k] + rb[k + 1]) * 1e3), cx_ratio=float((ux[s_] * A[s_]).sum() / A[s_].sum() / cxm),
                        dp0_q=float((p0m - (p0[s_] * wgt[s_]).sum() / wgt[s_].sum()) / q),
                        swirl_deg=float(np.degrees(np.arctan2((ut[s_] * wgt[s_]).sum(), (ux[s_] * wgt[s_]).sum()))),
                        swirl_rms_deg=float(np.sqrt((np.degrees(np.arctan2(ut[s_], ux[s_])) ** 2 * A[s_]).sum() / A[s_].sum()))))
    loc_sw = np.degrees(np.arctan2(ut, ux))
    return dict(x_mm=float(U[0, 0] * 1e3), area_m2=float(A.sum()), Q_m3s=float(W), p0=float(p0m), p=float((p * A).sum() / A.sum()),
                cx_mean=float(cxm), DC60=float((s_mean - roll[k60]) / q), DC60_sector_start_deg=float(k60 * 360.0 / n_sec),
                p0_sector_dev_q=dict(min=float((s_p0.min() - s_mean) / q), max=float((s_p0.max() - s_mean) / q)),
                swirl_sector_deg=dict(min=float(s_sw.min()), max=float(s_sw.max()), at_min=float(np.argmin(s_sw) * 360.0 / n_sec),
                                      at_max=float(np.argmax(s_sw) * 360.0 / n_sec)),
                swirl_local_deg=dict(p01=float(np.percentile(loc_sw, 1)), p99=float(np.percentile(loc_sw, 99)),
                                     rms=float(np.sqrt((loc_sw ** 2 * A).sum() / A.sum()))),
                swirl_mean_deg=float(np.degrees(np.arctan2((ut * wgt).sum(), (ux * wgt).sum()))),
                cx_sector=dict(min=float(s_cx.min() / cxm), max=float(s_cx.max() / cxm)),
                uniformity_index=float(1.0 - (np.abs(ux - cxm) * A).sum() / (2 * cxm * A.sum())),
                reverse_area=float(A[ux < 0].sum() / A.sum()), radial=rad, sector_p0_q=[float((v - s_mean) / q) for v in s_p0],
                sector_swirl_deg=[float(v) for v in s_sw], n_tri=int(len(T)))


def cyl_station(f, r_mm):
    """distanceSurface on a cylinder: mass-weighted p0 with the inward radial flux (points carry their own area share)"""
    import numpy as np
    U = f['U']; y, z = U[:, 1], U[:, 2]; r = np.hypot(y, z)
    on = np.abs(r - r_mm * 1e-3) < 3e-3                              # drop the end caps of the searchable cylinder
    ur = -(U[:, 4] * y + U[:, 5] * z) / r
    wgt = np.clip(ur, 0, None) * on
    return dict(r_mm=r_mm, p0=float((f['p0'][:, 3] * wgt).sum() / wgt.sum()), n=int(on.sum()),
                ur_mean=float(ur.mean()), reverse_frac=float((ur < 0).mean()))


def post():
    inl = json.load(open('inlet.json')); g = json.load(open('geometry.json'))
    q = inl['q_eye_kin']
    a, b, ey = last_dat('ports'), last_dat('portsOut'), last_dat('eye')
    hist = [(ra[0], (ra[2] - re[1]) / q) for ra, re in zip(a, ey)]
    n = max(1, int(0.3 * len(hist))); tail = [h[1] for h in hist[-n:]]
    res = dict(iterations=hist[-1][0], zeta_eye=sum(tail) / len(tail), zeta_last=hist[-1][1], zeta_tail_min=min(tail),
               zeta_tail_max=max(tail), q_eye_kin=q, c_eye_bulk=inl['c_eye'], p0_in=a[-1][2], p_in=a[-1][1],
               p0_out=b[-1][2], zeta_outlet=(a[-1][2] - b[-1][2]) / q, zeta_history=hist[::max(1, len(hist) // 60)])
    fl = last_dat('flow'); res['Q_inlet_m3_s'] = -fl[-1][1]
    import re
    cm = open('log.checkMesh').read(); res['cells'] = int(re.search(r'cells:\s+(\d+)', cm).group(1))
    res['mesh_ok'] = 'Mesh OK' in cm
    try:
        yp = open('log.yPlus').read()
        res['yplus'] = {mm.group(1): dict(min=float(mm.group(2)), max=float(mm.group(3)), avg=float(mm.group(4)))
                        for mm in re.finditer(r'patch (\w+) y\+ : min = ([\d.eE+-]+), max = ([\d.eE+-]+), average = ([\d.eE+-]+)', yp)}
    except Exception:
        res['yplus'] = {}
    pl = raw_planes()
    res['eye'] = eye_metrics(pl['x%03d' % g['x_le']], g, q)
    for k in ('x212', 'x260'):
        if k in pl: res[k] = {kk: v for kk, v in eye_metrics(pl[k], g, q).items() if kk not in ('sector_p0_q', 'sector_swirl_deg')}
    res['stations'] = {}
    for nm, r in (('r270', 270.0), ('r152', 152.0)):
        if nm in pl:
            st = cyl_station(pl[nm], r); st['zeta_from_inlet'] = (res['p0_in'] - st['p0']) / q; res['stations'][nm] = st
    res['zeta_plane_eye'] = (res['p0_in'] - res['eye']['p0']) / q
    json.dump(res, open('result.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ('zeta_history',)}, indent=1)[:6000])


def plot(fn='inlet_cfd.png'):
    """in a finished case: |U| on z = 0 (x-y) and y = 0 (x-z) planes, the slot mid-plane and the eye plane"""
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    g = json.load(open('geometry.json')); inl = json.load(open('inlet.json')); bx = g['box']
    pl = raw_planes()
    fig, ax = plt.subplots(2, 2, figsize=(13, 11), dpi=100)
    def panel(a_, surf, i, j, lab_i, lab_j, lim, vmax, title, mask_len):
        U = pl[surf]['U']; X, Y = U[:, i] * 1e3, U[:, j] * 1e3; mag = np.linalg.norm(U[:, 3:6], axis=1)
        tri = mtri.Triangulation(X, Y); P = np.c_[X, Y][tri.triangles]
        e = np.max([np.linalg.norm(P[:, k] - P[:, (k + 1) % 3], axis=1) for k in range(3)], axis=0)
        tri.set_mask(e > mask_len)
        cs = a_.tricontourf(tri, mag, levels=np.linspace(0, vmax, 25), cmap='viridis', extend='max')
        a_.set_aspect('equal'); a_.set_xlabel(lab_i + ' [mm]'); a_.set_ylabel(lab_j + ' [mm]'); a_.set_xlim(lim[0]); a_.set_ylim(lim[1])
        a_.set_title(title, fontsize=9); return cs
    cs = panel(ax[0, 0], 'y0', 0, 2, 'x', 'z', ((bx['x0'] - 10, g['x_out']), (bx['z0'] - 10, bx['z1'] + 60)), 140,
               'y = 0: duct -> plenum -> top / bottom slot -> bend -> eye', 40)
    panel(ax[0, 1], 'z0', 0, 1, 'x', 'y', ((bx['x0'] - 10, g['x_out']), (bx['y0'] - 10, bx['y1'] + 10)), 140,
          'z = 0: side gaps -> slot (struts at 45 deg off this plane)', 40)
    panel(ax[1, 0], 'xslot', 1, 2, 'y', 'z', ((bx['y0'] - 10, bx['y1'] + 10), (bx['z0'] - 10, bx['z1'] + 10)), 140,
          'slot mid-plane x %.1f: radial inflow, 4 struts' % (0.5 * (g['x_hub'] + g['x_shr'])), 40)
    fe = pl['x%03d' % g['x_le']]; U = fe['U']; y, z = U[:, 1] * 1e3, U[:, 2] * 1e3
    T, A, yc, zc = tri_annulus(U[:, 1], U[:, 2], g['r_eye_hub'] * 1e-3, g['r_eye_shr'] * 1e-3)
    tri = mtri.Triangulation(y, z, T)
    q = inl['q_eye_kin']; p0 = fe['p0'][:, 3]
    p0in = json.load(open('result.json'))['p0_in'] if os.path.exists('result.json') else p0.max()
    cs2 = ax[1, 1].tripcolor(tri, (p0in - p0) / q, shading='gouraud', cmap='magma_r', vmin=0, vmax=0.3)
    ax[1, 1].set_aspect('equal'); ax[1, 1].set_title('eye x %.0f: total-pressure loss / q_eye (view from the front)' % g['x_le'], fontsize=9)
    ax[1, 1].set_xlabel('y [mm]'); ax[1, 1].set_ylabel('z [mm]')
    fig.colorbar(cs, ax=ax[0, :], shrink=0.7, label='|U| [m/s]  (eye bulk %.0f m/s)' % inl['c_eye'])
    fig.colorbar(cs2, ax=ax[1, 1], shrink=0.7, label='(p0_in - p0) / q_eye')
    fig.savefig(fn, bbox_inches='tight'); print('wrote', fn)


def collect():
    """local: fetch result.json (+ plot) of every finished case from the vast node, assemble results.json"""
    import subprocess
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', 'engine')))
    import a1000_inlet as E
    out = dict(design=E.DESIGN, meshes={}, designs={})
    for d in sorted(os.listdir(HERE)):
        if not d.startswith('case_'): continue
        name = d[5:]
        cd = os.path.join(HERE, d)
        subprocess.run(['rsync', '-a', 'vast:/root/runs/a1000_inl/%s/result.json' % d, cd + '/'], capture_output=True)
        f = os.path.join(cd, 'result.json')
        if not os.path.exists(f): continue
        r = json.load(open(f)); r.pop('zeta_history', None)
        dsg, mesh = name.split('_', 1)
        if dsg == E.DESIGN: out['meshes'][mesh] = r
        out['designs'].setdefault(dsg, {})[mesh] = dict(zeta_eye=r['zeta_eye'], zeta_tail_min=r['zeta_tail_min'],
                                                        zeta_tail_max=r['zeta_tail_max'], cells=r['cells'], DC60=r['eye']['DC60'],
                                                        swirl_sector=r['eye']['swirl_sector_deg'], note=E.DESIGN_NOTES.get(dsg, ''))
    json.dump(out, open(os.path.join(HERE, 'results.json'), 'w'), indent=1)
    for d, ms in out['designs'].items():
        for m, r in ms.items():
            print('%s %-7s cells %8d  zeta %.4f  DC60 %.3f  swirl %.1f..%.1f deg' % (d, m, r['cells'], r['zeta_eye'], r['DC60'],
                                                                                 r['swirl_sector']['min'], r['swirl_sector']['max']))


if __name__ == '__main__':
    if '--collect' in sys.argv: collect()
    elif '--write' in sys.argv:
        i = sys.argv.index('--write'); args = sys.argv[i + 1:]
        write_cases(args[0] if args else 'A', args[1].split(',') if len(args) > 1 else None)
    elif '--geom' in sys.argv: make_geometry()
    elif '--post' in sys.argv: post()
    elif '--plot' in sys.argv: plot()
