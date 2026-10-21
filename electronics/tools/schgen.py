#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
schgen.py - netlist-driven KiCad 10 schematic + PCB-outline generator (GR180-CCHP).

A board is described in Python as a *spec* (parts + pin->net maps).  schgen turns
it into a real, fully wired, hierarchical KiCad 10 project:

  * root .kicad_sch with one hierarchical sheet symbol per Sheet
  * one child .kicad_sch per Sheet; every part placed on a 1.27 mm grid,
    every connected pin gets a 2.54 mm wire stub + global label at the stub
    end, every unused pin gets a no-connect flag
  * generated symbols (G(...)) written to symbols/<name>.kicad_sym and
    registered in the project sym-lib-table
  * PWR_FLAGs for power nets (automatic or explicit list)
  * <name>.kicad_pcb with Edge.Cuts outline, mounting holes, 2/4 layers

`build` then proves the result with kicad-cli: ERC (JSON), netlist export
(kicadxml) + round-trip comparison against the spec, PDF, BOM CSV, STEP of
the bare board.

Library use (in a board spec module):

    from schgen import Board, Sheet, P, R, C, L, D, G
    BOARD = Board(name='b1_ecu', title='GR180 B1 ECU', rev='0.2',
                  sheets=[Sheet('Power', parts=[...]), ...],
                  pcb=dict(w=220, h=160, holes='M3', hole_inset=4, layers=4))

CLI:
    python3 schgen.py build <spec.py> --out <dir>
    python3 schgen.py pins  <Lib:Symbol>        # pin table of a symbol
    python3 schgen.py find  <regex> [--lib L]   # search stock symbols

Python 3.8+, stdlib only.
"""
from __future__ import annotations

import copy
import csv
import datetime
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

__version__ = '1.0'

# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------
KICAD_APP = os.environ.get('KICAD_APP', '/Applications/KiCad/KiCad.app')
KICAD_CLI = os.environ.get('KICAD_CLI', os.path.join(KICAD_APP, 'Contents/MacOS/kicad-cli'))
STOCK_SYM_DIR = os.environ.get('KICAD_SYMBOL_DIR',
                               os.path.join(KICAD_APP, 'Contents/SharedSupport/symbols'))
STOCK_FP_DIR = os.environ.get('KICAD_FOOTPRINT_DIR',
                              os.path.join(KICAD_APP, 'Contents/SharedSupport/footprints'))

SCH_VERSION = 20260306      # what KiCad 10.0 eeschema writes
SYMLIB_VERSION = 20251024   # KiCad 10.0 symbol library format
PCB_VERSION = 20260206      # KiCad 10.0 pcbnew format
GENERATOR = 'schgen'
GEN_VERSION = '10.0'

GRID = 1.27                 # schematic connection grid (50 mil)
STUB = 2.54                 # wire stub length from pin end to label
FONT = 1.27                 # text size
CHAR_W = 1.05               # estimated stroke-font advance per char @1.27 mm
BLOCK_GAP = 5.08            # free space between placed blocks
MARGIN = 25.4               # page margin used by the placer
TITLE_BAND = 40.0           # keep-out band at the bottom (title block)

PAPERS = {'A4': (297.0, 210.0), 'A3': (420.0, 297.0), 'A2': (594.0, 420.0),
          'A1': (841.0, 594.0), 'A0': (1189.0, 841.0)}
PAPER_ORDER = ['A4', 'A3', 'A2', 'A1', 'A0']

_NS = uuid.UUID('9f6c1d2e-5b7a-4c3e-8f10-6a2b3c4d5e6f')


# KiCad's default ERC pin-conflict matrix (0 ok, 1 warning, 2 error), row/col order below
ERC_PIN_TYPES = ['input', 'output', 'bidirectional', 'tri_state', 'passive', 'free', 'unspecified',
                 'power_in', 'power_out', 'open_collector', 'open_emitter', 'no_connect']
ERC_DEFAULT_PIN_MAP = [[0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2], [0, 2, 0, 1, 0, 0, 1, 0, 2, 2, 2, 2],
                       [0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 2], [0, 1, 0, 0, 0, 0, 1, 1, 2, 1, 1, 2],
                       [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2],
                       [1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 2], [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 2],
                       [0, 2, 1, 2, 0, 0, 1, 0, 2, 2, 2, 2], [0, 2, 0, 1, 0, 0, 1, 0, 2, 0, 0, 2],
                       [0, 2, 1, 1, 0, 0, 1, 0, 2, 0, 0, 2], [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]]


class SpecError(Exception):
    """Raised for any inconsistency in a board spec."""


# --------------------------------------------------------------------------
# S-expressions
# --------------------------------------------------------------------------
class Sym(str):
    """A bare (unquoted) S-expression atom, e.g. kicad_sch, yes, power_in."""
    __slots__ = ()


YES, NO = Sym('yes'), Sym('no')
_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def _unescape(s):
    if '\\' not in s:
        return s
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            nx = s[i + 1]
            out.append({'n': '\n', 't': '\t', 'r': '\r'}.get(nx, nx))
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def sx_parse(text):
    """Parse one S-expression (the first top-level list) into nested lists.
    Bare atoms become Sym, quoted strings become str."""
    stack = [[]]
    pos, n = 0, len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == '':
                break
            raise ValueError('S-expression syntax error at offset %d: %r' % (pos, text[pos:pos + 40]))
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            if len(stack) < 2:
                raise ValueError('unbalanced ")" at offset %d' % pos)
            lst = stack.pop()
            stack[-1].append(lst)
            if len(stack) == 1:
                break
        elif m.group(3) is not None:
            stack[-1].append(_unescape(m.group(3)))
        else:
            stack[-1].append(Sym(m.group(4)))
    if len(stack) != 1 or not stack[0]:
        raise ValueError('incomplete S-expression')
    return stack[0][0]


def fmt(v):
    """Format a number the way KiCad does (max 4 decimals, no trailing zeros)."""
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, int):
        return str(v)
    s = '%.4f' % v
    s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '', '-') else s


def _atom(x):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    if isinstance(x, (int, float)):
        return fmt(x)
    if isinstance(x, str):
        return '"' + x.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    raise TypeError('cannot serialise %r' % (x,))


def _is_flat(node):
    return all(not isinstance(c, list) for c in node)


def sx_dump(node, ind=0):
    """Serialise nested lists with KiCad-like tab indentation."""
    if not isinstance(node, list):
        return _atom(node)
    if _is_flat(node):
        return '(' + ' '.join(_atom(c) for c in node) + ')'
    # short "simple" lists (only flat sub-lists) go on one line
    if all(not isinstance(c, list) or _is_flat(c) for c in node):
        one = '(' + ' '.join(sx_dump(c) for c in node) + ')'
        if len(one) <= 72 and node[0] not in ('symbol', 'property', 'pin', 'sheet', 'global_label',
                                               'wire', 'footprint', 'lib', 'pad', 'title_block'):
            return one
    head = []
    i = 0
    while i < len(node) and not isinstance(node[i], list):
        head.append(_atom(node[i]))
        i += 1
    t = '\t' * (ind + 1)
    body = ''.join('\n' + t + sx_dump(c, ind + 1) for c in node[i:])
    return '(' + ' '.join(head) + body + '\n' + '\t' * ind + ')'


def sx_find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def sx_findall(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def N(head, *items):
    """Build a list node with a bare head atom."""
    return [Sym(head)] + list(items)


def _xy(x, y):
    return N('xy', float(x), float(y))


def _uid(*parts):
    return str(uuid.uuid5(_NS, '/'.join(str(p) for p in parts)))


def _effects(justify=None, size=FONT, hide_in_effects=False):
    e = N('effects', N('font', N('size', size, size)))
    if justify:
        e.append([Sym('justify')] + [Sym(j) for j in justify.split()])
    if hide_in_effects:
        e.append(N('hide', YES))
    return e


def _prop(name, value, x, y, angle=0, hide=False, justify=None):
    """Schematic property in canonical KiCad 10 form."""
    p = N('property', name, value, N('at', round(float(x), 4), round(float(y), 4), angle))
    if hide:
        p.append(N('hide', YES))
    p += [N('show_name', NO), N('do_not_autoplace', NO), _effects(justify)]
    return p


def snap(v, g=GRID, up=False):
    k = v / g
    k = math.ceil(k - 1e-6) if up else round(k)
    return round(k * g, 4)


# --------------------------------------------------------------------------
# Library symbols
# --------------------------------------------------------------------------
class Pin:
    __slots__ = ('number', 'name', 'etype', 'shape', 'x', 'y', 'angle', 'length',
                 'unit', 'body', 'hidden', 'alts')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def outward(self):
        """Unit vector, in SCHEMATIC coordinates (y down), pointing away from
        the symbol body at the pin's connection point."""
        return {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}[self.angle]

    @property
    def side(self):
        return {0: 'L', 180: 'R', 270: 'T', 90: 'B'}[self.angle]

    def sch_point(self, ax, ay):
        return (round(ax + self.x, 4), round(ay - self.y, 4))

    def __repr__(self):
        return 'Pin(%s %s %s u%s)' % (self.number, self.name, self.etype, self.unit)


def norm_pin_name(s):
    """Strip KiCad overbar/sub/superscript markup: ~{RST} -> RST."""
    return re.sub(r'[~_^]\{([^}]*)\}', r'\1', s)


