# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""GR180 version E - generator cooling system design + lumped-parameter thermal network (LPTN), steady and transient,
with the closed-loop temperature control.  Goal (user): keep winding and magnet temperatures CONSTANT for 0-45 C ambient
and all loads.

Cooling concept
  * stator: dedicated glycol loop (MEG 35 %), double-start helical channel in the Al jacket sleeve around the shrunk-in
    stator; supply temperature held at 55 C at every ambient by a 3-way mixing valve + EC-fan dry cooler (split range);
    55 C is reachable at 45 C ambient (+2 K recirculation) with an 8 K approach -> the stator sees the same coolant all year
  * rotor / air gap / end windings: filtered plenum air (the GT intake is already G4+F7; + F9 cartridge on the blower) blown
    by an EC high-pressure radial blower into the front end bell, onto the front end winding, through the 3 mm air gap,
    over the rear end winding and out of the rear end bell into the plenum; the cavity stays ~3 kPa above the bearing chambers
    (= buffer air of the labyrinths, no oil mist into the winding); blower speed is the rotor-temperature actuator
    (compressor bleed rejected: 212 C; compressor-eye suction rejected: sub-atmospheric cavity would pull oil mist into the
    winding and the flow could not be controlled or kept at standstill)
  * bearings: oil jets (main lube system, 55 C supply) - modelled as boundary
Network (5 axial slices over the stack + front / rear end regions): per slice glycol, jacket wall, yoke, teeth, slot copper
top / bottom layer, gap air, sleeve, magnets, shaft (+ Cu screen); per end: end winding, end-space air, end bell, shaft end,
bearing; housing.  Copper loss temperature-dependent, air / glycol advection upwind.  Loop model: jacket -> return line ->
3-way valve -> dry cooler (eps-NTU, UA ~ fan^0.6) / bypass -> supply line; PI controllers (split range valve -> fan).
Run:  python3 sim/variant_e/eg_thermal.py   ->  sim/variant_e/eg_thermal.json
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'cad', 'variant_e'))
import eg_layout as EL                       # noqa: E402

EM, WIND = EL.EM, EL.WIND
EMJ = json.load(open(os.path.join(HERE, 'eg_em.json')))
w = 2 * math.pi * EL.F_EL
NS = 5                                        # axial slices of the active part
L = EM['stack'] / 1e3; DX = L / NS
RB, R2, RO = EM['bore'] / 2e3, (EM['bore'] / 2 + EM['slot_depth']) / 1e3, EM['stator_OD'] / 2e3
RS, RM, RC = EM['rotor_OD'] / 2e3, EM['magnet_OD'] / 2e3, EM['magnet_ID'] / 2e3
L_END = EMJ['winding']['end_winding']['end_length_per_turn_mm'] / 1e3

# ------------------------------------------------------------------ fluids
GLY = dict(name='MEG 35 % vol (inhibited, e.g. Clariant Antifrogen N / BASF Glysantin G48)', rho=1045.0, cp=3600.0, k=0.45, mu=1.25e-3, Pr=10.0)
OIL = dict(T_in=55.0, flow_L_min_per_bearing=2.5, rho=850.0, cp=2000.0)


def air(T):
    Tk = T + 273.15
    mu = 1.716e-5 * (Tk / 273.15) ** 1.5 * (273.15 + 110.4) / (Tk + 110.4)
    return dict(rho=1.03e5 / (287.05 * Tk), mu=mu, k=0.0241 * (Tk / 273.15) ** 0.81, cp=1007.0, Pr=0.71)


# ------------------------------------------------------------------ jacket channel design
JACKET = dict(material='EN AW-6082-T6', ID=EM['stator_OD'], wall=6.0, groove_w=18.0, groove_d=8.0, land=5.0, starts=2,
              length=EM['stack'] + 30.0, flow_L_min=30.0)


def jacket_design(j=JACKET, T=55.0):
    r_gb = j['ID'] / 2e3 + j['wall'] / 1e3                       # groove bottom radius
    p_start = j['starts'] * (j['groove_w'] + j['land']) / 1e3     # lead of one start
    turns = j['length'] / 1e3 / p_start
    Lch = turns * math.pi * 2 * (r_gb + j['groove_d'] / 2e3)
    A = j['groove_w'] * j['groove_d'] * 1e-6
    Dh = 2 * j['groove_w'] * j['groove_d'] / (j['groove_w'] + j['groove_d']) / 1e3
    Q = j['flow_L_min'] / 60e3 / j['starts']
    v = Q / A
    Re = GLY['rho'] * v * Dh / GLY['mu']
    if Re > 4000:
        f = (0.79 * math.log(Re) - 1.64) ** -2
        Nu = (f / 8) * (Re - 1000) * GLY['Pr'] / (1 + 12.7 * math.sqrt(f / 8) * (GLY['Pr'] ** (2 / 3) - 1))
    else:                                   # laminar / transitional (pump failure cases): fully developed rectangular duct
        f = 64.0 / max(Re, 1.0)
        Nu = 4.4
    dean = 1 + 3.6 * (1 - Dh / (2 * r_gb)) * (Dh / (2 * r_gb)) ** 0.8
    h = Nu * GLY['k'] / Dh * dean
    dp_ch = f * 1.15 * Lch / Dh * 0.5 * GLY['rho'] * v ** 2         # +15 % curvature friction
    dp_ports = 2 * 1.5 * 0.5 * GLY['rho'] * (Q * j['starts'] / (math.pi / 4 * 0.025 ** 2)) ** 2   # 2 x G1 ports (K 1.5 each) + manifolds
    # fin efficiency of the lands (Al, 5 mm wide, 8 mm high, both sides wetted)
    m_f = math.sqrt(2 * h / (170.0 * j['land'] / 1e3))
    eta_f = math.tanh(m_f * j['groove_d'] / 1e3) / (m_f * j['groove_d'] / 1e3)
    frac = (j['groove_w'] + 2 * j['groove_d'] * eta_f) / (j['groove_w'] + j['land'])
    return dict(r_groove_bottom_mm=round(r_gb * 1e3, 1), OD_mm=round(2 * r_gb * 1e3 + 2 * j['groove_d'], 1), turns_per_start=round(turns, 2),
                channel_length_per_start_m=round(Lch, 2), v_m_s=round(v, 2), Re=round(Re), Dh_mm=round(Dh * 1e3, 2), f_darcy=round(f, 4),
                dean_factor=round(dean, 3), h_W_m2K=round(h), fin_eff=round(eta_f, 3), area_factor=round(frac, 3),
                dp_channel_kPa=round(dp_ch / 1e3, 1), dp_ports_kPa=round(dp_ports / 1e3, 1), dp_total_kPa=round((dp_ch + dp_ports) / 1e3, 1),
                flow_L_min=j['flow_L_min'], C_W_K=round(j['flow_L_min'] / 60e3 * GLY['rho'] * GLY['cp'], 1))


