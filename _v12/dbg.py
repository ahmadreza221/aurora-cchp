import FreeCAD as App, Part
d=App.openDocument('/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-3D/GR180_Shaft_assembly.FCStd')
S=d.getObject('Shaft').Shape; N=d.getObject('NoseCone').Shape
c=S.common(N); print('vol',c.Volume,'bb',c.BoundBox)
for sl in c.Solids[:5]: print(' sol',round(sl.Volume,3),sl.BoundBox)
V=App.Vector
cy=Part.makeCylinder(6.5,16,V(-53,0,0),V(1,0,0))
print('S valid',S.isValid(),'S in region',round(S.common(cy).Volume,2),'N valid',N.isValid(),'N in region',round(N.common(cy).Volume,2))
print('N ref (cone minus bore approx)')
print('check S.common(N) via distToShape',S.distToShape(N)[0])
