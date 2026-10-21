# GR180-CCHP — انتخاب قطعات (بردها، تجهیزات میدانی، اینورتر، باتری، پایش از راه دور)

تاریخ: ۲۰۲۶-۱۰-۲۱ · سند اصلی: [`00_electrical_control_architecture.md`](00_electrical_control_architecture.md)

**دربارهٔ شماره‌های LCSC:**
- همهٔ شماره‌های `Cxxxx` این سند در **۲۰۲۶-۱۰-۲۱ از API قطعات JLCPCB** استعلام شدند. موجودی (stock) همان لحظه کنارشان آمده و تغییر می‌کند.
- همه از نوع «extended» هستند، به‌جز W25Q128 و ULN2003 که «basic» هستند. extended یعنی هزینهٔ setup در مونتاژ JLC.
- ردیف‌هایی که LCSC ندارد با «—» و منبع پیشنهادی مشخص شده‌اند.
- **مراقب برندهای مشابه با پیشوند متفاوت باشید** (مثلاً `GC3M…`، `MX74700T`، `-VB`، `-HXY`). این‌ها جایگزین سازگار یا نامشخص‌اند و نباید به‌جای قطعهٔ اصلی در مسیرهای قدرت و ایمنی خریده شوند.

> ⚠️ **تأمین و محدودیت صادرات:**
> - بخشی از قطعات منشأ آمریکایی دارند: TI، ADI/Maxim، Microchip، Wolfspeed، onsemi، Vishay، Allegro.
> - صادرات این قطعات به ایران مشمول تحریم‌ها و مقررات صادرات آمریکاست و مسیر خرید ممکن است ریسک حقوقی یا قطع ناگهانی تأمین داشته باشد.
> - برای هر ردیف حیاتی یک **جایگزین غیرآمریکایی** آمده است: ST (اروپا)، Infineon (آلمان)، Chipanalog / Novosense / GigaDevice (چین). طراحی PCB طوری انجام شود که جایگزین با حداقل تغییر (footprint سازگار یا پد دوگانه) نصب شود.
> - تصمیم مسیر تأمین با کاربر است (سؤال باز).

## ۱. B1 — ECU (اتاق برق)

