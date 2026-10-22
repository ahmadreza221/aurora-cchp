"""GR180-CCHP roof plant: equipment envelopes (with nozzles), piping routes, fire suppression, hall fan coils.

All positions are in the ROOF frame (m). Equipment envelopes follow datasheet-class dimensions (Yazaki SC10/SC5 class
chillers, 60-ton FRP round tower, ...); purchased items are envelopes with their connection points. EP-1 is a
placeholder (engine package session, docs/06 section 3). Configuration = recommended option of
docs/hvac/09_recheck_insulated_hall.md: SC10 + SC5 pair with the light items (TK-1 300 L, LLH-1 hydraulic
separator, PE100 condenser-water piping).
"""
import math

import FreeCAD as App
import Part

from plant_lib import (V, M, box, cyl, cylp, loft_rect_circle, i_beam, angle_post, Route, build_route, unit,
                       MATERIALS, OD_STEEL)

DUN = 0.155          # dunnage top (HEA140 on 22 mm EPDM bearing pads)
PAD = 0.025          # elastomer pad under equipment
SPR = 0.095          # spring isolator (25 mm deflection class) under skids / tower
EU = 'European'

C_EQ = (0.62, 0.66, 0.72)
C_CH = (0.30, 0.52, 0.80)
C_TW = (0.20, 0.65, 0.60)
C_EXH = (0.85, 0.45, 0.30)
C_TANK = (0.60, 0.45, 0.80)
C_PUMP = (0.20, 0.35, 0.70)
C_ELEC = (0.90, 0.78, 0.25)
C_FIRE = (0.85, 0.12, 0.12)
C_STEEL = (0.45, 0.47, 0.50)
C_REF = (0.85, 0.83, 0.78)


def rnz(m, tag, name, c, R, th, z, dn, medium, stub=0.10, mat='CS40'):
    """radial nozzle on a vertical cylinder (centre c=(x,y), radius R) at angle th (deg from +x, CCW)"""
    a = math.radians(th)
    d = (math.cos(a), math.sin(a), 0.0)
    p = (c[0] + R * d[0], c[1] + R * d[1], z)
    return m.nozzle(tag, name, p, d, dn, medium, stub=stub, mat=mat)


def dunnage(m, owner, x0, y0, x1, y1, axis='x', n=2, inset=0.10, ext=0.15):
    """two (or n) HEA140 beams under a footprint, on EPDM bearing pads (pads at beam ends and mid)."""
    beams = []
    if axis == 'x':
        ys = [y0 + inset + (y1 - y0 - 2 * inset) * k / (n - 1) for k in range(n)]
        for y in ys:
            beams.append(((x0 - ext, y, 0.022), (x1 + ext, y, 0.022)))
    else:
        xs = [x0 + inset + (x1 - x0 - 2 * inset) * k / (n - 1) for k in range(n)]
        for x in xs:
            beams.append(((x, y0 - ext, 0.022), (x, y1 + ext, 0.022)))
    L = 0.0
    npads = 0
    for a, b in beams:
        m.add('DUN-' + owner, 'DUN-%s beam' % owner, i_beam(a, b), 'struct', C_STEEL, connects={owner}, group='dunnage')
        L += math.dist(a, b)
        npts = max(2, int(math.ceil(math.dist(a, b) / 1.5)) + 1)
        for k in range(npts):
            t = k / (npts - 1)
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            m.add('DUN-' + owner, 'DUN-%s pad' % owner, box(px - 0.10, py - 0.10, 0.0, 0.20, 0.20, 0.022), 'struct', (0.1, 0.1, 0.1),
                  connects={owner}, group='dunnage')
            npads += 1
    m.dunnage_log.append((owner, L, npads))
    return beams


def mounts(m, owner, pts, kind='spring'):
    h = SPR if kind == 'spring' else PAD
    for (x, y) in pts:
        if kind == 'spring':
            sh = cyl(x, y, DUN, 0.13, h)
        else:
            sh = box(x - 0.08, y - 0.08, DUN, 0.16, 0.16, h)
        m.add(owner, '%s %s mount' % (owner, kind), sh, 'equip', (0.15, 0.15, 0.15) if kind != 'spring' else (0.9, 0.5, 0.1),
              connects={'DUN-' + owner})
    m.mount_log.append((owner, kind, len(pts)))


