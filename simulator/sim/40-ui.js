// ---------- the rail ----------

var SRC_LABEL = { rule: "from rule", example: "rule's worked example", illustrative: "illustrative",
  entered: "entered", null: "required" };

function renderAll() {
  $("empty").style.display = "none";
  var out = S.result.outputs, m = out.model || {};
  $("title").textContent = m.project_long_name || m.project || "Building simulator";
  document.title = (m.project || "Building") + " · ELV simulator";
  var pill = $("statusPill");
  var proto = S.result.tool === "bim.prototype";
  pill.textContent = proto ? "prototype" : S.result.status === "ok" ? "model ok" : words(S.result.status);
  pill.className = "pill " + (S.result.status === "ok" ? "ok" : "warn");
  var sel = $("storeySel");
  sel.innerHTML = '<option value="__all__">All storeys</option>' + S.storeys.map(function (s) {
    return '<option value="' + esc(s.name) + '">' + esc(s.name) + (s.elevation_m != null ? " (" + fmt(s.elevation_m) + " m)" : "") + "</option>";
  }).join("");
  sel.value = S.storey;
  renderModelInfo();
  renderSysList();
  renderModePanel();
  renderInspector();
  renderFindings();
  renderRules();
}

function renderModelInfo() {
  var out = S.result.outputs, m = out.model || {}, meta = S.meta || {};
  var fixture = meta.fixture ? '<div class="banner">' + esc(meta.fixture) + "</div>" : "";
  $("modelInfo").innerHTML = fixture + '<dl class="kv">'
    + "<dt>Source</dt><dd>" + esc(m.source || "—") + "</dd>"
    + "<dt>Written by</dt><dd>" + esc(m.authoring_application || "unknown") + (m.is_revit_export ? " · Revit export" : "") + "</dd>"
    + "<dt>Schema</dt><dd>" + esc(m.schema || "—") + "</dd>"
    + "<dt>Storeys</dt><dd>" + S.storeys.length + "</dd>"
    + "<dt>Rooms</dt><dd>" + S.rooms.length + " with an outline" + (S.roomsWithoutOutline.length ? ", " + S.roomsWithoutOutline.length + " without" : "") + "</dd>"
    + "<dt>Devices</dt><dd>" + S.devices.filter(function (d) { return !d.proposed; }).length + " placed"
      + (S.devices.some(function (d) { return d.proposed && d.rule; }) ? ", " + S.devices.filter(function (d) { return d.proposed && d.rule; }).length + " proposed from rules" : "")
      + (S.unplaced.length ? ", " + S.unplaced.length + " with no position" : "") + "</dd>"
    + "<dt>Element map</dt><dd>" + esc((out.element_map || {}).name || "—") + "</dd>"
    + "<dt>Engine</dt><dd class=\"mono\">" + esc(S.result.engine_version || "") + "</dd></dl>"
    + (S.result.tool === "bim.prototype"
      ? '<div class="banner">A prototype proposed from floor plans: walls, openings and rooms are traced from the drawings; heights, finishes and furniture are assumed. Review it against the drawings before relying on it.</div>'
      : '<p class="note">Positions, heights and room outlines are read from the model. Coverage uses the rules listed below; anything else is a setting you enter.</p>')
    + assumptionsHtml();
  renderBuildingInfo();
}

function assumptionsHtml() {
  var list = S.result.assumptions || [];
  if (!list.length) return "";
  return "<h3>Assumed (" + list.filter(function (a) { return a.status !== "verified"; }).length + ")</h3><ul class=\"flat\">"
    + list.map(function (a) {
      return "<li><b>" + esc(words(a.key)) + "</b> " + esc(a.value) + (a.unit ? " " + esc(a.unit) : "")
        + (a.status === "verified" ? ' <span class="ok-t">verified</span>' : ' <span class="warn-t">assumed</span>')
        + '<div class="note">' + esc(a.basis) + " · check: " + esc(a.verify_from) + "</div></li>";
    }).join("") + "</ul>";
}

