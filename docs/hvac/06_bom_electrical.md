# GR180-CCHP — فهرست اقلام (BOM) HVAC و بار الکتریکی

تاریخ: ۲۰۲۶-۱۰-۲۱

> **برندها فقط «کاندید» هستند.**
> - موجودی، نمایندگی در ایران و امکان واردات (به‌خصوص اقلام ژاپنی، آمریکایی و برخی اروپایی به‌خاطر تحریم و انتقال پول) باید پیش از سفارش استعلام شود.
> - «داخلی» یعنی ساخت یا مونتاژ در ایران یا عرضهٔ رایج در بازار ایران.
> - اولویت با کیفیت و عمر طولانی است (docs/03).
> - **بدون تأمین‌کنندهٔ آمریکایی** (docs/06_master_design §۵): فقط اروپایی، ژاپنی/تایوانی/کره‌ای، چینی و داخلی.
> - فهرست قطعه‌به‌قطعه با وزن و فایل مدل سه‌بعدی: `docs/bom/plant_bom.csv` (مدل: `cad/plant/`).

## ۱. BOM

### الف) اگزوز و آب داغ

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| HX-1 | 1 | مبدل اگزوز/آب لوله‌فین‌دار مارپیچ ۵۲ kW در اگزوز ۲۱۹ °C (ساخته برای ۶۹ kW، برای گزینهٔ تقویت نگه داشته)، ۸ × ۱۵ لوله Ø25.4 × 1.65، فین 11 × 0.8 mm، 5 fpi، **تمام 316L**، طراحی گاز ۴۰۰ °C، آب PN10 / 120 °C، هدرها بیرون جریان گاز، درب بازدید | ساخت سفارشی توسط سازندگان داخلی مبدل یا دیگ (با لولهٔ فین‌دار 316L وارداتی چینی، HF-welded). مرجع: Kelvion (آلمان)، Bosal (بلژیک)، Thermofin (آلمان) | طراحی حرارتی پایه در `hvac_design.py`. سازنده محاسبه را تأیید کند. تست ۱۵ bar. |
| D-101 | 1 | diverter سه‌دهانه DN250، 316L، طراحی ۶۵۰ °C، نشتی ≤ ۱ ٪، actuator 24 VAC مدوله + spring-return ≤ ۱۵ s، limit switch دوگانه | بدنه: ساخت داخلی. actuator: Belimo (سری spring-return، مثل AF24-SR / NF24-SR بسته به گشتاور)، Siemens GBB/GIB | شفت بلند با heat-break |
| ST-1 + bypass | 1 | دودکش و کانال DN250 دوجدارهٔ 316L با عایق، +۴.۰ m، drain و تله، پورت نمونه‌برداری، مهار باد | Jeremias، Schiedel (اروپا)؛ سازندگان داخلی دودکش استیل دوجداره | |
| SL-101 | 1 | **صداخفه‌کن اگزوز** جذبی straight-through DN250، طول ~۱.۲ m، 316L مشبک + پشم بازالت دمای بالا (۶۵۰ °C) با لایهٔ محافظ، IL ۱۵–۲۰ dB(A)، Δp ≤ ۵۰ Pa، ~۶۰ kg | Jeremias، Kemper (آلمان)؛ سازندگان داخلی صداخفه‌کن صنعتی | در دودکش مشترک، بالای اتصال bypass |
| IF-1 | 1 | **ورودی هوای موتور:** لوور آکوستیک ضد باران (عمق ۳۰۰ mm) + پلنوم با لاینر جاذب ۵۰ mm + فیلتر G4 + F8 + محفظهٔ CC-1 + droplet eliminator، گالوانیزهٔ رنگی یا آلومینیوم، ~۰.۵ × ۰.۵ m رو | Trox (آلمان)، Gebhardt؛ هواسازسازان داخلی (فیلتر: Camfil سوئد، فیلترسازان داخلی) | +۲۰–۴۰ Pa افت |
| NP-1 | 1 | pot خنثی‌کنندهٔ کندانس (MgO یا سنگ آهک) | Neutrakon یا ساخت داخلی | |
| LLH-1 | 1 | **جداکنندهٔ هیدرولیکی DN65** بدون بافر (گزینهٔ سبک پیشنهادی، `09` §۳)، ۶ اتصال DN50/65، PN10، با جداکنندهٔ لجن و هوا. گزینهٔ پایه: هدر + بافر ۲۰۰ L | Reflex، Caleffi، Sinusverteiler؛ ساخت داخلی | عایق ۵۰ mm |
| P-1A/B | 1 | پمپ دوقلو wet-rotor ECM، 8.80 m³/h @ 3.6 m، 110 °C | Grundfos MAGNA3 D، Wilo Stratos MAXO-D، DAB EVOPLUS D | duty/standby داخلی؛ هرگز با موتور روشن خاموش نمی‌شود |
| P-2A, P-2B | 2 | in-line ECM در حالت constant-flow (بدون شیر balancing): 8.64 m³/h @ 7.3 m و 4.32 m³/h @ 7.3 m | Grundfos MAGNA3 / TPE3، Wilo Stratos MAXO، DAB EVOPLUS | Δp ژنراتور ≤ ۵۰ kPa (مشخصات چیلر) |
| P-3 | 1 | wet-rotor ECM: 1.29 m³/h @ 6.7 m | Grundfos ALPHA2 / MAGNA3 25-xx، Wilo Yonos MAXO | |
| HX-2 | 1 | PHE **دوجداره** (double-wall) ۳۰ kW، 90/70 ← 50/62 °C، SS316 | Alfa Laval (DW)، SWEP (DW)، Kelvion | آب بهداشتی |
| HX-4 | 1 | PHE لحیم‌شدهٔ استیل، **trim اختیاری** گلیکول/آب خنک‌کن ۲.۷ kW (گلیکول 45/40 °C، CW 32/35 °C، 0.9 m³/h) + XV-305 (NC) | SWEP، Alfa Laval، Danfoss، Kaori | موتور به آن وابسته نیست |
| OC-1 | 1 | خنک‌کن روغن **۱.۱ kW** (۰.۸۱ kW روغن هسته روی یاتاقان‌های 608 × ۱.۲۵؛ ۱.۶ kW اگر یاتاقان‌های FPT/PMG هم روغن مشترک بگیرند) روی مدار گلیکول (روغن 100/70 °C، ~۱.۹ L/min؛ PHE لحیم‌شدهٔ استیل ~۱۰–۱۴ صفحه) | SWEP B10، Alfa Laval CB؛ چینی | قلم پکیج موتور؛ بعد از B3 و PMG در مسیر گلیکول |
| DC-1 | 1 | dry cooler مدار گلیکول **۴.۰ kW در هوای ۴۶ °C** (گلیکول ۵۹ → ۵۵ °C، ۱۵ L/min، هوا ~۲۶۰۰ m³/h)، فن‌های EC (~۰.۱۶ kW)، کویل Cu/Al با پوشش ساحلی | Güntner، LU-VE، Alfa Laval؛ سازندگان داخلی کندانسور هوایی | خنک‌کن اصلی؛ فن روی B4 (DC-1-FAN). **pad آدیاباتیک** (XV-307، ~۱۶ L/h در پیک) برای گلیکول ≤ ۴۵ °C (۳۸.۵ °C با pad، ۵۲ °C خشک) |
| HX-3 | 1 | PHE گرمایش ۱۵ kW، 85/60 ← 40/45 °C، SS316، brazed | SWEP، Alfa Laval، Danfoss، Kaori (تایوان)؛ برندهای چینی | |
| TV-131, V-PRI | 2 | شیر سه‌راهه DN25: مدوله و دووضعیته | Belimo (R3/LR)، Siemens VXG، Danfoss | |
| TK-DHW | 1 | مخزن DHW ۵۰۰ L، 316L یا لعابی، T&P، منبع انبساط بهداشتی، TMV ۵۰ °C | تولیدکنندگان داخلی منبع، Caleffi (TMV) | داخل ساختمان |
| P-7 | 1 | پمپ گردش DHW، برنزی یا استیل | Grundfos UP-B / COMFORT، Wilo Star-Z | |
| ET-1 | 1 | منبع انبساط ۳۵ L / 10 bar + **intermediate vessel ~20 L** | Reflex (N 35 + V 20)، Varem، Zilmet، Flamco؛ معادل داخلی | |
| AS-1 | 1 | جداکنندهٔ microbubble + dirt + magnetic، DN50، 110 °C | Spirotech SpiroCombi Air & Dirt، Caleffi DISCALDIRT (5463)، Flamco Flexair | |
| PSV-111 | 1 | شیر اطمینان DN20، ۵.۵ bar، بخار ≥ ۱۲۰ kg/h | Caleffi، Goetze، Herz | |

