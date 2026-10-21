# Graph Report - GR180-v12-backup-20261021-1404  (2026-10-21)

## Corpus Check
- Corpus is ~13,035 words - fits in a single context window. You may not need a graph.

## Summary
- 206 nodes · 434 edges · 13 communities
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.89)
- Token cost: 151,072 input · 0 output

## Community Hubs (Navigation)
- Engine Components & Findings
- Turbine Issues & Roadmap
- Cycle Simulation Model
- Geometry Measurement & Verify
- CAD Build Core Helpers
- FreeCAD Toolbar Animation
- Rotor Dynamics Model
- Generator Conversion Options
- CAD Hole & Part Helpers
- Blade & Bearing Geometry
- Oil Feed Drilling Helpers
- Helical Thread Modelling
- Compressor Blade Geometry

## God Nodes (most connected - your core abstractions)
1. `GR180-3D FreeCAD Model` - 14 edges
2. `Project Roadmap` - 12 edges
3. `main()` - 11 edges
4. `Front Bearing (sliding outer ring)` - 10 edges
5. `Turbine (GR180_Turbine 70.3 mm, 23 blades)` - 10 edges
6. `Generator Conversion Options` - 10 edges
7. `GR180 Shaft` - 9 edges
8. `Compressor Wheel (Schwitzer 316954, turned down)` - 9 edges
9. `match_turbojet()` - 8 edges
10. `main()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `C4: Turbine Centred on Only 7.7 mm of 8 mm Seat` --semantically_similar_to--> `Turbine Nut Thread Engagement Only 2.2 mm`  [INFERRED] [semantically similar]
  docs/01_analysis_review_v12.md → README.md
- `GR180 Single-Spool 180 N Turbojet` --references--> `GR180-3D FreeCAD Model`  [INFERRED]
  docs/01_analysis_review_v12.md → README.md
- `C5: Bearing Life for Generator Duty` --references--> `608 Hybrid Ceramic Bearings (2x)`  [INFERRED]
  docs/01_analysis_review_v12.md → README.md
- `I3: 1.4 mm Unshrouded Turbine Tip Trailing Edge` --references--> `Turbine (GR180_Turbine 70.3 mm, 23 blades)`  [INFERRED]
  docs/01_analysis_review_v12.md → README.md
- `I5: NGV-to-Rotor Axial Gap ~5.5 mm` --references--> `Turbine (GR180_Turbine 70.3 mm, 23 blades)`  [INFERRED]
  docs/01_analysis_review_v12.md → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **GR180 Rotor Stack (compressor, shaft, turbine, bearings, clamp parts)** — readme_compressor_wheel, readme_shaft, readme_turbine, readme_nose_cone, readme_608_hybrid_ceramic_bearings, readme_front_stack_shim, readme_rear_stack_spacer [INFERRED 0.85]
- **Critical v12 Review Findings C1-C5** — docs_01_analysis_review_v12_c1_mass_flow_mismatch, docs_01_analysis_review_v12_c2_critical_speed_mode, docs_01_analysis_review_v12_c3_turbine_tip_clearance, docs_01_analysis_review_v12_c4_turbine_centring, docs_01_analysis_review_v12_c5_bearing_life [EXTRACTED 1.00]
- **Generator Conversion Architectures** — docs_01_analysis_review_v12_arch_a_pm_on_shaft, docs_01_analysis_review_v12_arch_b_fpt_gearbox, docs_01_analysis_review_v12_arch_c_fpt_hs_pm, docs_01_analysis_review_v12_recuperator, docs_01_analysis_review_v12_chp [EXTRACTED 1.00]

## Communities (13 total, 0 thin omitted)

### Community 0 - "Engine Components & Findings"
Cohesion: 0.08
Nodes (43): C1: Compressor/Diffuser/Thrust Mass-Flow Mismatch, Simulated Design Point (176.5 N), I1: v12 Interference Check Incomplete, I2: Intake Outer M3 Thread Engagement FAIL, I4: Misleading NGV Angle in README, I6: Gas Supply Needs Booster or CNG, I7: Permax 280 Starter Likely Underpowered, P3: README Outdated (+35 more)

### Community 1 - "Turbine Issues & Roadmap"
Cohesion: 0.14
Nodes (22): C3: Turbine Tip Clearance Only 0.10 mm, C4: Turbine Centred on Only 7.7 mm of 8 mm Seat, ECU Control and Safety Systems, I3: 1.4 mm Unshrouded Turbine Tip Trailing Edge, I5: NGV-to-Rotor Axial Gap ~5.5 mm, I8: Rotor Stress and Burst Containment, P1: Hard-Coded Output Path, P2: No Git Version Control (+14 more)

### Community 2 - "Cycle Simulation Model"
Cohesion: 0.16
Nodes (14): calibrate(), chain(), compressor_checks(), fmt_pt(), free_power_turbine(), gas_generator(), main(), match_turbojet() (+6 more)

### Community 3 - "Geometry Measurement & Verify"
Cohesion: 0.15
Nodes (7): blade_row_throat(), pr(), thread_rod(), gap(), pr(), sh(), sweep()

### Community 4 - "CAD Build Core Helpers"
Cohesion: 0.15
Nodes (3): liner(), profile_sketch(), revolve()

### Community 5 - "FreeCAD Toolbar Animation"
Cohesion: 0.27
Nodes (8): _doc(), _home(), next_step(), tick(), _objs(), reset(), show_all(), spin()

### Community 6 - "Rotor Dynamics Model"
Cohesion: 0.25
Nodes (7): build(), criticals(), disks_from_json(), gen_rotor(), main(), shaft_r(), whirl()

### Community 7 - "Generator Conversion Options"
Cohesion: 0.21
Nodes (13): GR180 Full Analysis and v12 Design Review, Architecture A: PM Generator on Core Shaft, Architecture B: Free Power Turbine + Two-Stage Gearbox, Architecture C: FPT + High-Speed PM Generator + Inverter, C2: Bending/Conical Mode Near Operating Speed, C5: Bearing Life for Generator Duty, Campbell Diagram (sim/gr180_campbell.png), Combined Heat and Power (CHP) (+5 more)

### Community 8 - "CAD Hole & Part Helpers"
Cohesion: 0.18
Nodes (7): hexprism(), hole1(), hole_pattern(), hp(), radial_holes(), save_part(), subcyl_pattern()

### Community 9 - "Blade & Bearing Geometry"
Cohesion: 0.29
Nodes (6): arcpts(), bearing608(), cam_blade(), count_holes(), half_ellipse(), s_at()

### Community 10 - "Oil Feed Drilling Helpers"
Cohesion: 0.33
Nodes (7): D_(), drill(), oil_ring(), P(), Q(), rad_cyl(), unit()

### Community 11 - "Helical Thread Modelling"
Cohesion: 0.33
Nodes (4): prism_n(), tap(), tapcut(), thread_rod()

### Community 12 - "Compressor Blade Geometry"
Cohesion: 0.40
Nodes (5): cw_blade(), cw_hub(), cw_theta(), cw_tip(), cw_tip_r()

## Knowledge Gaps
- **8 isolated node(s):** `JMA Ireland KJ66 Build Manual`, `misterg.org.uk`, `JetCat P180 (TSFC reference class)`, `GR180 Compressor.pdf`, `I6: Gas Supply Needs Booster or CNG` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 41 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GR180-3D FreeCAD Model` connect `Engine Components & Findings` to `Turbine Issues & Roadmap`, `Geometry Measurement & Verify`, `CAD Build Core Helpers`, `Generator Conversion Options`?**
  _High betweenness centrality (0.233) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `GR180-3D FreeCAD Model` (e.g. with `GR180 Single-Spool 180 N Turbojet` and `measure_geometry.py`) actually correct?**
  _`GR180-3D FreeCAD Model` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `JMA Ireland KJ66 Build Manual`, `misterg.org.uk`, `JetCat P180 (TSFC reference class)` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Engine Components & Findings` be split into smaller, more focused modules?**
  _Cohesion score 0.08383838383838384 - nodes in this community are weakly interconnected._
- **Why does `v8 Changes: Turbine, NGV, Casing` connect `Turbine Issues & Roadmap` to `Engine Components & Findings`, `Geometry Measurement & Verify`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Should `Turbine Issues & Roadmap` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._
- **Why does `Project Roadmap` connect `Turbine Issues & Roadmap` to `Engine Components & Findings`, `Generator Conversion Options`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._