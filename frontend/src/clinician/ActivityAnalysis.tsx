import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Cpu, Sparkles, UserRound, X } from "lucide-react";
import { AaRoster, AaRun, AaStage, api, ClinicianParticipant, Evidence } from "../api";
import { useT } from "../i18n";
import { ErrorNote } from "../ui";

type Decision = "keep" | "discard";
const RANGES: [number, string][] = [[42, "chRange6w"], [91, "chRange3m"], [183, "chRange6m"]];
const MEASURE_VERSION: Record<string, string> = { rt_median_ms: "0.1", sleep_hours: "0.1", sleep_quality: "0.1", rounds_correct: "0.1", who5_raw: "1998-en" };
const KIND_ICON = { software: Cpu, ai: Sparkles, human: UserRound } as const;
const DAY = 864e5;

/** "Analyze activity history": a clinician-started, evidence-linked review. Shows who does each step (software, AI model, clinician),
 *  what every claim rests on, and records only the clinician's own decisions. Nothing is started by opening this page. */
export default function ActivityAnalysis({ person, evidence, onClose }: { person: ClinicianParticipant; evidence: Evidence[]; onClose: () => void }) {
  const { t } = useT();
  const [roster, setRoster] = useState<AaRoster | null>(null);
  const [run, setRun] = useState<AaRun | null>(null);
  const [prev, setPrev] = useState<{ run_id: string; created_at: string; state: string; range_days: number; mode: string; reviewed: boolean }[]>([]);
  const [range, setRange] = useState(183);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [open, setOpen] = useState<string | null>(null);              // a fact id whose text is shown
  const [chartOpen, setChartOpen] = useState<string | null>(null);
  const [dec, setDec] = useState<Record<string, Decision>>({});
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => { api.aaRoster().then(setRoster).catch(setError); api.aaRuns(person.id).then(setPrev).catch(() => undefined); }, [person.id]);
  useEffect(() => { dialog.current?.focus(); }, []);
  // Follow a running analysis. This reads server state only; it never starts or repeats a model call.
  useEffect(() => {
    if (!run || !["queued", "running"].includes(run.state)) return;
    const id = window.setInterval(() => { api.aaRun(run.run_id).then(setRun).catch(setError); }, 1200);
    return () => window.clearInterval(id);
  }, [run?.run_id, run?.state]);   // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setBusy(true); setError(null); setMsg(""); setDec({}); setNote("");
    try { setRun(await api.aaStart(person.id, range)); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const openRun = (id: string) => { setError(null); setMsg(""); setDec({}); api.aaRun(id).then(setRun).catch(setError); };
  const facts = useMemo(() => new Map((run?.ledger?.facts ?? []).map((f) => [f.id, f.text])), [run?.ledger]);
  const mode = roster?.mode ?? run?.mode ?? "off";
  const done = run ? run.stages.filter((s) => ["completed", "skipped", "unavailable", "blocked", "failed"].includes(s.status)).length : 0;
  const reviewed = run?.state === "reviewed";
  const save = async () => {
    if (!run) return;
    const decisions = Object.entries(dec).map(([k, decision]) => { const [kind, i] = k.split(":"); return { kind, index: Number(i), decision }; });
    if (!decisions.length) { setMsg(t("aaNeedDecision")); return; }
    setBusy(true); setError(null);
    try { setRun(await api.aaReview(run.run_id, decisions, note)); setMsg(t("aaSaved")); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const mark = (kind: string, i: number) => reviewed ? run?.review?.decisions.find((d) => d.kind === kind && d.index === i)?.decision : dec[`${kind}:${i}`];
  const pick = (kind: string, i: number, d: Decision) => setDec((x) => ({ ...x, [`${kind}:${i}`]: d }));

  const Cites = ({ cites }: { cites: string[] }) => (
    <span className="aa-cites">
      <span className="muted">{t("aaCites")}:</span>
      {cites.map((c) => <button key={c} type="button" className="aa-cite" aria-expanded={open === c} onClick={() => setOpen(open === c ? null : c)}>{c}</button>)}
      {cites.filter((c) => open === c).map((c) => <span key={c} className="aa-fact" dir="ltr" lang="en">{facts.get(c) ?? ""}</span>)}
    </span>
  );
  const Decide = ({ kind, i }: { kind: string; i: number }) => {
    const v = mark(kind, i);
    return (
      <span className="aa-decide" role="group" aria-label={`${t("aaKeep")} / ${t("aaDiscard")}`}>
        {(["keep", "discard"] as Decision[]).map((d) => (
          <button key={d} type="button" className="chip" aria-pressed={v === d} disabled={reviewed} onClick={() => pick(kind, i, d)}>{t(d === "keep" ? "aaKeep" : "aaDiscard")}</button>
        ))}
      </span>
    );
  };
  const statusOf = (i: number) => {
    const c = run?.cross_check?.items.find((x) => x.index === i);
    return c && run?.cross_check?.status === "completed" ? (c.supported ? "yes" : "no") : "none";
  };
  const refused = run?.summary?.status === "refused";
  const problemsFor = (i: number) => run?.summary?.validator?.problems.filter((p) => p.index === i) ?? [];

  return (
    <div className="report-scrim" role="dialog" aria-modal="true" aria-labelledby="aa-h" onClick={onClose}>
      <article className="report aa" ref={dialog} tabIndex={-1} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
        <div className="bar">
          <div>
            <p className="eyebrow">{t("appName")} · <bdi>{person.display_name}</bdi>{person.dataset && <> · <span className="tag demo">{t("cSynLabel")}</span></>}</p>
            <h1 id="aa-h">{t("aaTitle")}</h1>
          </div>
          <button className="btn" onClick={onClose}><X size={16} aria-hidden="true" />{t("aaClose")}</button>
        </div>
        <ErrorNote error={error} />
        <p>{t("aaIntro")}</p>
        <p className="notice">{mode === "mock" ? t("aaModeMock") : mode === "live" ? t("aaModeLive") : t("aaModeOff")}</p>

        {!run && (
          <>
            <fieldset className="aa-range"><legend>{t("aaRange")}</legend>
              {RANGES.map(([d, k]) => <label key={d}><input type="radio" name="aa-range" checked={range === d} onChange={() => setRange(d)} /> {t(k as "chRange6w")}</label>)}
            </fieldset>
            <div><button className="btn primary" disabled={busy || !roster} onClick={start}>{busy ? t("aaRunning") : t("aaRun")}</button></div>
            {roster && (
              <>
                <h2>{t("aaWho")}</h2>
                <ol className="aa-who">
                  {roster.stages.map((s) => {
                    const Icon = KIND_ICON[s.kind];
                    return (
                      <li key={s.id}><Icon size={15} aria-hidden="true" /> <b>{t(`aaStage_${s.id}` as "aaStage_collect")}</b> <span className="tag">{t(`aaKind_${s.kind}`)}</span>
                        {s.kind === "ai" && <span className="muted"> · {s.scripted ? t("aaScripted") : s.verified ? t("aaVerified") : t("aaNotVerified")} · {s.prompt_version}</span>}</li>
                    );
                  })}
                </ol>
                <p className="hint">{roster.sends}</p>
              </>
            )}
            {prev.length > 0 && (
              <>
                <h2>{t("aaPrev")}</h2>
                <ul className="aa-prev">{prev.map((p) => (
                  <li key={p.run_id}><span dir="ltr" className="mono">{p.run_id}</span> · {t.date(p.created_at, true)} · {t(`aaSt_${p.state === "awaiting_review" ? "waiting" : p.state === "reviewed" ? "completed" : p.state}` as "aaSt_waiting")}
                    <button className="link" onClick={() => openRun(p.run_id)}>{t("aaOpenRun")}</button></li>))}</ul>
              </>
            )}
          </>
        )}

        {run && (
          <>
            <AgentPanel run={run} done={done} expanded={expanded} setExpanded={setExpanded} roster={roster} />
            {run.state === "failed" && <p className="notice" role="alert">{t("aaFailedRun")}</p>}
            {run.stages.find((s) => s.id === "ledger")?.status === "skipped" && <p className="muted">{t("aaNoRecords")}</p>}
            <p className="notice">{t("aaDraftNote")}</p>

            {run.gate && (
              <section><h2>{t("aaGate")}</h2>
                <ul className="aa-gate">{run.gate.checks.map((c) => <li key={c.name} className={c.ok ? "ok" : "bad"}><b>{c.name}</b> · {c.ok ? (c.warning ? "!" : "✓") : "✗"} <span dir="ltr" lang="en">{c.detail}</span></li>)}</ul>
              </section>
            )}

            {run.summary && run.summary.statements.length > 0 && (
              <section><h2>{t("aaStatements")}</h2>
                {refused && <p className="notice" role="alert">{t("aaRefused")}</p>}
                <ol className="aa-list">{run.summary.statements.map((s, i) => (
                  <li key={i} className={problemsFor(i).length ? "refused" : ""}>
                    <p dir="ltr" lang="en">{s.text}</p>
                    {problemsFor(i).length > 0 && <p className="hint" dir="ltr" lang="en">{problemsFor(i).map((p) => `${p.code}: ${p.detail}`).join(" · ")}</p>}
                    <Cites cites={s.cites} />
                    <span className="muted aa-check">{t(`aaChecked_${statusOf(i)}` as "aaChecked_yes")}</span>
                    {!refused && <Decide kind="statement" i={i} />}
                  </li>))}
                </ol>
              </section>
            )}

            {run.challenge && (run.challenge.doubts.length > 0 || run.challenge.questions.length > 0) && (
              <section>
                {(["doubts", "questions"] as const).map((k) => run.challenge![k].length > 0 && (
                  <div key={k}><h2>{t(k === "doubts" ? "aaDoubts" : "aaQuestions")}</h2>
                    <ul className="aa-list">{run.challenge![k].map((s, i) => (
                      <li key={i}><p dir="ltr" lang="en">{s.text}</p><Cites cites={s.cites} /><Decide kind={k === "doubts" ? "doubt" : "question"} i={i} /></li>))}</ul>
                  </div>))}
              </section>
            )}

            {run.charts && run.charts.charts.length > 0 && (
              <section><h2>{t("aaCharts")}</h2>
                <p className="hint">{t("aaChartsNote")}</p>
                {run.charts.charts.map((c, i) => (
                  <div key={i} className="aa-chart">
                    <p dir="ltr" lang="en">{c.why}</p><Cites cites={c.cites} />
                    <button className="btn" aria-expanded={chartOpen === `${i}`} onClick={() => setChartOpen(chartOpen === `${i}` ? null : `${i}`)}>{t("aaOpenChart")}</button>
                    <Decide kind="chart" i={i} />
                    {chartOpen === `${i}` && <MiniChart measure={c.measure} range={c.range} evidence={evidence} />}
                  </div>))}
                {run.charts.dropped.length > 0 && <p className="hint">{t("aaDropped", { n: run.charts.dropped.length })}</p>}
              </section>
            )}

            {run.ledger && (
              <details><summary>{t("aaFacts")} ({run.ledger.facts.length})</summary>
                <ul className="aa-facts" dir="ltr" lang="en">{run.ledger.facts.map((f) => <li key={f.id}><b className="mono">{f.id}</b> {f.text}</li>)}</ul></details>
            )}

            {run.state === "awaiting_review" || reviewed ? (
              <section className="aa-review">
                <label>{t("aaNote")}<textarea className="note" value={reviewed ? run.review?.note ?? "" : note} disabled={reviewed} maxLength={500} onChange={(e) => setNote(e.target.value)} /></label>
                {!reviewed && <button className="btn primary" disabled={busy} onClick={save}>{t("aaSave")}</button>}
                {msg && <p role="status">{msg}</p>}
              </section>
            ) : null}
          </>
        )}
      </article>
    </div>
  );
}

function AgentPanel({ run, done, expanded, setExpanded, roster }: { run: AaRun; done: number; expanded: boolean; setExpanded: (v: boolean) => void; roster: AaRoster | null }) {
  const { t } = useT();
  const verified = (s: AaStage) => roster?.stages.find((x) => x.id === s.id)?.verified;
  return (
    <section className="aa-panel" aria-label={t("aaPanel")}>
      <div className="aa-panel-head">
        <b>{t("aaPanel")}</b>
        <span className="muted">{t("aaRunId")} <span className="mono" dir="ltr">{run.run_id}</span> · {t("aaProgress", { done: t.num(done), total: t.num(run.stages.length) })}</span>
        <button className="btn" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}{t(expanded ? "aaCollapse" : "aaExpand")}</button>
      </div>
      <ol className={`aa-chain ${expanded ? "open" : ""}`} aria-live="polite">
        {run.stages.map((s) => {
          const Icon = KIND_ICON[s.kind];
          return (
            <li key={s.id} className={`aa-stage ${s.status} ${s.kind}`}>
              <span className="aa-stage-head"><Icon size={14} aria-hidden="true" /> <span>{t(`aaStage_${s.id}` as "aaStage_collect")}</span>
                <span className="tag">{t(`aaKind_${s.kind}`)}</span> <span className={`aa-st ${s.status}`}>{t(`aaSt_${s.status}` as "aaSt_waiting")}</span></span>
              {expanded && (
                <span className="aa-stage-body">
                  {s.summary && <span dir="ltr" lang="en">{s.summary}</span>}
                  <span className="muted">{t(`aaNote_${s.kind}` as "aaNote_ai")}</span>
                  {s.kind === "ai" && (
                    <span className="muted" dir="ltr">
                      {s.scripted ? t("aaScripted") : `${t("aaModel")}: ${s.provider ?? "–"} / ${s.model ?? "–"}`} · {t("aaPrompt")}: {s.prompt_version ?? "–"} · {s.scripted ? "" : verified(s) ? t("aaVerified") : t("aaNotVerified")}
                    </span>)}
                  {(s.started_at || s.ended_at) && <span className="muted">{s.started_at && `${t("aaStarted")}: ${t.date(s.started_at, true)}`}{s.ended_at && ` · ${t("aaEnded")}: ${t.date(s.ended_at, true)}`}</span>}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** A chart a model proposed, drawn here from the recorded values. Its own scale; the same quality rules as the timeline. */
function MiniChart({ measure, range, evidence }: { measure: string; range: string; evidence: Evidence[] }) {
  const { t } = useT();
  const version = MEASURE_VERSION[measure];
  const all = evidence.filter((e) => e.measure === measure && e.protocol_version === version && e.value_num !== null);
  const newest = all.length ? Math.max(...all.map((e) => Date.parse(e.recorded_at))) : 0;
  const days = range === "6w" ? 42 : range === "3m" ? 91 : range === "6m" ? 183 : Infinity;
  const rows = all.filter((e) => Date.parse(e.recorded_at) >= newest - days * DAY).sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
  const pts = rows.filter((e) => e.status === "current" && e.quality !== "unusable");
  const W = 560, H = 190, L = 44, R = 12, T = 14, B = 26;
  if (!pts.length) return <p className="hint">{t("chNoInRange")}</p>;
  const vs = pts.map((e) => e.value_num as number);
  let lo = Math.min(...vs), hi = Math.max(...vs);
  if (measure === "who5_raw") { lo = 0; hi = 25; } else if (measure === "sleep_quality") { lo = 1; hi = 5; } else if (measure === "rounds_correct") { lo = 0; hi = 4; } else if (lo === hi) { lo -= 1; hi += 1; }
  const t0 = Date.parse(pts[0].recorded_at), t1 = Date.parse(pts[pts.length - 1].recorded_at) || t0 + DAY;
  const x = (iso: string) => L + ((Date.parse(iso) - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  return (
    <div className="aa-minichart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t.code(measure)} style={{ direction: "ltr" }}>
        {[lo, (lo + hi) / 2, hi].map((v) => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--line-soft)" /><text x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{t.num(v, 1)}</text></g>)}
        <text x={L} y={H - 6} fontSize="11" fill="var(--muted)">{t.date(pts[0].recorded_at)}</text>
        <text x={W - R} y={H - 6} fontSize="11" fill="var(--muted)" textAnchor="end">{t.date(pts[pts.length - 1].recorded_at)}</text>
        {pts.length > 1 && <polyline fill="none" stroke="#b9c4cc" strokeWidth="1.25" points={pts.map((e) => `${x(e.recorded_at)},${y(e.value_num as number)}`).join(" ")} />}
        {pts.map((e) => e.quality === "doubtful"
          ? <circle key={e.id} cx={x(e.recorded_at)} cy={y(e.value_num as number)} r="4" fill="#fff" stroke="var(--warn)" strokeWidth="2"><title>{`${t.date(e.recorded_at)} · ${t.num(e.value_num as number, 1)} · ${t(`quality_${e.quality}`)} · #${e.id}`}</title></circle>
          : <circle key={e.id} cx={x(e.recorded_at)} cy={y(e.value_num as number)} r="4" fill="var(--navy)"><title>{`${t.date(e.recorded_at)} · ${t.num(e.value_num as number, 1)} · ${t(`quality_${e.quality}`)} · #${e.id}`}</title></circle>)}
      </svg>
      <details><summary>{t("aaTableOf")}</summary>
        <div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>{t("chColDate")}</th><th>{t("chColValue")}</th><th>{t("chColQuality")}</th><th>{t("chColRecord")}</th></tr></thead>
          <tbody>{[...rows].reverse().map((e) => <tr key={e.id}><td>{t.date(e.recorded_at, true)}</td><td>{t.num(e.value_num as number, 1)}</td><td>{t(`quality_${e.quality}`)}{e.status !== "current" ? ` · ${t(`status_${e.status}`)}` : ""}</td><td>#{e.id}</td></tr>)}</tbody></table></div>
      </details>
    </div>
  );
}
