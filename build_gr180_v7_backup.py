import FreeCAD as App, Part, Sketcher, Mesh, os, math, glob
App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('CreateBackupFiles',False)
for f in glob.glob(os.path.expanduser('~/Desktop/GR180-3D/*.FCBak')): os.remove(f)
OUT=os.path.expanduser('~/Desktop/GR180-3D'); os.makedirs(OUT,exist_ok=True)
V=App.Vector
def profile_sketch(body,name,pts):
    sk=body.newObject('Sketcher::SketchObject',name)
    xy=[f for f in body.Origin.OriginFeatures if f.Role=='XY_Plane'][0]
    try: sk.AttachmentSupport=[(xy,'')]
    except Exception: sk.Support=(xy,[''])
    sk.MapMode='FlatFace'
    n=len(pts)
    for i in range(n):
        a,b=pts[i],pts[(i+1)%n]
        sk.addGeometry(Part.LineSegment(V(a[0],a[1],0),V(b[0],b[1],0)))
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%n,1))
    return sk
def revolve(body,sk,name):
    r=body.newObject('PartDesign::Revolution',name); r.Profile=sk
    r.ReferenceAxis=(sk,['H_Axis']); r.Angle=360; sk.Visibility=False; return r
def hole_pattern(doc,body,base,name,x0,length,pcd,d,n):
    c=body.newObject('PartDesign::SubtractiveCylinder',name)
    c.Radius=d/2; c.Height=length
    c.Placement=App.Placement(V(x0,pcd/2,0),App.Rotation(V(0,1,0),90))
    doc.recompute()
    p=body.newObject('PartDesign::PolarPattern',name+'_x%d'%n)
    p.Originals=[c]; p.Axis=( [f for f in body.Origin.OriginFeatures if f.Role=='X_Axis'][0],['']); p.Angle=360; p.Occurrences=n
    c.Visibility=False; body.Tip=p; doc.recompute(); return p
def save(doc,body,fname):
    doc.recompute()
    doc.saveAs(os.path.join(OUT,fname+'.FCStd'))
    s=body.Shape; s.exportStep(os.path.join(OUT,fname+'.step'))
    m=Mesh.Mesh(); m.addFacets(s.tessellate(0.02)); m.write(os.path.join(OUT,fname+'.stl'))
    b=s.BoundBox
    print(fname,'valid',s.isValid(),'solids',len(s.Solids),'bbox %.2f x %.2f x %.2f'%(b.XLength,b.YLength,b.ZLength),'vol %.1f'%s.Volume)
    return s

# ---- Shaft (silversteel), x=0 at front (compressor) end
d=App.newDocument('GR180_Shaft'); b=d.addObject('PartDesign::Body','Shaft')
t=math.tan(math.radians(7)); rm=7.0; re=rm-18*t
pts=[(0,0),(0,3),(15,3),(15,3.5),(49,3.5),(49,4),(58,4),(58,re),(76,rm),(127,rm),(145,re),(145,4),(166,4),(166,3),(175,3),(175,0)]
sk=profile_sketch(b,'ShaftProfile',pts); rv=revolve(b,sk,'ShaftRevolve')
b.Label='Shaft (Pos2, silversteel) - threads cosmetic: front M6 LH x15, rear M6 LH x9 (left-hand per GR130 practice)'
d.recompute(); ss=save(d,b,'GR180_Shaft')
# nose cone as separate body
nb=d.addObject('PartDesign::Body','NoseCone'); nb.Label='Nose cone nut (M6 LH, cosmetic thread)'
r0=17.9/2; rt=r0-24.1*math.tan(math.radians(15))
npts=[(0,5),(0,r0),(24.1,rt),(24.1,0),(12,0),(12,2.5),(2,2.5),(2,5)]
nsk=profile_sketch(nb,'NoseProfile',npts); revolve(nb,nsk,'NoseRevolve')
ch=nb.newObject('PartDesign::SubtractiveCylinder','CrossHole'); ch.Radius=1.0; ch.Height=20
ch.Placement=App.Placement(V(21.5,-10,0),App.Rotation(V(1,0,0),-90))
d.recompute(); d.save()
ns=nb.Shape; nb_=ns.BoundBox; print('Nose valid',ns.isValid(),'bbox %.2f x %.2f x %.2f'%(nb_.XLength,nb_.YLength,nb_.ZLength))
ns.exportStep(os.path.join(OUT,'GR180_NoseCone.step'))
m=Mesh.Mesh(); m.addFacets(ns.tessellate(0.02)); m.write(os.path.join(OUT,'GR180_NoseCone.stl'))
Part.makeCompound([ss,ns]).exportStep(os.path.join(OUT,'GR180_Shaft_with_nose.step'))

# ---- Shaft tunnel (aluminium), x=0 at front face
d2=App.newDocument('GR180_Shaft_tunnel'); tb=d2.addObject('PartDesign::Body','ShaftTunnel')
tb.Label='Shaft tunnel (Pos3, aluminium)'
XF=0.1    # tunnel flange face (was 2.0 + 2mm spigot): diffuser plate 4.4 front at -4.3 = 0.5 behind compressor back face (spacer 4.8 on 608 inner ring)
tp=[(XF,13),(XF,20),(7.3,20),(16.8,10.5),(95.3,10.5),(97.3,13),(99.3,13),(99.3,19),(103.3,19),(103.3,13),(107.3,13),
    (107.3,11),(97.3,11),(97.3,8.5),(11.3,8.5),(11.3,11),(XF,11)]
tsk=profile_sketch(tb,'TunnelProfile',tp); revolve(tb,tsk,'TunnelRevolve'); d2.recompute()
hole_pattern(d2,tb,None,'FrontHole_M3',XF,9,34,2.5,6)
hole_pattern(d2,tb,None,'RearHole',99.0,4.6,32,3.2,6)
ts=save(d2,tb,'GR180_Shaft_tunnel')

# ---- checks: radii at stations
def radius_at(s,x):
    c=s.common(Part.makeBox(0.01,60,0.01,V(x,-30,0)))
    return round(c.BoundBox.YMax,2)
for x in (7,30,53,100,160,170): print('shaft x',x,'Ø',2*radius_at(ss,x))
print('shaft Ø mid',2*radius_at(ss,100))
for x in (1,5,50,105,101): print('tunnel x',x,'OD',2*radius_at(ts,x))


