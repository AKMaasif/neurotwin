import { useEffect, useState } from "react";
import { MousePointerClick } from "lucide-react";
import { api, ClinicianParticipant, Evidence, ReviewItem, Session } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Status } from "../ui";
import type { Data, Sel } from "./ClinicianApp";
import Decide from "./Decide";
import ChangeSummary from "./Change";
import { valueText } from "./EvidenceTable";

const SESSION_LEVEL = new Set(["interrupted_session", "abandoned_session", "missing_required", "unknown_protocol"]);

export default function Detail({ person, data, sel, onSelect, onChanged }: {
  person: ClinicianParticipant | null; data: Data | null; sel: Sel; onSelect: (s: Sel) => void; onChanged: () => void;
}) {
  const { t } = useT();
  const record = sel?.kind === "record" ? data?.evidence.find((e) => e.id === sel.id) : undefined;
  const session = sel?.kind === "session" ? data?.sessions.find((s) => s.id === sel.id)
    : record?.session_id ? data?.sessions.find((s) => s.id === record.session_id) : undefined;
  const tab = sel?.kind === "session" ? "session" : "record";

  return (
    <>
      <div className="pane-head"><span className="pane-title">{t("wsInspector")}</span></div>
      <div className="subtabs" role="tablist">
        <button role="tab" className="subtab" aria-selected={tab === "record"} disabled={!record}
          onClick={() => record && onSelect({ kind: "record", id: record.id })}>{t("wsRecord")}</button>
        <button role="tab" className="subtab" aria-selected={tab === "session"} disabled={!session}
          onClick={() => session && onSelect({ kind: "session", id: session.id })}>{t("wsSession")}</button>
      </div>
      <div className="pane-body">
        {!person || !data ? <p className="muted">{person ? t("wsLoading") : t("cSelect")}</p>
          : !sel ? <><Empty /><ChangeSummary changes={data.changes} /></>
          : tab === "record" && record ? <RecordView key={record.id} r={record} session={session} data={data} onSelect={onSelect} onChanged={onChanged} />
          : session ? <SessionView s={session} data={data} onSelect={onSelect} onChanged={onChanged} />
          : <Empty />}
      </div>
    </>
  );
}

function Empty() {
  const { t } = useT();
  return (
    <div style={{ display: "grid", gap: 10, color: "var(--muted)" }}>
      <MousePointerClick size={22} aria-hidden="true" />
      <p style={{ margin: 0, color: "var(--ink)" }}>{t("wsPick")}</p>
      <p style={{ margin: 0 }}>{t("wsPickTip1")}</p>
      <p style={{ margin: 0 }}>{t("wsPickTip2")}</p>
    </div>
  );
}

function conditions(s: Session, t: ReturnType<typeof useT>["t"]) {
  const parts = [t(`sessionStatus_${s.status}` as "sessionStatus_completed")];
  if (s.interruptions) parts.push(`${t("dInterruptions")} ${t.num(s.interruptions)}`);
  if (s.assisted) parts.push(t("wsMarkAssisted"));
  if (s.unwell_today) parts.push(t("wsMarkUnwell"));
  return parts.join(" · ");
}