# ================================================================================================ equipment
def equipment(m):
    m.dunnage_log, m.mount_log = [], []
    B_PAD = DUN + PAD           # 0.18
    B_SPR = DUN + SPR           # 0.25

    # ---------------------------------------------------------------- IF-1 intake module
    t = 'IF-1'
    x0, y0, z0 = 0.40, 7.60, B_PAD
    m.add(t, 'IF-1 casing', box(x0 + 0.30, y0, z0, 0.55, 0.90, 1.40), 'equip', C_EQ)
    louver = box(x0, y0, z0, 0.30, 0.90, 1.40)
    for k in range(7):
        louver = louver.cut(box(x0 - 0.01, y0 + 0.05, z0 + 0.12 + k * 0.18, 0.12, 0.80, 0.07))
    m.add(t, 'IF-1 acoustic louver', louver, 'equip', (0.55, 0.58, 0.62))
    m.add(t, 'IF-1 filter door', box(x0 + 0.33, y0 - 0.015, z0 + 0.20, 0.45, 0.015, 1.00), 'equip', (0.4, 0.4, 0.45))
    m.add(t, 'IF-1 flex DN200', cylp((1.25, 7.85, 0.60), 0.25, (1, 0, 0), 0.05), 'equip', (0.15, 0.15, 0.15), connects={'EP-1'})
    m.nozzle(t, 'chw_in', (0.95, 7.60, 0.55), (0, -1, 0), 25, 'CHW supply 7 C', stub=0.10)
    m.nozzle(t, 'chw_out', (0.95, 7.60, 0.95), (0, -1, 0), 25, 'CHW return 12 C', stub=0.10)
    m.nozzle(t, 'cond', (0.65, 7.60, 0.28), (0, -1, 0), 25, 'condensate', stub=0.08, mat='PVC', flange=False)
    m.item(t, 'engine air intake module: acoustic rain louver, lined plenum, G4 + F8 filters, CHW coil CC-1 (10 rows, '
              '21 kW to 12 C), droplet eliminator, SS304 drain pan with LSH-221, DN200 outlet + flexible connector',
           'buy', 'galvanised + powder-coated casing, Cu/Cu or epoxy-coated Al-fin coil, 50 mm acoustic lining',
           '0.37 m3/s, coil 0.40 x 0.40 m face, 21 kW', 'Trox / Gebhardt (DE) casing; Lu-Ve (IT) or domestic coil makers; Camfil (SE) filters',
           150, 'intake', notes='CC-1 coil + filters inside; PDT-222/223, TE-221/222, MT-501 ports')
    m.footprints[t] = (0.40, 7.60, 1.25, 8.50)
    dunnage(m, t, 0.40, 7.60, 1.25, 8.50, axis='y')
    mounts(m, t, [(0.50, 7.70), (1.15, 7.70), (0.50, 8.40), (1.15, 8.40)], 'pad')
    m.zone(t, 0.40, 7.00, 1.25, 7.60, label='filter door (S)')

    # ---------------------------------------------------------------- EP-1 placeholder (engine package session)
    t = 'EP-1'
    m.add(t, 'EP-1 placeholder', box(1.30, 7.60, 0.0, 1.40, 0.90, 1.30), 'equip', (0.95, 0.60, 0.20))
    m.nozzle(t, 'air_in', (1.30, 7.85, 0.60), (-1, 0, 0), 200, 'intake air from IF-1', stub=0.0, flange=False)
    m.nozzle(t, 'exh_out', (2.70, 8.25, 0.80), (1, 0, 0), 250, 'exhaust 262 C after recuperator', stub=0.0, flange=False)
    m.nozzle(t, 'gas_in', (1.60, 7.60, 0.30), (0, -1, 0), 20, 'natural gas 4 bar', stub=0.10, mat='GAS')
    m.nozzle(t, 'gly_sup', (2.40, 7.60, 0.25), (0, -1, 0), 25, 'glycol supply to engine (cold)', stub=0.10, mat='SS304')
    m.nozzle(t, 'gly_ret', (2.40, 7.60, 0.40), (0, -1, 0), 25, 'glycol return from engine (hot)', stub=0.10, mat='SS304')
    m.nozzle(t, 'fire', (2.00, 8.05, 1.30), (0, 0, 1), 15, 'FK-5-1-12 discharge FZ1', stub=0.05, mat='SS316F')
    m.item(t, 'engine package GR180 + FPT + PMG + recuperator + enclosure (PLACEHOLDER box; model by engine-package '
              'session, cad_out/engine/)', 'make', 'see docs/06_master_design.md section 4 (E1-E5)', '1.40 x 0.90 x 1.30 m envelope',
           'engine package session', 450, 'engine', notes='not counted in plant BOM mass; interfaces per docs/06 section 3')
    m.footprints[t] = (1.30, 7.60, 2.70, 8.50)
    m.zone(t, 1.30, 8.50, 2.70, 9.50, label='package doors N')
    m.zone(t, 1.30, 6.60, 2.70, 7.60, label='package doors S')

    # ---------------------------------------------------------------- D-101 diverter
    t = 'D-101'
    m.add(t, 'D-101 body', box(4.64, 8.04, 0.59, 0.42, 0.42, 0.42), 'equip', C_EXH)
    m.add(t, 'D-101 actuator', box(4.73, 7.82, 0.68, 0.24, 0.22, 0.24), 'equip', (0.2, 0.2, 0.2))
    for (x, y) in ((4.66, 8.06), (5.00, 8.06), (4.66, 8.40), (5.00, 8.40)):
        m.add(t, 'D-101 leg', box(x, y, DUN, 0.04, 0.04, 0.59 - DUN), 'equip', C_STEEL)
    m.nozzle(t, 'in', (4.64, 8.25, 0.80), (-1, 0, 0), 250, 'exhaust in', stub=0.0, flange=False)
    m.nozzle(t, 'hx', (5.06, 8.25, 0.80), (1, 0, 0), 250, 'to HX-1', stub=0.04, flange=False)
    m.nozzle(t, 'byp', (4.85, 8.25, 1.01), (0, 0, 1), 250, 'to bypass', stub=0.0, flange=False)
    m.item(t, 'exhaust diverter damper, 3-way single blade, DN250, 650 C, leakage <= 1 %, 24 VAC modulating actuator '
              'with spring return to BYPASS <= 15 s, dual limit switches (ZSO-101), heat-break shaft',
           'buy', 'body 316L fabricated; actuator Belimo-class spring-return', 'DN250 / 650 C / ZC-101 2-10 V',
           'body: domestic stainless fabricator; actuator Belimo (CH), Siemens (DE)', 60, 'exhaust')

    # ---------------------------------------------------------------- HX-1 + stack frame + PSV
    t = 'HX-1'
    m.add(t, 'HX-1 casing', box(5.10, 7.60, 0.45, 0.80, 0.90, 1.43), 'equip', C_EXH)
    m.add(t, 'HX-1 outlet transition', loft_rect_circle(5.10, 7.60, 1.88, 0.80, 0.90, 5.50, 8.25, 2.25, 0.273), 'equip', C_EXH)
    m.add(t, 'HX-1 inspection door', box(5.90, 7.80, 1.10, 0.02, 0.50, 0.60), 'equip', (0.3, 0.3, 0.3))
    for (x, y) in ((5.10, 7.60), (5.84, 7.60), (5.10, 8.44), (5.84, 8.44)):
        m.add(t, 'HX-1 leg', box(x, y, DUN, 0.06, 0.06, 0.45 - DUN), 'equip', C_STEEL)
    # stack support frame (owned by HX-1)
    for (x, y) in ((5.02, 7.51), (5.92, 7.51), (5.02, 8.53), (5.92, 8.53)):
        m.add(t, 'stack frame post', box(x, y, DUN, 0.06, 0.06, 2.91 - DUN), 'equip', C_STEEL)
    m.add(t, 'stack collar S', box(5.02, 7.51, 2.85, 0.96, 0.06, 0.06), 'equip', C_STEEL)
    m.add(t, 'stack collar N', box(5.02, 8.53, 2.85, 0.96, 0.06, 0.06), 'equip', C_STEEL)
    m.add(t, 'stack strut S', box(5.47, 7.57, 2.85, 0.06, 8.25 - 0.26 - 7.57, 0.06), 'equip', C_STEEL)
    m.add(t, 'stack strut N', box(5.47, 8.51, 2.85, 0.06, 0.02, 0.06), 'equip', C_STEEL)
    m.add(t, 'PSV-111', cylp((5.80, 7.62, 1.88), 0.07, (0, 0, 1), 0.22), 'equip', (0.8, 0.1, 0.1))
    m.nozzle(t, 'gas_in', (5.10, 8.25, 0.80), (-1, 0, 0), 250, 'exhaust in', stub=0.0, flange=False)
    m.nozzle(t, 'gas_out', (5.50, 8.25, 2.25), (0, 0, 1), 250, 'exhaust to stack', stub=0.0, flange=False)
    m.nozzle(t, 'hw_sup', (5.70, 7.60, 1.15), (0, -1, 0), 50, 'HW supply 90 C', stub=0.15)
    m.nozzle(t, 'hw_ret', (5.30, 7.60, 1.80), (0, -1, 0), 50, 'HW return 83 C', stub=0.15)
    m.nozzle(t, 'drain', (5.90, 8.05, 0.55), (1, 0, 0), 25, 'start-up condensate', stub=0.05, mat='SS316D')
    m.item(t, 'exhaust/water economiser, spiral finned-tube, 8 tubes x 15 rows x 0.6 m, 42 m2, vertical up-flow, headers '
              'outside gas, inspection door, condensate drain, PSV-111 DN20 5.5 bar on outlet header; + stack support frame',
           'buy', 'all 316L, tube 25.4 x 1.65, fin 11 x 0.8 mm 5 fpi HF-welded; casing 100 mm rock wool + Al',
           '69 kW, gas 400 C design / water PN10 120 C', 'domestic boiler/HX makers (316L finned tube imported); Kelvion (DE), Bosal (BE)',
           349 + 80, 'exhaust', notes='thermal design sim/hvac/hvac_design.py section [2]; frame 80 kg')
    m.footprints[t] = (4.60, 7.50, 6.00, 8.60)
    dunnage(m, t, 4.60, 7.55, 6.00, 8.55, axis='x', n=3)
    m.zone(t, 5.10, 8.60, 5.90, 9.30, label='HX door / tube access N')
    m.zone(t, 5.10, 6.80, 5.90, 7.45, label='HX headers S')

    # ---------------------------------------------------------------- ST-1 stack (tee, silencer SL-101, top)
    t = 'ST-1'
    m.add(t, 'ST-1 tee', cyl(5.50, 8.25, 2.25, 0.37, 0.50), 'equip', C_EXH)
    m.add(t, 'SL-101 cone in', Part.makeCone(185, 250, 100, V(5.50, 8.25, 2.75)), 'equip', C_EXH)
    m.add(t, 'SL-101 silencer', cyl(5.50, 8.25, 2.85, 0.50, 1.10), 'equip', (0.75, 0.40, 0.28))
    m.add(t, 'SL-101 cone out', Part.makeCone(250, 185, 100, V(5.50, 8.25, 3.95)), 'equip', C_EXH)
    m.add(t, 'ST-1 top', cyl(5.50, 8.25, 4.05, 0.37, 0.15), 'equip', C_EXH)
    m.add(t, 'ST-1 sampling port', cylp((5.685, 8.25, 2.70), 0.04, (1, 0, 0), 0.08), 'equip', (0.3, 0.3, 0.3))
    m.nozzle(t, 'byp_in', (5.315, 8.25, 2.50), (-1, 0, 0), 250, 'bypass in', stub=0.115, mat='DUCT', flange=False)
    m.item(t, 'stack DN250 double wall with bypass tee, sampling port (TE-103), drain, top +4.2 m; incl. absorptive '
              'straight-through silencer SL-101 (1.2 m, IL 15-20 dB(A), dp <= 50 Pa)', 'buy',
           'inner 316L, 50 mm insulation, outer 1.4301; silencer: perforated 316L + basalt wool 650 C',
           'DN250, +4.2 m above roof', 'Jeremias, Schiedel (DE), Kemper (DE); domestic stainless fabricators', 140, 'exhaust')

    # ---------------------------------------------------------------- NP-1 neutraliser pot
    t = 'NP-1'
    m.add(t, 'NP-1 pot', cyl(6.40, 8.05, 0.0, 0.25, 0.40), 'equip', (0.5, 0.5, 0.55))
    m.nozzle(t, 'in', (6.40, 8.05, 0.40), (0, 0, 1), 25, 'condensate in', stub=0.03, mat='SS316D', flange=False)
    m.item(t, 'condensate neutraliser pot (MgO / limestone granulate), to roof drain', 'buy', 'PP/316L body', '10 L',
           'Neutrakon (DE) or domestic', 15, 'exhaust')

    # ---------------------------------------------------------------- LLH-1 hydraulic separator (light option)
    t = 'LLH-1'
    c = (6.60, 7.30)
    m.add(t, 'LLH-1 body (insulated)', cyl(c[0], c[1], 0.40, 0.32, 1.00), 'equip', C_TANK)
    for (dx, dy) in ((-0.10, -0.10), (0.10, -0.10), (-0.10, 0.10), (0.10, 0.10)):
        m.add(t, 'LLH-1 leg', box(c[0] + dx - 0.02, c[1] + dy - 0.02, B_PAD, 0.04, 0.04, 0.40 - B_PAD), 'equip', C_STEEL)
    m.nozzle(t, 'pri_in', (6.44, 7.30, 1.15), (-1, 0, 0), 50, 'HW from HX-1', stub=0.15)
    m.nozzle(t, 'pri_out', (6.44, 7.30, 0.55), (-1, 0, 0), 50, 'HW to P-1', stub=0.15)
    m.nozzle(t, 'sec_out', (6.60, 7.14, 1.15), (0, -1, 0), 65, 'HW secondary supply', stub=0.15)
    m.nozzle(t, 'sec_in', (6.60, 7.14, 0.75), (0, -1, 0), 65, 'HW secondary return', stub=0.15)
    m.nozzle(t, 'exp', (6.76, 7.30, 0.55), (1, 0, 0), 20, 'expansion / fill', stub=0.10)
    m.item(t, 'hydraulic separator (low-loss header) DN65 with integral air vent, dirt leg and drain (light option; '
              'replaces 200 L buffer)', 'buy', 'steel PN10, 50 mm stone wool + Al', 'DN65 / 13 m3/h / body DN200 x 1.0 m',
           'Reflex, Sinusverteiler (DE), Caleffi (IT); domestic', 45, 'hw')
    m.footprints[t] = (6.40, 7.10, 6.80, 7.50)
    dunnage(m, t, 6.35, 7.10, 6.85, 7.50, axis='x')

    # ---------------------------------------------------------------- ET-1 expansion set (vessel + intermediate)
    t = 'ET-1'
    m.add(t, 'ET-1 35 L vessel', cyl(7.25, 7.30, B_PAD, 0.36, 0.52), 'equip', (0.8, 0.15, 0.15))
    m.add(t, 'ET-1 intermediate vessel 20 L', cyl(7.25, 6.88, B_PAD, 0.27, 0.48), 'equip', (0.5, 0.5, 0.55))
    m.add(t, 'ET-1 link', cylp((7.25, 7.12, 0.30), 0.027, (0, -1, 0), 0.105), 'equip', (0.5, 0.5, 0.55))
    m.nozzle(t, 'conn', (7.25, 7.035, 0.55), (0, 1, 0), 20, 'expansion line', stub=0.0)
    m.item(t, 'HW expansion set: diaphragm vessel 35 L / 10 bar + 20 L intermediate (cooling) vessel, cap valve, drain',
           'buy', 'EN 13831', '35 L + 20 L', 'Reflex (N 35 + V 20), Zilmet (IT), Flamco (NL), Varem (IT)', 45, 'hw')
    m.footprints[t] = (7.05, 6.70, 7.45, 7.50)
    dunnage(m, t, 7.05, 6.70, 7.45, 7.50, axis='y')

    # ---------------------------------------------------------------- PS-1 hydronic skid frame (pumps are inline on routes)
    t = 'PS-1'
    zf = B_SPR
    for yb in (5.45, 6.25):
        m.add(t, 'PS-1 frame x-beam', box(2.80, yb - 0.03, zf, 2.80, 0.06, 0.12), 'equip', C_STEEL)
    for xb in (2.85, 3.70, 4.65, 5.55):
        m.add(t, 'PS-1 frame y-beam', box(xb - 0.03, 5.45, zf, 0.06, 0.80, 0.12), 'equip', C_STEEL)
    m.add(t, 'ET-2 25 L', cyl(3.45, 5.90, zf + 0.12, 0.30, 0.42), 'equip', (0.8, 0.15, 0.15))
    m.add(t, 'JB-PS1 junction box', box(2.85, 5.50, zf + 0.12, 0.20, 0.10, 0.40), 'equip', C_ELEC)
    m.add(t, 'FU-1 fill unit (BA + meter + pot)', box(4.10, 5.88, zf + 0.12, 0.40, 0.20, 0.30), 'equip', (0.3, 0.55, 0.3))
    m.nozzle(t, 'et2', (3.45, 5.75, 0.55), (0, -1, 0), 20, 'ET-2 connection', stub=0.10)
    m.item(t, 'hydronic pump skid PS-1: galvanised frame on spring isolators, carrying P-2A/B, P-5A/B, FT-211, HM-2/4, '
              'AS-2, ET-2 25 L, closed-loop fill unit FU-1 (BA backflow preventer, FQ-410, XV-410, dosing pot), JB-PS1',
           'make', 'S235 galvanised UPN120 frame, prefabricated and pressure-tested', '2.8 x 1.1 m',
           'domestic HVAC skid fabricator', 180, 'pumps', notes='pumps, valves and pipes listed separately')
    m.footprints[t] = (2.80, 5.20, 5.60, 6.30)
    dunnage(m, t, 2.80, 5.45, 5.60, 6.25, axis='x', inset=0.0, ext=0.02)
    mounts(m, t, [(2.85, 5.45), (3.70, 5.45), (4.65, 5.45), (5.55, 5.45), (2.85, 6.25), (3.70, 6.25), (4.65, 6.25), (5.55, 6.25)], 'spring')
    m.zone(t, 2.80, 6.32, 5.60, 7.00, z0=0.40, label='skid access N')

    # ---------------------------------------------------------------- PS-3 changeover + DHW/heating module
    t = 'PS-3'
    m.add(t, 'PS-3 module', box(5.75, 5.30, B_PAD, 0.60, 0.40, 1.20), 'equip', (0.35, 0.55, 0.75))
    m.nozzle(t, 'hw_in', (6.25, 5.70, 1.15), (0, 1, 0), 25, 'HW from header', stub=0.10)
    m.nozzle(t, 'hw_out', (6.05, 5.70, 0.75), (0, 1, 0), 25, 'HW to return header', stub=0.10)
    m.nozzle(t, 'chw_tk', (6.30, 5.30, 0.30), (0, -1, 0), 50, 'CHW secondary from TK-1', stub=0.10)
    m.nozzle(t, 'chwr_tk', (6.10, 5.30, 0.30), (0, -1, 0), 50, 'CHW secondary return to TK-1', stub=0.10)
    m.nozzle(t, 'chw_p5', (5.75, 5.50, 0.95), (-1, 0, 0), 50, 'CHW to P-5', stub=0.10)
    m.nozzle(t, 'chwr_hdr', (5.75, 5.50, 0.55), (-1, 0, 0), 50, 'CHW return from header', stub=0.10)
    m.nozzle(t, 'dhw_s', (6.35, 5.62, 0.50), (1, 0, 0), 25, 'DHW charging supply', stub=0.10)
    m.nozzle(t, 'dhw_r', (6.35, 5.42, 0.30), (1, 0, 0), 25, 'DHW charging return', stub=0.10)
    m.item(t, 'changeover + DHW/heating module PS-3 (prefabricated): P-3 (ECM 1.3 m3/h), TV-131 3-way limiter, V-PRI DHW '
              'priority, HX-3 heating PHE 15 kW, V-CO1/V-CO2 summer/winter 3-way DN50 with end switches, HM-3 port',
           'buy', 'insulated sheet housing, SS316 brazed PHE, Belimo-class valves', '0.60 x 0.40 x 1.20 m',
           'domestic HVAC module builders; components Grundfos (DK), Belimo (CH), SWEP (SE)', 120, 'pumps')
    m.footprints[t] = (5.75, 5.30, 6.35, 5.70)
    dunnage(m, t, 5.75, 5.30, 6.35, 5.70, axis='y', inset=0.08, ext=0.0)
    mounts(m, t, [(5.82, 5.38), (6.28, 5.38), (5.82, 5.62), (6.28, 5.62)], 'pad')

    # ---------------------------------------------------------------- chillers
    for t, x0, y0, w, d, h, kg, dn_h, dn_c, dn_w, label in (
            ('CH-1', 4.40, 2.50, 0.76, 0.97, 1.90, 560, 50, 50, 80, 'SC10 class 35 kW'),
            ('CH-2', 2.80, 2.60, 0.594, 0.744, 1.76, 420, 40, 40, 65, 'SC5 class 17.6 kW')):
        z0 = B_PAD
        m.add(t, '%s cabinet' % t, box(x0, y0, z0, w, d, h), 'equip', C_CH)
        m.add(t, '%s control panel' % t, box(x0 + 0.08, y0 - 0.04, z0 + 0.9, w - 0.16, 0.04, 0.6), 'equip', (0.9, 0.9, 0.92))
        yn = y0 + d
        xa, xb = (4.52, 4.80) if t == 'CH-1' else (2.92, 3.18)
        xc = 5.05 if t == 'CH-1' else 3.30
        zh = 1.60 if t == 'CH-1' else 1.45
        m.nozzle(t, 'hw_in', (xa, yn, zh), (0, 1, 0), dn_h, 'HW in 88 C', stub=0.13)
        m.nozzle(t, 'hw_out', (xb, yn, zh), (0, 1, 0), dn_h, 'HW out 83 C', stub=0.13)
        m.nozzle(t, 'chw_in', (xc, yn, 0.70 if t == 'CH-1' else 0.65), (0, 1, 0), dn_c, 'CHW in 12 C', stub=0.13)
        m.nozzle(t, 'chw_out', (xc, yn, 1.10 if t == 'CH-1' else 1.00), (0, 1, 0), dn_c, 'CHW out 7 C', stub=0.13)
        xe = x0 + w
        m.nozzle(t, 'cw_in', (xe, 2.85, 0.45 if t == 'CH-1' else 0.75), (1, 0, 0), dn_w, 'CW in 32 C', stub=0.10, mat='CS40')
        m.nozzle(t, 'cw_out', (xe, 3.10, 1.55 if t == 'CH-1' else 1.40), (1, 0, 0), dn_w, 'CW out 35.4 C', stub=0.10, mat='CS40')
        m.item(t, 'single-effect LiBr absorption chiller, hot-water driven, outdoor, %s; Modbus (generator T, '
                  'crystallisation margin, dilution state); rev B purchase spec: dp HW <= 50 / CHW <= 40 / CW <= 50 kPa, '
                  'CW 80-85 %% flow allowed' % label, 'buy', 'factory package', label,
               'Yazaki WFC-SC10/SC5 (JP, reference); EAW Wegracal SE 30/15 (DE); Thermax (IN); Broad, Shuangliang (CN)',
               kg, 'chillers', notes='nozzle sizes per final datasheet; reducers at nozzles counted in fittings')
        m.footprints[t] = (x0, y0, x0 + w, y0 + d)
        dunnage(m, t, x0, y0, x0 + w, y0 + d, axis='y', inset=0.08)
        mounts(m, t, [(x0 + 0.08, y0 + 0.10), (x0 + w - 0.08, y0 + 0.10), (x0 + 0.08, y0 + d - 0.10), (x0 + w - 0.08, y0 + d - 0.10)], 'pad')
        m.zone(t, x0, y0 - 0.80, x0 + w, y0, label='front panel / access S')
        m.zone(t, x0 - 0.60, y0, x0, y0 + d, label='tube cleaning W')

    # ---------------------------------------------------------------- TK-1 CHW buffer 300 L (light)
    t = 'TK-1'
    c = (6.40, 3.60)
    R = 0.325
    m.add(t, 'TK-1 vessel (insulated)', cyl(c[0], c[1], 0.25, 2 * R, 1.38), 'equip', C_TANK)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        m.add(t, 'TK-1 leg', box(c[0] + 0.20 * math.cos(a) - 0.03, c[1] + 0.20 * math.sin(a) - 0.03, B_PAD, 0.06, 0.06, 0.25 - B_PAD),
              'equip', C_STEEL)
    rnz(m, t, 'p1_in', c, R, 180, 1.35, 50, 'CHW from CH-1 evaporator', stub=0.15)
    rnz(m, t, 'p2_in', c, R, 180, 1.10, 40, 'CHW from CH-2 evaporator', stub=0.15)
    rnz(m, t, 'p1_out', c, R, 180, 0.40, 50, 'CHW to P-4A', stub=0.15)
    rnz(m, t, 'p2_out', c, R, 180, 0.65, 40, 'CHW to P-4B', stub=0.15)
    rnz(m, t, 's_out', c, R, 108, 0.95, 50, 'CHW secondary supply', stub=0.12)
    rnz(m, t, 's_in', c, R, 157, 0.55, 50, 'CHW secondary return', stub=0.12)
    m.item(t, 'CHW buffer / decoupler 300 L (light option; base 500 L), 6 nozzles, TE-211/212/214 wells, vent, drain',
           'buy', 'steel PN10, 50 mm elastomeric + Al', '300 L, Ø0.55 m', 'Reflex (DE), Caleffi (IT); domestic pressure-vessel makers', 430, 'chw')
    m.footprints[t] = (c[0] - R, c[1] - R, c[0] + R, c[1] + R)
    dunnage(m, t, c[0] - R, c[1] - R, c[0] + R, c[1] + R, axis='x', inset=0.10)

    # ---------------------------------------------------------------- CT-1 cooling tower
    t = 'CT-1'
    c = (8.25, 1.95)
    R = 0.94
    z0 = B_SPR
    m.add(t, 'CT-1 basin', cyl(c[0], c[1], z0, 2 * R, 0.55), 'equip', (0.15, 0.50, 0.48))
    m.add(t, 'CT-1 louvre band', cyl(c[0], c[1], z0 + 0.55, 2 * R - 0.04, 0.45), 'equip', (0.30, 0.70, 0.65))
    m.add(t, 'CT-1 casing', cyl(c[0], c[1], z0 + 1.00, 2 * R, 1.10), 'equip', C_TW)
    m.add(t, 'CT-1 fan stack', cyl(c[0], c[1], z0 + 2.10, 1.10, 0.40), 'equip', (0.1, 0.4, 0.4))
    m.add(t, 'CT-1 fan motor EC', cyl(c[0], c[1], z0 + 2.50, 0.30, 0.25), 'equip', (0.2, 0.2, 0.2))
    m.add(t, 'CT-1 base ring', cyl(c[0], c[1], DUN, 2 * R, SPR).cut(cyl(c[0], c[1], DUN, 2 * R - 0.20, SPR)), 'equip', (0.9, 0.5, 0.1),
          connects={'DUN-CT-1'})
    rnz(m, t, 'cw_out', c, R, 270, 0.45, 100, 'cold water to P-6', stub=0.10, mat='CS40')
    rnz(m, t, 'cw_in', c, R, 180, 2.05, 100, 'hot water to distribution', stub=0.10, mat='CS40')
    rnz(m, t, 'byp_in', c, R, 180, 0.75, 100, 'TV-301 bypass to basin', stub=0.10, mat='CS40')
    rnz(m, t, 'mu_in', c, R, 0, 0.80, 20, 'make-up (float valve)', stub=0.10, mat='PPR')
    rnz(m, t, 'ovf', c, R, 45, 0.70, 50, 'overflow', stub=0.10, mat='PVC')
    rnz(m, t, 'drn', c, R, 45, 0.33, 50, 'drain', stub=0.10, mat='PVC')
    m.item(t, 'cooling tower, FRP round counterflow, 60 ton class, low-head distribution (<= 25 kPa), low-noise EC/VFD fan '
              '1.5 kW (wide blades), basin splash mats, drift <= 0.002 %, vibration switch VS-301, covered basin, '
              'EH-301 1.5 kW basin heater, LT-301/LSLL-301/TE-303', 'buy', 'FRP UV-resistant, SS304 fittings',
           '111 kW @ 35.8/31.8 C, WB 28.5, 60 % fan, 24.2 m3/h', 'Liang Chi LBC-60, Kuken, Shinwa (TW); Truwater (MY); Gohl, Jaeggi (EU); domestic FRP towers',
           820, 'cw')
    m.footprints[t] = (c[0] - R, c[1] - R, c[0] + R, c[1] + R)
    dunnage(m, t, c[0] - R, c[1] - R, c[0] + R, c[1] + R, axis='x', inset=0.25, n=3)
    m.tower_ring = (c, R + 1.0)

    # ---------------------------------------------------------------- PS-2 CW skid frame + VFD cabinet + HX-4
    t = 'PS-2'
    zf = B_SPR
    for yb in (0.43, 1.27):
        m.add(t, 'PS-2 frame x-beam', box(5.00, yb - 0.03, zf, 1.35, 0.06, 0.12), 'equip', C_STEEL)
    for xb in (5.03, 5.70, 6.32):
        m.add(t, 'PS-2 frame y-beam', box(xb - 0.03, 0.40, zf, 0.06, 0.90, 0.12), 'equip', C_STEEL)
    m.add(t, 'VFD cabinet (P-6A/B)', box(5.55, 0.40, 0.55, 0.75, 0.08, 0.70), 'equip', C_ELEC)
    m.add(t, 'VFD stand', box(5.58, 0.40, zf + 0.12, 0.04, 0.04, 0.55 - zf - 0.12).fuse(box(6.24, 0.40, zf + 0.12, 0.04, 0.04, 0.55 - zf - 0.12)),
          'equip', C_STEEL)
    m.item(t, 'condenser-water pump skid PS-2: galvanised frame on spring isolators, P-6A/B, IP55 VFD cabinet (2 x 1.5 kW '
              'HVAC VFD, Modbus, DC choke), HX-4 bracket', 'make', 'S235 galvanised, prefabricated', '1.35 x 0.9 m',
           'domestic skid fabricator; VFD Danfoss FC 102 (DK), ABB ACH580 (FI), Siemens G120P (DE)', 120, 'pumps')
    m.footprints[t] = (5.00, 0.40, 6.35, 1.30)
    dunnage(m, t, 5.00, 0.43, 6.35, 1.27, axis='x', inset=0.0, ext=0.0)
    mounts(m, t, [(5.03, 0.43), (5.70, 0.43), (6.32, 0.43), (5.03, 1.27), (5.70, 1.27), (6.32, 1.27)], 'spring')
    m.zone(t, 5.00, 1.30, 6.35, 1.90, label='pump access N')

    t = 'HX-4'
    m.add(t, 'HX-4 brazed PHE', box(5.05, 0.70, 0.45, 0.12, 0.25, 0.38), 'equip', (0.7, 0.7, 0.75))
    m.add(t, 'HX-4 bracket', box(5.05, 0.70, 0.37, 0.12, 0.25, 0.08), 'equip', C_STEEL, connects={'PS-2'})
    m.nozzle(t, 'g_in', (5.08, 0.95, 0.80), (0, 1, 0), 25, 'glycol in', stub=0.06, mat='SS304', flange=False)
    m.nozzle(t, 'g_out', (5.08, 0.95, 0.52), (0, 1, 0), 25, 'glycol out', stub=0.06, mat='SS304', flange=False)
    m.nozzle(t, 'w_in', (5.14, 0.70, 0.52), (0, -1, 0), 25, 'CW in', stub=0.06, flange=False)
    m.nozzle(t, 'w_out', (5.14, 0.70, 0.80), (0, -1, 0), 25, 'CW out', stub=0.06, flange=False)
    m.item(t, 'glycol/condenser-water brazed PHE, optional trim (XV-305 NC); glycol 45/40 C, CW 32/35 C', 'buy', 'SS316 brazed',
           '2.7 kW, 0.9 m3/h CW', 'SWEP (SE), Alfa Laval (SE), Kaori (TW)', 15, 'cw', notes='on PS-2 west end')

    # ---------------------------------------------------------------- WT-1 water treatment skid (moved south, near PS-2)
    t = 'WT-1'
    x0, y0 = 3.55, 0.40
    m.add(t, 'WT-1 bund tray', box(x0, y0, B_PAD, 1.20, 0.70, 0.15), 'equip', (0.30, 0.55, 0.30))
    for k, xx in enumerate((3.90, 4.30, 4.51)):
        m.add(t, 'WT-1 chemical drum %d' % (k + 1), cyl(xx, 0.62, B_PAD + 0.15, 0.36, 0.55), 'equip', (0.9, 0.9, 0.3))
    m.add(t, 'WT-1 dosing/controller panel', box(x0, y0 + 0.05, B_PAD + 0.15, 0.06, 0.60, 1.10), 'equip', (0.85, 0.85, 0.88))
    m.add(t, 'F-SS separator', cyl(4.60, 0.95, B_PAD + 0.15, 0.16, 0.75), 'equip', (0.35, 0.35, 0.40))
    m.add(t, 'sample cell + coupon rack', box(x0 + 0.08, 0.95, 0.60, 0.40, 0.10, 0.35), 'equip', (0.6, 0.6, 0.65))
    m.nozzle(t, 'ss_in', (4.75, 1.00, 0.60), (1, 0, 0), 32, 'side-stream in', stub=0.06)
    m.nozzle(t, 'ss_out', (4.75, 0.80, 0.60), (1, 0, 0), 32, 'side-stream out', stub=0.06)
    m.nozzle(t, 'bd', (3.55, 0.90, 0.40), (-1, 0, 0), 25, 'blowdown to drain', stub=0.06, mat='PVC', flange=False)
    m.item(t, 'cooling-water treatment skid: chemical bund, 3 x 60 L drums, DP-1..3 diaphragm dosing pumps, EC/pH/ORP '
              'controller WT-1 (AIT-301/302/303), sample cell, coupon rack, F-SS centrifugal separator 2.2 m3/h with XV-303 '
              'purge, XV-302 blowdown + FQ-302', 'buy', 'PP/PE bund, SS fittings',
           '1.2 x 0.7 x 1.3 m', 'ProMinent DULCOMETER (DE), Emec, Seko (IT); Netafim/Arkal or Amiad (separator); domestic skid', 300, 'water')
    m.footprints[t] = (3.55, 0.40, 4.75, 1.10)
    dunnage(m, t, 3.55, 0.40, 4.75, 1.10, axis='x', inset=0.10, ext=0.0)
    m.zone(t, 2.95, 0.40, 3.55, 1.10, label='dosing panel access W')

    # ---------------------------------------------------------------- DC-1 dry cooler with adiabatic pads
    t = 'DC-1'
    x0, y0, z0 = 0.40, 5.60, B_PAD
    m.add(t, 'DC-1 casing + coil', box(x0, y0, z0 + 0.25, 1.20, 0.60, 0.75), 'equip', (0.55, 0.62, 0.68))
    for (x, y) in ((x0, y0), (x0 + 1.14, y0), (x0, y0 + 0.54), (x0 + 1.14, y0 + 0.54)):
        m.add(t, 'DC-1 leg', box(x, y, z0, 0.06, 0.06, 0.25), 'equip', C_STEEL)
    for k in range(2):
        m.add(t, 'DC-1 EC fan', cyl(x0 + 0.32 + 0.56 * k, y0 + 0.30, z0 + 1.00, 0.48, 0.12), 'equip', (0.2, 0.2, 0.2))
    m.add(t, 'DC-1 pad S', box(x0 + 0.05, y0 - 0.08, z0 + 0.35, 1.10, 0.08, 0.55), 'equip', (0.75, 0.65, 0.40))
    m.add(t, 'DC-1 pad N', box(x0 + 0.05, y0 + 0.60, z0 + 0.35, 1.10, 0.08, 0.55), 'equip', (0.75, 0.65, 0.40))
    m.nozzle(t, 'g_in', (0.40, 6.05, 0.40), (-1, 0, 0), 25, 'glycol hot in', stub=0.10, mat='SS304')
    m.nozzle(t, 'g_out', (0.40, 5.75, 0.50), (-1, 0, 0), 25, 'glycol cold out', stub=0.10, mat='SS304')
    m.nozzle(t, 'pad_w', (1.60, 6.10, 1.05), (1, 0, 0), 15, 'pad water (softened)', stub=0.06, mat='PPR', flange=False)
    m.item(t, 'engine glycol dry cooler, 2 EC fans (fan on B4 FAN3), coastal-coated Cu/Al coil, adiabatic pre-cooling pads '
              'both long sides with XV-307 + drain', 'buy', 'Cu/Al epoxy coil, galvanised casing',
           '4.0 kW @ 46 C dry (glycol 52 C) / 38.5 C with pads; 2600 m3/h', 'Guentner (DE), LU-VE (IT), Alfa Laval (SE); domestic air-cooler makers',
           90, 'engine', notes='interface with engine glycol loop M-751 (docs/electrical)')
    m.footprints[t] = (0.40, 5.52, 1.60, 6.28)
    dunnage(m, t, 0.40, 5.60, 1.60, 6.20, axis='x', inset=0.06, ext=0.0)
    m.zone(t, 0.40, 5.00, 1.60, 5.52, label='coil / pad access S')

    # ---------------------------------------------------------------- RS-1 riser hood + penetration
    t = 'RS-1'
    x0, y0, x1, y1 = 9.10, 5.60, 9.80, 6.30
    curb = box(x0, y0, 0.0, x1 - x0, y1 - y0, 0.20).cut(box(x0 + 0.08, y0 + 0.08, 0.0, x1 - x0 - 0.16, y1 - y0 - 0.16, 0.20))
    m.add(t, 'RS-1 curb', curb, 'equip', (0.7, 0.7, 0.7))
    hood = box(x0 - 0.05, y0 - 0.05, 0.80, x1 - x0 + 0.10, y1 - y0 + 0.10, 0.04)
    for (xa, ya, dx, dy) in ((x0 - 0.05, y0 - 0.05, x1 - x0 + 0.10, 0.03), (x0 - 0.05, y1 + 0.02, x1 - x0 + 0.10, 0.03),
                             (x1 + 0.02, y0 - 0.05, 0.03, y1 - y0 + 0.10)):
        hood = hood.fuse(box(xa, ya, 0.20, dx, dy, 0.60))
    m.add(t, 'RS-1 weather hood (open W)', hood, 'equip', (0.75, 0.75, 0.78))
    m.item(t, 'roof penetration: insulated upstand curb 0.7 x 0.7 m + weather hood open to the west, sealing boots per pipe',
           'make', 'concrete/steel upstand, galvanised hood, EPDM boots', '0.7 x 0.7 m, 8 pipes', 'site contractor', 60, 'riser')
    m.footprints[t] = (x0, y0, x1, y1)

    # ---------------------------------------------------------------- BOP-R panel
    t = 'BOP-R'
    m.add(t, 'BOP-R enclosure', box(7.00, 9.20, B_PAD, 1.20, 0.45, 2.00), 'equip', C_ELEC)
    m.add(t, 'BOP-R canopy', box(6.90, 9.10, 2.30, 1.40, 0.65, 0.04), 'equip', (0.8, 0.8, 0.8))
    for (x, y) in ((6.92, 9.62), (8.24, 9.62)):
        m.add(t, 'BOP-R canopy post', box(x, y, B_PAD, 0.04, 0.04, 2.30 - B_PAD), 'equip', C_STEEL)
    m.item(t, 'roof BOP/MCC panel envelope (B6-R + touch display, PSU 24 V, meters EM-HVAC / JT-191..196, MCB/MCCB, SPD, '
              'RCD) with sun canopy; contents per docs/electrical', 'buy', 'IP55, filtered fan, canopy',
           '1.2 x 0.45 x 2.0 m', 'Rittal (DE) or domestic panel builder; switchgear Schneider, ABB, Siemens', 220, 'elec')
    m.footprints[t] = (6.90, 9.10, 8.30, 9.75)
    dunnage(m, t, 7.00, 9.20, 8.20, 9.65, axis='x', inset=0.06)
    m.zone(t, 7.00, 8.20, 8.20, 9.10, label='panel doors S')

    # ---------------------------------------------------------------- FS-1 fire cylinder cabinet
    t = 'FS-1'
    m.add(t, 'FS-1 cabinet', box(3.00, 9.30, B_PAD, 0.60, 0.45, 1.40), 'equip', C_FIRE)
    m.add(t, 'FS-1 sunshade', box(2.95, 9.25, 1.62, 0.70, 0.55, 0.03), 'equip', (0.9, 0.9, 0.9))
    m.nozzle(t, 'out', (3.30, 9.52, B_PAD + 1.40), (0, 0, 1), 15, 'FK-5-1-12 discharge FZ1', stub=0.08, mat='SS316F')
    m.item(t, 'FZ1 cylinder cabinet: 2 x FK-5-1-12 cylinders 8 L (>= 1.52 kg each, N2 25 bar) main + reserve, solenoid + '
              'manual actuators, discharge hoses, check valves, manifold, PSL-890A/C, lock-off valve (ZSC-899A), TE-499',
           'buy', 'galvanised + white, 25 mm insulation, vented, shaded', '0.60 x 0.45 x 1.40 m',
           'listed systems: Siemens Sinorix 1230 (DE), Minimax MX 1230 (DE); listed Chinese makers', 80, 'fire')
    m.footprints[t] = (2.95, 9.25, 3.65, 9.80)
    dunnage(m, t, 3.00, 9.30, 3.60, 9.75, axis='x', inset=0.06)
    m.zone(t, 3.00, 8.50, 3.60, 9.30, label='cylinder access S')

    # ---------------------------------------------------------------- roof drains (assumed, site) and gas riser stub
    for tag, (x, y) in (('RD-1', (0.15, 7.05)), ('RD-2', (9.40, 3.20)), ('RD-3', (3.30, 0.15)), ('RD-4', (6.20, 8.55))):
        m.add(tag, '%s roof drain (assumed)' % tag, cyl(x, y, 0.0, 0.20, 0.03), 'ref', (0.2, 0.2, 0.2))
        m.interface('%s roof drain' % tag, tag, (x, y, 0.0), (0, 0, -1), 'DN50-100', 'drainage', 'site / building (ASSUMED position)')
    m.add('GAS-R', 'building gas riser stub (assumed)', cyl(0.10, 6.95, 0.0, 0.08, 0.75), 'ref', (0.95, 0.8, 0.1))


