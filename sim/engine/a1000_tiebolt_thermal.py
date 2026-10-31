#!/usr/bin/env python3
"""AURORA-1000 phase 5: transient thermal-structural analysis of the rotor (rev 1.3). Tie-bolt and stud preload histories,
remaining clamp and opening / slip margins of every curvic joint, and the disc thermal stresses through start, stop, trips,
hot restart and a load step.

Model
  heat        axisymmetric transient conduction of the whole rotor in CalculiX (CAX6, *HEAT TRANSFER): front stub, impeller 1,
              spacer, impeller 2, drum, blisks R1 / R2 with their cast arms, the R1 - R2 spacer ring and the rear stub, each
              joined to its neighbour only through its curvic band (an orthotropic layer of the tooth height: 0.4 x the metal
              conductivity for half the area in contact, the tooth gaps open); the tie bolt + nut is a body of its own, in
              contact with the stub at the nut face and with the drum bulkhead at the thread, and in its bore cavity. Closed
              cavities (bolt bore, nut pocket, drum interior, the internal cavities under the turbine arms) are meshed as gas
              with an equivalent conductivity: gas conduction (Nu = 1, the stable-stratification bound, no convection) +
              linearised radiation between the walls (concentric cylinders in the bolt bore, parallel walls elsewhere,
              e = 0.4-0.5). The three centring lands of the bolt sit 0.10 mm (cold) to ~0.2 mm (15k) from the impeller and
              spacer bores: the land gap is meshed 1.0 mm wide with the conductance of a 0.15 mm gas gap.
  boundaries  every free surface belongs to a zone with a sink temperature and a film coefficient that follow the phase 1
              time histories (sim/engine/a1000_thrust_transient.py: speed, compressor flow and stage temperatures, delivery,
              back-face and front-cavity pressures, balance-seal flow, TIT, turbine exit, turbine flow):
                - impeller hub flow paths: relative total temperature T01 + (w r)^2 / 2 cp (rothalpy, no inlet swirl), passage
                  turbulent h 650 W/m2K at design x 2.3 for the blades as fins -> 1500 W/m2K, x (m / m_d)^0.8
                - rotor-stator cavities (impeller back faces, turbine disc faces): turbulent free-disc correlation with core
                  rotation (Owen & Rogers): Nu_r = 0.0238 Re_r^0.8, Re_r = rho (1 - beta) w r^2 / mu, beta 0.4-0.45, laminar
                  0.33 Re^0.5 below the transition; the local h varies as r^0.6 inside a band
                - rotating cylinders (shafts, drum, seals): Nu_D = 0.133 Re_w^(2/3) Pr^(1/3) (Becker / Kays-Bjorklund),
                  Re_w = w D^2 / nu; x 2 for labyrinth lands with through-flow
                - blisk platforms: gas relative total temperature at the hub (TIT - 85 K n^2 at R1, stage-1 exit - 90 K n^2 at
                  R2, from the design triangles), endwall h 1180 W/m2K + the blades as fins (59 / 36 x sqrt(h P k A)) -> 1600 / 1400 W/m2K x (m / m_d)^0.8
                - turbine front cavity: compressor delivery air + windage heating 40 K n^3 / (balance-seal flow ratio)
                - interstage cavities (R1 aft, under NGV2, R2 front): no purge air; gas taken in at the R1 aft rim seal at the
                  stage-1 exit total temperature - 30 K (as sim/engine/a1000_hot_section_calc.py)
                - R2 aft cavity: hub buffer / cooling air (compressor delivery + 45 K in the JB2 shield channel, 14 g/s) mixed
                  with 40 % ingested exhaust gas
                - journals and thrust collar: oil film 3000 W/m2K at 75-85 C; oil mist in the housings 300 W/m2K; post-lube
                  40 min (3 l/min) after the stop, then natural convection
              at standstill each zone falls to natural convection + radiation (6-30 W/m2K) to the stator around it, whose
              temperature follows the running sink with a 300 s lag while running and decays to the 30 C enclosure with a
              zone time constant (25-60 min) after the stop: the hot casing and NGVs soak heat back into the rotor
  preload     tie bolt: nut-to-thread spring model of a1000_rotor_stack.tie_bolt() with the area-weighted FE temperature of
              the bolt and of the load path of every stack part in 2 mm x-bins, E(T), the hub Poisson shortening x n^2 from
              the FE; checked against the full FE at the critical times. Studs (16 x MJ10, IN718): grip temperature along
              r 76 from the FE with a 45 s lag of the stud in its hole, members' free growth from the FE, stud / member
              stiffness 1 : 3 (to be replaced by the phase 4 joint stiffnesses)
  stress      CalculiX static (CAX6) of the whole stack at the critical times: FE temperature field, centrifugal load, blade
              pulls, the tie-bolt preload as an initial-temperature shrink of a plain shank segment, the curvic bands as orthotropic
              layers (axial modulus from the joint stiffness, low radial shear for flank sliding). Bolt force from the shank
              stress, band contact pressure, disc and impeller peak stresses; LCF per cycle by Manson-Morrow (2 / 20)
Cases   A cold start to full load (phase 1 case d: starter, purge, light-off, acceleration, no load, sync, 300 s load ramp),
          then full load for 4 h
        B normal stop (phase 1 case e: unload, cool-down at minimum load, fuel off + BOV, coast-down) and 4 h standstill
        C1 trip from full load, breaker closed, BOV (phase 1 case b); C2 the same with the BOV failing to open; C3 load
          rejection + trip, breaker open, BOV (phase 1 case a, 15,350 rpm)
        D hot restart 15 / 30 / 60 min after trip C1 (the recuperator and combustor walls still hot), start sequence of A
        E load step 50 -> 100 % (TIT 650 -> 970 C in 10 s) from a steady 50 % load
        AS / BS cold start and normal stop with the operating rule (SLOW: minimum load at TIT 480 C, slow ramp / unload)
Run:    python sim/engine/a1000_tiebolt_thermal.py [--cases A,B,..] [--configs baseline,fix] [--threads N] [--par N]
          [--thermal-only | --conv-thermal | --post-only] [--mesh-check] [--step-check] [--remesh]
        (numpy, scipy, gmsh, matplotlib; CCX = ccx path). Work files in P5_WORK (default cad_out/fea_p5). On the cloud node:
        --thermal-only per configuration and case, then --pass2 (cavity energy balance on the first-pass walls; AS / BS
        with --fac-dt 6 --deltmx 30), --conv-thermal, then --post-only --suffix 2 --mesh-check --step-check
Writes: sim/engine/fea/a1000_tiebolt_thermal.json, docs/img/a1000_tiebolt_thermal.png, docs/img/a1000_tiebolt_fields.png
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'cad', 'engine')); sys.path.insert(0, os.path.join(ROOT, 'sim'))
_argv = list(sys.argv); sys.argv = [sys.argv[0], '--quiet']
import a1000_rotor_stack as RS                                # noqa: E402  (geometry, materials, stack model, ccx helpers)
import a1000_thrust_transient as TT                           # noqa: E402  (phase 1 time histories)
sys.argv = _argv
G, A, DF, TC, F = RS.G, RS.A, RS.DF, RS.TC, RS.F

WORK = os.environ.get('P5_WORK', os.path.join(ROOT, 'cad_out', 'fea_p5'))
OUT_JSON = os.path.join(HERE, 'fea', 'a1000_tiebolt_thermal.json')
THREADS = int(os.environ.get('P5_THREADS', '4'))
OM_D = RS.OM                                                   # 15,000 rpm
T_AMB = TT.T_AMB - 273.15                                     # 15 C (ISO inlet, as phase 1)
T_ENCL = 30.0                                                 # engine enclosure after the stop
SIG = 5.670e-8
CP_AIR, PR_AIR, R_AIR = 1010.0, 0.70, 287.0


# ================================================================================================ materials
# heat: k [W/mK], cp [J/kgK] vs T [C]; density [kg/m3]
THERM = {
    'IN718':     dict(T=[20, 300, 500, 700, 900], k=[11.4, 14.7, 17.8, 20.8, 24.0], cp=[435, 480, 530, 575, 620], rho=8190.0),
    'MAR-M247':  dict(T=[20, 400, 700, 900, 1000], k=[9.0, 13.0, 17.0, 20.0, 21.5], cp=[400, 450, 500, 540, 560], rho=8540.0),
    'Ti64':      dict(T=[20, 200, 400, 600], k=[6.7, 9.0, 11.6, 14.5], cp=[526, 570, 610, 650], rho=4430.0),
    '17-4PH':    dict(T=[20, 300, 500], k=[17.8, 20.5, 23.0], cp=[460, 520, 570], rho=7800.0),
    '34CrNiMo6': dict(T=[20, 200, 400, 600], k=[42.0, 40.0, 36.0, 32.0], cp=[460, 500, 560, 650], rho=7850.0),
    'Waspaloy':  dict(T=[20, 400, 650, 800], k=[10.7, 15.3, 19.0, 21.0], cp=[440, 495, 545, 580], rho=8190.0),
}
# elastic / expansion for the stress model (E [MPa], mean CTE from 20 C) beyond the stack tables where the FE needs it
MECH = {
    'IN718':     dict(T=[20, 400, 650, 760], E=[200e3, 184e3, 172e3, 165e3], a=[12.8e-6, 13.6e-6, 14.4e-6, 14.9e-6], nu=0.29),
    'MAR-M247':  dict(T=list(DF.MAT_T), E=list(DF.MAT_E), a=list(DF.MAT_A), nu=0.30),
    'Ti64':      dict(T=[20, 200, 400], E=[114e3, 104e3, 96e3], a=[8.6e-6, 9.2e-6, 9.6e-6], nu=0.34),
    '17-4PH':    dict(T=[20, 200, 400], E=[196e3, 188e3, 180e3], a=[10.8e-6, 11.2e-6, 11.6e-6], nu=0.27),
    '34CrNiMo6': dict(T=[20, 200, 400], E=[210e3, 200e3, 188e3], a=[11.5e-6, 12.5e-6, 13.3e-6], nu=0.29),
    'Waspaloy':  dict(T=[20, 400, 650, 760], E=[213e3, 196e3, 180e3, 172e3], a=[12.0e-6, 13.3e-6, 14.0e-6, 14.8e-6], nu=0.30),
}
YIELD = {'IN718': ([20, 400, 650, 760], [1030., 980., 940., 800.]), 'Ti64': ([20, 200, 400], [880., 690., 600.]),
         'MAR-M247': (list(DF.MAT_T), list(DF.MAT_YS)), '17-4PH': ([20, 300, 400], [1000., 880., 830.]),
         '34CrNiMo6': ([20, 200, 400], [700., 640., 560.]), 'Waspaloy': ([20, 400, 650, 760], [795., 725., 705., 690.])}
STUD_TMAX = {'IN718': 650.0, 'Waspaloy': 760.0}                 # bolting service limits (IN718: delta phase / relaxation)
UTS = {'IN718': ([20, 400, 650, 760], [1240., 1170., 1100., 950.]), 'Ti64': ([20, 200, 400], [950., 780., 690.]),
       'MAR-M247': (list(TC.MAT_T), list(TC.MAT_UTS)), 'Waspaloy': ([20, 400, 650, 760], [1275., 1180., 1140., 1000.])}
RA = {'IN718': 0.30, 'Ti64': 0.35, 'MAR-M247': TC.RA, 'Waspaloy': 0.25}


def tab(table, key, T):
    return float(np.interp(T, table['T'], table[key]))


def k_air(T):
    return 0.0241 * ((T + 273.15) / 273.15) ** 0.81


def mu_air(T):
    Tk = T + 273.15
    return 1.716e-5 * (Tk / 273.15) ** 1.5 * 383.55 / (Tk + 110.4)


# cavity gas as an equivalent solid: conduction + radiation between the walls; (geometry, e1, e2, r1, r2 or gap, conduction x)
CAVITY = {
    'AIR_BORE':   dict(kind='cyl', r1=14.0, r2=23.0, e1=0.4, e2=0.35, kx=1.0),
    'AIR_LAND':   dict(kind='cyl', r1=22.0, r2=23.0, e1=0.4, e2=0.35, kx=1.0 / 0.15),   # 1.0 mm meshed for a 0.15 mm gap
    'AIR_POCKET': dict(kind='gap', L=12.0, e1=0.4, e2=0.4, kx=1.0),
    'AIR_DRUM':   dict(kind='gap', L=45.0, e1=0.4, e2=0.45, kx=1.0),
    'AIR_TURB':   dict(kind='gap', L=50.0, e1=0.6, e2=0.6, kx=1.0),
}


def k_cavity(name, T):
    c = CAVITY[name]; Tk = T + 273.15; hr4 = 4 * SIG * Tk ** 3
    if c['kind'] == 'cyl':
        a, b = c['r1'] * 1e-3, c['r2'] * 1e-3
        h_r = hr4 / (1 / c['e1'] + (a / b) * (1 / c['e2'] - 1))
        k_r = a * math.log(b / a) * h_r                            # 2 pi k / ln(b/a) = 2 pi a h_r
    else:
        k_r = hr4 / (1 / c['e1'] + 1 / c['e2'] - 1) * c['L'] * 1e-3
    return c['kx'] * k_air(T) + k_r


# ================================================================================================ geometry
JOINT_H = dict(stub_I1=2.4, I1_spc=3.0, spc_I2=2.6, I2_drum=3.2)   # curvic tooth heights as in the CAD (curvic_face)
LAND_R = 22.0                                                   # bolt lands in the model (22.9 real; gap modelled 1.0 mm)


def joints():
    """curvic joints: name -> (x, forward part, aft part, (face overlap r0, r1), band ri, ro, tooth height h, members)"""
    c, xj, h = G.CURVIC_C, G.X_J, G.CURVIC_HOT
    return {
        'stub_I1': (G.X_I1[0], 'stub', 'imp1', (23.0, 60.5), c['stub_I1']['ri'], c['stub_I1']['ro'], JOINT_H['stub_I1']),
        'I1_spc':  (G.X_I1[1], 'imp1', 'spacer', (23.0, 72.0), c['I1_spc']['ri'], c['I1_spc']['ro'], JOINT_H['I1_spc']),
        'spc_I2':  (G.X_I2[0], 'spacer', 'imp2', (23.0, 80.5), c['spc_I2']['ri'], c['spc_I2']['ro'], JOINT_H['spc_I2']),
        'I2_drum': (G.X_I2[1], 'imp2', 'drum', (50.0, 77.0), c['I2_drum']['ri'], c['I2_drum']['ro'], JOINT_H['I2_drum']),
        'drum_R1': (xj['drum_R1'], 'drum', 'R1', (58.0, 92.0), h['ri'], h['ro'], h['h']),
        'R1_spc':  (xj['R1_spc'], 'R1', 'tspc', (60.0, 92.0), h['ri'], h['ro'], h['h']),
        'spc_R2':  (xj['spc_R2'], 'tspc', 'R2', (60.0, 92.0), h['ri'], h['ro'], h['h']),
        'R2_stub': (xj['R2_stub'], 'R2', 'rstub', (58.0, 92.0), h['ri'], h['ro'], h['h']),
    }


PART_MAT = dict(stub='34CrNiMo6', imp1='Ti64', spacer='17-4PH', imp2='Ti64', drum='IN718', R1='MAR-M247', tspc='IN718',
                R2='MAR-M247', rstub='IN718', bolt='IN718')


def bolt_profile():
    """tie bolt + nut in one body (the nut thread is bonded), lands at LAND_R"""
    p = [(x, (LAND_R if abs(r - G.TIE['land'] / 2) < 1e-6 else r)) for x, r in G.tie_profile()]
    x0n, x1n = G.TIE['x_nut']
    # tie_profile starts (20, 0), (20, 21), (52, 21): the nut (x 18-48, r 21-33) joins the r 21 edge
    out = [(x0n + 2, 0.0), (x0n + 2, 21.0), (x0n, 21.0), (x0n, 33.0), (x1n, 33.0), (x1n, 21.0)] + p[2:]
    return [(float(x), float(r)) for x, r in out]


def part_polys():
    R = G._R
    P = dict(stub=G.stub_profile(), imp1=R['discs']['impeller1']['poly'], spacer=G.spacer_profile(), imp2=R['discs']['impeller2']['poly'],
             drum=G.drum_profile(), R1=G.disc_profile_arms('R1'), tspc=G.turbine_spacer_profile(), R2=G.disc_profile_arms('R2'),
             rstub=G.rear_stub_profile(), bolt=bolt_profile())
    return {k: [(float(x), float(r)) for x, r in v] for k, v in P.items()}


def air_envelopes():
    """closed cavities as envelope polygons whose edges lie inside the surrounding solids (the solids are cut out)"""
    J = joints()
    top = [(47.0, 25.0)]
    for name in ('stub_I1', 'I1_spc', 'spc_I2'):
        x, _, _, _, ri, ro, h = J[name]; d = h / 2 + 0.35
        top += [(x - d, 25.0), (x - d, ri + 1.0), (x + d, ri + 1.0), (x + d, 25.0)]
    xi2 = J['I2_drum'][0]
    top += [(xi2 - 2.3, 25.0), (xi2 - 2.3, 72.0), (590.0, 72.0), (590.0, 0.0), (47.0, 0.0)]
    xdr = J['drum_R1'][0]; xr1 = G.HUB['R1']; xr2 = G.HUB['R2']
    return dict(
        pocket=([(0.0, 0.0), (47.0, 0.0), (47.0, 32.0), (49.0, 32.0), (49.0, 37.0), (0.0, 37.0)], 'AIR_POCKET'),
        bore=(top, 'AIR_DRUM'),
        drumaft=([(625.0, 0.0), (xr1[0] + 1.7, 0.0), (xr1[0] + 1.7, 60.0), (xdr + 1.7, 60.0), (xdr + 1.7, 63.0), (xdr - 1.8, 63.0),
                  (xdr - 1.8, 52.0), (625.0, 52.0)], 'AIR_DRUM'),
        r12=([(xr1[1] - 2.0, 0.0), (xr2[0] + 2.0, 0.0), (xr2[0] + 2.0, 63.0), (xr1[1] - 2.0, 63.0)], 'AIR_TURB'),
        r2s=([(xr2[1] - 2.0, 0.0), (G.X_J['R2_stub'] + 106.0, 0.0), (G.X_J['R2_stub'] + 106.0, 27.0), (G.X_J['R2_stub'] + 2.8, 27.0),
              (G.X_J['R2_stub'] + 2.8, 63.0), (xr2[1] - 2.0, 63.0)], 'AIR_TURB'))


def build_mesh(scale=1.0, path=None):
    """gmsh OCC: parts, curvic bands, cavity gas; second-order triangles (ccx axisymmetric: x = radius, y = axial).
    Returns dict(nodes (N x 2: r, x), ids, elems (M x 6, node ids), ereg (M region index), regions [names], edges)"""
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0); gmsh.model.add('rotor')
    occ = gmsh.model.occ
    def surf(poly):
        pts = [occ.addPoint(r, x, 0) for x, r in poly]
        ls = [occ.addLine(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        return occ.addPlaneSurface([occ.addCurveLoop(ls)])
    def clean(poly):
        out = []
        for p in poly:
            if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4: out.append(p)
        if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-4: out.pop()
        return out
    P = part_polys(); J = joints()
    tags = {k: surf(clean(v)) for k, v in P.items()}
    occ.synchronize()
    # curvic joints: cut the tooth slab out of both faces, add the band (the rest of the slab is the tooth-gap relief)
    bands = {}
    for name, (x, a, b, (o0, o1), ri, ro, h) in J.items():
        for part in (a, b):
            slab = occ.addRectangle(o0, x - h / 2, 0, o1 - o0, h)
            out, _ = occ.cut([(2, tags[part])], [(2, slab)])
            assert len(out) == 1, (name, part, out)
            tags[part] = out[0][1]
        bands[name] = occ.addRectangle(ri, x - h / 2, 0, ro - ri, h)
    occ.synchronize()
    solids = [(2, t) for t in list(tags.values()) + list(bands.values())]
    airs = {}
    for name, (poly, mat) in air_envelopes().items():
        env = surf(clean(poly))
        out, _ = occ.cut([(2, env)], solids, removeTool=False)
        airs[name] = ([t for d, t in out], mat)
    occ.synchronize()
    allent = solids + [(2, t) for v in airs.values() for t in v[0]]
    _, omap = occ.fragment(allent, [])
    occ.synchronize()
    # map back: each input entity -> list of output surfaces
    regions, reg_of_surf = [], {}
    def assign(name, inp):
        idx = len(regions); regions.append(name)
        for d, t in omap[allent.index(inp)]:
            reg_of_surf[t] = idx
    for k, t in tags.items(): assign(k, (2, t))
    for k, t in bands.items(): assign('band_' + k, (2, t))
    for k, (ts, mat) in airs.items():
        for t in ts: assign('air_%s_%s' % (k, mat), (2, t))
    # mesh size: background 3 mm, finer in the bolt bore and at the joints
    h0 = 5.0 * scale
    fl = gmsh.model.mesh.field
    boxes = [(0, 33.0, 15.0, 632.0, 2.5), (0, 120.0, 640.0, 915.0, 2.6), (0, 92.0, 0.0, 1005.0, 3.6), (190.0, 260.0, 680.0, 900.0, 3.6)]
    fids = []
    for r0, r1, x0, x1, hb in boxes:
        f = fl.add('Box'); fl.setNumber(f, 'VIn', hb * scale); fl.setNumber(f, 'VOut', h0)
        fl.setNumber(f, 'XMin', r0); fl.setNumber(f, 'XMax', r1); fl.setNumber(f, 'YMin', x0); fl.setNumber(f, 'YMax', x1); fids.append(f)
    for name, (x, a, b, (o0, o1), ri, ro, h) in J.items():
        f = fl.add('Box'); fl.setNumber(f, 'VIn', 0.8 * scale); fl.setNumber(f, 'VOut', h0)
        fl.setNumber(f, 'XMin', o0 - 1); fl.setNumber(f, 'XMax', o1 + 1); fl.setNumber(f, 'YMin', x - h); fl.setNumber(f, 'YMax', x + h)
        fids.append(f)
    fm = fl.add('Min'); fl.setNumbers(fm, 'FieldsList', fids); fl.setAsBackgroundMesh(fm)
    gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 0); gmsh.option.setNumber('Mesh.MeshSizeFromPoints', 0)
    gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 0)
    gmsh.option.setNumber('Mesh.ElementOrder', 2); gmsh.option.setNumber('Mesh.SecondOrderLinear', 1)
    gmsh.option.setNumber('Mesh.Algorithm', 6)
    gmsh.model.mesh.generate(2)
    nt, xyz, _ = gmsh.model.mesh.getNodes(); xyz = xyz.reshape(-1, 3)
    ids = nt.astype(int); pos = {int(t): i for i, t in enumerate(ids)}
    elems, ereg = [], []
    for d, t in gmsh.model.getEntities(2):
        et, etags, en = gmsh.model.mesh.getElements(2, t)
        for typ, conn in zip(et, en):
            assert typ == 9, typ
            for e in conn.reshape(-1, 6).astype(int):
                elems.append(e); ereg.append(reg_of_surf[t])
    gmsh.finalize()
    nodes = xyz[:, :2]                                          # (r, x)
    elems = np.array(elems); ereg = np.array(ereg)
    # counter-clockwise in (r, x)
    ii = np.vectorize(pos.get)
    a, b, c = (nodes[ii(elems[:, k])] for k in range(3))
    ar = 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    flip = ar < 0
    elems[flip] = elems[flip][:, [0, 2, 1, 5, 4, 3]]
    M = dict(nodes=nodes, ids=ids, elems=elems, ereg=ereg, regions=regions, scale=scale)
    M.update(mesh_derived(M))
    if path: np.savez_compressed(path, nodes=nodes, ids=ids, elems=elems, ereg=ereg, regions=np.array(regions), scale=scale)
    return M


def mesh_derived(M):
    """index arrays, element centroids / areas / volumes, free edges (element, face 1-3, region, r, x, length)"""
    ids, nodes, elems = M['ids'], M['nodes'], M['elems']
    pos = np.zeros(ids.max() + 1, dtype=int) - 1; pos[ids] = np.arange(len(ids))
    E = pos[elems]
    a, b, c = nodes[E[:, 0]], nodes[E[:, 1]], nodes[E[:, 2]]
    area = 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    cen = (a + b + c) / 3.0
    vol = 2 * math.pi * cen[:, 0] * area
    seen = {}
    for i, e in enumerate(E):
        for f, (p, q) in enumerate(((0, 1), (1, 2), (2, 0)), 1):
            key = (min(e[p], e[q]), max(e[p], e[q]))
            seen.setdefault(key, []).append((i, f))
    free = []
    for (p, q), lst in seen.items():
        if len(lst) == 1:
            i, f = lst[0]
            rm, xm = 0.5 * (nodes[p] + nodes[q])
            if rm < 0.05: continue                                  # axis
            free.append((i, f, int(M['ereg'][i]), rm, xm, float(np.hypot(*(nodes[p] - nodes[q])))))
    return dict(pos=pos, E=E, area=area, cen=cen, vol=vol, free=free)


def load_mesh(path):
    d = np.load(path, allow_pickle=False)
    M = dict(nodes=d['nodes'], ids=d['ids'], elems=d['elems'], ereg=d['ereg'], regions=[str(s) for s in d['regions']], scale=float(d['scale']))
    M.update(mesh_derived(M))
    return M


def region_material(name, cen=None):
    """thermal material of a region; bands: 'BAND_<joint>'; air: by cavity (the bore gas at the lands is AIR_LAND)"""
    if name.startswith('band_'): return 'BAND_' + name[5:]
    if name.startswith('air_'): return name.split('_', 2)[2]
    return PART_MAT[name]


def element_materials(M):
    """per-element material name (bore gas split into bolt annulus / lands / drum interior)"""
    mats = []
    lands = G.TIE['lands']
    for i, rg in enumerate(M['ereg']):
        name = M['regions'][rg]; m = region_material(name)
        if name.startswith('air_bore'):
            r, x = M['cen'][i]
            if x < G.X_I2[1] and r < 23.2:
                m = 'AIR_LAND' if any(abs(x - xl) < 8.0 and r > LAND_R - 0.01 for xl in lands) else 'AIR_BORE'
            else:
                m = 'AIR_DRUM'
        mats.append(m)
    return np.array(mats)


def band_members():
    J = joints()
    return {k: (PART_MAT[v[1]], PART_MAT[v[2]]) for k, v in J.items()}


# ================================================================================================ zones and correlations
def zone_of(region, r, x):
    """boundary zone of a free edge (region name, edge mid radius / axial position); None = adiabatic"""
    xm1 = 0.5 * sum(G.HUB['R1']); xm2 = 0.5 * sum(G.HUB['R2'])
    rh1, rh2 = A.row_radius('R1', 0.0), A.row_radius('R2', 0.0)
    if region.startswith('air_pocket'): return 'P_MOUTH' if x < 0.05 else None
    if region.startswith('air_r2s'): return 'RB_END' if x > G.X_J['R2_stub'] + 105.9 else None
    if region.startswith('air') or region.startswith('band') or region == 'bolt': return None
    if region == 'stub':
        xb = G.X_BRG[0]; L = G.JOURNAL['L']
        if abs(r - G.JOURNAL['D'] / 2) < 0.05 and xb - L / 2 - 1 <= x <= xb + L / 2 + 1: return 'S_J1'
        if G.COLLAR['x0'] - 0.05 <= x <= G.COLLAR['x1'] + 0.05 and r > G.THRUST['ri'] - 4.5: return 'S_TB'
        return 'S_IN' if x >= 190.0 else 'S_MIST'
    if region == 'imp1':
        if x > G.X_I1[1] - 0.6 and r < 212.5: return 'I1_BACK_%d' % (0 if r < 120 else 1 if r < 170 else 2)
        return 'I1_HUB_%d' % min(max(int((r - 60.0) // 40.0), 0), 3) if r > 59.0 else None
    if region == 'spacer': return 'SP_SEAL'
    if region == 'imp2':
        if x > G.X_I2[1] - 0.6 and r < 237.5:
            return 'I2_BACK_V' if r >= G.BACKFACE['r_seal'] else ('I2_BACK_P_%d' % (0 if r < 140 else 1))
        return 'I2_HUB_%d' % min(max(int((r - 80.0) // 40.0), 0), 3) if r > 79.0 else None
    if region == 'drum':
        return 'D_BAL' if x < G.X_I2[1] + 48.0 else 'D_FC'
    if region in ('R1', 'R2'):
        n = region[1]; xm = xm1 if n == '1' else xm2; rh = rh1 if n == '1' else rh2; hub = G.HUB[region]
        if r >= rh - 0.3: return 'R%s_PLAT' % n
        front = x < xm
        if r >= rh - 26.0: return 'R%s_RIM%s' % (n, 'F' if front else 'A')
        band = 0 if r < 110 else 1 if r < 160 else 2
        if n == '1':
            if front: return 'D_FC' if x < hub[0] - 0.2 else 'R1_FF_%d' % band
            return 'IS_A' if x > hub[1] + 0.2 else 'IS_1_%d' % band
        if front: return 'IS_A' if x < hub[0] - 0.2 else 'IS_2_%d' % band
        return 'R2A_A' if x > hub[1] + 0.2 else 'R2A_%d' % band
    if region == 'tspc': return 'TS_FIN' if r > G.TSPC['ro'] - 0.2 else 'IS_A'
    if region == 'rstub':
        xj = G.X_J['R2_stub']; xb = G.X_BRG[1]; L = G.JOURNAL['L']
        if x < xj + 12.5: return 'R2A_A'
        if x < xb - L / 2 - 6: return 'RS_SEAL'
        if x <= xb + L / 2 + 6: return 'RS_J2'
        return 'RS_END'
    raise ValueError(region)


def zone_rref(z):
    """reference radius of a zone (band centre) for the correlations and the r^0.6 scaling of disc faces"""
    if z.startswith('I1_HUB_'): return 80.0 + 40.0 * int(z[-1])
    if z.startswith('I2_HUB_'): return 100.0 + 40.0 * int(z[-1])
    if z.startswith('I1_BACK_'): return (96.0, 145.0, 191.0)[int(z[-1])]
    if z.startswith('I2_BACK_P_'): return (110.0, 170.0)[int(z[-1])]
    if z == 'I2_BACK_V': return 219.0
    if z[-2:] in ('_0', '_1', '_2') and (z.startswith('R1_FF') or z.startswith('IS_') or z.startswith('R2A_')):
        return (88.0, 135.0, 180.0)[int(z[-1])]
    return dict(R1_RIMF=200.0, R1_RIMA=200.0, R2_RIMF=190.0, R2_RIMA=190.0, R1_PLAT=214.0, R2_PLAT=203.0, IS_A=80.0, R2A_A=80.0,
                TS_FIN=90.0, D_FC=75.0, D_BAL=85.0, SP_SEAL=75.0, S_IN=50.0, S_MIST=50.0, S_J1=45.0, S_TB=62.0, RS_SEAL=44.5,
                RS_J2=45.0, RS_END=42.0, P_MOUTH=20.0, RB_END=12.0)[z]


def zone_disc(z):
    return z.startswith(('I1_BACK', 'I2_BACK', 'R1_FF', 'IS_1', 'IS_2', 'R2A_0', 'R2A_1', 'R2A_2', 'R1_RIM', 'R2_RIM'))


# standstill: natural convection + radiation to the stator [W/m2K] and the stator decay time [s]
def zone_standstill(z):
    if z in ('P_MOUTH', 'RB_END'): return 0.0, 1800.0
    if z.startswith(('S_', 'I1_', 'SP_', 'I2_')): return 6.0, 1800.0
    if z.startswith('D_') or z.startswith('R1_FF'): return 10.0, 2400.0
    if z.endswith('PLAT') or 'RIM' in z: return 25.0, 1500.0
    if z.startswith(('IS_', 'TS_')): return 15.0, 2400.0
    return 12.0, 3600.0


def h_disc(r_mm, om, rho, T, beta):
    """rotor face in a rotor-stator cavity: free-disc turbulent correlation with core rotation [W/m2K]"""
    r = r_mm * 1e-3; mu, k = mu_air(T), k_air(T)
    Re = max(rho * (1 - beta) * abs(om) * r * r / mu, 1.0)
    Nu = max(0.0238 * Re ** 0.8, 0.33 * Re ** 0.5)
    return Nu * k / r


def h_cyl(r_mm, om, rho, T):
    """rotating cylinder (Becker / Kays-Bjorklund) [W/m2K]"""
    D = 2 * r_mm * 1e-3; mu, k = mu_air(T), k_air(T)
    Re = max(rho * abs(om) * D * D / mu, 1.0)
    return 0.133 * Re ** (2.0 / 3.0) * PR_AIR ** (1.0 / 3.0) * k / D


def gas_state(t, Y, M):
    """engine state for the boundary conditions from the phase 1 model (temperatures in C, pressures Pa, flows kg/s)"""
    g = TT.gas(t, Y, M); c = g['c']
    wr = c['w'] / TT.W_DET if 'w' in c else 1.0
    T21 = TT.T_AMB + (TT.T21_D - TT.T_AMB) * wr; T012 = TT.T_AMB + (TT.T012_D - TT.T_AMB) * wr
    T22 = TT.T_AMB + (TT.T22_D - TT.T_AMB) * wr
    return dict(n=float(Y[0]), mc=float(max(c['m'], 0.0)), mt=float(max(g['mt'], 0.0)), m85=float(max(g['m85'], 0.0)),
                Tcd=g['Tcd'] - 273.15, T21=T21 - 273.15, T012=T012 - 273.15, T22=T22 - 273.15, TIT=g['T0'] - 273.15,
                Ttex=g['T_tex'] - 273.15, PA=g['PA'], pbf=g['pbf'], pcf=g['pcf'], p21=c['p21'], p22=c['p22'], pR1=g['pR1'],
                Tr=g['Tr'] - 273.15, PB=g['PB'])


REF = {}                                                        # design (rating) flows for the h scalings
TBC = dict(R1=0.0, R2=0.0, k=1.0)                                # thermal barrier on the blisk platform + blade roots [mm], k W/mK


def tbc(h, row):
    """gas-side film coefficient through a TBC of TBC[row] mm (series resistance)"""
    t = TBC[row] * 1e-3
    return h / (1.0 + h * t / TBC['k']) if t > 0 else h


# configurations: as designed; interstage purge (evaluated, rejected); fix (TBC on the R1 platform, R1 - R2 studs, nuts and
# spacer ring in Waspaloy at 24 kN with a 50 % relaxation allowance, re-torqued at the hot-section inspection)
CONFIGS = dict(baseline=dict(tag='', purge=False, tbc=0.0, r12='IN718', pre12=27.0, relax12=0.10),
               purge=dict(tag='_p', purge=True, tbc=0.0, r12='IN718', pre12=27.0, relax12=0.10),
               fix=dict(tag='_t', purge=False, tbc=0.4, r12='Waspaloy', pre12=24.0, relax12=0.50))
CFG = dict(CONFIGS['baseline'], name='baseline')


def set_config(name):
    c = CONFIGS[name]; CFG.clear(); CFG.update(c, name=name)
    PURGE['on'] = c['purge']; TBC['R1'] = c['tbc']; PART_MAT['tspc'] = c['r12']
    return c['tag']


PURGE = dict(on=False, frac=0.0045, pickup=150.0, ingest=0.20)   # interstage purge (sec. 22 fix): fraction of the air, heat
                                                                 # pick-up in the NGV2 vane cores [K], share of ingested gas
# hub relative total temperature below the absolute total at the row inlet (design triangles, a1000_turbine_checks)
DT_REL = (A.S1['T0_in'] - 273.15 - TC.t0rel_hub_C('R1'), A.S2['T0_in'] - 273.15 - TC.t0rel_hub_C('R2'))


def zone_run(z, s, oil, cav=None):
    """running sink temperature [C] and film coefficient [W/m2K] of zone z for engine state s; oil = (h factor, T offset);
    cav = cavity air temperatures from the energy balance (FC, IS, R2A) that replace the inflow estimates"""
    n = max(s['n'], 0.0); om = n * OM_D; rr = zone_rref(z)
    fo, To = oil
    if z == 'S_J1': return 75.0 + To, 3000.0 * fo
    if z == 'S_TB': return 80.0 + To, 3000.0 * fo
    if z == 'S_MIST': return 70.0 + To, 300.0 * min(fo, 1.0) * max(n, 0.1) ** 0.7
    if z == 'RS_J2': return 85.0 + To, 3000.0 * fo
    if z == 'RS_END': return 85.0 + To, 300.0 * min(fo, 1.0) * max(n, 0.1) ** 0.7
    if z == 'P_MOUTH': return 70.0 + To, 20.0
    if z == 'RB_END': return 85.0 + To, 20.0
    fm = (s['mc'] / REF['mc']) ** 0.8
    if z == 'S_IN':
        T = 0.5 * (T_AMB + s['T012']); return T, 2 * h_cyl(rr, om, 1.1e5 / (R_AIR * (T + 273.15)), T)
    if z.startswith('I1_HUB_'): return T_AMB + (om * rr * 1e-3) ** 2 / (2 * CP_AIR), 1500.0 * fm
    if z.startswith('I2_HUB_'): return s['T012'] + (om * rr * 1e-3) ** 2 / (2 * CP_AIR), 1500.0 * fm
    if z.startswith('I1_BACK_'):
        T = s['T21'] + (0.55 * om * rr * 1e-3) ** 2 / (2 * CP_AIR)
        return T, h_disc(rr, om, s['p21'] / (R_AIR * (s['T21'] + 273.15)), T, 0.45)
    if z == 'SP_SEAL':
        T = s['T012']; return T, 2 * h_cyl(rr, om, s['p21'] / (R_AIR * (T + 273.15)), T)
    if z == 'I2_BACK_V':
        T = s['T22'] + (0.55 * om * rr * 1e-3) ** 2 / (2 * CP_AIR)
        return T, h_disc(rr, om, s['p22'] / (R_AIR * (s['T22'] + 273.15)), T, 0.45)
    if z.startswith('I2_BACK_P_'):
        T = s['Tcd'] + 10.0 * n * n; return T, h_disc(rr, om, s['pbf'] / (R_AIR * (T + 273.15)), T, 0.40)
    if z == 'D_BAL':
        T = s['Tcd']; return T, 2 * h_cyl(rr, om, s['pbf'] / (R_AIR * (T + 273.15)), T)
    T_fc = s['Tcd'] + 40.0 * n ** 3 / max(s['m85'] / REF['m85'], 0.3)
    if cav: T_fc = cav.get('FC', T_fc)
    rho_fc = s['pcf'] / (R_AIR * (T_fc + 273.15))
    T_s1 = s['TIT'] - 0.49 * (s['TIT'] - s['Ttex'])               # stage 1 exit total
    T_is = T_s1 - 30.0
    if PURGE['on']:                                               # interstage purge (fix): delivery air through the NGV2 vane
        T_p = s['Tcd'] + PURGE['pickup'] + 40.0 * n ** 3          # cores + windage, the rest ingested gas
        T_is = T_p + PURGE['ingest'] * max(T_s1 - T_p, 0.0)
    if cav: T_is = cav.get('IS', T_is)
    rho_is = s['pR1'] / (R_AIR * (T_is + 273.15))
    T_rel1 = s['TIT'] - DT_REL[0] * n * n; T_rel2 = T_s1 - DT_REL[1] * n * n
    T_buf2 = s['Tcd'] + 45.0
    T_r2a = T_buf2 + 0.4 * (s['Ttex'] - T_buf2)
    if cav: T_r2a = cav.get('R2A', T_r2a)
    rho_r2a = 1.05e5 / (R_AIR * (T_r2a + 273.15))
    ft = (s['mt'] / REF['mt']) ** 0.8
    if z == 'D_FC': return T_fc, h_cyl(rr, om, rho_fc, T_fc)
    if z.startswith('R1_FF_'): return T_fc, h_disc(rr, om, rho_fc, T_fc, 0.40)
    if z == 'R1_RIMF':
        T = T_fc + 0.4 * (T_rel1 - T_fc); return T, h_disc(rr, om, rho_fc, T, 0.40)
    if z == 'R1_PLAT': return T_rel1, tbc(1600.0 * ft, 'R1')
    if z == 'R1_RIMA': return T_is, h_disc(rr, om, rho_is, T_is, 0.40)
    if z.startswith('IS_') and z != 'IS_A': return T_is, h_disc(rr, om, rho_is, T_is, 0.40)
    if z == 'IS_A': return T_is, h_cyl(rr, om, rho_is, T_is)
    if z == 'TS_FIN': return T_is, 2 * h_cyl(rr, om, rho_is, T_is)
    if z == 'R2_RIMF':
        T = T_is + 0.3 * (T_rel2 - T_is); return T, h_disc(rr, om, rho_is, T, 0.40)
    if z == 'R2_PLAT': return T_rel2, tbc(1400.0 * ft, 'R2')
    if z == 'R2_RIMA':
        T = T_r2a + 0.3 * (s['Ttex'] - T_r2a); return T, h_disc(rr, om, rho_r2a, T, 0.40)
    if z.startswith('R2A_') and z != 'R2A_A': return T_r2a, h_disc(rr, om, rho_r2a, T_r2a, 0.40)
    if z == 'R2A_A': return T_r2a, h_cyl(rr, om, rho_r2a, T_r2a)
    if z == 'RS_SEAL':
        return T_buf2, 2 * h_cyl(rr, om, 1.15e5 / (R_AIR * (T_buf2 + 273.15)), T_buf2)
    raise ValueError(z)


# ================================================================================================ case histories (phase 1)
POST_LUBE = 2400.0                                              # 40 min at 3 l/min (sec. 19)
SOAK = 4 * 3600.0                                               # standstill / full-load hold after each transient
TAU_REC_SOAK, TAU_W_SOAK = 3 * 3600.0, 3600.0                    # recuperator matrix / combustor walls at standstill
YR = None


def _sample(t, Y, Ms, stride=1):
    idx = list(range(0, len(t), stride))
    if idx[-1] != len(t) - 1: idx.append(len(t) - 1)
    return [(float(t[i]), gas_state(t[i], Y[i], Ms[i]), dict(Ms[i])) for i in idx]


def _hold(t0, t1, s, dt=60.0):
    ts = np.arange(t0 + dt, t1 + 1e-6, dt)
    return [(float(x), dict(s), {}) for x in ts]


def _standstill(t_stop, t1, s_last):
    s = dict(s_last, n=0.0, mc=0.0, mt=0.0, m85=0.0)
    ts = sorted(set(list(t_stop + np.array([1, 3, 10, 30, 60, 120, 300])) + list(np.arange(t_stop + 600.0, t1 + 1e-6, 300.0))))
    return [(float(x), dict(s), {}) for x in ts if x <= t1]


SLOW = dict(hold=1800.0, T_hold=753.15, ramp=2700.0, unload=1800.0, cool=2700.0)  # operating rule (sec. 22): minimum-load
                                                                 # hold and load ramp after a start; unload and cool-down before a stop.
                                                                 # Minimum load = TIT 480 C (no load at full speed ~440 C; TIT 650 C
                                                                 # is ~40 % load and heats the rims too fast for the solid hubs). The
                                                                 # start extremes come in the first minutes of the hold (a longer hold
                                                                 # or ramp gains nothing); a slower stop does
SLOW.update(json.loads(os.environ.get('P5_SLOW', '{}')))         # rule variants (separate P5_WORK)


def tt_start(y0, t_off=0.0, hot=False, slow=False):
    """phase 1 start sequence (case d) from the gas state y0 (cold or hot recuperator). hot: no no-load hold, the
    synchroniser closes the breaker at 99 % speed (with a hot recuperator zero fuel does not hold the speed at no load,
    phase 1: the governor would need the BOV)"""
    S = TT.START; tit_now = lambda y: y[5]
    segs = [dict(name='starter to 20 %', md=dict(starter=True, start_bleed=True, tit=('const', TT.T_AMB)), t_end=t_off + 60.0,
                 event=TT.ev_speed(0.20), direction=1),
            dict(name='purge', md=dict(starter=True, start_bleed=True, hold=True, tit=('const', TT.T_AMB)), t_end=lambda t0: t0 + 5.0),
            dict(name='light-off, acceleration', md=lambda t0, y: dict(starter=True, start_bleed=True,
                                                                       tit=('start', t0, S['T_lo'], S['rate'], S['T_acc'])),
                 t_end=lambda t0: t0 + 120.0, event=TT.ev_speed(0.99), direction=1, max_step=0.02),
            dict(name='no load (governor)', md=lambda t0, y: dict(tit=('gov', tit_now(y), S['T_acc'])), t_end=lambda t0: t0 + 30.0,
                 init=lambda t0, y, md: y[:8] + [0.0, 1.0], max_step=0.02),
            dict(name='sync, load ramp', md=lambda t0, y: dict(breaker=True, tit=('ramp', t0, y[5], t0 + S['t_ramp'], TT.TIT_R)),
                 t_end=lambda t0: t0 + S['t_ramp'] + 300.0, init=lambda t0, y, md: [1.0] + y[1:], max_step=0.5)]
    if hot: segs = [sg for sg in segs if not sg['name'].startswith('no load')]
    if slow:                                                     # sync, minimum-load hold, slow ramp to the rating
        segs[-1] = dict(name='sync, minimum-load hold', md=lambda t0, y: dict(breaker=True, tit=('ramp', t0, y[5], t0 + 30.0, SLOW['T_hold'])),
                        t_end=lambda t0: t0 + SLOW['hold'], init=lambda t0, y, md: [1.0] + y[1:], max_step=0.5)
        segs.append(dict(name='slow load ramp', md=lambda t0, y: dict(breaker=True, tit=('ramp', t0, y[5], t0 + SLOW['ramp'], TT.TIT_R)),
                         t_end=lambda t0: t0 + SLOW['ramp'] + 300.0, max_step=1.0))
    return TT.chain(segs, y0, t_start=t_off)


def tt_trip_nobov(y0, t_end=1200.0):
    """trip with the breaker closed and the BOV failing to open: the hot recuperator keeps the turbine driving the
    compressor until the reverse-power relay opens the breaker"""
    base = dict(breaker=True, tit=('const', TT.TIT_R))
    segs = [dict(name='trip, breaker closed, no BOV', md=lambda t0, y: TT.trip_md(base, 0.0, y, bov=False), t_end=1.0, max_step=2e-3,
                 event=TT.ev_reverse_power, direction=-1, group='rp')]
    segs += [dict(s, group='rp') if s['name'] == 'until reverse power' else s for s in TT.rp_and_coast(t_end)]
    segs[1]['t_end'] = lambda t0: t0 + 600.0; segs[1]['max_step'] = 0.1
    return TT.chain(segs, y0)


def histories(cases):
    """phase 1 histories -> list of (t, state, md) per case, and the case events (t, label)"""
    global YR
    TT.calibrate()
    yd = TT.steady(1.0, TT.TIT_D, {}, Tr=TT.T_RCX_D)
    YR = TT.steady(1.0, TT.TIT_R, {}, guess=yd)
    md_r = dict(breaker=True, tit=('const', TT.TIT_R))
    s_r = gas_state(0.0, YR, md_r)
    REF.update(mc=s_r['mc'], mt=s_r['mt'], m85=s_r['m85'], PA=s_r['PA'])
    REF['cav_m'] = {c: cavity_inflow(c, s_r)[0] for c in CAV_ZONES}
    out = {}
    import pickle
    def stopped_at(H):
        return H[-1][0]
    def trip_hist():
        t, Y, M, log = TT.case_b(YR)
        H = [(0.0, s_r, md_r)] + _sample(t, Y, M, 3)
        return H, Y[-1]
    for c in cases:
        cache = os.path.join(WORK, 'hist_%s.pkl' % c)            # the phase 1 runs are slow (C2, hot restarts): reuse them
        if os.path.exists(cache):
            out[c] = pickle.load(open(cache, 'rb')); continue
        ev = []
        if c == 'A':
            y0 = [0.02, TT.P_AMB, TT.P_AMB, TT.P_AMB, TT.P_AMB, TT.T_AMB, TT.T_AMB, TT.T_AMB, 0.0, 1.0]
            t, Y, M, log = tt_start(y0)
            H = _sample(t, Y, M, 2); ev = [(s['t0'], s['name']) for s in log]
            H += _hold(H[-1][0], SOAK, H[-1][1])
            init = 'cold'
        elif c == 'AS':                                          # cold start with the operating rule
            y0 = [0.02, TT.P_AMB, TT.P_AMB, TT.P_AMB, TT.P_AMB, TT.T_AMB, TT.T_AMB, TT.T_AMB, 0.0, 1.0]
            t, Y, M, log = tt_start(y0, slow=True)
            H = _sample(t, Y, M, 2); ev = [(s['t0'], s['name']) for s in log]
            H += _hold(H[-1][0], H[-1][0] + SOAK, H[-1][1])
            init = 'cold'
        elif c == 'BS':                                          # normal stop with the operating rule
            st0 = dict(TT.STOP); TT.STOP.update(t_unload=SLOW['unload'], t_cool=SLOW['cool'], T_min=SLOW['T_hold'])
            try:
                t, Y, M, log = TT.case_e(YR, t_end=SLOW['unload'] + SLOW['cool'] + 900.0)
            finally:
                TT.STOP.clear(); TT.STOP.update(st0)
            H = [(0.0, s_r, md_r)] + _sample(t, Y, M, 3); ev = [(s['t0'], s['name']) for s in log]
            H += _standstill(stopped_at(H), stopped_at(H) + SOAK, H[-1][1]); init = 'rating'
        elif c == 'B':
            t, Y, M, log = TT.case_e(YR)
            H = [(0.0, s_r, md_r)] + _sample(t, Y, M, 3); ev = [(s['t0'], s['name']) for s in log]
            H += _standstill(stopped_at(H), stopped_at(H) + SOAK, H[-1][1]); init = 'rating'
        elif c == 'C1':
            H, _ = trip_hist(); ev = [(0.0, 'trip')]
            H += _standstill(stopped_at(H), stopped_at(H) + SOAK, H[-1][1]); init = 'rating'
        elif c == 'C2':
            t, Y, M, log = tt_trip_nobov(YR)
            H = [(0.0, s_r, md_r)] + _sample(t, Y, M, 3); ev = [(s['t0'], s['name']) for s in log]
            H += _standstill(stopped_at(H), stopped_at(H) + SOAK, H[-1][1]); init = 'rating'
        elif c == 'C3':
            t, Y, M, log = TT.case_a(YR)
            H = [(0.0, s_r, md_r)] + _sample(t, Y, M, 3); ev = [(s['t0'], s['name']) for s in log]
            H += _standstill(stopped_at(H), stopped_at(H) + SOAK, H[-1][1]); init = 'rating'
        elif c.startswith('D'):
            wait = float(c[1:]) * 60.0
            H, ylast = trip_hist(); t_stop = stopped_at(H)
            t_rs = t_stop + wait
            H += [h for h in _standstill(t_stop, t_rs - 1.0, H[-1][1])]
            dt = t_rs - t_stop
            Tr = TT.T_AMB + (ylast[7] - TT.T_AMB) * math.exp(-dt / TAU_REC_SOAK)
            Tw = TT.T_AMB + (ylast[6] - TT.T_AMB) * math.exp(-dt / TAU_W_SOAK)
            y0 = [0.02, TT.P_AMB, TT.P_AMB, TT.P_AMB, TT.P_AMB, Tw, Tw, Tr, 0.0, 1.0]
            t, Y, M, log = tt_start(y0, t_off=t_rs, hot=True)
            H += _sample(t, Y, M, 2)
            H += _hold(H[-1][0], t_rs + SOAK, H[-1][1])
            ev = [(0.0, 'trip'), (t_stop, 'stopped'), (t_rs, 'restart')] + [(s['t0'], s['name']) for s in log]
            init = 'rating'
        elif c == 'E':
            T50 = 923.15
            y50 = TT.steady(1.0, T50, {}, guess=YR)
            md50 = dict(breaker=True, tit=('const', T50))
            segs = [dict(name='load step 50 -> 100 %', md=dict(breaker=True, tit=('ramp', 0.0, T50, 10.0, TT.TIT_R)), t_end=600.0, max_step=0.1)]
            t, Y, M, log = TT.chain(segs, y50)
            s50 = gas_state(0.0, y50, md50)
            H = [(0.0, s50, md50)] + _sample(t, Y, M, 3); ev = [(0.0, 'load step')]
            H += _hold(H[-1][0], SOAK, H[-1][1]); init = 'half'
        else:
            raise ValueError(c)
        # monotone time, drop duplicates
        HH = []
        for h in H:
            if not HH or h[0] > HH[-1][0] + 1e-6: HH.append(h)
        out[c] = dict(H=HH, events=ev, init=init)
        pickle.dump(out[c], open(cache + '.%d' % os.getpid(), 'wb')); os.replace(cache + '.%d' % os.getpid(), cache)
        print('   case %-4s %5d points, %.0f s, %s' % (c, len(HH), HH[-1][0], ', '.join('%.0f %s' % e for e in ev[:8])), flush=True)
    return out


def boundary_tables(H, zones, cav=None):
    """per zone: sink [C] and h [W/m2K] at the history times, with the oil schedule and the standstill stator lag;
    cav: per history time the cavity air temperatures of the energy balance (None: inflow estimates)"""
    t = np.array([h[0] for h in H]); n = np.array([h[1]['n'] for h in H])
    # oil: running while turning (n > 1 %), post-lube after each stop, off after POST_LUBE
    oil = np.zeros((len(t), 2))
    t_last_turn = -1e9
    for i in range(len(t)):
        if n[i] > 0.01:
            t_last_turn = t[i]; oil[i] = (1.0, 0.0)
        elif t[i] - t_last_turn < POST_LUBE and t_last_turn > -1e8: oil[i] = (0.1, -20.0)
        elif t_last_turn < -1e8: oil[i] = (0.1, -20.0)           # pre-lube before a cold start
        else: oil[i] = (0.0, -20.0)
    out = {}
    for z in zones:
        Ts = np.zeros(len(t)); hs = np.zeros(len(t))
        for i, (ti, s, md) in enumerate(H):
            Ts[i], hs[i] = zone_run(z, s, tuple(oil[i]), cav[i] if cav else None)
        h_ss, tau_ss = zone_standstill(z)
        # stator temperature: lags the running sink (300 s) while turning, decays to the enclosure after the stop
        Tst = np.zeros(len(t)); Tst[0] = Ts[0]
        for i in range(1, len(t)):
            w = min(max(n[i] / 0.10, 0.0), 1.0)
            tgt = w * Ts[i] + (1 - w) * T_ENCL
            tau = 1.0 / (w / 300.0 + (1 - w) / tau_ss)
            dt = t[i] - t[i - 1]
            Tst[i] = tgt + (Tst[i - 1] - tgt) * math.exp(-dt / tau)
        if z in ('P_MOUTH', 'RB_END'):
            run = n > 0.01
            Ts = np.where(run, Ts, Tst); htot = hs
            Tsink = Ts
        else:
            htot = hs + h_ss
            Tsink = (hs * Ts + h_ss * Tst) / np.maximum(htot, 1e-9)
        out[z] = (Tsink, htot)
    return t, out


# ================================================================================================ cavity energy balance
# Low-flow cavities: the air takes heat from the rotor walls, so its temperature is set by an energy balance, not by the
# inflow alone (turbine front cavity: 37 g/s against ~70 W/K of rotor hA). Well-mixed air, adiabatic stator side (lower
# bound of the air temperature, the conservative side for the rim-to-centre gradient of R1):
#   T_air = (m cp T_in + W + sum hA T_wall) / (m cp + sum hA)
# The wall temperatures come from a first transient pass (inflow estimates), corrected by the steady wall response
# dT_wall / dT_air of each cavity (two steady solutions at the rating) -> closed form per time; then the final pass.
CAV_ZONES = dict(FC=('D_FC', 'R1_FF_0', 'R1_FF_1', 'R1_FF_2'),
                 IS=('IS_1_0', 'IS_1_1', 'IS_1_2', 'IS_2_0', 'IS_2_1', 'IS_2_2', 'IS_A', 'TS_FIN', 'R1_RIMA'),
                 R2A=('R2A_0', 'R2A_1', 'R2A_2', 'R2A_A'))
IS_SEAL, IS_EXCHANGE = 0.0168, 3.0                              # interstage seal flow [kg/s] (hot-section calc); no purge: gas
                                                                 # exchange at the two rims taken as 3 x the seal flow
R2A_PURGE = 0.0142                                              # R2 aft cavity purge [kg/s] (a1000_lube_piping), 40 % ingested gas
W_CAV = dict(FC=1500.0, IS=1000.0, R2A=500.0)                     # windage at 15k [W]
CAV_BETA = {}                                                   # steady wall response dT_wall / dT_air (calibrated)


def cavity_inflow(c, s):
    """mass flow [kg/s], inflow temperature [C] and windage [W] of cavity c in state s"""
    n = max(s['n'], 0.0); T_s1 = s['TIT'] - 0.49 * (s['TIT'] - s['Ttex'])
    if c == 'FC': return s['m85'], s['Tcd'], W_CAV['FC'] * n ** 3
    if c == 'IS':
        if PURGE['on']:
            g = PURGE['ingest']; mp = PURGE['frac'] * s['mc']
            return mp / (1 - g), (1 - g) * (s['Tcd'] + PURGE['pickup']) + g * T_s1, W_CAV['IS'] * n ** 3
        return IS_EXCHANGE * IS_SEAL * s['mt'] / REF['mt'], T_s1, W_CAV['IS'] * n ** 3
    T_b = s['Tcd'] + 45.0
    return R2A_PURGE * s['PA'] / REF['PA'] / 0.6, T_b + 0.4 * (s['Ttex'] - T_b), W_CAV['R2A'] * n ** 3


def zone_faces(M):
    """per cavity zone: (element index, face, r-scaling factor, area m2) of its film faces"""
    out = {}
    for (i, f, rg, r, x, L) in M['free']:
        z = zone_of(M['regions'][rg], r, x)
        if z is None or not any(z in v for v in CAV_ZONES.values()): continue
        fac = (r / zone_rref(z)) ** 0.6 if zone_disc(z) else 1.0
        out.setdefault(z, []).append((i, f, fac, 2 * math.pi * r * L * 1e-6))
    return out


def wall_temps(M, Tn, faces):
    """area x h-factor weighted surface temperature of each cavity zone for nodal fields Tn [k x N]: {z: (A_eff, T[k])}"""
    out = {}
    E = M['E']
    for z, lst in faces.items():
        num = 0.0; A = 0.0
        for i, f, fac, a in lst:
            p, q, m = [(0, 1, 3), (1, 2, 4), (2, 0, 5)][f - 1]
            Tf = (Tn[:, E[i, p]] + Tn[:, E[i, q]] + 4 * Tn[:, E[i, m]]) / 6.0
            num = num + fac * a * Tf; A += fac * a
        out[z] = (A, num / A)
    return out


def cavity_air(H, walls_t, walls, oil=None):
    """cavity air temperature per history time: walls = {z: (A_eff, T_wall at walls_t)} of the first pass; its own air
    temperatures are recomputed from the inflow estimates, and the walls follow the change with CAV_BETA"""
    out = []
    for i, (t, s, md) in enumerate(H):
        d = {}
        for c, zs in CAV_ZONES.items():
            m, Tin, W = cavity_inflow(c, s)
            hA = 0.0; hAT = 0.0; Ta1 = None; Tws = []
            for z in zs:
                if z not in walls: continue
                T1, h = zone_run(z, s, (1.0, 0.0))
                Ta1 = T1 if Ta1 is None else Ta1
                A, Tw = walls[z]; Twz = float(np.interp(t, walls_t, Tw)); Tws.append(Twz)
                hA += h * A; hAT += h * A * Twz
            if hA + m * CP_AIR < 1e-6 or Ta1 is None: continue
            b = CAV_BETA.get(c, 0.0); mc = m * CP_AIR
            T0 = (mc * Tin + W + hAT) / (mc + hA)                        # walls as in the first pass
            # T_air (m cp + hA (1 - b)) = m cp T_in + W + sum hA (T_w1 - b T_a1); ill-conditioned at low flow (standstill: the
            # air does not matter there, h -> 0): blend to T0 below 30 % of the design flow, keep within the wall / inflow range
            Tb = (mc * Tin + W + hAT - b * hA * Ta1) / (mc + hA * (1 - b))
            w = min(max(m / (0.3 * REF['cav_m'][c]), 0.0), 1.0)
            lo, hi = min([Tin] + Tws) - 50.0, max([Tin] + Tws) + 150.0
            d[c] = min(max(w * Tb + (1 - w) * T0, lo), hi)
        out.append(d)
    return out


def calibrate_cavities(M, tag, threads=4):
    """steady wall response of each cavity at the rating: steady solution with the inflow estimates, the energy balance
    on its walls, a second steady solution with that air -> CAV_BETA; a third solution checks the converged air"""
    H0 = histories(['C1'])['C1']['H'][0]
    Hs = [H0, (1.0, H0[1], H0[2])]
    zones = sorted(set(z for (i, f, rg, r, x, L) in M['free'] for z in [zone_of(M['regions'][rg], r, x)] if z))
    faces = zone_faces(M)
    def run(k, cav):
        job = 'p5_cal%d%s' % (k, tag)
        t, BC = boundary_tables(Hs, zones, [cav, cav] if cav else None)
        write_thermal(os.path.join(WORK, job + '.inp'), M, 'steady', t, BC, 'rating', [], [])
        run_parallel([job], WORK, threads, 1)
        tt, ids, T = read_nt(os.path.join(WORK, job + '.frd'))
        Tn = np.zeros((1, len(M['ids']))); Tn[0, M['pos'][ids]] = T[-1]
        w = wall_temps(M, Tn, faces)
        return {z: (A, np.array([T_[0], T_[0]])) for z, (A, T_) in w.items()}
    tw = np.array([0.0, 1e9])
    ta0 = {c: zone_run(zs[0], H0[1], (1.0, 0.0))[0] for c, zs in CAV_ZONES.items()}
    CAV_BETA.clear()
    w0 = run(0, None)
    cav1 = cavity_air(Hs[:1], tw, w0)[0]
    w1 = run(1, cav1)
    beta = {}
    for c, zs in CAV_ZONES.items():
        num = den = 0.0
        for z in zs:
            if z not in w0: continue
            h = zone_run(z, H0[1], (1.0, 0.0))[1] * w0[z][0]
            num += h * (w1[z][1][0] - w0[z][1][0]); den += h
        beta[c] = min(max(num / den / (cav1[c] - ta0[c]), 0.0), 0.95) if abs(cav1[c] - ta0[c]) > 1.0 else 0.0
    CAV_BETA.update(beta)
    cav2 = cavity_air(Hs[:1], tw, w0)[0]                        # converged estimate (linear wall response)
    w2 = run(2, cav2)
    CAV_BETA.clear(); chk = cavity_air(Hs[:1], tw, w2)[0]; CAV_BETA.update(beta)   # balance on the walls of run 2
    out = dict(inflow=ta0, balance_1=cav1, beta=beta, converged=cav2, check=chk)
    print('   cavities%s: inflow %s -> balance %s; wall response %s; converged %s (check %s)' % (
        tag, *[' / '.join('%s %.0f' % (c, v) for c, v in d.items()) for d in (ta0, cav1, beta, cav2, chk)]), flush=True)
    json.dump(out, open(os.path.join(WORK, 'cavcal%s.json' % tag), 'w'), indent=1, default=float)
    return out


# ================================================================================================ ccx thermal input
def write_thermal(path, M, case, t, BC, init, steps, tpoints):
    """transient heat transfer input: materials, film zones with sink / film amplitudes (total time, shifted by 1 s for
    the initial steady step), steps with their maximum increment, nodal temperature output at tpoints"""
    mats = element_materials(M)
    ids, E = M['ids'], M['elems']
    lines = ['*HEADING', 'AURORA-1000 rotor transient heat, case %s' % case, '*NODE, NSET=NALL']
    lines += ['%d, %.5f, %.5f' % (i, r, x) for i, (r, x) in zip(ids, M['nodes'])]
    for m in sorted(set(mats)):
        sel = np.where(mats == m)[0]
        lines.append('*ELEMENT, TYPE=CAX6, ELSET=E_%s' % m.replace('-', ''))
        lines += ['%d, %s' % (k + 1, ', '.join(map(str, E[k]))) for k in sel]
    TT_ = np.array([20, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100], dtype=float)
    bm = band_members()
    for m in sorted(set(mats)):
        lines.append('*MATERIAL, NAME=%s' % m.replace('-', ''))
        if m.startswith('AIR'):
            lines.append('*CONDUCTIVITY'); lines += ['%.5f, %.1f' % (k_cavity(m, T), T) for T in TT_]
            lines += ['*SPECIFIC HEAT', '%.4e' % (1010.0 * 1e6), '*DENSITY', '%.4e' % (2.0e-12)]
        else:
            ms = bm[m[5:]] if m.startswith('BAND_') else (m, m)
            kf = 0.4 if m.startswith('BAND_') else 1.0
            th = [THERM[x] for x in ms]
            lines.append('*CONDUCTIVITY')
            lines += ['%.4f, %.1f' % (kf * 0.5 * sum(tab(q, 'k', T) for q in th), T) for T in TT_]
            lines.append('*SPECIFIC HEAT')
            lines += ['%.4e, %.1f' % (0.5 * sum(tab(q, 'cp', T) for q in th) * 1e6, T) for T in TT_]
            lines += ['*DENSITY', '%.4e' % (0.5 * sum(q['rho'] for q in th) * 1e-12)]
        lines.append('*SOLID SECTION, ELSET=E_%s, MATERIAL=%s' % (m.replace('-', ''), m.replace('-', '')))
    lines.append('*ELSET, ELSET=EALL')
    lines += ['E_%s,' % m.replace('-', '') for m in sorted(set(mats))]
    if init == 'cold':
        lines += ['*INITIAL CONDITIONS, TYPE=TEMPERATURE', 'NALL, %.2f' % T_AMB]
    else:
        lines += ['*INITIAL CONDITIONS, TYPE=TEMPERATURE', 'NALL, 300.0']
    ta = np.concatenate([[0.0], t + 1.0])
    for z, (Ts, hs) in BC.items():
        href = max(float(np.max(hs)), 1.0)
        lines.append('*AMPLITUDE, NAME=S_%s, TIME=TOTAL TIME' % z)
        vals = np.concatenate([[Ts[0]], Ts])
        lines += [', '.join('%.3f, %.3f' % (a, b) for a, b in zip(ta[k:k + 4], vals[k:k + 4])) for k in range(0, len(ta), 4)]
        lines.append('*AMPLITUDE, NAME=H_%s, TIME=TOTAL TIME' % z)
        vals = np.concatenate([[hs[0]], hs]) / href
        lines += [', '.join('%.3f, %.5f' % (a, b) for a, b in zip(ta[k:k + 4], vals[k:k + 4])) for k in range(0, len(ta), 4)]
        BC[z] = (Ts, hs, href)
    lines.append('*TIME POINTS, NAME=TP, TIME=TOTAL TIME')
    tp = sorted(set([1.0] + [round(x + 1.0, 3) for x in tpoints]))   # unique: a repeated point stops ccx (zero increment)
    ends = np.array([e for e, _ in steps] + [1.0])              # no point just off a step boundary (tiny increments)
    tp = [p_ for p_ in tp if not np.any((np.abs(ends - p_) > 1e-6) & (np.abs(ends - p_) < 0.5))]
    lines += [', '.join('%.3f' % v for v in tp[k:k + 8]) for k in range(0, len(tp), 8)]
    films = {}
    for (i, f, rg, r, x, L) in M['free']:
        z = zone_of(M['regions'][rg], r, x)
        if z is None: continue
        fac = (r / zone_rref(z)) ** 0.6 if zone_disc(z) else 1.0
        films.setdefault(z, []).append((i + 1, f, fac))
    def film_block():
        b = []
        for z, lst in films.items():
            href = BC[z][2]
            b.append('*FILM, AMPLITUDE=S_%s, FILM AMPLITUDE=H_%s' % (z, z))
            b += ['%d, F%d, 1.0, %.6e' % (e, f, href * fac * 1e-3) for e, f, fac in lst]
        return b
    if init != 'cold':
        lines += ['*STEP, INC=100', '*HEAT TRANSFER, STEADY STATE', '1.0, 1.0']
        lines += film_block()
        lines += ['*NODE FILE, TIME POINTS=TP', 'NT', '*END STEP']
    t_prev = 0.0 if init == 'cold' else 1.0
    for k, (t1, dtmax) in enumerate(steps):
        lines += ['*STEP, INC=100000', '*HEAT TRANSFER, DELTMX=%.1f' % STEP_DELTMX[0],
                  '%.4f, %.4f, %.2e, %.4f' % (min(0.01, dtmax) if k == 0 else dtmax, t1 - t_prev, 1e-6, dtmax)]   # ccx cuts back
                                                                 # on DELTMX; a small first increment in every step costs ~10
        if k == 0 and init == 'cold': lines += film_block()
        lines += ['*NODE FILE, TIME POINTS=TP', 'NT', '*END STEP']
        t_prev = t1
    open(path, 'w').write('\n'.join(lines) + '\n')
    return films


STEP_DELTMX = [10.0]


def step_plan(t_end, events, fac=2.0):
    """(end time, max increment) of the transient steps: fast after every event, coarse in holds"""
    marks = []
    for m_ in sorted(set([0.0] + [e[0] for e in events] + [t_end])):   # merge events closer than 1 s
        if not marks or m_ - marks[-1] >= 1.0: marks.append(m_)
    if marks[-1] < t_end: marks[-1] = t_end
    steps = []
    for k, te in enumerate(marks[:-1]):
        nxt = marks[k + 1]
        for dt_end, dtmax in ((5.0, 0.25), (40.0, 1.0), (400.0, 5.0), (1500.0, 20.0), (1e9, 90.0)):
            e = min(te + dt_end, nxt)
            if e > (steps[-1][0] if steps else 0.0) + 1e-6: steps.append((e, dtmax * fac))
            if e >= nxt: break
    return [(round(t1 + 1.0, 3), d) for t1, d in steps]           # same rounding as the time points (a point 1e-4 s after a
                                                                 # step start forces a tiny first increment)


def out_points(t_end, events):
    rel = [0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180, 240, 300, 360, 450, 600, 750, 900, 1200, 1500, 1800,
           2400, 3000, 3600, 4500, 5400, 7200, 9000, 10800, 12600, 14400]
    pts = set()
    for te, _ in [(0.0, '')] + list(events):
        for r in rel:
            if te + r <= t_end: pts.add(round(te + r, 3))
    pts.add(round(t_end, 3))
    # drop points within 0.5 s of another (event clusters): each one would cut an increment
    out = []
    for p_ in sorted(pts):
        if not out or p_ - out[-1] >= 0.5: out.append(p_)
    return out


# ================================================================================================ running ccx
def ccx_env(threads):
    return dict(os.environ, OMP_NUM_THREADS=str(threads), CCX_NPROC_EQUATION_SOLVER=str(threads))


def run_parallel(jobs, cwd, threads, max_par):
    """run ccx jobs (input names without .inp) max_par at a time; returns {job: seconds}"""
    import subprocess
    todo, run, done = list(jobs), {}, {}
    while todo or run:
        while todo and len(run) < max_par:
            j = todo.pop(0)
            log = open(os.path.join(cwd, j + '.log'), 'w')
            run[j] = (subprocess.Popen(['nice', '-n', '5', F.CCX, '-i', j], cwd=cwd, env=ccx_env(threads), stdout=log,
                                       stderr=subprocess.STDOUT), time.time(), log)
        for j in list(run):
            p, t0, log = run[j]
            if p.poll() is not None:
                log.close(); done[j] = time.time() - t0; del run[j]
                txt = open(os.path.join(cwd, j + '.log')).read()
                ok = 'Job finished' in txt
                print('   ccx %-28s %s in %.0f s' % (j, 'done' if ok else 'FAILED', done[j]), flush=True)
                if not ok: print(txt[-2500:])
        time.sleep(2.0)
    return done


def read_nt(path):
    """nodal temperatures of every result block of an frd: (times, node ids, T [k x N])"""
    times, blocks, ids = [], [], None
    with open(path) as f:
        cur = None; nid = []
        for line in f:
            if line.startswith('  100CL'):
                times.append(float(line[12:25])); cur = []; nid = []
                continue
            if cur is None: continue
            if line.startswith(' -1'):
                cur.append(line[13:25])
                if ids is None: nid.append(int(line[3:13]))
            elif line.startswith(' -3'):
                blocks.append(np.array(cur, dtype=float))
                if ids is None: ids = np.array(nid)
                cur = None
    return np.array(times), ids, np.vstack(blocks)


# ================================================================================================ post: derived histories
def sparse_avg(M):
    """element mean temperature = mean of the three mid-side nodes (exact area average of the quadratic field)"""
    from scipy.sparse import csr_matrix
    E = M['E']; m = len(E)
    rows = np.repeat(np.arange(m), 3); cols = E[:, 3:6].reshape(-1)
    return csr_matrix((np.full(3 * m, 1.0 / 3.0), (rows, cols)), shape=(m, len(M['ids'])))


def emat_mech(M):
    """per element: mechanical material key (part material, 'BAND_<joint>', or None for gas)"""
    out = []
    for rg in M['ereg']:
        name = M['regions'][rg]
        out.append(None if name.startswith('air') else ('BAND_' + name[5:] if name.startswith('band') else PART_MAT[name]))
    return out


def eps_th(mat, T):
    """mean thermal strain from 20 C (vectorised); bands: mean of the two members"""
    if mat.startswith('BAND_'):
        a, b = band_members()[mat[5:]]
        return 0.5 * (eps_th(a, T) + eps_th(b, T))
    q = MECH[mat]
    return np.interp(T, q['T'], q['a']) * (T - 20.0)


def E_of(mat, T):
    if mat.startswith('BAND_'):
        a, b = band_members()[mat[5:]]
        return 0.5 * (E_of(a, T) + E_of(b, T))
    q = MECH[mat]
    return np.interp(T, q['T'], q['E'])


def load_paths(M):
    """element selections and x-bins of the bolt grip, the compressor stack load path and the three stud lines"""
    cen, vol, mats = M['cen'], M['vol'], emat_mech(M)
    reg = np.array([M['regions'][k] for k in M['ereg']])
    r, x = cen[:, 0], cen[:, 1]
    x_nut, x_thr = G.TIE['x_nut'][1], G.TIE['x_end'] - G.TIE['thread_len'] / 2
    lp = dict(stub=48.0, imp1=70.0, spacer=72.0, imp2=75.0, drum=85.0)
    P = {}
    sel_b = np.where((reg == 'bolt') & (x > x_nut) & (x < x_thr))[0]
    in_lp = np.array([(rg in lp and rr <= lp[rg]) or (rg.startswith('band_') and rg[5:] in COMP_J) for rg, rr in zip(reg, r)])
    sel_s = np.where(in_lp & (x > x_nut) & (x < x_thr))[0]
    P['bolt'] = (sel_b, x_nut, x_thr); P['stack'] = (sel_s, x_nut, x_thr)
    J = joints(); xn = {k: v[2] for k, v in G.STUD_SETS.items()}
    grips = {'drum_R1': (G.STUD_SETS['drum - R1'][0], xn['drum - R1']), 'R1_R2': (xn['R1 - R2'], G.STUD_SETS['R1 - R2'][1]),
             'R2_stub': (xn['R2 - rear stub'], G.STUD_SETS['R2 - rear stub'][1])}
    for j, (x0, x1) in grips.items():
        sel = np.where((np.abs(r - G.STUD['r']) < 5.0) & (x > x0) & (x < x1) & np.array([m is not None for m in mats]))[0]
        P['stud_' + j] = (sel, x0, x1)
    return P, mats


def bin_strain(sel, x0, x1, Te, M, mats, dx=2.0):
    """free axial growth [mm] and compliance factor sum(dx / (E A)) [mm/N] of a load path from element temperatures"""
    x = M['cen'][sel, 1]; vol = M['vol'][sel]
    nb = max(int(round((x1 - x0) / dx)), 1); b = np.clip(((x - x0) / (x1 - x0) * nb).astype(int), 0, nb - 1)
    ms = [mats[i] for i in sel]
    eps = np.zeros(len(sel)); Ee = np.zeros(len(sel))
    for m in set(ms):
        k = np.array([mm == m for mm in ms])
        eps[k] = eps_th(m, Te[sel[k]]); Ee[k] = E_of(m, Te[sel[k]])
    V = np.bincount(b, vol, nb); Ve = np.bincount(b, vol * eps, nb); VE = np.bincount(b, vol * Ee, nb)
    L = (x1 - x0) / nb
    ok = V > 0
    d = float(np.sum(Ve[ok] / V[ok]) * L)
    # section area = V / L, mean modulus VE / V: compliance L / (E A) = L^2 / VE
    c = float(np.sum(L * L / VE[ok]))
    Tm = float(np.sum(Te[sel] * vol) / np.sum(vol))
    return d, c, Tm


def probes(M):
    """element indices for the temperature probes (disc rims / centres, impeller bores / tips, joints)"""
    cen = M['cen']; reg = np.array([M['regions'][k] for k in M['ereg']])
    def near(region, r, x):
        k = np.where(reg == region)[0]
        return int(k[np.argmin((cen[k, 0] - r) ** 2 + (cen[k, 1] - x) ** 2)])
    xm1, xm2 = 0.5 * sum(G.HUB['R1']), 0.5 * sum(G.HUB['R2'])
    rh1, rh2 = A.row_radius('R1', 0.0), A.row_radius('R2', 0.0)
    return dict(R1_rim=near('R1', rh1 - 3, xm1), R1_web=near('R1', 150.0, xm1), R1_centre=near('R1', 2.0, xm1),
                R2_rim=near('R2', rh2 - 3, xm2), R2_web=near('R2', 150.0, xm2), R2_centre=near('R2', 2.0, xm2),
                I1_bore=near('imp1', 25.0, 270.0), I1_tip=near('imp1', 205.0, 324.0), I2_bore=near('imp2', 25.0, 450.0),
                I2_tip=near('imp2', 230.0, 509.0), drum=near('drum', 78.0, 560.0), bulkhead=near('drum', 40.0, 608.0),
                stub=near('stub', 35.0, 150.0), bolt_mid=near('bolt', 7.0, 400.0), bolt_front=near('bolt', 7.0, 100.0),
                bolt_aft=near('bolt', 7.0, 560.0), tspc=near('tspc', 76.0, 0.5 * (G.X_J['R1_spc'] + G.X_J['spc_R2'])),
                rstub_j2=near('rstub', 40.0, G.X_BRG[1]))


def lag(t, y, tau):
    out = np.array(y, dtype=float)
    for i in range(1, len(t)):
        a = math.exp(-(t[i] - t[i - 1]) / tau); out[i] = y[i] + (out[i - 1] - y[i]) * a
    return out


STUD_AS = 61.2                                                  # MJ10x1.25 stress area [mm2]
STUD_TAU = 45.0                                                 # stud in its hole (0.25 mm gap, threads, nut face) [s]


GRIP = dict(drum_R1=('drum_R1',), R1_R2=('R1_spc', 'spc_R2'), R2_stub=('R2_stub',))


def grip_material(j, x):
    """clamped member at axial position x of a hot joint's grip (by geometry, not by mesh): curvic band, else the part"""
    J = joints()
    for b in GRIP[j]:
        xb, a, c, _, _, _, h = J[b]
        if abs(x - xb) <= h / 2: return 'BAND_' + b
    if j == 'drum_R1': return 'IN718' if x < J['drum_R1'][0] else 'MAR-M247'
    if j == 'R2_stub': return 'MAR-M247' if x < J['R2_stub'][0] else 'IN718'
    return 'MAR-M247' if (x < J['R1_spc'][0] or x > J['spc_R2'][0]) else PART_MAT['tspc']