function renderBuildingInfo() {
  var b = S.result.outputs.building;
  if (!b) return;
  $("bldInfo").innerHTML = '<table class="res"><thead><tr><th>Level</th><th class="num">Rooms</th><th class="num">Doors</th><th class="num">Windows</th></tr></thead><tbody>'
    + b.levels.map(function (l) {
      return "<tr><td>" + esc(l.name) + '<div class="note" style="margin:0">' + esc(l.source.file) + " · " + esc(l.source.scale || "")
        + " · walls " + fmt(l.source.wall_thickness_m, 2) + ' m</div></td><td class="num">' + (l.counts.rooms || 0)
        + '</td><td class="num">' + ((l.counts.door || 0) + (l.counts.opening || 0)) + '</td><td class="num">' + (l.counts.window || 0) + "</td></tr>";
    }).join("") + "</tbody></table>"
    + '<p class="note">Click a door or window to see why it was read that way.</p>';
  var top = b.roof.z + (b.roof.parapet_height_m || 0);
  $("optCut").max = String(Math.ceil(top * 10) / 10);
  $("optCut").step = "0.1";
  $("optCut").value = $("optCut").max;
  BLD.cut = null;
}

function renderSysList() {
  var counts = {};
  S.devices.forEach(function (d) { if (onStorey(d)) counts[d.system] = (counts[d.system] || 0) + 1; });
  var systems = Object.keys(counts).sort();
  $("sysList").innerHTML = systems.length ? systems.map(function (s) {
    return '<label class="chk"><input type="checkbox" data-sys="' + esc(s) + '"' + (S.hidden[s] ? "" : " checked") + '>'
      + '<span class="sw-dot" style="background:' + sysColor(s) + '"></span>' + esc(words(s))
      + '<span class="count">' + counts[s] + "</span></label>";
  }).join("") : '<p class="note">No devices on this storey.</p>';
  $("sysList").querySelectorAll("input[data-sys]").forEach(function (inp) {
    inp.addEventListener("change", function () {
      S.hidden[inp.dataset.sys] = !inp.checked;
      applyVisibility();
    });
  });
}

// One settings field: an input, and a line saying where its value came from.
function fieldHtml(group, key) {
  var f = SET[group][key], label = FIELD_LABELS[key] || key, input;
  if (key === "dori") {
    input = '<select data-set="' + group + "." + key + '">' + Object.keys(DORI).map(function (k) {
      return '<option value="' + k + '"' + (f.v === k ? " selected" : "") + ">" + k + " · " + DORI[k] + " px/m</option>";
    }).join("") + "</select>";
  } else if (key === "scope") {
    input = '<select data-set="drill.scope"><option value="storey"' + (f.v === "storey" ? " selected" : "") + '>fire storey</option>'
      + '<option value="building"' + (f.v === "building" ? " selected" : "") + ">whole building</option></select>";
  } else if (key === "through_walls") {
    input = '<input type="checkbox" data-set="sounder.through_walls"' + (f.v ? " checked" : "") + " style=\"width:auto\">";
  } else {
    input = '<input type="number" step="any" min="0" inputmode="decimal" data-set="' + group + "." + key + '" value="'
      + (f.v == null ? "" : f.v) + '" placeholder="required">';
  }
  var src = f.src ? SRC_LABEL[f.src] : "required";
  var cls = f.src === "illustrative" || f.src === "example" ? "warn-t" : f.src ? "" : "bad-t";
  return '<div class="field"><label>' + esc(label) + "</label>" + input
    + '<div class="src"><span class="' + cls + '">' + esc(src) + "</span> · " + esc(f.why) + "</div></div>";
}

function bindFields(scope, onChange) {
  scope.querySelectorAll("[data-set]").forEach(function (el) {
    el.addEventListener("change", function () {
      var parts = el.dataset.set.split("."), f = SET[parts[0]][parts[1]];
      if (el.type === "checkbox") f.v = el.checked;
      else if (el.tagName === "SELECT") f.v = el.value;
      else {
        var n = el.value.trim() === "" ? null : Number(el.value);
        if (n != null && !(isFinite(n) && n >= 0)) { toast("Enter a number of zero or more."); el.value = f.v == null ? "" : f.v; return; }
        f.v = n;
      }
      f.src = f.v == null ? null : "entered";
      onChange();
    });
  });
}

function fillIllustrative(group) {
  Object.keys(ILLUSTRATIVE[group]).forEach(function (k) {
    SET[group][k].v = ILLUSTRATIVE[group][k];
    SET[group][k].src = "illustrative";
  });
}

