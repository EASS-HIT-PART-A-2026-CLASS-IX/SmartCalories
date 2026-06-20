"""Nutrition math: TDEE, macro budgets, streaks, etc. Pure functions only."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable


def mifflin_st_jeor(weight_kg: float, height_cm: float, age_years: int, sex: str) -> int:
    """Basal metabolic rate (BMR) via Mifflin-St Jeor."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age_years
    return int(round(base + (5 if sex.lower() == "male" else -161)))


_ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def tdee(bmr: int, activity_level: str) -> int:
    factor = _ACTIVITY_FACTORS.get(activity_level.lower(), 1.4)
    return int(round(bmr * factor))


def suggest_macros(daily_kcal: int, protein_per_kg: float = 1.6, weight_kg: float = 70) -> dict[str, float]:
    """Reasonable defaults: protein from body weight, fat ~25% of kcal, carbs fill the rest."""
    protein_g = round(protein_per_kg * weight_kg, 1)
    fat_g = round(daily_kcal * 0.25 / 9, 1)
    remaining_kcal = max(0, daily_kcal - protein_g * 4 - fat_g * 9)
    carb_g = round(remaining_kcal / 4, 1)
    return {"protein_g": protein_g, "carb_g": carb_g, "fat_g": fat_g}


def aggregate(rows: Iterable) -> dict[str, float]:
    """Sum kcal/macros over an iterable of FoodEntry-like rows with .calories/.protein_g/.carb_g/.fat_g."""
    totals = {"calories": 0, "protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0}
    for r in rows:
        totals["calories"] += r.calories
        totals["protein_g"] += r.protein_g
        totals["carb_g"] += r.carb_g
        totals["fat_g"] += r.fat_g
    return totals


def streak_from_dates(eaten_dates: set[date], today: date | None = None) -> int:
    """Count consecutive days back from today with at least one entry."""
    today = today or datetime.now(timezone.utc).date()
    count = 0
    cursor = today
    while cursor in eaten_dates:
        count += 1
        cursor -= timedelta(days=1)
    return count