def stud_model(j, t, Te_hist, P, M, mats, dx=0.5):
    """stud preload [N] per stud vs time: members' free growth = sum over 0.5 mm x-bins of the grip (material by position,
    temperature = volume mean of the FE elements at r 76 +- 5 in the bin), stud = grip mean temperature lagged"""
    sel, x0, x1 = P['stud_' + j]
    Lg = x1 - x0
    nb = int(round(Lg / dx)); xc = x0 + (np.arange(nb) + 0.5) * Lg / nb
    xe = M['cen'][sel, 1]; b = np.clip(((xe - x0) / Lg * nb).astype(int), 0, nb - 1); vol = M['vol'][sel]
    V = np.bincount(b, vol, nb); ok = V > 0
    bm = [grip_material(j, x) for x in xc]
    dm, Ts = [], []
    for Te in Te_hist:
        Tb = np.bincount(b, vol * Te[sel], nb)
        Tb = np.interp(xc, xc[ok], Tb[ok] / V[ok])               # bins without an element centroid: interpolated
        dm.append(sum(float(eps_th(m, T)) for m, T in zip(bm, Tb)) * Lg / nb); Ts.append(float(Tb.mean()))
    dm, Ts = np.array(dm), np.array(Ts)
    Tst = lag(t, Ts, STUD_TAU)
    sm = stud_mat(j)
    ds = eps_th(sm, Tst) * Lg
    ks = E_of(sm, Tst) * STUD_AS / (Lg + 0.8 * G.STUD['d']); km = KM_FAC * ks
    ks0 = E_of(sm, 20.0) * STUD_AS / (Lg + 0.8 * G.STUD['d']); km0 = KM_FAC * ks0
    F0 = stud_pre(j) * 1e3; d0 = F0 * (1 / ks0 + 1 / km0)
    Fs = (d0 - ds + dm) / (1 / ks + 1 / km)
    return dict(F=Fs, T_stud=Tst, T_grip=Ts, Lg=Lg)