class LibSymbol:
    """A flattened library symbol (extends resolved) + parsed pin geometry."""

    def __init__(self, lib, name, node, source=None):
        self.lib, self.name, self.lib_id = lib, name, '%s:%s' % (lib, name)
        self.node = node
        self.source = source
        self.props = {}
        self.pins = []
        self.units = 1
        self.gfx = {}           # unit -> [x0, y0, x1, y1] in LIBRARY coords (y up)
        self.is_power = sx_find(node, 'power') is not None
        flags = {}
        for k in ('in_bom', 'on_board', 'exclude_from_sim', 'in_pos_files'):
            f = sx_find(node, k)
            flags[k] = (f[1] == 'yes') if f else (k != 'exclude_from_sim')
        self.flags = flags
        for p in sx_findall(node, 'property'):
            at = sx_find(p, 'at') or [None, 0, 0, 0]
            eff = sx_find(p, 'effects') or []
            hidden = (sx_find(p, 'hide') is not None and sx_find(p, 'hide')[1:2] != ['no']) or \
                (sx_find(eff, 'hide') is not None and sx_find(eff, 'hide')[1:2] != ['no']) or \
                ('hide' in [c for c in eff if not isinstance(c, list)])
            just = sx_find(eff, 'justify')
            self.props[p[1]] = dict(value=p[2], x=float(at[1]), y=float(at[2]),
                                    a=float(at[3]) if len(at) > 3 else 0.0,
                                    hidden=hidden, justify=' '.join(just[1:]) if just else None)
        for sub in sx_findall(node, 'symbol'):
            m = re.search(r'_(\d+)_(\d+)$', sub[1])
            if not m:
                continue
            unit, body = int(m.group(1)), int(m.group(2))
            self.units = max(self.units, unit)
            if body not in (0, 1):
                continue
            for g in sub[2:]:
                if not isinstance(g, list):
                    continue
                if g[0] == 'pin':
                    self._add_pin(g, unit, body)
                else:
                    self._add_gfx(g, unit)

    def _add_pin(self, g, unit, body):
        at = sx_find(g, 'at')
        ln = sx_find(g, 'length')
        nm = sx_find(g, 'name')
        nu = sx_find(g, 'number')
        hide = sx_find(g, 'hide')
        # KiCad >= 7: (hide yes) child; older libraries: bare `hide` atom in the pin header
        hidden = (hide is not None and hide[1:2] != ['no']) or any(c == 'hide' for c in g[1:4])
        self.pins.append(Pin(number=str(nu[1]) if nu else '', name=str(nm[1]) if nm else '',
                             etype=str(g[1]), shape=str(g[2]) if len(g) > 2 and not isinstance(g[2], list) else 'line',
                             x=float(at[1]), y=float(at[2]), angle=int(round(float(at[3]))) % 360,
                             length=float(ln[1]) if ln else 0.0, unit=unit, body=body,
                             hidden=bool(hidden), alts=[a[1] for a in sx_findall(g, 'alternate')]))

    def _add_gfx(self, g, unit):
        pts = []
        if g[0] == 'rectangle':
            for k in ('start', 'end'):
                q = sx_find(g, k)
                if q:
                    pts.append((float(q[1]), float(q[2])))
        elif g[0] in ('polyline', 'bezier'):
            pp = sx_find(g, 'pts')
            for q in (pp or [])[1:]:
                if isinstance(q, list) and q[0] == 'xy':
                    pts.append((float(q[1]), float(q[2])))
        elif g[0] == 'circle':
            c, r = sx_find(g, 'center'), sx_find(g, 'radius')
            if c and r:
                cx, cy, rr = float(c[1]), float(c[2]), float(r[1])
                pts += [(cx - rr, cy - rr), (cx + rr, cy + rr)]
        elif g[0] == 'arc':
            for k in ('start', 'mid', 'end'):
                q = sx_find(g, k)
                if q:
                    pts.append((float(q[1]), float(q[2])))
        elif g[0] in ('text', 'text_box'):
            q = sx_find(g, 'at') or sx_find(g, 'start')
            if q:
                pts.append((float(q[1]), float(q[2])))
        if not pts:
            return
        b = self.gfx.setdefault(unit, [1e9, 1e9, -1e9, -1e9])
        for x, y in pts:
            b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)

    def unit_pins(self, unit):
        return [p for p in self.pins if p.unit in (0, unit)]

    def unit_body_bbox(self, unit):
        """Body bbox of one unit in SCHEMATIC coords relative to the anchor."""
        bs = [self.gfx[u] for u in (0, unit) if u in self.gfx]
        if not bs:
            pts = [(p.x, p.y) for p in self.unit_pins(unit)] or [(0, 0)]
            bs = [[min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts), max(y for _, y in pts)]]
        x0 = min(b[0] for b in bs)
        x1 = max(b[2] for b in bs)
        y0 = min(b[1] for b in bs)
        y1 = max(b[3] for b in bs)
        return (x0, -y1, x1, -y0)

    def embed_node(self):
        n = copy.deepcopy(self.node)
        n[1] = self.lib_id
        return n


class SymbolLibrary:
    """One .kicad_sym file: raw nodes by name, flattening of `extends`."""

    def __init__(self, nick, path):
        self.nick, self.path = nick, path
        with open(path, encoding='utf-8') as f:
            root = sx_parse(f.read())
        self.raw = {s[1]: s for s in sx_findall(root, 'symbol')}
        self.cache = {}

    def names(self):
        return list(self.raw)

    def flatten(self, name, _depth=0):
        if name not in self.raw:
            raise SpecError('symbol %r not found in library %s (%s)' % (name, self.nick, self.path))
        node = self.raw[name]
        ext = sx_find(node, 'extends')
        if not ext:
            return copy.deepcopy(node)
        if _depth > 8:
            raise SpecError('extends chain too deep for %s:%s' % (self.nick, name))
        parent_name = ext[1]
        parent = self.flatten(parent_name, _depth + 1)
        dprops = {p[1]: p for p in sx_findall(node, 'property')}
        dother = {c[0]: c for c in node[2:] if isinstance(c, list)
                  and c[0] not in ('property', 'extends', 'symbol')}
        out = [Sym('symbol'), name]
        used = set()
        for c in parent[2:]:
            if not isinstance(c, list):
                out.append(c)
                continue
            if c[0] == 'property':
                if c[1] in dprops:
                    out.append(copy.deepcopy(dprops[c[1]]))
                    used.add(c[1])
                else:
                    out.append(c)
            elif c[0] == 'symbol':
                sub = copy.deepcopy(c)
                if sub[1].startswith(parent_name + '_'):
                    sub[1] = name + sub[1][len(parent_name):]
                out.append(sub)
            elif c[0] in dother:
                out.append(copy.deepcopy(dother.pop(c[0])))
            else:
                out.append(c)
        # derived-only properties go after the parent's properties
        last_prop = max([i for i, c in enumerate(out) if isinstance(c, list) and c[0] == 'property'] or [len(out) - 1])
        extra = [copy.deepcopy(p) for k, p in dprops.items() if k not in used]
        out[last_prop + 1:last_prop + 1] = extra
        for k, c in dother.items():
            out.insert(2, copy.deepcopy(c))
        return out

    def get(self, name):
        if name not in self.cache:
            self.cache[name] = LibSymbol(self.nick, name, self.flatten(name), self.path)
        return self.cache[name]


class SymbolResolver:
    """lib_id -> LibSymbol, from the stock library directory + generated symbols."""

    def __init__(self, sym_dir=STOCK_SYM_DIR, gen_lib=None, gen_symbols=()):
        self.sym_dir = sym_dir
        self.libs = {}
        self.gen_lib = gen_lib
        self.gen = {g.name: g for g in gen_symbols}
        self._gen_cache = {}

    def library(self, nick):
        if nick not in self.libs:
            path = os.path.join(self.sym_dir, nick + '.kicad_sym')
            if not os.path.isfile(path):
                raise SpecError('symbol library %r not found (%s)' % (nick, path))
            self.libs[nick] = SymbolLibrary(nick, path)
        return self.libs[nick]

    def get(self, lib_id):
        if isinstance(lib_id, GenSymbol):
            lib_id = '%s:%s' % (self.gen_lib, lib_id.name)
        if ':' not in lib_id:
            raise SpecError('lib_id %r must be "Library:Symbol"' % lib_id)
        nick, name = lib_id.split(':', 1)
        if nick in (self.gen_lib, 'gen') and name in self.gen:
            if name not in self._gen_cache:
                self._gen_cache[name] = LibSymbol(self.gen_lib, name, self.gen[name].node(), 'generated')
            return self._gen_cache[name]
        return self.library(nick).get(name)


# --------------------------------------------------------------------------
# Generated symbols
# --------------------------------------------------------------------------
ETYPES = {'in': 'input', 'input': 'input', 'i': 'input',
          'out': 'output', 'output': 'output', 'o': 'output',
          'io': 'bidirectional', 'bidir': 'bidirectional', 'bidirectional': 'bidirectional',
          'tri': 'tri_state', 'tri_state': 'tri_state',
          'pas': 'passive', 'passive': 'passive', 'p': 'passive',
          'pwr': 'power_in', 'pwr_in': 'power_in', 'power_in': 'power_in',
          'pwr_out': 'power_out', 'power_out': 'power_out',
          'oc': 'open_collector', 'open_collector': 'open_collector',
          'oe': 'open_emitter', 'open_emitter': 'open_emitter',
          'nc': 'no_connect', 'no_connect': 'no_connect',
          'free': 'free', 'unspecified': 'unspecified', 'unspec': 'unspecified'}
SIDES = {'l': 'L', 'left': 'L', 'r': 'R', 'right': 'R', 't': 'T', 'top': 'T', 'b': 'B', 'bottom': 'B'}


