import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ActEvent, ActNode, Activity, api } from "../api";

/** What the panel shows for each status: a glyph and a word, so colour is never the only signal. */
const STATUS: Record<string, { icon: string; text: string }> = {
  waiting: { icon: "○", text: "Waiting" }, queued: { icon: "◷", text: "Queued" }, running: { icon: "◐", text: "Running" },
  completed: { icon: "✓", text: "Completed" }, completed_with_warnings: { icon: "⚠", text: "Completed with warnings" },
  failed: { icon: "✕", text: "Failed" }, blocked: { icon: "⊘", text: "Blocked" }, unavailable: { icon: "–", text: "Unavailable" },
  cancelled: { icon: "■", text: "Cancelled" }, skipped: { icon: "↷", text: "Skipped" }, awaiting_review: { icon: "⏸", text: "Awaiting review" },
};
const KIND = { tool: { icon: "⚙", text: "Tool" }, ai: { icon: "✦", text: "AI agent" }, human: { icon: "☺", text: "Human review" } };
const DONE = ["completed", "completed_with_warnings", "awaiting_review"];
const NOT_RUN = ["unavailable", "skipped", "blocked", "failed", "cancelled"];
const TERMINAL = [...DONE, ...NOT_RUN];
const RUN_TEXT: Record<string, string> = { idle: "Idle", queued: "Queued", running: "Running", aligned: "Running", complete: "Completed", partial: "Completed with limits",
  failed: "Failed", cancelled: "Cancelled", blocked: "Blocked", unavailable: "Unavailable" };
const W = 184, H = 88, GX = 56, GY = 26, PAD = 24;

type Pos = { x: number; y: number };
type View = { x: number; y: number; k: number };

