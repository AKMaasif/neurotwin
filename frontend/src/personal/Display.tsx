import { useState } from "react";
import { useT } from "../i18n";
import { Heading } from "../ui";

export type Display = { text: "n" | "l" | "x"; contrast: boolean; calm: boolean };
const KEY = "neurotwin.display";
export const DEFAULT_DISPLAY: Display = { text: "n", contrast: false, calm: false };

export function loadDisplay(): Display {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    return { text: ["n", "l", "x"].includes(v.text) ? v.text : "n", contrast: v.contrast === true, calm: v.calm === true };
  } catch { return DEFAULT_DISPLAY; }
}
export const displayClasses = (d: Display) => `${d.text === "l" ? "txt-l" : d.text === "x" ? "txt-x" : ""} ${d.contrast ? "hc" : ""} ${d.calm ? "calm" : ""}`;

/** Per-device reading choices. Kept in the browser only (it may be unavailable, and then the choice lasts until the page is closed). */
export default function DisplaySettings({ value, onChange, onBack }: { value: Display; onChange: (d: Display) => void; onBack: () => void }) {
  const { t } = useT();
  const [d, setD] = useState(value);
  const set = (n: Display) => { setD(n); onChange(n); try { localStorage.setItem(KEY, JSON.stringify(n)); } catch { /* not kept after the page closes */ } };
  const toggle = (label: "dsContrast" | "dsCalm", key: "contrast" | "calm") => (
    <section className="p-card">
      <h2 style={{ fontSize: 20 }}>{t(label)}</h2>
      <div className="choices" role="radiogroup" aria-label={t(label)} style={{ display: "flex", gap: 12 }}>
        {([[true, "dsOn"], [false, "dsOff"]] as const).map(([v, k]) => (
          <button key={k} className="choice" role="radio" aria-checked={d[key] === v} onClick={() => set({ ...d, [key]: v })} style={{ flex: 1 }}><span className="dot" />{t(k)}</button>
        ))}
      </div>
    </section>
  );
  return (
    <>
      <Heading>{t("dsTitle")}</Heading>
      <p className="lede">{t("dsLede")}</p>
      <section className="p-card">
        <h2 style={{ fontSize: 20 }}>{t("dsText")}</h2>
        <div className="choices" role="radiogroup" aria-label={t("dsText")}>
          {([["n", "dsTextN"], ["l", "dsTextL"], ["x", "dsTextX"]] as const).map(([v, k]) => (
            <button key={v} className="choice" role="radio" aria-checked={d.text === v} onClick={() => set({ ...d, text: v })}><span className="dot" />{t(k)}</button>
          ))}
        </div>
      </section>
      {toggle("dsContrast", "contrast")}
      {toggle("dsCalm", "calm")}
      <p className="muted">{t("dsSpeech")}</p>
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
