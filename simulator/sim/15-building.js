// ---------- the building itself: walls, openings, slabs, roof, fit-out ----------
// Drawn from result.outputs.building when the scene is a prototype made from
// floor plans. Every height here comes from building.heights, which the engine
// records as an assumption unless someone supplied it; the fit-out is
// indicative and says so.

var BLD = { levels: [], openingMeshes: [], ceilings: [], fitout: [], roof: null, explode: 0, cut: null,
  layers: {} };

// Every part belongs to one layer the panel can switch off. Lintels and sill
// walls belong to the walls, so hiding walls hides them too; glass and frames
// belong to the windows, frames and leaves to the doors.
var LAYERS = ["walls", "doors", "windows", "floors", "slabs", "roof", "stairs", "furniture", "ceilings", "ground", "devices"];
function layer(name, obj) {
  (BLD.layers[name] = BLD.layers[name] || []).push(obj);
  return obj;
}

// Finishes by room type: indicative, chosen so rooms read as what they are.
var FLOOR_FINISH = {
  toilet: 0xd6dde0, kitchen: 0xd8d2c4, corridor: 0xcfc9bd, reception: 0xd9d1c1, lobby: 0xd9d1c1,
  office: 0x8fa6b8, open_office: 0x8fa6b8, meeting: 0x7f97ab, classroom: 0x9fb2a0,
  living: 0xb48a62, bedroom: 0xb08a66, dining: 0xb48a62, prayer: 0x6f8f7a,
  store: 0xbfc4c7, plant: 0xb0b6ba, server: 0xa9b0b5, stair: 0xc9c3b6, lift: 0xc9c3b6, room: 0xcfc9bd
};
var LOOK = {
  inside: 0xf1eee8, facade: 0xd9d2c3, wallTop: 0x6b6f73, slab: 0xb9b3a7, roof: 0x9a9890,
  glass: 0x9ec7de, frame: 0x3d4247, door: 0xa47a4f, ground: 0xc8cbb8, ceiling: 0xf6f5f1
};

function lambert(c, o) {
  o = o || {};
  return new THREE.MeshStandardMaterial({ color: c, roughness: o.r == null ? 0.85 : o.r, metalness: o.m || 0,
    transparent: !!o.t, opacity: o.t || 1, side: o.side || THREE.FrontSide, vertexColors: !!o.vc,
    depthWrite: o.t ? false : true });
}

function shapeWithHoles(poly) {
  var sh = shapeOf(poly.outer);
  (poly.holes || []).forEach(function (h) {
    var p = new THREE.Path();
    h.forEach(function (pt, i) { var x = pt[0] - O.x, y = pt[1] - O.y; if (i === 0) p.moveTo(x, y); else p.lineTo(x, y); });
    sh.holes.push(p);
  });
  return sh;
}

function insideFootprint(x, y, footprint) {
  for (var i = 0; i < footprint.length; i++) {
    var f = footprint[i];
    if (pip(x, y, f.outer) && !(f.holes || []).some(function (h) { return pip(x, y, h); })) return true;
  }
  return false;
}

// Wall faces that look outdoors get the facade colour; the rest are plastered.
function colourWalls(geo, footprint) {
  var pos = geo.attributes.position, n = pos.count, cols = new Float32Array(n * 3);
  var inside = new THREE.Color(LOOK.inside), outside = new THREE.Color(LOOK.facade), top = new THREE.Color(LOOK.wallTop);
  var a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), nrm = new THREE.Vector3();
  for (var i = 0; i < n; i += 3) {
    a.fromBufferAttribute(pos, i); b.fromBufferAttribute(pos, i + 1); c.fromBufferAttribute(pos, i + 2);
    nrm.subVectors(c, b).cross(new THREE.Vector3().subVectors(a, b)).normalize();
    var col;
    if (Math.abs(nrm.z) > 0.9) col = top;
    else {
      var mx = (a.x + b.x + c.x) / 3 + O.x, my = (a.y + b.y + c.y) / 3 + O.y;
      // ExtrudeGeometry winds sides so the normal can point either way; test both.
      var out1 = !insideFootprint(mx + nrm.x * 0.12, my + nrm.y * 0.12, footprint);
      var out2 = !insideFootprint(mx - nrm.x * 0.12, my - nrm.y * 0.12, footprint);
      col = (out1 || out2) && !(out1 && out2) ? outside : inside;
    }
    for (var k = 0; k < 3; k++) { cols[(i + k) * 3] = col.r; cols[(i + k) * 3 + 1] = col.g; cols[(i + k) * 3 + 2] = col.b; }
  }
  geo.setAttribute("color", new THREE.BufferAttribute(cols, 3));
}

