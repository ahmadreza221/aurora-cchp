# GR180: Rutten's original drawings vs. `build_gr180.py` (v12)

Date: 2026-10-21. Scope: every dimension on the 13 PDFs in `~/Downloads/GR1802009/`, compared with `build_gr180.py` (777 lines, v12). This is a read-only analysis. No CAD or script was changed.

## 0. Method, datum and reliability

**Datum.** All assembly positions use the CAD's own axis. x = 0 is the front face of the shaft tunnel (the front face of its Ø26 × 2 spigot on the original drawing), and +x points toward the turbine. The CAD tunnel keeps this coordinate system: its bore step is at 11.3 and its rear face at 107.3, the same as the drawing. So the drawing and CAD numbers below share one datum and can be compared directly.

**How values were read.** None of the PDFs contains text objects. All dimension text is stroked vector geometry. Two steps were used:

1. Every dimension label was read from high-resolution renders (zoom 3–16).
2. Every outline, extension line and circle was extracted from the vector paths with pymupdf and converted at 72/25.4 pt per mm.

All sheets are drawn at 1:1 on A4, and the scale checks agree to about ±0.05 mm:

| Check | Label | Drawn (vector) |
|---|---|---|
| Compressor OD | 74 | 73.96 |
| Diffuser / casing OD | 107 | 107.02 |
| Shaft length | 175 | 174.96 |
| Tunnel length | 107.3 | 107.32 (assembly 107.27) |
| Turbine hub | 14.51 | 14.52 |

As a result, **undimensioned features can be measured on the sheet** (shaft body Ø, axial positions in the assembly section, hole positions on the CC templates). Where a label and the drawn geometry disagree, both are given and the label is treated as governing. Known label/drawn disagreements:

| Feature | Label | Drawn |
|---|---|---|
| Intake shroud bore | Ø56.2 | Ø56.30 |
| Intake outer wall | Ø59.5 | Ø59.27 |
| NGV OD | Ø72.7 | Ø72.90 |
| Intake bellmouth tangent | 9.17 | 9.82 |
| CC inner sheet | 131 | 130.2 |
| CC outer group pitch | 25 (300/12) | 24.72 |

**Status codes:**
- MATCH: CAD equals the drawing within about 0.1 mm.
- MISMATCH: CAD differs from the drawing.
- CAD-ASSUMED: the CAD invented the feature; it is not on any drawing.
- DRAWING-ONLY: the feature is on a drawing and missing in the CAD.
- INTENTIONAL: a deliberate later change (v7–v12, see README).

**Source of the stack-up.** The axial stack comes from the *Engine complete* section, which is a 1:1 half-section. It is cross-checked against the part drawings. Two independent stacks were checked:
- **Rotor stack:** shaft → bearing → integrated spacer → wheel.
- **Stator stack:** tunnel flange → diffuser → intake outer → intake.

They close to within 0.05 mm at the point where they must meet: the shroud arc of the intake and the tip arc of the wheel.

---

## 1. Summary: most important discrepancies, ranked by functional impact

1. **The compressor wheel is wrong in shape and position (aerodynamics; tip clearance).**
   - The drawing gives LE plane → back face = 33, nose boss 0.6 ahead of the LE, inducer tip straight for 12.93, tip arc R13, tip at rim 7.68 ahead of the back face, and **b2 = 6.48** with a 1.2 mm disc at the rim.
   - The CAD (l.398) treats 33 as nose → back face. It takes the 5.6 nose protrusion from the *unmodified* Schwitzer view (lower view on the same sheet), which puts the **LE 5.6 mm too far aft relative to the wheel's own back face** (+2.09 relative to the drawing's assembly position). It uses 7.68 as the hub position, which gives **b2 = 2.90**. It also shrinks the inducer to **Ø55.6** (tip = shroud − 0.3, l.401) instead of Ø55.9.
   - In the assembly the CAD wheel back face is at −4.80; the drawing has −1.32. **The whole wheel sits 3.48 mm too far forward.**
   - Correcting b2 alone, without restoring the stack, would put the wheel tip **about 3.3 mm into the CAD intake shroud** at the rim (at x = −12.48 the CAD shroud is at r 33.7, while the wheel tip is at r 37).
   - On the drawing, the wheel tip arc and the intake shroud arc are concentric (tangent points −21.34 vs −21.38). That gives a uniform tip clearance of about 0.15 mm, and the impeller exit (6.48 wide) sits in the 7.0 diffuser channel with the hub flush with the vane root.

2. **The diffuser is missing three functional features (aerodynamics; back-face gap).**
   - **(a) Recess.** There is a **Ø74.4 × 2.0 recess** in the plate. The plate is only 2.4 thick inside Ø74.4 (labels "74.4", "2", "5.6", "17"). The wheel back face runs in this recess with a gap of about 0.8 mm. The CAD has a solid 4.4 plate with only a 0.5 mm ring relief Ø74.4–76 (l.308). This is why the CAD pushes the wheel forward.
   - **(b) Axial vane section.** The vanes continue round the 90° bend: 13 axial channels are milled with a Ø6 cutter between the Ø91 skirt and Ø107, each **113.63 mm²** (labelled), **1477 mm² total**. The photos confirm this. The CAD has a vaneless 2488 mm² annulus there, so there is no de-swirl before the combustor.
   - **(c) Vane form and throat.** The drawing vanes are sharp wedges with the LE on **Ø76.0**, flanks at 66°/80° from radial, a wedge of **14.0°** and a channel divergence of **13.7°**. That gives an inlet throat of **7.35 mm**, so **13 × 7.35 × 7.0 ≈ 669 mm²**. The CAD uses LE Ø76.4, LE thickness 1.0, flanks 70°/82° and a 12° wedge, giving a throat of 6.65 and 605 mm² (−10 %). The "6,66" label on the sheet is the spacing of the Ø6 cutter passes, not the throat.

3. **The stator stack is shifted −1.77 mm and radial centring has been lost (assembly, tip clearance).**
   - Removing the tunnel's Ø26 × 2 spigot (v7, INTENTIONAL) moved the diffuser, intake outer and intake 1.77–1.9 mm forward.
   - It also removed the only radial location of the diffuser. On the drawing, the diffuser bore Ø26 pilots on the spigot.
   - The intake's Ø76 × 2.59 spigot projects 0.59 into the diffuser vane LE circle (Ø76.0) and centres the shroud on the diffuser. In the CAD, the vane LE circle is Ø76.4, so this second centring fit is lost too.
   - With a 0.15 mm design tip clearance, centring through screw clearance alone (about ±0.1 mm) is not acceptable.

4. **The compressor blade hand and the diffuser vane hand are opposite in the CAD (aerodynamics). This holds regardless of view convention.**
   - In CAD coordinates, the impeller blade wrap increases θ from LE to exit (l.409–410), which implies rotation toward −θ (stated in README v12 as CCW seen from the intake).
   - The diffuser vanes advance toward **+θ** going outward (l.90–100).
   - Impeller exit swirl follows the rotation, so in the CAD it runs into the vanes from the wrong side.
   - The drawing (front view) and the photo `Diffuser compr.jpg` both show the real vanes advancing **clockwise going outward, seen from the intake**. That matches the CAD vanes and implies **clockwise** rotor rotation. The CAD impeller (and the stated rotation) would therefore be mirrored.
   - Against this, the drawing's **M6 LH** nose thread suggests CCW, if Rutten chose LH so that the starter tightens it.
   - **This must be checked on the real wheel** (exducer backsweep direction) before the thread hands and the CAD wheel are finalised.

