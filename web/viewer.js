import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export function mountViewer(container, data) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#f5f5f3");
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100000);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor("#f5f5f3");
  container.replaceChildren(renderer.domElement);
  renderer.domElement.setAttribute(
    "aria-label",
    "Interactive 3D preview of your custom LEGO build",
  );
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 10;
  const group = new THREE.Group();
  scene.add(group);
  const geometries = new Map();
  const materials = new Map();
  for (const [id, mesh] of Object.entries(data.meshes)) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(mesh.vertices.flat(), 3),
    );
    geometry.setIndex(mesh.faces.flat());
    geometry.computeVertexNormals();
    geometries.set(id, geometry);
  }
  for (const instance of data.instances) {
    const rgb = instance.color;
    const key = rgb.join(",");
    if (!materials.has(key))
      materials.set(
        key,
        new THREE.MeshStandardMaterial({
          color: new THREE.Color().setRGB(
            rgb[0] / 255,
            rgb[1] / 255,
            rgb[2] / 255,
            THREE.SRGBColorSpace,
          ),
          roughness: 0.28,
          metalness: 0,
        }),
      );
    const mesh = new THREE.Mesh(
      geometries.get(instance.part),
      materials.get(key),
    );
    const r = instance.rotation,
      t = instance.translation;
    mesh.matrixAutoUpdate = false;
    mesh.matrix.set(
      r[0][0],
      r[0][1],
      r[0][2],
      t[0],
      -r[1][0],
      -r[1][1],
      -r[1][2],
      -t[1],
      -r[2][0],
      -r[2][1],
      -r[2][2],
      -t[2],
      0,
      0,
      0,
      1,
    );
    group.add(mesh);
  }
  scene.add(new THREE.HemisphereLight(0xffffff, 0xa4a3a0, 2.5));
  const keyLight = new THREE.DirectionalLight(0xffffff, 3);
  keyLight.position.set(200, 400, 200);
  scene.add(keyLight);
  const fill = new THREE.DirectionalLight(0xffffff, 1.5);
  fill.position.set(-200, 100, -200);
  scene.add(fill);
  const bounds = new THREE.Box3().setFromObject(group),
    center = bounds.getCenter(new THREE.Vector3()),
    size = bounds.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z, 30);
  const grid = new THREE.GridHelper(radius * 2.6, 16, 0xe0e0dc, 0xe9e9e5);
  grid.position.set(center.x, bounds.min.y - 1, center.z);
  scene.add(grid);
  function reset() {
    camera.position
      .copy(center)
      .add(new THREE.Vector3(radius * 1.6, radius * 1.25, radius * 1.8));
    controls.target.copy(center);
    controls.update();
  }
  reset();
  const observer = new ResizeObserver(() => {
    const { width, height } = container.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  });
  observer.observe(container);
  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });
  return {
    reset,
    dispose() {
      observer.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      geometries.forEach((g) => g.dispose());
      materials.forEach((m) => m.dispose());
      grid.geometry.dispose();
      grid.material.dispose();
      renderer.dispose();
    },
  };
}
