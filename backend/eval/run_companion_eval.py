"""Text-understanding evaluation for the assistant's fixed rules (typed sentences, before any action).
Usage: python eval/run_companion_eval.py dev|final [--json out.json]

What this measures: whether the typed-or-transcribed sentence is mapped to the right allowed action and task. It does NOT measure speech
recognition, voice activity detection, text-to-speech, accessibility, or usefulness for real older adults. Sentences were written by the
developer, so they are an optimistic test; a real evaluation needs sentences recorded from the intended users."""
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import assistant as A  # noqa: E402

ROWS = [
    (SimpleNamespace(id=1, title="Morning walk", text_en="Walk for ten minutes after breakfast", text_ar="المشي لمدة عشر دقائق بعد الفطور"), {"reply": None, "snoozed_until": None}),
    (SimpleNamespace(id=2, title="Water", text_en="Drink a glass of water", text_ar="شرب كوب من الماء"), {"reply": None, "snoozed_until": None}),
]
CHANGES = {"mark_done", "mark_not_today", "snooze"}
NAMES = {"walk": 1, "water": 2}


def predict(case: dict) -> dict:
    ctx = case.get("ctx") or {}
    ctx = {**ctx, "last_item": NAMES.get(ctx.get("last_item"), ctx.get("last_item"))}
    p = A.parse(case["text"], ROWS, ctx)
    if "special" in p or p.get("tool") is None:
        return {"tool": None}
    a = p.get("arguments", {})
    return {"tool": p["tool"], "item": a.get("item_id"), "screen": a.get("screen"), "minutes": a.get("minutes")}


def judge(case: dict, got: dict) -> str:
    e = case["expect"]
    if e["tool"] is None:
        return "ok" if got["tool"] is None else ("unsafe_action" if got["tool"] in CHANGES else "acted_when_it_should_ask")
    if got["tool"] is None:
        return "missed"
    if got["tool"] != e["tool"]:
        return "unsafe_action" if got["tool"] in CHANGES else "wrong_tool"
    for k in ("item", "screen", "minutes"):
        if e.get(k) is not None and got.get(k) != e[k]:
            return "unsafe_action" if got["tool"] in CHANGES else "wrong_target"
    return "ok"


def main(which: str, out: str | None) -> None:
    cases = [json.loads(x) for x in (Path(__file__).parent / f"companion_{which}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    res, bad = Counter(), []
    by_lang: dict[str, Counter] = {"en": Counter(), "ar": Counter()}
    for c in cases:
        got = predict(c)
        v = judge(c, got)
        res[v] += 1; by_lang[c["lang"]][v] += 1
        if v != "ok":
            bad.append({"text": c["text"], "lang": c["lang"], "expected": c["expect"], "got": got, "result": v})
    n = len(cases)
    summary = {"set": which, "n": n, "correct": res["ok"], "accuracy": round(res["ok"] / n, 3), "counts": dict(res),
               "by_language": {k: {"n": sum(v.values()), "correct": v["ok"]} for k, v in by_lang.items()}, "failures": bad}
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, ensure_ascii=False, indent=1))
    for b in bad:
        print(" ✗", b["result"], "|", b["text"], "| expected", b["expected"]["tool"], b["expected"].get("item"), "| got", b["got"])
    if out:
        Path(out).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
