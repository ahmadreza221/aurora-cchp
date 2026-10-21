# GR180-CCHP — P&ID و دیاگرام جریان مدارهای آب (HVAC / Balance of Plant)

تاریخ: ۲۰۲۶-۱۰-۲۱ · مبنای اعداد: `sim/hvac/hvac_design.py` (خروجی در `sim/hvac/hvac_results.json`) · شمارهٔ تگ‌ها با `docs/hvac/io_list.csv` یکی است.

> این سند P&ID مفهومی (conceptual) است، برای طراحی پایه و استعلام. نقشهٔ P&ID اجرایی (ISA 5.1، با سایز تک‌تک شیرها و spec breaks) باید بعد از دریافت دیتاشیت قطعی چیلرها و برج تهیه شود.

## ۰. نمای کلی (block flow)

```mermaid
flowchart LR
  ENG["EP-1 GR180 + FPT + PMG<br/>recuperator eps 0.90"]
  D101{"D-801<br/>diverter"}
  HX1["HX-1 exhaust/water HX<br/>~69 kW"]
  ST1(["ST-1 stack"])
  LLH["LLH-1 HW header"]
  CH["CH-1 SC10 + CH-2 SC5<br/>LiBr single-effect"]
  DHW["DHW + winter heating<br/>HX-2, HX-3"]
  TK1["TK-1 CHW buffer 500 L"]
  CC1["CC-1 engine intake coil<br/>17-19 kW"]
  FCU["hall FCU-1..4<br/>18-24 kW"]
  FCUE["electrical room FCU-E<br/>2.5 kW"]
  CT1["CT-1 cooling tower<br/>40 ton class, 109 kW"]
  WT["make-up RO blend<br/>dosing + blowdown"]
  ENG -->|"exhaust 0.40 kg/s, 262-290 C"| D101
  D101 -->|"HX path"| HX1
  D101 -->|"bypass"| ST1
  HX1 -->|"96-100 C"| ST1
  HX1 ==>|"HW 90/83 C, 8.8 m3/h"| LLH
  LLH ==> CH
  LLH ==> DHW
  CH -->|"CHW 7/12 C, 42 kW"| TK1
  TK1 --> CC1
  TK1 --> FCU
  TK1 --> FCUE
  CH -->|"CW 32/35.4 C, 27.5 m3/h"| CT1
  WT --> CT1
  CC1 -.->|"intake air 46 -> 15 C"| ENG
```

**منطق کلی:** گرمای اگزوز بعد از recuperator (۲۶۲ °C در طراحی تابستان، ۲۹۰ °C بدون کویل ورودی) در HX-1 به آب داغ ۹۰/۸۳ °C داده می‌شود. آب داغ از یک **low-loss header** (LLH-1) به دو چیلر جذبی و شاخهٔ DHW/گرمایش می‌رود. آب سرد ۷/۱۲ °C در مخزن بافر TK-1 جمع می‌شود و سه مصرف‌کننده دارد: کویل ورودی هوای موتور، فن‌کویل‌های سالن و فن‌کویل اتاق برق. گرمای دفع‌شدهٔ چیلرها (~۱۰۹ kW) به برج خنک‌کن می‌رود. **damper دوراهی D-801** تضمین می‌کند موتور هیچ‌وقت به چیلر وابسته نباشد.

## ۱. اگزوز، مدار آب داغ، DHW و گرمایش زمستان

