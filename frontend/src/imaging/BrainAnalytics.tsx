import { useEffect, useMemo, useRef, useState } from "react";
import { Brain, ChevronRight, Layers, Maximize2, RotateCcw, Search, SlidersHorizontal, ZoomIn, ZoomOut } from "lucide-react";
import BrainScene, { SceneActions } from "./BrainScene";
import SliceView from "./SliceView";
import NativeWorkflow from "./NativeWorkflow";
import CompareVisits from "./CompareVisits";
import AgentAnalysis from "./AgentAnalysis";
import { BrainData, Cursor, Selection, Settings, initialSettings, loadBrain, offset, world } from "./data";
import { useT } from "../i18n";
import "./imaging.css";

export default function BrainAnalytics(_props: { onClose: () => void }) {
  const { t } = useT();
  const rtl = t.lang === "ar";
  const [data, setData] = useState<BrainData | null>(null), [error, setError] = useState("");
  const [progress, setProgress] = useState("Opening research imaging…"), [attempt, setAttempt] = useState(0);
  const [settings, setSettings] = useState<Settings>({ ...initialSettings });
  const [cursor, setCursor] = useState<Cursor>([128, 128, 128]), [selection, setSelection] = useState<Selection>(null);
  const [query, setQuery] = useState(""), [tab, setTab] = useState("viewer"), [expanded, setExpanded] = useState(false);
  const [inside, setInside] = useState(false);
  const scene = useRef<SceneActions>(null);
  const set = <K extends keyof Settings>(key: K, value: Settings[K]) => setSettings(s => ({ ...s, [key]: value }));
  useEffect(() => {
    if (tab === "native" || tab === "compare" || tab === "agent" || data) return;
    const controller = new AbortController(); setError(""); setData(null);
    loadBrain(controller.signal, setProgress).then(d => { setData(d); setCursor(d.manifest.shape.map(n => Math.floor(n / 2)) as Cursor); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [attempt, tab, data]);
  const rows = useMemo(() => data?.manifest.measurements.filter(row =>
    `${row.name} ${row.hemisphere || ""}`.toLowerCase().includes(query.toLowerCase())) || [], [data, query]);
  const selected = data?.manifest.measurements.find(m => m.key === selection?.key);
  const reset = () => { setInside(false); setSettings({ ...initialSettings }); scene.current?.reset(); };
  const enter = () => {
    setSettings(s => ({ ...s, surface: "pial", opacity: .28, planes: true, clipping: true }));
    setInside(true); scene.current?.enter();
  };
  const exportStats = () => {
    if (!data) return;
    const keys = ["name", "hemisphere", "kind", "volume", "area", "thickness"] as const;
    const csv = ["# OASIS-1 imported derivatives; QC not reviewed; volume mm3, area mm2, thickness mm", keys.join(","),
      ...data.manifest.measurements.map(row => keys.map(k => JSON.stringify(row[k] ?? "")).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = `${data.manifest.subject}-measurements.csv`; a.click(); URL.revokeObjectURL(url);
  };
  return <main className="brain-workspace" dir={rtl ? "rtl" : "ltr"} lang={t.lang}>
    <header className="brain-header">
      <div className="brain-brand"><div><strong>{t("baTitle")}</strong><small>{t("baSub")}</small></div></div>
      <span className="brain-badge">{t("baBadge")}</span>
    </header>
    <nav className="brain-tabs" aria-label={t("baNav")}>
      {[["viewer", t("baTabViewer")], ["native", t("baTabNative")], ["compare", t("baTabCompare")], ["agent", t("baTabAgent")], ["measurements", t("baTabMeasures")], ["provenance", t("baTabSource")]].map(([id, label]) =>
        <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}
      <span>{tab === "compare" || tab === "agent" ? t("baLblTwo") : tab === "native" ? t("baLblNative") : t("baLblOne")}</span>
    </nav>
    {tab === "native" || tab === "compare" || tab === "agent" ? <div dir="ltr" lang="en">{rtl && <p className="brain-en-only" dir="rtl" lang="ar">{t("baEnOnly")}</p>}{tab === "native" ? <NativeWorkflow /> : tab === "compare" ? <CompareVisits /> : <AgentAnalysis />}</div> : error ? <div className="brain-loading" role="alert"><Brain size={40} /><h1>{t("baUnavailTitle")}</h1><p dir="ltr" lang="en">{error}</p>
      <p>{t("baUnavailBody")}</p><div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}><button onClick={() => setAttempt(v => v + 1)}>{t("baTryAgain")}</button><button onClick={() => setTab("native")}>{t("baTabNative")}</button><button onClick={() => setTab("compare")}>{t("baTabCompare")}</button></div></div>
      : !data ? <div className="brain-loading" role="status"><Brain size={40} /><h1>{t("baOpening")}</h1><p dir="ltr" lang="en">{progress}</p><progress aria-label="Loading imaging artifacts" /></div>
      : <>
        <div className="brain-casebar"><span className="brain-case-icon"><Brain size={21} /></span><div><strong>{data.manifest.subject}</strong><small dir="ltr">OASIS-1 · Structural T1 MRI · {data.manifest.shape.join(" × ")} voxels</small></div>
          <span className="brain-qc">○ {t("baImported")}</span><button onClick={exportStats}>{t("baExport")}</button></div>
        {tab === "provenance" ? <section className="brain-document" dir="ltr" lang="en">
          <p className="brain-eyebrow">{t("baSrcEyebrow")}</p><h1>{t("baSrcTitle")}</h1>
          <p>This is a real OASIS research participant, separate from the synthetic people in the clinical workspace. The page reads existing FreeSurfer results from your local archive.</p>
          <dl><dt>Dataset / visit</dt><dd>{data.manifest.dataset} / {data.manifest.visit}</dd><dt>Archive</dt><dd>{data.manifest.source_archive}</dd>
            <dt>Processing version</dt><dd>{data.manifest.engine_version}</dd><dt>Display volume</dt><dd>T1.mgz, converted to an 8-bit working volume; original preserved locally</dd>
            <dt>Spatial frame</dt><dd>FreeSurfer surface RAS (millimetres); volume uses its voxel-to-surface transform</dd></dl>
          <h2>Current boundaries</h2><ul>{data.manifest.limitations.map(l => <li key={l}>{l}</li>)}
            <li>Native scan import and display preparation are available under Import & processing. These imported surfaces and measurements remain a separate legacy reference.</li>
            <li>Native segmentation, surface reconstruction, editing, clinical QC decisions and forecasts are not yet implemented.</li>
            <li>Inside exploration combines cortical transparency with MRI cutting planes; it does not show microscopic anatomy.</li></ul>
          <h2>Source integrity</h2><details><summary>{Object.keys(data.manifest.source_checksums).length} source artifacts with SHA-256 checksums</summary>
            <div className="brain-checksums">{Object.entries(data.manifest.source_checksums).map(([name, hash]) => <p key={name}><strong>{name}</strong><code>{hash}</code></p>)}</div></details>
        </section> : tab === "measurements" ? <section className="brain-measures">
          <div className="brain-table-heading"><div><p className="brain-eyebrow">{t("baMeasEyebrow")}</p><h1>{t("baMeasTitle")}</h1><p>{t("baMeasNote")}</p></div>
            <label className="brain-search"><Search size={16} /><input aria-label={t("baFind")} value={query} onChange={e => setQuery(e.target.value)} placeholder={t("baFind")} /></label></div>
          <div className="brain-table-scroll"><table><thead><tr><th>{t("baColRegion")}</th><th>{t("baColHemi")}</th><th>{t("baColVol")}</th><th>{t("baColArea")}</th><th>{t("baColThick")}</th></tr></thead>
            <tbody>{rows.map(row => <tr key={row.key}><th><button onClick={() => { setSelection({ key: row.key, name: row.name }); setTab("viewer"); }}>{row.name.replace(/_/g, " ")}</button></th>
              <td>{row.hemisphere === "lh" ? t("baHemiL") : row.hemisphere === "rh" ? t("baHemiR") : "—"}</td><td>{row.volume.toLocaleString()}</td><td>{row.area?.toLocaleString() ?? "—"}</td><td>{row.thickness?.toFixed(3) ?? "—"}</td></tr>)}</tbody></table>
            {!rows.length && <p>{t("baNoMatch")}</p>}</div>
        </section> : <div className={`brain-layout ${expanded ? "brain-expanded" : ""}`}>
          <aside className="brain-tools">
            <p className="brain-eyebrow"><Layers size={14} /> {t("baLayers")}</p>
            <h2>{t("baSurfaces")}</h2><label className="brain-control">Surface<select aria-label="Surface" value={settings.surface} onChange={e => {
              const surface = e.target.value; set("surface", surface); if (surface === "inflated") setInside(false);
            }}><option value="pial">Pial · outer cortex</option><option value="white">White · inner boundary</option><option value="inflated">Inflated · reveal folds</option></select></label>
            <div className="brain-check-row"><label><input type="checkbox" checked={settings.left} onChange={e => set("left", e.target.checked)} /> {t("baLeft")}</label>
              <label><input type="checkbox" checked={settings.right} onChange={e => set("right", e.target.checked)} /> {t("baRight")}</label></div>
            <label className="brain-control">Surface colors<select aria-label="Surface colors" value={settings.color} onChange={e => set("color", e.target.value)}>
              <option value="regions">Anatomical regions</option><option value="thickness">Cortical thickness</option><option value="plain">Plain surface</option></select></label>
            {settings.color === "thickness" && <div className="brain-scale"><div /><span>0 mm</span><span>5+ mm</span></div>}
            <label className="brain-control">Opacity <output>{Math.round(settings.opacity * 100)}%</output><input type="range" min={.08} max={1} step={.01} value={settings.opacity} onChange={e => set("opacity", +e.target.value)} /></label>
            <label className="brain-check"><input type="checkbox" checked={settings.wireframe} onChange={e => set("wireframe", e.target.checked)} /> Mesh wireframe</label>
            <h2>Explore inside</h2>
            <label className="brain-check"><input type="checkbox" checked={settings.clipping} onChange={e => set("clipping", e.target.checked)} /> Cut away the right side</label>
            {settings.clipping && <label className="brain-control">Cut position <output>{settings.cut} mm RAS</output><input type="range" min={-110} max={110} value={settings.cut} onChange={e => set("cut", +e.target.value)} /></label>}
            <label className="brain-check"><input type="checkbox" checked={settings.planes} disabled={settings.surface === "inflated"} onChange={e => set("planes", e.target.checked)} /> MRI cutting planes</label>
            {settings.surface === "inflated" && <p className="brain-tool-note">Inflation changes geometry. MRI planes and anatomical cursor linking are unavailable in this view.</p>}
            <button className="brain-enter" onClick={enter}>Explore inside <ChevronRight size={16} /></button>
            <p className="brain-tool-note">Moves the camera to the selected MRI location with transparent cortex and cutting planes.</p>
            <h2><SlidersHorizontal size={14} /> MRI appearance</h2>
            <label className="brain-check"><input type="checkbox" checked={settings.overlay} onChange={e => set("overlay", e.target.checked)} /> Segmentation overlay</label>
            <label className="brain-control">Brightness / level<input type="range" min={0} max={255} value={settings.level} onChange={e => set("level", +e.target.value)} /></label>
            <label className="brain-control">Contrast / window<input type="range" min={20} max={400} value={settings.width} onChange={e => set("width", +e.target.value)} /></label>
          </aside>
          <section className="brain-viewers">
            <div className="brain-viewer-toolbar"><strong>{inside ? t("baInsideTitle") : t("baInspectTitle")}</strong>
              <button aria-label="Zoom brain in" title="Zoom in" onClick={() => scene.current?.zoom(.8)}><ZoomIn size={16} /></button>
              <button aria-label="Zoom brain out" title="Zoom out" onClick={() => scene.current?.zoom(1.25)}><ZoomOut size={16} /></button>
              <button onClick={() => scene.current?.focus()}>{t("baFocus")}</button>
              <button onClick={reset}><RotateCcw size={15} /> {t("baReset")}</button>
              <button aria-label={expanded ? "Restore slice layout" : "Expand 3D view"} onClick={() => setExpanded(v => !v)}><Maximize2 size={16} /></button></div>
            <div className="brain-scene-wrap" dir="ltr"><BrainScene ref={scene} data={data} settings={settings} cursor={cursor} selection={selection} onSelect={setSelection} onCursor={setCursor} />
              <div className="brain-scene-caption">{settings.surface.toUpperCase()} SURFACE <span>Real scan-derived geometry</span></div></div>
            <div className="brain-slices" dir="ltr">{[0, 2, 1].map(axis => <SliceView key={axis} data={data} axis={axis} cursor={cursor} settings={settings} onCursor={setCursor} onSelect={setSelection} />)}</div>
          </section>
          <aside className="brain-inspector"><p className="brain-eyebrow">{t("baRegion")}</p>
            <h2>{selection ? selection.name.replace(/_/g, " ") : t("baExplore")}</h2>
            <p className="brain-tool-note">{t("baRegionHint")}</p>
            {selection && <button onClick={() => setSelection(null)}>{t("baClear")}</button>}
            {selected && <div className="brain-metrics"><div><span>Regional volume</span><strong>{selected.volume.toLocaleString()} <small>mm³</small></strong></div>
              {selected.area !== undefined && <div><span>Surface area</span><strong>{selected.area.toLocaleString()} <small>mm²</small></strong></div>}
              {selected.thickness !== undefined && <div><span>Mean cortical thickness</span><strong>{selected.thickness.toFixed(3)} <small>mm</small></strong></div>}</div>}
            {selection?.thickness !== undefined && <p className="brain-tool-note">Picked vertex thickness: {selection.thickness.toFixed(3)} mm. This differs from a regional average.</p>}
            {selection && !selected && <p className="brain-tool-note">No regional statistics row is available for this label.</p>}
            <h3>{t("baCursor")}</h3><p className="brain-coordinate">{cursor.join(" · ")} <small>voxel index</small></p>
            <p className="brain-coordinate">{world(data, cursor).map(v => v.toFixed(1)).join(" · ")} <small>surface RAS · mm</small></p>
            <p className="brain-tool-note">Segmentation label: {data.labels[offset(data.manifest.shape, cursor)]}</p>
            <h3>{t("baVisits")}</h3><p className="brain-tool-note">{t("baVisitsNote")}</p>
            <div className="brain-quality-note"><strong>{t("baQcTitle")}</strong><p>{t("baQcNote")}</p><button onClick={() => setTab("provenance")}>View source & quality</button></div>
          </aside>
        </div>}
        <footer className="brain-footer"><span>OASIS-1 / {data.manifest.subject}</span><span>{t("baFoot")}</span></footer>
      </>}
  </main>;
}
