# schgen: netlist-driven KiCad 10 schematic + PCB-outline generator

`schgen.py` turns a Python **board spec** (parts + pin→net maps) into a real,
fully wired, hierarchical KiCad 10 project. It then checks the result with
`kicad-cli`: it runs ERC, exports the netlist, and compares that netlist pin by
pin against the spec. It is meant for the GR180-CCHP control boards (B1 ECU,
B2 sensor I/O, B3 rectifier controller, B4 drivers, B6 BOP controller).
The script uses only the Python 3 standard library. It expects KiCad 10.0.x
(`kicad-cli` at `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`; you
can override this with `KICAD_CLI`, `KICAD_SYMBOL_DIR` or `KICAD_FOOTPRINT_DIR`).

## Commands

```sh
# build + validate (ERC, netlist round-trip, PDF, BOM, STEP, outline DRC)
python3 electronics/tools/schgen.py build electronics/tools/example/example_spec.py \
        --out electronics/tools/example/out
#   options: --no-check (write files only)  --no-pdf  --no-bom  --no-step  --kicad-cli PATH
#   exit code: 0 = PASS (0 ERC errors and 0 round-trip mismatches), 1 = FAIL, 2 = spec error

python3 electronics/tools/schgen.py pins MCU_ST_STM32G4:STM32G474RETx   # pin table (unit, number, name, type, side, hidden, alternates)
python3 electronics/tools/schgen.py find 'TJA105' --lib CAN             # search stock symbol names (regex)
```

You can also use it as a library: `import schgen; rep = schgen.build(BOARD, out_dir)` returns the report dict.

## Spec API

```python
from schgen import Board, Sheet, P, R, C, L, D, G

P(ref, lib_id, value=None, footprint=None, pins=None, mpn=None, mfr=None, lcsc=None,
  datasheet=None, dnp=False, default_nc=False, fields=None, description=None)
R(ref, value, size=None, a=None, b=None, **P_kwargs)        # Device:R, a->pin1, b->pin2
C(ref, value, size=None, a=None, b=None, **P_kwargs)        # Device:C   (lib_id='Device:C_Polarized': a=+)
L(ref, value, size=None, a=None, b=None, **P_kwargs)        # Device:L   (lib_id='Device:FerriteBead')
D(ref, value, size=None, k=None, a=None, kind='D', **P_kwargs)  # kind: D | D_Schottky | D_Zener | D_TVS | LED
G(name, pins=[(num, name, etype, side), ...], ref='U', value=None, footprint='', datasheet='~',
  description='', keywords='', pin_length=2.54)            # generated symbol
Sheet(name, parts=(), paper=None, file=None, title=None)
Board(name, title=None, rev='0.1', company='GR180-CCHP', paper='A3', sheets=(), pcb=None,
      power_flags='auto', symbols=(), date=None, comments=(), root_paper='A4',
      erc_rules=None, erc_pin_map=None)
```

* **pins** is a dict `{pin number or pin name: net}`. A name that matches several pins (`'GND'`,
  `'VSS'`, `'VDD'`) applies to all of them, across units. Overbar markup is optional:
  `'~{SHDN}'` and `'SHDN'` both work. The value `'NC'` puts a no-connect flag on the pin.
  Assigning one pin two different nets is an error.
* **Strict mode (default):** every pin must be assigned. If any pin is left out, the build stops and lists the missing pins.
  With `default_nc=True`, every unmentioned pin gets an NC flag. Library pins of type
  `no_connect` are treated as NC automatically and get no marker.
* **Stacked pins** (pins at the same spot, such as the STM32 VSS pins or connector GND pins) must all get the same net.
* `lib_id` is `'Library:Symbol'` (a stock KiCad library) or a `G(...)` object. You can also list
  generated symbols in `Board(symbols=[...])` and refer to them as `'gen:Name'`.
  Symbols that use `extends` are flattened before they are embedded.
* **Multi-unit symbols** (op-amps, 74xx, relays): every unit is placed (U5A, U5B, U5C...).
* The default sizes for `R`/`C`/`L`/`LED` are 0402/0402/0603/0603, and SOD-123 for `D`. Change them for all
  parts with `schgen.PASSIVE_SIZE['R'] = '0603'`, or per part with `size='0805'` or `footprint='Lib:Name'`.
* **G pin tuple:** `etype` can be `input output bidirectional tri_state passive power_in power_out
  open_collector open_emitter no_connect free unspecified`, or one of the aliases `in out io pwr pwr_out oc nc pas`.
  `side` is `L R T B`. The tuple `(None, None, None, side)` leaves an empty slot on that side.
