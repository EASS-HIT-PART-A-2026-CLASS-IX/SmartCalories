"""smolagents tools — the canonical actions the chat agent can take.

Each tool is a `Tool` subclass built per-request (see `agent.build_agent`) so it closes over
the request's SQLModel `session` and authenticated `user`. smolagents executes tool calls
sequentially within a single `agent.run`, so no cross-tool DB lock is needed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from smolagents import Tool
from sqlmodel import Session, select

from ..models import (
    FoodEntry,
    Meal,
    Source,
    User,
    UserGoals,
    WaterLog,
)
from ..services import nutrition as nut

logger = logging.getLogger(__name__)


def _meal_from_str(value: str | None) -> Meal:
    if not value:
        return Meal.snack
    try:
        return Meal(value.strip().lower())
    except ValueError:
        return Meal.snack


def _macros_today(session: Session, user: User) -> dict:
    """Shared by the macros + remaining-budget tools."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = session.exec(
        select(FoodEntry)
        .where(FoodEntry.user_uid == user.uid)
        .where(FoodEntry.eaten_at >= today)
    ).all()
    totals = nut.aggregate(rows)
    goals = session.get(UserGoals, user.uid)
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


class _RequestTool(Tool):
    """Base for tools that need the request's DB session + user."""

    def __init__(self, session: Session, user: User):
        self.session = session
        self.user = user
        super().__init__()


class LogFoodTool(_RequestTool):
    name = "log_food"
    description = (
        "Log a food entry to the user's diary. Returns the created entry id, name, calories "
        "and meal. Use this whenever the user says they ate something."
    )
    inputs = {
        "name": {"type": "string", "description": "Food name, e.g. 'scrambled eggs'."},
        "calories": {"type": "integer", "description": "Total calories for the portion."},
        "meal": {
            "type": "string",
            "description": "One of breakfast, lunch, dinner, snack. Defaults to snack.",
            "nullable": True,
        },
        "protein_g": {"type": "number", "description": "Protein grams.", "nullable": True},
        "carb_g": {"type": "number", "description": "Carb grams.", "nullable": True},
        "fat_g": {"type": "number", "description": "Fat grams.", "nullable": True},
        "notes": {"type": "string", "description": "Optional note.", "nullable": True},
    }
    output_type = "object"

    def forward(
        self,
        name: str,
        calories: int,
        meal: str | None = None,
        protein_g: float | None = None,
        carb_g: float | None = None,
        fat_g: float | None = None,
        notes: str | None = None,
    ) -> dict:
        entry = FoodEntry(
            user_uid=self.user.uid,
            name=name.strip(),
            calories=int(calories),
            protein_g=protein_g or 0.0,
            carb_g=carb_g or 0.0,
            fat_g=fat_g or 0.0,
            meal=_meal_from_str(meal),
            source=Source.agent,
            notes=notes,
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return {
            "id": entry.id,
            "name": entry.name,
            "calories": entry.calories,
            "meal": entry.meal.value if isinstance(entry.meal, Meal) else str(entry.meal),
        }


def _entry_summary(e: FoodEntry) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "calories": e.calories,
        "protein_g": e.protein_g,
        "carb_g": e.carb_g,
        "fat_g": e.fat_g,
        "meal": e.meal.value if isinstance(e.meal, Meal) else str(e.meal),
        "eaten_at": e.eaten_at.isoformat() if isinstance(e.eaten_at, datetime) else str(e.eaten_at),
    }


class ListRecentFoodsTool(_RequestTool):
    name = "list_recent_foods"
    description = (
        "List the user's most recently logged food entries with their ids. Call this FIRST when "
        "the user wants to edit or delete something they logged (e.g. 'change my breakfast', "
        "'remove the apple') so you know which entry id to pass to update_food / delete_food."
    )
    inputs = {
        "limit": {
            "type": "integer",
            "description": "How many recent entries to return (default 10, max 30).",
            "nullable": True,
        },
    }
    output_type = "object"

    def forward(self, limit: int | None = None) -> dict:
        n = max(1, min(int(limit or 10), 30))
        rows = self.session.exec(
            select(FoodEntry)
            .where(FoodEntry.user_uid == self.user.uid)
            .order_by(FoodEntry.eaten_at.desc())
            .limit(n)
        ).all()
        return {"entries": [_entry_summary(e) for e in rows]}


