# GR180 version D: radial-inflow turbine concept (shape + first meanline numbers) to replace the v13A axial turbine.
# Single shaft at 115k rpm: the turbine drives the compressor (~60 kW) and the front generator (~25 kW shaft).
# Gas from the annular combustor turns outward into a plenum, passes a 17-vane radial nozzle ring and enters the
# 13-blade wheel (radial-element blades at the inlet, twisted exducer), leaving axially into the exhaust diffuser.
# Envelope-level geometry for layout and look; the real aero/FEA design comes later.
# ENG frame (mm), x = engine axis. Run: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d_radial_turbine.py
import FreeCAD as App, Part, os, json, math
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if not os.path.exists(os.path.join(ROOT, 'cad_out')):
    ROOT = os.environ.get('GR180_ROOT', os.getcwd())
OUT = os.path.join(ROOT, 'cad_out', 'variant_d', 'RT'); os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- first meanline (single shaft, design point)
N = 115000.0; m = 0.40; T04 = 1073.15; P04 = 2.87e5; cp, g = 1148.0, 1.333
W_turb = 59.5e3 + 25.5e3                          # compressor + generator shaft (v13A compressor 0.395 kg/s, PR 3.1)
dh0 = W_turb / m                                  # J/kg
eta_ts = 0.80
dh_is = dh0 / eta_ts
PR_ts = (1 - dh_is / (cp * T04)) ** (-g / (g - 1))
C0 = math.sqrt(2 * dh_is)
D4 = 96.0; U4 = math.pi * D4 / 1000 * N / 60       # wheel tip diameter / speed
psi = dh0 / U4 ** 2
T6 = T04 - dh0 / cp; P6 = P04 / PR_ts
rho4 = 0.92 * P04 / (287 * T04)                    # static ~ 0.92 of total at the rotor inlet
cm4 = 0.26 * U4
b4 = m / (rho4 * cm4 * math.pi * D4 / 1000) * 1000
D6t, D6h = 74.0, 22.0
A6 = math.pi / 4 * ((D6t / 1000) ** 2 - (D6h / 1000) ** 2)
c6 = m / (P6 / (287 * T6) * A6)
MEAN = dict(N_rpm=N, mass_kg_s=m, T04_C=T04 - 273.15, P04_bar=P04 / 1e5, turbine_work_kW=W_turb / 1e3, dh0_kJ_kg=dh0 / 1e3,
            eta_ts=eta_ts, PR_ts=PR_ts, U4_m_s=U4, U_over_C0=U4 / C0, psi=psi, D4_mm=D4, b4_mm=b4, D6_tip_mm=D6t,
            D6_hub_mm=D6h, exducer_ratio=D6t / D4, c6_axial_m_s=c6, T6_C=T6 - 273.15, Z_rotor=13, Z_nozzle=17,
            alpha4_deg=round(math.degrees(math.atan(1 / 0.26 * psi)), 1),
            notes='U4 ~578 m/s is high for 800 C IN713LC: confirm by FEA/creep; exit velocity recovered in the diffuser')
for k, v in MEAN.items():
    print('%-16s %s' % (k, round(v, 3) if isinstance(v, float) else v))

# ---------------------------------------------------------------- geometry
X0 = 105.0                  # wheel back-plate face / inlet hub side (v13A turbine sat at x 107..122)
B4 = round(b4, 1)
R4 = D4 / 2; X6 = X0 + 47.0; R6H, R6T = D6h / 2, D6t / 2
def hub(a):  return (X6 - (X6 - X0) * math.cos(a), R4 - (R4 - R6H) * math.sin(a))
def shr(a):  return (X6 - (X6 - X0 - B4) * math.cos(a), R4 - (R4 - R6T) * math.sin(a))
def P(x, r, th): return V(x, r * math.cos(th), r * math.sin(th))

parts = {}
# hub body: back-plate disc + hub of revolution + nose stub (nut side)
prof = [V(X0 - 5, 0, 0), V(X0 - 5, 0, R4), V(X0, 0, R4)]
prof += [V(*[hub(a)[0], 0, hub(a)[1]]) for a in [i / 24 * math.pi / 2 for i in range(1, 25)]]
prof += [V(X6 + 8, 0, R6H), V(X6 + 8, 0, 0), V(X0 - 5, 0, 0)]
hubsolid = Part.Face(Part.makePolygon(prof)).revolve(V(0, 0, 0), V(1, 0, 0), 360)
# blades: radial-element at the inlet, wrap theta(s) = THM * s^2 (same on hub and shroud -> radial fibres)
THM, T_BL, Z = math.radians(42.0), 1.4, 13
wires = []
for i in range(17):
    s = i / 16; a = s * math.pi / 2; th = THM * s * s
    (xh, rh), (xs, rs) = hub(a), shr(a)
    rh_ = max(rh - 0.6, 1.0)                        # sink into the hub
    dh, ds = T_BL / 2 / rh_, T_BL / 2 / rs
    wires.append(Part.makePolygon([P(xh, rh_, th - dh), P(xs, rs, th - ds), P(xs, rs, th + ds), P(xh, rh_, th + dh), P(xh, rh_, th - dh)]))
