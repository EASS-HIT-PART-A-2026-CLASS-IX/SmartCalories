"""Gemini-vision-powered nutrition extraction from a meal photo.

Production uses a separate Pydantic AI agent typed to return `NutritionExtraction`.
Tests override `_vision_agent` (via `vision_agent_for_tests`) to bypass the LLM.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent

from ..config import get_settings


class NutritionExtraction(BaseModel):
    """Compact nutrition shell shared with `services/openfoodfacts.py`."""

    name: str = Field(description="Best guess of the dish or ingredient")
    calories: int = Field(ge=0)
    protein_g: float = Field(default=0.0, ge=0)
    carb_g: float = Field(default=0.0, ge=0)
    fat_g: float = Field(default=0.0, ge=0)
    serving_qty: float = 1.0
    serving_unit: str = "serving"
    confidence: float = Field(default=0.5, ge=0, le=1)
    note: str | None = None


SYSTEM = (
    "You are a nutrition vision specialist. Given a photo, identify the food and estimate "
    "calories + macros for the visible serving. If unsure, set a low confidence. Never invent "
    "specific brand details. Output strictly the structured JSON."
)


def _build_vision_model():
    settings = get_settings()
    if settings.gemini_api_key:
        from pydantic_ai.models.fallback import FallbackModel
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key=settings.gemini_api_key)
        # Vision requires multimodal-capable models. 1.5-flash → 2.0-flash → 2.5-flash → 2.5-pro.
        chain = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
        ]
        models = [GoogleModel(name, provider=provider) for name in chain]
        return FallbackModel(*models) if len(models) > 1 else models[0]
    from pydantic_ai.models.test import TestModel

    return TestModel(
        custom_output_args={
            "name": "Unknown food (test mode)",
            "calories": 0,
            "protein_g": 0,
            "carb_g": 0,
            "fat_g": 0,
            "confidence": 0.0,
            "note": "Set GEMINI_API_KEY for real analysis.",
        }
    )


_vision_agent: Agent[None, NutritionExtraction] = Agent(
    _build_vision_model(),
    output_type=NutritionExtraction,
    system_prompt=SYSTEM,
)


async def analyze_image(image_path: Path | str) -> NutritionExtraction:
    """Analyse an image file and return structured nutrition. Override in tests."""
    path = Path(image_path)
    image_bytes = path.read_bytes()
    media_type = "image/jpeg"
    if path.suffix.lower() == ".png":
        media_type = "image/png"
    elif path.suffix.lower() == ".webp":
        media_type = "image/webp"

    result = await _vision_agent.run(
        [
            "Identify this food and estimate nutrition for the visible portion.",
            BinaryContent(data=image_bytes, media_type=media_type),
        ]
    )
    return result.output


def get_vision_agent() -> Agent:
    """Exposed so tests can `vision.get_vision_agent().override(model=...)`."""
    return _vision_agent