### ب) چیلر و آب سرد

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| CH-1 / CH-2 | 1 + 1 | چیلر جذبی LiBr تک‌اثره با آب داغ، کلاس 35 + 17.6 kW (یا **۲ × ۳۵ kW**)، outdoor، آب سرد 7 °C. **مشخصات خرید rev B:** Δp آب داغ ≤ ۵۰، آب سرد ≤ ۴۰، آب خنک‌کن ≤ ۵۰ kPa؛ کار با ۸۰–۸۵ ٪ دبی CW؛ پورت Modbus (دمای ژنراتور، حاشیهٔ کریستالیزاسیون، رقیق‌سازی) | **Yazaki WFC-SC10 + SC5** (ژاپن، مرجع طراحی؛ امکان فروش به ایران نامطمئن). **EAW Wegracal SE 30 + SE 15** (آلمان). **Thermax** (هند، سری hot-water؛ حداقل ظرفیت استعلام شود). **Broad**، **Shuangliang**، **Hope Deepblue** (چین؛ مدل‌های کوچک hot-water استعلام شوند) | مهم‌ترین قلم واردات. دیتاشیت دبی‌ها، Δp، حداقل دمای آب خنک‌کن و فشار کاری لازم است. |
| TK-1 | 1 | مخزن بافر/decoupler آب سرد **۳۰۰ L** (گزینهٔ سبک؛ پایه ۵۰۰ L)، ۴ اتصال DN50، PN10، عایق ۵۰ mm + روکش | Reflex، Caleffi؛ ساخت داخلی | |
| P-4A, P-4B | 2 | in-line ECM در حالت constant-flow: 5.47 m³/h @ 6.0 m و 2.77 m³/h @ 6.0 m | Grundfos MAGNA3 / TPE3، Wilo Stratos MAXO، DAB | Δp اواپراتور ≤ ۴۰ kPa |
| P-5A/B | 1 | پمپ دوقلو ECM با کنترل Δp و reset، 6.77 m³/h @ 8.4 m | Grundfos MAGNA3 D، Wilo Stratos MAXO-D | |
| ET-2, AS-2, PSV-211 | 1 | منبع انبساط ۲۵ L / 10 bar؛ جداکنندهٔ DN50؛ PSV DN15 ۵.۵ bar | مثل ET-1 و AS-1 | |
| MV-CH1E, MV-CH2E | 2 | شیر توپی موتوری DN50 / DN40 on-off با end switch | Belimo (R2xx + LF/NF)، Siemens | اینترلاک changeover |
| V-CO1, V-CO2 | 2 | شیر توپی سه‌راهه DN50 on-off با end switch | Belimo، Siemens | |
| CC-1 | 1 | کویل آب سرد ورودی موتور **۲۱ kW تا هوای ۱۲ °C** (۱۷–۱۸.۷ kW در T1 = ۱۵ °C)، **۱۰ ردیف**، 10 fpi، 0.40 × 0.40 m، Cu/Cu (یا Al با Blygold)، سینی SS304، droplet eliminator | سازندگان داخلی کویل (معمولاً سازندگان هواساز)، Lu-Ve (ایتالیا)، Güntner | داخل IF-1 |
| TV-221 | 1 | PICV DN25 + actuator 0–10 V با فیدبک | Belimo EPIV / PIQCV، Danfoss AB-QM + NovoCon، IMI TA-Compact-P، Oventrop | |
| FCU-1..4 | 4 | فن‌کویل سقفی روکار (under-ceiling) کلاس **600 CFM** (~۵.۹ kW اسمی؛ سقف عایق، بار سالن ۱۷.۸ kW)، موتور EC، با PICV DN20 و کنترلر Modbus | **داخلی:** ساراول (Saravel)، ایران رادیاتور، تهویه. **چینی:** Gree، Midea. **پریمیوم:** Daikin، Sabiana (ایتالیا) | ظرفیت در شرایط ۲۵.۴ °C / ۹.۸ g/kg تأیید شود |
| PICV FCU | 4 + 1 | PICV DN20 مدوله (FCU-E: DN15 on/off) | Belimo، Danfoss، IMI TA | |
| کنترلر اتاق | 5 | ترموستات Modbus RTU با ورودی کندانس و خروجی 0–10 V فن EC | Siemens RDF، Schneider SE8000، برندهای چینی Modbus | |
| ERV-1 (اختیاری) | 1 | تهویهٔ بازیاب انرژی ۵۰۰ m³/h، هستهٔ enthalpy، فیلتر F7 | Daikin VAM، Mitsubishi Lossnay، Panasonic، Holtop (چین) | ~۲.۵ kW بار کمتر |
| FCU-E | 1 | فن‌کویل دیواری هیدرونیک کلاس 400 CFM، EC، سینی چکه + پمپ کندانس | مثل FCU | **نه بالای تجهیزات برقی** |
| AC-E | 1 | اسپلیت DX اینورتر 12 kBTU/h، **کمپرسور T3** (۵۲ °C)، ورودی dry-contact on/off | Gree، Midea، LG، Samsung (مونتاژ یا عرضهٔ داخلی) | پشتیبان |
| LD-E | 1 | کابل نشت‌یاب + ماژول | TTK FG-SYS (فرانسه)؛ چینی | |

