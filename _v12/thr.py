import FreeCAD as App, Part, math, time
V=App.Vector
def thread_rod(p0,dvec,L,d,p,lh=False,core=True,ext=0.0):
    """ISO 60deg thread solid along dvec from p0, length L. ext>0 enlarges radially (tap tool clearance)."""
    rM=d/2+ext; rm=d/2-0.6134*p+ext; s=0.05
    h=Part.makeHelix(p,L+2*p,rm-s,0,lh); h.translate(V(0,0,-p))
    wb=0.875*p; wt=0.125*p
    prof=Part.makePolygon([V(rm-s,0,-wb/2),V(rM,0,-wt/2),V(rM,0,wt/2),V(rm-s,0,wb/2),V(rm-s,0,-wb/2)])
    prof.translate(V(0,0,-p))
    ps=Part.BRepOffsetAPI.MakePipeShell(Part.Wire(h)); ps.setBiNormalMode(V(0,0,1)); ps.add(prof); ps.build(); ps.makeSolid(); sw=ps.shape()
    if sw.ShapeType!='Solid' and sw.Solids: sw=sw.Solids[0]
    print('  sweep',sw.ShapeType,round(sw.Volume,2),sw.isValid())
    if sw.Volume<0: sw.reverse()
    sol=Part.makeCylinder(rm,L+2*p,V(0,0,-p),V(0,0,1)).fuse(sw) if core else sw
    print('  fused',round(sol.Volume,2))
    sol=sol.common(Part.makeCylinder(rM+0.01,L,V(0,0,0),V(0,0,1)))
    sol=sol.removeSplitter()
    dv=V(dvec); dv.normalize()
    sol.Placement=App.Placement(p0,App.Rotation(V(0,0,1),dv))
    return Part.Shape(sol).copy() if False else sol.copy()
t=time.time(); r=thread_rod(V(0,0,0),V(1,0,0),15,6,1.0,True)
print('rod',r.isValid(),round(r.Volume,2),len(r.Solids),round(time.time()-t,2))
t=time.time(); nut=Part.makeCylinder(5,6,V(5,0,0),V(1,0,0)).cut(thread_rod(V(-1,0,0),V(1,0,0),17,6,1.0,True,ext=0.06))
print('nut',nut.isValid(),round(nut.Volume,2),round(time.time()-t,2),'common',round(nut.common(r).Volume,4))
t=time.time(); s=thread_rod(V(0,0,0),V(0,1,0),5,3,0.5); print('m3',s.isValid(),round(time.time()-t,2))
tool=thread_rod(V(-1,0,0),V(1,0,0),17,6,1.0,True,ext=0.06)
print('tool valid',tool.isValid())
n2=Part.makeCylinder(5,6,V(5,0,0),V(1,0,0)).cut(tool); print('n2',n2.isValid()); n2.fix(1e-5,1e-5,1e-4); print('fixed',n2.isValid(),round(n2.Volume,2))
n3=Part.makeCylinder(5,6,V(5,0,0),V(1,0,0)).cut(Part.makeCylinder(3.06,6,V(5,0,0),V(1,0,0)))
rid=Part.makeCylinder(3.06,8,V(4,0,0),V(1,0,0)).cut(tool); print('rid',rid.isValid())
n3=n3.fuse(rid.common(Part.makeCylinder(3.1,6,V(5,0,0),V(1,0,0)))); print('n3',n3.isValid(),round(n3.Volume,2))
