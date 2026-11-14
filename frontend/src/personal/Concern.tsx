import { useCallback, useEffect, useState } from "react";
import VoiceButton from "../voice";
import { api, Concern, ConcernSince, ConcernTopic } from "../api";
import { Key, useT } from "../i18n";
import { ErrorNote, Heading, Status } from "../ui";
import type { Screen } from "./PersonalApp";

const TOPICS: ConcernTopic[] = ["memory_or_thinking", "mood_or_worry", "sleep", "body_or_pain", "medicine_question", "something_else"];
const SINCES: ConcernSince[] = ["today", "few_days", "week_or_more", "not_sure"];

/** Tell the clinician something. Write, check exactly what will be sent, then Send. The person is told only what has actually happened:
 *  "in the inbox" is not "read". Not an emergency route; help is one tap away on every step. */
export default function ConcernScreen({ go, onBack }: { go: (s: Screen) => void; onBack: () => void }) {
  const { t } = useT();
  const [list, setList] = useState<Concern[]>([]);
  const [info, setInfo] = useState<{ monitoring_hours: string | null; recipients: { id: string; name: string }[] } | null>(null);
  const [topic, setTopic] = useState<ConcernTopic | "">("");
  const [since, setSince] = useState<ConcernSince | "">("");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Concern | null>(null);
  const [to, setTo] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => { api.concerns().then(setList).catch(setError); api.concernInfo().then(setInfo).catch(setError); }, []);
  useEffect(load, [load]);
  const ready = topic && since && text.trim();

  const preview = async () => {
    setError(null);
    try {
      const body = { topic, since, text };
      setDraft(draft ? await api.editConcern(draft.id, body) : await api.createConcern(body));
      if (info?.recipients.length === 1) setTo(info.recipients[0].id);
    } catch (e) { setError(e); }
  };
  const send = async () => {
    if (!draft) return;
    setError(null);
    try {
      await api.sendConcern(draft.id, draft.rev, to || undefined);
      setDraft(null); setTopic(""); setSince(""); setText(""); setNotice(t("cnSentOk")); load();
    } catch (e) { setError(e); }
  };
  const withdraw = async (id: number) => { setError(null); try { await api.withdrawConcern(id); load(); } catch (e) { setError(e); } };
  const stateLine = (c: Concern) => t(`cnSt_${c.status}` as Key, { name: c.recipient ?? "" });

  return (
    <>
      <Heading>{t("cnTitle")}</Heading>
      <p className="lede">{t("cnLede")}</p>
      <p role="note"><b>{t("cnNotEmergency")}</b> <button className="link" onClick={() => go("urgent")}>{t("urgentHelp")}</button></p>
      {info && <p className="hint">{info.monitoring_hours ? t("cnHours", { hours: info.monitoring_hours }) : t("cnHoursUnknown")}</p>}
      <ErrorNote error={error} />
      {notice && <p role="status">{notice}</p>}

      {!draft ? (
        <section className="p-card" style={{ display: "grid", gap: 10 }}>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend><b>{t("cnAbout")}</b></legend>
            {TOPICS.map((k) => (
              <label key={k} style={{ display: "flex", gap: 8, padding: "8px 0" }}>
                <input type="radio" name="topic" checked={topic === k} onChange={() => setTopic(k)} /> {t(`cnTopic_${k}` as Key)}
              </label>
            ))}
          </fieldset>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend><b>{t("cnSince")}</b></legend>
            {SINCES.map((k) => (
              <label key={k} style={{ display: "flex", gap: 8, padding: "8px 0" }}>
                <input type="radio" name="since" checked={since === k} onChange={() => setSince(k)} /> {t(`cnSince_${k}` as Key)}
              </label>
            ))}
          </fieldset>
          <label className="field"><span>{t("cnWords")}</span>
            <textarea className="note" rows={4} maxLength={600} value={text} onChange={(e) => setText(e.target.value)} /></label>
          <VoiceButton onText={(w) => setText((x) => (x ? `${x} ${w}` : w).slice(0, 600))} />
          <button className="btn primary block" disabled={!ready} onClick={preview}>{t("cnPreview")}</button>
        </section>
      ) : (
        <section className="p-card" aria-label={t("cnPreviewTitle")} style={{ display: "grid", gap: 8 }}>
          <p className="eyebrow">{t("cnPreviewTitle")}</p>
          <p><b>{t(`cnTopic_${draft.topic}` as Key)}</b> · {t(`cnSince_${draft.since}` as Key)}</p>
          <p style={{ whiteSpace: "pre-wrap" }}>{draft.text}</p>
          {info && info.recipients.length === 0 && <p className="hint">{t("cnNoClinician")}</p>}
          {info && info.recipients.length === 1 && <p>{t("cnTo", { name: info.recipients[0].name })}</p>}
          {info && info.recipients.length > 1 && (
            <label className="field"><span>{t("cnToChoose")}</span>
              <select value={to} onChange={(e) => setTo(e.target.value)}>
                <option value="" />{info.recipients.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></label>
          )}
          <button className="btn primary block" disabled={!info || info.recipients.length === 0 || !to} onClick={send}>{t("cnSend")}</button>
          <button className="btn block" onClick={() => setDraft(null)}>{t("cnEdit")}</button>
        </section>
      )}

      <Heading level={2}>{t("cnYours")}</Heading>
      {list.length === 0 && <p className="muted">{t("cnNone")}</p>}
      {list.filter((c) => c.status !== "draft").map((c) => (
        <section key={c.id} className="p-card" style={{ display: "grid", gap: 6 }}>
          <p className="eyebrow">{t.date(c.created_at)} · {t(`cnTopic_${c.topic}` as Key)}</p>
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{c.text}</p>
          <p><Status level={c.status === "withdrawn" ? "quiet" : c.status === "delivered" ? "warn" : "ok"}>{stateLine(c)}</Status></p>
          <ol style={{ margin: 0, paddingInlineStart: 20 }}>
            {c.events.map((e, k) => <li key={k} className="hint">{t(`cnEv_${e.kind}` as Key)} · {t.date(e.at, true)}{e.by && e.kind !== "created" && e.kind !== "sent" && e.kind !== "delivered" ? ` · ${e.by}` : ""}{e.note ? ` · ${e.note}` : ""}</li>)}
          </ol>
          {["delivered", "sent"].includes(c.status) && <button className="link" style={{ justifySelf: "start" }} onClick={() => withdraw(c.id)}>{t("cnWithdraw")}</button>}
        </section>
      ))}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
