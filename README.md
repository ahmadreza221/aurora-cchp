# GR180-3D: shaft, shaft tunnel and diffuser (FreeCAD models)
Rebuild everything (run from the project folder; output goes to $GR180_OUT or the current folder): freecadcmd -c "exec(open('build_gr180.py').read())"
All dimensions are in mm. The axial origin of the assembly is the front face of the tunnel (front spigot).

## Bearings and preload (as decided by the user)
- 2 x 608 hybrid ceramic, 8x22x7, Si3N4 balls, ABEC-7, full complement / 15° angular contact (e.g. GRW D608/602839).
- Front bearing at tunnel x 0-7 in the Ø22 x 11.3 bore. Its inner ring sits against the shaft shoulder (shaft x 58). The shaft is placed at tunnel offset -51.
- Intended fits: front housing Ø22 H6/H7 with a SLIDING outer ring (target 0.002-0.008 mm clearance) so the spring can preload it. Rear housing Ø22 light push fit (about 0-0.003 mm clearance). Shaft seats Ø8 g5/h5, near-zero to a few microns of clearance (glue or a light press per your practice).
- Behind the front bearing (between it and the bottom of the bore):
  - Spacer washer Ø21.8 / Ø16 x 1.5 (x 7-8.5). It bears on the OUTER ring only. An ID of 16 clears the inner ring (about Ø12). A Ø9 ID spacer would rub on the inner ring, so it was not used.
  - Single-turn wave spring Ø21.8 / about Ø16, t about 0.2-0.25, free height about 3.0, installed at 2.8 (x 8.5-11.3). Target preload about 15 N. Adjust by grinding the spacer.
- No oil-line or cooling changes.

## Diffuser (Pos 4, aluminium)
See the diffuser notes in the report. Some vane geometry is reconstructed from the front view; see "assumptions".

## v6 changes (2026-10-20)
- **Shaft threads**: front M6 LH x15 (nose/nut), **rear M6 LEFT-hand x9** (turbine nut). Cosmetic (not modelled as helix).
- **Shaft tolerances (from GR130 shaft sheet)**: bearing seats Ø8 **-0.002/-0.005**; Ø7 sections **+0.005**.
- **Vaporisers**: 12 straight sticks Ø6x0.3 at r42.1, x32.4–96.0, flared front, closed round rear (GR180 photo "Combustion chamber 5" shows 12 straight sticks; this overrides the GR130 J-shape). Fuel: brass ring manifold Ø3 at x15/r42.1, 12 needles Ø1 through 12 Ø1.6 holes in the CC front cap.
- **Supply lines**: 3x Ø3x0.5 brass through vanes 1/5/9 at r47.2 (Ø3.2 holes, replacing 3 of the 13 vane screws, as on the GR130 diffuser), O-ring 6x1.5 in a Ø6.2x1.5 recess in the intake-outer wall, washer 5.8x3.1x0.65, push-in fitting placeholders. Fuel -> manifold, oil -> Ø3.2 hole in tunnel at x18 (front bearing), gas -> ends ahead of the CC cap.
- **Placeholders**: NGV (shroud Ø72.7/75.9, hub Ø42.5/44.5, bore Ø26, 17 vanes), turbine Ø70.3 (23 flat blades) + nut, casing CV470 Ø107 ID t0.3.
- **Exhaust** SS 0.5: rim Ø77 over NGV rear, straight 31, cone to outlet Ø55.4, inner cone Ø52x42 starting 1.5 mm behind the turbine, 3 Ø3 struts.
- **Starter**: Permax 280 in plastic body Ø24.4, Ø24 hub, Bendix cup Ø16.5/14.5, 3 Ø4 struts to the intake lip.

## Compressor wheel (GR180_Compressor.FCStd/.step/.stl), Schwitzer 316954 turned down: "GR180 Compressor.pdf" + "GR180 Engine complete.pdf" section
- Drawing values: OD Ø74, inducer Ø55.9 (tip 0.3 inside the Ø56.2 shroud), nose Ø17.9, bore Ø7, nose to back face 33, back boss Ø21.9 + integrated spacer Ø13 x2.5 (Ø8 bore), back face to spacer end 4.8 (measured 4.6-4.8 on the section), hub at the rim 7.68 from the spacer end (exit width 2.9).
- Mounting: the spacer seats on the front 608 inner ring (turbine notes: "integrated spacer"), back face x=-4.8, nose x=-37.8. 38.4 = nose to spacer end on the drawing (0.6 more than 33+4.8; read as the length before the front core was shortened).
- Change: the tunnel's 2 mm front spigot was removed and the flange face set to x=+0.1, so the diffuser (plate 4.4, confirmed) and the intake moved forward 1.9.
- Blades: 7 main + 7 splitters, 25.71° pitch checked on the solid. Twist/sweep comes from the photos (no angle given in any file): wrap 37°, backswept exit.
- Clearances: back face to diffuser 0.50, tip to shroud 0.30, nose nut 1.2, intake outer 1.23.

