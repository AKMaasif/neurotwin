import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, User } from "./api";
import { useT } from "./i18n";
import { FormError } from "./ui";

/** Change password, and sign out other devices. Used in all three views; `large` gives the personal-app sizing. */
export default function Account({ user, large = false }: { user: User; large?: boolean }) {
  const { t } = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [others, setOthers] = useState<{ other_active_sessions: number; current_expires_at: string } | null>(null);

  const loadOthers = useCallback(() => { api.otherSessions().then(setOthers).catch(setError); }, []);
  useEffect(loadOthers, [loadOthers]);

  const local = next.length > 0 && next.length < 15 ? t("acTooShort") : again && next !== again ? t("acMismatch") : null;

  const change = async (e: FormEvent) => {
    e.preventDefault();
    if (local) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const r = await api.changePassword(current, next);
      setCurrent(""); setNext(""); setAgain("");
      setNotice(r.other_sessions_ended ? t("acChanged", { n: t.num(r.other_sessions_ended) }) : t("acChangedOnly"));
      loadOthers();
    } catch (err) { setError(err); }
    setBusy(false);
  };

  const signOutOthers = async () => {
    setBusy(true); setError(null); setNotice(null);
    try { const r = await api.revokeOtherSessions(); setNotice(t("acSignedOutOthers", { n: t.num(r.ended) })); loadOthers(); }
    catch (err) { setError(err); }
    setBusy(false);
  };

  return (
    <div className={`account ${large ? "large" : ""}`}>
      {user.username && <p className="muted" style={{ margin: 0 }}>{t("acSignedInAs", { username: user.username })}</p>}
      {notice && <div className="notice" role="status">{notice}</div>}
      <FormError error={error} />

      <form className="signin-form" onSubmit={change}>
        <h2>{t("acChangeTitle")}</h2>
        <label><span>{t("acCurrent")}</span>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" dir="ltr" /></label>
        <label><span>{t("acNew")}</span>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" dir="ltr" aria-describedby="pw-rule" /></label>
        <label><span>{t("acConfirm")}</span>
          <input type="password" value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" dir="ltr" /></label>
        <p id="pw-rule" className="muted" style={{ margin: 0 }}>{local ?? t("acRule")}</p>
        <button className="btn primary" type="submit" disabled={busy || !current || next.length < 15 || next !== again}>{t("acChange")}</button>
      </form>

      <section style={{ display: "grid", gap: 10 }}>
        <h2>{t("acDevicesTitle")}</h2>
        {others && (
          <>
            <p style={{ margin: 0 }}>{others.other_active_sessions ? t("acDevices", { n: t.num(others.other_active_sessions) }) : t("acNoDevices")}</p>
            <p className="muted" style={{ margin: 0 }}>{t("acSessionEnds", { date: t.date(others.current_expires_at, true) })}</p>
            {others.other_active_sessions > 0 && (
              <div><button className="btn" disabled={busy} onClick={signOutOthers}>{t("acSignOutOthers")}</button></div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
