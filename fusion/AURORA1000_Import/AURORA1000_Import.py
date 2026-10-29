"""Autodesk Fusion script: build the AURORA-1000 two-stage turbine (rev 3) from the compact STEP parts in fusion/A1000/.

Utilities > Scripts and Add-Ins > + (My Scripts) > pick this folder > Run. Imports into a new design, coloured:
  A1000 NGV1   : inner / outer rings + 1 vane, vane patterned 43 x   (MAR-M247 + TBC, orange)
  A1000 blisk 1: bore-less disc + 1 blade, blade patterned 59 x      (MAR-M247, silver)
  A1000 NGV2   : rings + 1 vane, patterned 47 x                      (MAR-M247, light orange)
  A1000 blisk 2: disc + 1 blade, patterned 36 x                      (MAR-M247, blue-grey)
Engine frame: X = engine axis (flow +x from the NGV1 leading edge), mm, as cad/engine/a1000_turbine.py. Counts and the
expected masses are read from fusion/A1000/parts.json. Geometry comes from the Python design code; change it there and
re-export (cad/engine/a1000_turbine.py --cad, then copy the pieces to fusion/A1000/), never edit the surfaces in Fusion.
The rim thermal-relief slots of the blisks (EDM, docs/08 section 12.9) are not in the CAD yet.
"""
import os
import json
import traceback

import adsk.core
import adsk.fusion

JOIN = True               # join the patterned blades / vanes into one body per row (slow: a few minutes per row)
HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, '..', 'A1000')
VERIFY = os.path.normpath(os.path.join(HERE, '..', '_a1000_verify.json'))
RHO = 8.54                # MAR-M247 g/cc (design-record density, independent of the library material)
ROWS = [  # component name, rings / disc file, vane / blade file, count key, colour
    ('A1000 NGV1 MAR-M247 (43 vanes)', 'A1000_N1_rings', 'A1000_N1_vane', 'N1', (222, 132, 76)),
    ('A1000 blisk 1 MAR-M247 (59 blades)', 'A1000_R1_disc', 'A1000_R1_blade', 'R1', (190, 194, 204)),
    ('A1000 NGV2 MAR-M247 (47 vanes)', 'A1000_N2_rings', 'A1000_N2_vane', 'N2', (226, 164, 97)),
    ('A1000 blisk 2 MAR-M247 (36 blades)', 'A1000_R2_disc', 'A1000_R2_blade', 'R2', (150, 170, 199)),
]


def import_step(app, occ, name):
    """Import a STEP file into occ.component; the translator's child occurrence is dissolved (bodies moved up)."""
    comp = occ.component
    path = os.path.normpath(os.path.join(PARTS, name + '.step'))
    if not os.path.exists(path):
        raise RuntimeError('missing ' + path)
    opt = app.importManager.createSTEPImportOptions(path)
    n0 = comp.bRepBodies.count; occ0 = comp.occurrences.count
    app.importManager.importToTarget(opt, comp)
    stale = [comp.occurrences.item(i) for i in range(occ0, comp.occurrences.count)]
    for child in stale:
        for b in [child.bRepBodies.item(j) for j in range(child.bRepBodies.count)]:
            b.moveToComponent(occ)
    for child in stale:
        try:
            child.deleteMe()
        except Exception:
            pass
    return [comp.bRepBodies.item(i) for i in range(n0, comp.bRepBodies.count)]


def pattern_join(comp, bases, tool, n, name):
    """Circular pattern of the tool body about the component X axis (n over 360 deg), then join to the first base body.
    NGV rings are two bodies (inner, outer): the vanes join both, so the whole row becomes one body."""
    ents = adsk.core.ObjectCollection.create(); ents.add(tool)
    pi = comp.features.circularPatternFeatures.createInput(ents, comp.xConstructionAxis)
    pi.quantity = adsk.core.ValueInput.createByReal(n)
    pi.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    pi.isSymmetric = False
    comp.features.circularPatternFeatures.add(pi).name = name + ' pattern'
    if not JOIN:
        return
    tools = adsk.core.ObjectCollection.create()
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b != bases[0]:
            tools.add(b)
    ci = comp.features.combineFeatures.createInput(bases[0], tools)
    ci.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    comp.features.combineFeatures.add(ci).name = name + ' join'


def base_appearance(app):
    for lib in app.materialLibraries:
        for nm in ('Paint - Enamel Glossy (White)', 'Plastic - Glossy (White)', 'Paint - Metallic (White)'):
            try:
                a = lib.appearances.itemByName(nm)
            except Exception:
                a = None
            if a:
                return a
    for lib in app.materialLibraries:
        for i in range(lib.appearances.count):
            a = lib.appearances.item(i)
            if any(p.objectType == adsk.core.ColorProperty.classType() for p in a.appearanceProperties):
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


def set_material(app, comp, names):
    for lib in app.materialLibraries:
        for nm in names:
            try:
                m = lib.materials.itemByName(nm)
            except Exception:
                m = None
            if m:
                comp.material = m
                return nm
    return None


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        meta = json.load(open(os.path.join(PARTS, 'parts.json')))
        Z = meta['pattern']['Z']
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        root = design.rootComponent
        base_app = base_appearance(app)
        out = {'components': {}, 'expected': meta.get('expected', {})}
        for cname, fbase, fpiece, key, rgb in ROWS:
            occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()); occ.component.name = cname
            c = occ.component
            bases = import_step(app, occ, fbase)
            piece = import_step(app, occ, fpiece)[0]; piece.name = 'vane' if key.startswith('N') else 'blade'
            for i, b in enumerate(bases):
                b.name = ('rings %d' % (i + 1)) if key.startswith('N') else 'disc'
            pattern_join(c, bases, piece, int(Z[key]), 'vanes' if key.startswith('N') else 'blades')
            set_material(app, c, ['Nickel Alloy', 'Inconel 718', 'Nickel'])
            if base_app:
                occ.appearance = coloured(design, base_app, cname.split(' MAR')[0], rgb)
            vol = sum(c.bRepBodies.item(i).physicalProperties.volume for i in range(c.bRepBodies.count))   # cm^3
            out['components'][key] = dict(name=cname, bodies=c.bRepBodies.count, volume_cm3=round(vol, 2),
                                          mass_kg=round(vol * RHO / 1e3, 3))
        with open(VERIFY, 'w') as f:
            f.write(json.dumps(out, indent=2))
        app.activeViewport.fit()
        if ui and context is not None:
            ui.messageBox('AURORA-1000 turbine imported: NGV1 43, blisk 1 59, NGV2 47, blisk 2 36.\n'
                          'Engine axis = X, mm. Masses in fusion/_a1000_verify.json.')
    except Exception:
        if ui and context is not None:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        try:
            with open(VERIFY, 'w') as f:
                f.write(json.dumps({'error': traceback.format_exc()}, indent=2))
        except Exception:
            pass