KM_FAC = 3.0                                                    # member / stud stiffness (stack model; phase 4 replaces it)


def stud_mat(j): return CFG['r12'] if j == 'R1_R2' else 'IN718'
def stud_pre(j): return CFG['pre12'] if j == 'R1_R2' else G.STUD['pre_kN']
def stud_relax(j): return CFG['relax12'] if j == 'R1_R2' else RELAX


# ================================================================================================ stress model
K_CURVIC = 2450.0                                               # curvic contact stiffness per band area [N/mm per mm2]
# (stack model: 0.5e-7 mm/N per compressor curvic contact = 2e7 N/mm on ~8,200 mm2); phase 4 values replace it per joint
K_JOINT = {}


def load_joint_stiffness():
    """phase 4 interface stiffnesses (sim/engine/fea/a1000_joint_fea.json, toothed joint minus a solid band, mean of cold
    and 15k) [N/mm] per curvic band; R1_R2 has two faces in series"""
    jf = os.path.join(HERE, 'fea', 'a1000_joint_fea.json')
    if not os.path.exists(jf): return {}
    out = {}
    for name, r in json.load(open(jf)).get('joints', {}).items():
        k = r.get('stiffness', {})
        v = [k[q] for q in ('interface_axial_a', 'interface_axial_b') if q in k and np.isfinite(k[q]) and k[q] > 0]
        if not v: continue
        if name == 'R1_R2': out['R1_spc'] = out['spc_R2'] = 2 * float(np.mean(v))
        else: out[name] = float(np.mean(v))
    return out


