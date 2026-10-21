# GR180-CCHP — فهرست اقلام (BOM) HVAC و بار الکتریکی

تاریخ: ۲۰۲۶-۱۰-۲۱

> **برندها فقط «کاندید» هستند.**
> - موجودی، نمایندگی در ایران و امکان واردات (به‌خصوص اقلام ژاپنی، آمریکایی و برخی اروپایی به‌خاطر تحریم و انتقال پول) باید پیش از سفارش استعلام شود.
> - «داخلی» یعنی ساخت یا مونتاژ در ایران یا عرضهٔ رایج در بازار ایران.
> - اولویت با کیفیت و عمر طولانی است (docs/03).

## ۱. BOM

### الف) اگزوز و آب داغ

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| HX-1 | 1 | مبدل اگزوز/آب لوله‌فین‌دار مارپیچ ۶۹ kW، ۸ × ۱۵ لوله Ø25.4 × 1.65، فین 11 × 0.8 mm، 5 fpi، **تمام 316L**، طراحی گاز ۴۰۰ °C، آب PN10 / 120 °C، هدرها بیرون جریان گاز، درب بازدید | ساخت سفارشی توسط سازندگان داخلی مبدل یا دیگ (با لولهٔ فین‌دار 316L وارداتی چینی، HF-welded). مرجع: Unifin (کانادا)، Cain Industries (آمریکا)، Kelvion (آلمان) | طراحی حرارتی پایه در `hvac_design.py`. سازنده محاسبه را تأیید کند. تست ۱۵ bar. |
| D-801 | 1 | diverter سه‌دهانه DN250، 316L، طراحی ۶۵۰ °C، نشتی ≤ ۱ ٪، actuator 24 VAC مدوله + spring-return ≤ ۱۵ s، limit switch دوگانه | بدنه: ساخت داخلی. actuator: Belimo (سری spring-return، مثل AF24-SR / NF24-SR بسته به گشتاور)، Siemens GBB/GIB | شفت بلند با heat-break |
| ST-1 + bypass | 1 | دودکش و کانال DN250 دوجدارهٔ 316L با عایق، +۴.۰ m، drain و تله، پورت نمونه‌برداری، مهار باد | Jeremias، Schiedel (اروپا)؛ سازندگان داخلی دودکش استیل دوجداره | |
| NP-1 | 1 | pot خنثی‌کنندهٔ کندانس (MgO یا سنگ آهک) | Neutrakon یا ساخت داخلی | |
| LLH-1 | 1 | هدر کم‌افت + بافر ۲۰۰ L، ۶ اتصال DN50/65، PN10 | Reflex، Caleffi، Sinusverteiler؛ ساخت داخلی (مخزن تحت فشار) | عایق ۵۰ mm |
| P-1A/B | 1 | پمپ دوقلو wet-rotor ECM، 8.8 m³/h @ 4.4 m، 110 °C | Grundfos MAGNA3 D، Wilo Stratos MAXO-D، DAB EVOPLUS D | duty/standby داخلی |
| P-2A, P-2B | 2 | in-line ECM: 8.64 m³/h @ 13.7 m و 4.32 m³/h @ 13.7 m | Grundfos MAGNA3 / TPE3، Wilo Stratos MAXO، DAB EVOPLUS | |
| P-3 | 1 | wet-rotor ECM: 1.3 m³/h @ 7.5 m | Grundfos ALPHA2 / MAGNA3 25-xx، Wilo Yonos MAXO | |
| HX-2 | 1 | PHE **دوجداره** (double-wall) ۳۰ kW، 90/70 ← 50/62 °C، SS316 | Alfa Laval (DW)، SWEP (DW)، Kelvion | آب بهداشتی |
| HX-4 | 1 | PHE لحیم‌شدهٔ استیل گلیکول/آب خنک‌کن ۳.۵ kW (گلیکول 40/35 °C، CW 32/35 °C، 1.0 m³/h) + XV-1305 (NO) | SWEP، Alfa Laval، Danfoss، Kaori | رابط مدار کمکی موتور |
| DC-1 | 1 | dry cooler مدار کمکی ~۴ kW در هوای ≤ ۲۵ °C، فن EC، کویل Cu/Al با پوشش ساحلی | Güntner، LU-VE، Alfa Laval؛ سازندگان داخلی کندانسور هوایی | زمستان و پشتیبان |
| HX-3 | 1 | PHE گرمایش ۱۵ kW، 85/60 ← 40/45 °C، SS316، brazed | SWEP، Alfa Laval، Danfoss، Kaori (تایوان)؛ برندهای چینی | |
| TV-1131, V-PRI | 2 | شیر سه‌راهه DN25: مدوله و دووضعیته | Belimo (R3/LR)، Siemens VXG، Danfoss | |
| TK-DHW | 1 | مخزن DHW ۵۰۰ L، 316L یا لعابی، T&P، منبع انبساط بهداشتی، TMV ۵۰ °C | تولیدکنندگان داخلی منبع، Caleffi (TMV) | داخل ساختمان |
| P-7 | 1 | پمپ گردش DHW، برنزی یا استیل | Grundfos UP-B / COMFORT، Wilo Star-Z | |
| ET-1 | 1 | منبع انبساط ۳۵ L / 10 bar + **intermediate vessel ~20 L** | Reflex (N 35 + V 20)، Varem، Zilmet، Flamco؛ معادل داخلی | |
| AS-1 | 1 | جداکنندهٔ microbubble + dirt + magnetic، DN50، 110 °C | Spirotech SpiroCombi Air & Dirt، Caleffi DISCALDIRT (5463)، Flamco Flexair | |
| PSV-1111 | 1 | شیر اطمینان DN20، ۵.۵ bar، بخار ≥ ۱۲۰ kg/h | Caleffi، Watts، Goetze | |