class UpdateFoodTool(_RequestTool):
    name = "update_food"
    description = (
        "Edit an existing diary entry by id. Only the fields you pass are changed; the rest stay "
        "the same. Use list_recent_foods first to find the id. Returns the updated entry."
    )
    inputs = {
        "entry_id": {"type": "integer", "description": "Id of the entry to edit."},
        "name": {"type": "string", "description": "New food name.", "nullable": True},
        "calories": {"type": "integer", "description": "New calorie total.", "nullable": True},
        "meal": {
            "type": "string",
            "description": "breakfast, lunch, dinner or snack.",
            "nullable": True,
        },
        "protein_g": {"type": "number", "description": "New protein grams.", "nullable": True},
        "carb_g": {"type": "number", "description": "New carb grams.", "nullable": True},
        "fat_g": {"type": "number", "description": "New fat grams.", "nullable": True},
        "notes": {"type": "string", "description": "New note.", "nullable": True},
    }
    output_type = "object"

    def forward(
        self,
        entry_id: int,
        name: str | None = None,
        calories: int | None = None,
        meal: str | None = None,
        protein_g: float | None = None,
        carb_g: float | None = None,
        fat_g: float | None = None,
        notes: str | None = None,
    ) -> dict:
        entry = self.session.get(FoodEntry, int(entry_id))
        if entry is None or entry.user_uid != self.user.uid:
            return {"ok": False, "error": f"No diary entry with id {entry_id} for this user."}
        if name is not None:
            entry.name = name.strip()
        if calories is not None:
            entry.calories = int(calories)
        if meal is not None:
            entry.meal = _meal_from_str(meal)
        if protein_g is not None:
            entry.protein_g = protein_g
        if carb_g is not None:
            entry.carb_g = carb_g
        if fat_g is not None:
            entry.fat_g = fat_g
        if notes is not None:
            entry.notes = notes
        entry.updated_at = datetime.now(timezone.utc)
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return {"ok": True, "entry": _entry_summary(entry)}


class DeleteFoodTool(_RequestTool):
    name = "delete_food"
    description = (
        "Delete a diary entry by id. Use list_recent_foods first to find the id. "
        "Confirm with the user before deleting if it's ambiguous which entry they mean."
    )
    inputs = {
        "entry_id": {"type": "integer", "description": "Id of the entry to delete."},
    }
    output_type = "object"

    def forward(self, entry_id: int) -> dict:
        entry = self.session.get(FoodEntry, int(entry_id))
        if entry is None or entry.user_uid != self.user.uid:
            return {"ok": False, "error": f"No diary entry with id {entry_id} for this user."}
        summary = _entry_summary(entry)
        self.session.delete(entry)
        self.session.commit()
        return {"ok": True, "deleted": summary}


class GetMacrosTodayTool(_RequestTool):
    name = "get_macros_today"
    description = (
        "Return today's CONSUMED totals (calories/protein/carb/fat) plus the user's goals. "
        "Use for 'what are my macros today?' / 'how much have I eaten?'."
    )
    inputs = {}
    output_type = "object"

    def forward(self) -> dict:
        return _macros_today(self.session, self.user)


class GetRemainingBudgetTool(_RequestTool):
    name = "get_remaining_budget"
    description = (
        "How many calories and macros are still available today before hitting goals. "
        "Use for 'how much can I still eat?' / 'what's my budget?'."
    )
    inputs = {}
    output_type = "object"

    def forward(self) -> dict:
        snap = _macros_today(self.session, self.user)
        if snap.get("target_kcal") is None:
            return {"message": "No daily calorie goal set. Use set_goal to configure one.", **snap}
        return {
            "remaining_kcal": max(0, (snap["target_kcal"] or 0) - snap["calories"]),
            "remaining_protein_g": max(0, (snap.get("target_protein_g") or 0) - snap["protein_g"]),
            "remaining_carb_g": max(0, (snap.get("target_carb_g") or 0) - snap["carb_g"]),
            "remaining_fat_g": max(0, (snap.get("target_fat_g") or 0) - snap["fat_g"]),
        }


