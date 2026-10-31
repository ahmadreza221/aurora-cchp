"""AURORA-1000 bearing lubrication, seals and engine piping (docs/08 sec. 19): sizing and checks.

Reads the bearing results of sim/engine/a1000_rotor_stack.py (sim/engine/fea/a1000_rotor_stack.json: power loss and
oil flow per bearing, rotor rev 1.3 + the 4-pad journals of sec. 19) and the combustor design point
(sim/engine/fea/a1000_combustor.json). Writes sim/engine/fea/a1000_lube_piping.json, which the CAD scripts
cad/engine/a1000_rotor.py (galleries, jets, orifices, drains, seals) and cad/engine/a1000_piping.py (lines) read.

  1  oil per bearing: friction loss + heat soak (JB2: shaft conduction from R2 and the exhaust through the heat shield)
  2  supply: header pressure, inlet orifice per bearing, directed-lube jets (journals), leading-edge-groove feed (thrust),
     galleries and transfer tubes, ISFD feed and end seals
  3  anti-rotation of pads, carriers, ISFD rings and thrust base rings
  4  gravity drains for oil + foam (API 614: half full at <= 0.3 m/s, slope >= 1:50), vent and mist separator
  5  oil-cavity seals: windbacks, labyrinths, buffer air from the compressor stage-1 exit
  6  JB2 in the exhaust hub: heat shield, cooling air, wetted-wall temperature, soak-back after a hot stop
  7  lines: oil supply / drain / vent, buffer + cooling air, fuel P / A / B1 / B2, BOV DN125, combustor drains
Run: python3 sim/engine/a1000_lube_piping.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FEA = os.path.join(HERE, 'fea')
RS = json.load(open(os.path.join(FEA, 'a1000_rotor_stack.json')))
CB = json.load(open(os.path.join(FEA, 'a1000_combustor.json')))
OUT = os.path.join(FEA, 'a1000_lube_piping.json')
_EX = os.path.join(FEA, 'a1000_exhaust.json')                  # phase 2 (hub buffer air, JB2 mount), if present
EX = json.load(open(_EX)) if os.path.exists(_EX) else {}

N_OP = 15000.0
OM = N_OP * 2 * math.pi / 60
RHO_OIL, CP_OIL, T_IN = 860.0, 2000.0, 50.0                    # ISO VG 32 turbine oil, supply 50 C
DT_OIL = 20.0                                                   # design temperature rise per bearing
P_ATM = 1.013e5
R_AIR = 287.0
G = 9.81

CHECKS = []


def check(name, value, limit, unit, ok, note=''):
    CHECKS.append(dict(name=name, value=round(value, 4), limit=limit, unit=unit, ok=bool(ok), note=note))
    print('  %-4s %-66s %10.3f %s (limit %s) %s' % ('ok' if ok else 'FAIL', name, value, unit, limit, note))


def visc(T):
    """ISO VG 32 dynamic viscosity [Pa s] (Walther: 32 cSt at 40 C, 5.4 cSt at 100 C), as a1000_rotor_stack.visc"""
    t1, n1, t2, n2 = 313.15, 32.0, 373.15, 5.4
    y1, y2 = math.log10(math.log10(n1 + 0.7)), math.log10(math.log10(n2 + 0.7))
    B = (y1 - y2) / (math.log10(t2) - math.log10(t1)); A_ = y1 + B * math.log10(t1)
    return (10 ** (10 ** (A_ - B * math.log10(T + 273.15))) - 0.7) * 1e-6 * RHO_OIL


def lpm(q): return q * 6e4
def m3s(l): return l / 6e4
def area(d_mm): return math.pi / 4 * (d_mm * 1e-3) ** 2


def orifice_d(Q, dp, Cd=0.62, rho=RHO_OIL):
    """sharp-edged orifice diameter [mm] for flow Q [m3/s] at dp [Pa]"""
    return math.sqrt(Q / (Cd * math.sqrt(2 * dp / rho)) * 4 / math.pi) * 1e3


def pipe_dp(Q, d_mm, L, K=0.0, rho=RHO_OIL, mu=None):
    """pressure loss [Pa] in a pipe: Darcy (laminar 64 / Re, turbulent Blasius) + sum K"""
    d = d_mm * 1e-3; v = Q / area(d_mm); mu = mu or visc(T_IN)
    Re = rho * v * d / mu
    f = 64 / Re if Re < 2300 else 0.316 / Re ** 0.25
    return (f * L / d + K) * 0.5 * rho * v ** 2, v, Re


# standard sizes: (OD, wall) [mm]
TUBE_L = {10: 1.0, 12: 1.0, 15: 1.5, 18: 1.5, 22: 1.5, 28: 2.0, 35: 2.0, 42: 2.0}      # ISO 8434-1 24 deg cone, series L
PIPE = {15: (21.3, 2.0), 20: (26.9, 2.0), 25: (33.7, 2.0), 32: (42.4, 2.0), 40: (48.3, 2.0), 50: (60.3, 2.0), 65: (76.1, 2.0),
        80: (88.9, 2.3), 100: (114.3, 2.3), 125: (139.7, 2.6)}                        # EN 10216-5 / ASME B36.19 10S


def tube_id(od): return od - 2 * TUBE_L[od]
def pipe_id(dn): return PIPE[dn][0] - 2 * PIPE[dn][1]


def pick_tube(Q, v_max):
    for od in sorted(TUBE_L):
        if Q / area(tube_id(od)) <= v_max: return od
    raise ValueError('flow too large for series L')


def pick_pipe(A_req):
    for dn in sorted(PIPE):
        if area(pipe_id(dn)) >= A_req: return dn
    raise ValueError('no DN')


def martin(A, pu, pd, n, T, kco=1.2):
    """labyrinth leakage [kg/s], Martin with carry-over factor"""
    r = pd / pu
    phi = math.sqrt((1 - r * r) / (n - math.log(r)))
    return kco * A * pu * phi / math.sqrt(R_AIR * T)


res = {}
print('AURORA-1000 lubrication, seals and piping')

# ================================================================================================ 1. oil per bearing
jb = RS['bearings']['journal']; tb = RS['bearings']['thrust_design']; tbs = RS['bearings']['thrust_sized']
n_pad_j = jb[0].get('n_pad', 5)
print('1. heat per bearing (rotor stack: journals %d pads %.0f x %.0f, thrust %d + %d pads)' % (n_pad_j, jb[0]['D'], jb[0]['L'], tb['n'], tb['n_in']))
# JB2 heat soak: (a) conduction from the R2 hub (450 C, disc FEA) along the cast aft arm (r 58-66, 22 mm to the joint face)
# and the IN718 rear stub (neck r 25-44.5, 25 mm to the journal) - the arm and flange are washed by the R2 aft-cavity purge
# air, taken as 30 % of the bare-conduction heat removed before the journal; (b) the exhaust hub (670 C gas, wall ~640 C)
# through the heat shield (ceramic fibre 12 mm in a 1.4828 foil can, k 0.10 W/mK at 350 C mean) into the cooling-air
# gap, of which the share that reaches the housing wall is taken from the air-side balance in section 6
T_R2_HUB, T_JOURNAL = 450.0, 110.0
k_m247, k_718 = 14.0, 17.0
R_arm = 0.022 / (k_m247 * math.pi * (0.066 ** 2 - 0.058 ** 2))
R_stub = 0.025 / (k_718 * math.pi * (0.0445 ** 2 - 0.025 ** 2))
Q_cond = (T_R2_HUB - T_JOURNAL) / (R_arm + R_stub) * (1 - 0.30)
print('   JB2 shaft conduction from R2: R arm %.2f + stub %.2f K/W -> %.2f kW to the journal (after 30 %% purge-air cooling)' % (R_arm, R_stub, Q_cond / 1e3))

# ================================================================================================ 6 (first: JB2 thermal)
# JB2 in the exhaust hub, phase 2 mount (sim/engine/a1000_exhaust.py JB2_MOUNT): the housing (1.4313, OD r 130) is clamped in
# the support ring EX-412 (r 130-150, x 925-985); 8 radial keys (16 x 40 mm) bridge from the ring to the hub bore ring
# (r 185, the hot frame ~640 C). Cooling air from the frame manifold (compressor delivery, 175 C) enters through orifices at
# the strut roots and flows aft -> forward in the channel r 150-167 between the ring and the heat shield (12 mm ceramic
# fibre in 1.4828 foil, r 167-181), then purges the R2 aft cavity. Heat into the JB2 oil: (a) shaft conduction from the R2
# hub, (b) the 8 keys, each with a 3 mm mica / zirconia barrier pad on the ring side (required), (c) the cooling air, which
# is hotter than the oil, through the exposed ring / housing, (d) the shield leakage goes into the air
T_GAS_HUB = 640.0                                               # frame hub ring (turbine exit 670 C, recovery)
st = RS['thrust']['states']
T_AIR1 = st['c2']['T02'] - 273.15                               # manifold air = compressor delivery
P_AIR1 = 1.35e5                                                 # in the shield channel after the strut-root orifices
M_HUB = EX.get('buffer_air', {}).get('feed_g_s', 21.7) * 1e-3     # hub buffer / cooling air (phase 2: 3 x d 4 from P2)
M_COOL = 0.7 * M_HUB                                            # share through the channel round the JB2 shield
cp_a = 1010.0
k_ins, t_ins = 0.10, 0.012
A_SH = math.pi * 0.348 * 0.095 + math.pi / 4 * (0.362 ** 2 - 0.192 ** 2)       # shield cylinder r 174 x 95 + front disc
q_sh = k_ins / t_ins * (T_GAS_HUB - T_AIR1) * A_SH
T_out = T_AIR1 + q_sh / (M_COOL * cp_a)
T_a = 0.5 * (T_AIR1 + T_out)
# keys: 1.4313 (k 25) 16 x 40 mm, 35 mm free length; barrier pad 3 mm, k 2 W/mK
n_key, A_key, L_key = 8, 0.016 * 0.040, 0.035
R_key = L_key / (25.0 * A_key); R_pad = 0.003 / (2.0 * A_key)
T_OIL_DR = T_IN + DT_OIL
h_oil, A_oil = 600.0, math.pi * 0.184 * 0.090                    # spray-wetted housing bore round the bearing
mu_a, k_a = 2.6e-5, 0.036
rho_a = P_AIR1 / (R_AIR * (T_a + 273.15))
A_ch = math.pi * (0.167 ** 2 - 0.150 ** 2)
v_ch = M_COOL / rho_a / A_ch; Dh = 0.034
h_air = max(10.0, 0.023 * (rho_a * v_ch * Dh / mu_a) ** 0.8 * 0.7 ** 0.4 * k_a / Dh)
A_ring = math.pi * 0.300 * 0.060 + math.pi * 0.26 * 0.035         # ring OD + exposed housing OD
T_wall = T_OIL_DR + 20.0
for _ in range(50):
    T_ring = T_wall + 10.0
    Q_keys = n_key * (T_GAS_HUB - T_ring) / (R_key + R_pad)
    Q_keys_bare = n_key * (T_GAS_HUB - T_ring) / R_key
    Q_air = h_air * A_ring * (T_a - T_ring)
    q_h = Q_keys + Q_air
    T_wall = T_OIL_DR + q_h / (h_oil * A_oil)
T_wall_wet = T_wall
T_patch = T_wall + Q_keys / n_key / (h_oil * 3 * 0.040 * 0.060)    # under a key, spread over 3 x the key footprint
T_patch_bare = T_OIL_DR + (Q_keys_bare + Q_air) / (h_oil * A_oil) + Q_keys_bare / n_key / (h_oil * 3 * 0.040 * 0.060)
print('6. JB2 in the exhaust hub (phase 2 mount): shield %.2f m2, %.0f mm fibre; cooling air %.0f g/s at %.0f C (manifold), out %.0f C'
      % (A_SH, t_ins * 1e3, M_COOL * 1e3, T_AIR1, T_out))
print('   keys %.0f W (bare keys %.0f W), air -> ring %.0f W, shield %.0f W into the air; wetted wall %.0f C, under a key %.0f C (bare %.0f C)'
      % (Q_keys, Q_keys_bare, Q_air, q_sh, T_wall_wet, T_patch, T_patch_bare))
T_seal_land = T_JOURNAL + (T_R2_HUB - T_JOURNAL) * 0.7 * R_stub * 0.35 / (R_arm + R_stub)
T_COKE = 150.0                                                  # wetted-wall limit for a mineral turbine oil (API 614 practice)
check('JB2 housing wetted-wall temperature (running)', T_wall_wet, T_COKE, 'C', T_wall_wet <= T_COKE, 'coking limit')
check('JB2 wetted wall under a frame key (with 3 mm barrier pads)', T_patch, T_COKE, 'C', T_patch <= T_COKE,
      'bare keys %.0f C' % T_patch_bare)
check('JB2 shield cooling-air outlet temperature', T_out, 300.0, 'C', T_out <= 300.0, 'buffer + R2 aft purge air')
# soak-back after a hot stop: the hub and the R2 disc keep feeding heat; housing + cartridge + ring ~ 30 kg steel
m_cart, cp_s, tau_disc = 30.0, 480.0, 900.0
Q0 = Q_cond / 0.7 + Q_keys                                      # no purge air after the stop
E_soak = Q0 * tau_disc
dT_nopost = E_soak / (m_cart * cp_s) * 0.6                      # 40 % lost to the hub air and radiation
T_peak_nopost = T_wall_wet + dT_nopost
Q_post = m3s(3.0)                                               # post-lube flow, l/min -> m3/s
dT_post = Q0 / (RHO_OIL * CP_OIL * Q_post)
T_peak_post = T_IN + dT_post + 15.0
print('   soak-back after a hot stop: %.1f MJ; without post-lube the wetted wall reaches ~%.0f C, with 3 l/min post-lube %.0f C'
      % (E_soak / 1e6, T_peak_nopost, T_peak_post))
check('JB2 soak-back with post-lube 3 l/min for 40 min', T_peak_post, T_COKE, 'C', T_peak_post <= T_COKE,
      'without post-lube %.0f C' % T_peak_nopost)
res['jb2_thermal'] = dict(mount='phase 2 EX-412 ring + 8 keys', shield_area_m2=A_SH, fibre_mm=t_ins * 1e3, k_fibre=k_ins,
                          m_cool_kg_s=M_COOL, T_air_in_C=T_AIR1, T_air_out_C=T_out, q_shield_kW=q_sh / 1e3, h_air=h_air,
                          Q_keys_kW=Q_keys / 1e3, Q_keys_bare_kW=Q_keys_bare / 1e3, Q_air_kW=Q_air / 1e3, q_into_oil_kW=q_h / 1e3,
                          T_wall_wetted_C=T_wall_wet, T_under_key_C=T_patch, T_under_key_bare_C=T_patch_bare,
                          key_pad='3 mm mica / zirconia between each key and the support ring (k <= 2 W/mK)',
                          Q_shaft_conduction_kW=Q_cond / 1e3, T_seal_land_C=T_seal_land,
                          soak_MJ=E_soak / 1e6, T_peak_no_postlube_C=T_peak_nopost, T_peak_postlube_C=T_peak_post,
                          post_lube=dict(flow_lpm=3.0, minutes=40, pump='AC main; DC emergency pump on loss of AC'),
                          coke_limit_C=T_COKE)

# ================================================================================================ 1. (cont.) flows
brg = {}
for name, P_kW, extra_kW in (('JB1', jb[0]['P_kW'], 0.0), ('JB2', jb[1]['P_kW'], Q_cond / 1e3 + max(q_h, 0) / 1e3),
                             ('TB', tbs['P_kW'], 0.0)):
    Qh = (P_kW + extra_kW) * 1e3 / (RHO_OIL * CP_OIL * DT_OIL)
    brg[name] = dict(P_friction_kW=P_kW, P_soak_kW=extra_kW, Q_heat_lpm=lpm(Qh))
# ISFD: feed into the land through 2 orifices, end seals = two piston rings (gap 0.15 mm, ~0.6 l/min each damper at 1.0 bar)
Q_isfd = m3s(0.6)
for name in ('JB1', 'JB2'):
    brg[name]['Q_isfd_lpm'] = lpm(Q_isfd)
# design flow: heat flow x 1.15 (pad-temperature margin, filter / orifice tolerance) + the ISFD flow
for name, b in brg.items():
    b['Q_design_lpm'] = 1.15 * b['Q_heat_lpm'] + b.get('Q_isfd_lpm', 0.0)
    print('   %-4s friction %.2f kW + soak %.2f kW -> %.1f l/min for %.0f K; design %.1f l/min' % (
        name, b['P_friction_kW'], b['P_soak_kW'], b['Q_heat_lpm'], DT_OIL, b['Q_design_lpm']))
Q_turb = sum(b['Q_design_lpm'] for b in brg.values())
# gearbox (bought in, shares the oil): 1,100 kW at >= 98.5 % -> 16.5 kW, 20 K
P_gb = 1100.0 * 0.015
Q_gb = P_gb * 1e3 / (RHO_OIL * CP_OIL * DT_OIL)
Q_tot = Q_turb + lpm(Q_gb) * 1.1
print('   turbine %.1f l/min + gearbox %.1f l/min -> lube module %.0f l/min; heat %.1f kW' % (Q_turb, lpm(Q_gb) * 1.1, Q_tot,
      sum(b['P_friction_kW'] + b['P_soak_kW'] for b in brg.values()) + P_gb))

# ================================================================================================ 2. supply, orifices, jets
P_HDR = 2.0e5                                                   # header at the engine (gauge), PCV on the lube module
P_JET = 1.0e5                                                   # pressure drop across the directed-lube jets / LEG feed
print('2. supply: header %.1f bar(g) at the engine, %.0f C, filter 10 um abs (beta 200), cooler, PCV' % (P_HDR / 1e5, T_IN))
lines = {}
# journals: directed lube, one spray bar in each of the 4 inter-pad gaps (0 / 90 / 180 / 270 deg), each with 2 jets aimed
# at the leading edge of the next pad (rotation +theta), 15 deg against the shaft surface
N_BAR, N_JET = 4, 2
for name in ('JB1', 'JB2'):
    b = brg[name]; Qj = m3s(b['Q_design_lpm'] - b['Q_isfd_lpm'])
    v_jet = 0.70 * math.sqrt(2 * P_JET / RHO_OIL)
    d_jet = math.sqrt(Qj / (N_BAR * N_JET) / v_jet * 4 / math.pi) * 1e3
    d_jet_sel = max(1.2, round(d_jet * 10) / 10)
    v_sel = Qj / (N_BAR * N_JET * area(d_jet_sel))
    dp_jet = 0.5 * RHO_OIL * (v_sel / 0.70) ** 2
    b.update(jets=dict(bars=N_BAR, per_bar=N_JET, d_mm=d_jet_sel, v_m_s=v_sel, dp_bar=dp_jet / 1e5, aim='leading edge of the next pad, 15 deg to the surface, with rotation'))
    check('%s jet diameter (clogging, 10 um filter)' % name, d_jet_sel, 1.2, 'mm', d_jet_sel >= 1.2)
    print('   %s directed lube: %d bars x %d jets d %.1f mm, %.1f m/s, dp %.2f bar' % (name, N_BAR, N_JET, d_jet_sel, v_sel, dp_jet / 1e5))
    b['p_bearing_bar'] = dp_jet / 1e5
# thrust: leading-edge-groove pads, feed hole per pad from the base-ring gallery; the flow splits by the pad losses
P_load, P_in = tbs['P_loaded_kW'], tbs['P_kW'] - tbs['P_loaded_kW']
Qtb = m3s(brg['TB']['Q_design_lpm'])
q_loaded, q_inact = Qtb * P_load / tbs['P_kW'] / tb['n'], Qtb * P_in / tbs['P_kW'] / tb['n_in']
d_leg_l = orifice_d(q_loaded, P_JET); d_leg_i = orifice_d(q_inact, P_JET)
brg['TB'].update(leg=dict(n_loaded=tb['n'], n_inactive=tb['n_in'], d_feed_loaded_mm=round(d_leg_l, 1), d_feed_inactive_mm=round(d_leg_i, 1),
                          Q_loaded_lpm=lpm(q_loaded * tb['n']), Q_inactive_lpm=lpm(q_inact * tb['n_in'])), p_bearing_bar=P_JET / 1e5)
print('   TB leading-edge grooves: %d loaded pads feed d %.1f mm (%.1f l/min), %d inactive d %.1f mm (%.1f l/min) at %.1f bar' % (
    tb['n'], d_leg_l, lpm(q_loaded * tb['n']), tb['n_in'], d_leg_i, lpm(q_inact * tb['n_in']), P_JET / 1e5))
# flow-setting orifices: journals - one in each of the 2 transfer tubes (housing groove at line pressure -> carrier gallery
# at the jet pressure), so the ISFD sees the full line pressure; thrust - one in the housing inlet union
for name, L_line, nK, n_or in (('JB1', 2.5, 6.0, 2), ('TB', 2.5, 6.0, 1), ('JB2', 4.5, 8.0, 2)):
    b = brg[name]; Q = m3s(b['Q_design_lpm'])
    od = pick_tube(Q, 1.5)
    dpl, v, Re = pipe_dp(Q, tube_id(od), L_line, nK)
    dpo = P_HDR - dpl - b['p_bearing_bar'] * 1e5
    Qo = (Q - (Q_isfd if name != 'TB' else 0.0)) / n_or
    d_or = orifice_d(Qo, dpo)
    b.update(supply_tube_OD=od, supply_v=v, line_dp_bar=dpl / 1e5, p_groove_barg=(P_HDR - dpl) / 1e5, orifice_dp_bar=dpo / 1e5,
             orifices=n_or, orifice_mm=round(d_or, 1), orifice_at='transfer tubes' if n_or == 2 else 'inlet union')
    print('   %-4s supply tube %d x %.1f (24 deg cone), %.2f m/s, line %.3f bar; %d orifice(s) d %.1f mm for %.2f bar (%s)' % (
        name, od, TUBE_L[od], v, dpl / 1e5, n_or, d_or, dpo / 1e5, b['orifice_at']))
    check('%s flow orifice diameter (>= 3 mm, no clogging)' % name, d_or, 3.0, 'mm', d_or >= 3.0)
# galleries: housing feed groove at the ISFD outer ring (between two O-rings) 10 x 6 mm; two transfer tubes (OD 12 / ID 8,
# FKM O-ring ends, cross the spring gap between two S-springs, carry the orifices) into the carrier gallery 8 x 5 mm; spray
# bars bored 4 mm
for name in ('JB1', 'JB2'):
    Q = m3s(brg[name]['Q_design_lpm'])
    v_gal = Q / 2 / (10e-3 * 6e-3)                             # the groove feeds both ways round
    v_tt = (Q - Q_isfd) / 2 / area(8.0)
    v_cg = (Q - Q_isfd) / 4 / (8e-3 * 5e-3)
    brg[name]['galleries'] = dict(housing_groove_mm='10 x 6', v_groove=v_gal, transfer_tubes='2 x OD 12 / ID 8, FKM O-rings',
                                  v_transfer=v_tt, carrier_groove_mm='8 x 5', v_carrier=v_cg, spray_bar_bore_mm=4.0)
    check('%s gallery / transfer-tube velocity' % name, max(v_gal, v_tt, v_cg), 2.0, 'm/s', max(v_gal, v_tt, v_cg) <= 2.0)
# ISFD feed: 2 orifices from the housing groove into the squeeze-film land (r 80, L 35, c 0.13), the land ends sealed by
# piston rings (cast iron, gap 0.15 mm); supply 1.0 bar above the cavity keeps a full film at the normal orbit
sfd = RS['bearings']['sfd']
mu70 = visc(70.0)
# normal orbit in the damper <= 2 x the API unbalance response of the rotor (the damper moves less than the journal)
api_um = max(c['value'] for c in RS['checks'] if c['test'].startswith('API unbalance response'))
e_norm = 2 * api_um / (sfd['c'] * 1e6)
p_dyn = 6 * mu70 * OM * e_norm * (0.035 / 2) ** 2 / (0.13e-3) ** 2 / (1 - e_norm) ** 3
p_isfd = brg['JB1']['p_groove_barg'] * 1e5 - 0.3e5               # land pressure after the feed orifices
d_isfd = orifice_d(Q_isfd / 2, 0.3e5)
res['isfd'] = dict(feed_orifices=2, d_orifice_mm=round(d_isfd, 1), Q_lpm=lpm(Q_isfd), end_seals='2 piston rings (cast iron), gap 0.15 mm',
                   p_land_barg=p_isfd / 1e5, e_normal=e_norm, p_dynamic_normal_bar=p_dyn / 1e5,
                   film='full film at the normal orbit; pi-film at large orbits (both in the rotor model)')
print('   ISFD: fed from the housing groove at line pressure, 2 orifices d %.1f mm, %.1f l/min, piston-ring end seals; land %.2f bar(g),'
      ' squeeze pressure at 2 x the API orbit (e %.2f) %.2f bar' % (d_isfd, lpm(Q_isfd), p_isfd / 1e5, e_norm, p_dyn / 1e5))
check('ISFD full film at 2 x the API orbit (land / squeeze pressure)', p_isfd / p_dyn, 1.0, '-', p_isfd >= p_dyn)

# ================================================================================================ 3. anti-rotation
print('3. anti-rotation (torque from the bearing friction, x 3 for start-up with mixed friction)')
ar = {}
for name, P_kW, r_pin, n_pin, d_pin in (('JB1/JB2 pad (each pad: pivot pin + offset stop pin)', jb[0]['P_kW'] / 4, 0.055, 1, 4.0),
                                        ('JB1/JB2 carrier in the ISFD ring (radial pin d 6 at 135 deg; split dowels d 6 / d 8)', jb[0]['P_kW'], 0.074, 1, 6.0),
                                        ('JB1/JB2 ISFD ring in the housing (radial pin d 8 at 45 deg)', jb[0]['P_kW'], 0.092, 1, 8.0),
                                        ('TB base ring in the housing (2 dowels per ring)', tbs['P_loaded_kW'], 0.074, 2, 6.0)):
    T = 3 * P_kW * 1e3 / OM
    F = T / r_pin / n_pin
    tau = F / area(d_pin) / 1e6
    ar[name] = dict(torque_Nm=T, force_N=F, d_pin_mm=d_pin, shear_MPa=tau)
    check('anti-rotation: ' + name, tau, 60.0, 'MPa', tau <= 60.0, 'pin %.0f mm, %.1f N m' % (d_pin, T))
res['anti_rotation'] = ar

# ================================================================================================ 5. seals and buffer air
print('5. oil-cavity seals')
# cavity pressure: tank vented through the mist separator (fan, -10 mbar) -> bearing cavities ~ 1.0 bar abs
P_CAV = P_ATM - 0.01e5
p_eye = st['c1']['p_eye']
T_buf = st['c1']['T02']                                         # TB buffer: stage-1 air
seals = {}
# JB1 front (coupling side, guard at ambient): windback (2-start, 3 mm pitch, handed to pump oil inward) + 3-tooth labyrinth
#   r 43, c 0.20; no buffer air: the cavity runs 10 mbar below the guard, so air leaks inward, oil cannot leave
A = 2 * math.pi * 0.043 * 0.20e-3
m = martin(A, P_ATM, P_CAV, 3, 303.0)
seals['JB1 front (coupling side)'] = dict(type='windback + 3-tooth labyrinth, r 43, c 0.20, no buffer', air_into_cavity_g_s=m * 1e3)
# TB rear (compressor inlet side, impeller-1 eye at p_eye < ambient): buffered: oil-side windback + 3 teeth | buffer annulus
#   | 4 teeth to the inlet; r 49, c 0.15; buffer 1.10 bar abs
P_BUF = 1.10e5
A = 2 * math.pi * 0.049 * 0.15e-3
m_in = martin(A, P_BUF, P_CAV, 3, T_buf); m_out = martin(A, P_BUF, p_eye, 4, T_buf)
seals['TB rear (inlet side, eye %.2f bar)' % (p_eye / 1e5)] = dict(type='windback + 3 teeth | buffer annulus 1.10 bar | 4 teeth, r 49, c 0.15',
                                                               air_into_cavity_g_s=m_in * 1e3, air_to_inlet_g_s=m_out * 1e3, buffer_g_s=(m_in + m_out) * 1e3)
check('TB rear seal: buffer above the eye pressure', P_BUF / p_eye, 1.05, '-', P_BUF >= 1.05 * p_eye, 'oil cannot be drawn into the compressor')
# JB2 front (turbine side, R2 aft cavity p_ra, hot): windback + 3 teeth | buffer annulus | 4 teeth to the R2 aft cavity on the
# r 44.5 land, c 0.20 (hot). The buffer annulus is fed from the hub cavity (phase 2: 3 choked d 4 orifices from P2 in the
# strut roots, 1.16 - 1.51 bar with a worn / new hub labyrinth) through 4 restrictor holes in the housing and the seal ring.
# The restrictor size is chosen so the buffer stays >= 3 % above the R2 aft cavity at the lowest hub pressure (worn hub
# labyrinth; hot gas then cannot reach the oil-side teeth) and the air into the bearing cavity stays within the DN25 vent
# of the -y strut at the highest (new labyrinth). An 8 % margin cannot be had over the whole hub range with a DN25 vent.
p_ra = RS['thrust']['cavities']['p_ra']
A2 = 2 * math.pi * 0.0445 * 0.20e-3
T2k = T_out + 273.15
p_hub = sorted(EX.get('buffer_air', {}).get('cavity_bar', {'lo': 1.16, 'hi': 1.51}).values())
P_HUB = (p_hub[0] * 1e5, p_hub[-1] * 1e5)


def jb2_buffer(d_r, P_h):
    """annulus pressure where 4 restrictors d_r [mm] from the hub P_h feed the two labyrinths: (p_b, m_in, m_out)"""
    lo, hi = p_ra * 1.0001, P_h * 0.9999
    for _ in range(60):
        p_b = 0.5 * (lo + hi)
        rho = P_h / (R_AIR * T2k)
        m_r = 0.62 * 4 * area(d_r) * math.sqrt(2 * rho * (P_h - p_b))
        need = martin(A2, p_b, P_CAV, 3, T2k) + martin(A2, p_b, p_ra, 4, T2k)
        lo, hi = (p_b, hi) if m_r > need else (lo, p_b)
    return p_b, martin(A2, p_b, P_CAV, 3, T2k), martin(A2, p_b, p_ra, 4, T2k)


A_vent25 = area(pipe_id(25))
cands = []
for d_r in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0):
    pb_lo, _, _ = jb2_buffer(d_r, P_HUB[0]); pb_hi, mi_hi, mo_hi = jb2_buffer(d_r, P_HUB[1])
    v_hi = mi_hi / 1.15 / A_vent25
    if pb_lo >= 1.03 * p_ra and v_hi <= 10.0: cands.append((d_r, pb_lo, pb_hi, mi_hi, v_hi))
D_RESTR = cands[-1][0] if cands else 3.0
pb_lo, m2_in_lo, m2_out_lo = jb2_buffer(D_RESTR, P_HUB[0]); P_BUF2, m2_in, m2_out = jb2_buffer(D_RESTR, P_HUB[1])
print('   JB2 buffer: hub %.2f - %.2f bar (phase 2), 4 restrictors d %.1f -> annulus %.2f - %.2f bar, air into the cavity %.1f - %.1f g/s'
      % (P_HUB[0] / 1e5, P_HUB[1] / 1e5, D_RESTR, pb_lo / 1e5, P_BUF2 / 1e5, m2_in_lo * 1e3, m2_in * 1e3))
check('JB2 front seal: buffer above the R2 aft cavity at the lowest hub pressure', pb_lo / p_ra, 1.03, '-', pb_lo >= 1.03 * p_ra,
      'restrictors 4 x d %.1f' % D_RESTR)
check('JB2 vent DN25 (phase 2 strut): air velocity at the highest hub pressure', m2_in / 1.15 / A_vent25, 10.0, 'm/s',
      m2_in / 1.15 / A_vent25 <= 10.0)
seals['JB2 front (turbine side, R2 aft cavity %.2f bar)' % (p_ra / 1e5)] = dict(
    type='split ring: 3 teeth | buffer annulus %.2f-%.2f bar (hub air, 4 restrictors d %.1f) | windback, r 44.5, c 0.20' % (
        pb_lo / 1e5, P_BUF2 / 1e5, D_RESTR), air_into_cavity_g_s=m2_in * 1e3, air_to_R2_cavity_g_s=m2_out * 1e3,
    restrictor_mm=D_RESTR, p_buffer_bar=[pb_lo / 1e5, P_BUF2 / 1e5])
# JB2 rear: the rear stub ends inside the housing: blind end cover with an O-ring, no shaft seal
seals['JB2 rear'] = dict(type='blind end cover (the rear stub ends inside), O-ring; no shaft seal', air_into_cavity_g_s=0.0)
for k, v in seals.items():
    print('   %-46s %-70s air into the cavity %.1f g/s' % (k, v['type'], v['air_into_cavity_g_s']))
# hub air balance (phase 2 feed): the part that goes into the JB2 cavity leaves through the vent; the rest purges the R2
# aft cavity through the hub labyrinth
m_purge = M_HUB - m2_in
check('R2 aft cavity purge left after the JB2 buffer', m_purge * 1e3, 3.0, 'g/s', m_purge >= 3e-3, 'hub feed %.1f g/s' % (M_HUB * 1e3))
res['seals'] = seals
res['hub_air_split_g_s'] = dict(feed=M_HUB * 1e3, jb2_cavity=m2_in * 1e3, R2_aft_purge=m_purge * 1e3)
# cost of the seal air: the TB buffer is stage-1 air (the part to the eye is recompressed, the part into the cavity leaves
# through the vent); the JB2 buffer air is compressor-delivery air from the frame manifold (phase 2's cooling flow), of which
# the part into the cavity leaves the cycle through the vent (the rest purges the R2 aft cavity, counted by phase 2)
w1 = 1005.0 * (st['c1']['T02'] - st['c1']['T01']); w12 = 1005.0 * (st['c2']['T02'] - st['c1']['T01'])
w_net = 985e3 / st['m_air']
m_bleed = m_in + m_out
P_cost = m_bleed * w1 + m_in * w_net + m2_in * (w12 + w_net)
res['bleed'] = dict(TB_buffer_kg_s=m_bleed, JB2_cavity_kg_s=m2_in, lost_kg_s=m_in + m2_in, P_cost_kW=P_cost / 1e3)
print('   seal air: TB buffer %.1f g/s from stage 1, JB2 cavity %.1f g/s from the manifold; %.1f g/s leave through the vent, cost ~%.1f kW' % (
    m_bleed * 1e3, m2_in * 1e3, (m_in + m2_in) * 1e3, P_cost / 1e3))
check('seal air: power cost', P_cost / 1e3, 0.005 * 985, 'kW', P_cost <= 0.005 * 985e3, '<= 0.5 % of the rating')

# ================================================================================================ 4. drains, vent
print('4. drains (API 614: half full at <= 0.3 m/s, slope >= 1:50) and vent')
air_cav = dict(FBH=(seals['JB1 front (coupling side)']['air_into_cavity_g_s'] + m_in * 1e3) * 1e-3, JB2=m2_in)
drains = {}
for cav, Q_l in (('FBH (JB1 + TB)', brg['JB1']['Q_design_lpm'] + brg['TB']['Q_design_lpm']), ('JB2', brg['JB2']['Q_design_lpm'])):
    Q = m3s(Q_l) * 1.3                                          # foam: 30 % entrained air by volume in the drain
    A_req = 2 * Q / 0.30
    dn = pick_pipe(A_req)
    dn = max(dn, 65 if cav.startswith('FBH') else 50)           # sump outlet flanges: FBH DN65, JB2 DN50 (strut passage)
    a_cav = air_cav['FBH' if cav.startswith('FBH') else 'JB2']
    # the buffer air leaves each cavity through its own vent (top of the housing) to the reservoir, so the drain runs oil
    dn_v = 25                                                   # FBH: DN25; JB2: DN25 in the -y strut (phase 2)
    v_vent = a_cav / 1.15 / area(pipe_id(dn_v))
    drains[cav] = dict(oil_lpm=Q_l, design_m3s=Q, DN=dn, ID_mm=pipe_id(dn), v_half_full=Q / (0.5 * area(pipe_id(dn))), slope_min='1:50',
                       air_g_s=a_cav * 1e3, vent_DN=dn_v, v_vent_m_s=v_vent)
    print('   %-15s %.1f l/min (+30 %% foam) -> DN%d (ID %.1f): %.2f m/s half full; vent DN%d for %.1f g/s air: %.1f m/s' % (
        cav, Q_l, dn, pipe_id(dn), Q / (0.5 * area(pipe_id(dn))), dn_v, a_cav * 1e3, v_vent))
    check('drain %s: velocity half full' % cav, Q / (0.5 * area(pipe_id(dn))), 0.30, 'm/s', Q / (0.5 * area(pipe_id(dn))) <= 0.30)
    check('vent %s: air velocity' % cav, v_vent, 10.0, 'm/s', v_vent <= 10.0, 'cavity top -> reservoir, mist separator on the tank')
# the JB2 drain passes the bottom exhaust strut: an oval passage of the same area as DN50 (40 x 66 mm) in a 56 mm strut
res['drains'] = drains
air_total = sum(air_cav.values())
# tank vent: mist separator (coalescing element + small fan, -10 mbar); vent DN50 to atmosphere above the package roof
res['vent'] = dict(air_into_tank_g_s=air_total * 1e3, separator='coalescing element + 0.1 kW fan, tank at -10 mbar', vent_DN=50,
                   oil_carry_over_target='< 5 mg/m3', v_vent=air_total / 1.15 / area(pipe_id(50)))
print('   tank vent: %.1f g/s air -> mist separator, DN50 outlet (%.2f m/s)' % (air_total * 1e3, air_total / 1.15 / area(pipe_id(50))))
# drain head: FBH outlet z -175 and JB2 strut outlet z -470 to the tank top z -715 (reservoir in the base frame)
for cav, z0, L in (('FBH', -175.0, 1.4), ('JB2', -470.0, 2.2)):
    slope = (z0 - (-715.0) - 40.0) / (L * 1e3)
    check('drain %s: available slope to the reservoir in the base frame' % cav, slope, 0.02, '-', slope >= 0.02, 'run %.1f m' % L)
res['reservoir'] = dict(location='in the base frame between the beams at x -540 and 200 (under the couplings and the gearbox front), top z -715',
                        working_l=round(Q_tot * 4), volume_l=round(Q_tot * 4 * 1.3), retention_min=4,
                        heater_kW=3.0, note='gearbox drains straight down through the deck')

# ================================================================================================ 7. lines
print('7. engine lines')
fuel = CB['design_point']; pm = CB['premixer']['fuel']
m_f = fuel['m_fuel']; W_gas = 18.12
p_man = pm['p_manifold_bar'] * 1e5; p_av = pm['p_available_bar'] * 1e5
T_gas = 293.15
rho_g = p_man / (8314.0 / W_gas * T_gas)
mu_g = 1.1e-5
circuits = dict(P=1, A=3, B1=1, B2=2)                             # premixers per circuit (sec. 16.9)
fl = {}
dp_fuel_max = 0.0
for c, n in circuits.items():
    m = m_f * n / 7.0; Qg = m / rho_g
    od = pick_tube(Qg, 20.0)
    dp, v, Re = pipe_dp(Qg, tube_id(od), 4.0, 5.0, rho=rho_g, mu=mu_g)       # valve block -> braided hose -> manifold
    od_p = pick_tube(m_f / 7.0 / rho_g, 20.0)                                # pigtail to each lance
    dpp, vp, _ = pipe_dp(m_f / 7.0 / rho_g, tube_id(od_p), 0.6, 2.5, rho=rho_g, mu=mu_g)
    fl[c] = dict(premixers=n, m_kg_s=m, tube_OD=od, v=v, dp_bar=dp / 1e5, pigtail_OD=od_p, v_pigtail=vp, dp_pigtail_bar=dpp / 1e5)
    dp_fuel_max = max(dp_fuel_max, (dp + dpp) / 1e5)
    print('   fuel %-2s %d premixer(s) %.4f kg/s: hose + tube %d x %.1f, %.1f m/s, %.3f bar; pigtail %d x %.1f, %.1f m/s, %.3f bar' % (
        c, n, m, od, TUBE_L[od], v, dp / 1e5, od_p, TUBE_L[od_p], vp, dpp / 1e5))
margin = (p_av - p_man) / 1e5 - (dp_fuel_max - 0.03)
check('fuel lines: supply margin after the line loss (combustor allowed 0.03 bar for lances)', margin, 0.05, 'bar', margin >= 0.05)
res['fuel'] = dict(circuits=fl, rho_kg_m3=rho_g, dp_max_bar=dp_fuel_max, margin_bar=margin,
                   header='DN50 PN16 from the gas train (shut-off, vent, 4 staging valves on the skid) to the valve block')

# oil-supply header from the module to the engine junction (turbine branch)
Q = m3s(Q_turb)
od_h = pick_tube(Q, 1.2)
dph, vh, _ = pipe_dp(Q, tube_id(od_h), 3.0, 8.0)
res['oil_header'] = dict(Q_lpm=Q_turb, tube_OD=od_h, v=vh, dp_bar=dph / 1e5)
print('   oil header (turbine branch) %.1f l/min: tube %d x %.1f, %.2f m/s' % (Q_turb, od_h, TUBE_L[od_h], vh))
# buffer / cooling air: stage-1 tap (return channel, top) -> manual valve + orifice -> two branches
m_air_lines = dict(TB_buffer=(m_in + m_out))
air = {}
for k, m in m_air_lines.items():
    rho_a = 1.80e5 / (R_AIR * T_buf)
    Q = m / rho_a
    od = pick_tube(Q, 25.0)
    air[k] = dict(m_g_s=m * 1e3, tube_OD=od, v=Q / area(tube_id(od)))
    print('   air %-12s %.1f g/s: tube %d x %.1f, %.1f m/s' % (k, m * 1e3, od, TUBE_L[od], Q / area(tube_id(od))))
res['air_lines'] = air
res['bov'] = dict(DN=125, m_kg_s=3.6, by='phase 2 (EX-441): tee on the DN350 cold-air pipe -> DN125 valve -> DN200 dump to the '
                  'economizer inlet plenum', valve='DN125 PN16 butterfly, pneumatic fail-open, 150 ms stroke (sec. 13.11)')
# combustor drains: false-start drain at the lowest point of the hot-gas scroll (CB-331, bottom) and of the can base plate
res['combustor_drains'] = dict(points=['scroll hot-gas casing CB-331 bottom (through CB-341), DN15', 'can base plate CB-302 low point, DN15'],
                               valve='normally open, closes at light-off (air-operated, fail-open), to a closed drain pot',
                               tube_OD=18)
res['bearings'] = brg
res['lube_module'] = dict(flow_lpm=round(Q_tot), header_barg=P_HDR / 1e5, T_supply_C=T_IN, filter='duplex 10 um abs, beta 200',
                          pumps='AC main + AC standby (auto changeover) + DC emergency pump (coast-down and post-lube)',
                          cooler='air-cooled, fan, sized for 40 C ambient', heat_kW=sum(b['P_friction_kW'] + b['P_soak_kW'] for b in brg.values()) + P_gb)

ok = sum(c['ok'] for c in CHECKS)
print('checks: %d of %d pass' % (ok, len(CHECKS)))
res['checks'] = CHECKS
json.dump(res, open(OUT, 'w'), indent=1, default=float)