### ج) آب خنک‌کن، برج و تصفیهٔ آب

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| CT-1 | 1 | برج FRP کلاس **۶۰ تن** با **توزیع کم‌ارتفاع** (ثقلی یا نازل کم‌فشار، ≤ ۲۵ kPa) و **فن EC/VFD ۱.۵ kW کم‌صدا** (پره‌های پهن)، **تشک ضد صدای آب** در حوضچه. طراحی ۱۱۱ kW، ۳۵.۸ → ۳۱.۸ °C @ WB 28.5 در ۶۰ ٪ دور. fill کم‌رسوب، drift ≤ ۰.۰۰۲ ٪، سوئیچ ارتعاش، حوضچهٔ سرپوشیده، اتصالات SS304 | **Liang Chi LBC-60** (تایوان)، Kuken، Shinwa (تایوان)، Truwater (مالزی)؛ سازندگان داخلی برج FRP؛ پریمیوم Gohl / Jaeggi (اروپا) | انتخاب با نرم‌افزار سازنده در ۶۰ ٪ دور تأیید شود |
| P-6A/B | 2 | end-suction یا in-line، 24.17 m³/h @ 8.6 m (۸۵ ٪ دبی نامی + HX-4؛ تا ۲۸.۵ m³/h در MAX-COOLING)، موتور IE4 1.5 kW، بدنه چدن و پروانهٔ برنزی یا استیل | Grundfos NB/NBE یا TP، Wilo Atmos GIGA، **پمپیران** (end-suction)، KSB Etanorm، Ebara | duty/standby، VFD روی FT-301 |
| VFD × 3 | 3 | VFD HVAC 1.5 kW (P-6A، P-6B) و 1.5 kW (فن، اگر فن EC نباشد)، Modbus RTU با گزارش توان، DC choke | Danfoss FC 102، ABB ACH580، Siemens G120P، Delta، INVT، LS | |
| BS-1 | 1 | basket strainer DN100 با گیج Δp | Zetkama، Genebre؛ داخلی | |
| TV-301 | 1 | شیر سه‌راههٔ bypass برج DN100 مدوله، یا دو پروانه‌ای کوپل | Belimo، Siemens، Genebre | |
| F-SS | 1 | جداکنندهٔ گریز از مرکز side-stream ~۲.۲ m³/h + purge خودکار | Netafim / Arkal (spin-klin)، Amiad (فیلتر دیسکی)؛ هیدروسیکلون یا فیلتر شنی داخلی | |
| WT-1 | 1 | کنترلر EC/pH/ORP با خروجی 4–20 mA و رله، سل نمونه، کوپن‌گیر | ProMinent DULCOMETER diaLog (آلمان)، Emec، Seko (ایتالیا)، Etatron | |
| DP-1..3 | 3 | پمپ دوزینگ دیافراگمی با ورودی پالس | ProMinent Beta/gamma، Grundfos DDA، Etatron، Seko | |
| مواد شیمیایی | — | بازدارنده (فسفونات + پلیمر + TTA)، BCDMH یا NaOCl + NaBr، isothiazolinone یا DBNPA، بازدارندهٔ مولیبدات برای مدارهای بسته | Kurita (ژاپن)، BWA (انگلیس)؛ پیمانکاران داخلی تصفیهٔ آب صنعتی | قرارداد سرویس ماهانه |
| XV-301/302/303 | 3 | شیر برقی و توپی موتوری DN20 | Belimo، ODE، Bürkert | |
| FQ-301/302/410 | 3 | کنتور آب با خروجی پالس | Zenner، Diehl Metering، B Meters؛ داخلی | |
| SOFT-1 | 1 | **سختی‌گیر دوقلوی متناوب** (twin alternating، meter-initiated)، ~۰.۵ m³/h، دو ستون رزین کاتیونی ۲۵ L، مخزن نمک ۱۰۰ L با LSL-403، صافی ۵۰ µm، خروجی سختی < ۱۰۰ ppm (ترجیحاً < ۱۷ ppm)، پساب احیا به فاضلاب (مجاز، تصمیم کاربر) | BWT (اتریش)، شیر کنترل Runxin / Canature (چین)؛ رزین Lanxess Lewatit (آلمان)، Thermax Tulsion (هند)؛ مونتاژکاران داخلی | داخل ساختمان؛ SOFT-1-FLT |
| RO-1 | 1 | RO **۴۰۰ L/h** permeate با ممبران **ULP** (~۰.۷ kWh/m³) روی آب سختی‌گیری‌شده (بازیافت ۰.۷۵)، پمپ VFD، کارتریج ۵ µm، مخزن blend ۵۰۰ L، TV-401. **اگر سازندهٔ چیلر ≥ ۲۰۰۰ µS/cm را بپذیرد، RO حذف می‌شود** (`03` §۳) | ممبران: Toray (ژاپن)، LG Chem (کره)، Vontron (چین)؛ اسکید: مونتاژکاران داخلی | بار قابل تعویق (MAX-POWER) |
| P-9 | 1 | بوستر طبقاتی ECM یا VFD با مخزن تحت فشار | Grundfos SCALA2 / CMBE، Wilo، DAB E.sybox | |
| EH-301, HT-1 | 1 + 30 m | هیتر حوضچه ۱.۵ kW با ترموستات؛ کابل self-regulating ۲۰ W/m با کنترلر، RCD ۳۰ mA | Eltherm (آلمان)، Heat Trace Ltd (انگلیس)؛ چینی | زمستان |
| backflow BA | 1 | backflow preventer نوع BA برای پرکن مدار بسته | Caleffi، SYR (Hans Sasserath) | |

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
| Δp هوا و گاز | 4–20 mA، 0–1 kPa / 0–500 Pa | Huba 699، Siemens QBM، Kalinsky |
| دبی‌سنج | الکترومغناطیسی DN50/DN100، 4–20 mA + Modbus | Endress+Hauser Promag، Siemens SITRANS FM، Krohne؛ چینی |
| کنتور انرژی حرارتی | HM-1، HM-2، HM-4، **HM-11/12، HM-21/22** (COP هر چیلر)، M-Bus | Kamstrup MULTICAL 603، Siemens Ultraheat T550، Danfoss Sonometer |
| کنتور برق | **EM-HVAC** (ورودی BOP-R، کلاس 0.5S) + **JT-191..196** (کنتور چندکاناله با CT شکاف‌دار) + JT-903/904 (داخل ساختمان)، Modbus RTU | Schneider PM5xxx / iEM، Janitza UMG، Carlo Gavazzi WM/EM؛ چینی (Acrel، Eastron SDM) |
| شیر staging آب خنک‌کن | MV-CH1C DN80، MV-CH2C DN65، پروانه‌ای موتوری on/off با end switch | Belimo، Siemens، Genebre |
| دما و رطوبت بیرون و ورودی برج | TT/MT-OA و **TT/MT-306** (ورودی برج)، 4–20 mA با radiation shield؛ **MT-501** (بعد از کویل) | Vaisala HMP110، E+E EE210، Rotronic |
| CO2 سالن | AT-H1، NDIR، Modbus | Vaisala GMW، E+E EE820، Sensirion-based |
| فلوسوئیچ | پدلی یا حرارتی، کنتاکت دوگانه | Kobold، Danfoss، Siemens |
| تابلوی BOP-R | IP55 با سایه‌بان و فن فیلتردار، MCB/MCCB، کنتاکتور، SPD، RCD، B6-R، منبع 24 V با باتری، کنتور EM-HVAC | Rittal یا تابلوساز داخلی؛ Schneider، ABB، Siemens، LS، Chint |

