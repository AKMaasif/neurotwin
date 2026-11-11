import { ReactNode, useEffect, useRef, useState } from "react";
import { ArrowRight, Heart, HeartHandshake, Pause, Play, ScanSearch, ShieldCheck, Stethoscope, UserRound, Waypoints, ClipboardList } from "lucide-react";
import { DemoAccount, User } from "../api";
import { Key, useT } from "../i18n";
import "./landing.css";

type Role = User["role"];

const CARDS: { role: Role; tag: Key; title: Key; body: Key; go: Key; Icon: typeof UserRound; tone: string }[] = [
  { role: "participant", tag: "lpPatTag", title: "lpPatTitle", body: "lpPatBody", go: "lpPatGo", Icon: UserRound, tone: "pat" },
  { role: "clinician", tag: "lpCliTag", title: "lpCliTitle", body: "lpCliBody", go: "lpCliGo", Icon: Stethoscope, tone: "cli" },
  { role: "family", tag: "lpFamTag", title: "lpFamTitle", body: "lpFamBody", go: "lpFamGo", Icon: HeartHandshake, tone: "fam" },
];

const STEPS: { n: string; t: Key; b: Key; Icon: typeof UserRound }[] = [
  { n: "01", t: "lpS1T", b: "lpS1B", Icon: ClipboardList },
  { n: "02", t: "lpS2T", b: "lpS2B", Icon: Waypoints },
  { n: "03", t: "lpS3T", b: "lpS3B", Icon: ScanSearch },
  { n: "04", t: "lpS4T", b: "lpS4B", Icon: Heart },
];

const PRINCIPLES: [Key, Key][] = [["lpP1T", "lpP1B"], ["lpP2T", "lpP2B"], ["lpP3T", "lpP3B"], ["lpP4T", "lpP4B"]];

function prefersReducedMotion() {
  return typeof window !== "undefined" && !!window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** The hero animation. It starts by itself only when that is kind: not with reduced motion, not on Data Saver, and it
 *  pauses while off screen. The person can always pause or play it with the button. */
function BrainVideo() {
  const { t } = useT();
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const userPaused = useRef(false);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const conn = (navigator as unknown as { connection?: { saveData?: boolean } }).connection;
    const allowAuto = !prefersReducedMotion() && !conn?.saveData;
    if (allowAuto) v.play().catch(() => undefined);
    else userPaused.current = true;
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(([e]) => {
      if (!e) return;
      if (e.isIntersecting) { if (!userPaused.current) v.play().catch(() => undefined); }
      else v.pause();
    }, { threshold: 0.15 });
    io.observe(v);
    return () => io.disconnect();
  }, []);

  const toggle = () => {
    const v = ref.current;
    if (!v) return;
    if (v.paused) { userPaused.current = false; v.play().catch(() => undefined); }
    else { userPaused.current = true; v.pause(); }
  };

  return (
    <div className="lp-video">
      <div className="lp-video-glow" aria-hidden="true" />
      <figure className="lp-video-frame" role="img" aria-label={t("lpVideoAlt")}>
        <video ref={ref} muted loop playsInline preload="metadata" poster="/landing/brain-poster.jpg" aria-hidden="true"
          onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}>
          <source src="/landing/brain-loop.mp4" type="video/mp4" />
        </video>
        <span className="lp-video-shade" aria-hidden="true" />
        <button type="button" className="lp-video-btn" onClick={toggle} aria-label={playing ? t("lpPause") : t("lpPlay")}>
          {playing ? <Pause size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}
        </button>
      </figure>
      <span className="lp-chip lp-chip-a" aria-hidden="true"><i style={{ background: "#2fa36b" }} />{t("lpChipBase")}</span>
      <span className="lp-chip lp-chip-b" aria-hidden="true"><i style={{ background: "#f5a623" }} />{t("lpChipChange")}</span>
      <span className="lp-chip lp-chip-c dark" aria-hidden="true"><i style={{ background: "#fff" }} />{t("lpChipReview")}</span>
    </div>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="lp-eyebrow reveal">{children}</div>;
}

export type LandingProps = {
  demo: DemoAccount[] | null;
  busy: string | null;
  error: ReactNode;
  onEnter: (a: DemoAccount) => void;
  /** Shown instead of the view cards when this server has no demo accounts (the password form). */
  fallback: ReactNode;
};

