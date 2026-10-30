"""AURORA-1000 turbine hot section (rev 1): horizontally split outer casing, shroud carriers, honeycomb shrouds, inner
diaphragms with honeycomb seals, radial centring pins. Calculations: sim/engine/a1000_hot_section_calc.py.

Concept (follows from rotor rev 1, cad/engine/a1000_rotor.py: the rotor is built and balanced as one unit, so the stator
must open around it):
  outer casing   EN-GJS-400-18LT ductile iron, split on the horizontal plane (z = 0), bathed inside by the compressor
                 delivery air (3.8 bar, 175 C) on its way from the compressor collector to the recuperator; the cold
                 casing carries the pressure, the NGV torque and the axial gas loads
  carriers       C1 (NGV1 outer ring + R1 shroud) and C2 (NGV2 outer ring + R2 shroud), 1.4828, also split in halves; they
                 run hot (547 / 497 C, the tip-clearance requirement of sim/engine/a1000_turbine_checks.py) and float on 8
                 radial pins in one plane (x of the C1 - C2 flange): free radial growth, centred, located axially there
  shrouds        brazed Hastelloy X honeycomb (1/32 in cells, 4 mm) on a 3 mm backing segment, abradable for start rubs
  diaphragms     front (NGV1 inner ring -> seal r 93-96 over the drum - R1 flanges) and interstage (NGV2 inner ring -> seal
                 r 93-96 over the R1 - R2 flanges), Hastelloy X, honeycomb lands; both in halves with the NGV rings
  NGV rings      cut into two halves at the split plane (EDM), strip seals in the cut faces (not modelled)
  rev 6          R1 - NGV2 axial gap +25 mm (docs/08 sec. 12.4.2): NGV2, R2 and C2 move 25 mm aft, the casing is 25 mm longer
                 (x 678-903), the pin plane and C1 stay behind R1; the open gap gets an outer liner (HS-222, in C2) and an
                 inner gap ring (HS-234, on the NGV2 inner ring) on the annulus lines; the interstage seal runs on the four
                 knife edges of the rotor's R1 - R2 spacer ring (RT-107)
Frame: rotor frame mm (x = engine axis, z up). Run:
  freecadcmd -c "import sys; sys.argv=['a1000_hot_section.py','--cad']; exec(open('cad/engine/a1000_hot_section.py').read())"
  -> cad_out/engine/A1000_hot/*.step, fusion/A1000_hot/*.step + parts.json
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'engine')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
_argv = list(sys.argv); sys.argv = [sys.argv[0]]
import a1000_rotor as G                                       # noqa: E402  (rotor rev 1 layout; a1000_turbine as G.A)
sys.argv = _argv
A, o = G.A, G.X_OFF


def X(row, edge):
    """row leading / trailing edge in the rotor frame"""
    return (A.X_LE if edge == 'le' else A.X_TE)[row] + o


TIP_COLD = dict(R1=0.50, R2=0.60)                               # cold tip clearance (sim/engine/a1000_turbine_checks.py)
HC = dict(t=4.0, back=3.0)                                       # honeycomb depth, backing thickness [mm]
CAS = dict(ri=322.0, t=22.0, x0=678.0, x1=903.0, fl_r=392.0, fl_t=24.0, split_w=48.0, split_t=28.0, bolt=16.0, pitch=66.0)   # rev 6: x1 878 -> 903
C1 = dict(x0=676.0, ri=258.0, ro=270.0)                            # NGV1 hook + R1 shroud
C2 = dict(x1=875.0, ri=272.0, ro=284.0)                            # NGV2 hook + R2 shroud (rev 6: x1 850 -> 875)
X_PIN = X('R1', 'te') + 0.5 * A.GAP2                             # C1 - C2 flange / pin plane (between R1 and NGV2; rev 6: kept
                                                                 # behind R1, so C1 and the pins stay, C2 takes the 25 mm)
LINER = dict(t=3.0, ax_cl=0.5, web=4.0)                          # rev 6 gap liners: thickness, axial clearance, support web
PIN = dict(n=8, d=20.0, r0=286.0, r1=CAS['ri'] + CAS['t'] - 4.0 + 22.0)       # head seats on the casing boss
FLANGE_C = dict(t=8.0, ro=300.0)                                 # C1 / C2 bolted flange
SEAL = dict(ri=92.6, ro=96.0, hc=3.4)                            # diaphragm honeycomb seal over the 92 mm rotor flanges


def shroud_r(row, x):
    """cold inner (abradable) radius of the honeycomb over a rotor row at x"""
    xl, xt = X(row, 'le'), X(row, 'te')
    return A.r_tip(min(max(x, xl), xt) - o) + TIP_COLD[row]


# ================================================================================================ FreeCAD (--cad)
def _fc():
    import FreeCAD as App, Part
    return App, Part, App.Vector


def revolve(poly):
    return G.revolve(poly)


def tube(x0, x1, ro, ri=0.0):
    return G.tube(x0, x1, ro, ri)


def half(shape, upper):
    """keep z >= 0 (upper) or z <= 0 (lower)"""
    App, Part, V = _fc()
    b = Part.makeBox(4000, 2000, 1000, V(-1000, -1000, 0.0 if upper else -1000.0))
    return shape.common(b)


def shroud_ring(row, n=12):
    """honeycomb + backing following the tip line (conical over R2) from LE - 3 to TE + 3"""
    x0, x1 = X(row, 'le') - 3.0, X(row, 'te') + 3.0
    xs = [x0 + (x1 - x0) * k / n for k in range(n + 1)]
    inner = [(x, shroud_r(row, x)) for x in xs]
    hcomb = revolve(inner + [(x, r + HC['t']) for x, r in inner[::-1]])
    back = revolve([(x, r + HC['t']) for x, r in inner] + [(x, r + HC['t'] + HC['back']) for x, r in inner[::-1]])
    return hcomb, back


def carriers():
    """C1 / C2 (1.4828): rings with the NGV hooks and the bolted flange at X_PIN"""
    App, Part, V = _fc()
    xf = X_PIN; t = FLANGE_C['t']
    n1_out = A.r_tip(A.X_TE['N1']) + 8.0                                   # NGV1 outer ring OD
    c1 = tube(C1['x0'], xf - t, C1['ro'], C1['ri'])
    c1 = c1.fuse(tube(C1['x0'], C1['x0'] + 10.0, C1['ri'], n1_out + 0.3))      # front hook over the NGV1 outer ring
    c1 = c1.fuse(tube(xf - t, xf, FLANGE_C['ro'], C1['ri']))
    n2_out = A.r_tip(A.X_TE['N2']) + 8.0
    c2 = tube(xf, C2['x1'], C2['ro'], C2['ri']).fuse(tube(xf, xf + t, FLANGE_C['ro'], C2['ri']))
    c2 = c2.fuse(tube(X('N2', 'le') + 3.5, X('N2', 'le') + 13.5, C2['ri'], n2_out + 0.3))   # NGV2 hook (over the outer ring)
    c2 = c2.fuse(tube(C2['x1'] - 8.0, C2['x1'], C2['ro'] + 10.0, C2['ri']))   # rear lip (rear pin slots)
    bolts = G.holes(xf - t - 1, xf + t + 1, 0.5 * (FLANGE_C['ro'] + max(C1['ro'], C2['ri'])) + 2.0, 11.0, 24)
    c1 = c1.cut(bolts); c2 = c2.cut(bolts)
    for k in range(PIN['n']):
        a = 2 * math.pi * (k + 0.5) / PIN['n']
        slot = Part.makeCylinder(PIN['d'] / 2 + 0.3, 40.0, V(xf, (FLANGE_C['ro'] - 30) * math.cos(a), (FLANGE_C['ro'] - 30) * math.sin(a)),
                                 V(0, math.cos(a), math.sin(a)))
        c1 = c1.cut(slot); c2 = c2.cut(slot)
    return c1.removeSplitter(), c2.removeSplitter()


def outer_casing():
    App, Part, V = _fc()
    c = CAS
    shell = tube(c['x0'], c['x1'], c['ri'] + c['t'], c['ri'])
    shell = shell.fuse(tube(c['x0'], c['x0'] + c['fl_t'], c['fl_r'], c['ri'])).fuse(tube(c['x1'] - c['fl_t'], c['x1'], c['fl_r'], c['ri']))
    # horizontal split flanges (both sides, y = +-), M16 bolts
    for sy in (1, -1):
        y0 = sy * (c['ri'] + c['t'] - 4.0); y1 = sy * (c['ri'] + c['t'] + c['split_w'])
        shell = shell.fuse(Part.makeBox(c['x1'] - c['x0'], abs(y1 - y0), 2 * c['split_t'], V(c['x0'], min(y0, y1), -c['split_t'])))
    shell = shell.cut(tube(c['x0'] - 1, c['x1'] + 1, c['ri'], 0.0))
    # radial pin bosses at X_PIN
    for k in range(PIN['n']):
        a = 2 * math.pi * (k + 0.5) / PIN['n']
        d = V(0, math.cos(a), math.sin(a))
        shell = shell.fuse(Part.makeCylinder(18.0, 22.0, V(X_PIN, 0, 0) + d * (c['ri'] + c['t'] - 4.0), d))
    # the compressor delivery air leaves through the rear flange annulus into the exhaust-end air manifold (next design step)
    for k in range(PIN['n']):
        a = 2 * math.pi * (k + 0.5) / PIN['n']
        d = V(0, math.cos(a), math.sin(a))
        shell = shell.cut(Part.makeCylinder(PIN['d'] / 2 + 0.1, 80.0, V(X_PIN, 0, 0) + d * (c['ri'] - 10.0), d))
    # bolts: split line and end flanges
    n_split = int((c['x1'] - c['x0'] - 40) // c['pitch']) + 1
    holes = []
    for sy in (1, -1):
        yb = sy * (c['ri'] + c['t'] + 0.55 * c['split_w'])
        for k in range(n_split):
            xb = c['x0'] + 20 + k * c['pitch']
            holes.append(Part.makeCylinder(c['bolt'] / 2 + 1.0, 4 * c['split_t'], V(xb, yb, -2 * c['split_t']), V(0, 0, 1)))
    shell = shell.cut(holes)
    shell = shell.cut(G.holes(c['x0'] - 1, c['x0'] + c['fl_t'] + 1, c['fl_r'] - 22.0, 18.0, 32, 0.25))
    shell = shell.cut(G.holes(c['x1'] - c['fl_t'] - 1, c['x1'] + 1, c['fl_r'] - 22.0, 18.0, 32, 0.25))
    return half(shell, True).removeSplitter(), half(shell, False).removeSplitter()


def diaphragm(x_ring, r_ring, x_seal, x_seal_len, t=3.0):
    """conical Hastelloy X diaphragm from the NGV inner ring (x_ring, r_ring) down to the seal carrier at x_seal, plus the
    honeycomb land r SEAL ri..ro over x_seal .. x_seal + x_seal_len"""
    App, Part, V = _fc()
    r_in = SEAL['ro'] + 2.0
    r_ring -= 1.0                                                           # flange under the NGV inner ring (bolted)
    cone = revolve([(x_ring, r_ring), (x_ring + t, r_ring), (x_seal + t + 4, r_in + 4), (x_seal + t + 4, r_in), (x_seal + 4, r_in),
                    (x_seal + 4, r_in + 2), (x_ring, r_ring - 2)])
    seal_back = tube(x_seal, x_seal + x_seal_len, r_in, SEAL['ro'])
    hc = tube(x_seal, x_seal + x_seal_len, SEAL['ro'], SEAL['ri'])
    return cone.fuse(seal_back).removeSplitter(), hc


def gap_liners():
    """rev 6: the open R1 - NGV2 gap. Outer liner on the casing line r_tip(x) from the R1 shroud to the NGV2 outer ring with
    a web up to the C2 bore at its aft end; inner ring on the hub line r_hub(x) from behind the R1 platform to the NGV2
    inner ring, with a flange down to the ring's front face (bolted, not modelled)"""
    q = LINER; xa, xb = X('R1', 'te') + 3.0 + q['ax_cl'], X('N2', 'le') - 4.0 - q['ax_cl']
    xs = sorted({xa, xb} | {x + o for x, _ in A.H_ST if xa < x + o < xb})
    rt = [(x, A.r_tip(x - o)) for x in xs]
    outer = revolve(rt + [(xb, C2['ri'] - 0.3), (xb - q['web'], C2['ri'] - 0.3), (xb - q['web'], A.r_tip(xb - q['web'] - o) + q['t'])] +
                    [(x, r + q['t']) for x, r in rt[::-1] if x < xb - q['web']])
    xi = X('R1', 'te') + A.PLAT_OVH + 1.5                                  # 1.5 mm axial gap to the R1 platform (rim seal)
    xs = sorted({xi, xb} | {x + o for x, _ in A.H_ST if xi < x + o < xb})
    rh = [(x, A.r_hub(x - o)) for x in xs]
    inner = revolve(rh + [(xb, A.r_hub(xb - o) - 10.0), (xb - q['web'], A.r_hub(xb - o) - 10.0), (xb - q['web'], A.r_hub(xb - q['web'] - o) - q['t'])] +
                    [(x, r - q['t']) for x, r in rh[::-1] if x < xb - q['web']])
    return outer, inner


