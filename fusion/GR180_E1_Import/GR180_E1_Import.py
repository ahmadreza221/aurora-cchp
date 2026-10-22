"""Autodesk Fusion script: build the GR180-CCHP E1 turbine stage from the compact STEP parts in fusion/E1/.

Utilities > Scripts and Add-Ins > + (My Scripts) > pick this folder > Run. Imports into a new design:
  E1 blisk (final)  : bore-less disc + 1 blade, blade patterned 29 x about the engine axis, joined
  E1 NGV (final)    : inner / outer rings + 1 vane, vane patterned 21 x, joined
  E1 shaft          : welded stub shaft (42CrMo4)
Engine frame: X = engine axis, mm (as cad/engine/gg_turbine.py). Set KIND = 'cast' for the cast blanks.
Geometry comes from the Python design code; change it there and re-export (fusion/export_e1_parts.py), not in Fusion.
"""
import os
import traceback

import adsk.core
import adsk.fusion

KIND = 'final'            # 'final' (machined) or 'cast' (investment-cast blank with stock)
JOIN = True               # join the patterned blades / vanes into one body (slow: a few minutes)
HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, '..', 'E1')


def import_step(app, comp, name):
    path = os.path.normpath(os.path.join(PARTS, name + '.step'))
    if not os.path.exists(path):
        raise RuntimeError('missing ' + path + ' (run fusion/export_e1_parts.py)')
    opt = app.importManager.createSTEPImportOptions(path)
    before = comp.bRepBodies.count
    app.importManager.importToTarget(opt, comp)
    # STEP import may create a child occurrence; collect bodies from the component and its children
    bodies = [comp.bRepBodies.item(i) for i in range(before, comp.bRepBodies.count)]
    if not bodies:
        for occ in comp.occurrences:
            bodies += [occ.bRepBodies.item(i) for i in range(occ.bRepBodies.count)]
    return bodies


def new_comp(root, name):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ.component


def pattern_join(comp, base, tool, n, name):
    """Circular pattern of the tool body about the component X axis (n instances over 360 deg), optionally joined to base."""
    ents = adsk.core.ObjectCollection.create(); ents.add(tool)
    pi = comp.features.circularPatternFeatures.createInput(ents, comp.xConstructionAxis)
    pi.quantity = adsk.core.ValueInput.createByReal(n)
    pi.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    pi.isSymmetric = False
    pat = comp.features.circularPatternFeatures.add(pi)
    pat.name = name + ' pattern'
    if not JOIN:
        return
    tools = adsk.core.ObjectCollection.create()
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b != base:
            tools.add(b)
    ci = comp.features.combineFeatures.createInput(base, tools)
    ci.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    comp.features.combineFeatures.add(ci).name = name + ' join'


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
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        root = design.rootComponent; root.name = 'GR180 E1 turbine stage (%s)' % KIND

        c = new_comp(root, 'E1 blisk IN713LC (%s)' % KIND)
        disc = import_step(app, c, 'E1_disc_boreless_' + KIND)[0]; disc.name = 'disc'
        blade = import_step(app, c, 'E1_blade_' + KIND)[0]; blade.name = 'blade'
        pattern_join(c, disc, blade, 29, 'blades')
        set_material(app, c, ['Nickel Alloy', 'Inconel 718', 'Nickel'])

        c = new_comp(root, 'E1 NGV ring IN713LC (%s)' % KIND)
        rings = import_step(app, c, 'E1_ngv_rings_' + KIND)
        vane = import_step(app, c, 'E1_ngv_vane_' + KIND)[0]; vane.name = 'vane'
        base = rings[0]; base.name = 'rings'
        pattern_join(c, base, vane, 21, 'vanes')
        set_material(app, c, ['Nickel Alloy', 'Inconel 718', 'Nickel'])

        c = new_comp(root, 'E1 shaft 42CrMo4 (welded)')
        import_step(app, c, 'E1_shaft_welded')[0].name = 'shaft'
        set_material(app, c, ['Steel AISI 4140 207 HB', 'Steel, Alloy', 'Steel'])

        app.activeViewport.fit()
        ui.messageBox('GR180 E1 (%s) imported: blisk 29 blades, NGV 21 vanes, welded shaft.\nEngine axis = X, mm.' % KIND)
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
