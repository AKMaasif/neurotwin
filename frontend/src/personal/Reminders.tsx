import { useCallback, useEffect, useState } from "react";
import { api, AwaitingPlan, DifficultyReason, Reminder } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

const REASONS: DifficultyReason[] = ["too_tiring", "unclear", "inaccessible", "need_help"];
const key = () => Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, "0")).join("");

/** Today's tasks. The server decides what "today" is from the person's time zone, and only plans the person has accepted make tasks.
 *  Every answer is optional; a task with no answer is simply shown as not answered, never as missed. */
export default function Reminders({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const [items, setItems] = useState<Reminder[] | null>(null);
  const [day, setDay] = useState("");
  const [tz, setTz] = useState("");
  const [plans, setPlans] = useState<AwaitingPlan[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => {
    Promise.all([api.reminders(), api.plansAwaiting()])
      .then(([r, p]) => { setItems(r.items); setDay(r.day); setTz(r.timezone); setPlans(p); })
      .catch(setError);
  }, []);
  useEffect(load, [load]);

  const answer = async (id: number, b: { reply: "done" | "not_today" | "snooze" | "difficulty"; snooze_minutes?: number; reason?: DifficultyReason }, msg?: string) => {
    setError(null);
    try { await api.replyReminder(id, { ...b, day, idem_key: key() }); if (msg) setNotice(msg); load(); } catch (e) { setError(e); }
  };
  const done = (items ?? []).filter((i) => i.reply === "done").length;

  return (
    <>
      <Heading>{t("remTitle")}</Heading>
      <p className="lede">{t("remLede")}</p>
      <ErrorNote error={error} onRetry={load} />
      {notice && <p role="status" className="hint">{notice}</p>}
      {plans.map((p) => <PlanCard key={p.id} plan={p} onDone={(m) => { setNotice(m); load(); }} onError={setError} />)}
      {items?.length === 0 && plans.length === 0 && <p className="muted">{t("remNone")}</p>}
      {items && items.length > 0 && (
        <p className="muted" role="status">{t("remMarkedDone", { n: t.num(done), m: t.num(items.length) })} · {t("remMarkedHint")}</p>
      )}
      <div style={{ display: "grid", gap: 12 }}>
        {items?.map((i) => <Task key={i.id} item={i} answer={answer} />)}
      </div>
      {tz && <p className="hint">{t("remTimezone", { tz })}</p>}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}

function PlanCard({ plan, onDone, onError }: { plan: AwaitingPlan; onDone: (msg: string) => void; onError: (e: unknown) => void }) {
  const { t } = useT();
  const [asking, setAsking] = useState(false);
  const [q, setQ] = useState("");
  const respond = async (r: "accept" | "question" | "decline") => {
    onError(null);
    try {
      await api.respondToPlan(plan.id, r, r === "question" ? q : undefined);
      onDone(r === "accept" ? t("remAcceptedOk") : r === "decline" ? t("remDeclinedOk") : t("remQuestionSent"));
      setAsking(false); setQ("");
    } catch (e) { onError(e); }
  };
  return (
    <section className="p-card" aria-label={t("remPlanTitle")}>
      <p className="eyebrow">{t("remPlanTitle")}</p>
      <p>{t("remPlanBody", { who: plan.sent_by ?? plan.written_by ?? "", date: t.date(plan.sent_at) })}</p>
      <ul style={{ paddingInlineStart: 20 }}>
        {plan.items.map((i) => <li key={i.id}><ItemText item={i} /></li>)}
      </ul>
      {!asking ? (
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="btn primary" onClick={() => respond("accept")}>{t("remAccept")}</button>
          <button className="btn" onClick={() => setAsking(true)}>{t("remAsk")}</button>
          <button className="btn" onClick={() => respond("decline")}>{t("remDecline")}</button>
        </div>
      ) : (
        <>
          <textarea className="note" value={q} maxLength={300} placeholder={t("remQuestionPh")} aria-label={t("remQuestionPh")} onChange={(e) => setQ(e.target.value)} />
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn primary" disabled={!q.trim()} onClick={() => respond("question")}>{t("remSendQuestion")}</button>
            <button className="btn" onClick={() => setAsking(false)}>{t("cancel")}</button>
          </div>
        </>
      )}
    </section>
  );
}

function pick(i: { text_en: string | null; text_ar: string | null }, lang: "en" | "ar") {
  const wanted = lang === "ar" ? "text_ar" : "text_en";
  const text = i[wanted] ?? (lang === "ar" ? i.text_en : i.text_ar) ?? "";
  return { text, other: i[wanted] == null };
}

function ItemText({ item }: { item: Reminder | AwaitingPlan["items"][number] }) {
  const { t } = useT();
  const { text, other } = pick(item, t.lang);
  return <span dir={other ? (t.lang === "ar" ? "ltr" : "rtl") : undefined} lang={other ? (t.lang === "ar" ? "en" : "ar") : t.lang}>{item.title ? `${item.title}: ` : ""}{text}</span>;
}

function Task({ item: i, answer }: {
  item: Reminder;
  answer: (id: number, b: { reply: "done" | "not_today" | "snooze" | "difficulty"; snooze_minutes?: number; reason?: DifficultyReason }, msg?: string) => void;
}) {
  const { t } = useT();
  const [more, setMore] = useState<"snooze" | "hard" | null>(null);
  const when = i.time_hhmm ? t("remAtTime", { time: i.time_hhmm })
    : i.window_start && i.window_end ? t("remBetween", { from: i.window_start, to: i.window_end }) : t(`dayPart_${i.day_part}`);
  const { other } = pick(i, t.lang);
  return (
    <section className="p-card" aria-label={when}>
      <p className="eyebrow">{when}</p>
      <p style={{ fontSize: "1.15em", margin: "4px 0" }}><ItemText item={i} /></p>
      {i.quantity != null && i.unit && <p className="muted">{t("remHowMuch", { q: t.num(i.quantity), unit: i.unit })}</p>}
      {i.precautions && <p className="muted">{t("remPrecautions", { text: i.precautions })}</p>}
      <p className="muted" style={{ fontSize: 13 }}>
        {t("remFrom", { who: i.written_by ?? "" })}
        {other ? ` · ${t("remShownIn", { lang: t.lang === "ar" ? "English" : "العربية" })}` : ""}
      </p>
      {i.snoozed_until && !i.reply && <p className="hint">{t("remSnoozedUntil", { time: t.date(i.snoozed_until, true) })}</p>}
      {i.reply ? (
        <p>{t("remAnswered", { answer: i.reply === "done" ? t("remDone") : t("remNotToday") })}{" "}
          <button className="link" onClick={() => answer(i.id, { reply: i.reply === "done" ? "not_today" : "done" })}>{t("remChange")}</button></p>
      ) : (
        <>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="btn primary" onClick={() => answer(i.id, { reply: "done" })}>{t("remDone")}</button>
            <button className="btn" onClick={() => answer(i.id, { reply: "not_today" })}>{t("remNotToday")}</button>
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 8 }}>
            <button className="link" onClick={() => setMore(more === "snooze" ? null : "snooze")}>{t("remSnooze")}</button>
            <button className="link" onClick={() => setMore(more === "hard" ? null : "hard")}>{t("remDifficulty")}</button>
          </div>
        </>
      )}
      {more === "snooze" && !i.reply && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {([30, 60, 120] as const).map((m) => (
            <button key={m} className="btn" onClick={() => { setMore(null); answer(i.id, { reply: "snooze", snooze_minutes: m }); }}>{t(`remSnooze${m}`)}</button>
          ))}
        </div>
      )}
      {more === "hard" && !i.reply && (
        <fieldset style={{ border: 0, padding: 0, marginTop: 8 }}>
          <legend className="hint">{t("remWhyHard")}</legend>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {REASONS.map((r) => (
              <button key={r} className="btn" onClick={() => { setMore(null); answer(i.id, { reply: "difficulty", reason: r }, t("remDiffSent")); }}>{t(`cpDiff_${r}`)}</button>
            ))}
          </div>
        </fieldset>
      )}
    </section>
  );
}