5. **Turbine and NGV axial stack (efficiency; tip leakage; hub pilot).**
   - On the drawing, the rear 608 sits on the shaft shoulder at 97.49 (about 0.2 from the bore step). The turbine hub occupies 104.48–119.00, and the blades are **fully inside the NGV shroud**: blade TE at 117.2, shroud end at 119.0.
   - The NGV-TE → rotor-LE axial gap is **3.1 at the hub and 2.0 at the tip**. The NGV inner ring → disc gap is 0.79.
   - The CAD (v11 rear spacer 6.3 + v12 rear oil ring 3.0) puts the turbine 2.82 mm further aft:
     - The blade tip TE is **1.4 mm outside the shroud**.
     - The gaps grow to **5.5 / 6.2**.
     - The hub pilots on **7.7 mm** of the Ø8 seat instead of **14.0**.
   - The CAD NGV has errors of its own:
     - The inner ring is 14.5 long; it should be 15.0. The "14.5" label is the outer-ring length up to a rib.
     - It carries a Ø75.9 × 4.0 rear **flange**. On the drawing, "4.0" (and "1.67") are the stock machined off the 30 mm JetMax blank. The real feature is a Ø75.9 × 1.5 **rib** at 14.5–16.0.
   - The CAD turbine blades are 7.2 / 6.7 wide (root / tip). The drawing has 6.7 / 6.2: "6,7" is at the root, and 7.2 is the blank's rim.

6. **Shaft geometry (rotor dynamics; bearing abutment).**
   - The shaft body is drawn **Ø15.5** (r 7.747 on both the shaft sheet and the assembly; not dimensioned), with **Ø11.0** at the 7° taper shoulders.
   - The CAD uses Ø14 and **Ø9.58** (l.41). That is 33 % less bending stiffness (the drawing is ×1.50 stiffer, d⁴) and about 15 g less mass. The CAD shoulder of Ø9.58 is a marginal abutment for the 608 inner ring.
   - The CAD shaft sits 3.5 mm further forward (offset −51 vs −47.5). Together with the shim and spacer this changes the bearing span (centre-to-centre) from **94.0** to **98.2** and the compressor overhang by +2.1.
   - The rotor-dynamics results in `docs/01` (C2) are therefore based on a different shaft and span.

7. **Front bearing seal and stack.**
   - The assembly shows an O-ring of **1.78 cord** centred at the bearing mid-plane (x 6.98) in a **Ø26 × 2.03** groove (x 5.97–8.00). The CAD has 22 × 1.0 in a Ø23.6 × 1.4 gland at 4.9–6.3 ("size assumed").
   - The drawing has the wheel spacer directly on the bearing, no shim, and 0.83 free space behind the bearing. The CAD has a 2.1 shim, a 2.2 wave-spring space and a front oil ring. These are INTENTIONAL but conflict with any restoration of the original wheel position (see §4.3).

8. **Hole-pattern conflicts and errors (assembly).**
   - The NGV web holes are **6 × Ø3 at PCD 34**. The tunnel rear flange is **M3 tapped at PCD 32**. This is a drawing-set inconsistency, and the CAD reproduces it: NGV PCD 34 (l.343) vs tunnel Ø3.2 at PCD 32 (l.70).
   - The CAD intake outer vane-screw holes are **Ø2.6**, which an M3 screw cannot pass. The drawing has Ø3.0 with a Ø6.0 counterbore.
   - The intake's **M5 air-start port** (3.4 wall on a 34° cone) is missing in the CAD. The CAD outer cone is 46° to Ø76 instead of 34° to Ø70.

9. **Minor items.**
   - CC hole rows are 0.15–0.5 mm off. The CC sits 2.8 mm aft of the assembly section (XCC 21.6 vs 18.8).
   - Nose cross hole: Ø2 vs Ø3. Outer bellmouth: R8.4 vs R8.5.
   - Turbine sleeve, web and rear boss shapes are assumed.
   - Details are in §2.

---

## 2. Per-part tables

Notation: "ax" is the local axial coordinate of the part, measured from its front face unless stated otherwise.

### 2.1 Compressor wheel: `GR180 Compressor.pdf`
The upper view is the machined GR180 wheel. The lower view is the Schwitzer 316954 wheel as supplied.

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| OD | Ø74 (drawn 73.96) | exducer tip / back disc | `CW_R2=37.0` (l.398) | MATCH | |
| Inducer tip | Ø55.9 | tip from LE to start of R13 | `rin-CW_TIPCL` → Ø55.6 (l.401) | MISMATCH −0.3 | CAD made 0.3 radial clearance by shrinking the wheel; drawing gives (56.2−55.9)/2 = 0.15 |
| Nose boss | Ø17.9 | hub nose | `CW_RN` (l.398) | MATCH | |
| Bore | Ø7 (drawn 36.2 long) | | r 3.5 (l.407) | MATCH | |
| Rear bore | Ø8, 2.2 deep (depth drawn only) | from spacer end | Ø8 × 2.5 (l.407) | MISMATCH minor | shaft Ø8 enters the wheel 2.0, so both work |
| Integrated spacer | Ø13 × 2.5 | rests on front 608 inner ring | −2.5..0, r 6.5 (l.407) | MATCH | |
| Back boss | Ø21.9; back face → boss end 2.3 (4.8 − 2.5) | | (l.407) | MATCH | |
| Back face → spacer end | 4.8 | | `CW_BACK=-4.8` | MATCH | |
| **LE plane → back face** | **33** | blade leading-edge plane (horizontal line 0.6 below nose top) | used as nose → back (`CW_NOSE=CW_BACK-33`, l.398) | MISMATCH | nose → back face = 33.6 |
| Nose → spacer end | 38.4 = 0.6 + 33 + 4.8 | overall | 37.8 | MISMATCH −0.6 | the 0.6 is the faced nose boss (drawn 0.59), not a shortened core |
| **Nose boss ahead of LE** | **0.6** (drawn 0.59) | | `CW_LE=CW_NOSE+5.6` (l.398) | MISMATCH +5.0 | 5.6 belongs to the *original* wheel (lower view); the GR180 nose was faced by 5.0 |
| Inducer straight | 12.93 | LE → tangent point of R13 | follows intake shroud, straight 9.1 (−32.2..−23.09) | MISMATCH | |
| Tip (shroud-side) contour | R13; centre r 40.95, 12.93 aft of LE | | intake R12.8 offset +0.3 (l.399–403) | MISMATCH | drawing arcs R13 (wheel) and R12.8 (shroud) are concentric in the assembly |
| Tip at rim → back face | 7.68 | | used as hub-at-rim (`CW_HUB_RIM=-7.68`, l.398) | MISMATCH | root cause of b2 error |
| **b2** | **6.48** | tip at rim → disc front face at rim | 2.904 (l.435 print) | MISMATCH | known |
| Disc at rim | 1.2 (7.68 − 6.48; drawn 1.23) | | 2.88 | MISMATCH | |
| Hub contour | cylinder Ø17.9 to 7.49 below the nose (drawn), then curve to r 33.4 on the disc face, flat r 33.4–37 | polyline identical to the original wheel's hub | quarter-ellipse from LE (r 8.95) to (−7.68, r 37) (l.404–405) | CAD-ASSUMED | |
| Blades | not on drawing | | 7 + 7, wrap 37° (l.409, 424) | CAD-ASSUMED | blade hand conflicts with diffuser (§1 item 4) |
| Notes | "18kg/40lbf+ thrust"; material "See parts" | | | n/a | |