function extrude(polys, z, height) {
  var parts = [];
  polys.forEach(function (p) {
    if (!p.outer || p.outer.length < 3) return;
    var g = new THREE.ExtrudeGeometry(shapeWithHoles(p), { depth: height, bevelEnabled: false });
    g.translate(0, 0, z - O.z);
    parts.push(g.index ? g.toNonIndexed() : g);
  });
  if (!parts.length) return null;
  var total = parts.reduce(function (s, g) { return s + g.attributes.position.count; }, 0);
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

function shadowed(m) { m.castShadow = true; m.receiveShadow = true; return m; }

// A box in an opening's own frame: x along the wall, y across it, z up.
function openingBox(op, base, w, t, z0, z1, mat, along) {
  if (z1 - z0 <= 0.005 || w <= 0.005) return null;
  var m = new THREE.Mesh(new THREE.BoxGeometry(w, t, z1 - z0), mat);
  var a = op.angle_deg * Math.PI / 180, c = L(op.center[0], op.center[1], base);
  var off = along || 0;
  m.position.set(c[0] + Math.cos(a) * off, c[1] + Math.sin(a) * off, c[2] + (z0 + z1) / 2);
  m.rotation.z = a;
  return shadowed(m);
}

function buildOpening(op, lv, node) {
  var base = lv.elevation_m, H = lv.wall_height_m, w = op.width_m, t = op.thickness_m + 0.01;
  var g = new THREE.Group(), part = op.kind === "window" ? "windows" : "doors";
  var add = function (m, as) { if (m) { g.add(m); layer(as || part, m); } };
  var wallMat = lambert(op.exterior ? LOOK.facade : LOOK.inside), frame = lambert(LOOK.frame, { r: 0.5, m: 0.3 });
  BLD.wallMats.push(wallMat);
  add(openingBox(op, base, w, t, op.head_m, H, wallMat), "walls");     // lintel
  if (op.kind === "window") {
    add(openingBox(op, base, w, t, 0, op.sill_m, wallMat), "walls");   // sill wall
    add(openingBox(op, base, w, 0.03, op.sill_m, op.head_m, lambert(LOOK.glass, { t: 0.35, r: 0.05, m: 0.1 })));
    add(openingBox(op, base, w, t * 0.6, op.sill_m - 0.05, op.sill_m, frame));
    add(openingBox(op, base, w, t * 0.6, op.head_m, op.head_m + 0.05, frame));
    add(openingBox(op, base, 0.05, t * 0.6, op.sill_m, op.head_m, frame, -w / 2 + 0.025));
    add(openingBox(op, base, 0.05, t * 0.6, op.sill_m, op.head_m, frame, w / 2 - 0.025));
    if (w > 1.3) add(openingBox(op, base, 0.04, t * 0.5, op.sill_m, op.head_m, frame, 0));
  } else if (op.kind === "door") {
    add(openingBox(op, base, 0.05, t, 0, op.head_m, frame, -w / 2 + 0.025));
    add(openingBox(op, base, 0.05, t, 0, op.head_m, frame, w / 2 - 0.025));
    if (op.leaf) {
      // Leaf hinged at one jamb, standing open. Which jamb and which way are
      // the drawing's swing; the angle is just open enough to read.
      var a = op.angle_deg * Math.PI / 180, side = op.swing_side ? -op.swing_side : 1;
      var leafW = w > 1.4 ? w / 2 : w - 0.08;
      var hinge = L(op.center[0] - Math.cos(a) * (w / 2 - 0.05), op.center[1] - Math.sin(a) * (w / 2 - 0.05), base);
      var pivot = new THREE.Group();
      pivot.position.set(hinge[0], hinge[1], hinge[2]);
      pivot.rotation.z = a + side * 1.15;
      var leaf = shadowed(new THREE.Mesh(new THREE.BoxGeometry(leafW, 0.045, op.head_m - 0.02), lambert(LOOK.door, { r: 0.6 })));
      leaf.position.set(leafW / 2, 0, (op.head_m - 0.02) / 2);
      pivot.add(leaf);
      g.add(pivot);
      layer("doors", pivot);
    }
  }
  g.traverse(function (m) { if (m.isMesh) { m.userData = { kind: "opening", op: op, level: lv.name }; BLD.openingMeshes.push(m); } });
  node.group.add(g);
}

function buildStair(room, lv, node) {
  // An indicative straight flight across the stair room, rising one storey.
  var b = room.bounds, lx = b.x1 - b.x0, ly = b.y1 - b.y0;
  var alongX = lx >= ly, run = Math.max(lx, ly) - 0.6, width = Math.min(Math.min(lx, ly) - 0.3, 1.4);
  if (run < 1.5 || width < 0.6) return;
  var rise = BLD.heights.storey_height_m, steps = Math.max(8, Math.min(22, Math.round(rise / 0.17)));
  var going = Math.min(0.3, run / steps), mat = lambert(0xb7b1a5), g = new THREE.Group();
  for (var i = 0; i < steps; i++) {
    var h = rise * (i + 1) / steps;
    var m = shadowed(new THREE.Mesh(new THREE.BoxGeometry(alongX ? going : width, alongX ? width : going, h), mat));
    var s = (alongX ? b.x0 : b.y0) + 0.3 + going * (i + 0.5);
    var cx = alongX ? s : (b.x0 + b.x1) / 2, cy = alongX ? (b.y0 + b.y1) / 2 : s;
    var p = L(cx, cy, lv.elevation_m + h / 2);
    m.position.set(p[0], p[1], p[2]);
    g.add(m);
  }
  node.group.add(g);
  layer("stairs", g);
}

// ---------- indicative fit-out ----------
function boxAt(g, x, y, z, w, d, h, color, rot) {
  var m = shadowed(new THREE.Mesh(new THREE.BoxGeometry(w, d, h), lambert(color, { r: 0.7 })));
  var p = L(x, y, z + h / 2);
  m.position.set(p[0], p[1], p[2]);
  if (rot) m.rotation.z = rot;
  g.add(m);
  return m;
}
function fits(room, x, y, w, d) {
  return [[-1, -1], [1, -1], [1, 1], [-1, 1]].every(function (s) { return pip(x + s[0] * w / 2, y + s[1] * d / 2, room.poly); });
}
function deskSet(g, room, x, y, z) {
  boxAt(g, x, y, z + 0.72, 1.4, 0.7, 0.04, 0xc8a77d);
  [[-0.65, -0.3], [0.65, -0.3], [-0.65, 0.3], [0.65, 0.3]].forEach(function (o) { boxAt(g, x + o[0], y + o[1], z, 0.04, 0.04, 0.72, 0x7c8186); });
  boxAt(g, x, y - 0.65, z + 0.42, 0.48, 0.48, 0.06, 0x2f3a45);
  boxAt(g, x, y - 0.87, z + 0.45, 0.48, 0.06, 0.5, 0x2f3a45);
  boxAt(g, x, y + 0.2, z + 0.76, 0.55, 0.03, 0.35, 0x222629);              // a screen
}
function furnish(room, lv, node) {
  var t = room.type || "room", b = room.bounds, z = lv.elevation_m, g = new THREE.Group();
  var cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2, lx = b.x1 - b.x0, ly = b.y1 - b.y0;
  var m = 0.9;
  if (t === "office" || t === "open_office" || t === "classroom" || t === "room" && lx * ly > 12) {
    for (var x = b.x0 + m + 0.7; x <= b.x1 - m - 0.7; x += 2.4) {
      for (var y = b.y0 + m + 0.9; y <= b.y1 - m - 0.5; y += 2.2) {
        if (fits(room, x, y - 0.3, 1.6, 1.8)) deskSet(g, room, x, y, z);
      }
    }
  } else if (t === "meeting" || t === "dining") {
    var tw = Math.max(1.2, Math.min(lx - 2.2, 6)), td = Math.max(0.9, Math.min(ly - 2.4, 1.4));
    if (lx < ly) { var s = tw; tw = Math.max(0.9, Math.min(lx - 2.4, 1.4)); td = Math.max(1.2, Math.min(ly - 2.2, 6)); }
    if (fits(room, cx, cy, tw, td)) {
      boxAt(g, cx, cy, z + 0.72, tw, td, 0.05, 0x6e4f36);
      boxAt(g, cx, cy, z, Math.min(tw, td) * 0.3, Math.min(tw, td) * 0.3, 0.72, 0x3a3f44);
      var n = Math.max(1, Math.floor(Math.max(tw, td) / 0.8));
      for (var i = 0; i < n; i++) {
        var u = -Math.max(tw, td) / 2 + 0.4 + i * (Math.max(tw, td) - 0.8) / Math.max(1, n - 1);
        [-1, 1].forEach(function (sd) {
          var px = tw >= td ? cx + u : cx + sd * (tw / 2 + 0.35), py = tw >= td ? cy + sd * (td / 2 + 0.35) : cy + u;
          boxAt(g, px, py, z + 0.42, 0.46, 0.46, 0.06, 0x2f3a45);
        });
      }
    }
  } else if (t === "toilet") {
    var alongX = lx >= ly, n2 = Math.floor((Math.max(lx, ly) - 0.4) / 1.0);
    for (var k = 0; k < n2; k++) {
      var p = (alongX ? b.x0 : b.y0) + 0.7 + k * 1.0;
      var wx = alongX ? p : b.x0 + 0.35, wy = alongX ? b.y1 - 0.35 : p;
      if (fits(room, wx, wy, 0.4, 0.4)) {
        boxAt(g, wx, wy, z, 0.38, 0.5, 0.42, 0xf4f4f2);
        boxAt(g, alongX ? wx : wx - 0.1, alongX ? wy + 0.1 : wy, z + 0.42, alongX ? 0.38 : 0.2, alongX ? 0.2 : 0.38, 0.4, 0xf4f4f2);
      }
    }
    var bx = alongX ? cx : b.x1 - 0.3, by = alongX ? b.y0 + 0.3 : cy;
    if (fits(room, bx, by, 0.5, 0.5)) boxAt(g, bx, by, z + 0.8, alongX ? Math.min(lx - 1, 2.4) : 0.5, alongX ? 0.5 : Math.min(ly - 1, 2.4), 0.1, 0xe9ecee);
  } else if (t === "kitchen") {
    var along = lx >= ly;
    var len = Math.max(lx, ly) - 0.4;
    boxAt(g, along ? cx : b.x0 + 0.33, along ? b.y1 - 0.33 : cy, z, along ? len : 0.62, along ? 0.62 : len, 0.9, 0xe4ddd0);
    if (fits(room, cx, cy, 1.0, 0.8)) boxAt(g, cx, cy, z + 0.72, 1.0, 0.8, 0.05, 0xc8a77d);
  } else if (t === "reception" || t === "lobby") {
    if (fits(room, cx, cy, 2.4, 0.7)) boxAt(g, cx, cy + Math.min(ly / 4, 1.5), z, 2.4, 0.7, 1.05, 0x7a5c43);
    if (fits(room, cx, cy - 1.2, 2.0, 0.85)) boxAt(g, cx, cy - Math.min(ly / 4, 1.5), z, 2.0, 0.85, 0.45, 0x51606b);
  } else if (t === "store" || t === "plant") {
    var al = lx >= ly, l2 = Math.max(lx, ly) - 0.6;
    [-1, 1].forEach(function (sd) {
      var sx = al ? cx : cx + sd * (lx / 2 - 0.3), sy = al ? cy + sd * (ly / 2 - 0.3) : cy;
      if (Math.min(lx, ly) > 1.4) boxAt(g, sx, sy, z, al ? l2 : 0.4, al ? 0.4 : l2, t === "plant" ? 1.6 : 2.0, t === "plant" ? 0x8c949a : 0x9aa1a6);
    });
  } else if (t === "server") {
    for (var rx = b.x0 + 0.9; rx <= b.x1 - 0.6; rx += 0.7) if (fits(room, rx, cy, 0.6, 1.0)) boxAt(g, rx, cy, z, 0.6, 1.0, 2.0, 0x23272b);
  } else if (t === "living") {
    if (fits(room, cx, cy - 1, 2.2, 0.9)) boxAt(g, cx, cy - Math.min(1.2, ly / 4), z, 2.2, 0.9, 0.45, 0x5d6b78);
    if (fits(room, cx, cy, 1.1, 0.6)) boxAt(g, cx, cy + 0.2, z, 1.1, 0.6, 0.4, 0x6e4f36);
  } else if (t === "bedroom") {
    if (fits(room, cx, cy, 1.6, 2.0)) { boxAt(g, cx, cy, z, 1.6, 2.0, 0.5, 0xe8e4dc); boxAt(g, cx, cy + 0.95, z, 1.6, 0.1, 1.0, 0x6e4f36); }
  }
  if (g.children.length) { node.group.add(g); BLD.fitout.push(g); layer("furniture", g); }
}

function buildBuilding() {
  BLD.levels = []; BLD.openingMeshes = []; BLD.ceilings = []; BLD.fitout = [];
  BLD.layers = {}; BLD.wallMats = [];
  var b = S.result.outputs.building;
  if (!b) return false;
  BLD.heights = b.heights;
  var slabMat = lambert(LOOK.slab);
  b.levels.forEach(function (lv, i) {
    var node = storeyNode(lv.name);
    // Slab under the floor; the ground floor sits on a plinth instead.
    var slab = extrude(lv.footprint, lv.elevation_m - lv.slab_thickness_m, lv.slab_thickness_m);
    if (slab) node.group.add(layer("slabs", shadowed(new THREE.Mesh(slab, slabMat))));
    var wg = extrude(lv.walls, lv.elevation_m, lv.wall_height_m);
    if (wg) {
      colourWalls(wg, lv.footprint);
      var wm = shadowed(new THREE.Mesh(wg, lambert(0xffffff, { vc: true })));
      BLD.wallMats.push(wm.material);
      node.group.add(layer("walls", wm));
    }
    if (lv.facade === "glass") {
      lv.footprint.forEach(function (f) {
        f.outer.forEach(function (p, k) {
          var q = f.outer[(k + 1) % f.outer.length], len = Math.hypot(q[0] - p[0], q[1] - p[1]);
          if (len < 0.3) return;
          buildOpening({ kind: "window", exterior: true, center: [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2],
            angle_deg: Math.atan2(q[1] - p[1], q[0] - p[0]) * 180 / Math.PI, width_m: len, thickness_m: 0.08,
            sill_m: 0.0, head_m: lv.wall_height_m - 0.05, evidence: "a thin outer outline, shown as a curtain wall" }, lv, node);
        });
      });
    }
    lv.openings.forEach(function (op) { buildOpening(op, lv, node); });
    S.rooms.filter(function (r) { return r.storey === lv.name; }).forEach(function (r) {
      var sp = (S.result.outputs.spaces || []).find(function (s) { return s.id === r.id; }) || {};
      r.type = sp.type || "room";
      if (r.mesh) r.mesh.material.color.set(FLOOR_FINISH[r.type] || FLOOR_FINISH.room);
      if (r.mesh) layer("floors", r.mesh);
      if (r.outline) layer("floors", r.outline);
      var ceil = new THREE.Mesh(new THREE.ShapeGeometry(shapeOf(r.poly)), lambert(LOOK.ceiling, { side: THREE.DoubleSide }));
      ceil.position.z = r.base + r.height - O.z;
      ceil.visible = false;
      node.group.add(ceil);
      BLD.ceilings.push(ceil);
      layer("ceilings", ceil);
      if (r.type === "stair") buildStair(r, lv, node);
      else furnish(r, lv, node);
    });
    BLD.levels.push({ name: lv.name, node: node, index: i });
  });
  // Roof and parapet over the top level.
  var roof = b.roof, rg = extrude(roof.footprint, roof.z - roof.slab_thickness_m, roof.slab_thickness_m);
  var rnode = storeyNode(b.levels[b.levels.length - 1].name);
  BLD.roof = new THREE.Group();
  if (rg) BLD.roof.add(shadowed(new THREE.Mesh(rg, lambert(LOOK.roof))));
  if (roof.parapet_height_m > 0) {
    roof.footprint.forEach(function (f) {
      f.outer.forEach(function (p, k) {
        var q = f.outer[(k + 1) % f.outer.length], len = Math.hypot(q[0] - p[0], q[1] - p[1]);
        if (len < 0.05) return;
        var m = shadowed(new THREE.Mesh(new THREE.BoxGeometry(len + roof.parapet_thickness_m, roof.parapet_thickness_m, roof.parapet_height_m), lambert(LOOK.facade)));
        var c = L((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, roof.z + roof.parapet_height_m / 2);
        m.position.set(c[0], c[1], c[2]);
        m.rotation.z = Math.atan2(q[1] - p[1], q[0] - p[0]);
        BLD.roof.add(m);
      });
    });
  }
  rnode.group.add(BLD.roof);
  layer("roof", BLD.roof);

  // Site: a ground plane under the building, and the sun casting shadows.
  var bb = S.result.outputs.bounds_m, span = Math.max(bb.max[0] - bb.min[0], bb.max[1] - bb.min[1], 10);
  var ground = new THREE.Mesh(new THREE.PlaneGeometry(span * 4, span * 4), lambert(LOOK.ground));
  var gc = L((bb.min[0] + bb.max[0]) / 2, (bb.min[1] + bb.max[1]) / 2, -0.02);
  ground.position.set(gc[0], gc[1], Math.min(gc[2], -0.02 - O.z + bb.min[2]));
  ground.receiveShadow = true;
  model.add(ground);
  BLD.ground = ground;
  layer("ground", ground);
  enableShadows(span);
  applyBuildingOptions();
  return true;
}

function enableShadows(span) {
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  var sun = scene3.children.find(function (c) { return c.isDirectionalLight; });
  var sky = scene3.children.find(function (c) { return c.isHemisphereLight; });
  if (sky) sky.intensity = 1.2;
  if (!sun) return;
  sun.intensity = 0.75;
  sun.castShadow = true;
  sun.position.set(span * 0.8, span * 1.6, span * 0.6);
  sun.shadow.mapSize.set(2048, 2048);
  var s = sun.shadow.camera;
  s.left = s.bottom = -span; s.right = s.top = span; s.near = 0.5; s.far = span * 5;
  s.updateProjectionMatrix();
  sun.shadow.bias = -0.0005;
}

function applyBuildingOptions() {
  if (!BLD.levels.length) return;
  var on = function (name) { var el = $("show-" + name); return !el || el.checked; };
  LAYERS.forEach(function (name) {
    var show = on(name);
    if (name === "roof") show = show && S.view !== "walk"
      && (S.storey === "__all__" || S.storey === BLD.levels[BLD.levels.length - 1].name);
    if (name === "walls") show = $("wallMode").value !== "hidden";
    (BLD.layers[name] || []).forEach(function (o) { o.visible = show; });
  });
  // Devices: the layer switch, on top of the per-system switches in Show.
  var devOn = on("devices");
  S.devices.forEach(function (d) { var g = G.deviceObjs[d.id]; if (g) g.visible = devOn && !S.hidden[d.system]; });
  // See-through walls keep the plan readable while the rooms stay visible.
  var ghost = $("wallMode").value === "ghost";
  (BLD.wallMats || []).forEach(function (m) {
    m.transparent = ghost; m.opacity = ghost ? 0.22 : 1; m.depthWrite = !ghost; m.needsUpdate = true;
  });
  BLD.levels.forEach(function (l) { l.node.group.position.z = l.index * BLD.explode; });
  renderer.localClippingEnabled = false;
  renderer.clippingPlanes = BLD.cut == null ? [] : [new THREE.Plane(new THREE.Vector3(0, -1, 0), BLD.cut - O.z)];
}

function exportGlb() {
  function go() {
    var exporter = new THREE.GLTFExporter();
    exporter.parse(model, function (buf) {
      var name = ((S.result.outputs.model || {}).project || "building").replace(/[^\w-]+/g, "_");
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([buf], { type: "model/gltf-binary" }));
      a.download = name + ".glb";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      toast("Exported " + name + ".glb — opens in Blender, SketchUp, Windows 3D Viewer and most BIM viewers.", 6000);
    }, { binary: true, onlyVisible: true });
  }
  if (THREE.GLTFExporter) return go();
  var s = document.createElement("script");
  s.src = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/exporters/GLTFExporter.js";
  s.onload = go;
  s.onerror = function () { toast("Could not load the glTF exporter (offline?)."); };
  document.head.appendChild(s);
}
