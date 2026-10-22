# Graph Report - aurora-cchp  (2026-10-22)

## Corpus Check
- 92 files · ~271,721 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 72 file(s) not represented in the graph (top: .kicad_sch 37, .csv 9, (none) 6)

## Summary
- 1468 nodes · 2694 edges · 85 communities (78 shown, 7 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 108 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d4297091`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- GR180-3D FreeCAD Model
- Turbine Issues & Roadmap
- Cycle Simulation Model
- verify_gr180.py
- math
- FreeCAD Toolbar Animation
- Rotor Dynamics Model
- Generator Conversion Options
- build_plant.py
- e4_recuperator_calc.py
- hvac_design.py
- Helical Thread Modelling
- Compressor Blade Geometry
- e3_fpt_pmg_calc.py
- P
- e2_combustor_calc.py
- el_build.py
- recuperator.py
- fpt_pmg.py
- schgen.py
- E3 — interduct، توربین قدرت آزاد (FPT)، روتور FPT/PMG، یاتاقان‌ها، ژنراتور ۳۰ kW و collector اگزوز
- GR180-CCHP — مدیریت انرژی (EMS): اولویت هوشمند برق در برابر سرمایش
- os
- N
- 2. Per-part tables
- _fc
- GR180-CCHP — فلسفهٔ کنترل، ماشین حالت ECU، trip‌ها، ایمنی و life counter
- LibSymbol
- e1_turbine_fea.py
- numpy
- gg_turbine.py
- ۴. توالی‌ها
- GR180-CCHP — حالت‌های اولویت برق (MAX-POWER / BALANCED / MAX-COOLING / AUTO) و کنترل هوشمند HVAC
- SpecError
- plant_lib.py
- GR180-CCHP — دیاگرام تک‌خطی قدرت (single-line)، حالت‌های کاری، حفاظت، زمین و صاعقه
- Section
- plant_items.py
- Stream
- GR180-CCHP — طرح کیفیت و تصفیهٔ آب
- Model
- GR180-CCHP — مشخصات سیستم یکپارچه (نسخهٔ ۳.۲: برق + سرمایش جذبی، نصب روی بام، برازجان)
- GR180-CCHP — فهرست ورودی/خروجی (I/O list)
- GR180-CCHP — انتخاب قطعات (rev 2: اروپایی)
- GR180-CCHP — فهرست تجهیزات و محاسبات اندازه‌گذاری HVAC
- roof_layout.py
- GR180-CCHP — اعلام حریق، منطق آزادسازی اطفا و اینترلاک‌ها (بخش برق و کنترل)
- concept_study.py
- e1_disc_thermal_study.py
- مطالعهٔ بزرگ‌سازی به ۲۱۰ kW برق + تبدیل گرما به برق (ORC) + گرمای خانوار
- GR180-CCHP — معماری سیستم برق و کنترل (سند اصلی)
- freecad
- design_ngv
- electrical_sizing.py
- ems_study.py
- 00_summary.md
- fc_vane
- Front Bearing (sliding outer ring)
- GR180-CHP — جمع‌بندی مفهومی (پیشنهاد برای تأیید)
- GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی
- Block
- life_study.py
- ۱. BOM
- b1_ecu_erc.json
- b2_sio_erc.json
- schgen_example_erc.json
- gg_turbine_meanline.py
- disc_profile
- Route
- Compressor Wheel (Schwitzer 316954, turned down)
- فاز ۱ — بازسازی هستهٔ GR180 طبق نقشهٔ اصلی (v13A، راه A)
- GR180-CCHP — طرح جامع (master design): مختصات، رابط‌ها، تقسیم کار، BOM
- GR180-CCHP — جدول کابل‌ها (بام ↔ اتاق برق، اتاق برق ↔ سالن، داخل اسکید)
- GR180-CCHP — B6: کنترلر HVAC/BOP خودمان (بدون PLC) و HMI لمسی
- GR180-CCHP — P&ID و دیاگرام جریان مدارهای آب (HVAC / Balance of Plant)
- GR180-CCHP — جانمایی روی بام، وزن‌ها و دسترسی سرویس
- GR180-CCHP — بازبینی با سالن عایق‌دار: یک چیلر یا دو چیلر، وزن بام، بار جزئی جزیره‌ای، صدا
- Pin
- measure_geometry.py
- G
- SymbolResolver
- GR180 Shaft
- electronics/README.md
- graphify

## God Nodes (most connected - your core abstractions)
1. `main()` - 29 edges
2. `main()` - 25 edges
3. `P()` - 21 edges
4. `SpecError` - 20 edges
5. `E3 — interduct، توربین قدرت آزاد (FPT)، روتور FPT/PMG، یاتاقان‌ها، ژنراتور ۳۰ kW و collector اگزوز` - 19 edges
6. `N()` - 18 edges
7. `C()` - 17 edges
8. `GR180-CCHP — مدیریت انرژی (EMS): اولویت هوشمند برق در برابر سرمایش` - 16 edges
9. `Section` - 15 edges
10. `_fc()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `۵. جانمایی` --references--> `svg()`  [INFERRED]
  docs/hvac/08_fire_suppression.md → sim/hvac/roof_layout.py
- `۱. ورودی‌ها و فرض‌های مرزی` --references--> `cycle()`  [INFERRED]
  docs/engine/E3_fpt_pmg.md → sim/concept_study.py
- `GR180-CCHP — جانمایی روی بام، وزن‌ها و دسترسی سرویس` --references--> `svg()`  [INFERRED]
  docs/hvac/04_roof_layout.md → sim/hvac/roof_layout.py
- `۰. مبنای طراحی` --references--> `cchp()`  [INFERRED]
  docs/hvac/02_equipment_sizing.md → sim/cchp_study.py
- `C4: Turbine Centred on Only 7.7 mm of 8 mm Seat` --semantically_similar_to--> `Turbine Nut Thread Engagement Only 2.2 mm`  [INFERRED] [semantically similar]
  docs/01_analysis_review_v12.md → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Critical v12 Review Findings C1-C5** — docs_01_analysis_review_v12_c1_mass_flow_mismatch, docs_01_analysis_review_v12_c2_critical_speed_mode, docs_01_analysis_review_v12_c3_turbine_tip_clearance, docs_01_analysis_review_v12_c4_turbine_centring, docs_01_analysis_review_v12_c5_bearing_life [EXTRACTED 1.00]
- **Generator Conversion Architectures** — docs_01_analysis_review_v12_arch_a_pm_on_shaft, docs_01_analysis_review_v12_arch_b_fpt_gearbox, docs_01_analysis_review_v12_arch_c_fpt_hs_pm, docs_01_analysis_review_v12_recuperator, docs_01_analysis_review_v12_chp [EXTRACTED 1.00]
- **GR180 Rotor Stack (compressor, shaft, turbine, bearings, clamp parts)** — readme_compressor_wheel, readme_shaft, readme_turbine, readme_nose_cone, readme_608_hybrid_ceramic_bearings, readme_front_stack_shim, readme_rear_stack_spacer [INFERRED 0.85]

## Communities (85 total, 7 thin omitted)

### Community 0 - "GR180-3D FreeCAD Model"
Cohesion: 0.16
Nodes (21): I6: Gas Supply Needs Booster or CNG, I7: Permax 280 Starter Likely Underpowered, Casing (CV470 can, photo-based), Combustion Chamber Front Cap, EGT Type K Thermocouple, Exhaust Duct (SS 0.5), M12x1 Gas Bulkhead Fitting, GR130 Engine (reference design) (+13 more)

### Community 1 - "Turbine Issues & Roadmap"
Cohesion: 0.15
Nodes (19): C3: Turbine Tip Clearance Only 0.10 mm, ECU Control and Safety Systems, I3: 1.4 mm Unshrouded Turbine Tip Trailing Edge, I4: Misleading NGV Angle in README, I5: NGV-to-Rotor Axial Gap ~5.5 mm, I8: Rotor Stress and Burst Containment, P1: Hard-Coded Output Path, P2: No Git Version Control (+11 more)

### Community 2 - "Cycle Simulation Model"
Cohesion: 0.16
Nodes (14): calibrate(), chain(), compressor_checks(), fmt_pt(), free_power_turbine(), gas_generator(), main(), match_turbojet() (+6 more)

### Community 3 - "verify_gr180.py"
Cohesion: 0.31
Nodes (7): I1: v12 Interference Check Incomplete, I2: Intake Outer M3 Thread Engagement FAIL, Modelled Helical Threads (v12), gap(), pr(), sh(), sweep()

### Community 4 - "math"
Cohesion: 0.09
Nodes (24): arcpts(), bearing608(), cam_blade(), count_holes(), _cum(), D_(), drill(), half_ellipse() (+16 more)

### Community 5 - "FreeCAD Toolbar Animation"
Cohesion: 0.27
Nodes (8): _doc(), _home(), next_step(), tick(), _objs(), reset(), show_all(), spin()

### Community 6 - "Rotor Dynamics Model"
Cohesion: 0.23
Nodes (7): build(), criticals(), disks_from_json(), gen_rotor(), main(), shaft_r(), whirl()

### Community 7 - "Generator Conversion Options"
Cohesion: 0.18
Nodes (14): Architecture A: PM Generator on Core Shaft, Architecture B: Free Power Turbine + Two-Stage Gearbox, Architecture C: FPT + High-Speed PM Generator + Inverter, C2: Bending/Conical Mode Near Operating Speed, C5: Bearing Life for Generator Duty, Campbell Diagram (sim/gr180_campbell.png), Combined Heat and Power (CHP), Generator Conversion Options (+6 more)

### Community 9 - "e4_recuperator_calc.py"
Cohesion: 0.05
Nodes (41): a347(), cold_distributors(), Core, cp347(), creep_hours(), cycle_sensitivity(), Duct, E347() (+33 more)

### Community 10 - "hvac_design.py"
Cohesion: 0.06
Nodes (50): bearing_loss_W(), build_pumps(), ch_dp(), chiller_pair(), coil_kW(), design_hx(), dew_point(), dew_points() (+42 more)

### Community 11 - "Helical Thread Modelling"
Cohesion: 0.33
Nodes (4): prism_n(), tap(), tapcut(), thread_rod()

### Community 12 - "Compressor Blade Geometry"
Cohesion: 0.50
Nodes (5): _at(), cw_blade(), cw_hub_in(), cw_theta(), cw_tip()

### Community 13 - "e3_fpt_pmg_calc.py"
Cohesion: 0.06
Nodes (46): allowed_count(), b_gap_2pole(), beam_sections(), bearings(), blade_campbell(), blade_counts(), blade_modes(), blade_props() (+38 more)

### Community 14 - "P"
Cohesion: 0.07
Nodes (31): bend(), loop_channel(), crystal(), crystal32k(), decaps(), di_bank(), input_24v(), iso_can() (+23 more)

### Community 15 - "e2_combustor_calc.py"
Cohesion: 0.07
Nodes (29): annular_plate_t(), annulus_area(), annulus_h(), casing_T(), cp_air(), cycle_e2(), Da(), _eps_cf() (+21 more)

### Community 16 - "el_build.py"
Cohesion: 0.10
Nodes (17): add(), box(), build_er(), build_roof(), build_room_ref(), build_route(), Cab, clash_check() (+9 more)

### Community 17 - "recuperator.py"
Cohesion: 0.09
Nodes (21): add(), bellows(), boss(), box(), cold_spool(), cyl(), detail_sample(), disk_flange() (+13 more)

### Community 18 - "fpt_pmg.py"
Cohesion: 0.08
Nodes (16): add(), area(), blade_row(), cone_tube(), frustum(), inside(), itf(), offset_curve() (+8 more)

### Community 19 - "schgen.py"
Cohesion: 0.10
Nodes (17): _atom(), build(), cmd_find(), cmd_pins(), compare_netlist(), fmt(), _is_flat(), load_spec() (+9 more)

### Community 20 - "E3 — interduct، توربین قدرت آزاد (FPT)، روتور FPT/PMG، یاتاقان‌ها، ژنراتور ۳۰ kW و collector اگزوز"
Cohesion: 0.07
Nodes (29): E3 — interduct، توربین قدرت آزاد (FPT)، روتور FPT/PMG، یاتاقان‌ها، ژنراتور ۳۰ kW و collector اگزوز, ۰. خلاصهٔ طراحی, ۱۰. overspeed و spin test (مشخصات), ۱۱. ژنراتور PMG (30 kW پیوسته @ 60k), ۱۱-۱ انتخاب ۲ قطب, ۱۱-۲ ابعاد و پارامترها (تحلیلی، حل دقیق دوبعدی میدان 2 قطب بین شفت و استاتور آهنی), ۱۱-۳ تلفات و راندمان, ۱۱-۴ خنک‌کاری (+21 more)

### Community 21 - "GR180-CCHP — مدیریت انرژی (EMS): اولویت هوشمند برق در برابر سرمایش"
Cohesion: 0.07
Nodes (27): GR180-CCHP — مدیریت انرژی (EMS): اولویت هوشمند برق در برابر سرمایش, ۰. خلاصه, ۱. چرا «خاموش کردن سرمایش» درست نیست؟ (ساعت طراحی تابستان), ۱۰. بهینه‌ساز اختیاری (B5), ۱۱. HMI، ثبت و گزارش, ۱۲. سنسورها و کنتورهای اضافه‌شده برای EMS, ۱۳. تست و commissioning, ۱۴. سؤال‌های باز EMS (+19 more)

### Community 22 - "os"
Cohesion: 0.12
Nodes (7): _root(), _root(), main(), md_escape(), counts(), main(), math_ceil()

### Community 23 - "N"
Cohesion: 0.19
Nodes (11): _effects(), lprop(), pin(), _load_footprint(), N(), pcb_outline(), _prop(), Sym (+3 more)

### Community 24 - "2. Per-part tables"
Cohesion: 0.08
Nodes (23): 0. Method, datum and reliability, 1. Summary: most important discrepancies, ranked by functional impact, 2.10 Combustion chamber: `GR180 CC Inner.pdf`, `GR180 CC Outer.pdf`, Engine complete, 2.11 Bearings, seals and stack hardware (from `GR180 Engine complete.pdf`), 2.12 Casing, exhaust, misc., 2.1 Compressor wheel: `GR180 Compressor.pdf`, 2.2 Diffuser: `GR180 Diffuser.pdf` (Pos 4, aluminium), 2.3 Intake / compressor shroud: `GR180 Intake.pdf` (aluminium) (+15 more)

### Community 25 - "_fc"
Cohesion: 0.16
Nodes (14): cyl(), _fc(), fc_build(), log(), fc_disc(), fc_full_wheel(), fc_ngv(), fc_sector() (+6 more)

### Community 26 - "GR180-CCHP — فلسفهٔ کنترل، ماشین حالت ECU، trip‌ها، ایمنی و life counter"
Cohesion: 0.10
Nodes (20): GR180-CCHP — فلسفهٔ کنترل، ماشین حالت ECU، trip‌ها، ایمنی و life counter, ۱. لایه‌های کنترل و ایمنی, ۱۰. شمارندهٔ عمر (life counter) و شمارنده‌های نگهداری, ۱۱. ارتباط ECU با بردها (خلاصه؛ جزئیات در سند 00 §۴), ۱۲. پارامترهای اصلی (مقدار اولیه → نهایی‌سازی در تست), ۱۳. برنامهٔ آزمون نرم‌افزار و سخت‌افزار (پیش از موتور), ۲. ماشین حالت, ۲-۱. جدول حالت‌ها (+12 more)

### Community 27 - "LibSymbol"
Cohesion: 0.15
Nodes (6): LibSymbol, sx_find(), sx_findall(), sx_parse(), SymbolLibrary, _unescape()

### Community 28 - "e1_turbine_fea.py"
Cohesion: 0.15
Nodes (11): axisym_mesh(), axisym_run(), axisym_study(), material_cards(), omega(), read_dat_stresses(), read_frd(), run_ccx() (+3 more)

### Community 29 - "numpy"
Cohesion: 0.12
Nodes (10): camber_theta(), passage_check(), polygon_area_centroid(), project_to_plane(), rot_x(), sample_profile(), sector_theta_table(), theta_mid() (+2 more)

### Community 30 - "gg_turbine.py"
Cohesion: 0.20
Nodes (13): aero_report(), am_exit_angle(), beta2(), beta3(), blade_pull_estimate(), design_rotor(), mach_rot_exit(), required_throats() (+5 more)

### Community 31 - "۴. توالی‌ها"
Cohesion: 0.11
Nodes (17): GR180-CCHP — توالی‌های کنترلی و فهرست I/O کنترلر پلانت, ۱. معماری کنترل (طبق قرارداد نهایی docs/electrical، CONTRACT v3), ۲. حالت‌های کار, ۳. setpointها (قابل تنظیم از HMI), ۴. توالی‌ها, ۴-۱. راه‌اندازی (START-UP) از حالت سرد, ۴-۱۰. گزارش‌دهی از راه دور (B5), ۴-۲. کار عادی تابستان (SUMMER-CCHP) (+9 more)

### Community 32 - "GR180-CCHP — حالت‌های اولویت برق (MAX-POWER / BALANCED / MAX-COOLING / AUTO) و کنترل هوشمند HVAC"
Cohesion: 0.11
Nodes (18): GR180-CCHP — حالت‌های اولویت برق (MAX-POWER / BALANCED / MAX-COOLING / AUTO) و کنترل هوشمند HVAC, ۱-ب. کار ۲۴ ساعته و فروش برق به شبکه (پاسخ کاربر ۵), ۱. نتیجه: برق خالص و سرمایش در هر حالت, ۲. حالت‌ها = `EMS_MODE` + اصلاح‌کننده‌ها (رجیسترهای docs/electrical/06 §۴), ۳. AUTO, ۴. توالی‌ها و قیود, ۴-۱. قیود چیلرهای LiBr (به جای هر عدد، عدد دفترچهٔ سازنده), ۴-۲. اجرای گام‌های MAX-POWER (merit order EMS) در سمت HVAC (+10 more)

### Community 33 - "SpecError"
Cohesion: 0.12
Nodes (8): Board, _check_net_name(), namew(), norm_pin_name(), Part, resolve_part(), ResolvedPart, SpecError

### Community 34 - "plant_lib.py"
Cohesion: 0.15
Nodes (9): auto_supports(), clash_check(), connected_overlap_check(), _dedupe(), in_any_footprint(), joint_points(), M(), step_overs() (+1 more)

### Community 35 - "GR180-CCHP — دیاگرام تک‌خطی قدرت (single-line)، حالت‌های کاری، حفاظت، زمین و صاعقه"
Cohesion: 0.12
Nodes (17): GR180-CCHP — دیاگرام تک‌خطی قدرت (single-line)، حالت‌های کاری، حفاظت، زمین و صاعقه, ۱. تصمیم معماری (rev 3), ۱۰. صدا, ۲. دیاگرام تک‌خطی, ۳-الف. کار عادی v1: موازی با شبکه، zero-export, ۳-ب. قطع شبکه → backup (جزیره), ۳-ج. خرابی اینورتر, ۳. حالت‌های کاری و رفتار انتقال (+9 more)

### Community 36 - "Section"
Cohesion: 0.19
Nodes (4): make(), fc_blade(), Section, at()

### Community 37 - "plant_items.py"
Cohesion: 0.26
Nodes (11): dunnage(), equipment(), mounts(), rnz(), angle_post(), box(), cyl(), cylp() (+3 more)

### Community 38 - "Stream"
Cohesion: 0.18
Nodes (5): dr_hub(), hub_cap_plane(), r_hub(), Stream, StreamOffset

### Community 39 - "GR180-CCHP — طرح کیفیت و تصفیهٔ آب"
Cohesion: 0.13
Nodes (14): GR180-CCHP — طرح کیفیت و تصفیهٔ آب, ۱. آب ورودی, ۲. حدود کیفیت آب, ۳. گزینه‌های آب جبرانی برج (با سختی‌گیر), ۴. سیستم سختی‌گیر، RO و blend, ۵. برنامهٔ تصفیهٔ برج خنک‌کن, ۵-۱. کنترل blowdown, ۵-۲. بازدارندهٔ رسوب و خوردگی (+6 more)

### Community 40 - "Model"
Cohesion: 0.14
Nodes (3): Model, Part_, pipe_od()

### Community 41 - "GR180-CCHP — مشخصات سیستم یکپارچه (نسخهٔ ۳.۲: برق + سرمایش جذبی، نصب روی بام، برازجان)"
Cohesion: 0.14
Nodes (13): GR180-CCHP — مشخصات سیستم یکپارچه (نسخهٔ ۳.۲: برق + سرمایش جذبی، نصب روی بام، برازجان), کیفیت آب, ۰. تصمیم‌های قطعی‌شده (v1), ۱. نقطهٔ کار در شرایط سایت (ورودی ۳۰ °C، ۵۰ m، بدون بوستر، ε 0.90), ۲-الف. تری‌جنریشن (برق + سرما + آب گرم) — نتیجهٔ `sim/cchp_study.py`, ۲. بار و گرما, ۳. ساخت — نظر نهایی, ۴. محرک‌های عمر در کار ۲۴/۷ (حدود ۸۰۰۰ ساعت در سال) (+5 more)

### Community 42 - "GR180-CCHP — فهرست ورودی/خروجی (I/O list)"
Cohesion: 0.14
Nodes (14): A. سرعت روتورها و ارتعاش, B. دماهای مسیر گاز و یاتاقان, C. فشارهای مسیر هوا و گاز داغ, D. قطار سوخت گاز (fuel gas train) و جرقه/شعله, E. سیستم روغن, F. مدار خنک‌کاری PMG و الکترونیک قدرت + سیم‌پیچ ژنراتور, G. جعبه (enclosure)، ایمنی، نشت گاز، آتش، درها, GR180-CCHP — فهرست ورودی/خروجی (I/O list) (+6 more)

### Community 43 - "GR180-CCHP — انتخاب قطعات (rev 2: اروپایی)"
Cohesion: 0.14
Nodes (14): GR180-CCHP — انتخاب قطعات (rev 2: اروپایی), جدول جایگزینی (rev 1 → rev 2), ۰. سیاست تأمین (تصمیم کاربر، D17), ۱. B1 — ECU (اتاق برق), ۱۰. پایش از راه دور (اینترنت ثابت با IP ثابت؛ هشدار Telegram و SMS), ۱۱. اعلام و اطفای حریق, ۲. B2 — I/O سنسورها (روی بام، RP-1), ۳. B3 — یکسوساز فعال SiC (PEB) و B3b (+6 more)

### Community 44 - "GR180-CCHP — فهرست تجهیزات و محاسبات اندازه‌گذاری HVAC"
Cohesion: 0.14
Nodes (14): D-101 (damper دوراهی) و ST-1 (دودکش), GR180-CCHP — فهرست تجهیزات و محاسبات اندازه‌گذاری HVAC, ۰. مبنای طراحی, ۱. مبدل اگزوز به آب HX-1, ۱۰. فهرست خلاصهٔ تجهیزات, ۲. چیلرهای جذبی CH-1 و CH-2, ۳. برج خنک‌کن CT-1, ۴. پمپ‌ها (+6 more)

### Community 45 - "roof_layout.py"
Cohesion: 0.31
Nodes (10): alternatives(), centre(), checks(), footprint(), main(), overlap(), rect_circle_dist(), svg() (+2 more)

### Community 46 - "GR180-CCHP — اعلام حریق، منطق آزادسازی اطفا و اینترلاک‌ها (بخش برق و کنترل)"
Cohesion: 0.15
Nodes (13): GR180-CCHP — اعلام حریق، منطق آزادسازی اطفا و اینترلاک‌ها (بخش برق و کنترل), ۱. اصول, ۲. ناحیه‌ها و آشکارسازها, ۳. پنل FCP, ۴-الف. FZ1: جعبهٔ موتور, ۴-ب. FZ2: اتاق برق و باتری, ۴. توالی‌ها, ۴-ج. FZ3: تابلوهای بام (+5 more)

### Community 47 - "concept_study.py"
Cohesion: 0.23
Nodes (7): ۱. ورودی‌ها و فرض‌های مرزی, cycle(), gas_booster_kW(), main(), main(), run(), size()

### Community 48 - "e1_disc_thermal_study.py"
Cohesion: 0.26
Nodes (7): boundary_edges(), case(), classify(), main(), norton_cards(), report(), thermal()

### Community 49 - "مطالعهٔ بزرگ‌سازی به ۲۱۰ kW برق + تبدیل گرما به برق (ORC) + گرمای خانوار"
Cohesion: 0.17
Nodes (11): مطالعهٔ بزرگ‌سازی به ۲۱۰ kW برق + تبدیل گرما به برق (ORC) + گرمای خانوار, ۱. جدول اصلی (۲۱۰ kW برق خالص در کار دائم), ۲. توربین چقدر بزرگ می‌شود؟ (حالت B، پیشنهادی برای ۲۱۰ kW), ۳. تبدیل گرما به برق بیشتر (ORC), ۴. گرما برای خانوار — چند خانوار؟, ۵. برق دائم یک دستگاه مشخص (ماشین کلاس B، دبی هوا ۱.۵۴ kg/s), ۶. مقایسهٔ کنار هم: فناوری خودمان (GR180 بزرگ‌شده) در برابر کلاس ۲۰۰ kW — کار دائم, ۷. هزینه و پیچیدگی ساخت (تخمین اولیه، ±۴۰ %) (+3 more)

### Community 50 - "GR180-CCHP — معماری سیستم برق و کنترل (سند اصلی)"
Cohesion: 0.17
Nodes (12): GR180-CCHP — معماری سیستم برق و کنترل (سند اصلی), ۰. نقشهٔ اسناد, ۱. مبنای طراحی (rev 3، با پاسخ‌های کاربر), ۱۰. سؤال‌های باز برای کاربر, ۲. معماری کلی و محل بردها, ۳. بردها و تابلوها (قطعات اروپایی، 04), ۴. شبکهٔ ارتباطی, ۵. تغذیهٔ الکترونیک و دامنه‌های ایزوله (+4 more)

### Community 51 - "freecad"
Cohesion: 0.25
Nodes (6): save_part(), build_route(), comp_len(), comp_shape(), i_beam(), unit()

### Community 52 - "design_ngv"
Cohesion: 0.20
Nodes (9): alpha2(), carter_mach_factor(), design_ngv(), make(), mach_ngv_exit(), ngv_params(), _solve_section(), f() (+1 more)

### Community 53 - "electrical_sizing.py"
Cohesion: 0.33
Nodes (9): battery(), cables(), dump_resistor(), hdr(), inverter_surge(), overspeed(), pmg_rectifier(), precharge() (+1 more)

### Community 54 - "ems_study.py"
Cohesion: 0.31
Nodes (7): bisect(), engine_levers(), main(), operating_point(), p_eng(), part_load(), pel()

### Community 55 - "00_summary.md"
Cohesion: 0.18
Nodes (7): GR180-CCHP — طراحی تأسیسات و HVAC (خلاصه), اعداد کلیدی (طراحی تابستان: ورودی موتور ۱۵ °C، هوای بیرون ۴۶ °C، WB ۲۸ °C؛ بستهٔ تجهیزات rev B؛ سالن عایق), تعامل با بخش‌های دیگر, سازگاری با docs/03, فهرست, پرسش‌های باز, یافته‌های مهم (نیاز به توجه)

### Community 56 - "fc_vane"
Cohesion: 0.20
Nodes (5): bs_wire(), fc_vane(), mk(), fillet_offset(), resample_closed()

### Community 57 - "Front Bearing (sliding outer ring)"
Cohesion: 0.38
Nodes (9): P3: README Outdated, Front Bearing (sliding outer ring), Front Bearing O-ring (22x1.0 FKM 75), Front Stack Shim 12/8 x2.1, Oil-Feed Rings (front/rear, 4x 0.45 mm jets), Front Oil Jet (0.5 mm at 42 deg), Shaft Tunnel, Spacer Washer 21.8/16 x1.5 (+1 more)

### Community 58 - "GR180-CHP — جمع‌بندی مفهومی (پیشنهاد برای تأیید)"
Cohesion: 0.20
Nodes (9): GR180-CHP — جمع‌بندی مفهومی (پیشنهاد برای تأیید), ۱. هدف‌ها (از کاربر), ۲. داده‌های جدید که تصمیم را عوض کرد, ۳. مقایسهٔ معماری‌ها (طراحی در ISA 15 °C، هوا 0.40 kg/s), ۴. پیشنهاد: S3 — «GR180 + توربین قدرت آزاد + ژنراتور پرسرعت + recuperator + CHP», ۵. تغییرات لازم در هر زیرسیستم, ۶. سنسورها و کنترل, ۷. برنامهٔ شبیه‌سازی و ابزار (روی Mac M4، 16 GB) (+1 more)

### Community 59 - "GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی"
Cohesion: 0.20
Nodes (10): GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی, ۱. ناحیه‌ها, ۲. انتخاب عامل, ۳. مقدار عامل, ۴. تجهیزات, ۵. جانمایی, ۶. توالی (پیشنهاد برای منطق docs/electrical), ۷. گزینهٔ جایگزین FZ1 (+2 more)

### Community 60 - "Block"
Cohesion: 0.24
Nodes (4): Block, _label_len(), pack_blocks(), snap()

### Community 61 - "life_study.py"
Cohesion: 0.31
Nodes (6): creep_hours(), line(), lmp(), main(), point(), site()

### Community 63 - "۱. BOM"
Cohesion: 0.22
Nodes (8): GR180-CCHP — فهرست اقلام (BOM) HVAC و بار الکتریکی, الف) اگزوز و آب داغ, ب) چیلر و آب سرد, ج) آب خنک‌کن، برج و تصفیهٔ آب, د) لوله‌کشی، عایق و ابزار دقیق, ه) اطفای حریق (`08_fire_suppression.md`), ۱. BOM, ۲. بار الکتریکی تجهیزات HVAC

