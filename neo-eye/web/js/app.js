// NEO-EYE — near-Earth space situational awareness viewer
// Frames: ecliptic J2000. Units: astronomical units (au). Time: Julian Date (UTC≈TDB for display; ~69 s offset ignored).
// Rendering uses a floating origin (Earth or Sun) so Earth-scale detail survives float32 GPU precision.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as SAT from 'satellite.js';
import * as AstroNS from 'astronomy-engine';
import { generatePopulation, cumN, diamKm, POP_MODEL } from './population.js';

const Astronomy = AstroNS.default && AstroNS.default.HelioVector ? AstroNS.default : AstroNS;

// ---------- constants ----------
const AU = 149597870.7;            // km
const RE = 6378.137 / AU, RM = 1737.4 / AU, RS = 695700 / AU;
const LD = 384400 / AU;            // lunar distance in au
const OBL = 23.4392811 * Math.PI / 180;
const D2R = Math.PI / 180;
const K_DEG = 0.9856076686;        // deg/day at 1 au
const jdNow = () => Date.now() / 86400000 + 2440587.5;
const jdToDate = (jd) => new Date((jd - 2440587.5) * 86400000);
const $ = (s) => document.querySelector(s);
const fmt = (x, d = 2) => (x == null || isNaN(x)) ? '—' : Number(x).toFixed(d);
const fmtInt = (x) => x == null ? '—' : x.toLocaleString('en-GB');
const ROT_EQJ_ECL = Astronomy.Rotation_EQJ_ECL();

const state = {
  jd: jdNow(), speed: 1, live: true, frame: 'geo', mode: 0, sel: null,
  layers: { known: true, comets: true, model: false, sats: true, debris: true, tracks: true, orbits: true, labels: true, sentryOnly: false },
};
const REF_JD = Math.floor(state.jd) + 0.5;

// ---------- data loading with integrity check ----------
async function sha256hex(buf) {
  try {
    const h = await crypto.subtle.digest('SHA-256', buf);
    return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join('');
  } catch { return null; }
}
const verify = {};
async function load(name, manifest) {
  $('#bootmsg').textContent = `LOADING ${name.toUpperCase()}…`;
  const r = await fetch(`data/${name}`);
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  const buf = await r.arrayBuffer();
  if (manifest && manifest.derived && manifest.derived[name]) {
    const h = await sha256hex(buf);
    verify[name] = h == null ? 'n/a' : (h === manifest.derived[name] ? 'ok' : 'bad');
  }
  return JSON.parse(new TextDecoder().decode(buf));
}

// ---------- renderer / scene ----------
const canvas = $('#gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.setClearColor(0x03060a, 1);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 1e-11, 1e3);
camera.up.set(0, 0, 1);
camera.position.set(0.004, -0.009, 0.004);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.minDistance = RE * 1.15; controls.maxDistance = 60; controls.zoomSpeed = 1.4;
controls.target.set(0, 0, 0); controls.enablePan = false;
scene.add(new THREE.AmbientLight(0x334455, 0.35));
const sunLight = new THREE.DirectionalLight(0xffffff, 2.2);
scene.add(sunLight, sunLight.target);

// starfield (procedural, fixed at "infinity")
{
  const n = 6000, p = new Float32Array(n * 3), c = new Float32Array(n * 3);
  let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < n; i++) {
    const u = r() * 2 - 1, th = r() * Math.PI * 2, rr = Math.sqrt(1 - u * u);
    p.set([rr * Math.cos(th) * 400, rr * Math.sin(th) * 400, u * 400], i * 3);
    const b = 0.25 + Math.pow(r(), 6) * 0.9; c.set([b * 0.9, b * 0.95, b], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('color', new THREE.BufferAttribute(c, 3));
  const stars = new THREE.Points(g, new THREE.PointsMaterial({ size: 1.3, sizeAttenuation: false, vertexColors: true, depthWrite: false }));
  stars.onBeforeRender = () => stars.position.copy(camera.position);
  stars.frustumCulled = false;
  scene.add(stars);
}

const helio = new THREE.Group();   // heliocentric ecliptic content, positioned at -origin
const geo = new THREE.Group();     // geocentric ecliptic content, positioned at Earth-origin
const eq = new THREE.Group();      // geocentric equatorial (TEME≈) content
eq.rotation.x = -OBL;
const spin = new THREE.Group();    // Earth-fixed content
const root = new THREE.Group();   // whole sky; tilted so Earth's north pole is "up" when zoomed in on Earth
scene.add(root); root.add(helio, geo, sunLight, sunLight.target); geo.add(eq); eq.add(spin);
const toW = (p) => new THREE.Vector3(p[0], p[1], p[2]).applyMatrix4(root.matrixWorld);

function glowTexture(rgb, soft = 0.4) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, `rgba(${rgb},1)`); gr.addColorStop(soft, `rgba(${rgb},.35)`); gr.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

// Sun
const sun = new THREE.Mesh(new THREE.SphereGeometry(RS, 48, 32), new THREE.MeshBasicMaterial({ color: 0xfff3d0 }));
const sunGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture('255,214,140', 0.25), blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: false }));
sunGlow.scale.set(0.09, 0.09, 1);
helio.add(sun, sunGlow);

