// --- devices: fire alarm only, every position from a cited rule ------------
var pickable=[], devices=[];
var gHalo=new THREE.Group(), gCov=new THREE.Group(), gStem=new THREE.Group();
scene.add(gHalo); scene.add(gCov); scene.add(gStem);

// A device is 100 mm across. Against a 23 m building that is a speck, so each
// one also gets a marker: a billboard ring at the device and a stem to the
// floor. The device stays true size; the marker is plainly a marker.
function haloFor(d,col){
  var c=document.createElement("canvas"); c.width=c.height=128;
  var g=c.getContext("2d");
  var hexs="#"+new THREE.Color(col).getHexString();
  g.strokeStyle=hexs; g.lineWidth=9; g.globalAlpha=0.95;
  g.beginPath(); g.arc(64,64,42,0,Math.PI*2); g.stroke();
  g.globalAlpha=0.22; g.fillStyle=hexs; g.beginPath(); g.arc(64,64,42,0,Math.PI*2); g.fill();
  g.globalAlpha=1; g.fillStyle=hexs; g.beginPath(); g.arc(64,64,11,0,Math.PI*2); g.fill();
  var t=new THREE.CanvasTexture(c);
  var s=new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true,
    depthTest:false,depthWrite:false}));
  s.scale.set(0.62,0.62,1); s.renderOrder=6;
  return s;
}
function addDevice(d){
  var f=DEV_FACTORY[d.device_type]; if(!f) return;
  var col=DEV_COL[d.system]||0xd42b22;
  var g=f();
  g.position.set(MX(d.x),d.z,MZ(d.y));
  if(d.face!==undefined) g.rotation.y=d.face;
  g.traverse(function(o){ if(o.isMesh){ o.userData.dev=d; pickable.push(o); } });
  g.userData.dev=d; gDev.add(g); devices.push({d:d,obj:g});

  var h=haloFor(d,col);
  h.position.set(MX(d.x),d.z-(d.z>2?0.07:0),MZ(d.y));
  h.userData.dev=d; gHalo.add(h);

  // Stem: ceiling devices hang from the slab, wall devices stand off the floor.
  var top=d.z>2?CH:d.z, bot=d.z>2?d.z-0.06:0;
  var stem=new THREE.Mesh(new THREE.CylinderGeometry(0.012,0.012,Math.max(0.02,top-bot),6),
    new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:0.5}));
  stem.position.set(MX(d.x),(top+bot)/2,MZ(d.y)); gStem.add(stem);

  // Coverage: the 9.1 m cell ELV-B-01 actually allows, drawn on the floor.
  if(d.device_type==="smoke_detector"){
    var S=KG.detector_rule.max_spacing_m;
    var cell=new THREE.Mesh(new THREE.PlaneGeometry(S,S),
      new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:0.07,
        depthWrite:false,side:THREE.DoubleSide}));
    cell.rotation.x=-Math.PI/2; cell.position.set(MX(d.x),0.012,MZ(d.y));
    var ring=new THREE.Mesh(new THREE.RingGeometry(S/2-0.05,S/2,40),
      new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:0.3,
        depthWrite:false,side:THREE.DoubleSide}));
    ring.rotation.x=-Math.PI/2; ring.position.set(MX(d.x),0.014,MZ(d.y));
    gCov.add(cell); gCov.add(ring);
  }
}
KG.proposed_detectors.forEach(function(p,i){
  addDevice({id:"SD-"+(i+1),device_type:"smoke_detector",system:"fire_alarm",
    label:"Smoke detector",x:p.x,y:p.y,z:CH,room:p.room,status:"proposed",
    height_source:"Ceiling mounted — ELV-B-01 / SPT-FA-01 (NFPA 72 Ch.17)",
    place_source:"ELV-B-01 (NFPA 72): max 9.1 m spacing, max 4.6 m to any wall"});
});
KG.proposed_call_points.forEach(function(p,i){
  addDevice({id:"MCP-"+(i+1),device_type:"manual_call_point",system:"fire_alarm",
    label:"Manual call point",x:p.x,y:p.y,z:1.15,room:null,status:"proposed",
    height_band:[1.07,1.22],
    height_source:"SPT-FA-12 (NFPA 72 §17.15.9) — operable part 1.07–1.22 m AFF",
    place_source:"SPT-FA-11 (NFPA 72 §17.15.9): within 1.5 m of each exit door"});
});

// --- room labels ----------------------------------------------------------
function labelSprite(text,sub){
  var c=document.createElement("canvas"); c.width=512; c.height=132;
  var g=c.getContext("2d"); g.textAlign="center";
  g.fillStyle=css("--fg"); g.font="600 44px 'IBM Plex Sans Condensed',sans-serif";
  g.fillText(text,256,52);
  if(sub){ g.fillStyle=css("--muted"); g.font="400 30px 'IBM Plex Mono',monospace";
    g.fillText(sub,256,96); }
  var t=new THREE.CanvasTexture(c);
  var s=new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true,depthTest:false}));
  s.scale.set(3.4,0.88,1); s.renderOrder=4; return s;
}
function drawLabels(){
  gLabel.children.forEach(function(s){ if(s.material.map) s.material.map.dispose(); });
  gLabel.clear();
  KG.rooms.forEach(function(r){
    if(r.type==="wc") return;
    var s=labelSprite(r.name,r.area_m2.toFixed(1)+" m²");
    s.position.set(MX((r.x0+r.x1)/2),0.05,MZ((r.y0+r.y1)/2));
    gLabel.add(s);
  });
}
drawLabels();