| کارکرد | قطعه | سازنده | LCSC (موجودی) | جایگزین | یادداشت |
|---|---|---|---|---|---|
| MCU اصلی | **STM32H743IIT6** (480 MHz، 2× FDCAN، Ethernet MAC، **LQFP-176، 140 GPIO**) | ST | C89597 (548) | STM32H743VIT6 C114409 (LQFP-100) **کافی نیست**: 24 DI + 12 رله + RMII + QSPI + 3 CAN + 2 UART + 6 ورودی سرعت از 82 GPIO بیشتر است؛ GigaDevice GD32H7 | ماشین حالت، گاورنر، life counter |
| MCU ایمنی (SMCU) | **dsPIC33CK256MP506-I/PT** | Microchip | C634006 (22) | **STM32G431RBT6** C431633 (2552) | تنوع معماری؛ موجودی کم، پس جایگزین ST روی همان برد قابل‌نصب طراحی شود (دو footprint) |
| watchdog خارجی | STWD100NYWY3F | ST | C46043 (19284) | TPS3431 | پنجره‌ای؛ رلهٔ ECU RUN PERMIT |
| FRAM شمارندهٔ عمر | **FM25V10-GTR** (1 Mbit SPI) ×2 (H7 + SMCU) | Infineon/Cypress | C44173 (5527) | MB85RS4MT C42742723 | 10¹⁴ سیکل نوشتن |
| فلش QSPI | W25Q128JVSIQ | Winbond | **C97521 (basic)** | — | event recorder |
| PHY اترنت | LAN8742A-CZ-TR (RMII) | Microchip | C621424 (8773) | KSZ8081RNACA-TR C100017؛ YT8512 (Motorcomm) | — |
| RJ45 + مگنتیک | HR911105A | HanRun | C12074 (54266) | — | — |
| CAN-FD ایزوله | **ISO1042BQDWVRQ1** + B0505S-1WR3 ×3 | TI + Mornsun | C2672259 (223) + C512048 (5926) | **ADM3055EBRIZ-RL** C658105 (isoPower)؛ Chipanalog CA-IS3062 / Novosense NSi1042 | 3 کانال: #1 موتور، #2 BOP (B6-R/B6-E طبق docs/hvac)، #3 BMS |
| کنترلر CAN-FD سوم | MCP2518FDT-E/SL (SPI) | Microchip | C626758 (22977) | — | FDCAN داخلی H7 فقط دو کانال دارد |
| حفاظت CAN | PESD2CANFD24V-TR + چوک CM ACT45B-510-2P | Nexperia + TDK | C552486 + C76584 | — | — |
| RS-485 ایزوله | **ADM2587EBRWZ-REEL7** (isoPower) ×2 | ADI | C12081 (6942) | **CA-IS2092W** C5121950 (6470) | Modbus اینورتر، کنتورها، VFDها |
| ESD RS-485 | SM712 | Semtech/… | C908219 | SM712-02HTG C172881 | — |
| ورودی‌های سرعت SPD-IN | AM26LV32EIDR (RS-422 برای N1-A) + ورودی open-collector با pull-up 24 V و اشمیت‌تریگر (N1-B، N2-B، UV) در ناحیهٔ ایزوله + ISO7741DWR؛ هر سیگنال به دو گیرندهٔ جدا (H7 و SMCU) | TI | C527448 (42602) + C571196 (8437) | ISO1410DWR C2671566؛ CA-IS3082WX C970942 | تغذیهٔ سنسورهای N1-B، N2-B و UV از ناحیهٔ SMCU |
| ورودی دیجیتال 24 V | ISO1212DBQR ×12 (24 کانال) | TI | C2859667 (4099) | اپتوکوپلر TLP291-4 C60900 | IEC 61131-2 نوع 1/3 |
| رله‌های عمومی | G5Q-14 DC24 ×12 + ULN2003ADR | Omron + TI | C397242 (11740) + C7512 (basic) | HF46F/24-HS1T C5274023 | load shedding، اینورتر، BMS-wake |
| رله‌های force-guided | G7SA-3A1B DC24 ×4 | Omron | C968857 (50) | — | SMCU PERMIT A/B، ECU RUN PERMIT |
| حفاظت ورودی 24 V | SMBJ33A + LM74700-Q1 (ideal diode) + eFuse TPS16630PWPR | TI | — / C22468156 (MX74700T، سازگار) / C1849461 (544) | — | معکوس، اضافه‌جریان |
| مبدل 24→5 V | TPS54360BDDAR | TI | C524806 (54998) | LMR38010 C5219308 | — |
| LDO 3.3 V | TLV75533PDBVR | TI | C404027 (115623) | — | — |
| مرجع و LDO کم‌نویز | REF5025AIDR، TPS7A4701RGWR | TI | C11341، C90084 | — | پایش 48 V/24 V |
| USB سرویس ایزوله | ADUM4160BRWZ-RL + USBLC6-2SC6 | ADI + ST | C57791 + C7519 | — | — |
| ترمینال‌ها | Phoenix MSTBA 2,5/..-G-5,08 (هدر) + MSTB 2,5/..-ST-5,08 (پلاگ)؛ سیگنال: MC 1,5/..-3,81 | Phoenix | C90074 + C90073؛ C480511 | — | همه قابل‌جداشدن، کددار |
| کریستال | ABM8-25.000MHZ-B2-T | Abracon | C596899 | — | — |

## ۲. B2 — I/O سنسورها (روی بام، RP-1)