// Earth
// globe in Earth-fixed coordinates (x → 0°E, z → North) with UVs straight from lon/lat
function globeGeometry(R, nLon = 256, nLat = 128) {
  const pos = [], nor = [], uv = [], idx = [];
  for (let j = 0; j <= nLat; j++) {
    const lat = -90 + 180 * j / nLat, cl = Math.cos(lat * D2R), sl = Math.sin(lat * D2R);
    for (let i = 0; i <= nLon; i++) {
      const lon = -180 + 360 * i / nLon, x = cl * Math.cos(lon * D2R), y = cl * Math.sin(lon * D2R);
      pos.push(R * x, R * y, R * sl); nor.push(x, y, sl); uv.push(i / nLon, j / nLat);
    }
  }
  for (let j = 0; j < nLat; j++) for (let i = 0; i < nLon; i++) {
    const a = j * (nLon + 1) + i, b = a + 1, c = a + nLon + 1, d = c + 1; idx.push(a, b, d, a, d, c);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(idx);
  return g;
}
const earthMat = new THREE.MeshPhongMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.0, shininess: 6, specular: 0x0a1418 });
const earth = new THREE.Mesh(globeGeometry(RE), earthMat);
spin.add(earth);
// Paint land (vivid) and sea (near-black with a soft coastal glow) — no political borders
function paintEarth(land) {
  const W = 4096, H = 2048, c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d');
  const X = (lon) => (lon + 180) / 360 * W, Y = (lat) => (90 - lat) / 180 * H;
  const sea = g.createLinearGradient(0, 0, 0, H);
  sea.addColorStop(0, '#060d14'); sea.addColorStop(0.5, '#03080d'); sea.addColorStop(1, '#060d14');
  g.fillStyle = sea; g.fillRect(0, 0, W, H);
  g.strokeStyle = 'rgba(94,240,255,.07)'; g.lineWidth = 1.5;
  for (let lat = -60; lat <= 60; lat += 30) { g.beginPath(); g.moveTo(0, Y(lat)); g.lineTo(W, Y(lat)); g.stroke(); }
  for (let lon = -150; lon <= 180; lon += 30) { g.beginPath(); g.moveTo(X(lon), 0); g.lineTo(X(lon), H); g.stroke(); }
  const path = (ring) => { g.beginPath(); g.moveTo(X(ring[0]), Y(ring[1])); for (let j = 2; j < ring.length; j += 2) g.lineTo(X(ring[j]), Y(ring[j + 1])); g.closePath(); };
  // glow pass (shadow bleeds into the sea), then crisp land, then coastline
  g.save(); g.shadowColor = 'rgba(60,255,200,.55)'; g.shadowBlur = 28; g.fillStyle = '#1b8f6c';
  for (const r of land) { path(r); g.fill(); } g.restore();
  const lg = g.createLinearGradient(0, 0, 0, H);
  lg.addColorStop(0, '#d8f5ff'); lg.addColorStop(0.12, '#4fe0b0'); lg.addColorStop(0.35, '#2fd08f'); lg.addColorStop(0.5, '#3fdc8a');
  lg.addColorStop(0.65, '#2fd08f'); lg.addColorStop(0.88, '#4fe0b0'); lg.addColorStop(1, '#e8f8ff');
  g.fillStyle = lg; for (const r of land) { path(r); g.fill(); }
  g.strokeStyle = '#b8fff0'; g.lineWidth = 2.2; g.lineJoin = 'round'; for (const r of land) { path(r); g.stroke(); }
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  earthMat.map = tex; earthMat.emissiveMap = tex; earthMat.emissiveIntensity = 0.16; earthMat.needsUpdate = true;
}
const atmo = new THREE.Mesh(new THREE.SphereGeometry(RE * 1.018, 64, 48), new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, side: THREE.BackSide, blending: THREE.AdditiveBlending,
  vertexShader: `varying vec3 vN; varying vec3 vV; void main(){ vec4 mv = modelViewMatrix*vec4(position,1.); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
  fragmentShader: `varying vec3 vN; varying vec3 vV; void main(){ float f = pow(1.0-abs(dot(vN,vV)), 4.0); gl_FragColor = vec4(0.25,0.7,1.0,1.0)*f*0.55; }`,
}));
spin.add(atmo);
function addGraticule() {
  const pts = [];
  const R = RE * 1.0015;
  const P = (lat, lon) => [R * Math.cos(lat * D2R) * Math.cos(lon * D2R), R * Math.cos(lat * D2R) * Math.sin(lon * D2R), R * Math.sin(lat * D2R)];
  for (let lat = -60; lat <= 60; lat += 30) for (let lon = 0; lon < 360; lon += 4) pts.push(...P(lat, lon), ...P(lat, lon + 4));
  for (let lon = 0; lon < 360; lon += 30) for (let lat = -88; lat < 88; lat += 4) pts.push(...P(lat, lon), ...P(lat + 4, lon));
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  spin.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x2a6f86, transparent: true, opacity: 0.22 })));
}
const earthGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture('94,200,255', 0.3), blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: false, transparent: true, opacity: 0.0 }));
earthGlow.scale.set(0.035, 0.035, 1);
geo.add(earthGlow);

// Moon
const moon = new THREE.Mesh(new THREE.SphereGeometry(RM, 48, 32), new THREE.MeshPhongMaterial({ color: 0x9a9a9a, shininess: 2 }));
geo.add(moon);

// body markers (fixed pixel size so they stay visible at au scale)
const BODIES = [
  ['Sun', null, 0xffd38a], ['Mercury', 'Mercury', 0xb8a99a], ['Venus', 'Venus', 0xf3d9a4], ['Earth', 'Earth', 0x5ec8ff],
  ['Moon', 'Moon', 0xdddddd], ['Mars', 'Mars', 0xff7a50], ['Jupiter', 'Jupiter', 0xe8c39e],
];
const bodyPos = new Float32Array(BODIES.length * 3), bodyCol = new Float32Array(BODIES.length * 3);
BODIES.forEach((b, i) => { const c = new THREE.Color(b[2]); bodyCol.set([c.r, c.g, c.b], i * 3); });
const bodyGeom = new THREE.BufferGeometry();
bodyGeom.setAttribute('position', new THREE.BufferAttribute(bodyPos, 3));
bodyGeom.setAttribute('color', new THREE.BufferAttribute(bodyCol, 3));
const bodyPts = new THREE.Points(bodyGeom, new THREE.PointsMaterial({ size: 7, sizeAttenuation: false, vertexColors: true, map: glowTexture('255,255,255', 0.5), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
bodyPts.frustumCulled = false;
root.add(bodyPts);
const bodyWorld = {};

// planet + Moon orbit lines
const orbitGroup = new THREE.Group(); helio.add(orbitGroup);
function eclVec(v) { const r = Astronomy.RotateVector(ROT_EQJ_ECL, v); return [r.x, r.y, r.z]; }
function helioOf(body, t) { return eclVec(Astronomy.HelioVector(Astronomy.Body[body], t)); }
function buildPlanetOrbits() {
  const per = { Mercury: 88, Venus: 225, Earth: 365.25, Mars: 687, Jupiter: 4333 };
  for (const [name, P] of Object.entries(per)) {
    const pts = [];
    for (let k = 0; k <= 360; k++) { const t = Astronomy.MakeTime(jdToDate(state.jd + (k / 360) * P)); pts.push(...helioOf(name, t)); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    orbitGroup.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: name === 'Earth' ? 0x2f8fb0 : 0x3a4e5a, transparent: true, opacity: name === 'Earth' ? 0.8 : 0.55 })));
  }
  const mp = [];
  for (let k = 0; k <= 240; k++) { const t = Astronomy.MakeTime(jdToDate(state.jd + (k / 240) * 27.32)); mp.push(...eclVec(Astronomy.GeoMoon(t))); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(mp, 3));
  const ml = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x8899aa, transparent: true, opacity: 0.45 }));
  geo.add(ml); state.moonOrbit = ml;
  // GEO ring reference (equatorial)
  const gr = []; const rg = 42164 / AU;
  for (let k = 0; k <= 180; k++) { const a = k / 180 * Math.PI * 2; gr.push(rg * Math.cos(a), rg * Math.sin(a), 0); }
  const g2 = new THREE.BufferGeometry(); g2.setAttribute('position', new THREE.Float32BufferAttribute(gr, 3));
  const geoRing = new THREE.Line(g2, new THREE.LineBasicMaterial({ color: 0xffb020, transparent: true, opacity: 0.25 }));
  eq.add(geoRing); state.geoRing = geoRing;
}

// ---------- NEO points (GPU two-body propagation) ----------
const neoVS = /* glsl */`
  attribute vec4 el1;   // a(au), e, i(rad), node(rad)
  attribute vec4 el2;   // peri(rad), M0(rad), n(rad/d), epoch-REF(d)
  attribute vec4 meta;  // H, U, flags, class
  uniform float uT; uniform vec3 uOrigin; uniform float uMode; uniform float uPx;
  uniform float uShowKnown, uShowComets, uShowModel, uSentryOnly; uniform float uSel;
  varying vec3 vCol; varying float vA;
  vec3 ramp(float x){ x=clamp(x,0.,1.); return x<0.5? mix(vec3(0.22,0.85,0.54), vec3(1.0,0.82,0.25), x*2.) : mix(vec3(1.0,0.82,0.25), vec3(1.0,0.23,0.23), (x-0.5)*2.); }
  void main(){
    float a=el1.x, e=el1.y, inc=el1.z, Om=el1.w, w=el2.x;
    float M = mod(el2.y + el2.z*(uT - el2.w), 6.28318530718);
    float E = e < 0.8 ? M : 3.14159265;
    for(int k=0;k<10;k++){ E -= (E - e*sin(E) - M)/(1.0 - e*cos(E)); }
    float xv = a*(cos(E)-e), yv = a*sqrt(max(0.,1.0-e*e))*sin(E);
    float cw=cos(w), sw=sin(w), cO=cos(Om), sO=sin(Om), ci=cos(inc), si=sin(inc);
    float x1 = cw*xv - sw*yv, y1 = sw*xv + cw*yv;
    vec3 p = vec3(cO*x1 - sO*ci*y1, sO*x1 + cO*ci*y1, si*y1) - uOrigin;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0);
    float H = meta.x, U = meta.y, f = meta.z, cls = meta.w;
    bool pha = mod(f,2.)>=1., sen = mod(floor(f/2.),2.)>=1., com = mod(floor(f/4.),2.)>=1., mdl = mod(floor(f/8.),2.)>=1.;
    float show = mdl ? uShowModel : (com ? uShowComets : uShowKnown);
    if (uSentryOnly > 0.5 && !sen && !mdl) show = 0.;
    float sz = clamp(1.4 + (23.0 - H)*0.42, 1.2, 7.5);
    vec3 c; float al = 0.85;
    if (mdl) { c = vec3(0.55,0.48,0.78); al = 0.22; sz = 1.3; }
    else if (uMode < 0.5) {
      c = cls==1.? vec3(1.0,0.62,0.26) : cls==2.? vec3(0.31,0.76,0.97) : cls==3.? vec3(0.48,0.85,0.56) : cls==4.? vec3(0.71,0.55,1.0) : vec3(0.88,0.97,1.0);
    } else if (uMode < 1.5) {
      if (sen) { c = vec3(1.0,0.69,0.13); sz += 2.0; al = 1.0; }
      else if (pha) { c = vec3(1.0,0.3,0.3); sz += 1.0; al = 0.95; }
      else { c = vec3(0.23,0.32,0.38); al = 0.35; }
    } else if (uMode < 2.5) {
      c = U < 0. ? vec3(0.4) : ramp(U/9.0); al = 0.9;
    } else {
      float t = clamp((H-14.)/14., 0., 1.);
      c = mix(vec3(1.0,0.97,0.88), vec3(0.85,0.2,0.1), t); al = 1.0 - t*0.6;
    }
    if (float(gl_VertexID) == uSel) { c = vec3(0.37,0.94,1.0); sz = 11.0; al = 1.0; }
    vCol = c; vA = al * show;
    gl_PointSize = show > 0.5 ? sz * uPx : 0.0;
  }`;
const neoFS = /* glsl */`
  varying vec3 vCol; varying float vA;
  void main(){ vec2 q = gl_PointCoord - 0.5; float d = length(q); if (d > 0.5 || vA <= 0.0) discard;
    float g = smoothstep(0.5, 0.0, d); gl_FragColor = vec4(vCol * (0.6 + 0.8*g), vA * g); }`;
const neoMat = new THREE.ShaderMaterial({
  vertexShader: neoVS, fragmentShader: neoFS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  uniforms: {
    uT: { value: 0 }, uOrigin: { value: new THREE.Vector3() }, uMode: { value: 0 }, uPx: { value: renderer.getPixelRatio() },
    uShowKnown: { value: 1 }, uShowComets: { value: 1 }, uShowModel: { value: 0 }, uSentryOnly: { value: 0 }, uSel: { value: -1 },
  },
});
let NEO = null;          // known catalogue (float64 copies for CPU picking)
let POP = null;          // modelled population summary

function buildNEO(neo) {
  const nK = neo.a.length;
  POP = generatePopulation(neo);
  const nM = POP.count, N = nK + nM;
  const el1 = new Float32Array(N * 4), el2 = new Float32Array(N * 4), meta = new Float32Array(N * 4), pos = new Float32Array(N * 3);
  const sentry = new Set();
  for (let k = 0; k < nK; k++) {
    const a = neo.a[k], n = K_DEG / Math.pow(a, 1.5) * D2R;
    el1.set([a, neo.e[k], neo.i[k] * D2R, neo.om[k] * D2R], k * 4);
    el2.set([neo.w[k] * D2R, neo.ma[k] * D2R, n, neo.ep[k] - REF_JD], k * 4);
    const flags = (neo.pha[k] ? 1 : 0) | (neo.sen[k] ? 2 : 0) | (neo.kind[k] === 'c' ? 4 : 0);
    meta.set([neo.H[k] ?? 20, neo.U[k], flags, neo.cls[k]], k * 4);
    if (neo.sen[k]) sentry.add(k);
  }
  for (let j = 0; j < nM; j++) {
    const k = nK + j, a = POP.a[j], n = K_DEG / Math.pow(a, 1.5) * D2R;
    el1.set([a, POP.e[j], POP.i[j] * D2R, POP.om[j] * D2R], k * 4);
    el2.set([POP.w[j] * D2R, POP.ma[j] * D2R, n, 0], k * 4);
    meta.set([POP.H[j], -1, 8, 0], k * 4);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('el1', new THREE.BufferAttribute(el1, 4));
  g.setAttribute('el2', new THREE.BufferAttribute(el2, 4));
  g.setAttribute('meta', new THREE.BufferAttribute(meta, 4));
  const pts = new THREE.Points(g, neoMat); pts.frustumCulled = false; pts.renderOrder = 2;
  root.add(pts);
  NEO = { ...neo, n: nK, sentry };
}

// CPU two-body (same maths as shader, float64) — for picking and the info card
function neoHelio(k, jd) {
  const a = NEO.a[k], e = NEO.e[k], inc = NEO.i[k] * D2R, Om = NEO.om[k] * D2R, w = NEO.w[k] * D2R;
  const n = K_DEG / Math.pow(a, 1.5) * D2R;
  let M = (NEO.ma[k] * D2R + n * (jd - NEO.ep[k])) % (2 * Math.PI); if (M < 0) M += 2 * Math.PI;
  let E = e < 0.8 ? M : Math.PI;
  for (let it = 0; it < 30; it++) { const d = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E)); E -= d; if (Math.abs(d) < 1e-12) break; }
  const xv = a * (Math.cos(E) - e), yv = a * Math.sqrt(1 - e * e) * Math.sin(E);
  const cw = Math.cos(w), sw = Math.sin(w), cO = Math.cos(Om), sO = Math.sin(Om), ci = Math.cos(inc), si = Math.sin(inc);
  const x1 = cw * xv - sw * yv, y1 = sw * xv + cw * yv;
  return [cO * x1 - sO * ci * y1, sO * x1 + cO * ci * y1, si * y1];
}
function orbitLine(k) {
  const a = NEO.a[k], e = NEO.e[k], pts = [];
  const P = 365.25 * Math.pow(a, 1.5);
  for (let s = 0; s <= 512; s++) {
    // sample in eccentric anomaly for even spacing
    const E = s / 512 * Math.PI * 2; const M = E - e * Math.sin(E);
    const n = K_DEG / Math.pow(a, 1.5) * D2R;
    const jd = NEO.ep[k] + (M - NEO.ma[k] * D2R) / n;
    pts.push(...neoHelio(k, jd));
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  return new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x5ef0ff, transparent: true, opacity: 0.85 }));
}

// ---------- satellites (SGP4) ----------
let SATS = null;
function buildSats(sats) {
  const F = sats.fields, idx = Object.fromEntries(F.map((f, i) => [f, i]));
  const recs = [], names = [], grp = [], cols = [];
  for (const r of sats.rows) {
    const omm = {}; for (const f of F) omm[f] = r[idx[f]];
    try { recs.push(SAT.json2satrec(omm)); } catch { continue; }
    names.push(r[idx.OBJECT_NAME]); grp.push(r[idx.G]);
    const nmm = Number(r[idx.MEAN_MOTION]), ecc = Number(r[idx.ECCENTRICITY]);
    const deb = sats.groups[r[idx.G]] !== 'active' || / DEB|R\/B/.test(r[idx.OBJECT_NAME]);
    const c = deb ? 0xff6b6b : nmm > 11.25 ? 0x5ef0ff : (nmm > 0.9 && nmm < 1.1 && ecc < 0.1) ? 0xffb020 : ecc > 0.25 ? 0xc58cff : 0x7bd88f;
    cols.push(c);
  }
  const N = recs.length, pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
  cols.forEach((c, i) => { const cc = new THREE.Color(c); col.set([cc.r, cc.g, cc.b], i * 3); });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const isDeb = new Uint8Array(N); cols.forEach((c, i) => isDeb[i] = c === 0xff6b6b ? 1 : 0);
  const satMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uPx: { value: renderer.getPixelRatio() }, uShowA: { value: 1 }, uShowD: { value: 1 }, uSel: { value: -1 }, uHov: { value: -1 }, uIcon: { value: 0 } },
    vertexShader: `attribute vec3 color; attribute float deb; uniform float uPx, uShowA, uShowD, uSel, uHov, uIcon; varying vec3 vC; varying float vA; varying float vD;
      void main(){ vC = color; vD = deb; float show = deb > 0.5 ? uShowD : uShowA; vA = show;
        float id = float(gl_VertexID); bool s = id==uSel, h = id==uHov;
        if (s || h) vC = vec3(1.0);
        float base = uIcon > 0.5 ? (deb > 0.5 ? 5.0 : 9.0) : 2.2;
        gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.);
        gl_PointSize = show*(s ? max(base*1.6, 9.) : h ? max(base*1.4, 8.) : base)*uPx; }`,
    fragmentShader: `varying vec3 vC; varying float vA; varying float vD; uniform float uIcon;
      void main(){ if (vA <= 0.) discard; vec2 q = gl_PointCoord - .5;
        if (uIcon > .5) {
          vec2 a = abs(q); float m;
          if (vD > .5) m = step(a.x + a.y, .42);                                   // debris: small diamond
          else m = max(max(step(a.x,.11)*step(a.y,.15),                               // bus
                           step(.19,a.x)*step(a.x,.49)*step(a.y,.09)),               // solar panels
                       step(a.x,.19)*step(a.y,.025));                                 // struts
          if (m < .5) discard; gl_FragColor = vec4(vC, vA);
        } else { float d = length(q); if (d > .5) discard; gl_FragColor = vec4(vC, vA*smoothstep(.5,0.,d)); } }`,
  });
  g.setAttribute('deb', new THREE.BufferAttribute(new Float32Array(isDeb), 1));
  const pts = new THREE.Points(g, satMat); pts.frustumCulled = false;
  eq.add(pts);
  SATS = { recs, names, grp, pos, g, mat: satMat, N, cursor: 0, isDeb, iss: names.findIndex(n => n.startsWith('ISS (ZARYA)')) };
}
function propagateSats(date, count) {
  if (!SATS) return;
  const { recs, pos, N } = SATS;
  const end = Math.min(N, SATS.cursor + count);
  for (let i = SATS.cursor; i < end; i++) {
    let pv = null; try { pv = SAT.propagate(recs[i], date); } catch { }
    const p = pv && pv.position;
    if (p && typeof p === 'object' && isFinite(p.x)) { pos[i * 3] = p.x / AU; pos[i * 3 + 1] = p.y / AU; pos[i * 3 + 2] = p.z / AU; }
    else { pos[i * 3] = pos[i * 3 + 1] = pos[i * 3 + 2] = 1e3; }
  }
  SATS.cursor = end >= N ? 0 : end;
  SATS.g.attributes.position.needsUpdate = true;
}

// ---------- Horizons flyby tracks ----------
let TRACKS = [];
const trackGroup = new THREE.Group(); geo.add(trackGroup);
let trackMarkers = null;
function buildTracks(tracks) {
  TRACKS = tracks.map(t => {
    const n = t.xyz.length / 3; let dmin = 1e9, kmin = 0;
    for (let k = 0; k < n; k++) { const d = Math.hypot(t.xyz[k * 3], t.xyz[k * 3 + 1], t.xyz[k * 3 + 2]); if (d < dmin) { dmin = d; kmin = k; } }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(t.xyz, 3));
    // fade each track away from Earth so the cislunar region stays readable
    const ca = new Float32Array(n * 4);
    for (let k = 0; k < n; k++) { const d = Math.hypot(t.xyz[k * 3], t.xyz[k * 3 + 1], t.xyz[k * 3 + 2]); ca.set([1, 1, 1, Math.max(0.04, Math.exp(-d / (4 * LD)))], k * 4); }
    g.setAttribute('color', new THREE.BufferAttribute(ca, 4));
    const hot = dmin < LD;
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({ vertexColors: true, color: hot ? 0xff6a3d : 0xffb020, transparent: true, opacity: hot ? 0.85 : 0.5, depthWrite: false }));
    trackGroup.add(line);
    return { ...t, n, dmin, jdca: t.jd0 + kmin * t.step, line };
  });
  const p = new Float32Array(TRACKS.length * 3).fill(1e3);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  trackMarkers = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffd27a, size: 7, sizeAttenuation: false, map: glowTexture('255,210,122', 0.45), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  trackMarkers.frustumCulled = false;
  geo.add(trackMarkers);
}
function trackPos(t, jd) {
  const f = (jd - t.jd0) / t.step; if (f < 0 || f > t.n - 1) return null;
  const k = Math.min(t.n - 2, Math.floor(f)), u = f - k, x = t.xyz;
  return [x[k * 3] + (x[k * 3 + 3] - x[k * 3]) * u, x[k * 3 + 1] + (x[k * 3 + 4] - x[k * 3 + 1]) * u, x[k * 3 + 2] + (x[k * 3 + 5] - x[k * 3 + 2]) * u];
}

// ---------- labels ----------
const labelRoot = $('#labels'); const labelPool = [];
function setLabels(items) {
  while (labelPool.length < items.length) { const d = document.createElement('div'); d.className = 'lb'; labelRoot.appendChild(d); labelPool.push(d); }
  const v = new THREE.Vector3(); let used = 0;
  for (const it of items) {
    (it.w ? v.copy(it.w) : v.copy(toW(it.p))).project(camera);
    if (v.z > 1 || v.z < -1 || Math.abs(v.x) > 1.05 || Math.abs(v.y) > 1.05) continue;
    const d = labelPool[used++];
    d.textContent = it.t; d.className = 'lb ' + (it.c || '');
    d.style.left = ((v.x + 1) / 2 * innerWidth) + 'px'; d.style.top = ((1 - v.y) / 2 * innerHeight) + 'px'; d.style.display = '';
  }
  for (let i = used; i < labelPool.length; i++) labelPool[i].style.display = 'none';
}

// ---------- UI ----------
let CAD = [], SENTRY = [], MANIFEST = null;
const LAYERS = [
  ['known', 'Known asteroids (JPL SBDB)', '#4fc3f7'], ['comets', 'Near-Earth comets', '#e0f7ff'],
  ['model', 'Modelled undiscovered', '#8a7fb0'], ['sentryOnly', 'Sentry risk list only', '#ffb020'],
  ['sats', 'Active satellites', '#5ef0ff'], ['debris', 'Debris clouds', '#ff6b6b'],
  ['tracks', 'Flyby tracks (Horizons)', '#ff6a3d'], ['orbits', 'Planet & Moon orbits', '#3a4e5a'], ['labels', 'Labels', '#cfe8f2'],
];
function layerCounts() {
  const nComets = NEO.kind.filter(k => k === 'c').length;
  return { known: NEO.n - nComets, comets: nComets, model: POP.count, sentryOnly: NEO.sentry.size, sats: SATS.N - SATS.isDeb.reduce((a, b) => a + b, 0), debris: SATS.isDeb.reduce((a, b) => a + b, 0), tracks: TRACKS.length };
}
function buildUI() {
  const cnt = layerCounts();
  $('#layers').innerHTML = LAYERS.map(([k, t, c]) => `<label class="tg"><input type="checkbox" data-l="${k}" ${state.layers[k] ? 'checked' : ''}><span class="sw" style="background:${c}"></span>${t}<span class="n">${cnt[k] != null ? fmtInt(cnt[k]) : ''}</span></label>`).join('');
  $('#layers').onchange = (e) => { const k = e.target.dataset.l; state.layers[k] = e.target.checked; applyLayers(); };
  const grp = (sel, attr, fn) => $(sel).addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b || b.dataset[attr] == null) return; $(sel).querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset[attr]); });
  grp('#frames', 'frame', setFrame);
  grp('#views', 'view', (v) => flyTo(v));
  grp('#modes', 'mode', (m) => { state.mode = +m; neoMat.uniforms.uMode.value = +m; drawLegend(); });
  grp('#sensors', 'sensor', (s) => { canvas.className = s; });
  $('#speeds').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.id === 'live') { state.live = true; state.jd = jdNow(); state.speed = 1; }
    else { state.live = false; state.speed = +b.dataset.s; }
    $('#speeds').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b || (b.id === 'live' && x.dataset.s === '1')));
  });
  // known vs estimated
  const Hk = NEO.H.filter((h, k) => h != null && NEO.kind[k] === 'a');
  const rows = [['≥ 1 km', 17.75], ['≥ 140 m', 22], ['≥ 55 m', 24]].map(([lab, h]) => {
    const known = Hk.filter(x => x < h).length, est = cumN(h);
    const pct = Math.min(100, known / est * 100);
    return `<tr><td>${lab}</td><td style="text-align:right">${fmtInt(known)} / ~${fmtInt(Math.round(est / 100) * 100)}</td><td style="width:70px;padding-left:8px"><div class="bar"><i style="width:${pct}%"></i></div></td><td style="text-align:right;width:34px">${pct.toFixed(0)}%</td></tr>`;
  });
  $('#cmp').innerHTML = `<tr><td class="n" style="margin:0">size</td><td class="n" style="text-align:right">known / est.</td><td></td><td></td></tr>` + rows.join('');
  $('#popinfo').onclick = (e) => { e.preventDefault(); showMethod(); };
  // search
  const lower = NEO.name.map(s => s.toLowerCase());
  $('#search').oninput = (e) => {
    const q = e.target.value.trim().toLowerCase(); const out = [];
    if (q.length >= 2) {
      for (let k = 0; k < lower.length && out.length < 8; k++) if (lower[k].includes(q)) out.push(`<div data-k="${k}">◇ ${NEO.name[k]}</div>`);
      if (SATS) for (let i = 0; i < SATS.N && out.length < 10; i++) if (SATS.names[i].toLowerCase().includes(q)) out.push(`<div data-s="${i}">▪ ${SATS.names[i]}</div>`);
    }
    $('#sres').innerHTML = out.join('');
  };
  $('#sres').onclick = (e) => {
    const d = e.target.closest('div'); if (!d) return;
    if (d.dataset.k) select({ type: 'neo', k: +d.dataset.k }); else select({ type: 'sat', k: +d.dataset.s });
    $('#sres').innerHTML = ''; $('#search').value = '';
  };
  buildCAList(); drawLegend(); buildProv(); initTips();
  $('#fps').textContent = `TRACKING ${fmtInt(NEO.n + POP.count + SATS.N + TRACKS.length + BODIES.length)} OBJECTS · ${fmtInt(NEO.n + SATS.N)} CATALOGUED`;
  // timeline
  const tl = $('#tl');
  tl.onclick = (e) => { const r = tl.getBoundingClientRect(); const f = (e.clientX - r.left) / r.width; state.jd = TL0 + f * (TL1 - TL0); goManual(); };
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') select(null); });
}
const TIPS = {
  'frame:geo': 'Earth stays fixed in the middle; the Sun, Moon and planets move around it. The analyst’s view of what is coming at us.',
  'frame:helio': 'The real solar-system layout: the Sun in the middle, Earth and the asteroids orbiting it.',
  'view:leo': 'Close-up of Earth and its satellites, out to the geostationary ring (36,000 km). Earth turns north-up here.',
  'view:cis': 'Earth–Moon space (~400,000 km). Real asteroid flybys from JPL Horizons show here as orange paths.',
  'view:near': 'About 40 million km around Earth: where close approaches start to matter.',
  'view:inner': 'Out to Jupiter: the whole near-Earth asteroid population around the Sun.',
  'mode:0': 'CLASS: colour asteroids by orbit family: Atira (inside Earth’s orbit), Aten, Apollo (cross Earth’s orbit), Amor (just outside), and comets.',
  'mode:1': 'THREAT: highlight potentially hazardous asteroids (PHAs, red) and objects on NASA’s Sentry impact-monitoring list (amber). Everything else dims.',
  'mode:2': 'INTEGRITY: colour by how well each orbit is known (JPL uncertainty U: 0 = precise, 9 = poorly constrained). This is the research lens: over half the catalogue is U ≥ 7.',
  'mode:3': 'SIZE: colour by brightness, which stands in for size (absolute magnitude H: lower = bigger).',
  'sensor:': 'EO (electro-optical): normal colour display.',
  'sensor:nv': 'NV: night-vision style (green). A display effect only; the data does not change.',
  'sensor:flir': 'FLIR: thermal-camera style (false colour). A display effect only; the data does not change.',
  'speed:-86400': 'Run time backwards at 1 day per second.', 'speed:0': 'Pause the clock.', 'speed:1': 'Real time.',
  'speed:3600': '1 hour per second: good for watching a flyby.', 'speed:86400': '1 day per second.', 'speed:2592000': '30 days per second: watch the planets and asteroids orbit.',
  'live': 'Jump back to now and run in real time.',
  'layer:known': 'Every near-Earth asteroid in NASA/JPL’s catalogue, moved along its orbit in real time.',
  'layer:comets': 'Comets whose orbits come near Earth’s (perihelion < 1.3 au).',
  'layer:model': 'NOT real objects: a statistical stand-in for the asteroids not yet discovered, from published population models. Shows the gap between what we know and what is out there.',
  'layer:sentryOnly': 'Show only objects on NASA’s Sentry list: those with a non-zero impact probability in the next 100 years.',
  'layer:sats': 'Active satellites, positions computed live with the SGP4 model from CelesTrak data.',
  'layer:debris': 'Tracked fragments from the four biggest break-ups: Fengyun-1C (2007 missile test), Cosmos 2251 + Iridium 33 (2009 collision), Cosmos 1408 (2021 missile test). Over the years each cloud spread into a shell around Earth.',
  'layer:tracks': 'Exact flyby paths (JPL Horizons) of every asteroid passing within 0.05 au (~19 Moon distances) of Earth in this window.',
  'layer:orbits': 'Orbits of the planets and the Moon, and the geostationary ring.',
  'layer:labels': 'Names on screen. Zoom into Earth to see satellite names and trails.',
};
function initTips() {
  const tipBox = document.createElement('div'); tipBox.id = 'uitip'; document.body.appendChild(tipBox);
  const keyOf = (el) => el.dataset.tip || (el.dataset.frame && 'frame:' + el.dataset.frame) || (el.dataset.view && 'view:' + el.dataset.view) || (el.dataset.mode != null && 'mode:' + el.dataset.mode) || (el.dataset.sensor != null && 'sensor:' + el.dataset.sensor) || (el.dataset.s != null && 'speed:' + el.dataset.s) || (el.id === 'live' && 'live') || (el.querySelector && el.querySelector('input[data-l]') && 'layer:' + el.querySelector('input[data-l]').dataset.l);
  document.addEventListener('mouseover', (e) => {
    const el = e.target.closest('button, label.tg, [data-tip]'); if (!el) { tipBox.style.display = 'none'; return; }
    const k = keyOf(el); const t = TIPS[k] || (k && !TIPS[k] && el.dataset.tip && el.dataset.tip.length > 12 ? el.dataset.tip : null);
    if (!t) { tipBox.style.display = 'none'; return; }
    tipBox.textContent = t; tipBox.style.display = 'block';
    const r = el.getBoundingClientRect(); const bw = Math.min(300, innerWidth - 20);
    let x = Math.min(innerWidth - bw - 10, Math.max(10, r.left)); let y = r.bottom + 8;
    tipBox.style.maxWidth = bw + 'px'; tipBox.style.left = x + 'px'; tipBox.style.top = y + 'px';
    if (y + tipBox.offsetHeight > innerHeight - 8) tipBox.style.top = (r.top - tipBox.offsetHeight - 8) + 'px';
  });
  $('#guideBtn').onclick = () => { const g = $('#guide'); g.style.display = g.style.display === 'flex' ? 'none' : 'flex'; };
  $('#guide').onclick = (e) => { if (e.target.id === 'guide' || e.target.id === 'gx') $('#guide').style.display = 'none'; };
  $('#panelsBtn').onclick = () => { document.body.classList.toggle('clean'); $('#panelsBtn').classList.toggle('on', !document.body.classList.contains('clean')); };
  try { if (!localStorage.getItem('neoeye-guided')) { $('#guide').style.display = 'flex'; localStorage.setItem('neoeye-guided', '1'); } } catch { }
}

function goManual() { state.live = false; document.querySelectorAll('#speeds button').forEach(x => x.classList.toggle('on', x.dataset.s === String(state.speed))); }

function drawLegend() {
  const L = [
    [['#ff9f43', 'Aten'], ['#4fc3f7', 'Apollo'], ['#7bd88f', 'Amor'], ['#b48cff', 'Atira'], ['#e0f7ff', 'Comet']],
    [['#ffb020', 'Sentry (impact-monitored)'], ['#ff4d4d', 'PHA'], ['#3a5260', 'Other']],
    [['#39d98a', 'U 0 · well determined'], ['#ffd040', 'U 4–5'], ['#ff3b3b', 'U 9 · poorly constrained']],
    [['#fff8e0', 'H 14 (≈ 5 km)'], ['#e07a40', 'H 22 (≈ 140 m)'], ['#a0301a', 'H 28 (≈ 9 m)']],
  ][state.mode];
  const sats = [['#5ef0ff', 'LEO'], ['#7bd88f', 'MEO'], ['#ffb020', 'GEO'], ['#c58cff', 'HEO'], ['#ff6b6b', 'debris']];
  $('#legend').innerHTML = L.map(([c, t]) => `<span class="sw" style="background:${c}"></span>${t}`).join('&nbsp;&nbsp;') +
    `<span class="sp"></span>` + sats.map(([c, t]) => `<span class="sw" style="background:${c}"></span>${t}`).join('&nbsp;&nbsp;');
}

const ldStr = (au) => au / LD < 10 ? `${(au / LD).toFixed(2)} LD` : `${(au / LD).toFixed(1)} LD`;
const sizeStr = (D, H) => D != null ? (D >= 1 ? `${D.toFixed(1)} km` : `${Math.round(D * 1000)} m`) : (H != null ? `~${diamKm(H) >= 1 ? diamKm(H).toFixed(1) + ' km' : Math.round(diamKm(H) * 1000) + ' m'}` : '—');
function buildCAList() {
  const now = jdNow();
  const rows = CAD.filter(c => c.jd >= now - 1).slice(0, 200);
  const trackSet = new Set(TRACKS.map(t => t.des));
  $('#cacount').textContent = `${rows.length} upcoming`;
  $('#calist').innerHTML = rows.map((c, i) => {
    const ld = c.dist / LD; const cls = ld < 1 ? 'crit' : ld < 5 ? 'hot' : '';
    const d = jdToDate(c.jd); const ds = d.toUTCString().slice(5, 11) + ' ' + d.toISOString().slice(11, 16);
    return `<div class="ca ${cls}" data-i="${CAD.indexOf(c)}"><span class="d">${ds}</span><span>${trackSet.has(c.des) ? '<span class="tk">◆</span> ' : ''}${c.des}<br><span class="d">${sizeStr(c.D, c.h)} · ${fmt(c.v, 1)} km/s</span></span><span class="ld">${ldStr(c.dist)}</span></div>`;
  }).join('');
  $('#calist').onclick = (e) => {
    const r = e.target.closest('.ca'); if (!r) return; const c = CAD[+r.dataset.i];
    state.jd = c.jd - 0.5; state.speed = 3600; goManual();
    const ti = TRACKS.findIndex(t => t.des === c.des);
    if (ti >= 0) { select({ type: 'track', k: ti }); if (state.frame !== 'geo') clickFrame('geo'); flyTo('cis'); }
    else { const k = NEO.pdes.indexOf(c.des); if (k >= 0) select({ type: 'neo', k }); if (state.frame !== 'geo') clickFrame('geo'); flyTo(c.dist < 0.02 ? 'cis' : 'near'); }
  };
}
function clickFrame(f) { const b = document.querySelector(`#frames button[data-frame="${f}"]`); b && b.click(); }

