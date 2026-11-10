import { useEffect, useState } from "react";
import { api, User } from "./api";
import { Key, useT } from "./i18n";
import { Brand, ErrorNote, LangSwitch } from "./ui";

const GROUPS: { role: User["role"]; label: Key }[] = [
  { role: "participant", label: "roleParticipant" },
  { role: "family", label: "roleFamily" },
  { role: "clinician", label: "roleClinician" },
];

export default function SignIn({ onSignedIn }: { onSignedIn: (token: string, u: User) => void }) {
  const { t } = useT();
  const [accounts, setAccounts] = useState<User[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = () => { setError(null); api.demoAccounts().then(setAccounts).catch(setError); };
  useEffect(load, []);

  const choose = async (u: User) => {
    try {
      const r = await api.login(u.id);
      onSignedIn(r.token, r.user);
    } catch (e) { setError(e); }
  };

  return (
    <main className="signin">
      <div className="topline"><Brand /><LangSwitch /></div>
      <div>
        <p className="eyebrow">{t("signinEyebrow")}</p>
        <h1>{t("signinTitle")}</h1>
      </div>
      <p className="lead">{t("signinLead")}</p>
      <div className="notice">{t("prototypeLong")}</div>
      <ErrorNote error={error} onRetry={load} />
      {accounts === null && !error && <p className="muted">{t("loading")}</p>}
      {accounts && GROUPS.map((g) => (
        <section className="acct-group" key={g.role} aria-labelledby={`g-${g.role}`}>
          <h2 id={`g-${g.role}`}>{t(g.label)}</h2>
          <div className="acct-list">
            {accounts.filter((a) => a.role === g.role).map((a) => (
              <button key={a.id} className="acct" onClick={() => choose(a)}>
                <b>{a.display_name}</b>
                <span>{t("signinAs")} {a.display_name} · {a.language === "ar" ? "العربية" : "English"}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
