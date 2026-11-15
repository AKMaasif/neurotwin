import { useEffect, useMemo, useState } from "react";
import { api, setCsrf, SIGNED_OUT, User } from "./api";
import { Lang, LangContext, makeT } from "./i18n";
import SignIn from "./SignIn";
import PersonalApp from "./personal/PersonalApp";
import FamilyApp from "./family/FamilyApp";
import ClinicianApp from "./clinician/ClinicianApp";
import * as nav from "./nav";

const LANG_KEY = "neurotwin.lang";
// The language a person picked in this browser (landing page, sign-in or header). null = never chosen here.
function chosenLang(): Lang | null {
  try { const v = localStorage.getItem(LANG_KEY); return v === "ar" || v === "en" ? v : null; } catch { return null; }
}
function savedLang(): Lang { return chosenLang() ?? "en"; }

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
    api.session().then((s) => {
      setCsrf(s.csrf); setUser(s.user);
      // A choice made in this browser wins; the account language is only the starting point when there is none.
      const mine = chosenLang();
      if (mine) { setLangState(mine); if (mine !== s.user.language) api.setLanguage(mine).catch(() => undefined); }
      else setLangState(s.user.language);
    })
      .catch(() => setUser(null)).finally(() => setChecked(true));
    const onSignedOut = () => setUser(null);
    window.addEventListener(SIGNED_OUT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT, onSignedOut);
  }, []);

  // Browser history follows the sign-in state: signed in = Back stays on the dashboard; signed out = nothing of it remains.
  useEffect(() => {
    if (!checked) return;
    if (user) nav.enter(); else nav.exit();
  }, [user, checked]);

  // A page restored from the browser's back/forward cache can show a dashboard that was visible before sign-out. Ask the server again.
  useEffect(() => {
    const onShow = (e: PageTransitionEvent) => {
      if (!e.persisted) return;
      api.session().then((s) => { setCsrf(s.csrf); setUser(s.user); }).catch(() => { setCsrf(null); setUser(null); });
    };
    window.addEventListener("pageshow", onShow);
    return () => window.removeEventListener("pageshow", onShow);
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(LANG_KEY, l); } catch { /* storage blocked */ }
    if (user) api.setLanguage(l).catch(() => undefined);
  };

  const signIn = (csrf: string, u: User) => {
    setCsrf(csrf);
    setUser(u);
    // Signing in must not change what the person is looking at: keep the language shown (landing choice or default)
    // as their choice and save it to the account, instead of switching to the account's stored language.
    try { localStorage.setItem(LANG_KEY, lang); } catch { /* storage blocked */ }
    if (lang !== u.language) api.setLanguage(lang).catch(() => undefined);
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