class GetStreakTool(_RequestTool):
    name = "get_streak"
    description = "Return the user's current logging streak in days."
    inputs = {}
    output_type = "object"

    def forward(self) -> dict:
        rows = self.session.exec(
            select(FoodEntry.eaten_at).where(FoodEntry.user_uid == self.user.uid)
        ).all()
        eaten_dates: set = set()
        for r in rows:
            dt = r if isinstance(r, datetime) else r[0]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            eaten_dates.add(dt.date())
        return {"days": nut.streak_from_dates(eaten_dates)}


class AddWaterTool(_RequestTool):
    name = "add_water"
    description = "Log a water intake in millilitres. Default is one 250ml glass."
    inputs = {
        "ml": {"type": "integer", "description": "Millilitres of water. Default 250.", "nullable": True},
    }
    output_type = "object"

    def forward(self, ml: int | None = None) -> dict:
        row = WaterLog(user_uid=self.user.uid, ml=int(ml) if ml else 250)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return {"id": row.id, "ml": row.ml}


class GetUserGoalsTool(_RequestTool):
    name = "get_user_goals"
    description = "Return the user's daily kcal/macro targets and dietary filters, if set."
    inputs = {}
    output_type = "object"

    def forward(self) -> dict:
        goals = self.session.get(UserGoals, self.user.uid)
        if goals is None:
            return {"daily_kcal": None}
        return {
            "daily_kcal": goals.daily_kcal,
            "protein_g": goals.protein_g,
            "carb_g": goals.carb_g,
            "fat_g": goals.fat_g,
            "dietary_filters": goals.dietary_filters,
        }


class SetGoalTool(_RequestTool):
    name = "set_goal"
    description = (
        "Update the user's daily kcal and macro targets. Only the fields you pass are changed."
    )
    inputs = {
        "daily_kcal": {"type": "integer", "description": "Daily calorie target.", "nullable": True},
        "protein_g": {"type": "number", "description": "Daily protein grams.", "nullable": True},
        "carb_g": {"type": "number", "description": "Daily carb grams.", "nullable": True},
        "fat_g": {"type": "number", "description": "Daily fat grams.", "nullable": True},
    }
    output_type = "object"

    def forward(
        self,
        daily_kcal: int | None = None,
        protein_g: float | None = None,
        carb_g: float | None = None,
        fat_g: float | None = None,
    ) -> dict:
        goals = self.session.get(UserGoals, self.user.uid)
        if goals is None:
            goals = UserGoals(user_uid=self.user.uid)
        for field, value in dict(
            daily_kcal=daily_kcal, protein_g=protein_g, carb_g=carb_g, fat_g=fat_g
        ).items():
            if value is not None:
                setattr(goals, field, value)
        self.session.add(goals)
        self.session.commit()
        self.session.refresh(goals)
        return {
            "daily_kcal": goals.daily_kcal,
            "protein_g": goals.protein_g,
            "carb_g": goals.carb_g,
            "fat_g": goals.fat_g,
            "dietary_filters": goals.dietary_filters,
        }


class ComputeTdeeTool(_RequestTool):
    name = "compute_tdee"
    description = (
        "Estimate BMR + TDEE (Mifflin-St Jeor) and suggested macros from body stats."
    )
    inputs = {
        "weight_kg": {"type": "number", "description": "Weight in kilograms."},
        "height_cm": {"type": "number", "description": "Height in centimetres."},
        "age_years": {"type": "integer", "description": "Age in years."},
        "sex": {"type": "string", "description": "'male' or 'female'."},
        "activity_level": {
            "type": "string",
            "description": "sedentary, light, moderate, active, very_active. Default moderate.",
            "nullable": True,
        },
    }
    output_type = "object"

    def forward(
        self,
        weight_kg: float,
        height_cm: float,
        age_years: int,
        sex: str,
        activity_level: str | None = None,
    ) -> dict:
        bmr = nut.mifflin_st_jeor(weight_kg, height_cm, age_years, sex)
        daily = nut.tdee(bmr, activity_level or "moderate")
        return {
            "bmr": bmr,
            "tdee": daily,
            "suggested_macros": nut.suggest_macros(daily, weight_kg=weight_kg),
        }


