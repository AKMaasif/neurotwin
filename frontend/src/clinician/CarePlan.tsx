import { useCallback, useEffect, useState } from "react";
import { api, CareItemClinician, ClinicianParticipant, DayPart } from "../api";
import { useT } from "../i18n";
import { ErrorNote, FormError, Status } from "../ui";

const WD = ["wd_0", "wd_1", "wd_2", "wd_3", "wd_4", "wd_5", "wd_6"] as const;
const PARTS: DayPart[] = ["morning", "afternoon", "evening", "anytime"];

/** The routines a clinician sets for one person. Plain text written by the clinician; no model is involved.
 *  What the person marked is shown as self-reported, and a day with no mark is shown as nothing at all. */
export default function CarePlan({ person }: { person: ClinicianParticipant }) {
  const { t } = useT();
  const [items, setItems] = useState<CareItemClinician[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => { api.carePlan(person.id).then(setItems).catch(setError); }, [person.id]);
  useEffect(load, [load]);

  return (
    <>
      <div className="d-title">
        <h2>{t("cpTitle")}</h2>
        <div className="meta">{t("cpLede")}</div>
      </div>
      <ErrorNote error={error} />
      <AddForm pid={person.id} onAdded={load} />
      {items?.length === 0 && <p className="hint">{t("cpNone")}</p>}
      {items?.map((i) => <Item key={i.id} item={i} onChanged={load} />)}
    </>
  );
}

function AddForm({ pid, onAdded }: { pid: string; onAdded: () => void }) {
  const { t } = useT();
  const [en, setEn] = useState("");
  const [ar, setAr] = useState("");
  const [part, setPart] = useState<DayPart>("morning");
  const [days, setDays] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const toggle = (d: number) => setDays(days.includes(d) ? days.filter((x) => x !== d) : [...days, d]);
  const submit = async () => {
    setBusy(true); setError(null);
    try {
      await api.addCareItem(pid, { text_en: en.trim() || null, text_ar: ar.trim() || null, day_part: part, weekdays: days });
      setEn(""); setAr(""); setDays([]); onAdded();
    } catch (e) { setError(e); }
    setBusy(false);
  };

  return (
    <div className="d-card" style={{ gap: 10 }}>
      <label className="field"><span>{t("cpTextEn")}</span>
        <textarea className="note" dir="ltr" lang="en" value={en} maxLength={300} onChange={(e) => setEn(e.target.value)} /></label>
      <label className="field"><span>{t("cpTextAr")}</span>
        <textarea className="note" dir="rtl" lang="ar" value={ar} maxLength={300} onChange={(e) => setAr(e.target.value)} /></label>
      <p className="hint">{t("cpTextHint")}</p>
      <label className="field"><span>{t("cpWhen")}</span>
        <select value={part} onChange={(e) => setPart(e.target.value as DayPart)}>
          {PARTS.map((p) => <option key={p} value={p}>{t(`dayPart_${p}`)}</option>)}
        </select></label>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="hint">{t("cpDays")} · {days.length === 0 ? t("cpEveryDay") : ""}</legend>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[0, 1, 2, 3, 4, 5, 6].map((d) => (
            <label key={d} className="tag" style={{ cursor: "pointer" }}>
              <input type="checkbox" checked={days.includes(d)} onChange={() => toggle(d)} /> {t(WD[d])}
            </label>
          ))}
        </div>
      </fieldset>
      <FormError error={error} />
      <button className="btn primary" disabled={busy || (!en.trim() && !ar.trim())} onClick={submit}>{t("cpAdd")}</button>
    </div>
  );
}

function Item({ item, onChanged }: { item: CareItemClinician; onChanged: () => void }) {
  const { t } = useT();
  const [stopping, setStopping] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const active = item.status === "active";

  const stop = async () => {
    setError(null);
    try { await api.stopCareItem(item.id, note); onChanged(); } catch (e) { setError(e); }
  };

  return (
    <div className="d-card" style={{ gap: 8, opacity: active ? 1 : 0.7 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <Status level={active ? "ok" : "quiet"}>{active ? t(`dayPart_${item.day_part}`) : t("cpStopped")}</Status>
        <span className="muted" style={{ fontSize: 12 }}>
          {item.weekdays.length ? item.weekdays.map((d) => t(WD[d])).join(" · ") : t("cpEveryDay")}
        </span>
      </div>
      {item.text_en && <p dir="ltr" lang="en" style={{ margin: 0 }}>{item.text_en}</p>}
      {item.text_ar && <p dir="rtl" lang="ar" style={{ margin: 0 }}>{item.text_ar}</p>}
      <p className="hint">{t("cpWrittenBy", { who: item.written_by ?? "—" })} · {t.date(item.created_at)}
        {item.stop_note ? ` · ${item.stop_note}` : ""}</p>

      <p className="hint" style={{ marginBottom: 0 }}>{t("cpMarked")}</p>
      {item.marked.length === 0 ? <p className="hint">{t("cpMarkedNone")}</p> : (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {item.marked.map((m) => (
            <span key={m.day} className="tag mono">{m.day.slice(5)} · {m.reply === "done" ? t("cpDone") : t("cpNotToday")}</span>
          ))}
        </div>
      )}

      {active && !stopping && <button className="link" style={{ justifySelf: "start" }} onClick={() => setStopping(true)}>{t("cpStop")}</button>}
      {active && stopping && (
        <>
          <input className="note" value={note} maxLength={300} placeholder={t("cpStopNote")} onChange={(e) => setNote(e.target.value)} />
          <ErrorNote error={error} />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn danger" onClick={stop}>{t("cpStop")}</button>
            <button className="btn" onClick={() => setStopping(false)}>{t("cancel")}</button>
          </div>
        </>
      )}
    </div>
  );
}