# ---- Diffuser (Pos4, aluminium). x=0 = front face of vanes, plate front x=7, plate back x=11.4, rim to x=17
d4=App.newDocument('GR180_Diffuser'); db=d4.addObject('PartDesign::Body','Diffuser'); db.Label='Diffuser (Pos4, aluminium)'
T=4.4
dp=[(7,13),(7,45.5),(17,45.5),(17,44.5),(7+T,44.5),(7+T,13)]
dsk=profile_sketch(db,'PlateRimProfile',dp); revolve(db,dsk,'PlateRimRevolve'); d4.recompute()
# one vane, front view sketch on YZ plane (sketch x->Y, sketch y->Z), padded +X 0..7.2 (0.2 into plate)
yz=[f for f in db.Origin.OriginFeatures if f.Role=='YZ_Plane'][0]
r0,r1,beta,wedge,t0=38.2,53.5,math.radians(70),math.radians(12),1.0
dx,dy=math.cos(beta),math.sin(beta)
def s_at(rr,ox=0,oy=0,ux=dx,uy=dy):
    # distance along (ux,uy) from point (r0+ox,oy) to circle radius rr
    px,py=r0+ox,oy; b=2*(px*ux+py*uy); c=px*px+py*py-rr*rr; return (-b+math.sqrt(b*b-4*c))/2
nx,ny=-dy,dx
b_=2*r0*dx
s1=s_at(r1)
A=(r0,0); B=(r0+s1*dx,s1*dy); D=(r0*math.cos(t0/r0),r0*math.sin(t0/r0))  # leading edge on Ø76.4
# pressure side: from D, direction rotated by wedge toward normal
ux,uy=dx*math.cos(wedge)+nx*math.sin(wedge), dy*math.cos(wedge)+ny*math.sin(wedge)
s2=s_at(r1,D[0]-r0,D[1],ux,uy); C=(D[0]+s2*ux,D[1]+s2*uy)
vs=db.newObject('Sketcher::SketchObject','VaneSketch')
try: vs.AttachmentSupport=[(yz,'')]
except Exception: vs.Support=(yz,[''])
vs.MapMode='FlatFace'
P=[A,B,C,D]
for k in range(4):
    a,b=P[k],P[(k+1)%4]; vs.addGeometry(Part.LineSegment(V(a[0],a[1],0),V(b[0],b[1],0)))
for k in range(4): vs.addConstraint(Sketcher.Constraint('Coincident',k,2,(k+1)%4,1))
pad=db.newObject('PartDesign::Pad','Vane'); pad.Profile=vs; pad.Length=7.2; vs.Visibility=False; d4.recompute()
if pad.Shape.BoundBox.XMin<-0.1: pad.Reversed=True; d4.recompute()
xax=[f for f in db.Origin.OriginFeatures if f.Role=='X_Axis'][0]
pp=db.newObject('PartDesign::PolarPattern','Vanes_x13'); pp.Originals=[pad]; pp.Axis=(xax,['']); pp.Angle=360; pp.Occurrences=13; db.Tip=pp; d4.recompute()
def arcpts(cx,cy,R,a0,a1,n=64):
    return [(cx+R*math.cos(math.radians(a0+(a1-a0)*k/n)),cy+R*math.sin(math.radians(a0+(a1-a0)*k/n))) for k in range(n+1)]
# R6 front-outer corner of vane tips (diffuser sheet R6), centre (x6, r47.5)
r6=[(-1,47.5)]+arcpts(6,47.5,6,180,90)+[(6,60),(-1,60)]
gs=profile_sketch(db,'VaneTipR6Profile',r6)
gr=db.newObject('PartDesign::Groove','VaneTip_R6'); gr.Profile=gs; gr.ReferenceAxis=(gs,['H_Axis']); gr.Angle=360; gs.Visibility=False; db.Tip=gr; d4.recompute()
# holes
def hp(name,x0,L,rad_y,rad_z,dia,n):
    c=db.newObject('PartDesign::SubtractiveCylinder',name); c.Radius=dia/2; c.Height=L
    c.Placement=App.Placement(V(x0,rad_y,rad_z),App.Rotation(V(0,1,0),90)); d4.recompute()
    p=db.newObject('PartDesign::PolarPattern',name+'_x%d'%n); p.Originals=[c]; p.Axis=(xax,['']); p.Angle=360; p.Occurrences=n; c.Visibility=False; db.Tip=p; d4.recompute()
hp('Hole_PCD34_D3_2',6,7,17,0,3.2,6)
hp('Hole_PCD60_D3',6,7,0,30,3.0,3)
rr=46.5
for _ in range(30):
    sm=s_at(rr); wm=t0+sm*math.tan(wedge); hy,hz=r0+sm*dx+nx*wm/2, sm*dy+ny*wm/2
    rr+=46.5-math.hypot(hy,hz)
vane_ang=math.atan2(hz,hy)
SUP_VANES=[1,5,9]; R_SUP=47.2; STEP13=2*math.pi/13
rr2=R_SUP
for _ in range(30):
    sm2=s_at(rr2); wm2=t0+sm2*math.tan(wedge); sy,sz=r0+sm2*dx+nx*wm2/2, sm2*dy+ny*wm2/2
    rr2+=R_SUP-math.hypot(sy,sz)
sup_ang0=math.atan2(sz,sy)
def hole1(doc,body,name,x0,L,ang,rad,dia):
    c=body.newObject('PartDesign::SubtractiveCylinder',name); c.Radius=dia/2; c.Height=L
    c.Placement=App.Placement(V(x0,rad*math.cos(ang),rad*math.sin(ang)),App.Rotation(V(0,1,0),90)); body.Tip=c; doc.recompute(); return c
for k in range(13):
    if k in SUP_VANES: hole1(d4,db,'SupplyLine_D3_2_vane%d'%k,-0.5,8.5,sup_ang0+k*STEP13,R_SUP,3.2)
    else: hole1(d4,db,'VaneScrew_D2_5_vane%d'%k,-0.5,8.5,vane_ang+k*STEP13,46.5,2.5)
