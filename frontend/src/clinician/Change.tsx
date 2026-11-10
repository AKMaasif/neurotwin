import { ChangeResult } from "../api";
import { useT } from "../i18n";
import { Status } from "../ui";

/** One line a clinician can read without the chart: what was compared, the difference with its interval, and what
 *  was left out. "Within" is shown as neutral, not as good news; "outside" asks for a look, not a conclusion. */
export function changeHeadline(c: ChangeResult, t: ReturnType<typeof useT>["t"]) {
  if (c.status === "insufficient") return t("chStatus_insufficient", { n: t.num(c.eligible_n), need: t.num(c.needed.baseline + c.needed.recent) });
  if (c.status === "outside") return `${t("chStatus_outside")} · ${t(`chDir_${c.direction ?? "higher"}`)}`;
  return t(`chStatus_${c.status}`);
}

export function ChangeLine({ c }: { c: ChangeResult }) {
  const { t } = useT();
  const unit = c.unit && c.unit !== "1-5" ? ` ${c.unit}` : "";
  const sign = (v: number) => `${v > 0 ? "+" : ""}${t.num(v, 1)}`;
  return (
    <div className="d-card">
      <span className="k">{t.code(c.measure)} <span className="mono" style={{ fontWeight: 400 }}>{c.protocol_version}</span></span>
      <Status level={c.status === "outside" ? "warn" : "quiet"}>{changeHeadline(c, t)}</Status>
      {c.difference !== null && c.interval && (
        <span className="mono" style={{ fontSize: 12.5 }}>
          {t("chDiff", { d: sign(c.difference), unit, lo: sign(c.interval[0]), hi: sign(c.interval[1]) })}
        </span>
      )}
      {c.baseline && c.recent && (
        <span className="muted" style={{ fontSize: 12.5 }}>
          {t("chWindows", { nb: t.num(c.baseline.n), nr: t.num(c.recent.n) })} · {t.date(c.baseline.from)} – {t.date(c.recent.to)}
        </span>
      )}
      {c.include_doubtful && <span className="hint" style={{ color: "var(--warn)" }}>{t("chDoubtfulCounted")}</span>}
      {Object.values(c.excluded).some((n) => n > 0) && (
        <span className="muted" style={{ fontSize: 12.5 }}>
          {t("chExcluded", { doubtful: t.num(c.excluded.doubtful), unusable: t.num(c.excluded.unusable),
            withdrawn: t.num(c.excluded.withdrawn), missing: t.num(c.excluded.missing) })}
        </span>
      )}
    </div>
  );
}

export default function ChangeSummary({ changes }: { changes: ChangeResult[] }) {
  const { t } = useT();
  if (changes.length === 0) return null;
  return (
    <>
      <p className="d-section">{t("chTitle")}</p>
      <p className="hint">{t("chLede")}</p>
      {changes.map((c) => <ChangeLine key={`${c.protocol_code}-${c.protocol_version}-${c.measure}`} c={c} />)}
      <p className="hint">{t("chMethod", { method: changes[0].method })}</p>
    </>
  );
}
