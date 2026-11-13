import { useEffect, useRef, useState } from "react";
import { api, AgentFamily, AgentReviewState, AgentAi, AgentChat, AgentReview, AgentVisual, AgentAiStatus, AgentPair, AgentRegion, AgentRun, AgentSaved } from "../api";
import AgentActivity from "./AgentActivity";
import AgentCharts, { AlignmentFit } from "./AgentCharts";

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
  const [run, setRun] = useState<AgentRun | null>(null), [liveSignal, setLiveSignal] = useState(0), [replaySignal, setReplaySignal] = useState(0);
  const [recorded, setRecorded] = useState(false), [reveal, setReveal] = useState(4);
  const revealTimer = useRef<number>();
  const [fam, setFam] = useState<AgentFamily | null>(null), [famBusy, setFamBusy] = useState(false), [famTo, setFamTo] = useState(""), [famPick, setFamPick] = useState<string[]>([]), [famPart, setFamPart] = useState("");
  const [cr, setCr] = useState<AgentReviewState | null>(null), [crBusy, setCrBusy] = useState(false), [crComment, setCrComment] = useState("");
  const [rev, setRev] = useState<AgentReview | null>(null), [chat, setChat] = useState<AgentChat[]>([]), [revBusy, setRevBusy] = useState(false), [question, setQuestion] = useState(""), [askBusy, setAskBusy] = useState(false), [revMode, setRevMode] = useState("off");
  const [vis, setVis] = useState<AgentVisual | null>(null), [visInfo, setVisInfo] = useState<{ images_allowed: boolean; mode: string } | null>(null), [visBusy, setVisBusy] = useState(false), [visOk, setVisOk] = useState(false);
  const [showMeasured, setShowMeasured] = useState(true), [showModel, setShowModel] = useState(true);
  const [ai, setAi] = useState<AgentAi | null>(null), [aiStatus, setAiStatus] = useState<AgentAiStatus | null>(null), [aiBusy, setAiBusy] = useState(false), [aiTick, setAiTick] = useState(0), [noiseBusy, setNoiseBusy] = useState(false), [aiLang, setAiLang] = useState<"en" | "ar">("en"), [famLang, setFamLang] = useState<"en" | "ar">("en"), [famRead, setFamRead] = useState(false);
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
    setError(""); stopReveal(); setRecorded(false);
    try {
      if (retry && run) setRun(await api.agentRetry(run.run_id));
      else { const [a, b] = pair.split("|"); setRun(await api.agentStart(a, b)); }
      setLiveSignal(n => n + 1);  // a new real run: the activity panel opens and follows it
    } catch (e) { setError((e as Error).message); }
  };
  const cancel = async () => { if (run) try { setRun(await api.agentCancel(run.run_id)); } catch (e) { setError((e as Error).message); } };

  useEffect(() => {
    setAi(null);
    if (run?.report) api.agentAi(run.run_id).then(r => { setAi(r.result); setAiStatus(r.status); }).catch(() => undefined);
  }, [run?.run_id, !!run?.report]);
  useEffect(() => {
    setVis(null);
    if (run?.report) api.agentVisual(run.run_id).then(r => { setVis(r.result); setVisInfo({ images_allowed: r.images_allowed, mode: r.mode }); }).catch(() => undefined);
  }, [run?.run_id, !!run?.report]);
  useEffect(() => {
    setRev(null); setChat([]);
    if (run?.report) api.agentReview(run.run_id).then(r => { setRev(r.result); setChat(r.chat); setRevMode(r.mode); }).catch(() => undefined);
  }, [run?.run_id, !!run?.report]);
  const runReview = async () => {
    if (!run) return; setRevBusy(true); setError("");
    try { setRev(await api.agentRunReview(run.run_id)); setAiTick(n => n + 1); } catch (e) { setError((e as Error).message); } finally { setRevBusy(false); }
  };
  const ask = async () => {
    if (!run || !question.trim()) return; setAskBusy(true); setError("");
    try { const a = await api.agentAsk(run.run_id, question.trim()); setChat(c => [...c, a]); setQuestion(""); setAiTick(n => n + 1); } catch (e) { setError((e as Error).message); } finally { setAskBusy(false); }
  };
  const loadCr = () => { if (run?.report) api.agentReviewState(run.run_id).then(setCr).catch(() => undefined); };
  useEffect(() => { setCr(null); loadCr(); }, [run?.run_id, !!run?.report, ai, vis, rev]);  // eslint-disable-line react-hooks/exhaustive-deps
  const crDo = async (f: () => Promise<unknown>) => { setCrBusy(true); setError(""); try { await f(); loadCr(); setAiTick(n => n + 1); } catch (e) { setError((e as Error).message); } finally { setCrBusy(false); } };
  const loadFam = (fid = famTo) => { if (run?.report) api.agentFamily(run.run_id, fid || undefined).then(setFam).catch(() => undefined); };
  useEffect(() => { setFam(null); loadFam(); }, [run?.run_id, !!run?.report, cr?.state]);  // eslint-disable-line react-hooks/exhaustive-deps
  const famDo = async (f: () => Promise<unknown>) => { setFamBusy(true); setError(""); try { await f(); loadFam(); setAiTick(n => n + 1); } catch (e) { setError((e as Error).message); } finally { setFamBusy(false); } };
  const look = async () => {
    if (!run) return; setVisBusy(true); setError("");
    try { setVis(await api.agentLook(run.run_id)); setAiTick(n => n + 1); } catch (e) { setError((e as Error).message); } finally { setVisBusy(false); }
  };
  const explain = async () => {
    if (!run) return; setAiBusy(true); setError("");
    try { setAi(await api.agentExplain(run.run_id, aiLang)); setAiTick(n => n + 1); } catch (e) { setError((e as Error).message); } finally { setAiBusy(false); }
  };
  const stopReveal = () => window.clearInterval(revealTimer.current);
  useEffect(() => stopReveal, []);
  const SECTIONS = ["ag-viewer", "ag-table", "ag-review", "ag-report"];
  /** A recorded run is watched first; its results then load one section at a time, scrolling to each. */
  const watchRecorded = async (r: AgentSaved) => {
    setError(""); stopReveal();
    try {
      const loaded = await api.agentRun(r.run_id);
      setRecorded(true); setReveal(0); setRun(loaded); setReplaySignal(n => n + 1);
    } catch (e) { setError((e as Error).message); }
  };
  const onReplayEnd = () => {
    stopReveal(); let k = 0;
    revealTimer.current = window.setInterval(() => {
      k += 1; setReveal(k);
      window.setTimeout(() => document.getElementById(SECTIONS[k - 1])?.scrollIntoView({ behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }), 60);
      if (k >= SECTIONS.length) { window.clearInterval(revealTimer.current); setRecorded(false); }
    }, 1000);
  };
  const shown = (n: number) => !recorded || reveal >= n;

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
      <p className="cmp-note-plain"><strong>Run agent</strong> plays a real run from the beginning, step by step, then loads its results one section at a time. It replays a run recorded earlier on this server; nothing is computed now.</p>
      <ul>{saved.map(r => <li key={r.run_id}><div><strong>{r.earlier.split("_")[1]} · {r.earlier.split("_").pop()} → {r.later.split("_").pop()}</strong>
        <span>{r.months !== null ? `${r.months} months${r.target_months ? ` (≈${r.target_months})` : ""}` : ""} · {r.segmentation ? `${r.segmentation} segmentation` : "no segmentation yet"}</span></div>
        <div className="ag-saved-actions">
          <button className="ag-watch" onClick={() => watchRecorded(r)} disabled={!!run && BUSY.includes(run.state)} title="Plays the recorded run from the beginning, then loads the results one by one. Nothing is computed.">Run agent</button></div></li>)}</ul>
      <details className="ag-guide"><summary>Analyse your own scans: what you need</summary>
        <ul>
          <li><strong>Two scans of one person</strong> taken about 12, 15 or 18 months apart, as NIfTI or Analyze files, with the time between them recorded.</li>
          <li><strong>A computer with at least 2 CPU cores and 4 GB of memory.</strong> On a 2-core machine the alignment of one 256×256×128 pair took about 33 seconds and used about 0.8 GB; the rest of the analysis takes a few seconds.</li>
          <li><strong>The alignment package</strong> (<code>antspyx</code>) on Linux or macOS, or Ubuntu under Windows (WSL).</li>
          <li><strong>A segmentation of each scan from SynthSeg</strong>, run once outside NeuroTwin. Without it the alignment and quality review run, and the regional steps show as unavailable.</li>
          <li>Full steps are in <code>docs/LIVE_RUN_GUIDE.md</code>. Nothing is a diagnosis; a clinician reviews every report.</li></ul></details></section>}
    <AgentActivity refreshSignal={aiTick} liveSignal={liveSignal} replaySignal={replaySignal} onReplayEnd={onReplayEnd} runId={run?.run_id ?? null} onCancel={cancel} onOpenResult={openResult} />
    {!pairs.length ? (!saved.length && <div className="cmp-empty"><h2>No pair is ready</h2><p>Two visits of one person must be extracted locally first. See <code>docs/OASIS2_COMPARE.md</code>.</p></div>) : <>
      <div className="ag-pick cmp-controls">
        <label>Scan pair<select value={pair} onChange={e => setPair(e.target.value)} disabled={!!run && BUSY.includes(run.state)}>
          {pairs.map(p => <option key={p.earlier + p.later} value={`${p.earlier}|${p.later}`}>{p.subject_id} · {p.earlier.split("_").pop()} → {p.later.split("_").pop()} · {p.interval.months.toFixed(1)} months
            {p.interval.nearest_target_months ? ` (≈${p.interval.nearest_target_months})` : " (outside 12/15/18)"}{p.segmented ? " · segmented" : ""}</option>)}</select></label>
        <button className="ag-run" onClick={() => start()} disabled={!pair || (!!run && BUSY.includes(run.state))}>Run Agent Analysis</button>
      </div>
      {error && <p role="alert" className="cmp-note">{error}</p>}
    </>}

    {run && shown(1) && <section aria-label="Progress" className="ag-steps">
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

    {run?.alignment && shown(1) && <section className="ag-viewer" id="ag-viewer" aria-label="Compare scans">
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
      <div className="ag-align"><h3>Alignment</h3><AlignmentFit before={run.alignment.correlation_before} after={run.alignment.correlation_after} /><p>{run.alignment.method} ({run.alignment.tool}). Similarity {run.alignment.correlation_before} → {run.alignment.correlation_after};
        estimated head movement {run.alignment.rotation_deg}° and {run.alignment.shift_mm_voxel_frame} mm. Measured over {run.alignment.mask}.</p></div>
    </section>}

    {run && !hasSeg && run.alignment && shown(2) && <section className="ag-need" role="status"><h2>Regional measurements are unavailable</h2>
      <p>{run.steps.find(s => s.key === "anatomical_analysis")?.detail}</p></section>}

    {hasSeg && shown(2) && <section className="ag-table" id="ag-table"><h2>Regional volumes <small>{run!.segmentation_tool?.tool} {run!.segmentation_tool?.version}</small></h2>
      <p className="cmp-note-plain">{run!.measurements!.source}. {run!.noise?.status === "estimated"
        ? `A same-session repeat spread was estimated from ${run!.noise.earlier_repeats.length} earlier and ${run!.noise.later_repeats.length} later repeat scans. It is a lower bound, not a test of whether a change is real; every difference stays marked uncertain.`
        : "No repeat-scan spread exists, so uncertainty is not estimated and every difference is marked uncertain."}
        {run!.noise?.flags?.map(f => ` ${f}`)}{run!.noise?.skipped?.map(k => ` Left out ${k.scan}: ${k.reason}.`)}
        {" "}<button className="ag-watch" disabled={noiseBusy} onClick={async () => { setNoiseBusy(true); try { setRun(await api.agentNoise(run!.run_id)); } catch (e) { setError((e as Error).message); } finally { setNoiseBusy(false); } }}>{noiseBusy ? "Reading repeats…" : "Re-read repeat scans"}</button></p>
      <div className="ag-scroll"><table><thead><tr><th>Region</th><th>Earlier mm³</th><th>Later mm³</th><th>Difference</th><th>Repeat spread (SD)</th><th>Status</th></tr></thead><tbody>
        {regions.map(r => <tr key={r.label} className={r.label === region ? "ag-sel" : ""}>
          <td><button onClick={() => { setRegion(r.label === region ? 0 : r.label); if (!layers.includes("regions")) toggle("regions"); }}>{r.name}</button></td>
          <td>{r.earlier_mm3}</td><td>{r.later_mm3}</td><td>{r.difference_mm3} ({r.difference_pct === null ? "n/a" : `${r.difference_pct}%`})</td><td>{r.repeat ? `${r.repeat.sd_mm3} mm³ · ${r.repeat.ratio === null ? "spread 0" : `${r.repeat.ratio}× the spread`} · ${r.repeat.within_repeat_range ? "inside" : "outside"} repeat range` : "not estimated"}</td><td>{r.status}</td></tr>)}
      </tbody></table></div>
      <AgentCharts regions={regions} months={run!.validation.interval?.months ?? null} selected={region} totals={{ earlier: run!.measurements!.earlier_total_mm3, later: run!.measurements!.later_total_mm3 }}
        onSelect={l => { setRegion(l); if (l && !layers.includes("regions")) toggle("regions"); }} />
      {picked && <aside className="ag-evidence" aria-label="Evidence"><h3>Evidence: {picked.name}</h3>
        <p>{picked.earlier_voxels} voxels earlier, {picked.later_voxels} later; {picked.earlier_mm3} → {picked.later_mm3} mm³ ({picked.difference_mm3} mm³).
          Source: voxel counts of the {run!.segmentation_tool?.tool} {run!.segmentation_tool?.version} segmentation. Earlier value, recent value, difference and repeat spread are as listed above.</p>
        <ul>{picked.review_notes.map(n => <li key={n}>{n}</li>)}</ul></aside>}
    </section>}

    {run?.review && shown(3) && <section className="ag-review" id="ag-review"><h2>Findings review</h2>
      {run.review.flags.length ? <ul>{run.review.flags.map(f => <li key={f}>{f}</li>)}</ul> : <p>No whole-scan inconsistency was found by the review rules.</p>}
      <p className="cmp-note-plain">{run.review.note}</p></section>}

    {run?.report && shown(4) && <section className="ag-report" id="ag-report"><h2>Report <small>{run.report.status}</small></h2>
      <p className="cmp-note-plain">Written by a {run.report.author}. It restates the measurements above and adds nothing.</p>
      {Object.entries(run.report.sections).map(([k, items]) => <div key={k}><h3>{{ measured: "Largest measured differences", quality_limitations: "Quality limitations", processing: "Processing", suggested_follow_up: "Suggested follow-up for clinician consideration", needs_clinical_review: "Needs clinical review" }[k] ?? k}</h3>
        <ul>{items.map(i => <li key={i}>{i}</li>)}</ul></div>)}</section>}

    {run?.report && shown(4) && <section className="ag-ai" id="ag-ai" aria-label="AI explanation draft"><h2>AI explanation <small>draft, not reviewed</small></h2>
      <p className="cmp-note-plain">Optional. A language model (Gemini) writes an explanation from the numbered facts above; a rule-based checker refuses added numbers or claims, and a second model (Meta) checks each sentence. It is a draft for the clinician: not a diagnosis, not a prediction. English, or Arabic with fixed draft terms and a back-translation check; Arabic has not been reviewed by a native clinical reader.</p>
      {!ai && <div className="ag-actions"><label>Language<select value={aiLang} onChange={e => setAiLang(e.target.value as "en" | "ar")}><option value="en">English</option><option value="ar">العربية (Arabic)</option></select></label><button onClick={explain} disabled={aiBusy || aiStatus?.mode === "off"} title={aiStatus?.mode === "off" ? "No model provider is configured on this server." : ""}>{aiBusy ? "Drafting and checking…" : "Draft AI explanation"}</button>
        {aiStatus?.mode === "off" && <span className="cmp-note-plain">No model provider is configured on this server, so this agent cannot run.</span>}</div>}
      {ai && <div>
        <p className={`ag-ai-state ${ai.qa.passed ? "ok" : "blocked"}`} role="status"><strong>{ai.qa.passed ? "Passed the checks" : "Blocked by the checks"}</strong> · AI draft, not reviewed by a clinician
          {ai.explanation.scripted && " · scripted demo text, no model was used"}</p>
        {ai.explanation.statements.length > 0 && <ol className="ag-ai-list">{ai.explanation.statements.map((st, i) => { const c = ai.cross_check.items.find(x => x.index === i);
          const bt = ai.arabic?.back_translation.items.find(x => x.index === i);
          return <li key={i}><span lang={ai.language === "ar" ? "ar" : "en"} dir={ai.language === "ar" ? "rtl" : "ltr"}>{st.text}</span>{bt && <small lang="en" dir="ltr">Back-translation to English: {bt.english}{bt.ok ? "" : ` (differs: ${bt.flags.join(", ")})`}{ai.arabic?.back_translation.scripted ? " · scripted demo" : ""}</small>} <small>cites {st.cites.join(", ")}{c ? (ai.cross_check.scripted ? " · scripted demo, not checked" : c.supported ? " · second model: supported" : ` · second model: not supported (${c.reason})`) : ""}</small></li>; })}</ol>}
        {ai.explanation.status !== "completed" && <p className="cmp-note-plain">{ai.explanation.reason ?? ai.explanation.validator?.problems.map(p => p.detail).join(" ")}</p>}
        <ul className="ag-ai-checks">{ai.qa.checks.map(c => <li key={c.name}><strong>{c.ok ? (c.warning ? "Warning" : "Passed") : "Failed"}</strong> {c.name}: {c.detail}</li>)}</ul>
        {ai.arabic && <p className="cmp-note-plain" role="note">Arabic terms: {ai.arabic.glossary_note}</p>}
        <p className="cmp-note-plain">Drafted by {ai.explanation.model ?? "no model"}{ai.cross_check.model ? `, checked by ${ai.cross_check.model}` : ""}. {ai.note}</p>
        <div className="ag-actions"><button onClick={explain} disabled={aiBusy}>{aiBusy ? "Drafting and checking…" : "Draft again"}</button></div></div>}
    </section>}

    {run?.report && shown(4) && <section className="ag-ai ag-vis" id="ag-vis" aria-label="AI visual comparison"><h2>AI visual comparison <small>impressions, not measured</small></h2>
      <p className="cmp-note-plain">Optional. A model (Gemini) looks at the same slices of both scans and points at places where the pictures seem to differ; a second model (Meta) reads them too, and rules refuse pointers on empty background or with forbidden wording. A pointer is drawn only if it matches one of the largest measured differences. These are unvalidated impressions, not findings, not a diagnosis.</p>
      {!vis && <div className="ag-actions">
        {visInfo?.mode !== "mock" && <label><input type="checkbox" checked={visOk} onChange={e => setVisOk(e.target.checked)} />I agree that key slices (images) of both scans are sent to Gemini and Meta.</label>}
        <button onClick={look} disabled={visBusy || visInfo?.mode === "off" || (visInfo?.mode !== "mock" && (!visOk || !visInfo?.images_allowed))}>{visBusy ? "Looking and checking…" : "Compare the scans with AI"}</button>
        {visInfo?.mode === "off" && <span className="cmp-note-plain">No model provider is configured on this server.</span>}
        {visInfo && visInfo.mode === "live" && !visInfo.images_allowed && <span className="cmp-note-plain">Sending images is switched off on this server (NEUROTWIN_AGENTS_SEND_IMAGES).</span>}</div>}
      {vis && <div>
        <p className={`ag-ai-state ${vis.observer.status === "completed" ? "ok" : "blocked"}`} role="status"><strong>{vis.observer.status === "completed" ? `${vis.observations.length} impression(s)` : "No result"}</strong> · AI, not reviewed by a clinician
          {vis.observer.scripted && " · scripted demo, no image was looked at"}{vis.observer.status !== "completed" && ` · ${vis.observer.reason ?? vis.observer.status}`}</p>
        <div className="ag-actions"><label><input type="checkbox" checked={showMeasured} onChange={e => setShowMeasured(e.target.checked)} />Measured change (rule-based)</label>
          <label><input type="checkbox" checked={showModel} onChange={e => setShowModel(e.target.checked)} />Model impressions (not measured)</label></div>
        {vis.observer.status === "completed" && <div className="ag-vis-grid">{vis.slices.map(sl => { const q = `axis=${sl.axis}&index=${sl.index}`, mine = vis.observations.filter(o => o.slice === sl.id && o.drawn);
          return <figure key={sl.id}><figcaption><strong>{sl.id} · {sl.view} slice {sl.index}</strong><span>{sl.reason}</span></figcaption>
            <div className="ag-vis-pair"><div className="ag-vis-img"><img src={`${base(run.run_id)}/slice.png?layer=earlier&${q}`} alt={`Earlier scan, ${sl.view} slice ${sl.index}`} /><em>Earlier</em></div>
              <div className="ag-vis-img"><img src={`${base(run.run_id)}/slice.png?layer=later_aligned&${q}`} alt={`Later scan aligned, ${sl.view} slice ${sl.index}`} />
                {showMeasured && <img className="ag-ov" src={`${base(run.run_id)}/overlay.png?layer=change&${q}`} alt="" />}
                {showModel && <svg className="ag-vis-marks" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{mine.map(o => <g key={o.index}><ellipse cx={o.x * 100} cy={o.y * 100} rx="5" ry="5" /><text x={o.x * 100 + 6} y={o.y * 100 - 5}>{o.index + 1}</text></g>)}</svg>}
                <em>Later, aligned</em></div></div></figure>; })}</div>}
        {vis.observations.length > 0 && <ol className="ag-ai-list">{vis.observations.map(o => <li key={o.index} value={o.index + 1}><span>{o.description || "(no description)"}</span>
          <small><strong>{o.status === "supported" ? (o.drawn ? "Drawn · matches a large measured difference" : "Matches a measured difference · needs a look") : o.status === "unsupported" ? "Listed, not drawn · not among the largest measured differences" : "Refused by the rules"}</strong>
            {" · "}{o.slice}{o.cites.length ? ` · cites ${o.cites.join(", ")}` : ""}{o.cross ? ` · second reader: ${o.cross.verdict.replace("_", " ")}${vis.cross_check.scripted ? " (scripted, not checked)" : ""}` : ""}{o.status === "rejected" ? ` · ${o.reason}` : ""}</small></li>)}</ol>}
        <p className="cmp-note-plain">Second reader: {vis.cross_check.status === "completed" ? `${vis.cross_check.model}` : `not cross-checked (${vis.cross_check.reason ?? vis.cross_check.status})`}. {vis.note}</p>
        <div className="ag-actions"><button onClick={look} disabled={visBusy}>{visBusy ? "Looking and checking…" : "Compare again"}</button></div></div>}
    </section>}

    {run?.report && shown(4) && <section className="ag-ai ag-rev" id="ag-rev" aria-label="AI review and questions"><h2>AI review and questions <small>drafts, not reviewed</small></h2>
      <p className="cmp-note-plain">Optional. A quality reviewer says whether the pair is fit to compare (a fixed rule sets the least cautious answer it may give); a challenger lists reasons a difference may be noise and questions to ask. You can also ask a question: it is answered only from numbered facts of this run, and questions about diagnosis, prediction, normal ranges or treatment are refused. Drafts by Gemini; not a diagnosis.</p>
      {!rev && <div className="ag-actions"><button onClick={runReview} disabled={revBusy || revMode === "off"}>{revBusy ? "Reviewing…" : "Run the AI review"}</button>
        {revMode === "off" && <span className="cmp-note-plain">No model provider is configured on this server.</span>}</div>}
      {rev && <div>
        <h3>Quality reviewer <small>{rev.quality.status === "completed" ? "" : rev.quality.status}</small></h3>
        <p className={`ag-ai-state ${rev.quality.verdict === "proceed" ? "ok" : "blocked"}`} role="status"><strong>{(rev.quality.verdict ?? rev.quality.gate).replace(/_/g, " ")}</strong>
          {rev.quality.overridden_by_gate ? ` · the model said ${rev.quality.model_verdict?.replace(/_/g, " ")}, but the rules require at least ${rev.quality.gate.replace(/_/g, " ")}` : ""}{rev.quality.scripted ? " · scripted demo text" : ""}{rev.quality.status !== "completed" && ` · ${rev.quality.reason ?? "the claim checker refused the draft"} (rule gate: ${rev.quality.gate.replace(/_/g, " ")})`}</p>
        {rev.quality.gate_reasons.length > 0 && <p className="cmp-note-plain">Rule gate: {rev.quality.gate_reasons.join(" ")}</p>}
        <ul className="ag-ai-list">{rev.quality.statements.map((x, i) => <li key={i}><span>{x.text}</span> <small>cites {x.cites.join(", ")}</small></li>)}</ul>
        <h3>Findings challenger <small>{rev.challenge.status === "completed" ? "" : rev.challenge.status}</small></h3>
        {rev.challenge.doubts.length > 0 && <><h4>Reasons to doubt</h4><ul className="ag-ai-list">{rev.challenge.doubts.map((x, i) => <li key={i}><span>{x.text}</span> <small>cites {x.cites.join(", ")}</small></li>)}</ul></>}
        {rev.challenge.questions.length > 0 && <><h4>Questions to ask</h4><ul className="ag-ai-list">{rev.challenge.questions.map((x, i) => <li key={i}><span>{x.text}</span> <small>cites {x.cites.join(", ")}</small></li>)}</ul></>}
        {rev.challenge.status !== "completed" && <p className="cmp-note-plain">{rev.challenge.reason ?? rev.challenge.validator?.problems.map(p => p.detail).join(" ") ?? ""}</p>}
        <p className="cmp-note-plain">{rev.note}</p>
        <div className="ag-actions"><button onClick={runReview} disabled={revBusy}>{revBusy ? "Reviewing…" : "Review again"}</button></div></div>}
      <h3>Ask the evidence</h3>
      <form className="ag-ask" onSubmit={e => { e.preventDefault(); ask(); }}>
        <label>Your question about this run<input value={question} maxLength={300} onChange={e => setQuestion(e.target.value)} placeholder="For example: why is the right amygdala marked small?" disabled={askBusy || revMode === "off"} /></label>
        <button type="submit" disabled={askBusy || !question.trim() || revMode === "off"}>{askBusy ? "Looking it up…" : "Ask"}</button></form>
      <ol className="ag-chat" aria-label="Questions and answers">{chat.map((c, i) => <li key={i}><p><strong>Q:</strong> {c.question}</p>
        {c.answer.length > 0 ? <ul className="ag-ai-list">{c.answer.map((x, j) => <li key={j}><span>{x.text}</span> <small>cites {x.cites.join(", ")}</small></li>)}</ul> : <p className="cmp-note-plain">{c.note || c.status.replace(/_/g, " ")}</p>}
        <small>{c.tools.length ? `Looked up: ${c.tools.map(t => t.name + (t.arg ? ` (${t.arg})` : "")).join(", ")}. ` : ""}{c.status === "refused" ? "Refused before any model was called. " : ""}{c.scripted ? "Scripted demo text. " : ""}AI draft, not reviewed.</small></li>)}</ol>
    </section>}

    {run?.report && shown(4) && cr && <section className="ag-ai ag-cr" id="ag-cr" aria-label="Clinician review"><h2>Clinician review <small>{cr.state.replace(/_/g, " ")}</small></h2>
      <p className="cmp-note-plain">Nothing written by a model counts until you accept it. Accept or reject each item below; approving records your decision under your account. It covers the accepted AI items and the draft report, and is not a clinical approval of any care. Regenerating a draft makes its items undecided again.</p>
      <div className="ag-actions"><button onClick={() => crDo(() => api.agentFollowup(run.run_id))} disabled={crBusy || revMode === "off"}>{cr.followup ? "Draft follow-up suggestions again" : "Draft follow-up suggestions (AI)"}</button>
        {cr.followup && cr.followup.status !== "completed" && <span className="cmp-note-plain">Follow-up: {cr.followup.reason ?? cr.followup.status}</span>}</div>
      {cr.items.length === 0 ? <p className="cmp-note-plain">No AI item is waiting for a decision. Draft an explanation, follow-up suggestions or a visual comparison above first.</p> :
        <ul className="ag-cr-list">{cr.items.map(it => <li key={it.id} className={it.decision ?? ""}><span><em>{({ explanation: "Explanation", followup: "Follow-up", visual: "Visual impression" })[it.kind]}</em> {it.text} <small>cites {it.cites.join(", ")}</small></span>
          <span className="ag-cr-btns"><button aria-pressed={it.decision === "accepted"} disabled={crBusy} onClick={() => crDo(() => api.agentDecideItem(run.run_id, it.id, it.decision === "accepted" ? "cleared" : "accepted"))}>Accept</button>
            <button aria-pressed={it.decision === "rejected"} disabled={crBusy} onClick={() => crDo(() => api.agentDecideItem(run.run_id, it.id, it.decision === "rejected" ? "cleared" : "rejected"))}>Reject</button></span></li>)}</ul>}
      <p className="cmp-note-plain" role="status">{cr.accepted} accepted · {cr.undecided} undecided{cr.approval ? ` · ${cr.approval.decision} by ${cr.approval.by} on ${cr.approval.at.slice(0, 10)}${cr.approval.comment ? `: ${cr.approval.comment}` : ""}` : ""}{cr.approval_outdated ? " · the drafts changed after approval, so the approval is outdated" : ""}</p>
      <div className="ag-actions"><label>Comment<input value={crComment} maxLength={500} onChange={e => setCrComment(e.target.value)} /></label>
        <button disabled={crBusy || cr.undecided > 0} onClick={() => crDo(() => api.agentDecide(run.run_id, "approve", crComment))} title={cr.undecided ? "Decide every item first." : ""}>Approve</button>
        <button disabled={crBusy || !crComment.trim()} onClick={() => crDo(() => api.agentDecide(run.run_id, "return", crComment))} title={crComment.trim() ? "" : "Write what should change."}>Return with comment</button>
        {cr.approval && <button disabled={crBusy} onClick={() => crDo(() => api.agentDecide(run.run_id, "reopen", ""))}>Reopen</button>}</div>
    </section>}

    {run?.report && shown(4) && fam && <section className="ag-ai ag-fam" id="ag-fam" aria-label="Family summary"><h2>Family summary <small>only after approval and consent</small></h2>
      <p className="cmp-note-plain">Optional. A model (Gemini) drafts a short, plain summary for one authorised family member. You read it, then release it. It is shown to the family member only while you have approved the review, the participant has agreed to share a scan-comparison summary, and the participant authorised that family member; if any of these ends, it disappears for them. English or Arabic; an Arabic summary is released only after you confirm that you have read it in Arabic.</p>
      <ol className="ag-fam-checks" aria-label="Conditions">{fam.preconditions.map(c => <li key={c.name} className={c.ok ? "ok" : "no"}><strong>{c.ok ? "Met" : "Not met"}</strong> {c.name}: {c.detail}</li>)}</ol>
      {!fam.link && <div className="ag-actions"><label>Participant this run concerns<select value={famPart} onChange={e => setFamPart(e.target.value)}><option value="">Choose…</option>{fam.participants.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <button disabled={famBusy || !famPart} onClick={() => famDo(() => api.agentFamilyLink(run.run_id, famPart))}>Link this run</button>
        {fam.participants.length === 0 && <span className="cmp-note-plain">No participant has shared their record with you for clinical review.</span>}</div>}
      {fam.link && <>
        <fieldset className="ag-fam-pick"><legend>Facts the summary may mention (at most two, optional)</legend>
          {[["F-total", "Total volume"], ["F-vent", "Ventricle share"], ...regions.slice(0, 6).map(r => [`F-R${r.label}`, r.name])].map(([id, name]) => <label key={id}><input type="checkbox" checked={famPick.includes(id)} disabled={!famPick.includes(id) && famPick.length >= 2}
            onChange={() => setFamPick(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])} />{name}</label>)}</fieldset>
        <div className="ag-actions"><label>Language<select value={famLang} onChange={e => setFamLang(e.target.value as "en" | "ar")}><option value="en">English</option><option value="ar">العربية (Arabic)</option></select></label><button disabled={famBusy || revMode === "off"} onClick={() => famDo(() => api.agentFamilyDraft(run.run_id, famPick, famLang))}>{fam.draft ? "Draft again" : "Draft the family summary (AI)"}</button></div>
        {fam.draft && <div><p className={`ag-ai-state ${fam.draft.status === "completed" ? "ok" : "blocked"}`} role="status"><strong>{fam.draft.status === "completed" ? "Draft ready for you to read" : "No usable draft"}</strong>{fam.draft.scripted && " · scripted demo text"}{fam.draft.status !== "completed" && ` · ${fam.draft.reason ?? fam.draft.validator?.problems.map(p => p.detail).join(" ")}`}</p>
          <div className="ag-fam-text" lang={fam.draft.language === "ar" ? "ar" : "en"} dir={fam.draft.language === "ar" ? "rtl" : "ltr"}>{fam.draft.statements.map((st, i) => <p key={i}>{st.text}</p>)}</div>
          {fam.draft.arabic && <div lang="en" dir="ltr" className="cmp-note-plain"><p><strong>Back-translation to English{fam.draft.arabic.back_translation.scripted ? " (scripted demo)" : ""}:</strong></p>
            <ol>{fam.draft.arabic.back_translation.items.map(i => <li key={i.index}>{i.english}{i.ok ? "" : ` (differs: ${i.flags.join(", ")})`}</li>)}</ol><p>{fam.draft.arabic.glossary_note}</p></div>}
          {fam.draft.status === "completed" && <div className="ag-actions"><label>Release to<select value={famTo} onChange={e => { setFamTo(e.target.value); loadFam(e.target.value); }}><option value="">Choose a family member…</option>{fam.family.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
            {fam.draft.language === "ar" && <label className="ag-fam-read"><input type="checkbox" checked={famRead} onChange={e => setFamRead(e.target.checked)} />I read Arabic and have read this summary in Arabic</label>}
            <button disabled={famBusy || !famTo || fam.preconditions.some(c => !c.ok) || !!fam.draft.release || (fam.draft.language === "ar" && !famRead)} onClick={() => famDo(() => api.agentFamilyRelease(run.run_id, famTo, famRead))}>Release to this family member</button>
            {fam.draft.release && <button disabled={famBusy} onClick={() => famDo(() => api.agentFamilyWithdraw(run.run_id))}>Withdraw the release</button>}</div>}
          {fam.draft.release && <p className="cmp-note-plain" role="status">Released on {fam.draft.release.at.slice(0, 10)}. It stays visible to the family member only while every condition above holds.</p>}</div>}
      </>}
    </section>}
  </section>;
}
