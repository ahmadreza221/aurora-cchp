#!/usr/bin/env python3
"""GR180-CCHP E1 - OpenFOAM (v2606, rhoSimpleFoam) single-passage NGV case generator + runner + post-processing.

Domain: one of 21 NGV passages, x 90 -> 110 mm (inlet plane 4.8 mm upstream of the ring front face, outlet at the
NGV/rotor interface), hub r 22.25, shroud r 36.05 -> 26 deg chamfer -> bore r_b (geometry/passage.json), periodic
sides (cyclicAMI, rotational 360/21 deg), vane walls from geometry/ngv_vane.stl (cad/engine/e1_cfd_geometry.py).
Background mesh: blockMesh 3-block annular sector (metres); snappyHexMesh castellates / snaps / adds layers on the vane.
Gas: air-like ideal gas (janaf), Sutherland viscosity; kOmegaSST; steady compressible (rhoSimpleFoam).
BCs: inlet total p / total T of the meanline (P01, T01), outlet static p = meanline NGV exit static P2 (x 110);
walls no-slip adiabatic.  Result of interest: mass flow at the meanline pressure ratio (throat check: 1175 mm2 CAD vs
1224 meanline), exit flow angle and Mach vs the meanline alpha2, loss (p0 drop).

Run:  python sim/cfd/e1_stage/make_case.py            # writes the case into sim/cfd/e1_stage/ngv/ and runs it
      python sim/cfd/e1_stage/make_case.py --mesh-only / --post-only / --level N (vane refinement level, default 3)
OpenFOAM: /Applications/OpenFOAM-v2606.app (gerlero/openfoam-app); OF env var overrides the launcher path.
"""
import json
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
GEO = os.path.join(HERE, 'geometry')
CASE = os.path.join(HERE, 'ngv')
OF = os.environ.get('OF', '/Applications/OpenFOAM-v2606.app/Contents/Resources/etc/openfoam')
META = json.load(open(os.path.join(GEO, 'passage.json')))
D = META['design']
NP = max(2, min(8, (os.cpu_count() or 4) - 2))

HEADER = '''FoamFile
{
    version     2.0;
    format      ascii;
    class       %s;
    object      %s;
}
'''


