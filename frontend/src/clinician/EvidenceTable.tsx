import { useState } from "react";
import { Evidence } from "../api";
import { useT } from "../i18n";
import { Status } from "../ui";

type Kind = "all" | Evidence["kind"];

export function valueText(e: Evidence, t: ReturnType<typeof useT>["t"]) {
  if (e.value_num !== null) {
    if (e.unit === "1-5") return `${t.num(e.value_num)} / 5`;
    if (e.unit === "count" || !e.unit) return t.num(e.value_num, 1);
    return `${t.num(e.value_num, 1)} ${e.unit}`;
  }
  if (e.value_text) return e.value_text.split(",").map((c) => t.code(c)).join(", ");
  return null;
}

export default function EvidenceTable({ evidence, history, setHistory, onOpen }: {
  evidence: Evidence[]; history: boolean; setHistory: (v: boolean) => void; onOpen: (id: number) => void;
}) {
  const { t } = useT();
  const [kind, setKind] = useState<Kind>("all");
  const rows = evidence.filter((e) => kind === "all" || e.kind === kind);

  return (
    <section className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div className="filters" role="group">
          {(["all", "observed", "self_reported", "inferred"] as Kind[]).map((k) => (
            <button key={k} className="chip" aria-pressed={kind === k} onClick={() => setKind(k)}>
              {k === "all" ? t("cAllKinds") : t(`kind_${k}`)}
            </button>
          ))}
        </div>
        <label style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={history} onChange={(e) => setHistory(e.target.checked)} />
          {t("cShowHistory")}
        </label>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="data">
          <thead>
            <tr>
              <th>{t("colRecorded")}</th><th>{t("colMeasure")}</th><th>{t("colKind")}</th><th>{t("colValue")}</th>
              <th>{t("colQuality")}</th><th>{t("colProtocol")}</th><th>{t("colProducer")}</th><th>{t("colStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => {
              const v = valueText(e, t);
              return (
                <tr key={e.id} className={`clickable ${e.status !== "current" ? "dim" : ""}`} onClick={() => onOpen(e.id)}
                  tabIndex={0} onKeyDown={(k) => { if (k.key === "Enter") onOpen(e.id); }}>
                  <td className="mono" style={{ whiteSpace: "nowrap" }}>{t.date(e.recorded_at, true)}</td>
                  <td>{t.code(e.measure)}</td>
                  <td><span className={`tag ${e.kind}`}>{t(`kind_${e.kind}`)}</span></td>
                  <td className="mono"><span className="val">{v ?? <span className="muted">{t("missing")} · {t.code(e.missing_reason)}</span>}</span></td>
                  <td><Status level={e.quality}>{t(`quality_${e.quality}`)}</Status></td>
                  <td className="mono muted">{e.protocol_code ? `${t.code(e.protocol_code)} ${e.protocol_version}` : "–"}</td>
                  <td className="muted">{t.code(e.producer_type)}</td>
                  <td>{e.status === "current" ? t("status_current") : <Status level="quiet">{t(`status_${e.status}`)}</Status>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
