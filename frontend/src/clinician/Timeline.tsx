import { useEffect, useRef, useState } from "react";
import { api, ChangeResult, Evidence, RoutineReplies, Session } from "../api";
import { changeHeadline } from "./Change";
import { useT } from "../i18n";
import type { Data, Sel } from "./ClinicianApp";

type Lane = { key: string; measure: string; version: string; label: string; height: number; fixed?: [number, number]; unit: string; note?: string };
type Tip = { x: number; y: number; lines: string[] };
type Range = "6w" | "3m" | "6m" | "all";
const RANGE_DAYS: Record<Range, number> = { "6w": 42, "3m": 91, "6m": 183, all: Infinity };
const REP_COLOUR = { done: "var(--navy)", not_today: "#8a97a0", difficulty: "var(--warn)", snooze: "#9fd0da" } as const;
const ROW_ORDER = ["reaction_time", "daily_checkin", "picture_sequence", "who5"];

const LABEL_EN = 210, LABEL_AR = 250, PAD_R = 28, AXIS_H = 30, GAP = 14;
const DAY = 864e5;

/** One person, over time, one lane per measure. Only records from the same activity version share a lane, unusable
 *  and withdrawn records sit on the lane's floor as crosses (counted, not plotted), and nothing is fitted or averaged. */