ds=save(d4,db,'GR180_Diffuser')
print('diffuser vane screw PCD %.2f'%(2*math.hypot(hy,hz)))
for x,nm in ((3.5,'vanes'),(9,'plate'),(12,'rim')):
    c=ds.common(Part.makeCylinder(80,0.01,V(x,0,0),V(1,0,0))); bb=c.BoundBox; print('diffuser x',x,nm,'max D %.2f'%(2*max(abs(bb.YMin),bb.YMax,abs(bb.ZMin),bb.ZMax)))

def subcyl_pattern(doc,body,name,x0,L,ang,pcd,dia,n):
    c=body.newObject('PartDesign::SubtractiveCylinder',name); c.Radius=dia/2; c.Height=L
    c.Placement=App.Placement(V(x0,pcd/2*math.cos(ang),pcd/2*math.sin(ang)),App.Rotation(V(0,1,0),90)); body.Tip=c; doc.recompute()
    xa=[f for f in body.Origin.OriginFeatures if f.Role=='X_Axis'][0]
    p=body.newObject('PartDesign::PolarPattern',name+'_x%d'%n); p.Originals=[c]; p.Axis=(xa,['']); p.Angle=360; p.Occurrences=n
    c.Visibility=False; body.Tip=p; doc.recompute(); return p
# ---- Intake (aluminium). local x=0 = bellmouth front, flange rear face x=36.59, rear spigot face x=39.18
d5=App.newDocument('GR180_Intake'); ib=d5.addObject('PartDesign::Body','Intake'); ib.Label='Intake / compressor shroud (aluminium)'
L_in=39.18; xf0=L_in-4.59; xf1=L_in-2.59; xt=9.17+17.56
rin=56.2/2; rout=59.5/2; Rs=12.8
inner=arcpts(10,38.15,10,180,270)            # bellmouth flow surface R10: (0,38.15)->(10,28.15)
end_dr=Rs-math.sqrt(Rs*Rs-(L_in-xt)**2)
shroud=[(xt+Rs*math.sin(math.radians(a)), rin+Rs-Rs*math.cos(math.radians(a))) for a in [k*math.degrees(math.asin((L_in-xt)/Rs))/16 for k in range(17)]]
outer=arcpts(10,38.15,38.15-rout,270,180)    # bellmouth outer R8.35: (10,29.75)->(1.65,38.15)
prof=inner+[(xt,rin)]+shroud[1:]+[(L_in,38.0),(xf1,38.0),(xf1,44.0),(xf0,44.0),(xf0,38.0),(xt,rout)]+outer
isk=profile_sketch(ib,'IntakeProfile',prof); revolve(ib,isk,'IntakeRevolve'); ib.Tip=ib.Group[-1]; d5.recompute()
subcyl_pattern(d5,ib,'FlangeHole_D3_PCD82',xf0-0.5,3,math.pi/2,82,3.0,6)
ins=save(d5,ib,'GR180_Intake')
print('intake shroud exit r %.2f (Ø%.2f), throat ID %.2f'%(rin+end_dr,2*(rin+end_dr),2*rin))
# ---- Intake outer (aluminium). local x=0 front, wall x=6..7.93, lip to x=12.48
d6=App.newDocument('GR180_Intake_outer'); ob=d6.addObject('PartDesign::Body','IntakeOuter'); ob.Label='Intake outer (aluminium)'
lip=arcpts(13.93,47.5,6,180,math.degrees(math.atan2(math.sqrt(36-1.45**2),-1.45)))   # R6 hugging diffuser vane-tip R6: (7.93,47.5)->(12.48,53.32)
oprof=[(0,51),(0,53),(6,53),(6,53.5),(12.48,53.5)]+lip[::-1]+[(7.93,38),(6,38),(6,51)]
# lip list reversed goes (12.48,53.32)->(7.93,47.5)
osk=profile_sketch(ob,'IntakeOuterProfile',oprof); revolve(ob,osk,'IntakeOuterRevolve'); ob.Tip=ob.Group[-1]; d6.recompute()
subcyl_pattern(d6,ob,'M3_tap_D2_5_PCD82',5.5,3,math.pi/2,82,2.5,6)
for k in range(13):
    if k in SUP_VANES:
        hole1(d6,ob,'SupplyLine_D3_2_v%d'%k,5.5,3,sup_ang0+k*STEP13,R_SUP,3.2)
        hole1(d6,ob,'Oring_recess_D6_2x1_5_v%d'%k,5.5,2.0,sup_ang0+k*STEP13,R_SUP,6.2)
    else:
        hole1(d6,ob,'VaneScrew_D2_6_v%d'%k,5.5,3,vane_ang+k*STEP13,46.5,2.6)
        hole1(d6,ob,'VaneScrew_cbore_D4_5_v%d'%k,5.5,1.5,vane_ang+k*STEP13,46.5,4.5)
ous=save(d6,ob,'GR180_Intake_outer')

# ---- Combustion chamber (SS316 sheet t=0.5), modelled directly in tunnel/assembly coordinates (x=0 tunnel front face)
d7=App.newDocument('GR180_Combustion_chamber'); TS=0.5
XCC=21.6                                  # CC front (from assembly drawing scale)
def radial_holes(doc,body,name,x,ang_deg,r_mid,dia,n):
    c=body.newObject('PartDesign::SubtractiveCylinder',name); c.Radius=dia/2; c.Height=4
    a=math.radians(ang_deg); dvec=V(0,math.cos(a),math.sin(a))
    c.Placement=App.Placement(V(x,0,0)+dvec*(r_mid-2),App.Rotation(V(0,0,1),dvec)); body.Tip=c; doc.recompute()
    xa=[f for f in body.Origin.OriginFeatures if f.Role=='X_Axis'][0]
    p=body.newObject('PartDesign::PolarPattern',name+'_x%d'%n); p.Originals=[c]; p.Axis=(xa,['']); p.Angle=360; p.Occurrences=n
    c.Visibility=False; body.Tip=p; doc.recompute(); return p
def liner(name,label,circ,L,x0):
    b=d7.addObject('PartDesign::Body',name); b.Label=label
    rm=circ/(2*math.pi); ri,ro=rm-TS/2,rm+TS/2
    sk=profile_sketch(b,name+'Profile',[(x0,ri),(x0,ro),(x0+L,ro),(x0+L,ri)]); revolve(b,sk,name+'Revolve'); b.Tip=b.Group[-1]; d7.recompute()
    return b,rm
