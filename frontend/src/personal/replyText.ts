import type { AssistantItem, AssistantReply } from "../api";
import type { Key, T } from "../i18n";

/** What the assistant said, as plain sentences. Shared by the Ask screen and the voice companion so both show and say the same words. */
export const itemTitle = (t: T, i: AssistantItem) => [i.title, t.lang === "ar" ? i.text_ar ?? i.text_en : i.text_en ?? i.text_ar].filter(Boolean).join(": ");
const confirmLine = (t: T, r: AssistantReply) => t(r.tool === "mark_done" ? "asConfirmDone" : r.tool === "mark_not_today" ? "asConfirmNot" : "asConfirmSnooze", { n: r.minutes ?? 0 });
const answerWord = (t: T, a: string | null) => (a === "done" ? t("remDone") : a === "not_today" ? t("remNotToday") : "—");

  /** What the bot said, as plain sentences (used for display of text-only parts and for reading aloud). */
export function replySentences(t: T, r: AssistantReply): string[] {
    const out: string[] = [];
    if (!r.understood) {
      out.push(t(r.reason === "which" ? "asWhich" : (`as${r.reason![0].toUpperCase()}${r.reason!.slice(1)}` as Key)));
    } else if (r.cancelled) out.push(t("asCancelled"));
    else if (r.confirmed) out.push(r.ok === false ? t("asTooLate") : t("asDoneOk"));
    else if (r.tool === "chat") out.push(t(r.kind === "greeting" ? "asGreeting" : r.kind === "thanks" ? "asThanks" : "asCapabilities"));
    else if (r.tool === "recall") out.push(r.said ? t("asRecall", { said: r.said }) : t("asRecallNone"));
    else if (r.tool === "recap") out.push(r.entries?.length ? t("asRecap") : t("asRecapNone"));
    else if (r.tool === "emergency") out.push(t("asUrgentOpen"));
    else if (r.navigate) out.push(t("asOpening"));
    else if (r.tool === "read_today" && !r.items?.length) out.push(t("asNone"));
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
