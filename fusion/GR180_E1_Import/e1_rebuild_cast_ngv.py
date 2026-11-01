"""Rebuild the cast-blank NGV component in a Fusion document from fusion/E1/E1_ngv_rings_cast.step + the machined vane.

Why: Fusion 2706's STEP translator imports E1_ngv_vane_cast.step as a broken (zero-volume) body and takes ~20 min.
Since 2026-10-23 the cast vane is identical to the machined vane (gg_turbine.py CAST_SHROUD_STOCK_U0 = 15.0), so the
healthy vane body of 'GR180 E1 Turbine' is copied with TemporaryBRepManager instead. The rings STEP (20 kB) imports
fine. Used from the Fusion MCP server:

    import importlib.util
    spec = importlib.util.spec_from_file_location('e1ngv', '<repo>/fusion/GR180_E1_Import/e1_rebuild_cast_ngv.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.rebuild('GR180 E1 Turbine (cast blanks)')      # source 'GR180 E1 Turbine' must be open too

Keeps the component name, material ('IN713LC (cast, 8.00 g/cc)') and the occurrence colour override, verifies the
mass (expected 124.4 g from the code) and saves. Logs to cad_out/engine/E1/_rebuild_ngv_log.txt.
"""
import os
import time

import adsk.core
import adsk.fusion

REPO = '/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-v12-backup-20261021-1404'
RINGS = os.path.join(REPO, 'fusion', 'E1', 'E1_ngv_rings_cast.step')
LOG = os.path.join(REPO, 'cad_out', 'engine', 'E1', '_rebuild_ngv_log.txt')
VANES = 21


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a') as f:
        f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
    print(msg)


def open_doc(name):
    app = adsk.core.Application.get()
    for i in range(app.documents.count):
        d = app.documents.item(i)
        if d.name.startswith(name):
            return d
    raise RuntimeError('document not open: ' + name)


def design_of(doc):
    return adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))


def ngv_occurrence(design):
    for occ in design.rootComponent.occurrences:
        if 'NGV' in occ.component.name:
            return occ
    raise RuntimeError('no NGV occurrence')


def import_step(app, occ, path):
    comp = occ.component
    opt = app.importManager.createSTEPImportOptions(path)
    n0 = comp.bRepBodies.count
    occ0 = comp.occurrences.count
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


def ensure_material(design, name, library_names=('Inconel 718', 'Nickel Alloy', 'Steel, Alloy'), density_kg_m3=8000.0):
    """Design material by name; deleting the last user purges it, so re-create it as a copy of a library material
    with the IN713LC density (8.00 g/cc) when missing."""
    m = design.materials.itemByName(name)
    if m:
        return m
    app = adsk.core.Application.get()
    for lib in app.materialLibraries:
        for nm in library_names:
            try:
                base = lib.materials.itemByName(nm)
            except Exception:
                base = None
            if base:
                m = design.materials.addByCopy(base, name)
                try:
                    m.materialProperties.itemById('structural_Density').value = density_kg_m3
                except Exception as e:
                    log('density not set: %s' % e)
                log('material %s re-created from %s' % (name, nm))
                return m
    raise RuntimeError('no library material to copy for ' + name)


def blue_appearance(design):
    """'GR180 NGV (blue)' of fusion/GR180_E1_Colors, created in the design if missing."""
    import importlib.util
    path = os.path.join(REPO, 'fusion', 'GR180_E1_Colors', 'GR180_E1_Colors.py')
    spec = importlib.util.spec_from_file_location('e1colors', path)
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    key, name, rgb = [x for x in c.COLOURS if x[0] == 'NGV'][0]
    return c.coloured(design, c.base_appearance(adsk.core.Application.get()), name, rgb)


MATERIAL = 'IN713LC (cast, 8.00 g/cc)'


def rebuild(cast_doc_name, source_doc_name='GR180 E1 Turbine', save=True, expected_g=124.4, material_name=MATERIAL):
    app = adsk.core.Application.get()
    t0 = time.time()
    log('=== rebuild NGV in %s' % cast_doc_name)
    src = open_doc(source_doc_name)
    vane = None
    for i in range(ngv_occurrence(design_of(src)).component.bRepBodies.count):
        b = ngv_occurrence(design_of(src)).component.bRepBodies.item(i)
        if b.name == 'vane':
            vane = b
            break
    if vane is None:
        raise RuntimeError('vane body not found in ' + source_doc_name)
    tmp = adsk.fusion.TemporaryBRepManager.get().copy(vane)
    log('source vane copied: faces %d' % tmp.faces.count)

    doc = open_doc(cast_doc_name)
    doc.activate()
    design = design_of(doc)
    root = design.rootComponent
    old = ngv_occurrence(design)
    name = old.component.name
    material = old.component.material
    appearance = old.appearance
    log('old component %s: %d bodies, material %s, appearance %s' % (name, old.component.bRepBodies.count, material.name if material else None, appearance.name if appearance else None))
    old.deleteMe()
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = name
    rings = import_step(app, occ, RINGS)
    for b in rings:
        bb = b.boundingBox
        r = max(abs(bb.maxPoint.y), abs(bb.maxPoint.z)) * 10
        b.name = 'rings outer' if r > 30 else 'rings inner + web'
    log('rings imported: %s (%.1f s)' % ([(b.name, b.faces.count) for b in rings], time.time() - t0))
    bf = comp.features.baseFeatures.add()
    bf.startEdit()
    comp.bRepBodies.add(tmp, bf)
    bf.finishEdit()
    bf.name = 'vane (copied from the machined document)'
    vb = comp.bRepBodies.item(comp.bRepBodies.count - 1)
    vb.name = 'vane'
    ents = adsk.core.ObjectCollection.create()
    ents.add(vb)
    pi = comp.features.circularPatternFeatures.createInput(ents, comp.xConstructionAxis)
    pi.quantity = adsk.core.ValueInput.createByReal(VANES)
    pi.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    pi.isSymmetric = False
    pat = comp.features.circularPatternFeatures.add(pi)
    pat.name = 'vanes pattern'
    log('vanes patterned: %d bodies (%.1f s)' % (comp.bRepBodies.count, time.time() - t0))
    # not the old component's material: a rolled-back earlier attempt can leave it on the default 'Steel'
    comp.material = ensure_material(design, material_name)
    # deleting the old occurrence purges its (then unused) colour from design.appearances: re-create it with the
    # colour script and apply it after the material (setting a material clears the override)
    occ.appearance = blue_appearance(design)
    pp = comp.getPhysicalProperties(adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy)
    mass = pp.mass * 1000
    log('mass %.2f g (expected %.1f), volume %.4f cm3, material %s, appearance %s (%.1f s)' % (
        mass, expected_g, pp.volume, comp.material.name if comp.material else None,
        occ.appearance.name if occ.appearance else None, time.time() - t0))
    if abs(mass - expected_g) > 1.5:
        raise RuntimeError('mass %.2f g off the expected %.1f g: not saved' % (mass, expected_g))
    if save:
        ok = doc.save('NGV cast blank rebuilt from E1_ngv_rings_cast.step (shroud-bore stock aft of the vanes only) + machined vane x21; mass %.1f g' % mass)
        log('saved %s' % ok)
    return mass


def run(context):
    try:
        rebuild('GR180 E1 Turbine (cast blanks)')
    except Exception as e:
        adsk.core.Application.get().userInterface.messageBox('Failed: %s' % e)
