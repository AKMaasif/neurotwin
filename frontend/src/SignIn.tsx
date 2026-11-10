import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, HeartHandshake, Stethoscope, UserRound } from "lucide-react";
import { api, DemoAccount, User } from "./api";
import { Key, useT } from "./i18n";
import { Brand, FormError, LangSwitch } from "./ui";

const VIEWS: { role: User["role"]; label: Key; blurb: Key; Icon: typeof UserRound }[] = [
  { role: "participant", label: "roleParticipant", blurb: "wlParticipant", Icon: UserRound },
  { role: "family", label: "roleFamily", blurb: "wlFamily", Icon: HeartHandshake },
  { role: "clinician", label: "roleClinician", blurb: "wlClinician", Icon: Stethoscope },
];

/** The front door. In demo mode: pick a view and go straight in, no username or password. On a server without demo
 *  mode there are no demo accounts to list, and the username and password form is shown instead. */
export default function SignIn({ onSignedIn }: { onSignedIn: (csrf: string, u: User) => void }) {
  const { t } = useT();
  const [demo, setDemo] = useState<DemoAccount[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => { api.demoAccounts().then(setDemo).catch(() => setDemo([])); }, []);

  const enter = async (a: DemoAccount) => {
    setBusy(a.username); setError(null);
    try { const r = await api.demoEnter(a.username); onSignedIn(r.csrf, r.user); }
    catch (err) { setError(err); }
    setBusy(null);
  };

  return (
    <main className="signin">
      <div className="topline"><Brand /><LangSwitch /></div>
      <div>
        <p className="eyebrow">{t("signinEyebrow")}</p>
        <h1>{t("signinTitle")}</h1>
      </div>
      <div className="notice">{t("prototypeLong")}</div>
      <FormError error={error} />

      {demo === null ? <p className="muted">{t("loading")}</p> : demo.length === 0 ? <PasswordForm onSignedIn={onSignedIn} /> : (
        <>
          <p className="lead">{t("wlLead")}</p>
          <div className="views">
            {VIEWS.map(({ role, label, blurb, Icon }) => {
              const people = demo.filter((a) => a.role === role);
              if (!people.length) return null;
              return (
                <section key={role} className="view-card" aria-labelledby={`v-${role}`}>
                  <div className="view-head">
                    <span className="ico"><Icon size={22} aria-hidden="true" /></span>
                    <div>
                      <h2 id={`v-${role}`}>{t(label)}</h2>
                      <p>{t(blurb)}</p>
                    </div>
                  </div>
                  <div className="view-actions">
                    {people.map((a, i) => (
                      <button key={a.username} className={`btn ${i === 0 ? "primary" : ""}`} disabled={busy !== null} onClick={() => enter(a)}>
                        <span>{t("wlOpenAs")} <bdi>{a.display_name}</bdi></span>
                        <ArrowRight size={18} aria-hidden="true" className="flip" />
                      </button>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("wlShared")}</p>
        </>
      )}
    </main>
  );
}

function PasswordForm({ onSignedIn }: { onSignedIn: (csrf: string, u: User) => void }) {
  const { t } = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try { const r = await api.login(username.trim(), password); setPassword(""); onSignedIn(r.csrf, r.user); }
    catch (err) { setError(err); }
    setBusy(false);
  };

  return (
    <form className="signin-form" onSubmit={submit} noValidate>
      <label>
        <span>{t("siUsername")}</span>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
          autoCapitalize="none" spellCheck={false} required dir="ltr" />
      </label>
      <label>
        <span>{t("siPassword")}</span>
        <span className="pw">
          <input type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password" required dir="ltr" />
          <button type="button" className="btn" onClick={() => setShow(!show)} aria-pressed={show}>{show ? t("siHide") : t("siShow")}</button>
        </span>
      </label>
      <FormError error={error} />
      <button className="btn primary" type="submit" disabled={busy || !username.trim() || !password}>
        {busy ? t("siSigningIn") : t("siSubmit")}
      </button>
    </form>
  );
}