K_JOINT.update(load_joint_stiffness())


def band_E2(j):
    x, a, b, (o0, o1), ri, ro, h = joints()[j]
    Ab = math.pi * (ro * ro - ri * ri)
    k = K_JOINT.get(j, K_CURVIC * Ab)
    return k * h / Ab, k


def mech_model(M):
    """mechanical element list (gas removed); the plain shank x 383-423 carries the tie-bolt preload as an initial
    temperature offset of its nodes (a fixed axial shrink, independent of the running temperature)"""
    mats = emat_mech(M)
    keep = [i for i, m in enumerate(mats) if m is not None]
    reg = [M['regions'][M['ereg'][i]] for i in range(len(mats))]
    pre = [i for i in keep if reg[i] == 'bolt' and PRE_SEG[0] <= M['cen'][i, 1] <= PRE_SEG[1]]
    for i in pre: mats[i] = 'BOLTPRE'
    pre_nodes = sorted(set(M['elems'][pre].reshape(-1)))
    used = sorted(set(M['elems'][keep].reshape(-1)))
    return dict(keep=keep, E=M['elems'], mats=mats, reg=reg, used=used, pre_nodes=pre_nodes, OFF=10_000_000)


PRE_SEG = (383.0, 423.0)                                        # preload segment of the shank (between the lands at 353 / 446)
ALPHA_PRE = 13.2e-6                                             # its constant expansion coefficient (IN718 at ~200 C)