export default function Timeline({ data, sel, onSelect, pid }: { data: Data; sel: Sel; onSelect: (s: Sel) => void; pid: string }) {
  const { t } = useT();
  const LABEL_W = t.lang === "ar" ? LABEL_AR : LABEL_EN;
  const lx = t.lang === "ar" ? LABEL_W - 50 : 12, anchor = t.lang === "ar" ? "end" : "start";
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(560, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [range, setRange] = useState<Range>("all");
  const [tip, setTip] = useState<Tip | null>(null);
  const [replies, setReplies] = useState<RoutineReplies | null>(null);
  useEffect(() => {
    let live = true;
    if (!pid) return;
    api.routineReplies(pid).then((r) => { if (live) setReplies(r); }).catch(() => { if (live) setReplies(null); });
    return () => { live = false; };
  }, [pid]);

  const allSessions = data.sessions.filter((s) => s.status !== "in_progress");
  if (allSessions.length === 0) return <div ref={ref} className="sheet"><p className="empty">{t("wsNoSessions")}</p></div>;
  const newest = Math.max(...allSessions.map((s) => Date.parse(s.started_at)));
  const cutoff = RANGE_DAYS[range] === Infinity ? -Infinity : newest - RANGE_DAYS[range] * DAY;
  const sessions = allSessions.filter((s) => Date.parse(s.started_at) >= cutoff);
  const evidence = data.evidence.filter((e) => Date.parse(e.recorded_at) >= cutoff);
  const times = sessions.map((s) => Date.parse(s.started_at));
  const t0 = Math.min(...times) - DAY, t1 = Math.max(...times) + DAY;
  const spanDays = Math.max(1, (t1 - t0) / DAY);
  const perDay = (width - LABEL_W - PAD_R) / spanDays;
  const mk = perDay >= 14 ? 11 : perDay >= 6 ? 8 : perDay >= 3 ? 6 : 4;   // marker size follows how crowded the days are
  const x = (iso: string) => LABEL_W + ((Date.parse(iso) - t0) / (t1 - t0)) * (width - LABEL_W - PAD_R);

  // Axis: weekly ticks for short spans, month starts for long ones, so labels never overlap.
  const ticks: { at: number; text: string }[] = [];
  const locale = t.lang === "ar" ? "ar-AE" : "en-GB";
  if (spanDays <= 84) {
    for (let d = t0 + DAY; d <= t1; d += 7 * DAY) ticks.push({ at: d, text: t.date(new Date(d).toISOString()).replace(/\s?\d{4}$/, "") });
  } else {
    const first = new Date(t0); first.setUTCDate(1); first.setUTCHours(0, 0, 0, 0);
    for (let m = new Date(first); m.getTime() <= t1; m.setUTCMonth(m.getUTCMonth() + 1)) {
      if (m.getTime() >= t0) ticks.push({ at: m.getTime(), text: new Intl.DateTimeFormat(locale, { month: "short", year: m.getUTCMonth() === 0 ? "numeric" : undefined, timeZone: "UTC" }).format(m) });
    }
  }

  const rows = ROW_ORDER.filter((c) => sessions.some((s) => s.protocol_code === c));
  const sesH = 22 + rows.length * 20;
  const has = (m: string, v: string) => evidence.some((e) => e.measure === m && e.protocol_version === v);
  const lanes: Lane[] = [
    { key: "rt", measure: "rt_median_ms", version: "0.1", label: t("wsLaneRt"), height: 150, unit: "ms" },
    { key: "sleep", measure: "sleep_hours", version: "0.1", label: t("wsLaneSleep"), height: 96, fixed: [0, 12], unit: "h" },
    { key: "sq", measure: "sleep_quality", version: "0.1", label: t("wsLaneSq"), height: 96, fixed: [1, 5], unit: "" },
    ...(has("rounds_correct", "0.1") ? [{ key: "pic", measure: "rounds_correct", version: "0.1", label: t("chLanePic"), height: 90, fixed: [0, 4] as [number, number], unit: "" }] : []),
    ...(has("who5_raw", "1998-en") ? [{ key: "who5", measure: "who5_raw", version: "1998-en", label: t("chLaneWho5"), height: 110, fixed: [0, 25] as [number, number], unit: "", note: t("chWho5Note") }] : []),
  ];
  const repWeeks = (replies?.weeks ?? []).filter((w) => Date.parse(w.week_start) + 7 * DAY >= t0 && Date.parse(w.week_start) <= t1);
  const REP_H = 100;

  let y = AXIS_H;
  const sesY = y; y += sesH + GAP;
  const laneY = lanes.map((l) => { const top = y; y += l.height + GAP; return top; });
  const repY = y; if (repWeeks.length) y += REP_H + GAP;
  const H = y + 4;
  const show = (el: Element, lines: string[]) => {
    const host = ref.current?.getBoundingClientRect(), r = el.getBoundingClientRect();
    if (host) setTip({ x: r.left - host.left + r.width / 2, y: r.top - host.top, lines });
  };
  const hide = () => setTip(null);

  const openBySession = new Set(data.items.filter((i) => i.status === "open").map((i) => i.session_id));
  const selRecord = sel?.kind === "record" ? data.evidence.find((e) => e.id === sel.id) : undefined;
  const selSession = sel?.kind === "session" ? sel.id : selRecord?.session_id ?? null;
  const key = (fn: () => void) => (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); } };

  const sessionColour = (s: Session) =>
    s.status === "completed" ? "var(--navy)" : s.status === "interrupted" ? "var(--warn)" : "var(--fail)";

  return (
    <div ref={ref} className="sheet" style={{ position: "relative" }}>
      <div className="range-bar" role="group" aria-label={t("chRangeLabel")}>
        <span className="muted">{t("chRangeLabel")}</span>
        {(["6w", "3m", "6m", "all"] as Range[]).map((r) => (
          <button key={r} className="chip" aria-pressed={range === r} onClick={() => setRange(r)}>{t(`chRange${r === "all" ? "All" : r}` as "chRange6w")}</button>
        ))}
        <span className="muted range-note">{t("chRangeNote", { from: t.date(new Date(t0 + DAY).toISOString()), to: t.date(new Date(t1 - DAY).toISOString()) })} · {t("chScaleNote")}</span>
      </div>
      {tip && (
        <div className="chart-tip" role="status" style={{ left: Math.min(Math.max(tip.x, 90), width - 90), top: tip.y - 8 }}>
          {tip.lines.map((l, i) => <div key={i} className={i === 0 ? "tip-head" : ""}>{l}</div>)}
        </div>
      )}
      <svg className="timeline" width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="group" aria-label={t("wsTimeline")} style={{ direction: "ltr", display: "block" }}>
        {ticks.map((k) => {
          const px = x(new Date(k.at).toISOString());
          return (
            <g key={k.at}>
              <line x1={px} x2={px} y1={AXIS_H - 6} y2={H - 4} stroke="var(--line-soft)" />
              <text x={px} y={AXIS_H - 12} textAnchor="middle">{k.text}</text>
            </g>
          );
        })}

        {/* Sessions lane: one row per activity */}
        <text className="lane-label" x={lx} textAnchor={anchor} y={sesY + 14}>{t("wsLaneSessions")}</text>
        {rows.map((c, i) => <text key={c} x={lx} textAnchor={anchor} y={sesY + 32 + i * 20}>{t.code(c)}</text>)}
        <line x1={LABEL_W} x2={width - PAD_R} y1={sesY + sesH} y2={sesY + sesH} stroke="var(--line)" />
        {sessions.map((s) => {
          const row = Math.max(0, rows.indexOf(s.protocol_code));
          const cx = x(s.started_at), cy = sesY + 28 + row * 20;
          const isSel = selSession === s.id;
          const flags = perDay >= 14 ? [s.assisted && "A", s.unwell_today && "U"].filter(Boolean).join(" ") : "";
          const label = `${t.code(s.protocol_code)} · ${t.date(s.started_at)} · ${t(`sessionStatus_${s.status}` as "sessionStatus_completed")}`;
          const lines = [`${t("wsSession")} #${s.id} · ${t.code(s.protocol_code)}`, t.date(s.started_at, true), t(`sessionStatus_${s.status}` as "sessionStatus_completed"),
            t("chTipFlags", { a: s.assisted ? t("chYes") : t("chNo"), u: s.unwell_today == null ? t("chOtherUnreported") : s.unwell_today ? t("chYes") : t("chNo") })];
          return (
            <g key={s.id} className={`pt ${isSel ? "sel" : ""}`} tabIndex={0} role="button" aria-label={label}
              onClick={() => onSelect({ kind: "session", id: s.id })} onKeyDown={key(() => onSelect({ kind: "session", id: s.id }))}
              onPointerEnter={(e) => show(e.currentTarget, lines)} onPointerLeave={hide} onFocus={(e) => show(e.currentTarget, lines)} onBlur={hide}>
              <rect className="ring" x={cx - mk / 2 - 3} y={cy - mk / 2 - 3} width={mk + 6} height={mk + 6} rx={5} fill="none" stroke="transparent" />
              <rect x={cx - mk / 2} y={cy - mk / 2} width={mk} height={mk} rx={Math.min(3, mk / 3)} fill={sessionColour(s)} />
              {openBySession.has(s.id) && mk >= 6 && <circle cx={cx + mk / 2 + 1} cy={cy - mk / 2 - 1} r={3} fill="var(--warn)" stroke="#fff" strokeWidth={1.2} />}
              {flags && <text x={cx + 12} y={cy + 4} style={{ fontFamily: "var(--mono)", fontWeight: 600, fill: "var(--ink)" }}>{flags}</text>}
            </g>
          );
        })}

        {lanes.map((l, i) => (
          <LaneView key={l.key} lane={l} top={laneY[i]} width={width} x={x}
            records={evidence.filter((e) => e.measure === l.measure && e.protocol_version === l.version)}
            change={range === "all" ? data.changes.find((c) => c.measure === l.measure && c.protocol_version === l.version) : undefined}
            selectedId={selRecord?.id ?? null} onSelect={(id) => onSelect({ kind: "record", id })} onKey={key} show={show} hide={hide} />
        ))}
        {repWeeks.length > 0 && <RepLane top={repY} height={REP_H} width={width} x={x} weeks={repWeeks} show={show} hide={hide} />}
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
      {repWeeks.length > 0 && (
        <div className="legend" style={{ padding: "0 8px 4px" }}>
          {(["done", "not_today", "difficulty", "snooze"] as const).map((k) => (
            <span key={k}><svg width="12" height="12"><rect x="1" y="1" width="10" height="10" rx="2" fill={REP_COLOUR[k]} /></svg>{t(`chRep_${k}`)}</span>
          ))}
        </div>
      )}
      {repWeeks.length > 0 && <p className="hint" style={{ padding: "0 8px" }}>{t("chRoutineNote")}</p>}
      {sessions.some((s) => data.evidence.some((e) => e.session_id === s.id && e.producer_version.startsWith("synthetic-history"))) && <p className="hint" style={{ padding: "0 8px" }}>{t("chDataset")}</p>}
      <div className="chart-tables">
        {lanes.map((l) => <LaneTable key={l.key} lane={l} records={evidence.filter((e) => e.measure === l.measure && e.protocol_version === l.version)} onSelect={(id) => onSelect({ kind: "record", id })} />)}
        {repWeeks.length > 0 && (
          <details>
            <summary>{t("chTableOf", { name: t("chLaneRoutine") })}</summary>
            <table className="chart-table"><thead><tr><th>{t("chColDate")}</th>{(["done", "not_today", "difficulty", "snooze"] as const).map((k) => <th key={k}>{t(`chRep_${k}`)}</th>)}</tr></thead>
              <tbody>{repWeeks.map((w) => <tr key={w.week_start}><td>{t.date(w.week_start)}</td><td>{t.num(w.done)}</td><td>{t.num(w.not_today)}</td><td>{t.num(w.difficulty)}</td><td>{t.num(w.snooze)}</td></tr>)}</tbody></table>
          </details>
        )}
      </div>
    </div>
  );
}