| کارکرد | قطعه | LCSC (موجودی) | جایگزین | یادداشت |
|---|---|---|---|---|
| MCU | STM32H743VIT6 (FFT ارتعاش و رأی‌گیری) | C114409 | STM32H723ZGT6 C730146 | هم‌سان با B1 برای قطعهٔ یدکی مشترک |
| ترموکوپل | **MAX31856MUD+T** ×12 | C2653162 (7580) | ADC ΔΣ 24 بیتی + CJC (PT1000) از سازندهٔ غیرآمریکایی | تشخیص قطعی/اتصال کوتاه TC؛ **ناحیهٔ آنالوگ ایزوله** (ISO7741 + B0505S) |
| RTD | **MAX31865ATP+T** ×12 | C118474 (14540) | ADS124S08 با منبع جریان | 3-wire، PT1000 |
| 4–20 mA | **ADS124S08IPBSR** ×2 (24 کانال) + شانت 50 Ω 0.1 % + REF5025 | C2870171 (1531) + C11341 | AD4111BCPZ C649166 (ورودی ±10 V/جریان یکپارچه) | تغذیهٔ حلقه با PTC + SMAJ33CA (C115251) |
| ارتعاش IEPE و آنالوگ سریع | **ADS131M04IPWR** ×2 (8 کانال هم‌زمان، تا 32 kS/s) + OPA2188AIDR | C2862562 (1579) + C17271 | — | VIB1–4، FAI1–4 (P2، مانیفولد) |
| منبع جریان IEPE 4 mA | LT3092EST#TRPBF | C580042 (1569) | — | تطابق 24 V |
| خروجی RS-422 سرعت N1-A به B1 | AM26LV31EIDR | C527446 (3120) | — | ورودی Hall با اشمیت‌تریگر؛ N1-B، N2-B و UV از B2 عبور نمی‌کنند |
| ورودی دیجیتال | ISO1212DBQR ×16 (32 کانال) | C2859667 | — | — |
| CAN-FD | ISO1042BQDWVRQ1 + B0505S-1WR3 | C2672259 + C512048 | ADM3055E | — |
| تغذیه | 24 V از DC-DC بام → TPS54360 → TLV75533 | C524806، C404027 | — | — |

## ۳. B3 — یکسوساز فعال SiC (PEB روی بام) و B3b

| کارکرد | قطعه | LCSC (موجودی) | جایگزین | یادداشت |
|---|---|---|---|---|
| کنترلر | **TMS320F28379DPTPT** (2× C28x + 2× CLA، SDFM، CMPSS) | C1339763 (108) | **STM32G474RET6** C521608 (HRTIM)؛ TMS320F28377S C1346020 | FOC در 40 kHz، PV emulation، Riso |
| SiC MOSFET 1200 V | **IMZA120R020M1HXKSA1** (CoolSiC 20 mΩ، TO-247-4) ×6 + 1 (چاپر) | C7207676 (68) | **C3M0021120K** C5713521 (185)؛ ماژول six-pack EasyPACK 2B CoolSiC (Infineon) از توزیع‌کننده | تلفات تقریبی ~48 W برای هر سوییچ در 30 kW، 40 kHz؛ راندمان یکسوساز ~99 % |
| دیود چاپر (SiC Schottky 1200 V/20 A) | IDW20G120C5B | C49450342 (60، نسخهٔ S-) | GC4D20120D C7435099 (برند سازگار) | freewheel سلف مقاومت |
| گیت‌درایور ایزوله | **UCC21750QDWRQ1** (DESAT، Miller clamp، 10 A) ×7 | C2868955 (1131) | Infineon 1ED3124MU12H / 1EDI3031AS؛ Novosense NSi6801 | — |
| تغذیهٔ ایزولهٔ گیت +15/−5 V | **MGJ2D241505SC** ×7 | C5369917 (90) | Mornsun QA01C C7500960 | 5.2 kV ایزولاسیون |
| جریان فاز و DC | شانت 1 mΩ (WSLP3921L1000FEA) + **AMC3306M25DWER** (ΔΣ با DC-DC داخلی) ×4 | C6029738 (4) + C2867907 (300) | AMC1306M25 C471874 + B0505S؛ Novosense NSi1306 | SDFM؛ OCP سریع با CMPSS |
| ولتاژ باس، V+/PE، V−/PE | **AMC3330DWER** ×3 | C2999368 (3923) | AMC3301DWER C2869778 | پایش عایق Riso |
| OVP مستقل (900 V) | تقسیم‌کنندهٔ HV + مقایسه‌گر + ISO7721DR → disable گیت + چاپر full-on | C366164 | — | مستقل از C2000 |
| CAN-FD | ISO1042 + B0505S | — | — | — |
| خازن DC-link | فیلم MKP DC-link 1100 V، مجموع ≥ 400 µF، ریپل ≥ 30 A rms | — (TDK B32776/B32778، KEMET C4AQ، Vishay MKP1848C از توزیع‌کننده) | — | عمر طولانی، بدون الکترولیت |
| کنتاکتور DC اصلی | ≥ 1000 V DC، 50 A، دوطرفه، کنتاکت کمکی | — (Schaltbau C195، Sensata/GIGAVAC سری HX، یا مدل 1000 V هونگ‌فا؛ **HFE18V-40/750 کافی نیست**) | — | K-DC+ و K-DC− |
| پیش‌شارژ | رلهٔ DC کوچک 1000 V + 2× 50 Ω 50 W سیمی | — | — | — |
| **B3b** پل دیودی | VS-36MT120 (1200 V، 35 A) | C506418 (40) | SEMIKRON SKD 30/12 | مستقل از B3 |
| B3b سوییچ | **IKW40N120H3** (IGBT 1200 V/40 A) + UCC5350MCDR | C94637 (3595) + C2872371 | — | — |
| B3b منطق و تغذیه | فلای‌بک HV خودتغذیه (کلاس VIPer26K / InnoSwitch3 1000 V) + مقایسه‌گر آنالوگ | — | — | **بدون نرم‌افزار** |
| K-BR | کنتاکتور قدرت AC با کنتاکت NC اصلی (یا NO + منطق معکوس با فنر)، 400 V، 63 A | — | — | باز با B3 HEALTHY · SR1-O5 |

