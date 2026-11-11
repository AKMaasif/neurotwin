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
    <div className="fam-compose">
      {draft ? (
        <>
          <h2 className="fam-h">{t("fmPreviewTitle", { name })}</h2>
          <div className="fam-bubble">
            <p dir="auto">{draft.text}</p>
          </div>
          <p className="fam-muted">{t("fmNotSent", { name })}</p>
          <FormError error={error} />
          <div className="fam-actions">
            <button className="fam-btn" disabled={busy} onClick={send}>{t("fmSend")}</button>
            <button className="fam-btn ghost" disabled={busy} onClick={() => setDraft(null)}>{t("fmEdit")}</button>
            <button className="fam-btn danger" disabled={busy} onClick={discard}>{t("fmDiscard")}</button>
          </div>
        </>
      ) : (
        <>
          <label className="fam-field"><span>{t("fmWrite", { name })}</span>
            <textarea value={text} maxLength={MAX} dir="auto"
              onChange={(e) => setText(e.target.value)} /></label>
          <p className="fam-muted">{t("fmHint", { name })} · {t("fmLeft", { n: t.num(MAX - text.length) })}</p>
          <VoiceButton onText={(w) => { setText((x) => (x ? `${x} ${w}` : w).slice(0, MAX)); setFromVoice(true); }} />
          {fromVoice && <p className="fam-voice">{t("voiceCheck")}</p>}
          <FormError error={error} />
          <button className="fam-btn" disabled={busy || !text.trim()} onClick={preview}>{t("fmPreview")}</button>
        </>
      )}
      {sent.length > 0 && (
        <>
          <h2 className="fam-h">{t("fmSentList")}</h2>
          <ul className="fam-sent">
            {sent.slice(0, 5).map((m) => (
              <li key={m.id}><span dir="auto">{m.text}</span>
                <small>{t.date(m.sent_at)} · {m.read ? t("fmSeen") : t("fmDelivered")}</small></li>
            ))}
          </ul>
        </>
      )}
      <ErrorNote error={draft ? null : error} />
    </div>
  );
}
