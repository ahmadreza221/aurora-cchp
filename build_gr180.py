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
pts=[(0,0),(0,3),(15,3),(15,3.5),(49,3.5),(49,4),(60.1,4),(60.1,re),(76,rm),(127,rm),(145,re),(145,4),(166,4),(166,3),(179.8,3),(179.8,0)]
sk=profile_sketch(b,'ShaftProfile',pts); rv=revolve(b,sk,'ShaftRevolve')
b.Label='Shaft (Pos2, silversteel) - threads cosmetic: front M6 LH x15, rear M6 LH x13.8 v11 (left-hand per GR130 practice)'
d.recompute(); ss=save(d,b,'GR180_Shaft')
# nose cone as separate body
nb=d.addObject('PartDesign::Body','NoseCone'); nb.Label='Nose cone nut (M6 LH, cosmetic thread)'
r0=17.9/2; rt=r0-24.1*math.tan(math.radians(15))
npts=[(0,5),(0,r0),(24.1,rt),(24.1,0),(15,0),(15,2.5),(2,2.5),(2,5)]
nsk=profile_sketch(nb,'NoseProfile',npts); revolve(nb,nsk,'NoseRevolve')
ch=nb.newObject('PartDesign::SubtractiveCylinder','CrossHole'); ch.Radius=1.0; ch.Height=20
ch.Placement=App.Placement(V(21.5,-10,0),App.Rotation(V(1,0,0),-90))
for _nm,_y in (('MagnetPocket_D2_1',6.5),('BalancePocket_D2_1',-6.5)):
    _c=nb.newObject('PartDesign::SubtractiveCylinder',_nm); _c.Radius=1.05; _c.Height=2.1
    _c.Placement=App.Placement(V(0,_y,0),App.Rotation(V(0,1,0),90)); nb.Tip=_c
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
c_=fb.newObject('PartDesign::SubtractiveCylinder','VapHole_D6_05'); c_.Radius=3.025; c_.Height=2
c_.Placement=App.Placement(V(XCC-1.5,rv*math.cos(VAP_A0),rv*math.sin(VAP_A0)),App.Rotation(V(0,1,0),90)); fb.Tip=c_; d7.recompute()
pn=fb.newObject('PartDesign::PolarPattern','NeedleHoles_x12'); pn.Originals=[c_]; pn.Axis=([f for f in fb.Origin.OriginFeatures if f.Role=='X_Axis'][0],['']); pn.Angle=360; pn.Occurrences=12; c_.Visibility=False; fb.Tip=pn; d7.recompute()
# gas/glow stub hole Ø3.2 at r=36 (angle set from supply layout below, computed early)
STEP13_=2*math.pi/13; A_GAS_=sup_ang0+9*STEP13_; R_GASC=36.0
cg=fb.newObject('PartDesign::SubtractiveCylinder','GasStubHole_D3_2'); cg.Radius=1.6; cg.Height=2
cg.Placement=App.Placement(V(XCC-1.5,R_GASC*math.cos(A_GAS_),R_GASC*math.sin(A_GAS_)),App.Rotation(V(0,1,0),90)); fb.Tip=cg; d7.recompute()
# 8.4 rear outer transition: from outer liner end down to NGV outer shroud (Ø72.7..75.9) -> sleeve Ø73.8 OD
rb=d7.addObject('PartDesign::Body','CC_RearCone'); rb.Label='CC rear transition 8.4 (SS t0.5, dims from assembly scale)'
xe=XCC+75.0; r_ngv=38.5   # sleeve ID 77.0 over NGV outer shroud OD 75.9
rp=[(xe-3,rmo+TS/2),(xe,rmo+TS/2),(xe+4,r_ngv),(103.3,r_ngv),(103.3,r_ngv-TS),(xe+4-0.4,r_ngv-TS),(xe-0.3,rmo-TS/2+0.0001+TS),(xe-3,rmo+TS/2+0.0001)]
rp=[(xe-3,rmo+TS/2),(xe-3,rmo+TS/2+TS),(xe+0.5,rmo+TS/2+TS),(xe+4.5,r_ngv),(103.3,r_ngv),(103.3,r_ngv-TS),(xe+4.2,r_ngv-TS),(xe+0.2,rmo+TS/2)]
rsk=profile_sketch(rb,'RearConeProfile',rp); revolve(rb,rsk,'RearConeRevolve'); rb.Tip=rb.Group[-1]; d7.recompute()
# 8.5 vaporiser sticks (photo 'Combustion chamber 5/6'): 12 straight SS316 Ø6x0.3, brazed/TIG-tacked through Ø6.05 holes in the front cap,
# mouth 1.0 proud of the cap front face with a small flare (Ø7), open rear end; length 66 (KJ66 practice 64, Ø6x0.3)
dv=6.0; xv0,xv1=XCC-TS-1.0,XCC-TS-1.0+66.0
vsh=[]
for k in range(NV):
    a=VAP_A0+2*math.pi*k/NV; cy,cz=rv*math.cos(a),rv*math.sin(a); ax_=V(1,0,0)
    outer=Part.makeCylinder(dv/2,xv1-xv0-1,V(xv0+1,cy,cz),ax_).fuse(Part.makeCone(3.5,dv/2,1,V(xv0,cy,cz),ax_))
    inner=Part.makeCylinder(dv/2-0.3,xv1-xv0+0.02,V(xv0-0.01,cy,cz),ax_).fuse(Part.makeCone(3.2,dv/2-0.3,1.0,V(xv0-0.001,cy,cz),ax_))
    vsh.append(outer.cut(inner).removeSplitter())
vf=d7.addObject('Part::Feature','CC_Vaporisers_shape'); vf.Shape=Part.makeCompound(vsh); vf.Label='CC vaporiser sticks 8.5 (12x Ø6x0.3 x66 straight, brazed through front cap, flared mouth)'
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
XM=15.0                                       # manifold plane (6.6 ahead of the cap face)
fuel=tube_path([P(XM,64.0,A_FUEL),P(XM,rv+1.0,A_FUEL)],4.0,3.0)   # v10 natural gas: Ø8x1 radial feed through casing (vane Ø3 lines too small)
# v10 natural-gas manifold ring Ø5x0.5 (was Ø3x0.5 brass (annealed, bent) at x=15, r=42.1; 12 hypodermic needles Ø0.8, 10 deep into each vaporiser mouth
man=Part.makeTorus(rv,2.5,V(XM,0,0),V(1,0,0)).cut(Part.makeTorus(rv,2.0,V(XM,0,0),V(1,0,0)))
XN_END=XCC-TS-1.0+10.0
needles=[Part.makeCylinder(0.75,XN_END-XM,P(XM,rv,VAP_A0+2*math.pi*k/NV),V(1,0,0)).cut(Part.makeCylinder(0.55,XN_END-XM,P(XM,rv,VAP_A0+2*math.pi*k/NV),V(1,0,0))) for k in range(NV)]
# 3 SS strip clips (0.5x2) spot-welded to the cap front face, each with a loop around the ring
clips=[]
for k in range(3):
    a=VAP_A0+math.pi/NV+k*2*math.pi/3
    loop=Part.makeTorus(3.0,0.35,P(XM,rv,a),V(-math.sin(a),math.cos(a),0)*0+V(0,-math.sin(a),math.cos(a)))
    strip=Part.makeBox(XCC-TS-(XM+2.0),2.0,0.5,V(XM+2.0,-1.0,-0.25))
    strip.rotate(V(0,0,0),V(1,0,0),0); strip.translate(V(0,0,0))
    strip.Placement=App.Placement(V(0,0,0),App.Rotation(V(1,0,0),math.degrees(a)))*App.Placement(V(0,rv,0),App.Rotation(V(0,0,1),90))*App.Placement(V(0,0,0),App.Rotation())
    strip=Part.makeBox(XCC-TS-(XM+2.9),0.5,2.0,V(XM+2.9,rv-0.25,-1.0)); strip.rotate(V(0,0,0),V(1,0,0),math.degrees(a))
    clips.append(loop.fuse(strip))
