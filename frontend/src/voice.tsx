import { useEffect, useRef, useState } from "react";
import { Mic, Square, X } from "lucide-react";
import { api } from "./api";
import { useT } from "./i18n";
import { FormError } from "./ui";

const MAX_SECONDS = 60;
const RATE = 16000;

/** Browsers record WebM or MP4. Speech providers want plain audio, so the clip is turned into a mono 16 kHz,
 *  16-bit WAV here, in the browser, before it is sent. */
async function toWav(blob: Blob): Promise<Blob> {
  const ctx = new AudioContext();
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
  await ctx.close();
  const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * RATE)), RATE);
  const src = off.createBufferSource();
  src.buffer = decoded; src.connect(off.destination); src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const out = new DataView(new ArrayBuffer(44 + pcm.length * 2));
  const text = (o: number, s: string) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  text(0, "RIFF"); out.setUint32(4, 36 + pcm.length * 2, true); text(8, "WAVE"); text(12, "fmt ");
  out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true);
  out.setUint32(24, RATE, true); out.setUint32(28, RATE * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true);
  text(36, "data"); out.setUint32(40, pcm.length * 2, true);
  pcm.forEach((v, i) => out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 0x7fff, true));
  return new Blob([out], { type: "audio/wav" });
}

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
        const out = await api.transcribe(await toWav(blob), t.lang);
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