* **power_flags:** with `'auto'`, every net that has a `power_in` pin and no `power_out` pin gets a PWR_FLAG,
  placed on the sheet called "Power" (or the first sheet). You can instead pass an explicit list of nets, or `None`.
* **paper:** sets the default paper size for child sheets. If the parts do not fit, schgen moves up a size
  (A4→A3→A2→A1→A0) and prints a warning. `'auto'` picks the smallest size that fits.
* **erc_rules** / **erc_pin_map:** these are written to the `.kicad_pro` file. Use them only with a
  written reason. Example: `erc_rules={'footprint_link_issues': 'ignore'}`. Another example:
  `erc_pin_map={('power_out', 'power_out'): 'warning'}` for STM32H7 VCAP pins, which KiCad's library marks power_out.
* **pcb:** `dict(w, h, holes='M3', hole_inset=4, layers=2|4|6, corner_radius=0, thickness=1.6, hole_positions=None)`.
  `holes` can be one of `M2 M2.5 M3 M4 M5 M6 M3_Pad M4_Pad` or a full footprint id.

## What `build` writes (into `--out`)

| file | content |
|---|---|
| `<name>.kicad_pro`, `sym-lib-table` | minimal project, generated-symbol library table, ERC overrides |
| `<name>.kicad_sch` | root sheet: one hierarchical sheet symbol per `Sheet` |
| `<sheet>.kicad_sch` | each part placed on the 1.27 mm grid; each connected pin gets a 2.54 mm wire stub and a **global label** at the stub end; each NC pin gets a no-connect flag |
| `symbols/<name>.kicad_sym` | generated symbols (if any) |
| `<name>.kicad_pcb` | Edge.Cuts outline (with optional rounded corners), mounting holes, 2/4/6 copper layers, title block; no components |
| `<name>_erc.json`, `<name>_netlist.xml` | kicad-cli ERC report and kicadxml netlist |
| `<name>.pdf`, `<name>_bom.csv` | schematic PDF; grouped BOM with MPN / Manufacturer / LCSC / Qty / DNP |
| `<name>_board.step` | bare-board STEP. The origin is the bottom-left board corner: X 0..w, Y 0..h, Z 0..~1.51 (KiCad models the dielectric body only) |
| `<name>_report.json` | full report (counts, ERC details, mismatches, commands run) |

Each instance carries the fields Reference, Value, Footprint, Datasheet and Description, plus MPN, Manufacturer and LCSC (hidden).
Any extra fields go through `fields={...}`. UUIDs are deterministic (uuid5), so rebuilding the same spec gives
byte-identical schematics apart from the date. The output is generated, so don't hand-edit it. Edit the spec and rebuild.
Symbol instance paths are `/<root-uuid>/<sheet-uuid>`.

## How it was verified

* The worked example (`example/example_spec.py`) is a 24 V → LMR16006 buck → LD1117 → STM32G474RET6 board with an
  8 MHz HSE, SWD, NRST and BOOT0, a TJA1051T/3 CAN-FD transceiver with split termination and NUP2105L ESD, an M12 connector
  (a generated symbol) and an MCP6002 24 V monitor (multi-unit). It builds with **0 ERC errors, 0 ERC warnings,
  and 28/28 nets identical in the round-trip**. The outline DRC is clean.
* The child sheets were loaded and re-saved by KiCad 10 (`kicad-cli sch upgrade`). The re-saved files are semantically identical
  to the generated ones; only the `generator` string differs.
* Negative tests showed that each check catches real faults:
  - Removing the PWR_FLAGs gives `power_pin_not_driven` errors.
  - Moving one label 0.01 mm off its wire end gives `label_dangling` and `pin_not_connected`, and the round-trip reports the pin missing from its net.
  - Swapping two labels makes the round-trip report both nets as different.

## Limitations

* Symbols are placed at rotation 0, never mirrored. The layout is a simple column-stacking grid in spec
  order, so put related parts next to each other in the spec. Bus labels (`D[0..7]`, `{...}`) are rejected.
* All nets use global labels, including power nets (no power-port symbols and no hierarchical pins). So a net name
  means the same net on every sheet.
* Pins can be referred to by number or primary name, not by alternate function name (`FDCAN1_RX`). Use the
  pin name (`PA11`) or number. Run `schgen.py pins` to see the alternates.
* A hidden pin that is not stacked under a visible pin is still wired at its location, but you get a warning. A hidden
  `power_in` pin also joins a global net with its own name implicitly, which is how KiCad behaves.
* The PCB is an outline only. No footprints or netlist import, because kicad-cli has no "update PCB from schematic" command.
