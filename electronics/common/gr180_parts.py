# -*- coding: utf-8 -*-
"""GR180-CCHP shared part library for the schgen board specs (European parts only, docs/electrical/04).

Generated symbols (G) for ICs that have no stock KiCad symbol, plus helper functions that return lists of parts for the
circuits that repeat on every board (decoupling, crystal, SWD, isolated CAN, isolated RS-485, 24 V DI banks, relay outputs,
protected 24 V / 48 V inputs). Every helper takes a Refs counter so references stay unique per board.

Pin tables of the generated symbols come from the manufacturer datasheets as far as they are known here; the ones marked
'VERIFY' are functional symbols whose pin NUMBERS must be checked against the datasheet before layout (the pin NAMES and the
netlist are what the schematic carries). Footprints are KiCad stock names where they exist, else ''.
"""
from schgen import P, R, C, L, D, G

MPN = {   # mpn, mfr, lcsc  (docs/electrical/04, queried 2026-10-21)
    'STM32H743IIT6': ('STM32H743IIT6', 'STMicroelectronics', 'C89597'),
    'STM32H743VIT6': ('STM32H743VIT6', 'STMicroelectronics', 'C114409'),
    'STM32F373VCT6': ('STM32F373VCT6', 'STMicroelectronics', 'C1121903'),
    'STM32G474RET6': ('STM32G474RET6', 'STMicroelectronics', 'C521608'),
    'STM32G0B1KET6': ('STM32G0B1KET6', 'STMicroelectronics', ''),
    'MKE16Z64VLF4': ('MKE16Z64VLF4', 'NXP', 'C1339264'),
    'TJA1052i-5': ('TJA1052IT/5Y', 'NXP', 'C92210'),
    'TJA1051T-3': ('TJA1051T/3,118', 'NXP', 'C38695'),
    'ST485E': ('ST485EBDR', 'STMicroelectronics', 'C81186'),
    'STISO621': ('STISO621TR', 'STMicroelectronics', 'C5447162'),
    'STISO620': ('STISO620TR', 'STMicroelectronics', 'C7089838'),
    'ST26C32': ('ST26C32ABDR', 'STMicroelectronics', 'C157432'),
    'ST26C31': ('ST26C31BDR', 'STMicroelectronics', 'C94192'),
    'ISO1I813T': ('ISO1I813TXUMA1', 'Infineon', 'C538445'),
    'ULN2803A': ('ULN2803A', 'STMicroelectronics', ''),
    'ULN2003A': ('ULN2003A', 'STMicroelectronics', 'C61273'),
    'M95M04': ('M95M04-DRMN6TP', 'STMicroelectronics', 'C1852765'),
    'W25Q128': ('W25Q128JVSIQ', 'Winbond (TW, non-EU exception)', 'C97521'),
    'STWD100': ('STWD100NYWY3F', 'STMicroelectronics', 'C46043'),
    'R-78E5.0-1.0': ('R-78E5.0-1.0', 'RECOM', ''),
    'R-78HB12-0.5': ('R-78HB12-0.5', 'RECOM', ''),
    'R1SX-0505': ('R1SX-0505', 'RECOM', ''),
    'R24P21503D': ('R24P21503D', 'RECOM', ''),
    'LD1117S33': ('LD1117S33TR', 'STMicroelectronics', 'C86781'),
    'LDL1117S33': ('LDL1117S33R', 'STMicroelectronics', 'C435835'),
    'RTL8201F': ('RTL8201F-VB-CG', 'Realtek (TW, non-EU exception)', 'C45044'),
    'RJ45-MAG': ('7499010211A', 'Wuerth Elektronik', ''),
    'FINDER-34.51': ('34.51.7.024.0010', 'Finder', ''),
    'FINDER-50.12': ('50.12.9.024.1000', 'Finder', ''),
    'TSV912': ('TSV912IST', 'STMicroelectronics', 'C2057297'),
    'TSZ122': ('TSZ122IST', 'STMicroelectronics', 'C52941316'),
    'TSB572': ('TSB572IST', 'STMicroelectronics', 'C2060321'),
    'LM317': ('LM317D2T-TR', 'STMicroelectronics', 'C91673'),
    'LM2903': ('LM2903YDT', 'STMicroelectronics', ''),
    'SMBJ33A': ('SMBJ33A-TR', 'STMicroelectronics', 'C133662'),
    'SMCJ58CA': ('SMCJ58CA-TR', 'STMicroelectronics', 'C310064'),
    'SMAJ33CA': ('SMAJ33CA-TR', 'STMicroelectronics', 'C115251'),
    'PESD2CANFD24V': ('PESD2CANFD24V-T', 'Nexperia', 'C552486'),
    'WE-SL5': ('744235510', 'Wuerth Elektronik', 'C5331174'),
    'IPB017N10N5': ('IPB017N10N5LFATMA1', 'Infineon', 'C536479'),
    'BSC0xxN10': ('BSC050N10NS5ATMA1', 'Infineon', ''),
    'IMZA120R020M1H': ('IMZA120R020M1HXKSA1', 'Infineon', 'C7207676'),
    'IDW20G120C5B': ('IDW20G120C5BFKSA1', 'Infineon', 'C49450342'),
    '1ED3491': ('1ED3491MU12MXUMA1', 'Infineon', 'C530929'),
    '6EDL7141': ('6EDL7141XUMA1', 'Infineon', 'C3655737'),
    'VNI4140K': ('VNI4140KTR', 'STMicroelectronics', 'C2688485'),
    'IPS1025H': ('IPS1025HTR-32', 'STMicroelectronics', 'C5268124'),
    'IKW40N120H3': ('IKW40N120H3FKSA1', 'Infineon', 'C94637'),
    'STGAP2SM': ('STGAP2SMTR', 'STMicroelectronics', 'C2802542'),
    'VIPer26LD': ('VIPER26LDTR', 'STMicroelectronics', ''),
    'SKD30/12': ('SKD 30/12 A1', 'Semikron Danfoss', ''),
    'LEM-HO50': ('HO 50-S/SP33-1106', 'LEM', ''),
    'LEM-DVL1000': ('DVL 1000', 'LEM', ''),
    'C195': ('C195 A/24EV', 'Schaltbau', ''),
    '74LVC1G17': ('74LVC1G17GW', 'Nexperia', ''),
    '74LVC2G17': ('74LVC2G17GV', 'Nexperia', ''),
    'US5881': ('US5881LUA', 'Melexis', ''),
    'CRYSTAL-25M': ('CM9V-T1A-25.000MHz', 'Micro Crystal', ''),
    'CRYSTAL-8M': ('CM9V-T1A-8.000MHz', 'Micro Crystal', ''),
    'CRYSTAL-32K': ('CM8V-T1A-32.768kHz', 'Micro Crystal', ''),
    'PHOENIX-MSTBA': ('MSTBA 2,5/x-G-5,08', 'Phoenix Contact', ''),
    'PHOENIX-MC': ('MC 1,5/x-G-3,81', 'Phoenix Contact', ''),
    'PHOENIX-PC': ('PC 6/x-G1-7,62', 'Phoenix Contact', ''),
    'SWD-HDR': ('20021111-00010T4LF', 'Amphenol ICC (FR site; alt. Harwin M50-3600542 UK)', ''),
    'SW-TACT': ('PTS645SM43SMTR92', 'C&K (FR/CH)', ''),
}


