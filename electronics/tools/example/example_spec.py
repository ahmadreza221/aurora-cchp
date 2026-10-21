# -*- coding: utf-8 -*-
"""
schgen worked example - a small but realistic CAN-FD node:

  24 V terminal -> reverse-polarity Schottky -> TVS -> LMR16006 buck (5 V)
  -> LD1117S33 LDO (3V3) -> STM32G474RET6 (8 MHz HSE, SWD, NRST button, BOOT0)
  -> TJA1051T/3 CAN-FD transceiver with split termination + NUP2105L ESD
  -> M12 CANopen field connector (generated symbol, no stock KiCad symbol)
  24 V monitor: divider + MCP6002 buffer (multi-unit symbol, unit B tied off).

Build + validate:
    python3 electronics/tools/schgen.py build electronics/tools/example/example_spec.py \
            --out electronics/tools/example/out
"""
from schgen import Board, Sheet, P, R, C, L, D, G

# ---------------------------------------------------------------------------
# Generated symbol: M12 A-coded 5-pin CANopen/DeviceNet connector (CiA 303-1)
# ---------------------------------------------------------------------------
M12_CAN = G('M12_A5_CANopen',
            pins=[('1', 'SHLD', 'passive', 'L'),
                  ('2', 'CAN_V+', 'passive', 'L'),
                  ('3', 'CAN_GND', 'passive', 'L'),
                  ('4', 'CAN_H', 'passive', 'L'),
                  ('5', 'CAN_L', 'passive', 'L')],
            ref='J', footprint='',
            description='M12 A-coded 5-pin male panel connector, CiA 303-1 CANopen pinout')

# ---------------------------------------------------------------------------
# Sheet 1: Power
# ---------------------------------------------------------------------------
power = [
    P('J1', 'Connector:Screw_Terminal_01x02', '24V IN',
      'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
      pins={'1': 'VIN_RAW', '2': 'GND'}, mpn='1715721', mfr='Phoenix Contact'),
    D('D1', 'B260A', 'SMA', k='+24V', a='VIN_RAW', kind='D_Schottky',
      mpn='B260A-13-F', mfr='Diodes Inc', lcsc='C79932'),
    D('D2', 'SMBJ33CA', 'SMB', k='+24V', a='GND', kind='D_TVS',
      mpn='SMBJ33CA', mfr='Littelfuse'),
    C('C1', '2.2u/50V', '1206', a='+24V', b='GND', mpn='GRM31CR71H225KA88L', mfr='Murata'),
    C('C2', '100n/50V', '0603', a='+24V', b='GND', mpn='GCM188R71H104KA57D', mfr='Murata'),
    R('R1', '100k', a='+24V', b='BUCK_EN'),
    P('U3', 'Regulator_Switching:LMR16006YQ5', 'LMR16006YQ5',
      pins={'VIN': '+24V', '~{SHDN}': 'BUCK_EN', 'GND': 'GND', 'CB': 'BUCK_CB',
            'SW': 'BUCK_SW', 'FB': '+5V'},
      mpn='LMR16006YQ5DDCRQ1', mfr='Texas Instruments'),
    C('C3', '100n', '0402', a='BUCK_CB', b='BUCK_SW'),
    D('D3', 'B160', 'SMA', k='BUCK_SW', a='GND', kind='D_Schottky', mpn='B160-13-F', mfr='Diodes Inc'),
    L('L1', '22u', footprint='Inductor_SMD:L_Taiyo-Yuden_NR-40xx', a='BUCK_SW', b='+5V',
      mpn='NR4018T220M', mfr='Taiyo Yuden'),
    C('C4', '22u/10V', '0805', a='+5V', b='GND'),
    C('C5', '10u/10V', '0805', a='+5V', b='GND'),
    P('U2', 'Regulator_Linear:LD1117S33TR_SOT223', 'LD1117S33',
      pins={'VI': '+5V', 'VO': '+3V3', 'GND': 'GND'},
      mpn='LD1117S33TR', mfr='STMicroelectronics', lcsc='C86781'),
    C('C6', '10u/10V', '0805', a='+3V3', b='GND'),
    R('R2', '1k', a='+3V3', b='LED_PWR'),
    D('D4', 'green', '0603', k='GND', a='LED_PWR', kind='LED'),
    # 24 V monitor: 100k/10k divider + buffer -> MCU ADC
    R('R8', '100k', '0603', a='+24V', b='V24_DIV'),
    R('R9', '10k', a='V24_DIV', b='GND'),
    C('C24', '100n', a='V24_DIV', b='GND'),
    P('U5', 'Amplifier_Operational:MCP6002-xSN', 'MCP6002',
      'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
      pins={'1': 'V24_SENSE', '2': 'V24_SENSE', '3': 'V24_DIV',      # unit A: buffer
            '5': 'GND', '6': 'OPB_FB', '7': 'OPB_FB',                 # unit B: unused, tied off
            'V+': '+3V3', 'V-': 'GND'},                               # unit C: power
      mpn='MCP6002T-I/SN', mfr='Microchip'),
    C('C25', '100n', a='+3V3', b='GND'),
]

