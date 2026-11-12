import { useEffect, useState } from "react";
import { api, Consent } from "../api";
import { useT } from "../i18n";
import { ErrorNote, Heading } from "../ui";

/** A separate, revocable consent: sharing a clinician-approved scan-comparison summary with an authorised family member. */
function ShareSummary() {
  const { t } = useT();
  const [c, setC] = useState<Consent | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null);
  useEffect(() => { api.consents().then((l) => setC(l.find((x) => x.scope === "family_imaging_summary") ?? null)).catch(setError); }, []);
  const set = async (granted: boolean) => { setBusy(true); setError(null); try { setC(await api.setConsent("family_imaging_summary", granted, t.lang)); } catch (e) { setError(e); } setBusy(false); };
  return (
    <div className="p-card" aria-labelledby="ss-h">
      <h2 id="ss-h" style={{ fontSize: "1.05rem" }}>{t("shareSumTitle")}</h2>
      <p>{t("shareSumBody")}</p>
      <p className="muted">{c?.granted ? t("shareSumOn", { date: t.date(c.at) }) : t("shareSumOff")}</p>
      {c?.granted
        ? <button className="btn block" disabled={busy} onClick={() => set(false)}>{t("shareSumStop")}</button>
        : <button className="btn primary block" disabled={busy} onClick={() => set(true)}>{t("shareSumAgree")}</button>}
      <ErrorNote error={error} />
    </div>
  );
}

export default function ConsentScreen({ consent, onChanged, onClose }: {
  consent: Consent | null; onChanged: () => void; onClose: () => void;
}) {
  const { t } = useT();
  const [confirming, setConfirming] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const decide = async (granted: boolean) => {
    setBusy(true); setError(null);
    try { await api.setConsent("participation", granted, t.lang); onChanged(); }
    catch (e) { setError(e); }
    setBusy(false);
  };

  if (declined) {
    return (
      <>
        <Heading>{t("consentHeading")}</Heading>
        <p>{t("consentDeclined")}</p>
        <button className="btn block" onClick={() => setDeclined(false)}>{t("back")}</button>
      </>
    );
  }

  // Already decided once: show the state and the one action that changes it.
  if (consent?.at) {
    return (
      <>
        <Heading>{t("consentTitle")}</Heading>
        <div className="p-card">
          <p>{consent.granted ? t("consentGiven", { date: t.date(consent.at) }) : t("consentWithdrawn", { date: t.date(consent.at) })}</p>
          {!confirming && (consent.granted
            ? <button className="btn danger block" onClick={() => setConfirming(true)}>{t("consentWithdraw")}</button>
            : <button className="btn primary block" disabled={busy} onClick={() => decide(true)}>{t("consentRejoin")}</button>)}
          {confirming && (
            <div role="alertdialog" aria-labelledby="wd" style={{ display: "grid", gap: 12 }}>
              <p id="wd">{t("consentWithdrawConfirm")}</p>
              <div className="p-actions two">
                <button className="btn" onClick={() => setConfirming(false)}>{t("cancel")}</button>
                <button className="btn danger" disabled={busy} onClick={() => decide(false)}>{t("consentWithdrawYes")}</button>
              </div>
            </div>
          )}
        </div>
        {consent.granted && <ShareSummary />}
        <p className="muted">{t("deletionNote")}</p>
        <ErrorNote error={error} />
        <button className="btn block" onClick={onClose}>{t("backHome")}</button>
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">{t("consentEyebrow")}</p>
      <Heading>{t("consentHeading")}</Heading>
      <p>{t("consentIntro")}</p>
      <ul className="plain-list">
        {(["consentPoint1", "consentPoint2", "consentPoint3", "consentPoint4", "consentPoint5"] as const)
          .map((k) => <li key={k}>{t(k)}</li>)}
      </ul>
      <ErrorNote error={error} />
      <div className="p-actions">
        <button className="btn primary block" disabled={busy} onClick={() => decide(true)}>{t("consentAgree")}</button>
        <button className="btn block" onClick={() => setDeclined(true)}>{t("consentNotNow")}</button>
      </div>
    </>
  );
}
