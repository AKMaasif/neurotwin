import { FormEvent, useEffect, useState } from "react";
import { api, DemoAccount, User } from "./api";
import { useT } from "./i18n";
import { FormError } from "./ui";
import Landing from "./landing/Landing";

/** The front door: the landing page. In demo mode the three view cards go straight in, no username or password. On a
 *  server without demo mode there are no demo accounts to list, and the username and password form is shown instead. */
export default function SignIn({ onSignedIn }: { onSignedIn: (csrf: string, u: User) => void }) {
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
    <Landing demo={demo} busy={busy} onEnter={enter} error={<FormError error={error} />}
      fallback={<PasswordForm onSignedIn={onSignedIn} />} />
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
