// ---------- palette helpers ----------
var css=function(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim();};
var hex=function(n){return new THREE.Color(css(n));};
var C=function(h){return new THREE.Color(h);};
var mat=function(c,o){o=o||{};return new THREE.MeshStandardMaterial({color:c,
  roughness:o.r===undefined?0.8:o.r, metalness:o.m||0, transparent:!!o.t,
  opacity:o.t||1, emissive:o.e?C(o.e):C(0x000000)});};
var box=function(w,h,d,c,o){return new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat(c,o));};
var put=function(m,x,y,z,ry){m.position.set(x,y,z); if(ry)m.rotation.y=ry; return m;};

// Finishes. Indicative, chosen to read as a nursery interior, not specified.
var FIN={
  wall:0xf2efe9, wall_d:0x6e7781, floor_tile:0xd8d3c8, floor_vinyl:0xc9ccd1,
  floor_carpet:0x7e9bb5, floor_wc:0xcfd6da, timber:0xb08357, timber_d:0x8a6540,
  white:0xf5f5f2, grey:0x9aa3ab, dark:0x3a4249, steel:0xa8b0b6,
  kidA:0xe4573d, kidB:0x3f9e6b, kidC:0xe8a63a, kidD:0x4a7fc1
};
var FLOOR_BY_TYPE={office:FIN.floor_vinyl, classroom:FIN.floor_carpet,
  reception:FIN.floor_tile, corridor:FIN.floor_tile, lobby:FIN.floor_tile,
  toilet:FIN.floor_wc, wc:FIN.floor_wc, kitchenette:FIN.floor_tile,
  store:FIN.floor_vinyl, electrical:FIN.floor_vinyl, janitor:FIN.floor_wc};

// ---------- room furniture ----------
// Indicative fit-out so each room reads as what it is. NOT a furniture
// schedule, no quantities, nothing to procure from.
function deskSet(g,x,z,ry,c){
  g.add(put(box(1.5,0.05,0.75,FIN.timber),x,0.73,z,ry));
  [[-0.7,-0.33],[0.7,-0.33],[-0.7,0.33],[0.7,0.33]].forEach(function(p){
    var s=Math.sin(ry||0),co=Math.cos(ry||0);
    g.add(put(box(0.05,0.72,0.05,FIN.steel),x+p[0]*co-p[1]*s,0.36,z+p[0]*s+p[1]*co));
  });
  var ch=new THREE.Group();
  ch.add(put(box(0.46,0.06,0.46,c||FIN.dark),0,0.45,0));
  ch.add(put(box(0.46,0.5,0.06,c||FIN.dark),0,0.7,-0.2));
  ch.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.03,0.03,0.42,8),mat(FIN.steel,{m:0.6,r:0.4})),0,0.22,0));
  ch.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.26,0.26,0.03,12),mat(FIN.dark)),0,0.02,0));
  put(ch,x+Math.sin(ry||0)*0.75,0,z+Math.cos(ry||0)*0.75,(ry||0)+Math.PI);
  g.add(ch);
}
function kidTable(g,x,z,col){
  var t=new THREE.Group();
  t.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.55,0.55,0.04,20),mat(col)),0,0.52,0));
  t.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.05,0.05,0.5,10),mat(FIN.steel,{m:0.5,r:0.4})),0,0.25,0));
  t.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.3,0.3,0.03,14),mat(FIN.steel,{m:0.5,r:0.4})),0,0.02,0));
  for(var i=0;i<4;i++){
    var a=i*Math.PI/2+0.4, cx=Math.cos(a)*0.82, cz=Math.sin(a)*0.82;
    var ch=new THREE.Group();
    ch.add(put(box(0.3,0.04,0.3,col),0,0.32,0));
    ch.add(put(box(0.3,0.34,0.04,col),0,0.49,-0.13));
    [[-0.12,-0.12],[0.12,-0.12],[-0.12,0.12],[0.12,0.12]].forEach(function(p){
      ch.add(put(box(0.03,0.32,0.03,FIN.steel),p[0],0.16,p[1]));});
    t.add(put(ch,cx,0,cz,-a+Math.PI/2));
  }
  put(t,x,0,z); g.add(t);
}
function shelving(g,x0,z0,x1,z1){
  var len=Math.max(Math.abs(x1-x0),Math.abs(z1-z0)), horiz=Math.abs(x1-x0)>=Math.abs(z1-z0);
  for(var lv=0;lv<4;lv++){
    var s=horiz?box(len,0.04,0.45,FIN.steel,{m:0.4,r:0.6}):box(0.45,0.04,len,FIN.steel,{m:0.4,r:0.6});
    g.add(put(s,(x0+x1)/2,0.35+lv*0.45,(z0+z1)/2));
  }
}
function wcPan(g,x,z,ry){
  var p=new THREE.Group();
  p.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.19,0.16,0.4,16),mat(FIN.white,{r:0.25})),0,0.2,0));
  p.add(put(box(0.36,0.03,0.46,FIN.white,{r:0.2}),0,0.41,0.02));
  p.add(put(box(0.38,0.5,0.18,FIN.white,{r:0.25}),0,0.55,-0.26));
  put(p,x,0,z,ry||0); g.add(p);
}
function basin(g,x,z,ry){
  var b=new THREE.Group();
  b.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.21,0.17,0.16,16),mat(FIN.white,{r:0.2})),0,0.78,0));
  b.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.02,0.02,0.18,8),mat(FIN.steel,{m:0.8,r:0.25})),0,0.95,-0.14));
  put(b,x,0,z,ry||0); g.add(b);
}
function counterRun(g,x0,z0,x1,z1,withSink){
  var horiz=Math.abs(x1-x0)>=Math.abs(z1-z0), len=Math.max(Math.abs(x1-x0),Math.abs(z1-z0));
  var cx=(x0+x1)/2, cz=(z0+z1)/2;
  g.add(put(horiz?box(len,0.86,0.6,FIN.timber_d):box(0.6,0.86,len,FIN.timber_d),cx,0.43,cz));
  g.add(put(horiz?box(len,0.04,0.64,FIN.grey,{r:0.4}):box(0.64,0.04,len,FIN.grey,{r:0.4}),cx,0.88,cz));
  g.add(put(horiz?box(len,0.7,0.35,FIN.timber):box(0.35,0.7,len,FIN.timber),cx,1.75,cz));
  if(withSink) g.add(put(box(0.5,0.03,0.4,FIN.steel,{m:0.8,r:0.25}),cx,0.9,cz));
}