def write_mech(path, M, MM, T_node, n_speed, delta, out_sets=True):
    """static: temperatures (T_node over the thermal node ids), centrifugal + blade pulls at speed fraction n_speed,
    tie-bolt closure delta [mm]: axial shrink of the preload segment (initial temperature offset delta / (alpha L))"""
    ids, nodes = M['ids'], M['nodes']; pos = M['pos']
    om = n_speed * OM_D
    L = ['*HEADING', 'AURORA-1000 rotor static', '*NODE, NSET=NALL']
    def xy(n):
        base = n - MM['OFF'] if n >= MM['OFF'] else n
        return nodes[pos[base]]
    for n in MM['used']:
        r, x = xy(n); L.append('%d, %.5f, %.5f' % (n, r, x))
    groups = {}
    for i in MM['keep']: groups.setdefault(MM['mats'][i], []).append(i)
    for m, lst in groups.items():
        L.append('*ELEMENT, TYPE=CAX6, ELSET=M_%s' % m.replace('-', ''))
        L += ['%d, %s' % (i + 1, ', '.join(map(str, MM['E'][i]))) for i in lst]
    L.append('*ELSET, ELSET=EALL'); L += ['M_%s,' % m.replace('-', '') for m in groups]
    bolt_el = [i for i in MM['keep'] if MM['reg'][i] == 'bolt']
    L.append('*ELSET, ELSET=EBOLT'); L += ['%d,' % (i + 1) for i in bolt_el]
    band_el = [i for i in MM['keep'] if MM['reg'][i].startswith('band')]
    L.append('*ELSET, ELSET=EBAND'); L += ['%d,' % (i + 1) for i in band_el]
    for m in groups:
        L.append('*MATERIAL, NAME=%s' % m.replace('-', ''))
        if m == 'BOLTPRE':
            q = MECH['IN718']
            L.append('*ELASTIC'); L += ['%.1f, %.3f, %.1f' % (e, q['nu'], T) for e, T in zip(q['E'], q['T'])]
            L += ['*EXPANSION, ZERO=20.', '%.4e' % ALPHA_PRE, '*DENSITY', '%.4e' % (THERM['IN718']['rho'] * 1e-12)]
        elif m.startswith('BAND_'):
            j = m[5:]; a, b = band_members()[j]; E2, _ = band_E2(j)
            L.append('*ELASTIC, TYPE=ENGINEERING CONSTANTS')
            for T in (20.0, 300.0, 600.0, 900.0):
                Em = float(E_of(m, T))
                L.append('%.1f, %.1f, %.1f, 0.10, 0.10, 0.10, %.1f, %.1f' % (0.3 * Em, E2, 0.3 * Em, 0.005 * Em, 0.01 * Em))
                L.append('%.1f, %.1f' % (0.01 * Em, T))
            Ts = [20.0, 200.0, 400.0, 600.0, 800.0]
            L.append('*EXPANSION, ZERO=20.'); L += ['%.4e, %.1f' % (0.5 * (np.interp(T, MECH[a]['T'], MECH[a]['a']) + np.interp(T, MECH[b]['T'], MECH[b]['a'])), T) for T in Ts]
            L += ['*DENSITY', '%.4e' % (0.5 * (THERM[a]['rho'] + THERM[b]['rho']) * 1e-12)]
        else:
            q = MECH[m]
            L.append('*ELASTIC'); L += ['%.1f, %.3f, %.1f' % (e, q['nu'], T) for e, T in zip(q['E'], q['T'])]
            L.append('*EXPANSION, ZERO=20.'); L += ['%.4e, %.1f' % (a, T) for a, T in zip(q['a'], q['T'])]
            L += ['*DENSITY', '%.4e' % (THERM[m]['rho'] * 1e-12)]
        L.append('*SOLID SECTION, ELSET=M_%s, MATERIAL=%s' % (m.replace('-', ''), m.replace('-', '')))
    # boundary: axis nodes radial, one collar node axial; preload segment nodes start at 20 C + the closure offset
    axis = [n for n in MM['used'] if xy(n)[0] < 1e-6]
    collar = min(MM['used'], key=lambda n: (xy(n)[1] - 0.5 * (G.COLLAR['x0'] + G.COLLAR['x1'])) ** 2 + (xy(n)[0] - 60.0) ** 2)
    L.append('*BOUNDARY'); L += ['%d, 1, 1, 0.' % n for n in axis] + ['%d, 2, 2, 0.' % collar]
    dT = delta / (ALPHA_PRE * (PRE_SEG[1] - PRE_SEG[0]))
    L += ['*INITIAL CONDITIONS, TYPE=TEMPERATURE', 'NALL, 20.'] + ['%d, %.4f' % (n, 20.0 + dT) for n in MM['pre_nodes']]
    L += ['*STEP', '*STATIC']
    if om > 0:
        L += ['*DLOAD', 'EALL, CENTRIF, %.6e, 0., 0., 0., 0., 1., 0.' % om ** 2]
        cl = blade_loads(M, MM, om)
        L.append('*CLOAD'); L += ['%d, 1, %.4f' % (k, v) for k, v in cl.items()]
    L.append('*TEMPERATURE')
    for n in MM['used']:
        base = n - MM['OFF'] if n >= MM['OFF'] else n
        L.append('%d, %.3f' % (n, T_node[pos[base]]))
    L += ['*NODE FILE', 'U', '*EL FILE', 'S']
    if out_sets: L += ['*EL PRINT, ELSET=EBOLT', 'S', '*EL PRINT, ELSET=EBAND', 'S']
    L += ['*END STEP']
    open(path, 'w').write('\n'.join(L) + '\n')


_BLADE = {}


