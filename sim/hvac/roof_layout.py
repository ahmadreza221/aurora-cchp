# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP roof layout: equipment positions on the 10 x 10 m roof over the hall, operating weights, centre of
gravity, separation checks (engine intake / exhaust stack / cooling tower / dry cooler) and service zones.
Writes docs/hvac/roof_layout.svg and sim/hvac/roof_layout.json.  Coordinates: x east, y north, metres, origin = SW
corner of the hall roof. Prevailing summer wind ASSUMED from the NW (Shamal) - confirm on site.
Run:  python3 sim/hvac/roof_layout.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = json.load(open(os.path.join(HERE, 'hvac_results.json'))) if os.path.exists(os.path.join(HERE, 'hvac_results.json')) else None
ROOF = (10.0, 10.0)

# tag: (label, kind, x0, y0, w, d, h, operating kg, group, service zones [(side, depth)])
TOWER_D = RES['tower']['dia'] if RES else 1.88
TOWER_KG = RES['tower']['op_kg'] if RES else 820
HX_KG = round(RES['hx']['mass']['op']) if RES else 350
CH1_KG = RES['chillers']['units']['CH-1']['op'] if RES else 560
CH2_KG = RES['chillers']['units']['CH-2']['op'] if RES else 420
EQ = {
    'IF-1':  ('intake louver + G4/F8 filters + CHW coil CC-1', 'rect', 0.40, 7.60, 0.90, 0.90, 1.40, 150, 'engine', [('W', 0.0)]),
    'EP-1':  ('engine package GR180+FPT+PMG+recuperator', 'rect', 1.30, 7.60, 1.40, 0.90, 1.30, 450, 'engine', [('N', 1.0), ('S', 1.0)]),
    'DC-1':  ('aux glycol dry cooler (engine interface)', 'rect', 0.40, 5.60, 1.20, 0.60, 1.00, 90, 'engine', [('S', 0.6)]),
    'D-101': ('exhaust diverter damper', 'rect', 4.60, 7.80, 0.50, 0.50, 0.90, 60, 'exhaust', []),
    'HX-1':  ('exhaust/water HX (vertical up-flow)', 'rect', 5.10, 7.60, 0.80, 0.90, 1.80, HX_KG, 'exhaust', [('N', 0.8), ('S', 0.8)]),
    'ST-1':  ('stack DN250 double wall + silencer SL-101, top +4.0 m', 'circle', 5.50, 8.05, 0.35, 0.35, 4.00, 140, 'exhaust', []),
    'LLH-1': ('HW low-loss header / buffer 200 L', 'circle', 6.60, 7.30, 0.50, 0.50, 1.40, 280, 'tank', []),
    'BOP-R': ('roof BOP/MCC panel (B6-R), sun canopy', 'rect', 7.00, 9.20, 1.20, 0.45, 2.00, 220, 'elec', [('S', 1.0)]),
    'PS-1':  ('hydronic pump skid P-1..P-5, ET-1/2, AS-1/2', 'rect', 2.80, 5.20, 2.80, 1.10, 1.20, 750, 'pump', [('N', 0.8), ('S', 0.8)]),
    'CH-1':  ('absorption chiller SC10 class', 'rect', 4.40, 2.50, 0.76, 0.97, 1.90, CH1_KG, 'chiller', [('N', 1.0), ('E', 0.6), ('W', 0.6), ('S', 0.5)]),
    'CH-2':  ('absorption chiller SC5 class', 'rect', 2.80, 2.60, 0.594, 0.744, 1.76, CH2_KG, 'chiller', [('N', 1.0), ('E', 0.6), ('W', 0.6), ('S', 0.5)]),
    'TK-1':  ('CHW buffer / decoupler 500 L', 'circle', 6.40, 3.60, 0.75, 0.75, 1.70, 650, 'tank', []),
    'CT-1':  ('cooling tower, FRP round, %.0f ton class' % (RES['tower']['sel']['S'] if RES else 40), 'circle', 8.25, 1.95,
              TOWER_D, TOWER_D, RES['tower']['height'] if RES else 1.95, TOWER_KG, 'tower', [('ring', 1.0)]),
    'PS-2':  ('CW pump skid P-6A/B + basket strainer', 'rect', 5.00, 0.40, 1.40, 0.90, 1.00, 380, 'pump', [('N', 0.6)]),
    'WT-1':  ('water treatment: dosing x3 in bund, EC ctrl, side-stream sep.', 'rect', 8.30, 4.00, 1.20, 0.70, 1.30, 300, 'water', [('W', 0.8)]),
    'RS-1':  ('riser + roof penetration to hall (CHW, DHW, drains)', 'rect', 9.30, 6.30, 0.40, 0.40, 0.50, 60, 'pipe', []),
    'FS-1':  ('fire suppression cabinet FK-5-1-12, 2 cyl., shaded/vented', 'rect', 3.00, 9.30, 0.60, 0.45, 1.40, 80, 'fire', [('S', 0.8)]),
    'HATCH': ('roof access hatch / stair (ASSUMED)', 'rect', 0.40, 0.40, 0.80, 0.80, 0.00, 0, 'access', []),
}
DISTRIBUTED = {'roof piping, filled, + supports': 450, 'galvanised steel dunnage / skid frames': 900,
               'cable trays, insulation, cladding, walkways': 250}