## v8 (2026-10-20): turbine, NGV, casing, diffuser relief, bearing O-ring
- **Turbine (GR180_Turbine)**, sources GR180 Turbine + NGV.pdf (lower view) and TW70blank.pdf.
  - Ø70.3, bore Ø8, hub length 14.51, blade root Ø44.2, rim width 7.2, blade width 6.7 at the tip ("6,7" on the sheet).
  - 23 blades, counted on the TW70 front view.
  - Assumed: front sleeve Ø13 × 6, dished web 3 thick, blade angles inlet 35/40° and exit −58/−52°, thickness 2.0 → 0.8.
  - Front face sits on the rear 608 inner ring at x=107.3. M6 left-hand nut Ø10×4 (assumed) at x=121.8.
  - **Thread engagement is only 2.2 mm.** The shaft thread runs to x=124, and shaft Ø8 145–166 (21) = bearing 7 + hub 14.51, so the drawing implies the rear bearing sits about 6 mm further forward. Unresolved.
- **NGV (GR180_NGV)**, source GR180 Turbine + NGV.pdf.
  - Outer Ø72.7, flange Ø75.9 × 4.0, shroud bore Ø70.5, 26° entry chamfer over 1.67, inner Ø44.5 / 42.5 × 14.5, web 1.5 at 8.5 with Ø26 bore, overall width 24.
  - 6 Ø3.2 holes on PCD 34 to the tunnel rear flange (Ø38 × 4, verified).
  - 15 vanes (NGV70blank).
  - The sheet's angle is 16°, not 19°. It is the vane trailing-edge line (not modelled). Exit angle 68°/64° assumed.
- **Diffuser:** Ø74.4–Ø76 rim relief 0.5 deep (depth assumed) in the plate face. The compressor back gap stays at 0.5 inside Ø74.4.
- **Front bearing O-ring:** 1.1 cord in a groove in the tunnel's Ø22 bore (Engine complete section, size assumed).
- **Casing (GR180_Casing): PHOTO-BASED.** CV470 can, ID107, t0.3, R12 rear shoulder down to Ø78 over the exhaust sleeve, rear flange ring, 6 radial M3 into the intake outer.
- **Exhaust:** inner cone moved to x=122.5 (GR130 note: 1–2 mm to the turbine).
- **Verification:** run verify_gr180.py (pairwise interference, gaps, rotor rotation sweep).
- **GR180Tools toolbar** (Mod symlink): GR180 Reset / Next part / Show all / Spin rotor. Macros are also in the FreeCAD Macro folder.

## v9 fuel system redesign (vaporisers fixed in the front cap)
Sources: GR180 photos `Combustion chamber 4/5/6` (12 straight sticks TIG-tacked through a ring), CC Inner sheet (12 hole columns), GR130 `Oil-fuel connection` sheet (Ø3 brass lines, 6x1.5 O-ring, Ø5.8 washer, Festo push-in), JMA Ireland KJ66 build manual and misterg.org.uk (Ø6x0.3 SS316 sticks ~64 long, Ø0.8 hypodermic needles, 3 SS strips locating the ring).
- CC_FrontCap: 12x Ø6.05 holes at r=42.1 (were Ø1.6 needle holes) + Ø3.2 start-gas stub hole at r=36.
- CC_Vaporisers: 12 straight Ø6x0.3x66, through the cap, mouth 1.0 proud with Ø7 flare, open rear end, x=20.1..86.1 (assumed brazed).
- SupplyLines: fuel ring Ø3x0.5 at x=15 r=42.1, 12 needles Ø0.8 inserted 10 into each mouth, 3 strip clips welded to the cap; fuel line with a joggle into the ring; start-gas line ends in the cap stub; oil line unchanged. All 3 still pass through diffuser vanes 1/5/9.
- Check: no volume interference; needle-to-tube wall 2.3 (needles centred; bend to touch the wall per KJ66 practice if wanted).
Backup of previous script: build_gr180_v8_backup.py. Preview: previews/GR180_fuel_system.png