async function buildProv() {
  const m = MANIFEST; const files = Object.entries(m.files);
  const raw = files.filter(([k]) => !k.startsWith('horizons/'));
  const nH = files.length - raw.length;
  const vs = Object.entries(verify);
  const allOk = vs.length && vs.every(([, v]) => v === 'ok');
  $('#pkt').textContent = `PACKET ${m.packet} · SEAL ${m.packet_sha256.slice(0, 12)}…`;
  $('#prov').innerHTML =
    `<div>${allOk ? '<span class="ok">✓ DERIVED DATA VERIFIED</span>' : vs.some(([, v]) => v === 'bad') ? '<span class="bad">✗ HASH MISMATCH</span>' : 'verification unavailable'} · ${vs.length} files SHA-256 checked in-browser</div>` +
    `<div style="margin-top:6px">${raw.map(([k, v]) => `${k} · ${new URL(v.url).host} · ${fmtInt(v.bytes)} B<br><span style="color:#3d5560">${v.sha256.slice(0, 32)}…</span>`).join('<br>')}<br>+ ${nH} JPL Horizons flyby ephemerides</div>` +
    `<div style="margin-top:6px">${m.errors.length ? `<span class="bad">${m.errors.length} fetch errors</span>` : '<span class="ok">0 fetch errors</span>'} · fetched ${raw[0] ? raw[0][1].fetched_utc : ''}</div>`;
}

