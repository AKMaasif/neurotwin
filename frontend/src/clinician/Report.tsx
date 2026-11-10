import { useEffect, useState } from "react";
import { Printer, X } from "lucide-react";
import { api, Report } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Mark } from "../ui";

/** A printable, factual summary built by the server from stored records. Counts, ranges and decisions only. */
export default function ReportView({ personId, onClose }: { personId: string; onClose: () => void }) {
  const { t } = useT();
  const [r, setR] = useState<Report | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { api.report(personId).then(setR).catch(setError); }, [personId]);

  const range = (vals: { value: number }[]) => {
    if (!vals.length) return "–";
    const v = vals.map((x) => x.value);
    return `${t.num(Math.min(...v), 1)} – ${t.num(Math.max(...v), 1)} (n=${t.num(v.length)})`;
  };

  return (
    <div className="report-scrim" role="dialog" aria-modal="true" aria-labelledby="rep-h" onClick={onClose}>
      <article className="report" onClick={(e) => e.stopPropagation()}>
        <div className="bar no-print">
          <span />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn primary" disabled={!r} onClick={() => window.print()}><Printer size={16} aria-hidden="true" />{t("repPrint")}</button>
            <button className="btn" onClick={onClose}><X size={16} aria-hidden="true" />{t("repClose")}</button>
          </div>
        </div>
        <ErrorNote error={error} />
        {!r ? !error && <p className="muted">{t("loading")}</p> : (
          <>
            <div className="bar">
              <div>
                <p className="eyebrow">{t("appName")} · {t("prototype")}</p>
                <h1 id="rep-h">{t("repTitle")}</h1>
              </div>
              <Mark size={36} />
            </div>
            <table>
              <tbody>
                <tr><th>{t("repFor")}</th><td><bdi>{r.participant.display_name}</bdi> {r.participant.is_demo && <span className="tag demo">{t("cDemo")}</span>}</td></tr>
                <tr><th>{t("repPeriod")}</th><td>{t.date(r.period.from)} – {t.date(r.period.to)}</td></tr>
                <tr><th>{t("repRules")}</th><td className="mono">{r.rules_version}</td></tr>
              </tbody>
            </table>
            <div className="notice">{t("repNotice")}</div>

            <h2>{t("repSessions")}</h2>
            <table>
              <thead><tr><th>{t("repTotal")}</th>{Object.keys(r.sessions.by_status).map((k) => <th key={k}>{t(`sessionStatus_${k}` as "sessionStatus_completed")}</th>)}<th>{t("dAssisted")}</th><th>{t("dUnwell")}</th></tr></thead>
              <tbody><tr>
                <td className="mono">{t.num(r.sessions.total)}</td>
                {Object.values(r.sessions.by_status).map((v, i) => <td key={i} className="mono">{t.num(v)}</td>)}
                <td className="mono">{t.num(r.sessions.assisted)}</td><td className="mono">{t.num(r.sessions.unwell)}</td>
              </tr></tbody>
            </table>

            <h2>{t("repMeasures")}</h2>
            <table>
              <thead><tr>
                <th>{t("colMeasure")}</th><th>{t("colKind")}</th><th>{t("repRecords")}</th><th>{t("quality_usable")}</th>
                <th>{t("quality_doubtful")}</th><th>{t("quality_unusable")}</th><th>{t("status_withdrawn")}</th><th>{t("repRange")}</th>
              </tr></thead>
              <tbody>
                {r.measures.filter((m) => m.measure !== "today_factors").map((m) => (
                  <tr key={`${m.protocol_code}-${m.protocol_version}-${m.measure}`}>
                    <td>{t.code(m.measure)} <span className="muted mono">{m.protocol_version}</span></td>
                    <td>{t(`kind_${m.kind as "observed"}`)}</td>
                    <td className="mono">{t.num(m.records)}</td><td className="mono">{t.num(m.usable)}</td>
                    <td className="mono">{t.num(m.doubtful)}</td><td className="mono">{t.num(m.unusable)}</td>
                    <td className="mono">{t.num(m.withdrawn)}</td>
                    <td className="mono">{range(m.values)}{m.unit && m.unit !== "count" && m.unit !== "1-5" && m.values.length ? ` ${m.unit}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h2>{t("repOpen")}</h2>
            {r.review.open.length === 0 ? <p className="muted">{t("repNoneOpen")}</p> : (
              <table><tbody>{r.review.open.map((i) => (
                <tr key={i.id}><td className="mono">#{i.id}</td><td>{t.code(i.reason)}</td><td className="mono">{t.date(i.created_at)}</td></tr>
              ))}</tbody></table>
            )}

            <h2>{t("repResolved")}</h2>
            {r.review.resolved.length === 0 ? <p className="muted">{t("repNoneOpen")}</p> : (
              <table><tbody>{r.review.resolved.map((i) => (
                <tr key={i.id}>
                  <td className="mono">#{i.id}</td><td>{t.code(i.reason)}</td>
                  <td>{i.decision ? t(`wsDecided_${i.decision}`) : t("wsReviewed")}</td>
                  <td>{i.resolution_note}</td><td className="mono">{i.resolved_by} · {t.date(i.resolved_at)}</td>
                </tr>
              ))}</tbody></table>
            )}
            <p className="muted" style={{ fontSize: 12 }}>{t("repGenerated", { who: r.generated_by, date: t.date(r.generated_at, true) })}</p>
          </>
        )}
      </article>
    </div>
  );
}
