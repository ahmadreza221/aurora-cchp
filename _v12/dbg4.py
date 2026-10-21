import FreeCAD as App
d=App.openDocument('/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-3D/GR180_Shaft_assembly.FCStd')
for n in ('Shaft','NoseCone','TurbineNut'):
    s=d.getObject(n).Shape; print('CHK',n,s.ShapeType,len(s.Solids),round(s.Volume,2),s.isValid(),[round(x.Volume,2) for x in s.Solids])
