import { useState } from "react";
import { ArrowLeft, Annoyed, BatteryLow, Check, CircleCheck, CloudRain, Frown, HeartPulse, Laugh, Meh, Minus, Moon, Plus, Smile, Thermometer } from "lucide-react";
import { api, Observation } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

const FACTORS = [["tired", "fTired"], ["unwell", "fUnwell"], ["pain", "fPain"], ["worried", "fWorried"]] as const;
const FACTOR_ICON = { tired: BatteryLow, unwell: Thermometer, pain: HeartPulse, worried: CloudRain } as const;
const FACE = { 5: Laugh, 4: Smile, 3: Meh, 2: Frown, 1: Annoyed } as const;

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
      <div className="pt-done">
        <span className="badge"><Check size={48} strokeWidth={3} aria-hidden="true" /></span>
        <Heading>{t("savedTitle")}</Heading>
        <p>{t("savedCheckin")}</p>
        <button className="btn primary block" onClick={onDone}>{t("backHome")}</button>
      </div>
    );
  }

  const goBack = () => {
    if (step === 0) onDone();
    else if (step === 3) { setFactors(undefined); setStep(2); }
    else setStep(step - 1);
  };
  const shown = Math.min(step, 2);
  const stepText = t("questionOf", { n: t.num(shown + 1), total: t.num(3) });
  const head = (
    <div className="pt-qhead">
      <button type="button" className="pt-qback" aria-label={t("back")} onClick={goBack}><ArrowLeft size={22} className="flip" aria-hidden="true" /></button>
      <div className="pt-seg" role="img" aria-label={stepText}>{[0, 1, 2].map((i) => <i key={i} className={i <= shown ? "on" : ""} />)}</div>
      <span className="pt-qn" aria-hidden="true">{t("ptStepOf", { n: t.num(shown + 1), total: t.num(3) })}</span>
    </div>
  );

  // Continue needs an answer; not answering is its own explicit button, never a silent default.
  const nav = (onSkip: () => void, answered: boolean) => (
    <div className="p-actions">
      <button className="btn primary block" disabled={!answered} onClick={() => setStep(step + 1)}>{t("continue")}</button>
      <button className="btn block" onClick={() => { onSkip(); setStep(step + 1); }}>{t("skip")}</button>
    </div>
  );

  return (
    <>
      {head}
      {step === 0 && (
        <>
          <span className="pt-qtag">{t("ptTagSleep")}</span>
          <Heading>{t("qSleepHours")}</Heading>
          <div className="pt-hours" role="group" aria-label={t("qSleepHours")}>
            <span className="moon"><Moon size={44} aria-hidden="true" /></span>
            <div className="row">
              <button type="button" className="pt-round" aria-label="−" onClick={() => setHours(Math.max(0, (hours ?? 7) - 0.5))}><Minus size={30} aria-hidden="true" /></button>
              <div className="val" aria-live="polite">{hours === null ? "–" : t.num(hours, 1)}<small>{t("hours")}</small></div>
              <button type="button" className="pt-round" aria-label="+" onClick={() => setHours(Math.min(16, (hours ?? 7) + 0.5))}><Plus size={30} aria-hidden="true" /></button>
            </div>
          </div>
          {nav(() => setHours(null), hours !== null)}
        </>
      )}
      {step === 1 && (
        <>
          <span className="pt-qtag">{t("ptTagSleep")}</span>
          <Heading>{t("qSleepQuality")}</Heading>
          <div className="pt-cards five" role="radiogroup" aria-label={t("qSleepQuality")}>
            {([5, 4, 3, 2, 1] as const).map((v) => {
              const Face = FACE[v];
              return (
                <button key={v} type="button" className={`pt-pick t${v}`} role="radio" aria-checked={quality === v} onClick={() => setQuality(v)}>
                  <span className="tick"><Check size={15} strokeWidth={3.5} aria-hidden="true" /></span>
                  <span className="face"><Face size={34} aria-hidden="true" /></span>
                  {t(`sq${v}` as "sq1")}
                </button>
              );
            })}
          </div>
          {nav(() => setQuality(null), quality !== null)}
        </>
      )}
      {step === 2 && (
        <>
          <span className="pt-qtag">{t("ptTagToday")}</span>
          <Heading>{t("qToday")}</Heading>
          <p className="muted">{t("qTodayHint")}</p>
          <div className="pt-cards">
            {FACTORS.map(([code, key]) => {
              const on = factors?.includes(code) ?? false;
              const Icon = FACTOR_ICON[code];
              return (
                <button key={code} type="button" className="pt-pick f" aria-pressed={on}
                  onClick={() => { const next = on ? (factors ?? []).filter((f) => f !== code) : [...(factors ?? []), code]; setFactors(next.length ? next : undefined); }}>
                  <span className="tick"><Check size={15} strokeWidth={3.5} aria-hidden="true" /></span>
                  <span className="face"><Icon size={32} aria-hidden="true" /></span>
                  {t(key)}
                </button>
              );
            })}
            <button type="button" className="pt-pick none" aria-pressed={Array.isArray(factors) && factors.length === 0} onClick={() => setFactors([])}>
              <span className="tick"><Check size={15} strokeWidth={3.5} aria-hidden="true" /></span>
              <span className="face"><CircleCheck size={30} aria-hidden="true" /></span>
              {t("fNone")}
            </button>
          </div>
          <ErrorNote error={error} />
          <div className="p-actions">
            <button className="btn primary block" disabled={busy || factors === undefined} onClick={submit}>{t("save")}</button>
            <button className="btn block" disabled={busy} onClick={() => { setFactors(null); setStep(3); }}>{t("skip")}</button>
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
          </div>
        </>
      )}
    </>
  );
}