fuel_sys=Part.makeCompound([fuel,man]+needles+clips)
oil=tube_path([P(-30,R_SUP,A_OIL),P(9,R_SUP,A_OIL),P(18,11.6,A_OIL),P(18,9.6,A_OIL)],1.5,1.0)
# v10: separate start-gas line removed (natural gas is also the start gas); cap stub hole kept as igniter/glow-plug boss position
seals=[]
for a in sup:
    c=P(xw,R_SUP,a)
    oring=Part.makeTorus(2.25,0.75,P(xw+0.75,R_SUP,a),V(1,0,0))
    washer=Part.makeCylinder(2.9,0.65,P(xw-0.65,R_SUP,a),V(1,0,0)).cut(Part.makeCylinder(1.55,0.65,P(xw-0.65,R_SUP,a),V(1,0,0)))
    fit=Part.makeCylinder(3.5,8,P(-30,R_SUP,a),V(1,0,0)).cut(Part.makeCylinder(1.5,8,P(-30,R_SUP,a),V(1,0,0)))
    seals+= [oring,washer,fit]
supply=Part.makeCompound([fuel_sys,oil])
save_part('GR180_Supply_lines','Supply lines: fuel (with manifold+12 needles), oil (to front bearing), gas - Ø3x0.5 brass',supply)
save_part('GR180_Supply_seals','O-rings 6x1.5, washers 5.8x3.1x0.65, push-in fittings 3/4mm (placeholder)',Part.makeCompound(seals))
# oil entry hole Ø3.2 in shaft tunnel wall at x=18 (feature added to the tunnel body, re-saved)
ts=save(d2,tb,'GR180_Shaft_tunnel')
# front bearing damping O-ring (Engine complete section): groove in Ø22 bore, O-ring 1.5 cord at bearing mid-width (size assumed)
save_part('GR180_Shaft_tunnel','Shaft tunnel (Pos3) incl. front O-ring groove',ts)
fb_oring=Part.makeTorus(11.6,0.55,V(3.5,0,0),V(1,0,0))
# wheel-rim relief per diffuser sheet Ø74.4 / Ø76 (depth 0.5 assumed): keeps 0.5 back gap on the plate face inside Ø74.4
ds=ds.cut(Part.makeCylinder(38.0,0.5,V(7,0,0),V(1,0,0)).cut(Part.makeCylinder(37.2,0.5,V(7,0,0),V(1,0,0)))).removeSplitter()
save_part('GR180_Diffuser','Diffuser (Pos4) incl. Ø74.4/Ø76 rim relief',ds)
# --- blade/vane helper: thin cambered blade lofted between two radii (sections on cylinders), x axial
def cam_blade(x0,chord,r_list,ang_in,ang_out,thk,theta0,n=24):
    secs=[]
    for i,r in enumerate(r_list):
        bi,bo,t,c=ang_in[i],ang_out[i],thk[i],chord[i]
        pts=[];y=0.0;prev=None
        cl=[]
        for k in range(n+1):
            s=k/n; b=math.radians(bi+(bo-bi)*s); u=c*s
            if k>0: y+=math.tan(math.radians(bi+(bo-bi)*(s-0.5/n)))*c/n
            cl.append((u,y,b))
        top=[];bot=[]
        for (u,y,b) in cl:
            h=min(t/2/math.cos(b),1.5*t)*(0.5+0.5*math.sin(math.pi*min(max(u/c,0.0),1.0))**0.5)
            top.append((u,y+h)); bot.append((u,y-h))
        ring=top+bot[::-1]
        ct,st_=math.cos(theta0),math.sin(theta0)
        w=[V(x0+u,r*ct-yy*st_,r*st_+yy*ct) for (u,yy) in ring]   # planar section tangent at radius r
        secs.append(Part.makePolygon(w+[w[0]]))
    return Part.makeLoft(secs,True,False)
# --- NGV (GR180 Turbine + NGV.pdf; JetMax NGV70blank: 15 vanes). local u=0 front, XN = web front on tunnel rear face 103.3
XN=103.3-8.5
def rv(pts): return Part.Face(Part.makePolygon([V(XN+u,r,0) for u,r in pts]+[V(XN+pts[0][0],pts[0][1],0)])).revolve(V(0,0,0),V(1,0,0),360)
ch=1.67*math.tan(math.radians(26))
outer=rv([(0,35.25+ch),(0,36.35),(20,36.35),(20,37.95),(24,37.95),(24,35.25),(1.67,35.25)])    # 26° entry chamfer, shroud bore Ø70.5, Ø72.7, flange Ø75.9 x4.0
inner=rv([(0,21.25),(0,22.25),(14.5,22.25),(14.5,21.25)])                                          # inner shroud Ø44.5/42.5 x14.5
web=rv([(8.5,13.0),(8.5,21.3),(10.0,21.3),(10.0,13.0)])                                            # web 1.5 at 8.5, bore Ø26
NGV_N=15
_vr=lambda r: 10.67+(10.0-10.67)*(r-21.9)/(35.6-21.9)
_ann=Part.makeCylinder(36.65,30,V(XN,0,0),V(1,0,0)).cut(Part.makeCylinder(21.5,30,V(XN,0,0),V(1,0,0)))   # v11: vanes embedded 0.3 into both rings
vanes=[cam_blade(XN+2.5,[_vr(19.5),_vr(38.5)],[19.5,38.5],[0,0],[68,64],[1.25,0.95],2*math.pi*k/NGV_N).common(_ann) for k in range(NGV_N)]
ngv=outer.fuse([inner,web]+vanes)
for k in range(6):
    a=math.radians(90+60*k); ngv=ngv.cut(Part.makeCylinder(1.6,3,P(XN+8,17,a),V(1,0,0)))