# ------------------------------------------------------------------ air path (blower -> F9 -> front end bell -> gap -> rear end bell -> plenum)
AIRPATH = dict(m_design=0.040, blower_heating_K=4.0)


def air_path(m, T=55.0):
    a = air(T)
    g = EM['gap'] / 1e3
    A_gap = math.pi * ((RS + g) ** 2 - RS ** 2)
    v = m / (a['rho'] * A_gap)
    Dh = 2 * g
    Re_a = a['rho'] * v * Dh / a['mu']
    Re_t = a['rho'] * w * RS * g / a['mu']
    f0 = 0.316 * Re_a ** -0.25 if Re_a > 2300 else 64 / max(Re_a, 1)
    f = f0 * (1 + (0.5 * Re_t / max(Re_a, 1)) ** 2) ** 0.19       # rotation raises the axial friction (Yamada-type)
    q = 0.5 * a['rho'] * v ** 2
    Lg = (EM['magnet_L'] + 24) / 1e3
    dp_gap = f * Lg / Dh * q + 1.5 * q                             # + entry 0.5 + exit 1.0
    A_ports = 12 * math.pi / 4 * 0.022 ** 2                       # 12 x d22 holes per end bell (in / out)
    qp = 0.5 * a['rho'] * (m / (a['rho'] * A_ports)) ** 2
    dp_bells = 2 * 2.5 * qp
    dp_filter = 120.0 * (m / AIRPATH['m_design']) ** 1.5           # F9 cartridge mid-life (clean 80, change 200 Pa)
    dp_duct = 150.0 * (m / AIRPATH['m_design']) ** 2               # DN80 hose 1.5 m + 2 bends + diffuser
    dp = dp_gap + dp_bells + dp_filter + dp_duct
    Q = m / air(30.0)['rho']
    # gap heat transfer (Dittus-Boelter on the effective velocity sqrt(v_ax^2 + (0.5 w R)^2), x1.2 Taylor-vortex enhancement)
    v_eff = math.hypot(v, 0.5 * w * RS)
    Re_e = a['rho'] * v_eff * Dh / a['mu']
    h_gap = 1.2 * 0.023 * Re_e ** 0.8 * a['Pr'] ** 0.4 * a['k'] / Dh
    return dict(m_kg_s=m, Q_m3_h=round(Q * 3600, 1), v_gap_m_s=round(v, 1), Re_axial=round(Re_a), Re_theta=round(Re_t), f=round(f, 4),
                dp_Pa=dict(gap=round(dp_gap), end_bells=round(dp_bells), filter_F9=round(dp_filter), duct=round(dp_duct), total=round(dp)),
                h_gap_W_m2K=round(h_gap), P_air_W=round(Q * dp), P_blower_el_W=round(Q * dp / 0.42))


# ------------------------------------------------------------------ material / interface data
K = dict(lam_inplane=26.0, cu=390.0, cuzr=320.0, steel=42.0, smco=10.0, cfrp_tr=0.70, al=170.0, apa=0.20, serving=0.20, litz_eq=1.5, wedge=0.30,
         h_contact_stator_jacket=3000.0, h_bond_magnet=6000.0, h_contact_sleeve=5000.0)
CP = dict(fe=460.0, cu=385.0, al=900.0, steel=460.0, smco=370.0, cfrp=900.0, ins=1200.0)


class Net:
    def __init__(self):
        self.names = []; self.C = []; self.G = {}; self.adv = []; self.Q = {}

    def node(self, n, C):
        self.names.append(n); self.C.append(C)
        return len(self.names) - 1

    def g(self, a, b, G):
        k = (min(a, b), max(a, b))
        self.G[k] = self.G.get(k, 0.0) + G

    def matrices(self, mcp):
        """mcp: dict adv-group -> m cp (W/K); adv: (group, upstream, downstream)"""
        n = len(self.names)
        A = np.zeros((n, n))
        for (a, b), G in self.G.items():
            A[a, a] += G; A[b, b] += G; A[a, b] -= G; A[b, a] -= G
        for grp, up, dn in self.adv:
            c = mcp[grp]
            A[dn, dn] += c
            if up is not None:
                A[dn, up] -= c
        return A