// --- camera -------------------------------------------------------------
var mode="orbit", span=Math.max(KG.building.width_m,KG.building.depth_m);
var orb={az:-0.7,el:0.95,r:span*1.25,tx:0,ty:1.0,tz:0};
var walk={x:MX(1.2),y:1.55,z:MZ(5.2),yaw:1.35,pitch:-0.03};
var keys=Object.create(null), held=false;
function applyOrbit(){
  var e=Math.max(0.1,Math.min(1.5,orb.el));
  camera.position.set(orb.tx+orb.r*Math.cos(e)*Math.sin(orb.az),orb.ty+orb.r*Math.sin(e),
                      orb.tz+orb.r*Math.cos(e)*Math.cos(orb.az));
  camera.lookAt(orb.tx,orb.ty,orb.tz);
}
function applyWalk(){
  camera.position.set(walk.x,walk.y,walk.z);
  var cp=Math.cos(walk.pitch);
  camera.lookAt(walk.x+Math.sin(walk.yaw)*cp,walk.y+Math.sin(walk.pitch),walk.z+Math.cos(walk.yaw)*cp);
}
applyOrbit();

var drag=false,lx=0,ly=0,moved=0;
cv.addEventListener("pointerdown",function(e){drag=true;moved=0;lx=e.clientX;ly=e.clientY;cv.setPointerCapture(e.pointerId);});
cv.addEventListener("pointermove",function(e){
  if(!drag)return; var dx=e.clientX-lx,dy=e.clientY-ly; lx=e.clientX; ly=e.clientY;
  moved+=Math.abs(dx)+Math.abs(dy);
  if(mode==="orbit"){orb.az-=dx*0.006;orb.el=Math.max(0.1,Math.min(1.5,orb.el+dy*0.005));applyOrbit();}
  else{walk.yaw-=dx*0.004;walk.pitch=Math.max(-1.2,Math.min(1.2,walk.pitch-dy*0.003));applyWalk();}
});
cv.addEventListener("pointerup",function(e){ if(drag&&moved<6)pick(e); drag=false; });
cv.addEventListener("pointercancel",function(){drag=false;});
cv.addEventListener("wheel",function(e){
  if(mode!=="orbit")return; e.preventDefault();
  orb.r=Math.max(4,Math.min(span*3.5,orb.r*(1+Math.sign(e.deltaY)*0.09))); applyOrbit();
},{passive:false});

var ray=new THREE.Raycaster(), ndc=new THREE.Vector2();
function pick(e){
  var b=cv.getBoundingClientRect();
  ndc.x=((e.clientX-b.left)/b.width)*2-1; ndc.y=-((e.clientY-b.top)/b.height)*2+1;
  ray.setFromCamera(ndc,camera);
  var hits=ray.intersectObjects(pickable,false);
  if(hits.length) select(hits[0].object.userData.dev);
}
document.addEventListener("keydown",function(e){
  var k=e.key.toLowerCase();
  if(["w","a","s","d","arrowup","arrowdown","arrowleft","arrowright"].indexOf(k)>-1){
    keys[k]=true; if(mode==="walk")e.preventDefault(); }
});
document.addEventListener("keyup",function(e){keys[e.key.toLowerCase()]=false;});
var wb=document.getElementById("walkbtn");
["pointerdown","touchstart"].forEach(function(t){wb.addEventListener(t,function(e){e.preventDefault();held=true;});});
["pointerup","pointercancel","touchend"].forEach(function(t){wb.addEventListener(t,function(){held=false;});});

function setMode(m){
  mode=m;
  document.getElementById("m-orbit").setAttribute("aria-pressed",String(m==="orbit"));
  document.getElementById("m-walk").setAttribute("aria-pressed",String(m==="walk"));
  document.getElementById("b-mode").textContent=m==="orbit"?"Overview":"Walk";
  cv.classList.toggle("walking",m==="walk");
  wb.classList.toggle("on",m==="walk");
  gLabel.visible=(m==="orbit")&&document.getElementById("c-labels").checked;
  gCov.visible=(m==="orbit")&&showFA&&document.getElementById("c-cov").checked;
  document.getElementById("hint").innerHTML=m==="orbit"
    ?"Drag to orbit, scroll to zoom. Click any device to see the rule behind it."
    :"<kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> to walk, drag to look. Eye height 1.55 m.";
  if(m==="walk")applyWalk(); else applyOrbit();
}
document.getElementById("m-orbit").addEventListener("click",function(){setMode("orbit");});
document.getElementById("m-walk").addEventListener("click",function(){setMode("walk");});

