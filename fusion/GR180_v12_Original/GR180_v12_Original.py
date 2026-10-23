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
            'D2': 'GR180-D2 Single-shaft + radial turbine (full assembly)',
            'E': 'GR180-E 250 kW single-shaft turbo-generator'}[MODE]
D2_SKIP = D_SKIP | {'GR180_Turbine', 'GR180_NGV', 'GR180_TurbineNut', 'D-180_Exhaust_Diffuser_DN150'}   # axial stage -> radial stage
SHOW_AUX = False         # user (2026-10-23): auxiliaries skid (gas train, oil, glycol) hidden for now
SHOW_FILTER_BOX = False  # user (2026-10-23): leave the V-cell filter box out for now, add it later
FILTER_BOX = {'INT-150*', 'INT-151*', 'INT-152*', 'INT-153*', 'FR-160*'}
D2_REPLACED = {'EXHAUST': {'RT-180_Exhaust_Diffuser_DN150'},
               'TURBINE': {'RT-*'}, 'ROTOR': {'GR180_Shaft', 'RT-140_Shaft_Extension', 'D-140_Quill_Shaft', 'GR180_FrontBearing*',
                                             'GR180_RearBearing*', 'D-141*', 'D-142*', 'GR180_Compressor', 'GR180_ShaftTunnel',
                                             'GR180_WaveSpring*', 'GR180_Balance_Slug'},
               'GENERATOR': {'D-1*'}, 'POD': {'D-1*'}, 'FRAME': set(), 'AUX': set(), 'INTAKE': {'D-160_Inlet_Screen', 'D-150*'}}
