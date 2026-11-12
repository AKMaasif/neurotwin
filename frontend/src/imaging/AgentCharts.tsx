import { useState } from "react";
import { AgentRegion } from "../api";

/**
 * Charts for the regional volume comparison. Every chart restates numbers from the table; none adds an estimate.
 * Uncertainty is not estimated by this pipeline, so no error bars, normal ranges or good/bad colours are drawn.
 * Colours: direction uses blue (smaller later) and orange (larger later), a neutral pair that does not mean good or bad.
 */
const SMALLER = "#2a78d6", LARGER = "#eb6834", LEFT = "#6250d6", RIGHT = "#008300";
const GROUPS: { key: string; name: string; color: string; test: (n: string) => boolean }[] = [
  { key: "wm", name: "Cerebral white matter", color: "#2a78d6", test: n => /cerebral white matter/.test(n) },
  { key: "cx", name: "Cerebral cortex", color: "#1baf7a", test: n => /cerebral cortex/.test(n) },
  { key: "cb", name: "Cerebellum", color: "#6250d6", test: n => /cerebellum/.test(n) },
  { key: "dp", name: "Deep structures and brain-stem", color: "#eda100", test: n => /thalamus|caudate|putamen|pallidum|hippocampus|amygdala|accumbens|ventral dc|brain-stem/.test(n) },
  { key: "vt", name: "Ventricles", color: "#e87ba4", test: n => /ventricle/.test(n) },
];
const SMALL_MM3 = 1500;  // below this, one voxel of boundary error moves the percentage a lot