ngv=ngv.removeSplitter()
print('NGV solids',len(ngv.Solids),'valid',ngv.isValid(),'shells',len(ngv.Shells))
save_part('GR180_NGV','NGV DA70 (Inconel): GR180 Turbine+NGV sheet, 15 vanes (JetMax NGV70 blank), exit angle assumed 68/64 deg',ngv)
# --- Turbine wheel (TW70blank + GR180 sheet): front face on rear 608 inner ring (x107.3)
XTB=107.3
tprof=[(0,4),(0,6.6),(6.0,6.6),(6.2,8.5),(7.6,12),(7.6,17),(6.2,19.8),(6.2,22.1),(13.4,22.1),(13.4,19.8),(10.6,17),(10.6,12),(14.51,8.5),(14.51,4)]
tw=Part.Face(Part.makePolygon([V(XTB+u,r,0) for u,r in tprof]+[V(XTB,4,0)])).revolve(V(0,0,0),V(1,0,0),360)
TW_N=23
tbl=[cam_blade(XTB+6.2,[7.2,6.7],[21.6,35.15],[35,40],[-58,-52],[2.0,0.8],2*math.pi*k/TW_N) for k in range(TW_N)]
tw=tw.fuse(tbl).common(Part.makeCylinder(35.15,30,V(100,0,0),V(1,0,0))).cut(Part.makeCylinder(4,30,V(100,0,0),V(1,0,0))).removeSplitter()
nut=Part.makeCylinder(5.0,6.0,V(XTB+14.51,0,0),V(1,0,0)).cut(Part.makeCylinder(3,6,V(XTB+14.51,0,0),V(1,0,0)))
save_part('GR180_Turbine','Turbine wheel DA 70.3 (Inconel), 23 blades (TW70blank), hub 14.51, blade 7.2->6.7',tw)
save_part('GR180_TurbineNut','M6 LH nut 10x6 (v11: 6 mm engagement, shaft 1 mm proud)',nut)
# --- Exhaust (GR130 method scaled x75.9/68.5): SS 0.5 sheet
k_=75.9/68.5; XE=112.8
L_str=28*k_; L_tot=59*k_; r_out=50*k_/2
pr=[(XE,38.0),(XE,38.5),(XE+6+L_str,38.5),(XE+L_tot,r_out+0.5),(XE+L_tot,r_out),(XE+6+L_str,38.0)]
w=Part.makePolygon([V(x,r,0) for x,r in pr]+[V(pr[0][0],pr[0][1],0)])
exo=Part.Face(w).revolve(V(0,0,0),V(1,0,0),360)
XC=122.5; ca,cb_=38*k_,47*k_/2      # inner cone: base Ø52, length 42
def half_ellipse(a,b,n=40): return [V(XC+a*math.sin(t*math.pi/2/n),b*math.cos(t*math.pi/2/n),0) for t in range(n+1)]
po=half_ellipse(ca,cb_); pi2=half_ellipse(ca-0.5,cb_-0.5)
w2=Part.makePolygon(po+pi2[::-1]+[po[0]]); cone=Part.Face(w2).revolve(V(0,0,0),V(1,0,0),360)
base=Part.makeCylinder(cb_,0.5,V(XC,0,0),V(1,0,0)).cut(Part.makeCylinder(7,0.5,V(XC,0,0),V(1,0,0)))
xs=XC+12; rs=cb_*math.sqrt(1-(12/ca)**2)
struts=[Part.makeCylinder(1.5,38.25-rs+1.0,P(xs,rs-0.5,math.radians(90+120*k)),V(0,math.cos(math.radians(90+120*k)),math.sin(math.radians(90+120*k)))) for k in range(3)]
exh=exo.fuse([cone,base]+struts).removeSplitter()
save_part('GR180_Exhaust','Exhaust (SS 0.5) - GR130 method scaled to GR180; outlet start Ø%.1f'%(2*r_out),exh)
# --- Casing (photo-based: Casing.jpg / Casing flange.jpg / Casing chrome.jpg): CV470 can ID107 t0.3, rounded rear shoulder onto exhaust sleeve
_cx0=XO+6; _cx1=96.0; _Rf=12.0
_arc=[(_cx1+_Rf*math.sin(math.radians(t)),53.5-_Rf+_Rf*math.cos(math.radians(t))) for t in range(0,91,6)]
_in=[(_cx0,53.5)]+_arc+[(_cx1+_Rf,39.0),(_cx1+_Rf+8,39.0)]
_out=[(x,r+0.3) for x,r in _in]
casing=Part.Face(Part.makePolygon([V(x,r,0) for x,r in _in+_out[::-1]]+[V(_cx0,53.5,0)])).revolve(V(0,0,0),V(1,0,0),360)
_rf=Part.makeCylinder(44,1.0,V(_cx1+_Rf+8-1.0,0,0),V(1,0,0)).cut(Part.makeCylinder(39.3,1.0,V(_cx1+_Rf+8-1.0,0,0),V(1,0,0)))   # rear flange ring (photo)
casing=casing.fuse(_rf)
for k in range(6):
    a_=math.radians(30+60*k); casing=casing.cut(Part.makeCylinder(1.6,3,P(XO+9.2,52.5,a_),V(0,math.cos(a_),math.sin(a_))))
casing=casing.cut(Part.makeCylinder(4.1,4,P(XM,51.5,A_FUEL),V(0,math.cos(A_FUEL),math.sin(A_FUEL))))   # v10 Ø8.2 gas inlet
casing=casing.removeSplitter()
save_part('GR180_Casing','Casing CV470 can (PHOTO-BASED, no drawing): ID107 t0.3, 6 radial M3 into intake outer, rear flange',casing)
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
# ======== v11: sensors, igniter, fastenings, oil jet, nose-cone clamp, rear stack (all assembly coords) ========
def D_(a): return V(0,math.cos(a),math.sin(a))
def hexprism(c,axis,af,h,bore=0.0):
    R=af/math.sqrt(3); pts=[V(R*math.cos(math.radians(60*k)),R*math.sin(math.radians(60*k)),0) for k in range(6)]
    s=Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,h))
    if bore>0: s=s.cut(Part.makeCylinder(bore/2,h,V(0,0,0),V(0,0,1)))
    s.Placement=App.Placement(c,App.Rotation(V(0,0,1),axis)); return Part.Shape(s).copy()
def rad_cyl(x,r0,r1,a,dia): return Part.makeCylinder(dia/2,r1-r0,P(x,r0,a),D_(a))
def tube_d(r,L,p,d): return Part.makeCylinder(r,L,p,d)
# --- 1) RPM: Allegro A1120EUA (SIP-3) Hall switch on Ø2.5 SS arm through an M3 boss in the intake wall (angle 90°),
#        diametral NdFeB Ø2x2 magnet in an axial pocket in the nose-cone rear face (r6.5), brass Ø2x2 balance slug opposite
A_RPM=math.radians(90); X_RPM=-39.3; xl_rpm=X_RPM-XI
ins=ins.fuse(Part.makeCylinder(3.5,4.1,V(xl_rpm,0,0)+D_(A_RPM)*29.4,D_(A_RPM)))
ins=ins.cut(Part.makeCylinder(1.25,8,V(xl_rpm,0,0)+D_(A_RPM)*27.0,D_(A_RPM)))          # M3 tap Ø2.5
# --- 2) starter mount ring on the bellmouth back (turned, r33..47, local x1.6..5.5) with 6x M3 (2 per strut foot)
ring_=Part.makeCylinder(47,4.5,V(1.6,0,0),V(1,0,0)).cut(Part.makeCylinder(33,4.5,V(1.6,0,0),V(1,0,0)))
ins=ins.fuse(ring_)
ST_ANG=[math.radians(30+120*k) for k in range(3)]; R_FT=43.0; T_OFF=5.0
for a in ST_ANG:
    for s_ in (-1,1):
        aa=a+s_*T_OFF/R_FT; ins=ins.cut(Part.makeCylinder(1.25,4.5,P(1.6,R_FT,aa),V(1,0,0)))
