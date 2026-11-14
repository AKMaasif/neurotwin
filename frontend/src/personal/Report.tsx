import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import { api, PatientReport } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

const PERIODS = [7, 11, 30];
const KEY = "neurotwin.appointment-questions";

function loadQs(): string[] { try { const v = JSON.parse(localStorage.getItem(KEY) ?? "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, 20) : []; } catch { return []; } }
function saveQs(q: string[]) { try { localStorage.setItem(KEY, JSON.stringify(q)); } catch { /* storage can be unavailable; the list still works on screen */ } }

/** The person's own period report, and the appointment-preparation page that wraps it. Nothing here is a score or an interpretation. */
export default function Report({ prep, onBack }: { prep?: boolean; onBack: () => void }) {
  const { t } = useT();
  const [days, setDays] = useState(11);
  const [r, setR] = useState<PatientReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [qs, setQs] = useState<string[]>(loadQs);
  useEffect(() => { setR(null); api.myReport(days).then(setR).catch(setError); }, [days]);
  const fmt = (d: string) => new Intl.DateTimeFormat(t.lang === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(d + "T00:00:00Z"));
  const setQ = (next: string[]) => { setQs(next); saveQs(next); };

  const val = (v: PatientReport["days"][0]["sessions"][0]["values"][0]) => {
    if (v.missing_reason) return t.code(v.missing_reason);
    if (v.measure === "sleep_hours") return `${t.num(v.value_num ?? 0, 1)} ${t("hours")}`;
    if (v.measure === "sleep_quality") return t(`sq${v.value_num}` as "sq1");
    if (v.measure === "today_factors") return (v.value_text ?? "").split(",").map((c) => t.code(c)).join(t.lang === "ar" ? "، " : ", ");
    return v.value_num !== null ? t.num(v.value_num, 1) : v.value_text ?? "";
  };

  return (
    <>
      <Heading>{prep ? t("rpPrepTitle") : t("rpTitle")}</Heading>
      <p className="lede">{t("rpLede")}</p>
      <div className="choices" role="radiogroup" aria-label={t("rpDays")} style={{ display: "flex", flexWrap: "wrap" }}>
        {PERIODS.map((n) => (
          <button key={n} className="choice" role="radio" aria-checked={days === n} onClick={() => setDays(n)} style={{ flex: "1 1 30%" }}>
            <span className="dot" />{t("rpDaysN", { n: t.num(n) })}
          </button>
        ))}
      </div>
      <ErrorNote error={error} />
      {r && (
        <article aria-label={t("rpTitle")} className="rp">
          <h2 style={{ fontSize: 20 }}>{t("rpPeriod", { from: fmt(r.period.from), to: fmt(r.period.to), n: t.num(r.period.days) })}</h2>

          <section>
            <h2>{t("rpActivities")}</h2>
            {r.days.filter((d) => d.sessions.length).reverse().map((d) => (
              <div key={d.date} className="p-card">
                <h3 style={{ fontSize: 18 }}>{fmt(d.date)}</h3>
                {d.sessions.map((s) => (
                  <div key={s.id}>
                    <p><b>{t.code(s.protocol_code)}</b> · {t(`sessionStatus_${s.status}` as "sessionStatus_completed")}
                      {s.assisted ? ` · ${t("rpAssisted")}` : ""}{s.interruptions > 0 ? ` · ${t("rpInterrupted")}` : ""}{s.unwell_today ? ` · ${t("rpUnwell")}` : ""}</p>
                    {s.protocol_code === "who5" && <p className="muted">{t("rpWho5Done")}</p>}
                    {s.values.length > 0 && (
                      <dl><dt className="muted">{t("rpYouTold")}</dt>
                        {s.values.map((v) => <dd key={v.measure}>{t.code(v.measure)}: {val(v)}</dd>)}</dl>
                    )}
                  </div>
                ))}
              </div>
            ))}
            <p className="muted">{t("rpNoNumbers")}</p>
            {r.missing.days_without_activity.length > 0 && r.missing.days_without_activity.length < r.period.days + 1 && (
              <p className="muted">{t("rpNothing", { days: r.missing.days_without_activity.map(fmt).join(t.lang === "ar" ? "، " : ", ") })}</p>
            )}
            {r.missing.skipped_answers > 0 && <p className="muted">{t("rpSkipped", { n: t.num(r.missing.skipped_answers) })}</p>}
          </section>

          <section>
            <h2>{t("rpRoutines")}</h2>
            {r.routines.length === 0 && <p className="muted">{t("rpNoRoutines")}</p>}
            {r.routines.map((x) => (
              <div key={x.item_id} className="p-card">
                <p><b>{(t.lang === "ar" ? x.text_ar : null) ?? x.title ?? x.text_en}</b></p>
                <p className="muted">{t("rpRoutineLine", { a: t.num(x.marked_done_days), b: t.num(x.not_today_days), c: t.num(x.difficulty_days), d: t.num(x.answered_days), n: t.num(r.period.days) })}</p>
              </div>
            ))}
          </section>

          {r.concerns_sent.length > 0 && (
            <section>
              <h2>{t("rpConcerns")}</h2>
              <ul>{r.concerns_sent.map((c) => <li key={c.id}>{fmt(c.sent_on)} · {t.code(c.topic)} · {t.code(c.status)}</li>)}</ul>
            </section>
          )}
        </article>
      )}

      {prep && (
        <section aria-labelledby="rp-q">
          <h2 id="rp-q">{t("rpQTitle")}</h2>
          <p className="muted">{t("rpQHelp")}</p>
          {qs.length === 0 && <p className="muted">{t("rpQNone")}</p>}
          <ol>
            {qs.map((q, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                <input value={q} maxLength={200} aria-label={t("rpQPlaceholder")} onChange={(e) => setQ(qs.map((x, j) => (j === i ? e.target.value : x)))} />
                <button className="link" onClick={() => setQ(qs.filter((_, j) => j !== i))}>{t("rpQRemove")}</button>
              </li>
            ))}
          </ol>
          {qs.length < 20 && <button className="btn block" onClick={() => setQ([...qs, ""])}>{t("rpQAdd")}</button>}
          <p className="muted">{t("rpTake")}</p>
        </section>
      )}
      <div className="p-actions">
        <button className="btn block no-print" onClick={() => window.print()}><Printer size={22} aria-hidden="true" /> {t("rpPrint")}</button>
        <button className="btn block no-print" onClick={onBack}>{t("backHome")}</button>
      </div>
    </>
  );
}