def centre(e):
    _, kind, x, y, w, d = e[:6]
    return (x, y) if kind == 'circle' else (x + w / 2, y + d / 2)

def footprint(e):
    _, kind, x, y, w, d = e[:6]
    return (x - w / 2, y - d / 2, w, d) if kind == 'circle' else (x, y, w, d)

def zones(e):
    out = []
    x, y, w, d = footprint(e)
    for side, dep in e[9]:
        if dep <= 0:
            continue
        if side == 'N':
            out.append((x, y + d, w, dep))
        elif side == 'S':
            out.append((x, y - dep, w, dep))
        elif side == 'E':
            out.append((x + w, y, dep, d))
        elif side == 'W':
            out.append((x - dep, y, dep, d))
        elif side == 'ring':
            out.append(('ring', centre(e), w / 2 + dep))
    return out

def overlap(a, b):
    return a[0] < b[0] + b[2] - 1e-6 and b[0] < a[0] + a[2] - 1e-6 and a[1] < b[1] + b[3] - 1e-6 and b[1] < a[1] + a[3] - 1e-6

def rect_circle_dist(r, c):
    x, y, w, d = r
    dx = max(x - c[0], 0, c[0] - (x + w))
    dy = max(y - c[1], 0, c[1] - (y + d))
    return math.hypot(dx, dy)

def checks():
    res = []
    intake = (EQ['IF-1'][2], centre(EQ['IF-1'])[1])
    stack, tower, dc = centre(EQ['ST-1']), centre(EQ['CT-1']), centre(EQ['DC-1'])
    d = math.dist
    res.append(('engine intake -> exhaust stack (horizontal)', d(intake, stack), 4.6, 'ASHRAE 62.1 T5-1 combustion exhaust 15 ft'))
    res.append(('stack top above intake top', EQ['ST-1'][6] - EQ['IF-1'][6], 2.0, 'plume clears the louver'))
    res.append(('engine intake -> cooling tower', d(intake, tower), 7.6, 'ASHRAE 62.1 T5-1 cooling-tower exhaust 25 ft'))
    res.append(('exhaust stack -> cooling tower', d(stack, tower), 5.0, 'no hot exhaust into tower inlet'))
    res.append(('stack top above tower top', EQ['ST-1'][6] - EQ['CT-1'][6], 1.0, 'exhaust above tower plume'))
    res.append(('engine intake -> dry-cooler discharge', d(intake, dc), 2.0, 'vertical discharge, downwind (SE) of intake'))
    res.append(('stack -> BOP panel (nearest edge)', rect_circle_dist(footprint(EQ['BOP-R']), stack), 1.5, 'radiant heat on the panel'))
    tw = footprint(EQ['CT-1'])
    res.append(('tower -> roof edge', min(tw[0], tw[1], ROOF[0] - tw[0] - tw[2], ROOF[1] - tw[1] - tw[3]), 0.8, 'parapet, maintenance'))
    ring_r = TOWER_D / 2 + 1.0
    worst = min((rect_circle_dist(footprint(e), tower), t) for t, e in EQ.items() if t not in ('CT-1',) and e[7] > 0)
    res.append(('tower air-inlet ring: nearest equipment (%s)' % worst[1], worst[0], ring_r, '>= 1 m clear around louvres'))
    # equipment footprint inside another item's service zone, or footprints overlapping
    conflicts = []
    for ta, ea in EQ.items():
        for tb, eb in EQ.items():
            if ta >= tb:
                continue
            if overlap(footprint(ea), footprint(eb)) and {ta, tb} != {'HX-1', 'ST-1'}:     # stack sits on the HX
                conflicts.append('%s overlaps %s' % (ta, tb))
    for ta, ea in EQ.items():
        for z in zones(ea):
            if z[0] == 'ring':
                continue
            for tb, eb in EQ.items():
                if ta != tb and tb not in ('ST-1',) and overlap(z, footprint(eb)) and not (ta == 'HX-1' and tb == 'ST-1'):
                    conflicts.append('%s in service zone of %s' % (tb, ta))
            if z[0] < 0 or z[1] < 0 or z[0] + z[2] > ROOF[0] + 1e-6 or z[1] + z[3] > ROOF[1] + 1e-6:
                conflicts.append('service zone of %s leaves the roof' % ta)
    return res, conflicts