ins=ins.removeSplitter()
save_part('GR180_Intake','Intake + v11 starter mount ring (6x M3 tapped, r43) + RPM sensor M3 boss',ins)
x_tab=XI+1.6
spokes=[]; st_fast=[]
for a in ST_ANG:
    p0=P(XS-27,10,a); p1=P(x_tab-1.5,R_FT,a)
    spokes.append(Part.makeCylinder(2,p1.sub(p0).Length,p0,p1.sub(p0)))
    tab=Part.makeBox(1.5,8,16,V(x_tab-1.5,39,-8)); tab.rotate(V(0,0,0),V(1,0,0),math.degrees(a))
    for s_ in (-1,1):
        aa=a+s_*T_OFF/R_FT
        tab=tab.cut(Part.makeCylinder(1.6,1.5,P(x_tab-1.5,R_FT,aa),V(1,0,0)))
        st_fast.append(Part.makeCylinder(2.75,3,P(x_tab-4.5,R_FT,aa),V(1,0,0)).fuse(Part.makeCylinder(1.25,5.4,P(x_tab-1.5,R_FT,aa),V(1,0,0))))
    spokes.append(tab)
starter=Part.makeCompound([st.removeSplitter(),body]+spokes)
save_part('GR180_Starter','Starter: Permax 280BB, 3 Ø4 struts + v11 feet 16x8x1.5 with 2x M3x6 each into intake mount ring',starter)
rpm_arm=rad_cyl(X_RPM,11.2,36.0,A_RPM,2.5)
rpm_head=Part.makeBox(3.0,1.6,4.1,V(X_RPM-1.5,9.6,-2.05)); rpm_head.rotate(V(0,0,0),V(1,0,0),math.degrees(A_RPM)-90+90)
rpm_head=Part.makeBox(3.0,4.1,1.6,V(X_RPM-1.5,-2.05,9.6))      # A1120 'UA' body 4.1x3.0x1.6, face 0.9 off nose cone (angle 90° = +z)
rpm_sleeve=rad_cyl(X_RPM,11.2,14.0,A_RPM,5.0)
rpm_nut=rad_cyl(X_RPM,33.5,35.9,A_RPM,5.5).cut(rad_cyl(X_RPM,33.5,35.9,A_RPM,2.5))
rpm_sensor=Part.makeCompound([rpm_head,rpm_sleeve.cut(rad_cyl(X_RPM,11.2,14.0,A_RPM,2.5)),rpm_arm,rpm_nut])
XN0=-4.8-33.0
rpm_mag=Part.makeCylinder(1.0,2.0,V(XN0-2.1,-6.5,0),V(1,0,0))
bal_slug=Part.makeCylinder(1.0,2.0,V(XN0-2.1,6.5,0),V(1,0,0))
save_part('GR180_RPM_sensor','A1120EUA Hall switch on Ø2.5 SS arm, M3 boss in intake wall, gap 0.9 to nose cone',rpm_sensor)
# --- 3) front-bearing oil jet line from boss A_GAS, Ø0.5 jet drilled at 42° into tunnel bore aimed at front 608 / spacer
Qo=(12.5,14.8); Qi=(8.3,11.0); ux_,ur_=Qi[0]-Qo[0],Qi[1]-Qo[1]; Lq=math.hypot(ux_,ur_); ux_,ur_=ux_/Lq,ur_/Lq
def Q(t,a=A_GAS): return P(Qo[0]+ux_*t,Qo[1]+ur_*t,a)
jdir=Q(1).sub(Q(0))
save_part('GR180_Shaft_tunnel','Shaft tunnel incl. O-ring groove, oil feed Ø3.2 (rear), v11 front-bearing Ø0.5 oil jet + Ø3.1 tube seat',ts)
oil2=tube_path([P(-30,R_SUP,A_GAS),P(9,R_SUP,A_GAS),Q(-6.0),Q(1.2)],1.5,1.0)
# --- 4) plug the remaining boss (A_FUEL, old liquid-fuel entry): Ø3 pin + Ø5.8 head on the washer, O-ring seals
seals=[]
for a in sup:
    oring=Part.makeTorus(2.25,0.75,P(xw+0.75,R_SUP,a),V(1,0,0))
    washer=Part.makeCylinder(2.9,0.65,P(xw-0.65,R_SUP,a),V(1,0,0)).cut(Part.makeCylinder(1.55,0.65,P(xw-0.65,R_SUP,a),V(1,0,0)))
    seals+=[oring,washer]
    if a==A_FUEL: seals.append(Part.makeCylinder(2.9,1.5,P(xw-2.15,R_SUP,a),V(1,0,0)).fuse(Part.makeCylinder(1.5,7.15,P(xw-2.15,R_SUP,a),V(1,0,0))))
    else: seals.append(Part.makeCylinder(3.5,8,P(-30,R_SUP,a),V(1,0,0)).cut(Part.makeCylinder(1.5,8,P(-30,R_SUP,a),V(1,0,0))))