def pins():
    App, Part, V = _fc()
    ps = []
    for k in range(PIN['n']):
        a = 2 * math.pi * (k + 0.5) / PIN['n']
        d = V(0, math.cos(a), math.sin(a))
        ps.append(Part.makeCylinder(PIN['d'] / 2, PIN['r1'] - (FLANGE_C['ro'] - 30) + 8.0, V(X_PIN, 0, 0) + d * (FLANGE_C['ro'] - 30), d))
        ps.append(Part.makeCylinder(16.0, 8.0, V(X_PIN, 0, 0) + d * PIN['r1'], d))                         # head
    return Part.makeCompound(ps)


def build_all():
    out = {}
    up, lo = outer_casing()
    out['HS-201 Outer casing upper half (EN-GJS-400-18LT)'] = (up, 'EN-GJS-400-18LT', 'casing')
    out['HS-202 Outer casing lower half (EN-GJS-400-18LT)'] = (lo, 'EN-GJS-400-18LT', 'casing')
    c1, c2 = carriers()
    out['HS-210 Shroud carrier C1 (NGV1 + R1, 1.4828)'] = (c1, '1.4828', 'carrier')
    out['HS-220 Shroud carrier C2 (NGV2 + R2, 1.4828)'] = (c2, '1.4828', 'carrier')
    lo, li = gap_liners()
    out['HS-222 Gap liner R1 - NGV2, outer (Hastelloy X)'] = (lo, 'Hastelloy X', 'carrier')
    for row, tag in (('R1', 'HS-211'), ('R2', 'HS-221')):
        hc, bk = shroud_ring(row)
        out['%s Honeycomb shroud %s (Hastelloy X)' % (tag, row)] = (hc, 'Hastelloy X honeycomb', 'honeycomb')
        out['%s Shroud backing %s' % (tag, row)] = (bk, 'Hastelloy X', 'carrier')
    n1_in = A.r_hub(A.X_LE['N1']) - 6.0
    d1, h1 = diaphragm(X('N1', 'le') - 4.0, n1_in, G.X_J['drum_R1'] - 12.0, 24.0)
    out['HS-230 Front diaphragm (Hastelloy X)'] = (d1, 'Hastelloy X', 'diaphragm')
    out['HS-231 Front seal honeycomb'] = (h1, 'Hastelloy X honeycomb', 'honeycomb')
    n2_in = A.r_hub(0.5 * (A.X_LE['N2'] + A.X_TE['N2'])) - 6.0
    d2, h2 = diaphragm(0.5 * (X('N2', 'le') + X('N2', 'te')) - 4.0, n2_in, G.X_J['R1_spc'] + 2.0, G.L_TSPC - 4.0)   # over the spacer fins
    out['HS-232 Interstage diaphragm (Hastelloy X)'] = (d2, 'Hastelloy X', 'diaphragm')
    out['HS-233 Interstage seal honeycomb'] = (h2, 'Hastelloy X honeycomb', 'honeycomb')
    out['HS-234 Gap ring R1 - NGV2, inner (Hastelloy X)'] = (li, 'Hastelloy X', 'diaphragm')
    out['HS-240 Radial centring pins x8 (1.4980)'] = (pins(), '1.4980 (A286)', 'pins')
    return out


