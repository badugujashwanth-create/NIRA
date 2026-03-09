import * as THREE from "https://unpkg.com/three@0.183.2/build/three.module.js";

const container = document.getElementById("scene-root");

const renderer = new THREE.WebGLRenderer({
  antialias: true,
  alpha: true,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8));
renderer.setSize(window.innerWidth, window.innerHeight);
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.1, 200);
camera.position.set(0, 1.8, 15);

const pointer = new THREE.Vector2(0, 0);
const smoothPointer = new THREE.Vector2(0, 0);
let hoverActive = false;
let energyPulse = 0;

const avatarGroup = new THREE.Group();
scene.add(avatarGroup);

const glowTexture = createGlowTexture();

// Deep-space atmosphere layers.
const stars = createStars(glowTexture);
const driftingField = createDriftingField(glowTexture);
const nebula = createNebula();
scene.add(stars);
scene.add(driftingField);
scene.add(nebula);

// Core avatar parts.
const bodySystem = createBodyParticles(glowTexture);
const hairSystem = createHairParticles(glowTexture);
const dressSystem = createDressParticles(glowTexture);
const haloSystem = createHalo();
const eyeSystem = createEyes(glowTexture);
const chestSymbol = createChestSymbol();

avatarGroup.add(bodySystem.points);
avatarGroup.add(hairSystem.points);
avatarGroup.add(dressSystem.points);
avatarGroup.add(haloSystem.group);
avatarGroup.add(eyeSystem.group);
avatarGroup.add(chestSymbol);

const ambientLight = new THREE.AmbientLight(0xa9d7ff, 0.6);
const keyLight = new THREE.PointLight(0x9fe6ff, 2.1, 40, 2);
keyLight.position.set(5, 7, 9);
const fillLight = new THREE.PointLight(0x5588ff, 0.7, 30, 2);
fillLight.position.set(-6, 1, -10);
scene.add(ambientLight, keyLight, fillLight);

window.addEventListener("resize", onResize);
window.addEventListener("mousemove", onPointerMove);
window.addEventListener("mouseenter", () => {
  hoverActive = true;
});
window.addEventListener("mouseleave", () => {
  hoverActive = false;
});
window.addEventListener("click", () => {
  energyPulse = 1;
});

animate();