## ۴. B4 — درایورها (روی بام، RP-1)

| کارکرد | قطعه | LCSC (موجودی) | جایگزین | یادداشت |
|---|---|---|---|---|
| MCU | **STM32G474RET6** (HRTIM + 3 تایمر پیشرفته) | C521608 (54) | 2× STM32G431RBT6 C431633 | 4 درایو BLDC |
| درایور گیت BLDC 48 V | **DRV8353RSRGZR** (100 V، 3 CSA، SPI) ×4 | C506246 (900) | — | استارتر، پمپ روغن، خنک‌کن، scavenge |
| MOSFET 100 V | **CSD19536KTT** (2.0 mΩ، D²PAK) ×24 | C2687963 (332) | Infineon IPT015N10N5 (TOLL) | استارتر 60 A پیک |
| سنس جریان | INA240A2PWR | C129949 (9176) | — | — |
| خروجی‌های 24 V (شیر، جرقه، چراغ) | **TPS27S100BPWPR** (high-side با سنس جریان) ×16 | C2680365 (626) | TPS1H100BQPWPRQ1 C475505 | تشخیص قطعی و اتصال کوتاه |
| درایور جریان شیر تناسبی | **DRV8876PWPR** (با IPROPI) ×4 | C575551 (16218) | — | PWM + dither |
| خروجی 0–10 V | AD5422BREZ-REEL ×4 | C192062 (3850) | DAC داخلی STM32 + OPA2188 | دمپر، کویل ورودی |
| ورودی 48 V | LM5069MM-2/NOPB (hot-swap 80 V) + SMCJ58CA | C111822 (7815) + C151898 | TPS16630 (60 V، ناکافی برای 48 V با گذرا) | — |
| تغذیهٔ منطق | LM5013DDAR (100 V → 12 V) → TPS54360 → TLV75533 | C5383001 (14794) | LM5164DDAR C477928 | — |
| CAN-FD | ISO1042 + B0505S | — | — | — |

## ۵. B5 — HMI (اتاق برق)