blade = Part.makeLoft(wires, True, True)
blades = [blade.copy() for _ in range(Z)]
for k, b in enumerate(blades):
    b.rotate(V(0, 0, 0), V(1, 0, 0), 360.0 * k / Z)
wheel = hubsolid.fuse(blades).removeSplitter()
parts['RT-101_Radial_Turbine_Wheel_13bl'] = wheel
# radial nozzle ring: 17 vanes between two side rings, vanes at ~alpha4 to the radial direction
RN0, RN1 = R4 + 3.0, R4 + 17.0
vanes = []
alpha = math.radians(MEAN['alpha4_deg'])
for k in range(17):
    th0 = 2 * math.pi * k / 17
    lead = P(X0, RN1, th0); trail_th = th0 + (RN1 - RN0) * math.tan(alpha) / RN0 * 0.55
    pts = [P(X0, RN1, th0), P(X0, RN0, trail_th), P(X0, RN0, trail_th + 0.03), P(X0, RN1, th0 + 0.045), P(X0, RN1, th0)]
    vanes.append(Part.Face(Part.makePolygon(pts)).extrude(V(B4, 0, 0)))
side_f = Part.makeCylinder(RN1 + 6, 2.5, V(X0 - 2.5, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(RN0 - 1, 4, V(X0 - 3, 0, 0), V(1, 0, 0)))
side_r = Part.makeCylinder(RN1 + 6, 2.5, V(X0 + B4, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(RN0 - 1, 4, V(X0 + B4 - 1, 0, 0), V(1, 0, 0)))
parts['RT-110_Radial_Nozzle_Ring_17v'] = side_f.fuse(side_r).fuse(vanes).removeSplitter()
# turbine housing / inlet plenum: gas from the combustor annulus (r 22..48 at x ~100) turns outward to the nozzle ring
RH = RN1 + 16.0
shell = Part.makeCylinder(RH + 3, X0 + B4 + 8 - (X0 - 22), V(X0 - 22, 0, 0), V(1, 0, 0)).cut(
    Part.makeCylinder(RH, X0 + B4 + 8 - (X0 - 22) + 2, V(X0 - 23, 0, 0), V(1, 0, 0)))
front_wall = Part.makeCylinder(RH + 3, 3, V(X0 - 22, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(49.0, 5, V(X0 - 23, 0, 0), V(1, 0, 0)))
rear_wall = Part.makeCylinder(RH + 3, 3, V(X0 + B4 + 5, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(RN0 - 2, 5, V(X0 + B4 + 4, 0, 0), V(1, 0, 0)))
# exducer shroud (follows the blade tip with 0.4 mm clearance) out to the diffuser flange
sp = [V(*[shr(a)[0], 0, shr(a)[1] + 0.4]) for a in [i / 24 * math.pi / 2 for i in range(0, 25)]]
sp_o = [V(p.x, 0, p.z + 3.0) for p in reversed(sp)]
shroud = Part.Face(Part.makePolygon(sp + [V(X6 + 12, 0, R6T + 0.4), V(X6 + 12, 0, R6T + 3.4)] + sp_o + [sp[0]])).revolve(V(0, 0, 0), V(1, 0, 0), 360)
parts['RT-120_Turbine_Housing_Plenum'] = shell.fuse(front_wall).fuse(rear_wall).removeSplitter()
parts['RT-121_Exducer_Shroud'] = shroud
parts['RT-130_Tie_Nut'] = Part.makeCylinder(6.0, 8.0, V(X6 + 8, 0, 0), V(1, 0, 0))

info = dict(meanline=MEAN, parts={})
for k, s in parts.items():
    s.exportStep(os.path.join(OUT, k + '.step'))
    bb = s.BoundBox
    info['parts'][k] = dict(valid=s.isValid(), x=[round(bb.XMin, 1), round(bb.XMax, 1)], r=round(max(bb.YMax, bb.ZMax), 1),
                            volume_cm3=round(s.Volume / 1000, 1))
    print(k, s.isValid(), 'x %.0f..%.0f r %.0f vol %.1f cm3' % (bb.XMin, bb.XMax, max(bb.YMax, bb.ZMax), s.Volume / 1000))
json.dump(info, open(os.path.join(OUT, 'radial_turbine.json'), 'w'), indent=1)
