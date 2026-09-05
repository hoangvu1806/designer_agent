import asyncio
import json
import warnings
from typing import TypeVar
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, ValidationError

from .config import Settings
from .errors import AppError

ModelT = TypeVar("ModelT", bound=BaseModel)
LLM_TIMEOUT_SECONDS = 90
STRUCTURED_PARSER_VERSION = "2026-09-01.3"


def parse_structured_output(content: str, schema: type[ModelT]) -> ModelT:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        return schema.model_validate_json(text)
    except ValidationError as error:
        raise AppError(
            "LLM_OUTPUT_INVALID",
            "The model returned invalid structured JSON",
            str(error),
            502,
            retryable=True,
            action="Retry the run; the response did not match the UI specification schema.",
        ) from error


class AdkProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def structured(self, *, prompt: str, schema: type[ModelT]) -> ModelT:
        if not self.settings.api_key or not self.settings.base_url:
            raise AppError(
                "LLM_NOT_CONFIGURED",
                "Model connection is not configured",
                "Set API_KEY and BASE_URL before creating a design.",
                503,
                action="Update the project .env file, then restart the backend.",
            )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"\[GEMINI_VIA_LITELLM\].*")
            model = LiteLlm(
                model=self.settings.llm_model,
                api_key=self.settings.api_key,
                api_base=self.settings.base_url,
            )
        agent = LlmAgent(
            name="designer_agent",
            model=model,
            instruction=(
                f"{prompt}\n\nJSON SCHEMA (authoritative):\n"
                f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}\n\n"
                "Return exactly one JSON object matching this schema."
            ),
        )
        runner = InMemoryRunner(agent=agent, app_name="agentic_designer")
        user_id = "designer"
        session = await runner.session_service.create_session(
            app_name="agentic_designer", user_id=user_id, session_id=str(uuid4())
        )
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text="Complete the task in the instruction.")],
        )
        final_content: str | None = None
        try:
            async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=message):
                    if event.is_final_response() and event.content and event.content.parts:
                        content = event.content.parts[0].text
                        if content:
                            final_content = content
        except TimeoutError as error:
            raise AppError(
                "LLM_TIMEOUT",
                "The model request timed out",
                f"No structured response after {LLM_TIMEOUT_SECONDS} seconds.",
                504,
                retryable=True,
                action="Retry or choose a faster model.",
            ) from error
        except AppError:
            raise
        except Exception as error:
            raise AppError(
                "LLM_REQUEST_FAILED",
                "The model request failed",
                str(error),
                502,
                retryable=True,
                action="Check API_KEY, BASE_URL, and LLM_MODEL, then retry.",
            ) from error
        finally:
            try:
                await runner.close()
            except Exception:
                pass
        if final_content:
            return parse_structured_output(final_content, schema)
        raise AppError(
            "LLM_OUTPUT_INVALID",
            "The model returned no valid specification",
            "ADK completed without a structured final response.",
            502,
            retryable=True,
            action="Retry the run or choose another model.",
        )