def build(m_air, gly_flow_L_min=None, T_air_ref=60.0):
    jd = jacket_design(dict(JACKET, flow_L_min=gly_flow_L_min or JACKET['flow_L_min']))
    ap = air_path(m_air, T_air_ref)
    net = Net(); N = {}
    # masses per slice
    m_yoke = EMJ['geometry']['masses']['iron_yoke_kg'] / NS; m_teeth = EMJ['geometry']['masses']['iron_teeth_kg'] / NS
    m_cu = EMJ['geometry']['masses']['copper_slot_kg'] / NS
    m_mag = EMJ['geometry']['masses']['magnets_kg'] / NS
    m_shaft = 7850 * math.pi * (RC - EM['shield_t'] / 1e3) ** 2 * DX + 8890 * math.pi * (RC ** 2 - (RC - EM['shield_t'] / 1e3) ** 2) * DX
    m_jk = 2700 * math.pi * ((RO + JACKET['wall'] / 1e3) ** 2 - RO ** 2) * DX * 1.4
    for i in range(NS):
        N['gly%d' % i] = net.node('glycol slice %d' % i, GLY['rho'] * GLY['cp'] * math.pi * 2 * RO * 0.008 * 0.018 * 2 * DX / 0.046 * 1.0)
        N['jk%d' % i] = net.node('jacket wall %d' % i, m_jk * CP['al'])
        N['yk%d' % i] = net.node('yoke %d' % i, m_yoke * CP['fe'])
        N['th%d' % i] = net.node('teeth %d' % i, m_teeth * CP['fe'])
        N['cb%d' % i] = net.node('slot Cu bottom layer %d' % i, 0.5 * m_cu * CP['cu'] + 0.3 * CP['ins'])
        N['ct%d' % i] = net.node('slot Cu top layer %d' % i, 0.5 * m_cu * CP['cu'] + 0.3 * CP['ins'])
        N['ag%d' % i] = net.node('gap air %d' % i, 1.1 * 1007 * math.pi * 2 * RS * 0.003 * DX)
        N['sl%d' % i] = net.node('sleeve %d' % i, EMJ['geometry']['masses']['sleeve_kg'] / NS * CP['cfrp'])
        N['mg%d' % i] = net.node('magnets %d' % i, m_mag * CP['smco'])
        N['sh%d' % i] = net.node('shaft + Cu screen %d' % i, m_shaft * CP['steel'])
    for e in ('f', 'r'):
        N['ew' + e] = net.node('end winding ' + e, EMJ['geometry']['masses']['copper_end_kg'] / 2 * CP['cu'] + 2.0 * CP['ins'])
        N['ae' + e] = net.node('end-space air ' + e, 2.0)
        N['eb' + e] = net.node('end bell ' + e, 14.0 * CP['al'])
        N['se' + e] = net.node('shaft end ' + e, 2.5 * CP['steel'])
        N['br' + e] = net.node('bearing ' + e, 0.25 * CP['steel'])
    N['hs'] = net.node('housing', 26.0 * CP['al'])
    N['amb'] = None
    # ---------------- conductances per slice
    Ast = 2 * math.pi * RO * DX
    hc = K['h_contact_stator_jacket']
    for i in range(NS):
        g_ = lambda a, b, G: net.g(N[a % i] if '%' in a else N[a], N[b % i] if '%' in b else N[b], G)
        # stator OD -> jacket wall -> glycol
        G_yo = 2 * math.pi * K['lam_inplane'] * DX / math.log(RO / (0.5 * (R2 + RO)))
        G_ojk = 1.0 / (1.0 / G_yo + 1.0 / (hc * Ast) + JACKET['wall'] / 1e3 / 2 / (K['al'] * Ast))
        g_('yk%d', 'jk%d', G_ojk)
        A_gb = 2 * math.pi * (RO + JACKET['wall'] / 1e3) * DX * jd['area_factor']
        g_('jk%d', 'gly%d', 1.0 / (1.0 / (jd['h_W_m2K'] * A_gb) + JACKET['wall'] / 1e3 / 2 / (K['al'] * Ast)))
        # glycol -> housing (outer channel wall)
        A_hs = 2 * math.pi * (RO + (JACKET['wall'] + JACKET['groove_d']) / 1e3) * DX * JACKET['groove_w'] / (JACKET['groove_w'] + JACKET['land'])
        g_('gly%d', 'hs', jd['h_W_m2K'] * A_hs)
        # teeth -> yoke (radial along the teeth + inner half of the yoke)
        ht = R2 - RB
        wt = 0.5 * (EMJ['geometry']['slot']['tooth_w_bore_mm'] + EMJ['geometry']['slot']['tooth_w_root_mm']) / 1e3
        G_t = K['lam_inplane'] * EM['slots'] * wt * DX / (ht / 2) * EM['stack_factor']
        G_yi = 2 * math.pi * K['lam_inplane'] * DX / math.log((0.5 * (R2 + RO)) / R2)
        g_('th%d', 'yk%d', 1.0 / (1 / G_t + 1 / G_yi))
        # slot copper: liner + serving + internal (litz with VPI resin)
        ws = EM['slot_w'] / 1e3; hl = (EM['slot_depth'] - EM['wedge_h']) / 2e3
        R_wall = WIND['liner'] / 1e3 / K['apa'] + 0.15e-3 / K['serving']
        A_side = EM['slots'] * 2 * hl * DX; A_bot = EM['slots'] * ws * DX
        R_int_side = (ws / 4) / K['litz_eq']; R_int_rad = (hl / 2) / K['litz_eq']
        g_('cb%d', 'th%d', A_side / (R_wall + R_int_side))
        g_('ct%d', 'th%d', A_side / (R_wall + R_int_side))
        g_('cb%d', 'yk%d', A_bot / (R_wall + R_int_rad + 0.5 * (R2 - RB) * 0 + 1.0 / 2e4))
        g_('ct%d', 'cb%d', A_bot / (WIND['separator'] / 1e3 / K['apa'] + 2 * 0.15e-3 / K['serving'] + 2 * R_int_rad))
        # gap side: wedge, teeth tips
        hg = ap['h_gap_W_m2K']
        A_w = EM['slots'] * ws * DX
        g_('ct%d', 'ag%d', 1.0 / (R_int_rad / A_w + EM['wedge_h'] / 1e3 / (K['wedge'] * A_w) + 1 / (hg * A_w)))
        A_tt = EM['slots'] * EMJ['geometry']['slot']['tooth_w_bore_mm'] / 1e3 * DX
        g_('th%d', 'ag%d', 1.0 / (ht / 2 / (K['lam_inplane'] * A_tt * EM['stack_factor']) + 1 / (hg * A_tt)))
        # rotor
        A_rs = 2 * math.pi * RS * DX
        g_('ag%d', 'sl%d', 1.0 / (1 / (hg * A_rs) + math.log(RS / (0.5 * (RS + RM))) / (2 * math.pi * K['cfrp_tr'] * DX)))
        g_('sl%d', 'mg%d', 1.0 / (math.log((0.5 * (RS + RM)) / RM) / (2 * math.pi * K['cfrp_tr'] * DX) + 1 / (K['h_contact_sleeve'] * 2 * math.pi * RM * DX)
                                  + math.log(RM / (0.5 * (RM + RC))) / (2 * math.pi * K['smco'] * DX)))
        g_('mg%d', 'sh%d', 1.0 / (math.log((0.5 * (RM + RC)) / RC) / (2 * math.pi * K['smco'] * DX) + 1 / (K['h_bond_magnet'] * 2 * math.pi * RC * DX)
                                  + 1 / (4 * math.pi * K['steel'] * DX)))
        # axial couplings between slices
        if i < NS - 1:
            kA_sh = K['steel'] * math.pi * (RC - EM['shield_t'] / 1e3) ** 2 + K['cuzr'] * math.pi * (RC ** 2 - (RC - EM['shield_t'] / 1e3) ** 2)
            net.g(N['sh%d' % i], N['sh%d' % (i + 1)], kA_sh / DX)
            A_cu = EM['slots'] * 2 * WIND['Cu_mm2'] * 1e-6
            net.g(N['cb%d' % i], N['cb%d' % (i + 1)], K['cu'] * A_cu / DX)
            net.g(N['ct%d' % i], N['ct%d' % (i + 1)], K['cu'] * A_cu / DX)
            net.g(N['yk%d' % i], N['yk%d' % (i + 1)], 1.5 * math.pi * (RO ** 2 - R2 ** 2) / DX)   # axial k of the stack ~1.5 W/mK
    # ---------------- end regions
    a60 = air(60.0)
    v_ew = 8.0 * (m_air / AIRPATH['m_design']) ** 0.8          # directed jets / guide ring onto the end winding (design 8 m/s)
    h_ew = 41.4 + 6.22 * v_ew
    A_ew = 0.12
    A_cu_all = EM['slots'] * 4 * WIND['Cu_mm2'] * 1e-6
    G_ew_ax = K['cu'] * A_cu_all / (L_END / 2 + DX / 2)
    for e, i_end in (('f', 0), ('r', NS - 1)):
        net.g(N['ew' + e], N['cb%d' % i_end], 0.5 * G_ew_ax); net.g(N['ew' + e], N['ct%d' % i_end], 0.5 * G_ew_ax)
        net.g(N['ew' + e], N['ae' + e], h_ew * A_ew)
        net.g(N['ew' + e], N['jk%d' % i_end], 0.6)                                   # resin / support ring to the jacket end
        net.g(N['ae' + e], N['eb' + e], 30.0 * 0.09)
        net.g(N['eb' + e], N['hs'], 25.0)                                            # bolted spigot flange (Al / Al)
        net.g(N['eb' + e], N['amb'] if False else N['eb' + e], 0.0)
        # rotor end face (end ring + sleeve end): rotating disk h ~ 400 W/m2K
        A_face = math.pi * (RS ** 2 - (RC - EM['shield_t'] / 1e3) ** 2)
        net.g(N['mg%d' % i_end], N['ae' + e], 1.0 / (1 / (400.0 * A_face) + 0.006 / (16.0 * A_face)))
        # shaft body -> shaft end (d60 / d50 steps, ~60 mm) -> bearing inner ring -> bearing -> oil; bearing -> hub (SFD film)
        net.g(N['sh%d' % i_end], N['se' + e], K['steel'] * math.pi * 0.028 ** 2 / 0.060)
        net.g(N['se' + e], N['br' + e], 25.0)
        net.g(N['br' + e], N['eb' + e], 8.0)
        net.g(N['se' + e], N['ae' + e], 60.0 * 2 * math.pi * 0.03 * 0.05)
    # housing outside: forced convection by the intake air around the pod (~3 m/s): h ~ 15 W/m2K over 0.5 m2 (handled as a
    # boundary term in solve()); end bells outside: 15 W/m2K x 0.08 m2
    # ---------------- advection
    net.adv.append(('air', None, N['aef']))
    net.adv.append(('air', N['aef'], N['ag0']))
    for i in range(NS - 1):
        net.adv.append(('air', N['ag%d' % i], N['ag%d' % (i + 1)]))
    net.adv.append(('air', N['ag%d' % (NS - 1)], N['aer']))
    net.adv.append(('gly', None, N['gly%d' % (NS - 1)]))            # glycol enters at the rear (air-outlet end) -> counter-flow
    for i in range(NS - 1, 0, -1):
        net.adv.append(('gly', N['gly%d' % i], N['gly%d' % (i - 1)]))
    return net, N, dict(jacket=jd, air=ap, h_ew=round(h_ew, 1), G_ew_axial=round(G_ew_ax, 2))


