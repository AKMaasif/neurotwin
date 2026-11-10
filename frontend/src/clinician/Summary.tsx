import { useCallback, useEffect, useState } from "react";
import { FileQuestion } from "lucide-react";
import { AiStatus, api, ClinicianParticipant, Draft } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Status } from "../ui";
import type { Sel } from "./ClinicianApp";

/** Model-written summary drafts for one person. A draft is shown only after the output validator passed it, always
 *  labelled as a draft with its model, and it stays a draft until this clinician approves or rejects it. */
export default function Summary({ person, onSelect }: { person: ClinicianParticipant; onSelect: (s: Sel) => void }) {
  const { t } = useT();
  const [ai, setAi] = useState<AiStatus | null>(null);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    api.drafts(person.id).then(setDrafts).catch(setError);
  }, [person.id]);
  useEffect(() => { api.aiStatus().then(setAi).catch(() => setAi(null)); load(); }, [load]);

  const create = async () => {
    setBusy(true); setError(null);
    try { await api.createDraft(person.id, t.lang); load(); } catch (e) { setError(e); }
    setBusy(false);
  };

  return (
    <>
      <div className="d-title">
        <h2>{t("smTitle")}</h2>
        <div className="meta">{t("smLede")}</div>
      </div>
      {ai && !ai.configured ? <div className="notice">{t("smNotConfigured")}</div> : (
        <div>
          <button className="btn primary" disabled={busy || !ai} onClick={create}>
            {busy ? t("smWriting") : t("smCreate")}
          </button>
          {ai?.configured && <p className="hint mono" style={{ marginTop: 6 }}>{ai.provider} · {ai.model}</p>}
        </div>
      )}
      <ErrorNote error={error} />
      {drafts?.length === 0 && <p className="hint">{t("smNone")}</p>}
      {drafts?.map((d) => <DraftCard key={d.id} d={d} onSelect={onSelect} onChanged={load} />)}
    </>
  );
}

function DraftCard({ d, onSelect, onChanged }: { d: Draft; onSelect: (s: Sel) => void; onChanged: () => void }) {
  const { t } = useT();
  const [texts, setTexts] = useState(d.statements.map((s) => s.text));
  const [editing, setEditing] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [facts, setFacts] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const pending = d.status === "pending_review";

  const decide = async (decision: "approve" | "reject") => {
    setBusy(true); setError(null);
    try {
      const statements = decision === "approve" ? d.statements.map((s, i) => ({ text: texts[i], cites: s.cites })) : undefined;
      await api.reviewDraft(d.id, decision, note, statements);
      onChanged();
    } catch (e) { setError(e); }
    setBusy(false);
  };

  const cite = (id: string) => {
    const n = Number(id.slice(1));
    if (id[0] === "E") onSelect({ kind: "record", id: n });
    else if (id[0] === "S") onSelect({ kind: "session", id: n });
  };
  const level = d.status === "approved" ? "ok" : d.status === "pending_review" ? "warn" : d.status === "refused" ? "fail" : "quiet";

  return (
    <div className={pending ? "decide" : "d-card"} style={{ gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <Status level={level}>{t(`smStatus_${d.status}`)}</Status>
        <span className="muted mono" style={{ fontSize: 12 }}>#{d.id} · {t.date(d.created_at, true)}</span>
      </div>
      <p className="hint mono">{d.provider} · {d.model} · {d.validator_version} · {t("smAttempts", { n: t.num(d.attempts) })}</p>

      {d.status === "refused" ? (
        <>
          <p className="hint">{t("smRefused")}</p>
          <ul className="reasons">
            {d.problems.slice(0, 6).map((p, i) => <li key={i} className="unusable"><span className="mono">{p.code}</span><small>{p.detail}</small></li>)}
          </ul>
        </>
      ) : (
        <ol className="draft-list" dir={d.language === "ar" ? "rtl" : "ltr"} lang={d.language}>
          {d.statements.map((s, i) => (
            <li key={i}>
              {editing === i && pending
                ? <textarea className="note" value={texts[i]} maxLength={800} onChange={(e) => setTexts(texts.map((x, k) => (k === i ? e.target.value : x)))} />
                : <span>{pending ? texts[i] : s.text}</span>}
              <span className="cites">
                {s.cites.map((c) => (
                  <button key={c} className="cite" disabled={c[0] !== "E" && c[0] !== "S"} onClick={() => cite(c)}>{c}</button>
                ))}
                {(s.edited || (pending && texts[i] !== s.text)) && <span className="tag">{t("smEdited")}</span>}
                {pending && <button className="link" onClick={() => setEditing(editing === i ? null : i)}>{editing === i ? t("done") : t("smEdit")}</button>}
              </span>
            </li>
          ))}
        </ol>
      )}

      {d.status !== "refused" && (
        <button className="link" style={{ justifySelf: "start" }} onClick={() => setFacts(!facts)}>
          <FileQuestion size={14} aria-hidden="true" /> {t("smFacts", { n: t.num(d.facts.length) })}
        </button>
      )}
      {facts && <ul className="fact-list">{d.facts.map((f) => <li key={f.id}><b className="mono">{f.id}</b> {f.text.replace(/^[^:]+:\s*/, "")}</li>)}</ul>}

      {pending && (
        <>
          <p className="hint">{t("smReviewHint")}</p>
          <textarea className="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("smNote")} maxLength={500} />
          <ErrorNote error={error} />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn primary" disabled={busy || texts.some((x) => !x.trim())} onClick={() => decide("approve")}>{t("smApprove")}</button>
            <button className="btn danger" disabled={busy || !note.trim()} onClick={() => decide("reject")}>{t("smReject")}</button>
          </div>
        </>
      )}
      {d.reviewed_by && (
        <p className="hint">{t("smReviewedBy", { who: d.reviewed_by, date: t.date(d.reviewed_at) })}{d.review_note ? `: ${d.review_note}` : ""}</p>
      )}
    </div>
  );
}