supply=Part.makeCompound([fuel_sys,oil,oil2])
save_part('GR180_Supply_lines','Supply: gas Ø8 feed+ring+12 needles, oil to rear (tunnel x18), v11 oil Ø3 to front-bearing jet',supply)
save_part('GR180_Supply_seals','O-rings 6x1.5, washers, 2 push-in fittings, v11 plug in the unused boss',Part.makeCompound(seals))
# --- 5) gas bulkhead fitting M12x1 (sleeve Ø12, bore 8) at the casing, inner locknut + outer hex + compression nut
casing=casing.cut(Part.makeCylinder(6.1,4,P(XM,51.5,A_FUEL),D_(A_FUEL)))
dF=D_(A_FUEL)
bulk=Part.makeCylinder(6,9.5,P(XM,48.8,A_FUEL),dF).fuse(hexprism(P(XM,48.8,A_FUEL),dF,14,4)).fuse(hexprism(P(XM,54.3,A_FUEL),dF,14,4))   # hex flats clear of the Ø107 can curvature
bulk=bulk.fuse(hexprism(P(XM,58.3,A_FUEL),dF,12,4.5)).cut(Part.makeCylinder(4.0,15,P(XM,48.8,A_FUEL),dF))
# --- 6) spark igniter 1/4-32 UNEF (RCEXL CM-6 type) in a weld boss on the casing, tip between 2 vaporisers
cand=[math.radians(30*k) for k in range(12)]
def adist(a,b): return abs((a-b+math.pi)%(2*math.pi)-math.pi)
A_IGN=max(cand,key=lambda c: min(adist(c,s_) for s_ in sup))
X_IGN=XCC+12.0
casing=casing.fuse(rad_cyl(X_IGN,53.6,60.6,A_IGN,10.0)).cut(rad_cyl(X_IGN,51.0,60.7,A_IGN,5.5))
# --- 7) casing rear flange Ø96 + 4x Ø3.2 at r44; exhaust gets a 3 mm SS ring with 4x M3 tapped
_x0=_cx1+_Rf+8-1.0
casing=casing.fuse(Part.makeCylinder(48,1.0,V(_x0,0,0),V(1,0,0)).cut(Part.makeCylinder(39.3,1.0,V(_x0,0,0),V(1,0,0))))
FL_ANG=[math.radians(45+90*k) for k in range(4)]
for a in FL_ANG: casing=casing.cut(Part.makeCylinder(1.6,1.0,P(_x0,44,a),V(1,0,0)))
casing=casing.removeSplitter()
save_part('GR180_Casing','Casing CV470 can + v11: flange Ø96 4xØ3.2, Ø12.2 bulkhead hole, 1/4-32 igniter boss',casing)
exh=exh.fuse(Part.makeCylinder(48,3,V(_x0+1,0,0),V(1,0,0)).cut(Part.makeCylinder(38.5,3,V(_x0+1,0,0),V(1,0,0))))
for a in FL_ANG: exh=exh.cut(Part.makeCylinder(1.25,3,P(_x0+1,44,a),V(1,0,0)))
fl_fast=[Part.makeCylinder(2.75,3,P(_x0-3,44,a),V(1,0,0)).fuse(Part.makeCylinder(1.25,4.5,P(_x0,44,a),V(1,0,0))) for a in FL_ANG]
# --- 8) EGT: type-K Ø1.5 sheathed probe, M4 compression fitting in a Ø8 weld boss on the exhaust duct, x=127, mid-way between struts
X_EGT=127.0; A_EGT=math.radians(30)
exh=exh.fuse(rad_cyl(X_EGT,38.2,42.5,A_EGT,8.0)).cut(rad_cyl(X_EGT,38.6,42.6,A_EGT,3.3)).cut(rad_cyl(X_EGT,37.5,39.6,A_EGT,1.6)).removeSplitter()
save_part('GR180_Exhaust','Exhaust (SS 0.5) + v11 rear ring 3mm 4xM3, EGT M4 weld boss at x127',exh)
dE=D_(A_EGT)
egt=rad_cyl(X_EGT,39.5,42.5,A_EGT,4.0).fuse(hexprism(P(X_EGT,42.5,A_EGT),dE,7,3)).cut(rad_cyl(X_EGT,39.4,45.6,A_EGT,1.5))
egt=Part.makeCompound([egt,rad_cyl(X_EGT,32.0,56.0,A_EGT,1.5),rad_cyl(X_EGT,56.0,60.0,A_EGT,3.0)])
save_part('GR180_EGT_probe','Type-K Ø1.5 sheathed EGT probe, tip r32 (mid gas path), M4 compression fitting',egt)
# igniter body & CC outer liner clearance hole Ø7
cc_parts['CC_Outer']=cc_parts['CC_Outer'].cut(rad_cyl(X_IGN,46.5,49.0,A_IGN,7.0))
save_part('GR180_CC_Outer','CC outer liner + v11 Ø7 igniter hole',cc_parts['CC_Outer'])
dI=D_(A_IGN)
ign=rad_cyl(X_IGN,48.2,58.6,A_IGN,6.35).fuse(hexprism(P(X_IGN,58.6,A_IGN),dI,8,4)).fuse(rad_cyl(X_IGN,62.6,70.6,A_IGN,4.0))
ign=ign.fuse(rad_cyl(X_IGN,45.0,48.2,A_IGN,4.0)).fuse(rad_cyl(X_IGN,43.5,45.0,A_IGN,1.0))
save_part('GR180_Igniter','Spark igniter 1/4-32 UNEF (RCEXL CM-6 class), gap tip at r44 between vaporisers, 12 mm behind cap',ign)
rear_spacer=Part.makeCylinder(6.05,6.3,V(94.0,0,0),V(1,0,0)).cut(Part.makeCylinder(4,6.3,V(94.0,0,0),V(1,0,0)))
fasteners=Part.makeCompound(st_fast+fl_fast)
print('v11 angles deg: igniter %.1f  fuel %.1f oil %.1f gas(oil2) %.1f'%tuple(math.degrees(x)%360 for x in (A_IGN,A_FUEL,A_OIL,A_GAS)))
# ======== v12: helical threads, oil-feed rings both bearings, front O-ring 22x1 FKM, real sensor/igniter hardware ========
AX=V(1,0,0)
def thread_rod(p0,dvec,L,d,p,lh=False,core=True,ext=0.0):
    """ISO 60deg (trapezoid-approx) helical thread solid from p0 along dvec, length L; ext>0 = tap tool (radial clearance)."""
    rM=d/2+ext; rm=d/2-0.6134*p+ext; s=0.05
    h=Part.makeHelix(p,L+2*p,rm-s,0,lh); h.translate(V(0,0,-p))
    wb=0.875*p; wt=0.125*p
    prof=Part.makePolygon([V(rm-s,0,-wb/2),V(rM,0,-wt/2),V(rM,0,wt/2),V(rm-s,0,wb/2),V(rm-s,0,-wb/2)]); prof.translate(V(0,0,-p))
    ps=Part.BRepOffsetAPI.MakePipeShell(Part.Wire(h)); ps.setBiNormalMode(V(0,0,1)); ps.add(prof); ps.build(); ps.makeSolid(); sw=ps.shape()
    if sw.ShapeType!='Solid' and sw.Solids: sw=sw.Solids[0]
    if sw.Volume<0: sw.reverse()
    sol=Part.makeCylinder(rm,L+2*p,V(0,0,-p),V(0,0,1)).fuse(sw) if core else sw
    sol=sol.common(Part.makeCylinder(rM+0.01,L,V(0,0,0),V(0,0,1)))
    sol=Part.Solid(sol.Solids[0]) if sol.Solids else sol
    if sol.Volume<0: sol.reverse()
    sol=sol.copy(); sol.rotate(V(0,0,0),V(0,0,1),37.0)   # keep helix start off cylinder seams (OCC boolean robustness)
    dv=V(dvec); dv.normalize(); sol.transformShape(App.Placement(p0,App.Rotation(V(0,0,1),dv)).toMatrix(),True); return sol
def prism_n(R,p0,dv,L,n=48):
    pts=[V(R*math.cos(2*math.pi*k/n),R*math.sin(2*math.pi*k/n),0) for k in range(n)]
    pr=Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,L)); w=V(dv); w.normalize()
    pr.transformShape(App.Placement(p0,App.Rotation(V(0,0,1),w)).toMatrix(),True); return pr
