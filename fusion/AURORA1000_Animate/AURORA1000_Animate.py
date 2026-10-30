"""Autodesk Fusion add-in: an "AURORA-1000" panel in the Design workspace (Solid tab) for "AURORA-1000 Package rev5".

  Assembly sequence  every part starts hidden; the parts fly into place in the build order of docs/08 sec. 13, with a
                     label per step in the top-left corner of the view:
                       1 front stub + thrust collar, impeller 1, spacer, impeller 2, drum, M42 tie bolt and nut
                       2 R1 blisk + drum - R1 studs, spacer ring RT-107, R2 blisk, rear stub + studs (balanced outside)
                       3 thrust and journal bearing cartridges
                       4 lower halves of the split casings, NGV rings and diaphragms, upper halves
                       5 scroll and can combustor, inlet, exhaust, recuperator, gearbox, generator, lube module, skid
  Spin rotor         the rotating groups (rotor shaft group with the high-speed coupling, blisks, impellers) turn slowly
                     about the engine axis (package X axis, y = z = 0, +X right-handed = the CAD +theta); the low-speed
                     coupling turns at -1/10 (star epicyclic 10:1: the output ring turns against the sun). Stationary
                     parts, bearing pads included, stay put; the casings keep their see-through look.
  Reset              stops a running animation and puts every occurrence back to the transform and visibility it had
                     when the animation started (each animation also does this itself when it ends).

The package is a direct-modelling design (fusion/AURORA1000_Package): one root occurrence per group, one sub-occurrence
per part. The animation only sets Occurrence.transform2 / isLightBulbOn (the parts through root-context proxies) and
redraws with Viewport.refresh + adsk.doEvents inside the command's execute event.
Install: copy this folder to the Fusion AddIns folder (the manifest has runOnStartup), or Utilities > Add-Ins > + > pick
this folder. From a script (e.g. the Fusion MCP) start it with app.scripts.itemByPath(folder).run(): Fusion sends no
events to handlers made by a script that has already ended.
"""
import math
import os
import time
import traceback

import adsk.core
import adsk.fusion

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, '_last_run.log')
WS_ID, TAB_ID, PANEL_ID = 'FusionSolidEnvironment', 'SolidTab', 'A1000AnimatePanel'
CMDS = [('A1000AnimAssembly', 'Assembly sequence', 'Parts fly into place in the build order of docs/08 sec. 13 (about 1 min). '
         'Click any AURORA-1000 button to stop.', 'assembly'),
        ('A1000AnimSpin', 'Spin rotor', 'The rotor turns slowly about the engine axis; the generator side turns at 1/10 '
         '(10:1 gearbox). Click any AURORA-1000 button to stop.', 'spin'),
        ('A1000AnimReset', 'Reset', 'Stop and put every part back to its original position and visibility.', 'reset')]
MARK = 'A1000 Rotor shaft'                                          # a group that only the package has
ROTATING = ('A1000 Rotor shaft', 'A1000 Turbine blisks', 'A1000 Compressor impellers')   # whole groups, 15,000 rpm
GEN_SIDE = ('Low-speed coupling',)                                  # parts on the 1,500 rpm side
GEAR = -10.0                                                        # star epicyclic: output against the input
SPIN_DEG, SPIN_S, SPIN_RAMP = 720.0, 20.0, 3.0                      # two turns in 20 s, 3 s spin-up / run-down
MOVE_S, PAUSE_S, TITLE_S = 0.9, 0.15, 1.6
TITLE, NOTE, PART = (255, 255, 255), (215, 225, 240), (255, 170, 60)    # label colours (Fusion's dark canvas)

