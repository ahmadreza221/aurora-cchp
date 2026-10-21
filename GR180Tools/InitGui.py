# GR180 Tools: adds a global "GR180" toolbar (Reset / Next part / Show all / Spin rotor)
def _gr180_toolbar():
    import FreeCADGui as Gui, sys, os
    try:
        from PySide6 import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets
    p=os.path.join(os.path.expanduser('~'),'Desktop','GR180-3D','GR180Tools')
    if p not in sys.path: sys.path.insert(0,p)
    import gr180_anim
    mw=Gui.getMainWindow()
    if mw.findChild(QtWidgets.QToolBar,'GR180Toolbar'): return
    tb=QtWidgets.QToolBar('GR180',mw); tb.setObjectName('GR180Toolbar'); mw.addToolBar(tb)
    for txt,fn in [('GR180 Reset',lambda: gr180_anim.reset()),('GR180 Next part ▶',lambda: gr180_anim.next_step()),
                   ('Show all',lambda: gr180_anim.show_all()),('Spin rotor ⟳',lambda: gr180_anim.spin())]:
        a=tb.addAction(txt); a.triggered.connect(fn)
    tb.show()
try:
    try:
        from PySide6 import QtCore
    except ImportError:
        from PySide import QtCore
    QtCore.QTimer.singleShot(3000,_gr180_toolbar)
except Exception as e:
    import FreeCAD; FreeCAD.Console.PrintError('GR180Tools: %s\n'%e)
