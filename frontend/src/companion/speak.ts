import { api } from "../api";

/** The companion's voice. Order: the server voice when the server has one and the person agreed to model use; otherwise the browser's own
 *  voice (a male voice if the device has one); otherwise nothing is spoken and the words stay on screen. `source()` says which is in use so
 *  the panel can tell the person plainly. Nothing here ever speaks without being asked by the session. */
export type Source = "server" | "browser" | "none";

export function pickVoice(lang: "en" | "ar"): SpeechSynthesisVoice | null {
  if (!("speechSynthesis" in window)) return null;
  const vs = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(lang));
  if (!vs.length) return null;
  // device voices rarely say their gender; common male voice names are preferred, otherwise the first voice for the language
  const male = /\b(male|david|mark|alex|daniel|james|google uk english male|tarik|maged|naayf|hamed|majed)\b/i;
  return vs.find((v) => male.test(v.name)) ?? vs[0];
}

export class Voice {
  speed = 1; volume = 1;
  private audio: HTMLAudioElement | null = null;
  private url: string | null = null;
  private gen = 0;
  server = false;
  last: string | null = null;      // what was last said, for the echo filter

  source(lang: "en" | "ar"): Source {
    if (this.server) return "server";
    return pickVoice(lang) ? "browser" : "none";
  }

  /** Speak `text`; resolves when it has finished or was stopped. */
  async say(text: string, lang: "en" | "ar", onStart?: () => void): Promise<void> {
    this.stop();
    const my = ++this.gen;
    this.last = text;
    if (this.server) {
      try {
        const wav = await api.speak(text, lang);
        if (my !== this.gen) return;
        this.url = URL.createObjectURL(wav);
        const a = new Audio(this.url); this.audio = a; a.volume = this.volume; a.playbackRate = this.speed;
        await new Promise<void>((res) => { a.onended = () => res(); a.onerror = () => res(); a.play().then(() => onStart?.()).catch(() => res()); });
        this.cleanup();
        return;
      } catch { this.server = false; /* fall through to the browser voice */ }
    }
    if (!("speechSynthesis" in window)) return;
    await new Promise<void>((res) => {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang === "ar" ? "ar" : "en"; u.rate = this.speed; u.volume = this.volume;
      const v = pickVoice(lang); if (v) u.voice = v;
      u.onstart = () => onStart?.(); u.onend = () => res(); u.onerror = () => res();
      window.speechSynthesis.speak(u);
    });
  }

  stop() {
    this.gen += 1;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (this.audio) { this.audio.pause(); }
    this.cleanup();
  }
  private cleanup() { if (this.url) URL.revokeObjectURL(this.url); this.url = null; this.audio = null; }
}