Lower view, the original wheel, kept for reference only (not built):

| Feature | Value |
|---|---|
| Tip at rim | Ø86.24 |
| Back disc | Ø81.8 |
| Overall length | 44.7 |
| Nose boss protrusion | 5.6 |
| Hub straight | 12 |
| Second "12" | LE → a point on the tip line; drawn straight is 15.0, so ambiguous |
| Blade height at Ø86.24 | 5.2 |
| Disc thickness | 1.2 |
| Blade height on a line at Ø75 | 6.1 |
| Back hub | Ø19.8 |

Evaluated at Ø74, the original contour gives b ≈ 6.2. The GR180 view's 6.48 is the explicit value; the 0.3 difference is a drafting inconsistency between the two views.

### 2.2 Diffuser: `GR180 Diffuser.pdf` (Pos 4, aluminium)
Local ax = 0 at the vane front face.

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| Vane OD | Ø107 ("107 Note casing diameter") | vane tips = casing ID | `r1=53.5` (l.89) | MATCH | |
| **Vane LE** | **Ø76** (section label; front view LE points at r 38.00) | sharp LE circle | `r0=38.2` → Ø76.4 (l.89, 97) | MISMATCH +0.4 | "76.4" on the sheet is the plate rear boss; vaneless gap 1.0 vs 1.2 |
| Vane height | 7 | front face → plate face outside Ø74.4 | plate front at ax 7; pad 7.2 into plate (l.85, 109) | MATCH | |
| Overall | 17 | | rim to ax 17 (l.85) | MATCH | |
| **Recess** | **Ø74.4 × 2.0** (ax 7 → 9) | seat for the wheel back face | none; 0.5-deep ring Ø74.4–76 instead (l.308) | MISMATCH (major) | causes the CAD plate to be 4.4 thick inside Ø74.4 |
| Plate rear face | ax 11.4 (17 − 5.6; drawn 11.51) | clamps on tunnel flange | `7+T` = 11.4 (l.84–85) | MATCH | |
| Plate thickness | 2.4 inside Ø74.4; 4.4 on Ø74.4–76.4 ring; 2.0 outside Ø79.4 ("8" = ax 9 → 17) | | 4.4 from r 13 to r 44.5 | MISMATCH | CAD has extra material ax 9–11.4 on r 39.7–44.5 |
| Plate rear boss | Ø76.4 ("76,4") with ≈30° cone to Ø79.4 (drawn) | | none | MISMATCH minor | |
| Skirt | Ø89 / Ø91, to ax 17 | inner wall of axial passage | r 44.5–45.5 (l.85) | MATCH | |
| Plate corner | R3 outer; R2 inner (drawn) | | square | MISMATCH minor | |
| Bore | Ø26 | pilots on tunnel spigot Ø26 | r 13 (l.85) | MATCH | CAD tunnel has no spigot, so no pilot |
| Vane count | 13 | | 13 (l.112) | MATCH | |
| Vane flanks | straight wedge, sharp LE; flanks 66.0° and 80.0° from radial at LE; reach Ø107 at 25.55° and 35.6° of arc behind LE | | 70° / 82°, LE thickness 1.0 (l.89–100) | MISMATCH | |
| Wedge angle | **14.0°** (label; measured 13.97°) | | 12° | MISMATCH | |
| Channel divergence | **13.7°** (label; measured 13.72° = pitch − wedge) | | 15.7° (27.7 − 12) | MISMATCH | |
| Inlet throat | 7.35 (computed from vectors; not labelled) → ≈669 mm² | LE to adjacent vane flank | 6.65 → 605 mm² (doc 01) | MISMATCH | |
| "6,66", "10,67", "11,56" | spacing and length of Ø6 cutter passes (thin circles Ø6.0) | milling of axial channels | used as throat | misread | |
| **Axial vane section** | 13 channels Ø6-milled between Ø91 and Ø107, ax ≈9 → 17; area **113.63 mm²** each (labelled, hatched) | de-swirl through the 90° bend | not modelled (open annulus 2488 mm²) | DRAWING-ONLY | confirmed by `Diffuser.jpg` |
| "17,0°" | angular dim in vane field | vertex not resolved | n/a | open | |
| Vane tip corner | R6, centre (ax 6.0, r 47.5) | | (l.116–118) | MATCH | |
| Holes PCD 34 | 6 × Ø3.0 + Ø5.5 counterbore (depth not given) | screws into tunnel flange (M3) | 6 × Ø3.2, no c'bore (l.124) | MISMATCH minor | with a 2.4 plate and 0.8 back gap only a low-head screw fits |
| Holes PCD 60 | 3 × M3 (Ø2.5 + Ø3.0 circles) at 0/120/240° | inside recess | 3 × Ø3.0 plain (l.125) | MISMATCH minor | purpose not stated (puller?) |
| Vane screws | 13 × Ø3.0 "⊗" at PCD 93.0, at vane mid-thickness | | 10 × M3 tapped (l.142, 617) + 3 × Ø3.2 supply lines (l.141) | INTENTIONAL (v6) | meaning of ⊗ (tapped vs through) not stated |

### 2.3 Intake / compressor shroud: `GR180 Intake.pdf` (aluminium)
Local ax = 0 at the bellmouth lip.

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| Lip OD | Ø76.3 | | 38.15 (l.158) | MATCH | |
| Inner bellmouth | R10 | | (l.158) | MATCH | |
| Outer bellmouth | R8,5 (label; drawn ≈8.4) | | 8.4 (comment "R8.35", l.161) | MISMATCH minor | |
| Shroud bore | Ø56.2 (drawn 56.30) | inducer shroud | `rin` (l.157) | MATCH | |
| Outer wall | Ø59.5 (drawn 59.27) | wall 1.65 | `rout` (l.157) | MATCH | |
| Lip → straight | 9.17 (drawn tangent 9.82) | | `xt=9.17+17.56` (l.156) | MATCH | label used |
| Straight length | 17.56 | → ax 26.73 = start of R12.8 | (l.156) | MATCH | |
| Shroud arc | R12.8 (centre r 40.9) to the rear face, ending r 38.0 | | `Rs` (l.157, 160) | MATCH | |
| Outer cone | **34°** from ax 26.73 to **Ø70** on flange front face | | 46.4° to Ø76 (l.162) | MISMATCH | external; changes wall thickness at the air-start boss |
| **M5 air-start** | "3,4 M5 airstart": 3.4 wall measured normal to the cone | compressed-air start port | none | DRAWING-ONLY | |
| 7.87 | ax 26.73 → flange front face (ax 34.59) | | `xf0` (l.156) | MATCH | |
| Flange | Ø88 × 2 | | (l.162) | MATCH | |
| 4.59 / 2.59 | rear face → flange front / rear | | `xf0`, `xf1` (l.156) | MATCH | |
| Rear spigot | Ø76 × 2.59 | through intake-outer bore; projects 0.59 into vane LE circle Ø76 | (l.162) | MATCH | centring fit lost in CAD (vane LE Ø76.4) |
| Overall | 39.18 | | `L_in` | MATCH | |
| Flange holes | 6 × Ø3, PCD 82, 60° pitch (two on horizontal CL) | | (l.164) | MATCH | clocking not comparable |
| CAD extras | — | | starter ring, RPM boss (l.448–458) | CAD-ASSUMED (v11) | |