### ب) چیلر و آب سرد

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| CH-1 / CH-2 | 1 + 1 | چیلر جذبی LiBr تک‌اثره با آب داغ، کلاس 35 + 17.6 kW (یا **۲ × ۳۵ kW**)، outdoor، آب سرد 7 °C | **Yazaki WFC-SC10 + SC5** (ژاپن، مرجع طراحی؛ امکان فروش به ایران نامطمئن). **EAW Wegracal SE 30 + SE 15** (آلمان). **Thermax** (هند، سری hot-water؛ حداقل ظرفیت استعلام شود). **Broad**، **Shuangliang**، **Hope Deepblue** (چین؛ مدل‌های کوچک hot-water استعلام شوند) | مهم‌ترین قلم واردات. دیتاشیت دبی‌ها، Δp، حداقل دمای آب خنک‌کن و فشار کاری لازم است. |
| TK-1 | 1 | مخزن بافر/decoupler آب سرد ۵۰۰ L، ۴ اتصال DN50، PN10، عایق ۵۰ mm + روکش | Reflex، Caleffi؛ ساخت داخلی | |
| P-4A, P-4B | 2 | in-line ECM: 5.47 m³/h @ 9.6 m و 2.77 m³/h @ 9.5 m | Grundfos MAGNA3 / TPE3، Wilo Stratos MAXO، DAB | |
| P-5A/B | 1 | پمپ دوقلو ECM با کنترل Δp، 7.8 m³/h @ 10.8 m | Grundfos MAGNA3 D، Wilo Stratos MAXO-D | |
| ET-2, AS-2, PSV-1211 | 1 | منبع انبساط ۲۵ L / 10 bar؛ جداکنندهٔ DN50؛ PSV DN15 ۵.۵ bar | مثل ET-1 و AS-1 | |
| MV-CH1E, MV-CH2E | 2 | شیر توپی موتوری DN50 / DN40 on-off با end switch | Belimo (R2xx + LF/NF)، Siemens | اینترلاک changeover |
| V-CO1, V-CO2 | 2 | شیر توپی سه‌راهه DN50 on-off با end switch | Belimo، Siemens | |
| CC-1 | 1 | کویل آب سرد ورودی موتور ۱۹ kW، ۸ ردیف، 10 fpi، 0.40 × 0.40 m، Cu/Cu (یا Al با Blygold)، سینی SS304، droplet eliminator | سازندگان داخلی کویل (معمولاً سازندگان هواساز)، Lu-Ve (ایتالیا)، Güntner | داخل IF-1 |
| TV-1221 | 1 | PICV DN25 + actuator 0–10 V با فیدبک | Belimo EPIV / PIQCV، Danfoss AB-QM + NovoCon، IMI TA-Compact-P | |
| FCU-1..4 | 4 | فن‌کویل سقفی روکار (under-ceiling) کلاس **800 CFM**، ۷.۶ kW اسمی، موتور EC، با PICV DN20 و کنترلر Modbus | **داخلی:** ساراول (Saravel)، ایران رادیاتور، تهویه. **چینی:** Gree، Midea. **پریمیوم:** Carrier، Daikin | ظرفیت در شرایط ۲۵.۴ °C / ۹.۸ g/kg تأیید شود |
| PICV FCU | 4 + 1 | PICV DN20 مدوله (FCU-E: DN15 on/off) | Belimo، Danfoss، IMI TA | |
| کنترلر اتاق | 5 | ترموستات Modbus RTU با ورودی کندانس و خروجی 0–10 V فن EC | Siemens RDF، Schneider SE8000، برندهای چینی Modbus | |
| ERV-1 (اختیاری) | 1 | تهویهٔ بازیاب انرژی ۵۰۰ m³/h، هستهٔ enthalpy، فیلتر F7 | Daikin VAM، Mitsubishi Lossnay، Panasonic، Holtop (چین) | ~۲.۵ kW بار کمتر |
| FCU-E | 1 | فن‌کویل دیواری هیدرونیک کلاس 400 CFM، EC، سینی چکه + پمپ کندانس | مثل FCU | **نه بالای تجهیزات برقی** |
| AC-E | 1 | اسپلیت DX اینورتر 12 kBTU/h، **کمپرسور T3** (۵۲ °C)، ورودی dry-contact on/off | Gree، Midea، LG، Samsung (مونتاژ یا عرضهٔ داخلی) | پشتیبان |
| LD-E | 1 | کابل نشت‌یاب + ماژول | TTK FG-SYS، nVent TraceTek؛ چینی | |

