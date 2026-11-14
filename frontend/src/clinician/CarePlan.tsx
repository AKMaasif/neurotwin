import { useCallback, useEffect, useState } from "react";
import { api, CareItemClinician, Notice, Suggestion, CarePlanClinician, CarePlanView, ClinicianParticipant, DayPart } from "../api";
import { Key, useT } from "../i18n";
import { ErrorNote, FormError, Status } from "../ui";

const WD = ["wd_0", "wd_1", "wd_2", "wd_3", "wd_4", "wd_5", "wd_6"] as const;
const PARTS: DayPart[] = ["morning", "afternoon", "evening", "anytime"];

/** The routines a clinician sets for one person. Plain text written by the clinician; no model is involved.
 *  What the person marked is shown as self-reported, and a day with no mark is shown as nothing at all. */
export default function CarePlan({ person }: { person: ClinicianParticipant }) {
  const { t } = useT();
  const [data, setData] = useState<CarePlanClinician | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notices, setNotices] = useState<Notice[]>([]);
  const load = useCallback(() => {
    api.carePlan(person.id).then(setData).catch(setError);
    api.notices().then((n) => setNotices(n.filter((x) => !x.read && x.about_id === person.id && x.kind.startsWith("plan_")))).catch(() => {});
  }, [person.id]);
  useEffect(load, [load]);

  return (
    <>
      <div className="d-title">
        <h2>{t("cpTitle")}</h2>
        <div className="meta">{t("cpLede")}</div>
      </div>
      <ErrorNote error={error} />
      {notices.map((n) => (
        <div key={n.id} className="d-card" role="status" style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
          <span>{t(n.kind === "plan_question" ? "noticeQuestion" : n.kind === "plan_accepted" ? "noticeAccepted" : "noticeDeclined", { who: n.about ?? "" })}</span>
          <button className="link" onClick={() => api.readNotice(n.id).then(load)}>{t("noticeMark")}</button>
        </div>
      ))}
      <AddForm pid={person.id} onAdded={load} />
      {data?.plans.length === 0 && <p className="hint">{t("cpNone")}</p>}
      {data?.plans.filter((p) => p.items.length > 0 || p.status !== "draft").map((p) => <Plan key={p.id} plan={p} onChanged={load} />)}
    </>
  );
}

function Plan({ plan, onChanged }: { plan: CarePlanView; onChanged: () => void }) {
  const { t } = useT();
  const [error, setError] = useState<unknown>(null);
  const act = async (f: () => Promise<unknown>) => { setError(null); try { await f(); onChanged(); } catch (e) { setError(e); } };
  const label = plan.status === "draft" ? t("cpDraft") : plan.status === "sent" ? t("cpSent") : plan.status === "accepted" ? t("cpAccepted")
    : plan.status === "declined" ? t("cpDeclined") : t("cpSuperseded");
  const hasActive = plan.items.some((i) => i.status === "active");
  return (
    <section style={{ display: "grid", gap: 8 }} aria-label={t("cpVersion", { n: plan.version })}>
      <div className="d-title">
        <h3>{t("cpVersion", { n: plan.version })} · <Status level={plan.status === "accepted" ? "ok" : plan.status === "declined" ? "warn" : "quiet"}>{label}</Status></h3>
        {plan.legacy && <div className="meta">{t("cpLegacy")}</div>}
      </div>
      <ErrorNote error={error} />
      {plan.status === "draft" && (
        <div className="d-card" style={{ gap: 8 }}>
          <p className="hint">{t("cpSendHint")}</p>
          <button className="btn primary" style={{ justifySelf: "start" }} disabled={!hasActive} onClick={() => act(() => api.sendCarePlan(plan.id))}>{t("cpSend")}</button>
        </div>
      )}
      {plan.status === "sent" && <button className="btn" style={{ justifySelf: "start" }} onClick={() => act(() => api.recallCarePlan(plan.id))}>{t("cpRecall")}</button>}
      {plan.responses.length > 0 && (
        <div className="d-card" style={{ gap: 4 }}>
          <p className="hint" style={{ margin: 0 }}>{t("cpResponses")}</p>
          {plan.responses.map((r, k) => (
            <p key={k} style={{ margin: 0 }}>{t.date(r.at, true)} · <b>{r.response === "question" ? t("cpQuestion") : r.response === "accept" ? t("cpAccept") : t("cpDecline")}</b>{r.note ? `: ${r.note}` : ""}
              {r.reviewed_at ? <span className="hint"> · {t("cpReviewedBy", { who: r.reviewed_by ?? "", date: t.date(r.reviewed_at, true) })}</span>
                : <> · <button className="link" onClick={() => act(() => api.reviewPlanResponse(r.id, ""))}>{t("cpReview")}</button></>}</p>
          ))}
        </div>
      )}
      {plan.items.map((i) => <Item key={i.id} item={i} onChanged={onChanged} />)}
    </section>
  );
}