### 2.4 Intake outer: `GR180 Intake outer.pdf` (aluminium)
Local ax = 0 at the front of the lip.

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| Front lip | Ø106 / Ø102 × 6 | casing spigot | (l.170) | MATCH | |
| OD | Ø107 "(refer casing)" | | 53.5 | MATCH | |
| Bore | Ø76 | intake spigot | 38 | MATCH | |
| Wall | ax 6 → 7.93 (12.48 − 4.55; drawn 6.0 → 8.0) | rear face on vane front | (l.170) | MATCH | label/drawn differ 0.07 |
| Overall | 12.48 | | (l.169) | MATCH | |
| Lip | R6 concave from Ø95 ("95, 2x6 from outer"); centre (ax 14.0, r 47.5) | concentric with diffuser R6 | (13.93, 47.5) (l.169) | MATCH | |
| Holes PCD 82 | 6 × M3 (two drawn with Ø2.5 core) | intake flange screws | Ø2.5, tapped 1.9 (l.173, 615) | MATCH | only 2 mm thread in Al, per drawing |
| **Vane-screw hole** | Ø3.0 with Ø6.0 c'bore at PCD 93 (one drawn); label "2,5" unresolved | | Ø2.6 + Ø4.5 × 1.5 (l.179–180) | MISMATCH | **Ø2.6 will not clear an M3** |
| Ø88 circle (front view) | no matching step in section | | — | open | |
| Supply-line holes, O-ring recess | — | | (l.176–177) | CAD-ASSUMED (v6) | |

### 2.5 Shaft tunnel: `GR180 Shaft tunnel.pdf` (Pos 3, aluminium)

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| Overall | 107.3 | spigot face → rear face | 107.3 (l.66) | MATCH | |
| Front spigot | Ø26 × 2 | pilots diffuser bore | removed; flange face `XF=0.1` (l.65) | INTENTIONAL (v7) | loses radial centring; moves stators −1.9 |
| Front flange | Ø40, ax 2.0 → 7.03 (5.0 thick, not labelled) | | 0.1 → 7.3 (7.2) (l.66) | MISMATCH | consequence of v7 |
| Cone | 45° to Ø21 at ax 16.5 | | to (16.8, 10.5) | MATCH (≈0.3) | |
| Front bore | Ø22 × 11.3 | front 608 | (l.67) | MATCH | |
| Centre bore | Ø17 | | r 8.5 | MATCH | radial gap to shaft: 0.75 (drawing) / 1.5 (CAD) |
| Tube | Ø21 | | r 10.5 | MATCH | |
| Rear cone | ends at 107.3 − 12 = 95.3 (drawn 95.46); starts 92.96 (drawn) | | starts 95.3, ends 97.3 | MISMATCH 2.0 | external only |
| Rear flange | Ø38 × 4 at 99.3–103.3 | NGV web seat | (l.66) | MATCH | drawn 99.44–103.46 |
| Rear spigot | Ø26 × 4 (drawn 3.85) | pilots NGV web | (l.66) | MATCH | |
| Rear bore | Ø22 × 10 (step at 97.3) | rear 608 | (l.67) | MATCH | |
| Front holes | 6 × M3 at PCD 34, about 9.5 deep from the flange face | diffuser screws | Ø2.5 × 9, tapped 8.5 (l.69, 605) | MATCH | |
| **Rear holes** | **M3 tapped** (thread lines) at **PCD 32** | NGV screws | Ø3.2 through at PCD 32 (l.70) | MISMATCH | and PCD 32 ≠ NGV PCD 34 (drawing conflict) |
| Band ax 1.0–4.0 ("3") | unhatched band, lines at 1.0 (spigot) and 4.0 (across flange) | | — | open | cannot be a void; meaning unknown |
| O-ring groove | not on this sheet (see 2.11) | | Ø23.6 × 1.4 at 4.9–6.3 (l.604) | see 2.11 | |
| Oil drillings / rings | — | | (l.594, 602–603) | CAD-ASSUMED (v11–v12) | |

### 2.6 Shaft: `GR180 Shaft.pdf` (Pos 2, silversteel)
Local x = 0 at the front end.

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| Overall | 175 | | 179.8 (l.42) | INTENTIONAL (v11, +4.8 rear thread) | |
| Front thread | M6 LH × 15 ("M6 LH" leader on nose cone) | | 0–15 LH (l.42, 577) | MATCH | |
| Ø7 | 15 → 49 ("49") | compressor bore | (l.42) | MATCH | |
| Front Ø8 seat | 49 → 58 ("58"), 9.0 long | 2.0 in wheel counterbore + 7 bearing | 49 → 60.1 (l.42) | INTENTIONAL (v12, shim) | |
| **Shoulders** | **Ø11.0** at 58 and 145 (drawn; not labelled) | 608 inner-ring abutment | `re` = Ø9.58 (l.41) | MISMATCH | Ø9.58 is marginal for a 608 (inner ring about Ø12) |
| Tapers | 7°, 18 long (58 → 76, 127 → 145) | | front 60.1 → 76 (15.9) | MISMATCH (consequence) | |
| **Body** | **Ø15.5** (drawn r 7.747; same in assembly; not labelled), 76 → 127 | | Ø14 (`rm=7.0`, l.41) | MISMATCH | stiffness ×0.67, mass −15 g in CAD |
| "87" | shoulder → shoulder 58 → 145 | bearing inner faces | 60.1 → 145 | INTENTIONAL (consequence) | |
| Rear Ø8 seat | 145 → 166 (21) | rear 608 (7) + turbine hub (14) | (l.42) | MATCH | |
| Rear thread | 9 (166 → 175); hand **not stated** | turbine nut | 13.8 LH (l.42, 578) | INTENTIONAL length; hand CAD-ASSUMED | |
| Tolerances | none on GR180 sheet | | from GR130 sheet (README) | CAD-ASSUMED | |

### 2.7 Nose cone (on the Shaft sheet)

