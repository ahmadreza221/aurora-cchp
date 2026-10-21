# GR180-CCHP — انتخاب قطعات (rev 2: اروپایی)

تاریخ: ۲۰۲۶-۱۰-۲۱ · سند اصلی: [`00_electrical_control_architecture.md`](00_electrical_control_architecture.md)

## ۰. سیاست تأمین (تصمیم کاربر، D17)

- **قطعات اروپایی در همه‌جا:**
  - ST (فرانسه/ایتالیا/سوئیس)، Infineon (آلمان)، NXP و Nexperia (هلند)، Semikron-Danfoss (آلمان/دانمارک)، Würth (آلمان)
  - RECOM (اتریش)، Traco (سوئیس)، LEM (سوئیس)، Melexis (بلژیک)، Isabellenhütte (آلمان)، WIMA (آلمان)، Finder (ایتالیا)، Phoenix Contact (آلمان)
- **هیچ قطعهٔ آمریکایی** به کار نمی‌رود: TI، ADI/Maxim، Microchip، Wolfspeed، onsemi، Vishay، Allegro، Littelfuse، Broadcom، Bussmann/Eaton، Honeywell، Sensata.
  - Murata و TDK آمریکایی نیستند. فقط برای یکدستی، معادل اروپایی‌شان (RECOM، EPCOS/TDK Europe) ترجیح داده شده است.
- **استثناها:** جایی که سازندهٔ اروپایی وجود ندارد (PHY اترنت 10/100، فلش سریال)، قطعهٔ **غیرآمریکایی آسیایی** با برچسب ⚑ آمده است.
- **شماره‌های LCSC** در ۲۰۲۶-۱۰-۲۱ از API قطعات JLCPCB استعلام شدند و موجودی همان لحظه کنارشان آمده است.
  - «—» یعنی LCSC موجودی ندارد. این قطعات از توزیع‌کنندهٔ اروپایی (Farnell، RS، Mouser EU، Distrelec، TME) تهیه و برای مونتاژ JLC به‌صورت consigned فرستاده می‌شوند.
  - **مراقب برندهای مشابه** باشید (`-VB`، `-HXY`، `TOKMAS`، `UMW`، …). این‌ها مجاز نیستند.

### جدول جایگزینی (rev 1 → rev 2)

| کارکرد | rev 1 (حذف‌شده) | rev 2 (اروپایی) |
|---|---|---|
| MCU یکسوساز B3 | TI TMS320F28379D | **ST STM32G474** (HRTIM 184 ps، CORDIC/FMAC، 5× ADC 4 MS/s، 7 comparator) |
| MCU ایمنی SMCU | Microchip dsPIC33CK / (STM32G431 موقت) | **NXP S32K144** (Cortex-M4F، ISO 26262 ASIL-B، FlexCAN-FD)؛ تنوع سازنده نسبت به ECU (ST) |
| CAN-FD ایزوله | TI ISO1042 / ADI ADM3055E | **NXP TJA1052i-5** (5 kV) + DC-DC ایزولهٔ RECOM |
| کنترلر CAN سوم | Microchip MCP2518FD | **حذف** (BOP روی Modbus TCP است؛ دو FDCAN داخلی کافی‌اند) |
| RS-485 ایزوله | ADI ADM2587E | **ST ST485EB + ST STISO621** + RECOM R1SX-0505 |
| RS-422 (سرعت) | TI AM26LV31/32 | **ST ST26C31 / ST26C32** |
| ایزولاتور دیجیتال | TI ISO7741/7721 | **ST STISO620/621** |
| ورودی دیجیتال ایزوله | TI ISO1212 | **Infineon ISO1I813T** (8 کانال، IEC 61131-2 نوع 1/3) |
| کلید high-side | TI TPS27S100 | **ST VNI4140K / IPS1025H**، Infineon ITS4300S / BTS3800SL |
| درایور گیت BLDC 48 V | TI DRV8353 | **Infineon 6EDL7141** (MOTIX) یا **ST STDRIVE101** |
| MOSFET 100 V | TI CSD19536 | **Infineon IPB017N10N5** (OptiMOS 5) |
| سنس جریان | TI INA240 | **ST TSC2011** یا CSA داخل 6EDL7141 |
| درایور شیر تناسبی | TI DRV8876 | MOSFET Infineon + شانت + حلقهٔ جریان STM32 |
| گیت‌درایور SiC | TI UCC21750 | **Infineon 1ED3491MU12M** (DESAT، soft-off) / **ST STGAP2SiCS** |
| تغذیهٔ گیت | Murata MGJ2D | **RECOM R24P21503D** (+15/−3 V، 5.2 kV) |
| SiC MOSFET | Wolfspeed C3M | **Infineon IMZA120R020M1H** / ST SCT020H120G3AG |
| سنس جریان و ولتاژ ایزوله | TI AMC3306 / AMC3330 | **کنترلر B3 روی پتانسیل DC−** + شانت Isabellenhütte + آپ‌امپ ST؛ ایزولاسیون فقط در ارتباط و تغذیه؛ پایش مستقل **LEM HO / DVL** (سوئیس) |
| ترموکوپل و RTD | Maxim MAX31856 / MAX31865 | **ST STM32F373** (3× SDADC 16 بیت، PGA تا 32×) به‌عنوان AFE |
| ADC 4–20 mA و ارتعاش | TI ADS124S08 / ADS131M04 | ADC 16 بیتی STM32H7 + آپ‌امپ ST (TSV912 / TSZ122) |
| منبع جریان IEPE | ADI LT3092 | **ST LM317D2T** در حالت منبع جریان (4 mA) |
| خروجی آنالوگ | ADI AD5422 | DAC داخلی STM32 + **ST TSB572** (36 V) |
| رگولاتورها | TI TPS54360، LM5013، TLV755، LM5069 | **RECOM R-78E5.0-1.0 / R-78HB12-0.5**، ST A6986 / L6984 / L7983، ST LDL1117 |
| حفاظت ورودی | TI TPS16630، LM74700 | **ST STEF01** (eFuse) + P-MOSFET Infineon + SMBJ33A (ST) |
| مرجع ولتاژ | TI REF5025 | ST TL1431 / مرجع داخلی STM32 (VREFBUF) |
| حافظهٔ شمارندهٔ عمر | Infineon/Cypress FM25V10 (طراحی آمریکایی) | **ST M95M04** (EEPROM SPI 4 Mbit، 4 میلیون سیکل) با wear-leveling (§۱) |
| USB سرویس ایزوله | ADI ADuM4160 | **حذف**؛ سرویس از راه Ethernet و SWD |
| PHY اترنت | Microchip LAN8742A | ⚑ Realtek RTL8201F (تایوان؛ PHY اروپایی 10/100 وجود ندارد) |
| فلش سریال | Winbond W25Q128 | ⚑ Winbond (تایوان، بدون تغییر) |
| ماژول HMI | Raspberry Pi CM5 (SoC Broadcom) | **NXP i.MX 8M Plus** روی Toradex Verdin (سوئیس) یا Phytec phyCORE (آلمان) |
| کریستال | Abracon | Micro Crystal (سوئیس)، Jauch (آلمان)، Würth WE-XTAL |
| RJ45 و چوک | HanRun، TDK ACT45B | **Würth** 7499010211A، WE-SL5 744235510 |
| رله | Omron G5Q / G7SA | **Finder** 34.51 (سیگنال)، **Finder 50.12** (force-guided، EN 61810-3) |
| سنسور Hall دور | Allegro A1120 | **Melexis US5881** (TO-92UA، هم‌پایه) یا Infineon TLE4964 |
| سنسور شعلهٔ UV | Hamamatsu R2868 | **Durag D-LX 100 UV** (آلمان) یا Siemens QRA2 + AGQ3 |
| شتاب‌سنج | CTC / Wilcoxon / PCB | **Hansford HS-100** (انگلستان)، IFM VSA (آلمان)، Brüel & Kjær (دانمارک) |
| کنتورها | Eastron SDM630 | **Carlo Gavazzi EM24 / EM340**، **Janitza UMG 96**، ABB B23/B24 |
| شارژر و DC-DC 48 V | Mean Well (تایوان) | **Victron** Smart IP43 48/13، **PULS** CD10.242 (آلمان)، Traco |
| اینورتر | Victron + Fronius (rev 2، باتری 48 V) | **rev 3:** Deye SUN-30K-SG01HP3-EU-BM3 + BOS-G20 (چین، غیرآمریکایی، تنها گزینهٔ backup بدون وقفه)؛ اروپایی: SMA Hybrid X 30 (§۸) |
| سوییچ شبکه | Moxa (TW)، Planet | **Westermo** (SE)، **Phoenix FL SWITCH** (DE)، Siemens SCALANCE |