def mm(key):
    """Keyword args mpn/mfr/lcsc for MPN[key]."""
    m, f, l = MPN[key]
    return dict(mpn=m, mfr=f, lcsc=l)


class Refs:
    """Unique reference designators per board: rx('C') -> 'C1', 'C2', ..."""

    def __init__(self, start=None):
        self.n = dict(start or {})

    def __call__(self, prefix):
        self.n[prefix] = self.n.get(prefix, 0) + 1
        return '%s%d' % (prefix, self.n[prefix])


# ----------------------------------------------------------------------------------------------- generated symbols
STISO621 = G('STISO621', ref='U', footprint='Package_SO:SOIC-8_7.5x5.85mm_P1.27mm',
             description='ST STISO621 dual-channel digital isolator, 1 forward + 1 reverse, 5 kV, SO8W',
             pins=[('1', 'VDD1', 'power_in', 'L'), ('2', 'INA', 'input', 'L'), ('3', 'OUTB', 'output', 'L'), ('4', 'GND1', 'power_in', 'L'),
                   ('8', 'VDD2', 'power_in', 'R'), ('7', 'OUTA', 'output', 'R'), ('6', 'INB', 'input', 'R'), ('5', 'GND2', 'power_in', 'R')])
STISO620 = G('STISO620', ref='U', footprint='Package_SO:SOIC-8_7.5x5.85mm_P1.27mm',
             description='ST STISO620 dual-channel digital isolator, both forward, 5 kV, SO8W',
             pins=[('1', 'VDD1', 'power_in', 'L'), ('2', 'INA', 'input', 'L'), ('3', 'INB', 'input', 'L'), ('4', 'GND1', 'power_in', 'L'),
                   ('8', 'VDD2', 'power_in', 'R'), ('7', 'OUTA', 'output', 'R'), ('6', 'OUTB', 'output', 'R'), ('5', 'GND2', 'power_in', 'R')])
ST26C32 = G('ST26C32', ref='U', footprint='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',
            description='ST ST26C32 quad RS-422 differential line receiver (AM26LV32 pinout)',
            pins=[('2', '1A', 'input', 'L'), ('1', '1B', 'input', 'L'), ('6', '2A', 'input', 'L'), ('7', '2B', 'input', 'L'),
                  ('10', '3A', 'input', 'L'), ('9', '3B', 'input', 'L'), ('14', '4A', 'input', 'L'), ('15', '4B', 'input', 'L'),
                  ('3', '1Y', 'output', 'R'), ('5', '2Y', 'output', 'R'), ('11', '3Y', 'output', 'R'), ('13', '4Y', 'output', 'R'),
                  ('4', 'G', 'input', 'R'), ('12', '~{G}', 'input', 'R'), ('16', 'VCC', 'power_in', 'T'), ('8', 'GND', 'power_in', 'B')])
ST26C31 = G('ST26C31', ref='U', footprint='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',
            description='ST ST26C31 quad RS-422 differential line driver (AM26LV31 pinout)',
            pins=[('1', '1A', 'input', 'L'), ('7', '2A', 'input', 'L'), ('9', '3A', 'input', 'L'), ('15', '4A', 'input', 'L'),
                  ('2', '1Y', 'output', 'R'), ('3', '1Z', 'output', 'R'), ('6', '2Y', 'output', 'R'), ('5', '2Z', 'output', 'R'),
                  ('10', '3Y', 'output', 'R'), ('11', '3Z', 'output', 'R'), ('14', '4Y', 'output', 'R'), ('13', '4Z', 'output', 'R'),
                  ('4', 'G', 'input', 'L'), ('12', '~{G}', 'input', 'L'), ('16', 'VCC', 'power_in', 'T'), ('8', 'GND', 'power_in', 'B')])