### ه) اطفای حریق (`08_fire_suppression.md`)

| تگ | تعداد | شرح و مشخصهٔ کلیدی | کاندیدها | نکته |
|---|---|---|---|---|
| FS-1A / FS-1B | 2 | سیلندر FK-5-1-12 جعبهٔ موتور (اصلی + رزرو)، هر کدام ≥ ۱.۵۲ kg در سیلندر ۸ L، N₂ ۲۵ bar، شیر با actuator سلونوئیدی + اهرم دستی، گیج + PSL-890A (و PSL-890C پیشنهادی)، شلنگ و check valve | **سیستم لیست‌شدهٔ کامل** (عامل، شیر، نازل، نرم‌افزار flow): Siemens Sinorix 1230، Minimax MX 1230 (آلمان)؛ سازندگان چینی دارای listing | عامل باید FK-5-1-12 لیست‌شده باشد (Novec متوقف شد) |
| FS-1 | 1 | کابینت سیلندرهای بام ۰.۶ × ۰.۴۵ × ۱.۴ m، گالوانیزه رنگ سفید، سایه‌بان، عایق ۲۵ mm، دریچهٔ تهویه، شیر lock-off با ZSC-899A، TE-499 | ساخت داخلی | ~۸۰ kg با سیلندرها |
| FS-2 | 1 | سیلندر ~۲۵ kg FK-5-1-12 اتاق برق (کلاس ۴۰ L)، بست دیواری، PSL-890B، LLI، شیر lock-off با ZSC-899B | مثل FS-1A | داخل ساختمان |
| لوله و اتصالات Z1 | ~۴ m | DN15، استیل 316 Sch80 یا گالوانیزهٔ Sch80، اتصالات لیست‌شده، بست لرزه‌ای | طبق سیستم لیست‌شده | از FS-1 تا سقف EP-1 |
| نازل Z1 | 2 | نازل ۱۸۰° برنجی/استیل، DN15 | طبق سیستم | ناحیهٔ داغ + ناحیهٔ قطار گاز |
| لوله و نازل Z2 | ~۶ m + 1 | DN25 + یک نازل ۳۶۰° | طبق سیستم | |
| PS-889A / B | 2 | سوئیچ فشار تأیید تخلیه | طبق سیستم | |
| HS-892..895 | 4 | شستی آزادسازی دستی (زرد) و abort (آبی) برای FZ1 و FZ2 | جزو FCP (docs/electrical) | فقط برای کامل‌بودن |
| FD-837 | 2 | دمپرهای آتش spring-close روی دهانه‌های تهویهٔ جعبه (K-VS) | پکیج موتور / docs/electrical | |
| XV-497 | 1 | دمپر موتوری spring-close روی کانال EF-E + ZSC-497 | Belimo | B6-E |
| دریچهٔ تخلیهٔ فشار | 1 | دیوار اتاق برق، دوجهته | طبق محاسبهٔ فروشنده | |
| خاموش‌کنندهٔ دستی | 3 | بام: CO2 ۵ kg + پودر ABC ۶ kg؛ اتاق برق: CO2 ۵ kg | تولیدکنندگان داخلی دارای استاندارد | |