# ---------------------------------------------------------------------------
# Sheet 2: MCU
# ---------------------------------------------------------------------------
mcu = [
    P('U1', 'MCU_ST_STM32G4:STM32G474RETx', 'STM32G474RET6',
      pins={'VDD': '+3V3', 'VBAT': '+3V3', 'VSS': 'GND',
            'VDDA': '+3V3A', 'VREF+': '+3V3A', 'VSSA': 'GND',
            'PG10': 'NRST',                     # PG10-NRST
            'PB8': 'BOOT0',                     # PB8-BOOT0
            'PF0': 'HSE_IN', 'PF1': 'HSE_OUT',
            'PA13': 'SWDIO', 'PA14': 'SWCLK', 'PB3': 'SWO',
            'PA11': 'CAN_RX', 'PA12': 'CAN_TX', 'PB4': 'CAN_SILENT',
            'PA0': 'V24_SENSE', 'PC13': 'LED_STAT'},
      default_nc=True, mpn='STM32G474RET6', mfr='STMicroelectronics', lcsc='C521608'),
    C('C10', '100n', a='+3V3', b='GND'),
    C('C11', '100n', a='+3V3', b='GND'),
    C('C12', '100n', a='+3V3', b='GND'),
    C('C13', '100n', a='+3V3', b='GND'),
    C('C14', '4.7u', '0603', a='+3V3', b='GND'),
    L('FB1', '600R@100MHz', '0603', a='+3V3', b='+3V3A', lib_id='Device:FerriteBead',
      mpn='BLM18AG601SN1D', mfr='Murata'),
    C('C15', '1u', a='+3V3A', b='GND'),
    C('C16', '10n', a='+3V3A', b='GND'),
    P('Y1', 'Device:Crystal_GND24', '8MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
      pins={'1': 'HSE_IN', '3': 'HSE_OUT', 'G': 'GND'},
      mpn='NX3225GA-8.000M-STD-CRG-2', mfr='NDK'),
    C('C17', '12p', a='HSE_IN', b='GND'),
    C('C18', '12p', a='HSE_OUT', b='GND'),
    P('SW1', 'Switch:SW_Push', 'RESET', 'Button_Switch_SMD:SW_SPST_TL3342',
      pins={'1': 'NRST', '2': 'GND'}, mpn='TL3342F160QG', mfr='E-Switch'),
    C('C19', '100n', a='NRST', b='GND'),
    R('R3', '10k', a='BOOT0', b='GND'),
    P('J2', 'Connector:Conn_ARM_JTAG_SWD_10', 'SWD',
      'Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD',
      pins={'VTref': '+3V3', 'SWDIO/TMS': 'SWDIO', 'SWCLK/TCK': 'SWCLK', 'SWO/TDO': 'SWO',
            'NC/TDI': 'NC', 'GND': 'GND', 'GNDDetect': 'GND', '~{RESET}': 'NRST'},
      mpn='FTSH-105-01-F-DV-K', mfr='Samtec'),
    R('R4', '1k', a='+3V3', b='LED_STAT_A'),
    D('D5', 'yellow', '0603', k='LED_STAT', a='LED_STAT_A', kind='LED'),
]

# ---------------------------------------------------------------------------
# Sheet 3: CAN-FD
# ---------------------------------------------------------------------------
can = [
    P('U4', 'Interface_CAN_LIN:TJA1051T-3', 'TJA1051T/3',
      pins={'TXD': 'CAN_TX', 'RXD': 'CAN_RX', 'VCC': '+5V', 'VIO': '+3V3', 'GND': 'GND',
            'CANH': 'CANH', 'CANL': 'CANL', 'S': 'CAN_SILENT'},
      mpn='TJA1051T/3,118', mfr='NXP', lcsc='C38695'),
    C('C20', '100n', a='+5V', b='GND'),
    C('C21', '100n', a='+3V3', b='GND'),
    R('R5', '10k', a='CAN_SILENT', b='GND', dnp=True),          # optional: MCU drives S
    R('R6', '60.4', '0603', a='CANH', b='CAN_SPLIT'),
    R('R7', '60.4', '0603', a='CAN_SPLIT', b='CANL'),
    C('C22', '4.7n', '0603', a='CAN_SPLIT', b='GND'),
    P('U6', 'Power_Protection:NUP2105L', 'NUP2105L',
      pins={'1': 'CANH', '2': 'CANL', 'A': 'GND'}, mpn='NUP2105LT1G', mfr='onsemi'),
    P('J3', M12_CAN, 'M12 CAN',
      pins={'SHLD': 'GND', 'CAN_V+': 'NC', 'CAN_GND': 'GND', 'CAN_H': 'CANH', 'CAN_L': 'CANL'},
      mpn='SACC-DSI-M12MS-5CON-L90', mfr='Phoenix Contact'),
]

BOARD = Board(
    name='schgen_example', title='schgen example - CAN-FD node', rev='0.1',
    company='GR180-CCHP', paper='A3',
    sheets=[Sheet('Power', parts=power), Sheet('MCU', parts=mcu), Sheet('CAN', parts=can)],
    pcb=dict(w=80, h=60, holes='M3', hole_inset=4, layers=4, corner_radius=2),
    power_flags='auto',
    comments=['schgen worked example (electronics/tools/example/example_spec.py)'],
)
