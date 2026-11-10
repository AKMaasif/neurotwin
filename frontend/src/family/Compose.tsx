import { useCallback, useEffect, useState } from "react";
import { api, Message } from "../api";
import { useT } from "../i18n";
import { ErrorNote, FormError } from "../ui";
import VoiceButton from "../voice";

const MAX = 300;

/** Write, preview, send. The message is stored as a draft when the preview is shown, and reaches the person only
 *  after Send. Going back to edit, or discarding, never sends it. */
export default function Compose({ pid, name }: { pid: string; name: string }) {
  const { t } = useT();
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Message | null>(null);
  const [sent, setSent] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [fromVoice, setFromVoice] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const loadSent = useCallback(() => {
    api.writtenMessages(pid).then((ms) => setSent(ms.filter((m) => m.status === "sent"))).catch(setError);
  }, [pid]);
  useEffect(loadSent, [loadSent]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e); }
    setBusy(false);
  };
  const preview = () => run(async () => setDraft(await api.draftMessage(pid, text)));
  const send = () => run(async () => { await api.sendMessage(draft!.id); setDraft(null); setText(""); setFromVoice(false); loadSent(); });
  const discard = () => run(async () => { await api.discardMessage(draft!.id); setDraft(null); setText(""); });

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {draft ? (
        <>
          <h3 style={{ margin: 0, fontSize: 16, color: "var(--muted)" }}>{t("fmPreviewTitle", { name })}</h3>
          <div className="p-card" style={{ background: "var(--surface-2, #f6f8fa)" }}>
            <p style={{ fontSize: "1.15em", margin: 0, whiteSpace: "pre-wrap" }} dir="auto">{draft.text}</p>
          </div>
          <p className="muted" style={{ fontSize: 14, margin: 0 }}>{t("fmNotSent", { name })}</p>
          <FormError error={error} />
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="btn primary" disabled={busy} onClick={send}>{t("fmSend")}</button>
            <button className="btn" disabled={busy} onClick={() => setDraft(null)}>{t("fmEdit")}</button>
            <button className="btn danger" disabled={busy} onClick={discard}>{t("fmDiscard")}</button>
          </div>
        </>
      ) : (
        <>
          <label className="field"><span>{t("fmWrite", { name })}</span>
            <textarea className="note" value={text} maxLength={MAX} dir="auto" style={{ minHeight: 96, fontSize: "1.05em" }}
              onChange={(e) => setText(e.target.value)} /></label>
          <p className="muted" style={{ fontSize: 14, margin: 0 }}>{t("fmHint", { name })} · {t("fmLeft", { n: t.num(MAX - text.length) })}</p>
          <VoiceButton onText={(w) => { setText((x) => (x ? `${x} ${w}` : w).slice(0, MAX)); setFromVoice(true); }} />
          {fromVoice && <p className="notice" style={{ margin: 0 }}>{t("voiceCheck")}</p>}
          <FormError error={error} />
          <button className="btn primary" style={{ justifySelf: "start" }} disabled={busy || !text.trim()} onClick={preview}>{t("fmPreview")}</button>
        </>
      )}
      {sent.length > 0 && (
        <>
          <h3 style={{ margin: "8px 0 0", fontSize: 16, color: "var(--muted)" }}>{t("fmSentList")}</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
            {sent.slice(0, 5).map((m) => (
              <li key={m.id}><span dir="auto">{m.text}</span>{" "}
                <span className="muted" style={{ fontSize: 13 }}>· {t.date(m.sent_at)} · {m.read ? t("fmSeen") : t("fmDelivered")}</span></li>
            ))}
          </ul>
        </>
      )}
      <ErrorNote error={draft ? null : error} />
    </div>
  );
}