function AddForm({ pid, onAdded }: { pid: string; onAdded: () => void }) {
  const { t } = useT();
  const [en, setEn] = useState("");
  const [ar, setAr] = useState("");
  const [part, setPart] = useState<DayPart>("morning");
  const [days, setDays] = useState<number[]>([]);
  const [x, setX] = useState({ title: "", time: "", from: "", to: "", start: "", end: "", qty: "", unit: "", prec: "" });
  const setF = (k: keyof typeof x) => (e: { target: { value: string } }) => setX({ ...x, [k]: e.target.value });
  const [sug, setSug] = useState<Suggestion | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const suggest = async () => {
    setError(null);
    try { setSug(await api.suggestFields(pid, en.trim() || null, ar.trim() || null)); } catch (e) { setError(e); }
  };
  const applySug = () => {
    if (!sug) return;
    const f = sug.fields;
    if (f.day_part) setPart(f.day_part);
    setDays(f.weekdays);
    setX({ ...x, time: f.time_hhmm ?? "", qty: f.quantity != null ? String(f.quantity) : "", unit: f.unit ?? "" });
    setSug(null);
  };

  const toggle = (d: number) => setDays(days.includes(d) ? days.filter((x) => x !== d) : [...days, d]);
  const submit = async () => {
    setBusy(true); setError(null);
    try {
      await api.addCareItem(pid, { text_en: en.trim() || null, text_ar: ar.trim() || null, day_part: part, weekdays: days,
        title: x.title.trim() || null, time_hhmm: x.time || null, window_start: x.from || null, window_end: x.to || null,
        start_date: x.start || null, end_date: x.end || null, quantity: x.qty.trim() ? Number(x.qty) : null, unit: x.unit.trim() || null,
        precautions: x.prec.trim() || null });
      setX({ title: "", time: "", from: "", to: "", start: "", end: "", qty: "", unit: "", prec: "" }); setEn(""); setAr(""); setDays([]); onAdded();
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
      <div style={{ display: "grid", gap: 6 }}>
        <button className="btn" style={{ justifySelf: "start" }} disabled={!en.trim() && !ar.trim()} onClick={suggest}>{t("cpSuggest")}</button>
        {sug && (
          <div className="d-card" role="status" style={{ gap: 6 }}>
            <p className="hint" style={{ margin: 0 }}>{t("cpSuggestNote")}</p>
            <p className="mono" style={{ margin: 0 }}>{[sug.fields.day_part, sug.fields.time_hhmm, sug.fields.quantity != null && `${sug.fields.quantity} ${sug.fields.unit}`,
              sug.fields.weekdays.length ? sug.fields.weekdays.map((d) => t(WD[d])).join(" · ") : null].filter(Boolean).join(" · ") || "—"}</p>
            <ul style={{ margin: 0, paddingInlineStart: 18 }}>{sug.flags.map((f, k) => <li key={k}>{t(`cpFlag_${f.code}` as Key)}</li>)}</ul>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={applySug}>{t("cpSuggestApply")}</button>
              <button className="btn" onClick={() => setSug(null)}>{t("cancel")}</button>
            </div>
          </div>
        )}
      </div>
      <details open={x.time !== "" || x.qty !== "" || x.unit !== ""}>
        <summary>{t("cpMore")}</summary>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          <label className="field"><span>{t("cpTitleField")}</span><input className="note" maxLength={120} value={x.title} onChange={setF("title")} /></label>
          <label className="field"><span>{t("cpTime")}</span><input type="time" value={x.time} onChange={setF("time")} /></label>
          <label className="field"><span>{t("cpWindowFrom")}</span><input type="time" value={x.from} onChange={setF("from")} /></label>
          <label className="field"><span>{t("cpWindowTo")}</span><input type="time" value={x.to} onChange={setF("to")} /></label>
          <label className="field"><span>{t("cpStartDate")}</span><input type="date" value={x.start} onChange={setF("start")} /></label>
          <label className="field"><span>{t("cpEndDate")}</span><input type="date" value={x.end} onChange={setF("end")} /></label>
          <label className="field"><span>{t("cpQuantity")}</span><input inputMode="decimal" value={x.qty} onChange={setF("qty")} /></label>
          <label className="field"><span>{t("cpUnit")}</span><input maxLength={20} value={x.unit} onChange={setF("unit")} /></label>
          <p className="hint">{t("cpUnitHint")}</p>
          <label className="field"><span>{t("cpPrecautions")}</span><input className="note" maxLength={300} value={x.prec} onChange={setF("prec")} /></label>
        </div>
      </details>
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
      {(item.title || item.time_hhmm || item.window_start || item.quantity != null || item.start_date || item.end_date || item.precautions) && (
        <p className="hint" style={{ margin: 0 }}>
          {[item.title, item.time_hhmm, item.window_start && `${item.window_start}–${item.window_end}`, item.quantity != null && `${item.quantity} ${item.unit}`,
            item.start_date && `${t("cpStartDate")} ${item.start_date}`, item.end_date && `${t("cpEndDate")} ${item.end_date}`, item.precautions].filter(Boolean).join(" · ")}
        </p>
      )}
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

      {item.difficulty.length > 0 && (
        <p className="hint">{t("cpDifficulty")}: {item.difficulty.map((d) => `${d.day.slice(5)} · ${t(`cpDiff_${d.reason}` as Key)}`).join(", ")}</p>
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