def losses_at(op_index=-1, Tcu=None, fac_scale=1.0):
    """heat sources per op point from eg_em.json; copper loss re-scaled with the copper temperature"""
    l = EMJ['losses'][op_index]['losses_W']
    return dict(cu=l['copper_dc_W'] + l['litz_proximity_W'], fe=l['iron_W'], mag=l['magnets_W'], screen=l['cu_screen_and_shaft_W'] + l['sleeve_end_rings_W'],
                wind_gap=EMJ['windage']['gap_W'], wind_face=EMJ['windage']['end_faces_W'], wind_step=EMJ['windage']['steps_labyrinths_W'],
                brg_f=EMJ['bearings']['front_W'], brg_r=EMJ['bearings']['rear_W'])


def sources(N, Lw, T, T_cu_ref=120.0, load_scale=None):
    """vector of heat input (W) for temperatures T (array)"""
    n = len(T)
    q = np.zeros(n)
    tea = EMJ['load_335kW']['iron_loss']
    ft = tea['teeth_W'] / tea['total_W']
    frac_slot = L / (L + L_END)
    rc = lambda Tx: (1 + 0.00393 * (Tx - 20.0)) / (1 + 0.00393 * (T_cu_ref - 20.0))
    for i in range(NS):
        for lay in ('cb', 'ct'):
            k = N['%s%d' % (lay, i)]
            q[k] += 0.5 * Lw['cu'] * frac_slot / NS * rc(T[k])
        q[N['th%d' % i]] += Lw['fe'] * ft / NS
        q[N['yk%d' % i]] += Lw['fe'] * (1 - ft) / NS
        q[N['ag%d' % i]] += Lw['wind_gap'] / NS
        q[N['mg%d' % i]] += Lw['mag'] / NS
        q[N['sh%d' % i]] += Lw['screen'] / NS
    for e in ('f', 'r'):
        k = N['ew' + e]
        q[k] += 0.5 * Lw['cu'] * (1 - frac_slot) * rc(T[k])
        q[N['ae' + e]] += 0.5 * Lw['wind_face']
        q[N['se' + e]] += 0.5 * Lw['wind_step']
    q[N['brf']] += Lw['brg_f']; q[N['brr']] += Lw['brg_r']
    return q


def solve_steady(T_amb, T_gly_in, m_air, Lw, gly_flow=30.0, iters=12):
    net, N, info = build(m_air, gly_flow)
    a = air(T_amb + 25)
    mcp = dict(air=m_air * a['cp'], gly=gly_flow / 60e3 * GLY['rho'] * GLY['cp'])
    A = net.matrices(mcp)
    n = len(net.names)
    b0 = np.zeros(n)
    T_air_in = T_amb + AIRPATH['blower_heating_K']
    b0[N['aef']] += mcp['air'] * T_air_in
    b0[N['gly%d' % (NS - 1)]] += mcp['gly'] * T_gly_in
    # boundaries: housing + end bells to the plenum air; bearings to oil (jet + drain)
    Ab = A.copy()
    for k, G in ((N['hs'], 15.0 * 0.5), (N['ebf'], 15.0 * 0.08), (N['ebr'], 15.0 * 0.08)):
        Ab[k, k] += G; b0[k] += G * (T_amb + 1.0)
    C_oil = OIL['flow_L_min_per_bearing'] / 60e3 * OIL['rho'] * OIL['cp']
    G_oil = 1.0 / (1.0 / 150.0 + 0.5 / C_oil)                 # jet film + half the oil temperature rise
    for e in ('f', 'r'):
        k = N['br' + e]; Ab[k, k] += G_oil; b0[k] += G_oil * OIL['T_in']
        k = N['eb' + e]; Ab[k, k] += 6.0; b0[k] += 6.0 * OIL['T_in']        # drain oil wetting the hub
    T = np.full(n, T_amb + 40.0)
    for _ in range(iters):
        q = sources(N, Lw, T)
        T = np.linalg.solve(Ab, b0 + q)
    q = sources(N, Lw, T)
    heat = dict(to_glycol_W=round(float(mcp['gly'] * (T[N['gly0']] - T_gly_in))), to_air_W=round(float(mcp['air'] * (T[N['aer']] - T_air_in))),
                to_oil_W=round(float(sum(G_oil * (T[N['br' + e]] - OIL['T_in']) + 6.0 * (T[N['eb' + e]] - OIL['T_in']) for e in ('f', 'r')))),
                to_plenum_W=round(float(15 * 0.5 * (T[N['hs']] - T_amb - 1) + sum(15 * 0.08 * (T[N['eb' + e]] - T_amb - 1) for e in ('f', 'r')))),
                sources_W=round(float(q.sum())))
    return T, N, net, info, heat


