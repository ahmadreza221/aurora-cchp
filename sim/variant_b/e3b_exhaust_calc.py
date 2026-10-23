#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP variant B (GR180-STEAM)  E3-B - compact exhaust collector for the simple-cycle gas section (generator 1).

Replaces the variant-A collector E3-110/111/112/113, the front foot E3-401 and the exit sensors E3-504/505/506 (they sat
on the old outlet transition).  Everything else of E3 (interduct+NGV E3-101, shroud + radial-diffuser west wall E3-102,
rotor, bearings, PMG) is kept unchanged; the axial-radial diffuser geometry of E3 is kept (exit r 125, x 231-253).

Concept (docs/variant_b/04_e3b_exhaust.md):
  radial diffuser exit r 125  ->  square plenum box around the FPT (inner 2a x 2a, x 154..249, symmetric about the axis)
  ->  open top  ->  short rectangle-to-round hood  ->  ONE round outlet, axis +z, DN200 (or DN250) PN6 flange.
  Box west end: 2-half bolted cover on the E3-101 mid flange.  Box east end: large round opening closed by the
  "rear unit" (spun hub bell = diffuser east wall + 4 mm disc + IN625 thermal-barrier cone to the PMG flange x 336).
  Centre-line support: two side lugs at z = 0 on a laser-cut portal plate (front support), PMG rear foot E3-402 kept.

Loss model (1-D, same diffuser model and coefficients as sim/engine/e3_fpt_pmg_calc.py, so the old and the new
collector are compared like-for-like):
  p4 = static at the radial-diffuser exit (E3 model: Cp = 0.60 (1 - 1/AR^2)); the radial jet dynamic head is dumped.
  plenum: the lower half of the flow travels round the sides, Q/4 per side at z = 0 through gap (a - 125) x L_eff;
          loss K_SIDE * q_side (two streams merge at the top: K ~ 1 on half the flow -> 0.5 on the whole flow).
  top opening (box section -> hood): K_TOP * q_top.  hood (rect -> round): K_HOOD * q5 + Borda (1 - A_top/A5)^2 q_top
  if it diffuses.  stub: friction.  p5 = flange static = P05 - q5.
  FPT: the E3 meanline (stage()) is re-solved for the Euler work that gives the variant-B back-pressure at the outlet
  flange (concept_study.cycle eps = 0: P_exit = Pa (1 + 0.015 HRSG + 0.005 stack) = 1.020 Pa) with each collector.