function animate() {
  requestAnimationFrame(animate);
  const time = performance.now() * 0.001;

  smoothPointer.x += (pointer.x - smoothPointer.x) * 0.045;
  smoothPointer.y += (pointer.y - smoothPointer.y) * 0.045;
  energyPulse *= 0.96;

  avatarGroup.rotation.y += ((smoothPointer.x * 0.34) - avatarGroup.rotation.y) * 0.03;
  avatarGroup.rotation.x += ((-smoothPointer.y * 0.12) - avatarGroup.rotation.x) * 0.03;
  avatarGroup.position.y = Math.sin(time * 0.55) * 0.2;

  bodySystem.update(time, smoothPointer, hoverActive, energyPulse);
  hairSystem.update(time, smoothPointer, hoverActive, energyPulse);
  dressSystem.update(time, hoverActive, energyPulse);
  haloSystem.update(time, hoverActive, energyPulse);
  eyeSystem.update(time, hoverActive, energyPulse);

  stars.rotation.y += 0.00025;
  driftingField.rotation.y -= 0.0004;
  driftingField.position.y = Math.sin(time * 0.18) * 0.25;
  nebula.rotation.z += 0.0004;
  chestSymbol.rotation.y += 0.012;
  chestSymbol.rotation.z = Math.sin(time * 0.7) * 0.16;
  chestSymbol.material.opacity = 0.7 + Math.sin(time * 2.2) * 0.15 + energyPulse * 0.12;
  chestSymbol.scale.setScalar(1 + energyPulse * 0.2);

  renderer.render(scene, camera);
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function onPointerMove(event) {
  pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
  pointer.y = (event.clientY / window.innerHeight) * 2 - 1;
}

function createStars(texture) {
  const count = 2600;
  const positions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const geometry = new THREE.BufferGeometry();

  for (let i = 0; i < count; i += 1) {
    const r = 38 + Math.random() * 52;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const cursor = i * 3;
    positions[cursor] = r * Math.sin(phi) * Math.cos(theta);
    positions[cursor + 1] = r * Math.cos(phi);
    positions[cursor + 2] = r * Math.sin(phi) * Math.sin(theta);
    sizes[i] = 0.8 + Math.random() * 1.7;
  }

  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));

  const material = new THREE.PointsMaterial({
    map: texture,
    size: 0.14,
    color: 0xbadfff,
    transparent: true,
    opacity: 0.65,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  return new THREE.Points(geometry, material);
}

function createDriftingField(texture) {
  const count = 1600;
  const positions = new Float32Array(count * 3);
  const geometry = new THREE.BufferGeometry();

  for (let i = 0; i < count; i += 1) {
    const cursor = i * 3;
    positions[cursor] = (Math.random() - 0.5) * 60;
    positions[cursor + 1] = (Math.random() - 0.5) * 34;
    positions[cursor + 2] = -12 - Math.random() * 28;
  }

  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

  const material = new THREE.PointsMaterial({
    map: texture,
    size: 0.18,
    color: 0x94d7ff,
    transparent: true,
    opacity: 0.18,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  return new THREE.Points(geometry, material);
}

function createNebula() {
  const group = new THREE.Group();

  for (const config of [
    { x: -4.8, y: 2.2, scale: 15, color: 0x4477ff, opacity: 0.08 },
    { x: 3.8, y: 0.8, scale: 13, color: 0x7de4ff, opacity: 0.07 },
    { x: 0.5, y: -3.1, scale: 18, color: 0x4a4dff, opacity: 0.06 },
  ]) {
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glowTexture,
        color: config.color,
        transparent: true,
        opacity: config.opacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    sprite.position.set(config.x, config.y, -14);
    sprite.scale.set(config.scale, config.scale * 0.8, 1);
    group.add(sprite);
  }

  return group;
}

function createBodyParticles(texture) {
  // Thousands of points are distributed into head, torso, arms, and lower silhouette
  // to create a feminine humanoid form with a soft cosmic distortion.
  const count = 7200;
  const base = new Float32Array(count * 3);
  const live = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const phases = new Float32Array(count);
  const geometry = new THREE.BufferGeometry();

  for (let i = 0; i < count; i += 1) {
    const point = sampleAvatarPoint();
    const cursor = i * 3;
    base[cursor] = point.x;
    base[cursor + 1] = point.y;
    base[cursor + 2] = point.z;
    live[cursor] = point.x;
    live[cursor + 1] = point.y;
    live[cursor + 2] = point.z;
    phases[i] = Math.random() * Math.PI * 2;

    const tint = 0.8 + Math.random() * 0.2;
    colors[cursor] = 0.56 * tint;
    colors[cursor + 1] = 0.82 * tint;
    colors[cursor + 2] = 1.0;
  }

  geometry.setAttribute("position", new THREE.BufferAttribute(live, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    map: texture,
    size: 0.12,
    vertexColors: true,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);

  function update(time, pointerValue, hovered, pulse) {
    const glowBoost = hovered ? 0.18 : 0;
    material.opacity = 0.88 + glowBoost * 0.5 + pulse * 0.08;
    material.size = 0.12 + glowBoost * 0.03 + pulse * 0.04;

    for (let i = 0; i < count; i += 1) {
      const cursor = i * 3;
      const x = base[cursor];
      const y = base[cursor + 1];
      const z = base[cursor + 2];
      const phase = phases[i];
      const ripple = Math.sin(time * 1.4 + phase + y * 0.8) * 0.025;
      const swirl = Math.cos(time * 0.9 + phase + z * 2.0) * 0.03;

      live[cursor] = x + ripple + x * pulse * 0.09 + pointerValue.x * 0.08 * (0.2 + y * 0.08);
      live[cursor + 1] = y + Math.sin(time * 1.7 + phase) * 0.018 + pulse * 0.06 * Math.max(0, 1 - Math.abs(y) / 5);
      live[cursor + 2] = z + swirl + pointerValue.y * 0.06 + z * pulse * 0.08;
    }

    geometry.attributes.position.needsUpdate = true;
  }

  return { points, update };
}

function createHairParticles(texture) {
  // Hair is represented as warm-toned particle strands that move like zero-gravity plasma.
  const strandCount = 58;
  const particlesPerStrand = 16;
  const count = strandCount * particlesPerStrand;
  const live = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const roots = [];
  const strandPhase = [];
  const geometry = new THREE.BufferGeometry();

  for (let strand = 0; strand < strandCount; strand += 1) {
    const angle = (strand / strandCount) * Math.PI * 2;
    const spread = 0.64 + Math.random() * 0.38;
    roots.push(
      new THREE.Vector3(
        Math.cos(angle) * spread * 0.72,
        2.58 + Math.random() * 0.26,
        Math.sin(angle) * spread * 0.6 - 0.08,
      ),
    );
    strandPhase.push(Math.random() * Math.PI * 2);

    for (let step = 0; step < particlesPerStrand; step += 1) {
      const cursor = (strand * particlesPerStrand + step) * 3;
      colors[cursor] = 0.54 + Math.random() * 0.08;
      colors[cursor + 1] = 0.34 + Math.random() * 0.08;
      colors[cursor + 2] = 0.24 + Math.random() * 0.06;
    }
  }

  geometry.setAttribute("position", new THREE.BufferAttribute(live, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    map: texture,
    size: 0.11,
    vertexColors: true,
    transparent: true,
    opacity: 0.75,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);

  function update(time, pointerValue, hovered, pulse) {
    const shimmer = hovered ? 0.14 : 0;
    material.opacity = 0.7 + shimmer + pulse * 0.08;

    for (let strand = 0; strand < strandCount; strand += 1) {
      const root = roots[strand];
      const phase = strandPhase[strand];

      for (let step = 0; step < particlesPerStrand; step += 1) {
        const t = step / (particlesPerStrand - 1);
        const sway = Math.sin(time * 0.9 + phase + t * 2.4) * 0.18;
        const drift = Math.cos(time * 0.7 + phase * 1.2 + t * 3.2) * 0.16;
        const sparkle = Math.sin(time * 3.0 + phase + t * 6.0) * 0.014;
        const cursor = (strand * particlesPerStrand + step) * 3;

        live[cursor] = root.x + sway * t + pointerValue.x * 0.22 * t + pulse * 0.08 * t;
        live[cursor + 1] = root.y - t * (3.8 + Math.sin(phase) * 0.3) + Math.sin(time * 0.8 + phase + t * 1.8) * 0.08;
        live[cursor + 2] = root.z - drift * t + pointerValue.y * 0.12 * t + sparkle;
      }
    }

    geometry.attributes.position.needsUpdate = true;
  }

  return { points, update };
}

function createDressParticles(texture) {
  // The dress is a conical field of drifting particles that continuously slides down
  // and respawns to keep the silhouette alive without expensive allocations.
  const count = 2600;
  const base = new Float32Array(count * 3);
  const live = new Float32Array(count * 3);
  const speeds = new Float32Array(count);
  const phases = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  const geometry = new THREE.BufferGeometry();

  for (let i = 0; i < count; i += 1) {
    const y = -0.7 - Math.random() * 4.8;
    const radius = 0.25 + ((y + 0.7) * -0.32) + Math.random() * 1.7;
    const angle = Math.random() * Math.PI * 2;
    const cursor = i * 3;

    base[cursor] = Math.cos(angle) * radius * 0.88;
    base[cursor + 1] = y;
    base[cursor + 2] = Math.sin(angle) * radius * 0.58;

    live[cursor] = base[cursor];
    live[cursor + 1] = base[cursor + 1];
    live[cursor + 2] = base[cursor + 2];

    speeds[i] = 0.002 + Math.random() * 0.006;
    phases[i] = Math.random() * Math.PI * 2;

    colors[cursor] = 0.62 + Math.random() * 0.14;
    colors[cursor + 1] = 0.84 + Math.random() * 0.12;
    colors[cursor + 2] = 1.0;
  }

  geometry.setAttribute("position", new THREE.BufferAttribute(live, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    map: texture,
    size: 0.1,
    vertexColors: true,
    transparent: true,
    opacity: 0.5,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  points.position.y = -0.2;

  function update(time, hovered, pulse) {
    material.opacity = 0.46 + (hovered ? 0.12 : 0) + pulse * 0.08;
    material.size = 0.1 + (hovered ? 0.01 : 0) + pulse * 0.03;

    for (let i = 0; i < count; i += 1) {
      const cursor = i * 3;
      live[cursor + 1] -= speeds[i];
      if (live[cursor + 1] < -5.9) {
        live[cursor] = base[cursor];
        live[cursor + 1] = -0.8 - Math.random() * 0.6;
        live[cursor + 2] = base[cursor + 2];
      }
      live[cursor] += Math.sin(time * 0.8 + phases[i]) * 0.0015;
      live[cursor + 2] += Math.cos(time * 0.7 + phases[i]) * 0.0012;
    }

    geometry.attributes.position.needsUpdate = true;
  }

  return { points, update };
}

function createHalo() {
  // The halo combines a ring with faint interface segments for a holographic backplate.
  const group = new THREE.Group();

  const ring = new THREE.Mesh(
    new THREE.RingGeometry(1.6, 1.95, 96),
    new THREE.MeshBasicMaterial({
      color: 0x8dd8ff,
      transparent: true,
      opacity: 0.18,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  ring.position.set(0, 2.55, -0.55);
  group.add(ring);

  const innerRing = new THREE.Mesh(
    new THREE.RingGeometry(1.24, 1.3, 72),
    new THREE.MeshBasicMaterial({
      color: 0xb9efff,
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  innerRing.position.copy(ring.position);
  group.add(innerRing);

  const spokesGeometry = new THREE.BufferGeometry();
  const spokePositions = [];
  for (let i = 0; i < 24; i += 1) {
    const angle = (i / 24) * Math.PI * 2;
    const inner = 1.32;
    const outer = i % 2 === 0 ? 1.92 : 1.78;
    spokePositions.push(Math.cos(angle) * inner, 2.55 + Math.sin(angle) * inner, -0.52);
    spokePositions.push(Math.cos(angle) * outer, 2.55 + Math.sin(angle) * outer, -0.52);
  }
  spokesGeometry.setAttribute("position", new THREE.Float32BufferAttribute(spokePositions, 3));
  const spokes = new THREE.LineSegments(
    spokesGeometry,
    new THREE.LineBasicMaterial({
      color: 0xa6e7ff,
      transparent: true,
      opacity: 0.24,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  group.add(spokes);

  function update(time, hovered, pulse) {
    group.rotation.z += 0.0022;
    ring.material.opacity = 0.18 + (hovered ? 0.06 : 0) + pulse * 0.08;
    innerRing.material.opacity = 0.22 + Math.sin(time * 1.8) * 0.03 + pulse * 0.05;
    spokes.material.opacity = 0.2 + (hovered ? 0.08 : 0) + pulse * 0.06;
  }

  return { group, update };
}

function createEyes(texture) {
  const group = new THREE.Group();

  const eyeMaterial = new THREE.SpriteMaterial({
    map: texture,
    color: 0xdff7ff,
    transparent: true,
    opacity: 0.9,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const leftEye = new THREE.Sprite(eyeMaterial.clone());
  const rightEye = new THREE.Sprite(eyeMaterial.clone());
  leftEye.position.set(-0.18, 2.4, 0.58);
  rightEye.position.set(0.18, 2.4, 0.58);
  leftEye.scale.set(0.26, 0.16, 1);
  rightEye.scale.set(0.26, 0.16, 1);
  group.add(leftEye, rightEye);

  function update(time, hovered, pulse) {
    const eyePulse = 0.78 + Math.sin(time * 2.3) * 0.18 + (hovered ? 0.1 : 0) + pulse * 0.22;
    leftEye.material.opacity = eyePulse;
    rightEye.material.opacity = eyePulse;
    leftEye.scale.set(0.26 + eyePulse * 0.06, 0.16 + eyePulse * 0.04, 1);
    rightEye.scale.set(0.26 + eyePulse * 0.06, 0.16 + eyePulse * 0.04, 1);
  }

  return { group, update };
}

function createChestSymbol() {
  const diamond = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.18, 0),
    new THREE.MeshBasicMaterial({
      color: 0xbfeeff,
      transparent: true,
      opacity: 0.78,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  diamond.position.set(0, 0.9, 0.72);
  return diamond;
}

function sampleAvatarPoint() {
  const part = Math.random();

  if (part < 0.18) {
    return sampleEllipsoid(0, 2.42, 0, 0.62, 0.9, 0.56);
  }
  if (part < 0.58) {
    return sampleEllipsoid(0, 0.85, 0, 1.04, 2.1, 0.72);
  }
  if (part < 0.74) {
    return sampleEllipsoid(Math.random() > 0.5 ? 0.82 : -0.82, 1.04, 0, 0.38, 1.1, 0.44);
  }
  if (part < 0.88) {
    return sampleEllipsoid(Math.random() > 0.5 ? 0.28 : -0.28, -1.1, 0, 0.42, 1.45, 0.3);
  }

  return sampleEllipsoid(0, -2.65, 0, 1.7, 1.18, 0.84);
}

function sampleEllipsoid(cx, cy, cz, rx, ry, rz) {
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  const radius = Math.cbrt(Math.random());
  return {
    x: cx + radius * rx * Math.sin(phi) * Math.cos(theta),
    y: cy + radius * ry * Math.cos(phi),
    z: cz + radius * rz * Math.sin(phi) * Math.sin(theta),
  };
}

function createGlowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.2, "rgba(228,246,255,0.95)");
  gradient.addColorStop(0.42, "rgba(154,220,255,0.5)");
  gradient.addColorStop(1, "rgba(154,220,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(canvas);
}
