import argparse
import asyncio
import json
from typing import Any

from app.core.config import Settings
from app.infrastructure.groq import GroqAdapter
from app.modules.llm.gateway import LLMProviderError, StructuredGenerationRequest


async def discover(smoke: bool) -> int:
    settings = Settings()
    adapter = GroqAdapter(settings)
    report: dict[str, Any] = {
        "provider": "groq",
        "configured_model": settings.groq_model,
        "reasoning_effort": settings.groq_reasoning_effort,
        "api_key_configured": bool(settings.groq_api_key.get_secret_value()),
    }
    try:
        models = await adapter.model_info()
        report["models"] = [item.model_dump() for item in sorted(models, key=lambda x: x.model_id)]
        report["configured_model_present"] = any(
            item.model_id == settings.groq_model and item.active for item in models
        )
        if smoke and report["configured_model_present"]:
            result = await adapter.generate_structured(
                StructuredGenerationRequest(
                    schema_name="careerpilot_model_smoke",
                    schema_definition={
                        "type": "object",
                        "properties": {"status": {"type": "string", "enum": ["PASS"]}},
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                    system_prompt="Return only the required structured result.",
                    user_payload="Return PASS.",
                )
            )
            report["smoke"] = {
                "status": "PASS" if result.value == {"status": "PASS"} else "FAIL",
                "structured_output": "strict_json_schema",
                "metadata": result.metadata.model_dump(),
            }
        elif smoke:
            report["smoke"] = {"status": "FAIL", "reason": "MODEL_UNAVAILABLE"}
        report["status"] = (
            "PASS"
            if report["configured_model_present"]
            and (not smoke or report["smoke"]["status"] == "PASS")
            else "FAIL"
        )
    except LLMProviderError as exc:
        report.update({"status": "FAIL", "error_category": exc.category})
    finally:
        await adapter.close()
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("status") == "PASS" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitized Groq discovery for CareerPilot")
    parser.add_argument("--smoke", action="store_true", help="also run a strict-schema smoke test")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(discover(args.smoke)))


if __name__ == "__main__":
    main()
