// ---------- three.js scene ----------
// The model is IFC (Z up, metres). It is built inside `root`, which is turned
// so Z points up the screen as three.js expects, and every coordinate is taken
// relative to the model's centre: survey coordinates run to hundreds of
// kilometres, which a 32-bit float cannot hold to the millimetre.

var renderer, scene3, root, model, persp, ortho, cam;
var raycaster = new THREE.Raycaster();
var G = { storeys: {}, deviceObjs: {}, floorMeshes: [], pickables: [], labels: [] };
var O = { x: 0, y: 0, z: 0 };       // model origin subtracted from every coordinate
var C = {
  target: new THREE.Vector3(), theta: -0.9, phi: 0.95, dist: 40, planZoom: 20,
  walk: { pos: new THREE.Vector3(), yaw: 0, pitch: 0 }, keys: {}, ptrs: {}, drag: null, pinch: null
};

function L(x, y, z) { return [x - O.x, y - O.y, z - O.z]; }           // IFC -> model-local
function toWorld(x, y, z) { return new THREE.Vector3(x - O.x, z - O.z, -(y - O.y)); }
function fromWorld(v) { return [v.x + O.x, -v.z + O.y, v.y + O.z]; }   // world -> IFC

function initThree() {
  renderer = new THREE.WebGLRenderer({ canvas: $("canvas"), antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  scene3 = new THREE.Scene();
  persp = new THREE.PerspectiveCamera(50, 1, 0.05, 50000);
  ortho = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 100000);
  cam = persp;
  scene3.add(new THREE.HemisphereLight(0xffffff, 0x50585f, 1.0));
  var sun = new THREE.DirectionalLight(0xffffff, 0.5);
  sun.position.set(30, 80, 20);
  scene3.add(sun);
  root = new THREE.Group();
  root.rotation.x = -Math.PI / 2;
  scene3.add(root);
  window.addEventListener("resize", resize);
  if (window.ResizeObserver) new ResizeObserver(resize).observe($("stage"));
  resize();
  bindControls();
  requestAnimationFrame(frame);
}

function resize() {
  var st = $("stage"), w = st.clientWidth || 1, h = st.clientHeight || 1;
  renderer.setSize(w, h, false);
  persp.aspect = w / h;
  persp.updateProjectionMatrix();
}

function disposeTree(obj) {
  obj.traverse(function (o) {
    if (o.geometry) o.geometry.dispose();
    if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) { m.dispose(); });
  });
}

function storeyNode(name) {
  var key = name || "(no storey)";
  if (!G.storeys[key]) {
    var n = { group: new THREE.Group(), rooms: new THREE.Group(), context: new THREE.Group(),
      devices: new THREE.Group(), overlay: new THREE.Group() };
    n.group.add(n.rooms, n.context, n.devices, n.overlay);
    model.add(n.group);
    G.storeys[key] = n;
  }
  return G.storeys[key];
}

function shapeOf(poly) {
  var sh = new THREE.Shape();
  poly.forEach(function (p, i) {
    var x = p[0] - O.x, y = p[1] - O.y;
    if (i === 0) sh.moveTo(x, y); else sh.lineTo(x, y);
  });
  return sh;
}

// Many extrusions become one geometry per storey and kind: thousands of walls
// as separate meshes would be thousands of draw calls.
function mergedExtrusions(items) {
  var parts = [], total = 0;
  items.forEach(function (it) {
    if (!(it.height_m > 0)) return;
    var g = new THREE.ExtrudeGeometry(shapeOf(it.footprint_m), { depth: it.height_m, bevelEnabled: false });
    g.translate(0, 0, it.base_z_m - O.z);
    var flat = g.index ? g.toNonIndexed() : g;
    if (flat !== g) g.dispose();
    parts.push(flat);
    total += flat.attributes.position.count;
  });
  if (!parts.length) return null;
  var pos = new Float32Array(total * 3), nor = new Float32Array(total * 3), o = 0;
  parts.forEach(function (g) {
    pos.set(g.attributes.position.array, o * 3);
    nor.set(g.attributes.normal.array, o * 3);
    o += g.attributes.position.count;
    g.dispose();
  });
  var out = new THREE.BufferGeometry();
  out.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  out.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  return out;
}

