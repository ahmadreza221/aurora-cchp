# GR180 version D2 - AUX side skid (AX-6xx): welded RHS 60x40x3 frame on the -y side of the FR-110 base frame (bolted to its
# end cross members, 4 own AV mounts), perforated deck plate, vertical service-panel plate for the gas train (outer face),
# radiator fan shroud at the rear end (blows +x, away from the intake), AV mount envelopes.
# Layout numbers: cad/variant_d/d2a_layout.py.  ENG frame mm.
# Run first: LANG=en_US.UTF-8 freecadcmd cad/variant_d/d2a_skid.py -> cad_out/variant_d/D2/AUX/AX-*.step + d2a_skid_parts.json
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'cad', 'variant_d'))
from d2a_common import *

clear_aux({'AX'})
S = LY.SKID
x0, x1 = S['x']
y0, y1 = S['y']
zt = S['z_top']
zb = zt - S['h']
W = S['w']


def rhs(xa, xb, ya, yb, za, zb_, t=3.0, along='x'):
    o = box(xa, xb, ya, yb, za, zb_)
    if along == 'x':
        i = box(xa - 1, xb + 1, ya + t, yb - t, za + t, zb_ - t)
    else:
        i = box(xa + t, xb - t, ya - 1, yb + 1, za + t, zb_ - t)
    return o.cut(i)


parts = {}
fr = rhs(x0, x1, y0, y0 + W, zb, zt)                                      # outer rail
fr = fr.fuse(rhs(x0, x1, y1 - W, y1, zb, zt))                             # inner rail (next to FR-110)
for (xa, xb) in ((x0, x0 + W), (x1 - W, x1)):                            # end cross members (tray runs under the deck between them)
    fr = fr.fuse(rhs(xa, xb, y0 + W, y1 - W, zb, zt, along='y'))
for (x, y) in LY.AV:                                                      # 50 x 50 x 8 mount pads
    fr = fr.fuse(box(x - 25, x + 25, y - 25, y + 25, zb - 8, zb).cut(cyl((x, y, zb - 10), (x, y, zb + 1), 5.5)))
for (xa, xb) in LY.BRIDGES_X:                                             # bridge brackets to the FR-110 -y rail (y -110): the
    fr = fr.fuse(box(xa, xb, -160.0, -110.0, zb, zt).cut(box(xa + 3, xb - 3, -161.0, -109.0, zb + 3, zt - 3)))   # cross-member ends carry the lifting lugs
m_fr = (2 * (x1 - x0) + 2 * (y1 - y0 - 2 * W)) * 1e-3 * 4.35 + 4 * 0.16 + 2 * 0.5
parts['AX-610_Aux_Skid_Frame_RHS'] = (fr.removeSplitter(), m_fr, 'make',
    'RHS 60x40x3 S355 (EN 10219) like FR-110: 2 rails L725 + 2 end cross members, 4 mount pads 50x50x8, 2 bridge brackets (U 20x50x60) '
    'bolted (2 x M10 each) to the FR-110 -y rail at x -160 / 170 (the FR-110 cross-member ends carry the lifting lugs); MAG on a flat table, hot-dip galvanised', 'local fabrication shop')

dk = box(LY.DECK['x'][0], LY.DECK['x'][1], LY.DECK['y'][0], LY.DECK['y'][1], zt, zt + LY.DECK['t'])
for (hx, hy, hr) in LY.DECK_HOLES:
    dk = dk.cut(cyl((hx, hy, zt - 1), (hx, hy, zt + 5), hr))
m_dk = (LY.DECK['x'][1] - LY.DECK['x'][0]) * (LY.DECK['y'][1] - LY.DECK['y'][0]) * 3 * 7.85e-6 * 0.75
parts['AX-611_Deck_Plate_Perforated'] = (dk, m_dk, 'make',
    '3 mm S355 perforated deck (25 % open, ventilation + drainage), bolted to the AX-610 rails, line cut-outs', 'local laser shop')

pn = box(LY.PANEL['x'][0], LY.PANEL['x'][1], LY.PANEL['y'][0], LY.PANEL['y'][1], zt + LY.DECK['t'], LY.PANEL['z'][1])
pn = pn.cut(cyl((235.0, -345.0, 150.0), (235.0, -325.0, 150.0), 11.0))   # gas outlet pass-through
pn = pn.fuse(box(LY.PANEL['x'][0], LY.PANEL['x'][1], LY.PANEL['y'][0] + 3.0, LY.PANEL['y'][0] + 30.0, zt + LY.DECK['t'], zt + LY.DECK['t'] + 3.0))
m_pn = (LY.PANEL['x'][1] - LY.PANEL['x'][0]) * (LY.PANEL['z'][1] - zt) * 3 * 7.9e-6
parts['AX-612_Service_Panel_Plate'] = (pn.removeSplitter(), m_pn, 'make',
    '3 mm 1.4301 plate 455 x 423 with a 27 mm foot flange bolted to the deck; carries the gas train (rows on the -y face), '
    'instrument blocks and the radiator top edge; pass-through for the gas outlet', 'local laser + press brake')

R = LY.RADIATOR
F = LY.FAN
ry0, ry1 = R['y0'], R['y0'] + R['w']
rz0, rz1 = R['z0'], R['z0'] + R['h']
sh = box(F['x0'], F['x1'], ry0 - 3, ry1 + 3, rz0 - 3, rz1 + 3).cut(box(F['x0'] - 1, F['x1'] + 1, ry0, ry1, rz0, rz1))
sh = sh.fuse(box(F['x0'], F['x0'] + 2, ry0, ry1, rz0, rz1).cut(cyl((F['x0'] - 1, 0.5 * (ry0 + ry1), 0.5 * (rz0 + rz1)), (F['x0'] + 3, 0.5 * (ry0 + ry1), 0.5 * (rz0 + rz1)), F['r'] - 12)))
for yy in (ry0 + 20, ry1 - 20):                                           # feet to the deck
    sh = sh.fuse(box(F['x0'], R['x0'] + R['t'], yy - 15, yy + 15, zt + LY.DECK['t'], rz0 - 3))
parts['AX-613_Radiator_Fan_Shroud'] = (sh.removeSplitter(), 2.4, 'make',
    '1.5 mm Al 5754 shroud box 286 x 326 x 52 with a 310 mm fan ring, 2 feet to the deck; carries the radiator core and the fan',
    'local sheet-metal shop')

av = comp([cyl((x, y, -239.0), (x, y, zb - 8), 30.0) for (x, y) in LY.AV])
parts['AX-614_AV_Mounts_x4_env'] = (av, 4 * 0.45, 'buy',
    '4 x cylindrical rubber-metal AV mounts D60 x 45, M10, ~150 N each (same family as FR-140)', 'Trelleborg (SE), ContiTech (DE), Paulstra (FR)')

export(parts, 'SKID', dict(title='GR180 D2 AUX side skid', frame='ENG mm', layout='cad/variant_d/d2a_layout.py'), 'd2a_skid_parts.json')
