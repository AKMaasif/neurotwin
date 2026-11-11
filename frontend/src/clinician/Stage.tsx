import { useEffect, useRef, useState } from "react";
import { Brain, CircleDashed, FileText, LineChart, Menu, Table2, X } from "lucide-react";
import { api, ClinicianParticipant, Evidence, User } from "../api";
import { useT } from "../i18n";
import { ErrorNote } from "../ui";
import type { Data, Sel } from "./ClinicianApp";
import EvidenceTable from "./EvidenceTable";
import Account from "../Account";
import Timeline from "./Timeline";

export default function Stage({ user, person, data, sel, onSelect, onSignOut, onReport, error, onRetry, withDoubtful, setWithDoubtful, onImaging }: {
  user: User; person: ClinicianParticipant | null; data: Data | null; sel: Sel; onSelect: (s: Sel) => void;
  onSignOut: () => void; onReport: () => void; error: unknown; onRetry: () => void;
  withDoubtful: boolean; setWithDoubtful: (v: boolean) => void;
  onImaging: () => void;
}) {
  const { t, setLang } = useT();
  const [mode, setMode] = useState<"timeline" | "table">("timeline");
  const [history, setHistory] = useState(false);
  const [withHistory, setWithHistory] = useState<Evidence[] | null>(null);
  const [menu, setMenu] = useState(false);
  const [account, setAccount] = useState(false);
  // Corrected (superseded) versions are fetched only when asked for.
  useEffect(() => {
    setWithHistory(null);
    if (history && person) api.evidence(person.id, true).then(setWithHistory).catch(() => setWithHistory(null));
  }, [history, person, data]);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false); };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [menu]);

  const record = sel?.kind === "record" ? data?.evidence.find((e) => e.id === sel.id) : undefined;
  const session = sel?.kind === "session" ? data?.sessions.find((s) => s.id === sel.id) : undefined;
  const done = data?.sessions.filter((s) => s.status !== "in_progress") ?? [];
  const sorted = [...done].sort((a, b) => a.started_at.localeCompare(b.started_at));

  return (
    <>
      <div className="rail" role="toolbar" aria-label={t("wsTimeline")}>
        <div className="rail-group">
          <button className="ibtn" aria-pressed={mode === "timeline"} title={t("wsTimeline")} aria-label={t("wsTimeline")} onClick={() => setMode("timeline")}><LineChart size={18} /></button>
          <button className="ibtn" aria-pressed={mode === "table"} title={t("wsTable")} aria-label={t("wsTable")} onClick={() => setMode("table")}><Table2 size={18} /></button>
        </div>
        <div className="rail-group">
          <button className="ibtn" aria-pressed={withDoubtful} title={t("chIncludeDoubtful")} aria-label={t("chIncludeDoubtful")}
            onClick={() => setWithDoubtful(!withDoubtful)}><CircleDashed size={18} /></button>
        </div>
        <div className="rail-group">
          <button className="ibtn" title={t("wsReport")} aria-label={t("wsReport")} disabled={!person} onClick={onReport}><FileText size={18} /></button>
        </div>
      </div>

      <div className="stage-top">
        <div className="pill" aria-live="polite">
          {!person ? <span className="t muted">{t("cSelect")}</span>
            : !data ? <span className="t muted">{t("wsLoading")}</span>
            : record ? (
              <>
                <span className={`tag ${record.kind}`}>{t(`kind_${record.kind}`)}</span>
                <span className="t"><b>#{record.id} {t.code(record.measure)}</b> <span className="muted">· {t.date(record.recorded_at)}</span></span>
                <button className="ibtn" aria-label={t("close")} onClick={() => onSelect(null)}><X size={16} /></button>
              </>
            ) : session ? (
              <>
                <span className="t"><b>{t("wsSession")} #{session.id} · {t.code(session.protocol_code)}</b> <span className="muted">· {t.date(session.started_at)}</span></span>
                <button className="ibtn" aria-label={t("close")} onClick={() => onSelect(null)}><X size={16} /></button>
              </>
            ) : (
              <span className="t">
                <b><bdi>{person.display_name}</bdi></b>{" "}
                <span className="muted">· {sorted.length ? t("wsSummary", { s: t.num(sorted.length), from: t.date(sorted[0].started_at), to: t.date(sorted[sorted.length - 1].started_at) }) : t("wsNoSessions")}</span>
                {person.is_demo && <> <span className="tag demo">{t("cDemo")}</span></>}
              </span>
            )}
        </div>
        <div className="stage-actions">
          <button className="btn" onClick={onImaging}><Brain size={16} aria-hidden="true" />{t.lang === "ar" ? "تحليل صور الدماغ" : "Brain Analytics"}</button>
          <button className="btn primary" disabled={!person} onClick={onReport}><FileText size={16} aria-hidden="true" />{t("wsReport")}</button>
          <div style={{ position: "relative" }} ref={menuRef}>
            <button className="btn" aria-label={t("wsMenu")} aria-expanded={menu} onClick={() => setMenu((v) => !v)}><Menu size={18} /></button>
            {menu && (
              <div className="menu" role="menu">
                <small>{user.display_name} · {t("roleClinician")}</small>
                <button role="menuitem" lang={t.lang === "en" ? "ar" : "en"} onClick={() => { setLang(t.lang === "en" ? "ar" : "en"); setMenu(false); }}>{t("switchTo")}</button>
                <div className="sep" />
                <small>{t("cScopeNote")}</small>
                <small>{t("wsKeys")}</small>
                {!user.is_demo && <button role="menuitem" onClick={() => { setAccount(true); setMenu(false); }}>{t("acLink")}</button>}
                <div className="sep" />
                <button role="menuitem" onClick={onSignOut}>{t("signOut")}</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {account && (
        <div className="modal-scrim" onClick={() => setAccount(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="acc-h" onClick={(e) => e.stopPropagation()}>
            <div className="bar"><h1 id="acc-h">{t("acTitle")}</h1><button className="btn" onClick={() => setAccount(false)}>{t("close")}</button></div>
            <Account user={user} />
          </div>
        </div>
      )}
      <div className="canvas">
        <ErrorNote error={error} onRetry={onRetry} />
        {data && (mode === "timeline"
          ? <Timeline data={data} sel={sel} onSelect={onSelect} />
          : <EvidenceTable evidence={history && withHistory ? withHistory : data.evidence} history={history} setHistory={setHistory}
              onOpen={(id) => onSelect({ kind: "record", id })} />)}
      </div>
    </>
  );
}