function showMethod() {
  const c = $('#card'); c.style.display = 'block';
  c.innerHTML = `<div class="row"><div class="nm">Modelled population</div><span class="sp"></span><button id="cx">✕</button></div>
  <div class="note" style="font-size:11px;color:var(--fg)">The violet haze is <b>not real objects</b>. It is a statistical stand-in for near-Earth asteroids the surveys have not found yet, so you can see the gap between the catalogue and the sky.</div>
  <div class="kv"><div>Size model</div><div>log-linear N(&lt;H) between published anchors: ${POP_MODEL.anchors.map(a => `H ${a[0]} → ${fmtInt(a[1])}`).join('; ')}; extrapolated to H ${POP_MODEL.hMax}</div>
  <div>Orbits</div><div>resampled from known H &lt; 20 orbits, jittered; random node, perihelion and phase</div>
  <div>Generated</div><div>${fmtInt(POP.count)} objects (seed ${POP_MODEL.seed})</div></div>
  <div class="note">Illustrative, not predictive: real undiscovered objects favour poor viewing geometry. Beyond H 22 treat as order of magnitude.</div>
  <div class="note">${POP_MODEL.refs.map(r => `<a href="${r[1]}" target="_blank" rel="noopener">${r[0]}</a>`).join('<br>')}</div>`;
  $('#cx').onclick = () => select(null);
}