M95M04 = G('M95M04', ref='U', footprint='Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',
           description='ST M95M04-DR 4 Mbit SPI EEPROM, 4 M cycles (life counter ring buffer)',
           pins=[('1', '~{S}', 'input', 'L'), ('2', 'Q', 'output', 'L'), ('3', '~{W}', 'input', 'L'), ('4', 'VSS', 'power_in', 'B'),
                 ('5', 'D', 'input', 'R'), ('6', 'C', 'input', 'R'), ('7', '~{HOLD}', 'input', 'R'), ('8', 'VCC', 'power_in', 'T')])
STWD100 = G('STWD100', ref='U', footprint='Package_TO_SOT_SMD:SOT-23-5',
            description='ST STWD100 window watchdog, SOT23-5. VERIFY pin numbers against the datasheet before layout',
            pins=[('1', 'WDI', 'input', 'L'), ('2', 'GND', 'power_in', 'B'), ('3', '~{EN}', 'input', 'L'), ('4', '~{WDO}', 'open_collector', 'R'),
                  ('5', 'VCC', 'power_in', 'T')])
ISO1I813T = G('ISO1I813T', ref='U', footprint='Package_SO:ST_PowerSSO-36_SlugDown',
              description='Infineon ISO1I813T 8-channel isolated 24 V digital input, IEC 61131-2 type 1/3, SPI. '
                          'FUNCTIONAL symbol: pin numbers VERIFY against the PG-DSO-36 datasheet',
              pins=[('1', 'IN0', 'input', 'L'), ('2', 'IN1', 'input', 'L'), ('3', 'IN2', 'input', 'L'), ('4', 'IN3', 'input', 'L'),
                    ('5', 'IN4', 'input', 'L'), ('6', 'IN5', 'input', 'L'), ('7', 'IN6', 'input', 'L'), ('8', 'IN7', 'input', 'L'),
                    ('9', 'VBB', 'power_in', 'L'), ('10', 'GNDF', 'power_in', 'L'), ('11', 'LED', 'output', 'L'),
                    ('20', 'VCC', 'power_in', 'R'), ('21', 'GND', 'power_in', 'R'), ('22', 'SCLK', 'input', 'R'), ('23', 'SI', 'input', 'R'),
                    ('24', 'SO', 'tri_state', 'R'), ('25', '~{CS}', 'input', 'R'), ('26', '~{RST}', 'input', 'R'), ('27', 'RDY', 'output', 'R'),
                    ('28', '~{FAULT}', 'open_collector', 'R')])
R1SX0505 = G('R1SX-0505', ref='U', footprint='',
             description='RECOM R1SX-0505 1 W isolated 5 V -> 5 V DC-DC, SIP4, 3 kV',
             pins=[('1', '+VIN', 'power_in', 'L'), ('2', '-VIN', 'power_in', 'L'), ('4', '+VOUT', 'power_out', 'R'), ('3', '-VOUT', 'power_out', 'R')])
R24P21503D = G('R24P21503D', ref='U', footprint='',
               description='RECOM R24P21503D 2 W isolated gate-drive supply, 24 V -> +15 V / -3 V, 5.2 kV. VERIFY pin numbers',
               pins=[('1', '+VIN', 'power_in', 'L'), ('2', '-VIN', 'power_in', 'L'), ('5', '+VOUT', 'power_out', 'R'), ('4', 'COM', 'power_out', 'R'),
                     ('3', '-VOUT', 'power_out', 'R')])
RTL8201F = G('RTL8201F', ref='U', footprint='Package_DFN_QFN:UQFN-32_5x5mm_P0.5mm',
             description='Realtek RTL8201F-VB-CG 10/100 Ethernet PHY, RMII (non-EU exception). FUNCTIONAL symbol: pin numbers VERIFY',
             pins=[('1', 'TXD0', 'input', 'L'), ('2', 'TXD1', 'input', 'L'), ('3', 'TXEN', 'input', 'L'), ('4', 'RXD0', 'output', 'L'),
                   ('5', 'RXD1', 'output', 'L'), ('6', 'CRS_DV', 'output', 'L'), ('7', 'RXER', 'output', 'L'), ('8', 'REF_CLK', 'bidirectional', 'L'),
                   ('9', 'MDC', 'input', 'L'), ('10', 'MDIO', 'bidirectional', 'L'), ('11', '~{RESET}', 'input', 'L'), ('12', 'INT/CLKOUT', 'output', 'L'),
                   ('13', 'TXP', 'bidirectional', 'R'), ('14', 'TXN', 'bidirectional', 'R'), ('15', 'RXP', 'bidirectional', 'R'), ('16', 'RXN', 'bidirectional', 'R'),
                   ('17', 'XTAL1', 'input', 'R'), ('18', 'XTAL2', 'output', 'R'), ('19', 'LED0', 'output', 'R'), ('20', 'LED1', 'output', 'R'),
                   ('21', 'RSET', 'passive', 'R'), ('22', 'VDDIO', 'power_in', 'T'), ('23', 'AVDD33', 'power_in', 'T'), ('24', 'DVDD', 'power_out', 'T'),
                   ('25', 'GND', 'power_in', 'B'), ('26', 'GND', 'power_in', 'B')])