| Dimension | Drawing | CAD (line) | Status | Note |
|---|---|---|---|---|
| Length | 24.1 | (l.49) | MATCH | |
| Base | Ø17.9 | `r0` (l.48) | MATCH | sits on the wheel nose face |
| Cone | 15° half-angle; rounded tip (drawn) | straight cone (l.48–49) | MATCH (tip shape differs) | |
| Base recess | Ø10 × 2 | (l.49) | MATCH | |
| Thread | M6 LH, full thread 10 deep from recess bottom (drill Ø5 × 10.5 + point) | bore to 15, 11 tapped (l.49, 581) | INTENTIONAL (v11) | |
| Cross hole | **Ø3.0** at 20.8 from base | Ø2.0 at 21.5 (l.51–52) | MISMATCH minor | |
| Magnet / balance pockets | — | (l.53–55) | CAD-ASSUMED (v11) | |

### 2.8 NGV: `GR180 Turbine + NGV.pdf` (Inconel)
The sheet's thin-line hatched outlines are the 30 mm JetMax NGV70 blank. **1.67 (front) + 24 + 4.0 (drawn 4.33, rear) = 30** is the stock to be removed, not part geometry. Local ax = 0 at the front (gas inlet).

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| Outer ring OD | Ø72.7 (drawn 72.90) | | 36.35 (l.334) | MATCH | |
| Shroud bore | Ø70.5 | turbine tip shroud | 35.25 | MATCH | |
| Overall | 24 | | (l.334) | MATCH | |
| Entry chamfer | 26° (right half drawn 2.03 ax × 0.97 rad; left half 1.23 ax) | | 26° over 1.67 (l.333) | MISMATCH minor | 1.67 is blank stock |
| **Ø75.9 feature** | **rib Ø75.9 × 1.5 at ax 14.5–16.0** ("14,5" + rib + "8,0" = 24) | location for CC rear cone / casing (assumed) | **flange Ø75.9 × 4.0 at ax 20–24** (l.334) | MISMATCH | assembly section draws the rib at ax ≈17.2–18.4 (inconsistent) |
| Inner ring | Ø44.5 / Ø42.5, **length 15.0** (8.5 + 1.5 + "5"; "9,0" = 24 − 15) | | 14.5 (l.335) | MISMATCH −0.5 | "14.5" is the outer-ring length to the rib |
| Web | 1.5 thick at ax 8.5, bore Ø26 | on tunnel rear flange / spigot | (l.336) | MATCH | |
| Web holes | 6 × Ø3.0 "⊗" at **PCD 34** | | Ø3.2 at r 17 (l.342–343) | MATCH | conflicts with tunnel PCD 32 |
| Vanes | 15 (NGV70 blank, counted) | | 15 (l.337) | MATCH | |
| Vane LE | ax 4.0 (hub) / 3.0 (tip) | | 2.5 (l.340) | MISMATCH | |
| Vane TE | ax 12.7 (hub) / 14.0 (tip) | | ≈13.15 (hub) / 12.5 (tip) | MISMATCH | drawing TE swept aft at the tip |
| Exit angle | not dimensioned; "16°" line unresolved | | 68° / 64° (l.340) | CAD-ASSUMED | |
| "1,33", "3,33" | stock removed at web / hub (blank → part) | | — | n/a | |
| Notes | "No tip grinding" | | | MATCH | |

### 2.9 Turbine wheel: `GR180 Turbine + NGV.pdf` (lower view) + `TW70blank.pdf`
Local ax = 0 at the hub front face.

| Dimension | Drawing | References | CAD (line) | Status | Note |
|---|---|---|---|---|---|
| OD | Ø70.3 | | 35.15 (l.352–353) | MATCH | |
| Bore | Ø8 | | r 4 (l.349) | MATCH | |
| Hub length | 14.51 (TW70 blank 16.5) | | 14.51 (l.349) | MATCH | |
| **Blade / rim width** | **6.7** at root (label; drawn 6.69); **6.2** at tip (drawn) | | 7.2 root / 6.7 tip (l.349, 352) | MISMATCH +0.5 | 7.2 is the blank's rim |
| Blade root | Ø44.2 (TW70; drawn 44.45) | | r 22.1 | MATCH | |
| Rim / blade axial position | ax 6.31 → 13.0 (drawn) | | 6.2 → 13.4 | MISMATCH minor | |
| Front sleeve | Ø12.8 × 4.3 (drawn; blank hub Ø12) | bears on 608 inner ring | Ø13.2 × 6.0 | MISMATCH minor | |
| Web | tapered, ≈6.9 at r 8 → ≈2.5 at r 19 (drawn) | | 3.0 uniform | CAD-ASSUMED | |
| Rear boss | Ø13, ax 13.46 → 14.52 | nut seat | cone to Ø17 | MISMATCH minor | |
| Blades | 23 (TW70 blank, counted) | | 23 (l.351) | MATCH | |
| Blade angles | not given | | 35/40 → −58/−52 | CAD-ASSUMED | |
| Tip clearance | (70.5 − 70.3)/2 = 0.10; "No tip grinding" | | 0.10 | MATCH | per drawing (doc 01 C3 still applies) |
| Nut | not drawn ("Misc. parts not finished") | | 10 AF × 6 (l.584) | CAD-ASSUMED | |

### 2.10 Combustion chamber: `GR180 CC Inner.pdf`, `GR180 CC Outer.pdf`, Engine complete
Material SS 316. The sheets are 1:1 paper templates ("check printed sheet for sizes which may vary"). Sheet thickness is not given.

| Dimension | Drawing | CAD (line) | Status | Note |
|---|---|---|---|---|
| Inner sheet (8.1) | 131 × 77 (drawn 130.2 × 77) | (l.199) | MATCH | |
| Inner columns | 12, pitch 131/12, first 5.5 from seam (drawn 5.44) | (l.200–201) | MATCH | |
| Inner rows (from front edge, drawn) | Ø2 (×12) + Ø2.5 (×12, half pitch) at **6.0**; Ø2.5 at **15.0**; Ø3 at **25 / 35 / 45**; Ø5.5 at **55.0** | 6.0 / 15.15 / 25.2 / 35.3 / 45.4 / 55.5 (l.202) | MISMATCH 0.15–0.5 | |
| Strip 77 × 5 | drawn above the inner sheet | — | DRAWING-ONLY | probably a seam strap; purpose not stated |
| Outer sheet | 300 × 75 (two taped strips); group pitch drawn 24.72 | (l.205) | MATCH (pitch ambiguity) | |
| Outer rows (from front edge, drawn) | **7.0**: Ø2/Ø2.5/Ø2 at +6.2/+12.3/+18.5 · **15** Ø3.5 · **25** Ø3.2 · **35** Ø3.5 · **45** Ø4 · **55** Ø5.5 ×2 at ±4.87 · **64** Ø2 ×2 (0, +12.4); first group 12.36 from strip end | 7.07 / 15.08 / 25.13 / 35.18 / 45.23 / 55.4 (±4.75) / 64.4; c0 12.6 (l.206–209) | MISMATCH 0.07–0.4 | |
| Thickness | not given | 0.5 (l.184) | CAD-ASSUMED | |
| CC position (assembly) | cap face **17.82**; liners from 18.79; outer ends 93.81, inner ends 95.80 (inside NGV inner ring) | `XCC=21.6` (l.185): cap 21.1, liners 21.6–96.6 / 98.6 | MISMATCH +2.8 | CAD comment says "from assembly drawing scale" |
| Liner diameters (assembly) | inner line r 21.21, outer r 47.46 | mean Ø41.70 / Ø95.49 | MATCH (±0.3) | |
| Vaporisers | schematic Ø6 tubes at r 41.6, ax 29.8 → 93.8 (Engine complete) | 12 × Ø6, 20.1 → 86.1 at r 42.1 (l.231–238) | CAD-ASSUMED (photo) | drawing is schematic |
| Igniter / glow-plug boss | on casing at ax ≈30–38 | igniter at 33.6 (l.509) | consistent | |

