import { describe, expect, it } from "vitest";
import { initial, step, micOpen, Ev, Session } from "./session";
import { defaultVad, isEcho, vadInit, vadStep, VadState } from "./vad";
import { downsample, rms, wavBytes } from "./pcm";

const run = (evs: Ev[], from: Session = initial) => evs.reduce(step, from);
const open = () => run([{ type: "open" }, { type: "granted" }]);

describe("session state machine", () => {
  it("never listens before an explicit open and permission", () => {
    expect(initial.phase).toBe("inactive");
    expect(micOpen(initial.phase)).toBe(false);
    expect(run([{ type: "open" }]).phase).toBe("requesting");
    expect(micOpen("requesting")).toBe(false);
    expect(run([{ type: "granted" }]).phase).toBe("inactive");       // permission without an open does nothing
  });
  it("permission denied is a stable state with a way back", () => {
    const s = run([{ type: "open" }, { type: "denied" }]);
    expect(s.phase).toBe("denied");
    expect(run([{ type: "open" }], s).phase).toBe("requesting");
  });
  it("walks a full turn and returns to listening", () => {
    let s = open();
    s = step(s, { type: "speech_start" }); expect(s.phase).toBe("hearing"); const t = s.turn;
    s = run([{ type: "finished", turn: t }, { type: "heard", turn: t }, { type: "replied", turn: t, speak: true }], s);
    expect(s.phase).toBe("speaking");
    expect(step(s, { type: "spoken_done" }).phase).toBe("listening");
  });
  it("ignores a duplicate or stale submission", () => {
    let s = open(); s = step(s, { type: "speech_start" }); const t = s.turn;
    s = step(s, { type: "finished", turn: t });
    const again = step(s, { type: "finished", turn: t });
    expect(again).toEqual(s);                                        // second "finished" changes nothing
    expect(step(s, { type: "heard", turn: t - 1 })).toEqual(s);      // a late answer for an old turn is dropped
  });
  it("the greeting is spoken after permission, then listening resumes", () => {
    const g = step(open(), { type: "greet" });
    expect(g.phase).toBe("speaking");
    expect(step(g, { type: "spoken_done" }).phase).toBe("listening");
    expect(step(initial, { type: "greet" }).phase).toBe("inactive");
  });
  it("barge-in stops speaking and starts a new turn", () => {
    let s = open(); s = step(s, { type: "speech_start" }); const t = s.turn;
    s = run([{ type: "finished", turn: t }, { type: "heard", turn: t }, { type: "replied", turn: t, speak: true }], s);
    const b = step(s, { type: "barge_in" });
    expect(b.phase).toBe("hearing"); expect(b.turn).toBe(t + 1);
  });
  it("noise that is too short returns to listening without a request", () => {
    let s = open(); s = step(s, { type: "speech_start" });
    expect(step(s, { type: "too_quiet", turn: s.turn }).phase).toBe("listening");
  });
  it("pause releases the microphone; resume listens again; end resets", () => {
    const p = step(open(), { type: "pause" });
    expect(p.phase).toBe("paused"); expect(micOpen(p.phase)).toBe(false);
    expect(step(p, { type: "resume" }).phase).toBe("listening");
    expect(step(open(), { type: "end" })).toEqual(initial);
  });
  it("device loss and offline are handled", () => {
    expect(step(open(), { type: "device_lost" }).phase).toBe("failed");
    const o = step(open(), { type: "offline" });
    expect(o.phase).toBe("offline"); expect(step(o, { type: "online" }).phase).toBe("listening");
  });
  it("a failed transcription or reply does not end the session", () => {
    let s = open(); s = step(s, { type: "speech_start" }); const t = s.turn;
    s = run([{ type: "finished", turn: t }, { type: "stt_failed", turn: t }], s);
    expect(s.phase).toBe("listening");
  });
});

/** Feed `ms` of constant loudness in 20 ms frames. */
function feed(v: VadState, level: number, ms: number, speaking = false) {
  let s = v; const outs: string[] = [];
  for (let t = 0; t < ms; t += 20) { const r = vadStep(s, level, 20, defaultVad, speaking); s = r.s; if (r.out !== "none") outs.push(r.out); }
  return { s, outs };
}

describe("voice activity detection", () => {
  it("waits through a long pause for a slow speaker, then ends after the configured silence", () => {
    let r = feed(vadInit(), 0.001, 1000);           // quiet room
    r = feed(r.s, 0.08, 800);                       // speech
    expect(r.outs).toEqual(["start"]);
    r = feed(r.s, 0.002, 1500, false);              // a 1.5 s thinking pause: still the same turn
    expect(r.outs).toEqual([]);
    r = feed(r.s, 0.08, 600);                       // continues
    r = feed(r.s, 0.002, 2000);                     // silence longer than 1.8 s
    expect(r.outs).toEqual(["end"]);
  });
  it("does not cut off by word count: 20 s of continuous speech stays one turn", () => {
    let r = feed(vadInit(), 0.08, 20000);
    expect(r.outs).toEqual(["start"]);
  });
  it("a click or cough is too short to become a turn", () => {
    let r = feed(vadInit(), 0.001, 500);
    r = feed(r.s, 0.2, 200);                        // ~200 ms burst
    r = feed(r.s, 0.001, 2000);
    expect(r.outs).toContain("too_short");
    expect(r.outs).not.toContain("end");
  });
  it("steady background noise raises the floor and is not speech", () => {
    const r = feed(vadInit(), 0.02, 5000);
    expect(r.outs.length).toBeLessThanOrEqual(1);
    const later = feed(r.s, 0.02, 3000);
    expect(later.outs).toEqual([]);
  });
  it("ends a turn at the maximum length", () => {
    const r = feed(vadInit(), 0.08, 50000);
    expect(r.outs).toContain("too_long");
  });
  it("leaked assistant speech does not barge in, a strong sustained voice does", () => {
    const quiet = feed(vadInit(), 0.001, 1000).s;
    expect(feed(quiet, 0.02, 3000, true).outs).toEqual([]);          // echo-level leak while speaking
    expect(feed(quiet, 0.2, 100, true).outs).toEqual([]);            // inside the guard period
    const r = feed(quiet, 0.2, 1000, true);
    expect(r.outs).toEqual(["barge"]);
  });
});

describe("echo and television filter", () => {
  it("drops a transcript that repeats the companion's own last line", () => {
    expect(isEcho("you have two things today the water and a walk", "You have two things today: the water and a walk.")).toBe(true);
  });
  it("keeps a genuine reply and short answers", () => {
    expect(isEcho("yes", "Mark the water as done?")).toBe(false);
    expect(isEcho("move the walk to later please", "You have two things today: the water and a walk.")).toBe(false);
    expect(isEcho("anything", null)).toBe(false);
  });
});

describe("pcm helpers", () => {
  it("measures loudness", () => { expect(rms(new Float32Array([0.5, -0.5, 0.5, -0.5]))).toBeCloseTo(0.5); expect(rms(new Float32Array(0))).toBe(0); });
  it("downsamples 48 kHz to 16 kHz by a third", () => { expect(downsample(new Float32Array(4800), 48000).length).toBe(1600); });
  it("writes a valid 16 kHz mono WAV header", () => {
    const b = wavBytes(new Float32Array(160)), v = new DataView(b);
    expect(new TextDecoder().decode(new Uint8Array(b, 0, 4))).toBe("RIFF");
    expect(v.getUint32(24, true)).toBe(16000); expect(v.getUint16(22, true)).toBe(1); expect(b.byteLength).toBe(44 + 320);
  });
});