function ruleRefs(codes) {
  return codes.map(function (c) {
    var r = S.rules[c];
    return r ? '<span class="mono">' + esc(c) + "</span> " + esc(r.source) : '<span class="mono">' + esc(c) + "</span>";
  }).join(" · ");
}

function renderModePanel() {
  var p = $("modePanel"), html = "";
  if (S.mode === "inspect") {
    var types = {};
    S.devices.forEach(function (d) { if (onStorey(d)) types[d.device_type] = (types[d.device_type] || 0) + 1; });
    html = '<p class="note">Click a device or a room to see what the model says about it. Drag to turn, right-drag or shift-drag to pan, scroll to zoom.</p>';
    if (!Object.keys(types).length) {
      p.innerHTML = html + '<p class="note">No placed devices on this view.</p>';
      return;
    }
    html += '<table class="res"><thead><tr><th>Device type</th><th class="num">On view</th></tr></thead><tbody>'
      + Object.keys(types).sort().map(function (t) { return "<tr><td>" + esc(words(t)) + '</td><td class="num">' + types[t] + "</td></tr>"; }).join("")
      + "</tbody></table>";
    p.innerHTML = html;
    return;
  }

  if (S.mode === "coverage") {
    var kind = S.analysis, A = ANALYSES[kind], c = S.coverage && S.coverage.kind === kind ? S.coverage : null;
    html += '<div class="tabs">' + Object.keys(ANALYSES).map(function (k) {
      return '<button class="seg" data-an="' + k + '" aria-pressed="' + (k === kind) + '">' + esc(ANALYSES[k].label) + "</button>";
    }).join("") + "</div>";
    html += '<p class="note">' + ruleRefs(A.rules) + "</p>";
    html += Object.keys(SET[kind]).map(function (k) { return fieldHtml(kind, k); }).join("");
    if (kind === "cctv") {
      var reach = cctvReach();
      html += '<p class="note">Max distance for ' + esc(setting("cctv", "dori")) + ": <b>" + fmt(reach, 1) + " m</b> (SPT-CC-03). "
        + "A camera's aim is not in the IFC model; it starts along the family's X axis — set it per camera in Selection.</p>";
    }
    if (kind === "smoke") html += '<p class="note">Radius 0.7 × S = <b>' + fmt(0.7 * setting("smoke", "spacing_m")) + " m</b> on the ceiling (SPT-FA-02).</p>";
    if (kind === "heat") html += '<p class="note">Spacing is reduced for the room\'s modelled ceiling height (SPT-FA-04), then the 0.7 × S radius is applied.</p>';
    if (kind === "sounder" && ILLUSTRATIVE.sounder) {
      html += '<div class="row"><button class="btn sm" data-illus="sounder">Use illustrative values</button></div>';
      if (setting("sounder", "out_dba") != null && setting("sounder", "avg_dba") != null && setting("sounder", "max_dba") != null) {
        html += '<p class="note">Required at 1.5 m: <b>' + fmt(Math.max(setting("sounder", "avg_dba") + 15, setting("sounder", "max_dba") + 5), 1)
          + " dBA</b>. Free-field fall-off, 6 dB per doubling of distance; room reflections would only add level.</p>";
      }
    }

    if (c && c.missing) {
      html += '<div class="banner">To run this check, enter: ' + esc(c.missing.join(", ")) + ".</div>";
    } else if (c) {
      if (c.illustrative) html += '<div class="banner">Computed with illustrative values — not a design check.</div>';
      html += '<h3>' + c.full + " of " + c.assessed + " rooms fully covered</h3>"
        + '<p class="note">' + c.devices + " " + (c.devices === 1 ? "device" : "devices") + " in scope · "
        + fmt(c.gapArea, 1) + " m² not reached" + (c.outside ? " · " + c.outside + " outside any room (not counted)" : "") + "</p>";
      var rows = c.rooms.slice().sort(function (a, b) { return (a.total ? a.pct : 101) - (b.total ? b.pct : 101); });
      html += '<table class="res"><thead><tr><th>Room</th><th class="num">Dev.</th><th class="num">Covered</th><th class="num">Gap m²</th></tr></thead><tbody>'
        + rows.map(function (x) {
          var st = x.total ? statusOf(x.pct) : "";
          return '<tr data-room="' + esc(x.room.id) + '"><td>' + esc(x.room.label)
            + (S.storey === "__all__" ? '<div class="note" style="margin:0">' + esc(x.room.storey) + "</div>" : "")
            + (x.note ? '<div class="note" style="margin:0">' + esc(x.note) + "</div>" : "") + '</td><td class="num">' + x.devices
            + '</td><td class="num ' + st + '-t">' + (x.total ? Math.floor(x.pct) + "%" : "n/a") + '</td><td class="num">'
            + (x.total ? fmt(x.gapArea, 1) : "") + "</td></tr>";
        }).join("") + "</tbody></table>";
    }

    html += "<h3>What if</h3>"
      + '<p class="note">Take a device out of service from Selection, or add one:</p>'
      + '<div class="row"><select data-place class="btn sm" aria-label="Device to place">' + Object.keys(PROPOSABLE).map(function (t) {
        return '<option value="' + t + '"' + (t === S.placeType ? " selected" : "") + ">" + esc(words(t)) + "</option>";
      }).join("") + "</select>"
      + '<button class="btn sm' + (S.tool === "place" ? " primary" : "") + '" data-act="place">' + (S.tool === "place" ? "Placing… (Esc)" : "Place") + "</button>"
      + '<button class="btn sm" data-act="clear">Clear proposals</button></div>'
      + '<div class="row" style="margin-top:8px"><button class="btn sm" data-act="csv"' + (c && c.rooms ? "" : " disabled") + ">Coverage CSV</button>"
      + '<button class="btn sm" data-act="json">Proposals JSON</button></div>';
    p.innerHTML = html;

    p.querySelectorAll("[data-an]").forEach(function (b) {
      b.addEventListener("click", function () { S.analysis = b.dataset.an; runCoverage(); });
    });
    bindFields(p, runCoverage);
    p.querySelectorAll("[data-illus]").forEach(function (b) {
      b.addEventListener("click", function () { fillIllustrative(b.dataset.illus); runCoverage(); });
    });
    p.querySelectorAll("tr[data-room]").forEach(function (tr) {
      tr.addEventListener("click", function () {
        var r = roomById(tr.dataset.room);
        if (r) { focusRoom(r); select({ kind: "room", ref: r }); }
      });
    });
    p.querySelector("[data-place]").addEventListener("change", function (e) {
      S.placeType = e.target.value;
      if (S.tool === "place") setTool("place");
    });
    p.querySelector('[data-act="place"]').addEventListener("click", function () { setTool(S.tool === "place" ? null : "place"); });
    p.querySelector('[data-act="clear"]').addEventListener("click", function () {
      S.devices.filter(function (d) { return d.proposed; }).forEach(function (d) { removeDeviceObject(d.id); });
      S.devices = S.devices.filter(function (d) { return !d.proposed; });
      if (S.selected && S.selected.ref && S.selected.ref.proposed) select(null);
      afterChange();
    });
    p.querySelector('[data-act="csv"]').addEventListener("click", function () {
      var csv = coverageCsv();
      if (csv) download("coverage-" + S.analysis + ".csv", csv, "text/csv");
    });
    p.querySelector('[data-act="json"]').addEventListener("click", function () {
      download("simulator-proposals.json", proposalsJson(), "application/json");
    });
    return;
  }

  // Fire drill
  var d = S.drill;
  html += '<p class="note">Click <b>Start a fire</b>, then a room. Or click a manual call point to raise the alarm by hand.</p>';
  html += Object.keys(SET.drill).map(function (k) { return fieldHtml("drill", k); }).join("");
  html += '<div class="row"><button class="btn sm" data-illus="drill">Use illustrative values</button>'
    + '<button class="btn sm ' + (S.tool === "ignite" ? "" : "primary") + '" data-act="ignite">' + (S.tool === "ignite" ? "Click a room… (Esc)" : "Start a fire") + "</button></div>";
  if (d) {
    if (d.illustrative) html += '<div class="banner">Timings use illustrative values — the sequence is the point, not the seconds.</div>';
    var first = d.detections && d.detections[0], alarm = d.events.find(function (e) { return e.kind === "alarm"; });
    html += '<dl class="kv" style="margin-top:10px">'
      + "<dt>Origin</dt><dd>" + esc(d.manual ? (d.manual.name || "call point") : d.room.label) + "</dd>"
      + "<dt>Detected</dt><dd>" + (d.manual ? "manual" : first ? clock(first.t) + " by " + esc(first.d.name || words(first.d.device_type)) : '<span class="bad-t">not automatically</span>') + "</dd>"
      + "<dt>Alarm</dt><dd>" + (alarm ? clock(alarm.t) : "—") + "</dd>"
      + "<dt>Sounders</dt><dd>" + ((d.sounders || []).length) + " in scope</dd></dl>";
    html += '<h3>Event log</h3><div class="log"></div>';
  }
  p.innerHTML = html;
  bindFields(p, function () { if (S.drill) { resetDrill(); } renderModePanel(); });
  p.querySelector("[data-illus]").addEventListener("click", function () { fillIllustrative("drill"); renderModePanel(); });
  p.querySelector('[data-act="ignite"]').addEventListener("click", function () {
    if (S.tool === "ignite") { setTool(null); return; }
    if (drillReady(false)) setTool("ignite");
  });
  if (d) renderDrillLog();
}

