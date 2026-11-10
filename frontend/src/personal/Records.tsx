import { useCallback, useEffect, useState } from "react";
import { api, Evidence, Session, User } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

/** The person's own history. Self-reported answers are shown and can be corrected; activity results are not shown
 *  as numbers here, on purpose: a bare number without context invites worry. The clinician sees them with context. */
export default function Records({ user, onBack }: { user: User; onBack: () => void }) {
  const { t } = useT();
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [editing, setEditing] = useState<Evidence | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, e] = await Promise.all([api.sessions(user.id), api.evidence(user.id)]);
      setSessions(s.filter((x) => x.status !== "in_progress")); setEvidence(e);
    } catch (e) { setError(e); }
  }, [user.id]);
  useEffect(() => { load(); }, [load]);

  if (editing) return <Correct record={editing} onClose={(ok) => { setEditing(null); if (ok) { setNotice(t("corrected")); load(); } }} />;

  const answer = (e: Evidence) => {
    if (e.missing_reason) return t("notAnswered");
    if (e.measure === "sleep_hours") return `${t.num(e.value_num ?? 0, 1)} ${t("hours")}`;
    if (e.measure === "sleep_quality") return t(`sq${e.value_num}` as "sq1");
    if (e.measure === "today_factors") return (e.value_text ?? "").split(",").map((c) => t.code(c)).join(t.lang === "ar" ? "، " : ", ");
    return "";
  };

  return (
    <>
      <Heading>{t("recordsTitle")}</Heading>
      <p className="lede">{t("recordsLede")}</p>
      {notice && <div className="notice" role="status">{notice}</div>}
      <ErrorNote error={error} onRetry={load} />
      {sessions === null && <p className="muted">{t("loading")}</p>}
      {sessions?.length === 0 && <p className="muted">{t("recordsNone")}</p>}
      {sessions?.map((s) => {
        const answers = evidence.filter((e) => e.session_id === s.id && e.kind === "self_reported" && e.status === "current");
        return (
          <section key={s.id} className="p-card">
            <div>
              <b>{t.code(s.protocol_code)}</b>
              <div className="muted" style={{ fontSize: 16 }}>{t.date(s.started_at, true)} · {t(`sessionStatus_${s.status}` as "sessionStatus_completed")}</div>
            </div>
            {answers.length > 0 && (
              <dl className="kv">
                {answers.map((e) => (
                  <div key={e.id} style={{ display: "contents" }}>
                    <dt>{t.code(e.measure)}</dt>
                    <dd>
                      {answer(e)}
                      {e.measure !== "today_factors" && (
                        <> · <button className="link" onClick={() => setEditing(e)}>{t("correct")}</button></>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        );
      })}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}

function Correct({ record, onClose }: { record: Evidence; onClose: (ok: boolean) => void }) {
  const { t } = useT();
  const quality = record.measure === "sleep_quality";
  const [value, setValue] = useState<number>(record.value_num ?? (quality ? 3 : 7));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true); setError(null);
    try { await api.amend(record.id, { value_num: value, reason }); onClose(true); } catch (e) { setError(e); }
    setBusy(false);
  };

  return (
    <>
      <Heading>{t("correctTitle")}</Heading>
      <p className="muted">{t.code(record.measure)}</p>
      {quality ? (
        <div className="choices" role="radiogroup">
          {[5, 4, 3, 2, 1].map((v) => (
            <button key={v} className="choice" role="radio" aria-checked={value === v} onClick={() => setValue(v)}>
              <span className="dot" />{t(`sq${v}` as "sq1")}
            </button>
          ))}
        </div>
      ) : (
        <div className="stepper">
          <button className="btn" aria-label="−" onClick={() => setValue(Math.max(0, value - 0.5))}>−</button>
          <div className="val">{t.num(value, 1)} <span className="muted" style={{ fontSize: 18 }}>{t("hours")}</span></div>
          <button className="btn" aria-label="+" onClick={() => setValue(Math.min(16, value + 0.5))}>+</button>
        </div>
      )}
      <label style={{ display: "grid", gap: 8 }}>
        <span>{t("correctReason")}</span>
        <textarea className="note" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("correctReasonHint")} maxLength={300} />
      </label>
      <ErrorNote error={error} />
      <div className="p-actions">
        <button className="btn primary block" disabled={busy || !reason.trim()} onClick={save}>{t("save")}</button>
        <button className="btn block" onClick={() => onClose(false)}>{t("cancel")}</button>
      </div>
    </>
  );
}
