"""Pydantic AI tools — the canonical actions the agent can take.

These are also re-exported by the MCP server (Phase 14) so external clients
(Claude Desktop, etc.) can drive the same diary operations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic_ai import RunContext
from sqlmodel import select

from ..models import (
    FoodEntry,
    Meal,
    Source,
    UserGoals,
    WaterLog,
)
from ..services import nutrition as nut
from .agent import AgentDeps, agent


def _meal_from_str(value: str | None) -> Meal:
    if not value:
        return Meal.snack
    try:
        return Meal(value.strip().lower())
    except ValueError:
        return Meal.snack


@agent.tool
def log_food(
    ctx: RunContext[AgentDeps],
    name: str,
    calories: int,
    meal: str = "snack",
    protein_g: float = 0.0,
    carb_g: float = 0.0,
    fat_g: float = 0.0,
    notes: str | None = None,
) -> dict:
    """Log a food entry for the user. Returns the created entry id and remaining daily budget."""
    with ctx.deps.db_lock:
        entry = FoodEntry(
            user_uid=ctx.deps.user.uid,
            name=name.strip(),
            calories=calories,
            protein_g=protein_g,
            carb_g=carb_g,
            fat_g=fat_g,
            meal=_meal_from_str(meal),
            source=Source.agent,
            notes=notes,
        )
        ctx.deps.session.add(entry)
        ctx.deps.session.commit()
        ctx.deps.session.refresh(entry)
        return {
            "id": entry.id,
            "name": entry.name,
            "calories": entry.calories,
            "meal": entry.meal.value if isinstance(entry.meal, Meal) else str(entry.meal),
        }


@agent.tool
def get_macros_today(ctx: RunContext[AgentDeps]) -> dict:
    """Return today's total kcal/protein/carb/fat plus the user's goals if set."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with ctx.deps.db_lock:
        rows = ctx.deps.session.exec(
            select(FoodEntry)
            .where(FoodEntry.user_uid == ctx.deps.user.uid)
            .where(FoodEntry.eaten_at >= today)
        ).all()
        totals = nut.aggregate(rows)
        goals = ctx.deps.session.get(UserGoals, ctx.deps.user.uid)
    return {
        "calories": int(totals["calories"]),
        "protein_g": totals["protein_g"],
        "carb_g": totals["carb_g"],
        "fat_g": totals["fat_g"],
        "target_kcal": goals.daily_kcal if goals else None,
        "target_protein_g": goals.protein_g if goals else None,
        "target_carb_g": goals.carb_g if goals else None,
        "target_fat_g": goals.fat_g if goals else None,
    }


@agent.tool
def get_remaining_budget(ctx: RunContext[AgentDeps]) -> dict:
    """How many calories and macros are still available today before hitting goals."""
    snap = get_macros_today(ctx)
    if snap.get("target_kcal") is None:
        return {"message": "No daily calorie goal set. Use set_goal to configure one.", **snap}
    return {
        "remaining_kcal": max(0, (snap["target_kcal"] or 0) - snap["calories"]),
        "remaining_protein_g": max(0, (snap.get("target_protein_g") or 0) - snap["protein_g"]),
        "remaining_carb_g": max(0, (snap.get("target_carb_g") or 0) - snap["carb_g"]),
        "remaining_fat_g": max(0, (snap.get("target_fat_g") or 0) - snap["fat_g"]),
    }


@agent.tool
def get_streak(ctx: RunContext[AgentDeps]) -> dict:
    with ctx.deps.db_lock:
        rows = ctx.deps.session.exec(
            select(FoodEntry.eaten_at).where(FoodEntry.user_uid == ctx.deps.user.uid)
        ).all()
    eaten_dates: set = set()
    for r in rows:
        dt = r if isinstance(r, datetime) else r[0]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        eaten_dates.add(dt.date())
    return {"days": nut.streak_from_dates(eaten_dates)}


@agent.tool
def add_water(ctx: RunContext[AgentDeps], ml: int = 250) -> dict:
    """Log a water intake in ml. Default is one 250ml glass."""
    with ctx.deps.db_lock:
        row = WaterLog(user_uid=ctx.deps.user.uid, ml=ml)
        ctx.deps.session.add(row)
        ctx.deps.session.commit()
        ctx.deps.session.refresh(row)
        return {"id": row.id, "ml": row.ml}


@agent.tool
def get_user_goals(ctx: RunContext[AgentDeps]) -> dict:
    with ctx.deps.db_lock:
        goals = ctx.deps.session.get(UserGoals, ctx.deps.user.uid)
    if goals is None:
        return {"daily_kcal": None}
    return {
        "daily_kcal": goals.daily_kcal,
        "protein_g": goals.protein_g,
        "carb_g": goals.carb_g,
        "fat_g": goals.fat_g,
        "dietary_filters": goals.dietary_filters,
    }


@agent.tool
def set_goal(
    ctx: RunContext[AgentDeps],
    daily_kcal: int | None = None,
    protein_g: float | None = None,
    carb_g: float | None = None,
    fat_g: float | None = None,
) -> dict:
    """Update the user's daily kcal and macro targets. Only fields you pass are changed."""
    with ctx.deps.db_lock:
        goals = ctx.deps.session.get(UserGoals, ctx.deps.user.uid)
        if goals is None:
            goals = UserGoals(user_uid=ctx.deps.user.uid)
        for field, value in dict(
            daily_kcal=daily_kcal, protein_g=protein_g, carb_g=carb_g, fat_g=fat_g
        ).items():
            if value is not None:
                setattr(goals, field, value)
        ctx.deps.session.add(goals)
        ctx.deps.session.commit()
        ctx.deps.session.refresh(goals)
    return get_user_goals(ctx)


@agent.tool
def compute_tdee(
    ctx: RunContext[AgentDeps],
    weight_kg: float,
    height_cm: float,
    age_years: int,
    sex: str,
    activity_level: str = "moderate",
) -> dict:
    bmr = nut.mifflin_st_jeor(weight_kg, height_cm, age_years, sex)
    daily = nut.tdee(bmr, activity_level)
    return {
        "bmr": bmr,
        "tdee": daily,
        "suggested_macros": nut.suggest_macros(daily, weight_kg=weight_kg),
    }


@agent.tool
async def analyze_image_tool(ctx: RunContext[AgentDeps], image_path: str) -> dict:
    """Analyze a previously-uploaded meal photo at `image_path` and return parsed nutrition."""
    from . import vision

    extraction = await vision.analyze_image(image_path)
    return extraction.model_dump()