### ج) آب خنک‌کن، برج و تصفیهٔ آب

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| CT-1 | 1 | برج counterflow گرد FRP کلاس **۴۰ تن** (۱۰۹ kW، 34.9 → 31.5 °C @ WB 28.5)، fill کم‌رسوب، drift ≤ ۰.۰۰۲ ٪، موتور IP55 مناسب VFD، سوئیچ ارتعاش، حوضچهٔ سرپوشیده، اتصالات SS304 | **Liang Chi LBC-40** (تایوان)، Kuken، Shinwa (تایوان)، Truwater (مالزی)؛ سازندگان داخلی برج FRP گرد؛ پریمیوم EVAPCO، BAC | انتخاب با نرم‌افزار سازنده تأیید شود |
| P-6A/B | 2 | end-suction یا in-line، 27.5 m³/h @ 17.1 m، موتور IE4 2.2 kW، بدنه چدن و پروانهٔ برنزی یا استیل | Grundfos NB/NBE یا TP، Wilo Atmos GIGA، **پمپیران** (end-suction)، Lowara/Xylem، Ebara | duty/standby |
| VFD × 3 | 3 | VFD HVAC 2.2 kW (P-6A، P-6B) و 1.5 kW (فن)، Modbus RTU، فیلتر هارمونیک یا DC choke | Danfoss FC 102، ABB ACH580، Siemens G120P، Delta، INVT، LS | |
| BS-1 | 1 | basket strainer DN100 با گیج Δp | Zetkama، Genebre؛ داخلی | |
| TV-1301 | 1 | شیر سه‌راههٔ bypass برج DN100 مدوله، یا دو پروانه‌ای کوپل | Belimo، Siemens، Keystone | |
| F-SS | 1 | جداکنندهٔ گریز از مرکز side-stream ~۲.۲ m³/h + purge خودکار | Lakos (Pentair)، Yardney؛ فیلتر شنی داخلی | |
| WT-1 | 1 | کنترلر EC/pH/ORP با خروجی 4–20 mA و رله، سل نمونه، کوپن‌گیر | Walchem W900، ProMinent DULCOMETER diaLog، Emec، Seko | |
| DP-1..3 | 3 | پمپ دوزینگ دیافراگمی با ورودی پالس | ProMinent Beta/gamma، Grundfos DDA، Etatron، Seko | |
| مواد شیمیایی | — | بازدارنده (فسفونات + پلیمر + TTA)، BCDMH یا NaOCl + NaBr، isothiazolinone یا DBNPA، بازدارندهٔ مولیبدات برای مدارهای بسته | Nalco/Ecolab، Kurita، BWA؛ پیمانکاران داخلی تصفیهٔ آب صنعتی | قرارداد سرویس ماهانه |
| XV-1301/1302/1303 | 3 | شیر برقی و توپی موتوری DN20 | Belimo، ASCO، ODE | |
| FQ-1301/1302/1410 | 3 | کنتور آب با خروجی پالس | Zenner، Sensus، Itron؛ داخلی | |
| RO-1 | 1 | RO ۳۰۰ L/h permeate، ۲ × 4040 BW، پیش‌تصفیه ۵ µm، دوز antiscalant، مخزن blend ۳۰۰–۵۰۰ L، TV-1401 | ممبران: DuPont FilmTec، Hydranautics، Toray، Vontron (چین)؛ اسکید: مونتاژکاران داخلی | داخل ساختمان |
| P-9 | 1 | بوستر طبقاتی ECM یا VFD با مخزن تحت فشار | Grundfos SCALA2 / CMBE، Wilo، DAB E.sybox | |
| EH-1301, HT-1 | 1 + 30 m | هیتر حوضچه ۱.۵ kW با ترموستات؛ کابل self-regulating ۲۰ W/m با کنترلر، RCD ۳۰ mA | nVent Raychem، Thermon؛ چینی | زمستان |
| backflow BA | 1 | backflow preventer نوع BA برای پرکن مدار بسته | Watts، Caleffi، Honeywell | |

