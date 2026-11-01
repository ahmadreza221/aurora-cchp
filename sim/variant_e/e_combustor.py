# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180 version E - single vertical reverse-flow CAN combustor (city gas) inside the cool pressure casing.

Lefebvre & Ballal 'Gas Turbine Combustion' (3rd ed.) design method:
  * casing reference area from the liner pressure-loss factor PLF = dP_liner / q_ref (tubular ~37);
  * liner diameter 0.68 x casing ID, zone lengths (primary 0.8 D, secondary 0.5 D, dilution 1.5 D);
  * air split (swirler, primary / secondary / dilution jets, film cooling) -> zone equivalence ratios;
  * hole areas from the liner pressure drop (Cd 0.6-0.65), jet penetration check;
  * loading parameter theta (combustion efficiency), residence time, heat-release intensity;
  * pattern factor (tubular-chamber correlation) at 770 and 850 C;
  * liner wall temperature + oxidation life (doubling per 25 K), NOx range (diffusion-type primary zone, estimate);
  * gas injector (8 radial holes, 0.30 bar), spark igniter, UV flame scanner.
Air / fuel / pressures from sim/variant_e/e_cycle.json (770 C design) and e_cycle.offdesign (850 C peak).

Run:  python3 sim/variant_e/e_combustor.py  ->  sim/variant_e/e_combustor.json
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e_props as gp                                                      # noqa: E402
import e_cycle as ec                                                      # noqa: E402

CASING_PIPE = dict(name='DN300 (323.9 x 7.1, EN 10216-2 P265GH or 1.4541)', OD=323.9, t=7.1)
DL_OVER_DREF = 0.68
SPLIT = dict(swirler=0.12, primary=0.18, secondary=0.15, film=0.20, dilution=0.35)
CD = dict(primary=0.60, secondary=0.60, dilution=0.65)
HOLES = dict(primary=8, secondary=12, dilution=10)


def T_ad(air, T_in, phi):
    """adiabatic flame temperature of the gas at equivalence ratio phi (no dissociation above ~2000 K: -3 %)"""
    far = phi * gp.STOICH_FAR
    prod = gp.products(air, far)
    T = prod.T_from_h((air.h(T_in) + far * gp.LHV) / (1 + far), 1800.0)
    return T - 0.03 * max(T - 1900.0, 0.0)