# 8.1 CC inner: flat 131 x 77 rolled -> mean Ø41.70; 12 hole columns, pitch 131/12, first column 5.5 from seam
cb,rmi=liner('CC_Inner','CC inner liner 8.1 (SS316 t0.5, 131x77 rolled)',131.0,77.0,XCC)
pi_=131.0/12; th=lambda u,circ: u/circ*360.0
a0=th(5.5,131.0); ah=th(5.5+pi_/2,131.0)
for nm,y,dia,ang in [('R1_D2',6.0,2.0,a0),('R1_D2_5',6.0,2.5,ah),('R2_D2_5',15.15,2.5,a0),('R3_D3',25.2,3.0,a0),('R4_D3',35.3,3.0,a0),('R5_D3',45.4,3.0,a0),('R6_D5_5',55.5,5.5,a0)]:
    radial_holes(d7,cb,'I_'+nm,XCC+y,ang,rmi,dia,12)
# 8.? CC outer: flat 300 x 75 (two taped strips) rolled -> mean Ø95.49; 12 groups, pitch 25, first column 12.6 from edge
ob2,rmo=liner('CC_Outer','CC outer liner (SS316 t0.5, 300x75 rolled)',300.0,75.0,XCC)
c0=12.6
for nm,y,dia,du in [('R1a_D2',7.07,2.0,6.25),('R1b_D2_5',7.07,2.5,12.5),('R1c_D2',7.07,2.0,18.75),('R2_D3_5',15.08,3.5,0),('R3_D3_2',25.13,3.2,0),
                    ('R4_D3_5',35.18,3.5,0),('R5_D4',45.23,4.0,0),('R6a_D5_5',55.4,5.5,-4.75),('R6b_D5_5',55.4,5.5,4.75),('R7a_D2',64.4,2.0,0),('R7b_D2',64.4,2.0,12.5)]:
    radial_holes(d7,ob2,'O_'+nm,XCC+y,th(c0+du,300.0),rmo,dia,12)
# 8.2/8.3 front cap: annular end plate with short lips (inner lip inside inner liner, outer lip outside outer liner)
fb=d7.addObject('PartDesign::Body','CC_FrontCap'); fb.Label='CC front cap 8.2/8.3 (SS t0.5, dims from assembly scale)'
ri_in=rmi-TS/2; ro_out=rmo+TS/2; Llip=4.0
fp=[(XCC-TS,ri_in-TS),(XCC-TS,ro_out+TS),(XCC+Llip,ro_out+TS),(XCC+Llip,ro_out),(XCC,ro_out),(XCC,ri_in),(XCC+Llip,ri_in),(XCC+Llip,ri_in-TS)]
fsk=profile_sketch(fb,'FrontCapProfile',fp); revolve(fb,fsk,'FrontCapRevolve'); fb.Tip=fb.Group[-1]; d7.recompute()
NV=12; rv=42.1; VAP_A0=math.pi/12
c_=fb.newObject('PartDesign::SubtractiveCylinder','NeedleHole_D1_6'); c_.Radius=0.8; c_.Height=2
c_.Placement=App.Placement(V(XCC-1.5,rv*math.cos(VAP_A0),rv*math.sin(VAP_A0)),App.Rotation(V(0,1,0),90)); fb.Tip=c_; d7.recompute()
pn=fb.newObject('PartDesign::PolarPattern','NeedleHoles_x12'); pn.Originals=[c_]; pn.Axis=([f for f in fb.Origin.OriginFeatures if f.Role=='X_Axis'][0],['']); pn.Angle=360; pn.Occurrences=12; c_.Visibility=False; fb.Tip=pn; d7.recompute()
# 8.4 rear outer transition: from outer liner end down to NGV outer shroud (Ø72.7..75.9) -> sleeve Ø73.8 OD
rb=d7.addObject('PartDesign::Body','CC_RearCone'); rb.Label='CC rear transition 8.4 (SS t0.5, dims from assembly scale)'
xe=XCC+75.0; r_ngv=38.5   # sleeve ID 77.0 over NGV outer shroud OD 75.9
rp=[(xe-3,rmo+TS/2),(xe,rmo+TS/2),(xe+4,r_ngv),(103.3,r_ngv),(103.3,r_ngv-TS),(xe+4-0.4,r_ngv-TS),(xe-0.3,rmo-TS/2+0.0001+TS),(xe-3,rmo+TS/2+0.0001)]
rp=[(xe-3,rmo+TS/2),(xe-3,rmo+TS/2+TS),(xe+0.5,rmo+TS/2+TS),(xe+4.5,r_ngv),(103.3,r_ngv),(103.3,r_ngv-TS),(xe+4.2,r_ngv-TS),(xe+0.2,rmo+TS/2)]
rsk=profile_sketch(rb,'RearConeProfile',rp); revolve(rb,rsk,'RearConeRevolve'); rb.Tip=rb.Group[-1]; d7.recompute()
# 8.5 vaporiser sticks: 12 x Ø6 x 0.3 at r=42.1 (GR180 photo shows 12 straight sticks on the rear ring), flared open front, closed rounded rear
dv=6.0; xv0,xv1=32.4,96.0
vsh=[]
for k in range(NV):
    a=VAP_A0+2*math.pi*k/NV; cy,cz=rv*math.cos(a),rv*math.sin(a); ax_=V(1,0,0)
    outer=Part.makeCylinder(dv/2,xv1-xv0-dv/2-2,V(xv0+2,cy,cz),ax_).fuse(Part.makeSphere(dv/2,V(xv1-dv/2,cy,cz))).fuse(Part.makeCone(3.75,dv/2,2,V(xv0,cy,cz),ax_))
    inner=Part.makeCylinder(dv/2-0.3,xv1-xv0-dv/2-2+0.01,V(xv0+2,cy,cz),ax_).fuse(Part.makeSphere(dv/2-0.3,V(xv1-dv/2,cy,cz))).fuse(Part.makeCone(3.45,dv/2-0.3,2.01,V(xv0-0.005,cy,cz),ax_))
    vsh.append(outer.cut(inner))