// ---------- Yield & Exposure ----------
// Impact energy if the object hit Earth: sphere of rock (2,600 kg/m³), impact speed from the
// encounter speed v∞ plus Earth's escape speed (11.19 km/s); 17 km/s typical if v∞ unknown.
function impactYield(Dkm, vinf) {
  if (Dkm == null) return null;
  const v = vinf != null ? Math.sqrt(vinf * vinf + 11.19 * 11.19) : 17;
  const m = 2600 * Math.PI / 6 * Math.pow(Dkm * 1000, 3);
  const mt = 0.5 * m * Math.pow(v * 1000, 2) / 4.184e15;
  const cls = Dkm < 0.03 ? 'mostly burns up — airburst' : Dkm < 0.14 ? 'local / city scale' : Dkm < 1 ? 'regional scale' : 'global effects';
  const e = mt >= 1 ? `${mt >= 100 ? Math.round(mt).toLocaleString('en-GB') : mt.toFixed(1)} Mt TNT` : `${Math.max(0.1, mt * 1000).toFixed(mt * 1000 < 10 ? 1 : 0)} kt TNT`;
  return { text: e, cls, v };
}
const yieldRow = (Dkm, vinf) => { const y = impactYield(Dkm, vinf); return y ? `<div>If it hit Earth</div><div>~${y.text} <span class="n">(${y.cls}; ${y.v.toFixed(1)} km/s)</span></div>` : ''; };
function nextApproach(des) { const now = state.jd; return CAD.find(c => c.des === des && c.jd >= now - 0.5); }