function LaneView({ lane, top, width, x, records, change, selectedId, onSelect, onKey, show, hide }: {
  lane: Lane; top: number; width: number; x: (iso: string) => number; records: Evidence[]; change?: ChangeResult; selectedId: number | null;
  onSelect: (id: number) => void; onKey: (fn: () => void) => (e: React.KeyboardEvent) => void;
  show: (el: Element, lines: string[]) => void; hide: () => void;
}) {
  const { t } = useT();
  const LABEL_W = t.lang === "ar" ? LABEL_AR : LABEL_EN;
  const lx = t.lang === "ar" ? LABEL_W - 50 : 12, anchor = t.lang === "ar" ? "end" : "start", wrapAt = t.lang === "ar" ? 20 : 30;
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

  const band = (w: { from: string; to: string }, fill: string, label: string) => {
    const x0 = x(w.from) - 12, x1 = x(w.to) + 12;
    return (
      <g aria-hidden="true">
        <rect x={x0} y={top} width={x1 - x0} height={lane.height - 18} fill={fill} rx={6} />
        <text x={x0 + 6} y={top + 12} style={{ fontSize: 10.5 }}>{label}</text>
      </g>
    );
  };
  const headline = change ? changeHeadline(change, t) : "";
  const tipLines = (e: Evidence) => [
    `${t.code(e.measure)}: ${e.value_num !== null ? `${t.num(e.value_num, 1)}${lane.unit ? ` ${lane.unit}` : ""}` : t("missing")}`,
    t.date(e.recorded_at, true),
    `${t(`quality_${e.quality}`)}${e.quality_reasons.length ? ` · ${e.quality_reasons.map((q) => t.code(q)).join(", ")}` : ""}${e.status !== "current" ? ` · ${t(`status_${e.status}`)}` : ""}`,
    `${t("chColRecord")} #${e.id}${e.session_id ? ` · ${t("wsSession")} #${e.session_id}` : ""}`];

  return (
    <g>
      {change?.baseline && band(change.baseline, "rgba(5,38,64,0.05)", t("chBaseline"))}
      {change?.recent && band(change.recent, change.status === "outside" ? "rgba(138,86,0,0.09)" : "rgba(15,125,146,0.08)", t("chRecent"))}
      <text className="lane-label" x={lx} textAnchor={anchor} y={top + 14}>{lane.label}</text>
      {change && (
        <text x={lx} textAnchor={anchor} y={top + 32} style={{ fontSize: 11, fill: change.status === "outside" ? "var(--warn)" : "var(--muted)" }}>
          {headline.length > wrapAt ? <><tspan x={lx} textAnchor={anchor}>{headline.slice(0, headline.lastIndexOf(" ", wrapAt))}</tspan><tspan x={lx} textAnchor={anchor} dy={14}>{headline.slice(headline.lastIndexOf(" ", wrapAt) + 1)}</tspan></> : headline}
        </text>
      )}
      {floor.length > 0 && <text x={lx} textAnchor={anchor} y={floorY + 4}>{t("wsNotPlotted")} · {t.num(floor.length)}</text>}
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
            onClick={() => onSelect(e.id)} onKeyDown={onKey(() => onSelect(e.id))}
            onPointerEnter={(ev) => show(ev.currentTarget, tipLines(e))} onPointerLeave={hide} onFocus={(ev) => show(ev.currentTarget, tipLines(e))} onBlur={hide}>
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
            onClick={() => onSelect(e.id)} onKeyDown={onKey(() => onSelect(e.id))}
            onPointerEnter={(ev) => show(ev.currentTarget, tipLines(e))} onPointerLeave={hide} onFocus={(ev) => show(ev.currentTarget, tipLines(e))} onBlur={hide}>
            <circle className="ring" cx={cx} cy={floorY} r={9} fill="transparent" stroke="transparent" />
            <path d={`M${cx - 4} ${floorY - 4}L${cx + 4} ${floorY + 4}M${cx + 4} ${floorY - 4}L${cx - 4} ${floorY + 4}`} stroke="#8a97a0" strokeWidth={1.8} />
          </g>
        );
      })}
    </g>
  );
}