RJ45_MAG = G('RJ45_MAG_7499010211A', ref='J', footprint='Connector_RJ:RJ45_Wuerth_7499010121A_Horizontal',
             description='Wuerth 7499010211A RJ45 with 10/100 magnetics and 2 LEDs (footprint of the 7499010121A family: VERIFY)',
             pins=[('1', 'TD+', 'bidirectional', 'L'), ('2', 'TD-', 'bidirectional', 'L'), ('3', 'TCT', 'passive', 'L'), ('4', 'RD+', 'bidirectional', 'L'),
                   ('5', 'RD-', 'bidirectional', 'L'), ('6', 'RCT', 'passive', 'L'), ('7', 'LED1_A', 'passive', 'R'), ('8', 'LED1_K', 'passive', 'R'),
                   ('9', 'LED2_A', 'passive', 'R'), ('10', 'LED2_K', 'passive', 'R'), ('11', 'SHLD', 'passive', 'B'), ('12', 'SHLD', 'passive', 'B')])
FINDER5012 = G('FINDER_50.12', ref='K', footprint='',
               description='Finder 50.12.9.024.1000 force-guided relay, 2 CO (EN 61810-3), 24 V DC coil',
               pins=[('A1', 'A1', 'passive', 'L'), ('A2', 'A2', 'passive', 'L'), ('11', '11', 'passive', 'R'), ('12', '12', 'passive', 'R'),
                     ('14', '14', 'passive', 'R'), ('21', '21', 'passive', 'R'), ('22', '22', 'passive', 'R'), ('24', '24', 'passive', 'R')])
STEF01 = G('STEF01', ref='U', footprint='',
           description='ST STEF01 8-48 V electronic fuse (DFN10). FUNCTIONAL symbol: pin numbers VERIFY',
           pins=[('1', 'IN', 'power_in', 'L'), ('2', 'IN', 'passive', 'L'), ('3', 'EN/FAULT', 'bidirectional', 'L'), ('4', 'ISET', 'passive', 'L'),
                 ('5', 'dv/dt', 'passive', 'L'), ('6', 'GND', 'power_in', 'B'), ('7', 'OUT', 'power_out', 'R'), ('8', 'OUT', 'passive', 'R'),
                 ('9', 'ILIM', 'passive', 'R'), ('10', 'GATE', 'passive', 'R')])
SKD3012 = G('SKD30_12', ref='D', footprint='',
            description='Semikron Danfoss SKD 30/12 A1 three-phase bridge rectifier 1200 V 30 A',
            pins=[('U', 'U', 'passive', 'L'), ('V', 'V', 'passive', 'L'), ('W', 'W', 'passive', 'L'), ('+', '+', 'passive', 'R'), ('-', '-', 'passive', 'R')])
COOLSIC4 = G('CoolSiC_TO247-4', ref='Q', footprint='Package_TO_SOT_THT:TO-247-4_Vertical',
             description='Infineon IMZA120R020M1H CoolSiC MOSFET 1200 V 20 mohm, TO-247-4 with Kelvin source',
             pins=[('1', 'G', 'input', 'L'), ('2', 'D', 'passive', 'T'), ('3', 'S', 'passive', 'B'), ('4', 'KS', 'passive', 'L')])
GD1ED3491 = G('1ED3491MU12M', ref='U', footprint='Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
              description='Infineon 1ED3491MU12M isolated SiC gate driver with DESAT, soft-off, Miller clamp. FUNCTIONAL symbol: pin numbers VERIFY',
              pins=[('1', 'VCC1', 'power_in', 'L'), ('2', 'IN+', 'input', 'L'), ('3', 'IN-', 'input', 'L'), ('4', 'RDY', 'open_collector', 'L'),
                    ('5', '~{FLT}', 'open_collector', 'L'), ('6', '~{RST}', 'input', 'L'), ('7', 'GND1', 'power_in', 'L'), ('8', 'NC', 'no_connect', 'L'),
                    ('16', 'VCC2', 'power_in', 'R'), ('15', 'OUT', 'output', 'R'), ('14', 'CLAMP', 'output', 'R'), ('13', 'DESAT', 'input', 'R'),
                    ('12', 'GND2', 'power_in', 'R'), ('11', 'VEE2', 'power_in', 'R'), ('10', 'OFF', 'output', 'R'), ('9', 'NC', 'no_connect', 'R')])
LEM_HO50 = G('LEM_HO50-S', ref='U', footprint='',
             description='LEM HO 50-S/SP33 open-loop Hall current transducer, 3.3 V, 50 A nominal',
             pins=[('1', 'VC', 'power_in', 'T'), ('2', 'GND', 'power_in', 'B'), ('3', 'VOUT', 'output', 'R'), ('4', 'VREF', 'bidirectional', 'R'),
                   ('5', '~{OCD}', 'open_collector', 'R')])
LEM_DVL1000 = G('LEM_DVL1000', ref='U', footprint='',
                description='LEM DVL 1000 isolated voltage transducer, +/-1000 V, 4-20 mA / +/-50 mA output. VERIFY output type',
                pins=[('1', 'HT+', 'input', 'L'), ('2', 'HT-', 'input', 'L'), ('3', '+VC', 'power_in', 'T'), ('4', '-VC', 'power_in', 'B'),
                      ('5', 'OUT', 'output', 'R'), ('6', '0V', 'passive', 'R')])