// ---------- selection & info card ----------
let selLine = null;
function select(s) {
  state.sel = s;
  neoMat.uniforms.uSel.value = s && s.type === 'neo' ? s.k : -1;
  if (SATS) SATS.mat.uniforms.uSel.value = s && s.type === 'sat' ? s.k : -1;
  if (selLine) { selLine.parent.remove(selLine); selLine.geometry.dispose(); selLine = null; }
  TRACKS.forEach((t, i) => { t.line.material.opacity = s && s.type === 'track' && s.k === i ? 1 : (t.dmin < LD ? 0.9 : 0.6); t.line.material.color.set(s && s.type === 'track' && s.k === i ? 0x5ef0ff : (t.dmin < LD ? 0xff6a3d : 0xffb020)); });
  const c = $('#card');
  if (!s) { c.style.display = 'none'; return; }
  if (s.type === 'neo') { selLine = orbitLine(s.k); helio.add(selLine); }
  if (s.type === 'sat') {
    const rec = SATS.recs[s.k], P = 2 * Math.PI / rec.no; const pts = []; const d0 = jdToDate(state.jd);
    for (let m = 0; m <= 200; m++) { const pv = SAT.propagate(rec, new Date(d0.getTime() + m / 200 * P * 60000)); if (pv && pv.position && typeof pv.position === 'object') pts.push(pv.position.x / AU, pv.position.y / AU, pv.position.z / AU); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    selLine = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.7 })); eq.add(selLine);
  }
  c.style.display = 'block'; renderCard();
}
function integrityVerdict(U, arc) {
  if (U == null || U < 0) return ['UNRATED', '#888'];
  if (U <= 2) return ['WELL DETERMINED', '#39d98a'];
  if (U <= 5) return ['MODERATE UNCERTAINTY', '#ffd040'];
  return [arc != null && arc < 30 ? 'POORLY CONSTRAINED · SHORT ARC' : 'POORLY CONSTRAINED', '#ff3b3b'];
}
function geoDistNow(k) {
  const p = neoHelio(k, state.jd), e = state.earthHelio; return Math.hypot(p[0] - e[0], p[1] - e[1], p[2] - e[2]);
}
function renderCard() {
  const s = state.sel, c = $('#card'); if (!s) return;
  if (s.type === 'neo') {
    const k = s.k, a = NEO.a[k], e = NEO.e[k];
    const cls = ['—', 'Aten', 'Apollo', 'Amor', 'Atira', 'Jupiter-family comet', 'Halley-type comet', 'Encke-type comet', 'Chiron-type / other comet', 'Parabolic'][NEO.cls[k]] || '—';
    const [v, vc] = integrityVerdict(NEO.U[k], NEO.arc[k]);
    const sen = NEO.sen[k] ? SENTRY.find(x => x.des === NEO.pdes[k]) : null;
    c.innerHTML = `<div class="row"><div class="nm">${NEO.name[k]}</div><span class="sp"></span><button id="cx">✕</button></div>
      <div>${NEO.pha[k] ? '<span class="tag" style="color:#ff4d4d">PHA</span>' : ''}${sen ? '<span class="tag" style="color:#ffb020">SENTRY</span>' : ''}<span class="tag" style="color:${vc}">${v}</span></div>
      <div class="kv">
        <div>Class</div><div>${cls}</div>
        <div>Abs. magnitude H</div><div>${fmt(NEO.H[k], 2)}</div>
        <div>Size</div><div>${sizeStr(NEO.D[k], NEO.H[k])}${NEO.D[k] == null ? ' (from H, pv 0.14)' : ''}</div>
        <div>a · e · i</div><div>${fmt(a, 3)} au · ${fmt(e, 3)} · ${fmt(NEO.i[k], 1)}°</div>
        <div>q / Q</div><div>${fmt(a * (1 - e), 3)} / ${fmt(a * (1 + e), 3)} au</div>
        <div>Period</div><div>${fmt(365.25 * Math.pow(a, 1.5) / 365.25, 2)} yr</div>
        <div>Earth MOID</div><div>${NEO.moid[k] != null ? `${fmt(NEO.moid[k], 5)} au · ${ldStr(NEO.moid[k])}` : '—'}</div>
        <div>Now from Earth</div><div>${fmt(geoDistNow(k), 3)} au <span class="n">(2-body)</span></div>
        <div>Uncertainty U</div><div>${NEO.U[k] >= 0 ? NEO.U[k] : '—'} / 9</div>
        <div>Obs. arc · n</div><div>${NEO.arc[k] != null ? fmtInt(NEO.arc[k]) + ' d' : '—'} · ${NEO.nobs[k] ?? '—'}</div>
        <div>Last observed</div><div>${NEO.last[k] || '—'}</div>
        ${sen ? `<div>Impact prob.</div><div style="color:#ffb020">${sen.ip.toExponential(2)} · PS ${sen.ps} · TS ${sen.ts}</div><div>Window</div><div>${sen.range} (${sen.n} VIs)</div>` : ''}
      </div>
      <h2>Yield &amp; exposure</h2>
      <div class="kv" style="margin-top:0">
        ${yieldRow(NEO.D[k] ?? (NEO.H[k] != null && NEO.kind[k] === 'a' ? diamKm(NEO.H[k]) : null), sen ? sen.vi : (nextApproach(NEO.pdes[k]) || {}).vi)}
        <div>Next close pass</div><div>${(() => { const c = nextApproach(NEO.pdes[k]); return c ? `${jdToDate(c.jd).toISOString().slice(0, 10)} · ${ldStr(c.dist)}` : 'none within 0.2 au in the next 12 months'; })()}</div>
      </div>
      <div class="note"><a href="https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=${encodeURIComponent(NEO.pdes[k])}" target="_blank" rel="noopener">Open in JPL SBDB ↗</a></div>`;
  } else if (s.type === 'sat') {
    const rec = SATS.recs[s.k], nrev = rec.no * 1440 / (2 * Math.PI);
    const p = SATS.pos.subarray(s.k * 3, s.k * 3 + 3); const r = Math.hypot(p[0], p[1], p[2]) * AU;
    c.innerHTML = `<div class="row"><div class="nm">${SATS.names[s.k]}</div><span class="sp"></span><button id="cx">✕</button></div>
      <div class="kv"><div>NORAD ID</div><div>${rec.satnum}</div><div>Group</div><div>${['active', 'COSMOS 1408 debris', 'COSMOS 2251 debris', 'FENGYUN 1C debris', 'IRIDIUM 33 debris'][SATS.grp[s.k]] || '—'}</div>
      <div>Altitude</div><div>${fmtInt(Math.round(r - 6378))} km</div><div>Period</div><div>${fmt(1440 / nrev, 1)} min</div>
      <div>Inclination</div><div>${fmt(rec.inclo / D2R, 2)}°</div><div>Eccentricity</div><div>${fmt(rec.ecco, 4)}</div></div>
      <div class="note">SGP4 propagation of CelesTrak GP elements.</div>`;
  } else if (s.type === 'track') {
    const t = TRACKS[s.k]; const p = trackPos(t, state.jd);
    const ca = CAD.find(c => c.des === t.des && Math.abs(c.jd - t.jdca) < 2);
    c.innerHTML = `<div class="row"><div class="nm">${ca ? ca.name : t.des}</div><span class="sp"></span><button id="cx">✕</button></div>
      <div><span class="tag" style="color:#ff6a3d">FLYBY</span><span class="tag" style="color:#5ef0ff">JPL HORIZONS</span></div>
      <div class="kv"><div>Closest approach</div><div>${jdToDate(t.jdca).toISOString().slice(0, 16).replace('T', ' ')} UTC</div>
      <div>Miss distance</div><div>${ldStr(t.dmin)} · ${fmtInt(Math.round(t.dmin * AU))} km</div>
      ${ca ? `<div>3σ range</div><div>${fmtInt(Math.round(ca.dmin * AU))}–${fmtInt(Math.round(ca.dmax * AU))} km</div><div>Rel. velocity</div><div>${fmt(ca.v, 2)} km/s</div><div>Size</div><div>${sizeStr(ca.D, ca.h)}</div><div>CA time σ</div><div>${ca.ts}</div>${yieldRow(ca.D ?? (ca.h != null ? diamKm(ca.h) : null), ca.vi)}` : ''}
      <div>Now from Earth</div><div>${p ? ldStr(Math.hypot(...p)) : 'outside ±5 d window'}</div></div>
      <div class="note">Track: geocentric ecliptic state vectors, 1 h step, ±5 d around CA. SHA-256 ${t.sha256 ? t.sha256.slice(0, 16) + '…' : '—'}</div>`;
  }
  const x = $('#cx'); if (x) x.onclick = () => select(null);
}

