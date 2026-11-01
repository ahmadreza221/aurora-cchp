#!/usr/bin/env python3
"""Copy the AURORA-1000 compressor impeller STEP pieces from the CAD output into fusion/A1000C/ and write
fusion/A1000C/parts.json (pattern counts, material densities, the expected impeller masses for the Fusion import check and
the rotor-dynamics lumps).

Run after the CAD:  python3 fusion/export_a1000_impellers.py [revision text]
Reads:  cad_out/engine/A1000/A1000_C<1|2>_<hub|blade|splitter>.step + A1000_C_parts.json
        (freecadcmd ... cad/engine/a1000_impeller.py --cad), sim/a1000_impeller_design.json
Pieces are in the rotor frame of sim/engine/a1000_rotordynamics.py (mm, X = engine axis from the gearbox coupling face).
The blade and the splitter are each stored at their own position (splitter half a pitch ahead of the blade): both are
patterned 13 x 360 deg / 13 from 0.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
OUT = os.path.join(HERE, 'A1000C')
PIECES = ['hub', 'blade', 'splitter']
Z = 13


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else 'rev 1'
    cad = json.load(open(os.path.join(SRC, 'A1000_C_parts.json')))
    des = json.load(open(os.path.join(ROOT, 'sim', 'a1000_impeller_design.json')))
    STAGES = {k: v['material'] for k, v in des['stages'].items()}
    os.makedirs(OUT, exist_ok=True)
    info, expected, rotor = {}, {}, {}
    for k, mat in STAGES.items():
        for p in PIECES:
            n = 'A1000_%s_%s' % (k, p)
            shutil.copyfile(os.path.join(SRC, n + '.step'), os.path.join(OUT, n + '.step'))
            c = cad[n]
            info[n] = dict(mass_kg=round(c['mass_kg'], 4), vol_cm3=round(c['vol_mm3'] / 1e3, 3), valid=c['valid'],
                           solids=c['solids'], density_g_cc=c['rho'] / 1e3)
        expected[k] = round(cad['A1000_%s_hub' % k]['mass_kg'] + Z * (cad['A1000_%s_blade' % k]['mass_kg'] +
                                                                    cad['A1000_%s_splitter' % k]['mass_kg']), 3)
        r = cad['A1000_%s_rotor' % k]
        rotor[k] = dict(m=round(r['m'], 3), x_cg=round(r['x_cg'], 2), Ip=round(r['Ip'], 5), Id=round(r['Id'], 5), x0=r['x0'],
                        L=r['L'], r2=r['r2'])
    st = des['stages']
    info['pattern'] = dict(Z=Z, axis='x', units='mm', revision=rev, materials=STAGES,
                           density_g_cc={k: st[k]['rho'] / 1e3 for k in STAGES},
                           D2_mm={k: round(2 * st[k]['geometry']['r2'], 1) for k in STAGES},
                           note='blade and splitter at their own angular positions, both patterned 13 x 360/13 deg from 0')
    info['expected'] = {'impeller%s_kg' % k[1]: v for k, v in expected.items()}
    info['rotor'] = rotor
    json.dump(info, open(os.path.join(OUT, 'parts.json'), 'w'), indent=1)
    print('fusion/A1000C: %d STEP pieces, expected %s' % (len(STAGES) * len(PIECES), info['expected']))


if __name__ == '__main__':
    main()