```mermaid
flowchart TB
  subgraph EX["Exhaust side, 316L"]
    ENG["EP-1 engine package<br/>TE-106, PT-205"]
    D101{"D-801 diverter damper<br/>ZC-801 / ZT-801 / ZSO-801<br/>spring-return to BYPASS"}
    HX1["HX-1 finned-tube economiser<br/>8 tubes x 15 rows, 42 m2<br/>PDT-1102, TE-107"]
    BYP["bypass duct DN250"]
    ST1(["ST-1 stack DN250 double wall<br/>top +4.0 m, TE-1103"])
    NP["condensate neutraliser pot"]
    ENG -->|"DN250 hot duct, insulated"| D101
    D101 -->|"HX path"| HX1
    D101 -->|"bypass"| BYP
    HX1 --> ST1
    BYP --> ST1
    HX1 -.->|"start-up condensate"| NP
  end
  subgraph HWP["HW primary 90/83 C, constant 8.8 m3/h"]
    SAF["TE-1111, TSHH-1111 98 C<br/>PSH-1111 5.0 bar, PSV-1111 5.5 bar"]
    AS1["AS-1 air + dirt + magnetic separator"]
    LLH["LLH-1 low-loss header / buffer 200 L<br/>TE-1113, TE-1114"]
    P1["P-1A/B twin ECM<br/>FT-1111, FSL-1111"]
    ET1["ET-1 35 L + intermediate vessel"]
    FILL["closed-loop fill: RO water<br/>BA backflow preventer<br/>XV-1410, FQ-1410, dosing pot"]
    SAF ==> AS1 ==> LLH
    LLH ==>|"HWR 83 C"| P1
    ET1 --- P1
    FILL --- P1
  end
  subgraph HWS["HW secondary"]
    P2A["P-2A 8.64 m3/h"]
    G1["CH-1 generator SC10 class"]
    P2B["P-2B 4.32 m3/h"]
    G2["CH-2 generator SC5 class"]
    P3["P-3 1.3 m3/h"]
    TV131{"TV-1131 3-way<br/>temperature limiter"}
    VPRI{"V-PRI<br/>DHW priority valve"}
    HX2["HX-2 double-wall PHE 30 kW<br/>DHW charging"]
    HX3["HX-3 heating PHE 15 kW<br/>TV-1231, TE-1231"]
    P2A ==> G1
    P2B ==> G2
    P3 ==> TV131 ==> VPRI
    VPRI ==>|"DHW first"| HX2
    VPRI ==>|"winter heating"| HX3
  end
  DHW["TK-DHW 500 L, indoor<br/>P-7, TE-1132/1133<br/>legionella 65 C weekly, TMV 50 C"]
  CHWNET["CHW distribution header<br/>winter changeover V-CO1/V-CO2"]
  HX1 ==>|"HWS 90 C"| SAF
  P1 ==>|"TE-1112, PT-1111"| HX1
  LLH ==> P2A
  LLH ==> P2B
  LLH ==> P3
  G1 ==> LLH
  G2 ==> LLH
  HX2 ==> LLH
  HX3 ==> LLH
  HX2 -->|"DHW 60-65 C"| DHW
  HX3 -->|"heating 45/40 C"| CHWNET
```

نکات کلیدی:

- **D-801** یک diverter تک‌تیغه است، یعنی هیچ‌وقت هر دو مسیر هم‌زمان بسته نمی‌شوند. actuator آن **spring-return به حالت BYPASS** است. فرمان مدوله از B4 می‌آید (ZC-801، مالک ECU؛ docs/electrical). تغذیهٔ 24 VAC آن یک زنجیرهٔ سخت‌افزاری است (خروجی ایمن SR1 در سری با کنتاکت‌های حفاظتی). با هر کدام از این موارد تغذیه قطع می‌شود و damper ظرف ۱۵ ثانیه به bypass برمی‌گردد:
  - TSHH-1111 (۹۸ °C)
  - PSH-1111
  - FSL-1111 (قطع جریان)
  - E-stop
  - trip موتور
- **HX-1** عمودی (up-flow) است و دودکش مستقیم روی آن نصب می‌شود. bypass بالای HX به همان دودکش می‌پیوندد. در کف ورودی یک تخلیهٔ کندانس با pot خنثی‌کننده (سنگ آهک/MgO) هست. کندانس فقط در start-up سرد پیش می‌آید، چون نقطهٔ شبنم آب اگزوز ~۲۸ °C است.
- **PSV-1111** (DN20، تنظیم ۵.۵ bar) روی خروجی HX-1 و قبل از هر شیر قطع نصب می‌شود. ظرفیت بخار آن باید ≥ ۱۲۰ kg/h باشد (حالت خشک‌شدن مبدل با ۷۲ kW)، با لولهٔ تخلیه به نقطهٔ امن.
- **LLH-1** مدار اولیه (دبی ثابت HX) را از مدار ثانویه (چیلرها با دبی نامی‌شان، و شاخهٔ DHW) جدا می‌کند:
  - دبی ثانویه (۱۳.۰ m³/h) از دبی اولیه (۸.۸ m³/h) بیشتر است، پس چیلرها آب ~۸۷.۹ °C می‌گیرند (≈ ۸۸ °C نامی).
  - HX-1 آب برگشت ۸۳ °C می‌گیرد. این برای approach سرد مبدل و فاصله از نقطهٔ شبنم اسیدی (۶۰–۷۸ °C) خوب است.