## v10 natural gas (methane) fuel system, supply 4 barg max
Estimates (no fuel data in GR180 notes): thrust 176.5 N, TSFC ~0.147 kg/N/h (JetCat P180 class) -> kerosene 7.2 g/s full, ~1.6 g/s idle. Methane by LHV (43.1/50.0 MJ/kg): 6.2 g/s = ~33 Nm3/h full, ~1.4 g/s = ~7 Nm3/h idle. PR ~2.5 (tip 465 m/s) -> CC ~2.4 bar abs.
- Needles: 12x Ø1.5x0.2 (ID 1.1, straight, centred), total 11.4 mm2, Cd 0.8 -> manifold ~4.0 bar abs (3.0 barg) at full power, near-choked (critical 0.544, actual 0.60).
- Ring: Ø5x0.5 (ID 4) at x=15 r=42.1; feed: Ø8x1 (ID 6) radial through a Ø8.2 casing hole at x=15 (the Ø3 vane lines, ID 2, would choke at ~1.5 g/s).
- Start-gas line removed; cap stub hole = igniter/glow plug. Vane lines: oil (unchanged); the two freed vane holes plugged or used as P2 pressure tap.
- Changed-part check: no volume interference; feed tube 0.1 to casing hole.
Backup: build_gr180_v9_backup.py

## v11 – sensors, igniter, fastenings, oil jet, rotor clamp (backup: build_gr180_v10.py)
- RPM: Allegro A1120EUA Hall switch (3–24 V, open collector, tr 0.2 µs, 800 kHz sampling) on Ø2.5 SS arm, M3 boss in intake wall at x=-39.3, angle 90°; face 0.9 mm off nose cone. Magnet NdFeB Ø2×2 diametral in axial pocket Ø2.1×2.1 at r6.5 in nose-cone rear face (trapped by compressor nose), brass Ø2×2 balance slug opposite. 1 pulse/rev = 2 kHz @120k.
- Igniter: spark plug 1/4-32 UNEF (RCEXL CM-6 class), weld boss Ø10×5 on casing, x=33.6 (12 mm behind cap face – liner hole rows forbid 5–8 mm), angle 330°, gap at r44 midway between two vaporisers; Ø7 hole in CC outer liner.
- EGT: type K Ø1.5 sheathed, M4 compression fitting in Ø8 weld boss on exhaust duct, x=127 (5 mm behind turbine), tip r32, angle 30° (midway between struts).
- Starter: turned mount ring on bellmouth back (r33–47, local x1.6–5.5), 6×M3 tapped at r43; 3 feet 16×8×1.5 SS, 2×M3×6 each.
- Rear: casing flange Ø96 with 4×Ø3.2 @ r44 (45°+90k) → 4×M3×8 into 3 mm SS ring welded on exhaust (M3 tapped).
- Gas: M12×1 bulkhead (bore 8) with inner locknut + outer hex + compression nut; casing hole Ø12.2.
- Oil: 2nd Ø3×0.5 line from boss @274.5° to tunnel; Ø3.1 seat + Ø0.5 jet at 42° exiting the bore at x≈8.3 aimed at front 608/spacer. Boss @53° plugged (Ø3 pin + Ø5.8 head, O-ring).
- Nose cone: seated on compressor nose face x=-37.8, bore deepened to 15 → 11.2 mm M6LH engagement, 1.8 mm thread reserve, 1.8 mm shaft-end clearance.
- Rear stack: shaft +4.8 mm (rear thread 13.8), nut 10×6 → 6 mm engagement, shaft 1 mm proud; new spacer Ø12/Ø8×6.3 between shaft shoulder (x94) and rear 608 inner ring so the nut clamp closes.

## v12 – threads, oil-feed rings, O-ring (backup: build_gr180_v11.py, verify_gr180_v11.py)
- Rotor turns CCW seen from intake (backswept exducer). Shaft ends M6x1 **LH** (nose cone: starter torque tightens; turbine nut: air drag tightens). All other threads RH.
- Helical threads modelled (internal = tap tool, +0.06 radial clearance): shaft front 15 / rear 13.8, nose cone (11.2 engaged), turbine nut 10AF x6, igniter 1/4-32 UNEF (boss 7 high), EGT M4x0.7, RPM arm M3 + DIN 439 nut, bulkhead M12x1 + 2 nuts, 10 ISO 4762 M3 screws, tapped M3: tunnel 6, intake outer 6, diffuser vanes 10, starter ring 6 (ring now 4.5 thick), exhaust ring 4.
- Oil-feed rings (static, press fit + Loctite 641): front Ø22/Ø13 x2.0 at x0.1–2.1, rear Ø22/Ø13 x3.0 at x97.3–100.3 (on bore step); groove/rebate + 4x Ø0.45 jets exiting at ball pitch r7.55. Feed drillings Ø0.8 + Ø3.1 tube seats (front 285° from boss 274.5°; rear at A_OIL, old x18 hole removed).
- Front stack: compressor spacer → shim Ø12/Ø8x2.1 → 608 at x2.1–9.1 → shaft shoulder moved to shaft x60.1; old 1.5 spacer removed; wave spring 9.1–11.3.
- Front O-ring 22x1.0 FKM 75: gland Ø23.6 x1.4 at x4.9–6.3 (squeeze 20 %, fill 70 %). Rear: none (temperature > FKM limit, bearing must slide for thermal growth).
