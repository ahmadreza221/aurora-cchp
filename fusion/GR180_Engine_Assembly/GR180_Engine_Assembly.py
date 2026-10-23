"""Autodesk Fusion script: the whole GR180-CCHP engine as it is designed today, one component per subsystem.

  Core GR180 v13A          cad_out/v13A/asm_parts/*.step   (minus parts replaced by E1 / E2 / E3)
  E1 GG turbine stage      fusion/E1/*.step                (blisk 29 blades, NGV 21 vanes, welded shaft)
  E2 combustor             cad_out/engine/E2/E2-*.step when built; until then the v13A combustor as a stand-in
  E3 interduct+FPT+PMG     cad_out/engine/E3/E3-*.step
  E4 recuperator           cad_out/engine/E4/E4_*.step     (ROOF mm -> ENG mm, offset read from E4_interfaces.json)
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
V13A_DIR = os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts')
ENGINE_DIR = os.path.join(ROOT, 'cad_out', 'engine')     # E2/E3/E4 outputs (a session worktree's cad_out/engine before merge)
VARIANT = 'A'            # 'A' recuperated (E2 + E4) | 'B' simple cycle (E2-B, no E4) | 'C' compact turbo-generator (E2-B + compact exhaust + low frame)
VC_DIR = os.path.join(ROOT, 'cad_out', 'variant_c')     # variant-C outputs (EXH/, FRAME/)
C_SKIP = ('E2B-103', 'E3-110', 'E3-111', 'E3-112', 'E3-113', 'E3-401', 'E3-402', 'E3-504', 'E3-505', 'E3-506', 'E3B-401')
VB_DIR = os.path.join(ROOT, 'cad_out', 'variant_b')     # variant-B outputs (E2B/, E3B/)
DOC_NAME = 'GR180-CCHP Engine assembly'
CM = 0.1                 # Fusion internal unit is cm

REPLACED = {'Turbine', 'TurbineNut', 'NGV', 'Shaft', 'Exhaust', 'Balance_Slug'}            # by E1 / E3
COMBUSTOR = {'CC_FrontCap', 'CC_Inner', 'CC_Outer', 'CC_RearCone', 'CC_Vaporisers', 'Casing',
             'GasBulkhead', 'SupplyLines', 'SupplySeals', 'Igniter', 'EGT_Probe'}             # by E2 (own igniter, T3/T4 on E2/E3)
COLOURS = {'Core': (185, 189, 196), 'E1': (60, 110, 210), 'E2': (200, 85, 75), 'E2 stand-in': (200, 85, 75),
           'E2 insulation': (240, 236, 220), 'E2 sensors': (50, 175, 100),
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
    has_e2 = VARIANT in ('B', 'C') or bool(glob.glob(os.path.join(ENGINE_DIR, 'E2', 'E2-*.step')))
    legacy = None if has_e2 else group(root, 'E2 stand-in: v13A combustor (to be replaced)')
    n = 0
    for f in sorted(glob.glob(os.path.join(V13A_DIR, '*.step'))):
        name = os.path.splitext(os.path.basename(f))[0]
        if name in REPLACED or (name in COMBUSTOR and has_e2):
            continue
        occ = import_part(app, legacy if name in COMBUSTOR else core, f, name); n += 1
        if name == 'Fasteners' and has_e2:      # only the front screws stay; the rear ones held Rutten's casing/exhaust
            for b in [occ.bRepBodies.item(i) for i in range(occ.bRepBodies.count)]:
                if b.boundingBox.maxPoint.x >= 0:
                    b.deleteMe()
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
    files = sorted(glob.glob(os.path.join(ENGINE_DIR, 'E2', 'E2-*.step')))
    if not files:
        print('E2 not built yet'); return
    root = design.rootComponent
    g = group(root, 'E2 combustor + pressure casing + collector')
    ins = group(root, 'E2 insulation')
    sens = group(root, 'E2 sensors + igniter')
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        num = int(name.split('_')[0].split('-')[1])
        tgt = sens if num >= 500 else (ins if num in (160, 161) else g)
        import_part(app, tgt, f, name)
    print('E2 parts', len(files))


def sec_e2b(app, design):
    """Variant B combustor (simple cycle, no recuperator ports)."""
    files = sorted(glob.glob(os.path.join(VB_DIR, 'E2B', 'E2B-*.step')))
    if not files:
        print('E2-B not built yet'); return
    root = design.rootComponent
    g = group(root, 'E2-B combustor + casing (simple cycle)')
    ins = group(root, 'E2-B insulation')
    sens = group(root, 'E2-B sensors + igniter')
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        if VARIANT == 'C' and name.startswith(C_SKIP):
            continue
        num = int(name.split('_')[0].split('-')[1])
        tgt = sens if num >= 500 else (ins if 'Insulation' in name else g)
        import_part(app, tgt, f, name)
    print('E2-B parts', len(files))


def sec_e3(app, design):
    root = design.rootComponent
    g = group(root, 'E3 interduct + FPT + bearings + PMG + collector')
    pmg = group(root, 'E3 PMG active parts')
    sens = group(root, 'E3 sensors')
    files = sorted(glob.glob(os.path.join(ENGINE_DIR, 'E3', 'E3-*.step')))
    if VARIANT == 'C':                          # compact exhaust + low frame replace the collector, feet and exit sensors
        files = [f for f in files if not os.path.basename(f).startswith(C_SKIP)]
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        num = int(name.split('_')[0].split('-')[1])
        tgt = sens if 500 <= num < 600 else (pmg if num in (202, 203, 204, 303, 304) else g)
        import_part(app, tgt, f, name)
    print('E3 parts', len(files))


def sec_exh_c(app, design):
    """Variant C compact exhaust (square plenum box, DN200 outlet up) and the low base frame."""
    root = design.rootComponent
    g = group(root, 'C exhaust (compact box + DN200 up)')
    ins = group(root, 'C exhaust insulation')
    fr = group(root, 'C base frame + supports')
    n = 0
    for f in sorted(glob.glob(os.path.join(VC_DIR, 'EXH', 'E3B-*.step'))):
        name = os.path.splitext(os.path.basename(f))[0]
        if name.startswith(C_SKIP):
            continue
        import_part(app, ins if 'Insulation' in name else g, f, name); n += 1
    for f in sorted(glob.glob(os.path.join(VC_DIR, 'FRAME', 'C-*.step'))):
        import_part(app, fr, f, os.path.splitext(os.path.basename(f))[0]); n += 1
    print('C exhaust + frame parts', n)


def sec_e4(app, design):
    root = design.rootComponent
    import json                                # E4 is modelled in the ROOF frame: ENG = ROOF - (ENG origin in ROOF)
    i0 = json.load(open(os.path.join(ENGINE_DIR, 'E4', 'E4_interfaces.json')))['interfaces'][0]
    move = tuple(e - r * 1000.0 for r, e in zip(i0['roof_m'], i0['eng_mm']))
    g = group(root, 'E4 recuperator', move)
    ins = group(root, 'E4 insulation', move)
    n = 0
    for key in ('core', 'headers_plenums', 'ducts', 'ports', 'supports', 'insulation'):
        f = os.path.join(ENGINE_DIR, 'E4', 'E4_%s.step' % key)
        if os.path.exists(f):
            import_part(app, ins if key == 'insulation' else g, f, 'E4 ' + key); n += 1
    ins.isLightBulbOn = False                  # hidden by default; switch on in the browser
    print('E4 parts', n, 'offset', [round(v, 1) for v in move])


def sec_colour(app, design):
    root = design.rootComponent
    keys = [('E2 insulation', 'E2 insulation'), ('E2 sensors', 'E2 sensors'),
            ('E3 PMG', 'E3 PMG'), ('E3 sensors', 'E3 sensors'), ('E4 insulation', 'E4 insulation'),
            ('E2 stand-in', 'E2 stand-in'), ('Core', 'Core'), ('E1', 'E1'), ('E2', 'E2'), ('E3', 'E3'), ('E4', 'E4')]
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        for k, c in keys:
            if o.component.name.startswith(k):
                o.appearance = coloured(app, design, c, COLOURS[c]); break
    app.activeViewport.camera.isFitView = True
    app.activeViewport.fit()
    print('coloured', root.occurrences.count, 'groups')


# x-ray look: every part its own colour, shells see-through. First match wins: (name substrings, label, rgb, opacity)
XRAY = [
    (('IntakeOuter', 'Casing', 'CC_Outer', 'Collector', 'WestCover', 'Hot_Pressure_Casing', 'Collector_Drum', 'C2_Inlet',
      'C1_Outlet', 'Insulation', 'HeatShield', 'Heat_Shield', 'Support_Cone', 'PMG_Housing', 'B1_Bearing_Housing',
      'B2_Housing', 'End_Cover', 'Interduct', 'Shroud', 'Bulkhead', 'Front_Casing', 'E3B-110', 'West_Cover', 'Rear_Unit'), 'shell (glass)', (170, 200, 225), 0.18),
    (('TE-', 'PT-', 'SE-', 'VE-', 'RPM', 'EGT', 'Igniter', 'IGN', 'UV', 'BE-'), 'sensors', (40, 180, 100), 1.0),   # before 'Liner' (liner-wall TCs)
    (('Compressor',), 'compressor', (205, 210, 220), 1.0),
    (('Diffuser',), 'diffuser', (120, 150, 190), 1.0),
    (('Intake', 'NoseCone'), 'intake', (150, 155, 165), 1.0),
    (('blisk', 'Blisk'), 'turbine rotor', (230, 175, 40), 1.0),
    (('NGV',), 'NGV', (60, 110, 210), 1.0),
    (('shaft', 'Shaft', 'Tie_Stud', 'Nut', 'Locknut', 'HeatDam'), 'shaft', (190, 55, 45), 1.0),
    (('Bearing', 'Wave', 'Oring', 'SFD', 'PistonRing', 'Gasket'), 'bearings + seals', (245, 215, 60), 1.0),
    (('Magnet', 'CF_Sleeve'), 'PMG rotor magnets', (200, 60, 170), 1.0),
    (('Stator_Core',), 'stator core', (80, 85, 95), 1.0),
    (('Winding',), 'stator winding (copper)', (200, 110, 50), 1.0),
    (('CC_', 'Liner', 'Vaporiser', 'Baffle'), 'combustor liner', (235, 95, 60), 1.0),
    (('Supply', 'Gas', 'Injector', 'Manifold', 'Fitting'), 'gas system', (250, 190, 0), 1.0),
    (('Starter',), 'starter', (60, 60, 70), 1.0),
    (('Terminal',), 'terminal box', (40, 120, 220), 1.0),
    (('Foot', 'Feet', 'E3B-4', 'Support', 'Rails', 'Flexure'), 'feet + frame', (90, 95, 100), 1.0),
    (('Fan',), 'fan', (120, 200, 240), 1.0),
    (('Fasteners', 'Studs'), 'fasteners', (70, 70, 75), 1.0),
]


def sec_xray(app, design):
    """Per-part colours, see-through shells, everything visible except E4 (power section only)."""
    root = design.rootComponent
    n = 0
    for g in [root.occurrences.item(i) for i in range(root.occurrences.count)]:
        g.appearance = None
        g.isLightBulbOn = not g.component.name.startswith('E4')
        for o in [g.childOccurrences.item(j) for j in range(g.childOccurrences.count)]:
            o.isLightBulbOn = True
            for keys, label, rgb, op in XRAY:
                if any(k in o.component.name for k in keys):
                    o.appearance = coloured(app, design, label, rgb)
                    o.component.opacity = op             # opacity lives on the component in the Fusion API
                    n += 1
                    break
    app.activeViewport.fit()
    print('styled', n, 'parts')


def sec_clear(app, design):
    """Empty the open assembly document (rebuild in place, keeps its name and version history)."""
    assert app.activeDocument.name.startswith(DOC_NAME), app.activeDocument.name
    root = design.rootComponent
    for o in [root.occurrences.item(i) for i in range(root.occurrences.count)]:
        o.deleteMe()
    print('cleared')


def sec_power_only(app, design):
    """Show the engine up to the generator: hide E4 and the insulation."""
    root = design.rootComponent
    for o in [root.occurrences.item(i) for i in range(root.occurrences.count)]:
        o.isLightBulbOn = not (o.component.name.startswith('E4') or 'insulation' in o.component.name)
    app.activeViewport.fit()


def sec_save(app, design):
    """Save next to the E1 documents (same Fusion project folder) as DOC_NAME."""
    doc = app.activeDocument
    if doc.isSaved:
        doc.save('rebuilt by GR180_Engine_Assembly'); print('saved', doc.name); return
    folder = None
    for d in app.documents:
        if d.name.startswith('GR180 E1') and d.dataFile:
            folder = d.dataFile.parentFolder; break
    if not folder:                              # activeProject can fail right after start-up; pick the project by name
        projects = [app.data.dataProjects.item(i) for i in range(app.data.dataProjects.count)]
        proj = next((p for p in projects if p.name == 'Default Project'), projects[0])
        folder = proj.rootFolder
    doc.saveAs(DOC_NAME, folder, 'GR180-CCHP engine: core v13A + E1 + E2 + E3 + E4 (ENG frame, mm)', '')
    print('saved as', DOC_NAME, 'in', folder.name)


def run(_context):
    app, design = app_design()
    secs = SECTIONS or ['new', 'core', 'e1', 'e2', 'e3', 'e4', 'colour', 'save']
    for s in secs:
        if s != 'new':
            app, design = app_design()
        globals()['sec_' + s](app, design)