def hot_spots(T, N):
    sl = [T[N['cb%d' % i]] for i in range(NS)] + [T[N['ct%d' % i]] for i in range(NS)]
    # hot spot inside the copper layer = layer node + internal rise (half-layer conduction, ~ +3 K at 335 kW, from the R_int terms)
    return dict(winding_slot_max=round(max(sl), 1), winding_slot_mean=round(float(np.mean(sl)), 1), end_winding_front=round(float(T[N['ewf']]), 1),
                end_winding_rear=round(float(T[N['ewr']]), 1), winding_hot_spot_est=round(max(max(sl), T[N['ewf']], T[N['ewr']]) + 5.0, 1),
                magnet_max=round(max(T[N['mg%d' % i]] for i in range(NS)), 1), magnet_mean=round(float(np.mean([T[N['mg%d' % i]] for i in range(NS)])), 1),
                sleeve_max=round(max(T[N['sl%d' % i]] for i in range(NS)), 1), shaft_max=round(max(T[N['sh%d' % i]] for i in range(NS)), 1),
                yoke_max=round(max(T[N['yk%d' % i]] for i in range(NS)), 1), teeth_max=round(max(T[N['th%d' % i]] for i in range(NS)), 1),
                gap_air_out=round(float(T[N['aer']]), 1), bearing_front=round(float(T[N['brf']]), 1), bearing_rear=round(float(T[N['brr']]), 1),
                glycol_out=round(float(T[N['gly0']]), 1), housing=round(float(T[N['hs']]), 1))


# ------------------------------------------------------------------ dry cooler + loop
COOLER = dict(UA_max=450.0, C_air_max=2000.0 / 3600 * 1.10 * 1007, fan_P_max=150.0, fan_min=0.15, recirc_K=2.0,
              spec='dry cooler, 1 x EC axial fan d450-500 (2000 m3/h, 150 W), Cu tube / Al fin coil 2 rows ~0.6 m2 face, UA >= 450 W/K at full fan, '
                   'MEG 35 %, dp <= 30 kPa at 30 L/min; candidates Guentner (DE) GDF / GFH compact, LU-VE (IT) EHL, Thermokey (IT), Kelvion (DE)')


def cooler_out(T_in, C_gly, T_air, fan):
    UA = COOLER['UA_max'] * max(fan, 1e-3) ** 0.6
    Ca = COOLER['C_air_max'] * max(fan, 0.05)     # natural draft ~5 % with the fan off
    Cmin, Cmax = min(Ca, C_gly), max(Ca, C_gly)
    NTU = UA / Cmin; Cr = Cmin / Cmax
    eps = 1 - math.exp((math.exp(-Cr * NTU ** 0.78) - 1) * NTU ** 0.22 / Cr)       # cross-flow, both unmixed
    Qc = eps * Cmin * (T_in - T_air)
    return T_in - Qc / C_gly, Qc


class PI:
    def __init__(self, kp, ti, lo, hi, u0=0.0):
        self.kp, self.ti, self.lo, self.hi, self.i = kp, ti, lo, hi, u0

    def step(self, err, dt):
        u = self.kp * err + self.i
        if self.lo < u < self.hi:
            self.i += self.kp * err * dt / self.ti
        return min(max(u, self.lo), self.hi)


CTRL = dict(T_supply_SP=55.0, T_rotor_SP=85.0, blower_min=0.35, blower_max=1.0, m_air_max=0.050,
            pi_supply=dict(kp=0.25, ti=60.0), pi_rotor=dict(kp=0.04, ti=300.0),
            winding_outer_loop=dict(target_C=82.0, SP_range=(55.0, 68.0), kp=0.2, ti=1200.0))


