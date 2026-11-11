import { useEffect, useMemo, useState } from "react";
import { api, Oasis2Subject, Oasis2Visit } from "../api";

const AXES = [0, 1, 2] as const;  // voxel axes; anatomical names are not shown because orientation is unverified
const slice = (mri: string, axis: number, index: number) => `/api/imaging/oasis2/visits/${mri}/slice.png?axis=${axis}&index=${index}`;
const years = (days: number) => (days / 365.25).toFixed(2);
const show = (v: number | null | undefined, digits?: number) => v === null || v === undefined ? "missing" : digits === undefined ? String(v) : v.toFixed(digits);

/** Level 2: imported nWBV at each recorded visit. Needs three or more visits; otherwise it says so. Descriptive only. */
function Trend({ subject }: { subject: Oasis2Subject }) {
  const pts = subject.visits.filter(v => v.imported_measures.nWBV !== null).map(v => ({ x: v.delay_days / 365.25, y: v.imported_measures.nWBV as number, id: v.mri_id }));
  if (pts.length < 3) return <section className="cmp-trend"><h2>Trend over visits</h2>
    <p role="status">Not enough visits to describe a trend. {subject.subject_id} has {pts.length} recorded {pts.length === 1 ? "visit" : "visits"}; at least three are needed.</p></section>;
  const W = 520, H = 180, pad = 36, xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys) - 0.01, y1 = Math.max(...ys) + 0.01;
  const sx = (x: number) => pad + ((x - x0) / (x1 - x0 || 1)) * (W - 2 * pad), sy = (y: number) => H - pad - ((y - y0) / (y1 - y0 || 1)) * (H - 2 * pad);
  const mx = xs.reduce((a, b) => a + b) / xs.length, my = ys.reduce((a, b) => a + b) / ys.length;
  const slope = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0) / xs.reduce((a, x) => a + (x - mx) ** 2, 0);
  return <section className="cmp-trend"><h2>Trend over visits</h2>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Imported nWBV at ${pts.length} visits over ${(x1 - x0).toFixed(1)} years`}>
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="#8aa0b2" /><line x1={pad} y1={pad / 2} x2={pad} y2={H - pad} stroke="#8aa0b2" />
      <polyline fill="none" stroke="#2f7f95" strokeWidth="2" points={pts.map(p => `${sx(p.x)},${sy(p.y)}`).join(" ")} />
      {pts.map(p => <g key={p.id}><circle cx={sx(p.x)} cy={sy(p.y)} r="5" fill="#12304a" /><text x={sx(p.x)} y={sy(p.y) - 10} fontSize="11" textAnchor="middle" fill="#12304a">{p.y.toFixed(3)}</text></g>)}
      <text x={W / 2} y={H - 8} fontSize="11" textAnchor="middle" fill="#3d566b">years since the first visit</text>
      <text x="12" y={H / 2} fontSize="11" transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle" fill="#3d566b">nWBV (imported)</text>
    </svg>
    <p>Across these {pts.length} visits the imported value changed by about {slope.toFixed(4)} per year on average (a straight line through the points).</p>
    <p className="cmp-note-plain">Descriptive only. nWBV comes from the OASIS table; its measurement variability is not known here, so no uncertainty range, no abnormal/normal call and no forecast is given.</p>
  </section>;
}

/** Two visits of one person side by side. Observed images only: no registration, no prediction. */
export default function CompareVisits() {
  const [list, setList] = useState<Oasis2Subject[] | null>(null), [error, setError] = useState("");
  const [sid, setSid] = useState(""), [a, setA] = useState(""), [b, setB] = useState("");
  const [axis, setAxis] = useState<(typeof AXES)[number]>(2), [index, setIndex] = useState(64), [failed, setFailed] = useState<string[]>([]);
  useEffect(() => { api.oasis2Subjects().then(r => {
    setList(r.subjects); const first = r.subjects.find(s => s.ready); if (first) pick(first);
  }).catch(e => setError(e.message)); }, []);
  const subject = list?.find(s => s.subject_id === sid);
  const prepared = subject?.visits.filter(v => v.prepared) ?? [];
  const va = prepared.find(v => v.mri_id === a), vb = prepared.find(v => v.mri_id === b);
  function pick(s: Oasis2Subject) {
    const ready = s.visits.filter(v => v.prepared); setSid(s.subject_id); setFailed([]);
    setA(ready[0]?.mri_id ?? ""); setB(ready[ready.length - 1]?.mri_id ?? "");
  }
  const [shape, setShape] = useState<number[] | null>(null);
  useEffect(() => { setShape(null); if (a) api.oasis2Info(a).then(r => setShape(r.shape)).catch(() => setShape(null)); }, [a]);
  const sliceCount = shape ? shape[axis] : 128;  // the server still refuses an index outside the real volume
  useEffect(() => { setIndex(Math.floor(sliceCount / 2)); setFailed([]); }, [sliceCount, axis]);
  const gap = useMemo(() => va && vb ? Math.abs(vb.delay_days - va.delay_days) : null, [va, vb]);

  if (error) return <section className="brain-loading" role="alert"><h1>Visit comparison is not ready on this server</h1><p>{error}</p>
    <p>The OASIS-2 manifest and at least one subject's scans must be prepared on the server (see docs/OASIS2_COMPARE.md).</p></section>;
  if (!list) return <section className="brain-loading" role="status"><h1>Opening OASIS-2 visits</h1><progress aria-label="Loading" /></section>;
  const readyCount = list.filter(s => s.ready).length;

  const panel = (v: Oasis2Visit | undefined, label: string) => v && <figure className="cmp-panel">
    <figcaption><strong>{label} · {v.mri_id.split("_").pop()}</strong><span>day {v.delay_days} · {years(v.delay_days)} years from the first visit</span></figcaption>
    {failed.includes(v.mri_id + axis + index)
      ? <div className="cmp-fail" role="alert">No image at this slice for this visit.</div>
      : <img src={slice(v.mri_id, axis, index)} alt={`Slice ${index} along voxel axis ${axis + 1} of ${v.mri_id}`} onError={() => setFailed(f => [...f, v.mri_id + axis + index])} />}
    <dl><dt>Age</dt><dd>{show(v.clinical.Age)}</dd><dt>MMSE</dt><dd>{show(v.clinical.MMSE)}</dd><dt>CDR</dt><dd>{show(v.clinical.CDR)}</dd>
      <dt>nWBV</dt><dd>{show(v.imported_measures.nWBV, 3)} <em>imported</em></dd></dl>
  </figure>;

  return <section className="cmp">
    <header><p className="brain-eyebrow">SAME PERSON · TWO VISITS</p><h1>Compare visits</h1>
      <p>Observed anatomy only. The values under each image come from the OASIS table and are imported, not measured by NeuroTwin. Nothing here is a diagnosis or a prediction.</p></header>
    {!readyCount ? <div className="cmp-empty"><h2>No subject is ready to compare</h2>
      <p>Two visits of a subject must be extracted locally. See <code>docs/OASIS2_COMPARE.md</code> for the one command that prepares a few subjects.</p></div> : <>
      <div className="cmp-controls">
        <label>Person<select value={sid} onChange={e => { const s = list.find(x => x.subject_id === e.target.value); if (s) pick(s); }}>
          {list.filter(s => s.ready).map(s => <option key={s.subject_id} value={s.subject_id}>{s.subject_id} · {s.visits.length} visits</option>)}</select></label>
        <label>Earlier<select value={a} onChange={e => setA(e.target.value)}>{prepared.map(v => <option key={v.mri_id} value={v.mri_id}>{v.mri_id.split("_").pop()} · day {v.delay_days}</option>)}</select></label>
        <label>Later<select value={b} onChange={e => setB(e.target.value)}>{prepared.map(v => <option key={v.mri_id} value={v.mri_id}>{v.mri_id.split("_").pop()} · day {v.delay_days}</option>)}</select></label>
        <fieldset><legend>Slice along</legend>{AXES.map(x => <label key={x}><input type="radio" name="axis" checked={axis === x} onChange={() => setAxis(x)} />Voxel axis {x + 1}</label>)}</fieldset>
        <label>Slice {index}<input type="range" min={0} max={sliceCount - 1} value={index} onChange={e => setIndex(+e.target.value)} /></label>
      </div>
      {va && vb && va.mri_id === vb.mri_id && <p className="cmp-note" role="status">The same visit is chosen on both sides. Pick two different visits to compare.</p>}
      {gap !== null && gap > 0 && <p className="cmp-gap">{years(gap)} years between these two visits (from the dataset's recorded delay).{gap < 365 && " This is under a year."}</p>}
      <div className="cmp-grid">{panel(va, "Earlier")}{panel(vb, "Later")}</div>
      {subject && <Trend subject={subject} />}
      <ul className="cmp-limits">
        <li><strong>Not registered.</strong> The two images are not aligned, so the same slice number may show different anatomy. Do not read differences between panels as change.</li>
        <li><strong>Orientation not verified.</strong> These raw files are Analyze format and the views are in voxel axes, not confirmed left/right.</li>
        <li><strong>Which visits.</strong> Each visit has several repeat scans; the first (mpr-1) is shown. Repeats are not extra time points.</li>
        <li>No segmentation, volume change or forecast is computed here.</li>
      </ul></>}
  </section>;
}