VNI4140K = G('VNI4140K', ref='U', footprint='Package_SO:PowerSSO-16-1EP_3.9x4.9mm_P0.5mm_EP2.5x3.61mm',
             description='ST VNI4140K quad high-side driver 24 V 0.7 A with diagnostics. FUNCTIONAL symbol: pin numbers VERIFY',
             pins=[('1', 'IN1', 'input', 'L'), ('2', 'IN2', 'input', 'L'), ('3', 'IN3', 'input', 'L'), ('4', 'IN4', 'input', 'L'),
                   ('5', 'GND', 'power_in', 'B'), ('6', '~{FAULT}', 'open_collector', 'L'), ('7', 'STATUS', 'output', 'L'), ('8', 'VCC', 'power_in', 'T'),
                   ('9', 'OUT1', 'power_out', 'R'), ('10', 'OUT2', 'power_out', 'R'), ('11', 'OUT3', 'power_out', 'R'), ('12', 'OUT4', 'power_out', 'R'),
                   ('13', 'NC', 'no_connect', 'R'), ('14', 'NC', 'no_connect', 'R'), ('15', 'NC', 'no_connect', 'R'), ('16', 'NC', 'no_connect', 'R')])
IPS1025H = G('IPS1025H', ref='U', footprint='Package_SO:PowerSSO-16-1EP_3.9x4.9mm_P0.5mm_EP2.5x3.61mm',
             description='ST IPS1025H single-channel high-side switch 2.5 A with diagnostics. FUNCTIONAL symbol: pin numbers VERIFY',
             pins=[('1', 'IN', 'input', 'L'), ('2', 'GND', 'power_in', 'B'), ('3', 'VCC', 'power_in', 'T'), ('4', 'OUT', 'power_out', 'R'),
                   ('5', 'DIAG', 'open_collector', 'L')])
GD6EDL7141 = G('6EDL7141', ref='U', footprint='Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm',
               description='Infineon 6EDL7141 three-phase smart gate driver 48 V with 3 CSA and SPI. FUNCTIONAL symbol: pin numbers VERIFY',
               pins=[('1', 'PVDD', 'power_in', 'T'), ('2', 'VDDB', 'power_in', 'T'), ('3', 'DVDD', 'power_out', 'T'), ('4', 'GND', 'power_in', 'B'),
                     ('5', 'PGND', 'power_in', 'B'), ('6', 'CP1', 'passive', 'T'), ('7', 'CP2', 'passive', 'T'), ('8', 'VCP', 'passive', 'T'),
                     ('9', 'INHA', 'input', 'L'), ('10', 'INLA', 'input', 'L'), ('11', 'INHB', 'input', 'L'), ('12', 'INLB', 'input', 'L'),
                     ('13', 'INHC', 'input', 'L'), ('14', 'INLC', 'input', 'L'), ('15', 'EN_DRV', 'input', 'L'), ('16', '~{FAULT}', 'open_collector', 'L'),
                     ('17', '~{SCS}', 'input', 'L'), ('18', 'SCLK', 'input', 'L'), ('19', 'SDI', 'input', 'L'), ('20', 'SDO', 'output', 'L'),
                     ('21', 'CSO_A', 'output', 'L'), ('22', 'CSO_B', 'output', 'L'), ('23', 'CSO_C', 'output', 'L'),
                     ('24', 'GHA', 'output', 'R'), ('25', 'SHA', 'passive', 'R'), ('26', 'GLA', 'output', 'R'), ('27', 'GHB', 'output', 'R'),
                     ('28', 'SHB', 'passive', 'R'), ('29', 'GLB', 'output', 'R'), ('30', 'GHC', 'output', 'R'), ('31', 'SHC', 'passive', 'R'),
                     ('32', 'GLC', 'output', 'R'), ('33', 'SPA', 'input', 'R'), ('34', 'SNA', 'input', 'R'), ('35', 'SPB', 'input', 'R'),
                     ('36', 'SNB', 'input', 'R'), ('37', 'SPC', 'input', 'R'), ('38', 'SNC', 'input', 'R'), ('39', 'BRAKE', 'input', 'L'),
                     ('40', 'DIR', 'input', 'L'), ('41', 'nSLEEP', 'input', 'L')])
STM1001 = G('STM1001', ref='U', footprint='Package_TO_SOT_SMD:SOT-23',
            description='ST STM1001 voltage supervisor, open-drain active-low reset, SOT23-3',
            pins=[('1', '~{RST}', 'open_collector', 'R'), ('2', 'VCC', 'power_in', 'T'), ('3', 'GND', 'power_in', 'B')])
M12_8 = G('M12_A8', ref='J', footprint='', description='M12 A-coded 8-pin panel connector (Phoenix SACC-DSI-M12FS-8CON)',
          pins=[(str(i), str(i), 'passive', 'L') for i in range(1, 9)])
M12_5 = G('M12_A5', ref='J', footprint='', description='M12 A-coded 5-pin panel connector (Phoenix SACC-DSI-M12FS-5CON)',
          pins=[(str(i), str(i), 'passive', 'L') for i in range(1, 6)])
M12_4 = G('M12_A4', ref='J', footprint='', description='M12 A-coded 4-pin panel connector',
          pins=[(str(i), str(i), 'passive', 'L') for i in range(1, 5)])
TBUS5 = G('TBUS_5', ref='J', footprint='', description='Phoenix ME 22,5 TBUS 5-pin DIN-rail bus connector (1 +24V, 2 0V, 3 CANH, 4 CANL, 5 ADDR)',
          pins=[('1', '+24V', 'power_in', 'L'), ('2', '0V', 'power_in', 'L'), ('3', 'CANH', 'bidirectional', 'L'), ('4', 'CANL', 'bidirectional', 'L'),
                ('5', 'ADDR', 'passive', 'L')])
CT_SHUNT = G('Shunt_4W', ref='R', footprint='', description='Isabellenhuette 4-terminal shunt (BVR / PMx)',
             pins=[('1', 'I+', 'passive', 'L'), ('2', 'I-', 'passive', 'R'), ('3', 'S+', 'passive', 'T'), ('4', 'S-', 'passive', 'B')])
