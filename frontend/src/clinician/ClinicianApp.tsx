import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Activity, LineChart, PanelRight, Users } from "lucide-react";
import { api, AuditRow, ChangeResult, ClinicianParticipant, Evidence, ReviewItem, Session, User } from "../api";
import { useT } from "../i18n";
import { ErrorNote } from "../ui";
import Caseload from "./Caseload";
import Stage from "./Stage";
import Detail from "./Detail";
import Dock from "./Dock";
import ReportView from "./Report";
const BrainAnalytics = lazy(() => import("../imaging/BrainAnalytics"));

export type Sel = { kind: "record"; id: number } | { kind: "session"; id: number } | null;
export type Data = { sessions: Session[]; evidence: Evidence[]; items: ReviewItem[]; audit: AuditRow[]; changes: ChangeResult[] };
type Pane = "left" | "stage" | "right" | "dock";

const narrowQuery = "(max-width: 1100px)";
const isNarrow = () => typeof window !== "undefined" && window.matchMedia?.(narrowQuery).matches;

/** The clinician workspace: caseload on one side, the person's timeline in the middle, the selected record's detail on
 *  the other side, and an activity panel underneath showing how the selected session came to be. */
export default function ClinicianApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const { t } = useT();
  const [people, setPeople] = useState<ClinicianParticipant[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [data, setData] = useState<Data | null>(null);
  const [sel, setSel] = useState<Sel>(null);
  const [leftTab, setLeftTab] = useState<"people" | "check" | "concerns">("people");
  const [dockOpen, setDockOpen] = useState(true);
  const [pane, setPane] = useState<Pane>("left");
  const [report, setReport] = useState(false);
  const [withDoubtful, setWithDoubtful] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [imaging, setImaging] = useState(false);

  const loadPeople = useCallback(async () => {
    try {
      const p = await api.clinicianParticipants();
      setPeople(p);
      setPid((cur) => cur ?? p.find((x) => x.open_items > 0)?.id ?? p[0]?.id ?? null);
    } catch (e) { setError(e); }
  }, []);
  useEffect(() => { loadPeople(); }, [loadPeople]);

  const loadData = useCallback(async (id: string, doubtful: boolean) => {
    setError(null);
    try {
      const [sessions, evidence, items, changes] = await Promise.all([
        api.sessions(id), api.evidence(id), api.reviewItems(id, "all"), api.change(id, doubtful)]);
      const audit = await api.audit(id);   // after the others, so it includes this view
      setData({ sessions, evidence, items, audit, changes });
    } catch (e) { setError(e); }
  }, []);
  useEffect(() => { if (pid) { setData(null); setSel(null); loadData(pid, withDoubtful); } }, [pid, loadData]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (pid) loadData(pid, withDoubtful); }, [withDoubtful]);  // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(() => { if (pid) loadData(pid, withDoubtful); loadPeople(); }, [pid, withDoubtful, loadData, loadPeople]);

  const select = useCallback((s: Sel) => {
    setSel(s);
    if (s && isNarrow()) setPane("right");
  }, []);

  const openItems = useMemo(() => (data?.items ?? []).filter((i) => i.status === "open"), [data]);

  // Keys: J/K walk the open items, Esc clears, W toggles the activity panel. Ignored while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (imaging || tag === "INPUT" || tag === "TEXTAREA" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "Escape") { setSel(null); setReport(false); }
      else if (e.key === "w" || e.key === "W") setDockOpen((v) => !v);
      else if ((e.key === "j" || e.key === "k") && openItems.length) {
        const withRecord = openItems.filter((i) => i.evidence_id);
        const cur = sel?.kind === "record" ? withRecord.findIndex((i) => i.evidence_id === sel.id) : -1;
        const next = e.key === "j" ? (cur + 1) % withRecord.length : (cur - 1 + withRecord.length) % withRecord.length;
        const target = withRecord[next];
        if (target?.evidence_id) { setLeftTab("check"); select({ kind: "record", id: target.evidence_id }); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openItems, sel, select, imaging]);

  const person = people?.find((p) => p.id === pid) ?? null;

  if (imaging) return <Suspense fallback={<p role="status">Opening Brain Analytics…</p>}><BrainAnalytics onClose={() => { setPane("stage"); setImaging(false); }} /></Suspense>;

  return (
    <div className="ws" data-pane={pane}>
      <aside className="ws-left" aria-label={t("wsCaseload")}>
        <Caseload
          user={user} people={people} person={person} onPerson={(id) => { setPid(id); setPane("stage"); }}
          data={data} sel={sel} onSelect={select} tab={leftTab} setTab={setLeftTab} onChanged={refresh}
        />
      </aside>
      <section className="ws-stage" aria-label={t("wsTimeline")}>
        <Stage
          user={user} person={person} data={data} sel={sel} onSelect={select} onSignOut={onSignOut}
          onReport={() => setReport(true)} error={error} onRetry={refresh}
          withDoubtful={withDoubtful} setWithDoubtful={setWithDoubtful}
          onImaging={() => setImaging(true)}
        />
      </section>
      <aside className="ws-right" aria-label={t("wsInspector")}>
        <Detail person={person} data={data} sel={sel} onSelect={select} onChanged={refresh} />
      </aside>
      <section className="ws-dock" aria-label={t("wsActivity")}>
        <Dock data={data} sel={sel} open={dockOpen || pane === "dock"} setOpen={setDockOpen} people={people} user={user} />
      </section>
      <nav className="ws-mobilenav" aria-label={t("wsMenu")}>
        {([["left", Users, t("wsCaseload")], ["stage", LineChart, t("wsTimeline")], ["right", PanelRight, t("wsInspector")],
          ["dock", Activity, t("wsActivity")]] as const).map(([k, Icon, label]) => (
          <button key={k} aria-current={pane === k} onClick={() => setPane(k)}><Icon size={20} aria-hidden="true" />{label}</button>
        ))}
      </nav>
      {report && person && <ReportView personId={person.id} onClose={() => setReport(false)} />}
      {!people && error ? <div style={{ position: "fixed", bottom: 16, insetInlineStart: 16 }}><ErrorNote error={error} onRetry={refresh} /></div> : null}
    </div>
  );
}
