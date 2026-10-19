"""
SPT Calculation Engine — deterministic engineering maths, separate from AI.

    AI layer   : decides "battery sizing is required", extracts device list from BOQ/drawing
    KB layer   : supplies manufacturer data (quiescent currents, PoE budgets, power loss)
    THIS layer : performs the calculation and returns a traceable CalcResult

Every function returns CalcResult with .inputs, .outputs, .steps, .assumptions,
.warnings, .references, .passed and .report() for a printable calc sheet.
"""
from .core import CalcResult, CalcInputError
from .voltage_drop import voltage_drop, nac_end_of_line, conductor_resistance
from .battery import fire_alarm_battery, dc_battery_bank, DeviceLoad, PRESETS as BATTERY_PRESETS
from .poe import poe_budget, PoEDevice
from .bandwidth import network_bandwidth, Stream, estimate_bitrate_mbps
from .storage import video_storage
from .ups import ups_sizing, UPSLoad
from .load import load_schedule, Load
from .cable_sizing import cable_sizing
from .lock_psu import lock_psu, LockLoad, ReaderLoad
from .bms_station import bms_station_select, StationModel

# Registry — the AI layer calls modules by name through this map only.
REGISTRY = {
    "voltage_drop": voltage_drop,
    "nac_end_of_line": nac_end_of_line,
    "fire_alarm_battery": fire_alarm_battery,
    "dc_battery_bank": dc_battery_bank,
    "poe_budget": poe_budget,
    "network_bandwidth": network_bandwidth,
    "video_storage": video_storage,
    "ups_sizing": ups_sizing,
    "load_schedule": load_schedule,
    "cable_sizing": cable_sizing,
    "lock_psu": lock_psu,
    "bms_station_select": bms_station_select,
}

__version__ = "0.1.0"