- **V-PRI** شیر سه‌راههٔ اولویت است:
  - وقتی TE-1132 < SP، کل جریان شاخه به DHW می‌رود.
  - در غیر این صورت، در زمستان به گرمایش می‌رود.
  - در تابستان، شاخه فقط وقتی فعال است که چیلرها گرما را کامل مصرف نکنند (TE-1111 > ۹۲ °C یا damper در حال bypass)، یا DHW زیر حداقل باشد.
- **HX-2** صفحه‌ای **دوجداره (double-wall، با درز نشت قابل‌مشاهده)** است، چون مدار آب داغ ماده بازدارنده دارد و آب مصرفی بهداشتی است.

## ۲. مدار آب سرد (۷/۱۲ °C) و changeover زمستان

```mermaid
flowchart TB
  subgraph PRI["CHW primary, constant flow at chiller rating"]
    TK1["TK-1 buffer / decoupler 500 L<br/>TE-1211 top, TE-1212 bottom"]
    P4A["P-4A 5.5 m3/h"]
    E1["CH-1 evaporator<br/>FS-1201, TE-1201"]
    MV1["MV-CH1E isolation"]
    P4B["P-4B 2.8 m3/h"]
    E2["CH-2 evaporator<br/>FS-1202, TE-1202"]
    MV2["MV-CH2E isolation"]
    P4A --> E1 --> MV1
    P4B --> E2 --> MV2
  end
  subgraph SEC["CHW secondary, variable flow up to 7.8 m3/h"]
    VCO1{"V-CO1 summer/winter"}
    P5["P-5A/B twin ECM, dp control<br/>PT-1211, FT-1211"]
    AS2["AS-2 air + dirt separator<br/>on warm return"]
    ET2["ET-2 25 L at P-5 suction"]
    HDR["CHW supply header"]
    CC1["CC-1 engine intake coil, 8 rows<br/>TV-1221 PICV, TE-1221 air 15 C<br/>TE-1222, LSH-1221"]
    HALL["hall FCU-1..4, 800 CFM class<br/>PICV + Modbus room controllers<br/>DPT-1211 at riser foot"]
    FCUE["FCU-E electrical room<br/>2-way valve, LD-E leak cable"]
    RET["CHW return header<br/>TE-1213, HM-2, HM-4"]
    VCO2{"V-CO2 summer/winter"}
    VCO1 --> P5 --> HDR
    ET2 --- P5
    HDR -->|"3.2 m3/h DN40"| CC1
    HDR -->|"4.1 m3/h DN40, roof 6 m + riser 3.5 m"| HALL
    HDR -->|"0.5 m3/h DN20"| FCUE
    CC1 --> RET
    HALL --> RET
    FCUE --> RET
    RET --> AS2 --> VCO2
  end
  HX3["HX-3 heating PHE (winter)"]
  BASIN["CT-1 basin, low-TDS make-up"]
  DRAIN["building drain"]
  ACE["AC-E DX split 12 kBTU/h<br/>automatic standby"]
  TK1 -->|"bottom 12 C"| P4A
  TK1 -->|"bottom 12 C"| P4B
  MV1 -->|"7 C"| TK1
  MV2 -->|"7 C"| TK1
  TK1 -->|"top 7 C, summer"| VCO1
  HX3 -.->|"winter 45 C"| VCO1
  VCO2 -->|"summer"| TK1
  VCO2 -.->|"winter"| HX3
  CC1 -.->|"condensate ~8 L/h"| BASIN
  HALL -.->|"condensate ~5 L/h"| DRAIN
  ACE -.- FCUE
```

نکات کلیدی:

- چیلرهای جذبی کوچک **دبی آب سرد ثابت** (نامی) می‌خواهند، پس مدار اولیه دبی ثابت دارد.
  - هر چیلر پمپ خودش را دارد (P-4A/B). وقتی یک چیلر خاموش است، از آن جریانی رد نمی‌شود.
  - TK-1 هم decoupler است و هم ذخیرهٔ سرما. ۵۰۰ L با ΔT ۵ K حدود ۲.۹ kWh ذخیره دارد، یعنی ~۱۰ دقیقه کویل ورودی بعد از trip یا در restart.