# build order: (step title, step note, [(label, part-name prefixes, offset mm the parts fly in from), ...])
XA, XF, ZD, ZU = (650, 0, 0), (-650, 0, 0), (0, 0, -900), (0, 0, 900)
STEPS = [
    ('1/5  Compressor rotor stack',
     'Curvic couplings centre every joint. The M42 tie bolt (IN718) clamps the stack with 185 kN.',
     [('Front stub shaft with the thrust collar (RT-101)', ['RT-101'], XF),
      ('Impeller 1, Ti-6Al-4V, 13 + 13 blades', ['Impeller 1'], XA),
      ('Compressor spacer (RT-104)', ['RT-104'], XA),
      ('Impeller 2, 13 + 13 blades', ['Impeller 2'], XA),
      ('Drum, IN718 (RT-105)', ['RT-105'], XA),
      ('Tie bolt M42 (RT-102)', ['RT-102'], (-1100, 0, 0)),
      ('Tie-bolt nut (RT-103)', ['RT-103'], (-450, 0, 0))]),
    ('2/5  Turbine rotor stack',
     'Bolted curvic flanges with 16 x M10 IN718 studs. The rotor is balanced outside the engine.',
     [('R1 blisk, cast MAR-M247, 59 blades', ['A1000_R1 disc', 'Blisk 1 blade'], XA),
      ('Studs + nuts drum - R1 (RT-111)', ['RT-111'], (300, 0, 0)),
      ('Turbine spacer ring R1 - R2 (RT-107)', ['RT-107'], XA),
      ('R2 blisk, cast MAR-M247, 36 blades', ['A1000_R2 disc', 'Blisk 2 blade'], XA),
      ('Studs + nuts R1 - R2 (RT-112)', ['RT-112'], (300, 0, 0)),
      ('Rear stub shaft (RT-106)', ['RT-106'], XA),
      ('Studs + nuts R2 - rear stub (RT-113)', ['RT-113'], (300, 0, 0))]),
    ('3/5  Bearing cartridges',
     'Tilting-pad journal bearings with S-spring damper rings (ISFD); double-acting thrust bearing on the collar.',
     [('Thrust bearing: 8 + 4 pads, carrier rings, housing + inlet hub fairing', ['TB '], (-600, 0, 0)),
      ('Journal bearing 1: 5 pads, carrier, ISFD ring, housing', ['JB1'], (-700, 0, 0)),
      ('Journal bearing 2 in the exhaust hub: 5 pads, carrier, ISFD ring, housing', ['JB2'], (700, 0, 0))]),
    ('4/5  Split casings: lower halves, NGV rings, upper halves',
     'The rotor goes into the lower halves. NGV rings, carriers and diaphragms are split too (shown whole in the CAD).',
     [('Turbine outer casing, lower half (HS-202)', ['HS-202'], ZD),
      ('Compressor casing with vaned diffusers and return channel', ['Compressor casing', 'Diffuser', 'Return-channel'], ZD),
      ('Front diaphragm + seal honeycomb (HS-230, HS-231)', ['HS-230', 'HS-231'], ZD),
      ('NGV1 ring (48 vanes), shroud carrier C1, R1 honeycomb shroud', ['NGV1', 'HS-210', 'HS-211'], ZD),
      ('Gap liner and gap ring R1 - NGV2 (HS-222, HS-234)', ['HS-222', 'HS-234'], ZD),
      ('NGV2 ring (24 vanes), shroud carrier C2, R2 honeycomb shroud', ['NGV2', 'HS-220', 'HS-221'], ZD),
      ('Interstage diaphragm + seal honeycomb (HS-232, HS-233)', ['HS-232', 'HS-233'], ZD),
      ('Radial centring pins x 8 (HS-240)', ['HS-240'], (0, 0, 600)),
      ('Turbine outer casing, upper half (HS-201)', ['HS-201'], ZU)]),
    ('5/5  Combustor, exhaust, recuperator, gearbox, generator, skid',
     'DLE can combustor on top, scroll to NGV1; bought-in recuperator, 10:1 gearbox and 1,250 kVA generator.',
     [('Scroll lower halves: pressure casing CB-341, hot-gas casing CB-331', ['CB-341', 'CB-331'], ZD),
      ('Deswirl vanes, NGV1 leaf seals, scroll support pins', ['CB-332', 'CB-350', 'CB-360'], (0, 0, 600)),
      ('Scroll upper halves + insulation cassettes', ['CB-330', 'CB-333', 'CB-340'], ZU),
      ('Can casing and base plate', ['CB-301', 'CB-302'], (0, 0, 1300)),
      ('Impingement sleeve and liner', ['CB-321', 'CB-320'], (0, 0, 1300)),
      ('Head cover with 7 premixers (pilot + 6 mains)', ['CB-303', 'CB-310'], (0, 0, 1000)),
      ('Fuel manifolds, igniter + 2 UV flame scanners', ['CB-370', 'CB-371'], (0, 0, 800)),
      ('Air inlet plenum + bellmouth', ['Air inlet'], (0, 0, 1100)),
      ('Exhaust diffuser with 5 struts, exhaust collector', ['Exhaust'], (1000, 0, 0)),
      ('Recuperator (bought in) and ducts', ['Recuperator'], (0, 1400, 0)),
      ('High-speed coupling, epicyclic gearbox 10:1, starter motor', ['High-speed coupling', 'Epicyclic', 'Starter'], (-900, 0, 0)),
      ('Low-speed coupling and synchronous generator', ['Low-speed coupling', 'Synchronous generator'], (-1300, 0, 0)),
      ('Lube oil module', ['Lube oil'], (0, -1000, 0)),
      ('Base frame (skid)', ['Base frame'], (0, 0, -1100))]),
]
VIEW_ENGINE = ((45.0, 0.0, 0.0), 220.0)                            # camera target (cm) and view extents
VIEW_PACKAGE = ((-55.0, 42.0, 52.0), 520.0)
VIEW_DIR = (0.6, -0.8, 0.5)