class AnalyzeImageTool(_RequestTool):
    name = "analyze_image_tool"
    description = (
        "Analyze a meal photo the user attached (given its image_path) and return parsed "
        "nutrition (name, calories, macros, confidence). Call this when the user sends a photo."
    )
    inputs = {
        "image_path": {"type": "string", "description": "Server path of the uploaded image."},
    }
    output_type = "object"

    def forward(self, image_path: str) -> dict:
        from . import vision

        # vision.analyze_image is async; the agent runs in a worker thread with no event loop,
        # so a fresh asyncio.run is safe here.
        extraction = asyncio.run(vision.analyze_image(image_path))
        return extraction.model_dump()


class SearchNutritionTool(_RequestTool):
    name = "search_nutrition"
    description = (
        "Look up nutrition for a BRANDED/packaged product (e.g. 'Coca Cola Zero', 'Pringles') "
        "via Open Food Facts. Returns up to 3 matches with kcal/macros per 100g and per serving. "
        "Do NOT use for generic whole foods you already know."
    )
    inputs = {
        "query": {"type": "string", "description": "Product name to look up."},
    }
    output_type = "object"

    def forward(self, query: str) -> dict:
        import httpx

        # Open Food Facts is a free, best-effort public API — it routinely 503s / times out.
        # A flaky lookup must NOT crash the agent turn; degrade gracefully instead.
        try:
            resp = httpx.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": query,
                    "search_simple": "1",
                    "action": "process",
                    "json": "1",
                    "page_size": "5",
                    "fields": "product_name,brands,nutriments,serving_size,serving_quantity",
                },
                headers={"User-Agent": "SmartCalories/1.0 (calorie-tracker; +https://github.com)"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("search_nutrition lookup failed for %r: %s", query, exc)
            return {
                "found": False,
                "message": (
                    f"The nutrition database is unavailable right now (lookup for '{query}' "
                    "failed). Give your best estimate, or ask the user for the calories."
                ),
            }

        results = []
        for product in data.get("products", [])[:3]:
            nutr = product.get("nutriments", {})
            kcal_100g = nutr.get("energy-kcal_100g") or nutr.get("energy_100g")
            if kcal_100g is None:
                continue
            item: dict = {
                "name": product.get("product_name") or "Unknown",
                "brand": product.get("brands") or "",
                "kcal_per_100g": round(float(kcal_100g), 1),
                "protein_g_per_100g": round(float(nutr.get("proteins_100g") or 0), 1),
                "carb_g_per_100g": round(float(nutr.get("carbohydrates_100g") or 0), 1),
                "fat_g_per_100g": round(float(nutr.get("fat_100g") or 0), 1),
            }
            serving_size = product.get("serving_size") or ""
            serving_qty = product.get("serving_quantity")
            kcal_serving = nutr.get("energy-kcal_serving") or nutr.get("energy_serving")
            if kcal_serving:
                item.update(
                    serving_size=serving_size,
                    kcal_per_serving=round(float(kcal_serving), 1),
                    protein_g_per_serving=round(float(nutr.get("proteins_serving") or 0), 1),
                    carb_g_per_serving=round(float(nutr.get("carbohydrates_serving") or 0), 1),
                    fat_g_per_serving=round(float(nutr.get("fat_serving") or 0), 1),
                )
            elif serving_qty:
                factor = float(serving_qty) / 100.0
                item.update(
                    serving_size=serving_size,
                    kcal_per_serving=round(float(kcal_100g) * factor, 1),
                    protein_g_per_serving=round(float(nutr.get("proteins_100g") or 0) * factor, 1),
                    carb_g_per_serving=round(float(nutr.get("carbohydrates_100g") or 0) * factor, 1),
                    fat_g_per_serving=round(float(nutr.get("fat_100g") or 0) * factor, 1),
                )
            results.append(item)

        if not results:
            return {
                "found": False,
                "message": f"No nutrition data found for '{query}'. Ask the user for the calories.",
            }
        return {"found": True, "results": results}


def build_request_tools(session: Session, user: User) -> list[Tool]:
    """Instantiate the per-request diary tools. `agent.build_agent` appends WebSearchTool."""
    classes = (
        LogFoodTool,
        ListRecentFoodsTool,
        UpdateFoodTool,
        DeleteFoodTool,
        GetMacrosTodayTool,
        GetRemainingBudgetTool,
        GetStreakTool,
        AddWaterTool,
        GetUserGoalsTool,
        SetGoalTool,
        ComputeTdeeTool,
        AnalyzeImageTool,
        SearchNutritionTool,
    )
    return [cls(session, user) for cls in classes]
