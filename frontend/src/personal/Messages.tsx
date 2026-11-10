import { useCallback, useEffect, useState } from "react";
import { api, Message } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

/** Notes from family members the person chose to share with. Opening the screen marks them read; the person can
 *  remove any message from their own view. No reply is asked for and nothing here is shown to clinicians. */
export default function Messages({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const [items, setItems] = useState<Message[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => { api.inbox().then(setItems).catch(setError); }, []);
  useEffect(load, [load]);
  useEffect(() => { items?.filter((m) => !m.read).forEach((m) => api.readMessage(m.id).catch(() => undefined)); }, [items]);

  const remove = async (id: number) => {
    setError(null);
    try { await api.hideMessage(id); load(); } catch (e) { setError(e); }
  };

  return (
    <>
      <Heading>{t("msgTitle")}</Heading>
      <p className="lede">{t("msgLede")}</p>
      <ErrorNote error={error} onRetry={load} />
      {items?.length === 0 && <p className="muted">{t("msgNone")}</p>}
      <div style={{ display: "grid", gap: 12 }}>
        {items?.map((m) => (
          <section key={m.id} className="p-card">
            <p className="muted" style={{ fontSize: 14, margin: 0 }}>{t("msgFrom", { who: m.sender })} · {t.date(m.sent_at)}</p>
            <p style={{ fontSize: "1.15em", margin: "6px 0", whiteSpace: "pre-wrap" }} dir="auto">{m.text}</p>
            <button className="link" onClick={() => remove(m.id)}>{t("msgRemove")}</button>
          </section>
        ))}
      </div>
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
