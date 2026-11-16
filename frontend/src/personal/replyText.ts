import type { AssistantItem, AssistantReply } from "../api";
import type { Key, T } from "../i18n";

/** What the assistant said, as plain sentences. Shared by the Ask screen and the voice companion so both show and say the same words. */
export const itemTitle = (t: T, i: AssistantItem) => [i.title, t.lang === "ar" ? i.text_ar ?? i.text_en : i.text_en ?? i.text_ar].filter(Boolean).join(": ");
const confirmLine = (t: T, r: AssistantReply) => t(r.tool === "mark_done" ? "asConfirmDone" : r.tool === "mark_not_today" ? "asConfirmNot" : "asConfirmSnooze", { n: r.minutes ?? 0 });
const answerWord = (t: T, a: string | null) => (a === "done" ? t("remDone") : a === "not_today" ? t("remNotToday") : "—");

/** Replies whose words are fixed here, never model text (docs/ASSISTANT_WORKFLOW.md, section 3). */
const FIXED: Partial<Record<string, Key>> = { my_health: "asMyHealth", not_allowed: "asNotAllowed", make_image: "asImageSoon", blocked: "asBlocked" };
const AI_WHY: Record<"off" | "needs_consent" | "real_data", Key> = { off: "asAiOff", needs_consent: "asAiNeedsConsent", real_data: "asAiRealData" };

/** What to say aloud: the model's plain spoken version when there is one (no lists or symbols), otherwise the screen sentences. */
export function replySpeech(t: T, r: AssistantReply): string {
  if ((r.tool === "answer" || r.tool === "plan") && r.speech && !(r.kind && FIXED[r.kind])) return r.speech;
  return replySentences(t, r).join(". ");
}

/** The language the reply is written in: a model answer follows the person's message, even when the screen is in the other language. */
export const replyLang = (t: T, r: AssistantReply): "en" | "ar" => (r.tool === "answer" || r.tool === "plan") && r.lang && !(r.kind && FIXED[r.kind]) ? r.lang : t.lang;

  /** What the bot said, as plain sentences (used for display of text-only parts and for reading aloud). */
export function replySentences(t: T, r: AssistantReply): string[] {
    const out: string[] = [];
    if (!r.understood) {
      out.push(t(r.reason === "which" ? "asWhich" : (`as${r.reason![0].toUpperCase()}${r.reason!.slice(1)}` as Key)));
      if (r.reason === "not_understood" && r.ai && r.ai !== "on") out.push(t(AI_WHY[r.ai]));
    } else if (r.tool === "answer" || r.tool === "plan") {
      const fixed = r.kind ? FIXED[r.kind] : undefined;
      if (fixed) out.push(t(fixed));
      else if (r.text) out.push(...r.text.split(/\n+/).map((l) => l.trim()).filter(Boolean));
      r.plan?.forEach((p) => out.push(`${p.time}  ${p.activity}`));
    } else if (r.cancelled) out.push(t("asCancelled"));
    else if (r.confirmed) out.push(r.ok === false ? t("asTooLate") : t("asDoneOk"));
    else if (r.tool === "chat") out.push(t(r.kind === "greeting" ? "asGreeting" : r.kind === "thanks" ? "asThanks" : "asCapabilities"));
    else if (r.tool === "recall") out.push(r.said ? t("asRecall", { said: r.said }) : t("asRecallNone"));
    else if (r.tool === "recap") out.push(r.entries?.length ? t("asRecap") : t("asRecapNone"));
    else if (r.tool === "emergency") out.push(t("asUrgentOpen"));
    else if (r.tool === "ask_urgent") out.push(t("asAskUrgent"));
    else if (r.tool === "urgent_declined") out.push(t("asUrgentDeclined"));
    else if (r.navigate) out.push(t("asOpening"));
    else if (r.tool === "read_today" && !r.items?.length) out.push(t("asNone"));
    if (r.urgent_declined) out.unshift(t("asUrgentDeclinedThen"));
    if ((r.via === "context" || r.via === "answer") && r.item) out.unshift(t(r.via === "context" ? "asVia_context" : "asVia_answer", { what: itemTitle(t, r.item) }));
    if (r.needs_confirmation && r.item) out.push(...(r.already ? [t("asAlready", { answer: answerWord(t, r.already) })] : []), confirmLine(t, r), itemTitle(t, r.item));
    r.items?.forEach((i) => out.push(`${i.time_hhmm ? `${i.time_hhmm}, ` : ""}${itemTitle(t, i)}`));
    r.entries?.forEach((e) => out.push(`${itemTitle(t, e.item)}: ${answerWord(t, e.reply)}`));
    if (!r.needs_confirmation && r.item && !r.confirmed && !r.cancelled && r.tool === "explain_instruction") {
      const i = r.item;
      out.push([i.time_hhmm, i.quantity != null && i.unit ? `${i.quantity} ${i.unit}` : null, i.precautions, t("remFrom", { who: i.written_by ?? "" })].filter(Boolean).join(" · "));
    }
    return out;
  }