# ================================================================================================ piping
def piping(m):
    R_ = []

    def add(*a, **k):
        r = Route(*a, **k)
        R_.append(r)
        return r

    nz = m.nz

    # ---------------- exhaust
    add('HD-1', 'L-EX-01', 'exhaust EP-1 -> D-101', 250, 'DUCT', [nz('EP-1', 'exh_out'), nz('D-101', 'in')], ins='DW50',
        connects={'EP-1', 'D-101'}, inline=[dict(type='bellows', tag='EJ-101', at=(2.95, 8.25, 0.80), dn=250)], group='exhaust')
    add('BP-1', 'L-EX-02', 'exhaust bypass D-101 -> ST-1', 250, 'DUCT',
        [nz('D-101', 'byp'), (4.85, 8.25, 2.50), nz('ST-1', 'byp_in')], ins='DW50', connects={'D-101', 'ST-1', 'HX-1'}, group='exhaust', support=False)

    # ---------------- HW primary (HX-1 <-> LLH-1)
    add('HW-01S', 'L-HW-01', 'HW primary supply HX-1 -> LLH-1', 50, 'CS40',
        [nz('HX-1', 'hw_sup'), (5.70, 7.30, 1.15), nz('LLH-1', 'pri_in')], ins='MW50', connects={'HX-1', 'LLH-1'},
        inline=[dict(type='separator', tag='AS-1', at=(6.04, 7.30, 1.15))], support=False)
    add('HW-01R', 'L-HW-01', 'HW primary return LLH-1 -> P-1 -> HX-1', 50, 'CS40',
        [nz('LLH-1', 'pri_out'), (5.30, 7.30, 0.55), (5.30, 7.30, 1.80), nz('HX-1', 'hw_ret')], ins='MW50',
        connects={'HX-1', 'LLH-1'},
        inline=[dict(type='pump_twin', tag='P-1A/B', at=(5.62, 7.30, 0.55), motor_dir=(0, 0, 1)),
                dict(type='magflow', tag='FT-111', at=(5.95, 7.30, 0.55)),
                dict(type='heatmeter', tag='HM-1', at=(5.30, 7.30, 1.30))])
    add('EXP-1', 'L-HW-EX', 'expansion line LLH-1 -> ET-1', 20, 'CS40',
        [nz('LLH-1', 'exp'), (7.25, 7.30, 0.55), nz('ET-1', 'conn')], ins=None, connects={'LLH-1', 'ET-1'})

    # ---------------- HW secondary headers on PS-1
    add('HW-S', 'L-HW-02', 'HW secondary supply header LLH-1 -> PS-1', 65, 'CS40',
        [nz('LLH-1', 'sec_out'), (6.60, 6.10, 1.15), (2.92, 6.10, 1.15)], ins='MW50', connects={'LLH-1', 'PS-1'})
    add('HW-R', 'L-HW-02', 'HW secondary return header PS-1 -> LLH-1', 65, 'CS40',
        [(3.18, 6.10, 0.75), (6.60, 6.10, 0.75), nz('LLH-1', 'sec_in')], ins='MW50', connects={'LLH-1', 'PS-1'})
    add('HWS-1', 'L-HW-03', 'HW supply CH-1 generator (P-2A)', 50, 'CS40',
        [(4.52, 6.10, 1.15), (4.52, 5.32, 1.15), (4.52, 5.32, 0.30), (4.52, 4.12, 0.30), (4.52, 4.12, 1.60), nz('CH-1', 'hw_in')],
        ins='MW50', parent='HW-S', connects={'PS-1', 'CH-1'},
        inline=[dict(type='pump_inline', tag='P-2A', at=(4.52, 5.78, 1.15)),
                dict(type='ystrainer', tag='', at=(4.52, 3.95, 1.60)),
                dict(type='ball', tag='', at=(4.52, 3.76, 1.60))])
    add('HWR-1', 'L-HW-03', 'HW return CH-1 generator', 50, 'CS40',
        [nz('CH-1', 'hw_out'), (4.80, 4.30, 1.60), (4.80, 4.30, 0.30), (4.80, 5.32, 0.30), (4.80, 5.32, 0.75), (4.80, 6.10, 0.75)],
        ins='MW50', end_parent='HW-R', connects={'PS-1', 'CH-1'},
        inline=[dict(type='ball', tag='', at=(4.80, 3.74, 1.60)), dict(type='heatmeter', tag='HM-11', at=(4.80, 3.98, 1.60))])
    add('HWS-2', 'L-HW-04', 'HW supply CH-2 generator (P-2B)', 40, 'CS40',
        [(2.92, 6.10, 1.15), (2.92, 5.32, 1.15), (2.92, 5.32, 0.30), (2.92, 4.12, 0.30), (2.92, 4.12, 1.45), nz('CH-2', 'hw_in')],
        ins='MW50', parent='HW-S', connects={'PS-1', 'CH-2'},
        inline=[dict(type='pump_inline', tag='P-2B', at=(2.92, 5.78, 1.15)),
                dict(type='ystrainer', tag='', at=(2.92, 3.85, 1.45)),
                dict(type='ball', tag='', at=(2.92, 3.64, 1.45))])
    add('HWR-2', 'L-HW-04', 'HW return CH-2 generator', 40, 'CS40',
        [nz('CH-2', 'hw_out'), (3.18, 4.30, 1.45), (3.18, 4.30, 0.30), (3.18, 5.32, 0.30), (3.18, 5.32, 0.75), (3.18, 6.10, 0.75)],
        ins='MW50', end_parent='HW-R', connects={'PS-1', 'CH-2'},
        inline=[dict(type='ball', tag='', at=(3.18, 3.62, 1.45)), dict(type='heatmeter', tag='HM-12', at=(3.18, 3.90, 1.45))])
    add('HW-P3S', 'L-HW-05', 'HW to PS-3 (P-3 DHW / heating)', 25, 'CS40',
        [(6.25, 6.10, 1.15), nz('PS-3', 'hw_in')], ins='MW50', parent='HW-S', connects={'PS-3'})
    add('HW-P3R', 'L-HW-05', 'HW from PS-3 to return header', 25, 'CS40',
        [nz('PS-3', 'hw_out'), (6.05, 6.10, 0.75)], ins='MW50', end_parent='HW-R', connects={'PS-3'})

    # ---------------- CHW primary (chillers <-> TK-1 with P-4A/B)
    add('CHP-1O', 'L-CH-01', 'CHW CH-1 evaporator out -> TK-1', 50, 'CS40',
        [nz('CH-1', 'chw_out'), (5.70, 3.60, 1.10), (5.70, 3.60, 1.35), nz('TK-1', 'p1_in')], ins='EL40', connects={'CH-1', 'TK-1'},
        inline=[dict(type='motorball', tag='MV-CH1E', at=(5.30, 3.60, 1.10)), dict(type='heatmeter', tag='HM-21', at=(5.52, 3.60, 1.10))])
    add('CHP-1I', 'L-CH-01', 'CHW TK-1 -> P-4A -> CH-1 evaporator', 50, 'CS40',
        [nz('TK-1', 'p1_out'), (5.70, 3.60, 0.40), (5.70, 3.60, 0.70), nz('CH-1', 'chw_in')], ins='EL40', connects={'CH-1', 'TK-1'},
        inline=[dict(type='pump_inline', tag='P-4A', at=(5.42, 3.60, 0.70), motor_dir=(0, -1, 0)),
                dict(type='ystrainer', tag='', at=(5.18, 3.60, 0.70))])
    add('CHP-2O', 'L-CH-02', 'CHW CH-2 evaporator out -> TK-1', 40, 'CS40',
        [nz('CH-2', 'chw_out'), (3.30, 3.80, 1.00), (5.85, 3.80, 1.00), (5.85, 3.80, 1.10), (5.85, 3.60, 1.10), nz('TK-1', 'p2_in')],
        ins='EL40', connects={'CH-2', 'TK-1'},
        inline=[dict(type='motorball', tag='MV-CH2E', at=(3.70, 3.80, 1.00)), dict(type='heatmeter', tag='HM-22', at=(4.10, 3.80, 1.00))])
    add('CHP-2I', 'L-CH-02', 'CHW TK-1 -> P-4B -> CH-2 evaporator', 40, 'CS40',
        [nz('TK-1', 'p2_out'), (5.85, 3.60, 0.65), (5.85, 3.95, 0.65), (3.30, 3.95, 0.65), nz('CH-2', 'chw_in')],
        ins='EL40', connects={'CH-2', 'TK-1'},
        inline=[dict(type='pump_inline', tag='P-4B', at=(5.40, 3.95, 0.65), motor_dir=(0, 1, 0)),
                dict(type='ystrainer', tag='', at=(3.75, 3.95, 0.65))])

    # ---------------- CHW secondary TK-1 <-> PS-3 <-> PS-1
    add('CHS-T', 'L-CH-03', 'CHW secondary TK-1 -> PS-3 (V-CO1)', 50, 'CS40',
        [nz('TK-1', 's_out'), (6.30, 4.25, 0.95), (6.30, 4.25, 0.30), nz('PS-3', 'chw_tk')],
        ins='EL40', connects={'TK-1', 'PS-3'})
    add('CHR-T', 'L-CH-03', 'CHW secondary PS-3 (V-CO2) -> TK-1', 50, 'CS40',
        [nz('PS-3', 'chwr_tk'), (6.10, 4.30, 0.55), (6.10, 4.30, 0.30)] if False else
        [nz('PS-3', 'chwr_tk'), (6.10, 4.30, 0.30), (6.10, 4.30, 0.55), nz('TK-1', 's_in')],
        ins='EL40', connects={'TK-1', 'PS-3'})
    add('CHW-S', 'L-CH-03', 'CHW secondary supply header PS-3 -> P-5 -> PS-1', 50, 'CS40',
        [nz('PS-3', 'chw_p5'), (3.40, 5.50, 0.95)], ins='EL40', connects={'PS-3', 'PS-1'},
        inline=[dict(type='pump_twin', tag='P-5A/B', at=(5.25, 5.50, 0.95), motor_dir=(0, 0, 1)),
                dict(type='magflow', tag='FT-211', at=(4.95, 5.50, 0.95))])
    add('CHW-R', 'L-CH-03', 'CHW secondary return header PS-1 -> PS-3', 50, 'CS40',
        [(3.55, 5.50, 0.55), nz('PS-3', 'chwr_hdr')], ins='EL40', connects={'PS-3', 'PS-1'},
        inline=[dict(type='heatmeter', tag='HM-2', at=(4.30, 5.50, 0.55)),
                dict(type='separator', tag='AS-2', at=(5.30, 5.50, 0.55))])
    add('ET2-L', 'L-CH-EX', 'ET-2 connection to CHW return', 20, 'CS40',
        [nz('PS-1', 'et2'), (3.45, 5.50, 0.55)], ins=None, end_parent='CHW-R', connects={'PS-1'})

    # ---------------- CC-1 branch (to IF-1)
    add('CC-S', 'L-CH-04', 'CHW to intake coil CC-1', 40, 'CS40',
        [(3.40, 5.50, 0.95), (3.40, 6.38, 0.95), (3.40, 6.38, 0.30), (0.95, 6.38, 0.30), (0.95, 6.38, 0.55), nz('IF-1', 'chw_in')],
        ins='EL40', parent='CHW-S', connects={'PS-1', 'IF-1'},
        inline=[dict(type='picv', tag='TV-221', at=(0.95, 7.12, 0.55), dn=25), dict(type='ball', tag='', at=(0.95, 6.80, 0.55))])
    add('CC-R', 'L-CH-04', 'CHW return from CC-1', 40, 'CS40',
        [nz('IF-1', 'chw_out'), (0.95, 7.30, 0.95), (1.12, 7.30, 0.95), (1.12, 6.53, 0.95), (1.12, 6.53, 0.30), (3.55, 6.53, 0.30),
         (3.55, 6.53, 0.55), (3.55, 5.50, 0.55)], ins='EL40', end_parent='CHW-R', connects={'PS-1', 'IF-1'},
        inline=[dict(type='heatmeter', tag='HM-4', at=(2.95, 6.53, 0.30)), dict(type='ball', tag='', at=(1.12, 7.00, 0.95))])

    # ---------------- hall + ER branches (PS-1 -> corridor -> RS-1)
    # hall lane y 5.94 (clear of the HW headers at 6.10). Supplies drop at x 5.68 (hall) / 6.80 (ER, east of the HW headers);
    # returns stay at z 0.55 and leave the lane east of the supply risers (hall -> CHW-R, ER -> hall return).
    add('HALL-S', 'L-CH-05', 'CHW hall supply (roof)', 40, 'CS40',
        [(4.35, 5.50, 0.95), (4.35, 5.94, 0.95), (5.68, 5.94, 0.95), (5.68, 5.94, 0.30), (9.25, 5.94, 0.30), (9.25, 5.94, -0.42),
         (8.40, 5.94, -0.42)], ins='EL40', parent='CHW-S', connects={'PS-1', 'RS-1', 'REF'}, support=True)
    add('HALL-R', 'L-CH-05', 'CHW hall return (roof)', 40, 'CS40',
        [(8.55, 5.94, -0.60), (9.50, 5.94, -0.60), (9.50, 5.94, 0.55), (5.85, 5.94, 0.55), (5.85, 5.78, 0.55), (5.55, 5.78, 0.55),
         (5.55, 5.50, 0.55)], ins='EL40', end_parent='CHW-R', connects={'PS-1', 'RS-1', 'REF'})
    add('ER-S', 'L-CH-08', 'CHW electrical-room supply', 20, 'CS40',
        [(4.20, 5.50, 0.95), (4.20, 6.12, 0.95), (6.80, 6.12, 0.95), (6.80, 6.12, 0.30), (9.25, 6.12, 0.30), (9.25, 6.12, -2.50),
         (10.0, 6.12, -2.50)], ins='EL40', parent='CHW-S', connects={'PS-1', 'RS-1', 'REF'})
    add('ER-R', 'L-CH-08', 'CHW electrical-room return (joins the hall return)', 20, 'CS40',
        [(10.0, 6.12, -2.30), (9.50, 6.12, -2.30), (9.50, 6.12, 0.55), (7.00, 6.12, 0.55), (7.00, 5.94, 0.55)],
        ins='EL40', end_parent='HALL-R', connects={'PS-1', 'RS-1', 'REF'})
    add('DHW-S', 'L-HW-05', 'DHW charging supply PS-3 -> indoor TK-DHW', 25, 'CS40',
        [nz('PS-3', 'dhw_s'), (6.62, 5.62, 0.50), (6.62, 5.80, 0.50), (9.50, 5.80, 0.50), (9.50, 5.80, -2.30), (10.0, 5.80, -2.30)],
        ins='MW50', connects={'PS-3', 'RS-1', 'REF'})
    add('DHW-R', 'L-HW-05', 'DHW charging return indoor -> PS-3', 25, 'CS40',
        [(10.0, 5.80, -2.50), (9.25, 5.80, -2.50), (9.25, 5.80, 0.30), (6.80, 5.80, 0.30), (6.80, 5.42, 0.30), nz('PS-3', 'dhw_r')],
        ins='MW50', connects={'PS-3', 'RS-1', 'REF'})

    # ---------------- make-up, pad water, fill
    add('MU-1', 'L-MU-01', 'tower make-up (softened / RO blend) RS-1 -> CT-1', 20, 'PPR',
        [(10.0, 6.24, -2.50), (9.68, 6.24, -2.50), (9.68, 6.24, 0.40), (9.68, 1.95, 0.40), (9.50, 1.95, 0.40), (9.50, 1.95, 0.80),
         nz('CT-1', 'mu_in')], ins='EL25H', connects={'RS-1', 'CT-1', 'REF'}, heat_trace=True,
        inline=[dict(type='meter_water', tag='FQ-301', at=(9.68, 3.40, 0.40), dn=20), dict(type='motorball', tag='XV-301', at=(9.68, 2.95, 0.40), dn=20)])
    add('PW-1', 'L-MU-02', 'softened water to DC-1 pads + closed-loop fill', 15, 'PPR',
        [(9.68, 6.24, 0.40), (2.65, 6.24, 0.40), (2.65, 6.24, 0.30), (1.66, 6.24, 0.30), (1.66, 6.10, 0.30), (1.66, 6.10, 1.05),
         nz('DC-1', 'pad_w')] if False else
        [(9.68, 6.24, 0.40), (6.40, 6.24, 0.40), (6.40, 6.24, 0.70), (2.65, 6.24, 0.70), (2.65, 6.24, 0.30), (1.66, 6.24, 0.30),
         (1.66, 6.24, 1.05), nz('DC-1', 'pad_w')],
        ins='EL25H', parent='MU-1', connects={'DC-1', 'PS-1'}, heat_trace=True,
        inline=[dict(type='motorball', tag='XV-307', at=(2.80, 6.24, 0.70), dn=15)])

    # ---------------- glycol loop EP-1 <-> DC-1 <-> HX-4 (perimeter route)
    add('GL-R', 'L-GL-01', 'glycol engine return -> DC-1', 25, 'SS304',
        [nz('EP-1', 'gly_ret'), (2.40, 6.74, 0.40), (0.15, 6.74, 0.40), (0.15, 6.05, 0.40), nz('DC-1', 'g_in')],
        connects={'EP-1', 'DC-1'})
    add('GL-1', 'L-GL-02', 'glycol DC-1 -> HX-4', 25, 'SS304',
        [nz('DC-1', 'g_out'), (0.15, 5.75, 0.50), (0.15, 5.75, 0.40), (0.15, 1.30, 0.40), (4.96, 1.30, 0.40), (4.96, 1.30, 1.10),
         (5.08, 1.30, 1.10), (5.08, 1.10, 1.10), (5.08, 1.10, 0.80), nz('HX-4', 'g_in')] if False else
        [nz('DC-1', 'g_out'), (0.15, 5.75, 0.50), (0.15, 5.75, 0.40), (0.15, 1.30, 0.40), (4.96, 1.30, 0.40), (4.96, 1.30, 1.10),
         (5.08, 1.30, 1.10), (5.08, nz('HX-4', 'g_in')[1], 1.10), nz('HX-4', 'g_in')],
        connects={'DC-1', 'HX-4', 'PS-2'})
    add('GL-2', 'L-GL-03', 'glycol HX-4 -> engine supply', 25, 'SS304',
        [nz('HX-4', 'g_out'), (5.08, 1.12, 0.52), (5.08, 1.12, 1.25)] if False else
        [nz('HX-4', 'g_out'), (5.08, 1.13, 0.52), (4.98, 1.13, 0.52)] if False else
        [nz('HX-4', 'g_out'), (5.08, 1.12, 0.52), (5.08, 1.12, 0.25), (5.08, 1.42, 0.25), (0.27, 1.42, 0.25), (0.27, 6.86, 0.25),
         (2.40, 6.86, 0.25), nz('EP-1', 'gly_sup')],
        connects={'HX-4', 'EP-1', 'PS-2', 'DC-1'})

    # ---------------- condenser water
    add('CW-S', 'L-CW-01', 'CW tower basin -> PS-2 suction header', 100, 'PE100',
        [nz('CT-1', 'cw_out'), (8.25, 0.55, 0.45), (5.25, 0.55, 0.45)], connects={'CT-1', 'PS-2'},
        inline=[dict(type='basket', tag='BS-1', at=(7.25, 0.55, 0.45), dn=100), dict(type='magflow', tag='FT-301', at=(6.62, 0.55, 0.45), dn=100)])
    for tag, x in (('P-6A', 5.45), ('P-6B', 5.95)):
        add('CW-%s' % tag, 'L-CW-01', 'CW pump branch %s' % tag, 65, 'CS40', [(x, 0.55, 0.45), (x, 1.22, 0.45)],
            parent='CW-S', end_parent='CW-D', connects={'PS-2'}, support=False,
            inline=[dict(type='butterfly', tag='', at=(x, 0.67, 0.45)), dict(type='pump_inline', tag=tag, at=(x, 0.88, 0.45)),
                    dict(type='check', tag='', at=(x, 1.11, 0.45))])
    add('CW-D', 'L-CW-01', 'CW discharge header PS-2', 100, 'PE100', [(5.95, 1.22, 0.45), (5.10, 1.22, 0.45)], connects={'PS-2'}, support=False)
    add('CW-1', 'L-CW-02', 'CW supply CH-1', 80, 'PE100',
        [(5.70, 1.22, 0.45), (5.70, 2.85, 0.45), nz('CH-1', 'cw_in')], parent='CW-D', connects={'PS-2', 'CH-1'},
        inline=[dict(type='butterfly', tag='', at=(5.70, 2.40, 0.45), dn=80)])
    add('CW-2', 'L-CW-03', 'CW supply CH-2', 65, 'PE100',
        [(5.10, 1.22, 0.45), (5.10, 1.22, 0.75), (5.10, 1.65, 0.75), (3.68, 1.65, 0.75), (3.68, 2.85, 0.75), nz('CH-2', 'cw_in')],
        parent='CW-D', connects={'PS-2', 'CH-2'}, inline=[dict(type='butterfly', tag='', at=(3.68, 2.40, 0.75), dn=65)])
    add('CW-2R', 'L-CW-03', 'CW return CH-2 (MV-CH2C)', 65, 'PE100',
        [nz('CH-2', 'cw_out'), (3.68, 3.10, 1.40), (3.68, 3.10, 2.55), (5.85, 3.10, 2.55)], connects={'CH-2'}, end_parent='CW-R',
        inline=[dict(type='mbutterfly', tag='MV-CH2C', at=(3.68, 3.10, 1.95), dn=65, act=(0, -1, 0))])
    add('CW-R', 'L-CW-01', 'CW return CH-1 -> TV-301 -> tower', 100, 'PE100',
        [nz('CH-1', 'cw_out'), (5.85, 3.10, 1.55), (5.85, 3.10, 2.55), (7.00, 3.10, 2.55), (7.00, 1.95, 2.55), (7.00, 1.95, 0.75),
         nz('CT-1', 'byp_in')], connects={'CH-1', 'CT-1'},
        inline=[dict(type='mbutterfly', tag='MV-CH1C', at=(5.85, 3.10, 1.95), dn=80), dict(type='threeway', tag='TV-301', at=(7.00, 1.95, 2.05), dn=100)])
    add('CW-RT', 'L-CW-01', 'TV-301 -> tower distribution', 100, 'PE100', [(7.00, 1.95, 2.05), nz('CT-1', 'cw_in')],
        parent='CW-R', connects={'CT-1'}, support=False)
    add('CW-SS', 'L-CW-04', 'side-stream discharge -> F-SS', 32, 'CS40',
        [(5.30, 1.22, 0.45), (5.30, 1.00, 0.45), (5.30, 1.00, 0.95), (5.00, 1.00, 0.95), (5.00, 1.00, 0.60), nz('WT-1', 'ss_in')] if False else
        [(5.25, 1.22, 0.45), (5.25, 1.22, 0.98), (4.99, 1.22, 0.98), (4.99, 1.00, 0.98), (4.99, 1.00, 0.60), nz('WT-1', 'ss_in')],
        parent='CW-D', connects={'WT-1', 'PS-2'}, support=False)
    add('CW-SSR', 'L-CW-04', 'F-SS -> suction header', 32, 'CS40',
        [nz('WT-1', 'ss_out'), (5.25, 0.80, 0.60), (5.25, 0.55, 0.60), (5.25, 0.55, 0.45)] if False else
        [nz('WT-1', 'ss_out'), (4.95, 0.80, 0.60), (4.95, 0.55, 0.60), (5.33, 0.55, 0.60), (5.33, 0.55, 0.45)],
        end_parent='CW-S', connects={'WT-1', 'PS-2'}, support=False)
    add('CW-H4I', 'L-CW-05', 'CW discharge -> XV-305 -> HX-4', 25, 'CS40',
        [(5.40, 1.22, 0.45), (5.40, 1.22, 0.25)] if False else
        [(5.18, 0.55, 0.45), (5.18, 0.55, 0.30), (5.14, 0.55, 0.30)] if False else
        [(5.36, 1.22, 0.45), (5.36, 1.05, 0.45), (5.36, 1.05, 0.30), (5.14, 1.05, 0.30)] if False else
        [(5.14, 0.55, 0.45), (5.14, 0.55, 0.52), nz('HX-4', 'w_in')],
        parent='CW-S', connects={'HX-4', 'PS-2'}, support=False,
        inline=[])
    add('CW-H4O', 'L-CW-05', 'HX-4 -> XV-305 -> CW discharge', 25, 'CS40',
        [nz('HX-4', 'w_out'), (5.14, 0.60, 0.80), (5.14, 0.60, 1.12), (5.36, 0.60, 1.12), (5.36, 1.22, 1.12), (5.36, 1.22, 0.45)],
        end_parent='CW-D', connects={'HX-4', 'PS-2'}, support=False,
        inline=[dict(type='motorball', tag='XV-305', at=(5.36, 0.95, 1.12), dn=25)])

    # ---------------- drains
    add('DR-HX', 'L-DR-01', 'HX-1 start-up condensate -> NP-1', 25, 'SS316D',
        [nz('HX-1', 'drain'), (6.40, 8.05, 0.55), nz('NP-1', 'in')], connects={'HX-1', 'NP-1'}, support=False)
    add('DR-CC', 'L-DR-02', 'CC-1 condensate -> roof drain RD-1', 25, 'PVC',
        [nz('IF-1', 'cond'), (0.65, 7.05, 0.28), (0.15, 7.05, 0.28), (0.15, 7.05, 0.03)], connects={'IF-1', 'RD-1'})
    add('DR-OV', 'L-DR-03', 'CT-1 overflow -> RD-2', 50, 'PVC',
        [nz('CT-1', 'ovf'), (9.40, 2.75, 0.70) if False else (9.40, 2.75, 0.70), (9.40, 3.20, 0.70), (9.40, 3.20, 0.03)] if False else
        [nz('CT-1', 'ovf'), (9.30, 2.83, 0.70), (9.30, 3.20, 0.70), (9.30, 3.20, 0.03)], connects={'CT-1', 'RD-2'})
    add('DR-BD', 'L-DR-04', 'WT-1 blowdown -> RD-3', 25, 'PVC',
        [nz('WT-1', 'bd'), (3.30, 0.90, 0.40), (3.30, 0.15, 0.40), (3.30, 0.15, 0.03)], connects={'WT-1', 'RD-3'})

    # ---------------- gas
    add('GAS-1', 'L-NG-01', 'natural gas from building riser stub -> EP-1 gas train', 20, 'GAS',
        [(0.10, 6.95, 0.75), (1.60, 6.95, 0.75), (1.60, 7.30, 0.75), (1.60, 7.30, 0.30), nz('EP-1', 'gas_in')],
        connects={'EP-1', 'GAS-R'}, inline=[dict(type='ball', tag='HV-601 (manual, yellow)', at=(0.60, 6.95, 0.75), dn=20),
                                           dict(type='flex', tag='', at=(1.60, 7.43, 0.30), dn=20)])

    # ---------------- fire FZ1
    add('FZ1', 'L-FS-01', 'FK-5-1-12 discharge FS-1 -> EP-1 roof (FZ1)', 15, 'SS316F',
        [nz('FS-1', 'out'), (3.30, 9.52, 1.70), (2.00, 9.52, 1.70), (2.00, 8.05, 1.70), nz('EP-1', 'fire')],
        connects={'FS-1', 'EP-1'}, group='fire', support=False,
        inline=[dict(type='psv', tag='PS-889A', at=(2.60, 9.52, 1.70), dn=15)])

    for r in R_:
        build_route(m, r)


