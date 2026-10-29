"""AURORA-1000 turbine: colour render of the 2-stage turbine (NGV1, blisk 1, NGV2, blisk 2) from the CAD pieces, offscreen VTK.

The full rows are instanced from the single blade / vane pieces (rotated copies), no boolean fuse is needed. The outer NGV
rings are cut away over the upper half so the rotor blades show.
Input:  cad_out/engine/A1000/A1000_<R1|R2>_blade.brep, _disc.brep, A1000_<N1|N2>_vane.brep, _rings.brep  (a1000_turbine.py --cad)
Run:    xvfb-run -a freecadcmd -c "exec(open('cad/engine/a1000_render.py').read())"
Writes: docs/img/a1000_turbine_render_iso.png, docs/img/a1000_turbine_render_blades.png
"""
import math
import os

import numpy as np
import FreeCAD as App  # noqa: F401
import Part
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

ROOT = os.environ.get('GR180_ROOT', os.getcwd())
CAD = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
IMG = os.path.join(ROOT, 'docs', 'img')
import json  # noqa: E402
Z = {k: json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))[k]['Z'] for k in ('N1', 'R1', 'N2', 'R2')}
COL = dict(N1=(0.86, 0.52, 0.30), R1=(0.74, 0.76, 0.80), N2=(0.88, 0.64, 0.38), R2=(0.66, 0.70, 0.78),
           disc=(0.58, 0.60, 0.64), ring=(0.36, 0.37, 0.40))


def tess(name, tol=0.02, solid=None):
    s = Part.Shape(); s.read(os.path.join(CAD, name + '.brep'))
    if solid is not None: s = sorted(s.Solids, key=lambda q: q.BoundBox.YMax)[solid]   # rings: 0 inner, 1 outer
    v, t = s.tessellate(tol)
    return np.array([(p.x, p.y, p.z) for p in v]), np.array(t, dtype=np.int64)


def rot_x(V, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return np.c_[V[:, 0], c * V[:, 1] - s * V[:, 2], s * V[:, 1] + c * V[:, 2]]


def instance(V, T, n):
    Vs, Ts = [], []
    for k in range(n):
        Vs.append(rot_x(V, 360.0 * k / n)); Ts.append(T + k * len(V))
    return np.vstack(Vs), np.vstack(Ts)


def polydata(V, T):
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(V.astype(np.float64), deep=True))
    cells = vtk.vtkCellArray(); ca = np.hstack([np.full((len(T), 1), 3), T]).astype(np.int64).ravel()
    cells.SetCells(len(T), numpy_to_vtkIdTypeArray(ca, deep=True))
    pd = vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(cells)
    return pd


def actor(pd, col, clip=None, spec=0.45):
    src = pd
    if clip is not None:                                      # keep the half-space below the clip plane (cut-away)
        pl = vtk.vtkPlane(); pl.SetOrigin(0, 0, 0); pl.SetNormal(*clip)
        cp = vtk.vtkClipPolyData(); cp.SetInputData(pd); cp.SetClipFunction(pl); cp.InsideOutOn(); cp.Update()
        src = cp.GetOutput()
    nm = vtk.vtkPolyDataNormals(); nm.SetInputData(src); nm.SetFeatureAngle(35); nm.SplittingOn(); nm.ConsistencyOn()
    mp = vtk.vtkPolyDataMapper(); mp.SetInputConnection(nm.GetOutputPort())
    ac = vtk.vtkActor(); ac.SetMapper(mp); pr = ac.GetProperty()
    pr.SetColor(*col); pr.SetInterpolationToPhong(); pr.SetSpecular(spec); pr.SetSpecularPower(35); pr.SetDiffuse(0.78)
    pr.SetAmbient(0.14)
    return ac


def scene():
    acts = []
    for row in ('R1', 'R2'):
        V, T = tess('A1000_%s_blade' % row, 0.01); acts.append(actor(polydata(*instance(V, T, Z[row])), COL[row]))
        V, T = tess('A1000_%s_disc' % row, 0.05); acts.append(actor(polydata(V, T), COL['disc'], spec=0.3))
    for row in ('N1', 'N2'):
        V, T = tess('A1000_%s_vane' % row, 0.01)
        Vi, Ti = instance(V, T, Z[row])
        # vanes in the cut-away (upper half, y > 0) are left out so the rotor blades show
        keep = [k for k in range(Z[row]) if Vi[k * len(V):(k + 1) * len(V), 1].mean() < 0]
        Ti = np.vstack([Ti[k * len(T):(k + 1) * len(T)] for k in keep])
        acts.append(actor(polydata(Vi, Ti), COL[row]))
        V, T = tess('A1000_%s_rings' % row, 0.05, solid=0); acts.append(actor(polydata(V, T), COL['ring'], spec=0.25))
        V, T = tess('A1000_%s_rings' % row, 0.05, solid=1); acts.append(actor(polydata(V, T), COL['ring'], clip=(0, 1, 0), spec=0.25))
    return acts


def render(acts, png, focal, pos, angle, size=(1800, 1250)):
    ren = vtk.vtkRenderer()
    for a in acts: ren.AddActor(a)
    ren.SetBackground(0.10, 0.10, 0.11); ren.SetBackground2(0.32, 0.34, 0.38); ren.GradientBackgroundOn()
    win = vtk.vtkRenderWindow(); win.SetOffScreenRendering(1); win.AddRenderer(ren); win.SetSize(*size); win.SetMultiSamples(8)
    cam = ren.GetActiveCamera(); cam.SetFocalPoint(*focal); cam.SetPosition(*pos); cam.SetViewUp(0, 1, 0); cam.SetViewAngle(angle)
    ren.ResetCameraClippingRange()
    for p, i in (((0.4, 0.8, 1.0), 0.8), ((-1.0, -0.3, 0.6), 0.35), ((0.0, -1.0, -0.4), 0.2)):
        l_ = vtk.vtkLight(); l_.SetLightTypeToCameraLight(); l_.SetPosition(*p); l_.SetIntensity(i); ren.AddLight(l_)
    win.Render()
    w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(win); w2i.Update()
    wr = vtk.vtkPNGWriter(); wr.SetFileName(png); wr.SetInputConnection(w2i.GetOutputPort()); wr.Write(); print('written', png, flush=True)


acts = scene()
render(acts, os.path.join(IMG, 'a1000_turbine_render_iso.png'), (80.0, 20.0, 0.0), (-300.0, 640.0, 900.0), 36)
if os.environ.get('A1000_ISO_ONLY') is None: render(acts, os.path.join(IMG, 'a1000_turbine_render_blades.png'), (60.0, 225.0, 0.0), (-150.0, 330.0, 190.0), 26)