def tapcut(shape,p0,dvec,L,d,p,lh=False):     # for prismatic blanks (hex nuts): direct cut works
    s_=shape.cut(thread_rod(p0,dvec,L,d,p,lh,True,ext=0.06))
    if not s_.isValid(): s_.fix(1e-5,1e-5,1e-4)
    return s_
def tap(shape,p0,dvec,L,d,p,lh=False):
    """tapped hole in solid material over [p0,p0+L]: polygon-prism zone replaced by (zone - tap tool); avoids cylinder/helix-flank booleans"""
    tool=thread_rod(p0,dvec,L,d,p,lh,True,ext=0.06)
    rz=(d/2+0.09)/math.cos(math.pi/48); ri=(d/2-0.6134*p+0.06)*0.95
    outer=prism_n(rz,p0,dvec,L); keep=outer.cut(prism_n(ri,p0,dvec,L)).cut(tool)
    s_=shape.cut(outer).fuse(keep)
    if s_.Volume<0: s_.reverse()
    if not s_.isValid(): s_.fix(1e-5,1e-5,1e-4)
    return s_
THREADS=[]   # (location, size, hand, engagement, material)
def unit(v): w=V(v); w.normalize(); return w
# --- shaft & nose cone in assembly coords: M6x1 LH both ends (rotor turns CCW seen from the intake: backswept exducer wrap +theta)
sh_asm=ss.copy(); sh_asm.translate(V(-51,0,0))
sh_asm=sh_asm.cut(Part.makeCylinder(3.2,15,V(-51,0,0),AX)).fuse(thread_rod(V(-51,0,0),AX,15,6,1.0,True))
sh_asm=sh_asm.cut(Part.makeCylinder(3.2,13.8,V(115,0,0),AX)).fuse(thread_rod(V(115,0,0),AX,13.8,6,1.0,True))
save_part('GR180_Shaft','Shaft (assembly coords) M6x1 LH helical threads: front 15, rear 13.8',sh_asm)
no_asm=ns.copy(); no_asm.transformShape(App.Placement(V(-37.8,0,0),App.Rotation(V(0,0,1),180)).toMatrix())
no_asm=tap(no_asm,V(-51,0,0),AX,11,6,1.0,True)   # identical helix to the shaft rod (phase-exact)
save_part('GR180_NoseCone','Nose cone nut (assembly coords) M6x1 LH internal, 11.2 engaged',no_asm)
THREADS+= [('Shaft front / nose cone','M6x1','LH','11.2 mm (1.9d) in Al','starter torque tightens'),('Shaft rear / turbine nut','M6x1','LH','6.0 mm (1.0d) in steel','air drag on nut tightens')]
nut=hexprism(V(XTB+14.51,0,0),AX,10,6); nut=tapcut(nut,V(115,0,0),AX,13.8,6,1.0,True)
save_part('GR180_TurbineNut','Turbine nut M6x1 LH, 10 AF x 6, A4/Inconel, helical thread',nut)
# --- oil-feed rings (static, press-fit H7/p6 + Loctite 641) upstream of each 608, groove + 4x Ø0.45 jets at ball pitch r7.55
def oil_ring(x0,t,g0,g1):
    r=Part.makeCylinder(11,t,V(x0,0,0),AX).cut(Part.makeCylinder(6.5,t,V(x0,0,0),AX))
    r=r.cut(Part.makeCylinder(11,g1-g0,V(g0,0,0),AX).cut(Part.makeCylinder(10.2,g1-g0,V(g0,0,0),AX)))
    for k in range(4):
        a=math.radians(45+90*k); pa=P((g0+g1)/2,10.5,a); pb=P(x0+t,7.55,a); d_=pb.sub(pa); u_=unit(d_)
        r=r.cut(Part.makeCylinder(0.225,d_.Length+0.6,pa.sub(u_*0.3),u_))
    return r
oilring_f=oil_ring(0.1,2.0,0.6,1.6); oilring_r=oil_ring(97.3,3.0,97.3,98.8)
front_shim=Part.makeCylinder(6.05,2.1,V(0,0,0),AX).cut(Part.makeCylinder(4,2.1,V(0,0,0),AX))
# feed drillings Ø0.8 + Ø3.1 tube seats
A_F1=math.radians(285.0)
def drill(sh_,po,pi_,a,seat_back,seat_fwd):
    Po=P(po[0],po[1],a); Pi=P(pi_[0],pi_[1],a); u_=unit(Pi.sub(Po)); L_=Pi.sub(Po).Length
    sh_=sh_.cut(Part.makeCylinder(0.4,L_+0.6,Po.sub(u_*0.5),u_)).cut(Part.makeCylinder(1.55,seat_back+seat_fwd,Po.sub(u_*seat_back),u_))
    return sh_,Po,u_
ts,Pf,uf=drill(ts,(6.8,20.0),(1.1,10.5),A_F1,3.0,1.5)
ts,Pr,ur=drill(ts,(96.3,11.75),(98.2,10.35),A_OIL,3.0,1.0)
ts=ts.cut(Part.makeCylinder(11.8,1.4,V(4.9,0,0),AX).cut(Part.makeCylinder(11,1.4,V(4.9,0,0),AX)))     # O-ring gland 22x1: depth 0.8 (20% squeeze), width 1.4 (fill 70%)
for k in range(6): ts=tap(ts,P(XF,17,math.radians(60*k)),AX,8.5,3,0.5)
save_part('GR180_Shaft_tunnel','Shaft tunnel v12: O-ring gland 22x1, 2 oil drillings Ø0.8+seat, 6x M3 helical tapped',ts)
oil=tube_path([P(-30,R_SUP,A_OIL),P(9,R_SUP,A_OIL),P(18,16.5,A_OIL),Pr.sub(ur*8.0),Pr.add(ur*0.8)],1.5,1.0)
oil2=tube_path([P(-30,R_SUP,A_GAS),P(8.5,R_SUP,A_GAS),Pf.sub(uf*6.0),Pf.add(uf*1.2)],1.5,1.0)
supply=Part.makeCompound([fuel_sys,oil,oil2])
save_part('GR180_Supply_lines','Supply v12: gas Ø8 feed+ring+needles; oil Ø3x0.5 -> rear oil ring (A_OIL), -> front oil ring (A_GAS boss, entry 285°)',supply)
_e=Part.Ellipse(V(5.6+0.625,11.4,0),V(5.6,11.8,0),V(5.6,11.4,0))
fb_oring=Part.Face(Part.Wire(_e.toShape())).revolve(V(0,0,0),AX,360)
save_part('GR180_FrontBearing_Oring','O-ring 22x1.0 FKM 75 (installed, 20% squeeze, ellipse section)',fb_oring)
# --- M3 tapped holes: intake outer 6x, diffuser vane screws 10x, starter ring 6x (through, 4.5), exhaust ring 4x
for k in range(6): ous=tap(ous,P(6.0,41,math.pi/2+k*math.pi/3),AX,1.9,3,0.5)
save_part('GR180_Intake_outer','Intake outer v12: 6x M3 helical tapped (PCD82)',ous)
for k in range(13):
    if k not in SUP_VANES: ds=tap(ds,P(0.0,46.5,vane_ang+k*STEP13),AX,8.0,3,0.5)