const fmt = (n: number) => Math.round(n).toLocaleString("en-US");
const pct = (n: number | null) => n === null ? "n/a" : `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
const niceStep = (max: number) => { const raw = max / 4, p = 10 ** Math.floor(Math.log10(raw)); const f = raw / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; };
const span = (max: number) => { const s = niceStep(max); return { step: s, lim: Math.ceil(max / s) * s }; };
const title = (n: string) => n.charAt(0).toUpperCase() + n.slice(1);

type Props = { regions: AgentRegion[]; months: number | null; selected: number; onSelect: (label: number) => void; totals: { earlier: number; later: number } };

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return <details className="agc-table"><summary>View as table</summary><div className="ag-scroll"><table><thead><tr>{head.map(h => <th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table></div></details>;
}

/** Percentage or absolute change per region as bars from a zero line. */
function ChangeBars({ regions, mode, selected, onSelect, perYear }: { regions: AgentRegion[]; mode: "pct" | "mm3"; selected: number; onSelect: (l: number) => void; perYear: number | null }) {
  const [hover, setHover] = useState<AgentRegion | null>(null);
  const val = (r: AgentRegion) => mode === "pct" ? (r.difference_pct ?? 0) : r.difference_mm3;
  const rows = [...regions].filter(r => mode === "mm3" || r.difference_pct !== null).sort((a, b) => Math.abs(val(b)) - Math.abs(val(a)));
  const { step, lim } = span(Math.max(...rows.map(r => Math.abs(val(r))), 1) * 1.3);
  const L = 200, R = 60, W = 640, rowH = 22, T = 8, B = 34, H = T + rows.length * rowH + B, inner = W - L - R;
  const x = (v: number) => L + ((v + lim) / (2 * lim)) * inner, zero = x(0);
  const ticks: number[] = []; for (let t = -lim; t <= lim + 1e-9; t += step) ticks.push(Math.round(t * 1e6) / 1e6);
  const unit = mode === "pct" ? "%" : "";
  const label = (r: AgentRegion) => mode === "pct" ? pct(r.difference_pct) : `${r.difference_mm3 > 0 ? "+" : ""}${fmt(r.difference_mm3)} mm³`;
  return <div className="agc-chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={mode === "pct" ? "Percentage change in volume for each measured region, largest change first" : "Change in volume in cubic millimetres for each measured region, largest change first"}>
      {ticks.map(t => <g key={t}><line x1={x(t)} x2={x(t)} y1={T} y2={H - B} className="agc-grid" /><text x={x(t)} y={H - B + 16} textAnchor="middle" className="agc-tick">{t > 0 ? "+" : ""}{fmt(t)}{unit}</text></g>)}
      <line x1={zero} x2={zero} y1={T} y2={H - B} className="agc-base" />
      {rows.map((r, i) => {
        const v = val(r), y = T + i * rowH, up = v >= 0, small = r.earlier_mm3 < SMALL_MM3, w = Math.abs(x(v) - zero), c = up ? LARGER : SMALLER;
        const showVal = i < 5 || r.label === selected;
        return <g key={r.label} className={`agc-row${r.label === selected ? " sel" : ""}`} tabIndex={0} role="button" aria-pressed={r.label === selected}
          aria-label={`${title(r.name)}: ${label(r)}, ${fmt(r.earlier_mm3)} to ${fmt(r.later_mm3)} cubic millimetres${small ? ", small structure" : ""}. Select to show on the scan.`}
          onClick={() => onSelect(r.label === selected ? 0 : r.label)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(r.label === selected ? 0 : r.label); } }}
          onMouseEnter={() => setHover(r)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(r)} onBlur={() => setHover(null)}>
          <rect x={0} y={y} width={W} height={rowH} className="agc-hit" />
          <text x={L - 8} y={y + rowH / 2 + 4} textAnchor="end" className="agc-name">{title(r.name)}{small ? " †" : ""}</text>
          {w > 0 && <rect x={up ? zero : zero - w} y={y + 4} width={Math.max(w, 1)} height={14} rx={3} fill={small ? "none" : c} stroke={c} strokeWidth={small ? 2 : 0} className="agc-bar" />}
          {showVal && <text x={up ? zero + w + 6 : zero - w - 6} y={y + rowH / 2 + 4} textAnchor={up ? "start" : "end"} className="agc-val">{label(r)}</text>}
        </g>;
      })}
    </svg>
    <p className="agc-readout" aria-live="polite">{hover ? <><strong>{title(hover.name)}</strong>: {fmt(hover.earlier_mm3)} → {fmt(hover.later_mm3)} mm³ ({label(hover)}){hover.earlier_mm3 < SMALL_MM3 ? ", small structure" : ""}</> : "Hover or focus a bar for its volumes. Select a bar to show that region on the scans."}</p>
    <ul className="agc-legend" aria-label="Legend">
      <li><span className="agc-sw" style={{ background: SMALLER }} />Smaller in the later scan</li>
      <li><span className="agc-sw" style={{ background: LARGER }} />Larger in the later scan</li>
      <li><span className="agc-sw hollow" style={{ borderColor: "#52514e" }} />† Small structure (under {fmt(SMALL_MM3)} mm³): a hollow bar, because a few voxels move the percentage a lot</li></ul>
    {perYear !== null && mode === "pct" && <p className="cmp-note-plain">Interval: {perYear} months. The bars show the change over that interval, not a yearly rate.</p>}
    <Table head={["Region", "Earlier mm³", "Later mm³", mode === "pct" ? "Change %" : "Change mm³"]} rows={rows.map(r => [title(r.name), fmt(r.earlier_mm3), fmt(r.later_mm3), mode === "pct" ? pct(r.difference_pct) : fmt(r.difference_mm3)])} />
  </div>;
}

/** Left and right of each paired structure on one percentage scale. */
function LeftRight({ regions }: { regions: AgentRegion[] }) {
  const names = [...new Set(regions.map(r => r.name.replace(/^(left|right) /, "")))];
  const pairs = names.map(n => ({ n, l: regions.find(r => r.name === `left ${n}`), r: regions.find(r => r.name === `right ${n}`) }))
    .filter((p): p is { n: string; l: AgentRegion; r: AgentRegion } => !!p.l && !!p.r && p.l.difference_pct !== null && p.r.difference_pct !== null)
    .sort((a, b) => Math.abs((b.l.difference_pct ?? 0) - (b.r.difference_pct ?? 0)) - Math.abs((a.l.difference_pct ?? 0) - (a.r.difference_pct ?? 0)));
  if (!pairs.length) return null;
  const { step, lim } = span(Math.max(...pairs.flatMap(p => [Math.abs(p.l.difference_pct!), Math.abs(p.r.difference_pct!)]), 1));
  const L = 200, R = 24, W = 640, rowH = 24, T = 8, B = 34, H = T + pairs.length * rowH + B, x = (v: number) => L + ((v + lim) / (2 * lim)) * (W - L - R);
  const ticks: number[] = []; for (let t = -lim; t <= lim + 1e-9; t += step) ticks.push(Math.round(t * 1e6) / 1e6);
  return <div className="agc-chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Percentage change of the left and right side of each paired structure, largest left-right gap first">
      {ticks.map(t => <g key={t}><line x1={x(t)} x2={x(t)} y1={T} y2={H - B} className="agc-grid" /><text x={x(t)} y={H - B + 16} textAnchor="middle" className="agc-tick">{t > 0 ? "+" : ""}{fmt(t)}%</text></g>)}
      <line x1={x(0)} x2={x(0)} y1={T} y2={H - B} className="agc-base" />
      {pairs.map((p, i) => { const y = T + i * rowH + rowH / 2; return <g key={p.n}>
        <title>{`${title(p.n)}: left ${pct(p.l.difference_pct)}, right ${pct(p.r.difference_pct)}`}</title>
        <text x={L - 8} y={y + 4} textAnchor="end" className="agc-name">{title(p.n)}</text>
        <line x1={x(p.l.difference_pct!)} x2={x(p.r.difference_pct!)} y1={y} y2={y} className="agc-link" />
        <circle cx={x(p.l.difference_pct!)} cy={y} r={5} fill={LEFT} className="agc-dot" />
        <circle cx={x(p.r.difference_pct!)} cy={y} r={5} fill={RIGHT} className="agc-dot" /></g>; })}
    </svg>
    <ul className="agc-legend" aria-label="Legend"><li><span className="agc-sw round" style={{ background: LEFT }} />Left side</li><li><span className="agc-sw round" style={{ background: RIGHT }} />Right side</li></ul>
    <Table head={["Structure", "Left %", "Right %", "Gap (points)"]} rows={pairs.map(p => [title(p.n), pct(p.l.difference_pct), pct(p.r.difference_pct), Math.abs(p.l.difference_pct! - p.r.difference_pct!).toFixed(1)])} />
  </div>;
}

/** How the measured volume is divided between tissue groups, earlier and later, as two tall segmented bars. */
function Composition({ regions }: { regions: AgentRegion[] }) {
  const totals = (k: "earlier_mm3" | "later_mm3") => GROUPS.map(g => ({ ...g, v: regions.filter(r => g.test(r.name)).reduce((s, r) => s + r[k], 0) }));
  const rows = [{ name: "Earlier scan", parts: totals("earlier_mm3") }, { name: "Later scan", parts: totals("later_mm3") }];
  const W = 640, L = 100, bw = W - L - 8;
  const bar = (parts: { key: string; name: string; color: string; v: number }[], y: number, name: string) => {
    const sum = parts.reduce((s, p) => s + p.v, 0); let off = L;
    return <g role="img" aria-label={`${name}: ${parts.map(p => `${p.name} ${(100 * p.v / sum).toFixed(1)}%`).join(", ")}`}>
      <text x={L - 10} y={y + 19} textAnchor="end" className="agc-name">{name}</text>
      {parts.map(p => { const w = (p.v / sum) * bw, x0 = off; off += w; const share = `${(100 * p.v / sum).toFixed(0)}%`;
        return <g key={p.key}><title>{`${p.name}: ${fmt(p.v)} mm³, ${(100 * p.v / sum).toFixed(1)}%`}</title>
          <rect x={x0 + 1} y={y} width={Math.max(w - 2, 0)} height={28} rx={4} fill={p.color} />
          {w > 44 && <text x={x0 + 8} y={y + 19} className="agc-in" fill={p.key === "dp" ? "#0b0b0b" : "#ffffff"}>{share}</text>}</g>; })}
    </g>;
  };
  return <div className="agc-chart">
    <svg viewBox={`0 0 ${W} 86`} role="group" aria-label="Share of the measured volume by tissue group, earlier and later scan">
      {bar(rows[0].parts, 6, rows[0].name)}{bar(rows[1].parts, 48, rows[1].name)}</svg>
    <ul className="agc-legend" aria-label="Legend">{GROUPS.map(g => <li key={g.key}><span className="agc-sw" style={{ background: g.color }} />{g.name}</li>)}</ul>
    <p className="cmp-note-plain">Shares of the structures that were measured, not of the whole head. A share inside a block is printed only where it fits; every value is in the table.</p>
    <Table head={["Group", "Earlier mm³", "Earlier share", "Later mm³", "Later share"]} rows={GROUPS.map((g, i) => {
      const a = rows[0].parts[i].v, b = rows[1].parts[i].v, sa = rows[0].parts.reduce((s, p) => s + p.v, 0), sb = rows[1].parts.reduce((s, p) => s + p.v, 0);
      return [g.name, fmt(a), `${(100 * a / sa).toFixed(1)}%`, fmt(b), `${(100 * b / sb).toFixed(1)}%`]; })} />
  </div>;
}

export default function AgentCharts({ regions, months, selected, onSelect, totals }: Props) {
  const [mode, setMode] = useState<"pct" | "mm3">("pct");
  const change = totals.earlier ? (100 * (totals.later - totals.earlier) / totals.earlier) : null;
  return <section className="ag-charts" aria-label="Charts of the regional volume comparison">
    <h3>Charts</h3>
    <p className="cmp-note-plain">These charts only redraw the table above. Uncertainty is not estimated, so they show no error bars and no normal range, and colour shows direction only; it does not mean better or worse. Not a diagnosis.</p>
    <figure><figcaption><strong>Which regions changed most</strong>
      <span role="group" aria-label="Chart units" className="agc-switch"><button aria-pressed={mode === "pct"} onClick={() => setMode("pct")}>Percent</button><button aria-pressed={mode === "mm3"} onClick={() => setMode("mm3")}>Cubic millimetres</button></span></figcaption>
      <ChangeBars regions={regions} mode={mode} selected={selected} onSelect={onSelect} perYear={months} />
      {mode === "mm3" && <p className="cmp-note-plain">In cubic millimetres the large structures dominate; small structures look unchanged even when their percentage is large. Switch to percent to compare them.</p>}</figure>
    <figure><figcaption><strong>Left against right</strong></figcaption>
      <p className="cmp-note-plain">Each line joins the left and right change of one structure. A long line means the two sides changed differently over this interval.</p><LeftRight regions={regions} /></figure>
    <figure><figcaption><strong>Share of measured volume by tissue group</strong></figcaption><Composition regions={regions} />
      {change !== null && <p className="cmp-note-plain">Total of the measured structures: {fmt(totals.earlier)} → {fmt(totals.later)} mm³ ({pct(change)}).</p>}</figure>
  </section>;
}

/** Image similarity before and after alignment, on its 0 to 1 scale. */
export function AlignmentFit({ before, after }: { before: number; after: number }) {
  const W = 420, L = 8, R = 8, x = (v: number) => L + v * (W - L - R);
  return <figure className="agc-fit"><svg viewBox={`0 0 ${W} 52`} role="img" aria-label={`Image similarity ${before} before alignment and ${after} after alignment, on a scale from 0 to 1`}>
    <line x1={x(0)} x2={x(1)} y1={20} y2={20} className="agc-base" />
    <line x1={x(before)} x2={x(after)} y1={20} y2={20} className="agc-link" />
    <circle cx={x(before)} cy={20} r={5} fill="#898781" className="agc-dot" /><circle cx={x(after)} cy={20} r={5} fill="#2a78d6" className="agc-dot" />
    <text x={x(0)} y={46} className="agc-tick">0</text><text x={x(1)} y={46} textAnchor="end" className="agc-tick">1</text>
    <text x={x(before)} y={10} textAnchor={before <= after ? "end" : "start"} className="agc-val">before {before}</text><text x={x(after)} y={10} textAnchor={before <= after ? "start" : "end"} className="agc-val">after {after}</text></svg>
    <figcaption className="cmp-note-plain">Similarity of the two scans (correlation) before and after alignment. It shows how well they were aligned, not a brain finding.</figcaption></figure>;
}