_app = adsk.core.Application.get()
_handlers = []
_state = dict(busy=False, stop=False, orig=None, design=None, hud=None)


def log(s, new=False):
    with open(LOG, 'w' if new else 'a') as f:
        f.write('%s  %s\n' % (time.strftime('%H:%M:%S'), s))


def package():
    """The active design if it is the AURORA-1000 package, else None (with a message)."""
    design = adsk.fusion.Design.cast(_app.activeProduct)
    if design:
        root = design.rootComponent
        if any(root.occurrences.item(i).component.name == MARK for i in range(root.occurrences.count)):
            return design
    _app.userInterface.messageBox('Open "AURORA-1000 Package rev5" (Design workspace) first.', 'AURORA-1000')
    return None


def occurrences(design):
    """[(group occurrence, [part occurrences])]. The parts are proxies in the root context: inside a command Fusion only
    takes a nested transform through such a proxy, and its transform2 is then relative to the root."""
    root = design.rootComponent
    out = []
    for i in range(root.occurrences.count):
        g = root.occurrences.item(i)
        out.append((g, [g.component.occurrences.item(j).createForAssemblyContext(g) for j in range(g.component.occurrences.count)]))
    return out


def capture(design):
    _state['design'] = design
    _state['orig'] = [(o, o.transform2.asArray(), o.isLightBulbOn) for g, subs in occurrences(design) for o in [g] + subs]


def restore():
    """Original transforms and light bulbs back; returns (occurrences restored, mismatches)."""
    n = bad = 0
    for o, arr, bulb in _state['orig'] or []:
        ok = True
        try:
            m = adsk.core.Matrix3D.create(); m.setWithArray(arr)
            o.transform2 = m
            ok = max(abs(a - b) for a, b in zip(o.transform2.asArray(), arr)) < 1e-12   # a proxy reads back via its parent
        except Exception:                                           # occurrence gone (document closed)
            ok = False
        try:                                                        # the light bulb even if the transform failed
            if o.isLightBulbOn != bulb:
                o.isLightBulbOn = bulb
        except Exception:
            ok = False
        n += ok
        bad += not ok
    return n, bad


def frame():
    _app.activeViewport.refresh()
    adsk.doEvents()


def wait(seconds):
    t0 = time.time()
    while time.time() - t0 < seconds and not _state['stop']:
        frame()


def ease(f):
    return f * f * (3.0 - 2.0 * f)


def hud(design, lines):
    """Labels in the top-left corner of the view (custom graphics: not saved, no undo)."""
    hud_clear()
    try:
        g = design.rootComponent.customGraphicsGroups.add()
        y = 28
        for text, px, rgb in lines:
            t = g.addText(text, 'Arial', px, adsk.core.Matrix3D.create())
            t.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255))
            t.viewPlacement = adsk.fusion.CustomGraphicsViewPlacement.create(
                adsk.core.Point3D.create(0, 0, 0), adsk.fusion.ViewCorners.upperLeftViewCorner, adsk.core.Point2D.create(24, y))
            t.viewScale = adsk.fusion.CustomGraphicsViewScale.create(1.0, adsk.core.Point3D.create(0, 0, 0))
            t.billBoarding = adsk.fusion.CustomGraphicsBillBoard.create(None)        # face the screen
            t.depthPriority = 10
            t.isSelectable = False
            y += int(px * 2.4)                                  # the text draws ~1.6 x its size
        _state['hud'] = g
    except Exception:
        log('hud: ' + traceback.format_exc())