class GenSymbol:
    """A generated rectangular symbol for parts without a stock KiCad symbol."""

    def __init__(self, name, pins, ref='U', value=None, footprint='', datasheet='~',
                 description='', keywords='', pin_length=2.54):
        if not re.match(r'^[A-Za-z0-9_.+\-]+$', name):
            raise SpecError('generated symbol name %r: use [A-Za-z0-9_.+-] only' % name)
        self.name, self.ref, self.value = name, ref, value or name
        self.footprint, self.datasheet = footprint or '', datasheet or '~'
        self.description, self.keywords = description, keywords
        self.pin_length = pin_length
        self.sides = {'L': [], 'R': [], 'T': [], 'B': []}
        seen = set()
        for e in pins:
            e = tuple(e)
            if len(e) == 3:
                e = (e[0], e[1], 'passive', e[2])
            if len(e) != 4:
                raise SpecError('G(%s): pin entry %r must be (num, name, etype, side)' % (name, e))
            num, pname, et, side = e
            sd = SIDES.get(str(side).lower())
            if sd is None:
                raise SpecError('G(%s): bad side %r' % (name, side))
            if num is None:                       # spacer
                self.sides[sd].append(None)
                continue
            num = str(num)
            if num in seen:
                raise SpecError('G(%s): duplicate pin number %s' % (name, num))
            seen.add(num)
            et2 = ETYPES.get(str(et).lower())
            if et2 is None:
                raise SpecError('G(%s): bad electrical type %r for pin %s' % (name, et, num))
            self.sides[sd].append((num, str(pname or '~'), et2))

    def node(self):
        p, L = 2.54, self.pin_length
        S = self.sides

        def namew(lst):
            return max([len(norm_pin_name(e[1])) for e in lst if e and e[1] != '~'] or [0]) * CHAR_W

        nl, nr, nt, nb = (len(S[k]) for k in 'LRTB')
        W = max(namew(S['L']) + namew(S['R']) + 2 * 1.016 + 2.54, (max(nt, nb) + 1) * p, 10.16)
        W = math.ceil(W / (2 * p) - 1e-6) * 2 * p
        # vertical room for the (vertical) names of top/bottom pins, so they never
        # collide with the horizontal names of the side pins
        top_res = math.ceil((namew(S['T']) + 1.016 + 0.5) / p - 1e-6) * p if nt else 0.0
        bot_res = math.ceil((namew(S['B']) + 1.016 + 0.5) / p - 1e-6) * p if nb else 0.0
        H = max(top_res + bot_res + (max(nl, nr) + 1) * p, 5.08)
        H = math.ceil(H / (2 * p) - 1e-6) * 2 * p
        x0, x1, yt, yb = -W / 2, W / 2, H / 2, -H / 2
        ys = yt - top_res              # side pins start one pitch below this line
        u0 = N('symbol', self.name + '_0_1',
               N('rectangle', N('start', x0, yt), N('end', x1, yb),
                 N('stroke', N('width', 0.254), N('type', Sym('default'))),
                 N('fill', N('type', Sym('background')))))
        u1 = N('symbol', self.name + '_1_1')

        def pin(e, x, y, a):
            num, nm, et = e
            return N('pin', Sym(et), Sym('line'), N('at', round(x, 4), round(y, 4), a), N('length', L),
                     N('name', nm, _effects()), N('number', num, _effects()))

        for i, e in enumerate(S['L']):
            if e:
                u1.append(pin(e, x0 - L, ys - (i + 1) * p, 0))
        for i, e in enumerate(S['R']):
            if e:
                u1.append(pin(e, x1 + L, ys - (i + 1) * p, 180))
        for i, e in enumerate(S['T']):
            if e:
                u1.append(pin(e, x0 + (i + 1) * p, yt + L, 270))
        for i, e in enumerate(S['B']):
            if e:
                u1.append(pin(e, x0 + (i + 1) * p, yb - L, 90))

        def lprop(name, value, x, y, hide=False, justify=None):
            q = N('property', name, value, N('at', round(x, 4), round(y, 4), 0))
            if hide:
                q.append(N('hide', YES))
            q += [N('show_name', NO), N('do_not_autoplace', NO), _effects(justify)]
            return q

        top = yt + (L + 1.27 if nt else 1.27)
        bot = yb - (L + 1.27 if nb else 1.27)
        props = [lprop('Reference', self.ref, x0, top, justify='left bottom'),
                 lprop('Value', self.value, x0, bot, justify='left top'),
                 lprop('Footprint', self.footprint, 0, 0, hide=True),
                 lprop('Datasheet', self.datasheet, 0, 0, hide=True),
                 lprop('Description', self.description, 0, 0, hide=True)]
        if self.keywords:
            props.append(lprop('ki_keywords', self.keywords, 0, 0, hide=True))
        return N('symbol', self.name,
                 N('pin_names', N('offset', 1.016)),
                 N('exclude_from_sim', NO), N('in_bom', YES), N('on_board', YES), N('in_pos_files', YES),
                 N('duplicate_pin_numbers_are_jumpers', NO),
                 *props, u0, u1, N('embedded_fonts', NO))


def G(name, pins, ref='U', value=None, footprint='', datasheet='~', description='',
      keywords='', pin_length=2.54):
    """Generated symbol. pins = [(num, name, etype, side), ...];
    etype in input/output/bidirectional/tri_state/passive/power_in/power_out/
    open_collector/open_emitter/no_connect/free/unspecified (aliases in, out, io,
    pwr, pwr_out, oc, nc, pas); side in L/R/T/B.  (None, None, None, side) = spacer."""
    return GenSymbol(name, pins, ref=ref, value=value, footprint=footprint, datasheet=datasheet,
                     description=description, keywords=keywords, pin_length=pin_length)


# --------------------------------------------------------------------------
# Spec API
# --------------------------------------------------------------------------
NC = 'NC'


class Part:
    def __init__(self, ref, lib_id, value=None, footprint=None, pins=None, mpn=None, mfr=None,
                 lcsc=None, datasheet=None, dnp=False, default_nc=False, fields=None, description=None):
        if not isinstance(ref, str) or not re.match(r'^[A-Za-z_#]+[A-Za-z_]*\d+$', ref):
            raise SpecError('reference %r must look like U12 / R3 / J1' % (ref,))
        self.ref, self.lib_id, self.value = ref, lib_id, value
        self.footprint, self.pins = footprint, dict(pins or {})
        self.mpn, self.mfr, self.lcsc, self.datasheet = mpn, mfr, lcsc, datasheet
        self.dnp, self.default_nc = bool(dnp), bool(default_nc)
        self.fields = dict(fields or {})
        self.description = description

    def __repr__(self):
        return 'Part(%s, %s)' % (self.ref, self.lib_id)


def P(ref, lib_id, value=None, footprint=None, pins=None, mpn=None, mfr=None, lcsc=None,
      datasheet=None, dnp=False, default_nc=False, fields=None, description=None):
    """Generic part. lib_id = 'Lib:Symbol' or a G(...) object.
    pins = {pin number or pin name: net | 'NC'}; a name matching several pins
    (GND, VSS, ...) applies to all.  Strict: every pin must be assigned unless
    default_nc=True (then unmentioned pins get a no-connect flag)."""
    return Part(ref, lib_id, value, footprint, pins, mpn, mfr, lcsc, datasheet, dnp,
                default_nc, fields, description)


PASSIVE_SIZE = {'R': '0402', 'C': '0402', 'L': '0603', 'LED': '0603', 'D': 'SOD-123'}
_METRIC = {'0201': '0603Metric', '0402': '1005Metric', '0603': '1608Metric', '0805': '2012Metric',
           '1206': '3216Metric', '1210': '3225Metric', '1812': '4532Metric', '2010': '5025Metric',
           '2512': '6332Metric'}


def _chip_fp(lib, prefix, size):
    if ':' in size:
        return size
    if size not in _METRIC:
        raise SpecError('unknown chip size %r (known: %s)' % (size, ', '.join(_METRIC)))
    return '%s:%s_%s_%s' % (lib, prefix, size, _METRIC[size])


def R(ref, value, size=None, a=None, b=None, **kw):
    """Device:R. size '0402'/'0603'/... or a full footprint 'Lib:Name'. a->pin1, b->pin2."""
    fp = kw.pop('footprint', None) or _chip_fp('Resistor_SMD', 'R', size or PASSIVE_SIZE['R'])
    return P(ref, kw.pop('lib_id', 'Device:R'), value, fp, pins={'1': a, '2': b}, **kw)


def C(ref, value, size=None, a=None, b=None, **kw):
    """Device:C (use lib_id='Device:C_Polarized' for electrolytics: a=+, b=-)."""
    fp = kw.pop('footprint', None) or _chip_fp('Capacitor_SMD', 'C', size or PASSIVE_SIZE['C'])
    return P(ref, kw.pop('lib_id', 'Device:C'), value, fp, pins={'1': a, '2': b}, **kw)


def L(ref, value, size=None, a=None, b=None, **kw):
    """Device:L (or lib_id='Device:FerriteBead')."""
    fp = kw.pop('footprint', None) or _chip_fp('Inductor_SMD', 'L', size or PASSIVE_SIZE['L'])
    return P(ref, kw.pop('lib_id', 'Device:L'), value, fp, pins={'1': a, '2': b}, **kw)


def D(ref, value, size=None, k=None, a=None, kind='D', **kw):
    """Diode: kind 'D' | 'D_Schottky' | 'D_Zener' | 'D_TVS' | 'LED' (Device:<kind>).
    k = cathode net (pin 1), a = anode net (pin 2).  D_TVS (bidirectional): k->A1, a->A2.
    size: 'SOD-123', 'SMA', 'SMB', ... for diodes, '0603' etc. for LEDs, or a full footprint."""
    sz = size or (PASSIVE_SIZE['LED'] if kind == 'LED' else PASSIVE_SIZE['D'])
    if 'footprint' in kw:
        fp = kw.pop('footprint')
    elif ':' in sz:
        fp = sz
    elif kind == 'LED':
        fp = _chip_fp('LED_SMD', 'LED', sz)
    else:
        fp = 'Diode_SMD:D_%s' % sz
    return P(ref, kw.pop('lib_id', 'Device:%s' % kind), value, fp, pins={'1': k, '2': a}, **kw)


class Sheet:
    def __init__(self, name, parts=(), paper=None, file=None, title=None):
        if not re.match(r'^[A-Za-z0-9_\- ]+$', name):
            raise SpecError('sheet name %r: use letters, digits, _ - and space' % name)
        self.name, self.parts, self.paper = name, list(parts), paper
        self.file = file or re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_') + '.kicad_sch'
        self.title = title


