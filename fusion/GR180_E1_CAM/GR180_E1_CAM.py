"""Autodesk Fusion CAM helpers for the GR180 E1 turbine stage (Manufacture workspace, adsk.cam API).

Loaded from the Fusion MCP server with importlib (see GR180_E1_Drawings.py for the pattern) or run as a script.
Setups follow docs/engine/E1_manufacturing.md section 7: turning of the rotor unit (wheel + welded shaft), two
chuckings of the NGV ring, and the shaft. Blades and vanes stay as-cast: no 5-axis operations are created.

All helpers log to cad_out/engine/E1/_cam_log.txt so progress survives MCP time-outs.
"""
import os
import json
import traceback

import adsk.core
import adsk.fusion
import adsk.cam

OUT = '/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-v12-backup-20261021-1404/cad_out/engine/E1'
LOG = os.path.join(OUT, '_cam_log.txt')


def log(msg):
    os.makedirs(OUT, exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(str(msg) + '\n')
    print(msg)


def app():
    return adsk.core.Application.get()


def cam_product(doc=None, activate=True):
    """CAM product of the document; activates the Manufacture workspace once if the product does not exist yet."""
    a = app()
    doc = doc or a.activeDocument

    def get():
        try:   # itemByProductType raises 'failed to find product' (2706) instead of returning null
            return adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))
        except Exception:
            return None
    cam = get()
    if cam is None and activate:
        a.userInterface.workspaces.itemById('CAMEnvironment').activate()
        adsk.doEvents()
        cam = get()
    return cam


def occurrence(design, key):
    for occ in design.rootComponent.allOccurrences:
        if key.lower() in occ.component.name.lower():
            return occ
    return None


# ---------------------------------------------------------------- discovery
def param_dump(params, only_visible=True):
    out = []
    for i in range(params.count):
        p = params.item(i)
        try:
            if only_visible and not p.isVisible:
                continue
            out.append((p.name, p.expression))
        except Exception:
            out.append((p.name, '?'))
    return out


def tool_libraries(location='fusion'):
    """[(url, name)] of the tool libraries at the given location."""
    loc = {'fusion': adsk.cam.LibraryLocations.Fusion360LibraryLocation,
           'local': adsk.cam.LibraryLocations.LocalLibraryLocation,
           'cloud': adsk.cam.LibraryLocations.CloudLibraryLocation}[location]
    tl = adsk.cam.CAMManager.get().libraryManager.toolLibraries
    root = tl.urlByLocation(loc)
    out = []
    def walk(url):
        for u in tl.childAssetURLs(url):
            out.append((u, tl.displayName(u)))
        for f in tl.childFolderURLs(url):
            walk(f)
    walk(root)
    return out


def find_tools(tool_types, location='fusion', library_filter=None, limit=50):
    """Tools whose 'tool_type' parameter is in tool_types (e.g. 'turning general', 'turning grooving',
    'turning boring', 'turning threading'). Returns [(library name, index, tool_type, description, Tool)]."""
    tl = adsk.cam.CAMManager.get().libraryManager.toolLibraries
    found = []
    for url, name in tool_libraries(location):
        if library_filter and library_filter.lower() not in name.lower():
            continue
        lib = tl.toolLibraryAtURL(url)
        if lib is None:
            continue
        for i in range(lib.count):
            t = lib.item(i)
            try:
                tt = t.parameters.itemByName('tool_type').value.value
            except Exception:
                continue
            if tt in tool_types:
                found.append((name, i, tt, t.description, t))
                if len(found) >= limit:
                    return found
    return found


# ---------------------------------------------------------------- creation
def collection(items):
    oc = adsk.core.ObjectCollection.create()
    for it in items:
        oc.add(it)
    return oc


def turning_setup(cam, models, name, stock_mode=None, params=None):
    """Turning setup on the given models (list of Occurrence / BRepBody). params: {paramName: expression}.
    For the E1 rotor unit pass the revolved bodies only ('disc', 'shaft'): the spun profile of the 29 B-spline blades
    makes the turning profile fail ('No valid turning profile found'). Setup.models (after creation) wants an
    ObjectCollection: use collection([...])."""
    si = cam.setups.createInput(adsk.cam.OperationTypes.TurningOperation)
    si.models = models
    si.name = name
    if stock_mode is not None:
        si.stockMode = stock_mode
    for k, v in (params or {}).items():
        try:
            si.parameters.itemByName(k).expression = v
        except Exception:
            log('setup param %s=%s failed: %s' % (k, v, traceback.format_exc().splitlines()[-1]))
    s = cam.setups.add(si)
    log('setup created: %s' % s.name)
    return s


def operation(setup, strategy, name, tool=None, params=None, generate=False):
    """One operation in the setup. params: {paramName: expression}; unknown names are logged and skipped."""
    ops = setup.operations
    oi = ops.createInput(strategy)
    oi.displayName = name
    if tool is not None:
        oi.tool = tool
    for k, v in (params or {}).items():
        try:
            oi.parameters.itemByName(k).expression = v
        except Exception:
            log('op %s param %s=%s failed: %s' % (name, k, v, traceback.format_exc().splitlines()[-1]))
    op = ops.add(oi)
    log('operation created: %s (%s) tool=%s' % (op.name, strategy, tool.description if tool else None))
    if generate:
        cam = adsk.cam.CAM.cast(app().activeDocument.products.itemByProductType('CAMProductType'))
        cam.generateToolpath(op)
    return op


def report(cam):
    out = []
    for i in range(cam.setups.count):
        s = cam.setups.item(i)
        ops = []
        for j in range(s.allOperations.count):
            o = s.allOperations.item(j)
            ops.append({'name': o.name, 'strategy': o.strategy, 'error': o.error if o.hasError else '',
                        'warning': o.warning if o.hasWarning else ''})
        out.append({'setup': s.name, 'type': s.operationType, 'operations': ops})
    return out


def run(context):
    ui = None
    try:
        a = app(); ui = a.userInterface
        cam = cam_product()
        ui.messageBox('CAM product: %s setups, strategies known after a setup exists.' % cam.setups.count)
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
