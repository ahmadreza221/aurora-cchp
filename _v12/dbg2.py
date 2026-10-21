import FreeCAD as App, Part, math
V=App.Vector
src=open('/Users/ahmadrezaasiyaeemoghadam/Desktop/GR180-3D/build_gr180.py').read()
i=src.index('def thread_rod'); j=src.index('THREADS=[]')
exec(src[i:j])
AX=V(1,0,0)
rod=thread_rod(V(-51,0,0),AX,15,6,1.0,True)
blank=Part.makeCylinder(5,13,V(-52.8,0,0),AX).cut(Part.makeCylinder(2.5,13,V(-52.8,0,0),AX))
n=tap(blank,V(-51,0,0),AX,11,6,1.0,True)
print('nut valid',n.isValid(),'vol',round(n.Volume,2),'blank',round(blank.Volume,2),'interf',round(n.common(rod).Volume,4))
tool=thread_rod(V(-51,0,0),AX,15,6,1.0,True,True,ext=0.06)
print('tool',tool.isValid(),round(tool.Volume,2),tool.ShapeType,len(tool.Solids))
ann=Part.makeCylinder(3.061,15,V(-51,0,0),AX).cut(Part.makeCylinder(2.5,15,V(-51,0,0),AX))
k=ann.cut(tool); print('ann',round(ann.Volume,2),'ann-tool',round(k.Volume,2),'ann∩tool',round(ann.common(tool).Volume,2))
t2=Part.Solid(tool.Solids[0]) if tool.Solids else tool
print('rod',rod.isValid(),round(rod.Volume,2),'ann∩rod',round(ann.common(rod).Volume,2))
for tol in (1e-5,1e-4,1e-3):
    try: print('fuzzy',tol,round(ann.common(rod,tol).Volume,2), round(ann.cut(tool,tol).Volume,2))
    except Exception as e: print('fuzzy err',e)
c2=Part.makeCylinder(3.061,13,V(-50,0,0),AX).cut(Part.makeCylinder(2.5,13,V(-50,0,0),AX))
print('inner ann',round(c2.common(rod).Volume,2),round(c2.cut(tool).Volume,2), round(c2.Volume,2))
