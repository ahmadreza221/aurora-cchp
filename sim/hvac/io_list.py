# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP balance-of-plant (HVAC / water side) instrument and actuator I/O list.

Boards follow docs/electrical/00_electrical_control_architecture.md: B1 ECU (indoor), B2 sensor I/O and B4 drivers in
RP-1 on the roof, SR1 safety relay (group D = HVAC, never stops the engine), B5 HMI. The HVAC loops own tags 1xx-4xx
(the engine package moved to 0xx and 5xx-9xx); shared rows below keep the board/channel given in
docs/electrical/02_io_list.csv. NEW: B6-R = HVAC/BOP controller in BOP-R on the roof, B6-E = same board indoors, both on
Modbus TCP (B1 = client; docs/electrical CONTRACT v3).
Writes docs/hvac/io_list.csv (UTF-8 with BOM for Excel) and prints counts per board / signal type.
Run:  python3 sim/hvac/io_list.py          (summary)
      python3 sim/hvac/io_list.py --md     (also print the markdown table used in docs/hvac/05_controls_io.md)
"""
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# signal types: AI-RTD (PT1000 3/4-wire), AI-TC (type K), AI-mA (4-20 mA 2-wire loop-powered), AI-V (0/2-10 V),
# AO-V (0/2-10 V), DI (24 VDC dry contact), PI (pulse input, counter), DO (relay 230 VAC/24 V, 2 A),
# SAFE-DI / SAFE-DO (hard-wired safety chain), BUS (Modbus RTU / M-Bus device, no point wiring)
IO = [
    # tag, شرح, type, range / signal, location, board, function / setpoints
    # ---------------- exhaust & diverter
    ('TE-101', 'دمای گاز اگزوز ورودی HX-1 (بعد از recuperator)', 'AI-TC', '0-600 °C', 'duct before D-101', 'B2', 'TC07 (docs/electrical); H 320 °C = عیب recuperator (ECU)؛ محاسبهٔ گرما در B6-R'),
    ('TE-102', 'دمای گاز خروجی HX-1', 'AI-TC', '0-400 °C', 'HX-1 outlet', 'B6-R', 'H 130 °C = رسوب؛ L 85 °C = خطر میعان'),
    ('TE-103', 'دمای دودکش مشترک', 'AI-TC', '0-600 °C', 'ST-1', 'B6-R', 'تأیید موقعیت damper (bypass ⇒ > 200 °C)'),
    ('PT-101', 'فشار برگشتی اگزوز قبل از diverter D-101', 'AI-mA', '-0.5..+2.5 kPa', 'duct before D-101', 'B2', 'AI03 (docs/electrical); H 1.0 kPa ALM، HH 1.5 kPa FSD در ECU'),
    ('PDT-102', 'افت فشار سمت گاز HX-1', 'AI-mA', '0-1 kPa', 'across HX-1', 'B6-R', 'روند رسوب؛ H 0.25 kPa'),
    ('ZC-101', 'فرمان موقعیت diverter damper D-101', 'AO-V', '2-10 V = 0 % bypass..100 % HX', 'D-101', 'B4', 'AO01 (docs/electrical CONTRACT v3)؛ مالک ECU. B6-R فقط موقعیت درخواستی (PI روی TE-111) را با Modbus TCP می‌فرستد؛ قطع > 5 s → دودکش'),
    ('ZT-101', 'فیدبک موقعیت D-101', 'AI-V', '2-10 V = 0-100 %', 'D-101', 'B2', 'AI16 (docs/electrical)؛ B6-R آن را از Modbus TCP می‌خواند'),
    ('ZSO-101', 'D-101 کاملاً در حالت BYPASS (کنتاکت اول)', 'SAFE-DI', 'dry contact', 'D-101', 'SR1', 'SI16 + B2 DI22 (docs/electrical)؛ مجوز light-off'),
    ('ZSO-101b', 'کنتاکت دوم ZSO-101 برای وضعیت', 'DI', 'dry contact', 'D-101', 'B6-R', ''),
    ('ZSH-101', 'D-101 کاملاً در مسیر HX', 'DI', 'dry contact', 'D-101', 'B6-R', 'با ZSO-101: «هر دو مسیر بسته» → آلارم'),
    ('K-EX', 'تغذیهٔ 24 VAC actuator D-101 (fail → bypass با فنر)', 'SAFE-DO', '24 VAC via force-guided contactor', 'BOP-R', 'SR1', 'O6 (docs/electrical)؛ گروه D: موتور را متوقف نمی‌کند'),
    ('TE-104', 'دمای هوای ورودی موتور پشت لوور (تشخیص recirculation)', 'AI-RTD', '-10..+70 °C', 'IF-1 inlet', 'B6-R', 'TE-104 − TT-OA > 3 K → آلارم بازچرخش'),
    # ---------------- hot water
    ('TE-111', 'دمای رفت آب داغ (خروجی HX-1)', 'AI-RTD', '0-150 °C', 'HX-1 outlet', 'B6-R', 'SP کنترل damper 92 °C؛ H 95 °C'),
    ('TSHH-111', 'ترموستات حد بالا آب داغ 98 °C (manual reset)', 'SAFE-DI', 'NC contact x2', 'HX-1 outlet', 'SR1', 'SI17 (docs/electrical) → K-EX؛ کنتاکت دوم وضعیت به B6-R'),
    ('PSH-111', 'سوئیچ فشار بالای مدار آب داغ 5.0 bar', 'SAFE-DI', 'NC contact', 'HX-1 outlet', 'SR1', 'SI17 سری با TSHH-111 (قبل از PSV 5.5 bar)'),
    ('TE-112', 'دمای برگشت آب به HX-1', 'AI-RTD', '0-150 °C', 'HX-1 inlet', 'B6-R', 'L 70 °C → bypass جزئی (میعان اسیدی)'),
    ('PT-111', 'فشار استاتیک مدار آب داغ', 'AI-mA', '0-10 bar', 'P-1 suction', 'B6-R', 'L 0.8 bar نشتی؛ H 4.5 bar'),
    ('FT-111', 'دبی مدار اولیه آب داغ (electromagnetic)', 'AI-mA', '0-15 m³/h', 'P-1 discharge', 'B6-R', 'L 4.5 m³/h (design 6.2)'),
    ('FSL-111', 'فلوسوئیچ مدار اولیه (paddle/thermal)', 'SAFE-DI', 'NC contact', 'HX-1 inlet', 'SR1', 'SI18 با تأخیر 10 s → K-EX؛ reset خودکار وقتی دبی برگشت'),
    ('P-1-CMD', 'فرمان پمپ دوقلوی P-1A/B', 'DO', 'relay', 'PS-1', 'B6-R', 'همیشه روشن وقتی موتور روشن است + 15 min run-on'),
    ('P-1-FLT', 'خطای پمپ P-1 (هر دو هد)', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('P-1-BUS', 'P-1A/B ECM: دور، توان، آلارم، تعویض نوبتی', 'BUS', 'Modbus RTU bus-1', 'PS-1', 'B6-R', 'alternation 24 h'),
    ('TE-113', 'دمای بالای LLH-1', 'AI-RTD', '0-150 °C', 'LLH-1', 'B6-R', ''),
    ('TE-114', 'دمای برگشت مصرف‌کننده‌ها به LLH-1', 'AI-RTD', '0-150 °C', 'LLH-1', 'B6-R', ''),
    ('P-2A-CMD', 'فرمان پمپ آب داغ چیلر CH-1', 'DO', 'relay', 'PS-1', 'B6-R', 'با CH-1'),
    ('P-2A-FLT', 'خطای P-2A', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('P-2B-CMD', 'فرمان پمپ آب داغ چیلر CH-2', 'DO', 'relay', 'PS-1', 'B6-R', 'با CH-2'),
    ('P-2B-FLT', 'خطای P-2B', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('HM-1', 'کنتور انرژی گرمای بازیافتی HX-1 (مدار اولیه)', 'BUS', 'M-Bus', 'HW primary', 'B6-R', 'kWh، دبی، دماها؛ راندمان CHP'),
    ('HM-11', 'کنتور گرمای ورودی CH-1 (آب داغ)', 'BUS', 'M-Bus', 'CH-1 HW', 'B6-R', 'جدید (حالت‌ها): COP لحظه‌ای هر چیلر'),
    ('HM-12', 'کنتور گرمای ورودی CH-2 (آب داغ)', 'BUS', 'M-Bus', 'CH-2 HW', 'B6-R', 'جدید (حالت‌ها)'),
    ('P-3-CMD', 'فرمان پمپ شاخهٔ DHW/گرمایش', 'DO', 'relay', 'PS-1', 'B6-R', ''),
    ('P-3-FLT', 'خطای P-3', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('V-PRI', 'شیر سه‌راههٔ اولویت DHW ↔ گرمایش (2 وضعیت)', 'DO', '230 VAC SPDT', 'PS-1', 'B6-R', 'DHW اولویت دارد'),
    ('V-PRI-ZS', 'end switch شیر V-PRI', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('TV-131', 'شیر سه‌راههٔ محدودکنندهٔ دمای رفت شاخه', 'AO-V', '0-10 V', 'PS-1', 'B6-R', 'DHW ≤ 75 °C، گرمایش ≤ 50 °C'),
    ('TE-131', 'دمای رفت شاخهٔ DHW/گرمایش', 'AI-RTD', '0-150 °C', 'PS-1', 'B6-R', ''),
    ('TE-132', 'دمای بالای مخزن DHW', 'AI-RTD', '0-100 °C', 'DHW tank (indoor)', 'B6-E', 'SP 60 °C؛ legionella هفتگی ≥ 65 °C/1 h'),
    ('TE-133', 'دمای پایین مخزن DHW', 'AI-RTD', '0-100 °C', 'DHW tank (indoor)', 'B6-E', ''),
    ('P-7-CMD', 'پمپ شارژ/گردش DHW', 'DO', 'relay', 'DHW room', 'B6-E', ''),
    ('P-7-FLT', 'خطای P-7', 'DI', 'dry contact', 'DHW room', 'B6-E', ''),
    ('HM-3', 'کنتور انرژی DHW/گرمایش', 'BUS', 'M-Bus', 'DHW branch', 'B6-E', ''),
    ('TV-231', 'شیر کنترل HX-3 (گرمایش زمستان، سمت آب داغ)', 'AO-V', '0-10 V', 'PS-1', 'B6-R', 'SP رفت گرمایش 45 °C'),
    ('TE-231', 'دمای رفت گرمایش (ثانویهٔ HX-3)', 'AI-RTD', '0-100 °C', 'PS-1', 'B6-R', 'H 55 °C'),
    # ---------------- chillers
    ('CH-1-CMD', 'فرمان start/stop از راه دور CH-1', 'DO', 'dry contact', 'CH-1', 'B6-R', ''),
    ('CH-1-RUN', 'وضعیت کار CH-1', 'DI', 'dry contact', 'CH-1', 'B6-R', ''),
    ('CH-1-ALM', 'آلارم عمومی CH-1', 'DI', 'dry contact', 'CH-1', 'B6-R', ''),
    ('CH-2-CMD', 'فرمان start/stop از راه دور CH-2', 'DO', 'dry contact', 'CH-2', 'B6-R', ''),
    ('CH-2-RUN', 'وضعیت کار CH-2', 'DI', 'dry contact', 'CH-2', 'B6-R', ''),
    ('CH-2-ALM', 'آلارم عمومی CH-2', 'DI', 'dry contact', 'CH-2', 'B6-R', ''),
    ('CH-BUS', 'پورت Modbus چیلرها: دمای ژنراتور، غلظت/حاشیهٔ کریستالیزاسیون، وضعیت رقیق‌سازی، تایمرها', 'BUS', 'Modbus RTU bus-1', 'CH-1/2', 'B6-R', 'الزام در مشخصات خرید (حالت‌ها)'),
    ('MV-CH1E', 'شیر قطع موتوری اواپراتور CH-1', 'DO', '230 VAC', 'CH-1 CHW', 'B6-R', 'در زمستان بسته: آب داغ هرگز وارد اواپراتور نشود'),
    ('MV-CH1E-ZS', 'end switch بسته MV-CH1E', 'DI', 'dry contact', 'CH-1 CHW', 'B6-R', 'اینترلاک changeover'),
    ('MV-CH2E', 'شیر قطع موتوری اواپراتور CH-2', 'DO', '230 VAC', 'CH-2 CHW', 'B6-R', ''),
    ('MV-CH2E-ZS', 'end switch بسته MV-CH2E', 'DI', 'dry contact', 'CH-2 CHW', 'B6-R', ''),
    ('TE-201', 'دمای خروجی آب سرد CH-1', 'AI-RTD', '-10..+60 °C', 'CH-1', 'B6-R', 'عیب‌یابی عملکرد'),
    ('TE-202', 'دمای خروجی آب سرد CH-2', 'AI-RTD', '-10..+60 °C', 'CH-2', 'B6-R', ''),
    ('TE-203', 'دمای خروجی آب خنک‌کن CH-1', 'AI-RTD', '0-60 °C', 'CH-1', 'B6-R', ''),
    ('TE-204', 'دمای خروجی آب خنک‌کن CH-2', 'AI-RTD', '0-60 °C', 'CH-2', 'B6-R', ''),
    ('FS-201', 'فلوسوئیچ آب سرد CH-1', 'DI', 'dry contact', 'CH-1', 'B6-R', 'کنتاکت اول به اینترلاک چیلر، دوم به B6-R'),
    ('FS-202', 'فلوسوئیچ آب سرد CH-2', 'DI', 'dry contact', 'CH-2', 'B6-R', ''),
    ('FS-301', 'فلوسوئیچ آب خنک‌کن CH-1', 'DI', 'dry contact', 'CH-1', 'B6-R', ''),
    ('FS-302', 'فلوسوئیچ آب خنک‌کن CH-2', 'DI', 'dry contact', 'CH-2', 'B6-R', ''),
    ('MV-CH1C', 'شیر قطع موتوری آب خنک‌کن CH-1 (پروانه‌ای DN80)', 'DO', '230 VAC', 'CH-1 CW', 'B6-R', 'جدید: staging؛ باز تا پایان رقیق‌سازی'),
    ('MV-CH1C-ZS', 'end switch بسته MV-CH1C', 'DI', 'dry contact', 'CH-1 CW', 'B6-R', ''),
    ('MV-CH2C', 'شیر قطع موتوری آب خنک‌کن CH-2 (پروانه‌ای DN65)', 'DO', '230 VAC', 'CH-2 CW', 'B6-R', 'جدید: در MAX-POWER بسته → دبی P-6 کم'),
    ('MV-CH2C-ZS', 'end switch بسته MV-CH2C', 'DI', 'dry contact', 'CH-2 CW', 'B6-R', ''),
    # ---------------- chilled water
    ('P-4A-CMD', 'فرمان پمپ آب سرد اولیهٔ CH-1', 'DO', 'relay', 'PS-1', 'B6-R', 'با CH-1 + run-on رقیق‌سازی 15 min'),
    ('P-4A-FLT', 'خطای P-4A', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('P-4B-CMD', 'فرمان پمپ آب سرد اولیهٔ CH-2', 'DO', 'relay', 'PS-1', 'B6-R', ''),
    ('P-4B-FLT', 'خطای P-4B', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('TE-211', 'دمای بالای مخزن TK-1 (رفت به مصرف)', 'AI-RTD', '-10..+60 °C', 'TK-1', 'B6-R', 'H 10 °C به مدت 10 min → منطق اولویت'),
    ('TE-212', 'دمای پایین مخزن TK-1', 'AI-RTD', '-10..+60 °C', 'TK-1', 'B6-R', ''),
    ('TE-213', 'دمای برگشت آب سرد از مصرف‌کننده‌ها', 'AI-RTD', '-10..+60 °C', 'header', 'B6-R', ''),
    ('TE-214', 'دمای وسط مخزن TK-1 (لایه‌بندی، ذخیرهٔ سرما)', 'AI-RTD', '-10..+60 °C', 'TK-1', 'B6-R', 'جدید: kWh سرمای ذخیره برای ECU'),
    ('PT-211', 'فشار استاتیک مدار آب سرد', 'AI-mA', '0-10 bar', 'P-5 suction', 'B6-R', 'L 0.8 bar'),
    ('DPT-211', 'اختلاف فشار index (پای رایزر سالن)', 'AI-mA', '0-2.5 bar', 'hall riser', 'B6-R', 'SP ≈ 65 kPa (تنظیم در commissioning) → دور P-5'),
    ('FT-211', 'دبی ثانویهٔ آب سرد (electromagnetic)', 'AI-mA', '0-12 m³/h', 'P-5 discharge', 'B6-R', ''),
    ('P-5-CMD', 'فرمان پمپ دوقلوی P-5A/B', 'DO', 'relay', 'PS-1', 'B6-R', ''),
    ('P-5-FLT', 'خطای P-5', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('P-5-BUS', 'P-5A/B ECM: setpoint دور/Δp، توان، آلارم', 'BUS', 'Modbus RTU bus-1', 'PS-1', 'B6-R', ''),
    ('HM-2', 'کنتور انرژی سرمایش ساختمان (سالن + اتاق برق)', 'BUS', 'M-Bus', 'hall branch', 'B6-R', ''),
    ('HM-4', 'کنتور انرژی سرمایش کویل ورودی موتور', 'BUS', 'M-Bus', 'CC-1 branch', 'B6-R', ''),
    ('HM-21', 'کنتور سرمای تولیدی CH-1', 'BUS', 'M-Bus', 'CH-1 CHW', 'B6-R', 'جدید: COP و بار هر چیلر'),
    ('HM-22', 'کنتور سرمای تولیدی CH-2', 'BUS', 'M-Bus', 'CH-2 CHW', 'B6-R', 'جدید'),
    ('TV-221', 'شیر PICV کویل ورودی موتور CC-1', 'AO-V', '0-10 V', 'CC-1', 'B6-R', 'PI روی TE-221 (SP 15 °C)'),
    ('ZT-221', 'فیدبک موقعیت TV-221', 'AI-V', '2-10 V', 'CC-1', 'B6-R', ''),
    ('TE-221', 'دمای هوای بعد از کویل CC-1', 'AI-RTD', '-10..+70 °C', 'IF-1 after coil', 'B6-R', 'کنترل TV-221؛ T1 موتور = TE-501 روی B2'),
    ('TE-222', 'دمای آب خروجی کویل CC-1', 'AI-RTD', '-10..+60 °C', 'CC-1', 'B6-R', 'حفاظت یخ‌زدگی < 4 °C'),
    ('MT-501', 'رطوبت نسبی هوای بعد از کویل CC-1', 'AI-mA', '0-100 %', 'IF-1 after coil', 'B2', 'docs/electrical؛ بار نهان کویل، اشباع/حمل قطره'),
    ('LSH-221', 'سطح بالای سینی کندانس CC-1 (float)', 'DI', 'dry contact', 'CC-1', 'B6-R', 'تخلیهٔ مسدود → بستن TV-221 + آلارم (حمل قطره به کمپرسور)'),
    ('PDT-222', 'افت فشار فیلترهای G4 و F8 ورودی هوا', 'AI-mA', '0-500 Pa (x2)', 'IF-1', 'B2', 'AI13–AI14 (docs/electrical); ECU: جمع > 400 Pa DRT'),
    ('PDT-223', 'افت فشار سمت هوای کویل CC-1', 'AI-mA', '0-500 Pa', 'IF-1', 'B2', 'AI15 (docs/electrical); H 300 Pa'),
    ('TT-OA', 'دمای هوای بیرون (radiation shield، سایه)', 'AI-mA', '-20..+60 °C', 'roof north side', 'B6-R', 'به ECU از Modbus TCP (پیش‌بینی P_max)؛ منطق یخ‌زدگی و changeover'),
    ('MT-OA', 'رطوبت نسبی هوای بیرون', 'AI-mA', '0-100 %', 'roof north side', 'B6-R', 'محاسبهٔ wet-bulb'),
    ('V-CO1', 'شیر changeover تابستان/زمستان (مکش P-5)', 'DO', '230 VAC SPDT', 'PS-1', 'B6-R', ''),
    ('V-CO1-ZS', 'end switch V-CO1', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('V-CO2', 'شیر changeover تابستان/زمستان (برگشت)', 'DO', '230 VAC SPDT', 'PS-1', 'B6-R', ''),
    ('V-CO2-ZS', 'end switch V-CO2', 'DI', 'dry contact', 'PS-1', 'B6-R', ''),
    ('FCU-1..4', 'کنترلر اتاق فن‌کویل‌های سالن (دما، رطوبت، setpoint، سرعت فن EC، شیر، کندانس)', 'BUS', 'Modbus RTU bus-2 (4 devices)', 'hall', 'B6-R', 'SP 24 °C؛ RH برای منطق comfort guard'),
    ('ERV-1', 'تهویهٔ بازیاب انرژی (اختیاری)', 'BUS', 'Modbus RTU bus-2', 'hall', 'B6-R', ''),
    ('TE-H1', 'دما/رطوبت مرجع سالن', 'BUS', 'Modbus RTU bus-2', 'hall', 'B6-R', 'ورودی منطق اولویت برق/آسایش'),
    ('AT-H1', 'CO2 سالن (NDIR)', 'BUS', 'Modbus RTU bus-2', 'hall', 'B6-R', 'جدید: اشغال سالن و کنترل ERV (هوای تازهٔ متناسب با تقاضا)'),
    # ---------------- electrical room (indoor)
    ('FCU-E-RC', 'کنترلر اتاق FCU-E (دما و رطوبت اتاق برق)', 'BUS', 'Modbus RTU', 'electrical room', 'B6-E', 'SP 25 °C؛ TT-ER روی B1 (docs/electrical) برای باتری'),
    ('FCU-E-V', 'شیر آب سرد FCU-E', 'DO', '24 VAC on/off', 'electrical room', 'B6-E', ''),
    ('FCU-E-F', 'فرمان دور فن EC فن‌کویل FCU-E', 'AO-V', '0-10 V', 'electrical room', 'B6-E', ''),
    ('FCU-E-S', 'وضعیت/خطای FCU-E', 'DI', 'dry contact', 'electrical room', 'B6-E', ''),
    ('AC-E-EN', 'فعال‌سازی اسپلیت DX پشتیبان', 'DO', 'dry contact (adapter)', 'electrical room', 'B6-E', 'روشن در 28 °C یا نبود آب سرد'),
    ('AC-E-ST', 'وضعیت کار اسپلیت (current switch)', 'DI', 'dry contact', 'electrical room', 'B6-E', ''),
    ('LD-E', 'کابل تشخیص نشت آب زیر FCU-E و لوله‌ها', 'DI', 'dry contact', 'electrical room', 'B6-E', 'بستن FCU-E-V + آلارم'),
    ('EF-E', 'فن تخلیهٔ اتاق برق/باتری', 'DO', 'relay', 'electrical room', 'B6-E', ''),
    ('SD-E', 'دتکتور دود اتاق برق/باتری (از پنل آتش)', 'DI', 'dry contact', 'electrical room', 'B1', 'DI15 (docs/electrical); HVAC: قطع فن‌ها و AC-E از CAN'),
    # ---------------- condenser water / tower
    ('TE-301', 'دمای آب خنک‌کن رفت به چیلرها (خروجی برج)', 'AI-RTD', '0-60 °C', 'PS-2', 'B6-R', 'کنترل فن برج SP 27 °C (هرچه سردتر بهتر)؛ حداقل 26 °C با TV-301'),
    ('TE-302', 'دمای برگشت آب خنک‌کن به برج', 'AI-RTD', '0-60 °C', 'CT-1 inlet', 'B6-R', ''),
    ('TE-303', 'دمای حوضچهٔ برج', 'AI-RTD', '-10..+60 °C', 'CT-1 basin', 'B6-R', '< 5 °C → EH-301'),
    ('P-6-CMD', 'فرمان VFD پمپ آب خنک‌کن P-6A/B', 'DO', 'relay (x2)', 'PS-2', 'B6-R', 'duty/standby'),
    ('P-6-FLT', 'خطای VFD پمپ‌های P-6', 'DI', 'dry contact (x2)', 'PS-2', 'B6-R', ''),
    ('P-6-BUS', 'VFD پمپ‌های P-6: دور، توان، آلارم', 'BUS', 'Modbus RTU bus-1', 'BOP-R', 'B6-R', 'دور ثابت روی دبی نامی'),
    ('FT-301', 'دبی آب خنک‌کن (electromagnetic)', 'AI-mA', '0-40 m³/h', 'PS-2', 'B6-R', 'نامی 27.5 m³/h ±10 %'),
    ('TT-306', 'دمای هوای ورودی برج (سایه، کنار لوور برج)', 'AI-mA', '-20..+60 °C', 'CT-1 inlet', 'B6-R', 'جدید: wet-bulb واقعی برج و تشخیص بازچرخش پلوم'),
    ('MT-306', 'رطوبت نسبی هوای ورودی برج', 'AI-mA', '0-100 %', 'CT-1 inlet', 'B6-R', 'جدید'),
    ('CT-FAN-CMD', 'فرمان VFD فن برج', 'DO', 'relay', 'BOP-R', 'B6-R', ''),
    ('CT-FAN-FLT', 'خطای VFD فن برج', 'DI', 'dry contact', 'BOP-R', 'B6-R', ''),
    ('CT-FAN-BUS', 'VFD فن برج: setpoint دور، توان', 'BUS', 'Modbus RTU bus-1', 'BOP-R', 'B6-R', 'حداقل 25 %'),
    ('VS-301', 'سوئیچ ارتعاش فن برج', 'DI', 'dry contact', 'CT-1', 'B6-R', 'توقف فن + آلارم'),
    ('TV-301', 'شیر سه‌راههٔ bypass برج', 'AO-V', '0-10 V', 'PS-2', 'B6-R', 'حداقل دمای آب خنک‌کن در start-up/زمستان'),
    ('LT-301', 'سطح حوضچهٔ برج (hydrostatic)', 'AI-mA', '0-500 mm', 'CT-1 basin', 'B6-R', 'L/H آلارم؛ کنترل make-up'),
    ('LSLL-301', 'سطح خیلی پایین حوضچه (float)', 'DI', 'dry contact', 'CT-1 basin', 'B6-R', 'اینترلاک سخت‌افزاری با استارتر P-6 + آلارم'),
    ('XV-301', 'شیر برقی آب جبرانی برج', 'DO', '24 VAC', 'CT-1', 'B6-R', 'شناور مکانیکی پشتیبان'),
    ('FQ-301', 'کنتور آب جبرانی برج', 'PI', '1 L/pulse', 'make-up line', 'B6-R', 'دوز متناسب inhibitor؛ آلارم مصرف غیرعادی'),
    ('AIT-301', 'هدایت الکتریکی آب برج (کنترلر)', 'AI-mA', '0-5000 µS/cm', 'side-stream', 'B6-R', 'blowdown SP 800 µS/cm (گزینهٔ RO)'),
    ('XV-302', 'شیر موتوری blowdown', 'DO', '24 VAC', 'side-stream', 'B6-R', ''),
    ('XV-302-ZS', 'end switch شیر blowdown', 'DI', 'dry contact', 'side-stream', 'B6-R', ''),
    ('FQ-302', 'کنتور blowdown', 'PI', '1 L/pulse', 'drain line', 'B6-R', 'محاسبهٔ cycles واقعی'),
    ('AIT-302', 'ORP / کلر آزاد', 'AI-mA', '0-1000 mV', 'side-stream', 'B6-R', 'FRC 0.5-1.0 ppm'),
    ('AIT-303', 'pH آب برج', 'AI-mA', '0-14', 'side-stream', 'B6-R', 'آلارم خارج از 6.5-8.2'),
    ('DP-1', 'پمپ دوزینگ inhibitor', 'DO', 'pulse relay', 'WT-1', 'B6-R', 'متناسب با FQ-301'),
    ('DP-2', 'پمپ دوزینگ biocide اکسیدکننده', 'DO', 'relay', 'WT-1', 'B6-R', 'روی AIT-302'),
    ('DP-3', 'پمپ دوزینگ biocide غیراکسیدکننده', 'DO', 'relay', 'WT-1', 'B6-R', 'shock هفتگی + قفل blowdown'),
    ('LSL-DP', 'سطح پایین مخازن مواد شیمیایی (x3)', 'DI', 'dry contact (x3)', 'WT-1', 'B6-R', ''),
    ('XV-303', 'شیر purge جداکنندهٔ side-stream', 'DO', '24 VAC', 'WT-1', 'B6-R', 'جزئی از blowdown'),
    ('EH-301', 'کنتاکتور هیتر حوضچهٔ برج', 'DO', 'relay', 'BOP-R', 'B6-R', 'فقط با سطح کافی'),
    ('HT-1', 'فعال‌سازی heat tracing و خطای آن', 'DO', 'relay', 'BOP-R', 'B6-R', 'TT-OA < 3 °C'),
    ('HT-1-F', 'خطای کنترلر heat tracing', 'DI', 'dry contact', 'BOP-R', 'B6-R', ''),
    # ---------------- make-up / RO (indoor)
    ('RO-1-EN', 'فعال‌سازی RO', 'DO', 'dry contact', 'water room', 'B6-E', ''),
    ('RO-1-RUN', 'وضعیت کار RO', 'DI', 'dry contact', 'water room', 'B6-E', ''),
    ('RO-1-FLT', 'خطای RO', 'DI', 'dry contact', 'water room', 'B6-E', ''),
    ('AIT-401', 'هدایت permeate', 'AI-mA', '0-200 µS/cm', 'RO-1', 'B6-E', 'H 50 µS/cm → سرویس ممبران'),
    ('AIT-402', 'هدایت آب جبرانی blend', 'AI-mA', '0-2000 µS/cm', 'blend tank', 'B6-E', 'SP 229 µS/cm'),
    ('TV-401', 'شیر blend آب شهری', 'AO-V', '0-10 V', 'blend tank', 'B6-E', 'PI روی AIT-402'),
    ('LT-401', 'سطح مخزن blend/permeate', 'AI-mA', '0-1.5 m', 'blend tank', 'B6-E', ''),
    ('P-9-CMD', 'پمپ بوستر آب جبرانی به بام', 'DO', 'relay', 'water room', 'B6-E', ''),
    ('P-9-FLT', 'خطای P-9', 'DI', 'dry contact', 'water room', 'B6-E', ''),
    ('LSL-400', 'سطح پایین مخزن آب شهری', 'DI', 'dry contact', 'city tank', 'B6-E', ''),
    ('XV-410', 'شیر پرکن خودکار مدارهای بسته (آب RO)', 'DO', '24 VAC', 'water room', 'B6-E', 'حداکثر 20 L/day، بعد قفل + آلارم نشتی'),
    ('FQ-410', 'کنتور پرکن مدارهای بسته', 'PI', '0.1 L/pulse', 'water room', 'B6-E', ''),
    # ---------------- electrical / safety / interface
    ('EM-HVAC', 'کنتور انرژی ورودی تابلوی BOP-R (سه‌فاز، کلاس 0.5S)', 'BUS', 'Modbus RTU bus-1', 'BOP-R', 'B6-R', '= P_HVAC_KW به EMS (docs/electrical/06)'),
    ('JT-191', 'زیرکنتور گروه CH-1 (CH-1 + P-2A + P-4A)', 'BUS', 'Modbus RTU bus-1 (multi-CT meter)', 'BOP-R', 'B6-R', 'جدید: هزینهٔ برق هر stage'),
    ('JT-192', 'زیرکنتور گروه CH-2 (CH-2 + P-2B + P-4B)', 'BUS', 'Modbus RTU bus-1 (multi-CT meter)', 'BOP-R', 'B6-R', 'جدید'),
    ('JT-193', 'زیرکنتور آب خنک‌کن (VFD پمپ P-6 + VFD فن برج)', 'BUS', 'Modbus RTU bus-1 (multi-CT meter)', 'BOP-R', 'B6-R', 'جدید؛ VFDها هم توان را گزارش می‌کنند'),
    ('JT-194', 'زیرکنتور توزیع (P-1، P-3، P-5)', 'BUS', 'Modbus RTU bus-1 (multi-CT meter)', 'BOP-R', 'B6-R', 'جدید'),
    ('JT-195', 'زیرکنتور تصفیهٔ آب و هیترها (WT-1، EH-301، HT-1)', 'BUS', 'Modbus RTU bus-1 (multi-CT meter)', 'BOP-R', 'B6-R', 'جدید'),
    ('JT-196', 'زیرکنتور فن‌های DC-1 و مصرف تابلو', 'BUS', 'Modbus RTU bus-1 (multi-CT meter)', 'BOP-R', 'B6-R', 'جدید (DC-1 بار موتور است)'),
    ('JT-904', 'کنتور مصرف کمکی داخل ساختمان (RO-1، P-9، P-7، FCU-E، AC-E، EF-E)', 'BUS', 'Modbus RTU', 'electrical room', 'B1', 'RS-485 #2 (docs/electrical)'),
    ('JT-903', 'کنتور فن‌کویل‌ها و ERV سالن', 'BUS', 'Modbus RTU', 'hall panel', 'B1', 'RS-485 #2 (docs/electrical)؛ مصرف سمت ساختمان'),
    ('PMR-1', 'رلهٔ کنترل فاز تابلوی BOP', 'DI', 'dry contact', 'BOP-R', 'B6-R', ''),
    ('ESD-R', 'E-stop روی بام (در جعبه؛ یک شستی دوم کنار BOP-R به‌صورت سری)', 'SAFE-DI', 'NC dual channel', 'roof', 'SR1', 'SI01 + B2 DI10 (docs/electrical)'),
    ('ENG-RUN', 'سیگنال سخت‌افزاری «موتور روشن» از B1', 'DI', 'dry contact (B1 RO08)', 'BOP-R', 'B6-R', 'پشتیبان Modbus TCP برای حالت محلی امن'),
    ('XV-305', 'شیر on/off سمت آب خنک‌کن HX-4 (trim گلیکول)', 'DO', '24 VAC، normally closed', 'PS-2', 'B6-R', 'باز وقتی CW در کار است و TE-GLY > 40 °C؛ اختیاری (بخش ۷ سند 07)'),
    ('XV-307', 'شیر آب پدهای پیش‌سرمایش adiabatic در DC-1 (آب نرم‌شده)', 'DO', '24 VDC, NC', 'DC-1', 'B4', 'B4 DO12 (docs/electrical)؛ باز وقتی TT-OA > 35 °C یا TE-GLY > 42 °C'),
    ('SOFT-1-FLT', 'خطا یا regeneration سختی‌گیر SOFT-1', 'DI', 'dry contact', 'water room', 'B6-E', ''),
    ('LSL-403', 'سطح پایین نمک مخزن brine سختی‌گیر', 'DI', 'dry contact', 'water room', 'B6-E', ''),
    # ---------------- fire suppression FK-5-1-12 (docs/hvac/08): mechanical side here. Detection, release, discharge and
    # lock-off signals are owned by docs/electrical/02_io_list.csv group L (panel FCP, tags 87x-89x: XY-888A/B, PS-889A/B,
    # PSL-890A/B, ZSC-899A/B, HS-892..895, FD-837/K-VS) and are NOT repeated here. Proposed to electrical: XY-888C / PSL-890C
    # for the FZ1 reserve cylinder FS-1B. Only the HVAC-side points below remain.
    ('XV-497', 'دمپر موتوری کانال EF-E اتاق برق (spring-close؛ تغذیه از مدار FCP REL3 / XS-874)', 'DO', '24 VAC', 'electrical room', 'B6-E', 'بسته قبل از تخلیهٔ FS-2 (FZ2)؛ EF-E و AC-E خاموش (سخت‌افزاری با XS-874)'),
    ('ZSC-497', 'end switch بسته XV-497', 'DI', 'dry contact', 'electrical room', 'B6-E', ''),
    ('TE-499', 'دمای کابینت سیلندرهای FS-1 روی بام', 'AI-RTD', '0-80 °C', 'FS-1 cabinet', 'B6-R', 'آلارم 50 °C (حد نگهداری FK-5-1-12)'),
    ('DC-1-FAN', 'فن EC dry cooler مدار گلیکول DC-1', 'AO-V', 'PWM/0-10 V + tach', 'DC-1', 'B4', 'FAN3 (docs/electrical); PI روی TE-GLY؛ تغذیه از BOP-R'),
    ('TE-GLY', 'دمای رفت گلیکول به PMG / B3 / خنک‌کن روغن', 'AI-RTD', '0-120 °C', 'DC-1 outlet', 'B2', 'RTD08 (docs/electrical)؛ هدف ≤ 40 °C (PMG 35–40 °C، docs/06 §۲؛ با پد DC-1 ~38.5 °C در 46 °C)؛ ALM 58 / FSD 65 °C'),
    ('EH-950', 'المنت برقی ۶ kW مخزن DHW (dump برق مازاد)', 'DO', '24 V → SSR', 'DHW tank', 'B1', 'RO10 (docs/electrical); قطع در TE-132 > 75 °C'),
]

def counts():
    c = collections.Counter((r[5], r[2]) for r in IO)
    mult = {'PDT-222': 2, 'P-6-CMD': 2, 'P-6-FLT': 2, 'LSL-DP': 3}
    for r in IO:
        if r[0] in mult:
            c[(r[5], r[2])] += mult[r[0]] - 1
    return c

def main():
    path = os.path.join(ROOT, 'docs', 'hvac', 'io_list.csv')
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['tag', 'description_fa', 'signal_type', 'range_signal', 'location', 'board', 'function_setpoints_fa'])
        w.writerows(IO)
    c = counts()
    boards = sorted({b for b, _ in c})
    types = ['AI-RTD', 'AI-TC', 'AI-mA', 'AI-V', 'AO-V', 'DI', 'PI', 'DO', 'SAFE-DI', 'SAFE-DO', 'BUS']
    print('I/O LIST: %d entries -> %s' % (len(IO), os.path.relpath(path, os.getcwd())))
    print('  %-6s' % 'board' + ''.join('%8s' % t for t in types) + '   total')
    for b in boards:
        print('  %-6s' % b + ''.join('%8d' % c[(b, t)] for t in types) + '   %5d' % sum(c[(b, t)] for t in types))
    b6 = {t: c[('B6-R', t)] for t in types}
    print('\nB6-R minimum hardware (+25 %% spare): RTD %d, TC %d, AI 4-20 mA %d, AI 0-10 V %d, AO %d, DI %d (incl. %d counters), DO %d,'
          ' RS-485 x2 (bus-1 plant, bus-2 hall), M-Bus master x1, Ethernet (Modbus TCP server) x1' % tuple(
              math_ceil(v * 1.25) for v in (b6['AI-RTD'], b6['AI-TC'], b6['AI-mA'], b6['AI-V'], b6['AO-V'], b6['DI'] + b6['PI'],
                                            b6['PI'], b6['DO'])))
    if '--md' in sys.argv:
        print('\n| tag | شرح | نوع سیگنال | رنج / سیگنال | محل | برد | عملکرد / setpoint |')
        print('|---|---|---|---|---|---|---|')
        for r in IO:
            print('| ' + ' | '.join(x.replace('|', '/') for x in r) + ' |')

def math_ceil(x):
    return int(-(-x // 1))

if __name__ == '__main__':
    main()