> **چرا M95M04 به‌جای FRAM:**
> - FRAM اروپایی وجود ندارد.
> - شمارندهٔ عمر هر 60 s یک رکورد 32 بایتی با CRC و شمارهٔ ترتیبی می‌نویسد. با ring buffer روی 4 Mbit (16 384 رکورد)، هر سلول حدود هر 11 روز یک بار نوشته می‌شود؛ 4 میلیون سیکل یعنی بیش از 50 سال.
> - **ذخیرهٔ لحظهٔ قطع برق:**
>   - رویداد trip و power-fail بلافاصله نوشته می‌شود. زمان نوشتن صفحه حدود 5 ms است.
>   - خازن نگهدارنده روی 3V3 حداقل 20 ms زمان می‌دهد. برق 24 V از 48 V UPS می‌آید و قطع ناگهانی آن نادر است.
>   - آشکارسازی افت ولتاژ با PVD داخلی STM32 انجام می‌شود.

## ۱. B1 — ECU (اتاق برق)

| کارکرد | قطعه | سازنده | LCSC (موجودی) | یادداشت |
|---|---|---|---|---|
| MCU اصلی | **STM32H743IIT6** (LQFP-176، 140 GPIO، 2× FDCAN، Ethernet MAC) | ST | C89597 (548) | ماشین حالت، گاورنر، EMS، شمارندهٔ عمر |
| MCU ایمنی (SMCU) | **FS32K144HFT0VLLT** (LQFP-100، 112 MHz) | NXP | C515292 (5940) | جایگزین هم‌خانواده: FS32K118LAT0MLHT C3230951 (788)؛ ارزان‌تر: MKE16Z64VLF4 C1339264 (موجودی کم) |
| watchdog خارجی | STWD100NYWY3F | ST | C46043 | پنجره‌ای؛ رلهٔ ECU RUN PERMIT |
| حافظهٔ شمارندهٔ عمر ×2 (H7، SMCU) | **M95M04-DRMN6TP** (SPI EEPROM 4 Mbit) | ST | C1852765 (153) | جایگزین: M95M02 C915963 |
| فلش event recorder | ⚑ W25Q128JVSIQ (QSPI) | Winbond (TW) | C97521 (basic) | — |
| PHY اترنت | ⚑ RTL8201F-VB-CG (RMII) | Realtek (TW) | C45044 (51618) | — |
| RJ45 با مگنتیک | 7499010211A | Würth | — | از توزیع‌کننده |
| CAN-FD ایزوله ×2 (#1 موتور، #2 BMS باتری HV listen-only) | **TJA1052IT/5Y** + RECOM R1SX-0505 | NXP + RECOM | C92210 (8790) + — | — |
| حفاظت CAN | PESD2CANFD24V-T + چوک WE-SL5 744235510 | Nexperia + Würth | C552486 + C5331174 | — |
| RS-485 ایزوله ×3 (HI-1؛ کنتورها و VFD؛ JT-901) | **ST485EBDR** + **STISO621TR** + R1SX-0505 | ST + RECOM | C81186 (6355) + C5447162 (1159) | ESD: SMBJ / ESDA (ST) |
| ورودی‌های سرعت SPD-IN | **ST26C32ABDR** (RS-422، N1-A) + ورودی open-collector با اشمیت‌تریگر (N1-B، N2-B، UV) + **STISO620TR** | ST | C157432 (3953) + C7089838 | هر سیگنال به H7 و SMCU جدا |
| ورودی دیجیتال 24 V (32 کانال) | **ISO1I813T** ×4 | Infineon | C538445 (1510) | SPI، تشخیص قطعی سیم |
| رله‌های عمومی ×16 | Finder 34.51.7.024.0010 + 2× **ULN2803A** | Finder + ST | — | شامل K-LS1..4، K-SP1..3، EH-950 |
| رله‌های force-guided ×3 | Finder 50.12.9.024.1000 | Finder | — | SMCU PERMIT A/B، ECU RUN PERMIT |
| تغذیه | 24 V → **R-78E5.0-1.0** → **LDL1117S33R** (3V3 ECU) و LDL1117S33R جدا (3V3 SMCU) | RECOM + ST | — + C435835 | — |
| حفاظت ورودی 24 V | **SMBJ33A-TR** + P-MOSFET Infineon (معکوس) + **STEF01** (eFuse) | ST + Infineon | C133662 + — | — |
| کریستال | 25 MHz (HSE)، 32.768 kHz (RTC) | Micro Crystal / Jauch | — | — |
| ترمینال‌ها | Phoenix MSTBA 2,5/..-G-5,08 + MSTB، سیگنال MC 1,5/..-3,81 | Phoenix | C90074 + C90073؛ C480511 | قابل‌جداشدن، کددار |

بودجهٔ پایه‌های H7 (176 پایه):
- RMII: 9
- 2× FDCAN: 4
- QSPI: 6
- 3× SPI (DI، M95M04، رزرو): 12
- 2× USART با DE: 6
- 6 ورودی سرعت (TIM capture): 6
- 12 رله: 12
- 4 permit/feedback: 4
- SWD: 2
- نتیجه: **حدود 61 پایه، با جای خالی کافی.**

## ۲. B2 — I/O سنسورها (روی بام، RP-1)

**معماری:**
- کل برد روی زمین محلی جعبه است و ایزولاسیون فقط در CAN و تغذیه است.
- ترموکوپل‌ها ungrounded و حلقه‌های 4–20 mA دوسیمه‌اند.
- **AFE دقیق** روی STM32F373 است و از راه SPI به H7 وصل می‌شود.

| کارکرد | قطعه | LCSC (موجودی) | یادداشت |
|---|---|---|---|
| MCU اصلی | STM32H743VIT6 | C114409 (3628) | FFT ارتعاش، رأی‌گیری ITT، تقویم ارسال CAN |
| AFE ترموکوپل و RTD | **STM32F373VCT6** ×2 (3× SDADC 16 بیت، PGA تا 32×، 21 کانال تفاضلی در هر کدام) | C1121903 (278) | 12 TC + 16 RTD (3-wire نسبتی با منبع جریان مشترک)؛ CJC با PT1000 روی بلوک ایزوترمال؛ تشخیص قطعی TC با pull-up 10 MΩ؛ بدون مالتی‌پلکسر (42 کانال تفاضلی کافی است) |
| 4–20 mA (24 کانال) | ADC 16 بیتی H7 + بافر **TSV912** + شانت 50 Ω 0.1 % (Isabellenhütte) | — | حفاظت: PTC + SMAJ33CA (ST) |
| IEPE و آنالوگ سریع (8 کانال) | ADC 16 بیتی H7 (dual/triple، نمونهٔ هم‌زمان) + فیلتر **TSZ122** / TSV912 | C52941316 | منبع جریان 4 mA: **LM317D2T-TR** (C91673) |
| خروجی RS-422 سرعت N1-A | **ST26C31BDR** | C94192 (16537) | — |
| ورودی دیجیتال (32 کانال) | ISO1I813T ×4 | C538445 | — |
| CAN-FD | TJA1052IT/5Y + R1SX-0505 | C92210 | — |
| تغذیه | 24 V → R-78E5.0-1.0 → LDL1117S33R | — + C435835 | مرجع ADC: VREFBUF |

## ۳. B3 — یکسوساز فعال SiC (PEB) و B3b

**معماری rev 2:**
- کنترلر روی **پتانسیل DC− باس** (سمت HV) قرار می‌گیرد.
- اندازه‌گیری‌ها غیرایزوله‌اند: شانت‌های پایین‌دست فاز، تقسیم‌کنندهٔ ولتاژ باس، تقسیم‌کننده‌های V+/PE و V−/PE برای Riso از راه مقاومت‌های بزرگ.
- **ایزولاسیون تقویت‌شده** فقط در این سه مسیر است:
  - ارتباط (TJA1052i-5، STISO621)
  - تغذیهٔ 24 V (RECOM ایزوله، ≥ 4 kV / 1000 V کار)
  - رلهٔ B3-HEALTHY
- سنسورهای ایزولهٔ LEM برای پایش مستقل استفاده می‌شوند: OCP دوم و OVP دوم.

| کارکرد | قطعه | LCSC (موجودی) | یادداشت |
|---|---|---|---|
| کنترلر | **STM32G474RET6** | C521608 (54) | HRTIM برای PWM 40 kHz و چاپر؛ comparatorهای داخلی برای OCP سریع (< 1 µs)؛ FOC + PV emulation + Riso |
| SiC MOSFET ×7 | **IMZA120R020M1HXKSA1** (CoolSiC 20 mΩ، TO-247-4) | C7207676 (68) | یا ماژول six-pack EasyPACK 2B CoolSiC؛ جایگزین ST SCT020H120G3AG |
| دیود چاپر | IDW20G120C5B | C49450342 | Infineon CoolSiC Schottky |
| گیت‌درایور ×7 | **1ED3491MU12M** (DESAT، soft-off، Miller clamp) | C530929 (288) | جایگزین: 1ED3124MU12H (C5353840)، STGAP2SICSCTR (C5267670) |
| تغذیهٔ گیت ×7 | **RECOM R24P21503D** (+15/−3 V، 5.2 kV) | — | ورودی 24 V از تغذیهٔ ایزولهٔ برد |
| شانت فاز و DC | Isabellenhütte BVR (1 mΩ، 5 W) + **TSZ122** | — + C52941316 | ADC هم‌زمان G474 |
| پایش مستقل | **LEM HO 50-S-0100** (جریان)، **LEM DVL 1000** (ولتاژ باس) | — | سوئیس |
| مقاومت‌های تقسیم HV | EBG (اتریش) یا TT Electronics/Welwyn (انگلستان)، ≥ 1000 V | — | — |
| OVP مستقل 900 V | تقسیم‌کنندهٔ جدا + مقایسه‌گر ST **TS3011** + latch → disable گیت‌ها + چاپر full-on | — | مستقل از MCU |
| CAN-FD ایزوله | TJA1052IT/5Y | C92210 | — |
| خازن DC-link | **WIMA DC-LINK MKP 6** یا **EPCOS B3277x**، 1100 V، ≥ 400 µF، ریپل ≥ 30 A rms | — | بدون الکترولیت |
| کنتاکتورهای DC و پیش‌شارژ | **Schaltbau C195** (1000–1500 V DC، دوطرفه) + رلهٔ پیش‌شارژ 1000 V + 2× 50 Ω 50 W | — | آلمان |
| B3b: پل دیودی | **Semikron SKD 30/12** | — | مستقل از B3 |
| B3b: IGBT + درایور | IKW40N120H3 + **STGAP2SMTR** | C94637 + C2802542 (1116) | منطق آنالوگ بدون نرم‌افزار |
| B3b: تغذیهٔ خودی | فلای‌بک HV با ST **VIPer26K** (1050 V) | — | — |
| K-BR | کنتاکتور AC با کنتاکت NC (Siemens 3RT / ABB AF / Schneider TeSys)، 400 V، 63 A | — | باز با B3-HEALTHY · SR1-O5 |

## ۴. B4 — درایورها (روی بام، RP-1)

| کارکرد | قطعه | LCSC (موجودی) | یادداشت |
|---|---|---|---|
| MCU | STM32G474RET6 | C521608 | 4 درایو BLDC: استارتر M-020، پمپ روغن، scavenge M-711، پمپ گلیکول |
| درایور گیت BLDC 48 V ×4 | **6EDL7141XUMA1** (MOTIX، 3 CSA، SPI) | C3655737 (263) | جایگزین: **STDRIVE101** (C2969847، 237) |
| MOSFET 100 V | **IPB017N10N5** (1.7 mΩ، D²PAK) | C536479 (143) | استارتر: 60 A پیک؛ پمپ‌ها: OptiMOS کوچک‌تر (BSC…N10NS5) |
| سنس جریان | CSA داخل 6EDL7141 / **TSC2011IST** | — | — |
| خروجی‌های 24 V (16 کانال) | **VNI4140KTR** ×4 (هر کدام 4 کانال، 0.7 A) + **IPS1025HTR-32** (2.5 A) برای جرقه و SSV | C2688485 (202) + C5268124 | تشخیص قطعی و اتصال کوتاه |
| شیر تناسبی (جریان کنترل‌شده) | MOSFET Infineon + شانت + TSZ122 + حلقهٔ جریان STM32 (PWM 5 kHz + dither) | — | — |
| خروجی 0–10 V / 4–20 mA (ZC-101، …) | DAC STM32 + **TSB572IST** | — | — |
| تغذیهٔ منطق | **R-78HB12-0.5** (48→12 V، ورودی تا 72 V) → R-78E5.0 → LDL1117 | — | — |
| ورودی 48 V | فیوز + TVS SMCJ58CA (ST) + P-MOSFET Infineon + محدودکنندهٔ inrush | — | — |
| CAN-FD | TJA1052IT/5Y | C92210 | — |

## ۵. B5 — HMI و دروازهٔ داده (اتاق برق)

| کارکرد | انتخاب | یادداشت |
|---|---|---|
| ماژول | **NXP i.MX 8M Plus** (4× A53، GPU، 2× GbE، **2× CAN-FD**، LVDS/DSI، NPU) روی **Toradex Verdin iMX8M Plus** (سوئیس) یا **Phytec phyCORE-i.MX 8M Plus** (آلمان)، نسخهٔ صنعتی −40…+85 °C | Linux (Torizon OS یا Yocto)؛ RTC + watchdog؛ v1 روی برد حامل **Toradex Mallow** (خریدنی) |
| برد حامل B5 | طراحی خودمان در KiCad (Verdin: SODIMM-260) یا Toradex Mallow/Dahlia برای v1 | 24 V، 2× Ethernet (OT، مدیریت)، CAN-FD (شنود باس موتور)، RS-485، M.2 NVMe |
| ذخیره‌سازی | NVMe صنعتی با PLP، **Swissbit** (سوئیس)، 256 GB | روند و رکوردها |
| نمایشگر | 10.1" IPS، 1280×800، LVDS، لمسی خازنی، optical bonding، ≥ 500 nit: **DATA MODUL easyTOUCH eTD101W3201** (259 × 177 × 18.9 mm) یا **Distec POS-PRO 10.1** (آلمان) | روی در کابینت CP-E |
| مانیتور سرویس بام | همان پنل HMI B6 (Riverdi 10.1"، §۶) با صفحه‌های موتور، یا thin client روی فیبر | سند 03 §۹ |

## ۶. B6 — کنترلر HVAC/BOP (برد خودمان، بدون PLC)

طراحی کامل در [08_b6_bop_controller.md](08_b6_bop_controller.md).

| بخش | قطعه | LCSC (موجودی) |
|---|---|---|
| برد پایه: MCU | STM32H743IIT6 | C89597 |
| برد پایه: Ethernet | ⚑ RTL8201F + Würth RJ45 | C45044 |
| برد پایه: RS-485 ایزوله ×3 (Modbus RTU برای VFDها، کنتورها، چیلرها) | ST485EBDR + STISO621TR | C81186 + C5447162 |
| برد پایه: M-Bus master (HM-1..4، HM-11..22) | ماژول M-Bus level converter (Relay GmbH / Lingg & Janke، آلمان) یا مدار گسسته با ترانزیستورهای Nexperia | — |
| برد پایه: حافظه | M95M04 (پارامترها، شمارنده‌ها) + ⚑ W25Q128 (روند محلی) | C1852765 + C97521 |
| کارت AFE (16 RTD / 8 TC / 8 AI) | STM32F373VCT6 + TSV912 + شانت Isabellenhütte | C1121903 |
| کارت DI-16 | 2× ISO1I813T | C538445 |
| کارت DO-16 | 16× Finder 34.51 + 2× ULN2003A (ST) یا 4× VNI4140K برای خروجی ترانزیستوری | C61273 / C2688485 |
| کارت AO-8 | DAC STM32G474 + TSB572 (0–10 V / 4–20 mA) | C521608 |
| اتصال کارت‌ها | باس SPI ایزوله یا CAN-FD داخلی رک (TJA1052) | C92210 |
| HMI لمسی | **Riverdi** (لهستان) STM32 Embedded Display 10.1" **RVT101HVSNWC00-B** (STM32H757XI، IPS 1280×800، PCAP، optical bonding؛ 257.96 × 168.6 × 15.5 mm، 0.52 kg؛ نسخهٔ پرنور تأیید شود) با firmware **TouchGFX** خودمان؛ RS-485 به CPU | — |

## ۷. تجهیزات میدانی (اروپایی)

| تجهیز | مشخصه | انتخاب |
|---|---|---|
| ترموکوپل | K، کلاس 1، MI Ø1.5 (ITT) / Ø3، Inconel 600، **ungrounded**، اتصال فشاری M4 | **WIKA** TC80، **Rössel**، **JUMO**، TC Direct (انگلستان) |
| RTD | PT1000 کلاس A، 3-wire، SS316 | WIKA، JUMO |
| P2 (سریع) | 0–6 bar abs، 4–20 mA، < 1 ms | **Keller** PA-23 / PA-21Y (سوئیس)، WIKA S-20 |
| سایر فشارها | 4–20 mA، ±0.25 % FS، سازگار با متان | **Danfoss** MBS 3000 / 1700، WIKA A-10، Keller |
| ΔP پایین | 0–500 / 0–1000 Pa | **Huba** 699 (سوئیس)، Siemens QBM |
| RH بعد از کویل (MT-501) | پروب **گرم‌شونده**، ±2 % RH | **E+E** EE33 (اتریش)، **Vaisala** HMP7 (فنلاند)، Rotronic HC2A (سوئیس) |
| روغن: PDT-703، PT-709، LT-707 | 0–2.5 bar ΔP؛ −50…+500 mbar؛ سطح پیوسته 4–20 mA | Keller PD-23؛ Huba 520؛ **Baumer** CleverLevel / Gems-free |
| دور N1/N2 | Hall | **Melexis US5881** (TO-92UA، جایگزین مستقیم A1120)؛ ممتاز: **Micro-Epsilon turboSPEED DZ140** (آلمان، از روی پره‌ها) |
| ارتعاش | IEPE 100 mV/g، ±50 g، تا 120 °C | **Hansford HS-100**، **IFM VSA**، Brüel & Kjær 4533 |
| شعله | UV، 24 V، خروجی رله/پالس | **Durag D-LX 100 UV** یا **Siemens QRA2 + AGQ3** (آلمان)؛ پنجرهٔ کوارتز |
| SSV1/SSV2، XV-610 | EN 161 کلاس A، pmax ≥ 6 bar، 24 VDC، < 1 s، POC | **GSR** سری D (آلمان)، **Dungs** سری فشار بالا (MV/HP؛ رنج 6 bar تأیید شود)؛ Kromschröder ساخت آلمان است ولی مالکیت آمریکایی دارد |
| شیر تناسبی و دبی‌سنج گاز | PWM 24 V / MFC حرارتی | **Bürkert** 2875 + 8746 (آلمان)؛ Endress+Hauser t-mass (سوئیس) |
| کلیدهای فشار گاز | EN 1854، 0.5–6 bar | Dungs GW (نسخهٔ فشار بالا)، GSR |
| اگزایتر جرقه | 24 VDC، ≥ 8 kV | **COFI** / **BRAHMA** (ایتالیا)، Danfoss EBI4 |
| آشکارساز گاز | متان NDIR، 4–20 mA + رله، ATEX | **Dräger** Polytron 5310 (آلمان)، **Crowcon** Xgard IQ (انگلستان) |
| کلید درها، E-stop | PL e | **Schmersal** BNS 260، **Euchner** CES، **Pilz** PSENmag؛ Schneider XB4، Siemens 3SU1، Pilz PIT es |
| SR1 | رلهٔ ایمنی قابل پیکربندی PL e | **Pilz PNOZmulti 2**: PNOZ m B0 (772100، 45 mm) + 2× PNOZ m EF 16DI (772140) + PNOZ m EF 4DI4DOR (772143)؛ Phoenix PSR-TRISAFE، Siemens 3SK2 |
| مانیتور سرعت (اختیاری) | گواهی‌دار | Pilz PNOZ s30 |
| اکچویتور دمپر | 24 V، spring return | **Belimo** NF24A-SR / AF24-SR (سوئیس) |
| فن EC | 48 VDC، 0–10 V + tach | **ebm-papst** (آلمان) |
| پمپ‌های روغن | چرخ‌دنده‌ای فشار + scavenge (BLDC 48 V)، فیلتر 10 µm با bypass، خنک‌کن OC-1 روی حلقهٔ گلیکول | پمپ: **Oberdorfer** / **Kracht** (آلمان) با موتور BLDC؛ فیلتر: **Hydac** / **Argo-Hytos** |
| استارتر | BLDC 48 V، 1.5–2 kW، **کلاچ یک‌طرفه (sprag، Ringspann / GMN آلمان)** + پینی در سوراخ عرضی Ø3 دماغه؛ چرخش ساعت‌گرد از دید ورودی؛ پشتیبان هوای فشرده M5 با XV-021 | موتور: **maxon** (سوئیس)، **Dunkermotoren** (آلمان)، **ebm-papst** |
| آتش | سند [07](07_fire_protection.md) | Siemens Sinteso، Minimax، Bosch، Hekatron |

## ۸. اینورتر هیبرید و باتری‌ها (rev 3: باتری HV ۲۰ kWh، شبکهٔ پشتیبان با zero-export)

**تصمیم کاربر:**
- باتری اصلی **HV LFP ۲۰ kWh** + باتری 48 V
- **شبکه منبع پشتیبان خودکار**، با zero-export تا مجوز DG
- هدف نهایی: صادرات
- بارهای واقعی ~5–8 kW

**معیارها:**
1. درگاه GRID + **درگاه LOAD (backup، ترجیحاً بدون وقفه)**؛ zero-export با CT یا کنتور.
2. ورودی DC (MPPT) با بازه‌ای که 720 V را در بار کامل پوشش دهد؛ حداکثر 1000 V؛ ≥ 24 kW DC.
3. باتری HV با جریان کافی برای ~12 kW در backup (trip توربین).
4. ۱۰۰ ٪ بار نامتعادل؛ پیک فاز کافی برای استارت کولر 12,000 BTU (calc §۵).
5. گواهی grid-tie: EN 50549-1، VDE-AR-N 4105، IEC 62116، IEC 61727، IEC 62109.
6. Modbus باز برای EMS؛ سرویس در منطقه.
7. **بدون محتوای آمریکایی**؛ ترجیح اروپایی.

**نتیجهٔ بررسی datasheetها (۲۰۲۶-۱۰-۲۱؛ منبع هر عدد در `cad/electrical/el_items.py` و پوشهٔ تحقیق):**

| گزینه | درگاه backup | انتقال | توان | باتری | MPPT | نتیجه |
|---|---|---|---|---|---|---|
| **Deye SUN-30K-SG01HP3-EU-BM3** (چین) | **LOAD داخلی (UPS) + GEN** | در datasheet نیامده؛ فروشنده‌ها < 4 ms (**تأیید شود**) | 30 kW، هر فاز ≤ 50 %، پیک 1.5× / 10 s | 160–800 V، **2× 50 A** | 3× 36 A، 150–850 V (بار کامل 360–850) | **انتخاب مرجع** |
| Deye SUN-25K-SG01HP3-EU-AM2 (چین) | LOAD داخلی | همان | 25 kW | 160–700 V، **1× 50 A** (با BOS-G20 فقط ~10 kW) | 2× 26 A، بار کامل 625–850 V | باتری کم‌توان |
| SMA Sunny Tripower Hybrid X 30 (آلمان) + SMA Backup | جعبهٔ خارجی | **پس از 1–600 s قطع شبکه** (پیش‌فرض 2 s) | 30 kW | 120–800 V، 50 A؛ فقط باتری SMA در 20–30 kW | 4× 32 A، 180–850 V | اروپایی، بدون وقفه نیست |
| KOSTAL PLENTICORE G3 L 20 (آلمان) + BackUp Switch | سوییچ خارجی | < 5 s دستی / < 30 s خودکار | 20 kW، 6.66 kW در هر فاز در backup | 95–820 V، **30 A** | 3 MPPT، 227–800 V | اروپایی؛ استارت کولر در backup بیش از پیک |
| Fronius Symo GEN24 10 Plus (اتریش) | Backup Controller | ~10 s | **10 kW** | 22 A | 2 MPPT | کوچک |
| SMA STP Smart Energy 10 (آلمان) | داخلی | 30 ms تا 10 s | **10 kW** | 30 A | 2 MPPT | کوچک |

**انتخاب: Deye SUN-30K-SG01HP3-EU-BM3 + Deye BOS-G20.**
- تنها ترکیب این اندازه که **درگاه LOAD بدون وقفه**، **~20 kW از باتری ۲۰ kWh**، و MPPT مناسب B3 را با هم دارد.
- **چینی است، نه آمریکایی** (مجاز طبق docs/06 §۵)، و در ایران رایج است و سرویس دارد.
- اگر کاربر اروپایی بودن را بر انتقال بدون وقفه ترجیح دهد، گزینهٔ اروپایی **SMA Hybrid X 30 + SMA Home Storage** است، با پذیرش قطعی ~2 s در قطع شبکه (سؤال باز 00 §۱۰-۱).

| قلم | انتخاب | ابعاد و وزن (datasheet) |
|---|---|---|
| **HI-1** | Deye SUN-30K-SG01HP3-EU-BM3 | 527 × 894 × 294 mm، 80 kg، IP65، دیواری |
| **BAT-1** | Deye **BOS-G20**: 4× BOS-GM5.1 (5.12 kWh، 51.2 V، 100 Ah؛ 440 × 133 × 570 mm، 45 kg) + جعبهٔ کنترل HVB750V/100A-EU (440 × 150 × 570، 19 kg) در رک 3U-LRACK | 530 × 1629 × 602 mm، 240 kg؛ 20.48 kWh، 204.8 V (166–234 V)، 100 A اسمی / 125 A برای 2 min؛ IEC 62619، VDE 2510-50، UN38.3 |
| CT / کنتور zero-export | کنتور سه‌فاز تأییدشدهٔ Deye (یا CTهای همراه) در ورودی شبکه | — |
| **ATS-1** | **Socomec ATyS p M 4P 63 A** (9384 4006، فرانسه) | 324 × 245 mm (عمق تأیید شود)، 4.3 kg |
| **BAT-2** (باس 48 V) | **Pylontech US5000** (48 V، 100 Ah، 4.8 kWh، 19") در جعبهٔ فولادی با فیوز Class-T؛ جایگزین اروپایی: Victron Lithium NG 51.2 V 100 Ah (648 × 235 × 162 mm، 37 kg) | 442 × 162 × 420 mm، 40 kg |
| شارژر 48 V | 2× **Victron Smart IP43 Charger 48/13** (هلند، 13 A، دیواری) + ORing | 249 × 180 × 116 mm |
| DC-DC 48→24 V | **PULS CD10.242** (آلمان، 10 A، DIN) | 42 × 124 × 117 mm |

> **دو نکته که باید با Deye یا فروشنده تأیید شود:**
> - **زمان انتقال UPS درگاه LOAD.** datasheet و دفترچه عددی ندارند.
> - **موازی‌کردن دو ورودی باتری روی یک رشتهٔ BOS-G20.** این برای رسیدن به ~20 kW از باتری لازم است.
>
> **اگر موازی‌کردن مجاز نباشد:** BOS-G با 8 ماژول (409.6 V، 41 kWh) لازم می‌شود، یا حذف بار در backup به ~10 kW.

## ۹. سایر تجهیزات قدرت

| تجهیز | انتخاب اروپایی |
|---|---|
| DCD-1 (ایزولاتور DC 1000 V) | **ABB OTDC**، **Santon** (هلند) |
| SPD AC، DC و داده | **DEHN**، **Phoenix Contact**، **OBO Bettermann** (آلمان)، **Citel** (فرانسه) |
| فیوز gPV، NH و Class-T 48 V | **Mersen** (فرانسه)، **SIBA** (آلمان) |
| مقاومت‌های ترمز R_BR1 / R_BR2 (RB-1) | **Danotherm** (دانمارک)، **Frizlen** (آلمان)، **Cressall** (انگلستان)؛ مبنای ابعاد: Schneider VW3A7790 (3× 6.7 Ω، 20 kW، IP23، 1060 × 565 × 540 mm). مدل کاتالوگی 18 Ω با ≥ 400 kJ یافت نشد، پس ساخت سفارشی با تأمین‌کننده |
| کنتورها JT-901..920 | **Carlo Gavazzi** EM24 (سه‌فاز، CT) / EM340 / EM111 (تک‌فاز)، **Janitza** UMG 96-PA (کلاس 0.5S)، ABB B23/B24؛ همه Modbus RTU |
| VFD پمپ‌ها | **Danfoss** FC 51 / FC 102، **ABB** ACS580، **Siemens** G120X |
| soft starter کمپرسور تک‌فاز | **Carlo Gavazzi RSHR / RSBS** (کاهش LRA حدود 60 %) |
| رلهٔ حفاظت رابط (grid-tie، اگر لازم شد) | **Ziehl UFR1001E**، **Bender LINETRAXX VMD460-NA** (آلمان) |
| مانیتور عایق (اختیاری، DC و IT) | **Bender** ISOMETER (آلمان) |
| سوییچ شبکه | **Westermo Lynx L205-S1** (سوئد)، **Phoenix FL SWITCH 2105** (آلمان)؛ فیبر OM3 زره‌دار |
| روتر | **Teltonika** RUTX11 (لیتوانی): WAN اینترنت ثابت + LTE پشتیبان، SMS، WireGuard |
| تابلو و یراق | **Rittal**، **Phoenix**، **Weidmüller**، **WAGO** |
| کلید و حفاظت | **ABB**، **Siemens**، **Schneider**، **Hager** |
| کابل | **Lapp**، **Helukabel** (آلمان)، **Prysmian** (ایتالیا)؛ آتش: FE180 / PH120 (سند 05) |

## ۱۰. پایش از راه دور (اینترنت ثابت با IP ثابت؛ هشدار Telegram و SMS)

```
 B1 ECU ─Modbus TCP / UDP 100 Hz─┐
 B6-R/E/C ─Modbus TCP────────────┼─ B5 (i.MX 8M Plus) ─┬─ HMI محلی (Qt / Chromium kiosk)
 HI-1 Deye ─Modbus RTU (B1) ───────┘                     ├─ VictoriaMetrics (روند 1 s)، PostgreSQL (آلارم ISA-18.2، رویداد، شمارنده‌ها)، Grafana
                                                       ├─ gr180-notify: قواعد اولویت → Telegram + SMS
                                                       └─ Mosquitto bridge (TLS، store-and-forward) → VPS (اختیاری)
 روتر Teltonika RUTX11:
   WAN1 = اینترنت ثابت با IP ثابت، WAN2 = LTE (failover)
   ├─ سرور WireGuard روی IP ثابت (تنها پورت باز: UDP 51820)؛ کلید جدا برای هر کاربر
   ├─ مودم LTE: SMS مستقیم، مستقل از اینترنت (API محلی روتر از B5)
   └─ VLANها: OT (B1، B5، B6، logger اینورتر، FCP gateway)، مدیریت، IT؛ فایروال بین VLANها
 VPS خارج از کشور (اختیاری ولی برای Telegram لازم): رلهٔ Telegram Bot API + آینهٔ داده + پشتیبان روزانه
```

- **IP ثابت:** مهندسین مستقیم به WireGuard سایت وصل می‌شوند و برای دسترسی VPS لازم نیست.
  - پورتال ابری سازندهٔ اینورتر (Deye SolarmanPV) اختیاری است و به اینترنت خارجی وابسته است. **مبنای پایش، B5 محلی است.** logger وای‌فای اینورتر در VLAN جدا یا غیرفعال.
- **Telegram:**
  - Bot API از ایران فیلتر است. پس B5 پیام را با MQTT روی TLS به **VPS خارج از کشور** می‌فرستد و VPS آن را به `api.telegram.org` می‌دهد.
  - اگر VPS در دسترس نباشد، پیام در صف می‌ماند و SMS جای آن را می‌گیرد.
- **SMS از دو مسیر مستقل:**
  1. **مودم LTE روتر** با سیم‌کارت محلی، بدون وابستگی به اینترنت (مسیر اصلی برای P1/P2)
  2. سرویس پیامک داخلی روی اینترنت (Kavenegar / Ghasedak) به‌عنوان پشتیبان
- **برای P1، SMS مستقیماً هم از FCP آتش‌نشانی** (شمارنده/دیالر GSM گواهی‌دار EN 54-21) ارسال می‌شود، مستقل از B5.
- **اولویت‌ها و مسیرها** (جزئیات در 06 §۱۱):

| اولویت | نمونه | Telegram | SMS | تماس صوتی | تکرار تا تأیید |
|---|---|---|---|---|---|
| P1 | trip ایمنی، آتش، نشت گاز، خطای ESD | ✓ | ✓ (همهٔ کشیک‌ها) | ✓ (روتر، اختیاری) | هر 5 min |
| P2 | trip فرایندی، فاز نزدیک حد، SOC < 20 %، قطع شبکه | ✓ | ✓ (کشیک اول) | — | هر 15 min |
| P3 | آلارم، نگهداری لازم | ✓ | — | — | — |
| P4 | گزارش روزانه (kWh، ساعت کار، شمارندهٔ عمر، COP) | ✓ (08:00) | — | — | — |

- **امنیت:**
  - فرمان‌های راه دور فقط در حالت REMOTE؛ trip‌های L/LO فقط محلی ریست می‌شوند (03 §۷)
  - 2FA روی وب HMI، audit log
  - سیستم‌عامل B5 فقط‌خواندنی با به‌روزرسانی امضاشده
  - مرجع: IEC 62443-3-3 SL2
- **هیچ تابع ایمنی به B5، شبکه یا اینترنت وابسته نیست.**

## ۱۱. اعلام و اطفای حریق

جزئیات در [07_fire_protection.md](07_fire_protection.md). خلاصه:

| بخش | انتخاب |
|---|---|
| پنل کنترل اطفا (FCP) | گواهی‌دار EN 54-2/4 و **EN 12094-1**: **Siemens Sinteso XC10** (مرجع؛ 505 × 375 × 125 mm، 6.5 kg) یا FC2020 + ماژول اطفا، **Minimax FMZ 5000**، **Bosch FPA-1000**، **Hekatron Integral** (آلمان) |
| دتکتور حرارتی | EN 54-5 کلاس A2R/BS (ROR + ثابت)؛ نسخهٔ دمای بالا کلاس CS/DS در جعبهٔ موتور |
| دتکتور شعله | IR3 / UV-IR، EN 54-10 (جعبهٔ موتور، روی بام) |
| دتکتور دود | نوری EN 54-7 (اتاق برق، اتاق باتری)؛ اختیاری: مکشی EN 54-20 (Wagner TITANUS، آلمان) |
| گاز باتری | آشکارساز **H₂** (Dräger Polytron 8100 EC + DrägerSensor H2، 150 × 280 × 130 mm) + CO؛ Crowcon Xgard |
| شستی‌ها | دستی آژیر (EN 54-11)، **شستی رهاسازی زرد**، **شستی abort آبی**، **کلید lock-off** |
| آژیر و فلاشر | EN 54-3 / EN 54-23 (داخل و خارج هر ناحیه) |
| شیر رهاسازی | سولنوئید 24 V پایش‌شده روی مخزن (طراحی HVAC)، کلید فشار تخلیه، کلید وضعیت شیر دستی |
| دیالر | GSM / IP دیالر EN 54-21 |
