import { useCallback, useEffect, useState } from "react";
import { LogOut, PenLine, UserRound, Users } from "lucide-react";
import { api, FamilyEntry, User } from "../api";
import { useT } from "../i18n";
import { Brand, ErrorNote, LangSwitch, Status } from "../ui";
import Account from "../Account";
import Compose from "./Compose";
import "./family.css";

type View = "people" | "write" | "account";

/** What a family member sees: only who shares with them and which activities were done. Never answers or results. */
export default function FamilyApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const { t } = useT();
  const [entries, setEntries] = useState<FamilyEntry[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [view, setView] = useState<View>("people");
  const [who, setWho] = useState<string | null>(null);

  const load = useCallback(() => { setError(null); api.familyShared().then(setEntries).catch(setError); }, []);
  useEffect(load, [load]);

  const active = (entries ?? []).filter((e) => e.active);
  const target = active.find((e) => e.participant_id === who) ?? active[0];
  const initial = (n: string) => [...n.trim()][0] ?? "?";

  const nav: [View, string, typeof Users][] = [["people", t("famNavPeople"), Users], ["write", t("famNavWrite"), PenLine]];
  if (!user.is_demo) nav.push(["account", t("acTitle"), UserRound]);

  return (
    <div className="fam">
      <aside className="fam-side">
        <Brand />
        <nav aria-label={t("famMenu")}>
          {nav.map(([v, label, Icon]) => (
            <button key={v} className="fam-nav" aria-current={view === v ? "page" : undefined} onClick={() => setView(v)}>
              <Icon size={20} aria-hidden="true" />{label}
            </button>
          ))}
        </nav>
        <div className="fam-side-foot">
          <LangSwitch />
          <button className="fam-nav" onClick={onSignOut}><LogOut size={20} className="flip" aria-hidden="true" />{t("signOut")}</button>
        </div>
      </aside>

      <main className="fam-main">
        <header className="fam-head">
          <p className="fam-eyebrow">{t("roleFamily")}</p>
          <h1>{t("hello", { name: user.display_name })}</h1>
          <p className="fam-lede">{t("familyLede")}</p>
        </header>
        <ErrorNote error={error} onRetry={load} />
        {entries === null && !error && <p className="fam-muted">{t("loading")}</p>}

        {view === "people" && (
          <>
            {entries?.length === 0 && <p className="fam-card fam-muted">{t("familyNone")}</p>}
            <div className="fam-grid">
              {entries?.map((e) => {
                const done = e.recent.filter((r) => r.status === "completed").length;
                return (
                  <section key={e.participant_id} className="fam-card fam-person">
                    <div className="fam-who">
                      <span className="fam-avatar" aria-hidden="true">{initial(e.display_name)}</span>
                      <div>
                        <h2>{e.display_name}</h2>
                        {e.active && <span className="fam-muted">{t("sharingSince", { date: t.date(e.since) })}</span>}
                      </div>
                    </div>
                    {!e.active ? (
                      <p className="fam-ended">{t("familyEnded", { name: e.display_name, date: t.date(e.ended_at) })}</p>
                    ) : (
                      <>
                        <div className="fam-stats">
                          <span><b>{t.num(e.recent.length)}</b>{t("familyRecent")}</span>
                          <span><b>{t.num(done)}</b>{t("sessionStatus_completed")}</span>
                        </div>
                        {e.recent.length === 0 && <p className="fam-muted">{t("familyNoRecent")}</p>}
                        <ul className="fam-timeline">
                          {e.recent.slice(0, 6).map((r, i) => (
                            <li key={i}>
                              <span>{t.code(r.protocol_code)}<small>{t.date(r.at)}</small></span>
                              <Status level={r.status === "completed" ? "ok" : "quiet"}>{t(`sessionStatus_${r.status}` as "sessionStatus_completed")}</Status>
                            </li>
                          ))}
                        </ul>
                        <button className="fam-btn" onClick={() => { setWho(e.participant_id); setView("write"); }}>
                          <PenLine size={18} aria-hidden="true" />{t("famNavWrite")}
                        </button>
                      </>
                    )}
                  </section>
                );
              })}
            </div>
            <aside className="fam-note">
              <h2>{t("famSeeTitle")}</h2>
              <p>{t("familyWhat")}</p>
              <p>{t("familyNoResponse")}</p>
            </aside>
          </>
        )}

        {view === "write" && entries && (
          active.length === 0 ? <p className="fam-card fam-muted">{t("famNoActive")}</p> : (
            <section className="fam-card">
              {active.length > 1 && (
                <div className="fam-pick" role="radiogroup" aria-label={t("famWhoFor")}>
                  {active.map((e) => (
                    <button key={e.participant_id} role="radio" aria-checked={e.participant_id === target.participant_id}
                      onClick={() => setWho(e.participant_id)}>{e.display_name}</button>
                  ))}
                </div>
              )}
              <Compose key={target.participant_id} pid={target.participant_id} name={target.display_name} />
            </section>
          )
        )}

        {view === "account" && (
          <section className="fam-card"><Account user={user} large /></section>
        )}
        <p className="fam-foot">{t("prototypeLong")}</p>
      </main>
    </div>
  );
}
