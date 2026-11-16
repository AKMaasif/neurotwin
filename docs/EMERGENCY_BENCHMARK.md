# Emergency-phrase benchmark

**There is no fresh held-out set yet for the current rule; write one before quoting a held-out figure.**


Run on 2026-11-16 by `backend/eval/run_emergency_benchmark.py` (sentences: `backend/eval/emergency_set.jsonl`).

## What this measures, and what it does not

When a person types or says something that sounds like an emergency, the assistant must open the help screen (local
emergency numbers and the person's trusted contact) **before anything else**, without a language model. This benchmark
checks that fixed rule on English and Arabic sentences.

- **Sensitivity**: of the emergency sentences, how many opened the help screen. **Specificity**: of the ordinary
  sentences, how many did not.
- **dev** sentences have been used to tune the rule. **held-out** sentences are written after a rule change and run
  once; whatever they miss is recorded below, then fixed, and they move into dev. So the current held-out line is only
  meaningful when it is a fresh set: see the history.
- All sentences were written by the build team, not by older adults, and are typed text: speech recognition errors are
  not included. Small sets give wide confidence intervals (Wilson, 95%). This is a software safety check, not a
  clinical or triage accuracy figure. The app never calls anyone and never says help is coming.
- The rule deliberately errs towards opening the help screen: a false alarm costs one tap back; a miss could cost more.

## Results

| Set | Sensitivity (emergencies caught) | Specificity (ordinary sentences left alone) |
|---|---|---|
| dev | 112/112 = 100% (95% CI 97–100%) | 77/80 = 96% (95% CI 90–99%) |
| held-out | — | — |

## Sentences handled wrongly (current rule)

- dev, en: "help me find my report" — false alarm
- dev, en: "is it urgent to take my medicine" — false alarm
- dev, en: "can you help me understand my results" — false alarm

## History of held-out runs (each set seen once, before it was used for tuning)

| Date | Rule version | Held-out sensitivity | Held-out specificity | Missed, then fixed |
|---|---|---|---|---|
| 2026-11-16 | round 1 | 17/20 = 85% (95% CI 64–95%) | 13/15 = 87% (95% CI 62–96%) | "please help", "I think I'm having a heart attack", "النجدة" (false alarm "I fell behind on my tasks") |
| 2026-11-16 | round 2 | 18/20 = 90% (95% CI 70–97%) | 15/15 = 100% (95% CI 80–100%) | "pain in my chest", "عندي ألم شديد في الصدر" |
| 2026-11-16 | round 3 (wider wording: collapse, stroke signs, overdose, bleeding, dialect) | 8/20 = 40% (95% CI 22–61%) | 14/15 = 93% (95% CI 70–99%) | "I can't get up off the floor", "my husband has collapsed", "I'm struggling to breathe", "my face is drooping and my arm feels weak", "I tripped and hit my head, it's bleeding", "help help", "I feel like I'm going to pass out", "I took too many of my pills", "أبي سقط على الأرض", "صدري يؤلمني جدا", "أحس إني راح يغمى علي", "عندي ضيق تنفس شديد" (false alarm "I fell in love with this garden") |
| 2026-11-16 | round 4 (deliberately new kinds: seizure, self-harm, SOS, emergency numbers, "need a doctor now", someone not moving, Gulf dialect) | 0/20 = 0% (95% CI 0–16%) | 14/15 = 93% (95% CI 70–99%) | all 20, e.g. "I'm having a seizure", "I want to end my life", "please call 999", "أمي ما ترد ولا تتحرك", "أبغى أموت" (false alarm "I had a stroke of luck") |

Before round 1, the original rule missed 8 of 32 dev emergency sentences, including "Help!", "I'm hurt", "my chest
hurts", "لا أستطيع التنفس" and "سقطت", and wrongly fired on "I fell asleep early".

**What the held-out rounds show.** The rule is a word list. It catches the kinds of wording it has seen (100% on
the tuning set) but generalises poorly to new kinds: round 4 was written deliberately from situations the list had
never covered and caught none of them. The dev figure must therefore not be read as "100% emergency detection". The
word list is a fast first line, not the only route to help: the urgent-help button is shown on every screen of the personal app (one tap, no words needed),
and a pilot needs real wording from older adults and a clinically reviewed list of situations. Being cautious, it also
fires on some everyday sentences that contain an alarming word (for example "dizzy", or "أموت" in a figure of
speech); a false alarm costs one tap back.

## Next steps

Collect real wording from older adults and family members in both languages (spoken and typed), add regional Arabic
dialect forms, and repeat after speech-to-text so recognition errors are counted.
