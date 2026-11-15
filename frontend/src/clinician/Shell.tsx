import { ReactNode, useEffect, useState } from "react";
import { ArrowLeft, LogOut } from "lucide-react";
import { api, SystemStatus, User } from "../api";
import { useT } from "../i18n";
import { Brand, LangSwitch } from "../ui";

/** The one clinician frame: header (brand, where you are, language, account, sign out) and a narrow footer with honest status.
 *  Pages inside it keep their own page-level controls but not their own brand, language or sign-out. */
export default function Shell({ user, page, onBack, onDetails, onSignOut, children }: {
  user: User; page: "workspace" | "brain"; onBack?: () => void; onDetails: () => void; onSignOut: () => void; children: ReactNode;
}) {
  const { t } = useT();
  return (
    <div className="shell" data-page={page}>
      <header className="shell-bar">
        <Brand size="sm" page={page === "brain" ? t("shPageBrain") : t("shPageWorkspace")} />
        <div className="shell-end">
          {page === "brain" && onBack && <button className="btn" onClick={onBack}><ArrowLeft size={16} aria-hidden="true" className="flip" />{t("shBack")}</button>}
          <LangSwitch />
          <span className="shell-who" title={user.display_name}><bdi>{user.display_name}</bdi> · {t("roleClinician")}</span>
          <button className="btn" onClick={onSignOut}><LogOut size={16} aria-hidden="true" className="flip" />{t("signOut")}</button>
        </div>
      </header>
      <div className="shell-body">{children}</div>
      <StatusFooter onDetails={onDetails} />
    </div>
  );
}

/** Availability is not execution. "Configured" means a key and model id are set; nothing here has contacted a provider, so none is called
 *  "available" or "live". "Running" appears only while an analysis run is actually executing on the server. */
function StatusFooter({ onDetails }: { onDetails: () => void }) {
  const { t } = useT();
  const [s, setS] = useState<SystemStatus | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    const load = () => api.systemStatus().then((x) => { if (live) { setS(x); setFailed(false); } }).catch(() => { if (live) setFailed(true); });
    load();
    const id = window.setInterval(load, 30000);        // reads server state only; makes no provider call
    window.addEventListener("focus", load);
    return () => { live = false; window.clearInterval(id); window.removeEventListener("focus", load); };
  }, []);
  const name: Record<string, string> = { gemini: "Gemini", meta: "Meta" };
  return (
    <footer className="shell-foot" aria-label={t("shFootLabel")}>
      {failed && !s ? <span>{t("shStatusFailed")}</span> : !s ? <span>{t("loading")}</span> : (
        <>
          <span>{t("shAiMode")}: <b>{t(`shMode_${s.mode}` as "shMode_off")}</b></span>
          {Object.entries(s.providers).map(([k, v]) => (
            <span key={k}>{name[k] ?? k}: <b>{t(v.state === "checked_ok" ? "shCheckedOk" : v.state === "check_failed" ? "shCheckFailed" : v.state === "configured" ? "shConfigured" : "shNotConfigured")}</b></span>
          ))}
          <span aria-live="polite">{t("shAnalysis")}: <b>{t(s.analysis.state === "running" ? "shRunning" : "shIdle")}</b></span>
          {!s.checked && <span className="muted">{t("shNotChecked")}</span>}
        </>
      )}
      <button className="link" onClick={onDetails}>{t("shDetails")}</button>
    </footer>
  );
}
