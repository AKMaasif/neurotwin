import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Circle, FileUp, Lock, RefreshCw } from "lucide-react";
import { imagingPost } from "../api";
import { getResearch } from "./data";
import { useT } from "../i18n";

type Stage = { id: string; name: string; status: string; detail: string };
type Result = { shape: number[]; source_shape: number[]; source_spacing_mm: number[]; display_spacing_mm: number[];
  source_affine: number[][]; display_affine: number[][]; axis_codes: string[] | null; spatial_frame_explicit: boolean;
  display_percentiles: number[]; anatomical_qc: string };
type Run = { id: string; scan_id: string; subject: string; status: string; stages: Stage[];
  findings: { code: string; severity: string; message: string }[]; result: Result | null; error: string | null;
  files: { original_name: string; stored_name: string; bytes: number; sha256: string }[]; retryable: boolean;
  created_at: string; producer_version: string; parent_run_id: string | null };
const statusText = (s: string) => s.replace(/_/g, " ");

function NativeSlices({ run }: { run: Run }) {
  const { t } = useT();
  const result = run.result!;
  const [volume, setVolume] = useState<Uint8Array | null>(null), [error, setError] = useState("");
  const [cursor, setCursor] = useState(result.shape.map(n => Math.floor(n / 2)));
  const refs = useRef<(HTMLCanvasElement | null)[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    getResearch(`native/runs/${run.id}/volume`, controller.signal).then(r => r.arrayBuffer()).then(buffer => {
      if (buffer.byteLength !== result.shape.reduce((a, b) => a * b, 1)) throw new Error("Prepared volume size disagrees with its manifest.");
      setVolume(new Uint8Array(buffer));
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [run.id, result]);
  useEffect(() => {
    if (!volume) return;
    const [nx, ny, nz] = result.shape;
    [0, 1, 2].forEach(axis => {
      const canvas = refs.current[axis]; if (!canvas) return;
      const w = axis === 0 ? ny : nx, h = axis === 2 ? ny : nz;
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d"); if (!ctx) return;
      const image = ctx.createImageData(w, h);
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const c = axis === 0 ? [cursor[0], x, nz - 1 - y] : axis === 1 ? [x, cursor[1], nz - 1 - y] : [x, ny - 1 - y, cursor[2]];
        const value = volume[(c[0] * ny + c[1]) * nz + c[2]];
        const p = (y * w + x) * 4;
        image.data[p] = image.data[p + 1] = image.data[p + 2] = value; image.data[p + 3] = 255;
      }
      ctx.putImageData(image, 0, 0);
    });
  }, [volume, cursor, result]);
  if (error) return <p role="alert">{error}</p>;
  return <div className="native-preview"><div className="native-preview-head"><strong>{t("nvHead")}</strong><span>{t("nvNoSeg")}</span></div>
    {!volume && <p role="status">{t("nvLoadVol")}</p>}
    <div className="native-slices">{[0, 1, 2].map(axis => {
      const axes = axis === 0 ? [1, 2] : axis === 1 ? [0, 2] : [0, 1];
      const ratio = result.shape[axes[0]] * result.display_spacing_mm[axes[0]] / (result.shape[axes[1]] * result.display_spacing_mm[axes[1]]);
      return <section key={axis}><header><strong>{result.axis_codes?.join("") === "RAS" ? [t("nvSag"), t("nvCor"), t("nvAx")][axis] : t("nvVoxAxis", { n: axis + 1 })}</strong>
        <span>{cursor[axis] + 1}/{result.shape[axis]}</span></header>
        <div><canvas ref={el => { refs.current[axis] = el; }} style={{ aspectRatio: `${ratio}`, width: "100%", height: "auto" }} aria-label={t("nvCanvas", { n: axis + 1 })} /></div>
        <input aria-label={t("nvSliceAria", { n: axis + 1 })} type="range" min={0} max={result.shape[axis] - 1} value={cursor[axis]}
          onChange={e => setCursor(c => c.map((v, i) => i === axis ? +e.target.value : v))} />
      </section>;
    })}</div>
    <p>{result.spatial_frame_explicit ? t("nvOriented") : t("nvUnverified")}</p>
  </div>;
}

export default function NativeWorkflow() {
  const { t } = useT();
  const [runs, setRuns] = useState<Run[]>([]), [selectedId, setSelectedId] = useState<string | null>(null);
  const [available, setAvailable] = useState(true), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [files, setFiles] = useState<File[]>([]), [confirmed, setConfirmed] = useState(false);
  const [loaded, setLoaded] = useState(false), [refresh, setRefresh] = useState(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const body = await (await getResearch("native/runs", controller.signal)).json();
        if (controller.signal.aborted) return;
        setRuns(body.runs); setAvailable(body.available); setLoaded(true);
        setSelectedId(id => id && body.runs.some((r: Run) => r.id === id) ? id : body.runs[0]?.id ?? null);
        if (body.runs.some((r: Run) => ["queued", "running"].includes(r.status))) timer = setTimeout(poll, 1200);
      } catch (e) { if (!controller.signal.aborted) { setError((e as Error).message); setLoaded(true); } }
    };
    poll(); return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);
  const selected = runs.find(r => r.id === selectedId);
  const act = async (path: string, body?: FormData) => {
    setBusy(true); setError("");
    try { const run = await imagingPost<Run>(path, body); if (mounted.current) { setSelectedId(run.id); setRefresh(n => n + 1); } }
    catch (e) { if (mounted.current) setError((e as Error).message); }
    finally { if (mounted.current) setBusy(false); }
  };
  const importFiles = () => {
    if (files.reduce((n, f) => n + f.size, 0) > 80 * 1024 * 1024) { setError(t("nvTooBig")); return; }
    const body = new FormData(); body.append("confirmed", "true"); files.forEach(f => body.append("files", f)); act("import", body);
  };
  return <section className="native-workflow">
    <div className="native-title"><div><p className="brain-eyebrow">NEUROTWIN NATIVE / 0.1</p><h1>{t("nvTitle")}</h1>
      <p>{t("nvSub")}</p></div><button onClick={() => setRefresh(n => n + 1)}><RefreshCw size={15} /> {t("nvRefresh")}</button></div>
    <div className="native-boundary"><strong>{t("nvBoundaryH")}</strong><span>{t("nvBoundary")}</span></div>
    {error && <div className="native-error" role="alert">{error}</div>}
    {!available && <div className="native-error">{t("nvNotInstalled")}</div>}
    <div className="native-import-grid"><section className="native-card"><h2><FileUp size={17} /> {t("nvImportH")}</h2>
      <p>{t("nvImportP")}</p>
      <input aria-label={t("nvFilesAria")} type="file" multiple accept=".nii,.gz,.hdr,.img" onChange={e => setFiles(Array.from(e.target.files || []))} />
      <label className="brain-check"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> {t("nvConfirm")}</label>
      <button className="native-primary" disabled={busy || !available || !confirmed || !files.length} onClick={importFiles}>{busy ? t("nvSubmitting") : t("nvImportBtn")}</button>
      <small>{t("nvLimit")}</small></section>
      <section className="native-card"><h2>{t("nvExistH")}</h2><p>{t("nvExistP1")}</p>
        <p>{t("nvExistP2")}</p>
        <button disabled={busy || !available} onClick={() => act("sample")}>{busy ? t("nvSubmitting") : t("nvExistBtn")}</button>
        <small>{t("nvExistNote")}</small></section></div>
    <div className="native-run-heading"><h2>{t("nvHistory")}</h2>{runs.length > 0 && <select aria-label={t("nvAttemptAria")} value={selectedId || ""} onChange={e => setSelectedId(e.target.value)}>
      {runs.map(r => <option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString()} · {statusText(r.status)} · {r.id.slice(0, 8)}</option>)}</select>}</div>
    {!loaded ? <p role="status">{t("nvLoadHist")}</p> : !selected ? <div className="native-empty">{t("nvNoRuns")}</div> : <>
      <div className="native-run-summary"><div><strong>{t("nvAttempt", { id: selected.id.slice(0, 8) })}</strong><small>{selected.producer_version} · {selected.files.map(f => f.original_name).join(" + ")}</small></div>
        <span className={`native-status ${selected.status}`}>{statusText(selected.status)}</span>
        {["queued", "running"].includes(selected.status) && <button disabled={busy} onClick={() => act(`runs/${selected.id}/cancel`)}>{t("nvCancel")}</button>}
        {(selected.retryable || selected.status === "cancelled") && <button disabled={busy} onClick={() => act(`runs/${selected.id}/retry`)}>{t("nvRetry")}</button>}</div>
      {selected.error && <div className="native-error" role="alert">{selected.error}</div>}
      <ol className="native-stages">{selected.stages.map((stage, i) => <li key={stage.id} className={`native-stage ${stage.status}`}>
        <span className="native-step-icon">{stage.status === "succeeded" ? <CheckCircle2 size={20} /> : stage.status === "blocked" ? <Lock size={18} /> : <Circle size={19} />}</span>
        <div><strong>{i + 1}. {stage.name}</strong><p>{stage.detail}</p></div><span className="native-stage-status">{statusText(stage.status)}</span></li>)}</ol>
      {selected.findings.length > 0 && <section className="native-card native-findings"><h2>{t("nvReview")}</h2><ul>{selected.findings.map(f => <li key={f.code}>{f.message}</li>)}</ul></section>}
      {selected.result && selected.status === "awaiting_review" && <NativeSlices key={selected.id} run={selected} />}
      {selected.result && <section className="native-card"><h2>{t("nvGeomH")}</h2><dl className="native-facts"><dt>{t("nvDimOrig")}</dt><dd>{selected.result.source_shape.join(" × ")}</dd>
        <dt>{t("nvSpacing")}</dt><dd>{selected.result.source_spacing_mm.map(v => v.toFixed(3)).join(" × ")} mm</dd><dt>{t("nvDimDisp")}</dt><dd>{selected.result.shape.join(" × ")}</dd>
        <dt>{t("nvTransform")}</dt><dd>{selected.result.spatial_frame_explicit ? t("nvExplicit") : t("nvUnverifiedO")}</dd>
        <dt>{t("nvScaling")}</dt><dd>{t("nvScalingV")}</dd></dl>
        <details><summary>{t("nvChecksums")}</summary>{selected.files.map(f => <p key={f.stored_name} className="brain-checksums"><strong>{f.original_name}</strong><code>{f.sha256}</code></p>)}</details></section>}
    </>}
  </section>;
}