// ---------- picking & hover ----------
// Near Earth only satellites/flybys are candidates (asteroids are millions of km away); anything
// hidden behind the globe is ignored; empty-space clicks clear the selection.
function earthWorld() { const v = new THREE.Vector3(); geo.getWorldPosition(v); return v; }
function occluded(P, C, E) {
  const d = P.clone().sub(C), L = d.length(); d.divideScalar(L);
  const tca = E.clone().sub(C).dot(d); if (tca < 0) return false;
  const d2 = E.distanceToSquared(C) - tca * tca, R2 = (RE * 0.999) ** 2; if (d2 > R2) return false;
  return tca - Math.sqrt(R2 - d2) < L;
}
function findAt(px, py, radius) {
  camera.updateMatrixWorld(); root.updateMatrixWorld();
  const v = new THREE.Vector3(), C = camera.position, E = earthWorld();
  const camDist = C.distanceTo(controls.target), near = camDist < 0.02;
  let best = null, bd = radius;
  const test = (W, obj) => {
    v.copy(W).project(camera); if (v.z > 1 || v.z < -1) return;
    const d = Math.hypot((v.x + 1) / 2 * innerWidth - px, (1 - v.y) / 2 * innerHeight - py);
    if (d < bd && !(near && occluded(W, C, E))) { bd = d; best = obj; }
  };
  const O = state.origin, w = new THREE.Vector3();
  if (!near && (state.layers.known || state.layers.comets)) for (let k = 0; k < NEO.n; k++) {
    const com = NEO.kind[k] === 'c'; if (com ? !state.layers.comets : !state.layers.known) continue;
    if (state.layers.sentryOnly && !NEO.sen[k]) continue;
    const p = neoHelio(k, state.jd); test(toW([p[0] - O[0], p[1] - O[1], p[2] - O[2]]), { type: 'neo', k });
  }
  if (state.layers.tracks) TRACKS.forEach((t, i) => { const p = trackPos(t, state.jd); if (p) test(geo.localToWorld(w.set(p[0], p[1], p[2])).clone(), { type: 'track', k: i }); });
  if (SATS && camDist < 0.05 && (state.layers.sats || state.layers.debris)) {
    const m = eq.matrixWorld;
    for (let i = 0; i < SATS.N; i++) {
      if (SATS.isDeb[i] ? !state.layers.debris : !state.layers.sats) continue;
      if (SATS.pos[i * 3] > 100) continue;
      test(w.set(SATS.pos[i * 3], SATS.pos[i * 3 + 1], SATS.pos[i * 3 + 2]).applyMatrix4(m).clone(), { type: 'sat', k: i });
    }
  }
  return best;
}
function nameOf(o) { return !o ? '' : o.type === 'neo' ? NEO.name[o.k] : o.type === 'sat' ? SATS.names[o.k] : TRACKS[o.k].des + ' (flyby)'; }
let downAt = null, hoverT = 0;
const tip = document.createElement('div'); tip.id = 'hovertip'; document.body.appendChild(tip);
canvas.addEventListener('pointerdown', (e) => downAt = [e.clientX, e.clientY]);
canvas.addEventListener('pointerup', (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4) return;
  const hit = findAt(e.clientX, e.clientY, e.pointerType === 'touch' ? 22 : 11);
  select(hit);
});
canvas.addEventListener('pointermove', (e) => {
  if (e.buttons || !NEO) return; const now = performance.now(); if (now - hoverT < 90) return; hoverT = now;
  const hit = findAt(e.clientX, e.clientY, 11);
  if (SATS) SATS.mat.uniforms.uHov.value = hit && hit.type === 'sat' ? hit.k : -1;
  canvas.style.cursor = hit ? 'pointer' : 'grab';
  if (hit) { tip.textContent = nameOf(hit); tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; tip.style.display = 'block'; }
  else tip.style.display = 'none';
});
canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; });

// ---------- satellite names + motion trails when close to Earth ----------
const trailGeom = new THREE.BufferGeometry();
const trails = new THREE.LineSegments(trailGeom, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
trails.frustumCulled = false; eq.add(trails);
const FAMOUS = [/^ISS \(ZARYA\)/, /^CSS \(TIANHE\)/, /^HST$/, /^TIANGONG/];
function refreshSatLabels() {
  state.satLabels = [];
  if (!SATS || !state.layers.labels) { trailGeom.setDrawRange(0, 0); return; }
  const camDist = camera.position.distanceTo(controls.target);
  if (camDist > 0.004) { trailGeom.setDrawRange(0, 0); return; }
  camera.updateMatrixWorld(); root.updateMatrixWorld();
  const m = eq.matrixWorld, C = camera.position, E = earthWorld(), w = new THREE.Vector3(), v = new THREE.Vector3();
  const cand = [];
  for (let i = 0; i < SATS.N; i++) {
    if (SATS.isDeb[i] ? !state.layers.debris : !state.layers.sats) continue;
    if (SATS.pos[i * 3] > 100) continue;
    w.set(SATS.pos[i * 3], SATS.pos[i * 3 + 1], SATS.pos[i * 3 + 2]).applyMatrix4(m);
    v.copy(w).project(camera); if (v.z > 1 || Math.abs(v.x) > 0.92 || Math.abs(v.y) > 0.9) continue;
    if (occluded(w, C, E)) continue;
    const sx = (v.x + 1) / 2 * innerWidth, sy = (1 - v.y) / 2 * innerHeight;
    const fam = FAMOUS.some(r => r.test(SATS.names[i]));
    cand.push({ i, sx, sy, score: fam ? -1e9 : Math.hypot(v.x, v.y * 1.4) + (SATS.isDeb[i] ? 0.5 : 0) + (/ DEB| R\/B/.test(SATS.names[i]) ? 0.3 : 0) + (/^STARLINK|^ONEWEB/.test(SATS.names[i]) ? 0.35 : 0) });
  }
  cand.sort((a, b) => a.score - b.score);
  const chosen = [];
  for (const c of cand) {
    if (chosen.length >= 12) break;
    if (chosen.some(o => Math.abs(o.sx - c.sx) < 170 && Math.abs(o.sy - c.sy) < 30)) continue;
    chosen.push(c);
  }
  state.satLabels = chosen.map(c => c.i);
  // trails: last ~1/10 of an orbit, fading out
  const list = [...state.satLabels]; if (state.sel && state.sel.type === 'sat' && !list.includes(state.sel.k)) list.push(state.sel.k);
  const pos = [], col = [], t0 = jdToDate(state.jd).getTime(), N = 24;
  for (const i of list) {
    const rec = SATS.recs[i], P = 2 * Math.PI / rec.no * 60000, span = P / 36;
    let prev = null;
    for (let k = 0; k <= N; k++) {
      let pv = null; try { pv = SAT.propagate(rec, new Date(t0 - span * k / N)); } catch { }
      const p = pv && pv.position; if (!p || typeof p !== 'object' || !isFinite(p.x)) { prev = null; continue; }
      const cur = [p.x / AU, p.y / AU, p.z / AU];
      if (prev) { pos.push(...prev, ...cur); const a = 1 - (k - 1) / N, b = 1 - k / N; col.push(0.37 * a, 0.94 * a, a, 0.37 * b, 0.94 * b, b); }
      prev = cur;
    }
  }
  trailGeom.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  trailGeom.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  trailGeom.setDrawRange(0, pos.length / 3);
}

// ---------- camera ----------
const VIEWS = { leo: 0.00085, cis: 0.011, near: 0.28, inner: 4.2 };
let fly = null;
function flyTo(name) {
  const d1 = VIEWS[name]; if (!d1) return;
  if (name === 'inner' && state.frame === 'geo') { /* keep Earth-centred: the Sun will circle */ }
  const dir = camera.position.clone().sub(controls.target).normalize();
  if (dir.lengthSq() < 0.5) dir.set(0.3, -0.85, 0.42).normalize();
  if (name === 'inner' || name === 'near') dir.lerp(new THREE.Vector3(0.15, -0.55, 0.82).normalize(), 0.6).normalize();
  fly = { t0: performance.now(), d0: camera.position.distanceTo(controls.target), d1, dir0: dir.clone(), dir1: dir };
}
function setFrame(f) {
  state.frame = f;
  if (f === 'helio' && camera.position.length() < 1) flyTo('inner');
  if (f === 'geo' && camera.position.length() > 2) flyTo('near');
}

// ---------- timeline ----------
let TL0 = 0, TL1 = 0;
function drawTimeline() {
  const tl = $('#tl'); const w = tl.clientWidth, h = tl.clientHeight; const dpr = Math.min(devicePixelRatio, 2);
  if (tl.width !== w * dpr) { tl.width = w * dpr; tl.height = h * dpr; }
  const g = tl.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
  const now = jdNow(); TL0 = now - 30; TL1 = now + 365;
  const X = (jd) => (jd - TL0) / (TL1 - TL0) * w;
  g.strokeStyle = 'rgba(120,220,255,.15)'; g.beginPath(); g.moveTo(0, h - 12.5); g.lineTo(w, h - 12.5); g.stroke();
  g.font = '9px JetBrains Mono, monospace'; g.fillStyle = '#56707b';
  const d0 = jdToDate(TL0);
  for (let m = 0; m < 14; m++) {
    const d = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth() + m, 1)); const jd = d.getTime() / 86400000 + 2440587.5;
    if (jd < TL0 || jd > TL1) continue; const x = X(jd);
    g.fillRect(x, h - 16, 1, 7); g.fillText(d.toUTCString().slice(8, 11).toUpperCase() + (d.getUTCMonth() === 0 ? ' ' + d.getUTCFullYear() : ''), x + 3, h - 2);
  }
  for (const c of CAD) {
    if (c.jd < TL0 || c.jd > TL1) continue; const ld = c.dist / LD;
    const hh = Math.max(3, Math.min(30, 30 - Math.log10(ld + 0.05) * 12));
    g.fillStyle = ld < 1 ? '#ff4d4d' : ld < 5 ? '#ffb020' : 'rgba(120,220,255,.35)';
    g.fillRect(X(c.jd), h - 13 - hh, 1.2, hh);
  }
  g.fillStyle = 'rgba(255,255,255,.5)'; g.fillRect(X(now), 0, 1, h - 12);
  g.fillStyle = '#5ef0ff'; const xs = X(state.jd); g.fillRect(xs - 1, 0, 2, h - 12);
  g.beginPath(); g.moveTo(xs - 5, 0); g.lineTo(xs + 5, 0); g.lineTo(xs, 6); g.fill();
}