def w(rel, cls, body):
    path = os.path.join(CASE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(HEADER % (cls, os.path.basename(rel)) + body)


def block_mesh():
    """3 blocks in x: inlet (r 22.25..36.05), chamfer (36.05 -> rb), bore (rb). Sector +-pitch/2 about the vane."""
    Zn = META['Z_ngv']; pitch = math.radians(360.0 / Zn)
    v0, v1 = META['vane_theta_deg']
    thc = math.radians(0.5 * (v0 + v1))              # vane centre angle
    tl, tr = thc - pitch / 2, thc + pitch / 2
    rh, rs, rb = META['r_hub_ngv'], META['r_shroud_inlet'], META['r_bore']
    x_in, x_f = META['x_inlet'], 94.8
    x_ch = x_f + (rs - rb) / math.tan(math.radians(26))
    x_out = META['x_interface']
    xs = [x_in, x_f, x_ch, x_out]
    ro = [rs, rs, rb, rb]
    S = 1e-3
    verts = []
    def P(x, r, th):
        verts.append('    (%.6f %.6f %.6f)' % (x * S, r * math.cos(th) * S, r * math.sin(th) * S)); return len(verts) - 1
    idx = []
    for k, x in enumerate(xs):
        idx.append([P(x, rh, tl), P(x, ro[k], tl), P(x, ro[k], tr), P(x, rh, tr)])
    # cells: axial per block, radial, tangential (coarse background; snappy refines the vane region)
    nx = [8, 4, 24]; nr = 22; nt = 24
    blocks = []
    for k in range(3):
        a, b = idx[k], idx[k + 1]
        # hex ordering: x-direction = axial, y = radial, z = tangential
        blocks.append('    hex (%d %d %d %d %d %d %d %d) (%d %d %d) simpleGrading (1 1 1)' % (
            a[0], b[0], b[1], a[1], a[3], b[3], b[2], a[2], nx[k], nr, nt))
    edges = []
    for k in range(4):
        x = xs[k]
        for (i, j, r) in ((idx[k][0], idx[k][3], rh), (idx[k][1], idx[k][2], ro[k])):
            edges.append('    arc %d %d (%.6f %.6f %.6f)' % (i, j, x * S, r * math.cos(thc) * S, r * math.sin(thc) * S))
    def face(a, b, c, d): return '(%d %d %d %d)' % (a, b, c, d)
    inlet = [face(idx[0][0], idx[0][1], idx[0][2], idx[0][3])]
    outlet = [face(idx[3][0], idx[3][3], idx[3][2], idx[3][1])]
    hub, shroud, left, right = [], [], [], []
    for k in range(3):
        a, b = idx[k], idx[k + 1]
        hub.append(face(a[0], b[0], b[3], a[3]))
        shroud.append(face(a[1], a[2], b[2], b[1]))
        left.append(face(a[0], a[1], b[1], b[0]))
        right.append(face(a[3], b[3], b[2], a[2]))
    body = '''scale 1;

vertices
(
%s
);

blocks
(
%s
);

edges
(
%s
);

boundary
(
    inlet   { type patch; faces ( %s ); }
    outlet  { type patch; faces ( %s ); }
    hub     { type wall;  faces ( %s ); }
    shroud  { type wall;  faces ( %s ); }
    per1
    {
        type            cyclicAMI;
        neighbourPatch  per2;
        transformType   rotational;
        rotationAxis    (1 0 0);
        rotationCentre  (0 0 0);
        faces ( %s );
    }
    per2
    {
        type            cyclicAMI;
        neighbourPatch  per1;
        transformType   rotational;
        rotationAxis    (1 0 0);
        rotationCentre  (0 0 0);
        faces ( %s );
    }
);
''' % ('\n'.join(verts), '\n'.join(blocks), '\n'.join(edges), ' '.join(inlet), ' '.join(outlet), ' '.join(hub),
       ' '.join(shroud), ' '.join(left), ' '.join(right))
    w('system/blockMeshDict', 'dictionary', body)
    return dict(thc=thc, tl=tl, tr=tr, x_ch=x_ch)


def snappy(level):
    v0, v1 = META['vane_theta_deg']; thc = math.radians(0.5 * (v0 + v1))
    # a point in the fluid: mid passage, just upstream of the vane LE, mid span
    x_le = META['x_ngv_le_te'][0]; r_m = 0.5 * (META['r_hub_ngv'] + META['r_bore'])
    pitch = math.radians(360.0 / META['Z_ngv'])
    th = thc + pitch * 0.45
    loc = (x_le - 3.0) * 1e-3, r_m * math.cos(th) * 1e-3, r_m * math.sin(th) * 1e-3
    body = '''castellatedMesh true;
snap            true;
addLayers       true;

geometry
{
    vane
    {
        type triSurfaceMesh;
        file "ngv_vane_m.stl";
    }
    refineBox
    {
        type box;
        min (%.5f -1 -1);
        max (%.5f  1  1);
    }
}

castellatedMeshControls
{
    maxLocalCells       4000000;
    maxGlobalCells      12000000;
    minRefinementCells  10;
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels 3;
    features
    (
        { file "ngv_vane_m.eMesh"; level %d; }
    );
    refinementSurfaces
    {
        vane { level (%d %d); patchInfo { type wall; } }
    }
    resolveFeatureAngle 25;
    refinementRegions
    {
        vane     { mode distance; levels ((0.0006 %d) (0.0015 %d)); }
        refineBox { mode inside; levels ((1e15 1)); }
    }
    locationInMesh (%.6f %.6f %.6f);
    allowFreeStandingZoneFaces true;
}

snapControls
{
    nSmoothPatch    3;
    tolerance       2.0;
    nSolveIter      50;
    nRelaxIter      5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}

addLayersControls
{
    relativeSizes       true;
    layers
    {
        vane   { nSurfaceLayers 6; }
        hub    { nSurfaceLayers 3; }
        shroud { nSurfaceLayers 3; }
    }
    expansionRatio      1.25;
    finalLayerThickness 0.35;
    minThickness        0.05;
    nGrow               0;
    featureAngle        120;
    slipFeatureAngle    30;
    nRelaxIter          5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals      3;
    nSmoothThickness    10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle  90;
    minMedialAxisAngle  90;
    nBufferCellsNoExtrude 0;
    nLayerIter          50;
}

meshQualityControls
{
    maxNonOrtho         70;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave          80;
    minVol              1e-18;
    minTetQuality       1e-30;
    minArea             -1;
    minTwist            0.02;
    minDeterminant      0.001;
    minFaceWeight       0.05;
    minVolRatio         0.01;
    minTriangleTwist    -1;
    nSmoothScale        4;
    errorReduction      0.75;
    relaxed { maxNonOrtho 75; }
}

mergeTolerance 1e-6;
''' % ((META['x_ngv_le_te'][0] - 2.5) * 1e-3, (META['x_ngv_le_te'][1] + 3.0) * 1e-3, level, level, level + 1, level + 1, level, *loc)
    w('system/snappyHexMeshDict', 'dictionary', body)
    w('system/surfaceFeatureExtractDict', 'dictionary', '''ngv_vane_m.stl
{
    extractionMethod    extractFromSurface;
    includedAngle       150;
    subsetFeatures { nonManifoldEdges no; openEdges yes; }
    writeObj            no;
}
''')


def controls():
    w('system/controlDict', 'dictionary', '''application     rhoSimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         1500;
deltaT          1;
writeControl    timeStep;
writeInterval   250;
purgeWrite      2;
writeFormat     binary;
writePrecision  8;
timeFormat      general;
runTimeModifiable true;

functions
{
    mdot_in  { type flowRatePatch; libs (fieldFunctionObjects); patch inlet;  writeControl timeStep; writeInterval 25; log true; }
    mdot_out { type flowRatePatch; libs (fieldFunctionObjects); patch outlet; writeControl timeStep; writeInterval 25; log true; }
    p0 { type pressure; libs (fieldFunctionObjects); mode total; rho rho; writeControl writeTime; }
    Ma { type MachNo; libs (fieldFunctionObjects); writeControl writeTime; }
    out_avg
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name outlet;
        operation weightedAreaAverage; weightField phi; fields (p T total(p) U); writeControl timeStep; writeInterval 25; log true; writeFields false;
    }
    in_avg
    {
        type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet;
        operation weightedAreaAverage; weightField phi; fields (p T total(p)); writeControl timeStep; writeInterval 25; log true; writeFields false;
    }
    yPlus { type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }
}
''')
    w('system/fvSchemes', 'dictionary', '''ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; limited cellLimited Gauss linear 1; grad(U) $limited; grad(e) $limited; grad(h) $limited; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwindV limited;
    div(phi,e)      bounded Gauss linearUpwind limited;
    div(phi,h)      bounded Gauss linearUpwind limited;
    div(phi,K)      bounded Gauss linearUpwind limited;
    div(phi,Ekp)    bounded Gauss linearUpwind limited;
    div(phi,k)      bounded Gauss limitedLinear 1;
    div(phi,omega)  bounded Gauss limitedLinear 1;
    div(phid,p)     Gauss limitedLinear 1;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes   { default limited corrected 0.5; }
wallDist        { method meshWave; }
''')
    w('system/fvSolution', 'dictionary', '''solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-8;
        relTol          0.05;
    }
    "(U|e|h|k|omega)"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-8;
        relTol          0.1;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent      yes;
    transonic       yes;
    pMinFactor      0.3;
    pMaxFactor      1.5;
    residualControl { p 1e-5; U 1e-5; e 1e-5; "(k|omega)" 1e-5; }
}

relaxationFactors
{
    fields    { p 0.3; rho 0.05; }
    equations { U 0.7; e 0.5; h 0.5; "(k|omega)" 0.7; }
}
''')
    w('system/decomposeParDict', 'dictionary', 'numberOfSubdomains %d;\nmethod scotch;\n' % NP)


def constant():
    w('constant/thermophysicalProperties', 'dictionary', '''thermoType
{
    type            hePsiThermo;
    mixture         pureMixture;
    transport       sutherland;
    thermo          janaf;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleInternalEnergy;
}

mixture
{
    specie    { molWeight 28.96; }
    thermodynamics
    {
        Tlow 200; Thigh 3000; Tcommon 1000;
        highCpCoeffs ( 3.0879 0.00124597 -4.23719e-07 6.74775e-11 -3.97077e-15 -995.263 5.95961 );
        lowCpCoeffs  ( 3.56839 -0.000678729 1.55371e-06 -3.29937e-12 -4.66395e-13 -1062.12 3.71582 );
    }
    transport { As 1.4792e-06; Ts 116; }
}
''')
    w('constant/turbulenceProperties', 'dictionary', 'simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n')


def fields():
    p01, t01, p2 = D['P01_Pa'], D['T01_K'], D['P2_Pa']
    # inlet turbulence: 5 % intensity, length 2 mm
    u_in = 120.0; k = 1.5 * (0.05 * u_in)**2; omg = math.sqrt(k) / (0.09**0.25 * 0.002)
    per = '    per1 { type cyclicAMI; }\n    per2 { type cyclicAMI; }\n'
    w('0/p', 'volScalarField', '''dimensions [1 -1 -2 0 0 0 0];
internalField uniform %.1f;
boundaryField
{
    inlet  { type totalPressure; p0 uniform %.1f; gamma 1.33; rho rho; psi psi; value uniform %.1f; }
    outlet { type fixedValue; value uniform %.1f; }
    "(hub|shroud|vane)" { type zeroGradient; }
%s}
''' % (0.5 * (p01 + p2), p01, p01 * 0.95, p2, per))
    w('0/T', 'volScalarField', '''dimensions [0 0 0 1 0 0 0];
internalField uniform %.1f;
boundaryField
{
    inlet  { type totalTemperature; T0 uniform %.1f; gamma 1.33; psi psi; value uniform %.1f; }
    outlet { type inletOutlet; inletValue uniform %.1f; value uniform %.1f; }
    "(hub|shroud|vane)" { type zeroGradient; }
%s}
''' % (0.5 * (t01 + D['T2_K']), t01, t01, D['T2_K'], D['T2_K'], per))
    w('0/U', 'volVectorField', '''dimensions [0 1 -1 0 0 0 0];
internalField uniform (%.1f 0 0);
boundaryField
{
    inlet  { type pressureInletOutletVelocity; value uniform (%.1f 0 0); }
    outlet { type inletOutlet; inletValue uniform (0 0 0); value uniform (%.1f 0 0); }
    "(hub|shroud|vane)" { type noSlip; }
%s}
''' % (u_in, u_in, 250.0, per))
    w('0/k', 'volScalarField', '''dimensions [0 2 -2 0 0 0 0];
internalField uniform %.3f;
boundaryField
{
    inlet  { type fixedValue; value uniform %.3f; }
    outlet { type inletOutlet; inletValue uniform %.3f; value uniform %.3f; }
    "(hub|shroud|vane)" { type kqRWallFunction; value uniform %.3f; }
%s}
''' % (k, k, k, k, k, per))
    w('0/omega', 'volScalarField', '''dimensions [0 0 -1 0 0 0 0];
internalField uniform %.1f;
boundaryField
{
    inlet  { type fixedValue; value uniform %.1f; }
    outlet { type inletOutlet; inletValue uniform %.1f; value uniform %.1f; }
    "(hub|shroud|vane)" { type omegaWallFunction; value uniform %.1f; }
%s}
''' % (omg, omg, omg, omg, omg, per))
    w('0/nut', 'volScalarField', '''dimensions [0 2 -1 0 0 0 0];
internalField uniform 0;
boundaryField
{
    inlet  { type calculated; value uniform 0; }
    outlet { type calculated; value uniform 0; }
    "(hub|shroud|vane)" { type nutkWallFunction; value uniform 0; }
%s}
''' % per)
    w('0/alphat', 'volScalarField', '''dimensions [1 -1 -1 0 0 0 0];
internalField uniform 0;
boundaryField
{
    inlet  { type calculated; value uniform 0; }
    outlet { type calculated; value uniform 0; }
    "(hub|shroud|vane)" { type compressible::alphatWallFunction; Prt 0.85; value uniform 0; }
%s}
''' % per)


def stl_periodic(src, dst, pitch_deg, copies=(-1, 0, 1), scale=1e-3):
    """Binary STL -> binary STL in metres with the surface repeated at k x pitch about the x axis (neighbouring vanes), so
    the straight periodic sides of the sector cut the vane row consistently on both sides."""
    import struct
    data = open(src, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0]
    tris = []
    for i in range(n):
        o = 84 + 50 * i
        v = struct.unpack('<12f', data[o:o + 48])
        tris.append(v)
    out = [b'periodic vane row'.ljust(80, b' '), struct.pack('<I', n * len(copies))]
    for k in copies:
        a = math.radians(k * pitch_deg); c, sn = math.cos(a), math.sin(a)
        for v in tris:
            pts = []
            for j in range(4):
                x, y, z = v[3 * j:3 * j + 3]
                yr, zr = c * y - sn * z, sn * y + c * z
                f = 1.0 if j == 0 else scale
                pts += [x * f, yr * f, zr * f]
            out.append(struct.pack('<12fH', *pts, 0))
    open(dst, 'wb').write(b''.join(out))
    return n * len(copies)


def sh(cmd, log):
    """run a command inside the OpenFOAM environment, in the case folder, logging to log"""
    full = 'cd "%s" && %s' % (CASE, cmd)
    with open(os.path.join(CASE, log), 'w') as f:
        p = subprocess.run([OF, '-c', full], stdout=f, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        print(open(os.path.join(CASE, log)).read()[-4000:])
        raise RuntimeError('failed: ' + cmd)
    return p.returncode


def build(level):
    if os.path.isdir(CASE):
        shutil.rmtree(CASE)
    os.makedirs(os.path.join(CASE, 'constant', 'triSurface'), exist_ok=True)
    block_mesh(); snappy(level); controls(); constant(); fields()
    nf = stl_periodic(os.path.join(GEO, 'ngv_vane.stl'), os.path.join(CASE, 'constant', 'triSurface', 'ngv_vane_m.stl'), 360.0 / META['Z_ngv'])
    print('vane row STL: %d facets (3 vanes, metres)' % nf)
    open(os.path.join(CASE, 'Allrun.sh'), 'w').write('''#!/bin/bash
set -e
cd "$(dirname "$0")"
blockMesh > log.blockMesh 2>&1
surfaceFeatureExtract > log.surfaceFeatureExtract 2>&1
snappyHexMesh -overwrite > log.snappyHexMesh 2>&1
checkMesh -allTopology -allGeometry > log.checkMesh 2>&1 || true
decomposePar -force > log.decomposePar 2>&1
mpirun -np %d rhoSimpleFoam -parallel > log.rhoSimpleFoam 2>&1
reconstructPar -latestTime > log.reconstructPar 2>&1
''' % NP)
    os.chmod(os.path.join(CASE, 'Allrun.sh'), 0o755)
    print('case written:', CASE)


def post():
    """mass flow, exit angle / Mach / loss from the function-object logs and the latest fields (postProcess)."""
    import re
    res = {}
    def last_value(path, col=-1):
        vals = [l.split() for l in open(path) if l.strip() and not l.startswith('#')]
        return [float(v) for v in vals[-1]] if vals else None
    try:
        fin = last_value(os.path.join(CASE, 'postProcessing', 'mdot_in', '0', 'surfaceFieldValue.dat'))
    except Exception:
        fin = None
    pp = os.path.join(CASE, 'postProcessing')
    for name in ('mdot_in', 'mdot_out', 'in_avg', 'out_avg'):
        d = os.path.join(pp, name)
        if not os.path.isdir(d):
            continue
        tdirs = sorted(os.listdir(d), key=lambda s: float(s) if s.replace('.', '').isdigit() else 0)
        f = os.path.join(d, tdirs[-1], 'surfaceFieldValue.dat')
        if os.path.exists(f):
            lines = [l for l in open(f) if l.strip() and not l.startswith('#')]
            hdr = [l for l in open(f) if l.startswith('#') and 'Time' in l]
            res[name] = dict(header=hdr[-1].strip('# \n') if hdr else '', last=lines[-1].split())
    Zn = META['Z_ngv']
    if 'mdot_in' in res:
        m1 = float(res['mdot_in']['last'][1]); res['mdot_stage_kg_s'] = abs(m1) * Zn
        res['mdot_meanline_kg_s'] = D['mdot_kg_s']; res['mdot_ratio'] = abs(m1) * Zn / D['mdot_kg_s']
    json.dump(res, open(os.path.join(HERE, 'ngv_results.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    level = int(a[a.index('--level') + 1]) if '--level' in a else 3
    if '--post-only' in a:
        post(); sys.exit(0)
    build(level)
    if '--write-only' in a:
        sys.exit(0)
    print('meshing + solving (log in %s) ...' % CASE, flush=True)
    sh('bash Allrun.sh' if '--mesh-only' not in a else 'bash -c "blockMesh && surfaceFeatureExtract && snappyHexMesh -overwrite && checkMesh -allGeometry -allTopology"', 'log.Allrun')
    if '--mesh-only' not in a:
        post()
