import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { ChevronDown, Keyboard, Mic, MicOff, Pause, Play, Square, UserRound, X, Maximize2, Minimize2, Volume2 } from "lucide-react";
import { api, ApiError, AssistantReply, CompanionConfig, User } from "../api";
import { useT } from "../i18n";
import { initial, micOpen, Phase, step, Ev } from "../companion/session";
import { Engine } from "../companion/engine";
import { Voice } from "../companion/speak";
import { defaultVad, isEcho } from "../companion/vad";
import { replySentences } from "./replyText";
import type { Screen } from "./PersonalApp";

const NAV: Record<string, Screen> = { prep: "prep", report: "report", concern: "concern", reminders: "reminders", messages: "messages", records: "records", home: "home", urgent: "urgent", checkin: "checkin", reaction: "reaction", memory: "memory", wellbeing: "wellbeing" };
type Line = { who: "you" | "bot"; text: string };
type Prefs = { speed: number; volume: number; silence: number; keepBg: boolean; captions: boolean; review: boolean };
const PREFS_KEY = "nt.companion.prefs";
const defaults: Prefs = { speed: 1, volume: 1, silence: 1.8, keepBg: false, captions: true, review: false };
const loadPrefs = (): Prefs => { try { return { ...defaults, ...JSON.parse(localStorage.getItem(PREFS_KEY) || "{}") }; } catch { return defaults; } };
const savePrefs = (p: Prefs) => { try { localStorage.setItem(PREFS_KEY, JSON.stringify(p)); } catch { /* private mode: settings last for this visit only */ } };

/** A voice-first companion for the patient app. It lives above every patient screen, so a conversation survives moving between them.
 *  The microphone is opened only after the person presses "Start talking", has agreed to voice, and the browser has allowed it. Every
 *  request goes through the same assistant as the typed Ask screen (fixed, validated actions; changes only after a visible Yes). */
