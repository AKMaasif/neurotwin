import { useMemo, useState } from "react";
import { ClipboardCheck, Search } from "lucide-react";
import { ClinicianParticipant, ReviewItem, User } from "../api";
import { useT } from "../i18n";
import { Mark } from "../ui";
import type { Data, Sel } from "./ClinicianApp";
import Decide from "./Decide";

const SESSION_LEVEL = new Set(["interrupted_session", "abandoned_session", "missing_required", "unknown_protocol"]);
const initials = (name: string) => name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

export default function Caseload({ people, person, onPerson, data, sel, onSelect, tab, setTab, onChanged }: {
  user: User; people: ClinicianParticipant[] | null; person: ClinicianParticipant | null; onPerson: (id: string) => void;
  data: Data | null; sel: Sel; onSelect: (s: Sel) => void; tab: "people" | "check"; setTab: (t: "people" | "check") => void;
  onChanged: () => void;
}) {
  const { t } = useT();
  const open = useMemo(() => (data?.items ?? []).filter((i) => i.status === "open"), [data]);

  return (
    <>
      <div className="pane-head">
        <span className="pane-title"><Mark size={22} />{t("wsCaseload")}</span>
      </div>
      <div className="subtabs" role="tablist">
        <button role="tab" className="subtab" aria-selected={tab === "people"} onClick={() => setTab("people")}>
          {t("wsPeople")} {people && <span className="badge">{t.num(people.length)}</span>}
        </button>
        <button role="tab" className="subtab" aria-selected={tab === "check"} onClick={() => setTab("check")}>
          {t("tabCheck")} {open.length > 0 && <span className="badge warn">{t.num(open.length)}</span>}
        </button>
      </div>
      {tab === "people"
        ? <People people={people} person={person} onPerson={onPerson} goCheck={(id) => { onPerson(id); setTab("check"); }} />
        : <Queue person={person} items={open} data={data} sel={sel} onSelect={onSelect} onChanged={onChanged} />}
    </>
  );
}