function buildScene() {
  if (model) { root.remove(model); disposeTree(model); }
  model = new THREE.Group();
  root.add(model);
  G = { storeys: {}, deviceObjs: {}, floorMeshes: [], pickables: [], labels: [] };
  $("labels").innerHTML = "";
  scene3.background = new THREE.Color(css("--scene-bg"));

  var b = S.result.outputs.bounds_m;
  O = b ? { x: (b.min[0] + b.max[0]) / 2, y: (b.min[1] + b.max[1]) / 2, z: b.min[2] } : { x: 0, y: 0, z: 0 };
  S.storeys.forEach(function (st) { storeyNode(st.name); });

  // Rooms: a floor to click on and colour, and an outline.
  var floorCol = new THREE.Color(css("--scene-floor"));
  var lineCol = new THREE.Color(css("--scene-wall"));
  S.rooms.forEach(function (r) {
    var node = storeyNode(r.storey);
    var geo = new THREE.ShapeGeometry(shapeOf(r.poly));
    geo.translate(0, 0, r.base - O.z + 0.01);
    var mat = new THREE.MeshStandardMaterial({ color: floorCol, side: THREE.DoubleSide, roughness: 0.95,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    var mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { kind: "room", id: r.id };
    node.rooms.add(mesh);
    G.floorMeshes.push(mesh);
    r.mesh = mesh;
    var pts = r.poly.map(function (p) { return new THREE.Vector3(p[0] - O.x, p[1] - O.y, r.base - O.z + 0.02); });
    var line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: lineCol }));
    node.rooms.add(line);
    r.outline = line;

    var el = document.createElement("div");
    el.className = "rlabel";
    // <bdi>: an Arabic room name must not pull the number or percentage across.
    el.innerHTML = (r.number ? "<b>" + esc(r.number) + "</b>" : "") + "<bdi>" + esc(r.name || (r.number ? "" : r.label)) + "</bdi>"
      + '<span class="pct"></span>';
    $("labels").appendChild(el);
    G.labels.push({ el: el, room: r, pct: el.querySelector(".pct") });
  });

  // Context: walls, columns, slabs as merged extrusions.
  var byKey = {};
  (S.result.outputs.context || []).forEach(function (c) {
    var key = (c.storey || "(no storey)") + "|" + c.kind;
    (byKey[key] = byKey[key] || []).push(c);
  });
  var looks = {
    wall: { color: css("--scene-wall"), opacity: 0.38 },
    column: { color: css("--scene-wall"), opacity: 0.8 },
    slab: { color: css("--scene-slab"), opacity: 0.12 },
    covering: { color: css("--scene-slab"), opacity: 0.1 },
    railing: { color: css("--scene-wall"), opacity: 0.5 }
  };
  Object.keys(byKey).forEach(function (key) {
    var parts = key.split("|"), geo = mergedExtrusions(byKey[key]);
    if (!geo) return;
    var look = looks[parts[1]] || looks.wall;
    var mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: new THREE.Color(look.color),
      transparent: true, opacity: look.opacity, depthWrite: look.opacity > 0.5, roughness: 0.9 }));
    mesh.renderOrder = 1;
    storeyNode(parts[0]).context.add(mesh);
  });

  S.devices.forEach(addDeviceObject);
  var hasBuilding = buildBuilding();
  scene3.background = new THREE.Color(hasBuilding ? css("--sky") || css("--scene-bg") : css("--scene-bg"));
  $("bldSection").style.display = hasBuilding ? "block" : "none";

  // One marker shows the selection wherever it is.
  var mk = new THREE.Group();
  var ring = new THREE.Mesh(new THREE.RingGeometry(0.28, 0.36, 40),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(css("--accent")), side: THREE.DoubleSide, depthTest: false, transparent: true }));
  ring.renderOrder = 10;
  mk.add(ring);
  mk.visible = false;
  model.add(mk);
  G.marker = mk;

  applyVisibility();
  fitView();
}

