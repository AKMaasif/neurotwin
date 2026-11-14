import { useState } from "react";
import { Check } from "lucide-react";
import { api, Observation } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

/** WHO-5 Well-Being Index (WHO, 1998). Wording, response options and 0-5 scoring are exactly as published and are not edited.
 *  Shown in English only: an Arabic version is added only when the owner supplies the official text (no machine translation).
 *  The activity adds no cut-off, no label such as "low" or "changed", and shows the person no score. */
const ITEMS = [
  "I have felt cheerful and in good spirits",
  "I have felt calm and relaxed",
  "I have felt active and vigorous",
  "I woke up feeling fresh and rested",
  "My daily life has been filled with things that interest me",
] as const;
const OPTIONS = [[5, "All of the time"], [4, "Most of the time"], [3, "More than half of the time"], [2, "Less than half of the time"], [1, "Some of the time"], [0, "At no time"]] as const;

export default function Who5({ onDone }: { onDone: () => void }) {
  const { t } = useT();
  const [step, setStep] = useState(-1);                                  // -1 = introduction
  const [answers, setAnswers] = useState<(number | null | undefined)[]>([undefined, undefined, undefined, undefined, undefined]);  // null = skipped
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const set = (i: number, v: number | null) => setAnswers((a) => a.map((x, j) => (j === i ? v : x)));
  const complete = answers.every((a) => typeof a === "number");

  const submit = async () => {
    setBusy(true); setError(null);
    const obs: Observation[] = answers.map((a, i) => typeof a === "number"
      ? { measure: `who5_${i + 1}`, kind: "self_reported", unit: "0-5", value_num: a }
      : { measure: `who5_${i + 1}`, kind: "self_reported", unit: "0-5", missing_reason: "skipped_by_participant" });
    // The published raw score is the plain sum of five answers. With any answer missing there is no total, and none is estimated.
    obs.push(complete
      ? { measure: "who5_raw", kind: "self_reported", unit: "0-25", value_num: (answers as number[]).reduce((x, y) => x + y, 0) }
      : { measure: "who5_raw", kind: "self_reported", unit: "0-25", missing_reason: "incomplete_items" });
    try {
      const s = await api.startSession({ protocol_code: "who5", protocol_version: "1998-en", language: t.lang, device: "web" });
      await api.completeSession(s.id, { status: "completed", interruptions: 0, observations: obs, client_version: "web-who5/1998-en" });
      setSaved(true);
    } catch (e) { setError(e); }
    setBusy(false);
  };

  if (saved) {
    return (
      <div className="pt-done">
        <span className="badge"><Check size={48} strokeWidth={3} aria-hidden="true" /></span>
        <Heading>{t("memSaved")}</Heading>
        <p>{t("w5SavedBody")}</p>
        {!complete && <p className="muted">{t("w5Partial")}</p>}
        <button className="btn primary block" onClick={onDone}>{t("backHome")}</button>
      </div>
    );
  }

  if (step < 0) {
    return (
      <>
        <Heading>{t("w5Title")}</Heading>
        <p>{t("w5Intro")}</p>
        <p className="muted">{t("w5Lang")}</p>
        <div className="p-actions">
          <button className="btn primary block" onClick={() => setStep(0)}>{t("memBegin")}</button>
          <button className="link" onClick={onDone}>{t("back")}</button>
        </div>
      </>
    );
  }

  const last = step === ITEMS.length - 1;
  const cur = answers[step];
  return (
    <>
      <p className="progress" aria-live="polite">{t("w5Q", { n: t.num(step + 1) })}</p>
      <p className="muted">{t("w5Stem")}</p>
      <h1 lang="en" dir="ltr" style={{ textAlign: "start" }}>{ITEMS[step]}</h1>
      <div className="choices" role="radiogroup" aria-label={ITEMS[step]} lang="en" dir="ltr">
        {OPTIONS.map(([v, label]) => (
          <button key={v} className="choice" role="radio" aria-checked={cur === v} onClick={() => set(step, v)}>
            <span className="dot" />{label}
          </button>
        ))}
      </div>
      <ErrorNote error={error} />
      <div className="p-actions">
        {!last
          ? <button className="btn primary block" disabled={cur === undefined} onClick={() => setStep(step + 1)}>{t("w5Next")}</button>
          : <button className="btn primary block" disabled={busy || cur === undefined} onClick={submit}>{t("w5Save")}</button>}
        <button className="btn block" onClick={() => { set(step, null); if (!last) setStep(step + 1); }}>{t("w5Skip")}</button>
        {step > 0 && <button className="link" onClick={() => setStep(step - 1)}>{t("back")}</button>}
      </div>
    </>
  );
}