def blade_loads(M, MM, om):
    """radial nodal forces of the blades: turbine blade pulls on the platform top (as a1000_disc_fea), impeller blades
    (impeller mass - hub ring) spread along the hub flow surface by length, acting 10 mm above the hub line"""
    if not _BLADE:
        R = G._R; ids, nodes = M['ids'], M['nodes']
        out = {}
        for reg_name, zpre, key in (('imp1', 'I1_HUB_', 'impeller1'), ('imp2', 'I2_HUB_', 'impeller2')):
            V, _ = G.poly_area_props(R['discs'][key]['poly']); mb = R['discs'][key]['m'] - V * 1e-9 * THERM['Ti64']['rho']
            edges = [(i, f, r, x, Ln) for (i, f, rg, r, x, Ln) in M['free'] if M['regions'][rg] == reg_name and (zone_of(reg_name, r, x) or '').startswith(zpre)]
            Ltot = sum(e[4] for e in edges)
            for i, f, r, x, Ln in edges:
                e = M['elems'][i]; p, q, m_ = [(0, 1, 3), (1, 2, 4), (2, 0, 5)][f - 1]
                dm = mb * Ln / Ltot
                for nid, w in ((e[p], 1 / 6), (e[q], 1 / 6), (e[m_], 2 / 3)):
                    out[int(nid)] = out.get(int(nid), 0.0) + w * dm * (r + 10.0) * 1e-3
        for row in ('R1', 'R2'):
            m_b = DF.PARTS['A1000_%s_blade' % row]['mass_kg']; Z = A.Z[row]
            rh, rt = A.row_radius(row, 0.0), A.row_radius(row, 1.0)
            r_cg = 0.5 * (rh + rt) - 0.10 * (rt - rh)
            edges = [(i, f, r, x, Ln) for (i, f, rg, r, x, Ln) in M['free'] if M['regions'][rg] == row and zone_of(row, r, x) == '%s_PLAT' % row]
            Ltot = sum(e[4] for e in edges)
            for i, f, r, x, Ln in edges:
                e = M['elems'][i]; p, q, m_ = [(0, 1, 3), (1, 2, 4), (2, 0, 5)][f - 1]
                for nid, w in ((e[p], 1 / 6), (e[q], 1 / 6), (e[m_], 2 / 3)):
                    out[int(nid)] = out.get(int(nid), 0.0) + w * Z * m_b * r_cg * 1e-3 * Ln / Ltot
        _BLADE.update(out)
    return {k: v * om * om for k, v in _BLADE.items()}


def read_stress(path, M, MM):
    """frd nodal stresses (6 comps; axisymmetric: 1 radial, 2 axial, 3 hoop, 4 r-x shear) of the thermal node ids"""
    S = np.full((len(M['ids']), 6), np.nan)
    with open(path) as f:
        mode = None
        for line in f:
            if line.startswith(' -4'):
                mode = 'S' if 'STRESS' in line else None; continue
            if mode == 'S':
                if line.startswith(' -1'):
                    n = int(line[3:13])
                    if n >= 99_999_999: continue
                    base = n - MM['OFF'] if n >= MM['OFF'] else n
                    S[M['pos'][base]] = [float(line[13 + 12 * k:25 + 12 * k]) for k in range(6)]
                elif line.startswith(' -3'): mode = None
    return S


def read_el_print(path):
    """*EL PRINT integration-point stresses: {elem: mean of the ip values (6)}"""
    out = {}
    with open(path) as f:
        on = False
        for line in f:
            if 'stresses (elem, integ.pnt.' in line: on = True; continue
            if not on: continue
            p = line.split()
            if len(p) == 8:
                try:
                    out.setdefault(int(p[0]), []).append([float(v) for v in p[2:]])
                except ValueError:
                    pass
    return {k: np.mean(v, axis=0) for k, v in out.items()}


def bolt_force(elp, M):
    """tie-bolt axial force [N]: volume integral of the axial stress over plain-shank elements / length (two segments
    outside the preload segment)"""
    res = []
    for x0, x1 in ((290.0, 330.0), (480.0, 570.0)):
        acc = 0.0
        for e, s in elp.items():
            i = e - 1
            if M['regions'][M['ereg'][i]] != 'bolt': continue
            r, x = M['cen'][i]
            if x0 <= x <= x1: acc += s[1] * M['vol'][i]
        res.append(acc / (x1 - x0))
    return float(np.mean(res)), res


def band_stress(elp, M):
    """per curvic band: axial force [N] (- = compression) and the radial profile of the axial stress (5 bins)"""
    out = {}
    J = joints()
    for j, (x, a, b, (o0, o1), ri, ro, h) in J.items():
        name = 'band_' + j; acc = 0.0; prof = np.zeros(5); w = np.zeros(5)
        for e, s in elp.items():
            i = e - 1
            if M['regions'][M['ereg'][i]] != name: continue
            r = M['cen'][i, 0]; acc += s[1] * M['vol'][i]
            k = min(int((r - ri) / (ro - ri) * 5), 4); prof[k] += s[1] * M['vol'][i]; w[k] += M['vol'][i]
        out[j] = dict(N=acc / h, sigma=list(prof / np.maximum(w, 1e-9)), A=math.pi * (ro * ro - ri * ri))
    return out


# ================================================================================================ stages
CASES = ['A', 'B', 'C1', 'C2', 'C3', 'D15', 'D30', 'D60', 'E', 'AS', 'BS']
CASE_NAME = dict(A='cold start to full load', B='normal stop + standstill', C1='trip, breaker closed, BOV', C2='trip, BOV fails',
                 C3='load rejection + trip (BOV)', D15='hot restart 15 min after trip', D30='hot restart 30 min after trip',
                 D60='hot restart 60 min after trip', E='load step 50 -> 100 %', AS='cold start, operating rule (%.0f min hold at TIT %.0f C, %.0f min ramp)'
                 % (SLOW['hold'] / 60, SLOW['T_hold'] - 273.15, SLOW['ramp'] / 60),
                 BS='normal stop, operating rule (%.0f min unload, %.0f min cool-down at TIT %.0f C)'
                 % (SLOW['unload'] / 60, SLOW['cool'] / 60, SLOW['T_hold'] - 273.15))
HIST_KEYS = ('n', 'mc', 'mt', 'Tcd', 'TIT', 'Ttex', 'T012', 'T21', 'T22', 'Tr')


def stage_thermal(cases, M, tag='', fac_dt=2.0, deltmx=10.0, max_par=9, threads=2, t_cut=None, cav_from=None):
    """heat runs of the cases; cav_from: tag of the first pass whose wall temperatures feed the cavity energy balance"""
    print('2. phase 1 histories', flush=True)
    H = histories(cases)
    faces = zone_faces(M) if cav_from is not None else None
    zones = sorted(set(z for (i, f, rg, r, x, L) in M['free'] for z in [zone_of(M['regions'][rg], r, x)] if z))
    jobs, meta = [], {}
    STEP_DELTMX[0] = deltmx
    for c in cases:
        if t_cut is not None:                                   # convergence checks: the critical window only
            tc = t_cut(H[c]['events']); H[c]['H'] = [h for h in H[c]['H'] if h[0] <= tc]
            H[c]['events'] = [e for e in H[c]['events'] if e[0] < tc]
        cav = None
        if cav_from is not None:
            t1, _, Tn1 = case_fields(c, M, cav_from)
            cav = cavity_air(H[c]['H'], t1, wall_temps(M, Tn1, faces)); del Tn1
        t, BC = boundary_tables(H[c]['H'], zones, cav)
        steps = step_plan(t[-1], H[c]['events'], fac_dt)
        tp = out_points(t[-1], H[c]['events'])
        job = 'p5_%s%s' % (c, tag)
        write_thermal(os.path.join(WORK, job + '.inp'), M, c, t, BC, H[c]['init'], steps, tp)
        jobs.append(job)
        hist = {k: [h[1][k] for h in H[c]['H']] for k in HIST_KEYS}
        cav_t0 = cav[0] if cav else {}
        meta[c] = dict(t=list(t), hist=hist, events=H[c]['events'], init=H[c]['init'], steps=steps, tpoints=tp, cav_t0=cav_t0,
                       cav_beta=dict(CAV_BETA),
                       bc_t0={z: (float(v[0][0]), float(v[1][0])) for z, v in BC.items()},
                       bc_max={z: (float(np.max(v[0])), float(np.max(v[1]))) for z, v in BC.items()})
        print('   %s: %d zones, %d steps, %d output times' % (job, len(BC), len(steps), len(tp)), flush=True)
    mf = os.path.join(WORK, 'meta%s.json' % tag)                # merge: other processes may run other cases of this tag
    allm = json.load(open(mf)) if os.path.exists(mf) else {}
    allm.update(meta); json.dump(allm, open(mf, 'w'), default=float)
    print('3. ccx transient heat (%d jobs, %d at a time x %d threads)' % (len(jobs), max_par, threads), flush=True)
    run_parallel(jobs, WORK, threads, max_par)
    return meta


def case_fields(c, M, tag=''):
    """(case times [s], element temperatures [k x m], nodal temperatures [k x N]) of a finished thermal job"""
    tt, ids, T = read_nt(os.path.join(WORK, 'p5_%s%s.frd' % (c, tag)))
    order = M['pos'][ids]
    Tn = np.zeros((T.shape[0], len(M['ids']))); Tn[:, order] = T
    t = tt - 1.0
    keep = np.r_[True, np.diff(t) > 1e-6]                       # step-end duplicates
    t, Tn = t[keep], Tn[keep]
    S = sparse_avg(M)
    Te = (S @ Tn.T).T
    return t, Te, Tn


def spring_history(c, t, Te, M, P, mats, meta, cal):
    n = np.interp(t, meta[c]['t'], meta[c]['hist']['n'])
    db, cb, Tb, ds, cs, Ts = [], [], [], [], [], []
    for row in Te:
        a = bin_strain(*P['bolt'], row, M, mats); b = bin_strain(*P['stack'], row, M, mats)
        db.append(a[0]); cb.append(a[1]); Tb.append(a[2]); ds.append(b[0]); cs.append(b[1]); Ts.append(b[2])
    db, cb, ds, cs = map(np.array, (db, cb, ds, cs))
    ctot = cal['c_ratio'] * (cb + cs)
    F = (cal['delta0'] + ds - db) / ctot + cal['dF_spin'] * n ** 2 * cal['c0'] / ctot
    return dict(t=t, n=n, F=F, T_bolt=np.array(Tb), T_stack=np.array(Ts), d_bolt=db, d_stack=ds)


def pick_times(c, sh, st, pr, t):
    """critical output times: bolt preload min / max, stud preload min, disc rim - centre extremes, the end state"""
    idx = {0: 'initial state', int(np.argmin(sh['F'])): 'bolt min', int(np.argmax(sh['F'])): 'bolt max', len(t) - 1: 'end'}
    for j, s in st.items(): idx.setdefault(int(np.argmin(s['F'])), 'stud %s min' % j)
    for row in ('R1', 'R2'):
        d = pr['%s_rim' % row] - pr['%s_centre' % row]
        idx.setdefault(int(np.argmax(d)), '%s rim-centre max' % row); idx.setdefault(int(np.argmin(d)), '%s rim-centre min' % row)
    d = pr['I2_tip'] - pr['I2_bore']; idx.setdefault(int(np.argmax(d)), 'I2 tip-bore max'); idx.setdefault(int(np.argmin(d)), 'I2 tip-bore min')
    return dict(sorted(idx.items()))


def manson(mat, d_eps, T, s_max):
    """Manson-Morrow cycles with the 2 / 20 factors (a1000_turbine_checks.manson_cycles) for the rotor materials"""
    if mat == 'MAR-M247': return TC.manson_cycles(d_eps, T, s_max)
    Su = float(np.interp(T, *UTS[mat])); E = float(E_of(mat, T)); D = -math.log(1 - RA[mat]); sm = 0.5 * s_max
    def N_of(de):
        lo, hi = 0.0, 12.0
        for _ in range(80):
            m = 0.5 * (lo + hi); N = 10 ** m
            if 3.5 * (Su - sm) / E * N ** -0.12 + D ** 0.6 * N ** -0.6 > de: lo = m
            else: hi = m
        return 10 ** lo
    return min(N_of(2 * d_eps), N_of(d_eps) / 20)


def vm6(s):
    s = np.asarray(s)
    return np.sqrt(0.5 * ((s[..., 0] - s[..., 1]) ** 2 + (s[..., 1] - s[..., 2]) ** 2 + (s[..., 2] - s[..., 0]) ** 2) + 3 * s[..., 3] ** 2)


def mech_run(jobs, max_par, threads):
    run_parallel([j for j in jobs], WORK, threads, max_par)


def mech_result(job, M, MM):
    elp = read_el_print(os.path.join(WORK, job + '.dat'))
    Fb, seg = bolt_force(elp, M)
    bands = band_stress(elp, M)
    S = read_stress(os.path.join(WORK, job + '.frd'), M, MM)
    return dict(F=Fb, F_seg=seg, bands=bands), S


def stage_mech(M, cases, meta, tag='', max_par=8, threads=2, cal=None):
    """reference runs (assembly, spin), spring histories, critical-time stress runs"""
    MM = mech_model(M); P, mats = load_paths(M); PI = probes(M)
    T20 = np.full(len(M['ids']), 20.0)
    F0 = G.TIE['pre_kN'] * 1e3
    if cal is None:
        print('4. stress model: references', flush=True)
        write_mech(os.path.join(WORK, 'm_asm1.inp'), M, MM, T20, 0.0, 1.0)
        mech_run(['m_asm1'], 1, 8)
        F1 = mech_result('m_asm1', M, MM)[0]['F']
        d0 = F0 / F1
        for job, n in (('m_asm', 0.0), ('m_spin', 1.0), ('m_trip', RS.N_TRIP / RS.N_OP)):
            write_mech(os.path.join(WORK, job + '.inp'), M, MM, T20, n, d0)
        mech_run(['m_asm', 'm_spin', 'm_trip'], 3, 4)
        R = {j: mech_result(j, M, MM) for j in ('m_asm', 'm_spin', 'm_trip')}
        for j, (r, S) in R.items(): np.save(os.path.join(WORK, j + '_S.npy'), S.astype(np.float32))
        Te20 = np.full(len(M['elems']), 20.0)
        cb0 = bin_strain(*P['bolt'], Te20, M, mats)[1]; cs0 = bin_strain(*P['stack'], Te20, M, mats)[1]
        cal = dict(F1=F1, delta0=d0, c0=d0 / F0, c_ratio=(d0 / F0) / (cb0 + cs0), F_asm=R['m_asm'][0]['F'], F_spin=R['m_spin'][0]['F'],
                   F_trip=R['m_trip'][0]['F'], dF_spin=R['m_spin'][0]['F'] - R['m_asm'][0]['F'], bands_asm=R['m_asm'][0]['bands'],
                   bands_spin=R['m_spin'][0]['bands'], bands_trip=R['m_trip'][0]['bands'], cb0=cb0, cs0=cs0,
                   k_bolt_model=1 / cb0, k_stack_model=1 / cs0)
        print('   closure %.4f mm for %.0f kN (FE compliance %.3e mm/N; bins %.3e); 15k spin %+.1f kN, trip speed %+.1f kN' % (
            d0, F0 / 1e3, cal['c0'], cb0 + cs0, cal['dF_spin'] / 1e3, (cal['F_trip'] - cal['F_asm']) / 1e3), flush=True)
    print('5. preload histories and critical times', flush=True)
    out, jobs, crit = {}, [], {}
    for c in cases:
        t, Te, Tn = case_fields(c, M, tag)
        sh = spring_history(c, t, Te, M, P, mats, meta, cal)
        st = {j: stud_model(j, t, Te, P, M, mats) for j in ('drum_R1', 'R1_R2', 'R2_stub')}
        pr = {k: Te[:, i] for k, i in PI.items()}
        picks = pick_times(c, sh, st, pr, t)
        crit[c] = []
        for k, label in picks.items():
            job = 'm_%s%s_%03d' % (c, tag, k)
            write_mech(os.path.join(WORK, job + '.inp'), M, MM, Tn[k], float(sh['n'][k]), cal['delta0'])
            jobs.append(job); crit[c].append(dict(job=job, k=int(k), t=float(t[k]), n=float(sh['n'][k]), label=label))
        out[c] = dict(t=t, sh=sh, st=st, pr=pr)
        print('   %-4s bolt %.0f..%.0f kN (T bolt %.0f..%.0f C, stack %.0f..%.0f C); studs R1-R2 %.1f..%.1f kN; %d critical times' % (
            c, sh['F'].min() / 1e3, sh['F'].max() / 1e3, sh['T_bolt'].min(), sh['T_bolt'].max(), sh['T_stack'].min(), sh['T_stack'].max(),
            st['R1_R2']['F'].min() / 1e3, st['R1_R2']['F'].max() / 1e3, len(picks)), flush=True)
    print('6. stress model at %d critical times' % len(jobs), flush=True)
    mech_run(jobs, max_par, threads)
    for c in cases:
        for d in crit[c]:
            r, S = mech_result(d['job'], M, MM); d.update(r)
            np.save(os.path.join(WORK, d['job'] + '_S.npy'), S.astype(np.float32))
    return out, crit, cal


# ================================================================================================ joints, LCF, checks
HOT_SETS = dict(drum_R1=('drum_R1',), R1_R2=('R1_spc', 'spc_R2'), R2_stub=('R2_stub',))
COMP_J = ('stub_I1', 'I1_spc', 'spc_I2', 'I2_drum')
RELAX = 0.10                                                    # long-term stud relaxation allowance (stack model)


def stack_required():
    S = json.load(open(os.path.join(HERE, 'fea', 'a1000_rotor_stack.json')))
    req = {j: dict(F=v['F'], **v['parts']) for j, v in S['tie_bolt']['required'].items()}
    for j, v in S['hot_joints']['joints'].items(): req[j] = dict(F=v['required'], **v['parts'])
    return req, S