vf=d7.addObject('Part::Feature','CC_Vaporisers_shape'); vf.Shape=Part.makeCompound(vsh); vf.Label='CC vaporiser sticks 8.5 (12x Ø6x0.3, flared)'
cc_parts={'CC_Inner':cb.Shape,'CC_Outer':ob2.Shape,'CC_FrontCap':fb.Shape,'CC_RearCone':rb.Shape,'CC_Vaporisers':vf.Shape}
for k,v in cc_parts.items():
    bb=v.BoundBox; print(k,'valid',v.isValid(),'x %.2f..%.2f D %.2f'%(bb.XMin,bb.XMax,bb.YLength))
    v.exportStep(os.path.join(OUT,'GR180_'+k+'.step')); m=Mesh.Mesh(); m.addFacets(v.tessellate(0.05)); m.write(os.path.join(OUT,'GR180_'+k+'.stl'))
Part.makeCompound(list(cc_parts.values())).exportStep(os.path.join(OUT,'GR180_Combustion_chamber.step'))
def count_radial(shape,x,label):
    c=shape.common(Part.makeBox(0.02,200,200,V(x,-100,-100))); print(label,'cut faces',len(c.Faces))

# ======== v6 additions (all in assembly coordinates, x=0 tunnel front face) ========
def save_part(fname,label,shape):
    dd=App.newDocument(fname); o_=dd.addObject('Part::Feature',fname.replace('GR180_','')); o_.Label=label; o_.Shape=shape
    dd.recompute(); dd.saveAs(os.path.join(OUT,fname+'.FCStd')); shape.exportStep(os.path.join(OUT,fname+'.step'))
    m=Mesh.Mesh(); m.addFacets(shape.tessellate(0.05)); m.write(os.path.join(OUT,fname+'.stl'))
    bb=shape.BoundBox; print(fname,'valid',shape.isValid(),'x %.2f..%.2f D %.2f'%(bb.XMin,bb.XMax,bb.YLength)); return shape
def P(x,r,a): return V(x,r*math.cos(a),r*math.sin(a))
def tube_path(pts,ro,ri=None):
    sh=None
    for p0,p1 in zip(pts[:-1],pts[1:]):
        d_=p1.sub(p0); c=Part.makeCylinder(ro,d_.Length,p0,d_)
        sh=c if sh is None else sh.fuse(c)
    for p in pts[1:-1]: sh=sh.fuse(Part.makeSphere(ro,p))
    if ri:
        hole=None
        for p0,p1 in zip(pts[:-1],pts[1:]):
            d_=p1.sub(p0); e_=d_.normalize()*0.01; c=Part.makeCylinder(ri,d_.Length+0.02,p0.sub(e_),d_)
            hole=c if hole is None else hole.fuse(c)
        for p in pts[1:-1]: hole=hole.fuse(Part.makeSphere(ri,p))
        sh=sh.cut(hole)
    return sh.removeSplitter()
XD=XF-(7+T); XO=XD-7.93; XI=XO+6-xf1        # diffuser, intake-outer, intake offsets (same as assembly)
sup=[sup_ang0+k*STEP13 for k in SUP_VANES]   # angles of the 3 supply lines
A_FUEL,A_OIL,A_GAS=sup
# --- supply lines (3x Ø3x0.5 brass) + O-rings 6x1.5 + washers Ø5.8x0.65 + push-in fittings (placeholder)
xw=XO+6                                      # intake-outer wall front face
fuel=tube_path([P(-30,R_SUP,A_FUEL),P(8,R_SUP,A_FUEL),P(14,rv+1.6,A_FUEL)],1.5,1.0)
# fuel manifold ring Ø3 brass at x=15, r=42.1 with 12 needles Ø1 into the vaporiser mouths
man=Part.makeTorus(rv,1.5,V(15,0,0),V(1,0,0)).cut(Part.makeTorus(rv,1.0,V(15,0,0),V(1,0,0)))
needles=[Part.makeCylinder(0.5,34-15,P(15,rv,VAP_A0+2*math.pi*k/NV),V(1,0,0)) for k in range(NV)]
fuel_sys=Part.makeCompound([fuel,man]+needles)
oil=tube_path([P(-30,R_SUP,A_OIL),P(9,R_SUP,A_OIL),P(18,11.6,A_OIL),P(18,9.6,A_OIL)],1.5,1.0)
gas=tube_path([P(-30,R_SUP,A_GAS),P(18,R_SUP,A_GAS)],1.5,1.0)
seals=[]
for a in sup:
    c=P(xw,R_SUP,a)
    oring=Part.makeTorus(2.25,0.75,P(xw+0.75,R_SUP,a),V(1,0,0))
    washer=Part.makeCylinder(2.9,0.65,P(xw-0.65,R_SUP,a),V(1,0,0)).cut(Part.makeCylinder(1.55,0.65,P(xw-0.65,R_SUP,a),V(1,0,0)))
    fit=Part.makeCylinder(3.5,8,P(-30,R_SUP,a),V(1,0,0)).cut(Part.makeCylinder(1.5,8,P(-30,R_SUP,a),V(1,0,0)))
    seals+= [oring,washer,fit]
supply=Part.makeCompound([fuel_sys,oil,gas])
save_part('GR180_Supply_lines','Supply lines: fuel (with manifold+12 needles), oil (to front bearing), gas - Ø3x0.5 brass',supply)
save_part('GR180_Supply_seals','O-rings 6x1.5, washers 5.8x3.1x0.65, push-in fittings 3/4mm (placeholder)',Part.makeCompound(seals))
# oil entry hole Ø3.2 in shaft tunnel wall at x=18 (feature added to the tunnel body, re-saved)
oh=tb.newObject('PartDesign::SubtractiveCylinder','OilFeed_D3_2'); oh.Radius=1.6; oh.Height=6
oh.Placement=App.Placement(P(18,7.5,A_OIL),App.Rotation(V(0,0,1),V(0,math.cos(A_OIL),math.sin(A_OIL)))); tb.Tip=oh; d2.recompute()
ts=save(d2,tb,'GR180_Shaft_tunnel')
# --- NGV placeholder (JetMax DA70 / GR180 sheet): hub disc Ø26 bore, inner shroud 42.5/44.5, outer shroud 72.7/75.9, width 24, 17 flat vanes
XN=103.3-8.5
ngv=Part.makeCylinder(37.95,24,V(XN,0,0),V(1,0,0)).cut(Part.makeCylinder(36.35,24,V(XN,0,0),V(1,0,0)))
ngv=ngv.fuse(Part.makeCylinder(22.25,14.5,V(XN,0,0),V(1,0,0)).cut(Part.makeCylinder(21.25,14.5,V(XN,0,0),V(1,0,0))))
ngv=ngv.fuse(Part.makeCylinder(21.25,1.5,V(XN+8.5,0,0),V(1,0,0)).cut(Part.makeCylinder(13.0,1.5,V(XN+8.5,0,0),V(1,0,0))))
for k in range(17):
    v_=Part.makeBox(12,36.6-22.0,1.2,V(XN+1,22.0,-0.6)); v_.rotate(V(XN+7,0,0),V(0,1,0),0)
    v_.rotate(V(XN+7,29,0),V(0,1,0),-26); v_.rotate(V(0,0,0),V(1,0,0),360.0*k/17)
    ngv=ngv.fuse(v_.common(Part.makeCylinder(36.5,24,V(XN,0,0),V(1,0,0)).cut(Part.makeCylinder(22.1,24,V(XN,0,0),V(1,0,0)))))
