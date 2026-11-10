import { useState } from "react";
import { api, Decision } from "../api";
import { useT } from "../i18n";
import { ErrorNote } from "../ui";

/** Keep or exclude, with a note. Used for one item and for a batch. A decision is always written down. */
export default function Decide({ ids, sessionWide, onDone, compact = false }: {
  ids: number[]; sessionWide?: boolean; onDone: () => void; compact?: boolean;
}) {
  const { t } = useT();
  const [decision, setDecision] = useState<Decision>("keep");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      if (ids.length === 1) await api.resolve(ids[0], note, decision);
      else await api.resolveBatch(ids, note, decision);
      setNote(""); onDone();
    } catch (e) { setError(e); }
    setBusy(false);
  };

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div className="seg" role="group" aria-label={t("wsDecision")}>
        <button aria-pressed={decision === "keep"} onClick={() => setDecision("keep")}>{t("wsKeep")}</button>
        <button className="ex" aria-pressed={decision === "exclude"} onClick={() => setDecision("exclude")}>{t("wsExclude")}</button>
      </div>
      {!compact && (
        <p className="hint">{decision === "keep" ? t("wsKeepHint") : sessionWide ? t("wsExcludeSessionHint") : t("wsExcludeHint")}</p>
      )}
      <textarea className="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("checkNoteHint")}
        aria-label={t("checkNote")} maxLength={500} />
      <ErrorNote error={error} />
      <button className="btn primary" disabled={busy || !note.trim()} onClick={submit}>
        {ids.length === 1 ? t("wsRecordDecision") : t("wsApplyTo", { n: t.num(ids.length) })}
      </button>
    </div>
  );
}