### Community 64 - "b1_ecu_erc.json"
Cohesion: 0.22
Nodes (8): coordinate_units, date, ignored_checks, included_severities, kicad_version, $schema, sheets, source

### Community 65 - "b2_sio_erc.json"
Cohesion: 0.22
Nodes (8): coordinate_units, date, ignored_checks, included_severities, kicad_version, $schema, sheets, source

### Community 66 - "schgen_example_erc.json"
Cohesion: 0.22
Nodes (8): coordinate_units, date, ignored_checks, included_severities, kicad_version, $schema, sheets, source

### Community 67 - "gg_turbine_meanline.py"
Cohesion: 0.36
Nodes (6): design(), legacy(), mu_gas(), report(), soderberg(), zweifel_pitch()

### Community 68 - "disc_profile"
Cohesion: 0.25
Nodes (3): disc_profile(), _fillet_corner(), flare_bezier()

### Community 69 - "Route"
Cohesion: 0.32
Nodes (5): hall(), add(), piping(), add(), Route

### Community 70 - "Compressor Wheel (Schwitzer 316954, turned down)"
Cohesion: 0.32
Nodes (8): C1: Compressor/Diffuser/Thrust Mass-Flow Mismatch, Simulated Design Point (176.5 N), Compressor Wheel (Schwitzer 316954, turned down), Diffuser (Pos 4, aluminium), GR180 Compressor.pdf, GR180 Engine complete.pdf, Nose Cone (M6 LH), RPM Hall Sensor (Allegro A1120EUA)