// ---------- devices, modelled roughly as the products are ----------
function deviceParts(d) {
  var t = d.device_type, white = 0xf2f2ef, dark = 0x30363c;
  var sys = new THREE.Color(sysColor(d.system));
  var parts = [];
  function cyl(r, h, color, z) {
    var g = new THREE.CylinderGeometry(r, r, h, 24);
    g.rotateX(Math.PI / 2);
    g.translate(0, 0, z);
    parts.push([g, color]);
  }
  function box(x, y, z, color, at) {
    var g = new THREE.BoxGeometry(x, y, z);
    g.translate(at[0], at[1], at[2]);
    parts.push([g, color]);
  }
  if (t === "smoke_detector" || t === "multisensor_detector" || t === "heat_detector") {
    cyl(0.055, 0.045, white, -0.0225);
    cyl(0.03, 0.012, t === "heat_detector" ? 0xd9822b : sys, -0.05);
  } else if (t === "manual_call_point") {
    box(0.09, 0.06, 0.09, sys, [0, 0, 0]);
  } else if (NOTIFIERS.indexOf(t) >= 0 || t === "speaker") {
    cyl(0.06, 0.09, t === "speaker" ? white : sys, 0);
    if (t !== "sounder") cyl(0.035, 0.03, 0xfff4c2, 0.06);
  } else if (t === "camera" || t === "ptz_camera") {
    box(0.22, 0.09, 0.09, white, [0.11, 0, -0.06]);
    cyl(0.03, 0.03, dark, -0.06);
    var lens = new THREE.CylinderGeometry(0.035, 0.035, 0.03, 18);
    lens.rotateZ(Math.PI / 2);
    lens.translate(0.235, 0, -0.06);
    parts.push([lens, dark]);
  } else if (t === "card_reader") {
    box(0.05, 0.03, 0.12, sys, [0, 0, 0]);
  } else if (t === "wireless_access_point") {
    cyl(0.1, 0.035, white, -0.0175);
    cyl(0.012, 0.005, sys, -0.037);
  } else if (t === "data_outlet") {
    box(0.086, 0.02, 0.086, white, [0, 0, 0]);
    box(0.05, 0.022, 0.02, sys, [0, 0, 0]);
  } else {
    var s = new THREE.SphereGeometry(0.06, 16, 12);
    parts.push([s, sys]);
  }
  return parts;
}

function addDeviceObject(d) {
  var node = storeyNode(d.storey), g = new THREE.Group();
  deviceParts(d).forEach(function (p) {
    var mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(p[1]), roughness: 0.5, metalness: 0.05,
      transparent: true, opacity: 1 });
    var m = new THREE.Mesh(p[0], mat);
    m.userData = { kind: "device", id: d.id };
    g.add(m);
    G.pickables.push(m);
  });
  if (d.proposed) {
    var halo = new THREE.Mesh(new THREE.RingGeometry(0.12, 0.16, 32),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(css("--accent")), side: THREE.DoubleSide, transparent: true, opacity: 0.9 }));
    halo.position.z = -0.002;
    g.add(halo);
  }
  var p = L(d.x_m, d.y_m, d.z_m);
  g.position.set(p[0], p[1], p[2]);
  if (d.device_type === "camera" || d.device_type === "ptz_camera") g.rotation.z = aimOf(d) * Math.PI / 180;
  g.userData = { kind: "device", id: d.id };
  node.devices.add(g);
  G.deviceObjs[d.id] = g;
  styleDevice(d);
}

function removeDeviceObject(id) {
  var g = G.deviceObjs[id];
  if (!g) return;
  g.parent.remove(g);
  G.pickables = G.pickables.filter(function (m) { return m.parent !== g; });
  disposeTree(g);
  delete G.deviceObjs[id];
}

// Enlarged to be findable from above; true size when walking among them.
function deviceScale() { return S.view !== "walk" && $("optBig").checked ? 2.5 : 1; }

// Out of service: faded. In alarm: pulsing (see frame()).
function styleDevice(d) {
  var g = G.deviceObjs[d.id];
  if (!g) return;
  var s = deviceScale();
  g.scale.set(s, s, s);
  g.children.forEach(function (m) {
    if (!m.material || m.userData.kind !== "device") return;
    m.material.opacity = S.disabled[d.id] ? 0.25 : 1;
    m.material.depthWrite = !S.disabled[d.id];
  });
}

