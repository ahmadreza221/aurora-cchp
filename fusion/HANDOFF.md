# Handoff: continue GR180-CCHP in Autodesk Fusion (local Claude Code on the Mac)

**Talk to the user in Persian (فارسی) only.** The user follows along live in the Fusion window.

## Context
- Project: GR180-based micro gas turbine CCHP. >20 kW 3-phase electric (η_el ≈ 20 %, total ≈ 55 %), absorption chiller,
  DHW, 24/7 duty, ground-level open-field install in Borazjan (50 m altitude, ambient up to 46 °C).
- Precision matters: the parts are made by CNC, SLM and vacuum investment casting (IN713LC).
- **The geometry source is the Python code**, not Fusion:
  - `cad/engine/gg_turbine.py`: turbine stage geometry.
  - `sim/engine/*`: aero, FEA, vibration.
  - `docs/engine/E1_gg_turbine.md`: design record.
- Fusion is for viewing, assembly, drawings, CAM and inspection. Never hand-edit blade or vane surfaces in Fusion; change the
  code, re-export, and upload a new version.
- Work on git branch `main-smmbai`, then commit and push. Draft PR #1 is open on GitHub.
  A cloud Claude session works on the same branch, so `git pull` before starting.

## Step 1: build the E1 turbine stage in Fusion
1. `git pull`. Confirm `fusion/E1/*.step` (9 files) and `fusion/GR180_E1_Import/` exist.
2. Check the `fusion` MCP server (`/mcp` shows it connected) and look at its 4 tools to see what they can do: run a script,
   execute API Python, query the design, and so on.
3. Build the stage in the open Fusion design, preferably by running `fusion/GR180_E1_Import/GR180_E1_Import.py` through
   the MCP. The Fusion API needs the script's `run(context)`. If the MCP can only execute Python, run the same code with
   `PARTS` set to the absolute path of `fusion/E1`.
   - Units are mm, and the engine axis is **X**.
   - The script builds three components:
     - E1 blisk: bore-less disc plus one blade, circular-patterned 29×, joined.
     - E1 NGV ring: rings plus one vane, patterned 21×, joined.
     - E1 shaft (welded).
   - The script was written without access to Fusion, so it may need fixes. Likely problems:
     - STEP import creating a child occurrence; use proxies or pattern inside that component.
     - Circular pattern of bodies in a parametric design.
     - Material names.
     - Slow joins; `JOIN = False` is the fallback.
   - Fix the script in the repo, not only in memory.
4. Verify against the CAD record. Fusion mass is in g with the IN713LC density set to 8.00 g/cc.

   | Part | Expected |
   |---|---|
   | blisk final | ≈ 116.9 g, x 104.30..121.04, tip radius 35.15 |
   | NGV final | ≈ 111.6 g, x 94.80..118.80, shroud bore r 35.35 |
   | shaft | ≈ 137 g (steel 7.85 g/cc → ~135 g) |

   Also check the gaps:

   | Gap | Expected |
   |---|---|
   | blade tip to NGV shroud bore | 0.20 mm radial |
   | NGV inner ring end to rotor platform | 0.30 mm axial |
   | NGV trailing edge to rotor leading edge | 2.65 mm (hub) / 2.90 mm (tip) |

   Use Inspect > Measure and Interference, and report the results in Persian.
5. Save as "GR180 E1 Turbine" in My Project. Also build `KIND = 'cast'` as a second design, "GR180 E1 Turbine (cast
   blanks)".

## Step 2: other engine modules
Each module needs the same treatment: export compact STEP (one blade plus revolved bodies, as in
`fusion/export_e1_parts.py`), an import script, a check and a save.
- E2 combustor: `sim/engine/e2_*`.
  - 7 injectors.
  - Holes: 21 secondary × Ø5.8, 42 dilution × Ø8.4, 56 dome × Ø1.7.
  - Flange 16 × M8, PCD 160, OD 176.
  - `e2_combustor_calc.py` still carries a stale 12 × M6 flange; do not regress `e2_design.json`.
- E3 free power turbine and PMG: `docs/engine/E3_fpt_pmg.md`.
- GR180 compressor and core: `build_gr180.py` and `cad/`.
- FreeCAD and CalculiX may not be installed on the Mac. The cloud session used FreeCAD 1.1.3 from conda-forge
  (micromamba) with `ccx` and python-gmsh. Install them with micromamba if you need to re-export or run the FEA, or ask the
  user to request the export from the cloud session.

## Step 3: drawings and manufacturing in Fusion
1. Drawings with GD&T:
   - blisk: cast and machined
   - NGV: cast and machined
   - shaft
   - friction-weld detail: IN713LC / 42CrMo4, flash removed, 0.5 mm relief inside the 608 inner-ring contact, UT inspection
2. CAM: 5-axis finishing of the blisk tip and platform faces, NGV ring bores, shaft turning.
3. Rotor balance spec.

## Open engineering items (`docs/engine/E1_gg_turbine.md` §4)
1. 3D blade-root stress in a sector, with the fillets.
2. Hot tip clearance.
3. LCF at the web fillet.
4. Turbine-stage CFD with OpenFOAM on the Mac; NGV throat 1175 mm² vs 1224 mm² meanline.
5. Forced response for EO42 × ND13: crossings at 107k and 118k rpm.
6. Test plan: ping test, spin test, tip timing.

## Key numbers
| Item | Value |
|---|---|
| Design speed | 115k rpm (band 100–120k, trip 120k) |
| Rotor blades | 29 |
| NGV vanes | 21 |
| Injectors | 7 |
| Bore-less disc | 615 MPa peak hot, burst 201k rpm, creep ≥ 1e6 h |
| Blade root P/A | 285 MPa at 730 °C |

Blade frequencies at 115k (Hz):

| F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 |
|---|---|---|---|---|---|---|---|
| 7132 | 15215 | 20585 | 32539 | 46624 | 49360 | 55941 | 76795 |

Design rule: no 4-fold features in the gas path ahead of the turbine.

## AURORA-1000 (1 MW, geared, 15,000 rpm): two-stage turbine, rev 5
Design record: `docs/08_aurora1000_1MW_concept.md` §12. Geometry: `cad/engine/a1000_turbine.py`.
1. `git pull`. Check that `fusion/A1000/*.step` (8 files) and `fusion/A1000/parts.json` exist (`pattern.revision` = "rev 5").
2. Run `fusion/AURORA1000_Import/AURORA1000_Import.py` through the Fusion MCP, the same way as the E1 import. It builds
   four coloured components (counts are read from `parts.json`):

   | Component | Pattern | Colour |
   |---|---|---|
   | NGV1 | 39 vanes | orange |
   | blisk 1 | 59 blades | silver |
   | NGV2 | 29 vanes | light orange |
   | blisk 2 | 36 blades | blue-grey |

   Units are mm and the engine axis is X.
3. Verify against `parts.json` → `expected`: blisk 1 44.4 kg, blisk 2 52.5 kg, NGV1 8.6 kg, NGV2 14.4 kg, at MAR-M247 8.54 g/cc.
   Fix any Fusion-API problem in the script in the repo.
4. Save the design as **"AURORA-1000 Turbine rev5"**, take a screenshot for the user, then commit and push.
