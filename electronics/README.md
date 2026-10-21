# GR180-CCHP — electronics (KiCad)

وضعیت: **اسکلت (rev 0.1، ۲۰۲۶-۱۰-۲۱)**. معماری و دلیل هر انتخاب در [`docs/electrical/`](../docs/electrical/00_electrical_control_architecture.md) آمده است.

## `ecu/` — برد B1 ECU (اتاق برق)

پروژهٔ KiCad 10، سلسله‌مراتبی. باز کردن: `ecu/gr180_ecu.kicad_pro`.

| شیت | فایل | محتوای فعلی | منبع طراحی |
|---|---|---|---|
| Power | `power.kicad_sch` | TPS54360 (24→5 V)، دو TLV75533 (+3V3 ECU و +3V3_SMCU جدا) | 04 §۱ |
| MCU_Main | `mcu_main.kicad_sch` | **STM32H743IIT6** (LQFP-176)، W25Q128JV (event recorder)، FM25V10 (life counter) | 03 §۱۰، §۱۱ |
| Safety_MCU | `safety_mcu.kicad_sch` | STM32G431RBT6 (جای dsPIC33CK256MP506، معماری متنوع)، FM25V10، STWD100 | 03 §۸ |
| CAN_FD | `can_fd.kicad_sch` | 3× ISO1042 (موتور، BOP، BMS) + MCP2518FD برای CAN سوم | 00 §۴ |
| Comms_RS485_ETH | `comms.kicad_sch` | 2× ADM2587E، LAN8742A | 00 §۴ |
| Speed_Inputs | `speed_inputs.kicad_sch` | 2× AM26LV32 (یکی برای ECU، یکی برای SMCU) | 03 §۸، 05 W102a/b |
| Digital_IO | `digital_io.kicad_sch` | 12× ISO1212 (24 DI)، 2× ULN2003A (12 رله) | 02 بودجهٔ کانال |
| Field_Connectors | `connectors.kicad_sch` | J801–J811 (Phoenix MSTB 5.08 / MC 3.81) | 05 |

**قراردادها:**
- شیت‌ها در شیت اصلی با برچسب‌های هم‌نام به هم وصل‌اند. هر شیت فرزند hierarchical label‌های متناظر را دارد.
- هر IC فیلدهای `MPN` و `LCSC` دارد. شماره‌ها در ۲۰۲۶-۱۰-۲۱ از JLCPCB استعلام شده‌اند.
- کتابخانهٔ نماد پروژه: `ecu/symbols/gr180.kicad_sym` (ISO1042BQDWV، FM25V10-G، STWD100NYWY3F)، ثبت‌شده در `sym-lib-table`. **pinout نماد STWD100 باید با datasheet چک شود.**
- روی هر شیت یک یادداشت «TO COMPLETE» هست که مدارهای باقی‌مانده را فهرست می‌کند.

**ERC:**
- ERC اجرا می‌شود و فایل‌ها بدون خطای ساختاری باز می‌شوند.
- خطاهای فعلی (~۱۲۰۰ مورد) همه از نوع اسکلت‌اند:
  - پایه‌های IC هنوز سیم‌کشی نشده‌اند (`pin_not_connected`، `power_pin_not_driven`).
  - برچسب‌هایی که هنوز به پایهٔ واقعی نرسیده‌اند (`label_dangling`).
- با تکمیل هر شیت باید به صفر برسند.

**کارهای بعدی:**
1. سیم‌کشی کامل شیت‌ها: دکاپلینگ، کریستال‌ها، SWD، دامنه‌های ایزوله با B0505S، حفاظت ورودی 24 V، رله‌های G7SA برای permitها و رله‌های G5Q.
2. تخصیص پایه‌های STM32H743IIT6 با STM32CubeMX:
   - FDCAN1/2
   - SPI4 (MCP2518FD)
   - SPI (FRAM)
   - QUADSPI
   - USART×2 با DE
   - RMII
   - TIM capture برای ورودی‌های سرعت
   - GPIO برای DI و RO
3. PCB: ۴ لایه، فاصله‌های خزشی (creepage) ایزولاسیون طبق IEC 60664 (≥ 8 mm بین دامنهٔ میدان و منطق)، conformal coating طبق IPC-CC-830 با نواحی ماسک برای کانکتورها.
4. سپس بردهای B2 (I/O سنسور)، B4 (درایورها) و B3 (یکسوساز SiC؛ با بازبینی متخصص قدرت).

> پروژه با KiCad MCP در `~/Documents/KiCad-Projects/gr180_ecu/` ساخته شد (MCP فقط در آن پوشه می‌نویسد) و نسخهٔ کامل اینجا کپی شده است. **مرجع اصلی همین پوشهٔ `electronics/ecu/` است.**
