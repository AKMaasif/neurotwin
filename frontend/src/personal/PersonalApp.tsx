import { useCallback, useEffect, useState } from "react";
import { api, Consent, Session, User } from "../api";
import { useT } from "../i18n";
import { Brand, ErrorNote, Heading, LangSwitch } from "../ui";
import ConsentScreen from "./Consent";
import Checkin from "./Checkin";
import Reaction from "./Reaction";
import Sharing from "./Sharing";
import Records from "./Records";

export type Screen = "home" | "consent" | "checkin" | "reaction" | "sharing" | "records" | "urgent" | "about";

export default function PersonalApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const { t } = useT();
  const [screen, setScreen] = useState<Screen>("home");
  const [consent, setConsent] = useState<Consent | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [cs, ss] = await Promise.all([api.consents(), api.sessions(user.id)]);
      setConsent(cs.find((c) => c.scope === "participation") ?? null);
      setSessions(ss);
    } catch (e) { setError(e); }
    setReady(true);
  }, [user.id]);
  useEffect(() => { refresh(); }, [refresh]);

  const go = (s: Screen) => { setScreen(s); window.scrollTo(0, 0); };
  const home = () => { go("home"); refresh(); };
  const participating = consent?.granted === true;

  let body;
  if (!ready) body = <p className="muted">{t("loading")}</p>;
  else if (screen === "consent" || (screen === "home" && !participating && consent?.at == null))
    body = <ConsentScreen consent={consent} onChanged={home} onClose={home} />;
  else if (screen === "checkin") body = <Checkin onDone={home} />;
  else if (screen === "reaction") body = <Reaction onDone={home} />;
  else if (screen === "sharing") body = <Sharing onBack={home} />;
  else if (screen === "records") body = <Records user={user} onBack={home} />;
  else if (screen === "urgent") body = <Info title={t("urgentTitle")} lines={[t("urgentBody"), t("urgentUAE")]} onBack={home} />;
  else if (screen === "about") body = <Info title={t("aboutTitle")} lines={[t("aboutBody"), t("prototypeLong")]} onBack={home} />;
  else body = <Home user={user} sessions={sessions} participating={participating} go={go} />;

  return (
    <div className="personal">
      <header className="p-bar">
        <Brand />
        <div className="who">
          <LangSwitch />
          <button className="link" onClick={onSignOut}>{t("signOut")}</button>
        </div>
      </header>
      <main className="p-main">
        <ErrorNote error={error} onRetry={refresh} />
        {body}
      </main>
      <footer className="p-foot">
        <button className="link" onClick={() => go("urgent")}>{t("urgentHelp")}</button>
        <button className="link" onClick={() => go("about")}>{t("aboutLink")}</button>
      </footer>
    </div>
  );
}

function isToday(iso: string) {
  const d = new Date(iso), n = new Date();
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
}

function Home({ user, sessions, participating, go }: {
  user: User; sessions: Session[]; participating: boolean; go: (s: Screen) => void;
}) {
  const { t } = useT();
  const doneToday = (code: string) => sessions.some((s) => s.protocol_code === code && s.status === "completed" && isToday(s.started_at));
  const activities = [
    { code: "daily_checkin", screen: "checkin" as Screen, title: t("checkinTitle"), meta: t("checkinMeta") },
    { code: "reaction_time", screen: "reaction" as Screen, title: t("reactionTitle"), meta: t("reactionMeta") },
  ];
  const next = activities.find((a) => !doneToday(a.code));

  return (
    <>
      <div style={{ display: "grid", gap: 6 }}>
        <Heading>{t("hello", { name: user.display_name })}</Heading>
        <p className="lede">{t("homeLede")}</p>
      </div>

      {!participating && (
        <div className="notice warn">
          {t("consentNone")} <button className="link" onClick={() => go("consent")}>{t("consentTitle")}</button>
        </div>
      )}

      {participating && next && (
        <section className="p-card next" aria-labelledby="next-h">
          <p className="eyebrow">{t("nextUp")}</p>
          <h2 id="next-h">{next.title}</h2>
          <p className="muted">{next.meta}</p>
          <button className="btn primary block" onClick={() => go(next.screen)}>{t("start")}</button>
        </section>
      )}

      {participating && (
        <div className="p-list">
          {activities.filter((a) => a !== next).map((a) => (
            <button key={a.code} className="p-row" onClick={() => go(a.screen)}>
              <span className="t"><b>{a.title}</b><span>{doneToday(a.code) ? `✓ ${t("doneToday")}` : a.meta}</span></span>
              <span className="chev" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
      )}

      <div className="p-list">
        {([["sharing", "sharingTitle", "sharingMeta"], ["records", "recordsTitle", "recordsMeta"],
          ["consent", "consentTitle", "consentMeta"]] as const).map(([s, title, meta]) => (
          <button key={s} className="p-row" onClick={() => go(s)}>
            <span className="t"><b>{t(title)}</b><span>{t(meta)}</span></span>
            <span className="chev" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
    </>
  );
}

function Info({ title, lines, onBack }: { title: string; lines: string[]; onBack: () => void }) {
  const { t } = useT();
  return (
    <>
      <Heading>{title}</Heading>
      {lines.map((l) => <p key={l}>{l}</p>)}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
