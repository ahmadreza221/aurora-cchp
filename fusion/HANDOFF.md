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
   | NGV1 | 48 vanes | orange |
   | blisk 1 | 59 blades | silver |
   | NGV2 | 24 vanes | light orange |
   | blisk 2 | 36 blades | blue-grey |

   Units are mm and the engine axis is X.
3. Verify against `parts.json` → `expected`: blisk 1 44.4 kg, blisk 2 52.5 kg, NGV1 7.2 kg, NGV2 17.1 kg, at MAR-M247 8.54 g/cc.
   Fix any Fusion-API problem in the script in the repo.
4. Save the design as **"AURORA-1000 Turbine rev5"**, take a screenshot for the user, then commit and push.

**Done 2026-10-30 (local Mac, Fusion 2706):** "AURORA-1000 Turbine rev5" saved in Default Project. Imported with
`JOIN = False`, 55 s. Fusion masses: NGV1 7.237, blisk 1 44.393, NGV2 17.067, blisk 2 52.515 kg (expected 7.24 / 44.38 /
17.06 / 52.50).

### Whole package in Fusion
1. `A1000_STEP=1 GR180_ROOT=$PWD freecadcmd -c "exec(open('cad/engine/a1000_viewer_export.py').read())"` writes
   `fusion/A1000_pkg/*.step` + `pkg.json`. These are the same parts as the web viewer. The turbine rows are referenced
   from `fusion/A1000`.
2. Run `fusion/AURORA1000_Package/AURORA1000_Package.py`. It builds a direct-modelling design with one component per
   group and one sub-component per part. Casings, ducts and the recuperator are see-through.
3. Result: 43 parts, 264 bodies. Bounding box: x −3500..2400, y −1250..2100, z −1000..1810 mm. Saved as
   **"AURORA-1000 Package rev5"**. Runtime is about 20 s.

Copies of both designs are in `~/Desktop/GR180-Designs/11_AURORA-1000_1MW` (f3d, screenshots, POWER.md).

## AURORA-1000 rotor rev 1: stack, joints, bearings (2026-10-30)
Design record: `docs/08_aurora1000_1MW_concept.md` §13. Geometry: `cad/engine/a1000_rotor.py`. Checks:
`sim/engine/a1000_rotor_stack.py` (32 of 33 pass; the one fail is the impeller 1 front curvic in Al 2618, Ti-6Al-4V passes).
1. `freecadcmd -c "import sys; sys.argv=['a1000_rotor.py','--cad']; exec(open('cad/engine/a1000_rotor.py').read())"` writes
   `fusion/A1000_rotor/*.step` + `parts.json`. These are the shafts, tie bolt, drum, studs, the blisk discs with cast arms,
   and the bearings (pads, carrier, ISFD ring, housings, thrust bearing).
2. `fusion/AURORA1000_Rotor/AURORA1000_Rotor.py` builds "AURORA-1000 Rotor and Bearings rev1".
   - `SECTION = True` gives the half-section design.
   - It takes about 1 min.
3. `A1000_STEP=1 ... a1000_viewer_export.py` puts the rotor rev 1 parts into `fusion/A1000_pkg/pkg.json`. Then
   `AURORA1000_Package.py` rebuilds the whole package.
4. The blisk arms are not yet in `cad/engine/a1000_turbine.py`. The `fusion/A1000` disc pieces are still the bore-less rev 5
   discs.
## AURORA-1000 compressor impellers, rev 1 (2026-10-30)
Design record: `docs/08_aurora1000_1MW_concept.md` §15. Geometry: `cad/engine/a1000_impeller.py`. Checks:
`sim/engine/a1000_impeller_fea.py`.
1. CAD: `freecadcmd -c "import sys; sys.argv=['x','--cad']; exec(open('cad/engine/a1000_impeller.py').read())"`, then
   `python3 fusion/export_a1000_impellers.py "rev 1"`. This copies the six pieces (hub, blade and splitter per stage, in the
   rotor frame) to `fusion/A1000C/`. It also writes `parts.json` with the materials, the expected masses and the
   rotor-dynamics lumps.
2. Run `fusion/AURORA1000_Compressor/AURORA1000_Compressor.py`. It builds two coloured components. Each has the hub, one
   blade and one splitter, with blade and splitter patterned 13×. Both pieces sit at their own angular position, so both
   patterns start at 0.
   - Both impellers are Ti-6Al-4V (4.43 g/cc).
   - Expected masses: impeller 1 22.17 kg, impeller 2 28.35 kg.
   - The hub faces carry the mating curvic teeth of rotor rev 1.1.
3. Package:
   - `A1000_STEP=1 ... a1000_viewer_export.py` takes the impellers from `fusion/A1000C`.
   - It builds the compressor casing from the flow path: shroud walls, vaned diffusers, crossover, diaphragm, return channel
     and collector.
   - The diffuser and return-channel vanes are separate parts in a new group `diff`.
   - The rotor rev 1 and hot-section blocks still replace their own parts after that.
