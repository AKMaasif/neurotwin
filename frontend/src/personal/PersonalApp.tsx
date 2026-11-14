import { useCallback, useEffect, useState } from "react";
import { BellRing, ChartNoAxesColumn, ChevronRight, Info as InfoIcon, MessageCircle, MessageCircleHeart, Phone, ShieldCheck, Users, UserRound, Zap, House } from "lucide-react";
import { api, Consent, Session, User } from "../api";
import { useT } from "../i18n";
import { Brand, ErrorNote, Heading, LangSwitch } from "../ui";
import ConsentScreen from "./Consent";
import Checkin from "./Checkin";
import Reaction from "./Reaction";
import Sharing from "./Sharing";
import Records from "./Records";
import Reminders from "./Reminders";
import Assistant from "./Assistant";
import ConcernScreen from "./Concern";
import Messages from "./Messages";
import Account from "../Account";
import "./patient.css";

export type Screen = "home" | "consent" | "checkin" | "reaction" | "sharing" | "reminders" | "messages" | "records" | "account" | "urgent" | "about" | "assistant" | "concern";

const TAB_SCREENS: Screen[] = ["home", "reminders", "messages", "records"];

export default function PersonalApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const { t } = useT();
  const [screen, setScreen] = useState<Screen>("home");
  const [consent, setConsent] = useState<Consent | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [unread, setUnread] = useState(0);
  const [waiting, setWaiting] = useState(0);
  const [concernNews, setConcernNews] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [cs, ss, inbox, pl] = await Promise.all([api.consents(), api.sessions(user.id), api.inbox().catch(() => []), api.plansAwaiting().catch(() => [])]);
      setConsent(cs.find((c) => c.scope === "participation") ?? null);
      setSessions(ss);
      setUnread(inbox.filter((m) => !m.read).length);
      setWaiting(pl.length);
      api.notices().then((n) => setConcernNews(n.filter((x) => !x.read && x.kind.startsWith("concern_")).length)).catch(() => {});
    } catch (e) { setError(e); }
    setReady(true);
  }, [user.id]);
  useEffect(() => { refresh(); }, [refresh]);

  const go = (s: Screen) => { setScreen(s); window.scrollTo(0, 0); };
  const home = () => { go("home"); refresh(); };
  const tab = (s: Screen) => { go(s); refresh(); };
  const participating = consent?.granted === true;
  const needsConsent = screen === "home" && !participating && consent?.at == null;

  let body;
  if (!ready) body = <p className="muted">{t("loading")}</p>;
  else if (screen === "consent" || needsConsent)
    body = <ConsentScreen consent={consent} onChanged={home} onClose={home} />;
  else if (screen === "checkin") body = <Checkin onDone={home} />;
  else if (screen === "reaction") body = <Reaction onDone={home} />;
  else if (screen === "messages") body = <Messages onBack={home} />;
  else if (screen === "reminders") body = <Reminders onBack={home} />;
  else if (screen === "assistant") body = <Assistant go={go} onBack={home} />;
  else if (screen === "concern") body = <ConcernScreen go={go} onBack={home} />;
  else if (screen === "sharing") body = <Sharing onBack={home} />;
  else if (screen === "records") body = <Records user={user} onBack={home} />;
  else if (screen === "account") body = (
    <>
      <Heading>{t("acTitle")}</Heading>
      <Account user={user} large />
      <button className="btn block" onClick={home}>{t("backHome")}</button>
    </>
  );
  else if (screen === "urgent") body = <Info title={t("urgentTitle")} lines={[t("urgentBody"), t("urgentUAE")]} onBack={home} />;
  else if (screen === "about") body = <Info title={t("aboutTitle")} lines={[t("aboutBody"), t("prototypeLong")]} onBack={home} />;
  else body = <Home user={user} sessions={sessions} participating={participating} unread={unread} waiting={waiting} concernNews={concernNews} go={go} />;

  const tabbed = ready && TAB_SCREENS.includes(screen) && !needsConsent;

  return (
    <div className={`personal ${tabbed ? "has-tabs" : ""}`}>
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
      {tabbed && (
        <nav className="pt-tabs" aria-label={t("appName")}>
          {([["home", "ptTabToday", House], ["reminders", "ptTabReminders", BellRing], ["messages", "ptTabMessages", MessageCircle], ["records", "recordsTitle", ChartNoAxesColumn]] as const).map(([s, label, Icon]) => (
            <button key={s} onClick={() => tab(s)} aria-current={screen === s ? "page" : undefined}>
              <Icon size={24} aria-hidden="true" />{t(label)}
              {s === "messages" && unread > 0 && <span className="dot" role="img" aria-label={t("ptNew", { n: unread })} />}
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}

function isToday(iso: string) {
  const d = new Date(iso), n = new Date();
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
}

/** The four numbers behind the ring: how many of today's two activities are finished. Not a score, not a streak. */
function Ring({ done, total, label }: { done: number; total: number; label: string }) {
  const { t } = useT();
  const offset = 264 - 264 * (total ? done / total : 0);
  return (
    <svg className="ring" width="104" height="104" viewBox="0 0 104 104" role="img" aria-label={label}>
      <circle className="trk" cx="52" cy="52" r="42" fill="none" strokeWidth="10" />
      <circle className="bar" cx="52" cy="52" r="42" fill="none" strokeWidth="10" style={{ strokeDashoffset: offset }} transform="rotate(-90 52 52)" />
      <text x="52" y="60" textAnchor="middle" fill="#fff" fontWeight="800" fontSize="26">{t.num(done)}/{t.num(total)}</text>
    </svg>
  );
}

function Home({ user, sessions, participating, unread, waiting, concernNews, go }: {
  user: User; sessions: Session[]; participating: boolean; unread: number; waiting: number; concernNews: number; go: (s: Screen) => void;
}) {
  const { t } = useT();
  const doneToday = (code: string) => sessions.some((s) => s.protocol_code === code && s.status === "completed" && isToday(s.started_at));
  const activities = [
    { code: "daily_checkin", screen: "checkin" as Screen, title: t("checkinTitle"), meta: t("checkinMeta"), Icon: MessageCircleHeart, tone: "a" },
    { code: "reaction_time", screen: "reaction" as Screen, title: t("reactionTitle"), meta: t("reactionMeta"), Icon: Zap, tone: "g" },
  ];
  const next = activities.find((a) => !doneToday(a.code));
  const done = activities.filter((a) => doneToday(a.code)).length;
  const ringLabel = t("ptProgress", { n: t.num(done), total: t.num(activities.length) });

  const manage = [
    { s: "consent" as Screen, title: t("consentTitle"), meta: t("consentMeta"), Icon: ShieldCheck, cls: "c1" },
    { s: "sharing" as Screen, title: t("sharingTitle"), meta: t("sharingMeta"), Icon: Users, cls: "c2" },
    { s: "about" as Screen, title: t("aboutTitle"), meta: t("aboutLink"), Icon: InfoIcon, cls: "c4" },
    ...(!user.is_demo ? [{ s: "account" as Screen, title: t("acTitle"), meta: t("acLink"), Icon: UserRound, cls: "c5" }] : []),
  ];

  return (
    <div className="pt-rise" style={{ display: "contents" }}>
      <div className="pt-hello">
        <Heading>{t("hello", { name: user.display_name })}</Heading>
        <p className="lede">{t("homeLede")}</p>
      </div>

      {!participating && (
        <div className="notice warn">
          {t("consentNone")} <button className="link" onClick={() => go("consent")}>{t("consentTitle")}</button>
        </div>
      )}

      {participating && (
        <section className="pt-hero" aria-label={ringLabel}>
          <Ring done={done} total={activities.length} label={ringLabel} />
          <div>
            <b>{done === activities.length ? t("ptProgressAll") : done === 0 ? t("ptProgressNone") : ringLabel}</b>
            <span>{t("ptProgressSub")}</span>
          </div>
        </section>
      )}

      {participating && (
        <>
          <h2 className="pt-sec">{t("ptForToday")}</h2>
          {activities.map((a) => {
            const isDone = doneToday(a.code);
            return (
              <button key={a.code} className={`pt-tile ${isDone ? "done" : a === next ? "next" : ""}`} onClick={() => go(a.screen)}>
                <span className={`ico ${a.tone}`}><a.Icon size={34} aria-hidden="true" /></span>
                <span className="t"><b>{a.title}</b><span>{isDone ? `✓ ${t("doneToday")}` : a.meta}</span></span>
                <ChevronRight className="go" size={26} aria-hidden="true" />
              </button>
            );
          })}
        </>
      )}

      <button className="pt-tile" onClick={() => go("reminders")}>
        <span className="ico v"><BellRing size={32} aria-hidden="true" /></span>
        <span className="t"><b>{t("remTitle")}</b><span>{waiting > 0 ? t("remPending") : t("remMeta")}</span></span>
        {waiting > 0 && <span className="pt-badge" aria-hidden="true">{t.num(waiting)}</span>}
        <ChevronRight className="go" size={26} aria-hidden="true" />
      </button>
      <button className="pt-tile" onClick={() => go("concern")}>
        <span className="ico v"><MessageCircle size={32} aria-hidden="true" /></span>
        <span className="t"><b>{t("cnTitle")}</b><span>{concernNews > 0 ? t("cnUpdate") : t("cnMeta")}</span></span>
        {concernNews > 0 && <span className="pt-badge" aria-hidden="true">{t.num(concernNews)}</span>}
        <ChevronRight className="go" size={26} aria-hidden="true" />
      </button>
      <button className="pt-tile" onClick={() => go("assistant")}>
        <span className="ico r"><MessageCircle size={32} aria-hidden="true" /></span>
        <span className="t"><b>{t("asTitle")}</b><span>{t("asMeta")}</span></span>
        <ChevronRight className="go" size={26} aria-hidden="true" />
      </button>
      <button className="pt-tile" onClick={() => go("messages")}>
        <span className="ico r"><MessageCircle size={32} aria-hidden="true" /></span>
        <span className="t"><b>{t("msgTitle")}</b><span>{unread > 0 ? t("ptNew", { n: t.num(unread) }) : t("msgMeta")}</span></span>
        {unread > 0 && <span className="pt-badge" aria-hidden="true">{t.num(unread)}</span>}
        <ChevronRight className="go" size={26} aria-hidden="true" />
      </button>

      <h2 className="pt-sec">{t("ptManage")}</h2>
      <div className="pt-grid">
        {manage.map(({ s, title, meta, Icon, cls }) => (
          <button key={s} className={`pt-mini ${cls}`} onClick={() => go(s)}>
            <Icon size={28} aria-hidden="true" /><b>{title}</b><span>{meta}</span>
          </button>
        ))}
      </div>

      <button className="pt-urgent" onClick={() => go("urgent")}>
        <span className="ico"><Phone size={26} aria-hidden="true" /></span>
        <span><b>{t("urgentHelp")}</b><span>{t("ptUrgentSub")}</span></span>
      </button>
    </div>
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
