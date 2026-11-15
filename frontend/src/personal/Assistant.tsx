import { useCallback, useEffect, useState } from "react";
import VoiceButton from "../voice";
import { api, ApiError, AssistantItem, AssistantReply } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";
import type { Screen } from "./PersonalApp";
import { itemTitle, replySentences } from "./replyText";

type Msg = { who: "you" | "bot"; text?: string | null; reply?: AssistantReply | null; fresh?: boolean };
const NAV: Record<string, Screen> = { prep: "prep", report: "report", concern: "concern", reminders: "reminders", messages: "messages", records: "records", home: "home", urgent: "urgent", checkin: "checkin", reaction: "reaction", memory: "memory", wellbeing: "wellbeing" };

/** A typed or spoken assistant with a short fixed list of things it can do. It matches words by fixed rules (no model) and follows the
 *  conversation: "it", "the other one", "yes" and "and the water?" are read against the last few minutes. The conversation is kept only for
 *  the person, who can clear it or switch it off. Any change is read back and recorded only after "Yes". It never calls anyone. */
export default function Assistant({ go, onBack }: { go: (s: Screen) => void; onBack: () => void }) {
  const { t } = useT();
  const [text, setText] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [memory, setMemory] = useState(true);
  const [days, setDays] = useState(30);
  const [heard, setHeard] = useState(false);
  const [reading, setReading] = useState(false);
  const [canRead, setCanRead] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    api.assistantHistory().then((h) => {
      setMemory(h.memory); setDays(h.keeps_days);
      setMsgs(h.messages.map((m) => ({ who: m.who, text: m.text, reply: m.payload })));
    }).catch(setError);
  }, []);
  useEffect(load, [load]);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const check = () => setCanRead(window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(t.lang)));
    check();
    window.speechSynthesis.addEventListener?.("voiceschanged", check);
    return () => { window.speechSynthesis.cancel(); window.speechSynthesis.removeEventListener?.("voiceschanged", check); };
  }, [t.lang]);

  const title = (i: AssistantItem) => itemTitle(t, i);
  const sentences = (r: AssistantReply) => replySentences(t, r);
  const read = (what: string) => {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(what);
    u.lang = t.lang === "ar" ? "ar" : "en";
    u.onend = () => setReading(false);
    setReading(true);
    window.speechSynthesis.speak(u);
  };

  const send = async (msg: string) => {
    setError(null); setNote(null);
    if (!msg.trim()) return;
    try {
      const r = await api.assistantSay(msg);
      // a typed or spoken yes/no answers the waiting proposal; a new proposal replaces it. Either way the older buttons go.
      setMsgs((m) => [...m.map((x) => (x.reply?.confirmation_id && (r.confirmed || r.cancelled || r.needs_confirmation) ? { ...x, reply: { ...x.reply, pending: false } } : x)),
        { who: "you", text: msg }, { who: "bot", reply: r, fresh: true }]);
      if (r.understood && r.navigate && NAV[r.navigate]) go(NAV[r.navigate]);
    } catch (e) { setError(e); }
    setText(""); setHeard(false);
  };

  const settle = (id: string, extra: Partial<AssistantReply>) =>
    setMsgs((m) => m.map((x) => (x.reply?.confirmation_id === id ? { ...x, reply: { ...x.reply!, pending: false, ...extra } } : x)));

  const decide = async (r: AssistantReply, yes: boolean) => {
    setError(null);
    const id = r.confirmation_id!;
    try {
      if (yes) {
        await api.assistantConfirm(id);
        settle(id, {});
        setMsgs((m) => [...m, { who: "bot", reply: { understood: true, tool: r.tool, confirmed: true, ok: true, item: r.item }, fresh: true }]);
      } else {
        await api.assistantCancel(id);
        settle(id, {});
        setMsgs((m) => [...m, { who: "bot", reply: { understood: true, tool: r.tool, cancelled: true, item: r.item }, fresh: true }]);
      }
    } catch (e) {
      settle(id, {});
      if (e instanceof ApiError && e.status === 410) setMsgs((m) => [...m, { who: "bot", reply: { understood: true, tool: r.tool, confirmed: true, ok: false }, fresh: true }]);
      else setError(e);
    }
  };

  const clear = async () => { setError(null); try { await api.assistantClear(); setMsgs([]); setNote(t("asClearOk")); } catch (e) { setError(e); } };
  const toggle = async () => {
    setError(null);
    try { const r = await api.assistantMemory(!memory); setMemory(r.memory); if (!r.memory) setMsgs([]); } catch (e) { setError(e); }
  };

  return (
    <>
      <Heading>{t("asTitle")}</Heading>
      <p className="lede">{t("asLede")}</p>
      <p className="hint">{t("asTry")}</p>
      <p className="hint">{memory ? t("asMemoryNote", { n: t.num(days) }) : t("asMemoryOffNote")}</p>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <button className="link" onClick={toggle}>{memory ? t("asForgetOn") : t("asForgetOff")}</button>
        {memory && msgs.length > 0 && <button className="link" onClick={clear}>{t("asClear")}</button>}
      </div>
      <ErrorNote error={error} />
      {note && <p role="status" className="hint">{note}</p>}
      <div role="log" aria-live="polite" style={{ display: "grid", gap: 10 }}>
        {msgs.map((m, k) => {
          if (m.who === "you") {
            return (
              <section key={k} className="p-card" aria-label={t("asYou")}>
                <p className="eyebrow">{t("asYou")}</p>
                <p style={{ margin: "4px 0" }}>{m.text}</p>
              </section>
            );
          }
          const r = m.reply;
          if (!r) return null;
          const lines = sentences(r);
          return (
            <section key={k} className="p-card" aria-label={t("asHelper")}>
              <p className="eyebrow">{t("asHelper")}</p>
              {lines.map((l, j) => <p key={j} style={{ margin: "4px 0" }}>{l}</p>)}
              {r.choices?.map((i) => (
                <button key={i.id} className="btn block" onClick={() => send(`${i.text_en ?? i.text_ar ?? ""}`)}>{title(i)}</button>
              ))}
              {r.needs_confirmation && r.pending !== false && (m.fresh || r.pending) && (
                <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
                  <button className="btn primary" onClick={() => decide(r, true)}>{t("asYes")}</button>
                  <button className="btn" onClick={() => decide(r, false)}>{t("asNo")}</button>
                </div>
              )}
              {canRead && lines.length > 0 && (
                <button className="link" onClick={() => reading ? (window.speechSynthesis.cancel(), setReading(false)) : read(lines.join(". "))}>
                  {reading ? t("asStopReading") : t("asReadAloud")}</button>
              )}
            </section>
          );
        })}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(text); }} style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <VoiceButton onText={(w) => { setText(w.slice(0, 300)); setHeard(true); }} />
        {heard && <p className="hint" role="status">{t("asHeard")}</p>}
        <input className="note" value={text} maxLength={300} placeholder={t("asPlaceholder")} aria-label={t("asPlaceholder")} onChange={(e) => setText(e.target.value)} />
        <button className="btn primary block" type="submit" disabled={!text.trim()}>{t("asSend")}</button>
      </form>
      {canRead && <p className="hint">{t("asReadNote")}</p>}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