function applyVisibility() {
  Object.keys(G.storeys).forEach(function (name) {
    G.storeys[name].group.visible = S.storey === "__all__" || name === S.storey;
    G.storeys[name].context.visible = $("optWalls").checked;
  });
  S.devices.forEach(function (d) {
    var g = G.deviceObjs[d.id];
    if (g) g.visible = !S.hidden[d.system];
  });
  G.labels.forEach(function (l) { l.el.style.display = "none"; });
}

// ---------- framing ----------
function visibleBox() {
  var box = new THREE.Box3(), any = false;
  S.rooms.forEach(function (r) {
    if (!onStorey(r)) return;
    r.poly.forEach(function (p) { box.expandByPoint(toWorld(p[0], p[1], r.base)); box.expandByPoint(toWorld(p[0], p[1], r.base + r.height)); });
    any = true;
  });
  S.devices.forEach(function (d) {
    if (!onStorey(d)) return;
    box.expandByPoint(toWorld(d.x_m, d.y_m, d.z_m));
    any = true;
  });
  if (!any) {
    var b = S.result.outputs.bounds_m;
    if (!b) return null;
    box.expandByPoint(toWorld(b.min[0], b.min[1], b.min[2]));
    box.expandByPoint(toWorld(b.max[0], b.max[1], b.max[2]));
  }
  return box;
}

function fitView(box) {
  box = box || visibleBox();
  if (!box) return;
  var c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  var base = S.storey === "__all__" ? box.min.y : storeyBase(S.storey) - O.z;
  C.target.set(c.x, base, c.z);
  var radius = Math.max(size.x, size.z, 4) * 0.5;
  var aspect = persp.aspect || 1;
  // On a tall, narrow screen the width is what runs out first.
  C.dist = radius * 2.4 / Math.min(1, aspect);
  C.planZoom = Math.max(size.z / 2, size.x / 2 / aspect, 3) * 1.12;
}

function focusRoom(r) {
  var box = new THREE.Box3();
  r.poly.forEach(function (p) { box.expandByPoint(toWorld(p[0], p[1], r.base)); });
  var c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  C.target.set(c.x, r.base - O.z, c.z);
  C.dist = Math.max(size.x, size.z, 4) * 1.6;
  C.planZoom = Math.max(size.z, size.x / (persp.aspect || 1), 4) * 0.75;
}

function setView(v) {
  // Ceilings come on when you walk in and go off when you look from above;
  // the Ceilings box stays yours to change in either view.
  var ceil = $("show-ceilings");
  if (ceil && (v === "walk") !== (S.view === "walk")) ceil.checked = v === "walk";
  S.view = v;
  ["Orbit", "Plan", "Walk"].forEach(function (n) { $("view" + n).setAttribute("aria-pressed", String(n.toLowerCase() === v)); });
  $("walkHint").style.display = v === "walk" ? "block" : "none";
  S.devices.forEach(styleDevice);
  applyBuildingOptions();
  if (S.selected) select(S.selected);
  if (v === "walk") {
    var base = S.storey === "__all__" ? (S.storeys[0] ? S.storeys[0].base : 0) : storeyBase(S.storey);
    // Start in the largest room, looking along its length.
    var r = S.rooms.filter(function (x) { return S.storey === "__all__" ? x.storey === (S.storeys[0] || {}).name : x.storey === S.storey; })
      .sort(function (a, b) { return polyArea(b.poly) - polyArea(a.poly); })[0];
    // Stand near one end, looking down the room's length: a view of the room,
    // not of the wall a few metres in front of the middle.
    var at = C.target.clone();
    C.walk.yaw = 0;                      // yaw 0 looks north (IFC +Y)
    if (r) {
      var lx = r.bounds.x1 - r.bounds.x0, ly = r.bounds.y1 - r.bounds.y0;
      var eastWest = lx > ly, back = Math.max(0, (eastWest ? lx : ly) / 2 - 0.9);
      var sx = r.center[0] - (eastWest ? back : 0), sy = r.center[1] - (eastWest ? 0 : back);
      if (!pip(sx, sy, r.poly)) { sx = r.center[0]; sy = r.center[1]; }
      at = toWorld(sx, sy, base);
      C.walk.yaw = eastWest ? -Math.PI / 2 : 0;
    }
    C.walk.pos.set(at.x, base - O.z + 1.6, at.z);
    C.walk.pitch = 0;
    $("canvas").focus();
  }
}

