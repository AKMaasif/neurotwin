/** The companion's conversation state machine. Pure: no browser, no network. The UI and the audio loop only send events and
 *  render the state, so the rules (what may happen after what) live, and are tested, in one place.
 *
 *  inactive → requesting → listening → hearing → transcribing → interpreting → speaking → listening …
 *  Side states: paused (microphone released), denied, failed, offline.
 *  Every turn has a number. An event for an older turn is ignored, so a late transcript or a repeated "finished" never submits twice. */
export type Phase = "inactive" | "requesting" | "listening" | "hearing" | "transcribing" | "interpreting" | "speaking" | "paused" | "denied" | "failed" | "offline";

export type Session = { phase: Phase; turn: number; resume: Phase | null; reason: string | null };

export type Ev =
  | { type: "open" } | { type: "granted" } | { type: "denied" }
  | { type: "speech_start" } | { type: "finished"; turn: number } | { type: "too_quiet"; turn: number }
  | { type: "heard"; turn: number } | { type: "nothing"; turn: number } | { type: "stt_failed"; turn: number }
  | { type: "replied"; turn: number; speak: boolean } | { type: "reply_failed"; turn: number }
  | { type: "greet" } | { type: "spoken_done" } | { type: "barge_in" } | { type: "stop_speaking" }
  | { type: "pause" } | { type: "resume" } | { type: "end" } | { type: "device_lost" }
  | { type: "offline" } | { type: "online" } | { type: "retry" };

export const initial: Session = { phase: "inactive", turn: 0, resume: null, reason: null };

const LIVE: Phase[] = ["listening", "hearing", "transcribing", "interpreting", "speaking"];

export function step(s: Session, e: Ev): Session {
  const go = (phase: Phase, extra: Partial<Session> = {}): Session => ({ ...s, phase, reason: null, ...extra });
  switch (e.type) {
    case "open": return s.phase === "inactive" || s.phase === "denied" || s.phase === "failed" ? go("requesting", { turn: 0, resume: null }) : s;
    case "granted": return s.phase === "requesting" ? go("listening") : s;
    case "denied": return s.phase === "requesting" || LIVE.includes(s.phase) ? go("denied") : s;
    case "end": return go("inactive", { turn: 0, resume: null });
    case "device_lost": return s.phase === "inactive" ? s : go("failed", { reason: "device", resume: null });
    case "retry": return s.phase === "failed" || s.phase === "offline" ? go("requesting") : s;
    case "offline": return LIVE.includes(s.phase) ? go("offline", { resume: s.phase === "speaking" ? "listening" : s.phase }) : s;
    case "online": return s.phase === "offline" ? go("listening", { resume: null }) : s;
    case "pause": return LIVE.includes(s.phase) ? go("paused", { resume: null }) : s;
    case "resume": return s.phase === "paused" ? go("listening") : s;
    case "speech_start":
      // while hearing nothing new; while speaking this is only valid through "barge_in"
      return s.phase === "listening" ? go("hearing", { turn: s.turn + 1 }) : s;
    case "barge_in": return s.phase === "speaking" ? go("hearing", { turn: s.turn + 1 }) : s;
    case "stop_speaking": return s.phase === "speaking" ? go("listening") : s;
    case "finished": return s.phase === "hearing" && e.turn === s.turn ? go("transcribing") : s;
    case "too_quiet": return s.phase === "hearing" && e.turn === s.turn ? go("listening") : s;
    case "heard": return s.phase === "transcribing" && e.turn === s.turn ? go("interpreting") : s;
    case "nothing": return s.phase === "transcribing" && e.turn === s.turn ? go("listening", { reason: "nothing" }) : s;
    case "stt_failed": return s.phase === "transcribing" && e.turn === s.turn ? go("listening", { reason: "stt" }) : s;
    case "replied": return s.phase === "interpreting" && e.turn === s.turn ? go(e.speak ? "speaking" : "listening") : s;
    case "reply_failed": return s.phase === "interpreting" && e.turn === s.turn ? go("listening", { reason: "reply" }) : s;
    case "greet": return s.phase === "listening" ? go("speaking") : s;
    case "spoken_done": return s.phase === "speaking" ? go("listening") : s;
  }
}

/** The microphone should be open (and listening for speech) only in these phases. Everything else releases it. */
export const micOpen = (p: Phase) => p === "listening" || p === "hearing" || p === "transcribing" || p === "interpreting" || p === "speaking";
