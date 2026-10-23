# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CHP (concept S3) — temperature / speed / life / efficiency trade-off.

Speed line (air flow, PR vs N1) from gr180_cycle calibrated on Rutten's test data (115 N@100k ... 186 N@119k, eta_c 0.70).
Life indicators are first estimates for choosing the operating point; FEA (CalculiX) replaces them in phase 1:
  * turbine blade root centrifugal stress ~ 283 MPa @120k (tapered blade, rho 8000) scaled with N^2
  * blade metal temperature ~ TIT - 70 K (relative frame + conduction to disk)
  * creep rupture: Larson-Miller (C=20) for cast IN-713LC, generic literature curve; design value uses stress x 1.5
  * disk bore hoop stress ~ 640 MPa @120k (uniform-disk estimate incl. blade rim load) scaled with N^2; IN-713LC
    yield ~ 740 MPa at the bore temperature (~450 C)

Run:  uv run sim/life_study.py
"""
import math
import concept_study as cs

SPEED_LINE = [(100e3, 2.52, 0.337), (105e3, 2.72, 0.359), (110e3, 2.86, 0.373), (117e3, 3.19, 0.407), (119e3, 3.27, 0.415)]
LMP_713LC = [(700, 21.2e3), (500, 23.8e3), (330, 25.0e3), (200, 26.3e3), (80, 28.8e3)]   # (stress MPa, T[K]*(20+log10 t_h))

def line(N):
    for (n0, p0, m0), (n1, p1, m1) in zip(SPEED_LINE[:-1], SPEED_LINE[1:]):
        if n0 <= N <= n1 or N > SPEED_LINE[-1][0]:
            t = (N - n0) / (n1 - n0); return p0 + t * (p1 - p0), m0 + t * (m1 - m0)
    return SPEED_LINE[0][1], SPEED_LINE[0][2]

def lmp(sig):
    for (s0, P0), (s1, P1) in zip(LMP_713LC[:-1], LMP_713LC[1:]):
        if s1 <= sig <= s0:
            t = (math.log(s0) - math.log(sig)) / (math.log(s0) - math.log(s1)); return P0 + t * (P1 - P0)
    return LMP_713LC[0][1] if sig > LMP_713LC[0][0] else LMP_713LC[-1][1]

def creep_hours(sig, T_metal_K):
    return 10 ** (lmp(sig) / T_metal_K - 20)

EFF = {'target': dict(eta_c=0.73, eta_t=0.82, eta_pt=0.78), 'as-is': dict(eta_c=0.70, eta_t=0.80, eta_pt=0.75)}

# As-built engine (docs/08_design_point_update.md).  Used by cchp_study, sim/hvac and docs/electrical/calc via asbuilt=True;
# the engine sizing scripts (sim/engine/*) keep the original cycle (asbuilt=False) as their design basis.
#  * E3 (docs/engine/E3_fpt_pmg.md): FPT aero 25.41 kW (E1 meanline P03 0.94 % below the cycle), bearings/seals 0.54 kW
#    -> shaft 24.86 kW; PMG 24.86 -> 24.11 kW at the terminals (eta 0.970 here, 0.975 at the 30 kW rating).
#    The FPT was matched to the cycle's back-pressure budget (recuperator hot side 3.5 %), so the budget dp is kept here.
#  * E4 (sim/engine/e4_recuperator_calc.py): eps net 0.905 at design flow (clean 0.913 - 0.008), higher at part flow;
#    duty and exhaust temperature with real cp(T) -> 169 kW, hot outlet ~219 C (constant-cp model: 159 kW, 262 C).
E4_EPS_CLEAN = [(0.50, 0.941), (0.75, 0.926), (1.00, 0.913)]       # (flow / design flow, clean effectiveness), E4 sec. 5
E4_EPS_LOSS, E4_FLOW_DES = 0.008, 0.3949                            # maldistribution + longitudinal conduction; kg/s
ASBUILT = dict(fpt_k=0.9762, fpt_loss=540.0, eta_gen=0.970, real_cp=True)

def eps_e4(ma):
    x = ma / E4_FLOW_DES
    pts = E4_EPS_CLEAN
    if x <= pts[0][0]:
        e = pts[0][1]
    else:
        i = 1 if x <= pts[1][0] else 2
        (x0, e0), (x1, e1) = pts[i - 1], pts[i]
        e = e0 + (x - x0) / (x1 - x0) * (e1 - e0)                  # linear, extrapolated above design flow
    return e - E4_EPS_LOSS

def point(N, TIT_C, eff='target', eps=0.90, T_amb_C=15.0, alt_m=0.0, booster=True, asbuilt=False):
    """Compressor runs on corrected speed N/sqrt(theta); physical flow = corrected flow * delta/sqrt(theta)."""
    th = (T_amb_C + 273.15) / 288.15; de = (1 - 2.25577e-5 * alt_m) ** 5.25588
    PR, ma_c = line(N / math.sqrt(th)); ma = ma_c * de / math.sqrt(th)
    extra = dict(ASBUILT) if asbuilt else {}
    if asbuilt:
        eps = eps_e4(ma)
    r = cs.cycle(dict(EFF[eff], arch='fpt', ma=ma, PR=PR, TIT=TIT_C + 273.15, eps=eps,
                      T_amb=T_amb_C + 273.15, P_amb=101325.0 * de, booster=booster, **extra))
    sb = 283.0 * (N / 120e3) ** 2
    r.update(N=N, PR=PR, ma=ma, eps=eps, sig_blade=sb, sig_bore=640.0 * (N / 120e3) ** 2,
             life_blade=creep_hours(1.5 * sb, TIT_C + 273.15 - 70), T4=None)
    return r

def main():
    print('Concept S3, recuperator eps 0.90, %s efficiencies' % 'TARGET (tuned core, FPT 0.78)')
    print('%7s %5s %6s %5s | %6s %6s | %6s %6s %6s | %8s %8s %8s' % ('N1', 'TIT', 'air', 'PR', 'P_el', 'eta_el', 'comb', 'FPTex', 'stack',
                                                                  'sig_bl', 'bl.life', 'bore/ys'))
    print('%7s %5s %6s %5s | %6s %6s | %6s %6s %6s | %8s %8s %8s' % ('rpm', 'C', 'kg/s', '', 'kW', '%', 'in C', 'C', 'in C', 'MPa', 'h (SF1.5)', ''))
    for N in (100e3, 105e3, 110e3, 115e3, 119e3):
        for T in (750, 800, 850):
            r = point(N, T)
            print('%7.0f %5d %6.3f %5.2f | %6.1f %6.1f | %6.0f %6.0f %6.0f | %8.0f %8.0f %8.2f' % (
                N, T, r['ma'], r['PR'], r['P_el'] / 1e3, r['eta_el'] * 100, r['T2r'] - 273.15, r['T_hot'] - 273.15,
                r['T_stack_in'] - 273.15, r['sig_blade'], min(r['life_blade'], 9.99e6), r['sig_bore'] / 740))
        print()
    print('Same with AS-IS component efficiencies (eta_c .70, eta_t .80, FPT .75):')
    for N, T in ((110e3, 800), (112e3, 800), (115e3, 800), (119e3, 850)):
        r = point(N, T, 'as-is')
        print('  N1 %3.0fk TIT %d C: P_el %.1f kW, eta_el %.1f %%' % (N / 1e3, T, r['P_el'] / 1e3, r['eta_el'] * 100))

def site():
    """Customer site: 50 m altitude, intake air held at <= 30 C, city gas 4 barg (no booster)."""
    print('SITE: 50 m, intake 30 C, no gas booster, recuperator eps 0.90')
    print('%5s %5s %5s | %6s %6s %6s | %6s %6s | %7s %9s' % ('N1 k', 'TIT', 'eff', 'air', 'PR', 'P3bar', 'P_el', 'eta_el', 'sig_bl', 'blade h'))
    for eff in ('target', 'as-is'):
        for N in (110e3, 115e3, 119e3):
            for T in (800, 825, 850):
                r = point(N, T, eff, T_amb_C=30.0, alt_m=50.0, booster=False)
                print('%5.0f %5d %6s | %6.3f %6.2f %6.2f | %6.1f %6.1f | %7.0f %9.0f' % (N / 1e3, T, eff, r['ma'], r['PR'], r['P3'] / 1e5,
                      r['P_el'] / 1e3, r['eta_el'] * 100, r['sig_blade'], min(r['life_blade'], 9.99e6)))
    for Tin in (15.0, 20.0, 25.0, 30.0):
        r = point(115e3, 800, 'target', T_amb_C=Tin, alt_m=50.0, booster=False)
        print('  intake %2.0f C, 115k/800 C target: %.1f kW, %.1f %%' % (Tin, r['P_el'] / 1e3, r['eta_el'] * 100))

if __name__ == '__main__':
    import sys
    site() if 'site' in sys.argv else main()