## ۲. بار الکتریکی تجهیزات HVAC

خروجی `hvac_design.py`. ستون‌ها:

- **متصل:** توان نامی واحد در حال کار با حاشیه.
- **تابستان:** کار پیوسته در طراحی تابستان.
- **زمستان:** کار متوسط در زمستان.

| تگ | قلم | متصل kW | تابستان (BALANCED) kW | زمستان kW | تغذیه | برد |
|---|---|---|---|---|---|---|
| P-1A/B | HW primary pump, twin ECM | 0.32 | 0.20 | 0.20 | 1~230 V | B6-R |
| P-2A | HW pump CH-1, ECM const. flow | 0.53 | 0.35 | 0.00 | 1~230 V | B6-R |
| P-2B | HW pump CH-2, ECM const. flow | 0.30 | 0.20 | 0.00 | 1~230 V | B6-R |
| P-3 | DHW/heating branch pump | 0.11 | 0.02 | 0.07 | 1~230 V | B6-R |
| P-4A | CHW primary CH-1, ECM const. flow | 0.32 | 0.21 | 0.00 | 1~230 V | B6-R |
| P-4B | CHW primary CH-2, ECM const. flow | 0.18 | 0.12 | 0.00 | 1~230 V | B6-R |
| P-5A/B | CHW secondary twin ECM (dp control) | 0.53 | 0.31 | 0.13 | 1~230 V | B6-R |
| P-6A/B | condenser-water pump + VFD | 1.38 | 0.98 | 0.00 | 3~400 V | B6-R |
| CT-1 fan | tower EC/VFD fan | 1.50 | 0.20 | 0.00 | 3~400 V | B6-R |
| CH-1 | chiller controls/pumps (internal) | 0.21 | 0.21 | 0.00 | 1~230 V | B6-R |
| CH-2 | chiller controls/pumps (internal) | 0.05 | 0.05 | 0.00 | 1~230 V | B6-R |
| D-101 | exhaust diverter actuator (spring return) | 0.02 | 0.01 | 0.01 | 24 VAC from K-EX (SR1-O6) | B6-R/SR1 |
| WT-1 | dosing pumps x3 + conductivity controller + BD valve | 0.10 | 0.05 | 0.01 | 1~230 V | B6-R |
| F-SS | side-stream separator purge valve | 0.01 | 0.01 | 0.00 | 24 VDC | B6-R |
| RO-1 | softener + RO 400 L/h ULP (indoor), deferrable | 0.60 | 0.15 | 0.03 | 1~230 V | B6-E |
| P-9 | make-up / permeate booster to roof, deferrable | 0.37 | 0.04 | 0.02 | 1~230 V | B6-E |
| P-7 | DHW tank charging / circulation | 0.06 | 0.03 | 0.06 | 1~230 V | B6-E |
| EH-301 | tower basin heater (freeze, standby) | 1.50 | 0.00 | 0.05 | 1~230 V | B6-R |
| HT-1 | heat tracing make-up/CW lines 30 m x 20 W/m | 0.60 | 0.00 | 0.05 | 1~230 V | B6-R |
| BOP-R | roof BOP panel: B6-R, PSU, meters, panel fan | 0.08 | 0.08 | 0.06 | 1~230 V | B6-R |
| DC-1 | engine glycol dry cooler EC fans (fed from BOP-R, in engine P_aux) | 0.19 | 0.05 | 0.10 | 1~230 V | B4 (engine) |
| FCU-1..4 | hall fan coils 4 x 600 CFM (EC motors) | 0.20 | 0.18 | 0.08 | 1~230 V | building |
| ERV-1 | energy-recovery ventilator 500 m3/h, CO2 control | 0.18 | 0.15 | 0.10 | 1~230 V | building |
| FCU-E | electrical-room fan coil EC | 0.04 | 0.04 | 0.00 | 1~230 V | B6-E |
| AC-E | electrical-room DX split standby 12 kBTU/h | 1.50 | 0.00 | 0.30 | 1~230 V | B6-E |
| EF-E | battery/electrical-room exhaust fan | 0.03 | 0.03 | 0.03 | 1~230 V | B6-E |
| **جمع** | | **10.90** | **3.66** | **1.30** | | |