CM_CHOKE3 = G('CM_Choke_3ph', ref='L', footprint='', description='three-phase common-mode choke (Schaffner / Wuerth)',
              pins=[('1', 'U_IN', 'passive', 'L'), ('2', 'V_IN', 'passive', 'L'), ('3', 'W_IN', 'passive', 'L'),
                    ('4', 'U_OUT', 'passive', 'R'), ('5', 'V_OUT', 'passive', 'R'), ('6', 'W_OUT', 'passive', 'R')])

# footprints
F_PHX = {2: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
         4: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal',
         8: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-8-5.08_1x08_P5.08mm_Horizontal',
         10: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-10-5.08_1x10_P5.08mm_Horizontal',
         12: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-12-5.08_1x12_P5.08mm_Horizontal',
         16: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-16-5.08_1x16_P5.08mm_Horizontal'}
F_PHX381 = {2: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1-2-3.81_1x02_P3.81mm_Horizontal',
            4: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1-4-3.81_1x04_P3.81mm_Horizontal',
            8: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1-8-3.81_1x08_P3.81mm_Horizontal',
            10: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1-10-3.81_1x10_P3.81mm_Horizontal',
            12: 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1-12-3.81_1x12_P3.81mm_Horizontal'}
F_SOIC8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
F_D2PAK = 'Package_TO_SOT_SMD:TO-263-3_TabPin2'
F_SOT223 = 'Package_TO_SOT_SMD:SOT-223-3_TabPin2'
F_XTAL = 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm'
F_SWD = 'Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD'


# ----------------------------------------------------------------------------------------------- helpers
def terminal(ref, nets, value, pitch=5.08, **kw):
    """Phoenix pluggable terminal block with len(nets) poles (2..16); nets in pole order."""
    n = len(nets)
    if n <= 8:
        lib = 'Connector:Screw_Terminal_01x%02d' % n
    else:
        lib = 'Connector_Generic:Conn_01x%02d' % n
    fp = (F_PHX if pitch == 5.08 else F_PHX381).get(n, '')
    pins = {('%d' % (i + 1)): nets[i] for i in range(n)}
    kw.setdefault('mfr', 'Phoenix Contact')
    kw.setdefault('mpn', ('MSTBA 2,5/%d-G-5,08' if pitch == 5.08 else 'MC 1,5/%d-G-3,81') % n)
    return P(ref, lib, value, fp, pins=pins, **kw)


def decaps(rx, net, gnd, n=4, value='100n', bulk=None):
    out = [C(rx('C'), value, a=net, b=gnd) for _ in range(n)]
    if bulk:
        out.append(C(rx('C'), bulk, '0805', a=net, b=gnd))
    return out


def crystal(rx, net_in, net_out, gnd, freq='25MHz', load='12p', key='CRYSTAL-25M'):
    return [P(rx('Y'), 'Device:Crystal_GND24', freq, F_XTAL, pins={'1': net_in, '3': net_out, 'G': gnd}, **mm(key)),
            C(rx('C'), load, a=net_in, b=gnd), C(rx('C'), load, a=net_out, b=gnd)]


def crystal32k(rx, net_in, net_out, gnd):
    return [P(rx('Y'), 'Device:Crystal', '32.768kHz', 'Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm', pins={'1': net_in, '2': net_out}, **mm('CRYSTAL-32K')),
            C(rx('C'), '6p8', a=net_in, b=gnd), C(rx('C'), '6p8', a=net_out, b=gnd)]


def swd(rx, vdd, gnd, swdio, swclk, swo, nrst, value='SWD'):
    return [P(rx('J'), 'Connector:Conn_ARM_JTAG_SWD_10', value, F_SWD,
              pins={'VTref': vdd, 'SWDIO/TMS': swdio, 'SWCLK/TCK': swclk, 'SWO/TDO': swo, 'NC/TDI': 'NC', 'GND': gnd, 'GNDDetect': gnd,
                    '~{RESET}': nrst}, **mm('SWD-HDR')),
            P(rx('SW'), 'Switch:SW_Push', 'RESET', 'Button_Switch_SMD:SW_SPST_TL3342', pins={'1': nrst, '2': gnd}, **mm('SW-TACT')),
            C(rx('C'), '100n', a=nrst, b=gnd)]


def led(rx, net_anode_src, gnd, color='green', r='1k'):
    n = rx('LED')
    return [R(rx('R'), r, a=net_anode_src, b='LEDA_' + n), D(rx('D'), color, '0603', k=gnd, a='LEDA_' + n, kind='LED')]


def iso_can(rx, tag, txd, rxd, stb, vdd_logic, gnd_logic, v5_logic, canh, canl, gnd_bus, term_jumper=True):
    """Isolated CAN-FD channel: NXP TJA1052i-5 + RECOM R1SX-0505 bus-side supply + Wuerth CMC + Nexperia TVS + 120 R termination jumper."""
    vb, gb = 'VBUS5_' + tag, gnd_bus
    hb, lb = 'CANH_IC_' + tag, 'CANL_IC_' + tag
    parts = [
        P(rx('U'), R1SX0505, 'R1SX-0505', pins={'+VIN': v5_logic, '-VIN': gnd_logic, '+VOUT': vb, '-VOUT': gb}, **mm('R1SX-0505')),
        C(rx('C'), '4.7u', '0805', a=v5_logic, b=gnd_logic), C(rx('C'), '4.7u', '0805', a=vb, b=gb), C(rx('C'), '100n', a=vb, b=gb),
        P(rx('U'), 'Interface_CAN_LIN:TJA1052i-5', 'TJA1052i-5',
          pins={'VDD1': vdd_logic, 'GND1': gnd_logic, 'TXD': txd, 'RXD': rxd, 'VDD2': vb, 'GND2': gb, 'CANL': lb, 'CANH': hb, 'STB': stb},
          default_nc=True, **mm('TJA1052i-5')),
        C(rx('C'), '100n', a=vdd_logic, b=gnd_logic),
        P(rx('L'), 'Device:L_Coupled', 'WE-SL5 51uH', '', pins={'1': hb, '2': canh, '3': lb, '4': canl}, **mm('WE-SL5')),
        P(rx('D'), 'Device:D_TVS_Dual_AAC', 'PESD2CANFD24V', 'Package_TO_SOT_SMD:SOT-23', pins={'A1': canh, 'A2': canl, 'common': gb}, **mm('PESD2CANFD24V')),
        R(rx('R'), '2M', a=gb, b=gnd_logic), C(rx('C'), '4.7n/2kV', '1206', a=gb, b=gnd_logic),
    ]
    if term_jumper:
        parts += [R(rx('R'), '120', '0603', a=canh, b='CANT_' + tag),
                  P(rx('JP'), 'Connector_Generic:Conn_01x02', 'TERM ' + tag, 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
                    pins={'1': 'CANT_' + tag, '2': canl}, mfr='Wuerth', mpn='61300211121')]
    return parts


def iso_rs485(rx, tag, txd, rxd, de, vdd_logic, gnd_logic, v5_logic, a, b, gnd_bus, term=True):
    """Isolated RS-485 channel: ST485E on an isolated 5 V (RECOM R1SX-0505), ST STISO621 (TXD fwd + RXD rev) + STISO620 (DE, spare),
    bias + termination, TVS."""
    vb, gb = 'VISO5_' + tag, gnd_bus
    t, r, d = 'TXD_I_' + tag, 'RXD_I_' + tag, 'DE_I_' + tag
    parts = [
        P(rx('U'), R1SX0505, 'R1SX-0505', pins={'+VIN': v5_logic, '-VIN': gnd_logic, '+VOUT': vb, '-VOUT': gb}, **mm('R1SX-0505')),
        C(rx('C'), '4.7u', '0805', a=vb, b=gb), C(rx('C'), '100n', a=vb, b=gb),
        P(rx('U'), STISO621, 'STISO621', pins={'VDD1': vdd_logic, 'INA': txd, 'OUTB': rxd, 'GND1': gnd_logic, 'VDD2': vb, 'OUTA': t, 'INB': r, 'GND2': gb},
          **mm('STISO621')),
        P(rx('U'), STISO620, 'STISO620', pins={'VDD1': vdd_logic, 'INA': de, 'INB': gnd_logic, 'GND1': gnd_logic, 'VDD2': vb, 'OUTA': d, 'OUTB': 'NC', 'GND2': gb},
          **mm('STISO620')),
        C(rx('C'), '100n', a=vdd_logic, b=gnd_logic), C(rx('C'), '100n', a=vb, b=gb),
        P(rx('U'), 'Interface_UART:ST485E', 'ST485EB', F_SOIC8, pins={'RO': r, '~{RE}': d, 'DE': d, 'DI': t, 'GND': gb, 'A': a, 'B': b, 'VCC': vb},
          **mm('ST485E')),
        R(rx('R'), '680', '0603', a=vb, b=a), R(rx('R'), '680', '0603', a=b, b=gb),
        P(rx('D'), 'Device:D_TVS_Dual_AAC', 'SM712-equiv (ST ESDA)', 'Package_TO_SOT_SMD:SOT-23', pins={'A1': a, 'A2': b, 'common': gb},
          mfr='STMicroelectronics', mpn='ESDA25P35-1U1M? VERIFY: use a 12/7 V asymmetric RS-485 TVS from ST/Nexperia'),
        R(rx('R'), '2M', a=gb, b=gnd_logic), C(rx('C'), '4.7n/2kV', '1206', a=gb, b=gnd_logic),
    ]
    if term:
        parts += [R(rx('R'), '120', '0603', a=a, b='T485_' + tag),
                  P(rx('JP'), 'Connector_Generic:Conn_01x02', 'TERM ' + tag, 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
                    pins={'1': 'T485_' + tag, '2': b}, mfr='Wuerth', mpn='61300211121')]
    return parts


def di_bank(rx, tag, in_nets, v24_field, gnd_field, vcc, gnd, sclk, si, so, cs, rst, rdy, fault):
    """8 x 24 V isolated digital inputs on one Infineon ISO1I813T (in_nets: list of 8 field nets; 'NC' allowed)."""
    pins = {'IN%d' % i: in_nets[i] for i in range(8)}
    pins.update({'VBB': v24_field, 'GNDF': gnd_field, 'LED': 'NC', 'VCC': vcc, 'GND': gnd, 'SCLK': sclk, 'SI': si, 'SO': so, '~{CS}': cs,
                 '~{RST}': rst, 'RDY': rdy, '~{FAULT}': fault})
    parts = [P(rx('U'), ISO1I813T, 'ISO1I813T', pins=pins, **mm('ISO1I813T')),
             C(rx('C'), '100n', a=vcc, b=gnd), C(rx('C'), '100n/50V', '0603', a=v24_field, b=gnd_field)]
    for n in in_nets:
        if n != 'NC':
            parts.append(P(rx('D'), 'Device:D_TVS', 'SMAJ33CA', 'Diode_SMD:D_SMA', pins={'A1': n, 'A2': gnd_field}, **mm('SMAJ33CA')))
    return parts


def relay_out(rx, tag, drive_nets, v24, gnd, com_nets=None, no_nets=None):
    """Up to 8 Finder 34.51 relays driven by one ST ULN2803A. drive_nets: MCU outputs (3.3 V). Returns parts; contact nets
    default to RO_<tag>_<i>_COM / _NO."""
    n = len(drive_nets)
    assert n <= 8
    pins = {'I%d' % (i + 1): (drive_nets[i] if i < n else 'NC') for i in range(8)}
    pins.update({'GND': gnd, 'COM': v24})
    coils = ['RLYC_%s_%d' % (tag, i + 1) for i in range(n)]
    for i in range(8):
        pins['O%d' % (i + 1)] = coils[i] if i < n else 'NC'
    parts = [P(rx('U'), 'Transistor_Array:ULN2803A', 'ULN2803A', 'Package_SO:SOIC-18W_7.5x11.6mm_P1.27mm', pins=pins, **mm('ULN2803A'))]
    for i in range(n):
        com = (com_nets or ['RO_%s_%d_COM' % (tag, i + 1)] * n)[i]
        no = (no_nets or ['RO_%s_%d_NO' % (tag, i + 1)] * n)[i]
        parts.append(P(rx('K'), 'Relay:FINDER-34.51', '34.51 24VDC', 'Relay_THT:Relay_SPDT_Finder_34.51_Vertical',
                       pins={'A1': v24, 'A2': coils[i], '11': com, '12': 'NC', '14': no}, **mm('FINDER-34.51')))
        parts += [R(rx('R'), '2k2', a=v24, b='RLED_%s_%d' % (tag, i + 1)),
                  D(rx('D'), 'yellow', '0603', k=coils[i], a='RLED_%s_%d' % (tag, i + 1), kind='LED')]
    return parts


def input_24v(rx, vin_raw, gnd, vout='+24V', fuse='3A', tvs='SMBJ33A'):
    """24 V supply input: fuse, reverse-polarity P-MOSFET (Infineon), TVS (ST), bulk + ceramic."""
    return [P(rx('F'), 'Device:Fuse', fuse, 'Fuse:Fuse_1206_3216Metric', pins={'1': vin_raw, '2': 'VIN_F'}, mfr='SCHURTER (CH)', mpn='3413.0225.26 class'),
            P(rx('Q'), 'Transistor_FET:Q_PMOS_GDS', 'IPD90P04P4L', 'Package_TO_SOT_SMD:TO-252-2', pins={'G': 'VRP_G', 'D': 'VIN_F', 'S': vout},
              mfr='Infineon', mpn='IPD90P04P4L-04'),
            R(rx('R'), '100k', a='VRP_G', b=gnd), D(rx('D'), '12V', 'SOD-123', k=vout, a='VRP_G', kind='D_Zener', mfr='Nexperia', mpn='BZT52H-C12'),
            P(rx('D'), 'Device:D_TVS', tvs, 'Diode_SMD:D_SMB', pins={'A1': vout, 'A2': gnd}, **mm(tvs)),
            C(rx('C'), '100u/50V', a=vout, b=gnd, footprint='Capacitor_THT:CP_Radial_D8.0mm_P3.50mm', lib_id='Device:C_Polarized', mfr='Wuerth', mpn='860020675017'),
            C(rx('C'), '1u/50V', '0805', a=vout, b=gnd), C(rx('C'), '100n/50V', '0603', a=vout, b=gnd)]


def logic_rails(rx, v24, gnd, v5='+5V', v3='+3V3', with_3v3=True):
    """RECOM R-78E5.0-1.0 (24 -> 5 V) and ST LD1117S33 (5 -> 3.3 V)."""
    parts = [P(rx('U'), 'Converter_DCDC:R-78E5.0-1.0', 'R-78E5.0-1.0', 'Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT',
               pins={'IN': v24, 'GND': gnd, 'OUT': v5}, **mm('R-78E5.0-1.0')),
             C(rx('C'), '10u/50V', '1206', a=v24, b=gnd), C(rx('C'), '22u/10V', '0805', a=v5, b=gnd), C(rx('C'), '100n', a=v5, b=gnd)]
    if with_3v3:
        parts += [P(rx('U'), 'Regulator_Linear:LD1117S33TR_SOT223', 'LD1117S33', F_SOT223, pins={'VI': v5, 'VO': v3, 'GND': gnd}, **mm('LD1117S33')),
                  C(rx('C'), '10u/10V', '0805', a=v3, b=gnd), C(rx('C'), '100n', a=v3, b=gnd)]
        parts += led(rx, v3, gnd, 'green')
    return parts


def testpoints(rx, nets):
    return [P(rx('TP'), 'Connector:TestPoint', n, 'TestPoint:TestPoint_Pad_D1.5mm', pins={'1': n}, mfr='-', mpn='-') for n in nets]


def opamp_dual(rx, value, key, pins, fp=F_SOIC8):
    """ST dual op-amp on the generic Opamp_Dual symbol. pins: dict with keys OUT1, IN1-, IN1+, OUT2, IN2-, IN2+, V+, V-."""
    return P(rx('U'), 'Amplifier_Operational:Opamp_Dual', value, fp,
             pins={'1': pins['OUT1'], '2': pins['IN1-'], '3': pins['IN1+'], '7': pins['OUT2'], '6': pins['IN2-'], '5': pins['IN2+'],
                   '8': pins['V+'], '4': pins['V-']}, **mm(key))
