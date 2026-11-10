import { useEffect, useRef, useState } from "react";
import { Evidence, Session } from "../api";
import { useT } from "../i18n";
import type { Data, Sel } from "./ClinicianApp";

type Lane = { key: string; measure: string; label: string; height: number; fixed?: [number, number]; unit: string };

const LABEL_W = 210, PAD_R = 28, AXIS_H = 30, SES_H = 64, GAP = 14;
const DAY = 864e5;

/** One person, over time, one lane per measure. Only records from the same activity version share a lane, unusable
 *  and withdrawn records sit on the lane's floor as crosses (counted, not plotted), and nothing is fitted or averaged. */
export default function Timeline({ data, sel, onSelect }: { data: Data; sel: Sel; onSelect: (s: Sel) => void }) {
  const { t } = useT();
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(560, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const sessions = data.sessions.filter((s) => s.status !== "in_progress");
  if (sessions.length === 0) return <div ref={ref} className="sheet"><p className="empty">{t("wsNoSessions")}</p></div>;

  const lanes: Lane[] = [
    { key: "rt", measure: "rt_median_ms", label: t("wsLaneRt"), height: 150, unit: "ms" },
    { key: "sleep", measure: "sleep_hours", label: t("wsLaneSleep"), height: 96, fixed: [0, 12], unit: "h" },
    { key: "sq", measure: "sleep_quality", label: t("wsLaneSq"), height: 96, fixed: [1, 5], unit: "" },
  ];
  const times = sessions.map((s) => Date.parse(s.started_at));
  const t0 = Math.min(...times) - DAY, t1 = Math.max(...times) + DAY;
  const x = (iso: string) => LABEL_W + ((Date.parse(iso) - t0) / (t1 - t0)) * (width - LABEL_W - PAD_R);
  const weeks: number[] = [];
  for (let d = t0 + DAY; d <= t1; d += 7 * DAY) weeks.push(d);

  let y = AXIS_H;
  const sesY = y; y += SES_H + GAP;
  const laneY = lanes.map((l) => { const top = y; y += l.height + GAP; return top; });
  const H = y + 4;

  const openBySession = new Set(data.items.filter((i) => i.status === "open").map((i) => i.session_id));
  const selRecord = sel?.kind === "record" ? data.evidence.find((e) => e.id === sel.id) : undefined;
  const selSession = sel?.kind === "session" ? sel.id : selRecord?.session_id ?? null;
  const key = (fn: () => void) => (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); } };

  const sessionColour = (s: Session) =>
    s.status === "completed" ? "var(--navy)" : s.status === "interrupted" ? "var(--warn)" : "var(--fail)";

  return (
    <div ref={ref} className="sheet">
      <svg className="timeline" width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="group" aria-label={t("wsTimeline")} style={{ direction: "ltr", display: "block" }}>
        {weeks.map((d) => (
          <g key={d}>
            <line x1={x(new Date(d).toISOString())} x2={x(new Date(d).toISOString())} y1={AXIS_H - 6} y2={H - 4} stroke="var(--line-soft)" />
            <text x={x(new Date(d).toISOString())} y={AXIS_H - 12} textAnchor="middle">{t.date(new Date(d).toISOString()).replace(/\s?\d{4}$/, "")}</text>
          </g>
        ))}

        {/* Sessions lane: one row per activity */}
        <text className="lane-label" x={12} y={sesY + 14}>{t("wsLaneSessions")}</text>
        <text x={12} y={sesY + 32}>{t.code("reaction_time")}</text>
        <text x={12} y={sesY + 52}>{t.code("daily_checkin")}</text>
        <line x1={LABEL_W} x2={width - PAD_R} y1={sesY + SES_H} y2={sesY + SES_H} stroke="var(--line)" />
        {sessions.map((s) => {
          const cx = x(s.started_at), cy = sesY + (s.protocol_code === "reaction_time" ? 28 : 48);
          const isSel = selSession === s.id;
          const flags = [s.assisted && "A", s.unwell_today && "U"].filter(Boolean).join(" ");
          const label = `${t.code(s.protocol_code)} · ${t.date(s.started_at)} · ${t(`sessionStatus_${s.status}` as "sessionStatus_completed")}`;
          return (
            <g key={s.id} className={`pt ${isSel ? "sel" : ""}`} tabIndex={0} role="button" aria-label={label}
              onClick={() => onSelect({ kind: "session", id: s.id })} onKeyDown={key(() => onSelect({ kind: "session", id: s.id }))}>
              <title>{label}</title>
              <rect className="ring" x={cx - 9} y={cy - 9} width={18} height={18} rx={5} fill="none" stroke="transparent" />
              <rect x={cx - 5.5} y={cy - 5.5} width={11} height={11} rx={3} fill={sessionColour(s)} />
              {openBySession.has(s.id) && <circle cx={cx + 7} cy={cy - 7} r={3.5} fill="var(--warn)" stroke="#fff" strokeWidth={1.5} />}
              {flags && <text x={cx + 12} y={cy + 4} style={{ fontFamily: "var(--mono)", fontWeight: 600, fill: "var(--ink)" }}>{flags}</text>}
            </g>
          );
        })}

        {lanes.map((l, i) => (
          <LaneView key={l.key} lane={l} top={laneY[i]} width={width} x={x}
            records={data.evidence.filter((e) => e.measure === l.measure && e.protocol_version === "0.1")}
            selectedId={selRecord?.id ?? null} onSelect={(id) => onSelect({ kind: "record", id })} onKey={key} />
        ))}
      </svg>
      <div className="legend" style={{ padding: "4px 8px 8px" }}>
        <span><svg width="12" height="12"><rect x="1" y="1" width="10" height="10" rx="3" fill="var(--navy)" /></svg>{t("sessionStatus_completed")}</span>
        <span><svg width="12" height="12"><rect x="1" y="1" width="10" height="10" rx="3" fill="var(--warn)" /></svg>{t("sessionStatus_interrupted")}</span>
        <span><svg width="12" height="12"><rect x="1" y="1" width="10" height="10" rx="3" fill="var(--fail)" /></svg>{t("sessionStatus_abandoned")}</span>
        <span className="mono">A</span><span style={{ marginInlineStart: -10 }}>{t("wsMarkAssisted")}</span>
        <span className="mono">U</span><span style={{ marginInlineStart: -10 }}>{t("wsMarkUnwell")}</span>
        <span><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" fill="var(--warn)" /></svg>{t("tabCheck")}</span>
        <span><svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="var(--navy)" /></svg>{t("cLegendUsable")}</span>
        <span><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" fill="#fff" stroke="var(--warn)" strokeWidth="2" /></svg>{t("cLegendDoubtful")}</span>
        <span><svg width="12" height="12"><path d="M2 2L10 10M10 2L2 10" stroke="#8a97a0" strokeWidth="1.8" /></svg>{t("wsNotPlotted")}</span>
      </div>
    </div>
  );
}