function RecordView({ r, session, data, onSelect, onChanged }: {
  r: Evidence; session?: Session; data: Data; onSelect: (s: Sel) => void; onChanged: () => void;
}) {
  const { t } = useT();
  const items = data.items.filter((i) => i.evidence_id === r.id);
  const open = items.filter((i) => i.status === "open");
  const closed = items.filter((i) => i.status !== "open");
  const [earlier, setEarlier] = useState<Evidence[]>([]);
  const [withdrawing, setWithdrawing] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (r.supersedes_id) api.evidenceDetail(r.id).then((d) => setEarlier(d.earlier_versions)).catch(() => undefined);
  }, [r.id, r.supersedes_id]);

  const withdraw = async () => {
    setError(null);
    try { await api.withdraw(r.id, reason); setWithdrawing(false); setReason(""); onChanged(); } catch (e) { setError(e); }
  };

  return (
    <>
      <div className="d-title">
        <h2><span className="num">#{r.id}</span>{t.code(r.measure)}</h2>
        <div className="meta">
          <span className={`tag ${r.kind}`}>{t(`kind_${r.kind}`)}</span>
          <Status level={r.quality}>{t(`quality_${r.quality}`)}</Status>
          {r.status !== "current" && <Status level="quiet">{t(`status_${r.status}`)}</Status>}
        </div>
        <div className="meta">{t.code(r.protocol_code)} {r.protocol_version} · {t.date(r.recorded_at, true)}</div>
      </div>
      <div className="d-value">{valueText(r, t) ?? <span className="muted" style={{ fontSize: 15 }}>{t("missing")} · {t.code(r.missing_reason)}</span>}</div>
      {r.change_reason && <div className="notice"><strong>{t("dChangeReason")}:</strong> {r.change_reason}</div>}

      {open.map((i) => (
        <div key={i.id} className="decide">
          <Status level="warn">{t.code(i.reason)}</Status>
          <p className="hint mono">{t("wsFoundBy", { rules: i.raised_by })} · #{i.id}</p>
          <Decide ids={[i.id]} sessionWide={SESSION_LEVEL.has(i.reason)} onDone={onChanged} />
        </div>
      ))}

      <p className="d-section">{t("dQuality")}</p>
      {r.quality_reasons.length === 0 ? <p className="hint">{t("dNoReasons")}</p> : (
        <ul className="reasons">
          {r.quality_reasons.map((q) => <li key={q} className={r.quality}><span>{t.code(q)}</span><small className="mono">{q}</small></li>)}
        </ul>
      )}

      {session && (
        <button className="d-card" style={{ textAlign: "start", cursor: "pointer", background: "none" }} onClick={() => onSelect({ kind: "session", id: session.id })}>
          <span className="k"><span className="sw" style={{ background: "var(--navy)" }} />{t("wsSession")} #{session.id}</span>
          <span>{t.code(session.protocol_code)} · {t.date(session.started_at, true)}</span>
          <span className="muted">{conditions(session, t)}</span>
        </button>
      )}
      <div className="d-card">
        <span className="k"><span className="sw" style={{ background: "var(--cyan)" }} />{t("wsProducer")}</span>
        <span>{t.code(r.producer_type)} · <span className="mono">{r.producer_id}</span></span>
        <span className="muted mono">{r.producer_version}</span>
      </div>

      {closed.length > 0 && (
        <>
          <p className="d-section">{t("wsReviewed")}</p>
          {closed.map((i) => <Resolved key={i.id} i={i} />)}
        </>
      )}

      {earlier.length > 0 && (
        <>
          <p className="d-section">{t("dHistory")}</p>
          {earlier.map((v) => (
            <div key={v.id} className="d-card">
              <span className="mono">{valueText(v, t) ?? t("missing")}</span>
              <span className="muted mono">#{v.id} · {t.date(v.recorded_at, true)}</span>
            </div>
          ))}
        </>
      )}

      {r.status === "current" && open.length === 0 && (
        <>
          <p className="d-section">{t("dWithdraw")}</p>
          {!withdrawing ? <div><button className="btn danger" onClick={() => setWithdrawing(true)}>{t("dWithdraw")}</button></div> : (
            <div style={{ display: "grid", gap: 8 }}>
              <p className="hint">{t("dWithdrawHint")}</p>
              <textarea className="note" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("dReason")} maxLength={300} />
              <ErrorNote error={error} />
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn danger" disabled={!reason.trim()} onClick={withdraw}>{t("dWithdraw")}</button>
                <button className="btn" onClick={() => setWithdrawing(false)}>{t("cancel")}</button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}

function Resolved({ i }: { i: ReviewItem }) {
  const { t } = useT();
  return (
    <div className="d-card">
      <span className="k">{t.code(i.reason)}</span>
      <span><Status level={i.decision === "exclude" ? "fail" : "ok"}>{i.decision ? t(`wsDecided_${i.decision}`) : t("wsReviewed")}</Status>
        <span className="muted"> · {i.resolved_by} · {t.date(i.resolved_at)}</span></span>
      {i.resolution_note && <span>{i.resolution_note}</span>}
    </div>
  );
}

function SessionView({ s, data, onSelect, onChanged }: { s: Session; data: Data; onSelect: (s: Sel) => void; onChanged: () => void }) {
  const { t } = useT();
  const records = data.evidence.filter((e) => e.session_id === s.id);
  const items = data.items.filter((i) => i.session_id === s.id);
  const yesNo = (v: boolean | null) => (v === null ? t("dNotAsked") : v ? t("yes") : t("no"));
  return (
    <>
      <div className="d-title">
        <h2><span className="num">#{s.id}</span>{t.code(s.protocol_code)}</h2>
        <div className="meta">{s.protocol_version} · {t.date(s.started_at, true)}</div>
      </div>
      <dl className="kv">
        <dt>{t("colStatus")}</dt><dd>{t(`sessionStatus_${s.status}` as "sessionStatus_completed")}</dd>
        <dt>{t("dInterruptions")}</dt><dd className="mono">{t.num(s.interruptions)}</dd>
        <dt>{t("dAssisted")}</dt><dd>{yesNo(s.assisted)}</dd>
        {s.assistance_note && <><dt>{t("dAssistNote")}</dt><dd>{s.assistance_note}</dd></>}
        <dt>{t("dUnwell")}</dt><dd>{yesNo(s.unwell_today)}</dd>
        <dt>{t("dDevice")}</dt><dd className="mono">{s.device}</dd>
        <dt>{t("language")}</dt><dd className="mono">{s.language}</dd>
      </dl>
      <p className="d-section">{t("wsInSession")}</p>
      <ul className="mini-list">
        {records.map((e) => (
          <li key={e.id}>
            <button onClick={() => onSelect({ kind: "record", id: e.id })}>
              <span>{t.code(e.measure)} <span className="muted mono">{valueText(e, t) ?? t("missing")}</span></span>
              <Status level={e.status === "withdrawn" ? "quiet" : e.quality}>{e.status === "withdrawn" ? t("status_withdrawn") : t(`quality_${e.quality}`)}</Status>
            </button>
          </li>
        ))}
      </ul>
      {items.length > 0 && <p className="d-section">{t("wsOnSession")}</p>}
      {items.filter((i) => i.status === "open").map((i) => (
        <div key={i.id} className="decide">
          <Status level="warn">{t.code(i.reason)}</Status>
          <Decide ids={[i.id]} sessionWide={SESSION_LEVEL.has(i.reason)} onDone={onChanged} />
        </div>
      ))}
      {items.filter((i) => i.status !== "open").map((i) => <Resolved key={i.id} i={i} />)}
    </>
  );
}