- مدار ثانویه **دبی متغیر** دارد. مصرف‌کننده‌ها شیر دوراههٔ PICV دارند و P-5 دورش را روی Δp انتهای رایزر سالن (DPT-1211) تنظیم می‌کند. حداقل دبی پمپ را خود ECM حفظ می‌کند، یا یک by-pass کوچک با شیر Δp در انتهای خط.
- **ترتیب changeover:**
  - در زمستان چیلرها خاموش‌اند و MV-CH1E/MV-CH2E بسته‌اند (end switch در اینترلاک).
  - V-CO1/V-CO2 مکش و برگشت P-5 را از TK-1 به HX-3 می‌برند.
  - **قاعدهٔ ایمنی:** تا وقتی end switch هر دو MV بسته را تأیید نکرده، V-CO به حالت زمستان نمی‌رود. این برای جلوگیری از ورود آب داغ به اواپراتور LiBr است.
- **کندانس کویل ورودی** (~۸ L/h در WB ۲۸ °C) تقریباً بدون املاح است و با شیب به حوضچهٔ برج می‌رود (make-up رایگان کم‌TDS). کندانس فن‌کویل‌های سالن به فاضلاب ساختمان می‌رود، با تله (P-trap).
- **اتاق برق:** FCU-E خنک‌کن اصلی است. یک اسپلیت DX 12 kBTU/h از نوع T3 پشتیبان خودکار است، برای زمستان (حالت گرمایش شبکه)، استارت، و خرابی چیلر.

## ۳. مدار آب خنک‌کن، برج، آب جبرانی، blowdown و تصفیه

```mermaid
flowchart TB
  subgraph CW["Condenser water, open loop 27.5 m3/h, 32 to 35.4 C"]
    CT1["CT-1 FRP counterflow tower, 40 ton class<br/>VFD fan, VS-1301, drift max 0.002 %<br/>LT-1301, LSLL-1301, TE-1303, EH-1301"]
    BS["basket strainer DN100"]
    P6["P-6A/B duty/standby + VFD<br/>FT-1301"]
    A1["CH-1 absorber + condenser<br/>18.4 m3/h, FS-1301, TE-1203"]
    A2["CH-2 absorber + condenser<br/>9.2 m3/h, FS-1302, TE-1204"]
    TV301{"TV-1301 3-way tower bypass"}
    BS --> P6
    P6 --> A1
    P6 --> A2
    A1 --> TV301
    A2 --> TV301
  end
  subgraph AUX["Engine aux glycol loop interface, docs/electrical 5xx"]
    HX4["HX-4 glycol / CW brazed PHE<br/>3.5 kW, glycol 40 to 35 C"]
    XV1305["XV-1305 NO valve<br/>1.0 m3/h CW"]
    DC1["DC-1 dry cooler, EC fans<br/>winter and backup"]
    GLY["M-501 glycol pump, PMG + B3 + oil cooler<br/>TE-503 / TE-504 on B2"]
    GLY --> DC1 --> HX4 --> GLY
  end
  subgraph WT["Treatment, roof skid WT-1"]
    SEP["F-SS centrifugal separator<br/>XV-1303 purge"]
    SMP["sample cell<br/>AIT-1301 EC, AIT-1302 ORP, AIT-1303 pH"]
    XV302["XV-1302 blowdown + FQ-1302"]
    DP1["DP-1 inhibitor, prop. to FQ-1301"]
    DP2["DP-2 oxidising biocide, on ORP"]
    DP3["DP-3 non-oxidising biocide, weekly"]
    SEP --> SMP --> XV302
  end
  subgraph MU["Make-up, indoor water room + riser"]
    CITY["city water tank, TDS 400 ppm<br/>LSL-1400"]
    F5["5 um cartridge + antiscalant"]
    RO["RO-1 300 L/h<br/>AIT-1401"]
    BT["TK-1401 blend tank<br/>AIT-1402, LT-1401, TV-1401"]
    P9["P-9 booster to roof"]
    FQ301["FQ-1301 make-up meter"]
    XV301["XV-1301 + mechanical float"]
    CITY --> F5 --> RO -->|"permeate"| BT
    CITY -->|"TV-1401 blend"| BT
    BT --> P9 -->|"heat-traced on roof"| FQ301 --> XV301
  end
  DRN["drain"]
  FILL2["closed-loop fill unit<br/>HW + CHW loops"]
  CT1 -->|"TE-1301"| BS
  TV301 -->|"TE-1302 to spray"| CT1
  TV301 -.->|"bypass to basin"| CT1
  P6 -->|"side-stream ~2.2 m3/h"| SEP
  P6 --> XV1305 --> HX4
  HX4 -->|"CW return"| TV301
  SEP --> CT1
  XV302 --> DRN
  DP1 --> CT1
  DP2 --> CT1
  DP3 --> CT1
  XV301 --> CT1
  RO -.->|"reject, reuse for WC or irrigation"| DRN
  RO -->|"pure permeate"| FILL2
```