def transient(scenario, dt=2.0, t_end=4 * 3600.0, outer_loop=False, record_every=60.0):
    """scenario(t) -> dict(T_amb, load (0..1 of 335 kW losses, 'speed'), blower_ok, pump_ok)"""
    Lw0 = losses_at(-1)
    m_air_max = CTRL['m_air_max']
    net, N, info = build(m_air_max)
    n = len(net.names)
    C = np.array(net.C)
    s0 = scenario(0.0)
    T = np.full(n, s0['T_amb'])
    V_loop = dict(supply=6.0e-3, ret=6.0e-3, cooler=5.0e-3)
    T_sup, T_ret, T_coo = s0['T_amb'], s0['T_amb'], s0['T_amb']
    pi_s = PI(CTRL['pi_supply']['kp'], CTRL['pi_supply']['ti'], 0.0, 2.0)
    pi_r = PI(CTRL['pi_rotor']['kp'], CTRL['pi_rotor']['ti'], CTRL['blower_min'], CTRL['blower_max'], CTRL['blower_min'])
    pi_w = PI(CTRL['winding_outer_loop']['kp'], CTRL['winding_outer_loop']['ti'], CTRL['T_supply_SP'] - 5.0, CTRL['T_supply_SP'] + 5.0, u0=CTRL['T_supply_SP'])
    SP = CTRL['T_supply_SP']
    blow = CTRL['blower_min']
    rec = []
    C_oil = OIL['flow_L_min_per_bearing'] / 60e3 * OIL['rho'] * OIL['cp']
    G_oil = 1.0 / (1.0 / 150.0 + 0.5 / C_oil)
    t = 0.0; nxt = 0.0
    u = 0.0
    while t <= t_end + 1e-6:
        sc = scenario(t)
        ld = sc['load']; spd = sc.get('speed', 1.0 if ld > 0 else 0.0)
        Lw = {k: v * (ld if k in ('cu',) else 1.0) for k, v in Lw0.items()}
        Lw['cu'] = Lw0['cu'] * ld ** 2 if ld > 0 else 0.0
        for k in ('fe', 'wind_gap', 'wind_face', 'wind_step', 'brg_f', 'brg_r'):
            Lw[k] = Lw0[k] * (spd ** (3 if 'wind' in k else 1.7 if k == 'fe' else 1.2))
        for k in ('mag', 'screen'):
            Lw[k] = Lw0[k] * (ld ** 2) * spd
        gly = 30.0 if sc.get('pump_ok', True) else 0.05
        m_air = (m_air_max * blow) if sc.get('blower_ok', True) else 0.004 * spd
        net.adv = net.adv  # unchanged topology
        a = air(sc['T_amb'] + 25)
        mcp = dict(air=m_air * a['cp'], gly=gly / 60e3 * GLY['rho'] * GLY['cp'])
        A = net.matrices(mcp)
        b0 = np.zeros(n)
        b0[N['aef']] += mcp['air'] * (sc['T_amb'] + AIRPATH['blower_heating_K'] * blow ** 2)
        b0[N['gly%d' % (NS - 1)]] += mcp['gly'] * T_sup
        for k, G in ((N['hs'], 7.5), (N['ebf'], 1.2), (N['ebr'], 1.2)):
            A[k, k] += G; b0[k] += G * (sc['T_amb'] + 1)
        Toil = OIL['T_in'] if spd > 0.05 else sc['T_amb'] + 10
        for e in ('f', 'r'):
            k = N['br' + e]; A[k, k] += G_oil * (1 if spd > 0.05 else 0.05); b0[k] += G_oil * (1 if spd > 0.05 else 0.05) * Toil
            k = N['eb' + e]; A[k, k] += 6.0 * (1 if spd > 0.05 else 0.1); b0[k] += 6.0 * (1 if spd > 0.05 else 0.1) * Toil
        q = sources(N, Lw, T)
        M = np.diag(C / dt) + A
        T = np.linalg.solve(M, C / dt * T + b0 + q)
        # loop: jacket outlet -> return line -> valve -> cooler / bypass -> supply line
        Cg = mcp['gly']
        T_out = T[N['gly0']]
        T_ret += dt * Cg / (V_loop['ret'] * GLY['rho'] * GLY['cp']) * (T_out - T_ret)
        x = min(max(u, 0.0), 1.0); fan = COOLER['fan_min'] + (1 - COOLER['fan_min']) * min(max(u - 1.0, 0.0), 1.0) if u > 1.0 else (COOLER['fan_min'] if x > 0.02 else 0.0)
        T_air_c = sc['T_amb'] + COOLER['recirc_K'] * fan
        T_c_target, Qc = cooler_out(T_coo, max(Cg * x, 1e-3), T_air_c, fan)
        T_coo += dt * max(Cg * x, 5.0) / (V_loop['cooler'] * GLY['rho'] * GLY['cp']) * (T_ret - T_coo) - dt * Qc / (V_loop['cooler'] * GLY['rho'] * GLY['cp'])
        T_mix = x * T_coo + (1 - x) * T_ret
        T_sup += dt * Cg / (V_loop['supply'] * GLY['rho'] * GLY['cp']) * (T_mix - T_sup)
        # controllers
        hs = hot_spots(T, N)
        if outer_loop:      # feed-forward from the electrical load (copper loss ~ P^2) + slow PI trim on the max slot PT100
            lo_, hi_ = CTRL['winding_outer_loop']['SP_range']
            ff = lo_ + (hi_ - lo_) * (1 - min(ld, 1.0) ** 2) if ld > 0.05 else CTRL['T_supply_SP']
            trim = pi_w.step(CTRL['winding_outer_loop']['target_C'] - hs['winding_slot_max'], dt) - CTRL['T_supply_SP'] if ld > 0.05 else 0.0
            SP = min(max(ff + trim, lo_), hi_)
        u = pi_s.step(T_sup - SP, dt)
        T_rotor_meas = max(T[N['mg%d' % (NS - 1)]], T[N['sl%d' % (NS - 1)]])       # IR pyrometer on the rear sleeve end + EMF observer
        if sc.get('blower_ok', True):
            blow = pi_r.step(T_rotor_meas - CTRL['T_rotor_SP'], dt) if spd > 0.2 else CTRL['blower_min']
        if t >= nxt - 1e-9:
            rec.append(dict(t_min=round(t / 60, 1), T_amb=sc['T_amb'], load=round(ld, 3), T_supply=round(T_sup, 2), SP=round(SP, 2), valve=round(x, 3), fan=round(fan, 3),
                            blower=round(blow, 3), Q_cooler_W=round(Qc), winding_slot=hs['winding_slot_max'], end_winding=max(hs['end_winding_front'], hs['end_winding_rear']),
                            magnet=hs['magnet_max'], sleeve=hs['sleeve_max'], bearing=max(hs['bearing_front'], hs['bearing_rear']), air_out=hs['gap_air_out'],
                            glycol_out=hs['glycol_out']))
            nxt += record_every
        t += dt
    return rec


def summarize(rec, t_from_min):
    r = [x for x in rec if x['t_min'] >= t_from_min]
    out = {}
    for k in ('winding_slot', 'end_winding', 'magnet', 'T_supply', 'bearing', 'air_out'):
        v = [x[k] for x in r]
        out[k] = dict(min=round(min(v), 1), max=round(max(v), 1), spread=round(max(v) - min(v), 1))
    return out