### 2.11 Bearings, seals and stack hardware (from `GR180 Engine complete.pdf`)

| Item | Drawing (assembly section) | CAD v12 (line) | Status | Note |
|---|---|---|---|---|
| Bearings | 2 × 8 × 22 × 7 (608 size, drawn) | 608 hybrid (l.680–688) | MATCH | type / ceramic per user decision |
| Front bearing | x 3.47–10.47, inner ring between wheel spacer and shaft shoulder (10.50) | 2.1–9.1 (l.687) | INTENTIONAL (v12) | |
| Front shim | none | Ø12.1/Ø8 × 2.1 at 0–2.1 (l.595) | INTENTIONAL (v12) | |
| Behind front bearing | 0.83 free (10.47 → 11.3), part not drawn | wave spring 9.1–11.3 (l.693) | INTENTIONAL | |
| **Front O-ring** | cord **Ø1.78** (drawn circle), centre r 12.0 at x 6.98 (bearing mid-plane); groove **Ø26 × 2.03** at 5.97–8.00 | 22 × 1.0 FKM, gland Ø23.6 × 1.4 at 4.9–6.3 (l.604, 611) | MISMATCH | CAD "size assumed"; drawn groove depth 2.03 vs cord 1.78 gives no squeeze as drawn (schematic) |
| Wheel boss in bore | Ø21.9 boss enters Ø22 bore by 0.97 (0.05 radial) | boss ends −2.5; oil ring occupies 0.1–2.1 (l.594) | MISMATCH (consequence) | |
| Front oil ring | none | Ø22/Ø13 × 2.0 at 0.1–2.1 (l.594) | INTENTIONAL (v12) | |
| Rear bearing | 97.49–104.48 on shaft shoulder; 0.21 from bore step (97.28) | 100.3–107.3 (l.688) | INTENTIONAL (v11/v12) | |
| Rear spacer | none | Ø12.1/Ø8 × 6.3 at 94.0–100.3 (l.536) | INTENTIONAL (v11) | |
| Rear oil ring | none | Ø22/Ø13 × 3.0 at 97.3–100.3 (l.594) | INTENTIONAL (v12) | |
| Rear O-ring | none | none | MATCH | |

### 2.12 Casing, exhaust, misc.
- `GR180 turbine notes.pdf` lists "Casing & exhaust" and "Misc. parts" as **not finished**. The notes give:

  | Item | Value |
  |---|---|
  | Diameter | 107 mm (CV470 canister) |
  | Length | 240 mm |
  | Weight | 1200 g |
  | Turbine | JetMax DA 70.3 |
  | NGV | DA 70 |
  | Compressor | Schwitzer 316954 |
  | Rated thrust | 18 kg / 40 lb at 120 000 rpm |
  | EGT | ≤ 750 °C take-off; 550–650 °C normal; 730 °C max on prototype |

- Thrust data, read from the graph (approximate):

  | rpm | 33k | 60k | 80k | 100k | 105k | 110k | 117k | 119k |
  |---|---|---|---|---|---|---|---|---|
  | Thrust (N) | 7 | 32 | 65 | 115 | 133 | 145 | 178 | 186 |

  EGT is 560 °C at 33k, has a minimum of 520 °C at 80k, and reaches 720 °C at 119k.
- The CAD casing, exhaust, starter, turbine nut, fasteners, sensors, igniter and gas system are all **CAD-ASSUMED** (photo-, GR130- or catalogue-based).
- The Engine complete section shows the casing inner wall at r 53.47 (Ø106.9) from x −11.52 (intake outer front face) to about 100.5. The exhaust is schematic only.
- The horizontal "107.3 mm" at the top of the Engine complete sheet spans 102.0 mm on the sheet and matches no feature; it looks like a stray label (the tunnel length is 107.3).

---

## 3. Axial stack-up (assembly x, mm; x = 0 tunnel spigot front face)

"Drawing (assembly)" values are measured on the 1:1 Engine complete section. "Part-label chain" values build the stack from the labelled part dimensions; they are given only where they differ by more than 0.05. The rotor's axial position is **not dimensioned** anywhere. It is set by the shaft shoulders and the rear 608 against the tunnel bore step. The section draws a 0.21 gap at that step. If the bearing sits *on* the step, every rotor value below moves −0.2.

### 3.1 Stators

| Face | Drawing (assembly) | Part-label chain | CAD v12 | Δ CAD − drawing |
|---|---|---|---|---|
| Intake bellmouth lip | −48.14 | −47.92 | −49.82 | −1.68 |
| Intake flange front face | −13.51 | −13.33 | −15.23 | −1.72 |
| Shroud R12.8 tangent point | **−21.38** | −21.19 | **−23.09** | −1.71 |
| Intake flange rear = intake-outer front face | −11.52 | −11.33 | −13.23 | −1.71 |
| Intake rear face (shroud ends at r 38.0) | −8.94 | −8.74 | −10.64 | −1.70 |
| Intake-outer lip front | −17.53 | −17.33 | −19.23 | −1.70 |
| Intake-outer rear face = diffuser vane front | **−9.53** | −9.40 | **−11.30** | −1.77 |
| Diffuser vane root (plate face outside Ø74.4) | **−2.50** | −2.40 | **−4.30** | −1.80 |
| Diffuser recess floor (faces wheel back) | **−0.51** | −0.40 | none (plate face −4.30; relief ring to −3.80) | n/a |
| Diffuser plate rear = tunnel flange face | **1.99** | 2.00 | **0.10** | −1.89 |
| Diffuser skirt / axial-vane rear end | 7.49 | 7.60 | 5.70 | −1.79 |
| Tunnel spigot front face | 0.00 | 0.00 | removed (bore starts 0.10) | n/a |
| Tunnel front bore step | 11.30 | 11.30 | 11.30 | 0 |
| CC front cap face | 17.82 | n/a | 21.10 | +3.28 |
| CC liners start | 18.79 | n/a | 21.60 | +2.81 |
| NGV front (outer / inner ring) | 94.78 / 94.99 | 94.80 | 94.80 | ≈0 |
| Outer liner rear end | 93.81 | n/a | 96.60 | +2.79 |
| Inner liner rear end | 95.80 | n/a | 98.60 | +2.80 |
| Tunnel rear bore step | 97.28 | 97.30 | 97.30 | 0 |
| NGV vane LE (hub / tip) | 98.97 / 98.00 | n/a | 97.30 | −1.7 / −0.7 |
| Tunnel rear flange (front / rear face) | 99.44 / 103.46 | 99.30 / 103.30 | 99.30 / 103.30 | −0.15 |
| NGV web (front / rear) | 103.46 / 104.94 | 103.30 / 104.80 | 103.30 / 104.80 | −0.15 |
| Tunnel rear face | 107.27 | 107.30 | 107.30 | 0 |
| NGV vane TE (hub / tip) | 107.69 / 108.96 | n/a | 107.95 / 107.32 | +0.3 / −1.6 |
| NGV inner ring rear end | **109.99** | 109.80 | **109.30** | −0.69 |
| NGV Ø75.9 rib (part sheet) | 109.5–111.0 (section draws it at 112.2–113.4) | 109.3–110.8 | flange 114.8–118.8 | n/a |
| NGV outer ring rear end | 118.99 | 118.80 | 118.80 | −0.19 |

