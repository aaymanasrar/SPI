"""Words people use for ELV devices, mapped to the device types the drawing
tools count in (cad/default_symbols.json).

Shared by the spec reader and the BOQ matcher, so a spec clause, a BOQ row and a
drawing block that mean the same device land on the same key. Matching is by
phrase, longest first, so "sounder strobe" is not read as a bare "sounder".

This is vocabulary, not engineering: nothing here is a quantity, a spacing or a
height.
"""
from __future__ import annotations

import re

#: (system, device_type) -> phrases, lower case. Longer phrases are tried first.
DEVICE_PHRASES: dict[tuple[str, str], list[str]] = {
    ("fire_alarm", "smoke_detector"): ["optical smoke detector", "photoelectric smoke detector",
                                        "smoke detector", "smoke detectors", "smoke sensor",
                                        "smoke detection"],
    ("fire_alarm", "heat_detector"): ["heat detector", "heat detectors", "rate of rise detector",
                                       "fixed temperature detector", "heat detection"],
    ("fire_alarm", "multisensor_detector"): ["multisensor detector", "multi-sensor detector",
                                              "multi sensor detector", "multicriteria detector"],
    ("fire_alarm", "beam_detector"): ["beam detector", "beam detectors"],
    ("fire_alarm", "duct_detector"): ["duct detector", "duct smoke detector"],
    ("fire_alarm", "manual_call_point"): ["manual call point", "manual call points", "call point",
                                           "call points", "break glass unit", "break glass",
                                           "manual pull station", "pull station", "mcp"],
    ("fire_alarm", "sounder_strobe"): ["sounder strobe", "sounder/strobe", "sounder-strobe",
                                        "sounder beacon", "horn strobe", "horn/strobe",
                                        "sounder strobes", "horn strobes"],
    ("fire_alarm", "sounder"): ["sounder", "sounders", "alarm bell", "fire bell", "horn"],
    ("fire_alarm", "strobe"): ["strobe", "strobes", "visual alarm device", "beacon"],
    ("fire_alarm", "fire_alarm_panel"): ["fire alarm control panel", "fire alarm panel", "facp",
                                          "control and indicating equipment"],
    ("cctv", "ptz_camera"): ["ptz camera", "ptz cameras", "pan tilt zoom camera"],
    ("cctv", "camera"): ["ip camera", "cctv camera", "dome camera", "bullet camera",
                          "fixed camera", "camera", "cameras"],
    ("cctv", "recorder"): ["network video recorder", "nvr", "video recorder"],
    ("access_control", "card_reader"): ["card reader", "card readers", "proximity reader",
                                         "access reader", "biometric reader"],
    ("access_control", "exit_button"): ["exit button", "exit buttons", "request to exit",
                                         "request-to-exit", "rex button", "push to exit"],
    ("access_control", "door_contact"): ["door contact", "door contacts", "door position switch",
                                          "magnetic contact"],
    ("access_control", "magnetic_lock"): ["magnetic lock", "maglock", "mag lock",
                                           "electromagnetic lock"],
    ("access_control", "electric_strike"): ["electric strike"],
    ("access_control", "door_controller"): ["door controller", "access controller",
                                             "access control panel"],
    ("access_control", "emergency_door_release"): ["emergency door release", "break glass door release",
                                                    "green break glass"],
    ("data", "wireless_access_point"): ["wireless access point", "wireless access points",
                                         "access point", "wap", "wi-fi access point"],
    ("data", "data_outlet"): ["data outlet", "data outlets", "data point", "data points",
                              "network outlet", "network outlets", "rj45 outlet", "telecom outlet",
                              "information outlet"],
    ("data", "patch_panel"): ["patch panel", "patch panels"],
    ("public_address", "speaker"): ["ceiling speaker", "loudspeaker", "speaker", "speakers"],
    ("public_address", "volume_control"): ["volume control", "attenuator"],
}

SYSTEM_PHRASES: dict[str, list[str]] = {
    "fire_alarm": ["fire alarm", "fire detection", "fire alarm system", "fdas"],
    "cctv": ["cctv", "video surveillance", "closed circuit television"],
    "access_control": ["access control", "acs"],
    "data": ["structured cabling", "data network", "data system", "lan"],
    "public_address": ["public address", "voice evacuation", "pava"],
    "intrusion": ["intrusion", "intruder alarm", "burglar alarm"],
}

