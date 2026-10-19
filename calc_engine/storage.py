"""Video / data storage sizing with RAID and file-system overhead."""
from __future__ import annotations

import math
from .core import CalcResult, CalcInputError, require_positive, require_range, r

RAID_USABLE = {  # fraction of raw capacity usable for n disks
    "raid0": lambda n: 1.0,
    "raid1": lambda n: 0.5,
    "raid5": lambda n: (n - 1) / n,
    "raid6": lambda n: (n - 2) / n,
    "raid10": lambda n: 0.5,
}
RAID_MIN_DISKS = {"raid0": 1, "raid1": 2, "raid5": 3, "raid6": 4, "raid10": 4}


def video_storage(total_bitrate_mbps: float, retention_days: float,
                  hours_per_day: float = 24.0, recording_duty_pct: float = 100.0,
                  disk_size_tb: float = 8.0, raid: str = "raid5",
                  hot_spares: int = 0, fs_overhead_pct: float = 10.0,
                  growth_pct: float = 0.0) -> CalcResult:
    """
    Storage (TB, decimal) = Mbps × 3600 × h/day × days × duty / 8 / 1e6
    total_bitrate_mbps: sum of recorded streams (take from network_bandwidth 'camera_ingest_mbps').
    recording_duty_pct: <100 for motion/event recording — state basis explicitly.
    """
    require_positive(total_bitrate_mbps=total_bitrate_mbps, retention_days=retention_days,
                     disk_size_tb=disk_size_tb)
    require_range("hours_per_day", hours_per_day, 0.1, 24)
    require_range("recording_duty_pct", recording_duty_pct, 1, 100)
    if raid not in RAID_USABLE:
        raise CalcInputError(f"raid must be one of {list(RAID_USABLE)}")
    res = CalcResult("video_storage", inputs=dict(
        total_bitrate_mbps=total_bitrate_mbps, retention_days=retention_days,
        hours_per_day=hours_per_day, recording_duty_pct=recording_duty_pct,
        disk_size_tb=disk_size_tb, raid=raid, hot_spares=hot_spares,
        fs_overhead_pct=fs_overhead_pct, growth_pct=growth_pct), outputs={})
    tb = total_bitrate_mbps * 3600 * hours_per_day * retention_days * (recording_duty_pct / 100) / 8 / 1e6
    res.step(f"Net = {total_bitrate_mbps} Mbps × 3600 × {hours_per_day} h × {retention_days} d × "
             f"{recording_duty_pct}% / 8 / 10⁶ = {r(tb,2)} TB")
    need = tb * (1 + fs_overhead_pct / 100) * (1 + growth_pct / 100)
    res.step(f"× (1 + {fs_overhead_pct}% FS) × (1 + {growth_pct}% growth) = {r(need,2)} TB usable required")

    n = RAID_MIN_DISKS[raid]
    while disk_size_tb * n * RAID_USABLE[raid](n) < need:
        n += 1
        if raid in ("raid1",) and n > 2:
            raise CalcInputError("RAID1 is 2 disks; use raid10 for larger arrays")
        if raid == "raid10" and n % 2:
            n += 1
    usable = disk_size_tb * n * RAID_USABLE[raid](n)
    res.step(f"{raid.upper()} with {n} × {disk_size_tb} TB → usable {r(usable,2)} TB")
    res.outputs = {"net_storage_tb": r(tb, 2), "required_usable_tb": r(need, 2),
                   "disks_in_array": n, "hot_spares": hot_spares, "total_disks": n + hot_spares,
                   "raw_tb": r(disk_size_tb * (n + hot_spares), 1), "usable_tb": r(usable, 2),
                   "daily_tb": r(tb / retention_days, 3)}
    res.passed = True
    if raid == "raid5" and disk_size_tb >= 8 and n > 6:
        res.warnings.append("Large RAID5 array with ≥8 TB disks — rebuild risk; consider RAID6")
    res.assumptions.append("Decimal TB (10¹² bytes) as marketed by disk vendors; OS shows TiB (≈ 0.909×)")
    return res