def hud_clear():
    g, _state['hud'] = _state['hud'], None
    try:
        if g and g.isValid:
            g.deleteMe()
    except Exception:
        pass


def view(target, extents):
    vp = _app.activeViewport
    cam = vp.camera
    cam.isSmoothTransition = False                                  # a smooth move drops the new view extents
    n = math.sqrt(sum(v * v for v in VIEW_DIR))
    cam.target = adsk.core.Point3D.create(*target)
    cam.eye = adsk.core.Point3D.create(*[t + 2000.0 * v / n for t, v in zip(target, VIEW_DIR)])
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    vp.camera = cam
    cam = vp.camera                                                 # the extents only hold once the new eye is set
    cam.viewExtents = extents
    vp.camera = cam


def plan(design):
    """STEPS with the part occurrences matched by name prefix; parts no step names come last."""
    parts = [o for _, subs in occurrences(design) for o in subs]
    free, out = [True] * len(parts), []                             # Occurrence objects are not hashable
    for title, note, moves in STEPS:
        mv = []
        for label, prefixes, off in moves:
            idx = [i for i, o in enumerate(parts) if free[i] and o.component.name.startswith(tuple(prefixes))]
            for i in idx:
                free[i] = False
            if idx:
                mv.append((label, [parts[i] for i in idx], off))
        out.append((title, note, mv))
    rest = [o for i, o in enumerate(parts) if free[i]]
    if rest:
        out.append(('Other parts', '', [('Remaining parts', rest, ZU)]))
    return out


def animation(name):
    """Decorator: one animation at a time; originals captured before and restored after, also on stop or error."""
    def wrap(body):
        def run_it():
            design = package()
            if not design:
                return
            _state.update(busy=True, stop=False)
            log('%s start' % name, new=True)
            capture(design)
            t0 = time.time()
            try:
                body(design)
            finally:
                hud_clear()
                n, bad = restore()
                frame()
                _state['busy'] = False
                log('%s end after %.1f s (stopped %s): %d occurrences restored, %d mismatches' %
                    (name, time.time() - t0, _state['stop'], n, bad))
        return run_it
    return wrap


@animation('assembly')
def assembly(design):
    steps = plan(design)
    for _, occs, _ in [m for s in steps for m in s[2]]:
        for o in occs:
            o.isLightBulbOn = False
    view(*VIEW_ENGINE)
    frames = 0
    for k, (title, note, moves) in enumerate(steps):
        if title.startswith('5/5'):
            view(*VIEW_PACKAGE)
        hud(design, [('AURORA-1000 assembly sequence   ' + title, 16, TITLE), (note, 12, NOTE)])
        wait(TITLE_S)
        for label, occs, off in moves:
            if _state['stop']:
                return
            hud(design, [('AURORA-1000 assembly sequence   ' + title, 16, TITLE), (note, 12, NOTE),
                         (label, 14, PART)])
            base = [o.transform2 for o in occs]
            vec = [v / 10.0 for v in off]                           # mm -> cm
            t0 = time.time()
            while True:
                f = min(1.0, (time.time() - t0) / MOVE_S)
                s = 1.0 - ease(f)
                for o, m0 in zip(occs, base):
                    m = m0.copy()
                    m.translation = adsk.core.Vector3D.create(m0.translation.x + vec[0] * s, m0.translation.y + vec[1] * s,
                                                              m0.translation.z + vec[2] * s)
                    o.transform2 = m
                    if not o.isLightBulbOn:
                        o.isLightBulbOn = True
                frame(); frames += 1
                if f >= 1.0 or _state['stop']:
                    break
            log('  %-60s %2d parts' % (label[:60], len(occs)))
            wait(PAUSE_S)
    hud(design, [('AURORA-1000 assembled: %d parts' % sum(len(m[1]) for s in steps for m in s[2]), 16, TITLE)])
    wait(TITLE_S)
    log('  %d frames' % frames)


def spin_angle(t):
    """Rotor angle (deg) at time t: linear spin-up, constant speed, linear run-down, SPIN_DEG in SPIN_S."""
    w = SPIN_DEG / (SPIN_S - SPIN_RAMP)
    if t <= 0.0:
        return 0.0
    if t < SPIN_RAMP:
        return 0.5 * w * t * t / SPIN_RAMP
    if t < SPIN_S - SPIN_RAMP:
        return 0.5 * w * SPIN_RAMP + w * (t - SPIN_RAMP)
    if t < SPIN_S:
        return SPIN_DEG - 0.5 * w * (SPIN_S - t) ** 2 / SPIN_RAMP
    return SPIN_DEG


