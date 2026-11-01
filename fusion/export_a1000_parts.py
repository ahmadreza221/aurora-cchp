#!/usr/bin/env python3
"""Copy the AURORA-1000 turbine STEP pieces from the CAD output into fusion/A1000/ and write fusion/A1000/parts.json
(pattern counts, row positions and the expected row masses for the Fusion import check).

Run after the CAD:  python3 fusion/export_a1000_parts.py [revision text]
Reads:  cad_out/engine/A1000/A1000_<piece>.step + A1000_parts.json (cad/engine/a1000_turbine.py --cad),
        sim/a1000_turbine_design.json (vane / blade counts, row x positions)
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(ROOT, 'cad_out', 'engine', 'A1000')
OUT = os.path.join(HERE, 'A1000')
PIECES = ['A1000_R1_blade', 'A1000_R1_disc', 'A1000_R2_blade', 'A1000_R2_disc',
          'A1000_N1_vane', 'A1000_N1_rings', 'A1000_N2_vane', 'A1000_N2_rings']
RHO = 8.54                                                    # MAR-M247 g/cc


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else 'rev 5'
    cad = json.load(open(os.path.join(SRC, 'A1000_parts.json')))
    des = json.load(open(os.path.join(ROOT, 'sim', 'a1000_turbine_design.json')))
    os.makedirs(OUT, exist_ok=True)
    info = {}
    for p in PIECES:
        shutil.copyfile(os.path.join(SRC, p + '.step'), os.path.join(OUT, p + '.step'))
        c = cad[p]
        info[p] = dict(mass_kg=round(c['mass_kg'], 4), vol_cm3=round(c['vol_mm3'] / 1e3, 3), valid=c['valid'], solids=c['solids'])
    Z = {r: des[r]['Z'] for r in ('N1', 'R1', 'N2', 'R2')}
    row_kg = lambda base, piece, r: round(cad[base]['mass_kg'] + Z[r] * cad[piece]['mass_kg'], 2)
    info['pattern'] = dict(Z=Z, axis='x', units='mm', density_g_cc=RHO, alloy='MAR-M247', revision=rev,
                           rows={r: dict(x_le=round(des[r]['x_le'], 2), x_te=round(des[r]['x_te'], 2)) for r in Z},
                           note='blade / vane pieces at 0 deg; disc seam and NGV rings rotated by half a pitch '
                                '(cad/engine/a1000_turbine.py)')
    info['expected'] = dict(blisk1_kg=row_kg('A1000_R1_disc', 'A1000_R1_blade', 'R1'),
                            blisk2_kg=row_kg('A1000_R2_disc', 'A1000_R2_blade', 'R2'),
                            ngv1_kg=row_kg('A1000_N1_rings', 'A1000_N1_vane', 'N1'),
                            ngv2_kg=row_kg('A1000_N2_rings', 'A1000_N2_vane', 'N2'))
    json.dump(info, open(os.path.join(OUT, 'parts.json'), 'w'), indent=1)
    print('fusion/A1000: %d STEP pieces, counts %s, expected %s' % (len(PIECES), Z, info['expected']))


if __name__ == '__main__':
    main()
