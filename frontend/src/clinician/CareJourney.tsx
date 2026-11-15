import { useCallback, useEffect, useRef, useState } from "react";
import { api, CareJourney as Journey, CarePlanView } from "../api";
import { Key, useT } from "../i18n";
import { ErrorNote } from "../ui";

const OUTCOMES = ["open", "follow_up_required", "resolved", "referred", "closed_no_action"];

export default function CareJourney({ concernId, onClose, onAnalyze, onPlan }: {
  concernId: number; onClose: () => void; onAnalyze: (pid: string) => void; onPlan: (pid: string) => void;
}) {
  const { t } = useT();
  const [row, setRow] = useState<Journey | null>(null);
  const [plans, setPlans] = useState<CarePlanView[]>([]);
  const [runs, setRuns] = useState<{ run_id: string; created_at: string }[]>([]);
  const [plan, setPlan] = useState("");
  const [run, setRun] = useState("");
  const [action, setAction] = useState("");
  const [date, setDate] = useState("");
  const [outcome, setOutcome] = useState("open");
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const panel = useRef<HTMLElement>(null);
  const apply = (r: Journey) => {
    setRow(r); setPlan(r.plan ? String(r.plan.id) : ""); setRun(r.analysis?.run_id ?? "");
    setAction(r.next_action); setDate(r.follow_up_on ?? ""); setOutcome(r.outcome);
  };
  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api.journeyFromConcern(concernId);
      apply(r);
      const [p, a] = await Promise.all([api.carePlan(r.participant_id), api.aaRuns(r.participant_id)]);
      setPlans(p.plans); setRuns(a.filter(x => x.state === "reviewed"));
    } catch (e) { setError(e); }
  }, [concernId]);
  useEffect(() => {
    const launcher = document.activeElement as HTMLElement | null;
    load(); panel.current?.focus();
    return () => { if (launcher?.isConnected) launcher.focus(); };
  }, [load]);
  useEffect(() => {
    // Disabling the focused Save button can move focus to the document body.
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
    };
    window.addEventListener("keydown", escape, true);
    return () => window.removeEventListener("keydown", escape, true);
  }, [onClose]);
  const save = async () => {
    if (!row) return;
    setBusy(true); setError(null); setSaved(false);
    try {
      const r = await api.updateJourney(row.id, { expected_revision: row.revision, plan_id: plan ? +plan : null,
        // Do not re-link unchanged historical sources: users can still record follow-up when old evidence becomes stale.
        ...(run !== (row.analysis?.run_id ?? "") ? { analysis_run_id: run || null } : {}),
        next_action: action, follow_up_on: date || null, outcome, note });
      apply(r); setNote(""); setSaved(true);
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const trap = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); onClose(); }
    if (e.key !== "Tab" || !panel.current) return;
    const all = [...panel.current.querySelectorAll<HTMLElement>("button:not([disabled]),input,select,textarea")];
    const first = all[0], last = all[all.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
  };
  return <div className="report-scrim" role="dialog" aria-modal="true" aria-labelledby="cj-title" onKeyDown={trap}>
    <article className="report" ref={panel} tabIndex={-1}>
      <div className="bar"><h1 id="cj-title">{t("cjTitle")}{row ? ` #${row.id}` : ""}</h1><button className="btn" onClick={onClose}>{t("close")}</button></div>
      <p>{t("cjIntro")}</p><ErrorNote error={error} onRetry={load} />
      {!row ? <p role="status">{t("loading")}</p> : <>
        <p><b>{t("cjOwner")}:</b> {row.clinician} · <b>{t("cjConcern")}:</b> {t(`cnEv_${row.concern_status}` as Key)}</p>
        <div className="cj-grid">
          <label>{t("cjAnalysis")}<select value={run} onChange={e => setRun(e.target.value)}>
            <option value="">{t("cjNone")}</option>
            {row.analysis && !runs.some(r => r.run_id === row.analysis!.run_id) && <option value={row.analysis.run_id}>{row.analysis.run_id}</option>}
            {runs.map(r => <option key={r.run_id} value={r.run_id}>{r.run_id} · {t.date(r.created_at)}</option>)}
          </select></label>
          <label>{t("cjPlan")}<select value={plan} onChange={e => setPlan(e.target.value)}>
            <option value="">{t("cjNone")}</option>{plans.map(p => <option key={p.id} value={p.id}>#{p.id} · v{p.version} · {t.code(p.status)}</option>)}
          </select></label>
          <label>{t("cjAction")}<textarea value={action} maxLength={300} onChange={e => setAction(e.target.value)} /></label>
          <label>{t("cjDate")}<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
          <label>{t("cjOutcome")}<select value={outcome} onChange={e => setOutcome(e.target.value)}>{OUTCOMES.map(s => <option key={s} value={s}>{t(`cjState_${s}` as Key)}</option>)}</select></label>
          <label>{t("cjNote")}<textarea value={note} maxLength={500} onChange={e => setNote(e.target.value)} /></label>
        </div>
        {row.analysis && (row.analysis.source_status !== "current" || !row.analysis.review_unchanged) && <p className="notice warn" role="status">{t("cjStale")}</p>}
        <p>{t("cjResponses")}: {t("remDone")} {t.num(row.responses.done)} · {t("remNotToday")} {t.num(row.responses.not_today)} · {t.num(row.responses.difficulty)} {t.code("difficulty")}</p>
        <p className="hint">{t("cjBoundary")}</p>
        <div className="cj-actions"><button className="btn primary" disabled={busy} onClick={save}>{t("save")}</button>
          <button className="btn" disabled={busy} onClick={load}>{t("cjRefresh")}</button>
          <button className="btn" onClick={() => onAnalyze(row.participant_id)}>{t("cjAnalyze")}</button>
          <button className="btn" onClick={() => onPlan(row.participant_id)}>{t("cjViewPlan")}</button></div>
        {saved && <p role="status">{t("cjSaved")}</p>}
        <h2>{t("cjHistory")}</h2><ol>{row.events.map(e => <li key={e.id}>{t.date(e.at, true)} · {e.by} · {t(`cjState_${e.outcome}` as Key)}{e.note ? ` · ${e.note}` : ""}</li>)}</ol>
      </>}
    </article>
  </div>;
}