function RepLane({ top, height, width, x, weeks, show, hide }: {
  top: number; height: number; width: number; x: (iso: string) => number; weeks: RoutineReplies["weeks"]; show: (el: Element, lines: string[]) => void; hide: () => void;
}) {
  const { t } = useT();
  const LABEL_W = t.lang === "ar" ? LABEL_AR : LABEL_EN;
  const lx = t.lang === "ar" ? LABEL_W - 50 : 12, anchor = t.lang === "ar" ? "end" : "start";
  const total = (w: RoutineReplies["weeks"][number]) => w.done + w.not_today + w.difficulty + w.snooze;
  const max = Math.max(4, ...weeks.map(total));
  const inner = height - 22, y = (v: number) => top + 6 + (1 - v / max) * (inner - 6), base = y(0);
  const bw = Math.max(3, Math.min(22, ((width - LABEL_W - PAD_R) / (weeks.length + 1)) * 0.6));
  const label = t("chLaneRoutine");
  return (
    <g>
      <text className="lane-label" x={lx} textAnchor={anchor} y={top + 14}>{label.length > 24 && t.lang === "ar" ? label.slice(0, label.lastIndexOf(" ", 24)) : label}</text>
      {t.lang === "ar" && label.length > 24 && <text x={lx} textAnchor={anchor} y={top + 30}>{label.slice(label.lastIndexOf(" ", 24) + 1)}</text>}
      {[0, Math.ceil(max / 2), max].map((v) => (
        <g key={v}><line x1={LABEL_W} x2={width - PAD_R} y1={y(v)} y2={y(v)} stroke="var(--line-soft)" /><text x={LABEL_W - 8} y={y(v) + 4} textAnchor="end">{t.num(v)}</text></g>
      ))}
      <line x1={LABEL_W} x2={width - PAD_R} y1={top + height} y2={top + height} stroke="var(--line)" />
      {weeks.map((w) => {
        const cx = x(new Date(Date.parse(w.week_start) + 3.5 * DAY).toISOString());
        const lines = [`${t("chLaneRoutine")}`, t.date(w.week_start), ...(["done", "not_today", "difficulty", "snooze"] as const).map((k) => `${t(`chRep_${k}`)}: ${t.num(w[k])}`)];
        let acc = 0;
        return (
          <g key={w.week_start} className="pt" tabIndex={0} role="img" aria-label={lines.join(", ")}
            onPointerEnter={(e) => show(e.currentTarget, lines)} onPointerLeave={hide} onFocus={(e) => show(e.currentTarget, lines)} onBlur={hide}>
            <rect x={cx - bw / 2 - 2} y={top} width={bw + 4} height={height - 18} fill="transparent" />
            {(["done", "not_today", "difficulty", "snooze"] as const).map((k) => {
              if (!w[k]) return null;
              const h = base - y(w[k]); const yy = base - acc - h; acc += h;
              return <rect key={k} x={cx - bw / 2} y={yy} width={bw} height={Math.max(1, h - 1)} rx={1.5} fill={REP_COLOUR[k]} />;
            })}
          </g>
        );
      })}
    </g>
  );
}

