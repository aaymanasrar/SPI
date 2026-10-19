"""
Reference data tables.

!! VERIFY BEFORE IFC ISSUE !!
Values below are transcribed from the cited standards as commonly published.
They are fit for pre-sales / budgetary sizing. Before a calculation is issued
for construction, check each table against your licensed copy of the standard
(and SBC 401 / SAES-P-100 where the project is Saudi Aramco).
"""

# ---------------------------------------------------------------------------
# Conductor DC resistance at 20 °C, plain annealed copper, class 2 stranded
# Source: IEC 60228 Table 2 (ohm/km)
# ---------------------------------------------------------------------------
CU_RESISTANCE_20C_OHM_PER_KM = {
    1.0: 18.1, 1.5: 12.1, 2.5: 7.41, 4: 4.61, 6: 3.08, 10: 1.83, 16: 1.15,
    25: 0.727, 35: 0.524, 50: 0.387, 70: 0.268, 95: 0.193, 120: 0.153,
    150: 0.124, 185: 0.0991, 240: 0.0754, 300: 0.0601,
}
# Aluminium, class 2 (IEC 60228 Table 2)
AL_RESISTANCE_20C_OHM_PER_KM = {
    16: 1.91, 25: 1.20, 35: 0.868, 50: 0.641, 70: 0.443, 95: 0.320,
    120: 0.253, 150: 0.206, 185: 0.164, 240: 0.125, 300: 0.100,
}
ALPHA_20 = {"cu": 0.00393, "al": 0.00403}   # temperature coefficient /K

# Uncoated copper, stranded — NEC Chapter 9 Table 8 (ohm per 1000 ft at 75 °C)
# Used for fire-alarm NAC / SLC and low-voltage DC runs specified in AWG
AWG_RESISTANCE_OHM_PER_KFT_75C = {
    18: 8.08, 16: 5.08, 14: 3.14, 12: 1.98, 10: 1.24, 8: 0.778, 6: 0.491,
}
AWG_TO_MM2 = {18: 0.823, 16: 1.31, 14: 2.08, 12: 3.31, 10: 5.26, 8: 8.37, 6: 13.3}

# Typical LV multicore reactance when the cable datasheet is not yet known
DEFAULT_REACTANCE_OHM_PER_KM = 0.08

# ---------------------------------------------------------------------------
# Current-carrying capacity, copper, IEC 60364-5-52 Annex B (amps)
# Reference ambient 30 °C in air. Key: (insulation, method, loaded_conductors)
# ---------------------------------------------------------------------------
AMPACITY_CU = {
    # PVC 70 °C — Table B.52.2 / B.52.4
    ("pvc", "B1", 2): {1.5: 17.5, 2.5: 24, 4: 32, 6: 41, 10: 57, 16: 76, 25: 101,
                       35: 125, 50: 151, 70: 192, 95: 232, 120: 269},
    ("pvc", "B1", 3): {1.5: 15.5, 2.5: 21, 4: 28, 6: 36, 10: 50, 16: 68, 25: 89,
                       35: 110, 50: 134, 70: 171, 95: 207, 120: 239},
    ("pvc", "C", 2): {1.5: 19.5, 2.5: 27, 4: 36, 6: 46, 10: 63, 16: 85, 25: 112,
                      35: 138, 50: 168, 70: 213, 95: 258, 120: 299, 150: 344,
                      185: 392, 240: 461, 300: 530},
    ("pvc", "C", 3): {1.5: 17.5, 2.5: 24, 4: 32, 6: 41, 10: 57, 16: 76, 25: 96,
                      35: 119, 50: 144, 70: 184, 95: 223, 120: 259, 150: 299,
                      185: 341, 240: 403, 300: 464},
    # XLPE/EPR 90 °C — Table B.52.3 / B.52.5
    ("xlpe", "C", 2): {1.5: 24, 2.5: 33, 4: 45, 6: 58, 10: 80, 16: 107, 25: 138,
                       35: 171, 50: 209, 70: 269, 95: 328, 120: 382, 150: 441,
                       185: 506, 240: 599, 300: 693},
    ("xlpe", "C", 3): {1.5: 22, 2.5: 30, 4: 40, 6: 52, 10: 71, 16: 96, 25: 119,
                       35: 147, 50: 179, 70: 229, 95: 278, 120: 322, 150: 371,
                       185: 424, 240: 500, 300: 576},
}

