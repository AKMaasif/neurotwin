import { FormEvent, useEffect, useRef, useState } from "react";
import { api, DemoAccount, User } from "./api";
import { Key, useT } from "./i18n";
import { Brand, FormError, LangSwitch } from "./ui";

const GROUPS: { role: User["role"]; label: Key }[] = [
  { role: "participant", label: "roleParticipant" },
  { role: "family", label: "roleFamily" },
  { role: "clinician", label: "roleClinician" },
];

export default function SignIn({ onSignedIn }: { onSignedIn: (csrf: string, u: User) => void }) {
  const { t } = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [demo, setDemo] = useState<DemoAccount[]>([]);
  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.demoAccounts().then(setDemo).catch(() => setDemo([])); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.login(username.trim(), password);
      setPassword("");
      onSignedIn(r.csrf, r.user);
    } catch (err) { setError(err); }
    setBusy(false);
  };

  const use = (a: DemoAccount) => { setUsername(a.username); passwordRef.current?.focus(); };

  return (
    <main className="signin">
      <div className="topline"><Brand /><LangSwitch /></div>
      <div>
        <p className="eyebrow">{t("signinEyebrow")}</p>
        <h1>{t("signinTitle")}</h1>
      </div>
      <div className="notice">{t("prototypeLong")}</div>

      <form className="signin-form" onSubmit={submit} noValidate>
        <label>
          <span>{t("siUsername")}</span>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
            autoCapitalize="none" spellCheck={false} required dir="ltr" />
        </label>
        <label>
          <span>{t("siPassword")}</span>
          <span className="pw">
            <input ref={passwordRef} type={show ? "text" : "password"} value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required dir="ltr" />
            <button type="button" className="btn" onClick={() => setShow(!show)} aria-pressed={show}>{show ? t("siHide") : t("siShow")}</button>
          </span>
        </label>
        <FormError error={error} />
        <button className="btn primary" type="submit" disabled={busy || !username.trim() || !password}>
          {busy ? t("siSigningIn") : t("siSubmit")}
        </button>
      </form>

      {demo.length > 0 && (
        <section className="acct-group" aria-labelledby="demo-h">
          <h2 id="demo-h">{t("siDemoTitle")}</h2>
          <p className="muted" style={{ margin: "0 0 10px", fontSize: 14 }}>{t("siDemoHint")}</p>
          {GROUPS.map((g) => {
            const rows = demo.filter((a) => a.role === g.role);
            if (!rows.length) return null;
            return (
              <div key={g.role} style={{ marginBottom: 12 }}>
                <h2 style={{ marginBottom: 6 }}>{t(g.label)}</h2>
                <div className="acct-list">
                  {rows.map((a) => (
                    <button key={a.username} className="acct" onClick={() => use(a)} aria-label={`${t("siUse")} ${a.display_name}`}>
                      <b><bdi>{a.display_name}</bdi></b>
                      <span className="mono" dir="ltr">{a.username}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      )}
    </main>
  );
}
