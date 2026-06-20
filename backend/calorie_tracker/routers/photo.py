from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from ..ai import vision
from ..deps import CurrentUser, SessionDep
from ..models import FoodEntry, Meal, Source
from ..services.storage import save_upload

router = APIRouter(prefix="/photo", tags=["photo"])


@router.post("/scan", status_code=status.HTTP_200_OK)
async def scan_photo(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    meal: str = Query(default="snack"),
    commit: bool = Query(default=False),
) -> dict:
    """Save the uploaded image, run vision analysis, optionally write a FoodEntry."""
    raw = await file.read()
    saved_path = await run_in_threadpool(save_upload, user.uid, file.filename or "meal.jpg", raw)
    relative_path = str(saved_path)

    extraction = await vision.analyze_image(saved_path)

    entry_dict: dict | None = None
    if commit:
        try:
            meal_enum = Meal(meal.strip().lower())
        except ValueError:
            meal_enum = Meal.snack
        entry = FoodEntry(
            user_uid=user.uid,
            name=extraction.name,
            calories=extraction.calories,
            protein_g=extraction.protein_g,
            carb_g=extraction.carb_g,
            fat_g=extraction.fat_g,
            serving_qty=extraction.serving_qty,
            serving_unit=extraction.serving_unit,
            meal=meal_enum,
            eaten_at=datetime.now(timezone.utc),
            source=Source.photo,
            image_path=relative_path,
            notes=extraction.note,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        entry_dict = {
            "id": entry.id,
            "name": entry.name,
            "calories": entry.calories,
            "meal": entry.meal.value if isinstance(entry.meal, Meal) else str(entry.meal),
        }

    return {
        "image_path": relative_path,
        "extraction": extraction.model_dump(),
        "entry": entry_dict,
    }
