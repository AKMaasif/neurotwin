import { useState } from "react";
import { Activity, ChevronDown, ChevronUp } from "lucide-react";
import { ClinicianParticipant, User } from "../api";
import { useT } from "../i18n";
import type { Data, Sel } from "./ClinicianApp";
import { valueText } from "./EvidenceTable";

type Step = { lane: 0 | 1 | 2 | 3; title: string; sub: string; tone?: "warn" | "fail" | "ok" | "navy"; at: string; order: number };

/** The activity panel. Workings draws, for the selected session, each step that produced what the clinician sees:
 *  who started it, what was recorded, what the rules found, what was flagged and what a person decided. It reads only
 *  stored records: it never fills a gap or describes reasoning it does not have. */
export default function Dock({ data, sel, open, setOpen }: {
  data: Data | null; sel: Sel; open: boolean; setOpen: (v: boolean) => void; people: ClinicianParticipant[] | null; user: User;
}) {
  const { t } = useT();
  const [view, setView] = useState<"workings" | "steps">("workings");

  return (
    <>
      <div className="dock-head">
        <span className="pane-title"><Activity size={16} aria-hidden="true" />{t("wsActivity")}</span>
        <div className="seg" style={{ width: 240 }} role="group">
          <button aria-pressed={view === "workings"} onClick={() => { setView("workings"); setOpen(true); }}>{t("wsWorkings")}</button>
          <button aria-pressed={view === "steps"} onClick={() => { setView("steps"); setOpen(true); }}>{t("wsSteps")}</button>
        </div>
        <span style={{ flex: 1 }} />
        <button className="ibtn" aria-label={open ? t("wsCollapse") : t("wsExpand")} title={open ? t("wsCollapse") : t("wsExpand")} onClick={() => setOpen(!open)}>
          {open ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
        </button>
      </div>
      {open && (
        <div className="dock-body">
          {!data ? <p className="wk-lede">{t("wsLoading")}</p> : view === "workings" ? <Workings data={data} sel={sel} /> : <AccessLog data={data} />}
        </div>
      )}
    </>
  );
}

function Workings({ data, sel }: { data: Data; sel: Sel }) {
  const { t } = useT();
  const sessionId = sel?.kind === "session" ? sel.id : sel?.kind === "record" ? data.evidence.find((e) => e.id === sel.id)?.session_id : null;
  const s = data.sessions.find((x) => x.id === sessionId);
  if (!s) return <p className="wk-lede">{t("wsWorkingsPick")}</p>;

  const records = data.evidence.filter((e) => e.session_id === s.id);
  const items = data.items.filter((i) => i.session_id === s.id);
  const steps: Step[] = [];
  let n = 0;
  const flags = [s.assisted && t("wsMarkAssisted"), s.unwell_today && t("wsMarkUnwell"), s.interruptions && t("wsMarkInterrupted")].filter(Boolean).join(" · ");
  steps.push({ lane: 0, title: t("wsStepStarted"), sub: `${t.code(s.protocol_code)} ${s.protocol_version}${flags ? " · " + flags : ""}`, at: s.started_at, order: n++ });
  for (const e of records) {
    steps.push({ lane: e.producer_type === "person" ? 0 : 1, title: `${t("wsStepRecorded")}: ${t.code(e.measure)}`,
      sub: valueText(e, t) ?? `${t("missing")} · ${t.code(e.missing_reason)}`, at: e.recorded_at, order: n++ });
  }
  if (records.length) {
    const c = { usable: 0, doubtful: 0, unusable: 0 };
    records.forEach((e) => { c[e.quality] += 1; });
    const worst = c.unusable ? "fail" : c.doubtful ? "warn" : "ok";
    const parts = (["usable", "doubtful", "unusable"] as const).filter((k) => c[k]).map((k) => `${t.num(c[k])} ${t(`quality_${k}`)}`);
    const reasons = [...new Set(records.flatMap((e) => e.quality_reasons))].map((r) => t.code(r));
    steps.push({ lane: 2, title: t("wsStepVerdict"), sub: reasons.length ? `${parts.join(" · ")} — ${reasons.join(", ")}` : `${parts.join(" · ")} · ${t("wsStepNoConcerns")}`,
      tone: worst, at: records[records.length - 1].recorded_at, order: n++ });
  }
  for (const i of items) steps.push({ lane: 2, title: t("wsStepRaised"), sub: t.code(i.reason), tone: "warn", at: i.created_at, order: n++ });
  for (const i of items.filter((x) => x.status !== "open")) {
    steps.push({ lane: 3, title: `${t("wsStepDecided")}: ${i.decision ? t(`wsDecided_${i.decision}`) : t("wsReviewed")}`,
      sub: `${i.resolved_by ?? ""} · ${i.resolution_note ?? ""}`, tone: i.decision === "exclude" ? "fail" : "navy", at: i.resolved_at ?? i.created_at, order: n++ });
  }
  for (const e of records.filter((x) => x.status === "withdrawn" && !x.change_reason?.startsWith("Excluded in review"))) {
    const who = data.audit.find((a) => a.action === "evidence.withdrawn" && a.target === `evidence:${e.id}`);
    steps.push({ lane: who && who.actor_id === e.participant_id ? 0 : 3, title: `${t("wsStepWithdrawn")}: ${t.code(e.measure)}`,
      sub: `${who?.actor_id ?? ""} · ${e.change_reason ?? ""}`, tone: "fail", at: who?.at ?? e.recorded_at, order: n++ });
  }
  steps.sort((a, b) => a.at.localeCompare(b.at) || a.order - b.order);
  const lanes = [t("wsLanePerson"), t("wsLaneDevice"), t("wsLaneRules"), t("wsLaneClinician")];

  return (
    <>
      <p className="wk-lede">{t("wsWorkingsLede")}</p>
      <div className="wk">
        <div className="wk-lanes">{lanes.map((l) => <div key={l} className="wk-lane">{l}</div>)}</div>
        {steps.map((st, i) => (
          <div key={i} className="wk-col" aria-label={t.date(st.at, true)}>
            <div className={`wk-step ${st.tone ?? ""}`} style={{ gridRow: st.lane + 1 }} title={`${st.title} — ${st.sub} — ${t.date(st.at, true)}`}>
              <b>{st.title}</b>
              <span>{st.sub}</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function AccessLog({ data }: { data: Data }) {
  const { t } = useT();
  return (
    <div style={{ padding: "8px 14px" }}>
      <p className="hint" style={{ marginBottom: 6 }}>{t("auditLede")}</p>
      <table className="data">
        <thead><tr><th>{t("colRecorded")}</th><th>{t("dProducer")}</th><th>{t("colStatus")}</th><th></th></tr></thead>
        <tbody>
          {data.audit.map((a) => (
            <tr key={a.id}>
              <td className="mono" style={{ whiteSpace: "nowrap" }}>{t.date(a.at, true)}</td>
              <td>{a.actor_id}</td>
              <td>{t.code(a.action)}</td>
              <td className="mono muted">{a.target}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