4. **Done 2026-10-30 (Fusion MCP)**, both rebuilt in place with a new version of the same file:
   - "AURORA-1000 Compressor rev1" v4: Fusion masses 22.15 / 28.29 kg, with curvic teeth.
   - "AURORA-1000 Package rev5" v10: radial inlet on the rotor hub fairing.

## AURORA-1000 combustion system rev 1: DLE can, scroll, scroll pressure casing (2026-10-30)
Design record: `docs/08_aurora1000_1MW_concept.md` §16. Checks: `sim/engine/a1000_combustor.py` (30 of 30 pass; the chemistry
is in `sim/engine/a1000_combustor_chem.py`, which needs Cantera; its results are cached in `sim/engine/fea/`).
1. CAD: `freecadcmd -c "import sys; sys.argv=['a1000_combustor.py','--cad']; exec(open('cad/engine/a1000_combustor.py').read())"`
   writes `fusion/A1000_comb/*.step` + `parts.json` (16 parts, ~1.2 t). `--section` draws `docs/img/a1000_combustor_section.png`.
2. Package: `a1000_viewer_export.py` reads `fusion/A1000_comb` in place of the concept can, scroll and injector (group
   `comb` for the hot parts, `casing` for the pressure casings and insulation, `aux` for the manifolds). `A1000_STEP_DIR`
   writes the STEP set to another folder, so only `pkg.json` and the changed parts need to be copied.
3. **Done 2026-10-30 (Fusion MCP)**: "AURORA-1000 Package rev5" **v11**, rebuilt in place by running `fill()` of
   `AURORA1000_Package.py` into the opened document after deleting its root occurrences: 79 parts, 527 bodies, bbox
   x −3500..2400, y −1250..2100, z −1000..2049 mm. The combustor volumes match the CAD masses. With the machine loaded the
   rebuild took ~6 min (the MCP call times out after 60 s; the script keeps running: log to a file and poll it).

## AURORA-1000 rev 6: R1 - NGV2 gap +25 mm (2026-10-30)
Design record: `docs/08_aurora1000_1MW_concept.md` §12.4.3, §13.9, §14.1. NGV2, R2 and everything behind them sit 25 mm
further aft (`a1000_turbine.DGAP2`); NGV1, R1 and the combustor are unchanged.
1. Turbine pieces: `a1000_turbine.py --cad`, then `python3 fusion/export_a1000_parts.py "rev 6 (R1 - NGV2 gap +25 mm)"`.
   Only the N2 and R2 pieces changed (same shapes, moved 25 mm); `parts.json` has the new row positions.
2. Rotor: new part `RT-107 Turbine spacer ring R1 - R2` (IN718, curvic both faces, 4 seal fins); the R1 - R2 studs are 51 mm
   (were 26). R2, the rear stub and JB2 moved 25 mm aft.
3. Hot section: casing x 678-903, C2 to x 875; new parts `HS-222` (outer gap liner) and `HS-234` (inner gap ring).
4. Combustor: only the scroll pressure casing halves changed (rear plate x 903 -> 928).
5. Package: `fusion/A1000_pkg` re-exported (82 parts in `pkg.json`). **The Fusion designs "Turbine rev5" and "Rotor and
   Bearings rev1" are not rebuilt yet** with these files; "Package rev5" is, as v12 (next section).

## AURORA-1000 package v12 and the animation add-in (2026-10-31)
1. **"AURORA-1000 Package rev5" v12**, rebuilt in place like v11 from `fusion/A1000_pkg/pkg.json`:
   - Contents: rotor rev 1.3, hot section and turbine rev 6, combustion rev 1.
   - Result: 82 parts, 526 bodies, bbox x −3500..2400, y −1250..2100, z −1000..2049 mm. The run took 5 min.
   - Read back: all 23 rotor and bearing volumes match `fusion/A1000_rotor/parts.json` within 0.02 %. The impeller hubs
     are 17.78 / 25.71 kg at 4.43 g/cc.
2. **Add-in `fusion/AURORA1000_Animate/`**: a panel **AURORA-1000** in the Design workspace (Solid tab) with three buttons
   for the package design.
   - Installed in `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/` with runOnStartup.
   - **Assembly sequence** (about 55 s): all parts are hidden, then they fly in by the build order of docs/08 §13 (5 steps,
     40 moves), with a label at the top left of the view.
   - **Spin rotor** (20 s, 2 turns): the rotor shaft group, the blisks and the impellers turn about the X axis
     (y = z = 0). The low-speed coupling turns at −1/10.
   - **Reset**: stops an animation and restores the transforms and light bulbs the animation started from. Each
     animation also restores them itself at the end; this was checked bit-exact against `pkg.json`.
   - Clicking any of the three buttons during an animation stops it.
3. Fusion API lessons:
   - Start an add-in from the MCP with `app.scripts.itemByPath(folder).run()`. Handlers made by an MCP script get no
     events after that script ends.
   - Inside a command, a nested occurrence takes `transform2` only through its root-context proxy
     (`createForAssemblyContext`).
   - A smooth camera transition drops `viewExtents`. Set the extents after the new eye has been applied.
   - Custom-graphics text needs `viewPlacement`, `viewScale` and `billBoarding` to lie flat on the screen.