# Ambient air temperature correction, Table B.52.14 (reference 30 °C)
TEMP_CORRECTION_AIR = {
    "pvc":  {10: 1.22, 15: 1.17, 20: 1.12, 25: 1.06, 30: 1.00, 35: 0.94,
             40: 0.87, 45: 0.79, 50: 0.71, 55: 0.61, 60: 0.50},
    "xlpe": {10: 1.15, 15: 1.12, 20: 1.08, 25: 1.04, 30: 1.00, 35: 0.96,
             40: 0.91, 45: 0.87, 50: 0.82, 55: 0.76, 60: 0.71, 65: 0.65, 70: 0.58},
}

# Grouping, bunched in air / on a surface / enclosed — Table B.52.17 row 1
GROUPING_BUNCHED = {1: 1.00, 2: 0.80, 3: 0.70, 4: 0.65, 5: 0.60, 6: 0.57,
                    7: 0.54, 8: 0.52, 9: 0.50, 12: 0.45, 16: 0.41, 20: 0.38}

# Adiabatic k factors, IEC 60364-5-54 Table A.54.2 / 4-43 (copper / aluminium)
K_FACTOR = {("cu", "pvc"): 115, ("cu", "xlpe"): 143,
            ("al", "pvc"): 76, ("al", "xlpe"): 94}

# Preferred protective device ratings (A) — IEC 60898 / 60947-2 common series
STANDARD_BREAKER_A = [6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160,
                      200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600]

# Voltage-drop guidance, IEC 60364-5-52 Annex G (installation origin → load)
VD_LIMITS_PCT = {
    "public_lv_lighting": 3.0, "public_lv_other": 5.0,
    "private_lv_lighting": 6.0, "private_lv_other": 8.0,
}

# ---------------------------------------------------------------------------
# PoE — IEEE 802.3af / at / bt power classes
# pse_w = minimum power at PSE port; pd_w = max power available at the PD
# ---------------------------------------------------------------------------
POE_CLASSES = {
    0: {"std": "802.3af", "type": 1, "pse_w": 15.4, "pd_w": 12.95},
    1: {"std": "802.3af", "type": 1, "pse_w": 4.0,  "pd_w": 3.84},
    2: {"std": "802.3af", "type": 1, "pse_w": 7.0,  "pd_w": 6.49},
    3: {"std": "802.3af", "type": 1, "pse_w": 15.4, "pd_w": 12.95},
    4: {"std": "802.3at", "type": 2, "pse_w": 30.0, "pd_w": 25.5},
    5: {"std": "802.3bt", "type": 3, "pse_w": 45.0, "pd_w": 40.0},
    6: {"std": "802.3bt", "type": 3, "pse_w": 60.0, "pd_w": 51.0},
    7: {"std": "802.3bt", "type": 4, "pse_w": 75.0, "pd_w": 62.0},
    8: {"std": "802.3bt", "type": 4, "pse_w": 90.0, "pd_w": 71.3},
}
POE_MAX_CHANNEL_M = 100

# Standard UPS ratings (kVA) for selection
STANDARD_UPS_KVA = [0.6, 1, 1.5, 2, 3, 5, 6, 8, 10, 15, 20, 30, 40, 60, 80,
                    100, 120, 160, 200, 250, 300, 400, 500]
# Standard VRLA 12 V block capacities (Ah)
STANDARD_BATTERY_AH = [1.2, 2.3, 3.2, 7, 7.2, 9, 12, 17, 18, 24, 26, 33, 38,
                       40, 45, 55, 65, 75, 100, 120, 150, 200]
