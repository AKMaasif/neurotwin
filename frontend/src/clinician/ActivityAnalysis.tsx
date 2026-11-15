import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Cpu, Sparkles, UserRound, X } from "lucide-react";
import { AaRoster, AaRun, AaStage, ActivityCoverage, api, ClinicianParticipant, Evidence } from "../api";
import { useT } from "../i18n";
import { ErrorNote } from "../ui";

type Decision = "keep" | "discard" | "edit";
const RANGES: [number, string][] = [[42, "chRange6w"], [91, "chRange3m"], [183, "chRange6m"]];
const MEASURE_VERSION: Record<string, string> = { rt_median_ms: "0.1", sleep_hours: "0.1", sleep_quality: "0.1", rounds_correct: "0.1", who5_raw: "1998-en" };
const KIND_ICON = { software: Cpu, ai: Sparkles, human: UserRound } as const;
const DAY = 864e5;

/** "Analyze activity history": a clinician-started, evidence-linked review. Shows who does each step (software, AI model, clinician),
 *  what every claim rests on, and records only the clinician's own decisions. Nothing is started by opening this page. */
export default function ActivityAnalysis({ person, evidence, onClose, onReport }: { person: ClinicianParticipant; evidence: Evidence[]; onClose: () => void; onReport: () => void }) {
  const { t } = useT();
  const [roster, setRoster] = useState<AaRoster | null>(null);
  const [coverage, setCoverage] = useState<ActivityCoverage | null>(null);
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
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const chartsRef = useRef<HTMLElement>(null);
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => { api.aaRoster().then(setRoster).catch(setError); api.aaRuns(person.id).then(setPrev).catch(() => undefined); }, [person.id]);
  useEffect(() => { let active = true; setCoverage(null); api.aaCoverage(person.id, range).then(r => { if (active) setCoverage(r); }).catch(e => { if (active) setError(e); }); return () => { active = false; }; }, [person.id, range]);
  useEffect(() => { dialog.current?.focus(); }, []);
  // Follow a running analysis. This reads server state only; it never starts or repeats a model call.
  useEffect(() => {
    if (!run || !["queued", "running"].includes(run.state)) return;
    const id = window.setInterval(() => { api.aaRun(run.run_id).then(setRun).catch(setError); }, 1200);
    return () => window.clearInterval(id);
  }, [run?.run_id, run?.state]);   // eslint-disable-line react-hooks/exhaustive-deps

  const cancel = async () => { if (!run) return; setBusy(true); setError(null); try { setRun(await api.aaCancel(run.run_id)); } catch (e) { setError(e); } finally { setBusy(false); } };
  const retry = async () => { if (!run) return; setBusy(true); setError(null); setDec({}); setTexts({}); try { setRun(await api.aaRetry(run.run_id)); } catch (e) { setError(e); } finally { setBusy(false); } };
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
    const decisions = Object.entries(dec).map(([k, decision]) => { const [kind, i] = k.split(":"); return { kind, index: Number(i), decision, ...(decision === "edit" ? { text: texts[k] ?? "" } : {}) }; });
    if (!decisions.length) { setMsg(t("aaNeedDecision")); return; }
    setBusy(true); setError(null);
    try { setRun(await api.aaReview(run.run_id, decisions, note)); setMsg(t("aaSaved")); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const mark = (kind: string, i: number) => reviewed ? run?.review?.decisions.find((d) => d.kind === kind && d.index === i)?.decision : dec[`${kind}:${i}`];
  const edited = (kind: string, i: number) => run?.review?.decisions.find((d) => d.kind === kind && d.index === i && d.decision === "edit")?.text;
  const pick = (kind: string, i: number, d: Decision) => setDec((x) => ({ ...x, [`${kind}:${i}`]: d }));

  const Cites = ({ cites }: { cites: string[] }) => (
    <span className="aa-cites">
      <span className="muted">{t("aaCites")}:</span>
      {cites.map((c) => <button key={c} type="button" className="aa-cite" aria-expanded={open === c} onClick={() => setOpen(open === c ? null : c)}>{c}</button>)}
      {cites.filter((c) => open === c).map((c) => <span key={c} className="aa-fact" dir="ltr" lang="en">{facts.get(c) ?? ""}</span>)}
    </span>
  );
  const Decide = ({ kind, i, original }: { kind: string; i: number; original?: string }) => {
    const v = mark(kind, i), key = `${kind}:${i}`, canEdit = kind !== "chart";
    const choices: Decision[] = canEdit ? ["keep", "edit", "discard"] : ["keep", "discard"];
    return (
      <>
        <span className="aa-decide" role="group" aria-label={`${t("aaKeep")} / ${t("aaEdit")} / ${t("aaDiscard")}`}>
          {choices.map((d) => (
            <button key={d} type="button" className="chip" aria-pressed={v === d} disabled={reviewed}
              onClick={() => { pick(kind, i, d); if (d === "edit") { setEditing(key); setTexts((x) => ({ ...x, [key]: x[key] ?? original ?? "" })); } }}>{t(d === "keep" ? "aaKeep" : d === "edit" ? "aaEdit" : "aaDiscard")}</button>
          ))}
        </span>
        {v === "edit" && !reviewed && editing === key && (
          <span className="aa-edit">
            <textarea className="note" aria-label={t("aaEdit")} value={texts[key] ?? ""} maxLength={600} onChange={(e) => setTexts((x) => ({ ...x, [key]: e.target.value }))} />
            <span className="hint">{t("aaEditNote")}</span>
          </span>
        )}
        {reviewed && edited(kind, i) && <span className="aa-edited"><b>{t("aaEdited")}:</b> {edited(kind, i)}</span>}
      </>
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
        {!run && coverage && <section aria-label={t("cjCoverage")} className="d-card">
          <h2>{t("cjCoverage")}</h2><p>{t("cjCoverageNote")}</p>
          <p><bdi>{coverage.period.from} – {coverage.period.to}</bdi> · {t("wsSession")}: {t.num(coverage.sessions)}</p>
          <p>{coverage.versions.join(" · ")}</p>
          <ul>{Object.entries(coverage.quality).map(([k, v]) => <li key={k}>{t.code(k)}: {t.num(v)}</li>)}</ul>
          {coverage.comparisons.map((c, i) => <p key={i}>{t.code(c.measure)} · {c.protocol_version} · {t.code(c.status)} ({t.num(c.eligible_n)})</p>)}
        </section>}
        {run?.source_status === "changed" && <p className="notice warn" role="alert">{t("cjChanged")}</p>}
        {run?.source_status === "unverified_legacy" && <p className="notice" role="status">{t("cjLegacy")}</p>}

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
            <AgentPanel run={run} done={done} expanded={expanded} setExpanded={setExpanded} roster={roster} busy={busy} onCancel={cancel} onRetry={retry}
              onCharts={() => chartsRef.current?.scrollIntoView({ block: "start" })} hasCharts={!!run.charts?.charts.length} onReport={onReport} />
            {run.state === "failed" && <p className="notice" role="alert">{t("aaFailedRun")}</p>}
            {run.state === "cancelled" && <p className="notice" role="status">{t("aaCancelledRun")}</p>}
            {run.state === "interrupted" && <p className="notice" role="alert">{t("aaInterruptedRun")}</p>}
            {run.retry_of && <p className="hint">{t("aaRetryOf", { id: run.retry_of })}</p>}
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
                    {!refused && <Decide kind="statement" i={i} original={s.text} />}
                  </li>))}
                </ol>
              </section>
            )}

            {run.challenge && (run.challenge.doubts.length > 0 || run.challenge.questions.length > 0) && (
              <section>
                {(["doubts", "questions"] as const).map((k) => run.challenge![k].length > 0 && (
                  <div key={k}><h2>{t(k === "doubts" ? "aaDoubts" : "aaQuestions")}</h2>
                    <ul className="aa-list">{run.challenge![k].map((s, i) => (
                      <li key={i}><p dir="ltr" lang="en">{s.text}</p><Cites cites={s.cites} /><Decide kind={k === "doubts" ? "doubt" : "question"} i={i} original={s.text} /></li>))}</ul>
                  </div>))}
              </section>
            )}

            {run.charts && run.charts.charts.length > 0 && (
              <section ref={chartsRef} tabIndex={-1}><h2>{t("aaCharts")}</h2>
                <p className="hint">{t("aaChartsNote")}</p>
                {run.charts.charts.map((c, i) => (
                  <div key={i} className="aa-chart">
                    <p dir="ltr" lang="en">{c.why}</p><Cites cites={c.cites} />
                    <button className="btn" aria-expanded={chartOpen === `${i}`} onClick={() => setChartOpen(chartOpen === `${i}` ? null : `${i}`)}>{t("aaOpenChart")}</button>
                    <Decide kind="chart" i={i} />
                    {chartOpen === `${i}` && <MiniChart measure={c.measure} range={c.range} evidence={evidence} runId={run.run_id} synthetic={!!person.dataset} cites={c.cites} person={person.display_name} />}
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

function AgentPanel({ run, done, expanded, setExpanded, roster, busy, onCancel, onRetry, onCharts, hasCharts, onReport }: { run: AaRun; done: number; expanded: boolean; setExpanded: (v: boolean) => void; roster: AaRoster | null;
  busy: boolean; onCancel: () => void; onRetry: () => void; onCharts: () => void; hasCharts: boolean; onReport: () => void }) {
  const { t } = useT();
  const verified = (s: AaStage) => roster?.stages.find((x) => x.id === s.id)?.verified;
  const byId = new Map(run.stages.map((s) => [s.id, s]));
  const depth = (s: AaStage): number => (s.deps?.length ? 1 + Math.max(...s.deps.map((d) => (byId.get(d) ? depth(byId.get(d)!) : 0))) : 0);
  const running = run.stages.find((s) => s.status === "running");
  const active = ["queued", "running"].includes(run.state);
  return (
    <section className="aa-panel" aria-label={t("aaPanel")}>
      <div className="aa-panel-head">
        <b>{t("aaPanel")}</b>
        <span className="muted">{t("aaRunId")} <span className="mono" dir="ltr">{run.run_id}</span> · {t("aaProgress", { done: t.num(done), total: t.num(run.stages.length) })}</span>
        {running && <span className="aa-now" role="status">{t(`aaStage_${running.id}` as "aaStage_collect")}…</span>}
        {active && <button className="btn" disabled={busy} onClick={onCancel}>{t("aaCancel")}</button>}
        {["failed", "interrupted", "cancelled"].includes(run.state) && <button className="btn primary" disabled={busy} onClick={onRetry}>{t("aaRetry")}</button>}
        <button className="btn" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}{t(expanded ? "aaCollapse" : "aaExpand")}</button>
      </div>
      <ol className={`aa-chain ${expanded ? "open" : ""}`} aria-live="polite" style={expanded ? { gridTemplateColumns: `repeat(${Math.max(...run.stages.map(depth)) + 1}, minmax(160px, 1fr))` } : undefined}>
        {run.stages.map((s) => {
          const Icon = KIND_ICON[s.kind];
          return (
            <li key={s.id} className={`aa-stage ${s.status} ${s.kind}`} style={expanded ? { gridColumn: depth(s) + 1 } : undefined}>
              <span className="aa-stage-head"><Icon size={14} aria-hidden="true" /> <span>{t(`aaStage_${s.id}` as "aaStage_collect")}</span>
                <span className="tag">{t(`aaKind_${s.kind}`)}</span> <span className={`aa-st ${s.status}`}>{t(`aaSt_${s.status}` as "aaSt_waiting")}</span></span>
              {expanded && (
                <span className="aa-stage-body">
                  <span className="muted">{t("aaAfter")}: {s.deps?.length ? s.deps.map((d) => t(`aaStage_${d}` as "aaStage_collect")).join(t.lang === "ar" ? "، " : ", ") : t("aaNone")}</span>
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
      {expanded && (
        <>
          <div className="aa-links"><span className="muted">{t("aaLinks")}:</span>
            {hasCharts && <button className="link" onClick={onCharts}>{t("aaGoCharts")}</button>}
            <button className="link" onClick={onReport}>{t("aaGoReport")}</button></div>
          <details open><summary>{t("aaTimeline")} ({run.events.length})</summary>
            <ol className="aa-events">{run.events.map((e, i) => (
              <li key={i}><span className="muted" dir="ltr">{t.date(e.at, true)}</span> · {e.stage ? t(`aaStage_${e.stage}` as "aaStage_collect") : "—"} · <b>{t(`aaSt_${e.status}` as "aaSt_waiting")}</b>
                {e.summary && <span dir="ltr" lang="en"> · {e.summary}</span>}</li>))}</ol>
          </details>
        </>
      )}
    </section>
  );
}

/** A chart a model proposed, drawn here from the recorded values. Its own scale; the same quality rules as the timeline. */
function MiniChart({ measure, range, evidence, runId, synthetic, cites, person }: { measure: string; range: string; evidence: Evidence[]; runId: string; synthetic: boolean; cites: string[]; person: string }) {
  const { t } = useT();
  const svgRef = useRef<SVGSVGElement>(null);
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
  const lines = [
    `${measure} · protocol ${version} · ${range} · ${pts.length} usable records (ids ${pts.map((e) => "#" + e.id).join(" ")})`,
    `Drawn by software from the recorded values. The chart was suggested by a model; the values were not. Run ${runId}. Facts: ${cites.join(", ")}.`,
    `${synthetic ? "Synthetic demonstration data. " : ""}Research prototype. Not a diagnosis or a prediction.`];
  const download = (name: string, body: string, type: string) => {
    const url = URL.createObjectURL(new Blob([body], { type })); const a = document.createElement("a");
    a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
  };
  const exportSvg = () => {
    if (!svgRef.current) return;
    const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    const inner = svgRef.current.innerHTML.replace(/var\(--line-soft\)/g, "#d8e0e6").replace(/var\(--muted\)/g, "#5b6b78").replace(/var\(--warn\)/g, "#b45309").replace(/var\(--navy\)/g, "#12304a");
    const out = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H + 62}" width="${W}" height="${H + 62}" font-family="sans-serif"><title>${esc(measure)}</title><rect width="100%" height="100%" fill="#fff"/>${inner}` +
      lines.map((l, i) => `<text x="${L}" y="${H + 14 + i * 16}" font-size="10" fill="#3d566b">${esc(l)}</text>`).join("") + `</svg>`;
    download(`${runId}-${measure}.svg`, out, "image/svg+xml");
  };
  const exportCsv = () => download(`${runId}-${measure}.csv`, [...lines.map((l) => "# " + l), "record_id,recorded_at,value,quality,status",
    ...rows.map((e) => [e.id, e.recorded_at, e.value_num, e.quality, e.status].join(","))].join("\n"), "text/csv");
  void person;
  return (
    <div className="aa-minichart">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t.code(measure)} style={{ direction: "ltr" }}>
        {[lo, (lo + hi) / 2, hi].map((v) => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--line-soft)" /><text x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{t.num(v, 1)}</text></g>)}
        <text x={L} y={H - 6} fontSize="11" fill="var(--muted)">{t.date(pts[0].recorded_at)}</text>
        <text x={W - R} y={H - 6} fontSize="11" fill="var(--muted)" textAnchor="end">{t.date(pts[pts.length - 1].recorded_at)}</text>
        {pts.length > 1 && <polyline fill="none" stroke="#b9c4cc" strokeWidth="1.25" points={pts.map((e) => `${x(e.recorded_at)},${y(e.value_num as number)}`).join(" ")} />}
        {pts.map((e) => e.quality === "doubtful"
          ? <circle key={e.id} cx={x(e.recorded_at)} cy={y(e.value_num as number)} r="4" fill="#fff" stroke="var(--warn)" strokeWidth="2"><title>{`${t.date(e.recorded_at)} · ${t.num(e.value_num as number, 1)} · ${t(`quality_${e.quality}`)} · #${e.id}`}</title></circle>
          : <circle key={e.id} cx={x(e.recorded_at)} cy={y(e.value_num as number)} r="4" fill="var(--navy)"><title>{`${t.date(e.recorded_at)} · ${t.num(e.value_num as number, 1)} · ${t(`quality_${e.quality}`)} · #${e.id}`}</title></circle>)}
      </svg>
      <div className="aa-export"><button className="btn" onClick={exportSvg}>{t("aaExportSvg")}</button><button className="btn" onClick={exportCsv}>{t("aaExportCsv")}</button></div>
      <details><summary>{t("aaTableOf")}</summary>
        <div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>{t("chColDate")}</th><th>{t("chColValue")}</th><th>{t("chColQuality")}</th><th>{t("chColRecord")}</th></tr></thead>
          <tbody>{[...rows].reverse().map((e) => <tr key={e.id}><td>{t.date(e.recorded_at, true)}</td><td>{t.num(e.value_num as number, 1)}</td><td>{t(`quality_${e.quality}`)}{e.status !== "current" ? ` · ${t(`status_${e.status}`)}` : ""}</td><td>#{e.id}</td></tr>)}</tbody></table></div>
      </details>
    </div>
  );
}
