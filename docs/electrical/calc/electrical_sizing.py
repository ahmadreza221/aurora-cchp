# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP electrical sizing: PMG/rectifier window, FPT load-loss overspeed, dump resistor, pre-charge,
per-phase surge and unbalance with the real loads (rev 3), 20 kWh HV battery power, 48 V essential-bus UPS, cable voltage drop.

Every assumption is a named constant below; docs/electrical/*.md quote the printed results.
Run:  python3 docs/electrical/calc/electrical_sizing.py
"""
import math

# ---------------------------------------------------------------- design basis (docs/03 §1, §5, §9; sim/cchp_study.py)
P_SHAFT_V1 = 25.6e3      # FPT shaft power, 115k / TIT 800 C / intake chilled to 15 C (sim: life_study.point)
P_DESIGN = 30e3          # modular rating of FPT, PMG, rectifier, inverter (docs/03 §0)
ETA_PMG, ETA_REC = 0.95, 0.985
N2_RATED, N2_MAX_GOV, N2_TRIP_SMCU = 60e3, 65e3, 71.5e3
E_LL_RATED = 360.0       # PMG back-EMF, line-line rms at 60k rpm (design rule chosen below)
L_S = 100e-6             # PMG synchronous inductance per phase (assumed, high-speed SPM)
V_MP, V_OC, V_CHOP_ON, V_CHOP_FULL, V_OVP_HW = 720.0, 780.0, 800.0, 830.0, 900.0   # DC link (PV-emulation window)
I_MPPT_MAX = 36.0        # per-MPPT current limit of the reference hybrid inverter (Deye SUN-30K-SG01HP3-EU-BM3: 3x 36 A, 150-850 V)

# rotor of the free power turbine + PMG (assumed until the FPT/PMG CAD exists)
J_FPT, J_PMG, J_SHAFT = 4.0e-4, 3.0e-4, 1.0e-4   # kg m^2

# loads (docs/03 §0, §2; company ~20 kW of pumps + split/packaged AC)
INV_P = 30e3             # inverter rating, 3-phase 400/230 V
INV_SURGE = (1.5, 10.0)  # (x rated, seconds) — Deye HP3 class; Solis S6-EH3P: 1.6x for 2 s (verify on datasheet)
BASE_KW = 15.0           # company load already running when a motor starts (balanced)
AUX_KW = 4.0             # plant auxiliaries on AC in summer: sim/hvac/hvac_results.json revA (3.8 kW) + engine AC aux
AUX_TRIP_KW = 2.5        # aux left after a turbine trip (HVAC BOP pumps/tower shed by B6-R: no heat, no chiller)
PUMP_KW, PUMP_EFF, PUMP_PF = 3.0, 0.86, 0.82
AC_RLA, AC_LRA = 10.0, 50.0   # 24k BTU fixed-speed split, single phase 230 V

RHO_CU_70C = 0.0206      # ohm mm^2 / m, copper at 70 C
L_ROOF = 30.0            # cable route roof panel RP-1 <-> electrical room (ASSUMPTION, confirm on site)
L_HALL = 6.0             # electrical room <-> hall / company DB (docs/03 §8)


def hdr(t):
    print('\n' + t + '\n' + '-' * len(t))


def pmg_rectifier():
    hdr('1. PMG / active rectifier window')
    p_dc = P_SHAFT_V1 * ETA_PMG * ETA_REC
    print('v1 DC power into the inverter PV port: %.1f kW (shaft %.1f kW x PMG %.2f x rectifier %.3f)'
          % (p_dc / 1e3, P_SHAFT_V1 / 1e3, ETA_PMG, ETA_REC))
    for poles in (2, 4):
        f = [n / 60 * poles / 2 for n in (50e3, N2_RATED, N2_MAX_GOV, N2_TRIP_SMCU)]
        print('  %d-pole PMG: f_e = %.0f / %.0f / %.0f / %.0f Hz at 50k / 60k / 65k / 71.5k rpm -> f_sw >= 30 x f_e = %.0f kHz'
              % (poles, *f, 30 * f[2] / 1e3))
    i_ph = P_DESIGN / ETA_REC / (math.sqrt(3) * E_LL_RATED * 0.98)
    print('E_LL = %.0f V rms @60k -> phase current at %.0f kW DC: %.1f A rms' % (E_LL_RATED, P_DESIGN / 1e3, i_ph))
    for n in (N2_RATED, N2_MAX_GOV, N2_TRIP_SMCU):
        e_pk_ph = E_LL_RATED * n / N2_RATED * math.sqrt(2) / math.sqrt(3)
        w = 2 * math.pi * n / 60                       # 2-pole: electrical = mechanical rad/s
        v_term = math.hypot(e_pk_ph, w * L_S * i_ph * math.sqrt(2))
        v_avail = V_MP / math.sqrt(3)
        print('  %5.1fk rpm: E_ph,pk %.0f V, |E + jwLI|pk %.0f V vs SVPWM limit %.0f V at %.0f V DC -> modulation %.2f;'
              ' diode-rectified EMF peak %.0f V (%s DC link -> NO passive braking)'
              % (n / 1e3, e_pk_ph, v_term, v_avail, V_MP, v_term / v_avail, e_pk_ph * math.sqrt(3),
                 '<' if e_pk_ph * math.sqrt(3) < V_MP else '>='))
    for p in (p_dc, P_DESIGN):
        i = p / V_MP
        print('  DC current at %.1f kW, %.0f V: %.1f A -> %d MPPT input(s) of %.0f A' % (p / 1e3, V_MP, i, math.ceil(i / I_MPPT_MAX), I_MPPT_MAX))


def overspeed():
    hdr('2. FPT load loss: overspeed with NO electrical braking')
    J = J_FPT + J_PMG + J_SHAFT
    w0 = 2 * math.pi * N2_RATED / 60
    print('J (FPT + PMG + shaft) = %.1e kg m^2 (assumed); stored energy at 60k = %.1f kJ' % (J, 0.5 * J * w0 ** 2 / 1e3))
    for p in (P_SHAFT_V1, P_DESIGN):
        for pct in (1.05, 1.10, 1.20):
            dt = 0.5 * J * ((w0 * pct) ** 2 - w0 ** 2) / p
            print('  P = %.1f kW: time to %3.0f %% speed = %4.0f ms' % (p / 1e3, pct * 100, dt * 1e3))
    print('  after fuel cut the hot recuperator keeps driving the gas generator and the FPT; energy E = P0 x tau:')
    for tau in (1.0, 3.0, 10.0):
        e = P_SHAFT_V1 * tau
        wf = math.sqrt(w0 ** 2 + 2 * e / J)
        print('    tau %4.1f s: E %5.0f kJ -> runaway bound %.0fk rpm (%.0f %%), windage/turbine torque roll-off ignored'
              % (tau, e / 1e3, wf * 60 / 2 / math.pi / 1e3, wf / w0 * 100))
    print('  => braking must be local hardware (< 20 ms), continuous, and redundant (DC chopper + independent PMG brake).')


def dump_resistor():
    hdr('3. Dump (braking) resistor on the DC link + independent PMG brake')
    p_peak = 36e3
    r = V_CHOP_ON ** 2 / p_peak
    print('R_DC = V_on^2 / P_peak = %.0f^2 / %.0f kW = %.1f ohm -> 2 x 36 ohm in parallel = 18 ohm' % (V_CHOP_ON, p_peak / 1e3, r))
    for v in (V_CHOP_ON, V_CHOP_FULL, V_OVP_HW):
        print('  at %.0f V: %.1f kW' % (v, v ** 2 / 18.0 / 1e3))
    cases = [('load rejection, fuel to idle in 2 s, inverter back after 30 s (idle FPT ~4 kW)', P_SHAFT_V1 * 1.0 + 4e3 * 30),
             ('start: FPT held at GG idle until inverter accepts PV (300 s x 4 kW)', 4e3 * 300),
             ('ESD from full load, recuperator soak tau 10 s', P_SHAFT_V1 * 10)]
    for lab, e in cases:
        print('  %-80s %6.0f kJ' % (lab, e / 1e3))
    print('  rating: 36 kW peak (10 s), >= 400 kJ adiabatic, 6 kW continuous, IP23 + rain hood, NC thermal switch')
    for n in (N2_RATED, 66e3, N2_TRIP_SMCU):
        vdc = 1.35 * E_LL_RATED * n / N2_RATED
        print('  independent PMG brake (diode bridge + chopper, R 8 ohm): %.1fk rpm -> %.0f V DC -> %.1f kW'
              % (n / 1e3, vdc, vdc ** 2 / 8.0 / 1e3))


def precharge():
    hdr('4. DC pre-charge (rectifier DC link -> inverter PV input)')
    c = 400e-6 + 200e-6         # B3 film link + inverter PV input capacitance (assumed)
    r = 100.0
    print('C = %.0f uF, R_pre = %.0f ohm: tau %.0f ms, 5 tau %.0f ms, I_peak %.1f A, energy in R %.0f J (= 1/2 C V^2)'
          % (c * 1e6, r, r * c * 1e3, 5 * r * c * 1e3, V_MP / r, 0.5 * c * V_MP ** 2))
    print('  close the main contactor when |V_B3 - V_inv| < 20 V; pre-charge resistor: 2 x 50 ohm 50 W, pulse >= 300 J')


# ---------------------------------------------------------------- hybrid inverter (backup LOAD port) per phase, real loads (rev 3)
# (name, per-phase continuous A (rated / 3 phases), per-phase max unbalanced A, peak factor x rated, peak s, battery A, note) — datasheets 09/2026
INVERTERS = [
    ('Deye SUN-30K-SG01HP3-EU-BM3 (CN, reference)', 30e3 / 3 / 230, 60.0, 1.5, 10, 100, 'each phase <= 50 % rated; 2x 50 A battery inputs',
     (204.8, 'Deye BOS-G20')),
    ('Deye SUN-25K-SG01HP3-EU-AM2 (CN)', 25e3 / 3 / 230, 25e3 * 0.5 / 230, 1.5, 10, 50, '1x 50 A battery input', (204.8, 'Deye BOS-G20')),
    ('SMA STP Hybrid X 30 + SMA Backup (DE)', 29.99e3 / 3 / 230, 29.99e3 / 3 / 230, 1.0, 0, 50, 'backup after 1-600 s grid loss (not seamless); surge not stated',
     (400.0, 'SMA Home Storage / Storage M (~400 V assumed)')),
    ('KOSTAL PLENTICORE G3 L 20 + BackUp Switch (DE)', 32.0, 32.0, 22.1 / 20.0, 5, 30, 'backup < 5 s (manual) / < 30 s (auto box)',
     (409.6, 'BYD HVM 22.1')),
]
# real site loads (user): per phase allocation of 06 §7 (one split per phase); amps at 230 V
SPLIT_RLA, SPLIT_LRA = 5.5, 27.0     # 12,000 BTU fixed-speed wall split (~1.2 kW), LRA ~5x RLA (measure at commissioning)
FRIDGE_RLA, FRIDGE_LRA = 0.8, 8.0
PUMP_FLC_3PH = 3.0e3 / (math.sqrt(3) * 400 * 0.86 * 0.82) * 0.95   # 3 kW pump on VFD, input current per phase (VFD PF ~0.95)
AUX_HVAC_KW = 3.3                    # HVAC aux BALANCED (docs/hvac rev B), mostly three-phase
CTRL_KW = 0.3
PHASE_1PH_KW = {'L1': ('split 1 + fridge + lighting 0.6 kW', 1.2 + 0.15 + 0.6), 'L2': ('split 2 + PCs 0.8 kW', 1.2 + 0.8),
                'L3': ('split 3 + TV/sockets 0.4 kW + ER single-phase HVAC (FCU-E/AC-E) 0.9 kW', 1.2 + 0.4 + 0.9)}
BAT_STACK_V = 204.8                  # Deye BOS-G20: 4 x 51.2 V


def inverter_surge():
    hdr('5. Per-phase surge and unbalance with the real loads (backup LOAD port = worst case; with the grid in parallel the grid takes inrush)')
    three = PUMP_FLC_3PH + (AUX_HVAC_KW + CTRL_KW) * 1e3 / (3 * 230)
    base = {ph: three + kw * 1e3 / 230 for ph, (lab, kw) in PHASE_1PH_KW.items()}
    print('three-phase share per phase: pump on VFD %.1f A + HVAC aux/controls %.1f A = %.1f A' % (PUMP_FLC_3PH, three - PUMP_FLC_3PH, three))
    for ph, (lab, kw) in PHASE_1PH_KW.items():
        print('  %s: %-70s -> %.1f A running (all compressors on)' % (ph, lab, base[ph]))
    imax, imin = max(base.values()), min(base.values())
    print('  unbalance (I_max - I_min)/I_avg = %.0f %% (rule 06 §7-6: <= 30 %%)' % ((imax - imin) / (sum(base.values()) / 3) * 100))
    worst = max(base, key=base.get)
    for name, ic, iunb, pk, pks, ibat, note, bat in INVERTERS:
        ip = ic * pk if pks else ic
        print('  %s: per phase %.0f A rated, %.0f A unbalanced max, peak %.0f A (%s) [%s]' % (name, ic, iunb, ip, ('%d s' % pks) if pks else 'n/a', note))
        events = [('split restart (compressor off -> LRA)', base[worst] - SPLIT_RLA + SPLIT_LRA),
                  ('two splits starting on one phase (misallocated)', base[worst] - SPLIT_RLA + 2 * SPLIT_LRA),
                  ('split + fridge start together', base[worst] - SPLIT_RLA - FRIDGE_RLA + SPLIT_LRA + FRIDGE_LRA),
                  ('3 kW pump on VFD start', base[worst] + 0.1 * PUMP_FLC_3PH)]
        for lab, tot in events:
            verdict = 'OK (continuous)' if tot <= min(ic, iunb) else ('peak window' if tot <= 0.85 * max(ip, ic) else 'EXCEEDS 0.85 x peak')
            print('    %s %-46s %5.1f A -> %s' % (worst, lab, tot, verdict))
        tok = math.floor((0.85 * max(ip, ic) - (base[worst] - SPLIT_RLA)) / SPLIT_LRA)
        print('    start tokens on %s (06 §7-4): N_tok = %d' % (worst, min(2, max(tok, 0))))


def battery():
    hdr('6. Battery 20 kWh HV LFP (user decision): power check in backup')
    site_peak, site_typ = 8.0, 5.0
    aux = AUX_HVAC_KW + CTRL_KW
    p_trip = site_peak + aux
    print('backup + turbine trip: battery carries site %.1f + aux %.1f = %.1f kW until load shedding / restart' % (site_peak, aux, p_trip))
    for name, ic, iunb, pk, pks, ibat, note, (vbat, bname) in INVERTERS:
        p_bat = vbat * min(ibat, 100) * 0.97 / 1e3
        print('  %-48s %3d A x %.0f V (%s) -> %.1f kW from the battery -> %s' % (name, ibat, vbat, bname, p_bat,
              'OK' if p_bat >= p_trip else 'SHORT: shed to %.1f kW (groups 4, 3) or use a >= 400 V stack' % p_bat))
    e = 20.48 * 0.9
    print('  energy: %.1f kWh usable (90 %% DoD) -> %.1f h at %.1f kW (peak + aux), %.1f h at %.1f kW (typical + aux)'
          % (e, e / p_trip, p_trip, e / (site_typ + aux), site_typ + aux))
    print('  grid present (normal v1): turbine trip -> grid supplies the loads; battery only covers the short dip of a grid outage')
    print('  reserve for a black start without grid: 15 min start at ~4 kW + 30 min critical 5 kW = %.1f kWh; SOC floor 20 %% (= 4.1 kWh)' % (4 * 0.25 + 5 * 0.5))


def ups48():
    hdr('7. 48 V essential bus (DC-UPS, independent of the 20 kWh HV battery and the inverter)')
    loads = dict(ecu_b1=15, b2_sensors=25, b4_logic=10, b3_logic=30, hmi_b5=25, network=20, gas_valves=60, igniter=30,
                 oil_pump=150, coolant_pump=100, encl_fans=160, misc=40)
    run = sum(loads.values())
    blackout = loads['ecu_b1'] + loads['b2_sensors'] + loads['b4_logic'] + loads['oil_pump'] + loads['encl_fans'] + loads['network'] + loads['hmi_b5']
    print('running load %.0f W; blackout (post-lube + vent + controls) %.0f W; starter 2 kW x 90 s = %.0f Wh'
          % (run, blackout, 2000 * 90 / 3600))
    for ah in (50, 100):
        e = 51.2 * ah * 0.8
        print('  48 V %d Ah LFP: %.1f kWh usable -> %.1f h at running load, %.1f h blackout' % (ah, e / 1e3, e / run, e / blackout))


def cables():
    hdr('8. Cable voltage drop (copper %.4f ohm mm^2/m at 70 C)' % RHO_CU_70C)
    rows = [('DC 750 V roof->ER, 2 x 1 x 10 mm2, 41.7 A', 720, 41.7, 2 * L_ROOF, 10, False),
            ('DC 750 V roof->ER, 2 x 1 x 16 mm2, 41.7 A', 720, 41.7, 2 * L_ROOF, 16, False),
            ('AC 400 V ER->hall, 5G10, 43.5 A', 400, 43.5, L_HALL, 10, True),
            ('AC 400 V ER->roof BOP-R, 5G10, 20 A (HVAC ~11 kW connected)', 400, 20, L_ROOF, 10, True),
            ('48 V ER->roof, 2 x 1 x 25 mm2, starter peak 58 A', 48, 58, 2 * L_ROOF, 25, False),
            ('48 V ER->roof, 2 x 1 x 25 mm2, steady 15 A', 48, 15, 2 * L_ROOF, 25, False)]
    for lab, v, i, l, a, three in rows:
        r = RHO_CU_70C * l / a
        dv = (math.sqrt(3) * i * r if three else i * r)
        print('  %-52s dV %5.2f V = %4.2f %%  loss %4.0f W' % (lab, dv, dv / v * 100, (3 if three else 1) * i * i * r))


if __name__ == '__main__':
    pmg_rectifier(); overspeed(); dump_resistor(); precharge(); inverter_surge(); battery(); ups48(); cables()
