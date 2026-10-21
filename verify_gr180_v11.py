# GR180 assembly verification: static pairwise interference, key gaps, rotor rotation sweep, per-part STEP export
import FreeCAD as App, Part, math, os, sys, time
V=App.Vector
OUT=os.path.expanduser('~/Desktop/GR180-3D')
try: d3
except NameError: d3=App.openDocument(os.path.join(OUT,'GR180_Shaft_assembly.FCStd'))
def pr(*a): print(*a); sys.stdout.flush()
O={o_.Name:o_ for o_ in d3.Objects if hasattr(o_,'Shape') and o_.Shape.Volume>0}
def sh(n): return O[n].Shape
def gap(A,B):
    try: return A.distToShape(B)[0]
    except Exception: return float('nan')
SEC=os.environ.get('SEC','all')
names=list(O); t0=time.time(); hits=[]
if SEC not in ('all','pair'): names=[]
for i in range(len(names)):
    for j in range(i+1,len(names)):
        A,B=sh(names[i]),sh(names[j])
        if not A.BoundBox.intersect(B.BoundBox): continue
        g=gap(A,B)
        if g==g and g>1e-4: continue
        t=time.time(); v=A.common(B).Volume
        if v>1e-3: hits.append((names[i],names[j],v)); pr('INTERFERENCE %s / %s  %.3f mm3 (%.0fs)'%(names[i],names[j],v,time.time()-t))
        else: pr('contact (zero gap, no volume) %s / %s'%(names[i],names[j]))
pr('pairwise done in %.0fs, %d interferences'%(time.time()-t0,len(hits)))
pairs=[('Turbine','NGV'),('Turbine','Exhaust'),('Turbine','ShaftTunnel'),('Turbine','Casing'),('TurbineNut','Exhaust'),('Compressor','Intake'),('Compressor','Diffuser'),('Compressor','IntakeOuter'),
       ('Shaft','ShaftTunnel'),('Shaft','Diffuser'),('Shaft','NGV'),('NoseCone','Intake'),('NoseCone','Starter'),('NGV','Exhaust'),('NGV','ShaftTunnel'),('Casing','IntakeOuter'),('Casing','Exhaust'),('Casing','Diffuser'),('FrontBearing_Oring','ShaftTunnel'),('FrontBearing_Oring','FrontBearing_608_hybrid_8x22x7')]
for a_,b_ in (pairs if SEC in ('all','pair') else []):
    if a_ in O and b_ in O: pr('STATIC gap %-20s %-32s %.3f'%(a_,b_,gap(sh(a_),sh(b_))))
def sweep(rot,stat,angs):
    if SEC not in ('all',rot): return
    for st in stat:
        mn=(1e9,0)
        for a in angs:
            r=sh(rot).copy(); r.rotate(V(0,0,0),V(1,0,0),a); d_=gap(r,sh(st))
            if d_==d_ and d_<mn[0]: mn=(d_,a)
        pr('ROT %-11s vs %-12s min %.3f mm at %.2f deg (%d positions)'%(rot,st,mn[0],mn[1],len(angs)))
t0=time.time()
angC=[k*360/14/12 for k in range(12)]+[k*30 for k in range(1,12)]
angT=[k*360/23/10 for k in range(10)]+[k*30 for k in range(1,12)]
sweep('Compressor',['Intake','Diffuser','IntakeOuter'],angC)
sweep('Turbine',['NGV','Exhaust','Casing'],angT)
sweep('Shaft',['ShaftTunnel','Diffuser','NGV'],[0,90,180,270])
sweep('NoseCone',['Intake','Starter'],[0,90,180,270])
sweep('TurbineNut',['Exhaust'],[0,90,180,270])
sweep('Shaft',['Exhaust'],[0,90,180,270])
sweep('NoseCone',['RPM_Sensor'],[0,90,180,270])
sweep('RPM_Magnet',['RPM_Sensor'],[k*15 for k in range(24)])
sweep('Compressor',['RPM_Sensor'],angC)
sweep('Turbine',['EGT_Probe'],angT)
pr('rotation sweep %.0fs'%(time.time()-t0))
os.makedirs(os.path.join(OUT,'asm_parts'),exist_ok=True)
for n in (O if SEC in ('all','pair') else []): sh(n).exportStep(os.path.join(OUT,'asm_parts',n+'.step'))
pr('ALLDONE')