### د) لوله‌کشی، عایق و ابزار دقیق

| قلم | مشخصه | کاندیدها |
|---|---|---|
| لولهٔ آب داغ | A106 Gr.B Sch40 بدون درز، جوشی، فلنج PN16 | نورد و لولهٔ صفا و دیگر تولیدکنندگان داخلی؛ وارداتی |
| لولهٔ آب سرد | A53/A106 Sch40؛ داخل سالن فولاد یا PP-R PN20 | داخلی |
| لولهٔ آب خنک‌کن | **316L Sch10S** (ترجیح) یا PE100 SDR11 مشکی | استیل وارداتی؛ PE داخلی |
| عایق آب سرد | الاستومری (k ≤ 0.036)، **۴۰ mm روی بام** + روکش آلومینیوم/GRP، ۱۹ mm داخل | Armacell (Armaflex)، K-Flex، Kaimann؛ معادل داخلی |
| عایق آب داغ و اگزوز | پشم سنگ ۵۰ mm (لوله) و ۱۰۰ mm (HX و کانال) + روکش آلومینیوم | Rockwool، Isover؛ پشم سنگ و شیشهٔ داخلی |
| شیرها | پروانه‌ای lug PN16 EPDM (≥ DN65)، توپی full-bore (≤ DN50)، یکطرفهٔ silent، balancing با test point | Genebre، Zetkama، KSB، IMI TA (STAD)؛ داخلی برای شیرهای قطع |
| صافی Y | توری ۱ mm، فلنجی یا دنده‌ای | Genebre، Zetkama؛ داخلی |
| RTD | PT1000 کلاس A با غلاف (thermowell) استیل | WIKA، JUMO، Endress+Hauser، Siemens QAE |
| ترموکوپل | نوع K، غلاف 316/Inconel | WIKA، JUMO؛ داخلی |
| ترانسمیتر فشار و Δp آب | 4–20 mA، 0–10 bar / 0–2.5 bar | WIKA، Danfoss MBS، Huba، Keller، Siemens QBE |
| Δp هوا و گاز | 4–20 mA، 0–1 kPa / 0–500 Pa | Huba 699، Dwyer 616KD، Siemens QBM |
| دبی‌سنج | الکترومغناطیسی DN50/DN100، 4–20 mA + Modbus | Endress+Hauser Promag، Siemens SITRANS FM، Krohne؛ چینی |
| کنتور انرژی | HM-1..4، M-Bus | Kamstrup MULTICAL 603، Siemens Ultraheat T550، Danfoss Sonometer |
| دما و رطوبت بیرون | 4–20 mA با radiation shield | Vaisala HMP110، E+E EE210، Rotronic |
| فلوسوئیچ | پدلی یا حرارتی، کنتاکت دوگانه | Honeywell، Kobold، Danfoss |
| تابلوی BOP-R | IP55 با سایه‌بان و فن فیلتردار، MCB/MCCB، کنتاکتور، SPD، RCD، B6-R، منبع 24 V با باتری، کنتور EM-HVAC | Rittal یا تابلوساز داخلی؛ Schneider، ABB، Siemens، LS، Chint |

