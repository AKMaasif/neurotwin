import { useEffect, useRef, useState } from "react";
import { Mic, Square, X } from "lucide-react";
import { api } from "./api";
import { useT } from "./i18n";
import { FormError } from "./ui";

const MAX_SECONDS = 60;

/** Dictation into a text box. Recording starts only when the person presses the button, a red indicator and a
 *  timer stay on screen the whole time, and the microphone is released as soon as it stops. The words come back as
 *  text for the person to read and fix; nothing is sent or saved because of them. The button is hidden when the
 *  server has no speech provider or the browser cannot record. */
export default function VoiceButton({ onText }: { onText: (text: string) => void }) {
  const { t } = useT();
  const [available, setAvailable] = useState(false);
  const [state, setState] = useState<"idle" | "recording" | "working">("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const cancelled = useRef(false);

  useEffect(() => {
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) return;
    api.voiceStatus().then((s) => setAvailable(s.available)).catch(() => setAvailable(false));
    return () => release();
  }, []);

  useEffect(() => {
    if (state !== "recording") return;
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [state]);
  useEffect(() => { if (state === "recording" && seconds >= MAX_SECONDS) stop(); }, [seconds, state]);

  function release() {
    stream.current?.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
  }

  async function start() {
    setError(null); cancelled.current = false; chunks.current = []; setSeconds(0);
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch { setError(new Error(t("voiceDenied"))); return; }
    const r = new MediaRecorder(stream.current);
    r.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
    r.onstop = async () => {
      release();
      if (cancelled.current) { setState("idle"); return; }
      setState("working");
      try {
        const blob = new Blob(chunks.current, { type: r.mimeType || "audio/webm" });
        const out = await api.transcribe(blob, t.lang);
        if (out.text) onText(out.text); else setError(new Error(t("voiceNothing")));
      } catch (e) { setError(e); }
      setState("idle");
    };
    rec.current = r;
    r.start();
    setState("recording");
  }
  const stop = () => { if (rec.current?.state === "recording") rec.current.stop(); };
  const cancel = () => { cancelled.current = true; stop(); };

  if (!available) return null;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {state === "recording" ? (
        <div role="status" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span aria-hidden="true" style={{ width: 12, height: 12, borderRadius: "50%", background: "#c0392b" }} />
          <b>{t("voiceRecording")}</b>
          <span className="mono">{t.num(Math.floor(seconds / 60))}:{String(seconds % 60).padStart(2, "0")}</span>
          <button type="button" className="btn primary" onClick={stop}><Square size={14} aria-hidden="true" /> {t("voiceStop")}</button>
          <button type="button" className="btn" onClick={cancel}><X size={14} aria-hidden="true" /> {t("cancel")}</button>
        </div>
      ) : (
        <button type="button" className="btn" style={{ justifySelf: "start" }} disabled={state === "working"} onClick={start}>
          <Mic size={16} aria-hidden="true" /> {state === "working" ? t("voiceWorking") : t("voiceStart")}
        </button>
      )}
      <FormError error={error} />
    </div>
  );
}
