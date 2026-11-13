import { useEffect, useState } from "react";
import VoiceButton from "../voice";
import { api, ApiError, AssistantItem, AssistantReply } from "../api";
import { Key, useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";
import type { Screen } from "./PersonalApp";

type Line = { orig?: string; who: "you" | "bot"; text?: string; items?: AssistantItem[]; pick?: AssistantItem[]; confirm?: { id: string; tool: string; item: AssistantItem; minutes: number | null } };
const NAV: Record<string, Screen> = { reminders: "reminders", messages: "messages", records: "records", home: "home", urgent: "urgent", checkin: "checkin", reaction: "reaction" };

/** A typed assistant with a short fixed list of things it can do. It matches words by fixed rules (no model), and any change is
 *  read back first and only recorded after "Yes". It never calls anyone; "help" opens the urgent page. */
export default function Assistant({ go, onBack }: { go: (s: Screen) => void; onBack: () => void }) {
  const { t } = useT();
  const [text, setText] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [heard, setHeard] = useState(false);
  const [reading, setReading] = useState(false);
  const [canRead, setCanRead] = useState(false);
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const check = () => setCanRead(window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(t.lang)));
    check();
    window.speechSynthesis.addEventListener?.("voiceschanged", check);
    return () => { window.speechSynthesis.cancel(); window.speechSynthesis.removeEventListener?.("voiceschanged", check); };
  }, [t.lang]);
  const read = (what: string) => {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(what);
    u.lang = t.lang === "ar" ? "ar" : "en";
    u.onend = () => setReading(false);
    setReading(true);
    window.speechSynthesis.speak(u);
  };
  const add = (l: Line) => setLines((x) => [...x, l]);
  const title = (i: AssistantItem) => [i.title, t.lang === "ar" ? i.text_ar ?? i.text_en : i.text_en ?? i.text_ar].filter(Boolean).join(": ");

  const send = async (msg: string) => {
    setError(null);
    if (!msg.trim()) return;
    add({ who: "you", text: msg });
    try {
      const r: AssistantReply = await api.assistantSay(msg);
      if (!r.understood) {
        add({ who: "bot", text: t(r.reason === "which" ? "asWhich" : (`as${r.reason[0].toUpperCase()}${r.reason.slice(1)}` as Key)), pick: r.reason === "which" ? r.choices : undefined, orig: msg });
      } else if (r.needs_confirmation) {
        add({ who: "bot", confirm: { id: r.confirmation_id, tool: r.tool, item: r.item, minutes: r.minutes } });
      } else if (r.items) {
        add({ who: "bot", text: r.items.length ? undefined : t("asNone"), items: r.items });
      } else if (r.item) {
        add({ who: "bot", items: [r.item] });
      } else if (r.navigate && NAV[r.navigate]) {
        add({ who: "bot", text: r.tool === "emergency" ? t("asUrgentOpen") : t("asOpening") });
        go(NAV[r.navigate]);
      }
    } catch (e) { setError(e); }
    setText(""); setHeard(false);
  };

  const decide = async (c: NonNullable<Line["confirm"]>, yes: boolean) => {
    setLines((x) => x.map((l) => (l.confirm?.id === c.id ? { ...l, confirm: undefined, text: "…" } : l)));
    if (!yes) { add({ who: "bot", text: t("asCancelled") }); return; }
    try { await api.assistantConfirm(c.id); add({ who: "bot", text: t("asDoneOk") }); }
    catch (e) { if (e instanceof ApiError && e.status === 410) add({ who: "bot", text: t("asTooLate") }); else setError(e); }
  };

  return (
    <>
      <Heading>{t("asTitle")}</Heading>
      <p className="lede">{t("asLede")}</p>
      <p className="hint">{t("asTry")}</p>
      <ErrorNote error={error} />
      <div role="log" aria-live="polite" style={{ display: "grid", gap: 10 }}>
        {lines.map((l, k) => (
          <section key={k} className="p-card" aria-label={l.who === "you" ? t("asYou") : t("asHelper")}>
            <p className="eyebrow">{l.who === "you" ? t("asYou") : t("asHelper")}</p>
            {l.text && l.text !== "…" && <p style={{ margin: "4px 0" }}>{l.text}</p>}
            {l.items?.map((i) => <p key={i.id} style={{ margin: "4px 0" }}>{i.time_hhmm ? `${i.time_hhmm} · ` : ""}{title(i)}{i.quantity != null && i.unit ? ` · ${i.quantity} ${i.unit}` : ""}{i.precautions ? ` · ${i.precautions}` : ""}</p>)}
            {l.pick?.map((i) => <button key={i.id} className="btn block" onClick={() => send(`${l.orig ?? ""} ${i.text_en ?? i.text_ar ?? ""}`.trim())}>{title(i)}</button>)}
            {l.who === "bot" && canRead && (l.text || l.items || l.confirm) && (
              <button className="link" onClick={() => reading ? (window.speechSynthesis.cancel(), setReading(false)) : read([l.text, ...(l.items ?? []).map(title), l.confirm ? `${t(l.confirm.tool === "mark_done" ? "asConfirmDone" : l.confirm.tool === "mark_not_today" ? "asConfirmNot" : "asConfirmSnooze", { n: l.confirm.minutes ?? 0 })} ${title(l.confirm.item)}` : ""].filter(Boolean).join(". "))}>
                {reading ? t("asStopReading") : t("asReadAloud")}</button>
            )}
            {l.confirm && (
              <>
                <p style={{ margin: "4px 0" }}>{t(l.confirm.tool === "mark_done" ? "asConfirmDone" : l.confirm.tool === "mark_not_today" ? "asConfirmNot" : "asConfirmSnooze", { n: l.confirm.minutes ?? 0 })}</p>
                <p style={{ fontSize: "1.1em", margin: "4px 0" }}>{title(l.confirm.item)}</p>
                <div style={{ display: "flex", gap: 10 }}>
                  <button className="btn primary" onClick={() => decide(l.confirm!, true)}>{t("asYes")}</button>
                  <button className="btn" onClick={() => decide(l.confirm!, false)}>{t("asNo")}</button>
                </div>
              </>
            )}
          </section>
        ))}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(text); }} style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <VoiceButton onText={(w) => { setText(w.slice(0, 300)); setHeard(true); }} />
        {heard && <p className="hint" role="status">{t("asHeard")}</p>}
        <input className="note" value={text} maxLength={300} placeholder={t("asPlaceholder")} aria-label={t("asPlaceholder")} onChange={(e) => { setText(e.target.value); }} />
        <button className="btn primary block" type="submit" disabled={!text.trim()}>{t("asSend")}</button>
      </form>
      {canRead && <p className="hint">{t("asReadNote")}</p>}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
