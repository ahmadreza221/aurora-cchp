"""Autodesk Fusion script: the whole AURORA-1000 package (1 MW, 15,000 rpm, geared) from fusion/A1000_pkg/pkg.json.

Utilities > Scripts and Add-Ins > + (My Scripts) > pick this folder > Run. Builds a new direct-modelling design with one
component per group (turbine, NGVs, rotor, compressor, casings, combustor, exhaust, bearings, recuperator, gearbox,
generator, lube module, skid) and one sub-component per part, coloured as the web viewer; casings, ducts and the
recuperator are see-through so the rotor stays visible.
  turbine rows : the rev 5 pieces from fusion/A1000 (same files as AURORA1000_Import), moved by x_offset_turbine and
                 patterned (NGV1 48, blisk 1 59, NGV2 24, blisk 2 36)
  the rest     : the rotor-dynamics shaft segments, the meanline impellers and the concept envelopes of docs/08
Frame: rotor frame of sim/engine/a1000_rotordynamics.py, mm, X = engine axis from the gearbox coupling face (x = 0) to
the exhaust, Z up. Regenerate the parts with
  A1000_STEP=1 freecadcmd -c "exec(open('cad/engine/a1000_viewer_export.py').read())"
"""
import json
import math
import os
import traceback

import adsk.core
import adsk.fusion

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.normpath(os.path.join(HERE, '..', 'A1000_pkg'))
VERIFY = os.path.normpath(os.path.join(HERE, '..', '_a1000_pkg_verify.json'))
LABEL = {'turbine': 'Turbine blisks', 'ngv': 'Turbine NGVs', 'rotor': 'Rotor shaft', 'comp': 'Compressor impellers',
         'casing': 'Casings and inlet', 'comb': 'Combustor', 'exhaust': 'Exhaust', 'bearing': 'Bearings',
         'recup': 'Recuperator', 'gearbox': 'Gearbox', 'gen': 'Generator', 'aux': 'Lube oil', 'skid': 'Skid'}
OPACITY = {'casing': 0.22, 'exhaust': 0.30, 'recup': 0.30, 'comb': 0.45}       # by group, 1.0 otherwise
OPACITY_PART = {'Turbine casing insulation': 0.10, 'Air inlet plenum + bellmouth': 0.15}


def clean(name):
    return ''.join('-' if c in ':/\\*?"<>|' else c for c in name)


def import_step(app, comp, path):
    """Import a STEP file into comp and return its solids as temporary B-Reps (component coordinates); the translator's
    child occurrence is removed, so the caller adds the bodies to comp itself (direct design)."""
    occ0 = comp.occurrences.count
    app.importManager.importToTarget(app.importManager.createSTEPImportOptions(path), comp)
    tbm = adsk.fusion.TemporaryBRepManager.get()
    stale = [comp.occurrences.item(i) for i in range(occ0, comp.occurrences.count)]
    temps = [tbm.copy(c.component.bRepBodies.item(j)) for c in stale for j in range(c.component.bRepBodies.count)]
    for c in stale:
        c.deleteMe()
    return temps


def libraries(app):
    libs = app.materialLibraries
    for i in range(libs.count):
        try:
            yield libs.item(i)
        except Exception:                                           # a broken / unnamed library (seen on Fusion 2706)
            pass


def base_appearance(app):
    for lib in libraries(app):
        for nm in ('Paint - Enamel Glossy (White)', 'Plastic - Glossy (White)', 'Paint - Metallic (White)'):
            try:
                a = lib.appearances.itemByName(nm)
            except Exception:
                a = None
            if a:
                return a
    return None


def coloured(design, base, name, rgb):
    a = design.appearances.itemByName(name)
    if not a:
        a = design.appearances.addByCopy(base, name)
    for p in a.appearanceProperties:
        if p.objectType == adsk.core.ColorProperty.classType():
            cp = adsk.core.ColorProperty.cast(p)
            if cp.id in ('opaque_albedo', 'generic_diffuse', 'metal_f0') or cp.name.lower() in ('color', 'colour'):
                cp.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
    return a


def build(app, log):
    pkg = json.load(open(os.path.join(PKG, 'pkg.json')))
    base = base_appearance(app)
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        return doc, fill(app, doc, pkg, base, log)
    except Exception:
        doc.close(False)                                            # the new, unsaved design made above
        raise


def fill(app, doc, pkg, base, log):
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    root = design.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()
    groups, out = {}, dict(parts={}, bodies=0)
    for p in pkg['parts']:
        g = p['group']
        if g not in groups:
            occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            occ.component.name = 'A1000 ' + LABEL.get(g, g)
            groups[g] = occ.component
        m = adsk.core.Matrix3D.create(); m.translation = adsk.core.Vector3D.create(p['dx'] / 10.0, 0, 0)     # cm
        socc = groups[g].occurrences.addNewComponent(m); sub = socc.component
        sub.name = clean(p['name']); sub.opacity = OPACITY_PART.get(p['name'], OPACITY.get(g, 1.0))
        if base:
            socc.appearance = coloured(design, base, 'A1000 ' + g, pkg['groups'][g]['rgb'])
        temps = import_step(app, sub, os.path.normpath(os.path.join(PKG, p['step'])))
        for k, ang in enumerate(p['inst'], 1):                      # instances of one blade / vane about the X axis
            rot = adsk.core.Matrix3D.create()
            rot.setToRotation(math.radians(ang), adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
            for t in temps:
                c = tbm.copy(t); tbm.transform(c, rot)
                sub.bRepBodies.add(c).name = clean(p['name']).split(' x')[0] + (' %d' % k if len(p['inst']) > 1 else '')
        out['parts'][p['name']] = sub.bRepBodies.count; out['bodies'] += sub.bRepBodies.count
        log('%-40s %4d bodies' % (p['name'], sub.bRepBodies.count))
    bb = root.boundingBox
    out['bbox_mm'] = [[round(bb.minPoint.x * 10), round(bb.minPoint.y * 10), round(bb.minPoint.z * 10)],
                      [round(bb.maxPoint.x * 10), round(bb.maxPoint.y * 10), round(bb.maxPoint.z * 10)]]
    return out


def run(context):
    ui = None
    lines = []

    def log(s):
        lines.append(s)
        with open(VERIFY[:-5] + '.log', 'w') as f:
            f.write('\n'.join(lines))
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        doc, out = build(app, log)
        with open(VERIFY, 'w') as f:
            f.write(json.dumps(out, indent=1))
        app.activeViewport.fit()
        if ui and context is not None:
            ui.messageBox('AURORA-1000 package: %d parts, %d bodies, bbox %s mm' % (len(out['parts']), out['bodies'], out['bbox_mm']))
    except Exception:
        log(traceback.format_exc())
        if ui and context is not None:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        else:
            raise
