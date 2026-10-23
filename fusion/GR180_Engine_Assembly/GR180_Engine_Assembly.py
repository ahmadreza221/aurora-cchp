"""Autodesk Fusion script: the whole GR180-CCHP engine as it is designed today, one component per subsystem.

  Core GR180 v13A          cad_out/v13A/asm_parts/*.step   (minus parts replaced by E1 / E2 / E3)
  E1 GG turbine stage      fusion/E1/*.step                (blisk 29 blades, NGV 21 vanes, welded shaft)
  E2 combustor             cad_out/engine/E2/*.step when built; until then the v13A combustor as a stand-in
  E3 interduct+FPT+PMG     cad_out/engine/E3/E3-*.step
  E4 recuperator           cad_out/engine/E4/E4_*.step     (ROOF mm -> ENG mm: -1680, -7850, -600)
Engine frame: X = engine axis, mm (ENG). Geometry comes from the Python design code; change it there, not in Fusion.

Utilities > Scripts and Add-Ins > + > pick this folder > Run (all sections in one go). The MCP driver runs it section
by section (SECTIONS) so each call stays short.
"""
import os
import glob

import adsk.core
import adsk.fusion

ROOT = '/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-v12-backup-20261021-1404'
SECTIONS = None          # None = everything; the MCP driver sets e.g. ['new', 'core']
DOC_NAME = 'GR180-CCHP Engine assembly'
CM = 0.1                 # Fusion internal unit is cm

REPLACED = {'Turbine', 'TurbineNut', 'NGV', 'Shaft', 'Exhaust', 'Balance_Slug'}            # by E1 / E3
COMBUSTOR = {'CC_FrontCap', 'CC_Inner', 'CC_Outer', 'CC_RearCone', 'CC_Vaporisers', 'Casing',
             'GasBulkhead', 'SupplyLines', 'SupplySeals'}                                   # by E2
COLOURS = {'Core': (185, 189, 196), 'E1': (60, 110, 210), 'E2': (215, 140, 50), 'E2 stand-in': (200, 85, 75),
           'E3': (225, 160, 70), 'E3 PMG': (184, 108, 52), 'E3 sensors': (50, 175, 100), 'E4': (150, 156, 150),
           'E4 insulation': (240, 236, 220)}


def app_design():
    app = adsk.core.Application.get()
    return app, adsk.fusion.Design.cast(app.activeProduct)


def group(root, name, move_mm=None):
    """Top-level subsystem component (reused if it exists)."""
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        if o.component.name == name:
            return o
    m = adsk.core.Matrix3D.create()
    if move_mm:
        m.translation = adsk.core.Vector3D.create(*[v * CM for v in move_mm])
    o = root.occurrences.addNewComponent(m)
    o.component.name = name
    return o


def import_part(app, parent_occ, path, name):
    """STEP -> new child component `name` of parent_occ. Fusion's translator adds its own child occurrence: move its
    bodies up into the new component and delete it, so the browser shows one component per part."""
    comp = parent_occ.component
    occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    occ = occ.createForAssemblyContext(parent_occ)
    c = occ.component
    k0 = c.occurrences.count
    app.importManager.importToTarget(app.importManager.createSTEPImportOptions(path), c)
    stale = [c.occurrences.item(i) for i in range(k0, c.occurrences.count)]
    for child in stale:
        for b in [child.bRepBodies.item(j) for j in range(child.bRepBodies.count)]:
            b.moveToComponent(occ)
        for sub in [child.childOccurrences.item(j) for j in range(child.childOccurrences.count)]:
            for b in [sub.bRepBodies.item(j) for j in range(sub.bRepBodies.count)]:
                b.moveToComponent(occ)
    for child in stale:
        try:
            child.deleteMe()
        except Exception:
            pass
    return occ