## ۲. بار الکتریکی تجهیزات HVAC

خروجی `hvac_design.py`. ستون‌ها:

- **متصل:** توان نامی واحد در حال کار با حاشیه.
- **تابستان:** کار پیوسته در طراحی تابستان.
- **زمستان:** کار متوسط در زمستان.

| تگ | قلم | متصل kW | تابستان kW | زمستان kW | تغذیه | برد |
|---|---|---|---|---|---|---|
| P-1A/B | HW primary pump, twin ECM | 0.38 | 0.23 | 0.23 | 1~230 V | B6-R |
| P-2A | HW pump CH-1 | 0.89 | 0.59 | 0.00 | 1~230 V | B6-R |
| P-2B | HW pump CH-2 | 0.50 | 0.33 | 0.00 | 1~230 V | B6-R |
| P-3 | DHW/heating branch pump | 0.12 | 0.02 | 0.08 | 1~230 V | B6-R |
| P-4A | CHW primary CH-1 | 0.46 | 0.31 | 0.00 | 1~230 V | B6-R |
| P-4B | CHW primary CH-2 | 0.26 | 0.18 | 0.00 | 1~230 V | B6-R |
| P-5A/B | CHW secondary twin ECM (dp control) | 0.73 | 0.37 | 0.18 | 1~230 V | B6-R |
| P-6A/B | condenser-water pump + VFD | 2.97 | 2.12 | 0.00 | 3~400 V | B6-R |
| CT-1 fan | tower fan + VFD | 1.10 | 0.83 | 0.00 | 3~400 V | B6-R |
| CH-1 | chiller controls/pumps (internal) | 0.21 | 0.21 | 0.00 | 1~230 V | B6-R |
| CH-2 | chiller controls/pumps (internal) | 0.05 | 0.05 | 0.00 | 1~230 V | B6-R |
| D-801 | exhaust diverter actuator (spring return) | 0.02 | 0.01 | 0.01 | 24 VAC via SR1 safety output | B4/SR1 |
| WT-1 | dosing pumps x3 + conductivity controller + BD valve | 0.10 | 0.05 | 0.01 | 1~230 V | B6-R |
| F-SS | side-stream separator purge valve | 0.01 | 0.01 | 0.00 | 24 VDC | B6-R |
| RO-1 | RO unit 300 L/h (indoor), ~40 % duty | 0.75 | 0.30 | 0.05 | 1~230 V | B6-E |
| P-9 | make-up / permeate booster to roof | 0.37 | 0.10 | 0.02 | 1~230 V | B6-E |
| P-7 | DHW tank charging / circulation | 0.06 | 0.03 | 0.06 | 1~230 V | B6-E |
| EH-1301 | tower basin heater (freeze, standby) | 1.50 | 0.00 | 0.05 | 1~230 V | B6-R |
| HT-1 | heat tracing make-up/CW lines 30 m x 20 W/m | 0.60 | 0.00 | 0.05 | 1~230 V | B6-R |
| BOP-R | roof BOP panel: B6-R, PSU, meters, panel fan | 0.08 | 0.08 | 0.06 | 1~230 V | B6-R |
| DC-1 | aux glycol dry cooler EC fans (winter / backup) | 0.35 | 0.05 | 0.15 | 1~230 V | B6-R |
| FCU-1..4 | hall fan coils 4 x 800 CFM (EC motors) | 0.26 | 0.18 | 0.10 | 1~230 V | building |
| ERV-1 | energy-recovery ventilator 500 m3/h (option) | 0.18 | 0.15 | 0.10 | 1~230 V | building |
| FCU-E | electrical-room fan coil EC | 0.04 | 0.04 | 0.00 | 1~230 V | B6-E |
| AC-E | electrical-room DX split standby 12 kBTU/h | 1.50 | 0.00 | 0.30 | 1~230 V | B6-E |
| EF-E | battery/electrical-room exhaust fan | 0.03 | 0.03 | 0.03 | 1~230 V | B6-E |
| **جمع** | | **13.52** | **6.27** | **1.49** | | |