# ================================================================================================ hall (below the roof)
def hall(m):
    """reference building (slab, hall shell) + 4 under-ceiling FCUs + CHW distribution + condensate."""
    m.add('REF', 'roof slab (reference)', box(0, 0, -0.30, 10, 10, 0.30), 'ref', C_REF)
    for (x0, y0, dx, dy) in ((0, -0.25, 10, 0.25), (0, 10, 10, 0.25), (-0.25, 0, 0.25, 10), (10, 0, 0.25, 10)):
        m.add('REF', 'hall wall (reference)', box(x0, y0, -2.80, dx, dy, 2.50), 'ref', C_REF)
    m.add('REF', 'hall floor (reference)', box(0, 0, -2.85, 10, 10, 0.05), 'ref', C_REF)
    R_ = []

    def add(*a, **k):
        r = Route(*a, **k)
        R_.append(r)
        return r

    fcu = [('FCU-1', 2.5, 0.40, 'S'), ('FCU-2', 7.5, 0.40, 'S'), ('FCU-3', 2.5, 9.60, 'N'), ('FCU-4', 7.5, 9.60, 'N')]
    for t, xc, yc, wall in fcu:
        x0, x1 = xc - 0.60, xc + 0.60
        y0, y1 = yc - 0.30, yc + 0.30
        m.add(t, '%s unit' % t, box(x0, y0, -0.545, 1.20, 0.60, 0.235), 'equip', (0.92, 0.92, 0.92))
        m.add(t, '%s grille' % t, box(x0 + 0.05, (y1 if wall == 'S' else y0 - 0.01), -0.52, 1.10, 0.01, 0.12), 'equip', (0.6, 0.6, 0.6))
        sgn = 1 if wall == 'S' else -1
        m.nozzle(t, 'in', (x1, yc + sgn * 0.12, -0.42), (1, 0, 0), 20, 'CHW in', stub=0.08, flange=False)
        m.nozzle(t, 'out', (x1, yc - sgn * 0.12, -0.42), (1, 0, 0), 20, 'CHW out', stub=0.08, flange=False)
        m.nozzle(t, 'cd', (x1, yc - sgn * 0.24, -0.53), (1, 0, 0), 20, 'condensate', stub=0.05, mat='PVC', flange=False)
        m.item(t, 'under-ceiling exposed fan coil 600 CFM class, EC motor, 2-pipe, drain pan + condensate pump-free gravity '
                  'drain, Modbus room controller with RH (FCU-1..4 controllers)', 'buy', 'galvanised casing, Cu/Al coil',
               '5.9 kW nominal / 5.1 kW site, 0.76 m3/h', 'Saravel, Iran Radiator (IR); Gree, Midea (CN); Daikin (JP), Sabiana (IT)',
               30, 'hall')
    # supply / return mains and branches (supply z -0.42, return z -0.60)
    add('H-S1', 'L-CH-05', 'hall supply main DN40 -> tee x 8.40', 40, 'CS40', [(8.40, 5.94, -0.42), (3.40, 5.94, -0.42)], ins='EL19', parent='HALL-S', hall=True, connects={'REF'})
    add('H-R1', 'L-CH-05', 'hall return main', 40, 'CS40', [(3.55, 5.94, -0.60), (8.55, 5.94, -0.60)], ins='EL19', end_parent='HALL-R',
        hall=True, connects={'REF'})
    for t, xc, yc, wall in fcu:
        xs = xc + 0.60 + 0.30
        xr = xs + 0.15
        nin, nout, ncd = m.nz(t, 'in'), m.nz(t, 'out'), m.nz(t, 'cd')
        par_s = 'HALL-S' if xc > 5 else 'H-S1'
        par_r = 'HALL-R' if xc > 5 else 'H-R1'
        add('%s-S' % t, 'L-CH-06/07', 'hall branch supply %s' % t, 25, 'CS40',
            [(xs, 5.94, -0.42), (xs, nin[1], -0.42), nin], ins='EL19', parent=par_s, hall=True, connects={t, 'REF', 'HALL-S', 'H-S1'},
            inline=[dict(type='picv', tag='PICV-%s' % t, at=(xs, nin[1] + (0.40 if wall == 'S' else -0.40), -0.42), dn=20),
                    dict(type='ball', tag='', at=(xs, nin[1] + (0.75 if wall == 'S' else -0.75), -0.42), dn=20)])
        add('%s-R' % t, 'L-CH-06/07', 'hall branch return %s' % t, 25, 'CS40',
            [nout, (xr, nout[1], -0.42), (xr, nout[1], -0.60), (xr, 5.94, -0.60)], ins='EL19', end_parent=par_r, hall=True,
            connects={t, 'REF', 'HALL-R', 'H-R1'}, inline=[dict(type='ball', tag='', at=(xr, nout[1] + (0.45 if wall == 'S' else -0.45), -0.60), dn=20)])
        yw = 0.05 if wall == 'S' else 9.95
        add('%s-CD' % t, 'L-DR-05', 'condensate %s -> building drain' % t, 20, 'PVC',
            [ncd, (xs + 0.40, ncd[1], -0.53), (xs + 0.40, yw, -0.53), (xs + 0.40, yw, -2.70)], hall=True, connects={t, 'REF'})
        m.interface('%s condensate' % t, t, (xs + 0.40, yw, -2.70), (0, 0, -1), 'DN20', 'condensate', 'building drain (site)')
    for r in R_:
        build_route(m, r)