def pattern(comp, body, n, name):
    """n copies of body about the engine (X) axis; direct design, so plain transformed copies instead of a feature."""
    tb = adsk.fusion.TemporaryBRepManager.get()
    for k in range(1, n):
        t = tb.copy(body)
        m = adsk.core.Matrix3D.create()
        m.setToRotation(2 * 3.141592653589793 * k / n, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
        tb.transform(t, m)
        comp.bRepBodies.add(t).name = '%s %d' % (name, k + 1)
    body.name = '%s 1' % name


def base_appearance(app):
    for lib in app.materialLibraries:
        for name in ('Paint - Enamel Glossy (White)', 'Plastic - Glossy (White)', 'Paint - Metallic (White)'):
            try:
                a = lib.appearances.itemByName(name)
            except Exception:
                a = None
            if a:
                return a
    raise RuntimeError('no plain library appearance found')


def coloured(app, design, name, rgb):
    a = design.appearances.itemByName('GR180 ' + name)
    if not a:
        a = design.appearances.addByCopy(base_appearance(app), 'GR180 ' + name)
    for p in a.appearanceProperties:
        if p.objectType == adsk.core.ColorProperty.classType():
            cp = adsk.core.ColorProperty.cast(p)
            if cp.id in ('opaque_albedo', 'generic_diffuse', 'metal_f0') or cp.name.lower() in ('color', 'colour'):
                cp.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
    return a


def sec_new(app, design):
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.DirectDesignType   # no timeline: imports and moves cannot break
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    print('new design', doc.name)


def sec_core(app, design):
    root = design.rootComponent
    core = group(root, 'Core GR180 v13A')
    has_e2 = bool(glob.glob(os.path.join(ROOT, 'cad_out', 'engine', 'E2', '*.step')))
    legacy = None if has_e2 else group(root, 'E2 stand-in: v13A combustor (to be replaced)')
    n = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts', '*.step'))):
        name = os.path.splitext(os.path.basename(f))[0]
        if name in REPLACED or (name in COMBUSTOR and has_e2):
            continue
        import_part(app, legacy if name in COMBUSTOR else core, f, name); n += 1
    print('core parts', n, '| E2 built:', has_e2)


def sec_e1(app, design):
    g = group(design.rootComponent, 'E1 GG turbine stage (IN713LC)')
    d = os.path.join(ROOT, 'fusion', 'E1')
    blisk = import_part(app, g, os.path.join(d, 'E1_disc_boreless_final.step'), 'E1 blisk (29 blades)')
    tmp = import_part(app, g, os.path.join(d, 'E1_blade_final.step'), 'tmp blade')
    blade = tmp.bRepBodies.item(0).moveToComponent(blisk); tmp.deleteMe()
    pattern(blisk.component, blade.nativeObject or blade, 29, 'blade')
    ngv = import_part(app, g, os.path.join(d, 'E1_ngv_rings_final.step'), 'E1 NGV ring (21 vanes)')
    tmp = import_part(app, g, os.path.join(d, 'E1_ngv_vane_final.step'), 'tmp vane')
    vane = tmp.bRepBodies.item(0).moveToComponent(ngv); tmp.deleteMe()
    pattern(ngv.component, vane.nativeObject or vane, 21, 'vane')
    import_part(app, g, os.path.join(d, 'E1_shaft_welded.step'), 'E1 shaft 42CrMo4 (friction-welded)')
    print('E1 done')


def sec_e2(app, design):
    files = sorted(glob.glob(os.path.join(ROOT, 'cad_out', 'engine', 'E2', '*.step')))
    files = [f for f in files if 'assembly' not in os.path.basename(f).lower()]
    if not files:
        print('E2 not built yet'); return
    g = group(design.rootComponent, 'E2 combustor + pressure casing')
    for f in files:
        import_part(app, g, f, os.path.splitext(os.path.basename(f))[0])
    print('E2 parts', len(files))


def sec_e3(app, design):
    root = design.rootComponent
    g = group(root, 'E3 interduct + FPT + bearings + PMG + collector')
    pmg = group(root, 'E3 PMG active parts')
    sens = group(root, 'E3 sensors')
    files = sorted(glob.glob(os.path.join(ROOT, 'cad_out', 'engine', 'E3', 'E3-*.step')))
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        num = int(name.split('_')[0].split('-')[1])
        tgt = sens if 500 <= num < 600 else (pmg if num in (202, 203, 204, 303, 304) else g)
        import_part(app, tgt, f, name)
    print('E3 parts', len(files))


def sec_e4(app, design):
    root = design.rootComponent
    move = (-1680.0, -7850.0, -600.0)          # E4 is modelled in the ROOF frame (mm)
    g = group(root, 'E4 recuperator', move)
    ins = group(root, 'E4 insulation', move)
    n = 0
    for key in ('core', 'headers_plenums', 'ducts', 'ports', 'supports', 'insulation'):
        f = os.path.join(ROOT, 'cad_out', 'engine', 'E4', 'E4_%s.step' % key)
        if os.path.exists(f):
            import_part(app, ins if key == 'insulation' else g, f, 'E4 ' + key); n += 1
    ins.isLightBulbOn = False                  # hidden by default; switch on in the browser
    print('E4 parts', n)


def sec_colour(app, design):
    root = design.rootComponent
    keys = [('E3 PMG', 'E3 PMG'), ('E3 sensors', 'E3 sensors'), ('E4 insulation', 'E4 insulation'),
            ('E2 stand-in', 'E2 stand-in'), ('Core', 'Core'), ('E1', 'E1'), ('E2', 'E2'), ('E3', 'E3'), ('E4', 'E4')]
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        for k, c in keys:
            if o.component.name.startswith(k):
                o.appearance = coloured(app, design, c, COLOURS[c]); break
    app.activeViewport.camera.isFitView = True
    app.activeViewport.fit()
    print('coloured', root.occurrences.count, 'groups')


def sec_save(app, design):
    """Save next to the E1 documents (same Fusion project folder) as DOC_NAME."""
    doc = app.activeDocument
    if doc.isSaved:
        doc.save('rebuilt by GR180_Engine_Assembly'); print('saved', doc.name); return
    folder = None
    for d in app.documents:
        if d.name.startswith('GR180 E1') and d.dataFile:
            folder = d.dataFile.parentFolder; break
    folder = folder or app.data.activeProject.rootFolder
    doc.saveAs(DOC_NAME, folder, 'GR180-CCHP engine: core v13A + E1 + E2 + E3 + E4 (ENG frame, mm)', '')
    print('saved as', DOC_NAME, 'in', folder.name)


def run(_context):
    app, design = app_design()
    secs = SECTIONS or ['new', 'core', 'e1', 'e2', 'e3', 'e4', 'colour', 'save']
    for s in secs:
        if s != 'new':
            app, design = app_design()
        globals()['sec_' + s](app, design)
