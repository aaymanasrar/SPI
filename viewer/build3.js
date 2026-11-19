// ---------- scene assembly ----------
var KG=window.__KG__;
var CH=3.0;                      // ceiling height: a caller input, not on the plan
var cv=document.getElementById("view"), stage=document.getElementById("stage");
var renderer=new THREE.WebGLRenderer({canvas:cv,antialias:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
var scene=new THREE.Scene();
var camera=new THREE.PerspectiveCamera(58,1,0.05,500);
var cx=KG.building.width_m/2, cz=KG.building.depth_m/2;
var MX=function(x){return x-cx;}, MZ=function(y){return cz-y;};

scene.add(new THREE.HemisphereLight(0xffffff,0x4e5861,1.0));
var sun=new THREE.DirectionalLight(0xfff4e2,0.6); sun.position.set(14,22,10); scene.add(sun);
var fill=new THREE.DirectionalLight(0xdce8ff,0.25); fill.position.set(-12,14,-8); scene.add(fill);

var gShell=new THREE.Group(), gFit=new THREE.Group(), gDev=new THREE.Group(),
    gLabel=new THREE.Group(), gGlass=new THREE.Group();
[gShell,gFit,gDev,gLabel,gGlass].forEach(function(g){scene.add(g);});

// --- floors -------------------------------------------------------------
KG.rooms.forEach(function(r){
  var w=r.x1-r.x0, d=r.y1-r.y0;
  var f=new THREE.Mesh(new THREE.PlaneGeometry(w,d),
    mat(FLOOR_BY_TYPE[r.type]||FIN.floor_vinyl,{r:0.95}));
  f.rotation.x=-Math.PI/2;
  f.position.set(MX((r.x0+r.x1)/2),0.004,MZ((r.y0+r.y1)/2));
  gShell.add(f);
});

// --- walls with door and window openings --------------------------------
var TH=0.11, DOOR_H=2.10, SILL=0.95, WIN_H=1.35;
function openingsOn(a,b,horiz,fixed){
  var out=[];
  function consider(list,kind,h,sill){
    list.forEach(function(o){
      var along=horiz?o.x:o.y, across=horiz?o.y:o.x;
      if(Math.abs(across-fixed)>0.22) return;
      if(along<Math.min(a,b)-0.05||along>Math.max(a,b)+0.05) return;
      out.push({s:along-o.w/2,e:along+o.w/2,h:h,sill:sill,kind:kind,mark:o.mark});
    });
  }
  consider(KG.doors.filter(function(d){return horiz?d.dir==="h":d.dir==="v";}),"door",DOOR_H,0);
  consider(KG.windows.filter(function(d){return horiz?d.dir==="h":d.dir==="v";}),"window",WIN_H,SILL);
  return out.sort(function(p,q){return p.s-q.s;});
}
function wallRun(a,b,fixed,horiz){
  var lo=Math.min(a,b), hi=Math.max(a,b);
  var ops=openingsOn(a,b,horiz,fixed).filter(function(o){return o.e>lo&&o.s<hi;});
  var cur=lo;
  function solid(s,e,y0,y1){
    if(e-s<0.02||y1-y0<0.02) return;
    var m=horiz?box(e-s,y1-y0,TH,FIN.wall,{r:0.9}):box(TH,y1-y0,e-s,FIN.wall,{r:0.9});
    gShell.add(put(m,horiz?MX((s+e)/2):MX(fixed),(y0+y1)/2,horiz?MZ(fixed):MZ((s+e)/2)));
  }
  ops.forEach(function(o){
    var s=Math.max(o.s,lo), e=Math.min(o.e,hi);
    solid(cur,s,0,CH);
    solid(s,e,0,o.sill);                       // sill below a window
    solid(s,e,o.sill+o.h,CH);                  // head above the opening
    if(o.kind==="window"){
      var g=horiz?new THREE.BoxGeometry(e-s,o.h,0.02):new THREE.BoxGeometry(0.02,o.h,e-s);
      var pane=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xbcd6e8,
        roughness:0.05,metalness:0.1,transparent:true,opacity:0.3}));
      gGlass.add(put(pane,horiz?MX((s+e)/2):MX(fixed),o.sill+o.h/2,horiz?MZ(fixed):MZ((s+e)/2)));
    } else {
      var leaf=horiz?box(e-s-0.04,o.h-0.03,0.035,FIN.timber,{r:0.6})
                    :box(0.035,o.h-0.03,e-s-0.04,FIN.timber,{r:0.6});
      leaf.material.transparent=true; leaf.material.opacity=0.55;
      gShell.add(put(leaf,horiz?MX((s+e)/2):MX(fixed),o.h/2,horiz?MZ(fixed):MZ((s+e)/2)));
    }
    cur=Math.max(cur,e);
  });
  solid(cur,hi,0,CH);
}
var seen={};
KG.rooms.forEach(function(r){
  var k;
  k="h|"+r.y0.toFixed(2)+"|"+r.x0.toFixed(2)+"|"+r.x1.toFixed(2);
  if(!seen[k]){seen[k]=1; wallRun(r.x0,r.x1,r.y0,true);}
  k="h|"+r.y1.toFixed(2)+"|"+r.x0.toFixed(2)+"|"+r.x1.toFixed(2);
  if(!seen[k]){seen[k]=1; wallRun(r.x0,r.x1,r.y1,true);}
  k="v|"+r.x0.toFixed(2)+"|"+r.y0.toFixed(2)+"|"+r.y1.toFixed(2);
  if(!seen[k]){seen[k]=1; wallRun(r.y0,r.y1,r.x0,false);}
  k="v|"+r.x1.toFixed(2)+"|"+r.y0.toFixed(2)+"|"+r.y1.toFixed(2);
  if(!seen[k]){seen[k]=1; wallRun(r.y0,r.y1,r.x1,false);}
});

