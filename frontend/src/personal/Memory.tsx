import { useCallback, useEffect, useRef, useState } from "react";
import { Cloud, Heart, Leaf, Moon, Star, Sun } from "lucide-react";
import { api, Observation } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

// Prototype picture-sequence memory activity, version 0.1. Engineering settings, not clinical ones. No timing is scored.
const PICS = [["sun", Sun, "memSun"], ["moon", Moon, "memMoon"], ["star", Star, "memStar"], ["heart", Heart, "memHeart"], ["leaf", Leaf, "memLeaf"], ["cloud", Cloud, "memCloud"]] as const;
const ROUNDS = [3, 3, 4, 4];     // saved rounds: sequence lengths
const PRACTICE = 2;
const SHOW_MS = 1400;            // each picture
const GAP_MS = 400;

type Phase = "intro" | "show" | "answer" | "practiceDone" | "stopping" | "saving" | "done";

/** A fresh sequence of distinct pictures. */
function sequence(n: number): number[] {
  const idx = [0, 1, 2, 3, 4, 5];
  for (let i = idx.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [idx[i], idx[j]] = [idx[j], idx[i]]; }
  return idx.slice(0, n);
}

export default function Memory({ onDone }: { onDone: () => void }) {
  const { t } = useT();
  const [phase, setPhase] = useState<Phase>("intro");
  const [helper, setHelper] = useState<boolean | null>(null);
  const [round, setRound] = useState(-1);                       // -1 = practice, then 0..ROUNDS.length-1
  const [seq, setSeq] = useState<number[]>([]);
  const [shownIdx, setShownIdx] = useState(-1);
  const [picked, setPicked] = useState<number[]>([]);
  const [stoppedEarly, setStoppedEarly] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const sessionId = useRef<number | null>(null);
  const correct = useRef(0);
  const shown = useRef(0);
  const longest = useRef(0);
  const interruptions = useRef(0);
  const timers = useRef<number[]>([]);
  const phaseRef = useRef<Phase>("intro");
  const resumeTo = useRef<Phase>("answer");
  phaseRef.current = phase;

  const clear = () => { timers.current.forEach((x) => window.clearTimeout(x)); timers.current = []; };
  useEffect(() => clear, []);
  useEffect(() => {
    const onHide = () => { if (document.hidden && (phaseRef.current === "show" || phaseRef.current === "answer")) interruptions.current += 1; };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, []);

  const finish = useCallback(async (status: "completed" | "interrupted" | "abandoned") => {
    clear(); setPhase("saving");
    const obs: Observation[] = [
      { measure: "rounds_correct", kind: "observed", unit: "count", value_num: correct.current },
      { measure: "rounds_shown", kind: "observed", unit: "count", value_num: shown.current },
      { measure: "longest_correct", kind: "observed", unit: "count", value_num: longest.current },
    ];
    try {
      if (sessionId.current !== null) {
        await api.completeSession(sessionId.current, { status, interruptions: interruptions.current, observations: obs, client_version: "web-memory/0.1" });
      }
    } catch (e) { setError(e); }
    setPhase("done");
  }, []);

  const startRound = useCallback((r: number) => {
    clear();
    const s = sequence(r < 0 ? PRACTICE : ROUNDS[r]);
    setRound(r); setSeq(s); setPicked([]); setShownIdx(-1); setPhase("show");
    s.forEach((_, i) => {
      timers.current.push(window.setTimeout(() => setShownIdx(i), 600 + i * (SHOW_MS + GAP_MS)));
      timers.current.push(window.setTimeout(() => setShownIdx(-1), 600 + i * (SHOW_MS + GAP_MS) + SHOW_MS));
    });
    timers.current.push(window.setTimeout(() => setPhase("answer"), 600 + s.length * (SHOW_MS + GAP_MS)));
  }, []);

  const begin = async () => {
    setError(null);
    try {
      const s = await api.startSession({ protocol_code: "picture_sequence", protocol_version: "0.1", language: t.lang, device: "web", assisted: helper === true });
      sessionId.current = s.id;
      startRound(-1);
    } catch (e) { setError(e); }
  };

  const pick = (i: number) => {
    if (phaseRef.current !== "answer" || picked.includes(i)) return;
    const next = [...picked, i];
    setPicked(next);
    if (next.length < seq.length) return;
    const ok = next.every((p, k) => p === seq[k]);
    if (round >= 0) {
      shown.current += 1;
      if (ok) { correct.current += 1; longest.current = Math.max(longest.current, seq.length); }
    }
    if (round < 0) { setPhase("practiceDone"); return; }
    if (round + 1 >= ROUNDS.length) { finish(interruptions.current > 0 ? "interrupted" : "completed"); return; }
    timers.current.push(window.setTimeout(() => startRound(round + 1), 900));
  };

  const askStop = (from: Phase) => { clear(); resumeTo.current = from; setPhase("stopping"); };

  if (phase === "intro") {
    return (
      <>
        <Heading>{t("memTitle")}</Heading>
        <p>{t("memIntro1")}</p>
        <p className="muted">{t("memIntro2")}</p>
        <section className="p-card">
          <h2 style={{ fontSize: 20 }}>{t("rtHelper")}</h2>
          <div className="choices" role="radiogroup">
            {([[true, "yes"], [false, "no"]] as const).map(([v, k]) => (
              <button key={k} className="choice" role="radio" aria-checked={helper === v} onClick={() => setHelper(v)}><span className="dot" />{t(k)}</button>
            ))}
          </div>
        </section>
        <ErrorNote error={error} />
        <div className="p-actions">
          <button className="btn primary block" disabled={helper === null} onClick={begin}>{t("memBegin")}</button>
          <button className="link" onClick={onDone}>{t("back")}</button>
        </div>
      </>
    );
  }
  if (phase === "practiceDone") {
    return (
      <>
        <Heading>{t("memPracticeDone")}</Heading>
        <div className="p-actions">
          <button className="btn primary block" onClick={() => startRound(0)}>{t("memStartReal")}</button>
          <button className="btn block" onClick={() => askStop("practiceDone")}>{t("memStop")}</button>
        </div>
      </>
    );
  }
  if (phase === "stopping") {
    return (
      <div role="alertdialog" aria-labelledby="mem-stop-q" style={{ display: "grid", gap: 16 }}>
        <Heading><span id="mem-stop-q">{t("memStopConfirm")}</span></Heading>
        <div className="p-actions">
          <button className="btn danger block" onClick={() => { setStoppedEarly(true); finish("abandoned"); }}>{t("memStopYes")}</button>
          <button className="btn block" onClick={() => (resumeTo.current === "practiceDone" ? setPhase("practiceDone") : startRound(round))}>{t("memKeepGoing")}</button>
        </div>
      </div>
    );
  }
  if (phase === "saving") return <p className="muted">{t("loading")}</p>;
  if (phase === "done") {
    return (
      <>
        <Heading>{t("memSaved")}</Heading>
        <p>{stoppedEarly ? t("memStoppedBody") : t("memSavedBody")}</p>
        <ErrorNote error={error} />
        <button className="btn primary block" onClick={onDone}>{t("backHome")}</button>
      </>
    );
  }

  // show or answer
  const showing = phase === "show";
  const Cur = shownIdx >= 0 ? PICS[seq[shownIdx]] : null;
  return (
    <>
      <p className="progress" aria-live="polite">{round < 0 ? t("memPractice") : t("memRound", { n: t.num(round + 1), total: t.num(ROUNDS.length) })}</p>
      <h1 aria-live="polite">{showing ? t("memWatch") : t("memYourTurn")}</h1>
      {showing ? (
        <div className="mem-stage" aria-live="assertive">
          {Cur && (() => { const [, Icon, name] = Cur; return <><Icon size={120} aria-hidden="true" /><span className="mem-name">{t(name)}</span></>; })()}
        </div>
      ) : (
        <div className="mem-grid" role="group" aria-label={t("memYourTurn")}>
          {PICS.map(([id, Icon, name], i) => {
            const at = picked.indexOf(i);
            return (
              <button key={id} className="mem-pic" disabled={at >= 0} onClick={() => pick(i)} aria-label={t(name)}>
                <Icon size={56} aria-hidden="true" /><span>{t(name)}</span>
                {at >= 0 && <b className="mem-n">{t.num(at + 1)}</b>}
              </button>
            );
          })}
        </div>
      )}
      <div className="p-actions">
        {!showing && picked.length > 0 && <button className="btn block" onClick={() => setPicked([])}>{t("memUndo")}</button>}
        <button className="btn block" onClick={() => askStop(phase)}>{t("memStop")}</button>
      </div>
    </>
  );
}
