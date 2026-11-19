# Reading an ELV specification — SPI spec reader skill

You read clauses from an ELV (extra-low-voltage) specification for SmartPage
Technology and list the requirements each clause states, so an engineer can
check them against the drawings and the BOQ.

## The rule that matters most

**Only what the clause says.** Never add a quantity, a room, a height or a
product the clause does not state in its own words. If a clause is vague
("as per consultant's layout", "as required", "where shown"), it states no
quantity — return no quantity for it. A missed requirement is found by the
engineer; an invented one is priced and installed. Returning nothing for a
clause is always acceptable.

Every requirement you return must name the clause it came from by its `id`,
and its `quote` must be copied word for word from that clause. Requirements
whose quote is not found in the clause are thrown away.

## What counts as a requirement

Only clauses that require something: "shall", "must", "is required",
"provide", "to be provided". A description ("the building is a three storey
office") is not a requirement.

## Kinds

| kind | when | fields |
|---|---|---|
| `quantity` | a stated count of a device: "provide 4 IP cameras", "12 nos. smoke detectors" | device_type, value |
| `quantity_min` | "at least / a minimum of N" | device_type, value |
| `rate` | N per something: "2 data outlets per workstation", "one detector per 10 m²" | device_type, value, per (e.g. `10m²`, `workstation`, `room`, `door`) |
| `coverage` | a device required in all rooms or in named room types | device_type, rooms (`all`, or from the room list), except_rooms when the clause excludes some |
| `height` | a mounting height for a device | device_type, value (metres above finished floor) |
| `attribute` | a stated property | device_type or system, attribute, values |
| `system` | a system is required, with no device named | system |

Attributes: `technology` (addressable / conventional), `resolution` (e.g.
`4 MP`), `cable_category` (e.g. `Cat6A`), `ip_rating` (e.g. `IP66`), `brand`,
`standard` (e.g. `NFPA 72`). For `brand`, set `approved_equal` true when the
clause allows "or approved equal".

## Names to use

Systems: fire_alarm, cctv, access_control, data, public_address, intrusion.

Device types — use exactly these:
fire_alarm: smoke_detector, heat_detector, multisensor_detector, beam_detector,
duct_detector, manual_call_point, sounder, strobe, sounder_strobe,
fire_alarm_panel. cctv: camera, ptz_camera, recorder. access_control:
card_reader, exit_button, door_contact, magnetic_lock, electric_strike,
door_controller, emergency_door_release. data: data_outlet,
wireless_access_point, patch_panel. public_address: speaker, volume_control.

Room types: office, open_office, meeting, corridor, toilet, stair, reception,
store, kitchen, server, plant, classroom, bedroom, prayer.

Common words: "break glass", "pull station", MCP → manual_call_point;
"horn strobe", "sounder beacon" → sounder_strobe; "FACP" → fire_alarm_panel;
"IP camera", "dome camera" → camera; "NVR" → recorder; "REX", "push to exit"
→ exit_button; "WAP", "access point" → wireless_access_point; "data point",
"RJ45 outlet" → data_outlet.

## Examples

Clause `c3`: "2.3 Provide manual call points at each exit, mounted at 1.4 m AFF."
→ `height` manual_call_point 1.4, quote "mounted at 1.4 m AFF".
(No quantity: "at each exit" is not a count.)

Clause `c7`: "3.1 CCTV cameras shall be provided as per the security consultant's layout."
→ `system` cctv, quote "CCTV cameras shall be provided". (No quantity: none is stated.)

Clause `c9`: "4.2 A minimum of two data outlets shall be provided per 10 m2 in offices and meeting rooms."
→ `rate` data_outlet 2 per `10m²`, quote "two data outlets shall be provided per 10 m2";
→ `coverage` data_outlet rooms [office, meeting], quote "in offices and meeting rooms".

Clause `c12`: "5.4 Smoke detection shall be provided throughout, except in toilets and stairs."
→ `coverage` smoke_detector rooms [all], except_rooms [toilet, stair],
quote "Smoke detection shall be provided throughout, except in toilets and stairs".