def weights():
    rows, M, Mx, My = [], 0.0, 0.0, 0.0
    for t, e in EQ.items():
        if e[7] <= 0:
            continue
        x, y, w, d = footprint(e)
        area = math.pi * w * w / 4 if e[1] == 'circle' else w * d
        cx, cy = centre(e)
        rows.append(dict(tag=t, label=e[0], kg=e[7], area=area, kg_m2=e[7] / area, cx=cx, cy=cy))
        M, Mx, My = M + e[7], Mx + e[7] * cx, My + e[7] * cy
    dist = sum(DISTRIBUTED.values())
    total = M + dist
    cgx = (Mx + dist * 5.0) / total
    cgy = (My + dist * 5.0) / total
    return rows, M, dist, total, cgx, cgy

COL = {'engine': '#f2a65a', 'exhaust': '#e4572e', 'chiller': '#4a90d9', 'tower': '#2bb3a3', 'tank': '#9b6fd1',
       'pump': '#8c8c8c', 'elec': '#e8c547', 'water': '#5cb85c', 'pipe': '#b0b0b0', 'access': '#ffffff', 'fire': '#d62728'}

def svg(res, conflicts, wt):
    S, X0, Y0 = 62.0, 70.0, 70.0
    W, H = X0 + ROOF[0] * S + 380, Y0 + ROOF[1] * S + 90
    def px(x, y):
        return X0 + x * S, Y0 + (ROOF[1] - y) * S
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Helvetica, Arial, sans-serif">' % (W, H, W, H),
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<text x="%d" y="28" font-size="18" font-weight="bold" fill="#222">GR180-CCHP roof plant - layout sketch (10 x 10 m roof over the hall)</text>' % X0,
         '<text x="%d" y="48" font-size="12" fill="#555">x east / y north, 1 grid = 1 m. Dimensions approximate; operating weights in kg. Generated by sim/hvac/roof_layout.py</text>' % X0]
    x0, y0 = px(0, ROOF[1])
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#f7f5ef" stroke="#333" stroke-width="2.5"/>' % (x0, y0, ROOF[0] * S, ROOF[1] * S))
    for i in range(1, 10):
        a, b = px(i, 0)
        c, d = px(0, i)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#ddd" stroke-width="1"/>' % (a, y0, a, b))
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#ddd" stroke-width="1"/>' % (x0, d, x0 + ROOF[0] * S, d))
        o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#999" text-anchor="middle">%d</text>' % (a, b + 14, i))
        o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#999" text-anchor="end">%d</text>' % (x0 - 4, d + 3, i))
    # walkway
    for wx, wy, ww, wd in ((1.2, 4.45, 8.0, 0.75), (1.6, 0.4, 0.9, 7.2)):
        a, b = px(wx, wy + wd)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#fff3c4" stroke="#d8b84a" stroke-dasharray="4 3" opacity="0.8"/>' % (a, b, ww * S, wd * S))
    a, b = px(7.6, 4.82)
    o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#9a7d1a" text-anchor="middle">walkway >= 0.75 m</text>' % (a, b + 3))
    # service zones
    for t, e in EQ.items():
        for z in zones(e):
            if z[0] == 'ring':
                cx, cy = px(*z[1])
                o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="#2bb3a3" stroke-dasharray="6 4" stroke-width="1.2"/>' % (cx, cy, z[2] * S))
            else:
                a, b = px(z[0], z[1] + z[3])
                o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#cfe3ff" fill-opacity="0.35" stroke="#7aa7e0" stroke-dasharray="4 3"/>' % (a, b, z[2] * S, z[3] * S))
    # hot duct + pipes (indicative)
    for ((xa, ya), (xb, yb)), col, wdt in ((((2.7, 8.05), (4.6, 8.05)), '#e4572e', 6), (((5.9, 8.05), (6.6, 7.3)), '#d9534f', 3),
                                         (((6.6, 7.3), (5.6, 5.8)), '#d9534f', 3), (((4.0, 5.2), (4.8, 3.47)), '#4a90d9', 3),
                                         (((5.6, 5.6), (9.5, 6.5)), '#4a90d9', 3), (((7.6, 1.4), (6.4, 0.85)), '#2bb3a3', 4),
                                         (((6.4, 0.85), (4.8, 2.5)), '#2bb3a3', 4), (((1.0, 7.6), (1.0, 6.2)), '#4a90d9', 2)):
        a, b = px(xa, ya)
        c, d = px(xb, yb)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%d" opacity="0.6" stroke-linecap="round"/>' % (a, b, c, d, col, wdt))
    # equipment
    for t, e in EQ.items():
        label, kind, x, y, w, d, h, kg, grp = e[:9]
        if kind == 'circle':
            cx, cy = px(x, y)
            o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="#333" stroke-width="1.5"/>' % (cx, cy, w / 2 * S, COL[grp]))
        else:
            a, b = px(x, y + d)
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="#333" stroke-width="1.5" rx="2"/>' % (a, b, w * S, d * S, COL[grp]))
        cx, cy = px(*centre(e))
        dy = {'ST-1': -22, 'HX-1': 16}.get(t, 0)
        o.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="bold" fill="#111" text-anchor="middle">%s</text>' % (cx, cy + dy - 1, t))
        if kg:
            o.append('<text x="%.1f" y="%.1f" font-size="9" fill="#222" text-anchor="middle">%d kg</text>' % (cx, cy + dy + 10, kg))
    # separation lines
    intake = (EQ['IF-1'][2], centre(EQ['IF-1'])[1])
    for (p, q, txt, f) in ((intake, centre(EQ['ST-1']), 'intake-stack', 0.45), (intake, centre(EQ['CT-1']), 'intake-tower', 0.17),
                           (centre(EQ['ST-1']), centre(EQ['CT-1']), 'stack-tower', 0.78)):
        a, b = px(*p)
        c, d = px(*q)
        dist = math.dist(p, q)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c0392b" stroke-width="1.3" stroke-dasharray="7 4"/>' % (a, b, c, d))
        o.append('<text x="%.1f" y="%.1f" font-size="11" fill="#c0392b" text-anchor="start" font-weight="bold">%s %.1f m</text>' % (
            a + f * (c - a) + 6, b + f * (d - b) - 6, txt, dist))
    # intake marker
    a, b = px(*intake)
    o.append('<path d="M %.1f %.1f l -16 -9 l 0 18 z" fill="#1f77b4"/>' % (a - 2, b))
    o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#1f77b4" text-anchor="end">air in</text>' % (a - 20, b - 12))
    # CG
    _, _, _, total, cgx, cgy = wt
    a, b = px(cgx, cgy)
    o.append('<circle cx="%.1f" cy="%.1f" r="7" fill="none" stroke="#000" stroke-width="2"/><line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000"/><line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000"/>' % (a, b, a - 10, b, a + 10, b, a, b - 10, a, b + 10))
    o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#000" text-anchor="end">CG (%.1f, %.1f) total %.1f t</text>' % (a - 10, b + 16, cgx, cgy, total / 1e3))
    # north + wind
    nx, ny = X0 + ROOF[0] * S + 40, Y0 + 40
    o.append('<path d="M %.1f %.1f l -9 22 l 9 -6 l 9 6 z" fill="#333"/><text x="%.1f" y="%.1f" font-size="13" font-weight="bold" text-anchor="middle">N</text>' % (nx, ny - 22, nx, ny - 26))
    o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#555" stroke-width="3" marker-end="url(#ar)"/>' % (nx + 30, ny - 25, nx + 70, ny + 15))
    o.append('<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#555"/></marker></defs>')
    o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#555">prevailing wind NW (ASSUMED)</text>' % (nx + 20, ny + 32))
    # legend + checks
    lx, ly = X0 + ROOF[0] * S + 20, Y0 + 90
    o.append('<text x="%.1f" y="%.1f" font-size="12" font-weight="bold">Equipment (operating kg)</text>' % (lx, ly))
    ly += 6
    for t, e in EQ.items():
        if e[7] <= 0 and t != 'HATCH':
            continue
        ly += 15
        o.append('<rect x="%.1f" y="%.1f" width="10" height="10" fill="%s" stroke="#333"/>' % (lx, ly - 9, COL[e[8]]))
        o.append('<text x="%.1f" y="%.1f" font-size="9.5" fill="#222">%s - %s</text>' % (lx + 15, ly, t, e[0][:48]))
    ly += 22
    o.append('<text x="%.1f" y="%.1f" font-size="12" font-weight="bold">Separation checks</text>' % (lx, ly))
    for name, val, req, _ in res:
        ly += 14
        ok = val >= req - 1e-6
        o.append('<text x="%.1f" y="%.1f" font-size="9.5" fill="%s">%s %s: %.1f m (min %.1f)</text>' % (
            lx, ly, '#1e7d32' if ok else '#c0392b', 'OK ' if ok else 'NO ', name[:38], val, req))
    ly += 18
    o.append('<text x="%.1f" y="%.1f" font-size="9.5" fill="#222">dashed blue = service zones; teal ring = tower air inlet</text>' % (lx, ly))
    ly += 13
    o.append('<text x="%.1f" y="%.1f" font-size="9.5" fill="#222">layout conflicts: %s</text>' % (lx, ly, 'none' if not conflicts else len(conflicts)))
    # scale bar
    a, b = px(0, 0)
    o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000" stroke-width="3"/><text x="%.1f" y="%.1f" font-size="11">2 m</text>' % (a, b + 34, a + 2 * S, b + 34, a + 2 * S + 6, b + 38))
    o.append('<text x="%.1f" y="%.1f" font-size="10" fill="#555">Hall below: 10 x 10 x 2.5 m. Electrical room, inverter, battery, ECU, HMI, RO unit and DHW tank are INDOORS (not on this roof).</text>' % (a, b + 58))
    o.append('</svg>')
    return '\n'.join(o)

