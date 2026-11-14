import { ReactNode, useEffect, useRef } from "react";
import { useT } from "./i18n";

export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#052640" />
      <circle cx="13" cy="16" r="6.5" fill="none" stroke="#fff" strokeWidth="2" />
      <circle cx="19" cy="16" r="6.5" fill="none" stroke="#7fd3e3" strokeWidth="2" />
    </svg>
  );
}

/** The one NeuroTwin brand: the two-ring mark and the wordmark. The wordmark is the product name and is not translated.
 *  Used everywhere (landing, sign-in, loading, every portal, Brain Analytics). `size` picks a variant, `tone="light"` is for dark backgrounds. */
export function Brand({ size = "md", tone = "dark", page }: { size?: "sm" | "md" | "lg"; tone?: "dark" | "light"; page?: string }) {
  const px = size === "sm" ? 22 : size === "lg" ? 40 : 30;
  return (
    <span className={`brand brand-${size} brand-${tone}`}>
      <Mark size={px} />
      <span className="brand-word" lang="en" dir="ltr">NeuroTwin</span>
      {page && <span className="brand-page"><span aria-hidden="true">/</span> {page}</span>}
    </span>
  );
}

const GLYPH: Record<string, string> = { usable: "✓", doubtful: "?", unusable: "✕", ok: "✓", warn: "!", fail: "✕", quiet: "–" };

/** Status as a symbol and a word, never colour alone. */
export function Status({ level, children }: { level: keyof typeof GLYPH; children: ReactNode }) {
  return <span className={`status ${level}`}><span className="glyph" aria-hidden="true">{GLYPH[level]}</span>{children}</span>;
}

export function LangSwitch() {
  const { t, setLang } = useT();
  return (
    <button className="btn" onClick={() => setLang(t.lang === "en" ? "ar" : "en")} lang={t.lang === "en" ? "ar" : "en"}>
      {t("switchTo")}
    </button>
  );
}

/** Moves focus to a screen's heading when the screen changes, so screen-reader users hear where they are. */
export function Heading({ children, level = 1 }: { children: ReactNode; level?: 1 | 2 }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  const Tag = level === 1 ? "h1" : "h2";
  return <Tag ref={ref} tabIndex={-1} style={{ outline: "none" }}>{children}</Tag>;
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useT();
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="notice warn" role="alert">
      <strong>{t("somethingWrong")}</strong> <span className="muted">{msg}</span>
      {onRetry && <> <button className="link" onClick={onRetry}>{t("tryAgain")}</button></>}
    </div>
  );
}

/** A plain message for a form that did not go through: the server's own words, no extra framing. */
export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return <p className="form-error" role="alert">{msg}</p>;
}