**خلاصه:**

- **مصرف داخلی پلانت در BALANCED** (بدون فن‌کویل‌ها و ERV سالن، و بدون DC-1 که بار خود موتور است): **3.03 kW** با بستهٔ rev B (سالن عایق، ۱۷.۸ kW؛ موتور as-built، docs/08). طرح اول (rev A): 5.25 kW. زمستان 0.95 kW. انرژی سالانهٔ HVAC ~22 MWh (کار ۲۴ ساعته).
- **برق خالص تابستان در BALANCED: ~19.3 kW** (rev A: 17.1 kW؛ docs/03: ۲۱.۰ kW با فرض ۱.۳ kW برای پمپ‌ها و فن برج). سالن در BALANCED ۹.۹ از ۱۷.۸ kW.
  - در MAX-POWER **۲۰.۲ kW** و در MAX-COOLING (سالن کامل) ۱۶.۷ kW (`07_power_modes.md`).
  - بزرگ‌ترین قلم هنوز P-6 است (۰.۹۸ kW)، بعد P-2A و P-5.
- **سود مقابل:** سرمای ساختمان (12.4 kW در BALANCED، سالن + اتاق برق) ~4.8 kW برق کولرهای گازی را حذف می‌کند (COP ۲.۶).
- **اندازه‌گیری:** EM-HVAC، JT-191 تا JT-196 و JT-903/904 مصرف واقعی هر گروه را به ECU می‌دهند (Modbus TCP، B1 client؛ CONTRACT v3). پیش‌بینی هر حالت با آن‌ها کالیبره می‌شود.

**تغذیه:**

- **تابلوی BOP-R** از خروجی سه‌فاز ۴۰۰ V اینورتر تغذیه می‌شود.
  - بار متصل ~۱۱ kW، یعنی ~۱۸ A با PF ۰.۹. جریان کار تابستان (BALANCED) ~۶ A.
  - **فیدر ۴ × ۱۰ mm² مس + ارت با MCCB ۳۲ A** (جا برای توسعه و هارمونیک VFD).
  - دو بخش: **ضروری** (B6، چیلرها، P-1، P-4، P-6، فن برج، D-101) و **غیرضروری** (هیترها، heat tracing).
  - SPD نوع 2. RCD ۳۰ mA برای هیترها و پریزها.
- **بارهای B6-E** (RO، P-9، P-7، FCU-E، AC-E، EF-E) از تابلوی ۲۳۰ V اتاق برق تغذیه می‌شوند.
- **جریان راه‌اندازی:** همهٔ پمپ‌ها ECM یا VFD با استارت نرم‌اند، پس جریان راه‌اندازی بزرگ به اینورتر تحمیل نمی‌شود (docs/03 §۲). AC-E اینورتری است.