@animation('spin')
def spin(design):
    groups = occurrences(design)
    fast = [g for g, _ in groups if g.component.name in ROTATING]
    slow = [o for _, subs in groups for o in subs if o.component.name.startswith(GEN_SIDE)]
    base = [(o, o.transform2, 1.0) for o in fast] + [(o, o.transform2, 1.0 / GEAR) for o in slow]
    hud(design, [('AURORA-1000 spin rotor', 16, TITLE),
                 ('Rotor (shafts, tie bolt, drum, studs, impellers, blisks, high-speed coupling): 15,000 rpm, shown slowed down.',
                  12, NOTE),
                 ('Generator side after the 10:1 star gearbox: 1,500 rpm, opposite sense. Bearings and casings stand still.',
                  12, NOTE)])
    axis, origin = adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0)
    t0, frames = time.time(), 0
    while not _state['stop']:
        t = time.time() - t0
        a = math.radians(spin_angle(t))
        for o, m0, k in base:
            r = adsk.core.Matrix3D.create(); r.setToRotation(a * k, axis, origin)
            m = m0.copy(); m.transformBy(r)
            o.transform2 = m
        frame(); frames += 1
        if t >= SPIN_S:
            break
    log('  %d rotating groups, %d generator-side parts, %d frames (%.1f fps)' %
        (len(fast), len(slow), frames, frames / max(1e-3, time.time() - t0)))


def reset():
    if _state['busy']:
        _state['stop'] = True
        return
    hud_clear()
    if _state['orig'] and _state['design'] == adsk.fusion.Design.cast(_app.activeProduct):
        n, bad = restore()
        frame()
        log('reset: %d occurrences restored, %d mismatches' % (n, bad), new=True)
    else:
        log('reset: nothing animated yet', new=True)


ACTIONS = dict(assembly=assembly, spin=spin, reset=reset)


class _Execute(adsk.core.CommandEventHandler):
    def __init__(self, action):
        super().__init__()
        self.action = action

    def notify(self, args):
        try:
            ACTIONS[self.action]()
        except Exception:
            log(traceback.format_exc())
            _app.userInterface.messageBox('AURORA-1000 %s failed:\n%s' % (self.action, traceback.format_exc()))


class _Created(adsk.core.CommandCreatedEventHandler):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.execute = _Execute(action)

    def notify(self, args):
        try:
            if _state['busy']:                                      # a click during an animation stops it
                _state['stop'] = True
                return
            args.command.execute.add(self.execute)
        except Exception:
            log(traceback.format_exc())


def run(context):
    try:
        stop(context)                                               # a second load replaces the first one cleanly
        ui = _app.userInterface
        tab = ui.workspaces.itemById(WS_ID).toolbarTabs.itemById(TAB_ID)
        panel = tab.toolbarPanels.add(PANEL_ID, 'AURORA-1000', '', False)
        for cid, name, tip, action in CMDS:
            d = ui.commandDefinitions.addButtonDefinition(cid, name, tip, os.path.join(HERE, 'resources', action, ''))
            h = _Created(action)
            d.commandCreated.add(h)
            _handlers.append(h)
            c = panel.controls.addCommand(d)
            c.isPromoted = True
            c.isPromotedByDefault = True
    except Exception:
        _app.userInterface.messageBox('AURORA1000_Animate failed to start:\n' + traceback.format_exc())


def stop(context):
    try:
        _state['stop'] = True
        hud_clear()
        ui = _app.userInterface
        panel = ui.workspaces.itemById(WS_ID).toolbarTabs.itemById(TAB_ID).toolbarPanels.itemById(PANEL_ID)
        for cid, _, _, _ in CMDS:
            c = panel.controls.itemById(cid) if panel else None
            if c:
                c.deleteMe()
            d = ui.commandDefinitions.itemById(cid)
            if d:
                d.deleteMe()
        if panel:
            panel.deleteMe()
        _handlers.clear()
    except Exception:
        _app.userInterface.messageBox('AURORA1000_Animate failed to stop:\n' + traceback.format_exc())