**خلاصه:**

- **مصرف داخلی پلانت** (بدون فن‌کویل‌ها و ERV سالن): **۵.۹۳ kW در تابستان** و ۱.۲۹ kW در زمستان. انرژی سالانهٔ HVAC ~۳۹ MWh.
- **اثر بر برق خالص:** `cchp_study.py` برای پمپ‌ها و فن برج فقط **۱.۳ kW** فرض کرده بود (`AUX_CCHP`). عدد واقعی با تجهیزات بالا ~۵.۹ kW است. پس برق خالص طراحی تابستان از **۲۱.۳** به **~۱۶.۶ kW** می‌رسد.
  - بزرگ‌ترین قلم: پمپ آب خنک‌کن P-6 (۲.۱ kW). Δp جذب‌کننده و کندانسور چیلر ۸۴ kPa و ارتفاع برج ۴۰ kPa است.
  - بعد از آن فن برج (۰.۸) و پمپ‌های آب داغ چیلرها (۰.۹).
- **درآمد مقابل:** سرمای ساختمان (۲۵.۴ kW) ~۹.۸ kW برق کولرهای گازی را حذف می‌کند (COP ۲.۶). سود الکتریکی معادل کل سیستم هنوز مثبت و بزرگ است.
- **کاهش ممکن** (~۰.۵–۰.۸ kW):
  - چیلری با Δp کمتر در مدار خنک‌کن.
  - برج cross-flow با توزیع ثقلی (ارتفاع پمپاژ کمتر).
  - حذف primary/secondary آب داغ (−۰.۲ kW، توصیه نمی‌شود؛ `02` بخش ۴).

**تغذیه:**

- **تابلوی BOP-R** از خروجی سه‌فاز ۴۰۰ V اینورتر تغذیه می‌شود.
  - بار متصل ~۱۳.۵ kW، یعنی ~۲۲ A با PF ۰.۹. جریان کار تابستان ~۱۰ A.
  - **فیدر ۴ × ۱۰ mm² مس + ارت با MCCB ۳۲ A** (جا برای توسعه و هارمونیک VFD).
  - دو بخش: **ضروری** (B6، چیلرها، P-1، P-4، P-6، فن برج، D-801) و **غیرضروری** (هیترها، heat tracing).
  - SPD نوع 2. RCD ۳۰ mA برای هیترها و پریزها.
- **بارهای B6-E** (RO، P-9، P-7، FCU-E، AC-E، EF-E) از تابلوی ۲۳۰ V اتاق برق تغذیه می‌شوند.
- **جریان راه‌اندازی:** همهٔ پمپ‌ها ECM یا VFD با استارت نرم‌اند، پس جریان راه‌اندازی بزرگ به اینورتر تحمیل نمی‌شود (docs/03 §۲). AC-E اینورتری است.
