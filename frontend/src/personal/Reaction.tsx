import { useCallback, useEffect, useRef, useState } from "react";
import { api, Observation } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

// Prototype simple reaction-time activity, version 0.1. Engineering settings, not clinical ones:
const TRIALS = 5;            // timed taps after one practice
const MAX_ATTEMPTS = 10;     // stop asking after this many attempts (early or missed taps count)
const MIN_WAIT = 1500, MAX_WAIT = 4000;   // ms before the box changes
const TIMEOUT = 3000;        // ms after the change before a tap counts as missed

type Phase = "intro" | "practice" | "practiceDone" | "trials" | "stopping" | "saving" | "done";
type Pad = "wait" | "go" | "early" | "missed";

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b), m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

export default function Reaction({ onDone }: { onDone: () => void }) {
  const { t } = useT();
  const [phase, setPhase] = useState<Phase>("intro");
  const [pad, setPad] = useState<Pad>("wait");
  const [helper, setHelper] = useState<boolean | null>(null);
  const [unwell, setUnwell] = useState<boolean | null | "skip">(null);
  const [stoppedEarly, setStoppedEarly] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [, force] = useState(0);

  const sessionId = useRef<number | null>(null);
  const rts = useRef<number[]>([]);
  const early = useRef(0);
  const attempts = useRef(0);
  const interruptions = useRef(0);
  const goAt = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const phaseRef = useRef<Phase>("intro");
  const padRef = useRef<Pad>("wait");
  phaseRef.current = phase;
  padRef.current = pad;

  const clear = () => window.clearTimeout(timer.current);
  useEffect(() => clear, []);

  // Leaving the tab mid-activity is an interruption; it is recorded, not hidden.
  useEffect(() => {
    const onHide = () => {
      if (document.hidden && (phaseRef.current === "practice" || phaseRef.current === "trials")) interruptions.current += 1;
    };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, []);

  const arm = useCallback(() => {
    clear();
    setPad("wait");
    const wait = MIN_WAIT + Math.random() * (MAX_WAIT - MIN_WAIT);
    timer.current = window.setTimeout(() => {
      goAt.current = performance.now();
      setPad("go");
      timer.current = window.setTimeout(() => { setPad("missed"); onMissed(); }, TIMEOUT);
    }, wait);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const finish = useCallback(async (status: "completed" | "interrupted" | "abandoned") => {
    clear();
    setPhase("saving");
    const valid = rts.current;
    const obs: Observation[] = [
      valid.length
        ? { measure: "rt_median_ms", kind: "observed", unit: "ms", value_num: Math.round(median(valid)) }
        : { measure: "rt_median_ms", kind: "observed", unit: "ms",
            missing_reason: status === "abandoned" ? "stopped_by_participant" : "no_valid_trials" },
      { measure: "valid_trials", kind: "observed", unit: "count", value_num: valid.length },
      { measure: "anticipations", kind: "observed", unit: "count", value_num: early.current },
    ];
    try {
      if (sessionId.current !== null) {
        await api.completeSession(sessionId.current, {
          status, interruptions: interruptions.current, observations: obs, client_version: "web-reaction/0.1",
        });
      }
      setPhase("done");
    } catch (e) { setError(e); setPhase("done"); }
  }, []);

  const nextOrFinish = useCallback(() => {
    if (phaseRef.current === "practice") { clear(); setPhase("practiceDone"); return; }
    if (rts.current.length >= TRIALS || attempts.current >= MAX_ATTEMPTS) {
      finish(interruptions.current > 0 ? "interrupted" : "completed");
      return;
    }
    timer.current = window.setTimeout(arm, 900);
    force((n) => n + 1);
  }, [arm, finish]);

  function onMissed() {
    if (phaseRef.current === "trials") attempts.current += 1;
    nextOrFinish();
  }

  const tap = useCallback(() => {
    const p = phaseRef.current;
    if (p !== "practice" && p !== "trials") return;
    const state = padRef.current;
    if (state === "wait") {
      clear();
      setPad("early");
      if (p === "practice") { timer.current = window.setTimeout(arm, 1200); return; }  // practise until it lands
      early.current += 1; attempts.current += 1;
      nextOrFinish();
    } else if (state === "go") {
      clear();
      const rt = performance.now() - goAt.current;
      if (p === "trials") { attempts.current += 1; rts.current.push(rt); }
      setPad("wait");
      nextOrFinish();
    }
  }, [nextOrFinish]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space" && (phaseRef.current === "practice" || phaseRef.current === "trials")) { e.preventDefault(); tap(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tap]);

  const begin = async () => {
    setError(null);
    try {
      const s = await api.startSession({
        protocol_code: "reaction_time", protocol_version: "0.1", language: t.lang, device: "web",
        assisted: helper === true, unwell_today: unwell === "skip" ? null : unwell,
      });
      sessionId.current = s.id;
      setPhase("practice");
      arm();
    } catch (e) { setError(e); }
  };

  const startTrials = () => { setPhase("trials"); arm(); };
  const askStop = () => { clear(); setPhase("stopping"); };
  const resume = (to: Phase) => { setPhase(to); arm(); };
  const resumeTo = useRef<Phase>("trials");

  if (phase === "intro") {
    const yn = (value: boolean | null | "skip", set: (v: boolean | "skip") => void, withSkip: boolean) => (
      <div className="choices" role="radiogroup">
        {([[true, "yes"], [false, "no"], ...(withSkip ? [["skip", "preferNot"]] : [])] as [boolean | "skip", "yes"][]).map(([v, k]) => (
          <button key={String(v)} className="choice" role="radio" aria-checked={value === v} onClick={() => set(v)}>
            <span className="dot" />{t(k)}
          </button>
        ))}
      </div>
    );
    return (
      <>
        <Heading>{t("rtIntroTitle")}</Heading>
        <p>{t("rtIntro1")}</p>
        <p className="muted">{t("rtIntro2")}</p>
        <section className="p-card">
          <h2 style={{ fontSize: 20 }}>{t("rtHelper")}</h2>
          {yn(helper, (v) => setHelper(v === true), false)}
        </section>
        <section className="p-card">
          <h2 style={{ fontSize: 20 }}>{t("rtUnwell")}</h2>
          {yn(unwell, (v) => setUnwell(v), true)}
        </section>
        <ErrorNote error={error} />
        <div className="p-actions">
          <button className="btn primary block" disabled={helper === null} onClick={begin}>{t("rtBegin")}</button>
          <button className="link" onClick={onDone}>{t("back")}</button>
        </div>
      </>
    );
  }

  if (phase === "practiceDone") {
    return (
      <>
        <Heading>{t("rtPracticeDone")}</Heading>
        <div className="p-actions">
          <button className="btn primary block" onClick={startTrials}>{t("rtStartReal")}</button>
          <button className="btn block" onClick={() => { resumeTo.current = "practiceDone"; askStop(); }}>{t("rtStop")}</button>
        </div>
      </>
    );
  }

  if (phase === "stopping") {
    return (
      <div role="alertdialog" aria-labelledby="stop-q" style={{ display: "grid", gap: 16 }}>
        <Heading><span id="stop-q">{t("rtStopConfirm")}</span></Heading>
        <div className="p-actions">
          <button className="btn danger block" onClick={() => { setStoppedEarly(true); finish("abandoned"); }}>{t("rtStopYes")}</button>
          <button className="btn block" onClick={() => (resumeTo.current === "practiceDone" ? setPhase("practiceDone") : resume(resumeTo.current))}>
            {t("rtKeepGoing")}
          </button>
        </div>
      </div>
    );
  }

  if (phase === "saving") return <p className="muted">{t("loading")}</p>;

  if (phase === "done") {
    return (
      <>
        <Heading>{t("rtSaved")}</Heading>
        <p>{stoppedEarly ? t("rtStoppedBody") : t("rtSavedBody")}</p>
        <ErrorNote error={error} />
        <button className="btn primary block" onClick={onDone}>{t("backHome")}</button>
      </>
    );
  }

  // practice or trials
  const label = pad === "go" ? t("rtTap") : pad === "early" ? t("rtEarly") : pad === "missed" ? t("rtMissed") : t("rtWait");
  return (
    <>
      <p className="progress" aria-live="polite">
        {phase === "practice" ? t("rtPractice") : t("rtTrial", { n: t.num(Math.min(rts.current.length + 1, TRIALS)), total: t.num(TRIALS) })}
      </p>
      <div className={`rt-pad ${pad === "go" ? "go" : pad === "early" ? "early" : ""}`}
        role="button" tabIndex={0} aria-live="assertive" onPointerDown={(e) => { e.preventDefault(); tap(); }}>
        {label}
      </div>
      <p className="muted" style={{ fontSize: 16 }}>{t("rtKeyHint")}</p>
      <button className="btn block" onClick={() => { resumeTo.current = phase; askStop(); }}>{t("rtStop")}</button>
    </>
  );
}