function applyLayers() {
  const L = state.layers, u = neoMat.uniforms;
  u.uShowKnown.value = L.known ? 1 : 0; u.uShowComets.value = L.comets ? 1 : 0; u.uShowModel.value = L.model ? 1 : 0; u.uSentryOnly.value = L.sentryOnly ? 1 : 0;
  if (SATS) { SATS.mat.uniforms.uShowA.value = L.sats ? 1 : 0; SATS.mat.uniforms.uShowD.value = L.debris ? 1 : 0; }
  trackGroup.visible = L.tracks && !state.closeUp; if (trackMarkers) trackMarkers.visible = L.tracks;
  orbitGroup.visible = L.orbits; if (state.moonOrbit) state.moonOrbit.visible = L.orbits; if (state.geoRing) state.geoRing.visible = L.orbits;
  labelRoot.style.display = L.labels ? '' : 'none';
}

// ---------- main loop ----------
let last = performance.now(), lastUI = 0;
state.origin = [0, 0, 0]; state.earthHelio = [1, 0, 0];
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  if (state.live) state.jd = jdNow(); else state.jd += dt * state.speed / 86400;
  const date = jdToDate(state.jd), at = Astronomy.MakeTime(date);
  const E = helioOf('Earth', at); state.earthHelio = E;
  const O = state.frame === 'geo' ? E : [0, 0, 0]; state.origin = O;
  helio.position.set(-O[0], -O[1], -O[2]);
  geo.position.set(E[0] - O[0], E[1] - O[1], E[2] - O[2]);
  spin.rotation.z = SAT.gstime(date);
  const Mo = eclVec(Astronomy.GeoMoon(at)); moon.position.set(...Mo);
  // markers
  const pw = {};
  for (let i = 0; i < BODIES.length; i++) {
    const [name, body] = BODIES[i]; let p;
    if (name === 'Sun') p = [-O[0], -O[1], -O[2]];
    else if (name === 'Earth') p = [E[0] - O[0], E[1] - O[1], E[2] - O[2]];
    else if (name === 'Moon') p = [E[0] - O[0] + Mo[0], E[1] - O[1] + Mo[1], E[2] - O[2] + Mo[2]];
    else { const h = helioOf(body, at); p = [h[0] - O[0], h[1] - O[1], h[2] - O[2]]; }
    bodyPos.set(p, i * 3); pw[name] = p;
  }
  bodyGeom.attributes.position.needsUpdate = true;
  const camDist = camera.position.distanceTo(controls.target);
  // north-up near Earth, ecliptic-flat far away (smooth in between)
  const tl = Math.min(1, Math.max(0, (Math.log10(camDist) - Math.log10(0.08)) / (Math.log10(0.006) - Math.log10(0.08))));
  root.rotation.x = OBL * tl * tl * (3 - 2 * tl);
  if (SATS) SATS.mat.uniforms.uIcon.value = camDist < 0.0025 ? 1 : 0;
  const cu = camDist < 0.0022; if (cu !== state.closeUp) { state.closeUp = cu; applyLayers(); }
  if (now - (state.lblT || 0) > 400) { state.lblT = now; refreshSatLabels(); }
  bodyPts.material.size = camDist < 0.02 ? 0 : 7;
  earthGlow.material.opacity = camDist > 0.02 ? 0.8 : 0;
  sunLight.position.set(...pw.Sun); sunLight.target.position.set(...pw.Earth);
  // NEOs
  neoMat.uniforms.uT.value = state.jd - REF_JD;
  neoMat.uniforms.uOrigin.value.set(...O);
  // satellites: refresh a slice every frame (full catalogue every few frames)
  propagateSats(date, Math.abs(state.speed) > 600 ? 20000 : 5000);
  // flyby markers
  const lbs = [];
  if (trackMarkers) {
    const tp = trackMarkers.geometry.attributes.position.array;
    TRACKS.forEach((t, i) => {
      const p = trackPos(t, state.jd);
      if (p) { tp.set(p, i * 3); const d = Math.hypot(...p); if (state.layers.tracks && d < 0.03 && camDist < 0.2 && camDist > 0.0025) lbs.push({ p: [pw.Earth[0] + p[0], pw.Earth[1] + p[1], pw.Earth[2] + p[2]], t: `${t.des} · ${ldStr(d)}`, c: 'trk', d }); }
      else tp.set([1e3, 1e3, 1e3], i * 3);
    });
    trackMarkers.geometry.attributes.position.needsUpdate = true;
  }
  lbs.sort((a, b) => a.d - b.d); lbs.length = Math.min(lbs.length, 8);
  // fly animation
  if (fly) {
    const u = Math.min(1, (now - fly.t0) / 1400), s = u * u * (3 - 2 * u);
    const d = Math.exp(Math.log(fly.d0) + (Math.log(fly.d1) - Math.log(fly.d0)) * s);
    camera.position.copy(controls.target).addScaledVector(fly.dir0.clone().lerp(fly.dir1, s).normalize(), d);
    if (u >= 1) fly = null;
  }
  controls.update();
  // labels
  if (state.layers.labels) {
    for (const [name] of BODIES) {
      if ((name === 'Earth' && camDist < 0.0025) || (name === 'Moon' && camDist > 1.5)) continue;
      if (camDist < 0.0025 && name !== 'Moon') continue;
      lbs.push({ p: pw[name], t: name.toUpperCase(), c: 'body' });
    }
    if (SATS && state.satLabels) for (const i of state.satLabels) {
      if (state.sel && state.sel.type === 'sat' && state.sel.k === i) continue;
      const w = new THREE.Vector3(SATS.pos[i * 3], SATS.pos[i * 3 + 1], SATS.pos[i * 3 + 2]).applyMatrix4(eq.matrixWorld);
      const nm = SATS.names[i].replace(/^ISS \(ZARYA\)/, 'ISS · Space Station').replace(/^CSS \(TIANHE\)/, 'Tiangong · Space Station');
      lbs.push({ w, t: nm, c: SATS.isDeb[i] ? 'deb' : 'sat' });
    }
    const s = state.sel;
    if (s && s.type === 'neo') { const p = neoHelio(s.k, state.jd); lbs.push({ p: [p[0] - O[0], p[1] - O[1], p[2] - O[2]], t: NEO.name[s.k], c: 'sel' }); }
    if (s && s.type === 'sat') { const w = new THREE.Vector3(SATS.pos[s.k * 3], SATS.pos[s.k * 3 + 1], SATS.pos[s.k * 3 + 2]).applyMatrix4(eq.matrixWorld); lbs.push({ w, t: SATS.names[s.k], c: 'sel' }); }
  }
  renderer.render(scene, camera);
  setLabels(lbs);
  if (now - lastUI > 200) {
    lastUI = now;
    $('#clock').textContent = new Date().toISOString().slice(0, 19).replace('T', ' ');
    $('#simtime').textContent = date.toISOString().slice(0, 19).replace('T', ' ');
    drawTimeline();
    if (state.sel && state.sel.type !== 'neo') renderCard();
  }
  requestAnimationFrame(frame);
}

addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

// ---------- boot ----------
(async function boot() {
  try {
    MANIFEST = await (await fetch('data/manifest.json')).json();
    const [neo, sats, cad, sentry, tracks, land] = await Promise.all(['neo.json', 'sats.json', 'cad.json', 'sentry.json', 'tracks.json', 'land.json'].map(n => load(n, MANIFEST)));
    $('#bootmsg').textContent = 'PROPAGATING ORBITS…';
    await new Promise(r => setTimeout(r, 20));
    CAD = cad; SENTRY = sentry;
    paintEarth(land);
    buildNEO(neo); buildSats(sats); buildTracks(tracks); buildPlanetOrbits();
    propagateSats(jdToDate(state.jd), 1e6);
    buildUI(); applyLayers();
    const h = location.hash.slice(1);
    if (h === 'inner') { clickFrame('helio'); }
    flyTo(VIEWS[h] ? h : 'cis');
    $('#boot').style.display = 'none';
    window.__neo = { THREE, earth, sunLight, earthMat, camera, controls, state, flyTo, select, clickFrame, TRACKS, NEO, POP, SATS, verify };
    requestAnimationFrame((t) => { last = t; frame(t); });
  } catch (err) {
    console.error(err); $('#bootmsg').textContent = 'BOOT FAILED: ' + err.message;
  }
})();
