#!/bin/bash
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
