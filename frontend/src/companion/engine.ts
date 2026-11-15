import { defaultVad, VadConfig, vadInit, vadStep, VadState } from "./vad";
import { downsample, rms, wavBytes } from "./pcm";

/** The microphone loop. It opens the microphone only when `start()` is called (after the person opened the companion, agreed to voice and
 *  allowed the browser), asks the browser for echo cancellation and noise suppression, keeps a half-second of audio before speech so the
 *  first word is not lost, and hands back one finished turn at a time as a WAV. `stop()` releases every track and closes the audio context. */
export type EngineEvents = {
  onStart: () => void; onTurn: (wav: Blob, turn: number) => void; onTooShort: () => void; onBarge: () => void;
  onLevel: (level: number) => void; onLost: () => void;
};

const PRE_ROLL_MS = 500;

export class Engine {
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private node: ScriptProcessorNode | null = null;
  private src: MediaStreamAudioSourceNode | null = null;
  private vad: VadState = vadInit();
  private frames: Float32Array[] = [];
  private pre: Float32Array[] = [];
  private preMs = 0;
  private capturing = false;
  private rate = 48000;
  private turn = 0;
  private gen = 0;
  private holdUntil = 0;
  private _speaking = false;  // true while the companion's own voice plays
  muted = false;
  get speaking() { return this._speaking; }
  /** While the companion talks, only a strong sustained voice counts. When it stops, the first 300 ms (its own echo tail) are ignored. */
  setSpeaking(b: boolean) { if (this._speaking && !b) this.holdUntil = performance.now() + 300; this._speaking = b; }
  setMuted(b: boolean) { this.muted = b; this.stream?.getAudioTracks().forEach((tr) => { tr.enabled = !b; }); if (b) this.discard(); }
  cfg: VadConfig = { ...defaultVad };

  constructor(private ev: EngineEvents) {}

  get active() { return this.stream !== null; }

  async start(): Promise<void> {
    if (this.stream) return;
    const my = ++this.gen;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    if (my !== this.gen) { stream.getTracks().forEach((tr) => tr.stop()); throw new Error("cancelled"); }   // stopped while the browser was asking
    this.stream = stream;
    stream.getAudioTracks().forEach((tr) => { tr.onended = () => { if (this.stream) this.ev.onLost(); }; });
    const ctx = new AudioContext();
    this.ctx = ctx; this.rate = ctx.sampleRate;
    this.src = ctx.createMediaStreamSource(stream);
    this.node = ctx.createScriptProcessor(2048, 1, 1);
    this.node.onaudioprocess = (e) => this.frame(new Float32Array(e.inputBuffer.getChannelData(0)));
    this.src.connect(this.node); this.node.connect(ctx.destination);   // destination is silent: the output buffer is never written
    this.vad = vadInit();
  }

  /** Begin a turn right away (barge-in or "I'm listening again"): audio from now on belongs to it. */
  private frame(x: Float32Array) {
    if (this.muted || performance.now() < this.holdUntil) { this.ev.onLevel(0); return; }
    const dt = (x.length / this.rate) * 1000, level = rms(x);
    this.ev.onLevel(level);
    const { s, out } = vadStep(this.vad, level, dt, this.cfg, this._speaking);
    this.vad = s;
    if (out === "start" || out === "barge") {
      this.frames = [...this.pre, x]; this.pre = []; this.preMs = 0; this.capturing = true; this.turn += 1;
      if (out === "barge") this.ev.onBarge(); else this.ev.onStart();
      return;
    }
    if (this.capturing) {
      this.frames.push(x);
      if (out === "end" || out === "too_long") this.finish();
      else if (out === "too_short") { this.discard(); this.ev.onTooShort(); }
      return;
    }
    this.pre.push(x); this.preMs += dt;
    while (this.preMs > PRE_ROLL_MS && this.pre.length) { this.preMs -= (this.pre.shift()!.length / this.rate) * 1000; }
  }

  /** The person pressed "I'm finished", or the silence ran out. Returns false if there was no turn to send. */
  finish(): boolean {
    if (!this.capturing) return false;
    const all = this.frames; this.discard();
    const len = all.reduce((n, f) => n + f.length, 0), flat = new Float32Array(len);
    let o = 0; for (const f of all) { flat.set(f, o); o += f.length; }
    this.vad = { ...vadInit(), floor: this.vad.floor };
    this.ev.onTurn(new Blob([wavBytes(downsample(flat, this.rate))], { type: "audio/wav" }), this.turn);
    return true;
  }
  private discard() { this.frames = []; this.capturing = false; this.vad = { ...vadInit(), floor: this.vad.floor }; }

  /** Release the microphone completely. Safe to call twice. */
  stop() {
    this.gen += 1;
    this.node && (this.node.onaudioprocess = null);
    try { this.src?.disconnect(); this.node?.disconnect(); } catch { /* already gone */ }
    this.stream?.getTracks().forEach((tr) => { tr.onended = null; tr.stop(); });
    this.ctx?.close().catch(() => {});
    this.stream = null; this.ctx = null; this.node = null; this.src = null;
    this.frames = []; this.pre = []; this.preMs = 0; this.capturing = false; this._speaking = false; this.muted = false;
    this.vad = vadInit();
  }
}