const reduced = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const clock = (ts: string | null) => { if (!ts) return "–"; const d = new Date(ts); return `${d.toLocaleTimeString([], { hour12: false })}.${String(d.getMilliseconds()).padStart(3, "0")}`; };
const span = (ms: number | null) => ms === null ? "–" : ms < 1000 ? `${ms} ms` : ms < 60000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.floor(ms / 60000)} min ${Math.round((ms % 60000) / 1000)} s`;

function layout(nodes: ActNode[]) {
  const depth = new Map<string, number>();
  const d = (n: ActNode): number => { if (depth.has(n.id)) return depth.get(n.id)!; const v = n.deps.length ? 1 + Math.max(...n.deps.map(id => d(nodes.find(m => m.id === id)!))) : 0; depth.set(n.id, v); return v; };
  nodes.forEach(d);
  const cols = Math.max(...depth.values()) + 1, rows: ActNode[][] = Array.from({ length: cols }, () => []);
  nodes.forEach(n => rows[depth.get(n.id)!].push(n));
  const tall = Math.max(...rows.map(r => r.length)), pos = new Map<string, Pos>();
  rows.forEach((col, c) => col.forEach((n, i) => pos.set(n.id, { x: PAD + c * (W + GX), y: PAD + ((tall - col.length) / 2 + i) * (H + GY) })));
  return { pos, w: PAD * 2 + cols * W + (cols - 1) * GX, h: PAD * 2 + tall * H + (tall - 1) * GY };
}

/** Rebuild what the graph looked like after the first ``upto`` recorded events. Reads the log only; nothing is run. */
function fold(base: ActNode[], events: ActEvent[], upto: number): ActNode[] {
  const cur = new Map<string, { status: string; summary: string }>(), t = new Map<string, { s: string | null; e: string | null }>();
  events.slice(0, upto).forEach(e => {
    if (e.type !== "status") return;
    cur.set(e.node, { status: e.status, summary: e.summary });
    const x = t.get(e.node) ?? { s: null, e: null };
    if (e.status === "running" && !x.s) x.s = e.ts;
    if (TERMINAL.includes(e.status)) { x.e = e.ts; x.s = x.s ?? e.ts; } else x.e = null;
    t.set(e.node, x);
  });
  return base.map(n => {
    const c = cur.get(n.id), x = t.get(n.id);
    const status = c?.status ?? "waiting";
    return { ...n, status, summary: c?.summary ?? null, outputs: DONE.includes(status) ? n.outputs : [], started_at: x?.s ?? null, ended_at: x?.e ?? null,
      duration_ms: x?.s && x.e ? new Date(x.e).getTime() - new Date(x.s).getTime() : null };
  });
}

function Chip({ status }: { status: string }) {
  const s = STATUS[status] ?? { icon: "?", text: status };
  return <span className={`aa-chip aa-s-${status}`}><span aria-hidden="true">{s.icon}</span> {s.text}</span>;
}

type Props = { refreshSignal?: number; liveSignal?: number; replaySignal?: number; onReplayEnd?: () => void; runId: string | null; onCancel: () => void; onOpenResult: (target: string) => void };

/** Agent Activity: a compact status card that opens into the real workflow graph, event list and timeline of one run. */
export default function AgentActivity({ refreshSignal = 0, liveSignal = 0, replaySignal = 0, onReplayEnd, runId, onCancel, onOpenResult }: Props) {
  const [act, setAct] = useState<Activity | null>(null), [events, setEvents] = useState<ActEvent[]>([]), [lost, setLost] = useState(false), [error, setError] = useState("");
  const [open, setOpen] = useState(false), [folded, setFolded] = useState(false), [sel, setSel] = useState<string | null>(null), [view, setView] = useState<View | null>(null);
  const [follow, setFollow] = useState(false), [tab, setTab] = useState<"timeline" | "events">("timeline"), [onlySel, setOnlySel] = useState(false);
  const [replay, setReplay] = useState<number | null>(null), [playing, setPlaying] = useState(false), [speed, setSpeed] = useState(10), [now, setNow] = useState(Date.now());
  const last = useRef(0), canvas = useRef<HTMLDivElement>(null), expandBtn = useRef<HTMLButtonElement>(null), dialog = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 400 }), drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  // Live updates by polling with a cursor: a dropped connection resumes from the last event seen, and an event is never added twice.
  useEffect(() => {
    let stop = false, timer = 0;
    last.current = 0; setEvents([]); setSel(null); setReplay(null); setPlaying(false); setError(""); setLost(false);
    const tick = async () => {
      try {
        const a = runId ? await api.agentActivity(runId, last.current) : await api.agentWorkflow();
        if (stop) return;
        setLost(false); setError(""); setAct(a);
        if (runId) {
          last.current = Math.max(last.current, a.last_seq);
          if (a.events.length) setEvents(prev => { const seen = new Set(prev.map(e => e.id)); return [...prev, ...a.events.filter(e => !seen.has(e.id))].sort((p, q) => p.seq - q.seq); });
          if (a.live) timer = window.setTimeout(tick, 1000);
        }
      } catch (e) {
        if (stop) return;
        setLost(true); setError((e as Error).message);
        timer = window.setTimeout(tick, 3000);
      }
    };
    tick();
    return () => { stop = true; window.clearTimeout(timer); };
  }, [runId, refreshSignal]);

  useEffect(() => { if (!act?.live) return; const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, [act?.live]);

  const replaying = replay !== null;
  const nodes = useMemo(() => act ? (replaying ? fold(act.nodes, events, replay!) : act.nodes) : [], [act, events, replay, replaying]);
  const geo = useMemo(() => nodes.length ? layout(nodes) : null, [nodes.length]);  // eslint-disable-line react-hooks/exhaustive-deps
  const byId = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);
  const active = nodes.find(n => n.status === "running") ?? null;
  const selected = sel ? byId.get(sel) ?? null : follow && active ? active : null;  // following a live run shows the running step's details
  const done = nodes.filter(n => DONE.includes(n.status)).length, notRun = nodes.filter(n => NOT_RUN.includes(n.status)).length;
  const remaining = nodes.length - done - notRun;
  const runState = act?.state ?? "idle";
  const shownEvents = (replaying ? events.slice(0, replay!) : events).filter(e => !onlySel || !sel || e.node === sel);

  const fit = useCallback(() => {
    if (!geo) return;
    const k = Math.min(size.w / geo.w, size.h / geo.h, 1.2);
    setView({ k, x: (size.w - geo.w * k) / 2, y: (size.h - geo.h * k) / 2 });
  }, [geo, size]);
  const zoomBy = useCallback((f: number, cx = size.w / 2, cy = size.h / 2) => setView(v => {
    const cur = v ?? { x: 0, y: 0, k: 1 }, k = Math.max(0.2, Math.min(2.5, cur.k * f));
    return { k, x: cx - (cx - cur.x) * (k / cur.k), y: cy - (cy - cur.y) * (k / cur.k) };
  }), [size]);
  const centreOn = useCallback((id: string) => {
    const p = geo?.pos.get(id); if (!p) return;
    setView(v => { const k = v?.k ?? 1; return { k, x: size.w / 2 - (p.x + W / 2) * k, y: size.h / 2 - (p.y + H / 2) * k }; });
  }, [geo, size]);

  useLayoutEffect(() => {
    if (!open || !canvas.current) return;
    const el = canvas.current, measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure); ro.observe(el);
    return () => ro.disconnect();
  }, [open]);
  useEffect(() => {  // first opening: fit when that stays readable, otherwise start at the left at a readable size; later openings keep the position
    if (!open || view || !geo) return;
    const k = Math.min(size.w / geo.w, size.h / geo.h, 1.2);
    if (k >= 0.7) fit(); else setView({ k: 0.7, x: 16, y: Math.max(8, (size.h - geo.h * 0.7) / 2) });
  }, [open, view, geo, fit, size]);
  useEffect(() => { if (open && follow && active) centreOn(active.id); }, [open, follow, active?.id]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = canvas.current; if (!open || !el) return;
    const wheel = (e: WheelEvent) => { e.preventDefault(); const r = el.getBoundingClientRect(); zoomBy(e.deltaY < 0 ? 1.1 : 1 / 1.1, e.clientX - r.left, e.clientY - r.top); };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [open, zoomBy]);

  useEffect(() => {  // replay steps through the recorded events only, spaced by their real gaps divided by the speed
    if (!playing || replay === null) return;
    if (replay >= events.length) { setPlaying(false); return; }
    const gap = replay === 0 ? 400 : (new Date(events[replay].ts).getTime() - new Date(events[replay - 1].ts).getTime()) / speed;
    const t = window.setTimeout(() => setReplay(r => (r ?? 0) + 1), Math.min(2200, Math.max(150, gap)));
    return () => window.clearTimeout(t);
  }, [playing, replay, events, speed]);

  // Starting a real run opens the panel and follows the running step; nothing opens for saved results.
  useEffect(() => { if (liveSignal > 0) { auto.current = false; setOpen(true); setFollow(true); setView(null); setTab("timeline"); } }, [liveSignal]);

  // "Watch recorded run": open the panel and play the stored events from the beginning. When it ends the panel closes and the
  // page loads the results one by one (onReplayEnd). A run saved before event recording has nothing to play: results show at once.
  const auto = useRef(false), pending = useRef(false);
  useEffect(() => { if (replaySignal > 0) { pending.current = true; auto.current = true; setOpen(true); setFollow(true); setView(null); setTab("timeline"); setReplay(null); } }, [replaySignal]);
  useEffect(() => {
    if (!pending.current || !act || act.run_id !== runId) return;
    if (act.live) { pending.current = false; auto.current = false; return; }
    if (!act.has_events) { pending.current = false; auto.current = false; setOpen(false); onReplayEnd?.(); return; }
    if (events.length && events[events.length - 1].seq === act.last_seq) { pending.current = false; setReplay(0); setPlaying(true); }
  }, [act, events, runId, replaySignal]);  // eslint-disable-line react-hooks/exhaustive-deps
  const finish = () => {  // the recorded run was played to its end, or skipped
    if (!auto.current) return;
    auto.current = false; setPlaying(false); setReplay(null);
    window.setTimeout(() => { setOpen(false); onReplayEnd?.(); }, 1200);
  };
  useEffect(() => { if (auto.current && replay !== null && events.length > 0 && replay >= events.length) finish(); }, [replay, events.length]);  // eslint-disable-line react-hooks/exhaustive-deps


  const close = () => { setOpen(false); window.setTimeout(() => expandBtn.current?.focus(), 0); };
  useEffect(() => { if (open) dialog.current?.querySelector<HTMLElement>("[data-first]")?.focus(); }, [open]);
  useEffect(() => {  // Escape minimizes even when focus has not reached the panel yet
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [open]);  // eslint-disable-line react-hooks/exhaustive-deps
  const keys = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); close(); return; }
    if (e.key === "Tab" && dialog.current) {  // keep Tab inside the open panel
      const f = [...dialog.current.querySelectorAll<HTMLElement>("button:not([disabled]),input:not([disabled]),[tabindex='0']")].filter(x => x.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], lastEl = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); lastEl.focus(); } else if (!e.shiftKey && document.activeElement === lastEl) { e.preventDefault(); first.focus(); }
    }
  };
  const canvasKeys = (e: React.KeyboardEvent) => {
    const step = 60;
    if (e.key === "+" || e.key === "=") zoomBy(1.2); else if (e.key === "-") zoomBy(1 / 1.2); else if (e.key === "0") fit();
    else if (e.key === "ArrowLeft") setView(v => v && { ...v, x: v.x + step }); else if (e.key === "ArrowRight") setView(v => v && { ...v, x: v.x - step });
    else if (e.key === "ArrowUp") setView(v => v && { ...v, y: v.y + step }); else if (e.key === "ArrowDown") setView(v => v && { ...v, y: v.y - step });
    else return;
    e.preventDefault();
  };
  const down = (e: React.PointerEvent) => { if ((e.target as HTMLElement).closest("button")) return; drag.current = { x: e.clientX, y: e.clientY, vx: view?.x ?? 0, vy: view?.y ?? 0 }; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); setFollow(false); };
  const move = (e: React.PointerEvent) => { const d = drag.current; if (d) setView(v => v && { ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }); };
  const up = () => { drag.current = null; };

  const idle = !runId;
  const headline = idle ? "No analysis is running." : active ? `Running: ${active.label}` : act?.live ? "Waiting for the next step." : `${RUN_TEXT[runState] ?? runState}.`;
  const detail = idle ? "Press Run live on a saved analysis, or choose a pair below and run Agent Analysis. This panel then opens and follows the real steps." : active?.summary ?? (act?.historical ? ({ cancelled: "The analysis was cancelled; the steps after it did not run.", failed: "The analysis stopped with an error; the steps after it did not run.", blocked: "The pair did not pass validation, so nothing was run.", partial: "Finished with limits: some steps are unavailable, shown in the graph.", complete: "Stored record of a finished analysis." } as Record<string, string>)[runState] ?? "Stored record of a finished analysis." : "");
  const open_ = (t: string | null) => { if (!t) return; close(); window.setTimeout(() => onOpenResult(t), 50); };

  const t0 = act?.started_at ? new Date(act.started_at).getTime() : 0;
  const tEnd = (() => { const ends = nodes.map(n => n.ended_at ? new Date(n.ended_at).getTime() : 0); const m = Math.max(0, ...ends); return act?.live && !replaying ? Math.max(now, m) : m || t0 + 1; })();
  const total = Math.max(tEnd - t0, 1);

  const stateBadge = idle ? "Idle" : replaying || pending.current ? "Replay of a recorded run" : act?.live ? "Live" : act?.has_events ? "Historical record" : "Saved result";

  return <>
    <section className="aa-compact" aria-label="Agent Activity" data-testid="agent-activity">
      <header>
        <h2>Agent Activity</h2>
        <span className={`aa-badge ${act?.live ? "aa-live" : ""}`}>{stateBadge}</span>
        <button className="aa-quiet" onClick={() => setFolded(f => !f)} aria-expanded={!folded} aria-label={folded ? "Show the Agent Activity summary" : "Minimize the Agent Activity summary"}>{folded ? "▸" : "▾"}</button>
        <button ref={expandBtn} onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open}>Expand</button>
      </header>
      {!folded && <div className="aa-body">
        <p className="aa-status" role="status" aria-live="polite"><strong>{headline}</strong>{detail ? <><br />{detail}</> : null}</p>
        {!idle && <p className="aa-state">Analysis: <Chip status={act?.live ? "running" : runState === "complete" ? "completed" : runState === "partial" ? "completed_with_warnings" : runState === "aligned" ? "running" : runState} /></p>}
        {nodes.length > 0 && <>
          <div className="aa-seg" role="img" aria-label={`${done} steps finished, ${remaining} remaining, ${notRun} not run`}>
            {nodes.map(n => <i key={n.id} className={`aa-s-${n.status}`} title={`${n.label}: ${STATUS[n.status]?.text ?? n.status}`} />)}</div>
          <p className="aa-counts">{idle ? `${nodes.filter(n => n.implemented).length} steps built, ${nodes.filter(n => !n.implemented).length} not connected.` : `${done} finished · ${remaining} remaining · ${notRun} not run`}</p></>}
        {lost && <p className="aa-lost" role="status">Connection to the server was lost. Showing the last known state; retrying.{error ? ` (${error})` : ""}</p>}
        {act?.cancel_supported && <p className="aa-row"><button onClick={onCancel}>Cancel analysis</button><small>Closing this panel does not stop the analysis.</small></p>}
        {act?.note && <p className="aa-note">{act.note}</p>}
      </div>}
    </section>

    {open && act && geo && <div className="aa-overlay" role="dialog" aria-modal="true" aria-labelledby="aa-title" ref={dialog} onKeyDown={keys}>
      <header className="aa-top">
        <div><h2 id="aa-title">Agent Activity</h2>
          <p>{replaying ? `Replaying a recorded run at ${speed}× speed. Nothing is being computed now.` : idle ? "The workflow as built. Nothing has run yet." : act.live ? "Live: updating from the server." : act.has_events ? "Historical record of this run. Opening it does not run anything again." : "Saved result. No timeline was recorded for this run."}
            {act.parent_run_id ? " This run is a retry." : ""}</p></div>
        <div className="aa-tools" role="toolbar" aria-label="Graph controls">
          <label className="aa-check"><input type="checkbox" checked={follow} onChange={e => setFollow(e.target.checked)} disabled={!act.live && !replaying} />Follow active step</label>
          <button data-first onClick={() => zoomBy(1 / 1.2)} aria-label="Zoom out">−</button><output aria-label="Zoom level">{Math.round((view?.k ?? 1) * 100)}%</output>
          <button onClick={() => zoomBy(1.2)} aria-label="Zoom in">+</button><button onClick={fit}>Fit</button>
          <button onClick={() => { setFollow(false); setView({ k: 1, x: 20, y: Math.max(20, size.h / 2 - (geo.h / 2)) }); }}>Reset</button>
          {act.cancel_supported && <button onClick={onCancel}>Cancel analysis</button>}
          <button onClick={close}>Minimize</button></div>
        {lost && <p className="aa-lost" role="status">Connection to the server was lost. Showing the last known state; retrying.</p>}
      </header>
      <div className="aa-main">
        <div className="aa-graph">
          <div ref={canvas} className={`aa-canvas ${reduced() ? "aa-still" : ""}`} tabIndex={0} role="group" dir="ltr"
            aria-label="Workflow graph. Arrow keys move the view, plus and minus zoom, zero fits the graph. Tab reaches each step."
            onKeyDown={canvasKeys} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
            <div className="aa-world" style={{ width: geo.w, height: geo.h, transform: `translate(${view?.x ?? 0}px, ${view?.y ?? 0}px) scale(${view?.k ?? 1})` }}>
              <svg width={geo.w} height={geo.h} aria-hidden="true">
                {nodes.flatMap(n => n.deps.map(dep => {
                  const a = geo.pos.get(dep)!, b = geo.pos.get(n.id)!, src = byId.get(dep)!;
                  const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, c = GX * 0.6;
                  const live = n.status === "running", dim = NOT_RUN.includes(n.status) || NOT_RUN.includes(src.status);
                  return <path key={`${dep}-${n.id}`} d={`M${x1},${y1} C${x1 + c},${y1} ${x2 - c},${y2} ${x2},${y2}`} className={`aa-edge ${live ? "aa-edge-live" : ""} ${dim ? "aa-edge-dim" : ""}`} />;
                }))}
              </svg>
              {nodes.map(n => { const p = geo.pos.get(n.id)!;
                return <button key={n.id} className={`aa-node aa-k-${n.kind} aa-s-${n.status} ${sel === n.id ? "aa-picked" : ""} ${!n.implemented ? "aa-planned" : ""}`} style={{ left: p.x, top: p.y, width: W, height: H }}
                  onClick={() => setSel(n.id)} aria-pressed={sel === n.id} aria-label={`${n.label}. ${KIND[n.kind].text}. ${STATUS[n.status]?.text ?? n.status}.`}>
                  <small><span aria-hidden="true">{KIND[n.kind].icon}</span> {KIND[n.kind].text}</small><strong>{n.label}</strong><Chip status={n.status} /></button>; })}
            </div>
            <div className="aa-mini" aria-hidden="true" onClick={e => {
              const r = e.currentTarget.getBoundingClientRect(), s = Math.min(180 / geo.w, 110 / geo.h), k = view?.k ?? 1;
              setFollow(false); setView({ k, x: size.w / 2 - ((e.clientX - r.left) / s) * k, y: size.h / 2 - ((e.clientY - r.top) / s) * k });
            }}>
              {(() => { const s = Math.min(180 / geo.w, 110 / geo.h), k = view?.k ?? 1, mh = Math.max(36, Math.ceil(geo.h * s)); return <svg width="180" height={mh} style={{ overflow: "hidden", display: "block" }}>
                {nodes.map(n => { const p = geo.pos.get(n.id)!; return <rect key={n.id} x={p.x * s} y={p.y * s} width={W * s} height={H * s} className={`aa-s-${n.status}`} />; })}
                <rect className="aa-vp" x={(-(view?.x ?? 0) / k) * s} y={(-(view?.y ?? 0) / k) * s} width={(size.w / k) * s} height={(size.h / k) * s} />              </svg>; })()}</div>
          </div>
          <ul className="aa-legend" aria-label="Legend">
            <li><span className="aa-key aa-k-tool" /> Tool: ordinary software step</li><li><span className="aa-key aa-k-ai" /> AI agent: model-assisted</li>
            <li><span className="aa-key aa-k-human" /> Human review gate</li><li><span className="aa-key aa-planned" /> Dashed: not connected or not run</li></ul>
        </div>

        <aside className="aa-detail" aria-label="Step details" aria-live="polite">
          {!selected ? <><h3>Select a step</h3><p>Choose any step in the graph to see what it did, what it used and what it produced.</p>
            <p className="aa-note">Only ordinary software steps run today. The two AI agents and the brain-extraction step are shown as unavailable because they are not connected.</p></> : <>
            <h3>{selected.label}</h3>
            <p><span className={`aa-kind aa-k-${selected.kind}`}>{KIND[selected.kind].icon} {KIND[selected.kind].text}</span> <Chip status={selected.status} /></p>
            <p>{selected.role}</p>
            {selected.summary && <p><strong>What happened.</strong> {selected.summary}</p>}
            <dl>
              <dt>Started</dt><dd>{clock(selected.started_at)}</dd><dt>Ended</dt><dd>{clock(selected.ended_at)}</dd><dt>Duration</dt><dd>{span(selected.duration_ms)}</dd>
              <dt>Tool or version</dt><dd>{selected.tool ?? "–"}</dd>
              <dt>Depends on</dt><dd>{selected.deps.length ? selected.deps.map(d => `${byId.get(d)?.label ?? d} (${STATUS[byId.get(d)?.status ?? "waiting"]?.text})`).join("; ") : "Nothing: this is the first step."}</dd>
              <dt>Feeds</dt><dd>{nodes.filter(m => m.deps.includes(selected.id)).map(m => m.label).join("; ") || "–"}</dd></dl>
            {selected.inputs.length > 0 && <><h4>Inputs</h4><ul>{selected.inputs.map(i => <li key={i}>{i}</li>)}</ul></>}
            {selected.warnings.length > 0 && <><h4>Warnings and reasons</h4><ul>{selected.warnings.map(i => <li key={i}>{i}</li>)}</ul></>}
            <h4>Outputs</h4>
            {selected.outputs.length ? <ul>{selected.outputs.map(o => <li key={o.label}>{o.label}{o.target && <> <button onClick={() => open_(o.target)}>Open result</button></>}</li>)}</ul>
              : <p>{NOT_RUN.includes(selected.status) ? "No output: this step did not run." : "None yet."}</p>}
            <p className="aa-note">Shows what each step did and used. It does not show model reasoning, prompts or credentials.</p></>}
        </aside>
      </div>

      <section className="aa-foot" aria-label="Execution history">
        <div className="aa-tabs" role="tablist">
          <button role="tab" aria-selected={tab === "timeline"} onClick={() => setTab("timeline")}>Timeline</button>
          <button role="tab" aria-selected={tab === "events"} onClick={() => setTab("events")}>Events ({events.length})</button>
          {act.has_events && !act.live && <span className="aa-replay">
            {!replaying ? <button onClick={() => { setReplay(0); setPlaying(true); }}>Replay a recorded run (no processing)</button> : <>
              <button onClick={() => setPlaying(p => !p)}>{playing ? "Pause" : "Play"}</button>
              <input type="range" min={0} max={events.length} value={replay!} onChange={e => { setPlaying(false); setReplay(+e.target.value); }} aria-label="Replay position" />
              <span>{replay} / {events.length}</span>
              <label className="aa-check">Speed <select value={speed} onChange={e => setSpeed(+e.target.value)} aria-label="Replay speed"><option value={1}>Real time</option><option value={10}>10×</option><option value={30}>30×</option></select></label>
              {auto.current ? <button onClick={() => setReplay(events.length)}>Skip to result</button> : <button onClick={() => { setReplay(null); setPlaying(false); }}>Exit replay</button>}</>}</span>}
        </div>
        {tab === "timeline" ? <div role="tabpanel" className="aa-timeline">
          {!act.has_events ? <p className="aa-note">{act.note ?? "No events yet."}</p> : <>
            <ol>{nodes.map(n => { const s = n.started_at ? new Date(n.started_at).getTime() : null, e = n.ended_at ? new Date(n.ended_at).getTime() : s !== null && n.status === "running" ? Math.max(now, s) : s;
              const ran = ["unavailable", "skipped"].includes(n.status), left = s === null ? 0 : ((s - t0) / total) * 100, width = s === null || e === null ? 0 : Math.max(((e - s) / total) * 100, 0.8);
              return <li key={n.id}><button onClick={() => setSel(n.id)} className={sel === n.id ? "aa-picked" : ""}><span className="aa-tl-name" title={n.label}>{n.label}</span>
                <span className="aa-tl-track" aria-hidden="true">{s !== null && !ran && <i className={`aa-s-${n.status}`} style={{ left: `${left}%`, width: `${width}%` }} />}</span>
                <span className="aa-tl-time">{ran ? "did not run" : s === null ? "not started" : `${clock(n.started_at)} · ${span(n.duration_ms ?? (n.status === "running" && s ? Math.max(0, now - s) : null))}`}</span></button></li>; })}</ol>
            <p className="aa-axis"><span>{clock(act.started_at)}</span><span>Total {span(total)}</span></p></>}</div>
          : <div role="tabpanel" className="aa-events">
            <label className="aa-check"><input type="checkbox" checked={onlySel} onChange={e => setOnlySel(e.target.checked)} disabled={!sel} />Only the selected step</label>
            {shownEvents.length === 0 ? <p className="aa-note">{act.note ?? "No events yet."}</p> :
              <ol>{shownEvents.map(e => <li key={e.id}><time dateTime={e.ts}>{clock(e.ts)}</time><span className="aa-type">{{ status: "status", run: "run", tool_call: "tool call", handoff: "hand-off" }[e.type]}</span>
                <strong>{e.node === "run" ? "Analysis" : byId.get(e.node)?.label ?? e.node}</strong><Chip status={e.status} /><span className="aa-sum">{e.summary}</span></li>)}</ol>}</div>}
      </section>
    </div>}
  </>;
}