function LaneView({ lane, top, width, x, records, selectedId, onSelect, onKey }: {
  lane: Lane; top: number; width: number; x: (iso: string) => number; records: Evidence[]; selectedId: number | null;
  onSelect: (id: number) => void; onKey: (fn: () => void) => (e: React.KeyboardEvent) => void;
}) {
  const { t } = useT();
  const plotted = records.filter((e) => e.status === "current" && e.quality !== "unusable" && e.value_num !== null)
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
  const floor = records.filter((e) => !plotted.includes(e));
  const vals = plotted.map((e) => e.value_num as number);
  let lo: number, hi: number, step: number;
  if (lane.fixed) { [lo, hi] = lane.fixed; step = lane.fixed[1] - lane.fixed[0] <= 4 ? 1 : 3; }
  else {
    const min = vals.length ? Math.min(...vals) : 0, max = vals.length ? Math.max(...vals) : 1;
    step = [10, 25, 50, 100, 200, 500].find((s) => (max - min) / s <= 3) ?? 1000;
    lo = Math.floor((min - step / 2) / step) * step; hi = Math.ceil((max + step / 2) / step) * step;
  }
  const inner = lane.height - 22;           // the bottom 22 px is the floor for records not plotted
  const y = (v: number) => top + 6 + (1 - (v - lo) / (hi - lo || 1)) * (inner - 6);
  const ticks: number[] = [];
  for (let v = lo; v <= hi + 1e-9; v += step) ticks.push(v);
  const floorY = top + lane.height - 8;

  return (
    <g>
      <text className="lane-label" x={12} y={top + 14}>{lane.label}</text>
      {floor.length > 0 && <text x={12} y={floorY + 4}>{t("wsNotPlotted")} · {t.num(floor.length)}</text>}
      {ticks.map((v) => (
        <g key={v}>
          <line x1={LABEL_W} x2={width - PAD_R} y1={y(v)} y2={y(v)} stroke="var(--line-soft)" />
          <text x={LABEL_W - 8} y={y(v) + 4} textAnchor="end">{t.num(v)}</text>
        </g>
      ))}
      <line x1={LABEL_W} x2={width - PAD_R} y1={top + lane.height} y2={top + lane.height} stroke="var(--line)" />
      {plotted.length > 1 && (
        <polyline fill="none" stroke="#b9c4cc" strokeWidth={1.25}
          points={plotted.map((e) => `${x(e.recorded_at)},${y(e.value_num as number)}`).join(" ")} />
      )}
      {plotted.map((e) => {
        const cx = x(e.recorded_at), cy = y(e.value_num as number), doubt = e.quality === "doubtful";
        const label = `${t.code(e.measure)} · ${t.date(e.recorded_at)} · ${t.num(e.value_num as number, 1)} ${lane.unit} · ${t(`quality_${e.quality}`)}`;
        return (
          <g key={e.id} className={`pt ${selectedId === e.id ? "sel" : ""}`} tabIndex={0} role="button" aria-label={label}
            onClick={() => onSelect(e.id)} onKeyDown={onKey(() => onSelect(e.id))}>
            <title>{label}</title>
            <circle className="ring" cx={cx} cy={cy} r={10} fill="transparent" stroke="transparent" />
            {doubt ? <circle cx={cx} cy={cy} r={5.5} fill="#fff" stroke="var(--warn)" strokeWidth={2} />
              : <circle cx={cx} cy={cy} r={5.5} fill="var(--navy)" />}
          </g>
        );
      })}
      {floor.map((e) => {
        const cx = x(e.recorded_at);
        const why = e.status !== "current" ? t(`status_${e.status}`) : e.missing_reason ? t("missing") : t(`quality_${e.quality}`);
        const label = `${t.code(e.measure)} · ${t.date(e.recorded_at)} · ${why}`;
        return (
          <g key={e.id} className={`pt ${selectedId === e.id ? "sel" : ""}`} tabIndex={0} role="button" aria-label={label}
            onClick={() => onSelect(e.id)} onKeyDown={onKey(() => onSelect(e.id))}>
            <title>{label}</title>
            <circle className="ring" cx={cx} cy={floorY} r={9} fill="transparent" stroke="transparent" />
            <path d={`M${cx - 4} ${floorY - 4}L${cx + 4} ${floorY + 4}M${cx + 4} ${floorY - 4}L${cx - 4} ${floorY + 4}`} stroke="#8a97a0" strokeWidth={1.8} />
          </g>
        );
      })}
    </g>
  );
}