| کارکرد | انتخاب | یادداشت |
|---|---|---|
| ماژول | **Raspberry Pi CM5**: 8 GB RAM، 32 GB eMMC، **بدون Wi-Fi** (امنیت؛ مدل دقیق مثل CM5008032 هنگام سفارش بررسی شود) | RTC و watchdog داخلی دارد |
| کانکتور | 2× Hirose DF40C-100DS-0.4V(51) — **C597931 (30822)** | — |
| ذخیره‌سازی | M.2 NVMe صنعتی 256 GB با power-loss protection | پایگاه دادهٔ روند و رکوردها |
| CAN-FD | MCP2518FDT-E/SL **C626758 (22977)** + ISO1042 | شنود مستقیم باس موتور (فقط خواندن) |
| RS-485 | ADM2587E | رزرو |
| نمایشگر | 10.1" IPS 1280×800، لمسی خازنی، optical bonding، ≥ 500 nit، DSI یا HDMI | روی در کابینت ECU |
| مانیتور سرویس بام | پنل 10" IP65، ≥ 1000 nit، PoE، به‌صورت thin client (Chromium kiosk) روی فیبر | سند 03 §۹ |
| **جایگزین خریدنی برای v1** | پنل HMI صنعتی مبتنی بر Compute Module با CAN و RS-485 و جلوی IP65 (کلاس Seeed reTerminal DM) | زمان توسعه را کم می‌کند؛ B5 سفارشی در نسخهٔ بعد |

## ۶. تجهیزات میدانی

| تجهیز | مشخصه | گزینه‌ها |
|---|---|---|
| ترموکوپل‌ها | K، کلاس 1، MI Ø1.5 (ITT) / Ø3، غلاف Inconel 600، **ungrounded**، اتصال فشاری (M4 برای EGT طبق v11) | Omega، TC Ltd، Watlow، یا سازندهٔ داخلی با گواهی کالیبراسیون |
| RTD | PT1000 کلاس A، 3-wire، غلاف SS316 | — |
| P2 (سریع) | 0–6 bar abs، 4–20 mA، پاسخ < 1 ms، دمای فرایند تا 150 °C با sense line | Keller PA-23 / PA-21Y، WIKA S-20 |
| سایر فشارها | 4–20 mA، ±0.25 % FS، سازگار با متان برای مسیر گاز | Danfoss MBS 3000 / MBS 1700، WIKA A-10، Keller PA-21Y |
| ΔP پایین (فیلتر، bellmouth) | 0–1000 Pa / 0–25 mbar | Huba 699، Dwyer 616KD، Siemens QBM |
| سرعت N1 | Allegro A1120 (طرح v11) ×2 | **گزینهٔ ممتاز:** Micro-Epsilon turboSPEED DZ140 (جریان گردابی از روی پره‌ها، تا 400k rpm، بدون آهنربا) |
| سرعت N2-B | Hall + آهنربا یا هدف ۲ دندانه روی سر سرد شفت PMG | Micro-Epsilon DZ140 روی پره‌های FPT |
| ارتعاش | IEPE 100 mV/g، ±50 g، 2 Hz–10 kHz، تا 120 °C (نسخهٔ دمای بالا در صورت نیاز) | CTC AC102، Wilcoxon 786A، Hansford HS-100، PCB 603C01 |
| شعله | UVTRON Hamamatsu R2868 + درایور C10807 (12–24 V) + پنجرهٔ کوارتز | جایگزین: میلهٔ یونیزاسیون (عمر کم در لاینر) |
| SSV1/SSV2 | **EN 161 کلاس A، pmax ≥ 6 bar**، DN15، 24 VDC، بسته‌شدن < 1 s، POC | Kromschröder (سری VG با pmax 6 bar)، GSR سری D، **Dungs رایج فقط 500 mbar است، مناسب نیست** |
| XV-610 (رایزر) | مثل SSV، با reset دستی (اختیاری) | — |
| شیر تناسبی | PWM، 24 V، Kv کوچک، سازگار با 6 bar | Bürkert 2875 (+ کنترلر)، **جایگزین یکپارچه: MFC حرارتی** (Bürkert 8746، Alicat MCR-500SLPM) |
| دبی‌سنج گاز | thermal MFM 0–20 Nm³/h، 4–20 mA + Modbus | Bürkert 8746، Alicat، Endress+Hauser t-mass |
| کلیدهای فشار گاز | EN 1854، 0.5–6 bar | Kromschröder DG، Honeywell C6097 (بررسی رنج) |
| اگزایتر جرقه | 24 VDC، ≥ 8 kV، 50–200 جرقه/s، شیلددار | ترانس جرقهٔ مشعل 24 VDC (Danfoss، COFI، BRAHMA) |
| آشکارساز گاز | متان NDIR، 4–20 mA + دو رله، ATEX/IECEx | Dräger Polytron 5310، Honeywell Sensepoint XCD، Crowcon Xgard IQ، MSA Ultima X |
| کلید درها | مغناطیسی کدشده PL e، 2 کانال | Schmersal BNS 260، Pilz PSENmag، Euchner CES |
| E-stop | IEC 60947-5-5، 2 NC | Schneider XB4، Siemens 3SU1، Pilz PIT es |
| SR1 | رلهٔ ایمنی قابل پیکربندی PL e | Pilz PNOZmulti 2، Phoenix PSR-TRISAFE، Siemens 3SK2 |
| مانیتور سرعت (اختیاری) | گواهی‌دار، ≥ 2.5 kHz | کلاس Pilz PNOZ s30 (بررسی حد فرکانس) |
| دتکتور آتش | حرارتی 90 °C + rate-of-rise | — |
| اکچویتور دمپر | 24 V، 0–10 V، spring return، بدنهٔ دمپر SS برای 300 °C | Belimo NF24A-SR / AF24-SR |
| فن جعبه | EC 48 VDC، 0–10 V + tach | ebm-papst (سری 48 VDC) |
| پمپ‌ها | چرخ‌دنده‌ای روغن + BLDC 48 V؛ گردشی خنک‌کن 48 V | طبق طراحی سیستم روغن |

