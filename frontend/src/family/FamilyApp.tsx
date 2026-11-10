import { useCallback, useEffect, useState } from "react";
import { api, FamilyEntry, User } from "../api";
import { useT } from "../i18n";
import { Brand, ErrorNote, Heading, LangSwitch, Status } from "../ui";
import Account from "../Account";
import Compose from "./Compose";

/** What a family member sees: only who shares with them and which activities were done. Never answers or results. */
export default function FamilyApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const { t } = useT();
  const [entries, setEntries] = useState<FamilyEntry[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [account, setAccount] = useState(false);

  const load = useCallback(() => { setError(null); api.familyShared().then(setEntries).catch(setError); }, []);
  useEffect(load, [load]);

  return (
    <div className="personal">
      <header className="p-bar">
        <Brand />
        <div className="who">
          <LangSwitch />
          {!user.is_demo && <button className="link" onClick={() => setAccount(!account)} aria-pressed={account}>{t("acTitle")}</button>}
          <button className="link" onClick={onSignOut}>{t("signOut")}</button>
        </div>
      </header>
      <main className="p-main">
        {account ? (
          <>
            <Heading>{t("acTitle")}</Heading>
            <Account user={user} large />
            <button className="btn block" onClick={() => setAccount(false)}>{t("back")}</button>
          </>
        ) : <>
        <Heading>{t("hello", { name: user.display_name })}</Heading>
        <p className="lede">{t("familyLede")}</p>
        <ErrorNote error={error} onRetry={load} />
        {entries === null && !error && <p className="muted">{t("loading")}</p>}
        {entries?.length === 0 && <p className="muted">{t("familyNone")}</p>}
        {entries?.map((e) => (
          <section key={e.participant_id} className="p-card">
            <div>
              <h2>{e.display_name}</h2>
              {e.active && <span className="muted" style={{ fontSize: 16 }}>{t("sharingSince", { date: t.date(e.since) })}</span>}
            </div>
            {!e.active ? (
              <p>{t("familyEnded", { name: e.display_name, date: t.date(e.ended_at) })}</p>
            ) : (
              <>
                <h3 style={{ margin: 0, fontSize: 16, color: "var(--muted)" }}>{t("familyRecent")}</h3>
                {e.recent.length === 0 && <p className="muted">{t("familyNoRecent")}</p>}
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
                  {e.recent.slice(0, 6).map((r, i) => (
                    <li key={i} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, alignItems: "baseline" }}>
                      <span>{t.code(r.protocol_code)} <span className="muted">· {t.date(r.at)}</span></span>
                      <Status level={r.status === "completed" ? "ok" : "quiet"}>{t(`sessionStatus_${r.status}` as "sessionStatus_completed")}</Status>
                    </li>
                  ))}
                </ul>
                <p className="muted" style={{ fontSize: 16 }}>{t("familyWhat")} {t("familyNoResponse")}</p>
                <Compose pid={e.participant_id} name={e.display_name} />
              </>
            )}
          </section>
        ))}
        </>}
      </main>
      <footer className="p-foot"><span>{t("prototypeLong")}</span></footer>
    </div>
  );
}
