import FreeCAD as App, Part
V=App.Vector
src=open('/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-3D/build_gr180.py').read()
i=src.index('def thread_rod'); j=src.index('THREADS=[]'); exec(src[i:j])
AX=V(1,0,0)
rod=thread_rod(V(0,0,0),AX,15,6,1.0,True)
print('core',round(rod.common(Part.makeCylinder(2.0,10,V(2,0,0),AX)).Volume,2),'exp',round(3.14159*4*10,2))
print('box',round(rod.common(Part.makeBox(10,10,10,V(2,0,0))).Volume,2))
print('ann',round(rod.common(Part.makeCylinder(3.2,10,V(2,0,0),AX).cut(Part.makeCylinder(2.6,10,V(2,0,0),AX))).Volume,2))
print('faces',len(rod.Faces),[f.Surface.__class__.__name__ for f in rod.Faces])