نکات کلیدی:

- **برج:** counterflow، FRP گرد، فن VFD. حذف‌کنندهٔ قطره (drift eliminator) ≤ ۰.۰۰۲ ٪. حوضچه سرپوشیده و سایه‌دار، با کف شیب‌دار و تخلیهٔ کامل.
  - TV-1301 در start-up و زمستان آب را مستقیم به حوضچه برمی‌گرداند تا دمای آب خنک‌کن از حداقل مجاز چیلر (~۲۶ °C، طبق دیتاشیت) پایین‌تر نرود.
- **HX-4 (رابط مدار کمکی موتور):**
  - مدار گلیکول ژنراتور، یکسوساز و خنک‌کن روغن (پمپ M-501 و سنسورها در docs/electrical) باید ~۳۵–۴۰ °C بماند (آلارم بالای ۵۰ °C).
  - در هوای ۴۶ °C یک dry cooler به‌تنهایی این را نمی‌دهد. پس در تابستان ~۳.۵ kW از یک PHE کوچک (HX-4) به آب خنک‌کن داده می‌شود: ۱.۰ m³/h. با آن برج ۱۱۲ kW می‌شود و آب سرد برج ۳۱.۶ °C، پس انتخاب برج عوض نمی‌شود.
  - در زمستان (برج خاموش) و در خرابی برج، DC-1 کار را می‌کند.
  - XV-1305 از نوع normally-open است. با قطع برق یا ارتباط، باز می‌ماند و DC-1 روی ۱۰۰ ٪ می‌رود.
- **side-stream** (~۸ ٪ جریان) از جداکنندهٔ گریز از مرکز رد می‌شود. این برای گرد و خاک برازجان است. purge آن جزئی از blowdown حساب می‌شود.
  - سنسورهای کیفیت آب در همین مسیر نمونه نصب می‌شوند، که جریانشان پیوسته و تمیز است.
- **آب جبرانی:**
  - توصیه: **blend آب RO و آب شهری** تا هدایت آب جبرانی ~۲۳۰ µS/cm شود. با ۳.۵ سیکل، آب در گردش ≤ ۸۰۰ µS/cm می‌ماند (حد رایج سازندهٔ چیلر). جزئیات در `03_water_treatment.md`.
  - شیر شناور مکانیکی پشتیبان شیر برقی است.
- **پرکن مدارهای بسته** فقط با آب RO انجام می‌شود، از مسیر backflow preventer نوع BA. کنتور پرکن FQ-1410 نشتی مدار بسته را نشان می‌دهد (حد ۲۰ L/day).

## ۴. فهرست خطوط (line list) — نتیجهٔ `hvac_design.py`

معیار سایز: افت فشار R ≤ ۲۵۰ Pa/m (به‌خاطر کار ۲۴/۷). سرعت ≤ ۱.۲ m/s تا DN50 و ≤ ۱.۸ m/s بالاتر. لوله Sch40. ضریب ۱.۵ برای اتصالات.

