"""Every emergency sentence in the benchmark set (English and Arabic) must open the help screen. False alarms are tolerated by design
(one tap back), but are capped so the rule cannot drift into firing on everything. See docs/EMERGENCY_BENCHMARK.md."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("emergency_bench", Path(__file__).resolve().parents[1] / "eval" / "run_emergency_benchmark.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


def test_no_emergency_sentence_is_missed_and_false_alarms_stay_rare():
    stats, wrong = bench.run()
    assert [w["text"] for w in wrong if w["result"] == "missed"] == []
    fp = sum(s["fp"] for s in stats.values())
    neg = sum(s["fp"] + s["tn"] for s in stats.values())
    assert neg >= 30 and fp / neg <= 0.10


def test_ordinary_sentences_that_look_close_do_not_fire():
    from app import assistant as A
    for t in ("I fell asleep early", "I fell behind on my tasks", "what is on today", "open the well-being questions", "شربت الماء"):
        assert A.parse(t, [], {}).get("tool") != "emergency", t
