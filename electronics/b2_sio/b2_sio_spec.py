# -*- coding: utf-8 -*-
"""GR180-CCHP B2 sensor I/O board (roof cabinet RP-1) - schgen board spec, rev 0.2 (European parts, docs/electrical/04 §2).

Channels per docs/electrical/02_io_list.csv (board B2): TC01..TC12 (STM32F373 AFE #1), RTD01..RTD16 (STM32F373 AFE #2),
AI01..AI24 (4-20 mA / AI16 2-10 V) and VIB1..VIB3 + FAI1..FAI2 (fast) on the STM32H743 ADCs, FI01..FI06 pulse inputs (FI01 re-sent as
RS-422 to B1 SPD-IN1), DI01..DI32 (4x ISO1I813T), CAN-FD #1 engine bus (TJA1052i-5 isolated).
MCU: STM32H743IIT6 (LQFP-176) instead of the VIT6 of 04 §2 because the 32 analog inputs (24 + 8) need more ADC pins than LQFP-100 has.
Build:  python3 electronics/tools/schgen.py build electronics/b2_sio/b2_sio_spec.py --out electronics/b2_sio/out
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
from schgen import Board, Sheet, P, R, C, L, D, G
from gr180_parts import *   # noqa

rx = Refs()
GND = 'GND'

AI = {1: 'PT522', 2: 'PT524', 3: 'PT101', 4: 'PDT526', 5: 'PT601', 6: 'PT604', 7: 'PT613', 8: 'FT606', 9: 'PT701', 10: 'PT755', 11: 'AT821', 12: 'AT822',
      13: 'PDT222A', 14: 'PDT222B', 15: 'PDT223', 16: 'ZT101_2_10V', 17: 'PDT703', 18: 'PT709', 19: 'LT707', 20: 'MT501', 21: 'BE631_UV_INT', 22: 'SPARE',
      23: 'SPARE', 24: 'SPARE'}
TC = {1: 'TE502', 2: 'TE503', 3: 'TE504A', 4: 'TE504B', 5: 'TE504C', 6: 'TE505', 7: 'TE101', 8: 'TE512', 9: 'TE508', 10: 'TE509', 11: 'TE510', 12: 'TE511'}
RTD = {1: 'TE501_T1', 2: 'TE607', 3: 'TE704', 4: 'TE705', 5: 'TE706', 6: 'TE720', 7: 'TE721', 8: 'TE_GLY', 9: 'TE754', 10: 'TE834', 11: 'SPARE', 12: 'TE708',
       13: 'SPARE', 14: 'SPARE', 15: 'SPARE', 16: 'SPARE'}
DI = {1: 'ZSC610', 2: 'PSL602', 3: 'PSH603', 4: 'ZSC611', 5: 'ZSC612', 6: 'PSL702', 7: 'SPARE', 8: 'LSL707', 9: 'LSL756', 10: 'ESD_R_STAT', 11: 'ZS811', 12: 'ZS812',
      13: 'ZS813', 14: 'ZS814', 15: 'AT821_10PCT', 16: 'AT822_10PCT', 17: 'PDSL831', 18: 'TSH836', 19: 'HS841_A', 20: 'HS841_B', 21: 'HS842_RESET', 22: 'ZSO101',
      23: 'XS_SPD_ROOF', 24: 'FD837_CLOSED', 25: 'SPARE', 26: 'SPARE', 27: 'SPARE', 28: 'SPARE', 29: 'SPARE', 30: 'SPARE', 31: 'SPARE', 32: 'SPARE'}
FI = {1: 'SE001A_N1A', 2: 'SPARE', 3: 'FT752', 4: 'FQ608', 5: 'SPARE', 6: 'SPARE'}
ADC_PIN = ['PA0', 'PA1', 'PA2', 'PA3', 'PA4', 'PA5', 'PA6', 'PA7', 'PB0', 'PB1', 'PC0', 'PC1', 'PC2_C', 'PC3_C', 'PC4', 'PC5',
           'PF3', 'PF4', 'PF5', 'PF6', 'PF7', 'PF8', 'PF9', 'PF10']                     # AI01..AI24
FAST_PIN = {'VIB1': 'PF11', 'VIB2': 'PF12', 'VIB3': 'PF13', 'FAI1': 'PF14', 'FAI2': 'PH2', 'FAI3': 'PH3', 'FAI4': 'PH4'}

# ================================================================================================= Power
power = [terminal(rx('J'), ['V24_IN_RAW', GND, 'PE'], '24V IN (from RP-1 DC-DC)')]
power += input_24v(rx, 'V24_IN_RAW', GND, '+24V', fuse='3A', tvs='SMBJ33A')
power += logic_rails(rx, '+24V', GND, '+5V', '+3V3')
power += [P(rx('U'), 'Regulator_Linear:LD1117S33TR_SOT223', 'LD1117S33 (analog)', F_SOT223, pins={'VI': '+5V', 'VO': '+3V3A', 'GND': GND}, **mm('LD1117S33')),
          C(rx('C'), '10u/10V', '0805', a='+3V3A', b=GND), C(rx('C'), '100n', a='+3V3A', b=GND),
          L(rx('FB'), '600R@100MHz', '0603', a='+3V3A', b='+3V3_SD', lib_id='Device:FerriteBead', mfr='Wuerth', mpn='742792040'),
          C(rx('C'), '1u', a='+3V3_SD', b=GND), C(rx('C'), '100n', a='+3V3_SD', b=GND),
          # mid-rail 1.65 V for the IEPE AC path, 2.5 V reference TL431 (ST) for the RTD/TC checks
          R(rx('R'), '10k 0.1%', '0603', a='+3V3A', b='VMID'), R(rx('R'), '10k 0.1%', '0603', a='VMID', b=GND), C(rx('C'), '10u', '0805', a='VMID', b=GND),
          P(rx('U'), 'Reference_Voltage:TL431DBZ', 'TL431 (ST)', 'Package_TO_SOT_SMD:SOT-23', pins={'K': 'VREF25', 'REF': 'VREF25', 'A': GND}, mfr='STMicroelectronics', mpn='TL431AIL3T'),
          R(rx('R'), '1k', a='+5V', b='VREF25'), C(rx('C'), '100n', a='VREF25', b=GND),
          # 24 V loop supply for the 4-20 mA transmitters and the field DI supply
          P(rx('F'), 'Device:Polyfuse', '1.1A', 'Fuse:Fuse_1812_4532Metric', pins={'1': '+24V', '2': '+24V_LOOP'}, mfr='Schurter', mpn='PFRA.110'),
          P(rx('D'), 'Device:D_TVS', 'SMBJ33A', 'Diode_SMD:D_SMB', pins={'A1': '+24V_LOOP', 'A2': GND}, **mm('SMBJ33A')),
          P(rx('F'), 'Device:Polyfuse', '500mA', 'Fuse:Fuse_1206_3216Metric', pins={'1': '+24V', '2': '+24V_FLD'}, mfr='Schurter', mpn='PFRA.050'),
          P(rx('D'), 'Device:D_TVS', 'SMBJ33A', 'Diode_SMD:D_SMB', pins={'A1': '+24V_FLD', 'A2': 'GND_FLD'}, **mm('SMBJ33A')),
          R(rx('R'), '0R (field GND link)', '1206', a=GND, b='GND_FLD')]
power += testpoints(rx, ['+24V', '+5V', '+3V3', '+3V3A', 'VMID', 'VREF25', GND])

# ================================================================================================= MCU (STM32H743IIT6)
H7 = {'VDD': '+3V3', 'VDD33_USB': '+3V3', 'VBAT': '+3V3', 'VSS': GND, 'VSSA': GND, 'VDDA': '+3V3A', 'VREF+': '+3V3A', 'PDR_ON': '+3V3', 'VCAP': 'VCAP',
      'NRST': 'NRST', 'BOOT0': 'BOOT0', 'PH0': 'HSE_IN', 'PH1': 'HSE_OUT', 'PA13': 'SWDIO', 'PA14': 'SWCLK', 'PB3': 'SWO',
      'PD0': 'CAN1_RX', 'PD1': 'CAN1_TX', 'PD2': 'CAN1_STB',
      # SPI3 master to the two F373 AFEs
      'PC10': 'SPI3_SCK', 'PC11': 'SPI3_MISO', 'PC12': 'SPI3_MOSI', 'PD4': 'AFE_TC_CS', 'PD5': 'AFE_RTD_CS', 'PD6': 'AFE_TC_DRDY', 'PD7': 'AFE_RTD_DRDY',
      'PD8': 'AFE_NRST',
      # SPI2 to the 4x ISO1I813T
      'PI1': 'SPI2_SCK', 'PI2': 'SPI2_MISO', 'PI3': 'SPI2_MOSI', 'PI4': 'DI_CS1', 'PI5': 'DI_CS2', 'PI6': 'DI_CS3', 'PI7': 'DI_CS4',
      'PI9': 'DI_RDY1', 'PI10': 'DI_RDY2', 'PI11': 'DI_RDY3', 'PH6': 'DI_RDY4', 'PH7': 'DI_FAULT', 'PH8': 'DI_RST',
      # pulse inputs (timer capture)
      'PE9': 'FI01_IN', 'PE11': 'FI02_IN', 'PE13': 'FI03_IN', 'PE14': 'FI04_IN', 'PD12': 'FI05_IN', 'PD13': 'FI06_IN',
      # IEPE bias window status, LEDs, board temperature
      'PG0': 'VIB1_BIAS_OK', 'PG1': 'VIB2_BIAS_OK', 'PG2': 'VIB3_BIAS_OK', 'PG5': 'LED_HB', 'PG6': 'LED_FLT', 'PH5': 'TE835_BOARD_T'}
for i, pin in enumerate(ADC_PIN):
    H7[pin] = 'AI%02d_ADC' % (i + 1)
for k, pin in FAST_PIN.items():
    H7[pin] = k + '_ADC'
mcu = [P(rx('U'), 'MCU_ST_STM32H7:STM32H743IITx', 'STM32H743IIT6', pins=H7, default_nc=True, **mm('STM32H743IIT6'))]
mcu += decaps(rx, '+3V3', GND, n=12, bulk='10u')
mcu += [C(rx('C'), '2.2u', '0603', a='VCAP', b=GND), C(rx('C'), '2.2u', '0603', a='VCAP', b=GND)]
mcu += crystal(rx, 'HSE_IN', 'HSE_OUT', GND, '25MHz', '12p')
mcu += swd(rx, '+3V3', GND, 'SWDIO', 'SWCLK', 'SWO', 'NRST', 'SWD H7')
mcu += [R(rx('R'), '10k', a='BOOT0', b=GND), R(rx('R'), '10k', a='NRST', b='+3V3')]
mcu += led(rx, 'LED_HB', GND, 'green') + led(rx, 'LED_FLT', GND, 'red')
STLM20 = G('STLM20', ref='U', footprint='Package_TO_SOT_SMD:SOT-23', description='ST STLM20 analog temperature sensor (board temperature TE-835)',
           pins=[('1', 'VDD', 'power_in', 'T'), ('2', 'GND', 'power_in', 'B'), ('3', 'VOUT', 'output', 'R')])
mcu += [P(rx('U'), STLM20, 'STLM20W87F', pins={'VDD': '+3V3A', 'GND': GND, 'VOUT': 'TE835_BOARD_T'}, mfr='STMicroelectronics', mpn='STLM20W87F'),
        C(rx('C'), '100n', a='+3V3A', b=GND)]

# ================================================================================================= AFE #1: thermocouples (STM32F373, SDADC)
# SDADC input pins of the F373 used here (VERIFY the SDADC channel mapping in the STM32F373 datasheet before layout):
SD_PINS = ['PE7', 'PE8', 'PE9', 'PE10', 'PE11', 'PE12', 'PB0', 'PB1', 'PB2', 'PE13', 'PE14', 'PE15', 'PB10', 'PB14', 'PB15', 'PD8', 'PD9', 'PD10',
           'PD11', 'PD12', 'PD13', 'PD14', 'PD15', 'PC0', 'PC1', 'PC2', 'PC3']


def f373(ref_value, cs, drdy, tagp):
    pins = {'VDD': '+3V3', 'VBAT': '+3V3', 'VSS': GND, 'VSSA': GND, 'VDDA': '+3V3A', 'VREF+': '+3V3A', 'VDDSD12': '+3V3_SD', 'VDDSD3': '+3V3_SD',
            'VSSSD': GND, 'VREFSD+': '+3V3_SD', 'VREFSD-': GND, 'NRST': 'AFE_NRST', 'BOOT0': GND,
            'PA5': 'SPI3_SCK', 'PA6': 'SPI3_MISO', 'PA7': 'SPI3_MOSI', 'PA4': cs, 'PA8': drdy, 'PA13': tagp + '_SWDIO', 'PA14': tagp + '_SWCLK'}
    return pins


tc_pins = f373('AFE TC', 'AFE_TC_CS', 'AFE_TC_DRDY', 'TCAFE')
afe_tc = []
for i in range(1, 13):
    p, n = 'TC%02d_%s_P' % (i, TC[i]), 'TC%02d_%s_N' % (i, TC[i])
    fp, fn = 'TC%02d_FP' % i, 'TC%02d_FN' % i
    tc_pins[SD_PINS[2 * (i - 1)]] = fp
    tc_pins[SD_PINS[2 * (i - 1) + 1]] = fn
    afe_tc += [R(rx('R'), '1k', a=p, b=fp), R(rx('R'), '1k', a=n, b=fn), C(rx('C'), '100n', a=fp, b=fn), C(rx('C'), '10n', a=fp, b=GND), C(rx('C'), '10n', a=fn, b=GND),
               R(rx('R'), '10M', '0603', a=fp, b='+3V3A'), R(rx('R'), '10M', '0603', a=fn, b=GND)]       # open-TC detection: input drifts to the rails
# cold-junction PT1000 x2 on the isothermal terminal blocks (0.5 mA from LM334)
for k, pin in ((1, 'PC0'), (2, 'PC1')):
    cj = 'CJC%d' % k
    tc_pins[pin] = cj
    afe_tc += [P(rx('U'), 'Reference_Current:LM334SM', 'LM334 (ST) 0.5 mA', pins={'3': '+5V', '2': cj + '_RSET', '1': cj}, mfr='STMicroelectronics', mpn='LM334DT'),
               R(rx('R'), '136', '0603', a=cj + '_RSET', b=cj),
               P(rx('RT'), 'Device:Thermistor_PTC', 'PT1000 CJC (SMD 0603, Heraeus)', 'Resistor_SMD:R_0603_1608Metric', pins={'1': cj, '2': GND}, mfr='Heraeus Nexensos', mpn='32208550'),
               C(rx('C'), '100n', a=cj, b=GND)]
tc_pins['PC2'] = 'VREF25'                 # reference check channel
afe_tc = [P(rx('U'), 'MCU_ST_STM32F3:STM32F373VCTx', 'STM32F373VCT6 (TC AFE)', pins=tc_pins, default_nc=True, **mm('STM32F373VCT6'))] + afe_tc
afe_tc += decaps(rx, '+3V3', GND, n=4, bulk='4.7u') + [C(rx('C'), '1u', a='+3V3_SD', b=GND), C(rx('C'), '100n', a='+3V3_SD', b=GND)]
afe_tc += swd(rx, '+3V3', GND, 'TCAFE_SWDIO', 'TCAFE_SWCLK', 'NC', 'AFE_NRST', 'SWD TC AFE')

# ================================================================================================= AFE #2: RTDs (STM32F373, SDADC)
rtd_pins = f373('AFE RTD', 'AFE_RTD_CS', 'AFE_RTD_DRDY', 'RTDAFE')
afe_rtd = []
for i in range(1, 17):
    top, lead = 'RTD%02d_%s_EXC' % (i, RTD[i]), 'RTD%02d_%s_RET' % (i, RTD[i])
    f = 'RTD%02d_F' % i
    rtd_pins[SD_PINS[i - 1]] = f
    afe_rtd += [P(rx('U'), 'Reference_Current:LM334SM', 'LM334 (ST) 0.5 mA', pins={'3': '+5V', '2': 'RTD%02d_RSET' % i, '1': top}, mfr='STMicroelectronics', mpn='LM334DT'),
                R(rx('R'), '136', '0603', a='RTD%02d_RSET' % i, b=top),
                R(rx('R'), '1k', a=top, b=f), C(rx('C'), '100n', a=f, b=GND),
                P(rx('D'), 'Device:D_TVS', 'PESD5V0 class (Nexperia)', 'Package_TO_SOT_SMD:SOT-23', pins={'A1': top, 'A2': GND}, mfr='Nexperia', mpn='PESD5V0S1BL')]
    if i <= 8:                                                                   # 3-wire lead compensation for RTD01..RTD08
        rtd_pins[SD_PINS[15 + i]] = 'RTD%02d_LS' % i
        afe_rtd += [R(rx('R'), '1k', a=lead, b='RTD%02d_LS' % i), C(rx('C'), '100n', a='RTD%02d_LS' % i, b=GND)]
rtd_pins[SD_PINS[24]] = 'RTD_REF_F'
afe_rtd += [P(rx('U'), 'Reference_Current:LM334SM', 'LM334 (ST) 0.5 mA ref', pins={'3': '+5V', '2': 'RTDREF_RSET', '1': 'RTD_REF'}, mfr='STMicroelectronics', mpn='LM334DT'),
            R(rx('R'), '136', '0603', a='RTDREF_RSET', b='RTD_REF'), R(rx('R'), '1k 0.01% (Vishay-free: Susumu RG / Isabellenhuette)', '0603', a='RTD_REF', b=GND),
            R(rx('R'), '1k', a='RTD_REF', b='RTD_REF_F'), C(rx('C'), '100n', a='RTD_REF_F', b=GND)]
afe_rtd = [P(rx('U'), 'MCU_ST_STM32F3:STM32F373VCTx', 'STM32F373VCT6 (RTD AFE)', pins=rtd_pins, default_nc=True, **mm('STM32F373VCT6'))] + afe_rtd
afe_rtd += decaps(rx, '+3V3', GND, n=4, bulk='4.7u') + [C(rx('C'), '1u', a='+3V3_SD', b=GND), C(rx('C'), '100n', a='+3V3_SD', b=GND)]
afe_rtd += swd(rx, '+3V3', GND, 'RTDAFE_SWDIO', 'RTDAFE_SWCLK', 'NC', 'AFE_NRST', 'SWD RTD AFE')
afe_rtd += [R(rx('R'), '10k', a='AFE_NRST', b='+3V3')]

# ================================================================================================= 4-20 mA inputs (24) + fast inputs (FAI1/2)
ai = []


def loop_channel(tag, adc, fast=False, volt=False):
    """2-wire 4-20 mA loop: +24V_LOOP via PTC to the transmitter, return through a 49.9 R 0.1 % shunt; RC into the ADC, 3.3 V clamp."""
    sup, ret = tag + '_LOOP+', tag + '_RET'
    parts = [P(rx('F'), 'Device:Polyfuse', '50mA', 'Fuse:Fuse_0805_2012Metric', pins={'1': '+24V_LOOP', '2': sup}, mfr='Schurter', mpn='PFRA.005')]
    if volt:                                                                      # AI16 ZT-101: 2-10 V signal -> 20k/6.8k divider
        parts += [R(rx('R'), '20k 0.1%', '0603', a=ret, b=adc + '_X'), R(rx('R'), '6k8 0.1%', '0603', a=adc + '_X', b=GND), R(rx('R'), '1k', a=adc + '_X', b=adc)]
    else:
        parts += [R(rx('R'), '49.9 0.1%', '0805', a=ret, b=GND, mfr='Isabellenhuette / Susumu', mpn='RG2012P-49R9-B-T5'), R(rx('R'), '1k', a=ret, b=adc)]
    parts += [C(rx('C'), '1n' if fast else '100n', a=adc, b=GND),
              D(rx('D'), 'BZT52C3V3', 'SOD-123', k=adc, a=GND, kind='D_Zener', mfr='Nexperia', mpn='BZT52H-C3V3'),
              P(rx('D'), 'Device:D_TVS', 'SMAJ33CA', 'Diode_SMD:D_SMA', pins={'A1': sup, 'A2': GND}, **mm('SMAJ33CA'))]
    return parts


for i in range(1, 25):
    ai += loop_channel('AI%02d_%s' % (i, AI[i]), 'AI%02d_ADC' % i, volt=(i == 16))
for tag, adc in (('FAI1_PT521', 'FAI1_ADC'), ('FAI2_PT605', 'FAI2_ADC'), ('FAI3_SPARE', 'FAI3_ADC'), ('FAI4_SPARE', 'FAI4_ADC')):
    ai += loop_channel(tag, adc, fast=True)

# ================================================================================================= IEPE accelerometers (VIB1..VIB3)
iepe = []
for i in range(1, 4):
    t = 'VIB%d' % i
    sens, ac, g, adc = t + '_SENS', t + '_AC', t + '_G', t + '_ADC'
    iepe += [P(rx('U'), 'Regulator_Linear:LM317_SOT-223', 'LM317 (ST) 4 mA source', F_SOT223, pins={'VI': '+24V', 'VO': t + '_VO', 'ADJ': sens}, **mm('LM317')),
             R(rx('R'), '312 (1.25 V / 4 mA)', '0805', a=t + '_VO', b=sens), C(rx('C'), '100n/50V', '0603', a='+24V', b=GND),
             P(rx('D'), 'Device:D_TVS', 'SMAJ26CA', 'Diode_SMD:D_SMA', pins={'A1': sens, 'A2': GND}, mfr='STMicroelectronics', mpn='SMAJ26CA-TR'),
             # AC path: 10 uF coupling, gain 2 non-inverting around VMID, 2-pole RC ~10 kHz into the ADC
             C(rx('C'), '10u/50V', '1206', a=sens, b=ac), R(rx('R'), '1M', '0603', a=ac, b='VMID'),
             opamp_dual(rx, 'TSV912 (IEPE %d)' % i, 'TSV912', dict(OUT1=g, **{'IN1-': g + '_FB', 'IN1+': ac}, OUT2=t + '_BUF', **{'IN2-': t + '_BUF', 'IN2+': g + '_LP'}, **{'V+': '+3V3A', 'V-': GND}),
                        fp='Package_TO_SOT_SMD:SOT-23-8'),
             R(rx('R'), '10k', a=g, b=g + '_FB'), R(rx('R'), '10k', a=g + '_FB', b='VMID'),
             R(rx('R'), '1k6', a=g, b=g + '_LP'), C(rx('C'), '10n', a=g + '_LP', b=GND), R(rx('R'), '100', a=t + '_BUF', b=adc), C(rx('C'), '1n', a=adc, b=GND),
             C(rx('C'), '100n', a='+3V3A', b=GND),
             # bias window (8..20 V on the sensor line = sensor present and not shorted): divider 1/10 + LM2903 (ST) window comparator, open-collector wired-AND
             R(rx('R'), '90k', '0603', a=sens, b=t + '_BDIV'), R(rx('R'), '10k', a=t + '_BDIV', b=GND), C(rx('C'), '100n', a=t + '_BDIV', b=GND),
             P(rx('U'), 'Comparator:LM2903', 'LM2903 (ST) bias window', F_SOIC8, pins={'1': t + '_BIAS_OK', '2': 'VTH_0V8', '3': t + '_BDIV', '7': t + '_BIAS_OK', '6': t + '_BDIV', '5': 'VTH_2V0',
                                                                                     'V+': '+3V3A', 'V-': GND}, **mm('LM2903')),
             R(rx('R'), '10k', a=t + '_BIAS_OK', b='+3V3')]
iepe += [R(rx('R'), '31k6', '0603', a='+3V3A', b='VTH_0V8'), R(rx('R'), '10k', a='VTH_0V8', b=GND), R(rx('R'), '6k49', '0603', a='+3V3A', b='VTH_2V0'), R(rx('R'), '10k', a='VTH_2V0', b=GND)]

# ================================================================================================= Pulse inputs FI01..FI06 + RS-422 re-transmit of FI01
fi = []
for i in range(1, 7):
    raw, lv = 'FI%02d_%s_IN24' % (i, FI[i]), 'FI%02d_LV' % i
    fi += [R(rx('R'), '2k2 0.5W', '1206', a='+24V_FLD', b=raw), R(rx('R'), '15k', a=raw, b=lv), R(rx('R'), '3k3', a=lv, b=GND), C(rx('C'), '1n', a=lv, b=GND),
           D(rx('D'), 'BZT52C3V6', 'SOD-123', k=lv, a=GND, kind='D_Zener', mfr='Nexperia', mpn='BZT52H-C3V6'),
           P(rx('D'), 'Device:D_TVS', 'SMAJ33CA', 'Diode_SMD:D_SMA', pins={'A1': raw, 'A2': GND}, **mm('SMAJ33CA')),
           P(rx('U'), '74xGxx:74LVC1G17', '74LVC1G17', 'Package_TO_SOT_SMD:SOT-353_SC-70-5', pins={'2': lv, '4': 'FI%02d_IN' % i, 'VCC': '+3V3', 'GND': GND}, **mm('74LVC1G17'))]
fi += [P(rx('U'), ST26C31, 'ST26C31 (N1-A -> B1 SPD-IN1, W102a)', pins={'1A': 'FI01_IN', '1Y': 'N1A_422_A', '1Z': 'N1A_422_B', '2A': 'FI03_IN', '2Y': 'FI03_422_A', '2Z': 'FI03_422_B',
                                                                     '3A': GND, '3Y': 'NC', '3Z': 'NC', '4A': GND, '4Y': 'NC', '4Z': 'NC', 'G': '+3V3', '~{G}': GND, 'VCC': '+3V3', 'GND': GND},
         **mm('ST26C31')), C(rx('C'), '100n', a='+3V3', b=GND),
       P(rx('D'), 'Device:D_TVS_Dual_AAC', 'ESD RS-422', 'Package_TO_SOT_SMD:SOT-23', pins={'A1': 'N1A_422_A', 'A2': 'N1A_422_B', 'common': GND}, mfr='Nexperia', mpn='PESD5V0X2UM')]

# ================================================================================================= Digital inputs (32x)
dio = []
for k in range(4):
    nets = ['DI%02d_%s' % (8 * k + i + 1, DI[8 * k + i + 1]) for i in range(8)]
    dio += di_bank(rx, 'B%d' % (k + 1), nets, '+24V_FLD', 'GND_FLD', '+3V3', GND, 'SPI2_SCK', 'SPI2_MOSI', 'SPI2_MISO', 'DI_CS%d' % (k + 1), 'DI_RST',
                   'DI_RDY%d' % (k + 1), 'DI_FAULT')
dio += [R(rx('R'), '10k', a='DI_FAULT', b='+3V3'), R(rx('R'), '10k', a='DI_RST', b='+3V3')]

# ================================================================================================= CAN-FD #1 (engine bus)
can = iso_can(rx, 'ENG', 'CAN1_TX', 'CAN1_RX', 'CAN1_STB', '+3V3', GND, '+5V', 'CAN1_H', 'CAN1_L', 'GND_CAN1', term_jumper=True)

# ================================================================================================= Connectors
conn = [terminal(rx('J'), ['CAN1_H', 'CAN1_L', 'GND_CAN1', 'PE'], 'W101 CAN-FD #1 engine', pitch=3.81),
        terminal(rx('J'), ['N1A_422_A', 'N1A_422_B', 'FI03_422_A', 'FI03_422_B', GND, 'PE'], 'W102a RS-422 N1-A (+FI03 spare) to B1', pitch=3.81)]
for k in range(2):
    nets = []
    for i in range(6 * k + 1, 6 * k + 7):
        nets += ['TC%02d_%s_P' % (i, TC[i]), 'TC%02d_%s_N' % (i, TC[i])]
    conn.append(terminal(rx('J'), nets, 'TC%02d..TC%02d (isothermal block, CJC%d)' % (6 * k + 1, 6 * k + 6, k + 1), pitch=3.81))
for k in range(4):
    nets = []
    for i in range(4 * k + 1, 4 * k + 5):
        nets += ['RTD%02d_%s_EXC' % (i, RTD[i]), 'RTD%02d_%s_RET' % (i, RTD[i]), GND]
    conn.append(terminal(rx('J'), nets, 'RTD%02d..RTD%02d 3-wire (EXC, RET sense, GND)' % (4 * k + 1, 4 * k + 4), pitch=3.81))
for k in range(4):
    nets = []
    for i in range(6 * k + 1, 6 * k + 7):
        nets += ['AI%02d_%s_LOOP+' % (i, AI[i]), 'AI%02d_%s_RET' % (i, AI[i])]
    conn.append(terminal(rx('J'), nets, 'AI%02d..AI%02d 4-20 mA (loop+, return)' % (6 * k + 1, 6 * k + 6)))
conn.append(terminal(rx('J'), ['FAI1_PT521_LOOP+', 'FAI1_PT521_RET', 'FAI2_PT605_LOOP+', 'FAI2_PT605_RET', 'FAI3_SPARE_LOOP+', 'FAI3_SPARE_RET', 'FAI4_SPARE_LOOP+', 'FAI4_SPARE_RET'],
                     'FAI1..FAI4 fast 4-20 mA'))
conn.append(terminal(rx('J'), ['VIB1_SENS', GND, 'VIB2_SENS', GND, 'VIB3_SENS', GND, 'PE', 'PE'], 'VIB1..VIB3 IEPE (M12 2-pin cordsets)'))
for k in range(4):
    nets = ['DI%02d_%s' % (8 * k + i + 1, DI[8 * k + i + 1]) for i in range(8)]
    conn.append(terminal(rx('J'), nets + ['+24V_FLD', 'GND_FLD'], 'DI%02d..DI%02d' % (8 * k + 1, 8 * k + 8)))
fin = []
for i in range(1, 7):
    fin += ['+24V_FLD', 'FI%02d_%s_IN24' % (i, FI[i]), GND]
conn.append(terminal(rx('J'), fin[:9] + ['PE'], 'FI01..FI03 (24V, pulse, GND)'))
conn.append(terminal(rx('J'), fin[9:] + ['PE'], 'FI04..FI06 (24V, pulse, GND)'))

BOARD = Board(
    name='b2_sio', title='GR180-CCHP B2 sensor I/O', rev='0.2', company='GR180-CCHP', paper='A2',
    sheets=[Sheet('Power', parts=power), Sheet('MCU', parts=mcu), Sheet('AFE_TC', parts=afe_tc), Sheet('AFE_RTD', parts=afe_rtd), Sheet('AI_4_20mA', parts=ai),
            Sheet('IEPE', parts=iepe), Sheet('Pulse_Inputs', parts=fi), Sheet('Digital_Inputs', parts=dio), Sheet('CAN', parts=can), Sheet('Connectors', parts=conn)],
    pcb=dict(w=220, h=160, holes='M3', hole_inset=4, layers=4, corner_radius=2),
    power_flags='auto', erc_pin_map={('power_out', 'power_out'): 'warning'},
    comments=['B2 sensor I/O rev 0.2 - European parts (docs/electrical/04 §2); channels per 02_io_list.csv'],
)