| خط | سرویس | دبی m³/h | DN | v m/s | R Pa/m | طول یک‌طرفه m | جنس / عایق |
|---|---|---|---|---|---|---|---|
| L-HW-01 | آب داغ اولیه HX-1 ↔ LLH-1 | 8.8 | 50 | 1.13 | 244 | 6 | A106 Gr.B Sch40 جوشی، پشم سنگ ۵۰ mm + روکش آلومینیوم |
| L-HW-02 | هدر LLH-1 → چیلرها | 13.0 | 65 | 1.17 | 209 | 2 | همان |
| L-HW-03 | شاخهٔ CH-1 (P-2A) | 8.64 | 50 | 1.11 | 236 | 4 | همان |
| L-HW-04 | شاخهٔ CH-2 (P-2B) | 4.32 | 40 | 0.91 | 222 | 4 | همان |
| L-HW-05 | شاخهٔ DHW/گرمایش تا مخزن داخل ساختمان | 1.3 | 25 | 0.64 | 198 | 15 | همان |
| L-CH-01 | آب سرد اولیه CH-1 ↔ TK-1 | 5.47 | 50 | 0.70 | 122 | 5 | A53/A106 Sch40، الاستومری ۴۰ mm + روکش (بام) |
| L-CH-02 | آب سرد اولیه CH-2 ↔ TK-1 | 2.77 | 40 | 0.59 | 121 | 5 | همان |
| L-CH-03 | ثانویه TK-1 → هدر (P-5) | 7.8 | 50 | 1.00 | 233 | 3 | همان |
| L-CH-04 | شاخهٔ کویل ورودی CC-1 | 3.2 | 40 | 0.68 | 157 | 5 | همان |
| L-CH-05 | اصلی سالن: ۶ m روی بام + رایزر ۳.۵ m | 4.1 | 40 | 0.86 | 244 | 9.5 | همان؛ داخل رایزر ۲۵ mm |
| L-CH-06 | توزیع سالن، ۲ فن‌کویل | 2.0 | 32 | 0.59 | 147 | 9 | فولاد یا PP-R PN20، الاستومری ۱۹ mm |
| L-CH-07 | توزیع سالن، آخرین فن‌کویل | 1.0 | 25 | 0.51 | 163 | 7 | همان |
| L-CH-08 | شاخهٔ اتاق برق (طول فرضی) | 0.5 | 20 | 0.41 | 150 | 15 | همان؛ **از بالای تجهیزات برقی رد نشود** |
| L-CW-01 | آب خنک‌کن برج ↔ هدر چیلرها | 27.5 | 100 | 0.93 | 82 | 8 | 316L Sch10S (ترجیح) یا PE100 SDR11 مشکی UV-stable |
| L-CW-02 | شاخهٔ CH-1 | 18.4 | 80 | 1.07 | 149 | 3 | همان |
| L-CW-03 | شاخهٔ CH-2 | 9.2 | 65 | 0.83 | 120 | 3 | همان |
| L-CW-04 | side-stream | 2.2 | 32 | 0.63 | 152 | 3 | 316L / PP |
| L-MU-01 | آب جبرانی blend از داخل ساختمان | 0.5 | 20 | 0.40 | 136 | 20 | PP-R PN20، heat tracing + عایق ۲۵ mm روی بام |

## ۵. راهنمای تگ‌ها

| پیشوند | معنی |
|---|---|
| HX | مبدل حرارتی (HX-1 اگزوز/آب، HX-2 DHW دوجداره، HX-3 گرمایش) |
| CH / CT / CC / FCU | چیلر جذبی / برج خنک‌کن / کویل آب سرد ورودی موتور / فن‌کویل |
| P / ET / AS / LLH / TK | پمپ / منبع انبساط / جداکنندهٔ هوا و لجن / هدر کم‌افت / مخزن |
| D / TV / MV / V / XV / PSV | damper / شیر کنترلی / شیر قطع موتوری / شیر changeover یا priority / شیر برقی on-off / شیر اطمینان |
| TE, PT, PDT, DPT, FT, FS, LT, LS, AIT, FQ, ZT, ZS | دما، فشار، اختلاف فشار هوا/گاز، اختلاف فشار آب، دبی، فلوسوئیچ، سطح، سوئیچ سطح، آنالایزر (EC، ORP، pH)، کنتور حجمی، موقعیت، limit switch |
| HM | کنتور انرژی حرارتی (M-Bus) |
| H / HH / L / LL | حد آلارم بالا / trip بالا / پایین / trip پایین |

جدول کامل I/O با رنج و برد در `05_controls_io.md` و `io_list.csv` است.