export default function Landing({ demo, busy, error, onEnter, fallback }: LandingProps) {
  const { t, setLang } = useT();
  const root = useRef<HTMLDivElement>(null);

  // Gentle reveal on scroll. Without motion, or without IntersectionObserver, everything is simply shown.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const items = Array.from(el.querySelectorAll<HTMLElement>(".reveal"));
    if (prefersReducedMotion() || !("IntersectionObserver" in window)) { items.forEach((i) => i.classList.add("in")); return; }
    el.classList.add("lp-anim");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    items.forEach((i) => io.observe(i));
    return () => io.disconnect();
  }, [demo]);

  return (
    <div className="lp" ref={root}>
      <a className="lp-skip" href="#lp-access">{t("lpSkip")}</a>

      {/* ---- Hero ---- */}
      <header className="lp-hero-wrap">
        <div className="lp-hero">
          <svg className="lp-rings" viewBox="0 0 1400 760" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <g fill="none" stroke="#fff" strokeOpacity=".14"><circle cx="1000" cy="380" r="260" /><circle cx="1000" cy="380" r="360" /><circle cx="1000" cy="380" r="470" /></g>
          </svg>

          <nav className="lp-nav" aria-label={t("lpMain")}>
            <div className="lp-nav-start">
              <a className="lp-logo" href="#top">
                <svg width="30" height="30" viewBox="0 0 34 34" fill="none" aria-hidden="true"><circle cx="17" cy="17" r="15" stroke="#fff" strokeWidth="2" /><path d="M8 20c3-8 6-8 9-2s6 4 9-4" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" /></svg>
                {t("appName")}
              </a>
              <div className="lp-links">
                <a href="#lp-how">{t("lpNavHow")}</a>
                <a href="#lp-access">{t("lpNavAccess")}</a>
                <a href="#lp-principles">{t("lpNavPrinciples")}</a>
              </div>
            </div>
            <div className="lp-nav-end">
              <button type="button" className="lp-lang" onClick={() => setLang(t.lang === "en" ? "ar" : "en")} lang={t.lang === "en" ? "ar" : "en"}>
                {t("switchTo")}
              </button>
              <a className="lp-btn light" href="#lp-access">{t("lpTry")}</a>
            </div>
          </nav>

          <div className="lp-hero-body" id="top">
            <div className="lp-hero-copy">
              <span className="lp-badge"><i aria-hidden="true" />{t("lpBadge")}</span>
              <h1><span>{t("lpH1a")}</span> <span>{t("lpH1b")}</span> <span>{t("lpH1c")}</span></h1>
              <p>{t("lpSub")}</p>
              <div className="lp-cta">
                <a className="lp-btn navy" href="#lp-access">{t("lpCtaPrimary")}<ArrowRight size={18} aria-hidden="true" className="flip" /></a>
                <a className="lp-btn ghost" href="#lp-how">{t("lpCtaSecondary")}</a>
              </div>
              <p className="lp-fine">{t("lpFine")}</p>
            </div>
            <BrainVideo />
          </div>

          <div className="lp-note"><ShieldCheck size={22} aria-hidden="true" /><span>{t("lpNote")}</span></div>
        </div>
      </header>

      <main>
        {/* ---- What it is ---- */}
        <section className="lp-wrap lp-what" aria-labelledby="lp-what-h">
          <div className="lp-what-big reveal">
            <div className="lp-big" aria-hidden="true">{t("lpWhatBig")}</div>
            <div className="lp-big-cap">{t("lpWhatCap")}</div>
          </div>
          <div className="lp-what-text reveal">
            <h2 id="lp-what-h">{t("lpWhatTitle")}</h2>
            <p>{t("lpWhatBody")}</p>
            <a className="lp-btn navy" href="#lp-how">{t("lpReadMore")}</a>
          </div>
        </section>

        <div className="lp-wrap"><ul className="lp-trust reveal">
          <li>{t("lpTrust1")}</li><li>{t("lpTrust2")}</li><li>{t("lpTrust3")}</li><li>{t("lpTrust4")}</li>
        </ul></div>

        {/* ---- Anatomy ---- */}
        <section className="lp-band-wrap" aria-labelledby="lp-anat-h">
          <div className="lp-band reveal">
            <div className="lp-band-head">
              <div className="lp-eyebrow light">{t("lpAnatEyebrow")}</div>
              <h2 id="lp-anat-h">{t("lpAnatTitle")}</h2>
              <p>{t("lpAnatBody")}</p>
            </div>
            <picture>
              <source media="(max-width: 700px)" srcSet="/landing/brain-anatomy-1200.webp" />
              <img src="/landing/brain-anatomy.webp" alt={t("lpAnatAlt")} loading="lazy" decoding="async" width="2400" height="630" />
            </picture>
            <p className="lp-band-note">{t("lpAnatNote")}</p>
          </div>
        </section>

        {/* ---- Access ---- */}
        <section id="lp-access" className="lp-access" aria-labelledby="lp-access-h">
          <div className="lp-wrap">
            <Eyebrow>{t("lpAccessEyebrow")}</Eyebrow>
            <h2 id="lp-access-h" className="reveal">{t("lpAccessTitle")}</h2>
            <p className="lp-lead reveal">{t("lpAccessBody")}</p>
            {error}
            {demo === null ? <p className="lp-lead">{t("loading")}</p>
              : demo.length === 0 ? <div className="lp-fallback">{fallback}</div>
              : (
                <>
                  <div className="lp-cards">
                    {CARDS.map(({ role, tag, title, body, go, Icon, tone }) => {
                      const people = demo.filter((a) => a.role === role);
                      if (!people.length) return null;
                      const [first, ...others] = people;
                      return (
                        <article key={role} className={`lp-card ${tone} reveal`} aria-labelledby={`lp-c-${role}`}>
                          <span className="lp-card-orb" aria-hidden="true" />
                          <span className="lp-card-ico"><Icon size={30} aria-hidden="true" /></span>
                          <div className="lp-card-tag">{t(tag)}</div>
                          <h3 id={`lp-c-${role}`}>{t(title)}</h3>
                          <p>{t(body)}</p>
                          <button type="button" className="lp-card-go" disabled={busy !== null} onClick={() => onEnter(first!)}>
                            <span><b>{t(go)}</b><small>{t("wlOpenAs")} <bdi>{first!.display_name}</bdi></small></span>
                            <span className="lp-arrow"><ArrowRight size={20} aria-hidden="true" className="flip" /></span>
                          </button>
                          {others.length > 0 && (
                            <div className="lp-others">
                              <span>{t("lpOrOpenAs")}</span>
                              {others.map((a) => (
                                <button key={a.username} type="button" disabled={busy !== null} onClick={() => onEnter(a)}><bdi>{a.display_name}</bdi></button>
                              ))}
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                  <p className="lp-shared">{t("wlShared")}</p>
                </>
              )}
          </div>
        </section>

        {/* ---- How it works ---- */}
        <section id="lp-how" className="lp-wrap lp-how" aria-labelledby="lp-how-h">
          <Eyebrow>{t("lpHowEyebrow")}</Eyebrow>
          <h2 id="lp-how-h" className="reveal">{t("lpHowTitle")}</h2>
          <p className="lp-lead reveal">{t("lpHowSub")}</p>
          <div className="lp-track" aria-hidden="true"><i /></div>
          <ol className="lp-steps">
            {STEPS.map(({ n, t: k, b, Icon }, i) => (
              <li key={n} className={`lp-step s${i + 1}`}>
                <div className="lp-step-n">{n}</div>
                <Icon size={44} strokeWidth={1.6} aria-hidden="true" />
                <h3>{t(k)}</h3>
                <p>{t(b)}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ---- Three views ---- */}
        <section className="lp-wrap lp-views" aria-labelledby="lp-views-h">
          <Eyebrow>{t("lpViewsEyebrow")}</Eyebrow>
          <h2 id="lp-views-h" className="reveal">{t("lpViewsTitle")}</h2>
          <div className="lp-views-grid">
            <div className="lp-view pat reveal"><h3>{t("lpVPatT")}</h3><p>{t("lpVPatB")}</p></div>
            <div className="lp-view cli reveal"><h3>{t("lpVCliT")}</h3><p>{t("lpVCliB")}</p></div>
            <div className="lp-view fam reveal"><h3>{t("lpVFamT")}</h3><p>{t("lpVFamB")}</p></div>
          </div>
        </section>

        {/* ---- Principles ---- */}
        <section id="lp-principles" className="lp-wrap lp-prin" aria-labelledby="lp-prin-h">
          <Eyebrow>{t("lpPrinEyebrow")}</Eyebrow>
          <h2 id="lp-prin-h" className="reveal">{t("lpPrinTitle")}</h2>
          <div className="lp-prin-grid">
            {PRINCIPLES.map(([h, b]) => (
              <div key={h} className="lp-prin-item reveal"><h3>{t(h)}</h3><p>{t(b)}</p></div>
            ))}
          </div>
          <p className="lp-status">{t("lpStatus")}</p>
        </section>

        {/* ---- Final call ---- */}
        <section className="lp-wrap lp-final">
          <div className="lp-final-card reveal">
            <h2>{t("lpFinalTitle")}</h2>
            <a className="lp-btn light big" href="#lp-access">{t("lpFinalCta")}</a>
          </div>
        </section>
      </main>

      <footer className="lp-wrap lp-foot"><span>{t("lpFootLeft")}</span><span>English · العربية</span></footer>
    </div>
  );
}
