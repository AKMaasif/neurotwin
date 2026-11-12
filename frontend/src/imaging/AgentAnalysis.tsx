import { useEffect, useRef, useState } from "react";
import { api, AgentPair, AgentRegion, AgentRun, AgentSaved } from "../api";
import AgentActivity from "./AgentActivity";

const base = (id: string) => `/api/imaging/agent/runs/${id}`;
const KEY = "nt-agent-run", VIEWS = "nt-agent-views-";
const BUSY = ["queued", "running", "aligned"];
const STATE_TEXT: Record<string, string> = { done: "Done", warning: "Done with warnings", running: "Running", pending: "Waiting", unavailable: "Unavailable",
  failed: "Failed", blocked: "Blocked", cancelled: "Cancelled" };
type View = { axis: number; index: number; region: number; layers: string[]; opacity: number; zoom: number };

const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked */ } };

/** Two scans of one person: validation, alignment, imported segmentation, volume comparison, review and a draft report. */
export default function AgentAnalysis() {
  const [saved, setSaved] = useState<AgentSaved[]>([]), [pairs, setPairs] = useState<AgentPair[] | null>(null), [error, setError] = useState(""), [pair, setPair] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null), [liveSignal, setLiveSignal] = useState(0);
  const [axis, setAxis] = useState(2), [index, setIndex] = useState(64), [layers, setLayers] = useState<string[]>(["original"]);
  const [opacity, setOpacity] = useState(0.6), [zoom, setZoom] = useState(1), [region, setRegion] = useState(0), [later, setLater] = useState("later_aligned");
  const [views, setViews] = useState<View[]>([]), [shape, setShape] = useState<number[] | null>(null);
  const timer = useRef<number>();

  useEffect(() => {
    api.agentPairs().then(r => { setPairs(r.pairs); setPair(p => p || (r.pairs[0] ? `${r.pairs[0].earlier}|${r.pairs[0].later}` : "")); }).catch(e => setError(e.message));
    api.agentSaved().then(r => setSaved(r.runs)).catch(() => undefined);
    const last = read(KEY);
    if (last) api.agentRun(last).then(setRun).catch(() => undefined);  // results survive a refresh
  }, []);
  useEffect(() => {
    window.clearTimeout(timer.current);
    if (run && BUSY.includes(run.state)) timer.current = window.setTimeout(() => api.agentRun(run.run_id).then(setRun).catch(e => setError(e.message)), 1500);
    return () => window.clearTimeout(timer.current);
  }, [run]);
  useEffect(() => {
    if (!run) return;
    write(KEY, run.run_id);
    try { setViews(JSON.parse(read(VIEWS + run.run_id) ?? "[]")); } catch { setViews([]); }
    const sh = run.validation.checks?.earlier?.shape ?? null;  // stored with the run, so saved runs need no original scans
    setShape(sh); if (sh) setIndex(i => Math.min(i, sh[axis] - 1));
  }, [run?.run_id, run?.alignment !== null]);

  const start = async (retry?: boolean) => {
    setError("");
    try {
      if (retry && run) setRun(await api.agentRetry(run.run_id));
      else { const [a, b] = pair.split("|"); setRun(await api.agentStart(a, b)); }
      setLiveSignal(n => n + 1);  // a new real run: the activity panel opens and follows it
    } catch (e) { setError((e as Error).message); }
  };
  const runLive = async (r: AgentSaved) => {
    setError("");
    try { setRun(await api.agentStart(r.earlier, r.later)); setLiveSignal(n => n + 1); } catch (e) { setError((e as Error).message); }
  };
  const cancel = async () => { if (run) try { setRun(await api.agentCancel(run.run_id)); } catch (e) { setError((e as Error).message); } };

  const openResult = (target: string) => {
    const id = { viewer: "ag-viewer", measurements: "ag-table", review: "ag-review", report: "ag-report" }[target];
    const el = id ? document.getElementById(id) : null;
    if (!el) return;
    el.scrollIntoView({ behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    el.setAttribute("tabindex", "-1"); (el as HTMLElement).focus({ preventScroll: true });
  };

  if (error && !pairs) return <section className="brain-loading" role="alert"><h1>Agent Analysis is not ready on this server</h1><p>{error}</p></section>;
  if (!pairs) return <section className="brain-loading" role="status"><h1>Looking for scan pairs</h1><progress aria-label="Loading" /></section>;

  const sliceCount = shape ? shape[axis] : 128;
  const hasSeg = !!run?.measurements;
  const regions = run?.measurements?.regions ?? [];
  const picked: AgentRegion | undefined = regions.find(r => r.label === region);
  const toggle = (l: string) => setLayers(x => x.includes(l) ? x.filter(y => y !== l) : [...x, l]);
  const stack = (which: "earlier" | "later") => {
    const baseLayer = which === "earlier" ? "earlier" : later;
    const q = `axis=${axis}&index=${index}`;
    return <div className="ag-stage"><div className="ag-zoom" style={{ transform: `scale(${zoom})` }}>
      {layers.includes("original") && <img src={`${base(run!.run_id)}/slice.png?layer=${baseLayer}&${q}`} alt={`${which} scan, slice ${index}`} />}
      {hasSeg && layers.includes("regions") && <img className="ag-ov" style={{ opacity }} src={`${base(run!.run_id)}/overlay.png?layer=regions&${q}&label=${region}`} alt="" />}
      {hasSeg && layers.includes("change") && which === "later" && <img className="ag-ov" style={{ opacity }} src={`${base(run!.run_id)}/overlay.png?layer=change&${q}&label=${region}`} alt="" />}
    </div></div>;
  };
  const saveView = () => { const v = [...views, { axis, index, region, layers, opacity, zoom }].slice(-8); setViews(v); write(VIEWS + run!.run_id, JSON.stringify(v)); };
  const open = (v: View) => { setAxis(v.axis); setIndex(v.index); setRegion(v.region); setLayers(v.layers); setOpacity(v.opacity); setZoom(v.zoom); };

  return <section className="cmp ag">
    <header><p className="brain-eyebrow">SAME PERSON · TWO SCANS · RESEARCH</p><h1>Agent Analysis</h1>
      <p>Compares two scans of one person taken about 12, 15 or 18 months apart, from the original volumes. Measured differences only: nothing here is a diagnosis or a prediction.</p></header>
    {saved.length > 0 && <section className="ag-saved" aria-label="Saved analyses"><h2>Saved analyses</h2>
      <p className="cmp-note-plain">Finished runs on this server. <strong>View saved result</strong> shows what was stored; nothing is recomputed. <strong>Run live</strong> starts a new real analysis of the same two scans and shows each step as it happens.</p>
      <ul>{saved.map(r => <li key={r.run_id}><div><strong>{r.earlier.split("_")[1]} · {r.earlier.split("_").pop()} → {r.later.split("_").pop()}</strong>
        <span>{r.months !== null ? `${r.months} months${r.target_months ? ` (≈${r.target_months})` : ""}` : ""} · {r.segmentation ? `${r.segmentation} segmentation` : "no segmentation yet"}</span></div>
        <div className="ag-saved-actions">
          <button onClick={() => api.agentRun(r.run_id).then(setRun).catch(e => setError(e.message))} aria-pressed={run?.run_id === r.run_id}>View saved result</button>
          <button className="ag-live" onClick={() => runLive(r)} disabled={!!run && BUSY.includes(run.state)} title="Starts a new real analysis of these two scans. If this server cannot run a step, that step is shown as unavailable.">Run live</button></div></li>)}</ul></section>}
    <AgentActivity liveSignal={liveSignal} runId={run?.run_id ?? null} onCancel={cancel} onOpenResult={openResult} />
    {!pairs.length ? (!saved.length && <div className="cmp-empty"><h2>No pair is ready</h2><p>Two visits of one person must be extracted locally first. See <code>docs/OASIS2_COMPARE.md</code>.</p></div>) : <>
      <div className="ag-pick cmp-controls">
        <label>Scan pair<select value={pair} onChange={e => setPair(e.target.value)} disabled={!!run && BUSY.includes(run.state)}>
          {pairs.map(p => <option key={p.earlier + p.later} value={`${p.earlier}|${p.later}`}>{p.subject_id} · {p.earlier.split("_").pop()} → {p.later.split("_").pop()} · {p.interval.months.toFixed(1)} months
            {p.interval.nearest_target_months ? ` (≈${p.interval.nearest_target_months})` : " (outside 12/15/18)"}{p.segmented ? " · segmented" : ""}</option>)}</select></label>
        <button className="ag-run" onClick={() => start()} disabled={!pair || (!!run && BUSY.includes(run.state))}>Run Agent Analysis</button>
      </div>
      {error && <p role="alert" className="cmp-note">{error}</p>}
    </>}

    {run && <section aria-label="Progress" className="ag-steps">
      <h2>Progress <small>{run.earlier} → {run.later}{run.parent_run_id ? " · retry" : ""}</small></h2>
      {run.validation.interval && <p className="cmp-gap">Interval from the recorded day offsets: {run.validation.interval.months} months ({run.validation.interval.days} days)
        {run.validation.interval.nearest_target_months ? `, matching the ${run.validation.interval.nearest_target_months}-month window.` : ", outside the 12, 15 and 18-month windows."}</p>}
      <ol>{run.steps.map(s => <li key={s.key} className={`ag-${s.state}`}><span className="ag-chip">{STATE_TEXT[s.state] ?? s.state}</span> <strong>{s.label}</strong>
        {s.detail && <p>{s.detail}</p>}</li>)}</ol>
      <div className="ag-actions">
        {BUSY.includes(run.state) && <button onClick={cancel}>Cancel</button>}
        {["failed", "cancelled", "blocked", "partial", "complete"].includes(run.state) && <button onClick={() => start(true)}>Run again</button>}
      </div>
      <details><summary>Limitations of this pair ({run.validation.limitations.length})</summary><ul className="cmp-limits">{run.validation.limitations.map(l => <li key={l}>{l}</li>)}</ul></details>
    </section>}

    {run?.alignment && <section className="ag-viewer" id="ag-viewer" aria-label="Compare scans">
      <h2>Side-by-side view</h2>
      <div className="cmp-controls">
        <fieldset><legend>Slice along</legend>{[0, 1, 2].map(x => <label key={x}><input type="radio" name="agaxis" checked={axis === x} onChange={() => { setAxis(x); setIndex(Math.floor((shape?.[x] ?? 128) / 2)); }} />Voxel axis {x + 1}</label>)}</fieldset>
        <label>Slice {index}<input type="range" min={0} max={sliceCount - 1} value={index} onChange={e => setIndex(+e.target.value)} /></label>
        <label>Zoom {zoom.toFixed(1)}×<input type="range" min={1} max={3} step={0.1} value={zoom} onChange={e => setZoom(+e.target.value)} /></label>
        <label>Overlay opacity {Math.round(opacity * 100)}%<input type="range" min={0.1} max={1} step={0.05} value={opacity} onChange={e => setOpacity(+e.target.value)} /></label>
        <fieldset><legend>Layers</legend>
          <label><input type="checkbox" checked={layers.includes("original")} onChange={() => toggle("original")} />Original scan</label>
          <label title={hasSeg ? "" : "Needs the segmentation import"}><input type="checkbox" disabled={!hasSeg} checked={layers.includes("regions")} onChange={() => toggle("regions")} />Segmentation regions{hasSeg ? "" : " (unavailable)"}</label>
          <label title={hasSeg ? "" : "Needs the segmentation import"}><input type="checkbox" disabled={!hasSeg} checked={layers.includes("change")} onChange={() => toggle("change")} />Measured change{hasSeg ? "" : " (unavailable)"}</label></fieldset>
        <fieldset><legend>Later scan shown</legend>
          <label><input type="radio" name="aglater" checked={later === "later_aligned"} onChange={() => setLater("later_aligned")} />Aligned to the earlier scan</label>
          <label><input type="radio" name="aglater" checked={later === "later_original"} onChange={() => setLater("later_original")} />Original, not aligned</label></fieldset>
      </div>
      <div className="cmp-grid">
        <figure className="cmp-panel"><figcaption><strong>Earlier · {run.earlier.split("_").pop()}</strong></figcaption>{stack("earlier")}</figure>
        <figure className="cmp-panel"><figcaption><strong>Later · {run.later.split("_").pop()}</strong><span>{later === "later_aligned" ? "aligned to the earlier scan" : "original position"}</span></figcaption>{stack("later")}</figure>
      </div>
      {hasSeg && layers.includes("change") && <p className="cmp-note-plain">Change layer: <span className="ag-key ag-loss" /> labelled in the earlier scan only, <span className="ag-key ag-gain" /> in the later scan only. Boundary differences include alignment error.</p>}
      <p className="cmp-note-plain">Rotation: only switching the slice direction is offered; no 3D rotation of these volumes.</p>
      <div className="ag-actions"><button onClick={saveView}>Save this view</button>
        {views.map((v, i) => <button key={i} onClick={() => open(v)}>View {i + 1}: axis {v.axis + 1}, slice {v.index}{v.region ? `, ${regions.find(r => r.label === v.region)?.name ?? ""}` : ""}</button>)}</div>
      <div className="ag-align"><h3>Alignment</h3><p>{run.alignment.method} ({run.alignment.tool}). Similarity {run.alignment.correlation_before} → {run.alignment.correlation_after};
        estimated head movement {run.alignment.rotation_deg}° and {run.alignment.shift_mm_voxel_frame} mm. Measured over {run.alignment.mask}.</p></div>
    </section>}

    {run && !hasSeg && run.alignment && <section className="ag-need" role="status"><h2>Regional measurements are unavailable</h2>
      <p>{run.steps.find(s => s.key === "anatomical_analysis")?.detail}</p></section>}

    {hasSeg && <section className="ag-table" id="ag-table"><h2>Regional volumes <small>{run!.segmentation_tool?.tool} {run!.segmentation_tool?.version}</small></h2>
      <p className="cmp-note-plain">{run!.measurements!.source}. Uncertainty is not estimated, so every difference is marked uncertain.</p>
      <div className="ag-scroll"><table><thead><tr><th>Region</th><th>Earlier mm³</th><th>Later mm³</th><th>Difference</th><th>Uncertainty</th><th>Status</th></tr></thead><tbody>
        {regions.map(r => <tr key={r.label} className={r.label === region ? "ag-sel" : ""}>
          <td><button onClick={() => { setRegion(r.label === region ? 0 : r.label); if (!layers.includes("regions")) toggle("regions"); }}>{r.name}</button></td>
          <td>{r.earlier_mm3}</td><td>{r.later_mm3}</td><td>{r.difference_mm3} ({r.difference_pct === null ? "n/a" : `${r.difference_pct}%`})</td><td>not estimated</td><td>{r.status}</td></tr>)}
      </tbody></table></div>
      {picked && <aside className="ag-evidence" aria-label="Evidence"><h3>Evidence: {picked.name}</h3>
        <p>{picked.earlier_voxels} voxels earlier, {picked.later_voxels} later; {picked.earlier_mm3} → {picked.later_mm3} mm³ ({picked.difference_mm3} mm³).
          Source: voxel counts of the {run!.segmentation_tool?.tool} {run!.segmentation_tool?.version} segmentation. Earlier value, recent value, difference and uncertainty are as listed above.</p>
        <ul>{picked.review_notes.map(n => <li key={n}>{n}</li>)}</ul></aside>}
    </section>}

    {run?.review && <section className="ag-review" id="ag-review"><h2>Findings review</h2>
      {run.review.flags.length ? <ul>{run.review.flags.map(f => <li key={f}>{f}</li>)}</ul> : <p>No whole-scan inconsistency was found by the review rules.</p>}
      <p className="cmp-note-plain">{run.review.note}</p></section>}

    {run?.report && <section className="ag-report" id="ag-report"><h2>Report <small>{run.report.status}</small></h2>
      <p className="cmp-note-plain">Written by a {run.report.author}. It restates the measurements above and adds nothing.</p>
      {Object.entries(run.report.sections).map(([k, items]) => <div key={k}><h3>{{ measured: "Largest measured differences", quality_limitations: "Quality limitations", processing: "Processing", suggested_follow_up: "Suggested follow-up for clinician consideration", needs_clinical_review: "Needs clinical review" }[k] ?? k}</h3>
        <ul>{items.map(i => <li key={i}>{i}</li>)}</ul></div>)}</section>}
  </section>;
}
