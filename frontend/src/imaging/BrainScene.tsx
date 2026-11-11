import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { BrainData, Cursor, Settings, Selection, drawSlice, heat, sliceSize, sliceVoxel, world } from "./data";

export type SceneActions = { reset: () => void; zoom: (factor: number) => void; enter: () => void; focus: () => void };
type Props = { data: BrainData; settings: Settings; cursor: Cursor; selection: Selection;
  onSelect: (s: Selection) => void; onCursor: (c: Cursor) => void };
type Runtime = { renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
  controls: OrbitControls; meshes: THREE.Mesh<THREE.BufferGeometry, THREE.MeshPhongMaterial>[];
  planes: THREE.Group; geometries: Record<string, THREE.BufferGeometry>; cut: THREE.Plane };

const BrainScene = forwardRef<SceneActions, Props>(function BrainScene(props, ref) {
  const host = useRef<HTMLDivElement>(null), runtime = useRef<Runtime | null>(null), live = useRef(props);
  live.current = props;
  const [failure, setFailure] = useState("");
  useImperativeHandle(ref, () => ({
    reset() { const r = runtime.current; if (r) { r.camera.position.set(200, -240, 140); r.controls.target.set(0, 0, 0); r.controls.update(); } },
    zoom(factor) { const r = runtime.current; if (r) { r.camera.position.sub(r.controls.target).multiplyScalar(factor).add(r.controls.target); r.controls.update(); } },
    enter() { const r = runtime.current; if (r) { const p = new THREE.Vector3(...world(live.current.data, live.current.cursor));
      r.controls.target.copy(p); r.camera.position.copy(p).add(new THREE.Vector3(45, -65, 35)); r.controls.update(); } },
    focus() { const r = runtime.current; if (r) { const p = new THREE.Vector3(...world(live.current.data, live.current.cursor));
      const delta = r.camera.position.clone().sub(r.controls.target); r.controls.target.copy(p); r.camera.position.copy(p).add(delta); r.controls.update(); } },
  }), []);

  useEffect(() => {
    const el = host.current; if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true }); }
    catch { setFailure("3D graphics are unavailable in this browser. MRI slices and measurements remain available."); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.localClippingEnabled = true;
    renderer.setClearColor("#0c1725"); el.appendChild(renderer.domElement);
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(42, 1, .1, 2000);
    camera.up.set(0, 0, 1); camera.position.set(200, -240, 140);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.minDistance = 2; controls.maxDistance = 900; controls.zoomSpeed = .85;
    scene.add(new THREE.HemisphereLight(0xe8f4ff, 0x393c55, 2));
    const lamp = new THREE.DirectionalLight(0xffffff, 2.2); lamp.position.set(100, -200, 300); scene.add(lamp);
    const fill = new THREE.DirectionalLight(0x84cee6, 1.2); fill.position.set(-200, 100, 0); scene.add(fill);
    const geometries: Record<string, THREE.BufferGeometry> = {}, meshes: Runtime["meshes"] = [];
    const cut = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
    for (const hemi of ["lh", "rh"]) {
      const h = props.data.hemispheres[hemi];
      for (const [name, surface] of Object.entries(h.surfaces)) {
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(surface.positions, 3));
        g.setIndex(new THREE.BufferAttribute(surface.indices, 1));
        g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(surface.positions.length), 3));
        g.computeVertexNormals(); g.computeBoundingSphere(); geometries[`${hemi}.${name}`] = g;
      }
      const material = new THREE.MeshPhongMaterial({ vertexColors: true, side: THREE.DoubleSide, shininess: 25 });
      const mesh = new THREE.Mesh(geometries[`${hemi}.pial`], material); mesh.userData.hemi = hemi;
      meshes.push(mesh); scene.add(mesh);
    }
    const planes = new THREE.Group(); scene.add(planes);
    const r = { renderer, scene, camera, controls, meshes, planes, geometries, cut }; runtime.current = r;
    const resize = new ResizeObserver(() => { const w = el.clientWidth, h = el.clientHeight;
      if (w && h) { renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); } });
    resize.observe(el);
    let down = [0, 0];
    const pointerDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const pointerUp = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
      const { settings, data, onSelect, onCursor } = live.current;
      const rect = renderer.domElement.getBoundingClientRect();
      const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2((e.clientX - rect.left) / rect.width * 2 - 1, -(e.clientY - rect.top) / rect.height * 2 + 1), camera);
      const hit = ray.intersectObjects(meshes.filter(m => m.visible)).find(h => !settings.clipping || h.point.x <= settings.cut);
      if (!hit?.face) return;
      const hemi = hit.object.userData.hemi as string, h = data.hemispheres[hemi], vertex = hit.face.a;
      const region = h.regions[h.annotation[vertex]];
      onSelect(region ? { key: region.key, name: `${hemi === "lh" ? "Left" : "Right"} ${region.name}`, thickness: h.thickness[vertex] } : null);
      if (settings.surface !== "inflated") {
        const matrix = new THREE.Matrix4().set(...data.manifest.voxel_to_surface_ras.flat() as Parameters<THREE.Matrix4["set"]>);
        const c = hit.point.clone().applyMatrix4(matrix.invert());
        onCursor(c.toArray().map((v, i) => Math.max(0, Math.min(data.manifest.shape[i] - 1, Math.round(v)))) as Cursor);
      }
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
    return () => {
      resize.disconnect(); renderer.setAnimationLoop(null); controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", pointerDown); renderer.domElement.removeEventListener("pointerup", pointerUp);
      Object.values(geometries).forEach(g => g.dispose()); meshes.forEach(m => m.material.dispose());
      planes.children.forEach(child => { const m = child as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>; m.geometry.dispose(); m.material.map?.dispose(); m.material.dispose(); });
      renderer.dispose(); renderer.domElement.remove(); runtime.current = null;
    };
  }, [props.data]);

  useEffect(() => {
    const r = runtime.current; if (!r) return;
    const { data, settings, selection } = props;
    r.cut.constant = settings.cut;
    for (const mesh of r.meshes) {
      const hemi = mesh.userData.hemi as string, h = data.hemispheres[hemi];
      mesh.visible = hemi === "lh" ? settings.left : settings.right;
      mesh.geometry = r.geometries[`${hemi}.${settings.surface}`];
      const colors = mesh.geometry.getAttribute("color") as THREE.BufferAttribute;
      const color = new THREE.Color();
      for (let i = 0; i < h.annotation.length; i++) {
        const region = h.regions[h.annotation[i]];
        const rgb = selection?.key === region?.key ? [255, 235, 120]
          : settings.color === "thickness" ? heat(h.thickness[i]) : settings.color === "regions" ? region?.color || [140, 150, 160] : [192, 176, 184];
        color.setRGB(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, THREE.SRGBColorSpace);
        colors.setXYZ(i, color.r, color.g, color.b);
      }
      colors.needsUpdate = true;
      mesh.material.opacity = settings.opacity; mesh.material.transparent = settings.opacity < 1;
      mesh.material.depthWrite = settings.opacity >= .95; mesh.material.wireframe = settings.wireframe;
      mesh.material.clippingPlanes = settings.clipping ? [r.cut] : [];
      mesh.material.needsUpdate = true;
    }
  }, [props.data, props.settings, props.selection]);

  useEffect(() => {
    const r = runtime.current; if (!r) return;
    const { data, settings, cursor } = props;
    r.planes.children.slice().forEach(child => { const m = child as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
      m.geometry.dispose(); m.material.map?.dispose(); m.material.dispose(); r.planes.remove(child); });
    if (!settings.planes || settings.surface === "inflated") return;
    for (const axis of [0, 1, 2]) {
      const canvas = document.createElement("canvas"); drawSlice(canvas, data, axis, cursor, settings);
      const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; texture.flipY = false;
      const [w, h] = sliceSize(data.manifest.shape, axis);
      const positions = [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]].flatMap(([u, v]) => world(data, sliceVoxel(data.manifest.shape, axis, cursor, u, v)));
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2)); g.setIndex([0, 1, 2, 0, 2, 3]);
      const material = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide });
      r.planes.add(new THREE.Mesh(g, material));
    }
  }, [props.data, props.cursor, props.settings]);

  return <div className="brain-scene" ref={host} aria-label="Interactive scan-derived 3D brain">
    {failure && <div className="brain-webgl-error" role="alert">{failure}</div>}
    {!failure && <div className="brain-scene-hint">Drag to rotate · Scroll to zoom · Right-drag to pan · Click cortex to inspect</div>}
  </div>;
});
export default BrainScene;