D_SKIP = {'GR180_Starter', 'GR180_NoseCone', 'GR180_Exhaust'}      # replaced by the generator pod and the exhaust diffuser
SKIP = {'GR180_Combustion_chamber', 'GR180_Shaft_assembly', 'GR180_Shaft_with_nose'}   # composites of other files
# first match wins: (substring, rgb, opacity)
STYLE = [('Compressor_Wheel', (205, 210, 220), 1.0), ('Turbine_Wheel', (230, 175, 40), 1.0), ('Nozzle_Ring', (60, 110, 210), 1.0),
         ('Liner', (235, 95, 60), 1.0), ('Swirler', (240, 190, 0), 1.0), ('Gas_Lance', (240, 190, 0), 1.0), ('Igniter', (40, 180, 100), 1.0),
         ('UV_Flame', (40, 180, 100), 1.0), ('Combustor_Casing', (170, 200, 225), 0.3), ('Top_Cover', (170, 200, 225), 0.4),
         ('Transition_Cone', (235, 95, 60), 1.0), ('Hangers', (90, 95, 100), 1.0), ('Outer_Casing', (170, 200, 225), 0.3),
         ('Inlet_Shroud', (170, 200, 225), 0.4), ('Back_Plate', (120, 150, 190), 1.0), ('Hot_Plenum', (235, 140, 90), 0.5),
         ('Cool_Pressure', (170, 200, 225), 0.25), ('Heat_Shield', (150, 150, 160), 1.0), ('Shroud_Diffuser', (170, 200, 225), 0.4),
         ('Bearing_Housing', (170, 200, 225), 0.35), ('Core_Shaft', (190, 55, 45), 1.0), ('Generator_Shaft', (190, 55, 45), 1.0),
         ('Spacer_Sleeve', (190, 55, 45), 1.0), ('Clamp_Nut', (150, 150, 160), 1.0), ('Slinger', (150, 150, 160), 1.0),
         ('Diffuser_Cone', (245, 110, 10), 1.0), ('Elbow', (245, 110, 10), 1.0), ('Turning_Vanes', (245, 110, 10), 1.0),
         ('Intake_Plenum', (200, 205, 215), 0.3), ('Filter_Interface', (90, 95, 100), 1.0), ('Base_Frame', (55, 60, 65), 1.0),
         ('Pedestals', (55, 60, 65), 1.0), ('Saddles', (55, 60, 65), 1.0), ('AV_Mounts', (30, 30, 30), 1.0),
         ('End_Bell', (170, 200, 225), 0.35), ('Winding_End', (200, 110, 50), 1.0), ('Magnets_Sleeve', (200, 60, 170), 1.0),
         ('Speed_Wheel', (150, 150, 160), 1.0), ('Quill', (190, 55, 45), 1.0),
         ('Pod_Housing', (170, 200, 225), 0.3), ('Front_Cover', (170, 200, 225), 0.35), ('Glycol_Jacket', (120, 170, 220), 0.35),
         ('Magnet', (200, 60, 170), 1.0), ('Carbon_Sleeve', (40, 40, 45), 1.0), ('End_Rings', (150, 150, 160), 1.0),
         ('Locknut', (150, 150, 160), 1.0), ('Seal_Spacer', (150, 150, 160), 1.0), ('Dowel', (110, 110, 115), 1.0),
         ('Screws', (110, 110, 115), 1.0), ('Phase_Studs', (200, 110, 50), 1.0), ('Terminal_Block', (230, 200, 120), 1.0),
         ('Gasket', (30, 30, 30), 1.0), ('Lead-out', (30, 30, 30), 1.0), ('Cable_Glands', (30, 30, 30), 1.0),
         ('Hose_Nipples', (40, 120, 220), 1.0), ('Plug', (110, 110, 115), 1.0), ('Shim', (150, 150, 160), 1.0),
         ('Filter_Box_Posts', (55, 60, 65), 1.0), ('Filter_Box', (200, 205, 215), 0.3), ('Lid_Grille', (60, 60, 65), 0.6),
         ('V-Cell', (235, 235, 230), 0.85), ('Toggle_Latches', (240, 190, 0), 1.0), ('Pod_Cradle', (55, 60, 65), 1.0),
         ('Weight_Relief', (55, 60, 65), 1.0), ('End_Ring', (245, 110, 10), 1.0), ('Diffuser_Weldment', (245, 110, 10), 1.0),
         ('Plenum_Can', (200, 205, 215), 0.35), ('Dish_Skirt', (200, 205, 215), 0.45), ('Rear_Ring', (90, 95, 100), 1.0),
         ('Port_FOD', (60, 60, 65), 0.4), ('Diffuser_Stub', (245, 110, 10), 1.0), ('Flange_DN125', (245, 110, 10), 1.0),
         ('Inlet_Flange', (90, 95, 100), 1.0), ('Front_Pedestal', (55, 60, 65), 1.0), ('Body_Sleeve', (190, 55, 45), 1.0),
         ('Engine_Shaft', (190, 55, 45), 1.0), ('Clamp', (90, 95, 100), 1.0), ('SFD', (120, 200, 200), 1.0), ('O-rings', (30, 30, 30), 1.0),
         ('Oil_Feed', (240, 190, 0), 1.0), ('Scavenge', (240, 190, 0), 1.0), ('Seal_Retainer', (150, 150, 160), 1.0),
         ('End_Shield', (170, 200, 225), 0.35), ('Bearing_Cover', (170, 200, 225), 0.35), ('Quill_Guard', (170, 200, 225), 0.35),
         ('Glycol', (40, 120, 220), 1.0), ('Wave_Spring', (245, 215, 60), 1.0), ('Cartridge', (230, 230, 220), 0.2), ('FOD_Guard', (60, 60, 65), 0.35), ('Insulation', (240, 236, 220), 0.15),
         ('Plenum_Bell', (200, 205, 215), 0.45), ('Tube_Sheet', (200, 205, 215), 0.6), ('Skirt', (200, 205, 215), 0.45),
         ('Yoke', (90, 95, 100), 1.0), ('Clamp', (90, 95, 100), 1.0), ('Tail_Fairing', (170, 200, 225), 0.5),
         ('Diffuser_Elbow', (245, 110, 10), 1.0), ('VBand', (90, 95, 100), 1.0), ('Flange_DN200', (245, 110, 10), 1.0),
         ('Support_Lugs', (60, 60, 65), 1.0), ('Heat_Shield', (150, 150, 160), 1.0), ('End_Support', (60, 60, 65), 1.0),
         ('Base_Frame', (55, 60, 65), 1.0), ('Saddle', (55, 60, 65), 1.0), ('Collar', (55, 60, 65), 1.0), ('Pedestals', (55, 60, 65), 1.0),
         ('AV_Mounts', (30, 30, 30), 1.0), ('Lifting', (240, 190, 0), 1.0), ('Turbine_Wheel', (230, 175, 40), 1.0), ('Nozzle_Ring', (60, 110, 210), 1.0), ('Housing_Plenum', (170, 200, 225), 0.25),
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
    existing = next((d for d in app.documents if d.name.split(' v')[0] == DOC_NAME or d.name == DOC_NAME), None)
    if existing:                                 # rebuild in place: keeps one file with version history
        existing.activate()
        design = adsk.fusion.Design.cast(app.activeProduct)
        for o in [design.rootComponent.occurrences.item(i) for i in range(design.rootComponent.occurrences.count)]:
            o.deleteMe()
    else:
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    root = design.rootComponent
    if MODE == 'E':                              # version E (250 kW), all subsystem folders
        steps = {os.path.splitext(os.path.basename(f))[0]: f
                 for f in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_e', '*', 'E-*.step'))}
        stls = {}
    elif MODE == 'RT':                             # version D radial turbine stage on its own page
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
            skip = set(D2_SKIP if MODE == 'D2' else D_SKIP)
            if MODE == 'D2':
                steps.update({os.path.splitext(os.path.basename(f))[0]: f
                              for f in glob.glob(os.path.join(ROOT, 'cad_out', 'variant_d', 'RT2', 'RT-*.step'))})
                d2 = os.path.join(ROOT, 'cad_out', 'variant_d', 'D2')
                for sub in ('INTAKE', 'EXHAUST', 'FRAME', 'ROTOR', 'TURBINE', 'GENERATOR', 'POD') + (('AUX',) if SHOW_AUX else ()):
                    fs = [f for f in glob.glob(os.path.join(d2, sub, '*.step')) if '_assembly' not in f]
                    if not fs:
                        continue
                    steps.update({os.path.splitext(os.path.basename(f))[0]: f for f in fs})
                    skip |= D2_REPLACED.get(sub, set())   # detailed subsystem replaces the concept parts
            if not SHOW_FILTER_BOX:
                skip |= FILTER_BOX
            skip = {k for k in steps if k in skip or any(k.startswith(p) for p in skip if p.endswith('*'))} | skip
            steps = {k: v for k, v in steps.items() if k not in skip}
    n = 0
    for name in sorted(set(steps) | set(stls)):
        if name in SKIP:
            continue
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = name.replace('GR180_', '')
        if name in steps:
            k0 = occ.component.occurrences.count
            try:
                app.importManager.importToTarget(app.importManager.createSTEPImportOptions(steps[name]), occ.component)
            except RuntimeError as e:             # a file being rewritten by a design script: skip it, report it
                print('SKIPPED', name, str(e)[:80]); occ.deleteMe(); continue
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
    if existing:
        app.activeDocument.save('rebuilt (%s)' % MODE)
    else:
        app.activeDocument.saveAs(DOC_NAME, folder, 'GR180 turbojet %s (FreeCAD build_gr180.py output)' % MODE, '')
    print('parts', n, '| saved as', DOC_NAME)