## ۷. اینورتر هیبرید — معیارها و کاندیداها

**معیارهای اجباری:**
1. سه‌فاز 400/230 V، **≥ 30 kW پیوسته**، کار **off-grid با black start از باتری**. حالت on-grid بعداً با همان دستگاه (گواهی EN 50549 / IEC 62116).
2. **درگاه PV:**
   - Vmax ≥ 1000 V، رنج MPPT شامل 700–800 V
   - ≥ 2 MPPT با ≥ 36 A
   - امکان موازی‌کردن ورودی‌ها
   - «PV start delay» قابل تنظیم و کوتاه
   - توانایی curtail در جزیره
3. **درگاه باتری HV:** 150/160–800 V، ≥ 2× 50 A، پروتکل BMS باتری انتخابی در لیست سازگاری، **battery activation / wake از PV**.
4. **۱۰۰ ٪ بار نامتعادل** در هر فاز. surge ≥ 1.5× برای ≥ 5 s. THD ولتاژ < 3 % با بار غیرخطی.
5. **Modbus RTU/TCP با نقشهٔ رجیستر منتشرشده:** خواندن توان‌ها، SOC و خطاها؛ نوشتن on/off و حدها. کنتاکت remote on/off.
6. **امکان موازی** (اینورتر دوم برای 30 kW آینده یا افزونگی).
7. رلهٔ N-PE داخلی برای جزیره، یا راهنمای اجرای K-NPE.
8. IP65، کار تا 45 °C بدون derate شدید. **خدمات پس از فروش و قطعه در ایران.**

| کاندیدا | دادهٔ کلیدی (طبق datasheet و فروشنده‌ها؛ **باید با datasheet رسمی منطقه تأیید شود**) | نظر |
|---|---|---|
| **Deye SUN-30K-SG01HP3-EU-BM3** | باتری 160–800 V با 2 ورودی (50+50 A)؛ PV حداکثر 1000 V، MPPT 150–850 V، 3 MPPT (~36 A هر کدام طبق فروشنده‌ها)؛ PV حداکثر 39 kW؛ **۱۰۰ ٪ نامتعادل**؛ موازی تا ۱۰ دستگاه | **اولویت ۱:** در ایران رایج است و سرویس دارد |
| **Solis S6-EH3P30K-H** | باتری 150–800 V، 2× 70 A؛ MPPT 150–850 V، 3 MPPT × 40 A؛ backup peak 1.6× برای 2 s | اولویت ۲؛ surge کوتاه‌تر است |
| سایر (Sungrow، GoodWe، Growatt سری HV سه‌فاز) | با همین معیارها ارزیابی شوند | — |