save_part('GR180_Diffuser','Diffuser v12: 10x M3 helical tapped vane screw holes',ds)
for a in ST_ANG:
    for s_ in (-1,1): ins=tap(ins,P(1.6,R_FT,a+s_*T_OFF/R_FT),AX,4.5,3,0.5)
ins=tap(ins,V(xl_rpm,0,0)+D_(A_RPM)*28.5,D_(A_RPM),5.0,3,0.5)
save_part('GR180_Intake','Intake v12: starter ring 4.5 thick 6x M3 tapped, RPM boss M3 tapped',ins)
for a in FL_ANG: exh=tap(exh,P(_x0+1,44,a),AX,3.0,3,0.5)
# EGT boss M4x0.7
exh=tap(exh,P(X_EGT,38.6+0.7,A_EGT),D_(A_EGT),42.5-(38.6+0.7),4,0.7)
save_part('GR180_Exhaust','Exhaust v12: ring 4x M3 tapped, EGT boss M4x0.7 tapped',exh)
# --- screws: ISO 4762 M3 (heads on sheet: no counterbore possible, seat on plain face)
scr=[]
for a in ST_ANG:
    for s_ in (-1,1):
        aa=a+s_*T_OFF/R_FT; scr.append(Part.makeCylinder(2.75,3,P(x_tab-4.5,R_FT,aa),AX).fuse(thread_rod(P(x_tab-1.5,R_FT,aa),AX,6.0,3,0.5)))
for a in FL_ANG: scr.append(Part.makeCylinder(2.75,3,P(_x0-3,44,a),AX).fuse(thread_rod(P(_x0,44,a),AX,4.5,3,0.5)))
fasteners=Part.makeCompound(scr)
save_part('GR180_Fasteners','ISO 4762 M3x6 (6, starter) + M3x5 (4, rear flange) A2, helical',fasteners)
# --- casing igniter boss 1/4-32 UNEF tapped (boss 7 high: 7.3 engaged = 1.15d steel)
casing=tap(casing,P(X_IGN,51.0+4*25.4/32,A_IGN),D_(A_IGN),60.6-(51.0+4*25.4/32),6.35,25.4/32)
save_part('GR180_Casing','Casing v12: igniter boss 1/4-32 UNEF helical tapped',casing)
# --- igniter (RCEXL CM-6 class 1/4-32 UNEF RH): shank, thread, hex 8, terminal, ceramic, centre electrode, ground strap gap 0.7
dI=D_(A_IGN); tI=V(0,-math.sin(A_IGN),math.cos(A_IGN)); pI=25.4/32
r_t0=51.0+3*pI
ign=rad_cyl(X_IGN,48.2,r_t0,A_IGN,5.0).fuse(thread_rod(P(X_IGN,r_t0,A_IGN),dI,60.6-r_t0,6.35,pI))
ign=ign.fuse(hexprism(P(X_IGN,60.6,A_IGN),dI,8,4)).fuse(rad_cyl(X_IGN,64.6,72.6,A_IGN,4.0))
ign=ign.fuse(rad_cyl(X_IGN,45.0,48.2,A_IGN,4.0)).fuse(rad_cyl(X_IGN,43.5,45.0,A_IGN,1.0))
g0=P(X_IGN,48.2,A_IGN).add(tI*1.8); g1=P(X_IGN,42.5,A_IGN).add(tI*1.8); g2=P(X_IGN,42.5,A_IGN)
ign=ign.fuse(Part.makeCylinder(0.3,g0.sub(g1).Length,g1,g0.sub(g1))).fuse(Part.makeCylinder(0.3,1.8,g2,tI)).fuse(Part.makeSphere(0.3,g1))
save_part('GR180_Igniter','Spark igniter 1/4-32 UNEF RH (RCEXL CM-6 class) helical, hex 8, gap 0.7 at r43.2',ign)
# --- EGT fitting M4x0.7 RH, hex 7 + type-K probe Ø1.5
dE=D_(A_EGT); r_e0=38.6+0.7
egt=thread_rod(P(X_EGT,r_e0,A_EGT),dE,42.5-r_e0,4,0.7).fuse(hexprism(P(X_EGT,42.5,A_EGT),dE,7,3)).cut(rad_cyl(X_EGT,r_e0-0.1,45.6,A_EGT,1.5))
egt=Part.makeCompound([egt,rad_cyl(X_EGT,32.0,56.0,A_EGT,1.5),rad_cyl(X_EGT,56.0,60.0,A_EGT,3.0)])
save_part('GR180_EGT_probe','Type-K Ø1.5 probe + M4x0.7 RH compression fitting (helical), hex 7',egt)
# --- RPM arm M3x0.5 RH in intake boss + DIN 439 M3 lock nut 5.5AF x1.8
rpm_th=thread_rod(P(X_RPM,28.0,A_RPM),D_(A_RPM),8.0,3,0.5)
rpm_ln=tapcut(hexprism(P(X_RPM,33.5,A_RPM),D_(A_RPM),5.5,1.8),P(X_RPM,28.0,A_RPM),D_(A_RPM),8.0,3,0.5)
rpm_sensor=Part.makeCompound([rpm_head,rpm_sleeve.cut(rad_cyl(X_RPM,11.2,14.0,A_RPM,2.5)),rad_cyl(X_RPM,11.2,28.0,A_RPM,2.5),rpm_th,rpm_ln])
save_part('GR180_RPM_sensor','A1120EUA on Ø2.5 arm, M3x0.5 RH thread in intake boss + DIN 439 lock nut',rpm_sensor)
# --- gas bulkhead M12x1 RH: body (thread + 14AF collar), tapped locknut 14AF x4, tapped compression nut 12AF x4.5
b0=P(XM,48.8,A_FUEL)
bulk_body=thread_rod(b0,dF,14.0,12,1.0).fuse(hexprism(P(XM,54.3,A_FUEL),dF,14,4)).cut(Part.makeCylinder(4.0,15,b0,dF))
bulk_ln=tapcut(hexprism(b0,dF,14,4),b0,dF,14,12,1.0)
bulk_cn=tapcut(hexprism(P(XM,58.3,A_FUEL),dF,12,4.5),b0,dF,14,12,1.0)
bulk=Part.makeCompound([bulk_body,bulk_ln,bulk_cn])
save_part('GR180_GasBulkhead','Gas bulkhead M12x1 RH (helical) body + locknut + compression nut, bore Ø8',bulk)
THREADS+= [('Igniter / casing boss','1/4-32 UNEF','RH','6.4 mm (1.0d) steel',''),('EGT fitting / exhaust boss','M4x0.7','RH','3.2-4.3 mm (~1d) steel',''),
 ('RPM arm / intake boss','M3x0.5','RH','5.0 mm (1.7d) Al','+ DIN 439 locknut'),('Gas bulkhead','M12x1','RH','locknut 4 / comp. nut 4.5',''),
 ('Starter feet -> intake ring','6x M3x0.5','RH','4.5 mm (1.5d) Al','ISO 4762 M3x6'),('Rear flange -> exhaust ring','4x M3x0.5','RH','3.0 mm (1.0d) SS','ISO 4762 M3x5'),
 ('Tunnel front (diffuser screws)','6x M3','RH','8.5 mm (2.8d) Al',''),('Intake outer PCD82','6x M3','RH','1.9 mm (0.63d) Al wall','FAIL <1.5d -> use through screw + nut or Helicoil not possible'),('Diffuser vanes','10x M3','RH','8.0 mm (2.7d) Al','')]