def main():
    jd = jacket_design()
    out = dict(title='GR180 version E generator cooling system + thermal network (steady / transient / control)', date='2026-10-24',
               script='sim/variant_e/eg_thermal.py', inputs=dict(losses='sim/variant_e/eg_em.json', slices=NS, materials_k=K, glycol=GLY, oil=OIL),
               jacket=dict(design=JACKET, result=jd))
    # air-flow sizing: flow vs. rotor temperature at 45 C ambient, full load
    sweep = []
    Lw = losses_at(-1)
    for m in (0.015, 0.025, 0.035, 0.045, 0.055):
        T, N, net, info, heat = solve_steady(45.0, CTRL['T_supply_SP'], m, Lw)
        hs = hot_spots(T, N)
        sweep.append(dict(m_air=m, Q_m3_h=info['air']['Q_m3_h'], dp_Pa=info['air']['dp_Pa']['total'], P_blower_W=info['air']['P_blower_el_W'],
                          magnet_max=hs['magnet_max'], winding=hs['winding_hot_spot_est'], air_out=hs['gap_air_out'], h_gap=info['air']['h_gap_W_m2K']))
    out['air_flow_sweep_45C_335kW'] = sweep
    out['air_path_design'] = air_path(CTRL['m_air_max'])
    # steady states
    st = {}
    for name, Ta, op, m in (('335 kW, 0 C ambient', 0.0, -1, None), ('335 kW, 15 C ambient', 15.0, -1, None),
                            ('335 kW, 30 C ambient', 30.0, -1, None), ('335 kW, 45 C ambient', 45.0, -1, None),
                            ('335 kW, 45 C ambient, blower 100 %', 45.0, -1, CTRL['m_air_max']),
                            ('306 kW (770 C), 30 C', 30.0, 1, None), ('270 kW (250 kW net), 30 C', 30.0, 0, None),
                            ('335 kW, 45 C, blower failed (leakage only)', 45.0, -1, 0.004), ('335 kW, 45 C, glycol pump stopped (0.05 L/min)', 45.0, -1, CTRL['m_air_max'])):
        Lw = losses_at(op)
        if m is None:            # blower speed that gives the rotor set-point (bisection)
            lo, hi = CTRL['blower_min'], 1.0
            for _ in range(25):
                mid = 0.5 * (lo + hi)
                T, N, net, info, heat = solve_steady(Ta, CTRL['T_supply_SP'], CTRL['m_air_max'] * mid, Lw)
                if max(T[N['mg%d' % (NS - 1)]], T[N['sl%d' % (NS - 1)]]) > CTRL['T_rotor_SP']:
                    lo = mid
                else:
                    hi = mid
            m = CTRL['m_air_max'] * hi
        gly = 0.05 if 'pump' in name else 30.0
        T, N, net, info, heat = solve_steady(Ta, CTRL['T_supply_SP'], m, Lw, gly_flow=gly)
        st[name] = dict(m_air=round(m, 4), blower_pct=round(100 * m / CTRL['m_air_max']), hot_spots=hot_spots(T, N), heat=heat, h_gap=info['air']['h_gap_W_m2K'],
                        nodes={net.names[k]: round(float(T[k]), 1) for k in range(len(T))} if name == '335 kW, 45 C ambient' else None)
    out['steady'] = st
    # radiator / dry cooler sizing at 45 C (+2 K recirculation), heat = glycol heat at 335 kW + 50 % margin
    Q_g = st['335 kW, 45 C ambient']['heat']['to_glycol_W']
    Cg = 30.0 / 60e3 * GLY['rho'] * GLY['cp']
    T_in = CTRL['T_supply_SP'] + 1.5 * Q_g / Cg
    lo, hi = 0.05, 1.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        To, Qc = cooler_out(T_in, Cg, 45.0 + COOLER['recirc_K'], mid)
        if To > CTRL['T_supply_SP']:
            lo = mid
        else:
            hi = mid
    fan45 = hi
    fan30 = None
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        To, Qc = cooler_out(CTRL['T_supply_SP'] + Q_g / Cg, Cg, 32.0, mid)
        if To > CTRL['T_supply_SP']:
            lo = mid
        else:
            hi = mid
    fan30 = hi
    out['dry_cooler'] = dict(COOLER, design_duty_W=round(1.5 * Q_g), heat_at_335kW_W=Q_g, glycol_in_C=round(T_in, 2), air_in_C=45 + COOLER['recirc_K'],
                             fan_speed_needed_45C_150pct=round(fan45, 3), fan_power_45C_W=round(COOLER['fan_P_max'] * fan45 ** 3),
                             fan_speed_30C_100pct=round(fan30, 3), fan_power_30C_W=round(COOLER['fan_P_max'] * fan30 ** 3),
                             approach_K=round(CTRL['T_supply_SP'] - 45 - COOLER['recirc_K'], 1),
                             margin='at 45 C ambient the cooler rejects 150 %% of the generator heat with the fan at %.0f %%' % (100 * fan45))
    out['pump'] = dict(flow_L_min=30.0, head_kPa=round(jd['dp_total_kPa'] + 30 + 20 + 15 + 10, 1), breakdown_kPa=dict(jacket=jd['dp_total_kPa'], dry_cooler=30, pipes_DN25_2x10m=20,
                       valve_3way_kvs6=15, strainer=10), P_el_W=round(30 / 60e3 * (jd['dp_total_kPa'] + 75) * 1e3 / 0.35),
                       spec='wet-rotor circulator with ECM + 0-10 V speed, e.g. Grundfos MAGNA3 25-120 (DK) / Wilo Stratos MAXO 25/0.5-12 (DE); flow switch + vortex flow meter (Huba Control 210 CH / SIKA VVX DE)')
    # transients
    def sc_start(Ta):
        def f(t):
            if t < 120:
                return dict(T_amb=Ta, load=0.0, speed=min(t / 120, 0.86))
            if t < 300:
                return dict(T_amb=Ta, load=(t - 120) / 180, speed=1.0)
            return dict(T_amb=Ta, load=1.0, speed=1.0)
        return f

    def sc_ambient(t):
        Ta = 30.0 + 15.0 * min(max((t - 3600) / 1800, 0.0), 1.0)
        return dict(T_amb=Ta, load=1.0, speed=1.0)

    def sc_load(t):
        ld = 1.0 if t < 2 * 3600 or t > 4 * 3600 else 0.45
        return dict(T_amb=30.0, load=ld, speed=1.0 if ld > 0.5 else 0.99)

    def sc_blower_fail(t):
        return dict(T_amb=45.0, load=1.0, speed=1.0, blower_ok=t < 2 * 3600)

    def sc_pump_fail(t):
        return dict(T_amb=45.0, load=1.0, speed=1.0, pump_ok=t < 2 * 3600)
    tr = {}
    tr['cold start 30 C -> 335 kW'] = transient(sc_start(30.0), t_end=4 * 3600)
    tr['cold start 45 C -> 335 kW'] = transient(sc_start(45.0), t_end=4 * 3600)
    tr['cold start 0 C -> 335 kW'] = transient(sc_start(0.0), t_end=4 * 3600)
    tr['ambient ramp 30 -> 45 C at 335 kW'] = transient(sc_ambient, t_end=5 * 3600)
    tr['load 335 -> 150 -> 335 kW, 30 C (no outer loop)'] = transient(sc_load, t_end=6 * 3600)
    tr['load 335 -> 150 -> 335 kW, 30 C (winding outer loop)'] = transient(sc_load, t_end=6 * 3600, outer_loop=True)
    tr['blower failure at 2 h, 45 C, 335 kW'] = transient(sc_blower_fail, t_end=3.5 * 3600, dt=2.0)
    tr['glycol pump failure at 2 h, 45 C, 335 kW'] = transient(sc_pump_fail, t_end=4.0 * 3600, dt=1.0, record_every=30.0)
    summ = {}
    summ['steady band, 3-4 h, start 0 / 30 / 45 C'] = {k: summarize(tr[k], 180) for k in ('cold start 0 C -> 335 kW', 'cold start 30 C -> 335 kW', 'cold start 45 C -> 335 kW')}
    summ['ambient ramp 30 -> 45 C (whole run after 1 h)'] = summarize(tr['ambient ramp 30 -> 45 C at 335 kW'], 60)
    summ['load cycling (after 1.5 h)'] = dict(no_outer=summarize(tr['load 335 -> 150 -> 335 kW, 30 C (no outer loop)'], 90),
                                              outer=summarize(tr['load 335 -> 150 -> 335 kW, 30 C (winding outer loop)'], 90))

    def first_cross(rec, key, lim, t0):
        for x in rec:
            if x['t_min'] >= t0 and x[key] >= lim:
                return round(x['t_min'] - t0, 1)
        return None
    def t90(rec, key, t0=5.0):
        r = [x for x in rec if x['t_min'] >= t0]
        y0, y1 = r[0][key], r[-1][key]
        for x in r:
            if abs(x[key] - y0) >= 0.9 * abs(y1 - y0):
                return round(x['t_min'], 1)
        return None
    summ['time_to_90pct_from_cold_start_30C_min'] = {k: t90(tr['cold start 30 C -> 335 kW'], k) for k in ('winding_slot', 'end_winding', 'magnet', 'bearing')}
    summ['blower failure'] = dict(magnet_alarm_130C_after_min=first_cross(tr['blower failure at 2 h, 45 C, 335 kW'], 'magnet', 130.0, 120),
                                  magnet_trip_150C_after_min=first_cross(tr['blower failure at 2 h, 45 C, 335 kW'], 'magnet', 150.0, 120),
                                  end_winding_alarm_140C_after_min=first_cross(tr['blower failure at 2 h, 45 C, 335 kW'], 'end_winding', 140.0, 120),
                                  magnet_end=tr['blower failure at 2 h, 45 C, 335 kW'][-1]['magnet'], end_winding_end=tr['blower failure at 2 h, 45 C, 335 kW'][-1]['end_winding'])
    summ['pump failure'] = dict(winding_alarm_140C_after_min=first_cross(tr['glycol pump failure at 2 h, 45 C, 335 kW'], 'winding_slot', 140.0, 120),
                                winding_trip_155C_after_min=first_cross(tr['glycol pump failure at 2 h, 45 C, 335 kW'], 'winding_slot', 155.0, 120),
                                winding_end=tr['glycol pump failure at 2 h, 45 C, 335 kW'][-1]['winding_slot'])
    out['transients'] = {k: v[::max(1, len(v) // 120)] for k, v in tr.items()}
    out['transient_summary'] = summ
    out['control'] = dict(CTRL, structure=[
        'L1 coolant supply temperature: PT100 TT-G03 after the 3-way valve -> PI (kp 0.25 /K, Ti 60 s) -> split range: 0-1 = 3-way mixing valve (bypass -> cooler), 1-2 = dry-cooler EC fan 15 -> 100 %; pump at constant 30 L/min (ECM, flow meter FT-G01)',
        'L2 rotor temperature: IR pyrometer TT-R01/02 on the CFRP sleeve ends + EMF observer (V_dc, I_dc, speed -> E -> Br -> T_magnet) -> PI (Ti 300 s) -> blower VFD 35-100 %; SP 85 C',
        'L3 winding temperature floor (part load): coolant SP = 55 + 13 x (1 - (P / 335 kW)^2) C (feed-forward from the AFE power) + slow PI trim (Ti 1200 s, +/-5 K) on the max slot PT100 towards 82 C -> the winding stays near its full-load temperature at every load (less thermal cycling of the VPI / Litz)',
        'interlocks: start permissive = glycol flow OK + blower running + T_supply > 20 C (heater 2 kW in the loop for cold starts / anti-condensation) ; blower stays on 15 min after stop'],
        tuning='PI gains tested in the transient model (no overshoot > 1 K on the supply, rotor settles in ~30 min)')
    out['protection'] = [
        dict(signal='winding slot PT100 (6, 3 used)', alarm_C=140, trip_C=155, note='class H 180 C; full-load value ~%.0f C' % st['335 kW, 45 C ambient']['hot_spots']['winding_slot_max']),
        dict(signal='end-winding PT100 (4, 2 used)', alarm_C=140, trip_C=155),
        dict(signal='rotor (IR + EMF observer)', alarm_C=130, trip_C=150, note='CFRP high-Tg epoxy (Tg >= 190 C) and magnet adhesive limit; Sm2Co17 itself is good to 300 C'),
        dict(signal='bearing outer ring PT100 (2)', alarm_C=100, trip_C=110),
        dict(signal='oil drain PT100 (2)', alarm_C=90, trip_C=100),
        dict(signal='coolant supply TT-G03', alarm_C=60, trip_C=65, low_alarm_C=40),
        dict(signal='coolant flow FT-G01', alarm='< 24 L/min', trip='< 15 L/min for 10 s -> unload to 40 % then trip at winding 155 C'),
        dict(signal='cooling-air dp PDT-A01 (filter + generator)', alarm='< 60 % of the speed-dependent nominal (blower fault) or filter dp > 200 Pa', trip='rotor trip via the IR / EMF signal'),
        dict(signal='glycol expansion-tank level LS-G01 + leak-off drain float switch LS-G02 (between the double O-rings, pod bottom)', alarm='low level / any leak-off', trip='low-low level'),
        dict(signal='vibration (2 accelerometers on the end bells)', alarm_mm_s=4.5, trip_mm_s=7.1),
        dict(signal='insulation (online IMD on the IT DC link)', alarm_kOhm=100, trip_kOhm=30)]
    out['sensors'] = ['6 x PT100 slot (flat 3 x 10 mm, between the layers at mid-stack, 2 per phase, 3-wire, class A)', '4 x PT100 end winding (2 per end, at the coil noses, bonded + tied before VPI)',
                      '2 x PT100 bearing outer ring (M8 x 1 probe in the cartridge, 1.5 mm wall)', '2 x PT100 oil drain', '4 x PT100 glycol (pod in / out, supply after the valve, return)',
                      '2 x PT100 cooling air (blower outlet, generator outlet)', '2 x IR pyrometer 8-14 um on the sleeve ends (Optris CSmicro LT (DE) / Calex PyroMini (UK)) through the end-bell ports',
                      'glycol vortex flow meter + flow switch', 'air dp transmitter (generator + filter)', '2 x accelerometers 100 mV/g on the end bells', '2 x speed / phase pickups on the front speed wheel']
    json.dump(out, open(os.path.join(HERE, 'eg_thermal.json'), 'w'), indent=1, default=float)
    print('jacket:', jd)
    print('air path @ %.3f kg/s:' % CTRL['m_air_max'], out['air_path_design'])
    for s in sweep:
        print('  air sweep 45 C:', s)
    for k, v in st.items():
        print('%-48s blower %3d %%  %s  heat %s' % (k, v['blower_pct'], {kk: v['hot_spots'][kk] for kk in ('winding_hot_spot_est', 'winding_slot_max', 'end_winding_front', 'end_winding_rear',
              'magnet_max', 'sleeve_max', 'bearing_front', 'gap_air_out', 'glycol_out')}, v['heat']))
    print('dry cooler:', {k: v for k, v in out['dry_cooler'].items() if k not in ('spec',)})
    print('pump:', out['pump']['head_kPa'], 'kPa', out['pump']['P_el_W'], 'W')
    print(json.dumps(summ, indent=0)[:3000])
    print('-> sim/variant_e/eg_thermal.json')


if __name__ == '__main__':
    main()
