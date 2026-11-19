// ---------- fire drill ----------
// A sequence, not a fire model. Smoke spreads across the ceiling of the room
// of origin at a speed the person enters; a detector in that room goes into
// alarm once the smoke reaches it and its response time has passed; the panel
// raises the alarm after its delay and starts the sounders in the scope the
// person chose. The point is the order of events and the gaps it exposes — a
// room with no detector, a floor with no sounder — not the seconds.

function drillReady(manual) {
  var keys = manual ? ["panel_delay"] : ["speed", "det_delay", "panel_delay"];
  var miss = keys.filter(function (k) { return SET.drill[k].v == null; });
  if (miss.length) {
    toast("Enter " + miss.map(function (k) { return FIELD_LABELS[k].toLowerCase(); }).join(", ") + " first, or use the illustrative values.", 4500);
    return false;
  }
  return true;
}

function resetDrill(keep) {
  if (S.drill) {
    if (S.drill.smokeMesh) { S.drill.smokeMesh.parent.remove(S.drill.smokeMesh); disposeTree(S.drill.smokeMesh); }
    if (S.drill.originMark) { S.drill.originMark.parent.remove(S.drill.originMark); disposeTree(S.drill.originMark); }
    S.drill.lit.forEach(function (id) { glow(id, 0); });
  }
  if (!keep) S.drill = null;
  $("drillBar").style.display = S.mode === "drill" && S.drill ? "flex" : "none";
  $("drillClock").textContent = "0:00";
  $("drillPlay").textContent = "Play";
}

function notifiersInScope(storey) {
  var all = activeDevices(NOTIFIERS);
  return setting("drill", "scope") === "building" ? all : all.filter(function (d) { return d.storey === storey; });
}

function scopeRooms(storey) {
  return setting("drill", "scope") === "building" ? S.rooms : S.rooms.filter(function (r) { return r.storey === storey; });
}

function finishEvents(drill, storey, alarmT) {
  var sounders = notifiersInScope(storey);
  drill.sounders = sounders;
  if (alarmT == null) return;
  drill.events.push({ t: alarmT, kind: "alarm",
    text: "Panel in alarm — " + sounders.length + " sounder" + (sounders.length === 1 ? "" : "s") + " started ("
      + (setting("drill", "scope") === "building" ? "whole building" : storey) + ")" });
  if (!sounders.length) {
    drill.events.push({ t: alarmT, kind: "gap", text: "No sounder or strobe in scope — nobody is warned." });
  }
  var withSounder = {};
  sounders.forEach(function (d) { var r = roomOf(d); if (r) withSounder[r.id] = true; });
  var silent = scopeRooms(storey).filter(function (r) { return !withSounder[r.id]; });
  drill.silentRooms = silent;
  if (silent.length && sounders.length) {
    drill.events.push({ t: alarmT, kind: "note",
      text: silent.length + " room" + (silent.length === 1 ? "" : "s") + " in scope have no sounder of their own; whether they hear one is the Sounders coverage check." });
  }
}

function startDrillAt(room, point) {
  if (!drillReady(false)) return;
  resetDrill();
  setTool(null);
  var speed = setting("drill", "speed"), detDelay = setting("drill", "det_delay"), panel = setting("drill", "panel_delay");
  var drill = { room: room, point: point, t: 0, playing: true, events: [], shown: 0, lit: [], detections: [],
    illustrative: anyIllustrative("drill"), manual: null };
  drill.events.push({ t: 0, kind: "start", text: "Fire starts in " + room.label });

  var dets = activeDevices(DETECTORS).filter(function (d) { return roomOf(d) === room; });
  dets.forEach(function (d) {
    var dist = Math.hypot(d.x_m - point[0], d.y_m - point[1]);
    drill.detections.push({ d: d, t: dist / speed + detDelay, dist: dist });
  });
  drill.detections.sort(function (a, b) { return a.t - b.t; });
  drill.detections.forEach(function (x) {
    drill.events.push({ t: x.t, kind: "detect", id: x.d.id,
      text: (x.d.name || words(x.d.device_type)) + " in alarm — smoke travelled " + fmt(x.dist, 1) + " m" });
  });
  var alarmT = drill.detections.length ? drill.detections[0].t + panel : null;
  if (alarmT == null) {
    drill.events.push({ t: 0, kind: "gap", text: "No working automatic detector in " + room.label
      + ". The fire is not detected unless someone operates a call point." });
  }
  finishEvents(drill, room.storey, alarmT);
  drill.events.sort(function (a, b) { return a.t - b.t; });

  // Smoke as sample points sorted by distance; drawing the first n of them is
  // drawing the smoke at radius r.
  var step = Math.max(0.25, gridStep(room) * 0.8), cells = cellsOf(room, step).map(function (c) {
    return [c[0], c[1], Math.hypot(c[0] - point[0], c[1] - point[1])];
  }).sort(function (a, b) { return a[2] - b[2]; });
  drill.cells = cells;
  drill.speed = speed;
  var mesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(css("--smoke")), transparent: true, opacity: 0.42, depthWrite: false, side: THREE.DoubleSide }),
    Math.max(cells.length, 1));
  var m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), sc = new THREE.Vector3(step * 0.95, step * 0.95, 1), pos = new THREE.Vector3();
  var ceiling = room.base + room.height - 0.08;
  cells.forEach(function (c, i) {
    var p = L(c[0], c[1], ceiling);
    mesh.setMatrixAt(i, m4.compose(pos.set(p[0], p[1], p[2]), q, sc));
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.count = 0;
  mesh.renderOrder = 3;
  storeyNode(room.storey).overlay.add(mesh);
  drill.smokeMesh = mesh;

  var mark = new THREE.Mesh(new THREE.ConeGeometry(0.25, 0.6, 16),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(css("--bad")) }));
  mark.rotation.x = Math.PI / 2;
  var mp = L(point[0], point[1], room.base + 0.3);
  mark.position.set(mp[0], mp[1], mp[2]);
  storeyNode(room.storey).overlay.add(mark);
  drill.originMark = mark;

  var last = drill.events.reduce(function (m, e) { return Math.max(m, e.t); }, 0);
  var fill = cells.length ? cells[cells.length - 1][2] / speed : 0;
  drill.end = Math.min(1800, Math.max(last, fill) + 20);
  S.drill = drill;
  $("drillBar").style.display = "flex";
  $("drillPlay").textContent = "Pause";
  renderModePanel();
}