function renderInspector() {
  var el = $("inspector"), sel = S.selected;
  if (!sel) { el.innerHTML = '<p class="note">Click a device or a room.</p>'; return; }
  if (sel.kind === "opening") {
    var op = sel.ref;
    el.innerHTML = "<h3 style=\"margin-top:0\">" + esc(op.kind === "opening" ? "Opening" : words(op.kind)) + " · " + esc(sel.level) + "</h3>"
      + '<dl class="kv"><dt>Width</dt><dd>' + fmt(op.width_m, 2) + " m</dd>"
      + "<dt>Wall</dt><dd>" + fmt(op.thickness_m, 2) + " m thick, " + (op.exterior ? "outside wall" : "inside wall") + "</dd>"
      + "<dt>Read as</dt><dd>" + esc(op.evidence) + "</dd>"
      + (op.kind === "window" ? "<dt>Sill · head</dt><dd>" + fmt(op.sill_m, 2) + " · " + fmt(op.head_m, 2) + ' m <span class="warn-t">assumed</span></dd>'
        : "<dt>Head</dt><dd>" + fmt(op.head_m, 2) + ' m <span class="warn-t">assumed</span></dd>')
      + "<dt>Position</dt><dd class=\"mono\">" + fmt(op.center[0], 2) + ", " + fmt(op.center[1], 2) + "</dd></dl>";
    return;
  }
  if (sel.kind === "device") {
    var d = sel.ref, r = roomOf(d), cam = d.device_type === "camera" || d.device_type === "ptz_camera";
    var basis = d.position_basis === "geometry" ? "from the geometry — the family was exported with its placement at the origin"
      : d.position_basis === "simulator" ? "placed in the simulator"
      : d.position_basis === "proposed" ? "proposed by rule" : "from the element's placement";
    el.innerHTML = "<h3 style=\"margin-top:0\">" + esc(d.name || words(d.device_type)) + "</h3>"
      + (d.proposed ? '<div class="banner info">' + (d.rule ? "Proposed from the rules library — not in the drawings." : "Proposal made in the simulator — not in the model.") + "</div>" : "")
      + (S.disabled[d.id] ? '<div class="banner">Out of service in this what-if.</div>' : "")
      + '<dl class="kv">'
      + "<dt>Type</dt><dd>" + esc(words(d.device_type)) + " · " + esc(words(d.system)) + "</dd>"
      + (d.type_name ? "<dt>Family:Type</dt><dd>" + esc(d.type_name) + "</dd>" : "")
      + (d.ifc_class ? "<dt>IFC</dt><dd class=\"mono\">" + esc(d.ifc_class) + (d.predefined_type ? " · " + esc(d.predefined_type) : "") + "</dd>" : "")
      + (d.tag ? "<dt>Revit id</dt><dd class=\"mono\">" + esc(d.tag) + "</dd>" : "")
      + "<dt>Storey</dt><dd>" + esc(d.storey) + "</dd>"
      + "<dt>Room</dt><dd>" + (r ? esc(r.label) + (d.space_basis === "model" ? "" : ' <span class="note">(by position)</span>') : '<span class="warn-t">outside every room</span>') + "</dd>"
      + "<dt>Position</dt><dd class=\"mono\">" + fmt(d.x_m, 3) + ", " + fmt(d.y_m, 3) + ", " + fmt(d.z_m, 3) + " m</dd>"
      + "<dt>Basis</dt><dd>" + esc(basis) + "</dd>"
      + (r ? "<dt>Above floor</dt><dd>" + fmt(d.z_m - r.base, 2) + " m" + (d.height_note ? " · " + esc(d.height_note) : "") + "</dd>" : "")
      + (d.global_id || d.id ? "<dt>Source</dt><dd class=\"mono\">" + esc(d.source_reference) + "</dd>" : "")
      + (d.rule ? "<dt>Rule</dt><dd><span class=\"mono\">" + esc(d.rule) + "</span><div class=\"note\" style=\"margin:2px 0 0\">" + esc(d.basis || "") + "</div></dd>" : "")
      + "</dl>"
      + (cam ? '<div class="field" style="margin-top:10px"><label>Aim (°, 0 = east, 90 = north)</label><input type="number" step="5" data-aim value="' + Math.round(aimOf(d) * 10) / 10 + '">'
        + '<div class="src">' + (S.aim[d.id] != null ? "set in the simulator" : "the family's X axis — not a statement of where it looks") + "</div></div>"
        + '<input type="range" min="-180" max="180" step="1" data-aimr value="' + Math.round(aimOf(d)) + '" aria-label="Aim">' : "")
      + '<div class="row" style="margin-top:10px">'
      + (d.proposed ? '<button class="btn sm" data-act="remove">Remove proposal</button>'
        : '<button class="btn sm" data-act="toggle">' + (S.disabled[d.id] ? "Return to service" : "Take out of service") + "</button>")
      + "</div>";
    var tog = el.querySelector('[data-act="toggle"]');
    if (tog) tog.addEventListener("click", function () {
      if (S.disabled[d.id]) delete S.disabled[d.id]; else S.disabled[d.id] = true;
      styleDevice(d);
      afterChange();
    });
    var rm = el.querySelector('[data-act="remove"]');
    if (rm) rm.addEventListener("click", function () { removeProposal(d); });
    var setAim = function (v) {
      if (!isFinite(v)) return;
      S.aim[d.id] = ((v + 540) % 360) - 180;
      var g = G.deviceObjs[d.id];
      if (g) g.rotation.z = S.aim[d.id] * Math.PI / 180;
      if (S.mode === "coverage" && S.analysis === "cctv") runCoverage();
    };
    var aimIn = el.querySelector("[data-aim]"), aimR = el.querySelector("[data-aimr]");
    if (aimIn) aimIn.addEventListener("change", function () { setAim(Number(aimIn.value)); renderInspector(); });
    if (aimR) aimR.addEventListener("input", function () { setAim(Number(aimR.value)); aimIn.value = aimR.value; });
    return;
  }
  var rm2 = sel.ref, inRoom = S.devices.filter(function (x) { return roomOf(x) === rm2; }), byType = {};
  inRoom.forEach(function (x) { byType[x.device_type] = (byType[x.device_type] || 0) + 1; });
  var diff = rm2.area && rm2.outlineArea ? Math.abs(rm2.outlineArea - rm2.area) / rm2.area : null;
  el.innerHTML = "<h3 style=\"margin-top:0\">" + esc(rm2.label) + "</h3><dl class=\"kv\">"
    + "<dt>Storey</dt><dd>" + esc(rm2.storey) + "</dd>"
    + "<dt>Floor area</dt><dd>" + (rm2.area != null ? fmt(rm2.area) + " m² <span class=\"note\">(" + esc(rm2.areaSource) + ")</span>" : '<span class="warn-t">not in the model</span>') + "</dd>"
    + "<dt>Outline</dt><dd>" + fmt(rm2.outlineArea) + " m²" + (diff != null && diff > 0.02 ? ' <span class="warn-t">differs from the quantity by ' + fmt(diff * 100, 1) + "%</span>" : "") + "</dd>"
    + "<dt>Height</dt><dd>" + fmt(rm2.height) + " m <span class=\"note\">(room extrusion)</span></dd>"
    + "<dt>Devices</dt><dd>" + (inRoom.length ? Object.keys(byType).sort().map(function (t) { return byType[t] + " " + esc(words(t)); }).join(", ") : "none") + "</dd>"
    + "</dl>";
}

