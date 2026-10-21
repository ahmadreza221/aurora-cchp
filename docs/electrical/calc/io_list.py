# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""GR180-CCHP I/O list — single source of truth.

Writes docs/electrical/02_io_list.md (tables per subsystem + channel budget per board) and docs/electrical/02_io_list.csv.
Run:  python3 docs/electrical/calc/io_list.py
Columns: tag, group, description, location, signal, range, accuracy, rate, connector, board, channel, role, notes
role: C = control, P = protection (see 03_control_philosophy.md trip table), M = monitoring / life counter
"""
import csv, collections, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, '..', '02_io_list.md')
OUT_CSV = os.path.join(HERE, '..', '02_io_list.csv')

GROUPS = collections.OrderedDict([
    ('A', 'سرعت روتورها و ارتعاش'),
    ('B', 'دماهای مسیر گاز و یاتاقان'),
    ('C', 'فشارهای مسیر هوا و گاز داغ'),
    ('D', 'قطار سوخت گاز (fuel gas train) و جرقه/شعله'),
    ('E', 'سیستم روغن'),
    ('F', 'مدار خنک‌کاری PMG و الکترونیک قدرت + سیم‌پیچ ژنراتور'),
    ('G', 'جعبه (enclosure)، ایمنی، نشت گاز، آتش، درها'),
    ('H', 'ورودی هوا و محیط'),
    ('I', 'اگزوز، بازیافت گرما و رابط HVAC/BOP (تگ‌ها و منطق طبق docs/hvac)'),
    ('J', 'برق: یکسوساز B3، اینورتر، باتری، UPS، کنتورها، load shedding'),
])

LOC = {
    'R-ENG': 'بام: ناحیهٔ موتور (داغ)', 'R-GAS': 'بام: ناحیهٔ گاز', 'R-AIR': 'بام: ورودی هوا',
    'R-CHP': 'بام: ناحیهٔ آب/CHP', 'R-ELC': 'بام: تابلوی RP-1 روی اسکید', 'R-ROOF': 'بام: بیرون اسکید',
    'ER': 'داخل: اتاق برق', 'HALL': 'داخل: سالن / تابلوی شرکت',
}

TC = ('TC type K class 1 (IEC 60584-1)، MI Ø1.5–3، غلاف Inconel 600، ungrounded')
RTD = 'PT1000 class A، 3-wire'
MA = '4–20 mA، 2-wire (loop 24 V از B2)'

# tag, group, description, loc, signal, range, accuracy, rate, connector, board, channel, role, notes
IO = [
    # ---------------------------------------------------------------- A: speed & vibration
    ('SE-001A', 'A', 'N1-A: دور هستهٔ GR180 — Hall A1120 روی intake، آهنربای nose cone (سنسور فعلی v11)', 'R-ENG',
     'پالس 1 ppr، open-collector 24 V → line driver RS-422 روی B2', '0–2.0 kHz (0–120k rpm)', '±0.01 % (timer capture)',
     'هر پالس؛ گاورنر 1 kHz', 'M8 3-pin → B2؛ RS-422 روی W102a', 'B2', 'FI01 + RS422-OUT1 → B1 SPD-IN1 (H7 TIM + SMCU)', 'C,P', 'گاورنر N1، trip N1 در ECU'),
    ('SE-001B', 'A', 'N1-B: سنسور Hall دوم، ۱۸۰° از N1-A، تغذیه و کابل مستقل', 'R-ENG',
     'پالس open-collector، تغذیهٔ 12 V از ناحیهٔ SMCU روی B1، pull-up در B1 (بدون الکترونیک فعال روی بام)', '0–2.0 kHz', '±0.01 %', 'هر پالس', 'M8 3-pin → کابل W102b',
     'B1', 'SPD-IN2 (SMCU اصلی + H7 مقایسه)', 'P', 'overspeed مستقل؛ اختلاف N1A/N1B > 2 % → trip'),
    ('SE-002A', 'A', 'N2-A: دور FPT/PMG از فرکانس back-EMF (PLL در B3)', 'R-ELC', 'داخلی B3 → CAN-FD',
     '0–80k rpm', '±0.05 %', '10 kHz (B3)، 1 kHz روی CAN', '—', 'B3', 'internal', 'C,P', 'حلقهٔ سرعت N2 در B3'),
    ('SE-002B', 'A', 'N2-B: سنسور مستقل دور FPT (Hall + آهنربا یا هدف ۲ دندانه روی انتهای سرد شفت PMG)', 'R-ENG',
     'پالس open-collector 1–2 ppr، تغذیه از B1 (SMCU)', '0–2.6 kHz', '±0.01 %', 'هر پالس', 'M8 3-pin → کابل W102b', 'B1',
     'SPD-IN3 (SMCU اصلی + H7)', 'P', 'overspeed N2 مستقل از B3؛ اختلاف N2A/N2B > 3 % → trip'),
    ('M-020', 'A', 'استارتر BLDC هسته (1.5–2 kW، Hall داخلی، کلاچ یک‌طرفه؛ cut-out ~45k rpm هسته)', 'R-ENG',
     'درایو BLDC سه‌فاز 48 V، 60 A پیک، 3× Hall', '0–50k rpm (سمت هسته)', '±1 % سرعت', 'حلقهٔ سرعت 1 kHz',
     'کابل قدرت 3×6 mm² + Hall M12 (≤ 2 m)', 'B4', 'MD1', 'C', 'تغذیه از باس اضطراری 48 V؛ purge، cranking، motoring cool-down'),
    ('VE-010', 'A', 'ارتعاش هسته (فلنج یاتاقان جلو/intake، سمت سرد)', 'R-ENG', 'IEPE 100 mV/g، 4 mA constant current',
     '±50 g، 2 Hz–10 kHz', '±5 %', '25.6 kS/s (FFT، 1× = 1.9 kHz)', 'M12 2-pin یا کابل یکپارچه', 'B2', 'VIB1 (ADS131M04 #1 ch0)', 'P,M',
     'trip و روند (trend)؛ دمای نصب ≤ 120 °C'),
    ('VE-011', 'A', 'ارتعاش FPT/PMG (هوزینگ یاتاقان سمت توربین)', 'R-ENG', 'IEPE 100 mV/g', '±50 g، 2 Hz–10 kHz', '±5 %',
     '25.6 kS/s', 'M12 2-pin', 'B2', 'VIB2 (ADS131M04 #1 ch1)', 'P,M', '1× FPT = 1.0–1.1 kHz'),
    ('VE-012', 'A', 'ارتعاش PMG سمت آزاد / محوری (رزرو)', 'R-ENG', 'IEPE 100 mV/g', '±50 g', '±5 %', '25.6 kS/s', 'M12 2-pin',
     'B2', 'VIB3 (ADS131M04 #1 ch2)', 'M', 'رزرو'),

    # ---------------------------------------------------------------- B: gas-path & bearing temperatures
    ('TE-502', 'B', 'T2: دمای خروجی کمپرسور', 'R-ENG', TC, '0–300 °C (طراحی ~165)', '±1.5 K', '10 Hz',
     'هد TC + کابل KX شیلددار → ترمینال ایزوترمال B2', 'B2', 'TC01 (MAX31856)', 'M', 'راندمان کمپرسور، سرج'),
    ('TE-503', 'B', 'T2r: خروجی سمت سرد recuperator / ورودی محفظه', 'R-ENG', TC, '0–700 °C (طراحی ~565)', '±1.5 K / 0.4 %',
     '10 Hz', 'هد TC + KX', 'B2', 'TC02', 'M,P', 'ε recuperator؛ آلارم > 600 °C'),
    ('TE-504A', 'B', 'ITT-1: دمای بین‌توربینی (خروجی توربین هسته، محل EGT راتن)', 'R-ENG', TC + '، Ø1.5 (پاسخ سریع)',
     '0–1000 °C (طراحی ~667 @ TIT 800)', '±1.5 K / 0.4 %', '10 Hz', 'هد TC + KX', 'B2', 'TC03', 'C,P',
     'رأی‌گیری 2oo3 → محدودکنندهٔ ITT و trip'),
    ('TE-504B', 'B', 'ITT-2 (۱۲۰°)', 'R-ENG', TC + '، Ø1.5', '0–1000 °C', '±1.5 K / 0.4 %', '10 Hz', 'هد TC + KX', 'B2', 'TC04', 'C,P', ''),
    ('TE-504C', 'B', 'ITT-3 (۲۴۰°)', 'R-ENG', TC + '، Ø1.5', '0–1000 °C', '±1.5 K / 0.4 %', '10 Hz', 'هد TC + KX', 'B2', 'TC05', 'C,P',
     'تشخیص light-off و flame-out از نرخ تغییر ITT'),
    ('TE-505', 'B', 'TOT: خروجی FPT = ورودی سمت داغ recuperator', 'R-ENG', TC, '0–900 °C (طراحی ~610)', '±1.5 K / 0.4 %', '10 Hz',
     'هد TC + KX', 'B2', 'TC06', 'C,P', 'محدودیت نرخ گرم‌شدن recuperator؛ trip > 660 °C'),
    ('TE-101', 'B', '(تگ docs/hvac) دمای گاز اگزوز ورودی HX-1، بعد از recuperator', 'R-CHP', TC, '0–600 °C (طراحی ~262)', '±1.5 K', '2 Hz',
     'هد TC + KX', 'B2', 'TC07', 'P,M', 'H 320 °C = عیب recuperator (آلارم ECU)؛ محاسبهٔ گرما در B6-R'),
    ('TE-512', 'B', 'رزرو (دمای دودکش TE-103 و خروجی HX-1 TE-102 روی B6-R هستند)', 'R-ENG', TC, '—', '—', '—', '—', 'B2', 'TC08', 'M', 'رزرو'),
    ('TE-508', 'B', 'دمای هوزینگ یاتاقان عقب هسته (سمت داغ)', 'R-ENG', TC, '0–300 °C', '±1.5 K', '2 Hz', 'هد TC + KX', 'B2', 'TC09', 'P,M',
     'آلارم 140 / trip 160 °C (موقت، با تست تأیید شود)'),
    ('TE-509', 'B', 'دمای هوای ناحیهٔ داغ جعبه (کنار محفظه)', 'R-ENG', TC, '0–250 °C', '±1.5 K', '1 Hz', 'هد TC + KX', 'B2', 'TC10', 'P,M',
     'آلارم نشتی گاز داغ / عایق'),
    ('TE-510', 'B', 'رزرو: interduct/ورودی NGV FPT یا مسیر bypass', 'R-ENG', TC, '0–1000 °C', '±1.5 K', '10 Hz', 'هد TC + KX', 'B2', 'TC11', 'M', 'رزرو'),
    ('TE-511', 'B', 'رزرو', 'R-ENG', TC, '—', '—', '—', '—', 'B2', 'TC12', 'M', 'رزرو'),

    # ---------------------------------------------------------------- C: air & hot-gas pressures
    ('PT-521', 'C', 'P2: فشار خروجی کمپرسور (sense line ≥ 300 mm برای خنک‌شدن)', 'R-ENG', MA + '، پاسخ < 1 ms',
     '0–6 bar abs (طراحی ~3.1)', '±0.25 % FS', '2 kS/s (تشخیص سرج)', 'M12 4-pin A', 'B2', 'FAI1 (ADS131M04 #2 ch0)', 'C,P',
     'سرج، برنامهٔ شتاب W_f/P2'),
    ('PT-522', 'C', 'P3: بعد از سمت سرد recuperator / ورودی محفظه', 'R-ENG', MA, '0–6 bar abs (~2.9)', '±0.25 % FS', '50 Hz', 'M12 4-pin A',
     'B2', 'AI01 (ADS124S08 #1)', 'M', 'ΔP recuperator و محفظه'),
    ('PT-524', 'C', 'P45: فشار interduct (بین توربین هسته و FPT)', 'R-ENG', MA, '0–4 bar abs', '±0.25 % FS', '50 Hz', 'M12 4-pin A',
     'B2', 'AI02', 'M', 'نسبت فشار FPT'),
    ('PT-101', 'C', '(تگ docs/hvac) فشار برگشتی اگزوز قبل از diverter D-101', 'R-CHP', MA, '−0.5…+2.5 kPa g', '±0.5 % FS', '10 Hz', 'M12 4-pin A',
     'B2', 'AI03', 'P,M', 'H 1.0 kPa → ALM؛ HH 1.5 kPa → FSD (آستانه از docs/hvac)'),
    ('PDT-526', 'C', 'ΔP دهانهٔ bellmouth ورودی کمپرسور (دبی جرمی هوا)', 'R-AIR', MA, '0–25 mbar', '±0.25 % FS', '10 Hz', 'M12 4-pin A',
     'B2', 'AI04', 'M', 'heat-rate و پایش عملکرد'),

    # ---------------------------------------------------------------- D: fuel gas train, ignition, flame
    ('XV-610', 'D', 'شیر قطع اصلی گاز روی رایزر (بیرون جعبه)، NC، 24 VDC، EN 161 کلاس A', 'R-ROOF',
     'DO 24 V، 0.5 A (از خروجی ایمن SR1 → B4)', 'باز/بسته', '—', '—', 'EN 175301-803 A', 'B4', 'DO01 (via SR1-O3)', 'C,P',
     'روی نشت گاز، آتش و ESD بسته می‌شود'),
    ('ZSC-610', 'D', 'سوییچ وضعیت بسته XV-610', 'R-ROOF', 'DI 24 V (NC = closed)', '—', '—', '10 Hz', 'M12', 'B2', 'DI01', 'M', ''),
    ('PT-601', 'D', 'فشار گاز تغذیه (قبل از SSVها)', 'R-GAS', MA + '، سازگار با متان', '0–10 barg (طراحی 4، حداقل 3.5)', '±0.25 % FS',
     '10 Hz', 'M12 4-pin A', 'B2', 'AI05', 'P,M', 'آلارم < 3.5، start inhibit < 3.2'),
    ('PSL-602', 'D', 'کلید فشار پایین گاز (EN 1854)، تنظیم 3.0 barg', 'R-GAS', 'کنتاکت NC دوکاناله', '—', '—', 'سخت‌افزاری',
     'EN 175301-803', 'SR1', 'S07 + B2 DI02 (کپی)', 'P', 'زنجیرهٔ ایمنی'),
    ('PSH-603', 'D', 'کلید فشار بالای گاز، تنظیم 5.0 barg (خرابی رگولاتور)', 'R-GAS', 'کنتاکت NC', '—', '—', 'سخت‌افزاری',
     'EN 175301-803', 'SR1', 'S07 (سری با PSL) + B2 DI03', 'P', 'زنجیرهٔ ایمنی'),
    ('PT-604', 'D', 'فشار بعد از رگولاتور (ورودی شیر تناسبی)', 'R-GAS', MA, '0–6 barg (~3.0)', '±0.25 % FS', '10 Hz', 'M12 4-pin A',
     'B2', 'AI06', 'M', ''),
    ('XV-611', 'D', 'SSV1: شیر قطع ایمنی اول (EN 161 کلاس A، pmax ≥ 6 bar، 24 VDC، بسته‌شدن < 1 s)', 'R-GAS',
     'DO 24 V از SR1 کانال A در سری با B4', 'باز/بسته', '—', '—', 'EN 175301-803 A', 'B4', 'DO02 (via SR1-O1)', 'C,P', 'double block'),
    ('XV-612', 'D', 'SSV2: شیر قطع ایمنی دوم (مثل SSV1)', 'R-GAS', 'DO 24 V از SR1 کانال B در سری با B4', 'باز/بسته', '—', '—',
     'EN 175301-803 A', 'B4', 'DO03 (via SR1-O2)', 'C,P', 'double block'),
    ('ZSC-611', 'D', 'proof-of-closure SSV1', 'R-GAS', 'DI 24 V', '—', '—', '10 Hz', 'M12', 'B2', 'DI04 + SR1 S08 (پایش)', 'P', 'پیش‌شرط استارت'),
    ('ZSC-612', 'D', 'proof-of-closure SSV2', 'R-GAS', 'DI 24 V', '—', '—', '10 Hz', 'M12', 'B2', 'DI05 + SR1 S08', 'P', ''),
    ('XV-621', 'D', 'شیر vent بین SSV1 و SSV2 (NO، energize-to-close) → دودکش امن', 'R-GAS', 'DO 24 V از SR1', 'باز/بسته', '—', '—',
     'EN 175301-803 A', 'B4', 'DO04 (via SR1-O1)', 'P', 'double-block-and-bleed'),
    ('PT-613', 'D', 'فشار فضای بین SSV1 و SSV2 (آزمون نشتی شیرها، valve proving)', 'R-GAS', MA, '0–6 barg', '±0.25 % FS', '10 Hz',
     'M12 4-pin A', 'B2', 'AI07', 'P', 'proving قبل از هر استارت و بعد از توقف'),
    ('FCV-620', 'D', 'شیر تناسبی سوخت (metering) — PWM جریان‌کنترل', 'R-GAS', 'PWM 24 V، 0–1 A، dither 200 Hz', '0–100 %',
     '±1 % جریان', 'حلقهٔ جریان 5 kHz', 'EN 175301-803 / M12', 'B4', 'PO01', 'C', 'حلقهٔ بیرونی با FT-606'),
    ('PT-605', 'D', 'فشار مانیفولد گاز (بعد از شیر تناسبی، قبل از انژکتورها)', 'R-GAS', MA, '0–6 barg (~2.5)', '±0.25 % FS',
     '1 kS/s', 'M12 4-pin A', 'B2', 'FAI2 (ADS131M04 #2 ch1)', 'C,M', 'تخمین دبی، تشخیص گرفتگی انژکتور'),
    ('FT-606', 'D', 'دبی‌سنج جرمی حرارتی گاز (thermal MFM)', 'R-GAS', '4–20 mA (+ Modbus RTU)', '0–20 Nm³/h (0–4 g/s)', '±1 % RD',
     '50 Hz', 'M12 5-pin', 'B2', 'AI08', 'C,M', 'طراحی 11.2 Nm³/h؛ heat-rate و life'),
    ('TE-607', 'D', 'دمای گاز', 'R-GAS', RTD, '-10–+70 °C', '±0.3 K', '1 Hz', 'M12 4-pin', 'B2', 'RTD02 (MAX31865)', 'M', 'جبران چگالی'),
    ('FQ-608', 'D', 'کنتور گاز شرکت گاز (پالس LF reed)', 'R-ROOF', 'پالس خشک', '0.1 m³/پالس', 'کلاس کنتور', 'هر پالس', 'کابل کنتور',
     'B2', 'FI04', 'M', 'حسابداری انرژی'),
    ('IGN-630', 'D', 'اگزایتر جرقه (24 VDC، ≥ 8 kV، 50–200 جرقه/ثانیه)', 'R-ENG', 'DO 24 V، 2 A (از SR1-O4)', 'روشن/خاموش', '—', '—',
     'M12 / ترمینال', 'B4', 'DO05', 'C', 'کابل HV سیلیکونی ≤ 1 m، دور از سیگنال'),
    ('BE-631', 'D', 'سنسور شعلهٔ UV (Hamamatsu R2868 + درایور C10807) پشت پنجرهٔ کوارتز', 'R-ENG', 'پالس open-collector (C10807)، تغذیهٔ 12 V از B1 (SMCU)', '0–5000 cps (پس‌زمینه < 10 cpm)',
     '—', 'شمارش 100 ms', 'M12 4-pin → کابل W102b', 'B1', 'SPD-IN4 (SMCU + H7)', 'C,P', 'flame-out در SMCU و ECU'),

    # ---------------------------------------------------------------- E: oil
    ('PT-701', 'E', 'فشار روغن تغذیه (بعد از فیلتر، به جت‌ها)', 'R-ENG', MA, '0–10 barg', '±0.25 % FS', '50 Hz', 'M12 4-pin A', 'B2', 'AI09',
     'C,P', 'PID سرعت پمپ روغن؛ آلارم/trip (مقادیر با طراحی سیستم روغن)'),
    ('PSL-702', 'E', 'کلید فشار پایین روغن (مکانیکی، مستقل از PT-701)', 'R-ENG', 'کنتاکت NC', 'تنظیم ~1.0 barg (TBD)', '—', 'سخت‌افزاری',
     'EN 175301-803', 'SR1', 'S09 + B2 DI06', 'P', 'زنجیرهٔ ایمنی (Stop cat 0)'),
    ('PDS-703', 'E', 'ΔP فیلتر روغن (10 µm)', 'R-ENG', 'DI 24 V', 'تنظیم 1.5 bar', '—', '1 Hz', 'M12', 'B2', 'DI07', 'M', 'آلارم تعویض فیلتر'),
    ('TE-704', 'E', 'دمای مخزن روغن', 'R-ENG', RTD, '-10–150 °C', '±0.3 K', '1 Hz', 'M12 4-pin', 'B2', 'RTD03', 'C,P', 'گرمکن و مجوز استارت'),
    ('TE-705', 'E', 'دمای روغن برگشتی یاتاقان‌های هسته', 'R-ENG', RTD, '0–200 °C', '±0.5 K', '2 Hz', 'M12 4-pin', 'B2', 'RTD04', 'P,M', ''),
    ('TE-706', 'E', 'دمای روغن برگشتی یاتاقان‌های FPT/PMG', 'R-ENG', RTD, '0–200 °C', '±0.5 K', '2 Hz', 'M12 4-pin', 'B2', 'RTD05', 'P,M', ''),
    ('LSL-707', 'E', 'سطح پایین مخزن روغن (float)', 'R-ENG', 'DI 24 V', '—', '—', '1 Hz', 'M12', 'B2', 'DI08', 'P', 'start inhibit / آلارم'),
    ('M-710', 'E', 'پمپ روغن فشار (gear pump + BLDC 48 V)', 'R-ENG', 'درایو BLDC سه‌فاز 48 V، 10 A + Hall', '0–4000 rpm', '—',
     'حلقهٔ سرعت 1 kHz', 'M12 power + Hall', 'B4', 'MD2', 'C', 'pre-lube، post-lube از UPS 48 V'),
    ('M-711', 'E', 'پمپ scavenge (اگر طراحی روغن لازم بداند)', 'R-ENG', 'درایو BLDC 48 V، 5 A', '—', '—', '—', 'M12', 'B4', 'MD4 (رزرو)', 'C', 'TBD'),
    ('EH-712', 'E', 'گرمکن مخزن روغن 200 W', 'R-ENG', 'DO 24 V → SSR', 'روشن/خاموش', '—', '—', 'ترمینال', 'B4', 'DO06', 'C', 'استارت زمستان'),
    ('TE-720', 'E', 'دمای یاتاقان FPT سمت توربین (PT1000 جاسازی‌شده)', 'R-ENG', RTD, '0–200 °C', '±0.5 K', '2 Hz', 'M12 4-pin', 'B2', 'RTD06',
     'P,M', 'آلارم 120 / trip 135 °C (موقت)'),
    ('TE-721', 'E', 'دمای یاتاقان PMG سمت آزاد', 'R-ENG', RTD, '0–200 °C', '±0.5 K', '2 Hz', 'M12 4-pin', 'B2', 'RTD07', 'P,M', ''),

    # ---------------------------------------------------------------- F: PMG / electronics coolant
    ('M-751', 'F', 'پمپ مدار بستهٔ خنک‌کاری PMG + B3 + خنک‌کن روغن (گلیکول ~30 %)', 'R-ENG', 'BLDC 48 V، PWM + tach', '0–100 %', '—',
     '10 Hz', 'M12 5-pin', 'B4', 'MD3', 'C', 'بعد از توقف 15 min ادامه'),
    ('FT-752', 'F', 'دبی مدار خنک‌کاری (توربینی/vortex)', 'R-ENG', 'پالس 24 V', '1–30 L/min', '±2 %', 'هر پالس', 'M12', 'B2', 'FI03', 'P',
     'دبی کم → آلارم 5 s، CSD 30 s'),
    ('TE-GLY', 'F', '(تگ docs/hvac) دمای رفت گلیکول مدار کمکی از dry cooler DC-1 به PMG / B3 / خنک‌کن روغن', 'R-CHP', RTD, '0–120 °C', '±0.3 K', '1 Hz',
     'M12 4-pin', 'B2', 'RTD08', 'C,P,M', 'آلارم > 50 °C؛ حلقهٔ PI فن DC-1'),
    ('DC-1-FAN', 'F', '(تگ docs/hvac) فن EC dry cooler مدار کمکی گلیکول', 'R-CHP', 'تغذیه از BOP-R + فرمان 0–10 V/PWM و tach از B4', '0–100 %',
     '—', '1 Hz', 'M12 5-pin', 'B4', 'FAN3', 'C', 'PI روی TE-GLY؛ موتور به مدار آب CHP وابسته نیست'),
    ('TE-754', 'F', 'دمای برگشت مایع خنک‌کن (بعد از PMG)', 'R-ENG', RTD, '0–100 °C', '±0.3 K', '1 Hz', 'M12 4-pin', 'B2', 'RTD09', 'M', 'تلفات PMG'),
    ('PT-755', 'F', 'فشار مدار خنک‌کاری (تشخیص نشتی)', 'R-ENG', MA, '0–4 barg', '±0.5 % FS', '2 Hz', 'M12 4-pin A', 'B2', 'AI10', 'P,M', ''),
    ('LSL-756', 'F', 'سطح پایین منبع انبساط', 'R-ENG', 'DI 24 V', '—', '—', '1 Hz', 'M12', 'B2', 'DI09', 'P', ''),
    ('TE-760', 'F', 'دمای سیم‌پیچ PMG فاز U (PT1000 جاسازی، عایق تقویت‌شده)', 'R-ENG', RTD + '، ورودی ایزولهٔ B3', '0–220 °C', '±1 K',
     '2 Hz', 'کانکتور ترمینال ژنراتور', 'B3', 'RTD-W1', 'P', 'کلاس H: آلارم 140، CSD 155 °C'),
    ('TE-761', 'F', 'دمای سیم‌پیچ PMG فاز V', 'R-ENG', RTD, '0–220 °C', '±1 K', '2 Hz', '—', 'B3', 'RTD-W2', 'P', ''),
    ('TE-762', 'F', 'دمای سیم‌پیچ PMG فاز W', 'R-ENG', RTD, '0–220 °C', '±1 K', '2 Hz', '—', 'B3', 'RTD-W3', 'P', ''),

    # ---------------------------------------------------------------- G: enclosure & safety
    ('ESD-R', 'G', '(تگ docs/hvac) E-stop روی در جلوی جعبه (بام)', 'R-ELC', '2× NC دوکاناله', '—', '—', 'سخت‌افزاری', 'M12 8-pin', 'SR1',
     'S01 + B2 DI10 (وضعیت)', 'P', 'Stop cat 0'),
    ('ESD-E', 'G', 'E-stop اتاق برق', 'ER', '2× NC دوکاناله', '—', '—', 'سخت‌افزاری', 'ترمینال', 'SR1', 'S02 (کابل W103) + B1 DI01', 'P', 'Stop cat 0'),
    ('ESD-H', 'G', 'E-stop سالن/دفتر (اختیاری)', 'HALL', '2× NC', '—', '—', 'سخت‌افزاری', 'ترمینال', 'SR1', 'S03 (سری با S02)', 'P', ''),
    ('ZS-811', 'G', 'کلید درِ چپ جعبه (کدشدهٔ مغناطیسی، 2 کانال)', 'R-ENG', '2× OSSD/NC', '—', '—', 'سخت‌افزاری', 'M12 8-pin', 'SR1',
     'S04 + B2 DI11', 'P', 'Stop cat 1، تأخیر 3 s'),
    ('ZS-812', 'G', 'کلید درِ راست جعبه', 'R-ENG', '2× OSSD/NC', '—', '—', 'سخت‌افزاری', 'M12 8-pin', 'SR1', 'S05 + B2 DI12', 'P', 'Stop cat 1'),
    ('ZS-813', 'G', 'کلید سقف برداشتنی / دریچهٔ سرویس', 'R-ENG', '2× OSSD/NC', '—', '—', 'سخت‌افزاری', 'M12 8-pin', 'SR1', 'S06 + B2 DI13', 'P', 'Stop cat 1'),
    ('ZS-814', 'G', 'درِ تابلوی برق RP-1 (قفل کلیدی، فقط آلارم)', 'R-ELC', 'DI 24 V', '—', '—', '1 Hz', 'M12', 'B2', 'DI14', 'M', 'بدون trip؛ ثبت دسترسی'),
    ('AT-821', 'G', 'آشکارساز متان NDIR — ناحیهٔ قطار گاز (بالا)', 'R-GAS', '4–20 mA + رله 10 % و 20 % LEL', '0–100 % LEL', '±3 % LEL',
     '2 Hz', 'M20 گلند / M12', 'B2', 'AI11 + DI15 (10 %) + SR1 S10 (20 %)', 'P', '10 % → آلارم + تهویه max؛ 20 % → ESD + XV-610'),
    ('AT-822', 'G', 'آشکارساز متان NDIR — سقف ناحیهٔ موتور', 'R-ENG', '4–20 mA + رله 10/20 %', '0–100 % LEL', '±3 % LEL', '2 Hz',
     'M20 / M12', 'B2', 'AI12 + DI16 + SR1 S10', 'P', ''),
    ('PDSL-831', 'G', 'اثبات تهویهٔ جعبه (ΔP switch)', 'R-ENG', 'کنتاکت NC', 'تنظیم 50 Pa', '—', 'سخت‌افزاری', 'M12', 'SR1',
     'S11 (تأخیر 10 s) + B2 DI17', 'P', 'purge جعبه قبل از استارت'),
    ('M-832', 'G', 'فن تهویهٔ جعبه 1 (EC 48 V)', 'R-ENG', 'تغذیهٔ 48 V سوییچ‌شده + 0–10 V + tach', '0–100 %', '—', '1 Hz', 'M12 5-pin', 'B4',
     'FAN1', 'C', 'Ex ec در صورت طبقه‌بندی Zone 2'),
    ('M-833', 'G', 'فن تهویهٔ جعبه 2 (افزونه)', 'R-ENG', 'مثل M-832', '0–100 %', '—', '1 Hz', 'M12 5-pin', 'B4', 'FAN2', 'C', 'N+1'),
    ('TE-834', 'G', 'دمای هوای جعبه (ناحیهٔ موتور)', 'R-ENG', RTD, '0–120 °C', '±0.5 K', '1 Hz', 'M12 4-pin', 'B2', 'RTD10', 'P,M',
     'آلارم 60، CSD 70 °C'),
    ('TE-835', 'G', 'دمای هوای تابلوی RP-1', 'R-ELC', 'سنسور روی برد B2', '0–85 °C', '±1 K', '1 Hz', '—', 'B2', 'internal', 'P,M', 'آلارم 50 °C'),
    ('TSH-836', 'G', 'آشکارساز حرارتی آتش (ثابت 90 °C + rate-of-rise)', 'R-ENG', 'کنتاکت NC', '—', '—', 'سخت‌افزاری', 'ترمینال', 'SR1',
     'S12 + B2 DI18', 'P', 'ESD + بستن XV-610'),
    ('XA-840', 'G', 'چراغ وضعیت سه‌رنگ + آژیر روی جعبه', 'R-ELC', 'DO 24 V ×4', '—', '—', '—', 'M12', 'B4', 'DO07–DO10', 'M', ''),
    ('HS-841', 'G', 'کلید سلکتور کلیدی OFF / LOCAL / REMOTE / MAINT', 'R-ELC', 'DI 24 V ×2 (کدشده)', '—', '—', '10 Hz', 'ترمینال', 'B2',
     'DI19–DI20', 'C', 'استارت از راه دور فقط در REMOTE'),
    ('HS-842', 'G', 'شستی reset ایمنی (محلی، روی بام)', 'R-ELC', 'NO', '—', '—', 'سخت‌افزاری', 'ترمینال', 'SR1', 'RESET + B2 DI21', 'P',
     'reset تریپ‌های ایمنی فقط محلی'),
    ('XS-850', 'G', 'B3 HEALTHY (سخت‌افزاری، dynamic)', 'R-ELC', 'خروجی رله/OSSD از B3', '—', '—', 'سخت‌افزاری', 'ترمینال', 'SR1',
     'S13 + B1 DI02', 'P', 'افت → B3b ترمز + ESD'),
    ('XS-851', 'G', 'SMCU PERMIT کانال A و B (پالسی، از B1)', 'ER', '2× خروجی dynamic → رله force-guided', '—', '—', 'سخت‌افزاری',
     'کابل W103', 'SR1', 'S14', 'P', 'watchdog سخت‌افزاری'),
    ('XS-852', 'G', 'ECU RUN PERMIT (H7 از طریق watchdog خارجی STWD100)', 'ER', 'خروجی رله', '—', '—', 'سخت‌افزاری', 'کابل W103', 'SR1',
     'S15', 'P', ''),
    ('XS-853', 'G', 'بازخورد وضعیت SR1 (خروجی‌های ایمن روشن/خاموش، خطا)', 'R-ELC', 'DO SR1 → DI', '—', '—', '100 Hz', 'کابل W103',
     'B1', 'DI03–DI04 (H7 و SMCU)', 'P', 'تست دوره‌ای زنجیره'),
    ('TSH-860', 'G', 'کلید حرارتی مقاومت ترمز (NC، 200 °C)', 'R-ROOF', 'کنتاکت NC', '—', '—', 'سخت‌افزاری', 'ترمینال', 'B3',
     'DI-R1 (+ مدل حرارتی)', 'P', 'آلارم → CSD'),

    # ---------------------------------------------------------------- H: intake & ambient
    ('TE-501', 'H', 'T1: دمای هوای ورودی کمپرسور (پایین‌دست کویل CC-1، کنار bellmouth)', 'R-AIR', RTD, '-20–+60 °C (طراحی 15)', '±0.3 K', '2 Hz',
     'M12 4-pin', 'B2', 'RTD01', 'C,M', 'دور اصلاح‌شده و P_max؛ جدا از TE-221 کنترل کویل (B6-R)'),
    ('PDT-222', 'H', '(تگ docs/hvac) ΔP فیلترهای G4 و F8 ورودی هوا (دو کانال)', 'R-AIR', MA, '0–500 Pa ×2', '±1 % FS', '1 Hz', 'M12 4-pin A', 'B2',
     'AI13–AI14', 'P,M', 'آلارم هر طبقه طبق docs/hvac؛ ECU: مجموع > 400 Pa → DRT، > 480 Pa → CSD'),
    ('PDT-223', 'H', '(تگ docs/hvac) ΔP سمت هوای کویل CC-1', 'R-AIR', MA, '0–500 Pa', '±1 % FS', '1 Hz', 'M12 4-pin A', 'B2', 'AI15', 'P,M',
     'H 300 Pa → آلارم'),
    ('TE-221', 'H', '(تگ docs/hvac) دمای هوای بعد از کویل CC-1 — کنترل TV-221 (SP 15 °C، در COMFORT تا 25 °C)', 'R-AIR', 'RTD روی B6-R → CAN-FD #2',
     '-10–+70 °C', '±0.3 K', '1 Hz', '—', 'B6-R', 'via CAN-FD2', 'M', 'ECU اولویت POWER/COMFORT و P_max را هماهنگ می‌کند'),
    ('TE-104', 'H', '(تگ docs/hvac) دمای هوای ورودی پشت لوور — تشخیص بازچرخش اگزوز/برج', 'R-AIR', 'RTD روی B6-R → CAN-FD #2', '-10–+70 °C',
     '±0.3 K', '1 Hz', '—', 'B6-R', 'via CAN-FD2', 'M', 'TE-104 − TT-OA > 3 K → آلارم'),
    ('TT-OA', 'H', '(تگ docs/hvac) دمای هوای بیرون', 'R-ROOF', '4–20 mA روی B6-R → CAN-FD #2', '-20–+60 °C', '±0.3 K', '0.1 Hz', '—', 'B6-R',
     'via CAN-FD2', 'M', 'پیش‌بینی P_max'),
    ('MT-OA', 'H', '(تگ docs/hvac) رطوبت نسبی هوای بیرون', 'R-ROOF', '4–20 mA روی B6-R → CAN-FD #2', '0–100 % RH', '±2 % RH', '0.1 Hz', '—', 'B6-R',
     'via CAN-FD2', 'M', ''),

    # ---------------------------------------------------------------- I: exhaust & CHP/HVAC hooks
    ('ZC-101', 'I', '(تگ docs/hvac) فرمان diverter D-101 (bypass ↔ HX-1)؛ PI روی TE-111 در B6-R؛ تغذیهٔ actuator از K-EX', 'R-CHP',
     'AO 2–10 V از B6-R', '0–100 %', '±2 %', '1 Hz', '—', 'B6-R', '—', 'M', 'fail-safe: فنر به bypass در ≤ 15 s'),
    ('ZSO-101', 'I', '(تگ docs/hvac) D-101 کاملاً در bypass (limit switch، کنتاکت اول)', 'R-CHP', 'کنتاکت خشک', '—', '—', 'سخت‌افزاری',
     'M12', 'SR1', 'S16 + B2 DI22 (کپی)', 'P', 'مجوز light-off: SSV در استارت فقط با D-101 در bypass؛ کنتاکت دوم ZSO-101b به B6-R'),
    ('K-EX', 'I', '(تگ docs/hvac) رلهٔ ایمنی تغذیهٔ 24 VAC actuator D-101 — افتادن = D-101 به bypass', 'R-CHP',
     'خروجی ایمن SR1-O6 → کنتاکتور force-guided', '—', '—', 'سخت‌افزاری', 'ترمینال BOP-R', 'SR1', 'O6', 'P',
     'قطع با TSHH-111، PSH-111، FSL-111 (10 s)، E-stop، هر trip موتور'),
    ('TSHH-111', 'I', '(تگ docs/hvac) ترموستات حد بالای آب داغ 98 °C، reset دستی', 'R-CHP', 'کنتاکت NC', '98 °C', '—', 'سخت‌افزاری', 'ترمینال',
     'SR1', 'S17 + B6-R (وضعیت)', 'P', 'فقط K-EX را می‌اندازد؛ موتور ادامه می‌دهد'),
    ('PSH-111', 'I', '(تگ docs/hvac) سوییچ فشار بالای مدار آب داغ 5.0 bar', 'R-CHP', 'کنتاکت NC', '5.0 bar', '—', 'سخت‌افزاری', 'ترمینال',
     'SR1', 'S17 (سری)', 'P', 'قبل از PSV 5.5 bar'),
    ('FSL-111', 'I', '(تگ docs/hvac) فلوسوییچ مدار اولیهٔ آب داغ', 'R-CHP', 'کنتاکت NC', '—', '—', 'سخت‌افزاری', 'ترمینال', 'SR1',
     'S18 (تأخیر 10 s)', 'P', 'بی‌دبی → D-101 به bypass'),
    ('ENG-RUN', 'I', '(تگ docs/hvac) سیگنال سخت‌افزاری «موتور روشن / گرما موجود» به B6-R', 'ER', 'کنتاکت خشک رله', '—', '—', '—',
     'کابل W103 → BOP-R', 'B1', 'RO08', 'C', 'پشتیبان CAN برای حالت محلی امن B6-R'),
    ('BOP-BUS', 'I', 'بردهای BOP (B6-R روی بام، B6-E در اتاق برق، طبق docs/hvac): پمپ‌ها، چیلرها، برج، HX-1، TE-111..114، heat meterها، کویل ورودی، DHW', 'R-CHP',
     'CAN-FD #2 (BOP)', '—', '—', '10 Hz', 'کابل W115', 'B1', 'CAN-FD2', 'C,M', 'فهرست کامل در docs/hvac/io_list.csv'),
    ('EH-950', 'I', 'گرمکن برقی منبع DHW (TK-DHW داخل ساختمان؛ dump مفید، 6 kW، SSR سه‌فاز) — قلم جدید، به docs/hvac اضافه شود', 'ER',
     'DO 24 V → SSR (برق از AUX-DB)', '0–6 kW (PWM 1 s)', '—', '1 Hz', 'ترمینال', 'B1', 'RO10', 'C',
     'مصرف مازاد وقتی SOC > 90 %؛ قطع در TE-132 (B6-E) > 75 °C'),

    # ---------------------------------------------------------------- J: electrical
    ('B3-VDC', 'J', 'ولتاژ باس DC یکسوساز (AMC3330 ایزوله)', 'R-ELC', 'داخلی B3', '0–1000 V', '±0.5 %', '40 kHz (کنترل)', '—', 'B3', 'internal',
     'C,P', 'چاپر 800–830 V، OVP سخت‌افزاری 900 V'),
    ('B3-IPH', 'J', 'جریان سه فاز PMG (shunt + AMC3306M25 → SDFM)', 'R-ELC', 'داخلی B3', '±150 A', '±0.5 %', '40 kHz', '—', 'B3', 'internal',
     'C,P', 'desat + OCP سخت‌افزاری'),
    ('B3-IDC', 'J', 'جریان DC خروجی', 'R-ELC', 'داخلی B3', '±60 A', '±0.5 %', '10 kHz', '—', 'B3', 'internal', 'C,M', 'انرژی تولیدی'),
    ('B3-RISO', 'J', 'مقاومت عایقی باس DC نسبت به زمین (اندازه‌گیری با مقاومت سوییچ‌شده)', 'R-ELC', 'داخلی B3', '0–10 MΩ', '±10 %',
     'قبل از وصل + هر 10 s', '—', 'B3', 'internal', 'P', '< 100 kΩ آلارم، < 50 kΩ مانع وصل'),
    ('B3-K', 'J', 'کنتاکتورهای DC اصلی (+/−) و پیش‌شارژ — فرمان و بازخورد', 'R-ELC', 'داخلی B3', '—', '—', '—', '—', 'B3', 'internal', 'C', ''),
    ('B3-CHOP', 'J', 'چاپر مقاومت ترمز (duty، دمای مدل‌شده)', 'R-ELC', 'داخلی B3', '0–100 %', '—', '40 kHz', '—', 'B3', 'internal', 'C,P', ''),
    ('B3B-ST', 'J', 'ترمز مستقل PMG (B3b): وضعیت کنتاکتور NC و چاپر', 'R-ELC', 'DI از B3b', '—', '—', '100 Hz', 'ترمینال', 'B3', 'DI-B1', 'P',
     'مستقل از کنترلر B3'),
    ('INV-MB', 'J', 'اینورتر هیبرید: P/Q/V/f هر فاز، توان PV، SOC و جریان باتری، خطاها، محدودیت‌ها', 'ER', 'Modbus RTU (RS-485)', '—', '—',
     '1 Hz (5 Hz رجیسترهای توان)', 'ترمینال', 'B1', 'RS485-1', 'C,M', 'مبنای load following و SOC'),
    ('INV-DO', 'J', 'فرمان remote ON/OFF اینورتر (dry contact)', 'ER', 'رله', '—', '—', '—', 'ترمینال', 'B1', 'RO05', 'C', ''),
    ('INV-DI', 'J', 'رلهٔ خطای اینورتر', 'ER', 'DI 24 V', '—', '—', '10 Hz', 'ترمینال', 'B1', 'DI05', 'P', 'load rejection'),
    ('BMS-CAN', 'J', 'BMS باتری HV: SOC، SOH، CVL/CCL/DCL، دمای سلول، آلارم‌ها', 'ER', 'CAN 500 kbit/s (listen-only) یا از رجیسترهای اینورتر',
     '—', '—', '1 Hz', 'RJ45/ترمینال', 'B1', 'CAN3', 'M', ''),
    ('BMS-WAKE', 'J', 'بیدارکردن BMS (کنتاکت خشک موازی شستی باتری)', 'ER', 'رله', '—', '—', '—', 'ترمینال', 'B1', 'RO06', 'C', 'black start'),
    ('UPS-DCOK', 'J', 'DC-OK دو شارژر 48 V', 'ER', 'DI 24 V ×2', '—', '—', '1 Hz', 'ترمینال', 'B1', 'DI06–DI07', 'M', ''),
    ('UPS-BMS', 'J', 'BMS باتری 48 V (SOC، ولتاژ، دما)', 'ER', 'CAN/RS-485', '—', '—', '1 Hz', 'RJ45', 'B1', 'CAN3', 'P,M', '< 46 V → CSD'),
    ('JT-901', 'J', 'کنتور انرژی خروجی اینورتر (سه‌فاز، کلاس 0.5S)', 'ER', 'Modbus RTU', '—', '±0.5 %', '1 Hz', 'ترمینال', 'B1', 'RS485-2', 'M', ''),
    ('JT-902', 'J', 'کنتور انرژی AUX-DB (مصرف داخلی)', 'ER', 'Modbus RTU', '—', '±1 %', '1 Hz', 'ترمینال', 'B1', 'RS485-2', 'M', 'برق خالص'),
    ('VFD-P1..Pn', 'J', 'VFD پمپ‌های ۳ kW شرکت (Modbus RTU): فرمان، سرعت، جریان، خطا', 'HALL', 'Modbus RTU', '—', '—', '1 Hz', 'ترمینال',
     'B1', 'RS485-2', 'C,M', 'استارت پله‌ای'),
    ('K-LS1..4', 'J', 'کنتاکتورهای load shedding تابلوی شرکت (۴ گروه)', 'HALL', 'RO → رله واسط 24 VDC', '—', '—', '—', 'کابل W109', 'B1',
     'RO01–RO04', 'C', ''),
    ('ZS-LS1..4', 'J', 'کنتاکت کمکی کنتاکتورهای load shedding', 'HALL', 'DI 24 V ×4', '—', '—', '10 Hz', 'کابل W109', 'B1', 'DI08–DI11', 'M', ''),
    ('ZS-COS', 'J', 'موقعیت کلید تبدیل نیروگاه/شبکه (bypass نگهداری)', 'HALL', 'DI 24 V ×2', '—', '—', '1 Hz', 'کابل W109', 'B1', 'DI12–DI13', 'M', ''),
    ('XS-SPD', 'J', 'وضعیت SPDها (همه با کنتاکت سیگنال)', 'ER', 'DI 24 V', '—', '—', '0.1 Hz', 'ترمینال', 'B1', 'DI14 (ER) / B2 DI23 (بام)', 'M', ''),
    ('SD-E', 'J', '(تگ docs/hvac) دتکتور دود اتاق برق/باتری (از پنل آتش)', 'ER', 'DI 24 V', '—', '—', '1 Hz', 'ترمینال', 'B1', 'DI15', 'P', 'آلارم + CSD'),
    ('TT-ER', 'J', 'دما و رطوبت اتاق برق', 'ER', 'Modbus RTU', '0–50 °C', '±0.5 K', '0.1 Hz', 'ترمینال', 'B1', 'RS485-2', 'M', 'باتری ≤ 30 °C'),
    ('XS-GRID', 'J', 'حضور شبکه (رلهٔ ولتاژ سمت برق شهر) — برای v2', 'HALL', 'DI 24 V', '—', '—', '10 Hz', 'ترمینال', 'B1', 'DI16', 'M', ''),
    ('XA-BLD', 'J', 'آلارم مشترک به ساختمان / نگهبانی', 'ER', 'رله', '—', '—', '—', 'ترمینال', 'B1', 'RO07', 'M', ''),
]

ROLE = {'C': 'کنترل', 'P': 'حفاظت', 'M': 'پایش'}


def md_escape(s):
    return str(s).replace('|', '\\|')


def main():
    tags = [r[0] for r in IO]
    dup = [t for t, n in collections.Counter(tags).items() if n > 1]
    assert not dup, dup
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['tag', 'group', 'description', 'location', 'signal', 'range', 'accuracy', 'rate', 'connector', 'board', 'channel', 'role', 'notes'])
        for r in IO:
            w.writerow([r[0], GROUPS[r[1]], r[2], LOC[r[3]], *r[4:]])

    lines = []
    lines.append('# GR180-CCHP — فهرست ورودی/خروجی (I/O list)\n')
    lines.append('تاریخ: ۲۰۲۶-۱۰-۲۱ · **فایل تولیدشده** از `docs/electrical/calc/io_list.py` (منبع واحد). '
                 'نسخهٔ CSV: [`02_io_list.csv`](02_io_list.csv). معماری و بردها: [`00_electrical_control_architecture.md`](00_electrical_control_architecture.md)؛ '
                 'آستانه‌های trip: [`03_control_philosophy.md`](03_control_philosophy.md)؛ کابل‌ها: [`05_cable_schedule.md`](05_cable_schedule.md).\n')
    lines.append('**قواعد عمومی**\n')
    lines.append('- همهٔ ترموکوپل‌ها **ungrounded** هستند (جلوگیری از حلقهٔ زمین با MAX31856 غیرایزوله)؛ اتصال TC به مس فقط روی ترمینال‌های ایزوترمال B2، کنار CJC.')
    lines.append('- سیگنال‌های 4–20 mA از B2 تغذیهٔ حلقه می‌گیرند (24 V محدود‌شده با PTC + TVS)؛ مقاومت شانت 50 Ω دقیق 0.1 %.')
    lines.append('- تجهیزات داخل ناحیهٔ گاز در صورت طبقه‌بندی Zone 2 (IEC 60079-10-1) باید **Ex ec / Ex nA** یا ATEX Cat 3 باشند؛ هدف طراحی تهویه، ناحیهٔ «NE» است.')
    lines.append('- «role»: C کنترل، P حفاظت (ارجاع به جدول trip)، M پایش/life counter.')
    lines.append('- مکان: ' + '؛ '.join('`%s` = %s' % (k, v) for k, v in LOC.items()) + '.\n')
    for g, title in GROUPS.items():
        rows = [r for r in IO if r[1] == g]
        lines.append('## %s. %s\n' % (g, title))
        lines.append('| Tag | شرح | مکان | نوع سیگنال | رنج | دقت | نرخ نمونه | کانکتور | برد / کانال | نقش | یادداشت |')
        lines.append('|---|---|---|---|---|---|---|---|---|---|---|')
        for r in rows:
            role = '، '.join(ROLE[x] for x in r[11].split(','))
            lines.append('| `%s` | %s | %s | %s | %s | %s | %s | %s | **%s** %s | %s | %s |' % (
                r[0], md_escape(r[2]), r[3], md_escape(r[4]), md_escape(r[5]), md_escape(r[6]), md_escape(r[7]),
                md_escape(r[8]), r[9], md_escape(r[10]), role, md_escape(r[12])))
        lines.append('')

    # channel budget per board (counted from the list, spares added in the board spec)
    lines.append('## بودجهٔ کانال هر برد (شمرده‌شده از همین فهرست)\n')
    def chans(text, prefix):
        out = set()
        for m in re.finditer(r'(?<![A-Z])%s(\d+)(?:\s*[–-]\s*%s(\d+))?' % (prefix, prefix), text):
            lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
            out.update(range(lo, hi + 1))
        return out

    def part(r, board):                     # the piece of the channel text that belongs to `board`
        ch = r[10]
        if r[9] == board:
            return re.split(r'\bB[1-5] ', ch)[0]
        m = re.search(r'%s (\S+)' % board, ch)
        return m.group(1) if m else ''

    budget = [  # (label, board, prefixes, capacity)
        ('B2 TC (MAX31856 ×12)', 'B2', ['TC'], 12), ('B2 RTD (MAX31865 ×12)', 'B2', ['RTD'], 12),
        ('B2 AI 4–20 mA (ADS124S08 ×2)', 'B2', ['AI'], 24), ('B2 fast AI / IEPE (ADS131M04 ×2)', 'B2', ['VIB', 'FAI'], 8),
        ('B2 frequency/pulse', 'B2', ['FI'], 6), ('B2 DI 24 V (ISO1212 ×16)', 'B2', ['DI'], 32),
        ('B4 DO 24 V high-side', 'B4', ['DO'], 16), ('B4 PWM current out', 'B4', ['PO'], 4), ('B4 AO 0–10 V', 'B4', ['AO'], 4),
        ('B4 BLDC drives (MD) + fans', 'B4', ['MD', 'FAN'], 8),
        ('B1 speed/pulse inputs SPD-IN (×2 MCU)', 'B1', ['IN'], 6), ('B1 DI 24 V (ISO1212 ×12)', 'B1', ['DI'], 24), ('B1 relay out', 'B1', ['RO'], 12),
        ('SR1 safety inputs (2-ch)', 'SR1', ['S'], 24),
    ]
    lines.append('| نوع | کانال استفاده‌شده | ظرفیت برد | ذخیره |')
    lines.append('|---|---|---|---|')
    for lab, board, prefixes, capn in budget:
        used = set()
        for r in IO:
            t = part(r, board)
            if board == 'B1' and prefixes == ['IN']:
                t = r[10]
            for pf in prefixes:
                used |= {(pf, n) for n in chans(t, pf)}
        lines.append('| %s | %d | %d | %d |' % (lab, len(used), capn, capn - len(used)))
    n_hv = sum(1 for r in IO if 'docs/hvac' in r[2])
    lines.append('| تگ‌های مشترک با docs/hvac (هم‌نام) | %d | — | — |' % n_hv)
    lines.append('')
    lines.append('> ظرفیت‌ها حدود ۲۰–۳۰ ٪ ذخیره دارند. هر تغییر I/O فقط در `calc/io_list.py` انجام شود و فایل دوباره ساخته شود.\n')
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('wrote %s (%d points) and %s' % (os.path.relpath(OUT_MD), len(IO), os.path.relpath(OUT_CSV)))


if __name__ == '__main__':
    main()