def main_cad():
    out_c = os.path.join(ROOT, 'cad_out', 'engine', 'A1000_hot'); out_f = os.path.join(ROOT, 'fusion', 'A1000_hot')
    os.makedirs(out_c, exist_ok=True); os.makedirs(out_f, exist_ok=True)
    rho = {'EN-GJS-400-18LT': 7100, '1.4828': 7900, 'Hastelloy X': 8220, 'Hastelloy X honeycomb': 8220 * 0.08, '1.4980 (A286)': 7940}
    info = {}
    for name, (s, mat, grp) in build_all().items():
        fn = ''.join(c if c.isalnum() else '_' for c in name).strip('_') + '.step'
        s.exportStep(os.path.join(out_c, fn)); s.exportStep(os.path.join(out_f, fn))
        bb = s.BoundBox
        info[name] = dict(step=fn, material=mat, group=grp, valid=s.isValid(), solids=len(s.Solids), mass_kg=round(s.Volume * 1e-9 * rho.get(mat, 7850), 2),
                          x=[round(bb.XMin, 1), round(bb.XMax, 1)], r=round(max(bb.YMax, bb.ZMax, -bb.YMin, -bb.ZMin), 1))
        print('%-52s %-5s solids %2d  %7.2f kg  x %.0f..%.0f  r %.0f' % (name, s.isValid(), len(s.Solids), info[name]['mass_kg'], bb.XMin, bb.XMax, info[name]['r']), flush=True)
    json.dump(dict(frame='rotor frame mm', x_pin=X_PIN, parts=info), open(os.path.join(out_f, 'parts.json'), 'w'), indent=1)


if '--cad' in sys.argv:
    main_cad()
