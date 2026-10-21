# GR180 step-by-step assembly animation for FreeCAD GUI (works on the open GR180_Shaft_assembly document)
try:
    import FreeCAD as App, FreeCADGui as Gui
    try:
        from PySide6 import QtCore
    except ImportError:
        from PySide import QtCore
except ImportError:
    App=Gui=QtCore=None
ORDER=[('ShaftTunnel',(0,0,0)),('FrontBearing_Oring',(-60,0,0)),('FrontBearing_608_hybrid_8x22x7',(-80,0,0)),('Spacer_22x16x1_5',(-90,0,0)),
       ('WaveSpring_22x16_free3_0_inst2_8',(-100,0,0)),('RearBearing_608_hybrid_8x22x7',(90,0,0)),('Shaft',(-200,0,0)),('Diffuser',(-120,0,0)),
       ('Compressor',(-150,0,0)),('NoseCone',(-180,0,0)),('IntakeOuter',(-160,0,0)),('Intake',(-190,0,0)),
       ('SupplyLines',(0,120,0)),('SupplySeals',(0,140,0)),('CC_Inner',(0,0,130)),('CC_Outer',(0,0,150)),('CC_FrontCap',(0,0,170)),
       ('CC_RearCone',(0,0,190)),('CC_Vaporisers',(0,0,210)),('NGV',(150,0,0)),('Turbine',(170,0,0)),('TurbineNut',(190,0,0)),
       ('Exhaust',(220,0,0)),('Casing',(0,180,0)),('Starter',(-260,0,0))]
STEPS=30; MS=25
def _doc():
    d=App.getDocument('GR180_Shaft_assembly') if 'GR180_Shaft_assembly' in App.listDocuments() else App.ActiveDocument
    return d
def _home(o):
    if 'GR180Home' not in o.PropertiesList:
        o.addProperty('App::PropertyPlacement','GR180Home','GR180'); o.GR180Home=o.Placement
    return o.GR180Home
def _objs(d):
    return [(d.getObject(n),off) for n,off in ORDER if d.getObject(n)]
def reset():
    d=_doc()
    for o,off in _objs(d):
        h=_home(o); o.Placement=h
        if o.Name!='ShaftTunnel': o.ViewObject.Visibility=False
    d.GR180Step=0 if 'GR180Step' in d.PropertiesList else 0
    if 'GR180Step' not in d.PropertiesList: d.addProperty('App::PropertyInteger','GR180Step','GR180')
    d.GR180Step=1; d.recompute(); Gui.SendMsgToActiveView('ViewFit'); App.Console.PrintMessage('GR180: reset - only tunnel shown, press Next\n')
_t=None
def next_step():
    global _t
    d=_doc()
    if 'GR180Step' not in d.PropertiesList: reset()
    ol=_objs(d); i=d.GR180Step
    if i>=len(ol): App.Console.PrintMessage('GR180: assembly complete\n'); return
    o,off=ol[i]; h=_home(o); d.GR180Step=i+1
    o.ViewObject.Visibility=True
    st={'k':0}
    def tick():
        k=st['k']; f=1-(k/STEPS); f=f*f*(3-2*f)
        o.Placement=App.Placement(h.Base+App.Vector(*off)*f,h.Rotation); Gui.updateGui()
        st['k']+=1
        if k>=STEPS: _t.stop(); o.Placement=h; App.Console.PrintMessage('GR180: placed %s (%d/%d)\n'%(o.Name,i+1,len(ol)))
    _t=QtCore.QTimer(); _t.timeout.connect(tick); _t.start(MS)
def show_all():
    d=_doc()
    for o,off in _objs(d): o.Placement=_home(o); o.ViewObject.Visibility=True
    if 'GR180Step' in d.PropertiesList: d.GR180Step=len(_objs(d))
ROTOR=['Shaft','NoseCone','Compressor','Turbine','TurbineNut']
_s=None
def spin():
    global _s
    if _s and _s.isActive(): _s.stop(); return
    d=_doc(); ob=[d.getObject(n) for n in ROTOR if d.getObject(n)]
    for o in ob: _home(o)
    st={'a':0.0}
    def tick():
        st['a']=(st['a']+6)%360
        for o in ob:
            h=o.GR180Home; o.Placement=App.Placement(App.Vector(0,0,0),App.Rotation(App.Vector(1,0,0),st['a'])).multiply(h)
        Gui.updateGui()
    _s=QtCore.QTimer(); _s.timeout.connect(tick); _s.start(30)