// --- interior fit-out, by room type -------------------------------------
KG.rooms.forEach(function(r){
  var x0=MX(r.x0), x1=MX(r.x1), z0=MZ(r.y0), z1=MZ(r.y1);
  var mx=(x0+x1)/2, mz=(z0+z1)/2, w=Math.abs(x1-x0), d=Math.abs(z1-z0);
  var g=new THREE.Group(); gFit.add(g);
  switch(r.type){
    case "office":
      deskSet(g,mx,mz+0.3,0);
      shelving(g,x0+0.35,z0-0.3,x0+0.35,z0-1.9);
      break;
    case "reception":
      g.add(put(box(2.6,1.05,0.65,FIN.timber_d,{r:0.6}),mx+0.4,0.52,mz-0.9));
      g.add(put(box(2.8,0.05,0.8,FIN.grey,{r:0.4}),mx+0.4,1.07,mz-0.9));
      deskSet(g,mx+0.4,mz-1.7,Math.PI);
      for(var s=0;s<3;s++){
        g.add(put(box(0.55,0.08,0.55,FIN.kidD,{r:0.7}),x0+0.9,0.42,mz+1.2-s*0.7));
        g.add(put(box(0.55,0.45,0.08,FIN.kidD,{r:0.7}),x0+0.9,0.65,mz+0.93-s*0.7));
      }
      break;
    case "classroom":
      var cols=[FIN.kidA,FIN.kidB,FIN.kidC,FIN.kidD];
      var nx=Math.max(1,Math.floor(w/3.0)), nz=Math.max(1,Math.floor(d/3.0)), k=0;
      for(var i=0;i<nx;i++) for(var j=0;j<nz;j++){
        kidTable(g,x0+(i+0.5)*(w/nx)*(x1>x0?1:-1),z0+(j+0.5)*(d/nz)*(z1>z0?1:-1),cols[k++%4]);
      }
      deskSet(g,mx,z1+(z0>z1?0.9:-0.9),z0>z1?Math.PI:0);
      shelving(g,x0+0.3,mz-1.2,x0+0.3,mz+1.2);
      var rug=new THREE.Mesh(new THREE.CircleGeometry(1.25,28),mat(FIN.kidC,{r:0.95}));
      rug.rotation.x=-Math.PI/2; g.add(put(rug,mx,0.008,mz+(z0>z1?1.6:-1.6)));
      break;
    case "toilet":
      wcPan(g,x1+(x0>x1?0.55:-0.55),z0+(z1>z0?0.6:-0.6),Math.PI/2);
      basin(g,x0+(x1>x0?0.5:-0.5),z0+(z1>z0?0.6:-0.6),-Math.PI/2);
      basin(g,x0+(x1>x0?0.5:-0.5),z0+(z1>z0?1.4:-1.4),-Math.PI/2);
      break;
    case "wc":
      wcPan(g,mx,mz,0);
      break;
    case "kitchenette":
      counterRun(g,x0+0.4,z0+(z1>z0?0.35:-0.35),x1-0.4,z0+(z1>z0?0.35:-0.35),true);
      break;
    case "store":
      shelving(g,x0+0.3,z0+(z1>z0?0.35:-0.35),x1-0.3,z0+(z1>z0?0.35:-0.35));
      shelving(g,x0+0.3,z1-(z1>z0?0.35:-0.35),x1-0.3,z1-(z1>z0?0.35:-0.35));
      break;
    case "electrical":
      g.add(put(box(0.9,1.6,0.22,FIN.steel,{m:0.5,r:0.5}),mx,1.5,z1+(z0>z1?0.15:-0.15)));
      g.add(put(box(0.78,1.45,0.03,0x6d757c,{m:0.4,r:0.5}),mx,1.5,z1+(z0>z1?0.3:-0.3)));
      break;
    case "janitor":
      g.add(put(box(0.6,0.5,0.5,FIN.white,{r:0.3}),mx,0.25,mz));
      break;
  }
});