for t_ in THREADS: print('THREAD',' | '.join(t_))
print('v12 vols: shaft %.0f nose %.0f nut %.0f tunnel %.0f'%(sh_asm.Volume,no_asm.Volume,nut.Volume,ts.Volume)); print('v12 valid: shaft',sh_asm.isValid(),'nose',no_asm.isValid(),'nut',nut.isValid(),'tunnel',ts.isValid(),'casing',casing.isValid(),'exh',exh.isValid(),'intake',ins.isValid())
# ---- assembly
d3=App.newDocument('GR180_Shaft_assembly')
a=d3.addObject('Part::Feature','ShaftTunnel'); a.Shape=ts
o=-51.0  # shaft front bearing shoulder (shaft x58) at tunnel x7 -> front 608 sits at tunnel x0-7
s1=d3.addObject('Part::Feature','Shaft'); s1.Shape=sh_asm
n1=d3.addObject('Part::Feature','NoseCone'); n1.Shape=no_asm
pass  # v12: nose already in assembly coords
def ring(nm,x,L,ro,ri,col):
    o_=d3.addObject('Part::Feature',nm); o_.Shape=Part.makeCylinder(ro,L,V(x,0,0),V(1,0,0)).cut(Part.makeCylinder(ri,L,V(x,0,0),V(1,0,0))); return o_
def bearing608(nm,x):
    # 8x22x7: outer ring 22/18.4, inner ring 12.1/8, 7 Si3N4 balls d3.969 on pitch Ø15.1
    sh=[Part.makeCylinder(11,7,V(x,0,0),V(1,0,0)).cut(Part.makeCylinder(9.2,7,V(x,0,0),V(1,0,0))),
        Part.makeCylinder(6.05,7,V(x,0,0),V(1,0,0)).cut(Part.makeCylinder(4,7,V(x,0,0),V(1,0,0)))]
    for k in range(7):
        a_=2*math.pi*k/7; sh.append(Part.makeSphere(3.969/2,V(x+3.5,7.55*math.cos(a_),7.55*math.sin(a_))))
    o_=d3.addObject('Part::Feature',nm); o_.Shape=Part.makeCompound(sh); return o_
bearing608('FrontBearing_608_hybrid_8x22x7',2.1)
bearing608('RearBearing_608_hybrid_8x22x7',100.3)
# wave spring modelled as a wavy single-turn ring (3 waves), envelope 21.8/16.2, installed height 2.8 (x8.5-11.3)
import Part as _P
pts=[];N=180
for k in range(N+1):
    t_=2*math.pi*k/N; pts.append(V(9.1+1.1+0.6*math.cos(3*t_),10.4*math.cos(t_),10.4*math.sin(t_)))
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
for k,v in [('SupplyLines',supply),('SupplySeals',Part.makeCompound(seals)),('NGV',ngv),('Turbine',tw),('TurbineNut',nut),('Exhaust',exh),('Casing',casing),('Starter',starter),('Compressor',cw),('FrontBearing_Oring',fb_oring),('RPM_Sensor',rpm_sensor),('RPM_Magnet',rpm_mag),('Balance_Slug',bal_slug),('Igniter',ign),('EGT_Probe',egt),('GasBulkhead',bulk),('Fasteners',fasteners),('RearSpacer_8x12x6_3',rear_spacer),('OilRing_Front',oilring_f),('OilRing_Rear',oilring_r),('FrontShim_8x12x2_1',front_shim)]:
    o_=d3.addObject('Part::Feature',k); o_.Shape=v
d3.recompute(); d3.saveAs(os.path.join(OUT,'GR180_Shaft_assembly.FCStd'))
Part.makeCompound([o_.Shape for o_ in d3.Objects]).exportStep(os.path.join(OUT,'GR180_Shaft_assembly.step'))
def gs_(o_): return o_.Shape
objs=[o_ for o_ in d3.Objects]
import sys; sys.stdout.flush()
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

# v11: verification run separately (parallel): verify_gr180.py
''' (new parts) and rotation sweep =====
O={o_.Name:o_ for o_ in d3.Objects}
def gap(A,B):
    try: return A.distToShape(B)[0]
    except Exception:
        try: return A.distToShape(B.Shells[0] if B.Shells else B)[0]
        except Exception: return float('nan')
def sh(n): return O[n].Shape
pairs=[('Turbine','NGV'),('Turbine','Exhaust'),('Turbine','ShaftTunnel'),('Turbine','Casing'),('TurbineNut','Exhaust'),('Compressor','Intake'),('Compressor','Diffuser'),('Compressor','IntakeOuter'),
       ('Shaft','ShaftTunnel'),('Shaft','Diffuser'),('Shaft','NGV'),('NoseCone','Intake'),('NoseCone','Starter'),('NGV','Exhaust'),('NGV','ShaftTunnel'),('Casing','IntakeOuter'),('Casing','Exhaust'),('Casing','Diffuser'),('FrontBearing_Oring','ShaftTunnel')]
for a_,b_ in pairs:
    print('STATIC gap %-20s %-14s %.3f'%(a_,b_,gap(sh(a_),sh(b_))))
import time; t0=time.time()
def sweep(rot,stat,angs):
    res={}
    for st in stat:
        mn=(1e9,0)
        for a in angs:
            r=sh(rot).copy(); r.rotate(V(0,0,0),V(1,0,0),a); d_=gap(r,sh(st))
            if d_!=d_: continue
            if d_<mn[0]: mn=(d_,a)
        res[st]=mn; print('ROT %-11s vs %-12s min %.3f at %.2f deg (%d steps)'%(rot,st,mn[0],mn[1],len(angs)))
angC=[k*360/14/16 for k in range(16)]+[k*30 for k in range(1,12)]
angT=[k*360/23/12 for k in range(12)]+[k*30 for k in range(1,12)]
sweep('Compressor',['Intake','Diffuser','IntakeOuter'],angC)
sweep('Turbine',['NGV','Exhaust','Casing'],angT)
sweep('Shaft',['ShaftTunnel','Diffuser','NGV'],[0,90,180,270])
sweep('NoseCone',['Intake','Starter'],[0,90,180,270])
sweep('TurbineNut',['Exhaust'],[0,90,180,270])
print('rotation sweep s',round(time.time()-t0))
# per-object STEP for animation/video
os.makedirs(os.path.join(OUT,'asm_parts'),exist_ok=True)
for o_ in d3.Objects:
    if o_.Shape.Volume>0: o_.Shape.exportStep(os.path.join(OUT,'asm_parts',o_.Name+'.step'))
print('ALLDONE')

'''