### Community 71 - "فاز ۱ — بازسازی هستهٔ GR180 طبق نقشهٔ اصلی (v13A، راه A)"
Cohesion: 0.25
Nodes (7): فاز ۱ — بازسازی هستهٔ GR180 طبق نقشهٔ اصلی (v13A، راه A), ۱. چه چیزی عوض شد, ۲. جهت چرخش و رزوه‌ها, ۳. اعداد کلیدی v13A (اندازه‌گیری روی CAD), ۴. دینامیک روتور (شفت درست), ۵. چک کامل تداخل (۳۳ قطعه، همهٔ جفت‌ها، ۲۱ دقیقه), ۶. باز / مرحلهٔ بعد

### Community 72 - "GR180-CCHP — طرح جامع (master design): مختصات، رابط‌ها، تقسیم کار، BOM"
Cohesion: 0.25
Nodes (7): GR180-CCHP — طرح جامع (master design): مختصات، رابط‌ها، تقسیم کار، BOM, ۱. دستگاه‌های مختصات (برای همهٔ طراحان، اجباری), ۲. نقطهٔ طراحی پیوسته (همهٔ زیرسیستم‌ها بر این مبنا), ۳. رابط‌های پکیج EP-1 (در قاب ROOF، m), ۴. تقسیم کار و فایل‌ها, ۵. فهرست قطعات (BOM), ۶. تعریف «تمام‌شده»

