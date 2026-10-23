"""Autodesk Fusion helpers for the GR180 E1 turbine-stage drawings (preview drawing API, Fusion 2706+).

Used from the Fusion MCP server with short scripts, e.g.

    import importlib.util
    spec = importlib.util.spec_from_file_location('e1dwg', '<repo>/fusion/GR180_E1_Drawings/GR180_E1_Drawings.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    doc, dwg = m.new_drawing('GR180 E1 Turbine', 'GR180 E1 Blisk machined drawing')
    sheet = dwg.activeSheet
    v = m.base_view(sheet, 'right', 2.0, 120, 150)

or as a Fusion script (Utilities > Scripts and Add-Ins): run() makes one test drawing of the active design.

Sheet space: BaseViewInput.placementPoint is in cm; ViewCurve points and DrawingPoint.create are in the drawing's
length unit as reported by probe_units(). All helpers take millimetres and convert.

What the API can do (2706.1): manual drawing from a design DataFile (ISO/ASME, mm, sheet size), base views
(orientation, scale, style), linear/diameter/radius/angular dimensions on view curves, datum identifiers, feature
control frames, custom tables (used here for the drawing notes), PDF/DWG/DXF export.
Not available: section, projected and detail views, text notes, surface-finish symbols, dimension tolerances.
"""
import os
import json
import math
import traceback

import adsk.core
import adsk.fusion
import adsk.drawing

OUT = '/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-v12-backup-20261021-1404/cad_out/engine/E1'
LOG = os.path.join(OUT, '_drawings_log.txt')

ORIENT = {
    'front': adsk.drawing.ViewOrientationTypes.FrontViewOrientationType,
    'back': adsk.drawing.ViewOrientationTypes.BackViewOrientationType,
    'top': adsk.drawing.ViewOrientationTypes.TopViewOrientationType,
    'bottom': adsk.drawing.ViewOrientationTypes.BottomViewOrientationType,
    'right': adsk.drawing.ViewOrientationTypes.RightViewOrientationType,
    'left': adsk.drawing.ViewOrientationTypes.LeftViewOrientationType,
    'iso': adsk.drawing.ViewOrientationTypes.IsoTopRightViewOrientationType,
}
STYLE = {
    'visible': adsk.drawing.DrawingViewStyleTypes.VisibleEdgesDrawingViewStyleType,
    'hidden': adsk.drawing.DrawingViewStyleTypes.VisibleAndHiddenEdgesDrawingViewStyleType,
    'shaded': adsk.drawing.DrawingViewStyleTypes.ShadedVisibleEdgesDrawingViewStyleType,
}
GDT = {
    'runout': adsk.drawing.GeometricCharacteristicTypes.CircularRunoutGeometricCharacteristicType,
    'total_runout': adsk.drawing.GeometricCharacteristicTypes.TotalRunoutGeometricCharacteristicType,
    'perp': adsk.drawing.GeometricCharacteristicTypes.PerpendicularityGeometricCharacteristicType,
    'coax': adsk.drawing.GeometricCharacteristicTypes.CoaxialityGeometricCharacteristicType,
    'flat': adsk.drawing.GeometricCharacteristicTypes.FlatnessGeometricCharacteristicType,
    'cyl': adsk.drawing.GeometricCharacteristicTypes.CylindricityGeometricCharacteristicType,
    'round': adsk.drawing.GeometricCharacteristicTypes.CircularityGeometricCharacteristicType,
    'profile': adsk.drawing.GeometricCharacteristicTypes.ProfileOfSurfaceGeometricCharacteristicType,
    'position': adsk.drawing.GeometricCharacteristicTypes.PositionGeometricCharacteristicType,
}
CURVE = {0: 'line', 1: 'arc', 2: 'circle', 3: 'ellipse', 4: 'spline', 5: 'polyline'}