### 3.2 Rotor

| Face | Drawing (assembly) | CAD v12 | Δ CAD − drawing |
|---|---|---|---|
| Nose-cone tip | −59.0 | −61.9 | −2.9 |
| Shaft front end | **−47.50** (−47.42 drawn) | **−51.00** | −3.50 |
| Nose-cone internal thread | −36.92 → −46.92 (10 full thread) | tapped −40.0 → −51.0; bore to −52.8 (l.581) | n/a |
| Nose-cone recess bottom | −36.92 | −39.80 | −2.88 |
| Shaft M6 → Ø7 step | −32.43 | −36.00 | −3.57 |
| Wheel nose face = nose-cone base | **−34.93** | **−37.80** | −2.87 |
| Wheel LE plane | **−34.29** | **−32.20** | **+2.09** |
| Wheel tip-arc tangent (end of Ø55.9 straight) | **−21.34** | −23.09 (= shroud; CAD tip Ø55.6) | −1.75 |
| Wheel tip at rim (r 37) | **−9.00** | **−10.58** | −1.58 |
| Wheel disc front face at rim (hub at rim) | **−2.50** | **−7.68** | −5.18 |
| Wheel back face | **−1.32** | **−4.80** | **−3.48** |
| Ø21.9 boss end | +0.97 | −2.50 | −3.47 |
| Shaft Ø7 → Ø8 step | +1.48 | −2.00 | −3.48 |
| Wheel spacer end | **+3.47** | **0.00** | −3.47 |
| Front shim | none | 0.00–2.10 | n/a |
| Front 608 | **3.47–10.47** | **2.10–9.10** | −1.37 |
| Front shaft shoulder | 10.50 | 9.10 | −1.40 |
| Shaft body (Ø15.5 drawing / Ø14 CAD) | 28.49–79.50 | 25.00–76.00 | −3.50 |
| Rear shaft shoulder | **97.49** | **94.00** | −3.49 |
| Rear spacer | none | 94.00–100.30 | n/a |
| Rear 608 | **97.49–104.48** | **100.30–107.30** | +2.81 |
| Turbine hub front face | **104.48** | **107.30** | +2.82 |
| Turbine blade LE (root / tip) | 110.78 / 111.00 | 113.50 | +2.7 / +2.5 |
| Turbine blade TE (root / tip) | 117.47 / 117.22 | 120.70 / 120.20 | +3.2 / +3.0 |
| Shaft Ø8 → M6 step | **118.49** | **115.00** | −3.49 |
| Turbine hub rear face (nut seat) | 119.00 | 121.81 | +2.81 |
| Shaft rear end | 127.46 | 128.80 | +1.34 |

### 3.3 Resulting clearances and fits

| Quantity | Drawing | CAD v12 | Comment |
|---|---|---|---|
| Wheel back face → diffuser | 0.81 (recess floor) | 0.50 (plate face) | |
| Wheel rim → recess wall | 0.20 radial (Ø74 in Ø74.4) | no wall | |
| Inducer tip clearance | 0.15 radial | 0.30 radial | |
| Tip-arc / shroud-arc alignment | 0.04 axial (concentric, about 0.15 uniform) | 0.3 by construction, wrong wheel | |
| Impeller exit vs diffuser channel | tip 0.53 aft of vane front; hub flush with vane root | tip 0.72 aft of vane front; hub 3.38 ahead of plate face | |
| Vaneless radial gap | 1.0 (r 37 → 38.0) | 1.2 | |
| Diffuser inlet throat | 7.35 → ≈669 mm² | 6.65 → 605 mm² | |
| Diffuser axial passage | 13 × 113.63 = 1477 mm², vaned | 2488 mm², vaneless | |
| Wheel boss in tunnel bore | 0.97 long × 0.05 radial (labyrinth) | none | |
| Front 608 → bore step | 0.83 | 2.20 | |
| Rear 608 → bore step | 0.21 | 3.0 (oil ring) | |
| Bearing span (centre to centre) | **94.0** | **98.2** | |
| Shaft body / shoulder Ø | 15.5 / 11.0 | 14.0 / 9.58 | |
| Shaft → tunnel bore Ø17 | 0.75 radial | 1.50 radial | |
| Nose thread engagement | 10.0 | 11.2 | |
| Turbine hub pilot on Ø8 | **14.0** | **7.7** | |
| Rear thread available behind hub | 8.46 | 6.0 engaged + 1.0 proud | |
| NGV inner ring → turbine disc | 0.79 | 4.20 | |
| NGV TE → rotor LE (hub / tip) | **3.09 / 2.04** | **5.55 / 6.18** | |
| Rotor tip TE vs NGV shroud end | **−1.77 (fully shrouded)** | **+1.4 (unshrouded)** | |
| Turbine tip clearance | 0.10 radial | 0.10 radial | |
| Diffuser bore on tunnel spigot | Ø26 / Ø26 pilot | no pilot | |
| Intake spigot in vane LE circle | Ø76 / Ø76.0 pilot, 0.59 long | Ø76 in Ø76.4 (0.2 gap) | |

### 3.4 What a consistent correction requires (numbers, no files changed)

There are two consistent options. Both need the drawing wheel geometry (b2 6.48, LE 33 ahead of the back face, R13 tip arc, Ø55.9) **and** the Ø74.4 × 2.0 diffuser recess (plate 2.4 inside Ø74.4). Changing b2 alone creates a 3.3 mm tip/shroud clash.

**Option A: restore the original stack.**
1. Reinstate the tunnel spigot (flange face at 2.0). The diffuser, intake outer and intake return +1.77…1.89 to the drawing values in §3.1.
2. Set the wheel back face at −1.32. The spacer end is then at +3.47.
3. Remove the 2.1 shim and restore the shaft to 175 / Ø8 seat 49–58 / offset −47.5. Front 608 at 3.47–10.47, rear 608 at 97.49–104.48, turbine at 104.48.
4. The v12 oil rings then have no room:
   - The front ring at 0.1–2.1 collides with the wheel boss (to +0.97, r 6.5–10.95).
   - The rear ring needs 3 mm, but only 0.21 is available at the bore step.