#: Device phrase -> key, longest phrase first so the most specific wins.
_DEVICE_INDEX = sorted(((p, k) for k, ps in DEVICE_PHRASES.items() for p in ps),
                       key=lambda t: -len(t[0]))
_SYSTEM_INDEX = sorted(((p, k) for k, ps in SYSTEM_PHRASES.items() for p in ps),
                       key=lambda t: -len(t[0]))


def _find(text: str, index: list[tuple[str, object]]) -> list[tuple[object, int, int]]:
    """All non-overlapping matches, longest phrase first, as (key, start, end)."""
    low = text.lower()
    taken: list[tuple[int, int]] = []
    out: list[tuple[object, int, int]] = []
    for phrase, key in index:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", low):
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            taken.append((s, e))
            out.append((key, s, e))
    return sorted(out, key=lambda t: t[1])


def devices_in(text: str) -> list[tuple[tuple[str, str], int, int]]:
    return _find(text, _DEVICE_INDEX)  # type: ignore[return-value]


def systems_in(text: str) -> list[str]:
    return list(dict.fromkeys(k for k, _, _ in _find(text, _SYSTEM_INDEX)))  # type: ignore[misc]


def device_of(description: str) -> tuple[str, str] | None:
    """The one device a BOQ description names, or None when it names none or
    several different ones (a combined line is not guessed at)."""
    found = list(dict.fromkeys(k for k, _, _ in devices_in(description)))
    return found[0] if len(found) == 1 else None


def label(device_type: str) -> str:
    return device_type.replace("_", " ")


# ---- attributes a spec states and a BOQ line can contradict ------------------
#: name -> (pattern, normaliser). Each pattern's group(1) is the value.
ATTRIBUTE_PATTERNS: dict[str, tuple[str, object]] = {
    "technology": (r"\b(addressable|conventional|analogue addressable|analog addressable)\b",
                   lambda v: "addressable" if "addressable" in v else v),
    "resolution": (r"\b(\d{1,2}(?:\.\d)?)\s?(?:mp|megapixel)\b", lambda v: f"{float(v):g} MP"),
    "cable_category": (r"\bcat(?:egory)?\s?-?(5e|6a|6|7a|7|8)\b", lambda v: f"Cat{v.upper()}"),
    "ip_rating": (r"\bip\s?(\d{2})\b", lambda v: f"IP{v}"),
    "standard": (r"\b(nfpa\s?72|nfpa\s?70|bs\s?5839(?:-\d)?|en\s?54(?:-\d+)?|bs\s?en\s?54(?:-\d+)?|"
                 r"tia-?568(?:\.\d)?|iso/iec\s?11801|ul\s?268|ul\s?521|en\s?62676(?:-\d)?|"
                 r"bs\s?7671|en\s?50131|saso|sbc\s?801|ncd)\b",
                 lambda v: re.sub(r"\s+", " ", v.upper())),
    "brand": (r"\b(siemens|honeywell|notifier|bosch|axis|hikvision|dahua|hanwha|avigilon|"
              r"hid|lenel|genetec|tyco|simplex|edwards|apollo|hochiki|gent|morley|"
              r"commscope|panduit|legrand|schneider|cisco|aruba|ubiquiti|milestone)\b",
              lambda v: v.capitalize()),
}

APPROVED_EQUAL = re.compile(r"\b(or\s+(?:approved\s+)?equal|or\s+equivalent|approved\s+equal)\b", re.I)


def attributes_in(text: str) -> dict[str, list[str]]:
    """Every attribute value stated in the text, normalised, in order of appearance."""
    out: dict[str, list[str]] = {}
    low = text.lower()
    for name, (pattern, norm) in ATTRIBUTE_PATTERNS.items():
        vals = [norm(m.group(1)) for m in re.finditer(pattern, low)]  # type: ignore[operator]
        if vals:
            out[name] = list(dict.fromkeys(vals))
    return out
