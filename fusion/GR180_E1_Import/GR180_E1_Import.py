"""Autodesk Fusion script: build the GR180-CCHP E1 turbine stage from the compact STEP parts in fusion/E1/.

Utilities > Scripts and Add-Ins > + (My Scripts) > pick this folder > Run. Imports into a new design:
  E1 blisk (final)  : bore-less disc + 1 blade, blade patterned 29 x about the engine axis, joined
  E1 NGV (final)    : inner / outer rings + 1 vane, vane patterned 21 x, joined
  E1 shaft          : welded stub shaft (42CrMo4)
Engine frame: X = engine axis, mm (as cad/engine/gg_turbine.py). Set KIND = 'cast' for the cast blanks.
Geometry comes from the Python design code; change it there and re-export (fusion/export_e1_parts.py), not in Fusion.
"""
import os
import json
import traceback

import adsk.core
import adsk.fusion

KIND = 'final'            # 'final' (machined) or 'cast' (investment-cast blank with stock)
JOIN = True               # join the patterned blades / vanes into one body (slow: a few minutes)
HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, '..', 'E1')
# written by run(); density in g/cc (IN713LC 8.00, 42CrMo4 7.85) for mass checks independent of the library material
VERIFY = os.path.normpath(os.path.join(HERE, '..', '_e1_verify.json'))
RHO = {'blisk': 8.00, 'ngv': 8.00, 'shaft': 7.85}


def import_step(app, occ, name):
    """Import a compact STEP file into occ.component.

    Fusion's STEP translator drops the body into a NEW CHILD occurrence of the target rather than into the
    component itself. Move those bodies up into occ.component and delete the empty translator occurrence, so the
    returned bodies live in the component and can be patterned / joined there. Returns the bodies added by this call.
    """
    comp = occ.component
    path = os.path.normpath(os.path.join(PARTS, name + '.step'))
    if not os.path.exists(path):
        raise RuntimeError('missing ' + path + ' (run fusion/export_e1_parts.py)')
    opt = app.importManager.createSTEPImportOptions(path)
    n0 = comp.bRepBodies.count
    occ0 = comp.occurrences.count
    app.importManager.importToTarget(opt, comp)
    # any occurrence beyond occ0 is a fresh STEP-translator child: move its bodies into comp, then remove it
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


def new_comp(root, name):
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ


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


def write_verify(comps, kind):
    """Dump volume (cm^3), mass (g at the IN713LC/42CrMo4 density) and bbox (mm) per component to VERIFY json.

    Fusion internal length unit is cm, so physicalProperties.volume is cm^3 and boundingBox coords are cm. Mass is
    computed from volume x RHO rather than the assigned library material, so it matches the design-record density."""
    out = {'kind': kind, 'components': {}}
    for key, comp in comps.items():
        vol = 0.0
        xs = []; ys = []; zs = []
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
            vol += b.physicalProperties.volume  # cm^3
            bb = b.boundingBox
            xs += [bb.minPoint.x, bb.maxPoint.x]
            ys += [bb.minPoint.y, bb.maxPoint.y]
            zs += [bb.minPoint.z, bb.maxPoint.z]
        mm = 10.0
        out['components'][key] = {
            'bodies': comp.bRepBodies.count,
            'volume_cm3': round(vol, 4),
            'mass_g': round(vol * RHO[key], 3),
            'x_min_mm': round(min(xs) * mm, 3), 'x_max_mm': round(max(xs) * mm, 3),
            'y_half_mm': round((max(ys) - min(ys)) / 2 * mm, 3),
            'z_half_mm': round((max(zs) - min(zs)) / 2 * mm, 3),
        }
    with open(VERIFY, 'w') as f:
        f.write(json.dumps(out, indent=2))


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        root = design.rootComponent  # root component name is read-only; the design is named on save instead

        occ = new_comp(root, 'E1 blisk IN713LC (%s)' % KIND); c = occ.component
        disc = import_step(app, occ, 'E1_disc_boreless_' + KIND)[0]; disc.name = 'disc'
        blade = import_step(app, occ, 'E1_blade_' + KIND)[0]; blade.name = 'blade'
        pattern_join(c, disc, blade, 29, 'blades')
        set_material(app, c, ['Nickel Alloy', 'Inconel 718', 'Nickel'])

        occ = new_comp(root, 'E1 NGV ring IN713LC (%s)' % KIND); n = occ.component
        rings = import_step(app, occ, 'E1_ngv_rings_' + KIND)
        vane = import_step(app, occ, 'E1_ngv_vane_' + KIND)[0]; vane.name = 'vane'
        base = rings[0]; base.name = 'rings'
        pattern_join(n, base, vane, 21, 'vanes')
        set_material(app, n, ['Nickel Alloy', 'Inconel 718', 'Nickel'])

        occ = new_comp(root, 'E1 shaft 42CrMo4 (welded)'); s = occ.component
        import_step(app, occ, 'E1_shaft_welded')[0].name = 'shaft'
        set_material(app, s, ['Steel AISI 4140 207 HB', 'Steel, Alloy', 'Steel'])

        write_verify({'blisk': c, 'ngv': n, 'shaft': s}, KIND)
        app.activeViewport.fit()
        if ui and context is not None:  # interactive add-in run; stay silent when driven headless (context None)
            ui.messageBox('GR180 E1 (%s) imported: blisk 29 blades, NGV 21 vanes, welded shaft.\nEngine axis = X, mm.' % KIND)
    except Exception:
        if ui and context is not None:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        try:
            with open(VERIFY, 'w') as f:
                f.write(json.dumps({'error': traceback.format_exc()}, indent=2))
        except Exception:
            pass