def alternatives(rows, dist_total):
    """Roof weight of lighter options (user: RC building; asked what drives ~7 t)."""
    kg = {r['tag']: r['kg'] for r in rows}
    base = sum(kg.values()) + dist_total
    light = {'TK-1 500 -> 300 L': -220, 'LLH-1 buffer -> DN65 hydraulic separator': -200,
             'CW piping PE100 instead of 316L/steel spools': -50}
    single = dict(light)
    single['CH-2 SC5 not installed'] = -kg['CH-2']
    single['P-2B, P-4B and CH-2 branch piping'] = -80
    if RES and 'recheck' in RES:
        single['tower %d ton instead of %d ton' % (RES['recheck']['tower_single']['S'], RES['tower']['sel']['S'])] = \
            RES['recheck']['tower_single_kg'] - kg['CT-1']
    return dict(base=base, light=dict(items=light, total=base + sum(light.values())),
                single=dict(items=single, total=base + sum(single.values())))

def main():
    res, conflicts = checks()
    wt = weights()
    rows, M, dist, total, cgx, cgy = wt
    print('ROOF LAYOUT %.0f x %.0f m' % ROOF)
    print('  %-6s %-58s %6s %6s %7s %10s' % ('tag', 'item', 'kg', 'm2', 'kg/m2', 'centre'))
    for r in rows:
        print('  %-6s %-58s %6d %6.2f %7.0f (%4.1f,%4.1f)' % (r['tag'], r['label'][:58], r['kg'], r['area'], r['kg_m2'], r['cx'], r['cy']))
    for k, v in DISTRIBUTED.items():
        print('  %-65s %6d  (distributed)' % (k, v))
    print('  equipment %.0f kg + distributed %.0f kg = %.1f t; average %.0f kg/m2 over the roof; CG (%.2f, %.2f) m' % (
        M, dist, total / 1e3, total / (ROOF[0] * ROOF[1]), cgx, cgy))
    alt = alternatives(rows, dist)
    print('  lighter options: pair + light items %.1f t (%s); single SC10 + light items %.1f t' % (
        alt['light']['total'] / 1e3, ', '.join('%s %+d' % kv for kv in alt['light']['items'].items()), alt['single']['total'] / 1e3))
    print('\nSEPARATION / CLEARANCE CHECKS')
    for name, val, req, ref in res:
        print('  %-3s %-48s %5.1f m (min %.1f)  %s' % ('OK' if val >= req - 1e-6 else 'NO', name, val, req, ref))
    print('  layout conflicts: %s' % ('none' if not conflicts else '; '.join(conflicts)))
    path = os.path.join(ROOT, 'docs', 'hvac', 'roof_layout.svg')
    with open(path, 'w') as fh:
        fh.write(svg(res, conflicts, wt))
    with open(os.path.join(HERE, 'roof_layout.json'), 'w') as fh:
        json.dump(dict(equipment={t: dict(label=e[0], kind=e[1], x=e[2], y=e[3], w=e[4], d=e[5], h=e[6], kg=e[7], group=e[8])
                                  for t, e in EQ.items()}, weights=rows, distributed=DISTRIBUTED, total_kg=total,
                       cg=(cgx, cgy), checks=[dict(name=n, value=v, min=q, ref=r) for n, v, q, r in res], alternatives=alt,
                       conflicts=conflicts), fh, indent=1)
    print('written %s' % os.path.relpath(path, os.getcwd()))

if __name__ == '__main__':
    main()