function applyCamera() {
  var stage = $("stage"), aspect = (stage.clientWidth || 1) / (stage.clientHeight || 1);
  if (S.view === "plan") {
    cam = ortho;
    ortho.left = -C.planZoom * aspect; ortho.right = C.planZoom * aspect;
    ortho.top = C.planZoom; ortho.bottom = -C.planZoom;
    ortho.position.set(C.target.x, C.target.y + 1000, C.target.z);
    ortho.up.set(0, 0, -1);                 // north (IFC +Y) up the screen
    ortho.lookAt(C.target.x, C.target.y, C.target.z);
    ortho.updateProjectionMatrix();
  } else if (S.view === "walk") {
    cam = persp;
    var w = C.walk, dir = new THREE.Vector3(-Math.sin(w.yaw) * Math.cos(w.pitch), Math.sin(w.pitch), -Math.cos(w.yaw) * Math.cos(w.pitch));
    persp.position.copy(w.pos);
    persp.up.set(0, 1, 0);
    persp.lookAt(w.pos.clone().add(dir));
  } else {
    cam = persp;
    var sp = Math.sin(C.phi);
    persp.position.set(C.target.x + C.dist * sp * Math.cos(C.theta), C.target.y + C.dist * Math.cos(C.phi),
      C.target.z + C.dist * sp * Math.sin(C.theta));
    persp.up.set(0, 1, 0);
    persp.lookAt(C.target);
  }
}

function stepWalk(dt) {
  var k = C.keys, w = C.walk, speed = (k.Shift ? 4.5 : 1.6) * dt;
  var fx = -Math.sin(w.yaw), fz = -Math.cos(w.yaw), rx = Math.cos(w.yaw), rz = -Math.sin(w.yaw);
  var f = (k.w || k.ArrowUp ? 1 : 0) - (k.s || k.ArrowDown ? 1 : 0);
  var r = (k.d ? 1 : 0) - (k.a ? 1 : 0);
  var turn = (k.ArrowLeft ? 1 : 0) - (k.ArrowRight ? 1 : 0);
  w.yaw += turn * 1.6 * dt;
  w.pos.x += (fx * f + rx * r) * speed;
  w.pos.z += (fz * f + rz * r) * speed;
}

