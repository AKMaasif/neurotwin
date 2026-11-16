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
| dev | 72/72 = 100% (95% CI 95–100%) | 47/50 = 94% (95% CI 84–98%) |
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

Before round 1, the original rule missed 8 of 32 dev emergency sentences, including "Help!", "I'm hurt", "my chest
hurts", "لا أستطيع التنفس" and "سقطت", and wrongly fired on "I fell asleep early".

## Next steps

Collect real wording from older adults and family members in both languages (spoken and typed), add regional Arabic
dialect forms, and repeat after speech-to-text so recognition errors are counted.
