import { useCallback, useEffect, useState } from "react";
import { api, Concern } from "../api";
import { Key, useT } from "../i18n";
import { ErrorNote, Status } from "../ui";

/** Reports the person chose to send this clinician. Plain list, newest first: no urgency label, no ranking, no interpretation.
 *  Acknowledge, review and close are each the clinician's own action and are what the person is told. */
export default function Concerns({ onCount }: { onCount?: (n: number) => void }) {
  const { t } = useT();
  const [rows, setRows] = useState<Concern[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => {
    api.concernInbox().then((r) => { setRows(r); onCount?.(r.filter((x) => x.status === "delivered").length); }).catch(setError);
  }, [onCount]);
  useEffect(load, [load]);
  return (
    <>
      <div className="d-title"><h2>{t("cnInbox")}</h2><div className="meta">{t("cnInboxLede")}</div></div>
      <ErrorNote error={error} onRetry={load} />
      {rows?.length === 0 && <p className="hint">{t("cnInboxNone")}</p>}
      {rows?.map((c) => <Row key={c.id} c={c} onChanged={load} />)}
    </>
  );
}

function Row({ c, onChanged }: { c: Concern; onChanged: () => void }) {
  const { t } = useT();
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const act = async (f: () => Promise<unknown>) => { setError(null); try { await f(); setNote(""); onChanged(); } catch (e) { setError(e); } };
  const open = c.status === "acknowledged" || c.status === "reviewed";
  return (
    <div className="d-card" style={{ gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <b>{t("cnFrom", { who: c.participant ?? "" })}</b>
        <Status level={c.status === "delivered" ? "warn" : c.status === "closed" || c.status === "withdrawn" ? "quiet" : "ok"}>{t(`cnEv_${c.status === "delivered" ? "delivered" : c.status}` as Key)}</Status>
      </div>
      <p className="hint" style={{ margin: 0 }}>{t(`cnTopic_${c.topic}` as Key)} · {t(`cnSince_${c.since}` as Key)} · {t.date(c.created_at, true)}</p>
      <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{c.text}</p>
      <p className="hint" style={{ margin: 0 }}>{t("cnYouWrote")}</p>
      <ol style={{ margin: 0, paddingInlineStart: 20 }}>
        {c.events.map((e, k) => <li key={k} className="hint">{t(`cnEv_${e.kind}` as Key)} · {t.date(e.at, true)} · {e.by}{e.note ? ` · ${e.note}` : ""}</li>)}
      </ol>
      <ErrorNote error={error} />
      {c.status === "withdrawn" && <p className="hint">{t("cnWithdrawnBy")}</p>}
      {c.status === "delivered" && <button className="btn primary" style={{ justifySelf: "start" }} onClick={() => act(() => api.acknowledgeConcern(c.id))}>{t("cnAck")}</button>}
      {open && (
        <>
          <input className="note" value={note} maxLength={300} placeholder={t("cnNote")} aria-label={t("cnNote")} onChange={(e) => setNote(e.target.value)} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {c.status === "acknowledged" && <button className="btn" onClick={() => act(() => api.reviewConcern(c.id, note))}>{t("cnReviewBtn")}</button>}
            <button className="btn" onClick={() => act(() => api.closeConcern(c.id, note))}>{t("cnCloseBtn")}</button>
          </div>
        </>
      )}
    </div>
  );
}
