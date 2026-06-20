from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .models import Meal, Source


class FoodEntryCreate(BaseModel):
    """EX1-compatible payload. Extra macro/meal fields are optional and default to safe values."""

    name: str = Field(min_length=1, max_length=200)
    calories: int = Field(ge=0, le=50_000)
    meal: str = Field(min_length=1, max_length=40)
    protein_g: float = Field(default=0.0, ge=0)
    carb_g: float = Field(default=0.0, ge=0)
    fat_g: float = Field(default=0.0, ge=0)
    serving_qty: float = Field(default=1.0, ge=0)
    serving_unit: str = Field(default="serving", max_length=40)
    eaten_at: datetime | None = None
    source: Source = Source.manual
    notes: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "FoodEntryCreate":
        self.name = self.name.strip()
        self.meal = self.meal.strip().title()
        return self


def _meal_to_display(meal: Meal | str) -> str:
    if isinstance(meal, Meal):
        return meal.value.title()
    return str(meal).title()


# --- User-facing DTOs (Phase 2) ---


class UserRead(BaseModel):
    uid: str
    email: str | None
    display_name: str | None
    is_anonymous: bool
    role: str
    timezone: str | None
    locale: str | None


class UserPatch(BaseModel):
    display_name: str | None = None
    timezone: str | None = None
    locale: str | None = None


class GoalsRead(BaseModel):
    daily_kcal: int | None = None
    protein_g: float | None = None
    carb_g: float | None = None
    fat_g: float | None = None
    tdee: int | None = None
    activity_level: str | None = None
    dietary_filters: list[str] = Field(default_factory=list)
    weight_kg: float | None = None
    height_cm: float | None = None
    sex: str | None = None


class GoalsUpsert(GoalsRead):
    pass


class PreferencesRead(BaseModel):
    theme: str = "system"
    language: str = "en"
    units: str = "metric"
    notifications: dict[str, Any] = Field(default_factory=dict)


class PreferencesUpsert(PreferencesRead):
    pass


# --- Diary / domain DTOs (Phase 4) ---


class DiaryEntryRead(BaseModel):
    id: int
    name: str
    calories: int
    protein_g: float
    carb_g: float
    fat_g: float
    serving_qty: float
    serving_unit: str
    meal: str
    eaten_at: datetime
    source: Source
    image_path: str | None
    barcode: str | None
    notes: str | None

    @classmethod
    def from_orm_row(cls, row) -> "DiaryEntryRead":
        return cls(
            id=row.id,
            name=row.name,
            calories=row.calories,
            protein_g=row.protein_g,
            carb_g=row.carb_g,
            fat_g=row.fat_g,
            serving_qty=row.serving_qty,
            serving_unit=row.serving_unit,
            meal=_meal_to_display(row.meal),
            eaten_at=row.eaten_at,
            source=row.source,
            image_path=row.image_path,
            barcode=row.barcode,
            notes=row.notes,
        )


class DiaryEntryPatch(BaseModel):
    name: str | None = None
    calories: int | None = None
    protein_g: float | None = None
    carb_g: float | None = None
    fat_g: float | None = None
    serving_qty: float | None = None
    serving_unit: str | None = None
    meal: str | None = None
    eaten_at: datetime | None = None
    notes: str | None = None


class MacrosSnapshot(BaseModel):
    date: str  # ISO date
    calories: int = 0
    protein_g: float = 0.0
    carb_g: float = 0.0
    fat_g: float = 0.0
    target_kcal: int | None = None
    target_protein_g: float | None = None
    target_carb_g: float | None = None
    target_fat_g: float | None = None


class StreakInfo(BaseModel):
    days: int


class TDEERequest(BaseModel):
    weight_kg: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    age_years: int = Field(gt=0, le=120)
    sex: str
    activity_level: str = "moderate"


class TDEEResponse(BaseModel):
    bmr: int
    tdee: int
    suggested_macros: dict[str, float]


class WaterLogCreate(BaseModel):
    ml: int = Field(ge=0, le=10_000)


class LogRangeRead(BaseModel):
    water_ml_total: int
