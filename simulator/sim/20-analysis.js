// ---------- coverage analyses ----------
// Each analysis applies one cited rule, room by room. A room is sampled on a
// grid over its modelled outline; a sample point is covered when a device in
// the same room reaches it. Devices in other rooms do not count, because
// detection and sight do not pass through walls. Sound can, and only when the
// person says so, with the wall loss they enter.
//
// The numbers below are the rules' own. simulator/rules.py refuses to build if
// the rule text stops saying them.

// SPT-FA-04 (NFPA 72 Table 17.6.3.5.1): ceiling height up to (m) -> factor.
// The rule's condition is "ceiling > 3.0 m", so there is no reduction below it.
var HEAT_FACTORS = [[3.0, 1.0], [3.7, 0.91], [4.3, 0.84], [4.9, 0.77], [5.5, 0.71], [6.1, 0.64],
  [6.7, 0.58], [7.3, 0.52], [7.9, 0.46], [8.5, 0.40], [9.1, 0.34]];
function heatFactor(h) {
  for (var i = 0; i < HEAT_FACTORS.length; i++) if (h <= HEAT_FACTORS[i][0] + 1e-9) return HEAT_FACTORS[i][1];
  return null;      // above the table: not covered by the rule
}

var ANALYSES = {
  smoke: { label: "Smoke", title: "Smoke detection", rules: ["SPT-FA-01", "SPT-FA-02"],
    types: ["smoke_detector", "multisensor_detector"] },
  heat: { label: "Heat", title: "Heat detection", rules: ["SPT-FA-04", "SPT-FA-02"],
    types: ["heat_detector"] },
  cctv: { label: "CCTV", title: "CCTV pixel density", rules: ["SPT-CC-01", "SPT-CC-03", "SPT-CC-09"],
    types: ["camera"] },
  sounder: { label: "Sounders", title: "Sounder audibility", rules: ["SPT-FA-13"],
    types: ["sounder", "sounder_strobe", "bell"] }
};
var FIELD_LABELS = {
  spacing_m: "Detector spacing S (m)", listed_m: "Listed spacing (m)", dori: "DORI class",
  hres_px: "Horizontal resolution (px)", hfov_deg: "Horizontal field of view (°)", target_m: "Target height (m)",
  out_dba: "Sounder output at 1 m (dBA)", avg_dba: "Average ambient (dBA)", max_dba: "Max ambient ≥ 60 s (dBA)",
  through_walls: "Count sounders in other rooms", wall_db: "Wall and door loss (dB)",
  speed: "Smoke spread (m/s)", det_delay: "Detector response (s)", panel_delay: "Panel delay (s)", scope: "Sounders started"
};

function missingInputs(group) {
  var need = Object.keys(SET[group]).filter(function (k) {
    if (group === "sounder" && k === "wall_db" && !SET.sounder.through_walls.v) return false;
    return SET[group][k].v == null || SET[group][k].v === "";
  });
  return need.map(function (k) { return FIELD_LABELS[k] || k; });
}

function cctvReach() {
  var ppm = DORI[setting("cctv", "dori")], hres = setting("cctv", "hres_px"), hfov = setting("cctv", "hfov_deg");
  if (!(ppm > 0 && hres > 0 && hfov > 0 && hfov < 180)) return null;
  return hres / (ppm * 2 * Math.tan(hfov * Math.PI / 360));        // SPT-CC-03
}

function gridStep(r) { return Math.max(0.2, Math.min(1.0, Math.sqrt(polyArea(r.poly) / 2500))); }

function cellsOf(r, step) {
  var b = r.bounds, cells = [];
  for (var x = b.x0 + step / 2; x < b.x1; x += step) {
    for (var y = b.y0 + step / 2; y < b.y1; y += step) if (pip(x, y, r.poly)) cells.push([x, y]);
  }
  return cells;
}