Run:   python3 sim/variant_b/e3b_exhaust_calc.py        (pure python; imports sim/engine/e3_fpt_pmg_calc.py, read-only)
Writes: sim/variant_b/e3b_exhaust_results.json  (geometry 'design' block is read by cad/variant_b/e3b_exhaust.py)
Frame: ENG (mm), x = tunnel front face, +x downstream (east), y north, z up.  # ASSUMPTION marks every guessed value.
"""
import json, math, os, sys, csv

HERE = os.path.dirname(os.path.abspath(__file__)); SIM = os.path.dirname(HERE); ROOT = os.path.dirname(SIM)
sys.path.insert(0, SIM); sys.path.insert(0, os.path.join(SIM, 'engine'))
import e3_fpt_pmg_calc as E3          # noqa: E402  (variant-A E3 meanline; only stage()/constants are used)

CR = json.load(open(os.path.join(ROOT, 'cad_out', 'engine', 'E3', 'E3_calc_results.json')))
VB = json.load(open(os.path.join(HERE, 'vb_results.json')))
P01, T01 = CR['interduct']['P01'], CR['interduct']['T01']
GEO, X = CR['geometry']['GEO'], CR['geometry']['X']
RG, CP = E3.RG, E3.CP
PA = E3.PA_SITE                                  # 50 m site ambient, Pa
MG_A = E3.MG                                     # variant A gas flow through E3 (0.3972 kg/s)
MG_B = 0.401                                     # variant B: 0.395 kg/s air + ~6.05 g/s fuel (vb_cycle / e2b_combustor_calc)
P_BACK_A = E3.P_EXIT                             # variant A: static at H1 = Pa (1 + 0.035 + 0.015 + 0.005)
P_BACK_B = PA * (1 + 0.015 + 0.005)              # variant B: concept_study.cycle(eps=0) P_exit (HRSG 1.5 % + stack 0.5 %)
P_MECH = CR['power']['P_mech_loss']              # bearings + seals (W), unchanged

# ------------------------------------------------------------------------------------------------ coefficients
K_SIDE = 0.5          # plenum side flow (merging of the two side streams at the top, on the whole flow)   # ASSUMPTION
L_EFF = 0.8           # fraction of the box inner length that carries the circumferential flow              # ASSUMPTION
K_TOP = 0.3           # plenum -> top opening (flow already mostly vertical in the upper half)              # ASSUMPTION
K_HOOD = 0.10         # rect -> round transition, ~constant area, 40 deg walls (on q5)                       # REF Idelchik 5-x
LAMBDA = 0.02         # pipe friction
T_HOOD_DEG = 40.0     # max hood wall angle from vertical (x expansion side)
V_SIDE_MAX_FACTOR = 1.0   # side velocity <= radial-diffuser exit velocity (no re-acceleration above V4)
DP_TARGET = 0.0060    # collector static loss p4 -> p5 target, fraction of Pa (caller: 0.5-0.8 % for the exhaust)

PIPE = {200: dict(OD=219.1, t=3.0, fl_OD=320.0, fl_PCD=280.0, n=8, bolt='M16', hole=18.0, fl_t=20.0),   # EN 1092-1 PN6 type 01
        250: dict(OD=273.0, t=3.0, fl_OD=375.0, fl_PCD=335.0, n=12, bolt='M16', hole=18.0, fl_t=22.0)}
for v in PIPE.values(): v['ID'] = v['OD'] - 2 * v['t']

# fixed geometry (mm) - see the module docstring
T_SH = 3.0                      # box sheet 1.4828, 3 mm
X_COVER0, T_COVER = 145.0, 5.0  # 2-half west cover on the E3-101 mid flange face (x 145); + 1 mm gasket
X_WP0 = X_COVER0 + T_COVER + 1.0           # west end plate 151..154
X_IN0 = X_WP0 + T_SH                       # box inner west face 154
X_EP1 = X['rad_e'] - 1.0                   # east end plate east face 252 (+1 mm gasket -> rear disc gas face = diffuser east wall 253)
X_IN1 = X_EP1 - T_SH                       # box inner east face 249
L_IN = X_IN1 - X_IN0                       # 95
XC = 0.5 * (X_IN0 + X_IN1)                 # outlet axis x 201.5
R_DIFF = GEO['rad_out']                    # 125
STUB_L = 150.0                             # stub incl. flange (caller: ~150 mm)


def rho(p, T): return p / (RG * T)


def collector_new(p4, T, mg, a, dn):
    """new box collector: static loss p4 -> p5 and the velocities"""
    pp = PIPE[dn]; r = rho(p4, T); Q = mg / r
    g = a - R_DIFF
    A_side = g * L_IN * L_EFF * 1e-6
    V_side = Q / 4 / A_side
    A_top = (2 * a) * L_IN * 1e-6
    V_top = Q / A_top
    A5 = math.pi / 4 * (pp['ID'] * 1e-3) ** 2
    V5 = Q / A5
    q = lambda V: 0.5 * r * V ** 2
    dP = dict(side=K_SIDE * q(V_side), top=K_TOP * q(V_top),
              hood=K_HOOD * q(V5) + (max(0.0, 1 - A_top / A5) ** 2) * q(V_top),
              stub=LAMBDA * (STUB_L - pp['fl_t'] + 70.0) / pp['ID'] * q(V5))
    P05 = p4 - sum(dP.values()); p5 = P05 - q(V5)
    dx = pp['ID'] / 2 - L_IN / 2
    h = 5 * math.ceil(dx / math.tan(math.radians(T_HOOD_DEG)) / 5)
    return dict(a=a, DN=dn, Q_m3s=Q, rho=r, V_side=V_side, V_top=V_top, V5=V5, q5=q(V5), A_side_m2=A_side, A_top_m2=A_top,
                A5_m2=A5, dP=dP, dP0_total=sum(dP.values()), P05=P05, p5=p5, dp_static=p4 - p5, hood_h=h)


def collector_old_mine(p4, T, mg):
    """variant-A drum (R 215, x 151..296, side outlet 120 x 240 -> DN250) evaluated with the SAME model as the new box"""
    r = rho(p4, T); Q = mg / r; q = lambda V: 0.5 * r * V ** 2
    g = GEO['drum_ro'] - 3.0 - R_DIFF; L = (X['drum1'] - 3.0) - (X['drum0'] + 6.0)
    V_side = Q / 4 / (g * L * L_EFF * 1e-6)
    A_open = (120 * 240 - (4 - math.pi) * 30 ** 2) * 1e-6           # rounded rectangle opening
    V_top = Q / A_open
    A5 = math.pi / 4 * 0.2604 ** 2; V5 = Q / A5
    dP = dict(side=K_SIDE * q(V_side), top=K_TOP * q(V_top), hood=K_HOOD * q(V5) + 0.5 * (1 - A_open / A5) ** 2 * q(V_top),
              stub=LAMBDA * 0.1 / 0.2604 * q(V5))
    P05 = p4 - sum(dP.values()); p5 = P05 - q(V5)
    return dict(V_side=V_side, V_top=V_top, V5=V5, dP=dP, dP0_total=sum(dP.values()), p5=p5, dp_static=p4 - p5)


def solve_fpt(P_back, mg, coll):
    """Euler work W such that the static at the outlet flange equals P_back. coll: 'E3' (built-in E3 model) or a function
    (s -> p5).  Returns (stage dict, p5, shaft power W)."""
    E3.MG = mg
    lo, hi = 30e3, 110e3
    for _ in range(70):
        W = 0.5 * (lo + hi); s = E3.stage(P01, T01, W)
        p5 = s['p5'] if coll == 'E3' else coll(s)
        if p5 > P_back: lo = W
        else: hi = W
    E3.MG = MG_A
    return s, p5, s['W_shaft_aero'] * mg - P_MECH



def main():
    out = dict(note='E3-B compact exhaust collector, variant B; see module docstring', inputs={}, sweep=[], design={}, fpt={},
               thermal={}, mass_estimate={}, sensors={})
    # ---------------------------------------------------------------- reference: E3 design (variant A)
    sA, p5A, PsA = solve_fpt(P_BACK_A, MG_A, 'E3')
    # ---------------------------------------------------------------- variant B with the E3 collector (E3's own model)
    sBo, p5Bo, PsBo = solve_fpt(P_BACK_B, MG_B, 'E3')
    T = sBo['T03']; p4 = sBo['p4']
    q4 = 0.5 * rho(p4, T) * sBo['V4'] ** 2
    out['inputs'] = dict(mg_B_kg_s=MG_B, mg_A_kg_s=MG_A, P01_Pa=P01, T01_K=T01, Pa_site_Pa=PA, P_back_A_Pa=P_BACK_A,
                         P_back_B_Pa=P_BACK_B, T_exh_C=T - 273.15, T_hrsg_in_cycle_C=VB[0]['T_hrsg_in_C'], p4_B_Pa=p4,
                         V4_radial_diffuser_exit_m_s=sBo['V4'], q4_Pa=q4, AR_diff=sBo['AR_diff'], Cp_diff=sBo['Cp_diff'],
                         p3_B_Pa=sBo['p3'], q3_B_Pa=sBo['q3'], coefficients=dict(K_SIDE=K_SIDE, L_EFF=L_EFF, K_TOP=K_TOP,
                         K_HOOD=K_HOOD, LAMBDA=LAMBDA, T_HOOD_DEG=T_HOOD_DEG, DP_TARGET=DP_TARGET))
    # ---------------------------------------------------------------- sweep box half-width a and outlet DN
    print('E3-B collector sweep (variant B, %.3f kg/s, %.0f C, p4 %.0f Pa, V4 %.1f m/s, q4 %.0f Pa)' % (MG_B, T - 273.15, p4, sBo['V4'], q4))
    print('%4s %4s %7s %6s %6s %7s %7s %7s %6s' % ('DN', 'a', 'V_side', 'V_top', 'V5', 'dP0', 'p4-p5', '% Pa', 'hood'))
    choice = None
    for dn in (200, 250):
        for a in range(150, 231, 5):
            c = collector_new(p4, T, MG_B, float(a), dn)
            ok = c['V_side'] <= V_SIDE_MAX_FACTOR * sBo['V4'] and c['dp_static'] / PA <= DP_TARGET
            out['sweep'].append(dict(DN=dn, a=a, V_side=round(c['V_side'], 1), V_top=round(c['V_top'], 1), V5=round(c['V5'], 1),
                                     dP0=round(c['dP0_total']), dp_static=round(c['dp_static']), pct=round(100 * c['dp_static'] / PA, 3), ok=ok))
            print('%4d %4d %7.1f %6.1f %6.1f %7.0f %7.0f %7.3f %6.0f %s' % (dn, a, c['V_side'], c['V_top'], c['V5'], c['dP0_total'],
                                                                         c['dp_static'], 100 * c['dp_static'] / PA, c['hood_h'], '<-' if ok and choice is None else ''))
            if ok and choice is None: choice = c
        if choice: break
    c = choice
    a = c['a']; pp = PIPE[c['DN']]
    # ---------------------------------------------------------------- FPT with the new collector and like-for-like old
    def p5_new(s): return s['p4'] - collector_new(s['p4'], s['T03'], MG_B, a, c['DN'])['dp_static']
    def p5_oldm(s): return s['p4'] - collector_old_mine(s['p4'], s['T03'], MG_B)['dp_static']
    sBn, p5Bn, PsBn = solve_fpt(P_BACK_B, MG_B, p5_new)
    sBm, p5Bm, PsBm = solve_fpt(P_BACK_B, MG_B, p5_oldm)
    old_m = collector_old_mine(p4, T, MG_B)
    old_e3 = dict(dp_static=sBo['p4'] - sBo['p5'], V_plenum=sBo['V_plenum'], V5=sBo['V5'])
    out['fpt'] = dict(
        E3_design_variantA=dict(P_shaft_kW=PsA / 1e3, p5_Pa=p5A, eta_ts=sA['eta_ts'], note='E3 design value (E3_fpt_pmg.md: 24.86 kW shaft)'),
        B_old_collector_E3_model=dict(P_shaft_kW=PsBo / 1e3, eta_ts=sBo['eta_ts'], dp_static_p4_p5_Pa=old_e3['dp_static']),
        B_old_collector_same_model=dict(P_shaft_kW=PsBm / 1e3, eta_ts=sBm['eta_ts'], dp_static_p4_p5_Pa=old_m['dp_static']),
        B_new_E3B=dict(P_shaft_kW=PsBn / 1e3, eta_ts=sBn['eta_ts'], P_PMG_terminals_kW=PsBn * CR['power']['eta_PMG'] / 1e3,
                       p3_Pa=sBn['p3'], p4_Pa=sBn['p4'], p5_Pa=p5Bn, T03_C=sBn['T03'] - 273.15),
        penalty_vs_old_same_model_W=PsBn - PsBm, penalty_vs_old_same_model_pct=100 * (PsBn - PsBm) / PsBm,
        penalty_vs_old_E3_model_W=PsBn - PsBo, penalty_vs_old_E3_model_pct=100 * (PsBn - PsBo) / PsBo,
        delta_vs_E3_design_value_W=PsBn - PsA,
        sensitivity_W_per_100Pa=None)
    sBx, _, Psx = solve_fpt(P_BACK_B + 100.0, MG_B, p5_new)
    out['fpt']['sensitivity_W_per_100Pa'] = Psx - PsBn
    # ---------------------------------------------------------------- design block (read by the CAD)
    h = c['hood_h']
    Z_BOX = a                                   # inner half height = half width (square, symmetric about the axis)
    z_h0 = Z_BOX; z_h1 = z_h0 + h; z_fl0 = z_h1 + STUB_L - pp['fl_t']; z_fl1 = z_fl0 + pp['fl_t']
    out['design'] = dict(
        a_inner=a, sheet_t=T_SH, corner_R_inner=20.0, x_cover0=X_COVER0, t_cover=T_COVER, x_wp0=X_WP0, x_in0=X_IN0, x_in1=X_IN1,
        x_ep1=X_EP1, x_rad_e=X['rad_e'], x_outlet=XC, DN=c['DN'], pipe=pp, z_hood0=z_h0, z_hood1=z_h1, z_flange0=z_fl0,
        z_flange1=z_fl1, hood_h=h, wp_open_r=140.0, cover_OD=330.0, cover_ID=85.0, cover_bolts=dict(n=16, PCD=305.0, hole=9.0, M='M8', phase=11.25),
        mid_flange_bolts=dict(n=12, PCD=132.0, hole=6.6, M='M6', phase=15.0),
        ep_open_r=150.0, disc_OD=344.0, disc_t=4.0, disc_bolts=dict(n=16, PCD=322.0, hole=9.0, M='M8', phase=11.25),
        bell=dict(x0=X['rot_te'] + 2.2, r0=GEO['rot_hub_te'], R=GEO['hub_bend_R'], t=2.5),
        cone=dict(x0=X_EP1 + 1.0 + 4.0, r0=120.0, x1=336.0, r1=84.0, t=1.5, windows=6, flange=[333.0, 336.0, 76.0, 86.0]),
        heat_shield=dict(x0=X_EP1 + 1.0 + 4.0 + 0.2, t=2.5, r0=62.0, r1=116.0),
        support=dict(x=XC, lug_w=60.0, lug_t=10.0, lug_y1=278.0, leg_y=(258.0, 288.0), web_z=(-390.0, -330.0), plate_t=8.0,
                     base=(60.0, 600.0, 10.0), z_skid=-400.0),
        insulation=dict(t=None, material='microporous (Promat MICROTHERM / Morgan WDS class) in 0.5 mm 1.4301 cassettes'),
        sensors=dict(z=z_h1 + 0.5 * (STUB_L - pp['fl_t']), boss_r1=pp['OD'] / 2 + 60.0 + 15.0, immersion=60.0),
        drain=dict(x=XC, d='G1/2'))
    # ---------------------------------------------------------------- thermal: insulation / skin, heat loss, heat to the PMG
    SIG = 5.670e-8
    def skin(t_ins, T_air, Tg=T - 273.15, k=None, eps=0.30, h_c=8.0):
        k = k or (0.021 + 1.0e-5 * 0.5 * (Tg + 60.0) + 2.0e-8 * (0.5 * (Tg + 60.0)) ** 2)   # microporous k(Tmean)  # REF Microtherm datasheet trend
        Ts = T_air + 20.0
        for _ in range(60):
            h_r = eps * SIG * ((Ts + 273.15) ** 4 - (T_air + 273.15) ** 4) / max(Ts - T_air, 1e-3)
            q = (Tg - Ts) / (1 / 60.0 + T_SH * 1e-3 / 20.0 + t_ins * 1e-3 / k)       # gas side h ~60 W/m2K, steel
            Ts = T_air + q / (h_c + h_r)
        return Ts, q, k
    A_out = 2 * (2 * (a + T_SH + 70) * (L_IN + 2 * T_SH + 140)) * 1e-6 + 2 * ((2 * (a + 63)) ** 2 - math.pi * 0.125e3 ** 2) * 1e-6 * 0.7 \
        + 2 * (a + 63) * 2 * (L_IN + 126) * 1e-6 + math.pi * (pp['OD'] + 120) * 1e-3 * STUB_L * 1e-3 * 1.5   # jacket outer area (approx.)
    th = {}
    t_need = None
    for t_ in range(20, 151, 5):                      # thinnest standard panel giving <= 60 C skin in a 40 C enclosure
        if skin(float(t_), 40.0)[0] <= 60.0: t_need = t_; break
    out['design']['insulation']['t'] = float(t_need)
    for T_air in (30.0, 40.0):
        for t_ in sorted({60.0, float(t_need)}):
            Ts, q, k = skin(t_, T_air)
            th['enclosure_%.0fC_ins_%.0fmm' % (T_air, t_)] = dict(skin_C=Ts, q_W_m2=q, k_ins=k, heat_loss_W=q * A_out)
    # heat into the PMG housing (glycol): cone conduction + mica spacer, heat shield -> PMG front wall, hub bell -> B1 nose
    cn = out['design']['cone']; k625 = 15.5
    L_c = math.hypot(cn['x1'] - cn['x0'], cn['r0'] - cn['r1']) * 1e-3
    A_c = 2 * math.pi * 0.5 * (cn['r0'] + cn['r1']) * 1e-3 * cn['t'] * 1e-3 * 0.6     # 40 % windows at the mid length
    R_cone = L_c / (k625 * A_c); R_mica = 0.003 / (0.5 * math.pi * (0.086 ** 2 - 0.076 ** 2))
    T_root = T - 273.15 - 20.0; T_pmg = 55.0
    Q_cone = (T_root - T_pmg) / (R_cone + R_mica)
    A_face = math.pi * (0.0709 ** 2 - 0.062 ** 2)                                   # PMG front-wall ring facing the shield
    R_face = 0.0025 / 0.08 + 1 / (0.04 / 0.0023 + 5.0)
    Q_face = (T_root - T_pmg) / R_face * A_face
    Q_bell = CR['thermal']['Q_hub_bell_W']                                           # unchanged bell / B1 nose (E3 calc)
    th.update(insulation_t_mm=float(t_need), insulation_needed_for_60C_at_40C_mm=t_need, jacket_outer_area_m2=A_out,
              Q_to_PMG_cone_W=Q_cone, Q_to_PMG_face_W=Q_face, Q_bell_to_B1_W=Q_bell, Q_to_glycol_total_W=Q_cone + Q_face,
              Q_old_cone_W=CR['thermal']['Q_cone_W'], R_cone_K_W=R_cone, R_mica_K_W=R_mica,
              growth_mm=dict(box_half_width=a * 18.5e-6 * (T - 273.15 - 20), stub_top_vs_axis=(z_fl1) * 18.5e-6 * (T - 273.15 - 20),
                             box_length=(X_EP1 - X_COVER0) * 18.5e-6 * (T - 273.15 - 20),
                             axis_rise_bottom_foot_would_be=(a + T_SH) * 18.5e-6 * (T - 273.15 - 20) + 200 * 17e-6 * 300,
                             axis_rise_centreline_support=400 * 12e-6 * 25))
    out['thermal'] = th
    # ---------------------------------------------------------------- mass estimate (CAD gives the real numbers)
    rho_s = 7.8e-6
    m_box = rho_s * T_SH * ((2 * 2 * a + 2 * a) * L_IN + 2 * ((2 * a) ** 2 - math.pi * 145 ** 2))
    m_hood = rho_s * T_SH * 0.5 * (2 * (L_IN + 2 * a) + math.pi * pp['ID']) * math.hypot(h, 60)
    m_stub = rho_s * T_SH * math.pi * pp['OD'] * (STUB_L - pp['fl_t']) + rho_s * pp['fl_t'] * math.pi / 4 * (pp['fl_OD'] ** 2 - pp['OD'] ** 2)
    m_cover = rho_s * T_COVER * math.pi / 4 * (330 ** 2 - 85 ** 2)
    m_rear = rho_s * 4 * math.pi / 4 * (344 ** 2 - 120 ** 2) + 8.44e-6 * 1.5 * math.pi * (120 + 84) * L_c * 1e3 * 0.85 + 0.35
    out['mass_estimate'] = dict(box_kg=m_box, hood_kg=m_hood, stub_flange_kg=m_stub, cover_kg=m_cover, rear_unit_kg=m_rear,
                                metal_total_kg=m_box + m_hood + m_stub + m_cover + m_rear)
    # old (variant A) parts replaced, from docs/bom/engine_E3_bom.csv
    old = {}
    try:
        for r_ in csv.DictReader(open(os.path.join(ROOT, 'docs', 'bom', 'engine_E3_bom.csv'))):
            if r_['tag'] in ('E3-110', 'E3-111', 'E3-112', 'E3-113', 'E3-401', 'E3-504', 'E3-505', 'E3-506', 'E3-610'):
                old[r_['tag']] = float(r_['mass_kg'] or 0)
    except Exception as e:
        old['error'] = str(e)
    out['mass_estimate']['replaced_variantA_kg'] = old
    out['selected'] = dict(DN=c['DN'], a=a, V_side=c['V_side'], V_top=c['V_top'], V5=c['V5'], q5=c['q5'], Q_m3s=c['Q_m3s'],
                           rho=c['rho'], dP=c['dP'], dP0_total_Pa=c['dP0_total'], dp_static_p4_p5_Pa=c['dp_static'],
                           dp_static_pct_Pa=100 * c['dp_static'] / PA, dP0_pct_Pa=100 * c['dP0_total'] / PA,
                           net_p3_to_p5_Pa=p5Bn - sBn['p3'], dP0_P03_to_P05_Pa=sBn['P03'] - (p5Bn + c['q5']),
                           old_E3_model=old_e3, old_same_model=dict(dp_static=old_m['dp_static'], V_side=old_m['V_side'], V_top=old_m['V_top'],
                                                                     V5=old_m['V5'], dP=old_m['dP']))
    json.dump(out, open(os.path.join(HERE, 'e3b_exhaust_results.json'), 'w'), indent=1)
    # ---------------------------------------------------------------- report
    f = out['fpt']; s = out['selected']
    print('\nselected: DN%d, box inner %d x %d (a %d), hood h %d, outlet axis x %.1f, flange face z %.0f' % (c['DN'], 2 * a, 2 * a, a, h, XC, z_fl1))
    print('velocities: side %.1f, top %.1f, outlet %.1f m/s (V4 %.1f); Q %.3f m3/s, rho %.3f' % (c['V_side'], c['V_top'], c['V5'], sBo['V4'], c['Q_m3s'], c['rho']))
    print('losses (Pa): %s;  p4->p5 static %.0f Pa = %.2f %% Pa;  total %.0f Pa' % ({k: round(v) for k, v in c['dP'].items()}, c['dp_static'],
          100 * c['dp_static'] / PA, c['dP0_total']))
    print('old drum: E3 model p4->p5 %.0f Pa; same model %.0f Pa' % (old_e3['dp_static'], old_m['dp_static']))
    print('FPT shaft: E3 design (A) %.2f kW | B old (E3 model) %.2f | B old (same model) %.2f | B new %.2f kW -> penalty %.0f W (%.2f %%) like-for-like, '
          '%.0f W vs E3 model; vs E3 design value %+.0f W; %.0f W per +100 Pa'
          % (PsA / 1e3, PsBo / 1e3, PsBm / 1e3, PsBn / 1e3, f['penalty_vs_old_same_model_W'], f['penalty_vs_old_same_model_pct'],
             f['penalty_vs_old_E3_model_W'], f['delta_vs_E3_design_value_W'], f['sensitivity_W_per_100Pa']))
    print('p3 %.0f (%.2f %% above Pa), p4 %.0f, p5 %.0f Pa (%.2f %% above Pa)' % (sBn['p3'], 100 * (sBn['p3'] / PA - 1), sBn['p4'], p5Bn, 100 * (p5Bn / PA - 1)))
    for kk, v in th.items():
        if kk.startswith('enclosure'): print('insulation, %s: skin %.1f C, %.0f W/m2, loss %.0f W' % (kk, v['skin_C'], v['q_W_m2'], v['heat_loss_W']))
    print('insulation needed for 60 C skin at 40 C enclosure: %s mm; heat to PMG: cone %.0f W + face %.0f W (old cone %.0f W); bell->B1 %.0f W'
          % (t_need, Q_cone, Q_face, CR['thermal']['Q_cone_W'], Q_bell))
    print('growth (mm): %s' % {k: round(v, 2) for k, v in th['growth_mm'].items()})
    print('mass estimate: %s; replaced variant-A parts: %s' % ({k: round(v, 1) for k, v in out['mass_estimate'].items() if isinstance(v, float)}, old))


if __name__ == '__main__':
    main()
