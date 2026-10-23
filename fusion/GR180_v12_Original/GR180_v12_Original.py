"""Autodesk Fusion script: the user's original GR180 v12 turbojet (FreeCAD model, STEP/STL files in the repo root,
snapshot 2026-10-21 14:04) as one Fusion design, one component per part, coloured like the FreeCAD view
(pink intake/compressor side, see-through casing and liner, orange exhaust, green starter).
Run from Utilities > Scripts and Add-Ins, or through fusion/tools/fusion_mcp.py script <this file>.
"""
import os
import glob

import adsk.core
import adsk.fusion

ROOT = '/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-v12-backup-20261021-1404'
MODE = 'v12'             # 'v12' original | 'v13A' drawing-corrected | 'D' single-shaft turbo-generator concept (v13A + front PMG pod)
DOC_NAME = {'v12': 'GR180 v12 original turbojet', 'v13A': 'GR180 v13A turbojet (drawing-corrected)',
            'D': 'GR180-D Single-shaft turbo-generator (concept)', 'RT': 'GR180-D Radial turbine stage (concept)',
            'D2': 'GR180-D2 Single-shaft + radial turbine (full assembly)'}[MODE]
D2_SKIP = D_SKIP | {'GR180_Turbine', 'GR180_NGV', 'GR180_TurbineNut', 'D-180_Exhaust_Diffuser_DN150'}   # axial stage -> radial stage
D_SKIP = {'GR180_Starter', 'GR180_NoseCone', 'GR180_Exhaust'}      # replaced by the generator pod and the exhaust diffuser
SKIP = {'GR180_Combustion_chamber', 'GR180_Shaft_assembly', 'GR180_Shaft_with_nose'}   # composites of other files
# first match wins: (substring, rgb, opacity)
STYLE = [('Turbine_Wheel', (230, 175, 40), 1.0), ('Nozzle_Ring', (60, 110, 210), 1.0), ('Housing_Plenum', (170, 200, 225), 0.25),
         ('Exducer_Shroud', (170, 200, 225), 0.35), ('Tie_Nut', (90, 90, 95), 1.0), ('Shaft_Extension', (190, 55, 45), 1.0),
         ('Generator_Housing', (170, 200, 225), 0.25), ('Front_Cap', (170, 200, 225), 0.35), ('Inlet_Screen', (150, 150, 155), 0.25),
         ('Stator_Core', (80, 85, 95), 1.0), ('Winding', (200, 110, 50), 1.0), ('PMG_Rotor', (200, 60, 170), 1.0),
         ('Quill', (190, 55, 45), 1.0), ('Coupling', (150, 150, 160), 1.0), ('Struts', (60, 60, 65), 1.0), ('Terminal', (40, 120, 220), 1.0),
         ('Exhaust', (245, 110, 10), 1.0), ('Casing', (215, 185, 160), 0.25), ('CC_Outer', (215, 185, 160), 0.35), ('Intake_outer', (225, 140, 150), 0.6), ('IntakeOuter', (225, 140, 150), 0.6), ('ShaftTunnel', (120, 200, 200), 1.0),
         ('Intake', (225, 140, 150), 1.0), ('NoseCone', (200, 200, 205), 1.0), ('Starter', (30, 170, 40), 1.0),
         ('Compressor', (205, 210, 220), 1.0), ('Diffuser', (225, 120, 170), 1.0), ('Exhaust', (245, 110, 10), 1.0),
         ('Turbine', (230, 175, 40), 1.0), ('NGV', (60, 110, 210), 1.0), ('Shaft_tunnel', (120, 200, 200), 1.0),
         ('Shaft', (190, 55, 45), 1.0), ('CC_', (230, 200, 120), 1.0), ('Vaporisers', (230, 200, 120), 1.0),
         ('Bearing', (245, 215, 60), 1.0), ('Igniter', (90, 90, 95), 1.0), ('EGT', (90, 90, 95), 1.0),
         ('RPM', (40, 180, 100), 1.0), ('Supply', (240, 190, 0), 1.0), ('GasBulkhead', (240, 190, 0), 1.0),
         ('Fasteners', (70, 70, 75), 1.0)]