for k in range(6):
    a=math.radians(90+60*k); ngv=ngv.cut(Part.makeCylinder(1.6,3,P(XN+8,16,a),V(1,0,0)))
ngv=ngv.removeSplitter()
save_part('GR180_NGV_placeholder','PLACEHOLDER NGV DA70 (Inconel) - simplified vanes',ngv)
# --- Turbine wheel placeholder Ø70.3, bore Ø8, hub Ø44.2, 23 blades
XT=109.5
tw=Part.makeCylinder(22.1,6.5,V(XT,0,0),V(1,0,0)).fuse(Part.makeCylinder(6,XT-107.3,V(107.3,0,0),V(1,0,0)))
for k in range(23):
    b_=Part.makeBox(6.5,35.15-21.5,1.0,V(XT,21.5,-0.5)); b_.rotate(V(XT+3.25,28,0),V(0,1,0),30); b_.rotate(V(0,0,0),V(1,0,0),360.0*k/23)
    tw=tw.fuse(b_.common(Part.makeCylinder(35.15,6.5,V(XT,0,0),V(1,0,0))))
tw=tw.cut(Part.makeCylinder(4,20,V(100,0,0),V(1,0,0))).removeSplitter()
nut=Part.makeCylinder(5,5,V(116,0,0),V(1,0,0)).cut(Part.makeCylinder(3,5,V(116,0,0),V(1,0,0)))
save_part('GR180_Turbine_placeholder','PLACEHOLDER turbine wheel DA 70.3 + M6 LH nut',Part.makeCompound([tw,nut]))
# --- Exhaust (GR130 method scaled x75.9/68.5): SS 0.5 sheet
k_=75.9/68.5; XE=112.8
L_str=28*k_; L_tot=59*k_; r_out=50*k_/2
pr=[(XE,38.0),(XE,38.5),(XE+6+L_str,38.5),(XE+L_tot,r_out+0.5),(XE+L_tot,r_out),(XE+6+L_str,38.0)]
w=Part.makePolygon([V(x,r,0) for x,r in pr]+[V(pr[0][0],pr[0][1],0)])
exo=Part.Face(w).revolve(V(0,0,0),V(1,0,0),360)
XC=117.5; ca,cb_=38*k_,47*k_/2      # inner cone: base Ø52, length 42
def half_ellipse(a,b,n=40): return [V(XC+a*math.sin(t*math.pi/2/n),b*math.cos(t*math.pi/2/n),0) for t in range(n+1)]
po=half_ellipse(ca,cb_); pi2=half_ellipse(ca-0.5,cb_-0.5)
w2=Part.makePolygon(po+pi2[::-1]+[po[0]]); cone=Part.Face(w2).revolve(V(0,0,0),V(1,0,0),360)
base=Part.makeCylinder(cb_,0.5,V(XC,0,0),V(1,0,0)).cut(Part.makeCylinder(7,0.5,V(XC,0,0),V(1,0,0)))
xs=XC+12; rs=cb_*math.sqrt(1-(12/ca)**2)
struts=[Part.makeCylinder(1.5,38.25-rs+1.0,P(xs,rs-0.5,math.radians(90+120*k)),V(0,math.cos(math.radians(90+120*k)),math.sin(math.radians(90+120*k)))) for k in range(3)]
exh=exo.fuse([cone,base]+struts).removeSplitter()
save_part('GR180_Exhaust','Exhaust (SS 0.5) - GR130 method scaled to GR180; outlet start Ø%.1f'%(2*r_out),exh)
# --- Casing placeholder: CV470 canister Ø107 ID, t0.3, neck down onto exhaust rim area
cp=[(XO+6,53.5),(XO+6,53.8),(95,53.8),(108,39.3),(113,39.3),(113,39.0),(108,39.0),(95,53.5)]
w3=Part.makePolygon([V(x,r,0) for x,r in cp]+[V(cp[0][0],cp[0][1],0)])
casing=Part.Face(w3).revolve(V(0,0,0),V(1,0,0),360)
save_part('GR180_Casing_placeholder','PLACEHOLDER casing CV470 canister (ID107, t0.3)',casing)
# --- Starter (Startermotor300.pdf): Permax 280BB, plastic body, Bendix cup, 3 struts to intake lip
XS=-66.0; ax_=V(-1,0,0)
st=Part.makeCylinder(8.25,14,V(XS,0,0),ax_).cut(Part.makeCylinder(7.25,14,V(XS,0,0),ax_))            # cup Ø16.5/14.5 x14
st=st.fuse(Part.makeCone(8.25,12,6,V(XS-14,0,0),ax_)).fuse(Part.makeCylinder(12,15,V(XS-20,0,0),ax_))  # 44° flare + Ø24 x15 hub
body=Part.makeCylinder(12.2,32.7-12.2,V(XS-35,0,0),ax_).fuse(Part.makeSphere(12.2,V(XS-35-(32.7-12.2),0,0)).common(Part.makeBox(13,30,30,V(XS-35-(32.7-12.2)-13,-15,-15))))
spokes=[]
for k in range(3):
    a=math.radians(30+120*k); p0=P(XS-27,10,a); p1=P(XI-0.3,36.0,a)
    spokes.append(Part.makeCylinder(2,p1.sub(p0).Length,p0,p1.sub(p0)))