// ---------- pointer, wheel, keys ----------
function bindControls() {
  var cv = $("canvas");
  cv.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  cv.addEventListener("pointerdown", function (e) {
    cv.setPointerCapture(e.pointerId);
    C.ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
    var ids = Object.keys(C.ptrs);
    if (ids.length === 1) C.drag = { x: e.clientX, y: e.clientY, button: e.button, pan: e.button === 2 || e.shiftKey || e.ctrlKey, moved: 0 };
    if (ids.length === 2) {
      var a = C.ptrs[ids[0]], b = C.ptrs[ids[1]];
      C.pinch = Math.hypot(a.x - b.x, a.y - b.y);
      if (C.drag) C.drag.moved = 99;      // a pinch is never a click
    }
  });
  cv.addEventListener("pointermove", function (e) {
    if (!C.ptrs[e.pointerId]) return;
    C.ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
    var ids = Object.keys(C.ptrs);
    if (ids.length === 2 && C.pinch) {
      var a = C.ptrs[ids[0]], b = C.ptrs[ids[1]], d = Math.hypot(a.x - b.x, a.y - b.y);
      zoom(C.pinch / Math.max(d, 1));
      C.pinch = d;
      return;
    }
    if (!C.drag) return;
    var dx = e.clientX - C.drag.x, dy = e.clientY - C.drag.y;
    C.drag.x = e.clientX; C.drag.y = e.clientY;
    C.drag.moved += Math.abs(dx) + Math.abs(dy);
    if (C.drag.moved < 4) return;
    var h = $("stage").clientHeight || 1;
    if (S.view === "walk") {
      C.walk.yaw -= dx * 0.004;
      C.walk.pitch = Math.max(-1.3, Math.min(1.3, C.walk.pitch - dy * 0.004));
    } else if (S.view === "plan") {
      var wpp = 2 * C.planZoom / h;
      C.target.x -= dx * wpp;
      C.target.z -= dy * wpp;
    } else if (C.drag.pan) {
      var scale = C.dist * 2 * Math.tan(persp.fov * Math.PI / 360) / h;
      var right = new THREE.Vector3().setFromMatrixColumn(persp.matrix, 0);
      var fwd = new THREE.Vector3(-Math.cos(C.theta), 0, -Math.sin(C.theta));
      C.target.addScaledVector(right, -dx * scale).addScaledVector(fwd, dy * scale);
    } else {
      C.theta += dx * 0.006;
      C.phi = Math.max(0.05, Math.min(1.5, C.phi - dy * 0.006));
    }
  });
  function end(e) {
    var wasClick = C.drag && C.drag.moved < 4 && Object.keys(C.ptrs).length === 1;
    delete C.ptrs[e.pointerId];
    if (Object.keys(C.ptrs).length < 2) C.pinch = null;
    if (wasClick && e.type === "pointerup") onPick(e);
    if (!Object.keys(C.ptrs).length) C.drag = null;
  }
  cv.addEventListener("pointerup", end);
  cv.addEventListener("pointercancel", end);
  cv.addEventListener("wheel", function (e) {
    e.preventDefault();
    if (S.view === "walk") {
      C.walk.pos.x += -Math.sin(C.walk.yaw) * -e.deltaY * 0.01;
      C.walk.pos.z += -Math.cos(C.walk.yaw) * -e.deltaY * 0.01;
    } else zoom(Math.exp(e.deltaY * 0.0012));
  }, { passive: false });
  window.addEventListener("keydown", function (e) {
    if (/INPUT|SELECT|TEXTAREA/.test((e.target || {}).tagName)) return;
    var k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (S.view === "walk" && ["w", "a", "s", "d", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].indexOf(k) >= 0) e.preventDefault();
    C.keys[k] = true;
    C.keys.Shift = e.shiftKey;
    if (k === "Escape") {
      if (S.tool) setTool(null);
      else if (S.view === "walk") setView("orbit");
      else select(null);
    }
  });
  window.addEventListener("keyup", function (e) {
    var k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    C.keys[k] = false;
    C.keys.Shift = e.shiftKey;
  });
  window.addEventListener("blur", function () { C.keys = {}; });
}

function zoom(f) {
  if (S.view === "plan") C.planZoom = Math.max(0.5, Math.min(5000, C.planZoom * f));
  else C.dist = Math.max(0.8, Math.min(20000, C.dist * f));
}

function ndcOf(e) {
  var r = $("canvas").getBoundingClientRect();
  return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
}

// The first visible room floor under the pointer, and the IFC point there.
function floorHit(e) {
  raycaster.setFromCamera(ndcOf(e), cam);
  var hits = raycaster.intersectObjects(G.floorMeshes.filter(function (m) { return m.parent.parent.visible; }), false);
  if (!hits.length) return null;
  return { room: roomById(hits[0].object.userData.id), point: fromWorld(hits[0].point) };
}

function deviceHit(e) {
  raycaster.setFromCamera(ndcOf(e), cam);
  var cands = G.pickables.filter(function (m) {
    var g = m.parent;
    return g.visible && g.parent && g.parent.parent && g.parent.parent.visible;
  });
  var hits = raycaster.intersectObjects(cands, false);
  return hits.length ? deviceById(hits[0].object.userData.id) : null;
}

function onPick(e) {
  if (S.tool === "place" || S.tool === "ignite") {
    var fh = floorHit(e);
    if (!fh) { toast("Click inside a room."); return; }
    if (S.tool === "place") placeProposal(fh.room, fh.point);
    else startDrillAt(fh.room, fh.point);
    return;
  }
  var d = deviceHit(e);
  if (!d && BLD.openingMeshes.length) {
    raycaster.setFromCamera(ndcOf(e), cam);
    var oh = raycaster.intersectObjects(BLD.openingMeshes.filter(function (m) { return m.visible; }), false);
    var fl = raycaster.intersectObjects(G.floorMeshes, false);
    if (oh.length && (!fl.length || oh[0].distance < fl[0].distance)) {
      select({ kind: "opening", ref: oh[0].object.userData.op, level: oh[0].object.userData.level });
      return;
    }
  }
  if (d) {
    if (S.mode === "drill" && d.device_type === "manual_call_point") { startDrillFromCallPoint(d); return; }
    select({ kind: "device", ref: d });
    return;
  }
  var h = floorHit(e);
  select(h ? { kind: "room", ref: h.room } : null);
}

