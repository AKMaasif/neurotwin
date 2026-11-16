import { Ear, Eye, Moon, Thermometer, VolumeX } from "lucide-react";
import type { Conditions } from "../api";
import { useT } from "../i18n";

export type TodayAnswers = Conditions & { unwell_today: boolean | null };
export const NO_ANSWERS: TodayAnswers = { see_clearly: null, hear_clearly: null, slept_well: null, quiet_place: null, unwell_today: null };

const ROWS = [
  ["see_clearly", "condSee", Eye],
  ["hear_clearly", "condHear", Ear],
  ["slept_well", "condSleep", Moon],
  ["quiet_place", "condQuiet", VolumeX],
  ["unwell_today", "rtUnwell", Thermometer],
] as const;

/** Today's conditions, asked before an activity: things that change how a result reads (vision, hearing, sleep, a quiet
 * place, feeling unwell). Every question is optional; tapping the chosen answer again clears it, and an unanswered
 * question is stored as "not asked", never as a guess. The answers label the result for the clinician and never change it. */
export default function TodayConditions({ value, onChange }: { value: TodayAnswers; onChange: (update: (prev: TodayAnswers) => TodayAnswers) => void }) {
  const { t } = useT();
  return (
    <section className="p-card cond" aria-labelledby="cond-h">
      <h2 id="cond-h" style={{ fontSize: 20 }}>{t("condTitle")}</h2>
      <p className="muted" style={{ marginTop: 0 }}>{t("condHint")}</p>
      {ROWS.map(([key, label, Icon]) => (
        <div key={key} className="cond-row" role="radiogroup" aria-label={t(label)}>
          <span className="cond-q"><Icon size={26} aria-hidden="true" />{t(label)}</span>
          <span className="cond-a">
            {([[true, "yes"], [false, "no"]] as const).map(([v, k]) => (
              <button key={k} type="button" className="choice" role="radio" aria-checked={value[key] === v}
                onClick={() => onChange((p) => ({ ...p, [key]: p[key] === v ? null : v }))}>
                <span className="dot" />{t(k)}
              </button>
            ))}
          </span>
        </div>
      ))}
    </section>
  );
}