def joint_margins(d, cal, st_at, req):
    """margins of one stress state d (critical-time result); st_at = stud preload per stud of each hot set at that time.
    margin: total clamp / the stack model's required clamp (bending + torque separation + axial, as a1000_rotor_stack);
    margin_local: the FE contact pressure of each radial fifth of the band over the separating pressure there (axial and
    torque uniform, the 3 g bending moment linear in r): < 1 means the teeth would lift at that radius"""
    out = {}
    def local(j, p, r):
        x, _, _, _, ri, ro, h = joints()[j]
        rb = ri + (np.arange(5) + 0.5) * (ro - ri) / 5
        Ab = math.pi * (ro * ro - ri * ri); I = math.pi / 4 * (ro ** 4 - ri ** 4)
        M_ = r['bending'] * I / (ro * Ab)                         # moment behind the stack's bending clamp F_b = M ro A / I
        q_open = r['axial'] / Ab + M_ * rb / I; q_slip = max(r['torque'], 1.0) / Ab
        return dict(p=list(map(float, p)), p_min=float(p.min()), open=bool(p.min() <= 0.0), margin_local=float(np.min(p / (q_open + q_slip))),
                    margin_open=float(np.min(p / q_open)), margin_slip=float(np.min(p / q_slip)))
    for j in COMP_J:
        b = d['bands'][j]; C = -b['N']; C0 = -cal['bands_asm'][j]['N']
        out[j] = dict(clamp=C, fraction=C / C0, p_mean=C / b['A'], margin=C / req[j]['F'], **local(j, -np.array(b['sigma']), req[j]))
    for hs, bands in HOT_SETS.items():
        Ns = G.STUD['n'] * st_at[hs]; Ns_eol = Ns - G.STUD['n'] * stud_relax(hs) * stud_pre(hs) * 1e3
        N0 = G.STUD['n'] * stud_pre(hs) * 1e3; worst = None
        for j in bands:
            b = d['bands'][j]
            m = local(j, Ns_eol / b['A'] - np.array(b['sigma']), req[hs])
            if worst is None or m['margin_local'] < worst['margin_local']: worst = dict(m, band=j)
        out[hs] = dict(clamp=Ns, clamp_eol=Ns_eol, fraction=Ns / N0, margin=Ns_eol / req[hs]['F'], **worst)
    return out


LCF_PARTS = dict(R1='MAR-M247', R2='MAR-M247', imp1='Ti64', imp2='Ti64', drum='IN718', tspc='IN718', rstub='IN718')
CYCLES = dict(standard=('AS', 'BS'), standard_fast=('A', 'B'), trip=('AS', 'C1'), trip_noBOV=('AS', 'C2'), load_rejection=('AS', 'C3'),
              hot_restart_15=('AS', 'D15'), hot_restart_30=('AS', 'D30'), hot_restart_60=('AS', 'D60'), load_step=('E',))


def lcf(M, crit, cases):
    """per cycle and part: smallest Manson-Morrow life over the nodes for the largest von Mises range between any two of
    the cycle's states (assembly / rest included)"""
    S_asm = np.load(os.path.join(WORK, 'm_asm_S.npy')).astype(float)
    reg_n = {}
    for i, rg in enumerate(M['ereg']):
        name = M['regions'][rg]
        if name in LCF_PARTS:
            for nid in M['elems'][i]: reg_n.setdefault(name, set()).add(M['pos'][nid])
    iface = art_nodes(M)                                     # interfaces, relief corners, platform ends
    states = {}
    for c in cases:
        for d in crit[c]:
            states[d['job']] = (c, d, np.load(os.path.join(WORK, d['job'] + '_S.npy')).astype(float))
    out = {}
    Tn_cache = {}
    for cyc, cs in CYCLES.items():
        if not all(c in cases for c in cs): continue
        jobs = [j for j, (c, d, S) in states.items() if c in cs]
        res = {}
        groups = []
        for part, mat in LCF_PARTS.items():
            mat = PART_MAT.get(part, mat)
            nd = np.array(sorted(reg_n[part] - iface))
            if part in ('R1', 'R2'):                            # platform as a1000_turbine_checks: Kt 1.3 at the blade fillets,
                rh = A.row_radius(part, 0.0); pl = M['nodes'][nd, 0] > rh - 0.5   # no mean-stress correction (TMF)
                groups += [(part, mat, nd[~pl], 1.0, True), (part + '_platform', mat, nd[pl], 1.3, False)]
            else:
                groups.append((part, mat, nd, 1.0, True))
        for part, mat, nd, kt, mean in groups:
            best = None
            rest = cyc != 'load_step'                           # a load cycle does not pass through the rest state
            stk = ([S_asm[nd]] if rest else []) + [states[j][2][nd] for j in jobs]
            names = (['rest'] if rest else []) + jobs
            Ts = ([np.full(len(nd), 20.0)] if rest else []) + [temps_of(states[j][1], M, Tn_cache)[nd] for j in jobs]
            for a in range(len(stk)):
                for b in range(a + 1, len(stk)):
                    dv = vm6(stk[a] - stk[b]); k = int(np.nanargmax(dv))
                    if best is None or dv[k] > best[0]:
                        best = (float(dv[k]), a, b, k)
            dv, a, b, k = best
            dv *= kt
            T = float(max(Ts[a][k], Ts[b][k])); smax = float(max(vm6(stk[a][k]), vm6(stk[b][k]))) * kt if mean else 0.0
            N = manson(mat, dv / float(E_of(mat, T)), T, smax)
            res[part] = dict(range=dv, Kt=kt, T=T, s_max=smax, cycles=N, at=[float(v) for v in M['nodes'][nd[k]]], states=[names[a], names[b]])
        out[cyc] = res
    ref = out.get('standard')
    if ref:
        for cyc, res in out.items():
            for part, v in res.items(): v['equivalent'] = ref[part]['cycles'] / v['cycles']
    return out


def temps_of(d, M, cache):
    key = d['job']
    if key not in cache: cache[key] = _temps_from_inp(os.path.join(WORK, key + '.inp'), M)
    return cache[key]


def _temps_from_inp(path, M):
    T = np.full(len(M['ids']), 20.0); on = False
    for line in open(path):
        if line.startswith('*TEMPERATURE'): on = True; continue
        if on:
            if line.startswith('*'): break
            a, b = line.split(','); n = int(a)
            if n < 10_000_000: T[M['pos'][n]] = float(b)
    return T


def artifact_nodes(M):
    """node positions whose stresses are model artefacts: band / gas interfaces, the sharp tooth-gap relief corners next to
    every curvic band (the tooth roots are phase 4's 3D model), the platform end corners (as a1000_disc_fea), the bolt
    preload segment and threads"""
    out = set()
    for i, rg in enumerate(M['ereg']):
        name = M['regions'][rg]
        if name.startswith('band') or name.startswith('air'):
            out.update(M['pos'][M['elems'][i]])
    r, x = M['nodes'][:, 0], M['nodes'][:, 1]
    bad = np.zeros(len(r), bool)
    for j, (xj, a, b, (o0, o1), ri, ro, h) in joints().items():
        bad |= (np.abs(x - xj) < h / 2 + 3.0) & (r > o0 - 2.0) & (r < o1 + 2.0)
    for row in ('R1', 'R2'):
        rh = A.row_radius(row, 0.0)
        for xe in (A.X_LE[row] - A.PLAT_OVH + G.X_OFF, A.X_TE[row] + A.PLAT_OVH + G.X_OFF):
            bad |= np.hypot(r - rh, x - xe) < 2.5
    out.update(np.where(bad)[0])
    return out


def stress_peaks(S, M):
    """peak stresses of one state: blisk centres (von Mises) and platforms (hoop), impeller bores (hoop), drum, bolt (interior
    nodes: no band / gas interface; the bolt away from the preload segment and the threads)"""
    reg = np.array([M['regions'][k] for k in M['ereg']])
    nr = {}
    for i, rg in enumerate(reg):
        for nid in M['elems'][i]: nr.setdefault(rg, set()).add(M['pos'][nid])
    iface = art_nodes(M)
    nodes = M['nodes']; out = {}
    def inner(part): return np.array(sorted(nr[part] - iface))
    for row in ('R1', 'R2'):
        nd = inner(row); r, x = nodes[nd, 0], nodes[nd, 1]; xm = 0.5 * sum(G.HUB[row]); rh = A.row_radius(row, 0.0)
        c = nd[(r < 30.0) & (np.abs(x - xm) < 15.0)]; p = nd[(r > rh - 0.5)]
        out[row + '_centre_vm'] = float(np.nanmax(vm6(S[c]))); out[row + '_plat_hoop_min'] = float(np.nanmin(S[p, 2]))
        out[row + '_plat_hoop_max'] = float(np.nanmax(S[p, 2]))
        out[row + '_vm_max'] = float(np.nanmax(vm6(S[nd[r < rh - 3.0]])))
    for im in ('imp1', 'imp2'):
        nd = np.array(sorted(nr[im])); r = nodes[nd, 0]; b = nd[r < 23.5]
        out[im + '_bore_hoop'] = float(np.nanmax(S[b, 2])); out[im + '_vm_max'] = float(np.nanmax(vm6(S[inner(im)])))
    for part in ('drum', 'tspc'):
        out[part + '_vm_max'] = float(np.nanmax(vm6(S[inner(part)])))
    nd = inner('bolt'); x = nodes[nd, 1]
    nd = nd[((x < PRE_SEG[0] - 10) | (x > PRE_SEG[1] + 10)) & (x > G.TIE['x_nut'][1] + 12) & (x < G.TIE['x_end'] - G.TIE['thread_len'] - 10)]
    out['bolt_vm_max'] = float(np.nanmax(vm6(S[nd])))
    return out


_ART = {}


def art_nodes(M):
    if 'nodes' not in _ART: _ART['nodes'] = artifact_nodes(M)
    return _ART['nodes']


def ds(t, *ys, n=220, keep=()):
    """down-sample histories for the JSON (keep the critical indices)"""
    idx = np.unique(np.r_[np.linspace(0, len(t) - 1, min(len(t), n)).astype(int), list(keep)])
    return [list(map(float, np.asarray(t)[idx]))] + [list(map(float, np.asarray(y)[idx])) for y in ys]


def report_config(M, cases, meta, out, crit, cal, purge):
    req, S_st = stack_required()
    A_sh = math.pi / 4 * G.TIE['shank'] ** 2
    R = dict(purge=dict(PURGE, on=purge), cases={})
    for c in cases:
        o = out[c]; t, sh, st, pr = o['t'], o['sh'], o['st'], o['pr']
        ks = [d['k'] for d in crit[c]]
        for d in crit[c]:
            st_at = {hs: float(st[hs]['F'][d['k']]) for hs in st}
            d['margins'] = joint_margins(d, cal, st_at, req)
            d['F_spring'] = float(sh['F'][d['k']]); d['T_bolt'] = float(sh['T_bolt'][d['k']]); d['T_stack'] = float(sh['T_stack'][d['k']])
            d['studs'] = st_at
            d['peaks'] = stress_peaks(np.load(os.path.join(WORK, d['job'] + '_S.npy')).astype(float), M)
        kmin, kmax = int(np.argmin(sh['F'])), int(np.argmax(sh['F']))
        Tb_max = float(sh['T_bolt'].max())
        R['cases'][c] = dict(
            name=CASE_NAME[c], events=meta[c]['events'],
            bolt=dict(F_min=float(sh['F'][kmin]), t_min=float(t[kmin]), F_max=float(sh['F'][kmax]), t_max=float(t[kmax]),
                      F_end=float(sh['F'][-1]), T_max=Tb_max, T_min=float(sh['T_bolt'].min()), stress_max=float(sh['F'][kmax] / A_sh)),
            studs={hs: dict(F_min=float(v['F'].min()), t_min=float(t[int(np.argmin(v['F']))]), F_max=float(v['F'].max()),
                            F_0=float(v['F'][0]), T_0=float(v['T_stud'][0]), T_max=float(v['T_stud'].max()),
                            stress_max=float(v['F'].max() / STUD_AS), material=stud_mat(hs), pre_kN=stud_pre(hs),
                            relax=stud_relax(hs)) for hs, v in st.items()},
            history=dict(zip(('t', 'n', 'F_bolt', 'T_bolt', 'T_stack', 'F_stud_drum_R1', 'F_stud_R1_R2', 'F_stud_R2_stub', 'T_stud_R1_R2',
                              'R1_rim', 'R1_centre', 'R2_rim', 'R2_centre', 'I1_bore', 'I1_tip', 'I2_bore', 'I2_tip', 'drum', 'bulkhead', 'tspc'),
                             ds(t, sh['n'], sh['F'], sh['T_bolt'], sh['T_stack'], st['drum_R1']['F'], st['R1_R2']['F'], st['R2_stub']['F'],
                                st['R1_R2']['T_stud'], pr['R1_rim'], pr['R1_centre'], pr['R2_rim'], pr['R2_centre'], pr['I1_bore'], pr['I1_tip'],
                                pr['I2_bore'], pr['I2_tip'], pr['drum'], pr['bulkhead'], pr['tspc'], keep=ks))),
            critical=[{k: v for k, v in d.items() if k not in ('F_seg',)} for d in crit[c]])
    R['lcf'] = lcf(M, crit, cases)
    # hot-joint summary for a1000_rotor_stack.py: steady rating (C1 initial state) and the worst of all cases
    R['hot_joints'] = {hs: dict(material=stud_mat(hs), pre_kN=stud_pre(hs), relax=stud_relax(hs),
                                T_ss=R['cases']['C1']['studs'][hs]['T_0'] if 'C1' in R['cases'] else None,
                                F_ss=R['cases']['C1']['studs'][hs]['F_0'] if 'C1' in R['cases'] else None,
                                F_min=min(v['studs'][hs]['F_min'] for v in R['cases'].values()),
                                T_max=max(v['studs'][hs]['T_max'] for v in R['cases'].values())) for hs in HOT_SETS}
    return R


def checks_of(R, cal, req):
    """rotor check list entries (same format as a1000_rotor_stack.check)"""
    chk = []
    def check(test, value, limit, unit, ok, note=''):
        chk.append(dict(test=test, value=float(value), limit=float(limit), unit=unit, ok=bool(ok), note=note))
        print('  %-56s %10.4g %-4s (limit %.4g) %s  %s' % (test, value, unit, limit, 'OK' if ok else 'FAIL', note))
    C = R['cases']; A_sh = math.pi / 4 * G.TIE['shank'] ** 2
    F_req = max(req[j]['F'] for j in COMP_J)
    cmin = min(C, key=lambda c: C[c]['bolt']['F_min']); Fmin = C[cmin]['bolt']['F_min']
    check('transient: tie-bolt min preload / required', Fmin / F_req, 1.25, '-', Fmin / F_req >= 1.25,
          'min %.0f kN in %s at %.0f s, required %.0f kN' % (Fmin / 1e3, cmin, C[cmin]['bolt']['t_min'], F_req / 1e3))
    cmax = max(C, key=lambda c: C[c]['bolt']['F_max']); Fmax = C[cmax]['bolt']['F_max']; Tb = max(v['bolt']['T_max'] for v in C.values())
    sy = float(np.interp(Tb, *YIELD['IN718']))
    check('transient: tie-bolt max shank stress / 0.75 Sy', Fmax / A_sh / (0.75 * sy), 1.0, '-', Fmax / A_sh <= 0.75 * sy,
          'max %.0f kN (%.0f MPa) in %s; Sy at %.0f C' % (Fmax / 1e3, Fmax / A_sh, cmax, Tb))
    check('transient: tie-bolt max temperature (IN718 relaxation onset 593 C)', Tb, 593.0, 'C', Tb <= 593.0, 'no creep / relaxation')
    # spring model against the FE at the critical times
    dev = [abs(d['F_spring'] / d['F'] - 1) for v in C.values() for d in v['critical']]
    check('spring preload model vs FE at the critical times', 100 * max(dev), 10.0, '%', max(dev) <= 0.10, '%d states' % len(dev))
    # compressor curvics (FE states)
    worst = {}
    for c, v in C.items():
        for d in v['critical']:
            for j, m in d['margins'].items():
                if j not in worst or m['margin'] < worst[j][0]['margin']: worst[j] = (m, c, d['t'])
    for j in list(COMP_J) + list(HOT_SETS):
        m, c, tt = worst[j]
        check('transient: joint %s clamp / required%s' % (j, '' if j in COMP_J else ' (studs, %.0f %% relaxation)' % (100 * stud_relax(j))),
              m['margin'], 1.25, '-', m['margin'] >= 1.25, '%s at %.0f s, %.0f %% of the assembly clamp' % (c, tt, 100 * m['fraction']))
        # local contact of the 2D band proxy (bonded layer, estimated stiffness): information for phase 4's 3D contact
        # model, not a check (R['joint_local'])
        wl = min(((d['margins'][j], c_, d['t']) for c_, v in C.items() for d in v['critical']), key=lambda q: q[0]['margin_local'])
        R.setdefault('joint_local', {})[j] = dict(margin_local=wl[0]['margin_local'], p=wl[0]['p'], case=wl[1], t=wl[2],
                                                  margin_open=wl[0]['margin_open'], margin_slip=wl[0]['margin_slip'])
    for hs in HOT_SETS:
        Ts = max(v['studs'][hs]['T_max'] for v in C.values()); smax = max(v['studs'][hs]['stress_max'] for v in C.values())
        sm = stud_mat(hs); TL = STUD_TMAX[sm]
        check('transient: studs %s max temperature (%s bolting %.0f C)' % (hs, sm, TL), Ts, TL, 'C', Ts <= TL, '')
        sy = float(np.interp(Ts, *YIELD[sm]))
        check('transient: studs %s max stress / 0.7 Sy' % hs, smax / (0.7 * sy), 1.0, '-', smax <= 0.7 * sy, '%.0f MPa (%s)' % (smax, sm))
    L = R['lcf']
    for part in (('R1', 'R1_platform', 'R2', 'R2_platform', 'imp1', 'imp2', 'drum') if 'standard' in L else ()):
        Nw = min(L[cyc][part]['cycles'] for cyc in L); cw = min(L, key=lambda k: L[k][part]['cycles'])
        Ns = L['standard'][part]['cycles']
        check('LCF %s: standard start-stop cycles' % part, Ns, TC.STARTS_REQ, 'cyc', Ns >= TC.STARTS_REQ,
              'worst cycle %s %.2g (%.2f standard cycles each)' % (cw, Nw, L[cw][part]['equivalent']))
    return chk


# ================================================================================================ plots
COL = dict(A='#1f77b4', B='#7f7f7f', C1='#d62728', C2='#ff7f0e', C3='#9467bd', D15='#2ca02c', D30='#17becf', D60='#8c564b', E='#e377c2',
           AS='#000080', BS='#404040')


