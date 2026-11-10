import { useState } from "react";
import { api, Observation } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

const FACTORS = [["tired", "fTired"], ["unwell", "fUnwell"], ["pain", "fPain"], ["worried", "fWorried"]] as const;

/** Three questions, one per screen. Every question can be skipped; a skip is stored as "skipped", never as a value. */
export default function Checkin({ onDone }: { onDone: () => void }) {
  const { t } = useT();
  const [step, setStep] = useState(0);
  const [hours, setHours] = useState<number | null>(7);
  const [quality, setQuality] = useState<number | null>(null);
  // undefined = not answered yet, null = skipped, [] = "none of these"
  const [factors, setFactors] = useState<string[] | null | undefined>(undefined);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setBusy(true); setError(null);
    const obs: Observation[] = [
      hours === null
        ? { measure: "sleep_hours", kind: "self_reported", unit: "h", missing_reason: "skipped_by_participant" }
        : { measure: "sleep_hours", kind: "self_reported", unit: "h", value_num: hours },
      quality === null
        ? { measure: "sleep_quality", kind: "self_reported", unit: "1-5", missing_reason: "skipped_by_participant" }
        : { measure: "sleep_quality", kind: "self_reported", unit: "1-5", value_num: quality },
      !factors || factors.length === 0
        ? (factors ? { measure: "today_factors", kind: "self_reported", value_text: "none" }
                   : { measure: "today_factors", kind: "self_reported", missing_reason: "skipped_by_participant" })
        : { measure: "today_factors", kind: "self_reported", value_text: factors.join(",") },
    ];
    try {
      const s = await api.startSession({ protocol_code: "daily_checkin", protocol_version: "0.1", language: t.lang, device: "web",
        unwell_today: factors ? factors.includes("unwell") : null });
      await api.completeSession(s.id, { status: "completed", interruptions: 0, observations: obs, client_version: "web/0.1" });
      setSaved(true);
    } catch (e) { setError(e); }
    setBusy(false);
  };

  if (saved) {
    return (
      <>
        <Heading>{t("savedTitle")}</Heading>
        <p>{t("savedCheckin")}</p>
        <button className="btn primary block" onClick={onDone}>{t("backHome")}</button>
      </>
    );
  }

  // Continue needs an answer; not answering is its own explicit button, never a silent default.
  const nav = (onSkip: () => void, answered: boolean) => (
    <div className="p-actions">
      <button className="btn primary block" disabled={!answered} onClick={() => setStep(step + 1)}>{t("continue")}</button>
      <button className="btn block" onClick={() => { onSkip(); setStep(step + 1); }}>{t("skip")}</button>
      <button className="link" onClick={() => (step === 0 ? onDone() : setStep(step - 1))}>{t("back")}</button>
    </div>
  );

  return (
    <>
      <p className="progress">{t("questionOf", { n: t.num(step + 1), total: t.num(3) })}</p>
      {step === 0 && (
        <>
          <Heading>{t("qSleepHours")}</Heading>
          <div className="stepper" role="group" aria-label={t("qSleepHours")}>
            <button className="btn" aria-label="−" onClick={() => setHours(Math.max(0, (hours ?? 7) - 0.5))}>−</button>
            <div className="val" aria-live="polite">{hours === null ? "–" : t.num(hours, 1)} <span className="muted" style={{ fontSize: 18 }}>{t("hours")}</span></div>
            <button className="btn" aria-label="+" onClick={() => setHours(Math.min(16, (hours ?? 7) + 0.5))}>+</button>
          </div>
          {nav(() => setHours(null), hours !== null)}
        </>
      )}
      {step === 1 && (
        <>
          <Heading>{t("qSleepQuality")}</Heading>
          <div className="choices" role="radiogroup" aria-label={t("qSleepQuality")}>
            {([5, 4, 3, 2, 1] as const).map((v) => (
              <button key={v} className="choice" role="radio" aria-checked={quality === v} onClick={() => setQuality(v)}>
                <span className="dot" />{t(`sq${v}` as "sq1")}
              </button>
            ))}
          </div>
          {nav(() => setQuality(null), quality !== null)}
        </>
      )}
      {step === 2 && (
        <>
          <Heading>{t("qToday")}</Heading>
          <p className="muted">{t("qTodayHint")}</p>
          <div className="choices">
            {FACTORS.map(([code, key]) => {
              const on = factors?.includes(code) ?? false;
              return (
                <button key={code} className="choice" aria-pressed={on}
                  onClick={() => { const next = on ? (factors ?? []).filter((f) => f !== code) : [...(factors ?? []), code]; setFactors(next.length ? next : undefined); }}>
                  <span className="dot" />{t(key)}
                </button>
              );
            })}
            <button className="choice" aria-pressed={Array.isArray(factors) && factors.length === 0} onClick={() => setFactors([])}>
              <span className="dot" />{t("fNone")}
            </button>
          </div>
          <ErrorNote error={error} />
          <div className="p-actions">
            <button className="btn primary block" disabled={busy || factors === undefined} onClick={submit}>{t("save")}</button>
            <button className="btn block" disabled={busy} onClick={() => { setFactors(null); setStep(3); }}>{t("skip")}</button>
            <button className="link" onClick={() => setStep(1)}>{t("back")}</button>
          </div>
        </>
      )}
      {step === 3 && (
        <>
          <Heading>{t("qToday")}</Heading>
          <p className="muted">{t("skip")}</p>
          <ErrorNote error={error} />
          <div className="p-actions">
            <button className="btn primary block" disabled={busy} onClick={submit}>{t("save")}</button>
            <button className="link" onClick={() => { setFactors(undefined); setStep(2); }}>{t("back")}</button>
          </div>
        </>
      )}
    </>
  );
}
