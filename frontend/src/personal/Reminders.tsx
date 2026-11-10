import { useCallback, useEffect, useState } from "react";
import { api, Reminder } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

/** The person's own date, from their device. Sent to the server so "today" follows where they are. */
export function localDay(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Today's routines from the person's clinician. Every answer is optional; nothing is reported if they skip. */
export default function Reminders({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const day = localDay();
  const [items, setItems] = useState<Reminder[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => { api.reminders(day).then((r) => setItems(r.items)).catch(setError); }, [day]);
  useEffect(load, [load]);

  const answer = async (id: number, reply: "done" | "not_today") => {
    setError(null);
    try { await api.replyReminder(id, reply, day); load(); } catch (e) { setError(e); }
  };

  return (
    <>
      <Heading>{t("remTitle")}</Heading>
      <p className="lede">{t("remLede")}</p>
      <ErrorNote error={error} onRetry={load} />
      {items?.length === 0 && <p className="muted">{t("remNone")}</p>}
      <div style={{ display: "grid", gap: 12 }}>
        {items?.map((i) => {
          const wanted = t.lang === "ar" ? "text_ar" : "text_en";
          const text = i[wanted] ?? (t.lang === "ar" ? i.text_en : i.text_ar) ?? "";
          const otherLang = i[wanted] == null;
          return (
            <section key={i.id} className="p-card" aria-label={t(`dayPart_${i.day_part}`)}>
              <p className="eyebrow">{t(`dayPart_${i.day_part}`)}</p>
              <p dir={otherLang ? (t.lang === "ar" ? "ltr" : "rtl") : undefined} lang={otherLang ? (t.lang === "ar" ? "en" : "ar") : t.lang}
                style={{ fontSize: "1.15em", margin: "4px 0" }}>{text}</p>
              <p className="muted" style={{ fontSize: 13 }}>
                {t("remFrom", { who: i.written_by ?? "" })}
                {otherLang ? ` · ${t("remShownIn", { lang: t.lang === "ar" ? "English" : "العربية" })}` : ""}
              </p>
              {i.reply ? (
                <p>{t("remAnswered", { answer: i.reply === "done" ? t("remDone") : t("remNotToday") })}{" "}
                  <button className="link" onClick={() => answer(i.id, i.reply === "done" ? "not_today" : "done")}>{t("remChange")}</button></p>
              ) : (
                <div style={{ display: "flex", gap: 10 }}>
                  <button className="btn primary" onClick={() => answer(i.id, "done")}>{t("remDone")}</button>
                  <button className="btn" onClick={() => answer(i.id, "not_today")}>{t("remNotToday")}</button>
                </div>
              )}
            </section>
          );
        })}
      </div>
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