// ---------- the per-room test ----------
function evaluateRoom(kind, r, inRoom, onLevel) {
  var step = gridStep(r), cells = cellsOf(r, step);
  var res = { room: r, step: step, total: cells.length, covered: 0, uncovered: [], loud: [], devices: inRoom.length, note: null };
  if (!cells.length) { res.note = "outline too small to sample"; return res; }
  var test;

  if (kind === "smoke" || kind === "heat") {
    var radius;
    if (kind === "smoke") radius = 0.7 * setting("smoke", "spacing_m");              // SPT-FA-02
    else {
      var f = heatFactor(r.height);
      if (f == null) { res.note = "ceiling " + fmt(r.height) + " m is above the SPT-FA-04 table"; res.total = 0; return res; }
      radius = 0.7 * setting("heat", "listed_m") * f;                                 // SPT-FA-04, then 0.7S
      res.factor = f;
    }
    res.radius = radius;
    var r2 = radius * radius;
    test = function (x, y) {
      for (var i = 0; i < inRoom.length; i++) {
        var dx = inRoom[i].x_m - x, dy = inRoom[i].y_m - y;
        if (dx * dx + dy * dy <= r2) return true;
      }
      return false;
    };
  } else if (kind === "cctv") {
    var dmax = cctvReach(), half = setting("cctv", "hfov_deg") / 2, target = r.base + setting("cctv", "target_m");
    var cams = inRoom.map(function (c) {
      var dz = c.z_m - target, reach = dmax > Math.abs(dz) ? Math.sqrt(dmax * dmax - dz * dz) : 0;
      return { x: c.x_m, y: c.y_m, reach: reach, aim: aimOf(c) };
    });
    res.reach = dmax;
    test = function (x, y) {
      for (var i = 0; i < cams.length; i++) {
        var c = cams[i], dx = x - c.x, dy = y - c.y, d = Math.sqrt(dx * dx + dy * dy);
        if (d <= c.reach && d > 0.05 && Math.abs(angleDiff(Math.atan2(dy, dx) * 180 / Math.PI, c.aim)) <= half) return true;
      }
      return false;
    };
  } else if (kind === "sounder") {
    // SPT-FA-13: required = max(L_avg + 15, L_max + 5), measured 1.5 m AFF,
    // never above 110 dBA. Level falls 6 dB per doubling of distance (free
    // field); reflections would only add, so this errs on the quiet side.
    var out = setting("sounder", "out_dba"), need = Math.max(setting("sounder", "avg_dba") + 15, setting("sounder", "max_dba") + 5);
    var through = setting("sounder", "through_walls"), loss = setting("sounder", "wall_db") || 0, ear = r.base + 1.5;
    var srcs = (through ? onLevel : inRoom).map(function (s) {
      return { x: s.x_m, y: s.y_m, z: s.z_m, l: out - (inRoom.indexOf(s) >= 0 ? 0 : loss) };
    });
    res.required = need;
    test = function (x, y) {
      var e = 0;
      for (var i = 0; i < srcs.length; i++) {
        var s = srcs[i], d = Math.max(1, Math.sqrt((s.x - x) * (s.x - x) + (s.y - y) * (s.y - y) + (s.z - ear) * (s.z - ear)));
        e += Math.pow(10, (s.l - 20 * Math.log10(d)) / 10);
      }
      var level = e > 0 ? 10 * Math.log10(e) : -Infinity;
      if (level > 110) res.loud.push([x, y]);
      return level >= need;
    };
  }

  cells.forEach(function (c) {
    if (test(c[0], c[1])) res.covered++;
    else res.uncovered.push(c);
  });
  res.pct = res.covered / res.total * 100;
  res.gapArea = res.uncovered.length * step * step;
  return res;
}

// ---------- running and drawing ----------
function clearOverlay() {
  Object.keys(G.storeys).forEach(function (k) {
    var ov = G.storeys[k].overlay;
    while (ov.children.length) { var c = ov.children.pop(); disposeTree(c); }
  });
  S.rooms.forEach(function (r) { if (r.mesh) r.mesh.material.color.set(css("--scene-floor")); });
  G.labels.forEach(function (l) { l.pct.textContent = ""; l.pct.className = "pct"; });
  $("legendCov").style.display = "none";
}

function statusOf(pct) { return pct >= 99.95 ? "ok" : pct >= 90 ? "warn" : "bad"; }

function runCoverage() {
  clearOverlay();
  var kind = S.analysis, A = ANALYSES[kind], miss = missingInputs(kind);
  if (miss.length) {
    S.coverage = { kind: kind, missing: miss };
    renderModePanel();
    return;
  }
  var rooms = S.rooms.filter(onStorey);
  var devs = activeDevices(A.types).filter(onStorey);
  var byRoom = {}, byLevel = {};
  devs.forEach(function (d) {
    var r = roomOf(d);
    if (r) (byRoom[r.id] = byRoom[r.id] || []).push(d);
    (byLevel[d.storey] = byLevel[d.storey] || []).push(d);
  });
  var results = rooms.map(function (r) { return evaluateRoom(kind, r, byRoom[r.id] || [], byLevel[r.storey] || []); });

  drawCoverage(kind, results, devs);
  var assessed = results.filter(function (x) { return x.total > 0; });
  S.coverage = {
    kind: kind, rooms: results,
    full: assessed.filter(function (x) { return x.pct >= 99.95; }).length,
    assessed: assessed.length,
    gapArea: assessed.reduce(function (s, x) { return s + x.gapArea; }, 0),
    devices: devs.length,
    illustrative: anyIllustrative(kind),
    outside: devs.filter(function (d) { return !roomOf(d); }).length
  };
  renderModePanel();
  legend(kind);
}

