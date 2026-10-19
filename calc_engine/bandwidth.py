"""Network bandwidth — CCTV / IP stream aggregation and uplink utilisation."""
from __future__ import annotations

from dataclasses import dataclass
from .core import CalcResult, CalcInputError, require_positive, r

# Bits-per-pixel starting points for bitrate ESTIMATION only (medium scene activity).
# Always prefer the camera vendor's calculator / datasheet bitrate.
BPP_ESTIMATE = {"h264": 0.10, "h265": 0.05, "mjpeg": 1.0}


@dataclass
class Stream:
    name: str
    qty: int
    bitrate_mbps: float | None = None    # preferred: from vendor calculator
    width: int | None = None             # estimation mode
    height: int | None = None
    fps: float | None = None
    codec: str = "h265"
    streams_per_device: int = 1          # e.g. main + sub stream both sent


def estimate_bitrate_mbps(width: int, height: int, fps: float, codec: str = "h265") -> float:
    if codec not in BPP_ESTIMATE:
        raise CalcInputError(f"codec must be one of {list(BPP_ESTIMATE)}")
    return width * height * fps * BPP_ESTIMATE[codec] / 1e6


def network_bandwidth(streams: list[Stream], link_capacity_mbps: float = 1000.0,
                      protocol_overhead: float = 1.10, max_utilisation_pct: float = 70.0,
                      viewing_clients: int = 0, viewing_mbps_per_client: float = 0.0) -> CalcResult:
    """
    Aggregate = Σ(qty × streams × bitrate) × protocol overhead (+ live viewing clients).
    protocol_overhead 1.10 ≈ IP/UDP/RTP headers; max_utilisation 70 % leaves room for bursts.
    """
    require_positive(link_capacity_mbps=link_capacity_mbps, protocol_overhead=protocol_overhead)
    res = CalcResult("network_bandwidth", inputs=dict(
        link_capacity_mbps=link_capacity_mbps, protocol_overhead=protocol_overhead,
        max_utilisation_pct=max_utilisation_pct, viewing_clients=viewing_clients,
        viewing_mbps_per_client=viewing_mbps_per_client,
        streams=[s.__dict__ for s in streams]), outputs={})
    total = 0.0
    for s in streams:
        if s.bitrate_mbps is not None:
            br = s.bitrate_mbps
            src = "given"
        elif None not in (s.width, s.height, s.fps):
            br = estimate_bitrate_mbps(s.width, s.height, s.fps, s.codec)
            src = f"ESTIMATED {s.width}×{s.height}×{s.fps}fps×{BPP_ESTIMATE[s.codec]}bpp"
            res.assumptions.append(f"{s.name}: bitrate estimated — replace with vendor calculator value")
        else:
            raise CalcInputError(f"{s.name}: give bitrate_mbps or width/height/fps")
        line = s.qty * s.streams_per_device * br
        total += line
        res.step(f"{s.name} ×{s.qty} × {s.streams_per_device} stream(s) × {r(br,2)} Mbps ({src}) = {r(line,2)} Mbps")
    view = viewing_clients * viewing_mbps_per_client
    if view:
        res.step(f"Live viewing: {viewing_clients} × {viewing_mbps_per_client} = {r(view,2)} Mbps")
    agg = (total + view) * protocol_overhead
    res.step(f"Aggregate = ({r(total,2)} + {r(view,2)}) × {protocol_overhead} = {r(agg,2)} Mbps")
    util = agg / link_capacity_mbps * 100
    res.step(f"Utilisation = {r(agg,2)} / {link_capacity_mbps} = {r(util,1)} %")
    res.outputs = {"camera_ingest_mbps": r(total, 2), "aggregate_mbps": r(agg, 2),
                   "utilisation_pct": r(util, 1), "max_utilisation_pct": max_utilisation_pct,
                   "min_link_mbps_required": r(agg / (max_utilisation_pct / 100), 1)}
    res.passed = util <= max_utilisation_pct
    res.references.append("Design practice: ≤70 % sustained link utilisation for real-time video")
    return res
