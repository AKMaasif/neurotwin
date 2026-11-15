/** Voice activity detection on short frames of microphone energy. Pure and configurable. A turn ends after `silenceMs` of quiet that
 *  follows real speech. There is no word-count cut-off, so a slow speaker with long pauses is not cut short; the person can always say
 *  or press "I'm finished". Noise that is too short or too quiet never becomes a turn. */
export type VadConfig = { silenceMs: number; minSpeechMs: number; maxTurnMs: number; floorMin: number; startRatio: number; bargeRatio: number; bargeMs: number; bargeGuardMs: number };
export const defaultVad: VadConfig = { silenceMs: 1800, minSpeechMs: 350, maxTurnMs: 45000, floorMin: 0.012, startRatio: 3, bargeRatio: 6, bargeMs: 300, bargeGuardMs: 400 };

export type VadState = { floor: number; speaking: boolean; loudMs: number; speechMs: number; quietMs: number; turnMs: number; bargeMs: number; sinceTtsMs: number };
export type VadOut = "none" | "start" | "end" | "too_short" | "too_long" | "barge";

export const vadInit = (): VadState => ({ floor: 0.01, speaking: false, loudMs: 0, speechMs: 0, quietMs: 0, turnMs: 0, bargeMs: 0, sinceTtsMs: 0 });

/** One frame: `rms` 0..1, `dt` ms of audio in the frame, `assistantSpeaking` true while the companion's own voice is playing. */
export function vadStep(v: VadState, rms: number, dt: number, cfg: VadConfig, assistantSpeaking: boolean): { s: VadState; out: VadOut } {
  const s = { ...v };
  const thr = Math.max(cfg.floorMin, s.floor * cfg.startRatio);
  if (assistantSpeaking) {
    s.sinceTtsMs += dt;
    // the companion's own voice may leak back in: only a clearly stronger, sustained sound after a short guard counts as the person
    const bargeThr = Math.max(cfg.floorMin * 4, s.floor * cfg.bargeRatio);
    s.bargeMs = s.sinceTtsMs > cfg.bargeGuardMs && rms > bargeThr ? s.bargeMs + dt : 0;
    if (s.bargeMs >= cfg.bargeMs) return { s: { ...vadInit(), floor: s.floor, speaking: true, speechMs: s.bargeMs, loudMs: s.bargeMs }, out: "barge" };
    return { s, out: "none" };
  }
  s.sinceTtsMs = 0; s.bargeMs = 0;
  if (!s.speaking) {
    if (rms > thr) { s.loudMs += dt; } else { s.loudMs = 0; s.floor = Math.max(0.002, s.floor * 0.95 + rms * 0.05); }
    if (s.loudMs >= Math.min(cfg.minSpeechMs, 200)) { return { s: { ...s, speaking: true, speechMs: s.loudMs, quietMs: 0, turnMs: s.loudMs }, out: "start" }; }
    return { s, out: "none" };
  }
  s.turnMs += dt;
  if (rms > thr) { s.speechMs += dt; s.quietMs = 0; } else { s.quietMs += dt; }
  if (s.turnMs >= cfg.maxTurnMs) return { s: { ...vadInit(), floor: s.floor }, out: "too_long" };
  if (s.quietMs >= cfg.silenceMs) {
    const out: VadOut = s.speechMs >= cfg.minSpeechMs ? "end" : "too_short";
    return { s: { ...vadInit(), floor: s.floor }, out };
  }
  return { s, out: "none" };
}

/** Words the companion itself just said, heard again through a speaker, or a television repeating a phrase, must not become a command.
 *  A transcript that is nearly all words from the companion's last line is dropped. */
export function isEcho(heard: string, spoken: string | null | undefined): boolean {
  if (!spoken) return false;
  const tok = (x: string) => x.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);
  const a = tok(heard), b = new Set(tok(spoken));
  if (a.length < 3) return false;
  return a.filter((w) => b.has(w)).length / a.length >= 0.8;
}
