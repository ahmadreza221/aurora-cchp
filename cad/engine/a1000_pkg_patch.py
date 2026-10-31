"""Refresh fusion/A1000_pkg/pkg.json from the part lists of the detailed CAD (no FreeCAD needed): the entries of the rotor
and bearings (fusion/A1000_rotor), hot section (fusion/A1000_hot), combustion system (fusion/A1000_comb) and engine piping
(fusion/A1000_pipe, docs/08 sec. 19) are replaced by the current parts.json of each folder, with the same group mapping as
cad/engine/a1000_viewer_export.py (which writes the same entries when it regenerates the whole package). The envelopes
(compressor casing, inlet, exhaust, recuperator, gearbox, generator, lube module, skid) are kept as they are.
Run: python3 cad/engine/a1000_pkg_patch.py [pkg.json path]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FUS = os.path.join(ROOT, 'fusion')
PKG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FUS, 'A1000_pkg', 'pkg.json')

GMAP_ROTOR = dict(shaft='rotor', tie='rotor', drum='rotor', studs='rotor', blisk='turbine', pads='bearing', carrier='bearing',
                  cage='bearing', housing='bearing')
CGRP = dict(hot='comb', casing='casing', insulation='casing', aux='aux')
PIPE_RGB = [74, 140, 196]


def entries(folder, gmap):
    fn = os.path.join(FUS, folder, 'parts.json')
    if not os.path.exists(fn): return None
    out = []
    for name, q in json.load(open(fn))['parts'].items():
        e = dict(name=name, group=gmap(q['group']), inst=[0.0], material=q['material'], step='../%s/%s' % (folder, q['step']), dx=0.0)
        if 'mass_kg' in q: e['mass_kg'] = q['mass_kg']
        if 'desc' in q: e['desc'] = q['desc']
        out.append(e)
    return out


def main():
    pkg = json.load(open(PKG))
    n0 = len(pkg['parts'])
    for folder, gmap in (('A1000_rotor', lambda g: GMAP_ROTOR[g]), ('A1000_hot', lambda g: 'casing' if g == 'casing' else 'hot'),
                         ('A1000_comb', lambda g: CGRP[g]), ('A1000_pipe', lambda g: 'pipe')):
        new = entries(folder, gmap)
        if new is None: continue
        pre = '../%s/' % folder
        keep = [e for e in pkg['parts'] if not e.get('step', '').startswith(pre)]
        pkg['parts'] = keep + new
        print('%-12s %d entries' % (folder, len(new)))
    pkg['groups'].setdefault('pipe', dict(rgb=PIPE_RGB))
    json.dump(pkg, open(PKG, 'w'), indent=1)
    print('%s: %d -> %d parts' % (os.path.relpath(PKG, ROOT), n0, len(pkg['parts'])))


if __name__ == '__main__':
    main()