export default function Companion({ user, tabbed, go }: { user: User; tabbed: boolean; go: (s: Screen) => void }) {
  const { t } = useT();
  const [cfg, setCfg] = useState<CompanionConfig | null>(null);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [sess, send] = useReducer(step, initial);
  const sref = useRef(sess);
  const [lines, setLines] = useState<Line[]>([]);
  const [level, setLevel] = useState(0);
  const [muted, setMutedState] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState<AssistantReply | null>(null);
  const [draft, setDraft] = useState("");
  const [typed, setTyped] = useState("");
  const [memory, setMemory] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [source, setSource] = useState<"server" | "browser" | "none">("none");
  const engine = useRef<Engine | null>(null);
  const voice = useRef(new Voice());
  const busy = useRef(false);
  const lang = t.lang as "en" | "ar";

  /** One place changes the session, so the ref used by audio callbacks never lags behind what the screen shows. */
  const dispatch = useCallback((e: Ev) => { const n = step(sref.current, e); sref.current = n; send(e); return n; }, []);

  useEffect(() => { api.companionConfig().then(setCfg).catch(() => setCfg(null)); }, []);
  useEffect(() => { if (open) api.assistantHistory().then((h) => setMemory(h.memory)).catch(() => {}); }, [open]);
  useEffect(() => { voice.current.speed = prefs.speed; voice.current.volume = prefs.volume; if (engine.current) engine.current.cfg = { ...defaultVad, silenceMs: prefs.silence * 1000 }; savePrefs(prefs); }, [prefs]);
  useEffect(() => { voice.current.server = !!(cfg?.tts.server && cfg.model.consented); setSource(voice.current.source(lang)); }, [cfg, lang]);
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const f = () => setSource(voice.current.source(lang));
    window.speechSynthesis.addEventListener?.("voiceschanged", f);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", f);
  }, [lang]);

  const stopAll = useCallback(() => { voice.current.stop(); engine.current?.stop(); engine.current = null; setLevel(0); setMutedState(false); }, []);
  // Whatever happens, leaving the patient app (sign-out, closing) releases the microphone and stops speech.
  useEffect(() => stopAll, [stopAll]);
  // The microphone follows the phase: any phase that is not "listening-ish" has it released.
  useEffect(() => { if (!micOpen(sess.phase) && sess.phase !== "requesting") { engine.current?.stop(); engine.current = null; setLevel(0); } }, [sess.phase]);

  const add = (who: Line["who"], text: string) => setLines((l) => [...l.slice(-11), { who, text }]);

  const speak = useCallback(async (text: string) => {
    const cut = text.slice(0, cfg?.limits.speak_chars ?? 600);
    engine.current?.setSpeaking(true);
    try { await voice.current.say(cut, lang); } finally { engine.current?.setSpeaking(false); }
    dispatch({ type: "spoken_done" });          // ignored unless the session was speaking
  }, [cfg, lang, dispatch]);

  /** A request from the person (spoken, or typed or edited) goes to the same assistant as the Ask screen. */
  const handle = useCallback(async (text: string, turn: number | null, spoken: boolean) => {
    if (busy.current) return;
    busy.current = true; setNote(null);
    try {
      const r = await api.assistantSay(text);
      const out = replySentences(t, r);
      add("you", text);
      if (out.length) add("bot", out.join(" "));
      setPending(r.needs_confirmation && r.confirmation_id ? r : null);
      if (r.understood && r.navigate && NAV[r.navigate]) go(NAV[r.navigate]);
      const talk = spoken && out.length > 0 && !muted;
      if (turn !== null) {
        const n = dispatch({ type: "replied", turn, speak: talk });
        if (n.phase === "speaking") void speak(out.join(". "));
      } else if (sref.current.phase !== "inactive" && sref.current.phase !== "paused" && out.length) void speak(out.join(". "));
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : t("cmpFailed"));
      if (turn !== null) dispatch({ type: "reply_failed", turn });
    } finally { busy.current = false; }
  }, [t, go, dispatch, speak, muted]);

  const transcribe = useCallback(async (wav: Blob, turn: number) => {
    try {
      const out = await api.transcribe(wav, lang);
      const text = (out.text || "").trim();
      if (!text) { dispatch({ type: "nothing", turn }); setNote(t("cmpNothing")); return; }
      if (isEcho(text, voice.current.last)) { dispatch({ type: "nothing", turn }); return; }   // its own voice, or a television
      if (prefs.review) { dispatch({ type: "nothing", turn }); dispatch({ type: "pause" }); setDraft(text); return; }
      if (dispatch({ type: "heard", turn }).phase === "interpreting") await handle(text, turn, true);
    } catch (e) {
      dispatch({ type: "stt_failed", turn });
      setNote(e instanceof ApiError && e.status === 403 ? t("cmpNeedsConsent") : e instanceof ApiError ? e.message : t("cmpNothing"));
    }
  }, [lang, dispatch, handle, t, prefs.review]);

  const makeEngine = useCallback(() => new Engine({
    onStart: () => { dispatch({ type: "speech_start" }); },
    onBarge: () => { voice.current.stop(); engine.current?.setSpeaking(false); dispatch({ type: "barge_in" }); },
    onTooShort: () => { dispatch({ type: "too_quiet", turn: sref.current.turn }); },
    onTurn: (wav) => { const turn = sref.current.turn; if (dispatch({ type: "finished", turn }).phase === "transcribing") void transcribe(wav, turn); },
    onLevel: (l) => setLevel(Math.min(1, l * 8)),
    onLost: () => { dispatch({ type: "device_lost" }); stopAll(); },
  }), [dispatch, transcribe, stopAll]);

  const begin = async (greet: boolean) => {
    setNote(null);
    const e = makeEngine(); e.cfg = { ...defaultVad, silenceMs: prefs.silence * 1000 };
    engine.current = e;
    dispatch({ type: sref.current.phase === "offline" ? "retry" : "open" });
    try { await e.start(); } catch { engine.current = null; dispatch({ type: "denied" }); return; }
    dispatch({ type: "granted" });
    if (greet) {
      const hello = user.display_name ? t("cmpGreetName", { name: user.display_name }) : t("cmpGreet");   // the display name only, nothing else
      add("bot", hello); dispatch({ type: "greet" }); void speak(hello);
    }
  };
  const resume = async () => { dispatch({ type: "resume" }); const e = makeEngine(); e.cfg = { ...defaultVad, silenceMs: prefs.silence * 1000 }; engine.current = e; try { await e.start(); } catch { engine.current = null; dispatch({ type: "denied" }); } };
  const pause = () => { voice.current.stop(); dispatch({ type: "pause" }); };
  const end = () => { stopAll(); dispatch({ type: "end" }); setLines([]); setPending(null); setDraft(""); setNote(t("cmpEnded")); };
  const mute = () => { const m = !muted; setMutedState(m); engine.current?.setMuted(m); };
  const finished = () => { engine.current?.finish(); };
  const stopSpeaking = () => { voice.current.stop(); engine.current?.setSpeaking(false); dispatch({ type: "stop_speaking" }); };

  // visibility, connectivity
  useEffect(() => {
    const vis = () => { if (document.hidden && !prefs.keepBg && micOpen(sref.current.phase)) { voice.current.stop(); dispatch({ type: "pause" }); setNote(t("cmpHidden")); } };
    const off = () => { if (micOpen(sref.current.phase)) { voice.current.stop(); dispatch({ type: "offline" }); } };
    const on = () => { if (sref.current.phase === "offline") void begin(false); };
    document.addEventListener("visibilitychange", vis); window.addEventListener("offline", off); window.addEventListener("online", on);
    return () => { document.removeEventListener("visibilitychange", vis); window.removeEventListener("offline", off); window.removeEventListener("online", on); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefs.keepBg, t, dispatch]);

  const minimise = () => { setOpen(false); setExpanded(false); if (!prefs.keepBg && micOpen(sref.current.phase)) pause(); };

  const grant = async (scope: "voice_recording" | "assistant_model", granted: boolean) => {
    try { await api.setConsent(scope, granted, lang); setCfg(await api.companionConfig()); if (!granted) { if (scope === "voice_recording") end(); } } catch (e) { setNote(e instanceof ApiError ? e.message : t("cmpFailed")); }
  };

  const decide = async (r: AssistantReply, yes: boolean) => {
    const id = r.confirmation_id; if (!id) return;
    setPending(null);
    try {
      if (yes) { await api.assistantConfirm(id); add("bot", t("asDoneOk")); } else { await api.assistantCancel(id); add("bot", t("asCancelled")); }
    } catch (e) { add("bot", e instanceof ApiError && e.status === 410 ? t("asTooLate") : t("cmpFailed")); }
  };

  const phase: Phase = sess.phase;
  const label = !cfg?.stt.available && phase === "inactive" ? t("cmpState_unavailable") : t(`cmpState_${phase}` as "cmpState_inactive");
  const consented = !!cfg?.stt.consented;
  const live = micOpen(phase);
  const Icon = phase === "paused" || phase === "denied" || muted ? MicOff : phase === "speaking" ? Volume2 : phase === "inactive" ? UserRound : Mic;
  const cls = useMemo(() => `cmp-wrap ${tabbed ? "has-tabs" : ""} ${expanded ? "big" : ""}`, [tabbed, expanded]);
  if (!cfg?.enabled) return null;

  return (
    <div className={cls} data-phase={phase}>
      {!open && (
        <button className="cmp-launch" onClick={() => setOpen(true)} aria-label={`${t("cmpLauncher")}. ${label}`}>
          <span className="cmp-avatar" aria-hidden="true"><Icon size={26} /></span>
          <span className="cmp-launch-text">{t("cmpLauncher")}<small>{live ? t("cmpMicOn") : t("cmpMicOff")} · {label}</small></span>
        </button>
      )}
      {open && (
        <section className="cmp-panel" role="dialog" aria-modal="false" aria-label={t("cmpAria")}>
          <header className="cmp-head">
            <span className="cmp-avatar" aria-hidden="true"><Icon size={22} /></span>
            <div className="cmp-title"><b>{t("cmpTitle")}</b>
              <span role="status" aria-live="polite" className="cmp-state">{label} · {live ? t("cmpMicOn") : t("cmpMicOff")}{muted ? ` · ${t("cmpMute")}` : ""}</span>
            </div>
            <button className="cmp-ico" onClick={() => setExpanded((x) => !x)} aria-label={expanded ? t("cmpMinimize") : t("cmpExpand")}>{expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}</button>
            <button className="cmp-ico" onClick={minimise} aria-label={t("cmpClose")}><ChevronDown size={18} /></button>
          </header>
          <p className="hint" style={{ margin: 0 }}>{t(`cmpVoice_${source}` as "cmpVoice_none")}</p>
          {live && <div className="cmp-meter" aria-hidden="true"><i style={{ width: `${Math.round(level * 100)}%` }} /></div>}
          {note && <p className="cmp-note" role="status">{note}</p>}
          {phase === "denied" && <p className="cmp-note" role="alert">{t("cmpDenied")}</p>}
          {phase === "failed" && <p className="cmp-note" role="alert">{t("cmpLost")}</p>}

          {!cfg.stt.available && <p className="cmp-note">{t("cmpNoStt")}</p>}
          {cfg.stt.available && !consented && (
            <div className="cmp-card">
              <b>{t("cmpConsentTitle")}</b><p>{t("cmpConsentBody")}</p>
              <div className="cmp-row"><button className="btn primary" onClick={() => grant("voice_recording", true)}>{t("cmpConsentAllow")}</button><button className="btn" onClick={minimise}>{t("cmpConsentLater")}</button></div>
            </div>
          )}

          {cfg.stt.available && consented && cfg.tts.server && !cfg.model.consented && (
            <div className="cmp-card">
              <p>{t("cmpModelConsent")}</p>
              <div className="cmp-row"><button className="btn primary" onClick={() => grant("assistant_model", true)}>{t("cmpModelAllow")}</button></div>
            </div>
          )}

          {cfg.stt.available && consented && (phase === "inactive" || phase === "denied" || phase === "failed") && (
            <button className="btn primary block" onClick={() => begin(true)}><Mic size={16} aria-hidden="true" /> {t("cmpStart")}</button>
          )}

          {prefs.captions && lines.length > 0 && (
            <div className="cmp-log" role="log" aria-live="polite" aria-label={t("cmpCaptions")}>
              {lines.map((l, i) => <p key={i} className={l.who}><b>{l.who === "you" ? t("asYou") : t("asHelper")}:</b> {l.text}</p>)}
            </div>
          )}

          {draft && (
            <div className="cmp-card">
              <label htmlFor="cmp-draft">{t("cmpHeard")}</label>
              <input id="cmp-draft" className="note" value={draft} maxLength={300} onChange={(e) => setDraft(e.target.value)} />
              <div className="cmp-row">
                <button className="btn primary" disabled={!draft.trim()} onClick={() => { const d = draft; setDraft(""); void resume().then(() => handle(d, null, true)); }}>{t("cmpSendHeard")}</button>
                <button className="btn" onClick={() => setDraft("")}>{t("cmpDiscard")}</button>
              </div>
            </div>
          )}

          {pending && (
            <div className="cmp-card" role="group" aria-label={t("asHelper")}>
              <p>{t("cmpSayYes")}</p>
              <div className="cmp-row"><button className="btn primary" onClick={() => decide(pending, true)}>{t("asYes")}</button><button className="btn" onClick={() => decide(pending, false)}>{t("asNo")}</button></div>
            </div>
          )}

          <div className="cmp-controls">
            {phase === "hearing" && <button className="btn primary" onClick={finished}><Square size={16} aria-hidden="true" /> {t("cmpFinished")}</button>}
            {phase === "speaking" && <button className="btn" onClick={stopSpeaking}><Square size={16} aria-hidden="true" /> {t("cmpStopSpeak")}</button>}
            {live && <button className="btn" onClick={mute} aria-pressed={muted}>{muted ? <MicOff size={16} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />} {muted ? t("cmpUnmute") : t("cmpMute")}</button>}
            {live && <button className="btn" onClick={pause}><Pause size={16} aria-hidden="true" /> {t("cmpPause")}</button>}
            {phase === "paused" && <button className="btn primary" onClick={() => void resume()}><Play size={16} aria-hidden="true" /> {t("cmpResume")}</button>}
            {phase === "offline" && <button className="btn" onClick={() => void begin(false)}>{t("cmpRetry")}</button>}
            {live && <button className="btn" onClick={() => { pause(); document.getElementById("cmp-type")?.focus(); }}><Keyboard size={16} aria-hidden="true" /> {t("cmpType")}</button>}
            {(live || phase === "paused" || phase === "offline") && <button className="btn" onClick={end}><X size={16} aria-hidden="true" /> {t("cmpEnd")}</button>}
          </div>

          <form className="cmp-type" onSubmit={(e) => { e.preventDefault(); const x = typed.trim(); if (x) { setTyped(""); void handle(x, null, live && !muted); } }}>
            <input id="cmp-type" className="note" value={typed} maxLength={300} placeholder={t("cmpTypePlaceholder")} aria-label={t("cmpTypePlaceholder")} onChange={(e) => setTyped(e.target.value)} />
            <button className="btn" type="submit" disabled={!typed.trim()}>{t("asSend")}</button>
          </form>

          <button className="link" aria-expanded={showSettings} onClick={() => setShowSettings((x) => !x)}>{t("cmpHistory")}</button>
          {showSettings && (
            <div className="cmp-card">
              <p className="hint">{t(`cmpVoice_${source}` as "cmpVoice_none")}</p>
              <label>{t("cmpSpeed")}: {t.num(prefs.speed)}<input type="range" min={0.7} max={1.3} step={0.1} value={prefs.speed} onChange={(e) => setPrefs({ ...prefs, speed: +e.target.value })} /></label>
              <label>{t("cmpVolume")}: {t.num(Math.round(prefs.volume * 100))}%<input type="range" min={0.2} max={1} step={0.1} value={prefs.volume} onChange={(e) => setPrefs({ ...prefs, volume: +e.target.value })} /></label>
              <label>{t("cmpSilence")}: {t("cmpSilenceUnit", { n: t.num(prefs.silence) })}<input type="range" min={1} max={4} step={0.5} value={prefs.silence} onChange={(e) => setPrefs({ ...prefs, silence: +e.target.value })} /></label>
              <label className="cmp-check"><input type="checkbox" checked={prefs.captions} onChange={(e) => setPrefs({ ...prefs, captions: e.target.checked })} /> {t("cmpCaptions")}</label>
              <label className="cmp-check"><input type="checkbox" checked={prefs.review} onChange={(e) => setPrefs({ ...prefs, review: e.target.checked })} /> {t("cmpHeard")}</label>
              <label className="cmp-check"><input type="checkbox" checked={prefs.keepBg} onChange={(e) => setPrefs({ ...prefs, keepBg: e.target.checked })} /> {t("cmpKeepBg")}</label>
              <p className="hint">{t("cmpKeepBgNote")}</p>
              <p className="hint">{memory ? t("asMemoryNote", { n: t.num(30) }) : t("asMemoryOffNote")}</p>
              <div className="cmp-row">
                <button className="link" onClick={async () => { try { const r = await api.assistantMemory(!memory); setMemory(r.memory); } catch { setNote(t("cmpFailed")); } }}>{memory ? t("asForgetOn") : t("asForgetOff")}</button>
                <button className="link" onClick={async () => { try { await api.assistantClear(); setLines([]); setNote(t("asClearOk")); } catch { setNote(t("cmpFailed")); } }}>{t("asClear")}</button>
              </div>
              {cfg.model.available && (cfg.model.consented
                ? <div className="cmp-row"><span className="hint">{t("cmpModelOn")}</span><button className="link" onClick={() => grant("assistant_model", false)}>{t("cmpModelRevoke")}</button></div>
                : <div><p className="hint">{t("cmpModelConsent")}</p><button className="btn" onClick={() => grant("assistant_model", true)}>{t("cmpModelAllow")}</button></div>)}
              {consented && <button className="link" onClick={() => grant("voice_recording", false)}>{t("cmpVoiceRevoke")}</button>}
              <p className="hint">{t("cmpMicHint")}</p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
