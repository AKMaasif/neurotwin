import { useEffect, useState } from "react";
import { api, Background as Bg } from "../api";
import { useT } from "../i18n";
import { ErrorNote } from "../ui";

/** Education and first language: optional, the person's own to set or clear. The clinician sees them as context only. */
export default function Background() {
  const { t } = useT();
  const [bg, setBg] = useState<Bg | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { api.background().then(setBg, setError); }, []);
  if (!bg) return <ErrorNote error={error} />;

  const save = async (next: { education: string | null; first_language: string | null }) => {
    setError(null); setSaved(false);
    try { setBg(await api.setBackground(next)); setSaved(true); } catch (e) { setError(e); }
  };
  const field = (key: "education" | "first_language", label: string, prefix: "bg_" | "bgl_") => (
    <label style={{ display: "grid", gap: 6, fontWeight: 700 }}>
      {label}
      <select value={bg[key] ?? ""} style={{ minHeight: 56, fontSize: 18 }}
        onChange={(e) => save({ education: bg.education, first_language: bg.first_language, [key]: e.target.value || null })}>
        <option value="">{t("bgNotSaid")}</option>
        {(bg.options?.[key] ?? []).map((o) => <option key={o} value={o}>{t(`${prefix}${o}` as "bg_none")}</option>)}
      </select>
    </label>
  );
  return (
    <section className="p-card" aria-labelledby="bg-h" style={{ display: "grid", gap: 12 }}>
      <h2 id="bg-h" style={{ fontSize: 20, margin: 0 }}>{t("bgTitle")}</h2>
      <p className="muted" style={{ margin: 0 }}>{t("bgHint")}</p>
      {field("education", t("bgEducation"), "bg_")}
      {field("first_language", t("bgLanguage"), "bgl_")}
      {saved && <p role="status" style={{ margin: 0 }}>{t("bgSaved")}</p>}
      <ErrorNote error={error} />
    </section>
  );
}