### Community 73 - "GR180-CCHP — جدول کابل‌ها (بام ↔ اتاق برق، اتاق برق ↔ سالن، داخل اسکید)"
Cohesion: 0.25
Nodes (8): GR180-CCHP — جدول کابل‌ها (بام ↔ اتاق برق، اتاق برق ↔ سالن، داخل اسکید), ۱. کلاس‌بندی و قواعد مسیر (EN 50174-2 / IEC 61000-5-2), ۲. کابل‌های قدرت, ۳. کابل‌های کنترل و داده بام ↔ ER, ۴-ب. کابل‌های اعلام و اطفای حریق ([07](07_fire_protection.md)), ۴. کابل‌های ER و ER ↔ سالن, ۵. کابل‌های سنسور داخل اسکید (نوعی), ۶. خلاصهٔ مقدار (برای برآورد خرید، +۱۵ ٪)

### Community 74 - "GR180-CCHP — B6: کنترلر HVAC/BOP خودمان (بدون PLC) و HMI لمسی"
Cohesion: 0.25
Nodes (8): GR180-CCHP — B6: کنترلر HVAC/BOP خودمان (بدون PLC) و HMI لمسی, ۱. معماری: ماژولار روی ریل DIN (مثل یک PLC، ولی برد خودمان), ۲. ماژول‌ها (قطعات اروپایی، 04 §۶), ۳. پیکربندی‌ها (از `docs/hvac/io_list.csv` دور ۳، 178 ردیف؛ اعداد HVAC با +25 % ذخیره), ۴. نرم‌افزار, ۵. HMI لمسی B6 (Riverdi + TouchGFX), ۶. فایل‌های طراحی, ۷. سؤال‌های باز

