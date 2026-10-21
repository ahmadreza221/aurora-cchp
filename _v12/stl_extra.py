import FreeCAD as App, Mesh, os
OUT=os.path.expanduser('~/Desktop/GR180-3D')
d=App.openDocument(os.path.join(OUT,'GR180_Shaft_assembly.FCStd'))
for o in d.Objects:
    if o.Name.startswith(('OilRing','FrontShim','FrontBearing_608','RearBearing_608','WaveSpring','RearSpacer')):
        m=Mesh.Mesh(); m.addFacets(o.Shape.tessellate(0.03)); m.write(os.path.join(OUT,'GR180_'+o.Name+'.stl')); print('stl',o.Name)
