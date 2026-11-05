"""Small paid-capable synthetic smoke check; no patient inputs or key logging."""

import asyncio
import json
from pathlib import Path

from app.ai import gateway
from app.config import settings
from app.main import EvidenceDraft


async def main():
    results = {"synthetic_only": True, "clinical_validation": False, "checks": {}}
    catalogs = await gateway.catalogs()
    for name, item in catalogs.items():
        results["checks"][name + "_catalog"] = {
            "status": item["status"],
            "models": item["models"],
        }
    tests = [
        (
            "gemini_structured",
            lambda: gateway.intent(
                "Please open the screen where I can change my preferences."
            ),
        ),
        (
            "meta_structured",
            lambda: gateway.structured(
                "meta",
                settings.meta_draft_model,
                "Synthetic source ID demo-1 says: participant requests transport help. Return one neutral observation linked to demo-1, no medical advice.",
                EvidenceDraft.model_json_schema(),
            ),
        ),
    ]
    for name, fn in tests:
        try:
            r = await fn()
            if name == "meta_structured":
                parsed = EvidenceDraft.model_validate(r)
                assert all(i.source_id == "demo-1" for i in parsed.items)
            results["checks"][name] = {
                "status": "passed",
                "model": settings.gemini_routine_model
                if name == "gemini_structured"
                else settings.meta_draft_model,
            }
        except Exception as e:
            results["checks"][name] = {
                "status": "failed",
                "error_type": type(e).__name__,
            }
    try:
        audio = await gateway.synthesize("Open settings.")
        results["checks"]["gemini_tts"] = {
            "status": "passed",
            "bytes": len(audio),
            "model": settings.gemini_tts_model,
        }
        try:
            text = await gateway.transcribe(audio, "audio/wav")
            results["checks"]["meta_asr"] = {
                "status": "passed",
                "transcript_matches": "settings" in text.lower(),
                "model": settings.meta_transcribe_model,
            }
        except Exception as e:
            results["checks"]["meta_asr"] = {
                "status": "failed",
                "error_type": type(e).__name__,
            }
    except Exception as e:
        results["checks"]["gemini_tts"] = {
            "status": "failed",
            "error_type": type(e).__name__,
        }
    Path("test-results").mkdir(exist_ok=True)
    Path("test-results/provider-smoke.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: {a: b for a, b in v.items() if a != "models"}
                for k, v in results["checks"].items()
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