### Community 75 - "GR180-CCHP — P&ID و دیاگرام جریان مدارهای آب (HVAC / Balance of Plant)"
Cohesion: 0.25
Nodes (7): GR180-CCHP — P&ID و دیاگرام جریان مدارهای آب (HVAC / Balance of Plant), ۰. نمای کلی (block flow), ۱. اگزوز، مدار آب داغ، DHW و گرمایش زمستان, ۲. مدار آب سرد (۷/۱۲ °C) و changeover زمستان, ۳. مدار آب خنک‌کن، برج، آب جبرانی، blowdown و تصفیه, ۴. فهرست خطوط (line list) — نتیجهٔ `hvac_design.py`, ۵. راهنمای تگ‌ها

### Community 76 - "GR180-CCHP — جانمایی روی بام، وزن‌ها و دسترسی سرویس"
Cohesion: 0.29
Nodes (6): GR180-CCHP — جانمایی روی بام، وزن‌ها و دسترسی سرویس, ۱. منطق جانمایی, ۲. بررسی فاصله‌ها (خروجی اسکریپت), ۳. وزن‌ها برای کنترل سازه, ۴. دسترسی سرویس و نصب, ۵. ابعاد کلی

### Community 77 - "GR180-CCHP — بازبینی با سالن عایق‌دار: یک چیلر یا دو چیلر، وزن بام، بار جزئی جزیره‌ای، صدا"
Cohesion: 0.29
Nodes (6): GR180-CCHP — بازبینی با سالن عایق‌دار: یک چیلر یا دو چیلر، وزن بام، بار جزئی جزیره‌ای، صدا, ۱. اثر سالن عایق‌دار, ۲. یک SC10 یا SC10 + SC5؟, ۳. وزن بام: چه چیزی آن را ~۷.۴ t می‌کند و چطور کمش کنیم, ۴. بار جزئی جزیره‌ای v1 (۱۰۰–۱۰۵k rpm، TIT ۷۵۰ °C), ۵. صدا (بدون حد قانونی؛ «ساکت‌تر بهتر»)