function renderFindings() {
  var r = S.result, out = r.outputs, html = "";
  if (r.missing && r.missing.length) {
    html += "<h3 style=\"margin-top:0\">Not counted (" + r.missing.length + ")</h3><ul class=\"flat\">"
      + r.missing.map(function (m) { return "<li><b>" + esc(m.record) + "</b><div class=\"note\">" + esc(m.note || m.field) + "</div></li>"; }).join("") + "</ul>";
  }
  if (r.findings && r.findings.length) {
    html += "<h3>Findings</h3><ul class=\"flat\">" + r.findings.map(function (f) {
      return '<li><span class="sev ' + esc(f.severity) + '">' + esc(f.severity) + "</span><span class=\"mono\">" + esc(f.code) + "</span>"
        + '<div>' + esc(f.detail) + '</div><div class="note">' + esc(f.action) + "</div></li>";
    }).join("") + "</ul>";
  }
  if (r.warnings && r.warnings.length) {
    html += "<h3>Warnings</h3><ul class=\"flat\">" + r.warnings.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul>";
  }
  if (out.counts && out.counts.length) {
    html += '<h3>Counted devices</h3><table class="res"><thead><tr><th>System</th><th>Type</th><th class="num">Qty</th></tr></thead><tbody>'
      + out.counts.map(function (c) { return "<tr><td>" + esc(words(c.system)) + "</td><td>" + esc(words(c.device_type)) + '</td><td class="num">' + c.quantity + "</td></tr>"; }).join("")
      + "</tbody></table><p class=\"note\">Counts are proposals for review, as from every craft tool.</p>";
  }
  $("findings").innerHTML = html || '<p class="note">Nothing to report.</p>';
}