function LaneTable({ lane, records, onSelect }: { lane: Lane; records: Evidence[]; onSelect: (id: number) => void }) {
  const { t } = useT();
  const rows = [...records].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
  return (
    <details>
      <summary>{t("chTableOf", { name: lane.label })}</summary>
      {lane.note && <p className="hint">{lane.note}</p>}
      {rows.length === 0 ? <p className="hint">{t("chNoInRange")}</p> : (
        <div className="chart-table-wrap">
          <table className="chart-table">
            <thead><tr><th>{t("chColDate")}</th><th>{t("chColValue")}</th><th>{t("chColQuality")}</th><th>{t("chColRecord")}</th><th>{t("chColSession")}</th></tr></thead>
            <tbody>{rows.map((e) => (
              <tr key={e.id}>
                <td>{t.date(e.recorded_at, true)}</td>
                <td>{e.value_num !== null ? `${t.num(e.value_num, 1)}${lane.unit ? ` ${lane.unit}` : ""}` : t("missing")}</td>
                <td>{t(`quality_${e.quality}`)}{e.status !== "current" ? ` · ${t(`status_${e.status}`)}` : ""}</td>
                <td><button className="link" onClick={() => onSelect(e.id)}>#{e.id}</button></td>
                <td>{e.session_id ? `#${e.session_id}` : ""}</td>
              </tr>))}</tbody>
          </table>
        </div>)}
    </details>
  );
}