function drawCoverage(kind, results, devs) {
  var bad = new THREE.Color(css("--bad")), warn = new THREE.Color(css("--warn")), ok = new THREE.Color(css("--ok"));
  var floor = new THREE.Color(css("--scene-floor"));
  var sysCol = new THREE.Color(sysColor(kind === "cctv" ? "cctv" : "fire_alarm"));

  results.forEach(function (res) {
    var r = res.room, lab = G.labels.find(function (l) { return l.room === r; });
    if (!res.total) { if (lab) lab.pct.textContent = " · n/a"; return; }
    var st = statusOf(res.pct);
    r.mesh.material.color.copy(floor).lerp(st === "ok" ? ok : st === "warn" ? warn : bad, 0.55);
    if (lab) { lab.pct.textContent = " · " + Math.floor(res.pct) + "%"; lab.pct.className = "pct " + st + "-t"; }
  });

  // Reach of each device, drawn where it applies: ceiling discs for
  // detectors, floor wedges for cameras.
  devs.forEach(function (d) {
    var r = roomOf(d);
    if (!r) return;
    var res = results.find(function (x) { return x.room === r; });
    if (!res || !res.total) return;
    var node = storeyNode(d.storey), mat = new THREE.MeshBasicMaterial({ color: sysCol, transparent: true, opacity: 0.12,
      side: THREE.DoubleSide, depthWrite: false });
    var lineMat = new THREE.LineBasicMaterial({ color: sysCol, transparent: true, opacity: 0.6 });
    var p;
    if ((kind === "smoke" || kind === "heat") && res.radius) {
      p = L(d.x_m, d.y_m, d.z_m - 0.06);
      var disc = new THREE.Mesh(new THREE.CircleGeometry(res.radius, 48), mat);
      disc.position.set(p[0], p[1], p[2]);
      node.overlay.add(disc);
      var ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
        new THREE.EllipseCurve(0, 0, res.radius, res.radius, 0, Math.PI * 2).getPoints(64)), lineMat);
      ring.position.copy(disc.position);
      node.overlay.add(ring);
    } else if (kind === "cctv" && res.reach) {
      var target = r.base + setting("cctv", "target_m"), dz = d.z_m - target;
      var reach = res.reach > Math.abs(dz) ? Math.sqrt(res.reach * res.reach - dz * dz) : 0;
      if (reach <= 0) return;
      var half = setting("cctv", "hfov_deg") * Math.PI / 360, aim = aimOf(d) * Math.PI / 180;
      p = L(d.x_m, d.y_m, r.base + 0.05);
      var wedge = new THREE.Mesh(new THREE.CircleGeometry(reach, 48, aim - half, half * 2), mat);
      wedge.position.set(p[0], p[1], p[2]);
      node.overlay.add(wedge);
    }
  });

  // Uncovered sample points, one instanced mesh per storey.
  var perStorey = {};
  results.forEach(function (res) {
    var key = res.room.storey;
    (perStorey[key] = perStorey[key] || { gaps: [], loud: [] });
    res.uncovered.forEach(function (c) { perStorey[key].gaps.push([c[0], c[1], res.room.base, res.step]); });
    res.loud.forEach(function (c) { perStorey[key].loud.push([c[0], c[1], res.room.base, res.step]); });
  });
  var m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3(), pos = new THREE.Vector3();
  Object.keys(perStorey).forEach(function (key) {
    [["gaps", bad], ["loud", warn]].forEach(function (pair) {
      var list = perStorey[key][pair[0]];
      if (!list.length) return;
      if (list.length > 60000) list = list.filter(function (_, i) { return i % Math.ceil(list.length / 60000) === 0; });
      var mesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1),
        new THREE.MeshBasicMaterial({ color: pair[1], transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide }), list.length);
      list.forEach(function (c, i) {
        var p = L(c[0], c[1], c[2] + 0.04);
        pos.set(p[0], p[1], p[2]);
        sc.set(c[3] * 0.86, c[3] * 0.86, 1);
        mesh.setMatrixAt(i, m4.compose(pos, q, sc));
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.renderOrder = 2;
      storeyNode(key).overlay.add(mesh);
    });
  });
}

