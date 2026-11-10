import { useCallback, useEffect, useState } from "react";
import { api, Grant, User } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

const purposeFor = (u: User) => (u.role === "clinician" ? "clinical_review" : "participation_updates");

export default function Sharing({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const [grants, setGrants] = useState<Grant[] | null>(null);
  const [people, setPeople] = useState<User[]>([]);
  const [adding, setAdding] = useState(false);
  const [picked, setPicked] = useState<User | null>(null);
  const [stopping, setStopping] = useState<Grant | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [g, p] = await Promise.all([api.grants(), api.grantCandidates()]);
      setGrants(g); setPeople(p);
    } catch (e) { setError(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); await load(); setAdding(false); setPicked(null); setStopping(null); } catch (e) { setError(e); }
    setBusy(false);
  };

  if (stopping) {
    return (
      <div role="alertdialog" aria-labelledby="stop" style={{ display: "grid", gap: 16 }}>
        <Heading><span id="stop">{t("sharingStopConfirm", { name: stopping.grantee.display_name })}</span></Heading>
        <ErrorNote error={error} />
        <div className="p-actions">
          <button className="btn danger block" disabled={busy} onClick={() => act(() => api.revokeGrant(stopping.id))}>{t("sharingStopYes")}</button>
          <button className="btn block" onClick={() => setStopping(null)}>{t("cancel")}</button>
        </div>
      </div>
    );
  }

  if (picked) {
    const purpose = purposeFor(picked);
    return (
      <>
        <Heading>{t("sharingConfirm", { name: picked.display_name })}</Heading>
        <div className="p-card">
          <b>{t(`purposeShort_${purpose}` as "purposeShort_clinical_review")}</b>
          <p>{t(`purpose_${purpose}` as "purpose_clinical_review")}</p>
        </div>
        <ErrorNote error={error} />
        <div className="p-actions">
          <button className="btn primary block" disabled={busy} onClick={() => act(() => api.createGrant(picked.id, purpose))}>{t("sharingYes")}</button>
          <button className="btn block" onClick={() => setPicked(null)}>{t("cancel")}</button>
        </div>
      </>
    );
  }

  const active = grants?.filter((g) => g.active) ?? [];
  const past = grants?.filter((g) => !g.active) ?? [];
  const available = people.filter((p) => !active.some((g) => g.grantee.id === p.id && g.purpose === purposeFor(p)));

  if (adding) {
    return (
      <>
        <Heading>{t("sharingChoose")}</Heading>
        {available.length === 0 && <p className="muted">{t("sharingAllShared")}</p>}
        <div className="p-list">
          {available.map((p) => (
            <button key={p.id} className="p-row" onClick={() => setPicked(p)}>
              <span className="t"><b>{p.display_name}</b>
                <span>{t(p.role === "clinician" ? "roleClinician" : "roleFamily")} · {t(`purposeShort_${purposeFor(p)}` as "purposeShort_clinical_review")}</span></span>
              <span className="chev" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
        <button className="btn block" onClick={() => setAdding(false)}>{t("back")}</button>
      </>
    );
  }

  return (
    <>
      <Heading>{t("sharingTitle")}</Heading>
      <p className="lede">{t("sharingLede")}</p>
      <ErrorNote error={error} onRetry={load} />
      {grants === null ? <p className="muted">{t("loading")}</p> : (
        <>
          <h2>{t("sharingActive")}</h2>
          {active.length === 0 && <p className="muted">{t("sharingNone")}</p>}
          {active.map((g) => (
            <div key={g.id} className="p-card">
              <div>
                <b>{g.grantee.display_name}</b> <span className="muted">· {t("sharingSince", { date: t.date(g.created_at) })}</span>
              </div>
              <p className="muted">{t(`purpose_${g.purpose}` as "purpose_clinical_review")}</p>
              <button className="btn danger" onClick={() => setStopping(g)}>{t("sharingStop")}</button>
            </div>
          ))}
          <button className="btn primary block" onClick={() => setAdding(true)}>{t("sharingAdd")}</button>
          {past.length > 0 && (
            <>
              <h2>{t("sharingPast")}</h2>
              {past.map((g) => (
                <p key={g.id} className="muted">
                  {g.grantee.display_name} · {t(`purposeShort_${g.purpose}` as "purposeShort_clinical_review")} · {t("sharingEnded", { date: t.date(g.revoked_at) })}
                </p>
              ))}
            </>
          )}
        </>
      )}
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
