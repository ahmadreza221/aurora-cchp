# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP electrical sizing: PMG/rectifier window, FPT load-loss overspeed, dump resistor, pre-charge,
inverter surge, HV battery C-rate, 48 V essential-bus UPS, cable voltage drop.

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
I_MPPT_MAX = 36.0        # per-MPPT current limit of the candidate inverters (Deye HP3 ~36 A, Solis S6-EH3P 40 A)

# rotor of the free power turbine + PMG (assumed until the FPT/PMG CAD exists)
J_FPT, J_PMG, J_SHAFT = 4.0e-4, 3.0e-4, 1.0e-4   # kg m^2

# loads (docs/03 §0, §2; company ~20 kW of pumps + split/packaged AC)
INV_P = 30e3             # inverter rating, 3-phase 400/230 V
INV_SURGE = (1.5, 10.0)  # (x rated, seconds) — Deye HP3 class; Solis S6-EH3P: 1.6x for 2 s (verify on datasheet)
BASE_KW = 15.0           # company load already running when a motor starts (balanced)
AUX_KW = 6.0             # plant auxiliaries on AC in summer: docs/hvac/06_bom_electrical.md (5.9 kW BOP + engine AC aux)
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


def inverter_surge():
    hdr('5. Inverter surge check (%.0f kW, %.1fx for %.0f s)' % (INV_P / 1e3, *INV_SURGE))
    i_rated = INV_P / 3 / 230
    i_surge = i_rated * INV_SURGE[0]
    flc = PUMP_KW * 1e3 / (math.sqrt(3) * 400 * PUMP_EFF * PUMP_PF)
    base = (BASE_KW + AUX_KW) * 1e3 / 3 / 230
    print('rated %.1f A/phase, surge %.1f A/phase; pump FLC %.1f A; base load %.1f A/phase' % (i_rated, i_surge, flc, base))
    rows = [('3 kW pump DOL (LRC 6.5 x FLC)', 6.5 * flc), ('3 kW pump star (LRC/3)', 6.5 * flc / 3),
            ('3 kW pump star->delta open transition spike (~6 x, 1-2 cycles)', 6.0 * flc), ('3 kW pump on VFD (<= 1.1 x FLC)', 1.1 * flc),
            ('24k BTU split fixed-speed (LRA, one phase)', AC_LRA), ('same + compressor soft starter (-65 %)', AC_LRA * 0.35),
            ('inverter-type (DC inverter) split', AC_RLA),
            ('two fixed-speed splits on one phase at once', 2 * AC_LRA)]
    for lab, i in rows:
        tot = base + i
        print('  %-62s start %5.1f A -> phase %5.1f A = %4.2f x rated (%s)'
              % (lab, i, tot, tot / i_rated, 'OK' if tot <= i_rated else ('surge window' if tot <= i_surge else 'EXCEEDS SURGE')))


def battery():
    hdr('6. HV battery: power, not energy, sets the size')
    p_trip = (20 + AUX_TRIP_KW) * 1e3
    p_crit = 10e3
    print('turbine trip at full company load: battery carries %.1f kW for <= 60 s (load shedding), then <= %.0f kW critical load'
          % (p_trip / 1e3, p_crit / 1e3))
    for kwh in (10.2, 15.4, 20.5, 25.6):
        cont, peak = kwh * 1.0, kwh * 1.5          # typical HV LFP stack: 1C continuous, ~1.5C for 60 s (verify per product)
        ok = peak * 1e3 >= p_trip * 1.2 and cont * 1e3 >= p_crit
        print('  %4.1f kWh LFP: 1C continuous %4.1f kW, 1.5C/60 s peak %4.1f kW -> %s'
              % (kwh, cont, peak, 'OK (>= 1.2 x trip load)' if ok else 'too small for a full-load trip'))
    print('  energy reserve for a restart: 15 min start at ~4 kW + 30 min critical load 5 kW = %.1f kWh; SOC window 20-90 %%' % (4 * 0.25 + 5 * 0.5))


def ups48():
    hdr('7. 48 V essential bus (DC-UPS, independent of HV battery and inverter)')
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
            ('AC 400 V ER->roof BOP-R, 5G10, 20 A (HVAC ~10 kW connected)', 400, 20, L_ROOF, 10, True),
            ('48 V ER->roof, 2 x 1 x 25 mm2, starter peak 58 A', 48, 58, 2 * L_ROOF, 25, False),
            ('48 V ER->roof, 2 x 1 x 25 mm2, steady 15 A', 48, 15, 2 * L_ROOF, 25, False)]
    for lab, v, i, l, a, three in rows:
        r = RHO_CU_70C * l / a
        dv = (math.sqrt(3) * i * r if three else i * r)
        print('  %-52s dV %5.2f V = %4.2f %%  loss %4.0f W' % (lab, dv, dv / v * 100, (3 if three else 1) * i * i * r))


if __name__ == '__main__':
    pmg_rectifier(); overspeed(); dump_resistor(); precharge(); inverter_surge(); battery(); ups48(); cables()