def design(r, label):
    air = r['air']
    m3 = r['ma'] * (1 - ec.B['leak_lost'] - ec.B['buffer'])
    T3, P3 = r['T2'], r['P3c']
    rho3 = P3 / (air.R * T3)
    dP_L = ec.B['dp_liner'] * P3
    PLF = 37.0
    D_ref = (CASING_PIPE['OD'] - 2 * CASING_PIPE['t']) / 1e3
    A_ref = math.pi / 4 * D_ref ** 2
    U_ref = m3 / (rho3 * A_ref)
    q_ref = 0.5 * rho3 * U_ref ** 2
    PLF_actual = dP_L / q_ref
    D_L = round(DL_OVER_DREF * D_ref * 1e3 / 5) * 5 / 1e3
    A_L = math.pi / 4 * D_L ** 2
    A_an = A_ref - math.pi / 4 * (D_L + 2 * 0.0015) ** 2
    U_an = m3 / (rho3 * A_an)
    L_pz, L_sz, L_dz = 0.8 * D_L, 0.5 * D_L, 1.5 * D_L
    L_L = L_pz + L_sz + L_dz
    mf = r['mf']
    phi_all = mf / m3 / gp.STOICH_FAR
    m_pz = m3 * (SPLIT['swirler'] + SPLIT['primary'] + 0.33 * SPLIT['film'])
    phi_pz = mf / m_pz / gp.STOICH_FAR
    m_sz = m_pz + m3 * (SPLIT['secondary'] + 0.33 * SPLIT['film'])
    phi_sz = mf / m_sz / gp.STOICH_FAR
    T_pz = T_ad(air, T3, min(phi_pz, 1.0))
    T_sz = T_ad(air, T3, phi_sz)
    V_j = math.sqrt(2 * dP_L / rho3)
    holes = {}
    for k in ('primary', 'secondary', 'dilution'):
        mj = m3 * SPLIT[k]
        A_eff = mj / (rho3 * V_j)
        A_geo = A_eff / CD[k]
        d = math.sqrt(4 * A_geo / HOLES[k] / math.pi)
        # jet penetration (Norster): Ymax = 1.15 d_j sqrt(J) sin(theta), J = momentum flux ratio jet / gas
        T_g = {'primary': T_pz, 'secondary': T_sz, 'dilution': 0.5 * (T_sz + r['TIT'])}[k]
        rho_g = P3 / (air.R * T_g)
        U_g = m3 * 0.6 / (rho_g * A_L)
        J = rho3 * (V_j * CD[k] / 0.8) ** 2 / (rho_g * U_g ** 2)
        Ymax = 1.15 * d * 0.8 * math.sqrt(J)
        holes[k] = dict(n=HOLES[k], d_mm=round(d * 1e3, 1), area_geo_mm2=round(A_geo * 1e6), J=round(J, 1), penetration_mm=round(Ymax * 1e3),
                        penetration_over_R=round(Ymax / (D_L / 2), 2))
    # film cooling: 4 slot rings, slot height 2.0 mm
    m_film = m3 * SPLIT['film']
    film = dict(rings=4, slot_h_mm=2.0, per_ring_kg_s=round(m_film / 4, 4), slot_velocity_m_s=round(m_film / 4 / (rho3 * math.pi * D_L * 0.002), 1),
                build='4 machined slot rings (turned 2.4951 alloy 75 (VDM), 48 x d4.0 metering holes each) welded between the rolled liner sections')
    # swirler: axial, 12 flat vanes 45 deg, hub 50 / tip 110 mm
    m_sw = m3 * SPLIT['swirler']
    A_sw = math.pi / 4 * (0.110 ** 2 - 0.050 ** 2) * (1 - 12 * 0.0015 / (math.pi * 0.08)) * math.cos(math.radians(45))
    V_sw = m_sw / (rho3 * A_sw)
    SN = 2 / 3 * (1 - (0.050 / 0.110) ** 3) / (1 - (0.050 / 0.110) ** 2) * math.tan(math.radians(45))
    # gas injector: 8 radial holes, dP 0.30 bar, gas at ~P3 + 0.3 bar, 30 C
    P_gas = P3 + 0.30e5
    rho_gas = P_gas / (518.3 * 303.0)
    V_gas = 0.80 * math.sqrt(2 * 0.30e5 / rho_gas)
    A_gas = mf / (rho_gas * V_gas)
    d_gas = math.sqrt(4 * A_gas / 8 / math.pi)
    # loading, residence time, heat release
    V_L = A_L * L_L
    theta = (P3 ** 1.75 * A_ref * D_ref ** 0.75 * math.exp(T3 / 300.0)) / m3
    eta_theta = 1 - math.exp(-theta / 2.9e7) if theta < 1e9 else 0.9999          # Lefebvre-type, calibrated to ~99.9 % at theta 2e8 (est)
    rho_avg = P3 / (air.R * 0.5 * (T_pz + r['TIT']))
    t_res = rho_avg * V_L / (r['ma'] + mf)
    HRI = mf * gp.LHV / (V_L * P3 / 101325.0) / 1e6
    # pattern factor (tubular, Lefebvre): (Tmax - T4) / (T4 - T3) = 1 - exp(-1 / (0.070 L/D dP/q))
    PF = 1 - math.exp(-1.0 / (0.070 * (L_L / D_L) * PLF_actual))
    PF_plenum = 0.75 * PF                                                       # extra mixing in the transition + 360 deg plenum (est)
    T_peak = r['TIT'] + PF_plenum * (r['TIT'] - T3)
    # liner wall temperature (est): film + backside convection -> wall at ~40 % of the way from T3 to the primary-zone gas
    T_wall = T3 + 0.40 * (T_pz - T3)
    out = dict(case=label, air_kg_s=m3, T3_C=T3 - 273.15, P3_bar=P3 / 1e5, fuel_kg_s=mf, TIT_C=r['TIT'] - 273.15,
               casing=dict(pipe=CASING_PIPE['name'], D_ref_mm=D_ref * 1e3, A_ref_m2=A_ref, U_ref_m_s=U_ref, q_ref_Pa=q_ref, dP_liner_kPa=dP_L / 1e3,
                           PLF=PLF_actual, annulus_velocity_m_s=U_an),
               liner=dict(D_mm=D_L * 1e3, L_mm=L_L * 1e3, L_pz_mm=L_pz * 1e3, L_sz_mm=L_sz * 1e3, L_dz_mm=L_dz * 1e3, volume_L=V_L * 1e3,
                          material='2.4951 alloy 75 (VDM) sheet 1.5 mm (or 2.4665 alloy X), laser-cut flat patterns, rolled + TIG, thermal-barrier coat optional'),
               air_split=SPLIT, phi_overall=phi_all, phi_primary=phi_pz, phi_secondary=phi_sz, T_primary_C=T_pz - 273.15, T_secondary_C=T_sz - 273.15,
               holes=holes, film=film,
               swirler=dict(type='axial, 12 flat 1.5 mm vanes at 45 deg slotted into turned hub 50 / tip 110 rings', velocity_m_s=V_sw, swirl_number=SN),
               injector=dict(holes=8, d_mm=d_gas * 1e3, dP_bar=0.30, gas_density=rho_gas, jet_m_s=V_gas,
                             type='central gas lance with 8 radial jets into the swirler exit (partially premixed diffusion flame), 1.4404 + 2.4665 tip'),
               loading=dict(theta=theta, eta_comb_est=eta_theta, residence_ms=t_res * 1e3, heat_release_MW_m3_atm=HRI),
               pattern_factor=dict(liner_exit=PF, at_nozzle_est=PF_plenum, T_peak_nozzle_inlet_C=T_peak - 273.15),
               wall=dict(T_max_est_C=T_wall - 273.15))
    return out


