"""Autodesk Fusion script: AURORA-1000 rotor stack and bearings (rotor rev 1) from fusion/A1000_rotor (cad/engine/a1000_rotor.py).

Utilities > Scripts and Add-Ins > + (My Scripts) > pick this folder > Run. Builds a new direct-modelling design:
  Rotor - compressor stack   front stub + collar, tie bolt + nut, spacer, drum (IN718)
  Rotor - turbine            blisks R1 / R2 with the cast arms (rev 5 blades patterned from fusion/A1000), studs + nuts,
                             rear stub
  Impellers (placeholder)    meanline envelopes from fusion/A1000_pkg, see-through, until the compressor detail design
  Journal bearing 1 / 2      tilting pads, carrier, ISFD damper ring, cartridge housing (see-through)
  Thrust bearing             pads, carrier rings, housing (see-through)
SECTION = True keeps only the half y <= 0 of every body (a cut-away view). Frame: rotor frame mm, X = engine axis.
"""
import json
import math
import os
import traceback

import adsk.core
import adsk.fusion

HERE = os.path.dirname(os.path.abspath(__file__))
SECTION = False
ROT = os.path.normpath(os.path.join(HERE, '..', 'A1000_rotor'))
TURB = os.path.normpath(os.path.join(HERE, '..', 'A1000'))
PKG = os.path.normpath(os.path.join(HERE, '..', 'A1000_pkg'))
VERIFY = os.path.normpath(os.path.join(HERE, '..', '_a1000_rotor_verify.json'))
COLOUR = {'shaft': (150, 156, 166), 'tie': (201, 162, 39), 'drum': (150, 110, 170), 'studs': (214, 175, 60),
          'blisk': (196, 200, 210), 'blade': (196, 200, 210), 'pads': (176, 120, 60), 'carrier': (70, 76, 86),
          'cage': (230, 190, 40), 'housing': (120, 128, 138), 'impeller': (150, 190, 230)}
OPACITY = {'housing': 0.28, 'impeller': 0.35}


def import_step(app, comp, path):
    """STEP into comp -> list of temporary B-Reps (component coordinates); the translator's child occurrence is removed"""
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


def half_box():
    """temporary box covering y <= 0 (cm), for the cut-away"""
    tbm = adsk.fusion.TemporaryBRepManager.get()
    c = adsk.core.Point3D.create(-50.0, -50.0, 0.0)
    ob = adsk.core.OrientedBoundingBox3D.create(c, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0), 600.0, 100.0, 600.0)
    return tbm.createBox(ob)


def build(app, log):
    info = json.load(open(os.path.join(ROT, 'parts.json')))
    tpar = json.load(open(os.path.join(TURB, 'parts.json'))); Z = tpar['pattern']['Z']
    pkg = json.load(open(os.path.join(PKG, 'pkg.json')))
    base = base_appearance(app)
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        return doc, fill(app, doc, info, Z, pkg, base, log)
    except Exception:
        doc.close(False)                                          # the new, unsaved design made above
        raise


def fill(app, doc, info, Z, pkg, base, log):
    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    root = design.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()
    box = half_box() if SECTION else None
    groups = {}
    out = dict(parts={}, bodies=0, section=SECTION)

    def group_comp(label):
        if label not in groups:
            o = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()); o.component.name = label; groups[label] = o.component
        return groups[label]

    def add(label, name, colour_key, temps, dx=0.0, inst=(0.0,)):
        comp = group_comp(label)
        m = adsk.core.Matrix3D.create(); m.translation = adsk.core.Vector3D.create(dx / 10.0, 0, 0)
        so = comp.occurrences.addNewComponent(m); sub = so.component
        sub.name = ''.join('-' if c in ':/\\*?"<>|' else c for c in name)
        sub.opacity = OPACITY.get(colour_key, 1.0)
        if base:
            so.appearance = coloured(design, base, 'A1000 rotor ' + colour_key, COLOUR[colour_key])
        n = 0
        for ang in inst:
            rot = adsk.core.Matrix3D.create()
            rot.setToRotation(math.radians(ang), adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
            for t in temps:
                c = tbm.copy(t); tbm.transform(c, rot)
                if box is not None:
                    tbm.booleanOperation(c, _box_local(box, dx), adsk.fusion.BooleanTypes.IntersectionBooleanType)
                    if c.volume <= 1e-9:
                        continue
                sub.bRepBodies.add(c); n += 1
        out['parts'][name] = n; out['bodies'] += n
        log('%-55s %4d bodies' % (name, n))

    group_of = {'shaft': 'Rotor - shafts', 'tie': 'Rotor - shafts', 'drum': 'Rotor - shafts', 'studs': 'Rotor - turbine joints',
                'blisk': 'Rotor - turbine blisks', 'pads': None, 'carrier': None, 'cage': None, 'housing': None}
    for name, p in info['parts'].items():
        temps = import_step(app, group_comp('_import'), os.path.join(ROT, p['step']))
        g = p['group']
        if name.startswith('JB1'): label = 'Journal bearing 1 (front)'
        elif name.startswith('JB2'): label = 'Journal bearing 2 (rear, exhaust hub)'
        elif name.startswith('TB'): label = 'Thrust bearing'
        else: label = group_of[g]
        add(label, name, g, temps)
    for row, key in (('R1', 'R1'), ('R2', 'R2')):
        temps = import_step(app, group_comp('_import'), os.path.join(TURB, 'A1000_%s_blade.step' % row))
        add('Rotor - turbine blisks', 'A1000_%s blades x%d (rev 5)' % (row, Z[key]), 'blade', temps, info['x_offset_turbine'],
            [360.0 * k / Z[key] for k in range(Z[key])])
    for p in pkg['parts']:
        if p['name'].startswith('Impeller'):
            temps = import_step(app, group_comp('_import'), os.path.join(PKG, p['step']))
            add('Impellers (meanline placeholder)', p['name'], 'impeller', temps, 0.0, p['inst'])
    groups.pop('_import', None)
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        if o.component.name == '_import':
            o.deleteMe(); break
    bb = root.boundingBox
    out['bbox_mm'] = [[round(bb.minPoint.x * 10), round(bb.minPoint.y * 10), round(bb.minPoint.z * 10)],
                      [round(bb.maxPoint.x * 10), round(bb.maxPoint.y * 10), round(bb.maxPoint.z * 10)]]
    return out


def _shift(dx):
    m = adsk.core.Matrix3D.create(); m.translation = adsk.core.Vector3D.create(dx / 10.0, 0, 0); return m


def _box_local(box, dx):
    """the half-space box in the coordinates of a sub-component moved by dx (bodies are added in local coordinates)"""
    tbm = adsk.fusion.TemporaryBRepManager.get(); b = tbm.copy(box); tbm.transform(b, _shift(-dx)); return b


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
            ui.messageBox('AURORA-1000 rotor + bearings: %d parts, %d bodies' % (len(out['parts']), out['bodies']))
    except Exception:
        log(traceback.format_exc())
        if ui and context is not None:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        else:
            raise