function renderRules() {
  var codes = Object.keys(S.rules);
  $("rulesList").innerHTML = codes.length ? codes.map(function (c) {
    var r = S.rules[c];
    return '<details class="rule"><summary><span class="mono">' + esc(c) + "</span> " + esc(r.name) + "</summary>"
      + "<p><b>Source:</b> " + esc(r.source) + (r.overlay ? " · " + esc(r.overlay) : "") + "</p>"
      + (r.condition ? "<p><b>When:</b> " + esc(r.condition) + "</p>" : "")
      + "<p><b>Limit:</b> " + esc(r.value_limit) + "</p>"
      + (r.calculation ? "<p><b>Calculation:</b> " + esc(r.calculation) + "</p>" : "")
      + "<p>" + esc(r.verification_note) + "</p></details>";
  }).join("") + '<p class="note">From the SPT engineering rules library (migration 0017). The build stops if their text changes.</p>'
    : '<p class="note">No rules were bundled with this page.</p>';
}

function download(name, text, type) {
  var a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: type }));
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}

// ---------- modes and wiring ----------
function setMode(m) {
  resetDrill();
  S.mode = m;
  setTool(null);
  ["Inspect", "Coverage", "Drill"].forEach(function (n) { $("mode" + n).setAttribute("aria-pressed", String(n.toLowerCase() === m)); });
  clearOverlay();
  S.coverage = null;
  if (m === "coverage") runCoverage();
  else renderModePanel();
  $("drillBar").style.display = m === "drill" && S.drill ? "flex" : "none";
}