function select(sel) {
  S.selected = sel;
  var mk = G.marker;
  if (mk) {
    if (sel && sel.kind === "device") {
      var d = sel.ref, p = L(d.x_m, d.y_m, d.z_m);
      mk.position.set(p[0], p[1], p[2] - 0.08);
      mk.scale.setScalar(deviceScale() * 0.9);
      mk.visible = true;
    } else if (sel && sel.kind === "room") {
      var r = sel.ref, b = r.bounds;
      var c = L(r.center[0], r.center[1], r.base + 0.03);
      mk.position.set(c[0], c[1], c[2]);
      mk.scale.setScalar(Math.max(0.6, Math.min(b.x1 - b.x0, b.y1 - b.y0) * 0.18));
      mk.visible = true;
    } else if (sel && sel.kind === "opening") {
      var lv = (S.result.outputs.building.levels || []).find(function (l) { return l.name === sel.level; });
      var oc = L(sel.ref.center[0], sel.ref.center[1], (lv ? lv.elevation_m : 0) + 0.03);
      mk.position.set(oc[0], oc[1], oc[2]);
      mk.scale.setScalar(Math.max(0.8, sel.ref.width_m * 0.9));
      mk.visible = true;
    } else mk.visible = false;
  }
  S.rooms.forEach(function (r) {
    if (r.outline) r.outline.material.color.set(css(sel && sel.kind === "room" && sel.ref === r ? "--accent" : "--scene-wall"));
  });
  renderInspector();
}

// ---------- labels and the frame loop ----------
function explodeOffset(storey) {
  if (!BLD.explode) return 0;
  var l = BLD.levels.find(function (x) { return x.name === storey; });
  return l ? l.index * BLD.explode : 0;
}

function updateLabels() {
  if (!$("optLabels").checked || S.view === "walk") {
    G.labels.forEach(function (l) { l.el.style.display = "none"; });
    return;
  }
  var w = $("stage").clientWidth, h = $("stage").clientHeight, v = new THREE.Vector3(), shown = 0;
  // Looking at a whole building, only the floor you can actually see is labelled:
  // none under a roof, the highest one under a section cut, all when separated.
  var only = null, hideAll = false;
  if (S.storey === "__all__" && BLD.levels.length && !BLD.explode) {
    var below = BLD.levels.filter(function (l) {
      var lv = S.result.outputs.building.levels[l.index];
      return BLD.cut == null || lv.elevation_m < BLD.cut;
    });
    if (BLD.cut == null && BLD.roof && BLD.roof.visible) hideAll = true;
    else if (below.length) only = below[below.length - 1].name;
  }
  G.labels.forEach(function (l) {
    var r = l.room;
    if (!onStorey(r) || shown > 400 || hideAll || (only && r.storey !== only)) { l.el.style.display = "none"; return; }
    v.copy(toWorld(r.center[0], r.center[1], r.base + 0.05 + explodeOffset(r.storey))).project(cam);
    if (v.z > 1 || Math.abs(v.x) > 1.05 || Math.abs(v.y) > 1.05) { l.el.style.display = "none"; return; }
    l.el.style.display = "block";
    l.el.style.left = ((v.x + 1) / 2 * w) + "px";
    l.el.style.top = ((1 - v.y) / 2 * h) + "px";
    shown++;
  });
}

var lastT = performance.now();
function frame(t) {
  requestAnimationFrame(frame);
  var dt = Math.min(0.1, (t - lastT) / 1000);
  lastT = t;
  if (!S.result) return;
  if (S.view === "walk") stepWalk(dt);
  drillTick(dt, t);
  applyCamera();
  renderer.render(scene3, cam);
  updateLabels();
}