starter=Part.makeCompound([st.removeSplitter(),body]+spokes)
save_part('GR180_Starter','Starter: Permax 280BB in plastic body, Bendix cup, 3 Ø4 struts (Startermotor300.pdf)',starter)
# ---- Compressor wheel: Schwitzer 316954 turned to Ø74 ("GR180 Compressor.pdf"), modelled in ASSEMBLY coords (flow +x)
# integrated spacer Ø13 x2.5 (bore Ø8) rests on front 608 inner ring at x=0; back face x=-2.5; nose x=-38.4 (overall 38.4)
CW_R2=37.0; CW_BACK=-4.8; CW_NOSE=CW_BACK-33.0; CW_HUB_RIM=-7.68; CW_LE=CW_NOSE+5.6; CW_RN=17.9/2; CW_TIPCL=0.3
XS_T=((XF-(7+T))-7.93+6-xf1)+xt; RS_C=rin+Rs   # intake shroud arc centre (assembly x, r)
def cw_tip_r(x):          # blade tip = intake shroud offset inward by CW_TIPCL
    if x<=XS_T: return rin-CW_TIPCL
    return RS_C-math.sqrt((Rs+CW_TIPCL)**2-(x-XS_T)**2)
CW_TIPX=XS_T+math.sqrt((Rs+CW_TIPCL)**2-(RS_C-CW_R2)**2)   # where tip line reaches r37
def cw_hub(m):            # quarter ellipse, axial at nose -> radial at rim
    t=m*math.pi/2; return (CW_LE+(CW_HUB_RIM-CW_LE)*math.sin(t), CW_R2-(CW_R2-CW_RN)*math.cos(t))
def cw_tip(m): x=CW_LE+(CW_TIPX-CW_LE)*m; return (x,min(cw_tip_r(x),CW_R2))
hubp=[(CW_NOSE,3.5),(CW_NOSE,CW_RN)]+[cw_hub(k/40) for k in range(41)]+[(CW_BACK,CW_R2),(CW_BACK,21.9/2),(-2.5,21.9/2),(-2.5,6.5),(0.0,6.5),(0.0,4.0),(-2.5,4.0),(-2.5,3.5)]
hub=Part.Face(Part.makePolygon([V(x,r,0) for x,r in hubp]+[V(CW_NOSE,3.5,0)])).revolve(V(0,0,0),V(1,0,0),360)
def cw_theta(m): return 1.15*m-0.5*m*m        # wrap 37°, steep inducer, ~backswept exducer
def cw_blade(a0,m0,th_h,th_t):
    secs=[]
    for k in range(25):
        m=m0+(1-m0)*k/24; th=a0+cw_theta(m)
        (xh,rh),(xt_,rt)=cw_hub(m),cw_tip(m)
        rh2=rh-0.6*(1 if m<0.98 else 0)                          # sink into hub for a clean fuse
        if m>=0.98: xh=xh-0.0
        pts=[]
        for (x,r,t_) in [(xh,rh2,th_h),(xt_,rt,th_t)]:
            pts.append((x,r,t_))
        w=[P(pts[0][0],pts[0][1],th-pts[0][2]/2/pts[0][1]),P(pts[1][0],pts[1][1],th-pts[1][2]/2/pts[1][1]),
           P(pts[1][0],pts[1][1],th+pts[1][2]/2/pts[1][1]),P(pts[0][0],pts[0][1],th+pts[0][2]/2/pts[0][1])]
        secs.append(Part.makePolygon(w+[w[0]]))
    return Part.makeLoft(secs,True,False)
CW_NB=7   # 7 main + 7 splitters, counted on user photo (14 exducer tips)
blades=[cw_blade(2*math.pi*k/CW_NB,0.0,1.4,0.7) for k in range(CW_NB)]+[cw_blade(2*math.pi*k/CW_NB+math.pi/CW_NB,0.40,1.2,0.6) for k in range(CW_NB)]
cw=hub
for b_ in blades: cw=cw.fuse(b_)
cw=cw.common(Part.makeCylinder(CW_R2,60,V(-50,0,0),V(1,0,0)))   # OD turned to Ø74
cw=cw.cut(Part.makeCylinder(3.5,60,V(-50,0,0),V(1,0,0))).removeSplitter()
print('blade solids valid',[b_.isValid() for b_ in blades].count(True),'of',len(blades))
_ring=Part.makeCylinder(36.5,60,V(-50,0,0),V(1,0,0)).cut(Part.makeCylinder(35.5,60,V(-50,0,0),V(1,0,0)))
_sec=cw.common(_ring.cut(Part.makeCylinder(40,60,V(CW_HUB_RIM-0.3,0,0),V(1,0,0))))
_ang=sorted(math.degrees(math.atan2(sl.CenterOfMass.z,sl.CenterOfMass.y))%360 for sl in _sec.Solids)
print('blades at r36 (above hub):',len(_sec.Solids),'pitch',[round((_ang[(i+1)%len(_ang)]-_ang[i])%360,2) for i in range(len(_ang))])
print('compressor: valid',cw.isValid(),'vol %.0f mm3 mass(Al) %.0f g'%(cw.Volume,cw.Volume*2.7e-3),'tip exit x %.2f, b2 %.2f'%(CW_TIPX,CW_HUB_RIM-CW_TIPX))
save_part('GR180_Compressor','Compressor wheel Schwitzer 316954 turned to Ø74, 7+7 blades (GR180 Compressor.pdf)',cw)
# ---- assembly
d3=App.newDocument('GR180_Shaft_assembly')
a=d3.addObject('Part::Feature','ShaftTunnel'); a.Shape=ts
o=-51.0  # shaft front bearing shoulder (shaft x58) at tunnel x7 -> front 608 sits at tunnel x0-7
s1=d3.addObject('Part::Feature','Shaft'); s1.Shape=ss; s1.Placement=App.Placement(V(o,0,0),App.Rotation())
n1=d3.addObject('Part::Feature','NoseCone'); n1.Shape=ns
n1.Placement=App.Placement(V(o+12,0,0),App.Rotation(V(0,0,1),180))  # nut on front M6 LH thread, tip forward
def ring(nm,x,L,ro,ri,col):
    o_=d3.addObject('Part::Feature',nm); o_.Shape=Part.makeCylinder(ro,L,V(x,0,0),V(1,0,0)).cut(Part.makeCylinder(ri,L,V(x,0,0),V(1,0,0))); return o_