def base_appearance(app):
    for lib in app.materialLibraries:
        for name in ('Paint - Enamel Glossy (White)', 'Plastic - Glossy (White)'):
            try:
                a = lib.appearances.itemByName(name)
            except Exception:
                a = None
            if a:
                return a
    raise RuntimeError('no plain library appearance found')


def coloured(app, design, rgb):
    name = 'v12 %d-%d-%d' % rgb
    a = design.appearances.itemByName(name) or design.appearances.addByCopy(base_appearance(app), name)
    for p in a.appearanceProperties:
        if p.objectType == adsk.core.ColorProperty.classType():
            cp = adsk.core.ColorProperty.cast(p)
            if cp.id in ('opaque_albedo', 'generic_diffuse', 'metal_f0') or cp.name.lower() in ('color', 'colour'):
                cp.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
    return a


def run(_context):
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    root = design.rootComponent
    if MODE == 'RT':                             # version D radial turbine stage on its own page
        steps = {os.path.splitext(os.path.basename(f))[0]: f
                 for f in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_d', 'RT', 'RT-*.step'))}
        stls = {}
    elif MODE == 'v12':
        steps = {os.path.splitext(os.path.basename(f))[0]: f for f in glob.glob(os.path.join(ROOT, 'GR180_*.step'))}
        stls = {os.path.splitext(os.path.basename(f))[0]: f for f in glob.glob(os.path.join(ROOT, 'GR180_*.stl'))}
    else:
        steps = {'GR180_' + os.path.splitext(os.path.basename(f))[0]: f
                 for f in glob.glob(os.path.join(ROOT, 'cad_out', 'v13A', 'asm_parts', '*.step'))}
        stls = {}
        if MODE in ('D', 'D2'):
            steps.update({os.path.splitext(os.path.basename(f))[0]: f
                          for f in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_d', 'D-*.step'))})
            if MODE == 'D2':
                steps.update({os.path.splitext(os.path.basename(f))[0]: f
                              for f in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_d', 'RT2', 'RT-*.step'))})
            skip = D2_SKIP if MODE == 'D2' else D_SKIP
            steps = {k: v for k, v in steps.items() if k not in skip}
    n = 0
    for name in sorted(set(steps) | set(stls)):
        if name in SKIP:
            continue
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name.replace('GR180_', '')
        if name in steps:
            k0 = occ.component.occurrences.count
            app.importManager.importToTarget(app.importManager.createSTEPImportOptions(steps[name]), occ.component)
            for child in [occ.component.occurrences.item(i) for i in range(k0, occ.component.occurrences.count)]:
                for b in [child.bRepBodies.item(j) for j in range(child.bRepBodies.count)]:
                    b.moveToComponent(occ)
                child.deleteMe()
        else:                                    # parts that only exist as STL (bearings, spacers, wave spring, oil rings)
            occ.component.meshBodies.add(stls[name], adsk.fusion.MeshUnits.MillimeterMeshUnit)
        for key, rgb, op in STYLE:
            if key in name:
                occ.appearance = coloured(app, design, rgb)
                occ.component.opacity = op
                break
        n += 1
    app.activeViewport.fit()
    folder = None
    for d in app.documents:
        if d.name.startswith('GR180') and d.dataFile:
            folder = d.dataFile.parentFolder; break
    if not folder:
        projects = [app.data.dataProjects.item(i) for i in range(app.data.dataProjects.count)]
        folder = next((p for p in projects if p.name == 'Default Project'), projects[0]).rootFolder
    app.activeDocument.saveAs(DOC_NAME, folder, 'GR180 turbojet %s (FreeCAD build_gr180.py output)' % MODE, '')
    print('parts', n, '| saved as', DOC_NAME)
