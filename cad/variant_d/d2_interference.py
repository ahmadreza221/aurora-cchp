# GR180 version D2 - interference check of the new INTAKE / EXHAUST / FRAME parts against the D2 reference parts
# (v13A core minus Starter/NoseCone/Exhaust/Turbine/NGV/TurbineNut + D-* minus D-180 + the D2R turbine T-* from
# cad_out/variant_d/D2/TURBINE or GR180_D2_TURBINE_DIR, else RT2/RT-*) and against each other.
# Contact faces of bolted / clamped joints are allowed (common volume < 50 mm3); D-160, D-150 and RT-180 are superseded
# (their overlaps are listed as 'superseded part', not counted).
# Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2_interference.py -> cad_out/variant_d/D2/d2_interference.json
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2_common import *

ref = {k: Part.read(p) for k, p in d2_reference_files(include_superseded=True).items()}
new = {}
for sub in ('INTAKE', 'EXHAUST', 'FRAME'):
    for p in sorted(glob.glob(os.path.join(OUT, sub, '*.step'))):
        new[os.path.splitext(os.path.basename(p))[0]] = Part.read(p)
CONTACT = {('INT-120_Pod_Tail_Fairing', 'D-101_Generator_Housing_Jacket'), ('INT-112_Rear_Ring_2halves_Foot', 'Casing'),
           ('INT-115_Pod_Struts_x3', 'D-101_Generator_Housing_Jacket'), ('INT-110_Plenum_Can_SidePort', 'D-101_Generator_Housing_Jacket'),
           ('EX-111_Inlet_Flange_6xM6', 'T-121_Exducer_Shroud_Exhaust_Flange'), ('FR-131_Slide_Pedestals_x4', 'T-120_Turbine_Housing_Plenum')}
NEW_CONTACT = {('INT-110_Plenum_Can_SidePort', 'INT-112_Rear_Ring_2halves_Foot'), ('INT-111_Dish_Skirt', 'INT-112_Rear_Ring_2halves_Foot'),
               ('INT-110_Plenum_Can_SidePort', 'INT-140_Port_FOD_Guard'), ('INT-111_Dish_Skirt', 'INT-115_Pod_Struts_x3'),
               ('INT-120_Pod_Tail_Fairing', 'INT-115_Pod_Struts_x3'), ('INT-112_Rear_Ring_2halves_Foot', 'FR-120_Front_Pedestal_Fixed'),
               ('EX-110_Diffuser_Stub_Weldment', 'EX-111_Inlet_Flange_6xM6'), ('EX-110_Diffuser_Stub_Weldment', 'EX-112_Flange_DN125_PN6'),
               ('EX-110_Diffuser_Stub_Weldment', 'EX-113_Support_Lugs'), ('EX-120_Insulation_Jacket_env', 'EX-110_Diffuser_Stub_Weldment'),
               ('EX-113_Support_Lugs', 'FR-131_Slide_Pedestals_x4'),
               ('FR-110_Base_Frame_RHS', 'FR-120_Front_Pedestal_Fixed'), ('FR-110_Base_Frame_RHS', 'FR-131_Slide_Pedestals_x4'),
               ('FR-110_Base_Frame_RHS', 'FR-140_AV_Mounts_x4_env'), ('FR-110_Base_Frame_RHS', 'FR-150_Lifting_Lugs_x4')}

res = interference(new, ref, CONTACT)
names = sorted(new)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if not new[a].BoundBox.intersect(new[b].BoundBox):
            continue
        v = new[a].common(new[b]).Volume
        if v > 1.0:
            ok = ((a, b) in NEW_CONTACT or (b, a) in NEW_CONTACT) and v < 50
            res.append(dict(new=a, ref=b, common_mm3=round(v, 2), status='contact (allowed)' if ok else 'OVERLAP (new vs new)'))
bad = [r for r in res if r['status'].startswith('OVERLAP')]
out = dict(turbine_dir=os.path.relpath(TURBINE_DIR, ROOT) if TURBINE_DIR.startswith(ROOT) else TURBINE_DIR, reference_parts=sorted(ref), new_parts=names, superseded=SUPERSEDED, results=res, n_overlaps=len(bad),
           verdict='0 overlaps' if not bad else '%d overlaps' % len(bad))
json.dump(out, open(os.path.join(OUT, 'd2_interference.json'), 'w'), indent=1)
for r in res:
    print('%-34s %-38s %10.2f mm3  %s' % (r['new'], r['ref'], r['common_mm3'], r['status']))
print('reference %d parts, new %d parts -> %s' % (len(ref), len(new), out['verdict']))
