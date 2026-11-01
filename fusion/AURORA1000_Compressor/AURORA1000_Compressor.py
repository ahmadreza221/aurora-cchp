"""Autodesk Fusion script: build the two AURORA-1000 compressor impellers from the compact STEP parts in fusion/A1000C/.

Utilities > Scripts and Add-Ins > + (My Scripts) > pick this folder > Run. Imports into a new design, coloured:
  A1000 impeller 1: turned hub + 1 main blade + 1 splitter, both patterned 13 x   (light blue)
  A1000 impeller 2: same                                                          (violet-grey)
  material of each impeller from fusion/A1000C/parts.json (rev 1: both Ti-6Al-4V)
The blades are ruled surfaces (5-axis flank milling, both sides straight lines hub -> tip) with the root fillet of the
cutter ball. Frame: rotor frame of sim/engine/a1000_rotordynamics.py, X = engine axis from the gearbox coupling face, mm
(the same frame as the package, fusion/AURORA1000_Package). Counts, revision and the expected masses are read from
fusion/A1000C/parts.json. Geometry comes from the Python design code (cad/engine/a1000_impeller.py); change it there and
re-export (--cad, then python3 fusion/export_a1000_impellers.py), never edit the surfaces in Fusion.
"""
import os
import json
import traceback

import adsk.core
import adsk.fusion

JOIN = False              # join the patterned blades into the hub (one body per impeller; slow)
HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, '..', 'A1000C')
VERIFY = os.path.normpath(os.path.join(HERE, '..', '_a1000c_verify.json'))
STAGES = [('C1', 'A1000 impeller 1 %s (13 + 13)', (150, 186, 222)), ('C2', 'A1000 impeller 2 %s (13 + 13)', (172, 160, 196))]
LIBMAT = {'Al 2618-T61': ['Aluminum 2618', 'Aluminum', 'Aluminum 6061'],          # Fusion library names to try
          'Ti-6Al-4V': ['Titanium 6AL-4V', 'Titanium Ti-6Al-4V', 'Titanium']}


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


def pattern(comp, body, n, name):
    """circular pattern of one body about the component X axis, n over 360 deg"""
    ents = adsk.core.ObjectCollection.create(); ents.add(body)
    pi = comp.features.circularPatternFeatures.createInput(ents, comp.xConstructionAxis)
    pi.quantity = adsk.core.ValueInput.createByReal(n)
    pi.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    pi.isSymmetric = False
    comp.features.circularPatternFeatures.add(pi).name = name + ' pattern'


def join_all(comp, base, name):
    tools = adsk.core.ObjectCollection.create()
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b != base:
            tools.add(b)
    ci = comp.features.combineFeatures.createInput(base, tools)
    ci.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    comp.features.combineFeatures.add(ci).name = name + ' join'


def libraries(app):
    libs = app.materialLibraries
    for i in range(libs.count):
        try:
            yield libs.item(i)
        except Exception:
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


def set_material(app, comp, names):
    for lib in libraries(app):
        for nm in names:
            try:
                m = lib.materials.itemByName(nm)
            except Exception:
                m = None
            if m:
                comp.material = m
                return nm
    return None


def build(app, doc):
    meta = json.load(open(os.path.join(PARTS, 'parts.json')))
    Z = int(meta['pattern']['Z']); rho = meta['pattern']['density_g_cc']
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    root = design.rootComponent
    base_app = base_appearance(app)
    out = {'revision': meta['pattern'].get('revision', ''), 'components': {}, 'expected': meta.get('expected', {})}
    for key, cfmt, rgb in STAGES:
        mname = meta['pattern']['materials'][key]; cname = cfmt % mname; mats = LIBMAT.get(mname, [])
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()); occ.component.name = cname
        c = occ.component
        hub = import_step(app, occ, 'A1000_%s_hub' % key)[0]; hub.name = 'hub'
        blade = import_step(app, occ, 'A1000_%s_blade' % key)[0]; blade.name = 'blade'
        split = import_step(app, occ, 'A1000_%s_splitter' % key)[0]; split.name = 'splitter'
        pattern(c, blade, Z, 'blades'); pattern(c, split, Z, 'splitters')
        if JOIN:
            join_all(c, hub, 'impeller')
        mat = set_material(app, c, mats)
        if base_app:
            occ.appearance = coloured(design, base_app, cname.split(' (')[0], rgb)
        vol = sum(c.bRepBodies.item(i).physicalProperties.volume for i in range(c.bRepBodies.count))   # cm^3
        out['components'][key] = dict(name=cname, bodies=c.bRepBodies.count, volume_cm3=round(vol, 2), material=mat,
                                      mass_kg=round(vol * rho[key] / 1e3, 3))
    return out


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        out = build(app, doc)
        with open(VERIFY, 'w') as f:
            f.write(json.dumps(out, indent=2))
        app.activeViewport.fit()
        if ui and context is not None:
            ui.messageBox('AURORA-1000 impellers (%s) imported: %s.\nEngine axis = X, mm. Masses in fusion/_a1000c_verify.json.' % (
                out['revision'], ', '.join('%s %.2f kg' % (k, v['mass_kg']) for k, v in out['components'].items())))
    except Exception:
        if ui and context is not None:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        try:
            with open(VERIFY, 'w') as f:
                f.write(json.dumps({'error': traceback.format_exc()}, indent=2))
        except Exception:
            pass
