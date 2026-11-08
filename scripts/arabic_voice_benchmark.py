"""Optional live smoke test with generated generic Arabic commands, never patient audio."""

import asyncio
import json

from app.ai import ProviderUnavailable, gateway
from app.arabic import command, normalize
from app.config import ROOT

PHRASES = ["افتح الإعدادات", "كبر الخط", "توقف"]


def word_error(reference, hypothesis):
    a, b = normalize(reference).split(), normalize(hypothesis).split()
    costs = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, costs = costs, [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            costs[j] = min(
                costs[j - 1] + 1, previous[j] + 1, previous[j - 1] + (x != y)
            )
    return costs[-1] / max(1, len(a))


async def main():
    folder = ROOT / "test-results" / "arabic-live-voice"
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    for i, phrase in enumerate(PHRASES):
        try:
            audio = await gateway.synthesize(phrase)
            (folder / f"synthetic-command-{i + 1}.wav").write_bytes(audio)
            transcript = await gateway.transcribe_arabic(audio, "audio/wav")
            cases.append(
                dict(
                    source="generated synthetic speech",
                    word_error_rate=word_error(phrase, transcript),
                    command_match=command(phrase) == command(transcript),
                    provider_status="responded",
                )
            )
        except ProviderUnavailable:
            cases.append(dict(provider_status="unavailable", command_match=None))
            break
    report = dict(
        cases=cases,
        planned_cases=len(PHRASES),
        completed=sum(c["provider_status"] == "responded" for c in cases),
        command_matches=sum(c.get("command_match") is True for c in cases),
        older_adult_validation=False,
        gulf_dialect_validation=False,
        browser_voice_quality_validation=False,
        qualified_language_review=False,
    )
    (folder / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())