function startDrillFromCallPoint(mcp) {
  if (!drillReady(true)) return;
  resetDrill();
  setTool(null);
  var drill = { room: roomOf(mcp), point: null, t: 0, playing: true, events: [], shown: 0, lit: [mcp.id], detections: [],
    illustrative: anyIllustrative("drill"), manual: mcp };
  drill.events.push({ t: 0, kind: "start", text: (mcp.name || "Call point") + " operated" + (drill.room ? " in " + drill.room.label : "") });
  finishEvents(drill, mcp.storey, setting("drill", "panel_delay"));
  drill.events.sort(function (a, b) { return a.t - b.t; });
  drill.end = drill.events[drill.events.length - 1].t + 20;
  S.drill = drill;
  glow(mcp.id, 1);
  $("drillBar").style.display = "flex";
  $("drillPlay").textContent = "Pause";
  renderModePanel();
}

function glow(id, level) {
  var g = G.deviceObjs[id];
  if (!g) return;
  g.children.forEach(function (m) {
    if (m.material && m.material.emissive) {
      m.material.emissive.set(css("--bad"));
      m.material.emissiveIntensity = level;
    }
  });
}

function drillTick(dt, now) {
  var d = S.drill;
  if (!d) return;
  if (d.playing) {
    d.t = Math.min(d.end, d.t + dt * Number($("drillSpeed").value || 1));
    if (d.t >= d.end) { d.playing = false; $("drillPlay").textContent = "Replay"; }
  }
  $("drillClock").textContent = clock(d.t);

  if (d.smokeMesh && d.cells.length) {
    var r = d.speed * d.t, lo = 0, hi = d.cells.length;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (d.cells[mid][2] <= r) lo = mid + 1; else hi = mid; }
    d.smokeMesh.count = lo;
  }
  var flash = 0.5 + 0.5 * Math.sin(now / 160);
  d.lit = [];
  d.events.forEach(function (e) {
    if (e.kind === "detect" && d.t >= e.t) { glow(e.id, 0.4 + 0.6 * flash); d.lit.push(e.id); }
  });
  if (d.manual) { glow(d.manual.id, 0.4 + 0.6 * flash); d.lit.push(d.manual.id); }
  var alarm = d.events.find(function (e) { return e.kind === "alarm"; });
  (d.sounders || []).forEach(function (s) {
    var on = alarm && d.t >= alarm.t;
    glow(s.id, on ? (Math.sin(now / 90) > 0 ? 1 : 0.1) : 0);
    if (on) d.lit.push(s.id);
  });

  var due = d.events.filter(function (e) { return e.t <= d.t; }).length;
  if (due !== d.shown) { d.shown = due; renderDrillLog(); }
}

function renderDrillLog() {
  var el = document.querySelector("#modePanel .log");
  if (!el || !S.drill) return;
  el.innerHTML = S.drill.events.slice(0, S.drill.shown).map(function (e) {
    var cls = e.kind === "gap" ? "bad-t" : e.kind === "alarm" ? "warn-t" : "";
    return '<div><span class="t">' + clock(e.t) + '</span><span class="' + cls + '">' + esc(e.text) + "</span></div>";
  }).join("") || '<div class="t">waiting…</div>';
  el.scrollTop = el.scrollHeight;
}
