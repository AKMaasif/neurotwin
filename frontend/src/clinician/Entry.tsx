import { useEffect, useRef } from "react";
import { Check, Circle, Loader2, TriangleAlert } from "lucide-react";
import { useT } from "../i18n";

const STAGES = ["ldOpen", "ldRecords", "ldHistory", "ldViews"] as const;

/** The first load of the workspace, shown as the real steps it takes: the session is known, the caseload is fetched, one person's records
 *  are fetched, the views are rendered. Nothing here waits for show. If a step fails it says which one and offers a retry. */
export function WorkspaceLoader({ stage, failed, onRetry, onSignOut }: { stage: 1 | 2 | 3 | 4; failed: boolean; onRetry: () => void; onSignOut: () => void }) {
  const { t } = useT();
  // stage 1 = fetching the caseload, 2 = fetching the person's records, 3 = rendering, 4 = ready. "Opening your workspace" is already done.
  const current = stage; // index into STAGES of the step in progress (0 is done)
  return (
    <section className="entry" aria-labelledby="ld-h">
      <h1 id="ld-h">{failed ? t("ldFailedTitle") : t("ldTitle")}</h1>
      <ol className="entry-steps" role="status" aria-live="polite">
        {STAGES.map((k, i) => {
          const done = i < current || (i === 0);
          const active = i === current && !failed;
          const bad = i === current && failed;
          return (
            <li key={k} className={done ? "done" : active ? "active" : bad ? "bad" : ""}>
              {done ? <Check size={18} aria-hidden="true" /> : bad ? <TriangleAlert size={18} aria-hidden="true" /> : active ? <Loader2 size={18} aria-hidden="true" className="spin" /> : <Circle size={18} aria-hidden="true" />}
              <span>{t(k)}{bad ? ` — ${t("ldDidNotFinish")}` : ""}</span>
            </li>
          );
        })}
      </ol>
      {failed && (
        <div className="entry-actions">
          <button className="btn primary" onClick={onRetry}>{t("tryAgain")}</button>
          <button className="btn" onClick={onSignOut}>{t("signOut")}</button>
        </div>
      )}
    </section>
  );
}

/** A short notice before the restricted research workspace. It introduces the space; the server still decides who may see anything. */
export function BrainGate({ onEnter, onBack }: { onEnter: () => void; onBack: () => void }) {
  const { t } = useT();
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  return (
    <section className="entry" aria-labelledby="bg-h">
      <h1 id="bg-h" ref={ref} tabIndex={-1}>{t("shPageBrain")}</h1>
      <p className="entry-notice">{t("bgNotice")}</p>
      <div className="entry-actions">
        <button className="btn primary" onClick={onEnter}>{t("bgEnter")}</button>
        <button className="btn" onClick={onBack}>{t("back")}</button>
      </div>
    </section>
  );
}
