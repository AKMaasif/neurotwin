export type Measurement = { key: string; name: string; kind: string; hemisphere: string | null; label_id?: number;
  volume: number; thickness?: number; area?: number };
export type Manifest = { subject: string; dataset: string; visit: string; status: string; engine_version: string;
  shape: number[]; voxel_to_surface_ras: number[][]; measurements: Measurement[]; limitations: string[];
  source_archive: string; source_checksums: Record<string, string> };
export type Region = { name: string; key: string; color: number[] };
export type Surface = { positions: Float32Array; indices: Uint32Array };
export type Hemisphere = { regions: Region[]; annotation: Int32Array; thickness: Float32Array;
  surfaces: Record<string, Surface> };
export type BrainData = { manifest: Manifest; volume: Uint8Array; labels: Uint16Array; hemispheres: Record<string, Hemisphere> };
export type Cursor = [number, number, number];
export type Selection = { key: string; name: string; thickness?: number } | null;
export type Settings = { surface: string; color: string; opacity: number; left: boolean; right: boolean;
  clipping: boolean; cut: number; planes: boolean; overlay: boolean; level: number; width: number; wireframe: boolean };
export const initialSettings: Settings = { surface: "pial", color: "regions", opacity: 1, left: true, right: true,
  clipping: false, cut: 0, planes: false, overlay: false, level: 110, width: 220, wireframe: false };

export async function getResearch(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(`/api/imaging/${path}`, { credentials: "same-origin", signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Imaging request failed (${response.status}).`);
  }
  return response;
}

export async function loadBrain(signal: AbortSignal, progress: (message: string) => void): Promise<BrainData> {
  progress("Reading the research case…");
  const manifest: Manifest = await (await getResearch("case", signal)).json();
  const bin = async (name: string) => (await getResearch(`artifacts/${name}`, signal)).arrayBuffer();
  progress("Loading MRI volume and anatomical labels…");
  const [v, l] = await Promise.all([bin("volume.bin"), bin("labels.bin")]);
  const count = manifest.shape.reduce((a, b) => a * b, 1);
  if (v.byteLength !== count || l.byteLength !== count * 2) throw new Error("Volume size does not match its geometry.");
  const hemispheres: Record<string, Hemisphere> = {};
  for (const hemi of ["lh", "rh"]) {
    progress(`Loading ${hemi === "lh" ? "left" : "right"} cortical surfaces…`);
    const [regions, annotation, thickness] = await Promise.all([
      getResearch(`artifacts/${hemi}.regions.json`, signal).then(r => r.json()), bin(`${hemi}.annotation.bin`), bin(`${hemi}.thickness.bin`),
    ]);
    const surfaces: Record<string, Surface> = {};
    for (const type of ["pial", "white", "inflated"]) {
      const [p, f] = await Promise.all([bin(`${hemi}.${type}.vertices.bin`), bin(`${hemi}.${type}.faces.bin`)]);
      if (p.byteLength / 12 !== annotation.byteLength / 4 || thickness.byteLength !== annotation.byteLength) {
        throw new Error("Surface and annotation sizes disagree.");
      }
      surfaces[type] = { positions: new Float32Array(p), indices: new Uint32Array(f) };
    }
    hemispheres[hemi] = { regions, annotation: new Int32Array(annotation), thickness: new Float32Array(thickness), surfaces };
  }
  return { manifest, volume: new Uint8Array(v), labels: new Uint16Array(l), hemispheres };
}

export function offset(shape: number[], c: number[]) { return (c[0] * shape[1] + c[1]) * shape[2] + c[2]; }
export function world(data: BrainData, c: number[]): [number, number, number] {
  return data.manifest.voxel_to_surface_ras.slice(0, 3).map(row => row[0] * c[0] + row[1] * c[1] + row[2] * c[2] + row[3]) as Cursor;
}
export function labelColor(id: number): [number, number, number] {
  return [65 + (id * 71) % 160, 65 + (id * 113) % 160, 65 + (id * 151) % 160];
}
export function heat(value: number): [number, number, number] {
  const t = Math.max(0, Math.min(1, value / 5));
  return t < .5 ? [Math.round(t * 2 * 255), Math.round(t * 2 * 190), 220] : [255, Math.round(190 + (t - .5) * 130), Math.round(220 * (2 - t * 2))];
}
export function sliceSize(shape: number[], axis: number): [number, number] {
  return axis === 0 ? [shape[2], shape[1]] : axis === 1 ? [shape[0], shape[2]] : [shape[0], shape[1]];
}
export function sliceVoxel(shape: number[], axis: number, cursor: Cursor, u: number, v: number): Cursor {
  return axis === 0 ? [cursor[0], v, u] : axis === 1 ? [shape[0] - 1 - u, cursor[1], shape[2] - 1 - v] : [shape[0] - 1 - u, v, cursor[2]];
}
export function cursorPixel(shape: number[], axis: number, c: Cursor): [number, number] {
  return axis === 0 ? [c[2], c[1]] : axis === 1 ? [shape[0] - 1 - c[0], shape[2] - 1 - c[2]] : [shape[0] - 1 - c[0], c[1]];
}
export function drawSlice(canvas: HTMLCanvasElement, data: BrainData, axis: number, cursor: Cursor, settings: Settings) {
  const shape = data.manifest.shape;
  const [w, h] = sliceSize(shape, axis);
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d"); if (!ctx) return;
  const image = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const index = offset(shape, sliceVoxel(shape, axis, cursor, x, y));
    const value = Math.max(0, Math.min(255, (data.volume[index] - settings.level + settings.width / 2) * 255 / settings.width));
    const id = data.labels[index], color = labelColor(id);
    const p = (y * w + x) * 4;
    for (let k = 0; k < 3; k++) image.data[p + k] = settings.overlay && id ? value * .55 + color[k] * .45 : value;
    image.data[p + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
}
