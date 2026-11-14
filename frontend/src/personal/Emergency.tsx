import { useEffect, useState } from "react";
import { Phone, MessageSquare } from "lucide-react";
import { api, EmergencyConfig } from "../api";
import { useT } from "../i18n";
import { Heading } from "../ui";

/** Built in, so this screen is complete without the server or any model. */
const FALLBACK: EmergencyConfig = { region: "AE", numbers: [{ id: "ambulance", number: "998" }, { id: "police", number: "999" }], verified: false, trusted: null };
const LABEL: Record<string, "emAmbulance" | "emPolice" | "emFire" | "emGeneral"> = { ambulance: "emAmbulance", police: "emPolice", fire: "emFire", general: "emGeneral" };
const clean = (p: string) => p.replace(/[^\d+]/g, "");

/** Urgent help. It hands the call to the phone's own dialer and says plainly what NeuroTwin cannot do. Nothing here is logged or sent. */
export default function Emergency({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const [cfg, setCfg] = useState<EmergencyConfig>(FALLBACK);
  const [offline, setOffline] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [bad, setBad] = useState(false);
  useEffect(() => { api.emergencyConfig().then(setCfg).catch(() => setOffline(true)); }, []);

  const save = async () => {
    setBad(false);
    try { const r = await api.setTrusted(name, phone); setCfg({ ...cfg, trusted: r }); setEditing(false); } catch { setBad(true); }
  };
  const remove = async () => { try { await api.clearTrusted(); setCfg({ ...cfg, trusted: null }); setEditing(false); } catch { setBad(true); } };
  const edit = () => { setName(cfg.trusted?.name ?? ""); setPhone(cfg.trusted?.phone ?? ""); setBad(false); setEditing(true); };

  return (
    <>
      <Heading>{t("urgentTitle")}</Heading>
      <p>{t("urgentBody")}</p>
      <section aria-labelledby="em-nums">
        <h2 id="em-nums">{t("emNumbersTitle")}</h2>
        {cfg.numbers.map((n) => (
          <a key={n.id} className="btn block em-call" href={`tel:${n.number}`}>
            <Phone size={22} aria-hidden="true" /> {t("emCall", { label: t(LABEL[n.id] ?? "emGeneral"), n: n.number })}
          </a>
        ))}
        <p className="muted">{cfg.verified ? t("emVerified") : t("emUnverified")}</p>
        {offline && <p className="muted">{t("emConfigOffline")}</p>}
      </section>
      <p role="note"><b>{t("emLimits")}</b></p>
      <section aria-labelledby="em-trust">
        <h2 id="em-trust">{t("emTrustedTitle")}</h2>
        {cfg.trusted && !editing && (
          <>
            <a className="btn block em-call" href={`tel:${clean(cfg.trusted.phone)}`}><Phone size={22} aria-hidden="true" /> {t("emTrustedCall", { name: cfg.trusted.name })}</a>
            <a className="btn block" href={`sms:${clean(cfg.trusted.phone)}?body=${encodeURIComponent(t("emTrustedSms"))}`}><MessageSquare size={22} aria-hidden="true" /> {t("emTrustedText", { name: cfg.trusted.name })}</a>
            <button className="btn block" onClick={edit}>{t("emTrustedChange")}</button>
          </>
        )}
        {!cfg.trusted && !editing && (
          <>
            <p>{t("emTrustedNone")}</p>
            {!offline && <button className="btn block" onClick={edit}>{t("emTrustedAdd")}</button>}
          </>
        )}
        {editing && (
          <form onSubmit={(e) => { e.preventDefault(); void save(); }}>
            <label>{t("emTrustedName")}<input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoComplete="off" /></label>
            <label>{t("emTrustedPhone")}<input value={phone} maxLength={24} inputMode="tel" dir="ltr" onChange={(e) => setPhone(e.target.value)} autoComplete="off" /></label>
            {bad && <p role="alert">{t("emTrustedBad")}</p>}
            <button className="btn primary block" type="submit">{t("emTrustedSave")}</button>
            {cfg.trusted && <button className="btn block" type="button" onClick={remove}>{t("emTrustedRemove")}</button>}
            <button className="btn block" type="button" onClick={() => setEditing(false)}>{t("backHome")}</button>
          </form>
        )}
      </section>
      <section aria-labelledby="em-steps">
        <h2 id="em-steps">{t("emStepsTitle")}</h2>
        <ol><li>{t("emStep1")}</li><li>{t("emStep2")}</li><li>{t("emStep3")}</li></ol>
      </section>
      <button className="btn block" onClick={onBack}>{t("backHome")}</button>
    </>
  );
}