function legend(kind) {
  var el = $("legendCov"), A = ANALYSES[kind];
  var sw = function (v) { return '<span class="sw" style="background:' + css(v) + '"></span>'; };
  var extra = kind === "sounder" ? sw("--warn") + "over 110 dBA" : "";
  el.innerHTML = "<b>" + esc(A.title) + "</b> · rooms: " + sw("--ok") + "covered" + sw("--warn") + "≥ 90 %" + sw("--bad") + "< 90 %"
    + "<br>squares: " + sw("--bad") + "not reached" + extra
    + (S.coverage && S.coverage.illustrative ? '<br><span class="warn-t">Computed with illustrative values.</span>' : "");
  el.style.display = "block";
}

function coverageCsv() {
  var c = S.coverage;
  if (!c || !c.rooms) return null;
  var A = ANALYSES[c.kind];
  var rows = [["analysis", "rules", "storey", "room", "devices_in_room", "sampled_points", "covered_pct", "gap_area_m2", "note"]];
  c.rooms.forEach(function (x) {
    rows.push([A.title, A.rules.join(" "), x.room.storey, x.room.label, x.devices, x.total,
      x.total ? x.pct.toFixed(1) : "", x.total ? x.gapArea.toFixed(2) : "", x.note || ""]);
  });
  var settings = Object.keys(SET[c.kind]).map(function (k) {
    return (FIELD_LABELS[k] || k) + "=" + SET[c.kind][k].v + " (" + (SET[c.kind][k].src || "unset") + ")";
  }).join("; ");
  rows.push([]);
  rows.push(["settings", settings]);
  rows.push(["model", S.result.outputs.model.source, S.result.outputs.model.authoring_application || ""]);
  return rows.map(function (r) {
    return r.map(function (v) { v = String(v == null ? "" : v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(",");
  }).join("\n");
}

// ---------- what-if: proposals ----------
function setTool(tool) {
  S.tool = tool;
  var hint = $("placeHint");
  if (tool === "place") { hint.textContent = "Click inside a room to place a " + words(S.placeType) + " · Esc to stop"; hint.style.display = "block"; }
  else if (tool === "ignite") { hint.textContent = "Click inside a room to start the fire · Esc to cancel"; hint.style.display = "block"; }
  else hint.style.display = "none";
  $("canvas").style.cursor = tool ? "crosshair" : "";
  renderModePanel();
}

function placeProposal(room, point) {
  var spec = PROPOSABLE[S.placeType], type = S.placeType;
  var z = spec.at === "ceiling" ? room.base + room.height - (type === "camera" ? 0.1 : 0) : room.base + spec.at;
  var n = ++S.proposals;
  var aim = type === "camera" ? Math.atan2(room.center[1] - point[1], room.center[0] - point[0]) * 180 / Math.PI : 0;
  var d = {
    id: "proposal-" + n, device_type: type, system: spec.system, name: "Proposed " + words(type) + " " + n,
    type_name: null, tag: null, ifc_class: null, predefined_type: null, storey: room.storey, space: room.label,
    space_basis: "located", x_m: +point[0].toFixed(3), y_m: +point[1].toFixed(3), z_m: +z.toFixed(3),
    yaw_deg: +aim.toFixed(1), position_basis: "simulator", source_reference: "placed in the simulator",
    proposed: true, roomId: room.id, height_note: spec.note || null
  };
  S.devices.push(d);
  addDeviceObject(d);
  afterChange();
  toast("Placed " + d.name + " in " + room.label + ".");
}

function removeProposal(d) {
  removeDeviceObject(d.id);
  S.devices = S.devices.filter(function (x) { return x !== d; });
  if (S.selected && S.selected.ref === d) select(null);
  afterChange();
}

function proposalsJson() {
  var list = S.devices.filter(function (d) { return d.proposed; }).map(function (d) {
    return { device_type: d.device_type, system: d.system, storey: d.storey, room: d.space,
      x_m: d.x_m, y_m: d.y_m, z_m: d.z_m, yaw_deg: d.device_type === "camera" ? aimOf(d) : null,
      height_basis: d.height_note || "room ceiling height from the model",
      status: "proposal from the simulator — not a design, not a quantity" };
  });
  return JSON.stringify({ model: S.result.outputs.model, out_of_service: Object.keys(S.disabled),
    camera_aims_set: S.aim, proposals: list }, null, 1);
}

function afterChange() {
  if (S.mode === "coverage") runCoverage();
  renderSysList();
  renderInspector();
}