function openScene(text, name) {
  var data;
  try { data = JSON.parse(text); } catch (e) { toast(name + " is not JSON."); return; }
  try {
    loadResult(data);
  } catch (e) { toast(e.message, 6000); return; }
  S.meta = { fixture: null, source_file: name };
  buildScene();
  setMode(S.mode);
  renderAll();
  toast("Opened " + name + ".");
}

function wire() {
  $("storeySel").addEventListener("change", function (e) {
    S.storey = e.target.value;
    resetDrill();
    applyVisibility();
    fitView();
    if (S.view === "walk") setView("walk");
    renderSysList();
    if (S.mode === "coverage") runCoverage(); else renderModePanel();
  });
  $("viewOrbit").addEventListener("click", function () { setView("orbit"); });
  $("viewPlan").addEventListener("click", function () { setView("plan"); });
  $("viewWalk").addEventListener("click", function () { setView("walk"); });
  $("modeInspect").addEventListener("click", function () { setMode("inspect"); });
  $("modeCoverage").addEventListener("click", function () { setMode("coverage"); });
  $("modeDrill").addEventListener("click", function () { setMode("drill"); });
  $("optWalls").addEventListener("change", applyVisibility);
  $("wallMode").addEventListener("change", applyBuildingOptions);
  $("layerList").querySelectorAll("input").forEach(function (el) { el.addEventListener("change", applyBuildingOptions); });
  // Presets: everything back on, or just walls, openings and floors from above.
  var preset = function (shown, walls) {
    $("layerList").querySelectorAll("input").forEach(function (el) { el.checked = shown.indexOf(el.id.slice(5)) >= 0; });
    $("wallMode").value = walls;
    applyBuildingOptions();
  };
  $("showAll").addEventListener("click", function () {
    preset(["doors", "windows", "floors", "slabs", "roof", "stairs", "furniture", "ground", "devices"], "solid");
  });
  $("showPlan").addEventListener("click", function () {
    preset(["doors", "windows", "floors", "stairs", "devices"], "solid");
    setView("plan");
  });
  $("optExplode").addEventListener("input", function (e) { BLD.explode = Number(e.target.value); applyBuildingOptions(); });
  $("optCut").addEventListener("input", function (e) {
    var v = Number(e.target.value);
    BLD.cut = v >= Number(e.target.max) ? null : v;
    applyBuildingOptions();
  });
  $("exportGlb").addEventListener("click", exportGlb);
  $("optLabels").addEventListener("change", updateLabels);
  $("optBig").addEventListener("change", function () {
    S.devices.forEach(styleDevice);
    if (S.selected) select(S.selected);
  });
  $("themeBtn").addEventListener("click", function () {
    var dark = document.documentElement.getAttribute("data-theme") === "dark"
      || (!document.documentElement.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
    if (!S.result) return;
    var keep = S.selected;
    resetDrill();
    buildScene();
    setMode(S.mode);
    if (keep) select(keep);
  });
  $("openScene").addEventListener("click", function () { $("sceneFile").click(); });
  $("sceneFile").addEventListener("change", function (e) {
    var f = e.target.files[0];
    if (!f) return;
    f.text().then(function (t) { openScene(t, f.name); });
    e.target.value = "";
  });
  var stage = $("stage"), depth = 0;
  stage.addEventListener("dragenter", function (e) { e.preventDefault(); depth++; $("dropHint").style.display = "flex"; });
  stage.addEventListener("dragover", function (e) { e.preventDefault(); });
  stage.addEventListener("dragleave", function () { if (--depth <= 0) { depth = 0; $("dropHint").style.display = "none"; } });
  stage.addEventListener("drop", function (e) {
    e.preventDefault();
    depth = 0;
    $("dropHint").style.display = "none";
    var f = e.dataTransfer.files[0];
    if (f) f.text().then(function (t) { openScene(t, f.name); });
  });
  $("drillPlay").addEventListener("click", function () {
    var d = S.drill;
    if (!d) return;
    if (d.t >= d.end) {
      d.t = 0; d.shown = 0;
      d.events.forEach(function (ev) { if (ev.id) glow(ev.id, 0); });
      (d.sounders || []).forEach(function (s) { glow(s.id, 0); });
      d.playing = true;
      renderDrillLog();
    } else d.playing = !d.playing;
    $("drillPlay").textContent = d.playing ? "Pause" : "Play";
  });
  $("drillReset").addEventListener("click", function () { resetDrill(); renderModePanel(); });
}

function init() {
  initThree();
  wire();
  var data = window.__SCENE__;
  if (!data) { $("empty").style.display = "flex"; return; }
  try {
    loadResult(data);
  } catch (e) {
    $("empty").style.display = "flex";
    toast(e.message, 8000);
    return;
  }
  buildScene();
  renderAll();
  // Automation handle, only on request: page tests need screen positions.
  if (/(^|[#&])test\b/.test(location.hash.slice(1))) {
    window.__sim = {
      S: S,
      toScreen: function (x, y, z) {
        var v = toWorld(x, y, z).project(cam), r = $("canvas").getBoundingClientRect();
        return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };
      }
    };
  }
}

init();
