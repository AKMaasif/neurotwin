import { useEffect, useMemo, useState } from "react";
import { api, setCsrf, SIGNED_OUT, User } from "./api";
import { Lang, LangContext, makeT } from "./i18n";
import SignIn from "./SignIn";
import PersonalApp from "./personal/PersonalApp";
import FamilyApp from "./family/FamilyApp";
import ClinicianApp from "./clinician/ClinicianApp";

const LANG_KEY = "neurotwin.lang";
function savedLang(): Lang {
  try { return localStorage.getItem(LANG_KEY) === "ar" ? "ar" : "en"; } catch { return "en"; }
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(savedLang);
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const t = useMemo(() => makeT(lang), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.body.dir = lang === "ar" ? "rtl" : "ltr";
    document.title = t("appName");
  }, [lang, t]);

  // Is this browser already signed in? The cookie is invisible to the page, so ask the server.
  useEffect(() => {
    api.session().then((s) => { setCsrf(s.csrf); setUser(s.user); setLangState(s.user.language); })
      .catch(() => setUser(null)).finally(() => setChecked(true));
    const onSignedOut = () => setUser(null);
    window.addEventListener(SIGNED_OUT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT, onSignedOut);
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(LANG_KEY, l); } catch { /* storage blocked */ }
    if (user) api.setLanguage(l).catch(() => undefined);
  };

  const signIn = (csrf: string, u: User) => {
    setCsrf(csrf);
    setUser(u);
    setLang(u.language);
  };
  const signOut = () => {
    api.logout().catch(() => undefined).finally(() => { setCsrf(null); setUser(null); });
  };

  return (
    <LangContext.Provider value={{ t, setLang }}>
      {!checked ? null
        : !user ? <SignIn onSignedIn={signIn} />
        : user.role === "participant" ? <PersonalApp user={user} onSignOut={signOut} />
        : user.role === "family" ? <FamilyApp user={user} onSignOut={signOut} />
        : <ClinicianApp user={user} onSignOut={signOut} />}
    </LangContext.Provider>
  );
}