function People({ people, person, onPerson, goCheck }: {
  people: ClinicianParticipant[] | null; person: ClinicianParticipant | null; onPerson: (id: string) => void;
  goCheck: (id: string) => void;
}) {
  const { t } = useT();
  const [q, setQ] = useState("");
  if (!people) return <div className="pane-body"><p className="muted">{t("loading")}</p></div>;
  const totalOpen = people.reduce((n, p) => n + p.open_items, 0);
  const shown = people.filter((p) => p.display_name.toLowerCase().includes(q.trim().toLowerCase()));
  const groups = [
    { key: "needs", label: t("wsNeedsReview"), rows: shown.filter((p) => p.open_items > 0) },
    { key: "ok", label: t("wsUpToDate"), rows: shown.filter((p) => p.open_items === 0) },
  ];
  const first = people.find((p) => p.open_items > 0);

  return (
    <div className="pane-body">
      <div className="pane-meta">
        <b>{t("wsCaseload")}</b>
        <span>{t("wsCaseloadMeta", { n: t.num(people.length) })}</span>
      </div>
      <div className="lead-card">
        <div className="row1">
          <span className="ico"><ClipboardCheck size={18} aria-hidden="true" /></span>
          <div>
            <b>{t("wsReview")}</b><span className="step">{t("wsStep1")}</span>
            <div className="sub">{t("wsReviewSub")}</div>
          </div>
        </div>
        <button className="btn primary" disabled={!first} onClick={() => first && goCheck(first.id)}>
          {first ? t("wsReviewAll", { n: t.num(totalOpen) }) : t("wsReviewNone")}
        </button>
      </div>
      <label className="search">
        <Search size={16} aria-hidden="true" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("wsFilter")} aria-label={t("wsFilter")} />
      </label>
      {people.length === 0 && <p className="muted">{t("cNoParticipants")}</p>}
      {people.length > 0 && shown.length === 0 && <p className="muted">{t("wsNoMatch")}</p>}
      {groups.filter((g) => g.rows.length).map((g) => (
        <div key={g.key} style={{ display: "grid", gap: 2 }}>
          <div className="group-h"><span>{g.label}</span><span className="n">{t.num(g.rows.length)}</span></div>
          {g.rows.map((p) => (
            <button key={p.id} className="list-row" aria-current={person?.id === p.id} onClick={() => onPerson(p.id)}>
              <span className="tile" aria-hidden="true">{initials(p.display_name)}</span>
              <span className="main">
                <b><bdi>{p.display_name}</bdi></b>
                <span>{p.last_activity ? t("cLastActivity", { date: t.date(p.last_activity) }) : t("wsNoSessions")}</span>
              </span>
              <span className="end">
                <span className={`dot ${p.open_items ? "warn" : "ok"}`} aria-hidden="true" />
                {p.open_items ? t("cOpenItems", { n: t.num(p.open_items) }) : t("cNoOpen")}
              </span>
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

function Queue({ person, items, data, sel, onSelect, onChanged }: {
  person: ClinicianParticipant | null; items: ReviewItem[]; data: Data | null; sel: Sel; onSelect: (s: Sel) => void;
  onChanged: () => void;
}) {
  const { t } = useT();
  const [checked, setChecked] = useState<Set<number>>(new Set());
  if (!person) return <div className="pane-body"><p className="muted">{t("cSelect")}</p></div>;
  if (!data) return <div className="pane-body"><p className="muted">{t("wsLoading")}</p></div>;

  const byReason = new Map<string, ReviewItem[]>();
  for (const i of items) byReason.set(i.reason, [...(byReason.get(i.reason) ?? []), i]);
  const toggle = (ids: number[], on: boolean) => {
    const next = new Set(checked);
    ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
    setChecked(next);
  };
  const live = [...checked].filter((id) => items.some((i) => i.id === id));
  const record = (i: ReviewItem) => data.evidence.find((e) => e.id === i.evidence_id);

  return (
    <div className="pane-body">
      <div className="pane-meta">
        <b><bdi>{person.display_name}</bdi></b>
        <span>{items.length ? t("cOpenItems", { n: t.num(items.length) }) : t("checkNone")}</span>
      </div>
      {[...byReason.entries()].map(([reason, group]) => {
        const all = group.every((i) => checked.has(i.id));
        return (
          <div key={reason} style={{ display: "grid", gap: 2 }}>
            <div className="group-h">
              <label>
                <input type="checkbox" checked={all} aria-label={t("wsSelectGroup")}
                  onChange={(e) => toggle(group.map((i) => i.id), e.target.checked)} />
                {t.code(reason)}
              </label>
              <span className="n">{t.num(group.length)}</span>
            </div>
            {group.map((i) => {
              const r = record(i);
              const current = sel?.kind === "record" && sel.id === i.evidence_id;
              return (
                <div key={i.id} className="list-row qrow" aria-current={current}
                  onClick={() => i.evidence_id && onSelect({ kind: "record", id: i.evidence_id })}>
                  <input type="checkbox" checked={checked.has(i.id)} onClick={(e) => e.stopPropagation()}
                    onChange={(e) => toggle([i.id], e.target.checked)} aria-label={`#${i.id}`} />
                  <span className="dot warn" aria-hidden="true" />
                  <span className="main">
                    <b>{r ? t.code(r.measure) : t.code(reason)}</b>
                    <span>{r ? `${t.code(r.protocol_code)} · ${t.date(r.recorded_at)}` : t.date(i.created_at)}</span>
                  </span>
                  <span className="end">#{i.id}</span>
                </div>
              );
            })}
          </div>
        );
      })}
      {live.length > 0 && (
        <div className="bulk">
          <div className="row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <b>{t("wsSelected", { n: t.num(live.length) })}</b>
            <button className="link" onClick={() => setChecked(new Set())}>{t("wsClearSel")}</button>
          </div>
          <Decide ids={live} compact sessionWide={items.some((i) => live.includes(i.id) && SESSION_LEVEL.has(i.reason))}
            onDone={() => { setChecked(new Set()); onChanged(); }} />
        </div>
      )}
    </div>
  );
}