### Community 79 - "measure_geometry.py"
Cohesion: 0.40
Nodes (3): GR180 Full Analysis and v12 Design Review, blade_row_throat(), pr()

### Community 82 - "GR180 Shaft"
Cohesion: 1.00
Nodes (3): C4: Turbine Centred on Only 7.7 mm of 8 mm Seat, Rear Stack Spacer 12/8 x6.3, GR180 Shaft

## Knowledge Gaps
- **9 isolated node(s):** `/Users/ahmadrezaasiyaeemoghadam/.local/bin/graphify-mcp`, `I6: Gas Supply Needs Booster or CNG`, `I7: Permax 280 Starter Likely Underpowered`, `GR180 Compressor.pdf`, `JetCat P180 (TSFC reference class)` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 664 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `svg()` connect `roof_layout.py` to `GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی`, `GR180-CCHP — جانمایی روی بام، وزن‌ها و دسترسی سرویس`, `math`?**
  _High betweenness centrality (0.263) - this node is a cross-community bridge._
- **What connects `/Users/ahmadrezaasiyaeemoghadam/.local/bin/graphify-mcp`, `I6: Gas Supply Needs Booster or CNG`, `I7: Permax 280 Starter Likely Underpowered` to the rest of the system?**
  _9 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `math` be split into smaller, more focused modules?**
  _Cohesion score 0.09365079365079365 - nodes in this community are weakly interconnected._
- **Why does `۵. جانمایی` connect `GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی` to `roof_layout.py`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Should `build_plant.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Why does `GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی` connect `GR180-CCHP — سیستم اطفای حریق با گاز پاک (FK-5-1-12)، بخش مکانیکی` to `00_summary.md`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Should `e4_recuperator_calc.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05009009009009009 - nodes in this community are weakly interconnected._