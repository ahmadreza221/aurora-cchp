"""Autodesk Fusion script: colour the GR180 E1 turbine stage in the active design (after GR180_E1_Import).

Components are matched by name: 'blisk' -> gold (IN713LC rotor), 'NGV' -> blue (IN713LC vane ring),
'shaft' -> red (42CrMo4 welded shaft). Run it in the design that holds the stage.
"""
import traceback

import adsk.core
import adsk.fusion

COLOURS = [('blisk', 'GR180 rotor (gold)', (212, 160, 55)),
           ('NGV', 'GR180 NGV (blue)', (60, 120, 205)),
           ('shaft', 'GR180 shaft (red)', (190, 55, 45))]


def base_appearance(app):
    """A plain opaque library appearance with a colour property, to copy into the design."""
    for lib in app.materialLibraries:
        for name in ('Paint - Enamel Glossy (White)', 'Plastic - Glossy (White)', 'Paint - Metallic (White)'):
            try:
                a = lib.appearances.itemByName(name)
            except Exception:
                a = None
            if a:
                return a
    for lib in app.materialLibraries:
        for i in range(lib.appearances.count):
            a = lib.appearances.item(i)
            if any(p.objectType == adsk.core.ColorProperty.classType() for p in a.appearanceProperties):
                return a
    raise RuntimeError('no library appearance with a colour property found')


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


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open the design with the E1 turbine stage first.'); return
        base = base_appearance(app)
        done = []
        for occ in design.rootComponent.allOccurrences:
            for key, aname, rgb in COLOURS:
                if key.lower() in occ.component.name.lower():
                    occ.appearance = coloured(design, base, aname, rgb)
                    done.append(occ.component.name)
                    break
        app.activeViewport.refresh()
        ui.messageBox('Coloured %d components:\n%s' % (len(done), '\n'.join(done) or '(none matched)'))
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