def log(msg):
    os.makedirs(OUT, exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(str(msg) + '\n')
    print(msg)


def app():
    return adsk.core.Application.get()


# ---------------------------------------------------------------- data files / documents
def find_datafile(name, project='Default Project'):
    """DataFile with this exact name: open documents first, then the project's root folder (one level)."""
    a = app()
    for i in range(a.documents.count):
        d = a.documents.item(i)
        try:
            if d.dataFile and d.dataFile.name == name:
                return d.dataFile
        except Exception:
            pass
    for p in a.data.dataProjects:
        if p.name != project:
            continue
        for f in p.rootFolder.dataFiles:
            if f.name == name:
                return f
    return None


def open_document(name):
    """Open (or front) the document with this name; returns the Document."""
    a = app()
    for i in range(a.documents.count):
        d = a.documents.item(i)
        if d.name.startswith(name):
            d.activate()
            return d
    df = find_datafile(name)
    if df is None:
        raise RuntimeError('data file not found: ' + name)
    return a.documents.open(df, True)


def drawing_of(doc):
    return adsk.drawing.Drawing.cast(doc.products.itemByProductType('DrawingProductType'))


def new_drawing(design_name, drawing_name=None, sheet='A3', standard='ISO'):
    """Create a manual drawing document from the saved design DataFile and open it. Returns (doc, Drawing)."""
    df = find_datafile(design_name)
    if df is None:
        raise RuntimeError('design data file not found: ' + design_name)
    dm = adsk.drawing.DrawingManager.get()
    inp = dm.createDrawingInput(df, adsk.drawing.DrawingCreationModes.ManualDrawingCreationMode)
    inp.standard = (adsk.drawing.DrawingStandardTypes.ISODrawingStandardType if standard == 'ISO'
                    else adsk.drawing.DrawingStandardTypes.ASMEDrawingStandardType)
    inp.units = adsk.drawing.DrawingUnitTypes.MillimeterDrawingUnitType
    inp.sheetSize = {'A4': adsk.drawing.SheetSizes.A4ISOSheetSize, 'A3': adsk.drawing.SheetSizes.A3ISOSheetSize,
                     'A2': adsk.drawing.SheetSizes.A2ISOSheetSize}[sheet]
    inp.orientationType = adsk.drawing.SheetOrientationTypes.LandscapeSheetOrientationType
    inp.baseDocumentType = adsk.drawing.BaseDocumentTypes.FromScratchBaseDocumentType
    ddf = dm.createDrawing(inp)
    if ddf is None:
        raise RuntimeError('createDrawing returned null')
    if drawing_name:
        try:
            ddf.name = drawing_name
        except Exception:
            log('rename failed: ' + traceback.format_exc())
    a = app()
    doc = a.activeDocument
    dwg = drawing_of(doc) if doc else None
    if dwg is None:
        doc = a.documents.open(ddf, True)
        dwg = drawing_of(doc)
    return doc, dwg


# ---------------------------------------------------------------- views and curves
def base_view(sheet, orient, scale, x_mm, y_mm, style='visible', tangent='off'):
    vi = sheet.views.createBaseViewInput()
    vi.placementPoint = adsk.core.Point2D.create(x_mm / 10.0, y_mm / 10.0)   # cm
    vp = vi.viewParameters
    vp.orientation = ORIENT[orient]
    vp.scaleValue = scale
    vp.style = STYLE[style]
    try:
        vp.tangentEdgesType = {'off': adsk.drawing.TangentEdgeDisplayTypes.OffTangentEdgeDisplayType,
                               'full': adsk.drawing.TangentEdgeDisplayTypes.FullLengthTangentEdgeDisplayType,
                               'short': adsk.drawing.TangentEdgeDisplayTypes.ShortenedTangentEdgeDisplayType}[tangent]
    except Exception:
        pass
    v = sheet.views.add(vi)
    if v is None:
        raise RuntimeError('views.add returned null')
    return v


def p2(pt):
    return (round(pt.x, 4), round(pt.y, 4))


def curve_info(view, limit=None):
    """List of (index, type, start, end, mid/center, radius) in sheet units for the view's curves."""
    out = []
    vc = view.viewCurves
    n = vc.count if limit is None else min(vc.count, limit)
    for i in range(n):
        c = vc.item(i)
        t = CURVE.get(c.type, str(c.type))
        s = e = m = r = None
        try:
            s = p2(c.startPoint.geometry)
            e = p2(c.endPoint.geometry)
        except Exception:
            pass
        try:
            if t == 'line':
                m = p2(c.midPoint.geometry)
            elif t in ('arc', 'circle', 'spline'):
                cp = c.centerPoint.geometry
                m = p2(cp)
                if s:
                    r = round(math.hypot(s[0] - cp.x, s[1] - cp.y), 4)
        except Exception:
            pass
        out.append((i, t, s, e, m, r))
    return out


def find_circle(view, radius_mm, scale, unit=1.0, tol=0.02):
    """Circle/arc view curve whose radius matches radius_mm * scale (sheet units: unit = mm per sheet unit)."""
    want = radius_mm * scale / unit
    best = None
    for i, t, s, e, m, r in curve_info(view):
        if t in ('circle', 'arc') and r is not None and abs(r - want) <= tol * max(1.0, want):
            if best is None or abs(r - want) < best[1]:
                best = (i, abs(r - want))
    return view.viewCurves.item(best[0]) if best else None


def find_line(view, pa_mm, pb_mm, center_mm, scale, unit=1.0, tol_mm=0.15):
    """Line view curve whose end points match two model-plane points (mm, 2D in the view plane), given the view's
    model centre (mm) and sheet centre (sheet units) found with view_center()."""
    cx, cy, sx, sy = center_mm
    def sheet(p):
        return ((p[0] - cx) * scale / unit + sx, (p[1] - cy) * scale / unit + sy)
    a = sheet(pa_mm); b = sheet(pb_mm)
    tol = tol_mm * scale / unit
    for i, t, s, e, m, r in curve_info(view):
        if t != 'line' or s is None:
            continue
        d1 = math.hypot(s[0] - a[0], s[1] - a[1]) + math.hypot(e[0] - b[0], e[1] - b[1])
        d2 = math.hypot(s[0] - b[0], s[1] - b[1]) + math.hypot(e[0] - a[0], e[1] - a[1])
        if min(d1, d2) <= 2 * tol:
            return view.viewCurves.item(i)
    return None


def dpoint(x, y):
    return adsk.drawing.DrawingPoint.create(adsk.core.Point2D.create(x, y))


# ---------------------------------------------------------------- annotations
def dim_diameter(sheet, curve, x, y):
    return sheet.drawingDimensions.addDiameterDimension(curve, dpoint(x, y))


def dim_radius(sheet, curve, x, y):
    return sheet.drawingDimensions.addRadialDimension(curve, dpoint(x, y))


def dim_linear(sheet, p1, p2_, place, aligned=False):
    """p1, p2_: DrawingPoint (from a view curve accessor, associative) or (x, y) tuples in sheet units."""
    a = p1 if not isinstance(p1, tuple) else dpoint(*p1)
    b = p2_ if not isinstance(p2_, tuple) else dpoint(*p2_)
    return sheet.drawingDimensions.addLinearDimension(a, b, dpoint(*place), aligned)


def datum(sheet, letter, curve, attach, box):
    """Datum identifier 'letter' attached to a view curve; attach and box are (x, y) in sheet units."""
    di = sheet.drawingSymbols.createDatumIdentifierInput()
    di.identifier = letter
    di.viewCurve = curve
    di.leaderPoints = [dpoint(*attach), dpoint(*box)]
    di.placementPoint = dpoint(*box)
    s = sheet.drawingSymbols.addDatumIdentifier(di)
    if s is None:
        raise RuntimeError('datum %s not created' % letter)
    return s


def fcf(sheet, char, tol, datums, curve, attach, box, second=None):
    """Feature control frame: char from GDT, tol string ('0.02'), datums list of up to 3 letters."""
    fi = sheet.drawingSymbols.createFeatureControlFrameInput()
    fr = fi.firstFrame
    fr.geometricCharacteristic = GDT[char]
    fr.primaryTolerance = tol
    for attr, d in zip(('primaryDatum', 'secondaryDatum', 'tertiaryDatum'), datums):
        setattr(fr, attr, d)
    if second:
        fi.isSecondFrameEnabled = True
        fr2 = fi.secondFrame
        fr2.geometricCharacteristic = GDT[second[0]]
        fr2.primaryTolerance = second[1]
        for attr, d in zip(('primaryDatum', 'secondaryDatum', 'tertiaryDatum'), second[2]):
            setattr(fr2, attr, d)
    if curve is not None:
        fi.viewCurve = curve
    fi.leaderPoints = [dpoint(*attach), dpoint(*box)]
    fi.placementPoint = dpoint(*box)
    s = sheet.drawingSymbols.addFeatureControlFrame(fi)
    if s is None:
        raise RuntimeError('FCF not created')
    return s


def notes_table(sheet, title, lines):
    """One-column custom table: row 0 = title, then one note per row."""
    ti = sheet.customTables.createInput()
    ti.rowCount = len(lines) + 1
    ti.columnCount = 1
    t = sheet.customTables.add(ti)
    if t is None:
        raise RuntimeError('custom table not created')
    t.setCellData(0, 0, title)
    for i, s in enumerate(lines):
        t.setCellData(i + 1, 0, s)
    return t


def export_pdf(dwg, filename):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, filename)
    em = dwg.exportManager
    opt = em.createPDFExportOptions(path)
    try:
        opt.openPDF = False
    except Exception:
        pass
    ok = em.execute(opt)
    return path if ok else None


def probe_units(sheet):
    """Sheet width/height as the API reports them (A3 = 42.0 x 29.7 if cm, 420 x 297 if mm)."""
    return sheet.width, sheet.height


def save(doc, description):
    return doc.save(description)


def run(context):
    """Interactive test: one drawing of the active design with two base views."""
    ui = None
    try:
        a = app(); ui = a.userInterface
        src = a.activeDocument
        if not src.dataFile:
            ui.messageBox('Save the design first.'); return
        doc, dwg = new_drawing(src.dataFile.name, src.dataFile.name + ' drawing (test)')
        sheet = dwg.activeSheet
        base_view(sheet, 'right', 1.0, 120, 150)
        base_view(sheet, 'front', 1.0, 300, 150)
        ui.messageBox('Drawing created: %s, sheet %s x %s' % (doc.name, sheet.width, sheet.height))
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
