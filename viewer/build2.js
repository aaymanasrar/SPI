// ---------- ELV devices, modelled as the real products read on site ----------
var DEV_COL={fire_alarm:0xd42b22, cctv:0xc07a0f, access_control:0x2f6fd0, data:0x1b8c62};

function mkSmokeDetector(){            // base plate + ivory head + LED
  var g=new THREE.Group();
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.055,0.055,0.012,20),mat(0xf0ece2,{r:0.5})),0,-0.006,0));
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.048,0.052,0.022,20),mat(0xf6f3ea,{r:0.45})),0,-0.026,0));
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.030,0.038,0.016,20),mat(0xe8e3d6,{r:0.5})),0,-0.044,0));
  g.add(put(new THREE.Mesh(new THREE.SphereGeometry(0.006,8,6),mat(0xd42b22,{e:0x5a0f0b,r:0.3})),0.034,-0.040,0));
  return g;                            // hangs below the ceiling plane
}
function mkDomeCamera(){               // mounting plate, dome, lens
  var g=new THREE.Group();
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.058,0.058,0.016,20),mat(0xe9e6e0,{r:0.5})),0,-0.008,0));
  var dome=new THREE.Mesh(new THREE.SphereGeometry(0.052,20,12,0,Math.PI*2,0,Math.PI/2),
    new THREE.MeshStandardMaterial({color:0x2b3238,roughness:0.15,metalness:0.1,
      transparent:true,opacity:0.72,side:THREE.DoubleSide}));
  dome.rotation.x=Math.PI; g.add(put(dome,0,-0.016,0));
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.019,0.023,0.022,14),mat(0x11151a,{r:0.2,m:0.3})),0.012,-0.040,0.012));
  return g;
}
function mkCallPoint(){                // red backbox, pale frangible element
  var g=new THREE.Group();
  g.add(put(box(0.095,0.095,0.028,0xc0241c,{r:0.45}),0,0,0));
  g.add(put(box(0.062,0.062,0.006,0xf4f1e8,{r:0.3,e:0x241010}),0,0.004,0.017));
  g.add(put(box(0.062,0.012,0.004,0xf7f7f4,{r:0.3}),0,-0.036,0.016));
  return g;
}
function mkSounderStrobe(){            // red base, clear strobe lens
  var g=new THREE.Group();
  g.add(put(box(0.10,0.085,0.035,0xc0241c,{r:0.45}),0,0,0));
  var lens=new THREE.Mesh(new THREE.CylinderGeometry(0.036,0.040,0.030,16),
    new THREE.MeshStandardMaterial({color:0xfff6e0,roughness:0.1,transparent:true,
      opacity:0.78,emissive:C(0x6a5520)}));
  lens.rotation.x=Math.PI/2; g.add(put(lens,0,-0.012,0.028));
  for(var i=0;i<4;i++) g.add(put(box(0.07,0.004,0.004,0x8d1a14),0,0.030-i*0.011,0.019));
  return g;
}
function mkCardReader(){               // slim dark reader, LED and keyline
  var g=new THREE.Group();
  g.add(put(box(0.048,0.115,0.018,0x24292e,{r:0.4}),0,0,0));
  g.add(put(box(0.030,0.030,0.004,0x2f6fd0,{e:0x0d2544,r:0.3}),0,0.028,0.011));
  g.add(put(box(0.012,0.004,0.004,0x4ade80,{e:0x16351f}),0,-0.040,0.011));
  return g;
}
function mkWap(){                      // flat white ceiling access point
  var g=new THREE.Group();
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.085,0.085,0.026,22),mat(0xf2f1ee,{r:0.5})),0,-0.013,0));
  g.add(put(new THREE.Mesh(new THREE.CylinderGeometry(0.030,0.030,0.004,14),mat(0xd8d6d1,{r:0.5})),0,-0.028,0));
  g.add(put(new THREE.Mesh(new THREE.SphereGeometry(0.005,8,6),mat(0x1b8c62,{e:0x0b3324})),0.055,-0.027,0));
  return g;
}
function mkDataOutlet(){               // faceplate with two RJ45 ports
  var g=new THREE.Group();
  g.add(put(box(0.086,0.086,0.010,0xf4f3f0,{r:0.4}),0,0,0));
  g.add(put(box(0.018,0.022,0.004,0x2a2f34),-0.018,0.006,0.007));
  g.add(put(box(0.018,0.022,0.004,0x2a2f34),0.018,0.006,0.007));
  return g;
}
function mkDoorContact(){
  var g=new THREE.Group();
  g.add(put(box(0.018,0.062,0.014,0xe8e6e1,{r:0.4}),0,0,0));
  g.add(put(box(0.014,0.040,0.012,0xd5d2cb,{r:0.4}),0.026,0,0));
  return g;
}
var DEV_FACTORY={smoke_detector:mkSmokeDetector, camera:mkDomeCamera,
  manual_call_point:mkCallPoint, sounder_strobe:mkSounderStrobe,
  card_reader:mkCardReader, wireless_access_point:mkWap,
  data_outlet:mkDataOutlet, door_contact:mkDoorContact};
