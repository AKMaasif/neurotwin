import { useEffect, useRef, useState } from "react";
import { BrainData, Cursor, Settings, Selection, cursorPixel, drawSlice, offset, sliceSize, sliceVoxel } from "./data";

export default function SliceView({ data, axis, cursor, settings, onCursor, onSelect }: {
  data: BrainData; axis: number; cursor: Cursor; settings: Settings;
  onCursor: (c: Cursor) => void; onSelect: (s: Selection) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const shape = data.manifest.shape, [w, h] = sliceSize(shape, axis);
  const [cx, cy] = cursorPixel(shape, axis, cursor);
  useEffect(() => { if (ref.current) drawSlice(ref.current, data, axis, cursor, settings); }, [data, axis, cursor, settings]);
  return <section className="brain-slice" aria-label={["Sagittal", "Axial", "Coronal"][axis] + " MRI view"}>
    <header><strong>{["Sagittal", "Axial", "Coronal"][axis]}</strong><span>{cursor[axis] + 1} / {shape[axis]}</span>
      <button onClick={() => setZoom(Math.max(1, zoom - .5))} aria-label="Zoom slice out">−</button>
      <button onClick={() => setZoom(Math.min(4, zoom + .5))} aria-label="Zoom slice in">+</button>
      <button onClick={() => setZoom(1)}>Fit</button></header>
    <div className="brain-slice-frame" onWheel={e => { const next = [...cursor] as Cursor;
      next[axis] = Math.max(0, Math.min(shape[axis] - 1, next[axis] + Math.sign(e.deltaY))); onCursor(next); }}>
      <div className="brain-slice-image" style={{ aspectRatio: `${w}/${h}`, width: `${zoom * 100}%`, maxWidth: "none" }}>
        <canvas ref={ref} aria-label="Click MRI to inspect an anatomical label" onClick={e => {
          const r = e.currentTarget.getBoundingClientRect();
          const u = Math.max(0, Math.min(w - 1, Math.floor((e.clientX - r.left) / r.width * w)));
          const v = Math.max(0, Math.min(h - 1, Math.floor((e.clientY - r.top) / r.height * h)));
          const c = sliceVoxel(shape, axis, cursor, u, v); onCursor(c);
          const id = data.labels[offset(shape, c)];
          const row = data.manifest.measurements.find(m => m.label_id === id);
          onSelect(id ? { key: `aseg:${id}`, name: row?.name || `Segmentation label ${id}` } : null);
        }} />
        <div className="brain-cross-v" style={{ left: `${(cx + .5) / w * 100}%` }} />
        <div className="brain-cross-h" style={{ top: `${(cy + .5) / h * 100}%` }} />
      </div>
      <span className="brain-orient top">{axis === 1 ? "A" : "S"}</span>
      <span className="brain-orient bottom">{axis === 1 ? "P" : "I"}</span>
      <span className="brain-orient left">{axis === 0 ? "P" : "L"}</span>
      <span className="brain-orient right">{axis === 0 ? "A" : "R"}</span>
    </div>
    <input type="range" aria-label={["Sagittal", "Axial", "Coronal"][axis] + " slice"} min={0} max={shape[axis] - 1}
      value={cursor[axis]} onChange={e => { const next = [...cursor] as Cursor; next[axis] = +e.target.value; onCursor(next); }} />
  </section>;
}
