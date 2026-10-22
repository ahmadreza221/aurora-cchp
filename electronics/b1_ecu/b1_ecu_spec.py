# -*- coding: utf-8 -*-
"""GR180-CCHP B1 ECU (electrical room, cabinet CP-E) - schgen board spec, rev 0.2 (European parts, docs/electrical/04 §1).

Sheets: Power | MCU (STM32H743IIT6) | Memory | SMCU (NXP MKE16Z64VLF4) | CAN (2x TJA1052i-5) | RS485 (3x ST485E isolated) |
Ethernet (RTL8201F + Wuerth RJ45) | Speed_Inputs (SPD-IN1..6) | Digital_Inputs (32x ISO1I813T) | Relays (16x Finder 34.51) |
Permits (SMCU PERMIT A/B charge pumps, STWD100 -> ECU RUN PERMIT, Finder 50.12) | Connectors.
Channel names follow docs/electrical/02_io_list.csv (board B1). Build:
  python3 electronics/tools/schgen.py build electronics/b1_ecu/b1_ecu_spec.py --out electronics/b1_ecu/out
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
from schgen import Board, Sheet, P, R, C, L, D
from gr180_parts import *   # noqa

rx = Refs()
GND = 'GND'

# I/O list (02_io_list.csv, board B1)
DI = {1: 'ESD_E_STAT', 2: 'XS850_B3_HEALTHY', 3: 'XS853_SR1_STAT_A', 4: 'XS853_SR1_STAT_B', 5: 'INV_DI_FAULT', 6: 'UPS_DCOK_1', 7: 'UPS_DCOK_2',
      8: 'ZS_LS1', 9: 'ZS_LS2', 10: 'ZS_LS3', 11: 'ZS_LS4', 12: 'ZS_ATS_I', 13: 'ZS_ATS_II', 14: 'XS_SPD', 15: 'SD_E_FIRE_FZ2', 16: 'XS_GRID',
      17: 'XS871_FIRE_PREALM', 18: 'XS872_FIRE_FZ1', 19: 'XS873_FIRE_FZ3', 20: 'XS875_AGENT_RELEASED', 21: 'XS876_FCP_FAULT', 22: 'AT885_H2_A1',
      23: 'XS_IPR_TRIP', 24: 'ZS_NPE', 25: 'XA_ATS_FAULT', 26: 'ZS_SP1', 27: 'ZS_SP2', 28: 'ZS_SP3',
      29: 'PERMIT_A_MIRROR', 30: 'PERMIT_B_MIRROR', 31: 'RUN_PERMIT_MIRROR', 32: 'DI32_SPARE'}
RO = {1: 'K_LS1', 2: 'K_LS2', 3: 'K_LS3', 4: 'K_LS4', 5: 'INV_DO_ONOFF', 6: 'BMS_WAKE', 7: 'XA_BLD', 8: 'ENG_RUN', 9: 'K_SP1', 10: 'EH950_SSR',
      11: 'K_SP2', 12: 'K_SP3', 13: 'RO13_SPARE', 14: 'RO14_SPARE', 15: 'RO15_SPARE', 16: 'RO16_SPARE'}

# ================================================================================================= Power
power = [terminal(rx('J'), ['V24_IN_RAW', GND, 'PE'], '24V IN (W-PWR)')]
power += input_24v(rx, 'V24_IN_RAW', GND, '+24V', fuse='3A', tvs='SMBJ33A')
power += [P(rx('U'), STEF01, 'STEF01 eFuse 2 A', pins={'IN': '+24V', 'EN/FAULT': 'EFUSE_FLT', 'ISET': 'EF_ISET', 'dv/dt': 'EF_DVDT', 'GND': GND,
                                                     'OUT': '+24V_P', 'ILIM': 'EF_ILIM', 'GATE': 'EF_GATE'}, mfr='STMicroelectronics', mpn='STEF01FTR'),
          R(rx('R'), '20k', a='EF_ISET', b=GND), C(rx('C'), '10n', a='EF_DVDT', b=GND), R(rx('R'), '22k', a='EF_ILIM', b=GND),
          C(rx('C'), '1n', a='EF_GATE', b=GND), R(rx('R'), '100k', a='EFUSE_FLT', b='+3V3')]
power += logic_rails(rx, '+24V_P', GND, '+5V', '+3V3')
# separate 3V3 for the safety MCU domain (own LDO + own supervisor), 04 §1
power += [P(rx('U'), 'Regulator_Linear:LD1117S33TR_SOT223', 'LD1117S33 (SMCU)', F_SOT223, pins={'VI': '+5V', 'VO': '+3V3_SMCU', 'GND': GND}, **mm('LD1117S33')),
          C(rx('C'), '10u/10V', '0805', a='+3V3_SMCU', b=GND), C(rx('C'), '100n', a='+3V3_SMCU', b=GND)]
# 12 V supply for the safety speed sensors (N1-B, N2-B, UV relay) - SMCU domain, RECOM R-78HB12-0.5 (24 -> 12 V)
power += [P(rx('U'), 'Converter_DCDC:R-78HB12-0.5', 'R-78HB12-0.5', 'Converter_DCDC:Converter_DCDC_RECOM_R-78HB-0.5_THT',
            pins={'IN': '+24V_P', 'GND': GND, 'OUT': '+12V_SENS'}, **mm('R-78HB12-0.5')),
          C(rx('C'), '10u/50V', '1206', a='+24V_P', b=GND), C(rx('C'), '22u/25V', '1206', a='+12V_SENS', b=GND),
          P(rx('F'), 'Device:Polyfuse', '200mA', 'Fuse:Fuse_1206_3216Metric', pins={'1': '+12V_SENS', '2': '+12V_SENS_F'}, mfr='Bourns-free: Littelfuse-free -> use Schurter PFRA', mpn='PFRA.020'),
          ]
# analog rail + hold-up for the EEPROM power-fail write (PVD on the H7)
power += [L(rx('FB'), '600R@100MHz', '0603', a='+3V3', b='+3V3A', lib_id='Device:FerriteBead', mfr='Wuerth', mpn='742792040'),
          C(rx('C'), '1u', a='+3V3A', b=GND), C(rx('C'), '10n', a='+3V3A', b=GND),
          C(rx('C'), '1000u/6.3V hold-up', a='+3V3', b=GND, footprint='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm', lib_id='Device:C_Polarized', mfr='Wuerth', mpn='860080675015'),
          R(rx('R'), '100k', '0603', a='+24V_P', b='V24_MON'), R(rx('R'), '10k', a='V24_MON', b=GND), C(rx('C'), '100n', a='V24_MON', b=GND)]
power += testpoints(rx, ['+24V_P', '+5V', '+3V3', '+3V3_SMCU', '+12V_SENS', GND])

# ================================================================================================= MCU (STM32H743IIT6)
H7 = {
    'VDD': '+3V3', 'VDD33_USB': '+3V3', 'VBAT': 'VBAT', 'VSS': GND, 'VSSA': GND, 'VDDA': '+3V3A', 'VREF+': '+3V3A', 'PDR_ON': '+3V3',
    'VCAP': 'VCAP', 'NRST': 'NRST', 'BOOT0': 'BOOT0', 'PH0': 'HSE_IN', 'PH1': 'HSE_OUT', 'PC14': 'LSE_IN', 'PC15': 'LSE_OUT',
    'PA13': 'SWDIO', 'PA14': 'SWCLK', 'PB3': 'SWO',
    # FDCAN1 engine bus, FDCAN2 BMS bus
    'PD0': 'CAN1_RX', 'PD1': 'CAN1_TX', 'PD2': 'CAN1_STB', 'PB12': 'CAN2_RX', 'PB13': 'CAN2_TX', 'PD3': 'CAN2_STB',
    # USART1 = RS485-1 (HI-1), USART2 = RS485-2 (meters/VFD), USART3 = RS485-3 (JT-901)
    'PA9': 'U1_TX', 'PA10': 'U1_RX', 'PA12': 'U1_DE', 'PD5': 'U2_TX', 'PD6': 'U2_RX', 'PD4': 'U2_DE', 'PD8': 'U3_TX', 'PD9': 'U3_RX', 'PB14': 'U3_DE',
    # RMII to RTL8201F
    'PA1': 'RMII_REF_CLK', 'PA2': 'RMII_MDIO', 'PC1': 'RMII_MDC', 'PA7': 'RMII_CRS_DV', 'PC4': 'RMII_RXD0', 'PC5': 'RMII_RXD1',
    'PG11': 'RMII_TX_EN', 'PG13': 'RMII_TXD0', 'PG14': 'RMII_TXD1', 'PG7': 'PHY_NRST', 'PG8': 'PHY_INT',
    # QUADSPI flash (event recorder)
    'PB2': 'QSPI_CLK', 'PB6': 'QSPI_NCS', 'PD11': 'QSPI_IO0', 'PD12': 'QSPI_IO1', 'PE2': 'QSPI_IO2', 'PD13': 'QSPI_IO3',
    # SPI1 = life-counter EEPROM
    'PA5': 'SPI1_SCK', 'PA6': 'SPI1_MISO', 'PB5': 'SPI1_MOSI', 'PA4': 'EE_CS', 'PG9': 'EE_WP',
    # SPI2 = 4x ISO1I813T digital inputs
    'PI1': 'SPI2_SCK', 'PI2': 'SPI2_MISO', 'PI3': 'SPI2_MOSI', 'PI4': 'DI_CS1', 'PI5': 'DI_CS2', 'PI6': 'DI_CS3', 'PI7': 'DI_CS4',
    'PI9': 'DI_RDY1', 'PI10': 'DI_RDY2', 'PI11': 'DI_RDY3', 'PH2': 'DI_RDY4', 'PH3': 'DI_FAULT', 'PH4': 'DI_RST',
    # SPI4 = link to the SMCU + heartbeat GPIOs
    'PE12': 'SPI4_SCK', 'PE13': 'SPI4_MISO', 'PE14': 'SPI4_MOSI', 'PE11': 'SMCU_CS', 'PE10': 'HB_TO_SMCU', 'PG2': 'HB_FROM_SMCU',
    # speed / pulse inputs (timer capture)
    'PA0': 'SPD_IN1_H7', 'PB10': 'SPD_IN2_H7', 'PB11': 'SPD_IN3_H7', 'PE5': 'SPD_IN4_H7', 'PE6': 'SPD_IN5_H7', 'PA3': 'SPD_IN6_H7',
    # watchdog kick, readbacks, LEDs, misc
    'PG0': 'ECU_WDI', 'PG1': 'RUN_PERMIT_SENSE', 'PG3': 'PERMIT_A_PUMP_SENSE', 'PG4': 'PERMIT_B_PUMP_SENSE', 'PG5': 'LED_HB', 'PG6': 'LED_FLT',
    'PC0': 'V24_MON', 'PG10': 'EFUSE_FLT', 'PE3': 'CAN1_ERR_LED', 'PE4': 'SMCU_ALM_IN',
}
for i in range(16):
    H7['PF%d' % i] = 'RO%02d_DRV' % (i + 1)
mcu = [P(rx('U'), 'MCU_ST_STM32H7:STM32H743IITx', 'STM32H743IIT6', pins=H7, default_nc=True, **mm('STM32H743IIT6'))]
mcu += decaps(rx, '+3V3', GND, n=12, bulk='10u')
mcu += [C(rx('C'), '2.2u', '0603', a='VCAP', b=GND), C(rx('C'), '2.2u', '0603', a='VCAP', b=GND)]
mcu += crystal(rx, 'HSE_IN', 'HSE_OUT', GND, '25MHz', '12p') + crystal32k(rx, 'LSE_IN', 'LSE_OUT', GND)
mcu += swd(rx, '+3V3', GND, 'SWDIO', 'SWCLK', 'SWO', 'NRST', 'SWD ECU')
mcu += [R(rx('R'), '10k', a='BOOT0', b=GND), R(rx('R'), '10k', a='NRST', b='+3V3'),
        P(rx('BT'), 'Device:Battery_Cell', 'CR2032', 'Battery:BatteryHolder_Keystone_3034_1x20mm', pins={'+': 'VBAT_CELL', '-': GND}, mfr='Renata (CH)', mpn='CR2032'),
        D(rx('D'), 'BAT54', 'SOD-123', k='VBAT', a='VBAT_CELL', kind='D_Schottky', mfr='Nexperia', mpn='BAT54-7'),
        D(rx('D'), 'BAT54', 'SOD-123', k='VBAT', a='+3V3', kind='D_Schottky', mfr='Nexperia', mpn='BAT54-7'), C(rx('C'), '100n', a='VBAT', b=GND)]
mcu += led(rx, 'LED_HB', GND, 'green') + led(rx, 'LED_FLT', GND, 'red') + led(rx, 'CAN1_ERR_LED', GND, 'yellow')
mcu += testpoints(rx, ['ECU_WDI', 'HB_TO_SMCU', 'HB_FROM_SMCU'])

# ================================================================================================= Memory
memory = [
    P(rx('U'), M95M04, 'M95M04-DR (life counter, H7)', pins={'~{S}': 'EE_CS', 'Q': 'SPI1_MISO', '~{W}': 'EE_WP', 'VSS': GND, 'D': 'SPI1_MOSI', 'C': 'SPI1_SCK',
                                                            '~{HOLD}': '+3V3', 'VCC': '+3V3'}, **mm('M95M04')),
    C(rx('C'), '100n', a='+3V3', b=GND), R(rx('R'), '10k', a='EE_CS', b='+3V3'),
    P(rx('U'), 'Memory_Flash:W25Q128JVS', 'W25Q128JV (event recorder)', pins={'~{CS}': 'QSPI_NCS', 'DO/IO_{1}': 'QSPI_IO1', '~{WP}/IO_{2}': 'QSPI_IO2', 'GND': GND,
                                                                             'DI/IO_{0}': 'QSPI_IO0', 'CLK': 'QSPI_CLK', '~{HOLD}/~{RESET}/IO_{3}': 'QSPI_IO3', 'VCC': '+3V3'},
      **mm('W25Q128')),
    C(rx('C'), '100n', a='+3V3', b=GND), R(rx('R'), '10k', a='QSPI_NCS', b='+3V3'),
]

# ================================================================================================= SMCU (NXP MKE16Z64VLF4, own 3V3, own clock)
SM = {'VDD': '+3V3_SMCU', 'VDDA': '+3V3_SMCU', 'VREFH': '+3V3_SMCU', 'VSS/VREFL': GND, 'VSS': GND,
      'PTA4': 'SMCU_SWDIO', 'PTC4': 'SMCU_SWCLK', 'PTA5': 'SMCU_NRST',
      'PTB7': 'SMCU_XTAL_IN', 'PTB6': 'SMCU_XTAL_OUT',
      # SPI0 slave to the H7 (link) + heartbeat GPIOs
      'PTB2': 'SPI4_SCK', 'PTB4': 'SPI4_MISO', 'PTB3': 'SPI4_MOSI', 'PTB5': 'SMCU_CS', 'PTD3': 'HB_TO_SMCU', 'PTD2': 'HB_FROM_SMCU',
      # SPI1 master to its own EEPROM
      'PTD0': 'SMCU_EE_SCK', 'PTD1': 'SMCU_EE_MISO', 'PTE0': 'SMCU_EE_MOSI', 'PTE1': 'SMCU_EE_CS',
      # safety speed inputs (own receivers) + UV flame relay
      'PTE4': 'SPD_IN1_S', 'PTE5': 'SPD_IN2_S', 'PTE10': 'SPD_IN3_S', 'PTE11': 'SPD_IN4_S', 'PTE8': 'SPD_IN5_S', 'PTE3': 'SPD_IN6_S',
      # permits (1 kHz PWM into charge pumps), reset of the H7, alarm, readbacks (ADC)
      'PTC0': 'PERMIT_A_PWM', 'PTC1': 'PERMIT_B_PWM', 'PTC2': 'ECU_NRST_OD', 'PTC3': 'SMCU_ALM_IN', 'PTA0': 'PERMIT_A_PUMP_SENSE', 'PTA1': 'PERMIT_B_PUMP_SENSE',
      'PTA2': 'RUN_PERMIT_SENSE', 'PTA3': 'SMCU_LED', 'PTA6': 'B3_HEALTHY_S', 'PTA7': 'SR1_STAT_S'}
smcu = [P(rx('U'), 'MCU_NXP_Kinetis:MKE16Z64VLF4', 'MKE16Z64VLF4 (SMCU; S32K144 upgrade path)', pins=SM, default_nc=True, **mm('MKE16Z64VLF4'))]
smcu += decaps(rx, '+3V3_SMCU', GND, n=4, bulk='4.7u')
smcu += crystal(rx, 'SMCU_XTAL_IN', 'SMCU_XTAL_OUT', GND, '8MHz', '18p', key='CRYSTAL-8M')
smcu += swd(rx, '+3V3_SMCU', GND, 'SMCU_SWDIO', 'SMCU_SWCLK', 'NC', 'SMCU_NRST', 'SWD SMCU')
smcu += [R(rx('R'), '10k', a='SMCU_NRST', b='+3V3_SMCU'),
         # supervisor for the SMCU rail: ST STM1001 class (SOT23-3) -> holds SMCU_NRST low below 2.9 V
         P(rx('U'), STM1001, 'STM1001T', pins={'VCC': '+3V3_SMCU', 'GND': GND, '~{RST}': 'SMCU_NRST'}, mfr='STMicroelectronics', mpn='STM1001TWX6F'),
         P(rx('U'), M95M04, 'M95M04-DR (life counter copy, SMCU)', pins={'~{S}': 'SMCU_EE_CS', 'Q': 'SMCU_EE_MISO', '~{W}': '+3V3_SMCU', 'VSS': GND, 'D': 'SMCU_EE_MOSI',
                                                                       'C': 'SMCU_EE_SCK', '~{HOLD}': '+3V3_SMCU', 'VCC': '+3V3_SMCU'}, **mm('M95M04')),
         C(rx('C'), '100n', a='+3V3_SMCU', b=GND),
         # ECU_NRST open-drain from the SMCU into the H7 NRST (NPN, Nexperia)
         P(rx('Q'), 'Transistor_BJT:BC847', 'BC847', 'Package_TO_SOT_SMD:SOT-23', pins={'B': 'ECU_NRST_B', 'C': 'NRST', 'E': GND}, mfr='Nexperia', mpn='BC847B,215'),
         R(rx('R'), '4k7', a='ECU_NRST_OD', b='ECU_NRST_B'),
         # H7 -> SMCU status copies (B3 HEALTHY and SR1 status at 3.3 V logic from the DI bank are read over SPI; direct copies for independence)
         R(rx('R'), '10k', a='B3_HEALTHY_S', b='XS850_B3_HEALTHY_3V3'), R(rx('R'), '10k', a='SR1_STAT_S', b='XS853_SR1_STAT_3V3')]
smcu += led(rx, 'SMCU_LED', GND, 'red')

# ================================================================================================= CAN (engine bus, BMS bus)
can = iso_can(rx, 'ENG', 'CAN1_TX', 'CAN1_RX', 'CAN1_STB', '+3V3', GND, '+5V', 'CAN1_H', 'CAN1_L', 'GND_CAN1', term_jumper=True)
can += iso_can(rx, 'BMS', 'CAN2_TX', 'CAN2_RX', 'CAN2_STB', '+3V3', GND, '+5V', 'CAN2_H', 'CAN2_L', 'GND_CAN2', term_jumper=False)

# ================================================================================================= RS-485 x3
rs485 = iso_rs485(rx, 'INV', 'U1_TX', 'U1_RX', 'U1_DE', '+3V3', GND, '+5V', 'RS1_A', 'RS1_B', 'GND_RS1')
rs485 += iso_rs485(rx, 'MET', 'U2_TX', 'U2_RX', 'U2_DE', '+3V3', GND, '+5V', 'RS2_A', 'RS2_B', 'GND_RS2')
rs485 += iso_rs485(rx, 'JT901', 'U3_TX', 'U3_RX', 'U3_DE', '+3V3', GND, '+5V', 'RS3_A', 'RS3_B', 'GND_RS3')

# ================================================================================================= Ethernet (RMII PHY + RJ45 with magnetics)
eth = [P(rx('U'), RTL8201F, 'RTL8201F-VB-CG', pins={'TXD0': 'RMII_TXD0', 'TXD1': 'RMII_TXD1', 'TXEN': 'RMII_TX_EN', 'RXD0': 'RMII_RXD0', 'RXD1': 'RMII_RXD1',
                                                   'CRS_DV': 'RMII_CRS_DV', 'RXER': 'NC', 'REF_CLK': 'RMII_REF_CLK_PHY', 'MDC': 'RMII_MDC', 'MDIO': 'RMII_MDIO',
                                                   '~{RESET}': 'PHY_NRST', 'INT/CLKOUT': 'PHY_INT', 'TXP': 'ETH_TXP', 'TXN': 'ETH_TXN', 'RXP': 'ETH_RXP', 'RXN': 'ETH_RXN',
                                                   'XTAL1': 'PHY_XI', 'XTAL2': 'PHY_XO', 'LED0': 'PHY_LED0', 'LED1': 'PHY_LED1', 'RSET': 'PHY_RSET', 'VDDIO': '+3V3',
                                                   'AVDD33': '+3V3', 'DVDD': 'PHY_DVDD', 'GND': GND}, **mm('RTL8201F')),
       C(rx('C'), '100n', a='+3V3', b=GND), C(rx('C'), '100n', a='+3V3', b=GND), C(rx('C'), '4.7u', '0805', a='+3V3', b=GND),
       C(rx('C'), '2.2u', '0603', a='PHY_DVDD', b=GND), R(rx('R'), '2k49 1%', '0603', a='PHY_RSET', b=GND), R(rx('R'), '1k5', a='RMII_MDIO', b='+3V3'),
       R(rx('R'), '33', a='RMII_REF_CLK', b='RMII_REF_CLK_PHY'), R(rx('R'), '10k', a='PHY_NRST', b='+3V3')]
eth += crystal(rx, 'PHY_XI', 'PHY_XO', GND, '25MHz', '18p')
eth += [P(rx('J'), RJ45_MAG, 'RJ45 7499010211A', pins={'TD+': 'ETH_TXP', 'TD-': 'ETH_TXN', 'TCT': 'ETH_CT', 'RD+': 'ETH_RXP', 'RD-': 'ETH_RXN', 'RCT': 'ETH_CT',
                                                      'LED1_A': '+3V3', 'LED1_K': 'PHY_LED0_K', 'LED2_A': '+3V3', 'LED2_K': 'PHY_LED1_K', 'SHLD': 'ETH_SHLD'}, **mm('RJ45-MAG')),
        R(rx('R'), '330', a='PHY_LED0', b='PHY_LED0_K'), R(rx('R'), '330', a='PHY_LED1', b='PHY_LED1_K'),
        R(rx('R'), '49.9', '0603', a='ETH_CT', b='ETH_CT_R'), C(rx('C'), '100n/50V', '0603', a='ETH_CT_R', b=GND),
        R(rx('R'), '1M', '0805', a='ETH_SHLD', b=GND), C(rx('C'), '1n/2kV', '1206', a='ETH_SHLD', b=GND)]

# ================================================================================================= Speed inputs (SPD-IN1..6; each to the H7 AND the SMCU)
speed = [P(rx('U'), ST26C32, 'ST26C32 (N1-A RS-422 from B2)', pins={'1A': 'N1A_422_A', '1B': 'N1A_422_B', '1Y': 'SPD1_RAW', '2A': 'SPD5_422_A', '2B': 'SPD5_422_B', '2Y': 'SPD5_RAW',
                                                                    '3A': 'SPD6_422_A', '3B': 'SPD6_422_B', '3Y': 'SPD6_RAW', '4A': GND, '4B': '+3V3', '4Y': 'NC',
                                                                    'G': '+3V3', '~{G}': GND, 'VCC': '+3V3', 'GND': GND}, **mm('ST26C32')),
         C(rx('C'), '100n', a='+3V3', b=GND),
         R(rx('R'), '120', '0603', a='N1A_422_A', b='N1A_422_B'), R(rx('R'), '120', '0603', a='SPD5_422_A', b='SPD5_422_B'), R(rx('R'), '120', '0603', a='SPD6_422_A', b='SPD6_422_B')]
# open-collector sensor inputs (N1-B, N2-B, UV relay) with 12 V pull-ups, divider + Schmitt trigger; sensor supply +12V_SENS_F from the SMCU domain
for i, tag in ((2, 'N1B'), (3, 'N2B'), (4, 'UV')):
    raw, lv = 'SPD%d_OC' % i, 'SPD%d_LV' % i
    speed += [R(rx('R'), '2k2 0.5W', '1206', a='+12V_SENS_F', b=raw), R(rx('R'), '10k', a=raw, b=lv), R(rx('R'), '3k9', a=lv, b=GND), C(rx('C'), '1n', a=lv, b=GND),
              D(rx('D'), 'BZT52C3V6', 'SOD-123', k=lv, a=GND, kind='D_Zener', mfr='Nexperia', mpn='BZT52H-C3V6'),
              P(rx('D'), 'Device:D_TVS', 'SMAJ15CA', 'Diode_SMD:D_SMA', pins={'A1': raw, 'A2': GND}, mfr='STMicroelectronics', mpn='SMAJ15CA-TR'),
              P(rx('U'), '74xGxx:74LVC1G17', '74LVC1G17', 'Package_TO_SOT_SMD:SOT-353_SC-70-5', pins={'2': lv, '4': 'SPD%d_RAW' % i, 'VCC': '+3V3', 'GND': GND}, **mm('74LVC1G17'))]
# split every SPDn_RAW into an H7 copy and an SMCU copy through separate buffers (74LVC2G17: unit A -> H7, unit B -> SMCU)
for i in range(1, 7):
    speed += [P(rx('U'), '74xGxx:74LVC2G17', '74LVC2G17', 'Package_TO_SOT_SMD:SOT-363_SC-70-6',
                pins={'1': 'SPD%d_RAW' % i, '6': 'SPD_IN%d_H7' % i, '3': 'SPD%d_RAW' % i, '4': 'SPD_IN%d_S' % i, 'VCC': '+3V3', 'GND': GND}, **mm('74LVC2G17'))]
speed += [C(rx('C'), '100n', a='+3V3', b=GND)] * 1

# ================================================================================================= Digital inputs (32x, 4x ISO1I813T on SPI2)
dio = []
for k in range(4):
    nets = ['DI%02d_%s' % (8 * k + i + 1, DI[8 * k + i + 1]) for i in range(8)]
    dio += di_bank(rx, 'B%d' % (k + 1), nets, '+24V_FLD', 'GND_FLD', '+3V3', GND, 'SPI2_SCK', 'SPI2_MOSI', 'SPI2_MISO', 'DI_CS%d' % (k + 1), 'DI_RST',
                   'DI_RDY%d' % (k + 1), 'DI_FAULT')
dio += [R(rx('R'), '10k', a='DI_FAULT', b='+3V3'), R(rx('R'), '10k', a='DI_RST', b='+3V3'),
        P(rx('F'), 'Device:Polyfuse', '500mA', 'Fuse:Fuse_1206_3216Metric', pins={'1': '+24V_P', '2': '+24V_FLD'}, mfr='Schurter', mpn='PFRA.050'),
        R(rx('R'), '0R (field GND link)', '1206', a=GND, b='GND_FLD'),
        P(rx('D'), 'Device:D_TVS', 'SMBJ33A', 'Diode_SMD:D_SMB', pins={'A1': '+24V_FLD', 'A2': 'GND_FLD'}, **mm('SMBJ33A'))]
# B3 HEALTHY and SR1 status also reach the SMCU directly (3.3 V level from a resistor/zener input, not through SPI)
for src, dst in (('DI02_XS850_B3_HEALTHY', 'XS850_B3_HEALTHY_3V3'), ('DI03_XS853_SR1_STAT_A', 'XS853_SR1_STAT_3V3')):
    dio += [R(rx('R'), '22k', '0603', a=src, b=dst), R(rx('R'), '3k9', a=dst, b=GND), D(rx('D'), 'BZT52C3V6', 'SOD-123', k=dst, a=GND, kind='D_Zener', mfr='Nexperia', mpn='BZT52H-C3V6')]

# ================================================================================================= Relays (16x Finder 34.51, 2x ULN2803A)
relays = relay_out(rx, 'A', ['RO%02d_DRV' % i for i in range(1, 9)], '+24V_P', GND,
                   com_nets=['RO%02d_%s_COM' % (i, RO[i]) for i in range(1, 9)], no_nets=['RO%02d_%s_NO' % (i, RO[i]) for i in range(1, 9)])
relays += relay_out(rx, 'B', ['RO%02d_DRV' % i for i in range(9, 17)], '+24V_P', GND,
                    com_nets=['RO%02d_%s_COM' % (i, RO[i]) for i in range(9, 17)], no_nets=['RO%02d_%s_NO' % (i, RO[i]) for i in range(9, 17)])

# ================================================================================================= Permits (dynamic, force-guided relays)
permits = []
for tag, pwm, sense in (('A', 'PERMIT_A_PWM', 'PERMIT_A_PUMP_SENSE'), ('B', 'PERMIT_B_PWM', 'PERMIT_B_PUMP_SENSE')):
    x, y, b, coil = 'CP%s_X' % tag, 'CP%s_Y' % tag, 'CP%s_B' % tag, 'PERMIT_%s_COIL' % tag
    permits += [C(rx('C'), '100n', a=pwm, b=x),
                D(rx('D'), 'BAT54', 'SOD-123', k=x, a=GND, kind='D_Schottky', mfr='Nexperia', mpn='BAT54-7'),
                D(rx('D'), 'BAT54', 'SOD-123', k=y, a=x, kind='D_Schottky', mfr='Nexperia', mpn='BAT54-7'),
                C(rx('C'), '1u', '0603', a=y, b=GND), R(rx('R'), '47k', a=y, b=GND), R(rx('R'), '4k7', a=y, b=b),
                R(rx('R'), '100k', a=y, b=sense), C(rx('C'), '10n', a=sense, b=GND),
                P(rx('Q'), 'Transistor_BJT:BC817', 'BC817', 'Package_TO_SOT_SMD:SOT-23', pins={'B': b, 'C': coil, 'E': GND}, mfr='Nexperia', mpn='BC817-40,215'),
                D(rx('D'), 'BAS21', 'SOD-123', k='+24V_P', a=coil, mfr='Nexperia', mpn='BAS21,215'),
                P(rx('K'), FINDER5012, 'Finder 50.12 PERMIT %s' % tag,
                  pins={'A1': '+24V_P', 'A2': coil, '11': 'PERMIT_%s_C' % tag, '14': 'PERMIT_%s_NO' % tag, '12': 'NC',
                        '21': '+24V_FLD', '22': 'DI%d_PERMIT_%s_MIRROR' % (29 if tag == 'A' else 30, tag), '24': 'NC'}, **mm('FINDER-50.12'))]
# ECU RUN PERMIT: STWD100 window watchdog kicked by the H7; /WDO low -> relay released
permits += [P(rx('U'), STWD100, 'STWD100NYWY3F', pins={'WDI': 'ECU_WDI', 'GND': GND, '~{EN}': GND, '~{WDO}': 'WDO_N', 'VCC': '+3V3'}, **mm('STWD100')),
            C(rx('C'), '100n', a='+3V3', b=GND), R(rx('R'), '10k', a='WDO_N', b='+3V3'),
            P(rx('Q'), 'Transistor_BJT:BC817', 'BC817', 'Package_TO_SOT_SMD:SOT-23', pins={'B': 'RUNP_B', 'C': 'RUN_PERMIT_COIL', 'E': GND}, mfr='Nexperia', mpn='BC817-40,215'),
            R(rx('R'), '4k7', a='WDO_N', b='RUNP_B'), R(rx('R'), '100k', a='WDO_N', b='RUN_PERMIT_SENSE'),
            D(rx('D'), 'BAS21', 'SOD-123', k='+24V_P', a='RUN_PERMIT_COIL', mfr='Nexperia', mpn='BAS21,215'),
            P(rx('K'), FINDER5012, 'Finder 50.12 ECU RUN PERMIT',
              pins={'A1': '+24V_P', 'A2': 'RUN_PERMIT_COIL', '11': 'RUN_PERMIT_C', '14': 'RUN_PERMIT_NO', '12': 'NC',
                    '21': '+24V_FLD', '22': 'DI31_RUN_PERMIT_MIRROR', '24': 'NC'}, **mm('FINDER-50.12'))]

# ================================================================================================= Connectors
conn = [
    terminal(rx('J'), ['CAN1_H', 'CAN1_L', 'GND_CAN1', 'PE'], 'W101 CAN-FD #1 engine', pitch=3.81),
    terminal(rx('J'), ['CAN2_H', 'CAN2_L', 'GND_CAN2', 'PE'], 'W107 CAN #2 BMS', pitch=3.81),
    terminal(rx('J'), ['RS1_A', 'RS1_B', 'GND_RS1', 'PE'], 'W105 RS-485 #1 HI-1', pitch=3.81),
    terminal(rx('J'), ['RS2_A', 'RS2_B', 'GND_RS2', 'PE'], 'W106 RS-485 #2 meters/VFD', pitch=3.81),
    terminal(rx('J'), ['RS3_A', 'RS3_B', 'GND_RS3', 'PE'], 'W123 RS-485 #3 JT-901', pitch=3.81),
    terminal(rx('J'), ['N1A_422_A', 'N1A_422_B', 'SPD5_422_A', 'SPD5_422_B', 'SPD6_422_A', 'SPD6_422_B', GND, 'PE'], 'W102a N1-A RS-422 (+2 spare)', pitch=3.81),
    terminal(rx('J'), ['+12V_SENS_F', 'SPD2_OC', GND, '+12V_SENS_F', 'SPD3_OC', GND, '+12V_SENS_F', 'SPD4_OC', GND, 'PE'], 'W102b N1-B, N2-B, UV (SMCU)', pitch=3.81),
    terminal(rx('J'), ['PERMIT_A_C', 'PERMIT_A_NO', 'PERMIT_B_C', 'PERMIT_B_NO', 'RUN_PERMIT_C', 'RUN_PERMIT_NO', '+24V_FLD', 'DI03_XS853_SR1_STAT_A',
                       'DI04_XS853_SR1_STAT_B', 'DI01_ESD_E_STAT', 'DI02_XS850_B3_HEALTHY', 'GND_FLD'], 'W103 safety loop to SR1'),
]
for k in range(4):
    nets = ['DI%02d_%s' % (8 * k + i + 1, DI[8 * k + i + 1]) for i in range(8)]
    if k == 0:
        nets = ['DI05_INV_DI_FAULT', 'DI06_UPS_DCOK_1', 'DI07_UPS_DCOK_2', 'DI08_ZS_LS1', 'NC', 'NC', 'NC', 'NC']   # DI01..04 are on W103
    if k == 3:
        nets = nets[:4] + ['NC'] * 4                                                                                  # DI29..31 are the permit mirrors (on-board)
    conn.append(terminal(rx('J'), nets + ['+24V_FLD', 'GND_FLD'], 'DI %02d..%02d (W109/W124)' % (8 * k + 1, 8 * k + 8)))
for k in range(2):
    nets = []
    for i in range(8 * k + 1, 8 * k + 9):
        nets += ['RO%02d_%s_COM' % (i, RO[i]), 'RO%02d_%s_NO' % (i, RO[i])]
    conn.append(terminal(rx('J'), nets, 'RO %02d..%02d (W108/W109/W103)' % (8 * k + 1, 8 * k + 8)))
conn += [terminal(rx('J'), ['SMCU_ALM_IN', GND], 'service: SMCU ALM out', pitch=3.81)]

BOARD = Board(
    name='b1_ecu', title='GR180-CCHP B1 ECU', rev='0.2', company='GR180-CCHP', paper='A2',
    sheets=[Sheet('Power', parts=power), Sheet('MCU', parts=mcu), Sheet('Memory', parts=memory), Sheet('SMCU', parts=smcu), Sheet('CAN', parts=can),
            Sheet('RS485', parts=rs485), Sheet('Ethernet', parts=eth), Sheet('Speed_Inputs', parts=speed), Sheet('Digital_Inputs', parts=dio),
            Sheet('Relays', parts=relays), Sheet('Permits', parts=permits), Sheet('Connectors', parts=conn)],
    pcb=dict(w=220, h=160, holes='M3', hole_inset=4, layers=4, corner_radius=2),
    power_flags='auto',
    erc_pin_map={('power_out', 'power_out'): 'warning'},    # STM32H7 VCAP pins are both marked power_out in the KiCad library
    comments=['B1 ECU rev 0.2 - European parts (docs/electrical/04 §1); channels per 02_io_list.csv'],
)