def bearing608(nm,x):
    # 8x22x7: outer ring 22/18.4, inner ring 12.1/8, 7 Si3N4 balls d3.969 on pitch Ø15.1
    sh=[Part.makeCylinder(11,7,V(x,0,0),V(1,0,0)).cut(Part.makeCylinder(9.2,7,V(x,0,0),V(1,0,0))),
        Part.makeCylinder(6.05,7,V(x,0,0),V(1,0,0)).cut(Part.makeCylinder(4,7,V(x,0,0),V(1,0,0)))]
    for k in range(7):
        a_=2*math.pi*k/7; sh.append(Part.makeSphere(3.969/2,V(x+3.5,7.55*math.cos(a_),7.55*math.sin(a_))))
    o_=d3.addObject('Part::Feature',nm); o_.Shape=Part.makeCompound(sh); return o_
bearing608('FrontBearing_608_hybrid_8x22x7',0.0)
bearing608('RearBearing_608_hybrid_8x22x7',100.3)
ring('Spacer_22x16x1_5',7.0,1.5,10.9,8.0,None)
# wave spring modelled as a wavy single-turn ring (3 waves), envelope 21.8/16.2, installed height 2.8 (x8.5-11.3)
import Part as _P
pts=[];N=180
for k in range(N+1):
    t_=2*math.pi*k/N; pts.append(V(8.5+1.4+0.9*math.cos(3*t_),10.4*math.cos(t_),10.4*math.sin(t_)))
path=_P.BSplineCurve(); path.interpolate(pts[:-1],PeriodicFlag=True)
prof=_P.Face(_P.Wire(_P.makePolygon([V(0,-1.35,-0.125),V(0,1.35,-0.125),V(0,1.35,0.125),V(0,-1.35,0.125),V(0,-1.35,-0.125)])))
pe=path.toShape()
try:
    sw=_P.Wire(pe).makePipeShell([_P.Wire(_P.makeCircle(0.5,pts[0],path.tangent(path.FirstParameter)[0]))],True,True)
    ws=sw
except Exception as e:
    print('wave pipe failed',e); ws=Part.makeCylinder(10.9,2.8,V(8.5,0,0),V(1,0,0)).cut(Part.makeCylinder(8.1,2.8,V(8.5,0,0),V(1,0,0)))
wo=d3.addObject('Part::Feature','WaveSpring_22x16_free3_0_inst2_8'); wo.Shape=ws
dfo=d3.addObject('Part::Feature','Diffuser'); dfo.Shape=ds; dfo.Placement=App.Placement(V(XF-(7+T),0,0),App.Rotation())
xd=XF-(7+T)              # diffuser vane front face in assembly
xo=xd-7.93              # intake-outer wall rear face on diffuser vane front face
iof=d3.addObject('Part::Feature','IntakeOuter'); iof.Shape=ous; iof.Placement=App.Placement(V(xo,0,0),App.Rotation())
xi=xo+6-xf1+0           # intake flange rear face (local xf1... front face xf0) -> on intake-outer wall front face
xi=xo+6-xf1
inf=d3.addObject('Part::Feature','Intake'); inf.Shape=ins; inf.Placement=App.Placement(V(xi,0,0),App.Rotation())
for k,v in cc_parts.items():
    o_=d3.addObject('Part::Feature',k); o_.Shape=v
for k,v in [('SupplyLines',supply),('SupplySeals',Part.makeCompound(seals)),('NGV_placeholder',ngv),('Turbine_placeholder',tw),('TurbineNut',nut),('Exhaust',exh),('Casing_placeholder',casing),('Starter',starter),('Compressor',cw)]:
    o_=d3.addObject('Part::Feature',k); o_.Shape=v
d3.recompute(); d3.saveAs(os.path.join(OUT,'GR180_Shaft_assembly.FCStd'))
Part.makeCompound([o_.Shape for o_ in d3.Objects]).exportStep(os.path.join(OUT,'GR180_Shaft_assembly.step'))
def gs_(o_): return o_.Shape
objs=[o_ for o_ in d3.Objects]
for k1 in range(len(objs)):
    for k2 in range(k1+1,len(objs)):
        v_=objs[k1].Shape.common(objs[k2].Shape).Volume
        if v_>1e-3: print('INTERFERENCE',objs[k1].Name,objs[k2].Name,round(v_,3))
print('pairwise interference check done')
print('interf shaft/tunnel',round(gs_(s1).common(gs_(a)).Volume,3),'diffuser/tunnel',round(gs_(dfo).common(gs_(a)).Volume,3),'diffuser/shaft',round(gs_(dfo).common(gs_(s1)).Volume,3))
for o_ in d3.Objects:
    bb=gs_(o_).BoundBox; print('asm',o_.Name,'x %.2f..%.2f'%(bb.XMin,bb.XMax),'D %.2f'%bb.YLength)
shr=ins.copy(); shr.Placement=App.Placement(V(xi,0,0),App.Rotation())
for nm_,sh_ in [('Intake',shr),('Diffuser',dfo.Shape),('Shaft',s1.Shape),('NoseCone',n1.Shape),('IntakeOuter',iof.Shape)]:
    print('clearance compressor-%s min %.3f mm'%(nm_,cw.distToShape(sh_)[0]))
print('DONE')
def count_holes(shape,x,rmin,rmax,label):
    c=shape.common(Part.makeCylinder(80,0.02,V(x,0,0),V(1,0,0)))
    n=0
    for e in c.Edges:
        if e.Curve.TypeId=='Part::GeomCircle' and e.Vertexes and abs(e.Vertexes[0].Point.x-x)<1e-3:
            cc=e.Curve.Center; rr=math.hypot(cc.y,cc.z)
            if rmin<rr<rmax and e.Curve.Radius<3: n+=1
    print(label,'holes',n)
count_holes(ts,3,15,18,'tunnel front PCD34'); count_holes(ts,101,14,18,'tunnel rear PCD32')
count_holes(ds,9,15,18,'diffuser PCD34'); count_holes(ds,9,28,32,'diffuser PCD60'); count_holes(ds,3.5,44,49,'diffuser vane PCD93')
c=ds.common(Part.makeCylinder(80,0.01,V(3.5,0,0),V(1,0,0))); print('diffuser vane max R %.2f'%max(math.hypot(v.Point.y,v.Point.z) for v in c.Vertexes))