5. The oil feed must be redesigned (for example a jet through the tunnel wall, as on the original).

**Option B: keep the v7–v12 stator frame (no spigot).**
1. Place the wheel so its tip arc is concentric with the CAD shroud: back face = −23.09 + 20.07 = **−3.02**. The impeller exit is then tip −10.70 and hub −4.22, against a vane front of −11.30 and a vane root of −4.30.
2. With the recess floor at −2.30, the back gap is 0.72.
3. The spacer end moves to **+1.78**. The front shim must shrink from 2.1 to **≈0.32** (front 608 stays at 2.1–9.1).
4. The front oil-ring ID (Ø13) must be enlarged, because the Ø13 wheel spacer then runs inside it from 0.1 to 1.78.
5. Radial centring of diffuser and shroud must be restored by another means: dowels, or a Ø26 register machined into the 7.2 flange.

**Turbine side, either option.**
- To recover the drawing's blade shrouding and NGV–rotor gaps, the turbine must sit about 2.8 mm further forward (hub at ≈104.5).
- Its Ø8 pilot should be ≥ 14 mm, so the shaft Ø8 rear seat must end at or after hub front + 14.
- With the rear oil ring kept, this is only possible if the oil ring moves forward of the bearing, out of the 3 mm in front of it, or the NGV / rear flange is moved aft by the same amount.

---

## 4. Intentional deviations (README v7–v12) and their consequences

| Change | Version | Consequence vs drawing |
|---|---|---|
| Tunnel front spigot removed; flange face 2.0 → 0.1 | v7 | Diffuser, intake outer and intake 1.77–1.9 forward. Diffuser no longer piloted on Ø26. Front flange 7.2 thick instead of 5.0. Combined with the b2 misread, this hid the missing Ø74.4 × 2 recess. |
| Diffuser "rim relief" Ø74.4–76 × 0.5 | v8 | Misreading of the Ø74.4 × 2.0 recess. |
| Front O-ring 1.1 cord "assumed", then 22 × 1.0 gland at 4.9–6.3 | v8 / v12 | Assembly shows 1.78 cord in a Ø26 × 2.03 groove at the bearing mid-plane. |
| Rear spacer 6.3 + shaft +4.8 rear | v11 | Turbine 2.82 aft. Hub pilot 14.0 → 7.7 (doc 01 C4). Blade tips 1.4 outside the NGV shroud (doc 01 I3). NGV–rotor gap 2–3 → 5.5–6.2 (doc 01 I5). |
| Nose-cone bore deepened to 15 | v11 | 11.2 engagement vs 10.0; fine. |
| Front shim 2.1, Ø8 seat to 60.1, shaft offset −51 | v12 | Shaft 3.5 forward. Bearing span 94.0 → 98.2. Shoulder abutment Ø9.58. Compressor overhang +2.1. |
| Oil-feed rings front (0.1–2.1) and rear (97.3–100.3) | v12 | Front ring occupies the space where the wheel boss runs in the bore on the drawing. Rear ring pushes the rear bearing and turbine aft. |
| Wave spring 9.1–11.3 | v12 | Drawing leaves only 0.83 behind the front bearing. |
| Diffuser vanes 1, 5, 9 used for supply lines | v6 | No conflict with drawing beyond hole sizes. |
| Shaft rear thread LH | v6 / v12 | Drawing states LH only for the front (nose) thread; see the rotation-hand item. |

---

## 5. Open items (could not be resolved from the drawings)

1. **Rotation direction and blade hand.**
   - Diffuser vane lean (drawing and photo) implies clockwise seen from the intake.
   - The CAD wheel wrap implies CCW. The CAD diffuser and wheel are of opposite hand in the CAD frame.
   - The front "M6 LH" would suit CCW if chosen for starter torque.
   - Check the physical exducer backsweep. The same check settles both thread hands.
2. **Rotor axial location.** Not dimensioned. The section shows the rear 608 0.21 from the tunnel bore step and 0.83 free behind the front 608. No spring, shim or preload part is drawn or specified.
3. **Diffuser "17,0°".** The vertex and reference lines could not be identified. 14.0° (wedge) and 13.7° (divergence) are resolved.
4. **NGV "16°" line.** A thin line from the inner-ring front corner at about 16.6° to the axis. It may relate to the vane trailing edge or exit angle, but it is not dimensioned as such. The NGV exit angle and throat are therefore **not** defined by the drawings. CAD 68/64° and 1212 mm² remain assumptions.
5. **NGV Ø75.9 rib position.** The part sheet gives ax 14.5–16.0 (from the "14,5" and "8,0" labels). The assembly section draws it at about 17.2–18.4. The function (CC rear cone or casing seat) is not stated.
6. **NGV–tunnel screw pattern.** NGV PCD 34 vs tunnel rear PCD 32 (M3 tapped). One of the two sheets is wrong, and the assembly section does not show the NGV hole. The number of tunnel rear holes is not shown (6 assumed from the NGV).
7. **Tunnel front band ax 1.0–4.0** with a "3" dimension: unhatched across spigot and flange. It is not a groove (the spigot tip would be detached). Possibly a hatching error or a separate ring.
8. **Front O-ring.** As drawn, cord 1.78 in a 2.03-deep groove gives no squeeze, so the section is schematic. Groove ID, cross-section and compound are not specified.
9. **Diffuser counterbore depths.** PCD 34 Ø5.5 counterbore depth and screw type are not given. With a 2.4 plate and a 0.8 back gap, only low-head screws fit. Whether the 13 Ø3 vane holes and the 3 PCD 60 holes are tapped or through is not stated, and the purpose of the PCD 60 holes is unknown.
10. **Intake outer.** The meaning of the "2,5" label at the vane-screw counterbore (a 2.5-deep counterbore cannot fit a 2.0 wall). The Ø88 circle in the front view has no matching step in the section.
11. **Compressor drafting inconsistency.** In the GR180 view, the LE plane sits 0.47 further from the (copied) hub curve than in the original-wheel view, and the original contour gives b ≈ 6.2 at Ø74. The labels (33, 7.68, 6.48) are taken as governing.
12. **Shaft body Ø15.5 and shoulders Ø11.0** are scaled from the 1:1 sheet (consistent on two sheets) but not labelled. Confirm on the real shaft before re-running the rotor model.
13. **CC sheet sizes.**
    - Templates are "1/1 to be checked when printed": the outer pitch is drawn 24.72 (296.6 total) against a 300 label, and the inner sheet is drawn 130.2 against a 131 label.
    - The 77 × 5 strip is unexplained.
    - Liner thickness is not given.
    - The vaporiser arrangement in the section is schematic: tubes 29.8–93.8, not attached to the cap. Photos remain the only source.
14. **Casing, exhaust, turbine nut, starter.** No finished drawings exist (per the notes). All CAD geometry for these parts is assumed.
15. **Tolerances and fits.** No tolerances or fits appear on any GR180 sheet: bearing seats, housing bores, wheel bores, spigots. All CAD fits come from the GR130 sheet or user decisions.