// --- rail ---------------------------------------------------------------
function titleCase(s){return s.replace(/_/g," ").replace(/\b\w/g,function(c){return c.toUpperCase();});}
var showFA=true;
document.getElementById("t-fa").addEventListener("click",function(){
  showFA=!showFA; this.setAttribute("aria-pressed",String(showFA));
  gDev.visible=showFA; gHalo.visible=showFA; gStem.visible=showFA;
  gCov.visible=showFA&&document.getElementById("c-cov").checked;
});
document.getElementById("c-cov").addEventListener("change",function(e){
  gCov.visible=e.target.checked&&showFA;
});
document.getElementById("c-halo").addEventListener("change",function(e){
  gHalo.visible=e.target.checked&&showFA; gStem.visible=e.target.checked&&showFA;
});
// Dim the architecture so the services read on their own.
var dimmed=false;
document.getElementById("c-dim").addEventListener("change",function(e){
  dimmed=e.target.checked;
  gShell.traverse(function(o){ if(o.isMesh){ o.material.transparent=true;
    o.material.opacity=dimmed?0.14:(o.material.userData.o0===undefined?1:o.material.userData.o0);
    if(o.material.userData.o0===undefined) o.material.userData.o0=1; }});
  gFit.traverse(function(o){ if(o.isMesh){ o.material.transparent=true;
    o.material.opacity=dimmed?0.2:1; }});
});
document.getElementById("c-fit").addEventListener("change",function(e){gFit.visible=e.target.checked;});
document.getElementById("c-walls").addEventListener("change",function(e){
  gShell.visible=e.target.checked; gGlass.visible=e.target.checked;
});
document.getElementById("c-labels").addEventListener("change",function(e){
  gLabel.visible=e.target.checked&&mode==="orbit";
});

function select(d){
  document.getElementById("d-empty").hidden=true;
  document.getElementById("d-body").hidden=false;
  document.getElementById("d-dot").style.background="var(--sys-fire)";
  document.getElementById("d-name").textContent=d.label;
  document.getElementById("d-id").textContent=d.id;
  document.getElementById("d-room").textContent=d.room||"—";
  document.getElementById("d-xy").textContent=d.x.toFixed(2)+", "+d.y.toFixed(2)+" m";
  var band=d.height_band?"  (band "+d.height_band[0].toFixed(2)+"–"+d.height_band[1].toFixed(2)+" m)":"";
  document.getElementById("d-z").textContent=d.z.toFixed(2)+" m AFF"+band;
  document.getElementById("d-hsrc").textContent=d.height_source;
  document.getElementById("d-psrc").textContent=d.place_source;
}

document.getElementById("s-area").textContent=KG.rooms.reduce(function(a,r){return a+r.area_m2;},0).toFixed(0);
document.getElementById("s-rooms").textContent=KG.rooms.length;
document.getElementById("s-dev").textContent=devices.length;
document.getElementById("n-fa").textContent=devices.length;
document.getElementById("n-sd").textContent=KG.proposed_detectors.length;
document.getElementById("n-mcp").textContent=KG.proposed_call_points.length;
document.getElementById("conflict").textContent=KG.building.vertical_conflict;

// --- resize, theme, loop -------------------------------------------------
function resize(){
  var w=stage.clientWidth||1,h=stage.clientHeight||1;
  renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix();
}
window.addEventListener("resize",resize);
function repaint(){ scene.background=hex("--scene-bg"); drawLabels(); gLabel.visible=(mode==="orbit")&&document.getElementById("c-labels").checked; }
if(window.matchMedia){
  var mq=window.matchMedia("(prefers-color-scheme: dark)");
  (mq.addEventListener?mq.addEventListener.bind(mq,"change"):mq.addListener.bind(mq))(repaint);
}
new MutationObserver(repaint).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});

var last=performance.now();
function frame(now){
  var dt=Math.min(0.05,(now-last)/1000); last=now;
  if(mode==="walk"){
    var sp=2.4*dt,f=0,s=0;
    if(keys.w||keys.arrowup||held)f+=1;
    if(keys.s||keys.arrowdown)f-=1;
    if(keys.a||keys.arrowleft)s-=1;
    if(keys.d||keys.arrowright)s+=1;
    if(f||s){
      walk.x+=(Math.sin(walk.yaw)*f+Math.cos(walk.yaw)*s)*sp;
      walk.z+=(Math.cos(walk.yaw)*f-Math.sin(walk.yaw)*s)*sp;
      var pad=1.0;
      walk.x=Math.max(MX(0)-pad,Math.min(MX(KG.building.width_m)+pad,walk.x));
      walk.z=Math.min(MZ(0)+pad,Math.max(MZ(KG.building.depth_m)-pad,walk.z));
      applyWalk();
    }
  }
  renderer.render(scene,camera); requestAnimationFrame(frame);
}
resize(); repaint(); requestAnimationFrame(frame);
