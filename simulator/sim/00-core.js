// ---------- shared state and helpers ----------
// Everything the page shows comes from one bim.scene_3d result. Values the
// model does not hold (a sounder's output, how fast smoke travels) are settings
// a person enters; each one carries where it came from, and results computed
// from an illustrative value say so.

var $ = function (id) { return document.getElementById(id); };
var css = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };

function esc(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
function fmt(n, d) {
  if (n == null || !isFinite(n)) return "—";
  if (Math.abs(n) < 1e-9) n = 0;          // no "-0"
  return Number(n).toLocaleString("en-GB", { maximumFractionDigits: d == null ? 2 : d, minimumFractionDigits: 0 });
}
function clock(t) {
  var s = Math.max(0, Math.floor(t));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function words(s) { return String(s || "").replace(/_/g, " "); }

var toastTimer = null;
function toast(msg, ms) {
  var t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { t.classList.remove("show"); }, ms || 3200);
}

// ---------- systems and device kinds ----------
var SYS_VAR = { fire_alarm: "--sys-fire", cctv: "--sys-cctv", access_control: "--sys-acs",
  data: "--sys-data", public_address: "--sys-pa", intrusion: "--sys-int" };
function sysColor(system) { return css(SYS_VAR[system] || "--sys-other"); }

var DETECTORS = ["smoke_detector", "multisensor_detector", "heat_detector"];
var NOTIFIERS = ["sounder", "sounder_strobe", "strobe", "bell"];
var CEILING_TYPES = ["smoke_detector", "multisensor_detector", "heat_detector", "camera",
  "wireless_access_point", "speaker"];

// What a person can add in the what-if tools, and where it goes vertically.
// Ceiling devices sit at the room's modelled height. A wall sounder sits inside
// the SPT-FA-15 lens band; 2.2 m is chosen within 2.03-2.44 m, not specified.
var PROPOSABLE = {
  smoke_detector: { system: "fire_alarm", at: "ceiling" },
  heat_detector: { system: "fire_alarm", at: "ceiling" },
  sounder_strobe: { system: "fire_alarm", at: 2.2, note: "within the SPT-FA-15 band (2.03-2.44 m AFF)" },
  camera: { system: "cctv", at: "ceiling" }
};

// ---------- geometry ----------
function pip(x, y, poly) {
  var inside = false;
  for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    var xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-30) + xi) inside = !inside;
  }
  return inside;
}
function polyArea(poly) {
  var s = 0;
  for (var i = 0; i < poly.length; i++) {
    var a = poly[i], b = poly[(i + 1) % poly.length];
    s += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(s) / 2;
}
function polyBounds(poly) {
  var b = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  poly.forEach(function (p) {
    b.x0 = Math.min(b.x0, p[0]); b.y0 = Math.min(b.y0, p[1]);
    b.x1 = Math.max(b.x1, p[0]); b.y1 = Math.max(b.y1, p[1]);
  });
  return b;
}
function centroid(poly) {
  // Area-weighted centroid; falls back to the vertex mean for slivers.
  var a = 0, cx = 0, cy = 0;
  for (var i = 0; i < poly.length; i++) {
    var p = poly[i], q = poly[(i + 1) % poly.length], k = p[0] * q[1] - q[0] * p[1];
    a += k; cx += (p[0] + q[0]) * k; cy += (p[1] + q[1]) * k;
  }
  if (Math.abs(a) < 1e-9) {
    var mx = 0, my = 0;
    poly.forEach(function (p) { mx += p[0]; my += p[1]; });
    return [mx / poly.length, my / poly.length];
  }
  return [cx / (3 * a), cy / (3 * a)];
}
// Smallest signed difference between two angles in degrees.
function angleDiff(a, b) {
  var d = ((a - b) % 360 + 540) % 360 - 180;
  return d;
}

// ---------- state ----------
var S = {
  result: null,          // the bim.scene_3d ToolResult
  rules: window.__RULES__ || {},
  meta: window.__META__ || {},
  storeys: [],           // [{name, elevation_m, base}]
  rooms: [],             // spaces with an outline, plus derived fields
  devices: [],           // model devices with a position, plus proposals
  storey: "__all__",
  view: "orbit",
  mode: "inspect",
  analysis: "smoke",
  selected: null,        // {kind: "device"|"room", ref}
  disabled: {},          // device id -> true (out of service in the what-if)
  aim: {},               // camera id -> yaw degrees set in the simulator
  tool: null,            // "place" | "ignite" | null
  placeType: "smoke_detector",
  proposals: 0,
  hidden: {},            // system -> true
  coverage: null,        // last analysis result
  drill: null
};

// Settings, each with where its value came from. "rule" values are derived
// from the cited rule, "example" values are a rule's own worked example,
// "illustrative" values were filled in by the button that says so, and
// "entered" values were typed by the person using the page.
var SET = {
  smoke: { spacing_m: { v: 9.1, src: "rule", why: "SPT-FA-01 nominal spacing on a smooth, flat ceiling" } },
  heat: { listed_m: { v: null, src: null, why: "the detector's listed spacing, from its datasheet (SPT-FA-04: typically 7.6-15.2 m)" } },
  cctv: {
    dori: { v: "identify", src: "rule", why: "SPT-CC-01 class" },
    hres_px: { v: 2688, src: "example", why: "SPT-CC-03 worked example — replace with the camera datasheet" },
    hfov_deg: { v: 90, src: "example", why: "SPT-CC-03 worked example — replace with the lens at its set focal length" },
    target_m: { v: 1.6, src: "rule", why: "face height used by SPT-CC-09" }
  },
  sounder: {
    out_dba: { v: null, src: null, why: "sounder output at 1 m, from its datasheet" },
    avg_dba: { v: null, src: null, why: "average ambient level, from a survey" },
    max_dba: { v: null, src: null, why: "maximum ambient lasting 60 s or more, from a survey" },
    through_walls: { v: false, src: "entered", why: "let sounders in other rooms count" },
    wall_db: { v: null, src: null, why: "sound reduction of the walls and doors in between" }
  },
  drill: {
    speed: { v: null, src: null, why: "how fast smoke spreads across the ceiling, m/s" },
    det_delay: { v: null, src: null, why: "detector response time once smoke arrives, s" },
    panel_delay: { v: null, src: null, why: "panel processing and any alarm verification delay, s" },
    scope: { v: "storey", src: "entered", why: "which sounders the cause and effect starts" }
  }
};
var ILLUSTRATIVE = {
  sounder: { out_dba: 100, avg_dba: 50, max_dba: 60, wall_db: 25 },
  drill: { speed: 0.3, det_delay: 10, panel_delay: 5 }
};
var DORI = { detect: 25, observe: 62.5, recognise: 125, identify: 250 };   // SPT-CC-01, px/m

function setting(group, key) { return SET[group][key].v; }
function anyIllustrative(group) {
  return Object.keys(SET[group]).some(function (k) { return SET[group][k].src === "illustrative"; });
}

// ---------- loading a scene ----------
function loadResult(result) {
  if (!result || ["bim.scene_3d", "bim.prototype"].indexOf(result.tool) < 0 || !result.outputs) {
    throw new Error("This is not a building scene. Build one with: python -m craft.bim scene model.ifc --out scene.json");
  }
  var out = result.outputs;
  S.result = result;
  S.selected = null; S.disabled = {}; S.aim = {}; S.tool = null; S.coverage = null; S.drill = null;
  S.proposals = 0;

  var names = {};
  S.storeys = (out.storeys || []).map(function (s) {
    names[s.name] = true;
    return { name: s.name, elevation_m: s.elevation_m, base: s.elevation_m };
  });
  // Rooms and devices can name a storey the list does not (or none at all).
  function ensure(name) {
    var n = name || "(no storey)";
    if (!names[n]) { names[n] = true; S.storeys.push({ name: n, elevation_m: null, base: null }); }
    return n;
  }

  S.rooms = (out.spaces || []).filter(function (s) { return s.footprint_m && s.footprint_m.length >= 3; })
    .map(function (s) {
      return {
        id: s.id, label: s.label, number: s.number, name: s.name, storey: ensure(s.storey),
        poly: s.footprint_m, base: s.base_z_m, height: s.height_m,
        area: s.area_m2, areaSource: s.area_source, outlineArea: s.outline_area_m2,
        center: centroid(s.footprint_m), bounds: polyBounds(s.footprint_m)
      };
    });
  S.roomsWithoutOutline = (out.spaces || []).filter(function (s) { return !(s.footprint_m && s.footprint_m.length >= 3); });

  S.devices = (out.devices || []).filter(function (d) { return d.x_m != null; }).map(function (d) {
    return Object.assign({}, d, { storey: ensure(d.storey), proposed: !!d.proposed });
  });
  S.unplaced = (out.devices || []).filter(function (d) { return d.x_m == null; });

  // A storey's floor level: its elevation, else the lowest room or device on it.
  S.storeys.forEach(function (st) {
    if (st.base != null) return;
    var zs = S.rooms.filter(function (r) { return r.storey === st.name; }).map(function (r) { return r.base; })
      .concat(S.devices.filter(function (d) { return d.storey === st.name; }).map(function (d) { return d.z_m - 0.5; }));
    st.base = zs.length ? Math.min.apply(null, zs) : 0;
  });
  S.storeys.sort(function (a, b) { return a.base - b.base; });
  // A prototype is a whole building to look at; a model is checked floor by floor.
  S.storey = S.storeys.length > 1 && !out.building ? S.storeys[0].name : "__all__";
}

function roomById(id) { return S.rooms.find(function (r) { return r.id === id; }) || null; }
function deviceById(id) { return S.devices.find(function (d) { return d.id === id; }) || null; }
function storeyBase(name) {
  var s = S.storeys.find(function (x) { return x.name === name; });
  return s ? s.base : 0;
}
function onStorey(item) { return S.storey === "__all__" || item.storey === S.storey; }

// The room a device is in: the engine's answer for model devices, a point-in-
// outline test for proposals and for anything the engine could not place.
function roomOf(d) {
  if (d.roomId !== undefined) return d.roomId ? roomById(d.roomId) : null;
  var found = null;
  if (d.space) {
    found = S.rooms.find(function (r) { return r.label === d.space && r.storey === d.storey; }) || null;
  }
  if (!found) {
    found = S.rooms.find(function (r) {
      return r.storey === d.storey && d.z_m >= r.base - 0.05 && d.z_m <= r.base + r.height + 0.05
        && pip(d.x_m, d.y_m, r.poly);
    }) || null;
  }
  d.roomId = found ? found.id : null;
  return found;
}

function activeDevices(types) {
  return S.devices.filter(function (d) { return types.indexOf(d.device_type) >= 0 && !S.disabled[d.id]; });
}

function aimOf(d) { return S.aim[d.id] != null ? S.aim[d.id] : (d.yaw_deg || 0); }
