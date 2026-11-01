"""Autodesk Fusion add-in: an "AURORA-1000" panel in the Design workspace (Solid tab) for "AURORA-1000 Package rev5".

  Assembly sequence  every part starts hidden; the parts fly into place in the build order of docs/08 sec. 19 (checked
                     step by step along each path by cad/engine/a1000_assembly_check.py), with a label per step in the
                     top-left corner of the view:
                       1 rotor stack on the build table above the stand, balanced as one unit
                       2 lower shell on the stand: scroll casing, scroll, turbine and compressor casings, front bearing
                         housing FB-2 with the lower bearing halves, stator half-module (split parts are shown whole)
                       3 the balanced rotor is lowered in as one unit
                       4 upper halves: FB-1, turbine casing, scroll, scroll casing; exhaust frame from the rear, then the
                         JB2 seal ring and cartridge from the rear
                       5 combustor can and head from above
                       6 package: base frame with the oil reservoir, lube module, gearbox, generator, couplings, inlet,
                         recuperator, piping
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
CMDS = [('A1000AnimAssembly', 'Assembly sequence', 'Parts fly into place in the build order of docs/08 sec. 19 (about 1 min). '
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

# build order (docs/08 sec. 19, cad/engine/a1000_assembly_seq.py): (step title, step note, [(label, part-name prefixes,
# offset mm the parts fly in from[, offset they stop at, again]), ...]). A move ends at its stop offset (default home);
# 'again' moves parts an earlier move already placed (the rotor is stacked above the stand, then lowered in).
XA, XF, ZD, ZU = (650, 0, 0), (-650, 0, 0), (0, 0, -900), (0, 0, 900)
HI = (0, 0, 700)                                                    # the rotor is stacked 700 mm above its place
ROTOR_PARTS = ['RT-1', 'Impeller', 'A1000_R1 disc', 'A1000_R2 disc', 'Blisk 1 blade', 'Blisk 2 blade']


def _hi(off):
    return tuple(a + b for a, b in zip(off, HI))


STEPS = [
    ('1/6  Rotor stack, balanced as one unit',
     'Curvic couplings centre every joint. M42 tie bolt (IN718) 185 kN; turbine flanges 16 x M10 studs, nuts started on the '
     'stud tips with the disc 6 mm short, then run down.',
     [('Front stub shaft with the thrust collar (RT-101)', ['RT-101'], _hi(XF), HI),
      ('Impeller 1, Ti-6Al-4V, 13 + 13 blades', ['Impeller 1'], _hi(XA), HI),
      ('Compressor spacer (RT-104)', ['RT-104'], _hi(XA), HI),
      ('Impeller 2, 13 + 13 blades', ['Impeller 2'], _hi(XA), HI),
      ('Drum, IN718 (RT-105)', ['RT-105'], _hi(XA), HI),
      ('Tie bolt M42 (RT-102) and nut (RT-103) from the front', ['RT-102', 'RT-103'], _hi((-1100, 0, 0)), HI),
      ('R1 blisk with the drum - R1 studs and nuts (RT-111)', ['A1000_R1 disc', 'Blisk 1 blade', 'RT-111'], _hi(XA), HI),
      ('Turbine spacer ring R1 - R2 (RT-107)', ['RT-107'], _hi(XA), HI),
      ('R2 blisk with the R1 - R2 studs and nuts (RT-112)', ['A1000_R2 disc', 'Blisk 2 blade', 'RT-112'], _hi(XA), HI),
      ('Rear stub shaft with the R2 - stub studs and nuts (RT-106, RT-113)', ['RT-106', 'RT-113'], _hi(XA), HI)]),
    ('2/6  Lower shell on the build stand',
     'Lower halves first; split rings, carriers and bearing parts are shown whole (in the machine they are halves).',
     [('Scroll pressure casing, lower half (CB-341)', ['CB-341'], ZD),
      ('Hot-gas scroll lower half, deswirl vanes, insulation; lower scroll pins', ['CB-331', 'CB-332', 'CB-333', 'CB-360'], ZD),
      ('Turbine outer casing, lower half (HS-202, bottom key cast on)', ['HS-202'], ZD),
      ('Compressor casing with vaned diffusers and return channel', ['Compressor casing', 'Diffuser', 'Return-channel'], ZD),
      ('Inlet casing, lower half (IN-502, phase 3): onto the compressor-casing spigot, with the FB-2 foot brackets', ['IN-502'], ZD),
      ('Front bearing housing, lower half (FB-2), onto the IN-502 brackets', ['FB-2'], ZD),
      ('JB1: split ISFD ring, carrier, 4 pads; thrust bearing: split base rings, 8 + 4 pads', ['JB1', 'TB '], (0, 0, -500)),
      ('Stator half-module: C1 + C2, NGV1 / NGV2, shrouds, gap liners, diaphragms, NGV1 seals, support keys',
       ['NGV1', 'NGV2', 'HS-210', 'HS-211', 'HS-220', 'HS-221', 'HS-222', 'HS-234', 'HS-230', 'HS-231', 'HS-232', 'HS-233',
        'CB-350', 'HS-240'], ZD)]),
    ('3/6  The balanced rotor is lowered in',
     'Front on the JB1 lower pads, rear stub on a tail-stock support tool until JB2 is in.',
     [('Rotor (balanced unit)', ROTOR_PARTS, HI, (0, 0, 0), True)]),
    ('4/6  Upper halves, exhaust frame, JB2 from the rear',
     'Upper halves come straight down. JB2 is a one-piece cartridge that slides on from the rear and can be pulled without '
     'opening the casing.',
     [('Front bearing housing, upper half (FB-1)', ['FB-1'], ZU),
      ('Inlet casing, upper half (IN-501): hub wall over FB-1', ['IN-501'], ZU),
      ('Turbine outer casing, upper half (HS-201, top key into the carrier slot)', ['HS-201'], ZU),
      ('Hot-gas scroll upper half (CB-330)', ['CB-330'], ZU),
      ('Scroll pressure casing, upper half (CB-340)', ['CB-340'], ZU),
      ('Exhaust air manifold and exhaust frame with its struts (from the rear)', ['Exhaust diffuser', 'EX-401', 'EX-402', 'EX-410',
                                                                                'EX-411', 'EX-413', 'EX-414'], (1000, 0, 0)),
      ('JB2 split seal ring (labyrinth + buffer + windback)', ['JB2 front seal'], (400, 0, 0)),
      ('JB2 cartridge: housing, ISFD ring, carrier, 4 pads, heat shield, frame support ring', ['JB2 bearing', 'JB2 integral', 'JB2 pad',
                                                                                             'JB2 tilting', 'JB2 heat shield', 'EX-412'], (600, 0, 0)),
      ('JB2 end cover; exhaust collector, hub cover, transition', ['JB2 end cover', 'Exhaust collector', 'EX-420', 'EX-421', 'EX-430'],
       (800, 0, 0))]),
    ('5/6  Combustor',
     'DLE can on top, scroll to NGV1. Fuel circuits P / A / B1 / B2 end in unions at the bulkhead on the head cover.',
     [('Can casing and base plate', ['CB-301', 'CB-302'], (0, 0, 1300)),
      ('Impingement sleeve and liner', ['CB-321', 'CB-320'], (0, 0, 1300)),
      ('Head cover with 7 premixers (pilot + 6 mains)', ['CB-303', 'CB-310'], (0, 0, 1000)),
      ('Fuel manifolds P / A / B1 / B2', ['CB-370'], (0, 0, 800)),
      ('Igniter (along its tilted axis) + 2 UV flame scanners', ['CB-371'], (0, 120, 800))]),
    ('6/6  Package',
     'The core waits on the crane: the plenum lower half goes on the base frame first and the core is lowered into it. '
     'FB lines in two spools each (in through the open tunnel mouth, union in front of the plenum). Oil reservoir in the '
     'frame, drains fall to it. Bought-in recuperator, 10:1 gearbox, 1,250 kVA generator.',
     [('Base frame (skid) with the oil reservoir, pipe supports', ['Base frame', 'LO-100', 'PL-90'], (0, 0, -1100)),
      ('Lube oil module', ['Lube oil'], (0, -1000, 0)),
      ('Plenum lower half (IN-511, phase 3): the engine core is lowered into it', ['IN-511'], (0, 0, 1100)),
      ('FB oil block; JB1 / TB oil, FB drain, vent and buffer-air lines through the tunnel', ['PL-01', 'PL-02', 'PL-03', 'PL-05',
                                                                                               'PL-07', 'PL-09'], (-900, 0, 0)),
      ('Epicyclic gearbox 10:1, starter motor, synchronous generator', ['Epicyclic', 'Starter', 'Synchronous generator'], (0, 0, 900)),
      ('Couplings, from above through the open tunnel', ['High-speed coupling', 'Low-speed coupling'], (0, 0, 700)),
      ('Plenum upper half (IN-510) and filter-house adapter (IN-520)', ['IN-510', 'IN-520', 'Air inlet'], (0, 0, 1100)),
      ('Recuperator (bought in), ducts, BOV, economizer + stack', ['Recuperator', 'EX-44', 'EX-45', 'EX-46', 'EX-47'], (0, 1400, 0)),
      ('JB2 oil, drain and vent lines (hoses at the struts), gearbox oil feed', ['PL-04', 'PL-06', 'PL-08', 'PL-13'], (0, -900, 0)),
      ('Gas valve block and fuel hoses, combustor drains', ['PL-10', 'PL-12'], (0, -900, 0))]),
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
    """STEPS with the part occurrences matched by name prefix: [(title, note, [(label, occs, start, stop)])]; a part goes to
    the first move that names it, except moves marked 'again' (they take parts already placed); unnamed parts come last."""
    parts = [o for _, subs in occurrences(design) for o in subs]
    free, out = [True] * len(parts), []                             # Occurrence objects are not hashable
    for title, note, moves in STEPS:
        mv = []
        for m in moves:
            label, prefixes, off = m[:3]
            stop = m[3] if len(m) > 3 else (0, 0, 0)
            again = len(m) > 4 and m[4]
            idx = [i for i, o in enumerate(parts) if (again or free[i]) and o.component.name.startswith(tuple(prefixes))]
            for i in idx:
                free[i] = False
            if idx:
                mv.append((label, [parts[i] for i in idx], off, stop))
        out.append((title, note, mv))
    rest = [o for i, o in enumerate(parts) if free[i]]
    if rest:
        out.append(('Other parts', '', [('Remaining parts', rest, ZU, (0, 0, 0))]))
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
    for _, occs, _, _ in [m for s in steps for m in s[2]]:
        for o in occs:
            o.isLightBulbOn = False
    home = {}                                                       # occurrence -> home translation (cm), first sight
    view(*VIEW_ENGINE)
    frames = 0
    for k, (title, note, moves) in enumerate(steps):
        if title.startswith('6/6'):
            view(*VIEW_PACKAGE)
        hud(design, [('AURORA-1000 assembly sequence   ' + title, 16, TITLE), (note, 12, NOTE)])
        wait(TITLE_S)
        for label, occs, off, stop in moves:
            if _state['stop']:
                return
            hud(design, [('AURORA-1000 assembly sequence   ' + title, 16, TITLE), (note, 12, NOTE),
                         (label, 14, PART)])
            base = []
            for o in occs:
                m0 = o.transform2
                key = o.fullPathName
                if key not in home:
                    home[key] = (m0.translation.x, m0.translation.y, m0.translation.z)
                base.append((m0, home[key]))
            a = [v / 10.0 for v in off]; b = [v / 10.0 for v in stop]  # mm -> cm
            t0 = time.time()
            while True:
                f = min(1.0, (time.time() - t0) / MOVE_S)
                s = ease(f)
                for o, (m0, h) in zip(occs, base):
                    m = m0.copy()
                    m.translation = adsk.core.Vector3D.create(*[h[i] + a[i] + (b[i] - a[i]) * s for i in range(3)])
                    o.transform2 = m
                    if not o.isLightBulbOn:
                        o.isLightBulbOn = True
                frame(); frames += 1
                if f >= 1.0 or _state['stop']:
                    break
            log('  %-60s %2d parts' % (label[:60], len(occs)))
            wait(PAUSE_S)
    hud(design, [('AURORA-1000 assembled: %d parts' % len({o.fullPathName for s in steps for m in s[2] for o in m[1]}), 16, TITLE)])
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