منابع داده: [Deye 30–60K HP3 datasheet (US variant)](https://www.deyeinverter.com/deyeinverter/2026/07/10/rand/3076/%E3%80%90b%E3%80%91datasheet_sun-30-60k-sg01hp3-us-bm4-277v_20260710_en.pdf)، [Deye HP3 EU family page](https://deye.com/ja/?p=7455)، [Solis S6-EH3P(30-50)K-H datasheet](https://www.solisinverters.com/uploads/file/Solis_datasheet_S6-EH3P%2829%2C9-50%29K-H_Global_V1%2C8_2024_04.pdf).

## ۸. باتری HV — معیارها و کاندیداها

- **ظرفیت ≥ 20 kWh اسمی**، با توان پیوسته ≥ 20 kW (1C) و پیک ≥ 30 kW برای 60 s (سند 01 §۷). کمتر از سند 03 (۱۰–۱۵ kWh) **کافی نیست**؛ سؤال باز برای کاربر.
- شیمی LFP منشوری، ≥ 6000 سیکل در 80 % DoD، دمای کار 0–45 °C، گواهی IEC 62619 / UN38.3.
- BMS با تعادل‌سازی (balancing)، **پورت دوم CAN/RS-485** برای پایش B1، wake از راه دور (کنتاکت خشک)، و در لیست سازگاری اینورتر انتخابی.
- ولتاژ اسمی در رنج باتری اینورتر (معمولاً 200–500 V).
- **کاندیداها:**
  - Deye BOS-G (HV، ماژول 5.12 kWh / 100 Ah؛ ۴ ماژول ≈ 20.5 kWh)
  - Pylontech Force H3
  - BYD Battery-Box Premium HVM (۶–۸ ماژول)
- انتخاب نهایی پس از انتخاب اینورتر انجام شود (لیست سازگاری).

**باتری 48 V (باس اضطراری):**
- LFP 48 V، 100 Ah، رکی، با BMS (CAN/RS-485). کاندیداها: Deye SE-G5.1 Pro، Pylontech US5000، Dyness.
- شارژرها: 2× Mean Well RSP-1000-48 (تنظیم 54.0 V، current sharing) یا NPB-1700-48.
- مبدل‌های DC-DC (رنج ورودی 33.6–67.2 V را بررسی کنید): Mean Well DDR-240C-24 در ER و DDR-480C-24 روی بام.

## ۹. سایر تجهیزات قدرت

| تجهیز | مشخصه | گزینه |
|---|---|---|
| DCD-1 | ایزولاتور DC-PV2، 1000 V، 50 A، دوپل، IP66، قفل‌شو | ABB OTDC، Santon، Suntree |
| SPD DC | Type 1+2 (بام) / Type 2 (ER)، Ucpv ≥ 1000 V | Phoenix VAL-MS…DC-PV، DEHN DEHNcombo / DEHNguard YPV |
| SPD AC | Type 1+2 (BOP-R)، Type 2 (MDB-P، تابلوی شرکت) | Phoenix، DEHN، ABB OVR |
| SPD داده | CAN، RS-422، حلقهٔ ایمنی 24 V | Phoenix TERMITRAB / PLUGTRAB، DEHN BLITZDUCTOR XT |
| فیوز gPV | 1000 V DC، 40 A | Mersen HP10M / HP14M، Bussmann PV |
| مقاومت‌های ترمز | R_BR1: 18 Ω (2×36)، 36 kW/10 s، ≥ 400 kJ، 6 kW پیوسته؛ R_BR2: 8 Ω، 30–40 kW/10 s؛ فولاد ضدزنگ edge-wound یا grid، IP23 + کلاهک باران، کلید حرارتی NC | Cressall، Danotherm، Frizlen، یا ساخت داخلی با تست نوعی |
| کنتورها | سه‌فاز، Modbus RTU، کلاس 0.5S/1 | Eastron SDM630-Modbus، Schneider PM5110، Janitza UMG 96 |
| VFD پمپ‌ها | 4 kW، چوک DC، C2، Modbus | سند 01 §۶ |
| کولرها | soft starter کمپرسور یا جایگزینی با اینورتری | مدل‌های اینورتری Gree / Midea / LG در ایران رایج‌اند |
| شبکه | سوییچ مدیریتی صنعتی با SFP ×2 (ER و بام)، فیبر OM3 زره‌دار 4 کور | Moxa، Phoenix FL SWITCH، Planet IGS |
| روتر | LTE دو سیم‌کارت با WireGuard، پیامک آلارم، باند LTE ایران (B3/B7/B40/B41 بررسی شود) | Teltonika RUT956 / RUTX11 |

## ۱۰. پشتهٔ پایش از راه دور (B5 + ابر)

```
 B1 ECU ──Ethernet (VLAN OT)── B5 CM5 ──┬── HMI محلی (Chromium kiosk) + مانیتور سرویس بام (thin client، فیبر)
   Modbus TCP server                    ├── gr180-gateway (Python/Go): Modbus TCP poll 1–10 Hz، UDP 100 Hz، دانلود event record
   UDP stream 100 Hz                    ├── VictoriaMetrics (روند 1 s، ۲ سال محلی ≈ 3 GB/سال)
   HTTP/TFTP: رکورد trip               ├── PostgreSQL / SQLite: آلارم‌ها (ISA-18.2)، رویدادها، شمارنده‌های عمر
                                        ├── Grafana (روند مهندسی) + Node-RED (یکپارچه‌سازی HVAC، اختیاری)
                                        ├── Mosquitto bridge (TLS، store-and-forward) ──┐
                                        └── WireGuard client                           │
 روتر LTE + اینترنت ساختمان (فایروال، بدون پورت باز ورودی) ──── WireGuard ──────────── VPS (داخلی، مثلاً ArvanCloud/ParsPack، یا خارجی در صورت امکان)
                                                                                          ├── WireGuard hub (دسترسی مهندسین)
                                                                                          ├── EMQX/Mosquitto + VictoriaMetrics + Grafana
                                                                                          ├── هشدار: Grafana alerting → پیامک (Kavenegar) / Bale / Telegram / email
                                                                                          └── پشتیبان روزانهٔ پایگاه داده و رکوردها
```

**اصول:**
- **هیچ تابع ایمنی به B5 یا شبکه وابسته نیست.**
- فرمان‌های راه دور فقط در حالت REMOTE: start/stop، setpoint، reset تریپ‌های کلاس R. trip‌های L و LO فقط محلی ریست می‌شوند (سند 03 §۷).
- **احراز هویت:** حساب‌های نقش‌محور (اپراتور، مهندس، نگهداری)، 2FA روی VPS، ثبت همهٔ فرمان‌ها (audit log).
- **امنیت سیستم‌عامل B5:**
  - Raspberry Pi OS Lite 64-bit (Debian 12) با root فقط‌خواندنی (overlayroot) و داده روی NVMe
  - به‌روزرسانی امضاشده
  - شبکهٔ OT جدا از IT (VLAN)
- **سرویس‌های خارجی ممکن است از ایران مسدود باشند** (AWS IoT، Azure، Teltonika RMS)، پس همه‌چیز **self-hosted** است. پیامک داخلی هم به‌عنوان پشتیبان پیام‌رسان‌ها در نظر گرفته شده.
- **به‌روزرسانی firmware بردها:** از B5 روی CAN-FD با bootloader امضاشده، فقط در MAINT و STANDBY.
- **زمان:** NTP از اینترنت + RTC CM5. B1 با B5 همگام می‌شود (برای هم‌زمانی رویدادها ±10 ms).