def plot(res, req):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    cfgs = [k for k in ('baseline', 'fix') if k in res['configs']]
    final = res['configs'][cfgs[-1]]
    fig, axs = plt.subplots(2, 3, figsize=(17, 9.5), dpi=100)
    F_req = max(req[j]['F'] for j in COMP_J)
    ax = axs[0, 0]
    for c, v in final['cases'].items():
        h = v['history']; ax.plot(np.array(h['t']) / 60, np.array(h['F_bolt']) / 1e3, color=COL[c], lw=1.2, label='%s %s' % (c, v['name']))
    ax.axhline(G.TIE['pre_kN'], color='k', ls=':', lw=0.8); ax.axhline(1.25 * F_req / 1e3, color='r', ls='--', lw=1.0, label='1.25 x required')
    ax.set_xscale('symlog', linthresh=1.0); ax.set_xlim(0, 300); ax.set_xlabel('time [min] (symlog)'); ax.set_ylabel('tie-bolt preload [kN]')
    ax.set_title('Tie bolt M42 IN718 through the transients', fontsize=10); ax.legend(fontsize=6.5, loc='lower left'); ax.grid(alpha=0.3)
    ax = axs[0, 1]
    for c in ('A', 'D30', 'C1'):
        if c not in final['cases']: continue
        h = final['cases'][c]['history']; tm = np.array(h['t']) / 60
        ax.plot(tm, h['T_bolt'], color=COL[c], lw=1.4, label='%s bolt (grip mean)' % c)
        ax.plot(tm, h['T_stack'], color=COL[c], lw=1.0, ls='--', label='%s stack load path' % c)
    ax.set_xscale('symlog', linthresh=1.0); ax.set_xlim(0, 300); ax.set_xlabel('time [min] (symlog)'); ax.set_ylabel('mean temperature [C]')
    ax.set_title('Bolt lags the stack: heats later, cools later', fontsize=10); ax.legend(fontsize=7); ax.grid(alpha=0.3)
    ax = axs[0, 2]
    for cfg, ls in zip(cfgs, ('--', '-')):
        for c in ('A', 'C1', 'D30'):
            if c not in res['configs'][cfg]['cases']: continue
            h = res['configs'][cfg]['cases'][c]['history']
            ax.plot(np.array(h['t']) / 60, np.array(h['F_stud_R1_R2']) / 1e3, color=COL[c], ls=ls, lw=1.1, label='%s %s' % (c, cfg))
    ax.axhline(G.STUD['pre_kN'], color='k', ls=':', lw=0.8); ax.axhline(CONFIGS['fix']['pre12'], color='g', ls=':', lw=0.8)
    ax.set_xscale('symlog', linthresh=1.0); ax.set_xlim(0, 300); ax.set_xlabel('time [min] (symlog)'); ax.set_ylabel('R1 - R2 stud preload [kN / stud]')
    ax2 = ax.twinx()
    for cfg, ls in zip(cfgs, ('--', '-')):
        if 'A' in res['configs'][cfg]['cases']:
            h = res['configs'][cfg]['cases']['A']['history']; ax2.plot(np.array(h['t']) / 60, h['T_stud_R1_R2'], color='tab:red', ls=ls, lw=0.8)
    ax2.set_ylabel('R1 - R2 stud temperature, case A [C]', color='tab:red'); ax2.axhline(650, color='tab:red', ls=':', lw=0.8)
    ax.set_title('R1 - R2 studs (dashed: as designed, IN718 %.0f kN; solid: fix, Waspaloy %.0f kN)' % (G.STUD['pre_kN'], CONFIGS['fix']['pre12']),
                 fontsize=9); ax.legend(fontsize=6.5, loc='lower right'); ax.grid(alpha=0.3)
    ax = axs[1, 0]
    for c in ('A', 'AS'):
        if c not in final['cases']: continue
        h = final['cases'][c]['history']; tm = np.array(h['t']) / 60
        for k, ls in (('R1_rim', '-'), ('R1_centre', '--'), ('R2_rim', '-.'), ('R2_centre', ':')):
            ax.plot(tm, h[k], color=COL[c], ls=ls, lw=1.1, label='%s %s' % (c, k))
    ax.set_xscale('symlog', linthresh=1.0); ax.set_xlim(0, 300); ax.set_xlabel('time [min] (symlog)'); ax.set_ylabel('temperature [C]')
    ax.set_title('Blisk rim and centre: phase 1 cold start (A) and the operating rule (AS)', fontsize=10); ax.legend(fontsize=6.5, ncol=2); ax.grid(alpha=0.3)
    ax = axs[1, 1]
    js = list(COMP_J) + list(HOT_SETS)
    for cfg, off, colr in zip(cfgs, (-0.2, 0.2), ('#bbbbbb', '#2ca02c')):
        mins = []
        for j in js:
            mins.append(min(d['margins'][j]['margin'] for v in res['configs'][cfg]['cases'].values() for d in v['critical']))
        ax.bar(np.arange(len(js)) + off, mins, width=0.38, color=colr, label=cfg)
    ax.axhline(1.25, color='r', ls='--', lw=1.0); ax.set_xticks(range(len(js))); ax.set_xticklabels(js, rotation=30, fontsize=8)
    ax.set_ylabel('min clamp / required (all cases)'); ax.set_yscale('log'); ax.legend(fontsize=8); ax.grid(alpha=0.3, which='both')
    ax.set_title('Joint clamp margins, worst state of all cases', fontsize=10)
    ax = axs[1, 2]
    L = final['lcf']; cyc = list(L.keys()); parts = ['R1', 'R1_platform', 'R2', 'R2_platform', 'imp1', 'imp2', 'drum']
    for k, p in enumerate(parts):
        ax.bar(np.arange(len(cyc)) + (k - 3) * 0.12, [L[c][p]['cycles'] for c in cyc], width=0.12, label=p)
    ax.axhline(TC.STARTS_REQ, color='r', ls='--', lw=1.0); ax.set_yscale('log'); ax.set_xticks(range(len(cyc)))
    ax.set_xticklabels(cyc, rotation=30, fontsize=8); ax.set_ylabel('LCF life [cycles] (Manson-Morrow, 2 / 20)'); ax.legend(fontsize=7, ncol=3)
    ax.set_title('LCF of each cycle type', fontsize=10); ax.grid(alpha=0.3, which='both')
    fig.suptitle('AURORA-1000 rotor transient thermal-structural analysis (phase 5): CalculiX CAX6 heat + stress, phase 1 histories', fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_tiebolt_thermal.png')); plt.close(fig)
    print('written docs/img/a1000_tiebolt_thermal.png')


def plot_fields(M, states):
    """temperature fields of the rotor section at a few states: [(title, nodal T)]"""
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    mats = emat_mech(M); keep = np.array([m is not None for m in mats])
    E = M['E'][keep][:, :3]
    tri = mtri.Triangulation(M['nodes'][:, 1], M['nodes'][:, 0], E)
    fig, axs = plt.subplots(len(states), 1, figsize=(15, 3.1 * len(states)), dpi=100)
    for ax, (title, T) in zip(np.atleast_1d(axs), states):
        cs = ax.tripcolor(tri, T, shading='gouraud', cmap='inferno', vmin=0, vmax=900)
        ax.set_aspect('equal'); ax.set_xlim(-5, 1010); ax.set_ylim(0, 245); ax.set_title(title, fontsize=9.5); ax.set_ylabel('r [mm]')
        fig.colorbar(cs, ax=ax, fraction=0.02, pad=0.01, label='T [C]')
    np.atleast_1d(axs)[-1].set_xlabel('x [mm] (rotor frame)')
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, 'docs', 'img', 'a1000_tiebolt_fields.png')); plt.close(fig)
    print('written docs/img/a1000_tiebolt_fields.png')


# ================================================================================================ main
MESH_FINE = 0.75                                                # fine mesh of the convergence check (x 0.75 element size)


CONV_CASE = 'E'                                                  # mesh / time-step check case (one event, cheap)


def conv_window(events):
    """mesh / time-step check window: the first hour after the event (hot restart: after the restart)"""
    rs = [e[0] for e in events if e[1] == 'restart']
    return (rs[0] if rs else 0.0) + 3600.0


def quick_compare(Mx, tag, cal, meta_x, c='D30', t_max=None):
    """thermal-only comparison for the mesh / time-step checks (spring preload, bolt temperature, R1 gradient)"""
    P, mats = load_paths(Mx); PI = probes(Mx)
    Te20 = np.full(len(Mx['elems']), 20.0)                      # the FE compliance scales the bins of this mesh
    cal = dict(cal, c_ratio=cal['c0'] / (bin_strain(*P['bolt'], Te20, Mx, mats)[1] + bin_strain(*P['stack'], Te20, Mx, mats)[1]))
    t, Te, Tn = case_fields(c, Mx, tag)
    if t_max is not None:
        k = t <= t_max + 1e-6; t, Te, Tn = t[k], Te[k], Tn[k]
    sh = spring_history(c, t, Te, Mx, P, mats, meta_x, cal)
    st = stud_model('R1_R2', t, Te, P, Mx, mats)
    d1 = Te[:, PI['R1_rim']] - Te[:, PI['R1_centre']]
    return dict(F_min=float(sh['F'].min()), F_max=float(sh['F'].max()), T_bolt_max=float(sh['T_bolt'].max()),
                stud_min=float(st['F'].min()), R1_dT_max=float(d1.max()), nodes=len(Mx['ids']))


def main():
    args = sys.argv[1:]
    def opt(name, default):
        return args[args.index(name) + 1] if name in args else default
    cases = opt('--cases', ','.join(CASES)).split(',')
    configs = opt('--configs', 'baseline,fix').split(',')
    th, par = int(opt('--threads', '2')), int(opt('--par', '9'))
    fdt, dmx = float(opt('--fac-dt', '2.0')), float(opt('--deltmx', '10.0'))   # step-plan factor, DELTMX [K]
    post_only = '--post-only' in args
    os.makedirs(WORK, exist_ok=True)
    print('AURORA-1000 phase 5: rotor transient thermal-structural (work %s)' % WORK)
    print('1. mesh', flush=True)
    mp = os.path.join(WORK, 'mesh_1.0.npz')
    M = load_mesh(mp) if (os.path.exists(mp) and '--remesh' not in args) else build_mesh(1.0, mp)
    print('   %d nodes, %d CAX6 elements, %d regions' % (len(M['ids']), len(M['elems']), len(M['regions'])), flush=True)
    req, _ = stack_required()
    res = dict(rev='rotor rev 1.3, phase 5', work=WORK, mesh=dict(nodes=len(M['ids']), elements=len(M['elems'])), configs={},
               model=dict(T_inlet=T_AMB, T_enclosure=T_ENCL, post_lube_s=POST_LUBE, cavities=CAVITY, land_gap_model_mm=1.0, land_gap_mm=0.15,
                          stud_lag_s=STUD_TAU, km_factor=KM_FAC, k_curvic_per_mm2=K_CURVIC, k_joint=K_JOINT, relaxation=RELAX,
                          dt_rel=DT_REL, purge=PURGE))
    sens = opt('--land-gap', None)                              # sensitivity: bolt land gas gap [mm] (0.15 nominal)
    stag = ('' if sens is None else '_lg%s' % sens) + opt('--tag-suffix', '')
    if sens is not None: CAVITY['AIR_LAND']['kx'] = 1.0 / float(sens)
    if '--pass2' in args:                                       # cavity energy balance on the first-pass walls, final heat runs
        for cfg in configs:
            t1 = set_config(cfg) + stag
            src = opt('--cav-from', t1)                         # fix: the walls of the as-designed first pass
            cc = os.path.join(WORK, 'cavcal%s.json' % t1)
            if os.path.exists(cc) and '--recal' not in args:    # parallel processes share one calibration
                histories(cases); CAV_BETA.clear(); CAV_BETA.update(json.load(open(cc))['beta'])
            else: calibrate_cavities(M, t1)
            stage_thermal(cases, M, t1 + '2', fac_dt=fdt, deltmx=dmx, max_par=par, threads=th, cav_from=src)
        return None
    if '--thermal-only' in args:                                # heat runs only (several processes can share the node)
        for cfg in configs:
            stage_thermal(cases, M, set_config(cfg) + stag, fac_dt=fdt, deltmx=dmx, max_par=par, threads=th)
        return None
    if '--conv-thermal' in args:                                # D30 on the fine mesh and with half the time steps
        tag = set_config(configs[-1])
        Mf = build_mesh(MESH_FINE, os.path.join(WORK, 'mesh_fine.npz'))
        stage_thermal([CONV_CASE], Mf, tag + '_fine', max_par=1, threads=th, t_cut=conv_window)
        stage_thermal([CONV_CASE], M, tag + '_dt', fac_dt=1.0, deltmx=5.0, max_par=1, threads=th, t_cut=conv_window)
        return None
    cal = None
    suffix = opt('--suffix', '')                                # '2': the final pass with the cavity energy balance
    for cfg in configs:
        tag = set_config(cfg) + suffix
        cc = os.path.join(WORK, 'cavcal%s.json' % tag[:-len(suffix)] if suffix else 'cavcal%s.json' % tag)
        if os.path.exists(cc): CAV_BETA.update(json.load(open(cc))['beta'])
        print('=== configuration %s (interstage purge %s)' % (cfg, 'on' if PURGE['on'] else 'off'), flush=True)
        if post_only: meta = json.load(open(os.path.join(WORK, 'meta%s.json' % tag)))
        else: meta = stage_thermal(cases, M, tag, max_par=par, threads=th)
        cs = [c for c in cases if c in meta and os.path.exists(os.path.join(WORK, 'p5_%s%s.frd' % (c, tag)))]   # AS / BS: fix only
        out, crit, cal = stage_mech(M, cs, meta, tag, max_par=min(par * th, 16), threads=1, cal=cal)
        R = report_config(M, cs, meta, out, crit, cal, PURGE['on'])
        R['config'] = dict(CFG)
        cr = next(c for c in cs if meta[c]['init'] == 'rating')
        R['bc_rating'] = meta[cr]['bc_t0']; R['bc_max'] = {c: meta[c]['bc_max'] for c in cs}
        R['cavity_air_rating'] = meta[cr].get('cav_t0', {})
        if os.path.exists(cc): R['cavity_calibration'] = json.load(open(cc))
        res['configs'][cfg] = R
    res['calibration'] = cal
    print('7. checks', flush=True)
    for cfg in configs:
        print('   configuration %s' % cfg); set_config(cfg)
        res['configs'][cfg]['checks'] = checks_of(res['configs'][cfg], cal, req)
    res['checks'] = res['configs'][configs[-1]]['checks']
    res['final_config'] = configs[-1]
    if '--mesh-check' in args or '--step-check' in args:
        ccfg = opt('--conv-config', 'baseline')                 # the checks run on the first-pass BCs of this configuration
        print('8. mesh and time-step checks (case %s, first pass, configuration %s)' % (CONV_CASE, ccfg), flush=True)
        tag = set_config(ccfg)
        meta = json.load(open(os.path.join(WORK, 'meta%s.json' % tag)))
        tw = conv_window(meta[CONV_CASE]['events'])
        base = quick_compare(M, tag, cal, meta, CONV_CASE, t_max=tw)
        chk = dict(base=base, window_s=tw)
        if '--mesh-check' in args:
            fm = os.path.join(WORK, 'mesh_fine.npz')
            Mf = load_mesh(fm) if os.path.exists(fm) else build_mesh(MESH_FINE, fm)
            if os.path.exists(os.path.join(WORK, 'p5_%s%s_fine.frd' % (CONV_CASE, tag))):
                mf = json.load(open(os.path.join(WORK, 'meta%s_fine.json' % tag)))
            else: mf = stage_thermal([CONV_CASE], Mf, tag + '_fine', max_par=1, threads=8, t_cut=conv_window)
            chk['fine_mesh'] = quick_compare(Mf, tag + '_fine', cal, mf, CONV_CASE, t_max=tw)
        if '--step-check' in args:
            if os.path.exists(os.path.join(WORK, 'p5_%s%s_dt.frd' % (CONV_CASE, tag))):
                ms = json.load(open(os.path.join(WORK, 'meta%s_dt.json' % tag)))
            else: ms = stage_thermal([CONV_CASE], M, tag + '_dt', fac_dt=1.0, deltmx=5.0, max_par=1, threads=8, t_cut=conv_window)
            chk['half_step'] = quick_compare(M, tag + '_dt', cal, ms, CONV_CASE, t_max=tw)
        res['convergence'] = chk
        for f in sorted(os.listdir(WORK)):                      # land-gap sensitivity runs (--land-gap X --thermal-only)
            if f.startswith('meta%s_lg' % tag) and f.endswith('.json'):
                st = f[4:-5]; ms = json.load(open(os.path.join(WORK, f)))
                chk['land_gap_%s' % st.split('_lg')[1]] = {c: dict(sens=quick_compare(M, st, cal, ms, c), base=quick_compare(M, tag, cal, meta, c))
                                                          for c in ms if os.path.exists(os.path.join(WORK, 'p5_%s%s.frd' % (c, st)))}
        for k in ('fine_mesh', 'half_step'):
            if k not in chk: continue
            d = max(abs(chk[k][q] / base[q] - 1) for q in ('F_min', 'F_max', 'stud_min'))
            dT = max(abs(chk[k][q] - base[q]) for q in ('T_bolt_max', 'R1_dT_max'))
            print('   %-10s preload / stud change %.2f %%, temperatures %.1f K (%d nodes)' % (k, 100 * d, dT, chk[k]['nodes']))
            res['checks'].append(dict(test='phase 5 %s: preload change (case %s)' % (k.replace('_', ' '), CONV_CASE), value=100 * d, limit=3.0, unit='%',
                                      ok=bool(d <= 0.03), note='bolt / R1 temperatures within %.1f K' % dT))
    n_ok = sum(c['ok'] for c in res['checks'])
    print('checks: %d of %d pass (configuration %s)' % (n_ok, len(res['checks']), configs[-1]))
    json.dump(res, open(OUT_JSON, 'w'), indent=1, default=float)
    print('written %s' % OUT_JSON)
    plot(res, req)
    fin = res['configs'][configs[-1]]['cases']
    states = []
    for c, lab in (('C1', 'initial state'), ('D30', 'bolt min'), ('A', 'R1 rim-centre max')):
        if c in fin:
            d = next((d for d in fin[c]['critical'] if d['label'] == lab), None)
            if d: states.append(('%s: %s, t = %.0f s, %.0f rpm' % (CASE_NAME[c], lab, d['t'], d['n'] * 15000),
                                 _temps_from_inp(os.path.join(WORK, d['job'] + '.inp'), M)))
    if states: plot_fields(M, states)
    return res


if __name__ == '__main__':
    main()