# ================================================================================================ interfaces
def interfaces(m):
    I = m.interface
    for name in ('air_in', 'exh_out', 'gas_in', 'gly_sup', 'gly_ret', 'fire'):
        n = m.nozzles[('EP-1', name)]
        I('EP-1 %s' % name, 'EP-1', n['p'], n['d'], 'DN%d' % n['dn'], n['medium'], 'engine package session (docs/06 section 3)')
    # FZ1 detector / nozzle mounting points inside EP-1 (package to confirm)
    for tag, p, note in (('TSH-871', (1.70, 8.05, 1.25), 'heat detector, hot zone, under package roof'),
                         ('TSH-872', (2.45, 7.80, 1.25), 'heat detector, gas-train side'),
                         ('BS-873', (1.40, 8.40, 1.10), 'IR3 flame detector, corner, viewing combustor + gas train'),
                         ('FN-1', (1.75, 8.05, 1.22), 'FK-5-1-12 nozzle 180 deg, hot zone'),
                         ('FN-2', (2.45, 8.05, 1.22), 'FK-5-1-12 nozzle 180 deg, gas-train zone')):
        I('%s mounting point' % tag, 'EP-1', p, (0, 0, -1), '-', 'fire (FZ1)', 'engine package session + docs/electrical (FCP)', note)
    for tag, p, note in (('HS-892', (3.75, 9.40, 1.40), 'yellow manual release FZ1, on FS-1 east side'),
                         ('HS-894', (3.75, 9.40, 1.20), 'blue abort/hold FZ1'),
                         ('XA-879', (3.30, 9.78, 1.90), 'sounder/beacon FZ1 on FS-1 sunshade post')):
        I('%s mounting point' % tag, 'FS-1', p, (0, -1, 0), '-', 'fire (FZ1)', 'docs/electrical (FCP)', note)
    I('BOP-R cable entry (bottom gland plate)', 'BOP-R', (7.60, 9.42, 0.18), (0, 0, -1), 'gland plate 0.4 x 0.2', 'power/signal',
      'docs/electrical (cable tray)')
    I('RS-1 roof penetration', 'RS-1', (9.45, 5.95, 0.0), (0, 0, -1), '0.7 x 0.7 m', '8 pipes', 'site (structure)')
    for rn, end, med, cp in (('ER-S', -1, 'CHW supply to FCU-E (30 m route)', 'electrical room (site route)'),
                             ('ER-R', 0, 'CHW return from FCU-E', 'electrical room (site route)'),
                             ('DHW-S', -1, 'DHW charging supply to TK-DHW / HX-2', 'indoor DHW room (site)'),
                             ('DHW-R', 0, 'DHW charging return', 'indoor DHW room (site)'),
                             ('MU-1', 0, 'make-up water from TK-401 / P-9', 'indoor water room (site)')):
        r = m.routes[rn]
        p = r.pts[end]
        I('%s building connection' % rn, rn, p, (1, 0, 0), 'DN%d' % r.dn, med, cp, 'pipe leaves the hall through the east wall at x = 10.0')
    I('GAS-1 building riser stub', 'GAS-1', (0.10, 6.95, 0.75), (-1, 0, 0), 'DN20', 'natural gas 4 bar', 'site / gas company (ASSUMED position)')
    I('IF-1 outlet flange', 'IF-1', (1.25, 7.85, 0.60), (1, 0, 0), 'DN200', 'intake air', 'EP-1 via flexible connector 50 mm')