def liner_life(T_wall_C, T_ref_C=745.0, L_ref_h=70000.0, doubling_K=30.0):
    """oxidation + thermal-fatigue limited liner life (ESTIMATE): anchored at 70 kh for the 770 C design wall temperature
    (small uncooled-turbine industrial GT practice: HSI ~25-30 kh, overhaul ~50-60 kh at TIT 900-1000 C), halves every 30 K"""
    return L_ref_h * 2 ** ((T_ref_C - T_wall_C) / doubling_K)


def main():
    r770 = ec.D
    r850 = ec.offdesign(ec.T_DES, ec.TIT_PEAK)
    a, b = design(r770, 'TIT 770 C design'), design(r850, 'TIT 850 C peak')
    for x in (a, b):
        c, l, h = x['casing'], x['liner'], x['holes']
        print('%s: air %.3f kg/s at %.0f C / %.3f bar, fuel %.4f kg/s' % (x['case'], x['air_kg_s'], x['T3_C'], x['P3_bar'], x['fuel_kg_s']))
        print('  casing %s: D_ref %.0f mm, U_ref %.1f m/s, q_ref %.0f Pa, dP_liner %.1f kPa, PLF %.1f, annulus %.1f m/s' % (
            c['pipe'], c['D_ref_mm'], c['U_ref_m_s'], c['q_ref_Pa'], c['dP_liner_kPa'], c['PLF'], c['annulus_velocity_m_s']))
        print('  liner D %.0f x L %.0f mm (pz %.0f / sz %.0f / dz %.0f), V %.1f L' % (l['D_mm'], l['L_mm'], l['L_pz_mm'], l['L_sz_mm'], l['L_dz_mm'], l['volume_L']))
        print('  phi overall %.3f  primary %.3f (T %.0f C)  secondary %.3f (T %.0f C)' % (x['phi_overall'], x['phi_primary'], x['T_primary_C'], x['phi_secondary'], x['T_secondary_C']))
        for k, v in h.items():
            print('  %-9s %2d x d%.1f mm  J %.1f  penetration %d mm (%.2f R)' % (k, v['n'], v['d_mm'], v['J'], v['penetration_mm'], v['penetration_over_R']))
        print('  swirler %.0f m/s SN %.2f | injector 8 x d%.2f mm | theta %.2e eta %.4f | t_res %.1f ms | HRI %.0f MW/m3/atm' % (
            x['swirler']['velocity_m_s'], x['swirler']['swirl_number'], x['injector']['d_mm'], x['loading']['theta'], x['loading']['eta_comb_est'],
            x['loading']['residence_ms'], x['loading']['heat_release_MW_m3_atm']))
        print('  pattern factor liner %.3f, at nozzle %.3f -> peak %.0f C | liner wall ~%.0f C' % (
            x['pattern_factor']['liner_exit'], x['pattern_factor']['at_nozzle_est'], x['pattern_factor']['T_peak_nozzle_inlet_C'], x['wall']['T_max_est_C']))
    la, lb = liner_life(a['wall']['T_max_est_C']), liner_life(b['wall']['T_max_est_C'])
    tu = json.load(open(os.path.join(HERE, 'e_turbine.json')))
    lt = tu['life']
    vane_ox = lambda T: 80000.0 * 2 ** ((lt[0]['nozzle_vane']['T_metal_C'] - T) / 30.0)   # nozzle vane oxidation / TMF (est): 80 kh at the 770 C design metal T, halves every 30 K
    hot = dict(
        TIT_770=dict(liner_h=round(la), nozzle_oxidation_h=round(vane_ox(lt[0]['nozzle_vane']['T_metal_C'])),
                     nozzle_creep_h=round(lt[0]['nozzle_vane']['creep_life_h']), wheel_creep_h=round(min(lt[0]['wheel_rim']['creep_life_h'], lt[0]['wheel_blade_root']['creep_life_h']))),
        TIT_850=dict(liner_h=round(lb), nozzle_oxidation_h=round(vane_ox(lt[1]['nozzle_vane']['T_metal_C'])),
                     nozzle_creep_h=round(lt[1]['nozzle_vane']['creep_life_h']), wheel_creep_h=round(min(lt[1]['wheel_rim']['creep_life_h'], lt[1]['wheel_blade_root']['creep_life_h']))))
    for k in hot:
        hot[k]['hot_section_overhaul_h'] = min(v for kk, v in hot[k].items() if kk.endswith('_h'))
    hot['life_consumption_850_vs_770'] = round(hot['TIT_770']['hot_section_overhaul_h'] / hot['TIT_850']['hot_section_overhaul_h'], 1)
    hot['plan'] = ('inspection (borescope: liner, transition, nozzle, wheel LE) every 8,000 h; liner + transition exchange at ~%.0f kh at 770 C; '
                   'nozzle ring at ~%.0f kh; turbine wheel creep is not limiting at 770 C - wheel life is set by LCF (starts, est >= 10,000) and by the '
                   'supplier rating; every hour at 850 C counts as ~%.0f h at 770 C for the liner / nozzle'
                   % (hot['TIT_770']['liner_h'] / 1e3, min(hot['TIT_770']['nozzle_oxidation_h'], hot['TIT_770']['nozzle_creep_h']) / 1e3,
                      hot['life_consumption_850_vs_770']))
    print('hot-section life (est):', json.dumps(hot, indent=1))
    nox = dict(range_ppm_15O2=[60, 120], basis='diffusion-type primary zone at phi_pz %.2f (T_pz %.0f C), P3 4 bar, T3 212 C: comparable small single-can '
                                              'industrial GTs without water injection 80-150 ppm; low P3 / T3 lowers it (estimate, measure on the rig)'
               % (a['phi_primary'], a['T_primary_C']),
               v2='lean-premixed swirler (phi_pz ~0.55-0.6, premix tube, pilot) for <= 25 ppm: flashback / acoustics development - later version')
    res = dict(title='GR180 version E single can combustor (reverse flow, vertical, cool casing)', date='2026-10-23', script='sim/variant_e/e_combustor.py',
               design_770=a, peak_850=b, hot_section_life=hot, nox=nox,
               ignition=dict(igniter='industrial gas-engine spark plug in a cooled sleeve (M18x1.5 boss), high-energy capacitive coil (MOTORTECH DE / NGK JP plug)',
                             position='primary zone, 0.35 x L_pz from the dome, 30 deg off the top', light_off='motored by the PMG at ~20-25 % speed, phi_pz ~1 at light-off'),
               flame_detection='UV flame scanner on a sight tube through the dome (DURAG DE, Siemens QRA class) + 2 EGT thermocouples in the diffuser',
               removal='top flange DN350 PN10: lift the dome + injector + liner out upward (no engine strip); transition duct stays in the hot plenum (spigot + piston ring)')
    json.dump(res, open(os.path.join(HERE, 'e_combustor.json'), 'w'), indent=1, default=str)
    print('-> sim/variant_e/e_combustor.json')


if __name__ == '__main__':
    main()