class Board:
    def __init__(self, name, title=None, rev='0.1', company='GR180-CCHP', paper='A3', sheets=(),
                 pcb=None, power_flags='auto', symbols=(), date=None, comments=(),
                 root_paper='A4', erc_rules=None, erc_pin_map=None):
        if not re.match(r'^[A-Za-z0-9_\-]+$', name):
            raise SpecError('board name %r: use [A-Za-z0-9_-]' % name)
        self.name, self.title, self.rev, self.company = name, title or name, rev, company
        self.paper, self.root_paper = paper, root_paper
        self.sheets = list(sheets)
        self.pcb = dict(pcb or {})
        self.power_flags = power_flags
        self.symbols = list(symbols)
        self.date = date or datetime.date.today().isoformat()
        self.comments = list(comments)
        self.erc_rules = dict(erc_rules or {})
        for k, v in self.erc_rules.items():
            if v not in ('error', 'warning', 'ignore'):
                raise SpecError('erc_rules[%r] must be error/warning/ignore, not %r' % (k, v))
        self.erc_pin_map = None
        if erc_pin_map:
            lvl = {'ok': 0, 'warning': 1, 'error': 2}
            pm = [row[:] for row in ERC_DEFAULT_PIN_MAP]
            for (a, b2), v in dict(erc_pin_map).items():
                if a not in ERC_PIN_TYPES or b2 not in ERC_PIN_TYPES or v not in lvl:
                    raise SpecError('erc_pin_map key %r / value %r invalid (types %s; ok/warning/error)'
                                    % ((a, b2), v, ERC_PIN_TYPES))
                i, j = ERC_PIN_TYPES.index(a), ERC_PIN_TYPES.index(b2)
                pm[i][j] = pm[j][i] = lvl[v]
            self.erc_pin_map = pm
        names = [s.name for s in self.sheets]
        if len(set(names)) != len(names):
            raise SpecError('duplicate sheet names')
        files = [s.file for s in self.sheets]
        if len(set(files)) != len(files) or (name + '.kicad_sch') in files:
            raise SpecError('sheet file names collide: %s' % files)

    def all_parts(self):
        for s in self.sheets:
            for p in s.parts:
                yield s, p


# --------------------------------------------------------------------------
# Resolution: parts -> pins -> nets
# --------------------------------------------------------------------------
_BUS_RE = re.compile(r'\[\d+\.\.\d+\]|(?<!~)\{')


def _check_net_name(net, ref):
    if not isinstance(net, str) or not net.strip() or net != net.strip():
        raise SpecError('%s: bad net name %r' % (ref, net))
    if _BUS_RE.search(net):
        raise SpecError('%s: net %r looks like a bus (x[a..b] / {..}); not supported' % (ref, net))
    if any(c in net for c in '\n\t\r'):
        raise SpecError('%s: control characters in net name %r' % (ref, net))


class ResolvedPart:
    def __init__(self, sheet, part, sym):
        self.sheet, self.part, self.sym = sheet, part, sym
        self.assign = {}        # id(Pin) -> net name or NC
        self.auto_nc = set()    # id(Pin) of library no_connect pins NC'd automatically

    @property
    def ref(self):
        return self.part.ref


def resolve_part(sheet, part, resolver, warnings):
    sym = resolver.get(part.lib_id)
    if sym.is_power:
        raise SpecError('%s: %s is a power symbol; use nets (global labels) instead' % (part.ref, sym.lib_id))
    rp = ResolvedPart(sheet, part, sym)
    pins = sym.pins
    by_num, by_name, by_norm = {}, {}, {}
    for p in pins:
        by_num.setdefault(p.number, []).append(p)
        by_name.setdefault(p.name, []).append(p)
        by_norm.setdefault(norm_pin_name(p.name), []).append(p)
    for key, net in part.pins.items():
        k = str(key)
        if k in by_num:
            targets = by_num[k]
        elif k in by_name and k != '~':
            targets = by_name[k]
        elif norm_pin_name(k) in by_norm and k != '~':
            targets = by_norm[norm_pin_name(k)]
        else:
            avail = ', '.join(sorted({'%s/%s' % (p.number, p.name) for p in pins}, key=_natkey))
            raise SpecError('%s (%s): no pin with number or name %r. Pins: %s' % (part.ref, sym.lib_id, k, avail))
        if net is None:
            raise SpecError('%s: pin %r mapped to None (use a net name or "NC")' % (part.ref, k))
        val = NC if str(net).upper() == 'NC' else net
        if val != NC:
            _check_net_name(val, part.ref)
        for p in targets:
            old = rp.assign.get(id(p))
            if old is not None and old != val:
                raise SpecError('%s: pin %s (%s) assigned twice: %r and %r' % (part.ref, p.number, p.name, old, val))
            rp.assign[id(p)] = val
    missing = []
    for p in pins:
        if id(p) in rp.assign:
            if p.etype == 'no_connect' and rp.assign[id(p)] != NC:
                warnings.append('%s: pin %s (%s) is type no_connect in the library but mapped to %s'
                                % (part.ref, p.number, p.name, rp.assign[id(p)]))
            continue
        if p.etype == 'no_connect':
            rp.assign[id(p)] = NC
            rp.auto_nc.add(id(p))
        elif part.default_nc:
            rp.assign[id(p)] = NC
        else:
            missing.append(p)
    if missing:
        raise SpecError('%s (%s): %d pin(s) not assigned (strict mode; map them, use "NC", or default_nc=True): %s'
                        % (part.ref, sym.lib_id, len(missing),
                           ', '.join('%s/%s' % (p.number, p.name) for p in sorted(missing, key=lambda q: _natkey(q.number)))))
    # stacked pins (same unit, same location) must agree
    for u in range(1, sym.units + 1):
        loc = {}
        for p in sym.unit_pins(u):
            loc.setdefault((p.x, p.y), []).append(p)
        for (x, y), grp in loc.items():
            vals = {rp.assign[id(p)] for p in grp}
            if len(vals) > 1:
                raise SpecError('%s: stacked pins %s at the same location get different nets %s'
                                % (part.ref, [q.number for q in grp], sorted(vals)))
    # hidden pins: fine when stacked under a visible pin (STM32 VSS, connector GND);
    # a lone hidden pin is still wired/NC-flagged at its location, but warn.
    visible = [q for q in pins if not q.hidden]
    for p in pins:
        if not p.hidden:
            continue
        # units overlap when equal or when either pin is common to all units (unit 0)
        stacked = any(q.x == p.x and q.y == p.y and (q.unit == p.unit or 0 in (q.unit, p.unit))
                      for q in visible)
        if not stacked and rp.assign[id(p)] != NC:
            warnings.append('%s: pin %s (%s) is hidden in the library symbol; wired anyway'
                            % (part.ref, p.number, p.name))
        if not stacked and p.etype == 'power_in' and rp.assign[id(p)] != p.name:
            warnings.append('%s: hidden power_in pin %s (%s) implicitly joins global net %r in KiCad'
                            % (part.ref, p.number, p.name, p.name))
    return rp


def _natkey(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', str(s))]


# --------------------------------------------------------------------------
# Placement
# --------------------------------------------------------------------------
def _label_len(net):
    return len(net) * CHAR_W + 3.6


class Block:
    """One placed symbol unit (or a PWR_FLAG) with wires/labels/NC markers."""

    def __init__(self, rp, sym, unit, ref, value, flag_net=None):
        self.rp, self.sym, self.unit, self.ref, self.value = rp, sym, unit, ref, value
        self.flag_net = flag_net
        self.conns = []         # (px, py, dx, dy, net)   relative to anchor, sch coords
        self.ncs = []           # (px, py)
        pins = sym.unit_pins(unit)
        groups = {}
        for p in pins:
            groups.setdefault((p.x, -p.y), []).append(p)
        for pt, grp in groups.items():
            p = next((q for q in grp if not q.hidden), grp[0])
            net = flag_net if flag_net else rp.assign[id(p)]
            if net == NC:
                # library no_connect-type pins need no marker (ERC ignores them)
                if not all(q.etype == 'no_connect' for q in grp):
                    self.ncs.append(pt)
            else:
                dx, dy = p.outward
                self.conns.append((pt[0], pt[1], dx, dy, net))
        bx0, by0, bx1, by1 = sym.unit_body_bbox(unit)
        self.body = (bx0, by0, bx1, by1)
        xs, ys = [bx0, bx1], [by0, by1]
        for p in pins:
            xs.append(p.x)
            ys.append(-p.y)
        for px, py, dx, dy, net in self.conns:
            ex, ey = px + dx * STUB, py + dy * STUB
            ll = _label_len(net)
            if dx:
                xs += [ex + dx * ll]
                ys += [ey - 1.6, ey + 1.6]
            else:
                ys += [ey + dy * ll]
                xs += [ex - 1.6, ex + 1.6]
        for px, py in self.ncs:
            xs += [px - 1, px + 1]
            ys += [py - 1, py + 1]
        self.pb = (min(xs), min(ys), max(xs), max(ys))
        self.fields = self._place_fields()
        for (_, txt, fx, fy, just) in self.fields:
            w = len(txt) * CHAR_W
            if just == 'center':
                xs += [fx - w / 2, fx + w / 2]
            elif 'right' in just:
                xs += [fx - w, fx]
            else:
                xs += [fx, fx + w]
            if 'bottom' in just:
                ys += [fy - 1.8, fy]
            elif 'top' in just:
                ys += [fy, fy + 1.8]
            else:
                ys += [fy - 0.9, fy + 0.9]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.w = self.bbox[2] - self.bbox[0]
        self.h = self.bbox[3] - self.bbox[1]
        self.anchor = None

    def _place_fields(self):
        """Simple field auto-placement: Reference/Value next to the body on a
        side without wired pins; else outside the pin/label bbox."""
        if self.flag_net:
            v = self.sym.props.get('Value', {'x': 0, 'y': 0})
            return [('Value', self.value, v['x'], -v['y'], 'center')]
        ref = self.ref
        val = self.value or ''
        dirs = {(dx, dy) for (_, _, dx, dy, _) in self.conns}
        bx0, by0, bx1, by1 = self.body
        cy = (by0 + by1) / 2
        cx = bx0
        out = []
        # pins that are present on a side (even NC) also count as occupied for text
        occ = set(dirs)
        for p in self.sym.unit_pins(self.unit):
            occ.add(p.outward)
        if (1, 0) not in occ:
            x = max(bx1, max([p.x for p in self.sym.unit_pins(self.unit)] or [bx1])) + 1.27
            out = [('Reference', ref, x, cy - 0.635, 'left bottom'), ('Value', val, x, cy + 0.635, 'left top')]
        elif (-1, 0) not in occ:
            x = min(bx0, min([p.x for p in self.sym.unit_pins(self.unit)] or [bx0])) - 1.27
            out = [('Reference', ref, x, cy - 0.635, 'right bottom'), ('Value', val, x, cy + 0.635, 'right top')]
        elif (0, -1) not in occ:
            out = [('Reference', ref, cx, by0 - 1.27 - 2.0, 'left bottom'), ('Value', val, cx, by0 - 1.27, 'left bottom')]
        elif (0, 1) not in occ:
            out = [('Reference', ref, cx, by1 + 1.27, 'left top'), ('Value', val, cx, by1 + 1.27 + 2.0, 'left top')]
        else:
            x0, y0, x1, y1 = self.pb
            out = [('Reference', ref, x0, y0 - 1.27, 'left bottom'), ('Value', val, x0, y1 + 1.27, 'left top')]
        return [(n, t, snap(x, 0.635), snap(y, 0.635), j) for (n, t, x, y, j) in out]


def pack_blocks(blocks, W, H):
    """Column-stacking shelf packer.  Returns (fits, used_w, used_h)."""
    x_lim, y_lim = W - MARGIN, H - TITLE_BAND - 10.0
    x, row_y, row_h = MARGIN, MARGIN, 0.0
    col = None
    max_x = MARGIN
    for b in blocks:
        w, h = b.w + BLOCK_GAP, b.h + BLOCK_GAP
        if col is not None and col['used'] + h <= row_h + 1e-6 and col['x'] + max(col['w'], w) <= x_lim:
            px, py = col['x'], row_y + col['used']
            col['used'] += h
            col['w'] = max(col['w'], w)
        else:
            if col is not None:
                x = col['x'] + col['w']
            if x + w > x_lim and x > MARGIN:
                row_y += row_h
                x, row_h = MARGIN, 0.0
            col = {'x': x, 'w': w, 'used': h}
            row_h = max(row_h, h)
            px, py = x, row_y
        b.anchor = (snap(px - b.bbox[0], up=True), snap(py - b.bbox[1], up=True))
        max_x = max(max_x, px + w)
    used_h = row_y + row_h
    return (max_x <= x_lim + 1e-6 and used_h <= y_lim + 1e-6), max_x, used_h


# --------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------
class Writer:
    def __init__(self, board, out_dir, resolver=None):
        self.b = board
        self.out = os.path.abspath(out_dir)
        self.resolver = resolver or SymbolResolver(gen_lib=board.name, gen_symbols=self._collect_gen())
        self.warnings = []
        self.root_uuid = _uid(board.name, 'root')
        self.rparts = []
        self.nets = {}          # net -> set((ref, pin_number))
        self.nc_pins = set()    # (ref, pin_number)
        self.etypes = {}        # net -> set(etype)
        self.sheet_blocks = {}  # sheet name -> [Block]
        self.sheet_paper = {}
        self.flag_nets = []
        self.files = []

    def _collect_gen(self):
        gens = {g.name: g for g in self.b.symbols}
        for _, p in self.b.all_parts():
            if isinstance(p.lib_id, GenSymbol):
                g0 = gens.get(p.lib_id.name)
                if g0 is not None and g0 is not p.lib_id:
                    raise SpecError('two different generated symbols named %s' % p.lib_id.name)
                gens[p.lib_id.name] = p.lib_id
        self.gen_symbols = list(gens.values())
        return self.gen_symbols

    # ---- resolve ---------------------------------------------------------
    def resolve(self):
        refs = {}
        for sh, p in self.b.all_parts():
            if p.ref in refs:
                raise SpecError('duplicate reference %s (sheets %s and %s)' % (p.ref, refs[p.ref], sh.name))
            refs[p.ref] = sh.name
            rp = resolve_part(sh, p, self.resolver, self.warnings)
            self.rparts.append(rp)
            for pin in rp.sym.pins:
                net = rp.assign[id(pin)]
                if net == NC:
                    self.nc_pins.add((p.ref, pin.number))
                else:
                    self.nets.setdefault(net, set()).add((p.ref, pin.number))
                    self.etypes.setdefault(net, set()).add(pin.etype)
        if not self.rparts:
            raise SpecError('board has no parts')
        for net, nodes in sorted(self.nets.items()):
            if len(nodes) < 2:
                self.warnings.append('net %r has a single node %s (dangling)' % (net, sorted(nodes)))
        # power flags
        pf = self.b.power_flags
        if pf == 'auto' or pf is True:
            self.flag_nets = sorted(n for n, t in self.etypes.items()
                                    if 'power_in' in t and 'power_out' not in t)
        elif pf:
            self.flag_nets = list(pf)
            for n in self.flag_nets:
                if n not in self.nets:
                    raise SpecError('power_flags: net %r not used by any pin' % n)
                if 'power_out' in self.etypes.get(n, ()):
                    self.warnings.append('power flag on %r which already has a power_out pin '
                                         '(ERC will report power_out vs power_out)' % n)
        else:
            self.flag_nets = []

    # ---- layout ----------------------------------------------------------
    def layout(self):
        flag_sym = self.resolver.get('power:PWR_FLAG') if self.flag_nets else None
        flag_sheet = None
        if self.flag_nets:     # PWR_FLAGs go on the sheet named "Power", else on the first sheet
            flag_sheet = next((s for s in self.b.sheets if s.name.lower() == 'power'), self.b.sheets[0])
        for sh in self.b.sheets:
            blocks = []
            for rp in [r for r in self.rparts if r.sheet is sh]:
                p = rp.part
                val = p.value if p.value is not None else rp.sym.props.get('Value', {}).get('value', '')
                for u in range(1, rp.sym.units + 1):
                    blocks.append(Block(rp, rp.sym, u, p.ref, val))
            if sh is flag_sheet:
                for i, n in enumerate(self.flag_nets):
                    blocks.append(Block(None, flag_sym, 1, '#FLG%02d' % (i + 1), 'PWR_FLAG', flag_net=n))
            want = sh.paper or self.b.paper or 'A3'
            order = PAPER_ORDER[PAPER_ORDER.index(want):] if want in PAPER_ORDER else [want]
            if want == 'auto':
                order = PAPER_ORDER
            for paper in order:
                if paper not in PAPERS:
                    raise SpecError('unknown paper %r' % paper)
                fits, _, _ = pack_blocks(blocks, *PAPERS[paper])
                if fits:
                    break
            else:
                self.warnings.append('sheet %s does not fit even on %s; content overflows the frame' % (sh.name, order[-1]))
            if paper != want and want != 'auto':
                self.warnings.append('sheet %s: content does not fit on %s, using %s' % (sh.name, want, paper))
            self.sheet_blocks[sh.name] = blocks
            self.sheet_paper[sh.name] = paper

    # ---- emit ------------------------------------------------------------
    def _title_block(self, subtitle=None):
        tb = N('title_block', N('title', self.b.title + (' - ' + subtitle if subtitle else '')),
               N('date', self.b.date), N('rev', self.b.rev), N('company', self.b.company))
        comments = list(self.b.comments)
        comments.append('Generated by schgen %s from a Python board spec - do not hand-edit, edit the spec.' % __version__)
        for i, c in enumerate(comments[:9]):
            tb.append(N('comment', i + 1, c))
        return tb

    def _sheet_file(self, sh, page):
        sheet_uuid = _uid(self.b.name, 'sheet', sh.name)
        path = '/%s/%s' % (self.root_uuid, sheet_uuid)
        blocks = self.sheet_blocks[sh.name]
        doc = N('kicad_sch', N('version', SCH_VERSION), N('generator', GENERATOR),
                N('generator_version', GEN_VERSION), N('uuid', _uid(self.b.name, 'file', sh.file)),
                N('paper', self.sheet_paper[sh.name]), self._title_block(sh.title or sh.name))
        libs = N('lib_symbols')
        seen = set()
        for bl in blocks:
            if bl.sym.lib_id not in seen:
                seen.add(bl.sym.lib_id)
                libs.append(bl.sym.embed_node())
        doc.append(libs)
        items = []
        for bl in blocks:
            ax, ay = bl.anchor
            key = (bl.ref, bl.unit, bl.flag_net or '')
            for i, (px, py, dx, dy, net) in enumerate(bl.conns):
                x1, y1 = round(ax + px, 4), round(ay + py, 4)
                x2, y2 = round(x1 + dx * STUB, 4), round(y1 + dy * STUB, 4)
                items.append(N('wire', N('pts', _xy(x1, y1), _xy(x2, y2)),
                               N('stroke', N('width', 0), N('type', Sym('default'))),
                               N('uuid', _uid(self.b.name, 'w', sh.name, *key, i))))
                ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
                just = 'left' if ang in (0, 90) else 'right'
                items.append(N('global_label', net, N('shape', Sym('passive')),
                               N('at', x2, y2, ang), N('fields_autoplaced', YES),
                               _effects(just), N('uuid', _uid(self.b.name, 'gl', sh.name, *key, i)),
                               _prop('Intersheetrefs', '${INTERSHEET_REFS}', x2, y2, 0, hide=True, justify=just)))
            for i, (px, py) in enumerate(bl.ncs):
                items.append(N('no_connect', N('at', round(ax + px, 4), round(ay + py, 4)),
                               N('uuid', _uid(self.b.name, 'nc', sh.name, *key, i))))
            items.append(self._symbol_node(bl, path, sh))
        doc += items
        doc.append(N('embedded_fonts', NO))
        return doc

    def _symbol_node(self, bl, path, sh):
        ax, ay = bl.anchor
        sym = bl.sym
        if bl.flag_net:
            part = None
            dnp = False
        else:
            part = bl.rp.part
            dnp = part.dnp
        node = N('symbol', N('lib_id', sym.lib_id), N('at', ax, ay, 0), N('unit', bl.unit),
                 N('body_style', 1),
                 N('exclude_from_sim', YES if sym.flags['exclude_from_sim'] else NO),
                 N('in_bom', YES if sym.flags['in_bom'] else NO),
                 N('on_board', YES if sym.flags['on_board'] else NO),
                 N('in_pos_files', YES if sym.flags['in_pos_files'] else NO),
                 N('dnp', YES if dnp else NO),
                 N('uuid', _uid(self.b.name, 'sym', bl.ref, bl.unit, bl.flag_net or '')))
        lp = sym.props
        if part is None:
            r = lp['Reference']
            v = lp['Value']
            node.append(_prop('Reference', bl.ref, ax + r['x'], ay - r['y'], 0, hide=True))
            node.append(_prop('Value', 'PWR_FLAG', ax + v['x'], ay - v['y'], 0, hide=False))
            node.append(_prop('Footprint', '', ax, ay, 0, hide=True))
            node.append(_prop('Datasheet', '', ax, ay, 0, hide=True))
            node.append(_prop('Description', lp.get('Description', {}).get('value', ''), ax, ay, 0, hide=True))
        else:
            fpos = {n: (x, y, j) for (n, _, x, y, j) in bl.fields}
            fp = part.footprint if part.footprint is not None else lp.get('Footprint', {}).get('value', '')
            ds = part.datasheet if part.datasheet is not None else lp.get('Datasheet', {}).get('value', '~')
            desc = part.description if part.description is not None else lp.get('Description', {}).get('value', '')
            for name, val in (('Reference', part.ref), ('Value', bl.value)):
                x, y, j = fpos[name]
                node.append(_prop(name, val, ax + x, ay + y, 0, hide=False, justify=j))
            node.append(_prop('Footprint', fp or '', ax, ay, 0, hide=True))
            node.append(_prop('Datasheet', ds or '~', ax, ay, 0, hide=True))
            node.append(_prop('Description', desc or '', ax, ay, 0, hide=True))
            node.append(_prop('MPN', part.mpn or '', ax, ay, 0, hide=True))
            node.append(_prop('Manufacturer', part.mfr or '', ax, ay, 0, hide=True))
            node.append(_prop('LCSC', part.lcsc or '', ax, ay, 0, hide=True))
            for k, v in part.fields.items():
                node.append(_prop(str(k), str(v), ax, ay, 0, hide=True))
        seen_nums = set()
        for p in sym.pins:           # KiCad lists all pins of the symbol in every unit instance
            if p.number in seen_nums:
                continue
            seen_nums.add(p.number)
            node.append(N('pin', p.number, N('uuid', _uid(self.b.name, 'pin', bl.ref, bl.unit, p.number, p.name))))
        node.append(N('instances', N('project', self.b.name,
                                     N('path', path, N('reference', bl.ref), N('unit', bl.unit)))))
        return node

    def _root_file(self):
        doc = N('kicad_sch', N('version', SCH_VERSION), N('generator', GENERATOR),
                N('generator_version', GEN_VERSION), N('uuid', self.root_uuid),
                N('paper', self.b.root_paper), self._title_block(), N('lib_symbols'))
        W, H = PAPERS.get(self.b.root_paper, (297, 210))
        bw, bh, gx, gy = 45.72, 15.24, 20.32, 20.32
        per_row = max(1, int((W - 2 * MARGIN + gx) // (bw + gx)))
        for i, sh in enumerate(self.b.sheets):
            x = MARGIN + (i % per_row) * (bw + gx)
            y = MARGIN + 10.16 + (i // per_row) * (bh + gy)
            x, y = snap(x), snap(y)
            su = _uid(self.b.name, 'sheet', sh.name)
            nparts = sum(1 for r in self.rparts if r.sheet is sh)
            doc.append(N('sheet', N('at', x, y), N('size', bw, bh),
                         N('exclude_from_sim', NO), N('in_bom', YES), N('on_board', YES), N('dnp', NO),
                         N('fields_autoplaced', YES),
                         N('stroke', N('width', 0.1524), N('type', Sym('solid'))),
                         N('fill', N('color', 0, 0, 0, 0.0)),
                         N('uuid', su),
                         _prop('Sheetname', sh.name, x, round(y - 0.7116, 4), 0, justify='left bottom'),
                         _prop('Sheetfile', sh.file, x, round(y + bh + 0.5946, 4), 0, justify='left top'),
                         N('instances', N('project', self.b.name,
                                          N('path', '/' + self.root_uuid, N('page', str(i + 2)))))))
            doc.append(N('text', '%d parts' % nparts, N('exclude_from_sim', NO),
                         N('at', snap(x + 1.27), snap(y + bh / 2), 0),
                         _effects('left'), N('uuid', _uid(self.b.name, 'sheettext', sh.name))))
        doc.append(N('sheet_instances', N('path', '/', N('page', '1'))))
        doc.append(N('embedded_fonts', NO))
        return doc

    def _gen_lib(self):
        doc = N('kicad_symbol_lib', N('version', SYMLIB_VERSION), N('generator', GENERATOR),
                N('generator_version', GEN_VERSION))
        for g in self.gen_symbols:
            doc.append(g.node())
        return doc

    def _project_json(self):
        pages = [[self.root_uuid, 'Root']] + [[_uid(self.b.name, 'sheet', s.name), s.name] for s in self.b.sheets]
        return {
            'board': {'design_settings': {'defaults': {}, 'diff_pair_dimensions': [], 'drc_exclusions': [],
                                          'rules': {}, 'track_widths': [], 'via_dimensions': []}},
            'boards': [],
            'libraries': {'pinned_footprint_libs': [], 'pinned_symbol_libs': []},
            'meta': {'filename': self.b.name + '.kicad_pro', 'version': 3},
            'net_settings': {'classes': [{'name': 'Default', 'priority': 2147483647, 'clearance': 0.2,
                                          'track_width': 0.2, 'via_diameter': 0.6, 'via_drill': 0.3,
                                          'wire_width': 6, 'bus_width': 12, 'line_style': 0,
                                          'schematic_color': 'rgba(0, 0, 0, 0.000)',
                                          'pcb_color': 'rgba(0, 0, 0, 0.000)'}],
                             'meta': {'version': 4}},
            'erc': dict({'erc_exclusions': [], 'meta': {'version': 0}, 'rule_severities': dict(self.b.erc_rules)},
                        **({'pin_map': self.b.erc_pin_map} if self.b.erc_pin_map else {})),
            'pcbnew': {'page_layout_descr_file': ''},
            'schematic': {'meta': {'version': 1}},
            'sheets': pages,
            'text_variables': {},
        }

    def write(self):
        os.makedirs(self.out, exist_ok=True)
        # remove stale schgen-generated sheets
        for f in os.listdir(self.out):
            if f.endswith('.kicad_sch'):
                fp = os.path.join(self.out, f)
                try:
                    with open(fp, encoding='utf-8') as fh:
                        head = fh.read(400)
                    if '(generator "schgen")' in head:
                        os.remove(fp)
                except OSError:
                    pass
        name = self.b.name

        def put(fn, text):
            path = os.path.join(self.out, fn)
            d = os.path.dirname(path)
            os.makedirs(d, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            self.files.append(path)

        put(name + '.kicad_pro', json.dumps(self._project_json(), indent=2) + '\n')
        put(name + '.kicad_sch', sx_dump(self._root_file()) + '\n')
        for i, sh in enumerate(self.b.sheets):
            put(sh.file, sx_dump(self._sheet_file(sh, i + 2)) + '\n')
        if self.gen_symbols:
            put(os.path.join('symbols', name + '.kicad_sym'), sx_dump(self._gen_lib()) + '\n')
            table = ('(sym_lib_table\n\t(version 7)\n'
                     '\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/symbols/%s.kicad_sym")'
                     '(options "")(descr "schgen generated symbols"))\n)\n' % (name, name))
        else:
            table = '(sym_lib_table\n\t(version 7)\n)\n'
        put('sym-lib-table', table)
        if self.b.pcb:
            put(name + '.kicad_pcb', sx_dump(pcb_outline(self.b)) + '\n')


# --------------------------------------------------------------------------
# PCB outline
# --------------------------------------------------------------------------
HOLE_FP = {'M2': 'MountingHole:MountingHole_2.2mm_M2', 'M2.5': 'MountingHole:MountingHole_2.7mm_M2.5',
           'M3': 'MountingHole:MountingHole_3.2mm_M3', 'M4': 'MountingHole:MountingHole_4.3mm_M4',
           'M5': 'MountingHole:MountingHole_5.3mm_M5', 'M6': 'MountingHole:MountingHole_6.4mm_M6',
           'M3_Pad': 'MountingHole:MountingHole_3.2mm_M3_Pad', 'M4_Pad': 'MountingHole:MountingHole_4.3mm_M4_Pad'}

PCB_ORIGIN = (50.0, 50.0)   # top-left corner of the board on the PCB page


def _load_footprint(fpid, ref, x, y, seed, flip_text=False):
    lib, name = fpid.split(':', 1)
    path = os.path.join(STOCK_FP_DIR, lib + '.pretty', name + '.kicad_mod')
    if not os.path.isfile(path):
        raise SpecError('footprint %s not found (%s)' % (fpid, path))
    with open(path, encoding='utf-8') as f:
        fp = sx_parse(f.read())
    out = [Sym('footprint'), fpid]
    for c in fp[2:]:
        if isinstance(c, list) and c[0] in ('version', 'generator', 'generator_version'):
            continue
        out.append(c)
    # insert uuid + at after the layer
    li = next((i for i, c in enumerate(out) if isinstance(c, list) and c[0] == 'layer'), 1)
    out[li + 1:li + 1] = [N('uuid', _uid(seed, 'fp', ref)), N('at', float(x), float(y))]
    for c in out:
        if isinstance(c, list) and c[0] == 'property' and c[1] == 'Reference':
            c[2] = ref
        if flip_text and isinstance(c, list) and c[0] == 'property' and c[1] in ('Reference', 'Value'):
            at = sx_find(c, 'at')       # mirror the text to the other side of the origin (keep it on board)
            if at:
                at[2] = -float(at[2])
    for i, c in enumerate(out):
        if isinstance(c, list) and c[0] == 'pad' and sx_find(c, 'uuid') is None:
            c.append(N('uuid', _uid(seed, 'pad', ref, i)))
    return out


def pcb_outline(board):
    pc = board.pcb
    w, h = float(pc.get('w', 100)), float(pc.get('h', 80))
    nl = int(pc.get('layers', 2))
    if nl not in (2, 4, 6):
        raise SpecError('pcb layers must be 2, 4 or 6')
    rad = float(pc.get('corner_radius', 0))
    thick = float(pc.get('thickness', 1.6))
    x0, y0 = PCB_ORIGIN
    x1, y1 = x0 + w, y0 + h
    paper = next((p for p in PAPER_ORDER if PAPERS[p][0] >= w + 2 * x0 and PAPERS[p][1] >= h + 2 * y0), 'A0')
    layers = N('layers', N(0, 'F.Cu', Sym('signal')))
    for i in range(nl - 2):
        layers.append(N(4 + 2 * i, 'In%d.Cu' % (i + 1), Sym('signal')))
    layers.append(N(2, 'B.Cu', Sym('signal')))
    for row in ((9, 'F.Adhes', 'user', 'F.Adhesive'), (11, 'B.Adhes', 'user', 'B.Adhesive'),
                (13, 'F.Paste', 'user'), (15, 'B.Paste', 'user'),
                (5, 'F.SilkS', 'user', 'F.Silkscreen'), (7, 'B.SilkS', 'user', 'B.Silkscreen'),
                (1, 'F.Mask', 'user'), (3, 'B.Mask', 'user'),
                (17, 'Dwgs.User', 'user', 'User.Drawings'), (19, 'Cmts.User', 'user', 'User.Comments'),
                (21, 'Eco1.User', 'user', 'User.Eco1'), (23, 'Eco2.User', 'user', 'User.Eco2'),
                (25, 'Edge.Cuts', 'user'), (27, 'Margin', 'user'),
                (31, 'F.CrtYd', 'user', 'F.Courtyard'), (29, 'B.CrtYd', 'user', 'B.Courtyard'),
                (35, 'F.Fab', 'user'), (33, 'B.Fab', 'user')):
        layers.append(N(row[0], row[1], Sym(row[2]), *row[3:]))
    seed = board.name + '/pcb'
    doc = N('kicad_pcb', N('version', PCB_VERSION), N('generator', GENERATOR),
            N('generator_version', GEN_VERSION),
            N('general', N('thickness', thick), N('legacy_teardrops', NO)),
            N('paper', paper),
            N('title_block', N('title', board.title), N('date', board.date), N('rev', board.rev),
              N('company', board.company),
              N('comment', 1, 'Board outline %g x %g mm, %d layers - generated by schgen' % (w, h, nl))),
            layers,
            N('setup', N('pad_to_mask_clearance', 0), N('allow_soldermask_bridges_in_footprints', NO)),
            N('net', 0, ''))
    stroke = N('stroke', N('width', 0.1), N('type', Sym('default')))
    if rad <= 0:
        doc.append(N('gr_rect', N('start', x0, y0), N('end', x1, y1), copy.deepcopy(stroke),
                     N('fill', NO), N('layer', 'Edge.Cuts'), N('uuid', _uid(seed, 'edge'))))
    else:
        r = rad
        segs = [((x0 + r, y0), (x1 - r, y0)), ((x1, y0 + r), (x1, y1 - r)),
                ((x1 - r, y1), (x0 + r, y1)), ((x0, y1 - r), (x0, y0 + r))]
        for i, (a, b) in enumerate(segs):
            doc.append(N('gr_line', N('start', *a), N('end', *b), copy.deepcopy(stroke),
                         N('layer', 'Edge.Cuts'), N('uuid', _uid(seed, 'el', i))))
        k = r * (1 - math.sqrt(0.5))
        arcs = [((x0, y0 + r), (x0 + k, y0 + k), (x0 + r, y0)),
                ((x1 - r, y0), (x1 - k, y0 + k), (x1, y0 + r)),
                ((x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1)),
                ((x0 + r, y1), (x0 + k, y1 - k), (x0, y1 - r))]
        for i, (a, m, b) in enumerate(arcs):
            doc.append(N('gr_arc', N('start', round(a[0], 4), round(a[1], 4)), N('mid', round(m[0], 4), round(m[1], 4)),
                         N('end', round(b[0], 4), round(b[1], 4)), copy.deepcopy(stroke),
                         N('layer', 'Edge.Cuts'), N('uuid', _uid(seed, 'ea', i))))
    holes = pc.get('holes', 'M3')
    if holes:
        fpid = holes if ':' in str(holes) else HOLE_FP.get(str(holes))
        if not fpid:
            raise SpecError('pcb holes %r unknown (use %s or a full footprint id)' % (holes, ', '.join(HOLE_FP)))
        ins = float(pc.get('hole_inset', 4))
        pts = pc.get('hole_positions') or [(ins, ins), (w - ins, ins), (w - ins, h - ins), (ins, h - ins)]
        for i, (hx, hy) in enumerate(pts):
            doc.append(_load_footprint(fpid, 'H%d' % (i + 1), x0 + hx, y0 + hy, seed, flip_text=hy < h / 2))
    doc.append(N('gr_text', '%s rev %s' % (board.title, board.rev),
                 N('at', x0 + w / 2, y0 + h / 2, 0), N('layer', 'F.SilkS'),
                 N('uuid', _uid(seed, 'title')),
                 N('effects', N('font', N('size', 2, 2), N('thickness', 0.3)))))
    doc.append(N('embedded_fonts', NO))
    return doc


# --------------------------------------------------------------------------
# Validation with kicad-cli
# --------------------------------------------------------------------------
def _run(args, log):
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise SpecError('kicad-cli not found at %s (set KICAD_CLI)' % args[0])
    log.append(dict(cmd=' '.join(args), rc=cp.returncode,
                    out=(cp.stdout or '')[-2000:], err=(cp.stderr or '')[-2000:]))
    return cp


def parse_erc(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    viol = []
    for sh in data.get('sheets', []):
        for v in sh.get('violations', []):
            v = dict(v)
            v['sheet'] = sh.get('path', '')
            viol.append(v)
    return viol


def parse_netlist_xml(path):
    root = ET.parse(path).getroot()
    comps = {}
    for c in root.iter('comp'):
        comps[c.get('ref')] = c
    nets = {}
    for n in root.iter('net'):
        nodes = set()
        for nd in n.iter('node'):
            nodes.add((nd.get('ref'), nd.get('pin')))
        nets[n.get('name')] = nodes
    return comps, nets


def compare_netlist(spec_nets, spec_nc, spec_refs, comps, nets):
    """Round-trip check.  Returns a list of human-readable mismatch strings."""
    mism = []
    flt = {name: {n for n in nodes if not n[0].startswith('#')} for name, nodes in nets.items()}
    flt = {k: v for k, v in flt.items() if v}
    by_node = {}
    for name, nodes in flt.items():
        for nd in nodes:
            by_node.setdefault(nd, []).append(name)
    for nd, names in by_node.items():
        if len(names) > 1:
            mism.append('pin %s.%s appears in several nets %s' % (nd[0], nd[1], names))
    for net, nodes in sorted(spec_nets.items()):
        got = flt.get(net)
        if got is None:
            # maybe KiCad named it differently: find the net containing our first node
            any_node = sorted(nodes)[0]
            other = by_node.get(any_node, ['<absent>'])
            mism.append('net %r missing in netlist (its pin %s.%s is on %s)' % (net, any_node[0], any_node[1], other))
            continue
        if got != nodes:
            extra = sorted(got - nodes)
            miss = sorted(nodes - got)
            mism.append('net %r differs: extra %s missing %s' % (net, extra, miss))
    for name, nodes in sorted(flt.items()):
        if name in spec_nets:
            continue
        if nodes <= spec_nc and len(nodes) == 1:
            continue
        mism.append('unexpected net %r with nodes %s' % (name, sorted(nodes)))
    got_refs = {r for r in comps if not r.startswith('#')}
    if got_refs != spec_refs:
        mism.append('component set differs: extra %s missing %s'
                    % (sorted(got_refs - spec_refs), sorted(spec_refs - got_refs)))
    return mism


def _step_bbox(path):
    """Bounding box of all B-rep vertices (VERTEX_POINT -> CARTESIAN_POINT)."""
    num = r'([-\d.Ee+]+)'
    rp = re.compile(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*%s\s*,\s*%s\s*,\s*%s\s*\)" % (num, num, num))
    rv = re.compile(r"VERTEX_POINT\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*\)")
    with open(path, encoding='utf-8', errors='replace') as f:
        txt = f.read()
    pts = {m.group(1): (float(m.group(2)), float(m.group(3)), float(m.group(4))) for m in rp.finditer(txt)}
    vs = [pts[m.group(1)] for m in rv.finditer(txt) if m.group(1) in pts]
    if not vs:
        return None
    return tuple(min(v[i] for v in vs) for i in range(3)) + tuple(max(v[i] for v in vs) for i in range(3))


def validate(writer, kicad_cli=KICAD_CLI, pdf=True, bom=True, step=True):
    b, out = writer.b, writer.out
    name = b.name
    root = os.path.join(out, name + '.kicad_sch')
    log = []
    rep = dict(board=name, out=out, commands=log)
    # ERC
    erc_path = os.path.join(out, name + '_erc.json')
    _run([kicad_cli, 'sch', 'erc', '--format', 'json', '--severity-error', '--severity-warning',
          '-o', erc_path, root], log)
    if os.path.isfile(erc_path):
        viol = parse_erc(erc_path)
        summ = {}
        for v in viol:
            k = (v.get('severity', '?'), v.get('type', '?'))
            summ[k] = summ.get(k, 0) + 1
        rep['erc'] = dict(errors=sum(1 for v in viol if v.get('severity') == 'error'),
                          warnings=sum(1 for v in viol if v.get('severity') == 'warning'),
                          by_type={'%s:%s' % k: n for k, n in sorted(summ.items())},
                          details=[dict(severity=v.get('severity'), type=v.get('type'),
                                        description=v.get('description'), sheet=v.get('sheet'),
                                        items=[i.get('description') for i in v.get('items', [])])
                                   for v in viol])
    else:
        rep['erc'] = dict(errors=-1, warnings=-1, by_type={}, details=[], failed=log[-1])
    # netlist round trip
    net_path = os.path.join(out, name + '_netlist.xml')
    _run([kicad_cli, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', net_path, root], log)
    if os.path.isfile(net_path):
        comps, nets = parse_netlist_xml(net_path)
        spec_refs = {rp.ref for rp in writer.rparts}
        mism = compare_netlist(writer.nets, writer.nc_pins, spec_refs, comps, nets)
        rep['roundtrip'] = dict(mismatches=mism, spec_nets=len(writer.nets),
                                netlist_nets=len(nets),
                                netlist_named_nets=sum(1 for n in nets if not n.startswith('unconnected-')),
                                components=len([c for c in comps if not c.startswith('#')]))
    else:
        rep['roundtrip'] = dict(mismatches=['netlist export failed'], failed=log[-1])
    if pdf:
        p = os.path.join(out, name + '.pdf')
        _run([kicad_cli, 'sch', 'export', 'pdf', '-o', p, root], log)
        rep['pdf'] = p if os.path.isfile(p) else None
    if bom:
        p = os.path.join(out, name + '_bom.csv')
        _run([kicad_cli, 'sch', 'export', 'bom', '-o', p,
              '--fields', 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,${QUANTITY},${DNP}',
              '--labels', 'Refs,Value,Footprint,MPN,Manufacturer,LCSC,Qty,DNP',
              '--group-by', 'Value,Footprint,MPN,Manufacturer,LCSC,${DNP}',
              '--ref-range-delimiter', '', root], log)
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                rows = list(csv.reader(f))
            rep['bom'] = dict(path=p, lines=max(0, len(rows) - 1))
        else:
            rep['bom'] = None
    if step and b.pcb:
        pcb = os.path.join(out, name + '.kicad_pcb')
        sp = os.path.join(out, name + '_board.step')
        x0, y0 = PCB_ORIGIN
        h = float(b.pcb.get('h', 80))
        _run([kicad_cli, 'pcb', 'export', 'step', '--board-only', '-f', '--no-optimize-step',
              '--user-origin', '%gx%gmm' % (x0, y0 + h), '-o', sp, pcb], log)
        rep['step'] = dict(path=sp if os.path.isfile(sp) else None,
                           bbox=_step_bbox(sp) if os.path.isfile(sp) else None)
    if b.pcb:
        dp = os.path.join(out, name + '_drc.json')
        _run([kicad_cli, 'pcb', 'drc', '--format', 'json', '-o', dp, os.path.join(out, name + '.kicad_pcb')], log)
        if os.path.isfile(dp):
            with open(dp, encoding='utf-8') as f:
                d = json.load(f)
            rep['pcb_drc'] = dict(violations=len(d.get('violations', [])),
                                  types=sorted({v.get('type') for v in d.get('violations', [])}))
            os.remove(dp)
    return rep


# --------------------------------------------------------------------------
# Top-level build + reporting
# --------------------------------------------------------------------------
def build(board, out_dir, check=True, kicad_cli=KICAD_CLI, pdf=True, bom=True, step=True, quiet=False):
    """Generate the KiCad project for `board` into `out_dir` and (optionally)
    validate it.  Returns the report dict."""
    w = Writer(board, out_dir)
    w.resolve()
    w.layout()
    prl = os.path.join(os.path.abspath(out_dir), board.name + '.kicad_prl')
    had_prl = os.path.isfile(prl)
    w.write()
    npins = sum(len(rp.sym.pins) for rp in w.rparts)
    rep = dict(board=board.name, parts=len(w.rparts),
               units=sum(len(v) for v in w.sheet_blocks.values()) - len(w.flag_nets),
               sheets=[dict(name=s.name, file=s.file, paper=w.sheet_paper[s.name],
                            parts=sum(1 for r in w.rparts if r.sheet is s)) for s in board.sheets],
               nets=len(w.nets), pins=npins,
               pins_connected=sum(len(v) for v in w.nets.values()),
               pins_nc=len(w.nc_pins), power_flags=w.flag_nets,
               generated_symbols=[g.name for g in w.gen_symbols],
               warnings=w.warnings, files=[os.path.relpath(f, w.out) for f in w.files])
    if check:
        rep.update(validate(w, kicad_cli=kicad_cli, pdf=pdf, bom=bom, step=step))
        if not had_prl and os.path.isfile(prl):
            os.remove(prl)          # created by kicad-cli; keep the output folder clean
    rep['ok'] = (not check) or (rep['erc']['errors'] == 0 and not rep['roundtrip']['mismatches'])
    with open(os.path.join(w.out, board.name + '_report.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1, default=str)
    if not quiet:
        print_report(rep)
    return rep


def print_report(rep):
    pr = print
    pr('== schgen build: %s ==' % rep['board'])
    pr('  parts %d (symbol units placed %d), sheets %d, nets %d, pins %d (connected %d, NC %d)'
       % (rep['parts'], rep['units'], len(rep['sheets']), rep['nets'], rep['pins'],
          rep['pins_connected'], rep['pins_nc']))
    for s in rep['sheets']:
        pr('    sheet %-12s %-22s %s  %d parts' % (s['name'], s['file'], s['paper'], s['parts']))
    if rep['power_flags']:
        pr('  PWR_FLAG on: %s' % ', '.join(rep['power_flags']))
    if rep['generated_symbols']:
        pr('  generated symbols: %s' % ', '.join(rep['generated_symbols']))
    for wmsg in rep['warnings']:
        pr('  spec warning: %s' % wmsg)
    if 'erc' in rep:
        e = rep['erc']
        pr('  ERC: %d error(s), %d warning(s)' % (e['errors'], e['warnings']))
        for k, n in e['by_type'].items():
            pr('    %-45s x%d' % (k, n))
        for d in e['details'][:12]:
            pr('      - [%s] %s: %s' % (d['severity'], d['type'], '; '.join(i for i in d['items'] if i)))
    if 'roundtrip' in rep:
        rt = rep['roundtrip']
        if rt['mismatches']:
            pr('  netlist round-trip: %d MISMATCH(ES)' % len(rt['mismatches']))
            for m in rt['mismatches'][:40]:
                pr('    ! ' + m)
        else:
            pr('  netlist round-trip: OK - %d/%d spec nets identical, %d components, no unexpected nets/pins'
               % (rt['spec_nets'], rt['spec_nets'], rt['components']))
    if rep.get('pdf'):
        pr('  PDF : %s' % rep['pdf'])
    if rep.get('bom'):
        pr('  BOM : %s (%d lines)' % (rep['bom']['path'], rep['bom']['lines']))
    if rep.get('step'):
        st = rep['step']
        if st['path']:
            bb = st['bbox']
            pr('  STEP: %s  bbox X %.1f..%.1f  Y %.1f..%.1f  Z %.2f..%.2f mm'
               % (st['path'], bb[0], bb[3], bb[1], bb[4], bb[2], bb[5]) if bb else '  STEP: %s' % st['path'])
        else:
            pr('  STEP: export FAILED')
    if rep.get('pcb_drc') is not None:
        pr('  PCB : outline DRC %d violation(s) %s' % (rep['pcb_drc']['violations'], ', '.join(rep['pcb_drc']['types'])))
    pr('  RESULT: %s' % ('PASS' if rep['ok'] else 'FAIL'))


def load_spec(path):
    """Import a board-spec module and return its BOARD object."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    # make `import schgen` inside the spec return THIS module (also when run as __main__)
    sys.modules.setdefault('schgen', sys.modules[__name__])
    spec_dir = os.path.dirname(os.path.abspath(path))
    if spec_dir not in sys.path:
        sys.path.insert(0, spec_dir)
    modname = '_schgen_spec_' + re.sub(r'\W', '_', os.path.splitext(os.path.basename(path))[0])
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    board = getattr(mod, 'BOARD', None)
    if board is None:
        raise SpecError('%s does not define BOARD' % path)
    return board


def cmd_pins(lib_id, sym_dir=STOCK_SYM_DIR):
    sym = SymbolResolver(sym_dir).get(lib_id)
    print('%s  units=%d  pins=%d  footprint=%s' % (sym.lib_id, sym.units, len(sym.pins),
                                                    sym.props.get('Footprint', {}).get('value', '')))
    print('%-5s %-6s %-24s %-15s %-4s %s' % ('unit', 'num', 'name', 'type', 'side', 'flags'))
    for p in sorted(sym.pins, key=lambda q: (q.unit, _natkey(q.number))):
        fl = []
        if p.hidden:
            fl.append('hidden')
        if p.alts:
            fl.append('alt:' + ','.join(p.alts[:6]) + ('...' if len(p.alts) > 6 else ''))
        print('%-5s %-6s %-24s %-15s %-4s %s' % (p.unit or 'all', p.number, p.name, p.etype, p.side, ' '.join(fl)))


def cmd_find(pattern, lib=None, sym_dir=STOCK_SYM_DIR):
    rx = re.compile(pattern, re.I)
    files = sorted(f for f in os.listdir(sym_dir) if f.endswith('.kicad_sym'))
    for f in files:
        nick = f[:-10]
        if lib and not re.search(lib, nick, re.I):
            continue
        with open(os.path.join(sym_dir, f), encoding='utf-8') as fh:
            txt = fh.read()
        for m in re.finditer(r'^\t\(symbol "([^"]+)"', txt, re.M):
            if rx.search(m.group(1)):
                print('%s:%s' % (nick, m.group(1)))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='schgen.py', description='netlist-driven KiCad 10 schematic generator')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='build a board spec into a KiCad project and validate it')
    b.add_argument('spec')
    b.add_argument('--out', required=True)
    b.add_argument('--no-check', action='store_true', help='only write files, skip kicad-cli validation')
    b.add_argument('--no-pdf', action='store_true')
    b.add_argument('--no-bom', action='store_true')
    b.add_argument('--no-step', action='store_true')
    b.add_argument('--kicad-cli', default=KICAD_CLI)
    pp = sub.add_parser('pins', help='print the pin table of a library symbol')
    pp.add_argument('lib_id')
    fp = sub.add_parser('find', help='search stock symbol names (regex)')
    fp.add_argument('pattern')
    fp.add_argument('--lib', default=None, help='regex on library nickname')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'build':
            board = load_spec(a.spec)
            rep = build(board, a.out, check=not a.no_check, kicad_cli=a.kicad_cli,
                        pdf=not a.no_pdf, bom=not a.no_bom, step=not a.no_step)
            return 0 if rep['ok'] else 1
        if a.cmd == 'pins':
            cmd_pins(a.lib_id)
            return 0
        if a.cmd == 'find':
            cmd_find(a.pattern, a.lib)
            return 0
    except SpecError as e:
        print('schgen: spec error: %s' % e, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.modules.setdefault('schgen', sys.modules[__name__])
    sys.exit(main())
